"""The wider reader of 2026-10-05 (t/mbpp_dfy.py `tuples`, `nested_ints`): a tuple is read as the list of the same
elements and a list of int lists as t's seq<seq>. No value t lacked is added, and no pool to v5 moves: the options
default off and the pools are read without them (t/PREDICT-2026-10-05-wider-reader.md)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import answer                                                   # noqa: E402
import mbpp_dfy                                                 # noqa: E402

POOL = dict(strings=True, nested_strings=True)
WIDE = dict(POOL, tuples=True, nested_ints=True)


def read(line, **options):
    return mbpp_dfy.parse_assertion(line, **options)


def test_a_tuple_reads_as_the_list_of_its_elements():
    p = read("assert tuple_modulo((10, 4, 5, 6), (5, 6, 7, 5)) == (0, 4, 5, 1)", **WIDE)
    assert p["args"] == [("seq", [10, 4, 5, 6]), ("seq", [5, 6, 7, 5])] and p["expected"] == ("seq", [0, 4, 5, 1])
    assert read("assert f((1, 2)) == 3", **WIDE)["args"] == read("assert f([1, 2]) == 3", **WIDE)["args"]
    assert read("assert f(()) == []", **WIDE)["args"] == [("seq", [])]


def test_rows_of_ints_read_as_a_nested_sequence_whatever_brackets_write_them():
    rows = ("seq-of-seq", [[5, 6, 7], [1, 3, 5]])
    for arg in ("[[5, 6, 7], [1, 3, 5]]", "[(5, 6, 7), (1, 3, 5)]", "((5, 6, 7), (1, 3, 5))", "([5, 6, 7], [1, 3, 5])"):
        assert read(f"assert f({arg}) == 1", **WIDE)["args"] == [rows], arg
    assert read("assert f([[], [1]]) == [[]]", **WIDE)["expected"] == ("seq-of-seq", [[]])
    assert read("assert f([['x', 'y'], ['a', 'b']]) == 1", **WIDE)["args"] == [("seq-of-seq", [[120, 121], [97, 98]])]


def test_strings_in_a_tuple_read_as_strings_in_a_list_do():
    assert (read("assert f(('ab', 'c')) == 1", **WIDE)["args"] == read("assert f(['ab', 'c']) == 1", **WIDE)["args"]
            == [("seq-of-seq", [[97, 98], [99]])])


@pytest.mark.parametrize("line, why", [
    ("assert f(('fox', 16, 19)) == 1", "arg:seq-of-seq"),       # a string and two ints: one sequence cannot hold both
    ("assert f([[1, 2], 3]) == 1", "arg:seq-of-seq"),           # a row and an int
    ("assert f([[[1]]]) == 1", "arg:seq-of-seq"),               # three deep: t has seq and seq<seq>
    ("assert f((1.5, 2)) == 1", "arg:float"),
    ("assert f({'a': 1}) == 1", "arg:dict"),
    ("assert f(1) == None", "expected:NoneType"),
])
def test_what_t_has_no_value_for_is_still_refused_by_name(line, why):
    assert read(line, **WIDE) == {"ok": False, "why": why}


@pytest.mark.parametrize("line", [
    "assert f((1, 2)) == 3", "assert f([1]) == (1, 2)", "assert f([[1, 2], [3]]) == 1", "assert f([(1, 2)]) == 1",
])
def test_the_pools_reading_is_unchanged(line):
    assert read(line, **POOL)["ok"] is False                    # every pool to v5 refuses these, as before
    assert read(line, **WIDE)["ok"] is True


def test_each_option_is_its_own():
    assert read("assert f((1, 2)) == 3", **POOL, tuples=True)["ok"]
    assert not read("assert f([(1, 2)]) == 3", **POOL, tuples=True)["ok"]           # rows need nested_ints
    assert read("assert f([[1, 2]]) == 3", **POOL, nested_ints=True)["ok"]
    assert not read("assert f([(1, 2)]) == 3", **POOL, nested_ints=True)["ok"]      # a tuple row needs tuples


def test_a_person_may_ask_with_tuples_and_is_told_plainly_what_cannot_be_read():
    entry = answer.entry_of("Modulo of tuple elements.", ["assert tuple_modulo((10, 4), (5, 6)) == (0, 4)"])
    assert entry["fn"] == "tuple_modulo" and entry["points"][0]["expected"] == ("seq", [0, 4])
    with pytest.raises(ValueError, match="a number that is not whole"):
        answer.entry_of("Area.", ["assert area(2) == 12.56"])
    with pytest.raises(ValueError, match="a dictionary"):
        answer.entry_of("Count.", ["assert count({'a': 1}) == 1"])
    with pytest.raises(ValueError, match="mixes kinds of element"):
        answer.entry_of("Find.", ["assert find(('fox', 16)) == 1"])
