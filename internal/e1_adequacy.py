#!/usr/bin/env python3
"""E1 — twin-gate adequacy, measured across all seven kernels.

For a corpus of t task files: classify every one-edit mutant by the interpreter over the task's
bounded domain (kernel-independent; audit.classify), then verify the real body and each survivor
in ALL SEVEN kernels. A *survivor* is a wrong program the spec accepts at every domain point — a
postcondition gap with a concrete witness. A survivor the gate ACCEPTS at threshold k (>= k kernels
verify it) is a false-accept. The gate is T_MIN_KERNELS = k on t/prove.py.

Outputs, per corpus:
  - spec-level mutant survival (complete: over every behaviour-changing mutant)
  - per-kernel false-accept (survivors that kernel proves / survivors it saw)
  - the coverage-vs-accuracy curve over k = 1..7:
        coverage(k)  = correct real bodies verified by >= k kernels   (yield; drops as k rises)
        false_acc(k) = survivors proved by >= k kernels                (wrong programs slipping through)

Self-contained: sets the lab's seven-kernel PATH + T_LEAN_BIN so no wrapper is needed.
Run with `python3 -I e1_adequacy.py <corpus_dir> <tag> [jobs]`.
"""
import json
import os
import pathlib
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
HOME = os.path.expanduser("~")
KDIRS = [f"{HOME}/.cargo/bin", f"{HOME}/.opam/default/bin", f"{HOME}/.elan/bin",
         f"{HOME}/.local/lean/bin", f"{HOME}/.local/fstar/fstar/bin",
         f"{HOME}/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin",
         f"{HOME}/.local/verus/verus-x86-linux", f"{HOME}/.local/dafny"]
os.environ["PATH"] = ":".join(KDIRS) + ":" + os.environ.get("PATH", "")
os.environ.setdefault("T_LEAN_BIN", f"{HOME}/.local/lean/bin/lean")
sys.path.insert(0, HERE)

import audit  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402

KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]


def _one(arg):
    path, kernel = arg
    try:
        r = audit.audit_file(path, kernel=kernel, seconds=audit.TASK_SECONDS, out_dir=None)
    except Exception as e:  # noqa: BLE001
        return kernel, {"name": pathlib.Path(path).stem, "status": f"error:{type(e).__name__}:{e}"}
    return kernel, r


def main() -> int:
    corpus = pathlib.Path(sys.argv[1])
    tag = sys.argv[2] if len(sys.argv) > 2 else corpus.name
    jobs = int(sys.argv[3]) if len(sys.argv) > 3 else 48
    files = [str(p) for p in sorted(corpus.iterdir()) if p.suffix in (".t", ".json")]
    work = [(f, k) for f in files for k in KERNELS]
    print(f"E1 {tag}: {len(files)} tasks x {len(KERNELS)} kernels = {len(work)} audits, jobs={jobs}", flush=True)

    results = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for i, out in enumerate(ex.map(_one, work), 1):
            results.append(out)
            if i % 50 == 0:
                print(f"  .. {i}/{len(work)}", flush=True)

    # merge per task
    tasks: dict = {}
    spec = {"behaviour_changing": 0, "killed": 0, "survivors_total": 0, "tasks": 0,
            "tasks_audited": 0, "tasks_with_survivor": 0}
    seen_spec = set()
    for kernel, r in results:
        if r.get("status") != "ok":
            continue
        name = r["name"]
        t = tasks.setdefault(name, {"real": set(), "surv": {}, "decided": set()})
        if r.get("real_verdict") == "verified":
            t["real"].add(kernel)
        if r.get("real_verdict") in ("verified", "refuted"):
            t["decided"].add(kernel)
        for s in r.get("survivors", []):
            key = (s.get("op"), s.get("change"))
            rec = t["surv"].setdefault(key, {"proved": set(), "saw": set(), "witness": s.get("witness")})
            if s.get("verdict") is not None:
                rec["saw"].add(kernel)
                if s.get("verdict") == "verified":
                    rec["proved"].add(kernel)
        # spec-level counts are kernel-independent; take them once per task
        if name not in seen_spec:
            seen_spec.add(name)
            spec["tasks"] += 1
            spec["tasks_audited"] += 1
            chg = r.get("killed", 0) + len(r.get("survivors", []))
            spec["behaviour_changing"] += chg
            spec["killed"] += r.get("killed", 0)
            spec["survivors_total"] += len(r.get("survivors", []))
            if r.get("survivors"):
                spec["tasks_with_survivor"] += 1

    reals = list(tasks.values())
    # survivors that at least one kernel actually adjudicated (first CONFIRM/task) -> the kernel-curve sample
    kerned_surv = [rec for t in tasks.values() for rec in t["surv"].values() if rec["saw"]]
    nr = max(1, len(reals))
    ns = len(kerned_surv)

    curve = []
    for k in range(1, 8):
        cov = sum(1 for t in reals if len(t["real"]) >= k) / nr
        fa_n = sum(1 for rec in kerned_surv if len(rec["proved"]) >= k)
        fa = fa_n / ns if ns else 0.0
        curve.append({"k": k, "coverage": round(cov, 4),
                      "false_accept": round(fa, 4), "false_accept_n": fa_n, "surv_n": ns})

    per_kernel = {}
    for kn in KERNELS:
        proved = sum(1 for rec in kerned_surv if kn in rec["proved"])
        saw = sum(1 for rec in kerned_surv if kn in rec["saw"])
        verified_real = sum(1 for t in reals if kn in t["real"])
        decided_real = sum(1 for t in reals if kn in t["decided"])
        per_kernel[kn] = {"survivors_proved": proved, "survivors_seen": saw,
                          "real_verified": verified_real, "real_decided": decided_real}

    survival_rate = (spec["survivors_total"] / spec["behaviour_changing"]) if spec["behaviour_changing"] else 0.0
    out = {"tag": tag, "corpus": str(corpus), "n_tasks": len(files),
           "spec_level": {**spec, "mutant_survival_rate": round(survival_rate, 4),
                          "kill_rate": round(1 - survival_rate, 4)},
           "kernel_adjudicated_survivors": ns,
           "per_kernel": per_kernel, "curve": curve}
    outpath = pathlib.Path("out") / f"E1-{tag}.json"
    outpath.parent.mkdir(exist_ok=True)
    outpath.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"\nE1 {tag}: {spec['tasks_audited']} tasks audited")
    print(f"  spec kills {spec['killed']}/{spec['behaviour_changing']} behaviour-changing mutants "
          f"({100*(1-survival_rate):.1f}%); {spec['survivors_total']} survivors across "
          f"{spec['tasks_with_survivor']} tasks")
    print(f"  kernel-adjudicated survivors: {ns}")
    print(f"  {'k':>2}  {'coverage':>9}  {'false-accept':>12}")
    for c in curve:
        print(f"  {c['k']:>2}  {c['coverage']*100:>8.1f}%  {c['false_accept']*100:>10.1f}%  ({c['false_accept_n']}/{c['surv_n']})")
    print(f"  wrote {outpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
