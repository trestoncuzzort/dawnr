#!/usr/bin/env python3
"""test_lift_nested_strings.py: LIFTER-DECISIONS row 43 (2026-09-27,
t/FEATURES-TRACK.md, nested string sequences) -- a Dafny `seq<string>` (or
`seq<seq<char>>`) parameter, return, local or display lifts as t's nested
seq (SPEC.md "Nested sequences (v1)") whose rows are code points (row 28's
string-as-seq, applied per row): no new t construct. A `seq<string>`
parameter gets the per-row code-point range requires the differential
harness needs; `xs[i][j]` is a char (its `as int` is the identity, `+` on it
still refuses `char-arith`); a display of strings is a nested literal;
three levels (`seq<seq<string>>`) still refuse by name. No prover for the
rewrite tests; `--slow` runs the check stage under dafny.

Run: python3 t/test_lift_nested_strings.py [--slow]   (or pytest)
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


FILTER_BY_PREFIX = """
method FilterByPrefix(xs: seq<string>, p: string) returns (filtered: seq<string>)
  ensures |filtered| <= |xs|
  ensures forall i :: 0 <= i < |filtered| ==> |filtered[i]| >= |p|
{
  filtered := [];
  var i := 0;
  while i < |xs|
    invariant 0 <= i <= |xs|
    invariant |filtered| <= i
    invariant forall k :: 0 <= k < |filtered| ==> |filtered[k]| >= |p|
    decreases |xs| - i
  {
    if |xs[i]| >= |p| && xs[i][..|p|] == p {
      filtered := filtered + [xs[i]];
    }
    i := i + 1;
  }
}
"""


def test_seq_of_string_param_and_return_lift_as_nested_seq() -> None:
    rr, _m, _v = _lift_one(FILTER_BY_PREFIX, "FilterByPrefix")
    task = rr.task
    assert task["params"][0]["type"] == {"seq": "seq"}, task["params"]
    assert task["params"][1]["type"] == "seq"
    assert task["returns"][0]["type"] == {"seq": "seq"}
    assert "strings-elements-requires" in _rules(rr)
    assert "string-elements-requires" in _rules(rr)
    # the per-row code-point bound is a nested forall over the rows
    outer = [r for r in task["requires"] if "forall" in r and "forall" in r["forall"]["body"]]
    assert outer, task["requires"]
    inner = outer[0]["forall"]["body"]["forall"]
    assert inner["hi"] == {"op": "len", "args": [{"op": "at", "args": [
        {"var": task["params"][0]["name"]}, {"var": outer[0]["forall"]["var"]}]}]}
    # the interpreter draws nested points that satisfy the lifted requires
    ref = interp.Reference(task)
    assert ref.points, "no points"
    env0, _ = ref.points[-1]
    assert isinstance(env0[task["params"][0]["name"]], (list, tuple))
    print("test_seq_of_string_param_and_return_lift_as_nested_seq: ok")


STRING_ROWS_LOCAL = """
method Names() returns (r: int)
  ensures r == 2
{
  var xs: seq<string> := ["ab", "c"];
  r := |xs|;
}
"""


def test_string_display_is_a_nested_literal() -> None:
    rr, _m, _v = _lift_one(STRING_ROWS_LOCAL, "Names")
    decl = rr.task["body"][0]["var"]
    assert decl["type"] == {"seq": "seq"}, decl
    assert decl["init"] == {"op": "seq", "args": [
        {"op": "seq", "args": [{"int": 97}, {"int": 98}]},
        {"op": "seq", "args": [{"int": 99}]}]}, decl["init"]
    assert "string-literal-lifted" in _rules(rr)
    print("test_string_display_is_a_nested_literal: ok")


UNTYPED_STRING_ROWS = """
method Untyped() returns (r: int)
  ensures r == 1
{
  var xs := ["x"];
  r := |xs|;
}
"""


def test_untyped_local_of_string_rows_is_nested() -> None:
    rr, _m, _v = _lift_one(UNTYPED_STRING_ROWS, "Untyped")
    assert rr.task["body"][0]["var"]["type"] == {"seq": "seq"}, rr.task["body"][0]
    print("test_untyped_local_of_string_rows_is_nested: ok")


ROW_CHAR = """
method FirstCode(xs: seq<string>) returns (r: int)
  requires |xs| > 0 && |xs[0]| > 0
  ensures r == xs[0][0] as int
{
  r := xs[0][0] as int;
}
"""


def test_row_element_is_a_char() -> None:
    rr, _m, _v = _lift_one(ROW_CHAR, "FirstCode")
    assert "char-as-int-lifted" in _rules(rr)
    body = rr.task["body"][0]
    assign = body["assign"] if "assign" in body else body["return"]
    assert assign[1] == {"op": "at", "args": [
        {"op": "at", "args": [{"var": rr.task["params"][0]["name"]}, {"int": 0}]}, {"int": 0}]}
    print("test_row_element_is_a_char: ok")


ROW_CHAR_ARITH = """
method Shift(xs: seq<string>) returns (r: char)
  requires |xs| > 0 && |xs[0]| > 0
  ensures true
{
  r := xs[0][0] + 'a';
}
"""


def test_row_char_arithmetic_still_refuses() -> None:
    _mod, _m, v = _classify_one(ROW_CHAR_ARITH, "Shift")
    assert not isinstance(v, C.Liftable) and v.reason == "char-arith", v
    print("test_row_char_arithmetic_still_refuses: ok")


THREE_DEEP = """
method Deep(xs: seq<seq<string>>) returns (r: int)
  ensures true
{
  r := 0;
}
"""


def test_three_levels_still_refuse() -> None:
    _mod, _m, v = _classify_one(THREE_DEEP, "Deep")
    assert not isinstance(v, C.Liftable) and v.reason == "nested-seq-deep", v
    print("test_three_levels_still_refuse: ok")


MEMBERSHIP = """
method Answer(b: bool) returns (r: string)
  ensures r in ["Yes", "No"]
{
  if b { r := "Yes"; } else { r := "No"; }
}
"""


def test_membership_in_a_display_of_strings() -> None:
    rr, _m, _v = _lift_one(MEMBERSHIP, "Answer")
    assert "in-desugared" in _rules(rr)
    print("test_membership_in_a_display_of_strings: ok")


def _check_end_to_end(src: str, method_name: str) -> None:
    rr, method, plan = _lift_one(src, method_name)
    with tempfile.TemporaryDirectory() as d:
        out = lift_check.check(rr.task, method, plan.closure, rr.record, Path(d) / "unit.check.dfy",
                               240.0, callees=rr.callees)
    assert out.refusal is None, (out.refusal, rr.record.checker_verdicts, rr.record.warnings)
    dv = str(rr.record.differential_verdict)
    # the differential arm needs `dafny run` (a dotnet build); where the
    # machine has no dotnet the arm reads `arm-unavailable`, never a pass
    # and never a refusal, and only the lemma verdicts above were measured
    assert dv.startswith("arm-unavailable") or dv not in ("None", "timeout"), dv
    print(f"    differential: {dv[:80]}")


def test_check_stage(slow: bool) -> None:
    if not slow:
        print("test_check_stage: skipped (pass --slow)")
        return
    for src, m in ((FILTER_BY_PREFIX, "FilterByPrefix"), (STRING_ROWS_LOCAL, "Names"),
                   (ROW_CHAR, "FirstCode"), (MEMBERSHIP, "Answer")):
        _check_end_to_end(src, m)
        print(f"test_check_stage: {m} ok")


def run(slow: bool = False) -> None:
    test_seq_of_string_param_and_return_lift_as_nested_seq()
    test_string_display_is_a_nested_literal()
    test_untyped_local_of_string_rows_is_nested()
    test_row_element_is_a_char()
    test_row_char_arithmetic_still_refuses()
    test_three_levels_still_refuse()
    test_membership_in_a_display_of_strings()
    test_check_stage(slow)
    print("test_lift_nested_strings: ok")


if __name__ == "__main__":
    run("--slow" in sys.argv[1:])
