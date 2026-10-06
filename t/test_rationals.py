#!/usr/bin/env python3
"""test_rationals.py: SPEC.md "Exact rationals (v1)" (2026-10-06) in the notation, the checker, the interpreter,
the twin ladder, the shape guard and the Dafny lowering's text. Standard library only;
`python3 t/test_rationals.py` exits nonzero on a failure and prints OK with the count otherwise."""
from __future__ import annotations

import subprocess
import sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_wf  # noqa: E402
import harness  # noqa: E402
import interp  # noqa: E402
import surface  # noqa: E402
import tshape  # noqa: E402

CHECKS = 0


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def _task(params: str, ret: str, body: str, ensures: str = "true") -> dict:
    return surface.parse("t 1\ntask f(%s) returns (r: %s)\n  ensures %s\n{ %s }\n" % (params, ret, ensures, body))


def _ev(expr_text: str, env: dict | None = None, params: str = "") -> object:
    task = _task(params, "real", "r := %s;" % expr_text)
    funs = interp.funs_of(task, task["body"])
    return interp.ev(task["body"][0]["assign"][1], dict(env or {}), funs, interp.St())


def test_literals_round_trip():
    for text, ast in (("1.5", [3, 2]), ("0.125", [1, 8]), ("3.0", [3, 1]), ("-2.5", [-5, 2]), ("0.1", [1, 10]),
                      ("100.25", [401, 4]), ("0.0", [0, 1])):
        task = _task("", "real", "r := %s;" % text)
        ok(task["body"][0]["assign"][1] == {"rat": ast}, "parses %s as %r" % (text, ast))
        ok(check_wf.check_wf(task) == [], "literal %s is well-formed" % text)
        printed = surface.print_task(task)
        ok(("r := %s;" % text) in printed, "prints back as %s: %s" % (text, printed.splitlines()[-2]))
        ok(surface.parse(printed) == task, "round trip %s" % text)
    ok(_task("", "real", "r := 1.50;")["body"][0]["assign"][1] == {"rat": [3, 2]}, "1.50 is 1.5 in lowest terms")
    ok(surface.print_task(_task("", "real", "r := 1.50;")).count("1.5;") == 1, "and prints as 1.5")
    for bad in ("3.", ".5"):
        try:
            _task("", "real", "r := %s;" % bad)
            ok(False, "refused %s" % bad)
        except surface.SurfaceError:
            ok(True, "refused %s" % bad)
    try:
        surface.print_task({"t": 1, "name": "f", "params": [], "returns": [{"name": "r", "type": "real"}],
                            "requires": [], "ensures": [{"bool": True}], "body": [{"assign": ["r", {"rat": [1, 3]}]}]})
        ok(False, "1/3 has no literal")
    except surface.SurfaceError:
        ok(True, "1/3 has no literal")
    for bad in ([1, 3], [2, 4], [1, -2], [1, 0], [1.5, 1]):
        errs = check_wf.check_wf({"t": 1, "name": "f", "params": [], "returns": [{"name": "r", "type": "real"}],
                                  "requires": [], "ensures": [{"bool": True}], "body": [{"assign": ["r", {"rat": bad}]}]})
        ok(any("real literal" in e for e in errs), "checker refuses rat %r: %r" % (bad, errs))
    # a real literal is never read after a dot: p.0.1 is two projections
    task = _task("p: ((int, int), int)", "int", "r := p.0.1;")
    ok(task["body"][0]["assign"][1] == {"op": "snd", "args": [{"op": "fst", "args": [{"var": "p"}]}]}, "p.0.1 is snd of fst")
    ok(check_wf.check_wf(task) == [], "and well-formed")


def test_typing():
    good = [("a: real, b: real", "real", "r := (a + b) / 2.0;"),
            ("n: int", "real", "r := real(n) / 2.0;"),
            ("x: real", "int", "r := floor(x) + ceil(x);"),
            ("x: real", "bool", "r := x < 1.5 and 0.0 <= x and x != 2.0;"),
            ("x: real", "real", "r := -x * 3.0 - 0.5;"),
            ("s: seq<real>", "real", "r := if len(s) > 0 then s[0] else 0.0;"),
            ("x: real", "(real, int)", "r := (x, floor(x));")]
    for params, ret, body in good:
        errs = check_wf.check_wf(_task(params, ret, body))
        ok(errs == [], "well-typed: %s -> %r" % (body, errs))
    bad = [("n: int", "real", "r := n + 1.0;", "all ints or all reals"),
           ("x: real", "bool", "r := x == 1;", "one type"),
           ("x: real", "real", "r := x % 2.0;", "all ints or all reals"),
           ("n: int", "int", "r := floor(n);", "floor wants a real"),
           ("x: real", "real", "r := real(x);", "toreal wants a int"),
           ("x: real", "bool", "r := x < 1;", "two ints or two reals"),
           ("x: real", "int", "r := x;", "assign")]
    for params, ret, body, msg in bad:
        errs = check_wf.check_wf(_task(params, ret, body))
        ok(any(msg in e for e in errs), "ill-typed %s needs %r: %r" % (body, msg, errs))
    ok(check_wf.expression_type({"op": "div", "args": [{"rat": [1, 1]}, {"rat": [3, 1]}]}, {})[0] == "real", "/ on reals is real")
    ok(check_wf.expression_type({"op": "div", "args": [{"int": 1}, {"int": 3}]}, {})[0] == "int", "/ on ints is int")


def test_interpreter_is_exact():
    ok(interp.ev(_task("", "bool", "r := 0.1 + 0.2 == 0.3;")["body"][0]["assign"][1], {}, {}, interp.St()) is True,
       "0.1 + 0.2 == 0.3 holds for exact rationals")
    ok(_ev("1.0 / 3.0") == Fraction(1, 3), "1.0 / 3.0 is a third")
    ok(_ev("real(7) / 2.0") == Fraction(7, 2), "real(7) / 2.0")
    ok(_ev("(1.0 / 3.0) * 3.0") == 1, "a third times three is one")
    ok(_ev("-1.5") == Fraction(-3, 2) and _ev("-(1.5)") == Fraction(-3, 2), "negative literal and neg")
    for text, want in (("floor(1.5)", 1), ("floor(-1.5)", -2), ("ceil(1.5)", 2), ("ceil(-1.5)", -1), ("ceil(2.0)", 2),
                       ("floor(2.0)", 2), ("floor(7.0 / 2.0)", 3), ("ceil(0.0 - 0.5)", 0)):
        task = _task("", "int", "r := %s;" % text)
        v = interp.ev(task["body"][0]["assign"][1], {}, {}, interp.St())
        ok(v == want and isinstance(v, int), "%s = %r (got %r)" % (text, want, v))
    try:
        _ev("1.0 / 0.0")
        ok(False, "division by zero is undefined")
    except interp.Undef:
        ok(True, "division by zero is undefined")
    ok(_ev("x / y", {"x": Fraction(1), "y": Fraction(4)}, "x: real, y: real") == Fraction(1, 4), "exact / on variables")
    ok(interp._j(Fraction(-3, 2)) == "-3/2" and interp._j(Fraction(2)) == "2/1", "witness rendering n/d")
    ok(interp._tv(Fraction(1)) != interp._tv(1), "a real is not an int")


def test_witness_ladder():
    task = _task("x: real", "real", "r := x + 2.5;")
    lad = interp.ladders(task)
    reals = lad["real"]
    ok(all(isinstance(v, Fraction) for v in reals), "the real ladder is Fractions")
    for want in (0, 1, -1, Fraction(1, 2), Fraction(5, 2), Fraction(7, 2), Fraction(3, 2), Fraction(1, 3)):
        ok(Fraction(want) in reals, "ladder holds %s" % want)
    ok(reals[0] == 0, "near first")
    ok(len(reals) == len(set(reals)), "no duplicates")
    seq_of_real = interp._ladder(lad, {"seq": "real"})
    ok(seq_of_real[0] == () and any(len(s) == 2 and all(isinstance(v, Fraction) for v in s) for s in seq_of_real),
       "a seq<real> ladder")


def test_twins_of_the_committed_tasks():
    want = {"average": "wrong-constant", "half_way": "off-by-one", "floor_ceil": "wrong-var", "safe_ratio": "collapse-if"}
    for name, op in want.items():
        task = surface.parse_file(str(HERE / "tasks" / f"{name}.t"))
        ok(check_wf.check_wf(task) == [], f"{name} is well-formed")
        ok(surface.parse(surface.print_task(task)) == task, f"{name} round-trips")
        twin, got, w = harness.twin_for(task)
        ok(twin is not None and got.split("#")[0] == op, f"{name}'s twin is {op}: {got}")
        ok(w.get("_ens") is True, f"{name}'s witness falsifies ensures: {w}")
        ok(check_wf.check_wf(dict(task, body=twin)) == [], f"{name}'s twin is a program of the language")
    # wrong-constant moves a real site by 1.0, never by the int 1
    task = _task("a: real", "real", "r := a * 2.0;", "r == a + a")
    harness._set_ctx(task)
    cands = list(harness._c_wrong_constant(task["body"], harness._scope(task)))
    ok(cands and all(c[0]["assign"][1]["args"][1] == {"rat": [d, 1]} for c, d in zip(cands, (1, -1))),
       "real wrong-constant candidates: %r" % cands)
    # off-by-one moves a real literal by one
    task = _task("a: real", "real", "r := a + 0.5;", "r > a")
    twins = [c for c in harness._c_off_by_one(task["body"], harness._scope(task))]
    ok({"rat": [3, 2]} in [c[0]["assign"][1]["args"][1] for c in twins]
       and {"rat": [-1, 2]} in [c[0]["assign"][1]["args"][1] for c in twins], "off-by-one on 0.5 gives 1.5 and -0.5")


def test_shape_guard():
    task = surface.parse_file(str(HERE / "tasks" / "half_way.t"))
    for carried in (frozenset(), frozenset({"*"})):
        try:
            tshape.abstain_unless_carried(task, task["body"], "k", carried)
            ok(False, "abstains on reals with carried=%r" % (set(carried),))
        except NotImplementedError as ex:
            ok("real" in str(ex), "abstains by name: %s" % ex)
    tshape.abstain_unless_carried(task, task["body"], "k", frozenset({"*", "real"}))
    ok(True, "carried reals pass")
    ok(tshape.mentions_real({"seq": "real"}) and tshape.mentions_real({"pair": ["int", {"tuple": ["int", "int", "real"]}]})
       and not tshape.mentions_real({"seq": {"seq": "seq"}}), "mentions_real")
    lit_only = _task("n: int", "int", "r := floor(1.5) + n;")
    try:
        tshape.abstain_on_reals(lit_only, lit_only["body"], "k")
        ok(False, "a real literal in an int task abstains")
    except NotImplementedError:
        ok(True, "a real literal in an int task abstains")


def test_dafny_text():
    def lowered(name, kernel="dafny"):
        out = subprocess.run([sys.executable, str(HERE / "cli.py"), "lower", str(HERE / "tasks" / f"{name}.t"),
                              "--kernel", kernel], capture_output=True, text=True, timeout=120)
        return out.stdout + out.stderr
    # SPARK (SPEC.md "Exact rationals (v1)", the Big_Reals encoding measured on 2026-10-06)
    sp = lowered("half_way", "spark")
    ok("Big_Reals" in sp and "return Big_Real" in sp and "To_Big_Real (Big_Integer'(2))" in sp,
       "half_way in SPARK: Big_Real and the quotient literal")
    ok("To_Big_Real (" in lowered("average", "spark"), "average in SPARK: real(x) is To_Big_Real")
    ok("has no floor or ceiling" in lowered("floor_ceil", "spark"), "floor_ceil in SPARK abstains by name")
    # F* (SPEC.md "Exact rationals (v1)": FStar.Real in the Ghost effect, measured 2026-10-06)
    fs = lowered("half_way", "fstar")
    ok("open FStar.Real" in fs and ": Ghost real" in fs and "/. 2.0R" in fs, "half_way in F*: Ghost real and the literal")
    ok("strong_excluded_middle (b == 0.0R)" in lowered("safe_ratio", "fstar"), "safe_ratio in F*: the ghost decision")
    ok("(of_int " in lowered("average", "fstar"), "average in F*: real(x) is of_int")
    ok("has no floor or ceiling" in lowered("floor_ceil", "fstar"), "floor_ceil in F* abstains by name")
    ok("returns (r: real)" in lowered("half_way") and "/ 2.0)" in lowered("half_way"), "half_way: real and the literal")
    fc = lowered("floor_ceil")
    ok(".Floor" in fc and "then" in fc and "Floor + 1" in fc, "floor_ceil: Floor and the conditional ceil")
    ok("as real" in lowered("average"), "average: the conversion")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"OK: {CHECKS} checks")
