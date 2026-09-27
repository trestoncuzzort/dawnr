"""dawnr_pipeline.py: dawnr end to end, one command, every stage resumable and measured.

    systemd-run --user --scope -p MemoryMax=8G \\
      ~/.venv-locallm/bin/python locallm/dawnr_pipeline.py --corpus <proved corpus.txt> --out <dir> \\
        [--preset tiny | --core <checkpoint dir>] [--mid-steps 300] [--dev 100] [--stages a,b,...]

nanochat drives its whole pipeline from runs/speedrun.sh
(https://github.com/karpathy/nanochat): tokenizer, base, mid-training, SFT,
RL, evaluation, report, top to bottom. This is that driver for dawnr, in
Python so that each stage can record what it ran on and be tested:

  1 tokenizer      the BPE the base stage will train with, built the same way
                   (data.build_tokenizer) on the TRAIN side of the corpus;
                   characters per token on both sides. With --core: the
                   core's own tokenizer, measured.
  2 base           train.py from random weights on the train side only (its
                   own early-stopping holdout is carved from that), or --core
                   as given; then the held-out loss on the validation-side
                   documents, which no stage ever trains on.
  3 conversations  chat_data.py: the proved corpus as conversations, the same
                   hash split, a share with real t-tool calls; with
                   --extra-conversations (repair_data.py's repair and pass
                   conversations), those are appended on the training side
                   after the same gates.
  4 mid            chat_train.py: the chat tokens added, the format and the
                   tool taught, loss on the assistant only.
  5 sft            chat_train.py again from mid on --sft-conversations when
                   given; with one data source today there is nothing separate
                   to fine-tune on, and the stage says so rather than
                   repeating mid.
  6 rl             not run: t/rl_grpo.py samples the document format, and
                   running it through the chat engine is the next port. The
                   stage records why it was skipped.
  7 eval           chat_eval.py: dev problems through the engine with the tool
                   live, graded by t/rl_reward's tiers; validation
                   conversations checked by the t tool. Never the held-out 200.
  8 report         dawnr_report.py: every stage's numbers in one report.md.

A stage writes <out>/<n>-<name>/stage.json with the hashes of everything it
read and its parameters. It is skipped when that file says "done" for the same
inputs, rerun when anything changed; since a stage's inputs include the files
the stage before it wrote, a change reruns everything downstream. Stage output
goes to log.txt beside it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "t"))

STAGES = ("tokenizer", "base", "conversations", "mid", "sft", "rl", "eval", "report")
PRESETS = {
    # minutes on one consumer GPU; for checking the pipeline, not for a result
    "tiny": {"n_layer": 4, "n_head": 4, "n_embd": 256, "block_size": 1024, "vocab_size": 2048,
             "steps": 300, "batch_size": 16},
    "small": {"n_layer": 6, "n_head": 8, "n_embd": 512, "block_size": 1024, "vocab_size": 4096,
              "steps": 2000, "batch_size": 16},
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fingerprint(inputs: dict) -> dict:
    """Parameters as given; every Path replaced by its content hash."""
    out = {}
    for k, v in sorted(inputs.items()):
        if isinstance(v, Path):
            out[k] = {"path": str(v), "sha256": sha256_file(v) if v.is_file() else None}
        else:
            out[k] = v
    return out


class Stage:
    def __init__(self, root: Path, index: int, name: str):
        self.name = name
        self.dir = root / f"{index}-{name}"
        self.record = self.dir / "stage.json"

    def interrupted_for(self, inputs: dict) -> bool:
        """The record says this stage was running on these inputs when it stopped: resume it."""
        rec = self.read()
        return rec.get("status") == "running" and rec.get("inputs") == inputs

    def done_for(self, inputs: dict) -> bool:
        if not self.record.is_file():
            return False
        rec = json.loads(self.record.read_text(encoding="utf-8"))
        return rec.get("status") in ("done", "skipped") and rec.get("inputs") == inputs

    def write(self, status: str, inputs: dict, **extra) -> dict:
        self.dir.mkdir(parents=True, exist_ok=True)
        rec = {"stage": self.name, "status": status, "inputs": inputs, **extra}
        self.record.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        return rec

    def read(self) -> dict:
        return json.loads(self.record.read_text(encoding="utf-8")) if self.record.is_file() else {}


def run_logged(cmd: list[str], log: Path, env: dict | None = None) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(f"\n$ {' '.join(cmd)}\n")
        f.flush()
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=str(HERE),
                           env={**os.environ, **(env or {})})
    if r.returncode:
        raise SystemExit(f"{cmd[1] if len(cmd) > 1 else cmd[0]} failed ({r.returncode}); see {log}")


# ------------------------------------------------------------------- stages --

def split_sides(corpus: Path, split_seed: int, val_frac: float) -> tuple[list[str], list[str]]:
    from data import split_documents
    return split_documents(corpus.read_text(encoding="utf-8"), val_frac=val_frac, seed=split_seed, by="hash")


def chars_per_token(tok, docs: list[str]) -> float | None:
    chars = sum(len(d) for d in docs)
    tokens = sum(len(tok.encode(d)) for d in docs)
    return round(chars / tokens, 4) if tokens else None


def stage_tokenizer(st: Stage, a, sides) -> dict:
    from data import build_tokenizer, load_tokenizer, tokenizer_fingerprint
    train, val = sides
    if a.core:
        tok = load_tokenizer(a.core / "tokenizer.json")
        origin = "core"
    else:
        tok = build_tokenizer("\n\n".join(train), kind="bpe", vocab_size=PRESETS[a.preset]["vocab_size"])
        origin = "trained on the train side (data.build_tokenizer, as train.py builds it)"
        st.dir.mkdir(parents=True, exist_ok=True)
        tok.save(st.dir / "tokenizer.json")
    return {"origin": origin, "vocab_size": tok.vocab_size, "fingerprint": tokenizer_fingerprint(tok),
            "chars_per_token_train": chars_per_token(tok, train), "chars_per_token_val": chars_per_token(tok, val),
            "train_documents": len(train), "val_documents": len(val)}


def heldout_loss(model_dir: Path, docs: list[str], block: int) -> dict:
    """Mean loss over whole held-out documents, one per row (data.DocumentBatches), per token and per character."""
    import torch
    from checkpoint import load_checkpoint
    from data import DocumentBatches, IGNORE_INDEX
    model, tok, cfg = load_checkpoint(model_dir)
    block = min(block, cfg.block_size) if block else cfg.block_size
    rows = DocumentBatches(docs, tok, block, seed=0, device=next(model.parameters()).device)
    total = count = 0.0
    with torch.no_grad():
        for x, y in rows.in_order(8):
            logits, _ = model(x)
            loss = torch.nn.functional.cross_entropy(logits.view(-1, logits.size(-1)).float(), y.view(-1),
                                                     ignore_index=IGNORE_INDEX, reduction="sum")
            total += float(loss)
            count += int((y != IGNORE_INDEX).sum())
    chars = sum(len(d.strip("\r\n")) + 2 for d in docs)
    return {"documents": len(docs), "target_tokens": int(count), "nats_per_token": round(total / count, 4),
            "nats_per_char": round(total / chars, 4), "cut_documents": rows.cut_documents}


def stage_base(st: Stage, a, sides, tok_record: dict) -> dict:
    from data import load_tokenizer, tokenizer_fingerprint
    train, val = sides
    if a.core:
        model_dir = a.core
        out = {"origin": "core", "model": str(a.core)}
        run = a.core / "run.json"
        if run.is_file():
            out["core_run"] = {k: v for k, v in json.loads(run.read_text()).items()
                               if k in ("completed_steps", "best_step", "best_val_loss")}
    else:
        p = PRESETS[a.preset]
        model_dir = st.dir / "model"
        data = st.dir / "train-side.txt"
        data.write_text("\n\n".join(train) + "\n", encoding="utf-8")
        cmd = [sys.executable, "train.py", "--data", str(data), "--out", str(model_dir),
               "--steps", str(p["steps"]), "--batch-size", str(p["batch_size"]),
               "--block-size", str(p["block_size"]), "--n-layer", str(p["n_layer"]), "--n-head", str(p["n_head"]),
               "--n-embd", str(p["n_embd"]), "--tokenizer", "bpe", "--vocab-size", str(p["vocab_size"]),
               "--seed", str(a.seed), "--eval-interval", "100"]
        run_logged(cmd, st.dir / "log.txt", {"LOCALLM_RUN_LOG": str(st.dir / "runs.jsonl")})
        import torch
        ck = torch.load(model_dir / "ckpt.pt", map_location="cpu", weights_only=True)
        out = {"origin": "trained from random weights", "model": str(model_dir), "preset": a.preset, **p,
               "training": {k: ck["training"].get(k) for k in ("weights", "saved_step", "saved_val_loss",
                                                               "saved_train_loss", "stopped_step", "stop_reason")}}
    tok = load_tokenizer(model_dir / "tokenizer.json")
    out["fingerprint"] = tokenizer_fingerprint(tok)
    if out["fingerprint"] != tok_record["fingerprint"]:
        raise SystemExit("the base model's tokenizer is not the one the tokenizer stage measured")
    out["heldout"] = heldout_loss(model_dir, val, a.block_size)
    return out


def stage_conversations(st: Stage, a) -> dict:
    out = st.dir / "conversations.jsonl"
    run_logged([sys.executable, "chat_data.py", "--corpus", str(a.corpus), "--split", str(a.split),
                "--out", str(out), "--tool-rate", str(a.tool_rate), "--split-seed", str(a.split_seed),
                "--val-frac", str(a.val_frac)], st.dir / "log.txt")
    summary = json.loads(out.with_suffix(".summary.json").read_text(encoding="utf-8"))
    result = {"file": str(out), **{k: v for k, v in summary.items() if k != "skipped"},
              "skipped": len(summary["skipped"])}
    if a.extra_conversations:
        import chat_data
        from collections import Counter
        text = a.extra_conversations.read_text(encoding="utf-8")
        extra = [json.loads(line) for line in text.splitlines() if line.strip()]
        wrong_side = [r.get("source") for r in extra if r.get("split") != "train"]
        if wrong_side:
            raise SystemExit(f"--extra-conversations holds {len(wrong_side)} rows not on the training side "
                             f"(first: {wrong_side[0]}); only training conversations are added")
        chat_data.gate("\n\n".join(json.dumps(r, ensure_ascii=False) for r in extra),
                       f"extra conversations {a.extra_conversations}", a.split)
        with out.open("a", encoding="utf-8") as f:
            for r in extra:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        result["extra"] = {"file": str(a.extra_conversations), "rows": len(extra),
                           "built": dict(Counter(r.get("built", "?") for r in extra))}
    return result


def stage_chat(st: Stage, a, init: Path, conversations: Path, steps: int, lr: float) -> dict:
    out = st.dir / "model"
    if out.exists() and not getattr(st, "resuming", False):
        import shutil
        shutil.rmtree(out)            # inputs changed: a stale state.pt must not be resumed
    run_logged([sys.executable, "chat_train.py", "--init", str(init), "--conversations", str(conversations),
                "--out", str(out), "--steps", str(steps), "--lr", str(lr), "--batch-size", str(a.chat_batch),
                "--block-size", str(a.block_size), "--seed", str(a.seed), "--eval-every", str(a.eval_every),
                "--resume"] + (["--harness-tokens"] if a.harness_tokens else [])
               + (["--gradient-checkpointing"] if a.gradient_checkpointing else []), st.dir / "log.txt")
    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    ident = run["identities"]
    return {"model": str(out), "initial": run["initial"], "final": run["final"], "seconds": run["seconds"],
            "chat_tokens_added": ident["chat_tokens_added"], "train": ident["train"], "val": ident["val"],
            "parameters": ident["parameters"], "steps": steps, "lr": lr, "peak_cuda_bytes": run["peak_cuda_bytes"]}


def stage_eval(st: Stage, a, model: Path, conversations: Path) -> dict:
    out = st.dir / "eval.json"
    run_logged([sys.executable, "chat_eval.py", "--model", str(model), "--conversations", str(conversations),
                "--split", str(a.split), "--out", str(out), "--dev", str(a.dev), "--max-tokens", str(a.max_tokens)],
               st.dir / "log.txt")
    return json.loads(out.read_text(encoding="utf-8"))


# --------------------------------------------------------------------- main --

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", type=Path, required=True, help="the proved corpus, one document per blank-line block")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--split", type=Path, default=ROOT / "t" / "out" / "loop" / "split-v5.json",
                    help="the evaluation split whose held-out ids must never appear")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--preset", choices=sorted(PRESETS), default="tiny")
    src.add_argument("--core", type=Path, default=None, help="start from this pretrained checkpoint (skips training base)")
    ap.add_argument("--split-seed", type=int, default=1337)
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--block-size", type=int, default=0,
                    help="chat row length and held-out row length; 0: chat_train's automatic choice, the model's context")
    ap.add_argument("--tool-rate", type=float, default=0.5)
    ap.add_argument("--extra-conversations", type=Path, default=None,
                    help="training-side conversations to add to the mid stage's data (repair_data.py build, "
                         "tool_conversations.py build)")
    ap.add_argument("--harness-tokens", action="store_true",
                    help="give the chat model the harness tokens even when no conversation uses them (a control "
                         "arm evaluated on tool conversations)")
    ap.add_argument("--gradient-checkpointing", action="store_true",
                    help="the chat stages recompute activations in the backward pass: less GPU memory, the same "
                         "batch and gradients (chat_train.py)")
    ap.add_argument("--mid-steps", type=int, default=300)
    ap.add_argument("--mid-lr", type=float, default=3e-4)
    ap.add_argument("--sft-conversations", type=Path, default=None)
    ap.add_argument("--sft-steps", type=int, default=100)
    ap.add_argument("--sft-lr", type=float, default=3e-5)
    ap.add_argument("--chat-batch", type=int, default=8)
    ap.add_argument("--eval-every", type=int, default=50)
    ap.add_argument("--dev", type=int, default=100, help="dev problems the eval stage asks")
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--heldout-tag", default=None,
                    help="an EXISTING answer set to score on the clean 200 in the report (no new generation)")
    ap.add_argument("--stages", default=",".join(STAGES), help="comma list; stages not named are not run")
    a = ap.parse_args(argv)
    wanted = [s.strip() for s in a.stages.split(",") if s.strip()]
    unknown = set(wanted) - set(STAGES)
    if unknown:
        ap.error(f"unknown stages {sorted(unknown)}; the stages are {', '.join(STAGES)}")
    a.corpus, a.out, a.split = a.corpus.resolve(), a.out.resolve(), a.split.resolve()
    if a.core:
        a.core = a.core.resolve()
    if a.extra_conversations:
        a.extra_conversations = a.extra_conversations.resolve()
    a.out.mkdir(parents=True, exist_ok=True)
    stages = {name: Stage(a.out, i + 1, name) for i, name in enumerate(STAGES)}

    # the corpus passes the trainers' gates before any stage reads it
    import chat_data
    chat_data.gate(a.corpus.read_text(encoding="utf-8"), str(a.corpus), a.split)
    sides = split_sides(a.corpus, a.split_seed, a.val_frac)
    common = {"corpus": a.corpus, "split": a.split, "split_seed": a.split_seed, "val_frac": a.val_frac}

    def step(name: str, inputs: dict, body):
        st = stages[name]
        fp = fingerprint(inputs)
        if name not in wanted:
            return st.read()
        if st.done_for(fp):
            print(f"[{name}] done for these inputs; skipped", flush=True)
            return st.read()
        print(f"[{name}] running", flush=True)
        started = time.monotonic()
        st.resuming = st.interrupted_for(fp)
        st.write("running", fp)
        result = body(st)
        status = result.pop("_status", "done")
        rec = st.write(status, fp, result=result, seconds=round(time.monotonic() - started, 1))
        print(f"[{name}] {status} in {rec['seconds']}s", flush=True)
        return rec

    tok = step("tokenizer", {**common, "core_tokenizer": a.core / "tokenizer.json" if a.core else None,
                             "preset": None if a.core else PRESETS[a.preset]},
               lambda st: stage_tokenizer(st, a, sides))
    base = step("base", {**common, "tokenizer_stage": stages["tokenizer"].record, "seed": a.seed,
                         "train_py": HERE / "train.py",
                         "core_ckpt": a.core / "ckpt.pt" if a.core else None, "block_size": a.block_size},
                lambda st: stage_base(st, a, sides, tok["result"]))
    conv = step("conversations", {**common, "tool_rate": a.tool_rate, "chat_data": HERE / "chat_data.py",
                                  "t_tool": HERE / "t_tool.py", "extra_conversations": a.extra_conversations},
                lambda st: stage_conversations(st, a))
    base_model = Path(base["result"]["model"]) if base.get("result") else None
    conv_file = Path(conv["result"]["file"]) if conv.get("result") else None
    mid = step("mid", {"base_ckpt": base_model / "ckpt.pt" if base_model else None, "conversations": conv_file,
                       "steps": a.mid_steps, "lr": a.mid_lr, "batch": a.chat_batch, "block_size": a.block_size,
                       "seed": a.seed, "chat_train": HERE / "chat_train.py", "chat": HERE / "chat.py",
                       **({"harness_tokens": True} if a.harness_tokens else {}),
                       **({"gradient_checkpointing": True} if a.gradient_checkpointing else {})},
               lambda st: stage_chat(st, a, base_model, conv_file, a.mid_steps, a.mid_lr))
    mid_model = Path(mid["result"]["model"]) if mid.get("result") else None

    def sft_body(st):
        if a.sft_conversations is None:
            return {"_status": "skipped", "why": "no --sft-conversations: the mid stage already trained on the "
                    "only conversation source; a separate SFT set (repairs after a failing tool verdict) is the "
                    "next data to build"}
        return stage_chat(st, a, mid_model, a.sft_conversations, a.sft_steps, a.sft_lr)
    sft = step("sft", {"mid_ckpt": mid_model / "ckpt.pt" if mid_model else None,
                       "conversations": a.sft_conversations, "steps": a.sft_steps, "lr": a.sft_lr}, sft_body)
    chat_model = Path(sft["result"]["model"]) if sft.get("status") == "done" else mid_model

    step("rl", {"model": chat_model / "ckpt.pt" if chat_model else None},
         lambda st: {"_status": "skipped", "why": "t/rl_grpo.py samples the document format (Problem/Signature "
                     "heads), not the chat format, and the feasibility measurement (t/RL-DESIGN-2026-09-26.md) "
                     "found 0.6% of problems solvable, too few to reinforce; RL through engine.py is the next port"})
    step("eval", {"model": chat_model / "ckpt.pt" if chat_model else None, "conversations": conv_file,
                  "dev": a.dev, "max_tokens": a.max_tokens, "chat_eval": HERE / "chat_eval.py",
                  "t_tool": HERE / "t_tool.py", "engine": HERE / "engine.py", "chat": HERE / "chat.py",
                  # the engine's t tool runs through the harness's registry (DAWNR-HARNESS.md)
                  "harness_runtime": HERE / "dawnr_harness" / "runtime.py",
                  "harness_tools": HERE / "dawnr_harness" / "tools.py",
                  "harness_checker": HERE / "dawnr_harness" / "checker.py"},
         lambda st: stage_eval(st, a, chat_model, conv_file))

    def report_body(st):
        import dawnr_report
        path = dawnr_report.write(a.out, heldout_tag=a.heldout_tag, split=a.split)
        return {"report": str(path)}
    # the report always regenerates: it only reads what the stages wrote
    stages["report"].record.unlink(missing_ok=True)
    step("report", {"stages": [str(stages[n].record) for n in STAGES[:-1]], "heldout_tag": a.heldout_tag},
         report_body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
