#!/usr/bin/env python3
"""E2 explicit alternate-solver run: re-verify under cvc5 the SPARK cells that SPARK VERIFIED under Z3 in
the fully-adjudicated direct-body matrix, and measure whether cvc5 agrees. SPARK is the only Z3-default
kernel whose adapter cleanly swaps solver (gnatprove --prover=cvc5, bundled); verus/fstar are Z3-locked and
Dafny-under-cvc5 core-dumps (honest refusals, recorded). Body-only adjudication, exactly as E1's direct-body
matrix, under T_SPARK_PROVER=cvc5. This restores the withdrawn independence claim with a real cvc5 number.
"""
import sys
sys.path.insert(0, ".")
import json
import os
import pathlib
import tempfile
import time
import collections

os.environ["T_SPARK_JOBS"] = "1"
import audit  # noqa: E402
import tasks_io  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402

KERN = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
OUT = pathlib.Path("out")


def norm(v):
    return ("verified" if v == "verified" else "refuted" if v == "refuted"
            else "unverifiable:" + (v.split(":", 1)[0] if ":" in v else v)), v


def _cell_cvc5(arg):
    path, which, body_json = arg
    os.environ["T_SPARK_PROVER"] = "cvc5"
    os.environ["T_SPARK_JOBS"] = "1"
    rec = {"path": path, "which": which}
    try:
        task = tasks_io.load_task(path)
        body = task["body"] if which == "REAL" else json.loads(body_json)
        _lmod, suffix = audit.tlib._LOWER_MOD["spark"]
        work = pathlib.Path(tempfile.mkdtemp(prefix="e2-cvc5-"))
        v = audit._kernel_verdict(task, body, "spark", work / f"c.{suffix}")
        rec["cvc5_state"], _ = norm(v)
    except Exception as e:  # noqa: BLE001
        rec["cvc5_state"] = "unverifiable:worker-error"
        rec["err"] = f"{type(e).__name__}:{e}"[:120]
    return rec


def main():
    grp = collections.defaultdict(dict)
    for tag in ("vcd", "df", "hev", "auto"):
        man = json.loads((OUT / f"E1MAN-{tag}.json").read_bytes())
        for ln in (OUT / f"E1FULL-{tag}.jsonl").read_text().splitlines():
            if not ln.strip():
                continue
            r = json.loads(ln)
            grp[(r["path"], r["which"])][r["kernel"]] = r["state"]
        # stash survivor bodies per (path, which)
        for p, t in man["tasks"].items():
            if t.get("status") == "ok":
                for s in t.get("survivors") or []:
                    grp[(p, s["id"])]["_body"] = json.dumps(s["body"])
    # target: every SPARK-verified-under-z3 survivor + every all-seven-accept real (coverage robustness)
    targets = []
    for (p, which), g in grp.items():
        if g.get("spark") != "verified":
            continue
        allseven = all(g.get(kn) == "verified" for kn in KERN)
        if which != "REAL":
            targets.append((p, which, g.get("_body")))
        elif allseven:
            targets.append((p, which, None))
    t0 = time.time()
    results = []
    with ProcessPoolExecutor(max_workers=6) as ex:
        for i, rec in enumerate(ex.map(_cell_cvc5, targets), 1):
            k = (rec["path"], rec["which"])
            rec["z3_state"] = "verified"
            rec["allseven_z3"] = all(grp[k].get(kn) == "verified" for kn in KERN)
            rec["which_kind"] = "REAL" if rec["which"] == "REAL" else "survivor"
            results.append(rec)
            if i % 50 == 0:
                print(f"  .. {i}/{len(targets)} ({time.time()-t0:.0f}s)", flush=True)
    surv = [r for r in results if r["which_kind"] == "survivor"]
    real = [r for r in results if r["which_kind"] == "REAL"]
    a7 = [r for r in results if r["allseven_z3"] and r["which_kind"] == "survivor"]
    agree = lambda rs: sum(1 for r in rs if r["cvc5_state"] == "verified")
    rep = {
        "measured": "SPARK re-verified under cvc5 (bundled, --prover=cvc5), body-only, vs its Z3 verdict",
        "n_targets": len(targets), "wall_s": round(time.time() - t0, 1),
        "survivors_z3_verified": len(surv), "survivors_cvc5_also_verified": agree(surv),
        "reals_allseven_z3_verified": len(real), "reals_cvc5_also_verified": agree(real),
        "allseven_survivors": len(a7), "allseven_survivors_cvc5_also_verified": agree(a7),
        "cvc5_state_dist_survivors": dict(collections.Counter(r["cvc5_state"] for r in surv)),
        "z3_locked_kernels": ["verus", "fstar", "dafny (Dafny hands cvc5 Z3-style flags; core-dumps)"],
        "results": results,
    }
    (OUT / "E2-CVC5.json").write_text(json.dumps(rep, indent=1))
    print(f"E2-CVC5 done: survivors {rep['survivors_cvc5_also_verified']}/{rep['survivors_z3_verified']} agree, "
          f"all-seven {rep['allseven_survivors_cvc5_also_verified']}/{rep['allseven_survivors']}, "
          f"reals {rep['reals_cvc5_also_verified']}/{rep['reals_allseven_z3_verified']} -> out/E2-CVC5.json")


if __name__ == "__main__":
    main()
