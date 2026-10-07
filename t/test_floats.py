#!/usr/bin/env python3
"""test_floats.py: SPEC.md "Floats (v1)" (PREDICT T48), IEEE-754 binary64: the notation, the typing, the
interpreter's rounding and definedness, the twins, the hand-back, and every kernel's refusal by name until SPARK's
lowering lands. Standard library only, no kernel runs."""
from __future__ import annotations

import math
import sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_wf  # noqa: E402
import harness  # noqa: E402
import interp  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402
import tlib  # noqa: E402
import to_python  # noqa: E402

CHECKS = 0


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def task_of(params: str, ret: str, body: str, ensures: str = "true") -> dict:
    return surface.parse(f"t 1\ntask fl({params}) returns (r: {ret})\n  ensures {ensures}\n{{\n  {body}\n}}\n")


def ev(text: str, env: dict, params: str = "x: float, y: float", ret: str = "float"):
    t = task_of(params, ret, f"r := {text};")
    errs = check_wf.check_wf(t)
    ok(errs == [], f"{text} is well-typed: {errs}")
    return interp.ev(t["body"][0]["assign"][1], dict(env), {}, interp.St())


def test_notation_and_typing():
    t = tasks_io.load_task(str(HERE / "tasks" / "sat_scale.t"))
    ok(check_wf.check_wf(t) == [] and surface.parse(surface.print_task(t)) == t, "sat_scale: well-formed, round trip")
    ok(t["params"][0] == {"name": "x", "type": "float"}, "the float type")
    for body, rule in (("r := x + 1;", "arith-int"), ("r := sqrt(1);", "float-conv"),
                       ("r := float(true);", "float-conv")):
        errs = check_wf.check_wf(task_of("x: float", "float", body))
        ok(any(check_wf.RULES[rule] in e for e in errs), f"{body}: {rule}, {errs}")
    ok(check_wf.check_wf(task_of("x: float", "real", "r := real(x) * 2.0;")) == [], "real(f) is a real")


def test_rounding_and_definedness():
    ok(ev("x + y", {"x": 0.1, "y": 0.2}) == 0.1 + 0.2 != 0.3, "binary64 rounding, not exact arithmetic")
    ok(ev("float(0.1)", {}) == 0.1, "a real literal rounded to nearest")
    ok(ev("float(9007199254740993)", {}) == 9007199254740992.0, "an int rounded to nearest, ties to even")
    ok(ev("sqrt(x)", {"x": 2.0}) == math.sqrt(2.0), "a correctly rounded square root")
    ok(interp.ev(task_of("x: float", "real", "r := real(x);")["body"][0]["assign"][1], {"x": 0.1}, {}, interp.St())
       == Fraction(0.1), "real(f) is the double's exact value")
    for text, env in (("x * y", {"x": 1e308, "y": 10.0}), ("x / y", {"x": 1.0, "y": 0.0}),
                      ("sqrt(x)", {"x": -1.0, "y": 0.0}), ("x - y", {"x": -1e308, "y": 1e308})):
        try:
            ev(text, env)
            ok(False, f"{text} at {env} has no value")
        except interp.Undef:
            ok(True, f"{text} at {env} has no value")
    ok(ev("x", {"x": -0.0, "y": 0.0}) == 0.0, "-0.0 equals 0.0")


def test_twins_and_hand_back():
    t = tasks_io.load_task(str(HERE / "tasks" / "sat_scale.t"))
    tw, op, w = harness.twin_for(t)
    ok(tw is not None and w.get("_ens") is True and isinstance(w["_twin"], float), f"a twin with a float witness: {w}")
    src, fn = to_python.translate(t)
    ok("_t_f(x * k)" in src, "float arithmetic checked for finiteness")
    r = to_python.check(t, src, fn)
    ok(r["agrees"], f"the hand-back agrees with t: {r}")
    t2 = task_of("x: float, y: float", "float", "r := x * y;")
    src2, fn2 = to_python.translate(t2)
    ns: dict = {}
    exec(compile(src2, "<hand-back>", "exec"), ns)
    try:
        ns[fn2](1e308, 10.0)
        ok(False, "an overflow raises")
    except ArithmeticError:
        ok(True, "an overflow raises")


def test_spark():
    # PREDICT T49: Long_Float, the literals as their exact decimal values, the rest refused by name
    src = tlib.lower(tasks_io.load_task(str(HERE / "tasks" / "sat_scale.t")), "spark")
    ok("function F (X : Long_Float; K : Long_Float; Lim : Long_Float) return Long_Float" in src, "Long_Float")
    ok("Long_Float'(1.000E3)" in src and "Long_Float'(0.0E0)" in src, "exact literals")
    import lower_spark
    ok(lower_spark._float_lit(0.1) == "Long_Float'(1.000000000000000055511151231257827021181583404541015625E-1)",
       "0.1 as the double it is")
    for body in ("r := sqrt(x);", "r := float(n);"):
        try:
            tlib.lower(task_of("x: float, n: int", "float", body), "spark")
            ok(False, f"{body} refuses")
        except NotImplementedError as e:
            ok("not lowered yet" in str(e) and "Floats" in str(e), f"{body} refuses by name: {e}")


def test_kernels_refuse_by_name():
    t = tasks_io.load_task(str(HERE / "tasks" / "sat_scale.t"))
    for k in ("dafny", "verus", "lean", "rocq", "fstar", "framac"):
        try:
            tlib.lower(t, k)
            ok(False, f"{k} refuses")
        except NotImplementedError as e:
            ok("floats are not lowered yet" in str(e), f"{k} refuses by name: {e}")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
