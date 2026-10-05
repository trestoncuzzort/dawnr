"""extract_eval.py: SQuAD's scoring, the two-readings rule and the report, with no server and no dataset."""
from locallm import extract_eval as ev

ROWS = [
    {"id": "a", "context": "The door code is 4417. Ask Dana.", "question": "What is the door code?", "answers": ["4417"],
     "values": {"schema": "the code is 4417", "located": None, "span": "4417", "twice": "4417"}},
    {"id": "b", "context": "The door code is 4417. Ask Dana.", "question": "Who has the key?", "answers": [],
     "values": {"schema": "Dana", "located": "Dana", "span": "Dana", "twice": None}},
    {"id": "c", "context": "It opened in the 10th and 11th centuries.", "question": "When?", "answers": ["10th and 11th centuries", "in the 10th and 11th centuries"],
     "values": {"schema": None, "located": None, "span": "the 10th and 11th centuries", "twice": "10th and 11th centuries"}},
]


def test_squads_exact_match_and_f1_after_its_normalisation():
    assert ev.score("The 10th and 11th Centuries.", ROWS[2]["answers"]) == {"shown": True, "em": True, "f1": 1.0}
    assert ev.score(None, ["x"]) == {"shown": False, "em": False, "f1": 0.0}
    assert ev.score("Dana", []) == {"shown": True, "em": False, "f1": 0.0}
    assert round(ev.f1("the code is 4417", "4417"), 3) == 0.5


def test_two_readings_agree_only_on_one_sentence_and_nested_words():
    assert ev.agree((2, "March 3, 2026"), (2, "March 3")) == "March 3"
    assert ev.agree((2, "March 3"), (3, "March 3")) is None and ev.agree((2, "March"), (2, "2026")) is None
    assert ev.agree(None, (1, "x")) is None


def test_the_report_counts_a_value_shown_for_an_unanswerable_question_as_wrong():
    r = ev.report(ROWS)
    assert r["span"]["shown"] == 3 and r["span"]["exact on answerable"] == 2 and r["span"]["left empty on unanswerable"] == 0
    assert r["span"]["exact of shown"] == round(2 / 3, 4)
    assert r["twice"]["shown"] == 2 and r["twice"]["exact of shown"] == 1.0 and r["twice"]["left empty on unanswerable"] == 1
    assert r["schema"]["not in the passage word for word"] == 1 and r["located"]["not in the passage word for word"] == 0


def test_the_sample_is_fixed_and_half_of_it_has_no_answer():
    rows = [{"id": f"y{i}", "answers": ["a"]} for i in range(20)] + [{"id": f"n{i}", "answers": []} for i in range(20)]
    picked = ev.sample(rows, 5)
    assert picked == ev.sample(list(reversed(rows)), 5)
    assert sum(bool(r["answers"]) for r in picked) == 5 and len(picked) == 10


def test_the_arms_read_one_question_through_a_stand_in_server():
    row = ROWS[0]
    seen = []

    def post(url, body):
        seen.append(body)
        if "response_format" in body:
            return {"choices": [{"message": {"content": '{"answer": "4417"}'}}]}
        return {"choices": [{"message": {"content": "S1: The door code is 4417"}}]}
    values = ev.answers("h:1", row, post)
    assert values == {"schema": "4417", "located": "4417", "span": "The door code is 4417", "twice": "The door code is 4417",
                      "value": "4417", "both": "4417"}
    assert seen[0]["response_format"]["json_schema"]["schema"] == ev.SCHEMA
    first, second = seen[1]["messages"][-1]["content"], seen[2]["messages"][-1]["content"]
    assert first.startswith("S1: The door code is 4417.\nS2: Ask Dana.") and second.startswith("S2: Ask Dana.\nS1: The door code is 4417.")
    # the command's own two readings are the measured arms' prompts, word for word
    assert seen[3]["messages"] == seen[0]["messages"] and seen[3]["response_format"] == seen[0]["response_format"]
    assert seen[4]["messages"] == seen[1]["messages"] and seen[4]["grammar"] == seen[1]["grammar"]
    assert ev.SCHEMA_SYSTEM == ev.ex.VALUE_SYSTEM and ev.SPAN_SYSTEM == ev.ex.SYSTEM and ev.SCHEMA == ev.ex.VALUE_SCHEMA


def test_a_second_sample_leaves_out_the_first_ones_questions():
    rows = [{"id": f"y{i}", "answers": ["a"]} for i in range(20)] + [{"id": f"n{i}", "answers": []} for i in range(20)]
    first = ev.sample(rows, 5)
    second = ev.sample(rows, 5, seed=2027, skip=frozenset(r["id"] for r in first))
    assert len(second) == 10 and not {r["id"] for r in first} & {r["id"] for r in second}


def test_an_earlier_runs_answers_are_reported_by_the_arms_they_have():
    assert set(ev.report(ROWS)) == {"schema", "located", "span", "twice"}
    rows = [dict(r, values=dict(r["values"], value=r["values"]["located"], both=None)) for r in ROWS]
    r = ev.report(rows)
    assert set(r) == set(ev.ARMS) and r["both"]["shown"] == 0 and r["value"]["shown"] == 1
    assert r["schema"]["not in a sentence as shown"] == 1 and r["span"]["not in a sentence as shown"] == 0
