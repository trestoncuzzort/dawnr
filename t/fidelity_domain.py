#!/usr/bin/env python3
"""Measure the input domain the body-fidelity checks actually cover.

LIFTER-DESIGN.md section 10(a) checks a lifted body against its source by
running both on every point of `interp.domain(task)` and reporting
"points=N bad=M". Section 11 is explicit that this leaves "identity of the
body's statement skeleton beyond the interp domain" unverified. That is the
honest caveat, but a caveat is not a number: nobody reading a coverage table
can tell whether "agrees on N points" means N was the whole domain or a
sliver of it.

This says which. For every task it reports the ladder each parameter draws
from, the size of the full cross product of those ladders, how many points
`interp.domain` actually visits under its MAX_POINTS cap, and the coverage
between them. It also reports the ladder's reach: the widest gap between
consecutive integer values, because a body that diverges from its source
strictly inside that gap is invisible to every check the lifter runs.

    python3 fidelity_domain.py                  # every task in tasks/
    python3 fidelity_domain.py tasks/gcd.json   # named tasks only
    python3 fidelity_domain.py --json           # machine-readable

Standard library only, no dafny, no network. Reading task JSON and counting
generator output is all it does, so it is fast enough to run in a gate.
"""
import glob
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import interp  # noqa: E402


def widest_gap(values):
    """The largest step between consecutive sorted ints, and where it falls.

    Returned as (size, low, high). A single-element ladder has no gap and
    reports (0, v, v). This is the blind spot in one number: any input in
    (low, high) is never tried, so a lift that diverges only there passes.
    """
    vals = sorted(set(values))
    if len(vals) < 2:
        return 0, vals[0] if vals else 0, vals[0] if vals else 0
    best = (0, vals[0], vals[0])
    for a, b in zip(vals, vals[1:]):
        if b - a > best[0]:
            best = (b - a, a, b)
    return best


def measure(path):
    """Domain facts for one task file."""
    with open(path, encoding="utf-8") as f:
        task = json.load(f)

    names = [(p["name"], p["type"]) for p in task["params"]]
    ladders = interp.ladders(task)

    full = 1
    for _, ty in names:
        full *= len(ladders[ty])

    visited = sum(1 for _ in interp.domain(task, names))

    ints = ladders["int"]
    gap, lo, hi = widest_gap(ints)

    return {
        "task": task["name"],
        "params": [{"name": n, "type": t, "ladder": len(ladders[t])}
                   for n, t in names],
        "full_cross": full,
        "visited": visited,
        "coverage": (visited / full) if full else 1.0,
        "capped": visited < full,
        "int_ladder": len(ints),
        "int_min": min(ints),
        "int_max": max(ints),
        "widest_gap": gap,
        "gap_between": [lo, hi],
    }


def main(argv):
    as_json = "--json" in argv
    paths = [a for a in argv[1:] if not a.startswith("--")]
    if not paths:
        here = os.path.dirname(os.path.abspath(__file__))
        paths = sorted(glob.glob(os.path.join(here, "tasks", "*.json")))

    rows = [measure(p) for p in paths]

    if as_json:
        print(json.dumps(rows, indent=2))
        return 0

    print("MAX_POINTS cap: %d" % interp.MAX_POINTS)
    print()
    print("%-16s %-14s %13s %9s %9s"
          % ("task", "params", "full cross", "visited", "coverage"))
    print("-" * 66)
    for r in rows:
        sig = ",".join(p["type"] for p in r["params"])
        print("%-16s %-14s %13s %9s %8.1f%%"
              % (r["task"], sig, "{:,}".format(r["full_cross"]),
                 "{:,}".format(r["visited"]), 100 * r["coverage"]))

    capped = [r for r in rows if r["capped"]]
    print("-" * 66)
    print("%d of %d tasks are truncated by the cap" % (len(capped), len(rows)))
    if capped:
        worst = min(capped, key=lambda r: r["coverage"])
        print("  lowest coverage: %s at %.1f%% (%s of %s points)"
              % (worst["task"], 100 * worst["coverage"],
                 "{:,}".format(worst["visited"]),
                 "{:,}".format(worst["full_cross"])))

    gaps = {(r["widest_gap"], tuple(r["gap_between"])) for r in rows}
    for gap, (lo, hi) in sorted(gaps, reverse=True)[:1]:
        print("  widest untried integer interval: (%s, %s), %s wide"
              % ("{:,}".format(lo), "{:,}".format(hi), "{:,}".format(gap)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
