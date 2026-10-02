"""t/answer.py: one question through the whole gate. Nothing is shown unless it passed the
question's tests, the specification stage (Clover's consistency check, arXiv:2310.17807) and a
proof with no prover refuting; a refusal names the gate that stopped each attempt."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import answer                                                   # noqa: E402
import py_sandbox                                               # noqa: E402
import spec_check                                               # noqa: E402

pytestmark = pytest.mark.skipif(not py_sandbox.available(), reason="bubblewrap is not installed")

ENTRY = answer.entry_of("Double a number.", ["assert double(3) == 6", "assert double(0) == 0"])


def task(ensures, body="r := 2 * n;"):
    return f"```t\nt 1\ntask double(n: int) returns (r: int)\n  ensures {ensures}\n{{\n  {body}\n}}\n```"


RIGHT, WEAK, OTHER = task("r == 2 * n"), task("n >= 0 ==> r >= n"), task("r == n * n - n", "r := n * n - n;")
PYTHON = "```python\ndef double(n):\n    return 2 * n\n```"
ALL = {k: "verified / refuted" for k in spec_check.KERNELS}


def student(*replies):
    queue = list(replies)

    def decode(conversations, temperature, salt, first, max_new):
        return [(queue.pop(0) if queue else "no answer", True, 0)]
    return decode


def python(reply=PYTHON):
    return lambda conversations, temperature, salt, first, max_new: [(reply, True, 0)]


def prover(cells_for):
    return lambda tasks, jobs: {t["name"]: cells_for(t) for t in tasks}


def test_a_right_answer_is_shown_with_its_level_and_what_stood_behind_the_specification():
    r = answer.answer(ENTRY, student(RIGHT), python(), answers=1, prover=prover(lambda t: dict(ALL, lean="timeout / refuted")))
    s = r["shown"]
    assert s["proved by"] == 6 and s["undecided"] == ["lean"]
    assert s["specification"] == ["ensures r == 2 * n"]
    assert s["behind the specification"]["agrees with the Python on"] >= 10
    assert s["behind the specification"]["mutated outputs rejected"] == 1.0
    assert "SHOWN: proved by 6 of 7 provers" in answer.render(r)


def test_a_weak_specification_is_never_sent_to_the_provers_and_the_refusal_says_why():
    called = []
    r = answer.answer(ENTRY, student(WEAK), python(), answers=1, prover=lambda tasks, jobs: called.append(tasks) or {})
    assert r["shown"] is None and not called
    assert r["refused"] == ["answer 1: weak specification"]
    assert answer.render(r).startswith("REFUSED: no answer's specification could be supported")


def test_another_function_that_fits_the_tests_is_refused_and_the_right_sample_is_shown():
    # n*n - n is 6 at 3 and 0 at 0: it passes both tests and is not doubling
    r = answer.answer(ENTRY, student(OTHER, RIGHT), python(), answers=2, prover=prover(lambda t: ALL))
    assert r["shown"]["answer"] == 2 and r["shown"]["proved by"] == 7
    assert "answer 1: the specification is false at the Python's answer" in r["refused"]


def test_without_a_tested_python_nothing_is_shown():
    r = answer.answer(ENTRY, student(RIGHT), python("```python\ndef double(n):\n    return n\n```"), answers=1,
                      prover=prover(lambda t: ALL))
    assert r["shown"] is None and r["refused"] == ["answer 1: no test-passing Python beside it"]


def test_an_answer_a_prover_refutes_or_none_proves_is_not_shown():
    r = answer.answer(ENTRY, student(RIGHT), python(), answers=1, prover=prover(lambda t: dict(ALL, dafny="refuted / refuted")))
    assert r["shown"] is None and r["refused"] == ["answer 1: refuted by dafny"]
    r = answer.answer(ENTRY, student(RIGHT), python(), answers=1,
                      prover=prover(lambda t: {k: "timeout / refuted" for k in spec_check.KERNELS}))
    assert r["shown"] is None and r["refused"] == ["answer 1: no prover proved it"]


def test_replies_that_do_not_parse_or_fail_a_test_are_named_and_duplicates_count_once():
    bad = task("r == 2 * n", "r := n;")                              # fails the first test
    r = answer.answer(ENTRY, student("prose only", bad, RIGHT, RIGHT), python(), answers=4, prover=prover(lambda t: ALL))
    assert r["pass the tests"] == 1 and r["shown"]["answer"] == 3
    assert r["refused"][:2] == ["answer 1: no task block", "answer 2: fails a test"]


def test_tests_that_are_not_plain_assertions_are_refused_before_anything_is_asked():
    with pytest.raises(ValueError):
        answer.entry_of("x", ["assert f(1) == 2", "assert g(1) == 2"])
    with pytest.raises(ValueError):
        answer.entry_of("x", [])


PARITY = answer.entry_of("Check for odd parity of a number.",
                         ["assert odd_parity(13) == True", "assert odd_parity(21) == True", "assert odd_parity(18) == False"])
IS_ODD = "```t\nt 1\ntask odd_parity(n: int) returns (r: bool)\n  ensures r == (n % 2 == 1)\n{\n  r := n % 2 == 1;\n}\n```"


def two_readings(conversations, temperature, salt, first, max_new):
    """The greedy Python reads 'odd parity' as 'odd'; the sampled ones as an odd count of one bits."""
    code = ("def odd_parity(n):\n    return n % 2 == 1\n" if temperature == 0.0
            else "def odd_parity(n):\n    return bin(n).count('1') % 2 == 1\n")
    return [(f"```python\n{code}```", True, 0)]


def test_a_question_two_test_passing_solutions_read_differently_is_refused_with_the_input_that_settles_it():
    """ClarifyGPT's consistency check (arXiv:2310.10996): with one Python the misreading is shown; with sampled
    solutions that read the question the other way it is refused, and the refusal asks for the deciding test."""
    shown = answer.answer(PARITY, student(IS_ODD), two_readings, answers=1, prover=prover(lambda t: ALL))
    assert shown["shown"] is not None                                    # one Python shares the misreading
    r = answer.answer(PARITY, student(IS_ODD), two_readings, answers=1, prover=prover(lambda t: ALL), consistency=2)
    assert r["shown"] is None and r["refused"] == ["answer 1: the Python solutions read the question differently"]
    assert r["ambiguous"]["another_solution_said"] in (True, False)
    text = answer.render(r)
    assert text.startswith("REFUSED: the question can be read more than one way.")
    assert "Another solution that passes the same tests answers odd_parity(" in text and "--test" in text
