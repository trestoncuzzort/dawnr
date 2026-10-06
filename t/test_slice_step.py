#!/usr/bin/env python3
"""test_slice_step.py: SPEC.md "Stepped slices (v1)" (2026-10-06): `s[a..b..k]` as sugar for a range comprehension, in
the notation (parse, print, round trip, the fresh bound variable, the refusals), the checker, the interpreter against
Python's own slicing, the twin ladder, the Python hand-back; and the Dafny text of a comprehension function with its
precondition (the `diffs` finding of T3c). Standard library only; no kernel runs (those are the matrix's)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_wf  # noqa: E402
import harness  # noqa: E402
import interp  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402
import to_python  # noqa: E402

CHECKS = 0


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def _task(params: str, ret: str, body: str, ensures: str = "true", requires: str = "true") -> dict:
    return surface.parse("t 1\ntask f(%s) returns (r: %s)\n  requires %s\n  ensures %s\n{ %s }\n"
                         % (params, ret, requires, ensures, body))


def _ev(text: str, env: dict, params: str = "s: seq"):
    task = _task(params, "seq", "r := %s;" % text)
    return interp.ev(task["body"][0]["assign"][1], dict(env), {}, interp.St())


SL = {"op": "slice", "args": [{"var": "s"}, {"int": 0}, {"var": "n"}]}
SL1 = {"op": "slice", "args": [{"var": "s"}, {"int": 1}, {"op": "len", "args": [{"var": "s"}]}]}


def test_sugar_expands_to_the_range_comprehension():
    t = _task("s: seq, n: int", "seq", "r := s[0..n..2];", requires="0 <= n and n <= len(s)")
    e = t["body"][0]["assign"][1]
    ok("comp" in e, "a stepped slice parses to a comprehension, got %r" % (e,))
    c = e["comp"]
    ok(c["var"] == "i" and c["lo"] == {"int": 0} and c["cond"] == {"bool": True}, "bound variable i over [0, ..), no condition")
    ok(c["hi"] == {"op": "div", "args": [{"op": "+", "args": [{"op": "len", "args": [SL]}, {"int": 1}]}, {"int": 2}]},
       "the bound is (len(s[0..n]) + 1) / 2: %r" % (c["hi"],))
    ok(c["body"] == {"op": "at", "args": [SL, {"op": "*", "args": [{"int": 2}, {"var": "i"}]}]},
       "the body is s[0..n][2 * i]: %r" % (c["body"],))
    ok(check_wf.check_wf(t) == [], "well-formed: %r" % check_wf.check_wf(t))
    printed = surface.print_task(t)
    ok("r := [s[0..n][2 * i] for i in [0, (len(s[0..n]) + 1) / 2)];" in printed,
       "printed as the comprehension, never as the sugar: %s" % printed)
    ok(surface.parse(printed) == t, "the printed comprehension reparses to the same AST")


def test_step_one_folds_the_arithmetic():
    t = _task("s: seq", "seq", "r := s[1..len(s)..1];", requires="len(s) >= 1")
    c = t["body"][0]["assign"][1]["comp"]
    ok(c["hi"] == {"op": "len", "args": [SL1]} and c["body"] == {"op": "at", "args": [SL1, {"var": "i"}]},
       "k == 1: the bound is len(s[1..len(s)]) and the body s[1..len(s)][i]: %r" % (c,))
    ok(check_wf.check_wf(t) == [], "well-formed")


def test_the_bound_variable_is_fresh_in_the_program():
    t = _task("s: seq, i: int, j: int", "seq", "r := s[0..i..2];", requires="0 <= i and i <= len(s)")
    ok(t["body"][0]["assign"][1]["comp"]["var"] == "k", "i and j taken: k")
    ok(check_wf.check_wf(t) == [], "and it shadows nothing")
    t = _task("s: seq, i: int, j: int, k: int", "seq", "r := s[0..i..2];", requires="0 <= i and i <= len(s)")
    ok(t["body"][0]["assign"][1]["comp"]["var"] == "i2", "i, j, k taken: i2")
    t = _task("s: seq, n: int", "seq", "r := s[0..n..2] + s[1..n..2];", requires="1 <= n and n <= len(s)")
    names = [a["comp"]["var"] for a in t["body"][0]["assign"][1]["args"]]
    ok(names == ["i", "j"], "two stepped slices in one program get two names: %r" % names)
    ok(check_wf.check_wf(t) == [] and surface.parse(surface.print_task(t)) == t, "both well-formed and round-tripping")
    e = surface.parse_expr("s[0..n..3]")
    ok(e["comp"]["var"] == "i" and surface.parse_expr(surface.pexpr(e)) == e, "an expression alone names it too")


def test_values_are_pythons():
    for s in ([], [5], [5, 6], [5, 6, 7], [5, 6, 7, 8], [1, 2, 3, 4, 5, 6, 7]):
        for a in range(0, len(s) + 1):
            for b in range(a, len(s) + 1):
                for k in (1, 2, 3, 5):
                    got = _ev("s[%d..%d..%d]" % (a, b, k), {"s": tuple(s)})
                    ok(list(got) == s[a:b:k], "s=%r s[%d..%d..%d] = %r, Python says %r" % (s, a, b, k, got, s[a:b:k]))
    for text, s in (("s[1..0..2]", (1, 2)), ("s[0..3..2]", (1, 2)), ("s[-1..2..2]", (1, 2))):
        try:
            _ev(text.replace("-1", "(0 - 1)"), {"s": s})
            ok(False, "%s on %r must be undefined (the two-bound slice's rule)" % (text, s))
        except interp.Undef:
            pass


def test_refused_by_name():
    for body, msg in (("r := s[0..n..0];", "0 is no step"),
                      ("r := s[0..n..-1];", "a reversal is rev(s)"),
                      ("r := s[0..n..k];", "written as the comprehension")):
        try:
            _task("s: seq, n: int, k: int", "seq", body)
            ok(False, "%s must not parse" % body)
        except surface.SurfaceError as exc:
            ok(msg in str(exc), "%s -> %s" % (body, exc))


def test_hand_back_and_twins():
    src, _fn = to_python.translate(_task("s: seq, n: int", "seq", "r := s[0..n..2];", requires="0 <= n and n <= len(s)"))
    ok("for i in range(0, " in src and "s[0:n]" in src, "the hand-back is the comprehension over Python's slice: %s" % src)
    for name in ("every_other", "odd_positions", "diffs"):
        task = tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))
        ok(check_wf.check_wf(task) == [], "%s well-formed" % name)
        twin, got, w = harness.twin_for(task)
        ok(twin is not None and w.get("_ens") is True, f"{name}: a twin with a witness that fails the ensures: {got} {w}")


def test_dafny_text_of_a_comprehension_function():
    def lowered(name):
        out = subprocess.run([sys.executable, str(HERE / "cli.py"), "lower", str(HERE / "tasks" / f"{name}.t"),
                              "--kernel", "dafny"], capture_output=True, text=True, timeout=120)
        return out.stdout + out.stderr
    d = lowered("diffs")
    ok("requires forall t_di :: 0 <= t_di < t_n ==> " in d and "t_ix(t_di)" in d.split("requires forall t_di")[1],
       "the precondition over the element, as the Std's Map requires f.requires(xs[i]), the range index through t_ix: %s" % d)
    ok("t_comp1(0, ((|s| - 1) - 0), s)" in d, "a range comprehension is its lower bound and its length: %s" % d)
    d = lowered("odd_positions")
    ok("requires t_n > 0 ==> " in d and "(1 <= |s|)" in d.split("requires t_n > 0 ==> ")[1].splitlines()[0],
       "the conjuncts without the element are stated once under a non-empty prefix: %s" % d)
    d = lowered("doubled")
    head = d.split("function t_comp1")[1].split("{")[0]
    ok("requires forall t_di" not in head and "requires t_n > 0" not in head and "requires 0 <= t_n <= |t_s|" in head,
       "a total body has no definedness precondition, only the prefix bound: %s" % d)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
