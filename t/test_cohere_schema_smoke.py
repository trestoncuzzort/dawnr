"""Schema validity alone must not pass a malformed, truncated or unaccounted reply."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "recipes"))
import cohere_schema_smoke as smoke


def reply(case, value=None, finish="COMPLETE"):
    return {"finish_reason": finish,
            "message": {"content": [{"type": "text", "text": json.dumps(
                case["expected"] if value is None else value)}]},
            "usage": {"billed_units": {"input_tokens": 100, "output_tokens": 20}}}


@pytest.mark.parametrize("case", smoke.fixtures(), ids=lambda case: case["name"])
def test_expected_contracts_survive_engine_typing_and_exact_roundtrip(case):
    reading = smoke.validate_reply(case, reply(case))
    assert reading["passed"] and reading["roundtrip_equal"]
    if case["name"] == "recursive":
        assert reading["expression_depth"] > 5


@pytest.mark.parametrize("expr", [
    {"int": True}, {"int": 1, "var": "x"}, {"var": "undeclared"},
    {"op": "+", "args": [{"int": 1}]},
    {"op": "==", "args": [{"var": "r"}, {"int": 7}], "extra": 1},
])
def test_invalid_ast_shapes_cannot_pass_through_json(expr):
    case = smoke.fixtures()[0]
    with pytest.raises(ValueError):
        smoke.validate_reply(case, reply(case, {"ensures": expr}))


def test_well_formedness_and_requested_shape_are_separate_checks():
    case = smoke.fixtures()[2]
    wrong_type = {"ensures": {"op": "+", "args": [{"var": "r"}, {"int": 1}]}}
    assert not smoke.validate_reply(case, reply(case, wrong_type))["well_formed"]
    simplified = {"ensures": {"op": "==", "args": [{"var": "r"},
                  {"op": "+", "args": [{"var": "x"}, {"int": 6}]}]}}
    result = smoke.validate_reply(case, reply(case, simplified))
    assert result["well_formed"] and result["roundtrip_equal"]
    assert not result["requested_shape"] and not result["passed"]


def test_truncated_reply_does_not_pass_even_when_its_json_is_complete():
    case = smoke.fixtures()[0]
    result = smoke.validate_reply(case, reply(case, finish="MAX_TOKENS"))
    assert result["requested_shape"] and not result["passed"]


@pytest.mark.parametrize("text", ['{"ensures":1,"ensures":2}', '{"ensures":{"int":NaN}}'])
def test_duplicate_fields_and_nonfinite_json_are_rejected(text):
    case = smoke.fixtures()[0]
    result = reply(case)
    result["message"]["content"][0]["text"] = text
    with pytest.raises(ValueError):
        smoke.validate_reply(case, result)


@pytest.mark.parametrize("units", [{}, {"input_tokens": -1, "output_tokens": 2},
                                   {"input_tokens": 1, "output_tokens": True}])
def test_missing_or_invalid_billing_is_not_zero_cost(units):
    with pytest.raises((KeyError, ValueError)):
        smoke.billed_cost({"usage": {"billed_units": units}})


def test_bounded_run_records_all_calls_and_refuses_directory_reuse(tmp_path):
    cases, calls = smoke.fixtures(), []

    def caller(key, request, attempts, timeout):
        assert attempts == 1 and timeout == 180
        case = cases[len(calls)]
        assert request == case["request"]
        calls.append(request)
        return reply(case)

    out = tmp_path / "run"
    result = smoke.run(out, "unused", caller)
    assert len(calls) == 3 and result["all_conditions_hold"]
    assert result["recorded_cost_usd"] == "0.00135"
    assert len((out / "ledger.jsonl").read_text().splitlines()) == 3
    with pytest.raises(FileExistsError):
        smoke.run(out, "unused", caller)
    assert len(calls) == 3


def test_private_provider_error_stays_private_and_quota_stops_calls(tmp_path, capsys):
    calls = []

    def caller(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("HTTP 429: private-provider-diagnostic")

    out = tmp_path / "run"
    result = smoke.run(out, "unused", caller)
    assert len(calls) == 1 and result["unresolved_billing_or_transport"]
    assert not result["all_conditions_hold"]
    assert "private-provider-diagnostic" not in json.dumps(result) + capsys.readouterr().out
    assert "private-provider-diagnostic" in (out / "inline-error.json").read_text()


def test_success_without_billing_preserves_response_and_stops(tmp_path):
    response = reply(smoke.fixtures()[0])
    response.pop("usage")
    calls = []

    def caller(*args, **kwargs):
        calls.append(1)
        return deepcopy(response)

    out = tmp_path / "run"
    result = smoke.run(out, "unused", caller)
    assert len(calls) == 1 and result["unresolved_billing_or_transport"]
    assert result["cases"][0]["error_kind"] == "missing_billing_evidence"
    assert (out / "inline-response.json").exists()
    assert not result["all_conditions_hold"]
