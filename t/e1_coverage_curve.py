#!/usr/bin/env python3
"""E1 DIRECT-BODY coverage curve over the corpora mutant matrix (the broader-benchmark evidence, SEPARATE
from the curated 426-pair paired-gate measurement in e1_pairs_aggregate.py). Built from the same frozen
manifest + fully-adjudicated matrix the aggregator uses (imported load(), identical keyset + fail-closed
exclusions). No acceptance/rejection is inferred from a missing cell.

LABELLING (important, per review):
  * This is the DIRECT-BODY path (audit._kernel_verdict): each body is lowered and the kernel asked to VERIFY
    it. A wrong body a kernel cannot verify reads UNPROVED, NOT refuted -- this path does not run the paired
    grounded-witness refutation, so it is NOT the operational paired gate and carries no same-kernel
    conjunction. k here is an experimental cross-kernel AGREEMENT (vote) count, NOT T_MIN_KERNELS (an
    availability floor), NOT a paired-gate threshold.
  * A "survivor" is a behaviour-changing mutant the bounded-domain interpreter could not separate from the
    real. Whether a survivor a kernel VERIFIES is an intended error or a specification-PERMITTED alternative
    is NOT adjudicated here -- there is no intended-wrong ground-truth label for this population. So we report
    the observed SURVIVOR-VERIFICATION RATE and explicitly mark intended-correctness UNKNOWN. We do NOT call
    it "wrong", "false-accept" or "accuracy".

    python3 -I e1_coverage_curve.py <tag> [<tag> ...]
"""
import json
import os
import sys
import collections
import pathlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I/-P drops the script dir; sibling import needs it
import e1_full_aggregate as agg

KERNELS = agg.KERNELS
OUT = pathlib.Path("out")
VERIFIED, REFUTED = "verified", "refuted"


def votes(d):
    v = sum(1 for k in KERNELS if d.get(k) == VERIFIED)
    r = sum(1 for k in KERNELS if d.get(k) == REFUTED)
    decided = sum(1 for k in KERNELS if d.get(k) in (VERIFIED, REFUTED))
    return {"verify": v, "refute": r, "decided": decided}


def main():
    tags = sys.argv[1:]
    if not tags:
        print("usage: e1_coverage_curve.py <tag> [<tag> ...]"); return 2
    expected, observed, meta, totals, dup, unknown, excl = agg.load(tags)

    surv = collections.defaultdict(dict)
    real = collections.defaultdict(dict)
    for (path, which, k), sid in expected.items():
        st = (observed.get((path, which, k)) or {}).get("state", "not-run")
        (real[path] if which == "REAL" else surv[which])[k] = st

    S = {sid: votes(surv[sid]) for sid in surv}
    R = {p: votes(real[p]) for p in real}
    nS, nR = len(S), len(R)

    curve = []
    for k in range(1, 8):
        real_cov = sum(1 for p in R if R[p]["verify"] >= k)
        surv_ver = sum(1 for sid in S if S[sid]["verify"] >= k)
        surv_decided = sum(1 for sid in S if S[sid]["decided"] >= k)
        curve.append({"k": k,
                      "real_verified_ge_k": real_cov, "real_coverage_pct": round(100 * real_cov / max(nR, 1), 1),
                      # intended-correctness UNKNOWN: this is a verification RATE, not an error/accuracy rate
                      "survivor_verified_ge_k": surv_ver,
                      "survivor_verified_rate_pct": round(100 * surv_ver / max(nS, 1), 1),
                      "survivor_decided_ge_k": surv_decided})

    def tally(group):
        c = collections.Counter()
        for g in group.values():
            for k in KERNELS:
                c[g.get(k, "not-run")] += 1     # states already carry their reason (verified/refuted/unverifiable:*)
        return dict(c)

    report = {
        "path": "DIRECT-BODY audit._kernel_verdict (NOT the paired grounded-witness gate; survivors read "
                "UNPROVED not REFUTED here)",
        "k_meaning": "experimental cross-kernel agreement (vote) count; NOT T_MIN_KERNELS; NOT a paired threshold",
        "intended_correctness": "UNKNOWN for survivors -- survivor-verification RATE reported, never 'wrong'/'accuracy'",
        "tags": tags, "n_survivors": nS, "n_real": nR,
        "cell_completeness": {"expected": len(expected), "observed": len(observed)},
        "row_hygiene": {"unknown": unknown, "identical_dup": dup, **excl},
        "real_cell_states": tally(real), "survivor_cell_states": tally(surv),
        "curve": curve}
    outp = OUT / f"E1-DIRECTBODY-CURVE-{'-'.join(tags)}.json"
    outp.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("## E1 DIRECT-BODY coverage curve (corpora mutant matrix) -- broader-benchmark evidence\n")
    print("DIRECT-BODY path (audit._kernel_verdict): a survivor a kernel cannot verify reads UNPROVED, not "
          "refuted. NOT the paired grounded-witness gate; k = cross-kernel agreement vote, NOT T_MIN_KERNELS.\n")
    print(f"Survivors (kernel-adjudicated): {nS}; real bodies: {nR}. "
          f"Cells {len(observed)}/{len(expected)} observed (missing = not-run, never a rejection).\n")
    print("Intended-correctness of survivors is UNKNOWN (spec-gap vs spec-permitted not adjudicated); the "
          "survivor column is a VERIFICATION RATE, not an error/accuracy rate.\n")
    print("| k | real verified≥k (coverage) | survivor verified≥k (rate, UNKNOWN intent) | survivor decided≥k |")
    print("|--:|--:|--:|--:|")
    for c in curve:
        print(f"| {c['k']} | {c['real_verified_ge_k']} ({c['real_coverage_pct']}%) | "
              f"{c['survivor_verified_ge_k']} ({c['survivor_verified_rate_pct']}%) | {c['survivor_decided_ge_k']} |")
    print(f"\nreal cell states: {report['real_cell_states']}")
    print(f"survivor cell states: {report['survivor_cell_states']}")
    print(f"wrote {outp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
