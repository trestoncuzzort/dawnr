#!/usr/bin/env python3
"""test_lift_return_default.py: LIFTER-DECISIONS row 45 (2026-09-27,
t/FEATURES-TRACK.md, return default) -- a method whose out-parameter section
4.7's syntactic walk (`_assigns_ret_all_paths`) cannot see assigned on every
path is no longer refused `return-not-assigned-on-all-paths`: the body opens
with the return type's default (`return-default-init`: 0, false, [], a pair
of those), and the check stage keeps the task only where dafny's own
definite-assignment check accepts the source method (`verify-source`), else
refuses `return-default-unverified`. A `char` return refuses
`return-default-char`. No prover for the rewrite tests; `--slow` runs the
check stage under dafny on a source dafny accepts and one it does not.

Run: python3 t/test_lift_return_default.py [--slow]   (or pytest)
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


def _lift_one(src: str, method_name: str, source_path: str = "unit.dfy"):
    mod, method, v = _classify_one(src, method_name)
    assert isinstance(v, C.Liftable), f"expected liftable, got refusal: {v}"
    rr = R.rewrite(mod, v, source_path, "sha")
    assert rr.refusal is None, rr.refusal
    errs = check_wf.check_wf(rr.task)
    assert errs == [], errs
    return rr, method, v


def _rules(rr) -> set:
    return {rw.rule for rw in rr.record.rewrites}


# Dafny 4.11.0 accepts this (definite assignment is a verification
# obligation: the loop exits only through the assigning `return`), the
# syntactic walk does not (a while body is never counted).
WHILE_TRUE = """
method FirstAtLeast(x: int) returns (r: int)
  ensures r >= 0 && r >= x
{
  var i := 0;
  while true
    invariant i >= 0
    decreases x - i
  {
    if i >= x { r := i; return; }
    i := i + 1;
  }
}
"""


def test_int_return_opens_with_zero() -> None:
    rr, _m, v = _lift_one(WHILE_TRUE, "FirstAtLeast")
    assert v.ret_default == "r"
    r = rr.task["returns"][0]["name"]
    assert rr.task["body"][0] == {"assign": [r, {"int": 0}]}, rr.task["body"][0]
    assert "return-default-init" in _rules(rr)
    assert any(c.rule == "return-default-init" for c in rr.record.clauses_added)
    ref = interp.Reference(rr.task)
    assert ref.points
    print("test_int_return_opens_with_zero: ok")


# Dafny 4.11.0 refuses this one ("out-parameter 'r' ... might be
# uninitialized at this return point"): the rewrite still lifts it, and the
# check stage's verify-source step is what refuses it.
IF_ONLY = """
method IfOnly(x: int) returns (r: int)
  ensures x > 0 ==> r == x
{
  if x > 0 { r := x; }
}
"""

SEQ_IF = """
method SeqIf(b: bool) returns (s: seq<int>)
  ensures b ==> |s| == 1
{
  if b { s := [1]; }
}
"""

STR_IF = """
method StrIf(b: bool) returns (s: string)
  ensures b ==> |s| == 1
{
  if b { s := "a"; }
}
"""

BOOL_IF = """
method BoolIf(b: bool) returns (c: bool)
  ensures b ==> c
{
  if b { c := true; }
}
"""

NAT_IF = """
method NatIf(b: bool, n: nat) returns (c: nat)
  ensures b ==> c == n
{
  if b { c := n; }
}
"""

TUPLE_IF = """
method TupIf(b: bool) returns (p: (int, bool))
  ensures b ==> p.0 == 1
{
  if b { p := (1, true); }
}
"""

NESTED_IF = """
method NestedIf(b: bool) returns (m: seq<seq<int>>)
  ensures b ==> |m| == 1
{
  if b { m := [[1, 2]]; }
}
"""


def test_every_defaultable_type() -> None:
    cases = [
        (IF_ONLY, "IfOnly", {"int": 0}),
        (SEQ_IF, "SeqIf", {"op": "seq", "args": []}),
        (STR_IF, "StrIf", {"op": "seq", "args": []}),
        (BOOL_IF, "BoolIf", {"bool": False}),
        (NAT_IF, "NatIf", {"int": 0}),
        (TUPLE_IF, "TupIf", {"op": "pair", "args": [{"int": 0}, {"bool": False}]}),
        (NESTED_IF, "NestedIf", {"op": "seq", "args": []}),
    ]
    for src, m, default in cases:
        rr, _m, _v = _lift_one(src, m)
        r = rr.task["returns"][0]["name"]
        assert rr.task["body"][0] == {"assign": [r, default]}, (m, rr.task["body"][0])
        assert "return-default-init" in _rules(rr)
        assert interp.Reference(rr.task).points, m
    print("test_every_defaultable_type: ok")


PAIR_IF = """
method PairIf(b: bool) returns (a: int, c: bool)
  ensures b ==> a == 1 && c
{
  if b { a := 1; c := true; }
}
"""


def test_pair_components_keep_their_default_init() -> None:
    rr, _m, v = _lift_one(PAIR_IF, "PairIf")
    assert v.ret_default == "a"
    assert {"default-init", "return-default-init"} <= _rules(rr)
    # the two locals open the body; no third default assignment is added
    assert [list(s)[0] for s in rr.task["body"][:2]] == ["var", "var"]
    assert not any("assign" in s and s["assign"][1] in ({"int": 0}, {"bool": False})
                   for s in rr.task["body"][2:-1])
    print("test_pair_components_keep_their_default_init: ok")


ASSIGNED = """
method Assigned(x: int) returns (r: int)
  ensures r >= 0
{
  if x >= 0 { r := x; } else { r := -x; }
}
"""


def test_assigned_everywhere_is_untouched() -> None:
    rr, _m, v = _lift_one(ASSIGNED, "Assigned")
    assert v.ret_default is None
    assert "return-default-init" not in _rules(rr)
    assert list(rr.task["body"][0])[0] == "if"
    print("test_assigned_everywhere_is_untouched: ok")


CHAR_IF = """
method CharIf(b: bool) returns (c: char)
  ensures b ==> c == 'a'
{
  if b { c := 'a'; }
}
"""


def test_char_return_refuses_by_name() -> None:
    _mod, _m, v = _classify_one(CHAR_IF, "CharIf")
    assert not isinstance(v, C.Liftable) and v.reason == "return-default-char", v
    print("test_char_return_refuses_by_name: ok")


def test_no_source_file_refuses_at_check() -> None:
    """The verify-source step never trusts a placeholder path."""
    ok, code, token = lift_check._verify_source_method(Path("unit.dfy"), "IfOnly", 5.0)
    assert (ok, code, token) == (False, -1, "no-source")
    print("test_no_source_file_refuses_at_check: ok")


def _check_end_to_end(src: str, method_name: str, expect_refusal):
    with tempfile.TemporaryDirectory() as d:
        src_path = Path(d) / f"{method_name}.dfy"
        src_path.write_text(src, encoding="utf-8")
        rr, method, plan = _lift_one(src, method_name, str(src_path))
        out = lift_check.check(rr.task, method, plan.closure, rr.record, Path(d) / "unit.check.dfy",
                               240.0, callees=rr.callees)
    if expect_refusal is None:
        assert out.refusal is None, (out.refusal, rr.record.checker_verdicts, rr.record.warnings)
        assert rr.record.dafny_exit_codes.get("verify-source") == 0
        dv = str(rr.record.differential_verdict)
        assert dv.startswith("arm-unavailable") or dv not in ("None", "timeout"), dv
    else:
        assert out.refusal is not None and out.refusal.reason == expect_refusal, out.refusal
        assert rr.record.dafny_exit_codes.get("verify-source") == 4, rr.record.dafny_exit_codes
    return out


def test_check_stage(slow: bool) -> None:
    if not slow:
        print("test_check_stage: skipped (pass --slow)")
        return
    _check_end_to_end(WHILE_TRUE, "FirstAtLeast", None)
    print("test_check_stage: FirstAtLeast checked (dafny accepts the source)")
    out = _check_end_to_end(IF_ONLY, "IfOnly", "return-default-unverified")
    assert "might be uninitialized" in out.refusal.token, out.refusal.token
    print("test_check_stage: IfOnly refused return-default-unverified")


def run(slow: bool = False) -> None:
    test_int_return_opens_with_zero()
    test_every_defaultable_type()
    test_pair_components_keep_their_default_init()
    test_assigned_everywhere_is_untouched()
    test_char_return_refuses_by_name()
    test_no_source_file_refuses_at_check()
    test_check_stage(slow)
    print("test_lift_return_default: ok")


if __name__ == "__main__":
    run("--slow" in sys.argv[1:])
