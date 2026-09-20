"""One arm of the latent/execution factorial: frozen identities, resumable state.

The four arms differ in exactly two flags. Everything else is identical by construction:
backbone initialization, dataset, example order, batch composition, optimizer
settings, learning-rate schedule and the synthesis/final-answer loss, and the identities that make that checkable are written into
`run.json` before the first update. Intermediate execution tokens are present
in every arm's input; only their loss mask changes.

Ordinary inference weights are exported separately from the resumable training
state, so nothing in the auxiliary objective reaches a served model.
"""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import shutil
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch

from completion_batch import IGNORE_INDEX, collate, encode_example, encode_segments
from data import load_tokenizer, tokenizer_fingerprint
from model import GPT, GPTConfig
from research_model import ResearchModel
import train as core_train

SCHEMA = 1
ARMS = {"baseline": (False, False), "latent": (True, False),
        "execution": (False, True), "combined": (True, True)}


def file_sha256(path):
    value = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def encode_dataset(rows, tokenizer, block_size):
    """Every arm's examples, in one order, with the two masks kept apart.

    `targets` is the synthesis/final-answer supervision every arm receives.
    `execution_targets` is disjoint from it and is only passed to the arms that
    supervise intermediate states. Overlength examples are dropped here, which
    is before any arm sees them.
    """
    examples, dropped = [], 0
    for row in rows:
        try:
            if row["kind"] == "synthesis":
                encoded = encode_example(tokenizer, row["prompt"], row["completion"],
                                         block_size=block_size)
                execution = [IGNORE_INDEX] * len(encoded["targets"])
            else:
                parts = [(text, role) for text, role in row["parts"]]
                encoded = encode_segments(tokenizer, row["prompt"], parts,
                                          block_size=block_size, supervise_execution=False)
                treated = encode_segments(tokenizer, row["prompt"], parts,
                                          block_size=block_size, supervise_execution=True)
                if treated["inputs"] != encoded["inputs"]:
                    raise AssertionError("treatments disagree on input IDs")
                execution = [target if answer == IGNORE_INDEX else IGNORE_INDEX
                             for target, answer in zip(treated["targets"], encoded["targets"])]
        except ValueError as error:
            if "exceeds context" not in str(error):
                raise
            dropped += 1
            continue
        examples.append({"inputs": encoded["inputs"], "targets": encoded["targets"],
                         "execution": execution, "kind": row["kind"],
                         "task_name": row["task_name"]})
    if not examples:
        raise ValueError("no example survived the context limit")
    return examples, dropped


def batches(examples, *, batch_size, seed, epoch):
    """Order depends on the seed and the epoch only, never on the arm."""
    order = list(range(len(examples)))
    random.Random((seed << 20) + epoch).shuffle(order)
    for start in range(0, len(order) - batch_size + 1, batch_size):
        yield [examples[index] for index in order[start:start + batch_size]]


def to_tensors(batch, device):
    inputs, targets, segments = collate(batch, device=device)
    execution = torch.full_like(targets, IGNORE_INDEX)
    for row, example in enumerate(batch):
        n = len(example["execution"])
        execution[row, :n] = torch.tensor(example["execution"], device=device)
    return inputs, targets, segments, execution


def build(init_dir, arm, device, dropout):
    """Backbone from the frozen study checkpoint; auxiliary modules on top."""
    checkpoint = torch.load(Path(init_dir) / "ckpt.pt", map_location="cpu", weights_only=True)
    checkpoint.pop("optimizer", None)
    config = GPTConfig(**{**checkpoint["config"], "dropout": dropout})
    core = GPT(config)
    core.load_state_dict(checkpoint["model"])
    latent, execution = ARMS[arm]
    model = ResearchModel(core, latent=latent, execution_weight=1.0 if execution else 0.0)
    return model.to(device), config, checkpoint.get("tokenizer_fingerprint")


def parameter_counts(model):
    backbone = sum(p.numel() for p in model.core.parameters())
    auxiliary = 0 if model.auxiliary is None else sum(p.numel() for p in model.auxiliary.parameters())
    return {"backbone": backbone, "auxiliary": auxiliary, "total": backbone + auxiliary}


def save_state(path, model, optimizer, step, identities, accounting):
    torch.save({"schema": SCHEMA, "wrapper": model.state_dict(),
                "optimizer": optimizer.state_dict(), "step": step,
                "identities": identities, "accounting": accounting,
                "rng": {"cpu": torch.get_rng_state(),
                        "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []}},
               path)


def export_inference(out, model, config, fingerprint, tokenizer_source):
    """Core-only weights in the project's own checkpoint schema."""
    torch.save({"model": model.inference_state_dict(), "config": asdict(config),
                "tokenizer_fingerprint": fingerprint}, out / "ckpt.pt")
    shutil.copyfile(tokenizer_source, out / "tokenizer.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--init", type=Path, required=True, help="frozen study arm directory")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--arm", choices=sorted(ARMS), required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--updates", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--block-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--dropout", type=float, default=0.0)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--log-every", type=int, default=25)
    parser.add_argument("--save-every", type=int, default=250)
    parser.add_argument("--device", default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", type=int, default=0,
                        help="stop after N updates without writing an inference export")
    args = parser.parse_args()

    device = args.device or core_train.pick_device()
    args.out.mkdir(parents=True, exist_ok=True)
    tokenizer_source = Path(args.init) / "tokenizer.json"
    tokenizer = load_tokenizer(tokenizer_source)
    rows = [json.loads(line) for line in
            (args.dataset / "train.jsonl").read_text().splitlines() if line]
    examples, dropped = encode_dataset(rows, tokenizer, args.block_size)
    manifest = json.loads((args.dataset / "manifest.json").read_text())
    identities = {"arm": args.arm, "seed": args.seed, "updates": args.updates,
                  "batch_size": args.batch_size, "block_size": args.block_size,
                  "lr": args.lr, "warmup": args.warmup, "dropout": args.dropout,
                  "dataset_files": manifest["files"], "dataset_seed": manifest["seed"],
                  "init": str(args.init), "init_ckpt_sha256": file_sha256(args.init / "ckpt.pt"),
                  "tokenizer_file_sha256": file_sha256(tokenizer_source),
                  "tokenizer_fingerprint": tokenizer_fingerprint(tokenizer),
                  "examples": len(examples), "dropped_overlength": dropped,
                  "example_order_sha256": sha256(
                      json.dumps([e["task_name"] for e in examples]).encode()).hexdigest(),
                  "latent": ARMS[args.arm][0], "execution": ARMS[args.arm][1]}

    torch.manual_seed(args.seed)
    if device.startswith("cuda"):
        torch.cuda.manual_seed_all(args.seed)
        torch.cuda.reset_peak_memory_stats()
    model, config, fingerprint = build(args.init, args.arm, device, args.dropout)
    if fingerprint and fingerprint != identities["tokenizer_fingerprint"]:
        raise ValueError("initialization checkpoint and tokenizer disagree")
    optimizer = core_train.make_optimizer(model, args.lr)
    identities["parameters"] = parameter_counts(model)
    accounting = {"input_tokens": 0, "answer_tokens": 0, "execution_tokens_supervised": 0,
                  "execution_tokens_present": 0, "updates": 0, "train_seconds": 0.0}

    state_path = args.out / "state.pt"
    start = 0
    if args.resume and state_path.exists():
        state = torch.load(state_path, map_location=device, weights_only=False)
        for key in ("arm", "seed", "dataset_files", "init_ckpt_sha256", "example_order_sha256"):
            if state["identities"][key] != identities[key]:
                raise ValueError(f"cannot resume: {key} changed since this run started")
        model.load_state_dict(state["wrapper"])
        optimizer.load_state_dict(state["optimizer"])
        torch.set_rng_state(state["rng"]["cpu"])
        if state["rng"]["cuda"] and torch.cuda.is_available():
            torch.cuda.set_rng_state_all(state["rng"]["cuda"])
        start, accounting = state["step"], state["accounting"]

    (args.out / "run.json").write_text(json.dumps(
        {"schema": SCHEMA, "status": "running", "device": device,
         "identities": identities}, indent=2, sort_keys=True) + "\n")
    metrics = (args.out / "metrics.jsonl").open("a")
    autocast = (torch.autocast(device_type="cuda", dtype=torch.bfloat16)
                if core_train.wants_bf16(device) else torch.autocast("cpu", enabled=False))
    limit = args.dry_run or args.updates
    step, started = start, time.monotonic()
    model.train()
    try:
        # Resume re-enters the same epoch at the same offset, so the batch a
        # resumed arm sees next is the one an uninterrupted arm would have seen.
        per_epoch = max(len(examples) // args.batch_size, 1)
        epoch, skip = divmod(start, per_epoch)
        stream = batches(examples, batch_size=args.batch_size, seed=args.seed, epoch=epoch)
        for _ in range(skip):
            next(stream, None)
        while step < limit:
            try:
                batch = next(stream)
            except StopIteration:
                epoch += 1
                stream = batches(examples, batch_size=args.batch_size, seed=args.seed, epoch=epoch)
                continue
            inputs, targets, segments, execution = to_tensors(batch, device)
            lr = core_train.cosine_lr(step, args.warmup, args.updates, args.lr, args.lr / 10)
            for group in optimizer.param_groups:
                group["lr"] = lr
            with autocast:
                _, losses = model(inputs, targets, segments,
                                  execution_targets=execution if ARMS[args.arm][1] else None)
            total = losses["total"]
            if not torch.isfinite(total):
                raise RuntimeError(f"non-finite loss at update {step}")
            optimizer.zero_grad(set_to_none=True)
            total.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
            optimizer.step()
            step += 1
            accounting["updates"] = step
            accounting["input_tokens"] += int((segments >= 0).sum())
            accounting["answer_tokens"] += int((targets != IGNORE_INDEX).sum())
            accounting["execution_tokens_present"] += int((execution != IGNORE_INDEX).sum())
            if ARMS[args.arm][1]:
                accounting["execution_tokens_supervised"] += int((execution != IGNORE_INDEX).sum())
            if step % args.log_every == 0 or step == limit:
                record = {"step": step, "lr": lr,
                          **{name: float(value.detach()) for name, value in losses.items()
                             if name != "pairs" and torch.is_tensor(value)},
                          "seconds": time.monotonic() - started}
                metrics.write(json.dumps(record, sort_keys=True) + "\n")
                metrics.flush()
                print(json.dumps(record), flush=True)
            if step % args.save_every == 0:
                accounting["train_seconds"] = time.monotonic() - started
                save_state(state_path, model, optimizer, step, identities, accounting)
    except BaseException as error:
        accounting["train_seconds"] = time.monotonic() - started
        (args.out / "run.json").write_text(json.dumps(
            {"schema": SCHEMA, "status": "failed", "device": device, "error": repr(error)[:400],
             "identities": identities, "accounting": accounting}, indent=2, sort_keys=True) + "\n")
        raise
    finally:
        metrics.close()

    accounting["train_seconds"] = time.monotonic() - started
    save_state(state_path, model, optimizer, step, identities, accounting)
    if not args.dry_run:
        export_inference(args.out, model, config, identities["tokenizer_fingerprint"],
                         tokenizer_source)
    peak = (torch.cuda.max_memory_allocated() if device.startswith("cuda") else 0)
    report = {"schema": SCHEMA, "status": "complete" if not args.dry_run else "dry_run",
              "device": device, "identities": identities, "accounting": accounting,
              "peak_allocated_bytes": peak,
              "final_losses": {name: float(value.detach()) for name, value in losses.items()
                               if torch.is_tensor(value)}}
    (args.out / "run.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"arm": args.arm, "seed": args.seed, "updates": accounting["updates"],
                      "peak_allocated_bytes": peak,
                      "answer_tokens": accounting["answer_tokens"],
                      "execution_tokens_supervised": accounting["execution_tokens_supervised"],
                      "train_seconds": round(accounting["train_seconds"], 1)}))


if __name__ == "__main__":
    main()
