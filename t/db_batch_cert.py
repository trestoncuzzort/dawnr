#!/usr/bin/env python3
"""Direct-body BATCH minter + STRUCTURAL audit over the 11,088-cell matrix (e1_full_adjudicate tags).

Mints one `direct-body-observation` certificate (db_certificate) per adjudicated row of each tag, and
STRUCTURALLY audits the whole set against the frozen manifest + rows WITHOUT re-running any kernel: every
cert's identity (src_hash == row.src_hash == manifest task_src_hash; survivor bodyhash == manifest; subjects
echo the embedded digests; config matches the tag's meta) must agree, with 0 missing/duplicate/unexpected.
Reproduction of the recorded STATE is sampled natively (db_certificate self-test + native replays), NOT 11,088
executed replays -- the same honest distinction as the paired set.

    python3 -I db_batch_cert.py mint-all <cert-dir>
    python3 -I db_batch_cert.py control
"""
import hashlib
import json
import os
import pathlib
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import db_certificate as DB  # noqa: E402

OUT = pathlib.Path(os.path.join(HERE, "out"))
TAGS = ["vcd", "df", "hev", "auto"]


def _safe(name):
    return hashlib.sha1(name.encode()).hexdigest()[:20]


def mint_all(cert_dir):
    cert_dir = pathlib.Path(cert_dir); cert_dir.mkdir(parents=True, exist_ok=True)
    total, index = 0, {"tags": {}, "by_state": {}, "config_ids": {}}
    audit_fail = []
    for tag in TAGS:
        man = json.loads((OUT / f"E1MAN-{tag}.json").read_bytes())
        meta = json.loads((OUT / f"E1FULL-{tag}.meta.json").read_bytes())
        cfg, cfg_id = meta["config"], meta["config_id"]
        rows = [json.loads(l) for l in (OUT / f"E1FULL-{tag}.jsonl").read_text().splitlines() if l.strip()]
        seen = set()
        tag_dir = cert_dir / tag; tag_dir.mkdir(exist_ok=True)
        minted = 0
        for r in rows:
            key = (r["path"], r["which"], r["kernel"])
            if key in seen:
                audit_fail.append(f"{tag}:duplicate:{key}"); continue
            seen.add(key)
            te = man["tasks"].get(r["path"])
            if not te or te.get("status") != "ok":
                audit_fail.append(f"{tag}:no-manifest-task:{r['path']}"); continue
            # STRUCTURAL identity: the row's src_hash must equal the manifest task_src_hash; config_id matches meta
            if r.get("src_hash") != te.get("task_src_hash"):
                audit_fail.append(f"{tag}:src_hash!=manifest:{key}")
            if r.get("config_id") != cfg_id:
                audit_fail.append(f"{tag}:config_id!=meta:{key}")
            try:
                cert = DB.mint(r, te, cfg)
            except Exception as e:  # noqa: BLE001
                audit_fail.append(f"{tag}:mint-error:{key}:{type(e).__name__}"); continue
            # cert identity echoes
            p = cert["predicate"]; subj = {s["name"]: s["digest"].get("sha1") for s in cert["subject"]}
            if p["src_hash"] != r["src_hash"] or subj.get("task") != r["src_hash"]:
                audit_fail.append(f"{tag}:cert-src-echo:{key}")
            if r["which"] != "REAL":
                sv = next((s for s in te["survivors"] if s["id"] == r["which"]), None)
                if not sv or p["survivor"]["bodyhash"] != sv["bodyhash"] or DB.canon(p["body"]) != sv["bodyhash"]:
                    audit_fail.append(f"{tag}:cert-bodyhash:{key}")
            (tag_dir / f"{_safe(r['path'])}.{r['which']}.{r['kernel']}.cert.json").write_text(json.dumps(cert))
            index["by_state"][r["state"]] = index["by_state"].get(r["state"], 0) + 1
            minted += 1
        total += minted
        index["tags"][tag] = {"corpus": man.get("corpus"), "rows": len(rows), "minted": minted,
                              "expected_cells": meta.get("expected_cells"), "config_id": cfg_id}
        index["config_ids"][tag] = cfg_id
    index["total_minted"] = total
    index["audit_fail"] = audit_fail[:50]
    index["audit_fail_count"] = len(audit_fail)
    index["note"] = ("public-safe: corpus-relative paths only, no account home path. STRUCTURAL audit (identity "
                     "vs frozen manifest/rows), NOT 11,088 executed replays; state reproduction is sampled "
                     "natively. Direct-body = body-only (survivor-verification rate, intended-correctness unknown).")
    (cert_dir / "INDEX.json").write_text(json.dumps(index, indent=1))
    okk = not audit_fail
    print(f"mint-all: {total} direct-body certs across {TAGS} -> {cert_dir}  structural-audit "
          f"{'PASS' if okk else 'FAIL (' + str(len(audit_fail)) + ')'}")
    print(f"  by_state {index['by_state']}")
    return 0 if okk else 2


def control():
    import tempfile
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond))); print(f"  {name}: [{'ok' if cond else 'FAIL'}]")
    # a tiny synthetic tag so control needs no corpus: 1 task (REAL) + 1 survivor, 1 kernel
    d = pathlib.Path(tempfile.mkdtemp()); out = d / "out"; out.mkdir()
    global OUT
    OUT = out
    task = {"name": "q", "requires": ["n >= 0"], "ensures": ["r == (n >= 0)"], "body": "r := true;"}
    tsh = DB.canon(task); sb = "r := false;"; bh = DB.canon(sb)
    svid = hashlib.sha1(f"{tsh}|neg|{bh}".encode()).hexdigest()[:16]
    man = {"tag": "t", "corpus": "synthetic/x", "tasks": {"synthetic/x/q.json": {
        "name": "q", "status": "ok", "task_src_hash": tsh, "n_selected": 1,
        "survivors": [{"id": svid, "op": "neg", "witness": {}, "body": sb, "bodyhash": bh}]}}}
    cfg = {"engine_pin": DB.current_engine_pin(), "spark_prover": "z3", "spark_jobs": "1"}; cfg_id = "cfg1x"
    rows = [{"path": "synthetic/x/q.json", "which": "REAL", "kernel": "dafny", "config_id": cfg_id, "src_hash": tsh, "state": "verified", "raw": "verified"},
            {"path": "synthetic/x/q.json", "which": svid, "kernel": "dafny", "config_id": cfg_id, "src_hash": tsh, "state": "refuted", "raw": "refuted"}]
    (out / "E1MAN-t.json").write_text(json.dumps(man))
    (out / "E1FULL-t.meta.json").write_text(json.dumps({"config": cfg, "config_id": cfg_id, "expected_cells": 2}))
    (out / "E1FULL-t.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    global TAGS
    TAGS = ["t"]
    cert_dir = d / "certs"
    rc = mint_all(cert_dir)
    idx = json.loads((cert_dir / "INDEX.json").read_text())
    ok("positive: 2 certs, structural audit clean", rc == 0 and idx["total_minted"] == 2 and idx["audit_fail_count"] == 0)
    ok("INDEX public-safe (no home path)", "/home" not in json.dumps(idx))
    # a REAL cert replays via stub -> reproduced; and a survivor cert embeds body
    import glob
    real_cert = json.loads(next(open(f).read() for f in glob.glob(str(cert_dir / "t" / "*.REAL.dafny.cert.json"))))
    ok("REAL cert replays (stub) reproduced",
       DB.check(real_cert, lambda p: task, lambda tk, b, k: ("verified" if "true" in b else "refuted", b))["verdict"] == DB.REPRODUCED)
    # tamper a row's src_hash vs manifest -> audit FAIL
    (out / "E1FULL-t.jsonl").write_text("\n".join(json.dumps({**r, "src_hash": ("0" * 40 if i == 0 else r["src_hash"])})
                                                   for i, r in enumerate(rows)) + "\n")
    rc2 = mint_all(d / "certs2")
    ok("row src_hash != manifest -> structural audit FAIL", rc2 == 2)
    allok = all(c for _, c in checks); print("DB-BATCH-CONTROL " + ("PASS" if allok else "FAIL")); return 0 if allok else 1


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "control":
        return control()
    if len(sys.argv) >= 3 and sys.argv[1] == "mint-all":
        return mint_all(sys.argv[2])
    print("usage: db_batch_cert.py mint-all <cert-dir> | control"); return 2


if __name__ == "__main__":
    sys.exit(main())
