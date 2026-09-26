"""Measure full-prefix and cached generation on the same model and prompt.

On a CPU, fix the thread count with --threads so repeated runs use the same
cores, and pass --order alternate so the two variants take turns (uncached,
cached, uncached, cached) and see the same load on a shared machine. Every run
records the one-minute load average beside its time. The 2026-09-19 GPU runs
used the defaults: all threads, one shuffled pair per repeat.
"""
import argparse
import contextlib
import hashlib
import json
import os
import platform
import random
import statistics
import time
from pathlib import Path

import torch

from model import GPT, GPTConfig


def load_average():
    """The (1, 5, 15)-minute load averages, or None where there are none (Windows)."""
    return list(os.getloadavg()) if hasattr(os, "getloadavg") else None


def processor_name():
    """The CPU model for the report, from /proc/cpuinfo where it exists."""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def summarize(rows, tokens):
    """Medians and ratios for one architecture's timed rows.

    ``paired_speedups`` divides each repeat's uncached time by the cached time
    measured next to it. ``noise`` is the larger of the two variants' relative
    range, (max - min) / median: a speedup closer to 1 than that is not told
    apart from run-to-run variation on the machine it was measured on.
    """
    seconds = {cached: [row["seconds"] for row in rows if row["cached"] == cached]
               for cached in (False, True)}
    median = {cached: statistics.median(values) for cached, values in seconds.items()}
    pairs = {}
    for row in rows:
        pairs.setdefault(row["repeat"], {})[row["cached"]] = row["seconds"]
    return {"uncached_seconds": median[False], "cached_seconds": median[True],
            "speedup": median[False] / median[True],
            "uncached_ms_per_step": 1000 * median[False] / tokens,
            "cached_ms_per_step": 1000 * median[True] / tokens,
            "paired_speedups": [pair[False] / pair[True] for _, pair in sorted(pairs.items())],
            "noise": max((max(values) - min(values)) / median[cached]
                         for cached, values in seconds.items()),
            "greedy_equal": all(row["greedy_equal"] for row in rows)}


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
    parser.add_argument("--threads", type=int, default=None,
                        help="torch.set_num_threads before building the model; default: torch's own choice")
    parser.add_argument("--order", choices=("shuffle", "alternate"), default="shuffle",
                        help="shuffle: each repeat's pair in random order (the 2026-09-19 GPU runs); "
                             "alternate: uncached then cached every repeat")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if min(args.prefix, args.tokens, args.batch, args.repeats) < 1 or args.warmup < 0:
        parser.error("prefix, tokens, batch and repeats must be positive; warmup cannot be negative")
    if args.threads is not None:
        if args.threads < 1:
            parser.error("threads must be positive")
        torch.set_num_threads(args.threads)
    device = torch.device(args.device)
    cuda = device.type == "cuda"
    sync = lambda: torch.cuda.synchronize(device) if cuda else None
    precision = lambda: torch.autocast("cuda", dtype=torch.bfloat16) if cuda else contextlib.nullcontext()
    architectures = ("gpt", "modern") if args.architecture == "both" else (args.architecture,)
    report = {"arguments": {**vars(args), "out": str(args.out)}, "torch": torch.__version__,
              "cuda": torch.version.cuda, "python": platform.python_version(),
              "model_sha256": hashlib.sha256(Path(__file__).with_name("model.py").read_bytes()).hexdigest(),
              "device": torch.cuda.get_device_name(device) if cuda else str(device),
              "processor": processor_name(), "threads": torch.get_num_threads(),
              "load_average_start": load_average(),
              "dtype": "bfloat16 autocast" if cuda else "float32", "work_checks": [],
              "cached_equals_uncached": {}, "runs": [], "summary": {}}
    order = random.Random(173)
    for architecture in architectures:
        torch.manual_seed(173)
        cfg = GPTConfig(vocab_size=args.vocab, block_size=args.context, n_layer=args.layers,
                        n_embd=args.width, n_head=args.heads, architecture=architecture)
        model = GPT(cfg).to(device).eval()
        ids = torch.randint(args.vocab, (args.batch, args.prefix), device=device)
        baseline = None
        checked = {}
        for cached in (False, True):
            # Untimed instrumentation confirms both paths execute every requested
            # decode step; timing below runs without hooks. A step whose first
            # layer sees more than one position is a prefill or, on the cached
            # path, a rebuild of the full window.
            chunks = []
            handle = model.transformer.h[0].attn.c_attn.register_forward_pre_hook(
                lambda _module, inputs: chunks.append(inputs[0].size(1)))
            try:
                with precision():
                    checked[cached] = model.generate(ids, args.tokens, temperature=0, use_cache=cached).cpu()
            finally:
                handle.remove()
            assert checked[cached].shape == (args.batch, args.prefix + args.tokens)
            assert len(chunks) == args.tokens
            report["work_checks"].append({"architecture": architecture, "cached": cached,
                                           "decode_steps": len(chunks), "first_layer_tokens": sum(chunks),
                                           "output_length": checked[cached].size(1), "largest_chunk": max(chunks),
                                           "multi_token_steps": sum(size > 1 for size in chunks)})
            for _ in range(args.warmup):
                with precision():
                    model.generate(ids, args.tokens, temperature=0, use_cache=cached)
        report["cached_equals_uncached"][architecture] = torch.equal(checked[False], checked[True])
        del checked
        sync()
        for repeat in range(args.repeats):
            variants = [False, True]
            if args.order == "shuffle":
                order.shuffle(variants)
            for cached in variants:
                sync()
                if cuda:
                    torch.cuda.reset_peak_memory_stats(device)
                load = load_average()
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
                       "ms_per_step": 1000 * elapsed / args.tokens,
                       "load_1min": load[0] if load else None,
                       "peak_allocated_bytes": torch.cuda.max_memory_allocated(device) if cuda else None,
                       "greedy_equal": torch.equal(current, baseline), "params": model.total_params()}
                report["runs"].append(row)
                print(json.dumps(row), flush=True)
        report["summary"][architecture] = summarize(
            [row for row in report["runs"] if row["architecture"] == architecture], args.tokens)
        del model, output, ids
        if cuda:
            torch.cuda.empty_cache()
    report["load_average_end"] = load_average()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
