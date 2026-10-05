"""calc.py: arithmetic the model writes, computed exactly, used only when its numbers are the question's and shown
only when separate workings agree (no model server)."""
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


def test_the_question_is_asked_once_greedily_and_then_sampled_under_the_grammar_and_the_result_is_read_out():
    seen = []

    def post(url, body):
        seen.append(body)
        return {"choices": [{"message": {"content": [RIGHT, ALSO_RIGHT, WRONG][len(seen) - 1]}}]}
    r = calc.calc("h:1", EGGS, 3, post)
    assert [b["temperature"] for b in seen] == [0.0, calc.TEMPERATURE, calc.TEMPERATURE] and all(b["grammar"] == calc.GRAMMAR for b in seen)
    assert r["answer"] is None
    text = calc.render(r)
    assert text.startswith("REFUSED: the ways of working it out disagree (18, 18, 25).") and "Way 3 gives 25:" in text
    shown = calc.render(calc.judge(EGGS, [RIGHT, ALSO_RIGHT, "answer = oops\n"]))
    assert shown.startswith("ANSWER: 18\n\n  # eggs left to sell\n  left = 16 - 3 - 4")
    assert "3 ways of working it out were written, 2 could be computed from your question's own numbers, and they all give 18." in shown


def test_the_grammar_ends_the_working_at_its_first_assignment_to_answer():
    assert calc.GRAMMAR.startswith('root ::= step{0,20} "answer = " expr "\\n"\n')
    assert "assign ::= target " in calc.GRAMMAR and 'target ::= [b-z] rest | "a" (' in calc.GRAMMAR
