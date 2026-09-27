#!/usr/bin/env python3
"""test_lift_seq_elements.py: LIFTER-DECISIONS row 46 (2026-09-27,
t/FEATURES-TRACK.md, nested-seq-other) -- a Dafny `seq<X>` whose element X
t has no value for refuses under the ELEMENT's own name (`seq-of-real`,
`seq-of-bitvector`, `seq-of-pair`, `seq-of-datatype`, `seq-of-set`,
`seq-of-map`), one level down too (`seq<seq<real>>`), and a sequence
display refuses by its element (`[i % 3 == 0]` is `seq-of-bool`, `[1.0]`
is `seq-of-real`); a display whose element is a cast to char/int is an
int-kinded row, so `[c as char]` lifts when the cast itself is safe and
refuses `char-cast-unbounded` (the cast pass's own name) when it is not.
`nested-seq-other` is left for a shape none of those names fits. No prover
needed.

Run: python3 t/test_lift_seq_elements.py   (or pytest)
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import check_wf                                                # noqa: E402
import interp                                                  # noqa: E402
import lift_classify as C                                      # noqa: E402
import lift_parse                                              # noqa: E402
import lift_rewrite as R                                       # noqa: E402


def _classify_one(src: str, method_name: str):
    mod = lift_parse.parse(src)
    methods = {m.name: m for m in lift_parse.gradable_methods(mod)}
    return mod, methods[method_name], C.classify(mod, methods[method_name])


def _refuses(src: str, method_name: str, reason: str) -> None:
    _mod, _m, v = _classify_one(src, method_name)
    assert not isinstance(v, C.Liftable) and v.reason == reason, (method_name, v)


SEQ_REAL = """
method Total(xs: seq<real>) returns (r: int)
  ensures r == |xs|
{
  r := |xs|;
}
"""

SEQ_SEQ_REAL = """
method Rows(m: seq<seq<real>>) returns (r: int)
  ensures r == |m|
{
  r := |m|;
}
"""

SEQ_BV = """
method Words(a: seq<bv32>) returns (r: int)
  ensures r == |a|
{
  r := |a|;
}
"""

SEQ_PAIR = """
method Pairs(l: seq<(int, int)>) returns (r: int)
  ensures r == |l|
{
  r := |l|;
}
"""

SEQ_GENERIC = """
method Count<T>(a: seq<T>) returns (r: int)
  ensures r == |a|
{
  r := |a|;
}
"""

SEQ_SET = """
method Sets(a: seq<set<int>>) returns (r: int)
  ensures r == |a|
{
  r := |a|;
}
"""


def test_element_types_refuse_by_name() -> None:
    _refuses(SEQ_REAL, "Total", "seq-of-real")
    _refuses(SEQ_SEQ_REAL, "Rows", "seq-of-real")
    _refuses(SEQ_BV, "Words", "seq-of-bitvector")
    _refuses(SEQ_PAIR, "Pairs", "seq-of-pair")
    _refuses(SEQ_GENERIC, "Count", "seq-of-datatype")
    _refuses(SEQ_SET, "Sets", "seq-of-set")
    print("test_element_types_refuse_by_name: ok")


BOOL_DISPLAY = """
method Flags(n: int) returns (r: int)
  ensures r >= 0
{
  var p := [n % 3 == 0];
  r := |p|;
}
"""

REAL_DISPLAY = """
method Ones() returns (r: int)
  ensures r == 1
{
  var p := [1.0];
  r := |p|;
}
"""

UNBOUNDED_CAST = """
method Digit(n: int) returns (s: string)
  requires 0 <= n < 10
  ensures |s| == 1
{
  s := [('0' as int + n) as char];
}
"""


def test_displays_refuse_by_element() -> None:
    _refuses(BOOL_DISPLAY, "Flags", "seq-of-bool")
    _refuses(REAL_DISPLAY, "Ones", "seq-of-real")
    # the display is an int row now; what refuses is the cast's own bound,
    # by the cast pass's own name, never the seq
    _refuses(UNBOUNDED_CAST, "Digit", "char-cast-unbounded")
    print("test_displays_refuse_by_element: ok")


SAFE_CAST_DISPLAY = """
method Wrap(c: char) returns (s: string)
  ensures |s| == 1
  ensures s[0] == c
{
  s := [(c as int) as char];
}
"""


def test_safe_cast_display_lifts() -> None:
    mod, method, v = _classify_one(SAFE_CAST_DISPLAY, "Wrap")
    assert isinstance(v, C.Liftable), v
    rr = R.rewrite(mod, v, "unit.dfy", "sha")
    assert rr.refusal is None, rr.refusal
    assert check_wf.check_wf(rr.task) == []
    rules = {rw.rule for rw in rr.record.rewrites}
    assert {"seq-literal-lifted", "int-as-char-lifted"} <= rules, rules
    assert interp.Reference(rr.task).points
    print("test_safe_cast_display_lifts: ok")


def run() -> None:
    test_element_types_refuse_by_name()
    test_displays_refuse_by_element()
    test_safe_cast_display_lifts()
    print("test_lift_seq_elements: ok")


if __name__ == "__main__":
    run()
