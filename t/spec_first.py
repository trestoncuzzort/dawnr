#!/usr/bin/env python3
"""t/spec_first.py -- the specification first, the proof second (2026-10-01).

    ~/.venv-t/bin/python t/spec_first.py --model DIR --from-samples TAG [TAG ...] --tag OUT \\
        --ids-file ids.txt [--per-problem 3] [--samples 2]

SAFE synthesizes specifications and proofs in two stages (arXiv:2410.15756, 3.2 and 3.3): a
specification is kept when it holds on at least 80% of the problem's test cases and rejects at
least 60% of mutated ones, up to three a function, and proofs are then written for the kept
specifications. Registered here as an arm in t/PREDICT-2026-10-01-several-answers.md.

Stage 1 needs no model. Every well-formed task among a problem's one-shot answers (the answer
sets named by --from-samples, already extracted) gives up its body and its lemmas, and what is
left is scored on the problem's own tests by t/spec_quality.py. The kept ones are deduplicated
with the task's name erased and ordered most complete first.

Stage 2 asks the student each kept specification as a specification-given question, in the words
t/student_rows.py trained it on: once greedy, then --samples times at temperature 0.7. An answer
is taken when it parses, carries the given specification unchanged (t/spec_given.kept), is well
formed and passes the problem's tests. The first taken answer is the problem's, and the answer
set OUT holds one record per answered problem in t/spec_experiment.py's layout, so extract, tests,
the kernels, the reference check and the scorers read it as any other.

OUT/spec_first.json records, per problem, what was scored, kept, asked and taken.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fuzz_lower                                               # noqa: E402
import harness                                                  # noqa: E402
import loop_dataset                                             # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_given                                               # noqa: E402
import spec_quality                                             # noqa: E402
import student_rows                                             # noqa: E402
import surface                                                  # noqa: E402

TEMPERATURE, TOP_P = 0.7, 0.95


def specification_of(task: dict) -> dict:
    """The task with its body and lemmas removed: what a specification-given question shows."""
    spec = copy.deepcopy(task)
    spec["body"] = []
    if "lemmas" in spec:
        spec["lemmas"] = []
    return spec


def _nameless(spec: dict) -> str:
    return surface.print_task(se.rename_task(copy.deepcopy(spec), "f"))


def kept_specifications(tasks: list[tuple[str, dict]], entry: dict, per_problem: int) -> tuple[list[dict], dict]:
    """([{"source", "task", "scores"}] most complete first, counts) from (source, extracted task) pairs."""
    seen, kept = set(), []
    counts = {"scored": 0, "kept": 0, "duplicate": 0, "dropped": 0, "unscorable": 0}
    for order, (source, task) in enumerate(tasks):
        spec = specification_of(task)
        try:
            text = _nameless(spec)
            surface.parse(surface.print_task(spec))             # it must survive its own printing
        except Exception:                                       # noqa: BLE001
            counts["unscorable"] += 1
            continue
        s = spec_quality.scores(spec, entry)
        counts["scored"] += 1
        if "unscorable" in s:
            counts["unscorable"] += 1
        elif not spec_quality.keeps(s):
            counts["dropped"] += 1
        elif text in seen:
            counts["duplicate"] += 1
        else:
            seen.add(text)
            kept.append({"source": source, "task": spec, "scores": s, "order": order})
    kept.sort(key=lambda k: (-k["scores"]["completeness"], -k["scores"]["correctness"], k["order"]))
    counts["kept"] = min(len(kept), per_problem)
    return kept[:per_problem], counts


def question(spec: dict) -> list[dict]:
    return [{"role": "system", "content": se.STUDENT_SYSTEM},
            {"role": "user", "content": student_rows.ASK + loop_dataset.fence(surface.print_task(spec).strip())}]


def accept(reply: str, spec: dict, entry: dict) -> tuple[str | None, str]:
    """(the answer's printed task, "taken") or (None, the first gate that refused it)."""
    block = se.find_block(reply)
    if block is None:
        return None, "no task block"
    try:
        task = surface.parse(block)
    except Exception:                                           # noqa: BLE001
        return None, "does not parse"
    why = spec_given.kept(spec, task)
    if why is not None:
        return None, "specification changed: " + why
    try:
        errs = fuzz_lower.check_wf(task)
        if errs and task.get("t") == 0 and not fuzz_lower.check_wf(dict(task, t=1)):
            task, errs = dict(task, t=1), []                    # the derivable format line (extract --promote-header)
    except Exception as e:                                      # noqa: BLE001
        errs = [f"{type(e).__name__}: {e}"]
    if errs:
        return None, "not well formed"
    if not all(se.run_point(task, p)["verdict"] == "pass" for p in entry["points"]):
        return None, "fails a test"
    return surface.print_task(task), "taken"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--from-samples", nargs="+", required=True, metavar="TAG")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--ids-file", type=Path, required=True)
    ap.add_argument("--pool", choices=se.POOL_VERSIONS, default="v5")
    ap.add_argument("--per-problem", type=int, default=3)
    ap.add_argument("--samples", type=int, default=2, help="sampled attempts after the greedy one")
    ap.add_argument("--max-new", type=int, default=1024)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--stage1-only", action="store_true", help="score and keep specifications; ask nothing")
    a = ap.parse_args(argv)

    P = {str(k): v for k, v in se.pool(a.pool).items()}
    ids = [x for x in a.ids_file.read_text(encoding="utf-8").split() if x.strip()]
    per, stats = {}, {}
    for tid in ids:
        tasks = []
        for tag in a.from_samples:
            d = se.OUT_ROOT / se.model_tag(tag)
            try:
                e = json.loads((d / "extract.json").read_text(encoding="utf-8")).get(tid) or {}
            except (OSError, ValueError):
                e = {}
            if e.get("stage") == "task" and (d / "tasks" / f"{e['name']}.json").exists():
                tasks.append((f"{tag}/{e['name']}", harness.load(d / "tasks" / f"{e['name']}.json")))
        per[tid], counts = kept_specifications(tasks, P[tid], a.per_problem)
        stats[tid] = {"one-shot tasks": len(tasks), **counts, "asked": 0, "taken": None, "refusals": {}}
    with_spec = [t for t in ids if per[t]]
    print(f"spec_first: {len(with_spec)} of {len(ids)} problems have a kept specification "
          f"({sum(len(per[t]) for t in ids)} specifications)", flush=True)

    d = se.outdir(a.tag)
    summary = {"problems": len(ids), "with a kept specification": len(with_spec), "per_problem": stats,
               "thresholds": {"correctness": spec_quality.MIN_CORRECTNESS, "completeness": spec_quality.MIN_COMPLETENESS}}
    if a.stage1_only:
        (d / "spec_first.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
        return 0

    import student_generate                                     # noqa: E402  (loads torch)
    lock = se.tag_lock(d)
    if lock is None:
        raise SystemExit(f"spec_first: another generator holds {a.tag}")
    model, tokenizer = student_generate.load(a.model)
    taken: dict[str, dict] = {}
    started = time.monotonic()
    for attempt in range(a.samples + 1):
        temperature = 0.0 if attempt == 0 else TEMPERATURE
        todo = [(t, k) for t in with_spec if t not in taken for k in range(len(per[t]))]
        for start in range(0, len(todo), a.batch):
            chunk = todo[start:start + a.batch]
            conversations = [question(per[t][k]["task"]) for t, k in chunk]
            replies = student_generate.decode(model, tokenizer, conversations, a.max_new, temperature, TOP_P,
                                              student_generate.problem_seed(attempt, chunk[0][0]))
            for (t, k), msgs, (text, stopped, ntok) in zip(chunk, conversations, replies):
                stats[t]["asked"] += 1
                if t in taken:
                    continue                                    # an earlier specification of this problem was just proved
                answer, why = accept(text, per[t][k]["task"], P[t])
                if answer is None:
                    stats[t]["refusals"][why.split(":")[0]] = stats[t]["refusals"].get(why.split(":")[0], 0) + 1
                    continue
                taken[t] = {"reply": loop_dataset.fence(answer.strip()), "messages": msgs, "tokens": ntok,
                            "stopped": stopped, "attempt": attempt, "specification": per[t][k]["source"],
                            "scores": per[t][k]["scores"]}
                stats[t]["taken"] = {"attempt": attempt, "specification": per[t][k]["source"]}
        print(f"spec_first: attempt {attempt} ({'greedy' if attempt == 0 else 'sampled'}): "
              f"{len(taken)} of {len(with_spec)} problems answered ({time.monotonic() - started:.0f} s)", flush=True)
    options = {"temperature": TEMPERATURE, "top_p": TOP_P, "num_predict": a.max_new, "decoder": "transformers-batched",
               "spec_first": {"from": a.from_samples, "per_problem": a.per_problem, "samples": a.samples}}
    for t, r in taken.items():
        se.write_record(d / "raw" / f"{t}.json", {
            "task_id": t, "fn": P[t]["fn"], "model": str(a.model), "digest": "", "pool_version": a.pool,
            "prompt_version": "spec-first", "options": options, "messages": r["messages"], "reply": r["reply"],
            "reply_tokens": r["tokens"], "done_reason": "stop" if r["stopped"] else "length",
            "spec_first": {"attempt": r["attempt"], "specification": r["specification"], "scores": r["scores"]}})
    summary["answered"] = len(taken)
    (d / "spec_first.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    lock.close()
    print(f"spec_first: {len(taken)} problems answered", flush=True)
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
