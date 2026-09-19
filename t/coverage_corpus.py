#!/usr/bin/env python3
"""t/coverage_corpus.py -- how far a whole corpus got through the pipeline, and what stopped the rest.

    python3 t/coverage_corpus.py [--pool v5] [--out t/COVERAGE-apps-2026-09-19.md] [--corpus apps]

ROADMAP 16.3 asks for a second coverage table over a second corpus, so the coverage claim is not a claim about
one benchmark. `t/coverage_census.py` cannot answer it: that one reads Dafny source and says which constructs
a program needs that t lacks, and APPS is Python.

This asks the question the pipeline can answer instead, and it is the better question for a corpus of problems
rather than of proofs: of the corpus's problems, how many did a model answer, how many of those answers were
well-formed t, passed the problem's own tests, and were verified by all seven with the twin refuted -- and for
the ones that got as far as the checkers and stopped, which kernel stopped them and why.

Every number comes from files already on disk: each answer set's extract.json, tests.json and kernels.md.
Nothing is generated and no kernel runs.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SE = HERE / "out" / "spec-experiment"
KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
CORPORA = {"apps": (200000, 300000, "APPS"), "humaneval": (100000, 200000, "HumanEval"),
           "mbpp": (0, 100000, "MBPP")}


def short(cell: str) -> str:
    """The reason a cell is not verified, in a word or two."""
    real = (cell or "").split(" / ", 1)[0].strip().replace(" (FLAKED)", "")
    return real or "?"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", default="apps", choices=sorted(CORPORA))
    ap.add_argument("--pool", default="v5")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    lo, hi, title = CORPORA[a.corpus]
    out = a.out or HERE / f"COVERAGE-{a.corpus}-{time.strftime('%Y-%m-%d')}.md"

    import spec_experiment as se
    pool = se.pool(a.pool)
    problems = {i for i in pool if lo <= int(i) < hi}
    if not problems:
        print(f"pool {a.pool} holds no {title} problem")
        return 1

    answered, wf, passed, clean = set(), set(), set(), set()
    blocked: collections.Counter = collections.Counter()
    sole: collections.Counter = collections.Counter()
    graded_names: set = set()
    for d in sorted(SE.glob("*")):
        try:
            ex = json.loads((d / "extract.json").read_text())
        except (OSError, ValueError):
            continue
        ids = {int(t) for t in ex if t.isdigit() and lo <= int(t) < hi}
        if not ids:
            continue
        answered |= ids & problems
        names = {}
        for tid, v in ex.items():
            if not tid.isdigit() or not (lo <= int(tid) < hi):
                continue
            if v.get("stage") == "task":
                wf.add(int(tid))
                if v.get("name"):
                    names[v["name"]] = int(tid)
        try:
            tests = {v.get("name"): v.get("overall") for v in json.loads((d / "tests.json").read_text()).values()}
        except (OSError, ValueError):
            tests = {}
        for n, verdict in tests.items():
            if verdict == "pass" and n in names:
                passed.add(names[n])
        if not (d / "kernels.md").exists():
            continue
        _cols, cells = se.parse_kernel_table(d / "kernels.md")
        for n, row in cells.items():
            if n not in names:
                continue
            graded_names.add(n)
            ok = [k for k in KERNELS if row.get(k, "").startswith("verified / refuted")]
            if len(ok) == len(KERNELS) and tests.get(n) == "pass":
                clean.add(names[n])
                continue
            missing = [k for k in KERNELS if k not in ok]
            for k in missing:
                blocked[(k, short(row.get(k, "")))] += 1
            if len(missing) == 1:
                sole[missing[0]] += 1

    pct = lambda n: f"{100 * n / len(problems):.1f}%"            # noqa: E731
    lines = [f"# t coverage: {title} ({len(problems)} problems in pool {a.pool})", "",
             f"Written by `t/coverage_corpus.py` on {time.strftime('%Y-%m-%d %H:%MZ', time.gmtime())}, from the",
             "answer sets already on disk. No kernel ran and nothing was generated. ROADMAP 16.3 asks for a",
             "second coverage table over a second corpus; this is the pipeline's own question, since",
             "`coverage_census.py` reads Dafny source and this corpus is Python.", "",
             "## How far the corpus got", "",
             "| stage | problems | share |", "|---|---|---|",
             f"| in the pool (their own examples read as t values) | {len(problems)} | 100% |",
             f"| a model answered | {len(answered)} | {pct(len(answered))} |",
             f"| the answer was well-formed t | {len(wf)} | {pct(len(wf))} |",
             f"| it passed the problem's own tests | {len(passed)} | {pct(len(passed))} |",
             f"| **all seven verified it with the twin refuted** | **{len(clean)}** | {pct(len(clean))} |", "",
             f"{len(graded_names)} answers reached the checkers.", ""]
    if blocked:
        lines += ["## What stopped the ones the checkers saw", "",
                  "One row per kernel and outcome, counted over every graded answer that was not clean. An",
                  "answer usually appears in several rows: it is counted once for each kernel that did not",
                  "verify it.", "", "| kernel | outcome | answers |", "|---|---|---|"]
        for (k, why), n in blocked.most_common(18):
            lines.append(f"| `{k}` | {why} | {n} |")
        lines += ["", "## Sole blockers", "",
                  "Answers where six kernels verified and one did not: the cheapest possible gains, since",
                  "everything else about them is already on the record.", "", "| kernel | answers it alone kept out |",
                  "|---|---|"]
        for k in KERNELS:
            lines.append(f"| `{k}` | {sole.get(k, 0)} |")
        lines.append("")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[6:22]))
    print(f"written to {out.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
