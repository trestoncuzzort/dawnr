#!/usr/bin/env python3
"""Record every result from a bounded Frama-C cell replay, without a release verdict.

Sources: grade_spec33.py's pinned input checks and encrypted workflow;
https://github.com/trestoncuzzort/dawnr/blob/main/t/verifiers/__init__.py (cell_pair).
"""
import argparse
import json
from pathlib import Path
import sys
from threading import Lock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "t"))
from grade_spec33 import checked_file, digest
from verifiers import cell_pair, framac


def diagnose(manifest_path, output, verify=None):
    manifest = json.loads(manifest_path.read_text())
    pairs = manifest["pairs"]
    if not 1 <= len(pairs) <= 8 or len({p["id"] for p in pairs}) != len(pairs):
        raise ValueError("supply one to eight distinct diagnostic pairs")
    checked = [(pair, checked_file(manifest_path.parent, pair["real"]),
                checked_file(manifest_path.parent, pair["twin"])) for pair in pairs]
    if output.exists():
        raise ValueError("use a fresh diagnostic output directory")
    output.mkdir(parents=True)
    verify = verify or framac.verify
    results = []
    for pair, real, twin in checked:
        calls, lock = [], Lock()

        def record(path):
            result = verify(path)
            with lock:
                calls.append({"side": "real" if path == real else "twin", **result.to_json()})
            return result

        (r, ra), (t, ta) = cell_pair(record, real, twin, 3)
        if len(calls) != 6:
            raise RuntimeError("missing diagnostic repetitions")
        results.append({"id": pair["id"], "inputs": {"real": pair["real"], "twin": pair["twin"]},
                        "agreement": {"real": ra, "twin": ta},
                        "representative_outcomes": {"real": r.outcome, "twin": t.outcome},
                        "calls": calls})
    receipt = {"purpose": "diagnostic only; no release qualification or score replacement",
               "input_manifest_sha256": digest(manifest_path), "repetitions_per_side": 3,
               "code_sha256": {name: digest(REPO / name) for name in
                               ("t/recipes/diagnose_framac.py", "t/verifiers/framac.py",
                                "t/verifiers/__init__.py")}, "pairs": results}
    (output / "diagnostic.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = diagnose(args.manifest.resolve(), args.out.resolve())
    print(json.dumps({"purpose": "diagnostic only", "pairs": len(result["pairs"]),
                      "recorded_calls": sum(len(p["calls"]) for p in result["pairs"])}))


if __name__ == "__main__":
    main()
