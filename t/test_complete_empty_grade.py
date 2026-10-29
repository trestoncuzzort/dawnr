"""A missing answer is zero coverage; missing evidence is still an error."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent / "recipes"))
import complete_empty_grade as empty
import v7_local_pair


@pytest.fixture
def run(tmp_path, monkeypatch):
    root = tmp_path / "generation"; root.mkdir()
    monkeypatch.setattr(empty.se, "OUT_ROOT", root)
    tag = "empty-control"; directory = root / tag
    (directory / "raw").mkdir(parents=True); (directory / "tasks").mkdir()
    panel = tmp_path / "panel.txt"; panel.write_text("1\n2\n")
    summary = {"problems": 2, "answered": 0, "per_problem": {"1": {"taken": None}, "2": {"taken": None}}}
    empty.write(directory / "spec_first.json", summary)
    empty.write(directory / "extract.json", {}); empty.write(directory / "tests.json", {})
    output = tmp_path / "grade"; output.mkdir(); empty.write(output / "evaluator.json", {"fixture": "fixed"})
    return tag, panel, output, directory


def test_complete_empty_run_is_zero_through_the_existing_reader(run, monkeypatch):
    tag, panel, output, directory = run
    def forbidden(*args, **kwargs): raise AssertionError("no model, kernel or reference call is allowed")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(empty.spec_check, "check_task", forbidden)
    monkeypatch.setattr(empty.se, "run_point", forbidden)
    assert empty.complete(tag, panel, output)
    record, sets, evaluator = v7_local_pair.arm(tag + ":" + str(output), {1, 2})
    assert sets["1"] == sets["7"] == set()
    assert record["scores"]["problems"] == 2 and record["scores"][">=1"] == 0
    assert evaluator == {"fixture": "fixed"}
    assert empty.read(output / "empty-grade.json")["kernel_or_reference_calls"] == 0
    with pytest.raises(ValueError, match="replace"):
        empty.complete(tag, panel, output)


def test_saved_replies_that_do_not_extract_are_also_measured_zero(run):
    tag, panel, output, directory = run
    summary = empty.read(directory / "spec_first.json")
    summary["answered"] = 1; summary["per_problem"]["1"]["taken"] = "saved"
    empty.write(directory / "spec_first.json", summary)
    empty.write(directory / "raw/1.json", {"task_id": 1, "text": "no program"})
    empty.write(directory / "extract.json", {"1": {"stage": "no block"}})
    assert empty.complete(tag, panel, output)
    assert empty.read(output / "empty-grade.json")["saved_raw_answers"] == 1
    assert empty.read(output / "levels.json")["pooled"][">=7"] == 0


def test_nonempty_tasks_leave_existing_grading_untouched(run):
    tag, panel, output, directory = run
    empty.write(directory / "tasks/program.json", {"name": "program"})
    before = {str(p): p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    assert empty.complete(tag, panel, output) is False
    assert {str(p): p.read_bytes() for p in directory.rglob("*") if p.is_file()} == before
    assert not (output / "GRADED").exists()


@pytest.mark.parametrize("change", ["panel", "extra-raw", "missing-raw", "missing-extraction", "missing-task", "stale-tests", "missing-evaluator"])
def test_incomplete_or_foreign_evidence_never_becomes_a_zero_grade(run, change):
    tag, panel, output, directory = run
    summary = empty.read(directory / "spec_first.json")
    if change == "panel": summary["per_problem"].pop("2")
    elif change == "extra-raw": empty.write(directory / "raw/999.json", {})
    elif change == "missing-raw":
        summary["answered"] = 1; summary["per_problem"]["1"]["taken"] = "missing"
    elif change in ("missing-extraction", "missing-task"):
        summary["answered"] = 1; summary["per_problem"]["1"]["taken"] = "saved"
        empty.write(directory / "raw/1.json", {})
        if change == "missing-task": empty.write(directory / "extract.json", {"1": {"stage": "task", "name": "gone"}})
    elif change == "stale-tests": empty.write(directory / "tests.json", {"1": {"overall": "pass"}})
    else: (output / "evaluator.json").unlink()
    empty.write(directory / "spec_first.json", summary)
    with pytest.raises(ValueError): empty.complete(tag, panel, output)
    assert not (output / "GRADED").exists()
