#!/usr/bin/env python3
"""test_methods.py: SPEC.md "Methods (v1)", the front half -- the notation,
well-formedness, the interpreter, the twin ladder, and each lowering's
shape on the fixtures in t/methods/. Kernel verdicts are measured by
run_par (t/FEATURES-TRACK.md records them); this file runs no prover.

The design is Dafny's (reference manual 6.3 and 8.5.2, and "Dafny works
modularly, ... using only the specifications of other methods"): a method
is verified against its own contract, and a call is the whole right-hand
side of an assignment, reasoned about through that contract.

Run: python3 t/test_methods.py   (or pytest)
"""

from __future__ import annotations

import copy
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import check_wf                                                # noqa: E402
import harness                                                 # noqa: E402
import interp                                                  # noqa: E402
import surface                                                 # noqa: E402

FIXTURES = sorted(glob.glob(os.path.join(HERE, "methods", "*.t")))


def _load(name: str) -> dict:
    return surface.parse_file(os.path.join(HERE, "methods", name + ".t"))


def _run(task: dict, body: list | None = None, **args):
    body = task["body"] if body is None else body
    env = dict(args)
    ret = task["returns"][0]["name"]
    env[ret] = None
    interp.exec_body(body, env, interp.funs_of(task, body), interp.St())
    return env[ret]


def test_fixtures_parse_check_and_round_trip() -> None:
    assert len(FIXTURES) >= 4, FIXTURES
    for f in FIXTURES:
        t = surface.parse_file(f)
        assert t.get("methods"), f
        assert check_wf.check_wf(t) == [], (f, check_wf.check_wf(t))
        text = surface.print_task(t)
        again = surface.parse(text)
        assert surface.canon(again) == surface.canon(t), f
        assert surface.print_task(again) == text, f


def test_interpreter_runs_the_callee_body() -> None:
    t = _load("max3")
    assert _run(t, a=1, b=5, c=3) == 5
    assert _run(t, a=-1, b=-5, c=-3) == -1
    t = _load("clamp_sum")
    assert _run(t, a=3, b=4, hi=5) == 5
    assert _run(t, a=-3, b=2, hi=5) == 2
    t = _load("rev_twice")
    assert _run(t, s=(1, 2, 3)) == (1, 2, 3)


def test_interpreter_call_with_false_requires_is_undefined() -> None:
    t = _load("clamp_sum")
    try:
        _run(t, a=1, b=1, hi=-1)
    except interp.Undef as u:
        assert "requires" in str(u)
    else:
        raise AssertionError("a call whose requires is false must be undefined")


def test_twin_leaves_methods_alone_and_carries_a_witness() -> None:
    for name in ("max3", "clamp_sum", "rev_twice"):
        t = _load(name)
        before = copy.deepcopy(t["methods"])
        body, op, w = harness.twin_for(t)
        assert body is not None and w is not None, (name, op)
        assert w["_kind"] == "value", (name, w)
        assert t["methods"] == before
        # the witness is real: the twin computes what the ladder says
        args = {k: v for k, v in w.items() if not k.startswith("_")}
        assert _run(t, body, **args) != _run(t, **args)


def _wf(src: str) -> list:
    return [e.split(" [SPEC")[0] for e in check_wf.check_wf(surface.parse(src))]


HEAD = "t 1 task f(x: int) returns (r: int) ensures true\n"
G = "method g(a: int) returns (b: int) ensures b == a { b := a }\n"


def test_call_positions_follow_dafny() -> None:
    assert _wf(HEAD + G + "{ r := g(x) }") == []
    assert _wf(HEAD + G + "{ var y: int := g(x); r := y }") == []
    for body in ("{ r := g(x) + 1 }", "{ r := g(g(x)) }",
                 "{ if g(x) > 0 { r := 1 } else { r := 0 } }",
                 "{ return g(x); }"):
        errs = _wf(HEAD + G + body)
        assert any("method call outside" in e for e in errs), (body, errs)
    errs = _wf("t 1 task f(x: int) returns (r: int) ensures r == g(x)\n" + G + "{ r := x }")
    assert any("method call outside" in e for e in errs), errs


def test_order_names_and_recursion() -> None:
    errs = _wf(HEAD + "method g(a: int) returns (b: int) ensures true { b := h(a) }\n"
               "method h(a: int) returns (b: int) ensures true { b := a }\n{ r := g(x) }")
    assert any("later method" in e for e in errs), errs
    errs = _wf(HEAD + "method f(a: int) returns (b: int) ensures true { b := a }\n{ r := x }")
    assert any("collides" in e for e in errs), errs
    rec = ("method p(n: int) returns (b: int) requires n >= 0 ensures b >= 1 decreases n\n"
           "{ if n == 0 { b := 1 } else { var c: int := p(n - 1); b := 2 * c } }\n")
    assert _wf(HEAD + rec + "{ r := x }") == []
    errs = _wf(HEAD + rec.replace(" decreases n", "") + "{ r := x }")
    assert any("without a decreases" in e for e in errs), errs
    errs = _wf("t 0 task f(x: int) returns (r: int) ensures true\n" + G + "{ r := x }")
    assert any("v1 field" in e for e in errs), errs


def test_recursive_method_runs() -> None:
    t = surface.parse(HEAD.replace("ensures true", "requires x >= 0 ensures r >= 1")
                      + "method p(n: int) returns (b: int) requires n >= 0 ensures b >= 1 "
                        "decreases n\n{ if n == 0 { b := 1 } else { var c: int := p(n - 1); "
                        "b := 2 * c } }\n{ r := p(x) }")
    assert check_wf.check_wf(t) == []
    assert _run(t, x=5) == 32


def test_dafny_lowers_each_method_as_its_own_method() -> None:
    import lower_dafny
    t = _load("clamp_sum")
    src = lower_dafny.lower(t, t["body"])
    assert "method clamp(x: int, h: int) returns (c: int)" in src
    assert "method add_clamped(" in src
    assert "r := add_clamped(a, b, hi);" in src
    assert src.index("method clamp(") < src.index("method add_clamped(") < src.index("method Clamp_sum(")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"{fn.__name__}: pass")
    print(f"test_methods: {len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
