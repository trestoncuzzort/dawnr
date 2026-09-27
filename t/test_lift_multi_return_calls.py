#!/usr/bin/env python3
"""test_lift_multi_return_calls.py: t/FEATURES-TRACK.md feature 6
(2026-09-27), LIFTER-DECISIONS row 41 -- a call of a two-out-parameter
method, `a, b := M(x);` or `var a, b := M(x);` (Dafny Reference Manual
8.5.2), lifts: the callee is a pair-returning t method (row 29's mapping of
two returns), the call binds the pair to a fresh local as the whole
right-hand side of its `var` init (SPEC.md "Methods (v1)"), and the two
names are its projections. No prover for the rewrite tests; `--slow` (or
pytest's `--slow`) runs the check stage under dafny, callee and caller.

Run: python3 t/test_lift_multi_return_calls.py [--slow]   (or pytest)
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


TWO = """
method Two(x: int) returns (a: int, b: int)
  ensures a == x && b == x + 1
{
  a := x;
  b := x + 1;
}
"""

VAR_FORM = TWO + """
method Caller(x: int) returns (r: int)
  ensures r == 2 * x + 1
{
  var a, b := Two(x);
  r := a + b;
}
"""

ASSIGN_FORM = TWO + """
method Caller(x: int) returns (r: int)
  ensures r == 2 * x + 1
{
  var a := 0;
  var b := 0;
  a, b := Two(x);
  r := a + b;
}
"""

SEQ_COMPONENT = """
method Split(s: seq<int>) returns (n: int, t: seq<int>)
  requires |s| > 0
  ensures n == s[0] && t == s[1..]
{
  n := s[0];
  t := s[1..];
}
method Head(s: seq<int>) returns (r: int)
  requires |s| > 0
  ensures r == s[0] + |s| - 1
{
  var h, rest := Split(s);
  r := h + |rest|;
}
"""


def _pair_local(task: dict) -> dict:
    (p,) = [s["var"] for s in task["body"] if "var" in s and isinstance(s["var"]["type"], dict)]
    return p


def test_var_form() -> None:
    rr, _m, _v = _lift_one(VAR_FORM, "Caller")
    task = rr.task
    (m,) = task["methods"]
    assert m["returns"][0]["type"] == {"pair": ["int", "int"]}, m["returns"]
    p = _pair_local(task)
    assert p["type"] == {"pair": ["int", "int"]} and p["init"] == {"call": {"fun": m["name"], "args": [{"var": "x"}]}}, p
    inits = [s["var"]["init"] for s in task["body"] if "var" in s and s["var"]["name"] in ("a", "b")]
    assert inits == [{"op": "fst", "args": [{"var": p["name"]}]}, {"op": "snd", "args": [{"var": p["name"]}]}], inits
    assert "multi-return-call-destructured" in {w.rule for w in rr.record.rewrites}
    ref = interp.Reference(task)
    assert ref.points and all(v == 2 * env["x"] + 1 for env, v in ref.points), ref.points[:3]


def test_assign_form() -> None:
    rr, _m, _v = _lift_one(ASSIGN_FORM, "Caller")
    task = rr.task
    p = _pair_local(task)
    assigns = [s["assign"] for s in task["body"] if "assign" in s and s["assign"][0] in ("a", "b")]
    assert assigns == [["a", {"op": "fst", "args": [{"var": p["name"]}]}],
                       ["b", {"op": "snd", "args": [{"var": p["name"]}]}]], assigns
    ref = interp.Reference(task)
    assert ref.points and all(v == 2 * env["x"] + 1 for env, v in ref.points), ref.points[:3]


def test_seq_component_typed_from_the_callee() -> None:
    rr, _m, _v = _lift_one(SEQ_COMPONENT, "Head")
    task = rr.task
    p = _pair_local(task)
    assert p["type"] == {"pair": ["int", "seq"]}, p
    rest = next(s["var"] for s in task["body"] if "var" in s and s["var"]["name"] == "rest")
    assert rest["type"] == "seq", rest
    ref = interp.Reference(task)
    assert ref.points and all(v == env["s"][0] + len(env["s"]) - 1 for env, v in ref.points), ref.points[:3]


THREE = """
method Three(x: int) returns (a: int, b: int, c: int)
  ensures a == x && b == x && c == x
{
  a := x; b := x; c := x;
}
method Caller(x: int) returns (r: int)
  ensures r == 3 * x
{
  var a, b, c := Three(x);
  r := a + b + c;
}
"""

SELF_DESTRUCTURE = """
method Twice(n: nat) returns (a: int, b: int)
  ensures a == n && b == n
  decreases n
{
  if n == 0 { a := 0; b := 0; }
  else { var p, q := Twice(n - 1); a := p + 1; b := q + 1; }
}
"""

INDEX_TARGET = TWO + """
method Caller(x: int) returns (r: seq<int>)
  ensures |r| == 1
{
  var b := 0;
  r := [0];
  r := r[0 := x];
  b, b := Two(x);
}
"""


def test_uncovered_shapes_stay_refused() -> None:
    v = _classify_one(THREE, "Caller")
    assert not isinstance(v, C.Liftable) and v.reason == "method-call-multi-return", v
    v = _classify_one(SELF_DESTRUCTURE, "Twice")
    assert not isinstance(v, C.Liftable) and v.reason == "multi-return-nested", v


def _check_end_to_end(src: str, method_name: str) -> None:
    rr, method, plan = _lift_one(src, method_name)
    with tempfile.TemporaryDirectory() as d:
        out = lift_check.check(rr.task, method, plan.closure, rr.record, Path(d) / "unit.check.dfy",
                               240.0, callees=rr.callees)
    assert out.refusal is None, (out.refusal, rr.record.checker_verdicts)


def test_check_stage(slow: bool) -> None:
    """The check stage under dafny: the callee's own lemmas and differential
    run (its pair return), then the caller's."""
    if not slow:
        print("test_check_stage: skipped (pass --slow)")
        return
    for src, m in ((VAR_FORM, "Caller"), (ASSIGN_FORM, "Caller"), (SEQ_COMPONENT, "Head")):
        _check_end_to_end(src, m)
        print(f"test_check_stage: {m} ok")


def run(slow: bool = False) -> None:
    test_var_form()
    test_assign_form()
    test_seq_component_typed_from_the_callee()
    test_uncovered_shapes_stay_refused()
    test_check_stage(slow)
    print("test_lift_multi_return_calls: ok")


if __name__ == "__main__":
    run("--slow" in sys.argv[1:])
