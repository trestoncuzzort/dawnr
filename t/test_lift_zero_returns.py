#!/usr/bin/env python3
"""test_lift_zero_returns.py: LIFTER-DECISIONS row 47 (2026-09-27,
t/FEATURES-TRACK.md, zero-returns) -- a Dafny method with no out-parameter
is a t task only through decision 22's modifies-param shape (its mutated
array is the return); everything else now refuses by a name that says why:
a `modifies` whose writes all happen inside a callee refuses
`array-mutation` (`modifies-via-call`), a body writing two arrays keeps the
shape detector's own `multi-array-mutation` instead of hiding it behind
`zero-returns`, and a method with no return and no `modifies` -- a lemma
about its parameters in t's vocabulary (SPEC.md "Lemmas (v1)") -- refuses
`lemma-shaped`. The modifies-param shape itself is unchanged and still
lifts. No prover needed.

Run: python3 t/test_lift_zero_returns.py   (or pytest)
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import check_wf                                                # noqa: E402
import lift_classify as C                                      # noqa: E402
import lift_parse                                              # noqa: E402
import lift_rewrite as R                                       # noqa: E402


def _classify_one(src: str, method_name: str):
    mod = lift_parse.parse(src)
    methods = {m.name: m for m in lift_parse.gradable_methods(mod)}
    return mod, methods[method_name], C.classify(mod, methods[method_name])


def _refuses(src: str, method_name: str, reason: str, token: str | None = None) -> None:
    _mod, _m, v = _classify_one(src, method_name)
    assert not isinstance(v, C.Liftable) and v.reason == reason, (method_name, v)
    if token is not None:
        assert v.token == token, (method_name, v)


LEMMA_SHAPED = """
method ExpIntSucc(x: nat, k: nat)
  ensures x + k >= x
{
}
"""

VIA_CALL = """
method Swap(a: array<int>, i: int, j: int)
  requires 0 <= i < a.Length && 0 <= j < a.Length
  modifies a
  ensures a[i] == old(a[j]) && a[j] == old(a[i])
{
  var t := a[i];
  a[i] := a[j];
  a[j] := t;
}

method SwapFirstTwo(a: array<int>)
  requires a.Length >= 2
  modifies a
  ensures a[0] == old(a[1])
{
  Swap(a, 0, 1);
}
"""

TWO_ARRAYS = """
method MyFun(a: array<int>, sum: array<int>, N: int)
  requires N > 0 && a.Length == N && sum.Length == 1
  modifies a, sum
  ensures sum[0] <= N
{
  var total := 0;
  var i := 0;
  while i < N
    invariant 0 <= i <= N && total <= i
  {
    if a[i] > 0 { total := total + 1; }
    a[i] := 0;
    i := i + 1;
  }
  sum[0] := total;
}
"""

NO_WRITE = """
method Touch(a: array<int>)
  modifies a
  ensures a.Length == old(a.Length)
{
}
"""


def test_refusals_by_name() -> None:
    _refuses(LEMMA_SHAPED, "ExpIntSucc", "lemma-shaped", "ExpIntSucc")
    _refuses(VIA_CALL, "SwapFirstTwo", "array-mutation", "modifies-via-call")
    # two arrays written: `array-mutation` either way -- the read-only-array
    # rule names the written param at the method line, the shape detector
    # names `multi-array-mutation` at the second write; both say why.
    _refuses(TWO_ARRAYS, "MyFun", "array-mutation")
    _refuses(NO_WRITE, "Touch", "array-mutation", "modifies-no-index-assign")
    print("test_refusals_by_name: ok")


FILL = """
method Fill(a: array<int>, v: int)
  modifies a
  ensures forall k :: 0 <= k < a.Length ==> a[k] == v
{
  var i := 0;
  while i < a.Length
    invariant 0 <= i <= a.Length
    invariant forall k :: 0 <= k < i ==> a[k] == v
    decreases a.Length - i
  {
    a[i] := v;
    i := i + 1;
  }
}
"""


def test_modifies_param_still_lifts() -> None:
    mod, method, v = _classify_one(FILL, "Fill")
    assert isinstance(v, C.Liftable), v
    rr = R.rewrite(mod, v, "unit.dfy", "sha")
    assert rr.refusal is None, rr.refusal
    assert check_wf.check_wf(rr.task) == []
    assert rr.task["returns"][0]["type"] == "seq"
    print("test_modifies_param_still_lifts: ok")


def run() -> None:
    test_refusals_by_name()
    test_modifies_param_still_lifts()
    print("test_lift_zero_returns: ok")


if __name__ == "__main__":
    run()
