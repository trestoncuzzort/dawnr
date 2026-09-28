"""test_lift_char_cast.py: LIFTER-DECISIONS row 55 (2026-09-28): an `as char`
cast lifts when the lifter can see its operand's interval lies in the char
range, read from requires clauses, loop invariants and single initialisers
(`_cast_bounds_env`, `_cast_interval`, `_char_cast_safe`). Pure parse and
classify, no prover."""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lift_classify as C                                      # noqa: E402
import lift_parse                                              # noqa: E402


def _classify_one(src: str, method_name: str):
    mod = lift_parse.parse(src)
    methods = {m.name: m for m in lift_parse.gradable_methods(mod)}
    return C.classify(mod, methods[method_name])


def _lifts(src: str, name: str) -> None:
    v = _classify_one(src, name)
    assert isinstance(v, C.Liftable), (name, v)
    assert any(r.rule == "int-as-char-bounded" for r in v.rewrites), [r.rule for r in v.rewrites]


def _refuses(src: str, name: str) -> None:
    v = _classify_one(src, name)
    assert not isinstance(v, C.Liftable) and v.reason == "char-cast-unbounded", (name, v)


DIGIT_REQUIRES = """
method DigitChar(d: int) returns (c: char)
  requires 0 <= d < 10
  ensures c == ('0' as int + d) as char
{
  c := ('0' as int + d) as char;
}
"""

DIGIT_MODULO = """
method LastDigit(n: int) returns (c: char)
  requires n >= 0
  ensures true
{
  var d := n % 10;
  c := ('0' as int + d) as char;
}
"""

SHIFT_LETTERS = """
function Shift(c: char): char
  requires 'a' <= c <= 'z'
{
  ((c as int - 'a' as int + 5) % 26 + 'a' as int) as char
}
method Encode(s: seq<char>) returns (r: seq<char>)
  requires forall i :: 0 <= i < |s| ==> 'a' <= s[i] <= 'z'
  ensures |r| == |s|
{
  r := [];
  var i := 0;
  while i < |s|
    invariant 0 <= i <= |s|
    invariant |r| == i
    decreases |s| - i
  {
    r := r + [Shift(s[i])];
    i := i + 1;
  }
}
"""

INVARIANT_BOUND = """
method Digits(n: int) returns (r: seq<char>)
  requires 0 <= n < 10
  ensures true
{
  r := [];
  var k := 0;
  while k < n
    invariant 0 <= k <= 9
    decreases n - k
  {
    r := r + [('0' as int + k) as char];
    k := k + 1;
  }
}
"""

UNBOUNDED = """
method Any(x: int) returns (c: char)
  ensures true
{
  c := x as char;
}
"""

TOO_WIDE = """
method Wide(x: int) returns (c: char)
  requires 0 <= x < 70000
  ensures true
{
  c := x as char;
}
"""

REASSIGNED = """
method Twice(n: int) returns (c: char)
  requires n >= 0
  ensures true
{
  var d := n % 10;
  d := n;
  c := ('0' as int + d) as char;
}
"""

GUARD_ONLY = """
function Up(c: char): char
{
  if c as int + 32 < 65536 then (c as int + 32) as char else c
}
method M(c: char) returns (r: char)
  ensures true
{
  r := Up(c);
}
"""


def test_a_requires_bound_on_the_digit_lifts() -> None:
    _lifts(DIGIT_REQUIRES, "DigitChar")


def test_a_modulo_initialiser_lifts() -> None:
    _lifts(DIGIT_MODULO, "LastDigit")


def test_a_char_range_through_modulo_and_offset_lifts() -> None:
    _lifts(SHIFT_LETTERS, "Encode")


def test_a_loop_invariant_bound_lifts() -> None:
    _lifts(INVARIANT_BOUND, "Digits")


def test_no_bound_still_refuses() -> None:
    _refuses(UNBOUNDED, "Any")


def test_a_bound_past_the_surrogate_gap_still_refuses() -> None:
    _refuses(TOO_WIDE, "Wide")


def test_a_reassigned_local_loses_its_initialiser() -> None:
    _refuses(REASSIGNED, "Twice")


def test_an_if_guard_alone_is_not_a_bound() -> None:
    _refuses(GUARD_ONLY, "M")


def test_intervals() -> None:
    env = {"d": [0, 9], "c": [97, 122]}
    src = "method X(d: int, c: char) returns (r: int) ensures true { r := 0; }"
    assert C._cast_interval(lift_parse.parse("function F(): int { 1 + 2 }").decls[0].body, {}, set()) == (3, 3)
    m = lift_parse.parse("function G(d: int): int { (48 + d) * 2 - 1 }").decls[0]
    assert C._cast_interval(m.body, env, set()) == (95, 113)
    m = lift_parse.parse("function H(n: int): int { n % 26 + 97 }").decls[0]
    assert C._cast_interval(m.body, env, set()) == (97, 122)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
