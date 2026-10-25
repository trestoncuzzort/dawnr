#!/usr/bin/env python3
"""Reconcile a completed JSON teacher cache with its expected requests and billing.

This reads private evidence and repeats only schema/static/representation checks. It
does not call a model, execute references, grade proofs, or decide whether to expand.
Expected requests must be prepared independently of the run being checked.
Verify the downloaded artifact digest separately before opening it; this checks
the correspondence of its preserved requests, responses and accounting records.

Sources: cohere_proxy.py (wire mapping, rounding and ledger fields), v6_server_route.py
(cache identity), cohere_run_report.py (recorded cost), cohere_json_smoke.py (raw evidence).
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

import cohere_proxy as proxy
import cohere_task_json as codec
from v6_server_route import canonical


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(text):
    return json.loads(text, object_pairs_hook=codec.unique_object, parse_constant=codec.reject_constant)


def rows(path):
    return [read_json(line) for line in path.read_text().splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def amount(value):
    require(type(value) in (int, float, str), "invalid billing number")
    result = Decimal(str(value))
    require(result.is_finite() and result >= 0, "invalid billing number")
    return result


def error_kind(error):
    if error == "ceiling":
        return error
    if re.match(r"HTTP \d{3}:", error):
        return error.split(":", 1)[0]
    return "network" if error.startswith("network:") else "proxy_error"


def audit(cache: Path, ledger: Path, log: Path, expected: dict) -> dict:
    """Require a complete request set, replayable conversion, and a billing bijection.

    Concurrent ledger entries have no request identifier. Match billed input/output,
    rounded cost, model and tag as a multiset, retaining duplicate multiplicities.
    This reconciles recorded charges; it does not establish an invoiced amount or
    the number of physical API attempts hidden inside the proxy's retry policy.
    """
    identity, model, tag = expected["identity"], expected["model"], expected["tag"]
    require(expected["codec_identity"] == codec.identity(), "codec differs from the registered transport")
    require(identity.endswith(":" + codec.identity()), "request identity does not bind the codec")
    prices = expected["prices_per_million"]
    require(list(proxy.PRICE[model]) == prices, "price basis differs from the registered proxy")
    protocol = read_json((cache / "protocol.json").read_text())
    require(protocol == read_json((cache / "completed.json").read_text()), "route is not complete")
    for field in ("identity", "model", "panel_sha256", "route_args", "driver_sha256", "sources"):
        require(protocol[field] == expected[field], "route protocol differs: " + field)

    requests = expected["requests"]
    require(bool(requests), "empty expected request set")
    expected_keys = {hashlib.sha256(canonical([identity, body])).hexdigest(): body for body in requests}
    require(len(expected_keys) == len(requests), "duplicate expected candidate requests")
    files = {p.stem: p for p in cache.glob("*.json") if p.name not in ("protocol.json", "completed.json")}
    require(set(files) == set(expected_keys), "saved requests differ from the expected candidates")

    charges, successful_logs, failed_logs = Counter(), Counter(), Counter()
    finishes, conversions, refusals, errors = Counter(), Counter(), Counter(), Counter()
    raw_responses, promoted = 0, 0
    for key, body in expected_keys.items():
        record = read_json(files[key].read_text())
        require(record["identity"] == identity and record["request"] == body, "cached request changed")
        response = record["response"]
        if "error" in response:
            error = response["error"]
            require(isinstance(error, str), "invalid proxy error")
            require(error != "billing_unresolved", "missing billed-unit evidence; spending is unresolved")
            require("cohere_source" not in response, "an error hides a provider response requiring billing review")
            empty = {"model": model, "choices": [{"index": 0,
                     "message": {"role": "assistant", "content": ""}, "finish_reason": "length"}],
                     "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, "error": error}
            require(response == empty, "failed request contains an unexpected answer")
            errors[error_kind(error)] += 1
            failed_logs[error] += 1
            continue

        source = response["cohere_source"]
        require(source["representation"] == "json" and source["identity"] == codec.identity(),
                "provider evidence has a different representation")
        wire = proxy.to_cohere(body, model, expected["think"], "json")
        require(source["request"] == wire, "actual provider request differs from the expected transformation")
        raw = source["response"]
        units = (raw.get("usage") or {}).get("billed_units") or {}
        require(all(type(units.get(k)) is int and units[k] >= 0 for k in ("input_tokens", "output_tokens")),
                "missing billed-unit evidence; spending is unresolved")
        replay = proxy.structured_reply(raw, wire, body["max_tokens"], model)
        require(response == replay, "saved conversion differs from the preserved provider reply")
        bi, bo = float(units["input_tokens"]), float(units["output_tokens"])
        # Reproduce the proxy's per-call binary-float rounding, including half-microdollar cases.
        cost = round(bi * prices[0] / 1e6 + bo * prices[1] / 1e6, 6)
        charges[(model, tag, amount(bi), amount(bo), amount(cost))] += 1
        conversion = source["conversion"]
        success_log = {"ok": True, "stop": response["stop_reason_raw"], "billed_in": bi, "billed_out": bo,
                       "usd": cost, **response["usage"], "conversion_status": conversion["status"]}
        successful_logs[canonical(success_log)] += 1
        raw_responses += 1
        finishes[str(raw.get("finish_reason"))] += 1
        conversions[conversion["status"]] += 1
        if conversion["status"] == "refused":
            refusals[conversion["error_type"]] += 1
        promoted += bool(conversion.get("header_promoted"))

    actual_charges = Counter()
    ledger_rows = rows(ledger)
    for row in ledger_rows:
        require(row["kind"] == "chat-proxy", "unexpected charge kind")
        actual_charges[(row["model"], row["tag"], amount(row["in"]), amount(row["out"]), amount(row["usd"]))] += 1
    require(actual_charges == charges, "ledger does not match all preserved billed units and charges")
    actual_successes, actual_failures = Counter(), Counter()
    log_rows = rows(log)
    for row in log_rows:
        require(type(row["ok"]) is bool, "invalid proxy log status")
        if row["ok"]:
            actual_successes[canonical({k: v for k, v in row.items() if k not in ("t", "seconds")})] += 1
        else:
            actual_failures[row["error"]] += 1
    require(actual_successes == successful_logs and actual_failures == failed_logs,
            "proxy log does not match every cached success and error")

    spent = sum((amount(row["usd"]) for row in ledger_rows), Decimal(0))
    return {"logical_candidates": len(requests), "provider_successful_responses": raw_responses,
            "provider_error_replies": sum(n for k, n in errors.items() if k != "ceiling"),
            "error_kinds": dict(errors), "ceiling_replies": errors["ceiling"],
            "finish_reasons": dict(finishes), "conversion_statuses": dict(conversions),
            "conversion_refusal_types": dict(refusals), "checked_header_promotions": promoted,
            "accepted_conversion_fraction": conversions["accepted"] / len(requests),
            "ledger_entries": len(ledger_rows), "proxy_log_entries": len(log_rows), "run_usd": str(spent),
            "all_expected_requests_match": True, "all_wire_requests_match": True,
            "all_saved_conversions_match": True, "all_billed_units_and_recorded_charges_match": True,
            "source_hashes_verified": len(protocol["sources"]),
            "billing_match_basis": "multiset of model, tag, billed input/output and rounded charge; no request IDs",
            "physical_api_attempts": "not observable from final replies; proxy may retry",
            "cost_scope": "recorded charges, not a provider invoice",
            "input_hashes": {"ledger": sha(ledger), "proxy_log": sha(log), "protocol": sha(cache / "protocol.json"),
                "cache_file_manifest": hashlib.sha256(canonical({k: sha(files[k]) for k in sorted(files)})).hexdigest()},
            "codec_identity": codec.identity(), "grader_or_model_calls": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cache", "ledger", "log", "expected", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args(argv)
    require(sha(args.expected) == args.expected_sha256, "expected request manifest changed")
    result = audit(args.cache, args.ledger, args.log, read_json(args.expected.read_text()))
    result["input_hashes"]["expected"] = args.expected_sha256
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
