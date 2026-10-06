#!/usr/bin/env python3
"""test_maps.py: SPEC.md "Maps (v1)" (2026-10-06): the type map<K, V>, the display, lookup, update, membership, len,
keys and remove in the notation, the checker, the interpreter (against Python's dict), the witness ladder, the twin
ladder, the shape guard, the Python hand-back and the Dafny text. Standard library only; no kernel runs."""
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


def _task(params: str, ret: str, body: str, ensures: str = "true", requires: str = "true") -> dict:
    return surface.parse("t 1\ntask f(%s) returns (r: %s)\n  requires %s\n  ensures %s\n{ %s }\n"
                         % (params, ret, requires, ensures, body))


def _ev(text: str, env: dict | None = None, params: str = "m: map<int, int>, k: int", ret: str = "int"):
    task = _task(params, ret, "r := %s;" % text)
    return interp.ev(task["body"][0]["assign"][1], dict(env or {}), {}, interp.St())


def _errs(text: str) -> list:
    return [str(e) for e in check_wf.check_wf(surface.parse(text))]


M = interp.MapV.of([(1, 10), (2, 20)])


def test_notation_and_types():
    t = _task("m: map<int, int>, k: int", "int", "r := m[k];", requires="k in m")
    ok(t["params"][0]["type"] == {"map": ["int", "int"]} and check_wf.check_wf(t) == [], "map<int, int> parses and types")
    ok(surface.parse(surface.print_task(t)) == t and "map<int, int>" in surface.print_task(t), "round trip")
    e = surface.parse_expr("map[1 := 2, x := y]")
    ok(e == {"op": "mapdisp", "args": [{"int": 1}, {"int": 2}, {"var": "x"}, {"var": "y"}]} and surface.pexpr(e) == "map[1 := 2, x := y]",
       "the display: %r" % (e,))
    ok(surface.pexpr(surface.parse_expr("map[]")) == "map[]", "the empty display")
    t = _task("s: seq<bool>", "map<seq<bool>, (int, int)>", "r := map[s := (1, 2)];")
    ok(check_wf.check_wf(t) == [] and surface.parse(surface.print_task(t)) == t, "compound keys and values: %r" % check_wf.check_wf(t))
    t = _task("m: map<int, int>", "set", "r := keys(m);")
    ok(check_wf.check_wf(t) == [], "keys(m) is a set of the key type")
    t = _task("m: map<int, int>", "map<int, int>", "r := remove(m[3 := 4], 3);")
    ok(check_wf.check_wf(t) == [], "remove and update keep the map's type")
    bad = _errs("t 1\ntask f(m: map<int, int>, b: bool) returns (r: int)\n  ensures true\n{ r := m[b]; }\n")
    ok(any("key of the map's key type" in e for e in bad), "a key of the wrong type: %r" % bad)
    bad = _errs("t 1\ntask f(x: int) returns (r: map<int, int>)\n  ensures true\n{ r := map[1 := 2, true := 3]; }\n")
    ok(any("keys must all be of one type" in e for e in bad), "mixed keys: %r" % bad)
    bad = _errs("t 1\ntask f(x: int) returns (r: map<int, int>)\n  ensures true\n{ r := map[1 := 2][3 := true]; }\n")
    ok(any("value of the map's value type" in e for e in bad), "a value of the wrong type: %r" % bad)
    bad = _errs("t 1\ntask f(s: seq) returns (r: int)\n  ensures true\n{ r := len(keys(s)); }\n")
    ok(any("keys of a non-map" in e for e in bad), "keys of a seq: %r" % bad)


def test_values_are_pythons():
    d = {1: 10, 2: 20}
    ok(_ev("m[k]", {"m": M, "k": 2}) == d[2] and _ev("len(m)", {"m": M, "k": 0}) == len(d), "lookup and len")
    ok(_ev("k in m", {"m": M, "k": 1}, ret="bool") is True and _ev("k in m", {"m": M, "k": 3}, ret="bool") is False, "membership")
    ok(interp._j(_ev("m[k := 5]", {"m": M, "k": 2}, ret="map<int, int>")) == [[1, 10], [2, 5]], "update overwrites")
    ok(interp._j(_ev("m[k := 5]", {"m": M, "k": 7}, ret="map<int, int>")) == [[1, 10], [2, 20], [7, 5]], "update inserts")
    ok(_ev("keys(m)", {"m": M, "k": 0}, ret="set") == frozenset({1, 2}), "keys")
    ok(interp._j(_ev("remove(m, k)", {"m": M, "k": 1}, ret="map<int, int>")) == [[2, 20]], "remove")
    ok(interp._j(_ev("remove(m, k)", {"m": M, "k": 9}, ret="map<int, int>")) == [[1, 10], [2, 20]], "remove of an absent key is total")
    ok(_ev("map[1 := 2, 1 := 3][1]", {"m": M, "k": 0}) == 3, "the rightmost of two equal keys wins")
    ok(_ev("map[1 := 2] == map[1 := 2]", {"m": M, "k": 0}, ret="bool") is True
       and _ev("remove(map[1 := 2, 3 := 4], 3) == map[1 := 2]", {"m": M, "k": 0}, ret="bool") is True, "extensional ==")
    try:
        _ev("m[k]", {"m": M, "k": 3})
        ok(False, "m[k] with k not in m must be undefined")
    except interp.Undef:
        pass
    ok(interp._tv(M) != interp._tv(((1, 10), (2, 20))), "a map is never a seq of pairs")


def test_ladder_and_twins():
    task = _task("m: map<int, int>, k: int", "int", "r := if k in m then m[k] else 0;")
    lad = interp.ladders(task)
    maps = interp._ladder(lad, {"map": ["int", "int"]})
    ok(maps[0] == interp.MapV.of([]) and len(maps) >= 8 and all(isinstance(x, interp.MapV) for x in maps),
       "the ladder starts at the empty map and holds small maps: %d" % len(maps))
    for name in ("lookup_or", "put_key", "index_map"):
        t = tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))
        ok(check_wf.check_wf(t) == [], f"{name} well-formed")
        twin, got, w = harness.twin_for(t)
        ok(twin is not None and w.get("_ens") is True, f"{name}: a twin with a witness that fails the ensures: {got} {w}")
        ok(tshape.beyond_v1(t["params"][0]["type"]) or tshape.beyond_v1(t["returns"][0]["type"]), f"{name} has a type beyond the old list")
    src, _fn = to_python.translate(tasks_io.load_task(str(HERE / "tasks" / "put_key.t")))
    ok("_t_update(" in src and "isinstance(s, dict)" in src, "the hand-back's dict-aware update: %s" % src)
    src, _fn = to_python.translate(_task("m: map<int, int>, k: int", "map<int, int>", "r := remove(m, k);"))
    ok("_t_mapdel(m, k)" in src and "if kk != k" in src, "the hand-back's removal: %s" % src)
    src, _fn = to_python.translate(_task("x: int", "map<int, int>", "r := map[1 := x];"))
    ok("{(1): x}" in src.replace(" ", "") or "{1: x}" in src, "a display hands back as a dict: %s" % src)


def test_kernel_text():
    def lowered(name, kernel):
        out = subprocess.run([sys.executable, str(HERE / "cli.py"), "lower", str(HERE / "tasks" / f"{name}.t"),
                              "--kernel", kernel], capture_output=True, text=True, timeout=120)
        return out.stdout + out.stderr
    d = lowered("put_key", "dafny")
    ok("map<int, int>" in d and "m[k := v]" in d and "(r - {k})" in d and "|r| >= |m|" in d.replace("(", "").replace(")", ""),
       "put_key in Dafny: the type, the update, the domain subtraction, the cardinality: %s" % d)
    d = lowered("index_map", "dafny")
    ok("map[]" in d and "m[x := i]" in d, "index_map in Dafny: the empty display and the update: %s" % d)
    v = lowered("put_key", "verus")
    ok("Map<int, int>" in v and "m.insert(k, v)" in v and "r.remove(k)" in v and "r.dom().contains(k)" in v,
       "put_key in Verus: the type, insert, remove, dom().contains: %s" % v)
    for kernel in ("spark", "fstar", "lean"):
        out = lowered("lookup_or", kernel)
        ok("map<int, int> is not lowered yet" in out, "%s abstains by name on the type: %s" % (kernel, out[:200]))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
