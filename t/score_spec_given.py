#!/usr/bin/env python3
"""t/score_spec_given.py -- score answers to specification-given questions (2026-10-01).

    python3 t/score_spec_given.py prepare --questions Q.jsonl --answers A.jsonl --tasks DIR --report R.json
    # then all seven kernels over DIR (t/run_par.py --tasks DIR --table TABLE), then:
    python3 t/score_spec_given.py levels --report R.json --table TABLE [--json OUT.json]

`prepare` takes each reply through four gates, in order, and writes the survivors as task files
for the kernels: a `t` block is found; it parses; it carries the question's specification
unchanged (t/spec_given.kept, the misaligned-specification filter); it is well formed (a `t 0`
line over a body that is well formed only as `t 1` is read as `t 1`, as extract --promote-header
does). Every answer's stage and reason are recorded, so a zero can be traced to its gate.

`levels` reads the kernels' table. An answer is proved at level k when at least k of the seven
kernels read `verified / refuted` and none refutes the program. A row the grader could not build
a sabotaged twin for reads `no-twin` in every cell and is NOT run: that is a missing measurement,
counted apart, never as unproved. There are no problem tests in this setting (the questions are
lifted programs), and no reference to compare a specification with: the given contract is the
ground truth, which is why the kept-specification gate comes first.

Questions are t/student_rows.py's held-out rows (`name`, `prompt`, `chosen`); answers are
`{"name", "reply"}` lines. Passing the questions' own `chosen` as the replies measures the
instrument's ceiling.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fuzz_lower                                               # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_given                                               # noqa: E402
import surface                                                  # noqa: E402

VERIFIED = "verified / refuted"
LEVELS = (1, 3, 5, 6, 7)
FENCED = re.compile(r"```t\n(.*?)\n```", re.S)


def question_task(row: dict) -> dict:
    """The task as it was asked: the fenced block of the question's user message."""
    user = row["prompt"][-1]["content"]
    return surface.parse(FENCED.search(user).group(1) + "\n")


def judge(question: dict, reply: str) -> tuple[str, str | None, dict | None]:
    """(stage, why, task): stage is no-block, parse, spec-changed, wf or ready."""
    block = se.find_block(reply)
    if block is None:
        return "no-block", None, None
    try:
        task = surface.parse(block)
    except Exception as e:                                      # noqa: BLE001
        return "parse", str(e)[:200], None
    why = spec_given.kept(question, task)
    if why is not None:
        return "spec-changed", why, None
    try:
        errs = fuzz_lower.check_wf(task)
        if errs and task.get("t") == 0 and not fuzz_lower.check_wf(dict(task, t=1)):
            task, errs = dict(task, t=1), []
    except Exception as e:                                      # noqa: BLE001
        errs = [f"check_wf raised {type(e).__name__}: {e}"[:200]]
    if errs:
        return "wf", "; ".join(errs)[:300], None
    return "ready", None, task


def prepare(questions: list[dict], answers: dict[str, str], tasks_dir: Path) -> dict:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    for old in tasks_dir.glob("*.json"):
        old.unlink()
    entries, tally = {}, Counter()
    for row in questions:
        name = row["name"]
        if name not in answers:
            entries[name] = {"stage": "unanswered", "why": None}
        else:
            stage, why, task = judge(question_task(row), answers[name])
            entries[name] = {"stage": stage, "why": why}
            if task is not None:
                (tasks_dir / f"{name}.json").write_text(json.dumps(task, indent=1), encoding="utf-8")
        tally[entries[name]["stage"]] += 1
    return {"questions": len(questions), "stages": dict(tally), "entries": entries}


def level_of(row: dict | None) -> tuple[str, int]:
    """("no-table" | "no-twin" | "refuted" | "graded", kernels that proved it and refuted its twin)."""
    if not row or set(row) != set(spec_check.KERNELS):
        return "no-table", 0
    cells = list(row.values())
    if all(str(c).startswith("no-twin") for c in cells):
        return "no-twin", 0
    if any(str(c).split(" / ")[0] == "refuted" for c in cells):
        return "refuted", 0
    return "graded", sum(1 for c in cells if c == VERIFIED)


def levels(report: dict, table: Path) -> dict:
    _cols, cells = se.parse_kernel_table(table) if table.exists() else ([], {})
    out = {"questions": report["questions"], "stages": report["stages"], "ready": 0,
           "no twin could be built (not graded)": 0, "a kernel refutes it": 0, "no row in the table": 0}
    best = []
    for name, e in report["entries"].items():
        if e["stage"] != "ready":
            continue
        out["ready"] += 1
        kind, k = level_of(cells.get(name))
        if kind == "no-twin":
            out["no twin could be built (not graded)"] += 1
        elif kind == "refuted":
            out["a kernel refutes it"] += 1
        elif kind == "no-table":
            out["no row in the table"] += 1
        else:
            best.append(k)
    for k in LEVELS:
        out[f"proved by at least {k}" if k < 7 else "proved by all seven"] = sum(1 for b in best if b >= k)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--questions", type=Path, required=True)
    p.add_argument("--answers", type=Path, required=True)
    p.add_argument("--tasks", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p = sub.add_parser("levels")
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--table", type=Path, required=True)
    p.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "prepare":
        questions = [json.loads(l) for l in a.questions.read_text(encoding="utf-8").splitlines() if l.strip()]
        answers = {}
        for line in a.answers.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                answers[r["name"]] = r["reply"]
        report = prepare(questions, answers, a.tasks)
        a.report.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({k: report[k] for k in ("questions", "stages")}))
        return 0
    out = levels(json.loads(a.report.read_text(encoding="utf-8")), a.table)
    if a.json:
        a.json.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
