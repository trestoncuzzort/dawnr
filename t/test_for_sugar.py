#!/usr/bin/env python3
"""test_for_sugar.py: SPEC.md "Loops as sugar (v1)" (2026-10-06): the three `for` forms expand to the AST's `while`
with the bounds and decreases supplied; the parser's refusals; the committed tasks' twins. Standard library only."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_wf  # noqa: E402
import harness  # noqa: E402
import surface  # noqa: E402

CHECKS = 0


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def _task(params: str, ret: str, body: str, ensures: str = "true") -> dict:
    return surface.parse("t 1\ntask f(%s) returns (r: %s)\n  ensures %s\n{ %s }\n" % (params, ret, ensures, body))


def test_range_form():
    t = _task("n: int", "int", "r := 0; for i in [0, n) invariant r >= 0 { r := r + i; }", "r >= 0")
    body = t["body"]
    ok(len(body) == 3 and body[1] == {"var": {"name": "i", "type": "int", "init": {"int": 0}}}, "the index is a local: %r" % body[1])
    w = body[2]["while"]
    ok(w["cond"] == {"op": "<", "args": [{"var": "i"}, {"var": "n"}]}, "cond i < n")
    ok(w["invariants"][0] == {"op": "<=", "args": [{"int": 0}, {"var": "i"}]}
       and w["invariants"][1] == {"op": "<=", "args": [{"var": "i"}, {"var": "n"}]}, "the two bound invariants come first")
    ok(w["invariants"][2] == {"op": ">=", "args": [{"var": "r"}, {"int": 0}]}, "then the user's")
    ok(w["decreases"] == {"op": "-", "args": [{"var": "n"}, {"var": "i"}]}, "decreases n - i")
    ok(w["body"][-1] == {"assign": ["i", {"op": "+", "args": [{"var": "i"}, {"int": 1}]}]}, "the step is last")
    ok(check_wf.check_wf(t) == [], "well-formed")
    printed = surface.print_task(t)
    ok("while i < n" in printed and "decreases n - i" in printed and "for" not in printed, "printed as the while")
    ok(surface.parse(printed) == t, "the printed while reparses to the same AST")


def test_seq_forms():
    t = _task("s: seq", "int", "r := 0; for x in s { r := r + x; }")
    w = t["body"][2]["while"]
    ok(t["body"][1]["var"]["name"] == "i_x" and w["cond"] == {"op": "<", "args": [{"var": "i_x"}, {"op": "len", "args": [{"var": "s"}]}]},
       "the hidden index is i_x: %r" % w["cond"])
    ok(w["body"][0] == {"var": {"name": "x", "type": "int", "init": {"op": "at", "args": [{"var": "s"}, {"var": "i_x"}]}}},
       "the element is declared first: %r" % w["body"][0])
    ok(check_wf.check_wf(t) == [], "well-formed")
    t2 = _task("s: seq<bool>", "int", "r := 0; for i, b in s { if b { r := r + 1; } }")
    w2 = t2["body"][2]["while"]
    ok(w2["body"][0]["var"] == {"name": "b", "type": "bool", "init": {"op": "at", "args": [{"var": "s"}, {"var": "i"}]}},
       "the element takes the seq's element type")
    ok(check_wf.check_wf(t2) == [], "well-formed over seq<bool>")
    t3 = _task("m: seq<seq>", "int", "r := 0; for row in m { r := r + len(row); }")
    ok(t3["body"][2]["while"]["body"][0]["var"]["type"] == "seq" and check_wf.check_wf(t3) == [], "a row of a seq<seq> is a seq")
    t4 = _task("", "int", "r := 0; for x in [1, 2, 3] { r := r + x; }")
    ok(t4["body"][2]["while"]["cond"]["args"][1] == {"op": "len", "args": [{"op": "seq", "args": [{"int": 1}, {"int": 2}, {"int": 3}]}]},
       "a seq display is a sequence, not a range")


def test_refusals():
    bad = [("s: seq", "r := 0; for x in s { x := 1; }", "may not assign"),
           ("n: int", "r := 0; for i in [0, n) { i := 0; }", "may not assign"),
           ("n: int", "r := 0; for i in [0, n) { n := 0; }", "which the body assigns"),
           ("s: seq", "r := 0; for x in s { s := []; }", "which the body assigns"),
           ("n: int", "r := 0; for x in n { r := x; }", "not a seq"),
           ("s: seq, x: int", "r := 0; for x in s { r := x; }", "already declared"),
           ("s: seq", "r := 0; for i, i in s { r := 1; }", "two names"),
           ("n: int", "r := 0; for i in [0, n, 1) { r := 1; }", "two bounds")]
    for params, body, msg in bad:
        try:
            _task(params, "int", body)
            ok(False, "refused: %s" % body)
        except surface.SurfaceError as ex:
            ok(msg in str(ex), "refused %s with %r: %s" % (body, msg, ex))
    # an invariant naming the element is unbound at the loop head: the checker says so in words
    t = _task("s: seq", "int", "r := 0; for x in s invariant x >= 0 { r := r + x; }")
    errs = check_wf.check_wf(t)
    ok(errs and any("x" in e for e in errs), "an element in an invariant is refused in words: %r" % errs)


def test_committed_tasks():
    for name in ("count_pos_for", "zeros_for", "any_neg_for"):
        task = surface.parse_file(str(HERE / "tasks" / f"{name}.t"))
        ok(check_wf.check_wf(task) == [], f"{name} is well-formed")
        ok(surface.parse(surface.print_task(task)) == task, f"{name} round-trips through its while")
        twin, op, w = harness.twin_for(task)
        ok(twin is not None and w is not None, f"{name} has a twin with a witness: {op}")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"OK: {CHECKS} checks")
