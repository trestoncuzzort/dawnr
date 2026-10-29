"""Internal teacher transport with named operands for fixed-arity operators.

Cohere does not support minItems/maxItems. Required named operands express
arity using supported object fields; the decoded contract still goes through
the original static, exact round-trip, reference and mutant checks.
Sources: https://docs.cohere.com/docs/structured-outputs; t/check_wf.py;
cohere_task_json.py. This changes transport, never language semantics.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

import cohere_task_json as original

HERE = original.HERE
surface = original.surface
spec_first_rows = original.spec_first_rows
canonical = original.canonical
FENCE = original.FENCE


def arities(op):
    if op in original.check_wf.VARIADIC | original.check_wf.NARY:
        return None
    if op in {"split", "min", "max", "strip", "lstrip", "rstrip"}:
        return (1, 2)
    if op in {"center", "ljust", "rjust"}:
        return (2, 3)
    if op in original.check_wf.UNARY:
        return (1,)
    if op in original.check_wf.TERNARY or op == "fold":
        return (3,)
    return (2,)


def encode(value):
    if isinstance(value, list):
        return [encode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {"op", "args"} and arities(value["op"]) is not None:
        if len(value["args"]) not in arities(value["op"]):
            raise ValueError("cannot encode an operator with incorrect arity")
        return {"op": value["op"], **{f"arg{i}": encode(arg) for i, arg in enumerate(value["args"], 1)}}
    return {key: encode(item) for key, item in value.items()}


def decode(value):
    if isinstance(value, list):
        return [decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "op" in value and arities(value["op"]) is not None:
        return {"op": value["op"], "args": [decode(value[f"arg{i}"]) for i in range(1, len(value))]}
    return {key: decode(item) for key, item in value.items()}


@lru_cache(maxsize=1)
def schema():
    result = deepcopy(original.schema())
    definitions = result["$defs"]
    alternatives = definitions["expr"]["anyOf"]
    alternatives[:] = [item for item in alternatives if "op" not in item.get("properties", {})]
    for count in (1, 2, 3):
        ops = sorted(op for op in original.check_wf.V1_OPS if arities(op) and count in arities(op))
        alternatives.append(original.obj({"op": {"type": "string", "enum": ops},
            **{f"arg{i}": {"$ref": "#/$defs/expr"} for i in range(1, count + 1)}}))
    variadic = sorted(original.check_wf.VARIADIC | original.check_wf.NARY)
    alternatives.append(original.obj({"op": {"type": "string", "enum": variadic},
                                       "args": original.array({"$ref": "#/$defs/expr"})}))
    # Restrict canonical spelling rather than silently normalizing paid replies.
    for variant in definitions["type"]["anyOf"]:
        for key in ("seq", "set"):
            if key in variant.get("properties", {}):
                variant["properties"][key] = {"$ref": "#/$defs/non_int_type"}
    definitions["non_int_type"] = deepcopy(definitions["type"])
    definitions["non_int_type"]["anyOf"][0]["enum"].remove("int")
    return result


def identity():
    return "t-json-v2:" + hashlib.sha256(canonical(schema()) + Path(__file__).read_bytes()
                                         + original.identity().encode()).hexdigest()


def contract_document(task):
    return encode(original.contract_document(task))


def decode_contract(text):
    from jsonschema import Draft202012Validator
    document = json.loads(text, object_pairs_hook=original.unique_object, parse_constant=original.reject_constant)
    Draft202012Validator(schema()).validate(document)
    return original.decode_contract(json.dumps(decode(document)))


@lru_cache(maxsize=8)
def converted_system(system):
    converted = original.converted_system(system)
    card, examples = converted.split("```json", 1)
    card = card.replace('{"op":"+","args":[{"var":"x"},{"int":1}]}',
                        '{"op":"+","arg1":{"var":"x"},"arg2":{"int":1}}')
    card += ("\nFor fixed-arity operators, use arg1, arg2 and arg3 in operand order, exactly as the schema specifies. "
             "Only variadic operators (seq, set, tuple, mapdisp, and, or) keep an args array. "
             "Calls and constructors also keep their args arrays. Never invent missing operands.\n")
    pattern = re.compile(r"```json\s*\n(.*?)```", re.DOTALL)
    return card + pattern.sub(lambda m: "```json\n" + json.dumps(encode(json.loads(m[1])),
                        ensure_ascii=False, separators=(",", ":")) + "\n```", "```json" + examples)


def messages(messages):
    original.messages(messages)  # retain the original prompt shape and six checked examples
    return [{"role": "system", "content": converted_system(messages[0]["content"])}, deepcopy(messages[1])]


def reply(result):
    if result.get("finish_reason") != "COMPLETE":
        raise ValueError("provider reply is incomplete")
    text = "".join(block["text"] for block in result["message"]["content"] if block["type"] == "text")
    task = decode_contract(text)
    return "```t\n" + surface.print_task(task).strip() + "\n```", {
        "status": "accepted", "task_sha256": hashlib.sha256(canonical(task)).hexdigest(),
        "header_promoted": json.loads(text)["t"] != task["t"]}


if __name__ == "__main__":
    print(identity())
