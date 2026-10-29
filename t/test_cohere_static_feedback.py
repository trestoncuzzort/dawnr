"""Reject altered repair evidence, preserve matched calls and keep the original gates."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest
pytest.importorskip("jsonschema")
sys.path.insert(0, str(Path(__file__).parent / "recipes"))
import cohere_static_feedback as feedback
from test_cohere_task_json import conversations, provider, task


@pytest.fixture
def case():
    body = feedback.request_body(conversations())
    wire = feedback.proxy.to_cohere(body, feedback.MODEL, 0, "json-v2")
    document = feedback.codec.contract_document(task())
    document["ensures"][0]["arg2"] = {"var": "undeclared"}
    response = feedback.proxy.structured_reply(provider(document), wire, 8000, feedback.MODEL, "json-v2")
    identity = "source:" + feedback.codec.identity()
    record = {"identity": identity, "request": body, "response": response}
    key = hashlib.sha256(feedback.canonical([identity, body])).hexdigest()
    return {"task_id": 7, "attempt": 0, "source_cache": key + ".json", "record": record}


def test_feedback_keeps_original_evidence_and_exact_diagnostic(case):
    before = deepcopy(case)
    questions = feedback.conversations(case)
    original = case["record"]["request"]["messages"]
    assert questions["fresh"] == original
    assert questions["feedback"][0] == original[0]
    assert questions["feedback"][1]["content"].startswith(original[1]["content"])
    source = case["record"]["response"]["cohere_source"]
    assert source["conversion"]["reason"] in questions["feedback"][1]["content"]
    assert source["response"]["message"]["content"][0]["text"] in questions["feedback"][1]["content"]
    assert case == before


def test_registered_requests_match_the_real_decoder_for_both_arms(case, tmp_path):
    requests = []
    def post(body):
        requests.append(body)
        return {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}],
                "usage": {"completion_tokens": 0}}
    decoder = feedback.Decoder("unused", feedback.MODEL, "fixture", tmp_path, post=post)
    for messages in feedback.conversations(case).values():
        decoder.one(messages, feedback.MAX_NEW, .7, .95, feedback.STAGE)
        assert requests[-1] == feedback.request_body(messages)
    assert len(requests) == 2 and requests[0] != requests[1]


@pytest.mark.parametrize("changed", ["cache", "wire", "diagnostic", "raw-reply", "native-reply", "incomplete"])
def test_changed_or_nonstatic_source_is_refused(case, changed):
    source = case["record"]["response"]["cohere_source"]
    if changed == "cache":
        case["source_cache"] = "0" * 64 + ".json"
    elif changed == "wire":
        source["request"]["temperature"] = .3
    elif changed == "diagnostic":
        source["conversion"]["reason"] += " altered"
    elif changed == "raw-reply":
        source["response"]["message"]["content"][0]["text"] = json.dumps(feedback.codec.contract_document(task()))
    elif changed == "native-reply":
        case["record"]["response"]["choices"][0]["message"]["content"] = "fabricated"
    else:
        source["response"]["finish_reason"] = "MAX_TOKENS"
    with pytest.raises(ValueError):
        feedback.conversations(case)


def test_wrong_problem_or_heldout_membership_cannot_reach_generation(case, monkeypatch):
    import spec_first_rows
    pool = {7: {"rec": {"code": "pass"}}}
    monkeypatch.setattr(spec_first_rows, "spec_question", lambda *_: conversations())
    feedback.check_membership({"cases": [case]}, pool, {7})
    with pytest.raises(ValueError, match="training side"):
        feedback.check_membership({"cases": [case]}, pool, set())
    with pytest.raises(ValueError, match="unique"):
        feedback.check_membership({"cases": [case, case]}, pool, {7})
    case["record"]["request"]["messages"][1]["content"] = "different problem"
    with pytest.raises(ValueError, match="declared problem"):
        feedback.check_membership({"cases": [case]}, pool, {7})


def test_restart_reuses_answers_and_refuses_changed_protocol(case, tmp_path, monkeypatch):
    calls = []
    def post(_self, body):
        calls.append(body)
        return {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}],
                "usage": {"completion_tokens": 0}}
    monkeypatch.setattr(feedback.Decoder, "_post", post)
    expected = {"identity": "fixture", "model": feedback.MODEL, "panel_sha256": "fixed-panel",
                "route_args": ["fixture"], "driver_sha256": "fixed-driver", "sources": {},
                "requests": [feedback.request_body(m) for m in feedback.conversations(case).values()]}
    endpoint = "http://127.0.0.1:8854/v1/chat/completions"
    feedback.generate(expected, endpoint, tmp_path)
    feedback.generate(expected, endpoint, tmp_path)
    assert len(calls) == 2
    expected["driver_sha256"] = "changed"
    with pytest.raises(ValueError, match="procedure changed"):
        feedback.generate(expected, endpoint, tmp_path)
    assert len(calls) == 2


def test_vacuous_repairs_cannot_bypass_the_visible_gate(tmp_path, monkeypatch):
    import spec_check
    import spec_experiment
    from test_spec_quality import ENTRY, _task

    monkeypatch.setattr(spec_experiment, "pool", lambda _name: {7: ENTRY})
    monkeypatch.setattr(spec_check, "check_task", lambda *_: pytest.fail("a vacuous contract must fail before references"))
    selection = {"cases": [{"task_id": 7}]}
    bodies = [feedback.request_body(conversations())]
    expected = {"requests": bodies, "identity": "fixture", "request_order": [{"case_index": 0, "task_id": 7, "arm": "feedback"}]}
    body = bodies[0]
    raw = provider(feedback.codec.contract_document(_task("true")))
    response = feedback.proxy.structured_reply(raw, feedback.proxy.to_cohere(body, feedback.MODEL, 0, "json-v2"),
                                                8000, feedback.MODEL, "json-v2")
    assert response["cohere_source"]["conversion"]["status"] == "accepted"
    key = hashlib.sha256(feedback.canonical(["fixture", body])).hexdigest()
    (tmp_path / (key + ".json")).write_text(json.dumps({"response": response}))
    commands = []
    monkeypatch.setattr(feedback.subprocess, "run", lambda args, **_kwargs: commands.append(args))
    feedback.score(selection, expected, tmp_path, tmp_path)
    for arm in feedback.ARMS:
        rows = [json.loads(s) for s in (tmp_path / (arm + "-prestrict.jsonl")).read_text().splitlines()]
        assert len(rows) == 1 and rows[0]["task_id"] == 7 and rows[0]["tasks"] == []
    assert len(commands) == 2
    assert all(c[c.index("--draws") + 1] == "1000" and c[c.index("--floor") + 1] == "0.9" for c in commands)
