#!/usr/bin/env python3
"""Contract-anchored Vericoding grading through the REPOSITORY's own proof+certificate path.

A reply is never graded against its own contract: we take ONLY the synthesized body, graft it onto the
FROZEN benchmark contract (whose content hash is bound in the manifest and re-checked here), and send that
populated task to the provers via prove.prove(student=None) — which does not call any model for a body that
is already present. A proved body yields a certificate via certificate.from_proof / write, and we REPLAY it
with certificate.check (no model) to confirm a portable artifact. We distinguish `kernels_proved` and
`all_seven` from merely all-requested. twin-survival is a SEPARATE deliverable and is reported as not-run here.

    ~/e3-venv/bin/python e3_contract_eval.py --self-test
    ~/e3-venv/bin/python e3_contract_eval.py --manifest M.json --veri-dir D --replies R.jsonl --out O.jsonl [--jobs 2]
"""
import argparse, json, os, sys, hashlib, pathlib, tempfile
os.environ.setdefault("T_LEAN_BIN", os.path.expanduser("~/.local/lean/bin/lean"))
os.environ["T_SPARK_JOBS"] = "1"
HOME = os.path.expanduser("~")
for d in [f"{HOME}/.cargo/bin", f"{HOME}/.opam/default/bin", f"{HOME}/.elan/bin", f"{HOME}/.local/lean/bin",
          f"{HOME}/.local/fstar/fstar/bin", f"{HOME}/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin",
          f"{HOME}/.local/verus/verus-x86-linux", f"{HOME}/.local/dafny"]:
    os.environ["PATH"] = d + ":" + os.environ.get("PATH", "")
sys.path.insert(0, ".")
SEVEN = {"dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"}


def task_hash(task):
    return hashlib.sha1(json.dumps(task, sort_keys=True, default=str).encode()).hexdigest()[:16]


def model_body(reply):
    import spec_experiment as se, surface
    blk = se.find_block(reply)
    if not blk:
        return None
    try:
        return surface.parse(blk).get("body")
    except Exception:
        return None


def grade_one(frozen_task, body, jobs=2, cert_dir=None, cert_id=None):
    """Grade a model body under the FROZEN contract via prove.prove + mint/replay a real certificate.
    Distinguishes kernels that RAN (verified or undecided) from kernels that VERIFIED; cert filename is a
    unique immutable identity so samples/arms never overwrite each other."""
    import prove, certificate
    spec = {**frozen_task, "body": body}
    r = prove.prove(spec, student=None, jobs=jobs)
    shown = r.get("shown")
    out = {"proved": bool(shown), "kernels_verified": [], "kernels_ran": [], "all_seven_verified": False,
           "all_seven_ran": False, "certificate_minted": False, "certificate_replayed": None, "why": r.get("why")}
    if not shown:
        return out
    verified = set(shown.get("provers") or [])
    ran = verified | set(shown.get("undecided") or []) | set((shown.get("cells") or {}).keys())
    out["kernels_verified"] = sorted(verified)
    out["kernels_ran"] = sorted(ran)
    out["all_seven_verified"] = verified >= SEVEN
    out["all_seven_ran"] = ran >= SEVEN
    cert = certificate.from_proof(r)
    if cert:
        out["certificate_minted"] = True
        import re
        safe = lambda s: re.sub(r"[^A-Za-z0-9_.-]", "_", str(s))
        body_hash = hashlib.sha1(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:16]
        # filesystem-safe identity carrying provenance AND the generated body, so different bodies for the
        # same (run,model,task,sample,contract) get DIFFERENT filenames (never a silent overwrite).
        name = (safe(cert_id) if cert_id else safe(frozen_task.get("name", "t"))) + "__body" + body_hash
        cdir = pathlib.Path(cert_dir or tempfile.mkdtemp(prefix="t-cert-")); cdir.mkdir(parents=True, exist_ok=True)
        cp = cdir / f"{name}.cert.json"
        # serialise via the engine writer to a temp, then place with os.link: atomic, EXCLUSIVE, NO-REPLACE.
        # (os.rename would replace an existing destination; the exists()-then-rename pattern is a TOCTOU race.)
        tmp = cdir / f".{name}.{os.getpid()}.tmp"
        certificate.write(tmp, cert)
        payload = tmp.read_bytes()
        try:
            os.link(tmp, cp)                                   # raises FileExistsError if cp exists; never overwrites
            placed = "created"
        except FileExistsError:
            existing = cp.read_bytes()                         # prior bytes are left untouched
            if existing == payload:
                placed = "byte-identical-reuse"
            else:
                placed = "IDENTITY-CONFLICT"; out["certificate_conflict"] = str(cp)
        finally:
            tmp.unlink(missing_ok=True)
        out["certificate_placed"] = placed
        if placed != "IDENTITY-CONFLICT":
            persisted = cp.read_bytes()
            out["certificate_persisted_sha256"] = hashlib.sha256(persisted).hexdigest()[:16]
            out["certificate_body_hash"] = body_hash
            try:
                from_disk = json.loads(cp.read_text())         # REPLAY the JSON read back from the file, no model
                rep = certificate.check(from_disk)
                out["certificate_replayed"] = (rep.get("verdict") == "reproduced")
                out["certificate_replay_verdict"] = rep.get("verdict")
            except Exception as e:  # noqa: BLE001
                out["certificate_replayed"] = False
                out["certificate_replay_raw"] = {"error": f"{type(e).__name__}:{e}"[:100]}
        out["certificate_path"] = str(cp)
        out["certificate_id"] = name
    return out


def self_test():
    import surface
    frozen = surface.parse("t 1\ntask inc(n: int) returns (r: int)\n  requires n >= 0\n  ensures r == n + 1\n{ }")
    honest = "```t\nt 1\ntask inc(n: int) returns (r: int)\n  requires n >= 0\n  ensures r == n + 1\n{ r := n + 1; }"
    cheat = "```t\nt 1\ntask inc(n: int) returns (r: int)\n  requires n >= 0\n  ensures true\n{ r := 0; }"
    h = grade_one(frozen, model_body(honest), jobs=2)
    c = grade_one(frozen, model_body(cheat), jobs=2)
    print("honest:", {k: h[k] for k in ("proved", "all_seven_verified", "certificate_minted", "certificate_replayed")})
    print("cheat :", {k: c[k] for k in ("proved", "all_seven_verified", "certificate_minted", "certificate_replayed")})
    ok_h = h["proved"] and h["certificate_minted"] and h["certificate_replayed"]
    ok_c = not c["proved"]
    print(f"accepted fixture proves+mints+replays [{'ok' if ok_h else 'FAIL'}]; "
          f"cheat denied credit [{'ok' if ok_c else 'FAIL'}]")
    print("CONTRACT+CERT SELF-TEST " + ("PASS" if ok_h and ok_c else "FAIL"))
    return 0 if ok_h and ok_c else 1


def control_test():
    """Two control families, one invocation.

    (A) REJECT-BEFORE-BOUNDARY: ineligible manifest / missing content_hash / drift / wrong-manifest relabel must
    all be rejected BEFORE the proof+model boundary. grade_one is stubbed to RAISE, so any reach is a failure.

    (B) PROMPT-HASH BINDING: with a RECORDING (non-raising) stub, a reply carrying the canonical prompt_hash must
    REACH grade_one (positive), while missing / wrong prompt_hash must be rejected and NOT reach it. The positive
    reaching the boundary is what proves the negative rejections are specific, not a blanket reject-everything.
    """
    import tempfile
    mid = lambda man: hashlib.sha1((json.dumps(man["eval_kept"], sort_keys=True) + str(man.get("training_selection_hash", ""))).encode()).hexdigest()[:16]

    def run(man, rep, label, stub):
        d = run.d
        (d / "man.json").write_text(json.dumps(man))
        (d / "r.jsonl").write_text(json.dumps(rep) + "\n")
        out = d / f"out-{label}.jsonl"
        argv = sys.argv; grade_one_save = globals()["grade_one"]
        globals()["grade_one"] = stub
        sys.argv = ["x", "--manifest", str(d / "man.json"), "--veri-dir", str(run.veri),
                    "--replies", str(d / "r.jsonl"), "--out", str(out)]
        try:
            rc = main()
        finally:
            sys.argv = argv; globals()["grade_one"] = grade_one_save
        rows = [json.loads(x) for x in out.read_text().splitlines()] if out.exists() else []
        return rc, rows
    run.d = pathlib.Path(tempfile.mkdtemp())
    run.veri = run.d / "veri"; run.veri.mkdir()

    # ---- (A) reject-before-boundary, raising stub ----
    boom_calls = {"n": 0}

    def boom(*_a, **_k):
        boom_calls["n"] += 1
        raise AssertionError("grade_one reached for an ineligible/missing-hash/drift/relabel row")
    (run.veri / "t0.json").write_text(json.dumps({"t": 1, "name": "t0", "gate": "loops", "params": [], "returns": [{"name": "r", "type": "int"}], "requires": [],
                                                  "ensures": [], "spec_funs": [], "body": []}))
    th = task_hash(json.loads((run.veri / "t0.json").read_text()))
    A = {}
    for label, man in (("ineligible", {"gate_ok": False, "final_eligibility": {}, "eval_kept": [{"name": "t0", "file": "t0.json", "content_hash": th}]}),
                       ("missing-hash", {"gate_ok": True, "eval_kept": [{"name": "t0", "file": "t0.json"}]}),
                       ("drift", {"gate_ok": True, "eval_kept": [{"name": "t0", "file": "t0.json", "content_hash": "deadbeefdeadbeef"}]}),
                       ("relabel", {"gate_ok": True, "eval_kept": [{"name": "t0", "file": "t0.json", "content_hash": th}]})):
        ch = man["eval_kept"][0].get("content_hash")
        rid = "WRONGMANIFESTID0" if label == "relabel" else mid(man)
        rep = {"id": "t0#greedy", "task": "t0", "sample": "greedy", "reply": "```t\nt 1\n```",
               "manifest_id": rid, "content_hash": ch}
        A[label] = run(man, rep, label, boom)

    # ---- (B) prompt-hash binding, recording (non-raising) stub ----
    import tasks_io, e3_prompt, surface
    src = "t 1\ntask pt0(n: int) returns (r: int)\n  requires n >= 0\n  ensures r == n + 1\n{ }"
    (run.veri / "pt0.json").write_text(json.dumps(surface.parse(src)))
    ftp = tasks_io.load_task(str(run.veri / "pt0.json"))
    boundp = task_hash(ftp)
    php = e3_prompt.prompt_hash(ftp)                             # canonical prompt-hash the generator must emit
    manp = {"gate_ok": True, "eval_kept": [{"name": "pt0", "file": "pt0.json", "content_hash": boundp}]}
    ridp = mid(manp)
    rec_calls = {"n": 0}

    def rec(ft, body, **k):                                      # records the boundary reach; never raises
        rec_calls["n"] += 1
        return {"proved": False, "kernels_verified": [], "kernels_ran": [], "all_seven_verified": False,
                "all_seven_ran": False, "certificate_minted": False, "certificate_replayed": None, "why": "stub"}
    good_reply = "```t\nt 1\ntask pt0(n: int) returns (r: int)\n  requires n >= 0\n  ensures r == n + 1\n{ r := n + 1; }"
    base_rep = {"id": "pt0#greedy", "task": "pt0", "sample": "greedy", "reply": good_reply,
                "manifest_id": ridp, "content_hash": boundp}
    B = {}
    B["pos"] = run(manp, {**base_rep, "prompt_hash": php}, "pp-pos", rec)
    n_after_pos = rec_calls["n"]
    B["missing"] = run(manp, {k: v for k, v in base_rep.items()}, "pp-missing", rec)   # no prompt_hash key
    B["wrong"] = run(manp, {**base_rep, "prompt_hash": "definitely-wrong0"}, "pp-wrong", rec)
    rec_total = rec_calls["n"]

    # ---- verdicts ----
    ok_inel = A["ineligible"][0] == 5                            # refused, no rows
    ok_miss = any(r.get("graded") == "missing-frozen-content-hash" for r in A["missing-hash"][1])
    ok_drift = any(r.get("graded") == "frozen-contract-hash-mismatch" for r in A["drift"][1])
    ok_relabel = any(r.get("graded") == "manifest-identity-mismatch" for r in A["relabel"][1])
    ok_boundary = boom_calls["n"] == 0
    ok_php_known = php is not None                               # fixture must actually render a canonical prompt
    pos_rows = B["pos"][1]
    ok_pos = (php is not None and n_after_pos == 1 and len(pos_rows) == 1
              and pos_rows[0].get("why") == "stub" and "graded" not in pos_rows[0]
              and pos_rows[0].get("prompt_hash") == php)         # positive REACHED grade_one and retained provenance
    ok_pmiss = (any(r.get("graded") == "prompt-hash-mismatch" for r in B["missing"][1]))
    ok_pwrong = (any(r.get("graded") == "prompt-hash-mismatch" for r in B["wrong"][1]))
    ok_pneg_boundary = rec_total == 1                            # ONLY the positive ever reached grade_one
    checks = (("ineligible refused(exit5)", ok_inel), ("missing-hash rejected", ok_miss),
              ("drift rejected", ok_drift), ("wrong-manifest relabel rejected", ok_relabel),
              ("grade_one never reached (reject cases)", ok_boundary),
              ("canonical prompt-hash computable for fixture", ok_php_known),
              ("correct prompt_hash REACHES grade_one + provenance kept", ok_pos),
              ("missing prompt_hash rejected", ok_pmiss), ("wrong prompt_hash rejected", ok_pwrong),
              ("only the positive reached grade_one (not reject-all)", ok_pneg_boundary))
    for k, v in checks:
        print(f"{k}: [{'ok' if v else 'FAIL'}]")
    allok = all(v for _, v in checks)
    print("CONTROL-TEST " + ("PASS" if allok else "FAIL"))
    return 0 if allok else 1


_CUR = {"body": None}


def cert_immutability_test():
    """Same cert_id + DIFFERENT body must NOT overwrite; same body reuses byte-identically; a different
    payload at the same path is a clear conflict. Stub proof/mint/check; keep the REAL certificate.write I/O."""
    import prove, certificate, tempfile
    op, of, oc = prove.prove, certificate.from_proof, certificate.check

    def fake_prove(spec, **k):
        _CUR["body"] = spec.get("body")
        return {"name": spec.get("name"), "why": None,
                "shown": {"program": json.dumps(spec.get("body"), sort_keys=True), "provers": sorted(SEVEN),
                          "undecided": [], "cells": {x: "verified / refuted" for x in SEVEN}}}

    def fake_from_proof(r, **k):
        return {"kind": "prove", "function": r["name"], "program": r["shown"]["program"]}  # body-dependent payload

    def fake_check(c):
        return {"verdict": "reproduced"}
    prove.prove, certificate.from_proof, certificate.check = fake_prove, fake_from_proof, fake_check
    d = pathlib.Path(tempfile.mkdtemp()); frozen = {"name": "T", "params": [], "returns": [{"name": "r", "type": "int"}],
                                                    "requires": [], "ensures": [], "spec_funs": []}
    try:
        g1 = grade_one(frozen, [{"assign": ["r", {"int": 1}]}], cert_dir=str(d), cert_id="run__m_slash__T__greedy__CH")
        g2 = grade_one(frozen, [{"assign": ["r", {"int": 2}]}], cert_dir=str(d), cert_id="run__m_slash__T__greedy__CH")
        g3 = grade_one(frozen, [{"assign": ["r", {"int": 1}]}], cert_dir=str(d), cert_id="run__m_slash__T__greedy__CH")
        diff = g1["certificate_path"] != g2["certificate_path"]
        both = pathlib.Path(g1["certificate_path"]).exists() and pathlib.Path(g2["certificate_path"]).exists()
        bytes_differ = pathlib.Path(g1["certificate_path"]).read_bytes() != pathlib.Path(g2["certificate_path"]).read_bytes()
        reuse = g3["certificate_placed"] == "byte-identical-reuse" and g3["certificate_path"] == g1["certificate_path"]
        # interleaving / no-replace: a DIFFERENT payload already sitting at the path (as if created just
        # before placement) must yield a conflict AND leave the prior bytes byte-for-byte unchanged.
        prior = b'{"different": true, "prior": "must-survive"}'
        pathlib.Path(g1["certificate_path"]).write_bytes(prior)
        g4 = grade_one(frozen, [{"assign": ["r", {"int": 1}]}], cert_dir=str(d), cert_id="run__m_slash__T__greedy__CH")
        conflict = g4.get("certificate_placed") == "IDENTITY-CONFLICT" and "certificate_conflict" in g4
        prior_preserved = pathlib.Path(g1["certificate_path"]).read_bytes() == prior
        no_slash = "/" not in pathlib.Path(g1["certificate_path"]).name
    finally:
        prove.prove, certificate.from_proof, certificate.check = op, of, oc
    for k, v in (("different body -> different path", diff), ("both artifacts preserved", both),
                 ("payloads differ by body", bytes_differ), ("same body -> byte-identical reuse", reuse),
                 ("different payload same path -> conflict (no overwrite)", conflict),
                 ("prior bytes preserved on conflict (no-replace)", prior_preserved),
                 ("filename filesystem-safe (no '/')", no_slash)):
        print(f"{k}: [{'ok' if v else 'FAIL'}]")
    allok = all([diff, both, bytes_differ, reuse, conflict, prior_preserved, no_slash])
    print("CERT-IMMUTABILITY-TEST " + ("PASS" if allok else "FAIL"))
    return 0 if allok else 1


def main():
    if "--self-test" in sys.argv:
        return self_test()
    if "--control-test" in sys.argv:
        return control_test()
    if "--cert-test" in sys.argv:
        return cert_immutability_test()
    import tasks_io
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=pathlib.Path, required=True)
    ap.add_argument("--veri-dir", type=pathlib.Path, required=True)
    ap.add_argument("--replies", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--model", default="unknown-model")
    ap.add_argument("--run", default="run")
    a = ap.parse_args()
    man = json.loads(a.manifest.read_text())
    # MANDATORY eligibility: an ineligible manifest never reaches the proof/model boundary.
    if not man.get("gate_ok"):
        print(f"REFUSED: manifest gate_ok is not True (final-eligibility gate failed): "
              f"{man.get('final_eligibility')}"); return 5
    frozen = {r["name"]: r for r in man["eval_kept"]}          # kept (contamination-clean) tasks only
    # manifest identity: same formula the generator stamps into each reply (relabel protection).
    manifest_id = hashlib.sha1((json.dumps(man["eval_kept"], sort_keys=True)
                                + str(man.get("training_selection_hash", ""))).encode()).hexdigest()[:16]
    cert_dir = a.out.parent / "certs"; cert_dir.mkdir(parents=True, exist_ok=True)
    fh = a.out.open("w", encoding="utf-8"); n = 0
    for ln in a.replies.read_text().splitlines():
        rep = json.loads(ln); task = rep["task"]
        sample = rep.get("sample", "?")
        if task not in frozen:
            fh.write(json.dumps({**rep, "graded": "excluded-or-unknown-task", "twin_survival": "not-run"}) + "\n"); continue
        if rep.get("manifest_id") != manifest_id:              # response generated against a DIFFERENT manifest
            fh.write(json.dumps({"id": rep["id"], "task": task, "graded": "manifest-identity-mismatch",
                                 "reply_manifest": rep.get("manifest_id"), "grading_manifest": manifest_id}) + "\n"); continue
        bound = frozen[task].get("content_hash")
        if not bound:                                          # MANDATORY: no hash -> refuse (never optional)
            fh.write(json.dumps({"id": rep["id"], "task": task, "graded": "missing-frozen-content-hash"}) + "\n"); continue
        if rep.get("content_hash") != bound:                   # reply bound to a different contract than the manifest's
            fh.write(json.dumps({"id": rep["id"], "task": task, "graded": "reply-content-hash-mismatch",
                                 "reply_hash": rep.get("content_hash"), "frozen_hash": bound}) + "\n"); continue
        ft = tasks_io.load_task(str(a.veri_dir / frozen[task]["file"]))
        if task_hash(ft) != bound:                             # drift: on-disk contract != frozen manifest hash (first)
            fh.write(json.dumps({"id": rep["id"], "task": task, "graded": "frozen-contract-hash-mismatch",
                                 "expected": bound, "got": task_hash(ft)}) + "\n"); continue
        from e3_prompt import prompt_hash as _ph
        expected_ph = _ph(ft)                                  # canonical prompt the generator must have used
        if rep.get("prompt_hash") != expected_ph:              # missing or wrong prompt-hash -> reject before proof
            fh.write(json.dumps({"id": rep["id"], "task": task, "graded": "prompt-hash-mismatch",
                                 "reply_prompt_hash": rep.get("prompt_hash"), "expected_prompt_hash": expected_ph}) + "\n"); continue
        body = model_body(rep["reply"])
        if body is None:
            fh.write(json.dumps({"id": rep["id"], "task": task, "sample": sample,
                                 "proved": False, "why": "no-parse", "twin_survival": "not-run"}) + "\n"); n += 1; continue
        cert_id = f"{a.run}__{a.model}__{task}__{sample}__{bound}"
        g = grade_one(ft, body, jobs=a.jobs, cert_dir=str(cert_dir), cert_id=cert_id)
        fh.write(json.dumps({"id": rep["id"], "task": task, "sample": sample, "content_hash": bound,
                             "prompt_hash": rep.get("prompt_hash"), "model": a.model, "run": a.run, **g,
                             "twin_survival": "not-run (separate deliverable)"}) + "\n")
        fh.flush(); n += 1
    fh.close()
    print(f"graded {n} replies via prove+certificate (contract-anchored, eligibility+hash enforced) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
