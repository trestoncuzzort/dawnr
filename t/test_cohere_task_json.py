"""Exercise the real contract schema, preserved prompt evidence and paid-reply refusal paths."""
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest
pytest.importorskip("jsonschema", reason="optional JSON teacher transport; install recipes/requirements-cohere-json.txt")
from jsonschema import Draft202012Validator, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent / "recipes"))
import cohere_proxy as proxy
import cohere_task_json as codec
import spec_first_rows
import surface
import teacher_primer


def task(name="example", version=1):
    return {"t": version, "gate": "loops", "name": name,
            "params": [{"name": "x", "type": "int"}], "returns": [{"name": "r", "type": "int"}],
            "requires": [], "ensures": [{"op": "==", "args": [{"var": "r"}, {"var": "x"}]}], "body": []}


def conversations():
    examples = [{"problem": "original example " + str(i), "tests": ["assert identity(3) == 3"],
                 "python": "def identity(x): return x", "spec": surface.print_task(task("example" + str(i), 0 if i == 0 else 1))}
                for i in range(6)]
    return [{"role": "system", "content": spec_first_rows.SPEC_SYSTEM + "\n\n" + teacher_primer.render(examples)},
            {"role": "user", "content": "Original problem, tests, signature and Python remain byte-identical."}]


def body():
    return {"messages": conversations(), "max_tokens": 8000, "temperature": 0.7, "top_p": 0.95, "seed": 42}


def provider(value=None, finish="COMPLETE"):
    return {"finish_reason": finish, "message": {"content": [
        {"type": "text", "text": json.dumps(codec.contract_document(task()) if value is None else value)}]},
        "usage": {"tokens": {"input_tokens": 100, "output_tokens": 20},
                  "billed_units": {"input_tokens": 100, "output_tokens": 20}}}


def test_schema_and_all_six_converted_examples_preserve_the_problem_evidence():
    Draft202012Validator.check_schema(codec.schema())
    original = conversations()
    frozen = deepcopy(original)
    request = proxy.to_cohere(body(), "command-a-03-2025", 0, "json")
    assert original == frozen and request["messages"][1] == original[1]
    converted = request["messages"][0]["content"]
    assert converted.count("```json") == 6 and "```t" not in converted
    for i in range(6):
        assert "original example " + str(i) in converted
    assert converted.count("assert identity(3) == 3") == 6
    assert converted.count("def identity(x): return x") == 6
    assert request["response_format"]["schema"] == codec.schema()
    assert (request["max_tokens"], request["temperature"], request["p"], request["seed"]) == (8000, 0.7, 0.95, 42)


@pytest.mark.parametrize("text", [
    't 1 task bounded(s: seq) returns (r: bool) ensures r == (forall i in [0, len(s)) . s[i] >= 0) {}',
    't 1 gate recursion task prefix(s: seq) returns (r: int) ensures r == upto(s, len(s)) '
    'spec fun upto(xs: seq, n: int): int decreases n = if n <= 0 then 0 else upto(xs, n - 1) + xs[n - 1] {}',
    't 1 task filtered(s: seq) returns (r: seq) ensures r == [x for x in s if x > 0] {}',
    't 1 task folded(s: seq) returns (r: int) ensures r == fold((a, x) => a + x, 0, s) {}',
    'datatype Choice = none | some(value: int)\nt 1 task inspect(x: Choice) returns (r: bool) ensures r == true {}',
    't 1 task nested(s: seq<seq>) returns (r: (int, seq)) ensures r == (len(s), []) {}',
])
def test_real_language_features_fit_the_schema_and_roundtrip(text):
    expected = surface.parse(text)
    document = codec.contract_document(expected)
    Draft202012Validator(codec.schema()).validate(document)
    assert codec.decode_contract(json.dumps(document)) == expected


def test_schema_rejects_extra_fields_and_noncanonical_literals():
    document = codec.contract_document(task())
    with pytest.raises(ValidationError):
        codec.decode_contract(json.dumps({**document, "body": []}))
    document["ensures"][0]["args"][1] = {"int": True}
    with pytest.raises(ValidationError):
        codec.decode_contract(json.dumps(document))


def test_duplicate_json_fields_are_not_silently_overwritten():
    with pytest.raises(ValueError, match="duplicate"):
        codec.decode_contract('{"t":1,"t":0}')


def test_incomplete_provider_reply_cannot_admit_an_otherwise_valid_contract():
    response = proxy.structured_reply(provider(finish="MAX_TOKENS"), {}, 8000, "command-a-03-2025")
    assert response["choices"][0]["message"]["content"] == ""
    assert response["cohere_source"]["conversion"]["status"] == "refused"


def test_surface_mode_retains_its_original_wire_behavior():
    request = proxy.to_cohere(body(), "command-a-03-2025", 0)
    assert request["messages"] == conversations() and "response_format" not in request
    result = provider()
    assert proxy.from_cohere(result, 8000, "command-a-03-2025")["choices"][0]["message"]["content"] == result["message"]["content"][0]["text"]


def handler(monkeypatch, result):
    charges, logs, sent, calls = [], [], [], []
    server = SimpleNamespace(model="command-a-03-2025", representation="json", think=0, key="unused",
                             spent=0, ceiling=25, unaccounted_response=False, tag="fixture",
                             gate=threading.Semaphore(1), lock=threading.Lock(), log=logs.append,
                             charge=lambda usd, meta: charges.append((usd, meta)))
    def api(key, request):
        calls.append(deepcopy(request))
        return deepcopy(result)
    monkeypatch.setattr(proxy, "call", api)
    def post(payload):
        h = object.__new__(proxy.Handler)
        data = json.dumps(payload).encode()
        h.path, h.headers, h.rfile, h.server = "/v1/chat/completions", {"Content-Length": str(len(data))}, io.BytesIO(data), server
        h._send = lambda status, response: sent.append((status, response))
        h.do_POST()
        return sent[-1][1]
    return post, charges, logs, calls


def test_invalid_paid_json_is_charged_and_preserved_but_not_sent_as_a_contract(monkeypatch):
    bad = codec.contract_document(task())
    bad["ensures"][0]["args"][1] = {"var": "undeclared"}
    raw = provider(bad)
    post, charges, logs, calls = handler(monkeypatch, raw)
    response = post(body())
    assert len(calls) == len(charges) == 1 and charges[0][0] > 0
    assert response["choices"][0]["message"]["content"] == ""
    source = response["cohere_source"]
    assert source["response"] == raw and source["request"] == calls[0]
    assert source["conversion"]["status"] == "refused" and logs[-1]["conversion_status"] == "refused"


def test_valid_reply_preserves_actual_api_evidence_and_passes_the_route(monkeypatch):
    raw = provider()
    post, charges, _, calls = handler(monkeypatch, raw)
    response = post(body())
    text = response["choices"][0]["message"]["content"]
    assert surface.parse(codec.FENCE.search(text)[1]) == task()
    assert response["cohere_source"]["response"] == raw
    assert response["cohere_source"]["request"] == calls[0]
    assert response["cohere_source"]["identity"] == codec.identity() and len(charges) == 1


def test_missing_billing_preserves_evidence_and_stops_further_provider_calls(monkeypatch):
    raw = provider()
    raw["usage"].pop("billed_units")
    post, charges, _, calls = handler(monkeypatch, raw)
    first = post(body())
    assert first["error"] == "billing_unresolved" and first["cohere_source"]["response"] == raw
    assert post(body())["error"] == "billing_unresolved"
    assert len(calls) == 1 and not charges


def test_full_schema_smoke_uses_the_real_decoder_and_one_metered_request(tmp_path):
    import cohere_json_smoke as smoke
    primer = conversations()[0]["content"][len(spec_first_rows.SPEC_SYSTEM + "\n\n"):]
    prepared = smoke.inputs(primer)
    calls = []
    def caller(key, request, attempts, timeout):
        assert attempts == 1 and timeout == 180 and request["max_tokens"] == 8000
        assert request["response_format"]["schema"] == codec.schema()
        calls.append(request)
        return provider(codec.contract_document(prepared["expected"]))
    output = tmp_path / "smoke"
    result = smoke.run(output, "unused", primer, caller)
    assert result["all_conditions_hold"] and result["requests"] == len(calls) == 1
    assert not result["unresolved_billing_or_transport"]
    caches = list((output / "cache").glob("*.json"))
    assert len(caches) == 1
    saved = json.loads(caches[0].read_text())
    assert saved["response"]["cohere_source"]["request"] == calls[0]
    assert saved["identity"] == prepared["identity"]


def test_full_schema_smoke_refuses_changed_registered_inputs_before_spending(tmp_path):
    import cohere_json_smoke as smoke
    primer = conversations()[0]["content"][len(spec_first_rows.SPEC_SYSTEM + "\n\n"):]
    def forbidden(*args, **kwargs):
        raise AssertionError("changed inputs reached the provider")
    with pytest.raises(ValueError, match="registered inputs changed"):
        smoke.run(tmp_path / "smoke", "unused", primer, forbidden, expected_input_sha256="0" * 64)
