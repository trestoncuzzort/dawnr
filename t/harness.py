"""t/harness.py: the backend-independent part of running a t task.

One implementation of: task loading, the twin operators, the flake
discipline, and the flip rule (real VERIFIED and twin REFUTED, or the task
is refused). Lowering files supply only syntax; verdicts come only from
t.verifiers backends.

Twin operators (SPEC.md "The twins", v2, the ladder below, tried in order):
  INVARIANT-DROP  (v1): delete one invariant of one loop (pre-order).
  COLLAPSE-IF     (v0): replace one `if` (pre-order) with its then-branch.
  NEGATE-COND         : swap one `if`'s branches, which is `not cond`.
  COMPARE-FLIP        : `<`<->`<=`, `>`<->`>=` in one executable expression.
  BOUNDARY-SWAP       : swap the operands of one order comparison.
  OFF-BY-ONE          : +/-1 on one literal, `at` index, or loop bound.
  WRONG-VAR           : one variable occurrence replaced by another one, or
                        (SPEC.md "Pairs", 2026-09-10) a pair's two components
                        swapped, or `fst`/`snd` swapped in one projection.
  DROP-GUARD          : drop one conjunct of an `if`/`while` condition.
  WRONG-CONSTANT      : (SPEC.md "The twins", the twin-ladder wave,
                        2026-09-11) `expr +- 1` at one assign/return
                        right-hand side or `var` initialiser proved
                        int-typed, the mutation a straight-line body with
                        no `if`, no loop, no literal, and no `at`/`update`/
                        `fill`/`slice` admits, so it is never reached by
                        OFF-BY-ONE.
  WRONG-OPERATOR      : one arithmetic operator (`+`, `-`, `*`, `div`,
                        `mod`) replaced by another from a fixed per-operator
                        list, at the same sites COMPARE-FLIP walks.

Both sit below every rung above: a task whose twin was already found by an
earlier rung keeps that exact twin, byte-identical (the 34 tasks committed
under t/tasks are the check).

Selection is derived from the body, never configured per task, and is
deterministic: operators in the fixed order above, sites within an operator in
the pre-order `collapse_first_if` already used, and the FIRST candidate with a
WITNESS wins. So the same task always yields the same twin, and the first two
rungs reproduce the v1 rule exactly wherever it was already load-bearing.

A witness is a measurement, not an assumption (t/interp.py; the house rule
applied to the harness itself). Measured over 1395 generated tasks from
fuzz_lower.py (7 seeds x 200), 129 twins, 9.2%, computed the same value
as the real program on every input tested: for those the "measured flip"
measured nothing, since no behavioural difference existed for a kernel to
detect. So:
  - a value-changing operator is accepted only with an input where the real
    body and the twin return different values (or the twin is undefined where
    the real body has a value);
  - INVARIANT-DROP, whose twin computes the SAME value by construction, is
    accepted only with a loop state the surviving invariants no longer cover
    (exit entailment or preservation).
No witness on any rung and the task is REFUSED: an unmeasurable twin is
reported as such rather than passed off as a flip.

The twin NEVER touches `requires`, `ensures`, `spec_funs`, or `decreases`:
the spec is the fixed instrument, the body (and its proof annotations) is
what gets broken.
"""
from __future__ import annotations

import json
from pathlib import Path

import interp
import tasks_io
from verifiers import Outcome, cell_pair

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"

KNOWN_VERSIONS = tasks_io.KNOWN_VERSIONS


def load(path: Path) -> dict:
    """A task, from a .t file (ROADMAP 14.1: surface.parse) or a .json one
    (a directory not yet converted, such as a spec-experiment run's own
    generated tasks/). tasks_io.load_task does the reading and the version
    check; this wrapper is kept so every existing `harness.load(...)` call
    site is unchanged."""
    return tasks_io.load_task(path)


def collapse_first_if(body: list) -> tuple[list, bool]:
    """v0 twin operator, pre-order: the first `if` encountered is replaced by
    its then-branch. Descends into `while` bodies (v1) so a loop containing
    the only `if` is still mutable; v0 tasks (top-level `if`, no loops) get
    byte-identical behavior to the original v0 operator."""
    out, done = [], False
    for s in body:
        if not done and "if" in s:
            out.extend(s["if"]["then"])
            done = True
        elif not done and "while" in s:
            inner, hit = collapse_first_if(s["while"]["body"])
            if hit:
                w = dict(s["while"])
                w["body"] = inner
                s = {"while": w}
                done = True
            out.append(s)
        else:
            out.append(s)
    return out, done


def drop_first_invariant(body: list) -> tuple[list, bool]:
    """v1 twin operator, pre-order: the first `while` that states any
    invariant loses its FIRST invariant. Everything else is untouched."""
    out, done = [], False
    for s in body:
        if not done and "while" in s and s["while"].get("invariants"):
            w = dict(s["while"])
            w["invariants"] = w["invariants"][1:]
            out.append({"while": w})
            done = True
        elif not done and "while" in s:
            inner, hit = drop_first_invariant(s["while"]["body"])
            w = dict(s["while"])
            w["body"] = inner
            out.append({"while": w})
            done = hit
        elif not done and "if" in s:
            c = s["if"]
            then2, hit = drop_first_invariant(c["then"])
            if hit:
                out.append({"if": {"cond": c["cond"],
                                   "then": then2, "else": c["else"]}})
                done = True
            else:
                else2, hit2 = drop_first_invariant(c["else"])
                out.append({"if": {"cond": c["cond"],
                                   "then": c["then"], "else": else2}})
                done = hit2
        else:
            out.append(s)
    return out, done


def _has_invariant_loop(body: list) -> bool:
    for s in body:
        if "while" in s:
            if s["while"].get("invariants"):
                return True
            if _has_invariant_loop(s["while"]["body"]):
                return True
        elif "if" in s:
            if (_has_invariant_loop(s["if"]["then"])
                    or _has_invariant_loop(s["if"]["else"])):
                return True
    return False


# ---------------------------------------------------------------------------
# The mutation ladder. Sites are enumerated in the same pre-order
# collapse_first_if uses, so rung 1 site 0 IS drop_first_invariant and rung 2
# site 0 IS collapse_first_if; a task whose v1 twin already had a witness
# keeps that exact twin.
# ---------------------------------------------------------------------------

MAX_CANDIDATES = 400      # ladder budget per task; the search is otherwise
                          # unbounded in wrong-var, which is quadratic in the
                          # number of names in scope.

FLIP = {"<": "<=", "<=": "<", ">": ">=", ">=": ">"}
ORDER_OPS = ("<", "<=", ">", ">=")


def _copy(o):
    return json.loads(json.dumps(o))       # a t body is pure JSON


def _replace(body: list, path: tuple, new):
    """`body` with the subtree at `path` replaced; `body` is not mutated."""
    out = _copy(body)
    node = out
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = _copy(new)
    return out


def _splice(body: list, path: tuple, stmts: list):
    """`body` with the STATEMENT at `path` replaced by `stmts` in place."""
    out = _copy(body)
    node = out
    for k in path[:-1]:
        node = node[k]
    i = path[-1]
    node[i:i + 1] = _copy(stmts)
    return out


def _stmts(body: list, scope: list, prefix: tuple = ()):
    """Pre-order over statements: statement, then into `if` branches and
    `while` bodies, yielding (path, stmt, scope), where scope is the
    (name, type) pairs a substitution at that statement may use. A `var`
    statement is yielded BEFORE its own name enters scope: its initialiser
    cannot see it."""
    sc = list(scope)
    for i, s in enumerate(body):
        p = prefix + (i,)
        yield p, s, list(sc)
        if "var" in s:
            sc.append((s["var"]["name"], s["var"]["type"]))
        elif "if" in s:
            yield from _stmts(s["if"]["then"], sc, p + ("if", "then"))
            yield from _stmts(s["if"]["else"], sc, p + ("if", "else"))
        elif "while" in s:
            yield from _stmts(s["while"]["body"], sc, p + ("while", "body"))


def _exprs(body: list, scope: list):
    """Pre-order over the expressions a twin may break: `if`/`while`
    conditions, assignment right-hand sides, local initialisers. Never
    `invariants` or `decreases`, because dropping an invariant is INVARIANT-DROP's
    job, and a rewritten `decreases` would break termination rather than the
    thing under test. Yields (path, expr, scope, kind)."""
    for p, s, sc in _stmts(body, scope):
        if "assign" in s:
            yield p + ("assign", 1), s["assign"][1], sc, "rhs"
        elif "return" in s:
            yield p + ("return", 1), s["return"][1], sc, "rhs"
        elif "var" in s:
            yield p + ("var", "init"), s["var"]["init"], sc, "init"
        elif "if" in s:
            yield p + ("if", "cond"), s["if"]["cond"], sc, "cond-if"
        elif "while" in s:
            yield p + ("while", "cond"), s["while"]["cond"], sc, "cond-while"


def _sub(e: dict, path: tuple):
    """Pre-order over an expression and its subexpressions."""
    yield path, e
    if "op" in e:
        for i, a in enumerate(e["args"]):
            yield from _sub(a, path + ("args", i))
    elif "ite" in e:
        for k in ("cond", "then", "else"):
            yield from _sub(e["ite"][k], path + ("ite", k))
    elif "forall" in e or "exists" in e:
        q = "forall" if "forall" in e else "exists"
        for k in ("lo", "hi", "body"):
            yield from _sub(e[q][k], path + (q, k))
    elif "call" in e:
        for i, a in enumerate(e["call"]["args"]):
            yield from _sub(a, path + ("call", "args", i))


def _c_collapse_if(body, scope):
    for p, s, _ in _stmts(body, scope):
        if "if" in s:
            yield _splice(body, p, s["if"]["then"])


def _c_negate_cond(body, scope):
    # `not cond` is realised as a branch swap: identical semantics, and it
    # introduces no operator a lowering may reject (fuzz_lower.py records
    # lower_rocq.py's cond_bool0 refusing a boolean connective in a v0
    # condition, so a literal `not` would turn a REFUTED cell into a
    # LOWER-ERROR one and lose the flip).
    for p, s, _ in _stmts(body, scope):
        if "if" in s:
            c = s["if"]
            yield _replace(body, p, {"if": {"cond": c["cond"],
                                            "then": c["else"],
                                            "else": c["then"]}})


def _c_compare_flip(body, scope):
    for path, e, _, _k in _exprs(body, scope):
        for sp, node in _sub(e, path):
            if node.get("op") in FLIP:
                yield _replace(body, sp, {"op": FLIP[node["op"]],
                                          "args": node["args"]})


def _c_boundary_swap(body, scope):
    for path, e, _, _k in _exprs(body, scope):
        for sp, node in _sub(e, path):
            if node.get("op") in ORDER_OPS:
                yield _replace(body, sp, {"op": node["op"],
                                          "args": node["args"][::-1]})


def _c_off_by_one(body, scope):
    for path, e, _, kind in _exprs(body, scope):
        for sp, node in _sub(e, path):
            if "int" in node:
                for d in (1, -1):
                    yield _replace(body, sp, {"int": node["int"] + d})
            elif node.get("op") in ("at", "update"):
                # The index of a read or of a functional update (SPEC.md
                # "Sequences as values"): s[i +- 1 := v] writes the wrong slot.
                for d in (1, -1):
                    yield _replace(body, sp + ("args", 1),
                                   {"op": "+", "args": [node["args"][1],
                                                        {"int": d}]})
            elif node.get("op") == "fill":
                # seq(n +- 1, v): the wrong length.
                for d in (1, -1):
                    yield _replace(body, sp + ("args", 0),
                                   {"op": "+", "args": [node["args"][0],
                                                        {"int": d}]})
            elif node.get("op") == "slice":
                # s[a +- 1 .. b] and s[a .. b +- 1] (SPEC.md "Sequences:
                # literals, concatenation, slices"): the wrong window, one
                # element too many or too few at either end.
                for k in (1, 2):
                    for d in (1, -1):
                        yield _replace(body, sp + ("args", k),
                                       {"op": "+", "args": [node["args"][k],
                                                            {"int": d}]})
            elif node.get("op") in ORDER_OPS and kind == "cond-while":
                # The loop bound: `i < len(s)` has no literal to move.
                for d in (1, -1):
                    yield _replace(body, sp + ("args", 1),
                                   {"op": "+", "args": [node["args"][1],
                                                        {"int": d}]})


def _c_wrong_var(body, scope):
    # Params and locals only, on BOTH sides of the substitution. The return
    # name is not a target: a body that reads it before its first assignment
    # is ill-formed rather than wrong, and a lowering rejects it instead of
    # refuting it, which loses the flip. It is not a source either, nor is a
    # quantifier's bound variable, because neither carries a declared type
    # here, and substituting across types would emit a twin no lowering can
    # even typecheck.
    #
    # SPEC.md "Pairs" (2026-09-10) gives this same rung one more move, at
    # zero new syntax: a `pair` node with its two components swapped, and a
    # `fst`/`snd` projection with the other one substituted. Both read the
    # OTHER thing already in reach at that site, exactly what a var-for-var
    # substitution does; `_sub`'s generic op/args walk already reaches these
    # nodes; no `at`/`slice`/`update` treatment is needed here, only these
    # two new node shapes.
    for path, e, sc, _k in _exprs(body, scope):
        ty_of = dict(sc)
        for sp, node in _sub(e, path):
            if "var" in node and node["var"] in ty_of:
                ty = ty_of[node["var"]]
                for alt, alt_ty in sc:
                    if alt != node["var"] and alt_ty == ty:
                        yield _replace(body, sp, {"var": alt})
            elif node.get("op") == "pair":
                a, b = node["args"]
                yield _replace(body, sp, {"op": "pair", "args": [b, a]})
            elif node.get("op") == "fst":
                yield _replace(body, sp, {"op": "snd", "args": node["args"]})
            elif node.get("op") == "snd":
                yield _replace(body, sp, {"op": "fst", "args": node["args"]})


def _c_drop_guard(body, scope):
    for path, e, _, kind in _exprs(body, scope):
        if kind not in ("cond-if", "cond-while"):
            continue
        if e.get("op") != "and" or len(e["args"]) < 2:
            continue
        for k in range(len(e["args"])):
            rest = e["args"][:k] + e["args"][k + 1:]
            yield _replace(body, path,
                           rest[0] if len(rest) == 1
                           else {"op": "and", "args": rest})


_INT_ROOTED_OPS = ("neg", "len", "*", "-", "div", "mod")


def _int_rooted(node: dict, ty_of: dict) -> bool:
    """True when `node`'s value is unambiguously int-typed, checked
    structurally so WRONG-CONSTANT never wraps a seq/bool/pair-typed site
    (Python's bool is an int subclass, so a silent `True + 1 == 2` would
    otherwise pass as a well-typed twin body while actually changing the
    return's runtime TYPE rather than an int value). `+` is deliberately
    excluded even though it is arithmetic: SPEC.md "Sequences: literals,
    concatenation, slices" overloads it for seq concatenation, and this
    predicate has no type-checker to tell the two apart at an arbitrary
    subexpression. Every op it does accept (`neg`, `len`, `*`, `-`, `div`,
    `mod`) has exactly one, int-returning, meaning in this language."""
    if "int" in node:
        return True
    if "var" in node:
        return ty_of.get(node["var"]) == "int"
    return node.get("op") in _INT_ROOTED_OPS


def _c_wrong_constant(body, scope):
    """WRONG-CONSTANT (SPEC.md "The twins", twin-ladder wave, 2026-09-11):
    `expr +- 1` at one assign/return right-hand side or `var` initialiser,
    restricted to sites `_int_rooted` proves int-typed. The mutation a
    straight-line body with no `if`, no loop, no literal, and no
    `at`/`update`/`fill`/`slice` admits -- OFF-BY-ONE has nothing to move
    there, since there is no literal or indexing op in the expression at
    all, only a computed value returned or assigned whole (e.g.
    `volume := size * size * size`, `ascii := c`)."""
    for path, e, sc, kind in _exprs(body, scope):
        if kind not in ("rhs", "init"):
            continue
        if not _int_rooted(e, dict(sc)):
            continue
        for d in (1, -1):
            yield _replace(body, path, {"op": "+", "args": [e, {"int": d}]})


ARITH_ALT = {"+": ("-", "*"), "-": ("+", "*"), "*": ("+", "-"),
             "div": ("mod",), "mod": ("div",)}


def _c_wrong_operator(body, scope):
    """WRONG-OPERATOR (SPEC.md "The twins", twin-ladder wave, 2026-09-11):
    one arithmetic operator swapped for another from ARITH_ALT's fixed
    per-operator list, at every site COMPARE-FLIP's own `_sub` walk
    reaches. Empty wherever the body has no `+`/`-`/`*`/`div`/`mod` node,
    which none of the earlier rungs touch (COMPARE-FLIP and BOUNDARY-SWAP
    only ever rewrite an order comparison, never the arithmetic feeding
    one)."""
    for path, e, sc, _kind in _exprs(body, scope):
        for sp, node in _sub(e, path):
            op = node.get("op")
            if op not in ARITH_ALT:
                continue
            if op == "+" and not any(_int_rooted(a, dict(sc))
                                     for a in node["args"]):
                # `+` is also seq concatenation (SPEC.md "Sequences"); a
                # swap is only an arithmetic twin when an operand is
                # provably int. Found at the wave G merge, 2026-09-11:
                # fz_p_lit_empty's `[] + s` swapped to `[] - s` raised
                # TypeError in interp and read as a poisoned cell in all
                # seven columns.
                continue
            for alt in ARITH_ALT[op]:
                yield _replace(body, sp, {"op": alt, "args": node["args"]})


EXTENSIONAL = (("collapse-if", _c_collapse_if),
               ("negate-cond", _c_negate_cond),
               ("compare-flip", _c_compare_flip),
               ("boundary-swap", _c_boundary_swap),
               ("off-by-one", _c_off_by_one),
               ("wrong-var", _c_wrong_var),
               ("drop-guard", _c_drop_guard),
               ("wrong-constant", _c_wrong_constant),
               ("wrong-operator", _c_wrong_operator))


def _invariant_candidates(task: dict):
    """(twin_body, loop, kept, names) per (loop, invariant) in pre-order.
    Candidate 0 is drop_first_invariant's twin. `names` is what a loop state
    ranges over: everything in scope at the loop, plus the return."""
    body = task["body"]
    scope = [(p["name"], p["type"]) for p in task["params"]]
    ret = task["returns"][0]
    for p, s, sc in _stmts(body, scope):
        if "while" not in s or not s["while"].get("invariants"):
            continue
        invs = s["while"]["invariants"]
        for j in range(len(invs)):
            kept = invs[:j] + invs[j + 1:]
            yield (_replace(body, p + ("while", "invariants"), kept),
                   s["while"], kept, sc + [(ret["name"], ret["type"])])


def _tag(op: str, k: int) -> str:
    return op if k == 0 else f"{op}#{k}"


def twin_for(task: dict) -> tuple[list | None, str | None, dict | None]:
    """Grounded twin selection: (twin_body, operator, witness), or
    (None, reason, None) when no rung of the ladder produced a witness.

    2026-09-12 (ROADMAP 16.2, "twin-order"): the EXTENSIONAL rungs are tried
    FIRST, in their existing order, and the invariant-drop candidates LAST.
    A body with a behavioral twin -- a value witness that falsifies
    `ensures` -- gets that twin; invariant-drop remains the twin only for a
    body with no behavioral rung at all (a straight-line loop obligation
    with nothing else to mutate, or every extensional rung merely
    reshuffling values `ensures` cannot tell apart). Reason: an
    INVARIANT-DROP twin is not a wrong program (SPEC.md "The twins"'
    dated paragraph below) -- every reachable loop-head state still
    satisfies every SURVIVING invariant, so no reachable witness can
    refute it, and a kernel that verifies it by re-deriving the dropped
    annotation is not unsound. A task whose body actually computes the
    wrong VALUE should be caught by a value witness before the ladder
    ever reaches for that reading."""
    n = 0
    ref = interp.Reference(task)
    # A witness that merely shows real and twin compute DIFFERENT values is
    # not grounds for expecting a refutation: a loose `ensures` can be
    # satisfied by both. Only a witness that FALSIFIES ensures entails that a
    # sound kernel must refute, which is what interp records in `_ens` and
    # what SPEC.md means by "the twin is REFUTED by the actual kernel".
    # Measured 2026-09-04: accepting on difference alone produced 88 cells
    # across all seven kernels whose twin came back VERIFIED, every one a
    # collapse-if, clustered by TASK rather than by kernel, which is the
    # signature of the twin being unrefutable rather than of seven adapters
    # being wrong. The ladder therefore prefers a refuting candidate and
    # falls back to a merely-differing one only when the whole ladder has
    # none, so the weakness is recorded in the tag instead of being silently
    # counted as a flip that failed.
    fallback = None
    if ref.points:
        for op, gen in EXTENSIONAL:
            for k, twin in enumerate(gen(task["body"], _scope(task))):
                n += 1
                if n > MAX_CANDIDATES:
                    break
                try:
                    w = ref.witness(twin)
                except TypeError:
                    # An ill-typed candidate (a rung rewrote a node whose
                    # type it could not see) is not a program of the
                    # language, so it is not a twin; the next candidate,
                    # never a poisoned cell. 2026-09-11.
                    continue
                if w is None:
                    continue
                if w.get("_ens") is True:
                    return twin, _tag(op, k), w
                if fallback is None:
                    fallback = (twin, _tag(op, k) + "+nonrefuting", w)
            if n > MAX_CANDIDATES:
                break
    for k, (twin, loop, kept, names) in enumerate(_invariant_candidates(task)):
        n += 1
        w = interp.invariant_witness(task, loop, kept, names)
        if w is not None:
            return twin, _tag("invariant-drop", k), w
    if not ref.points:
        # UNMEASURABLE, which is a different refusal from "the twin computes
        # the same thing", and the two causes are worth telling apart.
        if (ref.n_req == 0 and ref.n_domain > 0
                and ref.req_undef == ref.n_domain):
            # `requires` itself raised Undef at EVERY point tried (not just
            # evaluated False): a `div`/`mod` by zero inside `requires`,
            # ROADMAP 13.4 (2026-09-11). SPEC.md's "Undefined requires
            # (normative)" calls this DEFECTIVE, the same defect class as a
            # well-defined but unsatisfiable requires (fz_p_vac_unsat,
            # fz_p_vac_range), so it gets its own named refusal rather than
            # being folded into "no-input" silently.
            return None, "vacuous-requires-undefined", None
        return None, ("no-input" if not ref.n_req else "real-undefined"), None
    if n > MAX_CANDIDATES and fallback is None:
        return None, "candidate-budget", None
    if fallback is not None:
        return fallback
    return None, ("no-witness" if n else "no-operator"), None


def ladder_rungs(task: dict) -> list[tuple[str, list, dict | None]]:
    """Every rung the twin ladder can build for `task` (t/ladder_completeness.py,
    ROADMAP WS-19 move 6, added 2026-09-11): (operator_tag, twin_body,
    witness_or_None) per candidate, in the order `twin_for` uses (2026-09-12,
    "twin-order": EXTENSIONAL first, invariant-drop last -- see twin_for's
    own docstring), capped at MAX_CANDIDATES in both phases (twin_for caps
    only the extensional phase; invariant counts are small, so no measured
    task differs), but WITHOUT stopping at the first witness: every rung
    the ladder can build is enumerated, not only the one twin_for would
    pick.

    `witness_or_None` is the witness dict exactly when the interpreter shows
    the rung MUST be refuted by a sound kernel: an invariant-drop witness
    (interp.invariant_witness, which by construction only returns a forcing
    witness), or an extensional witness whose value also falsifies `ensures`
    (`w["_ens"] is True`, interp.Reference._breaks_ensures). A witness that
    only shows a value DIFFERENCE without falsifying `ensures` is recorded
    as no witness here, the same standard twin_for applies before accepting
    a rung as a flip. Reuses twin_for's own candidate generators (the
    invariant and EXTENSIONAL generators above) unchanged; this function
    adds no new mutation logic."""
    rungs: list[tuple[str, list, dict | None]] = []
    n = 0
    ref = interp.Reference(task)
    if ref.points:
        for op, gen in EXTENSIONAL:
            for k, twin in enumerate(gen(task["body"], _scope(task))):
                n += 1
                if n > MAX_CANDIDATES:
                    return rungs
                try:
                    w = ref.witness(twin)
                except TypeError:
                    # Same guard as twin_for: an ill-typed candidate is no rung.
                    continue
                refuted = w is not None and w.get("_ens") is True
                rungs.append((_tag(op, k), twin, w if refuted else None))
    for k, (twin, loop, kept, names) in enumerate(_invariant_candidates(task)):
        n += 1
        if n > MAX_CANDIDATES:
            return rungs
        w = interp.invariant_witness(task, loop, kept, names)
        rungs.append((_tag("invariant-drop", k), twin, w))
    return rungs


def _scope(task: dict) -> list:
    return [(p["name"], p["type"]) for p in task["params"]]


_TWIN_CACHE: dict[str, tuple] = {}


def twin_cached(task: dict) -> tuple[list | None, str | None, dict | None]:
    """run_all.py/run_par.py ask for the same task's twin once per backend;
    the ladder is a search, so it runs once."""
    key = json.dumps(task, sort_keys=True)
    if key not in _TWIN_CACHE:
        _TWIN_CACHE[key] = twin_for(task)
    return _TWIN_CACHE[key]


def make_twin(body: list, task: dict | None = None
              ) -> tuple[list | None, str | None]:
    """Deterministic twin selection. Returns (twin_body, operator_name), or
    (None, reason) when no operator produced a witness.

    `task` is what makes the choice measurable: without params, requires and
    ensures there is nothing to run the twin on. A body-only call is the
    UNGROUNDED v1 rule, kept for callers that carry their own semantic
    instrument (fuzz_lower.py decides twin strength with its own interpreter
    and must keep selecting the twin whose strength it reports)."""
    if task is not None:
        twin, op, _ = twin_cached(task)
        return twin, op
    if _has_invariant_loop(body):
        twin, _ = drop_first_invariant(body)
        return twin, "invariant-drop"
    twin, hit = collapse_first_if(body)
    if hit:
        return twin, "collapse-if"
    return None, None


REFUSALS = {
    "no-operator": "no `if` and no invariant, nothing to mutate, so the "
                   "twin is undefined",
    "no-witness": "every mutation on the ladder computes what the real body "
                  "computes, on the whole bounded domain, nothing to measure",
    "no-input": "no input in the bounded domain satisfies `requires`, a "
                "vacuous precondition, so there is nothing to measure",
    "vacuous-requires-undefined": "`requires` is undefined (raises, not "
                "merely evaluates False) at every type-correct input "
                "tried, a defective precondition per SPEC.md's Undefined "
                "requires (normative), so there is nothing to measure",
    "real-undefined": "the real body returns no value on any input that "
                      "satisfies `requires`, nothing for a twin to differ "
                      "from",
    "candidate-budget": f"no witness within {MAX_CANDIDATES} candidates",
}


def real_witness(task: dict) -> dict | None:
    """The interpreter's bounded search (interp.py's own machinery, the
    same domain() enumeration and MAX_POINTS budget interp.Reference already
    uses for twins) for an input on which the REAL body -- not a twin --
    violates its own `ensures`, or is undefined (interp.Undef) at an input
    `requires` admits. In exactly the shape lower(task, body, witness=w)
    already accepts ("_kind", the input names, "_real", "_twin", "_ens"):
    every lowering's certificate builder replays whatever body it is given
    at the witness's concrete values (t/lower_dafny.py's `_certificate`,
    `body is not task.get("body")` only decides whether to substitute a
    twin body in for the renamed one, never whether the witness is legal),
    so calling `lower(task, task["body"], witness=real_witness(task))`
    produces the REAL's own refutation certificate, not a twin's.

    Reuses interp.Reference (harness.twin_for's own search) for the "value"
    case: its `.points` are exactly the (env0, real value) pairs a bounded
    scan already computed, so the only new work here is asking whether the
    REAL's own value at each point satisfies `ensures` (Reference itself
    never asks this; it only compares real against a twin). Reference skips
    a requires-satisfying point where the body itself raises Undef ("a path
    that raises Undef ... continue"), which is the right call for a twin
    comparison but IS the defect for the real body itself, so a second pass
    over the same interp.domain() enumeration catches that case, using no
    search primitive interp.py does not already provide.

    None when the scan finds nothing: every committed task under t/tasks
    (t/test_real_witness.py asserts this for all of them).

    2026-09-12 (ROADMAP 13.4, the harness column): a requires-satisfying
    point where the real body HAS a value can still leave `ensures` itself
    undefined (an out-of-range `at`, a bad slice bound, a div/mod by zero
    written directly into the postcondition, never guarded by a `requires`
    that would exclude it) -- distinct from `ensures` evaluating cleanly to
    False. Both are certificate-worthy (SPEC.md's definedness obligation
    covers the postcondition, not only the body), but a kernel proves them
    two different ways: a false ensures is a VALUE counterexample, an
    undefined ensures is a DEFINEDNESS counterexample at the offending
    sub-expression. So this loop, unlike the single `_breaks_ensures` call
    it replaces, evaluates `ensures` itself instead of delegating, to catch
    interp.Undef and read the sub-expression it names (interp.Undef.expr,
    set at every raise site in ev() to the node being evaluated) rather
    than collapsing both cases into one "value" witness."""
    ref = interp.Reference(task)
    for env0, got in ref.points:
        env = dict(env0)
        env[ref.ret] = got
        # ROADMAP 13.4, framac-measure, 2026-09-11: check_measures=True
        # only on THIS scan's own St (interp.Reference above built `got`
        # with a default, unchecked St, so a bad decreases never keeps a
        # value from being computed -- it only stops THIS re-evaluation
        # of `ensures`, exactly where a spec_fun call can reach a broken
        # measure). See interp.MeasureViolation's docstring.
        st = interp.St(check_measures=True)
        try:
            broke = False
            for c in task["ensures"]:
                if not interp.ev(c, env, ref.funs, st):
                    broke = True
                    break
            if broke:
                w = interp._shown(env0)
                w.update(_kind="value", _real=interp._j(got),
                        _twin=interp._j(got), _ens=True)
                return w
        except interp.MeasureViolation as mv:
            w = interp._shown(env0)
            w.update(_kind="measure", _site=mv.site,
                    _caller_measure=interp._j(mv.caller_measure),
                    _callee_measure=interp._j(mv.callee_measure))
            return w
        except interp.Undef as u:
            w = interp._shown(env0)
            w.update(_kind="undefined", _real="no value",
                    _site="ensures", _expr=u.expr,
                    _value=interp._j(got))   # the body's own result, defined (2026-09-12)
            return w
        except (interp.Budget, RecursionError):
            continue
    names = interp._names(task)
    funs = ref.funs
    req = task.get("requires", [])
    ret = task["returns"][0]["name"]
    for env0 in interp.domain(task, names, interp.MAX_POINTS):
        st = interp.St(check_measures=True)
        try:
            if not all(interp.ev(c, env0, funs, st) for c in req):
                continue
        except (interp.Undef, interp.Budget, RecursionError,
               interp.MeasureViolation):
            continue          # a bad measure IN `requires` decides nothing
        env = dict(env0)
        env[ret] = None
        try:
            interp.exec_body(task["body"], env, funs, st)
        except interp.MeasureViolation as mv:
            # A loop's own variant, or a spec_fun the BODY (not just
            # `ensures`) calls: the first loop above never re-executes
            # the body, so this is the only scan that reaches it
            # (fz_p_badvariant, ROADMAP 13.4). `mv.site` is the raw AST
            # node for a loop (interp.MeasureViolation's docstring) --
            # not JSON-shaped, so it becomes the loop's own small index
            # (interp.loop_index) before this witness is shown or diffed
            # anywhere; a spec_fun's site is already its (JSON-safe) name.
            site = (mv.site if isinstance(mv.site, str)
                   else interp.loop_index(task, mv.site))
            w = interp._shown(env0)
            w.update(_kind="measure", _site=site,
                    _caller_measure=interp._j(mv.caller_measure),
                    _callee_measure=interp._j(mv.callee_measure))
            return w
        except interp.Undef as u:
            w = interp._shown(env0)
            w.update(_kind="undefined", _real="no value", _twin=str(u),
                    _ens=True)
            return w
        except (interp.Budget, RecursionError):
            continue
    return None


def witness(w: dict | None) -> str:
    """One line naming the input (or loop state) that makes the twin a
    measurement, the thing a REFUTED verdict is a verdict ABOUT."""
    if not w:
        return "none"
    kind = w.get("_kind")
    ins = ", ".join(f"{k}={v}" for k, v in w.items() if not k.startswith("_"))
    if kind in ("exit", "preservation"):
        return f"{kind} at {ins}"
    if kind == "measure":
        # ROADMAP 13.4, framac-measure, 2026-09-11.
        return (f"measure at {w.get('_site')}, {ins} -> "
               f"{w.get('_callee_measure')} not below "
               f"{w.get('_caller_measure')}")
    return f"{ins} -> real {w.get('_real')}, twin {w.get('_twin')}"


def decorative_kind(real_outcome: str, twin_outcome: str,
                    w: dict | None) -> str | None:
    """SPEC.md "The twins", 2026-09-11 paragraph (ROADMAP 13.3). None
    unless a column's real AND twin both come back VERIFIED (the harness
    already treats every other pairing as not-a-flip); the two outcomes
    that pairing can mean are told apart by the witness the ladder already
    measured, never by a fresh assumption:

    - "decorative": the ladder accepted this twin on the fallback path (a
      witness that shows real and twin compute DIFFERENT values but does
      not FALSIFY `ensures`, tagged "+nonrefuting" in twin_for, `_ens` not
      True on a "value" witness). Nothing entailed a refutation here, so
      a kernel verifying the twin too says the spec cannot tell them
      apart in that column: `ensures true` is the canonical case. Never
      counts as agreement, and is not a claim about the kernel.
    - "unsound": the witness DOES entail a refutation, and does so with a
      VALUE witness that falsifies `ensures` (`_ens is True` on a "value"
      or "undefined" kind). A kernel that verifies the twin anyway
      contradicts its own measured witness: a signal about that kernel,
      not about the spec's strength, counted separately from "decorative"
      so the two are never averaged together.
    - "re-derived" (2026-09-12, ROADMAP 16.2, "twin-order"): the witness is
      an INVARIANT-DROP proof witness (kind "exit" or "preservation").
      SPEC.md's dated paragraph in "The twins" states why this is NOT a
      soundness finding the way a value witness is: every reachable
      loop-head state still satisfies every SURVIVING invariant (dropping
      one leaves the rest true), so no reachable witness can refute this
      twin, and a kernel that verifies it did so by re-deriving the
      dropped annotation on its own -- interval inference, a stronger
      loop-invariant search, whatever that kernel's `while` rule already
      does. That is a fact about that kernel's inference, worth naming,
      never folded into "unsound" (which stays for a program a kernel
      accepted despite a witness showing its VALUE is wrong).

    A task with no witness (w is None, or falsy) never reaches this
    function with twin_outcome VERIFIED under the grounded ladder
    (twin_for returns twin_body=None, so the caller never lowers or
    verifies a twin at all): that combination is left as "decorative"
    rather than raising, so a caller that constructs the pairing by hand
    (t/test_twin_rule.py) gets the same conservative label a missing
    witness deserves."""
    if real_outcome != Outcome.VERIFIED or twin_outcome != Outcome.VERIFIED:
        return None
    if w and w.get("_kind") in ("exit", "preservation"):
        return "re-derived"
    if w and w.get("_ens") is True:
        return "unsound"
    return "decorative"


def run_task(task_path: Path, lower, backend, suffix: str) -> bool:
    """lower(task, body, witness=None) -> source text; backend is a
    t.verifiers module. The twin call passes the measured witness so
    a lowering may use it; the real call never does."""
    task = load(task_path)
    name = task["name"]
    OUT.mkdir(exist_ok=True)

    twin_body, op, w = twin_cached(task)
    if twin_body is None:
        print(f"  {name}: REFUSED, {REFUSALS[op]}")
        return False

    real = OUT / f"{name}.{suffix}"
    real.write_text(lower(task, task["body"]), encoding="utf-8",
                    newline="\n")
    twin = OUT / f"{name}_twin.{suffix}"
    twin.write_text(lower(task, twin_body, witness=w), encoding="utf-8",
                    newline="\n")

    (r_real, agree_r), (r_twin, agree_t) = cell_pair(backend.verify, real, twin)
    if not (agree_r and agree_t):
        print(f"  {name}: REFUSED, verdicts flaked across runs")
        return False
    flip = (r_real.outcome == Outcome.VERIFIED
            and r_twin.outcome == Outcome.REFUTED)
    kind = decorative_kind(r_real.outcome, r_twin.outcome, w)
    tag = (f"COUNTS  (real VERIFIED, {op} twin REFUTED, witness {witness(w)})"
           if flip else
           f"REFUSED (real {r_real.outcome}, {op} twin {r_twin.outcome}"
           # SPEC.md "The twins", 2026-09-11: real VERIFIED and twin
           # VERIFIED is named, never folded into a bare REFUSED. kind is
           # "decorative" when nothing the ladder measured entailed a
           # refutation here (the spec cannot tell real and twin apart,
           # e.g. `ensures true`), "unsound" when a VALUE witness DID
           # entail one (a kernel accepted a twin its own measured witness
           # says is wrong), and "re-derived" (2026-09-12, "twin-order")
           # when an INVARIANT-DROP proof witness did -- not a soundness
           # finding, the kernel re-derived the dropped annotation; see
           # decorative_kind's docstring.
           + (f", unsound: the twin is broken on {witness(w)} and the "
              f"kernel accepted it anyway)" if kind == "unsound" else
              f", re-derived: the kernel re-derived the dropped "
              f"annotation, {witness(w)})" if kind == "re-derived" else
              f", decorative: the spec cannot tell real from twin, "
              f"REFUSED)" if kind is not None else ")"))
    print(f"  {name}: {tag}")
    return flip


def run_all(argv: list[str], lower, backend, suffix: str) -> int:
    """Every committed task through one lowering, standalone.

    ROADMAP 14.1 made `.t` the input and moved every caller to tasks_io -- except these two, which kept
    spelling `.json` and so found nothing at all once t/tasks held only `.t` files (named open in 14.1's own
    entry on 2026-09-11, closed 2026-09-19). A name given on the command line is still taken as a stem, so
    `python3 lower_dafny.py abs` keeps working, and a path is taken as a path."""
    import tasks_io
    files = ([Path(a) if Path(a).exists() else tasks_io.find(HERE / "tasks", Path(a).stem) for a in argv]
             if argv else sorted(tasks_io.load_dir(HERE / "tasks")))
    print(f"t -> {backend.version()}")
    ok = all(run_task(f, lower, backend, suffix) for f in files)
    return 0 if ok else 1
