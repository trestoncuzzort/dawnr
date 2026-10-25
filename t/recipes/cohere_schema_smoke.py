#!/usr/bin/env python3
"""Three synthetic schema-capability calls, with private replies and aggregate receipts.

Sources: https://docs.cohere.com/docs/structured-outputs;
https://docs.cohere.com/reference/chat; t/SPEC.md; cohere_proxy.py.
This probes a small expression subset, not teacher quality or the full task grammar.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import surface
from check_wf import check_wf
import cohere_proxy

MODEL = "command-a-03-2025"
MAX_NEW = 2048
RESERVATION = Decimal("1")


def object_schema(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def fixtures() -> list[dict]:
    atom = {"anyOf": [object_schema({"int": {"type": "integer"}}),
                      object_schema({"var": {"type": "string", "enum": ["x", "r"]}})]}
    flat = object_schema({"ensures": object_schema({
        "op": {"type": "string", "enum": ["=="]},
        "args": {"type": "array", "items": deepcopy(atom)}})})
    referenced = deepcopy(flat)
    referenced["$defs"] = {"atom": deepcopy(atom)}
    referenced["properties"]["ensures"]["properties"]["args"]["items"] = {"$ref": "#/$defs/atom"}
    recursive = object_schema({"ensures": {"$ref": "#/$defs/expr"}})
    recursive["$defs"] = {"expr": {"anyOf": deepcopy(atom["anyOf"]) + [object_schema({
        "op": {"type": "string", "enum": ["+", "=="]},
        "args": {"type": "array", "items": {"$ref": "#/$defs/expr"}}})]}}
    cases = []
    for name, schema, depth in [("inline", flat, 0), ("references", referenced, 0),
                                ("recursive", recursive, 6)]:
        rhs = {"var": "x"} if depth else {"int": 7}
        for _ in range(depth):
            rhs = {"op": "+", "args": [rhs, {"int": 1}]}
        expected = {"ensures": {"op": "==", "args": [{"var": "r"}, rhs]}}
        instruction = ("r equals ((((((x + 1) + 1) + 1) + 1) + 1) + 1). "
                       "Preserve all six left-associated additions without simplifying."
                       if depth else "r equals the integer 7.")
        prompt = ("Generate a JSON object with the single field ensures. Its value is the expression AST for "
                  + instruction + " Use {\"int\":N} for an integer, {\"var\":NAME} for a variable, and "
                  "{\"op\":OP,\"args\":[LEFT,RIGHT]} for equality (==) or addition (+). "
                  "Put r on the left side of the equality. Return only JSON.")
        request = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                   "stream": False, "temperature": 0, "seed": 31000 + len(cases),
                   "max_tokens": MAX_NEW, "response_format": {"type": "json_object", "schema": schema}}
        assert len(json.dumps(request).encode()) < 16384
        cases.append({"name": name, "request": request, "expected": expected, "rhs": rhs})
    return cases


def unique_object(pairs: list) -> dict:
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON field")
        out[key] = value
    return out


def reject_constant(_value):
    raise ValueError("non-finite JSON number")


def expression_depth(expr, depth=0) -> int:
    """Exact probe subset; reject fields that a permissive schema might let through."""
    if depth > 32 or type(expr) is not dict:
        raise ValueError("invalid expression object or depth")
    if set(expr) == {"int"} and type(expr["int"]) is int:
        return 1
    if set(expr) == {"var"} and expr["var"] in ("x", "r"):
        return 1
    if set(expr) == {"op", "args"} and expr["op"] in ("+", "=="):
        args = expr["args"]
        if type(args) is list and len(args) == 2:
            return 1 + max(expression_depth(x, depth + 1) for x in args)
    raise ValueError("expression fields, operator or arity outside the probe subset")


def validate_reply(case: dict, result: dict) -> dict:
    message = result.get("message") or {}
    if type(message) is not dict or type(message.get("content")) is not list:
        raise ValueError("missing response content blocks")
    blocks = message["content"]
    if any(type(b) is not dict or (b.get("type") == "text" and type(b.get("text")) is not str)
           for b in blocks):
        raise ValueError("invalid response content block")
    text = "".join(b["text"] for b in blocks if b.get("type") == "text")
    metrics = {"complete": result.get("finish_reason") == "COMPLETE", "nonempty": bool(text.strip()),
               "valid_ast": False, "well_formed": False, "roundtrip_equal": False,
               "requested_shape": False, "expression_depth": None}
    value = json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
    if type(value) is not dict or set(value) != {"ensures"}:
        raise ValueError("reply must contain exactly one ensures expression")
    metrics["expression_depth"] = expression_depth(value["ensures"])
    metrics["valid_ast"] = True
    task = {"t": 0, "name": "schemaProbe", "params": [{"name": "x", "type": "int"}],
            "returns": [{"name": "r", "type": "int"}], "requires": [],
            "ensures": [value["ensures"]], "body": [{"assign": ["r", case["rhs"]]}]}
    metrics["well_formed"] = not check_wf(task)
    if metrics["well_formed"]:
        metrics["roundtrip_equal"] = surface.parse(surface.print_task(task)) == task
    metrics["requested_shape"] = value == case["expected"]
    metrics["passed"] = all(metrics[k] for k in ["complete", "nonempty", "valid_ast", "well_formed",
                                                "roundtrip_equal", "requested_shape"])
    return metrics


def billed_cost(result: dict) -> tuple[Decimal, dict]:
    units = result["usage"]["billed_units"]
    counts = {}
    for name in ("input_tokens", "output_tokens"):
        value = units[name]
        if type(value) is not int or value < 0:
            raise ValueError("missing or invalid billed units")
        counts[name] = value
    pi, po = map(lambda x: Decimal(str(x)), cohere_proxy.PRICE[MODEL])
    return (counts["input_tokens"] * pi + counts["output_tokens"] * po) / Decimal(1000000), counts


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def run(output: Path, key: str, caller=cohere_proxy.call) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    cases = fixtures()
    write_json(output / "inputs.json", cases)
    spent, readings, uncertain = Decimal(0), [], False
    for case in cases:
        if uncertain or spent >= RESERVATION:
            break
        reading = {"case": case["name"], "attempted": True, "api_success": False, "passed": False}
        try:
            result = caller(key, case["request"], attempts=1, timeout=180)
        except (RuntimeError, ValueError, OSError) as error:
            # Provider diagnostics can contain private text. Only a category leaves the archive.
            write_json(output / (case["name"] + "-error.json"), {"error": str(error)})
            status = re.match(r"HTTP (\d{3}):", str(error))
            reading["error_kind"] = "http_" + status[1] if status else "transport"
            uncertain = not status or status[1] != "400"
            readings.append(reading)
            continue
        write_json(output / (case["name"] + "-response.json"), result)
        reading["api_success"] = True
        try:
            cost, units = billed_cost(result)
        except (KeyError, TypeError, ValueError):
            reading["error_kind"] = "missing_billing_evidence"
            uncertain = True
            readings.append(reading)
            continue
        spent += cost
        reading.update({"cost_usd": str(cost), "billed_units": units})
        with (output / "ledger.jsonl").open("a") as ledger:
            ledger.write(json.dumps({"model": MODEL, "kind": "schema-smoke", "tag": case["name"],
                                     "usd": str(cost), **units}) + "\n")
        try:
            reading.update(validate_reply(case, result))
        except (ValueError, KeyError, TypeError, RecursionError) as error:
            reading["error_kind"] = "invalid_reply"
            write_json(output / (case["name"] + "-validation-error.json"), {"error": str(error)})
        readings.append(reading)
    result = {"kind": "Synthetic schema capability smoke; not a teacher-quality benchmark",
              "model": MODEL, "max_new": MAX_NEW, "request_limit": len(cases), "automatic_retries": 0,
              "reservation_usd": str(RESERVATION), "recorded_cost_usd": str(spent),
              "unresolved_billing_or_transport": uncertain, "cases": readings,
              "all_conditions_hold": len(readings) == len(cases) and all(r["passed"] for r in readings)
                                     and not uncertain and spent <= RESERVATION,
              "input_sha256": hashlib.sha256((output / "inputs.json").read_bytes()).hexdigest(),
              "code_sha256": {str(p.relative_to(HERE.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in [Path(__file__).resolve(), Path(cohere_proxy.__file__),
                                        HERE / "surface.py", HERE / "check_wf.py"]}}
    write_json(output / "summary.json", result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("paid capability calls run through cohere-schema-smoke.yml on GitHub")
    key = os.environ.get("COHERE_API_KEY", "").strip()
    if not key:
        parser.error("COHERE_API_KEY is missing")
    os.umask(0o077)
    result = run(args.out, key)
    return 0 if result["all_conditions_hold"] else 1


if __name__ == "__main__":
    sys.exit(main())
