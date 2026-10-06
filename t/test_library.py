#!/usr/bin/env python3
"""test_library.py: SPEC.md "The library (v1)" (2026-10-06) in the notation, the checker, the interpreter, the twin
ladder, the shape guard, the Python hand-back and the Dafny lowering's text. Standard library only;
`python3 t/test_library.py` exits nonzero on a failure and prints OK with the count otherwise."""
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
import to_python  # noqa: E402
import tshape  # noqa: E402

CHECKS = 0


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def _task(params: str, ret: str, body: str, ensures: str = "true", extra: str = "") -> dict:
    return surface.parse("t 1\ntask f(%s) returns (r: %s)\n  ensures %s\n%s{ %s }\n" % (params, ret, ensures, extra, body))


def _ev(text: str, env: dict | None = None, params: str = "", ret: str = "int"):
    task = _task(params, ret, "r := %s;" % text)
    return interp.ev(task["body"][0]["assign"][1], dict(env or {}), {}, interp.St())


def test_calls_are_operators_and_print_back():
    for text, op in (("min(a, b)", "min"), ("max(a, b)", "max"), ("abs(a)", "abs"), ("gcd(a, b)", "gcd"),
                     ("pow(a, b)", "pow"), ("isqrt(a)", "isqrt")):
        task = _task("a: int, b: int", "int", "r := %s;" % text)
        node = task["body"][0]["assign"][1]
        ok(node.get("op") == op, "%s is the operator %s: %r" % (text, op, node))
        ok(check_wf.check_wf(task) == [], "%s is well-formed" % text)
        ok(("r := %s;" % text) in surface.print_task(task) and surface.parse(surface.print_task(task)) == task,
           "%s prints back and reparses" % text)
    for text, op, params in (("sum(s)", "sum", "s: seq"), ("rev(s)", "rev", "s: seq")):
        task = _task(params, "int" if op == "sum" else "seq", "r := %s;" % text)
        ok(task["body"][0]["assign"][1].get("op") == op and check_wf.check_wf(task) == [], text)
    # a declared spec_fun of the same name shadows the library (as in Python); a task may be named abs
    task = _task("x: int", "int", "r := max(x, 1);", "true", "spec fun max(a: int, b: int): int decreases 0 = a + b\n")
    ok("call" in task["body"][0]["assign"][1] and check_wf.check_wf(task) == [], "a declared max stays a call")
    named = surface.parse("t 1\ntask abs(x: int) returns (r: int)\n  ensures r >= 0\n{ if x < 0 { r := -x; } else { r := x; } }\n")
    ok(named["name"] == "abs" and check_wf.check_wf(named) == [], "a task named abs")
    # membership in a seq, by the right operand's type
    task = _task("s: seq, x: int", "bool", "r := x in s;")
    ok(task["body"][0]["assign"][1]["op"] == "in" and check_wf.check_wf(task) == [], "x in s on a seq")


def test_sugar_and_the_raw_spelling():
    task = _task("s: seq", "int", "r := s[-1] + s[-2];", "len(s) > 1")
    printed = surface.print_task(task)
    ok("s[len(s) - 1] + s[len(s) - 2]" in printed, "s[-1] expands to len(s) - 1: %s" % printed)
    ok(surface.parse(printed) == task, "and reparses to the same AST")
    task = _task("s: seq", "seq", "r := s[1..-1] + s[-2..];")
    printed = surface.print_task(task)
    ok("s[1..len(s) - 1] + s[len(s) - 2..len(s)]" in printed, "slice bounds expand: %s" % printed)
    raw = _task("s: seq", "int", "r := s[(-1)];")
    ok(raw["body"][0]["assign"][1] == {"op": "at", "args": [{"var": "s"}, {"int": -1}]}, "s[(-1)] is the raw literal")
    ok("s[(-1)]" in surface.print_task(raw) and surface.parse(surface.print_task(raw)) == raw, "and prints back as itself")
    var = _task("s: seq, i: int", "int", "r := s[i];")
    ok(var["body"][0]["assign"][1]["args"][1] == {"var": "i"}, "a variable index is never wrapped")


def test_typing():
    bad = [("x: real, n: int", "real", "r := max(x, n);", "two ints or two reals"),
           ("s: seq", "int", "r := abs(s);", "abs wants"),
           ("w: set", "int", "r := sum(w);", "sum wants"),
           ("x: real", "int", "r := gcd(x, x);", "gcd wants"),
           ("n: int", "int", "r := rev(n);", "rev wants"),
           ("s: seq", "bool", "r := true in s;", "in wants (T, seq<T>)"),
           ("x: real", "int", "r := isqrt(x);", "isqrt wants"),
           ("s: seq<bool>", "seq<bool>", "r := sort(s);", "sort wants")]
    for params, ret, body, msg in bad:
        errs = check_wf.check_wf(_task(params, ret, body))
        ok(any(msg in e for e in errs), "ill-typed %s needs %r: %r" % (body, msg, errs))
    good = [("x: real, y: real", "real", "r := min(x, y) + abs(x);"),
            ("s: seq<real>", "real", "r := sum(s);"),
            ("s: seq<bool>", "seq<bool>", "r := rev(s);"),
            ("s: seq<seq>", "bool", "r := [1] in s;")]
    for params, ret, body in good:
        ok(check_wf.check_wf(_task(params, ret, body)) == [], "well-typed: %s" % body)


def test_interpreter_values():
    ok(_ev("min(3, 5)") == 3 and _ev("max(3, 5)") == 5 and _ev("abs(-7)") == 7, "min max abs")
    ok(_ev("gcd(12, 18)") == 6 and _ev("gcd(-12, 18)") == 6 and _ev("gcd(0, 0)") == 0 and _ev("gcd(7, 0)") == 7, "gcd")
    ok(_ev("pow(2, 10)") == 1024 and _ev("pow(5, 0)") == 1 and _ev("pow(-2, 3)") == -8, "pow")
    ok(_ev("isqrt(15)") == 3 and _ev("isqrt(16)") == 4 and _ev("isqrt(0)") == 0, "isqrt")
    ok(_ev("sum([1, 2, 3])") == 6 and _ev("sum([])") == 0, "sum")
    ok(_ev("rev([1, 2, 3])", ret="seq") == (3, 2, 1) and _ev("rev([])", ret="seq") == (), "rev")
    ok(_ev("2 in [1, 2, 3]", ret="bool") is True and _ev("4 in [1, 2, 3]", ret="bool") is False, "in on a seq")
    ok(_ev("sort([3, 1, 2])", ret="seq") == (1, 2, 3) and _ev("sort([])", ret="seq") == (), "sort (SPEC.md Sorting)")
    ok(_ev("sort(s)", {"s": (Fraction(1, 2), Fraction(-1, 3))}, "s: seq<real>", "seq<real>") == (Fraction(-1, 3), Fraction(1, 2)), "sort of reals")
    ok(_ev("min(1.5, 0.25)", ret="real") == Fraction(1, 4) and _ev("abs(-2.5)", ret="real") == Fraction(5, 2), "reals")
    ok(_ev("sum(s)", {"s": (Fraction(1, 2), Fraction(1, 2))}, "s: seq<real>", "real") == 1, "sum of reals")
    for text in ("pow(2, -1)", "isqrt(-1)"):
        try:
            _ev(text)
            ok(False, "%s is undefined" % text)
        except interp.Undef:
            ok(True, "%s is undefined" % text)


def test_twins_of_the_committed_tasks():
    want = {"sort_it": "wrong-var", "first_sorted": "off-by-one",
            "clamp": "wrong-var", "distance": "wrong-var", "sum_tail": "wrong-operator", "gcd_of": "wrong-var",
            "cube": "wrong-constant", "root_floor": "wrong-constant", "has_elem": "collapse-if",
            "palindrome": "wrong-var", "last_of": "off-by-one", "sum_one": "wrong-constant"}
    for name, op in want.items():
        task = surface.parse_file(str(HERE / "tasks" / f"{name}.t"))
        ok(check_wf.check_wf(task) == [], f"{name} is well-formed")
        ok(surface.parse(surface.print_task(task)) == task, f"{name} round-trips")
        twin, got, w = harness.twin_for(task)
        ok(twin is not None and got.split("#")[0] == op, f"{name}'s twin is {op}: {got}")
        ok(w.get("_ens") is True, f"{name}'s witness falsifies ensures: {w}")
    # min <-> max is the one new wrong-operator move
    task = _task("a: int, b: int", "int", "r := min(a, b);", "r <= a")
    harness._set_ctx(task)
    cands = list(harness._c_wrong_operator(task["body"], harness._scope(task)))
    ok(any(c[0]["assign"][1]["op"] == "max" for c in cands), "wrong-operator swaps min for max")


def test_shape_guard_and_hand_back():
    task = surface.parse_file(str(HERE / "tasks" / "clamp.t"))
    for kernel in ("lean", "rocq", "framac"):
        try:
            tshape.abstain_unless_carried(task, task["body"], kernel)
            ok(False, "%s abstains on the library" % kernel)
        except NotImplementedError as ex:
            ok("max" in str(ex) and "min" in str(ex), "abstains by name: %s" % ex)
    tshape.abstain_unless_carried(task, task["body"], "k", lib=frozenset({"min", "max"}))
    ok(True, "a kernel carrying min and max passes")
    mem = surface.parse_file(str(HERE / "tasks" / "has_elem.t"))
    try:
        tshape.abstain_on_library(mem, mem["body"], "k")
        ok(False, "membership in a seq abstains by name")
    except NotImplementedError as ex:
        ok("membership" in str(ex), "membership in a seq abstains by name")
    tshape.abstain_on_library(mem, mem["body"], "k", carried=frozenset({"in"}))
    src, _fn = to_python.translate(_task("a: int, b: int, s: seq", "int",
                                         "r := min(a, b) + max(a, b) + abs(a) + sum(s) + gcd(a, b) + pow(a, 2) + isqrt(b);"))
    for piece in ("min(", "max(", "abs(", "sum(", "_t_gcd(", "** ", "_t_isqrt(", "def _t_gcd", "def _t_isqrt"):
        ok(piece in src, "hand-back has %r" % piece)
    src, _fn = to_python.translate(_task("s: seq", "seq", "r := rev(s);"))
    ok("[::-1]" in src, "rev hands back as a reversed slice")
    src, _fn = to_python.translate(_task("s: seq", "seq", "r := sort(s);"))
    ok("tuple(sorted(s))" in src, "sort hands back as sorted")


def test_dafny_text():
    def lowered(name):
        out = subprocess.run([sys.executable, str(HERE / "cli.py"), "lower", str(HERE / "tasks" / f"{name}.t"),
                              "--kernel", "dafny"], capture_output=True, text=True, timeout=120)
        return out.stdout + out.stderr
    ok("function t_min(a: int, b: int): int" in lowered("clamp") and "t_max(lo, t_min(hi, x))" in lowered("clamp"),
       "clamp in Dafny: the Std.Math shapes")
    ok("requires n >= 0" in lowered("root_floor") and "t_isqrt(n)" in lowered("root_floor"), "isqrt carries its requires")
    ok("function t_rev<T>(s: seq<T>): (r: seq<T>)" in lowered("palindrome"), "rev is generic with its ensures")
    ok("t_gcdn(t_abs(a), t_abs(b))" in lowered("gcd_of"), "gcd is Euclid on absolute values")
    ok("(x in s)" in lowered("has_elem"), "membership is Dafny's own")
    st = lowered("sort_it")
    ok("function t_sort(s: seq<int>): (r: seq<int>)" in st and "multiset(s) == multiset(r)" in st and "predicate" not in st,
       "sort in Dafny: the Std's merge sort with its ensures, as functions only")
    # SPARK and F* (SPEC.md "The library (v1)": each kernel's own where it has one, a recursive definition where not)
    def lowered_in(name, kernel):
        out = subprocess.run([sys.executable, str(HERE / "cli.py"), "lower", str(HERE / "tasks" / f"{name}.t"),
                              "--kernel", kernel], capture_output=True, text=True, timeout=120)
        return out.stdout + out.stderr
    sp = lowered_in("clamp", "spark")
    ok("Max (Lo, Min (Hi, X))" in sp, "clamp in SPARK: Big_Integers' own Min and Max")
    ok("function T_Isqrt" in lowered_in("root_floor", "spark") and "Subprogram_Variant" in lowered_in("root_floor", "spark"),
       "isqrt in SPARK: a recursive expression function with a variant")
    ok("T_Contains (S, X)" in lowered_in("has_elem", "spark"), "membership in SPARK: the quantifier function")
    fs = lowered_in("clamp", "fstar")
    ok("FStar.Math.Lib.max" in fs and "FStar.Math.Lib.min" in fs, "clamp in F*: FStar.Math.Lib")
    ok("let rec t_gcdn" in lowered_in("gcd_of", "fstar"), "gcd in F*: Euclid as a let rec")
    ok("(Seq.mem x s)" in lowered_in("has_elem", "fstar"), "membership in F*: Seq.mem")
    vr = lowered_in("clamp", "verus")
    ok("pub open spec fn t_min(a: int, b: int) -> int" in vr and "t_max(lo, t_min(hi, x))" in vr, "clamp in Verus: the spec fns")
    rf = lowered_in("root_floor", "verus")
    ok("reveal_with_fuel(t_isqrt, 6);" in rf and "broadcast use t_isqrt_spec;" in rf, "isqrt in Verus: fuel and the lemma inside the proof fn")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"OK: {CHECKS} checks")
