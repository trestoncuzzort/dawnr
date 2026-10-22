#!/usr/bin/env python3
"""v9 rows, step 1: re-check the self-distilled specifications against the reference at a strict floor.

The v8 rows kept every candidate that agreed with the problem's solution and rejected at least 60% of mutated
outputs at 100 draws (spec_first.reference_keeps). v8 then fitted the tests: on the ceiling instrument the
three-test gate's precision fell from 0.785 to 0.515 (t/PREDICT-2026-10-21-v8-spec-rows.md). The literature names
this specification hacking and the remedy that worked was removing the weak specifications from the task set
(arXiv:2605.30914: verified pass rate 9.7% to 31.1% after filtering underspecified tasks); curated rows moved 4B
models where more rows did not (arXiv:2603.15510). This re-runs t/spec_check.check_task on every kept candidate at
1000 draws and keeps only those that agree, with at least MIN_DRAWS agreeing draws, and reject at least `floor` of
BOTH mutant families (spec_check.complete with the strict floor; a candidate with no judged mutant is dropped).
The output has the kept file's shape, so t/recipes/v8_spec_rows.py builds the rows from it unchanged.

    python3 t/recipes/v9_strict_specs.py --kept KEPT.jsonl [--kept ...] --pool v5 --draws 1000 --floor 0.9 \\
        --jobs 12 --out out/v9/strict-kept.jsonl --report out/v9/strict.json

Sources: t/spec_first.py (reference_keeps, the loop it mirrors); t/spec_check.py (check_task, complete);
SAFE arXiv:2410.15756 section 3.2 (the 60% floor this tightens); arXiv:2605.30914; arXiv:2603.15510.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
import multiprocessing
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402

MIN_DRAWS = 10
_POOL: dict[int, dict] = {}


def strict_keeps(r: dict, floor: float) -> bool:
    """Agrees on at least MIN_DRAWS draws and rejects at least `floor` of every judged mutant family."""
    if r.get("status") != "agrees" or (r.get("draws", 0) or 0) < MIN_DRAWS:
        return False
    return spec_check.complete(r, floor) is True


def _check(job: tuple) -> tuple:
    tid, index, task, draws, seed = job
    rnd = random.Random(seed)
    try:
        r = spec_check.check_task(task, _POOL[tid], draws, rnd)
    except Exception as e:                                      # noqa: BLE001
        r = {"status": f"check raised: {type(e).__name__}"}
    return tid, index, {k: r.get(k) for k in ("status", "draws", "completeness", "cross_completeness",
                                               "mutants_rejected", "mutants_accepted", "cross_rejected",
                                               "cross_accepted", "skipped")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kept", type=Path, action="append", required=True)
    ap.add_argument("--pool", choices=se.POOL_VERSIONS, default="v5")
    ap.add_argument("--draws", type=int, default=1000)
    ap.add_argument("--floor", type=float, default=0.9)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    a = ap.parse_args(argv)
    global _POOL
    _POOL = se.pool(a.pool)
    rows = []
    for path in a.kept:
        rows += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    jobs = []
    for n, row in enumerate(rows):
        tid = int(row["task_id"])
        if tid not in _POOL:
            continue
        for i, task in enumerate(row["tasks"]):
            jobs.append((tid, (n, i), task, a.draws, 1000 * n + i))
    results: dict[tuple, dict] = {}
    # fork, not forkserver (Python 3.14's Linux default): the children must inherit the loaded pool,
    # whose entries hold the problems' compiled functions and cannot be pickled across a spawn
    with multiprocessing.get_context("fork").Pool(a.jobs) as p:
        for tid, index, r in p.imap_unordered(_check, jobs, chunksize=4):
            results[index] = r
    kept_rows, dist, status = [], Counter(), Counter()
    before = after = 0
    for n, row in enumerate(rows):
        keep = []
        for i, task in enumerate(row["tasks"]):
            r = results.get((n, i), {"status": "not in the pool"})
            before += 1
            status[r["status"]] += 1
            c = r.get("completeness")
            dist[round(c, 1) if isinstance(c, (int, float)) else "none"] += 1
            if strict_keeps(r, a.floor):
                after += 1
                keep.append((task, row["sources"][i] if i < len(row.get("sources", [])) else None,
                             row["scores"][i] if i < len(row.get("scores", [])) else None, r))
        if keep:
            kept_rows.append({"task_id": row["task_id"], "tasks": [k[0] for k in keep],
                              "sources": [k[1] for k in keep], "scores": [k[2] for k in keep],
                              "reference": [k[3] for k in keep]})
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r) + "\n" for r in kept_rows), encoding="utf-8")
    report = {"inputs": [str(p) for p in a.kept], "pool": a.pool, "draws": a.draws, "floor": a.floor,
              "problems_in": len(rows), "candidates_in": before, "candidates_kept": after,
              "problems_kept": len(kept_rows), "status": dict(status),
              "completeness_distribution": {str(k): v for k, v in sorted(dist.items(), key=str)},
              "output": str(a.out)}
    a.report.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("candidates_in", "candidates_kept", "problems_in", "problems_kept")}))
    print("completeness at 1000 draws:", report["completeness_distribution"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
