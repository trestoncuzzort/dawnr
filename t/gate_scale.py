#!/usr/bin/env python3
"""Gate the DeepSeek-V3.2 validation samples through the seven kernels and
report per-problem yield (B1/B2 of PREDICT-2026-10-10-teacher-deepseek-validate).
Throwaway measurement harness: it only invokes the repo's own gate tools
(spec_experiment extract/tests, run_par.py) and tabulates their JSON output.
Self-contained: sets kernel PATH + T_LEAN_BIN and cwd so no shell wrapper is needed."""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))     # .../dawnr/t
os.chdir(HERE)
HOME = os.path.expanduser("~")
KDIRS = [f"{HOME}/.cargo/bin", f"{HOME}/.opam/default/bin", f"{HOME}/.elan/bin",
         f"{HOME}/.local/lean/bin", f"{HOME}/.local/fstar/fstar/bin",
         f"{HOME}/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin",
         f"{HOME}/.local/verus/verus-x86-linux", f"{HOME}/.local/dafny"]
os.environ["PATH"] = ":".join(KDIRS) + ":" + os.environ.get("PATH", "")
os.environ["T_LEAN_BIN"] = f"{HOME}/.local/lean/bin/lean"
sys.path.insert(0, HERE)

import spec_experiment as se
PY = sys.executable
KERNELS = "dafny,verus,spark,framac,lean,rocq,fstar"
TAGS = [f"deepseek-v3.2-scale-s{k}" for k in range(4)]
print("gate start; PATH head:", os.environ["PATH"].split(":")[0], flush=True)

def sh(args):
    r = subprocess.run(args, capture_output=True, text=True)
    return (r.stdout or "") + (r.stderr or "")

def parse_kernels_md(path):
    cols, rows = [], {}
    if not os.path.exists(path):
        return cols, rows
    for line in open(path, encoding="utf-8"):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == "task":
            cols = cells[1:]; continue
        if not cols or len(cells) != len(cols) + 1 or set(cells[0]) <= {"-"}:
            continue
        rows[cells[0]] = dict(zip(cols, cells[1:]))
    return cols, rows

per = {}
for tag in TAGS:
    d = se.outdir(tag)
    sh([PY, "spec_experiment.py", "extract", "--model", tag, "--pool", "v5"])
    tout = sh([PY, "spec_experiment.py", "tests", "--model", tag, "--pool", "v5"])
    tline = tout.strip().splitlines()[-1] if tout.strip() else ""
    rout = sh([PY, "run_par.py", "--tasks", str(d + "/tasks" if isinstance(d, str) else str(d) + "/tasks"),
               "--table", str(d) + "/kernels.md",
               "--kernels", KERNELS, "--jobs", "10", "--no-cache", "--allow-subset-table"])
    ext = json.loads(open(str(d) + "/extract.json").read()) if os.path.exists(str(d) + "/extract.json") else {}
    tests = json.loads(open(str(d) + "/tests.json").read()) if os.path.exists(str(d) + "/tests.json") else {}
    cols, rows = parse_kernels_md(str(d) + "/kernels.md")
    name2tid = {e["name"]: int(t) for t, e in ext.items() if e.get("stage") == "task" and "name" in e}
    nt = sum(1 for e in ext.values() if e.get("stage") == "task")
    print(f"[{tag}] tasks={nt} tests=({tline}) kcols={cols} rows={len(rows)} runpar_tail={rout.strip().splitlines()[-1] if rout.strip() else ''}", flush=True)
    for name, row in rows.items():
        tid = name2tid.get(name)
        if tid is None:
            continue
        nk = sum(1 for c in cols if row.get(c) == "verified / refuted")
        p = per.setdefault(tid, {"tp": False, "k1": False, "k7": False, "maxk": 0})
        p["maxk"] = max(p["maxk"], nk)
        p["k1"] = p["k1"] or nk >= 1
        p["k7"] = p["k7"] or nk >= 7
    for ts, r in tests.items():
        if r.get("overall") == "pass":
            per.setdefault(int(ts), {"tp": False, "k1": False, "k7": False, "maxk": 0})["tp"] = True

tp = sum(1 for p in per.values() if p["tp"])
k1 = sum(1 for p in per.values() if p["k1"])
k7 = sum(1 for p in per.values() if p["k7"])
print("=== YIELD (per problem, best of 4 samples) ===", flush=True)
print(json.dumps({"problems_seen": len(per), "tests_pass": tp,
                  "verified_ge1_kernel": k1, "verified_all7": k7,
                  "per_problem": {str(t): v for t, v in sorted(per.items())}}, indent=1), flush=True)
