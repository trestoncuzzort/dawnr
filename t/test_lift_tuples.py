#!/usr/bin/env python3
"""test_lift_tuples.py: LIFTER-DECISIONS row 44 (2026-09-27, t/FEATURES-TRACK.md,
tuples) -- a Dafny tuple type `(T1, T2)` with two components row 29 already
carries (int, nat, bool, seq, string) lifts as t's pair (SPEC.md "Pairs (v1)"):
a tuple-typed return under the source's own name, a tuple parameter or local,
the literal `(a, b)` as the pair literal, `p.0`/`p.1` as `fst`/`snd`; a `nat`
component gets the same guard/ensures a nat return or parameter does, on its
projection. Any other arity refuses `tuple-arity`, any other component type
`tuple-component`. No prover for the rewrite tests; `--slow` runs the check
stage under dafny.

Run: python3 t/test_lift_tuples.py [--slow]   (or pytest)
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


TUPLE_RETURN = """
method SumDiff(x: int, y: int) returns (result: (int, int))
  ensures result.0 == x + y
  ensures result.1 == x - y
{
  result := (x + y, x - y);
}
"""


def test_tuple_return_is_a_pair() -> None:
    rr, _m, _v = _lift_one(TUPLE_RETURN, "SumDiff")
    task = rr.task
    assert task["returns"][0]["type"] == {"pair": ["int", "int"]}, task["returns"]
    r = task["returns"][0]["name"]
    assert task["ensures"][0] == {"op": "==", "args": [{"op": "fst", "args": [{"var": r}]},
                                                        {"op": "+", "args": [{"var": "x"}, {"var": "y"}]}]}
    assert task["body"][-1]["assign"] == [r, {"op": "pair", "args": [
        {"op": "+", "args": [{"var": "x"}, {"var": "y"}]},
        {"op": "-", "args": [{"var": "x"}, {"var": "y"}]}]}]
    assert {"tuple-literal-lifted", "tuple-projection-lifted"} <= _rules(rr)
    ref = interp.Reference(task)
    assert ref.points
    print("test_tuple_return_is_a_pair: ok")


NAT_TUPLE = """
method Bounds(n: nat, m: nat) returns (pair: (nat, nat))
  ensures pair.0 <= pair.1
  ensures pair.0 == n || pair.0 == m
{
  if n <= m {
    pair := (n, m);
  } else {
    pair := (m, n);
  }
}
"""


def test_nat_components_get_their_ensures() -> None:
    rr, _m, _v = _lift_one(NAT_TUPLE, "Bounds")
    task = rr.task
    assert task["returns"][0]["type"] == {"pair": ["int", "int"]}
    r = task["returns"][0]["name"]
    ge0 = [e for e in task["ensures"] if e.get("op") == ">=" and e["args"][1] == {"int": 0}]
    assert {"op": "fst", "args": [{"var": r}]} in [e["args"][0] for e in ge0]
    assert {"op": "snd", "args": [{"var": r}]} in [e["args"][0] for e in ge0]
    assert "nat-return-ensures" in _rules(rr)
    print("test_nat_components_get_their_ensures: ok")


TUPLE_LOCAL_AND_PARAM = """
method Swap(p: (int, bool)) returns (r: (bool, int))
  ensures r.0 == p.1 && r.1 == p.0
{
  var q: (int, bool) := (p.0, p.1);
  r := (q.1, q.0);
}
"""


def test_tuple_parameter_and_local() -> None:
    rr, _m, _v = _lift_one(TUPLE_LOCAL_AND_PARAM, "Swap")
    task = rr.task
    assert task["params"][0]["type"] == {"pair": ["int", "bool"]}
    assert task["returns"][0]["type"] == {"pair": ["bool", "int"]}
    assert task["body"][0]["var"]["type"] == {"pair": ["int", "bool"]}
    assert interp.Reference(task).points
    print("test_tuple_parameter_and_local: ok")


NAT_PARAM = """
method First(p: (nat, int)) returns (r: int)
  ensures r >= 0
{
  r := p.0;
}
"""


def test_nat_component_of_a_parameter_is_guarded() -> None:
    rr, _m, _v = _lift_one(NAT_PARAM, "First")
    p = rr.task["params"][0]["name"]
    assert {"op": ">=", "args": [{"op": "fst", "args": [{"var": p}]}, {"int": 0}]} in rr.task["requires"]
    assert "nat-param-guard" in _rules(rr)
    print("test_nat_component_of_a_parameter_is_guarded: ok")


TRIPLE = """
method Three(x: int) returns (r: (int, int, int))
  ensures r.0 == x
{
  r := (x, x, x);
}
"""

REAL_COMPONENT = """
method Avg(n: int) returns (r: (int, real))
  ensures r.0 == n
{
  r := (n, 0.0);
}
"""


def test_other_tuples_refuse_by_name() -> None:
    _mod, _m, v = _classify_one(TRIPLE, "Three")
    assert not isinstance(v, C.Liftable) and v.reason == "tuple-arity", v
    _mod, _m, v = _classify_one(REAL_COMPONENT, "Avg")
    assert not isinstance(v, C.Liftable) and v.reason == "tuple-component", v
    print("test_other_tuples_refuse_by_name: ok")


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
    for src, m in ((TUPLE_RETURN, "SumDiff"), (NAT_TUPLE, "Bounds"), (TUPLE_LOCAL_AND_PARAM, "Swap"),
                   (NAT_PARAM, "First")):
        _check_end_to_end(src, m)
        print(f"test_check_stage: {m} ok")


def run(slow: bool = False) -> None:
    test_tuple_return_is_a_pair()
    test_nat_components_get_their_ensures()
    test_tuple_parameter_and_local()
    test_nat_component_of_a_parameter_is_guarded()
    test_other_tuples_refuse_by_name()
    test_check_stage(slow)
    print("test_lift_tuples: ok")


if __name__ == "__main__":
    run("--slow" in sys.argv[1:])
