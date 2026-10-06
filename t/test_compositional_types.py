#!/usr/bin/env python3
"""test_compositional_types.py: SPEC.md "Compositional types (v1)" (2026-10-06) in the notation, the checker, the
interpreter and the twin ladder. Standard library only; `python3 t/test_compositional_types.py` exits nonzero on a
failure and prints OK with the count otherwise."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_wf  # noqa: E402
import harness  # noqa: E402
import interp  # noqa: E402
import surface  # noqa: E402

CHECKS = 0


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def test_types_round_trip():
    for text in ("seq<bool>", "seq<seq<seq>>", "seq<(int, int)>", "(int, seq, bool)", "((int, int), (int, int))",
                 "set<seq>", "set<(int, bool)>", "(bool, set<seq>, seq<seq>)"):
        src = "t 1\ntask f(x: %s) returns (r: %s)\n  ensures r == x\n{ r := x; }\n" % (text, text)
        task = surface.parse(src)
        ok(check_wf.check_wf(task) == [], "well-formed: %s" % text)
        ok(surface.print_task(task).count(text) == 2, "prints back as itself: %s" % text)
        ok(surface.parse(surface.print_task(task)) == task, "round trip: %s" % text)
    for bad in ("seq<int>", "set<int>", "(int)"):
        try:
            surface.parse("t 1\ntask f(x: %s) returns (r: int)\n  ensures true\n{ r := 0; }\n" % bad)
            ok(False, "refused spelling: %s" % bad)
        except surface.SurfaceError:
            ok(True, "refused spelling: %s" % bad)
    for bad in ({"seq": "int"}, {"set": "int"}, {"tuple": ["int", "int"]}, {"tuple": ["int"]}, {"seq": "x"}):
        ok(not check_wf._valid_type(bad), "checker refuses %r" % (bad,))


def test_tuple_and_projection():
    task = surface.parse("t 1\ntask f(a: int, b: seq, c: bool) returns (r: (int, seq, bool))\n"
                         "  ensures r.0 == a\n  ensures r.1 == b\n  ensures r.2 == c\n{ r := (a, b, c); }\n")
    ok(check_wf.check_wf(task) == [], "tuple task is well-formed")
    ok(task["returns"][0]["type"] == {"tuple": ["int", "seq", "bool"]}, "tuple type parsed")
    ok(task["ensures"][2]["args"][0] == {"op": "proj", "args": [{"var": "r"}, {"int": 2}]}, ".2 is proj")
    ok(task["ensures"][0]["args"][0] == {"op": "fst", "args": [{"var": "r"}]}, ".0 is fst on a tuple")
    errs = check_wf.check_wf(surface.parse("t 1\ntask f(a: int) returns (r: (int, int, int))\n  ensures r.3 == a\n"
                                           "{ r := (a, a, a); }\n"))
    ok(any("projection" in e for e in errs), "projection past the end is refused: %r" % errs)
    errs = check_wf.check_wf({"t": 1, "name": "f", "params": [{"name": "a", "type": "int"}],
                              "returns": [{"name": "r", "type": "int"}], "requires": [], "ensures": [{"bool": True}],
                              "body": [{"assign": ["r", {"op": "proj", "args": [{"op": "tuple", "args": [
                                  {"var": "a"}, {"var": "a"}, {"var": "a"}]}, {"int": 1}]}]}]})
    ok(any("projection" in e for e in errs), "proj 1 is non-canonical (snd): %r" % errs)


def test_seq_and_set_of_anything():
    task = surface.parse("t 1\ntask f(s: seq<bool>, w: set<seq>) returns (r: (seq<bool>, set<seq>))\n"
                         "  ensures r.0 == s + [true]\n  ensures r.1 == union(w, {[97]})\n"
                         "{ r := (s + [true], union(w, {\"a\"})); }\n")
    ok(check_wf.check_wf(task) == [], "seq<bool> and set<seq> type: %r" % check_wf.check_wf(task))
    env = {"s": (True, False), "w": frozenset({(97,)})}
    funs = interp.funs_of(task, task["body"])
    v = interp.ev(task["body"][0]["assign"][1], env, funs, interp.St())
    ok(isinstance(v, interp.Pair) and v.a == (True, False, True) and v.b == frozenset({(97,)}), "evaluates: %r" % (v,))
    errs = check_wf.check_wf(surface.parse("t 1\ntask f(s: seq<bool>) returns (r: seq<bool>)\n  ensures true\n"
                                           "{ r := s + [1]; }\n"))
    ok(any("over non-int" in e or "one type" in e for e in errs), "a bool seq plus an int seq is refused: %r" % errs)
    errs = check_wf.check_wf(surface.parse("t 1\ntask f(w: set<seq>) returns (r: bool)\n  ensures true\n"
                                           "{ r := 3 in w; }\n"))
    ok(any("in wants" in e for e in errs), "an int in a set of strings is refused: %r" % errs)


def test_witness_ladders_and_tags():
    lad = interp.ladders({"params": [], "returns": [{"name": "r", "type": "int"}], "requires": [], "ensures": [], "body": []})
    bools = interp._ladder(lad, {"seq": "bool"})
    ok(bools[0] == () and (True,) in bools and (False, True) in bools, "a seq<bool> ladder")
    trips = interp._ladder(lad, {"tuple": ["int", "bool", "int"]})
    ok(all(isinstance(t, interp.Tup) and len(t.items) == 3 for t in trips) and len(trips) > 10, "a tuple ladder")
    strs = interp._ladder(lad, {"set": "seq"})
    ok(frozenset() in strs and all(isinstance(x, frozenset) for x in strs), "a set<seq> ladder")
    deep = interp._ladder(lad, {"seq": {"seq": "seq"}})
    ok(deep[0] == () and any(len(d) == 2 for d in deep), "a three-level seq ladder")
    ok(interp._tv((True,)) != interp._tv((1,)), "a seq of bools is not a seq of ints")
    ok(interp._tv(interp.Pair(1, 2)) != interp._tv((1, 2)), "a pair is not a seq")
    ok(interp._ladder(lad, {"pair": ["int", "int"]})[:3] == tuple(interp._dedup(
        [interp.Pair(a, b) for a, b in interp._shell([lad["int"], lad["int"]], interp.PAIR_SHELL)]))[:3],
        "the pair ladder of base types is what it was")


def test_twin_of_the_committed_tasks():
    for name in ("sort3", "zip_pairs", "signs", "words_seen", "swap_ends"):
        task = surface.parse_file(str(HERE / "tasks" / f"{name}.t"))
        ok(check_wf.check_wf(task) == [], f"{name} is well-formed")
        twin = harness.make_twin(task["body"], task)
        ok(twin is not None and twin[1] is not None, f"{name} has a twin with a witness: {str(twin)[:120]}")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"OK: {CHECKS} checks")
