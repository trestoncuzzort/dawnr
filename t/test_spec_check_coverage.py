"""The specification check's repair of 2026-10-01 (t/PREDICT-2026-10-01-spec-check-coverage.md):
a list of strings reaches the reference as strings, and one unusable draw no longer ends a check."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import spec_check                                               # noqa: E402
import surface                                                  # noqa: E402

FIND = """t 1
gate quantifiers
task find_substring(words: seq<seq>, sub: seq) returns (r: bool)
  ensures r == (exists i in [0, len(words)) . words[i].find(sub) != -1)
{
  r := false;
  var i: int := 0;
  while i < len(words)
    invariant 0 <= i
    invariant i <= len(words)
    invariant r == (exists j in [0, i) . words[j].find(sub) != -1)
    decreases len(words) - i
  {
    if words[i].find(sub) != -1 {
      r := true;
    } else {
    }
    i := i + 1;
  }
}
"""


def _codes(text):
    return [ord(c) for c in text]


def _entry(code, assertion, fn, args, expected):
    return {"rec": {"code": code, "test_list": [assertion], "text": ""}, "fn": fn,
            "points": [{"ok": True, "fn": fn, "args": args, "expected": expected}]}


FIND_ENTRY = _entry("def find_substring(str1, sub_str):\n    return any(sub_str in s for s in str1)\n",
                    'assert find_substring(["red", "black", "white"], "ack") == True', "find_substring",
                    [["seq-of-seq", [_codes("red"), _codes("black"), _codes("white")]], ["seq", _codes("ack")]],
                    ["bool", True])


def _int_task(name, requires, ensures, body):
    return surface.parse(f"t 1\ntask {name}(n: int) returns (r: int)\n{requires}  ensures {ensures}\n{{\n  {body}\n}}\n")


def test_a_list_of_strings_position_is_found_and_a_plain_string_is_not_one():
    assert spec_check.nested_string_positions(FIND_ENTRY) == [0]
    assert spec_check.string_positions(FIND_ENTRY) == [1]


def test_the_reference_gets_strings_for_a_list_of_strings():
    args = [[_codes("red"), _codes("black")], _codes("ack")]
    assert spec_check.python_arguments(args, [1], [0]) == [["red", "black"], "ack"]
    # a list of one-character strings is a flat seq in t and a list of characters to the reference
    assert spec_check.python_arguments([[97, 98]], [], [0]) == [["a", "b"]]
    # without the nested positions the call is what it was before the repair
    assert spec_check.python_arguments(args, [1]) == [[_codes("red"), _codes("black")], "ack"]


def test_a_specification_over_a_list_of_strings_is_checked_against_the_real_function():
    out = spec_check.check_task(surface.parse(FIND), FIND_ENTRY, 100, random.Random(1))
    assert out["status"] == "agrees" and out["draws"] > 50, out


def test_the_same_specification_read_disagrees_when_the_rows_go_over_as_integers(monkeypatch):
    monkeypatch.setattr(spec_check, "nested_string_positions", lambda entry: [])
    out = spec_check.check_task(surface.parse(FIND), FIND_ENTRY, 100, random.Random(1))
    assert out["status"] == "disagrees"                         # the fault this repair closes


def test_draws_for_a_list_of_strings_are_shaped_like_the_example():
    like = [_codes("red"), _codes("black")]
    rows = spec_check.draw("seq-of-seq", random.Random(3), like, strings=True)
    lo, hi = min(map(min, like)) - 2, max(map(max, like)) + 2
    assert all(lo <= c <= hi for row in rows for c in row) and len(rows) <= len(like) + 2
    assert all(len(row) <= 5 + 2 for row in rows)


def test_every_other_nested_draw_is_what_it_was():
    r1, r2 = random.Random(7), random.Random(7)
    old = [[r2.randint(-4, 4) for _ in range(r2.randint(0, 3))] for _ in range(r2.randint(0, 3))]
    assert spec_check.draw("seq-of-seq", r1, [[1, 2], [3]]) == old


def test_a_float_equal_to_an_integer_is_that_integer():
    assert spec_check.to_t(3.0) == 3 and spec_check.to_t([2.0, 4.0]) == (2, 4)
    for bad in (2.5, float("nan"), float("inf")):
        try:
            spec_check.to_t(bad)
        except TypeError:
            continue
        raise AssertionError(f"{bad!r} has no t value")


def test_a_reference_that_returns_whole_floats_is_checked():
    entry = _entry("def half(n):\n    return (n + 1) / 2 if n % 2 else n / 2\n", "assert half(5) == 3", "half",
                   [["int", 5]], ["int", 3])
    task = _int_task("half", "  requires n >= 0\n", "r == (n + 1) / 2", "r := (n + 1) / 2;")
    out = spec_check.check_task(task, entry, 100, random.Random(1))
    assert out["status"] == "agrees" and "skipped" not in out, out


def test_a_draw_whose_result_has_no_t_value_is_skipped_and_counted():
    entry = _entry("def keep(n):\n    return None if n < 3 else n\n", "assert keep(5) == 5", "keep",
                   [["int", 5]], ["int", 5])
    task = _int_task("keep", "", "r == n", "r := n;")
    out = spec_check.check_task(task, entry, 100, random.Random(1))
    assert out["status"] == "agrees", out
    assert out["skipped"]["reference result has no t value"] > 0
    assert out["draws"] + out["skipped"]["reference result has no t value"] == 100


def test_a_wrong_specification_still_disagrees_when_some_draws_are_skipped():
    entry = _entry("def keep(n):\n    return None if n < 3 else n\n", "assert keep(5) == 5", "keep",
                   [["int", 5]], ["int", 5])
    task = _int_task("keep", "", "r == n + 1", "r := n + 1;")
    assert spec_check.check_task(task, entry, 100, random.Random(1))["status"] == "disagrees"


def test_a_reference_with_no_usable_result_keeps_its_old_status():
    entry = _entry("def nothing(n):\n    return None\n", "assert nothing(5) == 5", "nothing",
                   [["int", 5]], ["int", 5])
    out = spec_check.check_task(_int_task("nothing", "", "r == n", "r := n;"), entry, 20, random.Random(1))
    assert out["status"] == "reference result has no t value" and out["draws"] == 0


def test_draws_the_reference_does_not_finish_are_skipped_and_the_check_stops_early(monkeypatch):
    real = spec_check.deadline
    monkeypatch.setattr(spec_check, "deadline", lambda seconds, exc=spec_check.Timeout: real(0.05, exc))
    entry = _entry("def slow(n):\n    while n > 4:\n        pass\n    return n\n", "assert slow(3) == 3", "slow",
                   [["int", 3]], ["int", 3])
    out = spec_check.check_task(_int_task("slow", "", "r == n", "r := n;"), entry, 100, random.Random(1))
    assert out["status"] == "agrees", out
    assert out["skipped"]["reference did not finish"] == spec_check.MAX_REFERENCE_TIMEOUTS
    assert out["draws"] < 100                                   # it stopped drawing


def test_a_reference_that_never_finishes_keeps_its_old_status(monkeypatch):
    real = spec_check.deadline
    monkeypatch.setattr(spec_check, "deadline", lambda seconds, exc=spec_check.Timeout: real(0.05, exc))
    entry = _entry("def never(n):\n    while True:\n        pass\n", "assert never(3) == 3", "never",
                   [["int", 3]], ["int", 3])
    out = spec_check.check_task(_int_task("never", "", "r == n", "r := n;"), entry, 100, random.Random(1))
    assert out["status"] == "reference did not finish" and out["draws"] == 0
