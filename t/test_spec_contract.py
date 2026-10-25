"""Reference agreement cannot replace static validity at a teacher-data boundary."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "recipes"))
import curate_spec_rows as curate
import prepare_release_rows as prep
from spec_contract import checked_contract
import surface
import spec_experiment as se
import v9_strict_specs as strict
import check_wf


def contract(version=1):
    return {"t": version, "gate": "loops", "name": "f",
            "params": [{"name": "x", "type": "int"}], "returns": [{"name": "r", "type": "int"}],
            "requires": [], "ensures": [{"op": "==", "args": [{"var": "r"}, {"var": "x"}]}], "body": []}


def row(task, prompt="question"):
    return {"source": "spec", "task_id": 7, "tag": "teacher:fixture", "prompt": prompt,
            "chosen": "```t\n" + surface.print_task(task).strip() + "\n```"}


def test_checked_promotion_preserves_every_contract_field_and_the_input():
    original = contract(0)
    frozen = deepcopy(original)
    result, promoted = checked_contract(original)
    assert promoted and result == dict(original, t=1)
    assert original == frozen


@pytest.mark.parametrize("version", [0, 1])
def test_recursive_program_contract_preserves_its_measure_before_a_body_exists(version):
    program = surface.parse((Path(__file__).parent / "tasks/factorial.t").read_text())
    assert not check_wf.check_wf(program)
    original = dict(program, body=[], t=version)
    frozen = deepcopy(original)
    result, promoted = checked_contract(original)
    assert result == dict(original, t=1) and promoted == (version == 0)
    assert original == frozen and result["decreases"] == program["decreases"]
    # A specification pass does not authorize this empty task as a verified program.
    assert any(e.rule == "decreases-selfcall" for e in check_wf.check_wf(result, positions={}))
    without_measure = deepcopy(program)
    del without_measure["decreases"]
    assert any(e.rule == "decreases-selfcall" for e in check_wf.check_wf(without_measure, positions={}))


@pytest.mark.parametrize("measure", [{"bool": True}, {"var": "r"}, {"call": {"fun": "missing", "args": []}}])
def test_deferred_task_body_does_not_skip_measure_type_scope_or_call_checks(measure):
    value = dict(contract(), decreases=measure)
    with pytest.raises(ValueError, match="ill-formed"):
        checked_contract(value)


def test_spec_function_termination_is_still_checked_with_an_empty_task_body():
    program = surface.parse((Path(__file__).parent / "tasks/factorial.t").read_text())
    value = dict(program, body=[])
    del value["spec_funs"][0]["decreases"]
    with pytest.raises(ValueError, match="calls itself without a decreases"):
        checked_contract(value)


def test_contract_entry_point_refuses_a_completed_body():
    program = surface.parse((Path(__file__).parent / "tasks/factorial.t").read_text())
    with pytest.raises(ValueError, match="empty body"):
        checked_contract(program)


@pytest.mark.parametrize("callee", ["missing_helper", "f"])
def test_undefined_and_circular_contract_calls_stop_before_reference_evaluation(callee, monkeypatch):
    task = contract()
    task["ensures"][0]["args"][1] = {"call": {"fun": callee, "args": [{"var": "x"}]}}
    def forbidden(*args, **kwargs):
        raise AssertionError("an invalid contract reached the reference oracle")
    monkeypatch.setattr(strict.spec_check, "check_task", forbidden)
    _tid, _index, result = strict._check((7, (0, 0), task, 1000, 0))
    assert result["status"] == "not well formed"
    assert not strict.strict_keeps(result, 0.9)


def test_dead_branch_does_not_hide_an_undefined_helper():
    task = contract()
    task["ensures"][0]["args"][1] = {"ite": {"cond": {"bool": False},
        "then": {"call": {"fun": "missing_helper", "args": []}}, "else": {"var": "x"}}}
    with pytest.raises(ValueError, match="ill-formed"):
        checked_contract(task)


def test_a_printer_cannot_silently_discard_an_expression_field():
    task = contract()
    task["ensures"][0]["extra_clause"] = {"bool": False}
    with pytest.raises(ValueError):
        checked_contract(task)


def test_strict_check_uses_promoted_header_without_changing_draws_or_oracle_result(monkeypatch):
    monkeypatch.setitem(strict._POOL, 7, "pool-entry")
    def oracle(task, entry, draws, rnd):
        assert task == contract(1) and entry == "pool-entry" and draws == 1000
        return {"status": "agrees", "draws": 40, "completeness": 0.95, "cross_completeness": 0.9}
    monkeypatch.setattr(strict.spec_check, "check_task", oracle)
    _, _, result = strict._check((7, (0, 0), contract(0), 1000, 0))
    assert result["static_contract_checked"] and result["header_promoted"]
    assert result["draws"] == 40 and strict.strict_keeps(result, 0.9)


def test_forged_reference_receipt_cannot_admit_an_invalid_source(tmp_path):
    task = contract()
    task["ensures"][0]["args"][1] = {"var": "not_declared"}
    kept = tmp_path / "kept.jsonl"
    kept.write_text(json.dumps({"task_id": 7, "tasks": [task], "reference": [
        {"status": "agrees", "draws": 1000, "completeness": 1, "cross_completeness": 1,
         "static_contract_checked": True}]}) + "\n")
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"pool": "v5", "draws": 1000, "floor": 0.9,
                                  "problems_kept": 1, "candidates_kept": 1}))
    with pytest.raises(ValueError, match="ill-formed"):
        prep.validate_strict(kept, report)


def test_curation_preserves_legacy_prefix_reference_rows_and_unmodified_contracts():
    base = [{"source": "legacy", "chosen": "not a task; registered control"}]
    python = {"source": "python", "tag": "teacher:fixture", "task_id": 7, "prompt": "python", "chosen": "return 1"}
    valid = row(contract())
    invalid = contract()
    invalid["ensures"][0]["args"][1] = {"var": "undefined"}
    candidate = base + [python, valid, row(invalid, "bad"), row(contract(0), "promote")]
    frozen = deepcopy(candidate)
    output, report = curate.filter_additions(base, candidate)
    assert output[:3] == base + [python, valid]
    assert len(output) == 4 and surface.parse(se.find_block(output[-1]["chosen"]))["t"] == 1
    assert report["counts"]["invalid_specifications_dropped"] == 1
    assert report["counts"]["headers_promoted"] == 1
    assert candidate == frozen


def test_header_normalization_does_not_create_duplicate_training_rows():
    output, report = curate.filter_additions([], [row(contract()), row(contract(0))])
    assert len(output) == 1 and output == [row(contract())]
    assert report["counts"]["duplicates_dropped"] == 1


def test_changed_frozen_prefix_is_refused():
    with pytest.raises(ValueError, match="frozen baseline"):
        curate.filter_additions([{"chosen": "original"}], [{"chosen": "changed"}])


def test_failed_full_audit_cannot_write_a_completion_receipt(tmp_path, monkeypatch):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    base = inputs / "base.jsonl"
    base.write_text('{"chosen":"registered base"}\n')
    candidate = inputs / "candidate.jsonl"
    candidate.write_text(base.read_text() + json.dumps(row(contract())) + "\n")
    entry = lambda path, n: {"path": path.name, "sha256": prep.digest(path), "rows": n}
    manifest = inputs / "manifest.json"
    manifest.write_text(json.dumps({"label": "fixture", "base": entry(base, 1), "candidate": entry(candidate, 2)}))
    def fail(command, **kwargs):
        assert "--panels" in command and "--refuse-gpl" in command
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(curate.subprocess, "run", fail)
    out = tmp_path / "out"
    with pytest.raises(subprocess.CalledProcessError):
        curate.curate(manifest, out, 1)
    assert not (out / "COMPLETE").exists() and not (out / "rows-manifest.json").exists()
