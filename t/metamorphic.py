#!/usr/bin/env python3
"""metamorphic.py: verdict invariance of the seven lowerings under rewrites
that PROVABLY preserve SPEC.md semantics.

Why this instrument and not another round of differential fuzzing. run_all.py
grades a cell by agreement and fuzz_lower.py grades a task by agreement plus a
reference interpreter; both are structurally blind to a bias SHARED by all
seven lowerings, because a shared bias produces a green table. The integer
width finding of 2026-09-01 (`lower_framac.py` lowering a t `int` to a C
`int`, so WP granted `x <= 2^31-1` for free) was caught only because Frama-C
happened to be the odd one out.

Metamorphic testing needs no oracle at all. Take a rewrite T with
`[[T(task)]] = [[task]]` under SPEC.md, and require verdict(T(task)) ==
verdict(task) in every kernel. A verdict that MOVES under a meaning-preserving
rewrite is a defect in a lowering or an adapter no matter what the other six
say, and no matter what any interpreter says. Nothing here is graded against
consensus.

WHAT EACH VERDICT MOVE MEANS, and the taxonomy is load-bearing:

  - VERIFIED <-> REFUTED across a rewrite: one of the two answers is wrong
    about a program the other one is also about. When the base task is
    KNOWN-FALSE by an exhibited witness, a VERIFIED on either side is an
    UNSOUNDNESS; otherwise it is a lowering bug of unknown direction.
  - anything <-> TIMEOUT / UNPROVED: the solver worked harder under the
    rewrite and ran out. INCOMPLETENESS, not unsoundness, per SPEC.md's taxonomy
    rule is that a budget exhaustion is never a refutation, and the same rule
    forbids reading it as a verdict change here. Reported as robustness.
  - anything <-> LOWER-ERROR / ABSTAIN: the rewrite left the fragment one
    lowering covers. A coverage gap in that lowering, reported as such.

SOUNDNESS OF THE REWRITES THEMSELVES. Each transformation below carries the
SPEC.md clause that makes it meaning-preserving, and definedness is argued
explicitly wherever short-circuiting is involved (SPEC.md "Definedness" makes
`and`/`or`/`implies`/`ite` non-strict, so an "obvious" identity such as
De Morgan has a real obligation attached). The proof is the argument in the
comment. The interpreter cross-check in `_equivalent` below is a TRIPWIRE on
that argument over a bounded domain, never its justification: a bounded search
is a sound proof of falsity and is not a sound proof of truth. A tripwire hit
is a bug in THIS file and is reported as such, never as a kernel finding.

Own output directory, never t/out/, because the suite's drivers own those filenames
(run_par.py's _live_conflict records what two writers cost). Base and variants
each get their own subdirectory and keep the SAME task name, so the lowered
files differ only by the rewrite and never by an identifier the lowering might
derive a module or theorem name from.

WHAT THE FIRST RUN MEASURED (2026-09-01, the training box, all seven kernels
of t/AGREEMENT.md): 79 base tasks, 10 true by construction, 15 false by an
exhibited witness to `ensures` and 54 generated, giving 1199 variants over 18
transformations, 1278 cases, 8798 kernel invocations. 0 tripwire hits. 212
verdict moves, EVERY one reproducing at flake n=3 and none of them an
unsoundness: 0 cases where a kernel VERIFIED a task with a witness against it,
and every move away from VERIFIED, which is the only direction a stronger
obligation can move one. Per kernel: verus 77, rocq 70, lean 20, fstar 19,
framac 17, dafny 9, spark 0 (spark's 20 moves are all TIMEOUT, which is the
honest report). Per rewrite the top four are let-copy 57, rename 26,
req-or-false 25, or-false 20.

Seven defect classes, each minimised to a hand-written t task the rest of the
suite does not generate:

  1. `lower_verus.py` lower_v0 emits the return binder as a literal
     `-> (r: int)` while the `ensures` it emits uses the task's own return
     name, so a task whose return is not spelled `r` lowers to Rust with an
     unbound identifier and verus scores MALFORMED. Every task in t/tasks/ and
     every task fuzz_lower.py generates names its return `r`, so no existing
     instrument can reach this; consistent renaming reaches it on the first
     try. SPEC.md names the return by the task, not by convention.
  2. `lower_framac.py` and `lower_fstar.py` emit `neg` as a bare prefix `-`
     with no space, so `neg` of a NEGATIVE literal produces `(--1)`, which C
     lexes as predecrement (maximal munch) and Frama-C rejects: MALFORMED on a
     task true by construction.
  3. The verus adapter's `_REQ_FALSE` regex scans a `requires` for a bare
     `false` token. `c or false` is the same precondition as `c`, and it turns
     VERIFIED into VACUOUS and REFUTED into VACUOUS, because the vacuity screen fires
     before the kernel's own verdict is read. The regex's comment records its
     false NEGATIVES; this is the false-positive direction. ROADMAP.md 10.2 is
     the standing conclusion: semantic vacuity is not decidable by regex.
  4. `lower_lean.py`, `lower_rocq.py` and `lower_fstar.py` hoist a `while` into
     a top-level definition whose contract is exactly the loop's invariant
     list, dropping the path conditions the preceding statements established.
     A local initialised from a parameter (`let-copy`) is then a fresh
     universal in the emitted lemma and the relation to the parameter is gone:
     lean's loop lemma becomes outright FALSE (it concludes `= n * 2` while
     quantifying over the copy), and lean/rocq/fstar REFUTE a task all seven
     verify without the copy. dafny/verus/framac keep the fact because a WP
     caller retains it; spark TIMEOUTs. Reported as REFUTED, which is the
     taxonomy violation ROADMAP.md 10.1 names: the obligation the lowering
     emitted is strictly STRONGER than the one SPEC.md states, so this can
     only cost a proof, never buy one.
  5. The fstar adapter scores MALFORMED whenever its query log holds no
     `unsat`, so a task F*'s own normaliser closes without calling Z3 is a
     non-verdict: `ensures r == x` for `assign r := x` measured MALFORMED,
     while MALFORMED is defined as "does not parse/resolve".
  6. TRIGGERS. `s[j]` inside a `forall` is the SMT trigger; `s[(j - 0)]` and
     `s[(j * 1)]` are not trigger candidates, so the same quantifier loses
     its instantiation. Verus makes it a hard error ("Could not automatically
     infer triggers"); Dafny emits the brittleness WARNING and, because
     `--allow-warnings` is off, exits 2, which verifiers/dafny.py maps to
     MALFORMED even though Dafny's own tally on the same run reads "2
     verified, 0 errors". Measured on one task Dafny also reported "this
     invariant could not be proved to be maintained" for `s[(j * 1)]` and the
     adapter scored REFUTED. The rewrite changes no value at any input.
  7. INCOMPLETENESS SOLD AS REFUTATION, the taxonomy rule of ROADMAP.md 10.1,
     violated by every adapter whose kernel FAILS a proof rather than
     exhausting a budget. Rocq is the clearest: 70 moves, all VERIFIED ->
     REFUTED, and coqc's own message on the smallest of them is "Tactic
     failure: unsolved t verification condition" for `3 * f(n-1)` rewritten to
     `(3 * f(n-1)) + 0`. verifiers/rocq.py's three-pass rule reads any failed
     full compile as REFUTED, so a tactic that gave up is indistinguishable
     from a false goal. spark is the counter-example that shows this is a
     choice and not a necessity: its 20 moves are all TIMEOUT.

    python3 t/metamorphic.py --out DIR --n 24 --seed 11 --jobs 40
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import random
import sys
import time
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fuzz_lower as fz                               # noqa: E402
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

# Outcomes that are knowledge. A move between two of these is a verdict
# change; a move involving anything else is incompleteness or coverage.
DECISIVE = (Outcome.VERIFIED, Outcome.REFUTED, Outcome.VACUOUS,
            Outcome.MALFORMED)
INCOMPLETE = (Outcome.TIMEOUT, Outcome.UNPROVED, Outcome.TOOL_ERROR)


def _copy(o):
    return json.loads(json.dumps(o))          # a t task is pure JSON


def _rng(name: str, salt: str) -> random.Random:
    # Site choice must be reproducible from the task alone; PYTHONHASHSEED
    # makes hash() unstable across processes, so the seed is a checksum.
    return random.Random(zlib.crc32(f"{name}/{salt}".encode()))


# ---------------------------------------------------------------------------
# Typed positions. A rewrite that replaces `e` by `e + 0` must know `e` is
# int-typed in ITS OWN scope, which for a quantifier body is not the task's
# scope. fuzz_lower._ty types a whole expression in a given env; this walk
# supplies the env each subexpression actually has.
# ---------------------------------------------------------------------------

def _ty(e, env, funs, ver):
    errs: list[str] = []
    t = fz._ty(e, env, funs, ver, errs, set())
    return None if errs else t


def _sites(e, env, funs, ver, path=()):
    """(path, node, type, env) for e and every subexpression, pre-order."""
    yield path, e, _ty(e, env, funs, ver), env
    if "op" in e:
        for i, a in enumerate(e.get("args", [])):
            yield from _sites(a, env, funs, ver, path + ("args", i))
    elif "ite" in e:
        for k in ("cond", "then", "else"):
            yield from _sites(e["ite"][k], env, funs, ver, path + ("ite", k))
    elif "forall" in e or "exists" in e:
        q = "forall" if "forall" in e else "exists"
        d = e[q]
        for k in ("lo", "hi"):
            yield from _sites(d[k], env, funs, ver, path + (q, k))
        sub = dict(env)
        sub[d["var"]] = "int"
        yield from _sites(d["body"], sub, funs, ver, path + (q, "body"))
    elif "call" in e:
        for i, a in enumerate(e["call"]["args"]):
            yield from _sites(a, env, funs, ver, path + ("call", "args", i))


def _stmt_exprs(body, env, funs, ver, path=()):
    """(path, expr, env, kind) over every expression a statement carries.

    `env` grows with each `var` declaration, in declaration order, so a
    rewrite at a later statement sees the locals SPEC.md's scope rule says it
    sees. Invariants and `decreases` are included: they are annotations, and a
    logically equivalent annotation is the same proof obligation, so their
    verdict must not move either."""
    env = dict(env)
    for i, s in enumerate(body):
        p = path + (i,)
        if "assign" in s:
            yield p + ("assign", 1), s["assign"][1], env, "rhs"
        elif "var" in s:
            d = s["var"]
            yield p + ("var", "init"), d["init"], env, "init"
            env = dict(env)
            env[d["name"]] = d["type"]
        elif "if" in s:
            c = s["if"]
            yield p + ("if", "cond"), c["cond"], env, "cond"
            yield from _stmt_exprs(c["then"], env, funs, ver, p + ("if", "then"))
            yield from _stmt_exprs(c["else"], env, funs, ver, p + ("if", "else"))
        elif "while" in s:
            w = s["while"]
            yield p + ("while", "cond"), w["cond"], env, "cond"
            for k, inv in enumerate(w.get("invariants", [])):
                yield p + ("while", "invariants", k), inv, env, "invariant"
            yield p + ("while", "decreases"), w["decreases"], env, "decreases"
            yield from _stmt_exprs(w["body"], env, funs, ver,
                                   p + ("while", "body"))


def _body_env(task):
    env = {p["name"]: p["type"] for p in task["params"]}
    env[task["returns"][0]["name"]] = task["returns"][0]["type"]
    return env


def _funs(task):
    f = {g["name"]: g for g in task.get("spec_funs", [])}
    if fz._self_calls(task["body"], task["name"]):
        f[task["name"]] = {"params": task["params"],
                           "result": task["returns"][0]["type"]}
    return f


def _all_body_sites(task):
    """Every (abs_path, node, type, kind) inside the body, typed."""
    ver, funs = task["t"], _funs(task)
    out = []
    for p, e, env, kind in _stmt_exprs(task["body"], _body_env(task),
                                       funs, ver):
        for sp, node, ty, _sc in _sites(e, env, funs, ver, p):
            out.append((sp, node, ty, kind))
    return out


def _get(root, path):
    node = root
    for k in path:
        node = node[k]
    return node


def _put(task, path, new):
    """`task` with the node at `path` (rooted at task["body"]) replaced."""
    out = _copy(task)
    node = out["body"]
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = _copy(new)
    return out


def _pick(task, salt, cands):
    """One site, chosen deterministically from the task's own identity. First
    site would concentrate every rewrite on the same syntactic position; the
    choice must vary across the corpus and still reproduce exactly."""
    if not cands:
        return None
    return cands[_rng(task["name"], salt).randrange(len(cands))]


TRUE0 = {"op": "==", "args": [{"int": 0}, {"int": 0}]}
FALSE0 = {"op": "!=", "args": [{"int": 0}, {"int": 0}]}


def _true(task):
    # SPEC.md gate 1 introduces the bool literal; a v0 task has no such form,
    # so the v0 spelling of `true` is a closed comparison, which is a v0 Expr.
    return {"bool": True} if task["t"] == 1 else _copy(TRUE0)


def _false(task):
    return {"bool": False} if task["t"] == 1 else _copy(FALSE0)


# ---------------------------------------------------------------------------
# The transformations. Each returns (variant_task, name_map) or None, where
# name_map sends a BASE parameter name to its variant name (identity except
# under renaming) so the equivalence tripwire can feed both the same input.
# ---------------------------------------------------------------------------

def t_rename(task):
    """Consistent alpha-renaming of every binder: params, the return, locals,
    quantifier bound variables, spec_fun names and their parameters.

    SPEC.md's semantics is environment lookup by name under the scope rule
    ("`requires` sees params; `ensures` sees params and returns; body
    expressions see params, returns, and locals declared above them"), so a
    bijective renaming onto FRESH names, fresh so that no binder can capture an
    occurrence that was free, leaves every lookup, and therefore every value,
    unchanged. The task's own name is NOT renamed: it is the self-call target
    and, in several lowerings, the emitted module/theorem identifier, and
    holding it fixed keeps the variant's identity comparable to the base's."""
    used = set()

    def collect(n):
        if isinstance(n, dict):
            for k, v in n.items():
                if k == "var" and isinstance(v, str):
                    used.add(v)
                elif k in ("name", "fun") and isinstance(v, str):
                    used.add(v)
                else:
                    collect(v)
        elif isinstance(n, list):
            for v in n:
                collect(v)

    collect(task)
    used.add(task["name"])
    ren, k = {}, 0

    def fresh():
        nonlocal k
        while True:
            c = f"mmv{k}"
            k += 1
            if c not in used:
                used.add(c)
                return c

    for p in task["params"]:
        ren[p["name"]] = fresh()
    ren[task["returns"][0]["name"]] = fresh()
    for f in task.get("spec_funs", []):
        ren[f["name"]] = fresh()
        for p in f["params"]:
            ren.setdefault(p["name"], fresh())

    def locals_of(n):
        if isinstance(n, dict):
            if "var" in n and isinstance(n["var"], dict):
                ren.setdefault(n["var"]["name"], fresh())
            for v in n.values():
                locals_of(v)
        elif isinstance(n, list):
            for v in n:
                locals_of(v)

    locals_of(task["body"])

    def walk(n):
        if isinstance(n, dict):
            out = {}
            for key, v in n.items():
                if key == "var" and isinstance(v, str):
                    out[key] = ren.get(v, v)
                elif key in ("name", "fun") and isinstance(v, str):
                    out[key] = ren.get(v, v)
                elif key == "assign":
                    # SYNTAX.md spells an assignment ["name", Expr]: the
                    # target is a bare string in a list, reached by no "name"
                    # or "var" key, so it needs its own arm.
                    out[key] = [ren.get(v[0], v[0]), walk(v[1])]
                else:
                    out[key] = walk(v)
            return out
        if isinstance(n, list):
            return [walk(v) for v in n]
        return n

    out = walk(task)
    out["name"] = task["name"]          # the task itself keeps its identity
    # A quantifier's bound variable is a `var` under forall/exists; walk()
    # above rewrote its occurrences only if it is in `ren`, and it is not, so
    # bound variables are renamed here to fresh names of their own.
    def rebind(n):
        if isinstance(n, dict):
            for q in ("forall", "exists"):
                if q in n:
                    d = n[q]
                    nv = fresh()
                    d["body"] = _subst_var(d["body"], d["var"], {"var": nv})
                    d["var"] = nv
            for v in n.values():
                rebind(v)
        elif isinstance(n, list):
            for v in n:
                rebind(v)

    rebind(out)
    return out, {p["name"]: ren[p["name"]] for p in task["params"]}


def _subst_var(node, old, new):
    if isinstance(node, dict):
        if "var" in node and node["var"] == old:
            return _copy(new)
        if ("forall" in node or "exists" in node):
            q = "forall" if "forall" in node else "exists"
            if node[q]["var"] == old:
                d = dict(node[q])
                d["lo"] = _subst_var(d["lo"], old, new)
                d["hi"] = _subst_var(d["hi"], old, new)
                return {q: d}          # the binder shadows: body is untouched
        return {k: _subst_var(v, old, new) for k, v in node.items()}
    if isinstance(node, list):
        return [_subst_var(v, old, new) for v in node]
    return node


def _int_rewrite(task, salt, wrap):
    """One int-typed body subexpression replaced by `wrap(e)`.

    SPEC.md: both versions use mathematical integers with no overflow, so
    `+ - * neg` are total and the identities below hold at every value. All of
    the wrappers are STRICT in `e` and introduce only closed literals, so a
    site where `e` is undefined stays undefined and no definedness obligation
    moves. The site excludes `decreases`: a rewritten measure is still the
    same function, but SPEC.md's termination obligation is stated on the
    measure's own expression and a lowering may legitimately syntax-match it."""
    cands = [p for p, _n, ty, kind in _all_body_sites(task)
             if ty == "int" and kind != "decreases"]
    p = _pick(task, salt, cands)
    if p is None:
        return None
    return _put(task, p, wrap(_get(task["body"], p))), {}


def t_add_zero(task):
    """e -> e + 0."""
    return _int_rewrite(task, "add0",
                        lambda e: {"op": "+", "args": [e, {"int": 0}]})


def t_mul_one(task):
    """e -> e * 1."""
    return _int_rewrite(task, "mul1",
                        lambda e: {"op": "*", "args": [e, {"int": 1}]})


def t_sub_zero(task):
    """e -> e - 0."""
    return _int_rewrite(task, "sub0",
                        lambda e: {"op": "-", "args": [e, {"int": 0}]})


def t_double_neg(task):
    """e -> neg (neg e)."""
    return _int_rewrite(task, "negneg",
                        lambda e: {"op": "neg",
                                   "args": [{"op": "neg", "args": [e]}]})


def t_comm_add(task):
    """a + b -> b + a.

    `+` is strict in both operands (SPEC.md gives non-strict evaluation only
    to and/or/implies/ite/forall/exists), so both forms are defined exactly
    when both operands are, and t has no side effects for an order to expose.
    Commutativity of addition over mathematical integers does the rest."""
    cands = [p for p, n, _t, kind in _all_body_sites(task)
             if n.get("op") == "+" and kind != "decreases"]
    p = _pick(task, "comm", cands)
    if p is None:
        return None
    n = _get(task["body"], p)
    return _put(task, p, {"op": "+", "args": n["args"][::-1]}), {}


def t_reassoc_add(task):
    """(a + b) + c -> a + (b + c). Same strictness argument as t_comm_add:
    all three operands are evaluated in both forms."""
    cands = [p for p, n, _t, kind in _all_body_sites(task)
             if n.get("op") == "+" and kind != "decreases"
             and n["args"][0].get("op") == "+"]
    p = _pick(task, "reassoc", cands)
    if p is None:
        return None
    n = _get(task["body"], p)
    a, b = n["args"][0]["args"]
    c = n["args"][1]
    return _put(task, p, {"op": "+",
                          "args": [a, {"op": "+", "args": [b, c]}]}), {}


def _bool_sites(task):
    return [p for p, _n, ty, _kind in _all_body_sites(task) if ty == "bool"]


def t_and_true(task):
    """c -> c and TRUE.

    SPEC.md: `and` is n-ary, left to right, and its k-th argument "need only
    be defined when no earlier argument decided the result". TRUE is a closed
    literal, defined everywhere, and it sits LAST, so the rewrite adds no
    definedness obligation to any earlier argument and removes none. The value
    is `c` because the conjunction is decided by `c` unless `c` is true."""
    p = _pick(task, "andT", _bool_sites(task))
    if p is None:
        return None
    return _put(task, p, {"op": "and", "args": [_get(task["body"], p),
                                                _true(task)]}), {}


def t_or_false(task):
    """c -> c or FALSE. Dual of t_and_true, on `or`'s left-to-right rule."""
    p = _pick(task, "orF", _bool_sites(task))
    if p is None:
        return None
    return _put(task, p, {"op": "or", "args": [_get(task["body"], p),
                                               _false(task)]}), {}


def t_not_not(task):
    """c -> not (not c). `not` is unary and strict, so definedness is
    unchanged, and double negation is the identity on bools."""
    p = _pick(task, "notnot", _bool_sites(task))
    if p is None:
        return None
    inner = {"op": "not", "args": [_get(task["body"], p)]}
    return _put(task, p, {"op": "not", "args": [inner]}), {}


def t_demorgan(task):
    """a1 and ... and an -> not (not a1 or ... or not an), and dually for `or`.

    The definedness obligation is the one that makes this non-trivial under
    SPEC.md. On the left, `a_k` need only be defined when a_1..a_{k-1} are all
    true. On the right, `not a_k` is reached only when `not a_1` .. `not
    a_{k-1}` are all false, i.e. when a_1..a_{k-1} are all true, the same
    condition, argument by argument. So the rewrite neither adds nor discharges
    a definedness obligation, and classical De Morgan gives the value."""
    cands = [p for p, n, _t, kind in _all_body_sites(task)
             if n.get("op") in ("and", "or") and kind != "decreases"]
    p = _pick(task, "demorgan", cands)
    if p is None:
        return None
    n = _get(task["body"], p)
    dual = "or" if n["op"] == "and" else "and"
    neg = [{"op": "not", "args": [a]} for a in n["args"]]
    return _put(task, p, {"op": "not", "args": [{"op": dual, "args": neg}]}), {}


def t_swap_if(task):
    """if c then A else B -> if not c then B else A.

    SPEC.md's `if` takes the branch the condition selects; `not` is total on
    bools and c is bool-typed by well-formedness, so the same branch runs in
    both forms and c's own definedness obligation is unchanged. This is the
    SEMANTICS-PRESERVING sibling of harness.py's NEGATE-COND twin operator,
    which swaps the branches WITHOUT negating and is therefore a mutation."""
    cands = [p for p, _s, _e, _k in _if_stmts(task)]
    p = _pick(task, "swapif", cands)
    if p is None:
        return None
    c = _get(task["body"], p)["if"]
    return _put(task, p, {"if": {"cond": {"op": "not", "args": [c["cond"]]},
                                 "then": c["else"], "else": c["then"]}}), {}


def _if_stmts(task):
    """(path, stmt, env, kind) for every `if` STATEMENT, pre-order."""

    def walk(body, env, path):
        env = dict(env)
        for i, s in enumerate(body):
            p = path + (i,)
            if "if" in s:
                yield p, s, env, "if"
                yield from walk(s["if"]["then"], env, p + ("if", "then"))
                yield from walk(s["if"]["else"], env, p + ("if", "else"))
            elif "while" in s:
                yield from walk(s["while"]["body"], env,
                                p + ("while", "body"))
            elif "var" in s:
                env = dict(env)
                env[s["var"]["name"]] = s["var"]["type"]

    return list(walk(task["body"], _body_env(task), ()))


def t_swap_cmp(task):
    """a < b -> b > a, a <= b -> b >= a, and the two mirrors.

    Not to be confused with harness.py's BOUNDARY-SWAP twin, which exchanges
    the operands and KEEPS the operator and is therefore a mutation. Here the
    operator is exchanged with its converse, which is the definition of the
    converse relation; both operands are evaluated in both forms (comparisons
    are strict), so definedness is unchanged."""
    conv = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}
    cands = [p for p, n, _t, kind in _all_body_sites(task)
             if n.get("op") in conv and kind != "decreases"]
    p = _pick(task, "swapcmp", cands)
    if p is None:
        return None
    n = _get(task["body"], p)
    return _put(task, p, {"op": conv[n["op"]],
                          "args": n["args"][::-1]}), {}


def _rw(stmt):
    """(reads, writes) of one statement, names only."""
    reads, writes = set(), set()

    def ex(n, bound):
        if isinstance(n, dict):
            if "var" in n and isinstance(n["var"], str):
                if n["var"] not in bound:
                    reads.add(n["var"])
                return
            for q in ("forall", "exists"):
                if q in n:
                    d = n[q]
                    ex(d["lo"], bound)
                    ex(d["hi"], bound)
                    ex(d["body"], bound | {d["var"]})
                    return
            for v in n.values():
                ex(v, bound)
        elif isinstance(n, list):
            for v in n:
                ex(v, bound)

    if "assign" in stmt:
        writes.add(stmt["assign"][0])
        ex(stmt["assign"][1], set())
    elif "var" in stmt:
        writes.add(stmt["var"]["name"])
        ex(stmt["var"]["init"], set())
    else:
        return None, None
    return reads, writes


def t_reorder(task):
    """Swap two ADJACENT INDEPENDENT statements.

    Independence is proved, not assumed, and only for the case where it is
    provable in one line: both statements are `assign` or `var` (no control
    flow, so no branch or loop body to reason about), and
    writes(S1) is disjoint from reads(S2) U writes(S2), and writes(S2) is
    disjoint from reads(S1). t has no heap and no aliasing (SPEC.md "What v1
    does not claim"), so name disjointness IS non-interference. Definedness
    survives too: neither statement can make the other defined, so if either
    is undefined the whole block is undefined in both orders. The pair is
    additionally required not to include the block's LAST statement, so the
    "must end every path in assign" rule cannot be broken by the swap, and a
    `var` that a later statement declares-then-uses is excluded by the
    disjointness test itself."""
    cands = []

    def walk(body, path):
        for i in range(len(body) - 2):
            r1, w1 = _rw(body[i])
            r2, w2 = _rw(body[i + 1])
            if r1 is None or r2 is None:
                continue
            if w1 & (r2 | w2) or w2 & r1:
                continue
            cands.append(path + (i,))
        for i, s in enumerate(body):
            p = path + (i,)
            if "if" in s:
                walk(s["if"]["then"], p + ("if", "then"))
                walk(s["if"]["else"], p + ("if", "else"))
            elif "while" in s:
                walk(s["while"]["body"], p + ("while", "body"))

    walk(task["body"], ())
    p = _pick(task, "reorder", cands)
    if p is None:
        return None
    out = _copy(task)
    node = out["body"]
    for k in p[:-1]:
        node = node[k]
    i = p[-1]
    node[i], node[i + 1] = node[i + 1], node[i]
    return out, {}


def t_let_copy(task):
    """Introduce a local initialised to a parameter and use it throughout.

    A t parameter is immutable: SPEC.md gate 2 says `assign` "now targets any
    return or local name in scope", and fuzz_lower.check_wf rejects an assign
    to anything else. So a local declared as the first statement of the body
    and initialised to `p` is equal to `p` at every later program point, and
    substituting it for every body occurrence of `p` changes no value. The
    local's name is fresh, so nothing is captured; `requires`/`ensures` are
    untouched and still name the parameter, which is still a parameter.
    v1 only; v0 has no local declarations."""
    if task["t"] != 1:
        return None
    ints = [p["name"] for p in task["params"] if p["type"] == "int"]
    if not ints:
        return None
    src = ints[_rng(task["name"], "letcopy").randrange(len(ints))]
    names = set()

    def collect(n):
        if isinstance(n, dict):
            for k, v in n.items():
                if k in ("var", "name", "fun") and isinstance(v, str):
                    names.add(v)
                else:
                    collect(v)
        elif isinstance(n, list):
            for v in n:
                collect(v)

    collect(task)
    cp, k = "mmcp0", 0
    while cp in names:
        k += 1
        cp = f"mmcp{k}"
    out = _copy(task)
    out["body"] = _subst_var(out["body"], src, {"var": cp})
    out["body"].insert(0, {"var": {"name": cp, "type": "int",
                                   "init": {"var": src}}})
    return out, {}


def t_pad(task):
    """Add a statement that cannot change the result.

    v1: an unused local. It is never read and never reassigned, so no
    expression's value depends on it and no path's return value can move.
    v0: v0 has no locals, and lower_rocq.py's body_expr0 requires a v0 body to
    be ONE statement (measured: appending a statement makes it raise, which
    run_all records as LOWER-ERROR rather than a verdict), so the v0 padding is
    a tautological guard around the whole body instead, `if TRUE then B else
    B`. The condition is a closed comparison, defined everywhere and true, so
    the then-branch runs and B is exactly what ran before; the else-branch is
    the same B, so the rewrite is value-preserving even read as a plain `if`."""
    out = _copy(task)
    if task["t"] == 1:
        names = set()

        def collect(n):
            if isinstance(n, dict):
                for k, v in n.items():
                    if k in ("var", "name", "fun") and isinstance(v, str):
                        names.add(v)
                    else:
                        collect(v)
            elif isinstance(n, list):
                for v in n:
                    collect(v)

        collect(task)
        pad, k = "mmpad0", 0
        while pad in names:
            k += 1
            pad = f"mmpad{k}"
        out["body"].insert(0, {"var": {"name": pad, "type": "int",
                                       "init": {"int": 0}}})
    else:
        out["body"] = [{"if": {"cond": _copy(TRUE0),
                               "then": _copy(task["body"]),
                               "else": _copy(task["body"])}}]
    return out, {}


def t_self_assign(task):
    """Append `assign r := r`, which reads the return at a point where every
    path has already assigned it (SPEC.md: the body "must end every path in
    assign") and writes back the value it just read. Applied only when the
    body's last top-level statement is already an assign to the return, so
    that precondition is syntactically checked and not assumed. v1 only, for
    lower_rocq.py's one-statement v0 body rule."""
    if task["t"] != 1:
        return None
    ret = task["returns"][0]["name"]
    last = task["body"][-1] if task["body"] else None
    if not (isinstance(last, dict) and "assign" in last
            and last["assign"][0] == ret):
        return None
    out = _copy(task)
    out["body"].append({"assign": [ret, {"var": ret}]})
    return out, {}


def t_spec_add_zero(task):
    """The same `e -> e + 0` identity, but inside an `ensures` clause.

    The body rewrites test the lowering's statement path; the spec is a
    separate translation with its own operator table in every one of the seven
    lowerings, and a verdict that moves here is a defect in that path. The
    postcondition denotes the same predicate, so the proof obligation is the
    same obligation."""
    ver, funs = task["t"], _funs(task)
    env = _body_env(task)
    cands = []
    for i, e in enumerate(task["ensures"]):
        for sp, _n, ty, _sc in _sites(e, env, funs, ver, (i,)):
            if ty == "int":
                cands.append(sp)
    p = _pick(task, "specadd0", cands)
    if p is None:
        return None
    out = _copy(task)
    node = out["ensures"]
    for k in p[:-1]:
        node = node[k]
    node[p[-1]] = {"op": "+", "args": [_copy(node[p[-1]]), {"int": 0}]}
    return out, {}


def _spec_rewrite(task, field, salt, want, wrap):
    """One clause of `requires`/`ensures` rewritten in place.

    The body rewrites exercise a lowering's statement path; `requires` and
    `ensures` go through a separate translation with its own operator table in
    every one of the seven, and an equivalent clause is the same obligation, so
    a verdict that moves here is a defect in that path."""
    ver, funs = task["t"], _funs(task)
    env = ({p["name"]: p["type"] for p in task["params"]} if field == "requires"
           else _body_env(task))
    cands = []
    for i, e in enumerate(task.get(field, [])):
        for sp, _n, ty, _sc in _sites(e, env, funs, ver, (i,)):
            if ty == want:
                cands.append(sp)
    p = _pick(task, salt, cands)
    if p is None:
        return None
    out = _copy(task)
    node = out[field]
    for k in p[:-1]:
        node = node[k]
    node[p[-1]] = wrap(_copy(node[p[-1]]), out)
    return out, {}


def t_req_or_false(task):
    """A `requires` clause c -> c or FALSE, by the same left-to-right rule as
    t_or_false. The precondition denotes the same set of inputs, so the same
    inputs are admitted and the same obligation is owed."""
    return _spec_rewrite(task, "requires", "reqorF", "bool",
                         lambda e, t: {"op": "or", "args": [e, _false(t)]})


def t_spec_not_not(task):
    """An `ensures` subformula c -> not (not c)."""
    return _spec_rewrite(task, "ensures", "specnn", "bool",
                         lambda e, t: {"op": "not", "args":
                                       [{"op": "not", "args": [e]}]})


TRANSFORMS = [
    ("rename", t_rename),
    ("add-zero", t_add_zero),
    ("mul-one", t_mul_one),
    ("sub-zero", t_sub_zero),
    ("double-neg", t_double_neg),
    ("comm-add", t_comm_add),
    ("reassoc-add", t_reassoc_add),
    ("and-true", t_and_true),
    ("or-false", t_or_false),
    ("not-not", t_not_not),
    ("de-morgan", t_demorgan),
    ("swap-if", t_swap_if),
    ("swap-cmp", t_swap_cmp),
    ("reorder", t_reorder),
    ("let-copy", t_let_copy),
    ("pad", t_pad),
    ("self-assign", t_self_assign),
    ("spec-add-zero", t_spec_add_zero),
    ("spec-not-not", t_spec_not_not),
    ("req-or-false", t_req_or_false),
]


# ---------------------------------------------------------------------------
# The tripwire. NOT the justification; see the module docstring.
# ---------------------------------------------------------------------------

def _observe(task, env0, ret):
    """What SPEC.md says is observable about one run: the return value, or the
    definedness/annotation failure that replaced it, plus each ensures clause.
    Budget exhaustion is not an observation: the padded variant costs a step
    more, so a run that hits the cap on one side and not the other is dropped
    rather than compared."""
    funs = fz._funs_of(task, task["body"])
    st = fz.St()
    try:
        if not all(fz.ev(c, env0, funs, st) for c in task.get("requires", [])):
            return ("req-false",)
    except fz.Undef:
        return ("req-undef",)
    except (fz.Budget, RecursionError):
        return None
    env = dict(env0)
    env[ret] = None
    try:
        fz.exec_body(task["body"], env, funs, st, True)
    except fz.Violation as v:
        return ("violation", v.kind)
    except fz.Undef:
        return ("body-undef",)
    except (fz.Budget, RecursionError):
        return None
    try:
        ens = tuple(bool(fz.ev(e, env, funs, st)) for e in task["ensures"])
    except fz.Undef:
        return ("value", fz._j(env[ret]), "ens-undef")
    except (fz.Budget, RecursionError):
        return None
    return ("value", fz._j(env[ret]), ens)


def _equivalent(base, variant, name_map, rng, k=120):
    """Bounded cross-check of a transformation against the interpreter.

    A disagreement PROVES the rewrite is not meaning-preserving and the
    transformation is withdrawn. Agreement proves nothing; it is a tripwire on
    the argument in the transformation's docstring, and the argument is what
    the soundness of this instrument rests on."""
    ret_b = base["returns"][0]["name"]
    ret_v = variant["returns"][0]["name"]
    for env0 in fz.sample_inputs(base, rng, k):
        a = _observe(base, env0, ret_b)
        env1 = {name_map.get(n, n): v for n, v in env0.items()}
        b = _observe(variant, env1, ret_v)
        if a is None or b is None:
            continue
        if a != b:
            return {"input": {n: fz._j(v) for n, v in env0.items()},
                    "base": str(a), "variant": str(b)}
    return None


# ---------------------------------------------------------------------------
# Corpus. Base tasks come from fuzz_lower's generator (so the shapes are the
# ones the suite already exercises) plus tasks whose postcondition is BUILT
# FROM the body, which are true for all inputs by construction and not by
# sampling, and their witnessed-false mutants.
# ---------------------------------------------------------------------------

def constructed(rng, k):
    """Tasks whose `ensures` is derived FROM the body, so truth is a property
    of the construction and not of any search.

    fuzz_lower.f_v0if already builds exactly this: it walks the body's own
    paths and emits one clause `pc implies r == val` per leaf `assign r :=
    val`, with `pc` the conjunction of the conditions along that path and the
    else-arm's condition negated by fuzz_lower._negate (NEGCMP for a
    comparison, `not` otherwise, an exact negation, since every v0 operator
    is total). The body assigns `val` to `r` exactly on the inputs where `pc`
    holds, so every clause is true at EVERY input, and `requires` is empty so
    "every input" is not narrowed. v0 has no partial operator (SPEC.md admits
    `at` in v1 only), so no definedness side condition attaches. Nothing here
    appeals to a bounded search, which is the point: a bounded search is a
    sound proof of falsity and never of truth."""
    out = []
    for i in range(k):
        t = fz.f_v0if(rng, 10_000 + i)
        t["name"] = f"mm_true{i}"
        t["requires"] = []
        if fz.check_wf(t):
            continue
        t["_family"] = "constructed-true"
        t["_truth"] = "true-by-construction"
        out.append(t)
    return out


def falsified(tasks, rng):
    """A known-true task whose postcondition is broken, with the interpreter
    exhibiting an input that falsifies it. ONE counterexample is a sound proof
    of falsity; this is the only direction a bounded search may be used in."""
    out = []
    for t in tasks:
        for j in range(len(t["ensures"])):
            f = _copy(t)
            f["name"] = t["name"].replace("true", "false")
            ej = f["ensures"][j]
            # Break the equality inside the (implication-guarded) clause; the
            # guard is left alone so the clause is still REACHABLE.
            tgt = ej["args"][1] if ej.get("op") == "implies" else ej
            if tgt.get("op") != "==":
                continue
            tgt["args"][1] = {"op": "+", "args": [_copy(tgt["args"][1]),
                                                  {"int": 1}]}
            if fz.check_wf(f):
                continue
            gt = fz.ground_truth(f, f["body"], rng, k=600)
            if gt["verdict"] != "refuted" or not gt["cex"]:
                continue        # no witness on this clause: try the next one
            f["_family"] = "constructed-false"
            f["_truth"] = "false-by-witness"
            f["_cex"] = gt["cex"]
            f["_cex_kind"] = gt["kind"]
            f["_broken_clause"] = j
            out.append(f)
            break
    return out


def build_bases(n: int, seed: int):
    rng = random.Random(seed)
    tr = constructed(rng, max(4, n // 6))
    fa = falsified(tr, rng)
    gen = []
    corpus = fz.build_corpus(n, seed)
    for t in corpus:
        if t.get("_wf_errors") or t.get("_family") in (None, "probe"):
            continue
        if t.get("_expect") not in ("verified", "refuted"):
            continue
        kind = str((t.get("_gt") or {}).get("kind") or "")
        if t["_expect"] == "refuted":
            # `false-by-witness` is a SOUNDNESS label, so it is spent only on
            # a counterexample to the POSTCONDITION. fuzz_lower.ground_truth
            # also reports `invariant`, `decreases`, `undefined-body` and
            # `undefined-ensures`: those are broken annotations or failed
            # definedness obligations, which every kernel refuses for its own
            # reason and which say nothing about the postcondition being
            # false. Keeping them would let a kernel's VERIFIED be called an
            # unsoundness on evidence that does not support it.
            if not kind.startswith("ensures["):
                continue
            t["_truth"] = "false-by-witness"
            t["_cex"] = (t.get("_gt") or {}).get("cex")
            t["_cex_kind"] = kind
        else:
            t["_truth"] = "true-on-sampled-inputs-only"
        gen.append(t)
    rng.shuffle(gen)
    return tr + fa + gen[:n]


def variants_of(task, rng):
    """(label, variant_task) for every transformation that applies and passes
    the tripwire. A tripwire hit is recorded on the task, not thrown away."""
    out, bugs = [], []
    for label, fn in TRANSFORMS:
        try:
            r = fn(_copy(task))
        except Exception as e:                            # noqa: BLE001
            bugs.append({"task": task["name"], "transform": label,
                         "error": f"{type(e).__name__}: {e}"})
            continue
        if r is None:
            continue
        v, nmap = r
        errs = fz.check_wf({k: x for k, x in v.items()
                            if not k.startswith("_")})
        if errs:
            bugs.append({"task": task["name"], "transform": label,
                         "error": f"variant not well formed: {errs[:3]}"})
            continue
        bad = _equivalent(task, v, nmap, rng)
        if bad:
            bugs.append({"task": task["name"], "transform": label,
                         "error": "TRIPWIRE: interpreter separates base from "
                                  "variant", "detail": bad})
            continue
        out.append((label, v))
    return out, bugs


# ---------------------------------------------------------------------------
# Runner. One subdirectory per case, identical task name inside it.
# ---------------------------------------------------------------------------

def _cell(bname: str, path: str, n: int):
    backend = importlib.import_module(f"verifiers.{bname}")
    p = Path(path)
    if n == 1:
        r = backend.verify(p)
        return bname, str(p), r.outcome, True, r.wall_ms
    r, agreed = flake_check(backend.verify, p, n)
    return bname, str(p), r.outcome, agreed, r.wall_ms


def prepare(cases, outdir: Path, present):
    """Lower every case for every kernel, sequentially, before any dispatch:
    a single writer for the whole time the sources are produced."""
    pending, notes = [], {}
    for cid, task in cases:
        d = outdir / cid
        d.mkdir(parents=True, exist_ok=True)
        clean = {k: v for k, v in task.items() if not k.startswith("_")}
        (d / "task.json").write_text(json.dumps(clean, indent=1))
        for bname, lower, sfx in present:
            try:
                src = lower(clean, clean["body"])
            except NotImplementedError as e:
                notes[(cid, bname)] = ("abstain", f"{e}"[:160])
                continue
            except Exception as e:                        # noqa: BLE001
                notes[(cid, bname)] = ("lower-error",
                                       f"{type(e).__name__}: {e}"[:160])
                continue
            p = d / f"{clean['name']}.{sfx}"
            p.write_text(src, encoding="utf-8")
            pending.append((bname, str(p), cid))
    return pending, notes


def run_cells(pending, jobs, n_flake, label="", checkpoint: Path | None = None):
    """Every finished cell is appended to `checkpoint` as it lands.

    Measured 2026-09-01 on the training box: a sweep of 8798 cells sharing the
    machine with two other campaigns fell from 17 cells/s to 1.9 cells/s, so a
    result held only in memory until the last cell is a result that a kill
    loses entirely. The file is JSONL and append-only for that reason: a
    partial sweep still has every verdict it paid for."""
    res = {}
    t0 = time.time()
    fh = open(checkpoint, "a", encoding="utf-8") if checkpoint else None
    ctx = mp_context()
    try:
        with ProcessPoolExecutor(max_workers=jobs, mp_context=ctx) as ex:
            futs = {ex.submit(_cell, b, p, n_flake): (b, p, cid)
                    for b, p, cid in pending}
            done = 0
            for fut in as_completed(futs):
                bname, path, outcome, agreed, ms = fut.result()
                cid = futs[fut][2]
                res[(cid, bname)] = (outcome, agreed, ms)
                if fh:
                    fh.write(json.dumps([cid, bname, outcome, agreed, ms])
                             + "\n")
                    fh.flush()
                done += 1
                if done % 100 == 0:
                    print(f"  {label}{done}/{len(pending)} cells, "
                          f"{time.time() - t0:.0f}s", flush=True)
    finally:
        if fh:
            fh.close()
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True,
                    help="output directory; NEVER t/out/, the suite owns it")
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--jobs", type=int,
                    default=max(1, (os.cpu_count() or 8) // 3))
    ap.add_argument("--flake", type=int, default=3,
                    help="re-runs when confirming a variance")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    outdir = Path(args.out).resolve()
    if outdir == (HERE / "out").resolve():
        print("REFUSED: t/out/ belongs to run_all.py/run_par.py.")
        return 2
    outdir.mkdir(parents=True, exist_ok=True)

    only = set(args.only.split(",")) if args.only else None
    present, cols = [], []
    for bname, lmod, sfx in BACKENDS:
        if only and bname not in only:
            continue
        try:
            be = importlib.import_module(f"verifiers.{bname}")
            cols.append((bname, be.version()))
            present.append((bname, importlib.import_module(lmod).lower, sfx))
        except (Exception, SystemExit) as e:              # noqa: BLE001
            cols.append((bname, f"ABSENT: {e}"))
    if len(present) < 2:
        print("REFUSED: fewer than two kernels present; invariance across one "
              "kernel is one opinion, not an invariance.")
        return 2

    rng = random.Random(args.seed * 7919 + 1)
    bases = build_bases(args.n, args.seed)
    cases, index, bugs = [], {}, []
    for i, task in enumerate(bases):
        bid = f"b{i:03d}"
        cases.append((f"{bid}.base", task))
        vs, b = variants_of(task, rng)
        bugs += b
        index[bid] = {"task": task["name"], "family": task.get("_family"),
                      "truth": task.get("_truth"),
                      "cex": task.get("_cex"), "cex_kind": task.get("_cex_kind"),
                      "variants": [lab for lab, _ in vs]}
        for lab, v in vs:
            cases.append((f"{bid}.{lab}", v))
    print(f"bases: {len(bases)}  cases: {len(cases)}  "
          f"transform bugs: {len(bugs)}")
    for b in bugs[:20]:
        print(f"  TRANSFORM-BUG {b['task']} [{b['transform']}]: {b['error']}")

    pending, notes = prepare(cases, outdir, present)
    print(f"cells: {len(pending)} (+{len(notes)} lower-error/abstain), "
          f"jobs={args.jobs}")
    res = run_cells(pending, args.jobs, 1,
                    checkpoint=outdir / "cells.jsonl")

    def verdict(cid, bname):
        if (cid, bname) in notes:
            return notes[(cid, bname)][0]
        c = res.get((cid, bname))
        return c[0] if c else "missing"

    variances, incomplete, coverage = [], [], []
    for bid, meta in index.items():
        for bname, _l, _s in present:
            base_v = verdict(f"{bid}.base", bname)
            for lab in meta["variants"]:
                vv = verdict(f"{bid}.{lab}", bname)
                if vv == base_v:
                    continue
                rec = {"base": bid, "task": meta["task"],
                       "family": meta["family"], "truth": meta["truth"],
                       "transform": lab, "kernel": bname,
                       "base_verdict": base_v, "variant_verdict": vv,
                       "cex": meta["cex"], "cex_kind": meta["cex_kind"]}
                if base_v in DECISIVE and vv in DECISIVE:
                    variances.append(rec)
                elif (base_v in INCOMPLETE) or (vv in INCOMPLETE):
                    incomplete.append(rec)
                else:
                    coverage.append(rec)

    # Flake discipline: a variance is re-measured at n=flake on BOTH halves
    # before it is reported. verifiers.flake_check refuses a witness whose own
    # outcome moved across runs, and a verdict that does not reproduce is
    # noise, not a finding.
    confirmed = []
    if variances:
        recheck = []
        for v in variances:
            for cid in (f"{v['base']}.base", f"{v['base']}.{v['transform']}"):
                p = _case_path(outdir, cid, index[v["base"]]["task"],
                               dict((b, s) for b, _l, s in present)[v["kernel"]])
                if p is not None:
                    recheck.append((v["kernel"], str(p), cid))
        recheck = sorted(set(recheck))
        print(f"re-measuring {len(recheck)} halves at n={args.flake}")
        r2 = run_cells(recheck, min(args.jobs, len(recheck) or 1),
                       args.flake, "flake ",
                       checkpoint=outdir / "flake.jsonl")
        for v in variances:
            a = r2.get((f"{v['base']}.base", v["kernel"]))
            b = r2.get((f"{v['base']}.{v['transform']}", v["kernel"]))
            v["reconfirm"] = {"base": a, "variant": b}
            if a and b and a[1] and b[1] and a[0] != b[0]:
                v["status"] = "CONFIRMED"
                confirmed.append(v)
            else:
                v["status"] = "NOT-REPRODUCED"

    report = {"backends": cols, "n_bases": len(bases), "n_cases": len(cases),
              "n_cells": len(pending), "index": index,
              "transform_bugs": bugs,
              "variances": variances, "confirmed": confirmed,
              "incompleteness": incomplete, "coverage": coverage,
              "oracle": _oracle(index, present, verdict)}
    (outdir / "report.json").write_text(json.dumps(report, indent=1))
    (outdir / "cells.json").write_text(json.dumps(
        {f"{k[0]}|{k[1]}": v for k, v in res.items()}, indent=1))

    print(f"\nvariance (decisive verdict moved): {len(variances)}  "
          f"CONFIRMED at n={args.flake}: {len(confirmed)}")
    for v in confirmed:
        print(f"  VARIANCE {v['task']} [{v['transform']}] {v['kernel']}: "
              f"{v['base_verdict']} -> {v['variant_verdict']}  "
              f"({v['truth']})")
    print(f"incompleteness (a side is timeout/unproved/tool_error): "
          f"{len(incomplete)}")
    print(f"coverage (a side is lower-error/abstain): {len(coverage)}")
    o = report["oracle"]
    print(f"oracle: known-false bases VERIFIED by a kernel: "
          f"{len(o['unsound'])}; known-true-by-construction bases not "
          f"VERIFIED: {len(o['true_not_verified'])}")
    for u in o["unsound"]:
        print(f"  UNSOUND {u['case']} {u['kernel']}: verified a task false "
              f"at {u['cex']}")
    return 0


def _case_path(outdir: Path, cid: str, taskname: str, sfx: str):
    p = outdir / cid / f"{taskname}.{sfx}"
    return p if p.exists() else None


def _oracle(index, present, verdict):
    """The ground-truth arm that runs alongside the invariance arm at no extra
    cost, because the cells are already measured. Only the FALSE direction is
    a soundness claim: a task with an exhibited counterexample is false for
    all time, so VERIFIED on it is an unsoundness. The TRUE direction is a
    claim only for the by-construction tasks; a `true-on-sampled-inputs-only`
    base that a kernel refutes is not a finding here, because the bounded
    search that labelled it never proved it true.

    The label is read off the BASE and applied to its variants, which is sound
    exactly because the rewrites preserve meaning: the witness that falsifies
    the base's postcondition falsifies the variant's, since the two denote the
    same predicate at the same input."""
    unsound, tnv = [], []
    for bid, meta in index.items():
        for bname, _l, _s in present:
            for cid in [f"{bid}.base"] + [f"{bid}.{x}" for x in
                                          meta["variants"]]:
                v = verdict(cid, bname)
                if meta["truth"] == "false-by-witness" and v == Outcome.VERIFIED:
                    unsound.append({"case": cid, "task": meta["task"],
                                    "kernel": bname, "cex": meta["cex"],
                                    "cex_kind": meta["cex_kind"]})
                if (meta["truth"] == "true-by-construction"
                        and v not in (Outcome.VERIFIED,)):
                    tnv.append({"case": cid, "task": meta["task"],
                                "kernel": bname, "outcome": v})
    return {"unsound": unsound, "true_not_verified": tnv}


if __name__ == "__main__":
    raise SystemExit(main())
