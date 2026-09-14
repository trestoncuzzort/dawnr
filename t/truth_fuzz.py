#!/usr/bin/env python3
"""t/truth_fuzz.py: grade the seven lowerings against truth known BEFORE any
kernel runs (ROADMAP.md 10.1), not against each other.

Differential fuzzing (fuzz_lower.py) compares kernels to kernels, so a
mistranslation SHARED by all seven is invisible to it: every column agrees and
the table is green. The measured precedent is the integer-width unsoundness,
caught only because Frama-C happened to be the odd one out. This file removes
consensus from the grading loop entirely.

WHAT ESTABLISHES A LABEL. A bounded search is a sound proof of FALSITY (one
counterexample settles it) and is never a sound proof of TRUTH (a property can
hold on [-40,40] and fail at 2^40). The two labels therefore come from
different instruments and the code keeps them apart:

  TRUE   : by CONSTRUCTION only. `denote()` computes the body's own denotation
           as a pure t expression (assign substitutes; `if` merges with `ite`,
           whose laziness is `if`'s), so `ensures r == denote(body)` holds at
           every input by structural induction on the body. Weakenings,
           conjunctions and algebraic rewrites carry a per-template
           justification in `why`; none of them appeals to a test. The bounded
           scan run over every TRUE task is a BUG-CATCH on this file: a hit
           aborts the run, it never promotes a task.
  FALSE  : by exhibited WITNESS: a concrete input where `requires` holds, the
           body yields a value, and `ensures` evaluates false. Checked twice,
           by t/interp.py and by `ck_ens` below, which is written from SPEC.md
           in a different style (UNDEF sentinel and an operator table instead
           of exceptions and an if-chain) so one coding slip cannot appear in
           both. No witness, no FALSE label and the candidate is discarded.
  ILLDEF : `ensures` (or the body) is undefined somewhere `requires` admits.
           SPEC.md "Definedness" makes a lowering that silently totalizes `at`
           wrong, so a sound kernel must not VERIFY; this is a separate label
           from FALSE because reporting a definedness failure as a refutation
           would be the taxonomy violation ROADMAP.md 10.1 forbids.

GRADING. VERIFIED on a FALSE or ILLDEF task is an UNSOUNDNESS. Not-VERIFIED on
a TRUE task is a lowering bug or a kernel that gave up; TIMEOUT, UNPROVED,
MALFORMED and ABSTAIN are recorded as incompleteness and never as refutation.
A wrong grade shared by every present kernel is the headline this file exists
to find.

MEASURED, first two runs (2026-09-01, the training box, seven kernels present,
flake n=3 per cell): 1009 task-instances over two seeds, 7063 cells, 21189
kernel invocations, 0 flake disagreements. 633 TRUE by construction, 357 FALSE
by witness, 19 ill-defined by witness.
  - NO kernel VERIFIED any of the 357 FALSE tasks, the 48 integer-width ones
    included. Grading against construction rather than consensus reproduces
    the WS-7 width repair without trusting it.
  - 13 UNSOUND cells, all lower_framac.py, all on ill-defined tasks: `at` in
    an ACSL SPEC position carries no definedness obligation, so a
    postcondition SPEC.md gives no meaning is proved. Eight distinct spec
    positions (ensures term, forall body, exists body, implies consequent,
    ite condition, `not` argument, spec_fun body, negative index).
  - 0 tasks on which every kernel returning a definite verdict returned the
    wrong one. The shared error this file exists to find is not present in
    the fragment it covers; one task (`gt_q_ex_lit`) was wrong on 3 of 6.
  - 39 cells REFUTED a task true by construction. Every one is incompleteness
    sold as refutation, since the truth is not in question.

The generated lowerings go to --out (default <repo>/t-truth-fuzz), never t/out/,
which the suite's own drivers own.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import interp                                            # noqa: E402
from verifiers import Outcome, flake_check, sha256_file, mp_context  # noqa: E402

BACKENDS = [
    ("dafny", "lower_dafny", "dfy"),
    ("verus", "lower_verus", "rs"),
    ("spark", "lower_spark", "ads"),
    ("framac", "lower_framac", "c"),
    ("lean", "lower_lean", "lean"),
    ("rocq", "lower_rocq", "v"),
    ("fstar", "lower_fstar", "fst"),
]

# ---------------------------------------------------------------------------
# Expression constructors.
# ---------------------------------------------------------------------------

def V(n): return {"var": n}
def I(n): return {"int": n}
def B(b): return {"bool": b}
def op(o, *a): return {"op": o, "args": list(a)}
def ite(c, t, e): return {"ite": {"cond": c, "then": t, "else": e}}
def fa(v, lo, hi, b):
    return {"forall": {"var": v, "lo": lo, "hi": hi, "body": b}}
def ex(v, lo, hi, b):
    return {"exists": {"var": v, "lo": lo, "hi": hi, "body": b}}
def call(f, *a): return {"call": {"fun": f, "args": list(a)}}


def size(e) -> int:
    if isinstance(e, dict):
        return 1 + sum(size(v) for v in e.values())
    if isinstance(e, list):
        return sum(size(v) for v in e)
    return 0


def eq_json(a, b) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ---------------------------------------------------------------------------
# The construction. `denote` is the only thing that licenses a TRUE label on a
# generated body, so it implements SPEC.md's statement semantics and nothing
# else: no simplification that is not an identity, no `while` (a loop has no
# closed form here, and the loop family below supplies its own justification).
# ---------------------------------------------------------------------------

UNSET_KEY = "__unassigned__"
UNSET = {UNSET_KEY: True}


def subst(e: dict, sigma: dict) -> dict:
    """`e` with every free `var` replaced by its denotation in `sigma`. A
    quantifier's bound variable shadows `sigma` (SPEC.md gate 1: the bound name
    is fresh and scoped to the body), so it is dropped before descending."""
    if "var" in e:
        if e["var"] in sigma:
            return json.loads(json.dumps(sigma[e["var"]]))
        return e
    if "int" in e or "bool" in e:
        return dict(e)
    if "op" in e:
        return {"op": e["op"], "args": [subst(a, sigma) for a in e["args"]]}
    if "ite" in e:
        c = e["ite"]
        return ite(subst(c["cond"], sigma), subst(c["then"], sigma),
                   subst(c["else"], sigma))
    if "forall" in e or "exists" in e:
        k = "forall" if "forall" in e else "exists"
        q = e[k]
        inner = {n: v for n, v in sigma.items() if n != q["var"]}
        node = {"var": q["var"], "lo": subst(q["lo"], sigma),
                "hi": subst(q["hi"], sigma), "body": subst(q["body"], inner)}
        return {k: node}
    if "call" in e:
        c = e["call"]
        return call(c["fun"], *[subst(a, sigma) for a in c["args"]])
    raise ValueError(f"t has no expression {e!r}")


def denote(body: list, sigma: dict) -> dict:
    """The post-state of `body` as pure expressions over `sigma`'s domain.

    `if` merges to `ite`, whose evaluation rule (SPEC.md gate 1: the taken
    branch only) is `if`'s, so the merge preserves definedness as well as
    value. Names a branch declares are dropped at the merge: SPEC.md's scope
    rule does not let them escape. `while` raises, because the loop family states its
    own invariant argument instead of claiming a closed form here."""
    s = dict(sigma)
    for st in body:
        if "assign" in st:
            n, e = st["assign"]
            s[n] = subst(e, s)
        elif "var" in st:
            d = st["var"]
            s[d["name"]] = subst(d["init"], s)
        elif "if" in st:
            c = subst(st["if"]["cond"], s)
            s1 = denote(st["if"]["then"], s)
            s2 = denote(st["if"]["else"], s)
            s = {n: (s1[n] if eq_json(s1[n], s2[n]) else ite(c, s1[n], s2[n]))
                 for n in s}
        else:
            raise ValueError(f"denote: no closed form for {list(st)}")
    return s


def mirror(task: dict, body: list | None = None) -> dict:
    """`denote(body)[r]`, the expression `ensures r == mirror(task)` makes
    true at every input by construction."""
    body = task["body"] if body is None else body
    ret = task["returns"][0]["name"]
    sigma = {p["name"]: V(p["name"]) for p in task["params"]}
    # The return starts UNSET, so a body that leaves a path without an assign
    # (SPEC.md v0: "must end every path in assign") cannot be mirrored rather
    # than being mirrored to whatever the other path computed.
    sigma[ret] = UNSET
    d = denote(body, sigma)[ret]
    if eq_json(d, UNSET) or UNSET_KEY in json.dumps(d):
        raise ValueError("body does not assign the return on every path")
    return d


# ---------------------------------------------------------------------------
# Format version: computed, never asserted. lower_rocq.py and lower_verus.py
# dispatch on it, so a v0-shaped task tagged v1 would silently take a
# different lowering path than the committed corpus does.
# ---------------------------------------------------------------------------

V1_OPS = {"len", "at", "div", "mod", "update", "fill", "seq", "slice",
          "pair", "fst", "snd"}


def _uses_v1(node) -> bool:
    if isinstance(node, dict):
        if ({"ite", "forall", "exists", "call", "bool", "while", "var"}
                & set(node)):
            if "var" in node and isinstance(node["var"], str):
                pass                      # `{"var": "x"}` is a v0 expression
            else:
                return True
        if node.get("op") in V1_OPS:
            return True
        return any(_uses_v1(v) for v in node.values())
    if isinstance(node, list):
        return any(_uses_v1(v) for v in node)
    return False


def finish(task: dict) -> dict:
    v1 = (_uses_v1(task.get("body", [])) or _uses_v1(task.get("ensures", []))
          or _uses_v1(task.get("requires", [])) or "spec_funs" in task
          or any(p["type"] != "int" for p in task["params"])
          or task["returns"][0]["type"] != "int")
    task["t"] = 1 if v1 else 0
    return task


# ---------------------------------------------------------------------------
# The independent checker. Re-read of SPEC.md in a deliberately different
# style from interp.ev, an UNDEF sentinel instead of exceptions and an operator
# table instead of an if-chain, so a single coding slip cannot appear in both
# and bless the same wrong witness. Used ONLY to confirm a FALSE label.
# ---------------------------------------------------------------------------

class _Undef:
    __slots__ = ()
    def __repr__(self): return "UNDEF"


UNDEF = _Undef()


class CkBudget(Exception):
    """A cap was hit, so this input decides nothing. Kept apart from UNDEF
    because folding budget exhaustion into "no value" would let an ILLDEF
    label be confirmed by a loop that merely ran long: the taxonomy error
    ROADMAP.md 10.1 forbids, one level down."""

_TAB = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "==": lambda a, b: (isinstance(a, bool) == isinstance(b, bool)) and a == b,
    "!=": lambda a, b: not ((isinstance(a, bool) == isinstance(b, bool))
                            and a == b),
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}


def ck(e, env, funs, fuel):
    """SPEC.md's evaluation, returning UNDEF where t has no value."""
    fuel[0] -= 1
    if fuel[0] < 0:
        raise CkBudget("step cap")
    k = set(e)
    if "int" in k:
        return e["int"]
    if "bool" in k:
        return e["bool"]
    if "var" in k:
        v = env.get(e["var"], UNDEF)
        return UNDEF if v is None else v
    if "ite" in k:
        c = ck(e["ite"]["cond"], env, funs, fuel)
        if c is UNDEF:
            return UNDEF
        return ck(e["ite"]["then" if c else "else"], env, funs, fuel)
    if "forall" in k or "exists" in k:
        q = e["forall"] if "forall" in k else e["exists"]
        univ = "forall" in k
        lo, hi = ck(q["lo"], env, funs, fuel), ck(q["hi"], env, funs, fuel)
        if lo is UNDEF or hi is UNDEF:
            return UNDEF
        if hi - lo > 5000:
            raise CkBudget("quantifier range")
        acc, bad = univ, False
        for i in range(lo, hi):
            sub = dict(env)
            sub[q["var"]] = i
            v = ck(q["body"], sub, funs, fuel)
            if v is UNDEF:
                bad = True               # SPEC.md: the body must be defined at
                continue           # EVERY point of [lo,hi), decided or not
            acc = (acc and v) if univ else (acc or v)
        return UNDEF if bad else bool(acc)
    if "call" in k:
        c = e["call"]
        f = funs.get(c["fun"])
        if f is None or len(c["args"]) != len(f["params"]):
            return UNDEF
        vals = [ck(a, env, funs, fuel) for a in c["args"]]
        if any(v is UNDEF for v in vals):
            return UNDEF
        return ck(f["body"], dict(zip([p["name"] for p in f["params"]], vals)),
                  funs, fuel)
    o = e["op"]
    if o == "and":
        for a in e["args"]:
            v = ck(a, env, funs, fuel)
            if v is UNDEF:
                return UNDEF
            if not v:
                return False
        return True
    if o == "or":
        for a in e["args"]:
            v = ck(a, env, funs, fuel)
            if v is UNDEF:
                return UNDEF
            if v:
                return True
        return False
    if o == "implies":
        p = ck(e["args"][0], env, funs, fuel)
        if p is UNDEF:
            return UNDEF
        if not p:
            return True
        q = ck(e["args"][1], env, funs, fuel)
        return UNDEF if q is UNDEF else bool(q)
    vs = [ck(a, env, funs, fuel) for a in e["args"]]
    if any(v is UNDEF for v in vs):
        return UNDEF
    if o == "neg":
        return -vs[0]
    if o == "not":
        return not vs[0]
    if o == "len":
        return len(vs[0])
    if o == "at":
        s, i = vs
        return s[i] if 0 <= i < len(s) else UNDEF
    if o == "update":
        # SPEC.md "Sequences as values" (2026-09-09): s[i := v], the same
        # definedness as `at`; a fresh tuple, never a mutation of `s`.
        s, i, v = vs
        return (s[:i] + (v,) + s[i + 1:]) if 0 <= i < len(s) else UNDEF
    if o == "fill":
        # seq(n, v): DEFINED IFF n >= 0.
        n, v = vs
        return (v,) * n if n >= 0 else UNDEF
    if o == "seq":
        # SPEC.md "Sequences: literals, concatenation, slices" (2026-09-09):
        # [e1, ..., en], every argument already evaluated above (any UNDEF
        # arg was caught by the `any(v is UNDEF for v in vs)` check that
        # precedes this dispatch), so a literal is defined iff all its
        # elements are.
        return tuple(vs)
    if o == "slice":
        # s[a..b]: DEFINED IFF 0 <= a <= b <= len(s); elements a..b-1.
        s, lo, hi = vs
        return tuple(s[lo:hi]) if 0 <= lo <= hi <= len(s) else UNDEF
    if o in ("div", "mod"):
        # SPEC.md "Division and modulo": Euclidean, undefined at y == 0,
        # written from scratch here (not from interp.ev or fuzz_lower.ev)
        # in this file's own UNDEF-sentinel style: r = x mod |y| in
        # [0, |y|), q = (x - r) // y exactly.
        x, y = vs
        if y == 0:
            return UNDEF
        r = x % abs(y)
        return r if o == "mod" else (x - r) // y
    if o == "pair":
        # SPEC.md "Pairs" (2026-09-10): (a, b), defined iff both components
        # are (any UNDEF arg was already caught above). interp.Pair, not a
        # bare tuple, for the same reason interp.py itself uses it: a tuple
        # here would be indistinguishable from a seq of the same length, and
        # this checker's env already carries interp.Pair values straight
        # through from _envs/falsify/illdefined without reshaping them.
        return interp.Pair(vs[0], vs[1])
    if o == "fst":
        return vs[0].a
    if o == "snd":
        return vs[0].b
    if o in _TAB:
        # `+` is here too: on two seqs (Python tuples) `+` is already
        # concatenation, the same overload SPEC.md's `+` gives it, so no
        # special case is needed for it as there was for `at`/`slice`.
        return _TAB[o](vs[0], vs[1])
    raise ValueError(f"t has no operator {o!r}")


def ck_run(body, env, funs, fuel):
    for s in body:
        fuel[0] -= 1
        if fuel[0] < 0:
            raise CkBudget("step cap")
        if "assign" in s:
            n, e = s["assign"]
            v = ck(e, env, funs, fuel)
            if v is UNDEF:
                return UNDEF
            env[n] = v
        elif "var" in s:
            d = s["var"]
            v = ck(d["init"], env, funs, fuel)
            if v is UNDEF:
                return UNDEF
            env[d["name"]] = v
        elif "if" in s:
            c = ck(s["if"]["cond"], env, funs, fuel)
            if c is UNDEF:
                return UNDEF
            br = s["if"]["then" if c else "else"]
            if ck_run(br, env, funs, fuel) is UNDEF:
                return UNDEF
        elif "while" in s:
            w = s["while"]
            for _ in range(2001):
                c = ck(w["cond"], env, funs, fuel)
                if c is UNDEF:
                    return UNDEF
                if not c:
                    break
                if ck_run(w["body"], env, funs, fuel) is UNDEF:
                    return UNDEF
            else:
                raise CkBudget("loop cap")
        else:
            raise ValueError(f"t has no statement {s!r}")
    return None


def ck_verdict(task: dict, env0: dict):
    """(requires_ok, r, ensures_value) under the independent reading, with
    ensures_value in {True, False, UNDEF, None}. None is "undecided within
    budget" and is never one of the other three: only False licenses a FALSE
    label and only UNDEF an ILLDEF one."""
    funs = {f["name"]: f for f in task.get("spec_funs", [])}
    fuel = [400_000]
    env = {k: (tuple(v) if isinstance(v, list) else v)
           for k, v in env0.items()}
    try:
        for c in task.get("requires", []):
            v = ck(c, env, funs, fuel)
            if v is UNDEF or not v:
                return False, None, None
        ret = task["returns"][0]["name"]
        run = dict(env)
        run[ret] = None
        if ck_run(task["body"], run, funs, fuel) is UNDEF or run[ret] is None:
            return True, None, UNDEF
        post = dict(env)
        post[ret] = run[ret]
        for c in task["ensures"]:
            v = ck(c, post, funs, fuel)
            if v is UNDEF:
                return True, run[ret], UNDEF
            if not v:
                return True, run[ret], False
        return True, run[ret], True
    except (CkBudget, RecursionError):
        return True, None, None


# ---------------------------------------------------------------------------
# Witness search. interp.py proposes, ck_verdict disposes: a FALSE label needs
# both readings to agree that the exhibited input falsifies `ensures`.
# ---------------------------------------------------------------------------

def _interp_verdict(task: dict, env0: dict):
    """The same triple from t/interp.py. interp.Budget is NOT interp.Undef: a
    loop that ran out of the interpreter's MAX_LOOP has not been shown to have
    no value, and folding the two would manufacture ILLDEF labels (measured on
    gt_loop_* at n = 10^6, where MAX_LOOP = 2000 stops a total loop)."""
    funs = interp.funs_of(task, task["body"])
    st = interp.St()
    try:
        for c in task.get("requires", []):
            if not interp.ev(c, env0, funs, st):
                return False, None, None
    except interp.Undef:
        return False, None, None
    except (interp.Budget, RecursionError):
        return True, None, None
    ret = task["returns"][0]["name"]
    env = dict(env0)
    env[ret] = None
    try:
        interp.exec_body(task["body"], env, funs, st)
    except interp.Undef:
        return True, None, "undef"
    except (interp.Budget, RecursionError):
        return True, None, None
    if env[ret] is None:
        return True, None, "undef"
    post = dict(env0)
    post[ret] = env[ret]
    try:
        for c in task["ensures"]:
            if not interp.ev(c, post, funs, st):
                return True, env[ret], False
    except interp.Undef:
        return True, env[ret], "undef"
    except (interp.Budget, RecursionError):
        return True, env[ret], None
    return True, env[ret], True


def _envs(task: dict, cands, limit: int):
    names = [(p["name"], p["type"]) for p in task["params"]]
    for c in cands:
        yield {n: (tuple(c[n]) if isinstance(c[n], list) else c[n])
               for n, _ in names}
    yield from interp.domain(task, names, limit)


def falsify(task: dict, cands=(), limit: int = 768):
    """A concrete input where `requires` holds, the body yields a value, and
    `ensures` is FALSE under both readings. That input is a sound proof of
    falsity; None means no claim is made."""
    for env in _envs(task, cands, limit):
        okr, r, ens = _interp_verdict(task, env)
        if not okr or ens is not False:
            continue
        okr2, r2, ens2 = ck_verdict(task, env)
        if not (okr2 and ens2 is False and r2 == r
                and isinstance(r2, bool) == isinstance(r, bool)):
            return {"_disagreement": True, "input": interp._shown(env),
                    "interp": [okr, interp._j(r), ens],
                    "ck": [okr2, interp._j(r2), str(ens2)]}
        w = interp._shown(env)
        w["_r"] = interp._j(r)
        return w
    return None


def illdefined(task: dict, cands=(), limit: int = 768):
    """An input `requires` admits on which the body or `ensures` has no value.
    Separate from falsify: SPEC.md's definedness obligation is a different
    thing to owe than a false postcondition."""
    for env in _envs(task, cands, limit):
        okr, r, ens = _interp_verdict(task, env)
        if not okr or ens != "undef":
            continue
        okr2, r2, ens2 = ck_verdict(task, env)
        if not (okr2 and ens2 is UNDEF):
            return {"_disagreement": True, "input": interp._shown(env),
                    "interp": [okr, ens], "ck": [okr2, str(ens2)]}
        w = interp._shown(env)
        w["_r"] = interp._j(r)
        return w
    return None


def scan_true(task: dict, limit: int = 768):
    """BUG-CATCH on this file, never a promotion: a TRUE label comes from the
    construction above, and a hit here means the construction is wrong."""
    for env in _envs(task, (), limit):
        okr, r, ens = _interp_verdict(task, env)
        if okr and ens in (False, "undef"):
            okr2, r2, ens2 = ck_verdict(task, env)
            w = interp._shown(env)
            w["_r"] = interp._j(r)
            w["_why"] = "false" if ens is False else "undefined"
            w["_ck"] = [okr2, interp._j(r2), str(ens2)]
            return w
    return None


# ---------------------------------------------------------------------------
# Random body generation. Integer parameters and TOTAL operators, `div` and
# `mod` included since 2026-09-08: the mirror is licensed by `denote`, and
# `denote`'s definedness argument is only as good as the body's, since a
# partial body would make `ensures r == D` true exactly where the body has a
# value and leave the kernel a definedness obligation the task never stated.
# `div`/`mod` are partial in general (undefined at y == 0, SPEC.md "Division
# and modulo"), so here the divisor is always a nonzero LITERAL from
# DIVISORS, never a sub-term that could evaluate to 0; that keeps every
# generated div/mod node total for every input, licensing the same
# structural-induction TRUE label as +/-/*/neg do. The seq families below
# guard `at` explicitly instead.
# ---------------------------------------------------------------------------

# Non-negative only. `neg` supplies negative values instead, because a
# negative literal under `neg` is a lowering probe in its own right
# (lower_framac.py emitted `(--3)`, which C lexes as predecrement, measured
# 2026-09-01 on gt_mirror_005) and belongs in fam_syntax where the finding is
# legible, not spread through every generated body as MALFORMED noise.
LITS = (0, 1, 2, 3, 5, 7, 10, 100)
DIVISORS = (-10, -7, -5, -3, -2, 2, 3, 5, 7, 10)


def gen_int(rng, names, d):
    if d <= 0 or rng.random() < 0.34:
        if rng.random() < 0.65:
            return V(rng.choice(names))
        return I(rng.choice(LITS))
    o = rng.choice(("+", "-", "*", "neg", "+", "-", "div", "mod"))
    if o == "neg":
        return op("neg", gen_int(rng, names, d - 1))
    if o in ("div", "mod"):
        return op(o, gen_int(rng, names, d - 1), I(rng.choice(DIVISORS)))
    return op(o, gen_int(rng, names, d - 1), gen_int(rng, names, d - 1))


def gen_bool(rng, names, d):
    if d <= 0 or rng.random() < 0.55:
        return op(rng.choice(("<", "<=", ">", ">=", "==", "!=")),
                  gen_int(rng, names, 1), gen_int(rng, names, 1))
    o = rng.choice(("and", "or", "not"))
    if o == "not":
        return op("not", gen_bool(rng, names, d - 1))
    return op(o, gen_bool(rng, names, d - 1), gen_bool(rng, names, d - 1))


def gen_body(rng, params, ret):
    """Four shapes. The choice is not aesthetic: measured on a 109-task run
    (2026-09-01, the training box), a body of several top-level statements
    costs the v0 path of lower_verus.py and lower_rocq.py a LOWER-ERROR ("body
    not expressible as one expression"), and any statement after a branch
    costs lower_lean.py an ABSTAIN. Both are fragment gaps, not verdicts, so a
    corpus that spends its cells on them measures the lowerings' coverage
    instead of their truth. Locals are declared once at the top level: a local
    redeclared inside a branch is a shadowing t/interp.py resolves by
    overwriting and C by scoping, and SPEC.md's scope rule settles neither."""
    if len(params) == 0:
        params = ["x"]
    shape = rng.random()
    if shape < 0.28:
        return [{"assign": [ret, gen_int(rng, params, 3)]}]
    if shape < 0.52:
        return [{"if": {"cond": gen_bool(rng, params, 1),
                        "then": [{"assign": [ret, gen_int(rng, params, 2)]}],
                        "else": [{"assign": [ret, gen_int(rng, params, 2)]}]}}]
    if shape < 0.72:
        inner = {"if": {"cond": gen_bool(rng, params, 1),
                        "then": [{"assign": [ret, gen_int(rng, params, 2)]}],
                        "else": [{"assign": [ret, gen_int(rng, params, 2)]}]}}
        return [{"if": {"cond": gen_bool(rng, params, 1),
                        "then": [inner],
                        "else": [{"assign": [ret, gen_int(rng, params, 2)]}]}}]
    names, out = list(params), []
    for k in range(rng.randint(1, 2)):
        n = f"a{k}"
        out.append({"var": {"name": n, "type": "int",
                            "init": gen_int(rng, names, 2)}})
        names.append(n)
    if rng.random() < 0.5:
        out.append({"assign": [ret, gen_int(rng, names, 3)]})
    else:
        out.append({"if": {"cond": gen_bool(rng, names, 1),
                           "then": [{"assign": [ret, gen_int(rng, names, 2)]}],
                           "else": [{"assign": [ret, gen_int(rng, names, 2)]}]}})
    return out


def base_task(name, params, ret_type="int"):
    return {"name": name,
            "params": [{"name": p, "type": "int"} for p in params],
            "returns": [{"name": "r", "type": ret_type}],
            "requires": [], "ensures": [], "body": []}


def base_seq_task(name, seq_params, ret_type="seq"):
    """`base_task`'s seq-typed twin for `fam_seqops_mirror`, params named
    `s0`/`s1` rather than `t`: `t` is the surface syntax's own
    format-version keyword and has no notation as a parameter name
    (SPEC.md's own committed sequence tasks hit the same wall, 2026-09-09;
    fuzz_lower.py's f_v1seqops names its second seq `u` for the same
    reason)."""
    return {"name": name,
            "params": [{"name": p, "type": "seq"} for p in seq_params],
            "returns": [{"name": "r", "type": ret_type}],
            "requires": [], "ensures": [], "body": []}


# ---------------------------------------------------------------------------
# Random seq body generation (SPEC.md "Sequences: literals, concatenation,
# slices (v1)", 2026-09-09), on the same TOTAL-operators discipline as
# gen_int/gen_bool above: `denote`'s TRUE label is only as good as the
# body's own definedness, so every node gen_seq can produce must be defined
# at EVERY input, with no requires to narrow the domain (fam_mirror never
# writes one either). `seq` (the literal) and `+` (concatenation) are
# unconditionally total per SPEC.md. `slice` in general is not (0 <= a <=
# b <= len(s) is a real obligation, guarded EXPLICITLY in fuzz_lower.py's
# f_v1seqops and truth_fuzz's own hand-built fam_definedness/fam_width
# instead of drawn at random here), so the one slice shape below is pinned
# to the WHOLE range, s[0..len(s)], which SPEC.md's own bounds make total
# by construction (0 <= 0 <= len(s) <= len(s) always) the same way a fixed
# nonzero DIVISORS literal keeps `div`/`mod` total for gen_int.
# ---------------------------------------------------------------------------

def gen_seq(rng, seqnames, d):
    if d <= 0 or rng.random() < 0.4:
        if seqnames and rng.random() < 0.7:
            return V(rng.choice(seqnames))
        return op("seq", *[I(rng.choice(LITS)) for _ in range(rng.randint(0, 3))])
    if rng.random() < 0.5:
        return op("+", gen_seq(rng, seqnames, d - 1), gen_seq(rng, seqnames, d - 1))
    inner = gen_seq(rng, seqnames, d - 1)
    return op("slice", inner, I(0), op("len", inner))


# ---------------------------------------------------------------------------
# Families.
# ---------------------------------------------------------------------------

def rec(task, truth, basis, why, family, witness=None, tag=""):
    return {"task": finish(task), "truth": truth, "basis": basis, "why": why,
            "family": family, "witness": witness, "tag": tag}


MIRROR_WHY = ("denote() is SPEC.md's statement semantics read compositionally "
              "(assign substitutes; `if` merges with `ite`, whose "
              "taken-branch "
              "rule is `if`'s), so r == denote(body)[r] at every input by "
              "structural induction on the body")


def fam_mirror(rng, n):
    """MIRROR + WEAKEN + PERTURB, from one pool of generated bodies."""
    out, i = [], 0
    while len([r for r in out if r["family"] == "mirror"]) < n:
        i += 1
        if i > 40 * n:
            break
        np = rng.randint(1, 3)
        params = ["x", "y", "z"][:np]
        body = gen_body(rng, params, "r")
        t = base_task(f"gt_mirror_{i:03d}", params)
        t["body"] = body
        try:
            D = mirror(t)
        except ValueError:
            continue
        if size(D) > 220:
            continue
        t["ensures"] = [op("==", V("r"), D)]
        out.append(rec(t, "TRUE", "construction", MIRROR_WHY, "mirror"))

        k = len(out)
        # WEAKEN: each form is entailed by `r == D` alone, with no appeal to a
        # test. Tautological disjuncts are avoided so the spark adapter's
        # vacuity probe (measured: it flags a postcondition that proves with
        # the body replaced) is not tripped by a task that is fine.
        wf = [("ge", op(">=", V("r"), D), "r == D entails r >= D"),
              ("le", op("<=", V("r"), D), "r == D entails r <= D"),
              ("dis", op("or", op("==", V("r"), D),
                         op("==", V("r"), op("+", D, I(1)))),
               "r == D entails the left disjunct, so the disjunction holds"),
              ("nn", op("not", op("!=", V("r"), D)),
               "not (r != D) is r == D"),
              ("imp", op("implies", op(">=", V(params[0]), I(0)),
                         op("==", V("r"), D)),
               "the consequent holds at every input, so the implication does"),
              ("ne1", op("!=", V("r"), op("+", D, I(1))),
               "r == D and D != D+1 over the integers"),
              ("cj", op("and", op("==", V("r"), D), op(">=", V("r"), D)),
               "a conjunction of two facts each entailed by r == D")]
        nm, e, why = wf[k % len(wf)]
        w = base_task(f"gt_weaken_{i:03d}_{nm}", params)
        w["body"] = json.loads(json.dumps(body))
        w["ensures"] = [e]
        out.append(rec(w, "TRUE", "construction", why, "weaken", tag=nm))

        # PERTURB: known-FALSE candidates. Each needs an exhibited witness or
        # it is discarded: a mutation is not a falsity proof.
        pf = [("plus1", op("==", V("r"), op("+", D, I(1)))),
              ("gt", op(">", V("r"), D)),
              ("lt", op("<", V("r"), D)),
              ("ne", op("!=", V("r"), D)),
              ("ge1", op(">=", V("r"), op("+", D, I(1)))),
              ("neg", op("==", V("r"), op("neg", D))),
              ("cj", op("and", op("==", V("r"), D),
                        op("==", V("r"), op("+", D, I(2))))),
              ("imp", op("implies", op(">=", V(params[0]), I(0)),
                         op("==", V("r"), op("-", D, I(1)))))]
        nm, e = pf[k % len(pf)]
        f = base_task(f"gt_false_{i:03d}_{nm}", params)
        f["body"] = json.loads(json.dumps(body))
        f["ensures"] = [e]
        finish(f)
        wit = falsify(f)
        if wit and not wit.get("_disagreement"):
            out.append(rec(f, "FALSE", "witness",
                           "a concrete input where requires holds, the body "
                           "yields a value and ensures evaluates false, "
                           "agreed "
                           "by interp.py and ck_ens", "false", wit, nm))
        elif wit:
            out.append(rec(f, "ORACLE-SPLIT", "none",
                           "interp.py and ck_ens disagree", "oracle-split", wit))
    return out


def fam_seqops_mirror(rng, n):
    """`fam_mirror`'s MIRROR + WEAKEN + PERTURB, over `gen_seq` instead of
    `gen_int`/`gen_body` (SPEC.md "Sequences: literals, concatenation,
    slices (v1)", 2026-09-09). `denote`/`mirror`/`subst` above are already
    generic in the operator name, so `seq`, `+` and `slice` needed no
    change there; what they needed was `V1_OPS` (this file's own
    `_uses_v1`) and `ck`'s operator table, both extended above, and a
    generator whose every node is TOTAL by construction (see gen_seq's
    docstring), the same discipline gen_int already keeps for `div`/`mod`.

    Every ensures stays element-wise (`at(r, k) == at(D, k)`), never a
    whole-seq `r == D`: fuzz_lower.py's f_v1seqval family already measures
    spark's whole-seq-`==` gap on its own terms, and a TRUE label earned
    through it here would let that gap read as spark merely being
    incomplete on every task in this family rather than the one thing it
    actually is."""
    out, i = [], 0
    while len([r for r in out if r["family"] == "seqops_mirror"]) < n:
        i += 1
        if i > 40 * n:
            break
        np = rng.randint(1, 2)
        seqnames = ["s0", "s1"][:np]
        D = gen_seq(rng, seqnames, 3)
        if size(D) > 160:
            continue
        t = base_seq_task(f"gt_seqops_{i:03d}", seqnames)
        t["body"] = [{"assign": ["r", D]}]
        ens_eq = [op("==", op("len", V("r")), op("len", D)),
                 fa("k", I(0), op("len", V("r")),
                    op("==", op("at", V("r"), V("k")), op("at", D, V("k"))))]
        t["ensures"] = ens_eq
        finish(t)
        out.append(rec(t, "TRUE", "construction",
                       "denote() is SPEC.md's statement semantics read "
                       "compositionally, `seq`/`+`/`slice` included; r == D "
                       "holds at every input by structural induction on the "
                       "body, stated element-wise rather than by the "
                       "whole-seq `==` this family deliberately avoids",
                       "seqops_mirror"))

        # WEAKEN: len(r) == len(D) alone, entailed by the element-wise fact
        # above, no appeal to a test.
        w = base_seq_task(f"gt_seqops_weaken_{i:03d}_len", seqnames)
        w["body"] = json.loads(json.dumps(t["body"]))
        w["ensures"] = [op("==", op("len", V("r")), op("len", D))]
        finish(w)
        out.append(rec(w, "TRUE", "construction",
                       "the element-wise fact entails the two seqs have "
                       "the same length", "seqops_weaken"))

        # PERTURB: every kept element off by one, element-wise, the same
        # shape fuzz_lower.py's fz_p_seqeq_false uses and for the same
        # reason: a witness needs len(D) >= 1, so this is FALSE at every
        # non-empty draw, not at every draw (an empty D makes the forall
        # vacuously true, SPEC.md's own rule for an empty range).
        f = base_seq_task(f"gt_seqops_false_{i:03d}", seqnames)
        f["body"] = json.loads(json.dumps(t["body"]))
        f["ensures"] = [op("==", op("len", V("r")), op("len", D)),
                       fa("k", I(0), op("len", V("r")),
                          op("==", op("at", V("r"), V("k")),
                             op("+", op("at", D, V("k")), I(1))))]
        finish(f)
        wit = falsify(f)
        if wit and not wit.get("_disagreement"):
            out.append(rec(f, "FALSE", "witness",
                           "every element off by one, false at any non-"
                           "empty draw of D, agreed by interp.py and "
                           "ck_ens", "seqops_false", wit))
        elif wit:
            out.append(rec(f, "ORACLE-SPLIT", "none",
                           "interp.py and ck_ens disagree", "oracle-split",
                           wit))
    return out


# Rewrites that are identities over the mathematical integers SPEC.md fixes,
# so a rewritten TRUE task is TRUE for the same reason the original was.
REWRITES = [
    ("plus0", lambda e: op("+", e, I(0)), "x + 0 == x over Z"),
    ("times1", lambda e: op("*", e, I(1)), "x * 1 == x over Z"),
    ("dblneg", lambda e: op("neg", op("neg", e)), "-(-x) == x over Z"),
    ("minus0", lambda e: op("-", e, I(0)), "x - 0 == x over Z"),
]


def rename(node, ren: dict):
    """Consistent renaming of parameters. `{"var": "x"}` is an expression and
    `{"var": {...}}` a local declaration, so the two spellings are separated
    here rather than by a textual substitution."""
    if isinstance(node, dict):
        if "var" in node and isinstance(node["var"], str):
            return {"var": ren.get(node["var"], node["var"])}
        return {k: rename(v, ren) for k, v in node.items()}
    if isinstance(node, list):
        return [rename(v, ren) for v in node]
    return node


def fam_metamorphic(rng, src):
    """Semantics-preserving rewrites of TRUE tasks: same verdict expected,
    which is the cheap half of ROADMAP.md 10.1's shared-error test."""
    out = []
    for j, r0 in enumerate(src):
        t = json.loads(json.dumps(r0["task"]))
        nm, f, why = REWRITES[j % len(REWRITES)]
        e0 = t["ensures"][0]
        if j % 2 == 0 and e0.get("op") in ("==", "<=", ">="):
            e0["args"][1] = f(e0["args"][1])
        else:
            last = t["body"][-1]
            if "assign" not in last:
                continue
            last["assign"][1] = f(last["assign"][1])
        # SPEC.md's scope rule makes a parameter name a bound name, so a
        # consistent renaming changes no denotation.
        ren = {p["name"]: f"q{k}" for k, p in enumerate(t["params"])}
        t = rename(t, ren)
        for p in t["params"]:
            p["name"] = ren[p["name"]]
        t["name"] = f"gt_meta_{j:03d}_{nm}"
        out.append(rec(t, "TRUE", "construction",
                       f"{r0['why']}; then {why} and a consistent renaming, "
                       f"both denotation-preserving", "metamorphic", tag=nm))
    return out


def fam_algebra():
    """Hand-derived templates: the postcondition is NOT a syntactic mirror of
    the body, so a lowering that mistranslates body and spec the same way
    cannot hide behind the symmetry."""
    A, out = [], []
    x, y, z = V("x"), V("y"), V("z")

    def T(name, params, req, ens, body, why, disc=None):
        t = base_task(name, params)
        t["requires"], t["ensures"], t["body"] = req, ens, body
        A.append((t, why, disc))

    T("gt_alg_dbl", ["x"], [], [op("==", V("r"), op("*", I(2), x))],
      [{"assign": ["r", op("+", x, x)]}], "x + x == 2*x over Z")
    T("gt_alg_sub", ["x", "y"], [], [op("==", op("+", V("r"), y), x)],
      [{"assign": ["r", op("-", x, y)]}], "(x - y) + y == x over Z")
    T("gt_alg_dist", ["x", "y", "z"], [],
      [op("==", V("r"), op("+", op("*", x, y), op("*", x, z)))],
      [{"assign": ["r", op("*", x, op("+", y, z))]}],
      "distributivity over Z")
    T("gt_alg_diffsq", ["x", "y"], [],
      [op("==", V("r"), op("-", op("*", x, x), op("*", y, y)))],
      [{"assign": ["r", op("*", op("+", x, y), op("-", x, y))]}],
      "(x+y)(x-y) == x^2 - y^2 over Z")
    T("gt_alg_binom", ["x"], [],
      [op("==", V("r"), op("*", op("+", x, I(1)), op("+", x, I(1))))],
      [{"assign": ["r", op("+", op("+", op("*", x, x), op("*", I(2), x)),
                           I(1))]}],
      "x^2 + 2x + 1 == (x+1)^2 over Z")
    T("gt_alg_abs", ["x"], [],
      [op(">=", V("r"), I(0)),
       op("or", op("==", V("r"), x), op("==", V("r"), op("neg", x))),
       op("==", op("*", V("r"), V("r")), op("*", x, x))],
      [{"if": {"cond": op("<", x, I(0)),
               "then": [{"assign": ["r", op("neg", x)]}],
               "else": [{"assign": ["r", x]}]}}],
      "case analysis: x < 0 gives r = -x > 0 and r^2 = x^2; otherwise r = x "
      ">= 0")
    T("gt_alg_max", ["x", "y"], [],
      [op(">=", V("r"), x), op(">=", V("r"), y),
       op("or", op("==", V("r"), x), op("==", V("r"), y))],
      [{"if": {"cond": op(">=", x, y), "then": [{"assign": ["r", x]}],
               "else": [{"assign": ["r", y]}]}}],
      "case analysis on the guard: each branch returns the larger operand")
    T("gt_alg_min", ["x", "y"], [],
      [op("<=", V("r"), x), op("<=", V("r"), y),
       op("or", op("==", V("r"), x), op("==", V("r"), y))],
      [{"if": {"cond": op("<=", x, y), "then": [{"assign": ["r", x]}],
               "else": [{"assign": ["r", y]}]}}],
      "case analysis on the guard: each branch returns the smaller operand")
    T("gt_alg_sq_nonneg", ["x"], [], [op(">=", V("r"), I(0))],
      [{"assign": ["r", op("*", x, x)]}],
      "a square is non-negative over Z", "32/64-bit: x*x wraps negative")
    T("gt_alg_negpos", ["x"], [op("<", x, I(0))], [op(">", V("r"), I(0))],
      [{"assign": ["r", op("neg", x)]}],
      "x < 0 gives -x > 0 over Z", "two's complement: -(-2^31) == -2^31")
    T("gt_alg_succ", ["x"], [op(">=", x, I(0))],
      [op(">", V("r"), x), op(">=", V("r"), I(1))],
      [{"assign": ["r", op("+", x, I(1))]}],
      "x + 1 > x over Z", "32-bit: x = 2^31-1 wraps to -2^31")
    T("gt_alg_addmono", ["x", "y"], [op(">=", x, I(0)), op(">=", y, I(0))],
      [op(">=", V("r"), x), op(">=", V("r"), y)],
      [{"assign": ["r", op("+", x, y)]}],
      "adding a non-negative is monotone over Z",
      "32-bit: 2^30 + 2^30 wraps to -2^31")
    T("gt_alg_cube", ["x"], [op(">=", x, I(0))], [op(">=", V("r"), I(0))],
      [{"assign": ["r", op("*", op("*", x, x), x)]}],
      "a product of non-negatives is non-negative over Z",
      "32/64-bit: x^3 wraps")
    T("gt_alg_scale", ["x"], [op(">=", x, I(0))], [op(">=", V("r"), I(0))],
      [{"assign": ["r", op("*", x, I(1000000))]}],
      "a product of non-negatives is non-negative over Z",
      "32-bit: x = 3000 wraps negative")
    T("gt_alg_zero", ["x"], [], [op("==", V("r"), I(0)), op("<=", V("r"), I(0)),
                                 op(">=", V("r"), I(0))],
      [{"assign": ["r", op("-", x, x)]}], "x - x == 0 over Z")
    T("gt_alg_swap", ["x", "y"], [], [op("==", V("r"), op("+", y, x))],
      [{"assign": ["r", op("+", x, y)]}], "commutativity of + over Z")
    T("gt_alg_assoc", ["x", "y", "z"], [],
      [op("==", V("r"), op("+", x, op("+", y, z)))],
      [{"assign": ["r", op("+", op("+", x, y), z)]}],
      "associativity of + over Z")
    T("gt_alg_nested", ["x"], [],
      [op(">=", V("r"), I(0)), op("<=", V("r"), I(2))],
      [{"if": {"cond": op("<", x, I(0)), "then": [{"assign": ["r", I(0)]}],
               "else": [{"if": {"cond": op("==", x, I(0)),
                                "then": [{"assign": ["r", I(1)]}],
                                "else": [{"assign": ["r", I(2)]}]}}]}}],
      "every path assigns a literal in [0,2]")
    for t, why, disc in A:
        out.append(rec(t, "TRUE", "construction", why, "algebra",
                       tag=("width" if disc else "")))
        if disc:
            out[-1]["discriminates"] = disc
    return out


BITS = [(31, 2147483647, -2147483648, "32-bit signed"),
        (63, 9223372036854775807, -9223372036854775808, "64-bit signed"),
        (15, 32767, -32768, "16-bit signed"),
        (7, 127, -128, "8-bit signed")]


def fam_width():
    """FALSE over Z, TRUE under a machine word: a VERIFIED here says the
    lowering silently used bounded integers, which SPEC.md's "mathematical
    integers, unbounded, no overflow" forbids. An independent re-check of the
    WS-7 integer repair that does not trust it."""
    out = []
    for k, hi, lo, label in BITS:
        t = base_task(f"gt_width_hi{k}", ["x"])
        t["ensures"] = [op("<=", V("r"), I(hi))]
        t["body"] = [{"assign": ["r", V("x")]}]
        finish(t)
        w = falsify(t, cands=[{"x": hi + 1}, {"x": hi + 7}])
        out.append(rec(t, "FALSE", "witness",
                       f"r == x and x = {hi + 1} exceeds {label}'s maximum; "
                       f"t integers are unbounded (SPEC.md)", "width", w,
                       f"hi{k}"))
        t = base_task(f"gt_width_lo{k}", ["x"])
        t["ensures"] = [op(">=", V("r"), I(lo))]
        t["body"] = [{"assign": ["r", V("x")]}]
        finish(t)
        w = falsify(t, cands=[{"x": lo - 1}, {"x": lo - 7}])
        out.append(rec(t, "FALSE", "witness",
                       f"r == x and x = {lo - 1} is below {label}'s minimum",
                       "width", w, f"lo{k}"))
        t = base_task(f"gt_width_band{k}", ["x"])
        t["ensures"] = [op("and", op(">=", V("r"), I(lo)), op("<=", V("r"), I(hi)))]
        t["body"] = [{"assign": ["r", V("x")]}]
        finish(t)
        w = falsify(t, cands=[{"x": hi + 1}, {"x": lo - 1}])
        out.append(rec(t, "FALSE", "witness",
                       f"r == x leaves the {label} band at x = {hi + 1}",
                       "width", w, f"band{k}"))
    # A true conjunct in front of the false one: a lowering that stops at the
    # first provable clause reads as VERIFIED here and nowhere else.
    # Through a spec_fun and through a loop invariant: the width repair has to
    # hold in every spec position, not only in a top-level `ensures`.
    t = base_task("gt_width_specfun", ["x"])
    t["spec_funs"] = [{"name": "idn", "params": [{"name": "k", "type": "int"}],
                       "result": "int", "decreases": I(0), "body": V("k")}]
    t["ensures"] = [op("<=", call("idn", V("r")), I(2147483647))]
    t["body"] = [{"assign": ["r", V("x")]}]
    finish(t)
    out.append(rec(t, "FALSE", "witness",
                   "idn(r) unfolds to r == x, and x = 2^31 exceeds the bound",
                   "width", falsify(t, cands=[{"x": 2147483648}]), "specfun"))
    t = base_task("gt_width_loop", ["n"])
    t["requires"] = [op(">=", V("n"), I(0))]
    t["ensures"] = [op("<=", V("r"), I(2147483647))]
    t["body"] = [{"assign": ["r", V("n")]},
                 {"var": {"name": "i", "type": "int", "init": I(0)}},
                 {"while": {"cond": op("<", V("i"), I(1)),
                            "invariants": [op("==", V("r"), V("n"))],
                            "decreases": op("-", I(1), V("i")),
                            "body": [{"assign": ["i", op("+", V("i"), I(1))]}]}}]
    finish(t)
    out.append(rec(t, "FALSE", "witness",
                   "the loop leaves r == n and n = 2^31 exceeds the bound",
                   "width", falsify(t, cands=[{"n": 2147483648}]), "loop"))
    t = base_task("gt_width_mixed", ["x"])
    t["ensures"] = [op(">=", op("*", V("r"), V("r")), I(0)),
                    op("<=", V("r"), I(2147483647))]
    t["body"] = [{"assign": ["r", V("x")]}]
    finish(t)
    out.append(rec(t, "FALSE", "witness",
                   "clause 0 is true over Z, clause 1 fails at x = 2^31",
                   "width", falsify(t, cands=[{"x": 2147483648}]), "mixed"))
    # Product: needs the lowering to keep width through an arithmetic op.
    t = base_task("gt_width_mul", ["x"])
    t["ensures"] = [op("<=", V("r"), I(4611686018427387903))]
    t["body"] = [{"assign": ["r", op("*", V("x"), V("x"))]}]
    finish(t)
    out.append(rec(t, "FALSE", "witness",
                   "x = 2^31 gives x*x = 2^62 > 2^62 - 1", "width",
                   falsify(t, cands=[{"x": 2147483648}]), "mul"))
    t = base_task("gt_width_sum", ["x", "y"])
    t["ensures"] = [op("<=", V("r"), I(4294967294))]
    t["body"] = [{"assign": ["r", op("+", V("x"), V("y"))]}]
    finish(t)
    out.append(rec(t, "FALSE", "witness",
                   "x = y = 2^31 gives r = 2^32 > 2^32 - 2", "width",
                   falsify(t, cands=[{"x": 2147483648, "y": 2147483648}]), "sum"))
    # Through a sequence element, which is a different lowering path (seq<int>,
    # C array, Lean List) than a scalar parameter.
    t = base_task("gt_width_seq", [])
    t["params"] = [{"name": "s", "type": "seq"}]
    t["requires"] = [op(">=", op("len", V("s")), I(1))]
    t["ensures"] = [op("==", V("r"), op("at", V("s"), I(0))),
                    op("<=", V("r"), I(2147483647))]
    t["body"] = [{"assign": ["r", op("at", V("s"), I(0))]}]
    finish(t)
    out.append(rec(t, "FALSE", "witness",
                   "s = [2^31] makes clause 1 false while clause 0 holds",
                   "width", falsify(t, cands=[{"s": [2147483648]}]), "seq"))
    return [r for r in out
            if r["witness"] and not r["witness"].get("_disagreement")]


def fam_definedness():
    """SPEC.md "Definedness": `at` is defined iff 0 <= i < len(s), and a
    lowering that silently totalizes it is wrong. The TRUE half must verify;
    the ILLDEF half must not."""
    out = []
    s, i = V("s"), V("i")
    ln = op("len", s)

    def seqtask(name, params, req, ens, body):
        t = {"name": name, "params": params,
             "returns": [{"name": "r", "type": "int"}],
             "requires": req, "ensures": ens, "body": body}
        return finish(t)

    P_S = [{"name": "s", "type": "seq"}]
    P_SI = [{"name": "s", "type": "seq"}, {"name": "i", "type": "int"}]

    t = seqtask("gt_def_guard_ok", P_SI, [],
                [op("==", V("r"), I(0)),
                 op("implies", op("and", op("<=", I(0), i), op("<", i, ln)),
                    op("==", op("at", s, i), op("at", s, i)))],
                [{"assign": ["r", I(0)]}])
    out.append(rec(t, "TRUE", "construction",
                   "SPEC.md: `implies p q` needs q defined only when p "
                   "holds, and p is exactly at's definedness condition",
                   "definedness"))
    t = seqtask("gt_def_or_ok", P_SI, [],
                [op("==", V("r"), I(0)),
                 op("or", op("not", op("and", op("<=", I(0), i), op("<", i, ln))),
                    op("==", op("at", s, i), op("at", s, i)))],
                [{"assign": ["r", I(0)]}])
    out.append(rec(t, "TRUE", "construction",
                   "SPEC.md: `or` evaluates left to right and the second "
                   "argument is needed only when the first is false",
                   "definedness"))
    t = seqtask("gt_def_forall_ok", P_S, [],
                [op("==", V("r"), I(0)),
                 fa("j", I(0), ln, op("==", op("at", s, V("j")),
                                      op("at", s, V("j"))))],
                [{"assign": ["r", I(0)]}])
    out.append(rec(t, "TRUE", "construction",
                   "the quantifier range is exactly [0, len(s)), where `at` "
                   "is "
                   "defined", "definedness"))
    t = seqtask("gt_def_empty_ok", P_S, [],
                [op("==", V("r"), I(0)),
                 fa("j", ln, I(0), op("==", op("at", s, V("j")), I(999)))],
                [{"assign": ["r", I(0)]}])
    out.append(rec(t, "TRUE", "construction",
                   "len(s) >= 0 makes [len(s), 0) empty, and SPEC.md decides "
                   "an "
                   "empty range without the body", "definedness"))
    t = seqtask("gt_def_head_ok", P_S, [op(">=", ln, I(1))],
                [op("==", V("r"), op("at", s, I(0)))],
                [{"assign": ["r", op("at", s, I(0))]}])
    out.append(rec(t, "TRUE", "construction",
                   "requires pins len(s) >= 1, so at(s,0) is defined",
                   "definedness"))

    ill = []
    t = seqtask("gt_def_head_bad", P_S, [],
                [op("==", V("r"), op("at", s, I(0)))],
                [{"assign": ["r", op("at", s, I(0))]}])
    ill.append((t, "at(s,0) has no value at len(s) == 0, so neither the body "
                   "nor the postcondition is defined there"))
    t = seqtask("gt_def_past_end", P_S, [op(">=", ln, I(1))],
                [op("==", V("r"), I(0)),
                 op("==", op("at", s, ln), op("at", s, ln))],
                [{"assign": ["r", I(0)]}])
    ill.append((t, "at(s, len(s)) is outside [0, len(s)) at every admitted "
                   "input"))
    t = seqtask("gt_def_forall_bad", P_S, [],
                [op("==", V("r"), I(0)),
                 fa("j", I(0), op("+", ln, I(1)),
                    op("==", op("at", s, V("j")), op("at", s, V("j"))))],
                [{"assign": ["r", I(0)]}])
    ill.append((t, "SPEC.md requires the body defined at EVERY point of "
                   "[0, len(s)+1), and j == len(s) is not one"))
    t = seqtask("gt_def_and_bad", P_SI, [],
                [op("==", V("r"), I(0)),
                 op("and", op("==", op("at", s, i), op("at", s, i)),
                    op("<", i, ln))],
                [{"assign": ["r", I(0)]}])
    ill.append((t, "the guard is the SECOND conjunct, so SPEC.md's left-to-"
                   "right rule leaves at(s,i) unguarded"))
    t = seqtask("gt_def_neg_idx", P_S, [op(">=", ln, I(1))],
                [op("==", V("r"), I(0)),
                 op("==", op("at", s, op("neg", I(1))),
                    op("at", s, op("neg", I(1))))],
                [{"assign": ["r", I(0)]}])
    ill.append((t, "index -1 is below 0, so `at` has no value there"))
    t = seqtask("gt_def_ite_bad", P_S, [op(">=", ln, I(1))],
                [op("==", V("r"), I(0)),
                 op("==", ite(op(">", ln, I(0)), op("at", s, ln), I(0)), I(0))],
                [{"assign": ["r", I(0)]}])
    ill.append((t, "the guard is true at every admitted input, so `ite` takes "
                   "the branch that reads at(s, len(s))"))
    t = seqtask("gt_def_exists_bad", P_S, [],
                [op("==", V("r"), I(0)),
                 ex("j", ln, op("+", ln, I(1)),
                    op("==", op("at", s, V("j")), op("at", s, V("j"))))],
                [{"assign": ["r", I(0)]}])
    ill.append((t, "the only point of [len(s), len(s)+1) is j == len(s), where "
                   "`at` has no value"))
    t = seqtask("gt_def_implies_bad", P_S, [],
                [op("==", V("r"), I(0)),
                 op("implies", op(">=", ln, I(0)),
                    op("==", op("at", s, ln), op("at", s, ln)))],
                [{"assign": ["r", I(0)]}])
    ill.append((t, "the antecedent holds at every input, so SPEC.md's rule "
                   "makes the consequent owe a value it does not have"))
    hd = {"name": "hd", "params": [{"name": "u", "type": "seq"}],
          "result": "int", "decreases": I(0),
          "body": op("at", V("u"), I(0))}
    t = seqtask("gt_def_specfun_bad", P_S, [],
                [op("==", V("r"), I(0)), op("==", call("hd", s), call("hd", s))],
                [{"assign": ["r", I(0)]}])
    t["spec_funs"] = [hd]
    finish(t)
    ill.append((t, "hd(s) unfolds to at(s,0), which has no value at "
                   "len(s) == 0; a spec_fun is a different lowering position "
                   "from an inline `at`"))
    t = seqtask("gt_def_ite_cond_bad", P_S, [op(">=", ln, I(1))],
                [op("==", V("r"), I(0)),
                 ite(op(">", op("at", s, ln), I(0)), op("==", V("r"), I(0)),
                     op("==", V("r"), I(0)))],
                [{"assign": ["r", I(0)]}])
    ill.append((t, "the `ite` CONDITION reads at(s, len(s)); SPEC.md needs the "
                   "condition defined before either branch is taken"))
    t = seqtask("gt_def_not_bad", P_S, [op(">=", ln, I(1))],
                [op("==", V("r"), I(0)),
                 op("not", op("!=", op("at", s, ln), op("at", s, ln)))],
                [{"assign": ["r", I(0)]}])
    ill.append((t, "`not` is strict, so its argument owes a value and "
                   "at(s, len(s)) has none"))
    for t, why in ill:
        w = illdefined(t, cands=[{"s": [], "i": 0}, {"s": [1], "i": 5},
                                 {"s": [1, 2], "i": -1}])
        if w and not w.get("_disagreement"):
            out.append(rec(t, "ILLDEF", "witness", why, "definedness", w))
    t = seqtask("gt_def_dead_branch", P_S, [],
                [op("==", V("r"), I(0))],
                [{"if": {"cond": op("<", ln, I(0)),
                         "then": [{"assign": ["r", op("at", s, ln)]}],
                         "else": [{"assign": ["r", I(0)]}]}}])
    out.append(rec(t, "TRUE", "construction",
                   "len(s) >= 0 makes the guard false everywhere, and SPEC.md "
                   "evaluates the taken branch only, so the unreachable `at` "
                   "owes nothing", "definedness"))
    return out


def fam_syntax(rng):
    """Lexical and precedence probes, pinned so the postcondition is a literal.
    Motivated by a measurement: on gt_mirror_005 lower_framac.py emitted
    `(--3)` for `neg` of the literal -3, which C lexes as predecrement."""
    out = []
    x, y = V("x"), V("y")
    cases = [
        ("neglit", {"x": 0}, [{"assign": ["r", op("+", x, op("neg", I(-3)))]}],
         3, -3),
        ("negneg", {"x": 0},
         [{"assign": ["r", op("+", x, op("neg", op("neg", op("neg", I(5)))))]}],
         -5, 5),
        ("subneg", {"x": 0}, [{"assign": ["r", op("-", x, I(-3))]}], 3, -3),
        ("negvar", {"x": -7}, [{"assign": ["r", op("neg", op("neg", x))]}],
         -7, 7),
        ("negmul", {"x": 3, "y": 5},
         [{"assign": ["r", op("neg", op("*", x, y))]}], -15, 15),
        ("zerosub", {"x": -2147483648},
         [{"assign": ["r", op("-", I(0), x)]}], 2147483648, -2147483648),
        ("deepparen", {"x": 1},
         [{"assign": ["r", op("*", op("+", op("*", x, I(2)), I(3)),
                              op("-", I(4), op("*", I(2), x)))]}], 10, 14),
        ("minlit", {"x": -9223372036854775808},
         [{"assign": ["r", op("+", x, I(0))]}], -9223372036854775808, 0),
        ("negsum", {"x": 4, "y": 6},
         [{"assign": ["r", op("neg", op("+", x, y))]}], -10, 10),
    ]
    for nm, pins, body, val, wrong in cases:
        t = _pin(f"gt_syn_{nm}", pins, json.loads(json.dumps(body)), val)
        out.append(rec(t, "TRUE", "construction", PIN_WHY, "syntax", tag=nm))
        f = _pin(f"gt_synf_{nm}", pins, json.loads(json.dumps(body)), wrong)
        w = falsify(f, cands=[dict(pins)])
        if w and not w.get("_disagreement"):
            out.append(rec(f, "FALSE", "witness",
                           f"the one admitted input gives {val}, not {wrong}",
                           "syntax", w, nm))
    return out


def fam_quant():
    """Bounded quantifiers over integer ranges, with no sequence, so a verdict here
    is about the quantifier lowering alone."""
    out = []
    n = V("n")

    def qt(name, req, ens, body, params=("n",)):
        t = base_task(name, list(params))
        t["requires"], t["ensures"], t["body"] = req, ens, body
        return finish(t)

    R0 = [{"assign": ["r", I(0)]}]
    out.append(rec(qt("gt_q_fa_lit", [], [op("==", V("r"), I(0)),
                                          fa("i", I(0), I(3), op(">=", V("i"), I(0)))],
                      R0),
                   "TRUE", "construction",
                   "every i in [0,3) satisfies i >= 0", "quant"))
    out.append(rec(qt("gt_q_ex_lit", [], [op("==", V("r"), I(0)),
                                          ex("i", I(0), I(3), op("==", V("i"), I(2)))],
                      R0),
                   "TRUE", "construction", "i = 2 lies in [0,3)", "quant"))
    out.append(rec(qt("gt_q_fa_empty", [], [op("==", V("r"), I(0)),
                                            fa("i", I(0), I(0), B(False))], R0),
                   "TRUE", "construction",
                   "SPEC.md: hi <= lo is the empty range and forall is true "
                   "on "
                   "it without the body", "quant"))
    out.append(rec(qt("gt_q_fa_var", [op(">=", n, I(0))],
                      [op("==", V("r"), V("n")),
                       fa("i", I(0), n, op("<", V("i"), n))],
                      [{"assign": ["r", V("n")]}]),
                   "TRUE", "construction",
                   "i < n is the range's own upper bound", "quant"))
    out.append(rec(qt("gt_q_fa_r", [op(">=", n, I(0))],
                      [op("==", V("r"), V("n")),
                       fa("i", I(0), n, op(">", V("r"), V("i")))],
                      [{"assign": ["r", V("n")]}]),
                   "TRUE", "construction",
                   "r == n and every i in [0,n) is < n", "quant"))
    for name, ens, cands, why in [
        ("gt_q_ex_empty", [op("==", V("r"), I(0)),
                           ex("i", I(0), I(0), B(True))], [{"n": 0}],
         "SPEC.md: exists is false on the empty range"),
        ("gt_q_fa_false", [op("==", V("r"), I(0)),
                           fa("i", I(0), I(3), op(">", V("i"), I(0)))], [{"n": 0}],
         "i = 0 lies in [0,3) and fails i > 0"),
        ("gt_q_ex_miss", [op("==", V("r"), I(0)),
                          ex("i", I(0), I(3), op("==", V("i"), I(9)))], [{"n": 0}],
         "no i in [0,3) equals 9"),
    ]:
        t = qt(name, [], ens, R0)
        w = falsify(t, cands=cands)
        if w and not w.get("_disagreement"):
            out.append(rec(t, "FALSE", "witness", why, "quant", w))
    t = qt("gt_q_fa_strict", [op(">=", n, I(1))],
           [op("==", V("r"), op("-", n, I(1))),
            fa("i", I(0), n, op(">", V("r"), V("i")))],
           [{"assign": ["r", op("-", V("n"), I(1))]}])
    w = falsify(t, cands=[{"n": 1}])
    if w and not w.get("_disagreement"):
        out.append(rec(t, "FALSE", "witness",
                       "at n = 1, r = 0 and i = 0 is in range with r > i "
                       "false",
                       "quant", w))
    return out


def fam_loops():
    """Loop schemas whose invariants are derived with the loop, so a REFUTED
    here is not this file failing to supply an adequate outline. Each `why`
    states initiation, preservation and exit."""
    out = []
    n, i, r = V("n"), V("i"), V("r")

    def loop(name, params, req, ens, body, why, ptype="int"):
        t = {"name": name,
             "params": [{"name": p, "type": ptype} for p in params],
             "returns": [{"name": "r", "type": "int"}],
             "requires": req, "ensures": ens, "body": body}
        return rec(finish(t), "TRUE", "construction", why, "loop")

    for c in (1, 2, 5, -3):
        body = [
            {"assign": ["r", I(0)]},
            {"var": {"name": "i", "type": "int", "init": I(0)}},
            {"while": {"cond": op("<", i, n),
                       "invariants": [op("==", r, op("*", I(c), i)),
                                      op("and", op(">=", i, I(0)),
                                         op("<=", i, n))],
                       "decreases": op("-", n, i),
                       "body": [{"assign": ["r", op("+", r, I(c))]},
                                {"assign": ["i", op("+", i, I(1))]}]}}]
        out.append(loop(f"gt_loop_acc{abs(c)}{'m' if c < 0 else ''}", ["n"],
                        [op(">=", n, I(0))],
                        [op("==", r, op("*", I(c), n))], body,
                        f"initiation 0 == {c}*0; preservation r+{c} == "
                        f"{c}*(i+1); exit i == n gives r == {c}*n"))
    body = [{"assign": ["r", I(0)]},
            {"var": {"name": "i", "type": "int", "init": V("n")}},
            {"while": {"cond": op(">", i, I(0)),
                       "invariants": [op("==", op("+", r, i), n),
                                      op("and", op(">=", i, I(0)),
                                         op("<=", i, n))],
                       "decreases": i,
                       "body": [{"assign": ["r", op("+", r, I(1))]},
                                {"assign": ["i", op("-", i, I(1))]}]}}]
    out.append(loop("gt_loop_down", ["n"], [op(">=", n, I(0))],
                    [op("==", r, n)], body,
                    "initiation 0 + n == n; preservation (r+1) + (i-1) == "
                    "r+i; "
                    "exit i == 0 gives r == n"))
    body = [{"assign": ["r", I(0)]},
            {"var": {"name": "i", "type": "int", "init": I(0)}},
            {"while": {"cond": op("<", i, n),
                       "invariants": [op("==", op("*", I(2), r),
                                         op("*", i, op("-", i, I(1)))),
                                      op("and", op(">=", i, I(0)),
                                         op("<=", i, n))],
                       "decreases": op("-", n, i),
                       "body": [{"assign": ["r", op("+", r, i)]},
                                {"assign": ["i", op("+", i, I(1))]}]}}]
    out.append(loop("gt_loop_gauss", ["n"], [op(">=", n, I(0))],
                    [op("==", op("*", I(2), r), op("*", n, op("-", n, I(1))))],
                    body,
                    "initiation 0 == 0*(-1); preservation 2(r+i) == i(i-1)+2i "
                    "== i(i+1) == i'(i'-1); exit i == n"))
    body = [{"assign": ["r", I(0)]},
            {"var": {"name": "i", "type": "int", "init": I(0)}},
            {"while": {"cond": op("<", i, n),
                       "invariants": [op("and", op(">=", i, I(0)),
                                         op("<=", i, n)),
                                      op("and", op(">=", r, I(0)),
                                         op("<=", r, i))],
                       "decreases": op("-", n, i),
                       "body": [{"if": {"cond": op(">", i, I(1)),
                                        "then": [{"assign": ["r", op("+", r, I(1))]}],
                                        "else": []}},
                                {"assign": ["i", op("+", i, I(1))]}]}}]
    out.append(loop("gt_loop_count", ["n"], [op(">=", n, I(0))],
                    [op(">=", r, I(0)), op("<=", r, n)], body,
                    "r rises by at most one per iteration while i rises by "
                    "exactly one, so 0 <= r <= i is preserved; exit i == n"))
    body = [{"assign": ["r", I(7)]},
            {"var": {"name": "i", "type": "int", "init": I(0)}},
            {"while": {"cond": op("<", i, n),
                       "invariants": [op("==", r, I(7))],
                       "decreases": op("-", n, i),
                       "body": [{"assign": ["i", op("+", i, I(1))]}]}}]
    out.append(loop("gt_loop_never", ["n"], [op("<=", n, I(0))],
                    [op("==", r, I(7))], body,
                    "requires n <= 0 with i == 0 falsifies the guard on "
                    "entry, "
                    "so r keeps its pre-loop value"))

    false = []
    for base in list(out):
        t = json.loads(json.dumps(base["task"]))
        t["name"] = base["task"]["name"].replace("gt_loop_", "gt_loopf_")
        t["ensures"] = [op("==", V("r"), op("+", e, I(1))) if e.get("op") == "=="
                        and eq_json(e["args"][0], V("r")) else e
                        for e in [t["ensures"][0]]]
        e0 = base["task"]["ensures"][0]
        t["ensures"] = [op("==", op("+", e0["args"][0], I(1)), e0["args"][1])
                        if e0.get("op") == "==" else op("not", e0)]
        finish(t)
        w = falsify(t, cands=[{"n": 0}, {"n": 1}, {"n": 2}, {"n": 3}])
        if w and not w.get("_disagreement"):
            false.append(rec(t, "FALSE", "witness",
                             "the postcondition is off by one from the value "
                             "the loop computes", "loop", w))
    return out + false


def fam_specfun():
    """spec_funs, including one well-founded recursion, with the postcondition
    anchored by the spec_fun rather than the task's own name (SPEC.md gate 3)."""
    out = []
    x, nn = V("x"), V("n")
    dbl = {"name": "dbl", "params": [{"name": "k", "type": "int"}],
           "result": "int", "decreases": I(0),
           "body": op("*", I(2), V("k"))}
    sq = {"name": "sq", "params": [{"name": "k", "type": "int"}],
          "result": "int", "decreases": I(0), "body": op("*", V("k"), V("k"))}
    sm = {"name": "sm", "params": [{"name": "k", "type": "int"}],
          "result": "int", "decreases": V("k"),
          "body": ite(op("<=", V("k"), I(0)), I(0),
                      op("+", V("k"), call("sm", op("-", V("k"), I(1)))))}

    def sf(name, funs, req, ens, body, params=("x",)):
        t = base_task(name, list(params))
        t["spec_funs"], t["requires"], t["ensures"], t["body"] = funs, req, ens, body
        return finish(t)

    out.append(rec(sf("gt_sf_dbl", [dbl], [], [op("==", V("r"), call("dbl", x))],
                      [{"assign": ["r", op("+", x, x)]}]),
                   "TRUE", "construction",
                   "dbl(x) unfolds to 2*x and x + x == 2*x over Z", "specfun"))
    out.append(rec(sf("gt_sf_sq", [sq], [], [op("==", V("r"), call("sq", x)),
                                             op(">=", V("r"), I(0))],
                      [{"assign": ["r", op("*", x, x)]}]),
                   "TRUE", "construction",
                   "sq(x) unfolds to x*x, which the body computes and which "
                   "is "
                   "non-negative over Z", "specfun"))
    for k, val in ((3, 6), (4, 10), (0, 0)):
        out.append(rec(sf(f"gt_sf_sum{k}", [sm], [op("==", nn, I(k))],
                          [op("==", V("r"), call("sm", nn))],
                          [{"assign": ["r", I(val)]}], params=("n",)),
                       "TRUE", "construction",
                       f"requires pins n == {k}; unfolding sm {k} times gives "
                       f"{val}", "specfun"))
        t = sf(f"gt_sff_sum{k}", [sm], [op("==", nn, I(k))],
               [op("==", V("r"), call("sm", nn))],
               [{"assign": ["r", I(val + 1)]}], params=("n",))
        w = falsify(t, cands=[{"n": k}])
        if w and not w.get("_disagreement"):
            out.append(rec(t, "FALSE", "witness",
                           f"sm({k}) == {val} but the body returns {val + 1}",
                           "specfun", w))
    t = sf("gt_sff_dbl", [dbl], [],
           [op("==", V("r"), op("+", call("dbl", x), I(1)))],
           [{"assign": ["r", op("+", x, x)]}])
    w = falsify(t, cands=[{"x": 0}])
    if w and not w.get("_disagreement"):
        out.append(rec(t, "FALSE", "witness",
                       "r == 2x and 2x != 2x + 1 over Z", "specfun", w))
    return out


PIN_WHY = ("`requires` pins every parameter to a literal, so the set of inputs "
           "it admits is a SINGLETON and evaluating SPEC.md's semantics at "
           "that "
           "one point is a complete proof, not a bounded search; the value is "
           "the one interp.py and ck agree on")


def _pin(name, pins, body, value, extra_req=()):
    t = base_task(name, list(pins))
    t["requires"] = ([op("==", V(k), I(v)) for k, v in pins.items()]
                     + list(extra_req))
    t["ensures"] = [op("==", V("r"), I(value))]
    t["body"] = body
    return finish(t)


def fam_pin(rng, n):
    """The postcondition is a LITERAL this file computed from SPEC.md, not a
    syntactic image of the body, so a mistranslation shared by all seven
    lowerings cannot hide behind the mirror's symmetry. The FALSE twin of each
    named case is the value a machine word would produce: a VERIFIED there is
    the integer-width unsoundness, seen without any appeal to consensus."""
    out = []
    x, y = V("x"), V("y")
    cases = [
        ("succ_max32", {"x": 2147483647}, [{"assign": ["r", op("+", x, I(1))]}],
         2147483648, -2147483648, "32-bit two's complement wrap"),
        ("succ_max64", {"x": 9223372036854775807},
         [{"assign": ["r", op("+", x, I(1))]}],
         9223372036854775808, -9223372036854775808, "64-bit wrap"),
        ("pred_min32", {"x": -2147483648}, [{"assign": ["r", op("-", x, I(1))]}],
         -2147483649, 2147483647, "32-bit wrap"),
        ("negmin32", {"x": -2147483648}, [{"assign": ["r", op("neg", x)]}],
         2147483648, -2147483648, "two's complement leaves -2^31 fixed"),
        ("mul32", {"x": 65536, "y": 65536},
         [{"assign": ["r", op("*", x, y)]}], 4294967296, 0,
         "32-bit: 2^16 * 2^16 truncates to 0"),
        ("mul64", {"x": 4294967296, "y": 4294967296},
         [{"assign": ["r", op("*", x, y)]}], 18446744073709551616, 0,
         "64-bit: 2^32 * 2^32 truncates to 0"),
        ("bignum", {"x": 12345678901234567890},
         [{"assign": ["r", op("+", x, x)]}], 24691357802469135780,
         None, "a literal wider than any machine word"),
        ("negprec", {"x": 3, "y": 5},
         [{"assign": ["r", op("*", op("neg", x), y)]}], -15, 15,
         "unary minus binding after the product"),
        ("subassoc", {"x": 10, "y": 4},
         [{"assign": ["r", op("-", op("-", x, y), I(3))]}], 3, 9,
         "subtraction re-associated to the right"),
    ]
    for nm, pins, body, val, wrong, note in cases:
        t = _pin(f"gt_pin_{nm}", pins, json.loads(json.dumps(body)), val)
        out.append(rec(t, "TRUE", "construction", PIN_WHY, "pin", tag=nm))
        if wrong is None:
            continue
        f = _pin(f"gt_pinf_{nm}", pins, json.loads(json.dumps(body)), wrong)
        w = falsify(f, cands=[dict(pins)])
        if w and not w.get("_disagreement"):
            out.append(rec(f, "FALSE", "witness",
                           f"the one admitted input gives {val}, not {wrong} "
                           f"({note})", "pin", w, nm))
    # Generated bodies over pinned inputs: the same singleton argument, applied
    # to expressions no hand-written case would reach.
    for k in range(n):
        params = ["x", "y"][:rng.randint(1, 2)]
        pins = {p: rng.choice((0, 1, -1, 7, -9, 100, 65536, 2147483647,
                               -2147483648, 4294967296, 10 ** 12))
                for p in params}
        body = gen_body(rng, params, "r")
        probe = base_task(f"gt_pin_gen{k:03d}", params)
        probe["requires"] = [op("==", V(p), I(v)) for p, v in pins.items()]
        probe["ensures"] = [op("==", V("r"), I(0))]
        probe["body"] = body
        finish(probe)
        okr, val, _ = _interp_verdict(probe, dict(pins))
        okr2, val2, _ = ck_verdict(probe, dict(pins))
        if not (okr and okr2 and val is not None and val == val2
                and isinstance(val, int) and not isinstance(val, bool)):
            continue
        t = _pin(f"gt_pin_gen{k:03d}", pins, json.loads(json.dumps(body)), val)
        out.append(rec(t, "TRUE", "construction", PIN_WHY, "pin", tag="gen"))
        f = _pin(f"gt_pinf_gen{k:03d}", pins, json.loads(json.dumps(body)),
                 val + 1)
        w = falsify(f, cands=[dict(pins)])
        if w and not w.get("_disagreement"):
            out.append(rec(f, "FALSE", "witness",
                           f"the one admitted input gives {val}, "
                           f"not {val + 1}",
                           "pin", w, "gen"))
    return out


def fam_seqpin():
    """The same singleton argument through a sequence: `requires` fixes the
    length and every element the body reads, so the body's value is determined
    and `at` is defined wherever it is used."""
    out = []
    s = V("s")
    ln = op("len", s)

    def st(name, req, ens, body):
        return finish({"name": name, "params": [{"name": "s", "type": "seq"}],
                       "returns": [{"name": "r", "type": "int"}],
                       "requires": req, "ensures": ens, "body": body})

    req2 = [op("==", ln, I(2)), op("==", op("at", s, I(0)), I(5)),
            op("==", op("at", s, I(1)), I(7))]
    body = [{"assign": ["r", op("+", op("at", s, I(0)), op("at", s, I(1)))]}]
    out.append(rec(st("gt_seqpin_sum", req2, [op("==", V("r"), I(12))], body),
                   "TRUE", "construction",
                   "requires fixes len(s) == 2, s[0] == 5 and s[1] == 7, so "
                   "the "
                   "body's value is 12 at every admitted input and both reads "
                   "are in range", "seqpin"))
    f = st("gt_seqpinf_sum", req2, [op("==", V("r"), I(13))],
           json.loads(json.dumps(body)))
    w = falsify(f, cands=[{"s": [5, 7]}])
    if w and not w.get("_disagreement"):
        out.append(rec(f, "FALSE", "witness",
                       "s = [5,7] is admitted and gives 12, not 13", "seqpin", w))
    reqw = [op("==", ln, I(1)),
            op("==", op("at", s, I(0)), I(2147483647))]
    bodyw = [{"assign": ["r", op("+", op("at", s, I(0)), I(1))]}]
    out.append(rec(st("gt_seqpin_wide", reqw, [op("==", V("r"), I(2147483648))],
                      bodyw), "TRUE", "construction",
                   "requires fixes s[0] == 2^31-1, so the body's value is "
                   "2^31; "
                   "t sequence elements are mathematical integers (SPEC.md "
                   "gate 1)", "seqpin", tag="width"))
    f = st("gt_seqpinf_wide", reqw, [op("==", V("r"), I(-2147483648))],
           json.loads(json.dumps(bodyw)))
    w = falsify(f, cands=[{"s": [2147483647]}])
    if w and not w.get("_disagreement"):
        out.append(rec(f, "FALSE", "witness",
                       "the admitted input gives 2^31, not the 32-bit wrap "
                       "-2^31", "seqpin", w, "width"))
    out.append(rec(st("gt_seq_lennn", [], [op("==", V("r"), I(0)),
                                           op(">=", ln, I(0))],
                      [{"assign": ["r", I(0)]}]),
                   "TRUE", "construction",
                   "SPEC.md gate 1: a seq has length len(s) >= 0", "seqpin"))
    f = st("gt_seqf_len1", [], [op("==", V("r"), I(0)), op(">=", ln, I(1))],
           [{"assign": ["r", I(0)]}])
    w = falsify(f, cands=[{"s": []}])
    if w and not w.get("_disagreement"):
        out.append(rec(f, "FALSE", "witness",
                       "the empty sequence is admitted and has length 0",
                       "seqpin", w))
    return out


def fam_pairs():
    """SPEC.md "Pairs" (2026-09-10): `{"pair": [T1, T2]}`, `fst`/`snd`
    projecting, always defined on a pair; `pair` itself defined iff both
    components are. Hand-derived, `fam_algebra`'s style, one shape per truth
    class this file already grades against, not a mirror-driven family:
    denote()/mirror() need no change to carry a `pair` node through their
    generic op/args walk, but the two identities here are stated directly
    from SPEC.md's own text rather than earned by re-deriving what SPEC.md
    already asserts.

    TRUE: the projection identity itself (`gt_pair_id`), the same identity
    with the construction actually swapped so body and ensures agree
    (`gt_pair_swap_id`), the identity again over the two other component
    types v1 allows -- bool (`gt_pair_bool_id`) and seq (`gt_pair_seq_id`,
    whose `==` on the seq component is SPEC.md's own extensional one, so it
    needs no length guard) -- and a pair PARAMETER projected and recombined
    (`gt_pair_proj_param`), the census shape fuzz_lower.py's f_v1pairs also
    measures, here as a construction proof rather than a fuzz instance.

    FALSE: a body that pairs (x, y) unswapped against an ensures that
    claims the swapped relationship (`gt_pair_false_swap`), and the same
    mismatch over a pair parameter's own two projections
    (`gt_pair_false_proj_param`), both false whenever the two components
    differ, both settled by an exhibited witness.

    ILLDEF: `fst(r) div snd(r)` in the ensures with no requires ever
    pinning `y` away from 0 (`gt_pair_illdef_div`) -- fam_definedness's own
    idiom (a trivial, always-defined body; the obligation lives entirely in
    ensures) read over a pair projection instead of a seq index."""
    out = []
    x, y = V("x"), V("y")
    PXY = [{"name": "x", "type": "int"}, {"name": "y", "type": "int"}]
    PT = {"pair": ["int", "int"]}

    def T(name, params, ret_type, ens, body, why):
        t = {"name": name, "params": params,
             "returns": [{"name": "r", "type": ret_type}],
             "requires": [], "ensures": ens, "body": body}
        finish(t)
        out.append(rec(t, "TRUE", "construction", why, "pairs"))

    T("gt_pair_id", PXY, PT,
      [op("==", op("fst", V("r")), x), op("==", op("snd", V("r")), y)],
      [{"assign": ["r", op("pair", x, y)]}],
      "SPEC.md 'Pairs': fst((a,b)) == a and snd((a,b)) == b, so this holds "
      "at every input by construction")

    T("gt_pair_swap_id", PXY, PT,
      [op("==", op("fst", V("r")), y), op("==", op("snd", V("r")), x)],
      [{"assign": ["r", op("pair", y, x)]}],
      "the body pairs (y, x), so fst(r) == y and snd(r) == x by the same "
      "projection identity as gt_pair_id")

    T("gt_pair_bool_id",
      [{"name": "b", "type": "bool"}, {"name": "n", "type": "int"}],
      {"pair": ["bool", "int"]},
      [op("==", op("fst", V("r")), V("b")),
       op("==", op("snd", V("r")), V("n"))],
      [{"assign": ["r", op("pair", V("b"), V("n"))]}],
      "the projection identity holds over any of the three base component "
      "types SPEC.md 'Pairs' allows, bool included")

    T("gt_pair_seq_id",
      [{"name": "s", "type": "seq"}, {"name": "n", "type": "int"}],
      {"pair": ["seq", "int"]},
      [op("==", op("fst", V("r")), V("s")),
       op("==", op("snd", V("r")), V("n"))],
      [{"assign": ["r", op("pair", V("s"), V("n"))]}],
      "the projection identity again, with a seq component compared by "
      "SPEC.md's own extensional `==` on two seqs, always defined")

    T("gt_pair_proj_param", [{"name": "p", "type": PT}], "int",
      [op("==", V("r"), op("+", op("fst", V("p")), op("snd", V("p"))))],
      [{"assign": ["r", op("+", op("fst", V("p")), op("snd", V("p")))]}],
      "r is assigned exactly the ensures expression, so r == fst(p) + "
      "snd(p) by reflexivity; a pair PARAMETER projected and recombined, "
      "the census shape SPEC.md 'Pairs' names")

    f = {"name": "gt_pair_false_swap", "params": PXY,
         "returns": [{"name": "r", "type": PT}], "requires": [],
         "ensures": [op("==", op("fst", V("r")), y),
                     op("==", op("snd", V("r")), x)],
         "body": [{"assign": ["r", op("pair", x, y)]}]}
    finish(f)
    w = falsify(f, cands=[{"x": 0, "y": 1}])
    if w and not w.get("_disagreement"):
        out.append(rec(f, "FALSE", "witness",
                       "the body pairs (x, y) unswapped; the ensures claims "
                       "the swapped (y, x) relationship instead, false "
                       "whenever x != y, agreed by interp.py and ck_ens",
                       "pairs_false", w, "swap"))

    f2 = {"name": "gt_pair_false_proj_param",
          "params": [{"name": "p", "type": PT}],
          "returns": [{"name": "r", "type": "int"}], "requires": [],
          "ensures": [op("==", V("r"), op("snd", V("p")))],
          "body": [{"assign": ["r", op("fst", V("p"))]}]}
    finish(f2)
    w2 = falsify(f2, cands=[{"p": interp.Pair(0, 1)}])
    if w2 and not w2.get("_disagreement"):
        out.append(rec(f2, "FALSE", "witness",
                       "r is fst(p); the ensures claims r == snd(p), false "
                       "whenever the pair's two components differ, agreed "
                       "by interp.py and ck_ens", "pairs_false", w2, "proj"))

    ill = {"name": "gt_pair_illdef_div", "params": PXY,
           "returns": [{"name": "r", "type": PT}], "requires": [],
           "ensures": [op("==", op("fst", V("r")),
                          op("div", op("fst", V("r")), op("snd", V("r"))))],
           "body": [{"assign": ["r", op("pair", x, y)]}]}
    finish(ill)
    wi = illdefined(ill, cands=[{"x": 0, "y": 0}, {"x": 5, "y": 0}])
    if wi and not wi.get("_disagreement"):
        out.append(rec(ill, "ILLDEF", "witness",
                       "fst(r) div snd(r) is undefined at snd(r) == 0, and "
                       "no requires ever excludes y == 0", "pairs_illdef",
                       wi))
    return out


NEST_T = {"seq": "seq"}     # SPEC.md "Nested sequences (v1)": seq<seq>


def fam_nested():
    """SPEC.md "Nested sequences (v1)" (2026-09-10): `{"seq": "seq"}`, the
    census's own DafnyBench and nl/ population (scratchpad
    shapes-nested/run_output.txt). Hand-derived, `fam_pairs`'s style: one
    shape per truth class this file already grades against. `denote`/
    `mirror`/`ck` need no change to carry a nested read through their
    generic op/args walk (interp.py's own `ev` clone already treats a row
    as a Python tuple of ints, and the outer value as a tuple of those),
    the same "no new machinery" property `fam_pairs` notes for `pair`.

    TRUE: a row-length identity (`gt_nest_rowlen_id`, r := len(m[i]),
    requires 0 <= i < len(m)) and a cell identity (`gt_nest_cell_id`, r :=
    m[i][j], requires both bounds) -- both "r is assigned exactly the
    ensures expression" reflexivity, `gt_pair_proj_param`'s own idiom, a
    requires guard standing in for `fam_pairs`'s always-total pair ops
    since `at`/`len` on a nested seq are partial (`swap_rows`/
    `row_max_len`'s own convention).

    FALSE: a swapped-rows ensures (`gt_nest_false_swap`) -- the body
    computes `swap_rows`'s own real update (rows i and j exchanged), the
    ensures claims the UNSWAPPED relationship instead, false whenever the
    two rows differ -- and a wrong cell (`gt_nest_false_cell`) -- r is
    m[i][j], the ensures claims r == m[i][j] + 1, false unconditionally
    since no integer is its own successor, needing no witness search at
    all (any admitted input refutes it).

    ILLDEF: a cell read with no inner guard (`gt_nest_illdef_cell`) --
    requires pins the OUTER index in range and never the inner one,
    `fam_definedness`'s own idiom (a trivial, always-defined body; the
    obligation lives entirely in ensures) read over a nested index
    instead of a flat one; witness at a SHORT row, m = [[]], i = j = 0,
    the one row m has is empty."""
    out = []

    t1 = {"name": "gt_nest_rowlen_id",
         "params": [{"name": "m", "type": NEST_T}, {"name": "i", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [op("and", op("<=", I(0), V("i")),
                        op("<", V("i"), op("len", V("m"))))],
         "ensures": [op("==", V("r"), op("len", op("at", V("m"), V("i"))))],
         "body": [{"assign": ["r", op("len", op("at", V("m"), V("i")))]}]}
    finish(t1)
    out.append(rec(t1, "TRUE", "construction",
                   "r is assigned exactly the ensures expression, "
                   "len(m[i]), so r == len(m[i]) by reflexivity; requires "
                   "pins i in range, the census's own row-length idiom",
                   "nested"))

    t2 = {"name": "gt_nest_cell_id",
         "params": [{"name": "m", "type": NEST_T}, {"name": "i", "type": "int"},
                   {"name": "j", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [op("and", op("<=", I(0), V("i")),
                        op("<", V("i"), op("len", V("m"))),
                        op("<=", I(0), V("j")),
                        op("<", V("j"), op("len", op("at", V("m"), V("i")))))],
         "ensures": [op("==", V("r"),
                       op("at", op("at", V("m"), V("i")), V("j")))],
         "body": [{"assign": ["r", op("at", op("at", V("m"), V("i")), V("j"))]}]}
    finish(t2)
    out.append(rec(t2, "TRUE", "construction",
                   "r is assigned exactly the ensures expression, "
                   "at(at(m,i),j); requires pins both indices in range, "
                   "SPEC.md's s[i][j] definedness obligation", "nested"))

    f1 = {"name": "gt_nest_false_swap",
         "params": [{"name": "m", "type": NEST_T}, {"name": "i", "type": "int"},
                   {"name": "j", "type": "int"}],
         "returns": [{"name": "r", "type": NEST_T}],
         "requires": [op("and", op("<=", I(0), V("i")),
                        op("<", V("i"), op("len", V("m")))),
                     op("and", op("<=", I(0), V("j")),
                        op("<", V("j"), op("len", V("m"))))],
         "ensures": [op("==", op("at", V("r"), V("i")), op("at", V("m"), V("i"))),
                    op("==", op("at", V("r"), V("j")), op("at", V("m"), V("j")))],
         "body": [{"assign": ["r", op("update",
                                     op("update", V("m"), V("i"),
                                        op("at", V("m"), V("j"))),
                                     V("j"), op("at", V("m"), V("i")))]}]}
    finish(f1)
    w1 = falsify(f1, cands=[{"m": ((0,), (1,)), "i": 0, "j": 1}])
    if w1 and not w1.get("_disagreement"):
        out.append(rec(f1, "FALSE", "witness",
                       "the body computes swap_rows's own real update "
                       "(rows i and j exchanged); the ensures claims the "
                       "UNSWAPPED relationship (r[i] == m[i], r[j] == "
                       "m[j]) instead, false whenever the two rows "
                       "differ, agreed by interp.py and ck_ens",
                       "nested_false", w1, "swap"))

    f2 = {"name": "gt_nest_false_cell",
         "params": [{"name": "m", "type": NEST_T}, {"name": "i", "type": "int"},
                   {"name": "j", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [op("and", op("<=", I(0), V("i")),
                        op("<", V("i"), op("len", V("m"))),
                        op("<=", I(0), V("j")),
                        op("<", V("j"), op("len", op("at", V("m"), V("i")))))],
         "ensures": [op("==", V("r"),
                       op("+", op("at", op("at", V("m"), V("i")), V("j")), I(1)))],
         "body": [{"assign": ["r", op("at", op("at", V("m"), V("i")), V("j"))]}]}
    finish(f2)
    w2 = falsify(f2, cands=[{"m": ((5,),), "i": 0, "j": 0}])
    if w2 and not w2.get("_disagreement"):
        out.append(rec(f2, "FALSE", "witness",
                       "r is m[i][j]; the ensures claims r == m[i][j] + 1, "
                       "false unconditionally since no integer is its own "
                       "successor, agreed by interp.py and ck_ens",
                       "nested_false", w2, "cell"))

    ill = {"name": "gt_nest_illdef_cell",
          "params": [{"name": "m", "type": NEST_T}, {"name": "i", "type": "int"},
                    {"name": "j", "type": "int"}],
          "returns": [{"name": "r", "type": "int"}],
          "requires": [op("and", op("<=", I(0), V("i")),
                         op("<", V("i"), op("len", V("m"))))],
          "ensures": [op("==", V("r"),
                        op("at", op("at", V("m"), V("i")), V("j")))],
          "body": [{"assign": ["r", I(0)]}]}
    finish(ill)
    wi = illdefined(ill, cands=[{"m": ((),), "i": 0, "j": 0}])
    if wi and not wi.get("_disagreement"):
        out.append(rec(ill, "ILLDEF", "witness",
                       "the ensures reads m[i][j] with the OUTER index "
                       "guarded and the inner one never pinned; undefined "
                       "at a SHORT row (m = [[]], i = j = 0, the one row "
                       "m has is empty)", "nested_illdef", wi))
    return out


# ---------------------------------------------------------------------------
# Corpus.
# ---------------------------------------------------------------------------

def build(seed: int, n_mirror: int):
    rng = random.Random(seed)
    recs = fam_mirror(rng, n_mirror)
    recs += fam_algebra()
    recs += fam_width()
    recs += fam_definedness()
    recs += fam_quant()
    recs += fam_loops()
    recs += fam_specfun()
    recs += fam_pin(rng, max(6, n_mirror // 3))
    recs += fam_seqpin()
    recs += fam_syntax(rng)
    trues = [r for r in recs if r["truth"] == "TRUE"
             and r["family"] in ("mirror", "algebra")]
    recs += fam_metamorphic(rng, trues[:max(8, n_mirror // 2)])
    # Appended LAST, after every existing family has already drawn what it
    # draws from `rng`: fam_seqops_mirror's own draws land strictly after
    # theirs in the stream, so a seed's pre-existing task set (name, body,
    # truth label, everything) is byte-identical to what it was before this
    # family existed. Only the seqops_* names are new.
    recs += fam_seqops_mirror(rng, max(4, n_mirror // 4))
    # Appended LAST for the same reason: fam_pairs draws NOTHING from `rng`
    # (every task is hand-derived, fam_algebra's style), so its presence or
    # absence changes no other family's draws either way; it is placed here
    # anyway so a byte-diff of an old seed's task set against a new run
    # shows only gt_pair_* as additions.
    recs += fam_pairs()
    # Appended LAST for the same reason fam_pairs is: fam_nested draws
    # NOTHING from `rng` either (hand-derived, fam_pairs's own style), so
    # its presence changes no other family's draws, and an old seed's task
    # set byte-diffs against this one showing only gt_nest_* as additions.
    recs += fam_nested()
    seen, out = set(), []
    for r in recs:
        nm = r["task"]["name"]
        if nm in seen:
            continue
        seen.add(nm)
        out.append(r)
    return out


def audit(recs):
    """Every TRUE task gets a bounded counterexample scan. A hit is a bug in
    THIS file's construction, never a promotion of the task, so it is fatal."""
    bad, ok = [], []
    for r in recs:
        if r["truth"] == "TRUE":
            w = scan_true(r["task"])
            if w is not None:
                bad.append((r, w))
                continue
        elif r["truth"] == "FALSE":
            if not r["witness"] or r["witness"].get("_disagreement"):
                bad.append((r, r["witness"]))
                continue
        elif r["truth"] == "ILLDEF":
            if not r["witness"] or r["witness"].get("_disagreement"):
                bad.append((r, r["witness"]))
                continue
        else:
            bad.append((r, r.get("witness")))
            continue
        ok.append(r)
    return ok, bad


# ---------------------------------------------------------------------------
# Lower, verify, grade.
# ---------------------------------------------------------------------------

def _cell(bname: str, name: str, path_s: str):
    backend = importlib.import_module(f"verifiers.{bname}")
    p = Path(path_s)
    r, agreed = flake_check(backend.verify, p)
    return name, bname, r.outcome, agreed, r.error[:400], r.exit_code


GOOD = {"TRUE": {Outcome.VERIFIED},
        "FALSE": {Outcome.REFUTED},
        "ILLDEF": {Outcome.REFUTED}}
# Not knowledge either way: recorded as incompleteness, never as a refutation
# and never as a pass (verifiers/__init__.py's taxonomy).
SOFT = {Outcome.TIMEOUT, Outcome.UNPROVED, Outcome.MALFORMED,
        Outcome.TOOL_ERROR, Outcome.VACUOUS, "abstain", "lower-error"}


def grade(truth: str, outcome: str) -> str:
    if outcome in GOOD[truth]:
        return "pass"
    if outcome == Outcome.VERIFIED:
        return "UNSOUND" if truth in ("FALSE", "ILLDEF") else "pass"
    if truth == "TRUE" and outcome == Outcome.REFUTED:
        return "REFUTES-TRUE"
    return "incomplete"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "t-truth-fuzz"))
    ap.add_argument("--jobs", type=int, default=48)
    ap.add_argument("--mirror", type=int, default=70)
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--tasks-only", action="store_true")
    ap.add_argument("--backends", default="")
    a = ap.parse_args()

    out = Path(a.out)
    (out / "tasks").mkdir(parents=True, exist_ok=True)
    (out / "src").mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    recs = build(a.seed, a.mirror)
    recs, bad = audit(recs)
    print(f"corpus: {len(recs)} tasks "
          f"({sum(r['truth'] == 'TRUE' for r in recs)} true, "
          f"{sum(r['truth'] == 'FALSE' for r in recs)} false, "
          f"{sum(r['truth'] == 'ILLDEF' for r in recs)} ill-defined) "
          f"in {time.time() - t0:.0f}s; {len(bad)} candidates discarded")
    for r, w in bad[:20]:
        print(f"  DISCARD {r['task']['name']} [{r['truth']}] {w}")
    if any(r["truth"] == "TRUE" for r, _ in bad):
        print("FATAL: a TRUE label failed its own counterexample scan; the "
              "construction in this file is wrong, and no finding downstream "
              "would be worth anything. Nothing was run.")
        for r, w in bad:
            if r["truth"] == "TRUE":
                print(f"  {r['task']['name']}: {w}")
        return 2
    for r in recs:
        (out / "tasks" / f"{r['task']['name']}.json").write_text(
            json.dumps(r, indent=1), encoding="utf-8")
    if a.tasks_only:
        return 0

    want = set(a.backends.split(",")) if a.backends else None
    cols, present = [], []
    for bname, lmod, suffix in BACKENDS:
        if want and bname not in want:
            continue
        try:
            ver = importlib.import_module(f"verifiers.{bname}").version()
        except (Exception, SystemExit) as e:               # noqa: BLE001
            cols.append((bname, f"ABSENT: {e}"))
            continue
        cols.append((bname, ver))
        present.append((bname, importlib.import_module(lmod).lower, suffix))

    cells, table = [], {}
    for bname, lower, suffix in present:
        for r in recs:
            task = r["task"]
            nm = task["name"]
            try:
                src = lower(task, task["body"])
            except NotImplementedError as e:
                table[(nm, bname)] = ("abstain", True, str(e)[:200], 0)
                continue
            except Exception as e:                          # noqa: BLE001
                table[(nm, bname)] = ("lower-error", True,
                                      f"{type(e).__name__}: {e}"[:200], 0)
                continue
            p = out / "src" / f"{nm}.{suffix}"
            p.write_text(src, encoding="utf-8")
            cells.append((bname, nm, str(p)))

    print(f"{len(present)} kernels x {len(recs)} tasks -> {len(cells)} cells "
          f"(flake n=3)")
    ctx = mp_context()
    done = 0
    with ProcessPoolExecutor(max_workers=a.jobs, mp_context=ctx) as ex:
        futs = [ex.submit(_cell, b, n, p) for b, n, p in cells]
        for fut in as_completed(futs):
            nm, bname, outc, agreed, err, code = fut.result()
            table[(nm, bname)] = (outc, agreed, err, code)
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(cells)} cells, {time.time() - t0:.0f}s")

    rows = []
    for r in recs:
        nm = r["task"]["name"]
        row = {"name": nm, "truth": r["truth"], "family": r["family"],
               "basis": r["basis"], "why": r["why"],
               "witness": r["witness"], "cells": {}}
        for bname, _, _ in present:
            outc, agreed, err, code = table.get((nm, bname),
                                                ("missing", True, "", 0))
            row["cells"][bname] = {"outcome": outc, "agreed": agreed,
                                   "grade": grade(r["truth"], outc),
                                   "error": err, "exit": code}
        rows.append(row)
    (out / "results.json").write_text(
        json.dumps({"generated": datetime.now(timezone.utc).isoformat(),
                    "seed": a.seed, "backends": dict(cols), "rows": rows},
                   indent=1), encoding="utf-8")

    unsound = [(r["name"], b) for r in rows for b, c in r["cells"].items()
               if c["grade"] == "UNSOUND"]
    reft = [(r["name"], b) for r in rows for b, c in r["cells"].items()
            if c["grade"] == "REFUTES-TRUE"]
    names = [b for b, _, _ in present]
    shared = [r["name"] for r in rows
              if names and all(r["cells"][b]["grade"] != "pass"
                              for b in names)]
    print(f"\nUNSOUNDNESS  : {len(unsound)} cells  {unsound[:12]}")
    print(f"REFUTES-TRUE : {len(reft)} cells  {reft[:12]}")
    print(f"ALL-KERNEL   : {len(shared)} tasks  {shared[:12]}")
    print(f"results -> {out / 'results.json'}  ({time.time() - t0:.0f}s)")
    return 1 if (unsound or shared) else 0


if __name__ == "__main__":
    raise SystemExit(main())
