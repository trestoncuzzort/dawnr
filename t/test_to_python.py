#!/usr/bin/env python3
"""t/to_python.py: a proved `t` program written again in Python and run beside `t`'s own interpreter.

Differential testing is the whole of the check (two implementations, the same inputs, any disagreement a bug;
research receipt 3a0219b3d74f), so these tests are about the places the two languages part: Euclidean division,
strings at the boundary, early returns, and a translation that is wrong being caught rather than shown.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import py_sandbox                                               # noqa: E402
import surface                                                  # noqa: E402
import to_python                                                # noqa: E402

needs_sandbox = pytest.mark.skipif(not py_sandbox.available(), reason="bubblewrap is not installed")


def parse(text: str) -> dict:
    return surface.parse(text.strip() + "\n")


def run(source: str, fn: str, *args):
    scope: dict = {}
    exec(source, scope)                                         # noqa: S102 -- the translator's own output, in a test
    return scope[fn](*args)


DIVMOD = """
t 1
task divmod_t(a: int, b: int) returns (r: int)
  requires b != 0
  ensures r == a / b * 1000 + a % b
{
  r := a / b * 1000 + a % b;
}
"""

UPPER_COUNT = """
t 1
gate loops
task count_upper(s: seq) returns (r: int)
  ensures r >= 0
{
  r := 0;
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    invariant r >= 0
    decreases len(s) - i
  {
    if s[i] >= 65 and s[i] <= 90 {
      r := r + 1;
    } else {
    }
    i := i + 1;
  }
}
"""

REVERSE = """
t 1
gate loops
task rev(s: seq) returns (r: seq)
  ensures len(r) == len(s)
{
  r := [];
  var i: int := len(s);
  while i > 0
    invariant 0 <= i and i <= len(s)
    invariant len(r) == len(s) - i
    decreases i
  {
    i := i - 1;
    r := r + [s[i]];
  }
}
"""

FIRST_NEG = """
t 1
gate loops
task first_negative(a: seq) returns (r: int)
  ensures r == -1 or (0 <= r and r < len(a))
{
  var i: int := 0;
  r := -1;
  while i < len(a)
    invariant 0 <= i and i <= len(a)
    invariant r == -1
    decreases len(a) - i
  {
    if a[i] < 0 {
      r := i;
      return r;
    } else {
    }
    i := i + 1;
  }
}
"""

KEYWORDS = """
t 0
task match(lambda: int, class: int) returns (r: int)
  ensures r == lambda + class
{
  r := lambda + class;
}
"""


def test_division_and_modulo_are_euclidean_not_pythons_floor():
    source, fn = to_python.translate(parse(DIVMOD))
    # t: -7 / 2 == -4 and -7 % 2 == 1; 7 / -2 == -3 and 7 % -2 == 1 (the remainder is never negative)
    assert run(source, fn, -7, 2) == -4 * 1000 + 1
    assert run(source, fn, 7, -2) == -3 * 1000 + 1
    assert run(source, fn, -7, -2) == 4 * 1000 + 1
    assert -7 // -2 * 1000 + -7 % -2 != run(source, fn, -7, -2)      # Python's own answer differs here


def test_a_string_in_the_questions_tests_is_a_string_at_the_boundary():
    tests = ['assert count_upper("PYthon") == 2']
    source, fn = to_python.translate(parse(UPPER_COUNT), tests, "count_upper")
    assert run(source, fn, "PYthon") == 2 and run(source, fn, "") == 0
    source, fn = to_python.translate(parse(REVERSE), ['assert rev("abc") == "cba"'], "rev")
    assert run(source, fn, "abc") == "cba"


def test_a_list_in_the_questions_tests_stays_a_list():
    source, fn = to_python.translate(parse(REVERSE), ["assert rev([1, 2, 3]) == [3, 2, 1]"], "rev")
    assert run(source, fn, [1, 2, 3]) == [3, 2, 1]
    assert isinstance(run(source, fn, []), list)


def test_an_early_return_leaves_the_loop():
    source, fn = to_python.translate(parse(FIRST_NEG), ["assert first_negative([1, -2, -3]) == 1"], "first_negative")
    assert run(source, fn, [1, -2, -3]) == 1 and run(source, fn, [1, 2]) == -1


def test_the_function_keeps_the_questions_name_and_hard_keywords_are_renamed():
    source, fn = to_python.translate(parse(KEYWORDS))
    assert fn == "match"                                        # a soft keyword: still the name the tests call
    assert "lambda_" in source and "class_" in source
    assert run(source, fn, 2, 3) == 5


def test_the_specification_is_carried_in_the_docstring_and_invariants_as_comments():
    source, _fn = to_python.translate(parse(UPPER_COUNT), [], "count_upper")
    assert "ensures  r >= 0" in source and "# invariant: 0 <= i and i <= len(s)" in source
    assert "checked against `t`, not itself proved" in source


def test_a_datatype_is_refused_by_name_and_not_guessed():
    task = parse(DIVMOD)
    task["body"] = [{"assign": ["r", {"ctor": {"dtype": "Colour", "ctor": "Red", "args": []}}]}]
    with pytest.raises(to_python.Unsupported, match="datatypes"):
        to_python.translate(task)


@needs_sandbox
def test_check_agrees_on_a_right_translation_with_the_tests_among_the_inputs():
    task = parse(DIVMOD)
    source, fn = to_python.translate(task, ["assert divmod_t(7, 2) == 3001"], "divmod_t")
    report = to_python.check(task, source, fn, ["assert divmod_t(7, 2) == 3001"])
    assert report["agrees"] and report["inputs"] >= 20


@needs_sandbox
def test_check_catches_a_translation_that_uses_pythons_division():
    task = parse(DIVMOD)
    source, fn = to_python.translate(task, [], "divmod_t")
    wrong = source.replace("_t_div(a, b)", "(a // b)").replace("_t_mod(a, b)", "(a % b)")
    assert wrong != source
    report = to_python.check(task, wrong, fn, [])
    assert not report["agrees"] and "why" in report


@needs_sandbox
def test_check_draws_only_inputs_the_requires_admits():
    task = parse(DIVMOD)                                        # requires b != 0: no input divides by zero
    source, fn = to_python.translate(task, [], "divmod_t")
    assert to_python.check(task, source, fn, [])["agrees"]


@needs_sandbox
def test_strings_agree_through_the_boundary():
    task = parse(REVERSE)
    tests = ['assert rev("abc") == "cba"']
    source, fn = to_python.translate(task, tests, "rev")
    report = to_python.check(task, source, fn, tests)
    assert report["agrees"], report


# ---- 2026-10-05, the wider reader: a result the question's tests write as a tuple leaves as one ----

MODULO = """
t 1
gate loops
task tuple_modulo(a: seq, b: seq) returns (r: seq)
  requires len(a) == len(b)
  requires forall i in [0, len(b)) . b[i] != 0
  ensures len(r) == len(a)
{
  r := [];
  var i: int := 0;
  while i < len(a)
    invariant 0 <= i and i <= len(a)
    invariant len(r) == i
    decreases len(a) - i
  {
    r := r + [a[i] % b[i]];
    i := i + 1;
  }
}
"""

PAIRS = """
t 1
gate loops
task swap_rows(m: seq<seq>) returns (r: seq<seq>)
  ensures len(r) == len(m)
{
  r := [];
  var i: int := len(m);
  while i > 0
    invariant 0 <= i and i <= len(m)
    invariant len(r) == len(m) - i
    decreases i
  {
    i := i - 1;
    r := r + [m[i]];
  }
}
"""


def test_a_tuple_in_and_a_tuple_out():
    tests = ["assert tuple_modulo((10, 4, 5, 6), (5, 6, 7, 5)) == (0, 4, 5, 1)"]
    source, fn = to_python.translate(parse(MODULO), tests, "tuple_modulo")
    got = run(source, fn, (10, 4, 5, 6), (5, 6, 7, 5))
    assert got == (0, 4, 5, 1) and isinstance(got, tuple)
    assert run(source, fn, [10, 4], [5, 6]) == (0, 4)           # a list goes in as well


def test_a_list_of_tuples_keeps_each_writing_at_its_depth():
    tests = ["assert swap_rows([(1, 2), (3, 4)]) == [(3, 4), (1, 2)]"]
    source, fn = to_python.translate(parse(PAIRS), tests, "swap_rows")
    got = run(source, fn, [(1, 2), (3, 4)])
    assert got == [(3, 4), (1, 2)] and isinstance(got, list) and isinstance(got[0], tuple)
    tests = ["assert swap_rows(((1, 2), (3, 4))) == ((3, 4), (1, 2))"]
    source, fn = to_python.translate(parse(PAIRS), tests, "swap_rows")
    assert run(source, fn, ((1, 2), (3, 4))) == ((3, 4), (1, 2))


def test_without_a_tuple_in_the_tests_nothing_changes():
    tests = ["assert tuple_modulo([10, 4], [5, 6]) == [0, 4]"]
    source, fn = to_python.translate(parse(MODULO), tests, "tuple_modulo")
    assert "_t_shape" not in source and run(source, fn, [10, 4], [5, 6]) == [0, 4]


@needs_sandbox
def test_check_passes_the_questions_own_tuple_test():
    task = parse(MODULO)
    tests = ["assert tuple_modulo((10, 4, 5, 6), (5, 6, 7, 5)) == (0, 4, 5, 1)"]
    source, fn = to_python.translate(task, tests, "tuple_modulo")
    report = to_python.check(task, source, fn, tests)
    assert report["agrees"], report
