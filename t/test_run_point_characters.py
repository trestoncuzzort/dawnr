"""A one-character string in a test is read at the type the task declares (2026-10-01;
arXiv:2208.08227 III-C.2). Before this a string parameter or result failed on such a test."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mbpp_dfy                                                 # noqa: E402
import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402

IDENT = "t 1\ntask f(s: %s) returns (r: %s)\n  ensures r == s\n{\n  r := s;\n}\n"


def _entry(*asserts):
    pts = [mbpp_dfy.parse_assertion(a, strings=True, nested_strings=True) for a in asserts]
    assert all(p["ok"] for p in pts)
    return se.mark_characters({"rec": {"test_list": list(asserts)}, "points": pts, "fn": "f"})


def test_the_marks_name_the_one_character_strings_and_nothing_else():
    e = _entry('assert f("a") == "a"', 'assert f("ab") == "ab"', "assert f(7) == 7")
    assert e["points"][0]["char_args"] == [0] and e["points"][0]["char_expected"] is True
    assert "char_args" not in e["points"][1] and "char_expected" not in e["points"][1]
    assert "char_args" not in e["points"][2] and "char_expected" not in e["points"][2]
    assert e["points"][0]["args"] == [("int", 97)] or e["points"][0]["args"] == [["int", 97]]   # the kind is untouched


def test_a_string_task_passes_a_test_whose_string_is_one_character():
    e = _entry('assert f("a") == "a"', 'assert f("ab") == "ab"')
    task = surface.parse(IDENT % ("seq", "seq"))
    assert [se.run_point(task, p)["verdict"] for p in e["points"]] == ["pass", "pass"]


def test_a_character_task_still_passes_the_character_test_and_fails_the_string_one():
    e = _entry('assert f("a") == "a"', 'assert f("ab") == "ab"')
    task = surface.parse(IDENT % ("int", "int"))
    assert [se.run_point(task, p)["verdict"] for p in e["points"]] == ["pass", "type"]


def test_an_integer_is_never_read_as_a_string():
    e = _entry("assert f(7) == 7")
    task = surface.parse(IDENT % ("seq", "seq"))
    assert se.run_point(task, e["points"][0])["verdict"] == "type"


def test_a_point_without_marks_is_read_as_before():
    task = surface.parse(IDENT % ("seq", "seq"))
    point = {"ok": True, "fn": "f", "args": [["int", 97]], "expected": ["int", 97]}
    assert se.run_point(task, point)["verdict"] == "type"


def test_the_pool_carries_the_marks():
    e = se.pool("v5")[113]                                      # check_integer("python"), ("1"), ("12345")
    assert any(p.get("char_args") == [0] for p in e["points"])
