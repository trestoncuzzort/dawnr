#!/usr/bin/env python3
"""fuzz_lower.py: differential fuzzing of the SEVEN LOWERINGS against one
reference semantics for t.

The suite's claim is not "seven kernels agree"; it is "seven kernels agree
BECAUSE each lowering is a faithful translation of SPEC.md". Seven kernels
faithfully agreeing on a mistranslated spec measures nothing. This file
generates random well-formed t tasks, decides each task's ground truth with a
reference interpreter of SPEC.md's semantics (including its partiality), and
then reports every place a kernel's verdict contradicts either another kernel
or that ground truth.

Three independent instruments, in order of strength:

  1. GROUND TRUTH.  ev()/exec_body() below implement SPEC.md exactly:
     mathematical (unbounded) integers, `at` DEFINED IFF 0 <= i < len(s) as
     the Undef exception, left-to-right short-circuit definedness for
     and/or/implies/ite, and forall/exists over [lo,hi) requiring the body
     defined at every point of the range (so an empty range is defined and
     the body need not be). A task whose ensures is falsified on a sampled
     input MUST be refuted by every kernel; a kernel that verifies it has a
     lowering that changed the meaning.

  2. CROSS-KERNEL.  Same real lowering, one kernel verified and another
     refuted. Three causes, distinguished by (1): mistranslation (the
     verifying kernel proves something the task does not say), incompleteness
     (the refuting kernel cannot prove a task instrument (1) says is true),
     or SPEC.md ambiguity.

  3. TWIN STRENGTH.  For each task, whether the twin body is SEMANTICALLY
     different from the real body (COLLAPSE-IF) or the dropped invariant is
     needed for exit-entailment / preservation (INVARIANT-DROP) is decided by
     the interpreter, not by the kernel. A twin that VERIFIES is then either a
     vacuous spec (twin provably differs, kernel accepts it anyway) or a
     benign no-op mutation (twin computes the same thing), and the flip rule
     cannot tell those apart on its own, and the difference is what the
     two-mutation discipline is actually worth.

DIVISION AND MODULO (v1, since 2026-09-08): `div` and `mod` are Euclidean,
undefined at y == 0 exactly as `at` is undefined outside [0, len), per
SPEC.md's "Division and modulo (v1)" section. The `f_v1divmod` family below
generates well-formed tasks over both operators, and this file's own `ev`
clone implements them the same way t/interp.py does: `r = x % abs(y)`, an
Undef at y == 0. Before this date the operators did not exist and the note
here said so; the fz_p_nodiv probe is the one thing that note left behind,
and it still holds for a different reason, given below where the probe is
defined: the JSON op name is the word `div`, and a literal slash token is
still not one.

Own output directory, never t/out/: the suite's drivers write t/out/ and a
second writer of the same filenames corrupts both runs (run_par.py's
_live_conflict records that lesson). Pass --out.

    python3 t/fuzz_lower.py --out DIR --n 120 --seed 1 --jobs 64
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                                        # noqa: E402
from verifiers import Outcome, flake_check, mp_context            # noqa: E402

BACKENDS = [
    ("dafny", "lower_dafny", "dfy"),
    ("verus", "lower_verus", "rs"),
    ("spark", "lower_spark", "ads"),
    ("framac", "lower_framac", "c"),
    ("lean", "lower_lean", "lean"),
    ("rocq", "lower_rocq", "v"),
    ("fstar", "lower_fstar", "fst"),
]

# ===========================================================================
# 1. Reference interpreter: SPEC.md semantics, partiality included.
# ===========================================================================


class Undef(Exception):
    """SPEC.md "Definedness": `at` outside [0, len) has no value, and no
    strict operator over it does either. Never a Python IndexError: an
    out-of-range read that silently returned 0 would be the exact
    totalization SPEC.md calls wrong."""


class Budget(Exception):
    """Interpreter step/range cap. Ground truth is then UNKNOWN for that
    sample and the sample is discarded rather than counted as a verdict."""


MAX_STEPS = 400_000
MAX_RANGE = 20_000        # a quantifier range wider than this is not sampled
MAX_LOOP = 20_000
MAX_SEQ = 1 << 16         # fill length cap, interp.py's MAX_SEQ mirrored


MAX_DEPTH = 60            # self-call nesting; each level costs ~8 Python
                          # frames, so this stays well inside the interpreter's own limit


class St:
    __slots__ = ("n", "d")

    def __init__(self):
        self.n = 0
        self.d = 0

    def tick(self):
        self.n += 1
        if self.n > MAX_STEPS:
            raise Budget("step cap")


def ev(e: dict, env: dict, funs: dict, st: St):
    st.tick()
    if "int" in e:
        return e["int"]
    if "bool" in e:
        return e["bool"]
    if "var" in e:
        try:
            return env[e["var"]]
        except KeyError:
            raise Undef(f"unbound {e['var']}") from None
    if "ite" in e:
        # SPEC.md: the taken branch only.
        c = ev(e["ite"]["cond"], env, funs, st)
        return ev(e["ite"]["then" if c else "else"], env, funs, st)
    if "forall" in e or "exists" in e:
        kind = "forall" if "forall" in e else "exists"
        q = e[kind]
        lo = ev(q["lo"], env, funs, st)
        hi = ev(q["hi"], env, funs, st)
        if hi - lo > MAX_RANGE:
            raise Budget("quantifier range")
        acc = (kind == "forall")
        # SPEC.md: "the body must be defined for every value of the bound
        # variable in [lo, hi)", so the body is evaluated at EVERY point even
        # after the result is decided. An empty range decides without ever
        # needing the body, which is why [0,0) over an undefined body is
        # defined and true.
        for i in range(lo, hi):
            sub = dict(env)
            sub[q["var"]] = i
            v = ev(q["body"], sub, funs, st)
            if kind == "forall":
                acc = acc and v
            else:
                acc = acc or v
        return acc
    if "call" in e:
        c = e["call"]
        f = funs.get(c["fun"])
        if f is None:
            raise Undef(f"no spec_fun {c['fun']}")
        args = [ev(a, env, funs, st) for a in c["args"]]
        sub = {p["name"]: a for p, a in zip(f["params"], args)}
        if "_exec" in f:
            # SPEC.md gate 3: a body self-call is a call of the task itself.
            # Executed for real, not modelled by its contract: ground truth
            # has to be the value, and the contract is what the KERNEL uses.
            body, ret = f["_exec"]
            st.d += 1
            if st.d > MAX_DEPTH:
                st.d -= 1
                raise Budget("self-call depth")
            try:
                sub[ret] = None
                exec_body(body, sub, funs, st, False)
                return sub[ret]
            finally:
                st.d -= 1
        return ev(f["body"], sub, funs, st)
    op = e["op"]
    if op == "and":
        for a in e["args"]:
            if not ev(a, env, funs, st):
                return False
        return True
    if op == "or":
        for a in e["args"]:
            if ev(a, env, funs, st):
                return True
        return False
    if op == "implies":
        return (not ev(e["args"][0], env, funs, st)
                or bool(ev(e["args"][1], env, funs, st)))
    args = [ev(a, env, funs, st) for a in e["args"]]
    if op == "neg":
        return -args[0]
    if op == "not":
        return not args[0]
    if op == "len":
        return len(args[0])
    if op == "at":
        s, i = args
        if not (0 <= i < len(s)):
            raise Undef(f"at index {i} outside [0,{len(s)})")
        return s[i]
    if op == "update":
        # SPEC.md "Sequences as values" (2026-09-09): s[i := v], the same
        # definedness as `at`. A CLONE of interp.ev's own update arm: a
        # fresh tuple, never a mutation of `s`.
        s, i, v = args
        if not (0 <= i < len(s)):
            raise Undef(f"update index {i} outside [0,{len(s)})")
        return s[:i] + (v,) + s[i + 1:]
    if op == "fill":
        # seq(n, v): DEFINED IFF n >= 0. A length past MAX_SEQ decides
        # nothing, like a quantifier range past MAX_RANGE.
        n, v = args
        if n < 0:
            raise Undef(f"fill length {n} < 0")
        if n > MAX_SEQ:
            raise Budget("seq length cap")
        return (v,) * n
    if op == "+":
        return args[0] + args[1]
    if op == "-":
        return args[0] - args[1]
    if op == "*":
        return args[0] * args[1]
    if op in ("div", "mod"):
        # SPEC.md "Division and modulo": Euclidean, undefined at y == 0.
        # A CLONE of interp.ev's own div/mod arm (see this file's module
        # docstring on why the clone is a clone and not a shared import):
        # r = x mod |y| in [0, |y|), q = (x - r) // y exactly.
        x, y = args
        if y == 0:
            raise Undef(f"{op} by zero")
        r = x % abs(y)
        return r if op == "mod" else (x - r) // y
    if op == "==":
        return args[0] == args[1]
    if op == "!=":
        return args[0] != args[1]
    if op == "<":
        return args[0] < args[1]
    if op == "<=":
        return args[0] <= args[1]
    if op == ">":
        return args[0] > args[1]
    if op == ">=":
        return args[0] >= args[1]
    raise ValueError(f"t has no operator {op!r}")


class Violation(Exception):
    def __init__(self, kind, detail):
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


def exec_body(body: list, env: dict, funs: dict, st: St,
              check_ann: bool) -> bool:
    """Execute statements, mutating env. When check_ann, every loop's
    invariants and decreases obligation (SPEC.md gate 2: >= 0 under the
    guard, strictly decreasing per iteration) is CHECKED on this input, so a
    generated annotation that is merely wrong is separated from a lowering
    that is unfaithful.

    Returns True when a `return` statement (SPEC.md "Early exit",
    2026-09-08) ended the run, mirroring interp.exec_body's flag: the value
    is in env under the return name, every enclosing block stops, and (per
    SPEC.md) the loop that was exited owes nothing here for its invariant
    or decreases at that point, so an early return skips those checks for
    the iteration that returned rather than failing them."""
    for s in body:
        st.tick()
        if "assign" in s:
            name, e = s["assign"]
            env[name] = ev(e, env, funs, st)
        elif "return" in s:
            name, e = s["return"]
            env[name] = ev(e, env, funs, st)
            return True
        elif "var" in s:
            d = s["var"]
            env[d["name"]] = ev(d["init"], env, funs, st)
        elif "if" in s:
            c = s["if"]
            if ev(c["cond"], env, funs, st):
                if exec_body(c["then"], env, funs, st, check_ann):
                    return True
            else:
                if exec_body(c["else"], env, funs, st, check_ann):
                    return True
        elif "while" in s:
            w = s["while"]
            invs = w.get("invariants", [])
            it = 0
            while True:
                if check_ann:
                    for k, inv in enumerate(invs):
                        if not ev(inv, env, funs, st):
                            raise Violation("invariant",
                                            f"invariant {k} false at iter {it}")
                g = ev(w["cond"], env, funs, st)
                if not g:
                    break
                d0 = ev(w["decreases"], env, funs, st)
                if check_ann and d0 < 0:
                    raise Violation("decreases",
                                    f"measure {d0} < 0 under the guard")
                if exec_body(w["body"], env, funs, st, check_ann):
                    return True
                d1 = ev(w["decreases"], env, funs, st)
                if check_ann and not d1 < d0:
                    raise Violation("decreases",
                                    f"measure {d0} -> {d1} not strictly down")
                it += 1
                if it > MAX_LOOP:
                    raise Budget("loop cap")
        else:
            raise ValueError(f"t has no statement {s!r}")
    return False


# ===========================================================================
# 2. Well-formedness: SYNTAX.md grammar plus SPEC.md's scope rules.
# ===========================================================================

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
V0_OPS = {"+", "-", "*", "neg", "==", "!=", "<", "<=", ">", ">=",
          "and", "or", "not", "implies"}
# div and mod are v1 (SPEC.md "Division and modulo", 2026-09-08): Euclidean,
# undefined at y == 0, so v1's definedness rules apply to them as to at.
V1_OPS = V0_OPS | {"len", "at", "div", "mod", "update", "fill"}
TERNARY = {"update"}
UNARY = {"neg", "not", "len"}
NARY = {"and", "or"}
BOOLR = {"==", "!=", "<", "<=", ">", ">=", "and", "or", "not", "implies"}
INTR = {"+", "-", "*", "neg", "len"}


def _ty(e, env, funs, ver, errs, bound):
    """Type of e in env, or None; appends to errs. env maps name -> type."""
    if "int" in e:
        return "int"
    if "bool" in e:
        if ver == 0:
            errs.append("bool literal in a v0 task")
        return "bool"
    if "var" in e:
        t = env.get(e["var"])
        if t is None:
            errs.append(f"unbound var {e['var']}")
        return t
    if "ite" in e or "forall" in e or "exists" in e or "call" in e:
        if ver == 0:
            errs.append("v1 expression form in a v0 task")
    if "ite" in e:
        c = e["ite"]
        if _ty(c["cond"], env, funs, ver, errs, bound) != "bool":
            errs.append("ite condition is not bool")
        a = _ty(c["then"], env, funs, ver, errs, bound)
        b = _ty(c["else"], env, funs, ver, errs, bound)
        if a != b:
            errs.append(f"ite branches differ: {a} vs {b}")
        return a
    if "forall" in e or "exists" in e:
        q = e["forall"] if "forall" in e else e["exists"]
        v = q["var"]
        if v in env or v in bound:
            errs.append(f"bound var {v} shadows a name in scope")
        for side in ("lo", "hi"):
            if _ty(q[side], env, funs, ver, errs, bound) != "int":
                errs.append(f"quantifier {side} is not int")
        sub = dict(env)
        sub[v] = "int"
        if _ty(q["body"], sub, funs, ver, errs, bound | {v}) != "bool":
            errs.append("quantifier body is not bool")
        return "bool"
    if "call" in e:
        c = e["call"]
        f = funs.get(c["fun"])
        if f is None:
            errs.append(f"call of unknown fun {c['fun']}")
            return None
        if len(f["params"]) != len(c["args"]):
            errs.append(f"arity mismatch calling {c['fun']}")
        for p, a in zip(f["params"], c["args"]):
            if _ty(a, env, funs, ver, errs, bound) != p["type"]:
                errs.append(f"argument type mismatch calling {c['fun']}")
        return f["result"]
    op = e["op"]
    ok = V0_OPS if ver == 0 else V1_OPS
    if op not in ok:
        errs.append(f"operator {op!r} not in v{ver}")
        return None
    args = e.get("args", [])
    if op in UNARY and len(args) != 1:
        errs.append(f"{op} takes one argument")
    if op in TERNARY and len(args) != 3:
        errs.append(f"{op} takes three arguments")
    if op not in UNARY and op not in NARY and op not in TERNARY and len(args) != 2:
        errs.append(f"{op} takes two arguments")
    if op in NARY and len(args) < 2:
        errs.append(f"{op} needs at least two arguments")
    ts = [_ty(a, env, funs, ver, errs, bound) for a in args]
    if op == "len":
        if ts[0] != "seq":
            errs.append("len of a non-seq")
        return "int"
    if op == "at":
        if ts[0] != "seq" or ts[1] != "int":
            errs.append("at wants (seq, int)")
        return "int"
    if op == "update":
        # SPEC.md "Sequences as values": s[i := v] is (seq, int, int) -> seq.
        if ts[0] != "seq" or ts[1] != "int" or ts[2] != "int":
            errs.append("update wants (seq, int, int)")
        return "seq"
    if op == "fill":
        if ts[0] != "int" or ts[1] != "int":
            errs.append("fill wants (int, int)")
        return "seq"
    if op in ("+", "-", "*", "neg", "div", "mod"):
        if any(t != "int" for t in ts):
            errs.append(f"{op} over non-int")
        return "int"
    if op in ("<", "<=", ">", ">="):
        if any(t != "int" for t in ts):
            errs.append(f"{op} is int-only (SPEC.md gate 1)")
        return "bool"
    if op in ("==", "!="):
        # Two seqs compare extensionally since SPEC.md "Sequences as values".
        if ts[0] != ts[1]:
            errs.append(f"{op} wants two ints, two bools or two seqs")
        return "bool"
    if any(t != "bool" for t in ts):
        errs.append(f"{op} over non-bool")
    return "bool"


def _self_calls(e, name) -> bool:
    if isinstance(e, dict):
        if "call" in e and e["call"]["fun"] == name:
            return True
        return any(_self_calls(v, name) for v in e.values())
    if isinstance(e, list):
        return any(_self_calls(v, name) for v in e)
    return False


def check_wf(task: dict) -> list[str]:
    errs: list[str] = []
    ver = task["t"]
    if not NAME_RE.match(task["name"]):
        errs.append("bad task name")
    if len(task["returns"]) != 1:
        errs.append("exactly one return value (SPEC.md v0 and v1)")
    if not task["ensures"]:
        errs.append("ensures must be non-empty")
    funs = {f["name"]: f for f in task.get("spec_funs", [])}
    if ver == 0 and (funs or "decreases" in task or "gate" in task):
        errs.append("v1 field in a v0 task")
    penv = {p["name"]: p["type"] for p in task["params"]}
    if ver == 0 and any(t != "int" for t in penv.values()):
        errs.append("v0 has int only")
    for i, f in enumerate(task.get("spec_funs", [])):
        fenv = {p["name"]: p["type"] for p in f["params"]}
        earlier = {g["name"]: g for g in task["spec_funs"][:i]}
        earlier[f["name"]] = f              # self-recursion is allowed
        if _ty(f["decreases"], fenv, earlier, ver, errs, set()) != "int":
            errs.append(f"spec_fun {f['name']} decreases is not int")
        if _ty(f["body"], fenv, earlier, ver, errs, set()) != f["result"]:
            errs.append(f"spec_fun {f['name']} body type != result")
    for e in task.get("requires", []):
        if _ty(e, penv, funs, ver, errs, set()) != "bool":
            errs.append("requires clause is not bool")
    ret = task["returns"][0]
    eenv = dict(penv)
    eenv[ret["name"]] = ret["type"]
    for e in task["ensures"]:
        if _ty(e, eenv, funs, ver, errs, set()) != "bool":
            errs.append("ensures clause is not bool")
    if _self_calls(task["ensures"], task["name"]):
        errs.append("ensures references the task name (SPEC.md gate 3)")
    selfrec = _self_calls(task["body"], task["name"])
    if selfrec and "decreases" not in task:
        errs.append("self-recursive body without a task decreases")
    if not selfrec and "decreases" in task:
        errs.append("task decreases without a self-call")
    bfuns = dict(funs)
    if selfrec:
        bfuns[task["name"]] = {"params": task["params"],
                               "result": ret["type"], "body": None,
                               "decreases": None}
    _check_stmts(task["body"], dict(eenv), bfuns, ver, errs, {ret["name"]})
    _check_returns(task["body"], ret["name"], errs)
    return errs


def _check_returns(body, rname, errs):
    """Every `return` names the task's return variable, never a local that
    happens to be assignable in scope (SPEC.md Early exit)."""
    for s in body:
        if "return" in s and s["return"][0] != rname:
            errs.append(f"return names {s['return'][0]}, not the task's return {rname}")
        elif "if" in s:
            _check_returns(s["if"]["then"], rname, errs)
            _check_returns(s["if"]["else"], rname, errs)
        elif "while" in s:
            _check_returns(s["while"]["body"], rname, errs)


def _check_stmts(body, env, funs, ver, errs, assignable):
    for s in body:
        if "assign" in s:
            n, e = s["assign"]
            if n not in assignable:
                errs.append(f"assign to {n}, not a return or local")
            t = _ty(e, env, funs, ver, errs, set())
            if t != env.get(n):
                errs.append(f"assign {n}: {t} into {env.get(n)}")
        elif "var" in s:
            if ver == 0:
                errs.append("local in a v0 task")
            d = s["var"]
            if d["name"] in env:
                errs.append(f"local {d['name']} shadows a name in scope")
            if _ty(d["init"], env, funs, ver, errs, set()) != d["type"]:
                errs.append(f"local {d['name']} init type mismatch")
            env[d["name"]] = d["type"]
            assignable.add(d["name"])
        elif "if" in s:
            c = s["if"]
            if _ty(c["cond"], env, funs, ver, errs, set()) != "bool":
                errs.append("if condition is not bool")
            _check_stmts(c["then"], dict(env), funs, ver, errs, set(assignable))
            _check_stmts(c["else"], dict(env), funs, ver, errs, set(assignable))
        elif "while" in s:
            if ver == 0:
                errs.append("while in a v0 task")
            w = s["while"]
            if _ty(w["cond"], env, funs, ver, errs, set()) != "bool":
                errs.append("loop condition is not bool")
            if "decreases" not in w:
                errs.append("loop without decreases (SPEC.md gate 2)")
            elif _ty(w["decreases"], env, funs, ver, errs, set()) != "int":
                errs.append("loop decreases is not int")
            for inv in w.get("invariants", []):
                if _ty(inv, env, funs, ver, errs, set()) != "bool":
                    errs.append("loop invariant is not bool")
            _check_stmts(w["body"], dict(env), funs, ver, errs, set(assignable))
        elif "return" in s:
            if ver == 0:
                errs.append("return in a v0 task")
            n, e = s["return"]
            if n not in assignable:
                errs.append(f"return names {n}, not the task's return")
            t = _ty(e, env, funs, ver, errs, set())
            if t != env.get(n):
                errs.append(f"return {n}: {t} into {env.get(n)}")
            if s is not body[-1]:
                errs.append("statement after return is unreachable (SPEC.md Early exit)")
        else:
            errs.append(f"t has no statement {sorted(s)!r}")


# ===========================================================================
# 3. Ground truth by sampling.
# ===========================================================================

SMALL = [-3, -2, -1, 0, 1, 2, 3, 4, 5, 7]
BIG = [2 ** 31, -2 ** 31 - 1, 2 ** 40, 10 ** 12, -10 ** 12, 2 ** 63]


def sample_inputs(task, rng, k):
    out = []
    for _ in range(k):
        env = {}
        for p in task["params"]:
            if p["type"] == "seq":
                n = rng.choice([0, 0, 1, 2, 3, 3, 4, 5, 6])
                # SPEC.md gate 1: a seq's ELEMENTS are mathematical integers,
                # same as an int parameter, so they are drawn from the same
                # two pools. Drawing them from SMALL alone made every
                # element-width claim unfalsifiable BY SAMPLING: the
                # 2026-09-01 framac finding (`int *s` typed every element
                # is_sint32) had to be hand-written as fz_p_elemwidth because
                # no generated task could reach a counterexample. 12% here
                # rather than the 8% used for a scalar: a counterexample needs
                # only ONE big element, and a seq has several draws.
                env[p["name"]] = tuple(
                    (rng.choice(BIG) if rng.random() < 0.12
                     else rng.choice(SMALL)) for _ in range(n))
            elif p["type"] == "bool":
                env[p["name"]] = rng.choice([True, False])
            else:
                env[p["name"]] = (rng.choice(BIG) if rng.random() < 0.08
                                  else rng.choice(SMALL))
        out.append(env)
    return out


def _funs_of(task, body):
    """spec_funs, plus the task itself when the body self-calls (gate 3)."""
    funs = {f["name"]: f for f in task.get("spec_funs", [])}
    if _self_calls(body, task["name"]):
        funs[task["name"]] = {"params": task["params"],
                              "_exec": (body, task["returns"][0]["name"])}
    return funs


def ground_truth(task, body, rng, k=260, check_ann=True):
    """Run `body` (real or twin) on sampled inputs satisfying requires.
    Returns a dict; `verdict` is 'refuted' when a sample falsifies ensures or
    an annotation, 'verified' when none of k samples did, 'unknown' when no
    sample got through."""
    funs = _funs_of(task, body)
    ret = task["returns"][0]["name"]
    res = {"n_ok": 0, "cex": None, "kind": None, "results": []}
    for env0 in sample_inputs(task, rng, k):
        st = St()
        try:
            if not all(ev(c, env0, funs, st) for c in task.get("requires", [])):
                continue
        except (Undef, Budget, RecursionError):
            continue
        env = dict(env0)
        env[ret] = None
        try:
            exec_body(body, env, funs, st, check_ann)
        except Violation as v:
            res["cex"] = {k2: _j(v2) for k2, v2 in env0.items()}
            res["kind"] = v.kind
            res["detail"] = str(v)
            break
        except Undef as u:
            res["cex"] = {k2: _j(v2) for k2, v2 in env0.items()}
            res["kind"] = "undefined-body"
            res["detail"] = str(u)
            break
        except (Budget, RecursionError):
            continue
        try:
            bad = [i for i, e in enumerate(task["ensures"])
                   if not ev(e, env, funs, st)]
        except Undef as u:
            res["cex"] = {k2: _j(v2) for k2, v2 in env0.items()}
            res["kind"] = "undefined-ensures"
            res["detail"] = str(u)
            break
        except (Budget, RecursionError):
            continue
        res["n_ok"] += 1
        res["results"].append((tuple(sorted(env0.items())), _j(env[ret])))
        if bad:
            res["cex"] = {k2: _j(v2) for k2, v2 in env0.items()}
            res["kind"] = f"ensures[{bad[0]}]"
            res["detail"] = f"r = {env[ret]}"
            break
    res["verdict"] = ("refuted" if res["cex"] else
                      "verified" if res["n_ok"] else "unknown")
    return res


def _j(v):
    return list(v) if isinstance(v, tuple) else v


def twin_semantics(task, real_body, twin_body, rng, k=260):
    """Does the twin COMPUTE something else? The flip rule reads a twin that
    verifies as 'the spec is vacuous', but a COLLAPSE-IF twin that happens to
    be extensionally equal to the real body verifies for a reason that has
    nothing to do with the spec's strength. Only the interpreter can separate
    those two."""
    funs = _funs_of(task, real_body)
    ret = task["returns"][0]["name"]
    differs = None
    for env0 in sample_inputs(task, rng, k):
        st = St()
        try:
            if not all(ev(c, env0, funs, st) for c in task.get("requires", [])):
                continue
            a = dict(env0)
            a[ret] = None
            exec_body(real_body, a, funs, st, False)
            b = dict(env0)
            b[ret] = None
            exec_body(twin_body, b, funs, st, False)
        except (Undef, Budget, Violation, RecursionError):
            continue
        if a[ret] != b[ret]:
            differs = {k2: _j(v2) for k2, v2 in env0.items()}
            differs["_real"] = _j(a[ret])
            differs["_twin"] = _j(b[ret])
            break
    return differs


def _first_loop(body):
    for s in body:
        if "while" in s and s["while"].get("invariants"):
            return s["while"]
        if "while" in s:
            r = _first_loop(s["while"]["body"])
            if r:
                return r
        if "if" in s:
            r = _first_loop(s["if"]["then"]) or _first_loop(s["if"]["else"])
            if r:
                return r
    return None


def invariant_load_bearing(task, rng, k=4000):
    """INVARIANT-DROP leaves a body that computes the same thing, so the
    interpreter cannot falsify it. What it CAN decide is whether the surviving
    invariants still entail what the loop is used for: sample states over the
    variables in scope at the loop and look for one satisfying
    requires & remaining-invariants & !guard but falsifying ensures (exit
    entailment), or satisfying requires & remaining-invariants & guard whose
    single iteration breaks a surviving invariant (preservation). A witness
    for either means a kernel MUST refute the twin; no witness means a twin
    that verifies says nothing about the spec."""
    loop = _first_loop(task["body"])
    if loop is None or not loop.get("invariants"):
        return {"applies": False}
    funs = _funs_of(task, task["body"])
    ret = task["returns"][0]
    rest = loop["invariants"][1:]
    names = [(p["name"], p["type"]) for p in task["params"]]
    names.append((ret["name"], ret["type"]))
    for s in task["body"]:                 # locals declared before the loop
        if "var" in s:
            names.append((s["var"]["name"], s["var"]["type"]))
    exit_w, pres_w = None, None
    for _ in range(k):
        env = {}
        for n, ty in names:
            if ty == "seq":
                ln = rng.choice([0, 1, 2, 3, 4])
                env[n] = tuple(rng.choice(SMALL) for _ in range(ln))
            elif ty == "bool":
                env[n] = rng.choice([True, False])
            else:
                env[n] = rng.choice(SMALL)
        st = St()
        try:
            if not all(ev(c, env, funs, st) for c in task.get("requires", [])):
                continue
            if not all(ev(c, env, funs, st) for c in rest):
                continue
            g = ev(loop["cond"], env, funs, st)
            if not g and exit_w is None:
                if not all(ev(c, env, funs, st) for c in task["ensures"]):
                    exit_w = {k2: _j(v2) for k2, v2 in env.items()}
            if g and pres_w is None:
                nxt = dict(env)
                exec_body(loop["body"], nxt, funs, st, False)
                if not all(ev(c, nxt, funs, st) for c in rest):
                    pres_w = {k2: _j(v2) for k2, v2 in env.items()}
        except (Undef, Budget, Violation, RecursionError):
            continue
        if exit_w and pres_w:
            break
    return {"applies": True, "exit_witness": exit_w,
            "preservation_witness": pres_w,
            "load_bearing": bool(exit_w or pres_w)}


# ===========================================================================
# 4. Generators. Every family is correct-by-construction; ground_truth() is
#    the check on that claim, not a substitute for it.
# ===========================================================================

def I(n):
    return {"int": n}


def V(x):
    return {"var": x}


def BL(b):
    return {"bool": b}


def OP(o, *a):
    return {"op": o, "args": list(a)}


def LEN(s):
    return OP("len", V(s))


def AT(s, i):
    return OP("at", V(s), i)


def UPD(s, i, v):
    return OP("update", V(s), i, v)


def FILL(n, v):
    return OP("fill", n, v)


def FA(v, lo, hi, b):
    return {"forall": {"var": v, "lo": lo, "hi": hi, "body": b}}


def EX(v, lo, hi, b):
    return {"exists": {"var": v, "lo": lo, "hi": hi, "body": b}}


def ITE(c, t, e):
    return {"ite": {"cond": c, "then": t, "else": e}}


def CALL(f, *a):
    return {"call": {"fun": f, "args": list(a)}}


def ASG(x, e):
    return {"assign": [x, e]}


def RET(x, e):
    return {"return": [x, e]}


def IFS(c, t, e):
    return {"if": {"cond": c, "then": t, "else": e}}


def LOC(n, ty, init):
    return {"var": {"name": n, "type": ty, "init": init}}


def WH(c, invs, dec, b):
    return {"while": {"cond": c, "invariants": invs,
                      "decreases": dec, "body": b}}


def _defined_first(invs):
    """Invariants in the order a kernel can check them (2026-09-09, the
    sequences-as-values family): every kernel checks an invariant's own
    definedness with only the EARLIER invariants in context, so a value
    invariant that reads r[k] must come after the invariants that bound
    len(r) and the loop index. The committed reverse task is written that
    way; the family's first draft put the value invariant first and read
    unproved in six columns on every loop shape (Dafny: "index out of
    range" on the invariant itself). Invariants with no `at` keep their
    order and go first; the rest follow in their order."""
    def has_at(e):
        if isinstance(e, dict):
            return e.get("op") in ("at", "update") or any(has_at(v) for v in e.values())
        if isinstance(e, list):
            return any(has_at(v) for v in e)
        return False
    return [e for e in invs if not has_at(e)] + [e for e in invs if has_at(e)]


def WH_DF(c, invs, dec, b):
    return WH(c, _defined_first(invs), dec, b)


def AND(*a):
    return OP("and", *a) if len(a) > 1 else a[0]


def _range_req(name, hi):
    """0 <= name < hi, the `at`/`update` in-bounds idiom used across the
    index-taking families and f_v1seqval below."""
    return AND(OP("<=", I(0), V(name)), OP("<", V(name), hi))


CMPS = ["==", "!=", "<", "<=", ">", ">="]
NEGCMP = {"==": "!=", "!=": "==", "<": ">=", ">=": "<", ">": "<=", "<=": ">"}
# Identifiers avoided across seven surface syntaxes: Ada/C/Dafny/Lean/Rocq/F*
# keywords and the `_loop`/`_n`/`_len` namespaces the lowerings reserve.
PNAMES = ["x", "y", "z", "w", "u"]


def _lin(rng, names, depth=0):
    """A small linear-ish integer expression; `*` only against a literal so
    the families stay inside what every SMT backend decides."""
    if depth >= 2 or not names or rng.random() < 0.35:
        return (V(rng.choice(names)) if names and rng.random() < 0.6
                else I(rng.choice([-5, -3, -2, -1, 0, 1, 2, 3, 4, 7, 11])))
    r = rng.random()
    if r < 0.3:
        return OP("+", _lin(rng, names, depth + 1), _lin(rng, names, depth + 1))
    if r < 0.6:
        return OP("-", _lin(rng, names, depth + 1), _lin(rng, names, depth + 1))
    if r < 0.75:
        return OP("neg", _lin(rng, names, depth + 1))
    return OP("*", I(rng.choice([-3, -2, 2, 3])), _lin(rng, names, depth + 1))


def _cmp(rng, names):
    return OP(rng.choice(CMPS), _lin(rng, names), _lin(rng, names))


def _cond(rng, names):
    """An `if` condition. SYNTAX.md's Stmt row puts a full Expr here, so the
    boolean connectives belong in a v0 condition as much as a comparison
    does; lower_rocq.py's cond_bool0 is the one lowering that rejects them
    (measured, see the report)."""
    r = rng.random()
    if r < 0.78:
        return _cmp(rng, names)
    if r < 0.86:
        return OP("and", _cmp(rng, names), _cmp(rng, names))
    if r < 0.93:
        return OP("or", _cmp(rng, names), _cmp(rng, names))
    return OP("not", _cmp(rng, names))


def _negate(e):
    if "op" in e and e["op"] in NEGCMP:
        return OP(NEGCMP[e["op"]], *e["args"])
    return OP("not", e)


def f_v0if(rng, idx):
    """v0: nested if/else over int params; ensures pins every path. Twin is
    COLLAPSE-IF."""
    k = rng.choice([1, 1, 2, 2, 3])
    names = PNAMES[:k]
    depth = rng.choice([1, 1, 2, 2, 3])

    def build(pc, d):
        if d == 0:
            return [ASG("r", _lin(rng, names))], [(pc, None)]
        c = _cond(rng, names)
        tb, tl = build(pc + [c], d - 1)
        eb, el = build(pc + [_negate(c)], d - 1)
        return [IFS(c, tb, eb)], tl + el

    body, leaves = build([], depth)
    ens = []
    for pc, _ in leaves:
        pass
    # ensures is derived from the body's own leaves: one implication per path.
    def paths(stmts, pc):
        for s in stmts:
            if "assign" in s:
                yield pc, s["assign"][1]
            else:
                c = s["if"]["cond"]
                yield from paths(s["if"]["then"], pc + [c])
                yield from paths(s["if"]["else"], pc + [_negate(c)])

    for pc, val in paths(body, []):
        ens.append(OP("implies", AND(*pc), OP("==", V("r"), val))
                   if pc else OP("==", V("r"), val))
    return {"t": 0, "name": f"fz_v0if_{idx:03d}",
            "params": [{"name": n, "type": "int"} for n in names],
            "returns": [{"name": "r", "type": "int"}],
            "requires": [], "ensures": ens, "body": body}


def f_v0loose(rng, idx):
    """v0 with a DELIBERATELY loose spec (max/abs shaped): the ensures pins
    the result only up to a choice, so whether COLLAPSE-IF is refutable is a
    property of the spec rather than of the mutation."""
    names = PNAMES[:2]
    c = OP(rng.choice([">=", ">", "<=", "<"]), V("x"), V("y"))
    body = [IFS(c, [ASG("r", V("x"))], [ASG("r", V("y"))])]
    if rng.random() < 0.5:
        ens = [OP(">=", V("r"), V("x")), OP(">=", V("r"), V("y")),
               OP("or", OP("==", V("r"), V("x")), OP("==", V("r"), V("y")))]
    else:                       # strictly weaker: only membership
        ens = [OP("or", OP("==", V("r"), V("x")), OP("==", V("r"), V("y")))]
    return {"t": 0, "name": f"fz_v0loose_{idx:03d}",
            "params": [{"name": n, "type": "int"} for n in names],
            "returns": [{"name": "r", "type": "int"}],
            "requires": [], "ensures": ens, "body": body}


def f_v1bool(rng, idx):
    """v1 bool return, boolean structure in the spec; COLLAPSE-IF twin."""
    names = PNAMES[:rng.choice([1, 2])]
    a, b = _cmp(rng, names), _cmp(rng, names)
    form = rng.choice([OP("and", a, b), OP("or", a, b),
                       OP("implies", a, b), OP("not", a),
                       OP("and", a, OP("not", b))])
    body = [IFS(form, [ASG("r", BL(True))], [ASG("r", BL(False))])]
    return {"t": 1, "name": f"fz_v1bool_{idx:03d}", "gate": "quantifiers",
            "params": [{"name": n, "type": "int"} for n in names],
            "returns": [{"name": "r", "type": "bool"}],
            "requires": [], "ensures": [OP("==", V("r"), form)], "body": body}


def f_v1loop(rng, idx):
    """v1 gate 2: one accumulating loop, closed-form ensures, invariant 0 the
    accumulator relation (INVARIANT-DROP twin)."""
    shape = rng.choice(["mulk", "sum", "odd", "down", "affine"])
    k = rng.choice([-3, -2, -1, 1, 2, 3, 5])
    c0 = rng.choice([0, 0, 1, -2, 4])
    params = [{"name": "n", "type": "int"}]
    req = [OP(">=", V("n"), I(0))]
    if shape == "mulk":
        params.append({"name": "y", "type": "int"})
        step, kk = V("y"), V("y")
    else:
        step = kk = I(k)
    if shape == "down":
        body = [ASG("r", I(c0)), LOC("i", "int", V("n")),
                WH(OP(">", V("i"), I(0)),
                   [OP("==", V("r"),
                       OP("+", I(c0),
                          OP("*", OP("-", V("n"), V("i")), kk))),
                    AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), V("n")))],
                   V("i"),
                   [ASG("r", OP("+", V("r"), step)),
                    ASG("i", OP("-", V("i"), I(1)))])]
        ens = [OP("==", V("r"), OP("+", I(c0), OP("*", V("n"), kk)))]
    elif shape == "sum":
        body = [ASG("r", I(0)), LOC("i", "int", I(0)),
                WH(OP("<", V("i"), V("n")),
                   [OP("==", OP("*", I(2), V("r")),
                       OP("*", V("i"), OP("+", V("i"), I(1)))),
                    AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), V("n")))],
                   OP("-", V("n"), V("i")),
                   [ASG("i", OP("+", V("i"), I(1))),
                    ASG("r", OP("+", V("r"), V("i")))])]
        ens = [OP("==", OP("*", I(2), V("r")),
                  OP("*", V("n"), OP("+", V("n"), I(1))))]
    elif shape == "odd":
        body = [ASG("r", I(0)), LOC("i", "int", I(0)),
                WH(OP("<", V("i"), V("n")),
                   [OP("==", V("r"), OP("*", V("i"), V("i"))),
                    AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), V("n")))],
                   OP("-", V("n"), V("i")),
                   [ASG("r", OP("+", V("r"),
                                OP("+", OP("*", I(2), V("i")), I(1)))),
                    ASG("i", OP("+", V("i"), I(1)))])]
        ens = [OP("==", V("r"), OP("*", V("n"), V("n")))]
    else:                                   # mulk / affine, up-counting
        body = [ASG("r", I(c0)), LOC("i", "int", I(0)),
                WH(OP("<", V("i"), V("n")),
                   [OP("==", V("r"),
                       OP("+", I(c0), OP("*", V("i"), kk))),
                    AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), V("n")))],
                   OP("-", V("n"), V("i")),
                   [ASG("r", OP("+", V("r"), step)),
                    ASG("i", OP("+", V("i"), I(1)))])]
        ens = [OP("==", V("r"), OP("+", I(c0), OP("*", V("n"), kk)))]
    return {"t": 1, "name": f"fz_v1loop_{idx:03d}", "gate": "loops",
            "params": params, "returns": [{"name": "r", "type": "int"}],
            "requires": req, "ensures": ens, "body": body}


def _pred(rng, elem, names):
    """A predicate over one sequence element; the constant is a literal or a
    parameter, both signs represented."""
    op = rng.choice(CMPS)
    rhs = (V(rng.choice(names)) if names and rng.random() < 0.5
           else I(rng.choice([-3, -1, 0, 0, 1, 2, 4])))
    return OP(op, elem, rhs), op, rhs


def f_v1scan(rng, idx):
    """v1 gates 1+2: a seq scan whose ensures is a bounded quantifier and
    whose loop carries the matching invariant."""
    kind = rng.choice(["forall", "exists", "max", "search"])
    extra = rng.random() < 0.6
    params = [{"name": "s", "type": "seq"}]
    if extra:
        params.append({"name": "x", "type": "int"})
    names = ["x"] if extra else []
    if kind in ("forall", "exists"):
        p_i, op, rhs = _pred(rng, AT("s", V("i")), names)
        p_j = OP(op, AT("s", V("j")), rhs)
        p_cur = OP(op, AT("s", V("i")), rhs)
        if kind == "forall":
            ens = [OP("==", V("r"), FA("i", I(0), LEN("s"), p_i))]
            inv0 = OP("==", V("r"),
                      FA("j", I(0), V("i"),
                         OP("implies", OP("<", V("j"), LEN("s")), p_j)))
            init, hit = BL(True), BL(False)
            cond = _negate(p_cur)
        else:
            ens = [OP("==", V("r"), EX("i", I(0), LEN("s"), p_i))]
            inv0 = OP("==", V("r"),
                      EX("j", I(0), V("i"),
                         OP("and", OP("<", V("j"), LEN("s")), p_j)))
            init, hit = BL(False), BL(True)
            cond = p_cur
        body = [ASG("r", init), LOC("i", "int", I(0)),
                WH(OP("<", V("i"), LEN("s")),
                   [inv0, OP(">=", V("i"), I(0))],
                   OP("-", LEN("s"), V("i")),
                   [IFS(cond, [ASG("r", hit)], []),
                    ASG("i", OP("+", V("i"), I(1)))])]
        return {"t": 1, "name": f"fz_v1scan_{idx:03d}", "gate": "quantifiers",
                "params": params, "returns": [{"name": "r", "type": "bool"}],
                "requires": [], "ensures": ens, "body": body}
    if kind == "max":
        want_max = rng.random() < 0.5
        rel = ">=" if want_max else "<="
        better = ">" if want_max else "<"
        ens = [FA("i", I(0), LEN("s"), OP(rel, V("r"), AT("s", V("i")))),
               EX("i", I(0), LEN("s"), OP("==", V("r"), AT("s", V("i"))))]
        body = [ASG("r", AT("s", I(0))), LOC("i", "int", I(1)),
                WH(OP("<", V("i"), LEN("s")),
                   [FA("j", I(0), V("i"),
                       OP("implies", OP("<", V("j"), LEN("s")),
                          OP(rel, V("r"), AT("s", V("j"))))),
                    EX("j", I(0), V("i"),
                       OP("and", OP("<", V("j"), LEN("s")),
                          OP("==", V("r"), AT("s", V("j"))))),
                    OP(">=", V("i"), I(1))],
                   OP("-", LEN("s"), V("i")),
                   [IFS(OP(better, AT("s", V("i")), V("r")),
                        [ASG("r", AT("s", V("i")))], []),
                    ASG("i", OP("+", V("i"), I(1)))])]
        return {"t": 1, "name": f"fz_v1scan_{idx:03d}", "gate": "quantifiers",
                "params": [{"name": "s", "type": "seq"}],
                "returns": [{"name": "r", "type": "int"}],
                "requires": [OP(">", LEN("s"), I(0))],
                "ensures": ens, "body": body}
    # search: first index whose element satisfies the predicate, else -1
    if not extra:
        params.append({"name": "x", "type": "int"})
        names = ["x"]
    p_i, op, rhs = _pred(rng, AT("s", V("i")), names)
    p_j = OP(op, AT("s", V("j")), rhs)
    p_r = OP(op, AT("s", V("r")), rhs)
    nomatch_j = OP("implies", OP("<", V("j"), LEN("s")),
                   _negate(OP(op, AT("s", V("j")), rhs)))
    ens = [OP("or", OP("==", V("r"), I(-1)),
              OP("and", OP(">=", V("r"), I(0)),
                 OP("<", V("r"), LEN("s")), p_r)),
           OP("implies", OP("==", V("r"), I(-1)),
              FA("i", I(0), LEN("s"), _negate(p_i))),
           OP("implies", OP("!=", V("r"), I(-1)),
              FA("j", I(0), V("r"), nomatch_j))]
    body = [ASG("r", I(-1)), LOC("i", "int", I(0)),
            WH(OP("and", OP("<", V("i"), LEN("s")),
                  OP("==", V("r"), I(-1))),
               [OP("implies", OP("==", V("r"), I(-1)),
                   FA("j", I(0), V("i"), nomatch_j)),
                OP("implies", OP("!=", V("r"), I(-1)),
                   OP("and", OP(">=", V("r"), I(0)),
                      OP("<", V("r"), LEN("s")), p_r,
                      FA("j", I(0), V("r"), nomatch_j))),
                AND(OP(">=", V("i"), I(0)),
                    OP("<=", V("i"), LEN("s")))],
               OP("-", LEN("s"), V("i")),
               [IFS(OP(op, AT("s", V("i")), rhs),
                    [ASG("r", V("i"))], []),
                ASG("i", OP("+", V("i"), I(1)))])]
    return {"t": 1, "name": f"fz_v1scan_{idx:03d}", "gate": "loops",
            "params": params, "returns": [{"name": "r", "type": "int"}],
            "requires": [], "ensures": ens, "body": body}


def f_v1rec(rng, idx):
    """v1 gate 3: a spec_fun anchoring the spec and a self-recursive body
    carrying the task decreases. COLLAPSE-IF twin (no loop)."""
    shape = rng.choice(["linear", "geom", "two", "sub"])
    k = rng.choice([-2, 1, 2, 3])
    base = rng.choice([0, 1, 2, -1])
    if shape == "linear":
        sf = {"name": "g", "params": [{"name": "n", "type": "int"}],
              "result": "int", "decreases": V("n"),
              "body": ITE(OP("<=", V("n"), I(0)), I(base),
                          OP("+", I(k), CALL("g", OP("-", V("n"), I(1)))))}
        body = [IFS(OP("==", V("n"), I(0)), [ASG("r", I(base))],
                    [ASG("r", OP("+", I(k),
                                 CALL("fz_v1rec_%03d" % idx,
                                      OP("-", V("n"), I(1)))))])]
    elif shape == "geom":
        sf = {"name": "g", "params": [{"name": "n", "type": "int"}],
              "result": "int", "decreases": V("n"),
              "body": ITE(OP("<=", V("n"), I(0)), I(1),
                          OP("*", I(k), CALL("g", OP("-", V("n"), I(1)))))}
        body = [IFS(OP("==", V("n"), I(0)), [ASG("r", I(1))],
                    [ASG("r", OP("*", I(k),
                                 CALL("fz_v1rec_%03d" % idx,
                                      OP("-", V("n"), I(1)))))])]
    elif shape == "two":
        sf = {"name": "g", "params": [{"name": "n", "type": "int"}],
              "result": "int", "decreases": V("n"),
              "body": ITE(OP("<=", V("n"), I(0)), I(base),
                          ITE(OP("==", V("n"), I(1)), I(base + 1),
                              OP("+", CALL("g", OP("-", V("n"), I(1))),
                                 CALL("g", OP("-", V("n"), I(2))))))}
        me = "fz_v1rec_%03d" % idx
        body = [IFS(OP("==", V("n"), I(0)), [ASG("r", I(base))],
                    [IFS(OP("==", V("n"), I(1)), [ASG("r", I(base + 1))],
                         [ASG("r", OP("+",
                                      CALL(me, OP("-", V("n"), I(1))),
                                      CALL(me, OP("-", V("n"), I(2)))))])])]
    else:                                   # subtractive, two parameters
        sf = {"name": "g", "params": [{"name": "n", "type": "int"},
                                      {"name": "m", "type": "int"}],
              "result": "int", "decreases": OP("+", V("n"), V("m")),
              "body": ITE(OP("<=", V("n"), I(0)), V("m"),
                          ITE(OP("<=", V("m"), I(0)), V("n"),
                              ITE(OP(">", V("n"), V("m")),
                                  CALL("g", OP("-", V("n"), V("m")), V("m")),
                                  ITE(OP(">", V("m"), V("n")),
                                      CALL("g", V("n"),
                                           OP("-", V("m"), V("n"))),
                                      V("n")))))}
        me = "fz_v1rec_%03d" % idx
        body = [IFS(OP("==", V("n"), I(0)), [ASG("r", V("m"))],
                    [IFS(OP("==", V("m"), I(0)), [ASG("r", V("n"))],
                         [IFS(OP(">", V("n"), V("m")),
                              [ASG("r", CALL(me, OP("-", V("n"), V("m")),
                                             V("m")))],
                              [IFS(OP(">", V("m"), V("n")),
                                   [ASG("r", CALL(me, V("n"),
                                                  OP("-", V("m"), V("n"))))],
                                   [ASG("r", V("n"))])])])])]
        return {"t": 1, "name": me, "gate": "recursion",
                "params": [{"name": "n", "type": "int"},
                           {"name": "m", "type": "int"}],
                "returns": [{"name": "r", "type": "int"}],
                "requires": [OP(">=", V("n"), I(0)), OP(">=", V("m"), I(0))],
                "ensures": [OP("==", V("r"), CALL("g", V("n"), V("m")))],
                "spec_funs": [sf], "decreases": OP("+", V("n"), V("m")),
                "body": body}
    return {"t": 1, "name": "fz_v1rec_%03d" % idx, "gate": "recursion",
            "params": [{"name": "n", "type": "int"}],
            "returns": [{"name": "r", "type": "int"}],
            "requires": [OP(">=", V("n"), I(0))],
            "ensures": [OP("==", V("r"), CALL("g", V("n")))],
            "spec_funs": [sf], "decreases": V("n"), "body": body}


def f_v1def(rng, idx):
    """SPEC.md "Definedness", the corners it specifies by name: `at` under
    each short-circuit position, an oversized quantifier range whose body is
    guarded by `implies`, an empty range over a body that has no value
    anywhere, and a negative lower bound."""
    kind = rng.choice(["andguard", "orguard", "impliesguard", "iteguard",
                       "overrange", "emptyrange", "negrange", "lastelem"])
    me = f"fz_v1def_{idx:03d}"
    s, x = "s", "x"
    if kind == "andguard":
        g = OP("and", OP(">=", V(x), I(0)), OP("<", V(x), LEN(s)),
               OP(">", AT(s, V(x)), I(0)))
        body = [IFS(OP("and", OP(">=", V(x), I(0)), OP("<", V(x), LEN(s))),
                    [IFS(OP(">", AT(s, V(x)), I(0)),
                         [ASG("r", I(1))], [ASG("r", I(0))])],
                    [ASG("r", I(0))])]
        ens = [OP("==", V("r"), ITE(g, I(1), I(0)))]
    elif kind == "orguard":
        g = OP("or", OP("<", V(x), I(0)), OP(">=", V(x), LEN(s)),
               OP(">", AT(s, V(x)), I(0)))
        body = [IFS(OP("or", OP("<", V(x), I(0)), OP(">=", V(x), LEN(s))),
                    [ASG("r", I(1))],
                    [IFS(OP(">", AT(s, V(x)), I(0)),
                         [ASG("r", I(1))], [ASG("r", I(0))])])]
        ens = [OP("==", V("r"), ITE(g, I(1), I(0)))]
    elif kind == "impliesguard":
        g = OP("implies", OP("and", OP(">=", V(x), I(0)),
                             OP("<", V(x), LEN(s))),
               OP(">=", AT(s, V(x)), I(0)))
        body = [IFS(OP("and", OP(">=", V(x), I(0)), OP("<", V(x), LEN(s))),
                    [IFS(OP(">=", AT(s, V(x)), I(0)),
                         [ASG("r", I(1))], [ASG("r", I(0))])],
                    [ASG("r", I(1))])]
        ens = [OP("==", V("r"), ITE(g, I(1), I(0)))]
    elif kind == "iteguard":
        g = OP(">", ITE(OP("and", OP(">=", V(x), I(0)),
                           OP("<", V(x), LEN(s))),
                        AT(s, V(x)), I(0)), I(0))
        body = [IFS(OP("and", OP(">=", V(x), I(0)), OP("<", V(x), LEN(s))),
                    [IFS(OP(">", AT(s, V(x)), I(0)),
                         [ASG("r", I(1))], [ASG("r", I(0))])],
                    [ASG("r", I(0))])]
        ens = [OP("==", V("r"), ITE(g, I(1), I(0)))]
    elif kind == "overrange":
        # hi = len(s) + 3 escapes the sequence; SPEC.md keeps the body
        # DEFINED because `implies` is lazy in its second argument.
        g = FA("i", I(0), OP("+", LEN(s), I(3)),
               OP("implies", OP("<", V("i"), LEN(s)),
                  OP(">=", AT(s, V("i")), I(0))))
        body = [IFS(g, [ASG("r", I(1))], [ASG("r", I(0))])]
        ens = [OP("==", V("r"), ITE(g, I(1), I(0)))]
    elif kind == "emptyrange":
        # hi <= lo: SPEC.md makes forall true / exists false WITHOUT the body
        # ever being evaluated, so a body with no value anywhere is legal.
        g = OP("and", FA("i", I(0), I(0), OP("==", AT(s, V("i")), I(9))),
               OP("not", EX("i", I(5), I(2), OP("==", AT(s, V("i")), I(9)))))
        body = [IFS(g, [ASG("r", I(1))], [ASG("r", I(0))])]
        ens = [OP("==", V("r"), I(1)), OP("==", V("r"), ITE(g, I(1), I(0)))]
    elif kind == "negrange":
        g = FA("i", I(-3), LEN(s),
               OP("implies", OP(">=", V("i"), I(0)),
                  OP(">=", AT(s, V("i")), I(0))))
        body = [IFS(g, [ASG("r", I(1))], [ASG("r", I(0))])]
        ens = [OP("==", V("r"), ITE(g, I(1), I(0)))]
    else:                                   # lastelem
        g = OP(">", AT(s, OP("-", LEN(s), I(1))), I(0))
        body = [IFS(g, [ASG("r", I(1))], [ASG("r", I(0))])]
        return {"t": 1, "name": me, "gate": "quantifiers",
                "params": [{"name": s, "type": "seq"}],
                "returns": [{"name": "r", "type": "int"}],
                "requires": [OP(">", LEN(s), I(0))],
                "ensures": [OP("==", V("r"), ITE(g, I(1), I(0)))],
                "body": body}
    params = [{"name": s, "type": "seq"}]
    if kind in ("andguard", "orguard", "impliesguard", "iteguard"):
        params.append({"name": x, "type": "int"})
    return {"t": 1, "name": me, "gate": "quantifiers", "params": params,
            "returns": [{"name": "r", "type": "int"}],
            "requires": [], "ensures": ens, "body": body}


def f_v1nest(rng, idx):
    """A loop whose body nests an `if` inside an `if`, and a statement after
    the loop: pre-order twin selection and per-branch invariant preservation
    at once."""
    me = f"fz_v1nest_{idx:03d}"
    k = rng.choice([1, 2, 3])
    body = [ASG("r", I(0)), LOC("i", "int", I(0)),
            WH(OP("<", V("i"), V("n")),
               [OP("==", V("r"), OP("*", V("i"), I(k))),
                AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), V("n")))],
               OP("-", V("n"), V("i")),
               [IFS(OP(">=", V("i"), I(0)),
                    [IFS(OP("<", V("i"), V("n")),
                         [ASG("r", OP("+", V("r"), I(k)))],
                         [ASG("r", OP("+", V("r"), I(k)))])],
                    [ASG("r", OP("+", V("r"), I(k)))]),
                ASG("i", OP("+", V("i"), I(1)))]),
            ASG("r", OP("+", V("r"), I(0)))]
    return {"t": 1, "name": me, "gate": "loops",
            "params": [{"name": "n", "type": "int"}],
            "returns": [{"name": "r", "type": "int"}],
            "requires": [OP(">=", V("n"), I(0))],
            "ensures": [OP("==", V("r"), OP("*", V("n"), I(k)))],
            "body": body}


DIVMOD_K = [2, 3, 4, 5, 6, 7, 8, 9, 10]


def f_v1divmod(rng, idx):
    """v1 "Division and modulo" (SPEC.md, 2026-09-08): three shapes over the
    Euclidean `div`/`mod` pair. `ceildiv` and `law` get a COLLAPSE-IF twin
    from their `if`; `digitsum` gets INVARIANT-DROP from its loop."""
    shape = rng.choice(["ceildiv", "digitsum"])
    me = f"fz_v1divmod_{idx:03d}"
    if shape == "ceildiv":
        # Ceiling division built from floor-style Euclidean div/mod: exact
        # when k divides x, one more than the floor otherwise. The `if` is a
        # real branch, not a filler one: COLLAPSE-IF applies the exact-case
        # formula everywhere, which is wrong whenever k does not divide x, so
        # the twin is refutable.
        k = rng.choice(DIVMOD_K)
        body = [IFS(OP("==", OP("mod", V("x"), I(k)), I(0)),
                    [ASG("r", OP("div", V("x"), I(k)))],
                    [ASG("r", OP("+", OP("div", V("x"), I(k)), I(1)))])]
        ens = [OP(">=", OP("*", V("r"), I(k)), V("x")),
               OP("<", OP("*", OP("-", V("r"), I(1)), I(k)), V("x"))]
        return {"t": 1, "name": me,
                "params": [{"name": "x", "type": "int"}],
                "returns": [{"name": "r", "type": "int"}],
                "requires": [], "ensures": ens, "body": body}
    if shape == "digitsum":
        # Generalizes t/tasks/digit_sum.json (base 10, a spec_fun) to a
        # random base k and a closed-form ensures instead: peeling the last
        # base-k digit (mod k) and shifting (div k) both preserve r + i's
        # residue mod (k - 1), which is why a digit sum agrees with its own
        # number mod (k - 1). Same invariant shape, no spec_fun needed.
        k = rng.choice([2, 3, 4, 5, 8, 10, 16])
        m = k - 1
        body = [ASG("r", I(0)), LOC("i", "int", V("n")),
                WH(OP(">", V("i"), I(0)),
                   [OP(">=", V("i"), I(0)),
                    OP("==", OP("mod", OP("+", V("r"), V("i")), I(m)),
                       OP("mod", V("n"), I(m)))],
                   V("i"),
                   [ASG("r", OP("+", V("r"), OP("mod", V("i"), I(k)))),
                    ASG("i", OP("div", V("i"), I(k)))])]
        ens = [OP("==", OP("mod", V("r"), I(m)), OP("mod", V("n"), I(m)))]
        return {"t": 1, "name": me, "gate": "loops",
                "params": [{"name": "n", "type": "int"}],
                "returns": [{"name": "r", "type": "int"}],
                "requires": [OP(">=", V("n"), I(0))],
                "ensures": ens, "body": body}
    # The Euclidean law itself is NOT a fuzz shape: a straight-line body has
    # no branch whose arms are both correct and different, and a no-op `if`
    # (measured 2026-09-08: 11 of 21 family tasks) gives a twin that
    # computes the same value and survives in every column. The law lives
    # in the committed task t/tasks/remainder.json, whose grounded ladder
    # finds a wrong-var twin.
    raise AssertionError("unreachable shape")


def f_v1exit(rng, idx):
    """SPEC.md "Early exit (v1)": search loops that return the moment they
    find what they are looking for, rather than threading a not-yet-found
    flag through the invariant to the end. Four shapes:
      first    - first index i in [0, len(s)) with s[i] op c, returning i
                 inside the loop and -1 after it (t/tasks/first_even.json's
                 shape, generalized over the comparison via `_pred`).
      exists   - exists an i with s[i] op c: true inside the loop, false
                 after it (one ensures clause, the quantifier itself).
      divisor  - first divisor of n in [2, n), returning it inside the loop
                 and -1 (n is prime) after it.
      sqrt     - first k with k*k >= n, returning inside the loop; the loop
                 always returns before its guard can go false, so the
                 statement after it is dead but still required (every path
                 to the end of the body assigns the return).
    Every shape's invariant tracks only "not found below i" (or "no k below
    i works" for sqrt): SPEC.md says a return owes the loop nothing at that
    exit, so the not-yet-found case is the only one the loop itself has to
    preserve, and the invariant is correspondingly one clause simpler than
    f_v1scan's threaded-flag search."""
    kind = rng.choice(["first", "exists", "divisor", "sqrt"])
    me = f"fz_v1exit_{idx:03d}"
    if kind in ("first", "exists"):
        extra = rng.random() < 0.5
        params = [{"name": "s", "type": "seq"}]
        names = []
        if extra:
            params.append({"name": "x", "type": "int"})
            names = ["x"]
        p_i, op, rhs = _pred(rng, AT("s", V("i")), names)
        p_j = OP(op, AT("s", V("j")), rhs)
        loop = WH(OP("<", V("i"), LEN("s")),
                  [AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("s"))),
                   FA("j", I(0), V("i"), _negate(p_j))],
                  OP("-", LEN("s"), V("i")),
                  [IFS(p_i,
                       [RET("r", V("i") if kind == "first" else BL(True))],
                       []),
                   ASG("i", OP("+", V("i"), I(1)))])
        body = [LOC("i", "int", I(0)), loop]
        if kind == "first":
            body.append(ASG("r", I(-1)))
            ens = [OP("or", OP("==", V("r"), I(-1)),
                      OP("and", OP(">=", V("r"), I(0)),
                         OP("<", V("r"), LEN("s")),
                         OP(op, AT("s", V("r")), rhs))),
                   OP("implies", OP("==", V("r"), I(-1)),
                      FA("i", I(0), LEN("s"),
                         _negate(OP(op, AT("s", V("i")), rhs)))),
                   OP("implies", OP("!=", V("r"), I(-1)),
                      FA("j", I(0), V("r"), _negate(p_j)))]
            ret_ty = "int"
        else:
            body.append(ASG("r", BL(False)))
            ens = [OP("==", V("r"), EX("i", I(0), LEN("s"), p_i))]
            ret_ty = "bool"
        return {"t": 1, "name": me, "gate": "loops",
                "params": params, "returns": [{"name": "r", "type": ret_ty}],
                "requires": [], "ensures": ens, "body": body}
    if kind == "divisor":
        body = [LOC("i", "int", I(2)),
                WH(OP("<", V("i"), V("n")),
                   [AND(OP(">=", V("i"), I(2)), OP("<=", V("i"), V("n"))),
                    FA("j", I(2), V("i"),
                       OP("!=", OP("mod", V("n"), V("j")), I(0)))],
                   OP("-", V("n"), V("i")),
                   [IFS(OP("==", OP("mod", V("n"), V("i")), I(0)),
                        [RET("r", V("i"))], []),
                    ASG("i", OP("+", V("i"), I(1)))]),
                ASG("r", I(-1))]
        ens = [OP("or", OP("==", V("r"), I(-1)),
                  OP("and", OP(">=", V("r"), I(2)), OP("<", V("r"), V("n")),
                     OP("==", OP("mod", V("n"), V("r")), I(0)))),
               OP("implies", OP("==", V("r"), I(-1)),
                  FA("j", I(2), V("n"),
                     OP("!=", OP("mod", V("n"), V("j")), I(0)))),
               OP("implies", OP("!=", V("r"), I(-1)),
                  FA("j", I(2), V("r"),
                     OP("!=", OP("mod", V("n"), V("j")), I(0))))]
        return {"t": 1, "name": me, "gate": "loops",
                "params": [{"name": "n", "type": "int"}],
                "returns": [{"name": "r", "type": "int"}],
                "requires": [OP(">=", V("n"), I(2))],
                "ensures": ens, "body": body}
    # sqrt: least k >= 0 with k*k >= n; the loop bound k <= n always finds
    # one (k = n suffices for n >= 1, k = 0 for n == 0), so the fallback
    # assign after the loop is unreachable but still required by
    # well-formedness: every path to the end of the body assigns `r`.
    body = [LOC("k", "int", I(0)),
            WH(OP("<=", V("k"), V("n")),
               [OP(">=", V("k"), I(0)),
                FA("j", I(0), V("k"),
                   OP("<", OP("*", V("j"), V("j")), V("n")))],
               OP("-", V("n"), V("k")),
               [IFS(OP(">=", OP("*", V("k"), V("k")), V("n")),
                    [RET("r", V("k"))], []),
                ASG("k", OP("+", V("k"), I(1)))]),
            ASG("r", V("k"))]
    ens = [OP("and", OP(">=", V("r"), I(0)),
              OP(">=", OP("*", V("r"), V("r")), V("n"))),
           FA("j", I(0), V("r"),
              OP("<", OP("*", V("j"), V("j")), V("n")))]
    return {"t": 1, "name": me, "gate": "loops",
            "params": [{"name": "n", "type": "int"}],
            "returns": [{"name": "r", "type": "int"}],
            "requires": [OP(">=", V("n"), I(0))],
            "ensures": ens, "body": body}


# --- 2026-09-09: SPEC.md "Sequences as values (v1)" -----------------------
#
# `update` (s[i := v]) and `fill` (seq(n, v)) are the two new v1 Expr forms;
# check_wf, interp.py and surface.py already accept both, and a `seq`
# return or local was accepted the same day. Six shapes, all correct by
# construction, all returning a `seq`:
#
#   swap      loop-free: swap positions i and j.
#   setpos    loop-free: set position i to a value.
#   reverse   loop: reverse into a `fill`ed seq.
#   fillcopy  loop: r := seq(len(s), 0), then copy s into r element by
#             element; ensures pins r == s (seq `==` is extensional).
#   clampneg  loop with an `if` inside: replace every negative element by
#             0, leave the rest.
#   idwrite   loop: r starts AS s and the loop writes each element back
#             UNCHANGED (s[i] into r[i := s[i]]); the twin therefore
#             computes the identical value (INVARIANT-DROP's own case, per
#             SPEC.md "The twins": "computes the same value by
#             construction"), so what has to carry the flip is the proof:
#             `ensures r == s` plus the surviving (bound-only) invariant
#             does not entail the dropped per-index equality, and
#             invariant_load_bearing below is exactly what checks that,
#             not the value.
#
# build_corpus's own twin selection (harness.make_twin, body-only) is the
# UNGROUNDED v1 rule: `if` -> COLLAPSE-IF, an invariant-carrying `while` ->
# INVARIANT-DROP, and NOTHING ELSE, unlike the full ladder harness.twin_for
# runs. So swap and setpos, both loop-free, each wrap their real update in
# an `if` whose OTHER arm is a genuine no-op (i == j; s[i] already == v):
# not filler, because COLLAPSE-IF keeps exactly that no-op branch and the
# real update is refutable against it wherever the guard was false. Every
# loop shape puts its value-pinning invariant FIRST, matching
# f_v1loop/f_v1scan's convention, because drop_first_invariant (the
# ungrounded rule's INVARIANT-DROP) always drops invariant 0 of the first
# invariant-carrying loop, and it is exactly that invariant whose absence
# must leave `ensures` unreachable from what remains.

def f_v1seqval(rng, idx):
    me = f"fz_v1seqval_{idx:03d}"
    shape = rng.choice(["swap", "setpos", "reverse", "fillcopy",
                        "clampneg", "idwrite"])

    if shape == "swap":
        order = rng.choice(["ij", "ji"])
        a, b = ("i", "j") if order == "ij" else ("j", "i")
        real = [LOC("tmp", "int", AT("s", V(a))),
                ASG("r", UPD("s", V(a), AT("s", V(b)))),
                ASG("r", UPD("r", V(b), V("tmp")))]
        body = [IFS(OP("==", V("i"), V("j")), [ASG("r", V("s"))], real)]
        ens = [OP("==", LEN("r"), LEN("s")),
               OP("==", AT("r", V("i")), AT("s", V("j"))),
               OP("==", AT("r", V("j")), AT("s", V("i"))),
               FA("k", I(0), LEN("s"),
                  OP("implies",
                     AND(OP("!=", V("k"), V("i")), OP("!=", V("k"), V("j"))),
                     OP("==", AT("r", V("k")), AT("s", V("k")))))]
        return {"t": 1, "name": me, "gate": "quantifiers",
                "params": [{"name": "s", "type": "seq"},
                          {"name": "i", "type": "int"},
                          {"name": "j", "type": "int"}],
                "returns": [{"name": "r", "type": "seq"}],
                "requires": [_range_req("i", LEN("s")),
                            _range_req("j", LEN("s"))],
                "ensures": ens, "body": body, "_shape": shape}

    if shape == "setpos":
        kind = rng.choice(["param", "add"])
        if kind == "param":
            params = [{"name": "s", "type": "seq"}, {"name": "i", "type": "int"},
                      {"name": "v", "type": "int"}]
            val = V("v")
        else:
            k = rng.choice([-5, -3, -2, -1, 1, 2, 3, 5])
            params = [{"name": "s", "type": "seq"}, {"name": "i", "type": "int"}]
            val = OP("+", AT("s", V("i")), I(k))
        body = [IFS(OP("==", AT("s", V("i")), val),
                    [ASG("r", V("s"))],
                    [ASG("r", UPD("s", V("i"), val))])]
        ens = [OP("==", LEN("r"), LEN("s")),
               OP("==", AT("r", V("i")), val),
               FA("k", I(0), LEN("s"),
                  OP("implies", OP("!=", V("k"), V("i")),
                     OP("==", AT("r", V("k")), AT("s", V("k")))))]
        return {"t": 1, "name": me, "gate": "quantifiers", "params": params,
                "returns": [{"name": "r", "type": "seq"}],
                "requires": [_range_req("i", LEN("s"))],
                "ensures": ens, "body": body, "_shape": shape}

    if shape == "reverse":
        c0 = rng.choice([0, -1, 3, 7])
        form = rng.choice(["a", "b"])

        def revidx(e):
            # Two syntactically distinct, semantically equal renderings of
            # len(s) - 1 - e, for corpus variety across draws.
            if form == "a":
                return OP("-", OP("-", LEN("s"), I(1)), e)
            return OP("-", OP("-", LEN("s"), e), I(1))

        body = [ASG("r", FILL(LEN("s"), I(c0))), LOC("i", "int", I(0)),
                WH_DF(OP("<", V("i"), LEN("s")),
                   [FA("k", I(0), V("i"),
                       OP("==", AT("r", V("k")), AT("s", revidx(V("k"))))),
                    OP("==", LEN("r"), LEN("s")),
                    AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("s")))],
                   OP("-", LEN("s"), V("i")),
                   [ASG("r", UPD("r", V("i"), AT("s", revidx(V("i"))))),
                    ASG("i", OP("+", V("i"), I(1)))])]
        ens = [OP("==", LEN("r"), LEN("s")),
               FA("k", I(0), LEN("s"),
                  OP("==", AT("r", V("k")), AT("s", revidx(V("k")))))]
        return {"t": 1, "name": me, "gate": "loops",
                "params": [{"name": "s", "type": "seq"}],
                "returns": [{"name": "r", "type": "seq"}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    if shape == "fillcopy":
        c0 = rng.choice([0, -1, 5, 9])
        body = [ASG("r", FILL(LEN("s"), I(c0))), LOC("i", "int", I(0)),
                WH_DF(OP("<", V("i"), LEN("s")),
                   [FA("k", I(0), V("i"),
                       OP("==", AT("r", V("k")), AT("s", V("k")))),
                    OP("==", LEN("r"), LEN("s")),
                    AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("s")))],
                   OP("-", LEN("s"), V("i")),
                   [ASG("r", UPD("r", V("i"), AT("s", V("i")))),
                    ASG("i", OP("+", V("i"), I(1)))])]
        ens = [OP("==", LEN("r"), LEN("s")), OP("==", V("r"), V("s"))]
        return {"t": 1, "name": me, "gate": "loops",
                "params": [{"name": "s", "type": "seq"}],
                "returns": [{"name": "r", "type": "seq"}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    if shape == "clampneg":
        c0 = rng.choice([0, -1, 9])
        body = [ASG("r", FILL(LEN("s"), I(c0))), LOC("i", "int", I(0)),
                WH_DF(OP("<", V("i"), LEN("s")),
                   [FA("k", I(0), V("i"),
                       OP("implies", OP("<", AT("s", V("k")), I(0)),
                          OP("==", AT("r", V("k")), I(0)))),
                    FA("k", I(0), V("i"),
                       OP("implies", OP(">=", AT("s", V("k")), I(0)),
                          OP("==", AT("r", V("k")), AT("s", V("k"))))),
                    OP("==", LEN("r"), LEN("s")),
                    AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("s")))],
                   OP("-", LEN("s"), V("i")),
                   [IFS(OP("<", AT("s", V("i")), I(0)),
                        [ASG("r", UPD("r", V("i"), I(0)))],
                        [ASG("r", UPD("r", V("i"), AT("s", V("i"))))]),
                    ASG("i", OP("+", V("i"), I(1)))])]
        ens = [OP("==", LEN("r"), LEN("s")),
               FA("k", I(0), LEN("s"),
                  OP("implies", OP("<", AT("s", V("k")), I(0)),
                     OP("==", AT("r", V("k")), I(0)))),
               FA("k", I(0), LEN("s"),
                  OP("implies", OP(">=", AT("s", V("k")), I(0)),
                     OP("==", AT("r", V("k")), AT("s", V("k")))))]
        return {"t": 1, "name": me, "gate": "loops",
                "params": [{"name": "s", "type": "seq"}],
                "returns": [{"name": "r", "type": "seq"}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    # idwrite: r starts AS s (not a fresh fill), and every iteration writes
    # s[i] back into r[i]: the real body is a true no-op, so the twin
    # (invariant-drop) computes the SAME value on every input, by
    # construction (SPEC.md "The twins"). `ensures r == s` plus the
    # surviving bound-only invariant is what has to make the dropped
    # per-index equality load-bearing, not any value difference. `eq_form`
    # is the same trick as reverse's `form`: two syntactically distinct,
    # semantically equal operand orders, so idwrite is not the one shape
    # in this family with zero entropy across draws.
    eq_form = rng.choice(["rs", "sr"])
    inv_eq = (OP("==", AT("r", V("k")), AT("s", V("k"))) if eq_form == "rs"
              else OP("==", AT("s", V("k")), AT("r", V("k"))))
    ens_eq = (OP("==", V("r"), V("s")) if eq_form == "rs"
              else OP("==", V("s"), V("r")))
    body = [ASG("r", V("s")), LOC("i", "int", I(0)),
            WH_DF(OP("<", V("i"), LEN("s")),
               [FA("k", I(0), V("i"), inv_eq),
                OP("==", LEN("r"), LEN("s")),
                AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("s")))],
               OP("-", LEN("s"), V("i")),
               [ASG("r", UPD("r", V("i"), AT("s", V("i")))),
                ASG("i", OP("+", V("i"), I(1)))])]
    ens = [OP("==", LEN("r"), LEN("s")), ens_eq]
    return {"t": 1, "name": me, "gate": "loops",
            "params": [{"name": "s", "type": "seq"}],
            "returns": [{"name": "r", "type": "seq"}],
            "requires": [], "ensures": ens, "body": body,
            "_shape": "idwrite"}


def f_wrong(rng, idx):
    """Category B: correct-by-construction, then ONE clause perturbed so the
    task is FALSE on a witness the interpreter finds. Every kernel must
    refute; a kernel that verifies has a lowering that proved something the
    task does not say."""
    base = rng.choice([f_v0if, f_v1loop, f_v1scan, f_v1rec])(rng, idx)
    new = f"fz_wrong_{idx:03d}"
    base = json.loads(json.dumps(base).replace(f'"{base["name"]}"',
                                               f'"{new}"'))
    base["name"] = new
    i = rng.randrange(len(base["ensures"]))
    e = base["ensures"][i]
    how = rng.choice(["off-by-one", "flip", "strengthen"])
    if how == "off-by-one" and "op" in e and e["op"] == "==":
        base["ensures"][i] = OP("==", e["args"][0],
                                OP("+", e["args"][1], I(1)))
    elif how == "flip" and "op" in e and e["op"] in NEGCMP:
        base["ensures"][i] = OP(NEGCMP[e["op"]], *e["args"])
    else:
        base["ensures"].append(OP(">", V(base["returns"][0]["name"]),
                                  I(10 ** 6))
                               if base["returns"][0]["type"] == "int"
                               else OP("==", V(base["returns"][0]["name"]),
                                       BL(True)))
    return base


FAMILIES = [
    ("v0if", f_v0if, 3),
    ("v0loose", f_v0loose, 1),
    ("v1bool", f_v1bool, 2),
    ("v1loop", f_v1loop, 3),
    ("v1scan", f_v1scan, 4),
    ("v1rec", f_v1rec, 3),
    ("v1def", f_v1def, 3),
    ("v1nest", f_v1nest, 1),
    ("v1divmod", f_v1divmod, 3),
    ("v1exit", f_v1exit, 3),
    ("v1seqval", f_v1seqval, 4),
    ("wrong", f_wrong, 3),
]


# ===========================================================================
# 5. Hand-built probes. Each one names the SPEC.md sentence it tests; these
#    are NOT random, and the undefined/vacuous ones are deliberately outside
#    the well-formed corpus (marked `adversarial`).
# ===========================================================================

def probes() -> list[dict]:
    P = []

    def add(task, expect, why, adversarial=False):
        task["_expect"] = expect
        task["_why"] = why
        task["_adversarial"] = adversarial
        P.append(task)

    # --- "Integer semantics in both versions: mathematical integers,
    # unbounded, no overflow." A backend whose lowering uses a machine type
    # for a t int turns a FALSE task into a proof.
    add({"t": 0, "name": "fz_p_bigneg",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP(">=", V("r"), I(0))],
         "body": [IFS(OP(">", V("x"), I(2 ** 31 - 1)),
                      [ASG("r", I(-1))], [ASG("r", I(0))])]},
        "refuted",
        "x = 2^31 gives r = -1; only a backend whose t int is 32-bit can "
        "verify this")
    add({"t": 0, "name": "fz_p_bigwide",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [OP(">=", V("x"), I(-2 * 10 ** 9)),
                      OP("<=", V("x"), I(2 * 10 ** 9))],
         "ensures": [OP("implies", OP(">=", V("x"), I(0)),
                        OP("==", V("r"),
                           OP("+", OP("+", V("x"), V("x")), V("x")))),
                     OP("implies", OP("<", V("x"), I(0)),
                        OP("==", V("r"), I(0)))],
         "body": [IFS(OP(">=", V("x"), I(0)),
                      [ASG("r", OP("+", OP("+", V("x"), V("x")), V("x")))],
                      [ASG("r", I(0))])]},
        "verified",
        "3x reaches 6e9; a 32-bit return type cannot hold it, and the ensures "
        "then has no model")
    add({"t": 1, "name": "fz_p_biglen", "gate": "quantifiers",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP("<=", LEN("s"), I(2 ** 31 - 1))],
         "body": [IFS(OP(">=", LEN("s"), I(0)),
                      [ASG("r", I(0))], [ASG("r", I(1))])]},
        "refuted",
        "SPEC.md gives seq a length that is only >= 0; a backend that bounds "
        "it by a machine type proves a false statement")

    # The three above all put the machine-representability question inside a
    # branch, which WP's smoke test then reports as unreachable (VACUOUS),
    # a refusal, not a false proof. These three keep BOTH branches reachable
    # in every backend, so a backend whose t int is a machine type reaches
    # VERIFIED on a task the interpreter refutes, and the flip rule counts it.
    add({"t": 0, "name": "fz_p_intwidth",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP("implies", OP(">=", V("x"), I(0)),
                        OP("==", V("r"), V("x"))),
                     OP("implies", OP("<", V("x"), I(0)),
                        OP("==", V("r"), I(0))),
                     OP("<=", V("r"), I(2 ** 31 - 1))],
         "body": [IFS(OP(">=", V("x"), I(0)),
                      [ASG("r", V("x"))], [ASG("r", I(0))])]},
        "refuted",
        "x = 2^31 makes r = 2^31 > 2^31-1; verifying it means the lowering "
        "constrained a t int to a machine range")
    add({"t": 1, "name": "fz_p_seqlen", "gate": "quantifiers",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP("implies", OP(">", LEN("s"), I(0)),
                        OP("==", V("r"), I(1))),
                     OP("implies", OP("==", LEN("s"), I(0)),
                        OP("==", V("r"), I(0))),
                     OP("<=", LEN("s"), I(2 ** 31 - 1))],
         "body": [IFS(OP(">", LEN("s"), I(0)),
                      [ASG("r", I(1))], [ASG("r", I(0))])]},
        "refuted",
        "SPEC.md gives len(s) no upper bound; verifying it means the lowering "
        "bounded the sequence length by a machine type")
    # A seq's ELEMENTS are mathematical integers too, and no probe reached
    # them until 2026-09-01: lower_framac.py's `int *s` made every element
    # is_sint32 under WP's default model, and this task proved 10/10 goals
    # there, VERIFIED with its twin REFUTED, so the flip rule would have
    # COUNTED a false theorem. The length probe above does not cover it: a
    # lowering can bound the elements while leaving the length free.
    add({"t": 1, "name": "fz_p_elemwidth", "gate": "quantifiers",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP("implies", OP(">", LEN("s"), I(0)),
                        OP("==", V("r"), I(1))),
                     OP("implies", OP("==", LEN("s"), I(0)),
                        OP("==", V("r"), I(0))),
                     OP("implies", OP(">", LEN("s"), I(0)),
                        OP("<=", AT("s", I(0)), I(2 ** 31 - 1)))],
         "body": [IFS(OP(">", LEN("s"), I(0)),
                      [ASG("r", I(1))], [ASG("r", I(0))])]},
        "refuted",
        "SPEC.md's seq elements are mathematical integers; verifying it "
        "means the lowering stored them in a machine type")
    add({"t": 1, "name": "fz_p_attotal", "gate": "quantifiers",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP("implies", OP(">", LEN("s"), I(0)),
                        OP("==", V("r"), I(1))),
                     OP("implies", OP("==", LEN("s"), I(0)),
                        OP("==", V("r"), I(0))),
                     OP("==", AT("s", LEN("s")), AT("s", LEN("s")))],
         "body": [IFS(OP(">", LEN("s"), I(0)),
                      [ASG("r", I(1))], [ASG("r", I(0))])]},
        "refuted",
        "s[len(s)] has no value, so the third clause has none either; e == e "
        "is provable under any totalization", adversarial=True)
    add({"t": 1, "name": "fz_p_bigrange", "gate": "quantifiers",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP("implies", OP(">", LEN("s"), I(0)),
                        OP("==", V("r"), I(1))),
                     OP("implies", OP("==", LEN("s"), I(0)),
                        OP("==", V("r"), I(0))),
                     FA("i", I(0), I(3 * 10 ** 9),
                        OP("implies", OP("<", V("i"), LEN("s")),
                           OP("==", AT("s", V("i")), AT("s", V("i")))))],
         "body": [IFS(OP(">", LEN("s"), I(0)),
                      [ASG("r", I(1))], [ASG("r", I(0))])]},
        "verified",
        "a quantifier range wider than a machine int; SPEC.md's bounded "
        "quantifier is over mathematical integers")

    # --- "the AST operator is the word div" (surface.py's own REFUSALS
    # entry, and SPEC.md's notation section): `/` and `%` are surface
    # NOTATION for the JSON ops `div` and `mod`, never JSON op names
    # themselves. Before 2026-09-08 this probe measured "no lowering may
    # accept division at all"; div and mod exist now, so what is left to
    # measure is narrower but still real: the literal slash token is not,
    # and never was, a t operator, so every lowering must still reject it
    # rather than mistake it for `div`.
    add({"t": 0, "name": "fz_p_nodiv",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP("==", V("r"), {"op": "/", "args": [V("x"), I(2)]})],
         "body": [IFS(OP(">=", V("x"), I(0)),
                      [ASG("r", {"op": "/", "args": [V("x"), I(2)]})],
                      [ASG("r", I(0))])]},
        "lower-error",
        "`/` (the bare slash) is not a t operator, `div` is; every lowering "
        "must reject the token rather than treat it as division",
        adversarial=True)

    # --- SPEC.md "Division and modulo (v1)" and "Undefined requires
    # (normative)", together: y == 0 is undefined exactly as `at` outside
    # [0, len) is, and a `requires` undefined at every type-correct input is
    # DEFECTIVE, so a lowering able to detect it must surface the defect
    # rather than verify.
    add({"t": 1, "name": "fz_p_divreq0",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [OP("==", OP("div", V("x"), I(0)), I(0))],
         "ensures": [OP("==", V("r"), I(0))],
         "body": [ASG("r", I(0))]},
        "refuted",
        "`x / 0` has no value at any x, so `requires x / 0 == 0` is "
        "undefined at every type-correct input, not merely narrowed; the "
        "task is DEFECTIVE and the real lowering must not VERIFY, exactly "
        "as the analogous `at` probe SPEC.md records under 'Undefined "
        "requires'", adversarial=True)

    # --- SPEC.md "At y == 0 both are undefined": `y - y` is well-defined
    # (it is 0), but dividing by it is not, so this body has no value at any
    # input reachable from `requires`, without a literal 0 in sight. A
    # lowering that only pattern-matches a literal zero divisor and misses
    # this one silently totalizes.
    add({"t": 1, "name": "fz_p_divzero_expr",
         "params": [{"name": "x", "type": "int"}, {"name": "y", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP("==", V("r"), I(0))],
         "body": [ASG("r", OP("div", V("x"), OP("-", V("y"), V("y"))))]},
        "refuted",
        "`y - y` is always 0, so `x / (y - y)` is undefined at every input; "
        "a lowering that discharges div's definedness obligation must "
        "refute rather than totalize it", adversarial=True)

    # --- The column-semantics probe (SPEC.md "Why Euclidean"): 0 <= x mod y
    # < |y| holds for every nonzero y regardless of x's sign, so x % y >= 0
    # even at x < 0. A lowering that emits its kernel's native truncating
    # `%` (sign follows the dividend) instead of redefining it as Euclidean
    # fails this one at x < 0, y > 0 specifically.
    add({"t": 1, "name": "fz_p_modsign_true",
         "params": [{"name": "x", "type": "int"}, {"name": "y", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [OP("<", V("x"), I(0)), OP(">", V("y"), I(0))],
         "ensures": [OP(">=", OP("mod", V("x"), V("y")), I(0))],
         "body": [ASG("r", OP("mod", V("x"), V("y")))]},
        "verified",
        "x % y >= 0 at every input requires admits, by SPEC.md's Euclidean "
        "law; a column whose lowering falls back to a truncating native "
        "`%` for negative x is not measuring this semantics")
    add({"t": 1, "name": "fz_p_modsign_false",
         "params": [{"name": "x", "type": "int"}, {"name": "y", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [OP("<", V("x"), I(0)), OP(">", V("y"), I(0))],
         "ensures": [OP("<", OP("mod", V("x"), V("y")), I(0))],
         "body": [ASG("r", OP("mod", V("x"), V("y")))]},
        "refuted",
        "the mirror of fz_p_modsign_true: x % y < 0 is false under "
        "Euclidean semantics at every input the requires admits, so no "
        "lowering that implements SPEC.md's div/mod may verify it")

    # --- The wave law: an unsatisfiable hypothesis discharges an obligation
    # that proves nothing. Only a KERNEL-NATIVE vacuity instrument sees it.
    add({"t": 0, "name": "fz_p_vac_unsat",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [OP("==", I(1), I(0))],
         "ensures": [OP("==", V("r"), I(5))],
         "body": [IFS(OP(">=", V("x"), I(0)),
                      [ASG("r", I(0))], [ASG("r", I(1))])]},
        "vacuous", "requires 1 == 0", adversarial=True)
    add({"t": 0, "name": "fz_p_vac_range",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [OP(">", V("x"), I(0)), OP("<", V("x"), I(0))],
         "ensures": [OP("==", V("r"), I(5))],
         "body": [IFS(OP(">=", V("x"), I(0)),
                      [ASG("r", I(0))], [ASG("r", I(1))])]},
        "vacuous", "requires x > 0 and x < 0", adversarial=True)
    add({"t": 1, "name": "fz_p_vac_post", "gate": "quantifiers",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [BL(True)],
         "body": [IFS(OP(">=", V("x"), I(0)),
                      [ASG("r", I(0))], [ASG("r", I(1))])]},
        "vacuous", "content-free postcondition", adversarial=True)

    # --- "a lowering that silently totalizes `at` is wrong."
    add({"t": 1, "name": "fz_p_at_oob", "gate": "quantifiers",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP("==", AT("s", LEN("s")), AT("s", LEN("s")))],
         "body": [IFS(OP(">=", LEN("s"), I(0)),
                      [ASG("r", I(0))], [ASG("r", I(1))])]},
        "refuted",
        "s[len(s)] has no value; e == e is true under ANY totalization, so a "
        "kernel that verifies this totalized `at`", adversarial=True)
    add({"t": 1, "name": "fz_p_at_neg", "gate": "quantifiers",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP("==", AT("s", I(-1)), AT("s", I(-1)))],
         "body": [IFS(OP(">=", LEN("s"), I(0)),
                      [ASG("r", I(0))], [ASG("r", I(1))])]},
        "refuted", "s[-1] has no value", adversarial=True)
    add({"t": 1, "name": "fz_p_at_zero", "gate": "quantifiers",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP("==", AT("s", LEN("s")), I(0))],
         "body": [IFS(OP(">=", LEN("s"), I(0)),
                      [ASG("r", I(0))], [ASG("r", I(1))])]},
        "refuted",
        "a kernel that verifies this totalized `at` to a DEFAULT value",
        adversarial=True)
    add({"t": 1, "name": "fz_p_at_body", "gate": "quantifiers",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP(">=", V("r"), I(0)), OP("<=", V("r"), I(0))],
         "body": [IFS(OP(">=", LEN("s"), I(0)),
                      [ASG("r", OP("-", AT("s", LEN("s")),
                                   AT("s", LEN("s"))))],
                      [ASG("r", I(0))])]},
        "refuted", "unguarded `at` in executable position", adversarial=True)

    # --- "well-definedness IS the termination obligation" (SPEC.md gate 3).
    add({"t": 1, "name": "fz_p_badrec", "gate": "recursion",
         "params": [{"name": "n", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [OP(">=", V("n"), I(0))],
         "ensures": [OP("==", V("r"), CALL("g", V("n")))],
         "spec_funs": [{"name": "g", "params": [{"name": "n", "type": "int"}],
                        "result": "int", "decreases": I(0),
                        "body": OP("+", CALL("g", V("n")), I(1))}],
         "body": [IFS(OP(">=", V("n"), I(0)),
                      [ASG("r", I(0))], [ASG("r", I(1))])]},
        "refuted",
        "g(n) = g(n)+1 with decreases 0 has no solution; a kernel that "
        "verifies accepted a non-well-founded logic function",
        adversarial=True)
    add({"t": 1, "name": "fz_p_badrec2", "gate": "recursion",
         "params": [{"name": "n", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [OP(">=", V("n"), I(0))],
         "ensures": [OP("==", V("r"), CALL("g", V("n")))],
         "spec_funs": [{"name": "g", "params": [{"name": "n", "type": "int"}],
                        "result": "int", "decreases": V("n"),
                        "body": ITE(OP("<=", V("n"), I(0)), I(0),
                                    CALL("g", OP("+", V("n"), I(1))))}],
         "body": [IFS(OP("<=", V("n"), I(0)),
                      [ASG("r", I(0))], [ASG("r", I(0))])]},
        "refuted",
        "the self-call increases the measure; the termination obligation must "
        "fail", adversarial=True)

    # --- SPEC.md loop rule: "decreases ... is >= 0 whenever the guard holds".
    add({"t": 1, "name": "fz_p_badvariant", "gate": "loops",
         "params": [{"name": "n", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [OP(">=", V("n"), I(0))],
         "ensures": [OP("==", V("r"), V("n"))],
         "body": [ASG("r", I(0)), LOC("i", "int", I(0)),
                  WH(OP("<", V("i"), V("n")),
                     [OP("==", V("r"), V("i")),
                      AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), V("n")))],
                     I(0),
                     [ASG("r", OP("+", V("r"), I(1))),
                      ASG("i", OP("+", V("i"), I(1)))])]},
        "refuted", "decreases 0 never strictly decreases", adversarial=True)

    # --- SPEC.md "Early exit (v1)": `return` evaluates Expr, assigns it to
    # the return variable, and ends the task; inside a loop it leaves
    # without owing the loop's invariant, only the ensures.
    add({"t": 1, "name": "fz_p_ret_first", "gate": "loops",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP("or", OP("==", V("r"), I(-1)),
                        OP("and", OP(">=", V("r"), I(0)),
                           OP("<", V("r"), LEN("s")),
                           OP("<", AT("s", V("r")), I(0)))),
                     OP("implies", OP("==", V("r"), I(-1)),
                        FA("i", I(0), LEN("s"),
                           OP(">=", AT("s", V("i")), I(0)))),
                     OP("implies", OP("!=", V("r"), I(-1)),
                        FA("j", I(0), V("r"),
                           OP(">=", AT("s", V("j")), I(0))))],
         "body": [LOC("i", "int", I(0)),
                  WH(OP("<", V("i"), LEN("s")),
                     [AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("s"))),
                      FA("j", I(0), V("i"), OP(">=", AT("s", V("j")), I(0)))],
                     OP("-", LEN("s"), V("i")),
                     [IFS(OP("<", AT("s", V("i")), I(0)),
                          [RET("r", V("i"))], []),
                      ASG("i", OP("+", V("i"), I(1)))]),
                  ASG("r", I(-1))]},
        "verified",
        "first negative index, returned from inside the loop: the return "
        "owes the ensures at that exit, not the loop invariant, and both "
        "the return and the natural exit (r = -1) satisfy it")
    add({"t": 1, "name": "fz_p_ret_unreachable",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP("==", V("r"), V("x"))],
         "body": [RET("r", V("x")), ASG("r", I(0))]},
        "wf-refused",
        "a statement follows a return in the same block; SPEC.md says no "
        "statement of its own block may follow it, and check_wf refuses",
        adversarial=True)
    add({"t": 1, "name": "fz_p_ret_falsens", "gate": "loops",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP("implies", OP("!=", V("r"), I(-1)),
                        OP(">", AT("s", V("r")), I(0)))],
         "body": [LOC("i", "int", I(0)),
                  WH(OP("<", V("i"), LEN("s")),
                     [AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("s"))),
                      FA("j", I(0), V("i"), OP(">=", AT("s", V("j")), I(0)))],
                     OP("-", LEN("s"), V("i")),
                     [IFS(OP("<", AT("s", V("i")), I(0)),
                          [RET("r", V("i"))], []),
                      ASG("i", OP("+", V("i"), I(1)))]),
                  ASG("r", I(-1))]},
        "refuted",
        "the body returns the first NEGATIVE index, but the ensures claims "
        "the found element is positive: false at the return, the obligation "
        "SPEC.md says a return owes there", adversarial=True)
    add({"t": 1, "name": "fz_p_ret_bothbranches",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}], "requires": [],
         "ensures": [OP(">=", V("r"), I(0)),
                     OP("or", OP("==", V("r"), V("x")),
                        OP("==", V("r"), OP("neg", V("x"))))],
         "body": [IFS(OP(">=", V("x"), I(0)),
                      [RET("r", V("x"))],
                      [RET("r", OP("neg", V("x")))])]},
        "verified",
        "a return in both arms of an if, nothing after it: well-formed "
        "(each arm's return is the last statement of its own block), and "
        "each arm owes the ensures at its own return")

    # --- SPEC.md "Sequences as values (v1)", 2026-09-09: `update` inside a
    # loop, correctly bounded and correctly specified.
    add({"t": 1, "name": "fz_p_upd_first", "gate": "loops",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "seq"}], "requires": [],
         "ensures": [OP("==", LEN("r"), LEN("s")),
                     FA("k", I(0), LEN("s"),
                        OP("==", AT("r", V("k")),
                           OP("+", AT("s", V("k")), I(1))))],
         "body": [ASG("r", V("s")), LOC("i", "int", I(0)),
                  WH_DF(OP("<", V("i"), LEN("s")),
                     [FA("k", I(0), V("i"),
                         OP("==", AT("r", V("k")),
                            OP("+", AT("s", V("k")), I(1)))),
                      OP("==", LEN("r"), LEN("s")),
                      AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("s")))],
                     OP("-", LEN("s"), V("i")),
                     [ASG("r", UPD("r", V("i"), OP("+", AT("s", V("i")), I(1)))),
                      ASG("i", OP("+", V("i"), I(1)))])]},
        "verified",
        "update inside a loop, r[k] == s[k] + 1 everywhere: the invariant "
        "matches the body exactly, so a faithful lowering of `update` "
        "verifies it")

    # --- "a lowering that silently totalizes at is wrong" (SPEC.md
    # Definedness), now for `update`: s[i := v] is DEFINED IFF 0 <= i <
    # len(s), and index len(s) is out of range at every length, empty
    # included, with no `requires` guarding it.
    add({"t": 1, "name": "fz_p_upd_oob", "gate": "quantifiers",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "seq"}], "requires": [],
         "ensures": [OP("==", LEN("r"), LEN("s"))],
         "body": [ASG("r", UPD("s", LEN("s"), I(0)))]},
        "refuted",
        "s[len(s) := 0] has no value at any length, unguarded by any "
        "requires; ground_truth's kind is undefined-body, which the "
        "verdict rule reports as refuted, the file's convention for an "
        "ill-defined real body, exactly as fz_p_at_oob's totalized `at` "
        "reads refuted rather than a distinct outcome",
        adversarial=True)

    # --- SPEC.md "fill ... DEFINED IFF n >= 0", and "Undefined requires
    # (normative)": a requires clause that fails to exclude n < 0 is not a
    # domain restriction, it lets an undefined `fill` through.
    add({"t": 1, "name": "fz_p_fill_neg", "gate": "quantifiers",
         "params": [{"name": "n", "type": "int"}],
         "returns": [{"name": "r", "type": "seq"}],
         "requires": [OP("<=", V("n"), I(100))],
         "ensures": [OP("==", LEN("r"), V("n"))],
         "body": [ASG("r", FILL(V("n"), I(0)))]},
        "refuted",
        "requires n <= 100 admits n = -1; seq(-1, 0) has no value, so the "
        "real body is undefined at an input the requires lets through, "
        "reported refuted for the same reason fz_p_upd_oob is",
        adversarial=True)

    # --- seq `==` is extensional (SPEC.md "Sequences as values"): a true
    # and a false instance of the same `ensures r == s` shape, the body
    # the only thing that differs.
    add({"t": 1, "name": "fz_p_seqeq_true", "gate": "loops",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "seq"}], "requires": [],
         "ensures": [OP("==", LEN("r"), LEN("s")), OP("==", V("r"), V("s"))],
         "body": [ASG("r", FILL(LEN("s"), I(0))), LOC("i", "int", I(0)),
                  WH_DF(OP("<", V("i"), LEN("s")),
                     [FA("k", I(0), V("i"),
                         OP("==", AT("r", V("k")), AT("s", V("k")))),
                      OP("==", LEN("r"), LEN("s")),
                      AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("s")))],
                     OP("-", LEN("s"), V("i")),
                     [ASG("r", UPD("r", V("i"), AT("s", V("i")))),
                      ASG("i", OP("+", V("i"), I(1)))])]},
        "verified",
        "r is s copied through update, index by index: r == s holds "
        "extensionally, and a lowering with a faithful seq equality "
        "verifies it")
    add({"t": 1, "name": "fz_p_seqeq_false", "gate": "loops",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "seq"}], "requires": [],
         "ensures": [OP("==", LEN("r"), LEN("s")), OP("==", V("r"), V("s"))],
         "body": [ASG("r", FILL(LEN("s"), I(0))), LOC("i", "int", I(0)),
                  WH_DF(OP("<", V("i"), LEN("s")),
                     [FA("k", I(0), V("i"),
                         OP("==", AT("r", V("k")),
                            OP("+", AT("s", V("k")), I(1)))),
                      OP("==", LEN("r"), LEN("s")),
                      AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("s")))],
                     OP("-", LEN("s"), V("i")),
                     [ASG("r", UPD("r", V("i"), OP("+", AT("s", V("i")), I(1)))),
                      ASG("i", OP("+", V("i"), I(1)))])]},
        "refuted",
        "the mirror of fz_p_seqeq_true: every element is off by one, so r "
        "== s is false at every non-empty s, the witness ground_truth "
        "finds on the first sampled non-empty input")

    # --- SPEC.md "Early exit (v1)" meets "Sequences as values": the
    # returned value is itself an `update`, not a name read back.
    add({"t": 1, "name": "fz_p_upd_ret",
         "params": [{"name": "s", "type": "seq"}, {"name": "i", "type": "int"},
                    {"name": "v", "type": "int"}],
         "returns": [{"name": "r", "type": "seq"}],
         "requires": [_range_req("i", LEN("s"))],
         "ensures": [OP("==", LEN("r"), LEN("s")),
                     OP("==", AT("r", V("i")), V("v")),
                     FA("k", I(0), LEN("s"),
                        OP("implies", OP("!=", V("k"), V("i")),
                           OP("==", AT("r", V("k")), AT("s", V("k")))))],
         "body": [RET("r", UPD("s", V("i"), V("v")))]},
        "verified",
        "the return statement's Expr is `update` itself, SPEC.md Early "
        "exit's position for it is the same as an assignment's "
        "right-hand side, and the update is in bounds by requires")
    return P


# ===========================================================================
# 6. Corpus construction.
# ===========================================================================

def build_corpus(n: int, seed: int):
    rng = random.Random(seed)
    weights = []
    for fam, fn, w in FAMILIES:
        weights += [(fam, fn)] * w
    corpus, idx, tries = [], 0, 0
    seen = set()
    while len(corpus) < n and tries < n * 40:
        tries += 1
        fam, fn = rng.choice(weights)
        idx += 1
        try:
            task = fn(rng, idx)
        except Exception:                                    # noqa: BLE001
            continue
        errs = check_wf(task)
        if errs:
            task["_wf_errors"] = errs
            corpus.append(task)                # a generator bug is a finding
            continue
        key = json.dumps({k: v for k, v in task.items() if k != "name"},
                         sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        twin, op = harness.make_twin(task["body"])
        if twin is None:
            continue                           # no twin: SPEC.md refuses it
        task["_family"] = fam
        task["_twin_op"] = op
        gt = ground_truth(task, task["body"], rng)
        if gt["verdict"] == "unknown":
            continue
        if gt["kind"] in ("invariant", "decreases", "undefined-body",
                          "undefined-ensures"):
            # A generated ANNOTATION or definedness bug, not a spec finding:
            # every kernel would refute for the same reason and the task would
            # teach nothing about the lowerings. Only keep the ones aimed at
            # the spec.
            if fam != "wrong":
                continue
        task["_expect"] = gt["verdict"]
        task["_gt"] = {k: gt[k] for k in ("kind", "cex", "n_ok")
                       if gt.get(k) is not None}
        task["_twin_differs"] = (twin_semantics(task, task["body"], twin, rng)
                                 if op == "collapse-if" else None)
        task["_inv"] = (invariant_load_bearing(task, rng)
                        if op == "invariant-drop" else {"applies": False})
        corpus.append(task)
    for p in probes():
        p["_family"] = "probe"
        p["_wf_errors"] = check_wf(p) if p["name"] != "fz_p_nodiv" else []
        twin, op = harness.make_twin(p["body"])
        p["_twin_op"] = op
        corpus.append(p)
    return corpus


# ===========================================================================
# 7. Driver: own out/ directory, lowering in the parent, verify in a pool.
# ===========================================================================

def _cell(bname: str, real: str, twin: str, n: int):
    backend = importlib.import_module(f"verifiers.{bname}")
    rp, tp = Path(real), Path(twin)
    if n == 1:
        a, b = backend.verify(rp), backend.verify(tp)
        return bname, rp.stem, a.outcome, b.outcome, True, a.wall_ms + b.wall_ms
    a, ok1 = flake_check(backend.verify, rp, n)
    b, ok2 = flake_check(backend.verify, tp, n)
    return bname, rp.stem, a.outcome, b.outcome, ok1 and ok2, a.wall_ms + b.wall_ms


def run(corpus, outdir: Path, jobs: int, n_flake: int, only=None):
    outdir.mkdir(parents=True, exist_ok=True)
    present, cols = [], []
    for bname, lmod, sfx in BACKENDS:
        if only and bname not in only:
            continue
        try:
            be = importlib.import_module(f"verifiers.{bname}")
            cols.append((bname, be.version()))
            present.append((bname, importlib.import_module(lmod).lower, sfx))
        except (Exception, SystemExit) as e:                 # noqa: BLE001
            cols.append((bname, f"ABSENT: {e}"))
    rows = {t["name"]: {} for t in corpus}
    pending = []
    for bname, lower, sfx in present:
        for task in corpus:
            name = task["name"]
            if task.get("_wf_errors"):
                rows[name][bname] = ("wf-error", "wf-error", True, 0)
                continue
            twin_body, op = harness.make_twin(task["body"])
            if twin_body is None:
                rows[name][bname] = ("no-twin", "no-twin", True, 0)
                continue
            clean = {k: v for k, v in task.items() if not k.startswith("_")}
            try:
                rs = lower(clean, task["body"])
                ts = lower(clean, twin_body)
            except NotImplementedError as e:
                rows[name][bname] = ("abstain", str(e)[:120], True, 0)
                continue
            except Exception as e:                           # noqa: BLE001
                rows[name][bname] = ("lower-error",
                                     f"{type(e).__name__}: {e}"[:120], True, 0)
                continue
            rp = outdir / f"{name}.{sfx}"
            tp = outdir / f"{name}_twin.{sfx}"
            rp.write_text(rs, encoding="utf-8")
            tp.write_text(ts, encoding="utf-8")
            pending.append((bname, str(rp), str(tp)))
    t0 = time.time()
    ctx = mp_context()
    done = 0
    with ProcessPoolExecutor(max_workers=jobs, mp_context=ctx) as ex:
        futs = [ex.submit(_cell, b, r, t, n_flake) for b, r, t in pending]
        for fut in as_completed(futs):
            bname, stem, ro, to, agreed, ms = fut.result()
            rows[stem][bname] = (ro, to, agreed, ms)
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(pending)} cells, "
                      f"{time.time() - t0:.0f}s", flush=True)
    return rows, cols


def analyse(corpus, rows):
    """A cell is a finding when it contradicts another kernel on the same real
    lowering, or contradicts the reference interpreter."""
    out = {"disagreements": [], "twin_survived": [], "vs_truth": [],
           "no_flip": []}
    for task in corpus:
        name = task["name"]
        cells = rows.get(name, {})
        real = {b: c[0] for b, c in cells.items()
                if c[0] in (Outcome.VERIFIED, Outcome.REFUTED,
                            Outcome.VACUOUS, Outcome.TIMEOUT,
                            Outcome.MALFORMED)}
        ver = sorted(b for b, o in real.items() if o == Outcome.VERIFIED)
        ref = sorted(b for b, o in real.items() if o == Outcome.REFUTED)
        if ver and ref:
            out["disagreements"].append(
                {"task": name, "family": task.get("_family"),
                 "verified": ver, "refuted": ref,
                 "expected": task.get("_expect"),
                 "why": task.get("_why"), "gt": task.get("_gt"),
                 "adversarial": task.get("_adversarial", False)})
        exp = task.get("_expect")
        if exp in ("verified", "refuted"):
            wrong = sorted(b for b, o in real.items()
                           if o != exp and o in (Outcome.VERIFIED,
                                                 Outcome.REFUTED))
            if wrong:
                out["vs_truth"].append(
                    {"task": name, "family": task.get("_family"),
                     "expected": exp, "disagreeing": {b: real[b]
                                                      for b in wrong},
                     "why": task.get("_why"), "gt": task.get("_gt"),
                     "adversarial": task.get("_adversarial", False)})
        surv = sorted(b for b, c in cells.items()
                      if c[0] == Outcome.VERIFIED and c[1] == Outcome.VERIFIED)
        if surv:
            out["twin_survived"].append(
                {"task": name, "family": task.get("_family"),
                 "op": task.get("_twin_op"), "backends": surv,
                 "twin_differs": task.get("_twin_differs"),
                 "inv": task.get("_inv")})
        # THE FLIP, counted. A twin that comes back TIMEOUT or UNPROVED is
        # neither a disagreement (nothing contradicts it) nor a survivor (it
        # did not verify), so until 2026-09-01 it was reported as NOTHING,
        # and a kernel that had stopped refuting altogether read as a clean
        # run. MEASURED that day: spark went from 101/110 flips to 0/359
        # across three fresh seeds while `disagreements` stayed at 4. The
        # twin's whole purpose is the flip, so a real VERIFIED whose twin is
        # not REFUTED is recorded here, with the outcome that replaced it.
        for b, c in cells.items():
            if c[0] == Outcome.VERIFIED and c[1] != Outcome.REFUTED:
                out["no_flip"].append(
                    {"task": name, "family": task.get("_family"),
                     "op": task.get("_twin_op"), "backend": b,
                     "twin_outcome": c[1]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True,
                    help="output directory; NEVER t/out/, the suite owns it")
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 8) // 2))
    ap.add_argument("--flake", type=int, default=1)
    ap.add_argument("--only", default="")
    ap.add_argument("--tasks", default="", help="comma-separated task names")
    ap.add_argument("--corpus-json", default="")
    args = ap.parse_args()
    outdir = Path(args.out).resolve()
    if outdir == (HERE / "out").resolve():
        print("REFUSED: t/out/ belongs to run_all.py/run_par.py.")
        return 2
    if args.corpus_json and Path(args.corpus_json).exists():
        corpus = json.loads(Path(args.corpus_json).read_text())
    else:
        corpus = build_corpus(args.n, args.seed)
        if args.corpus_json:
            Path(args.corpus_json).write_text(json.dumps(corpus, indent=1))
    if args.tasks:
        want = set(args.tasks.split(","))
        corpus = [t for t in corpus if t["name"] in want]
    only = set(args.only.split(",")) if args.only else None
    print(f"corpus: {len(corpus)} tasks "
          f"({sum(1 for t in corpus if t.get('_wf_errors'))} with wf errors)")
    rows, cols = run(corpus, outdir, args.jobs, args.flake, only)
    res = analyse(corpus, rows)
    (outdir / "rows.json").write_text(json.dumps(rows, indent=1))
    (outdir / "findings.json").write_text(json.dumps(res, indent=1))
    (outdir / "corpus.json").write_text(json.dumps(corpus, indent=1))
    nf = {}
    for d in res["no_flip"]:
        nf.setdefault(d["backend"], []).append(d["twin_outcome"])
    print(f"\ndisagreements: {len(res['disagreements'])}  "
          f"vs-truth: {len(res['vs_truth'])}  "
          f"twin-survived: {len(res['twin_survived'])}  "
          f"no-flip: {len(res['no_flip'])}")
    for b in sorted(nf):
        c = {o: nf[b].count(o) for o in sorted(set(nf[b]))}
        print(f"  NO-FLIP {b}: {len(nf[b])} real-VERIFIED cells whose twin "
              f"was not REFUTED: {c}")
    for d in res["disagreements"]:
        print(f"  DISAGREE {d['task']} [{d['family']}] "
              f"verified={d['verified']} refuted={d['refuted']} "
              f"expected={d['expected']}")
    for d in res["vs_truth"]:
        print(f"  VS-TRUTH {d['task']} [{d['family']}] expected={d['expected']}"
              f" got={d['disagreeing']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
