"""train.py — train a GPT from scratch on YOUR text. 100% local. No API, no account.

    python train.py --data your_corpus.txt --steps 2000 --out mymodel

Random init -> your weights. Everything (model, tokenizer, checkpoint) is written to
--out and belongs to you.
"""
from __future__ import annotations

import argparse
import contextlib
import math
import time
from pathlib import Path

import torch

import baselines
import runlog
from model import GPT, GPTConfig
from data import Corpus, build_tokenizer, tokenizer_fingerprint


# Explicit scaling recipes; old commands keep the original small GPT defaults.
MODEL_PRESETS = {
    "core-small": dict(n_layer=8, n_head=8, n_embd=512, block_size=2048),
    "core-medium": dict(n_layer=12, n_head=12, n_embd=768, block_size=2048),
    "core-large": dict(n_layer=24, n_head=16, n_embd=1024, block_size=2048),
}


def enable_fast_math() -> None:
    """Two settings that are free at this scale and off by default in PyTorch.

    TF32 matmuls cost ~10 bits of mantissa and nothing in training quality.
    Measured on this rig they are worth only ~5%, because a 3M-parameter model
    is bound by per-kernel overhead rather than arithmetic, but they are free.
    """
    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True


def pick_device() -> str:
    """The best device this machine has: CUDA, then Apple's MPS, then CPU.

    One implementation, imported everywhere a device gets chosen (CLI, GUI,
    benchmark, experiments), so two entry points cannot disagree about what
    "the graphics card" means on the same machine.
    """
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def wants_bf16(device: str) -> bool:
    """bf16 autocast, only where it is measured to help.

    CUDA: worth it when the card supports it. MPS: measured on an M5 Pro,
    default size 26.47 -> 21.49 ms/step, large 238.7 -> 158.7, so it is on.
    CPU: measured slower at this scale (the casts cost more than the smaller
    arithmetic saves — see the note in exp_lr_width.py), so it stays off.
    """
    if device == "cuda":
        return torch.cuda.is_bf16_supported()
    return device == "mps"


def sync(device: str) -> None:
    """Wait for the device's queued work. GPU launches are asynchronous, so a
    wall clock read without this measures kernel launches, not training."""
    if device == "cuda":
        torch.cuda.synchronize()
    elif device == "mps":
        torch.mps.synchronize()


def make_optimizer(model, lr: float):
    """AdamW, fused where the device offers it.

    A small model has many small parameter tensors, so the optimizer step is
    dominated by launch overhead rather than arithmetic. Fusing it into one
    kernel measured 5.37 -> 4.93 ms/step on CUDA here; on MPS it is nearly a
    wash (21.28 -> 20.96 ms/step on an M5 Pro) but never slower.
    """
    kw = dict(lr=lr, betas=(0.9, 0.95), weight_decay=0.1)
    dev = next(model.parameters()).device.type
    try:
        return torch.optim.AdamW(model.parameters(), fused=dev in ("cuda", "mps"), **kw)
    except (RuntimeError, TypeError):
        return torch.optim.AdamW(model.parameters(), **kw)


def _leak_of(text: str) -> dict:
    """Leakage verdict for the split this run actually trained on, so a val loss
    is never recorded without the context that says whether it means anything.

    A CRASH IS A VERDICT, and it is not a good one. This used to return {} on
    any exception, which wrote a row with no verdict in it at all; runlog's
    digest then read the missing verdict as "nothing to report" and filed the
    run beside the ones that were actually scanned and found clean. A scan that
    died tells you nothing about the split, so it must say exactly that and be
    counted with the runs whose val loss cannot be defended.

    AND THE ROW IS THE SCAN'S OWN. This built {"verdict", "content_frac"} by
    hand, which was the whole row while content overlap WAS the verdict. It is
    now the worst of three signals, and a hand-built row went on recording the
    one arm that structurally cannot see a short copied document: measured on
    test_detectors.short_document_fixture, verdict CONTAMINATED beside
    content_frac 0.0, with the two arms that decided it recorded nowhere. See
    leakage.Report.record.
    """
    try:
        from leakage import scan
        from data import group_split
        tr, va = group_split(text)
        rep = scan(tr, va, doc_aligned=True)      # group_split: it is
        return rep.record()
    except Exception as e:                       # noqa: BLE001
        print(f"[leakage] the scan failed ({type(e).__name__}: {e}), so this "
              f"run's val loss is UNVERIFIED. Judge it on train loss.")
        return {"verdict": "SCAN_FAILED", "error": f"{type(e).__name__}: {e}"}


def auto_lr(n_embd: int) -> float:
    """Width-appropriate learning rate.

    The old hardcoded 3e-4 is a GPT-2-scale constant (width 768-1600) and is far
    too low for the widths this rig runs. Measured on this box (exp_lr_width.py,
    prereg_lr_width.json): at width 256 / 4 layers on corpus.txt, lr=3e-3 beats
    3e-4 by 0.0439 train loss, 5 seeds/arm, zero range overlap.

    0.0439 is the GAP -- mean(control) 0.1495 minus mean(treatment) 0.1056 --
    which is what the experiment's success bar is written against and what its
    not_claimed section quotes. This line used to say 0.1056, the treatment
    arm's own mean, which is where the treatment ENDED and not what the change
    was worth. It overstated the effect by 2.4x.

    The 1/width scaling is muP's (Yang et al. 2022, arXiv:2203.03466). ANCHORED AT
    ONE MEASURED POINT ONLY (width 256). Other widths are extrapolation, not
    measurement — re-run exp_lr_width.py at a new width before trusting it there.
    """
    return 3e-3 * (256.0 / max(n_embd, 1))


def cosine_lr(step: int, warmup: int, total: int, lr: float, min_lr: float) -> float:
    if step < warmup:
        return lr * (step + 1) / warmup
    if step >= total:
        return min_lr
    ratio = (step - warmup) / max(1, total - warmup)
    return min_lr + 0.5 * (1 + math.cos(math.pi * ratio)) * (lr - min_lr)


EVAL_SEED = 12345          # eval draws are reproducible and never touch training


@torch.no_grad()
def estimate_loss(model, corpus, batch_size, block_size, iters=20):
    """Loss on fixed, independently-drawn batches.

    The batches come from a dedicated Generator seeded the same way every call,
    NOT from the global RNG. That matters more than it sounds: drawing eval
    batches from the training stream means the number of times you look at the
    model changes what the model learns, because every eval consumes random
    numbers the next training batch would otherwise have used.

    Measured on this repo before the fix, same seed and same data, varying only
    eval_interval over 248/249/250/251/252/500: final train loss spread 0.031166.
    After: 0.000000, identical regardless of how often you evaluate. It also
    makes successive evals comparable to each other, since they score the same
    batches rather than a fresh random sample each time.
    """
    dev = corpus.train.device
    g = torch.Generator(device=dev.type).manual_seed(EVAL_SEED)
    model.eval()
    out = {}
    for split in ("train", "val"):
        losses = torch.zeros(iters)
        for i in range(iters):
            x, y = corpus.get_batch(split, batch_size, block_size, generator=g)
            _, loss = model(x, y)
            losses[i] = loss.item()
        out[split] = losses.mean().item()
    model.train()
    return out


def parse_args(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="path to a .txt corpus (yours)")
    ap.add_argument("--out", default="out")
    ap.add_argument("--steps", type=int, default=2000)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--preset", choices=MODEL_PRESETS,
                    help="modern core size; explicit dimension flags override the preset")
    ap.add_argument("--architecture", choices=("gpt", "modern"), default=None)
    ap.add_argument("--gradient-checkpointing", action=argparse.BooleanOptionalAction,
                    default=None, help="recompute blocks during backward to reduce activation memory")
    ap.add_argument("--tokenizer", choices=("char", "bpe"), default="char")
    ap.add_argument("--vocab-size", type=int, default=8192,
                    help="target BPE vocabulary size; ignored by the character tokenizer")
    ap.add_argument("--block-size", type=int, default=None)
    ap.add_argument("--n-layer", type=int, default=None)
    ap.add_argument("--n-head", type=int, default=None)
    ap.add_argument("--n-embd", type=int, default=None)
    ap.add_argument("--dropout", type=float, default=0.1)
    ap.add_argument("--lr", type=float, default=None,
                    help="learning rate; default = auto_lr(n_embd), width-scaled")
    ap.add_argument("--eval-interval", type=int, default=250)
    ap.add_argument("--seed", type=int, default=1337)
    args = ap.parse_args(argv)
    defaults = MODEL_PRESETS.get(args.preset, dict(n_layer=4, n_head=4, n_embd=256, block_size=128))
    for key, value in defaults.items():
        if getattr(args, key) is None:
            setattr(args, key, value)
    if args.architecture is None:
        args.architecture = "modern" if args.preset else "gpt"
    if args.gradient_checkpointing is None:
        args.gradient_checkpointing = args.preset in ("core-medium", "core-large")
    return args


def main():
    args = parse_args()

    device = pick_device()
    torch.manual_seed(args.seed)

    if args.lr is None:
        args.lr = auto_lr(args.n_embd)
        print(f"lr: {args.lr:.2e} (auto, width-scaled from n_embd={args.n_embd}; "
              f"pass --lr to override)")

    text = Path(args.data).read_text(encoding="utf-8", errors="ignore")
    tok = build_tokenizer(text, kind=args.tokenizer, vocab_size=args.vocab_size)
    corpus = Corpus(text, tok, device)
    print(f"corpus: {len(text):,} chars | vocab {tok.vocab_size} | device {device}")

    cfg = GPTConfig(vocab_size=tok.vocab_size, block_size=args.block_size,
                    n_layer=args.n_layer, n_head=args.n_head, n_embd=args.n_embd,
                    dropout=args.dropout, bias=args.architecture == "gpt",
                    architecture=args.architecture,
                    gradient_checkpointing=args.gradient_checkpointing)
    model = GPT(cfg).to(device)
    print(f"model: {model.total_params() / 1e6:.2f}M total params | {args.architecture} | "
          f"{args.n_layer}L {args.n_head}H {args.n_embd}D")

    enable_fast_math()
    opt = make_optimizer(model, args.lr)
    use_bf16 = wants_bf16(device)
    amp = (lambda: torch.autocast(device, dtype=torch.bfloat16)) if use_bf16 \
        else (lambda: contextlib.nullcontext())

    Path(args.out).mkdir(parents=True, exist_ok=True)
    warmup = max(10, args.steps // 20)
    t0 = time.time()
    for step in range(args.steps):
        lr = cosine_lr(step, warmup, args.steps, args.lr, args.lr / 10)
        for g in opt.param_groups:
            g["lr"] = lr
        if step % args.eval_interval == 0 or step == args.steps - 1:
            L = estimate_loss(model, corpus, args.batch_size, args.block_size)
            print(f"step {step:5d} | train {L['train']:.4f} | val {L['val']:.4f} | "
                  f"lr {lr:.2e} | {time.time() - t0:.0f}s")
        x, y = corpus.get_batch("train", args.batch_size, args.block_size)
        with amp():
            _, loss = model(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()

    torch.save({"model": model.state_dict(), "config": cfg.__dict__,
                "tokenizer_fingerprint": tokenizer_fingerprint(tok)}, Path(args.out) / "ckpt.pt")
    tok.save(Path(args.out) / "tokenizer.json")
    print(f"\nsaved model + tokenizer to {args.out}/")

    # Append this run to the shared log. A checkpoint folder tells you nothing
    # about what produced it a week later; the log does.
    wall = time.time() - t0
    final = estimate_loss(model, corpus, args.batch_size, args.block_size)

    # What a lookup table scores on the SAME held-out text. Without this, a loss
    # can only be compared to uniform guessing, which anything beats — see
    # baselines.py. Scored on corpus.train/corpus.val rather than a fresh split,
    # so the baseline cannot describe a different holdout than the model was
    # scored on. This comparison is only meaningful for character-token loss.
    base = None
    if args.tokenizer == "char" and corpus.train_text is not None and corpus.val_text:
        base = baselines.compare(corpus.train_text, corpus.val_text,
                                 tok.vocab_size, model_val_nats=final["val"])
        print("\n--- how does that compare to a model that cannot learn? ---")
        for line in baselines.summary_lines(base):
            print(line)
    elif args.tokenizer != "char":
        print("Character n-gram comparisons omitted: BPE loss is measured per BPE token.")

    # corpus AND split. The corpus fingerprint says which text; the split
    # fingerprint says which tenth of it was held back, which is the part every
    # prereg here assumes is identical across runs and which nothing recorded.
    # A new key beside the old one, never a change to one: rows already written
    # must keep parsing, and they do.
    # data_device, not just device: if the corpus did not fit and fell back to
    # host memory, this run's ms/step and its batch sequence are both different
    # from an otherwise identical run that fitted. See Corpus._place.
    runlog.record("train", device=device, data_device=corpus.data_device,
                  out=args.out, source="cli",
                  corpus=runlog.corpus_fingerprint(text),
                  split_fingerprint=runlog.split_fingerprint(
                      corpus.val_frac, corpus.seed, corpus.val_text),
                  config={"n_layer": args.n_layer, "n_head": args.n_head,
                          "n_embd": args.n_embd, "block_size": args.block_size,
                          "batch_size": args.batch_size, "steps": args.steps,
                          "lr": args.lr, "dropout": args.dropout,
                          "seed": args.seed, "architecture": args.architecture,
                          "preset": args.preset, "tokenizer": args.tokenizer,
                          "vocab_size": tok.vocab_size,
                          "gradient_checkpointing": args.gradient_checkpointing},
                  metrics={"train_loss": final["train"], "val_loss": final["val"],
                           "wall_s": wall,
                           "ms_per_step": wall / max(args.steps, 1) * 1000,
                           "params": model.num_params(), "total_params": model.total_params()},
                  baselines=base,
                  leakage=_leak_of(text))
    print(f"recorded to {runlog.LOG.name}  (python runlog.py to review)")

    ctx = torch.zeros((1, 1), dtype=torch.long, device=device)
    sample = tok.decode(model.generate(ctx, 400, temperature=0.8, top_k=40)[0].tolist())
    print("\n--- sample from your model ---\n" + sample)


if __name__ == "__main__":
    main()
