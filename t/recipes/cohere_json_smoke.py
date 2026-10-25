#!/usr/bin/env python3
"""One private full-schema transport check before the real teacher pilot.

Sources: cohere_schema_smoke.py (billing/evidence), v6_server_route.py (the actual decoder),
https://docs.cohere.com/docs/structured-outputs. This synthetic fixture is not training data.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys

import cohere_proxy
import cohere_task_json as codec
from cohere_schema_smoke import billed_cost, write_json
from v6_server_route import Decoder

MODEL = "command-a-03-2025"
MAX_NEW = 8000
STAGE = 32000
SYNTHETIC = """t 1
gate recursion
task transportProbe(s: seq) returns (r: int)
  requires forall i in [0, len(s)) . s[i] >= 0
  ensures r == upto(s, len(s))
  ensures r >= 0
spec fun upto(xs: seq, n: int): int
  decreases n
= if n <= 0 or n > len(xs) then 0 else upto(xs, n - 1) + xs[n - 1]
{
}
"""


def inputs(primer: str) -> dict:
    task = codec.surface.parse(SYNTHETIC)
    document = codec.contract_document(task)
    messages = [{"role": "system", "content": codec.spec_first_rows.SPEC_SYSTEM + "\n\n" + primer},
                {"role": "user", "content": "This is a synthetic transport check. Return this exact JSON contract "
                 "without changing values or reordering clauses:\n" + json.dumps(document)}]
    codec.messages(messages)  # the same six examples must convert before any API call
    return {"model": MODEL, "messages": messages, "expected": task, "stage": STAGE, "max_new": MAX_NEW,
            "identity": "teacher-cohere:" + MODEL + ":full-schema-smoke:" + codec.identity()}


def run(output: Path, key: str, primer: str, caller=cohere_proxy.call, expected_input_sha256=None) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    prepared = inputs(primer)
    write_json(output / "inputs.json", prepared)
    if expected_input_sha256 is not None and hashlib.sha256((output / "inputs.json").read_bytes()).hexdigest() != expected_input_sha256:
        raise ValueError("registered inputs changed before the API request")
    calls = []
    reading = {"case": "full_teacher_schema", "api_success": False, "passed": False}
    cost = None

    def post(body):
        nonlocal cost
        if calls:
            raise ValueError("the registered smoke allows only one API request")
        request = cohere_proxy.to_cohere(body, MODEL, 0, "json")
        calls.append(request)
        write_json(output / "request.json", request)
        result = caller(key, request, attempts=1, timeout=180)
        write_json(output / "response.json", result)
        reading["api_success"] = True
        cost, units = billed_cost(result)
        (output / "ledger.jsonl").write_text(json.dumps({"model": MODEL, "kind": "full-schema-smoke",
            "usd": str(cost), **units}) + "\n")
        reading["billed_units"] = units
        return cohere_proxy.structured_reply(result, request, MAX_NEW, MODEL)

    decoder = Decoder("unused", MODEL, prepared["identity"], output / "cache", concurrency=1, post=post)
    try:
        text, stopped, tokens = decoder.one(prepared["messages"], MAX_NEW, 0, 0.95, STAGE)
        task = codec.surface.parse(codec.FENCE.search(text)[1])
        reading.update({"complete": stopped, "nonempty": bool(text), "completion_tokens": tokens,
                        "matches_original_contract": task == prepared["expected"],
                        "schema_and_static_checked": True})
        reading["passed"] = stopped and task == prepared["expected"]
    except Exception as error:
        reading["error_kind"] = type(error).__name__
        write_json(output / "error.json", {"error": str(error)})
    record = {"kind": "Full teacher schema and decoder transport smoke; no quality benchmark",
              "model": MODEL, "recorded_cost_usd": str(cost) if cost is not None else None,
              "unresolved_billing_or_transport": cost is None,
              "reservation_usd": "1", "requests": len(calls), "automatic_retries": 0,
              "cases": [reading], "all_conditions_hold": reading["passed"] and cost is not None and cost <= 1,
              "input_sha256": hashlib.sha256((output / "inputs.json").read_bytes()).hexdigest(),
              "primer_sha256": hashlib.sha256(primer.encode()).hexdigest(),
              "schema_sha256": hashlib.sha256(codec.canonical(codec.schema())).hexdigest(),
              "codec_identity": codec.identity(),
              "dependency_versions": {name: version(name) for name in
                                      ("jsonschema", "jsonschema-specifications", "referencing", "rpds-py")},
              "code_sha256": {str(p.relative_to(codec.HERE.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in [Path(__file__).resolve(), Path(cohere_proxy.__file__), Path(codec.__file__),
                                        Path(__file__).with_name("cohere_schema_smoke.py"),
                                        Path(__file__).with_name("v6_server_route.py"),
                                        Path(__file__).with_name("spec_contract.py"),
                                        Path(__file__).with_name("teacher_primer.py"),
                                        codec.HERE / "surface.py", codec.HERE / "check_wf.py",
                                        codec.HERE / "spec_first_rows.py"]}}
    write_json(output / "summary.json", record)
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--primer", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    args = parser.parse_args(argv)
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("paid capability calls run on GitHub")
    key = os.environ.get("COHERE_API_KEY", "").strip()
    if not key:
        parser.error("COHERE_API_KEY is missing")
    os.umask(0o077)
    result = run(args.out, key, args.primer.read_text(), expected_input_sha256=args.input_sha256)
    return 0 if result["all_conditions_hold"] else 1


if __name__ == "__main__":
    sys.exit(main())
