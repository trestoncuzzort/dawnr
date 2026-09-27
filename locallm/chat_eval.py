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

Both sets also get the numbers that say whether the model acts on a failed
check (FINDINGS-repair-2026-09-26.md): the final program (the last call, else
the text) run by the t tool on the prompt's own Example lines; whether an
answer that got a failing verdict made a later call with a different program
(acted on it) or the same one again; whether a failing first verdict ended in
a program that passes every example (repaired); and the calls themselves:
opened, closed, ended inside a call by <|assistant_end|>, out of tokens inside
a call, and the grammar's overrides (engine.py). `--no-grammar` evaluates with
the unmasked engine, to measure what the grammar changes on the same
checkpoint.

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
    row = engine.rows[0]
    return {"parts": parts, "program": chat.final_program(parts) if parts else None,
            "tool_calls": len(row.tool_calls), "calls": [c[0] for c in row.tool_calls],
            "tool_verdicts": [c[1] for c in row.tool_calls], "ended": row.completed,
            "unclosed_call": row.in_tool_block or row.ended_in_call, "ended_in_call": row.ended_in_call,
            "budget_in_call": row.in_tool_block and not row.completed,
            "grammar_overrides": row.grammar_overrides, "new_tokens": len(results[0])}


def verdict_ok(verdict: str) -> bool:
    """A t-tool verdict with nothing wrong in it: parses, well formed, every example passes."""
    lines = [ln for ln in verdict.split("\n") if ln.strip()]
    return bool(lines) and all(ln in ("parses: yes", "well formed: yes") or
                               (ln.startswith("example ") and ln.endswith(": pass")) for ln in lines)


def judge(got: dict, user: str) -> dict:
    """The final program under the t tool on the prompt's examples, and what the answer did with its verdicts."""
    import t_tool
    verdict = t_tool.call(got["program"], user) if got["program"] else "parses: no: no program"
    lines = verdict.split("\n")
    examples = [ln for ln in lines if ln.startswith("example")]
    failed = [i for i, v in enumerate(got["tool_verdicts"]) if not verdict_ok(v)]
    calls = [c.strip() for c in got["calls"]]
    acted = any(any(calls[j] != calls[i] for j in range(i + 1, len(calls))) for i in failed)
    repeated = any(any(calls[j] == calls[i] for j in range(i + 1, len(calls))) for i in failed)
    pass_all = bool(examples) and all(ln.endswith(": pass") for ln in examples)
    return {"verdict": verdict, "parses": "parses: yes" in lines, "well_formed": "well formed: yes" in lines,
            "examples_all_pass": pass_all, "got_failing_verdict": bool(failed), "acted_on_failure": acted,
            "repeated_after_failure": repeated, "repaired": bool(failed) and failed[0] == 0 and pass_all}


COUNTED = ("parses", "well_formed", "examples_all_pass", "got_failing_verdict", "acted_on_failure",
           "repeated_after_failure", "repaired")


def tally(counts, got: dict, judged: dict) -> None:
    counts["asked"] += 1
    for key in COUNTED:
        counts[key] += judged[key]
    counts["used_tool"] += got["tool_calls"] > 0
    counts["opened_call"] += got["tool_calls"] > 0 or got["unclosed_call"]
    counts["closed_every_call"] += got["tool_calls"] > 0 and not got["unclosed_call"]
    counts["unclosed_call"] += got["unclosed_call"]
    counts["ended_in_call"] += got["ended_in_call"]
    counts["budget_in_call"] += got["budget_in_call"]
    counts["ended"] += got["ended"]
    counts["tool_calls_total"] += got["tool_calls"]
    counts["grammar_overrides"] += got["grammar_overrides"]
    counts["answers_overridden"] += got["grammar_overrides"] > 0


ROW_KEYS = ("program", "tool_calls", "calls", "tool_verdicts", "ended", "unclosed_call", "ended_in_call",
            "budget_in_call", "grammar_overrides", "new_tokens")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--conversations", type=Path, default=None, help="chat_data.py JSONL (validation side is asked)")
    ap.add_argument("--split", type=Path, default=ROOT / "t" / "out" / "loop" / "split-v5.json")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dev", type=int, default=100, help="how many dev problems to ask (0: none)")
    ap.add_argument("--val", type=int, default=0, help="how many validation conversations to ask (0: all)")
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--no-grammar", action="store_true", help="the unmasked engine (engine.py's grammar off)")
    ap.add_argument("--device", default=None)
    a = ap.parse_args(argv)

    import chat
    import loop_filter
    import loop_locallm
    import rl_reward
    import spec_experiment as se
    from checkpoint import load_checkpoint
    from engine import Engine

    model, tok, _ = load_checkpoint(a.model, a.device)
    if not chat.has_chat_tokens(tok):
        raise SystemExit(f"{a.model} has no chat tokens; chat_eval judges chat-trained checkpoints")
    engine = Engine(model, tok, grammar=not a.no_grammar)
    eval_ids = {int(i) for i in json.loads(a.split.read_text(encoding="utf-8"))["eval_ids"]}
    started = time.monotonic()
    out: dict = {"model": str(a.model), "max_tokens": a.max_tokens, "decoding": "greedy",
                 "grammar": not a.no_grammar}
    rows_path = a.out.with_suffix(".rows.jsonl")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    rows_file = rows_path.open("w", encoding="utf-8")

    if a.dev:
        dev = sorted(loop_filter.r12_dev_ids())[:a.dev]
        leak = set(dev) & eval_ids
        if leak:
            raise SystemExit(f"dev ids overlap the held-out evaluation ids: {sorted(leak)[:5]}")
        pool = se.pool("v5")
        tiers, counts = Counter(), Counter()
        for tid in dev:
            entry = pool[tid]
            user = loop_locallm.problem_head(entry, with_examples=True).rstrip("\n")
            got = ask(engine, tok, user, a.max_tokens)
            sig = rl_reward.local_signals(tid, got["program"] or "", entry)
            tier = rl_reward.tier(sig)
            tiers[tier] += 1
            judged = judge(got, user)
            tally(counts, got, judged)
            rows_file.write(json.dumps({"set": "dev", "task_id": tid, "tier": tier, "stage": sig.get("stage"),
                                        "tests": sig.get("tests"), "verdict": judged["verdict"],
                                        **{k: judged[k] for k in COUNTED}, **{k: got[k] for k in ROW_KEYS}}) + "\n")
        out["dev"] = {**dict(counts), "asked": len(dev), "tiers": {t: tiers.get(t, 0) for t in rl_reward.ORDER},
                      "at_least_typed": sum(tiers[t] for t in rl_reward.ORDER[2:]),
                      "tests_passed": sum(tiers[t] for t in rl_reward.ORDER[3:]),
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
            judged = judge(got, user)
            tally(counts, got, judged)
            exact = (got["program"] or "").strip() == chat.final_program(c["messages"][1]["content"]).strip()
            counts["exact_program"] += exact
            rows_file.write(json.dumps({"set": "val", "source": c.get("source"), "verdict": judged["verdict"],
                                        "exact_program": exact, **{k: judged[k] for k in COUNTED},
                                        **{k: got[k] for k in ROW_KEYS}}) + "\n")
        out["val"] = dict(counts)
    rows_file.close()
    out["seconds"] = round(time.monotonic() - started, 1)
    out["rows"] = str(rows_path)
    a.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
