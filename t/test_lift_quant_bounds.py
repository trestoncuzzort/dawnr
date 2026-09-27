#!/usr/bin/env python3
"""test_lift_quant_bounds.py: t/FEATURES-TRACK.md feature 5 (2026-09-27),
LIFTER-DECISIONS row 40 -- the quantifier shapes the lifter now bounds:
a range written with `>=`/`>`, a `nat` binder with only an upper bound, a
membership conjunct among others, a chain holding several binders, a binder
pinned by an equality in the body, and a range read through a predicate's
body. Truly unbounded quantifiers stay refused by name. No prover for the
rewrite tests; `--slow` (or pytest's `--slow`) runs the check stage under
dafny, which proves each lifted clause equivalent to its source.

Run: python3 t/test_lift_quant_bounds.py [--slow]   (or pytest)
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import check_wf                                                # noqa: E402
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
    return rr.task, rr.record, methods[method_name], v


def _classify_one(src: str, method_name: str):
    mod = lift_parse.parse(src)
    methods = {m.name: m for m in lift_parse.gradable_methods(mod)}
    return C.classify(mod, methods[method_name])


def _rules(record) -> set:
    return {w.rule for w in record.rewrites}


def _quants(node, key: str) -> list:
    out = []
    if isinstance(node, dict):
        if key in node:
            out.append(node[key])
        for v in node.values():
            out += _quants(v, key)
    elif isinstance(node, list):
        for v in node:
            out += _quants(v, key)
    return out


LEN = lambda name: {"op": "len", "args": [{"var": name}]}  # noqa: E731


# HumanEval-Dafny's house style: the range as two comparisons, `>=` first.
GE_STYLE = """
method GetPositive(l: seq<int>) returns (result: seq<int>)
  ensures forall i: int :: i >= 0 && i < |result| ==> result[i] > 0
  ensures forall i: int :: i > 0 && i <= |result| && i % 2 == 0 ==> result[i - 1] > 0
{
  result := [];
}
"""


def test_ge_style_range() -> None:
    task, rec, _m, _v = _lift_one(GE_STYLE, "GetPositive")
    q1, q2 = _quants(task["ensures"], "forall")
    assert q1["lo"] == {"int": 0} and q1["hi"] == LEN("result"), q1
    # `i > 0` reads `0 + 1`, the `_plus1` spelling every strict bound has had
    assert q2["lo"] == {"op": "+", "args": [{"int": 0}, {"int": 1}]}, q2
    assert q2["hi"] == {"op": "+", "args": [LEN("result"), {"int": 1}]}, q2
    # the leftover conjunct `i % 2 == 0` stays as the antecedent
    assert q2["body"]["op"] == "implies" and q2["body"]["args"][0]["op"] == "==", q2["body"]
    assert "quantifier-bounded" in _rules(rec)


# A `nat` binder with only an upper bound: the type is the lower bound.
NAT_BINDER = """
method FirstZero(s: seq<int>, n: int) returns (r: bool)
  requires n <= |s|
  ensures r <==> exists y: nat :: y < n && s[y] == 0
{
  r := false;
}
"""


def test_nat_binder_upper_bound_only() -> None:
    task, rec, _m, _v = _lift_one(NAT_BINDER, "FirstZero")
    (q,) = _quants(task["ensures"], "exists")
    assert q["lo"] == {"int": 0} and q["hi"] == {"var": "n"}, q
    assert "quantifier-bounded-nat" in _rules(rec)


# A membership conjunct among others (HumanEval-Dafny 104 unique_digits).
MEMBERSHIP_AMONG = """
predicate HasNoEvenDigit(e: int)
{
  e % 2 == 1
}

method UniqueDigits(x: seq<int>) returns (result: seq<int>)
  ensures forall e: int :: e in x && HasNoEvenDigit(e) ==> e in result
{
  result := [];
}
"""


def test_membership_among_conjuncts() -> None:
    task, rec, _m, _v = _lift_one(MEMBERSHIP_AMONG, "UniqueDigits")
    (q,) = [q for q in _quants(task["ensures"], "forall")]
    assert q["lo"] == {"int": 0} and q["hi"] == LEN("x"), q
    body = q["body"]
    assert body["op"] == "implies", body
    # the predicate now reads x[j]
    assert body["args"][0]["call"]["args"][0]["op"] == "at", body["args"][0]
    assert "in-desugared" in _rules(rec)


# One chain holding several binders: the sortedness invariant and the
# four-binder nesting test (HumanEval-Dafny 132 is_nested).
CHAINS = """
method Nested(s: seq<int>, sorted: seq<int>, i: int, n: int) returns (res: bool)
  requires n == |sorted| && 0 <= i <= n
  ensures res == exists x: int, y: int, z: int, w: int :: 0 <= x < y < z < w < |s| && s[x] == 91 && s[y] == 91 && s[z] == 93 && s[w] == 93
  ensures forall k1: int, k2: int :: 0 <= k1 < i <= k2 < n ==> sorted[k1] <= sorted[k2]
  ensures forall k: int :: 0 <= k < i <= n ==> sorted[k] == sorted[k]
{
  res := false;
}
"""


def test_chain_with_several_binders() -> None:
    task, rec, _m, _v = _lift_one(CHAINS, "Nested")
    ex = _quants(task["ensures"][0], "exists")
    assert len(ex) == 4, len(ex)
    x, y, z, w = ex
    assert x["lo"] == {"int": 0} and x["hi"] == LEN("s"), x
    assert y["lo"] == {"op": "+", "args": [{"var": x["var"]}, {"int": 1}]} and y["hi"] == LEN("s"), y
    assert w["lo"] == {"op": "+", "args": [{"var": z["var"]}, {"int": 1}]}, w
    fa = _quants(task["ensures"][1], "forall")
    assert len(fa) == 2
    k1, k2 = fa
    assert k1["lo"] == {"int": 0} and k1["hi"] == {"var": "i"}, k1
    assert k2["lo"] == {"var": "i"} and k2["hi"] == {"var": "n"}, k2
    (k,) = _quants(task["ensures"][2], "forall")
    assert k["lo"] == {"int": 0} and k["hi"] == {"var": "i"}, k
    # the binder-free relation `i <= n` of the chain stays in the body
    assert k["body"]["op"] == "implies" and k["body"]["args"][0] == {"op": "<=", "args": [{"var": "i"}, {"var": "n"}]}, k["body"]
    assert "quantifier-bounded-chain" in _rules(rec)


# A binder pinned by an equality in an exists body (vericoding DA0491):
# the quantifier is its body.
PINNED = """
function Count(s: seq<int>): int
{
  |s|
}

method Solve(s: seq<int>) returns (result: int)
  ensures exists count: int :: count == Count(s) && result == count + 1
  ensures forall c: int :: c == Count(s) ==> result > c
{
  result := |s| + 1;
}
"""


def test_pinned_binder_eliminates_quantifier() -> None:
    task, rec, _m, _v = _lift_one(PINNED, "Solve")
    assert _quants(task["ensures"], "exists") == [] and _quants(task["ensures"], "forall") == []
    assert task["ensures"][0] == {"op": "==", "args": [{"var": "result"}, {"op": "+", "args": [{"call": {"fun": "count", "args": [{"var": "s"}]}}, {"int": 1}]}]}, task["ensures"][0]
    assert "quantifier-eliminated" in _rules(rec)


# A range read through a predicate's body (vericoding DA0128
# ValidRectangleCorner): the call stays in the body.
THROUGH_PREDICATE = """
predicate ValidCorner(k: int, m: int)
{
  0 <= k <= m && k % 2 == 0
}

function Value(k: int, m: int): int
{
  k * m
}

method Best(m: int) returns (result: int)
  requires m >= 0
  ensures forall k: int :: ValidCorner(k, m) ==> result >= Value(k, m)
{
  result := m * m;
}
"""


def test_range_through_predicate() -> None:
    task, rec, _m, _v = _lift_one(THROUGH_PREDICATE, "Best")
    (q,) = _quants(task["ensures"], "forall")
    assert q["lo"] == {"int": 0} and q["hi"] == {"op": "+", "args": [{"var": "m"}, {"int": 1}]}, q
    assert q["body"]["op"] == "implies" and "call" in q["body"]["args"][0], q["body"]
    assert "quantifier-bounded-predicate" in _rules(rec)


# Truly unbounded quantifiers stay refused by name.
UNBOUNDED_POWER = """
function power(n: int, y: nat): int
  decreases y
{
  if y == 0 then 1 else n * power(n, y - 1)
}

method IsSimplePower(x: int, n: int) returns (ans: bool)
  ensures ans <==> exists y: nat :: x == power(n, y)
{
  ans := false;
}
"""

UNBOUNDED_PRODUCT = """
method Factors(x: int) returns (ans: bool)
  ensures ans <==> exists a: int, b: int :: a > 0 && b > 0 && x == a * b
{
  ans := false;
}
"""

UNBOUNDED_LOWER_ONLY = """
method Above(x: int) returns (ans: bool)
  ensures ans <==> forall y: int :: y > x ==> y > 0
{
  ans := x >= 0;
}
"""


def test_truly_unbounded_stays_refused() -> None:
    for src, m in ((UNBOUNDED_POWER, "IsSimplePower"), (UNBOUNDED_PRODUCT, "Factors"),
                   (UNBOUNDED_LOWER_ONLY, "Above")):
        v = _classify_one(src, m)
        assert not isinstance(v, C.Liftable) and v.reason == "unbounded-quantifier", (m, v)


def _check_end_to_end(src: str, method_name: str) -> None:
    task, rec, method, plan = _lift_one(src, method_name)
    with tempfile.TemporaryDirectory() as d:
        out = lift_check.check(task, method, plan.closure, rec, Path(d) / "unit.check.dfy", 240.0)
    assert out.refusal is None, (out.refusal, rec.checker_verdicts)


def test_check_stage(slow: bool) -> None:
    """The check stage under dafny proves each lifted quantifier equivalent
    to its source (L_ens): the `>=` style, the nat binder, the membership
    conjunct, the chains, the pinned binder and the predicate range."""
    if not slow:
        print("test_check_stage: skipped (pass --slow)")
        return
    for src, m in ((GE_STYLE, "GetPositive"), (NAT_BINDER, "FirstZero"),
                   (MEMBERSHIP_AMONG, "UniqueDigits"), (CHAINS, "Nested"),
                   (PINNED, "Solve"), (THROUGH_PREDICATE, "Best")):
        _check_end_to_end(src, m)
        print(f"test_check_stage: {m} ok")


def run(slow: bool = False) -> None:
    test_ge_style_range()
    test_nat_binder_upper_bound_only()
    test_membership_among_conjuncts()
    test_chain_with_several_binders()
    test_pinned_binder_eliminates_quantifier()
    test_range_through_predicate()
    test_truly_unbounded_stays_refused()
    test_check_stage(slow)
    print("test_lift_quant_bounds: ok")


if __name__ == "__main__":
    run("--slow" in sys.argv[1:])
