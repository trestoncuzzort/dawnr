#!/usr/bin/env python3
"""test_lift_array_functions.py: t/FEATURES-TRACK.md feature 4 (2026-09-27),
LIFTER-DECISIONS row 42 -- a read-only `array<int>` parameter (decision 1)
stays a `seq` value when it is passed to a lemma (a ghost method that
cannot write the heap) or to another method whose own parameter is
read-only by the same condition; a mutated array passed to a lemma keeps
decision 22's shape; and a lemma with an `array<int>`/`array<nat>`
parameter lifts as a seq-param lemma. An array passed to a method that
writes it stays refused `array`. No prover for the rewrite tests; `--slow`
runs the check stage under dafny.

Run: python3 t/test_lift_array_functions.py [--slow]   (or pytest)
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import check_wf                                                # noqa: E402
import interp                                                  # noqa: E402
import lift_check                                              # noqa: E402
import lift_classify as C                                      # noqa: E402
import lift_parse                                              # noqa: E402
import lift_rewrite as R                                       # noqa: E402


def _lift_one(src: str, method_name: str):
    mod = lift_parse.parse(src)
    methods = {m.name: m for m in lift_parse.gradable_methods(mod)}
    v = C.classify(mod, methods[method_name])
    assert isinstance(v, C.Liftable), f"expected liftable, got refusal: {v}"
    rr = R.rewrite(mod, v, "unit.dfy", "sha")
    assert rr.refusal is None, rr.refusal
    errs = check_wf.check_wf(rr.task)
    assert errs == [], errs
    return rr, methods[method_name], v


def _classify_one(src: str, method_name: str):
    mod = lift_parse.parse(src)
    methods = {m.name: m for m in lift_parse.gradable_methods(mod)}
    return C.classify(mod, methods[method_name])


def _rules(record) -> set:
    return {w.rule for w in record.rewrites}


# vericoding DD0128's shape: a function reading the array, a lemma about
# it taking the array, and a method calling both with its parameter.
LEMMA_READS = """
function SumV(v: array<int>, c: int, f: int): int
  requires 0 <= c <= f <= v.Length
  reads v
  decreases f - c
{
  if c == f then 0 else v[c] + SumV(v, c + 1, f)
}

lemma SumVStep(v: array<int>, i: int)
  requires 0 <= i < v.Length
  ensures SumV(v, 0, i + 1) == SumV(v, 0, i) + v[i]
  decreases i
{
  if i > 0 { SumVStep(v, i - 1); }
}

method SumElems(v: array<int>) returns (sum: int)
  ensures sum == SumV(v, 0, v.Length)
{
  sum := 0;
  var i := 0;
  while i < v.Length
    invariant 0 <= i <= v.Length
    invariant sum == SumV(v, 0, i)
    decreases v.Length - i
  {
    SumVStep(v, i);
    sum := sum + v[i];
    i := i + 1;
  }
}
"""


def test_array_passed_to_a_lemma_stays_read_only() -> None:
    rr, _m, _v = _lift_one(LEMMA_READS, "SumElems")
    task = rr.task
    assert task["params"][0]["type"] == "seq", task["params"]
    (lemma,) = task["lemmas"]
    assert lemma["params"][0]["type"] == "seq", lemma["params"]
    assert "array-readonly-as-seq" in _rules(rr.record) and "lemma-lifted" in _rules(rr.record)
    ref = interp.Reference(task)
    assert ref.points and all(v == sum(env["v"]) for env, v in ref.points), ref.points[:3]


# vericoding DD0135's shape: a method handing its array to a callee that
# only reads it.
READONLY_CALLEE = """
method Count(v: array<int>, x: int) returns (c: int)
  ensures c >= 0
{
  c := 0;
  var i := 0;
  while i < v.Length
    invariant 0 <= i <= v.Length && c >= 0
    decreases v.Length - i
  {
    if v[i] == x { c := c + 1; }
    i := i + 1;
  }
}

method Has(v: array<int>, x: int) returns (b: bool)
  ensures b ==> v.Length > 0 || true
{
  var c := Count(v, x);
  b := c > 0;
}
"""


def test_array_passed_to_a_read_only_callee() -> None:
    rr, _m, _v = _lift_one(READONLY_CALLEE, "Has")
    task = rr.task
    assert task["params"][0]["type"] == "seq"
    (m,) = task["methods"]
    assert m["params"][0]["type"] == "seq", m["params"]
    assert "method-lifted" in _rules(rr.record)


# decision 22's in-place shape, with the corpus's own permutation lemma
# taking the mutated array: the lemma is no alias.
MUTATED_TO_LEMMA = """
lemma ZeroFact(a: array<int>, i: int)
  requires 0 <= i < a.Length
  ensures a[i] == a[i]
{
}

method Zero(a: array<int>)
  modifies a
  ensures forall k :: 0 <= k < a.Length ==> a[k] == 0
{
  var i := 0;
  while i < a.Length
    invariant 0 <= i <= a.Length
    invariant forall k :: 0 <= k < i ==> a[k] == 0
    decreases a.Length - i
  {
    a[i] := 0;
    ZeroFact(a, i);
    i := i + 1;
  }
}
"""


def test_mutated_array_passed_to_a_lemma() -> None:
    rr, _m, _v = _lift_one(MUTATED_TO_LEMMA, "Zero")
    task = rr.task
    assert task["returns"][0]["type"] == "seq" and "array-mutation-fresh-return" in _rules(rr.record)


# an array handed to a method that WRITES it is still an escape
WRITING_CALLEE = """
method Fill(a: array<int>, x: int)
  modifies a
  ensures forall k :: 0 <= k < a.Length ==> a[k] == x
{
  var i := 0;
  while i < a.Length
    invariant 0 <= i <= a.Length
    invariant forall k :: 0 <= k < i ==> a[k] == x
    decreases a.Length - i
  {
    a[i] := x;
    i := i + 1;
  }
}

method Reset(a: array<int>) returns (n: int)
  modifies a
  ensures n == a.Length
{
  Fill(a, 0);
  n := a.Length;
}
"""


def test_array_passed_to_a_writing_method_stays_refused() -> None:
    v = _classify_one(WRITING_CALLEE, "Reset")
    assert not isinstance(v, C.Liftable) and v.reason in ("array", "array-mutation"), v


NAT_ARRAY_LEMMA = """
lemma Pos(a: array<nat>, i: int)
  requires 0 <= i < a.Length
  ensures a[i] >= 0
{
}

method First(a: array<nat>) returns (r: int)
  requires a.Length > 0
  ensures r >= 0
{
  Pos(a, 0);
  r := a[0];
}
"""


def test_nat_array_lemma_param_gets_element_clause() -> None:
    rr, _m, _v = _lift_one(NAT_ARRAY_LEMMA, "First")
    (lemma,) = rr.task["lemmas"]
    assert lemma["params"][0]["type"] == "seq"
    assert any("forall" in r for r in lemma["requires"]), lemma["requires"]


MUTATED_TO_PREDICATE = """
predicate AllZero(a: array<int>, lo: int, hi: int)
  requires 0 <= lo <= hi <= a.Length
  reads a
{
  forall k :: lo <= k < hi ==> a[k] == 0
}

method Clear(a: array<int>)
  modifies a
  ensures AllZero(a, 0, a.Length)
{
  var i := 0;
  while i < a.Length
    invariant 0 <= i <= a.Length
    invariant AllZero(a, 0, i)
    decreases a.Length - i
  {
    a[i] := 0;
    i := i + 1;
  }
}
"""


def test_mutated_array_passed_to_a_predicate() -> None:
    """The in-place shape (2026-09-27): decision 22's mutated array read by
    a closure predicate in an invariant is no alias (a function reads the
    value at the point of evaluation, the threaded seq); it used to refuse
    `array`/`aliased` (insertionSort, sorting of the 2026-09-26 lift)."""
    rr, _m, _v = _lift_one(MUTATED_TO_PREDICATE, "Clear")
    assert rr.task["returns"][0]["type"] == "seq"
    assert any(f["name"].lower().startswith("allzero") for f in rr.task["spec_funs"])
    print("test_mutated_array_passed_to_a_predicate: ok")


def _check_end_to_end(src: str, method_name: str) -> None:
    rr, method, plan = _lift_one(src, method_name)
    with tempfile.TemporaryDirectory() as d:
        out = lift_check.check(rr.task, method, plan.closure, rr.record, Path(d) / "unit.check.dfy",
                               240.0, callees=rr.callees)
    assert out.refusal is None, (out.refusal, rr.record.checker_verdicts)


def test_check_stage(slow: bool) -> None:
    if not slow:
        print("test_check_stage: skipped (pass --slow)")
        return
    for src, m in ((LEMMA_READS, "SumElems"), (READONLY_CALLEE, "Has"), (MUTATED_TO_LEMMA, "Zero"),
                   (MUTATED_TO_PREDICATE, "Clear")):
        _check_end_to_end(src, m)
        print(f"test_check_stage: {m} ok")


def run(slow: bool = False) -> None:
    test_array_passed_to_a_lemma_stays_read_only()
    test_array_passed_to_a_read_only_callee()
    test_mutated_array_passed_to_a_lemma()
    test_array_passed_to_a_writing_method_stays_refused()
    test_nat_array_lemma_param_gets_element_clause()
    test_mutated_array_passed_to_a_predicate()
    test_check_stage(slow)
    print("test_lift_array_functions: ok")


if __name__ == "__main__":
    run("--slow" in sys.argv[1:])
