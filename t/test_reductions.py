#!/usr/bin/env python3
"""test_reductions.py: SPEC.md "Reductions (v1)" (2026-10-07): any, all, max(s), min(s) and toset in the notation, the
checker, the interpreter (against Python's own), the twin ladder, the hand-back, the Dafny and Verus text; and the
census corrections of the same landing (a consumed generator, a class wrapper, a modelled import). Standard library
only; no kernel runs."""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_wf  # noqa: E402
import harness  # noqa: E402
import interp  # noqa: E402
import nl_census  # noqa: E402
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


def _ev(text: str, env: dict, params: str = "s: seq, b: seq<bool>", ret: str = "int"):
    task = _task(params, ret, "r := %s;" % text)
    return interp.ev(task["body"][0]["assign"][1], dict(env), {}, interp.St())


def _errs(text: str) -> list:
    return [str(e) for e in check_wf.check_wf(surface.parse(text))]


def test_notation_and_types():
    e = surface.parse_expr("max(s)")
    ok(e == {"op": "max", "args": [{"var": "s"}]} and surface.pexpr(e) == "max(s)", "max of one argument: %r" % (e,))
    ok(surface.pexpr(surface.parse_expr("max(a, b)")) == "max(a, b)", "max of two arguments stays")
    for text, ret in (("any(b)", "bool"), ("all(b)", "bool"), ("max(s)", "int"), ("min(s)", "int"), ("toset(s)", "set")):
        t = _task("s: seq, b: seq<bool>", ret, "r := %s;" % text, requires="len(s) > 0")
        ok(check_wf.check_wf(t) == [] and surface.parse(surface.print_task(t)) == t, "%s types as %s and round-trips" % (text, ret))
    t = _task("s: seq<real>", "real", "r := max(s);", requires="len(s) > 0")
    ok(check_wf.check_wf(t) == [], "max of a seq<real> is a real")
    t = _task("s: seq<bool>", "set<bool>", "r := toset(s);")
    ok(check_wf.check_wf(t) == [], "toset of a seq<bool> is a set<bool>")
    bad = _errs("t 1\ntask f(s: seq) returns (r: bool)\n  ensures true\n{ r := any(s); }\n")
    ok(any("wants a seq<bool>" in e for e in bad), "any of a seq of ints: %r" % bad)
    bad = _errs("t 1\ntask f(b: seq<bool>) returns (r: int)\n  ensures true\n{ r := max(b); }\n")
    ok(any("seq of ints or of reals" in e for e in bad), "max of a seq<bool>: %r" % bad)
    bad = _errs("t 1\ntask f(x: int) returns (r: int)\n  ensures true\n{ r := max(x); }\n")
    ok(any("seq of ints or of reals" in e for e in bad), "max of one int: %r" % bad)


def test_values_are_pythons():
    for s in ((), (3,), (3, 1, 4), (-2, -5)):
        if s:
            ok(_ev("max(s)", {"s": s, "b": ()}) == max(s) and _ev("min(s)", {"s": s, "b": ()}) == min(s), "extrema of %r" % (s,))
        ok(_ev("toset(s)", {"s": s, "b": ()}, ret="set") == frozenset(s), "toset of %r" % (s,))
    for b in ((), (True,), (False,), (True, False)):
        ok(_ev("any(b)", {"s": (), "b": b}, ret="bool") is any(b) and _ev("all(b)", {"s": (), "b": b}, ret="bool") is all(b),
           "any/all of %r" % (b,))
    try:
        _ev("max(s)", {"s": (), "b": ()})
        ok(False, "max of an empty seq must be undefined")
    except interp.Undef:
        pass
    ok(_ev("all([x > 0 for x in s])", {"s": (1, 2), "b": ()}, ret="bool") is True
       and _ev("any([x > 5 for x in s])", {"s": (1, 2), "b": ()}, ret="bool") is False, "a reduction over a comprehension")


def test_twins_handback_and_kernel_text():
    for name in ("all_positive", "has_negative", "largest", "members_upto"):
        task = tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))
        ok(check_wf.check_wf(task) == [], f"{name} well-formed")
        twin, got, w = harness.twin_for(task)
        ok(twin is not None and w.get("_ens") is True, f"{name}: a twin with a witness that fails the ensures: {got} {w}")
    src, _fn = to_python.translate(tasks_io.load_task(str(HERE / "tasks" / "largest.t")))
    ok("max(s)" in src, "max(s) hands back as Python's max: %s" % src)
    src, _fn = to_python.translate(_task("s: seq", "set", "r := toset(s);"))
    ok("frozenset(s)" in src, "toset hands back as frozenset: %s" % src)

    def lowered(name, kernel):
        out = subprocess.run([sys.executable, str(HERE / "cli.py"), "lower", str(HERE / "tasks" / f"{name}.t"),
                              "--kernel", kernel], capture_output=True, text=True, timeout=120)
        return out.stdout + out.stderr
    d = lowered("largest", "dafny")
    ok("function t_maxs(s: seq<int>): int" in d and "requires |s| > 0" in d and "ensures t_maxs(s) in s" in d,
       "largest in Dafny: the Std's Max shape: %s" % d)
    d = lowered("all_positive", "dafny")
    ok("function t_all(s: seq<bool>): bool { forall i :: 0 <= i < |s| ==> s[i] }" in d, "all in Dafny: %s" % d)
    d = lowered("members_upto", "dafny")
    ok("function t_toset<T>(s: seq<T>): set<T> { set x: T | x in s }" in d, "toset in Dafny: %s" % d)
    v = lowered("largest", "verus")
    ok("s.max()" in v and "s.max_ensures();" in v, "largest in Verus: vstd's max and its lemma: %s" % v)
    v = lowered("has_negative", "verus")
    ok("(exists|t_qi: int| 0 <= t_qi && t_qi < s.len() && (s[t_qi] < (0int)))" in v,
       "any over a comprehension is the quantifier in Verus: %s" % v)
    v = lowered("members_upto", "verus")
    ok(".to_set()" in v and "broadcast use t_toset_sub;" in v, "toset in Verus with its membership lemmas: %s" % v)
    for kernel in ("spark", "fstar"):
        out = lowered("largest", kernel)
        ok("not lowered yet" in out, "%s abstains by name: %s" % (kernel, out[:160]))


def test_census_corrections():
    tags = nl_census.solution_tags("def f(s):\n    return sum(x for x in s if x > 0) + max(x for x in s)\n", "f", True)
    ok(tags.get("generator-consumed") and not tags.get("generator"), "a generator under sum/max is consumed: %r" % tags)
    tags = nl_census.solution_tags("def f(s):\n    g = (x for x in s)\n    return next(g)\n", "f", True)
    ok(tags.get("generator") and not tags.get("generator-consumed"), "a generator bound to a name is the gap: %r" % tags)
    tags = nl_census.solution_tags("def f(n):\n    yield n\n", "f", True)
    ok(tags.get("generator"), "a yield is the gap: %r" % tags)
    tags = nl_census.solution_tags("class Solution:\n    def f(self, s):\n        return self.g(s)\n    def g(self, s):\n        return len(s)\n", "f", True)
    ok(tags.get("class-wrapper") and not tags.get("class"), "a method-only class is a wrapper: %r" % tags)
    tags = nl_census.solution_tags("class C:\n    def __init__(self):\n        self.n = 0\n    def f(self, s):\n        self.n += 1\n        return self.n\n", "f", True)
    ok(tags.get("class") and not tags.get("class-wrapper"), "a stateful class is the gap: %r" % tags)
    tags = nl_census.solution_tags("from dataclasses import dataclass\n@dataclass\nclass P:\n    x: int\ndef f(p):\n    return p.x\n", "f", True)
    ok(tags.get("record"), "a dataclass is the gap record: %r" % tags)
    tags = nl_census.solution_tags("from collections import Counter\ndef f(s):\n    return Counter(s)\n", "f", True)
    ok(tags.get("import-modelled") and not tags.get("import"), "collections is modelled: %r" % tags)
    tags = nl_census.solution_tags("import itertools\ndef f(s):\n    return list(itertools.permutations(s))\n", "f", True)
    ok(tags.get("import") and not tags.get("import-modelled"), "itertools is the gap: %r" % tags)
    tags = nl_census.solution_tags("from functools import lru_cache\n@lru_cache\ndef f(n):\n    return n\n", "f", True)
    ok(tags.get("import-modelled"), "lru_cache alone is modelled: %r" % tags)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
