#!/usr/bin/env python3
"""Freeze the E3 Vericoding eval manifest and check contamination against the ACTUAL frozen training programs.
TWO detectors, reported separately:

  EXACT alpha-equivalence (high precision -> EXCLUDED): both sides parsed to the engine AST, then variables/
  parameters/bound names are renamed to positional ids by first occurrence while CONSTANTS, OPERATORS and
  function identities are PRESERVED. So r=x+1 != r=x+2 and r=x-y != r=x-x; only a truly alpha-equivalent spec
  matches. Each exclusion carries the matched training-row reference for triage.

  SHAPE abstraction (low precision -> CANDIDATE/uncertain, never auto-excluded): the blur (names->v,
  literals->#) that collapses template siblings; a manual-triage flag only, per t/DECONTAMINATION-2026-09-21.md
  (odd/even-style siblings reviewed and kept apart).

The gate FAILS CLOSED if the training index is empty or any training program fails to parse (unresolved rows
listed). The manifest is hash-bound to the exact training-selection files it was built against.

    python3 -I e3_eval_manifest.py <arms-dir> <vericoding_dir> <out.json> [--limit N]
    python3 -I e3_eval_manifest.py --self-test
"""
import json, sys, hashlib, pathlib
sys.path.insert(0, ".")


def _collect_vars(task):
    m = {}

    def note(nm):
        if isinstance(nm, str):
            m.setdefault(nm, f"v{len(m)}")
    for p in (task.get("params") or []):
        note(p.get("name") if isinstance(p, dict) else None)
    for r in (task.get("returns") or []):
        note(r.get("name") if isinstance(r, dict) else None)

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("var"), str):
                note(x["var"])
            for k in sorted(x):
                walk(x[k])
        elif isinstance(x, list):
            for v in x:
                walk(v)
    for part in ("requires", "ensures", "spec_funs"):
        walk(task.get(part))
    return m


def _alpha(x, m):
    """Rename variable NAMES via m; KEEP constants, operators and function identities."""
    if isinstance(x, dict):
        out = {}
        for k, v in sorted(x.items()):
            if k == "var" and isinstance(v, str):
                out[k] = m.get(v, v)
            elif k == "name" and isinstance(v, str) and v in m:
                out[k] = m[v]
            else:
                out[k] = _alpha(v, m)
        return out
    if isinstance(x, list):
        return [_alpha(v, m) for v in x]
    return x


def _blur_shape(x):
    if isinstance(x, dict):
        return {k: ("v" if k in ("var", "name") else "#" if k in ("int", "nat", "float") else _blur_shape(v))
                for k, v in sorted(x.items())}
    if isinstance(x, list):
        return [_blur_shape(v) for v in x]
    return x


def content_hash(task):
    return hashlib.sha1(json.dumps(task, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _sig(task):
    ps = tuple(str(p.get("type")) for p in (task.get("params") or []))
    rs = tuple(str(r.get("type")) for r in (task.get("returns") or []))
    return (len(ps), ps, rs)


def fp_from_task(task):
    m = _collect_vars(task)
    srt = {p: sorted((task.get(p) or []), key=lambda z: json.dumps(z, sort_keys=True))
           for p in ("requires", "ensures", "spec_funs")}
    exact = json.dumps({"sig": _sig(task), "a": {p: _alpha(srt[p], m) for p in srt}}, sort_keys=True, default=str)
    shape = json.dumps({"sig0": _sig(task)[0], "s": {p: _blur_shape(srt[p]) for p in srt}}, sort_keys=True, default=str)
    return {"sig": _sig(task), "exact_hash": hashlib.sha1(exact.encode()).hexdigest()[:16],
            "shape_hash": hashlib.sha1(shape.encode()).hexdigest()[:16]}


def fp_from_t_source(src):
    import spec_experiment as se, surface
    blk = se.find_block(src)
    if not blk:
        return None
    try:
        return fp_from_task(surface.parse(blk))
    except Exception:
        return None


def build_train_index(arms_dir):
    idx = {"exact": {}, "shape": {}, "n": 0, "unparsed": []}
    for nm in ("raw", "graded", "all7"):
        fp = pathlib.Path(arms_dir) / f"{nm}.jsonl"
        if not fp.exists():
            continue
        for i, ln in enumerate(fp.read_text().splitlines()):
            row = json.loads(ln)
            f = fp_from_t_source(row.get("chosen", ""))
            if not f:
                idx["unparsed"].append(f"{nm}#{i}:{row.get('task')}"); continue
            idx["exact"].setdefault(f["exact_hash"], f"{nm}#{i}:{row.get('task')}")
            idx["shape"].setdefault(f["shape_hash"], f"{nm}#{i}:{row.get('task')}")
            idx["n"] += 1
    return idx


def classify(f, idx):
    if f is None:
        return "unparsed", "could-not-parse", None
    if f["exact_hash"] in idx["exact"]:
        return "excluded", "exact-alpha-equivalent-duplicate", idx["exact"][f["exact_hash"]]
    if f["shape_hash"] in idx["shape"]:
        return "uncertain", "same-shape-template-sibling (manual triage)", idx["shape"][f["shape_hash"]]
    return "kept", "no-match", None


def verify_licences(veri_dir):
    p = pathlib.Path(veri_dir).parent / "LICENSE-vericoding"
    veri = ("MIT (verified: LICENSE-vericoding present)" if p.exists() and "MIT License" in p.read_text()[:400]
            else "LICENSE-vericoding missing or not MIT")
    ev = pathlib.Path("out/licence-evidence.json")
    ev = ev if ev.exists() else pathlib.Path("licence-evidence.json")
    out = json.loads(ev.read_text()) if ev.exists() else {"error": "licence-evidence.json not found"}
    out.setdefault("eval_benchmark_vericoding", {})["local_check"] = veri
    return out


def training_selection_hash(arms_dir):
    h = hashlib.sha1()
    for nm in ("raw", "graded", "all7"):
        fp = pathlib.Path(arms_dir) / f"{nm}.jsonl"
        h.update(fp.read_bytes() if fp.exists() else b"MISSING")
    return h.hexdigest()[:16]


def self_test():
    P = "```t\nt 1\ntask f(x: int, y: int) returns (r: int)\n  requires x >= 0\n  ensures r == {E}\n{ r := x; }"
    base = P.replace("{E}", "x + 1")
    renamed = "```t\nt 1\ntask g(a: int, b: int) returns (c: int)\n  requires a >= 0\n  ensures c == a + 1\n{ c := a; }"
    const_diff = P.replace("{E}", "x + 2")
    bind_diff = P.replace("{E}", "x - y")
    base_xx = P.replace("{E}", "x - x")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        a = pathlib.Path(d)
        (a / "all7.jsonl").write_text(json.dumps({"chosen": base, "task": "base"}) + "\n"
                                      + json.dumps({"chosen": base_xx, "task": "base_xx"}) + "\n")
        (a / "raw.jsonl").write_text(""); (a / "graded.jsonl").write_text("")
        idx = build_train_index(d)
    pos = classify(fp_from_t_source(renamed), idx)
    n1 = classify(fp_from_t_source(const_diff), idx)
    n2 = classify(fp_from_t_source(bind_diff), idx)
    ok_pos, ok_n1, ok_n2 = pos[0] == "excluded", n1[0] != "excluded", n2[0] != "excluded"
    print(f"positive (renamed identical): {pos[:2]} [{'ok' if ok_pos else 'FAIL'}]")
    print(f"neg const x+1 vs x+2: {n1[:2]} [{'ok' if ok_n1 else 'FAIL'}]")
    print(f"neg binding x-y vs x-x: {n2[:2]} [{'ok' if ok_n2 else 'FAIL'}]")
    print("SELF-TEST " + ("PASS" if ok_pos and ok_n1 and ok_n2 else "FAIL"))
    return 0 if (ok_pos and ok_n1 and ok_n2) else 1


def main():
    if "--self-test" in sys.argv:
        return self_test()
    import tasks_io
    arms_dir, veri_dir, outp = sys.argv[1], pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0
    idx = build_train_index(arms_dir)
    # FINAL three-arm eligibility: ALL required arms present and non-empty, licence evidence resolved,
    # training index non-empty and fully parsed. Fails closed otherwise (synthetic --self-test is separate).
    arm_files = {nm: pathlib.Path(arms_dir) / f"{nm}.jsonl" for nm in ("raw", "graded", "all7")}
    arm_rows = {nm: (len(p.read_text().splitlines()) if p.exists() else 0) for nm, p in arm_files.items()}
    arms_ok = all(p.exists() and p.stat().st_size > 0 and arm_rows[nm] > 0 for nm, p in arm_files.items())
    lic = verify_licences(veri_dir)
    lic_ok = ("error" not in lic
              and bool(lic.get("base_model")) and bool(lic.get("training_corpus_mbpp"))
              and "MIT (verified" in str(lic.get("eval_benchmark_vericoding", {}).get("local_check", "")))
    final_eligibility = {"arms_present_nonempty": arms_ok, "arm_rows": arm_rows,
                         "licence_evidence_ok": lic_ok, "train_index_nonempty": idx["n"] > 0,
                         "no_unparsed_training": not idx["unparsed"]}
    gate_ok = all(final_eligibility.values())
    files = [p for p in sorted(veri_dir.iterdir()) if p.suffix == ".json"]
    scoped = bool(limit)
    if limit:
        files = files[:limit]
    kept, excluded, uncertain = [], [], []
    for p in files:
        try:
            _task = tasks_io.load_task(str(p))
            f = fp_from_task(_task)
        except Exception as e:  # noqa: BLE001
            excluded.append({"file": p.name, "reason": f"load-error:{type(e).__name__}"}); continue
        cls, why, ref = classify(f, idx)
        rec = {"name": p.stem, "file": p.name, "exact_hash": f["exact_hash"],
               "content_hash": content_hash(_task), "why": why, "matched_train_row": ref}
        (kept if cls == "kept" else excluded if cls == "excluded" else uncertain).append(rec)
    man = {"benchmark": "Vericoding-Dafny lifted to t", "scoped_subset": scoped, "n_files": len(files),
           "gate_ok": gate_ok, "training_programs_indexed": idx["n"], "training_unparsed": idx["unparsed"],
           "training_selection_hash": training_selection_hash(arms_dir), "arms_dir": str(arms_dir),
           "detectors": {"excluded": "exact alpha-equivalence (constants+operators+binding preserved)",
                         "uncertain": "shape abstraction (template sibling) - MANUAL TRIAGE, not auto-excluded"},
           "limits": "alpha-equivalence over variables with literals/operators/function-identities preserved; "
                     "still a syntactic spec check, not behavioural equivalence; UNCERTAIN rows need triage per "
                     "t/DECONTAMINATION-2026-09-21.md; rebuild + re-hash-bind after final frequency/diversity "
                     "matching changes the training selection",
           "final_eligibility": final_eligibility, "licences": lic,
           "eval_kept": kept, "eval_uncertain": uncertain, "eval_excluded": excluded}
    outp.write_text(json.dumps(man, indent=2), encoding="utf-8")
    print(f"gate_ok={gate_ok} (train n={idx['n']} unparsed={len(idx['unparsed'])}); "
          f"kept {len(kept)}, uncertain {len(uncertain)}, excluded {len(excluded)} of {len(files)}; "
          f"train-selection-hash {man['training_selection_hash']} -> {outp}")
    return 0 if gate_ok else 4


if __name__ == "__main__":
    sys.exit(main())
