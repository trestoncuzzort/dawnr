"""Continue training an existing locallm checkpoint on a new corpus.

`train.py` builds a model and a tokenizer from scratch, which is why every
locallm row on the project's scoreboard is a small model that saw only the
pipeline's own tiny corpus. This script is the missing path: take a core that
was pretrained on real source, keep its frozen tokenizer and weights, and
specialize it on the filtered t data.

Identities are recorded before the first update, the training state resumes
exactly, and the export is an ordinary project checkpoint that
`checkpoint.load_checkpoint` and `t/loop_locallm.py generate` already read.

Since the r12 build (schema 2):

* The validation holdout is chosen by `--split-seed` and, by default, by a
  hash of each document's own text (`--split-by hash`), so it does not move
  with `--seed` or with the rest of the corpus. Dodge et al. (arXiv:2002.06305)
  separate the seeds that set initialization and data order; the holdout is a
  third one here. `--split-by order --split-seed <old --seed>` reproduces a run
  from before this change.
* `--deterministic` asks PyTorch for deterministic kernels before any CUDA use
  (docs.pytorch.org/docs/2.14/notes/randomness.html); run.json records what was
  requested and what the process actually got, either way.
* `--doc-batches` trains on one whole document per row (data.DocumentBatches)
  instead of random windows; `--keep-every N` writes weights-only copies of the
  model every N steps for a later stopping-step choice on a dev split (LIMA,
  arXiv:2305.11206, picks its epoch on a dev set rather than by perplexity).
"""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "t"
sys.path.insert(0, str(T))
sys.path.insert(1, str(Path(__file__).resolve().parent))

import loop_filter

# 1: the holdout followed --seed's document order. 2: --split-seed, a hash of
# each document by default, determinism and batching recorded.
SCHEMA = 2
CUBLAS_WORKSPACE = ":4096:8"
RESUME_KEYS = ("init_ckpt_sha256", "corpus_sha256", "evaluation_split_sha256", "seed", "split_seed")
RESUME_PATHS = (("split", "by"), ("batches", "kind"), ("reproducibility", "requested"))


def file_sha256(path):
    value = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def text_sha256(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def load_core(init_dir, device, dropout, torch_module, gpt, config_type):
    checkpoint = torch_module.load(Path(init_dir) / "ckpt.pt", map_location="cpu", weights_only=True)
    checkpoint.pop("optimizer", None)
    config = config_type(**{**checkpoint["config"], "dropout": dropout})
    model = gpt(config)
    model.load_state_dict(checkpoint["model"])
    return model.to(device), config, checkpoint.get("tokenizer_fingerprint")


def configure_determinism(requested: bool, torch_module) -> dict:
    """Ask for deterministic kernels before any CUDA work, and say what was got.

    CUBLAS_WORKSPACE_CONFIG is read once, at the first cuBLAS call
    (aten/src/ATen/cuda/CublasHandlePool.cpp), so it must be in the
    environment before the model touches the device. The flag alone does not
    promise bit identity across releases, platforms or CPU versus GPU
    (docs.pytorch.org/docs/2.14/notes/randomness.html); it is for reruns on
    one machine. Off by default here so every recorded r7-r11 command keeps its
    old behaviour; train_distributed.py defaults it on for its own reasons.
    """
    if requested:
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", CUBLAS_WORKSPACE)
        torch_module.use_deterministic_algorithms(True, warn_only=False)
    return {"requested": bool(requested),
            "use_deterministic_algorithms": bool(torch_module.are_deterministic_algorithms_enabled()),
            "warn_only": bool(torch_module.is_deterministic_algorithms_warn_only_enabled()),
            "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
            "torch": str(torch_module.__version__), "cuda": torch_module.version.cuda}


def document_loss(model, rows, batch_size, torch_module, ignore_index: int) -> float:
    """Token-weighted mean loss over every document exactly once, in fp32."""
    was_training = model.training
    model.eval()
    total, count = 0.0, 0
    with torch_module.no_grad():
        for x, y in rows.in_order(batch_size):
            _, loss = model(x, y)
            n = int((y != ignore_index).sum())
            total += float(loss) * n
            count += n
    if was_training:
        model.train()
    return total / max(count, 1)


def save_kept(model, config, fingerprint, step, out_dir, torch_module) -> Path:
    """A weights-only copy of the model at `step`, written atomically beside the rolling checkpoint."""
    path = Path(out_dir) / f"ckpt-step-{step}.pt"
    temporary = path.with_name(path.name + ".tmp")
    torch_module.save({"model": model.state_dict(), "config": asdict(config),
                       "tokenizer_fingerprint": fingerprint, "step": step}, temporary)
    os.replace(temporary, path)
    return path


def nested(mapping, path):
    for key in path:
        mapping = mapping.get(key) if isinstance(mapping, dict) else None
    return mapping


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
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
    parser.add_argument("--eval-iters", type=int, default=20,
                        help="window mode only; document mode evaluates every document once")
    parser.add_argument("--log-every", type=int, default=25)
    parser.add_argument("--save-every", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1337, help="dropout and the order of the training batches")
    parser.add_argument("--split-seed", type=int, default=1337,
                        help="chooses the validation documents; fixed across --seed. To reproduce a run "
                             "from before schema 2, pass --split-by order --split-seed <its --seed>")
    parser.add_argument("--split-by", choices=("hash", "order"), default="hash",
                        help="hash: each document is held out by its own text (default); "
                             "order: the seeded shuffle every run before r12 used")
    parser.add_argument("--allow-short-holdout", action="store_true",
                        help="continue, and record it, when the holdout is under the floor "
                             "split_verdict uses; otherwise the run refuses and names the share")
    parser.add_argument("--deterministic", action="store_true",
                        help="torch.use_deterministic_algorithms(True) and CUBLAS_WORKSPACE_CONFIG before any CUDA use")
    parser.add_argument("--doc-batches", action="store_true",
                        help="one whole document per training row, padded, instead of random windows")
    parser.add_argument("--keep-every", type=int, default=0,
                        help="write a weights-only ckpt-step-N.pt every N steps (0: off)")
    parser.add_argument("--device", default=None)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    try:
        eval_ids = {int(task_id) for task_id in json.loads(args.split.read_text(encoding="utf-8"))["eval_ids"]}
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read evaluation split {args.split}") from error
    data_text = args.data.read_text(encoding="utf-8")
    validation = loop_filter.validate_training_data(data_text, eval_ids)
    if not validation.ok:
        reasons = []
        if validation.held_out:
            reasons.append(f"contains held-out ids from {args.split}: "
                           f"{loop_filter.held_out_detail(validation.held_out)}")
        if validation.same_task_names or validation.same_task_ids:
            reasons.append(loop_filter.same_task_detail(validation))
        raise ValueError(f"cannot train: {args.data}: " + "; ".join(reasons))

    import torch
    from data import (Corpus, DocumentBatches, IGNORE_INDEX, SPLIT_CLOSE_ENOUGH, _SPLIT_EPS,
                      load_tokenizer, tokenizer_fingerprint)
    from model import GPT, GPTConfig
    import train as core_train

    reproducibility = configure_determinism(args.deterministic, torch)   # before pick_device
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
    corpus = Corpus(data_text, tokenizer, device, val_frac=args.val_frac, grouped=True,
                    seed=args.split_seed, split_by=args.split_by)

    # The hash split's holdout is binomial in the split seed, so its share is
    # checked against the same floor split_verdict applies (0.8 of the request)
    # and recorded. A short holdout is refused by name, never trimmed or swapped.
    n_documents = len(corpus.train_docs) + len(corpus.val_docs)
    val_share = len(corpus.val_text) / max(len(corpus.train_text) + len(corpus.val_text), 1)
    floor = args.val_frac * SPLIT_CLOSE_ENOUGH
    short = val_share < floor - _SPLIT_EPS
    if short and not args.allow_short_holdout:
        raise SystemExit(
            f"the holdout is {val_share:.1%} of the corpus by characters ({len(corpus.val_docs)} of "
            f"{n_documents} documents), under the floor of {floor:.1%} for --val-frac {args.val_frac}: "
            f"choose another --split-seed (the hash split's size varies with it), raise --val-frac, "
            f"or pass --allow-short-holdout to record it and continue")
    if args.doc_batches:
        if not corpus.val_docs:
            raise SystemExit(f"no validation documents at --split-seed {args.split_seed} and --val-frac "
                             f"{args.val_frac}; nothing to evaluate on")
        train_rows = DocumentBatches(corpus.train_docs, tokenizer, args.block_size, args.seed, device)
        val_rows = DocumentBatches(corpus.val_docs, tokenizer, args.block_size, args.seed, device)
        batches = {"kind": "documents", **train_rows.record(),
                   "validation": {k: v for k, v in val_rows.record().items()
                                  if k in ("documents", "target_tokens", "cut_documents", "cut_tokens",
                                           "longest_tokens", "dropped_characters", "blank_line_documents")}}
        print(json.dumps({"doc_batches": batches}), flush=True)
    else:
        if len(corpus.train) <= args.block_size:
            raise ValueError("corpus is smaller than one training window")
        train_rows = val_rows = None
        batches = {"kind": "windows", "order_seed": args.seed, "block_size": args.block_size}
    optimizer = core_train.make_optimizer(model, args.lr)
    identities = {"init": str(args.init), "init_ckpt_sha256": file_sha256(args.init / "ckpt.pt"),
                  "tokenizer_file_sha256": file_sha256(tokenizer_source),
                  "tokenizer_fingerprint": tokenizer_fingerprint(tokenizer),
                  "corpus": str(args.data), "corpus_sha256": file_sha256(args.data),
                  "evaluation_split": str(args.split), "evaluation_split_sha256": file_sha256(args.split),
                  "corpus_train_tokens": int(len(corpus.train)),
                  "corpus_val_tokens": int(len(corpus.val)),
                  "split": {"mode": corpus.split_mode, "by": corpus.split_by, "val_frac": args.val_frac,
                            "seed": args.split_seed, "train_documents": len(corpus.train_docs),
                            "val_documents": len(corpus.val_docs),
                            "train_sha256": text_sha256(corpus.train_text),
                            "val_sha256": text_sha256(corpus.val_text),
                            "val_char_share": val_share, "floor": floor,
                            "short_holdout_allowed": bool(short and args.allow_short_holdout)},
                  "split_seed": args.split_seed, "batches": batches, "reproducibility": reproducibility,
                  "config": asdict(config), "parameters": sum(p.numel() for p in model.parameters()),
                  "steps": args.steps, "batch_size": args.batch_size,
                  "block_size": args.block_size, "lr": args.lr, "warmup": args.warmup,
                  "dropout": args.dropout, "keep_every": args.keep_every,
                  "seed": args.seed}
    state_path, start, kept = args.out / "state.pt", 0, []
    if args.resume and state_path.exists():
        state = torch.load(state_path, map_location=device, weights_only=False)
        if state.get("schema") != SCHEMA:
            raise ValueError(f"cannot resume: state.pt has schema {state.get('schema')}, whose holdout "
                             f"followed --seed; this script writes schema {SCHEMA}")
        for key in RESUME_KEYS:
            if state["identities"].get(key) != identities[key]:
                raise ValueError(f"cannot resume: {key} changed since this run started")
        for path in RESUME_PATHS:
            if nested(state["identities"], path) != nested(identities, path):
                raise ValueError(f"cannot resume: {'.'.join(path)} changed since this run started")
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        torch.set_rng_state(state["rng"])
        # Window batches and dropout draw from the device's generator, so a GPU
        # run that restored only the CPU stream replayed its batch sequence.
        if device.startswith("cuda") and state.get("cuda_rng") is not None:
            torch.cuda.set_rng_state_all(state["cuda_rng"])
        start, kept = state["step"], list(state.get("kept", []))
    (args.out / "run.json").write_text(json.dumps(
        {"schema": SCHEMA, "status": "running", "device": device,
         "identities": identities, "kept": kept}, indent=2, sort_keys=True) + "\n")
    # Copied now rather than at the end, so a kept step is loadable while the run is still going.
    shutil.copyfile(tokenizer_source, args.out / "tokenizer.json")
    autocast = (torch.autocast(device_type="cuda", dtype=torch.bfloat16)
                if core_train.wants_bf16(device) else torch.autocast("cpu", enabled=False))

    def evaluate() -> dict:
        if args.doc_batches:
            return {"train": document_loss(model, train_rows, args.batch_size, torch, IGNORE_INDEX),
                    "val": document_loss(model, val_rows, args.batch_size, torch, IGNORE_INDEX)}
        return core_train.estimate_loss(model, corpus, args.batch_size, args.block_size, args.eval_iters)

    def save_state(step):
        torch.save({"schema": SCHEMA, "model": model.state_dict(),
                    "optimizer": optimizer.state_dict(), "step": step,
                    "identities": identities, "rng": torch.get_rng_state(),
                    "cuda_rng": torch.cuda.get_rng_state_all() if device.startswith("cuda") else None,
                    "kept": kept}, state_path)

    metrics = (args.out / "metrics.jsonl").open("a")
    initial = evaluate()
    started, step, losses = time.monotonic(), start, dict(initial)
    model.train()
    try:
        while step < args.steps:
            if args.doc_batches:
                inputs, targets = train_rows.get_batch(step, args.batch_size)
            else:
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
                losses = evaluate()
                model.train()
            if step % args.log_every == 0 or step == args.steps:
                record = {"step": step, "lr": lr, "train_step_loss": float(loss.detach()),
                          **{key: float(value) for key, value in losses.items()},
                          "eval": "documents" if args.doc_batches else "windows",
                          "seconds": time.monotonic() - started}
                if args.doc_batches:
                    record["epoch"] = step // train_rows.batches_per_epoch(args.batch_size)
                metrics.write(json.dumps(record, sort_keys=True) + "\n")
                metrics.flush()
                print(json.dumps(record), flush=True)
            if args.keep_every and step % args.keep_every == 0:
                path = save_kept(model, config, identities["tokenizer_fingerprint"], step, args.out, torch)
                kept.append({"step": step, "file": path.name})
            if step % args.save_every == 0:
                save_state(step)
    except BaseException as error:
        (args.out / "run.json").write_text(json.dumps(
            {"schema": SCHEMA, "status": "failed", "error": repr(error)[:400],
             "identities": identities, "step": step, "kept": kept}, indent=2, sort_keys=True) + "\n")
        raise
    finally:
        metrics.close()
    save_state(step)
    torch.save({"model": model.state_dict(), "config": asdict(config),
                "tokenizer_fingerprint": identities["tokenizer_fingerprint"]},
               args.out / "ckpt.pt")
    report = {"schema": SCHEMA, "status": "complete", "device": device,
              "identities": identities, "initial_losses": initial, "final_losses": losses,
              "kept": kept, "steps_run": step - start, "train_seconds": time.monotonic() - started,
              "peak_allocated_bytes": (torch.cuda.max_memory_allocated()
                                       if device.startswith("cuda") else 0)}
    (args.out / "run.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"out": str(args.out), "parameters": identities["parameters"],
                      "train_tokens": identities["corpus_train_tokens"],
                      "split": {"by": corpus.split_by, "seed": args.split_seed,
                                "val_documents": len(corpus.val_docs), "val_char_share": round(val_share, 4)},
                      "batches": batches["kind"], "deterministic": reproducibility["use_deterministic_algorithms"],
                      "initial": initial, "final": losses,
                      "seconds": round(report["train_seconds"], 1)}))


if __name__ == "__main__":
    main()
