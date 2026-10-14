#!/usr/bin/env python3
"""Executable controls for e1_structural_validator: a VALID minimal run must PASS; each crafted integrity
defect must FAIL; and a valid-but-unexpected scientific outcome (VERIFIED twins) must PASS with the finding
recorded (integrity is separate from the finding count). Mirrors the independent reproducer's cases.

    python3 -I e1_structural_validator_controls.py
"""
import copy
import hashlib
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import e1_structural_validator as V  # noqa: E402

EFF = "d6a55f7a691e"
KERNELS = ["dafny", "verus"]


def _sha1_12(o):
    return hashlib.sha1(json.dumps(o, sort_keys=True).encode()).hexdigest()[:12]


def build(root):
    root = pathlib.Path(root)
    run = root / "run"; (run / "src").mkdir(parents=True)
    pairs_dir = root / "pairs"; pairs_dir.mkdir()
    config = {"flake_n": 3, "spark_prover": None, "engine_pin": "deadbeef0000", "kernels": {k: "v1" for k in KERNELS}}
    cfg = _sha1_12(config)
    eff_config = {"base": cfg, "jobs": 2, "spark_env": {"T_SPARK_JOBS": "1"}, "available": KERNELS}
    eff = _sha1_12(eff_config)
    assert eff == EFF or True   # eff id is whatever this config hashes to; the validator recomputes it
    eff = _sha1_12(eff_config)
    pairs, keyset, src_index, resolution, rows = {}, [], {}, {}, []
    for pi, task in enumerate(["pa", "pb"]):
        prog = f"t 1\ntask {task}(n: int) returns (r: bool)\n  requires n >= 0\n  ensures r == (n >= 0)\n{{ r := true; }}"
        twin = prog.replace("r := true;", "r := false;")
        w = {"_kind": "value", "_ens": True, "n": 0}
        pid = hashlib.sha256((prog + "\0" + twin).encode()).hexdigest()[:16]
        (pairs_dir / f"{task}.{pid}.json").write_text(json.dumps(
            {"id": pid, "task": task, "program": "```t\n" + prog + "\n```", "twin": "```t\n" + twin + "\n```", "witness": w}))
        pairs[pid] = {"id": pid, "task": task, "program_sha256": V._sha(prog), "twin_sha256": V._sha(twin),
                      "witness_sha256": V._sha(w), "contract_sha256": V._contract_sha(prog),
                      "twin_contract_sha256": V._contract_sha(twin), "witness_kind": "value"}
        for kn in KERNELS:
            ck = f"{pid}|{kn}"; keyset.append([pid, kn]); sfx = {"dafny": "dfy", "verus": "rs"}[kn]
            rbody = f"// real {ck}".encode(); tbody = f"// twin {ck}".encode()
            rh = hashlib.sha256(rbody).hexdigest(); th = hashlib.sha256(tbody).hexdigest()
            (run / "src" / f"{rh}.{sfx}").write_bytes(rbody); (run / "src" / f"{th}.{sfx}").write_bytes(tbody)
            src_index[ck] = {"real": rh, "twin": th, "suffix": sfx}

            def R(b, s, o):
                return {"backend": b, "backend_version": "v1", "source_sha256": s, "outcome": o,
                        "ok": o == "verified", "budget": "bud", "wall_ms": 1, "extras": {}}
            resolution[ck] = {"state": "graded", "real_outcome": "verified", "twin_outcome": "refuted",
                              "real_agreed": True, "twin_agreed": True, "real_src_sha256": rh, "twin_src_sha256": th,
                              "suffix": sfx, "witness_kind": "value", "eff_config_id": eff}
            rows.append({"id": pid, "kernel": kn, "state": "graded", "eff_config_id": eff,
                         "program_sha256": V._sha(prog), "twin_sha256": V._sha(twin), "witness_sha256": V._sha(w),
                         "real_src_sha256": rh, "twin_src_sha256": th, "suffix": sfx,
                         "real_outcome": "verified", "twin_outcome": "refuted", "real_agreed": True, "twin_agreed": True,
                         "witness_kind": "value", "real_result": R(kn, rh, "verified"), "twin_result": R(kn, th, "refuted")})
    man = {"version": "e1_pairs_gate2", "config_id": cfg, "config": config, "kernels": KERNELS, "keyset": keyset,
           "n_pairs": len(pairs), "pairs": pairs, "expected_cells": len(keyset), "witness_kinds": ["value"]}
    rm = {"config_id": cfg, "eff_config_id": eff, "eff_config": eff_config, "config": config, "jobs": 2, "flake": 3,
          "spark_env": {"T_SPARK_JOBS": "1"}, "src_index": f"SI.{eff}.json", "resolution": f"RES.{eff}.json"}
    (run / "E1PAIRS2-MAN.json").write_text(json.dumps(man))
    (run / "E1PAIRS2-RUNMETA.json").write_text(json.dumps(rm))
    (run / f"SI.{eff}.json").write_text(json.dumps(src_index))
    (run / f"RES.{eff}.json").write_text(json.dumps(resolution))
    (run / "E1PAIRS2.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return run, pairs_dir, eff


def main():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond))); print(f"  {name}: [{'ok' if cond else 'FAIL'}]")

    def rewrite_rows(run, mutate):
        rows = [json.loads(l) for l in (run / "E1PAIRS2.jsonl").read_text().splitlines() if l.strip()]
        mutate(rows)
        (run / "E1PAIRS2.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    def res_path(run):
        rm = json.loads((run / "E1PAIRS2-RUNMETA.json").read_text()); return run / rm["resolution"]

    base = tempfile.mkdtemp()
    run, pdir, eff = build(base)
    rep = V.validate(run, pdir)
    ok("VALID minimal run -> PASS", rep["PASS"])
    ok("  curve k1 == n_pairs (all cells conj)", rep["finding_curve_same_kernel_conjunction"][0]["pairs_ge_k"] == rep["n_pairs"])

    # distinct-config history: add 2 graded rows under a DIFFERENT eff -> still PASS, counted out-of-config
    d = tempfile.mkdtemp(); run, pdir, eff = build(d)
    rewrite_rows(run, lambda rows: rows.extend([{**copy.deepcopy(rows[0]), "eff_config_id": "0000smoke0000"}]))
    rep = V.validate(run, pdir)
    ok("distinct-config history row -> PASS + counted out-of-config", rep["PASS"] and rep["out_of_config_rows"].get("0000smoke0000") == 1)

    # (1) conflicting SAME-eff duplicate row (resolution backs the other) -> FAIL
    d = tempfile.mkdtemp(); run, pdir, eff = build(d)
    rewrite_rows(run, lambda rows: rows.append({**copy.deepcopy(rows[0]), "twin_outcome": "verified"}))
    ok("(1) conflicting same-eff duplicate -> FAIL", not V.validate(run, pdir)["PASS"])

    # (5) same-eff EXACT duplicate -> FAIL
    d = tempfile.mkdtemp(); run, pdir, eff = build(d)
    rewrite_rows(run, lambda rows: rows.append(copy.deepcopy(rows[0])))
    ok("(5) same-eff exact duplicate -> FAIL", not V.validate(run, pdir)["PASS"])

    # (2) resolution with the WRONG eff id -> FAIL
    d = tempfile.mkdtemp(); run, pdir, eff = build(d)
    res = json.loads(res_path(run).read_text()); next(iter(res.values()))["eff_config_id"] = "wrongeff0000"
    res_path(run).write_text(json.dumps(res))
    ok("(2) resolution wrong eff id -> FAIL", not V.validate(run, pdir)["PASS"])

    # (3) agreement flags are the STRING "false" -> FAIL (malformed), never coerced to stable
    d = tempfile.mkdtemp(); run, pdir, eff = build(d)
    rewrite_rows(run, lambda rows: [r.__setitem__("real_agreed", "false") or r.__setitem__("twin_agreed", "false") for r in rows])
    res = json.loads(res_path(run).read_text())
    for v in res.values():
        v["real_agreed"] = "false"; v["twin_agreed"] = "false"
    res_path(run).write_text(json.dumps(res))
    rep = V.validate(run, pdir)
    ok("(3) string 'false' flags -> FAIL (malformed) and curve not counted",
       (not rep["PASS"]) and rep["finding_curve_same_kernel_conjunction"][6]["pairs_ge_k"] == 0)

    # (4) a required source path missing, but another suffix carries the same digest -> FAIL (byte re-hash)
    d = tempfile.mkdtemp(); run, pdir, eff = build(d)
    si = json.loads((run / f"SI.{eff}.json").read_text())
    ck0 = next(iter(si)); real_dig = si[ck0]["real"]; sfx = si[ck0]["suffix"]
    (run / "src" / f"{real_dig}.{sfx}").unlink()                       # remove the needed path
    (run / "src" / f"{real_dig}.other").write_bytes(f"// real {ck0}".encode())  # same digest, different suffix
    ok("(4) missing source path (same digest other suffix) -> FAIL", not V.validate(run, pdir)["PASS"])

    # (6) structurally consistent data with VERIFIED twins -> PASS + finding records them (NOT an integrity fail)
    d = tempfile.mkdtemp(); run, pdir, eff = build(d)

    def to_verified(rows):
        for r in rows:
            r["twin_outcome"] = "verified"; r["twin_result"]["outcome"] = "verified"; r["twin_result"]["ok"] = True
    rewrite_rows(run, to_verified)
    res = json.loads(res_path(run).read_text())
    for v in res.values():
        v["twin_outcome"] = "verified"
    res_path(run).write_text(json.dumps(res))
    rep = V.validate(run, pdir)
    ok("(6) VERIFIED twins -> PASS (integrity) + finding records them",
       rep["PASS"] and rep["finding_stable_verified_twins"] == len(KERNELS) * rep["n_pairs"])

    # (7) current resolution typed non-graded while a graded log row remains -> FAIL (typed current state wins)
    d = tempfile.mkdtemp(); run, pdir, eff = build(d)
    res = json.loads(res_path(run).read_text()); next(iter(res.values()))["state"] = "unverified:input-drift"
    res_path(run).write_text(json.dumps(res))
    ok("(7) resolution.state unverified while log graded -> FAIL", not V.validate(run, pdir)["PASS"])

    # (8) manifest pair contract_sha256 tampered -> FAIL (contract is re-hashed from the parsed payload)
    d = tempfile.mkdtemp(); run, pdir, eff = build(d)
    man = json.loads((run / "E1PAIRS2-MAN.json").read_text())
    man["pairs"][next(iter(man["pairs"]))]["contract_sha256"] = "f" * 64
    (run / "E1PAIRS2-MAN.json").write_text(json.dumps(man))
    ok("(8) manifest contract_sha256 tamper -> FAIL", not V.validate(run, pdir)["PASS"])

    # (9) runmeta.config payload tampered while config_id/eff unchanged -> FAIL (config validated, not just the id)
    d = tempfile.mkdtemp(); run, pdir, eff = build(d)
    rm = json.loads((run / "E1PAIRS2-RUNMETA.json").read_text()); rm["config"]["flake_n"] = 99
    (run / "E1PAIRS2-RUNMETA.json").write_text(json.dumps(rm))
    ok("(9) runmeta.config.flake_n=99 (ids unchanged) -> FAIL", not V.validate(run, pdir)["PASS"])

    allok = all(c for _, c in checks)
    print("STRUCTURAL-VALIDATOR-CONTROLS " + ("PASS" if allok else "FAIL"))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
