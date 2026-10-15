#!/usr/bin/env python3
"""E1 paired twin-gate over the 426 archived pairs -- SAFE v2 (separate from the preserved raw v1 run).

Admission/duplicate policy is the SHARED e1_admit module, used identically by resume, run completeness and
the authoritative aggregator, so one row can never be counted two ways. Integrity contract (all exercised by
`control`):
  * base config_id binds engine pin + git head/dirty + source hashes of the verdict-relevant engine modules +
    ALL SEVEN kernel versions & availability + flake + serial/spark policy + harness sha. eff_config_id adds
    the EFFECTIVE jobs + computed SPARK-jobs env + available kernels, and every graded row is bound to it, so a
    resume under different concurrency re-grades instead of silently reusing.
  * cmd_manifest freezes an IMMUTABLE manifest (enforces id==sha256(program\\0twin)[:16] and real/twin contract
    equality, fail-closed) and REFUSES to overwrite an existing manifest that differs in ANY frozen field
    (config, per-pair program/twin/witness/contract hashes, or keyset) -- preserving the existing bytes.
  * cmd_run validates each pair's CURRENT program/twin/witness/contract against the frozen manifest BEFORE any
    lowering; drift is an INCOMPLETE cell (never graded under a stale hash), and the validated snapshot is
    retained (mutable files never reopened). Typed outcomes (parse/lower/backend-unavailable/input-drift) are
    recomputed FRESH every run and never reused from a checkpoint, so a stale drift/parse row cannot poison a
    later valid resume.
  * a graded Result is reused only when e1_admit.graded_admissible holds: eff_config match, frozen identity
    match, both flake-agreement flags True, and each Result's own source_sha256 equals the bound lowered
    source (never the 64-zero placeholder). A kernel TIMEOUT is a produced, budget-limited OBSERVATION: reused
    like any graded Result, interpreted unverifiable. Only worker-level failures (no Result) are transient.
  * completeness applies the SAME policy: complete = a resolved deterministic typed outcome
    (lower-error/backend-unavailable) OR a single admissible graded observation; drift/worker/conflict/missing
    /source-mismatch are INCOMPLETE.

    python3 -I e1_pairs_gate2.py manifest <out-dir> [--flake 3]
    python3 -I e1_pairs_gate2.py run      <out-dir> [--jobs 8] [--flake 3] [--limit N]
    python3 -I e1_pairs_gate2.py control
"""
import argparse
import hashlib
import json
import os
import pathlib
import subprocess
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

import surface          # noqa: E402
import run_par          # noqa: E402
import verifiers        # noqa: E402
import e1_admit as admit  # noqa: E402
from concurrent.futures import ProcessPoolExecutor, as_completed  # noqa: E402

KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
PAIRS = pathlib.Path("twins/pairs")
ENGINE_MODS = ["run_par.py", "verifiers/__init__.py", "fuzz_lower.py", "tlib.py"]
IDENT_KEYS = ("program_sha256", "twin_sha256", "witness_sha256", "contract_sha256")


def sha_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def canon(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def unfence(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()


def _git(*args):
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:  # noqa: BLE001
        return "?"


def base_config_id(flake_n, cols):
    import re
    try:
        m = re.search(r"Pinned commit:\s*`?([0-9a-f]{40})`?", pathlib.Path("ENGINE.md").read_text())
        pin = m.group(1) if m else "nopin"
    except Exception:  # noqa: BLE001
        pin = "?"
    present = [b for b, v in cols if not str(v).startswith("ABSENT")]
    src = {}
    # verdict-relevant engine modules + every present adapter + the admission POLICY module (e1_admit)
    for mod in ENGINE_MODS + ["e1_admit.py"] + [f"verifiers/{b}.py" for b in present]:
        p = pathlib.Path(mod)
        src[mod] = sha_text(p.read_text())[:12] if p.exists() else "missing"
    for p in sorted(pathlib.Path(".").glob("lower_*.py")):   # per-kernel lowering modules also affect the verdict
        src[p.name] = sha_text(p.read_text())[:12]
    conf = {"gate": "paired-grounded-witness", "flake_n": flake_n, "engine_pin": pin[:12],
            "git_head": _git("rev-parse", "HEAD")[:12],
            # NB: the engine/harness/policy SOURCE is bound by content hashes in engine_src below (incl. dirty
            # edits); a global git-dirty COUNT is redundant with that and brittle (adding an unrelated harness
            # file would spuriously drift config_id between manifest-freeze and run), so it is not included.
            "kernels": {b: str(v)[:60] for b, v in cols}, "available": sorted(present),
            "serial": os.environ.get("T_CELL_SERIAL"), "spark_prover": os.environ.get("T_SPARK_PROVER"),
            "engine_src": src, "harness_sha": sha_text(pathlib.Path(__file__).read_text())[:12]}
    return hashlib.sha1(json.dumps(conf, sort_keys=True).encode()).hexdigest()[:12], conf


def eff_config_id(base_cfg, jobs, spark_env, present):
    eff = {"base": base_cfg, "jobs": jobs, "spark_env": dict(sorted(spark_env.items())),
           "available": sorted(present)}
    return hashlib.sha1(json.dumps(eff, sort_keys=True).encode()).hexdigest()[:12], eff


def pair_path(task, pid):
    return PAIRS / f"{task}.{pid}.json"


def read_pair(task, pid):
    r = json.loads(pair_path(task, pid).read_text())
    prog, twin = unfence(r["program"]), unfence(r["twin"])
    w = r.get("witness")
    ident = {"program_sha256": sha_text(prog), "twin_sha256": sha_text(twin),
             "witness_sha256": canon(w), "witness_kind": (w or {}).get("_kind"),
             "id_matches_sha": hashlib.sha256((prog + "\0" + twin).encode()).hexdigest()[:16] == pid,
             "archived_verified_by": r.get("verified_by"), "archived_twin_refuted_by": r.get("twin_refuted_by")}
    try:
        real_task = surface.parse(prog)
        twin_task = surface.parse(twin)
        contract = {k: v for k, v in real_task.items() if k != "body" and not k.startswith("_")}
        tcontract = {k: v for k, v in twin_task.items() if k != "body" and not k.startswith("_")}
        ident["contract_sha256"] = canon(contract)
        ident["twin_contract_sha256"] = canon(tcontract)
        ident["contract_eq"] = canon(contract) == canon(tcontract)
        snap = {"clean": {k: v for k, v in real_task.items() if not k.startswith("_")},
                "twin_body": twin_task.get("body"), "witness": w}
        return ident, snap, None
    except Exception as e:  # noqa: BLE001
        ident["contract_eq"] = None
        ident["contract_sha256"] = None
        return ident, None, f"{type(e).__name__}: {e}"[:160]


# --------------------------------------------------------------------- manifest

def cmd_manifest(a, _probe=None):
    out = pathlib.Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    cols, present = _probe() if _probe else run_par.probe_backends()
    cfg, conf = base_config_id(a.flake, cols)
    pairs, refusals = {}, []
    for p in sorted(PAIRS.glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        pid, task = r["id"], r.get("task")
        ident, _snap, perr = read_pair(task, pid)
        if not ident["id_matches_sha"]:
            refusals.append(f"{pid}: id != sha256(program\\0twin)[:16]")
        if perr is None and ident.get("contract_eq") is False:
            refusals.append(f"{pid}: real/twin contract differ")
        pairs[pid] = {"id": pid, "task": task, "problem": r.get("problem"), "operator": r.get("operator"),
                      "parse_ok": perr is None, "parse_error": perr, "witness_kind": ident["witness_kind"],
                      **{k: ident.get(k) for k in IDENT_KEYS},
                      "twin_contract_sha256": ident.get("twin_contract_sha256"),
                      "archived_verified_by": ident["archived_verified_by"],
                      "archived_twin_refuted_by": ident["archived_twin_refuted_by"]}
    if refusals:
        print(f"REFUSED manifest: {len(refusals)} pair-identity violations (fail-closed). e.g. {refusals[:3]}"); return 4
    keyset = [[pid, k] for pid in pairs for k in KERNELS]
    man = {"version": "e1_pairs_gate2", "config_id": cfg, "config": conf, "kernels": KERNELS,
           "n_pairs": len(pairs), "expected_cells": len(keyset),
           "witness_kinds": {wk: sum(1 for r in pairs.values() if r["witness_kind"] == wk)
                             for wk in sorted({r["witness_kind"] for r in pairs.values()})},
           "parse_ok_count": sum(1 for r in pairs.values() if r["parse_ok"]), "pairs": pairs, "keyset": keyset}
    manp = out / "E1PAIRS2-MAN.json"
    if manp.exists():                                    # IMMUTABLE: refuse ANY semantic difference; preserve bytes
        old = json.loads(manp.read_text())
        same = (old.get("config_id") == cfg               # compare the WHOLE canonical frozen pairs map, not a subset
                and canon(old.get("pairs")) == canon(man["pairs"])
                and old.get("keyset") == man["keyset"])
        if not same:
            print(f"REFUSED: a different manifest already exists at {manp} (cfg {old.get('config_id')} vs {cfg}); "
                  f"refusing silent re-freeze and preserving existing bytes. Use a fresh out-dir."); return 7
    tmp = manp.with_suffix(".json.tmp"); tmp.write_text(json.dumps(man, indent=2), encoding="utf-8")
    os.replace(tmp, manp)
    print(f"manifest: {len(pairs)} pairs, {len(keyset)} cells, cfg={cfg}; parse_ok={man['parse_ok_count']}/{len(pairs)} "
          f"witness_kinds={man['witness_kinds']} -> {manp}")
    return 0


# --------------------------------------------------------------------- run

def _pair_cell(bname, pid, real_path, twin_path, flake_n):
    import importlib
    backend = importlib.import_module(f"verifiers.{bname}")
    (r_real, a1), (r_twin, a2) = verifiers.cell_pair(backend.verify, pathlib.Path(real_path),
                                                     pathlib.Path(twin_path), flake_n)
    return {"id": pid, "kernel": bname, "real": r_real.to_json(), "twin": r_twin.to_json(),
            "real_agreed": bool(a1), "twin_agreed": bool(a2)}


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _ca_write(src_dir, text, suffix):
    data = text.encode("utf-8"); h = sha_bytes(data); p = src_dir / f"{h}.{suffix}"
    if p.exists():
        if p.read_bytes() != data:                       # on-disk bytes differ from the content-address: tampered
            raise RuntimeError(f"content-address collision at {p}")
    else:
        p.write_bytes(data)                              # write BYTES (no newline translation)
    return h, p


def _rehash_ok(src_dir, bs):
    """Re-hash the retained source BYTES (read_bytes, matching Result.source_sha256/sha256_file) -- read_text
    would normalise CRLF->LF and hide a byte edit."""
    try:
        rp = pathlib.Path(src_dir) / f"{bs['real_src_sha256']}.{bs['suffix']}"
        tp = pathlib.Path(src_dir) / f"{bs['twin_src_sha256']}.{bs['suffix']}"
        return (rp.exists() and sha_bytes(rp.read_bytes()) == bs["real_src_sha256"]
                and tp.exists() and sha_bytes(tp.read_bytes()) == bs["twin_src_sha256"])
    except Exception:  # noqa: BLE001
        return False


def cmd_run(a, _probe=None, _grade=None):
    out = pathlib.Path(a.out_dir); src = out / "src"; src.mkdir(parents=True, exist_ok=True)
    manp = out / "E1PAIRS2-MAN.json"
    if not manp.exists():
        print("REFUSED: no manifest; run `manifest` first."); return 5
    man = json.loads(manp.read_text())
    cols, present = _probe() if _probe else run_par.probe_backends()
    cfg, conf = base_config_id(a.flake, cols)
    if cfg != man["config_id"]:
        print(f"REFUSED: base config_id drift (manifest {man['config_id']} != now {cfg})."); return 6
    present_map = {b: (lower, suffix) for b, lower, suffix in present}
    spark_env = run_par.spark_jobs_env(a.jobs)
    eff_cfg, eff_conf = eff_config_id(cfg, a.jobs, spark_env, list(present_map))
    pairs = man["pairs"]
    ids = list(pairs)[:a.limit] if a.limit else list(pairs)
    ckpt = out / "E1PAIRS2.jsonl"

    # FRESH validation + lowering (typed states recomputed every run; never reused from the log).
    fresh = {}          # (pid,k) -> typed rec (resolved or incomplete) decided THIS run
    bound = {}          # (pid,k) -> {real/twin_src_sha256, paths, suffix} for gradeable cells
    for pid in ids:
        pr = pairs[pid]
        ident, snap, perr = read_pair(pr["task"], pid)
        drift = [k for k in IDENT_KEYS if ident.get(k) != pr.get(k)]
        if not ident["id_matches_sha"]:
            drift.append("id_matches_sha")
        if ident.get("contract_eq") is False:
            drift.append("contract_eq")
        if drift:
            for k in KERNELS:
                fresh[(pid, k)] = {"state": "unverified:input-drift", "reason": f"drift:{drift}"}
            continue
        if perr is not None:                             # frozen input was parse_ok; a parse-error now is drift
            for k in KERNELS:
                fresh[(pid, k)] = {"state": "unverified:input-drift", "reason": f"parse-now:{perr}"}
            continue
        clean, tb, w = snap["clean"], snap["twin_body"], snap["witness"]
        for k in KERNELS:
            if k not in present_map:
                fresh[(pid, k)] = {"state": "unverified:backend-unavailable"}; continue
            lower, suffix = present_map[k]
            try:
                real_src = lower(clean, clean["body"]); twin_src = lower(clean, tb, witness=w)
            except Exception as e:  # noqa: BLE001
                fresh[(pid, k)] = {"state": "unverified:lower-error", "reason": f"{type(e).__name__}:{e}"[:120]}; continue
            rh, rp = _ca_write(src, real_src, suffix); th, tp = _ca_write(src, twin_src, suffix)
            bound[(pid, k)] = {"real_src_sha256": rh, "twin_src_sha256": th,
                               "real_path": str(rp), "twin_path": str(tp), "suffix": suffix}

    # Freeze/MERGE the immutable SRC-INDEX from the validated, lowered inputs BEFORE any proof work. The merge
    # is monotonic: a run only ADDS keys for the cells it lowered, so a failed-preflight (all-drift -> empty)
    # attempt cannot poison it; a CONFLICT is only an existing key whose sha changed (real tamper/config drift),
    # caught HERE, before any kernel runs.
    sip = out / f"E1PAIRS2-SRC-INDEX.{eff_cfg}.json"
    new_index = {f"{pid}|{k}": {"real": bs["real_src_sha256"], "twin": bs["twin_src_sha256"], "suffix": bs["suffix"]}
                 for (pid, k), bs in bound.items()}
    existing_index = json.loads(sip.read_text()) if sip.exists() else {}
    for ck, v in new_index.items():
        if ck in existing_index and existing_index[ck] != v:
            print(f"REFUSED: source-index conflict at {ck} for eff_cfg {eff_cfg} (sha changed); preserving existing."); return 8
    merged_index = {**existing_index, **new_index}
    sip.write_text(json.dumps(merged_index, indent=0), encoding="utf-8")

    # prior GRADED rows only (typed are never reused)
    prior = {}
    if ckpt.exists():
        for ln in ckpt.read_text().splitlines():
            try:
                d = json.loads(ln)
            except Exception:  # noqa: BLE001
                continue
            if d.get("state") == "graded":
                prior.setdefault((d.get("id"), d.get("kernel")), []).append(d)

    def ident_of(pid):
        return {k: pairs[pid].get(k) for k in admit.IDENT3}

    reused, conflict, to_grade = {}, {}, []
    for key, bs in bound.items():
        adm = [d for d in prior.get(key, []) if admit.graded_admissible(d, eff_cfg, ident_of(key[0]), bs, strict=True)]
        interps = {admit.interp_key(d) for d in adm}
        if len(interps) > 1:
            conflict[key] = True
        elif len(interps) == 1:
            reused[key] = adm[-1]
        else:
            to_grade.append(key)

    print(f"run base={cfg} eff={eff_cfg}: {len(ids)*len(KERNELS)} cells; fresh-typed={len(fresh)} "
          f"reused={len(reused)} conflict={len(conflict)} to_grade={len(to_grade)}; "
          f"jobs={a.jobs} kernel_calls={2*a.flake*a.jobs} T_SPARK_JOBS={spark_env.get('T_SPARK_JOBS')}", flush=True)
    fh = ckpt.open("a", encoding="utf-8")
    # append fresh typed rows (for the record; never reused)
    for key, t in fresh.items():
        fh.write(json.dumps({"id": key[0], "kernel": key[1], "eff_config_id": eff_cfg,
                             "witness_kind": pairs[key[0]]["witness_kind"],
                             "program_sha256": pairs[key[0]]["program_sha256"],
                             "twin_sha256": pairs[key[0]]["twin_sha256"], **t}) + "\n")

    def emit_graded(pid, k, bs, d):
        pr = pairs[pid]
        rr, tr = d["real"], d["twin"]
        base = {"id": pid, "kernel": k, "eff_config_id": eff_cfg, "witness_kind": pr["witness_kind"],
                "program_sha256": pr["program_sha256"], "twin_sha256": pr["twin_sha256"],
                "witness_sha256": pr["witness_sha256"], "suffix": bs["suffix"],
                "real_src_sha256": bs["real_src_sha256"], "twin_src_sha256": bs["twin_src_sha256"]}
        # validate each Result graded the bytes we bound (no 64-zero, no swap)
        if rr.get("source_sha256") != bs["real_src_sha256"] or tr.get("source_sha256") != bs["twin_src_sha256"]:
            base.update(state="unverified:result-source-mismatch",
                        reason=f"real {rr.get('source_sha256','?')[:8]} vs {bs['real_src_sha256'][:8]}; "
                               f"twin {tr.get('source_sha256','?')[:8]} vs {bs['twin_src_sha256'][:8]}")
            return base, False
        base.update(state="graded", real_outcome=rr["outcome"], twin_outcome=tr["outcome"],
                    real_agreed=d["real_agreed"], twin_agreed=d["twin_agreed"], real_result=rr, twin_result=tr)
        return base, True

    newly = {}
    n = 0

    def run_one(pid, k, bs):
        nonlocal n
        try:
            d = (_grade or _pair_cell)(k, pid, bs["real_path"], bs["twin_path"], a.flake)
            rec, ok2 = emit_graded(pid, k, bs, d)
        except Exception as e:  # noqa: BLE001  worker-level failure: transient, no Result
            rec = {"id": pid, "kernel": k, "eff_config_id": eff_cfg, "witness_kind": pairs[pid]["witness_kind"],
                   "program_sha256": pairs[pid]["program_sha256"], "twin_sha256": pairs[pid]["twin_sha256"],
                   "state": "unverified:worker-error", "reason": f"{type(e).__name__}:{e}"[:160]}
            ok2 = False
        fh.write(json.dumps(rec) + "\n"); fh.flush(); n += 1
        newly[(pid, k)] = rec                            # store ALL emitted rows; completeness re-admits them

    if to_grade:
        if _grade:
            for key in to_grade:
                run_one(key[0], key[1], bound[key])
        else:
            with ProcessPoolExecutor(max_workers=a.jobs, mp_context=verifiers.mp_context(),
                                     initializer=run_par._worker_env, initargs=(spark_env,)) as ex:
                futs = {ex.submit(_pair_cell, k, pid, bound[(pid, k)]["real_path"], bound[(pid, k)]["twin_path"], a.flake):
                        (pid, k) for (pid, k) in to_grade}
                for fut in as_completed(futs):
                    pid, k = futs[fut]; bs = bound[(pid, k)]
                    try:
                        d = fut.result(); rec, _ok = emit_graded(pid, k, bs, d)
                    except Exception as e:  # noqa: BLE001
                        rec = {"id": pid, "kernel": k, "eff_config_id": eff_cfg,
                               "witness_kind": pairs[pid]["witness_kind"], "program_sha256": pairs[pid]["program_sha256"],
                               "twin_sha256": pairs[pid]["twin_sha256"], "state": "unverified:worker-error",
                               "reason": f"{type(e).__name__}:{e}"[:160]}
                    fh.write(json.dumps(rec) + "\n"); fh.flush(); n += 1
                    newly[(pid, k)] = rec                # store ALL emitted rows; completeness re-admits them
                    if n % 50 == 0:
                        print(f"  .. graded {n}/{len(to_grade)}", flush=True)
    fh.close()

    # Build the authoritative per-attempt RESOLUTION (bound to eff_cfg). A graded cell is resolved only if its
    # retained source BYTES still re-hash (read_bytes) to the frozen SRC-INDEX content-address, so later
    # aggregation binds to a frozen source + actual bytes, not a self-claim.
    def rehash_ok(bs):
        return _rehash_ok(src, bs)

    def graded_entry(row, bs):
        return {"state": "graded", "witness_kind": row.get("witness_kind"), "eff_config_id": eff_cfg,
                "real_outcome": row["real_outcome"], "twin_outcome": row["twin_outcome"],
                "real_agreed": row["real_agreed"], "twin_agreed": row["twin_agreed"],
                "real_src_sha256": bs["real_src_sha256"], "twin_src_sha256": bs["twin_src_sha256"], "suffix": bs["suffix"]}

    complete, incomplete, reasons = 0, [], {}
    resolution = {}
    for pid in ids:
        for k in KERNELS:
            key = (pid, k); ck = f"{pid}|{k}"; wk = pairs[pid]["witness_kind"]
            if key in fresh:
                t = fresh[key]
                resolution[ck] = {"state": t["state"], "reason": t.get("reason"), "witness_kind": wk, "eff_config_id": eff_cfg}
                if t["state"] in admit.RESOLVED_TYPED:
                    complete += 1; reasons[t["state"]] = reasons.get(t["state"], 0) + 1
                else:
                    incomplete.append(list(key)); reasons[t["state"]] = reasons.get(t["state"], 0) + 1
            elif key in conflict:
                resolution[ck] = {"state": "conflict", "witness_kind": wk, "eff_config_id": eff_cfg}
                incomplete.append(list(key)); reasons["conflict"] = reasons.get("conflict", 0) + 1
            elif key in reused and rehash_ok(bound[key]):
                resolution[ck] = graded_entry(reused[key], bound[key])
                complete += 1; reasons["reused-graded"] = reasons.get("reused-graded", 0) + 1
            elif newly.get(key) is not None and rehash_ok(bound.get(key, {})) and admit.graded_admissible(
                    newly[key], eff_cfg, ident_of(pid), bound.get(key), strict=True):
                resolution[ck] = graded_entry(newly[key], bound[key])
                complete += 1; reasons["newly-graded"] = reasons.get("newly-graded", 0) + 1
            else:
                row = newly.get(key)
                if row is None:
                    rk = "worker-or-missing"
                elif row.get("state") != "graded":           # typed worker/other failure carried verbatim
                    rk = row["state"].replace("unverified:", "")
                elif not (row.get("real_agreed") is True and row.get("twin_agreed") is True):
                    rk = "unstable"                          # a graded row that failed admission -> name the cause
                elif (row.get("real_result") or {}).get("backend") != k or (row.get("twin_result") or {}).get("backend") != k:
                    rk = "backend-mismatch"
                elif not rehash_ok(bound.get(key, {})):
                    rk = "source-bytes"
                else:
                    rk = "invalid-grade"
                resolution[ck] = {"state": f"incomplete:{rk}", "reason": (row or {}).get("reason"),
                                  "witness_kind": wk, "eff_config_id": eff_cfg}
                incomplete.append(list(key)); reasons[rk] = reasons.get(rk, 0) + 1

    (out / f"E1PAIRS2-RESOLUTION.{eff_cfg}.json").write_text(json.dumps(resolution, indent=0), encoding="utf-8")
    meta = {"config_id": cfg, "eff_config_id": eff_cfg, "eff_config": eff_conf, "config": conf,
            "jobs": a.jobs, "flake": a.flake, "spark_env": spark_env, "expected_cells": len(ids) * len(KERNELS),
            "complete": complete, "incomplete": len(incomplete), "incomplete_sample": incomplete[:20],
            "reasons": reasons, "graded_this_run": n,
            "src_index": sip.name, "resolution": f"E1PAIRS2-RESOLUTION.{eff_cfg}.json"}
    (out / "E1PAIRS2-RUNMETA.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"run done: {complete}/{len(ids)*len(KERNELS)} COMPLETE; incomplete={len(incomplete)}; reasons={reasons}", flush=True)
    print("E1PAIRS2-RUN-COMPLETE" if not incomplete else "E1PAIRS2-RUN-INCOMPLETE", flush=True)
    return 0 if not incomplete else 2


# --------------------------------------------------------------------- control

def cmd_control(_a):
    import tempfile
    import types
    global PAIRS
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond))); print(f"  {name}: [{'ok' if cond else 'FAIL'}]")

    d = pathlib.Path(tempfile.mkdtemp()); pdir = d / "twins" / "pairs"; pdir.mkdir(parents=True)
    PAIRS = pdir

    def mk(task, br, bt, w):
        prog = f"t 1\ntask {task}(n: int) returns (r: bool)\n  requires n >= 0\n  ensures r == (n >= 0)\n{{ {br} }}"
        twin = f"t 1\ntask {task}(n: int) returns (r: bool)\n  requires n >= 0\n  ensures r == (n >= 0)\n{{ {bt} }}"
        pid = hashlib.sha256((prog + "\0" + twin).encode()).hexdigest()[:16]
        f = pdir / f"{task}.{pid}.json"
        f.write_text(json.dumps({"id": pid, "task": task, "program": "```t\n" + prog + "\n```",
                                 "twin": "```t\n" + twin + "\n```", "witness": w,
                                 "verified_by": KERNELS, "twin_refuted_by": KERNELS}))
        return pid, f
    pid1, f1 = mk("p1", "r := true;", "r := false;", {"_kind": "value", "_ens": True, "n": 0})

    def probe():
        lower = lambda clean, body, witness=None: "// " + json.dumps(body)[:60] + "\n"
        cols = [("dafny", "d4.9"), ("verus", "v0.1")] + [(k, "ABSENT") for k in KERNELS[2:]]
        return cols, [("dafny", lower, "dfy"), ("verus", lower, "rs")]

    S = {"outcome": (admit.VERIFIED, admit.REFUTED), "agree": (True, True), "raise_once": [False],
         "sha_mode": "valid", "calls": []}

    def grade(k, pid, rp, tp, flake):
        S["calls"].append((pid, k))
        if S["raise_once"][0]:
            S["raise_once"][0] = False; raise RuntimeError("transient worker boom")
        ro, to = S["outcome"]; a1, a2 = S["agree"]
        rsha = verifiers.sha256_file(pathlib.Path(rp)) if S["sha_mode"] == "valid" else admit.ZERO_SHA
        tsha = verifiers.sha256_file(pathlib.Path(tp)) if S["sha_mode"] == "valid" else admit.ZERO_SHA
        R = lambda o, s: {"backend": k, "backend_version": "stub", "source_sha256": s, "outcome": o, "ok": o == admit.VERIFIED}
        return {"id": pid, "kernel": k, "real": R(ro, rsha), "twin": R(to, tsha), "real_agreed": a1, "twin_agreed": a2}

    def NS(outd, jobs=2):
        return types.SimpleNamespace(out_dir=str(outd), flake=3, jobs=jobs, limit=0)
    out = d / "run"
    ok("manifest freezes", cmd_manifest(NS(out), _probe=probe) == 0 and (out / "E1PAIRS2-MAN.json").exists())
    cmd_run(NS(out), _probe=probe, _grade=grade); first = len(S["calls"])
    ok("run grades present kernels (2)", first == 2)
    S["calls"].clear(); cmd_run(NS(out), _probe=probe, _grade=grade)
    ok("valid reuse grades nothing", len(S["calls"]) == 0)

    # drift -> no grade under stale hash; then RESTORE -> grades (fixes resume poisoning)
    r = json.loads(f1.read_text()); orig = r["program"]
    r["program"] = orig.replace("r := true;", "r := (n > -1);"); f1.write_text(json.dumps(r))
    S["calls"].clear(); cmd_run(NS(out), _probe=probe, _grade=grade)
    rows = [json.loads(x) for x in (out / "E1PAIRS2.jsonl").read_text().splitlines()]
    ok("drift: no grading under stale hash",
       any(x.get("state") == "unverified:input-drift" and x["id"] == pid1 for x in rows) and len(S["calls"]) == 0)
    r["program"] = orig; f1.write_text(json.dumps(r))
    S["calls"].clear(); rc_restore = cmd_run(NS(out), _probe=probe, _grade=grade)
    # correct outcome: drift did NOT poison -> cell completes after restore (via valid pre-drift reuse here)
    ok("restore after drift completes (no poisoning)", rc_restore == 0)

    # witness-only re-freeze refused + bytes preserved
    before = (out / "E1PAIRS2-MAN.json").read_bytes()
    r = json.loads(f1.read_text()); r["witness"] = {"_kind": "value", "_ens": True, "n": 5}; f1.write_text(json.dumps(r))
    rc_w = cmd_manifest(NS(out), _probe=probe)
    ok("witness-only re-freeze refused + bytes preserved",
       rc_w == 7 and (out / "E1PAIRS2-MAN.json").read_bytes() == before)
    r["witness"] = {"_kind": "value", "_ens": True, "n": 0}; f1.write_text(json.dumps(r))

    # zero-sha Result rejected (not a valid graded observation)
    o2 = d / "run2"; cmd_manifest(NS(o2), _probe=probe); S["sha_mode"] = "zero"; S["calls"].clear()
    rc_z = cmd_run(NS(o2), _probe=probe, _grade=grade)
    rowz = [json.loads(x) for x in (o2 / "E1PAIRS2.jsonl").read_text().splitlines()]
    ok("zero-sha Result rejected -> incomplete",
       rc_z == 2 and any(x.get("state") == "unverified:result-source-mismatch" for x in rowz))
    S["sha_mode"] = "valid"

    # jobs change -> re-grade (eff_config_id differs); zero reuse
    o3 = d / "run3"; cmd_manifest(NS(o3), _probe=probe)
    cmd_run(NS(o3, jobs=1), _probe=probe, _grade=grade); S["calls"].clear()
    cmd_run(NS(o3, jobs=2), _probe=probe, _grade=grade)
    ok("jobs change re-grades (eff_config bound)", len(S["calls"]) == 2)

    # stable timeout is a reused observation (not retried, not a verdict)
    o4 = d / "run4"; cmd_manifest(NS(o4), _probe=probe); S["outcome"] = (verifiers.Outcome.TIMEOUT, verifiers.Outcome.TIMEOUT)
    cmd_run(NS(o4), _probe=probe, _grade=grade); S["calls"].clear()
    cmd_run(NS(o4), _probe=probe, _grade=grade)
    ok("stable timeout reused as observation (0 regrade)", len(S["calls"]) == 0)
    S["outcome"] = (admit.VERIFIED, admit.REFUTED)

    # transient worker-error retried
    o5 = d / "run5"; cmd_manifest(NS(o5), _probe=probe); S["raise_once"][0] = True; S["calls"].clear()
    cmd_run(NS(o5), _probe=probe, _grade=grade); S["calls"].clear()
    cmd_run(NS(o5), _probe=probe, _grade=grade)
    ok("transient worker-error retried", len(S["calls"]) >= 1)

    # unstable agreed=False not reused
    o6 = d / "run6"; cmd_manifest(NS(o6), _probe=probe); S["agree"] = (False, False)
    cmd_run(NS(o6), _probe=probe, _grade=grade); S["calls"].clear()
    cmd_run(NS(o6), _probe=probe, _grade=grade)
    ok("unstable (agreed=False) not reused", len(S["calls"]) >= 1); S["agree"] = (True, True)

    # all-drift (empty index) must NOT poison a later valid resume -> fresh single-pair corpus
    pdir2 = d / "c2" / "twins" / "pairs"; pdir2.mkdir(parents=True); PAIRS = pdir2
    pq = "t 1\ntask q(n: int) returns (r: bool)\n  requires n >= 0\n  ensures r == (n >= 0)\n{ r := true; }"
    tq = "t 1\ntask q(n: int) returns (r: bool)\n  requires n >= 0\n  ensures r == (n >= 0)\n{ r := false; }"
    pidq = hashlib.sha256((pq + "\0" + tq).encode()).hexdigest()[:16]; fq = pdir2 / f"q.{pidq}.json"
    fq.write_text(json.dumps({"id": pidq, "task": "q", "program": "```t\n" + pq + "\n```", "twin": "```t\n" + tq + "\n```",
                              "witness": {"_kind": "value", "_ens": True, "n": 0}, "verified_by": KERNELS, "twin_refuted_by": KERNELS}))
    o7 = d / "run7"; cmd_manifest(NS(o7), _probe=probe)
    rq = json.loads(fq.read_text()); origq = rq["program"]
    rq["program"] = origq.replace("r := true;", "r := (n > -1);"); fq.write_text(json.dumps(rq))
    rc_drift = cmd_run(NS(o7), _probe=probe, _grade=grade)      # all cells drift -> empty index, incomplete
    rq["program"] = origq; fq.write_text(json.dumps(rq))
    rc_restore7 = cmd_run(NS(o7), _probe=probe, _grade=grade)   # restore -> must grade + complete, NEVER exit 8
    ok("all-drift empty index no poison; restore completes", rc_drift == 2 and rc_restore7 == 0)
    PAIRS = pdir

    # newline byte tamper (LF->CRLF) caught by read_bytes rehash (read_text would hide it)
    import tempfile as _tf
    sd = pathlib.Path(_tf.mkdtemp()); hz, pz = _ca_write(sd, "line1\nline2\n", "dfy")
    bsz = {"real_src_sha256": hz, "twin_src_sha256": hz, "suffix": "dfy"}
    ok("rehash valid before tamper", _rehash_ok(sd, bsz))
    pz.write_bytes(b"line1\r\nline2\r\n")                        # same text, different bytes
    ok("CRLF byte tamper caught by read_bytes rehash", not _rehash_ok(sd, bsz))

    allok = all(c for _, c in checks)
    print("CONTROL " + ("PASS" if allok else "FAIL"))
    return 0 if allok else 1


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("manifest"); m.add_argument("out_dir"); m.add_argument("--flake", type=int, default=3); m.set_defaults(fn=cmd_manifest)
    r = sub.add_parser("run"); r.add_argument("out_dir"); r.add_argument("--jobs", type=int, default=8)
    r.add_argument("--flake", type=int, default=3); r.add_argument("--limit", type=int, default=0); r.set_defaults(fn=cmd_run)
    c = sub.add_parser("control"); c.set_defaults(fn=cmd_control)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
