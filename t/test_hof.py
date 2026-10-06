#!/usr/bin/env python3
"""test_hof.py: SPEC.md "Higher-order calls (v1)" (2026-10-06): fold, sort_by, max_by and min_by with a lambda in the
notation, the checker, the interpreter (against Python's functools.reduce, sorted, max and min), the twin ladder,
the hand-back, the Dafny and Verus text and certificates, and the census reading of the same landing (a lambda in a
library position or bound to a name, a nested def that neither rebinds nor mutates what it captured). Standard
library only; no kernel runs."""
from __future__ import annotations

import functools
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_wf  # noqa: E402
import harness  # noqa: E402
import interp  # noqa: E402
import lower_dafny  # noqa: E402
import lower_verus  # noqa: E402
import nl_census  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402
import to_python  # noqa: E402

CHECKS = 0
TASKS = ("longest_row", "cheapest", "by_second", "weighted_sum")


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def _task(params: str, ret: str, body: str, ensures: str = "true", requires: str = "true") -> dict:
    return surface.parse("t 1\ntask f(%s) returns (r: %s)\n  requires %s\n  ensures %s\n{ %s }\n"
                         % (params, ret, requires, ensures, body))


def _ev(text: str, env: dict, params: str, ret: str):
    task = _task(params, ret, "r := %s;" % text)
    return interp.ev(task["body"][0]["assign"][1], dict(env), {}, interp.St())


def _errs(params: str, ret: str, body: str) -> list:
    return [str(e) for e in check_wf.check_wf(_task(params, ret, body))]


def test_notation_round_trip():
    for text in ("fold((a, x) => a + x, 0, s)", "max_by(rows, w => len(w))", "min_by(ps, p => p.1)",
                 "sort_by(ps, p => p.1)", "fold((a, y) => a + w * y, 0, s[0..i])"):
        e = surface.parse_expr(text)
        ok(surface.pexpr(e) == text and surface.parse_expr(surface.pexpr(e)) == e, "round trip of %s: %r" % (text, e))
    e = surface.parse_expr("max_by(rows, w => len(w))")
    ok(e == {"op": "max_by", "args": [{"var": "rows"}, {"lam": {"vars": ["w"], "body": {"op": "len",
                                                                                         "args": [{"var": "w"}]}}}]},
       "the lambda node: %r" % (e,))
    for name in TASKS:
        task = tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))
        ok(check_wf.check_wf(task) == [] and surface.parse(surface.print_task(task)) == task,
           f"{name} is well-formed and round-trips")


def test_checker_rules():
    bad = _errs("s: seq", "int", "r := len([x => x for y in s]);")
    ok(any("lambda" in e for e in bad), "a lambda outside a library call: %r" % bad)
    bad = _errs("s: seq", "int", "r := fold(x => x, 0, s);")
    ok(any("lambda of 2 parameter" in e for e in bad), "fold with a one-parameter lambda: %r" % bad)
    bad = _errs("s: seq", "int", "r := fold((a, x) => a > x, 0, s);")
    ok(any("fold's lambda returns" in e for e in bad), "fold whose body is not the accumulator's type: %r" % bad)
    bad = _errs("s: seq", "int", "r := max_by(s, x => x > 0);")
    ok(any("key is an int or a real" in e for e in bad), "a bool key: %r" % bad)
    bad = _errs("x: int", "int", "r := max_by(x, y => y);")
    ok(any("wants a seq" in e for e in bad), "max_by over an int: %r" % bad)
    bad = _errs("s: seq", "int", "r := fold((s, x) => s + x, 0, s);")
    ok(bad != [], "a lambda parameter shadowing a name in scope: %r" % bad)
    ok(_errs("s: seq<(int, int)>", "seq<(int, int)>", "r := sort_by(s, p => p.1);") == [], "sort_by over pairs types")
    ok(_errs("rows: seq<seq>", "seq", "r := max_by(rows, w => len(w));") == [], "max_by over rows types")


def test_values_are_pythons():
    rng = random.Random(20261006)
    for _ in range(300):
        s = tuple(rng.randint(-5, 5) for _ in range(rng.randint(0, 7)))
        w = rng.randint(-3, 3)
        got = _ev("fold((a, x) => a + w * x, 1, s)", {"s": s, "w": w}, "s: seq, w: int", "int")
        ok(got == functools.reduce(lambda a, x: a + w * x, s, 1), "fold of %r" % (s,))
        ps = tuple(interp.Pair(rng.randint(0, 3), rng.randint(0, 3)) for _ in range(len(s)))
        srt = _ev("sort_by(ps, p => p.1)", {"ps": ps}, "ps: seq<(int, int)>", "seq<(int, int)>")
        ok(srt == tuple(sorted(ps, key=lambda p: p.b)), "sort_by is Python's stable sort on %r" % (ps,))
        if s:
            ok(_ev("max_by(s, x => x * x)", {"s": s}, "s: seq", "int") == max(s, key=lambda x: x * x)
               and _ev("min_by(s, x => x * x)", {"s": s}, "s: seq", "int") == min(s, key=lambda x: x * x),
               "the first extreme of %r" % (s,))
    try:
        _ev("max_by(s, x => x)", {"s": ()}, "s: seq", "int")
        ok(False, "max_by of an empty seq must be undefined")
    except interp.Undef:
        pass


def test_twins_handback_and_kernel_text():
    for name in TASKS:
        task = tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))
        twin, got, w = harness.twin_for(task)
        ok(twin is not None and w.get("_ens") is True or w.get("_kind") != "value",
           f"{name}: a twin with a measured witness: {got} {w}")
    twin, got, _w = harness.twin_for(tasks_io.load_task(str(HERE / "tasks" / "longest_row.t")))
    ok(got == "wrong-operator" and "min_by" in surface.print_task({**tasks_io.load_task(
        str(HERE / "tasks" / "longest_row.t")), "body": twin}), "max_by's twin is min_by")
    for body, args, want in (("r := fold((a, x) => a + 2 * x, 1, s);", ((3, 4),), 15),
                             ("r := max_by(s, x => -x);", ((3, -1, 4),), -1),
                             ("r := min_by(s, x => x * x);", ((3, -1, 1),), -1)):
        src, fn = to_python.translate(_task("s: seq", "int", body, requires="len(s) > 0"))
        ns: dict = {}
        exec(src, ns)                                       # noqa: S102 (the hand-back is ours)
        ok(ns[fn](*args) == want and "lambda" in src, "%s hands back with a lambda and computes %r: %s" % (body, want, src))
    src, fn = to_python.translate(tasks_io.load_task(str(HERE / "tasks" / "by_second.t")))
    ns = {}
    exec(src, ns)                                           # noqa: S102
    ok("sorted(" in src and ns[fn]([[0, 2], [1, 1], [2, 1]]) == [[1, 1], [2, 1], [0, 2]],
       "sort_by hands back as Python's stable sorted with a key: %s" % src)

    def lowered(name, kernel):
        out = subprocess.run([sys.executable, str(HERE / "cli.py"), "lower", str(HERE / "tasks" / f"{name}.t"),
                              "--kernel", kernel], capture_output=True, text=True, timeout=120)
        return out.stdout + out.stderr
    d = lowered("weighted_sum", "dafny")
    ok("function t_fold1(" in d and "t_fold1(s, i, 0" in d and "t_fold1(s, |s|, 0" in d,
       "one fold function for the invariant's and the ensures' lambdas, in prefix form: %s" % d)
    d = lowered("by_second", "dafny")
    ok("function t_sortby1(" in d and "lemma t_sbsorted1(" in d and "lemma t_sbbound1(" in d,
       "sort_by in Dafny: the insertion sort and its two lemmas: %s" % d)
    v = lowered("longest_row", "verus")
    ok("pub open spec fn t_maxbyi1(" in v and "broadcast use t_maxby1_spec;" in v,
       "max_by in Verus: the index function and its broadcast lemma: %s" % v)
    v = lowered("by_second", "verus")
    ok("pub broadcast proof fn t_sortby1_mem(" in v and "to_multiset_ensures" in v,
       "sort_by in Verus: the insertion sort's membership lemma: %s" % v)
    v = lowered("weighted_sum", "verus")
    ok("pub open spec fn t_fold1(" in v and "t_fold1(s, i, (0int), w)" in v, "fold in Verus, prefix form: %s" % v)
    for kernel in ("spark", "framac", "rocq", "fstar"):
        out = lowered("longest_row", kernel)
        ok("max_by is not lowered yet" in out, "%s abstains by name: %s" % (kernel, out[:160]))
    # Lean carries fold, max_by and min_by since PREDICT T9 (2026-10-06); sort_by stays refused by name there
    out = lowered("longest_row", "lean")
    ok("def t_maxbyi1" in out and "theorem t_maxby1_bound" in out, "max_by in Lean: %s" % out[:160])


def test_certificates():
    # Dafny: membership in a seq of seqs is scanned, not hashed (measured: the longest_row twin's certificate was
    # refused by an unhashable list)
    task = tasks_io.load_task(str(HERE / "tasks" / "longest_row.t"))
    twin, _got, w = harness.twin_for(task)
    lower_dafny._hof_register(task, twin)
    lower_dafny._comp_register(task, twin)
    cert = lower_dafny._certificate(task, twin, w)
    ok(cert is not None and "r in rows" in cert, "longest_row's Dafny certificate: %s" % cert)
    # Verus: a ground fold unrolls into its nested body, so compute_only evaluates it
    e = surface.parse_expr("fold((a, x) => a + 2 * x, 1, [3, 4])")
    un = lower_verus._unroll(e, [100])
    ok("fold" not in repr(un) and "lam" not in repr(un), "a ground fold is unrolled: %r" % (un,))
    # Verus: the length of a display of pairs is ground (cheapest's and by_second's certificates)
    ok(lower_verus._gint({"op": "len", "args": [{"op": "seq", "args": [{"op": "pair", "args": [{"int": 0}, {"int": 1}]}]}]})
       == 1, "the length of a display of pairs")
    for name in ("cheapest", "by_second", "longest_row"):
        task = tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))
        twin, _got, w = harness.twin_for(task)
        src = lower_verus.lower(task, twin, w)
        ok("t_refutation_certificate" in src, f"{name}'s Verus twin carries a certificate")


def test_census_reading():
    def tags(src):
        return nl_census.solution_tags(src, "f", True)
    for src in ("def f(xs):\n    return sorted(xs, key=lambda p: p[1])\n",
                "def f(xs):\n    return max(xs, key=lambda w: len(w))\n",
                "def f(xs):\n    xs.sort(key=lambda p: -p)\n    return xs\n",
                "def f(xs):\n    return list(map(lambda x: x + 1, xs))\n",
                "def f(xs):\n    g = lambda x: x * 2\n    return [g(x) for x in xs]\n",
                "def f(xs):\n    def h(x):\n        return x + len(xs)\n    return [h(x) for x in xs]\n"):
        t = tags(src)
        ok(t.get("higher-order") and not t.get("closure"), "in the fragment: %r -> %r" % (src, t))
    t = tags("from functools import reduce\ndef f(xs):\n    return reduce(lambda a, x: a + x, xs, 0)\n")
    ok(t.get("higher-order") and t.get("import-modelled") and not t.get("import"), "reduce is t's fold: %r" % t)
    t = tags("import functools\ndef f(xs):\n    return functools.reduce(lambda a, x: a * x, xs)\n")
    ok(t.get("import-modelled") and not t.get("import"), "functools.reduce alone is modelled: %r" % t)
    for src in ("def f(xs):\n    return [(lambda y: y)(x) for x in xs]\n",
                "def f(xs):\n    out = []\n    def h(x):\n        out.append(x)\n    for x in xs:\n        h(x)\n    return out\n",
                "def f(n):\n    memo = {}\n    def g(i):\n        memo[i] = i\n        return i\n    return g(n)\n"):
        t = tags(src)
        ok(t.get("closure"), "the gap: %r -> %r" % (src, t))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
