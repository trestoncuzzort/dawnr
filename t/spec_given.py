#!/usr/bin/env python3
"""t/spec_given.py -- was the specification that was GIVEN the one that was proved? (2026-10-01)

In the "specification given, write the body" setting (the vericoding benchmark, arXiv:2509.22908;
SAFE, arXiv:2410.15756; AlphaVerus, arXiv:2412.06176) the given contract is the ground truth:
there is no reference solution and there are no tests to catch an answer that proves something
else. AlphaVerus names the hazard and filters for it ("the specification does not reflect the
desired input-output behavior"). So before an answer goes to the provers it must carry the
question's specification unchanged.

What is specification, and must equal the question's:
  the task's name, its parameters and results, every `requires`, every given `ensures` (more may
  be added: they only strengthen it), every given spec fun exactly (name, parameters, result,
  decreases, body), and every datatype.
What is proof, and is the answer's to write:
  the body with its loop invariants and decreases, the task's own `decreases`, the lemmas (SPEC.md,
  "Lemmas": a lemma's ensures is "the statement proved" and "a kernel that states it must prove
  it", so a lemma cannot assume anything), the format line and the gate line.

t/repair.py's spec_kept is not used here. It compares the parameters, results and requires and
checks that each ensures is still present; it does not look at spec funs. With tests and a
reference solution behind it that is survivable. Here it is a hole: an answer could keep
`ensures r == f(n)` word for word, redefine `spec fun f` as something trivial, and be counted as a
proof of the given contract. 15 of the 33 held-out questions built on 2026-10-01 have a spec fun.
"""
from __future__ import annotations

import json


def _same(a, b) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def kept(question: dict, answer: dict) -> str | None:
    """None when the answer carries the question's specification unchanged; else the first reason."""
    if answer.get("name") != question.get("name"):
        return "the task was renamed"
    for part in ("params", "returns"):
        if not _same(question.get(part), answer.get(part)):
            return f"the {part} differ"
    if not _same(question.get("requires", []), answer.get("requires", [])):
        return "a requires was changed, added or removed"
    have = [json.dumps(e, sort_keys=True) for e in answer.get("ensures", [])]
    for e in question.get("ensures", []):
        if json.dumps(e, sort_keys=True) not in have:
            return "a given ensures is missing or altered"
    if not _same(question.get("datatypes", []), answer.get("datatypes", [])):
        return "a datatype was changed, added or removed"
    given = {f["name"]: f for f in question.get("spec_funs", [])}
    written = {}
    for f in answer.get("spec_funs", []):
        if f["name"] in written:
            return f"spec fun {f['name']} is defined twice"
        written[f["name"]] = f
    for name, f in given.items():
        if name not in written:
            return f"given spec fun {name} is missing"
        if not _same(f, written[name]):
            return f"given spec fun {name} was redefined"
    for lemma in answer.get("lemmas", []):
        if lemma.get("name") in given:
            return f"a lemma takes the name of given spec fun {lemma['name']}"
    return None
