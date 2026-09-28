#!/usr/bin/env python3
"""test_lift_sets.py: LIFTER-DECISIONS row 52 (2026-09-27, SPEC.md "Finite
sets (v1)") -- the lifter's own mapping of Dafny's `set<int>` onto t's
finite-set type: a `set<int>` parameter, return or local; a display `{e,
...}`/`{}`; `in`/`!in`; `|s|`; `+`/`*`/`-` (Dafny's own union/intersection/
difference, Dafny Reference Manual 5.5.1) between two sets; `==`/`!=`. What
stays out of v1 refuses by name: a set comprehension (`set-comprehension`,
sharper than the plain `set` bucket a display or a typed name now uses), a
`set<T>` for T not int (`set-of-bool`/`set-of-real`/`set-of-pair`/...,
`nat-set-elements` for `set<nat>`), `iset`, `multiset` (a `multiset{...}`
display reuses the same AST node as a genuine set display, so it must
refuse by that name too, never lift as one), a subset comparison
(`set-subset`), disjointness (`set-disjoint`), a set used as a
quantifier's own range (`unbounded-quantifier` -- SPEC.md: "Not in v1: ...
a set as a quantifier's range"), and a set-typed spec_fun parameter
(`set-spec-fun-param`). No prover needed for the classify/rewrite tests;
`--slow` runs the check stage under dafny.

Run: python3 t/test_lift_sets.py [--slow]   (or pytest)
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


def _refuses(src: str, method_name: str, reason: str) -> None:
    _mod, _m, v = _classify_one(src, method_name)
    assert not isinstance(v, C.Liftable) and v.reason == reason, (method_name, v)


def _rules(rr) -> set:
    return {rw.rule for rw in rr.record.rewrites}


SET_PARAM_RETURN = """
method Common(a: set<int>, b: set<int>) returns (r: set<int>)
  ensures |r| <= |a|
{
  r := a * b;
}
"""


def test_set_param_and_return_lift() -> None:
    rr, _m, _v = _lift_one(SET_PARAM_RETURN, "Common")
    task = rr.task
    assert task["params"][0]["type"] == "set", task["params"]
    assert task["params"][1]["type"] == "set", task["params"]
    assert task["returns"][0]["type"] == "set", task["returns"]
    r = task["returns"][0]["name"]
    assert task["body"][-1]["assign"] == [r, {"op": "inter", "args": [
        {"var": task["params"][0]["name"]}, {"var": task["params"][1]["name"]}]}]
    assert task["ensures"][0] == {"op": "<=", "args": [
        {"op": "card", "args": [{"var": r}]},
        {"op": "card", "args": [{"var": task["params"][0]["name"]}]}]}
    assert "set-inter-lifted" in _rules(rr)
    assert "set-card-lifted" in _rules(rr)
    ref = interp.Reference(task)
    assert ref.points
    print("test_set_param_and_return_lift: ok")


SET_DISPLAY_AND_OPS = """
method Build(a: set<int>, x: int) returns (r: bool)
  ensures r == (x in a)
{
  var s := a + {1, 2, 3};
  var d := s - {1};
  r := x in d || x !in a;
}
"""


def test_display_union_diff_and_membership() -> None:
    rr, _m, _v = _lift_one(SET_DISPLAY_AND_OPS, "Build")
    task = rr.task
    body = task["body"]
    assert body[0]["var"]["type"] == "set"
    assert body[0]["var"]["init"]["op"] == "union"
    assert body[1]["var"]["init"]["op"] == "diff"
    rules = _rules(rr)
    assert {"set-literal-lifted", "set-union-lifted", "set-diff-lifted",
            "set-membership-lifted"} <= rules
    assert "in-desugared" not in rules  # never the seq desugaring for a set operand
    ref = interp.Reference(task)
    assert ref.points
    print("test_display_union_diff_and_membership: ok")


UNTYPED_LOCAL = """
method Union2(a: set<int>, b: set<int>) returns (r: int)
  ensures r >= 0
{
  var u := a + b;
  r := |u|;
}
"""


def test_untyped_local_infers_set_kind() -> None:
    # Row 52's own residual (measured against the smoke test this row's
    # implementation was built from): an UNTYPED local bound to a set
    # expression used to fall through to t's int default, and a later
    # set operator reading it printed the bare Dafny symbol instead of
    # `union`/`inter`/`diff`.
    rr, _m, _v = _lift_one(UNTYPED_LOCAL, "Union2")
    body = rr.task["body"]
    assert body[0]["var"]["type"] == "set", body[0]
    assert body[0]["var"]["init"] == {"op": "union", "args": [
        {"var": rr.task["params"][0]["name"]}, {"var": rr.task["params"][1]["name"]}]}
    assert rr.task["body"][1]["assign"][1] == {"op": "card", "args": [{"var": body[0]["var"]["name"]}]}
    print("test_untyped_local_infers_set_kind: ok")


TYPED_LOCAL_NO_INIT = """
method Declared(a: set<int>) returns (r: bool)
  ensures r
{
  var d: set<int>;
  d := a;
  r := |d| >= 0;
}
"""


def test_declared_local_with_no_initialiser_defaults_empty() -> None:
    rr, _m, _v = _lift_one(TYPED_LOCAL_NO_INIT, "Declared")
    body = rr.task["body"]
    assert body[0]["var"]["type"] == "set"
    assert body[0]["var"]["init"] == {"op": "set", "args": []}
    print("test_declared_local_with_no_initialiser_defaults_empty: ok")


def test_multiset_display_refuses_by_name() -> None:
    src = """
method M(x: int) returns (r: bool)
  ensures r
{
  var m := multiset{1, 2, 3};
  r := m != multiset{};
}
"""
    _refuses(src, "M", "multiset")


def test_iset_param_refuses_by_name() -> None:
    src = """
method K(a: iset<int>) returns (r: bool)
  ensures r
{
  r := true;
}
"""
    _refuses(src, "K", "iset")


def test_set_of_real_refuses_by_name() -> None:
    src = """
method H(a: set<real>) returns (r: int)
  ensures r == 0
{
  r := 0;
}
"""
    _refuses(src, "H", "set-of-real")


def test_set_of_nat_refuses_by_name() -> None:
    # SPEC.md "Finite sets (v1)" states int alone; a `set<nat>`'s
    # per-element non-negativity is part of the source's own theorem,
    # exactly as decision 14 reads a `seq<nat>` -- a fact this lifter has
    # no per-element guard to carry, so it refuses rather than drops it.
    src = """
method J(a: set<nat>) returns (r: int)
  ensures r == 0
{
  r := 0;
}
"""
    _refuses(src, "J", "nat-set-elements")


def test_bare_set_refuses_generic() -> None:
    src = """
predicate IsSubset(A: set, B: set)
{
  A <= B
}
method N(a: set<int>, b: set<int>) returns (r: bool)
  ensures r == IsSubset(a, b)
{
  r := IsSubset(a, b);
}
"""
    _refuses(src, "N", "set-spec-fun-param")


def test_set_display_of_non_int_refuses_by_element() -> None:
    src = """
method D(x: bool) returns (r: bool)
  ensures r
{
  var s := {x};
  r := true;
}
"""
    _refuses(src, "D", "set-of-bool")


def test_set_comprehension_refuses_sharper_than_plain_set() -> None:
    src = """
method G(n: int) returns (c: int)
  ensures c == |set i: int | 0 <= i < n && i % 2 == 0|
{
  c := |set i: int | 0 <= i < n && i % 2 == 0|;
}
"""
    _refuses(src, "G", "set-comprehension")


def test_subset_and_superset_refuse_by_name() -> None:
    src = """
method S(a: set<int>, b: set<int>) returns (r: bool)
  ensures r == (a <= b)
{
  r := a <= b;
}
"""
    _refuses(src, "S", "set-subset")
    src2 = src.replace("<=", ">")
    _refuses(src2, "S", "set-subset")


def test_disjointness_refuses_by_name() -> None:
    src = """
method Dj(a: set<int>, b: set<int>) returns (r: bool)
  ensures r == (a !! b)
{
  r := a !! b;
}
"""
    _refuses(src, "Dj", "set-disjoint")


def test_set_as_quantifier_range_refuses_unbounded() -> None:
    # SPEC.md "Finite sets (v1)": "Not in v1: ... a set as a quantifier's
    # range" -- a set has no [lo, hi) t can quantify over, so `x in c`
    # binding the quantifier's OWN variable stays refused even though a
    # plain membership test (test_display_union_diff_and_membership,
    # above) lifts to t's native `in`.
    src = """
method Q(c: set<int>) returns (r: bool)
  ensures r == (forall x :: x in c ==> x >= 0)
{
  r := forall x :: x in c ==> x >= 0;
}
"""
    _refuses(src, "Q", "unbounded-quantifier")


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
    for src, m in ((SET_PARAM_RETURN, "Common"), (SET_DISPLAY_AND_OPS, "Build"),
                   (UNTYPED_LOCAL, "Union2")):
        _check_end_to_end(src, m)
        print(f"test_check_stage: {m} ok")


def run(slow: bool = False) -> None:
    test_set_param_and_return_lift()
    test_display_union_diff_and_membership()
    test_untyped_local_infers_set_kind()
    test_declared_local_with_no_initialiser_defaults_empty()
    test_multiset_display_refuses_by_name()
    test_iset_param_refuses_by_name()
    test_set_of_real_refuses_by_name()
    test_set_of_nat_refuses_by_name()
    test_bare_set_refuses_generic()
    test_set_display_of_non_int_refuses_by_element()
    test_set_comprehension_refuses_sharper_than_plain_set()
    test_subset_and_superset_refuse_by_name()
    test_disjointness_refuses_by_name()
    test_set_as_quantifier_range_refuses_unbounded()
    test_check_stage(slow)
    print("test_lift_sets: ok")


if __name__ == "__main__":
    run("--slow" in sys.argv[1:])
