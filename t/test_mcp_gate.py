"""t/mcp_gate.py: dawnr's checks as MCP tools for an assistant that is not dawnr's. The caller writes; the same
gate decides; a refusal is a result, a malformed call an error (MCP specification 2025-06-18, server/tools)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import mcp_gate                                                 # noqa: E402
import py_sandbox                                               # noqa: E402
import spec_check                                               # noqa: E402

needs_sandbox = pytest.mark.skipif(not py_sandbox.available(), reason="no sandbox for a caller's Python here")
ALL = {k: "verified / refuted" for k in spec_check.KERNELS}
DOUBLE = "t 1\ntask double(n: int) returns (r: int)\n  ensures r == 2 * n\n{\n  r := 2 * n;\n}\n"
TESTS = ["assert double(3) == 6", "assert double(0) == 0"]
PYTHON = "def double(n):\n    return 2 * n\n"


def prover(cells_for=lambda task: ALL):
    return lambda tasks, jobs: {task["name"]: cells_for(task) for task in tasks}


def server(**kw):
    s = mcp_gate.Gate(prover=prover(), **kw)
    hello = s.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}}})
    assert hello["result"]["serverInfo"]["name"] == "dawnr" and "no model of its own" in hello["result"]["instructions"]
    return s


def call(s, name, arguments, rid=1):
    reply = s.handle({"jsonrpc": "2.0", "id": rid, "method": "tools/call", "params": {"name": name, "arguments": arguments}})
    return reply["result"]


def test_the_tools_are_listed_with_schemas_and_an_unknown_one_is_a_protocol_error():
    s = server()
    listed = s.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})["result"]["tools"]
    assert [t["name"] for t in listed] == ["t_reference", "prove", "check_certificate", "compute", "check_quotes"]
    assert all(t["inputSchema"]["type"] == "object" and t["description"] for t in listed)
    unknown = s.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "launch", "arguments": {}}})
    assert unknown["error"]["code"] == -32602


def test_the_reference_is_the_page_a_writer_that_has_never_seen_t_is_given():
    r = call(server(), "t_reference", {})
    assert not r["isError"] and "Examples of complete t tasks:" in r["content"][0]["text"] and "ensures" in r["content"][0]["text"]


@needs_sandbox
def test_a_callers_program_with_tests_and_its_own_python_goes_through_the_whole_gate_and_comes_back_with_a_certificate():
    r = call(server(), "prove", {"program": DOUBLE, "tests": TESTS, "python": PYTHON, "question": "Double a number."})
    assert not r["isError"] and r["content"][0]["text"].startswith("SHOWN: proved by 7 of 7 provers")
    data = r["structuredContent"]
    assert data["outcome"] == "shown" and data["certificate"]["predicate"]["kind"] == "ask"
    assert data["certificate"]["predicate"]["reference python"].strip() == PYTHON.strip()
    # the certificate it handed out replays through the next tool
    again = call(server(), "check_certificate", {"certificate": data["certificate"]})
    assert again["structuredContent"]["outcome"] == "reproduced" and again["content"][0]["text"].startswith("REPRODUCED")


@needs_sandbox
def test_a_specification_the_callers_own_python_contradicts_is_refused_as_a_result_not_an_error():
    wrong = DOUBLE.replace("ensures r == 2 * n", "ensures r == n + n + 0 * n and r >= n")
    r = call(server(), "prove", {"program": wrong, "tests": ["assert double(3) == 6", "assert double(-2) == -4"], "python": PYTHON})
    assert not r["isError"] and r["structuredContent"]["outcome"] == "refused" and r["content"][0]["text"].startswith("REFUSED")
    weak = call(server(), "prove", {"program": DOUBLE.replace("ensures r == 2 * n", "ensures r >= n or r < n"), "tests": TESTS, "python": PYTHON})
    assert weak["structuredContent"]["outcome"] == "refused" and "weak specification" in weak["content"][0]["text"]


def test_a_program_alone_is_proved_as_written_and_its_specification_measured():
    r = call(server(), "prove", {"program": DOUBLE})
    assert r["structuredContent"]["outcome"] == "proved" and r["structuredContent"]["certificate"]["predicate"]["kind"] == "prove"
    assert r["content"][0]["text"].startswith("PROVED: by 7 of 7 provers") and "rejects 100%" in r["content"][0]["text"]
    empty = call(server(), "prove", {"program": DOUBLE.replace("  r := 2 * n;\n", "")})
    assert empty["structuredContent"]["outcome"] == "refused" and "this tool runs no model" in empty["content"][0]["text"]
    unproved = mcp_gate.Gate(prover=prover(lambda task: {k: "unproved / refuted" for k in spec_check.KERNELS}))
    unproved.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
    assert call(unproved, "prove", {"program": DOUBLE})["structuredContent"]["outcome"] == "not proved"


def test_workings_are_computed_exactly_and_an_answer_needs_two_that_agree_on_the_questions_own_numbers():
    q = "A recipe needs 2.5 cups of flour for 12 muffins. How many cups are needed for 30 muffins?"
    r = call(server(), "compute", {"question": q, "workings": ["per = 2.5 / 12\nanswer = per * 30", "answer = 30 * 2.5 / 12"]})
    assert r["structuredContent"] == {"outcome": "answered", "why": None, "answer": "6.25",
                                      "ways": [{"used": True, "value": "6.25"}, {"used": True, "value": "6.25"}]}
    one = call(server(), "compute", {"question": q, "workings": ["answer = 6.25", "answer = 30 * 2.5 / 12"]})
    assert one["structuredContent"]["outcome"] == "refused" and one["structuredContent"]["ways"][0]["why"].startswith("it uses 6.25")
    split = call(server(), "compute", {"question": q, "workings": ["answer = 30 * 2.5 / 12", "answer = 12 * 2.5 / 30"]})
    assert split["structuredContent"]["outcome"] == "refused" and "disagree" in split["content"][0]["text"]


def test_a_quote_is_supported_only_word_for_word_with_its_value_inside_and_of_its_kind():
    doc = {"name": "invoice.txt", "text": "Invoice 2291. The total due is $1,250.00, payable by March 3, 2026.\n\nShip to the dock office."}
    r = call(server(), "check_quotes", {"documents": [doc], "claims": [
        {"claim": "The total is 1,250 dollars.", "quote": "The total due is $1,250.00, payable by March 3, 2026.", "value": "1,250.00", "kind": "number"},
        {"claim": "Payment is due in March.", "quote": "payable by March 3, 2026", "value": "March 3, 2026", "kind": "date"},
        {"claim": "The total is 1,300.", "quote": "The total due is $1,300.00."},
        {"claim": "It ships to the dock.", "quote": "Ship to the dock office.", "value": "the warehouse"},
        {"claim": "The invoice number is a date.", "quote": "Invoice 2291.", "value": "Invoice", "kind": "date"}]})
    rows = r["structuredContent"]["claims"]
    assert [x["found"] for x in rows] == [True, True, False, False, False]
    assert rows[0]["read as"] == 1250.0 and rows[1]["read as"] == "2026-03-03" and rows[0]["sentence"] == 2
    assert rows[2]["why"] == "the quote is not in the documents word for word" and rows[3]["why"] == "the value is not in the quoted sentence"
    assert r["content"][0]["text"].startswith("2 of 5 quotes are in the documents as quoted.")


def test_a_malformed_call_is_an_error_and_a_check_that_breaks_is_said():
    s = server()
    assert call(s, "prove", {"program": 7})["isError"] and call(s, "compute", {"question": "q"})["isError"]
    assert call(s, "check_certificate", {"certificate": {"_type": "x"}})["structuredContent"]["outcome"] == "failed"


def test_over_stdio_only_protocol_messages_come_out():
    messages = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": "compute", "arguments": {"question": "What is 17.5% of 2,340?", "workings": ["answer = 2340 * 17.5 / 100", "p = 17.5 / 100\nanswer = p * 2340"]}}}]
    p = subprocess.run([sys.executable, str(HERE / "mcp_gate.py")], input="".join(json.dumps(m) + "\n" for m in messages),
                       capture_output=True, text=True, timeout=60)
    lines = [json.loads(l) for l in p.stdout.splitlines()]
    assert [l["id"] for l in lines] == [1, 2] and lines[1]["result"]["structuredContent"]["answer"] == "409.5"
