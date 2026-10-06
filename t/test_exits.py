#!/usr/bin/env python3
"""test_exits.py: SPEC.md "Early exits (v1)" (2026-10-06): `break`, `continue` and `while true` in the notation, the
checker, the interpreter (and the `for` sugar's step at a `continue`), the twin ladder's DROP-EXIT, the shape guard,
the Dafny text and the Python hand-back; and the comprehension key by shape (one Dafny function for a comprehension
over a prefix and over the whole). Standard library only; no kernel runs (those are the matrix's)."""
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
import tshape  # noqa: E402

CHECKS = 0


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def _load(name: str) -> dict:
    return tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))


def _run(task: dict, env: dict):
    env = dict(env)
    interp.exec_body(task["body"], env, {f["name"]: f for f in task.get("spec_funs", [])}, interp.St())
    return env[task["returns"][0]["name"]]


def test_notation_round_trip():
    for name, words in (("index_of", ["break;"]), ("find_zero", ["while true", "break;"]),
                        ("count_evens_skip", ["continue;", "i := i + 1;"])):
        task = _load(name)
        text = surface.print_task(task)
        ok(all(w in text for w in words), f"{name} prints its exits: {text}")
        ok(surface.parse(text) == task and check_wf.check_wf(task) == [], f"{name} round-trips and is well-formed")
    t = surface.parse("t 1\ntask f(n: int) returns (r: int)\n  ensures true\n{ r := 0; while true decreases 0 { break; } }\n")
    ok(t["body"][1]["while"]["cond"] == {"bool": True} and t["body"][1]["while"]["body"] == [{"break": True}],
       "while true with a bare break: %r" % (t["body"],))


def test_checker_rules():
    def errs(text: str) -> list:
        # check_wf returns strings, "message [SPEC: rule text]"; the rule is read off the text after "[SPEC: "
        out = []
        for e in check_wf.check_wf(surface.parse(text)):
            tail = str(e).split("[SPEC: ")[-1]
            out.append({"break and continue belong": "exit-outside-loop", "no statement follows a break": "exit-unreachable",
                        "a while true loop holds": "loop-exit"}.get(next((k for k in ("break and continue belong",
                        "no statement follows a break", "a while true loop holds") if tail.startswith(k)), ""), tail))
        return out
    ok("exit-outside-loop" in errs("t 1\ntask f(x: int) returns (r: int)\n  ensures true\n{ r := x; break; }\n"), "break outside a loop")
    ok("exit-outside-loop" in errs("t 1\ntask f(x: int) returns (r: int)\n  ensures true\n{ r := x; if x > 0 { continue; } }\n"),
       "continue under an if outside a loop")
    ok("exit-unreachable" in errs("t 1\ntask f(x: int) returns (r: int)\n  ensures true\n"
                                   "{ var i: int := 0; while i < x invariant true decreases x - i { continue; i := i + 1; } r := i; }\n"),
       "a statement after continue")
    ok("loop-exit" in errs("t 1\ntask f(x: int) returns (r: int)\n  ensures true\n"
                            "{ var i: int := 0; while true invariant true decreases x - i { i := i + 1; } r := i; }\n"),
       "while true without an exit")
    ok("loop-exit" in errs("t 1\ntask f(x: int) returns (r: int)\n  ensures true\n"
                            "{ var i: int := 0; while true invariant true decreases x - i { while i < x invariant true decreases x - i { break; } } r := i; }\n"),
       "a break inside a nested loop is the nested loop's, not the while true's")
    ok("loop-exit" not in errs("t 1\ntask f(x: int) returns (r: int)\n  ensures true\n"
                                "{ var i: int := 0; while true invariant true decreases x - i { if i >= x { return i; } i := i + 1; } r := i; }\n"),
       "a return anywhere is an exit of a while true")
    ok(errs("t 1\ntask f(x: int) returns (r: int)\n  ensures true\n"
            "{ var i: int := 0; while i < x invariant true decreases x - i { if i == 2 { break; } i := i + 1; } r := i; }\n") == [],
       "a break under an if inside the loop is fine")


def test_interpreter_and_for_step():
    io = _load("index_of")
    ok(_run(io, {"s": (3, 1, 4), "x": 1}) == 1 and _run(io, {"s": (3, 1, 4), "x": 9}) == 3 and _run(io, {"s": (), "x": 0}) == 0,
       "index_of breaks at the first match or runs to the end")
    fz = _load("find_zero")
    ok(_run(fz, {"s": (3, 0, 4)}) == 1 and _run(fz, {"s": (3, 1)}) == 2 and _run(fz, {"s": ()}) == 0, "find_zero's two breaks")
    ce = _load("count_evens_skip")
    for s in ((), (1,), (2,), (1, 2, 3, 4, 6), (5, 7, 9)):
        ok(_run(ce, {"s": s}) == len([y for y in s if y % 2 == 0]), f"count_evens_skip on {s}")
    # a continue inside a nested while inside a for belongs to the inner loop: the for's step is not added to it
    t = surface.parse("t 1\ntask f(s: seq) returns (r: int)\n  ensures true\n{ r := 0; for x in s { var j: int := 0; "
                      "while j < 2 invariant true decreases 2 - j { j := j + 1; if j == 1 { continue; } r := r + x; } } }\n")
    inner = t["body"][2]["while"]["body"][2]["while"]["body"]   # [var x, var j, while, i := i + 1]
    ok(inner[1]["if"]["then"] == [{"continue": True}], "the inner continue is untouched: %r" % (inner,))
    ok(_run(t, {"s": (5, 6)}) == 11, "and the program runs as Python would (r = 5 + 6)")


def test_twins_guard_and_handback():
    for name in ("index_of", "find_zero", "count_evens_skip"):
        task = _load(name)
        twin, got, w = harness.twin_for(task)
        ok(twin is not None and w.get("_ens") is True, f"{name}: a twin with a witness that fails the ensures: {got} {w}")
        ok(tshape.has_exit(task, task["body"]), f"{name} has an exit")
        src, _fn = to_python.translate(task)
        ok(("break" in src) or ("continue" in src), f"{name} hands back Python's statement: {src}")
    body = _load("index_of")["body"]
    scope = [("s", "seq"), ("x", "int"), ("r", "int")]
    dropped = list(harness._c_drop_exit(body, scope))
    ok(len(dropped) == 1 and not tshape.has_exit({}, dropped[0]), "DROP-EXIT deletes the one break")
    ok(not tshape.has_exit(_load("evens"), _load("evens")["body"]), "a task without exits is not flagged")


def test_dafny_text_and_comprehension_key():
    def lowered(name):
        out = subprocess.run([sys.executable, str(HERE / "cli.py"), "lower", str(HERE / "tasks" / f"{name}.t"),
                              "--kernel", "dafny"], capture_output=True, text=True, timeout=120)
        return out.stdout + out.stderr
    d = lowered("find_zero")
    ok("while true" in d and d.count("break;") == 2, "find_zero in Dafny: while true and two breaks: %s" % d)
    d = lowered("count_evens_skip")
    ok("continue;" in d and "function t_comp1(" in d and "t_comp2" not in d,
       "count_evens_skip in Dafny: continue, and one comprehension function for the prefix and the whole: %s" % d)
    ok("t_comp1(s, i)" in d and "t_comp1(s, |s|)" in d, "the prefix call and the whole: %s" % d)
    for kernel in ("verus", "spark", "fstar"):
        out = subprocess.run([sys.executable, str(HERE / "cli.py"), "lower", str(HERE / "tasks" / "index_of.t"),
                              "--kernel", kernel], capture_output=True, text=True, timeout=120)
        ok("break, continue and while-true loops are not lowered yet" in out.stdout + out.stderr, "%s abstains by name" % kernel)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
