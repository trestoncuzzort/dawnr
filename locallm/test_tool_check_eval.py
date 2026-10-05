"""tool_check_eval.py: the split, BFCL's tools as OpenAI's, the comparison with a reference call, and the two
readings of one stored reply (no server, no dataset)."""
import json

from locallm import tool_check_eval as ev

TOOL = json.dumps({"name": "api.weather", "description": "Weather.", "parameters": {"type": "dict", "required": ["loc"], "properties": {
    "loc": {"type": "string", "description": "City, Country"}, "days": {"type": "integer", "default": 1},
    "opts": {"type": "dict", "properties": {"units": {"type": "tuple", "items": {"type": "float"}}}}}}})


def row(kind, question, calls, reference=None, held_out=None):
    return {"uuid": question, "kind": kind, "held_out": held_out, "messages": [{"role": "user", "content": question}],
            "tools": [ev.openai_tool(TOOL)], "target": "api_weather", "reference": reference,
            "reply": {"content": "", "tool_calls": [{"function": {"name": n, "arguments": json.dumps(a)}} for n, a in calls]}}


def test_a_bfcl_tool_becomes_an_openai_one():
    f = ev.openai_tool(TOOL)["function"]
    assert f["name"] == "api_weather" and f["parameters"]["type"] == "object" and f["parameters"]["required"] == ["loc"]
    assert f["parameters"]["properties"]["opts"] == {"type": "object", "properties": {"units": {"type": "array", "items": {"type": "number"}}}}
    assert ev.openai_tool({"name": "f"})["function"]["parameters"] == {"type": "object", "properties": {}}
    assert "type" not in ev.schema({"type": "any", "description": "x"})


def test_the_split_is_fixed_and_dev_and_test_share_nothing():
    rows = [{"uuid": f"{k}{i}", "correct_answer": k} for k in ev.KINDS for i in range(150)]
    dev, test = ev.split(rows, "dev"), ev.split(rows, "test", 20)
    assert len(dev) == 300 and len(test) == 60 and not {r["uuid"] for r in dev} & {r["uuid"] for r in ev.split(rows, "test")}
    assert dev == ev.split(list(reversed(rows)), "dev") and len(ev.split(rows, "test")) == 150


def test_a_value_agrees_with_the_reference_or_one_of_its_alternatives():
    assert ev.same("ha noi, vietnam", "Ha Noi, Vietnam") and ev.same(10, "10") and ev.same("Plus", ["plus", "Uber Plus"])
    assert not ev.same("Hanoi", "Ha Noi, Vietnam") and not ev.same(11, [10, 12])
    assert ev.same(["a", "b"], ["a", "b"]) and ev.same(["a"], [["a"], ["b"]]) and not ev.same(["a", "c"], ["a", "b"])
    assert ev.same({"size": "large"}, {"size": ["large"], "milk": ["coconut"]}) and not ev.same({"size": "small"}, {"size": ["large"]})


def test_one_reply_is_read_both_ways():
    # the value was said: both readings release the call, and it agrees with the reference
    j = ev.judge(row("tool_call", "Weather in Lisbon?", [("api_weather", {"loc": "Lisbon", "days": 1})], {"name": "api.weather", "arguments": {"loc": ["Lisbon", "Lisbon, Portugal"]}}))
    assert j["native"] and j["checked"] and j["native agrees"] and j["checked agrees"] and j["checked tool"]
    # a right call whose value was not said in those words: released natively, a question under the check
    j = ev.judge(row("tool_call", "Weather in the Portuguese capital?", [("api_weather", {"loc": "Lisbon"})], {"name": "api.weather", "arguments": {"loc": "Lisbon"}}))
    assert j["native agrees"] and not j["checked"] and j["action"] == "ask" and not j["checked agrees"]
    # the removed value invented: released natively, and the check asks for that parameter
    j = ev.judge(row("request_for_info", "Get the weather for me.", [("api_weather", {"loc": "Paris, France"})], held_out="loc"))
    assert j["native"] and not j["checked"] and j["asks for the removed one"] and j["asked"] == ["loc"]
    # no call at all: neither reading releases one
    j = ev.judge(row("cannot_answer", "Book a flight.", []))
    assert j == {"action": "none", "native": False, "checked": False}


def test_the_report_counts_calls_released_per_kind_and_their_agreement():
    rows = [row("tool_call", "Weather in Lisbon?", [("api_weather", {"loc": "Lisbon"})], {"name": "api.weather", "arguments": {"loc": "Lisbon"}}),
            row("tool_call", "Weather in the Portuguese capital?", [("api_weather", {"loc": "Lisbon"})], {"name": "api.weather", "arguments": {"loc": "Lisbon"}}),
            row("request_for_info", "Get the weather for me.", [("api_weather", {"loc": "Paris, France"})], held_out="loc"),
            row("cannot_answer", "Weather in Lisbon, by email.", [("send_email", {"to": "x"})])]
    r = ev.report(rows)
    assert r["tool_call"]["native: agrees with the reference call"] == 2 and r["tool_call"]["checked: agrees with the reference call"] == 1
    assert r["request_for_info"]["native: a call released"] == 1 and r["request_for_info"]["checked: a call released"] == 0
    assert r["request_for_info"]["checked: asked for the removed parameter"] == 1 and r["cannot_answer"]["checked: refused"] == 1
    assert r["native: of calls released, agreeing with a reference"] == {"released": 4, "agree": 2, "share": 0.5}
    assert r["checked: of calls released, agreeing with a reference"] == {"released": 1, "agree": 1, "share": 1.0}


def test_an_item_is_asked_with_its_tools_and_stored_with_what_the_check_needs():
    seen = []

    def post(url, body):
        seen.append(body)
        return {"choices": [{"message": {"content": None, "tool_calls": [{"function": {"name": "api_weather", "arguments": "{\"loc\": \"Lisbon\"}"}}]}}]}
    item = {"uuid": "u1", "correct_answer": "tool_call", "source": "BFCL v2 Live Simple", "question": "Weather in Lisbon?", "tools": [TOOL],
            "target_tool": TOOL, "answers": {"tool_call": json.dumps({"name": "api.weather", "arguments": {"loc": "Lisbon"}})}}
    got = ev.ask_item("h:1", item, post)
    assert seen[0]["tools"][0]["function"]["name"] == "api_weather" and seen[0]["temperature"] == 0
    assert got["target"] == "api_weather" and got["reference"]["arguments"] == {"loc": "Lisbon"} and got["reply"]["content"] == ""
    assert ev.judge(got)["checked agrees"]
    none = ev.ask_item("h:1", dict(item, tools=[], target_tool=None, correct_answer="cannot_answer"), post)
    assert "tools" not in seen[1] and none["target"] is None
