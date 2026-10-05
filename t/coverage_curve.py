#!/usr/bin/env python3
"""t/coverage_curve.py -- how the number of problems proved grows with the number of answers drawn (2026-10-05).

    python3 t/coverage_curve.py --split t/out/loop/split-v5.json --panel clean-182 --verdicts PATH \\
        [--larger] [--level 1] [--json OUT.json] TAG [TAG ...]

A scoreboard row says how many problems are proved when a fixed number of answers is drawn for each (17 for a
prompted model). With a checker that picks the winner, that number is one point on a curve: "Large Language
Monkeys" (Brown et al., arXiv:2407.21787) finds the share of problems solved by any sample growing about linearly
in the logarithm of the number of samples over four orders of magnitude, and that where answers are verified
automatically the growth is performance. This reads answer sets that are already graded (each TAG is one answer
a problem, as t/score_levels.py reads them) and reports, for every k up to the number of sets, how many problems
would be expected to have a counted answer had only k of the sets been drawn: for a problem counted in c of the n
sets, 1 - C(n-c, k)/C(n, k), summed over problems. That is Codex's unbiased estimator of pass@k (Chen et al.,
arXiv:2107.03374, eq. 1) with "passes the tests" replaced by "counted by the gate at this level".

It asks no model and runs no prover. Research receipt e3e11bfe6db1.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import score_levels  # noqa: E402


def expected(counts: list[int], n: int) -> list[float]:
    """curve[k-1]: the expected number of problems with a counted answer among k of the n sets drawn at random,
    given for each problem the number of sets in which it is counted."""
    return [sum(1 - math.comb(n - c, k) / math.comb(n, k) for c in counts) for k in range(1, n + 1)]


def doublings(curve: list[float]) -> list[tuple[int, int, float]]:
    """(k, 2k, problems gained) for k = 1, 2, 4, ... while 2k is on the curve."""
    out, k = [], 1
    while 2 * k <= len(curve):
        out.append((k, 2 * k, curve[2 * k - 1] - curve[k - 1]))
        k *= 2
    return out


def counts(tags: list[str], ids: set[int], verdicts: dict, level: int, min_completeness: float | None, larger: bool) -> dict[int, int]:
    """problem -> in how many of the tags' answer sets it is counted at `level` or above."""
    out = {tid: 0 for tid in ids}
    for tag in tags:
        for tid, v in score_levels.tag_levels(tag, ids, verdicts, min_completeness, larger).items():
            out[tid] += v[0] >= level
    return out


def render(tags: list[str], per: dict[int, int], curve: list[float]) -> str:
    n = len(tags)
    marks = sorted({k for k in (1, 2, 4, 8, 16, 32, 64, n) if k <= n})
    lines = ["| answers drawn | " + " | ".join(str(k) for k in marks) + " |", "|---|" + "---:|" * len(marks),
             "| problems expected to be counted | " + " | ".join(f"{curve[k - 1]:.1f}" for k in marks) + " |", ""]
    lines += [f"From {a} to {b} answers: {gain:+.1f} problems." for a, b, gain in doublings(curve)]
    lines.append(f"Counted in exactly one of the {n} sets: {sum(1 for c in per.values() if c == 1)} problems; "
                 f"in none: {sum(1 for c in per.values() if c == 0)} of {len(per)}.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("tags", nargs="+")
    ap.add_argument("--split", type=Path)
    ap.add_argument("--panel", choices=("clean-182", "clean-200", "all-232"), default="clean-182")
    ap.add_argument("--ids-file", type=Path)
    ap.add_argument("--verdicts", type=Path, required=True)
    ap.add_argument("--level", type=int, default=1, help="count an answer proved by at least this many kernels (default 1)")
    ap.add_argument("--min-completeness", type=float, default=score_levels.MIN_COMPLETENESS)
    ap.add_argument("--larger", action="store_true", help="the reading of record from 2026-10-05 (score_levels --larger)")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    if len(a.tags) < 2:
        raise SystemExit("coverage_curve: a curve needs at least two answer sets")
    ids = score_levels.panel_ids(a.split, a.panel, a.ids_file)
    verdicts = json.loads(a.verdicts.read_text(encoding="utf-8")).get("results", {})
    per = counts(a.tags, ids, verdicts, a.level, a.min_completeness, a.larger)
    curve = expected(list(per.values()), len(a.tags))
    print(render(a.tags, per, curve))
    if a.json:
        a.json.write_text(json.dumps({"tags": a.tags, "level": a.level, "problems": len(ids), "curve": curve,
                                      "counted in": {str(k): v for k, v in sorted(per.items())}}, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
