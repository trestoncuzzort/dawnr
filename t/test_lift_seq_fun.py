#!/usr/bin/env python3
"""test_lift_seq_fun.py: LIFTER-DECISIONS row 49 (2026-09-27, SPEC.md
"Seq-valued spec_funs (v1)") -- a Dafny function returning `string`,
`seq<char>`, `seq<int>` or `seq<nat>` lifts to a spec_fun with a `"seq"`
result (the string spellings as code points, row 28), where before this
row every such closure function refused `function-result`. A function
`requires` or a `nat` parameter totalises with the empty seq as the
default (decision 6); a `seq<nat>` result drops its element fact, counted.
A nested-seq or tuple result still refuses `function-result` by name. No
prover for the rewrite tests; `--slow` runs the check stage under dafny.

Run: python3 t/test_lift_seq_fun.py [--slow]   (or pytest)
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


def _classify_one(src: str, method_name: str):
    mod = lift_parse.parse(src)
    methods = {m.name: m for m in lift_parse.gradable_methods(mod)}
    return mod, methods[method_name], C.classify(mod, methods[method_name])


def _lift_one(src: str, method_name: str):
    mod, method, v = _classify_one(src, method_name)
    assert isinstance(v, C.Liftable), f"expected liftable, got refusal: {v}"
    rr = R.rewrite(mod, v, "unit.dfy", "sha")
    assert rr.refusal is None, rr.refusal
    errs = check_wf.check_wf(rr.task)
    assert errs == [], errs
    return rr, method, v


def _rules(rr) -> set:
    return {rw.rule for rw in rr.record.rewrites}


def _spec_fun(task: dict, name: str) -> dict:
    return next(f for f in task["spec_funs"] if f["name"] == name)


STRING_HELPER = """
function Tail(s: string): string
{
  if |s| >= 1 then s[1..] else ""
}

method DropFirst(s: string) returns (r: string)
  requires |s| >= 1
  ensures r == Tail(s)
  ensures |r| == |s| - 1
{
  r := s[1..];
}
"""


def test_string_function_is_a_seq_spec_fun() -> None:
    rr, _m, _v = _lift_one(STRING_HELPER, "DropFirst")
    task = rr.task
    f = _spec_fun(task, "tail")
    assert f["result"] == "seq", f
    assert f["body"]["ite"]["else"] == {"op": "seq", "args": []}, f["body"]
    assert task["ensures"][0] == {"op": "==", "args": [
        {"var": "r"}, {"call": {"fun": "tail", "args": [{"var": "s"}]}}]}
    assert "function-result-seq" in _rules(rr)
    assert interp.Reference(task).points
    print("test_string_function_is_a_seq_spec_fun: ok")


RECURSIVE_SEQ = """
function Dbl(s: seq<int>, n: nat): seq<int>
  requires n <= |s|
  decreases n
{
  if n == 0 then [] else Dbl(s, n - 1) + [2 * s[n - 1]]
}

method DoubleAll(s: seq<int>) returns (r: seq<int>)
  ensures r == Dbl(s, |s|)
  ensures |r| == |s|
{
  r := [];
  var i := 0;
  while i < |s|
    invariant 0 <= i <= |s|
    invariant r == Dbl(s, i)
    invariant |r| == i
    decreases |s| - i
  {
    r := r + [2 * s[i]];
    i := i + 1;
  }
}
"""


def test_recursive_seq_function_totalises_with_empty() -> None:
    rr, _m, _v = _lift_one(RECURSIVE_SEQ, "DoubleAll")
    task = rr.task
    f = _spec_fun(task, "dbl")
    assert f["result"] == "seq"
    # decision 6: the nat parameter and the requires become one guard with
    # the empty seq as the default outside the domain
    assert f["body"]["ite"]["else"] == {"op": "seq", "args": []}, f["body"]
    assert f["decreases"] == {"var": "n"}
    assert "spec-fun-totalised" in _rules(rr)
    assert task["body"][-1]["while"]["invariants"][1] == {"op": "==", "args": [
        {"var": "r"}, {"call": {"fun": "dbl", "args": [{"var": "s"}, {"var": "i"}]}}]}
    ref = interp.Reference(task)
    assert ref.points
    print("test_recursive_seq_function_totalises_with_empty: ok")


SEQ_RESULT_USED = """
function Evens(s: seq<int>): seq<int>
  decreases |s|
{
  if |s| == 0 then [] else if s[0] % 2 == 0 then [s[0]] + Evens(s[1..]) else Evens(s[1..])
}

method FirstEven(s: seq<int>) returns (r: int)
  requires |Evens(s)| > 0
  ensures r == Evens(s)[0]
{
  var i := 0;
  r := 0;
  while i < |s|
    invariant 0 <= i <= |s|
    invariant Evens(s[..i]) == []
    decreases |s| - i
  {
    if s[i] % 2 == 0 {
      r := s[i];
      return;
    }
    i := i + 1;
  }
}
"""


def test_seq_result_indexed_measured_sliced_and_compared() -> None:
    rr, _m, _v = _lift_one(SEQ_RESULT_USED, "FirstEven")
    task = rr.task
    f = _spec_fun(task, "evens")
    assert f["result"] == "seq"
    assert f["decreases"] == {"op": "len", "args": [{"var": "s_v"}]}, f["decreases"]
    call = {"call": {"fun": "evens", "args": [{"var": "s"}]}}
    assert task["requires"] == [{"op": ">", "args": [{"op": "len", "args": [call]}, {"int": 0}]}]
    assert task["ensures"] == [{"op": "==", "args": [{"var": "r"}, {"op": "at", "args": [call, {"int": 0}]}]}]
    inv = task["body"][-1]["while"]["invariants"][-1]
    assert inv["op"] == "==" and inv["args"][0]["call"]["fun"] == "evens"
    assert inv["args"][0]["call"]["args"][0]["op"] == "slice"
    assert inv["args"][1] == {"op": "seq", "args": []}
    print("test_seq_result_indexed_measured_sliced_and_compared: ok")


SEQ_NAT_RESULT = """
function Ones(n: nat): seq<nat>
  decreases n
{
  if n == 0 then [] else Ones(n - 1) + [1]
}

method MakeOnes(n: nat) returns (r: seq<nat>)
  ensures r == Ones(n)
{
  r := [];
  var i := 0;
  while i < n
    invariant 0 <= i <= n
    invariant r == Ones(i)
    decreases n - i
  {
    r := r + [1];
    i := i + 1;
  }
}
"""


def test_seq_nat_result_drops_its_fact_and_is_counted() -> None:
    rr, _m, _v = _lift_one(SEQ_NAT_RESULT, "MakeOnes")
    f = _spec_fun(rr.task, "ones")
    assert f["result"] == "seq"
    assert "nat-result-fact-dropped" in _rules(rr)
    assert any(c.rule == "nat-result-fact-dropped" for c in rr.record.clauses_dropped)
    print("test_seq_nat_result_drops_its_fact_and_is_counted: ok")


NESTED_RESULT = """
function Rows(n: nat): seq<seq<int>>
{
  if n == 0 then [] else [[n]]
}

method R(n: nat) returns (r: int)
  ensures r == |Rows(n)|
{
  r := if n == 0 then 0 else 1;
}
"""

TUPLE_RESULT = """
function Two(n: int): (int, int)
{
  (n, n)
}

method T(n: int) returns (r: int)
  ensures r == Two(n).0
{
  r := n;
}
"""


def test_other_results_still_refuse_by_name() -> None:
    _mod, _m, v = _classify_one(NESTED_RESULT, "R")
    assert not isinstance(v, C.Liftable) and v.reason == "function-result", v
    assert "seq<seq<int>>" in (v.token or ""), v
    _mod, _m, v = _classify_one(TUPLE_RESULT, "T")
    assert not isinstance(v, C.Liftable) and v.reason == "function-result", v
    print("test_other_results_still_refuse_by_name: ok")


BOOL_FUNCTION = """
function IsSmall(n: int): bool
{
  n < 10
}

method Clamp(n: int) returns (r: int)
  ensures IsSmall(r)
  ensures IsSmall(n) ==> r == n
{
  if n < 10 { r := n; } else { r := 9; }
}
"""


def test_bool_function_lifts_as_a_predicate() -> None:
    """A `function F(..): bool` is a predicate spelled as a function (Dafny
    Reference Manual 6.4.2) and lifts to a bool spec_fun exactly as a
    `predicate` does. Before 2026-09-27 (this feature's measurement, 66 of
    the 305 `function-result` methods of the baseline re-lift) classify
    refused it `function-result` although `_lift_function` already typed
    it bool; this test asserts the lift where an older one would have
    asserted the refusal."""
    rr, _m, _v = _lift_one(BOOL_FUNCTION, "Clamp")
    f = _spec_fun(rr.task, "isSmall")
    assert f["result"] == "bool", f
    assert f["body"] == {"op": "<", "args": [{"var": "n_v"}, {"int": 10}]}, f["body"]
    assert rr.task["ensures"][0] == {"call": {"fun": "isSmall", "args": [{"var": "r"}]}}
    assert interp.Reference(rr.task).points
    print("test_bool_function_lifts_as_a_predicate: ok")


def _check_end_to_end(src: str, method_name: str) -> None:
    rr, method, plan = _lift_one(src, method_name)
    with tempfile.TemporaryDirectory() as d:
        out = lift_check.check(rr.task, method, plan.closure, rr.record, Path(d) / "unit.check.dfy",
                               240.0, callees=rr.callees)
    assert out.refusal is None, (out.refusal, rr.record.checker_verdicts, rr.record.warnings)
    dv = str(rr.record.differential_verdict)
    assert dv.startswith("arm-unavailable") or dv not in ("None", "timeout"), dv
    print(f"    differential: {dv[:80]}")


def test_check_stage(slow: bool) -> None:
    if not slow:
        print("test_check_stage: skipped (pass --slow)")
        return
    for src, m in ((STRING_HELPER, "DropFirst"), (RECURSIVE_SEQ, "DoubleAll"),
                   (SEQ_NAT_RESULT, "MakeOnes")):
        _check_end_to_end(src, m)
        print(f"test_check_stage: {m} ok")


def run(slow: bool = False) -> None:
    test_string_function_is_a_seq_spec_fun()
    test_recursive_seq_function_totalises_with_empty()
    test_seq_result_indexed_measured_sliced_and_compared()
    test_seq_nat_result_drops_its_fact_and_is_counted()
    test_other_results_still_refuse_by_name()
    test_bool_function_lifts_as_a_predicate()
    test_check_stage(slow)
    print("test_lift_seq_fun: ok")


if __name__ == "__main__":
    run("--slow" in sys.argv[1:])
