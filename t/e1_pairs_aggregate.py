#!/usr/bin/env python3
"""Aggregate the paired twin-gate run into the E1 coverage-versus-accuracy curve. Admission is the SHARED
e1_admit policy, identical to the gate's resume/completeness, so one row is never counted two ways.

k = SAME-KERNEL CONJUNCTION (a kernel verifies the real AND refutes the twin, both stably). NOT T_MIN_KERNELS;
the across-halves count is a labelled DIAGNOSTIC only. STABILITY is a refusal; VACUOUS/TIMEOUT/UNPROVED are
unverifiable observations, never verdicts; conflicting admissible rows are QUARANTINED.

Modes:
  * v2 (authoritative, --manifest MAN.json [--runmeta RUNMETA.json]): ground truth, ids and the keyset come
    EXCLUSIVELY from the frozen manifest (never live twins/pairs). A row is admissible only via
    e1_admit.graded_admissible(strict): eff_config match (from RUNMETA, required), ALL frozen identity hashes
    present AND matching, and each Result's source_sha256 equal to the row's recorded lowered source. A
    --manifest that is missing or malformed FAILS (no silent fallback).
  * v1 (no --manifest): the preserved raw run has no identity binding, reported EXPLICITLY as UNVALIDATED;
    only the stability + conflict refusals apply. Ground truth from live twins/pairs.

    python3 -I e1_pairs_aggregate.py <checkpoint.jsonl> [out.json] --manifest MAN.json [--runmeta RM.json]
    python3 -I e1_pairs_aggregate.py <checkpoint.jsonl> [out.json]            # v1 UNVALIDATED
    python3 -I e1_pairs_aggregate.py control
"""
import json
import os
import sys
import hashlib
import collections
import pathlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I/-P drops the script dir; sibling import needs it
import e1_admit as admit

KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
PAIRS = pathlib.Path("twins/pairs")
V, R = admit.VERIFIED, admit.REFUTED


def gt_from_manifest(man):
    return {pid: {"witness_kind": p.get("witness_kind"),
                  "archived_verified_by": set(p.get("archived_verified_by") or []),
                  "archived_twin_refuted_by": set(p.get("archived_twin_refuted_by") or [])}
            for pid, p in man["pairs"].items()}


def gt_from_live():
    gt = {}
    for p in PAIRS.glob("*.json"):
        r = json.loads(p.read_text())
        gt[r["id"]] = {"witness_kind": (r.get("witness") or {}).get("_kind"),
                       "archived_verified_by": set(r.get("verified_by") or []),
                       "archived_twin_refuted_by": set(r.get("twin_refuted_by") or [])}
    return gt


def build_cells(recs, man, eff_cfg):
    strict = man is not None
    if not strict:
        # raw v1 legacy rows carry no 'state' field (they predate it) and were all graded. Normalize the
        # legacy shape ONLY inside the explicitly-UNVALIDATED v1 path -- never rewrite artifacts, never relax v2.
        recs = [({**d, "state": "graded"} if ("state" not in d and "real_outcome" in d) else d) for d in recs]
    pairs = man["pairs"] if man else {}
    by = collections.defaultdict(list)
    for d in recs:
        by[(d.get("id"), d.get("kernel"))].append(d)
    cells, stats = {}, collections.Counter()
    for key, rows in by.items():
        pid = key[0]
        pair_ident = {k: pairs[pid].get(k) for k in admit.IDENT3} if (strict and pid in pairs) else None
        adm = []
        for d in rows:
            bs = {"real_src_sha256": d.get("real_src_sha256"), "twin_src_sha256": d.get("twin_src_sha256")}
            if admit.graded_admissible(d, eff_cfg, pair_ident, bs, strict=strict):
                adm.append(d)
        if not adm:
            cells[key] = {"state": "not-admissible"}; stats["not-admissible"] += 1; continue
        if len({admit.interp_key(d) for d in adm}) > 1:
            cells[key] = {"state": "conflict"}; stats["conflict"] += 1; continue
        it = admit.interpret(adm[-1])
        cells[key] = {"state": "graded", "real": it["real"], "twin": it["twin"]}; stats["graded"] += 1
    return cells, stats


def build_cells_v2(run_dir, man, runmeta, eff_cfg):
    """Authoritative v2 cells: bind every graded cell to the FROZEN source index (not the row's self-claim),
    re-hash the retained source BYTES against it, and admit the append-log graded row (full Result, so
    backend/nested-outcome are checked) via the shared policy. Typed cells keep their reason in the denominator."""
    run_dir = pathlib.Path(run_dir); src_dir = run_dir / "src"
    src_index = json.loads((run_dir / runmeta["src_index"]).read_text())
    resolution = json.loads((run_dir / runmeta["resolution"]).read_text())
    log = collections.defaultdict(list)
    for ln in (run_dir / "E1PAIRS2.jsonl").read_text().splitlines():
        try:
            d = json.loads(ln)
        except Exception:  # noqa: BLE001
            continue
        if d.get("state") == "graded":
            log[(d.get("id"), d.get("kernel"))].append(d)

    def bytes_ok(si, side):
        try:
            fp = src_dir / f"{si[side]}.{si['suffix']}"
            return fp.exists() and hashlib.sha256(fp.read_bytes()).hexdigest() == si[side]
        except Exception:  # noqa: BLE001
            return False

    cells, stats = {}, collections.Counter()
    for pid, p in man["pairs"].items():
        pair_ident = {k: p.get(k) for k in admit.IDENT3}
        for kn in KERNELS:
            key = (pid, kn); ck = f"{pid}|{kn}"
            res = resolution.get(ck); si = src_index.get(ck)
            if res is not None and res.get("eff_config_id") != eff_cfg:
                cells[key] = {"state": "invalid:eff-mismatch"}; stats["invalid:eff-mismatch"] += 1; continue
            rstate = (res or {}).get("state")
            # The CURRENT attempt's resolution authorises a graded verdict. If this attempt did not grade the
            # cell (drift / worker / unstable / typed / missing), carry THAT reason -- a past valid observation
            # or a lingering source-index entry is historical, never this attempt's outcome.
            if rstate != "graded":
                cells[key] = {"state": rstate or "not-run"}; stats[rstate or "not-run"] += 1; continue
            if si is None:
                cells[key] = {"state": "invalid:graded-without-source-index"}; stats["invalid:graded-without-source-index"] += 1; continue
            if not (bytes_ok(si, "real") and bytes_ok(si, "twin")):
                cells[key] = {"state": "invalid:source-bytes"}; stats["invalid:source-bytes"] += 1; continue
            bound_src = {"real_src_sha256": si["real"], "twin_src_sha256": si["twin"]}
            adm = [d for d in log.get(key, []) if admit.graded_admissible(d, eff_cfg, pair_ident, bound_src, strict=True)]
            if not adm:
                cells[key] = {"state": "invalid:no-admissible-graded"}; stats["invalid:no-admissible-graded"] += 1; continue
            if len({admit.interp_key(d) for d in adm}) > 1:
                cells[key] = {"state": "conflict"}; stats["conflict"] += 1; continue
            row = adm[-1]
            if res.get("real_outcome") != row.get("real_outcome") or res.get("twin_outcome") != row.get("twin_outcome"):
                cells[key] = {"state": "invalid:resolution-mismatch"}; stats["invalid:resolution-mismatch"] += 1; continue
            it = admit.interpret(row)
            cells[key] = {"state": "graded", "real": it["real"], "twin": it["twin"]}; stats["graded"] += 1
    return cells, stats


def _sha12(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:12]


def aggregate_v2(man_path, runmeta_path):
    """Validate the EXACT requested manifest -> runmeta -> resolution/src-index chain, recomputing every id
    from its source (never trusting copied strings), then report. run_dir is the runmeta's directory."""
    man_path, runmeta_path = pathlib.Path(man_path), pathlib.Path(runmeta_path)
    if not man_path.exists() or not runmeta_path.exists():
        return {"mode": "v2-validated", "FAIL": [f"missing {'manifest' if not man_path.exists() else 'runmeta'} file"],
                "n_pairs": 0, "expected_cells": 0, "curve": []}, 3
    try:
        man = json.loads(man_path.read_text()); runmeta = json.loads(runmeta_path.read_text())
    except Exception as e:  # noqa: BLE001
        return {"mode": "v2-validated", "FAIL": [f"malformed json: {e}"], "n_pairs": 0, "expected_cells": 0, "curve": []}, 3
    run_dir = runmeta_path.parent
    eff_cfg, eff_conf = runmeta.get("eff_config_id"), runmeta.get("eff_config")
    errs = []
    # full chain, recomputed: base manifest config_id from man['config']; runmeta.config consistent; eff chain
    if not isinstance(man.get("config"), dict) or _sha12(man["config"]) != man.get("config_id"):
        errs.append("manifest config_id != recompute(manifest.config)")
    if runmeta.get("config") is not None and runmeta.get("config") != man.get("config"):
        errs.append("runmeta.config != manifest.config")
    if runmeta.get("config_id") is not None and runmeta.get("config_id") != man.get("config_id"):
        errs.append("runmeta.config_id != manifest.config_id")
    if not eff_cfg:
        errs.append("empty/missing eff_config_id")
    if not isinstance(eff_conf, dict):
        errs.append("missing eff_config")
    else:
        if eff_conf.get("base") != man.get("config_id"):
            errs.append(f"runmeta eff base {eff_conf.get('base')} != manifest config_id {man.get('config_id')}")
        if _sha12(eff_conf) != eff_cfg:
            errs.append(f"eff_config_id {eff_cfg} != recompute {_sha12(eff_conf)}")
    for f in ("src_index", "resolution"):
        if not (run_dir / str(runmeta.get(f))).exists():
            errs.append(f"missing {f} file")
    if errs:
        return {"mode": "v2-validated", "FAIL": errs, "n_pairs": 0, "expected_cells": 0, "curve": []}, 3
    cells, cellstats = build_cells_v2(run_dir, man, runmeta, eff_cfg)
    return _report(cells, cellstats, gt_from_manifest(man), "v2-validated", eff_cfg), 0


def _report(cells, cellstats, gt, mode, eff_cfg):
    ids = sorted(gt)
    expected = [(pid, k) for pid in ids for k in KERNELS]

    def sidestates(side):
        c = collections.Counter()
        for pid, k in expected:
            cl = cells.get((pid, k))
            c[(cl.get(side) if cl and cl.get("state") == "graded" else (cl or {}).get("state", "not-run"))] += 1
        return dict(c)

    per = {}
    for pid in ids:
        rv = tr = conj = 0; fa = []
        for k in KERNELS:
            cl = cells.get((pid, k))
            if not cl or cl.get("state") != "graded":
                continue
            if cl["real"] == V:
                rv += 1
            if cl["twin"] == R:
                tr += 1
            if cl["real"] == V and cl["twin"] == R:
                conj += 1
            if cl["twin"] == V:
                fa.append(k)
        per[pid] = {"rv": rv, "tr": tr, "conj": conj, "fa": fa, "wk": gt[pid]["witness_kind"]}

    curve = [{"k": k, "paired_gate_pass_same_kernel_conj": sum(1 for p in ids if per[p]["conj"] >= k),
              "paired_gate_pass_pct": round(100 * sum(1 for p in ids if per[p]["conj"] >= k) / max(len(ids), 1), 1),
              "real_verified_ge_k": sum(1 for p in ids if per[p]["rv"] >= k),
              "twin_refuted_ge_k": sum(1 for p in ids if per[p]["tr"] >= k),
              "DIAGNOSTIC_across_halves": sum(1 for p in ids if per[p]["rv"] >= k and per[p]["tr"] >= k)}
             for k in range(1, 8)]

    fa = {}
    for pid in ids:
        wk = per[pid]["wk"] or "unknown"
        b = fa.setdefault(wk, {"n_pairs": 0, "pairs_with_stable_verified_twin": 0, "by_kernel": collections.Counter()})
        b["n_pairs"] += 1
        if per[pid]["fa"]:
            b["pairs_with_stable_verified_twin"] += 1
            for k in per[pid]["fa"]:
                b["by_kernel"][k] += 1
    for wk in fa:
        fa[wk]["by_kernel"] = dict(fa[wk]["by_kernel"])

    repro = {"pairs_all7_real_verified": sum(1 for p in ids if per[p]["rv"] == 7),
             "pairs_all7_twin_refuted": sum(1 for p in ids if per[p]["tr"] == 7),
             "pairs_all7_conjunction": sum(1 for p in ids if per[p]["conj"] == 7)}
    return {"mode": mode,
            "eff_config_id": eff_cfg, "n_pairs": len(ids), "expected_cells": len(expected),
            "admissible_graded_cells": sum(1 for key in expected if (cells.get(key) or {}).get("state") == "graded"),
            "cell_states": dict(cellstats), "real_side_states": sidestates("real"),
            "twin_side_states": sidestates("twin"), "curve": curve,
            "reproducibility_vs_archived": repro, "false_accepts_by_witness_kind": fa,
            "notes": {"k": "same-kernel conjunction; NOT T_MIN_KERNELS; across-halves DIAGNOSTIC only",
                      "VACUOUS": "verifier refusal, never a false-accept", "stability": "both agreed flags True",
                      "false_accept": "stable twin==VERIFIED only; value-witness twins provably violate ensures"}}


def aggregate(recs, gt, man=None, eff_cfg=None):
    """v1 UNVALIDATED path + hand-row policy controls (build_cells). Authoritative v2 uses aggregate_v2()."""
    cells, cellstats = build_cells(recs, man, eff_cfg)
    mode = "v2-validated" if man else "v1-UNVALIDATED (preserved raw run; no identity binding)"
    return _report(cells, cellstats, gt, mode, eff_cfg)


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "control":
        return control()
    if len(sys.argv) >= 2 and sys.argv[1] == "pipeline":
        return pipeline_control()
    args = sys.argv[1:]
    manp = runp = None
    if "--manifest" in args:
        manp = pathlib.Path(args[args.index("--manifest") + 1])
    if "--runmeta" in args:
        runp = pathlib.Path(args[args.index("--runmeta") + 1])
    skip = set()
    for i, x in enumerate(args):
        if x in ("--manifest", "--runmeta"):
            skip.add(i); skip.add(i + 1)
    pos = [x for i, x in enumerate(args) if i not in skip and not x.startswith("--")]
    ckpt = pathlib.Path(pos[0]) if pos else None
    outp = pathlib.Path(pos[1]) if len(pos) > 1 else (manp.parent if manp else ckpt.parent) / "E1PAIRS-CURVE.json"

    if manp is not None:                                  # AUTHORITATIVE v2: honour the EXACT requested paths
        runp = runp or (manp.parent / "E1PAIRS2-RUNMETA.json")   # default runmeta sits beside the manifest
        rep, rc = aggregate_v2(manp, runp)                # validates existence + the FULL recomputed chain; no fallback
        run_dir = runp.parent
        if not rep.get("FAIL") and ckpt is not None and ckpt.resolve() != (run_dir / "E1PAIRS2.jsonl").resolve():
            rep = {"mode": "v2-validated", "FAIL": [f"checkpoint {ckpt} is not the run's log {run_dir/'E1PAIRS2.jsonl'}"],
                   "n_pairs": 0, "expected_cells": 0, "curve": []}; rc = 3
    else:                                                 # v1 UNVALIDATED: the preserved raw append-log
        gt = gt_from_live()
        recs = [json.loads(l) for l in ckpt.read_text().splitlines() if l.strip()]
        rep, rc = aggregate(recs, gt), 0
    eff_cfg = rep.get("eff_config_id")
    outp.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    if rep.get("FAIL"):
        print(f"## E1 paired curve [v2] FAILED chain validation: {rep['FAIL']}"); print(f"wrote {outp}"); return rc
    print(f"## E1 paired curve [{rep['mode']}] pairs={rep['n_pairs']} eff={eff_cfg} "
          f"admissible_graded={rep['admissible_graded_cells']}/{rep['expected_cells']}")
    print(f"cell states: {rep['cell_states']}")
    print(f"twin states: {rep['twin_side_states']}")
    print("| k | gate pass (conj) | % | real-ver≥k | twin-ref≥k | across-halves(DIAG) |")
    for c in rep["curve"]:
        print(f"| {c['k']} | {c['paired_gate_pass_same_kernel_conj']} | {c['paired_gate_pass_pct']}% | "
              f"{c['real_verified_ge_k']} | {c['twin_refuted_ge_k']} | {c['DIAGNOSTIC_across_halves']} |")
    print(f"reproducibility: {rep['reproducibility_vs_archived']}")
    print(f"false-accepts (stable VERIFIED twin only): {rep['false_accepts_by_witness_kind']}")
    print(f"wrote {outp}")
    return rc


def control():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond))); print(f"  {name}: [{'ok' if cond else 'FAIL'}]")
    EFF = "effcfg0000aa"
    man = {"config_id": "base000", "pairs": {
        "A": {"witness_kind": "value", "program_sha256": "pa", "twin_sha256": "ta", "witness_sha256": "wa",
              "archived_verified_by": KERNELS, "archived_twin_refuted_by": KERNELS},
        "B": {"witness_kind": "value", "program_sha256": "pb", "twin_sha256": "tb", "witness_sha256": "wb",
              "archived_verified_by": KERNELS, "archived_twin_refuted_by": KERNELS}},
        "keyset": [[p, k] for p in ("A", "B") for k in KERNELS]}
    gt = gt_from_manifest(man)

    def grow(pid, k, ro, to, ra=True, ta=True, rs="rs", ts="ts", drop_ident=False, no_result=False):
        d = {"id": pid, "kernel": k, "state": "graded", "eff_config_id": EFF,
             "real_outcome": ro, "twin_outcome": to, "real_agreed": ra, "twin_agreed": ta,
             "real_src_sha256": rs, "twin_src_sha256": ts}
        if not drop_ident:
            d.update(program_sha256=man["pairs"][pid]["program_sha256"], twin_sha256=man["pairs"][pid]["twin_sha256"],
                     witness_sha256=man["pairs"][pid]["witness_sha256"])
        if not no_result:
            d["real_result"] = {"backend": k, "source_sha256": rs, "outcome": ro}
            d["twin_result"] = {"backend": k, "source_sha256": ts, "outcome": to}
        return d

    # v2 positive: a fully valid row counts
    r = aggregate([grow("A", "dafny", V, R)], gt, man, EFF)
    ok("v2 positive valid row counts (k1 conj=1)", r["curve"][0]["paired_gate_pass_same_kernel_conj"] == 1 and r["mode"] == "v2-validated")
    # v2: identity hashes removed -> rejected (fail-closed)
    r = aggregate([grow("A", "dafny", V, R, drop_ident=True)], gt, man, EFF)
    ok("v2 missing identity -> rejected", r["curve"][0]["paired_gate_pass_same_kernel_conj"] == 0)
    # v2: no Result objects -> rejected
    r = aggregate([grow("A", "dafny", V, R, no_result=True)], gt, man, EFF)
    ok("v2 no-Result row -> rejected", r["curve"][0]["paired_gate_pass_same_kernel_conj"] == 0)
    # v2: Result source mismatch -> rejected
    bad = grow("A", "dafny", V, R); bad["real_result"]["source_sha256"] = admit.ZERO_SHA
    ok("v2 result-source mismatch -> rejected", aggregate([bad], gt, man, EFF)["curve"][0]["paired_gate_pass_same_kernel_conj"] == 0)
    # v2: wrong eff_config_id -> rejected
    we = grow("A", "dafny", V, R); we["eff_config_id"] = "other"
    ok("v2 wrong eff_config -> rejected", aggregate([we], gt, man, EFF)["curve"][0]["paired_gate_pass_same_kernel_conj"] == 0)
    # v2 denominator from manifest (ground truth independent of live PAIRS)
    ok("v2 denominator from manifest (2 pairs x 7)", aggregate([grow("A", "dafny", V, R)], gt, man, EFF)["expected_cells"] == 14)
    # stability + VACUOUS + conflict (shared policy)
    ok("unstable -> no pass", aggregate([grow("A", "dafny", V, R, ra=False, ta=False)], gt, man, EFF)["curve"][0]["paired_gate_pass_same_kernel_conj"] == 0)
    rv = aggregate([grow("A", "dafny", V, admit.VACUOUS)], gt, man, EFF)
    ok("vacuous twin -> no false-accept", rv["false_accepts_by_witness_kind"].get("value", {}).get("pairs_with_stable_verified_twin") == 0)
    base = [grow("A", "dafny", V, R), grow("A", "dafny", V, V)]
    rA = aggregate(list(base), gt, man, EFF); rB = aggregate(list(reversed(base)), gt, man, EFF)
    ok("conflict quarantined both orders", rA["cell_states"].get("conflict") == 1 and rB["cell_states"].get("conflict") == 1)
    # positive stable verified twin IS a false-accept
    r = aggregate([grow("B", "dafny", V, V)], gt, man, EFF)
    ok("stable verified twin is a false-accept", r["false_accepts_by_witness_kind"]["value"]["pairs_with_stable_verified_twin"] == 1)
    # v1 LEGACY row (real v1 shape: NO 'state' field, 'real_sha256' not 'real_src_sha256') admitted in v1 mode
    legacy = {"id": "A", "kernel": "dafny", "real_outcome": V, "twin_outcome": R, "real_agreed": True,
              "twin_agreed": True, "real_sha256": "x", "twin_sha256": "y",
              "real_result": {"backend": "dafny", "outcome": V, "source_sha256": "x"},
              "twin_result": {"backend": "dafny", "outcome": R, "source_sha256": "y"}}
    rL = aggregate([legacy], gt, man=None)
    ok("v1 legacy row (no state field) admitted in v1 mode",
       rL["mode"].startswith("v1") and rL["curve"][0]["paired_gate_pass_same_kernel_conj"] == 1)
    allok = all(c for _, c in checks)
    print("AGG-CONTROL " + ("PASS" if allok else "FAIL"))
    return 0 if allok else 1


def pipeline_control():
    """Real-CLI pipeline: gate2 cmd_manifest -> cmd_run (stub grade) -> aggregate_v2, then the round-4 tampers.
    Binds to the frozen source index + re-hashed bytes + validated config chain, and keeps typed reasons."""
    import tempfile
    import types
    import importlib
    g2 = importlib.import_module("e1_pairs_gate2")
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond))); print(f"  {name}: [{'ok' if cond else 'FAIL'}]")

    d = pathlib.Path(tempfile.mkdtemp()); pdir = d / "twins" / "pairs"; pdir.mkdir(parents=True)
    g2.PAIRS = pdir

    def mk(task, br, bt, w):
        prog = f"t 1\ntask {task}(n: int) returns (r: bool)\n  requires n >= 0\n  ensures r == (n >= 0)\n{{ {br} }}"
        twin = f"t 1\ntask {task}(n: int) returns (r: bool)\n  requires n >= 0\n  ensures r == (n >= 0)\n{{ {bt} }}"
        pid = hashlib.sha256((prog + "\0" + twin).encode()).hexdigest()[:16]
        (pdir / f"{task}.{pid}.json").write_text(json.dumps(
            {"id": pid, "task": task, "program": "```t\n" + prog + "\n```", "twin": "```t\n" + twin + "\n```",
             "witness": w, "verified_by": KERNELS, "twin_refuted_by": KERNELS}))
        return pid
    pidA = mk("pa", "r := true;", "r := false;", {"_kind": "value", "_ens": True, "n": 0})
    mk("pb", "r := true;", "r := false;", {"_kind": "value", "_ens": True, "n": 0})

    def probe():
        lower = lambda clean, body, witness=None: "// " + json.dumps(body)[:60] + "\n"
        cols = [("dafny", "d4.9"), ("verus", "v0.1")] + [(k, "ABSENT") for k in KERNELS[2:]]
        return cols, [("dafny", lower, "dfy"), ("verus", lower, "rs")]

    def grade(k, pid, rp, tp, flake):
        rs = g2.sha_bytes(pathlib.Path(rp).read_bytes()); ts = g2.sha_bytes(pathlib.Path(tp).read_bytes())
        Rr = {"backend": k, "backend_version": "stub", "source_sha256": rs, "outcome": admit.VERIFIED, "ok": True}
        Rt = {"backend": k, "backend_version": "stub", "source_sha256": ts, "outcome": admit.REFUTED, "ok": False}
        return {"id": pid, "kernel": k, "real": Rr, "twin": Rt, "real_agreed": True, "twin_agreed": True}

    run_dir = d / "run"

    def NS(jobs=2):
        return types.SimpleNamespace(out_dir=str(run_dir), flake=3, jobs=jobs, limit=0)
    g2.cmd_manifest(NS(), _probe=probe); g2.cmd_run(NS(), _probe=probe, _grade=grade)

    MAN = run_dir / "E1PAIRS2-MAN.json"; RM = run_dir / "E1PAIRS2-RUNMETA.json"; LOG = run_dir / "E1PAIRS2.jsonl"
    rep, rc = aggregate_v2(MAN, RM)
    ok("pipeline positive: 4 graded (2 pairs x 2 present kernels)", rep["cell_states"].get("graded") == 4 and rc == 0)
    ok("typed reason retained (backend-unavailable, not generic not-admissible)",
       rep["cell_states"].get("unverified:backend-unavailable", 0) == 10 and "not-admissible" not in rep["cell_states"])
    ok("k1 conj = 2 pairs", rep["curve"][0]["paired_gate_pass_same_kernel_conj"] == 2)

    si = json.loads((run_dir / json.loads(RM.read_text())["src_index"]).read_text())
    anyck = next(iter(si)); fp = run_dir / "src" / f"{si[anyck]['real']}.{si[anyck]['suffix']}"; saved = fp.read_bytes()
    fp.write_bytes(saved + b"// tamper\n")                       # (1) edit retained source bytes
    ok("source-byte tamper rejected", aggregate_v2(MAN, RM)[0]["cell_states"].get("invalid:source-bytes", 0) >= 1)
    fp.write_bytes(saved)

    log = LOG.read_text().splitlines()                           # (2) change row+Result src sha to a*64
    new = []
    for ln in log:
        dd = json.loads(ln)
        if dd.get("state") == "graded" and dd["id"] == pidA and dd["kernel"] == "dafny":
            dd["real_src_sha256"] = "a" * 64; dd["real_result"]["source_sha256"] = "a" * 64
        new.append(json.dumps(dd))
    LOG.write_text("\n".join(new) + "\n")
    ok("row/result src-sha tamper rejected (frozen-index binding)",
       aggregate_v2(MAN, RM)[0]["cell_states"].get("invalid:no-admissible-graded", 0) >= 1)
    LOG.write_text("\n".join(log) + "\n")

    good_rm = RM.read_text()                                     # (3) runmeta base != manifest config_id
    rm = json.loads(good_rm); rm["eff_config"]["base"] = "DIFFERENT0000"; RM.write_text(json.dumps(rm))
    r3, rc3 = aggregate_v2(MAN, RM)
    ok("runmeta base tamper -> chain FAIL (exit 3)", rc3 == 3 and "FAIL" in r3)
    rm2 = json.loads(good_rm); rm2["eff_config_id"] = None; RM.write_text(json.dumps(rm2))  # (4) delete eff
    ok("eff_config_id removed -> chain FAIL (exit 3)", aggregate_v2(MAN, RM)[1] == 3)
    RM.write_text(good_rm)

    # ---- ACTUAL main() entry-point cases with EXPLICIT filenames (not aggregate_v2 directly) ----
    def run_main(argv):
        old = sys.argv; sys.argv = ["agg"] + argv
        try:
            return main()
        finally:
            sys.argv = old
    cout = str(d / "curve.json")
    ok("main valid v2 -> exit 0", run_main([str(LOG), cout, "--manifest", str(MAN)]) == 0)
    ok("main --runmeta nonexistent -> exit 3", run_main([str(LOG), cout, "--manifest", str(MAN), "--runmeta", str(d / "nope.json")]) == 3)
    altrm = d / "alt-runmeta.json"; rmj = json.loads(good_rm); rmj["eff_config_id"] = "zzzz00000000"; altrm.write_text(json.dumps(rmj))
    ok("main alternate --runmeta mismatched eff -> exit 3", run_main([str(LOG), cout, "--manifest", str(MAN), "--runmeta", str(altrm)]) == 3)
    altman = run_dir / "ALT-MAN.json"; mj = json.loads(MAN.read_text()); mj["config_id"] = "deadbeef0000"; altman.write_text(json.dumps(mj))
    ok("main alternate --manifest different config_id -> exit 3", run_main([str(LOG), cout, "--manifest", str(altman)]) == 3)
    altman.unlink()
    ok("main checkpoint path not the run log -> exit 3",
       run_main([str(d / "elsewhere.jsonl"), cout, "--manifest", str(MAN)]) == 3)

    # (current-attempt) drift one pair's input, re-run cmd_run, then main() v2 must NOT grade the drifted cells
    paf = pdir / f"pa.{pidA}.json"; rp = json.loads(paf.read_text()); origp = rp["program"]
    rp["program"] = origp.replace("r := true;", "r := (n > -1);"); paf.write_text(json.dumps(rp))
    g2.cmd_run(NS(), _probe=probe, _grade=grade)                 # drift run: pa's cells -> input-drift this attempt
    run_main([str(LOG), cout, "--manifest", str(MAN)])
    repd = json.loads(pathlib.Path(cout).read_text())
    ok("current drift not reused as graded (history is historical)",
       repd["cell_states"].get("graded") == 2 and repd["cell_states"].get("unverified:input-drift") == 7)
    rp["program"] = origp; paf.write_text(json.dumps(rp))

    allok = all(c for _, c in checks); print("PIPELINE-CONTROL " + ("PASS" if allok else "FAIL")); return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
