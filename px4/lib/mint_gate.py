#!/usr/bin/env python3
"""Mint a PX4 formal-gate certificate from a gate folder.

A gate folder holds:
  model.t       the real PX4 logic + its safety contract (requires/ensures)
  twin.t        a broken variant (the regression this gate must catch); same contract, body weakened
  witness.json  a grounded counterexample input, e.g. {"_kind":"value","_ens":true,"ch":19}
This mints `cert.json`: a dawnr paired-observation certificate that `dawnr check` replays with NO model,
confirming the real body VERIFIES and the twin is REFUTED at the witness. It tries kernels in order and uses
the first that both verifies the real and refutes the twin (SPARK/gnatprove is the usual winner for integer
bounds because it produces the grounded refutation).

    python3 mint_gate.py <gate-dir> [--kernels spark,dafny,rocq,fstar,framac]
"""
import argparse
import hashlib
import json
import os
import pathlib
import sys

ENGINE = pathlib.Path(__file__).resolve().parents[2] / "t"   # dawnr/t
sys.path.insert(0, str(ENGINE))
os.environ.setdefault("HF_HOME", os.path.expanduser("~/hf-cache"))
import obs_certificate as OC  # noqa: E402

DEFAULT_KERNELS = ["spark", "dafny", "rocq", "fstar", "framac"]


def mint(gate_dir, kernels=None):
    g = pathlib.Path(gate_dir)
    real = (g / "model.t").read_text()
    twin = (g / "twin.t").read_text()
    witness = json.loads((g / "witness.json").read_text())
    pid = hashlib.sha256((real + "\0" + twin).encode()).hexdigest()[:16]
    pair = {"id": pid, "task": g.name, "program": real, "twin": twin, "witness": witness}
    pp = g / ".pair.json"
    pp.write_text(json.dumps(pair))
    out = g / "cert.json"
    for k in (kernels or DEFAULT_KERNELS):
        rc = OC.mint(str(pp), k, str(out))
        if rc == 0:
            rep = OC.check(json.loads(out.read_text()))
            if rep["verdict"] == OC.REPRODUCED:
                print(f"[{g.name}] minted with {k}: real verified, twin refuted at the witness -> cert.json")
                pp.unlink(missing_ok=True)
                return 0, k
            print(f"[{g.name}] {k}: minted but replay did not reproduce ({rep['verdict']}), trying next")
        else:
            print(f"[{g.name}] {k}: not (real-verified AND twin-refuted) here, trying next kernel")
    pp.unlink(missing_ok=True)
    print(f"[{g.name}] FAILED: no kernel both verified the real body and refuted the twin at the witness")
    return 1, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gate_dir")
    ap.add_argument("--kernels", default="")
    a = ap.parse_args()
    ks = [k.strip() for k in a.kernels.split(",") if k.strip()] or None
    rc, _ = mint(a.gate_dir, ks)
    return rc


if __name__ == "__main__":
    sys.exit(main())
