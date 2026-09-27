"""chat_eval.py: judge a chat-trained locallm with the proof engine's own grader.

    python3 locallm/chat_eval.py --model <dir> --conversations conv.jsonl --out eval.json \
        [--dev 100] [--val 0] [--max-tokens 400]

nanochat's scripts/chat_eval.py (https://github.com/karpathy/nanochat) samples
an answer per task problem through the engine and checks it (GSM8K's number,
HumanEval's tests). dawnr's checks are the project's own, and nothing here
re-implements one:

* dev problems (t/r12-dev-ids.json: MBPP train-side problems no training
  document names, the set r12 chooses stopping steps on) are asked with the
  prompt the r12 generator uses (loop_locallm.problem_head with its two
  Example lines), greedily, through the engine with the t tool live; the
  final program is graded by t/rl_reward.local_signals and rl_reward.tier:
  none, parses, typed, tests (the problem's assertions and 50 drawn inputs
  against its reference). The proof tiers need Dafny; `--prove` is not
  offered here, so the report says the top tiers were not asked.
* validation conversations (the corpus documents chat_data.py put on the
  validation side of the hash split) are asked with their user turn; the
  final program is checked by t_tool (parses, well formed, the examples).

The held-out evaluation problems are never asked: an id in the split's
eval_ids is refused by name.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "t"))


def ask(engine, tok, user: str, max_tokens: int) -> dict:
    import chat
    from engine import reply_parts
    prompt = chat.render_for_completion(tok, {"messages": [{"role": "user", "content": user}]})
    results, _masks = engine.generate_batch(prompt, 1, max_tokens=max_tokens, temperature=0.0, seed=0)
    parts = reply_parts(tok, results[0])
    calls = engine.rows[0].tool_calls
    ended = engine.rows[0].completed
    return {"parts": parts, "program": chat.final_program(parts) if parts else None,
            "tool_calls": len(calls), "tool_verdicts": [c[1] for c in calls], "ended": ended,
            "unclosed_call": engine.rows[0].in_tool_block,
            "new_tokens": len(results[0])}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--conversations", type=Path, default=None, help="chat_data.py JSONL (validation side is asked)")
    ap.add_argument("--split", type=Path, default=ROOT / "t" / "out" / "loop" / "split-v5.json")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dev", type=int, default=100, help="how many dev problems to ask (0: none)")
    ap.add_argument("--val", type=int, default=0, help="how many validation conversations to ask (0: all)")
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--device", default=None)
    a = ap.parse_args(argv)

    import chat
    import loop_filter
    import loop_locallm
    import rl_reward
    import spec_experiment as se
    import t_tool
    from checkpoint import load_checkpoint
    from engine import Engine

    model, tok, _ = load_checkpoint(a.model, a.device)
    if not chat.has_chat_tokens(tok):
        raise SystemExit(f"{a.model} has no chat tokens; chat_eval judges chat-trained checkpoints")
    engine = Engine(model, tok)
    eval_ids = {int(i) for i in json.loads(a.split.read_text(encoding="utf-8"))["eval_ids"]}
    started = time.monotonic()
    out: dict = {"model": str(a.model), "max_tokens": a.max_tokens, "decoding": "greedy"}
    rows_path = a.out.with_suffix(".rows.jsonl")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    rows_file = rows_path.open("w", encoding="utf-8")

    if a.dev:
        dev = sorted(loop_filter.r12_dev_ids())[:a.dev]
        leak = set(dev) & eval_ids
        if leak:
            raise SystemExit(f"dev ids overlap the held-out evaluation ids: {sorted(leak)[:5]}")
        pool = se.pool("v5")
        tiers, tool_rows, ended, unclosed = Counter(), 0, 0, 0
        for tid in dev:
            entry = pool[tid]
            user = loop_locallm.problem_head(entry, with_examples=True).rstrip("\n")
            got = ask(engine, tok, user, a.max_tokens)
            sig = rl_reward.local_signals(tid, got["program"] or "", entry)
            tier = rl_reward.tier(sig)
            tiers[tier] += 1
            tool_rows += got["tool_calls"] > 0
            ended += got["ended"]
            unclosed += got["unclosed_call"]
            rows_file.write(json.dumps({"set": "dev", "task_id": tid, "tier": tier, "stage": sig.get("stage"),
                                        "tests": sig.get("tests"), **{k: got[k] for k in
                                        ("program", "tool_calls", "tool_verdicts", "ended", "unclosed_call", "new_tokens")}}) + "\n")
        out["dev"] = {"asked": len(dev), "tiers": {t: tiers.get(t, 0) for t in rl_reward.ORDER},
                      "at_least_typed": sum(tiers[t] for t in rl_reward.ORDER[2:]),
                      "tests_passed": sum(tiers[t] for t in rl_reward.ORDER[3:]),
                      "used_tool": tool_rows, "unclosed_call": unclosed, "ended": ended,
                      "proof": "not asked (the proof tiers need Dafny; rl_reward.prove)"}

    if a.conversations is not None:
        convs = [json.loads(line) for line in a.conversations.read_text(encoding="utf-8").splitlines() if line.strip()]
        val = [c for c in convs if c.get("split") == "val"]
        if a.val:
            val = val[:a.val]
        counts = Counter()
        for c in val:
            user = c["messages"][0]["content"]
            got = ask(engine, tok, user, a.max_tokens)
            verdict = t_tool.call(got["program"], user) if got["program"] else "parses: no: no program"
            lines = verdict.split("\n")
            examples = [ln for ln in lines if ln.startswith("example")]
            counts["asked"] += 1
            counts["parses"] += "parses: yes" in lines
            counts["well_formed"] += "well formed: yes" in lines
            counts["examples_all_pass"] += bool(examples) and all(ln.endswith(": pass") for ln in examples)
            counts["exact_program"] += (got["program"] or "").strip() == chat.final_program(
                c["messages"][1]["content"]).strip()
            counts["used_tool"] += got["tool_calls"] > 0
            counts["unclosed_call"] += got["unclosed_call"]
            counts["ended"] += got["ended"]
            rows_file.write(json.dumps({"set": "val", "source": c.get("source"), "verdict": verdict,
                                        **{k: got[k] for k in ("program", "tool_calls", "ended", "unclosed_call",
                                                                "new_tokens")}}) + "\n")
        out["val"] = dict(counts)
    rows_file.close()
    out["seconds"] = round(time.monotonic() - started, 1)
    out["rows"] = str(rows_path)
    a.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
