"""Continue training an existing locallm checkpoint on a new corpus.

`train.py` builds a model and a tokenizer from scratch, which is why every
locallm row on the project's scoreboard is a small model that saw only the
pipeline's own tiny corpus. This script is the missing path: take a core that
was pretrained on real source, keep its frozen tokenizer and weights, and
specialize it on the filtered t data.

Identities are recorded before the first update, the training state resumes
exactly, and the export is an ordinary project checkpoint that
`checkpoint.load_checkpoint` and `t/loop_locallm.py generate` already read.
"""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "t"
sys.path.insert(0, str(T))
sys.path.insert(1, str(Path(__file__).resolve().parent))

import loop_filter

SCHEMA = 1


def file_sha256(path):
    value = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_core(init_dir, device, dropout, torch_module, gpt, config_type):
    checkpoint = torch_module.load(Path(init_dir) / "ckpt.pt", map_location="cpu", weights_only=True)
    checkpoint.pop("optimizer", None)
    config = config_type(**{**checkpoint["config"], "dropout": dropout})
    model = gpt(config)
    model.load_state_dict(checkpoint["model"])
    return model.to(device), config, checkpoint.get("tokenizer_fingerprint")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init", type=Path, required=True, help="checkpoint directory to continue")
    parser.add_argument("--data", type=Path, required=True, help="corpus .txt")
    parser.add_argument("--split", type=Path, required=True,
                        help="evaluation split whose eval_ids must be absent from --data")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--block-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=3e-5,
                        help="low by default: this continues a trained core rather than starting one")
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--dropout", type=float, default=0.0)
    parser.add_argument("--val-frac", type=float, default=0.1)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--eval-every", type=int, default=50)
    parser.add_argument("--eval-iters", type=int, default=20)
    parser.add_argument("--log-every", type=int, default=25)
    parser.add_argument("--save-every", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--device", default=None)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    try:
        eval_ids = {int(task_id) for task_id in json.loads(args.split.read_text(encoding="utf-8"))["eval_ids"]}
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read evaluation split {args.split}") from error
    data_text = args.data.read_text(encoding="utf-8")
    leaked = loop_filter.held_out_ids_in(data_text, eval_ids)
    if leaked:
        names = "; ".join(f"{task_id} ({', '.join(sorted(spellings))})"
                          for task_id, spellings in sorted(leaked.items()))
        raise ValueError(f"cannot train: {args.data} contains held-out ids from {args.split}: {names}")

    import torch
    from data import Corpus, load_tokenizer, tokenizer_fingerprint
    from model import GPT, GPTConfig
    import train as core_train

    device = args.device or core_train.pick_device()
    args.out.mkdir(parents=True, exist_ok=True)
    tokenizer_source = Path(args.init) / "tokenizer.json"
    tokenizer = load_tokenizer(tokenizer_source)
    torch.manual_seed(args.seed)
    if device.startswith("cuda"):
        torch.cuda.manual_seed_all(args.seed)
        torch.cuda.reset_peak_memory_stats()
    model, config, fingerprint = load_core(args.init, device, args.dropout, torch, GPT, GPTConfig)
    if fingerprint and fingerprint != tokenizer_fingerprint(tokenizer):
        raise ValueError("initialization checkpoint and its tokenizer disagree")
    if tokenizer.vocab_size != config.vocab_size:
        raise ValueError("tokenizer and embedding table disagree on vocabulary size")
    corpus = Corpus(data_text, tokenizer, device,
                    val_frac=args.val_frac, grouped=True, seed=args.seed)
    if len(corpus.train) <= args.block_size:
        raise ValueError("corpus is smaller than one training window")
    optimizer = core_train.make_optimizer(model, args.lr)
    identities = {"init": str(args.init), "init_ckpt_sha256": file_sha256(args.init / "ckpt.pt"),
                  "tokenizer_file_sha256": file_sha256(tokenizer_source),
                  "tokenizer_fingerprint": tokenizer_fingerprint(tokenizer),
                  "corpus": str(args.data), "corpus_sha256": file_sha256(args.data),
                  "evaluation_split": str(args.split), "evaluation_split_sha256": file_sha256(args.split),
                  "corpus_train_tokens": int(len(corpus.train)),
                  "corpus_val_tokens": int(len(corpus.val)),
                  "split": {"mode": corpus.split_mode, "val_frac": args.val_frac, "seed": args.seed},
                  "config": asdict(config), "parameters": sum(p.numel() for p in model.parameters()),
                  "steps": args.steps, "batch_size": args.batch_size,
                  "block_size": args.block_size, "lr": args.lr, "warmup": args.warmup,
                  "seed": args.seed}
    state_path, start = args.out / "state.pt", 0
    if args.resume and state_path.exists():
        state = torch.load(state_path, map_location=device, weights_only=False)
        for key in ("init_ckpt_sha256", "corpus_sha256", "evaluation_split_sha256", "seed"):
            if state["identities"].get(key) != identities[key]:
                raise ValueError(f"cannot resume: {key} changed since this run started")
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        torch.set_rng_state(state["rng"])
        start = state["step"]
    (args.out / "run.json").write_text(json.dumps(
        {"schema": SCHEMA, "status": "running", "device": device,
         "identities": identities}, indent=2, sort_keys=True) + "\n")
    autocast = (torch.autocast(device_type="cuda", dtype=torch.bfloat16)
                if core_train.wants_bf16(device) else torch.autocast("cpu", enabled=False))
    metrics = (args.out / "metrics.jsonl").open("a")
    initial = core_train.estimate_loss(model, corpus, args.batch_size, args.block_size,
                                       args.eval_iters)
    started, step, losses = time.monotonic(), start, dict(initial)
    model.train()
    try:
        while step < args.steps:
            inputs, targets = corpus.get_batch("train", args.batch_size, args.block_size)
            lr = core_train.cosine_lr(step, args.warmup, args.steps, args.lr, args.lr / 10)
            for group in optimizer.param_groups:
                group["lr"] = lr
            with autocast:
                _, loss = model(inputs, targets)
            if not torch.isfinite(loss):
                raise RuntimeError(f"non-finite loss at step {step}")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
            optimizer.step()
            step += 1
            if step % args.eval_every == 0 or step == args.steps:
                losses = core_train.estimate_loss(model, corpus, args.batch_size,
                                                  args.block_size, args.eval_iters)
                model.train()
            if step % args.log_every == 0 or step == args.steps:
                record = {"step": step, "lr": lr, "train_step_loss": float(loss.detach()),
                          **{key: float(value) for key, value in losses.items()},
                          "seconds": time.monotonic() - started}
                metrics.write(json.dumps(record, sort_keys=True) + "\n")
                metrics.flush()
                print(json.dumps(record), flush=True)
            if step % args.save_every == 0:
                torch.save({"schema": SCHEMA, "model": model.state_dict(),
                            "optimizer": optimizer.state_dict(), "step": step,
                            "identities": identities, "rng": torch.get_rng_state()}, state_path)
    except BaseException as error:
        (args.out / "run.json").write_text(json.dumps(
            {"schema": SCHEMA, "status": "failed", "error": repr(error)[:400],
             "identities": identities, "step": step}, indent=2, sort_keys=True) + "\n")
        raise
    finally:
        metrics.close()
    torch.save({"schema": SCHEMA, "model": model.state_dict(),
                "optimizer": optimizer.state_dict(), "step": step,
                "identities": identities, "rng": torch.get_rng_state()}, state_path)
    torch.save({"model": model.state_dict(), "config": asdict(config),
                "tokenizer_fingerprint": identities["tokenizer_fingerprint"]},
               args.out / "ckpt.pt")
    shutil.copyfile(tokenizer_source, args.out / "tokenizer.json")
    report = {"schema": SCHEMA, "status": "complete", "device": device,
              "identities": identities, "initial_losses": initial, "final_losses": losses,
              "steps_run": step - start, "train_seconds": time.monotonic() - started,
              "peak_allocated_bytes": (torch.cuda.max_memory_allocated()
                                       if device.startswith("cuda") else 0)}
    (args.out / "run.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"out": str(args.out), "parameters": identities["parameters"],
                      "train_tokens": identities["corpus_train_tokens"],
                      "initial": initial, "final": losses,
                      "seconds": round(report["train_seconds"], 1)}))


if __name__ == "__main__":
    main()
