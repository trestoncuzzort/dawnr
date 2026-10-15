#!/usr/bin/env python3
"""Measure the Frama-C adapter on specific archived twins, through the CLONE's (fixed) engine. Lowers the
archived real + twin (twin WITH witness) and runs real Frama-C/Alt-Ergo, printing per-side outcomes so the
before/after of the two narrow fixes is MEASURED, not assumed.

    python3 -I framac_measure.py <pairs_dir> <pair.json> [<pair.json> ...]
Run from the clone's t/ directory (its verifiers/surface/lower are on sys.path[0]).
"""
import json
import os
import pathlib
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
H = os.path.expanduser("~")
for d in [f"{H}/.opam/default/bin", f"{H}/.local/dafny"]:
    os.environ["PATH"] = d + ":" + os.environ.get("PATH", "")

import importlib      # noqa: E402
import surface          # noqa: E402
import run_par          # noqa: E402

_cols, _present = run_par.probe_backends()
_PM = {b: (low, suf) for b, low, suf in _present}
LOWER, SUFFIX = _PM.get("framac", (None, "c"))
BACKEND = importlib.import_module("verifiers.framac")


def unfence(s):
    s = (s or "").strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()


def measure(pair_path):
    if LOWER is None:
        print("  framac not available on this machine"); return None
    r = json.loads(pathlib.Path(pair_path).read_text())
    real_t, twin_t, w = unfence(r["program"]), unfence(r["twin"]), r.get("witness")
    real_task = surface.parse(real_t); twin_task = surface.parse(twin_t)
    clean = {k: v for k, v in real_task.items() if not k.startswith("_")}
    import tempfile
    work = pathlib.Path(tempfile.mkdtemp(prefix="fm-"))
    rp = work / f"real.{SUFFIX}"; tp = work / f"twin.{SUFFIX}"
    rp.write_text(LOWER(clean, clean["body"]), encoding="utf-8")
    tp.write_text(LOWER(clean, twin_task.get("body"), witness=w), encoding="utf-8")
    real = BACKEND.verify(rp); twin = BACKEND.verify(tp)
    print(f"  pair {r.get('id')} ({r.get('task')}): real={real.outcome}  twin={twin.outcome}  "
          f"(archived: real verified, twin refuted-by-all-7)")
    return r.get("id"), real.outcome, twin.outcome


def main():
    pairs_dir = pathlib.Path(sys.argv[1])
    for pid in sys.argv[2:]:
        matches = list(pairs_dir.glob(f"*.{pid}.json")) or [pairs_dir / pid]
        if not matches:
            print(f"  {pid}: NOT FOUND"); continue
        measure(matches[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
