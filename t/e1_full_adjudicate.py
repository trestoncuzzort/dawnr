#!/usr/bin/env python3
"""E1 FIXED, two phases, identity-bound. Prior art MutDafny (arXiv:2511.15403);
receipt e1-full-adjudication-2026-10-14.

  manifest  <corpus_dir> <tag> [max_surv]     freeze selected survivors with stable body-hash ids
  adjudicate <tag> <jobs> [config_label]       adjudicate real + each frozen survivor in all 7 kernels

Every result is bound to the task source hash AND a config id (engine pin + solver config + harness hash).
Resume reuses a cell ONLY when (path, which, kernel) is in the frozen manifest AND the stored src_hash and
config_id match the current run; a changed spec or a different solver forces a re-run and never silently
reuses a stale cell. Per cell keeps state AND raw detail; typed errors are not timeouts; a result is written
for every planned cell; output is checkpointed incrementally. Resource guards (A8): T_SPARK_JOBS=1.
"""
import json, os, sys, hashlib, pathlib, tempfile, signal, time, subprocess

os.environ.setdefault("T_LEAN_BIN", os.path.expanduser("~/.local/lean/bin/lean"))
os.environ["T_SPARK_JOBS"] = "1"
# T_SPARK_PROVER selects SPARK's backend (default z3); set explicitly for the alternate-solver comparison.
os.environ.setdefault("T_SPARK_PROVER", "z3")
HOME = os.path.expanduser("~")
KDIRS = [f"{HOME}/.cargo/bin", f"{HOME}/.opam/default/bin", f"{HOME}/.elan/bin", f"{HOME}/.local/lean/bin",
         f"{HOME}/.local/fstar/fstar/bin", f"{HOME}/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin",
         f"{HOME}/.local/verus/verus-x86-linux", f"{HOME}/.local/dafny"]
os.environ["PATH"] = ":".join(KDIRS) + ":" + os.environ.get("PATH", "")
sys.path.insert(0, ".")
import audit, tasks_io  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402

KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
OUT = pathlib.Path("out"); OUT.mkdir(exist_ok=True)


def canon(x):
    return hashlib.sha1(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()


def norm(v):
    s = "verified" if v == "verified" else "refuted" if v == "refuted" else \
        "unverifiable:" + (v.split(":", 1)[0] if ":" in v else v)
    return s, v


def config_id():
    """Bind results to engine + solver + harness identity so stale/cross-config cells are never reused."""
    def ver(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip()[:60]
        except Exception:
            return "?"
    import re
    try:
        engine = pathlib.Path("ENGINE.md").read_text()
        m = re.search(r"Pinned commit:\s*`?([0-9a-f]{40})`?", engine)
        pin = m.group(1) if m else "nopin"
    except Exception:
        pin = "?"
    conf = {"engine_pin": pin[:12], "spark_prover": os.environ.get("T_SPARK_PROVER"),
            "spark_jobs": os.environ.get("T_SPARK_JOBS"),
            "dafny": ver(["dafny", "--version"]), "z3": ver(["z3", "--version"]),
            "harness_sha": canon(pathlib.Path(__file__).read_text())[:12]}
    return hashlib.sha1(json.dumps(conf, sort_keys=True).encode()).hexdigest()[:12], conf


class _TO(Exception):
    pass


def reuse_ok(r, expected, cfg, src_by):
    """A checkpointed record may be reused on resume ONLY if its (path,which,kernel) is an expected
    manifest cell, its config_id matches this run, and its src_hash matches the manifest's frozen source
    for that task. A changed spec or a different solver config forces a re-run."""
    key = (r.get("path"), r.get("which"), r.get("kernel"))
    return (key in expected and r.get("config_id") == cfg and r.get("src_hash") == src_by.get(r.get("path")))


def build_manifest(corpus, tag, max_surv):
    files = [str(p) for p in sorted(pathlib.Path(corpus).iterdir()) if p.suffix in (".t", ".json")]
    man = {"tag": tag, "corpus": str(corpus), "classify_cap": audit.harness.MAX_CANDIDATES,
           "selection_cap": max_surv, "tasks": {}}
    n_sel = 0
    for path in files:
        try:
            task = tasks_io.load_task(path)
        except Exception as e:  # noqa: BLE001
            man["tasks"][path] = {"status": f"load-error:{type(e).__name__}"}
            continue
        old = signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(_TO()))
        signal.alarm(audit.TASK_SECONDS)
        try:
            res = audit.classify(task)
        except _TO:
            res = {"status": "classify-timeout"}
        except Exception as e:  # noqa: BLE001
            res = {"status": f"classify-error:{type(e).__name__}"}
        finally:
            signal.alarm(0); signal.signal(signal.SIGALRM, old)
        if res.get("status") != "ok":
            man["tasks"][path] = {"name": task.get("name"), "status": res.get("status")}
            continue
        tsh = canon(task)
        survs = res["survivors"]
        sel = []
        for s in survs[:max_surv]:
            bh = canon(s["body"])
            sel.append({"id": hashlib.sha1(f"{tsh}|{s['op']}|{bh}".encode()).hexdigest()[:16],
                        "op": s["op"], "witness": audit.harness.witness(s["witness"]),
                        "body": s["body"], "bodyhash": bh})
        n_sel += len(sel)
        man["tasks"][path] = {"name": res["name"], "status": "ok", "task_src_hash": tsh,
                              "n_survivors_total": len(survs), "n_selected": len(sel),
                              "capped_selection": len(survs) > max_surv, "classify_capped": res.get("capped", False),
                              "survivors": sel}
    (OUT / f"E1MAN-{tag}.json").write_text(json.dumps(man), encoding="utf-8")
    ok = [t for t in man["tasks"].values() if t.get("status") == "ok"]
    print(f"manifest {tag}: {len(files)} tasks, {len(ok)} ok, "
          f"{sum(1 for t in ok if t['n_selected'])} survivor-bearing, {n_sel} survivors frozen")


def _cell(arg):
    path, which, body_json, kernel, exp_src, cfg = arg
    rec = {"path": path, "which": which, "kernel": kernel, "config_id": cfg}
    try:
        task = tasks_io.load_task(path)
        got_src = canon(task)
        rec["src_hash"] = got_src
        if got_src != exp_src:                          # spec changed since the manifest was frozen
            rec.update(state="refused:source-changed", raw=f"exp {exp_src[:8]} got {got_src[:8]}")
            return rec
        body = task["body"] if which == "REAL" else json.loads(body_json)
        work = pathlib.Path(tempfile.mkdtemp(prefix="t-fa-"))
        _lmod, suffix = audit.tlib._LOWER_MOD[kernel]
        old = signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(_TO()))
        signal.alarm(max(90, audit.TASK_SECONDS))
        try:
            v = audit._kernel_verdict(task, body, kernel, work / f"c.{suffix}")
        finally:
            signal.alarm(0); signal.signal(signal.SIGALRM, old)
        st, raw = norm(v)
        rec.update(state=st, raw=raw)
    except _TO:
        rec.update(state="unverifiable:worker-timeout", raw="worker-timeout", src_hash=rec.get("src_hash"))
    except Exception as e:  # noqa: BLE001
        rec.update(state="unverifiable:worker-error", raw=f"{type(e).__name__}:{e}"[:160], src_hash=rec.get("src_hash"))
    return rec


def adjudicate(tag, jobs, label=""):
    man = json.loads((OUT / f"E1MAN-{tag}.json").read_text())
    cfg, conf = config_id()
    units, expected = [], set()
    scope = os.environ.get("E1_SCOPE", "all")            # "all" = full population (E1 deliverable); "survivors" = scoped diagnostic
    for path, t in man["tasks"].items():
        if t.get("status") != "ok":
            continue
        if scope == "survivors" and not t["survivors"]:
            continue                                     # scoped diagnostic: reals only where a survivor exists
        src = t["task_src_hash"]
        for k in KERNELS:
            units.append((path, "REAL", None, k, src, cfg)); expected.add((path, "REAL", k))
            for s in t["survivors"]:
                units.append((path, s["id"], json.dumps(s["body"]), k, src, cfg)); expected.add((path, s["id"], k))
    outp = OUT / f"E1FULL-{tag}.jsonl"
    # resume: reuse only cells matching the manifest key AND this config AND a non-stale src
    done = set()
    if outp.exists():
        src_by = {p: t.get("task_src_hash") for p, t in man["tasks"].items()}
        for ln in outp.read_text().splitlines():
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if reuse_ok(r, expected, cfg, src_by):
                done.add((r["path"], r["which"], r["kernel"]))
    todo = [u for u in units if (u[0], u[1], u[3]) not in done]
    (OUT / f"E1FULL-{tag}.meta.json").write_text(json.dumps(
        {"tag": tag, "label": label, "config_id": cfg, "config": conf,
         "expected_cells": len(expected), "resumed": len(done)}, indent=2))
    (OUT / f"E1FULL-{tag}.pid").write_text(str(os.getpid()))
    print(f"adjudicate {tag} [{label}] cfg={cfg}: {len(expected)} cells, {len(done)} reused, {len(todo)} to run, jobs={jobs}", flush=True)
    t0 = time.time(); n = 0
    with outp.open("a", encoding="utf-8") as fh, ProcessPoolExecutor(max_workers=jobs) as ex:
        for rec in ex.map(_cell, todo):
            fh.write(json.dumps(rec) + "\n"); fh.flush(); n += 1
            if n % 100 == 0:
                print(f"  .. {n}/{len(todo)} ({time.time()-t0:.0f}s)", flush=True)
    print(f"adjudicate {tag}: wrote {n} cells (+{len(done)} reused) -> {outp}", flush=True)


def main():
    cmd = sys.argv[1]
    if cmd == "manifest":
        build_manifest(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 12)
    elif cmd == "adjudicate":
        adjudicate(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 12,
                   sys.argv[4] if len(sys.argv) > 4 else "")
    else:
        print("usage: manifest <corpus> <tag> [max_surv] | adjudicate <tag> <jobs> [label]"); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
