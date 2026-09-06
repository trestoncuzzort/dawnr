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
  WRONG-VAR           : one variable occurrence replaced by another one.
  DROP-GUARD          : drop one conjunct of an `if`/`while` condition.

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
from verifiers import Outcome, flake_check

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"

KNOWN_VERSIONS = (0, 1)


def load(path: Path) -> dict:
    task = json.loads(path.read_text(encoding="utf-8"))
    assert task.get("t") in KNOWN_VERSIONS, (
        f"{path.name}: not a t task I know (t={task.get('t')!r}, "
        f"known: {KNOWN_VERSIONS})")
    return task


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
            elif node.get("op") == "at":
                for d in (1, -1):
                    yield _replace(body, sp + ("args", 1),
                                   {"op": "+", "args": [node["args"][1],
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
    for path, e, sc, _k in _exprs(body, scope):
        ty_of = dict(sc)
        for sp, node in _sub(e, path):
            if "var" in node and node["var"] in ty_of:
                ty = ty_of[node["var"]]
                for alt, alt_ty in sc:
                    if alt != node["var"] and alt_ty == ty:
                        yield _replace(body, sp, {"var": alt})


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


EXTENSIONAL = (("collapse-if", _c_collapse_if),
               ("negate-cond", _c_negate_cond),
               ("compare-flip", _c_compare_flip),
               ("boundary-swap", _c_boundary_swap),
               ("off-by-one", _c_off_by_one),
               ("wrong-var", _c_wrong_var),
               ("drop-guard", _c_drop_guard))


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
    (None, reason, None) when no rung of the ladder produced a witness."""
    n = 0
    for k, (twin, loop, kept, names) in enumerate(_invariant_candidates(task)):
        n += 1
        w = interp.invariant_witness(task, loop, kept, names)
        if w is not None:
            return twin, _tag("invariant-drop", k), w
    ref = interp.Reference(task)
    if not ref.points:
        # UNMEASURABLE, which is a different refusal from "the twin computes
        # the same thing", and the two causes are worth telling apart.
        return None, ("no-input" if not ref.n_req else "real-undefined"), None
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
    for op, gen in EXTENSIONAL:
        for k, twin in enumerate(gen(task["body"], _scope(task))):
            n += 1
            if n > MAX_CANDIDATES:
                break
            w = ref.witness(twin)
            if w is None:
                continue
            if w.get("_ens") is True:
                return twin, _tag(op, k), w
            if fallback is None:
                fallback = (twin, _tag(op, k) + "+nonrefuting", w)
        if n > MAX_CANDIDATES:
            break
    if n > MAX_CANDIDATES and fallback is None:
        return None, "candidate-budget", None
    if fallback is not None:
        return fallback
    return None, ("no-witness" if n else "no-operator"), None


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
    "real-undefined": "the real body returns no value on any input that "
                      "satisfies `requires`, nothing for a twin to differ "
                      "from",
    "candidate-budget": f"no witness within {MAX_CANDIDATES} candidates",
}


def witness(w: dict | None) -> str:
    """One line naming the input (or loop state) that makes the twin a
    measurement, the thing a REFUTED verdict is a verdict ABOUT."""
    if not w:
        return "none"
    kind = w.get("_kind")
    ins = ", ".join(f"{k}={v}" for k, v in w.items() if not k.startswith("_"))
    if kind in ("exit", "preservation"):
        return f"{kind} at {ins}"
    return f"{ins} -> real {w.get('_real')}, twin {w.get('_twin')}"


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

    r_real, agree_r = flake_check(backend.verify, real)
    r_twin, agree_t = flake_check(backend.verify, twin)
    if not (agree_r and agree_t):
        print(f"  {name}: REFUSED, verdicts flaked across runs")
        return False
    flip = (r_real.outcome == Outcome.VERIFIED
            and r_twin.outcome == Outcome.REFUTED)
    tag = (f"COUNTS  (real VERIFIED, {op} twin REFUTED, witness {witness(w)})"
           if flip else
           f"REFUSED (real {r_real.outcome}, {op} twin {r_twin.outcome}"
           + (f", vacuous spec: the twin is broken on {witness(w)} and the "
              f"kernel accepted it anyway)"
              if r_twin.outcome == Outcome.VERIFIED else ")"))
    print(f"  {name}: {tag}")
    return flip


def run_all(argv: list[str], lower, backend, suffix: str) -> int:
    want = argv or sorted(p.stem for p in (HERE / "tasks").glob("*.json"))
    print(f"t -> {backend.version()}")
    ok = all(run_task(HERE / "tasks" / f"{w}.json", lower, backend, suffix)
             for w in want)
    return 0 if ok else 1
