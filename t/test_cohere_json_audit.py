"""Reject missing or changed teacher evidence before using a grant-yield report."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest
pytest.importorskip("jsonschema", reason="optional JSON teacher transport")

sys.path.insert(0, str(Path(__file__).resolve().parent / "recipes"))
import cohere_json_audit as audit
import cohere_proxy as proxy
import cohere_task_json as codec
from test_cohere_task_json import conversations, provider, task
from v6_server_route import Decoder, canonical


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    """Run the real handler, ledger writer and decoder with an in-memory provider."""
    ledger, log, cache = tmp_path / "ledger.jsonl", tmp_path / "proxy.jsonl", tmp_path / "cache"
    monkeypatch.setattr(proxy, "LEDGER", str(ledger))
    model, tag = "command-a-03-2025", "fixture"
    identity = "teacher-cohere:" + model + ":fixture:" + codec.identity()
    server = SimpleNamespace(model=model, representation="json", think=0, key="unused", spent=0, calls=0,
        ceiling=25, unaccounted_response=False, tag=tag, gate=threading.Semaphore(1), lock=threading.Lock(),
        log_path=str(log))
    server.log = lambda record: proxy.Server.log(server, record)
    server.charge = lambda usd, meta: proxy.Server.charge(server, usd, meta)
    requests = []
    pending = []

    def api(_key, _request):
        value = pending.pop(0)
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)

    monkeypatch.setattr(proxy, "call", api)

    def post(body):
        requests.append(deepcopy(body))
        handler = object.__new__(proxy.Handler)
        data = json.dumps(body).encode()
        handler.path, handler.headers = "/v1/chat/completions", {"Content-Length": str(len(data))}
        handler.rfile, handler.server = io.BytesIO(data), server
        sent = []
        handler._send = lambda code, reply: sent.append((code, reply))
        handler.do_POST()
        assert sent[0][0] == 200
        return sent[0][1]

    def build(responses=None):
        invalid = codec.contract_document(task())
        invalid["ensures"][0]["args"][1] = {"var": "undeclared"}
        if responses is None:
            responses = [provider(), provider(invalid), provider(finish="MAX_TOKENS"),
                         RuntimeError("HTTP 422: NO_VALID_RESPONSE_GENERATED")]
            responses[1]["usage"]["billed_units"]["input_tokens"] = 101
        pending.extend(responses)
        decoder = Decoder("unused", model, identity, cache, post=post)
        for i in range(len(responses)):
            decoder.one(conversations(), 8000, 0 if i == 0 else 0.7, 0.95, 30100 + i)
        protocol = {"identity": identity, "model": model, "panel_sha256": "fixture-panel", "sources": {"t/fixture.py": "fixed"},
                    "route_args": ["--specs-only"], "driver_sha256": audit.sha(Path(__file__).parent / "recipes/v6_server_route.py")}
        for name in ("protocol.json", "completed.json"):
            (cache / name).write_text(json.dumps(protocol))
        manifest = {**protocol, "tag": tag, "codec_identity": codec.identity(), "think": 0,
                    "prices_per_million": [2.5, 10], "requests": requests}
        return cache, ledger, log, manifest
    return build


def test_real_cache_and_ledger_include_paid_conversion_refusals(evidence):
    cache, ledger, log, expected = evidence()
    result = audit.audit(cache, ledger, log, expected)
    assert result["logical_candidates"] == 4 and result["provider_successful_responses"] == 3
    assert result["ledger_entries"] == 3 and result["proxy_log_entries"] == 4
    assert result["conversion_statuses"] == {"accepted": 1, "refused": 2}
    assert result["finish_reasons"] == {"COMPLETE": 2, "MAX_TOKENS": 1}
    assert result["error_kinds"] == {"HTTP 422": 1} and result["accepted_conversion_fraction"] == 0.25
    assert result["all_billed_units_and_recorded_charges_match"]


@pytest.mark.parametrize("change", ["missing", "duplicate", "different_units", "different_cost"])
def test_ledger_requires_matching_units_cost_and_multiplicity(evidence, change):
    cache, ledger, log, expected = evidence()
    rows = audit.rows(ledger)
    if change == "missing":
        rows.pop()
    elif change == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif change == "different_units":
        rows[0]["in"] += 1
    else:
        rows[0]["usd"] += 0.000001
    ledger.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="ledger does not match"):
        audit.audit(cache, ledger, log, expected)


def test_changed_prompt_fails_even_with_consistent_recomputed_cache_and_wire(evidence):
    cache, ledger, log, expected = evidence([provider()])
    path = next(p for p in cache.glob("*.json") if p.name not in ("protocol.json", "completed.json"))
    record = json.loads(path.read_text())
    record["request"]["messages"][1]["content"] = "A different, easier problem."
    record["response"]["cohere_source"]["request"] = proxy.to_cohere(record["request"], expected["model"], 0, "json")
    changed_key = hashlib.sha256(canonical([expected["identity"], record["request"]])).hexdigest()
    path.unlink()
    (cache / (changed_key + ".json")).write_text(json.dumps(record))
    with pytest.raises(ValueError, match="expected candidates"):
        audit.audit(cache, ledger, log, expected)


@pytest.mark.parametrize("change", ["wire", "converted_content", "conversion_status", "billing"])
def test_saved_provider_evidence_must_reproduce_the_delivered_reply(evidence, change):
    cache, ledger, log, expected = evidence([provider()])
    path = next(p for p in cache.glob("*.json") if p.name not in ("protocol.json", "completed.json"))
    record = json.loads(path.read_text())
    reply = record["response"]
    if change == "wire":
        reply["cohere_source"]["request"]["temperature"] = 1
    elif change == "converted_content":
        reply["choices"][0]["message"]["content"] = ""
    elif change == "conversion_status":
        reply["cohere_source"]["conversion"]["status"] = "refused"
    else:
        reply["cohere_source"]["response"]["usage"].pop("billed_units")
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        audit.audit(cache, ledger, log, expected)


def test_missing_billing_is_unresolved_and_never_zero_cost(evidence):
    raw = provider()
    raw["usage"].pop("billed_units")
    cache, ledger, log, expected = evidence([raw])
    with pytest.raises(ValueError, match="spending is unresolved"):
        audit.audit(cache, ledger, log, expected)


def test_missing_proxy_error_is_not_a_complete_accounting(evidence):
    cache, ledger, log, expected = evidence()
    log.write_text("".join(json.dumps(row) + "\n" for row in audit.rows(log) if row["ok"]))
    with pytest.raises(ValueError, match="proxy log does not match"):
        audit.audit(cache, ledger, log, expected)


def test_stale_completion_receipt_cannot_authorize_an_audit(evidence):
    cache, ledger, log, expected = evidence()
    (cache / "completed.json").write_text("{}")
    with pytest.raises(ValueError, match="route is not complete"):
        audit.audit(cache, ledger, log, expected)


def test_changed_source_cannot_match_the_registered_run(evidence):
    cache, ledger, log, expected = evidence()
    protocol = json.loads((cache / "protocol.json").read_text())
    protocol["sources"]["t/fixture.py"] = "changed"
    for name in ("protocol.json", "completed.json"):
        (cache / name).write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="route protocol differs: sources"):
        audit.audit(cache, ledger, log, expected)


def test_changed_expected_manifest_fails_before_reading_results(tmp_path):
    path = tmp_path / "expected.json"
    path.write_text("{}")
    with pytest.raises(ValueError, match="expected request manifest changed"):
        audit.main(["--expected", str(path), "--expected-sha256", "0" * 64,
                    "--cache", "absent", "--ledger", "absent", "--log", "absent", "--out", "absent"])
