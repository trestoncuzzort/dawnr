"""Matched forward/backward probe, with optional bounded AdamW scale checks.

Run on the lab workstation with CUDA_VISIBLE_DEVICES set to a card that fits.
The generated JSON records every repeat, shape, version, and model count.
"""
import argparse
import contextlib
import gc
import json
import random
import time
from pathlib import Path

import torch

from model import GPT, GPTConfig


def measure(args, architecture, checkpointing):
    torch.manual_seed(args.seed)
    cfg = GPTConfig(vocab_size=args.vocab_size, block_size=args.context,
                    n_layer=args.layers, n_head=args.heads, n_embd=args.width,
                    architecture=architecture, bias=architecture == "gpt",
                    gradient_checkpointing=checkpointing)
    model = GPT(cfg).to(args.device).train()
    optimizer = (torch.optim.AdamW(model.parameters(), lr=1e-4, fused=args.device == "cuda")
                 if args.optimizer_step else None)
    generator = torch.Generator().manual_seed(args.seed)
    ids = torch.randint(args.vocab_size, (args.batch, args.context), generator=generator).to(args.device)

    def step():
        model.zero_grad(set_to_none=True)
        amp = (torch.autocast("cuda", dtype=torch.bfloat16)
               if args.device == "cuda" and args.dtype == "bfloat16" else contextlib.nullcontext())
        with amp:
            _, loss = model(ids, ids)
        loss.backward()
        if optimizer is not None:
            optimizer.step()
        return loss.detach()

    for _ in range(args.warmup):
        final_loss = step()
    model.zero_grad(set_to_none=True)
    if args.device == "cuda":
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    for _ in range(args.steps):
        final_loss = step()
    if args.device == "cuda":
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    finite = bool(torch.isfinite(final_loss).item()) and all(
        bool(torch.isfinite(p.grad).all().item()) for p in model.parameters() if p.grad is not None)
    if not finite:
        raise RuntimeError("Non-finite loss or gradients at benchmark shape")
    return dict(architecture=architecture, gradient_checkpointing=checkpointing,
                total_params=model.total_params(), ms_per_step=1000 * elapsed / args.steps,
                tokens_per_second=args.batch * args.context * args.steps / elapsed,
                finite_loss_and_gradients=finite,
                peak_allocated_bytes=(torch.cuda.max_memory_allocated() if args.device == "cuda" else None))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--dtype", choices=("float32", "bfloat16"), default="bfloat16")
    parser.add_argument("--vocab-size", type=int, default=8192)
    parser.add_argument("--layers", type=int, default=6)
    parser.add_argument("--heads", type=int, default=8)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--context", type=int, default=512)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=91)
    parser.add_argument("--variant", choices=("all", "gpt", "modern", "modern-checkpoint"),
                        default="all")
    parser.add_argument("--optimizer-step", action="store_true",
                        help="include real AdamW updates for a bounded random-input scale check")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    torch.set_num_threads(4)
    rows = []
    order = random.Random(args.seed)
    for repeat in range(args.repeats):
        variants = [("gpt", False), ("modern", False), ("modern", True)]
        if args.variant != "all":
            variants = [("gpt", False)] if args.variant == "gpt" else [
                ("modern", args.variant == "modern-checkpoint")]
        order.shuffle(variants)
        for architecture, checkpointing in variants:
            gc.collect()
            if args.device == "cuda":
                torch.cuda.empty_cache()
            row = measure(args, architecture, checkpointing)
            rows.append(dict(repeat=repeat, **row))
    result = dict(torch_version=torch.__version__,
                  device=(torch.cuda.get_device_name() if args.device == "cuda" else "cpu"),
                  settings={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
                  rows=rows,
                  limitation="Random inputs; throughput and memory only. No semantic quality measured.")
    rendered = json.dumps(result, indent=2)
    if args.out:
        args.out.write_text(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
