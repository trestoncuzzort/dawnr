#!/usr/bin/env python3
"""The three-decode protocol's reading (t/PREDICT-2026-10-22-seed-variance.md, "The protocol from here").

Each model is decoded several times on the development panel (seed offsets 0, 1000, 2000) and graded; this reads every
graded arm with v7_local_pair.arm (the same per-problem sets as every pairing of the week), and reports per model the
clean and all-seven count of each decode, the mean, and the per-problem success fraction over the decodes; then the
paired per-problem difference between candidate and baseline: the sum of the fractions' differences (the mean count
difference), the problems that moved in each direction, an exact sign test on the problems whose fraction differs, and
a paired permutation test on the per-problem differences (sign flips, 20,000 draws). A candidate is called better or
worse only on this paired reading, never on one decode's count.

Sources: arXiv:2605.30315 (Resolution Diagnostics for Paired LLM Evaluation: paired per-item tests, the resolution a
panel affords); arXiv:2406.10229 (Quantifying Variance in Evaluation Benchmarks: seed variance of benchmark scores);
arXiv:2107.03374 section 2.1 (the per-problem pass fraction over n samples as the estimator); t/recipes/v7_local_pair.py.

    python3 t/recipes/three_decode_report.py --panel t/out/v6-20261018/dev-95.txt \\
        --baseline v5-20261021-dev-desktop-r2:DIR --baseline v5-20261022-seedoff1000:DIR --baseline v5-20261022-seedoff2000:DIR \\
        --candidate v8-20261021-dev:DIR --candidate v8-20261022-seedoff1000:DIR --candidate v8-20261022-seedoff2000:DIR \\
        --out OUT.json
"""
from __future__ import annotations

import argparse
import json
from math import comb
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "recipes"))

LEVELS = ("1", "7")
NAMES = {"1": "clean", "7": "all_seven"}


def fractions(sets_per_decode: list[set[int]], ids: list[int]) -> dict[int, float]:
    """Per-problem success fraction over the decodes (the pass fraction estimator of arXiv:2107.03374 section 2.1)."""
    n = len(sets_per_decode)
    return {i: sum(1 for s in sets_per_decode if i in s) / n for i in ids}


def sign_test(diffs: dict[int, float]) -> dict:
    """Exact two-sided sign test on the problems whose fraction differs (zero differences are dropped)."""
    up = sum(1 for d in diffs.values() if d > 0)
    down = sum(1 for d in diffs.values() if d < 0)
    n = up + down
    if n == 0:
        return {"up": 0, "down": 0, "p": 1.0}
    k = min(up, down)
    tail = sum(comb(n, j) for j in range(k + 1)) / 2 ** n
    return {"up": up, "down": down, "p": min(1.0, 2 * tail)}


def permutation_test(diffs: dict[int, float], draws: int = 20000, seed: int = 0) -> dict:
    """Paired permutation test: flip the sign of each problem's difference at random; two-sided on the summed difference."""
    values = [d for d in diffs.values() if d != 0]
    observed = sum(values)
    if not values:
        return {"sum": 0.0, "p": 1.0, "draws": 0}
    rng = random.Random(seed)
    hits = 0
    for _ in range(draws):
        total = sum(v if rng.random() < .5 else -v for v in values)
        if abs(total) >= abs(observed) - 1e-12:
            hits += 1
    return {"sum": observed, "p": hits / draws, "draws": draws}


def decode_sets(spec: str, ids: list[int], arm) -> dict:
    """The per-level problem sets of one decode: one graded directory, or several joined with '+' when the panel was
    generated and graded in parts (each part scored on the ids it holds; a problem in no part counts as not solved)."""
    joined: dict = {}
    for part in spec.split("+"):
        tag, graded = part.split(":", 1)
        _, sets, _ = arm(part, set(ids))
        for level, members in sets.items():
            joined.setdefault(level, set()).update(members)
    return joined


def model_reading(name: str, arms: list[tuple[str, set[int]]], ids: list[int]) -> dict:
    counts = [len(s) for _, s in arms]
    frac = fractions([s for _, s in arms], ids)
    return {"model": name, "decodes": [{"tag": t, "count": len(s), "ids": sorted(s)} for t, s in arms],
            "mean": sum(counts) / len(counts), "min": min(counts), "max": max(counts),
            "problems_ever": sorted(i for i, f in frac.items() if f > 0),
            "problems_always": sorted(i for i, f in frac.items() if f == 1.0), "fraction": frac}


def compare(base: dict, cand: dict, ids: list[int]) -> dict:
    diffs = {i: cand["fraction"][i] - base["fraction"][i] for i in ids}
    moved = {str(i): d for i, d in diffs.items() if d != 0}
    return {"mean_difference": cand["mean"] - base["mean"], "summed_fraction_difference": sum(diffs.values()),
            "moved": moved, "sign_test": sign_test(diffs), "permutation_test": permutation_test(diffs)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--panel", type=Path, required=True)
    ap.add_argument("--baseline", action="append", required=True,
                    help="TAG:GRADED_DIR, repeat per decode; a decode graded in parts (the 95 and the wider 145 of the "
                         "240-problem panel) is TAG:DIR+TAG2:DIR2, the parts' sets joined")
    ap.add_argument("--candidate", action="append", required=True, help="as --baseline")
    ap.add_argument("--names", default="baseline,candidate")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    from v7_local_pair import arm                                   # noqa: E402  (graded arms, same sets as every pairing)
    ids = [int(x) for x in a.panel.read_text().split()]
    base_name, cand_name = a.names.split(",")
    readings = {}
    for name, specs in ((base_name, a.baseline), (cand_name, a.candidate)):
        arms = []
        for spec in specs:
            arms.append((spec.split(":", 1)[0].split("+")[0], decode_sets(spec, ids, arm)))
        readings[name] = {level: model_reading(name, [(t, s[level]) for t, s in arms], ids) for level in LEVELS}
    result = {"panel": str(a.panel), "problems": len(ids), "protocol": "three decodes per candidate, paired per problem",
              "decodes": {base_name: len(a.baseline), cand_name: len(a.candidate)},
              "unequal_decodes": len(a.baseline) != len(a.candidate),
              "readings": {NAMES[level]: {n: readings[n][level] for n in (base_name, cand_name)} for level in LEVELS},
              "paired": {NAMES[level]: compare(readings[base_name][level], readings[cand_name][level], ids) for level in LEVELS}}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    for level in LEVELS:
        b, c, p = readings[base_name][level], readings[cand_name][level], result["paired"][NAMES[level]]
        print(f"{NAMES[level]}: {base_name} {[d['count'] for d in b['decodes']]} mean {b['mean']:.2f} | "
              f"{cand_name} {[d['count'] for d in c['decodes']]} mean {c['mean']:.2f} | "
              f"paired mean diff {p['mean_difference']:+.2f}, up {p['sign_test']['up']} down {p['sign_test']['down']}, "
              f"sign p {p['sign_test']['p']:.3f}, permutation p {p['permutation_test']['p']:.3f}")
    if result["unequal_decodes"]:
        print("note: unequal decode counts; the reading is provisional until both have three")
    return 0


if __name__ == "__main__":
    sys.exit(main())
