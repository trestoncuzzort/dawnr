#!/usr/bin/env python3
"""test_lower_fstar_methods.py: SPEC.md "Methods (v1)" in the F* lowering.

Each method becomes its own `Pure` definition carrying its requires and
ensures, proved in the file ahead of the task, and marked
`[@@"opaque_to_smt"]` so a caller knows only the contract (F* tutorial,
"Marking definitions as opaque",
https://fstar-lang.org/tutorial/book/under_the_hood/uth_smt.html). A call
is the application `(m a1 .. an)`: F* makes the caller prove m's requires
at the arguments and gives it m's ensures of the result, Dafny's call rule.
The shapes this lowering cannot express raise NotImplementedError with a
named reason. Kernel verdicts are measured by kgrade/run_par; this file
runs no prover.

Run: python3 t/test_lower_fstar_methods.py   (or pytest)
"""

from __future__ import annotations

import copy
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import harness                                                 # noqa: E402
import surface                                                 # noqa: E402
from lower_fstar import lower                                  # noqa: E402

OPAQUE = '[@@"opaque_to_smt"]\n'
FIXTURES = sorted(glob.glob(os.path.join(HERE, "methods", "*.t")))


def _load(path: str) -> dict:
    return surface.parse_file(os.path.join(HERE, path))


def _raises(task: dict, reason: str) -> None:
    try:
        lower(task, task["body"])
    except NotImplementedError as e:
        assert reason in str(e), str(e)
        return
    raise AssertionError(f"expected NotImplementedError {reason!r}")


def test_every_fixture_lowers_real_and_twin() -> None:
    assert len(FIXTURES) >= 4, FIXTURES
    for f in FIXTURES:
        t = surface.parse_file(f)
        src = lower(t, t["body"])
        body, _op, w = harness.twin_for(t)
        lower(t, body, w)
        name = t["name"]
        task_at = src.index(f"\nlet {name} ")
        # every method is opaque, defined before the task, the task is not
        for m in t["methods"]:
            mn = m["name"]
            head = (f"{OPAQUE}let rec {mn} " if "decreases" in m
                    else f"{OPAQUE}let {mn} ")
            assert head in src, (f, mn)
            assert src.index(head) < task_at, (f, mn)
        assert src.count(OPAQUE) == len(t["methods"]), f
        assert f"{OPAQUE}let {name} " not in src, f


def test_max3_calls_nest_through_the_contract() -> None:
    t = _load("methods/max3.t")
    src = lower(t, t["body"])
    assert "(ensures (fun m -> (((m >= x) /\\ (m >= y))" in src
    assert "= (max2 (max2 a b) c)" in src


def test_clamp_sum_method_calls_an_earlier_method() -> None:
    t = _load("methods/clamp_sum.t")
    src = lower(t, t["body"])
    assert src.index("let clamp ") < src.index("let add_clamped ")
    assert "= (clamp ((clamp x h) + y) h)" in src
    assert "= (add_clamped a b hi)" in src


def test_count_pos_call_inside_a_loop() -> None:
    t = _load("methods/count_pos.t")
    src = lower(t, t["body"])
    assert "then count_pos_loop s (step r (Seq.index s i)) (i + 1)" in src
    assert "(requires ((k >= 0)))" in src


def test_rev_twice_method_with_a_loop_and_seq_values() -> None:
    t = _load("methods/rev_twice.t")
    src = lower(t, t["body"])
    # the method's loop helper precedes it; only the method is opaque
    assert src.index("let rec rev_loop ") < src.index(f"{OPAQUE}let rev ")
    assert f"{OPAQUE}let rec rev_loop" not in src
    assert ": Pure (Seq.seq int)" in src
    assert "= (rev (rev s))" in src


def test_opaque_callee_is_opaque() -> None:
    t = _load("methods_probe/opaque_callee.t")
    src = lower(t, t["body"])
    assert f"{OPAQUE}let inc (a:int)" in src
    assert "(ensures (fun b -> ((b > a))))" in src
    assert "= (inc x)" in src


REC = """t 1
task rec_sum(n: int, x: int) returns (r: int)
  requires n >= 0
  ensures r >= 0
method tri(k: int) returns (v: int)
  requires k >= 0
  ensures v >= k
  decreases k
{
  if k == 0 {
    v := 0;
  } else {
    var p: int := tri(k - 1);
    v := p + k;
  }
}
{
  if x > 0 {
    r := tri(n);
  } else {
    r := 0;
  }
}
"""


def test_self_recursive_method_is_an_opaque_let_rec() -> None:
    t = surface.parse(REC)
    src = lower(t, t["body"])
    assert f"{OPAQUE}let rec tri (k:int)" in src
    assert "(decreases k)" in src
    assert "= (if (k = 0) then 0 else ((tri (k - 1)) + k))" in src
    assert "= (if (x > 0) then (tri n) else 0)" in src


def test_dead_method_call_abstains() -> None:
    t = _load("methods/max3.t")
    t = copy.deepcopy(t)
    # the first call's result is overwritten before it is read
    t["body"] = [t["body"][0], {"assign": ["m1", {"int": 0}]}, t["body"][1]]
    _raises(t, "dead method call")


def test_pair_typed_method_abstains() -> None:
    t = copy.deepcopy(_load("methods/max3.t"))
    t["methods"][0]["params"][0]["type"] = {"pair": ["int", "int"]}
    _raises(t, "pair-typed param or return")


def test_method_that_loops_and_self_recurses_abstains() -> None:
    t = copy.deepcopy(_load("methods/rev_twice.t"))
    m = t["methods"][0]
    m["decreases"] = {"op": "len", "args": [{"var": "u"}]}
    m["body"] = m["body"] + [{"assign": ["v", {"call": {
        "fun": "rev", "args": [{"var": "v"}]}}]}]
    _raises(t, "both loops and self-recurses")


def test_an_empty_methods_list_changes_nothing() -> None:
    for name in ("abs", "contains"):
        t = _load(f"tasks/{name}.t")
        assert "methods" not in t
        t2 = dict(t, methods=[])
        assert lower(t, t["body"]) == lower(t2, t2["body"])


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"{fn.__name__}: pass")
    print(f"test_lower_fstar_methods: {len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
