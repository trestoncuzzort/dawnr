"""t/examples.py: examples a person approves in place of tests they would have to write. The drafts are run in the
sandbox; among the inputs they all answer the one that splits them most evenly is asked first (TiCoder,
arXiv:2404.10100), the inputs some draft fails on come last, and only what the person approved or typed becomes a
test."""
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
    assert left_out == ["draft 2: no Python in the reply", "draft 3: `xs` has no annotation",
                        "draft 4: it takes other kinds of input than most drafts"]
    first, temperature, _salt = m.asked[0]
    assert temperature == 0.0 and [t for _c, t, _s in m.asked[1:]] == [0.8] * 4
    said = first[-1]["content"]
    assert said.startswith("The largest number in a list.\n\nWrite one Python function that does this. What it works on comes in as its parameters")
    assert "built from int, bool, str, list[...] and tuple[...]." in said and "it does not ask for input" in said and "assert" not in said


def test_a_draft_says_which_annotation_was_not_read_and_a_helper_beside_the_function_is_no_obstacle():
    with_helper = "```python\ndef gcd(a: int, b: int) -> int:\n    return a if b == 0 else gcd(b, a % b)\n\ndef lcm(a: int, b: int) -> int:\n    return a * b // gcd(a, b)\n```"
    two_entries = "```python\ndef one(a: int):\n    return a\n\ndef two(a: int):\n    return a\n```"
    fs, left_out = examples.drafts(model(with_helper, py("    return 0", "lcm", "a: float, b: int"), two_entries), "The least common multiple.", 3)
    assert [(f["fn"], f["kinds"]) for f in fs] == [("lcm", ["int", "int"])]            # the function the other is there for
    assert left_out == ["draft 2: `a: float` is not an annotation this reads",
                        "draft 3: the file has more than one function; say which with --fn (one, two)"]


def test_with_a_header_the_drafts_are_held_to_its_name_and_parameters():
    named = py("    return max(xs[:k])", "top", "xs: list[int], k: int")
    m = model(named, py("    return max(xs)", "top", "xs: list[int]"), py("    return 0", "largest", "xs: list[int], k: int"))
    fs, left_out = examples.drafts(m, "The largest of the first k.", 3, header="def top(xs, k):")
    assert [f["n"] for f in fs] == [1]
    assert left_out == ["draft 2: it does not take the parameters asked for", "draft 3: the file has no top-level function `top`"]
    assert "Write the Python function `def top(xs, k):` that does this: keep that name and those parameters, in that order." in m.asked[0][0][-1]["content"]
    assert examples.header_of("top(xs, k)") == ("top", 2) == examples.header_of("def top(xs, k):")


def test_drafts_that_differ_only_in_tuple_or_list_run_side_by_side_and_the_commonest_writing_is_shown():
    as_pairs = py("    return 0", "f", "ps: list[tuple[int, int]]")
    fs, left_out = examples.drafts(model(py("    return 1", "f", "ps: list[list[int]]"), as_pairs, py("    return 2", "f", "ps: List[Tuple[int, ...]]"),
                                         py("    return 3", "f", "ps: tuple[tuple[int, int], ...]"), py("    return 4", "f", "ps: list[str]")), "Pairs.", 5)
    assert [f["n"] for f in fs] == [1, 2, 3, 4] and left_out == ["draft 5: it takes other kinds of input than most drafts"]
    assert examples.shape("tuple[tuple[int, int], ...]") == "list[list[int]]" == examples.shape("list[tuple[int, ...]]")
    assert examples.shape("tuple[str, int]") == "tuple[str, int]" and examples.shape("int") == "int"
    # each of the four wrote its own kind; with nothing commoner, the first draft's is what the examples are written with
    assert examples.shown_kinds(fs) == ["list[list[int]]"]
    assert examples.shown_kinds(fs[1:] + [dict(fs[1], n=9)]) == ["list[tuple[int, int]]"]


def rows(*said_by_draft, inputs=(([3, 9, 2],), ([],), ([5],), ([1, 1],))):
    return [{"args": args, "said": [said[k] for said in said_by_draft]} for k, args in enumerate(inputs)]


def test_among_the_inputs_every_draft_answers_the_most_even_split_is_asked_first_and_answers_prune():
    # three drafts: the largest, the largest again, and the last element; they part on [3, 9, 2] and nowhere else
    d = examples.Dialogue("largest", rows(["9", "0", "5", "1"], ["9", "0", "5", "1"], ["2", "0", "5", "1"]))
    assert d.split(d.rows[0]) == 0.5 and d.split(d.rows[1]) == 0
    q = d.next()
    assert q["call"] == "largest([3, 9, 2])" and q["choices"] == ["9", "2"] and not q["an error"]
    d.answer(q["row"], "9")
    assert d.alive == {0, 1} and d.tests == ["assert largest([3, 9, 2]) == 9"]
    # nothing splits the two left: their plainest answers are put for approval until three examples stand
    q = d.next()
    assert q["call"] == "largest([])" and q["choices"] == ["0"]
    d.answer(q["row"], "0")
    d.answer(d.next()["row"], "5")
    assert d.next() is None and d.tests == ["assert largest([3, 9, 2]) == 9", "assert largest([]) == 0", "assert largest([5]) == 5"]


def test_an_input_some_draft_fails_on_is_asked_last_after_the_plain_examples():
    # four drafts: all say 9 for [3, 9, 2]; on [] two say 0, one says None, one raises
    d = examples.Dialogue("largest", rows(["9", "0", "5", "1"], ["9", "0", "5", "1"], ["9", "None", "5", "1"], ["9", None, "5", "1"]))
    assert d.split(d.rows[1]) == 0.5 == d.doubt(d.rows[1])      # 0, 0, None, and one that raises: TiCoder leaves it out
    asked = []
    for value in ("9", "5", "1"):                               # the three inputs they all answer, in the order drawn
        q = d.next()
        asked.append(q["call"])
        assert not q["an error"] and q["choices"] == [value]
        d.answer(q["row"], value)
    assert asked == ["largest([3, 9, 2])", "largest([5])", "largest([1, 1])"]
    q = d.next()                                                # then whether the empty list is allowed, and what it gives
    assert q["call"] == "largest([])" and q["choices"] == ["0", "None"] and q["an error"]
    d.answer(q["row"], "None")
    assert d.alive == {2} and d.tests[-1] == "assert largest([]) == None" and d.next() is None      # four questions were put
    # a draft that answers nothing at all is not standing, so it makes no input one that "a draft fails on"
    d = examples.Dialogue("largest", rows(["9", "0", "5", "1"], [None, None, None, None]))
    assert d.alive == {0} and not d.next()["an error"]


def test_an_input_that_should_not_be_allowed_makes_no_test_and_a_typed_value_is_taken_as_written():
    d = examples.Dialogue("largest", rows(["9", "0", "5", "1"], ["9", None, "5", "1"]), questions=3)
    d.answer(1, None)                                           # the empty list is not allowed: no test, nobody dropped
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
    tests, prompts, shown = talk(d, "", "maybe", "x", "", "7", "", "1")
    assert shown[0].startswith("Before anything is proved, a few examples") and len(shown) == 4
    assert prompts[0] == "largest([])  the drafts disagree:  a) 0   b) None\n  Type a or b, or the right result, or x:  > "
    assert "nothing to accept" in shown[1] and "not a value I can read" in shown[2]      # Enter on a disagreement, then a word
    assert prompts[3] == "largest([3, 9, 2])  gives  9   > "
    # the 7 typed for [5] is what no draft says: it stands as the person's example, no draft is left, and the next
    # input is put with nothing proposed (Enter there accepts nothing)
    assert prompts[5] == "largest([1, 1])  should give what? (the right result, or x)  > " and "Nothing is proposed here" in shown[3]
    assert tests == ["assert largest([3, 9, 2]) == 9", "assert largest([5]) == 7", "assert largest([1, 1]) == 1"]


def test_with_no_draft_left_the_plainest_inputs_are_still_put_until_there_are_enough_examples():
    d = examples.Dialogue("largest", rows(["9", "0", "5", "1"]), questions=6)
    d.answer(0, "8")                                            # the one draft said 9
    assert d.alive == set()
    q = d.next()
    assert q == {"row": 1, "call": "largest([])", "choices": [], "an error": False}
    d.answer(1, None)                                           # not allowed: no test, and the asking goes on
    d.answer(d.next()["row"], "5")
    d.answer(d.next()["row"], "1")
    assert d.next() is None and len(d.tests) == 3               # three examples are enough
    never_ran = examples.Dialogue("f", rows([None, None, None, None]))
    assert never_ran.next() == {"row": 0, "call": "f([3, 9, 2])", "choices": [], "an error": False}


def test_a_letter_picks_among_the_drafts_answers_and_a_closed_terminal_keeps_what_was_approved():
    d = examples.Dialogue("largest", rows(["9", "0", "5", "1"], ["9", "None", "5", "1"], ["9", None, "5", "1"]))
    tests, prompts, _shown = talk(d, "", "", "", "B")
    assert tests[:3] == ["assert largest([3, 9, 2]) == 9", "assert largest([5]) == 5", "assert largest([1, 1]) == 1"]
    assert "a) 0   b) None   (and a draft fails on it)" in prompts[3] and tests[3] == "assert largest([]) == None" and d.alive == {1}

    # one answer and a draft that fails: Enter still accepts the answer, and the prompt says what x would mean
    d = examples.Dialogue("largest", rows(["9", "0", "5", "1"], ["9", None, "5", "1"]))
    tests, prompts, _shown = talk(d, "", "", "", "")
    assert prompts[3] == "largest([])  gives  0   (a draft fails on this input: x if it should not be allowed)   > "
    assert tests[3] == "assert largest([]) == 0" and d.alive == {0}

    def gone(prompt):
        raise EOFError
    d = examples.Dialogue("largest", rows(["9", "0", "5", "1"], ["9", "0", "5", "1"]))
    d.answer(0, "9")
    assert examples.interactive(d, gone, lambda text: None) == ["assert largest([3, 9, 2]) == 9"]


@needs_sandbox
def test_the_drafts_are_run_in_the_sandbox_and_the_examples_are_what_the_gate_reads():
    d, made = examples.propose(model(RIGHT, EMPTY_ZERO, EMPTY_NONE, LAST, RIGHT), "The largest number in a list.")
    assert made["drafts"] == [1, 2, 3, 4] and made["fn"] == "largest" and made["kinds"] == ["list[int]"]      # the fifth repeats the first
    # the empty list is the input they part on, but one of them fails on it, so it waits: [3, 1, 2] comes first,
    # where the draft that returns the last element says 2 and the others 3
    first = d.next()
    assert first["call"] == "largest([3, 1, 2])" and first["choices"] == ["3", "2"] and not first["an error"]
    # the person: the largest of an empty list is not a thing; otherwise the largest
    tests = examples.simulate(d, lambda args: repr(max(args[0])) if args[0] else None)
    assert len(tests) == 3 and tests[0] == "assert largest([3, 1, 2]) == 3" and all(t.startswith("assert largest([") for t in tests)
    assert d.left == 0 and 1 in d.asked                         # the fourth question was the empty list, and it made no test
    entry = answer.entry_of("The largest number in a list.", tests)
    assert entry["fn"] == "largest" and len(entry["points"]) == len(tests)
    # the draft that returns the last element is gone once an example separates it
    assert 3 not in d.alive


@needs_sandbox
def test_tuples_reach_a_draft_as_tuples_and_a_draft_that_does_not_load_answers_nothing():
    pairs = py("    return [a + b for a, b in ps]", "sums", "ps: list[tuple[int, int]]")
    broken = "```python\nfrom typing import ListInt\ndef sums(ps: list[tuple[int, int]]):\n    return []\n```"
    isinstance_check = py("    assert all(isinstance(p, tuple) for p in ps)\n    return [p[0] + p[1] for p in ps]", "sums", "ps: List[Tuple[int, int]]")
    d, made = examples.propose(model(pairs, broken, isinstance_check), "Add up each pair in a list of pairs.", n=3)
    assert made["kinds"] == ["list[tuple[int, int]]"] and made["drafts"] == [1, 2, 3]
    first = d.rows[0]
    assert first["args"] == ([(1, 2), (3, 4)],) and first["said"] == ["[3, 7]", None, "[3, 7]"]      # the broken one says nothing
    assert d.next()["call"] == "sums([(1, 2), (3, 4)])"
    one = py("    return sum(xs)", "total", "xs: tuple[int, ...]")
    d, made = examples.propose(model(one), "Add up a tuple of numbers.", n=1)
    assert made["kinds"] == ["tuple[int, ...]"] and d.next()["call"] == "total((1, 2, 3))"


def test_only_the_inputs_of_the_calls_the_model_suggests_are_taken():
    reply = ("Here are the calls:\n1. `is_magic([[2, 7, 6], [9, 5, 1], [4, 3, 8]])`\n2. is_magic([[1, 2], [3, 4]])  # not magic\n"
             "- is_magic([[1]]) == True\nprint(is_magic([]))\nis_magic([[2, 7, 6], [9, 5, 1], [4, 3, 8]])\nis_magic(matrix)\n"
             "is_magic([[1.5]])\nnot_is_magic([[5]])\nis_magic([[1]], 3)\nis_magic(m=[[1]])\nis_magic([[" + "1, " * 13 + "]])\n")
    # a call each once, as the kinds write it; the `== True` after one is not read; names, floats, another function,
    # another number of arguments, keywords and a value too long to read are passed over
    assert examples.suggested(reply, "is_magic", ["list[tuple[int, int]]"]) == [
        ([(2, 7, 6), (9, 5, 1), (4, 3, 8)],), ([(1, 2), (3, 4)],), ([(1,)],), ([],)]
    assert examples.suggested("f('a)b(', [1, 2])\nf('it\\'s', (3,))\nf('unclosed", "f", ["str", "tuple[int, ...]"]) == [("a)b(", (1, 2)), ("it's", (3,))]
    assert examples.suggested(None, "f", ["int"]) == [] == examples.suggested("f(1)\n" * 3, "g", ["int"])
    assert len(examples.suggested("\n".join(f"f({i})" for i in range(20)), "f", ["int"])) == examples.SUGGESTED
    asked = examples.suggestion("Is it a magic square?", "is_magic(m: list[list[int]])")[0]["content"]
    assert asked.startswith("A function `is_magic(m: list[list[int]])` has already been written for this request:\n\nIs it a magic square?")
    assert "Do not write the function." in asked and "with no result" in asked


@needs_sandbox
def test_the_suggested_inputs_are_run_first_and_what_the_model_wrote_beside_them_is_never_a_result():
    magic = py("    return len(m) == 3 and all(sum(r) == 15 for r in m)", "is_magic", "m: list[list[int]]")
    m = model(magic, "is_magic([[2, 7, 6], [9, 5, 1], [4, 3, 8]]) == False\nis_magic([[1, 2], [3, 4]]) == True")
    d, made = examples.propose(m, "Is it a 3 by 3 magic square?", n=1)
    assert made["suggested"] == 2 and [row["args"] for row in d.rows[:2]] == [([[2, 7, 6], [9, 5, 1], [4, 3, 8]],), ([[1, 2], [3, 4]],)]
    assert d.rows[0]["said"] == ["True"] and d.rows[1]["said"] == ["False"]      # what the draft does, not what was written beside the call
    assert "A function `is_magic(m: list[list[int]])` has already been written" in m.asked[-1][0][-1]["content"]
    assert d.next()["call"] == "is_magic([[2, 7, 6], [9, 5, 1], [4, 3, 8]])" and len(d.rows) > 4          # the drawn inputs follow


@needs_sandbox
def test_with_no_draft_that_runs_the_person_is_told_to_give_examples():
    with pytest.raises(examples.Refused, match="wrote no Python draft that could be run"):
        examples.propose(model("nothing", "still nothing"), "Something.", n=2)
