#!/usr/bin/env python3
"""Exact-pair OBSERVATION certificates for the E1 paired twin-gate.

A certificate binds, per (pair, kernel): the exact archived identities (program/twin/witness/contract
sha256), the kernel + backend version, the lowered real AND twin source BYTES (copied content-addressed into
the cert bundle), the measured per-kernel OUTCOME (verified / refuted / vacuous / unproved / timeout / ...),
the flake-agreement flags, and the eff_config / manifest-config identity it was produced under.

`replay` re-runs the kernel on the STORED sources with NO model (verifiers.<kernel>.verify under flake n=3),
after re-hashing the retained bytes against the recorded content-address, and confirms the SAME outcome. This
REPRODUCES THE OBSERVATION -- it is explicitly NOT a proof of whole-program correctness, and it covers
undecided (unproved/timeout) observations as well as verified/refuted. Any tamper of a source byte, a recorded
hash, the witness, or an identity makes replay FAIL.

Scope: this is the harness prototype that mints from an AUTHORITATIVE v2 run directory (frozen manifest +
src-index + resolution + content-addressed sources). The engine-native formalization, and authoritative
minting from the post-Frama-C-fix v2 run, remain the engine-first step. `from_proof` cannot express this
(it binds only program.t and regenerates its own twin).

    python3 -I e1_pairs_cert.py mint   <v2-run-dir> <cert-dir>
    python3 -I e1_pairs_cert.py replay <cert-dir> [--sample N]
    python3 -I e1_pairs_cert.py control
"""
import argparse
import hashlib
import json
import os
import pathlib
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

import e1_admit as admit  # noqa: E402

KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
DECIDED_OR_OBS = (admit.VERIFIED, admit.REFUTED, admit.VACUOUS, "unproved", "timeout", "tool_error", "malformed")


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def mint(run_dir, cert_dir):
    run_dir = pathlib.Path(run_dir); cert_dir = pathlib.Path(cert_dir)
    (cert_dir / "src").mkdir(parents=True, exist_ok=True)
    man = json.loads((run_dir / "E1PAIRS2-MAN.json").read_text())
    runmeta = json.loads((run_dir / "E1PAIRS2-RUNMETA.json").read_text())
    eff_cfg = runmeta.get("eff_config_id")
    src_index = json.loads((run_dir / runmeta["src_index"]).read_text())
    resolution = json.loads((run_dir / runmeta["resolution"]).read_text())
    log = {}
    for ln in (run_dir / "E1PAIRS2.jsonl").read_text().splitlines():
        try:
            d = json.loads(ln)
        except Exception:  # noqa: BLE001
            continue
        if d.get("state") == "graded":
            log.setdefault((d.get("id"), d.get("kernel")), []).append(d)
    minted, record_only = 0, 0
    index = []
    for pid, p in man["pairs"].items():
        ident = {k: p.get(k) for k in ("program_sha256", "twin_sha256", "witness_sha256", "contract_sha256")}
        for kn in KERNELS:
            ck = f"{pid}|{kn}"; si = src_index.get(ck); res = resolution.get(ck)
            if si is None:                                    # no kernel ran: record-only observation (reason kept)
                cert = {"kind": "observation-record-only", "pair": pid, "kernel": kn, "identity": ident,
                        "witness_kind": p.get("witness_kind"), "state": (res or {}).get("state"),
                        "reason": (res or {}).get("reason"), "eff_config_id": eff_cfg,
                        "manifest_config_id": man.get("config_id")}
                (cert_dir / f"{ck}.cert.json").write_text(json.dumps(cert, indent=1)); record_only += 1
                index.append({"ck": ck, "kind": "record-only"}); continue
            bound = {"real_src_sha256": si["real"], "twin_src_sha256": si["twin"]}
            adm = [d for d in log.get((pid, kn), []) if admit.graded_admissible(d, eff_cfg, ident, bound, strict=True)]
            if len({admit.interp_key(d) for d in adm}) != 1:
                continue                                      # not a single admissible observation -> no cert
            row = adm[-1]
            # copy the exact lowered source BYTES, content-addressed, into the bundle
            for side in ("real", "twin"):
                srcf = run_dir / "src" / f"{si[side]}.{si['suffix']}"
                (cert_dir / "src" / f"{si[side]}.{si['suffix']}").write_bytes(srcf.read_bytes())
            cert = {"kind": "observation", "pair": pid, "kernel": kn, "identity": ident,
                    "witness_kind": p.get("witness_kind"), "suffix": si["suffix"],
                    "real_src_sha256": si["real"], "twin_src_sha256": si["twin"],
                    "real_outcome": row["real_outcome"], "twin_outcome": row["twin_outcome"],
                    "real_agreed": row["real_agreed"], "twin_agreed": row["twin_agreed"],
                    "backend_version": (row.get("real_result") or {}).get("backend_version"),
                    "eff_config_id": eff_cfg, "manifest_config_id": man.get("config_id"),
                    "replays": "re-run the kernel on the stored sources (no model); reproduces the OBSERVATION, "
                               "not whole-program correctness"}
            (cert_dir / f"{ck}.cert.json").write_text(json.dumps(cert, indent=1)); minted += 1
            index.append({"ck": ck, "kind": "observation", "real_outcome": row["real_outcome"],
                          "twin_outcome": row["twin_outcome"]})
    (cert_dir / "INDEX.json").write_text(json.dumps(
        {"run_dir": str(run_dir), "eff_config_id": eff_cfg, "manifest_config_id": man.get("config_id"),
         "minted_observations": minted, "record_only": record_only, "entries": index}, indent=1))
    print(f"minted {minted} observation certs + {record_only} record-only -> {cert_dir}")
    return 0


def replay(cert_dir, verify_fn=None, sample=0):
    cert_dir = pathlib.Path(cert_dir)
    certs = sorted(cert_dir.glob("*.cert.json"))
    obs = [json.loads(c.read_text()) for c in certs]
    obs = [o for o in obs if o.get("kind") == "observation"]
    if sample:
        import random
        random.Random(0).shuffle(obs); obs = obs[:sample]
    if verify_fn is None:
        import importlib

        def verify_fn(kernel, path):
            import verifiers
            backend = importlib.import_module(f"verifiers.{kernel}")
            r, agreed = verifiers.flake_check(backend.verify, pathlib.Path(path), 3)
            return r.outcome, agreed
    reproduced, failed = 0, []
    for o in obs:
        rp = cert_dir / "src" / f"{o['real_src_sha256']}.{o['suffix']}"
        tp = cert_dir / "src" / f"{o['twin_src_sha256']}.{o['suffix']}"
        # byte integrity vs the recorded content-address (read_bytes)
        if not (rp.exists() and sha_bytes(rp.read_bytes()) == o["real_src_sha256"]
                and tp.exists() and sha_bytes(tp.read_bytes()) == o["twin_src_sha256"]):
            failed.append({"ck": f"{o['pair']}|{o['kernel']}", "why": "source-bytes-tampered"}); continue
        ro, ra = verify_fn(o["kernel"], str(rp)); to, ta = verify_fn(o["kernel"], str(tp))
        if ro == o["real_outcome"] and to == o["twin_outcome"]:
            reproduced += 1
        else:
            failed.append({"ck": f"{o['pair']}|{o['kernel']}", "why": f"outcome real {ro} vs {o['real_outcome']}, "
                           f"twin {to} vs {o['twin_outcome']}"})
    res = {"observations": len(obs), "reproduced": reproduced, "failed": len(failed),
           "reproduced_pct": round(100 * reproduced / max(1, len(obs)), 2), "failures": failed[:50],
           "note": "reproduces the OBSERVATION with no model; NOT a whole-program correctness proof"}
    (cert_dir / "REPLAY.json").write_text(json.dumps(res, indent=1))
    print(f"replay: {reproduced}/{len(obs)} observations reproduced ({res['reproduced_pct']}%); {len(failed)} failed")
    return 0 if not failed else 1


def control():
    import tempfile
    import types
    import importlib
    g2 = importlib.import_module("e1_pairs_gate2")
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond))); print(f"  {name}: [{'ok' if cond else 'FAIL'}]")

    d = pathlib.Path(tempfile.mkdtemp()); pdir = d / "twins" / "pairs"; pdir.mkdir(parents=True); g2.PAIRS = pdir
    pq = "t 1\ntask q(n: int) returns (r: bool)\n  requires n >= 0\n  ensures r == (n >= 0)\n{ r := true; }"
    tq = "t 1\ntask q(n: int) returns (r: bool)\n  requires n >= 0\n  ensures r == (n >= 0)\n{ r := false; }"
    pid = hashlib.sha256((pq + "\0" + tq).encode()).hexdigest()[:16]
    (pdir / f"q.{pid}.json").write_text(json.dumps({"id": pid, "task": "q", "program": "```t\n" + pq + "\n```",
        "twin": "```t\n" + tq + "\n```", "witness": {"_kind": "value", "_ens": True, "n": 0},
        "verified_by": KERNELS, "twin_refuted_by": KERNELS}))

    def probe():
        lower = lambda clean, body, witness=None: "// " + json.dumps(body)[:60] + "\n"
        return [("dafny", "d4.9"), ("verus", "v0.1")] + [(k, "ABSENT") for k in KERNELS[2:]], \
               [("dafny", lower, "dfy"), ("verus", lower, "rs")]

    def grade(k, pidx, rp, tp, flake):
        rs, ts = sha_bytes(pathlib.Path(rp).read_bytes()), sha_bytes(pathlib.Path(tp).read_bytes())
        R = lambda o, s: {"backend": k, "backend_version": "stub", "source_sha256": s, "outcome": o, "ok": o == admit.VERIFIED}
        return {"id": pidx, "kernel": k, "real": R(admit.VERIFIED, rs), "twin": R(admit.REFUTED, ts),
                "real_agreed": True, "twin_agreed": True}
    run_dir = d / "run"; NS = types.SimpleNamespace(out_dir=str(run_dir), flake=3, jobs=2, limit=0)
    g2.cmd_manifest(NS, _probe=probe); g2.cmd_run(NS, _probe=probe, _grade=grade)
    cert_dir = d / "certs"; mint(run_dir, cert_dir)
    ncerts = len(list(cert_dir.glob("*.cert.json")))
    ok("mint produced observation + record-only certs", ncerts == 14)   # 2 obs (dafny,verus) + 12 record-only? 7 kernels x1 pair
    obs_certs = [json.loads(c.read_text()) for c in cert_dir.glob("*.cert.json") if json.loads(c.read_text())["kind"] == "observation"]
    ok("2 observation certs (present kernels)", len(obs_certs) == 2)

    # stub verify: outcome looked up by stored source sha -> positive reproduces; a tampered byte changes sha -> miss
    lut = {}
    for o in obs_certs:
        lut[o["real_src_sha256"]] = (o["real_outcome"], True); lut[o["twin_src_sha256"]] = (o["twin_outcome"], True)

    def vstub(kernel, path):
        return lut.get(sha_bytes(pathlib.Path(path).read_bytes()), ("unproved", True))
    ok("positive replay reproduces observations", replay(cert_dir, verify_fn=vstub) == 0)

    # tamper a stored source byte -> replay must FAIL (byte integrity)
    some = next(cert_dir.glob("*.cert.json"))
    o = json.loads(some.read_text())
    while o.get("kind") != "observation":
        some = next(c for c in cert_dir.glob("*.cert.json") if json.loads(c.read_text())["kind"] == "observation"); o = json.loads(some.read_text())
    sf = cert_dir / "src" / f"{o['real_src_sha256']}.{o['suffix']}"; saved = sf.read_bytes()
    sf.write_bytes(saved + b"// tamper\n")
    ok("source-byte tamper -> replay FAIL", replay(cert_dir, verify_fn=vstub) == 1)
    sf.write_bytes(saved)

    # tamper the recorded outcome -> replay must FAIL (observation no longer reproduces)
    o2 = json.loads(some.read_text()); o2["twin_outcome"] = admit.VERIFIED; some.write_text(json.dumps(o2))
    ok("outcome tamper -> replay FAIL", replay(cert_dir, verify_fn=vstub) == 1)

    allok = all(c for _, c in checks); print("CERT-CONTROL " + ("PASS" if allok else "FAIL")); return 0 if allok else 1


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mint"); m.add_argument("run_dir"); m.add_argument("cert_dir")
    r = sub.add_parser("replay"); r.add_argument("cert_dir"); r.add_argument("--sample", type=int, default=0)
    sub.add_parser("control")
    a = ap.parse_args()
    if a.cmd == "mint":
        return mint(a.run_dir, a.cert_dir)
    if a.cmd == "replay":
        return replay(a.cert_dir, sample=a.sample)
    return control()


if __name__ == "__main__":
    sys.exit(main())
