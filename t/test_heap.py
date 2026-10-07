#!/usr/bin/env python3
"""test_heap.py: SPEC.md "Heap (v1)" (PREDICT T46), arrays by reference: the notation, the checker, the
interpreter, the twins, the Python hand-back, Dafny's native lowering and the other kernels' refusal by name.
Standard library only, no kernel runs."""
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

CHECKS = 0
TASKS = ("reverse_in_place", "swap_at", "clamp_all", "ring_push")


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def load(name: str) -> dict:
    return tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))


def rules(src: str) -> set:
    return {e.split("[SPEC:")[0] and e for e in check_wf.check_wf(surface.parse(src))}


def test_notation_round_trips():
    for n in TASKS:
        t = load(n)
        ok(check_wf.check_wf(t) == [], f"{n} is well-formed")
        ok(surface.parse(surface.print_task(t)) == t, f"{n} prints and parses back")
    t = load("swap_at")
    ok(t["params"][0] == {"name": "a", "type": "array"} and t["modifies"] == ["a"], "an array parameter and modifies")
    ok({"aset": ["a", {"var": "i"}, {"op": "at", "args": [{"var": "a"}, {"var": "j"}]}]} in t["body"], "a[i] := a[j]")
    ok("old" in str(t["ensures"]), "old(a) in an ensures")
    ok("modifies" not in load("clamp").keys() if (HERE / "tasks" / "clamp.t").exists() else True,
       "a task without arrays carries no modifies")


def test_checker_rules():
    head = "t 1\ntask f(a: array, s: seq) returns (r: int)\n"
    cases = {
        "array-param-only": head + "  ensures true\n{\n  var b: array := s;\n  r := 0;\n}\n",
        "array-assign": head + "  modifies a\n  ensures true\n{\n  a := s;\n  r := 0;\n}\n",
        "aset-modifies": head + "  requires len(a) > 0\n  ensures true\n{\n  a[0] := 1;\n  r := 0;\n}\n",
        "modifies-array": head + "  modifies s\n  ensures true\n{\n  r := 0;\n}\n",
        "old-position": head + "  ensures true\n{\n  r := len(old(a));\n}\n",
    }
    for rule, src in cases.items():
        errs = check_wf.check_wf(surface.parse(src))
        ok(any(check_wf.RULES[rule] in e for e in errs), f"{rule} refused by name: {errs}")
    nested = head + "  ensures len(old(old(a))) >= 0\n{\n  r := 0;\n}\n"
    ok(any("nested" in e for e in check_wf.check_wf(surface.parse(nested))), "old inside old")
    ok(check_wf.check_wf(surface.parse("t 1\ntask f(array: int) returns (r: int)\n  ensures true\n{\n  r := array;\n}\n"))
       == [], "`array` is still a name where no type is read")


def test_interpreter():
    task = load("swap_at")
    env = {"a": (1, 2, 3), "i": 0, "j": 2, "ok": None, interp.OLD_KEY: {"a": (1, 2, 3)}}
    interp.exec_body(task["body"], env, interp.funs_of(task, task["body"]), interp.St())
    ok(env["a"] == (3, 2, 1) and env["ok"] is True, f"the write in place: {env['a']}")
    ens_env = dict(env)
    ok(all(interp.ev(c, ens_env, {}, interp.St()) for c in task["ensures"]), "old(a) reads the entry contents")
    try:
        interp.exec_body([{"aset": ["a", {"int": 3}, {"int": 0}]}], {"a": (1,)}, {}, interp.St())
        ok(False, "a write outside the array is undefined")
    except interp.Undef:
        ok(True, "a write outside the array is undefined")
    try:
        interp.ev({"old": {"var": "a"}}, {"a": (1,)}, {}, interp.St())
        ok(False, "old with no entry state recorded decides nothing")
    except interp.Budget:
        ok(True, "old with no entry state recorded decides nothing")


def test_observable_and_witness():
    ref = interp.Reference(load("ring_push"))
    ok(ref.mods == ["buf"] and len(ref.heaps) == len(ref.points) > 0, "each point keeps the modified array's contents")
    tw, op, w = harness.twin_for(load("ring_push"))
    ok(tw is not None and w.get("_ens") is True and "_real_heap" in w, f"a twin, its witness with the heap: {w}")
    # a twin that only changes the array (the return the same) is still a different run
    task = load("reverse_in_place")
    loop = dict(task["body"][1]["while"])
    loop["body"] = [s for s in loop["body"] if not ("aset" in s and s["aset"][2] == {"var": "tmp"})]
    twin = [task["body"][0], {"while": loop}, task["body"][2]]
    w2 = interp.Reference(task).witness(twin)
    ok(w2 is not None and "_twin_heap" in w2, f"the array alone tells the twin apart: {w2}")
    ok("_real_heap" not in (harness.twin_for(load("index_of"))[2] or {}), "no heap fields without arrays")


def test_hand_back():
    for n in TASKS:
        t = load(n)
        src, fn = to_python.translate(t)
        ok("_t_aset(" in src, f"{n}: a write is _t_aset on the caller's list")
        r = to_python.check(t, src, fn)
        ok(r["agrees"], f"{n}: the hand-back agrees with t, the final list included: {r}")


def test_dafny():
    src = tlib.lower(load("swap_at"), "dafny")
    ok("method Swap_at(a: array<int>, i: int, j: int) returns (ok: bool)" in src and "  modifies a" in src,
       "an array<int> parameter, modifies")
    ok("a[i] := a[j];" in src and "old(a[..])" in src and "a.Length" in src, "writes, old, the array's own reads")
    two = surface.parse("t 1\ntask f(a: array, b: array) returns (r: int)\n  modifies a\n  ensures true\n"
                        "{\n  r := 0;\n}\n")
    ok("requires a != b" in tlib.lower(two, "dafny"), "the no-alias obligation stated")
    cert = tlib.lower(load("ring_push"), "dafny", twin_body=True)
    ok("lemma t_refutation_certificate()" in cert, "the twin's certificate")


def test_framac():
    # PREDICT T50: C pointers natively; old(a)[i] read at Pre through a \let-bound index; a whole old array refused
    src = tlib.lower(load("swap_at"), "framac")
    ok("int swap_at_t(int *a, int a_n, int i, int j)" in src and "requires \\valid(a + (0 .. a_n - 1));" in src
       and "assigns a[0 .. a_n - 1];" in src, "a written pointer: valid, assigns its elements")
    ok("a[i] = a[j];" in src and "\\at(a[t_old" in src and ", Pre))" in src, "a write; old(a)[j] at Pre")
    src = tlib.lower(load("offset_all"), "framac")
    ok("requires \\valid_read(b + (0 .. b_n - 1));" in src and "loop assigns a[0 .. a_n - 1], i;" in src,
       "a read-only array stays valid_read; the loop frames the written one")
    cert = tlib.lower(load("scale_all"), "framac", twin_body=True)
    ok("t_entry: ;" in cert and "\\at(a[t_old" in cert and "t_entry))" in cert, "the certificate's old reads its entry")
    try:
        tlib.lower(load("reverse_in_place"), "framac")
        ok(False, "a whole old array refuses")
    except NotImplementedError as e:
        ok("a whole array in old(...)" in str(e), f"refused by name: {e}")


def test_copy_in_copy_out():
    # PREDICT T53: the value kernels take the heap through tshape.desugar_heap; the rewrite computes what the in-place
    # program computes (result and final array) on every domain point
    import tshape
    for n in TASKS + ("scale_all", "offset_all", "relu_all"):
        t = load(n)
        t1, b1 = tshape.desugar_par(t, t["body"])
        nt, nb, _ = tshape.desugar_heap(t1, b1)
        ok(check_wf.check_wf({**nt, "body": nb}) == [], f"{n}: the rewrite is well-formed")
        ok(nt["returns"][0]["type"] == {"pair": [t["returns"][0]["type"], "seq"]}, f"{n}: returns (result, array)")
        ref, ref2 = interp.Reference(t), interp.Reference({**nt, "body": nb})
        m = t["modifies"][0]
        ok([(v, h[m]) for (_e, v), h in zip(ref.points, ref.heaps)] == [(v.a, v.b) for _e, v in ref2.points],
           f"{n}: the same result and final array everywhere")
    for k in ("verus", "lean", "rocq", "fstar", "spark"):
        src = tlib.lower(load("swap_at"), k)
        ok("t_out" in src or "F'Result.P_B" in src, f"{k} lowers the heap by the rewrite")
    two = surface.parse("t 1\ntask f(a: array, b: array) returns (r: int)\n  modifies a, b\n  ensures true\n"
                        "{\n  r := 0;\n}\n")
    try:
        tlib.lower(two, "lean")
        ok(False, "two written arrays refuse")
    except NotImplementedError as e:
        ok("two arrays" in str(e), f"two written arrays refuse by name: {e}")

if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
