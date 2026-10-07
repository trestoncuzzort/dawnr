#!/usr/bin/env python3
"""test_framac_seq_locals.py: seq locals in Frama-C (SPEC.md "The library (v1)", the Frama-C note of 2026-10-07,
PREDICT T31). Text-level checks only, no kernel runs:
- a seq local whose initializer the lowering writes gets a workspace buffer, with the reverse_copy contract;
- `rev` is a write loop in code and an element rewrite in a specification;
- the refutation certificate replays the local cell by cell and decides a seq equality as a goal;
- the shapes outside it keep their refusal by name."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lower_framac  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402
import tlib  # noqa: E402

CHECKS = 0


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def load(name: str) -> dict:
    return tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))


def refusal(src: str) -> str:
    task = surface.parse(src)
    try:
        lower_framac.lower(task, task["body"])
    except NotImplementedError as e:
        return str(e)
    return ""


def test_workspace_contract():
    src = tlib.lower(load("palindrome"), "framac")
    ok("int palindrome_t(int *s, int s_n, int *u, int u_n)" in src, "the local's buffer is a parameter pair")
    for clause in ("requires \\valid(u + (0 .. u_n - 1));", "requires u_n == s_n;",
                   "requires \\separated(s + (0 .. s_n - 1), u + (0 .. u_n - 1));", "assigns u[0 .. u_n - 1];"):
        ok(clause in src, f"the reverse_copy contract: {clause}")
    ok("u[__k] = s[((s_n - 1) - (0 + __k))];" in src, "rev is a write loop")
    ok("s[((s_n) - 1 - (__k))]" in src, "and an element rewrite in the ensures")


def test_other_initializers():
    src = tlib.lower(load("set_first"), "framac")
    ok("requires u_n == s_n;" in src and "u[__k] = s[__k];" in src and "  u[0] = x;" in src,
       "an update is a copy, then the one write")
    src = tlib.lower(load("doubled_head"), "framac")
    ok("int *u, int u_n" in src and "requires u_n == s_n;" in src and "u[__k] = (2 * s[__k]);" in src,
       "a map's buffer has the source's length")
    task = surface.parse("t 1\ntask f(n: int) returns (r: int)\n  requires n > 0\n  ensures r == 7\n"
                         "{\n  var u: seq := seq(n, 7);\n  r := u[n - 1];\n}\n")
    ok("requires u_n == n;" in lower_framac.lower(task, task["body"]), "a fill's buffer has its count")


def test_certificate_replays_the_local():
    src = tlib.lower(load("palindrome"), "framac", twin_body=True)
    cert = src[src.index("void t_certificate(void)"):]
    ok("int t_cert_u[2];" in cert and "int u_n = 2;" in cert, "the local is a ground array")
    ok("/*@ assert s_n == 2; */" in cert, "its source's length is asserted first")
    ok("u[0] = s[1];" in cert and "u[1] = s[0];" in cert, "rev cell by cell")
    ok("r = 1;" in cert and "/*@ assert ((u_n == u_n) &&" in cert, "the seq equality decided as a goal")
    ok("int u;" not in cert, "never predeclared as an int")


def test_ground_rev():
    ok(lower_framac._cev({"op": "rev", "args": [{"var": "s"}]}, {"s": [1, 2, 3]}) == [3, 2, 1], "_cev's rev")


def test_still_refused_by_name():
    in_loop = ("t 1\ntask f(s: seq) returns (r: int)\n  ensures true\n{\n  r := 0;\n  var i: int := 0;\n"
               "  while i < 1\n    invariant 0 <= i and i <= 1\n    decreases 1 - i\n  {\n"
               "    var u: seq := rev(s);\n    i := i + 1;\n  }\n}\n")
    ok("seq-typed local variables are not supported" in refusal(in_loop), "a local inside a loop")
    again = ("t 1\ntask f(s: seq) returns (r: int)\n  requires len(s) > 0\n  ensures true\n{\n"
             "  var u: seq := rev(s);\n  u := s;\n  r := u[0];\n}\n")
    ok("seq-typed local variables are not supported" in refusal(again), "a local written twice")
    concat = ("t 1\ntask f(s: seq) returns (r: int)\n  ensures true\n{\n"
                "  var u: seq := s + s;\n  r := len(u);\n}\n")
    ok("seq-typed local variables are not supported" in refusal(concat), "a concatenation")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
