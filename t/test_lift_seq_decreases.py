#!/usr/bin/env python3
"""test_lift_seq_decreases.py: t/FEATURES-TRACK.md feature 3 (2026-09-27),
LIFTER-DECISIONS row 39 -- a Dafny `decreases` whose component is a
SEQUENCE (Dafny's default measure for a function over a `seq`, or a stated
`decreases s`; likewise a loop that shrinks a seq local) lifts as
`len(component)`, the int measure t requires (SPEC.md gate 3; check_wf's
`spec-fun-decreases-int`), recorded `decreases-seq-length`. No prover for
the rewrite tests; `--slow` (or pytest's `--slow`) also runs the check
stage under dafny on each fixture, which is where the `|s|` side of the
L_dec/L_fun lemmas is exercised.

Run: python3 t/test_lift_seq_decreases.py [--slow]   (or pytest)
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


def _rules(record) -> list:
    return [w.rule for w in record.rewrites]


def _len_of(name: str) -> dict:
    return {"op": "len", "args": [{"var": name}]}


# A stated `decreases s` on a function over a sequence (what dafny's rprint
# also prints for a function that states none), and a loop that shrinks a
# seq local under `decreases t`. The local is typed as rprint always types
# it (LIFTER-DESIGN.md section 1, item 2); the checker's lemma parameters
# read a local's declared type.
STATED = """
function Sum(s: seq<int>): int
  decreases s
{
  if |s| == 0 then 0 else s[0] + Sum(s[1..])
}

method Total(s: seq<int>) returns (r: int)
  ensures r == Sum(s)
{
  r := 0;
  var t: seq<int> := s;
  while |t| > 0
    invariant r + Sum(t) == Sum(s)
    decreases t
  {
    r := r + t[0];
    t := t[1..];
  }
}
"""


def test_seq_measure_lifts_as_len() -> None:
    task, rec, _m, _plan = _lift_one(STATED, "Total")
    funs = {f["name"]: f for f in task["spec_funs"]}
    assert len(funs) == 1
    (f,) = funs.values()
    assert f["decreases"] == _len_of(f["params"][0]["name"]), f["decreases"]
    loop = next(s for s in task["body"] if "while" in s)["while"]
    assert loop["decreases"]["op"] == "len", loop["decreases"]
    assert _rules(rec).count("decreases-seq-length") == 2, _rules(rec)
    assert rec.decreases_origin.get("Sum") == "stated"


# A tuple measure whose seq component shrinks while the int one is passed
# through unchanged: projected (decision 11) to the seq, then to its length.
PROJECTED = """
function Count(s: seq<int>, k: int): int
  decreases s, k
{
  if |s| == 0 then 0 else (if s[0] == k then 1 else 0) + Count(s[1..], k)
}

method Occurrences(s: seq<int>, k: int) returns (r: int)
  ensures r == Count(s, k)
{
  r := Count(s, k);
}
"""


def test_projected_seq_component_lifts_as_len() -> None:
    task, rec, _m, _plan = _lift_one(PROJECTED, "Occurrences")
    (f,) = task["spec_funs"]
    assert f["decreases"] == _len_of(f["params"][0]["name"]), f["decreases"]
    assert "decreases-tuple-reduced" in _rules(rec)
    assert "decreases-seq-length" in _rules(rec)
    assert rec.decreases_origin.get("Count") == "projected"


# Both components change: the sum guess (decision 11), each seq component by
# its length, so the guess is still an int.
SUMMED = """
function Both(s: seq<int>, k: int): int
  decreases s, k
{
  if |s| == 0 || k <= 0 then 0 else s[0] + Both(s[1..], k - 1)
}

method UseBoth(s: seq<int>, k: int) returns (r: int)
  ensures r == Both(s, k)
{
  r := Both(s, k);
}
"""


def test_summed_measure_wraps_seq_component() -> None:
    task, rec, _m, _plan = _lift_one(SUMMED, "UseBoth")
    (f,) = task["spec_funs"]
    s_name, k_name = f["params"][0]["name"], f["params"][1]["name"]
    assert f["decreases"] == {"op": "+", "args": [_len_of(s_name), {"var": k_name}]}, f["decreases"]
    assert "guess:sum" in _rules(rec) and "decreases-seq-length" in _rules(rec)


# An int measure is untouched: no `len`, no `decreases-seq-length`.
INT_MEASURE = """
function Fact(n: nat): nat
  decreases n
{
  if n == 0 then 1 else n * Fact(n - 1)
}

method Factorial(n: nat) returns (r: nat)
  ensures r == Fact(n)
{
  r := Fact(n);
}
"""


def test_int_measure_unchanged() -> None:
    task, rec, _m, _plan = _lift_one(INT_MEASURE, "Factorial")
    (f,) = task["spec_funs"]
    assert f["decreases"] == {"var": f["params"][0]["name"]}, f["decreases"]
    assert "decreases-seq-length" not in _rules(rec)


def _check_end_to_end(src: str, method_name: str) -> None:
    task, rec, method, plan = _lift_one(src, method_name)
    with tempfile.TemporaryDirectory() as d:
        out = lift_check.check(task, method, plan.closure, rec, Path(d) / "unit.check.dfy", 240.0)
    assert out.refusal is None, (out.refusal, rec.checker_verdicts)


def test_check_stage_stated(slow: bool) -> None:
    """The check stage under dafny: L_fun_Sum inducts by `|s|`, the loop's
    L_dec compares `|t|` with the lifted `len(t)`, and the differential
    run agrees. Before this feature the task was refused
    `check-wf-failed: spec_fun ... decreases is not int`."""
    if not slow:
        print("test_check_stage_stated: skipped (pass --slow)")
        return
    _check_end_to_end(STATED, "Total")


def test_check_stage_projected(slow: bool) -> None:
    if not slow:
        print("test_check_stage_projected: skipped (pass --slow)")
        return
    _check_end_to_end(PROJECTED, "Occurrences")


def run(slow: bool = False) -> None:
    test_seq_measure_lifts_as_len()
    test_projected_seq_component_lifts_as_len()
    test_summed_measure_wraps_seq_component()
    test_int_measure_unchanged()
    test_check_stage_stated(slow)
    test_check_stage_projected(slow)
    print("test_lift_seq_decreases: ok")


if __name__ == "__main__":
    run("--slow" in sys.argv[1:])
