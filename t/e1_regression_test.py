#!/usr/bin/env python3
"""Regression checks for the fixed E1 matrix harness + aggregator. Run before scaling.
    ~/e3-venv/bin/python e1_regression_test.py
"""
import json, os, sys, subprocess, tempfile, pathlib
sys.path.insert(0, ".")
import e1_full_adjudicate as H

fails = []


def ck(name, cond):
    print(("ok  " if cond else "FAIL") + "  " + name)
    if not cond:
        fails.append(name)


# ---- 1. reuse_ok: changed source / changed config / unknown key are NOT reused ----
expected = {("/a", "REAL", "dafny"), ("/a", "s1", "dafny")}
src_by = {"/a": "AAA"}
ck("reuse accepts a matching cell",
   H.reuse_ok({"path": "/a", "which": "REAL", "kernel": "dafny", "config_id": "CFG", "src_hash": "AAA"},
              expected, "CFG", src_by))
ck("reuse rejects a changed config",
   not H.reuse_ok({"path": "/a", "which": "REAL", "kernel": "dafny", "config_id": "OLD", "src_hash": "AAA"},
                  expected, "CFG", src_by))
ck("reuse rejects a changed source (spec)",
   not H.reuse_ok({"path": "/a", "which": "s1", "kernel": "dafny", "config_id": "CFG", "src_hash": "ZZZ"},
                  expected, "CFG", src_by))
ck("reuse rejects an unknown key",
   not H.reuse_ok({"path": "/a", "which": "REAL", "kernel": "verus", "config_id": "CFG", "src_hash": "AAA"},
                  expected, "CFG", src_by))

# ---- 2-4. aggregator on fixtures: missing-all-seven, unknown/dup, unanimous refutation ----
K = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
with tempfile.TemporaryDirectory() as d:
    out = pathlib.Path(d) / "out"; out.mkdir()
    man = {"tag": "RT", "classify_cap": 400, "selection_cap": 12, "tasks": {
        "/a": {"name": "A", "status": "ok", "task_src_hash": "AAA", "n_survivors_total": 2, "n_selected": 2,
               "capped_selection": False, "classify_capped": False,
               "survivors": [{"id": "s1", "op": "o1", "witness": "w1", "body": [1], "bodyhash": "b1"},
                             {"id": "s2", "op": "o2", "witness": "w2", "body": [2], "bodyhash": "b2"}]},
        "/b": {"name": "B", "status": "ok", "task_src_hash": "BBB", "n_survivors_total": 1, "n_selected": 1,
               "capped_selection": False, "classify_capped": False,
               "survivors": [{"id": "s3", "op": "o3", "witness": "w3", "body": [3], "bodyhash": "b3"}]}}}
    (out / "E1MAN-RT.json").write_text(json.dumps(man))
    rows = []
    for k in K:                                        # s1 unanimously REFUTED
        rows.append({"path": "/a", "which": "s1", "kernel": k, "state": "refuted", "raw": "refuted",
                     "src_hash": "AAA", "config_id": "CFG"})
    for k in K:                                        # s3 unanimously VERIFIED
        rows.append({"path": "/b", "which": "s3", "kernel": k, "state": "verified", "raw": "verified",
                     "src_hash": "BBB", "config_id": "CFG"})
    # s2: NO cells at all -> must show as not-run x7, not-fully-decided, completeness < 100%
    rows.append({"path": "/a", "which": "s1", "kernel": "dafny", "state": "refuted", "raw": "refuted",
                 "src_hash": "AAA", "config_id": "CFG"})            # DUPLICATE key
    rows.append({"path": "/a", "which": "sX", "kernel": "dafny", "state": "verified", "raw": "v",
                 "src_hash": "AAA", "config_id": "CFG"})            # UNKNOWN key (sX not in manifest)
    (out / "E1FULL-RT.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (out / "E1FULL-RT.meta.json").write_text(json.dumps({"tag": "RT", "config_id": "CFG"}))
    agg = pathlib.Path(__file__).resolve().parent / "e1_full_aggregate.py"
    r = subprocess.run([sys.executable, "-I", str(agg), "RT"], cwd=d, capture_output=True, text=True)
    o = r.stdout
    print("---- aggregator output ----\n" + o + "\n---------------------------")
    # expected cells = (2 survivors + REAL) x 7 for /a  + (1 survivor + REAL) x 7 for /b = 3*7 + 2*7 = 35
    ck("completeness is not 100% (s2 + reals missing)", "/35" in o and "35/35" not in o)
    ck("unknown record rejected (1)", "unknown records rejected: 1" in o.lower())
    ck("duplicate key counted (1)", "identical duplicates: 1" in o.lower())
    ck("s1 counted unanimous-refuted, not disagreement",
       "Unanimous-refuted** (all 7 reject): **1" in o)
    ck("s3 counted unanimous-verified",
       "Unanimous-verified** (all 7 accept): **1" in o)
    ck("s2 (no cells) is not fully decided",
       "Not fully decided" in o and "/ 3**" in o)   # 3 survivors total, s2 not fully decided

# ---- 5. config_id must reflect the PINNED COMMIT, and change when only the pin changes ----
import importlib
with tempfile.TemporaryDirectory() as d:
    base = ("# t/ carries a pinned copy\n\nsome prose with accidental hex like cafe and faced beef\n\n"
            "Pinned commit: `{pin}` (t-proof-engine, 2026-10-10)\n")
    cwd0 = os.getcwd()
    try:
        for sub, pin in (("A", "d13d11d01f8f50687ef645d60aa08c870d664b84"),
                         ("B", "0000000000000000000000000000000000000000")):
            p = pathlib.Path(d) / sub; p.mkdir()
            (p / "ENGINE.md").write_text(base.format(pin=pin))
        os.chdir(pathlib.Path(d) / "A"); idA, confA = H.config_id()
        os.chdir(pathlib.Path(d) / "B"); idB, confB = H.config_id()
    finally:
        os.chdir(cwd0)
    ck("config_id binds the real pinned commit (not scraped prose hex)",
       confA["engine_pin"].startswith("d13d11d01f8f"))
    ck("config_id changes when ONLY the pinned commit changes", idA != idB)

# ---- 6. aggregator must reject stale config / wrong src, and flag conflicting duplicates ----
with tempfile.TemporaryDirectory() as d:
    out = pathlib.Path(d) / "out"; out.mkdir()
    man = {"tag": "RT2", "classify_cap": 400, "selection_cap": 12, "tasks": {
        "/c": {"name": "C", "status": "ok", "task_src_hash": "CCC", "n_survivors_total": 1, "n_selected": 1,
               "capped_selection": False, "classify_capped": False,
               "survivors": [{"id": "s4", "op": "o4", "witness": "w4", "body": [4], "bodyhash": "b4"}]},
        "/e": {"name": "E", "status": "ok", "task_src_hash": "DDD", "n_survivors_total": 1, "n_selected": 1,
               "capped_selection": False, "classify_capped": False,
               "survivors": [{"id": "s5", "op": "o5", "witness": "w5", "body": [5], "bodyhash": "b5"}]}}}
    (out / "E1MAN-RT2.json").write_text(json.dumps(man))
    (out / "E1FULL-RT2.meta.json").write_text(json.dumps({"tag": "RT2", "config_id": "CFG_NEW"}))
    rows = []
    # s4: 5 kernels good (CFG_NEW, src CCC), dafny STALE (CFG_OLD) -> excluded, verus WRONG-SRC -> excluded
    for k in ["spark", "framac", "lean", "rocq", "fstar"]:
        rows.append({"path": "/c", "which": "s4", "kernel": k, "state": "verified", "raw": "verified",
                     "src_hash": "CCC", "config_id": "CFG_NEW"})
    rows.append({"path": "/c", "which": "s4", "kernel": "dafny", "state": "verified", "raw": "v",
                 "src_hash": "CCC", "config_id": "CFG_OLD"})          # stale config -> must be excluded
    rows.append({"path": "/c", "which": "s4", "kernel": "verus", "state": "verified", "raw": "v",
                 "src_hash": "XXX", "config_id": "CFG_NEW"})          # wrong src -> must be excluded
    # s5: a CONFLICTING duplicate on dafny (verified vs refuted), both valid config/src -> must be FLAGGED
    for k in H.KERNELS:
        rows.append({"path": "/e", "which": "s5", "kernel": k, "state": "verified", "raw": "verified",
                     "src_hash": "DDD", "config_id": "CFG_NEW"})
    rows.append({"path": "/e", "which": "s5", "kernel": "dafny", "state": "refuted", "raw": "refuted",
                 "src_hash": "DDD", "config_id": "CFG_NEW"})          # conflict with the verified dafny above
    (out / "E1FULL-RT2.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    agg = pathlib.Path(__file__).resolve().parent / "e1_full_aggregate.py"
    r = subprocess.run([sys.executable, "-I", str(agg), "RT2"], cwd=d, capture_output=True, text=True)
    o = r.stdout
    print("---- RT2 aggregator output ----\n" + o[-1400:] + "\n------------------------------")
    ck("stale-config/wrong-src cells excluded (s4 dafny+verus not counted -> s4 not fully decided)",
       "excluded stale-config rows: 1" in o and "excluded wrong-src rows: 1" in o)   # 2 survivors x7 = 14 expected; s4 missing dafny+verus = 12 valid
    ck("conflicting duplicate is flagged, not last-wins",
       "conflict" in o.lower())


# ---- 7. missing/empty run metadata must FAIL CLOSED (reject all rows) ----
with tempfile.TemporaryDirectory() as d:
    out = pathlib.Path(d) / "out"; out.mkdir()
    man = {"tag": "RT3", "classify_cap": 400, "selection_cap": 12, "tasks": {
        "/f": {"name": "F", "status": "ok", "task_src_hash": "FFF", "n_survivors_total": 1, "n_selected": 1,
               "capped_selection": False, "classify_capped": False,
               "survivors": [{"id": "s6", "op": "o6", "witness": "w6", "body": [6], "bodyhash": "b6"}]}}}
    (out / "E1MAN-RT3.json").write_text(json.dumps(man))
    rows = [{"path": "/f", "which": "s6", "kernel": k, "state": "verified", "raw": "verified",
             "src_hash": "FFF", "config_id": "CFG"} for k in H.KERNELS]
    (out / "E1FULL-RT3.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    # NOTE: deliberately NO E1FULL-RT3.meta.json
    agg = pathlib.Path(__file__).resolve().parent / "e1_full_aggregate.py"
    r = subprocess.run([sys.executable, "-I", str(agg), "RT3"], cwd=d, capture_output=True, text=True)
    o = r.stdout
    ck("missing metadata fails closed (all 7 rows rejected, 0 fully-decided)",
       "excluded no-metadata rows (fail-closed): 7" in o and "0 / 1**" in o)

print(("\nALL REGRESSION CHECKS PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
