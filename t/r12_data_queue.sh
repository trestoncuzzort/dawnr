#!/bin/bash
# t/r12_data_queue.sh -- the data r12 trains on, as one ordered, resumable queue (2026-09-25).
#
#   bash t/r12_data_queue.sh status                 sentinels, tags, and what the lab looks like
#   bash t/r12_data_queue.sh gate [--grading]       the admission decision alone
#   bash t/r12_data_queue.sh p4-extract             qwen235-train-p4: extract and tests under pool v5 (light)
#   bash t/r12_data_queue.sh v6new-repair           qwen235-v6new: a fresh tag from the torn one, extracted (light)
#   bash t/r12_data_queue.sh train|p4|prover2|v6new one source: plan, grade in chunks, merge by content
#   bash t/r12_data_queue.sh spec                   specification checks, each tag under its one pool
#   bash t/r12_data_queue.sh build                  the r12 (split-v5) and r12v6 (split-v6) pool files
#   bash t/r12_data_queue.sh dev-ids                t/r12-dev-ids.json, the stopping-step dev split
#   bash t/r12_data_queue.sh verify-dev CORPUS      refuse a corpus that names a dev id under any alias
#   bash t/r12_data_queue.sh r11                    the twelve r11 baseline arms, extracted, tested and graded (heldout)
#   bash t/r12_data_queue.sh all                    everything above, in that order
#   bash t/r12_data_queue.sh _py NAME               print one embedded program (the tests read them so)
#
# The queue is a controller: it runs here, like t/grade_lab.sh, and every Python step
# runs on the lab workstation over ssh, niced, inside its ~/tup, so no compute happens
# on this machine. T_LAB comes only from t/lab-workstation.conf (gitignored). Grading
# goes only through t/grade_lab.sh, with --no-cache, because every cache entry these
# programs could hit came from tables graded under SPARK -j8 oversubscription, and
# run_par caches UNPROVED (t/DATA-r12.md).
#
# Every step is guarded three ways. Admission (`gate`): the lab must have no stopped
# process of ours, no orphaned prover of ours, no live pid in cpu-yield's frozen.pids,
# and load below 70 percent of its cores; grading also needs no generation process of
# ours and at least one cell of headroom, since `--jobs 0` means every core in run_par.
# GNU parallel's --load "does not police running work, only admits new work"
# (gnu.org/software/parallel/parallel.html, receipt 5d35b2e68b9c); this gate is the same
# thing before every step and before every grading chunk. Sentinels: a step is done only
# when t/out/r12-data/done/<step>.json on the lab records the sha256 of its inputs;
# the existence of a tool's output never counts (Luigi's atomic-write pattern,
# luigi.readthedocs.io/en/stable/luigi_patterns.html, receipt 31dfca2b8316). Locks: one
# mkdir lock on each side (mywiki.wooledge.org/BashFAQ/045, the atomic check-and-create).
#
# Exit statuses on their own line. `echo "$(date) rc=$?"` reports date's status, which is
# how the lab's old grade queue logged `GRADED qwen235-train rc=0` for a run that timeout
# killed before it wrote a table (gnu.org/software/bash/manual/html_node/Job-Control-Builtins.html).
set -u

RD=t/out/r12-data                 # both sides; the lab's copy is the one of record
SE=t/out/spec-experiment
SSH="ssh -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=30"
MAX_CELLS=${R12_MAX_CELLS:-12}
CHUNK=${R12_CHUNK:-40}
WAIT_MIN=${R12_WAIT_MINUTES:-0}   # 0: refuse and exit; N: re-check the gate every 5 minutes for N minutes
V6NEW_MODE=${R12_V6NEW_MODE:-repair}
LAB=; REPO=${T_LAB_REPO:-tup}

# ------------------------------------------------------------- embedded programs --
# Printed, never executed by eval: `_py NAME | python3 - ARGS` here or on the lab. Each
# imports spec_experiment first, which imports nl_census and lifts Python's 4300-digit
# int limit (docs.python.org/3/library/stdtypes.html#int-max-str-digits); one tests.json
# holds a 66,097-digit integer that a bare json.loads refuses.
_py() {
case "$1" in
facts) cat <<'PY'
import glob, json, os
PROVERS = ("z3", "cvc5", "alt-ergo", "gnatprove", "gnatwhy3", "why3server", "lean", "coqc", "dafny",
           "Dafny", "verus", "fstar", "fstar.exe")
GEN = ("loop_locallm.py generate", "loop_generate.py", "spec_experiment.py generate", "gen_fleet.sh")
me, self_pid = os.getuid(), os.getpid()
stopped, orphans, gen = [], [], []
for pd in glob.glob("/proc/[0-9]*"):
    pid = int(pd.rsplit("/", 1)[1])
    if pid == self_pid:
        continue
    try:
        if os.stat(pd).st_uid != me:
            continue
        stat = open(pd + "/stat").read()
        comm = stat[stat.index("(") + 1:stat.rindex(")")]
        state, ppid = stat[stat.rindex(")") + 2:].split()[:2]
        cmd = open(pd + "/cmdline", "rb").read().replace(b"\0", b" ").decode("utf-8", "replace")
    except (OSError, ValueError):
        continue
    if state == "T":
        stopped.append([pid, comm])
    if int(ppid) == 1 and any(comm == p or comm.startswith(p + "-") for p in PROVERS):
        orphans.append([pid, comm])
    if any(k in cmd for k in GEN):
        gen.append([pid, comm])
frozen_live = []
fp = os.path.expanduser("~/.local/share/cpu-yield/frozen.pids")
if os.path.exists(fp):
    for tok in open(fp).read().split():
        if tok.isdigit() and os.path.exists(f"/proc/{tok}"):
            try:
                if os.stat(f"/proc/{tok}").st_uid == me:
                    frozen_live.append(int(tok))
            except OSError:
                pass
print(json.dumps({"nproc": os.cpu_count(), "load1": os.getloadavg()[0], "stopped": stopped,
                  "orphans": orphans, "generating": gen, "frozen_live": frozen_live}))
PY
;;
gate) cat <<'PY'
import argparse, json, math, sys
ap = argparse.ArgumentParser()
ap.add_argument("--facts", default="-")
ap.add_argument("--grading", action="store_true")
ap.add_argument("--max-cells", type=int, default=12)
ap.add_argument("--load-frac", type=float, default=0.70)
ap.add_argument("--cores-per-cell", type=int, default=4)   # grade_lab.sh's own 4-cores-a-cell figure
a = ap.parse_args()
f = json.load(sys.stdin if a.facts == "-" else open(a.facts))
reasons = []
if f["stopped"]:
    reasons.append(f"{len(f['stopped'])} stopped process(es) of ours: {f['stopped'][:4]}")
if f["orphans"]:
    reasons.append(f"{len(f['orphans'])} orphaned prover(s) of ours (parent pid 1): {f['orphans'][:4]}")
if f["frozen_live"]:
    reasons.append(f"cpu-yield's frozen.pids names live pid(s): {f['frozen_live'][:4]}")
limit = a.load_frac * f["nproc"]
if f["load1"] > limit:
    reasons.append(f"load {f['load1']:.1f} is above {a.load_frac:.0%} of {f['nproc']} cores ({limit:.0f})")
if a.grading and f["generating"]:
    reasons.append(f"{len(f['generating'])} generation process(es) of ours are running: {f['generating'][:3]}")
cells = min(a.max_cells, int(math.floor((limit - f["load1"]) / a.cores_per_cell)))
if a.grading and not reasons and cells < 1:
    # --jobs 0 is not "no cells": run_par.py takes it as "as many as the machine has"
    reasons.append(f"headroom gives {cells} grading cell(s); refusing rather than passing --jobs 0")
ok = not reasons
print(json.dumps({"ok": ok, "cells": max(cells, 0) if ok else 0, "reasons": reasons,
                  "load1": round(f["load1"], 2), "nproc": f["nproc"]}))
sys.exit(0 if ok else 3)
PY
;;
sentinel) cat <<'PY'
import argparse, hashlib, json, os, sys, time
ap = argparse.ArgumentParser()
ap.add_argument("mode", choices=["check", "write"])
ap.add_argument("step")
ap.add_argument("--dir", default="t/out/r12-data/done")
ap.add_argument("--inputs", nargs="*", default=[])
ap.add_argument("--note", default="")
a = ap.parse_args()
def digest(paths):
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.encode("utf-8") + b"\0")
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        h.update(b"\0")
    return h.hexdigest()
path = os.path.join(a.dir, a.step + ".json")
missing = [p for p in a.inputs if not os.path.exists(p)]
if a.mode == "check":
    # the inputs of a check are the step's own outputs: one that does not exist yet means not done,
    # never "done with different inputs"
    if missing or not os.path.exists(path):
        print(f"{a.step}: not done" + (f" ({len(missing)} output(s) absent)" if missing else ""))
        sys.exit(1)
if missing:
    print(f"sentinel {a.step}: cannot record a step whose output is missing: {missing[:3]}", file=sys.stderr)
    sys.exit(3)
d = digest(a.inputs)
if a.mode == "check":
    old = json.load(open(path))
    if old.get("digest") != d:
        print(f"{a.step}: done before with different inputs (recorded {old.get('digest', '')[:12]}, now {d[:12]}); "
              f"move {path} aside to redo it")
        sys.exit(3)
    print(f"{a.step}: done ({old.get('when', '?')})")
    sys.exit(0)
os.makedirs(a.dir, exist_ok=True)
tmp = f"{path}.{os.getpid()}.tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump({"step": a.step, "digest": d, "inputs": sorted(a.inputs), "note": a.note,
               "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, fh, indent=1)
os.replace(tmp, path)
print(f"{a.step}: recorded {d[:12]}")
PY
;;
extract_check) cat <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, "t")
import spec_experiment as se
tag = sys.argv[1]
d = se.OUT_ROOT / tag
raw = {p.stem for p in (d / "raw").glob("*.json")}
problems = []
try:
    ext = json.loads((d / "extract.json").read_text(encoding="utf-8"))
    tests = json.loads((d / "tests.json").read_text(encoding="utf-8"))
except (OSError, ValueError) as e:
    print(f"{tag}: extract.json/tests.json unreadable: {e}")
    sys.exit(3)
if set(ext) != raw:
    problems.append(f"extract.json covers {len(ext)} records, raw/ has {len(raw)}")
tasked = {k for k, e in ext.items() if e.get("stage") == "task"}
if set(tests) != tasked:
    problems.append(f"tests.json covers {len(tests)} tasks, extract.json names {len(tasked)}")
files = {p.stem for p in (d / "tasks").glob("*.json")}
names = {e["name"] for e in ext.values() if e.get("stage") == "task"}
if files != names:
    problems.append(f"tasks/ holds {len(files)} files, extract.json names {len(names)}")
passing = sum(1 for v in tests.values() if v.get("overall") == "pass")
print(json.dumps({"tag": tag, "raw": len(raw), "tasks": len(tasked), "passing": passing, "problems": problems}))
sys.exit(3 if problems else 0)
PY
;;
repair) cat <<'PY'
import argparse, hashlib, json, os, shutil, sys
from collections import Counter
sys.path.insert(0, "t")
import spec_experiment as se
ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("dst")
ap.add_argument("--pool", default="v6")
ap.add_argument("--mode", choices=["repair", "drop"], default="repair")
ap.add_argument("--root", default=None, help="tag root instead of t/out/spec-experiment (tests)")
a = ap.parse_args()
root = se.OUT_ROOT if a.root is None else __import__("pathlib").Path(a.root)
src, dst = root / a.src, root / a.dst
if (dst / "raw").exists() and any((dst / "raw").iterdir()):
    print(f"refusing: {dst / 'raw'} already holds files; this repair writes a fresh tag only"); sys.exit(3)
files = sorted((src / "raw").glob("*.json"), key=lambda p: int(p.stem))
if not files:
    print(f"refusing: no raw records under {src}"); sys.exit(3)
dec = json.JSONDecoder()
intact, torn, unreadable = {}, {}, []
for p in files:
    text = p.read_text(encoding="utf-8")
    try:
        intact[p] = json.loads(text)
    except ValueError:
        try:
            obj, end = dec.raw_decode(text)      # the leading complete record, and where it ends
        except ValueError as e:
            unreadable.append(f"{p.name}: no leading record ({e})"); continue
        torn[p] = (obj, end, text)
if unreadable:
    print("refusing:\n  " + "\n  ".join(unreadable)); sys.exit(3)
if not intact:
    print("refusing: no intact record to take the tag's keys and options from"); sys.exit(3)
keys = set(next(iter(intact.values())))
sig = Counter((json.dumps(r.get("options"), sort_keys=True), r.get("model"), r.get("prompt_version"),
               r.get("pool_version")) for r in intact.values()).most_common(1)[0][0]
P = se.pool(a.pool) if (torn and a.mode == "repair") else {}
problems = []
for p, (obj, end, text) in sorted(torn.items()):
    head, tail, why = text[:end], text[end:], []
    if json.dumps(obj, indent=1) != head:
        why.append("the leading record does not re-serialise byte-exactly")
    if set(obj) != keys:
        why.append(f"keys differ from the tag's: {sorted(set(obj) ^ keys)}")
    if str(obj.get("task_id")) != p.stem:
        why.append("task_id differs from the file name")
    if (json.dumps(obj.get("options"), sort_keys=True), obj.get("model"), obj.get("prompt_version"),
            obj.get("pool_version")) != sig:
        why.append("options, model, prompt or pool differ from the tag's other records")
    if not tail.strip() or not tail.rstrip().endswith("}"):
        why.append("the tail is not the end of a second record")
    if a.mode == "repair":
        try:
            entry = P.get(int(obj.get("task_id")))
        except (TypeError, ValueError):
            entry = None
        if entry is None or obj.get("messages") != se.build_prompt(entry, obj.get("prompt_version")):
            why.append(f"messages differ from the prompt pool {a.pool} builds for this problem")
    if why:
        problems.append(f"{p.name}: " + "; ".join(why))
if problems:
    print("refusing, nothing written:\n  " + "\n  ".join(problems)); sys.exit(3)
(dst / "raw").mkdir(parents=True, exist_ok=True)
def put(path, data: bytes):
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data); os.replace(tmp, path)
manifest = {"source": a.src, "mode": a.mode, "pool": a.pool, "intact": len(intact), "repaired": [], "dropped": [],
            "sha256": {}}
for p, obj in intact.items():
    data = p.read_bytes(); put(dst / "raw" / p.name, data)
    manifest["sha256"][p.name] = hashlib.sha256(data).hexdigest()
for p, (obj, end, text) in sorted(torn.items()):
    if a.mode == "drop":
        manifest["dropped"].append(int(p.stem)); continue
    data = text[:end].encode("utf-8"); put(dst / "raw" / p.name, data)
    manifest["repaired"].append(int(p.stem)); manifest["sha256"][p.name] = hashlib.sha256(data).hexdigest()
put(dst / "REPAIR.json", json.dumps(manifest, indent=1).encode("utf-8"))
print(json.dumps({k: (v if not isinstance(v, dict) else len(v)) for k, v in manifest.items()}))
PY
;;
plan) cat <<'PY'
import argparse, hashlib, json, os, shutil, sys
from pathlib import Path
sys.path.insert(0, "t")
import spec_experiment as se, pool_pick, spec_check, surface, harness
ap = argparse.ArgumentParser()
ap.add_argument("tag")
ap.add_argument("--out", required=True); ap.add_argument("--prefix", required=True)
ap.add_argument("--chunk-size", type=int, default=40)
ap.add_argument("--trusted", default=None, help="an earlier table whose rows may be kept")
ap.add_argument("--graded-dir", default=None, help="the task files that table graded")
ap.add_argument("--dedupe-tag", default=None, help="a tag whose graded programs need not be graded again")
a = ap.parse_args()
d = se.OUT_ROOT / a.tag
tests = json.loads((d / "tests.json").read_text(encoding="utf-8"))
passing = sorted({v["name"] for v in tests.values() if v.get("overall") == "pass"})
current = {}
for name in passing:
    p = d / "tasks" / f"{name}.json"
    if not p.exists():
        print(f"refusing: {a.tag} passing answer {name} has no task file"); sys.exit(3)
    current[name] = harness.load(p)
def sha(task): return spec_check.task_sha256(task)
def bad_cell(c): return "timeout" in c or "FLAKED" in c
trusted_ok, seen_keys = set(), {}
if a.trusted and a.graded_dir:
    cols, rows = se.parse_kernel_table(Path(a.trusted))
    for name, row in rows.items():
        g = Path(a.graded_dir) / f"{name}.json"
        if name in current and g.exists() and sha(harness.load(g)) == sha(current[name]) \
                and cols == spec_check.KERNELS and not any(bad_cell(c) for c in row.values()):
            trusted_ok.add(name); seen_keys.setdefault(pool_pick.key(current[name]), ("trusted", name))
if a.dedupe_tag:
    od = se.OUT_ROOT / a.dedupe_tag
    cols, rows = se.parse_kernel_table(od / "kernels.md")
    for name, row in rows.items():
        g = od / "tasks" / f"{name}.json"
        if g.exists() and cols == spec_check.KERNELS and not any(bad_cell(c) for c in row.values()):
            seen_keys.setdefault(pool_pick.key(harness.load(g)), (a.dedupe_tag, name))
todo, deduped = [], {}
for name in passing:
    if name in trusted_ok:
        continue
    k = pool_pick.key(current[name])
    if k in seen_keys:
        deduped[name] = list(seen_keys[k]); continue
    seen_keys[k] = ("chunk", name); todo.append(name)
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
chunks = []
for i in range(0, len(todo), a.chunk_size):
    names = todo[i:i + a.chunk_size]
    cname = f"{a.prefix}{i // a.chunk_size + 1:02d}"
    cdir = out / cname
    manifest = {"tag": a.tag, "chunk": cname, "names": names, "sha256": {n: sha(current[n]) for n in names}}
    mpath = cdir / "manifest.json"
    if mpath.exists():
        old = json.loads(mpath.read_text(encoding="utf-8"))
        if old.get("names") != names or old.get("sha256") != manifest["sha256"]:
            print(f"refusing: {cdir} exists with a different manifest; move it aside to replan"); sys.exit(3)
        chunks.append(cname); continue
    (cdir / "grade-in").mkdir(parents=True, exist_ok=True)
    for n in names:
        shutil.copyfile(d / "tasks" / f"{n}.json", cdir / "grade-in" / f"{n}.json")
    tmp = cdir / f".manifest.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(manifest, indent=1), encoding="utf-8"); os.replace(tmp, mpath)
    chunks.append(cname)
plan = {"tag": a.tag, "passing": len(passing), "trusted_ok": sorted(trusted_ok), "deduped": deduped,
        "todo": todo, "chunks": chunks, "trusted": a.trusted, "graded_dir": a.graded_dir, "dedupe_tag": a.dedupe_tag}
ppath = out / f"{a.prefix}plan.json"
tmp = out / f".{a.prefix}plan.{os.getpid()}.tmp"
tmp.write_text(json.dumps(plan, indent=1), encoding="utf-8"); os.replace(tmp, ppath)
print(json.dumps({"tag": a.tag, "passing": len(passing), "trusted_ok": len(trusted_ok), "deduped": len(deduped),
                  "todo": len(todo), "chunks": chunks}))
PY
;;
check_table) cat <<'PY'
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, "t")
import spec_experiment as se, spec_check
ap = argparse.ArgumentParser()
ap.add_argument("table"); ap.add_argument("manifest")
a = ap.parse_args()
cols, rows = se.parse_kernel_table(Path(a.table))
names = set(json.loads(Path(a.manifest).read_text(encoding="utf-8"))["names"])
problems = []
if cols != spec_check.KERNELS:
    problems.append(f"columns {cols} are not the seven kernels")
if set(rows) != names:
    problems.append(f"rows differ from the manifest: missing {sorted(names - set(rows))[:5]}, "
                    f"extra {sorted(set(rows) - names)[:5]}")
if rows:
    for k in cols:   # preflight check 11b's rule: a column malformed on 90% of rows is a dead kernel, not verdicts
        n = sum(1 for r in rows.values() if r.get(k, "").lower().startswith("malformed"))
        if n >= 0.9 * len(rows):
            problems.append(f"{k} is malformed on {n} of {len(rows)} rows")
timeouts = sum(1 for r in rows.values() for c in r.values() if "timeout" in c)
flaked = sum(1 for r in rows.values() for c in r.values() if "FLAKED" in c)
clean = sum(1 for r in rows.values() if all(r.get(k) == "verified / refuted" for k in spec_check.KERNELS))
print(json.dumps({"rows": len(rows), "clean": clean, "timeouts": timeouts, "flaked": flaked, "problems": problems}))
sys.exit(3 if problems else 0)
PY
;;
merge) cat <<'PY'
import argparse, json, os, sys, time
from pathlib import Path
sys.path.insert(0, "t")
import spec_experiment as se, spec_check, harness
ap = argparse.ArgumentParser()
ap.add_argument("tag")
ap.add_argument("--chunks", required=True); ap.add_argument("--prefix", required=True)
ap.add_argument("--install", action="store_true")
a = ap.parse_args()
d = se.OUT_ROOT / a.tag
plan = json.loads((Path(a.chunks) / f"{a.prefix}plan.json").read_text(encoding="utf-8"))
tests = json.loads((d / "tests.json").read_text(encoding="utf-8"))
passing = sorted({v["name"] for v in tests.values() if v.get("overall") == "pass"})
current = {n: harness.load(d / "tasks" / f"{n}.json") for n in passing}
def sha(t): return spec_check.task_sha256(t)
sources = []
if plan.get("trusted") and plan.get("graded_dir"):
    sources.append((Path(plan["trusted"]), Path(plan["graded_dir"]), "trusted"))
for cname in plan["chunks"]:
    cdir = Path(a.chunks) / cname
    if not (cdir / "kernels.md").exists():
        print(f"refusing: chunk {cname} has no kernels.md yet"); sys.exit(3)
    sources.append((cdir / "kernels.md", cdir / "grade-in", cname))
rows_out, origin, dropped, overridden = {}, {}, [], 0
for table, gdir, label in sources:
    cols, rows = se.parse_kernel_table(table)
    if cols != spec_check.KERNELS:
        print(f"refusing: {table} does not have the seven kernel columns"); sys.exit(3)
    for name, row in rows.items():
        if name not in current:
            continue
        g = gdir / f"{name}.json"
        if not g.exists() or sha(harness.load(g)) != sha(current[name]):
            dropped.append(f"{label}:{name}"); continue
        if name in rows_out:
            overridden += 1
        rows_out[name], origin[name] = row, label
twins = 0
for name, (where, twin) in plan.get("deduped", {}).items():
    if name in rows_out:
        continue
    if where == "trusted" or where == "chunk":
        if twin in rows_out:
            rows_out[name], origin[name] = dict(rows_out[twin]), f"same program as {twin}"; twins += 1
    else:   # another tag's graded copy of the same program
        od = se.OUT_ROOT / where
        _cols, orows = se.parse_kernel_table(od / "kernels.md")
        if twin in orows:
            rows_out[name], origin[name] = dict(orows[twin]), f"same program as {where}/{twin}"; twins += 1
missing = [n for n in passing if n not in rows_out]
if missing:
    print(f"refusing: {len(missing)} passing answer(s) have no trustworthy row: {missing[:6]}"); sys.exit(3)
lines = [f"# t cross-kernel agreement, {time.strftime('%Y-%m-%d %H:%MZ', time.gmtime())}", "",
         "Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. "
         "A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` or `verified / unsound`; neither "
         "counts as agreement.", "",
         f"Merged by t/r12_data_queue.sh from {len(sources)} table(s); a row is kept only when the task it "
         f"graded has the sha256 of the current tasks/<name>.json (content, never the name alone); "
         f"{len(dropped)} row(s) dropped for a content mismatch, {overridden} replaced by a later grade, "
         f"{twins} copied from a row of the same program.", "",
         "| task | " + " | ".join(spec_check.KERNELS) + " |", "|" + "---|" * (len(spec_check.KERNELS) + 1)]
for name in sorted(rows_out):
    lines.append("| " + " | ".join([name] + [rows_out[name].get(k, "—") for k in spec_check.KERNELS]) + " |")
lines += ["", f"Kernels present: {len(spec_check.KERNELS)} of {len(spec_check.KERNELS)} "
          f"({', '.join(spec_check.KERNELS)})", "", "Row origins:"]
lines += [f"- {n}: {origin[n]}" for n in sorted(rows_out)]
text = "\n".join(lines) + "\n"
clean = sum(1 for r in rows_out.values() if all(r.get(k) == "verified / refuted" for k in spec_check.KERNELS))
if a.install:
    target = d / "kernels.md"
    if target.exists() and not (d / "kernels.md.pre-r12").exists():
        os.replace(target, d / "kernels.md.pre-r12")
    tmp = d / f".kernels.{os.getpid()}.tmp"
    tmp.write_text(text, encoding="utf-8"); os.replace(tmp, target)
else:
    sys.stdout.write(text)
print(json.dumps({"tag": a.tag, "rows": len(rows_out), "clean": clean, "dropped": dropped[:10],
                  "dropped_n": len(dropped), "overridden": overridden, "twins": twins,
                  "installed": bool(a.install)}))
PY
;;
spec_verify) cat <<'PY'
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, "t")
import spec_experiment as se, spec_check, harness
ap = argparse.ArgumentParser()
ap.add_argument("tag"); ap.add_argument("--pool", required=True); ap.add_argument("--log", required=True)
a = ap.parse_args()
d = se.OUT_ROOT / a.tag
problems = []
log = Path(a.log).read_text(encoding="utf-8", errors="replace")
if "NOT CHECKED" in log and a.tag in log.split("NOT CHECKED", 1)[1]:
    problems.append("spec_check reported the tag NOT CHECKED")
rep = json.loads((se.HERE / "out" / "spec-disagree.json").read_text(encoding="utf-8"))
results = rep.get("results", {})
cols, rows = se.parse_kernel_table(d / "kernels.md")
tests = {v["name"]: v.get("overall") for v in json.loads((d / "tests.json").read_text(encoding="utf-8")).values()}
checked = 0
for name, row in rows.items():
    if tests.get(name) != "pass" or not all(row.get(k, "").startswith("verified / refuted") for k in spec_check.KERNELS):
        continue
    r = results.get(f"{a.tag}/{name}")
    if r is None:
        problems.append(f"{name}: no specification result"); continue
    if r.get("pool") != a.pool:
        problems.append(f"{name}: checked under pool {r.get('pool')}, not {a.pool}")
    if r.get("task_sha256") != spec_check.task_sha256(harness.load(d / "tasks" / f"{name}.json")):
        problems.append(f"{name}: result is for a different task content")
    checked += 1
print(json.dumps({"tag": a.tag, "clean_checked": checked, "problems": problems[:8], "problems_n": len(problems)}))
sys.exit(3 if problems else 0)
PY
;;
dev_ids) cat <<'PY'
import argparse, hashlib, json, os, sys, time
from pathlib import Path
sys.path.insert(0, "t")
import spec_experiment as se, spec_check, loop_filter
ap = argparse.ArgumentParser()
ap.add_argument("--split", default="t/out/loop/split-v5.json")
ap.add_argument("--decontam", default="t/decontamination-2026-09-21.json")
ap.add_argument("--pool", default="v5")
ap.add_argument("--n", type=int, default=100)
ap.add_argument("--salt", default="r12-dev")
ap.add_argument("--out", required=True)
a = ap.parse_args()
def fsha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
split = json.loads(Path(a.split).read_text(encoding="utf-8"))
policy = json.loads(Path(a.decontam).read_text(encoding="utf-8"))
train = sorted({int(i) for i in split["train_ids"] if int(i) < se.HUMANEVAL_BASE})   # MBPP only
P = se.pool(a.pool)
with_tests = {t for t in train if t in P and P[t].get("points")}
positives, pending = set(), set()
for td in sorted(se.OUT_ROOT.glob("*")):
    tp = td / "tests.json"
    if not tp.is_file():
        continue
    try:
        tests = json.loads(tp.read_text(encoding="utf-8"))
    except ValueError:
        continue
    cols, rows = se.parse_kernel_table(td / "kernels.md")
    for tid_s, v in tests.items():
        try:
            tid = int(tid_s)
        except ValueError:
            continue
        if tid not in with_tests or v.get("overall") != "pass":
            continue
        row = rows.get(v.get("name"))
        if row is None or cols != spec_check.KERNELS:
            pending.add(tid)                       # passes its tests and was never graded seven ways
        elif all(row.get(k, "").startswith("verified / refuted") for k in spec_check.KERNELS):
            positives.add(tid)                     # a positive already
named = set()
loop = se.HERE / "out" / "loop"
texts = sorted(loop.glob("sft-*.jsonl")) + sorted(loop.glob("pairs-*.jsonl")) + sorted(loop.glob("corpus-*.txt")) \
    + sorted((se.HERE / "out" / "loop-locallm").glob("corpus*.txt"))
for p in texts:
    t = p.read_text(encoding="utf-8", errors="replace")
    named |= set(loop_filter.problem_ids_in(t))
    if p.suffix == ".jsonl":
        for line in t.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and isinstance(row.get("task_id"), int):
                named.add(row["task_id"])
for p in sorted((se.HERE / "out" / "lifted-tasks").glob("*.json")) + sorted((se.HERE / "tasks").glob("*.t")):
    tid = loop_filter.problem_id(p.stem)
    if tid is not None:
        named.add(tid)
# the merged policy: the hand list plus the behavioural duplicates of 2026-09-25
# (loop_filter.decontamination reads both); dev ids 199, 372 and 955 were on
# the merged list and off the hand list when only the hand list was read
merged = loop_filter.decontamination()
listed = set(merged.exclude_train_ids) | set(merged.overlap_eval_ids)
behavioural = Path("t/decontamination-behavioural-2026-09-25.json")
eligible = [t for t in sorted(with_tests) if t not in positives and t not in pending and t not in named and t not in listed]
def rank(t): return hashlib.sha256(f"{a.salt}:{t}".encode("utf-8")).hexdigest()
ordered = sorted(eligible, key=rank)
chosen = sorted(ordered[:a.n])
if len(chosen) < a.n:
    print(f"refusing: only {len(chosen)} eligible problems for a dev split of {a.n}"); sys.exit(3)
out = {"schema": 1, "about": "MBPP train-split problems for choosing the r12 fine-tune's stopping step by "
       "tests passed. Never trained on: the corpus builder and preflight refuse these ids under every alias.",
       "rule": ["split train_ids below the HumanEval base (MBPP), present in the pool with at least one test point",
                "not a positive: no tag holds a test-passing answer that is clean in all seven kernels",
                "not pending: no tag holds a test-passing answer that was never graded seven ways",
                "not named in any pool file, corpus, lifted task or committed task (problem_ids_in, task_id fields)",
                "not in the decontamination list (exclude_future_train_ids or overlap_ids)",
                f"ordered by sha256('{a.salt}:' + id); the first {a.n} are the dev ids"],
       "salt": a.salt, "n": a.n, "pool": a.pool,
       "inputs": {"split": a.split, "split_sha256": fsha(a.split), "decontamination": a.decontam,
                  "decontamination_sha256": fsha(a.decontam),
                  "decontamination_behavioural": str(behavioural) if behavioural.exists() else None,
                  "decontamination_behavioural_sha256": fsha(behavioural) if behavioural.exists() else None},
       "counts": {"mbpp_train": len(train), "with_tests": len(with_tests), "positives": len(positives & with_tests),
                  "pending": len(pending & with_tests), "named_in_training": len(named & with_tests),
                  "listed": len(listed & with_tests), "eligible": len(eligible)},
       "computed": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
       "eligible_in_hash_order": ordered, "dev_ids": chosen}
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
tmp = Path(a.out).with_name(f".{Path(a.out).name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8"); os.replace(tmp, a.out)
print(json.dumps(out["counts"]))
PY
;;
verify_dev) cat <<'PY'
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, "t")
import spec_experiment as se, loop_filter
ap = argparse.ArgumentParser()
ap.add_argument("corpus"); ap.add_argument("--dev", default="t/r12-dev-ids.json")
a = ap.parse_args()
dev = set(json.loads(Path(a.dev).read_text(encoding="utf-8"))["dev_ids"])
found = loop_filter.problem_ids_in(Path(a.corpus).read_text(encoding="utf-8", errors="replace"))
hits = {t: sorted(s) for t, s in found.items() if t in dev}
if hits:
    print(f"REFUSED: {a.corpus} names {len(hits)} dev id(s): {dict(list(hits.items())[:6])}"); sys.exit(3)
print(f"{a.corpus}: none of the {len(dev)} dev ids appears under any alias")
PY
;;
status) cat <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, "t")
import spec_experiment as se, spec_check
done = sorted(Path("t/out/r12-data/done").glob("*.json"))
print("done:", ", ".join(p.stem for p in done) or "nothing")
for tag in sys.argv[1:]:
    d = se.OUT_ROOT / tag
    raw = len(list((d / "raw").glob("*.json"))) if (d / "raw").exists() else 0
    tasks = len(list((d / "tasks").glob("*.json"))) if (d / "tasks").exists() else 0
    cols, rows = se.parse_kernel_table(d / "kernels.md")
    clean = sum(1 for r in rows.values() if all(r.get(k) == "verified / refuted" for k in spec_check.KERNELS))
    print(f"{tag}: raw {raw}, tasks {tasks}, table rows {len(rows)}, clean {clean}")
PY
;;
*) echo "no embedded program named '$1'" >&2; return 1 ;;
esac
}

# ------------------------------------------------------------------- helpers --
refuse() { echo "REFUSED: $*"; exit 3; }
lab() { $SSH "$LAB" "cd ~/$REPO && $*"; }
lab_py() { local name=$1; shift; _py "$name" | $SSH "$LAB" "cd ~/$REPO && nice -n 19 python3 - $*"; }
local_py() { local name=$1; shift; _py "$name" | python3 - "$@"; }

gate() {   # prints the decision; sets CELLS; returns 0 when the lab admits the work
  local flag=${1:-} out rc
  mkdir -p "$RD"
  _py facts | $SSH "$LAB" "python3 -" > "$RD/.facts.json" || refuse "could not read the lab's process table"
  out=$(local_py gate --facts "$RD/.facts.json" --max-cells "$MAX_CELLS" $flag); rc=$?
  echo "gate: $out"
  CELLS=$(printf '%s' "$out" | python3 -c 'import json,sys; print(json.load(sys.stdin)["cells"])' 2>/dev/null || echo 0)
  return $rc
}
admit() {  # gate, or wait for it up to R12_WAIT_MINUTES; never kills anything
  local flag=${1:-} waited=0
  until gate "$flag"; do
    [ "$WAIT_MIN" -gt 0 ] || refuse "the lab did not admit this step (R12_WAIT_MINUTES=N re-checks every 5 minutes)"
    [ "$waited" -lt "$WAIT_MIN" ] || refuse "the lab did not admit this step within $WAIT_MIN minutes"
    sleep 300; waited=$((waited + 5))
  done
}
done_step() { lab_py sentinel check "$1" --dir "$RD/done" --inputs "${@:2}"; }   # 0 done, 1 not, 3 different inputs
mark_step() { lab_py sentinel write "$1" --dir "$RD/done" --inputs "${@:2}" || refuse "could not record $1"; }
check_or_refuse() { local rc; done_step "$@"; rc=$?; [ "$rc" -eq 3 ] && refuse "$1 was done with different inputs"; return $rc; }

take_locks() {
  mkdir -p "$RD"
  mkdir "$RD/.lock" 2>/dev/null || refuse "another queue holds $RD/.lock here"
  lab "mkdir -p $RD && mkdir $RD/.lock" 2>/dev/null || { rmdir "$RD/.lock"; refuse "another queue holds $RD/.lock on the lab"; }
  trap 'rmdir "$RD/.lock" 2>/dev/null; $SSH "$LAB" "rmdir ~/$REPO/$RD/.lock" 2>/dev/null' EXIT
}

grade_chunks() {  # prefix: every planned chunk, one grade_lab.sh call each, table validated here
  local prefix=$1 list c rc
  list=$(lab "ls -d $RD/chunks/$prefix[0-9]* 2>/dev/null | xargs -rn1 basename")
  [ -n "$list" ] || { echo "== $prefix: no chunk to grade"; return 0; }
  for c in $list; do
    if check_or_refuse "chunk-$c" "$RD/chunks/$c/manifest.json"; then continue; fi
    mkdir -p "$SE/$c"
    rsync -a --delete "$LAB:~/$REPO/$RD/chunks/$c/grade-in/" "$SE/$c/grade-in/" || refuse "$c: cannot fetch grade-in"
    rsync -a "$LAB:~/$REPO/$RD/chunks/$c/manifest.json" "$SE/$c/manifest.json" || refuse "$c: cannot fetch manifest"
    [ -d "$SE/$c/.grading" ] && refuse "$c: a .grading lock exists; another grade may be running"
    [ -e "$SE/$c/kernels.md" ] && mv "$SE/$c/kernels.md" "$SE/$c/kernels.md.stale-$(date -u +%Y%m%dT%H%M%SZ)"
    admit --grading
    [ "${CELLS:-0}" -ge 1 ] || refuse "$c: no grading cell admitted"
    echo "== $c: grading with $CELLS cells, --no-cache"
    T_LAB_JOBS=$CELLS T_LAB_SETS=1 T_LAB_RUN_PAR=--no-cache bash t/grade_lab.sh tags "$c"
    rc=$?
    # grade_lab.sh's status is reported, but the table decides: it is validated on its own
    [ "$rc" -eq 0 ] || echo "== $c: grade_lab.sh exited $rc"
    [ -s "$SE/$c/kernels.md" ] || refuse "$c: no table came back"
    local_py check_table "$SE/$c/kernels.md" "$SE/$c/manifest.json" || refuse "$c: the table failed validation"
    rsync -a "$SE/$c/kernels.md" "$LAB:~/$REPO/$RD/chunks/$c/kernels.md" || refuse "$c: cannot store the table on the lab"
    mark_step "chunk-$c" "$RD/chunks/$c/manifest.json" "$RD/chunks/$c/kernels.md"
  done
}

source_step() {  # tag, trusted table or '', its graded dir or '', dedupe tag or ''
  # two statements: `local` expands every word before it assigns any, so
  # prefix="r12-$TAG-c" on the same line read TAG unset under set -u
  # (gnu.org/software/bash/manual/html_node/Bash-Builtins.html, local)
  local TAG=$1 TRUSTED=${2:-} GDIR=${3:-} DEDUPE=${4:-}
  local prefix="r12-$TAG-c" args=""
  if check_or_refuse "merge-$TAG" "$SE/$TAG/kernels.md" "$SE/$TAG/tests.json"; then echo "== $TAG: merged already"; return 0; fi
  admit
  lab_py extract_check "$TAG" || refuse "$TAG: extract.json, tests.json and tasks/ do not agree"
  [ -n "$TRUSTED" ] && args="--trusted $TRUSTED --graded-dir $GDIR"
  [ -n "$DEDUPE" ] && args="$args --dedupe-tag $DEDUPE"
  lab_py plan "$TAG" --out "$RD/chunks" --prefix "$prefix" --chunk-size "$CHUNK" $args || refuse "$TAG: planning failed"
  grade_chunks "$prefix"
  admit
  lab_py merge "$TAG" --chunks "$RD/chunks" --prefix "$prefix" --install || refuse "$TAG: merge refused"
  mark_step "merge-$TAG" "$SE/$TAG/kernels.md" "$SE/$TAG/tests.json"
}

# -------------------------------------------------------------------- steps --
step_p4_extract() {
  local TAG=qwen235-train-p4
  if check_or_refuse "extract-$TAG" "$SE/$TAG/extract.json" "$SE/$TAG/tests.json"; then echo "== $TAG: extracted already"; return 0; fi
  admit
  lab "nice -n 19 python3 t/spec_experiment.py extract --model $TAG --pool v5" || refuse "$TAG: extract failed"
  lab "nice -n 19 python3 t/spec_experiment.py tests --model $TAG --pool v5" || refuse "$TAG: tests failed"
  lab_py extract_check "$TAG" || refuse "$TAG: extraction incomplete"
  mark_step "extract-$TAG" "$SE/$TAG/extract.json" "$SE/$TAG/tests.json"
}
step_train() {
  # the RAM-disk grade of 2026-09-21 is the only table this tag ever had; /dev/shm does not survive a reboot
  lab "mkdir -p $RD/trusted && if [ -f /dev/shm/tup-grade/qwen235-train/kernels.md ] && [ ! -f $RD/trusted/qwen235-train.kernels.md ]; then cp /dev/shm/tup-grade/qwen235-train/kernels.md $RD/trusted/qwen235-train.kernels.md && rsync -a /dev/shm/tup-grade/qwen235-train/tasks/ $RD/trusted/qwen235-train.grade-in/; fi; ls $RD/trusted/qwen235-train.kernels.md 2>/dev/null" \
    && source_step qwen235-train "$RD/trusted/qwen235-train.kernels.md" "$RD/trusted/qwen235-train.grade-in" "" \
    || { echo "== qwen235-train: no trusted table to keep rows from; every passing answer is graded"; source_step qwen235-train "" "" ""; }
}
step_p4() { step_p4_extract; source_step qwen235-train-p4 "" "" qwen235-train; }
step_prover2() { source_step prover-train2 "" "" ""; }   # the reversed session's table is not trusted: all 37 regraded
step_v6new_repair() {   # the light half of v6new: a fresh tag from the torn one, extracted and tested, no grading
  local SRC=qwen235-v6new DST=qwen235-v6new-r12
  if ! check_or_refuse "repair-$SRC" "$SE/$DST/REPAIR.json"; then
    admit
    lab_py repair "$SRC" "$DST" --pool v6 --mode "$V6NEW_MODE" || refuse "$SRC: repair refused"
    mark_step "repair-$SRC" "$SE/$DST/REPAIR.json"
  fi
  if ! check_or_refuse "extract-$DST" "$SE/$DST/extract.json" "$SE/$DST/tests.json"; then
    admit
    lab "nice -n 19 python3 t/spec_experiment.py extract --model $DST --pool v6" || refuse "$DST: extract failed"
    lab "nice -n 19 python3 t/spec_experiment.py tests --model $DST --pool v6" || refuse "$DST: tests failed"
    lab_py extract_check "$DST" || refuse "$DST: extraction incomplete"
    mark_step "extract-$DST" "$SE/$DST/extract.json" "$SE/$DST/tests.json"
  fi
}
step_v6new() {
  step_v6new_repair
  # the original's 121 rows are kept only where the content still matches and no cell timed out
  source_step qwen235-v6new-r12 "$SE/qwen235-v6new/kernels.md" "$SE/qwen235-v6new/tasks" ""
}
step_spec() {
  local pair TAG POOL
  echo "NOTE: spec_check.py rewrites the tracked t/out/spec-disagree.json on the lab at a fixed path; the queue"
  echo "      carries it back deliberately (the command is printed at the end), so the lab's git pull will"
  echo "      refuse until it is committed here."
  for pair in qwen2.5-coder-1.5b-r0hf:v5 qwen2.5-coder-1.5b-r0hf-v3:v5 qwen2.5-coder-1.5b-r1-samp-s1:v5 \
              qwen3.8-27b-fp8-np1024:v5 qwen235-train:v5 qwen235-train-p4:v5 prover-train2:v5 \
              qwen235-v6new-r12:v6 qwen235-v6new-p4:v6; do
    TAG=${pair%%:*}; POOL=${pair##*:}
    if check_or_refuse "spec-$TAG" "$SE/$TAG/kernels.md"; then continue; fi
    admit
    lab "nice -n 19 python3 t/spec_check.py $TAG --pool $POOL --n 100 --only clean --out $RD/SPEC-CHECK-$TAG.md 2>&1 | tee $RD/spec-$TAG.log" \
      || refuse "$TAG: spec_check failed"
    lab_py spec_verify "$TAG" --pool "$POOL" --log "$RD/spec-$TAG.log" || refuse "$TAG: specification results incomplete"
    mark_step "spec-$TAG" "$SE/$TAG/kernels.md" "$RD/SPEC-CHECK-$TAG.md"
  done
  echo "carry the lab's results back:  rsync -a \"\$T_LAB:~/$REPO/t/out/spec-disagree.json\" t/out/spec-disagree.json"
}
step_build() {
  # the r8 recipe's tag glob (t/steps.json) plus this queue's sources; R12_BUILD_TAGS overrides the v5 list
  local V5=${R12_BUILD_TAGS:-'$(ls -d qwen3.8-27b-fp8 qwen3.8-27b-fp8-v3 qwen3.8-27b-fp8-v3-s2 qwen2.5-coder-14b-* qwen3-coder-30b-* deepseek-coder-v2-16b-* 2>/dev/null) student-r4-train locallm-r4-train qwen235-train qwen235-train-p4 prover-train2 qwen2.5-coder-1.5b-r0hf qwen2.5-coder-1.5b-r0hf-v3 qwen2.5-coder-1.5b-r1-samp-s1 qwen3.8-27b-fp8-np1024'}
  local V6='qwen235-v6new-r12 qwen235-v6new-p4'
  # the relabeled rows (t/relabel.py, 2026-09-25) join the r12 pool file when their file is on the lab,
  # capped per problem; the file is one of the sentinel's inputs, so a regenerated one rebuilds the pool
  local RELABEL=t/out/loop/relabel-2026-09-25.jsonl RELABEL_ARGS="" RELABEL_INPUT=""
  if lab "test -f $RELABEL"; then RELABEL_ARGS="--relabel-rows $RELABEL --relabel-cap 3"; RELABEL_INPUT=$RELABEL
  else echo "== build-r12: no $RELABEL on the lab; the pool gets no relabeled rows"; fi
  if ! check_or_refuse build-r12 t/out/loop/split-v5.json t/decontamination-2026-09-21.json t/decontamination-behavioural-2026-09-25.json $RELABEL_INPUT; then
    admit
    lab "cd $SE && for t in $V5; do [ -f \$t/kernels.md ] || { echo missing table: \$t; exit 3; }; done" || refuse "a v5 build tag has no table"
    lab "cd $SE && TAGS=\"$V5\" && cd ~/$REPO && nice -n 19 python3 t/loop_dataset.py --from-samples \$TAGS --split t/out/loop/split-v5.json --min-kernels 7 --out-suffix r12 $RELABEL_ARGS && wc -l t/out/loop/sft-r12.jsonl t/out/loop/pairs-r12.jsonl" \
      || refuse "loop_dataset (r12) failed"
    mark_step build-r12 t/out/loop/split-v5.json t/decontamination-2026-09-21.json t/decontamination-behavioural-2026-09-25.json $RELABEL_INPUT t/out/loop/sft-r12.jsonl
  fi
  if ! check_or_refuse build-r12v6 t/out/loop/split-v6.json; then
    admit
    lab "test -f t/out/loop/split-v6.json" || refuse "t/out/loop/split-v6.json is missing on the lab"
    lab "nice -n 19 python3 t/loop_dataset.py --from-samples $V6 --split t/out/loop/split-v6.json --min-kernels 7 --out-suffix r12v6 && wc -l t/out/loop/sft-r12v6.jsonl" \
      || refuse "loop_dataset (r12v6) failed"
    mark_step build-r12v6 t/out/loop/split-v6.json t/out/loop/sft-r12v6.jsonl
  fi
  echo "next: python3 t/preflight.py --split t/out/loop/split-v5.json --pool t/out/loop/sft-r12.jsonl --strict (plan step 2)"
}
# The r12 baseline: the twelve r11 arms (nine seeds, a same-seed rerun, two
# soups) were decoded on 2026-09-21 and never extracted, tested or graded.
# Each goes through grade_lab.sh heldout, the path every held-out arm takes:
# the raw answers come here, extraction and tests run here under the pool the
# records name, the seven kernels run on the lab, and the results are stored
# back on the lab, whose copy is the one of record. Last in `all`: positives
# first, the comparison arm second.
R11_TAGS="locallm-r11-s1 locallm-r11-s2 locallm-r11-s3 locallm-r11-s4 locallm-r11-s5 locallm-r11-s6 locallm-r11-s7 locallm-r11-s8 locallm-r11-s9 locallm-r11-rerun locallm-r11-soupA locallm-r11-soupB"
step_r11() {
  local T n
  for T in $R11_TAGS; do
    if check_or_refuse "r11-$T" "$SE/$T/kernels.md" "$SE/$T/tests.json"; then echo "== $T: graded already"; continue; fi
    lab "test -f t/out/gen-$T.done" || refuse "$T: no generation sentinel t/out/gen-$T.done on the lab"
    mkdir -p "$SE/$T"
    rsync -a --delete "$LAB:~/$REPO/$SE/$T/raw/" "$SE/$T/raw/" || refuse "$T: cannot fetch the raw answers"
    n=$(ls "$SE/$T/raw" | wc -l)
    [ "$n" -eq 232 ] || refuse "$T: expected 232 raw answers, found $n"
    admit --grading
    [ "${CELLS:-0}" -ge 1 ] || refuse "$T: no grading cell admitted"
    echo "== $T: heldout grading with $CELLS cells, --no-cache"
    T_LAB_JOBS=$CELLS T_LAB_SETS=1 T_LAB_RUN_PAR=--no-cache bash t/grade_lab.sh heldout "$T" || echo "== $T: grade_lab.sh exited $?"
    { [ -s "$SE/$T/kernels.md" ] && [ -s "$SE/$T/tests.json" ]; } || refuse "$T: no table or tests came back"
    rsync -a "$SE/$T/kernels.md" "$SE/$T/tests.json" "$SE/$T/extract.json" "$LAB:~/$REPO/$SE/$T/" || refuse "$T: cannot store the results on the lab"
    rsync -a --delete "$SE/$T/tasks/" "$LAB:~/$REPO/$SE/$T/tasks/" || refuse "$T: cannot store the tasks on the lab"
    mark_step "r11-$T" "$SE/$T/kernels.md" "$SE/$T/tests.json"
  done
}

step_dev_ids() {
  admit
  lab_py dev_ids --split t/out/loop/split-v5.json --decontam t/decontamination-2026-09-21.json --n 100 --salt r12-dev --out "$RD/r12-dev-ids.json" \
    || refuse "dev ids not computed"
  rsync -a "$LAB:~/$REPO/$RD/r12-dev-ids.json" t/r12-dev-ids.json || refuse "cannot fetch the dev ids"
  python3 -c 'import json,sys; d=json.load(open("t/r12-dev-ids.json")); open("t/out/loop/r12-dev-ids.txt","w").write("\n".join(map(str,d["dev_ids"]))+"\n"); print("t/r12-dev-ids.json:", len(d["dev_ids"]), "ids; t/out/loop/r12-dev-ids.txt written")'
  rsync -a t/out/loop/r12-dev-ids.txt "$LAB:~/$REPO/t/out/loop/r12-dev-ids.txt"
}

status() {
  echo "== lab"; gate || true
  lab_py status qwen235-train qwen235-train-p4 qwen235-v6new qwen235-v6new-r12 qwen235-v6new-p4 prover-train2
}

# --------------------------------------------------------------------- main --
main() {
  cd "$(dirname "$0")/.." || exit 1
  case "${1:-}" in
    _py) _py "$2"; exit $? ;;
    ""|-h|--help) sed -n '2,12p' "$0"; exit 0 ;;
  esac
  [ -f t/lab-workstation.conf ] && . t/lab-workstation.conf
  LAB=${T_LAB:?set T_LAB=user@host in t/lab-workstation.conf}
  $SSH "$LAB" true 2>/dev/null || refuse "the lab workstation is not reachable (VPN?)"
  case "$1" in
    status)     status ;;
    gate)       gate "${2:-}" ;;
    verify-dev) shift; [ -n "${1:-}" ] || refuse "verify-dev needs a corpus path"; local_py verify_dev "$1" --dev t/r12-dev-ids.json ;;
    *)          take_locks
                case "$1" in
                  p4-extract) step_p4_extract ;;
                  v6new-repair) step_v6new_repair ;;
                  train)      step_train ;;
                  p4)         step_p4 ;;
                  prover2)    step_prover2 ;;
                  v6new)      step_v6new ;;
                  spec)       step_spec ;;
                  build)      step_build ;;
                  dev-ids)    step_dev_ids ;;
                  r11)        step_r11 ;;
                  all)        step_p4_extract; step_train; step_p4; step_prover2; step_v6new; step_spec; step_build; step_dev_ids; step_r11 ;;
                  *)          refuse "unknown command '$1'" ;;
                esac ;;
  esac
}
main "$@"; exit $?
