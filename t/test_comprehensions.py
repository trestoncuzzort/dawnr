#!/usr/bin/env python3
"""test_comprehensions.py: SPEC.md "Comprehensions (v1)" (2026-10-06) in the notation, the checker, the interpreter,
the twin ladder and the Python hand-back. Standard library only."""
from __future__ import annotations

import sys
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


def _task(params: str, ret: str, body: str, ensures: str = "true") -> dict:
    return surface.parse("t 1\ntask f(%s) returns (r: %s)\n  ensures %s\n{ %s }\n" % (params, ret, ensures, body))


def _ev(text: str, env: dict | None = None, params: str = "", ret: str = "seq"):
    task = _task(params, ret, "r := %s;" % text)
    return interp.ev(task["body"][0]["assign"][1], dict(env or {}), {}, interp.St())


def test_forms_parse_and_print():
    t = _task("s: seq", "seq", "r := [x for x in s if x % 2 == 0];")
    c = t["body"][0]["assign"][1]["comp"]
    ok(c["var"] == "x" and c["seq"] == {"var": "s"} and c["body"] == {"var": "x"} and c["cond"]["op"] == "==", "a filter: %r" % c)
    ok(check_wf.check_wf(t) == [] and surface.parse(surface.print_task(t)) == t
       and "[x for x in s if x % 2 == 0]" in surface.print_task(t), "prints back and reparses")
    t = _task("s: seq", "seq", "r := [2 * x for x in s];")
    ok(t["body"][0]["assign"][1]["comp"]["cond"] == {"bool": True} and "if" not in surface.print_task(t).splitlines()[-2],
       "no condition is `true`, printed without `if`")
    t = _task("n: int", "seq", "r := [i * i for i in [0, n)];")
    c = t["body"][0]["assign"][1]["comp"]
    ok("lo" in c and c["lo"] == {"int": 0} and c["hi"] == {"var": "n"} and check_wf.check_wf(t) == [], "a range comprehension")
    t = _task("", "seq", "r := [y for y in [1, 2] if y > 1];")
    ok(t["body"][0]["assign"][1]["comp"]["seq"] == {"op": "seq", "args": [{"int": 1}, {"int": 2}]}, "a display as the source")
    t = _task("", "seq", "r := [y for y in [1] if y > 0];")
    ok(t["body"][0]["assign"][1]["comp"]["seq"] == {"op": "seq", "args": [{"int": 1}]}, "a one-element display as the source")
    t = _task("s: seq<bool>", "seq<bool>", "r := [not b for b in s];")
    ok(check_wf.check_wf(t) == [], "the bound variable takes the element type")
    t = _task("m: seq<seq>", "seq", "r := [len(row) for row in m];")
    ok(check_wf.check_wf(t) == [], "a row of a seq<seq>")


def test_typing_refusals():
    for params, ret, body, msg in (("n: int", "seq", "r := [x for x in n];", "ranges over a seq"),
                                   ("s: seq", "seq", "r := [x for x in s if x];", "condition is not bool"),
                                   ("s: seq, x: int", "seq", "r := [x for x in s];", "shadows"),
                                   ("s: seq", "seq", "r := [x for x in [0, s)];", "not int"),
                                   ("s: seq", "int", "r := [x for x in s];", "assign")):
        errs = check_wf.check_wf(_task(params, ret, body))
        ok(any(msg in e for e in errs), "refused %s with %r: %r" % (body, msg, errs))
    t = _task("s: seq", "seq<bool>", "r := [x > 0 for x in s];")
    ok(check_wf.check_wf(t) == [], "the result takes the body's type")


def test_interpreter():
    ok(_ev("[x for x in s if x % 2 == 0]", {"s": (1, 2, 3, 4)}, "s: seq") == (2, 4), "filter")
    ok(_ev("[2 * x for x in s]", {"s": (1, 2, 3)}, "s: seq") == (2, 4, 6), "map")
    ok(_ev("[i * i for i in [0, n)]", {"n": 4}, "n: int") == (0, 1, 4, 9), "range")
    ok(_ev("[i for i in [3, 1)]", {}, "") == (), "an empty range")
    ok(_ev("[x for x in s if x > 10]", {"s": (1, 2)}, "s: seq") == (), "nothing kept")
    try:
        _ev("[s[i] for i in [0, len(s) + 1)]", {"s": (1,)}, "s: seq")
        ok(False, "undefined body is undefined")
    except interp.Undef:
        ok(True, "undefined body is undefined")


def test_twins_and_guard():
    for name, op in (("evens", "off-by-one"), ("doubled", "off-by-one"), ("squares", "off-by-one")):
        task = surface.parse_file(str(HERE / "tasks" / f"{name}.t"))
        ok(check_wf.check_wf(task) == [], f"{name} is well-formed")
        ok(surface.parse(surface.print_task(task)) == task, f"{name} round-trips")
        twin, got, w = harness.twin_for(task)
        ok(twin is not None and got.split("#")[0] == op and w.get("_ens") is True, f"{name}: twin {got}, witness {w}")
    task = surface.parse_file(str(HERE / "tasks" / "evens.t"))
    for kernel in ("spark", "fstar", "lean", "rocq", "framac"):
        try:
            tshape.abstain_unless_carried(task, task["body"], kernel, carried=frozenset({"real"}))
            ok(False, "%s abstains on comprehensions" % kernel)
        except NotImplementedError as ex:
            ok("comprehension" in str(ex), "abstains by name: %s" % ex)
    tshape.abstain_unless_carried(task, task["body"], "k", carried=frozenset({"real", "comp"}))
    ok(True, "a kernel carrying comprehensions passes")


def test_kernel_text():
    import subprocess
    def lowered(name, kernel):
        out = subprocess.run([sys.executable, str(HERE / "cli.py"), "lower", str(HERE / "tasks" / f"{name}.t"),
                              "--kernel", kernel], capture_output=True, text=True, timeout=120)
        return out.stdout + out.stderr
    d = lowered("evens", "dafny")
    ok("function t_comp1(t_s: seq<int>, t_n: int): (t_r: seq<int>)" in d and "ensures |t_r| <= t_n" in d
       and "ensures forall t_i :: 0 <= t_i < |t_r| ==> ((t_r[t_i] % 2) == 0)" in d and "t_comp1(s, |s|)" in d,
       "evens in Dafny: the filter function in prefix form and its ensures (SPEC.md Comprehensions, the Dafny paragraph)")
    d = lowered("doubled", "dafny")
    ok("ensures |t_r| == t_n" in d and "t_r[t_i] == (2 * t_s[t_i])" in d, "doubled in Dafny: the map ensures")
    d = lowered("squares", "dafny")
    ok("function t_ix(t_i: int): int { t_i }" in d and "function t_comp1(t_a: int, t_n: int): (t_r: seq<int>)" in d
       and "t_comp1(0, (n - 0))" in d and "(t_a + t_ix(t_i))" in d,
       "squares in Dafny: a range comprehension in prefix form with the identity-function index (SPEC.md Comprehensions)")
    v = lowered("evens", "verus")
    ok("pub open spec fn t_comp1(t_s: Seq<int>) -> Seq<int>" in v and "pub broadcast proof fn t_comp1_spec" in v
       and "reveal_with_fuel(t_comp1, 6);" in v and "broadcast use t_comp1_spec;" in v, "evens in Verus: the spec fn, its lemma, fuel and use")
    ok("comprehensions are not lowered yet" in lowered("evens", "spark"), "spark abstains by name")
    # F* carries maps since PREDICT T16 and refuses a filter by name (test_fstar_comp.py)
    ok("filtered comprehension is not lowered yet" in lowered("evens", "fstar"), "fstar refuses a filter by name")


def test_hand_back():
    src, _fn = to_python.translate(_task("s: seq", "seq", "r := [x for x in s if x % 2 == 0];"))
    ok("tuple(x for x in s if" in src, "a filter hands back as a generator in a tuple: %s" % src)
    src, _fn = to_python.translate(_task("n: int", "seq", "r := [i * i for i in [0, n)];"))
    ok("for i in range(0, n)" in src, "a range hands back as range")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"OK: {CHECKS} checks")
