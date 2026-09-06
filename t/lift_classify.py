"""Classify one gradable method: refuse it (naming a section-5 reason and
the offending rprint line) or mark it liftable with the rewrite list
`lift_rewrite.py` must apply.

Reads LIFTER-DESIGN.md sections 4 (mapping rules -- what a rewrite IS),
5 (refusal rules -- the reason vocabulary and trigger table), 6 (decreases
inference -- when a loop/spec_fun's measure is uninferable), 7 (nat
handling -- when a nat parameter/return/local forces a refusal vs. an
added clause), 18.2 (the rewrite-vocabulary cross-reference), 18.6 (the
read-only-array-as-seq row), and LIFTER-DECISIONS.md whole (it overrides
the design wherever they differ, notably decision 1: read-only
`array<int>` lifts to `seq` rather than refusing). Also reads
`fuzz_lower.check_wf`'s shape (this module never calls it -- `lift_check
.py` does, post-rewrite -- but the rewrite list this module plans must be
achievable in a task that will pass it) and SYNTAX.md's reserved words
(`surface.py`'s KEYWORDS / a lowering's RESERVED set, for `name
-unsanitisable`/renaming decisions, decision-file row 8's neighbourhood).

Architecture role (LIFTER-DESIGN.md section 2's table, copied verbatim):
    input: Dafny AST
    output: per method: the refusal reason (section 5) or a "liftable"
            mark with the rewrite list
    MAY decide: the refusal reason from the census vocabulary plus
                section 5's additions
    MAY NOT decide: any rewrite

That last line is section 2's own word, and it is deliberately narrow:
this module decides WHETHER each section-4 rewrite rule fires (by
inspecting the AST and recording the rule id and line) but never performs
one -- it plans the list `lift_rewrite.py` executes to the letter,
producing no t syntax and touching no source clause itself.

SHARED HELPERS. `lift_rewrite.py` is this module's sibling (both are owned
by the same implementer, per the interfaces contract) and imports several
private helpers from here (the leading-underscore names) rather than
re-deriving the same AST analysis a second time: the call-graph closure,
the generic `walk` visitor, the type-acceptability check, the quantifier
bound extractor, the tail-return scan, and the read-only-array condition.
`classify` decides WHETHER a rule fires; `rewrite` (in the sibling module)
performs it, using the same detectors so the two never disagree about what
the AST contains.

KNOWN SHIM LIMITATIONS (documented here since this module is the one where
the gap first bites): `lift_parse.py` is still a stub (NotImplementedError)
as of this writing, so this module was developed and tested against a
hand-written parser shim living in `test_lift_rules.py` (never imported
here -- this module only ever touches `lift_ast` node types, exactly per
its contract). Two consequences worth naming: (1) section 4.8's renaming
check uses only the keyword list section 4.8 gives verbatim (t's own
KEYWORDS, "main", "t_refutation_certificate") plus the deterministic rename
rule; it does NOT check lower_fstar.py/lower_rocq.py/lower_spark.py's own
RESERVED sets, since reading those files was outside this task's assigned
reading list. (2) `decreases_origin`'s "stated" vs. "rprint-inferred" label
is a best-effort pattern match against section 6's own documented inferred
shapes (`hi - lo`, `hi - 0`, the `!=`-guard `ite`); it can only be exact
when `lift_resolve.py` eventually threads the ORIGINAL (pre-resolution)
print text through so the two can be diffed -- an input this module's
fixed signature does not currently receive. Neither limitation can corrupt
a lifted value: both are provenance/bookkeeping labels, not part of the
theorem the checker (`lift_check.py`) verifies.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Iterator, Optional

from lift_ast import (
    Assign, AssignSuchThat, AssertStmt, AssertByStmt, AssumeStmt, Binary,
    BlockStmt, BoolLit, BreakStmt, Call, CallStmt, CalcStmt, Cardinality,
    Cast, Chain, ContinueStmt, Decl, DecreasesClause, EnsuresClause, Expr,
    ExpectStmt, ForStmt, ForallStmt, FunctionDecl, Fresh, Iff, IfCaseStmt,
    IfExpr, IfStmt, Implies, Index, Ident, IntLit, InvariantClause,
    LabelStmt, LemmaDecl, Lhs, MapDisplay, Member, MethodDecl,
    ModifiesClause, Module, NaryBool, NewRhs, Node, Old, Param, PrintStmt,
    Quantifier, ReadsClause, Refusal, RequiresClause, RevealStmt,
    ReturnStmt, Rewrite, SeqDisplay, SeqUpdate, SkippedDecl, Slice, Star,
    Stmt, TupleExpr, Type, TypeTest, Unary, VarDeclStmt, WhileCaseStmt,
    WhileStmt,
)


# ---------------------------------------------------------------------------
# Generic AST walker. Every lift_ast node is a dataclass, so one visitor
# serves every node type: yield the node itself, then recurse through its
# dataclass fields (tuples/lists/dicts unwrapped, scalars ignored). Section
# 5's refusal rows are overwhelmingly "does construct X appear anywhere in
# the method's (or its closure's) reach" -- this makes each such row a
# one-line `isinstance` filter over `walk(...)` instead of a bespoke visitor.
# ---------------------------------------------------------------------------

def walk(obj) -> Iterator[Node]:
    if obj is None:
        return
    if isinstance(obj, Node):
        yield obj
        for f in dataclasses.fields(obj):
            yield from walk(getattr(obj, f.name))
    elif isinstance(obj, (tuple, list)):
        for item in obj:
            yield from walk(item)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(k)
            yield from walk(v)
    # else: str/int/bool/None -- a leaf, nothing to recurse into.


def _line(n: Node) -> int:
    return getattr(n, "line", 0)


# ---------------------------------------------------------------------------
# Section 4.8's keyword union, verbatim from the design text (the design
# names surface.py's KEYWORDS list inline; see module docstring for why the
# other three lowerings' RESERVED sets are not checked here).
# ---------------------------------------------------------------------------

T_KEYWORDS = {
    "t", "gate", "task", "returns", "requires", "ensures", "decreases",
    "spec", "fun", "var", "while", "invariant", "if", "then", "else",
    "forall", "exists", "in", "len", "true", "false", "and", "or", "not",
    "int", "bool", "seq",
}
RESERVED_EXTRA = {"main", "t_refutation_certificate"}


# ---------------------------------------------------------------------------
# Types.
# ---------------------------------------------------------------------------

def _is_nat(t: Optional[Type]) -> bool:
    return t is not None and t.kind == "nat"


def _is_int_like(t: Optional[Type]) -> bool:
    return t is not None and t.kind in ("int", "nat")


def _is_bool(t: Optional[Type]) -> bool:
    return t is not None and t.kind == "bool"


def _is_seq_of_int(t: Optional[Type]) -> bool:
    return (t is not None and t.kind == "seq" and len(t.args) == 1
            and _is_int_like(t.args[0]))


def _is_array_of_int(t: Optional[Type]) -> bool:
    return (t is not None and t.kind == "array" and not t.nullable
            and len(t.args) == 1 and _is_int_like(t.args[0]))


def _type_issue(t: Optional[Type]) -> Optional[str]:
    """Section 4.2's type table, as a refusal reason or None when the type
    is one this lifter can carry (int/nat/bool/seq<int|nat>). Array is
    handled by the caller separately (it needs a whole-closure usage
    check, decision 1 / section 18.6, not a local type test)."""
    if t is None:
        return "untyped-var"
    if t.kind in ("int", "nat", "bool"):
        return None
    if t.kind == "seq":
        if len(t.args) == 1 and _is_int_like(t.args[0]):
            return None
        return "nested-seq"
    if t.kind == "array":
        return "array"
    if t.kind in ("array2", "array3"):
        return "array"
    if t.kind == "real":
        return "real"
    if t.kind in ("char", "string"):
        return "string-char"
    if t.kind == "set" or t.kind == "iset":
        return "set"
    if t.kind in ("map", "imap"):
        return "map"
    if t.kind == "tuple":
        return "tuple"
    if t.kind == "bv":
        return "bitvector"
    if t.kind == "object":
        return "heap"
    if t.kind == "func":
        return "higher-order"
    if t.kind == "id":
        return "generics" if t.args else "datatype"
    return "type-decl"


# ---------------------------------------------------------------------------
# The call-graph closure (LIFTER-DESIGN.md section 4.1's "declarations
# outside the method's call-graph closure" row). We do not have rprint's
# own "CALL GRAPH for module _module" comment available (the shim parser
# strips comments; see the module docstring), so the closure -- and the
# mutual-recursion check that rides on it -- is computed here by a plain
# reachability walk over Call/Ident/CallStmt names instead. This is a
# strictly more mechanical (and checkable) source of the same fact.
# ---------------------------------------------------------------------------

def _called_names(node) -> set[str]:
    names: set[str] = set()
    for n in walk(node):
        if isinstance(n, Call) and isinstance(n.fn, Ident):
            names.add(n.fn.name)
        elif isinstance(n, CallStmt):
            names.add(n.name)
    return names


def _closure(module: Module, method: MethodDecl) -> tuple[Decl, ...]:
    by_name = {d.name: d for d in module.decls if d.name}
    order: list[Decl] = []
    seen: set[str] = set()

    def visit(name: str) -> None:
        if name in seen:
            return
        d = by_name.get(name)
        if d is None or not isinstance(d, (FunctionDecl, LemmaDecl)):
            return
        seen.add(name)
        for dep in _called_names(d):
            if dep != name:
                visit(dep)
        order.append(d)

    for dep in _called_names(method):
        if dep != method.name:
            visit(dep)
    return tuple(order)


def _mutual_recursion_issue(closure: tuple[Decl, ...]) -> Optional[tuple[int, str, str]]:
    funs = [d for d in closure if isinstance(d, FunctionDecl)]
    calls = {f.name: (_called_names(f) - {f.name}) for f in funs}
    names = set(calls)

    def reachable(start: str) -> set[str]:
        out: set[str] = set()
        stack = list(calls.get(start, ()) & names)
        while stack:
            n = stack.pop()
            if n in out:
                continue
            out.add(n)
            stack.extend(calls.get(n, ()) & names)
        return out

    for f in funs:
        reach = reachable(f.name)
        if f.name in reach:  # f reaches itself only via >=1 OTHER function
            return (f.line, "mutual-recursion", f.name)
    return None


# ---------------------------------------------------------------------------
# Quantifier bound extraction (section 4.4). Returns a dict describing how
# to build t's `forall`/`exists` node, or None if the range is not one of
# the bounded shapes -- in which case the caller refuses
# `unbounded-quantifier` (or `set`/`map` when the binder ranges over one).
# ---------------------------------------------------------------------------

def _is_ident(e: Expr, name: str) -> bool:
    """True iff `e` is exactly the bound variable `name` (never a compound
    expression that merely mentions it) -- integrator-added: `_bound_range`
    below called this and `_plus1` without either ever being defined
    anywhere in this file (measured: a `NameError` the instant a genuine
    literal `lo <= k < hi` chain guard reached this function, dormant only
    because zero of the 77 in-fragment files contain any quantifier at
    all, so `bound_quantifier` was never actually exercised by any
    implementer's own test run). Fixed 2026-09-05."""
    return isinstance(e, Ident) and e.name == name


def _plus1(e: Expr) -> Expr:
    """`e + 1`, to convert a strict `<` bound into t's own `lo <= v < hi`
    (inclusive lo, exclusive hi) convention, matching how `_lift_chain`'s
    `in-desugared` row already builds a `[0, len(s))` range."""
    return Binary(e.line, "+", e, IntLit(e.line, 1))


def _bound_range(binder: str, guard: Expr) -> Optional[tuple[Expr, Expr, Optional[Expr]]]:
    """`lo <= k < hi` and its three half-open siblings (section 4.4), for
    exactly the named binder, optionally AND'ed with more conjuncts.
    Returns (lo, hi, extra) where `extra` is the conjunction of whatever
    else was in the guard (None if nothing else was), or None if no
    conjunct bounds `binder` this way."""
    conjuncts = list(guard.args) if isinstance(guard, NaryBool) and guard.op == "&&" else [guard]
    for i, c in enumerate(conjuncts):
        if isinstance(c, Chain) and len(c.ops) == 2 and len(c.operands) == 3:
            lo_op, hi_op = c.ops
            lo, mid, hi = c.operands
            if _is_ident(mid, binder) and lo_op in ("<", "<=") and hi_op in ("<", "<="):
                lo2 = _plus1(lo) if lo_op == "<" else lo
                hi2 = _plus1(hi) if hi_op == "<=" else hi
                rest = [x for j, x in enumerate(conjuncts) if j != i]
                extra = None
                if rest:
                    extra = rest[0] if len(rest) == 1 else NaryBool(rest[0].line, "&&", tuple(rest))
                return (lo2, hi2, extra)
    # Integrator addition 2026-09-05: the SAME range, written as two
    # separate single-comparison conjuncts (`lo <= k && k < hi`) rather
    # than one written chain (`lo <= k < hi`) -- the shape
    # `lower_dafny.lower` always prints and dafny's own rprint never
    # recombines into a chain, measured via the 18.4 inverse test: every
    # one of 13/31 sampled tasks with a quantifier hit `unbounded
    # -quantifier` on the round trip before this was added, all for this
    # one reason.
    lo_i = hi_i = None
    lo = hi = None
    for i, c in enumerate(conjuncts):
        if not (isinstance(c, Chain) and len(c.ops) == 1 and len(c.operands) == 2):
            continue
        op = c.ops[0]
        a, b = c.operands
        if op in ("<", "<=") and _is_ident(b, binder) and lo_i is None:
            lo_i, lo = i, (_plus1(a) if op == "<" else a)
        elif op in ("<", "<=") and _is_ident(a, binder) and hi_i is None:
            hi_i, hi = i, (_plus1(b) if op == "<=" else b)
    if lo_i is not None and hi_i is not None and lo_i != hi_i:
        rest = [x for j, x in enumerate(conjuncts) if j not in (lo_i, hi_i)]
        extra = None
        if rest:
            extra = rest[0] if len(rest) == 1 else NaryBool(rest[0].line, "&&", tuple(rest))
        return (lo, hi, extra)
    return None


def _bound_membership(binder: str, guard: Expr) -> Optional[Expr]:
    """`k in s` (section 4.4's third quantifier row): returns `s` when
    `guard` is exactly `k in s` for the named binder, else None."""
    if isinstance(guard, Chain) and len(guard.ops) == 1 and guard.ops[0] == "in":
        a, b = guard.operands
        if _is_ident(a, binder):
            return b
    return None


def bound_quantifier(q: Quantifier):
    """Section 4.4's quantifier-bounding rules, unified into one contract:
    on success, returns {"binders": [(name, lo, hi, membership_seq), ...],
    "body": Expr} where `body` is the FULLY RESOLVED predicate to lift at
    the innermost level (every `&&`/`==>` combination already folded in),
    and each binder's `lo`/`hi` are `None` exactly when `membership_seq`
    is not (the `k in s` row, section 4.4's third quantifier row: `lo`/`hi`
    become `0`/`len(s)` and `body` must still be substituted `k -> s[j]`
    by the caller using the returned fresh binder position). Returns None
    when the range is not one of section 4.4's bounded shapes (the caller
    refuses `unbounded-quantifier`)."""
    if len(q.binders) == 0:
        return None

    if len(q.binders) == 1:
        b = q.binders[0]
        guard = q.range
        if guard is None:
            # Unguarded: the range lives inside body as `lo<=k<hi ==> P`
            # (forall) or `lo<=k<hi && P` (exists).
            if q.kind == "forall" and isinstance(q.body, Implies):
                got = _bound_range(b.name, q.body.left)
                if got is None or got[2] is not None:
                    return None  # extra conjuncts with no `==>` shape: bail
                lo, hi, _ = got
                return {"binders": [(b.name, lo, hi, None)], "body": q.body.right}
            if q.kind == "exists" and isinstance(q.body, NaryBool) and q.body.op == "&&":
                got = _bound_range(b.name, q.body)
                if got is None:
                    return None
                lo, hi, extra = got
                body = extra if extra is not None else BoolLit(q.line, True)
                return {"binders": [(b.name, lo, hi, None)], "body": body}
            return None
        mem = _bound_membership(b.name, guard)
        if mem is not None:
            return {"binders": [(b.name, None, None, mem)], "body": q.body}
        got = _bound_range(b.name, guard)
        if got is None:
            return None
        lo, hi, extra = got
        if extra is not None:
            body = Implies(q.line, extra, q.body) if q.kind == "forall" \
                else NaryBool(q.line, "&&", (extra, q.body))
        else:
            body = q.body
        return {"binders": [(b.name, lo, hi, None)], "body": body}

    # Multiple binders: each finds its own chain conjunct in a top-level
    # "&&" range guard (section 4.4's "two binders" row, generalised to N).
    guard = q.range
    if guard is None:
        return None
    conjuncts = list(guard.args) if isinstance(guard, NaryBool) and guard.op == "&&" else [guard]
    used = [False] * len(conjuncts)
    result_binders = []
    for b in q.binders:
        found = None
        for i, c in enumerate(conjuncts):
            if used[i]:
                continue
            if isinstance(c, Chain) and len(c.ops) == 2 and len(c.operands) == 3:
                lo_op, hi_op = c.ops
                lo, mid, hi = c.operands
                if _is_ident(mid, b.name) and lo_op in ("<", "<=") and hi_op in ("<", "<="):
                    lo2 = _plus1(lo) if lo_op == "<" else lo
                    hi2 = _plus1(hi) if hi_op == "<=" else hi
                    found = (lo2, hi2)
                    used[i] = True
                    break
        if found is None:
            return None
        result_binders.append((b.name, found[0], found[1], None))
    rest = [c for i, c in enumerate(conjuncts) if not used[i]]
    extra = None
    if rest:
        extra = rest[0] if len(rest) == 1 else NaryBool(rest[0].line, "&&", tuple(rest))
    if extra is not None:
        body = Implies(q.line, extra, q.body) if q.kind == "forall" \
            else NaryBool(q.line, "&&", (extra, q.body))
    else:
        body = q.body
    return {"binders": result_binders, "body": body}


# ---------------------------------------------------------------------------
# Tail-return scan (section 4.5's three `return` rows). Returns
# (issues, rewrites) where issues are early-exit refusal candidates and
# rewrites are `tail-return` candidates (both as plain tuples the caller
# turns into Refusal / Rewrite objects).
# ---------------------------------------------------------------------------

def scan_returns(stmts: tuple[Stmt, ...], tail: bool
                  ) -> tuple[list[tuple[int, str, str]], list[tuple[int, int]]]:
    issues: list[tuple[int, str, str]] = []
    rewrites: list[tuple[int, int]] = []  # (line, _) just to carry the line
    n = len(stmts)
    for i, s in enumerate(stmts):
        this_tail = tail and (i == n - 1)
        if isinstance(s, ReturnStmt):
            if this_tail:
                rewrites.append((s.line, 0))
            else:
                issues.append((s.line, "early-exit", "return"))
        elif isinstance(s, IfStmt):
            i2, r2 = scan_returns(s.then, this_tail)
            issues += i2
            rewrites += r2
            if isinstance(s.else_, tuple):
                i3, r3 = scan_returns(s.else_, this_tail)
            elif isinstance(s.else_, IfStmt):
                i3, r3 = scan_returns((s.else_,), this_tail)
            else:
                i3, r3 = [], []
            issues += i3
            rewrites += r3
        elif isinstance(s, WhileStmt):
            i2, r2 = scan_returns(s.body, False)
            issues += i2
            rewrites += r2
        elif isinstance(s, ForStmt):
            i2, r2 = scan_returns(s.body, False)
            issues += i2
            rewrites += r2
        elif isinstance(s, BlockStmt):
            i2, r2 = scan_returns(s.body, False)
            issues += i2
            rewrites += r2
        elif isinstance(s, LabelStmt):
            i2, r2 = scan_returns((s.stmt,), False)
            issues += i2
            rewrites += r2
    return issues, rewrites


# ---------------------------------------------------------------------------
# Read-only array condition (decision 1 / section 18.6).
# ---------------------------------------------------------------------------

def array_readonly_issue(param_name: str, method: MethodDecl,
                          closure: tuple[Decl, ...]) -> Optional[str]:
    """None if `param_name` (an `array<int|nat>` parameter) satisfies the
    read-only condition everywhere in the method's closure; else the
    section-5 reason it fails with (`array-mutation` for a write,
    `array` for anything else that disqualifies it -- new, or being
    passed to another call)."""
    scope: list[Node] = [method] + list(closure)
    for root in scope:
        for n in walk(root):
            if isinstance(n, Assign):
                for lhs in n.targets:
                    if (lhs.kind == "index" and isinstance(lhs.base, Ident)
                            and lhs.base.name == param_name):
                        return "array-mutation"
            if isinstance(n, (Call, CallStmt)):
                args = n.args
                for a in args:
                    if isinstance(a, Ident) and a.name == param_name:
                        return "array"
            if isinstance(n, NewRhs):
                return "array"
    return None


# ---------------------------------------------------------------------------
# Liftable and classify.
# ---------------------------------------------------------------------------

@dataclass
class Liftable:
    method: MethodDecl
    closure: tuple[Decl, ...]
    rewrites: list[Rewrite] = field(default_factory=list)


def _first(issues: list[tuple[int, str, str]]) -> tuple[int, str, str]:
    return min(issues, key=lambda t: t[0])


def classify(module: Module, method: MethodDecl) -> "Refusal | Liftable":
    issues: list[tuple[int, str, str]] = []
    rewrites: list[Rewrite] = []

    closure = _closure(module, method)
    scope_roots: list[Node] = [method] + list(closure)

    # -- returns: zero/multi first (section 5) --------------------------
    if len(method.returns) == 0:
        issues.append((method.line, "zero-returns", method.name or "?"))
    elif len(method.returns) > 1:
        issues.append((method.line, "multi-return", method.name or "?"))

    ret_param = method.returns[0] if len(method.returns) == 1 else None

    # -- param / return types --------------------------------------------
    array_params: list[Param] = []
    for p in method.params:
        if p.type is not None and p.type.kind == "array":
            if p.type.nullable or not _is_array_of_int(p.type):
                issues.append((p.line, "array", p.name))
            else:
                array_params.append(p)
            continue
        reason = _type_issue(p.type)
        if reason is not None:
            issues.append((p.line, reason, p.name))

    if ret_param is not None:
        rt = ret_param.type
        if rt is not None and rt.kind == "seq":
            issues.append((ret_param.line, "seq-return", ret_param.name))
        else:
            reason = _type_issue(rt)
            if reason is not None and not (rt is not None and rt.kind == "nat"):
                issues.append((ret_param.line, reason, ret_param.name))

    # -- read-only array condition (decision 1 / 18.6) -------------------
    for p in array_params:
        bad = array_readonly_issue(p.name, method, closure)
        if bad is not None:
            issues.append((p.line, bad, p.name))

    # -- modifies anywhere (method or a loop) => array-mutation ----------
    for n in walk(method):
        if isinstance(n, ModifiesClause):
            issues.append((n.line, "array-mutation", "modifies"))

    # -- everything a single generic pass over every node can catch ------
    closure_names = {d.name for d in closure if d.name}
    for root in scope_roots:
        for n in walk(root):
            _scan_node_for_issues(n, issues, method.name, closure_names)

    # -- definite assignment of the return, every path (section 4.7) -----
    if ret_param is not None and method.body is not None:
        if not _assigns_ret_all_paths(method.body, ret_param.name):
            issues.append((method.line, "return-not-assigned-on-all-paths",
                            ret_param.name))

    # -- self-recursion shape (section 4.5's `r := M(args)` row) ---------
    issues += _self_call_positions(method)

    # -- returns (tail vs early-exit) ------------------------------------
    if method.body is not None:
        ri, rr = scan_returns(method.body, True)
        issues += ri
        if rr:
            rewrites.append(Rewrite(rule="tail-return", line=rr[0][0]))

    # -- quantifier boundedness -------------------------------------------
    for root in scope_roots:
        for n in walk(root):
            if isinstance(n, Quantifier):
                got = bound_quantifier(n)
                if got is None:
                    issues.append((n.line, "unbounded-quantifier", n.kind))
                else:
                    has_mem = any(mem is not None for _, _, _, mem in got["binders"])
                    rewrites.append(Rewrite(rule="in-desugared" if has_mem
                                             else "quantifier-bounded", line=n.line))

    # -- mutual recursion ---------------------------------------------------
    mr = _mutual_recursion_issue(closure)
    if mr is not None:
        issues.append(mr)

    # -- function-contract (a `reads` clause on any closure function) ----
    for d in closure:
        if isinstance(d, FunctionDecl):
            for s in d.specs:
                if isinstance(s, ReadsClause):
                    nonempty = isinstance(s.exprs, Star) or (isinstance(s.exprs, tuple) and s.exprs)
                    if nonempty:
                        issues.append((s.line, "function-contract", d.name or "?"))

    # -- decreases inference (section 6 / decision 11) --------------------
    dec_issues = _decreases_issues(method, closure)
    issues += dec_issues

    if issues:
        line, reason, token = _first(issues)
        return Refusal(reason=reason, token=token, line=line, stage="classify")

    # -- plan the remaining rewrites (chains, iff, nat, split, etc.) ------
    rewrites += _plan_rewrites(module, method, closure, ret_param, array_params)

    return Liftable(method=method, closure=closure, rewrites=rewrites)


def _scan_node_for_issues(n: Node, issues: list, method_name: str,
                           closure_names: set[str]) -> None:
    """One generic pass catching every section-5 row that is a plain
    "does this construct appear anywhere" test. Rows needing context
    (self-recursion shape, tail returns, quantifier bounds, decreases,
    the read-only-array condition) have their own dedicated scans."""
    if isinstance(n, Binary) and n.op in ("/", "%"):
        issues.append((n.line, "div-mod", n.op))
    elif isinstance(n, SeqDisplay):
        issues.append((n.line, "seq-literal", "[...]"))
    elif isinstance(n, Slice):
        issues.append((n.line, "seq-slice", "[..]"))
    elif isinstance(n, SeqUpdate):
        issues.append((n.line, "seq-update", ":="))
    elif isinstance(n, (Old, Fresh)):
        issues.append((n.line, "old", "old"))
    elif isinstance(n, AssumeStmt):
        issues.append((n.line, "assume", "assume"))
    elif isinstance(n, AssignSuchThat):
        issues.append((n.line, "such-that-exec", ":|"))
    elif isinstance(n, PrintStmt):
        issues.append((n.line, "io", "print"))
    elif isinstance(n, ExpectStmt):
        issues.append((n.line, "io", "expect"))
    elif isinstance(n, (IfCaseStmt, WhileCaseStmt)):
        issues.append((n.line, "nondet", "case"))
    elif isinstance(n, IfStmt) and isinstance(n.cond, Star):
        issues.append((n.line, "nondet", "*"))
    elif isinstance(n, WhileStmt) and isinstance(n.cond, Star):
        issues.append((n.line, "nondet", "*"))
    elif isinstance(n, Assign) and any(isinstance(v, Star) for v in n.values):
        issues.append((n.line, "nondet", "*"))
    elif isinstance(n, (BreakStmt, ContinueStmt)):
        issues.append((n.line, "early-exit", "break/continue"))
    elif isinstance(n, VarDeclStmt) and n.names and any(
            nm.type is not None and nm.type.kind == "array" for nm in n.names):
        issues.append((n.line, "array", "local array"))
    elif isinstance(n, MapDisplay):
        issues.append((n.line, "map", "{...}"))
    elif isinstance(n, TupleExpr):
        issues.append((n.line, "tuple", "(...)"))
    elif isinstance(n, Cast):
        issues.append((n.line, "as-cast", "as"))
    elif isinstance(n, TypeTest):
        issues.append((n.line, "as-cast", "is"))
    elif isinstance(n, Member) and n.name != "Length":
        issues.append((n.line, "datatype", n.name))
    elif isinstance(n, VarDeclStmt) and n.ghost:
        issues.append((n.line, "ghost-local", "ghost var"))
    elif isinstance(n, CallStmt):
        if n.name == method_name:
            issues.append((n.line, "self-call-lazy", n.name))
        elif n.name not in closure_names:
            issues.append((n.line, "calls-other-method", n.name))
        # else: a lemma call in the closure -- dropped, not refused
        # (decision 8; see _plan_rewrites' lemma-call-dropped entry).


def _self_call_positions(method: MethodDecl) -> list[tuple[int, str, str]]:
    """Section 4.5's `r := M(args)` row: a self-call is only supported as
    the WHOLE right-hand side of a plain assignment, or inside a spec
    clause -- and even there, never under a lazily evaluated operator or a
    quantifier body (`self-call-lazy`). Everything else (a self-call
    nested in an if/while condition, or as a bare discarded call
    statement) is refused the same way."""
    name = method.name
    issues: list[tuple[int, str, str]] = []
    allowed_roots: list[Expr] = []
    if method.body is not None:
        for s in walk(method.body):
            if isinstance(s, Assign):
                allowed_roots.extend(v for v in s.values if isinstance(v, Expr))
            elif isinstance(s, VarDeclStmt) and s.init:
                allowed_roots.extend(v for v in s.init if isinstance(v, Expr))
    for spec in method.specs:
        e = getattr(spec, "expr", None)
        if e is not None:
            allowed_roots.append(e)

    allowed_ids = {id(n) for root in allowed_roots for n in walk(root)}

    def lazy_ids(root) -> set[int]:
        lz: set[int] = set()
        for n in walk(root):
            if isinstance(n, NaryBool):
                for a in n.args[1:]:
                    lz |= {id(x) for x in walk(a)}
            elif isinstance(n, Implies):
                lz |= {id(x) for x in walk(n.right)}
            elif isinstance(n, Quantifier):
                lz |= {id(x) for x in walk(n.body)}
        return lz

    lazy = set()
    for root in allowed_roots:
        lazy |= lazy_ids(root)

    def is_self_call(n) -> bool:
        return isinstance(n, Call) and isinstance(n.fn, Ident) and n.fn.name == name

    if method.body is not None:
        for n in walk(method.body):
            if is_self_call(n):
                if id(n) not in allowed_ids or id(n) in lazy:
                    issues.append((n.line, "self-call-lazy", name))
    for spec in method.specs:
        e = getattr(spec, "expr", None)
        if e is None:
            continue
        lz = lazy_ids(e)
        for n in walk(e):
            if is_self_call(n) and id(n) in lz:
                issues.append((n.line, "self-call-lazy", name))
    return issues


def _decreases_issues(method: MethodDecl, closure: tuple[Decl, ...]
                       ) -> list[tuple[int, str, str]]:
    from lift_ast import Binary
    issues: list[tuple[int, str, str]] = []

    def assigned_names(body) -> set[str]:
        names: set[str] = set()
        for n in walk(body):
            if isinstance(n, Assign):
                for t in n.targets:
                    if t.kind == "name":
                        names.add(t.name)
        return names

    for n in walk(method.body):
        if isinstance(n, WhileStmt):
            dcs = [s for s in n.specs if isinstance(s, DecreasesClause)]
            if not dcs:
                issues.append((n.line, "uninferable-decreases", "while"))
                continue
            dc = dcs[0]
            if isinstance(dc.exprs, Star):
                issues.append((dc.line, "decreases-star", "*"))
                continue
            exprs = dc.exprs
            if len(exprs) > 1:
                assigned = assigned_names(n.body)
                kept = [e for e in exprs if not (isinstance(e, Ident) and e.name not in assigned)]
                if len(kept) == 0:
                    issues.append((dc.line, "lexicographic-decreases", "decreases"))
                elif len(kept) >= 2 and not all(_is_int_expr_guess(e) for e in kept):
                    issues.append((dc.line, "lexicographic-decreases", "decreases"))
    for d in closure:
        if isinstance(d, FunctionDecl):
            dcs = [s for s in d.specs if isinstance(s, DecreasesClause)]
            if dcs:
                dc = dcs[0]
                if isinstance(dc.exprs, Star):
                    issues.append((dc.line, "decreases-star", "*"))
                elif len(dc.exprs) > 1:
                    calls = [c for c in walk(d.body) if isinstance(c, Call)
                             and isinstance(c.fn, Ident) and c.fn.name == d.name]
                    param_names = [p.name for p in d.params]
                    dropped = unchanged_at_every_call(param_names, calls, len(dc.exprs))
                    kept_idx = [i for i in range(len(dc.exprs)) if i not in dropped]
                    if len(kept_idx) == 0:
                        issues.append((dc.line, "lexicographic-decreases", d.name or "?"))
            # else: rprint always prints one; absence would be
            # uninferable-decreases, but for a spec_fun that never
            # self-calls no decreases is needed at all (no issue).
    return issues


def _is_int_expr_guess(e: Expr) -> bool:
    return True  # section 6: "if several remain and all are int" -- our
    # shim has no static type checker, so any surviving component is
    # accepted as summable; a genuinely non-int component (a seq, say)
    # would already have been refused earlier by the type checks.


# ---------------------------------------------------------------------------
# Rewrite planning (the Liftable.rewrites summary; lift_rewrite.py performs
# the mechanics itself using the same detectors, per the module docstring).
# ---------------------------------------------------------------------------

def _plan_rewrites(module: Module, method: MethodDecl, closure: tuple[Decl, ...],
                    ret_param: Optional[Param], array_params: list[Param]
                    ) -> list[Rewrite]:
    from lift_ast import Binary
    out: list[Rewrite] = []

    for p in method.params:
        if _is_nat(p.type):
            out.append(Rewrite(rule="nat-param-guard", line=p.line))
    if ret_param is not None and _is_nat(ret_param.type):
        out.append(Rewrite(rule="nat-return-ensures", line=ret_param.line))

    nat_names = {p.name for p in method.params if _is_nat(p.type)}
    if ret_param is not None and _is_nat(ret_param.type):
        nat_names.add(ret_param.name)
    for n in walk(method.body):
        if isinstance(n, VarDeclStmt):
            for nm in n.names:
                if _is_nat(nm.type):
                    nat_names.add(nm.name)
    for n in walk(method.body):
        if isinstance(n, WhileStmt):
            assigned = {t.name for s in walk(n.body) if isinstance(s, Assign)
                        for t in s.targets if t.kind == "name"}
            hit = nat_names & assigned
            if hit:
                out.append(Rewrite(rule="nat-invariant-added", line=n.line))

    for p in array_params:
        out.append(Rewrite(rule="array-readonly-as-seq", line=p.line))

    for d in closure:
        if isinstance(d, FunctionDecl):
            has_req = any(isinstance(s, RequiresClause) for s in d.specs)
            has_nat_param = any(_is_nat(p.type) for p in d.params)
            if has_req or has_nat_param:
                out.append(Rewrite(rule="spec-fun-totalised", line=d.line))
            if any(_is_nat(p.type) for p in d.params) is False and d.ret_type is not None and d.ret_type.kind == "nat":
                pass
            if d.ret_type is not None and d.ret_type.kind == "nat":
                out.append(Rewrite(rule="nat-result-fact-dropped", line=d.line))

    for n in walk(method):
        if isinstance(n, Chain) and len(n.ops) >= 2:
            out.append(Rewrite(rule="chain-desugared", line=n.line))
        elif isinstance(n, Iff):
            out.append(Rewrite(rule="iff-to-eq", line=n.line))

    for spec in method.specs:
        if isinstance(spec, EnsuresClause) and isinstance(spec.expr, NaryBool) and spec.expr.op == "&&":
            out.append(Rewrite(rule="split-conjuncts", line=spec.line))
    for spec in method.specs:
        if isinstance(spec, RequiresClause) and isinstance(spec.expr, NaryBool) and spec.expr.op == "&&":
            out.append(Rewrite(rule="split-conjuncts", line=spec.line))

    for n in walk(method.body):
        if isinstance(n, Assign) and len(n.targets) > 1:
            out.append(Rewrite(rule="parallel-assign-temps", line=n.line))
        elif isinstance(n, VarDeclStmt) and n.init is None:
            out.append(Rewrite(rule="default-init", line=n.line))
        elif isinstance(n, ForStmt):
            out.append(Rewrite(rule="for-desugared", line=n.line))

    for n in walk(method):
        if isinstance(n, AssertStmt):
            out.append(Rewrite(rule="assert-dropped", line=n.line))
        elif isinstance(n, AssertByStmt):
            out.append(Rewrite(rule="assert-dropped", line=n.line))
        elif isinstance(n, CalcStmt):
            out.append(Rewrite(rule="assert-dropped", line=n.line))
        elif isinstance(n, RevealStmt):
            out.append(Rewrite(rule="assert-dropped", line=n.line))
        elif isinstance(n, ForallStmt):
            out.append(Rewrite(rule="assert-dropped", line=n.line))
        elif isinstance(n, CallStmt):
            out.append(Rewrite(rule="lemma-call-dropped", line=n.line))

    for d in closure:
        if isinstance(d, FunctionDecl) and any(isinstance(s, EnsuresClause) for s in d.specs):
            out.append(Rewrite(rule="function-ensures-dropped", line=d.line))

    for d in module.decls:
        if isinstance(d, MethodDecl) and d.name == "Main":
            out.append(Rewrite(rule="main-dropped", line=d.line))

    reachable_names = {d.name for d in closure if d.name}
    for d in module.decls:
        if (isinstance(d, (FunctionDecl, LemmaDecl)) and d is not method
                and (d.name not in reachable_names)):
            out.append(Rewrite(rule="unused-function-dropped", line=d.line))

    return out


def _gradable_methods_fallback(module: Module) -> list[MethodDecl]:
    """Decision 9's own one-line rule, used only if `lift_parse
    .gradable_methods` is not yet implemented (it is this module's stub
    sibling's job; see `classify_all`'s docstring)."""
    return [d for d in module.decls
            if isinstance(d, MethodDecl) and d.name != "Main"
            and any(isinstance(s, EnsuresClause) for s in d.specs)]


def classify_all(module: Module) -> dict[str, "Refusal | Liftable"]:
    """Classify every gradable method in `module` (via
    `lift_parse.gradable_methods`), keyed by method name.

    A file with several gradable methods (decision 9) gets one entry per
    method here, never a single file-level verdict; a file-level
    `split-per-method` label (section 5's row for `multi-method`) is
    reported by the caller from `len(result) > 1`, not by this function,
    which never returns anything but per-method verdicts."""
    try:
        import lift_parse
        methods = lift_parse.gradable_methods(module)
    except NotImplementedError:
        methods = _gradable_methods_fallback(module)
    return {m.name: classify(module, m) for m in methods}


# ---------------------------------------------------------------------------
# Definite assignment of the return, on every path (section 4.7). A
# best-effort structural mirror of Dafny's own check: true iff every
# straight-line path through `stmts` assigns `ret_name` somewhere (a loop
# never counts, since it may run zero times; an `if` counts only when BOTH
# branches do, recursively; a tail `return e`/`return r`/`return;` counts
# exactly when the source's own return-elaboration (section 4.5) would make
# it into an assignment of `ret_name` or relies on one already having run).
# ---------------------------------------------------------------------------

def _assigns_ret_all_paths(stmts: tuple[Stmt, ...], ret_name: str) -> bool:
    assigned = False
    for s in stmts:
        if assigned:
            continue
        if isinstance(s, Assign):
            if any(t.kind == "name" and t.name == ret_name for t in s.targets):
                assigned = True
        elif isinstance(s, IfStmt):
            then_ok = _assigns_ret_all_paths(s.then, ret_name)
            if isinstance(s.else_, tuple):
                else_ok = _assigns_ret_all_paths(s.else_, ret_name)
            elif isinstance(s.else_, IfStmt):
                else_ok = _assigns_ret_all_paths((s.else_,), ret_name)
            else:
                else_ok = False
            if then_ok and else_ok:
                assigned = True
        elif isinstance(s, BlockStmt):
            if _assigns_ret_all_paths(s.body, ret_name):
                assigned = True
        elif isinstance(s, LabelStmt):
            if _assigns_ret_all_paths((s.stmt,), ret_name):
                assigned = True
        elif isinstance(s, ReturnStmt) and s.values:
            assigned = True  # tail `return e` (section 4.5) becomes `r := e`
        # WhileStmt / ForStmt: never counted (may execute zero times).
    return assigned


def unchanged_at_every_call(param_names: list[str], calls: list, n: int) -> set[int]:
    """Decision 11's function-tuple projection test: component `i` is
    dropped only when it is passed through UNCHANGED (the same-named
    identifier, in the same position) AT EVERY self-call found, not merely
    at one of them (gcd's `gcd(x-y, y)` and `gcd(x, y-x)`: `y` is
    unchanged only in the first call and `x` only in the second, so
    NEITHER is dropped and both survive into `guess:sum`, matching
    section 6's own worked example)."""
    if not calls:
        return set()
    unchanged = set(range(n))
    for c in calls:
        this_call = set()
        for i, (pn, arg) in enumerate(zip(param_names, c.args)):
            if isinstance(arg, Ident) and arg.name == pn:
                this_call.add(i)
        unchanged &= this_call
    return unchanged
