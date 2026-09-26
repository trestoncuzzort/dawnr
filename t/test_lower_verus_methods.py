#!/usr/bin/env python3
"""test_lower_verus_methods.py: SPEC.md "Methods (v1)" in the Verus
lowering. Shape only; this file runs no prover (verdicts are measured by
the grade and recorded in t/FEATURES-TRACK.md).

Each method lowers to its own `proof fn` carrying its own requires/ensures
(and decreases when it self-calls), before the task's proof fn, and a call
statement `x := m(args)` lowers to a plain Verus call of that proof fn,
which Verus reasons about through the callee's contract only (Verus guide,
"Preconditions (requires clauses)": "when Verus verifies the body of the
main function, it can assume that octuple satisfies its postconditions,
without having to know anything about the body of octuple"). The callee's
body is never inlined into the caller.

Run: python3 t/test_lower_verus_methods.py   (or pytest)
"""

from __future__ import annotations

import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import harness                                                 # noqa: E402
import lower_verus                                             # noqa: E402
import surface                                                 # noqa: E402


def _load(path: str) -> dict:
    return surface.parse_file(os.path.join(HERE, path))


def _lower(path: str) -> str:
    t = _load(path)
    return lower_verus.lower(t, t["body"])


def _raises(task: dict, needle: str) -> None:
    try:
        lower_verus.lower(task, task["body"])
    except NotImplementedError as e:
        assert needle in str(e), str(e)
        return
    raise AssertionError(f"expected NotImplementedError containing {needle!r}")


def test_max3_method_before_task_and_call_is_a_call():
    src = _lower("methods/max3.t")
    assert "proof fn max2(x: int, y: int) -> (m: int)" in src
    assert src.index("proof fn max2(") < src.index("proof fn max3(")
    head = src[src.index("proof fn max2("):src.index("proof fn max3(")]
    assert "ensures" in head and "((m == x) || (m == y))" in head
    assert "let mut m1: int = max2(a, b);" in src
    assert "r = max2(m1, c);" in src


def test_clamp_sum_methods_in_order_with_requires():
    src = _lower("methods/clamp_sum.t")
    i_c = src.index("proof fn clamp(")
    i_a = src.index("proof fn add_clamped(")
    i_t = src.index("proof fn clamp_sum(")
    assert i_c < i_a < i_t
    assert "requires\n        (h >= (0int))," in src[i_c:i_a]
    assert "s = clamp((u + y), h);" in src
    assert "r = add_clamped(a, b, hi);" in src


def test_count_pos_call_inside_loop_helper():
    src = _lower("methods/count_pos.t")
    assert "proof fn step(k: int, x: int) -> (n: int)" in src
    helper = src[src.index("proof fn t_lp_count_pos_0("):
                 src.index("proof fn count_pos(")]
    assert "r = step(r, s[i]);" in helper
    # a method result is never a defining fact of a loop helper
    assert "step(" not in helper.split("{", 1)[0]


def test_rev_twice_seq_method_with_its_own_loop():
    src = _lower("methods/rev_twice.t")
    assert "proof fn rev(u: Seq<int>) -> (v: Seq<int>)" in src
    assert "proof fn t_lp_rev_0(" in src
    assert "let mut w: Seq<int> = rev(s);" in src
    assert "r = rev(w);" in src


def test_opaque_callee_not_inlined():
    src = _lower("methods_probe/opaque_callee.t")
    main = src[src.index("proof fn opaque_callee("):]
    assert "r = inc(x);" in main
    assert "(a + (1int))" not in main and "(x + (1int));" not in main


def test_twin_keeps_methods_unmutated():
    t = _load("methods/max3.t")
    body, _op, w = harness.twin_for(t)
    assert body is not None
    real = lower_verus.lower(t, t["body"])
    twin = lower_verus.lower(t, body, w)
    cut = "proof fn max3("
    assert real[:real.index(cut)] == twin[:twin.index(cut)]


def test_recursive_method_carries_decreases():
    t = _load("methods/max3.t")
    t = copy.deepcopy(t)
    m = t["methods"][0]
    # max2(x, y) with a self-call guarded by a measure (lowering shape only)
    m["decreases"] = {"int": 0}
    src = lower_verus.lower(t, t["body"])
    head = src[src.index("proof fn max2("):src.index("proof fn max3(")]
    assert "decreases (0int)," in head


def test_abstain_self_call_inside_loop():
    t = copy.deepcopy(_load("methods/count_pos.t"))
    t["methods"].append({
        "name": "g", "params": [{"name": "k", "type": "int"}],
        "returns": [{"name": "s", "type": "int"}],
        "requires": [], "ensures": [{"bool": True}],
        "decreases": {"var": "k"},
        "body": [
            {"assign": ["s", {"int": 0}]},
            {"while": {"cond": {"op": "<", "args": [{"var": "s"}, {"var": "k"}]},
                       "invariants": [], "decreases": {"op": "-", "args": [{"var": "k"}, {"var": "s"}]},
                       "body": [{"assign": ["s", {"call": {"fun": "g", "args": [{"var": "s"}]}}]}]}}]})
    _raises(t, "self-calls inside a loop")


def test_abstain_name_collision():
    t = copy.deepcopy(_load("methods/max3.t"))
    t["methods"][0]["name"] = "main"
    t["body"] = [{"var": {"name": "m1", "type": "int",
                          "init": {"call": {"fun": "main", "args": [{"var": "a"}, {"var": "b"}]}}}},
                 {"assign": ["r", {"call": {"fun": "main", "args": [{"var": "m1"}, {"var": "c"}]}}]}]
    _raises(t, "declared name collision")


def test_abstain_v0_with_methods():
    t = copy.deepcopy(_load("methods/max3.t"))
    t["t"] = 0
    _raises(t, "methods are v1 only")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"{fn.__name__}: pass")
    print(f"test_lower_verus_methods: {len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
