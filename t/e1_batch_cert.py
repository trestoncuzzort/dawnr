#!/usr/bin/env python3
"""Run-backed BATCH observation-certificate minter over an authoritative v2 run.

It REUSES the validated aggregator's semantics (no weaker duplicate): e1_pairs_aggregate.aggregate_v2 does the
full manifest->runmeta->resolution/src-index chain validation, and build_cells_v2 does the admission (frozen
source-index byte re-hash, identity, current-resolution/row agreement). A certificate is emitted for EVERY
cell of the frozen keyset:

  * a cell the aggregator admits as graded -> a `paired-observation` certificate (obs_certificate): the exact
    archived real/twin/witness (whose ALL identity hashes -- program, twin, witness, contract -- are re-checked
    against the frozen manifest), the recorded outcome and full Result metadata, and run_backed = the run's
    eff_config_id + lowered-source digests. It REPLAYS through `dawnr check`, which re-lowers and re-runs the
    kernel (no model) AND binds run_backed (the re-lowered digests must match the run's) -- else not reproduced.
  * any other cell (lower-error / backend-unavailable / input-drift / worker / conflict / source-bytes /
    not-run) -> a native-checkable `observation-record-only` certificate carrying the identity + state + reason;
    `dawnr check` reports it UNDECIDED (never an empty-denominator success).

    python3 -I e1_batch_cert.py mint-run <v2-run-dir> <pairs-dir> <cert-dir>
    python3 -I e1_batch_cert.py control
"""
import hashlib
import json
import os
import pathlib
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import e1_admit as admit                 # noqa: E402
import obs_certificate as OC             # noqa: E402
import e1_pairs_aggregate as AGG         # noqa: E402

KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]


def mint_run(run_dir, pairs_dir, cert_dir):
    run_dir = pathlib.Path(run_dir); pairs_dir = pathlib.Path(pairs_dir); cert_dir = pathlib.Path(cert_dir)
    cert_dir.mkdir(parents=True, exist_ok=True)
    man_path = run_dir / "E1PAIRS2-MAN.json"; runmeta_path = run_dir / "E1PAIRS2-RUNMETA.json"
    # REUSE the validated aggregator for the full chain + the per-cell admission (no weaker duplicate).
    rep, rc = AGG.aggregate_v2(man_path, runmeta_path)
    if rc != 0:
        print(f"REFUSED mint-run: chain validation failed: {rep.get('FAIL')}"); return 3
    man = json.loads(man_path.read_text()); runmeta = json.loads(runmeta_path.read_text())
    man_sha = hashlib.sha256(man_path.read_bytes()).hexdigest()               # concrete source-run provenance:
    ckpt_sha = hashlib.sha256((run_dir / "E1PAIRS2.jsonl").read_bytes()).hexdigest()  # names WHICH run (pass1 vs pass2
    eff_cfg = rep["eff_config_id"]                                            # share config bytes but differ here)
    cells, _ = AGG.build_cells_v2(run_dir, man, runmeta, eff_cfg)
    src_index = json.loads((run_dir / runmeta["src_index"]).read_text())
    log = {}
    for ln in (run_dir / "E1PAIRS2.jsonl").read_text().splitlines():
        try:
            d = json.loads(ln)
        except Exception:  # noqa: BLE001
            continue
        if d.get("state") == "graded":
            log.setdefault((d.get("id"), d.get("kernel")), []).append(d)
    pair_text = {}
    for p in pairs_dir.glob("*.json"):
        r = json.loads(p.read_text())
        pair_text[r["id"]] = (OC.unfence(r["program"]), OC.unfence(r["twin"]), r.get("witness"))

    resolution = json.loads((run_dir / runmeta["resolution"]).read_text())
    eff_conf = runmeta.get("eff_config")
    env_spark_jobs = (runmeta.get("spark_env") or {}).get("T_SPARK_JOBS")   # worker-env-UPDATE value; may be absent
    counts = {"paired-observation": 0, "record-only": 0}
    index = []

    def record(ck, pid, kn, pr, state, reason=None):
        res = resolution.get(ck, {})
        if reason is None:
            reason = res.get("reason")                          # carry the run's recorded reason through
        # partial result: a log row may exist (e.g. unstable/conflict) even without an admissible observation
        rows = log.get((pid, kn), [])
        partial = {"real_result": rows[-1].get("real_result"), "twin_result": rows[-1].get("twin_result")} if rows else None
        ident = {k: pr.get(k) for k in ("program_sha256", "twin_sha256", "witness_sha256", "contract_sha256")}
        cert = OC.make_record(pid, kn, state, reason, ident, eff_cfg, man["config_id"], pr.get("witness_kind"), partial_result=partial)
        (cert_dir / f"{ck}.cert.json").write_text(json.dumps(cert, indent=1))
        counts["record-only"] += 1; index.append((ck, "record-only", state))

    for pid, pr in man["pairs"].items():
        for kn in KERNELS:
            ck = f"{pid}|{kn}"; cl = cells.get((pid, kn), {})
            if cl.get("state") != "graded":
                record(ck, pid, kn, pr, f"record-only:{cl.get('state', 'not-run')}"); continue
            txt = pair_text.get(pid)
            if txt is None:
                record(ck, pid, kn, pr, "record-only:missing-pair-text", None); continue
            real_t, twin_t, w = txt
            # the EMBEDDED archived text must match the frozen manifest on EVERY identity hash (not just prog/twin)
            if (OC._sha(real_t) != pr.get("program_sha256") or OC._sha(twin_t) != pr.get("twin_sha256")
                    or OC._sha(w) != pr.get("witness_sha256") or OC._contract_sha(real_t) != pr.get("contract_sha256")):
                record(ck, pid, kn, pr, "record-only:archived-identity-mismatch", "archived pair text != frozen manifest hashes"); continue
            si = src_index.get(ck) or {}
            bound = {"real_src_sha256": si.get("real"), "twin_src_sha256": si.get("twin")}
            adm = [d for d in log.get((pid, kn), [])
                   if admit.graded_admissible(d, eff_cfg, {k: pr.get(k) for k in admit.IDENT3}, bound, strict=True)]
            if len({admit.interp_key(d) for d in adm}) != 1:
                record(ck, pid, kn, pr, "record-only:no-single-admissible-graded", None); continue
            row = adm[-1]
            rr, tr = row.get("real_result") or {}, row.get("twin_result") or {}
            predicate = {"version": OC.VERSION, "kind": OC.KIND, "pair": pid, "task": pr.get("task"), "kernel": kn,
                         "flake": runmeta.get("flake", 3),
                         # provenance only -- the recorded worker-env-UPDATE value (None when that dict was empty).
                         # NOT authoritative: SPARK per-cell policy is bound at check from result_meta.extras.gnatprove_jobs
                         "spark_jobs": (int(env_spark_jobs) if env_spark_jobs is not None else None),
                         "witness": w, "witness_kind": pr.get("witness_kind"),
                         "real_program": real_t, "twin_program": twin_t, "contract_sha256": OC._contract_sha(real_t),
                         "observed": {"real_outcome": row["real_outcome"], "twin_outcome": row["twin_outcome"],
                                      "real_agreed": row["real_agreed"], "twin_agreed": row["twin_agreed"]},
                         "result_meta": {"real": rr, "twin": tr},   # FULL Results (backend/version/budget/wall_ms/error/extras/ok/exit/source_sha256)
                         "run_backed": {"eff_config_id": eff_cfg, "manifest_config_id": man["config_id"],
                                        "eff_config": eff_conf,          # recomputes to eff_config_id at check
                                        "base_config": man["config"],    # the FULL manifest config (flake_n/spark_prover/kernel versions/engine+harness source hashes); recomputes to manifest_config_id, so the replay's flake policy is hash-bound
                                        "run_real_src_sha256": si.get("real"), "run_twin_src_sha256": si.get("twin"),
                                        # concrete source-run provenance: names WHICH run (identical-config runs differ by checkpoint) + the exact record; retained reference, not a signature
                                        "run_ref": {"manifest_sha256": man_sha, "checkpoint_sha256": ckpt_sha,
                                                    "record_sha256": hashlib.sha256(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest()}},
                         "semantics": "run-backed observation; replay validates every run-backed binding field then re-lowers+re-runs and binds the run's lowered digests; NOT correctness"}
            cert = {"_type": OC.STATEMENT, "predicateType": OC.PREDICATE, "predicate": predicate,
                    "subject": [{"name": "real.t", "digest": {"sha256": OC._sha(real_t)}},
                                {"name": "twin.t", "digest": {"sha256": OC._sha(twin_t)}},
                                {"name": "witness", "digest": {"sha256": OC._sha(w)}}]}
            (cert_dir / f"{ck}.cert.json").write_text(json.dumps(cert, indent=1))
            counts["paired-observation"] += 1; index.append((ck, "paired-observation", row["twin_outcome"]))

    expected = len(man["pairs"]) * len(KERNELS)
    (cert_dir / "INDEX.json").write_text(json.dumps(
        {"run": run_dir.name,                              # public-safe by construction: basename only, no account home path
         "run_path_note": "absolute working path intentionally omitted for publication (AGENTS.md); the source run "
                          "is identified by the digests below, and raw artifacts are kept immutable elsewhere",
         "manifest_sha256": man_sha, "checkpoint_sha256": ckpt_sha,
         "eff_config_id": eff_cfg, "manifest_config_id": man["config_id"],
         "expected_cells": expected, "minted": len(index), "counts": counts, "entries": index}, indent=1))
    ok = len(index) == expected
    print(f"mint-run: {len(index)}/{expected} cells certified {counts} -> {cert_dir}  [{'complete' if ok else 'INCOMPLETE'}]")
    return 0 if ok else 2


def control():
    import tempfile
    import types
    import importlib
    g2 = importlib.import_module("e1_pairs_gate2")
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond))); print(f"  {name}: [{'ok' if cond else 'FAIL'}]")
    d = pathlib.Path(tempfile.mkdtemp()); pdir = d / "twins" / "pairs"; pdir.mkdir(parents=True); g2.PAIRS = pdir

    def mk(task, br, bt):
        prog = f"t 1\ntask {task}(n: int) returns (r: bool)\n  requires n >= 0\n  ensures r == (n >= 0)\n{{ {br} }}"
        twin = f"t 1\ntask {task}(n: int) returns (r: bool)\n  requires n >= 0\n  ensures r == (n >= 0)\n{{ {bt} }}"
        pid = hashlib.sha256((prog + "\0" + twin).encode()).hexdigest()[:16]
        f = pdir / f"{task}.{pid}.json"
        f.write_text(json.dumps({"id": pid, "task": task, "program": "```t\n" + prog + "\n```", "twin": "```t\n" + twin + "\n```",
            "witness": {"_kind": "value", "_ens": True, "n": 0}, "verified_by": KERNELS, "twin_refuted_by": KERNELS}))
        return pid, f
    pidA, fA = mk("pa", "r := true;", "r := false;"); pidB, fB = mk("pb", "r := true;", "r := false;")

    def probe():
        lower = lambda clean, body, witness=None: "// " + json.dumps(body)[:60] + "\n"
        return [("dafny", "d4.9"), ("verus", "v0.1")] + [(k, "ABSENT") for k in KERNELS[2:]], \
               [("dafny", lower, "dfy"), ("verus", lower, "rs")]
    # OC.check re-lowers via run_par.probe_backends; in this SYNTHETIC control the run lowered with the stub,
    # so make the replay use the SAME stub lowering (in a real run the engine lowering is identical both times).
    import run_par as _rp
    _rp.probe_backends = probe

    def grade(k, pid, rp, tp, flake):
        rs, ts = g2.sha_bytes(pathlib.Path(rp).read_bytes()), g2.sha_bytes(pathlib.Path(tp).read_bytes())
        R = lambda o, s: {"backend": k, "backend_version": "stub", "budget": "b", "wall_ms": 1, "source_sha256": s, "outcome": o, "ok": o == admit.VERIFIED}
        return {"id": pid, "kernel": k, "real": R(admit.VERIFIED, rs), "twin": R(admit.REFUTED, ts), "real_agreed": True, "twin_agreed": True}
    run_dir = d / "run"; NS = types.SimpleNamespace(out_dir=str(run_dir), flake=3, jobs=2, limit=0)
    g2.cmd_manifest(NS, _probe=probe); g2.cmd_run(NS, _probe=probe, _grade=grade)

    def vstub(path):
        t = pathlib.Path(path).read_text(); return (admit.REFUTED if "false" in t else admit.VERIFIED), True

    def mint(dst):
        return mint_run(run_dir, pdir, d / dst)
    # POSITIVE
    rc = mint("certs"); idx = json.loads((d / "certs" / "INDEX.json").read_text())
    ok("positive: cert for every cell (14); 4 graded + 10 record-only", idx["minted"] == 14 and idx["counts"]["paired-observation"] == 4 and idx["counts"]["record-only"] == 10)
    gc = next(c for c in (d / "certs").glob("*.cert.json") if json.loads(c.read_text())["predicate"]["kind"] == OC.KIND)
    cert = json.loads(gc.read_text())
    ok("graded cert carries result_meta + run_backed digests", cert["predicate"]["result_meta"]["real"]["backend_version"] == "stub" and cert["predicate"]["run_backed"]["run_real_src_sha256"])
    ok("graded cert replays reproduced (with run_backed binding ok)", OC.check(cert, verify_override=vstub)["verdict"] == OC.REPRODUCED)
    # (5) run_backed tamper -> OC.check now FAILS (binding is actually validated)
    tb = json.loads(gc.read_text()); tb["predicate"]["run_backed"]["run_real_src_sha256"] = "a" * 64
    ok("run_backed source-sha tamper -> replay FAILED", OC.check(tb, verify_override=vstub)["verdict"] == OC.FAILED)
    # each run-backed binding field tampered INDEPENDENTLY must FAIL (fail-closed, before the prover)
    import copy as _copy

    def _t(mut):
        c = _copy.deepcopy(cert); mut(c); return OC.check(c, verify_override=vstub)["verdict"]
    ok("eff_config_id-only tamper -> FAILED", _t(lambda c: c["predicate"]["run_backed"].__setitem__("eff_config_id", "zzzz00000000")) == OC.FAILED)
    ok("manifest_config_id-only tamper -> FAILED", _t(lambda c: c["predicate"]["run_backed"].__setitem__("manifest_config_id", "zzzz00000000")) == OC.FAILED)
    ok("delete BOTH run source hashes -> FAILED", _t(lambda c: [c["predicate"]["run_backed"].pop("run_real_src_sha256"), c["predicate"]["run_backed"].pop("run_twin_src_sha256")]) == OC.FAILED)
    ok("result_meta backend dafny->rocq -> FAILED", _t(lambda c: c["predicate"]["result_meta"]["real"].__setitem__("backend", "rocq")) == OC.FAILED)
    ok("eff_config content edit (id no longer recomputes) -> FAILED", _t(lambda c: c["predicate"]["run_backed"]["eff_config"].__setitem__("jobs", 999)) == OC.FAILED)
    # consistency chain (cheap, pre-prover): these REPRODUCED before base_config + policy + internal-consistency
    ok("result_meta.real.outcome contradiction (refuted vs observed verified) -> FAILED",
       _t(lambda c: c["predicate"]["result_meta"]["real"].__setitem__("outcome", admit.REFUTED)) == OC.FAILED)
    ok("result_meta.real.source_sha256 tamper -> FAILED",
       _t(lambda c: c["predicate"]["result_meta"]["real"].__setitem__("source_sha256", "b" * 64)) == OC.FAILED)
    ok("top-level flake 3->1 (base_config hash-bound to flake_n=3) -> FAILED",
       _t(lambda c: c["predicate"].__setitem__("flake", 1)) == OC.FAILED)
    # SPARK per-cell policy is bound from result_meta.extras.gnatprove_jobs (tested natively on a real SPARK
    # cell), NOT the top-level provenance spark_jobs field. Editing it alone on a NON-spark cell is not a binding.
    ok("top-level spark_jobs edit on non-spark cell -> still reproduces (provenance, not the binding)",
       _t(lambda c: c["predicate"].__setitem__("spark_jobs", 99)) == OC.REPRODUCED)
    ok("base_config content edit (flake_n 3->1; id no longer recomputes) -> FAILED",
       _t(lambda c: c["predicate"]["run_backed"]["base_config"].__setitem__("flake_n", 1)) == OC.FAILED)
    ok("missing base_config -> FAILED", _t(lambda c: c["predicate"]["run_backed"].pop("base_config")) == OC.FAILED)
    # a PRESENT-but-malformed run_backed block fails STRUCTURALLY (never silent ad-hoc, never AttributeError)
    ok("run_backed present but null -> structural FAILED", _t(lambda c: c["predicate"].__setitem__("run_backed", None)) == OC.FAILED)
    ok("run_backed present but [] -> structural FAILED", _t(lambda c: c["predicate"].__setitem__("run_backed", [])) == OC.FAILED)
    ok("run_backed present but 42 -> structural FAILED", _t(lambda c: c["predicate"].__setitem__("run_backed", 42)) == OC.FAILED)
    # a genuinely ad-hoc cert (run_backed KEY ABSENT) still replays, with narrower scope reported
    ok("run_backed KEY ABSENT -> ad-hoc still reproduces (narrower scope)",
       _t(lambda c: c["predicate"].pop("run_backed")) == OC.REPRODUCED)
    # record-only native check -> UNDECIDED (identity verified), NOT generic reject, NOT success
    ro = next(c for c in (d / "certs").glob("*.cert.json") if json.loads(c.read_text())["predicate"]["kind"] == OC.RECORD_KIND)
    rr = OC.check_record(json.loads(ro.read_text()))
    ok("record-only native check -> UNDECIDED with reason + identity ok", rr["verdict"] == OC.UNDECIDED and "proved here" not in OC.render(rr))

    # (1) witness tamper in the archived pair AFTER the run -> graded cell becomes record-only (identity mismatch)
    rA = json.loads(fA.read_text()); rA["witness"] = {"_kind": "value", "_ens": True, "n": 7}; fA.write_text(json.dumps(rA))
    mint("c1"); e1 = {ck: st for ck, kind, st in json.loads((d / "c1" / "INDEX.json").read_text())["entries"]}
    ok("witness tamper -> archived-identity-mismatch record-only", e1.get(f"{pidA}|dafny") == "record-only:archived-identity-mismatch")
    rA["witness"] = {"_kind": "value", "_ens": True, "n": 0}; fA.write_text(json.dumps(rA))
    # (2) corrupt a retained source file -> aggregator marks source-bytes -> record-only (not paired-observation)
    si = json.loads((run_dir / json.loads((run_dir / "E1PAIRS2-RUNMETA.json").read_text())["src_index"]).read_text())
    anyck = next(k for k in si); sfx = si[anyck]["suffix"]
    sp = run_dir / "src" / f"{si[anyck]['real']}.{sfx}"; saved = sp.read_bytes(); sp.write_bytes(saved + b"// tamper\n")
    mint("c2"); e2 = {ck: st for ck, kind, st in json.loads((d / "c2" / "INDEX.json").read_text())["entries"]}
    ok("source-byte corrupt -> record-only:invalid:source-bytes", e2.get(anyck, "").startswith("record-only:invalid:source-bytes"))
    sp.write_bytes(saved)
    # (3) resolution/row disagreement -> record-only (not a verified paired-observation)
    rmp = run_dir / "E1PAIRS2-RUNMETA.json"; resname = json.loads(rmp.read_text())["resolution"]; resp = run_dir / resname
    res = json.loads(resp.read_text()); good_res = resp.read_text()
    gck = next(ck for ck in res if res[ck].get("state") == "graded"); res[gck]["real_outcome"] = admit.REFUTED; resp.write_text(json.dumps(res))
    mint("c3"); e3 = {ck: st for ck, kind, st in json.loads((d / "c3" / "INDEX.json").read_text())["entries"]}
    ok("resolution/row disagreement -> record-only (not graded)", e3.get(gck, "").startswith("record-only:"))
    resp.write_text(good_res)
    # (4) chain tamper (runmeta.config_id) -> mint-run refuses (exit 3), reusing the aggregator's chain check
    good_rm = rmp.read_text(); rm = json.loads(good_rm); rm["config_id"] = "deadbeef0000"; rmp.write_text(json.dumps(rm))
    ok("chain tamper (runmeta.config_id) -> mint-run refuses (exit 3)", mint("c4") == 3)
    rmp.write_text(good_rm)

    allok = all(c for _, c in checks); print("BATCH-CERT-CONTROL " + ("PASS" if allok else "FAIL")); return 0 if allok else 1


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "control":
        return control()
    if len(sys.argv) >= 5 and sys.argv[1] == "mint-run":
        return mint_run(sys.argv[2], sys.argv[3], sys.argv[4])
    print("usage: e1_batch_cert.py mint-run <v2-run-dir> <pairs-dir> <cert-dir> | control"); return 2


if __name__ == "__main__":
    sys.exit(main())
