#!/usr/bin/env python3
"""Structured contract transport for the existing specification-only teacher.

Source: https://docs.cohere.com/docs/structured-outputs; t/SPEC.md;
t/check_wf.py and t/surface.py define the supported AST and its exact round trip.
No reference check, acceptance floor, or language semantics changes here.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import check_wf
import spec_first_rows
import surface
import teacher_primer
from spec_contract import checked_contract

REQUIRED = {"t", "name", "params", "returns", "requires", "ensures"}
OPTIONAL = {"gate", "spec_funs", "datatypes", "modifies", "decreases"}
FENCE = re.compile(r"```t\s*\n(.*?)```", re.DOTALL)

JSON_CARD = """You write specifications for t as a JSON expression tree. Return one JSON object matching
the supplied schema, without markdown fences or prose. Preserve the requested task name, parameter order,
parameter types and return type. The task has an empty body: omit its body field. Helper spec_funs have an
expression body. Use t=1 unless only version-zero constructs are needed.
Never call the task itself from its requires or ensures clauses. Every helper call must name a declared
spec_fun. Arithmetic operands must have the same type; use toreal explicitly when mixing integers and reals.

Integer values are mathematical integers. A string is a sequence of Unicode code points, not a string literal.
Types include int, bool, seq (sequence of ints), real, float, set, and compositional objects such as
{"seq":"seq"}, {"pair":["int","seq"]}, {"map":["int","seq"]}, and {"datatype":"D"}.
Canonical seq<int> and set<int> types are the strings seq and set. Declare every named datatype.

Expression nodes: {"int":3}, {"bool":true}, {"var":"x"}, {"rat":[1,2]}, or
{"op":"+","args":[{"var":"x"},{"int":1}]}. Operators use their engine names: div and mod for
integer division/modulo, implies for implication, at for indexing, seq for a sequence display, len for length,
and the library names such as count, split, join, sum, sort and abs. A conditional is
{"ite":{"cond":EXPR,"then":EXPR,"else":EXPR}}. Quantifiers are
{"forall":{"var":"i","lo":EXPR,"hi":EXPR,"body":EXPR}} or exists, with a half-open integer range;
collection quantifiers replace lo/hi with in. Bound names must be fresh. Guard partial operations explicitly.
Comprehensions use comp with var, cond, body and either seq or lo/hi. Higher-order operators use a lam node
with vars and body. Calls to declared pure helpers use {"call":{"fun":"NAME","args":[EXPR]}}.
A spec_fun has name, params, result, body, and a decreases expression when recursive. Constructors, fields
and exhaustive match expressions use the corresponding schema variants. No program statements are requested.

requires and ensures are arrays of Boolean expressions; all clauses are conjoined in order. Include at least
one ensures clause. State the result precisely: a weak condition does not pass the existing mutant checks.
The worked examples below preserve the original problems, tests and Python solutions, with their checked
contracts represented as JSON instead of t notation.
"""


def obj(properties: dict, optional=()) -> dict:
    return {"type": "object", "properties": properties,
            "required": [key for key in properties if key not in optional], "additionalProperties": False}


def array(item: dict) -> dict:
    return {"type": "array", "items": item}


@lru_cache(maxsize=1)
def schema() -> dict:
    ref = lambda name: {"$ref": "#/$defs/" + name}
    string = {"type": "string"}
    expr, typ = ref("expr"), ref("type")
    param = obj({"name": string, "type": typ})
    definitions = {
        "type": {"anyOf": [{"type": "string", "enum": sorted(set(check_wf.BASE_TYPES) | {"set", "array"})}]
                 + [obj({key: typ}) for key in ("seq", "set")]
                 + [obj({key: array(typ)}) for key in ("pair", "tuple", "map")]
                 + [obj({"datatype": string})]},
        "param": param,
        "datatype": obj({"name": string, "ctors": array(obj({"name": string, "fields": array(ref("param"))},
                                                              optional=("fields",)))}),
        "spec_fun": obj({"name": string, "params": array(ref("param")), "result": typ,
                         "body": expr, "decreases": expr}, optional=("decreases",)),
        "quantifier": {"anyOf": [obj({"var": string, "lo": expr, "hi": expr, "body": expr}),
                                  obj({"var": string, "in": expr, "body": expr})]},
        "comprehension": {"anyOf": [obj({"var": string, "lo": expr, "hi": expr, "cond": expr, "body": expr}),
                                      obj({"var": string, "seq": expr, "cond": expr, "body": expr})]},
        "expr": {"anyOf": [
            obj({"int": {"type": "integer"}}), obj({"rat": array({"type": "integer"})}),
            obj({"bool": {"type": "boolean"}}), obj({"var": string}), obj({"old": expr}),
            obj({"op": {"type": "string", "enum": sorted(check_wf.V1_OPS)}, "args": array(expr)}),
            obj({"ite": obj({"cond": expr, "then": expr, "else": expr})}),
            obj({"forall": ref("quantifier")}), obj({"exists": ref("quantifier")}),
            obj({"comp": ref("comprehension")}), obj({"lam": obj({"vars": array(string), "body": expr})}),
            obj({"call": obj({"fun": string, "args": array(expr)})}),
            obj({"ctor": obj({"dtype": string, "name": string, "args": array(expr)})}),
            obj({"field": obj({"of": expr, "name": string})}),
            obj({"match": obj({"scrutinee": expr, "arms": array(obj({
                "ctor": string, "binders": array(string), "body": expr}))})}),
        ]},
    }
    root = obj({"t": {"type": "integer", "enum": [0, 1]}, "name": string,
                "params": array(ref("param")), "returns": array(ref("param")),
                "requires": array(expr), "ensures": array(expr), "gate": string,
                "spec_funs": array(ref("spec_fun")), "datatypes": array(ref("datatype")),
                "modifies": array(string), "decreases": expr}, optional=OPTIONAL)
    root["$defs"] = definitions
    return root


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def identity() -> str:
    sources = [Path(__file__), Path(__file__).with_name("spec_contract.py"),
               Path(__file__).with_name("cohere_proxy.py"), Path(__file__).with_name("requirements-cohere-json.txt"),
               HERE / "check_wf.py", HERE / "surface.py", HERE / "spec_first_rows.py",
               Path(teacher_primer.__file__)]
    return "t-json-v1:" + hashlib.sha256(canonical(schema()) + b"".join(p.read_bytes() for p in sources)).hexdigest()


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field")
        value[key] = item
    return value


def reject_constant(_value):
    raise ValueError("non-finite JSON number")


def decode_contract(text: str) -> dict:
    from jsonschema import Draft202012Validator
    document = json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
    Draft202012Validator(schema()).validate(document)
    if type(document) is not dict or not REQUIRED <= set(document) or set(document) - REQUIRED - OPTIONAL:
        raise ValueError("contract fields differ from the registered representation")
    if type(document["t"]) is not int or document["t"] not in (0, 1):
        raise ValueError("invalid task version")
    if type(document["ensures"]) is not list or not document["ensures"]:
        raise ValueError("a contract needs an ensures clause")
    task, _promoted = checked_contract(dict(document, body=[]))
    return task


def contract_document(task: dict) -> dict:
    normalized, _promoted = checked_contract(task)
    document = {key: value for key, value in normalized.items() if key != "body"}
    decode_contract(json.dumps(document))
    return document


@lru_cache(maxsize=8)
def converted_system(system: str) -> str:
    prefix = spec_first_rows.SPEC_SYSTEM + "\n\n" + teacher_primer.CARD
    if not system.startswith(prefix):
        raise ValueError("the teacher primer differs from the registered card")
    examples = system[len(prefix):]
    count = 0

    def convert(match):
        nonlocal count
        task = surface.parse(match[1])
        document = contract_document(task)
        count += 1
        return "```json\n" + json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n```"

    converted = FENCE.sub(convert, examples)
    if count != 6 or "```t" in converted:
        raise ValueError("the JSON teacher needs the same six complete checked examples")
    return JSON_CARD + converted


def messages(messages: list[dict]) -> list[dict]:
    """Replace the notation card and each example's representation, retaining all problem evidence."""
    if (len(messages) != 2 or [m.get("role") for m in messages] != ["system", "user"]
            or any(type(m.get("content")) is not str for m in messages)):
        raise ValueError("JSON teacher transport expects one specification question")
    return [{"role": "system", "content": converted_system(messages[0]["content"])}, deepcopy(messages[1])]


def reply(result: dict) -> tuple[str, dict]:
    if result.get("finish_reason") != "COMPLETE":
        raise ValueError("provider reply is incomplete")
    text = "".join(block["text"] for block in result["message"]["content"] if block["type"] == "text")
    task = decode_contract(text)
    rendered = surface.print_task(task).strip()
    return "```t\n" + rendered + "\n```", {
        "status": "accepted", "task_sha256": hashlib.sha256(canonical(task)).hexdigest(),
        "header_promoted": json.loads(text)["t"] != task["t"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", action="store_true", required=True)
    parser.parse_args(argv)
    print(identity())
    return 0


if __name__ == "__main__":
    sys.exit(main())
