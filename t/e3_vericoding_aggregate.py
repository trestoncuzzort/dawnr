#!/usr/bin/env python3
"""Aggregate the Vericoding pass@1/pass@k eval, reliably. Programs are keyed vp<problem>_s<sample> (a
deterministic id the generator controls, so the model's own per-sample renaming cannot corrupt grouping).
For each arm, average over its seeds; the denominator is the FIXED number of problems attempted (a problem
with no well-formed/verified sample scores 0, it is not dropped). "pass" = the generated real body VERIFIED
by >=1 present kernel (Vericoding is spec-based). Unbiased pass@k = 1 - C(n-c,k)/C(n,k) per problem
(Chen et al 2021, arXiv:2107.03374), averaged.

    python3 e3_vericoding_aggregate.py <n_samples> <k> <n_problems> <out.json> <arm:dir1,dir2,...> ...
"""
import json
import math
import pathlib
import re
import statistics
import sys


def passk(n, c, k):
    if c <= 0:
        return 0.0
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def one_seed(gdir, n_problems, n_samples, k):
    v = json.loads((pathlib.Path(gdir) / "verdicts.json").read_text())
    present = v.get("kernels_present", [])
    prob = {}   # problem idx -> {sample: (passed, twin_refuted)}
    for key, t in (v.get("tasks") or {}).items():
        # grade.py prefixes the extracted program name as g_<name>_<hash>__<name>; search (not match) for
        # the controlled vp<problem>_s<sample> id anywhere in the key.
        m = re.search(r"vp(\d+)_s(\d+)", key)
        if not m:
            continue
        pi, s = int(m.group(1)), int(m.group(2))
        cols = t.get("columns") or {}
        passed = any((cols.get(kk) or {}).get("real") == "verified" for kk in present)
        twinref = any((cols.get(kk) or {}).get("twin") == "refuted" for kk in present)
        prob.setdefault(pi, {})[s] = (passed, twinref)
    greedy = sum(1 for pi in range(n_problems) if prob.get(pi, {}).get(0, (False, False))[0])
    p1 = statistics.mean([passk(n_samples, sum(1 for v2 in prob.get(pi, {}).values() if v2[0]), 1) for pi in range(n_problems)])
    pk = statistics.mean([passk(n_samples, sum(1 for v2 in prob.get(pi, {}).values() if v2[0]), k) for pi in range(n_problems)])
    verified = sum(1 for pi in prob for v2 in prob[pi].values() if v2[0])
    twin_surv = sum(1 for pi in prob for v2 in prob[pi].values() if v2[0] and not v2[1])  # verified but twin NOT refuted
    return {"greedy_pass_at_1": greedy, "pass_at_1": round(p1, 3), f"pass_at_{k}": round(pk, 3),
            "verified_samples": verified, "twin_survivors": twin_surv}


def main():
    n = int(sys.argv[1]); k = int(sys.argv[2]); npr = int(sys.argv[3]); outp = pathlib.Path(sys.argv[4])
    arms = {}
    for spec in sys.argv[5:]:
        arm, dirs = spec.split(":", 1)
        seeds = [one_seed(d, npr, n, k) for d in dirs.split(",") if (pathlib.Path(d) / "verdicts.json").is_file()]
        if not seeds:
            arms[arm] = {"seeds": 0}; continue
        mean = lambda key: round(statistics.mean([s[key] for s in seeds]), 3)
        arms[arm] = {"seeds": len(seeds), "n_problems": npr, "n_samples": n,
                     "greedy_pass_at_1_mean": mean("greedy_pass_at_1"),
                     "pass_at_1_mean": mean("pass_at_1"), f"pass_at_{k}_mean": mean(f"pass_at_{k}"),
                     "verified_samples_mean": mean("verified_samples"), "twin_survivors_mean": mean("twin_survivors"),
                     "per_seed": seeds}
    rep = {"eval": f"Vericoding, {npr} problems x {n} samples, pass=real verified by >=1 present kernel, "
                   f"unbiased pass@k, averaged over seeds; problem denominator fixed (0 if no verified sample)",
           "arms": arms}
    outp.write_text(json.dumps(rep, indent=2))
    print(f"wrote {outp}")
    print(f"{'arm':8} {'seeds':5} {'greedy@1':9} {'pass@1':7} {'pass@'+str(k):7} {'verif/seed':10} {'twin_surv':9}")
    for arm, d in arms.items():
        if d.get("seeds"):
            print(f"{arm:8} {d['seeds']:5} {d['greedy_pass_at_1_mean']:<9} {d['pass_at_1_mean']:<7} "
                  f"{d[f'pass_at_{k}_mean']:<7} {d['verified_samples_mean']:<10} {d['twin_survivors_mean']:<9}")


if __name__ == "__main__":
    main()
