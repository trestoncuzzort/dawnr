"""Do not turn missing teacher evidence into training rows or an understated grant total."""
import json
from decimal import Decimal
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "recipes"))
import cohere_run_report as report


def write(path, value, lines=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in value) if lines else json.dumps(value))


@pytest.fixture
def teacher(tmp_path):
    root = tmp_path / "run"
    artifact = root / "teacher-pass-0"
    directory = artifact / "out/r61"
    row = {"task_id": 1, "tasks": [{"name": "spec"}], "sources": ["sample"], "scores": [{}],
           "reference": [{"status": "agrees", "draws": 1000, "completeness": 0.95, "cross_completeness": 0.95}]}
    write(directory / "pass-0-ledger.jsonl", [{"usd": 0.1}, {"usd": 0.2}], lines=True)
    write(directory / "pass-0-kept.jsonl", [row], lines=True)
    write(directory / "pass-0-strict-kept.jsonl", [row], lines=True)
    write(directory / "pass-0-strict.json", {"pool": "v5", "draws": 1000, "floor": 0.9,
                                           "problems_kept": 1, "candidates_kept": 1})
    write(artifact / "t/out/spec-experiment/pass-0-tc00/spec_first.json",
          {"problems": 2, "per_problem": {"1": {}, "2": {}}})
    return root, directory


def test_keeps_only_strict_outputs_and_accounts_for_unreached_problems(teacher, tmp_path):
    root, directory = teacher
    prior = tmp_path / "prior.jsonl"
    write(prior, [{"usd": 82.8}], lines=True)
    result, rows, remaining = report.collect(root, ["1", "2", "3"], 1, [prior])
    assert result["run_usd"] == "0.3" and result["total_usd"] == "83.1"
    assert result["unallocated_usd"] == "866.9"
    assert result["accounted_problems"] == 2 and result["not_accounted_problems"] == 1
    assert [row["task_id"] for row in rows] == [1] and remaining == ["2", "3"]


def test_missing_job_cannot_be_reported_as_a_complete_run(teacher):
    with pytest.raises(ValueError, match="expected 2 job ledgers"):
        report.collect(teacher[0], ["1", "2"], 2, [])


def test_missing_strict_check_is_not_zero_yield(teacher):
    root, directory = teacher
    (directory / "pass-0-strict.json").unlink()
    with pytest.raises(ValueError, match="strict check missing"):
        report.collect(root, ["1", "2"], 1, [])


def test_weak_or_incomplete_evidence_cannot_enter_training(teacher):
    root, directory = teacher
    path = directory / "pass-0-strict-kept.jsonl"
    rows = report.jsonl(path)
    rows[0]["reference"][0]["cross_completeness"] = 0.2
    write(path, rows, lines=True)
    with pytest.raises(ValueError, match="lacks strict evidence"):
        report.collect(root, ["1", "2"], 1, [])


def test_unplanned_problem_is_refused(teacher):
    with pytest.raises(ValueError, match="unplanned problem"):
        report.collect(teacher[0], ["2", "3"], 1, [])


def test_empty_route_yield_is_valid_without_a_strict_report(teacher):
    root, directory = teacher
    (directory / "pass-0-kept.jsonl").write_text("")
    (directory / "pass-0-strict.json").unlink()
    (directory / "pass-0-strict-kept.jsonl").unlink()
    result, rows, remaining = report.collect(root, ["1", "2"], 1, [])
    assert result["strict_kept_problems"] == 0 and rows == [] and remaining == ["1", "2"]


def test_over_budget_never_yields_negative_or_extra_allocation(teacher):
    result, _, _ = report.collect(teacher[0], ["1", "2"], 1, [], Decimal("0.2"))
    assert result["unallocated_usd"] == "0"


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-1"])
def test_invalid_charges_are_refused(teacher, amount):
    root, directory = teacher
    write(directory / "pass-0-ledger.jsonl", [{"usd": amount}], lines=True)
    with pytest.raises(ValueError, match="invalid charge"):
        report.collect(root, ["1", "2"], 1, [])
