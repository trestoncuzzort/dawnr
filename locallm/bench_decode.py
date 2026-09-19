"""Measure full-prefix and cached generation on the same model and prompt."""
import argparse
import contextlib
import hashlib
import json
import random
import statistics
import time
from pathlib import Path

import torch

from model import GPT, GPTConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--architecture", choices=("gpt", "modern", "both"), default="both")
    parser.add_argument("--layers", type=int, default=8)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--heads", type=int, default=8)
    parser.add_argument("--vocab", type=int, default=8192)
    parser.add_argument("--context", type=int, default=2048)
    parser.add_argument("--prefix", type=int, default=512)
    parser.add_argument("--tokens", type=int, default=128)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if min(args.prefix, args.tokens, args.batch, args.repeats) < 1 or args.warmup < 0:
        parser.error("prefix, tokens, batch and repeats must be positive; warmup cannot be negative")
    device = torch.device(args.device)
    cuda = device.type == "cuda"
    sync = lambda: torch.cuda.synchronize(device) if cuda else None
    precision = lambda: torch.autocast("cuda", dtype=torch.bfloat16) if cuda else contextlib.nullcontext()
    architectures = ("gpt", "modern") if args.architecture == "both" else (args.architecture,)
    report = {"arguments": {**vars(args), "out": str(args.out)}, "torch": torch.__version__,
              "cuda": torch.version.cuda,
              "model_sha256": hashlib.sha256(Path(__file__).with_name("model.py").read_bytes()).hexdigest(),
              "device": torch.cuda.get_device_name(device) if cuda else str(device),
              "dtype": "bfloat16 autocast" if cuda else "float32", "work_checks": [],
              "runs": [], "summary": {}}
    order = random.Random(173)
    for architecture in architectures:
        torch.manual_seed(173)
        cfg = GPTConfig(vocab_size=args.vocab, block_size=args.context, n_layer=args.layers,
                        n_embd=args.width, n_head=args.heads, architecture=architecture)
        model = GPT(cfg).to(device).eval()
        ids = torch.randint(args.vocab, (args.batch, args.prefix), device=device)
        baseline = None
        for cached in (False, True):
            # Untimed instrumentation confirms both paths execute every requested
            # decode step; timing below runs without hooks.
            chunks = []
            handle = model.transformer.h[0].attn.c_attn.register_forward_pre_hook(
                lambda _module, inputs: chunks.append(inputs[0].size(1)))
            try:
                with precision():
                    checked = model.generate(ids, args.tokens, temperature=0, use_cache=cached)
            finally:
                handle.remove()
            assert checked.shape == (args.batch, args.prefix + args.tokens)
            assert len(chunks) == args.tokens
            report["work_checks"].append({"architecture": architecture, "cached": cached,
                                           "decode_steps": len(chunks), "first_layer_tokens": sum(chunks),
                                           "output_length": checked.size(1), "largest_chunk": max(chunks)})
            del checked
            for _ in range(args.warmup):
                with precision():
                    model.generate(ids, args.tokens, temperature=0, use_cache=cached)
        sync()
        for repeat in range(args.repeats):
            variants = [False, True]
            order.shuffle(variants)
            for cached in variants:
                sync()
                if cuda:
                    torch.cuda.reset_peak_memory_stats(device)
                start = time.perf_counter()
                with precision():
                    output = model.generate(ids, args.tokens, temperature=0, use_cache=cached)
                sync()
                elapsed = time.perf_counter() - start
                current = output.cpu()
                assert current.shape == (args.batch, args.prefix + args.tokens)
                if baseline is None:
                    baseline = current
                row = {"architecture": architecture, "cached": cached, "repeat": repeat,
                       "seconds": elapsed, "tokens_per_second": args.batch * args.tokens / elapsed,
                       "peak_allocated_bytes": torch.cuda.max_memory_allocated(device) if cuda else None,
                       "greedy_equal": torch.equal(current, baseline), "params": model.total_params()}
                report["runs"].append(row)
                print(json.dumps(row), flush=True)
        timings = {cached: statistics.median(row["seconds"] for row in report["runs"]
                                           if row["architecture"] == architecture and row["cached"] == cached)
                   for cached in (False, True)}
        report["summary"][architecture] = {"uncached_seconds": timings[False],
                                             "cached_seconds": timings[True],
                                             "speedup": timings[False] / timings[True]}
        del model, output, ids
        if cuda:
            torch.cuda.empty_cache()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
