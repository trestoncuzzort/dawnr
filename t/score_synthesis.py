"""Independent scorer for unaided t synthesis on the composition curriculum.

A candidate is only ever the body of a task whose contract is supplied from
the frozen manifest, so nothing a model writes can change the contract, the
tests or the expected values. Expected values come from the closed-form
oracle, never from running the reference body. Every non-answer is a failure, whether
malformed, contract-altering, undefined, over budget, over time or too long,, and all of them are counted and reported separately.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import signal
import time

import check_wf
from execution_trace import digest
import interp
import surface

SCHEMA = 1
VERDICTS = ("correct", "wrong_output", "malformed", "not_well_formed", "contract_modified",
            "undefined", "over_budget", "timeout", "too_long")


class Timeout(BaseException):
    """Deliberately not an Exception: interpreter handlers must not absorb it."""


def _alarm(seconds):
    def raise_timeout(signum, frame):
        raise Timeout()
    signal.signal(signal.SIGALRM, raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)


def run_case(task, x):
    """Value of the candidate at one input, or a verdict it failed under."""
    env = {"x": x}
    for ret in task["returns"]:
        env[ret["name"]] = None
    funs = interp.funs_of(task, task["body"])
    st = interp.St()
    try:
        if not all(interp.ev(e, env, funs, st) for e in task.get("requires", [])):
            return None, "undefined"
        interp.exec_body(task["body"], env, funs, st)
    except interp.Undef:
        return None, "undefined"
    except (interp.Budget, RecursionError):
        return None, "over_budget"
    value = env[task["returns"][0]["name"]]
    if value is None:
        return None, "undefined"
    return value, None


def _evaluate(entry, completion, result):
    """Verdict fields for one candidate; counters are written into `result`."""
    header = entry["prompt"].partition("\n")[2]
    try:
        task = surface.parse(header + completion)
    except surface.SurfaceError as error:
        return {"verdict": "malformed", "detail": str(error)[:200]}
    except RecursionError:
        return {"verdict": "malformed", "detail": "parser recursion limit"}
    errors = check_wf.check_wf(task)
    if errors:
        return {"verdict": "not_well_formed", "detail": str(errors[0])[:200]}
    contract = {key: task.get(key) for key in
                ("name", "params", "returns", "requires", "ensures", "spec_funs")}
    if digest(contract) != entry["contract_sha256"]:
        return {"verdict": "contract_modified"}
    passed = {}
    for stratum, tests in sorted(entry["tests"].items()):
        hits = 0
        for test in tests:
            value, failure = run_case(task, test["x"])
            result["tests_run"] += 1
            if failure is not None:
                return {"verdict": failure, "failing_x": test["x"]}
            hits += int(value == test["r"])
        passed[stratum] = {"passed": hits, "total": len(tests)}
        result["tests_passed"] += hits
    result["by_stratum"] = passed
    total = sum(len(tests) for tests in entry["tests"].values())
    return {"verdict": "correct" if result["tests_passed"] == total else "wrong_output"}


def score_candidate(entry, completion, *, time_limit, max_chars):
    """One candidate against one held-out task. Caps are per task, not per test."""
    result = {"task_name": entry["task_name"], "split": entry["split"],
              "pattern": entry["pattern"], "chars": len(completion),
              "completion_sha256": sha256(completion.encode()).hexdigest(),
              "tests_run": 0, "tests_passed": 0, "by_stratum": {}}
    if len(completion) > max_chars:
        return {**result, "verdict": "too_long", "seconds": 0.0}
    started = time.monotonic()
    _alarm(time_limit)
    try:
        outcome = _evaluate(entry, completion, result)
    except Timeout:
        outcome = {"verdict": "timeout"}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    return {**result, **outcome, "seconds": time.monotonic() - started}


def score(entries, candidates, *, time_limit, max_chars):
    """Every manifest task is scored: a missing candidate is a malformed answer."""
    rows = []
    for entry in entries:
        completion = candidates.get(entry["task_name"])
        if completion is None:
            rows.append({"task_name": entry["task_name"], "split": entry["split"],
                         "pattern": entry["pattern"], "verdict": "malformed",
                         "detail": "no candidate produced", "tests_run": 0,
                         "tests_passed": 0, "by_stratum": {}})
            continue
        rows.append(score_candidate(entry, completion, time_limit=time_limit,
                                    max_chars=max_chars))
    summary = {verdict: sum(1 for row in rows if row["verdict"] == verdict)
               for verdict in VERDICTS}
    summary = {verdict: count for verdict, count in summary.items() if count}
    by_split, by_stratum = {}, {}
    for row in rows:
        bucket = by_split.setdefault(row["split"], {"tasks": 0, "correct": 0})
        bucket["tasks"] += 1
        bucket["correct"] += int(row["verdict"] == "correct")
        for stratum, counts in row.get("by_stratum", {}).items():
            tally = by_stratum.setdefault(stratum, {"passed": 0, "total": 0})
            tally["passed"] += counts["passed"]
            tally["total"] += counts["total"]
    return {"schema": SCHEMA, "tasks": len(rows), "verdicts": summary,
            "by_split": by_split, "tests_by_stratum": by_stratum, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True,
                        help="eval_synthesis.jsonl from the dataset")
    parser.add_argument("--candidates", type=Path, required=True,
                        help="JSONL of {task_name, completion}")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--split", action="append", default=None)
    parser.add_argument("--time-limit", type=float, default=10.0)
    parser.add_argument("--max-chars", type=int, default=4000)
    args = parser.parse_args()
    entries = [json.loads(line) for line in args.manifest.read_text().splitlines() if line]
    if args.split:
        entries = [entry for entry in entries if entry["split"] in args.split]
    candidates = {}
    for line in args.candidates.read_text().splitlines():
        if not line:
            continue
        row = json.loads(line)
        candidates[row["task_name"]] = row["completion"]
    report = score(entries, candidates, time_limit=args.time_limit, max_chars=args.max_chars)
    report["manifest_sha256"] = sha256(args.manifest.read_bytes()).hexdigest()
    report["candidates_sha256"] = sha256(args.candidates.read_bytes()).hexdigest()
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("tasks", "verdicts", "by_split", "tests_by_stratum")}))


if __name__ == "__main__":
    main()
