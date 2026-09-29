#!/usr/bin/env python3
"""chat_heldout.py: the chat model's one look at the held-out 232, as an answer set the seven kernels grade.

    ~/.venv-locallm/bin/python locallm/chat_heldout.py --model <chat-trained checkpoint dir> --tag <tag> \\
        --prereg t/PREDICT-<date>-<name>.md [--split t/out/loop/split-v5.json] [--max-tokens 800] \\
        [--grammar --max-calls 2] [--answer best-verdict] [--resume] [--device cuda]

Every other arm on the scoreboard is an answer set under t/out/spec-experiment/<tag>/raw/, one
JSON record per held-out problem in the shape t/loop_locallm.py generate writes, then extracted,
tested and graded by `t/grade_lab.sh heldout <tag>` and scored by `t/score_heldout.py`. This
writes that record for a chat-trained checkpoint, so the chat pipeline is judged by the same
harness and the same scorer as the head-prompt arms (one harness for every model, the rule
lm-evaluation-harness states for its own benchmarks, github.com/EleutherAI/lm-evaluation-harness):

* the prompt is the one chat_eval.py asks its dev problems and the r12 generator asks the
  held-out ones (loop_locallm.problem_head with the problem's examples);
* the engine runs with the t tool live, the chat-token grammar and the call budget as asked;
* the answer is chat_eval's policy (best-verdict: the call the tool ranked highest, or the last
  program); the reply carries it between ```t fences, the whole conversation (parts, calls,
  verdicts) stays beside it under "conversation" for the audit.

The one-look rule (t/RUN-NEXT-locallm-r12.md, section E): the 232 are looked at once per
decision, predictions first. This refuses to run unless --prereg names an existing
t/PREDICT-*.md that mentions the tag, and it never overwrites a record; --resume skips the
problems already answered (a killed run leaves whole records only: written by rename).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "t"))

PROMPT_VERSION = "dawnr-chat-head-examples"


def check_prereg(prereg: Path, tag: str) -> None:
    """The look is registered: the file exists under t/ as a PREDICT file and names the tag."""
    if not prereg.is_file():
        raise SystemExit(f"REFUSED: --prereg {prereg} does not exist; register the look first (t/PREDICT-*.md)")
    if not prereg.name.startswith("PREDICT-"):
        raise SystemExit(f"REFUSED: --prereg {prereg} is not a t/PREDICT-*.md file")
    if tag not in prereg.read_text(encoding="utf-8"):
        raise SystemExit(f"REFUSED: {prereg} does not mention the tag {tag!r}; the look must be registered by name")


def record_for(tid: int, entry: dict, user: str, got: dict, meta: dict) -> dict:
    """One raw record in loop_locallm.py generate's shape, plus the conversation for the audit."""
    program = (got.get("program") or "").strip()
    return {"task_id": tid, "fn": entry["fn"], "model": meta["model"], "digest": meta["digest"],
            "checkpoint_sha256": meta["checkpoint_sha256"], "pool_version": meta["pool_version"],
            "prompt_version": PROMPT_VERSION, "options": dict(meta["options"]),
            "messages": [{"role": "user", "content": user}],
            "reply": ("```t\n" + program + "\n```") if program else "",
            "done_reason": "stop" if got.get("ended") else "length",
            "conversation": {k: got.get(k) for k in ("parts", "calls", "tool_verdicts", "tool_calls", "last_program",
                                                       "unclosed_call", "ended_in_call", "new_tokens")}}


def write_answer_set(raw_dir: Path, eval_ids: list[int], pool: dict, reply, meta: dict, resume: bool,
                     log=print) -> dict:
    """Ask every held-out problem through `reply(user, tid) -> got` and write raw/<tid>.json whole or not at all."""
    import loop_locallm
    raw_dir.mkdir(parents=True, exist_ok=True)
    existing = {int(p.stem) for p in raw_dir.glob("*.json")}
    if existing and not resume:
        raise SystemExit(f"REFUSED: {raw_dir} already holds {len(existing)} record(s); an answer set is never "
                         f"overwritten (a second look is a second registration); --resume continues one run")
    counts = {"asked": 0, "resumed": len(existing & set(eval_ids)), "with_program": 0, "ended": 0, "used_tool": 0}
    started = time.monotonic()
    for i, tid in enumerate(eval_ids):
        path = raw_dir / f"{tid}.json"
        if path.exists():
            continue
        entry = pool[tid]
        user = loop_locallm.problem_head(entry, with_examples=True).rstrip("\n")
        got = reply(user, tid)
        rec = record_for(tid, entry, user, got, meta)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(rec, indent=1), encoding="utf-8")
        os.replace(tmp, path)
        counts["asked"] += 1
        counts["with_program"] += bool(rec["reply"])
        counts["ended"] += rec["done_reason"] == "stop"
        counts["used_tool"] += bool(got.get("tool_calls"))
        if (i + 1) % 20 == 0:
            log(f"{i + 1} of {len(eval_ids)} ({time.monotonic() - started:.0f}s)")
    counts["seconds"] = round(time.monotonic() - started, 1)
    counts["records"] = len({int(p.stem) for p in raw_dir.glob('*.json')} & set(eval_ids))
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", type=Path, required=True, help="a chat-trained checkpoint directory")
    ap.add_argument("--tag", required=True, help="the answer set's name under t/out/spec-experiment/")
    ap.add_argument("--prereg", type=Path, required=True, help="the t/PREDICT-*.md that registers this look")
    ap.add_argument("--split", type=Path, default=ROOT / "t" / "out" / "loop" / "split-v5.json")
    ap.add_argument("--max-tokens", type=int, default=800)
    ap.add_argument("--grammar", action="store_true")
    ap.add_argument("--max-calls", type=int, default=None)
    ap.add_argument("--answer", choices=("last", "best-verdict"), default="best-verdict")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--device", default=None)
    a = ap.parse_args(argv)
    if a.max_calls is not None and not a.grammar:
        ap.error("--max-calls works through the grammar; add --grammar")
    check_prereg(a.prereg, a.tag)

    import chat
    import chat_eval
    import spec_experiment as se
    from checkpoint import load_checkpoint
    from continue_from_checkpoint import file_sha256
    from engine import Engine

    split = json.loads(a.split.read_text(encoding="utf-8"))
    eval_ids = sorted(int(i) for i in split["eval_ids"])
    pool_version = split.get("pool", "v1")
    pool = se.pool(pool_version)
    missing = [t for t in eval_ids if t not in pool]
    if missing:
        raise SystemExit(f"REFUSED: {len(missing)} held-out ids are not in pool {pool_version}: {missing[:5]}")
    model, tok, _ = load_checkpoint(a.model, a.device)
    if not chat.has_chat_tokens(tok):
        raise SystemExit(f"{a.model} has no chat tokens; this asks chat-trained checkpoints")
    engine = Engine(model, tok, grammar=a.grammar, max_calls=a.max_calls)
    meta = {"model": f"dawnr-chat:{a.model}", "digest": f"{sum(p.numel() for p in model.parameters())} params",
            "checkpoint_sha256": file_sha256(a.model / "ckpt.pt"), "pool_version": pool_version,
            "options": {"temperature": 0.0, "decoding": "greedy", "max_new_tokens": a.max_tokens,
                        "grammar": a.grammar, "max_calls": a.max_calls, "answer": a.answer,
                        "stop": "assistant-end", "seeding": "engine-seed-0", "prompt": PROMPT_VERSION}}

    def reply(user: str, tid: int) -> dict:
        return chat_eval.answered(chat_eval.ask(engine, tok, user, a.max_tokens), a.answer)

    raw_dir = se.OUT_ROOT / se.model_tag(a.tag) / "raw"
    counts = write_answer_set(raw_dir, eval_ids, pool, reply, meta, a.resume)
    summary = {"tag": a.tag, "model": str(a.model), "prereg": str(a.prereg), "options": meta["options"], **counts}
    (raw_dir.parent / "chat-heldout.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    if counts["records"] != len(eval_ids):
        print(f"INCOMPLETE: {counts['records']} of {len(eval_ids)} records; rerun with --resume", file=sys.stderr)
        return 1
    print(f"next: bash t/grade_lab.sh heldout {a.tag}   (then t/score_heldout.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
