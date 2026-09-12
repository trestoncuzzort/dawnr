"""t/interp.py: a reference interpreter for a t body over a FIXED bounded
input domain, and the witness search that makes a twin a measurement.

Why this file exists, measured: over 1395 tasks from fuzz_lower.py's
generator (7 seeds x 200, less the 5 its own well-formedness check rejects),
129 twins, 9.2% and 13 to 22 per seed, compute the same value as the real
body on every input the fuzzer sampled. On those tasks the twin is not a broken
program, so a REFUTED verdict is luck and a VERIFIED one cannot be told apart
from a vacuous spec.
harness.make_twin therefore accepts a mutation only with a WITNESS produced
here: an input where real and twin disagree (the value-changing operators) or
a loop state the surviving invariants no longer cover (INVARIANT-DROP, whose
mutation is to the proof and not to the computed value).

Not shared with fuzz_lower.py's interpreter: that module imports harness and
harness imports this one, so importing it back would be a cycle. What that
duplication is worth was OVER-STATED here until 2026-09-01, and the
correction matters because this file is being promoted to ground-truth
oracle: fuzz_lower.ev is a CLONE of `ev` below, not an independent reading of
SPEC.md: same dispatch order, same short-circuit idioms, same `not (0 <= i
< len(s))` guard, same forall accumulator; the diff is `args` renamed to `a`
plus formatting. Agreement between the two is therefore evidence of faithful
copying and NOT evidence against a shared misconception, which is exactly the
failure ROADMAP.md 10.1 exists to catch. The real independent check is
described under "Validation" below. One deliberate divergence from
fuzz_lower, stated because it is a semantic choice and not an accident: a
self-call inside a TWIN body resolves to the twin (SPEC.md gate 3, the
self-call denotes the task's own function, and in the twin lowering that
function is the twin), where fuzz_lower.twin_semantics resolves it to the
real body.

VALIDATION (2026-09-01, the oracle-validation wave). Three arms, because a
bounded search is a sound proof of FALSITY and never of TRUTH:
  - against SPEC.md by reading, clause by clause (see the citations inline);
  - against a from-scratch re-implementation written in a deliberately
    different style (option-typed definedness instead of exceptions,
    closure-compiled expressions, immutable state-passing): 263 664
    (task, input) triples over 248 tasks, the 11 committed plus 3 seeds of
    the generator, with 0 disagreements on value, on `requires` and on
    `ensures`, compared TYPE-AWARE so True and 1 do not pass for each other.
    That comparison was itself mutation-tested: ten seeded misconceptions
    (32-bit wraparound; `at` totalized three ways; non-short-circuit and /
    implies / ite; a short-circuiting forall; a closed quantifier range; an
    unassigned return reading 0) were all caught, so "0 disagreements" is a
    measurement and not a blind spot;
  - against all seven kernels on 20 probes whose verdict SPEC.md's text
    entails: no kernel VERIFIED any probe this file calls FALSE or
    UNDEFINED, and on 16 generated tasks where this file exhibits a concrete
    counterexample, dafny, verus, lean and rocq REFUTED all 16, 64 of 64
    cells. Every remaining disagreement ran the other way (this file says
    TRUE, a kernel says REFUTED) and every one of those diagnosed to the
    kernel side: a tactic or SMT call that could not discharge a true goal,
    reported as REFUTED rather than as incompleteness. That direction is
    ROADMAP.md 10.1's taxonomy bug, and it is why a kernel's REFUTED can
    never be used to correct this file.

The domain is enumerated, never sampled: the same task always yields the same
witness, because harness.make_twin's selection must stay deterministic and
content-derived like the operators it chooses between.

2026-09-11 (SPEC.md "The string library (v1)"): the 17 members (split,
join, tostr, count, find, strip, lstrip, rstrip, replace, lower, upper,
isdigit, isalpha, isupper, islower, startswith, endswith) landed here as
direct int-tuple transcriptions of Python's own str methods, not a
`chr()`-then-back call as first suggested: measured on the seq witness
ladder (`ladders()` below), a `chr()` implementation raises Python's own
ValueError (an escaping crash, not `Undef`) the first time the ladder's
existing small-negative alphabet entries (-1, -2, -3) reach a string-lib
op, since a code point is only ever 0..1114111 and `chr(-1)` is not one;
the int-tuple version is total on any int instead, matching SPEC.md's
"each total ... the library adds no undefined case". The witness alphabet
(`ALPHA`, `STR_ALPHA`) was widened from 8 to 13 entries, adding space,
'a', 'e', 'A', '0', so split has a whitespace run to separate on and
isdigit/isalpha/isupper/islower each see at least one witness that holds
and one that does not; without it every string-lib predicate was constant
(always False) across the whole witness domain of small ints. `word_count`,
`split_join` and `count_vowels` (tasks/) were run through
harness.twin_cached to get a measured twin and witness, which corrected
SPEC.md's three predicted twins to what the ladder actually finds.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

# Per-input caps. An input that exceeds one is DISCARDED (no verdict), never
# counted as agreement: a twin that merely runs out of budget has not been
# shown to compute the same value.
MAX_STEPS = 60_000
MAX_LOOP = 2_000
MAX_DEPTH = 40
MAX_RANGE = 5_000
MAX_BITS = 4096          # magnitude of any int an arithmetic op produces.
                         # Measured 2026-09-06 on DafnyBench mockExam2_p6,
                         # f(n) = n + f(n-1)*f(n-2): values grow doubly
                         # exponentially, the step cap never fires, and one
                         # multiplication on a far domain point ran for over
                         # an hour. The largest value any of the 87
                         # committed and lifted tasks computes is 621 bits,
                         # and their Reference points are identical with
                         # and without the cap (measured 2026-09-06).

# Domain caps. Points are enumerated in shell order (below) so the small,
# witness-dense corner of the product comes first and the cap trims the
# far corner, not the near one.
MAX_POINTS = 2048        # inputs per (real, twin) comparison
MAX_STATES = 20_000      # loop states per INVARIANT-DROP check;
                         # 4096 left fz_v1scan_085's first
                         # invariant unmeasurable at arity 4
                         # (s, x, i, r), which silently moved
                         # the twin to the second invariant.


class Undef(Exception):
    """SPEC.md "Definedness": `at` outside [0, len) has no value, and neither
    does a read of a return name before its first assignment. Never a Python
    IndexError or a None that compares, either of which would be the totalization
    SPEC.md calls wrong.

    2026-09-12 (ROADMAP 13.4, the harness column): `expr` names the AST
    node ev() was evaluating at the moment it raised -- the offending
    sub-expression itself (an `at`, `slice`, `update`, `fill`, `div`/`mod`,
    or unbound/unassigned `var`), in evaluation order since ev() raises at
    the first one it reaches and never continues past it. None only for a
    call-site Undef that names no single expression (there is none such
    left below; kept optional so a future raise site need not thread one
    through). harness.real_witness reads it to build the ensures-level
    undefined witness's `_expr`."""
    def __init__(self, msg, expr=None):
        super().__init__(msg)
        self.expr = expr


class Budget(Exception):
    """A cap above was hit; this input decides nothing."""


class MeasureViolation(Exception):
    """ROADMAP 13.4, framac-measure, 2026-09-11: the well-foundedness
    obligation SPEC.md's `decreases` carries, caught as a ground fact
    instead of an infinite descent. Raised ONLY when the caller opted in
    (`St(check_measures=True)`, harness.real_witness's own scans; every
    other caller, including interp.Reference's, keeps St()'s default and
    never sees this), so no existing behaviour changes for a body whose
    measures are fine or whose caller never asked.

    Two sites raise it, both against the SAME rule -- "the callee's
    measure is not strictly below the caller's, or the caller's measure
    is negative":
      - a spec function call, from within evaluating another call to the
        SAME function (`ev`'s "call" case): `site` is the function's
        name, `args` the callee's concrete argument dict.
      - a `while` loop carrying a `decreases`, between two consecutive
        iterations that both entered the loop body (`exec_body`'s
        "while" case): `site` is the loop's AST node (`w["while"]`,
        identity-comparable against `harness.real_witness`'s own
        `_loop_index` helper), `args` is None (a loop variant is not
        indexed by a call's arguments; the concrete input that exposes it
        is the witness's own top-level env).

    `caller_measure`/`callee_measure` are the two ground integers the
    rule compares: for a recursive call, the enclosing frame's measure
    and this call's; for a loop, the previous iteration's variant and
    this one's (or, when there is no previous iteration, this one's own
    value, when it alone is negative)."""
    def __init__(self, site, call_args, caller_measure, callee_measure):
        super().__init__(f"measure {callee_measure} not below "
                         f"{caller_measure} at {site}")
        self.site = site
        # NOT `self.args`: that name is BaseException's own (a tuple,
        # used by its __repr__/traceback machinery), and this class's
        # `call_args` is a dict or None -- overwriting `args` corrupted
        # exception printing (measured: raising this crashed inside
        # __init__ itself, "'NoneType' object is not iterable", before
        # this rename).
        self.call_args = call_args
        self.caller_measure = caller_measure
        self.callee_measure = callee_measure


@dataclass(frozen=True)
class Pair:
    """SPEC.md "Pairs" (2026-09-10): the runtime value of `{"op": "pair",
    "args": [a, b]}`. Kept OUT of Python's tuple on purpose: seqs are Python
    tuples (SPEC.md "Sequences as values"), and `_tv` below tags a value by
    `type(v).__name__` so a value witness can never mistake one t type for
    another (gate 1's int/bool distinction is the same mechanism); a bare
    `(a, b)` tuple would collide with a length-2 seq under that tag, which is
    exactly the confusion `_tv` exists to rule out. `@dataclass(frozen=True)`
    gives a componentwise `__eq__` for free, which is `==`/`!=` on two pairs
    (SPEC.md: "the polymorphic `==` again, two ints, two bools, two seqs,
    two pairs") and never true against a tuple of the same two values since
    the generated `__eq__` first checks `other.__class__ is self.__class__`;
    and a hash derived from the same two fields, needed because the domain
    ladders below (`_ladder`) dedup pair values through a set. Pairs have no
    order (SPEC.md: "`< <= > >=` stay int-only"), so no `__lt__` etc. is
    defined, on purpose: check_wf refuses the syntax before a Pair would ever
    reach one."""
    a: object
    b: object


MAX_SEQ = 1 << 16          # fill length cap, the seq analogue of MAX_BITS


# ---------------------------------------------------------------------------
# SPEC.md "The string library (v1)" (2026-09-11): 17 polymorphic seq
# operators, semantics Python's own str methods on the code-point sequence.
# Measured 2026-09-11: a `chr()`/`str()`-then-back implementation, the
# strategy the wave's own instructions suggested, crashes with a Python
# ValueError on any element outside [0, 1114111] -- and t's `seq` type
# carries any int, so a witness search over the ordinary seq ladder (which
# includes small negatives, `_around`'s literal neighbours, and so on) WILL
# feed one to a string-lib op sooner or later; SPEC.md says these ops are
# "each total ... the library adds no undefined case", which a crash
# obviously violates. Every member below is instead worked directly on the
# tuple of ints, a transcription of what the matching Python str method
# does (checked member by member against CPython's own behaviour on ASCII
# input, which is what the corpus is and what the domain below is built
# from): this is total for ANY int, never calls chr(), and is byte-for-byte
# what `chr()`-then-Python-method would compute whenever every element
# genuinely is a code point. `lower`/`upper`/`isdigit`/`isalpha`/`isupper`/
# `islower` follow SPEC.md's explicit ASCII-only tables (65-90, 97-122,
# 48-57) rather than Python's own Unicode-aware casing, exactly as SPEC.md
# states ("the Unicode case tables are not in v1, by name") -- delegating
# to Python's real `str.lower()` etc. would in fact do MORE than SPEC.md
# describes for a non-ASCII code point, which is the one place "call
# Python's method" and "read SPEC.md's own words" would disagree.
# ---------------------------------------------------------------------------
_WS = (9, 10, 11, 12, 13, 28, 29, 30, 31, 32)     # SPEC.md's split/strip
                                  # text names "9, 10, 11, 12, 13, 32";
                                  # measured 2026-09-11 against real
                                  # Python (test_strlib.py's parity test,
                                  # ASCII domain) that Python's own
                                  # str.split()/str.isspace() also treat
                                  # 28-31 (FS/GS/RS/US) as whitespace in
                                  # ASCII, so a strict 6-point set is not
                                  # "Python's s.split()" as SPEC.md's
                                  # primary sentence names it; corrected
                                  # here to the 10 ASCII code points
                                  # `chr(c).isspace()` actually holds for.
                                  # Full Unicode has 29 (SPEC.md's own
                                  # ASCII-corpus stance for lower/upper/
                                  # isX applies here too, by name).


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
        # SPEC.md: "t == [] inserts u before every code point and at the
        # end, as Python does."
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


def _bounded(v):
    """The magnitude cap, applied to every arithmetic result: an int past
    MAX_BITS decides nothing, like a step past MAX_STEPS."""
    if type(v) is int and v.bit_length() > MAX_BITS:
        raise Budget("magnitude cap")
    return v


class St:
    __slots__ = ("n", "d", "check_measures", "_measure_stack")

    def __init__(self, check_measures: bool = False):
        self.n = 0
        self.d = 0
        # ROADMAP 13.4, framac-measure, 2026-09-11: opt-in only (default
        # False keeps every existing caller, interp.Reference included,
        # byte-for-byte unaffected). True makes `ev`'s "call" case and
        # `exec_body`'s "while" case raise MeasureViolation instead of
        # silently ignoring a broken `decreases`/variant -- see that
        # class's docstring. harness.real_witness is the only caller
        # that sets it.
        self.check_measures = check_measures
        self._measure_stack: list[tuple[str, object]] = []

    def tick(self):
        self.n += 1
        if self.n > MAX_STEPS:
            raise Budget("step cap")


# ---------------------------------------------------------------------------
# SPEC.md semantics.
# ---------------------------------------------------------------------------

def ev(e: dict, env: dict, funs: dict, st: St):
    st.tick()
    if "int" in e:
        return e["int"]
    if "bool" in e:
        return e["bool"]
    if "var" in e:
        if e["var"] not in env:
            raise Undef(f"unbound {e['var']}", expr=e)
        v = env[e["var"]]
        if v is None:
            raise Undef(f"{e['var']} read before assignment", expr=e)
        return v
    if "ite" in e:
        c = e["ite"]
        return ev(c["then" if ev(c["cond"], env, funs, st) else "else"],
                  env, funs, st)
    if "forall" in e or "exists" in e:
        kind = "forall" if "forall" in e else "exists"
        q = e[kind]
        lo = ev(q["lo"], env, funs, st)
        hi = ev(q["hi"], env, funs, st)
        if hi - lo > MAX_RANGE:
            raise Budget("quantifier range")
        acc = kind == "forall"
        # SPEC.md: the body must be defined for EVERY value in [lo, hi), so
        # every point is evaluated even after the result is decided; an empty
        # range decides without the body and is therefore defined.
        for i in range(lo, hi):
            sub = dict(env)
            sub[q["var"]] = i
            v = ev(q["body"], sub, funs, st)
            acc = (acc and v) if kind == "forall" else (acc or v)
        # SPEC.md gate 1: a quantifier denotes a BOOLEAN. Without the cast the
        # accumulator returns the body's own last value, so an int-bodied
        # quantifier would yield an int that Python's == then compares equal
        # to True, the bool/int conflation this oracle must not have.
        return bool(acc)
    if "call" in e:
        c = e["call"]
        f = funs.get(c["fun"])
        if f is None:
            raise Undef(f"no spec_fun {c['fun']}", expr=e)
        args = [ev(a, env, funs, st) for a in c["args"]]
        if len(args) != len(f["params"]):
            # zip() would truncate and return a value for a call t has no
            # meaning for; an oracle must refuse instead of guessing.
            raise ValueError(f"{c['fun']}: {len(args)} args for "
                             f"{len(f['params'])} params")
        sub = {p["name"]: a for p, a in zip(f["params"], args)}
        if "_exec" in f:
            body, ret = f["_exec"]
            if ret in sub:
                # `sub[ret] = None` below would destroy a parameter of the
                # same name, silently changing what the call computes.
                raise ValueError(f"{c['fun']}: return name {ret!r} collides "
                                 f"with a parameter")
            st.d += 1
            if st.d > MAX_DEPTH:
                st.d -= 1
                raise Budget("self-call depth")
            try:
                sub[ret] = None
                exec_body(body, sub, funs, st)
                if sub[ret] is None:
                    raise Undef("self-call returned no value", expr=e)
                return sub[ret]
            finally:
                st.d -= 1
        # ROADMAP 13.4, framac-measure, 2026-09-11: a spec_fun's own
        # `decreases`, checked ONLY when the caller opted in
        # (st.check_measures; see St's and MeasureViolation's docstrings).
        # Not covering the "_exec" branch above (a TASK's own body
        # self-recursing, gate 3): no committed task or probe in scope
        # here reaches it through a `decreases`-bearing self-call, and
        # closing it is a separate, unmeasured gap, named rather than
        # silently assumed away.
        dec = f.get("decreases")
        if st.check_measures and dec is not None:
            callee_m = ev(dec, sub, funs, st)
            stack = st._measure_stack
            if stack and stack[-1][0] == c["fun"]:
                caller_m = stack[-1][1]
                if caller_m < 0 or not (callee_m < caller_m):
                    raise MeasureViolation(c["fun"], dict(sub),
                                           caller_m, callee_m)
            stack.append((c["fun"], callee_m))
            try:
                return ev(f["body"], sub, funs, st)
            finally:
                stack.pop()
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
    a = [ev(x, env, funs, st) for x in e["args"]]
    if op == "neg":
        return -a[0]
    if op == "not":
        return not a[0]
    if op == "len":
        return len(a[0])
    if op == "at":
        s, i = a
        if not (0 <= i < len(s)):
            raise Undef(f"at index {i} outside [0,{len(s)})", expr=e)
        return s[i]
    if op == "update":
        # SPEC.md "Sequences as values" (2026-09-09): s[i := v], the same
        # definedness as `at`; a fresh tuple, never a mutation in place.
        s, i, v = a
        if not (0 <= i < len(s)):
            raise Undef(f"update index {i} outside [0,{len(s)})", expr=e)
        return s[:i] + (v,) + s[i + 1:]
    if op == "fill":
        # seq(n, v): DEFINED IFF n >= 0. A length past MAX_SEQ decides
        # nothing, like an int past MAX_BITS.
        n, v = a
        if n < 0:
            raise Undef(f"fill length {n} < 0", expr=e)
        if n > MAX_SEQ:
            raise Budget("seq length cap")
        return (v,) * n
    if op == "seq":
        # SPEC.md "Sequences: literals, concatenation, slices" (2026-09-09):
        # [e1, ..., en], every element evaluated, so defined iff all are.
        return tuple(a)
    if op == "slice":
        # s[a..b]: DEFINED IFF 0 <= a <= b <= len(s); the elements a..b-1.
        s, lo, hi = a
        if not (0 <= lo <= hi <= len(s)):
            raise Undef(f"slice bounds [{lo}..{hi}] outside 0 <= a <= b <= {len(s)}", expr=e)
        return tuple(s[lo:hi])
    if op == "pair":
        # SPEC.md "Pairs" (2026-09-10): (a, b), a value defined iff both
        # components are (every argument above is already evaluated).
        return Pair(a[0], a[1])
    if op == "fst":
        # p.0: always defined on a pair (check_wf refuses a non-pair operand
        # before this ever runs).
        return a[0].a
    if op == "snd":
        return a[0].b
    if op == "split":
        # SPEC.md "The string library" (2026-09-11): split(s) on whitespace
        # runs, split(s, c) on one code point, two arities of one op.
        return _str_split_ws(a[0]) if len(a) == 1 else _str_split_sep(a[0], a[1])
    if op == "join":
        return _str_join(a[0], a[1])
    if op == "tostr":
        return _str_tostr(a[0])
    if op == "count":
        return _str_count(a[0], a[1])
    if op == "find":
        return _str_find(a[0], a[1])
    if op == "strip":
        return _str_strip(a[0], True, True)
    if op == "lstrip":
        return _str_strip(a[0], True, False)
    if op == "rstrip":
        return _str_strip(a[0], False, True)
    if op == "replace":
        return _str_replace(a[0], a[1], a[2])
    if op == "lower":
        return _str_lower(a[0])
    if op == "upper":
        return _str_upper(a[0])
    if op == "isdigit":
        return _str_isdigit(a[0])
    if op == "isalpha":
        return _str_isalpha(a[0])
    if op == "isupper":
        return _str_isupper(a[0])
    if op == "islower":
        return _str_islower(a[0])
    if op == "startswith":
        return _str_startswith(a[0], a[1])
    if op == "endswith":
        return _str_endswith(a[0], a[1])
    if op == "+":
        if isinstance(a[0], tuple):
            # s + t on two seqs is concatenation (SPEC.md "Sequences:
            # literals, concatenation, slices"): always defined, the
            # length cap the only limit, as for fill.
            if len(a[0]) + len(a[1]) > MAX_SEQ:
                raise Budget("seq length cap")
            return a[0] + tuple(a[1])
        return _bounded(a[0] + a[1])
    if op == "-":
        return _bounded(a[0] - a[1])
    if op == "*":
        return _bounded(a[0] * a[1])
    if op in ("div", "mod"):
        # SPEC.md "Division and modulo" (2026-09-08): Euclidean, the
        # convention SMT-LIB, Dafny, Boogie, Verus, Lean 4 and F* share and
        # the one DafnyBench's own `/` and `%` mean, so the lifter maps them
        # one to one. q = x div y and r = x mod y are the unique integers
        # with x == q * y + r and 0 <= r < |y|. y == 0 is undefined, a
        # definedness obligation every lowering owes, exactly like `at`
        # outside [0, len). Python's % with |y| gives the Euclidean r
        # directly, and the quotient is then exact.
        x, y = a
        if y == 0:
            raise Undef(f"{op} by zero", expr=e)
        r = x % abs(y)
        return r if op == "mod" else _bounded((x - r) // y)
    if op == "==":
        return a[0] == a[1]
    if op == "!=":
        return a[0] != a[1]
    if op == "<":
        return a[0] < a[1]
    if op == "<=":
        return a[0] <= a[1]
    if op == ">":
        return a[0] > a[1]
    if op == ">=":
        return a[0] >= a[1]
    raise ValueError(f"t has no operator {op!r}")


def exec_body(body: list, env: dict, funs: dict, st: St, hook=None) -> bool:
    """Run statements for their VALUE only. Invariants and `decreases` are not
    checked here: this interpreter answers "what does the twin compute", and a
    twin whose annotations are broken is exactly what the kernel is asked to
    detect.

    `hook(stmt, env)` fires once per ARRIVAL at a `while` header, before the
    guard. invariant_witness needs it to learn what an actual execution puts
    in the variables the loop does not assign; default None leaves behaviour
    unchanged for every other caller.

    Returns True when a `return` statement (SPEC.md "Early exit",
    2026-09-08) ended the run: the value is in env under the return name,
    and every enclosing block stops. Callers that run a whole body may
    ignore the flag; the nested calls below propagate it."""
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
            if exec_body(c["then"] if ev(c["cond"], env, funs, st) else c["else"],
                         env, funs, st, hook):
                return True
        elif "while" in s:
            w = s["while"]
            if hook is not None:
                hook(s, env)
            it = 0
            dec = w.get("decreases")
            prev_m = None
            # ROADMAP 13.4, framac-measure, 2026-09-11: the loop's OWN
            # variant, checked ONLY when the caller opted in
            # (st.check_measures). The module docstring above still
            # holds for every other caller (default False): "invariants
            # and decreases are not checked here". At each arrival that
            # is about to run the body again, the variant just computed
            # must be non-negative, and (from the second arrival on)
            # strictly below the PREVIOUS arrival's variant -- the same
            # rule ev()'s spec_fun case checks for a recursive call,
            # restated for a loop's iterations instead of a call chain.
            while ev(w["cond"], env, funs, st):
                if st.check_measures and dec is not None:
                    m = ev(dec, env, funs, st)
                    if m < 0 or (prev_m is not None and not (m < prev_m)):
                        raise MeasureViolation(w, None,
                                               prev_m if prev_m is not None
                                               else m, m)
                    prev_m = m
                if exec_body(w["body"], env, funs, st, hook):
                    return True
                it += 1
                if it > MAX_LOOP:
                    raise Budget("loop cap")
        else:
            raise ValueError(f"t has no statement {s!r}")
    return False


def assigned(body: list, out: set | None = None) -> set:
    """Every name `body` assigns, at any depth. This is exactly the set a
    kernel's while rule HAVOCS at the loop header: SPEC.md gate 2 states the
    standard partial-correctness package, under which a variable the loop
    does not assign keeps whatever the straight-line code before the loop
    gave it, and the kernel keeps that fact for free."""
    out = set() if out is None else out
    for s in body:
        if "assign" in s:
            out.add(s["assign"][0])
        elif "return" in s:
            out.add(s["return"][0])
        elif "var" in s and isinstance(s["var"], dict):
            out.add(s["var"]["name"])
        elif "if" in s:
            assigned(s["if"]["then"], out)
            assigned(s["if"]["else"], out)
        elif "while" in s:
            assigned(s["while"]["body"], out)
    return out


def self_calls(node, name: str) -> bool:
    """Does `node` (any JSON subtree of a task) call `name`?"""
    if isinstance(node, dict):
        c = node.get("call")
        if isinstance(c, dict) and c.get("fun") == name:
            return True
        return any(self_calls(v, name) for v in node.values())
    if isinstance(node, list):
        return any(self_calls(v, name) for v in node)
    return False


def funs_of(task: dict, body: list) -> dict:
    """spec_funs, plus the task itself when `body` self-calls (gate 3). The
    body passed in is the one that DEFINES the function: a twin's self-calls
    resolve to the twin."""
    funs = {f["name"]: f for f in task.get("spec_funs", [])}
    if self_calls(body, task["name"]):
        funs[task["name"]] = {"params": task["params"],
                              "_exec": (body, task["returns"][0]["name"])}
    return funs


def _loops(body: list) -> list:
    """Every `while` node under `body`, pre-order (the same order source
    reads top to bottom): the fixed enumeration `loop_index` below numbers
    against, so a MeasureViolation's `site` (the raw AST node, identity
    matters, not content -- two loops can look alike) turns into a small,
    stable integer for a witness to carry."""
    out = []
    for s in body:
        if "while" in s:
            out.append(s["while"])
            out.extend(_loops(s["while"]["body"]))
        elif "if" in s:
            out.extend(_loops(s["if"]["then"]))
            out.extend(_loops(s["if"]["else"]))
    return out


def loop_index(task: dict, loop: dict) -> int:
    """`loop`'s 0-based position among `task["body"]`'s `while` nodes
    (`_loops`'s pre-order), identity-matched (`is`, not `==`: two
    syntactically identical loops must not collide)."""
    for i, w in enumerate(_loops(task["body"])):
        if w is loop:
            return i
    raise ValueError("loop not found in task body")


# ---------------------------------------------------------------------------
# The bounded domain. Ladders ordered so index 0 is the most witness-dense
# value, because the arity cap trims the tail; CONTENT-DERIVED, because a
# generic ladder misses the constants the task itself talks about (measured:
# with a fixed [-3..5] alphabet, fz_v1scan_085's exit witness needs a sequence
# containing -3, the literal its own ensures compares against, and no
# reachable point of a task-independent seq ladder had one).
# ---------------------------------------------------------------------------

# [-40, 40] as the task report's domain, with +/-10^6 and the 32-bit
# boundaries at index 5-9 rather than after +/-5: an arity-3 task reaches
# only ladder index ~11 within MAX_POINTS, and with the boundaries at 11-15
# fz_v0if_144's collapse-if witness (z = -10^6) was outside the domain and
# the ladder fell through to a weaker operator. Small values are not lost by
# this: `ladders` puts the task's OWN literals in front of the whole list.
INTS = ((0, 1, -1, 2, -2)
        + (10 ** 6, -10 ** 6, 2 ** 31, -2 ** 31 - 1, 2 ** 31 - 1)
        + (3, -3, 4, -4, 5, -5)
        + tuple(v for k in range(6, 41) for v in (k, -k)))

BOOLS = (False, True)

ALPHA = 13              # sequence element alphabet size; 8 through
                        # 2026-09-10, raised to 13 on 2026-09-11 (SPEC.md
                        # "The string library") to fit STR_ALPHA's five
                        # code points ahead of the truncation below without
                        # crowding out the literal-derived witnesses a
                        # non-string seq task still needs.


def _dedup(vs):
    out, seen = [], set()
    for v in vs:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def literals(node) -> list[int]:
    """Every integer literal in the task, in pre-order of first appearance,
    the constants the spec and the body actually compare against."""
    out = []
    if isinstance(node, dict):
        if "int" in node and isinstance(node["int"], int):
            out.append(node["int"])
        for v in node.values():
            out += literals(v)
    elif isinstance(node, list):
        for v in node:
            out += literals(v)
    return out


def _seq_ladder(alpha: tuple) -> tuple:
    """Sequences over the task's own alphabet, short first: every length-0 and
    length-1 sequence, then lengths 2-5 in shell order under a per-length cap,
    so the near corner (small indices in every position) comes first."""
    out = [()] + [(a,) for a in alpha]
    out += [c for c in _shell([alpha, alpha], 24)]
    out += [c for c in _shell([alpha, alpha, alpha], 32)]
    quad = [alpha[:4]] * 4
    out += [c for c in _shell(quad, 16)]
    out += [tuple(alpha[:1]) * 5, tuple(alpha[:5])]
    return tuple(_dedup(out))


def _around(lits: list[int]) -> list[int]:
    """Each literal and its two neighbours. A spec that compares against k
    needs k-1, k, k+1 in the domain or `<` and `<=` are indistinguishable;
    measured on fz_v1scan_154, whose exit witness needs a sequence element
    ABOVE the literal 4 and whose alphabet contained no such value."""
    out = []
    for v in lits:
        out += [v, v + 1, v - 1]
    return out


NESTED_ROWS = 8          # row-alphabet size for the outer ladder, the seq
                         # analogue of ALPHA: a nested seq's outer positions
                         # draw from this many distinct small rows.


def _nested_seq_ladder(rows: tuple) -> tuple:
    """SPEC.md "Nested sequences" (2026-09-10): `{"seq": "seq"}`, a finite
    seq whose elements are seqs of ints. Built by calling `_seq_ladder`
    ITSELF with `rows` (already-enumerated small seqs) standing in for the
    int alphabet it usually takes: that function's short-first, shell-
    ordered construction does not care what its alphabet's elements ARE,
    only that they are hashable and few, so it gives small outer lengths
    over small rows for exactly the reason it gives small lengths over
    small ints, with no new algorithm. `rows[:NESTED_ROWS]` caps the row
    alphabet the same way `ALPHA` caps the int one, so the outer ladder's
    own internal shell caps (24, 32, 16) stay meaningful rather than
    building a product over dozens of rows most of which are redundant at
    this domain's size."""
    return _seq_ladder(rows[:NESTED_ROWS])


STR_ALPHA = (32, 97, 101, 65, 48)   # space, 'a', 'e', 'A', '0': added
                                     # 2026-09-11 for SPEC.md "The string
                                     # library" so split (needs a
                                     # whitespace run to separate on) and
                                     # the predicates isdigit/isalpha/
                                     # isupper/islower (each need a
                                     # witness that is one and one that
                                     # is not) have inputs where the
                                     # answer is not vacuous; without
                                     # this the seq alphabet was only
                                     # small ints and every string-lib
                                     # predicate was constant on the
                                     # whole witness domain.


def ladders(task: dict) -> dict:
    lits = literals(task)
    ints = tuple(_dedup([0, 1, -1] + _around(lits) + list(INTS)))
    # STR_ALPHA is appended LAST, not spliced in earlier: _seq_ladder builds
    # combinations by ALPHABET INDEX (shell order over positions), so
    # inserting new entries before the literal-derived ones would shift
    # every existing task's alphabet indices and could silently change
    # which witness a pre-2026-09-11 task's twin ladder finds first --
    # exactly the kind of regression this file has no test for except by
    # re-deriving it. Appending after `[2, -2, 3, -3]` keeps the first 8
    # dedup'd entries BYTE-IDENTICAL to ALPHA's old value of 8, so every
    # committed task's already-documented witness (divmod_pair, min_max,
    # swap_rows, row_max_len) is unchanged; verified 2026-09-11 by
    # re-running harness.twin_cached on each and comparing to SPEC.md's
    # committed witness text.
    alpha = tuple(_dedup([0, 1, -1] + _around(lits)
                         + [2, -2, 3, -3] + list(STR_ALPHA))[:ALPHA])
    seqs = _seq_ladder(alpha)
    return {"int": ints, "seq": seqs, "bool": BOOLS,
            "nested_seq": _nested_seq_ladder(seqs)}


PAIR_SHELL = 24          # 2-argument shell cap, the same magnitude
                         # _seq_ladder gives its own 2-tuples.


def _ladder(lad: dict, ty) -> tuple:
    """The value ladder for type `ty`: "int"/"bool"/"seq" index `lad`
    directly; a pair type `{"pair": [T1, T2]}` (SPEC.md "Pairs", 2026-09-10)
    is built by combining the two component ladders in shell order, so the
    near corner (both components small) comes first, exactly as
    `_seq_ladder` orders sequences and for the same reason: the arity cap
    below trims the far corner of the product, not the near one. T1 and T2
    are always base types (no pair of pairs), so this does not recurse.

    SPEC.md "Nested sequences" (2026-09-10) adds the other dict-shaped
    type, `{"seq": "seq"}`: `lad["nested_seq"]` is precomputed once in
    `ladders()` above rather than rebuilt per lookup, since (unlike a pair,
    whose two component types vary task to task) there is exactly one
    nested-seq type in v1, so one ladder serves every param, return and
    local of it in a task."""
    if isinstance(ty, dict):
        if "pair" in ty:
            t1, t2 = ty["pair"]
            return tuple(_dedup([Pair(a, b) for a, b in
                                 _shell([lad[t1], lad[t2]], PAIR_SHELL)]))
        return lad["nested_seq"]
    return lad[ty]


def _shell(lists: list, limit: int):
    """Cartesian product in shell order: every tuple whose largest ladder
    index is d, for d ascending. Lexicographic order would hold the first
    parameter at its first value for the whole cap and never reach a witness
    that needs two parameters to move."""
    if not lists:
        yield ()
        return
    n = 0
    for d in range(max(len(x) for x in lists)):
        for combo in itertools.product(*[range(min(d + 1, len(x)))
                                         for x in lists]):
            if max(combo) != d:
                continue
            yield tuple(lists[k][c] for k, c in enumerate(combo))
            n += 1
            if n >= limit:
                return


def domain(task: dict, names: list[tuple[str, str]],
           limit: int = MAX_POINTS):
    """All assignments to `names` (a list of (name, type)) from `task`'s
    ladders, capped at `limit` points in shell order."""
    lad = ladders(task)
    lists = [_ladder(lad, ty) for _, ty in names]
    for combo in _shell(lists, limit):
        yield {n: v for (n, _), v in zip(names, combo)}


def _names(task: dict) -> list[tuple[str, str]]:
    return [(p["name"], p["type"]) for p in task["params"]]


def _j(v):
    if isinstance(v, Pair):
        # SPEC.md "Pairs": shown as a 2-list, recursing so a seq component
        # (itself a tuple) prints as a list too rather than as a raw tuple.
        return [_j(v.a), _j(v.b)]
    if isinstance(v, tuple):
        # SPEC.md "Nested sequences" (2026-09-10): a row is itself a tuple,
        # so a bare `list(v)` here would print a nested seq as a list of
        # TUPLES, not the list of lists its own type is shown as elsewhere
        # (a pair's seq component, just above). Recursing one call per
        # element costs nothing extra for a plain (unnested) seq, since
        # `_j` on an int or bool falls straight through to the line below.
        return [_j(x) for x in v]
    return v


def _tv(v):
    """A value tagged with its t TYPE. Python makes True == 1, so a bare `!=`
    would call a bool-returning twin and an int-returning real body equal and
    silently drop the witness; SPEC.md gate 1 keeps int and bool distinct.
    A Pair's `type(v).__name__` is "Pair", never "tuple", so this keeps a
    pair distinct from a same-shaped seq for the same reason (SPEC.md
    "Pairs": "the runtime value of a pair must be DISTINCT from a seq")."""
    return ("bool", v) if isinstance(v, bool) else (type(v).__name__, v)


def _shown(env: dict) -> dict:
    return {k: _j(v) for k, v in env.items()}


# ---------------------------------------------------------------------------
# Witnesses.
# ---------------------------------------------------------------------------

class Reference:
    """The real body's value on each domain point, computed once and reused
    for every candidate twin: harness.make_twin walks a ladder of operators
    and re-running the real body per candidate dominated the search."""

    def __init__(self, task: dict, limit: int = MAX_POINTS):
        self.task = task
        self.ret = task["returns"][0]["name"]
        self.funs = funs_of(task, task["body"])
        self.points: list[tuple[dict, object]] = []
        self.n_req = 0        # points satisfying `requires`; 0 separates a
                              # vacuous precondition from a body that never
                              # returns a value (probes fz_p_vac_unsat and
                              # fz_p_at_body respectively).
        self.n_domain = 0     # every point tried, whatever `requires` did
                              # with it; the denominator `req_undef` below
                              # is measured against.
        self.req_undef = 0    # points where `requires` ITSELF raised Undef
                              # (e.g. a `div`/`mod` by zero inside requires,
                              # ROADMAP 13.4, 2026-09-11): distinct from a
                              # point where requires evaluated cleanly to
                              # False. `req_undef == n_domain > 0` (and
                              # n_req == 0) means requires is undefined at
                              # EVERY type-correct input tried, not merely
                              # narrowed to nothing -- SPEC.md's "Undefined
                              # requires (normative)" DEFECTIVE case, a
                              # different refusal from a well-defined but
                              # unsatisfiable requires (fz_p_vac_unsat,
                              # fz_p_vac_range).
        req = task.get("requires", [])
        for env0 in domain(task, _names(task), limit):
            self.n_domain += 1
            st = St()
            try:
                sat = all(ev(c, env0, self.funs, st) for c in req)
            except Undef:
                self.req_undef += 1
                continue          # requires itself has no value here
            except (Budget, RecursionError):
                continue          # undecided, so it witnesses nothing
            if not sat:
                continue
            self.n_req += 1
            env = dict(env0)
            env[self.ret] = None
            try:
                exec_body(task["body"], env, self.funs, st)
                v = env[self.ret]
                if v is None:
                    continue          # a path that assigns nothing: no value
            except (Undef, Budget, RecursionError):
                continue              # undecided, so it witnesses nothing
            self.points.append((env0, v))

    def _breaks_ensures(self, env0: dict, got) -> bool | None:
        """Does the twin's value actually FALSIFY `ensures` here? True is the
        only thing that forces a sound kernel to refute; a value that merely
        DIFFERS may still satisfy a loose spec (abs's twin returns -x, which
        is a different value at x=1 and also violates `r >= 0`; a spec of
        `r == x or r == -x` alone it would not violate). None when the
        question could not be decided within budget."""
        env = dict(env0)
        env[self.ret] = got
        st = St()
        try:
            for c in self.task["ensures"]:
                if not ev(c, env, self.funs, st):
                    return True
            return False
        except Undef:
            return True           # an ensures with no value is not satisfied
        except (Budget, RecursionError):
            return None

    def witness(self, twin_body: list) -> dict | None:
        """First domain point where the twin disagrees with the real body,
        or None. A twin that is UNDEFINED where the real body has a value
        counts: SPEC.md makes every lowering discharge definedness or
        abstain, so that difference is one a kernel must see.

        SPEC.md "The twins" defines the witness as a VALUE DIFFERENCE, and
        that is what this returns, unchanged. `_ens` records separately
        whether the twin's value also falsifies `ensures` at that point,
        because only that is grounds for saying a kernel MUST refute; see
        refuting_witness, which searches for one."""
        funs = funs_of(self.task, twin_body)
        for env0, real in self.points:
            st = St()
            env = dict(env0)
            env[self.ret] = None
            try:
                exec_body(twin_body, env, funs, st)
                got = env[self.ret]
            except Undef as u:
                w = _shown(env0)
                w.update(_kind="undefined", _real=_j(real), _twin=str(u),
                         _ens=True)   # no value at all cannot satisfy ensures
                return w
            except (Budget, RecursionError):
                continue
            if got is None or _tv(got) != _tv(real):
                w = _shown(env0)
                w.update(_kind="value", _real=_j(real),
                         _twin="no value" if got is None else _j(got),
                         _ens=(True if got is None
                               else self._breaks_ensures(env0, got)))
                return w
        return None

    def refuting_witness(self, twin_body: list) -> dict | None:
        """The first domain point where the twin's value FALSIFIES `ensures`
        the only kind of witness that entails a sound kernel must refute
        the twin. Separate from `witness` and never called by the twin
        ladder, because SPEC.md defines twin acceptance by value difference
        and changing that would move every published measurement. This is
        what a ground-truth grader (ROADMAP.md 10.1) should ask for, since a
        REFUTED it does not predict is a finding about the kernel."""
        funs = funs_of(self.task, twin_body)
        for env0, real in self.points:
            st = St()
            env = dict(env0)
            env[self.ret] = None
            try:
                exec_body(twin_body, env, funs, st)
                got = env[self.ret]
            except Undef as u:
                w = _shown(env0)
                w.update(_kind="undefined", _real=_j(real), _twin=str(u),
                         _ens=True)
                return w
            except (Budget, RecursionError):
                continue
            if got is None:
                w = _shown(env0)
                w.update(_kind="value", _real=_j(real), _twin="no value",
                         _ens=True)
                return w
            if self._breaks_ensures(env0, got) is True:
                w = _shown(env0)
                w.update(_kind="value", _real=_j(real), _twin=_j(got),
                         _ens=True)
                return w
        return None


class _Admissible:
    """Which loop states a SOUND kernel cannot rule out.

    A kernel's while rule havocs the variables the loop body assigns and
    keeps everything else. So a candidate state that moves an UNMODIFIED
    local off the value the code before the loop gave it is a state the
    kernel refutes on sight, and a "witness" standing on one is not evidence
    the kernel must refute the twin; it is a false accusation of vacuity.

    MEASURED 2026-09-01 on the smallest task with that shape (a local `m :=
    n` never assigned in the loop, invariant `m == n` dropped): the old
    unfiltered search returned `exit at n=0, m=1, r=1`, and dafny and verus
    both VERIFIED that twin, because neither can reach m != n.

    The filter is: params and modified names range freely (a kernel knows
    nothing about the modified ones beyond the invariants, and nothing about
    params beyond `requires`); an unmodified local or return must carry a
    value some ACTUAL execution puts there at this loop's header, since a
    state a real run reaches is one no sound kernel can exclude.

    Measured on the 407-task corpus (11 committed + 4 seeds x 80 generated),
    NO invariant-carrying loop has an unmodified non-param name in scope, so
    `fixed` is empty everywhere and this filter is a no-op there: the repair
    closes a latent hole and moves no existing measurement.

    TWIN-PRESERVATION, 2026-09-11 -- investigated, NOT extended to modified
    names, and here is why by measurement, so the next pass does not retry
    the same two dead ends. ROADMAP 16.2's wave-G finding is real: on
    dafny_synthesis 3 isNonPrime, 605 isPrime and 126 sumOfCommonDivisors
    the invariant-drop witness stands on a MODIFIED loop counter (`i`/`d`,
    initialised to a literal, stepped by a fixed `+1`) at a value no
    execution ever reaches (i=1 when `var i := 2` and the loop only ever
    does `i := i + 1`; i=-1 when `var i := 1` likewise) -- by hand, and by
    dafny (`dafny verify` on a standalone `while` with NO invariant at all
    still proves `assert i >= 2` inside the body, from nothing but the
    literal init and the one `+1` step: dafny auto-infers a monotone
    counter's own floor, a fact independent of whatever invariant is
    stated or dropped). Both a JOINT reachable-state-tuple filter and a
    MARGINAL per-name one (each requiring `exec_body`'s hook to fire on
    EVERY loop-header arrival, not just the first, itself a separate
    latent gap this pass found and would have had to fix) were built and
    measured against the 34 committed tasks: EITHER one, once broadened
    past unmodified names, silently changes is_prime's own witness (same
    counter shape, same early-return body) from its committed
    invariant-drop#1 (exit, d=4, n=4) to invariant-drop (return, d=1,
    n=2) -- and GRADED, that new twin reads verified/verified in dafny,
    breaking is_prime's committed verified/refuted row. Worse, the
    marginal filter (needed so sum_upto's own two committed invariant-drop
    witnesses, which stand on a run-time-UNREACHABLE (i, r) pair by
    design -- the pair the DROPPED invariant exists to rule out, not one
    any execution visits -- keep finding their forcing witness) still
    fails sum_upto's SECOND rung: dropping `i >= 0 and i <= n` (keeping
    only the accumulator relation `2*r == i*(i+1)`) is ALSO refuted by
    dafny (measured directly, hand-built .dfy), because without that
    bound an abstract, invariant-satisfying `i` may exceed `n` at the
    natural exit -- exactly the shape of excursion a reachability filter
    would also have to exclude, and doing so kills this genuine, dafny-
    confirmed witness too. So dafny's own automatic inference is
    ASYMMETRIC (a monotone counter's floor, free; the same counter's
    ceiling against a DIFFERENT invariant's own bound, not free) in a way
    no reachability model built from the interpreter's OWN semantics can
    honestly reproduce without asking dafny itself -- which witness
    computation, by design, never does. No fix shipped here for the three
    rows above (or for is_prime's shared exposure, currently avoided
    only because its ladder happens to land on a different, unaffected
    rung first): they are named honestly as dafny VERIFYING a twin whose
    witness respects every fact this class's stated frame rule checks
    (unmodified names' defining equations, `requires`) -- see the
    reproductions this wave's note names -- and nothing here is changed
    for them, per this task's own instruction for that case.

    A SEPARATE, independently real bug was also found and, for the same
    reason, NOT shipped: invariant_witness's own preservation check ran
    the trial iteration and asked whether `kept` still held regardless of
    whether that iteration took a `return` path (SPEC.md "Early exit") --
    a return never reaches "next iteration", so the obligation there is
    `ensures`, exactly what "exit" already judges at the loop's NATURAL
    exit, never "kept survives one more step" (a fact about the
    fall-through path a return never takes). MEASURED on
    dafny_synthesis 414 anyValueExists, 808 containsK, 69
    containsSequence and 809 isSmaller (their own k=0 invariant-drop
    candidate): the trial iteration returns, and `ensures` actually HOLDS
    at that return -- these are not forcing witnesses by
    invariant_witness's own stated standard at all, spurious "preservation"
    hits the harness should never have minted. Correcting just this,
    alone, with `_Admissible` untouched, ALSO changes is_prime's witness
    (its own k=0 candidate returns too, and the correction lets its
    genuine-per-the-interpreter, unreachable-per-dafny d=1 witness through
    for the reason above) -- the two bugs are entangled on this one
    committed task, and fixing the return-vs-preservation confusion alone
    cannot be shipped independently of the counter-reachability question
    without the same regression. Left unfixed here, named rather than
    silently patched, per this task's "stop and report" rule on a
    committed witness change; whoever picks this up next needs BOTH
    solved together, or a way to keep is_prime's ladder landing on its
    current (unaffected) rung on purpose."""

    def __init__(self, task, loop, names, funs):
        mod = assigned(loop["body"])
        params = {p["name"] for p in task["params"]}
        self.fixed = [n for n, _ in names if n not in mod and n not in params]
        self.params = [p["name"] for p in task["params"]]
        self.task, self.loop, self.funs = task, loop, funs
        self.cache: dict = {}

    def __bool__(self):
        return bool(self.fixed)

    def _reachable(self, key: tuple) -> set:
        """The tuples of `fixed` values an actual run leaves at the header,
        for one assignment to the params."""
        if key in self.cache:
            return self.cache[key]
        seen: set = set()
        env0 = dict(zip(self.params, key))
        env = dict(env0)
        env[self.task["returns"][0]["name"]] = None
        target = self.loop

        def hook(stmt, e):
            if stmt["while"] is target:
                v = tuple(e.get(n) for n in self.fixed)
                if all(x is not None for x in v):
                    seen.add(v)

        try:
            exec_body(self.task["body"], env, self.funs, St(), hook)
        except (Undef, Budget, RecursionError, ValueError):
            pass                      # a run that dies still yields what it
                                      # reached before dying
        self.cache[key] = seen
        return seen

    def ok(self, env: dict) -> bool:
        if not self.fixed:
            return True
        key = tuple(env[n] for n in self.params)
        return tuple(env.get(n) for n in self.fixed) in self._reachable(key)


def continuation(body: list, loop: dict) -> list | None:
    """The statements that run after `loop` exits, in order: the rest of its
    own block, then the rest of each enclosing `if`'s block, outward to the
    method's end. None when `loop` is not in `body`, or sits under an
    enclosing `while`: that loop's exit re-enters the outer one, whose
    invariant is the obligation there, so there is no straight run to the
    return to state. Identity, not equality: `loop` is the very dict
    `harness._invariant_candidates` yielded (or a lowering's `_twin_loop`
    found), because a body may hold two equal loops."""
    for i, s in enumerate(body):
        if "while" in s:
            if s["while"] is loop:
                return body[i + 1:]
            if _holds(s["while"]["body"], loop):
                return None
        elif "if" in s:
            for branch in (s["if"]["then"], s["if"]["else"]):
                if _holds(branch, loop):
                    inner = continuation(branch, loop)
                    return None if inner is None else inner + body[i + 1:]
    return None


def _holds(body: list, loop: dict) -> bool:
    for s in body:
        if "while" in s:
            if s["while"] is loop or _holds(s["while"]["body"], loop):
                return True
        elif "if" in s:
            if _holds(s["if"]["then"], loop) or _holds(s["if"]["else"], loop):
                return True
    return False


def exit_env(task: dict, body: list, loop: dict, state: dict) -> dict | None:
    """The environment at the method's return when `loop` (a dict inside
    `body`) exits in `state`: the continuation, run from that state. `state`
    maps every name in scope at the loop, params included, to a value. None
    when the loop has no continuation (under an enclosing while) or the run
    is undefined or over budget; a tail loop runs nothing and returns
    `state` unchanged.

    This is where the exit obligation lives. A kernel judges `ensures` at
    the return, and when statements follow the loop the loop-exit state is
    not the return state: slow_max (DafnyBench) assigns its result after
    its loop, and an exit witness judged at the loop's own `z` read REFUTED
    in three columns on a twin every kernel proves (measured 2026-09-07,
    ROADMAP 12.5). Every certificate builder that restates an exit witness
    goes through here, so the witness and its certificate name the same
    obligation."""
    cont = continuation(body, loop)
    if cont is None:
        return None
    env = dict(state)
    try:
        exec_body(cont, env, funs_of(task, body), St())
    except (Undef, Budget, RecursionError, ValueError):
        return None
    return env


def invariant_witness(task: dict, loop: dict, kept: list,
                      names: list[tuple[str, str]],
                      limit: int = MAX_STATES) -> dict | None:
    """INVARIANT-DROP leaves a body that computes the same value, so
    Reference.witness cannot see it. What is measurable is whether the
    SURVIVING invariants still carry the two obligations the dropped one was
    there for: a state satisfying requires and the survivors with the guard
    false but `ensures` false (exit entailment), or one satisfying them with
    the guard true whose single iteration breaks a survivor (preservation).
    Either means a kernel MUST refute the twin. Neither means a twin that
    verifies says nothing, and harness.make_twin moves on.

    The state must also be one the kernel cannot rule out; see _Admissible,
    without which this returns witnesses dafny and verus were measured to
    verify straight through.

    Exit entailment is judged at the RETURN, not at the loop: the state is
    run through whatever follows the loop first (exit_env), because that is
    where a kernel judges `ensures`. A loop under an enclosing while yields
    no exit witness at all (no straight run to the return; its exit
    obligation is the outer invariant), and the ladder moves on."""
    funs = funs_of(task, task["body"])
    cont = continuation(task["body"], loop)
    req = task.get("requires", [])
    ens = task["ensures"]
    adm = _Admissible(task, loop, names, funs)
    for env in domain(task, names, limit):
        st = St()
        try:
            if not all(ev(c, env, funs, st) for c in req):
                continue
            if not adm.ok(env):
                continue
            if not all(ev(c, env, funs, st) for c in kept):
                continue
            if not ev(loop["cond"], env, funs, st):
                if cont is None:
                    continue
                post = dict(env)
                exec_body(cont, post, funs, st)
                if not all(ev(c, post, funs, st) for c in ens):
                    w = _shown(env)
                    w["_kind"] = "exit"
                    return w
                continue
            nxt = dict(env)
            exec_body(loop["body"], nxt, funs, st)
            if not all(ev(c, nxt, funs, st) for c in kept):
                w = _shown(env)
                w["_kind"] = "preservation"
                return w
        except (Undef, Budget, RecursionError):
            continue
    return None
