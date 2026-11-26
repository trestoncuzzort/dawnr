"""t/typed_values.py: a test value is kept as its Python literal, given one type across a problem's tests, read at the
type a task declares (and refused where that type cannot hold it as it is), drawn in its example's shape, sent into
the sandbox and back as literal text, and mutated into wrong answers of its own type."""
import ast
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import interp                                                   # noqa: E402
import mbpp_dfy                                                 # noqa: E402
import py_sandbox                                               # noqa: E402
import typed_values as tv                                       # noqa: E402

needs_sandbox = pytest.mark.skipif(not py_sandbox.available(), reason="no sandbox here")


def lit(text):
    return tv.literal(ast.parse(text, mode="eval").body)


@pytest.mark.parametrize("values, words", [
    (["[('English', 88), ('Science', 90)]", "[('Telugu', 49)]"], "seq<(seq, int)>"),
    (["(1, 'Rash', 21)", "(2, 'Varsha', 20)"], "(int, seq, int)"),
    (["(True, 3)"], "(bool, int)"),
    (["{1: 2, 3: 4}", "{}"], "map<int, int>"),
    (["{'a': [1, 2]}"], "map<seq, seq>"),
    (["{(1, 3): 2}"], "map<seq, int>"),
    (["[[['*']]]", "[[['*', '*']], [['*', '*']]]"], "seq<seq<seq>>"),
    (["[True, False]", "[]"], "seq<bool>"),
    (["{1, 2}", "{}"], "set"),
    (["{(4, 5), (3, 4)}"], "set<seq>"),
    (["{'y', 'x'}"], "set<seq>"),
    (["None", "'a'", "'bc'"], "Option"),
    (["(10, 4, None)", "(7, 8)"], "seq<Option>"),
    (["[19, 'red', 12]", "[1]"], "seq<Item>"),
    (["(1, 5, (4, 6), 10)", "(2, 9, (5, 7))"], "seq<Item>"),
    (["(1, 2)", "(3, 4, 5)"], "seq"),                           # a tuple of one kind is a sequence, as before
    (["['a', 'b']"], "seq"),                                    # one-character strings are a string's code points
])
def test_a_position_gets_one_type_across_the_tests(values, words):
    t = tv.type_of([lit(v) for v in values])
    assert tv.words(t) == words


def test_the_datatypes_a_question_needs_are_declared_by_name():
    t = tv.type_of([lit("None"), lit("3")])
    assert tv.declarations([t]) == {'{"option": "int"}': ("Option", "datatype Option = Nothing | Some(v: int)")}
    t = tv.type_of([lit("[19, 'red', True, [1]]")])
    assert list(tv.declarations([t]).values()) == [("Item", "datatype Item = Bool(b: bool) | Int(i: int) | Seq(xs: seq) | Str(s: seq)")]


@pytest.mark.parametrize("values, why", [
    (["None", "None"], "None and nothing else"),
    (["('x', 2)", "'none'"], "values of different kinds"),
    (["[1, [2, [3]]]"], "values of different kinds"),           # a datatype field cannot be a list of them
    (["None", "('a', 2)"], "an optional value of a compound type"),
])
def test_values_with_no_t_type_are_refused_by_name(values, why):
    with pytest.raises(tv.Unreadable, match=why):
        tv.type_of([lit(v) for v in values])


@pytest.mark.parametrize("text, why", [("1.5", "float"), ("f(1)", "call:f"), ("x", "Name"), ("b'x'", "bytes"), ("1j", "complex")])
def test_a_literal_is_read_and_a_float_a_call_or_a_name_is_named(text, why):
    with pytest.raises(tv.Unreadable, match=why):
        lit(text)
    assert lit("{1: (2, 'a'), 3: None}") == {1: (2, "a"), 3: None} and lit("set()") == set() and lit("-3") == -3


OPTION = {"Option": {"name": "Option", "ctors": [{"name": "Nothing"}, {"name": "Some", "fields": [{"name": "v", "type": "int"}]}]}}
ITEM = {"Item": {"name": "Item", "ctors": [{"name": "Int", "fields": [{"name": "i", "type": "int"}]},
                                           {"name": "Str", "fields": [{"name": "s", "type": "seq"}]},
                                           {"name": "Seq", "fields": [{"name": "xs", "type": "seq"}]}]}}
MARK = {"Mark": {"name": "Mark", "ctors": [{"name": "Mark", "fields": [{"name": "subject", "type": "seq"},
                                                                        {"name": "score", "type": "int"}]}]}}


def test_a_value_is_read_at_the_declared_type():
    assert tv.read_at(("ab", 3), {"pair": ["seq", "int"]}) == interp.Pair((97, 98), 3)
    assert tv.read_at((1, "a", True), {"tuple": ["int", "seq", "bool"]}) == interp.Tup((1, (97,), True))
    assert tv.read_at({2: "x", 1: "yz"}, {"map": ["int", "seq"]}) == interp.MapV.of([(1, (121, 122)), (2, (120,))])
    assert tv.read_at({3, 1}, "set") == frozenset({1, 3}) and tv.read_at({}, "set") == frozenset()
    assert tv.read_at([[["*"]]], {"seq": {"seq": "seq"}}) == (((42,),),)
    assert tv.read_at([True, False], {"seq": "bool"}) == (True, False)
    assert tv.read_at(None, {"datatype": "Option"}, OPTION) == interp.Ctor("Option", "Nothing", ())
    assert tv.read_at(5, {"datatype": "Option"}, OPTION) == interp.Ctor("Option", "Some", (5,))
    assert tv.read_at([1, "ab", [2]], {"seq": {"datatype": "Item"}}, ITEM) == (
        interp.Ctor("Item", "Int", (1,)), interp.Ctor("Item", "Str", ((97, 98),)), interp.Ctor("Item", "Seq", ((2,),)))
    assert tv.read_at(("Maths", 97), {"datatype": "Mark"}, MARK) == interp.Ctor("Mark", "Mark", ((77, 97, 116, 104, 115), 97))
    assert tv.read_at("a", "int") == 97                         # SPEC.md: a character is its code point


@pytest.mark.parametrize("value, ty, why", [
    (True, "int", "bool where an int"),                          # gate 1: a bool is not an int
    (1, "bool", "int where a bool"),
    ([1, 2], "set", "list where a set"),                         # order and repeats would be lost
    ({"a": 1, 97: 2}, {"map": ["int", "int"]}, "two keys of the dict are one key"),
    ({"a", 97}, "set", "two elements of the set are one value"),
    ((1, 2, 3), {"pair": ["int", "int"]}, "pair"),
    (None, "int", "NoneType where an int"),
    ("ab", {"seq": "seq"}, "str where a seq<...>"),
    (1.5, "int", "float"),
])
def test_a_value_the_declared_type_cannot_hold_as_it_is_is_refused(value, ty, why):
    with pytest.raises(tv.Unreadable, match=why):
        tv.read_at(value, ty)


def test_a_constructor_is_chosen_only_where_one_is_meant():
    two_seqs = {"T": {"name": "T", "ctors": [{"name": "A", "fields": [{"name": "a", "type": "seq"}]},
                                             {"name": "B", "fields": [{"name": "b", "type": "seq"}]}]}}
    with pytest.raises(tv.Unreadable, match="more than one constructor of T"):
        tv.read_at("ab", {"datatype": "T"}, two_seqs)           # a str and a list are both a seq: which one is not said
    with pytest.raises(tv.Unreadable, match="2 constructors without fields"):
        tv.read_at(None, {"datatype": "C"}, {"C": {"name": "C", "ctors": [{"name": "X"}, {"name": "Y"}]}})
    with pytest.raises(tv.Unreadable, match="no constructor of Item takes it"):
        tv.read_at(True, {"datatype": "Item"}, ITEM)


def test_the_reader_keeps_every_reading_it_had_and_types_only_what_it_refused():
    wide = dict(strings=True, nested_strings=True, tuples=True, nested_ints=True)
    for line in ("assert f([1, 2], 'ab') == 3", "assert f(((1, 2), (3, 4))) == [[1]]", "assert f('a') == True"):
        old = mbpp_dfy.parse_assertion(line, **wide)
        new = mbpp_dfy.parse_assertion(line, **wide, typed=True)
        assert new["args"] == old["args"] and new["expected"] == old["expected"] and new["ok"]
    points = [mbpp_dfy.parse_assertion(x, **wide, typed=True) for x in
              ("assert f('abcabc') == None", "assert f('abc') == 'a'", "assert f('ab') == 'c'")]
    assert points[0]["args"][0] == ("seq", [97, 98, 99, 97, 98, 99]) and points[0]["expected"] == (tv.PENDING, None)
    tv.settle(points)
    kind = tv.kind_of({"option": "seq"})
    assert [p["expected"] for p in points] == [(kind, None), (kind, "a"), (kind, "c")]
    assert points[1]["args"][0] == ("seq", [97, 98, 99])        # the argument read whole, as it was
    assert mbpp_dfy.parse_assertion("assert f(1.5) == 1", **wide, typed=True) == {"ok": False, "why": "arg:float"}


def test_a_drawn_value_keeps_its_examples_shape():
    rnd = random.Random(3)
    for _ in range(50):
        v = tv.draw({"seq": {"pair": ["seq", "int"]}}, [("English", 88), ("Maths", 97)], rnd)
        assert isinstance(v, list) and all(isinstance(p, tuple) and isinstance(p[0], str) and isinstance(p[1], int) for p in v)
        m = tv.draw({"map": ["int", "seq"]}, {1: "ab"}, rnd)
        assert isinstance(m, dict) and all(isinstance(k, int) and isinstance(x, str) for k, x in m.items())
        s = tv.draw({"set": "seq"}, {(4, 5), (3, 4)}, rnd)
        assert isinstance(s, set) and all(isinstance(x, tuple) for x in s)
        assert tv.draw({"option": "int"}, None, rnd) is None and isinstance(tv.draw({"option": "int"}, 4, rnd), int)
        mixed = tv.draw({"seq": {"sum": ["Int", "Str"]}}, [19, "red"], rnd)
        assert all(isinstance(x, (int, str)) and not isinstance(x, bool) for x in mixed)
        assert all(isinstance(x, bool) for x in tv.draw({"seq": "bool"}, [True, False], rnd))
    larger = [tv.draw({"seq": {"pair": ["seq", "int"]}}, [("a", 1)], rnd, larger=True) for _ in range(20)]
    assert min(len(v) for v in larger) > 3


@pytest.mark.parametrize("value", [
    interp.Pair((97,), 3), interp.Tup((1, (2,), True)), frozenset({1, 2}), interp.MapV.of([(1, 2), (3, 4)]),
    interp.Ctor("Option", "Some", (5,)), (interp.Pair(1, 2), interp.Pair(3, 4)),
])
def test_wrong_answers_are_near_the_right_one_and_of_its_type(value):
    wrong = tv.mutations(value, OPTION)
    assert wrong and value not in wrong
    assert all(type(w) is type(value) for w in wrong)
    if isinstance(value, interp.Ctor):
        assert interp.Ctor("Option", "Nothing", ()) in wrong and interp.Ctor("Option", "Some", (6,)) in wrong


@needs_sandbox
def test_values_cross_into_the_sandbox_and_back_as_literals():
    code = ("from collections import Counter\n"
            "def f(d, s, t, n):\n    return Counter(d), sorted(s), t[::-1], n, object\n"
            "def g(x):\n    return {'k': x}\n"
            "def h(x):\n    raise TypeError('mine')\n")
    with py_sandbox.Session(code + tv.wrapper("g"), tv.LITERAL_CALL) as s:
        assert tv.decode(s.call(tv.encode([(1, "a")]))) == {"k": (1, "a")}
    with py_sandbox.Session(code + tv.wrapper("f"), tv.LITERAL_CALL) as s:
        assert tv.decode(s.call(tv.encode([{1: 2}, {3}, (4, 5), None]))) is tv.NO_VALUE     # an object has no literal
    with py_sandbox.Session(code + tv.wrapper("h"), tv.LITERAL_CALL) as s:
        with pytest.raises(py_sandbox.CallError, match="TypeError"):                       # the function's own error
            s.call(tv.encode([1]))
