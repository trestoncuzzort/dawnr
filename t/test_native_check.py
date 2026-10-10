"""Negative controls for the native CBMC receipt gate; optional real-tool pilot."""
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_check as native


def completed(data, code=0):
    return {"state": "finished", "exit": code, "stdout": json.dumps(data), "stderr": "", "seconds": 0.0}


def sample(loops=0):
    scope = {"expected_assertions": ["native.range"], "expected_assumptions": 1, "expected_loops": loops}
    inventory = completed([{"properties": [{"name": "harness.assertion.1", "description": "native.range"}]}])
    coverage = completed([{"goals": [
        {"goal": "harness.coverage.1", "description": "assert(false) before assume(count == 72)",
         "sourceLocation": {"function": "harness", "line": "5"}, "status": "satisfied"},
        {"goal": "harness.coverage.2", "description": "assert(false) after assume(count == 72)",
         "sourceLocation": {"function": "harness", "line": "5"}, "status": "satisfied"}],
        "totalGoals": 2, "goalsCovered": 2}])
    results = [{"property": "harness.assertion.1", "description": "native.range", "status": "SUCCESS"}]
    if loops:
        results += [{"property": "count_to.unwind.0", "description": "unwinding assertion loop 0", "status": "SUCCESS"}]
    checking = completed([{"result": results}, {"cProverStatus": "success"}])
    return inventory, coverage, checking, scope


def edit(run, change):
    payload = json.loads(run["stdout"])
    change(payload)
    run["stdout"] = json.dumps(payload)


def test_success_requires_property_inventory_coverage_and_terminal_agreement():
    assert native.interpret(*sample())["verdict"] == "complete"
    assert native.interpret(*sample(1))["verdict"] == "complete"


@pytest.mark.parametrize("failure", ["empty", "truncated", "no_results", "missing_property", "duplicate_property", "no_terminal",
                                       "duplicate_terminal", "wrong_terminal", "bad_exit", "no_assertion", "error_message",
                                       "missing_coverage", "duplicate_coverage", "coverage_total", "coverage_pair", "unknown_status", "malformed_trace", "malformed_location"])
def test_incomplete_or_inconsistent_output_never_counts_as_complete(failure):
    inventory, coverage, checking, scope = sample()
    if failure == "empty": checking["stdout"] = "[]"
    elif failure == "truncated": checking["stdout"] = checking["stdout"][:-1]
    elif failure == "no_results": edit(checking, lambda d: d.pop(0))
    elif failure == "missing_property": edit(inventory, lambda d: d[0]["properties"].append({"name": "wrap_bin.overflow.1"}))
    elif failure == "duplicate_property": edit(checking, lambda d: d[0]["result"].append(dict(d[0]["result"][0])))
    elif failure == "no_terminal": edit(checking, lambda d: d.pop())
    elif failure == "duplicate_terminal": edit(checking, lambda d: d.append({"cProverStatus": "success"}))
    elif failure == "wrong_terminal": edit(checking, lambda d: d[-1].update(cProverStatus="failure"))
    elif failure == "bad_exit": checking["exit"] = 10
    elif failure == "no_assertion": scope["expected_assertions"] = ["absent assertion"]
    elif failure == "error_message": edit(checking, lambda d: d.append({"messageType": "ERROR", "messageText": "parse failed"}))
    elif failure == "missing_coverage": edit(coverage, lambda d: d[0]["goals"].pop())
    elif failure == "duplicate_coverage": edit(coverage, lambda d: d[0]["goals"].__setitem__(1, d[0]["goals"][0]))
    elif failure == "coverage_total": edit(coverage, lambda d: d[0].update(goalsCovered=0))
    elif failure == "coverage_pair": edit(coverage, lambda d: d[0]["goals"][1].update(description="assert(false) before assume(count == 72)"))
    elif failure == "unknown_status": edit(checking, lambda d: d[0]["result"][0].update(status="looks-good"))
    elif failure == "malformed_location": edit(checking, lambda d: d[0]["result"][0].update(sourceLocation=None))
    elif failure == "malformed_trace":
        edit(checking, lambda d: d[0]["result"][0].update(status="FAILURE", trace=["not a trace step"]))
        edit(checking, lambda d: d[-1].update(cProverStatus="failure"))
        checking["exit"] = 10
    assert native.interpret(inventory, coverage, checking, scope)["verdict"] == "tool_error"


@pytest.mark.parametrize("state", ["absent", "timeout", "tool_error"])
def test_failed_stage_is_a_nonresult(state):
    args = list(sample())
    args[1]["state"] = state
    assert native.interpret(*args)["verdict"] == state


def test_unsatisfiable_assumptions_do_not_become_property_success():
    inventory, coverage, checking, scope = sample()
    edit(coverage, lambda d: d[0]["goals"][1].update(status="failed"))
    edit(coverage, lambda d: d[0].update(goalsCovered=1))
    assert native.interpret(inventory, coverage, checking, scope)["verdict"] == "vacuous"


def test_unwinding_failure_or_missing_unwinding_is_not_a_proof():
    inventory, coverage, checking, scope = sample(1)
    edit(checking, lambda d: d[0]["result"][-1].update(status="FAILURE"))
    edit(checking, lambda d: d[-1].update(cProverStatus="failure"))
    checking["exit"] = 10
    assert native.interpret(inventory, coverage, checking, scope)["verdict"] == "incomplete"
    inventory, coverage, checking, scope = sample()
    scope["expected_loops"] = 1
    assert native.interpret(inventory, coverage, checking, scope)["verdict"] == "tool_error"


def test_counterexample_requires_a_property_specific_trace():
    inventory, coverage, checking, scope = sample()
    edit(checking, lambda d: d[0]["result"][0].update(status="FAILURE"))
    edit(checking, lambda d: d[-1].update(cProverStatus="failure"))
    checking["exit"] = 10
    assert native.interpret(inventory, coverage, checking, scope)["verdict"] == "tool_error"
    edit(checking, lambda d: d[0]["result"][0].update(trace=[{"stepType": "failure", "property": "harness.assertion.1"}]))
    assert native.interpret(inventory, coverage, checking, scope)["verdict"] == "counterexample"


def test_no_source_byte_can_change_under_the_pinned_identity(tmp_path):
    for case in ("original", "fixed"):
        definition, identity = native.extract(case)
        assert native.digest(definition) == identity["definition_sha256"]
        (tmp_path / (case + ".cpp")).write_bytes((native.FIXTURES / (case + ".cpp")).read_bytes() + b"\n")
        with pytest.raises(ValueError, match="source mismatch"):
            native.extract(case, tmp_path)


def test_mutation_and_harness_assumptions_have_distinct_identities():
    generated = {case: native.build_case(case) for case in native.CASES}
    assert generated["fixed"][1]["source"]["revision"] == native.SOURCES["fixed"][0]
    assert generated["mutant"][2] == generated["original"][2]
    assert generated["mutant"][1]["source"]["mutation"]["replacement"]["revision"] == native.SOURCES["original"][0]
    assert generated["fixed"][1]["unit_sha256"] != generated["vacuous"][1]["unit_sha256"]
    assert generated["fixed"][1]["executed_definition_sha256"] != generated["mutant"][1]["executed_definition_sha256"]
    assert all(scope["unit_sha256"] == native.digest(unit) for unit, scope, _ in generated.values())


def test_missing_tool_writes_explicit_nonresult_and_retains_harness(tmp_path):
    result = native.check("fixed", tmp_path / "run", cbmc="/no-such-cbmc-for-this-test")
    assert result["verdict"] == "absent"
    assert (tmp_path / "run" / "unit.c").is_file()
    assert json.loads((tmp_path / "run" / "receipt.json").read_text())["verdict"] == "absent"


def test_timeout_cannot_return_a_successful_exit(tmp_path):
    result = native.run_process([sys.executable, "-c", "import time; time.sleep(10)"], tmp_path, 0.02)
    assert result["state"] == "timeout" and result["exit"] != 0


def test_public_locations_omit_working_directory():
    raw = {"sourceLocation": {"file": "unit.c", "workingDirectory": "private-machine-path"}, "nested": [{"workingDirectory": "private"}]}
    assert "private" not in json.dumps(native.clean(raw))


CBMC = os.environ.get("CBMC", "")


@pytest.mark.skipif(not CBMC, reason="set CBMC to run the native pilot")
@pytest.mark.parametrize("case,unwind,verdict", [("original", 4, "counterexample"), ("fixed", 4, "complete"),
                                               ("mutant", 4, "counterexample"), ("vacuous", 4, "vacuous"),
                                               ("loop", 1, "incomplete"), ("loop", 4, "complete")])
def test_real_cbmc_pilot(case, unwind, verdict, tmp_path):
    result = native.check(case, tmp_path / "run", cbmc=CBMC, unwind=unwind)
    assert result["verdict"] == verdict, result
    assert all(stage["state"] == "finished" for stage in result["stages"].values())
    if case in ("original", "mutant") and shutil.which("gcc"):
        statuses = {witness["status"] for witness in result["native_replay"]["witnesses"]}
        assert {"range_counterexample", "undefined_behavior"} <= statuses
