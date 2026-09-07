#!/usr/bin/env python3
"""lower_dafny.py: lower t tasks (v0 and v1) to Dafny, verify both the task
and its broken twin, and refuse anything that does not flip.

    python3 t/lower_dafny.py            # all of t/tasks/*.json
    python3 t/lower_dafny.py abs        # one task

The verdict is Dafny's, never this file's. Exit codes are the measured ones
from dafny_verify.py (dafny 4.11.0): 0 verified, 2 parse/resolution, 4
verification failed. A task COUNTS only when the real cell is VERIFIED and
the twin cell is REFUTED, and since 2026-09-02 REFUTED is no longer read off
exit 4 (could-not-prove, not a countermodel): it is minted only when dafny
itself accepts the refutation certificate this file appends to the twin
(see the certificate section below and verifiers/dafny.py). Everything else
is refused with the reason printed: twin-verifies means the spec is vacuous;
real-fails means the task is wrong; twin-malformed means the mutation broke
syntax rather than meaning and the witness would be about parsing, not
proof; twin-unproved means the kernel could neither prove the twin nor
accept the certificate, which is not knowledge either way.

v1 mapping, gate by gate (SPEC.md):
  quantifiers: t's bounded forall/exists over [lo,hi) lower to Dafny's native
    bounded quantifiers; `seq` is Dafny's seq<int>, `len` is |s|, `at` is s[i].
    Dafny's well-formedness checking discharges t's definedness obligations
    natively: `at` outside [0,len) is a verification error unless guarded, and
    &&/||/==>/ite/quantifier bodies are checked left-to-right / under-guard,
    exactly t's rules. Nothing is totalized.
  loops: t `while` lowers to Dafny while with invariant/decreases clauses;
    Dafny checks decreases >= 0 and strictly decreasing, t's obligation.
  recursion: spec_funs lower to Dafny `function` (pure, with decreases);
    a task self-call lowers to a call of the lowered METHOD, hoisted out of
    expression position into `var tmp := M(...);` statements (SPEC.md allows
    the hoist; evaluation is call-by-value left-to-right). Hoisting is refused
    (NotImplementedError, an ABSTAIN) when a self-call sits under a lazily
    evaluated position (quantifier body, ite branch, non-first and/or/implies
    argument) because unconditional evaluation there could smuggle in a
    precondition the taken path never owed. No task should put one there
    (SPEC: self-calls appear only where evaluation order is unobservable).

Stdlib only, same reason as dataset_gate.py.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import interp                                       # noqa: E402
from verifiers import Outcome, flake_check          # noqa: E402
from verifiers import dafny as dafny_backend        # noqa: E402

OUT = HERE / "out"

BIN_OPS = {"==": "==", "!=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">=",
           "+": "+", "-": "-", "*": "*", "implies": "==>"}
NARY_OPS = {"and": "&&", "or": "||"}
TYPES = {"int": "int", "bool": "bool", "seq": "seq<int>"}


def expr(e: dict, self_name: str | None = None) -> str:
    """Lower a spec-position expression. A self-call here is refused: SPEC.md
    puts task self-calls in bodies only, and the twin argument depends on the
    spec never mentioning the task's own (mutable) name."""
    if "int" in e:
        return str(e["int"])
    if "bool" in e:
        return "true" if e["bool"] else "false"
    if "var" in e:
        return e["var"]
    if "forall" in e:
        q = e["forall"]
        v = q["var"]
        return (f"(forall {v}: int :: "
                f"({expr(q['lo'], self_name)} <= {v} && "
                f"{v} < {expr(q['hi'], self_name)}) ==> "
                f"{expr(q['body'], self_name)})")
    if "exists" in e:
        q = e["exists"]
        v = q["var"]
        return (f"(exists {v}: int :: "
                f"({expr(q['lo'], self_name)} <= {v} && "
                f"{v} < {expr(q['hi'], self_name)}) && "
                f"{expr(q['body'], self_name)})")
    if "ite" in e:
        c = e["ite"]
        return (f"(if {expr(c['cond'], self_name)} "
                f"then {expr(c['then'], self_name)} "
                f"else {expr(c['else'], self_name)})")
    if "call" in e:
        c = e["call"]
        if c["fun"] == self_name:
            raise ValueError(
                f"self-call of {self_name!r} in spec position: t puts "
                f"self-calls in bodies only (SPEC.md gate 3)")
        args = ", ".join(expr(a, self_name) for a in c["args"])
        return f"{c['fun']}({args})"
    op, args = e["op"], [expr(a, self_name) for a in e.get("args", [])]
    if op == "neg":
        return f"(-{args[0]})"
    if op == "not":
        return f"(!{args[0]})"
    if op == "len":
        return f"|{args[0]}|"
    if op == "at":
        return f"{args[0]}[{args[1]}]"
    if op in NARY_OPS:
        return "(" + f" {NARY_OPS[op]} ".join(args) + ")"
    if op in BIN_OPS:
        return f"({args[0]} {BIN_OPS[op]} {args[1]})"
    raise ValueError(f"t has no operator {op!r}")


def _collect_names(obj) -> set[str]:
    """Every string anywhere in the task JSON, a superset of every identifier
    in scope, so a name absent from it is fresh everywhere."""
    out: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            out |= _collect_names(v)
    elif isinstance(obj, list):
        for v in obj:
            out |= _collect_names(v)
    elif isinstance(obj, str):
        out.add(obj)
    return out


class _Ctx:
    """Per-lowering context: the task's own name (self-calls target the
    lowered method and must be hoisted), the method name, a fresh-name
    supply that avoids everything the task ever mentions."""

    def __init__(self, task: dict, method: str):
        self.self_name = task["name"]
        self.method = method
        self._used = _collect_names(task)
        self._n = 0

    def fresh(self) -> str:
        while True:
            cand = f"t{self._n}"
            self._n += 1
            if cand not in self._used:
                self._used.add(cand)
                return cand


def body_expr(e: dict, ctx: _Ctx, pre: list[str], lazy: bool = False) -> str:
    """Lower a body-position expression, hoisting each self-call (left to
    right, innermost first: call-by-value order) into `pre` as a
    `var tmp := Method(...);` statement. `lazy` marks positions Dafny/t do not
    unconditionally evaluate; a self-call there cannot be hoisted without
    evaluating it on paths that never owed its precondition, so it is an
    explicit ABSTAIN, not a wrong program."""
    if "call" in e and e["call"]["fun"] == ctx.self_name:
        if lazy:
            raise NotImplementedError(
                "dafny: self-call under a lazily-evaluated position "
                "(ite branch / short-circuit arg / quantifier body): "
                "hoisting would evaluate it unconditionally")
        args = ", ".join(body_expr(a, ctx, pre) for a in e["call"]["args"])
        tmp = ctx.fresh()
        pre.append(f"var {tmp} := {ctx.method}({args});")
        return tmp
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        kind = "forall" if "forall" in e else "exists"
        v = q["var"]
        lo = body_expr(q["lo"], ctx, pre, lazy)
        hi = body_expr(q["hi"], ctx, pre, lazy)
        b = body_expr(q["body"], ctx, pre, lazy=True)
        glue = "==>" if kind == "forall" else "&&"
        return (f"({kind} {v}: int :: ({lo} <= {v} && {v} < {hi}) "
                f"{glue} {b})")
    if "ite" in e:
        c = e["ite"]
        cond = body_expr(c["cond"], ctx, pre, lazy)
        t = body_expr(c["then"], ctx, pre, lazy=True)
        f = body_expr(c["else"], ctx, pre, lazy=True)
        return f"(if {cond} then {t} else {f})"
    if "call" in e:
        c = e["call"]
        args = ", ".join(body_expr(a, ctx, pre, lazy) for a in c["args"])
        return f"{c['fun']}({args})"
    if "op" in e:
        op = e["op"]
        if op in NARY_OPS or op == "implies":
            # left-to-right short circuit: only the first arg is strict
            parts = [body_expr(a, ctx, pre, lazy if i == 0 else True)
                     for i, a in enumerate(e["args"])]
            if op == "implies":
                return f"({parts[0]} ==> {parts[1]})"
            return "(" + f" {NARY_OPS[op]} ".join(parts) + ")"
        # strict operators: same laziness as the enclosing position
        args = [body_expr(a, ctx, pre, lazy) for a in e.get("args", [])]
        if op == "neg":
            return f"(-{args[0]})"
        if op == "not":
            return f"(!{args[0]})"
        if op == "len":
            return f"|{args[0]}|"
        if op == "at":
            return f"{args[0]}[{args[1]}]"
        if op in BIN_OPS:
            return f"({args[0]} {BIN_OPS[op]} {args[1]})"
        raise ValueError(f"t has no operator {op!r}")
    # leaves share the spec lowering
    return expr(e, ctx.self_name)


def stmts(body: list, indent: str, ctx: _Ctx) -> str:
    out = []
    for s in body:
        if "assign" in s:
            name, e = s["assign"]
            pre: list[str] = []
            rhs = body_expr(e, ctx, pre)
            out.extend(indent + p for p in pre)
            out.append(f"{indent}{name} := {rhs};")
        elif "var" in s:
            d = s["var"]
            pre = []
            rhs = body_expr(d["init"], ctx, pre)
            out.extend(indent + p for p in pre)
            out.append(f"{indent}var {d['name']}: {TYPES[d['type']]} "
                       f":= {rhs};")
        elif "if" in s:
            c = s["if"]
            pre = []
            cond = body_expr(c["cond"], ctx, pre)
            out.extend(indent + p for p in pre)
            out.append(f"{indent}if {cond} {{")
            out.append(stmts(c["then"], indent + "  ", ctx))
            out.append(f"{indent}}} else {{")
            out.append(stmts(c["else"], indent + "  ", ctx))
            out.append(f"{indent}}}")
        elif "while" in s:
            w = s["while"]
            # guard/invariants/decreases are spec positions: no self-calls
            out.append(f"{indent}while {expr(w['cond'], ctx.self_name)}")
            for inv in w.get("invariants", []):
                out.append(f"{indent}  invariant {expr(inv, ctx.self_name)}")
            out.append(f"{indent}  decreases "
                       f"{expr(w['decreases'], ctx.self_name)}")
            out.append(f"{indent}{{")
            out.append(stmts(w["body"], indent + "  ", ctx))
            out.append(f"{indent}}}")
        else:
            raise ValueError(f"t has no statement {s!r}")
    return "\n".join(out)


# ------------------------------------------------ the refutation certificate
# Shared certificate protocol (2026-09-02, every column). Dafny's exit 4 is
# could-not-prove, not a countermodel: measured the same day on 4.11.0, the
# truth_fuzz task gt_q_ex_lit (true by construction, ensures r == 0 and an
# existential over [0,3) that i = 2 satisfies, body r := 0) exits 4 because
# Z3 does not instantiate the existential unprompted, and the old adapter
# sold that incompleteness as REFUTED. verifiers/dafny.py therefore no
# longer mints REFUTED from exit 4 at all. What it trusts is a proof it
# asked the kernel for: when lowering a TWIN whose measured witness is
# expressible as a ground formula, this file appends one lemma named
# exactly t_refutation_certificate whose ensures restates the witness as a
# ground theorem, and the adapter mints REFUTED only when dafny accepts that
# lemma in an isolated, targeted run. A file carrying the name can never
# mint VERIFIED.
#
# What each witness kind certifies (the formula is built exactly as
# lower_verus.py _certificate builds it):
#   value (_ens True only): requires holds at the witness input and the
#     ensures conjunction is false at (input, r := the twin's measured
#     result). The kernel checks the formula; it does NOT evaluate the twin
#     (a method is not callable from a lemma, measured: "in a lemma, calls
#     are allowed only to lemmas"), so r is the interpreter's reading of
#     the twin, the same trust lower_verus.py extends.
#   exit: the loop rule's post-loop obligation is false at the witness
#     state: requires and the twin's SURVIVING invariants hold, the guard is
#     false, and the ensures conjunction is false. The kept invariants and
#     guard are read off the twin body's own loop, found by diffing the real
#     body against the twin body, so the certificate speaks about the file
#     it travels in.
#   preservation, undefined: not emitted; such a cell honestly reads
#     unproved.
#
# Three Dafny-specific steps between that formula and the lemma, each one
# measured on 4.11.0 the same day:
#   1. Bounded quantifiers whose bounds are ground after substitution are
#      unrolled into finite conjunction/disjunction (cap 64), because Z3
#      will not instantiate them itself, the very gt_q_ex_lit failure. The
#      bound values are not trusted: `lo == LO` and `hi == HI` are emitted
#      as extra conjuncts the kernel re-proves, so the unrolled formula
#      entails the quantified one by arithmetic alone.
#   2. The formula is then evaluated at the witness by the interpreter
#      below, and every operand t's own short-circuit semantics never
#      evaluated is dropped: the tail of an and/or after its deciding
#      operand, the consequent of an implies with a false antecedent, the
#      untaken branch of an ite. Measured reason: dafny checks the
#      well-formedness of `s[(-1)]` under the (false) guard `(-1) >= 0`,
#      proves it from the contradiction, and --warn-contradictory-assumptions
#      turns that into a warning and exit 2 for the whole file, which is the
#      linear_search twin's shape (r = -1). Dropping is sound because every
#      deciding operand is hoisted as a top-level conjunct the kernel must
#      prove: under those conjuncts each rewritten node is logically equal
#      to the original, so the emitted formula entails the verus-shaped one
#      by propositional logic, never by the interpreter's word. Every
#      subterm that survives was evaluated to a defined value, so its
#      well-formedness is a ground truth dafny proves without contradiction.
#   3. Recursive spec_funs: dafny's default fuel decided `!(1 == fact(2))`
#      and `!(119 == fact(5))` unaided, but the lemma body carries an
#      interpreter-chosen assert ladder anyway (`assert f(args) == v;`,
#      callees before callers, cap 64): the kernel checks every step, so a
#      wrong hint can only lose the certificate.
# Seq witness values are let-bound by their own names (`var s: seq<int> :=
# [];`) in the ensures, and again in the lemma body when the assert ladder
# names them: an inline `[]` is "the type of this expression is
# underspecified", exit 2 (measured).
# Anything outside these rules yields no certificate: a missing or rejected
# certificate can only cost a flip (UNPROVED), never fake one. The emitted
# lemma is `lemma t_refutation_certificate()` with exactly one ensures
# clause, no requires, no decreases, no comment, no string, no attribute,
# and the file around it declares only unmodified functions, methods and
# lemmas: verifiers/dafny.py reads that shape back off the kernel's own
# --rprint of the file and refuses any certificate outside it (a requires
# clause would be an assumed fact), so this is the whole vocabulary a
# certificate-carrying file may use.

CERT_NAME = "t_refutation_certificate"
_UNROLL_CAP = 64
_HOIST_CAP = 256
_LADDER_CAP = 64
TRUE = {"bool": True}

_ARITH = {"+": lambda a, b: a + b, "-": lambda a, b: a - b,
          "*": lambda a, b: a * b, "==": lambda a, b: a == b,
          "!=": lambda a, b: a != b, "<": lambda a, b: a < b,
          "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
          ">=": lambda a, b: a >= b}


def _not(e: dict) -> dict:
    return {"op": "not", "args": [e]}


def _tlit(v):
    """A measured witness value as a t literal expression. Negative ints
    become neg nodes so they emit parenthesized, `(-1)`, and never fuse
    with a preceding operator."""
    if isinstance(v, bool):
        return {"bool": v}
    if isinstance(v, int):
        return {"int": v} if v >= 0 else {"op": "neg", "args": [{"int": -v}]}
    if isinstance(v, list) and all(
            isinstance(x, int) and not isinstance(x, bool) for x in v):
        return {"_seq": list(v)}
    raise ValueError(f"witness value {v!r} has no t literal")


def subst(e: dict, m: dict) -> dict:
    """Capture-avoiding substitution over a t expression: each mapped name
    is replaced by a whole t expression (dict). Carried here rather than
    imported from lower_verus.py, like lower_spark.py and lower_lean.py
    carry their own, so a verus-side change to literal typing can never
    silently change what this column certifies."""
    if "var" in e:
        v = m.get(e["var"])
        return e if v is None else v
    if "int" in e or "bool" in e or "_seq" in e:
        return e
    if "ite" in e:
        c = e["ite"]
        return {"ite": {"cond": subst(c["cond"], m),
                        "then": subst(c["then"], m),
                        "else": subst(c["else"], m)}}
    if "call" in e:
        c = e["call"]
        return {"call": {"fun": c["fun"],
                         "args": [subst(a, m) for a in c["args"]]}}
    if "forall" in e or "exists" in e:
        kind = "forall" if "forall" in e else "exists"
        q = e[kind]
        inner = {k: v for k, v in m.items() if k != q["var"]}
        return {kind: {"var": q["var"], "lo": subst(q["lo"], m),
                       "hi": subst(q["hi"], m),
                       "body": subst(q["body"], inner)}}
    return {"op": e["op"], "args": [subst(a, m) for a in e.get("args", [])]}


def _conj(parts: list) -> dict:
    parts = [p for p in parts if p != TRUE]
    if not parts:
        return TRUE
    if len(parts) == 1:
        return parts[0]
    return {"op": "and", "args": parts}


FALSE = {"bool": False}


def _nary(op: str, args: list) -> dict:
    """An and/or node over `args`, minus the operands that cannot change
    its value (a true conjunct, a false disjunct)."""
    unit = TRUE if op == "and" else FALSE
    args = [a for a in args if a != unit]
    if not args:
        return unit
    return args[0] if len(args) == 1 else {"op": op, "args": args}


def _twin_loop(real_body: list, twin_body: list) -> dict | None:
    """The single while whose invariant list the twin changed, or None."""
    diffs: list[dict] = []

    def walk(a: list, b: list) -> None:
        if len(a) != len(b):
            return
        for sa, sb in zip(a, b):
            if "while" in sa and "while" in sb:
                wa, wb = sa["while"], sb["while"]
                if wa.get("invariants", []) != wb.get("invariants", []):
                    diffs.append(wb)
                walk(wa["body"], wb["body"])
            elif "if" in sa and "if" in sb:
                walk(sa["if"]["then"], sb["if"]["then"])
                walk(sa["if"].get("else") or [], sb["if"].get("else") or [])

    walk(real_body, twin_body)
    return diffs[0] if len(diffs) == 1 else None


def _key(v):
    """A type-tagged hashable form of a value (True and 1 stay distinct)."""
    if isinstance(v, bool):
        return ("bool", v)
    if isinstance(v, list):
        return ("seq", tuple(v))
    return ("int", v)


def _ev(e: dict, env: dict, funs: dict, st, facts: dict, hoist):
    """Evaluate a t expression under SPEC.md semantics (the dispatch mirrors
    interp.ev) and return (e2, value), where e2 is e with every operand the
    evaluation never reached removed. With `hoist` a list, each removal's
    deciding fact is appended to it (the pruning step of the certificate
    section); with `hoist` None (inside spec_fun bodies) only the value is
    meaningful. Every spec_fun call evaluated is recorded in `facts`,
    callees before callers, for the assert ladder. This evaluator is a
    hint supplier, never an oracle: every value it produces is re-proved by
    the kernel, so an error here can lose a certificate, not fake one."""
    st.tick()
    if "int" in e:
        return e, e["int"]
    if "bool" in e:
        return e, e["bool"]
    if "_seq" in e:
        return e, list(e["_seq"])
    if "var" in e:
        if e["var"] not in env:
            raise interp.Undef(f"unbound {e['var']}")
        return e, env[e["var"]]
    if "ite" in e:
        c = e["ite"]
        ce, cv = _ev(c["cond"], env, funs, st, facts, hoist)
        if hoist is not None:
            hoist.append(ce if cv else _not(ce))
        return _ev(c["then"] if cv else c["else"], env, funs, st, facts,
                   hoist)
    if "forall" in e or "exists" in e:
        if hoist is not None:
            raise ValueError("quantifier survived unrolling")
        kind = "forall" if "forall" in e else "exists"
        q = e[kind]
        lo = _ev(q["lo"], env, funs, st, facts, None)[1]
        hi = _ev(q["hi"], env, funs, st, facts, None)[1]
        if hi - lo > interp.MAX_RANGE:
            raise interp.Budget("quantifier range")
        acc = kind == "forall"
        for i in range(lo, hi):
            sub = dict(env)
            sub[q["var"]] = i
            v = _ev(q["body"], sub, funs, st, facts, None)[1]
            acc = (acc and v) if kind == "forall" else (acc or v)
        return e, bool(acc)
    if "call" in e:
        c = e["call"]
        f = funs.get(c["fun"])
        if f is None or "_exec" in f:
            raise interp.Undef(f"no spec_fun {c['fun']}")
        pairs = [_ev(a, env, funs, st, facts, hoist) for a in c["args"]]
        args = [v for _, v in pairs]
        if len(args) != len(f["params"]):
            raise ValueError(f"{c['fun']}: {len(args)} args for "
                             f"{len(f['params'])} params")
        sub = {p["name"]: a for p, a in zip(f["params"], args)}
        st.d += 1
        if st.d > interp.MAX_DEPTH:
            st.d -= 1
            raise interp.Budget("spec_fun depth")
        try:
            v = _ev(f["body"], sub, funs, st, facts, None)[1]
        finally:
            st.d -= 1
        facts.setdefault((c["fun"], tuple(_key(a) for a in args)), v)
        return {"call": {"fun": c["fun"], "args": [x for x, _ in pairs]}}, v
    op = e["op"]
    args = e.get("args", [])
    if op in ("and", "or"):
        stop = op == "or"          # and stops at False, or stops at True
        kept = []
        for i, a in enumerate(args):
            ae, av = _ev(a, env, funs, st, facts, hoist)
            kept.append(ae)
            if bool(av) == stop:
                if hoist is not None and i + 1 < len(args):
                    hoist.append(ae if av else _not(ae))
                return _nary(op, kept), stop
        return _nary(op, kept), not stop
    if op == "implies":
        ae, av = _ev(args[0], env, funs, st, facts, hoist)
        if not av:
            if hoist is not None:
                hoist.append(_not(ae))
            return TRUE, True
        be, bv = _ev(args[1], env, funs, st, facts, hoist)
        return {"op": "implies", "args": [ae, be]}, bool(bv)
    pairs = [_ev(a, env, funs, st, facts, hoist) for a in args]
    vs = [v for _, v in pairs]
    out = {"op": op, "args": [x for x, _ in pairs]}
    if op == "neg":
        return out, -vs[0]
    if op == "not":
        return out, not vs[0]
    if op == "len":
        return out, len(vs[0])
    if op == "at":
        s, i = vs
        if not (0 <= i < len(s)):
            raise interp.Undef(f"at index {i} outside [0,{len(s)})")
        return out, s[i]
    if op in _ARITH:
        return out, _ARITH[op](vs[0], vs[1])
    raise ValueError(f"t has no operator {op!r}")


def _gint(e: dict, funs: dict, st) -> int:
    """Ground int value of a quantifier bound after witness substitution.
    Strict: a non-int (or a bool) refuses the certificate."""
    v = _ev(e, {}, funs, st, {}, None)[1]
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"quantifier bound not an int: {e!r}")
    return v


def _unroll(e: dict, funs: dict, st, budget: list, bounds: list) -> dict:
    """Replace bounded quantifiers (ground bounds) with finite conjunctions
    or disjunctions. `budget` is a one-element countdown over emitted
    instances; exhausting it raises and the certificate is refused. Each
    bound's value is recorded in `bounds` as an equation the kernel
    re-proves (step 1 of the certificate section)."""
    if "forall" in e or "exists" in e:
        kind = "forall" if "forall" in e else "exists"
        q = e[kind]
        lo_e = _unroll(q["lo"], funs, st, budget, bounds)
        hi_e = _unroll(q["hi"], funs, st, budget, bounds)
        lo, hi = _gint(lo_e, funs, st), _gint(hi_e, funs, st)
        for b_e, b_v in ((lo_e, lo), (hi_e, hi)):
            if b_e != _tlit(b_v):            # a literal bound proves itself
                bounds.append({"op": "==", "args": [b_e, _tlit(b_v)]})
        insts = []
        for k in range(lo, hi):
            budget[0] -= 1
            if budget[0] < 0:
                raise ValueError("quantifier unroll budget exhausted")
            insts.append(_unroll(subst(q["body"], {q["var"]: _tlit(k)}),
                                 funs, st, budget, bounds))
        if not insts:
            return {"bool": kind == "forall"}
        return _nary("and" if kind == "forall" else "or", insts)
    if "ite" in e:
        c = e["ite"]
        return {"ite": {"cond": _unroll(c["cond"], funs, st, budget, bounds),
                        "then": _unroll(c["then"], funs, st, budget, bounds),
                        "else": _unroll(c["else"], funs, st, budget, bounds)}}
    if "call" in e:
        c = e["call"]
        return {"call": {"fun": c["fun"],
                         "args": [_unroll(a, funs, st, budget, bounds)
                                  for a in c["args"]]}}
    if "op" in e:
        return {"op": e["op"],
                "args": [_unroll(a, funs, st, budget, bounds)
                         for a in e.get("args", [])]}
    return e


def _name_seqs(e: dict, names: dict, used: dict) -> dict:
    """Replace every seq literal by the witness name bound to that value
    (see the certificate section: `[]` needs a typed binding). A value
    with no name refuses the certificate (KeyError)."""
    if "_seq" in e:
        key = tuple(e["_seq"])
        used[key] = names[key]
        return {"var": names[key]}
    if "ite" in e:
        c = e["ite"]
        return {"ite": {"cond": _name_seqs(c["cond"], names, used),
                        "then": _name_seqs(c["then"], names, used),
                        "else": _name_seqs(c["else"], names, used)}}
    if "call" in e:
        c = e["call"]
        return {"call": {"fun": c["fun"],
                         "args": [_name_seqs(a, names, used)
                                  for a in c["args"]]}}
    if "op" in e:
        return {"op": e["op"],
                "args": [_name_seqs(a, names, used)
                         for a in e.get("args", [])]}
    return e


def _seq_lit(v: tuple) -> str:
    return "[" + ", ".join(str(x) for x in v) + "]"


def _certificate(task: dict, twin_body: list, w: dict) -> str | None:
    """The appended t_refutation_certificate lemma for a measured twin
    witness, or None when the witness is not expressible as a ground
    certificate under the rules in the section comment above."""
    kind = w.get("_kind")
    names = {k: v for k, v in w.items() if not k.startswith("_")}
    funs = {f["name"]: f for f in task.get("spec_funs", [])}
    st = interp.St()
    try:
        m = {n: _tlit(v) for n, v in names.items()}
        if kind == "value":
            if w.get("_ens") is not True:
                return None      # a drift a sound kernel may still accept
            tw = w.get("_twin")
            if isinstance(tw, str) or not isinstance(tw, (bool, int, list)):
                return None
            m2 = dict(m)
            m2[task["returns"][0]["name"]] = _tlit(tw)
            parts = [subst(rq, m2) for rq in task.get("requires", [])]
            parts.append(_not(_conj([subst(en, m2)
                                     for en in task["ensures"]])))
        elif kind == "exit":
            loop = _twin_loop(task["body"], twin_body)
            if loop is None:
                return None
            # The obligation is at the RETURN: the loop-exit state run
            # through whatever follows the loop (interp.exit_env, None under
            # an enclosing loop). A tail loop runs nothing and the formula
            # is unchanged. Measured 2026-09-07 (ROADMAP 12.5): slow_max
            # assigns z after its loop, and this lemma, stating not-ensures
            # at the loop's own z, minted REFUTED on a twin dafny proves.
            ret = task["returns"][0]["name"]
            post = interp.exit_env(task, twin_body, loop, names)
            if post is None:
                return None
            m2 = dict(m)
            m2[ret] = _tlit(post[ret])
            parts = [subst(rq, m) for rq in task.get("requires", [])]
            parts += [subst(iv, m) for iv in loop.get("invariants", [])]
            parts.append(_not(subst(loop["cond"], m)))
            parts.append(_not(_conj([subst(en, m2)
                                     for en in task["ensures"]])))
        else:
            return None          # preservation / undefined: see above
        bounds: list = []
        unrolled = _unroll(_conj(parts), funs, st, [_UNROLL_CAP], bounds)
        facts: dict = {}
        hoist: list = []
        pruned, val = _ev(_conj(bounds + [unrolled]), {}, funs, st, facts,
                          hoist)
        if val is not True:
            return None          # the interpreter itself rejects it
        if len(hoist) > _HOIST_CAP:
            raise ValueError("hoist cap exceeded")
        seen: dict = {}
        for h in hoist + [pruned]:
            seen.setdefault(json.dumps(h, sort_keys=True), h)
        formula = _conj(list(seen.values()))
        seq_names: dict = {}
        for n, v in names.items():
            if isinstance(v, list):
                seq_names.setdefault(tuple(v), n)
        used: dict = {}
        formula = _name_seqs(formula, seq_names, used)
        ladder: list[str] = []
        ladder_seqs: dict = {}
        if len(facts) <= _LADDER_CAP:
            for (fn, keys), v in facts.items():
                if isinstance(v, list):
                    continue
                args = []
                for tag, val_k in keys:
                    if tag == "seq":
                        if val_k not in seq_names:
                            break
                        ladder_seqs[val_k] = seq_names[val_k]
                        args.append(seq_names[val_k])
                    else:
                        args.append(expr(_tlit(val_k)))
                else:
                    ladder.append(f"  assert {fn}({', '.join(args)}) == "
                                  f"{expr(_tlit(v))};")
        body = expr(formula)
    except (ValueError, KeyError, TypeError, IndexError, interp.Undef,
            interp.Budget, RecursionError):
        return None
    lets = "".join(f"var {n}: seq<int> := {_seq_lit(v)}; "
                   for v, n in used.items())
    lines = [f"lemma {CERT_NAME}()", f"  ensures {lets}{body}", "{"]
    lines += [f"  var {n}: seq<int> := {_seq_lit(v)};"
              for v, n in ladder_seqs.items()]
    lines += ladder
    lines.append("}")
    return "\n".join(lines) + "\n"


# `witness` is the twin's measured witness (harness.twin_cached). Twin call
# sites pass it; when it is present and ground-certificatable, the lowering
# appends the refutation certificate lemma (see the section above).
def lower(task: dict, body: list, witness: dict | None = None) -> str:
    if CERT_NAME in _collect_names(task):
        raise ValueError(f"task mentions the protocol name {CERT_NAME!r}")
    self_name = task["name"]
    method = self_name.capitalize()
    ctx = _Ctx(task, method)
    lines = []

    for f in task.get("spec_funs", []):
        ps = ", ".join(f"{p['name']}: {TYPES[p['type']]}"
                       for p in f["params"])
        lines.append(f"function {f['name']}({ps}): {TYPES[f['result']]}")
        lines.append(f"  decreases {expr(f['decreases'], self_name)}")
        lines.append("{")
        lines.append(f"  {expr(f['body'], self_name)}")
        lines.append("}")
        lines.append("")

    ps = ", ".join(f"{p['name']}: {TYPES[p['type']]}"
                   for p in task["params"])
    ret = task["returns"][0]
    lines.append(f"method {method}({ps}) "
                 f"returns ({ret['name']}: {TYPES[ret['type']]})")
    for e in task.get("requires", []):
        lines.append(f"  requires {expr(e, self_name)}")
    for e in task["ensures"]:
        lines.append(f"  ensures {expr(e, self_name)}")
    if "decreases" in task:
        lines.append(f"  decreases {expr(task['decreases'], self_name)}")
    lines.append("{")
    lines.append(stmts(body, "  ", ctx))
    lines.append("}")
    src = "\n".join(lines) + "\n"
    if witness is not None:
        cert = _certificate(task, body, witness)
        if cert:
            src += "\n" + cert
    return src


if __name__ == "__main__":
    import harness
    raise SystemExit(harness.run_all(sys.argv[1:], lower, dafny_backend, "dfy"))
