#!/usr/bin/env python3
"""test_lift_datatypes.py: LIFTER-DECISIONS row 48 (2026-09-27, t/FEATURES-TRACK.md,
datatypes) -- the old blanket `datatype` refusal is split by what the method
actually touches, measured on the 78 methods it covered (42 touched no
datatype). `.0`/`.1` on an indexed element is `seq-of-pair` (row 46's name),
on any other expression `tuple-projection`; `Length0`/`Length1` are `array2`;
`Floor` is `real`; a `Ctor?` discriminator, a field, a datatype-typed
parameter or return is `datatype-<kind>` where the kind is read from the
file's `datatype` declarations (enum, record, sum, real, generic, recursive;
the hardest present when there are several); a member on a file with no
datatype is `member-access`. Nothing lifts: t has no datatype yet.

Run: python3 t/test_lift_datatypes.py [--slow]   (or pytest; --slow runs the check stage under dafny)
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


def _refusal(src: str, method_name: str):
    v = _classify_one(src, method_name)
    assert not isinstance(v, C.Liftable), f"expected a refusal, lifted: {v}"
    return v


SEQ_OF_PAIR = """
method FirstLeft(pairs: seq<(int, int)>) returns (r: int)
  requires |pairs| > 0
  ensures r == pairs[0].0
{
  r := pairs[0].0;
}
"""

TUPLE_PROJECTION = """
method UseFst(x: int) returns (r: int)
  ensures r == x
{
  r := (x, x).0;
}
"""


def test_pair_projections_are_named_by_their_base() -> None:
    v = _refusal(SEQ_OF_PAIR, "FirstLeft")
    assert v.reason == "seq-of-pair", v
    v = _refusal(TUPLE_PROJECTION, "UseFst")
    assert v.reason == "tuple-projection", v
    print("test_pair_projections_are_named_by_their_base: ok")


ARRAY2 = """
method Rows(a: array2<int>) returns (r: int)
  ensures r == a.Length0
{
  r := a.Length0;
}
"""

FLOOR = """
method Whole(x: real) returns (r: bool)
  ensures r == (x == x.Floor as real)
{
  r := x == x.Floor as real;
}
"""


def test_array2_and_floor_members_take_their_own_names() -> None:
    v = _refusal(ARRAY2, "Rows")
    assert v.reason == "array2", v
    v = _refusal(FLOOR, "Whole")
    assert v.reason == "real", v
    print("test_array2_and_floor_members_take_their_own_names: ok")


ENUM = """
datatype Color = Red | Green | Blue
method IsRed(c: Color) returns (r: bool)
  ensures r == c.Red?
{
  r := c.Red?;
}
"""

RECORD = """
datatype Point = Point(x: int, y: int)
method X(p: Point) returns (r: int)
  ensures r == p.x
{
  r := p.x;
}
"""

SUM = """
datatype Result = Ok(v: int) | Err(code: int)
method Get(x: int) returns (r: int)
  ensures r >= 0
{
  var res := Ok(x);
  r := if res.Ok? then 0 else 1;
}
"""

REAL_SUM = """
datatype Float = Finite(value: real) | NaN | PosInf
method IsNaN(f: Float) returns (r: bool)
  ensures r == f.NaN?
{
  r := f.NaN?;
}
"""

GENERIC = """
datatype Option<T> = None | Some(value: T)
method Has(x: int) returns (r: bool)
  ensures r
{
  var o := Some(x);
  r := o.Some?;
}
"""

GENERIC_PARAM = """
datatype Option<T> = None | Some(value: T)
method HasP(o: Option<int>) returns (r: bool)
  ensures r == o.Some?
{
  r := o.Some?;
}
"""

RECURSIVE = """
datatype List = Nil | Cons(head: int, tail: List)
method IsNil(l: List) returns (r: bool)
  ensures r == l.Nil?
{
  r := l.Nil?;
}
"""

MIXED = """
datatype TimeUnit = Years | Days | Hours
datatype Delta = Delta(value: int, unit: TimeUnit)
method Unit(d: Delta) returns (r: bool)
  ensures r == d.unit.Days?
{
  r := d.unit.Days?;
}
"""


def test_datatype_shapes_are_named() -> None:
    for src, m, kind in ((ENUM, "IsRed", "enum"), (RECORD, "X", "record"), (SUM, "Get", "sum"),
                         (REAL_SUM, "IsNaN", "real"), (GENERIC, "Has", "generic"),
                         (RECURSIVE, "IsNil", "recursive"), (MIXED, "Unit", "record")):
        v = _refusal(src, m)
        assert v.reason == f"datatype-{kind}", (m, v)
    # a parameter whose type is itself instantiated generic keeps the older,
    # equally exact `generics` name (row 30's `_type_issue`)
    v = _refusal(GENERIC_PARAM, "HasP")
    assert v.reason == "generics", v
    print("test_datatype_shapes_are_named: ok")


NO_DATATYPE = """
class Cell { var v: int }
method Read(c: Cell) returns (r: int)
  ensures r == c.v
{
  r := c.v;
}
"""


def test_member_on_a_file_without_datatypes() -> None:
    v = _refusal(NO_DATATYPE, "Read")
    assert v.reason == "type-decl", v  # class, trait, type, newtype all share the gap name
    v = _refusal(NO_DATATYPE.replace("class Cell { var v: int }", "type Cell"), "Read")
    assert v.reason == "type-decl", v
    print(f"test_member_on_a_file_without_datatypes: ok ({v.reason})")


def test_kind_order_is_hardest_first() -> None:
    mod = lift_parse.parse(MIXED)
    assert C._datatype_kind(mod) == "record"
    mod = lift_parse.parse(RECURSIVE + GENERIC.replace("Option", "Opt"))
    assert C._datatype_kind(mod) == "recursive"
    assert C._datatype_kind(lift_parse.parse(NO_DATATYPE)) is None
    print("test_kind_order_is_hardest_first: ok")


MATCH_INT = """
function Fib(n: nat): nat {
  match n {
    case 0 => 0
    case 1 => 1
    case _ => Fib(n - 1) + Fib(n - 2)
  }
}
method M(n: nat) returns (r: nat) ensures r == Fib(n) { r := Fib(n); }
"""

MATCH_STRING_STMT = """
method Day(day: string) returns (r: int)
  ensures r >= 0
{
  r := 0;
  match day {
    case "SUN" => r := 7;
    case _ => r := 1;
  }
}
"""

MATCH_CTOR = """
datatype Color = Red | Green
function Code(c: Color): int {
  match c {
    case Red => 0
    case Green => 1
  }
}
method M(c: Color) returns (r: int) ensures r == Code(c) { r := Code(c); }
"""

MATCH_CTOR_ARGS = """
datatype Option = None | Some(v: int)
method Get(o: Option) returns (r: int)
  ensures true
{
  match o {
    case None => r := 0;
    case Some(v) => r := v;
  }
}
"""


RECORD_LOCAL = """
datatype R = R(n: int, ok: bool)
method Local(x: int) returns (r: int)
  ensures r >= 0
{
  var parsed := R(x, x > 0);
  r := if parsed.ok then parsed.n else 0;
}
method Mk(x: int) returns (p: R) ensures true { p := R(x, true); }
method ViaCall(x: int) returns (r: int)
  ensures r >= 0
{
  var parsed := Mk(x);
  r := if parsed.ok then parsed.n else 0;
}
"""


def test_a_datatype_local_is_named_by_shape() -> None:
    v = _refusal(RECORD_LOCAL, "Local")
    assert v.reason == "datatype-record" and v.token == "field ok", v
    v = _refusal(RECORD_LOCAL, "ViaCall")
    assert v.reason == "callee-refused:datatype-record", v
    print("test_a_datatype_local_is_named_by_shape: ok")


MATCH_NO_DEFAULT = """
method Name(n: int) returns (r: int)
  requires 1 <= n <= 2
  ensures r == n
{
  match n {
    case 1 => r := 1;
    case 2 => r := 2;
  }
}
"""

MATCH_STMT = """
method Sign(n: int) returns (r: int)
  ensures n == 0 ==> r == 0
  ensures n == 1 ==> r == 1
  ensures n != 0 && n != 1 ==> r == 2
{
  match n {
    case 0 => r := 0;
    case 1 => r := 1;
    case _ => r := 2;
  }
}
"""

MATCH_EXPR = """
function Small(n: int): int {
  match n
  case 0 => 10
  case -1 => 20
  case _ => 30
}
method UseSmall(n: int) returns (r: int)
  ensures r == Small(n)
{
  r := Small(n);
}
"""


def test_a_match_on_int_literals_with_a_default_is_an_if_chain() -> None:
    import lift_rewrite as R
    import check_wf
    import interp
    mod = lift_parse.parse(MATCH_STMT)
    m = {d.name: d for d in lift_parse.gradable_methods(mod)}["Sign"]
    v = C.classify(mod, m)
    assert isinstance(v, C.Liftable), v
    assert any(rw.rule == "match-literal-if-chain" for rw in v.rewrites), v.rewrites
    rr = R.rewrite(mod, v, "unit.dfy", "sha")
    assert rr.refusal is None, rr.refusal
    assert check_wf.check_wf(rr.task) == []
    assert any(rw.rule == "match-literal-if-chain" for rw in rr.record.rewrites), rr.record.rewrites
    body = rr.task["body"]
    assert "if" in body[-1], body[-1]
    ref = interp.Reference(rr.task)
    assert ref.points
    # the chain is exact on every int: 0 -> 0, 1 -> 1, else 2 (the source's
    # cases in order, `_` last)
    funs = interp.funs_of(rr.task, body)
    r = rr.task["returns"][0]["name"]
    for n, want in ((0, 0), (1, 1), (5, 2), (-3, 2)):
        env = {"n": n}
        interp.exec_body(body, env, funs, interp.St())
        assert env[r] == want, (n, env)
    mod = lift_parse.parse(MATCH_EXPR)
    m = {d.name: d for d in lift_parse.gradable_methods(mod)}["UseSmall"]
    v = C.classify(mod, m)
    assert isinstance(v, C.Liftable), v
    assert any(rw.rule == "match-literal-if-chain" for rw in v.rewrites), v.rewrites
    rr = R.rewrite(mod, v, "unit.dfy", "sha")
    assert rr.refusal is None, rr.refusal
    assert check_wf.check_wf(rr.task) == []
    print("test_a_match_on_int_literals_with_a_default_is_an_if_chain: ok")


def test_match_is_named_by_its_first_pattern() -> None:
    mod = lift_parse.parse(MATCH_INT)  # parses now: an int match with a default
    assert mod.decls
    for src, want in ((MATCH_NO_DEFAULT, "match-no-default"), (MATCH_STRING_STMT, "match-literal"),
                      (MATCH_CTOR, "datatype"), (MATCH_CTOR_ARGS, "datatype")):
        try:
            lift_parse.parse(src)
        except lift_parse.LiftParseError as e:
            assert e.reason == want and e.token == "match", (e.reason, e.token, want)
        else:
            raise AssertionError("match parsed")
    print("test_match_is_named_by_its_first_pattern: ok")


def _check_end_to_end(src: str, method_name: str) -> None:
    import tempfile
    from pathlib import Path
    import lift_check
    import lift_rewrite as R
    mod = lift_parse.parse(src)
    method = {d.name: d for d in lift_parse.gradable_methods(mod)}[method_name]
    plan = C.classify(mod, method)
    assert isinstance(plan, C.Liftable), plan
    rr = R.rewrite(mod, plan, "unit.dfy", "sha")
    assert rr.refusal is None, rr.refusal
    with tempfile.TemporaryDirectory() as d:
        out = lift_check.check(rr.task, method, plan.closure, rr.record, Path(d) / "unit.check.dfy",
                               240.0, callees=rr.callees)
    assert out.refusal is None, (out.refusal, rr.record.checker_verdicts, rr.record.warnings)
    print(f"    {method_name}: {rr.record.checker_verdicts}")


def test_check_stage(slow: bool) -> None:
    """Dafny proves the if-chain body against the source's own clauses (the
    check stage's L_req/L_ens), statement form and expression form."""
    if not slow:
        print("test_check_stage: skipped (pass --slow)")
        return
    for src, m in ((MATCH_STMT, "Sign"), (MATCH_EXPR, "UseSmall")):
        _check_end_to_end(src, m)
        print(f"test_check_stage: {m} ok")


def run(slow: bool = False) -> None:
    test_match_is_named_by_its_first_pattern()
    test_a_match_on_int_literals_with_a_default_is_an_if_chain()
    test_a_datatype_local_is_named_by_shape()
    test_pair_projections_are_named_by_their_base()
    test_array2_and_floor_members_take_their_own_names()
    test_datatype_shapes_are_named()
    test_member_on_a_file_without_datatypes()
    test_kind_order_is_hardest_first()
    test_check_stage(slow)
    print("test_lift_datatypes: ok")


if __name__ == "__main__":
    run("--slow" in sys.argv[1:])
