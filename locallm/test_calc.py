"""calc.py: arithmetic the model writes, computed exactly, used only when its numbers are the question's and shown
only when separate workings agree (no model server)."""
import json
from fractions import Fraction

import pytest

from locallm import calc

EGGS = ("Janet's ducks lay 16 eggs per day. She eats three for breakfast and bakes muffins with four. She sells the "
        "remainder for $2 per egg. How much does she make every day?")
RIGHT = "# eggs left to sell\nleft = 16 - 3 - 4\n# money made\nanswer = left * 2\n"
ALSO_RIGHT = "eaten = 3 + 4\nanswer = (16 - eaten) * 2\n"
WRONG = "answer = 16 * 2 - 3 - 4\n"


def test_arithmetic_is_exact_and_division_and_rounding_are_a_persons():
    assert calc.evaluate("x = 0.1 + 0.2\nanswer = x * 10\n")[0] == 3            # no floating point
    assert calc.evaluate("answer = 7 / 2\n")[0] == Fraction(7, 2) and calc.evaluate("answer = 7 // 2\n")[0] == 3
    assert calc.evaluate("answer = -7 // 2\n")[0] == -4 and calc.evaluate("answer = -7 % 3\n")[0] == 2
    assert calc.evaluate("answer = round(2.5) + round(3.5) + round(-2.5)\n")[0] == 4   # halves away from zero: 3 + 4 - 3
    assert calc.evaluate("answer = round(10 / 3, 2)\n")[0] == Fraction(333, 100)
    assert calc.evaluate("answer = max(2, 3 ** 2, floor(9.9)) + ceil(0.1) + abs(-4) + min(1, 2)\n")[0] == 15
    value, written = calc.evaluate(RIGHT)
    assert value == 18 and written == [16, 3, 4, 2]


@pytest.mark.parametrize("program, why", [
    ("answer = x + 1\n", "`x` is used before it is given a value"),
    ("x = 1\n", "it never assigns `answer`"),
    ("answer = 1 / 0\n", "a division by zero"),
    ("answer = 2 ** 0.5\n", "a power that is not a small whole number"),
    ("answer = 2 ** 500\n", "a power that is not a small whole number"),
    ("import os\nanswer = 1\n", "a line that is not `name = arithmetic`"),
    ("answer = __import__('os').getcwd()\n", "something other than arithmetic"),
    ("answer = len('ab')\n", "something other than arithmetic"),
    ("answer = 'a' * 3\n", "is not a number"),
    ("answer = (1 +\n", "it is not arithmetic this reads"),
    ("answer = abs(1, 2)\n", "`abs` with the wrong number of values"),
])
def test_anything_but_arithmetic_over_assigned_names_is_unusable_and_says_why(program, why):
    with pytest.raises(calc.Unusable, match=why.replace("(", r"\(").replace(")", r"\)").replace("*", r"\*")):
        calc.evaluate(program)


def test_a_workings_numbers_must_be_the_questions_or_a_unit():
    assert calc.ungrounded([Fraction(16), Fraction(3), Fraction(4), Fraction(2)], EGGS) == []   # "three", "four" are words
    assert calc.ungrounded([Fraction(16), Fraction(5)], EGGS) == [Fraction(5)]
    q = "A coat costs $80 and is 20% off. A dozen buttons cost half as much as the coat. How much is the coat now?"
    for stated in ("0.2", "20", "0.8", "100", "12", "0.5", "2", "80", "1.2"):
        assert calc.ungrounded([Fraction(stated)], q) == [], stated
    assert calc.ungrounded([Fraction("0.25")], q) == [Fraction(1, 4)] and calc.ungrounded([Fraction(81)], q) == [Fraction(81)]
    assert calc.ungrounded([Fraction("2340")], "What is 17.5% of 2,340?") == []


def test_an_answer_is_shown_only_when_every_usable_working_agrees_and_two_could_be_used():
    r = calc.judge(EGGS, [RIGHT, ALSO_RIGHT, RIGHT])
    assert r["answer"] == 18 and r["agree"] == 3
    r = calc.judge(EGGS, [RIGHT, WRONG, RIGHT])
    assert r["answer"] is None and r["why"] == "the ways of working it out disagree (18, 25, 18)"
    r = calc.judge(EGGS, [RIGHT, "answer = 36\n", "answer = oops\n"])
    assert r["answer"] is None and r["why"].startswith("fewer than two ways") and r["agree"] == 1
    assert r["ways"][1]["why"] == "it uses 36, which the question does not state"
    # a working done in the head, even a right one, brings in a number the question does not state
    assert calc.judge(EGGS, [RIGHT, "answer = 18\n", ALSO_RIGHT])["answer"] == 18
    assert calc.judge(EGGS, [RIGHT, "answer = 18\n"])["answer"] is None
    # without the grounding rule the same workings would have been used
    assert calc.judge(EGGS, [RIGHT, "answer = 18\n"], grounded=False)["answer"] == 18


@pytest.mark.parametrize("x, text", [(Fraction(18), "18"), (Fraction(81, 5), "16.2"), (Fraction(819, 2), "409.5"),
                                     (Fraction(1, 3), "1/3 (about 0.3333)"), (Fraction(-7, 4), "-1.75"), (Fraction(1, 8), "0.125")])
def test_a_rational_is_shown_as_a_person_writes_it(x, text):
    assert calc.show(x) == text


def test_the_old_gate_reads_out_its_verdict():
    text = calc.render(calc.judge(EGGS, [RIGHT, ALSO_RIGHT, WRONG]))
    assert text.startswith("REFUSED: the ways of working it out disagree (18, 18, 25).") and "Way 3 gives 25:" in text
    shown = calc.render(calc.judge(EGGS, [RIGHT, ALSO_RIGHT, "answer = oops\n"]))
    assert shown.startswith("ANSWER: 18\n\n  # eggs left to sell\n  left = 16 - 3 - 4")
    assert "3 ways of working it out were written, 2 could be computed from your question's own numbers, and they all give 18." in shown


REASONED = "She has 16 - 3 - 4 = 9 eggs left and sells each for $2.\n9 * 2 = 18\n#### 18"


def test_the_reasoned_number_is_shown_only_when_a_separate_working_computes_it():
    r = calc.settle(EGGS, REASONED, [WRONG, RIGHT, "answer = oops\n"])
    assert r["answer"] == 18 and r["stated"] == 18 and r["agree"] == 1 and "why" not in r
    # the reasoning and the workings disagree: nothing is shown, and the refusal says what each gave
    r = calc.settle(EGGS, REASONED.replace("#### 18", "#### 81"), [RIGHT, WRONG, RIGHT])
    assert r["answer"] is None and r["why"] == "the reasoning ends on 81 and no working computed gives that (18, 25, 18)"
    # a stricter gate wants more than one working behind the number
    assert calc.settle(EGGS, REASONED, [RIGHT, WRONG, WRONG], needed=2)["why"] == "the reasoning ends on 18 and only 1 of the workings computed gives that (18, 25, 25)"
    assert calc.settle(EGGS, REASONED, [RIGHT, ALSO_RIGHT, WRONG], needed=2)["answer"] == 18
    assert calc.settle(EGGS, "It cannot be known.", [RIGHT])["why"] == "the reasoning does not end on a number"
    assert calc.settle(EGGS, REASONED, ["answer = oops\n"])["why"] == "no working could be computed to check the reasoning's 18"
    # a working done in the head agrees and is used, with the number it brought in pointed out
    r = calc.settle(EGGS, REASONED, ["answer = 18\n"])
    assert r["answer"] == 18 and r["ways"][0]["note"] == "it uses 18, which the question does not state"


def test_the_number_a_reply_ends_on():
    assert calc.reasoned_number("so 9 * 2 = 18\n#### 18 dollars") == 18 and calc.reasoned_number("The answer is 1,000 dollars.") == 1000
    assert calc.reasoned_number("#### $1,250.50") == Fraction("1250.5") and calc.reasoned_number("#### -3") == -3
    assert calc.reasoned_number("no number here") is None


def test_the_question_is_reasoned_once_in_prose_then_worked_under_the_grammar_and_the_result_is_read_out():
    seen = []

    def post(url, body):
        seen.append(body)
        return {"choices": [{"message": {"content": [REASONED, WRONG, ALSO_RIGHT, "answer = 18\n"][len(seen) - 1]}}]}
    r = calc.calc("h:1", EGGS, 3, post=post)
    # the prose answer first, free, with the measured prompt; then three workings under the grammar, none shown the prose
    assert "grammar" not in seen[0] and seen[0]["messages"][0]["content"] == calc.REASON_SYSTEM and seen[0]["temperature"] == 0
    assert [b["temperature"] for b in seen[1:]] == [0.0, calc.TEMPERATURE, calc.TEMPERATURE] and all(b["grammar"] == calc.GRAMMAR for b in seen[1:])
    assert all(b["messages"][-1]["content"] == EGGS for b in seen)
    assert r["answer"] == 18 and r["agree"] == 2 and r["question"] == EGGS
    text = calc.render(r)
    assert text.startswith("ANSWER: 18\n\n  eaten = 3 + 4\n  answer = (16 - eaten) * 2")       # the first working that agrees
    assert "The model reasoned its way to 18 in words; this working, written separately and computed exactly, gives the same (2 of 3 workings do)." in text
    refused = calc.render(calc.settle(EGGS, REASONED.replace("#### 18", "#### 81"), [RIGHT, "answer = oops\n"]))
    assert refused.startswith("REFUSED: the reasoning ends on 81 and no working computed gives that (18).")
    assert "Working 1 gives 18:" in refused and "Working 2 could not be computed:" in refused and "The reasoning:" in refused
    noted = calc.render(calc.settle(EGGS, REASONED, ["answer = 18\n"]))
    assert "Note: it uses 18, which the question does not state." in noted


def test_the_command_exits_zero_only_with_an_answer(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(calc, "calc", lambda host, question, ways, needed: dict(calc.settle(question, REASONED, [RIGHT]), question=question))
    out = tmp_path / "r.json"
    assert calc.main(["--host", "h:1", "--json", str(out), EGGS]) == 0 and capsys.readouterr().out.startswith("ANSWER: 18")
    saved = json.loads(out.read_text())
    assert saved["answer"] == "18" and saved["stated"] == "18" and saved["ways"][0]["value"] == "18"
    monkeypatch.setattr(calc, "calc", lambda host, question, ways, needed: dict(calc.settle(question, "#### 5", [RIGHT]), question=question))
    assert calc.main(["--host", "h:1", EGGS]) == 1 and capsys.readouterr().out.startswith("REFUSED:")


def test_the_grammar_ends_the_working_at_its_first_assignment_to_answer():
    assert calc.GRAMMAR.startswith('root ::= step{0,20} "answer = " expr "\\n"\n')
    assert "assign ::= target " in calc.GRAMMAR and 'target ::= [b-z] rest | "a" (' in calc.GRAMMAR
