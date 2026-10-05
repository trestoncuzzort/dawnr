"""tool_check.py: which values of a call are accounted for by the conversation or the schema, and what becomes of
a call whose values are not (no model server)."""
import json
from fractions import Fraction

import pytest

from locallm import tool_check as tc

WEATHER = {"type": "function", "function": {
    "name": "get_weather", "description": "Get the current weather.",
    "parameters": {"type": "object", "required": ["loc"], "properties": {
        "loc": {"type": "string", "description": "The location, as 'City, Country' (e.g., 'Paris, France')."},
        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"},
        "days": {"type": "integer", "description": "How many days ahead."}}}}}
RIDE = json.dumps({"name": "uber.ride", "description": "Book a ride.", "parameters": {"type": "dict", "required": ["loc", "type", "time"], "properties": {
    "loc": {"type": "string"}, "type": {"type": "string", "enum": ["plus", "comfort", "black"]}, "time": {"type": "integer"}}}})


def user(text):
    return [{"role": "user", "content": text}]


def call(name, **arguments):
    return {"id": "c1", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


def test_a_required_value_nobody_said_becomes_a_question_that_names_the_parameter():
    v = tc.check([WEATHER], user("Get the current weather for me."), call("get_weather", loc="Paris, France"))
    assert v["action"] == "ask" and [a["parameter"] for a in v["ask"]] == ["loc"]
    assert v["ask"][0]["proposed"] == "Paris, France" and v["ask"][0]["why"] == "those words were not said"
    text = tc.question(v)
    assert text.startswith("To call get_weather I need `loc` (The location, as 'City, Country' (e.g., 'Paris, France')). What should it be?")
    assert "The model proposed 'Paris, France'; those words were not said." in text


def test_a_call_whose_values_were_said_is_released_as_written():
    v = tc.check([WEATHER], user("Weather in Paris for the next three days, in Fahrenheit."),
                 call("get_weather", loc="Paris, France", unit="Fahrenheit", days=3))
    assert v == {"action": "call", "name": "get_weather", "arguments": {"loc": "Paris, France", "unit": "fahrenheit", "days": 3}, "left_out": []}
    assert tc.question(v) == ""


def test_an_optional_value_nobody_said_is_left_out_and_said():
    v = tc.check([WEATHER], user("Weather in Ha Noi?"), call("get_weather", loc="Hà Nội", days=7, verbose=True, unit="fahrenheit"))
    assert v["action"] == "call" and v["arguments"] == {"loc": "Hà Nội"}
    assert [(x["parameter"], x["why"]) for x in v["left_out"]] == [("days", "that number was not said"), ("verbose", "get_weather declares no such parameter"),
                                                                 ("unit", "which of celsius, fahrenheit was not said")]
    assert "Left out of get_weather: days = 7 (that number was not said)." in tc.question(v)


def test_a_missing_required_parameter_is_asked_for_and_an_undeclared_tool_is_refused():
    v = tc.check([WEATHER], user("Weather?"), call("get_weather", unit="celsius"))
    assert v["action"] == "ask" and v["ask"] == [{"parameter": "loc", "description": "The location, as 'City, Country' (e.g., 'Paris, France').",
                                                  "why": "the call gives no value for it"}]
    v = tc.check([WEATHER], user("Email Dana."), call("send_email", to="dana@example.com"))
    assert v == {"action": "refuse", "name": "send_email", "why": "no tool named send_email was declared"}
    assert tc.question(v) == "NOT CALLED: no tool named send_email was declared."
    bad = {"function": {"name": "get_weather", "arguments": "{not json"}}
    assert tc.check([WEATHER], user("Weather in Paris"), bad)["why"] == "the arguments are not one JSON object"


def test_the_schema_accounts_for_its_own_values():
    said = tc.Said("I need a ride from 2150 Shattuck Ave, Berkeley, and I can wait ten minutes.")
    assert tc.accounted("limo", {"enum": ["plus", "comfort"]}, said) == (False, "limo", "it is not one of plus, comfort")
    assert tc.accounted(40.733, {"default": "40.733"}, said)[0] and tc.accounted(True, {}, said)[0] and tc.accounted(None, {}, said)[0]
    assert tc.accounted("", {"default": ""}, said) == (False, "", "it is empty")
    # a choice among an enum has to have been made: its words or their stems said, or the only one, or the default
    assert tc.accounted("plus", {"enum": ["plus", "comfort"]}, said) == (False, "plus", "which of plus, comfort was not said")
    assert tc.accounted("Plus", {"enum": ["plus", "comfort"]}, tc.Said("A Plus ride, please.")) == (True, "plus", "")
    assert tc.accounted(2, {"enum": ["1", "2", "3"]}, tc.Said("two of them")) == (True, 2, "")    # passed on as the model wrote it
    assert tc.accounted("plus", {"enum": ["plus"]}, said)[0] and tc.accounted("comfort", {"enum": ["plus", "comfort"], "default": "comfort"}, said)[0]
    assert tc.accounted("Music", {"enum": ["Music", "Theater"]}, tc.Said("a musical performance in New York"))[0]
    assert tc.accounted("Sci-fi", {"enum": ["Drama", "Sci-fi"]}, tc.Said("scientific fiction movies"))[0]
    assert not tc.accounted("Theater", {"enum": ["Music", "Theater"]}, tc.Said("something to do in the city"))[0]      # `the` is no stem
    # and the looser reading releases it
    assert tc.accounted("plus", {"enum": ["plus", "comfort"]}, said, strict_enum=False) == (True, "plus", "")


@pytest.mark.parametrize("value, conversation, ok", [
    (10, "I can wait ten minutes", True), (10, "I can wait a while", False), (0.2, "take 20% off", True),
    (25, "a table for twenty-five", True), (200, "two hundred copies", True), (1250.5, "pay 1,250.50 now", True),
    (3, "items 1,2,3", True), (123, "items 1,2,3", False), (1234567890, "charge my card", False),
    ("2026-03-05", "on March 5th, 2026", True), ("2026-03-05", "sometime soon", False), ("23:00", "text Raj at 11PM", True),
    ("San Francisco, CA", "the best SF psychologist", True), ("Great Britain", "carbon intensity in GB", True),
    ("San Francisco, CA", "weather in San Francisco", True), ("Hà Nội, Vietnam", "weather of Ha Noi", True),
    ("my_token", "list my repositories", False), ("card123", "pay with my card", False),
    ("current location", "get the weather for me", False), ("the", "the weather", False), ([], "anything", False), ({}, "anything", False),
])
def test_a_value_is_accounted_for_by_what_was_said(value, conversation, ok):
    assert tc.accounted(value, {}, tc.Said(conversation))[0] is ok


def test_a_value_that_only_repeats_the_parameters_name_says_nothing():
    said = tc.Said("Retrieve the project that Adriel worked on.")
    assert tc.accounted("Project Name", {}, said, name="project_name") == (False, "Project Name", "it says nothing of its own")
    assert tc.accounted("Project Name", {}, said)[0]                                  # without the name, `project` was said
    assert tc.accounted("New York City", {}, tc.Said("events in New York"), name="city")[0]


def test_lists_and_objects_are_accounted_for_part_by_part():
    said = tc.Said("Make my latte large with coconut milk.")
    prop = {"type": "object", "properties": {"size": {"enum": ["small", "large"]}, "milk": {"type": "string"}}}
    assert tc.accounted({"size": "Large", "milk": "coconut"}, prop, said) == (True, {"size": "large", "milk": "coconut"}, "")
    ok, _value, why = tc.accounted({"size": "large", "milk": "oat"}, prop, said)
    assert not ok and why == "milk = 'oat': those words were not said"
    assert tc.accounted(["coconut", "latte"], {"items": {"type": "string"}}, said)[0]
    assert tc.accounted(["coconut", "vanilla"], {}, said)[2] == "'vanilla': those words were not said"


def test_only_the_person_the_system_and_tool_results_count_as_said():
    messages = [{"role": "system", "content": "The account is 4417."}, {"role": "user", "content": "Refund it."},
                {"role": "assistant", "content": "Shall I refund order 9001?"}, {"role": "tool", "content": "order 77 found"}]
    text = tc.said(messages)
    assert "4417" in text and "77" in text and "9001" not in text
    assert tc.said([{"role": "user", "content": [{"type": "text", "text": "from Lisbon"}]}]) == "from Lisbon"


def test_a_turn_is_released_only_when_every_call_is():
    tools, messages = [WEATHER, RIDE], user("Weather in Lisbon, and a Plus ride from the station in 10 minutes.")
    fine = call("get_weather", loc="Lisbon")
    ride = {"function": {"name": "uber.ride", "arguments": {"loc": "the station", "type": "Plus", "time": 10}}}
    v = tc.check_all(tools, messages, [fine, ride])
    assert v["action"] == "call" and v["calls"] == [{"name": "get_weather", "arguments": {"loc": "Lisbon"}},
                                                    {"name": "uber.ride", "arguments": {"loc": "the station", "type": "plus", "time": 10}}]
    invented = {"function": {"name": "uber.ride", "arguments": {"loc": "123 Main St", "type": "plus", "time": 10}}}
    v = tc.check_all(tools, messages, [fine, invented])
    assert v["action"] == "ask" and "calls" not in v and "To call uber.ride I need `loc`" in tc.question(v)
    assert tc.check_all(tools, messages, [fine, call("delete_everything")])["action"] == "refuse"


def test_the_command_shows_the_call_or_the_question(tmp_path, capsys, monkeypatch):
    tools = tmp_path / "tools.json"
    tools.write_text(json.dumps([WEATHER]))
    replies = iter([{"content": "", "tool_calls": [call("get_weather", loc="Paris, France")]},
                    {"content": "", "tool_calls": [call("get_weather", loc="Lisbon")]}, {"content": "Hello."}])
    monkeypatch.setattr(tc, "ask_model", lambda host, t, m: next(replies))
    out = tmp_path / "v.json"
    assert tc.main(["--host", "h:1", "--tools", str(tools), "--json", str(out), "Get the weather."]) == 1
    assert "To call get_weather I need `loc`" in capsys.readouterr().out and json.loads(out.read_text())["action"] == "ask"
    assert tc.main(["--host", "h:1", "--tools", str(tools), "Weather in Lisbon?"]) == 0
    assert capsys.readouterr().out.strip() == 'CALL get_weather({"loc": "Lisbon"})'
    assert tc.main(["--host", "h:1", "--tools", str(tools), "Hi"]) == 0 and capsys.readouterr().out.strip() == "Hello."
    assert tc.main(["--host", "h:1", "--tools", str(tmp_path / "absent.json"), "Hi"]) == 2


def test_numbers_are_read_as_a_person_writes_them():
    assert tc.numbers("20% off, 1,250.50 dollars, minus -5, a dozen") >= {Fraction(20), Fraction(1, 5), Fraction("1250.5"), Fraction(-5), Fraction(5), Fraction(12)}
    assert Fraction(123) not in tc.numbers("items 1,2,3") and tc.numbers("from 5-10") == {Fraction(5), Fraction(10)}
    assert tc.said_words("October 15th, 2026 at 05:30") == {"october", "10", "15th", "15", "2026", "at", "05", "5", "30"}
    assert {"11pm", "11", "23"} <= tc.said_words("at 11PM") and {"3", "15"} <= tc.said_words("3 p.m.") and "0" in tc.said_words("12 am")
    assert tc.value_words("the 2026-03-05 card123") == ["2026", "3", "5", "card123"]
