#!/usr/bin/env python3
"""Independent STRUCTURAL validator for an authoritative v2 paired run.

Deliberately NOT a wrapper around e1_pairs_aggregate: it re-opens the frozen run and re-checks the chain with
its own code, so it is a SEPARATE validator of the input/source/Result/resolution integrity, not a re-execution
of the aggregator. It is NOT a replay (it runs no kernel); replay reproduction is the certificates' job.

The checkpoint append-log may hold rows from MORE THAN ONE eff_config (an earlier SMOKE config + the FULL run).
Only rows whose eff_config_id == runmeta.eff_config_id belong to THIS run. The RESOLUTION map is the
authoritative CURRENT per-cell state: a cell counts as graded only where resolution says "graded"; a graded log
row under a non-graded typed current state, or a resolution-graded cell with no backing log row, is a
disagreement, not a silent vote.

Checks for the current run:
  * config_id == sha1(json(man.config))[:12] == runmeta.config_id; runmeta.config EQUALS manifest.config and
    hashes to runmeta.config_id; eff_config recomputes to eff_config_id; eff.base == config_id
  * every expected cell is graded-by-resolution, backed by EXACTLY ONE current-eff graded row (no missing/
    duplicate/unexpected/one-sided); rows under another eff are counted separately, never merged
  * the ORIGINAL archived payloads (twins/pairs/*.json) re-hash to the manifest program/twin/witness digests,
    AND the parsed non-body CONTRACT re-hashes to the manifest contract with real==twin (as the cert path does)
  * real/twin source_sha256 agree across row, src-index and resolution, AND the RETAINED lowered-source bytes
    re-hash to those digests (byte re-hash; cached by (digest,suffix); 4295 unique / 5964 refs)
  * backend == the cell's kernel; outcome + boolean stability flags agree across row and resolution
Reported findings (NOT integrity gates): the coverage curve and the stable-VERIFIED-twin count are scientific
results; a valid unexpected outcome is data, never malformed input.

Output is public-safe: run basename + digests only, never an absolute path.

    python3 -I e1_structural_validator.py <run-dir> <out.json> [pairs-dir]
"""
import collections
import hashlib
import json
import pathlib
import sys

# locate the engine dir (holding surface.py): internal/ may sit under t/ (lab layout) or at the repo root
# with t/ a sibling (published layout) -- append whichever candidate actually has the engine.
_here = pathlib.Path(__file__).resolve()
for _cand in (_here.parent.parent, _here.parent.parent / "t", _here.parent / "t"):
    if (_cand / "surface.py").exists():
        sys.path.append(str(_cand)); break
import surface  # noqa: E402


def _sha1_12(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:12]


def _unfence(s):
    s = (s or "").strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()


def _sha(text):                                 # matches obs_certificate._sha / the manifest canon()
    s = text if isinstance(text, str) else json.dumps(text, sort_keys=True, default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _contract_sha(t):                           # the non-body contract hash, exactly as the certificate path
    task = surface.parse(t)
    contract = {k: v for k, v in task.items() if k != "body" and not k.startswith("_")}
    return hashlib.sha256(json.dumps(contract, sort_keys=True, default=str).encode()).hexdigest()


def validate(run_dir, pairs_dir=None):
    run_dir = pathlib.Path(run_dir)
    pairs_dir = pathlib.Path(pairs_dir) if pairs_dir else (run_dir.parent.parent / "twins" / "pairs")
    man = json.loads((run_dir / "E1PAIRS2-MAN.json").read_bytes())
    rm = json.loads((run_dir / "E1PAIRS2-RUNMETA.json").read_bytes())
    man_sha = hashlib.sha256((run_dir / "E1PAIRS2-MAN.json").read_bytes()).hexdigest()
    ckpt_bytes = (run_dir / "E1PAIRS2.jsonl").read_bytes()
    ckpt_sha = hashlib.sha256(ckpt_bytes).hexdigest()
    cur_eff = rm["eff_config_id"]
    fail = []

    def need(cond, msg):
        if not cond:
            fail.append(msg)
        return cond

    kernels = man["kernels"]
    pairs = man["pairs"]
    keyset = {(x if isinstance(x, str) else f"{x[0]}|{x[1]}") for x in man["keyset"]}
    expected = {f"{pid}|{k}" for pid in pairs for k in kernels}
    need(keyset == expected, "keyset != pairs x kernels")
    need(_sha1_12(man["config"]) == man["config_id"] == rm["config_id"], "config_id != sha1(manifest.config)")
    need(rm.get("config") == man["config"], "runmeta.config != manifest.config")
    need(_sha1_12(rm.get("config")) == rm["config_id"], "runmeta.config does not hash to runmeta.config_id")
    eff = rm["eff_config"]
    need(_sha1_12(eff) == cur_eff, "eff_config_id != sha1(eff_config)")
    need(eff.get("base") == man["config_id"], "eff_config.base != config_id")

    src_index = json.loads((run_dir / rm["src_index"]).read_bytes())
    resolution = json.loads((run_dir / rm["resolution"]).read_bytes())
    srcdir = run_dir / "src"

    # (A) ORIGINAL archived payloads re-hash to manifest identity digests AND the parsed CONTRACT re-hashes
    payload = {}
    for p in pairs_dir.glob("*.json"):
        r = json.loads(p.read_bytes())
        payload[r["id"]] = (_unfence(r["program"]), _unfence(r["twin"]), r.get("witness"))
    payload_missing, payload_bad, contract_bad = [], [], []
    for pid, pr in pairs.items():
        t = payload.get(pid)
        if t is None:
            payload_missing.append(pid); continue
        rt, tt, w = t
        if not (_sha(rt) == pr.get("program_sha256") and _sha(tt) == pr.get("twin_sha256")
                and _sha(w) == pr.get("witness_sha256")):
            payload_bad.append(pid)
        try:
            cr, ct = _contract_sha(rt), _contract_sha(tt)
        except Exception:  # noqa: BLE001
            contract_bad.append(pid); continue
        if not (cr == pr.get("contract_sha256") and cr == ct and pr.get("twin_contract_sha256") in (None, ct)):
            contract_bad.append(pid)

    # (B) retained lowered-source bytes re-hash to the src-index digests; cache by (digest,suffix)
    rehashed, refs_ok, refs_bad = {}, 0, []
    for ck, si in src_index.items():
        for side in ("real", "twin"):
            key = (si[side], si["suffix"])
            if key not in rehashed:
                f = srcdir / f"{key[0]}.{key[1]}"
                rehashed[key] = f.is_file() and hashlib.sha256(f.read_bytes()).hexdigest() == key[0]
            if rehashed[key]:
                refs_ok += 1
            else:
                refs_bad.append(f"{ck}:{side}")

    # (C) group graded rows BY eff_config_id; the RESOLUTION is the authoritative current state
    cur_rows = collections.defaultdict(list)
    out_of_config = collections.Counter()
    unexpected = []
    for ln in ckpt_bytes.decode().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        d = json.loads(ln)
        if d.get("state") != "graded":
            continue
        if d.get("eff_config_id") != cur_eff:
            out_of_config[str(d.get("eff_config_id"))] += 1
            continue
        ck = f"{d.get('id')}|{d.get('kernel')}"
        if ck not in keyset:
            unexpected.append(ck); continue
        cur_rows[ck].append(d)
    dup_cells = sorted(ck for ck, v in cur_rows.items() if len(v) > 1)
    log_graded = set(cur_rows)
    res_graded = {ck for ck in keyset if resolution.get(ck, {}).get("state") == "graded"}
    res_graded_no_log = sorted(res_graded - log_graded)      # resolution says graded, no backing current-eff row
    log_graded_res_not = sorted(log_graded - res_graded)     # log row graded, but typed current state is NOT graded
    graded = {ck: cur_rows[ck][0] for ck in (res_graded & log_graded)}
    missing = sorted(keyset - res_graded)                    # cells not marked graded by the authoritative resolution

    ident_echo_bad, src_bad, backend_bad, outcome_bad, res_eff_bad, malformed_flags = [], [], [], [], [], []
    for ck, d in graded.items():
        pid, kn = ck.split("|", 1)
        pr, si, rs = pairs[pid], src_index.get(ck, {}), resolution.get(ck, {})
        if rs.get("eff_config_id") != cur_eff:
            res_eff_bad.append(ck)
        if not (d.get("program_sha256") == pr.get("program_sha256") and d.get("twin_sha256") == pr.get("twin_sha256")
                and d.get("witness_sha256") == pr.get("witness_sha256")):
            ident_echo_bad.append(ck)
        rr, tr = d.get("real_result") or {}, d.get("twin_result") or {}
        if not (rr.get("source_sha256") == d.get("real_src_sha256") == si.get("real") == rs.get("real_src_sha256")
                and tr.get("source_sha256") == d.get("twin_src_sha256") == si.get("twin") == rs.get("twin_src_sha256")):
            src_bad.append(ck)
        if rr.get("backend") != kn or tr.get("backend") != kn:
            backend_bad.append(ck)
        flags = [d.get("real_agreed"), d.get("twin_agreed"), rs.get("real_agreed"), rs.get("twin_agreed")]
        if not all(isinstance(fl, bool) for fl in flags):
            malformed_flags.append(ck)
        elif not (d.get("real_outcome") == rr.get("outcome") == rs.get("real_outcome")
                  and d.get("twin_outcome") == tr.get("outcome") == rs.get("twin_outcome")
                  and d.get("real_agreed") == rs.get("real_agreed") and d.get("twin_agreed") == rs.get("twin_agreed")):
            outcome_bad.append(ck)

    need(not missing, f"{len(missing)} cells not graded by the resolution")
    need(not dup_cells, f"{len(dup_cells)} DUPLICATE graded cells at current eff")
    need(not unexpected, f"{len(unexpected)} unexpected cells at current eff")
    need(not res_graded_no_log, f"{len(res_graded_no_log)} resolution-graded cells with no backing current-eff log row")
    need(not log_graded_res_not, f"{len(log_graded_res_not)} graded log rows whose current resolution is NOT graded")
    need(not payload_missing, f"{len(payload_missing)} archived payloads missing")
    need(not payload_bad, f"{len(payload_bad)} archived-payload identity re-hash mismatches vs manifest")
    need(not contract_bad, f"{len(contract_bad)} archived-payload contract re-hash / real==twin mismatches")
    need(not refs_bad, f"{len(refs_bad)} lowered-source byte re-hash mismatches")
    need(not ident_echo_bad, f"{len(ident_echo_bad)} row identity echoes != manifest")
    need(not src_bad, f"{len(src_bad)} source-hash cross-field disagreements")
    need(not backend_bad, f"{len(backend_bad)} backend!=kernel")
    need(not outcome_bad, f"{len(outcome_bad)} outcome/stability disagreements")
    need(not res_eff_bad, f"{len(res_eff_bad)} resolution rows at a different eff")
    need(not malformed_flags, f"{len(malformed_flags)} rows/resolutions with non-boolean agreement flags")

    # FINDINGS (scientific results, not integrity gates): curve + stable-VERIFIED-twin count
    per_pair_conj, twin_states, stable_verified_twins = [], {}, 0
    for pid in pairs:
        conj = 0
        for kn in kernels:
            d = graded.get(f"{pid}|{kn}")
            if not d:
                continue
            ro, to = d.get("real_outcome"), d.get("twin_outcome")
            ra, ta = d.get("real_agreed") is True, d.get("twin_agreed") is True   # strict; never coerce "false"
            twin_states[to] = twin_states.get(to, 0) + 1
            if to == "verified" and ta:
                stable_verified_twins += 1
            if ro == "verified" and to == "refuted" and ra and ta:
                conj += 1
        per_pair_conj.append(conj)
    n_pairs = len(pairs)
    curve = [{"k": k, "pairs_ge_k": sum(1 for c in per_pair_conj if c >= k),
              "pct": round(100.0 * sum(1 for c in per_pair_conj if c >= k) / n_pairs, 1)} for k in range(1, 8)]

    return {
        "validator": "e1_structural_validator (independent of e1_pairs_aggregate; structural, not a replay)",
        "run": run_dir.name, "manifest_sha256": man_sha, "checkpoint_sha256": ckpt_sha,
        "config_id": man["config_id"], "eff_config_id": cur_eff,
        "n_pairs": n_pairs, "kernels": kernels, "expected_cells": len(expected),
        "resolution_graded_cells": len(res_graded), "graded_backed_cells": len(graded),
        "missing": len(missing), "unexpected": len(unexpected), "duplicate_cells_current_eff": len(dup_cells),
        "resolution_graded_no_log": len(res_graded_no_log), "log_graded_resolution_not": len(log_graded_res_not),
        "out_of_config_rows": dict(out_of_config),
        "out_of_config_note": "graded rows under a different eff_config_id (e.g. an earlier SMOKE config); counted "
                              "separately, never merged into the current full-config run.",
        "archived_payloads_rehashed": len(pairs) - len(payload_missing), "archived_payload_mismatches": len(payload_bad),
        "contract_rehash_mismatches": len(contract_bad),
        "unique_source_files_rehashed": len(rehashed), "source_side_references": refs_ok,
        "source_rehash_mismatches": len(refs_bad),
        "row_identity_echo_mismatches": len(ident_echo_bad), "source_hash_disagreements": len(src_bad),
        "backend_mismatches": len(backend_bad), "outcome_stability_disagreements": len(outcome_bad),
        "resolution_eff_mismatches": len(res_eff_bad), "malformed_agreement_flags": len(malformed_flags),
        "finding_twin_states": twin_states, "finding_stable_verified_twins": stable_verified_twins,
        "finding_curve_same_kernel_conjunction": curve,
        "FAIL": fail, "PASS": not fail,
    }


def main():
    rep = validate(sys.argv[1], sys.argv[3] if len(sys.argv) > 3 else None)
    outp = pathlib.Path(sys.argv[2])
    outp.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(f"structural validation of run '{rep['run']}': {'PASS' if rep['PASS'] else 'FAIL ' + str(rep['FAIL'])}")
    print(f"  resolution-graded {rep['resolution_graded_cells']} backed {rep['graded_backed_cells']}/"
          f"{rep['expected_cells']}  missing/dup/unexpected {rep['missing']}/{rep['duplicate_cells_current_eff']}/"
          f"{rep['unexpected']}  res-no-log/log-not-res {rep['resolution_graded_no_log']}/"
          f"{rep['log_graded_resolution_not']}  out-of-config {rep['out_of_config_rows']}")
    print(f"  payload rehash mismatches {rep['archived_payload_mismatches']} contract {rep['contract_rehash_mismatches']}"
          f"  |  lowered-source {rep['unique_source_files_rehashed']} unique / {rep['source_side_references']} refs "
          f"(mismatches {rep['source_rehash_mismatches']})")
    print(f"  FINDING stable-VERIFIED-twins {rep['finding_stable_verified_twins']}  curve "
          + " ".join(f"k{c['k']}={c['pairs_ge_k']}" for c in rep["finding_curve_same_kernel_conjunction"]))
    print(f"  wrote {outp}")
    return 0 if rep["PASS"] else 1


if __name__ == "__main__":
    sys.exit(main())
