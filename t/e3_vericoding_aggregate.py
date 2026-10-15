#!/usr/bin/env python3
"""Aggregate the Vericoding pass@1/pass@k eval. Reads each arm's grade verdicts (programs keyed
<progbase>__s<sample>), groups by base problem, and reports per arm: greedy pass@1 (sample 0 verified),
unbiased pass@1 and pass@k (Chen et al 2021, arXiv:2107.03374: 1 - C(n-c,k)/C(n,k) averaged over problems),
and twin-refutation rate over well-formed solutions. "pass" = the generated program's real body VERIFIED by
>=1 present kernel (Vericoding is spec-based, no tests).

    python3 e3_vericoding_aggregate.py <n_samples> <k> <out.json> <arm:gradedir> ...
"""
import json
import math
import pathlib
import re
import sys


def unbiased_passk(n, c, k):
    if c >= n:
        return 1.0
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def load_arm(gdir, n_samples):
    v = json.loads((pathlib.Path(gdir) / "verdicts.json").read_text())
    present = v.get("kernels_present", [])
    tasks = v.get("tasks", {})
    by_base = {}   # base -> {sample: {passed, twin_refuted}}
    for key, t in tasks.items():
        m = re.search(r"__s(\d+)$", key)
        if not m:
            continue
        base, s = key[:m.start()], int(m.group(1))
        cols = t.get("columns") or {}
        passed = any(cols.get(kk, {}).get("real") == "verified" for kk in present)
        twinref = any(cols.get(kk, {}).get("twin") == "refuted" for kk in present)
        by_base.setdefault(base, {})[s] = {"passed": passed, "twin_refuted": twinref}
    return by_base, present


def main():
    n = int(sys.argv[1]); k = int(sys.argv[2]); outp = pathlib.Path(sys.argv[3])
    arms = {}
    for spec in sys.argv[4:]:
        arm, gdir = spec.split(":", 1)
        by_base, present = load_arm(gdir, n)
        # the problems attempted = the gen set; a problem with NO well-formed sample has c=0
        bases = set(by_base)
        if not bases:
            arms[arm] = {"problems_wellformed": 0, "note": "no well-formed sample from any problem"}
            continue
        p1_greedy = sum(1 for b in by_base if by_base[b].get(0, {}).get("passed"))
        p1_un = sum(unbiased_passk(n, sum(1 for s in by_base[b].values() if s["passed"]), 1) for b in by_base)
        pk_un = sum(unbiased_passk(n, sum(1 for s in by_base[b].values() if s["passed"]), k) for b in by_base)
        twinref = sum(1 for b in by_base for s in by_base[b].values() if s["passed"] and s["twin_refuted"])
        npass = sum(1 for b in by_base for s in by_base[b].values() if s["passed"])
        nb = len(bases)
        arms[arm] = {"problems_with_wellformed_prog": nb, "n_samples": n,
                     "greedy_pass_at_1_count": p1_greedy,
                     "pass_at_1_unbiased_mean_over_wf": round(p1_un / nb, 3),
                     f"pass_at_{k}_unbiased_mean_over_wf": round(pk_un / nb, 3),
                     "verified_samples": npass, "twin_refuted_of_verified": twinref}
    rep = {"eval": "Vericoding spec problems; student generates k samples; pass = real body verified by >=1 "
                   "present kernel; unbiased pass@k over n samples (arXiv:2107.03374). Denominator is problems "
                   "with >=1 well-formed sample; problems where every sample is malformed have pass=0.",
           "n_samples": n, "k": k, "arms": arms}
    outp.write_text(json.dumps(rep, indent=2))
    print(f"wrote {outp}")
    for arm, d in arms.items():
        print(f"  {arm}: {json.dumps(d)}")


if __name__ == "__main__":
    main()
