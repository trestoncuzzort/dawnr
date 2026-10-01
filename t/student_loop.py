#!/usr/bin/env python3
"""t/student_loop.py -- answer, hear what the gate's cheap checks say, try again (2026-10-01).

    ~/.venv-t/bin/python t/student_loop.py --model DIR --tag TAG --ids-file ids.txt --rounds 2

SAFE's self-debugging at inference (arXiv:2410.15756, section 3.3 and figure 2: an incorrect
answer and the verifier's message go back to the fine-tuned model, and one debugging sample after
one proof sample beats two proof samples). The checks used here are the ones that cost nothing:
does the reply contain a task, does it parse, is it well formed, does it pass the problem's own
tests. They run in this process between rounds. An answer that passes them is kept; one that does
not is sent back with t/debug_rows.message_for's words, the words the student was trained on.
The provers are not consulted in the loop: the final answer set goes to them as any other does.

Output: the answer set TAG in t/spec_experiment.py's layout (the last attempt per problem, with
`attempts` and the repair conversation beside the original prompt, as t/repair.py keeps them), and
TAG's `loop.json` with how many problems passed the cheap checks after each round.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import debug_rows                                               # noqa: E402
import fuzz_lower                                               # noqa: E402
import loop_dataset                                             # noqa: E402
import spec_experiment as se                                    # noqa: E402
import student_generate                                         # noqa: E402
import surface                                                  # noqa: E402


def cheap_check(reply: str, entry: dict, tid: str) -> dict:
    """What extract and tests would say about one reply, without writing anything:
    {"stage", "why", "tests", "attempt"}; `attempt` is the text to show the model again."""
    block = se.find_block(reply)
    if block is None:
        return {"stage": "no-block", "why": None, "tests": None, "attempt": None}
    try:
        task = surface.parse(block)
    except Exception as e:                                      # noqa: BLE001
        return {"stage": "parse", "why": str(e)[:200], "tests": None, "attempt": loop_dataset.fence(block)}
    task = se.rename_task(task, f"mbpp_{tid}__{entry['fn']}" if fuzz_lower.NAME_RE.match(
        f"mbpp_{tid}__{entry['fn']}") else f"mbpp_{tid}")
    try:
        errs = fuzz_lower.check_wf(task)
        if errs and task.get("t") == 0 and not fuzz_lower.check_wf(dict(task, t=1)):
            task, errs = dict(task, t=1), []                    # the derivable format line (extract --promote-header)
    except Exception as e:                                      # noqa: BLE001
        errs = [f"check_wf raised {type(e).__name__}: {e}"[:200]]
    shown = loop_dataset.fence(surface.print_task(task)) if not errs else loop_dataset.fence(block)
    if errs:
        return {"stage": "wf", "why": "; ".join(errs)[:300], "tests": None, "attempt": shown}
    points = [se.run_point(task, p) for p in entry["points"]]
    verdicts = [p["verdict"] for p in points]
    overall = ("pass" if all(v == "pass" for v in verdicts) else
               "signature" if any(v in ("arity", "type") for v in verdicts) else
               "fail" if any(v in ("fail", "crash") for v in verdicts) else
               "requires-excluded" if any(v == "requires-excluded" for v in verdicts) else "undefined")
    return {"stage": "task", "why": None, "tests": {"overall": overall, "points": points}, "attempt": shown}


def passed(check: dict) -> bool:
    return check["stage"] == "task" and check["tests"]["overall"] == "pass"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--ids-file", type=Path, required=True)
    ap.add_argument("--pool", choices=se.POOL_VERSIONS, default="v5")
    ap.add_argument("--rounds", type=int, default=2, help="repair rounds after the first answer")
    ap.add_argument("--max-new", type=int, default=1024)
    ap.add_argument("--batch", type=int, default=16)
    a = ap.parse_args(argv)

    P = {str(k): v for k, v in se.pool(a.pool).items()}
    ids = [x for x in a.ids_file.read_text(encoding="utf-8").split() if x.strip()]
    d = se.outdir(a.tag)
    lock = se.tag_lock(d)
    if lock is None:
        raise SystemExit(f"student_loop: another generator holds {a.tag}")
    model, tokenizer = student_generate.load(a.model)
    options = {"temperature": 0.0, "seed": 1, "num_predict": a.max_new, "decoder": "transformers-batched",
               "loop": {"rounds": a.rounds, "feedback": "parse, wf, tests"}}

    state = {t: {"messages": se.build_prompt(P[t], "s1"), "conversation": None, "reply": None,
                 "check": None, "attempts": 0, "stopped": None, "tokens": None} for t in ids}
    for t in ids:
        state[t]["conversation"] = list(state[t]["messages"])
    history, started = [], time.monotonic()
    for rnd in range(a.rounds + 1):
        todo = [t for t in ids if state[t]["check"] is None or not passed(state[t]["check"])]
        todo = [t for t in todo if rnd == 0 or state[t]["said"] is not None]
        for start in range(0, len(todo), a.batch):
            chunk = todo[start:start + a.batch]
            replies = student_generate.decode(model, tokenizer, [state[t]["conversation"] for t in chunk], a.max_new)
            for t, (text, stopped, ntok) in zip(chunk, replies):
                s = state[t]
                s.update(reply=text, stopped=stopped, tokens=ntok, attempts=s["attempts"] + 1)
                s["check"] = cheap_check(text, P[t], t)
                said = None
                if not passed(s["check"]) and s["check"]["attempt"]:
                    said = debug_rows.message_for(s["check"]["stage"], s["check"]["why"], s["check"]["tests"], None, None)
                s["said"] = said
                if said is not None:
                    s["conversation"] = s["messages"] + [{"role": "assistant", "content": s["check"]["attempt"]},
                                                         {"role": "user", "content": said[1] + debug_rows.ASK_AGAIN}]
        ok = sum(1 for t in ids if state[t]["check"] is not None and passed(state[t]["check"]))
        history.append({"round": rnd, "asked": len(todo), "pass the cheap checks": ok,
                        "seconds": round(time.monotonic() - started, 1)})
        print(f"student_loop: round {rnd}: asked {len(todo)}, {ok} of {len(ids)} pass parse, wf and tests", flush=True)

    for t in ids:
        s = state[t]
        se.write_record(d / "raw" / f"{t}.json", {
            "task_id": t, "fn": P[t]["fn"], "model": str(a.model), "digest": "", "pool_version": a.pool,
            "prompt_version": "s1", "options": options, "messages": s["messages"], "reply": s["reply"],
            "reply_tokens": s["tokens"], "done_reason": "stop" if s["stopped"] else "length",
            "attempts": s["attempts"],
            "repair_messages": s["conversation"] if s["attempts"] > 1 else None})
    (d / "loop.json").write_text(json.dumps({"rounds": history, "problems": len(ids)}, indent=1) + "\n", encoding="utf-8")
    lock.close()
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
