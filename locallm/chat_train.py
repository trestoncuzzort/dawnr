"""chat_train.py: mid-training and SFT in dawnr's chat format, loss on the assistant only.

    python3 locallm/chat_train.py --init <checkpoint dir> --conversations conv.jsonl --out <dir> \
        [--steps 300] [--lr 3e-5] [--batch-size 8] [--block-size 512] [--dropout 0.1] [--seed 1337]

nanochat (https://github.com/karpathy/nanochat, scripts/chat_sft.py, and the
first release's scripts/mid_train.py) trains the base model on rendered
conversations whose targets are masked to the assistant's tokens: the user's
turn and the tool's output are context, never targets. This is that stage for
locallm, on the conversations chat_data.py builds from the proved corpus.

What it takes from nanochat: rendering and masking (chat.py), padded rows
rather than cropped ones, warmup then decay, periodic validation loss on the
validation conversations. What differs: one conversation per row with no
packing (the whole set is tens of thousands of tokens; data.DocumentBatches'
reasoning), a conversation over the block refused by name, AdamW with the
project's decay groups and cosine schedule (train.make_optimizer, cosine_lr)
instead of Muon, and new chat-token rows added to a pretrained core with the
mean initialisation continue_from_checkpoint.py uses for FIM sentinels.

The same script is the mid-training stage (a core that has never seen the
chat tokens: they are added) and the SFT stage (a checkpoint that already has
them: nothing is added). Validation loss is recorded, not used to choose the
step; dawnr chooses steps by tests on the dev split (t/pick_stopping_step.py).

Writes an ordinary project checkpoint (ckpt.pt, tokenizer.json) that
checkpoint.load_checkpoint reads, plus metrics.jsonl and run.json. --resume
continues from state.pt when the inputs are the same.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESUME_KEYS = ("init_ckpt_sha256", "conversations_sha256", "seed", "block_size", "batch_size", "steps", "lr")


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_conversations(path: Path) -> tuple[list[dict], list[dict]]:
    train, val = [], []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        side = row.get("split", "train")
        if side not in ("train", "val"):
            raise ValueError(f"{path}:{n}: split must be train or val, not {side!r}")
        (train if side == "train" else val).append(row)
    if not train:
        raise ValueError(f"{path}: no training conversations")
    return train, val


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--init", type=Path, required=True, help="checkpoint directory (ckpt.pt, tokenizer.json)")
    ap.add_argument("--conversations", type=Path, required=True, help="JSONL from chat_data.py")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--block-size", type=int, default=0,
                    help="row length; 0 (default): the longest conversation, rounded up to 64, within the context")
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--weight-decay", type=float, default=0.1)
    ap.add_argument("--dropout", type=float, default=0.1)
    ap.add_argument("--grad-clip", type=float, default=1.0)
    ap.add_argument("--eval-every", type=int, default=50)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--device", default=None)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--harness-tokens", action="store_true",
                    help="add the harness tokens even when no conversation needs them, so a model trained without "
                         "tool conversations has the same ids as one trained with them (a control arm)")
    ap.add_argument("--gradient-checkpointing", action="store_true",
                    help="recompute each block's activations in the backward pass (torch.utils.checkpoint, RNG "
                         "preserved, so dropout masks are the same): less memory, the same batch and gradients")
    a = ap.parse_args(argv)

    import torch
    import chat
    import train as core_train
    from data import load_tokenizer, tokenizer_fingerprint
    from model import GPT, GPTConfig

    train_convs, val_convs = load_conversations(a.conversations)
    device = a.device or core_train.pick_device()
    torch.manual_seed(a.seed)
    ck = torch.load(a.init / "ckpt.pt", map_location="cpu", weights_only=True)
    ck.pop("optimizer", None)
    config = GPTConfig(**{**ck["config"], "dropout": a.dropout,
                          **({"gradient_checkpointing": True} if a.gradient_checkpointing else {})})
    model = GPT(config)
    model.load_state_dict(ck["model"])
    tokenizer = load_tokenizer(a.init / "tokenizer.json")
    if tokenizer.vocab_size != config.vocab_size:
        raise ValueError("the init's tokenizer and embedding table disagree on vocabulary size")
    # conversations that call registry tools or read untrusted output need the harness tokens too (DAWNR-HARNESS.md)
    harness = a.harness_tokens or chat.needs_harness_tokens(train_convs + val_convs)
    memory = chat.needs_memory_tokens(train_convs + val_convs)       # memory spans need the token (DAWNR-MEMORY.md)
    tokenizer = (chat.with_memory_tokens(tokenizer) if memory else
                 chat.with_harness_tokens(tokenizer) if harness else chat.with_chat_tokens(tokenizer))
    added = chat.grow_embeddings(model, tokenizer.vocab_size)
    model.to(device)
    # 2026-09-29 (the r12 corpus through the pipeline): a conversation longer than the
    # model's context cannot be trained without cutting it, and ConversationBatches
    # refuses a cut conversation by design (a cut one is not the conversation that was
    # built). Such conversations are dropped whole, by name, on both sides (the
    # validation loss is batched the same way), recorded in run.json under
    # identities["dropped_over_block"], and the run refuses only when no training
    # conversation remains. TRL's SFTTrainer truncates to max_length instead
    # (huggingface.co/docs/trl/main/en/sft_trainer) and nanochat's render_conversation
    # truncates at max_tokens; here nothing is cut, so every trained row is a whole,
    # gated conversation. First hit: vericoding_da0085__findMinimumTotalDistance,
    # 2,109 tokens against a context of 2,048.
    def rendered(convs):
        return [(c, len(chat.render_conversation(tokenizer, c)[0])) for c in convs]
    sides = {"train": rendered(train_convs), "val": rendered(val_convs)}
    dropped = [{"split": side, "source": c.get("source", "?"), "tokens": n}
               for side, rows in sides.items() for c, n in rows if n > config.block_size + 1]
    if dropped:
        train_convs = [c for c, n in sides["train"] if n <= config.block_size + 1]
        val_convs = [c for c, n in sides["val"] if n <= config.block_size + 1]
        for d in dropped:
            print(f"dropped ({d['split']}): {d['source']} is {d['tokens']} tokens, over the model's "
                  f"context of {config.block_size}; a whole conversation or none")
        if not train_convs:
            raise SystemExit("every training conversation is over the model's context; nothing to train on")
    if a.block_size == 0:
        longest = max(len(chat.render_conversation(tokenizer, c)[0]) for c in train_convs + val_convs) - 1
        a.block_size = min(config.block_size, -(-longest // 64) * 64)
    if a.block_size > config.block_size:
        raise SystemExit(f"--block-size {a.block_size} exceeds the model's context of {config.block_size}")

    train_rows = chat.ConversationBatches(train_convs, tokenizer, a.block_size, a.seed, device)
    val_rows = chat.ConversationBatches(val_convs, tokenizer, a.block_size, a.seed, device) if val_convs else None
    optimizer = core_train.make_optimizer(model, a.lr, a.weight_decay)
    identities = {"init": str(a.init), "init_ckpt_sha256": file_sha256(a.init / "ckpt.pt"),
                  "conversations": str(a.conversations), "conversations_sha256": file_sha256(a.conversations),
                  "chat_tokens": list(chat.CHAT_TOKENS), "chat_tokens_added": added,
                  "tokenizer_fingerprint": tokenizer_fingerprint(tokenizer),
                  "config": asdict(model.config), "parameters": sum(p.numel() for p in model.parameters()),
                  "train": train_rows.record(), "val": val_rows.record() if val_rows else None,
                  "seed": a.seed, "block_size": a.block_size, "batch_size": a.batch_size, "steps": a.steps,
                  "dropped_over_block": dropped,
                  **({"harness_tokens": list(chat.HARNESS_TOKENS)} if harness or memory else {}),
                  **({"memory_tokens": list(chat.MEMORY_TOKENS)} if memory else {}),
                  "lr": a.lr, "warmup": a.warmup, "weight_decay": a.weight_decay, "dropout": a.dropout,
                  "grad_clip": a.grad_clip, "device": device,
                  "source": "nanochat render_conversation masking (github.com/karpathy/nanochat)"}
    a.out.mkdir(parents=True, exist_ok=True)
    state_path, start = a.out / "state.pt", 0
    if a.resume and state_path.exists():
        state = torch.load(state_path, map_location=device, weights_only=False)
        for key in RESUME_KEYS:
            if state["identities"].get(key) != identities[key]:
                raise SystemExit(f"cannot resume: {key} changed since this run started")
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        torch.set_rng_state(state["rng"])
        if device.startswith("cuda") and state.get("cuda_rng") is not None:
            torch.cuda.set_rng_state_all(state["cuda_rng"])
        start = state["step"]
    tokenizer.save(a.out / "tokenizer.json")
    autocast = (torch.autocast(device_type="cuda", dtype=torch.bfloat16)
                if core_train.wants_bf16(device) else torch.autocast("cpu", enabled=False))

    @torch.no_grad()
    def masked_loss(rows) -> float | None:
        if rows is None:
            return None
        was = model.training
        model.eval()
        total = count = 0.0
        for x, y in rows.in_order(a.batch_size):
            with autocast:
                _, loss = model(x, y)
            n = int((y != chat.IGNORE_INDEX).sum())
            total += float(loss) * n
            count += n
        model.train(was)
        return total / count if count else None

    def save_state(step):
        torch.save({"model": model.state_dict(), "optimizer": optimizer.state_dict(), "step": step,
                    "identities": identities, "rng": torch.get_rng_state(),
                    "cuda_rng": torch.cuda.get_rng_state_all() if device.startswith("cuda") else None},
                   state_path)

    metrics = (a.out / "metrics.jsonl").open("a")
    first = {"step": start, "train": masked_loss(train_rows), "val": masked_loss(val_rows)}
    metrics.write(json.dumps(first) + "\n")
    metrics.flush()
    print(json.dumps(first), flush=True)
    (a.out / "run.json").write_text(json.dumps({"status": "running", "identities": identities,
                                                "initial": first}, indent=2) + "\n")
    started, step = time.monotonic(), start
    model.train()
    last = first
    while step < a.steps:
        x, y = train_rows.get_batch(step, a.batch_size)
        lr = core_train.cosine_lr(step, a.warmup, a.steps, a.lr, a.lr / 10)
        for group in optimizer.param_groups:
            group["lr"] = lr
        with autocast:
            _, loss = model(x, y)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        if a.grad_clip:
            torch.nn.utils.clip_grad_norm_(model.parameters(), a.grad_clip)
        optimizer.step()
        step += 1
        if step % a.eval_every == 0 or step == a.steps:
            last = {"step": step, "train": masked_loss(train_rows), "val": masked_loss(val_rows),
                    "batch_loss": float(loss), "lr": lr, "seconds": round(time.monotonic() - started, 1)}
            metrics.write(json.dumps(last) + "\n")
            metrics.flush()
            print(json.dumps(last), flush=True)
            save_state(step)
    metrics.close()
    model.eval()
    # checkpointing is how the run used memory, not part of the model: the saved config loads as every other arm's
    model.config.gradient_checkpointing = bool(ck["config"].get("gradient_checkpointing", False))
    torch.save({"model": model.state_dict(), "config": asdict(model.config),
                "tokenizer_fingerprint": tokenizer_fingerprint(tokenizer),
                "training": {"stage": "chat", "steps": step}}, a.out / "ckpt.pt")
    run = {"status": "complete", "identities": identities, "initial": first, "final": last,
           "seconds": round(time.monotonic() - started, 1),
           "peak_cuda_bytes": torch.cuda.max_memory_allocated() if device.startswith("cuda") else None}
    (a.out / "run.json").write_text(json.dumps(run, indent=2) + "\n")
    print(json.dumps({"saved": str(a.out), "final": last}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
