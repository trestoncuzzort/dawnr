#!/usr/bin/env python3
"""test_concurrency.py: SPEC.md "Concurrency (v1)" (PREDICT T47), parallel loops: the notation, the race-freedom
rules, schedule independence in the interpreter (the reverse schedule against the sequential rewrite), the thread-pool
hand-back and the kernels' sequential lowering. Standard library only, no kernel runs."""
from __future__ import annotations

import sys
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
import tshape  # noqa: E402

CHECKS = 0
TASKS = ("scale_all", "offset_all", "relu_all")


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def load(name: str) -> dict:
    return tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))


def errs_of(body: str) -> list:
    return check_wf.check_wf(surface.parse("t 1\ntask f(a: array, b: array) returns (r: int)\n  modifies a\n"
                                           "  requires len(a) == len(b)\n  ensures true\n{\n  r := 0;\n" + body + "}\n"))


def test_notation():
    for n in TASKS:
        t = load(n)
        ok(check_wf.check_wf(t) == [], f"{n} is well-formed")
        ok(surface.parse(surface.print_task(t)) == t, f"{n} prints and parses back")
    par = load("scale_all")["body"][0]["par"]
    ok(par["var"] == "i" and par["lo"] == {"int": 0} and len(par["invariants"]) == 3, f"the par node: {par}")


def test_race_rules():
    race = check_wf.RULES["par-race"]
    for body, why in (("  parallel for i in [0, len(a)) {\n    a[0] := 1;\n  }\n", "another element written"),
                      ("  parallel for i in [1, len(a)) {\n    a[i] := a[i - 1];\n  }\n", "another element read"),
                      ("  parallel for i in [0, len(a)) {\n    r := r + 1;\n  }\n", "a shared scalar written"),
                      ("  parallel for i in [0, len(a)) {\n    parallel for j in [0, 1) {\n      a[i] := 0;\n    }\n  }\n",
                       "a parallel loop inside one"),
                      ("  parallel for i in [0, a[0]) {\n    a[i] := 0;\n  }\n", "a bound read from a written array")):
        ok(any(race in e for e in errs_of(body)), f"{why} is a race: {errs_of(body)}")
    ok(any(check_wf.RULES["par-exit"] in e for e in errs_of("  parallel for i in [0, len(a)) {\n    break;\n  }\n")),
       "a break of the parallel loop")
    fine = ("  parallel for i in [0, len(a)) {\n    var t2: int := a[i] + b[i] + len(a);\n"
            "    var k: int := 0;\n    while k < 2\n      invariant 0 <= k and k <= 2\n      decreases 2 - k\n"
            "    {\n      t2 := t2 + 1;\n      k := k + 1;\n    }\n    a[i] := t2;\n  }\n")
    ok(errs_of(fine) == [], f"own element, own locals, a read-only array, an inner loop: {errs_of(fine)}")


def test_schedules_agree():
    # the interpreter's reverse schedule against the sequential rewrite the kernels verify, on every domain point
    for n in TASKS:
        t = load(n)
        _t2, seq_body = tshape.desugar_par(t, t["body"])
        ref = interp.Reference(t)
        ok(len(ref.points) > 10, f"{n}: points to compare on")
        seq = {**t, "body": seq_body}
        ref2 = interp.Reference(seq)
        ok([v for _e, v in ref.points] == [v for _e, v in ref2.points] and ref.heaps == ref2.heaps,
           f"{n}: the reverse schedule and the sequential loop agree everywhere")


def test_desugar_names():
    t = surface.parse("t 1\ntask f(a: array) returns (r: int)\n  modifies a\n  ensures true\n{\n"
                      "  parallel for i in [0, len(a)) {\n    a[i] := 1;\n  }\n"
                      "  parallel for i in [0, len(a)) {\n    a[i] := a[i] + 1;\n  }\n  r := 0;\n}\n")
    ok(check_wf.check_wf(t) == [], "two parallel loops with one index name")
    _t2, b = tshape.desugar_par(t, t["body"])
    ok(check_wf.check_wf({**t, "body": b}) == [], "and their rewrite declares two variables")
    ok(tshape.desugar_par(load("clamp_all"), load("clamp_all")["body"])[1] == load("clamp_all")["body"],
       "a body without parallel loops is unchanged")


def test_twins_and_hand_back():
    for n in TASKS:
        t = load(n)
        tw, op, w = harness.twin_for(t)
        ok(tw is not None and w.get("_ens") is True, f"{n}: a twin and its witness ({op})")
        src, fn = to_python.translate(t)
        ok("_t_par(" in src and "ThreadPoolExecutor" in src, f"{n}: the iterations on a thread pool")
        r = to_python.check(t, src, fn)
        ok(r["agrees"], f"{n}: the hand-back agrees with t: {r}")
    ns: dict = {}
    src, fn = to_python.translate(load("scale_all"))
    exec(compile(src, "<hand-back>", "exec"), ns)
    a = list(range(100))
    ok(ns[fn](a, 3) == 100 and a == [3 * x for x in range(100)], "on real threads, outside the sandbox")


def test_kernels():
    d = tlib.lower(load("offset_all"), "dafny")
    ok("while (i < a.Length)" in d and "a[i] := (a[i] - b[i]);" in d and "requires a != b" in d,
       "Dafny verifies the sequential loop")
    for k in ("verus", "lean", "rocq", "fstar", "spark", "framac"):
        try:
            tlib.lower(load("scale_all"), k)
            ok(False, f"{k} refuses")
        except NotImplementedError as e:
            ok("arrays by reference" in str(e), f"{k} refuses by name (the array): {e}")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
