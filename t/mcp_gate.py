#!/usr/bin/env python3
"""t/mcp_gate.py -- dawnr's checks as Model Context Protocol tools, for whatever assistant a person already uses
(2026-10-05).

    python3 t/mcp_gate.py            (stdio; `dawnr mcp` is this)

    claude mcp add dawnr -- dawnr mcp                      # Claude Code
    {"mcpServers": {"dawnr": {"command": "dawnr", "args": ["mcp"]}}}     # most other clients' configuration

None of these tools runs a model of dawnr's. The assistant that calls them is the writer, and it is trusted
exactly as far as dawnr's own model is: not at all (the checks decide; LCF's arrangement, research receipts
6829d2f2553a and d8d87ef52dd2). So a machine with dawnr's provers and no model file can prove what a frontier model
wrote. A refusal is an ordinary result that names the check that stopped it; only a malformed call is an error
(MCP, specification 2025-06-18, server/tools: `content`, `structuredContent`, `isError`).

  t_reference        the language `t` in one page with worked examples: what to read before writing a program
  prove              a `t` task with its body through the gate. With the question's tests and an independently
                     written Python solution, the whole of `dawnr ask`'s gate (t/answer.py): the tests, the
                     specification held against the Python on drawn inputs up to several times the examples' size,
                     the provers and the sabotaged twin. With the program alone, `dawnr prove`'s (t/prove.py): the
                     provers, and how much the specification says. A proved answer comes with its certificate.
  check_certificate  a certificate replayed on this machine (t/certificate.py)
  compute            a question with numbers and the caller's workings (assignments of arithmetic ending in
                     `answer = ...`): computed exactly, used only if their numbers are the question's, answered
                     only if at least two compute and all that compute agree (locallm/calc.py)
  check_quotes       claims with the sentence each is quoted from: is the quote in the person's text word for
                     word, is the value in the quote, does it read as its kind (locallm/extract_docs.py)

The protocol layer is locallm/dawnr_harness/mcp_server.py's (both protocol eras, tested against its own client).
"""
from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "locallm"))

from dawnr_harness.mcp_server import Server                     # noqa: E402
from dawnr_harness.tools import validate                        # noqa: E402

MAX_TEXT = 65536
_TESTS = {"type": "array", "maxItems": 20, "items": {"type": "string", "maxLength": 600},
          "description": "the question's examples, one `assert f(arguments) == value` line each"}
TOOLS = [
    {"name": "t_reference", "title": "The language t, on one page",
     "description": "The grammar and rules of t, the small verified language dawnr's provers check, with worked "
                    "examples of complete tasks. Read it once before writing a program for `prove`.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "prove", "title": "Prove a t program",
     "description": "Put a t task (specification and body) through dawnr's gate. Give `tests` and `python` (your own "
                    "independent Python solution to the same question) and the specification is also held against "
                    "that solution on drawn inputs; an answer then counts only if it passes the tests, its "
                    "specification is supported and pins the result down, and a prover proves it with its sabotaged "
                    "twin refuted. Give the program alone and it is proved as written, with a measure of how much "
                    "its specification says. Nothing you send is trusted; a refusal says which check stopped it.",
     "inputSchema": {"type": "object",
                     "properties": {"program": {"type": "string", "maxLength": MAX_TEXT, "description": "one t task, from its `t 1` line, body included"},
                                    "tests": _TESTS,
                                    "python": {"type": "string", "maxLength": MAX_TEXT,
                                               "description": "an independent Python solution to the question (run only in a sandbox)"},
                                    "question": {"type": "string", "maxLength": 4000, "description": "the question in words, for the record"}},
                     "required": ["program"], "additionalProperties": False}},
    {"name": "check_certificate", "title": "Replay a dawnr certificate",
     "description": "Replay a certificate with this machine's provers and no model: the tests, a search for an input "
                    "that breaks the specification, the proof and its sabotaged twin, the Python handed back.",
     "inputSchema": {"type": "object", "properties": {"certificate": {"type": "object", "description": "the certificate's JSON"}},
                     "required": ["certificate"], "additionalProperties": False}},
    {"name": "compute", "title": "Compute a working exactly",
     "description": "Give a question with numbers and two or more workings, each a few lines of `name = arithmetic` "
                    "ending in `answer = ...`, using only the question's numbers. They are computed in exact "
                    "fractions; a working that brings in another number is not used; an answer comes back only when "
                    "at least two compute and all that compute agree.",
     "inputSchema": {"type": "object",
                     "properties": {"question": {"type": "string", "maxLength": 4000},
                                    "workings": {"type": "array", "minItems": 1, "maxItems": 8, "items": {"type": "string", "maxLength": 4000}}},
                     "required": ["question", "workings"], "additionalProperties": False}},
    {"name": "check_quotes", "title": "Check quotes against the person's text",
     "description": "For each claim, is its quote in the documents word for word (as a whole sentence or a run of "
                    "one), is its value inside the quote, and does the value read as its kind (number, date)?",
     "inputSchema": {"type": "object",
                     "properties": {"documents": {"type": "array", "minItems": 1, "maxItems": 20,
                                                  "items": {"type": "object", "properties": {"name": {"type": "string", "maxLength": 200},
                                                                                           "text": {"type": "string", "maxLength": 1000000}},
                                                            "required": ["name", "text"]}},
                                    "claims": {"type": "array", "minItems": 1, "maxItems": 50,
                                               "items": {"type": "object",
                                                         "properties": {"claim": {"type": "string", "maxLength": 2000},
                                                                        "quote": {"type": "string", "maxLength": 2000},
                                                                        "value": {"type": "string", "maxLength": 400},
                                                                        "kind": {"type": "string", "enum": ["text", "number", "date"]}},
                                                         "required": ["quote"]}}},
                     "required": ["documents", "claims"], "additionalProperties": False}},
]
_BY_NAME = {t["name"]: t for t in TOOLS}


def _fixed(text: str):
    """A `decode` that answers with what the caller wrote, for gates that expect to ask a model."""
    return lambda conversations, *rest: [(text, True, 0) for _ in conversations]


def _fenced(text: str, language: str) -> str:
    return text if "```" in text else f"```{language}\n{text.strip()}\n```"


def reference() -> dict:
    import spec_experiment as se
    text = se.GRAMMAR_V5 + "\nExamples of complete t tasks:\n\n" + se.fewshot_text("v5")
    return {"text": text, "data": {"characters": len(text)}}


def prove(a: dict, prover=None) -> dict:
    import answer as gate
    import certificate
    import prove as spec_first_way
    tests = [t.strip() for t in a.get("tests") or [] if t.strip()]
    kw = {"prover": prover} if prover else {}
    if a.get("python"):
        if not tests:
            return {"text": "REFUSED: an independent Python solution needs the question's tests to be held against.", "data": {"outcome": "refused"}}
        try:
            entry = gate.entry_of(a.get("question") or "", tests)
        except ValueError as error:
            return {"text": f"REFUSED: {error}.", "data": {"outcome": "refused"}}
        r = gate.answer(entry, _fixed(_fenced(a["program"], "t")), _fixed(_fenced(a["python"], "python")), "s2", 1, consistency=0, **kw)
        made = certificate.from_answer(r)
        return {"text": gate.render(r), "data": {"outcome": "shown" if r["shown"] else "refused", "why": r.get("why"),
                                                 "provers": (r["shown"] or {}).get("provers", []), "certificate": made}}
    try:
        spec = spec_first_way.read_spec(a["program"])
        if not spec.get("body"):
            raise spec_first_way.Refused("the task has no body; write the body too (this tool runs no model)")
        given = spec_first_way.read_tests(tests, spec)
    except spec_first_way.Refused as refused:
        return {"text": f"REFUSED: {refused}.", "data": {"outcome": "refused"}}
    r = spec_first_way.prove(spec, None, tests=given, **kw)
    made = certificate.from_proof(r, tests)
    return {"text": spec_first_way.render_proof(r), "data": {"outcome": "proved" if r["shown"] else "not proved", "why": r.get("why"),
                                                             "provers": (r["shown"] or {}).get("provers", []), "certificate": made}}


def check_certificate(a: dict, prover=None) -> dict:
    import certificate
    report = certificate.check(a["certificate"], prover=prover)
    return {"text": certificate.render(report), "data": {"outcome": report["verdict"], "steps": report["steps"], "proved here": report["proved here"]}}


def compute(a: dict) -> dict:
    from locallm import calc
    r = dict(calc.judge(a["question"], [w if w.endswith("\n") else w + "\n" for w in a["workings"]]), question=a["question"])
    return {"text": calc.render(r), "data": {"outcome": "answered" if r["answer"] is not None else "refused", "why": r.get("why"),
                                             "answer": calc.show(r["answer"]) if isinstance(r["answer"], Fraction) else None,
                                             "ways": [{"used": "value" in w, **({"value": calc.show(w["value"])} if "value" in w else {"why": w["why"]})}
                                                      for w in r["ways"]]}}


def check_quotes(a: dict) -> dict:
    from locallm import cite_docs, extract_docs
    sentences = [(d["name"], n, s) for d in a["documents"] for n, s in enumerate(cite_docs.sentences(d["text"]), 1)]
    rows, lines = [], []
    for k, c in enumerate(a["claims"], 1):
        quote = " ".join(c["quote"].split())
        found = next(((name, n, s) for name, n, s in sentences if quote and quote in s), None)
        row = {"quote": c["quote"], "found": found is not None}
        if found is None:
            row["why"] = "the quote is not in the documents word for word"
        else:
            row.update(file=found[0], sentence=found[1])
            value = c.get("value")
            if value is not None and " ".join(value.split()) not in found[2]:
                row.update(found=False, why="the value is not in the quoted sentence")
            elif c.get("kind") in ("number", "date"):
                read, why = extract_docs.typed(c["kind"], value if value is not None else quote)
                if why:
                    row.update(found=False, why=why)
                else:
                    row["read as"] = read
        rows.append(row)
        lines.append(f"{k}. " + (f"FOUND in {row['file']}, sentence {row['sentence']}" + (f"; reads as {row['read as']}" if "read as" in row else "")
                                 if row["found"] else f"NOT SUPPORTED: {row['why']}") + f": \"{c['quote'][:120]}\"")
    ok = sum(r["found"] for r in rows)
    return {"text": f"{ok} of {len(rows)} quotes are in the documents as quoted.\n" + "\n".join(lines),
            "data": {"outcome": "all found" if ok == len(rows) else "some not supported", "claims": rows}}


class Gate(Server):
    info = {"name": "dawnr", "version": "0.6.0"}
    instructions = ("dawnr's checks, with no model of its own: prove a t program you wrote (read t_reference first), replay a "
                    "certificate, compute a working exactly, check quotes against a person's text. Nothing you send is "
                    "trusted; a refusal is an ordinary result that says which check stopped it.")

    def __init__(self, prover=None, **kw):
        super().__init__(**kw)
        self.prover = prover

    def tools(self) -> list[dict]:
        return TOOLS

    def call(self, name: str, arguments) -> dict:
        arguments = arguments if arguments is not None else {}
        errs = validate(_BY_NAME[name]["inputSchema"], arguments)
        if errs:
            return {"content": [{"type": "text", "text": "; ".join(errs)}], "isError": True}
        try:
            out = (reference() if name == "t_reference" else prove(arguments, self.prover) if name == "prove"
                   else check_certificate(arguments, self.prover) if name == "check_certificate"
                   else compute(arguments) if name == "compute" else check_quotes(arguments))
        except Exception as error:                              # noqa: BLE001 -- a check that broke is said, never passed
            return {"content": [{"type": "text", "text": f"the check could not be run ({type(error).__name__}: {error})"[:400]}], "isError": True}
        return {"content": [{"type": "text", "text": out["text"]}],
                "structuredContent": json.loads(json.dumps(out["data"], default=str)), "isError": False}


def main(argv=None) -> int:
    import os
    os.environ.setdefault("T_MIN_KERNELS", "1")                 # one installed prover is enough
    Gate().serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
