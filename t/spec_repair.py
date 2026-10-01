#!/usr/bin/env python3
"""t/spec_repair.py -- hand an answer back with the witness against its specification; keep what the
gate's stage then passes (2026-10-01).

    python3 t/spec_repair.py (--model DIR | --host H:P --name N) --python PYTHON.jsonl \\
        --from TAG [TAG ...] --tag OUT --ids-file ids.txt [--rounds 2] [--samples 2]

The gate's specification stage (t/spec_gate.py) refuses an answer whose specification is false at
the answer of the Python written beside the question, or does not pin that answer down, and it
holds a concrete witness when it does: the input, the Python's output, and the clause that fails
or the wrong output that is also accepted. VeriMed (arXiv:2605.13817) measures what the witness
is worth to a model repairing a formal answer: 98.5% with it, 58.5% with a generic retry, 80.0%
naming the violated requirement. SpecSyn (arXiv:2604.21570) strengthens a specification by
feeding back the variants it fails to discriminate. SAFE's self-debugging (arXiv:2410.15756,
3.3) is the loop's shape: the attempt and the checker's message go back, K samples are drawn,
and the first that the checker accepts is kept.

Candidates are the answers of the sets TAG that pass their problem's tests. If any of a problem's
candidates already passes the stage it is carried over untouched. Otherwise the first candidate
the stage holds a witness against goes back as the conversation t/debug_rows.py trains (the
question, the attempt, the witness in words, "Write the corrected task."), one greedy repair and
--samples sampled ones a round. A repair is judged only if it parses, is well formed and passes
the problem's tests; the first one the stage passes is the problem's answer, else the first one
with a new witness becomes the next round's attempt.

Nothing here uses a reference solution, and nothing is counted here: OUT is an answer set in
t/spec_experiment.py's layout and goes to the seven kernels and the reference check like any
other. OUT/spec_repair.json says how many were carried, repaired and left.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import debug_rows                                               # noqa: E402
import harness                                                  # noqa: E402
import loop_dataset                                             # noqa: E402
import proof_repair                                             # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_gate                                                # noqa: E402
import surface                                                  # noqa: E402

TEMPERATURE, TOP_P = 0.7, 0.95


def stage(task: dict, entry: dict, code: str | None) -> dict:
    """{"passes", "said"}: the stage's verdict and, when it refuses with a witness, the words."""
    v = spec_gate.judge(task, entry, code)
    return {"passes": v["passes"], "why": v["why"],
            "said": None if v["passes"] else debug_rows.spec_message(entry, task, v.get("agreement") or {})}


def repair_question(question: list[dict], attempt: dict, said: str) -> list[dict]:
    return question + [{"role": "assistant", "content": loop_dataset.fence(surface.print_task(attempt).strip())},
                       {"role": "user", "content": said + debug_rows.ASK_AGAIN}]


def run(candidates: dict, P: dict, python: dict, decode, rounds: int, samples: int, batch: int, max_new: int,
        judge=stage) -> tuple[dict, dict]:
    """candidates: tid -> {"question", "tasks": [task, ...]}. Returns (tid -> state, counts)."""
    state = {}
    for t, c in candidates.items():
        verdicts = [judge(task, P[t], python.get(t)) for task in c["tasks"]]
        ok = next((i for i, v in enumerate(verdicts) if v["passes"]), None)
        told = next((i for i, v in enumerate(verdicts) if v["said"]), None)
        i = ok if ok is not None else told if told is not None else 0
        state[t] = {"question": c["question"], "task": c["tasks"][i], "passes": ok is not None,
                    "said": None if ok is not None else verdicts[i]["said"], "why": verdicts[i]["why"], "round": 0, "asked": 0}
    counts = {"candidates": len(state), "pass the stage untouched": sum(1 for s in state.values() if s["passes"]),
              "no witness to act on": sum(1 for s in state.values() if not s["passes"] and not s["said"]), "rounds": []}
    for rnd in range(1, rounds + 1):
        open_ = [t for t in state if not state[t]["passes"] and state[t]["said"]]
        repaired, moved, refusals = 0, 0, {}
        passing: dict[str, list[dict]] = {t: [] for t in open_}
        for attempt in range(samples + 1):
            for start in range(0, len(open_), batch):
                chunk = open_[start:start + batch]
                convs = [repair_question(state[t]["question"], state[t]["task"], state[t]["said"]) for t in chunk]
                replies = decode(convs, 0.0 if attempt == 0 else TEMPERATURE, rnd * 100 + attempt, chunk[0], max_new)
                for t, (text, _stopped, _ntok) in zip(chunk, replies):
                    state[t]["asked"] += 1
                    task, why = proof_repair.cheap(text, P[t], None)
                    if task is None:
                        refusals[why] = refusals.get(why, 0) + 1
                    else:
                        passing[t].append(task)
        for t in open_:
            judged = [(task, judge(task, P[t], python.get(t))) for task in passing[t]]
            win = next(((task, v) for task, v in judged if v["passes"]), None)
            nxt = next(((task, v) for task, v in judged if v["said"]), None)
            if win is not None:
                state[t].update(task=win[0], passes=True, said=None, why="passes", round=rnd)
                repaired += 1
            elif nxt is not None:
                state[t].update(task=nxt[0], said=nxt[1]["said"], why=nxt[1]["why"], round=rnd)
                moved += 1
        counts["rounds"].append({"round": rnd, "sent back": len(open_), "repaired (the stage passes it)": repaired,
                                 "replaced by a repair with a new witness": moved, "refusals": refusals})
    counts["pass the stage at the end"] = sum(1 for s in state.values() if s["passes"])
    return state, counts


def gather(ids: list[str], sources: list[str]) -> dict:
    """tid -> {"question", "tasks", "sources"}: every distinct test-passing answer of the sets, in order."""
    out = {}
    for tid in ids:
        for tag in sources:
            d = se.OUT_ROOT / se.model_tag(tag)
            try:
                e = json.loads((d / "extract.json").read_text(encoding="utf-8")).get(tid) or {}
                t = json.loads((d / "tests.json").read_text(encoding="utf-8")).get(tid) or {}
                raw = json.loads((d / "raw" / f"{tid}.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if e.get("stage") != "task" or t.get("overall") != "pass":
                continue
            task = harness.load(d / "tasks" / f"{e['name']}.json")
            c = out.setdefault(tid, {"question": raw["messages"][:2], "tasks": [], "sources": [], "_seen": set()})
            text = surface.print_task(task)
            if text not in c["_seen"]:
                c["_seen"].add(text)
                c["tasks"].append(task)
                c["sources"].append(f"{tag}/{e['name']}")
    for c in out.values():
        del c["_seen"]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", help="a local merged student directory (loads torch)")
    ap.add_argument("--host", help="host:port[,host:port] of an OpenAI-compatible server holding the student")
    ap.add_argument("--name", default="student")
    ap.add_argument("--python", type=Path, required=True, help="JSONL of {task_id, code}: the tested Python beside each question")
    ap.add_argument("--from", dest="source", nargs="+", required=True, metavar="TAG")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--ids-file", type=Path, required=True)
    ap.add_argument("--pool", choices=se.POOL_VERSIONS, default="v5")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--samples", type=int, default=2)
    ap.add_argument("--max-new", type=int, default=1024)
    ap.add_argument("--batch", type=int, default=8)
    a = ap.parse_args(argv)
    if bool(a.model) == bool(a.host):
        ap.error("give --model or --host")
    P = {str(k): v for k, v in se.pool(a.pool).items()}
    ids = [x for x in a.ids_file.read_text(encoding="utf-8").split() if x in P]
    python = spec_gate.load_python(a.python)
    candidates = gather(ids, a.source)
    print(f"spec_repair: {len(candidates)} of {len(ids)} problems have a test-passing answer", flush=True)
    d = se.outdir(a.tag)
    lock = se.tag_lock(d)
    if lock is None:
        raise SystemExit(f"spec_repair: another generator holds {a.tag}")
    if a.host:
        import python_beside
        decode = python_beside.api_decode("openai", a.host.split(","), a.name)
    else:
        import student_generate                                 # noqa: E402  (loads torch)
        model, tokenizer = student_generate.load(a.model)

        def decode(conversations, temperature, salt, first, max_new):
            return student_generate.decode(model, tokenizer, conversations, max_new, temperature, TOP_P,
                                           student_generate.problem_seed(salt, first))
    state, counts = run(candidates, P, python, decode, a.rounds, a.samples, a.batch, a.max_new)
    options = {"temperature": TEMPERATURE, "top_p": TOP_P, "num_predict": a.max_new,
               "spec_repair": {"from": a.source, "rounds": a.rounds, "samples": a.samples, "python": str(a.python)}}
    for t, s in state.items():
        se.write_record(d / "raw" / f"{t}.json", {
            "task_id": t, "fn": P[t]["fn"], "model": str(a.model or a.name), "digest": "", "pool_version": a.pool,
            "prompt_version": "spec-repair", "options": options, "messages": s["question"],
            "reply": loop_dataset.fence(surface.print_task(s["task"]).strip()), "reply_tokens": None, "done_reason": "stop",
            "spec_repair": {"passes the stage": s["passes"], "why": s["why"], "round": s["round"], "asked": s["asked"]}})
    (d / "spec_repair.json").write_text(json.dumps(counts, indent=1) + "\n", encoding="utf-8")
    lock.close()
    print("spec_repair: " + json.dumps(counts), flush=True)
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
