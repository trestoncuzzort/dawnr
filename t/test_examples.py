"""t/examples.py: examples a person approves in place of tests they would have to write. The drafts are run in the
sandbox, the input that splits them most evenly is asked first (TiCoder, arXiv:2404.10100), and only what the
person approved or typed becomes a test."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import answer                                                   # noqa: E402
import examples                                                 # noqa: E402
import py_sandbox                                               # noqa: E402

needs_sandbox = pytest.mark.skipif(not py_sandbox.available(), reason="no sandbox for the drafts here")


def py(body: str, name: str = "largest", params: str = "xs: list[int]") -> str:
    return f"```python\ndef {name}({params}):\n{body}\n```"


RIGHT = py("    return max(xs)")
EMPTY_ZERO = py("    return max(xs) if xs else 0")
EMPTY_NONE = py("    best = None\n    for x in xs:\n        if best is None or x > best:\n            best = x\n    return best", "biggest")
LAST = py("    return xs[-1]")


def model(*replies):
    queue, asked = list(replies), []

    def decode(conversations, temperature, salt, first, max_new):
        asked.append((conversations[0], temperature, salt))
        return [(queue.pop(0) if queue else "nothing", True, 0)]
    decode.asked = asked
    return decode


def test_the_drafts_are_asked_from_the_words_alone_with_annotated_parameters():
    m = model(RIGHT, "no code here", py("    return max(xs)", params="xs"), py("    return 0", params="n: int"), EMPTY_ZERO)
    fs, left_out = examples.drafts(m, "The largest number in a list.", 5)
    assert [f["n"] for f in fs] == [1, 5] and [f["kinds"] for f in fs] == [["list[int]"], ["list[int]"]]
    assert left_out == ["draft 2: no Python in the reply", "draft 3: a parameter has no annotation this reads",
                        "draft 4: it takes other kinds of input than most drafts"]
    first, temperature, _salt = m.asked[0]
    assert temperature == 0.0 and [t for _c, t, _s in m.asked[1:]] == [0.8] * 4
    assert first[-1]["content"].startswith("The largest number in a list.\n\nWrite one Python function that does this.")
    assert "list[list[int]]" in first[-1]["content"] and "assert" not in first[-1]["content"]


def rows(*said_by_draft, inputs=(([3, 9, 2],), ([],), ([5],), ([1, 1],))):
    return [{"args": args, "said": [said[k] for said in said_by_draft]} for k, args in enumerate(inputs)]


def test_the_input_that_splits_the_drafts_most_evenly_is_asked_first_and_answers_prune():
    # four drafts: all say 9 for [3, 9, 2]; on [] two say 0, one says None, one raises
    d = examples.Dialogue("largest", rows(["9", "0", "5", "1"], ["9", "0", "5", "1"], ["9", "None", "5", "1"], ["9", None, "5", "1"]))
    q = d.next()
    assert q["call"] == "largest([])" and q["choices"] == ["0", "None"] and q["an error"] and d.split(d.rows[1]) == 0.5
    assert d.split(d.rows[0]) == 0                              # they all say 9 there
    d.answer(q["row"], "None")
    assert d.alive == {2} and d.tests == ["assert largest([]) == None"]
    # nothing splits the one draft left: its plainest answers are put for approval until three examples stand
    q = d.next()
    assert q["call"] == "largest([3, 9, 2])" and q["choices"] == ["9"] and not q["an error"]
    d.answer(q["row"], "9")
    d.answer(d.next()["row"], "5")
    assert d.next() is None and d.tests == ["assert largest([]) == None", "assert largest([3, 9, 2]) == 9", "assert largest([5]) == 5"]


def test_an_input_that_should_not_be_allowed_makes_no_test_and_a_typed_value_is_taken_as_written():
    d = examples.Dialogue("largest", rows(["9", "0", "5", "1"], ["9", None, "5", "1"]), questions=3)
    q = d.next()
    assert q["call"] == "largest([])" and q["choices"] == ["0"] and q["an error"]
    d.answer(q["row"], None)                                    # not allowed: no test, nobody dropped
    assert d.tests == [] and d.alive == {0, 1}
    d.answer(d.next()["row"], "(9)")                            # typed: the value, as Python writes it
    assert d.tests == ["assert largest([3, 9, 2]) == 9"]
    d.answer(d.next()["row"], "6")                              # no draft says 6: the example still stands, the drafts do not
    assert d.alive == set() and d.next() is None and d.tests[-1] == "assert largest([5]) == 6"
    with pytest.raises(ValueError, match="not a value this reads"):
        examples.Dialogue("f", rows(["1", "1", "1", "1"])).answer(0, "nine")


def test_a_tuple_and_a_list_of_the_same_elements_are_one_answer():
    d = examples.Dialogue("pair", rows(["(1, 2)", "0", "0", "0"], ["[1, 2]", "0", "0", "0"]))
    assert d.split(d.rows[0]) == 0 and d._groups(d.rows[0]) == [("(1, 2)", 2)]
    d.answer(0, "[1, 2]")
    assert d.alive == {0, 1} and d.tests == ["assert pair([3, 9, 2]) == [1, 2]"]
    assert examples.read_value("[1, 3]") == (True, [1, 3]) and examples.read_value("nine") == (False, None)


def talk(d, *replies):
    queue, shown, prompts = list(replies), [], []

    def ask(prompt):
        prompts.append(prompt)
        return queue.pop(0)
    return examples.interactive(d, ask, shown.append), prompts, shown


def test_in_a_terminal_enter_accepts_a_value_corrects_and_x_skips():
    d = examples.Dialogue("largest", rows(["9", "0", "5", "1"], ["9", "None", "5", "1"]))
    tests, prompts, shown = talk(d, "", "maybe", "x", "", "7")
    assert shown[0].startswith("Before anything is proved, a few examples") and len(shown) == 3
    assert prompts[0] == "largest([])  the drafts disagree:  a) 0   b) None\n  Type a or b, or the right result, or x:  > "
    assert "nothing to accept" in shown[1] and "not a value I can read" in shown[2]      # Enter on a disagreement, then a word
    assert prompts[3] == "largest([3, 9, 2])  gives  9   > "
    # the 7 typed for [5] is what no draft says: it stands as the person's example, and there is no draft left to ask about
    assert tests == ["assert largest([3, 9, 2]) == 9", "assert largest([5]) == 7"] and len(prompts) == 5


def test_a_letter_picks_among_the_drafts_answers_and_a_closed_terminal_keeps_what_was_approved():
    d = examples.Dialogue("largest", rows(["9", "0", "5", "1"], ["9", "None", "5", "1"], ["9", None, "5", "1"]))
    tests, prompts, _shown = talk(d, "B", "", "")
    assert "a) 0   b) None   (and a draft fails on it)" in prompts[0] and tests[0] == "assert largest([]) == None"
    assert d.alive == {1} and tests[1:] == ["assert largest([3, 9, 2]) == 9", "assert largest([5]) == 5"]

    def gone(prompt):
        raise EOFError
    d = examples.Dialogue("largest", rows(["9", "0", "5", "1"], ["9", "0", "5", "1"]))
    d.answer(0, "9")
    assert examples.interactive(d, gone, lambda text: None) == ["assert largest([3, 9, 2]) == 9"]


@needs_sandbox
def test_the_drafts_are_run_in_the_sandbox_and_the_examples_are_what_the_gate_reads():
    d, made = examples.propose(model(RIGHT, EMPTY_ZERO, EMPTY_NONE, LAST, RIGHT), "The largest number in a list.")
    assert made["drafts"] == [1, 2, 3, 4] and made["fn"] == "largest" and made["kinds"] == ["list[int]"]      # the fifth repeats the first
    first = d.next()
    assert first["call"] == "largest([])" and set(first["choices"]) == {"0", "None"} and first["an error"]
    # the person: the largest of an empty list is not a thing; otherwise the largest
    tests = examples.simulate(d, lambda args: repr(max(args[0])) if args[0] else None)
    assert 2 <= len(tests) <= examples.QUESTIONS - 1 and all(t.startswith("assert largest([") for t in tests)
    entry = answer.entry_of("The largest number in a list.", tests)
    assert entry["fn"] == "largest" and len(entry["points"]) == len(tests)
    # the draft that returns the last element is gone once an example separates it
    assert 3 not in d.alive


@needs_sandbox
def test_with_no_draft_that_runs_the_person_is_told_to_give_examples():
    with pytest.raises(examples.Refused, match="wrote no Python draft that could be run"):
        examples.propose(model("nothing", "still nothing"), "Something.", n=2)
