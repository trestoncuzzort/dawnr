"""Recompute a complete, paired v6 development receipt from preserved evidence.

Uses the same scoring and strict specification checks as v6_compare.py.
https://github.com/trestoncuzzort/dawnr/blob/main/t/score_levels.py
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import score_levels
import spec_check
import spec_experiment as se
from v6_compare import confirmed_specification, digest, integrity_findings, kernel_outcomes, paired, read
from v6_export import CONVERTER


PANEL_SHA256 = "f807aec7e6b89e524ded720d9ccfb670c1d504a5a5717966a4b870516701daf7"
REPOSITORY = Path(__file__).resolve().parents[2]


def arm_result(root, arm, ids):
    if not re.fullmatch(r"[a-z0-9]+", arm):
        raise ValueError("arm must be a lowercase alphanumeric label")
    tag = f"v6-20261018-{arm}-dev"
    generated = root / ("v5-dev" if arm == "v5" else tag)
    graded = root / "proof-results" / f"{arm}-dev-full"
    directory = se.OUT_ROOT / tag
    assert (graded / "GRADED").is_file(), f"{arm}: grading incomplete"
    protocol_path = generated / "requests/protocol.json"
    protocol = read(protocol_path)
    assert read(generated / "requests/completed.json") == protocol
    assert protocol["panel_sha256"] == PANEL_SHA256
    export_path = None
    if arm == "v5":
        model_digest = "d855000c3dffd9772da5a2f9dc238b41d7f8337d9bf58e578e5274ebb9566a4e"
        model_identity = f"student-v5:{model_digest}:llama-{CONVERTER}"
    else:
        export_path = root / f"export-{arm}-receipts/export.json"
        exported = read(export_path)
        assert exported["converter_commit"] == CONVERTER and exported["quantization"] == "Q8_0"
        model_identity = f"student-v6:{exported['output']['sha256']}:llama-{CONVERTER}"
    assert protocol["identity"] == model_identity, "development answers belong to another model"
    assert protocol["route_args"] == [
        "--tag", tag, "--ids-file", "t/out/v6-20261018/dev-95.txt", "--pool", "v5",
        "--python", "3", "--spec-samples", "4", "--per-problem", "3", "--samples", "2",
        "--max-new", "1024", "--batch", "16"]
    summary = read(directory / "spec_first.json")
    assert summary["problems"] == len(ids) and set(map(int, summary["per_problem"])) == ids
    taken = {int(i) for i, result in summary["per_problem"].items() if result.get("taken") is not None}
    assert {int(p.stem) for p in (directory / "raw").glob("*.json")} == taken
    assert summary["answered"] == len(taken)
    columns, cells = se.parse_kernel_table(directory / "kernels.md")
    tasks = {read(p)["name"] for p in (directory / "tasks").glob("*.json")}
    assert set(columns) == set(spec_check.KERNELS) and set(cells) == tasks
    verdicts = read(graded / "verdicts.json")["results"]
    assert set(verdicts) == {tag + "/" + name for name in tasks}
    rows, pooled = score_levels.table([tag], ids, verdicts, .6, True)
    assert read(graded / "levels.json") == {"rows": rows, "pooled": pooled, "ids": len(ids)}
    levels = score_levels.tag_levels(tag, ids, verdicts, .6, True)
    extracted = read(directory / "extract.json")
    unconfirmed = {i for i, values in levels.items() if values[0] and not
                   confirmed_specification(verdicts[tag + "/" + extracted[str(i)]["name"]])}
    sets = {str(k): {i for i, values in levels.items() if values[0] >= k and i not in unconfirmed}
            for k in score_levels.LEVELS}
    refusals = Counter()
    for result in summary["per_problem"].values():
        refusals.update(result["refusals"])
    paths = [directory / name for name in ("spec_first.json", "extract.json", "tests.json", "kernels.md")]
    paths += [graded / name for name in ("verdicts.json", "levels.json", "evaluator.json")]
    paths += [protocol_path, generated / "requests/completed.json"]
    if export_path is not None:
        paths.append(export_path)
    result = {
        "model_identity": model_identity,
        "python_test_passing": summary["with a tested Python solution"],
        "accepted_answers": summary["answered"], "scores": rows[0],
        "confirmed_ids": {k: sorted(v) for k, v in sets.items()},
        "unconfirmed_admissions": sorted(unconfirmed),
        "stage_totals": {k: sum(r[k] for r in summary["per_problem"].values()) for k in
                         ("python attempts", "written specifications", "scored", "kept",
                          "duplicate", "dropped", "unscorable", "asked")},
        "proof_refusals": dict(refusals), "integrity": integrity_findings(cells),
        "kernel_outcomes": kernel_outcomes(cells),
        "per_problem": {str(i): {"python_passed": summary["per_problem"][str(i)]["python"] is not None,
                                 "accepted_t": i in taken,
                                 "clean_kernels": 0 if i in unconfirmed else levels.get(i, (0,))[0]}
                        for i in sorted(ids)},
        "evidence_sha256": {str(path.resolve().relative_to(REPOSITORY)): digest(path) for path in paths},
    }
    normalized = {k: v for k, v in protocol.items() if k not in ("model", "identity")}
    normalized["route_args"] = [*normalized["route_args"]]
    normalized["route_args"][1] = "<paired-tag>"
    return result, sets, normalized, read(graded / "evaluator.json")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("t/out/v6-20261018"))
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    assert args.candidate != "v5"
    panel = args.root / "dev-95.txt"
    assert digest(panel) == PANEL_SHA256
    ids = set(map(int, panel.read_text().split()))
    assert len(ids) == 95
    baseline, a, protocol_a, evaluator_a = arm_result(args.root, "v5", ids)
    candidate, b, protocol_b, evaluator_b = arm_result(args.root, args.candidate, ids)
    assert protocol_a == protocol_b, "generation protocols differ"
    assert evaluator_a == evaluator_b, "evaluators differ"
    integrity_ok = not any(values for arm in (baseline, candidate) for values in arm["integrity"].values())
    result = {
        "panel": {"name": "development-95", "count": 95, "sha256": PANEL_SHA256},
        "route": "t/recipes/v6_server_route.py", "grade": "t/recipes/v6-grade.sh",
        "reporter": {"path": "t/recipes/v6_development_report.py", "sha256": digest(__file__)},
        "scope": "Development-only candidate selection. This is not a held-out result or release qualification.",
        "arms": {"v5": baseline, args.candidate: candidate},
        "same_generation_protocol": True, "same_evaluator": True,
        "paired": {k: paired(a[k], b[k]) for k in a},
        "development_gain_without_all_seven_regression":
            len(b["1"]) > len(a["1"]) and len(b["7"]) >= len(a["7"]) and integrity_ok,
    }
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"paired": result["paired"], "integrity_ok": integrity_ok,
                      "development_gain_without_all_seven_regression":
                          result["development_gain_without_all_seven_regression"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
