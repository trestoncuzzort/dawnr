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

import re                                                       # noqa: E402

import fuzz_lower                                               # noqa: E402
import harness                                                  # noqa: E402
import loop_dataset                                             # noqa: E402
import py_sandbox                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_first_rows                                          # noqa: E402
import spec_given                                               # noqa: E402
import spec_quality                                             # noqa: E402
import student_rows                                             # noqa: E402
import surface                                                  # noqa: E402

TEMPERATURE, TOP_P = 0.7, 0.95
_PYTHON = re.compile(r"```(?:python|py)\s*\n(.*?)```", re.S)


def python_of(reply: str) -> str | None:
    """The first fenced python block of a reply, or None."""
    m = _PYTHON.search(reply or "")
    return m.group(1) if m and m.group(1).strip() else None


def written_python(decode, ids: list[str], P: dict, attempts: int, batch: int, max_new: int) -> tuple[dict, dict]:
    """Step 0 of the --python route: (problem -> a Python solution the student wrote that passes the
    problem's tests in the sandbox, problem -> counts). One greedy attempt, then sampled ones."""
    python, counts = {}, {t: {"python attempts": 0, "python": None} for t in ids}
    for attempt in range(attempts):
        todo = [t for t in ids if t not in python]
        for start in range(0, len(todo), batch):
            chunk = todo[start:start + batch]
            replies = decode([spec_first_rows.python_question(P[t]) for t in chunk],
                             0.0 if attempt == 0 else TEMPERATURE, attempt, chunk[0], max_new)
            for t, (text, _stopped, _ntok) in zip(chunk, replies):
                counts[t]["python attempts"] += 1
                code = python_of(text)
                if code is None:
                    continue
                out = py_sandbox.run_tests(code, P[t]["rec"]["test_list"])
                if out.get("all_pass"):
                    python[t] = code
                    counts[t]["python"] = attempt
    return python, counts


def written_specifications(decode, python: dict, P: dict, samples: int, batch: int, max_new: int) -> dict:
    """Step 1 of the --python route: problem -> [(label, task)] the student wrote from the problem,
    its tests and its own tested Python. They are scored with every other candidate afterwards."""
    out = {t: [] for t in python}
    ids = list(python)
    for attempt in range(samples + 1):
        for start in range(0, len(ids), batch):
            chunk = ids[start:start + batch]
            replies = decode([spec_first_rows.spec_question(P[t], python[t]) for t in chunk],
                             0.0 if attempt == 0 else TEMPERATURE, 100 + attempt, chunk[0], max_new)
            for t, (text, _stopped, _ntok) in zip(chunk, replies):
                block = se.find_block(text)
                if block is None:
                    continue
                try:
                    out[t].append((f"written/{attempt}", surface.parse(block)))
                except Exception:                               # noqa: BLE001
                    continue
    return out


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


MIN_REFERENCE_DRAWS = 10
MIN_REFERENCE_COMPLETENESS = 0.6


def reference_keeps(r: dict) -> bool:
    """The reference check as a keep rule on the training side: the specification agrees with the
    problem's solution on at least ten drawn inputs, and of the mutated outputs judged on those
    inputs it rejects at least 60% (SAFE's floor for a usable specification, arXiv:2410.15756
    3.2). A specification that is true of the right answer and of most wrong ones is not a
    training example for specification writing."""
    if r.get("status") != "agrees" or r.get("draws", 0) < MIN_REFERENCE_DRAWS:
        return False
    import spec_check
    return spec_check.complete(r, MIN_REFERENCE_COMPLETENESS) is not False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--from-samples", nargs="*", default=[], metavar="TAG")
    ap.add_argument("--given-specs", type=Path, metavar="JSONL",
                    help='specifications to prove, one problem a line: {"task_id", "tasks": [task JSON, ...], '
                         '"sources": [...]}; each is stripped of its body and scored like any other candidate')
    ap.add_argument("--python", type=int, default=0, metavar="K",
                    help="the student first writes Python (K attempts, each run on the problem's tests in "
                         "t/py_sandbox.py), then specifications from the problem and that Python, and the "
                         "proof question shows it too; rows of t/spec_first_rows.py")
    ap.add_argument("--spec-samples", type=int, default=4, help="--python: sampled specifications after the greedy one")
    ap.add_argument("--reference-python", action="store_true",
                    help="TRAINING PROBLEMS ONLY: the Python shown is the problem's own solution (no step 0), and a "
                         "specification is kept only if it also agrees with that solution on drawn inputs "
                         "(t/spec_check.py, at least 10 of 100). Refused for any id outside the training side.")
    ap.add_argument("--specs-only", action="store_true", help="write the kept specifications and ask for no proof")
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
    if not a.from_samples and not a.python and not a.given_specs and not a.reference_python:
        ap.error("give --from-samples, --given-specs, --python, --reference-python, or a mix")
    if a.reference_python:
        if a.python:
            ap.error("--reference-python replaces step 0; do not give --python with it")
        import graded_pool                                      # noqa: E402
        allowed = graded_pool.training_ids(HERE / "out" / "loop" / "split-v5.json", se.pool(a.pool))
        outside = [t for t in ids if int(t) not in allowed]
        if outside:
            raise SystemExit(f"spec_first: --reference-python is for training problems; not on the training side: {outside[:5]}")
    given = {}
    if a.given_specs:
        for line in a.given_specs.read_text(encoding="utf-8").splitlines():
            if line.strip():
                g = json.loads(line)
                given[str(g["task_id"])] = list(zip(g["sources"], g["tasks"]))
    python, python_counts, written, model, tokenizer, student_generate = {}, {}, {}, None, None, None
    if a.python or a.reference_python:
        if a.stage1_only:
            ap.error("--python and --reference-python need the model; they cannot run with --stage1-only")
        import student_generate                                 # noqa: E402  (loads torch)
        model, tokenizer = student_generate.load(a.model)

        def decode(conversations, temperature, salt, first, max_new):
            return student_generate.decode(model, tokenizer, conversations, max_new, temperature, TOP_P,
                                           student_generate.problem_seed(salt, first))
        if a.reference_python:
            python = {t: P[t]["rec"]["code"].strip("\n") for t in ids if (P[t]["rec"].get("code") or "").strip()}
        else:
            python, python_counts = written_python(decode, ids, P, a.python, a.batch, a.max_new)
            print(f"spec_first: {len(python)} of {len(ids)} problems have a Python solution that passes "
                  "their tests", flush=True)
        written = written_specifications(decode, python, P, a.spec_samples, a.batch, a.max_new)
    per, stats = {}, {}
    for tid in ids:
        tasks = list(written.get(tid, [])) + list(given.get(tid, []))
        for tag in a.from_samples:
            d = se.OUT_ROOT / se.model_tag(tag)
            try:
                e = json.loads((d / "extract.json").read_text(encoding="utf-8")).get(tid) or {}
            except (OSError, ValueError):
                e = {}
            if e.get("stage") == "task" and (d / "tasks" / f"{e['name']}.json").exists():
                tasks.append((f"{tag}/{e['name']}", harness.load(d / "tasks" / f"{e['name']}.json")))
        per[tid], counts = kept_specifications(tasks, P[tid], a.per_problem)
        stats[tid] = {"one-shot tasks": len(tasks) - len(written.get(tid, [])),
                      "written specifications": len(written.get(tid, [])), **python_counts.get(tid, {}),
                      **counts, "asked": 0, "taken": None, "refusals": {}}
    if a.reference_python:
        # training problems: the reference check as a second filter (never available for a real question)
        import random
        import spec_check                                       # noqa: E402
        rnd, dropped = random.Random(1), 0
        for tid in ids:
            keep = []
            for k in per[tid]:
                try:
                    r = spec_check.check_task(k["task"], P[tid], 100, rnd)
                except Exception:                               # noqa: BLE001
                    r = {"status": "check raised"}
                if reference_keeps(r):
                    keep.append(dict(k, reference={"draws": r["draws"], "skipped": r.get("skipped"),
                                                   "completeness": r.get("completeness")}))
                else:
                    dropped += 1
            per[tid] = keep
            stats[tid]["kept"] = len(keep)
        print(f"spec_first: the reference check drops {dropped} specifications the tests had kept", flush=True)
    with_spec = [t for t in ids if per[t]]
    print(f"spec_first: {len(with_spec)} of {len(ids)} problems have a kept specification "
          f"({sum(len(per[t]) for t in ids)} specifications)", flush=True)

    d = se.outdir(a.tag)
    if a.python and python:
        # the student's own tested Python is the gate's second artifact (t/spec_gate.py); keep it
        (d / "python.jsonl").write_text("".join(
            json.dumps({"task_id": int(t), "code": python[t], "attempt": python_counts.get(t, {}).get("python")}) + "\n"
            for t in ids if t in python), encoding="utf-8")
    (d / "kept-specs.jsonl").write_text("".join(
        json.dumps({"task_id": int(t), "tasks": [k["task"] for k in per[t]], "sources": [k["source"] for k in per[t]],
                    "scores": [k["scores"] for k in per[t]]}) + "\n" for t in with_spec), encoding="utf-8")
    summary = {"problems": len(ids), "with a kept specification": len(with_spec), "per_problem": stats,
               "thresholds": {"correctness": spec_quality.MIN_CORRECTNESS, "completeness": spec_quality.MIN_COMPLETENESS}}
    if a.stage1_only or a.specs_only:
        (d / "spec_first.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
        return 0

    lock = se.tag_lock(d)
    if lock is None:
        raise SystemExit(f"spec_first: another generator holds {a.tag}")
    if model is None:
        import student_generate                                 # noqa: E402  (loads torch)
        model, tokenizer = student_generate.load(a.model)
    taken: dict[str, dict] = {}
    started = time.monotonic()
    for attempt in range(a.samples + 1):
        temperature = 0.0 if attempt == 0 else TEMPERATURE
        todo = [(t, k) for t in with_spec if t not in taken for k in range(len(per[t]))]
        for start in range(0, len(todo), a.batch):
            chunk = todo[start:start + a.batch]
            conversations = [spec_first_rows.proof_question(per[t][k]["task"], python[t]) if t in python
                             else question(per[t][k]["task"]) for t, k in chunk]
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
               "spec_first": {"from": a.from_samples, "per_problem": a.per_problem, "samples": a.samples,
                              "python": a.python, "spec_samples": a.spec_samples if a.python else None}}
    for t, r in taken.items():
        se.write_record(d / "raw" / f"{t}.json", {
            "task_id": t, "fn": P[t]["fn"], "model": str(a.model), "digest": "", "pool_version": a.pool,
            "prompt_version": "spec-first", "options": options, "messages": r["messages"], "reply": r["reply"],
            "reply_tokens": r["tokens"], "done_reason": "stop" if r["stopped"] else "length",
            "spec_first": {"attempt": r["attempt"], "specification": r["specification"], "scores": r["scores"]}})
    summary["answered"] = len(taken)
    if a.python:
        summary["with a tested Python solution"] = len(python)
    (d / "spec_first.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    lock.close()
    print(f"spec_first: {len(taken)} problems answered", flush=True)
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
