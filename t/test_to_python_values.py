#!/usr/bin/env python3
"""t/to_python.py's boundary at the values t/typed_values.py reads (2026-11-26): a map, a tuple of three or more, a
datatype value (an option's None, one kind of a mixed list) and a string inside any of them.

Two things are held for each. The COMPARISON of the proved program with a person's function (`to_python.check`, which
`dawnr verify` asks before showing a twin) says a right function agrees and REFUTES a function that differs only inside
the new type: a map with one value changed, a 3-tuple with one component changed, None where the program has a value,
a string inside a tuple changed. A function that agrees on its own examples and differs elsewhere is the case that
matters, so every wrong function here passes the examples it is given, and the refutation names the input and the
answer the program gives there. And the Python HAND-BACK (`to_python.translate`) runs, answers the examples, and agrees
with the program on the inputs `check` draws. Before this change none of them could be written: the boundary left a
dict as the interpreter's `MapV`, a tuple of three as one of the interpreter's own, and a datatype value as its class."""
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


def compare(task_text: str, code: str, fn: str, tests: list[str]) -> dict:
    """What `dawnr verify` asks: the person's function `code` against the proved program, on the program's own inputs."""
    return to_python.check(parse(task_text), code, fn, tests, outside=0)


MAP = "t 1\ntask from_pair(a: int, b: int) returns (r: map<int, int>)\n  ensures true\n{\n  r := map[0 := a, 1 := b];\n}\n"
MAP_ARG = ("t 1\ntask lookup(d: map<int, int>, k: int) returns (r: int)\n  requires k in d\n  ensures true\n{\n"
           "  r := d[k];\n}\n")
TUPLE3 = ("t 1\ntask swap3(p: (int, bool, seq)) returns (r: (seq, bool, int))\n  ensures true\n{\n"
          "  r := (p.2, p.1, p.0);\n}\n")
OPTION = ("datatype Option = Nothing | Some(v: int)\nt 1\ntask positive(n: int) returns (r: Option)\n  ensures true\n{\n"
          "  if n > 0 {\n    r := Option.Some(n);\n  } else {\n    r := Option.Nothing;\n  }\n}\n")
STRING_IN_TUPLE = "t 1\ntask tag(s: seq) returns (r: (seq, int))\n  ensures true\n{\n  r := (s, len(s));\n}\n"
STRING_IN_MAP = "t 1\ntask named(n: int) returns (r: map<int, seq>)\n  ensures true\n{\n  r := map[n := \"ab\"];\n}\n"
STRINGS_IN_SET = "t 1\ntask both(a: seq, b: seq) returns (r: set<seq>)\n  ensures true\n{\n  r := {a, b};\n}\n"
MIXED = ("datatype Item = Int(i: int) | Str(s: seq)\nt 1\ntask count_ints(xs: seq<Item>) returns (r: int)\n  ensures true\n{\n"
         "  r := len([x for x in xs if case x { Int(i) => true, Str(s) => false }]);\n}\n")

# (the program, the function that is right, the examples, a function that passes the examples and differs only inside
# the new type, the assertion the refutation must name: the program's answer at the input the function gets wrong)
CASES = {
    "map": (MAP, "def from_pair(a, b):\n    return {0: a, 1: b}\n", "from_pair",
            ["assert from_pair(1, 2) == {0: 1, 1: 2}", "assert from_pair(0, 0) == {0: 0, 1: 0}"],
            "def from_pair(a, b):\n    return {0: a, 1: b + 1 if b > 2 else b}\n"),
    "map argument": (MAP_ARG, "def lookup(d, k):\n    return d[k]\n", "lookup",
                     ["assert lookup({1: 7}, 1) == 7", "assert lookup({0: 3}, 0) == 3"],
                     "def lookup(d, k):\n    return d[k] + (1 if len(d) > 1 and k > 0 else 0)\n"),
    "3-tuple": (TUPLE3, "def swap3(p):\n    return (p[2], p[1], p[0])\n", "swap3",
                ["assert swap3((1, True, 'ab')) == ('ab', True, 1)", "assert swap3((0, False, 'x')) == ('x', False, 0)"],
                "def swap3(p):\n    return (p[2], p[1], p[0] + 1 if p[0] > 1 else p[0])\n"),
    "3-tuple, a bool changed": (TUPLE3, "def swap3(p):\n    return (p[2], p[1], p[0])\n", "swap3",
                                ["assert swap3((1, True, 'ab')) == ('ab', True, 1)", "assert swap3((0, False, 'x')) == ('x', False, 0)"],
                                "def swap3(p):\n    return (p[2], p[1] if p[0] < 2 else not p[1], p[0])\n"),
    "3-tuple, a string changed": (TUPLE3, "def swap3(p):\n    return (p[2], p[1], p[0])\n", "swap3",
                                  ["assert swap3((1, True, 'ab')) == ('ab', True, 1)", "assert swap3((0, False, 'xy')) == ('xy', False, 0)"],
                                  "def swap3(p):\n    return (p[2] if len(p[2]) != 1 else p[2] + '?', p[1], p[0])\n"),
    "None": (OPTION, "def positive(n):\n    return n if n > 0 else None\n", "positive",
             ["assert positive(3) == 3", "assert positive(-1) == None", "assert positive(0) == None"],
             "def positive(n):\n    return n if n > 1 else None\n"),
    "string in a tuple": (STRING_IN_TUPLE, "def tag(s):\n    return (s, len(s))\n", "tag",
                          ["assert tag('ab') == ('ab', 2)", "assert tag('xyz') == ('xyz', 3)"],
                          "def tag(s):\n    return (s + '!' if len(s) == 1 else s, len(s))\n"),
    "string in a map": (STRING_IN_MAP, "def named(n):\n    return {n: 'ab'}\n", "named",
                        ["assert named(1) == {1: 'ab'}", "assert named(2) == {2: 'ab'}"],
                        "def named(n):\n    return {n: 'ab' if n < 3 else 'ac'}\n"),
    "strings in a set": (STRINGS_IN_SET, "def both(a, b):\n    return {a, b}\n", "both",
                         ["assert both('ab', 'cd') == {'ab', 'cd'}", "assert both('ab', 'ab') == {'ab'}"],
                         "def both(a, b):\n    return {a, b} if a <= b else {a, b + 'x'}\n"),
    "a mixed list": (MIXED, "def count_ints(xs):\n    return sum(1 for x in xs if isinstance(x, int))\n", "count_ints",
                     ["assert count_ints([1, 'ab', 2]) == 2", "assert count_ints(['b', 'cd']) == 0"],
                     "def count_ints(xs):\n    return sum(1 for x in xs if isinstance(x, int) and x != 0)\n"),
}


@needs_sandbox
@pytest.mark.parametrize("name", list(CASES))
def test_a_right_function_compares_equal(name):
    task, right, fn, tests, _wrong = CASES[name]
    r = compare(task, right, fn, tests)
    assert r["agrees"] and r["inputs"] >= len(tests) + 5, r


@needs_sandbox
@pytest.mark.parametrize("name", list(CASES))
def test_a_function_that_differs_only_inside_the_new_type_is_refuted(name):
    task, right, fn, tests, wrong = CASES[name]
    # it passes the examples it is given, so the comparison has to find the input where it differs
    for line in tests:
        assert py_sandbox.run_tests(wrong, [line])["all_pass"], line
    r = compare(task, wrong, fn, tests)
    assert not r["agrees"] and not r.get("abstained"), r
    assert r["first"].startswith(f"assert {fn}(*") and r["first"] not in tests, r      # an input the examples do not hold


@needs_sandbox
@pytest.mark.parametrize("name", list(CASES))
def test_the_refutation_names_an_input_where_the_programs_answer_is_the_right_functions_and_not_the_wrong_ones(name):
    task, right, fn, tests, wrong = CASES[name]
    line = compare(task, wrong, fn, tests)["first"]
    assert line.startswith(f"assert {fn}(*[")                  # the input and the answer, written as the tests write values
    assert py_sandbox.run_tests(right, [line])["all_pass"], line
    assert not py_sandbox.run_tests(wrong, [line])["all_pass"], line


@needs_sandbox
def test_a_result_written_as_a_list_in_one_example_and_a_tuple_in_another_is_refused_by_name():
    # the program's answer cannot be written both ways, so nothing is compared (and nothing is claimed)
    r = compare(TUPLE3, "def swap3(p):\n    return (p[2], p[1], p[0])\n", "swap3",
                ["assert swap3((1, True, 'ab')) == ('ab', True, 1)", "assert swap3((4, False, 'c')) == ['c', False, 4]"])
    assert r["agrees"] is False and r["abstained"] and "list in one test and as a tuple in another" in r["why"], r


@needs_sandbox
def test_a_tuple_of_ints_the_tests_write_as_a_tuple_is_written_as_a_tuple_where_the_task_declares_one():
    # the older reader reads (1, 2, 3) as a sequence, so no test here is typed; the declared type decides the boundary
    task = "t 1\ntask rot3(p: (int, int, int)) returns (r: (int, int, int))\n  ensures true\n{\n  r := (p.1, p.2, p.0);\n}\n"
    tests = ["assert rot3((1, 2, 3)) == (2, 3, 1)", "assert rot3((0, 0, 0)) == (0, 0, 0)"]
    assert compare(task, "def rot3(p):\n    return (p[1], p[2], p[0])\n", "rot3", tests)["agrees"]
    r = compare(task, "def rot3(p):\n    return (p[1], p[2], p[0] + p[0] // 2)\n", "rot3", tests)
    assert not r["agrees"] and r["first"].startswith("assert rot3(*[("), r


def test_a_dict_inside_a_set_or_as_a_key_is_refused_by_name():
    with pytest.raises(to_python.Uncarried, match="dict inside a set"):
        to_python._form({"set": {"map": ["int", "int"]}}, [], {}, True)
    with pytest.raises(to_python.Uncarried, match="dict inside a set or as a key"):
        to_python._form({"map": [{"map": ["int", "int"]}, "int"]}, [], {}, True)


def test_a_datatype_whose_constructors_have_no_python_value_is_refused_by_name():
    dts = {"Colour": {"name": "Colour", "ctors": [{"name": "Red"}, {"name": "Blue"}]}}
    with pytest.raises(to_python.Uncarried, match="constructors have no Python value"):
        to_python._form({"datatype": "Colour"}, [], dts, True)


@pytest.mark.parametrize("name", list(CASES))
def test_the_python_hand_back_runs_and_answers_the_examples(name):
    task_text, _right, fn, tests, _wrong = CASES[name]
    task = parse(task_text)
    source, py_name = to_python.translate(task, tests, fn)
    assert py_name == fn
    scope: dict = {}
    exec(source, scope)                                         # noqa: S102 -- the translator's own output, in a test
    for line in tests:
        exec(line, scope)                                       # noqa: S102 -- the example, run against the hand-back
    assert "_t_in(" in source or "_t_out(" in source                  # a typed position is crossed by the shared code


@needs_sandbox
@pytest.mark.parametrize("name", list(CASES))
def test_the_python_hand_back_agrees_with_the_program_on_the_inputs_check_draws(name):
    task_text, _right, fn, tests, _wrong = CASES[name]
    task = parse(task_text)
    source, py_name = to_python.translate(task, tests, fn)
    report = to_python.check(task, source, py_name, tests)
    assert report["agrees"] and report["inputs"] >= len(tests) + 5, report


def test_the_hand_back_refuses_an_argument_that_is_not_of_the_declared_type_and_says_what_was_declared():
    task_text, _right, fn, tests, _wrong = CASES["map argument"]
    source, _ = to_python.translate(parse(task_text), tests, fn)
    scope: dict = {}
    exec(source, scope)                                         # noqa: S102
    with pytest.raises(TypeError, match=r"`d` must be map<int, int>; nothing was proved for anything else"):
        scope["lookup"]([1, 2], 1)
    with pytest.raises(ValueError, match="outside what was proved"):
        scope["lookup"]({1: 2}, 5)


def test_a_value_the_boundary_writes_is_the_python_value_the_reader_read_it_from():
    import typed_values
    dts = typed_values.datatypes_of(parse(OPTION)) | typed_values.datatypes_of(parse(MIXED))
    cases = [({"map": ["int", "seq"]}, {1: "ab", 2: ""}), ({"tuple": ["int", "bool", "seq"]}, (3, True, "xy")),
             ({"pair": ["seq", "int"]}, ("ab", 3)), ({"datatype": "Option"}, None), ({"datatype": "Option"}, 4),
             ({"seq": {"datatype": "Item"}}, [1, "ab", 2]), ({"set": "seq"}, {"ab", "cd"}),
             ({"seq": {"seq": "seq"}}, [["ab", "c"], []]), ({"map": ["seq", {"seq": "int"}]}, {"ab": [1, 2]})]
    for ty, value in cases:
        form = to_python._form(ty, [value], dts, True)
        read = typed_values.read_at(value, ty, dts)
        back = to_python._t_out(to_python._native(read), form)
        assert back == value and type(back) is type(value), (ty, value, back)
        assert to_python._t_in(back, form) == to_python._native(read), (ty, value)
