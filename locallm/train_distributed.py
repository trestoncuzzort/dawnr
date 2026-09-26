"""Train the local core with torchrun, one process per GPU, with exact step-boundary resume.

    torchrun --standalone --nproc-per-node=4 locallm/train_distributed.py \
        --data corpus.txt --preset core-medium --steps 2000 --out locallm/out/distributed

The corpus and batch RNG stay in CPU memory. Only each microbatch moves to the
rank's GPU. Checkpoints include the optimizer, learning-rate horizon, tokenizer
identity and every rank's RNG states; changing those inputs on resume is refused.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import platform
import random
import shutil
import time
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP

from data import CharTokenizer, Corpus, build_tokenizer, load_tokenizer, tokenizer_fingerprint
from model import GPT, GPTConfig
from train import BETAS, MODEL_PRESETS, auto_lr, cosine_lr, decay_split, enable_fast_math, make_optimizer

HERE = Path(__file__).resolve().parent
SCHEMA = 2
EVAL_SEED = 12345


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", required=True)
    parser.add_argument("--validation-data", help="an already separated validation file; neither file is resplit")
    parser.add_argument("--out", default=str(HERE / "out/distributed"))
    parser.add_argument("--preset", choices=MODEL_PRESETS, default="core-small")
    parser.add_argument("--architecture", choices=("gpt", "modern"), default="modern")
    parser.add_argument("--tokenizer", choices=("char", "bpe"), default="bpe")
    parser.add_argument("--tokenizer-file", help="copy a frozen tokenizer for a new run; verify that copy on resume")
    parser.add_argument("--vocab-size", type=int, default=8192)
    for name in ("block-size", "n-layer", "n-head", "n-embd"):
        parser.add_argument("--" + name, type=int)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--gradient-checkpointing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--steps", type=int, default=2000, help="fixed schedule horizon, unchanged when resuming")
    parser.add_argument("--stop-after", type=int, help="save and exit after this total number of optimizer steps")
    parser.add_argument("--batch-size", type=int, default=1, help="microbatch size per rank")
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--lr", type=float)
    parser.add_argument("--weight-decay", type=float, default=0.1,
                        help="AdamW decay on tensors with 2 or more dimensions only (train.decay_groups); "
                             "0.1 is what every recorded run used, the r12 sweep runs 0.8")
    parser.add_argument("--warmup-steps", type=int)
    parser.add_argument("--seed", type=int, default=1337, help="model initialization/dropout and batch streams")
    parser.add_argument("--split-seed", type=int, default=1337, help="fixed document split and tokenizer training split")
    parser.add_argument("--val-frac", type=float, default=0.1)
    parser.add_argument("--eval-every", type=int, default=100)
    parser.add_argument("--eval-iters", type=int, default=10)
    parser.add_argument("--save-every", type=int, default=50)
    parser.add_argument("--cpu-threads", type=int, default=4)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--bf16", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--deterministic", action=argparse.BooleanOptionalAction, default=True,
                        help="deterministic CUDA kernels and stable DDP reduction order across resume")
    parser.add_argument("--log-every", type=int, default=1, help="stdout optimizer-step interval; 0 prints evaluations only")
    parser.add_argument("--resume", action="store_true", help="resume --out/ckpt.pt at its next optimizer step")
    args = parser.parse_args(argv)
    for name, value in MODEL_PRESETS[args.preset].items():
        if getattr(args, name) is None:
            setattr(args, name, value)
    if args.lr is None:
        args.lr = auto_lr(args.n_embd)
    if args.warmup_steps is None:
        args.warmup_steps = min(args.steps, max(1, args.steps // 20))
    positive = ("steps", "batch_size", "grad_accum", "eval_every", "eval_iters", "save_every", "cpu_threads")
    if any(getattr(args, name) < 1 for name in positive):
        parser.error("steps, batch sizes, intervals, eval-iters and cpu-threads must be positive")
    if (not 0 < args.val_frac < 1 or args.lr <= 0 or args.weight_decay < 0 or args.warmup_steps < 0
            or args.log_every < 0):
        parser.error("invalid validation fraction, learning rate, weight decay or warm-up")
    if args.stop_after is not None and not 0 < args.stop_after <= args.steps:
        parser.error("--stop-after must be within the unchanged --steps horizon")
    return args


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, value: dict) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def training_identity(args, cfg: GPTConfig, corpus: Corpus, text: str, token_hash: str, world: int) -> dict:
    explicit = args.validation_data is not None
    return {"model": asdict(cfg), "world_size": world, "tokenizer_fingerprint": token_hash,
            "tokenizer": {"kind": args.tokenizer, "requested_vocab_size": args.vocab_size},
            "source": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                       for name in ("train_distributed.py", "model.py", "data.py", "train.py")},
            "data": {"corpus_sha256": digest(text), "train_sha256": digest(corpus.train_text),
                     "val_sha256": digest(corpus.val_text), "split_mode": "explicit" if explicit else "grouped",
                     "split_seed": None if explicit else args.split_seed,
                     "val_frac": None if explicit else args.val_frac},
            "training": {name: getattr(args, name) for name in
                         ("steps", "batch_size", "grad_accum", "lr", "warmup_steps", "seed", "bf16", "device",
                          "deterministic", "cpu_threads")},
            # Its own key rather than a "training" entry, so run_pretraining_study's
            # check of the recorded training keys and every ledger written before
            # r12 still read the same; a resume with another decay is refused here.
            "optimizer": {"kind": "AdamW", "betas": list(BETAS), "weight_decay": args.weight_decay,
                          "decay": "tensors with 2 or more dimensions, as nanoGPT configure_optimizers "
                                   "(raw.githubusercontent.com/karpathy/nanoGPT/master/model.py)"},
            "evaluation": {"iters": args.eval_iters, "seed": EVAL_SEED, "loss_units": "nats/token"},
            "runtime": {"python": platform.python_version(), "torch": str(torch.__version__),
                        "cuda": torch.version.cuda, "cudnn": torch.backends.cudnn.version(),
                        "device_name": torch.cuda.get_device_name() if args.device == "cuda" else "cpu"},
            "reproducibility": {"ddp_buckets": "registration_order" if args.deterministic else "adaptive",
                                "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG")
                                if args.device == "cuda" else None}}


def capture_rng(generator: torch.Generator, device: torch.device) -> dict:
    return {"python": random.getstate(), "torch": torch.get_rng_state(), "batch": generator.get_state(),
            "cuda": torch.cuda.get_rng_state(device).cpu() if device.type == "cuda" else None}


def restore_rng(state: dict, generator: torch.Generator, device: torch.device) -> None:
    random.setstate(state["python"])
    torch.set_rng_state(state["torch"].cpu())
    generator.set_state(state["batch"].cpu())
    if device.type == "cuda":
        torch.cuda.set_rng_state(state["cuda"].cpu(), device)


def validate_resume(checkpoint: dict, identity: dict) -> None:
    if checkpoint.get("distributed_schema") != SCHEMA:
        raise ValueError("Checkpoint is not a resumable distributed training checkpoint")
    if checkpoint.get("identity") != identity:
        differences = [key for key in identity if checkpoint.get("identity", {}).get(key) != identity[key]]
        raise ValueError("Resume inputs changed: " + ", ".join(differences))
    step = checkpoint.get("step")
    if not isinstance(step, int) or not 0 <= step <= identity["training"]["steps"]:
        raise ValueError("Checkpoint has an invalid completed-step count")
    if len(checkpoint.get("rank_rng", [])) != identity["world_size"]:
        raise ValueError("Checkpoint is missing rank RNG states")


def save_checkpoint(path: Path, model: GPT, optimizer, completed: int, identity: dict,
                    generator: torch.Generator, device: torch.device, rank: int, world: int,
                    losses: dict, initial_losses: dict) -> None:
    # The optimizer step has completed on every rank before its state is published.
    dist.barrier()
    rngs = [None] * world
    dist.all_gather_object(rngs, capture_rng(generator, device))
    if rank == 0:
        checkpoint = {"distributed_schema": SCHEMA, "model": model.state_dict(), "config": asdict(model.config),
                      "tokenizer_fingerprint": identity["tokenizer_fingerprint"], "optimizer": optimizer.state_dict(),
                      "step": completed, "identity": identity, "rank_rng": rngs, "losses": losses,
                      "initial_losses": initial_losses}
        temporary = path.with_name(path.name + ".tmp")
        torch.save(checkpoint, temporary)
        temporary.replace(path)
    dist.barrier()


def get_batch(corpus: Corpus, split: str, args, generator: torch.Generator, device: torch.device):
    x, y = corpus.get_batch(split, args.batch_size, args.block_size, generator=generator)
    if device.type == "cuda":
        x, y = x.pin_memory().to(device, non_blocking=True), y.pin_memory().to(device, non_blocking=True)
    return x, y


def autocast(args, device: torch.device):
    return torch.autocast(device_type=device.type, dtype=torch.bfloat16) if args.bf16 else contextlib.nullcontext()


def require_validation_coverage(tokenizer, validation_text: str) -> None:
    if isinstance(tokenizer, CharTokenizer):
        missing = set(validation_text) - set(tokenizer.chars)
        if missing:
            raise ValueError(f"Character tokenizer would discard {len(missing)} validation characters; use byte-level BPE")


def check_tokenizer_request(args, output_file: Path) -> None:
    if args.tokenizer_file and hashlib.sha256(Path(args.tokenizer_file).read_bytes()).digest() != hashlib.sha256(output_file.read_bytes()).digest():
        raise ValueError("Requested frozen tokenizer differs from the run's saved tokenizer")
    tokenizer = load_tokenizer(output_file)
    if isinstance(tokenizer, CharTokenizer) != (args.tokenizer == "char"):
        raise ValueError("Saved tokenizer kind differs from --tokenizer")


def prepare_metrics(path: Path, completed: int, initial_losses: dict, resume: bool) -> None:
    # A process may die after writing metrics but before its checkpoint is published.
    # Remove those uncommitted rows on resume, retaining the original step-zero baseline.
    rows = [{"step": 0, **initial_losses}]
    if resume and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if 0 < row.get("step", 0) <= completed:
                rows.append(row)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    temporary.replace(path)


def append_metric(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, sort_keys=True) + "\n")


@torch.no_grad()
def estimate_loss(model: GPT, corpus: Corpus, args, device: torch.device, rank: int, world: int) -> dict:
    generator = torch.Generator(device="cpu").manual_seed(EVAL_SEED + rank)
    was_training = model.training
    model.eval()
    values = torch.zeros(2, device=device, dtype=torch.float64)
    try:
        for index, split in enumerate(("train", "val")):
            for _ in range(args.eval_iters):
                x, y = get_batch(corpus, split, args, generator, device)
                with autocast(args, device):
                    _, loss = model(x, y)
                values[index] += loss.detach().double()
        dist.all_reduce(values)
        values /= args.eval_iters * world
        if not torch.isfinite(values).all():
            raise FloatingPointError("Nonfinite evaluation loss")
        return {"train_nats_per_token": values[0].item(), "val_nats_per_token": values[1].item()}
    finally:
        model.train(was_training)


def run(args, rank: int, world: int, local_rank: int) -> dict | None:
    torch.set_num_threads(args.cpu_threads)
    torch.set_num_interop_threads(1)
    device = torch.device("cuda", local_rank) if args.device == "cuda" else torch.device("cpu")
    if device.type == "cuda":
        torch.cuda.set_device(device)
        if args.bf16 and not torch.cuda.is_bf16_supported():
            raise ValueError("Selected CUDA device does not support requested BF16")
        torch.cuda.reset_peak_memory_stats(device)
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if device.type == "cuda":
        torch.cuda.manual_seed(args.seed + rank)
        enable_fast_math()

    out = Path(args.out)
    text = Path(args.data).read_bytes().decode("utf-8")
    validation_text = Path(args.validation_data).read_bytes().decode("utf-8") if args.validation_data else None
    if validation_text is not None and validation_text == text:
        raise ValueError("Explicit training and validation files are identical")
    if rank == 0:
        out.mkdir(parents=True, exist_ok=True)
        if args.resume:
            if not (out / "ckpt.pt").is_file() or not (out / "tokenizer.json").is_file():
                raise ValueError("Resume needs both ckpt.pt and tokenizer.json")
        else:
            if (out / "ckpt.pt").exists():
                raise ValueError("Output already contains a checkpoint; use --resume or a new output directory")
            if args.tokenizer_file:
                shutil.copyfile(args.tokenizer_file, out / "tokenizer.json.tmp")
            else:
                tokenizer = build_tokenizer(text, kind=args.tokenizer, vocab_size=args.vocab_size,
                                            val_frac=args.val_frac, seed=args.split_seed,
                                            training_text=text if validation_text is not None else None)
                tokenizer.save(out / "tokenizer.json.tmp")
            (out / "tokenizer.json.tmp").replace(out / "tokenizer.json")
    dist.barrier()
    check_tokenizer_request(args, out / "tokenizer.json")
    tokenizer = load_tokenizer(out / "tokenizer.json")
    if validation_text is not None:
        require_validation_coverage(tokenizer, validation_text)
    token_hash = tokenizer_fingerprint(tokenizer)
    fingerprints = [None] * world
    dist.all_gather_object(fingerprints, token_hash)
    if len(set(fingerprints)) != 1:
        raise ValueError("Ranks loaded different tokenizers")
    corpus = Corpus(text, tokenizer, "cpu", val_frac=args.val_frac, seed=args.split_seed,
                    validation_text=validation_text)
    if min(len(corpus.train), len(corpus.val)) <= args.block_size:
        raise ValueError("Both document splits must contain more tokens than --block-size")
    cfg = GPTConfig(vocab_size=tokenizer.vocab_size, block_size=args.block_size, n_layer=args.n_layer,
                    n_head=args.n_head, n_embd=args.n_embd, dropout=args.dropout,
                    bias=args.architecture == "gpt", architecture=args.architecture,
                    gradient_checkpointing=args.gradient_checkpointing)
    identity = training_identity(args, cfg, corpus, text, token_hash, world)
    model = GPT(cfg).to(device)
    # Default DDP rebuilds buckets after its first backward. A restarted process
    # would then reduce the next step in a different floating-point order. Dynamic
    # unused-parameter discovery keeps registration-order buckets stable; the
    # modest graph traversal cost buys exact continuation on the same GPU stack.
    wrapped = DDP(model, device_ids=[local_rank] if device.type == "cuda" else None,
                  broadcast_buffers=False, find_unused_parameters=args.deterministic)
    optimizer = make_optimizer(model, args.lr, args.weight_decay)
    generator = torch.Generator(device="cpu").manual_seed(args.seed + 1000003 * rank)
    # Distinct dropout streams after identical model initialization/broadcast.
    torch.manual_seed(args.seed + rank)
    completed, losses, initial_losses = 0, {}, {}
    if args.resume:
        checkpoint = torch.load(out / "ckpt.pt", map_location="cpu", weights_only=True)
        validate_resume(checkpoint, identity)
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        completed, losses = checkpoint["step"], checkpoint.get("losses", {})
        initial_losses = checkpoint["initial_losses"]
        restore_rng(checkpoint["rank_rng"][rank], generator, device)
        del checkpoint
    stop = args.stop_after or args.steps
    if stop < completed:
        raise ValueError("--stop-after precedes the checkpoint's completed steps")
    starting_step = completed
    started = time.monotonic()
    optimizer_seconds = 0.0
    if not args.resume:
        initial_losses = estimate_loss(model, corpus, args, device, rank, world)
    metadata = {"schema": SCHEMA, "identity": identity, "loss_units": "nats/token",
                "initial_losses": initial_losses,
                "evaluation_interval": args.eval_every,
                "tokenizer_file_sha256": hashlib.sha256((out / "tokenizer.json").read_bytes()).hexdigest(),
                "data_device": "cpu", "train_tokens": len(corpus.train), "val_tokens": len(corpus.val),
                "parameters": model.total_params(), "optimizer_groups": decay_split(model),
                "effective_batch_size": world * args.batch_size * args.grad_accum,
                "tokens_per_step": world * args.batch_size * args.grad_accum * args.block_size,
                "torch_version": str(torch.__version__), "resumed_from_step": completed,
                "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if rank == 0:
        prepare_metrics(out / "metrics.jsonl", completed, initial_losses, args.resume)
        write_json(out / "run.json", {**metadata, "status": "running", "completed_steps": completed})
        print(json.dumps({"event": "started", "world_size": world, "parameters": metadata["parameters"],
                          "tokens_per_step": metadata["tokens_per_step"], "completed_steps": completed}), flush=True)
        if not args.resume:
            print(json.dumps({"step": 0, **initial_losses}), flush=True)

    while completed < stop:
        step_started = time.monotonic()
        lr = cosine_lr(completed, args.warmup_steps, args.steps, args.lr, args.lr / 10)
        for group in optimizer.param_groups:
            group["lr"] = lr
        optimizer.zero_grad(set_to_none=True)
        train_loss = torch.zeros((), device=device, dtype=torch.float64)
        for micro in range(args.grad_accum):
            context = wrapped.no_sync() if micro < args.grad_accum - 1 else contextlib.nullcontext()
            with context:
                x, y = get_batch(corpus, "train", args, generator, device)
                with autocast(args, device):
                    _, loss = wrapped(x, y)
                finite = torch.isfinite(loss.detach()).to(torch.int32)
                dist.all_reduce(finite, op=dist.ReduceOp.MIN)
                if not finite.item():
                    raise FloatingPointError("Nonfinite training loss; no optimizer step or checkpoint was written")
                train_loss += loss.detach().double() / args.grad_accum
                (loss / args.grad_accum).backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
        optimizer.step()
        completed += 1
        dist.all_reduce(train_loss)
        train_loss /= world
        losses["last_step_nats_per_token"] = train_loss.item()
        step_seconds = time.monotonic() - step_started
        optimizer_seconds += step_seconds
        evaluate = completed % args.eval_every == 0 or completed == stop
        if evaluate:
            losses.update(estimate_loss(model, corpus, args, device, rank, world))
        if rank == 0:
            row = {"step": completed, "lr": lr, "train_step_nats_per_token": train_loss.item(),
                   "optimizer_seconds": step_seconds,
                   "optimizer_tokens_per_second": metadata["tokens_per_step"] / max(step_seconds, 1e-9)}
            if evaluate:
                row.update(losses)
                append_metric(out / "metrics.jsonl", row)
            if evaluate or (args.log_every and completed % args.log_every == 0):
                print(json.dumps(row), flush=True)
        if completed % args.save_every == 0 or completed == stop:
            save_checkpoint(out / "ckpt.pt", model, optimizer, completed, identity, generator,
                            device, rank, world, losses, initial_losses)
            if rank == 0:
                write_json(out / "run.json", {**metadata, "status": "complete" if completed == args.steps else "running",
                                              "completed_steps": completed, "losses": losses})

    peak = torch.tensor(torch.cuda.max_memory_allocated(device) if device.type == "cuda" else 0,
                        device=device, dtype=torch.int64)
    peaks = [torch.zeros_like(peak) for _ in range(world)]
    dist.all_gather(peaks, peak)
    reserved = torch.tensor(torch.cuda.max_memory_reserved(device) if device.type == "cuda" else 0,
                            device=device, dtype=torch.int64)
    reservations = [torch.zeros_like(reserved) for _ in range(world)]
    dist.all_gather(reservations, reserved)
    if rank == 0:
        elapsed = time.monotonic() - started
        result = {**metadata, "status": "complete" if completed == args.steps else "stopped",
                  "completed_steps": completed, "losses": losses, "wall_seconds": elapsed,
                  "optimizer_seconds": optimizer_seconds,
                  "optimizer_tokens_per_second": (completed - starting_step) * metadata["tokens_per_step"]
                  / max(optimizer_seconds, 1e-9),
                  "tokens_per_second": (completed - starting_step) * metadata["tokens_per_step"] / max(elapsed, 1e-9),
                  "peak_allocated_bytes_by_rank": [p.item() for p in peaks],
                  "peak_reserved_bytes_by_rank": [p.item() for p in reservations]}
        write_json(out / "run.json", result)
        return result
    return None


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.deterministic:
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.use_deterministic_algorithms(args.deterministic)
    rank, world, local_rank = (int(os.environ.get(k, "0" if k != "WORLD_SIZE" else "1"))
                               for k in ("RANK", "WORLD_SIZE", "LOCAL_RANK"))
    if "MASTER_ADDR" not in os.environ:
        raise SystemExit("Launch with torchrun --standalone --nproc-per-node=N")
    if args.device == "cuda" and (not torch.cuda.is_available() or local_rank >= torch.cuda.device_count()):
        raise SystemExit("Each local rank needs its own visible CUDA device")
    if args.device == "cuda":
        torch.cuda.set_device(local_rank)
    dist.init_process_group("nccl" if args.device == "cuda" else "gloo", timeout=timedelta(minutes=10))
    try:
        run(args, rank, world, local_rank)
    finally:
        dist.destroy_process_group()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
