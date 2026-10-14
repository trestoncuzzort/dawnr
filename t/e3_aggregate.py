#!/usr/bin/env python3
"""E3 aggregate: read the 9 graded eval runs (out/e3-grade/<arm>-s<seed>/) and report, per arm averaged
over seeds, pass@1 (generated solution's MBPP tests pass) and the gate coverage curve (a solution's real
body verified AND its twin refuted by >=k present kernels), plus twin-refutation rate. Held-out MBPP eval,
disjoint from the matched-arm train tasks. No invented comparison target: arms reported side by side.

    python3 e3_aggregate.py <grade-root> <eval-limit> <out.json>
"""
import json
import pathlib
import statistics
import sys

ARMS = ["raw", "graded", "all7"]
SEEDS = [0, 1, 2]


def cell_counts(col):
    return col.get("real") == "verified" and col.get("twin") == "refuted"


def one_run(gdir, n_eval):
    v = json.loads((gdir / "verdicts.json").read_text())
    tests = v.get("tests", {})
    tasks = v.get("tasks", {})
    present = v.get("kernels_present", [])
    pass1 = sum(1 for t in tests.values() if t.get("overall") == "pass")
    # per generated solution: how many present kernels count it (real verified + twin refuted)
    per = {name: sum(1 for k in present if cell_counts((tsk.get("columns") or {}).get(k, {})))
           for name, tsk in tasks.items()}
    gate = {k: sum(1 for c in per.values() if c >= k) for k in range(1, 8)}
    twin_ref = {name: sum(1 for k in present if ((tsk.get("columns") or {}).get(k, {})).get("twin") == "refuted")
                for name, tsk in tasks.items()}
    return {"n_eval": n_eval, "n_wellformed": len(tasks), "pass_at_1": pass1,
            "kernels_present": present, "gate_ge_k": gate,
            "twin_refuted_ge1": sum(1 for c in twin_ref.values() if c >= 1)}


def main():
    root = pathlib.Path(sys.argv[1]); n_eval = int(sys.argv[2]); outp = pathlib.Path(sys.argv[3])
    per_arm = {}
    for arm in ARMS:
        runs = []
        for s in SEEDS:
            g = root / f"{arm}-s{s}"
            if (g / "verdicts.json").is_file():
                runs.append(one_run(g, n_eval))
        if not runs:
            per_arm[arm] = {"seeds": 0}; continue
        mean = lambda xs: round(statistics.mean(xs), 2)
        per_arm[arm] = {
            "seeds": len(runs), "n_eval": n_eval,
            "pass_at_1_mean": mean([r["pass_at_1"] for r in runs]),
            "pass_at_1_pct": round(100 * statistics.mean([r["pass_at_1"] / n_eval for r in runs]), 1),
            "wellformed_mean": mean([r["n_wellformed"] for r in runs]),
            "gate_ge_k_mean": {k: mean([r["gate_ge_k"][k] for r in runs]) for k in range(1, 8)},
            "twin_refuted_ge1_mean": mean([r["twin_refuted_ge1"] for r in runs]),
            "per_seed": runs,
        }
    rep = {"eval": "held-out MBPP (disjoint from matched-arm train tasks), greedy pass@1, 3 seeds",
           "note": "lean absent in grade env -> gate over present kernels only; see kernels_present. "
                   "Small-N (30 train tasks / 25 eval); report the learning, no invented target.",
           "arms": per_arm}
    outp.write_text(json.dumps(rep, indent=2))
    print(f"wrote {outp}")
    print(f"{'arm':8} {'seeds':5} {'pass@1%':8} {'wf':5} {'gate>=1':8} {'gate>=5':8} {'twinref>=1':10}")
    for arm in ARMS:
        a = per_arm[arm]
        if a.get("seeds"):
            print(f"{arm:8} {a['seeds']:5} {a['pass_at_1_pct']:<8} {a['wellformed_mean']:<5} "
                  f"{a['gate_ge_k_mean'][1]:<8} {a['gate_ge_k_mean'][5]:<8} {a['twin_refuted_ge1_mean']:<10}")


if __name__ == "__main__":
    main()
