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

THE STRING LIBRARY (v1, since 2026-09-11): 17 members (split, join, tostr,
count, find, strip, lstrip, rstrip, replace, lower, upper, isdigit, isalpha,
isupper, islower, startswith, endswith), per SPEC.md "The string library
(v1)". `check_wf`'s `_ty` types each from SPEC.md's table (split has two
arities, one op); this file's own `ev` clone computes each as a direct
int-tuple transcription of Python's own str method (a CLONE of
interp.py's `_str_*` helpers, same reasoning: a `chr()`-then-back
implementation is not total on an out-of-range int, and SPEC.md calls
every member "total ... the library adds no undefined case"). No new
V1_OPS well-formedness case needed beyond arity and type: every member's
only definedness obligation is its own arguments', per SPEC.md.

DATED NOTE 2026-09-11: added `f_v1strlib`, the fuzz family for the string
library above (COVERAGE-string-lib.md's own census: the nl/ greedy order
over the sole blockers), eleven shapes, plus five hand-built probes
(`fz_p_str_splitempty`, `fz_p_str_countempty`, `fz_p_str_findempty`,
`fz_p_str_tab`, `fz_p_str_lowernonletter`) for SPEC.md's own stated
identities (`split("") == []`, `count(s, []) == len(s) + 1`, `find(s, [])
== 0`, the corrected 10-point whitespace set, `lower` fixing every
non-letter). Measured (`f_v1strlib`'s own docstring carries the per-shape
breakdown): --n 400 --seed 1 against this family alone saturates at 17
distinct well-formed tasks (one per shape/sub-variant combination; the
family's randomness is which member/branch/parameter-name is chosen, not
an embedded literal, the same saturation already measured for
`f_v1seqops`, 29 of 16000, and `f_v1divmod`, 16 of 16000), all 17
`ground_truth`-verified and all 17 carrying a twin (11 off-by-one, 2
wrong-var, 1 collapse-if, 1 negate-cond, 1 invariant-drop, with
`tostr_len`'s off-by-one tagged `+nonrefuting`: its ensures is too weak
to be falsified by the one-off shift the ladder finds). None of the
seven `lower_*.py` files has a string-lib case yet, so this family is
exercised through the reference interpreter and the twin ladder only,
not `run()`'s per-kernel lowering (`--only dafny` and the rest abstain on
every cell, per `lower`'s own `NotImplementedError` catch); `FAMILIES`
carries `("v1strlib", f_v1strlib, 4)` regardless, ready for the day a
kernel lowers a member.

Own output directory, never t/out/: the suite's drivers write t/out/ and a
second writer of the same filenames corrupts both runs (run_par.py's
_live_conflict records that lesson). Pass --out.

    python3 t/fuzz_lower.py --out DIR --n 120 --seed 1 --jobs 64

Well-formedness moved out, 2026-09-11 (ROADMAP 14.3, "The checker as a
module"): check_wf, _ty, _valid_type, _self_calls and everything only they
used (NAME_RE, the operator-classification sets, _check_stmts,
_check_returns) now live in t/check_wf.py; this file imports that module
and re-exports the same names (`fuzz_lower.check_wf`, `fuzz_lower.NAME_RE`,
etc.) as aliases, so every existing caller (grade.py, surface.py,
loop_generate.py, spec_experiment.py, boundary_probe.py, metamorphic.py,
test_lift_rules.py) is unchanged. Measured identical before/after the
move, from t/, kernels not involved:
  `python3 -c 'import fuzz_lower as f; c=f.build_corpus(400,1); \
  print(len(c), sum(1 for t in c if f.check_wf(t)))'` -> 453 4 (both)
  `python3 truth_fuzz.py --tasks-only --out <scratch> --seed 1` ->
  "corpus: 471 tasks (291 true, 167 false, 13 ill-defined) in 3s; 0
  candidates discarded" (both, before from a t/ copy with fuzz_lower.py
  reverted to the pre-move commit, after from this worktree)
  `python3 surface.py --check --n 20 --seeds 1,2` (after only, no v0
  before this move existed to compare against since surface.py already
  called fuzz_lower.check_wf) -> "corpus: 172 tasks seen, 4 rejected by
  check_wf, 168 well-formed (117 distinct)", both round-trip checks 168 of
  168, no failures.
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
import interp                                         # noqa: E402
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


# SPEC.md "The string library" (2026-09-11): CLONES of interp.py's own
# `_str_*` helpers (see that file's docstring on why this file's `ev` is a
# clone and not a shared import). Int-tuple transcriptions of Python's str
# methods, total on any int (no `chr()`), identical to interp.py's.
_WS = (9, 10, 11, 12, 13, 28, 29, 30, 31, 32)     # the 10 ASCII code
                                  # points `chr(c).isspace()` holds for,
                                  # measured 2026-09-11: interp.py's own
                                  # docstring on why SPEC.md's own "9, 10,
                                  # 11, 12, 13, 32" undercounts by 4.


def _str_split_ws(s: tuple) -> tuple:
    out, cur = [], []
    for c in s:
        if c in _WS:
            if cur:
                out.append(tuple(cur))
                cur = []
        else:
            cur.append(c)
    if cur:
        out.append(tuple(cur))
    return tuple(out)


def _str_split_sep(s: tuple, c: int) -> tuple:
    out, cur = [], []
    for x in s:
        if x == c:
            out.append(tuple(cur))
            cur = []
        else:
            cur.append(x)
    out.append(tuple(cur))
    return tuple(out)


def _str_join(rows: tuple, sep: tuple) -> tuple:
    if not rows:
        return ()
    out = list(rows[0])
    for r in rows[1:]:
        out += list(sep) + list(r)
    return tuple(out)


def _str_tostr(n: int) -> tuple:
    return tuple(ord(c) for c in str(n))


def _str_count(s: tuple, t: tuple) -> int:
    if not t:
        return len(s) + 1
    n, i, lt, ls = 0, 0, len(t), len(s)
    while i <= ls - lt:
        if s[i:i + lt] == t:
            n += 1
            i += lt
        else:
            i += 1
    return n


def _str_find(s: tuple, t: tuple) -> int:
    if not t:
        return 0
    lt, ls = len(t), len(s)
    for i in range(ls - lt + 1):
        if s[i:i + lt] == t:
            return i
    return -1


def _str_strip(s: tuple, left: bool, right: bool) -> tuple:
    lo, hi = 0, len(s)
    if left:
        while lo < hi and s[lo] in _WS:
            lo += 1
    if right:
        while hi > lo and s[hi - 1] in _WS:
            hi -= 1
    return s[lo:hi]


def _str_replace(s: tuple, t: tuple, u: tuple) -> tuple:
    if not t:
        out = []
        for c in s:
            out += list(u) + [c]
        return tuple(out + list(u))
    out, i, lt, ls = [], 0, len(t), len(s)
    while i <= ls - lt:
        if s[i:i + lt] == t:
            out += list(u)
            i += lt
        else:
            out.append(s[i])
            i += 1
    out += list(s[i:])
    return tuple(out)


def _is_upper_letter(c: int) -> bool:
    return 65 <= c <= 90


def _is_lower_letter(c: int) -> bool:
    return 97 <= c <= 122


def _str_lower(s: tuple) -> tuple:
    return tuple(c + 32 if _is_upper_letter(c) else c for c in s)


def _str_upper(s: tuple) -> tuple:
    return tuple(c - 32 if _is_lower_letter(c) else c for c in s)


def _str_isdigit(s: tuple) -> bool:
    return len(s) > 0 and all(48 <= c <= 57 for c in s)


def _str_isalpha(s: tuple) -> bool:
    return len(s) > 0 and all(_is_upper_letter(c) or _is_lower_letter(c)
                              for c in s)


def _str_isupper(s: tuple) -> bool:
    has = any(_is_upper_letter(c) or _is_lower_letter(c) for c in s)
    return has and not any(_is_lower_letter(c) for c in s)


def _str_islower(s: tuple) -> bool:
    has = any(_is_upper_letter(c) or _is_lower_letter(c) for c in s)
    return has and not any(_is_upper_letter(c) for c in s)


def _str_startswith(s: tuple, t: tuple) -> bool:
    return s[:len(t)] == t


def _str_endswith(s: tuple, t: tuple) -> bool:
    return len(t) <= len(s) and (len(t) == 0 or s[len(s) - len(t):] == t)


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
    if op == "seq":
        # SPEC.md "Sequences: literals, concatenation, slices" (2026-09-09):
        # [e1, ..., en], every argument already evaluated above, so a
        # literal is defined iff all its elements are. A CLONE of
        # interp.ev's own seq arm.
        return tuple(args)
    if op == "slice":
        # s[a..b]: DEFINED IFF 0 <= a <= b <= len(s); elements a..b-1. A
        # CLONE of interp.ev's own slice arm.
        s, lo, hi = args
        if not (0 <= lo <= hi <= len(s)):
            raise Undef(f"slice bounds [{lo}..{hi}] outside "
                        f"0 <= a <= b <= {len(s)}")
        return tuple(s[lo:hi])
    if op == "+":
        if isinstance(args[0], tuple):
            # s + t on two seqs is concatenation (SPEC.md "Sequences:
            # literals, concatenation, slices"): always defined, the
            # length cap the only limit, as for fill. A CLONE of
            # interp.ev's own + arm.
            if len(args[0]) + len(args[1]) > MAX_SEQ:
                raise Budget("seq length cap")
            return args[0] + tuple(args[1])
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
    if op == "pair":
        # SPEC.md "Pairs" (2026-09-10): (a, b), a value defined iff both
        # components are (every argument above is already evaluated). A
        # CLONE of interp.ev's own pair arm, using interp.Pair rather than a
        # bare tuple for the same reason interp.py does: a tuple here would
        # be indistinguishable from a seq of the same length, and this
        # file's `==`/`!=` below (Python's own operators) rely on that
        # distinction the same way interp.py's `_tv` does.
        return interp.Pair(args[0], args[1])
    if op == "fst":
        return args[0].a
    if op == "snd":
        return args[0].b
    if op == "split":
        return (_str_split_ws(args[0]) if len(args) == 1
                else _str_split_sep(args[0], args[1]))
    if op == "join":
        return _str_join(args[0], args[1])
    if op == "tostr":
        return _str_tostr(args[0])
    if op == "count":
        return _str_count(args[0], args[1])
    if op == "find":
        return _str_find(args[0], args[1])
    if op == "strip":
        return _str_strip(args[0], True, True)
    if op == "lstrip":
        return _str_strip(args[0], True, False)
    if op == "rstrip":
        return _str_strip(args[0], False, True)
    if op == "replace":
        return _str_replace(args[0], args[1], args[2])
    if op == "lower":
        return _str_lower(args[0])
    if op == "upper":
        return _str_upper(args[0])
    if op == "isdigit":
        return _str_isdigit(args[0])
    if op == "isalpha":
        return _str_isalpha(args[0])
    if op == "isupper":
        return _str_isupper(args[0])
    if op == "islower":
        return _str_islower(args[0])
    if op == "startswith":
        return _str_startswith(args[0], args[1])
    if op == "endswith":
        return _str_endswith(args[0], args[1])
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
# 2. Well-formedness: moved to check_wf.py (ROADMAP 14.3, 2026-09-11).
# check_wf, _ty, _valid_type and their helpers now live in check_wf.py, a
# module of its own with no import of this file (checked by
# test_check_wf.py's test_no_cycle), imported by this file, surface.py and
# the command. The names below are kept as aliases so grade.py (which reads
# fuzz_lower.NAME_RE directly) and every other caller of
# fuzz_lower.check_wf are unchanged.
# ===========================================================================

import check_wf as _check_wf_mod                     # noqa: E402

NAME_RE = _check_wf_mod.NAME_RE
check_wf = _check_wf_mod.check_wf
_valid_type = _check_wf_mod._valid_type
_ty = _check_wf_mod._ty
_self_calls = _check_wf_mod._self_calls          # used by _funs_of below, not only check_wf




# ===========================================================================
# 3. Ground truth by sampling.
# ===========================================================================

SMALL = [-3, -2, -1, 0, 1, 2, 3, 4, 5, 7]
BIG = [2 ** 31, -2 ** 31 - 1, 2 ** 40, 10 ** 12, -10 ** 12, 2 ** 63]


def _sample_value(ty, rng):
    """One value of type `ty` ("int"/"bool"/"seq", a pair `{"pair": [T1,
    T2]}` (SPEC.md "Pairs", 2026-09-10), or a nested seq `{"seq": "seq"}`
    (SPEC.md "Nested sequences", 2026-09-10)). Pulled out of sample_inputs
    so a pair's own two components, or a nested seq's own rows, are drawn
    from exactly the same pool their base type would use standalone,
    recursively: a pair's T1/T2 and a nested seq's rows are always base
    types (no pair of pairs, no three levels), so this never nests past
    one level."""
    if ty == "seq":
        n = rng.choice([0, 0, 1, 2, 3, 3, 4, 5, 6])
        # SPEC.md gate 1: a seq's ELEMENTS are mathematical integers, same
        # as an int parameter, so they are drawn from the same two pools.
        # Drawing them from SMALL alone made every element-width claim
        # unfalsifiable BY SAMPLING: the 2026-09-01 framac finding (`int *s`
        # typed every element is_sint32) had to be hand-written as
        # fz_p_elemwidth because no generated task could reach a
        # counterexample. 12% here rather than the 8% used for a scalar: a
        # counterexample needs only ONE big element, and a seq has several
        # draws.
        return tuple((rng.choice(BIG) if rng.random() < 0.12
                     else rng.choice(SMALL)) for _ in range(n))
    if ty == "bool":
        return rng.choice([True, False])
    if isinstance(ty, dict) and "pair" in ty:
        # SPEC.md "Pairs": a pair value, interp.Pair rather than a bare
        # tuple (see this file's `ev` "pair" arm on why).
        t1, t2 = ty["pair"]
        return interp.Pair(_sample_value(t1, rng), _sample_value(t2, rng))
    if isinstance(ty, dict):
        # SPEC.md "Nested sequences" (2026-09-10): {"seq": "seq"}. Rows are
        # drawn a little shorter and fewer than a bare seq's own elements
        # (n up to 4 rows, each row up to 3 ints) so a nested-seq input
        # stays small even though every row is itself a several-element
        # draw; ragged by default (SPEC.md: "no cross-row length equality"
        # measured), so rows are drawn INDEPENDENTLY and not forced equal.
        n = rng.choice([0, 0, 1, 2, 2, 3, 4])
        return tuple(_sample_value("seq", rng) for _ in range(n))
    return rng.choice(BIG) if rng.random() < 0.08 else rng.choice(SMALL)


def sample_inputs(task, rng, k):
    out = []
    for _ in range(k):
        env = {p["name"]: _sample_value(p["type"], rng)
               for p in task["params"]}
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
    if isinstance(v, interp.Pair):
        # SPEC.md "Pairs": shown as a 2-list, recursing so a seq component
        # (itself a tuple) prints as a list too rather than a raw tuple. A
        # CLONE of interp.py's own `_j`, checked BEFORE the tuple case below
        # since interp.Pair is deliberately not a tuple.
        return [_j(v.a), _j(v.b)]
    if isinstance(v, tuple):
        # SPEC.md "Nested sequences" (2026-09-10): a row is itself a tuple,
        # so recurse rather than stopping at `list(v)`, which would leave
        # the rows as raw tuples one level down. A CLONE of interp.py's own
        # `_j`, same fix, same reason.
        return [_j(x) for x in v]
    return v


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
    def draw(ty):
        if ty == "seq":
            ln = rng.choice([0, 1, 2, 3, 4])
            return tuple(rng.choice(SMALL) for _ in range(ln))
        if ty == "bool":
            return rng.choice([True, False])
        if isinstance(ty, dict) and "pair" in ty:
            # SPEC.md "Pairs": a pair-typed name in scope at the loop (the
            # task's own return, most often, per f_v1pairs's loop shapes --
            # min_max's two-int loop and the sentinel idiom both assemble
            # their pair AFTER the loop, but `ret` is still in `names`
            # unconditionally, so ensures that reads it via `fst`/`snd`
            # under the exit-entailment check below needs a real
            # interp.Pair here, not the int this branch used to fall
            # through to and hand `.a` an AttributeError on).
            t1, t2 = ty["pair"]
            return interp.Pair(draw(t1), draw(t2))
        if isinstance(ty, dict):
            # SPEC.md "Nested sequences" (2026-09-10): a seq<seq>-typed name
            # in scope at the loop (row_max_len's own parameter `m`, read by
            # every surviving invariant and by `ensures` through `at`/`len`
            # under the exit-entailment and preservation checks below,
            # exactly the role min_max's `ret` played for a pair) needs a
            # real tuple-of-rows here, for the same reason the pair arm
            # above needs a real interp.Pair: a plain int or an unnested seq
            # would raise, not merely disagree, the first time `at(m, k)`
            # is asked for a row.
            ln = rng.choice([0, 1, 2, 3])
            return tuple(draw("seq") for _ in range(ln))
        return rng.choice(SMALL)

    exit_w, pres_w = None, None
    for _ in range(k):
        env = {n: draw(ty) for n, ty in names}
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


def SEQ(*es):
    return OP("seq", *es)


def SLICE(s, a, b):
    return OP("slice", V(s), a, b)


def CAT(a, b):
    return OP("+", a, b)


def PAIR(a, b):
    return OP("pair", a, b)


def FST(p):
    return OP("fst", p)


def SND(p):
    return OP("snd", p)


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
    order and go first; the rest follow in their order. `slice` carries the
    same obligation, 0 <= a <= b <= len(s) (2026-09-09, sequence ops), so an
    invariant that slices under loop-varying bounds is held back exactly
    like one that indexes."""
    def has_at(e):
        if isinstance(e, dict):
            return (e.get("op") in ("at", "update", "slice")
                   or any(has_at(v) for v in e.values()))
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


def f_v1seqops(rng, idx):
    """SPEC.md "Sequences: literals, concatenation, slices (v1)"
    (2026-09-09): the literal, `+` concatenation and `slice`, on top of
    "Sequences as values"'s `at`/`update`/`fill`. Every ensures below is
    element-wise (`forall k in [0, len(r)) . r[k] == ...`), never a
    whole-seq `==`: SPEC.md's `==` on two seqs is extensional and
    f_v1seqval's fz_p_seqeq_* probes already measure that gap on its own,
    so this family stays on the ground `at`/`slice` reads a lowering
    cannot totalize away. Loop invariants go through WH_DF: `_defined_first`
    now treats `slice` the same as `at`/`update` (2026-09-09), so a
    length/range invariant is checked before one that slices or indexes."""
    me = f"fz_v1seqops_{idx:03d}"
    shape = rng.choice(["tail", "head", "window", "append_loop",
                        "filter_loop", "concat_params", "rotate",
                        "prepend_loop"])

    if shape in ("tail", "head"):
        # A slice of a parameter with a requires on its length: SPEC.md's
        # own committed `tail` task, plus its mirror `head`.
        if shape == "tail":
            body = [ASG("r", SLICE("s", I(1), LEN("s")))]
            ens = [OP("==", LEN("r"), OP("-", LEN("s"), I(1))),
                  FA("k", I(0), LEN("r"),
                     OP("==", AT("r", V("k")),
                        AT("s", OP("+", V("k"), I(1)))))]
        else:
            body = [ASG("r", SLICE("s", I(0), OP("-", LEN("s"), I(1))))]
            ens = [OP("==", LEN("r"), OP("-", LEN("s"), I(1))),
                  FA("k", I(0), LEN("r"),
                     OP("==", AT("r", V("k")), AT("s", V("k"))))]
        return {"t": 1, "name": me, "gate": "quantifiers",
                "params": [{"name": "s", "type": "seq"}],
                "returns": [{"name": "r", "type": "seq"}],
                "requires": [OP(">=", LEN("s"), I(1))],
                "ensures": ens, "body": body, "_shape": shape}

    if shape == "window":
        # s[a..b] with a, b PARAMETERS, exactly SPEC.md's own definedness
        # obligation stated as a requires: 0 <= a <= b <= len(s).
        body = [ASG("r", SLICE("s", V("a"), V("b")))]
        ens = [OP("==", LEN("r"), OP("-", V("b"), V("a"))),
              FA("k", I(0), LEN("r"),
                 OP("==", AT("r", V("k")),
                    AT("s", OP("+", V("a"), V("k")))))]
        return {"t": 1, "name": me, "gate": "quantifiers",
                "params": [{"name": "s", "type": "seq"},
                          {"name": "a", "type": "int"},
                          {"name": "b", "type": "int"}],
                "returns": [{"name": "r", "type": "seq"}],
                "requires": [AND(OP("<=", I(0), V("a")),
                                OP("<=", V("a"), V("b")),
                                OP("<=", V("b"), LEN("s")))],
                "ensures": ens, "body": body, "_shape": shape}

    if shape == "append_loop":
        # r := r + [f(s[i])] for every element: the census's top append
        # idiom (SPEC.md "Sequences: literals, concatenation, slices",
        # 28 of 50 blocked DafnyBench programs), now over `+` and `seq`
        # rather than `update` into a pre-filled `r`.
        c = rng.choice([-5, -3, -2, -1, 1, 2, 3, 5])

        def f(x):
            return OP("+", x, I(c))

        body = [ASG("r", SEQ()), LOC("i", "int", I(0)),
               WH_DF(OP("<", V("i"), LEN("s")),
                  [OP("==", LEN("r"), V("i")),
                   AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("s"))),
                   FA("k", I(0), V("i"),
                      OP("==", AT("r", V("k")), f(AT("s", V("k")))))],
                  OP("-", LEN("s"), V("i")),
                  [ASG("r", CAT(V("r"), SEQ(f(AT("s", V("i")))))),
                   ASG("i", OP("+", V("i"), I(1)))])]
        ens = [OP("==", LEN("r"), LEN("s")),
              FA("k", I(0), LEN("s"),
                 OP("==", AT("r", V("k")), f(AT("s", V("k")))))]
        return {"t": 1, "name": me, "gate": "loops",
                "params": [{"name": "s", "type": "seq"}],
                "returns": [{"name": "r", "type": "seq"}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    if shape == "filter_loop":
        # r := r + [s[i]] under a condition: `filter_pos`'s shape, now
        # measured for `len(r) <= len(s)` and an element PROPERTY (every
        # kept element satisfies the predicate) rather than a positional
        # correspondence, since a dropped element breaks any index-by-index
        # relation between r and s.
        kind = rng.choice(["nonneg", "gt", "lt"])
        c = rng.choice([-3, -2, -1, 0, 1, 2, 3])

        def pred(x):
            if kind == "nonneg":
                return OP(">=", x, I(0))
            if kind == "gt":
                return OP(">", x, I(c))
            return OP("<", x, I(c))

        body = [ASG("r", SEQ()), LOC("i", "int", I(0)),
               WH_DF(OP("<", V("i"), LEN("s")),
                  [OP("<=", LEN("r"), V("i")),
                   AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("s"))),
                   FA("k", I(0), LEN("r"), pred(AT("r", V("k"))))],
                  OP("-", LEN("s"), V("i")),
                  [IFS(pred(AT("s", V("i"))),
                       [ASG("r", CAT(V("r"), SEQ(AT("s", V("i")))))],
                       []),
                   ASG("i", OP("+", V("i"), I(1)))])]
        ens = [OP("<=", LEN("r"), LEN("s")),
              FA("k", I(0), LEN("r"), pred(AT("r", V("k"))))]
        return {"t": 1, "name": me, "gate": "loops",
                "params": [{"name": "s", "type": "seq"}],
                "returns": [{"name": "r", "type": "seq"}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    if shape == "concat_params":
        # r := s + u, the polymorphic `+` at its own two-parameter shape.
        # SPEC.md writes the concatenation `s + t`, but `t` is the surface
        # syntax's own format-version keyword (`t 0` / `t 1` opens every
        # file), so a parameter named `t` has no notation as a name
        # (2026-09-09, the sequences-as-values family hit the same wall);
        # `u` is the second seq here instead.
        body = [ASG("r", CAT(V("s"), V("u")))]
        ens = [OP("==", LEN("r"), OP("+", LEN("s"), LEN("u"))),
              FA("k", I(0), LEN("s"),
                 OP("==", AT("r", V("k")), AT("s", V("k")))),
              FA("k", I(0), LEN("u"),
                 OP("==", AT("r", OP("+", V("k"), LEN("s"))), AT("u", V("k"))))]
        return {"t": 1, "name": me, "gate": "quantifiers",
                "params": [{"name": "s", "type": "seq"},
                          {"name": "u", "type": "seq"}],
                "returns": [{"name": "r", "type": "seq"}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    if shape == "rotate":
        # s[1..] + s[..1]: `slice` and `+` composed, under len(s) > 0 so
        # both slices, and the rotated-in element at index 0, are in range.
        body = [ASG("r", CAT(SLICE("s", I(1), LEN("s")),
                             SLICE("s", I(0), I(1))))]
        ens = [OP("==", LEN("r"), LEN("s")),
              FA("k", I(0), OP("-", LEN("s"), I(1)),
                 OP("==", AT("r", V("k")),
                    AT("s", OP("+", V("k"), I(1))))),
              OP("==", AT("r", OP("-", LEN("s"), I(1))), AT("s", I(0)))]
        return {"t": 1, "name": me, "gate": "quantifiers",
                "params": [{"name": "s", "type": "seq"}],
                "returns": [{"name": "r", "type": "seq"}],
                "requires": [OP(">", LEN("s"), I(0))],
                "ensures": ens, "body": body, "_shape": shape}

    # prepend_loop: r := [s[i]] + r builds the reverse of s, one element at
    # a time from the front; r[k] == s[i-1-k] for k in [0,i) is the
    # invariant this shape earns, not the append_loop's r[k] == f(s[k]).
    body = [ASG("r", SEQ()), LOC("i", "int", I(0)),
           WH_DF(OP("<", V("i"), LEN("s")),
              [OP("==", LEN("r"), V("i")),
               AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("s"))),
               FA("k", I(0), V("i"),
                  OP("==", AT("r", V("k")),
                     AT("s", OP("-", OP("-", V("i"), I(1)), V("k")))))],
              OP("-", LEN("s"), V("i")),
              [ASG("r", CAT(SEQ(AT("s", V("i"))), V("r"))),
               ASG("i", OP("+", V("i"), I(1)))])]
    ens = [OP("==", LEN("r"), LEN("s")),
          FA("k", I(0), LEN("s"),
             OP("==", AT("r", V("k")),
                AT("s", OP("-", OP("-", LEN("s"), I(1)), V("k")))))]
    return {"t": 1, "name": me, "gate": "loops",
            "params": [{"name": "s", "type": "seq"}],
            "returns": [{"name": "r", "type": "seq"}],
            "requires": [], "ensures": ens, "body": body,
            "_shape": "prepend_loop"}


def f_v1pairs(rng, idx):
    """SPEC.md "Pairs" (2026-09-10): `{"pair": [T1, T2]}`, `fst`/`snd`
    projecting a pair value, always defined on one; `pair` itself defined
    iff both components are. The census that motivated the construct (785
    DafnyBench programs, `multi-return`; 24,748 nl/ problems, `tuple`)
    settled on eight shapes, one per instance here:

      expr_pair    loop-free: r := (e1, e2), two small linear expressions
                   over the int params, never a bare param echo.
      divmod_pair  the committed task's own shape, generalized: r := (x
                   div y, x mod y) under `requires y > 0`.
      proj_param   a pair PARAMETER projected and recombined: r := fst(p)
                   op snd(p) for op in {+, -, *}.
      swap_param   the swap the twin ladder names by name (SPEC.md "the
                   twin ladder gains one move"): r := (snd(p), fst(p)).
      sentinel     the flag-and-value idiom: a search loop over a seq
                   threads a bool `found` and an int `val` as two SEPARATE
                   locals (never a pair-typed loop variable -- SPEC.md's
                   frame rule havocs a pair by name, but nothing here needs
                   that, since the pair is assembled only after the loop
                   exits), paired up at the end.
      minmax       min_max's own shape: a loop keeping two ints (lo, hi)
                   in one pass, paired at the end.
      seq_len_pair a (seq, int) pair built from a slice and a length, the
                   window shape f_v1seqops's own "window" instance uses,
                   now wrapped in a pair with the seq's own length as the
                   second component.
      eq_params    equality of two pair PARAMETERS as a bool return: r :=
                   (p == q), and the ensures restates SPEC.md's own rule
                   that `==` on two pairs is componentwise, rather than
                   just echoing the assign.

    Twins go through the same GROUNDED ladder as every other family
    (harness.make_twin / harness.twin_cached in build_corpus/run): a
    loop-free shape gets whatever the EXTENSIONAL ladder's witness search
    finds (often wrong-var's pair-swap or fst/snd-swap move, SPEC.md
    "Pairs"), a loop-carrying shape (sentinel, minmax) gets
    INVARIANT-DROP first, same precedence as every other loop family
    here."""
    me = f"fz_v1pairs_{idx:03d}"
    shape = rng.choice(["expr_pair", "divmod_pair", "proj_param",
                        "swap_param", "sentinel", "minmax", "seq_len_pair",
                        "eq_params"])
    PT_II = {"pair": ["int", "int"]}

    if shape == "expr_pair":
        e1 = _lin(rng, ["x", "y"])
        e2 = _lin(rng, ["x", "y"])
        body = [ASG("r", PAIR(e1, e2))]
        ens = [OP("==", FST(V("r")), e1), OP("==", SND(V("r")), e2)]
        return {"t": 1, "name": me,
                "params": [{"name": "x", "type": "int"},
                          {"name": "y", "type": "int"}],
                "returns": [{"name": "r", "type": PT_II}],
                "requires": [], "ensures": ens, "body": body,
                "_shape": shape}

    if shape == "divmod_pair":
        # t/tasks/divmod_pair.json's own shape, generalized over the
        # family's random-seed loop: r := (x div y, x mod y), requires
        # y > 0 for the SAME reason the committed task states it (SPEC.md
        # "Division and modulo": Euclidean, undefined at y == 0, and the
        # ensures below pins 0 <= r.1 < y, which needs y positive rather
        # than merely nonzero).
        body = [ASG("r", PAIR(OP("div", V("x"), V("y")),
                             OP("mod", V("x"), V("y"))))]
        ens = [OP("==", OP("+", OP("*", FST(V("r")), V("y")), SND(V("r"))),
                  V("x")),
              OP("<=", I(0), SND(V("r"))),
              OP("<", SND(V("r")), V("y"))]
        return {"t": 1, "name": me,
                "params": [{"name": "x", "type": "int"},
                          {"name": "y", "type": "int"}],
                "returns": [{"name": "r", "type": PT_II}],
                "requires": [OP(">", V("y"), I(0))],
                "ensures": ens, "body": body, "_shape": shape}

    if shape == "proj_param":
        o = rng.choice(["+", "-", "*"])
        e = OP(o, FST(V("p")), SND(V("p")))
        body = [ASG("r", e)]
        ens = [OP("==", V("r"), e)]
        return {"t": 1, "name": me,
                "params": [{"name": "p", "type": PT_II}],
                "returns": [{"name": "r", "type": "int"}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    if shape == "swap_param":
        # SPEC.md "the twin ladder gains one move: wrong-var swaps the two
        # components of a pair and swaps fst for snd in a projection" --
        # this shape is exactly what that move targets: the swap is the
        # real body, so wrong-var's un-swap is the twin.
        body = [ASG("r", PAIR(SND(V("p")), FST(V("p"))))]
        ens = [OP("==", FST(V("r")), SND(V("p"))),
              OP("==", SND(V("r")), FST(V("p")))]
        return {"t": 1, "name": me,
                "params": [{"name": "p", "type": PT_II}],
                "returns": [{"name": "r", "type": PT_II}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    if shape == "sentinel":
        # The flag-and-value idiom (SPEC.md "Pairs": "3 the (bool, int)
        # flag-and-value idiom"): `found`/`val` are two SEPARATE scalar
        # locals threaded through the loop (never a pair-typed loop
        # variable), paired up only after the loop exits. The loop runs
        # the WHOLE range rather than stopping at the first hit (unlike
        # f_v1exit's early return, which this shape deliberately avoids:
        # a pair-typed RETURN cannot be assigned piecemeal by an early
        # `return` under SPEC.md's "one return value" rule the way a
        # scalar can), so `found`/`val` are only ever written the first
        # time the predicate holds.
        p_i, op, rhs = _pred(rng, AT("s", V("i")), [])
        p_j = OP(op, AT("s", V("j")), rhs)
        body = [LOC("found", "bool", BL(False)), LOC("val", "int", I(0)),
               LOC("i", "int", I(0)),
               WH_DF(OP("<", V("i"), LEN("s")),
                  [AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("s"))),
                   OP("implies", OP("not", V("found")),
                      FA("j", I(0), V("i"), _negate(p_j))),
                   OP("implies", V("found"),
                      EX("j", I(0), V("i"),
                         AND(p_j, OP("==", V("val"), AT("s", V("j"))))))],
                  OP("-", LEN("s"), V("i")),
                  [IFS(AND(OP("not", V("found")), p_i),
                       [ASG("found", BL(True)), ASG("val", AT("s", V("i")))],
                       []),
                   ASG("i", OP("+", V("i"), I(1)))]),
               ASG("r", PAIR(V("found"), V("val")))]
        # p_i was built from elem=at(s, i), so the ensures quantifiers below
        # reuse "i" as their own bound name too (fresh in each quantifier's
        # scope, exactly f_v1exit's own convention): a DIFFERENT bound name
        # here would leave p_i's "i" unbound outside the loop that declared
        # it.
        ens = [OP("==", FST(V("r")), EX("i", I(0), LEN("s"), p_i)),
              OP("implies", FST(V("r")),
                 EX("i", I(0), LEN("s"),
                    AND(p_i, OP("==", SND(V("r")), AT("s", V("i"))))))]
        return {"t": 1, "name": me, "gate": "loops",
                "params": [{"name": "s", "type": "seq"}],
                "returns": [{"name": "r", "type": {"pair": ["bool", "int"]}}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    if shape == "minmax":
        # t/tasks/min_max.json's own shape: a loop keeping two ints (lo,
        # hi) in one pass, non-empty s required so the seed at index 0 is
        # in range, paired up only after the loop.
        body = [LOC("lo", "int", AT("s", I(0))), LOC("hi", "int", AT("s", I(0))),
               LOC("i", "int", I(1)),
               WH_DF(OP("<", V("i"), LEN("s")),
                  [AND(OP("<=", I(1), V("i")), OP("<=", V("i"), LEN("s"))),
                   FA("k", I(0), V("i"), OP("<=", V("lo"), AT("s", V("k")))),
                   FA("k", I(0), V("i"), OP("<=", AT("s", V("k")), V("hi"))),
                   EX("k", I(0), V("i"), OP("==", V("lo"), AT("s", V("k")))),
                   EX("k", I(0), V("i"), OP("==", V("hi"), AT("s", V("k"))))],
                  OP("-", LEN("s"), V("i")),
                  [IFS(OP("<", AT("s", V("i")), V("lo")),
                       [ASG("lo", AT("s", V("i")))], []),
                   IFS(OP(">", AT("s", V("i")), V("hi")),
                       [ASG("hi", AT("s", V("i")))], []),
                   ASG("i", OP("+", V("i"), I(1)))]),
               ASG("r", PAIR(V("lo"), V("hi")))]
        ens = [FA("k", I(0), LEN("s"), OP("<=", FST(V("r")), AT("s", V("k")))),
              FA("k", I(0), LEN("s"), OP("<=", AT("s", V("k")), SND(V("r")))),
              EX("k", I(0), LEN("s"), OP("==", FST(V("r")), AT("s", V("k")))),
              EX("k", I(0), LEN("s"), OP("==", SND(V("r")), AT("s", V("k"))))]
        return {"t": 1, "name": me, "gate": "loops",
                "params": [{"name": "s", "type": "seq"}],
                "returns": [{"name": "r", "type": PT_II}],
                "requires": [OP(">", LEN("s"), I(0))],
                "ensures": ens, "body": body, "_shape": shape}

    if shape == "seq_len_pair":
        # A (seq, int) pair built from a slice and the seq's own length,
        # f_v1seqops's own "window" instance wrapped in a pair: the SAME
        # definedness obligation SPEC.md states for `slice`, 0 <= a <= b <=
        # len(s), stated as a requires exactly as that family states it.
        body = [ASG("r", PAIR(SLICE("s", V("a"), V("b")), LEN("s")))]
        ens = [OP("==", OP("len", FST(V("r"))), OP("-", V("b"), V("a"))),
              FA("k", I(0), OP("len", FST(V("r"))),
                 OP("==", OP("at", FST(V("r")), V("k")),
                    AT("s", OP("+", V("a"), V("k"))))),
              OP("==", SND(V("r")), LEN("s"))]
        return {"t": 1, "name": me, "gate": "quantifiers",
                "params": [{"name": "s", "type": "seq"},
                          {"name": "a", "type": "int"},
                          {"name": "b", "type": "int"}],
                "returns": [{"name": "r", "type": {"pair": ["seq", "int"]}}],
                "requires": [AND(OP("<=", I(0), V("a")),
                                OP("<=", V("a"), V("b")),
                                OP("<=", V("b"), LEN("s")))],
                "ensures": ens, "body": body, "_shape": shape}

    # eq_params: equality of two pair PARAMETERS as a bool return. SPEC.md
    # "Pairs": "`==` ... on two pairs of one type are componentwise ...
    # the polymorphic `==` again"; the ensures restates that rule rather
    # than echoing the assign, so a kernel that merely re-checks r against
    # `p == q` (the body's own expression) proves nothing this task did
    # not already say by construction.
    body = [ASG("r", OP("==", V("p"), V("q")))]
    ens = [OP("==", V("r"),
              AND(OP("==", FST(V("p")), FST(V("q"))),
                 OP("==", SND(V("p")), SND(V("q")))))]
    return {"t": 1, "name": me,
            "params": [{"name": "p", "type": PT_II},
                      {"name": "q", "type": PT_II}],
            "returns": [{"name": "r", "type": "bool"}],
            "requires": [], "ensures": ens, "body": body,
            "_shape": "eq_params"}


NEST_T = {"seq": "seq"}     # SPEC.md "Nested sequences (v1)": seq<seq>


def f_v1nested(rng, idx):
    """SPEC.md "Nested sequences (v1)" (2026-09-10): `{"seq": "seq"}`, one
    level, every seq operator polymorphic by static type already (no new
    Expr forms -- `_valid_type`/`_ty` above, `ev`, `_sample_value` and
    `invariant_load_bearing`'s `draw` all took this construct when the core
    landed, 2026-09-10, commit 6c8061d). Ten shapes, over the census's own
    population (scratchpad shapes-nested/run_output.txt, DafnyBench and
    nl/): a bare `at`/`len`/`update`/`slice`/`+`/`==` composed one level
    deeper is already well-typed, so this family's job is coverage of the
    shapes that dominate, not new machinery.

      param_rowlen   the DafnyBench shape (10 methods, Item 5): a nested
                     PARAMETER read row by row under a single-binder
                     `forall`, each iteration checking a `len(s[i])` fact
                     against a parameter (AllSequencesEqualLength's own
                     shape) -- INVARIANT-DROP twin.
      build_matrix   the nl/ shape (3,008 locals, Item 1): a local matrix
                     built by APPENDING ROWS in a loop (Item 2's "append
                     row (s + [row])", `s + [row]` over `seq<seq>` rather
                     than `f_v1seqops`'s own plain-seq append) -- also
                     INVARIANT-DROP.
      nested_lit     a nested literal with generation-time-fixed rows and
                     elements, indexed directly (no parameter, no loop),
                     `fz_p_nest_lit`'s own shape generalized over random
                     shapes -- COLLAPSE-IF has nothing to collapse here (no
                     `if`), so this shape is one of the "no-twin" instances
                     `build_corpus` already refuses by design (measured on
                     `f_v1seqops`'s loop-free shapes the same way).
      cell_read      `s[i][j]` (`at(at(s,i),j)`) guarded by an `if` testing
                     BOTH bounds (`fz_p_pair_seq`'s own idiom, read over a
                     nested seq instead of a `(seq, int)` pair) --
                     COLLAPSE-IF (the ladder's first rung, tried before
                     DROP-GUARD ever is) already witnesses this shape: the
                     unconditional `then` branch reads `at(m[i], j)` with
                     no guard at all, undefined whenever the outer bound
                     alone would have let a caller through, measured
                     rather than assumed.
      extreme_row    `row_max_len`'s own shape, generalized to `rng.choice`
                     of max or min length over the rows -- INVARIANT-DROP.
      row_swap_update `swap_rows`'s own shape, generalized: `rng.choice`
                     of the committed swap or a single-row `update(m, i,
                     u)` against a fresh row parameter `u` -- the twin
                     ladder's `off-by-one` on the index, or `wrong-var` on
                     `i`/`j`, is what a loop-free shape like this earns.
      concat_nested  `m + n` on two nested PARAMETERS, `f_v1seqops`'s own
                     `concat_params` one level deeper -- `off-by-one`/
                     `wrong-var` on the split point.
      slice_rows     `m[a..b]`, `f_v1seqops`'s own `window` one level
                     deeper -- `off-by-one` on `a`/`b`.
      eq_nested      `m == n` on two nested PARAMETERS as a bool return,
                     the ensures restating SPEC.md's own componentwise rule
                     (same length, equal rows) rather than the polymorphic
                     `==` the body already computes, `f_v1pairs`'s own
                     `eq_params` one level deeper -- `wrong-var` swapping
                     `m` for `n` in one conjunct.
      row_sum        a sum over ONE row's elements, `m[ri]` selected by a
                     parameter: the body accumulates it with a real
                     `while` loop (an int local, never a nested-seq loop
                     variable), and the ensures states the exact total via
                     a RECURSIVE spec_fun over the row (`f_v1rec`'s own
                     gate-3 idiom, the only way v1 states an aggregate with
                     no closed form, since summation is not one of the
                     polymorphic ops SPEC.md lists) -- INVARIANT-DROP.
                     Where SPEC.md was silent on how a sum composes with
                     "the nested single-binder quantifier form" it names
                     for a row (`forall i :: forall j :: ...`): that form
                     states a BOUND or a WITNESS over a row (`extreme_row`
                     and `param_rowlen` both use exactly it, one binder
                     each, nested by the outer index), not an exact
                     arithmetic total, so `row_sum` is the one shape that
                     needs the recursion idiom instead and is not claimed
                     to be an instance of the quantifier form itself.

    Twins go through the GROUNDED ladder (harness.make_twin/twin_cached),
    same as every other family; `_c_off_by_one`'s `at`/`update`/`slice`
    arms and `_c_drop_guard`'s `and`-conjunct arm already generalize to a
    nested read with no change (they match on the operator tag, not on
    the operand's type), which is the same "no new machinery" property
    the core landing gave `_ty`/`ev`."""
    me = f"fz_v1nested_{idx:03d}"
    shape = rng.choice(["param_rowlen", "build_matrix", "nested_lit",
                        "cell_read", "extreme_row", "row_swap_update",
                        "concat_nested", "slice_rows", "eq_nested",
                        "row_sum"])

    if shape == "param_rowlen":
        body = [LOC("ok", "bool", BL(True)), LOC("i", "int", I(0)),
               WH_DF(OP("<", V("i"), LEN("m")),
                  [OP("==", V("ok"),
                      FA("k", I(0), V("i"),
                         OP("==", OP("len", AT("m", V("k"))), V("L")))),
                   AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("m")))],
                  OP("-", LEN("m"), V("i")),
                  [IFS(OP("!=", OP("len", AT("m", V("i"))), V("L")),
                       [ASG("ok", BL(False))], []),
                   ASG("i", OP("+", V("i"), I(1)))]),
               ASG("r", V("ok"))]
        ens = [OP("==", V("r"),
                  FA("i", I(0), LEN("m"),
                     OP("==", OP("len", AT("m", V("i"))), V("L"))))]
        return {"t": 1, "name": me, "gate": "loops",
                "params": [{"name": "m", "type": NEST_T},
                          {"name": "L", "type": "int"}],
                "returns": [{"name": "r", "type": "bool"}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    if shape == "build_matrix":
        body = [LOC("m", NEST_T, SEQ()), LOC("i", "int", I(0)),
               WH_DF(OP("<", V("i"), LEN("s")),
                  [OP("==", LEN("m"), V("i")),
                   AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("s"))),
                   FA("k", I(0), V("i"),
                      AND(OP("==", OP("len", AT("m", V("k"))), I(1)),
                         OP("==", OP("at", AT("m", V("k")), I(0)),
                            AT("s", V("k")))))],
                  OP("-", LEN("s"), V("i")),
                  [ASG("m", CAT(V("m"), SEQ(SEQ(AT("s", V("i")))))),
                   ASG("i", OP("+", V("i"), I(1)))]),
               ASG("r", V("m"))]
        ens = [OP("==", LEN("r"), LEN("s")),
              FA("k", I(0), LEN("s"),
                 AND(OP("==", OP("len", AT("r", V("k"))), I(1)),
                    OP("==", OP("at", AT("r", V("k")), I(0)), AT("s", V("k")))))]
        return {"t": 1, "name": me, "gate": "loops",
                "params": [{"name": "s", "type": "seq"}],
                "returns": [{"name": "r", "type": NEST_T}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    if shape == "nested_lit":
        n_rows = rng.choice([0, 1, 1, 2, 2, 3])
        rows = [[rng.choice(SMALL) for _ in range(rng.choice([0, 1, 2, 3]))]
                for _ in range(n_rows)]
        body = [ASG("r", SEQ(*[SEQ(*[I(v) for v in row]) for row in rows]))]
        ens = [OP("==", LEN("r"), I(n_rows))]
        for ri, row in enumerate(rows):
            ens.append(OP("==", OP("len", AT("r", I(ri))), I(len(row))))
            for ci, v in enumerate(row):
                ens.append(OP("==", OP("at", AT("r", I(ri)), I(ci)), I(v)))
        return {"t": 1, "name": me,
                "params": [], "returns": [{"name": "r", "type": NEST_T}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    if shape == "cell_read":
        guard = AND(OP("<=", I(0), V("i")), OP("<", V("i"), LEN("m")),
                   OP("<=", I(0), V("j")),
                   OP("<", V("j"), OP("len", AT("m", V("i")))))
        body = [IFS(guard, [ASG("r", OP("at", AT("m", V("i")), V("j")))],
                   [ASG("r", I(0))])]
        ens = [OP("implies", guard,
                  OP("==", V("r"), OP("at", AT("m", V("i")), V("j")))),
              OP("implies", OP("not", guard), OP("==", V("r"), I(0)))]
        return {"t": 1, "name": me, "gate": "quantifiers",
                "params": [{"name": "m", "type": NEST_T},
                          {"name": "i", "type": "int"},
                          {"name": "j", "type": "int"}],
                "returns": [{"name": "r", "type": "int"}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    if shape == "extreme_row":
        kind = rng.choice(["max", "min"])
        wide, narrow = (">", "<=") if kind == "max" else ("<", ">=")
        body = [ASG("r", OP("len", AT("m", I(0)))), LOC("i", "int", I(1)),
               WH_DF(OP("<", V("i"), LEN("m")),
                  [FA("j", I(0), V("i"),
                      OP(narrow, OP("len", AT("m", V("j"))), V("r"))),
                   EX("j", I(0), V("i"),
                      OP("==", OP("len", AT("m", V("j"))), V("r"))),
                   AND(OP(">=", V("i"), I(1)), OP("<=", V("i"), LEN("m")))],
                  OP("-", LEN("m"), V("i")),
                  [IFS(OP(wide, OP("len", AT("m", V("i"))), V("r")),
                       [ASG("r", OP("len", AT("m", V("i"))))], []),
                   ASG("i", OP("+", V("i"), I(1)))])]
        ens = [FA("k", I(0), LEN("m"),
                  OP(narrow, OP("len", AT("m", V("k"))), V("r"))),
              EX("k", I(0), LEN("m"),
                 OP("==", OP("len", AT("m", V("k"))), V("r")))]
        return {"t": 1, "name": me, "gate": "loops",
                "params": [{"name": "m", "type": NEST_T}],
                "returns": [{"name": "r", "type": "int"}],
                "requires": [OP(">", LEN("m"), I(0))],
                "ensures": ens, "body": body, "_shape": f"extreme_row_{kind}"}

    if shape == "row_swap_update":
        op_kind = rng.choice(["swap", "update"])
        if op_kind == "swap":
            body = [ASG("r", OP("update",
                               OP("update", V("m"), V("i"), AT("m", V("j"))),
                               V("j"), AT("m", V("i"))))]
            ens = [OP("==", LEN("r"), LEN("m")),
                  OP("==", AT("r", V("i")), AT("m", V("j"))),
                  OP("==", AT("r", V("j")), AT("m", V("i"))),
                  FA("k", I(0), LEN("m"),
                     OP("implies",
                        AND(OP("!=", V("k"), V("i")), OP("!=", V("k"), V("j"))),
                        OP("==", AT("r", V("k")), AT("m", V("k")))))]
            req = [AND(OP("<=", I(0), V("i")), OP("<", V("i"), LEN("m"))),
                  AND(OP("<=", I(0), V("j")), OP("<", V("j"), LEN("m")))]
            return {"t": 1, "name": me, "gate": "quantifiers",
                    "params": [{"name": "m", "type": NEST_T},
                              {"name": "i", "type": "int"},
                              {"name": "j", "type": "int"}],
                    "returns": [{"name": "r", "type": NEST_T}],
                    "requires": req, "ensures": ens, "body": body,
                    "_shape": "row_swap"}
        body = [ASG("r", OP("update", V("m"), V("i"), V("u")))]
        ens = [OP("==", LEN("r"), LEN("m")),
              OP("==", AT("r", V("i")), V("u")),
              FA("k", I(0), LEN("m"),
                 OP("implies", OP("!=", V("k"), V("i")),
                    OP("==", AT("r", V("k")), AT("m", V("k")))))]
        return {"t": 1, "name": me, "gate": "quantifiers",
                "params": [{"name": "m", "type": NEST_T},
                          {"name": "i", "type": "int"},
                          {"name": "u", "type": "seq"}],
                "returns": [{"name": "r", "type": NEST_T}],
                "requires": [AND(OP("<=", I(0), V("i")), OP("<", V("i"), LEN("m")))],
                "ensures": ens, "body": body, "_shape": "row_update"}

    if shape == "concat_nested":
        body = [ASG("r", CAT(V("m"), V("n")))]
        ens = [OP("==", LEN("r"), OP("+", LEN("m"), LEN("n"))),
              FA("k", I(0), LEN("m"), OP("==", AT("r", V("k")), AT("m", V("k")))),
              FA("k", I(0), LEN("n"),
                 OP("==", AT("r", OP("+", V("k"), LEN("m"))), AT("n", V("k"))))]
        return {"t": 1, "name": me, "gate": "quantifiers",
                "params": [{"name": "m", "type": NEST_T},
                          {"name": "n", "type": NEST_T}],
                "returns": [{"name": "r", "type": NEST_T}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    if shape == "slice_rows":
        body = [ASG("r", SLICE("m", V("a"), V("b")))]
        ens = [OP("==", LEN("r"), OP("-", V("b"), V("a"))),
              FA("k", I(0), LEN("r"),
                 OP("==", AT("r", V("k")), AT("m", OP("+", V("a"), V("k")))))]
        return {"t": 1, "name": me, "gate": "quantifiers",
                "params": [{"name": "m", "type": NEST_T},
                          {"name": "a", "type": "int"},
                          {"name": "b", "type": "int"}],
                "returns": [{"name": "r", "type": NEST_T}],
                "requires": [AND(OP("<=", I(0), V("a")),
                                OP("<=", V("a"), V("b")),
                                OP("<=", V("b"), LEN("m")))],
                "ensures": ens, "body": body, "_shape": shape}

    if shape == "eq_nested":
        body = [ASG("r", OP("==", V("m"), V("n")))]
        ens = [OP("==", V("r"),
                  AND(OP("==", LEN("m"), LEN("n")),
                     FA("k", I(0), LEN("m"),
                        OP("==", AT("m", V("k")), AT("n", V("k"))))))]
        return {"t": 1, "name": me, "gate": "quantifiers",
                "params": [{"name": "m", "type": NEST_T},
                          {"name": "n", "type": NEST_T}],
                "returns": [{"name": "r", "type": "bool"}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    # row_sum: r == the sum of row m[ri]'s elements, ri a parameter. The
    # body accumulates it with a real loop; the ensures states the exact
    # value through a recursive GHOST spec_fun (never called from the
    # body -- f_v1rec's own body/spec_fun split, since not every lowering
    # treats a spec_fun as executable).
    sf = {"name": "rowsum",
         "params": [{"name": "row", "type": "seq"}, {"name": "k", "type": "int"}],
         "result": "int", "decreases": V("k"),
         "body": ITE(OP("<=", V("k"), I(0)), I(0),
                     OP("+", CALL("rowsum", V("row"), OP("-", V("k"), I(1))),
                        AT("row", OP("-", V("k"), I(1)))))}
    body = [LOC("row", "seq", AT("m", V("ri"))),
           LOC("total", "int", I(0)), LOC("k", "int", I(0)),
           WH_DF(OP("<", V("k"), LEN("row")),
              [OP("==", V("total"), CALL("rowsum", V("row"), V("k"))),
               AND(OP(">=", V("k"), I(0)), OP("<=", V("k"), LEN("row")))],
              OP("-", LEN("row"), V("k")),
              [ASG("total", OP("+", V("total"), AT("row", V("k")))),
               ASG("k", OP("+", V("k"), I(1)))]),
           ASG("r", V("total"))]
    ens = [OP("==", V("r"),
              CALL("rowsum", AT("m", V("ri")), OP("len", AT("m", V("ri")))))]
    return {"t": 1, "name": me, "gate": "recursion",
            "params": [{"name": "m", "type": NEST_T},
                      {"name": "ri", "type": "int"}],
            "returns": [{"name": "r", "type": "int"}],
            "requires": [AND(OP("<=", I(0), V("ri")), OP("<", V("ri"), LEN("m")))],
            "ensures": ens, "spec_funs": [sf], "body": body,
            "_shape": "row_sum"}


def f_v1strlib(rng, idx):
    """SPEC.md "The string library (v1)" (2026-09-11): 17 polymorphic seq
    operators over COVERAGE-string-lib.md's own census (the nl/ greedy
    order: split, str(), join, count, strip, replace, find, lower, upper,
    isdigit, isalpha). No new Expr forms and no new well-formedness case
    (`check_wf`'s `_ty` already types every member), so this family's job
    is the same as `f_v1nested`'s: coverage of the shapes that dominate,
    not new machinery. Eleven shapes; MEASURED 2026-09-11 (--n 400 --seed
    1, this file's own build_corpus loop restricted to this one family):
    unlike `f_v1nested`/`f_v1pairs`, this family's randomness is almost
    entirely in WHICH member/branch/parameter-name combination is chosen,
    not in an embedded integer literal (the census shapes below are laws
    over PARAMETERS, `s`, `c`, `a`, `b`, `n`, so two draws of the same
    shape/sub-variant are the same AST), so the build_corpus dedup key
    saturates fast: 16000 tries (the loop's own `n * 40` cap) produced
    only 17 distinct well-formed tasks, one per shape/sub-variant
    combination below (word_count 1, split_row 2, join_split_roundtrip 1,
    count_pattern 2, find_case 1, strip_len 3, replace_count 1, case_map
    2, startswith_endswith_slice 2, loop_count 1, tostr_len 1 = 17) --
    the same saturation already measured for `f_v1seqops` (29 of 16000)
    and `f_v1divmod` (16 of 16000), neither of which embeds a per-task
    literal either; `f_v1nested`/`f_v1pairs` reach 400 because their
    shapes embed an `rng.choice` CONSTANT (a row count, a swap-vs-update
    pick with a fresh index) directly into the tree. All 17 pass
    `ground_truth` at "verified" (no generator bug: every real body
    satisfies its own ensures over 260 sampled inputs) and all 17 got a
    twin from `harness.make_twin` -- op by shape, this run:

      word_count     `len(t2.split())` over a full-length SLICE `t2 :=
                     s[0..len(s)]` standing in for a loop-free body's own
                     copy of `s` -- `word_count.json`'s own committed
                     shape, generalized: the slice's `0` lower bound is
                     the only body-level literal. Measured: OFF-BY-ONE.
      split_row      two variants: `len` states SPEC.md's own identity
                     `len(s.split(c)) == s.count([c]) + 1` over a decoy
                     slice copy of `s` (measured: OFF-BY-ONE on the slice
                     bound); `index` reads `rows[0]` under an `if
                     len(rows) > 0` guard, the definedness obligation
                     `split`'s result carries stated explicitly rather
                     than assumed, `rows` a body-local so the ensures
                     restates `split(s, c)` directly (a body-local is
                     invisible to `ensures`, params-and-return only)
                     (measured: NEGATE-COND).
      join_split_roundtrip  the law `[c].join(s.split(c)) == s`, the
                     body rebuilding `s` with a decoy `trimmed :=
                     s.strip()` local also in scope but unused --
                     `split_join.json`'s own committed shape, generalized:
                     WRONG-VAR swaps `s` for `trimmed` inside the
                     `split` call, the committed task's own measured
                     twin. Measured: WRONG-VAR.
      count_pattern  `s.count(t)` over a decoy slice copy, `t` one code
                     point or `rng.choice` a two-code-point literal (the
                     census's `count(lit)` / `count(lit,n)` forms).
                     Measured: OFF-BY-ONE on the slice bound, both forms.
      find_case      `s.find([c])`, the `-1` case in SPEC.md's own words
                     stated as an `if idx == -1 then 0 else idx + 1`
                     (1-based-or-zero, so the two branches are both
                     reachable and distinguishable). Measured:
                     COLLAPSE-IF.
      strip_len      `len(s.strip())` (`rng.choice` also `lstrip`,
                     `rstrip`) over a decoy slice copy; the census's own
                     `strip()` / `rstrip()` top forms. Measured:
                     OFF-BY-ONE on the slice bound, all three members.
      replace_count  `s.replace([a], [b]).count([b]) == s.count([b]) +
                     s.count([a])` under `requires a != b`: a single-
                     code-point pattern's count is a positional tally, so
                     replacing every `a` with `b` (they differ) shifts
                     that tally exactly -- no decoy needed. Measured:
                     WRONG-VAR, swapping `a` for `b` inside the `replace`
                     call directly.
      case_map       `lower`/`upper` over a decoy slice copy, with
                     `s.isalpha() implies r.isupper()` (or `islower`) in
                     the ensures: SPEC.md's own predicate stated as a
                     consequence of the map rather than restated as an
                     independent fact. Measured: OFF-BY-ONE on the slice
                     bound, both members.
      startswith_endswith_slice  `s.startswith(s[0..n])` (or the
                     `endswith` mirror, `s[len(s)-n..len(s)]`), always
                     true by construction -- no decoy needed, the slice
                     bound `0`/`n`/`len(s)-n` is itself the target.
                     Measured: OFF-BY-ONE, both members.
      loop_count     a `while` loop over code points, invariant `r ==
                     s[0..i].count([c])`, ensures `r == s.count([c])` --
                     `count_vowels.json`'s own committed shape with one
                     code point instead of five. Measured: INVARIANT-DROP
                     on the running-tally invariant, the load-bearing
                     rung.
      tostr_len      `tostr(n + 0)` (the `+ 0` a decoy OFF-BY-ONE target,
                     `word_count`'s slice trick without a seq): `len(r)
                     >= 1` always, `n < 0 implies r[0] == 45` ('-') per
                     SPEC.md's own words. Measured: OFF-BY-ONE, but
                     TAGGED `+nonrefuting` (harness.py's fallback rung):
                     `n + 1` vs `n` changes `tostr`'s VALUE but the
                     ensures is too weak to be FALSIFIED by the shift on
                     the witness found, so this is the one shape
                     in the family whose ensures under-specifies `tostr`
                     against its own twin ladder -- measured, not fixed,
                     since SPEC.md's `tostr` clause is a length-and-sign
                     fact only, not a full digit-string characterization.

    Twins go through the GROUNDED ladder (harness.make_twin/twin_cached),
    same as every other family; no member-specific twin move exists
    (SPEC.md: "Twin operators apply to a member's arguments as to any
    expression; no member-specific twin exists in v1"), so the existing
    eight rungs see a string-lib call exactly as they see any other
    `OP`/`AT`/`SLICE` node -- no ladder change was needed for this family,
    the same "no new machinery" property the core landing gave `_ty`/`ev`.
    Lowering to the seven kernels is NOT attempted here: none of the seven
    `lower_*.py` files has a string-lib case yet (SPEC.md names this as
    the wave's own open work), so `run()`'s per-cell `abstain`/`lower-
    error` catch would fire on every cell; the family is exercised through
    the reference interpreter and the twin ladder only until a kernel
    lowers a member."""
    me = f"fz_v1strlib_{idx:03d}"
    shape = rng.choice(["word_count", "split_row", "join_split_roundtrip",
                        "count_pattern", "find_case", "strip_len",
                        "replace_count", "case_map",
                        "startswith_endswith_slice", "loop_count",
                        "tostr_len"])

    if shape == "word_count":
        body = [LOC("t2", "seq", SLICE("s", I(0), LEN("s"))),
               ASG("r", OP("len", OP("split", V("t2"))))]
        ens = [OP("==", V("r"), OP("len", OP("split", V("s"))))]
        return {"t": 1, "name": me,
                "params": [{"name": "s", "type": "seq"}],
                "returns": [{"name": "r", "type": "int"}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    if shape == "split_row":
        variant = rng.choice(["len", "index"])
        if variant == "len":
            body = [LOC("t2", "seq", SLICE("s", I(0), LEN("s"))),
                   ASG("rows", OP("split", V("t2"), V("c")))]
            ens = [OP("==", OP("len", V("rows")),
                      OP("+", OP("count", V("s"), SEQ(V("c"))), I(1)))]
            return {"t": 1, "name": me,
                    "params": [{"name": "s", "type": "seq"},
                              {"name": "c", "type": "int"}],
                    "returns": [{"name": "rows", "type": NEST_T}],
                    "requires": [], "ensures": ens, "body": body,
                    "_shape": "split_row_len"}
        splitexpr = OP("split", V("s"), V("c"))
        body = [LOC("rows", NEST_T, splitexpr),
               IFS(OP(">", OP("len", V("rows")), I(0)),
                   [ASG("r", AT("rows", I(0)))], [ASG("r", SEQ())])]
        # `rows` is a body-local, invisible to `ensures` (SPEC.md's own
        # ensures/requires environment is params + return only), so the
        # ensures restates `split(s, c)` directly rather than naming it.
        ens = [OP("implies", OP(">", OP("len", splitexpr), I(0)),
                  OP("==", V("r"), OP("at", splitexpr, I(0)))),
              OP("implies", OP("==", OP("len", splitexpr), I(0)),
                  OP("==", LEN("r"), I(0)))]
        return {"t": 1, "name": me,
                "params": [{"name": "s", "type": "seq"},
                          {"name": "c", "type": "int"}],
                "returns": [{"name": "r", "type": "seq"}],
                "requires": [], "ensures": ens, "body": body,
                "_shape": "split_row_index"}

    if shape == "join_split_roundtrip":
        body = [LOC("trimmed", "seq", OP("strip", V("s"))),
               LOC("rows", NEST_T, OP("split", V("s"), V("c"))),
               ASG("r", OP("join", V("rows"), SEQ(V("c"))))]
        ens = [OP("==", V("r"), V("s"))]
        return {"t": 1, "name": me,
                "params": [{"name": "s", "type": "seq"},
                          {"name": "c", "type": "int"}],
                "returns": [{"name": "r", "type": "seq"}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    if shape == "count_pattern":
        two = rng.choice([True, False])
        pat = SEQ(V("c1"), V("c2")) if two else SEQ(V("c1"))
        params = [{"name": "s", "type": "seq"}, {"name": "c1", "type": "int"}]
        if two:
            params.append({"name": "c2", "type": "int"})
        body = [LOC("t2", "seq", SLICE("s", I(0), LEN("s"))),
               ASG("r", OP("count", V("t2"), pat))]
        ens = [OP("==", V("r"), OP("count", V("s"), pat)),
              OP(">=", V("r"), I(0))]
        return {"t": 1, "name": me, "params": params,
                "returns": [{"name": "r", "type": "int"}],
                "requires": [], "ensures": ens, "body": body,
                "_shape": "count_two" if two else "count_one"}

    if shape == "find_case":
        body = [LOC("idx", "int", OP("find", V("s"), SEQ(V("c")))),
               IFS(OP("==", V("idx"), I(-1)), [ASG("r", I(0))],
                   [ASG("r", OP("+", V("idx"), I(1)))])]
        ens = [OP("implies", OP("==", V("r"), I(0)),
                  FA("k", I(0), LEN("s"), OP("!=", AT("s", V("k")), V("c")))),
              OP("implies", OP(">", V("r"), I(0)),
                  AND(OP("==", AT("s", OP("-", V("r"), I(1))), V("c")),
                     FA("k", I(0), OP("-", V("r"), I(1)),
                        OP("!=", AT("s", V("k")), V("c")))))]
        return {"t": 1, "name": me, "gate": "quantifiers",
                "params": [{"name": "s", "type": "seq"},
                          {"name": "c", "type": "int"}],
                "returns": [{"name": "r", "type": "int"}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    if shape == "strip_len":
        kind = rng.choice(["strip", "lstrip", "rstrip"])
        body = [LOC("t2", "seq", SLICE("s", I(0), LEN("s"))),
               LOC("u", "seq", OP(kind, V("t2"))),
               ASG("r", OP("len", V("u")))]
        ens = [OP("<=", V("r"), LEN("s")), OP(">=", V("r"), I(0)),
              OP("implies", OP("==", LEN("s"), I(0)), OP("==", V("r"), I(0)))]
        return {"t": 1, "name": me,
                "params": [{"name": "s", "type": "seq"}],
                "returns": [{"name": "r", "type": "int"}],
                "requires": [], "ensures": ens, "body": body,
                "_shape": f"strip_len_{kind}"}

    if shape == "replace_count":
        body = [LOC("t2", "seq",
                   OP("replace", V("s"), SEQ(V("a")), SEQ(V("b")))),
               ASG("r", OP("count", V("t2"), SEQ(V("b"))))]
        ens = [OP("==", V("r"),
                  OP("+", OP("count", V("s"), SEQ(V("b"))),
                     OP("count", V("s"), SEQ(V("a")))))]
        return {"t": 1, "name": me,
                "params": [{"name": "s", "type": "seq"},
                          {"name": "a", "type": "int"},
                          {"name": "b", "type": "int"}],
                "returns": [{"name": "r", "type": "int"}],
                "requires": [OP("!=", V("a"), V("b"))],
                "ensures": ens, "body": body, "_shape": shape}

    if shape == "case_map":
        kind = rng.choice(["lower", "upper"])
        pred = "islower" if kind == "lower" else "isupper"
        body = [LOC("t2", "seq", SLICE("s", I(0), LEN("s"))),
               ASG("r", OP(kind, V("t2")))]
        ens = [OP("==", LEN("r"), LEN("s")),
              OP("implies", OP("isalpha", V("s")), OP(pred, V("r")))]
        return {"t": 1, "name": me,
                "params": [{"name": "s", "type": "seq"}],
                "returns": [{"name": "r", "type": "seq"}],
                "requires": [], "ensures": ens, "body": body,
                "_shape": f"case_map_{kind}"}

    if shape == "startswith_endswith_slice":
        kind = rng.choice(["startswith", "endswith"])
        if kind == "startswith":
            body = [ASG("r", OP("startswith", V("s"),
                               SLICE("s", I(0), V("n"))))]
        else:
            body = [ASG("r", OP("endswith", V("s"),
                               SLICE("s", OP("-", LEN("s"), V("n")),
                                    LEN("s"))))]
        ens = [OP("==", V("r"), BL(True))]
        req = [AND(OP(">=", V("n"), I(0)), OP("<=", V("n"), LEN("s")))]
        return {"t": 1, "name": me, "gate": "quantifiers",
                "params": [{"name": "s", "type": "seq"},
                          {"name": "n", "type": "int"}],
                "returns": [{"name": "r", "type": "bool"}],
                "requires": req, "ensures": ens, "body": body,
                "_shape": f"{kind}_slice"}

    if shape == "loop_count":
        body = [ASG("r", I(0)), LOC("i", "int", I(0)),
               WH_DF(OP("<", V("i"), LEN("s")),
                  [OP("==", V("r"),
                      OP("count", SLICE("s", I(0), V("i")), SEQ(V("c")))),
                   AND(OP(">=", V("i"), I(0)), OP("<=", V("i"), LEN("s")))],
                  OP("-", LEN("s"), V("i")),
                  [IFS(OP("==", AT("s", V("i")), V("c")),
                       [ASG("r", OP("+", V("r"), I(1)))], []),
                   ASG("i", OP("+", V("i"), I(1)))])]
        ens = [OP("==", V("r"), OP("count", V("s"), SEQ(V("c"))))]
        return {"t": 1, "name": me, "gate": "loops",
                "params": [{"name": "s", "type": "seq"},
                          {"name": "c", "type": "int"}],
                "returns": [{"name": "r", "type": "int"}],
                "requires": [], "ensures": ens, "body": body, "_shape": shape}

    # tostr_len: len(tostr(n + 0)) >= 1 always, and a negative n's tostr
    # starts with '-' (45), SPEC.md's own words; the `+ 0` is a decoy
    # OFF-BY-ONE target, `word_count`'s slice trick without a seq.
    body = [LOC("t2", "int", OP("+", V("n"), I(0))),
           ASG("r", OP("tostr", V("t2")))]
    ens = [OP(">=", OP("len", V("r")), I(1)),
          OP("implies", OP("<", V("n"), I(0)), OP("==", AT("r", I(0)), I(45)))]
    return {"t": 1, "name": me,
            "params": [{"name": "n", "type": "int"}],
            "returns": [{"name": "r", "type": "seq"}],
            "requires": [], "ensures": ens, "body": body,
            "_shape": "tostr_len"}


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
    ("v1seqops", f_v1seqops, 4),
    ("v1pairs", f_v1pairs, 4),
    ("v1nested", f_v1nested, 4),
    ("v1strlib", f_v1strlib, 4),
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
        "vacuous",
        "`x / 0` has no value at any x, so `requires x / 0 == 0` is "
        "undefined at every type-correct input, not merely narrowed; the "
        "task is DEFECTIVE, the same class as fz_p_vac_unsat/fz_p_vac_range "
        "(a requires with no satisfying input, well-defined or not), and "
        "the real lowering must not VERIFY -- harness.twin_cached's own "
        "'vacuous-requires-undefined' refusal (ROADMAP 13.4, 2026-09-11) "
        "names it so before any kernel is asked; a kernel that lowers the "
        "real anyway (conformance.py's own no-twin-still-lowers path) must "
        "read it VACUOUS, exactly as the analogous `at` probe SPEC.md "
        "records under 'Undefined requires'", adversarial=True)

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

    # --- SPEC.md "Sequences: literals, concatenation, slices (v1)"
    # (2026-09-09): `slice` is DEFINED IFF 0 <= a <= b <= len(s), the same
    # partiality shape as `at`/`update`, and a requires that fails to
    # exclude the bad bound lets an undefined slice through, exactly as
    # fz_p_upd_oob and fz_p_fill_neg do for `update` and `fill`.
    add({"t": 1, "name": "fz_p_slice_oob", "gate": "quantifiers",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "seq"}],
         "requires": [],
         "ensures": [OP("==", LEN("r"), OP("+", LEN("s"), I(1)))],
         "body": [ASG("r", SLICE("s", I(0), OP("+", LEN("s"), I(1))))]},
        "refuted",
        "s[0..len(s)+1] has no value at any length, unguarded by any "
        "requires; ground_truth's kind is undefined-body, which the "
        "verdict rule reports as refuted, the file's convention for an "
        "ill-defined real body, exactly as fz_p_upd_oob's totalized "
        "`update` reads refuted rather than a distinct outcome",
        adversarial=True)
    add({"t": 1, "name": "fz_p_slice_rev", "gate": "quantifiers",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "seq"}],
         "requires": [],
         "ensures": [OP("==", LEN("r"), I(0))],
         "body": [ASG("r", SLICE("s", I(3), I(1)))]},
        "refuted",
        "s[3..1] violates 0 <= a <= b at every input regardless of len(s) "
        "(3 <= 1 is false unconditionally), so the body has no value on "
        "the whole domain; reported refuted for the same reason "
        "fz_p_slice_oob is",
        adversarial=True)

    # --- SPEC.md "Sequences: literals, concatenation, slices (v1)": the
    # empty literal and the concatenation identity `[] + s == s`, element-
    # wise (never the whole-seq `==` fz_p_seqeq_* already measures).
    add({"t": 1, "name": "fz_p_lit_empty", "gate": "quantifiers",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "seq"}],
         "requires": [],
         "ensures": [OP("==", OP("len", SEQ()), I(0)),
                     OP("==", LEN("r"), LEN("s")),
                     FA("k", I(0), LEN("s"),
                        OP("==", AT("r", V("k")), AT("s", V("k"))))],
         "body": [ASG("r", CAT(SEQ(), V("s")))]},
        "verified",
        "len([]) == 0 by SPEC.md's literal rule, and [] + s == s "
        "element-wise since concatenation's k-th element is s[k] once "
        "len([]) == 0 shifts every index by nothing")

    # --- `+` on two seqs: length is additive, the property `concat_params`
    # (f_v1seqops) states element-wise; here as a direct arithmetic fact,
    # no loop and no `at`.
    add({"t": 1, "name": "fz_p_concat_len", "gate": "quantifiers",
         # `u`, not `t`: `t` is the surface syntax's own format-version
         # keyword and has no notation as a parameter name.
         "params": [{"name": "s", "type": "seq"}, {"name": "u", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [OP("==", V("r"), OP("+", LEN("s"), LEN("u")))],
         "body": [ASG("r", OP("len", CAT(V("s"), V("u"))))]},
        "verified",
        "len(s + u) == len(s) + len(u) by SPEC.md's concatenation rule, "
        "for any two seqs, no requires needed since `+` on two seqs is "
        "always defined")

    # --- The literal indexed directly, no parameter and no loop: SPEC.md's
    # `seq` denotes the sequence whose k-th element is the k-th argument.
    add({"t": 1, "name": "fz_p_lit_index",
         "params": [],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [OP("==", V("r"), I(5))],
         "body": [ASG("r", OP("at", SEQ(I(3), I(5), I(7)), I(1)))]},
        "verified",
        "[3, 5, 7][1] == 5 by SPEC.md's literal rule, the k-th argument "
        "at index k, with no parameter and no loop to obscure it")

    # --- SPEC.md "Pairs" (2026-09-10): `fst`/`snd` project, "fst((a, b))
    # == a and snd((a, b)) == b", quoted directly. No `if`, no loop, no int
    # literal and no other var of type int in scope for wrong-var to reach
    # BESIDES `a` and `b` themselves, so the only candidates the grounded
    # ladder can raise here are wrong-var's own two pair-specific moves
    # (swap the `pair` node's two args, or swap `fst` for `snd`) and the
    # ordinary var-for-var substitution of `a` for `b` (or the reverse);
    # measured, not assumed, whether any of those four actually witnesses a
    # difference the interpreter can find.
    add({"t": 1, "name": "fz_p_pair_proj",
         "params": [{"name": "a", "type": "int"}, {"name": "b", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [OP("==", V("r"), V("a"))],
         "body": [ASG("r", FST(PAIR(V("a"), V("b"))))]},
        "verified",
        "fst((a, b)) == a by SPEC.md's projection identity, quoted "
        "directly; expected no-twin, since every candidate the ladder can "
        "raise on this body is one of wrong-var's own moves",
        adversarial=False)

    # --- The swap the twin ladder names by name: "wrong-var swaps the two
    # components of a pair and swaps fst for snd in a projection". The
    # body here IS the swap (correct by construction, SPEC.md's own
    # identity read component-by-component); the un-swap wrong-var can
    # reach from it is the twin, refuted whenever the two components of p
    # differ.
    add({"t": 1, "name": "fz_p_pair_swap",
         "params": [{"name": "p", "type": {"pair": ["int", "int"]}}],
         "returns": [{"name": "r", "type": {"pair": ["int", "int"]}}],
         "requires": [],
         "ensures": [OP("==", FST(V("r")), SND(V("p"))),
                     OP("==", SND(V("r")), FST(V("p")))],
         "body": [ASG("r", PAIR(SND(V("p")), FST(V("p"))))]},
        "verified",
        "the body pairs (snd(p), fst(p)); the ensures restates exactly "
        "that, so this holds by construction, and wrong-var's un-swap "
        "move is expected to be REFUTED, false whenever the pair's two "
        "components differ")

    # --- Componentwise equality, stated explicitly rather than through
    # SPEC.md's own polymorphic `==` on two pairs (fam_pairs's `eq_params`
    # shape uses the polymorphic form; this probe spells out both
    # conjuncts so a single wrong-var substitution can flip ONE of them
    # without touching the other, "a twin that flips one component").
    add({"t": 1, "name": "fz_p_pair_eq",
         "params": [{"name": "p", "type": {"pair": ["int", "int"]}},
                   {"name": "q", "type": {"pair": ["int", "int"]}}],
         "returns": [{"name": "r", "type": "bool"}],
         "requires": [],
         "ensures": [OP("==", V("r"), OP("==", V("p"), V("q")))],
         "body": [ASG("r", AND(OP("==", FST(V("p")), FST(V("q"))),
                              OP("==", SND(V("p")), SND(V("q")))))]},
        "verified",
        "r is the AND of the two componentwise equalities, which is "
        "exactly SPEC.md's rule for `==` on two pairs of one type; "
        "wrong-var substituting p for q (or q for p) in ONE conjunct "
        "flips that component's check to a tautology, expected refuted "
        "whenever the pairs agree in the other component but disagree in "
        "the flipped one")

    # --- A seq component projected and indexed UNDER ITS OWN BOUND: the
    # bound is len(fst(p)), read off the very pair being indexed, not an
    # external parameter. The `if` guard is both conjuncts SPEC.md's `at`
    # needs (0 <= snd(p) and snd(p) < len(fst(p))); DROP-GUARD (SPEC.md
    # "The twins", rung 8) drops one of them, letting an out-of-range
    # index through to `at`, undefined there.
    _pg_guard = AND(OP("<=", I(0), SND(V("p"))),
                    OP("<", SND(V("p")), OP("len", FST(V("p")))))
    add({"t": 1, "name": "fz_p_pair_seq", "gate": "quantifiers",
         "params": [{"name": "p", "type": {"pair": ["seq", "int"]}}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [OP("implies", _pg_guard,
                        OP("==", V("r"), OP("at", FST(V("p")), SND(V("p"))))),
                     OP("implies", OP("not", _pg_guard),
                        OP("==", V("r"), I(0)))],
         "body": [IFS(_pg_guard,
                      [ASG("r", OP("at", FST(V("p")), SND(V("p"))))],
                      [ASG("r", I(0))])]},
        "verified",
        "the if/ensures case split matches exactly, so this holds by "
        "construction for every p; DROP-GUARD on either conjunct of the "
        "if condition lets an out-of-range snd(p) reach `at(fst(p), "
        "snd(p))`, undefined there, expected refuted (ground_truth's "
        "undefined-body kind)")

    # --- A projection of a pair whose component divides by a PARAMETER
    # (not the pair's own other component): fst(p) div y, undefined at
    # y == 0 exactly as SPEC.md "Division and modulo" states, guarded by a
    # real requires rather than left adversarially unguarded (contrast
    # gt_pair_illdef_div in truth_fuzz.py, the same shape WITHOUT the
    # guard, built to be ILLDEF on purpose).
    add({"t": 1, "name": "fz_p_pair_div",
         "params": [{"name": "p", "type": {"pair": ["int", "int"]}},
                   {"name": "y", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [OP("!=", V("y"), I(0))],
         "ensures": [OP("==", V("r"), OP("div", FST(V("p")), V("y")))],
         "body": [ASG("r", OP("div", FST(V("p")), V("y")))]},
        "verified",
        "r is the body's own expression, so r == fst(p) div y by "
        "reflexivity; requires y != 0 is exactly SPEC.md's `div` "
        "definedness obligation, so the body has a value at every "
        "admitted input despite the projection reaching an operator that "
        "is undefined at zero")

    # --- SPEC.md "Nested sequences (v1)" (2026-09-10): `s[i][j]` is
    # `at(at(s,i),j)`, defined iff BOTH indices are in range; the if/ensures
    # case split matches exactly, `fz_p_pair_seq`'s own idiom read over a
    # nested seq instead of a `(seq, int)` pair. Measured, not assumed:
    # COLLAPSE-IF (the ladder's first rung) already witnesses this shape
    # before DROP-GUARD is ever tried -- the unconditional `then` branch
    # reads at(m[i], j) with no guard at all, undefined whenever the guard
    # was actually false (e.g. m = [], i = j = 0, where the real body's
    # else branch is the one SPEC.md's semantics take).
    _ncg = AND(OP("<=", I(0), V("i")), OP("<", V("i"), LEN("m")),
              OP("<=", I(0), V("j")),
              OP("<", V("j"), OP("len", AT("m", V("i")))))
    add({"t": 1, "name": "fz_p_nest_cell", "gate": "quantifiers",
         "params": [{"name": "m", "type": {"seq": "seq"}},
                   {"name": "i", "type": "int"}, {"name": "j", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [OP("implies", _ncg,
                        OP("==", V("r"), OP("at", AT("m", V("i")), V("j")))),
                     OP("implies", OP("not", _ncg), OP("==", V("r"), I(0)))],
         "body": [IFS(_ncg, [ASG("r", OP("at", AT("m", V("i")), V("j")))],
                      [ASG("r", I(0))])]},
        "verified",
        "the if/ensures case split matches exactly; COLLAPSE-IF (the "
        "ladder's first rung) takes the unconditional then-branch, "
        "undefined at m = [], i = j = 0, where the real body's guard is "
        "false, expected refuted (ground_truth's undefined-body kind)")

    # --- `len(s[i])` under a row-length fact: SPEC.md's census idiom (Item
    # 5, DafnyBench: "a parameter consumed row by row under a single-binder
    # forall with a len(s[i]) fact"), here as a direct requires/ensures
    # restatement rather than a loop.
    add({"t": 1, "name": "fz_p_nest_rowlen", "gate": "quantifiers",
         "params": [{"name": "m", "type": {"seq": "seq"}},
                   {"name": "i", "type": "int"}, {"name": "L", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [AND(OP("<=", I(0), V("i")), OP("<", V("i"), LEN("m"))),
                     OP("==", OP("len", AT("m", V("i"))), V("L"))],
         "ensures": [OP("==", V("r"), V("L"))],
         "body": [ASG("r", OP("len", AT("m", V("i"))))]},
        "verified",
        "the body's own expression is len(m[i]); the requires' row-length "
        "fact pins it to L directly, so r == L holds by substitution, no "
        "loop needed")

    # --- The nested literal, indexed directly: `len([[1, 2], [3]]) == 2`
    # (SPEC.md's literal rule, one argument per row) and
    # `len([[1, 2], [3]][1]) == 1` (row 1 is [3]), both true by
    # construction, no parameter and no loop to obscure either.
    add({"t": 1, "name": "fz_p_nest_lit",
         "params": [], "returns": [{"name": "r", "type": "bool"}],
         "requires": [],
         "ensures": [OP("==", V("r"), BL(True))],
         "body": [ASG("r", AND(
             OP("==", OP("len", SEQ(SEQ(I(1), I(2)), SEQ(I(3)))), I(2)),
             OP("==", OP("len", OP("at", SEQ(SEQ(I(1), I(2)), SEQ(I(3))),
                                   I(1))), I(1))))]},
        "verified",
        "[[1, 2], [3]] has 2 rows and its row at index 1 is [3], length "
        "1; both hold with no parameter and no loop, true by "
        "construction")

    # --- Extensional equality of two nested PARAMETERS (SPEC.md "Nested
    # sequences": "two nested seqs are equal iff same length and equal
    # rows"), the ensures restating that rule componentwise rather than the
    # raw polymorphic `==` the body already computes; a twin flipping ONE
    # cell (wrong-var substituting m for n in one occurrence) is the
    # ladder's own candidate here, `f_v1pairs`'s `fz_p_pair_eq` one level
    # deeper.
    add({"t": 1, "name": "fz_p_nest_eq", "gate": "quantifiers",
         "params": [{"name": "m", "type": {"seq": "seq"}},
                   {"name": "n", "type": {"seq": "seq"}}],
         "returns": [{"name": "r", "type": "bool"}],
         "requires": [],
         "ensures": [OP("==", V("r"),
                        AND(OP("==", LEN("m"), LEN("n")),
                           FA("k", I(0), LEN("m"),
                              OP("==", AT("m", V("k")), AT("n", V("k"))))))],
         "body": [ASG("r", OP("==", V("m"), V("n")))]},
        "verified",
        "r is the body's own polymorphic == on two nested seqs; the "
        "ensures restates SPEC.md's rule that two nested seqs are equal "
        "iff same length and equal rows, one conjunct per row rather "
        "than the raw m == n the body already computes")

    # --- The empty nested literal at a declared slot: `[]` is ambiguous
    # between a plain seq and a seq<seq> with no rows (SPEC.md "Nested
    # sequences"), resolved by the `expect` hint at the assignment/return
    # site; r's declared type is seq<seq>, so `len([]) == 0` holds of the
    # empty NESTED seq specifically, not the plain one.
    add({"t": 1, "name": "fz_p_nest_empty",
         "params": [], "returns": [{"name": "r", "type": {"seq": "seq"}}],
         "requires": [],
         "ensures": [OP("==", LEN("r"), I(0))],
         "body": [ASG("r", SEQ())]},
        "verified",
        "SPEC.md 'Nested sequences': [] is ambiguous between a plain seq "
        "and a seq<seq> with no rows, resolved by the declared type at "
        "the assignment; r's declared type is seq<seq>, so the `expect` "
        "hint types [] as the empty nested seq, len 0")

    # --- SPEC.md "The string library (v1)": `split(s)`'s own stated edge
    # case, "split("") == []" verbatim, true by construction, no
    # parameter and no loop.
    add({"t": 1, "name": "fz_p_str_splitempty",
         "params": [], "returns": [{"name": "r", "type": {"seq": "seq"}}],
         "requires": [],
         "ensures": [OP("==", LEN("r"), I(0))],
         "body": [ASG("r", OP("split", SEQ()))]},
        "verified",
        "SPEC.md's own words: split(\"\") == []; the empty seq has no "
        "whitespace run to separate, so split returns the empty nested "
        "seq, len 0")

    # --- SPEC.md's own identity for `count`: "count(s, []) == len(s) + 1"
    # verbatim, general over a PARAMETER s, no loop: the empty pattern
    # occurs once before every element and once after, len(s) + 1 places.
    add({"t": 1, "name": "fz_p_str_countempty",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [OP("==", V("r"), OP("+", LEN("s"), I(1)))],
         "body": [ASG("r", OP("count", V("s"), SEQ()))]},
        "verified",
        "SPEC.md's own words: count(s, []) == len(s) + 1, general over "
        "any s; the empty pattern matches at every gap between elements "
        "plus both ends")

    # --- SPEC.md's own identity for `find`: "find(s, []) == 0" verbatim,
    # general over a PARAMETER s, no loop: the empty pattern is found at
    # the least index, 0, regardless of s's contents or length.
    add({"t": 1, "name": "fz_p_str_findempty",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [OP("==", V("r"), I(0))],
         "body": [ASG("r", OP("find", V("s"), SEQ()))]},
        "verified",
        "SPEC.md's own words: find(s, []) == 0, general over any s; the "
        "empty pattern occurs at index 0 of any seq")

    # --- The whitespace set, measured 2026-09-11 (test_strlib.py's parity
    # test against real Python): 9 (tab) is one of the 10 ASCII code
    # points, not one of the 6 an earlier draft of SPEC.md named, so a
    # literal [65, 9, 66] ('A', TAB, 'B') must split into two one-code-
    # point rows, ['A'] and ['B'], with the tab consumed as a separator
    # and no empty row on either side.
    add({"t": 1, "name": "fz_p_str_tab",
         "params": [], "returns": [{"name": "r", "type": "bool"}],
         "requires": [],
         "ensures": [OP("==", V("r"), BL(True))],
         "body": [LOC("rows", {"seq": "seq"},
                     OP("split", SEQ(I(65), I(9), I(66)))),
                  ASG("r", AND(OP("==", OP("len", V("rows")), I(2)),
                              OP("==", AT("rows", I(0)), SEQ(I(65))),
                              OP("==", AT("rows", I(1)), SEQ(I(66)))))]},
        "verified",
        "code point 9 (tab) is in SPEC.md's 10-point whitespace set "
        "(measured 2026-09-11, test_strlib.py, correcting an earlier "
        "6-point draft), so 'A' TAB 'B' splits into ['A'], ['B'], no "
        "empty row on either side")

    # --- SPEC.md's own words for `lower`/`upper`: "the ASCII letters ... "
    # every other code point unchanged". A literal spanning the gaps
    # around both letter ranges (32 space, 64 '@', 91 '[', 96 '`', 123
    # '{') plus one code point far outside ASCII (SPEC.md gives a
    # character no bound but 0..1114111, and the library's `lower` is
    # total on any int, per interp.py's own `_str_lower`), none of them a
    # letter, so `lower` must be the identity on the whole literal.
    add({"t": 1, "name": "fz_p_str_lowernonletter",
         "params": [], "returns": [{"name": "r", "type": "seq"}],
         "requires": [],
         "ensures": [OP("==", V("r"),
                        SEQ(I(32), I(64), I(91), I(96), I(123), I(1000000)))],
         "body": [ASG("r", OP("lower",
                             SEQ(I(32), I(64), I(91), I(96), I(123),
                                I(1000000))))]},
        "verified",
        "32, 64, 91, 96, 123 sit in the gaps just outside both ASCII "
        "letter ranges (65-90, 97-122) and 1000000 is far outside ASCII "
        "entirely; SPEC.md's own words say lower leaves every non-letter "
        "code point unchanged, so the literal is a fixed point")
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
        # The GROUNDED ladder (harness.twin_for, the one run_par grades
        # with), since 2026-09-09 night: the body-only rule knew only
        # collapse-if and invariant-drop, so every loop-free, if-free
        # shape (a slice, a concatenation, a literal) was dropped here
        # before any kernel saw it, measured on the v1seqops family: 19 of
        # 1000 kept, 0 of the five loop-free shapes. A task the ladder
        # cannot witness is refused, as the sweep refuses it.
        twin, op = harness.make_twin(task["body"], task)
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
            # The grounded ladder with its witness, as run_par grades
            # (2026-09-09 night): the body-only rule gave loop-free shapes
            # no twin at all and gave the lowerings no witness, so every
            # twin read unproved instead of refuted (measured on the
            # v1seqops family: 78 no-flip cells, 10 of 22 tasks no-twin).
            clean = {k: v for k, v in task.items() if not k.startswith("_")}
            try:
                twin_body, op, wit = harness.twin_cached(clean)
            except Exception as e:                           # noqa: BLE001
                # The reference interpreter refused the task outright (the
                # adversarial probe fz_p_nodiv carries a bare `/`, which is
                # not a t operator; found 2026-09-10 by the first full
                # all-families run, every earlier run having used --tasks).
                # The probe's whole point is the LOWERING's own rejection,
                # so the real is lowered alone: a lowering that raises reads
                # lower-error (the probe's expected class), one that
                # abstains reads abstain, and one that ACCEPTS the token
                # reads no-twin with the interpreter's reason, which the
                # probe's expectation then flags.
                try:
                    lower(clean, task["body"])
                except NotImplementedError as e2:
                    rows[name][bname] = ("abstain", str(e2)[:120], True, 0)
                    continue
                except Exception as e2:                      # noqa: BLE001
                    rows[name][bname] = ("lower-error",
                                         f"{type(e2).__name__}: {e2}"[:120],
                                         True, 0)
                    continue
                rows[name][bname] = ("no-twin", f"interp: {e}"[:120], True, 0)
                continue
            if twin_body is None:
                rows[name][bname] = ("no-twin", "no-twin", True, 0)
                continue
            try:
                rs = lower(clean, task["body"])
                ts = lower(clean, twin_body, witness=wit)
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
    lowering, or contradicts the reference interpreter.

    SPEC.md "The twins", 2026-09-11 paragraph (ROADMAP 13.3): a real-
    VERIFIED, twin-VERIFIED cell (still gathered under "twin_survived", the
    pre-existing per-task summary) is ALSO split, per cell, into
    "decorative" or "unsound" (harness.decorative_kind, keyed off the same
    witness twin_for already measured) and is never counted under
    "no_flip" any more: no_flip is now real-VERIFIED cells whose twin came
    back UNPROVED, TIMEOUT or MALFORMED, the kernel's own twin discipline,
    not the fuzzer's spec strength. Before this split, a decorative
    `ensures true` and a kernel's own unsoundness both landed in the same
    no_flip bucket as an UNPROVED twin, so the statistic could not tell
    "this spec is too weak to measure" from "this kernel stopped
    refuting"."""
    out = {"disagreements": [], "twin_survived": [], "vs_truth": [],
           "no_flip": [], "decorative": [], "unsound": []}
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
        # not REFUTED is recorded here, with the outcome that replaced it,
        # EXCEPT a twin that came back VERIFIED too (see the docstring
        # above): that cell is decorative or unsound, not a no-flip.
        w = None
        if surv:
            clean = {k: v for k, v in task.items() if not k.startswith("_")}
            try:
                _, _, w = harness.twin_cached(clean)
            except Exception:                                # noqa: BLE001
                w = None
        for b, c in cells.items():
            if c[0] == Outcome.VERIFIED and c[1] == Outcome.VERIFIED:
                kind = harness.decorative_kind(c[0], c[1], w) or "decorative"
                out[kind].append(
                    {"task": name, "family": task.get("_family"),
                     "op": task.get("_twin_op"), "backend": b,
                     "witness": harness.witness(w)})
                continue
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
    dec = {}
    for d in res["decorative"]:
        dec.setdefault(d["backend"], []).append(d["task"])
    uns = {}
    for d in res["unsound"]:
        uns.setdefault(d["backend"], []).append(d["task"])
    print(f"\ndisagreements: {len(res['disagreements'])}  "
          f"vs-truth: {len(res['vs_truth'])}  "
          f"twin-survived: {len(res['twin_survived'])}  "
          f"no-flip: {len(res['no_flip'])}  "
          f"decorative: {len(res['decorative'])}  "
          f"unsound: {len(res['unsound'])}")
    for b in sorted(nf):
        c = {o: nf[b].count(o) for o in sorted(set(nf[b]))}
        print(f"  NO-FLIP {b}: {len(nf[b])} real-VERIFIED cells whose twin "
              f"was UNPROVED, TIMEOUT or MALFORMED (the kernel's own twin "
              f"discipline, SPEC.md \"The twins\" 2026-09-11): {c}")
    for b in sorted(dec):
        print(f"  DECORATIVE {b}: {len(dec[b])} real-VERIFIED, twin-VERIFIED "
              f"cells where the ladder's own witness did not entail a "
              f"refutation (the spec cannot tell real and twin apart): "
              f"{dec[b]}")
    for b in sorted(uns):
        print(f"  UNSOUND {b}: {len(uns[b])} real-VERIFIED, twin-VERIFIED "
              f"cells where the ladder's witness DID entail a refutation "
              f"and the kernel verified the twin anyway: {uns[b]}")
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
