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


# ---- the proved domain: the Python refuses what the proof does not cover (2026-10-05) ----

HEAD = """
t 1
task head(s: seq, k: int) returns (r: int)
  requires 0 <= k and k < len(s)
  requires s[k] >= 0
  ensures r == s[k]
{
  r := s[k];
}
"""


def test_outside_the_requires_the_python_raises_and_names_the_clause():
    source, fn = to_python.translate(parse(HEAD), ["assert head([4, 5], 1) == 5"])
    assert run(source, fn, [4, 5], 1) == 5
    for s, k in (([4, 5], 2), ([4, 5], -1), ([], 0), ([4, -5], 1)):
        with pytest.raises(ValueError, match=r"head: this input is outside what was proved \(requires 0 <= k"):
            run(source, fn, s, k)
    assert "Outside its `requires` it raises ValueError" in source


def test_a_requires_with_no_value_at_an_input_admits_nothing_instead_of_reading_pythons_negative_index():
    # s[k] at k = -1 is the last element in Python and undefined in t; written first, it must not let the input in
    task = parse(HEAD.replace("  requires 0 <= k and k < len(s)\n  requires s[k] >= 0\n",
                              "  requires s[k] >= 0 and 0 <= k and k < len(s)\n"))
    source, fn = to_python.translate(task, [])
    with pytest.raises(ValueError):
        run(source, fn, [1, 2, 3], -1)
    with pytest.raises(ValueError):
        run(source, fn, [1, 2, 3], 7)


def test_an_argument_of_another_type_is_refused_before_anything_runs():
    source, fn = to_python.translate(parse(HEAD), ["assert head([4, 5], 1) == 5"])
    for s, k, word in (("45", 1, "`s` must be a list of integers"), ([4.0, 5.0], 1, "`s` must be a list of integers"),
                       ([4, 5], 1.0, "`k` must be an integer"), ([4, 5], True, "`k` must be an integer"),
                       ([[4], [5]], 1, "`s` must be a list of integers")):
        with pytest.raises(TypeError, match=word):
            run(source, fn, s, k)
    assert run(source, fn, (4, 5), 0) == 4                      # a tuple is a sequence here, as the tests may write one


def test_strings_sets_and_nested_lists_are_each_held_to_their_own_writing():
    source, fn = to_python.translate(parse(REVERSE), ['assert rev("abc") == "cba"'], "rev")
    assert run(source, fn, "abc") == "cba"
    with pytest.raises(TypeError, match="must be a string"):
        run(source, fn, [97, 98, 99])
    rows = parse("t 1\ntask count_rows(m: seq<seq>) returns (r: int)\n  ensures r == len(m)\n{\n  r := len(m);\n}\n")
    source, fn = to_python.translate(rows, ["assert count_rows([[1, 2], [3]]) == 2"])
    assert run(source, fn, [[1, 2], [3]]) == 2 and run(source, fn, []) == 0
    with pytest.raises(TypeError, match="`m` must be a list of lists of integers"):
        run(source, fn, [1, 2])


@needs_sandbox
def test_check_holds_the_guard_to_the_interpreter_on_inputs_the_requires_excludes():
    task = parse(HEAD)
    source, fn = to_python.translate(task, ["assert head([4, 5], 1) == 5"])
    report = to_python.check(task, source, fn, ["assert head([4, 5], 1) == 5"])
    assert report["agrees"] and report["refused"] >= 10, report
    # a hand-back that answers outside the proved domain is not shown
    unguarded = source.replace("    if not _t_requires(s, k):\n", "    if False:\n")
    assert unguarded != source
    report = to_python.check(task, unguarded, fn, ["assert head([4, 5], 1) == 5"])
    assert not report["agrees"], report
