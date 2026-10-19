#!/usr/bin/env python3
"""Pair two graded development arms that share one local evaluator (2026-10-19).

t/recipes/v6_development_report.py pairs a candidate with v5's image-graded arm and asserts the
generation protocol receipts, which the local re-grades of 2026-10-19 do not carry under the v5
control's tag. This reads only what both arms have on disk (the generation directory under
t/out/spec-experiment and the graded directory with verdicts.json, levels.json, evaluator.json),
scores both with the same functions (score_levels.tag_levels, v6_compare.confirmed_specification),
refuses when the two evaluator records differ, and writes the paired sets.

Sources: t/recipes/v6_development_report.py (arm_result, the sets and the gain rule);
t/recipes/v6_compare.py; https://github.com/trestoncuzzort/dawnr/blob/main/t/score_levels.py

    python3 t/recipes/v7_local_pair.py --panel t/out/v6-20261018/dev-95.txt \\
        --baseline v6-20261018-v5-dev-local:t/out/v6-20261018/proof-results/v5-dev-local-full \\
        --candidate v6-20261018-corrective-dev:t/out/v6-20261018/proof-results/corrective-dev-full \\
        --out OUT.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "recipes"))
import score_levels                                             # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
from v6_compare import confirmed_specification, digest, integrity_findings, kernel_outcomes, paired, read  # noqa: E402


def arm(spec: str, ids: set[int]) -> tuple[dict, dict, dict]:
    tag, graded = spec.split(":", 1)
    graded = Path(graded)
    directory = se.OUT_ROOT / tag
    if not (graded / "GRADED").is_file():
        raise SystemExit(f"{tag}: grading incomplete")
    columns, cells = se.parse_kernel_table(directory / "kernels.md")
    tasks = {read(p)["name"] for p in (directory / "tasks").glob("*.json")}
    if set(columns) != set(spec_check.KERNELS) or set(cells) != tasks:
        raise SystemExit(f"{tag}: incomplete kernel or task coverage")
    verdicts = read(graded / "verdicts.json")["results"]
    if set(verdicts) != {tag + "/" + name for name in tasks}:
        raise SystemExit(f"{tag}: incomplete specification checks")
    rows, pooled = score_levels.table([tag], ids, verdicts, .6, True)
    if read(graded / "levels.json") != {"rows": rows, "pooled": pooled, "ids": len(ids)}:
        raise SystemExit(f"{tag}: levels.json does not match a recomputation")
    levels = score_levels.tag_levels(tag, ids, verdicts, .6, True)
    extracted = read(directory / "extract.json")
    unconfirmed = {i for i, values in levels.items() if values[0] and not
                   confirmed_specification(verdicts[tag + "/" + extracted[str(i)]["name"]])}
    sets = {str(k): {i for i, values in levels.items() if values[0] >= k and i not in unconfirmed}
            for k in score_levels.LEVELS}
    summary = read(directory / "spec_first.json")
    result = {"tag": tag, "graded": str(graded),
              "python_test_passing": summary.get("with a tested Python solution"),
              "accepted_answers": summary.get("answered"), "scores": rows[0],
              "confirmed_ids": {k: sorted(v) for k, v in sets.items()},
              "unconfirmed_admissions": sorted(unconfirmed),
              "integrity": integrity_findings(cells), "kernel_outcomes": kernel_outcomes(cells),
              "evidence_sha256": {name: digest(directory / name) for name in
                                  ("spec_first.json", "extract.json", "tests.json", "kernels.md")}}
    return result, sets, read(graded / "evaluator.json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--panel", type=Path, required=True)
    ap.add_argument("--baseline", required=True, help="TAG:GRADED_DIR")
    ap.add_argument("--candidate", required=True, help="TAG:GRADED_DIR")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    ids = set(map(int, a.panel.read_text().split()))
    base, sets_a, evaluator_a = arm(a.baseline, ids)
    cand, sets_b, evaluator_b = arm(a.candidate, ids)
    same = evaluator_a == evaluator_b
    differing = sorted(k for k in set(evaluator_a) | set(evaluator_b) if evaluator_a.get(k) != evaluator_b.get(k))
    integrity_ok = not any(values for r in (base, cand) for values in r["integrity"].values())
    result = {"panel": {"path": str(a.panel), "count": len(ids), "sha256": digest(a.panel)},
              "grade": "t/recipes/v6-grade.sh", "pairing": {"path": "t/recipes/v7_local_pair.py",
                                                            "sha256": digest(__file__)},
              "scope": "Development-only candidate selection on one local evaluator; not a held-out result.",
              "same_evaluator": same, "evaluator_differences": differing,
              "arms": {"baseline": base, "candidate": cand},
              "paired": {k: paired(sets_a[k], sets_b[k]) for k in sets_a},
              "development_gain_without_all_seven_regression":
                  same and integrity_ok and len(sets_b["1"]) > len(sets_a["1"]) and len(sets_b["7"]) >= len(sets_a["7"])}
    a.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"baseline": {"python": base["python_test_passing"], "t": base["accepted_answers"],
                                   "clean": len(sets_a["1"]), "all_seven": len(sets_a["7"])},
                      "candidate": {"python": cand["python_test_passing"], "t": cand["accepted_answers"],
                                    "clean": len(sets_b["1"]), "all_seven": len(sets_b["7"])},
                      "paired_clean": result["paired"]["1"], "paired_all_seven": result["paired"]["7"],
                      "same_evaluator": same, "integrity_ok": integrity_ok,
                      "gain": result["development_gain_without_all_seven_regression"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
