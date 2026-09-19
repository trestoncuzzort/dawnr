"""How large a locallm can this machine actually train, and how fast?

Answers a question the core report left open: it checked that an optimizer step
runs at 312M parameters, which is not the same as knowing the largest model
that trains here, nor whether training it would finish this year. Each size
gets real optimizer steps on real data shapes, and reports parameters, peak
memory, step time and tokens per second, or the fact that it did not fit.

The cards are shared. This measures what was free at the moment it ran, which
is a floor on the machine's capacity, not the machine's capacity.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch

from model import GPT, GPTConfig
import train as core_train

SCHEMA = 1
LADDER = [("91M", 12, 12, 768), ("162M", 16, 16, 1024), ("312M", 24, 16, 1024),
          ("500M", 24, 16, 1280), ("780M", 28, 20, 1600), ("1.2B", 32, 16, 2048),
          ("1.8B", 36, 24, 2304), ("2.7B", 40, 20, 2560)]
for _name, _layers, _heads, _width in LADDER:
    if _width % _heads:
        raise ValueError(f"{_name}: width {_width} does not divide into {_heads} heads")


def free_mib(device):
    free, total = torch.cuda.mem_get_info(device)
    return free // (1024 * 1024), total // (1024 * 1024)


def try_size(name, layers, heads, width, *, args, device):
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    before = free_mib(device)[0]
    record = {"size": name, "n_layer": layers, "n_head": heads, "n_embd": width,
              "batch_size": args.batch_size, "block_size": args.block_size,
              "gradient_checkpointing": args.gradient_checkpointing,
              "free_mib_before": before}
    model = optimizer = None
    try:
        config = GPTConfig(vocab_size=args.vocab_size, block_size=args.block_size,
                           n_layer=layers, n_head=heads, n_embd=width, dropout=0.0,
                           architecture=args.architecture,
                           gradient_checkpointing=args.gradient_checkpointing)
        model = GPT(config).to(device)
        record["parameters"] = sum(p.numel() for p in model.parameters())
        optimizer = core_train.make_optimizer(model, 1e-4)
        inputs = torch.randint(0, args.vocab_size, (args.batch_size, args.block_size),
                               device=device)
        targets = torch.randint(0, args.vocab_size, (args.batch_size, args.block_size),
                                device=device)
        autocast = (torch.autocast(device_type="cuda", dtype=torch.bfloat16)
                    if core_train.wants_bf16(device) else torch.autocast("cpu", enabled=False))
        times = []
        for step in range(args.steps):
            start = time.monotonic()
            with autocast:
                _, loss = model(inputs, targets)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            torch.cuda.synchronize(device)
            times.append(time.monotonic() - start)
            if not torch.isfinite(loss):
                raise RuntimeError("non-finite loss")
        steady = sorted(times)[len(times) // 2]
        record.update(status="trains", median_step_seconds=round(steady, 4),
                      tokens_per_second=round(args.batch_size * args.block_size / steady),
                      peak_allocated_mib=torch.cuda.max_memory_allocated(device) // (1024 * 1024),
                      peak_reserved_mib=torch.cuda.max_memory_reserved(device) // (1024 * 1024),
                      final_loss=float(loss.detach()))
    except torch.OutOfMemoryError as error:
        record.update(status="out_of_memory", detail=str(error)[:160])
    except RuntimeError as error:
        record.update(status="failed", detail=repr(error)[:200])
    finally:
        del model, optimizer
        torch.cuda.empty_cache()
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--block-size", type=int, default=512)
    parser.add_argument("--vocab-size", type=int, default=8192)
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--architecture", choices=("gpt", "modern"), default="gpt")
    parser.add_argument("--gradient-checkpointing", action="store_true")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--only", nargs="*", default=None, help="size labels to measure")
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("this measurement needs a CUDA device")
    device = torch.device(args.device)
    rows = []
    for name, layers, heads, width in LADDER:
        if args.only and name not in args.only:
            continue
        row = try_size(name, layers, heads, width, args=args, device=device)
        rows.append(row)
        print(json.dumps(row), flush=True)
        if row["status"] == "out_of_memory":
            break
    trained = [row for row in rows if row["status"] == "trains"]
    report = {"schema": SCHEMA, "device_name": torch.cuda.get_device_name(device),
              "free_mib_at_start": rows[0]["free_mib_before"] if rows else None,
              "total_mib": free_mib(device)[1],
              "settings": {key: getattr(args, key) for key in
                           ("batch_size", "block_size", "vocab_size", "steps",
                            "architecture", "gradient_checkpointing")},
              "largest_trained": trained[-1] if trained else None, "rows": rows,
              "caveat": "one shared card, measured against the free memory at the time"}
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"largest_trained": report["largest_trained"], "rows": len(rows)}))


if __name__ == "__main__":
    main()
