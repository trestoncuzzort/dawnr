#!/usr/bin/env python3
"""The specification stage's ceiling (t/PREDICT-2026-10-21-spec-ceiling.md): every scored candidate of a
stage-1 run judged by the route's SAFE gate (the scores in scored-specs.jsonl) and by the reference check
(spec_check.check_task against the problem's solution, the training-side keep rule spec_first.reference_keeps).

    python3 t/recipes/spec_ceiling.py --tag v5-20261021-spec20 --ids-file t/out/v6-20261018/dev-95.txt \\
        --n 200 --jobs 16 --out OUT.json

Sources: t/spec_first.py (reference_keeps, kept_specifications), t/spec_check.py (check_task, after EvalPlus's
seeded input mutation), SAFE arXiv:2410.15756 section 3.2 (the two scores).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_first                                               # noqa: E402
import spec_quality                                             # noqa: E402
import surface                                                  # noqa: E402

POOL = None
N = 200


def _init(pool_version: str, n: int) -> None:
    global POOL, N
    POOL = {str(k): v for k, v in se.pool(pool_version).items()}
    N = n


def judge(item: tuple[str, str, str]) -> dict:
    """(task_id, source, nameless spec text) -> the reference verdict of that candidate."""
    tid, source, text = item
    entry = POOL[tid]
    try:
        task = se.rename_task(surface.parse(text), entry["fn"])
    except Exception as e:                                      # noqa: BLE001
        return {"task_id": tid, "source": source, "status": f"unparsable: {type(e).__name__}", "reference": False}
    seed = int(hashlib.sha256(f"{tid}/{source}".encode()).hexdigest()[:8], 16)
    try:
        r = spec_check.check_task(task, entry, N, random.Random(seed))
    except Exception as e:                                      # noqa: BLE001
        r = {"status": f"check raised: {type(e).__name__}"}
    return {"task_id": tid, "source": source, "status": r.get("status"), "draws": r.get("draws"),
            "completeness": r.get("completeness"), "cross_completeness": r.get("cross_completeness"),
            "reference": spec_first.reference_keeps(r)}


def _sample_index(source: str) -> int:
    try:
        return int(source.rsplit("/", 1)[1])
    except (ValueError, IndexError):
        return 10 ** 6


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--ids-file", type=Path, required=True)
    ap.add_argument("--pool", default="v5")
    ap.add_argument("--n", type=int, default=200, help="reference draws per candidate")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--per-problem", type=int, default=3, help="the route's kept cap, for the selection gap")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    d = se.outdir(a.tag)
    ids = [x for x in a.ids_file.read_text().split() if x.strip()]
    sf = json.loads((d / "spec_first.json").read_text())
    per = sf["per_problem"]
    python = {str(json.loads(l)["task_id"]): json.loads(l) for l in (d / "python.jsonl").read_text().splitlines() if l.strip()}
    scored = [json.loads(l) for l in (d / "scored-specs.jsonl").read_text().splitlines() if l.strip()]
    by = defaultdict(list)
    for r in scored:
        by[str(r["task_id"])].append(r)
    items = [(t, r["source"], r["spec"]) for t, rs in by.items() for r in rs]
    with Pool(a.jobs, initializer=_init, initargs=(a.pool, a.n)) as pool:
        verdicts = pool.map(judge, items, chunksize=4)
    ref = {(v["task_id"], v["source"]): v for v in verdicts}
    # Python pass@k: attempts stop at the first pass, so pass@k = problems whose passing attempt index < k
    attempts = {t: per[t].get("python") for t in ids}
    max_k = max([a_ for a_ in attempts.values() if a_ is not None] + [0]) + 1
    python_pass = {k: sum(1 for t in ids if attempts[t] is not None and attempts[t] < k) for k in range(1, max(max_k, 10) + 1)}
    with_python = [t for t in ids if attempts[t] is not None]
    # specification pass@k by sample index, SAFE and reference
    spec_k = max([_sample_index(r["source"]) for r in scored if _sample_index(r["source"]) < 10 ** 6] + [0]) + 1
    safe_pass, ref_pass = {}, {}
    first_ref, first_safe = {}, {}
    for t in with_python:
        rs = sorted(by.get(t, []), key=lambda r: _sample_index(r["source"]))
        fs = next((_sample_index(r["source"]) for r in rs if r["verdict"] in ("kept", "duplicate")), None)
        fr = next((_sample_index(r["source"]) for r in rs if ref[(t, r["source"])]["reference"]), None)
        first_safe[t], first_ref[t] = fs, fr
    for k in range(1, spec_k + 1):
        safe_pass[k] = sum(1 for t in with_python if first_safe[t] is not None and first_safe[t] < k)
        ref_pass[k] = sum(1 for t in with_python if first_ref[t] is not None and first_ref[t] < k)
    # the gate's precision and the selection gap
    kept = [r for r in scored if r["verdict"] == "kept"]
    kept_ref = sum(1 for r in kept if ref[(str(r["task_id"]), r["source"])]["reference"])
    gap, details = [], {}
    for t in with_python:
        rs = by.get(t, [])
        any_ref = [r["source"] for r in rs if ref[(t, r["source"])]["reference"]]
        kept_t = [r for r in rs if r["verdict"] == "kept"]
        kept_t.sort(key=lambda r: (-r["scores"]["completeness"], -r["scores"]["correctness"]))
        top = kept_t[:a.per_problem]
        top_ref = [r["source"] for r in top if ref[(t, r["source"])]["reference"]]
        details[t] = {"candidates": len(rs), "safe_kept": len(kept_t), "reference_correct": any_ref,
                      "top_kept_reference_correct": top_ref, "first_reference_sample": first_ref[t],
                      "first_safe_sample": first_safe[t]}
        if any_ref and not top_ref:
            gap.append(t)
    out = {"tag": a.tag, "draws": a.n, "problems": len(ids), "with_python": len(with_python),
           "python_pass_at_k": python_pass, "candidates_scored": len(scored),
           "spec_pass_at_k": {"safe_gate": safe_pass, "reference": ref_pass},
           "safe_kept": len(kept), "safe_kept_reference_correct": kept_ref,
           "safe_precision": (kept_ref / len(kept)) if kept else None,
           "problems_with_a_reference_correct_candidate": sum(1 for t in with_python if first_ref[t] is not None),
           "selection_gap": gap, "per_problem": details,
           "reference_statuses": dict(sorted(((s, sum(1 for v in verdicts if v["status"] == s)) for s in {v["status"] for v in verdicts}), key=lambda x: -x[1]))}
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("with_python", "python_pass_at_k", "safe_kept", "safe_kept_reference_correct",
                                            "safe_precision", "problems_with_a_reference_correct_candidate", "selection_gap")}))
    print("spec pass@k reference:", ref_pass)
    print("spec pass@k SAFE gate:", safe_pass)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
