#!/usr/bin/env python3
"""t/score_heldout.py -- score answer sets on the held-out problems only (2026-09-17).

    python3 t/score_heldout.py --split t/out/loop/split-v3.json TAG [TAG ...]

TAG is a directory name under t/out/spec-experiment/ (spec_experiment.py's
layout: raw/, extract.json, tests.json, kernels.md). Every count is over the
split's eval_ids, the problems no training set may contain:

  answered      a reply was recorded
  task          the reply extracted to a well-formed t task
  tests pass    the task passes every one of the problem's tests
  graded        the task has a row in kernels.md
  clean         tests pass AND verified / refuted in every kernel column
                kernels.md has (the column count is printed; clean means
                all seven only when all seven were graded)
  wrong but proven   verified / refuted in every column while failing its
                tests: a proven program for the wrong problem, countable only
                for failing tasks that were graded

One line per tag, so rows for Phi-4-mini, a base model, a trained student and
a model locallm built compare directly. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_experiment as se                                    # noqa: E402

CLEAN = "verified / refuted"


def score(tag: str, eval_ids: set[int]) -> dict:
    d = se.outdir(tag)
    raw = {int(p.stem) for p in (d / "raw").glob("*.json") if p.stem.isdigit()}
    ext = json.loads((d / "extract.json").read_text(encoding="utf-8")) if (d / "extract.json").exists() else {}
    tests = json.loads((d / "tests.json").read_text(encoding="utf-8")) if (d / "tests.json").exists() else {}
    cols, cells = (se.parse_kernel_table(d / "kernels.md") if (d / "kernels.md").exists() else ([], {}))
    # 2026-09-18: an answer can pass its tests and all seven proofs and still hold a specification that
    # disagrees with the problem's own solution on other inputs (t/spec_check.py). Those are counted apart,
    # and "clean, spec checked" is clean minus them: the honest column once the specification is checked too.
    try:
        disagree = {x.split("/", 1)[1] for x in
                    json.loads((HERE / "out" / "spec-disagree.json").read_text())["disagree"]
                    if x.split("/", 1)[0] == tag}
    except (OSError, ValueError, KeyError, IndexError):
        disagree = set()
    r = {"tag": tag, "eval": len(eval_ids), "answered": 0, "task": 0, "tests pass": 0, "graded": 0,
         "clean": 0, "spec disagrees": 0, "clean, spec checked": 0, "wrong but proven": 0, "kernels": len(cols)}
    for tid in eval_ids:
        if tid in raw:
            r["answered"] += 1
        e = ext.get(str(tid), {})
        if e.get("stage") == "task":
            r["task"] += 1
        t = tests.get(str(tid), {})
        passed = t.get("overall") == "pass"
        r["tests pass"] += passed
        row = cells.get(t.get("name") or e.get("name") or "")
        if not row:
            continue
        r["graded"] += 1
        proven = bool(cols) and all(row.get(c) == CLEAN for c in cols)
        name = t.get("name") or e.get("name") or ""
        bad_spec = name in disagree
        r["clean"] += proven and passed
        r["spec disagrees"] += bool(proven and passed and bad_spec)
        r["clean, spec checked"] += bool(proven and passed and not bad_spec)
        r["wrong but proven"] += proven and not passed
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", type=Path, default=HERE / "out" / "loop" / "split-v3.json")
    ap.add_argument("tags", nargs="+")
    a = ap.parse_args()
    eval_ids = {int(i) for i in json.loads(a.split.read_text(encoding="utf-8"))["eval_ids"]}
    heads = ["tag", "kernels", "eval", "answered", "task", "tests pass", "graded", "clean", "spec disagrees",
             "clean, spec checked", "wrong but proven"]
    print("| " + " | ".join(heads) + " |")
    print("|" + "---|" * len(heads))
    for tag in a.tags:
        r = score(tag, eval_ids)
        print("| " + " | ".join(str(r[h]) for h in heads) + " |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
