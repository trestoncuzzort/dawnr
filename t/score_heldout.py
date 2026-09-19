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
  clean         tests pass AND stable verified / refuted in all seven named
                kernels; partial tables cannot contribute clean answers
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
KERNELS = {"dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"}
FAILING_TESTS = {"fail", "signature", "requires-excluded", "undefined"}


def checked_spec(result: dict, task_file: Path) -> str | None:
    """A set was checked only for the exact task contents its evidence describes."""
    from spec_check import task_sha256
    if result.get("status") not in {"agrees", "disagrees"}:
        return None
    if result.get("status") == "agrees" and result.get("draws", 0) <= 0:
        return None
    try:
        task = json.loads(task_file.read_text(encoding="utf-8"))
        if result.get("task_sha256") == task_sha256(task):
            return result["status"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def score(tag: str, eval_ids: set[int]) -> dict:
    d = se.outdir(tag)
    raw = {int(p.stem) for p in (d / "raw").glob("*.json") if p.stem.isdigit()}
    ext = json.loads((d / "extract.json").read_text(encoding="utf-8")) if (d / "extract.json").exists() else {}
    tests = json.loads((d / "tests.json").read_text(encoding="utf-8")) if (d / "tests.json").exists() else {}
    cols, cells = (se.parse_kernel_table(d / "kernels.md") if (d / "kernels.md").exists() else ([], {}))
    # Set-level provenance cannot prove that any particular answer was checked.
    # Refusals, zero valid draws and evidence for an older task all stay unchecked.
    spec_results = {}
    try:
        sd = json.loads((HERE / "out" / "spec-disagree.json").read_text())
        spec_results = sd.get("results", {})
    except (OSError, ValueError, KeyError, IndexError):
        pass
    r = {"tag": tag, "eval": len(eval_ids), "answered": 0, "task": 0, "tests pass": 0, "graded": 0,
         "clean": 0, "spec disagrees": 0, "clean, spec checked": 0, "spec unchecked": 0,
         "wrong but proven": 0, "kernels": len(cols)}
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
        proven = len(cols) == 7 and set(cols) == KERNELS and all(row.get(c) == CLEAN for c in KERNELS)
        name = t.get("name") or e.get("name") or ""
        outcome = checked_spec(spec_results.get(f"{tag}/{name}", {}), d / "tasks" / f"{name}.json") \
            if proven and passed else None
        r["clean"] += proven and passed
        r["spec disagrees"] += bool(proven and passed and outcome == "disagrees")
        r["clean, spec checked"] += bool(proven and passed and outcome == "agrees")
        r["spec unchecked"] += bool(proven and passed and outcome is None)
        r["wrong but proven"] += proven and t.get("overall") in FAILING_TESTS
    # The gate this project loses at, as one number: of the answers that pass their own tests, how many the
    # seven can prove. Round 6's student converts 3 of 9 where Phi-4-mini converts 3 of 6 and a proof-trained
    # 7B converts 6 of 10, and that difference is the whole story of where the loop is stuck -- it belongs in
    # the table rather than in a paragraph someone has to recompute (2026-09-19).
    r["converts"] = (f"{r['clean']}/{r['tests pass']}"
                     + (f" ({100 * r['clean'] / r['tests pass']:.0f}%)" if r["tests pass"] else ""))
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", type=Path, default=HERE / "out" / "loop" / "split-v3.json")
    ap.add_argument("tags", nargs="+")
    a = ap.parse_args()
    eval_ids = {int(i) for i in json.loads(a.split.read_text(encoding="utf-8"))["eval_ids"]}
    heads = ["tag", "kernels", "eval", "answered", "task", "tests pass", "graded", "clean", "converts",
             "spec disagrees", "clean, spec checked", "spec unchecked", "wrong but proven"]
    print("| " + " | ".join(heads) + " |")
    print("|" + "---|" * len(heads))
    for tag in a.tags:
        r = score(tag, eval_ids)
        print("| " + " | ".join(str(r[h]) for h in heads) + " |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
