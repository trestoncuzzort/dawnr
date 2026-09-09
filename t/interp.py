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
"""
from __future__ import annotations

import itertools

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
    SPEC.md calls wrong."""


class Budget(Exception):
    """A cap above was hit; this input decides nothing."""


MAX_SEQ = 1 << 16          # fill length cap, the seq analogue of MAX_BITS


def _bounded(v):
    """The magnitude cap, applied to every arithmetic result: an int past
    MAX_BITS decides nothing, like a step past MAX_STEPS."""
    if type(v) is int and v.bit_length() > MAX_BITS:
        raise Budget("magnitude cap")
    return v


class St:
    __slots__ = ("n", "d")

    def __init__(self):
        self.n = 0
        self.d = 0

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
            raise Undef(f"unbound {e['var']}")
        v = env[e["var"]]
        if v is None:
            raise Undef(f"{e['var']} read before assignment")
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
            raise Undef(f"no spec_fun {c['fun']}")
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
                    raise Undef("self-call returned no value")
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
            raise Undef(f"at index {i} outside [0,{len(s)})")
        return s[i]
    if op == "update":
        # SPEC.md "Sequences as values" (2026-09-09): s[i := v], the same
        # definedness as `at`; a fresh tuple, never a mutation in place.
        s, i, v = a
        if not (0 <= i < len(s)):
            raise Undef(f"update index {i} outside [0,{len(s)})")
        return s[:i] + (v,) + s[i + 1:]
    if op == "fill":
        # seq(n, v): DEFINED IFF n >= 0. A length past MAX_SEQ decides
        # nothing, like an int past MAX_BITS.
        n, v = a
        if n < 0:
            raise Undef(f"fill length {n} < 0")
        if n > MAX_SEQ:
            raise Budget("seq length cap")
        return (v,) * n
    if op == "+":
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
            raise Undef(f"{op} by zero")
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
            while ev(w["cond"], env, funs, st):
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

ALPHA = 8               # sequence element alphabet size


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


def ladders(task: dict) -> dict:
    lits = literals(task)
    ints = tuple(_dedup([0, 1, -1] + _around(lits) + list(INTS)))
    alpha = tuple(_dedup([0, 1, -1] + _around(lits)
                         + [2, -2, 3, -3])[:ALPHA])
    return {"int": ints, "seq": _seq_ladder(alpha), "bool": BOOLS}


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
    lists = [lad[ty] for _, ty in names]
    for combo in _shell(lists, limit):
        yield {n: v for (n, _), v in zip(names, combo)}


def _names(task: dict) -> list[tuple[str, str]]:
    return [(p["name"], p["type"]) for p in task["params"]]


def _j(v):
    return list(v) if isinstance(v, tuple) else v


def _tv(v):
    """A value tagged with its t TYPE. Python makes True == 1, so a bare `!=`
    would call a bool-returning twin and an int-returning real body equal and
    silently drop the witness; SPEC.md gate 1 keeps int and bool distinct."""
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
        req = task.get("requires", [])
        for env0 in domain(task, _names(task), limit):
            st = St()
            try:
                if not all(ev(c, env0, self.funs, st) for c in req):
                    continue
                self.n_req += 1
                env = dict(env0)
                env[self.ret] = None
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
    closes a latent hole and moves no existing measurement."""

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
