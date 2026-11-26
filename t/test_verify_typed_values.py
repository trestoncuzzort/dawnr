"""`dawnr verify` on functions whose tests hold values beyond ints, bools, strings and lists of them (2026-11-26):
a tuple mixing kinds, a dict, deeper nesting, None, a set, a list of bools, a list mixing kinds. Each is read at the
type the task declares (t/typed_values.py), the specification is held against the person's function on drawn
inputs of the same shapes, and where the comparison with the function cannot carry the type (t/to_python.py's
boundary, in the t engine) verify says so instead of claiming a difference. Until this change every one of these
was refused before the model was asked."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import py_sandbox                                               # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_gate                                                # noqa: E402
import surface                                                  # noqa: E402
import verify_py                                                # noqa: E402

needs_sandbox = pytest.mark.skipif(not py_sandbox.available(), reason="no sandbox for a person's Python here")

ALL = {k: "verified / refuted" for k in spec_check.KERNELS}


def student(*replies):
    queue = list(replies)
    asked = []

    def decode(conversations, temperature, salt, first, max_new):
        asked.append(conversations[0])
        return [(queue.pop(0) if queue else "no answer", True, 0)]
    decode.asked = asked
    return decode


def proving(tasks, jobs):
    return {task["name"]: ALL for task in tasks}


def fenced(text):
    return "```t\n" + text.strip("\n") + "\n```"


def ask(source, tests, spec, body=None, wrong=None):
    """The function read, its tests read, and the specification route asked once with `spec` (and `body`)."""
    f = verify_py.read_function(source)
    entry, _ = verify_py.entry_for(f, tests)
    right = verify_py.by_specification(entry, f, student(fenced(spec), fenced(body or spec)), specs=1, answers=1,
                                       prover=proving)
    refused = None
    if wrong:
        refused = verify_py.by_specification(entry, f, student(fenced(wrong)), specs=1, answers=1, prover=proving)
    right["held"] = spec_gate.judge(surface.parse(spec), entry, f["code"])    # what verify held the specification to
    return entry, right, refused


def held(r):
    """What holding the one specification against the function found."""
    return r["held"]


def abstained(r, words):
    assert r["shown"] is None, r["refused"]
    (line,) = r["refused"]
    assert line.startswith("specification 1, body 1: the comparison with your function cannot carry")
    assert words in line and "t/to_python.py" in line


def prompt_words(entry):
    return se.build_prompt(entry, "s2")[-1]["content"]


@needs_sandbox
def test_a_tuple_mixing_a_string_and_an_int_is_a_pair():
    entry, r, wrong = ask(
        "def second(p):\n    return p[1]\n",
        ["assert second(('ab', 3)) == 3", "assert second(('xyz', -1)) == -1"],
        "t 1\ntask second(p: (seq, int)) returns (r: int)\n  ensures r == p.1\n{\n}\n",
        "t 1\ntask second(p: (seq, int)) returns (r: int)\n  ensures r == p.1\n{\n  r := p.1;\n}\n",
        wrong="t 1\ntask second(p: (seq, int)) returns (r: int)\n  ensures r == len(p.0)\n{\n}\n")
    assert "of type(s) (seq, int)" in prompt_words(entry)
    h = held(r)
    assert h["passes"] and h["agreement"]["draws"] >= 10 and h["agreement"]["completeness"] >= 0.6
    abstained(r, "(seq, int)")
    assert wrong["refused"] == ["specification 1: `r == len(p.0)` is false at your function's own answer `second(('ab', 3)) == 3`"]


SQUARES_SPEC = """t 1
task square_map(n: int) returns (r: map<int, int>)
  requires n >= 0
  ensures len(r) == n
  ensures forall i in [0, n) . i in r and r[i] == i * i
{
}
"""
SQUARES_BODY = """t 1 gate loops
task square_map(n: int) returns (r: map<int, int>)
  requires n >= 0
  ensures len(r) == n
  ensures forall i in [0, n) . i in r and r[i] == i * i
{
  r := map[];
  var i: int := 0;
  while i < n
    invariant 0 <= i and i <= n
    invariant len(r) == i
    invariant forall j in [0, i) . j in r and r[j] == j * j
    decreases n - i
  {
    r := r[i := i * i];
    i := i + 1;
  }
}
"""


@needs_sandbox
def test_a_dict_is_a_map_and_crosses_into_the_sandbox_with_its_int_keys():
    entry, r, wrong = ask(
        "def square_map(n):\n    return {i: i * i for i in range(n)}\n",
        ["assert square_map(3) == {0: 0, 1: 1, 2: 4}", "assert square_map(0) == {}"],
        SQUARES_SPEC, SQUARES_BODY, wrong=SQUARES_SPEC.replace("r[i] == i * i", "r[i] == i + i"))
    assert "returning map<int, int>" in prompt_words(entry)
    h = held(r)
    assert h["passes"] and h["agreement"]["draws"] >= 10 and h["agreement"]["completeness"] >= 0.6
    abstained(r, "map<int, int>")
    assert wrong["refused"][0].startswith("specification 1: `len(r) == n; forall i in [0, n) . i in r and r[i] == i + i` is false at "
                                          "your function's own answer `square_map(3) == {0: 0, 1: 1, 2: 4}`")


@needs_sandbox
def test_a_dict_parameter_is_drawn_from_its_annotation_when_no_example_is_given():
    f = verify_py.read_function("def has_key(d: dict[str, int], k: str) -> bool:\n    return k in d\n")
    assert f["kinds"] == ["dict[str, int]", "str"]
    tests = verify_py.drawn_tests(f)
    assert tests[0] == "assert has_key({'ab': 2, '': 0}, 'ab') == True" and len(tests) == verify_py.EXAMPLES
    entry, drawn = verify_py.entry_for(f, [])
    assert drawn and "of type(s) map<seq, int>, seq" in prompt_words(entry)
    spec = "t 1\ntask has_key(d: map<seq, int>, k: seq) returns (r: bool)\n  ensures r == (k in d)\n{\n}\n"
    r = verify_py.by_specification(entry, f, student(fenced(spec), fenced(spec.replace("{\n}", "{\n  r := k in d;\n}"))),
                                   specs=1, answers=1, prover=proving)
    assert spec_gate.judge(surface.parse(spec), entry, f["code"])["passes"]
    abstained(r, "map<seq, int>")


@needs_sandbox
def test_three_levels_of_nesting_are_a_seq_of_seq_of_seq_and_the_twin_is_verified():
    spec = ("t 1\ntask cube(n: int) returns (r: seq<seq<seq>>)\n  requires n >= 0\n  ensures len(r) == n\n"
            "  ensures forall i in [0, n) . len(r[i]) == n and (forall j in [0, n) . len(r[i][j]) == n and "
            "(forall k in [0, n) . r[i][j][k] == 0))\n{\n}\n")
    entry, r, wrong = ask(
        "def cube(n):\n    return [[[0] * n for _ in range(n)] for _ in range(n)]\n",
        ["assert cube(1) == [[[0]]]", "assert cube(2) == [[[0, 0], [0, 0]], [[0, 0], [0, 0]]]"],
        spec, spec.replace("{\n}", "{\n  r := seq(n, seq(n, seq(n, 0)));\n}"),
        wrong=spec.replace("r[i][j][k] == 0", "r[i][j][k] == 1"))
    assert "returning seq<seq<seq>>" in prompt_words(entry)
    assert r["shown"] and r["shown"]["proved by"] == 7 and r["shown"]["same as yours on"] >= 10
    assert wrong["refused"][0].endswith("is false at your function's own answer `cube(1) == [[[0]]]`")


@needs_sandbox
def test_none_beside_a_value_is_an_option_the_task_declares():
    spec = ("datatype Option = Nothing | Some(v: int)\nt 1\ntask positive(n: int) returns (r: Option)\n"
            "  ensures n > 0 ==> r == Option.Some(n)\n  ensures n <= 0 ==> r == Option.Nothing\n{\n}\n")
    body = spec.replace("{\n}", "{\n  if n > 0 {\n    r := Option.Some(n);\n  } else {\n    r := Option.Nothing;\n  }\n}")
    entry, r, wrong = ask("def positive(n):\n    return n if n > 0 else None\n",
                          ["assert positive(3) == 3", "assert positive(-1) == None", "assert positive(0) == None"],
                          spec, body, wrong=spec.replace("Option.Some(n)", "Option.Some(n + 1)"))
    words = prompt_words(entry)
    assert "returning Option (declare before `t 1`: datatype Option = Nothing | Some(v: int))" in words
    h = held(r)
    assert h["passes"] and h["agreement"]["draws"] >= 10 and h["agreement"]["completeness"] >= 0.6
    abstained(r, "Option")
    assert wrong["refused"][0].endswith("is false at your function's own answer `positive(3) == 3`")


@needs_sandbox
def test_a_set_is_a_set_both_ways_and_the_twin_is_verified():
    spec = "t 1\ntask size(s: set) returns (r: int)\n  ensures r == card(s)\n{\n}\n"
    entry, r, _ = ask("def size(s):\n    return len(s)\n", ["assert size({1, 2, 3}) == 3", "assert size({5}) == 1"],
                      spec, spec.replace("{\n}", "{\n  r := card(s);\n}"))
    assert "of type(s) set," in prompt_words(entry) and r["shown"] and r["shown"]["proved by"] == 7
    spec = ("t 1\ntask evens(xs: seq) returns (r: set)\n  ensures forall i in [0, len(xs)) . (xs[i] in r) == (xs[i] % 2 == 0)\n"
            "  ensures forall x in r . x % 2 == 0 and x in toset(xs)\n{\n}\n")
    entry, r, wrong = ask("def evens(xs):\n    return {x for x in xs if x % 2 == 0}\n",
                          ["assert evens([1, 2, 4]) == {2, 4}", "assert evens([3, 6, 6]) == {6}", "assert evens([3]) == set()"],
                          spec, spec.replace("{\n}", "{\n  r := toset([x for x in xs if x % 2 == 0]);\n}"),
                          wrong=spec.replace("(xs[i] % 2 == 0)", "(xs[i] % 2 == 1)"))
    assert "returning set" in prompt_words(entry) and r["shown"] and r["shown"]["proved by"] == 7
    assert held(r)["agreement"]["completeness"] >= 0.6
    assert wrong["refused"][0].endswith("is false at your function's own answer `evens([1, 2, 4]) == {2, 4}`")


@needs_sandbox
def test_the_certificate_of_a_twin_over_a_set_replays_reading_its_tests_as_verify_read_them():
    import certificate
    spec = "t 1\ntask size(s: set) returns (r: int)\n  ensures r == card(s)\n{\n}\n"
    f = verify_py.read_function("def size(s):\n    return len(s)\n")
    entry, _ = verify_py.entry_for(f, ["assert size({1, 2, 3}) == 3", "assert size({5}) == 1"])
    r = verify_py.by_specification(entry, f, student(fenced(spec), fenced(spec.replace("{\n}", "{\n  r := card(s);\n}"))),
                                   specs=1, answers=1, prover=proving)
    made = certificate.from_verify(r, f)
    report = certificate.check(made, prover=proving)
    assert report["verdict"] == certificate.REPRODUCED, [s for s in report["steps"] if s["result"] != "ok"]
    assert {s["what"]: s["result"] for s in report["steps"]}["tests"] == "ok"


@needs_sandbox
def test_a_list_of_bools_is_a_seq_of_bools_and_the_twin_is_verified():
    spec = "t 1\ntask all_true(bs: seq<bool>) returns (r: bool)\n  ensures r == all(bs)\n{\n}\n"
    entry, r, wrong = ask("def all_true(bs):\n    return all(bs)\n",
                          ["assert all_true([True, True]) == True", "assert all_true([True, False]) == False"],
                          spec, spec.replace("{\n}", "{\n  r := all(bs);\n}"), wrong=spec.replace("all(bs)", "any(bs)"))
    assert "of type(s) seq<bool>" in prompt_words(entry)
    assert r["shown"] and r["shown"]["proved by"] == 7
    assert wrong["refused"][0].endswith("is false at your function's own answer `all_true([True, False]) == False`")


@needs_sandbox
def test_a_list_mixing_ints_and_strings_is_a_seq_of_a_datatype_with_one_constructor_a_kind():
    spec = ("datatype Item = Int(i: int) | Str(s: seq)\nt 1\ntask count_ints(xs: seq<Item>) returns (r: int)\n"
            "  ensures r == len([x for x in xs if case x { Int(i) => true, Str(s) => false }])\n{\n}\n")
    entry, r, wrong = ask("def count_ints(xs):\n    return sum(1 for x in xs if isinstance(x, int))\n",
                          # [1, 'a', 2] alone the reader reads as ints, the character being its code point: a longer
                          # string is what the reader refused
                          ["assert count_ints([1, 'ab', 2]) == 2", "assert count_ints(['b', 'cd']) == 0"],
                          spec, spec.replace("{\n}", "{\n  r := len([x for x in xs if case x { Int(i) => true, Str(s) => false }]);\n}"),
                          wrong=spec.replace("Int(i) => true, Str(s) => false", "Int(i) => false, Str(s) => true"))
    assert "of type(s) seq<Item>" in prompt_words(entry)
    assert "datatype Item = Int(i: int) | Str(s: seq)" in prompt_words(entry)
    assert held(r)["passes"] and held(r)["agreement"]["draws"] >= 10
    abstained(r, "seq<Item>")
    assert wrong["refused"][0].endswith("is false at your function's own answer `count_ints([1, 'ab', 2]) == 2`")


@needs_sandbox
@pytest.mark.parametrize("body, tests, why", [
    ("1", ["assert f((1.5, 2)) == 1"], "an argument is a number that is not whole"),
    ("None", ["assert f(1) == None", "assert f(2) == None"], "None and nothing else"),
    ("('xy', 2) if x == 1 else 'none'", ["assert f(1) == ('xy', 2)", "assert f(2) == 'none'"],
     "values of different kinds at one position"),
    ("1", ["assert f([1, [2, [3]]]) == 1"], "values of different kinds at one position"),
])
def test_what_t_still_has_no_type_for_is_refused_before_the_model_is_asked(body, tests, why):
    f = verify_py.read_function(f"def f(x):\n    return {body}\n")
    with pytest.raises(verify_py.Refused, match=why):
        verify_py.entry_for(f, tests)
