#!/usr/bin/env python3
"""test_lift_source_axiom.py: LIFTER-DECISIONS row 51 (2026-09-27,
t/LIFT-2026-09-26.md's DT0258 finding) -- a source-level reading of
`{:axiom}`, `{:verify false}` and `assume` (Dafny Reference Manual sections
11.2.4, 11.2.22, 8.18), refusing `source-axiom` when the method's spec,
body, invariants or closure references a declaration that is axiomatised
(carries `{:axiom}`/`{:verify false}`) or a function whose only stated
properties are axiom lemmas -- vericoding's DT0258 `NumpyBitwiseOr`
(t/out/lifted-tasks-2026-09-26.meta/staged/vericoding_DT0258.dfy): its
`BitwiseOr` is a placeholder returning 0, and its properties are
`lemma {:axiom}` statements false for that body (`BitwiseOr(x, 0) == x`
holds only when x == 0) -- and refusing `source-assume` when an `assume`
statement lies in the method's own body or in a lemma it calls (dropped as
a hint, decision 8, but never inspected for what it itself assumes until
now: `LemmaDecl.parts` is not a dataclass field, so `walk()` never
descended into a called lemma's proof). An axiom lemma the method's
closure never touches still lifts, noted `axiom-in-file`, not refused.

Run: python3 t/test_lift_source_axiom.py   (or pytest)
"""
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


def _refuses(src: str, method_name: str, reason: str, token: str | None = None) -> None:
    v = _classify_one(src, method_name)
    assert not isinstance(v, C.Liftable) and v.reason == reason, (method_name, v)
    if token is not None:
        assert v.token == token, (method_name, v)


# The DT0258 shape itself: a placeholder function whose only stated
# properties are `{:axiom}` lemmas, called directly from the method's spec
# and body (the loop also calls the axiom lemmas, as the vericoding source
# does -- both routes into `source-axiom` are exercised at once).
NUMPY_BITWISE_OR = """
function BitwiseOr(x: int, y: int): int
{
  0
}

lemma {:axiom} BitwiseOrCommutative(x: int, y: int)
  ensures BitwiseOr(x, y) == BitwiseOr(y, x)

lemma {:axiom} BitwiseOrIdentity(x: int)
  ensures BitwiseOr(x, 0) == x

method NumpyBitwiseOr(x1: seq<int>, x2: seq<int>) returns (result: seq<int>)
  requires |x1| == |x2|
  ensures |result| == |x1|
  ensures forall i :: 0 <= i < |result| ==> result[i] == BitwiseOr(x1[i], x2[i])
{
  result := [];
  var i := 0;
  while i < |x1|
    invariant 0 <= i <= |x1|
    invariant |result| == i
  {
    BitwiseOrCommutative(x1[i], x2[i]);
    BitwiseOrIdentity(x1[i]);
    result := result + [BitwiseOr(x1[i], x2[i])];
    i := i + 1;
  }
}
"""

# A function referenced only through its ensures, with no lemma of it
# CALLED from the method body -- exercises the axiom-only-function route
# (`_axiom_only_functions`) on its own, without a lemma call to also flag
# the closure directly.
AXIOM_ONLY_FUNCTION = """
function BitwiseOr(x: int, y: int): int
{
  0
}

lemma {:axiom} BitwiseOrIdentity(x: int)
  ensures BitwiseOr(x, 0) == x

method UseBitwiseOr(x: int) returns (r: int)
  ensures r == BitwiseOr(x, 0)
{
  r := BitwiseOr(x, 0);
}
"""

ASSUME_IN_BODY = """
method HasAssume(x: int) returns (r: int)
  ensures r == x
{
  assume x >= 0;
  r := x;
}
"""

# The gap row 51 closes: a lemma the method calls (dropped as a hint,
# decision 8) whose own proof hides an `assume` -- invisible to every
# check before this one, since `walk()` never reaches a `LemmaDecl`'s body.
ASSUME_IN_CALLEE_LEMMA = """
lemma Helper(x: int)
  ensures x >= 0
{
  assume x >= 0;
}

method UsesHelper(x: int) returns (r: int)
  ensures r == x
{
  Helper(x);
  r := x;
}
"""

VERIFY_FALSE_LEMMA = """
function Stub(x: int): int
{
  0
}

lemma {:verify false} StubIdentity(x: int)
  ensures Stub(x) == x

method UseStub(x: int) returns (r: int)
  ensures r == Stub(x)
{
  r := Stub(x);
}
"""

# An axiom lemma the method's closure never touches: it lifts as before,
# noted, not refused.
UNTOUCHED_AXIOM = """
lemma {:axiom} UnusedAxiom(x: int)
  ensures x + 0 == x

method Plain(x: int) returns (r: int)
  ensures r == x
{
  r := x;
}
"""


def test_axiom_lemma_and_axiom_only_function_refuse_source_axiom() -> None:
    _refuses(NUMPY_BITWISE_OR, "NumpyBitwiseOr", "source-axiom")
    _refuses(AXIOM_ONLY_FUNCTION, "UseBitwiseOr", "source-axiom", "BitwiseOr")
    _refuses(VERIFY_FALSE_LEMMA, "UseStub", "source-axiom")
    print("test_axiom_lemma_and_axiom_only_function_refuse_source_axiom: ok")


def test_assume_refuses_source_assume() -> None:
    _refuses(ASSUME_IN_BODY, "HasAssume", "source-assume", "assume")
    _refuses(ASSUME_IN_CALLEE_LEMMA, "UsesHelper", "source-assume", "assume")
    print("test_assume_refuses_source_assume: ok")


def test_untouched_axiom_lifts_with_note() -> None:
    v = _classify_one(UNTOUCHED_AXIOM, "Plain")
    assert isinstance(v, C.Liftable), v
    assert v.axiom_in_file, "expected the untouched axiom lemma's line noted"
    print("test_untouched_axiom_lifts_with_note: ok")


def run() -> None:
    test_axiom_lemma_and_axiom_only_function_refuse_source_axiom()
    test_assume_refuses_source_assume()
    test_untouched_axiom_lifts_with_note()
    print("test_lift_source_axiom: ok")


if __name__ == "__main__":
    run()
