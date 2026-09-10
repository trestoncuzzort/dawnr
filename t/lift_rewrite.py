"""Execute a `lift_classify.Liftable` plan: produce the t task JSON and the
provenance that says exactly how it was built.

Reads LIFTER-DESIGN.md sections 4 (mapping rules -- the ONLY rewrites this
module may perform), 5 (refusal rules -- `lift-check-failed`-adjacent
edge cases aside, a method classify already cleared should not refuse
here; if the AST cannot actually be rewritten as planned that is a
`lift_classify.py` bug, reported as `check-wf-failed` once
`fuzz_lower.check_wf` sees the result, never patched over here), 6
(decreases inference -- how the actual measure expression is built for
`decreases_origin`'s "stated" / "rprint-inferred" / "projected" /
"guess:sum" labels), 7 (nat handling -- the actual clause text for
`nat-return-ensures` / `nat-invariant-added` / `nat-param-guard` /
`spec-fun-totalised`), 18.2 (the rewrite-vocabulary cross-reference: the
exact rule-name strings to log), 18.6 (the read-only-array-as-seq rewrite
in full), and LIFTER-DECISIONS.md whole. Also reads SYNTAX.md's reserved
words (`surface.py` KEYWORDS, a lowering's RESERVED set) for the naming
rule (section 4.8: renaming a keyword-colliding or shadowed identifier,
e.g. `f` -> `f_v`, `gcd'` -> `gcd_p`).

This module shares its detectors with `lift_classify.py` (its sibling,
same implementer; see that module's docstring for the shared-helpers
list and the two documented shim limitations -- the section 4.8 rename
check's keyword set, and the `decreases_origin` "stated" vs.
"rprint-inferred" heuristic -- both apply here unchanged).

Architecture role (LIFTER-DESIGN.md section 2's table, copied verbatim):
    input: liftable method AST plus the call-graph closure
    output: the t task JSON, the rename map, the rewrite log, the
            added-clause log
    MAY decide: only the rewrites in section 4, deterministically
    MAY NOT decide: to add, drop or reorder any source clause except by a
                    rule in section 4

The task dict this module produces has exactly the shape of `t/tasks
/*.json` (SPEC.md / SYNTAX.md's grammar: `t`, `name`, `params`, `returns`,
`requires`, `ensures`, and v1's optional `gate`, `spec_funs`, `decreases`),
so it can be written straight to a `.json` file and passed unchanged to
`fuzz_lower.check_wf`, `interp.Reference`/`interp.domain`,
`harness.twin_for`, and `lower_dafny.lower`.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lift_ast import (
    Assign, Binary, BlockStmt, BoolLit, BreakStmt, Call, Cast, Chain,
    CharLit, ClauseAdded, ClauseDropped, ContinueStmt, Decl, DecreasesClause,
    EnsuresClause, Expr, ForStmt, Fresh, FunctionDecl, Ident, IfExpr, IfStmt,
    Iff, Implies, Index, IntLit, InvariantClause, LabelStmt, LemmaDecl,
    LiftRecord, Lhs, MethodDecl, Module, NaryBool, NewRhs, Old, Param,
    Quantifier, ReadsClause, Rename, RequiresClause, ReturnStmt, Rewrite,
    SeqDisplay, Slice, Stmt, StringLit, Type, Unary, VarDeclStmt, WhileStmt,
)
from lift_classify import (
    ArrayMutation, Liftable, T_KEYWORDS, RESERVED_EXTRA, bound_quantifier,
    decode_char_literal, decode_string_literal, expr_kind, find_array_mutation,
    scan_breaks, scan_null_checks, walk, unchanged_at_every_call, _is_seq_of_char,
)


# ---------------------------------------------------------------------------
# Section 4.8's naming: deterministic rename rule + task-name construction.
# ---------------------------------------------------------------------------

class _Renamer:
    """One rename authority per lift, shared by every scope in the task
    (task params/return/locals, every spec_fun's own name and params).
    Deliberately GLOBAL rather than per-scope: section 4.8's own example
    (`f` -> `f_v` because spark's `F` catches it) is about a
    case-insensitive, whole-FILE collision a backend can make, so this
    lifter never risks two distinct declarations in one task sharing a
    name after folding, even across two textually unrelated scopes."""

    def __init__(self) -> None:
        self._used_lower: set[str] = {k.lower() for k in (T_KEYWORDS | RESERVED_EXTRA)}

    def fresh(self, dafny_name: str, record: LiftRecord, why: str) -> str:
        name = dafny_name.replace("'", "_p")
        reason = None
        if name != dafny_name:
            reason = "apostrophe"
        if name and name[0].isupper():
            name = name[0].lower() + name[1:]
            reason = reason or "uppercase-initial"
        if not name or not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", name):
            name = "v" if not name else re.sub(r"[^A-Za-z0-9_]", "_", name)
            if not name[0].isalpha():
                name = "v_" + name
            reason = reason or "name-unsanitisable"
        base = name
        suffix = 0
        while name.lower() in self._used_lower:
            suffix += 1
            name = f"{base}_v{suffix if suffix > 1 else ''}"
            reason = reason or "collision"
        self._used_lower.add(name.lower())
        if reason is not None:
            key = dafny_name if dafny_name not in record.rename_map else f"{dafny_name}#{why}"
            record.rename_map[key] = Rename(t_name=name, reason=reason)
        return name


def _sanitize_stem(source_path: str) -> str:
    stem = Path(source_path).stem
    return re.sub(r"[^A-Za-z0-9_]", "_", stem).lower()


# ---------------------------------------------------------------------------
# Types, small expression builders.
# ---------------------------------------------------------------------------

def _t_type_of(t: Optional[Type]) -> str:
    if t is None:
        return "int"
    if t.kind == "bool":
        return "bool"
    if t.kind in ("seq", "array", "string"):
        # Row 28 (2026-09-09, SPEC.md "Strings as sequences of code
        # points (v1)"): `string` is the same t `seq` a Dafny
        # `seq<int>`/`array<int>` already lifts to.
        return "seq"
    return "int"  # int, nat, char (row 28: char is its own code point)


def _rw_seq_kind(e: Expr, scope: "Scope") -> Optional[str]:
    """Rows 25-27's `expr_kind` (`lift_classify.py`), reusing the live
    `Scope` this module already threads through the lift as the lookup:
    an `Ident`'s t-name, then that t-name's own `scope.types` entry
    (`scope.renames`/`scope.types` are the definitive, already-resolved
    answer by the time `_lift_expr` runs -- a function's own return kind
    is NOT resolved here, unlike `classify`'s `_build_kind_env`, since a
    `+` over a spec_fun call reaching this point was already accepted by
    `classify`; the only thing this module still needs to decide is
    whether to record `seq-concat-lifted`, never whether to accept). Used
    only for that bookkeeping, never to accept or refuse anything."""
    def lookup(name: str) -> Optional[str]:
        tname = scope.renames.get(name)
        return scope.types.get(tname) if tname is not None else None
    return expr_kind(e, lookup)


def _ge0(t_name: str) -> dict:
    return {"op": ">=", "args": [{"var": t_name}, {"int": 0}]}


def _ge0_of(e: dict) -> dict:
    """`_ge0`'s own inequality, over an arbitrary already-lifted
    expression rather than a bare variable name -- row 29 needs it for a
    `nat` pair COMPONENT, whose non-negativity ensures is stated on the
    projection (`r.0 >= 0`), never on the pair return itself (SPEC.md:
    "a pair has no order", so `r >= 0` is not even well-typed)."""
    return {"op": ">=", "args": [e, {"int": 0}]}


_CHAR_MAX = 1114111  # SPEC.md "an int in [0, 1114111]"; see lift_classify's
                      # own `_CHAR_MAX` comment for the measurement behind it


def _char_range(t_name: str) -> dict:
    """Row 28's own analogue of `_ge0`, for a char param/return: t's
    plain int has no notion of a char's own valid domain (SPEC.md: "No
    overflow semantics (mathematical integers)"), so a char parameter
    is restated as a `requires 0 <= v <= 1114111` exactly the way decision
    4/decision 6's `nat-param-guard` restates a nat parameter's own `>=
    0`, and a char return the matching `ensures` -- otherwise the
    lifted task's interp domain samples arbitrary ints where the source
    could only ever have been called with a valid char, a real
    widening of the theorem, and (measured directly, `trun.dfy` in the
    task's own scratch notes) the differential harness's own `n as char`
    conversion of an out-of-range point CRASHES the whole `dafny run`
    process rather than merely mis-comparing."""
    return {"op": "and", "args": [_ge0(t_name),
                                   {"op": "<=", "args": [{"var": t_name}, {"int": _CHAR_MAX}]}]}


def _and(parts: list) -> dict:
    if len(parts) == 1:
        return parts[0]
    return {"op": "and", "args": parts}


def _split_top_and(e: dict) -> list:
    if isinstance(e, dict) and e.get("op") == "and":
        return list(e["args"])
    return [e]


def _already_present(clause: dict, existing: list) -> bool:
    for e in existing:
        if e == clause:
            return True
        if isinstance(e, dict) and e.get("op") == "and" and clause in e.get("args", []):
            return True
    return False


def _strip_fresh_conjuncts(e: Expr, ret_name: Optional[str],
                            record: LiftRecord, line: int) -> Optional[Expr]:
    """Decision 22: `fresh(b)` on the returned array is DROPPED, not
    lifted (SPEC.md: "`fresh(b)` on a returned array is dropped''), `b`
    being the source's own return -- `ret_name`, `None` unless this is
    the "alloc-fill" shape. Only a TOP-LEVEL `&&` conjunct (`ensures
    fresh(b) && b.Length == n && ...`) is stripped HERE; `Fresh`
    anywhere else still reaches `_lift_expr`'s own fallback (`true`,
    never a crash). Returns `None` when the whole clause was `fresh(b)`
    alone (the caller drops the clause entirely)."""
    if ret_name is None:
        return e
    if isinstance(e, Fresh) and isinstance(e.arg, Ident) and e.arg.name == ret_name:
        record.rewrites.append(Rewrite(rule="fresh-dropped", line=line))
        return None
    if isinstance(e, NaryBool) and e.op == "&&":
        kept = [a for a in e.args
                if not (isinstance(a, Fresh) and isinstance(a.arg, Ident) and a.arg.name == ret_name)]
        if len(kept) == len(e.args):
            return e
        record.rewrites.append(Rewrite(rule="fresh-dropped", line=line))
        if not kept:
            return None
        if len(kept) == 1:
            return kept[0]
        return NaryBool(e.line, "&&", tuple(kept))
    return e


def _strip_null_checks(e: Expr, drop_ids: frozenset,
                        record: LiftRecord, line: int) -> Optional[Expr]:
    """Row 24 (2026-09-09): the same `!= null` comparisons
    `lift_classify.scan_null_checks` accepted for this method (each
    one's `null` Ident's `id()` is in `drop_ids`, computed once in
    `rewrite()` -- the SAME shared computation `classify` used to
    exempt them from the `heap` refusal, per `scan_breaks`'s pattern of
    never letting the two stages disagree) are DROPPED here rather than
    lifted: a `requires`/`ensures`/loop `invariant` clause that IS the
    comparison vanishes entirely; a TOP-LEVEL `&&` conjunct is removed
    from the conjunction, exactly `_strip_fresh_conjuncts`'s reading of
    "top level". The same comparison anywhere else (inside an `||`, an
    `==>`, or a body expression) was never placed in `drop_ids` to begin
    with -- `scan_null_checks` only ever matches a clause's own top
    level -- so it is untouched here and would reach `_lift_expr`'s own
    fallback; in practice this never happens, since `classify` refuses
    `heap` for that shape before `rewrite` is ever called. Returns
    `None` when the whole clause was the comparison alone (the caller
    drops the clause entirely, exactly `_strip_fresh_conjuncts`'s
    contract)."""
    if not drop_ids:
        return e

    def _is_dropped(a: Expr) -> bool:
        # A single relop always parses as a length-1 `Chain`, never a
        # `Binary` (`Binary` is `+ - * / %` only; see `_null_compare`'s
        # docstring in lift_classify.py).
        return (isinstance(a, Chain) and len(a.ops) == 1 and a.ops[0] == "!="
                and (id(a.operands[0]) in drop_ids or id(a.operands[1]) in drop_ids))

    if _is_dropped(e):
        record.clauses_dropped.append(ClauseDropped(rule="null-check-dropped", count=1))
        record.rewrites.append(Rewrite(rule="null-check-dropped", line=line))
        return None
    if isinstance(e, NaryBool) and e.op == "&&":
        kept = [a for a in e.args if not _is_dropped(a)]
        dropped_n = len(e.args) - len(kept)
        if dropped_n == 0:
            return e
        for _ in range(dropped_n):
            record.clauses_dropped.append(ClauseDropped(rule="null-check-dropped", count=1))
            record.rewrites.append(Rewrite(rule="null-check-dropped", line=line))
        if not kept:
            return None
        if len(kept) == 1:
            return kept[0]
        return NaryBool(e.line, "&&", tuple(kept))
    return e


# ---------------------------------------------------------------------------
# Scope: the live rename/type/nat-tracking environment threaded through the
# body lift. Copied (not shared) whenever two branches must not leak
# locals into each other (an `if`'s two arms, a loop's body).
# ---------------------------------------------------------------------------

@dataclass
class Scope:
    renames: dict = field(default_factory=dict)   # dafny name -> t name
    types: dict = field(default_factory=dict)      # t name -> "int"|"bool"|"seq"
    nat: list = field(default_factory=list)        # dafny names known nat-typed here
    ret_name: str = ""                             # dafny name of the task's return
    # Decision 22 (SPEC.md "Sequences as values (v1)"): a `modifies`-param
    # array mutation's two names for one Dafny identifier. `renames` maps
    # the array's dafny name to the RETURN's t-name everywhere by default
    # (a `modifies`-param body is primed `<ret> := a;`, so an unguarded
    # `a[k]` after that point IS the return's current value); `old(a[k])`/
    # `old(a[..])` need the PARAMETER's own (pre-mutation) t-name instead,
    # which is not recoverable from `renames` once the default above has
    # overwritten it -- these two fields carry it alongside.
    old_array_name: Optional[str] = None           # dafny name of the mutated array, or None
    old_array_param_tname: Optional[str] = None     # its own t-name (pre-mutation)
    # Row 24 (2026-09-09): `id()`s of the `null` Ident nodes
    # `lift_classify.scan_null_checks` accepted for THIS method (a
    # `!= null` on a non-nullable array param/return, in a whole-clause
    # or top-level `&&`-conjunct position) -- carried on `Scope` (rather
    # than threaded as its own parameter through every `_lift_stmt`
    # call) since a loop's `InvariantClause` is only reachable from
    # there and `Scope` already flows to every clause-lifting site via
    # `.copy()`. Set once in `rewrite()`; never mutated afterward.
    null_drop_ids: frozenset = frozenset()
    # Row 29 (2026-09-09, SPEC.md "Pairs (v1)"): a `multi-return`
    # method's two out-parameter names each read a DIFFERENT way in
    # different positions -- `r.0`/`r.1` in requires/ensures (a
    # postcondition names the FINAL value, which is exactly what the
    # pair return holds by construction at every exit), but the plain
    # LOCAL `a`/`b` everywhere in the body proper, loop invariants
    # included (an invariant reads the CURRENT, mid-loop value, which
    # `r` is not kept in sync with until the method actually exits --
    # `min_max.json`'s own hand-written invariants read `lo`/`hi`
    # directly, never `r.0`/`r.1`, the same reading this row follows).
    # `pair_view` (dafny out-param name -> (pair t-name, "fst"|"snd"))
    # is consulted by `_lift_expr`'s `Ident` case BEFORE `renames`, and
    # is populated only on the `Scope` used to lift `requires`/`ensures`
    # -- `rewrite()` clears it to `{}` on `body_scope` and points
    # `renames` at the two locals instead, so it can never fire past
    # that point even though `.copy()` (loop nesting) carries the
    # (now-empty) dict forward like any other field. `pair_ret` (t-name
    # of the pair return, dafny name of each out-parameter) is the
    # opposite direction: `_lift_stmt`'s own `ReturnStmt` case reads it
    # to build an early exit's `{"return": ["r", {"op": "pair", ...}]}`,
    # so it is set ONLY on `body_scope`, never on the outer `scope`.
    pair_view: dict = field(default_factory=dict)
    pair_ret: Optional[tuple] = None                # (pair t-name, dafny a-name, dafny b-name)

    def copy(self) -> "Scope":
        return Scope(dict(self.renames), dict(self.types), list(self.nat), self.ret_name,
                     self.old_array_name, self.old_array_param_tname, self.null_drop_ids,
                     dict(self.pair_view), self.pair_ret)


# ---------------------------------------------------------------------------
# Decision 22's `new int[n]` / `new nat[n]` size expression. `lift_ast`'s
# `NewRhs` keeps its source text verbatim, unparsed (it used to be always
# a refusal, so nothing past the refusal read it -- see the node's own
# docstring); this row needs the size EXPRESSION, not the text, to build
# `{"op": "fill", "args": [size, {"int": 0}]}`. Reusing `lift_parse`'s own
# tokenizer/parser on a tiny wrapper method is simpler and more robust
# than a second hand-rolled expression parser here: `lift_parse.parse` is
# the ONE place Dafny expression grammar is implemented, and the size
# text (`a.Length`, `n`, `a.Length / 2`, `s.Length - 1`, ...) is always a
# self-contained expression, never a statement.
# ---------------------------------------------------------------------------

def _parse_size_expr(size_text: str) -> Expr:
    import lift_parse
    src = f"method __t_decision22_snippet() returns (__r: int) {{ __r := {size_text}; }}"
    module = lift_parse.parse(src)
    for d in module.decls:
        if isinstance(d, MethodDecl) and d.body:
            s = d.body[0]
            if isinstance(s, Assign) and s.values:
                v = s.values[0]
                if isinstance(v, Expr):
                    return v
    raise ValueError(f"lift_rewrite: could not re-parse array-size expression {size_text!r} "
                      "(a lift_classify bug: this should have been validated before rewrite ran)")


def _lift_new_array(rhs: NewRhs, scope: Scope, fn_names: dict, self_name: str,
                     task_name: str, record: LiftRecord, renamer: "_Renamer") -> dict:
    """`new int[n]` / `new nat[n]` -> `{"op": "fill", "args": [n, 0]}`
    (SPEC.md "Sequences as values (v1)"; decision 22). Only ever called
    where `lift_classify.find_array_mutation` has already confirmed
    `rhs.text` matches this shape -- a mismatch here is a lift_classify
    bug, not a fresh refusal to invent this late."""
    from lift_classify import _new_array_size_text
    parsed = _new_array_size_text(rhs)
    if parsed is None:
        raise ValueError(f"lift_rewrite: {rhs.text!r} is not a decision-22 array allocation "
                          "(a lift_classify bug: this should have been refused before rewrite ran)")
    _elem_kind, size_text = parsed
    size_expr = _parse_size_expr(size_text)
    size_lifted = _lift_expr(size_expr, scope, fn_names, self_name, task_name, record, renamer)
    record.rewrites.append(Rewrite(rule="array-new-as-fill", line=rhs.line))
    return {"op": "fill", "args": [size_lifted, {"int": 0}]}


def _add_array_length_invariants(body_out: list, mutated_tname: str, len_expr: dict,
                                  record: LiftRecord) -> None:
    """Decision 22: unlike a real Dafny array (`.Length` fixed by
    construction, so the SOURCE never has to state it as a loop
    invariant), a `seq` variable's length is not automatically known
    preserved across a `while` loop -- Dafny needs to be TOLD, or the
    lowered task's own `ensures |ret| == ...` fails to verify even
    though `update`/`fill` both provably preserve/define length (Clover
    _array_product measured: without this, `ensures |c| == |a|` on the
    LOWERED method itself does not verify). So every loop that assigns
    `mutated_tname` gets `len(mutated_tname) == len_expr` appended to its
    own invariant list, after the source's own invariants, unless
    already present -- `len_expr` is `len(<the array's own PARAMETER>)`
    for the "modifies-param" shape (unchanging by construction: nothing
    resizes an array in place) or the lifted allocation-size expression
    itself for "alloc-fill" (the value `fill(n, 0)` was given at the one
    point it was created, before any loop could touch it)."""
    fact = {"op": "==", "args": [{"op": "len", "args": [{"var": mutated_tname}]}, len_expr]}

    def touches(node) -> bool:
        if isinstance(node, dict):
            if "assign" in node and node["assign"][0] == mutated_tname:
                return True
            return any(touches(v) for v in node.values())
        if isinstance(node, list):
            return any(touches(v) for v in node)
        return False

    def walk_stmts(stmts: list) -> None:
        for s in stmts:
            if not isinstance(s, dict):
                continue
            if "while" in s:
                w = s["while"]
                if touches(w["body"]) and fact not in w["invariants"]:
                    # PREPENDED, unlike decision 5's `nat-invariant-added`
                    # (which appends, deliberately, to keep the twin
                    # ladder's INVARIANT-DROP site indices stable against
                    # the AUTHOR's own invariants): here an author
                    # invariant that reads the mutated seq bounded by
                    # `len(<other side>)` needs THIS fact to be WELL
                    # -DEFINED at all (SPEC.md: "each loop invariant may
                    # assume earlier invariants in its list", so a fact
                    # coming after cannot rescue one that reads out of
                    # bounds before it) -- measured, Clover_double_array
                    # _elements: appended, the lowered task's own
                    # invariant list fails to verify ("index out of
                    # range"); prepended, it verifies. This shifts every
                    # author invariant's index by one on a decision-22
                    # task, a cost row 22 accepts explicitly (a synthetic
                    # invariant with no source line of its own to begin
                    # with, so there is no author site to misattribute).
                    w["invariants"].insert(0, fact)
                    record.rewrites.append(Rewrite(rule="array-length-invariant-added", line=0))
                walk_stmts(w["body"])
            elif "if" in s:
                walk_stmts(s["if"]["then"])
                walk_stmts(s["if"].get("else", []))
    walk_stmts(body_out)


# ---------------------------------------------------------------------------
# Expression lifting (section 4.3/4.4's tables). `fn_names` maps a closure
# function's dafny name to its t name; `self_name`/`task_name` let a
# self-call lift to `{"call": {"fun": task_name, ...}}` (SPEC.md gate 3:
# `fun` is the task's OWN name for direct self-recursion).
# ---------------------------------------------------------------------------

def _lift_expr(e, scope: Scope, fn_names: dict, self_name: str,
               task_name: str, record: LiftRecord, renamer: "_Renamer") -> dict:
    if isinstance(e, _AtHole):
        return {"op": "at", "args": [e.seq_expr_json, {"var": e.binder}]}
    if isinstance(e, IntLit):
        return {"int": e.value}
    if isinstance(e, BoolLit):
        return {"bool": e.value}
    if isinstance(e, CharLit):
        # Row 28 (2026-09-09, SPEC.md "Strings as sequences of code
        # points (v1)"): a char literal is its own code point, as a t
        # int; `lift_classify.decode_char_literal` already confirmed
        # this decodes (a lift_classify bug otherwise, same contract as
        # every other node here).
        cp = decode_char_literal(e.text)
        record.rewrites.append(Rewrite(rule="char-literal-lifted", line=e.line))
        return {"int": cp}
    if isinstance(e, StringLit):
        # Row 28: a string literal is t's seq literal of code points,
        # `""` the empty one (SPEC.md's own notation table).
        cps = decode_string_literal(e.text)
        record.rewrites.append(Rewrite(rule="string-literal-lifted", line=e.line))
        return {"op": "seq", "args": [{"int": cp} for cp in cps]}
    if isinstance(e, Ident):
        pv = scope.pair_view.get(e.name)
        if pv is not None:
            # Row 29: a requires/ensures (or a loop invariant reading an
            # out-parameter through THIS scope, which never happens --
            # `pair_view` is cleared on `body_scope`, see that field's
            # own docstring) reference to `a`/`b` becomes `r.0`/`r.1`.
            ret_t, proj = pv
            record.rewrites.append(Rewrite(rule="multi-return-pair-projected", line=e.line))
            return {"op": proj, "args": [{"var": ret_t}]}
        return {"var": scope.renames.get(e.name, e.name)}
    if isinstance(e, Unary):
        inner = _lift_expr(e.arg, scope, fn_names, self_name, task_name, record, renamer)
        return {"op": ("not" if e.op == "!" else "neg"), "args": [inner]}
    if isinstance(e, Binary):
        left = _lift_expr(e.left, scope, fn_names, self_name, task_name, record, renamer)
        right = _lift_expr(e.right, scope, fn_names, self_name, task_name, record, renamer)
        # `/` -> "div", `%` -> "mod" (SPEC.md "Division and modulo (v1)"):
        # Dafny's own `/` and `%` on int are Euclidean, measured on dafny
        # 4.11.0, matching t's div/mod one to one, so no domain narrowing
        # or totalising wrapper is needed here, only the name change.
        op = {"/": "div", "%": "mod"}.get(e.op, e.op)
        if e.op == "+" and _rw_seq_kind(e, scope) == "seq":
            # Row 26 (2026-09-09): t's own `+` is polymorphic by operand
            # type exactly as `==` already is (SPEC.md "Sequences:
            # literals, concatenation, slices (v1)"), so the JSON shape
            # above needs no change at all for a seq concatenation --
            # this only records the provenance `classify` already
            # confirmed (both operands seq-typed).
            record.rewrites.append(Rewrite(rule="seq-concat-lifted", line=e.line))
        return {"op": op, "args": [left, right]}
    if isinstance(e, NaryBool):
        args = [_lift_expr(a, scope, fn_names, self_name, task_name, record, renamer) for a in e.args]
        return {"op": ("and" if e.op == "&&" else "or"), "args": args}
    if isinstance(e, Implies):
        left = _lift_expr(e.left, scope, fn_names, self_name, task_name, record, renamer)
        right = _lift_expr(e.right, scope, fn_names, self_name, task_name, record, renamer)
        return {"op": "implies", "args": [left, right]}
    if isinstance(e, Iff):
        record.rewrites.append(Rewrite(rule="iff-to-eq", line=e.line))
        left = _lift_expr(e.left, scope, fn_names, self_name, task_name, record, renamer)
        right = _lift_expr(e.right, scope, fn_names, self_name, task_name, record, renamer)
        return {"op": "==", "args": [left, right]}
    if isinstance(e, Chain):
        return _lift_chain(e, scope, fn_names, self_name, task_name, record, renamer)
    if isinstance(e, IfExpr):
        return {"ite": {
            "cond": _lift_expr(e.cond, scope, fn_names, self_name, task_name, record, renamer),
            "then": _lift_expr(e.then, scope, fn_names, self_name, task_name, record, renamer),
            "else": _lift_expr(e.else_, scope, fn_names, self_name, task_name, record, renamer)}}
    if isinstance(e, Quantifier):
        return _lift_quantifier(e, scope, fn_names, self_name, task_name, record, renamer)
    if e.__class__.__name__ == "Cardinality":
        return {"op": "len", "args": [_lift_expr(e.arg, scope, fn_names, self_name, task_name, record, renamer)]}
    if e.__class__.__name__ == "Member":  # `.Length`, only reachable form (classify refused others)
        return {"op": "len", "args": [_lift_expr(e.base, scope, fn_names, self_name, task_name, record, renamer)]}
    if e.__class__.__name__ == "Index":
        return {"op": "at", "args": [
            _lift_expr(e.base, scope, fn_names, self_name, task_name, record, renamer),
            _lift_expr(e.index, scope, fn_names, self_name, task_name, record, renamer)]}
    if isinstance(e, Call):
        fn = e.fn.name if isinstance(e.fn, Ident) else "?"
        target = task_name if fn == self_name else fn_names.get(fn, fn)
        args = [_lift_expr(a, scope, fn_names, self_name, task_name, record, renamer) for a in e.args]
        return {"call": {"fun": target, "args": args}}
    if isinstance(e, Old):
        # Decision 22: `old(a[k])` and `old(a[..])` on the ONE
        # `modifies`-param mutated array read as the PARAMETER's own
        # (pre-mutation) value -- `scope.old_array_param_tname`, set up
        # once in `rewrite()`, not the ambient `scope.renames` entry for
        # `a` (which the body's priming `<ret> := a;` has made mean the
        # RETURN by the time any of this runs). Anything else under
        # `old(...)` is a lift_classify bug: no other shape is accepted.
        inner = e.arg
        if (scope.old_array_name is not None and isinstance(inner, Index)
                and isinstance(inner.base, Ident) and inner.base.name == scope.old_array_name):
            idx = _lift_expr(inner.index, scope, fn_names, self_name, task_name, record, renamer)
            record.rewrites.append(Rewrite(rule="old-array-elem-as-param", line=e.line))
            return {"op": "at", "args": [{"var": scope.old_array_param_tname}, idx]}
        if (scope.old_array_name is not None and isinstance(inner, Slice)
                and isinstance(inner.base, Ident) and inner.base.name == scope.old_array_name
                and inner.lo is None and inner.hi is None):
            record.rewrites.append(Rewrite(rule="old-array-whole-as-param", line=e.line))
            return {"var": scope.old_array_param_tname}
        raise ValueError(f"lift_rewrite: unsupported old(...) shape {inner!r} (a lift_classify "
                          f"bug: this should have been refused before rewrite ran)")
    if isinstance(e, Slice):
        # `a[..]` with NO `old` wrapper and NEITHER bound given -- the
        # whole-seq view, identity on a value seq (decision 22's own
        # reading, now also reachable for any other seq-typed receiver:
        # SPEC.md "a[..] on an array parameter ... is the parameter
        # itself" applies just as well to a read-only array or a plain
        # seq local/param/return, not only the row-22 mutated array) --
        # reads as whatever the base's ambient t-name currently is.
        if e.lo is None and e.hi is None:
            record.rewrites.append(Rewrite(rule="whole-slice-as-seq", line=e.line))
            return _lift_expr(e.base, scope, fn_names, self_name, task_name, record, renamer)
        # Row 27 (2026-09-09): a BOUNDED slice, or one of its two sugars
        # (`s[a..]` for `s[a..len(s)]`, `s[..b]` for `s[0..b]`) -- SPEC.md
        # "Sequences: literals, concatenation, slices (v1)" states the
        # AST always carries the three-argument form, the sugar expanded
        # here. `classify` has already confirmed the receiver is
        # seq-typed and, when it is decision 22's own mutated array, that
        # this slice is its accepted UNBOUNDED one (handled above) --
        # any bounded slice reaching here is never that array (row 22's
        # own refusal stands for a bounded slice of it).
        base_e = _lift_expr(e.base, scope, fn_names, self_name, task_name, record, renamer)
        lo_e = ({"int": 0} if e.lo is None
                else _lift_expr(e.lo, scope, fn_names, self_name, task_name, record, renamer))
        hi_e = ({"op": "len", "args": [base_e]} if e.hi is None
                else _lift_expr(e.hi, scope, fn_names, self_name, task_name, record, renamer))
        record.rewrites.append(Rewrite(rule="seq-slice-lifted", line=e.line))
        return {"op": "slice", "args": [base_e, lo_e, hi_e]}
    if isinstance(e, SeqDisplay):
        # Row 25 (2026-09-09): `[e1, ..., en]` (or `[]`, elems empty) is
        # t's literal one to one; `classify` has already confirmed every
        # element is int-typed (`_seq_literal_issue`).
        elems = [_lift_expr(el, scope, fn_names, self_name, task_name, record, renamer)
                 for el in e.elems]
        record.rewrites.append(Rewrite(rule="seq-literal-lifted", line=e.line))
        return {"op": "seq", "args": elems}
    if isinstance(e, Cast):
        # Row 28: `classify` has already confirmed this is one of the
        # two safe shapes (`char as int`, always; `int as char`, only
        # when the operand is visibly a code point already) -- both
        # directions are the plain identity on the lifted side, since a
        # char and its code point are ONE t int (SPEC.md: "the char
        # already is its code point"). Any other cast is a
        # lift_classify bug (should have refused `as-cast` already).
        if e.type.kind in ("int", "char"):
            record.rewrites.append(Rewrite(
                rule="char-as-int-lifted" if e.type.kind == "int" else "int-as-char-lifted",
                line=e.line))
            return _lift_expr(e.base, scope, fn_names, self_name, task_name, record, renamer)
        raise ValueError(f"lift_rewrite: unsupported cast {e!r} (a lift_classify "
                          f"bug: this should have been refused before rewrite ran)")
    if isinstance(e, Fresh):
        # Decision 22: `fresh(b)` on the returned array is dropped, not
        # lifted -- the common case (a TOP-LEVEL ensures conjunct) is
        # stripped before this is ever reached (`_strip_fresh_conjuncts`
        # in `rewrite()`); this is the fallback for the rare shape that
        # is not top-level, so lifting never crashes on it. `true` is a
        # sound (if unminimal) stand-in: fresh(b) is a definite-assignment
        # fact about the source's OWN semantics, never a value fact any
        # twin could exploit.
        record.rewrites.append(Rewrite(rule="fresh-dropped", line=e.line))
        return {"bool": True}
    raise ValueError(f"lift_rewrite: no expression mapping for {e!r} (a lift_classify bug: "
                      f"this construct should have been refused before rewrite ran)")


def _lift_chain(e: Chain, scope: Scope, fn_names: dict, self_name: str,
                 task_name: str, record: LiftRecord, renamer: "_Renamer") -> dict:
    if len(e.ops) == 1 and e.ops[0] not in ("in", "!in"):
        left = _lift_expr(e.operands[0], scope, fn_names, self_name, task_name, record, renamer)
        right = _lift_expr(e.operands[1], scope, fn_names, self_name, task_name, record, renamer)
        return {"op": e.ops[0], "args": [left, right]}
    if e.ops[0] in ("in", "!in"):
        record.rewrites.append(Rewrite(rule="in-desugared", line=e.line))
        x, s = e.operands
        k = renamer.fresh("k", record, "quantbind")
        s_e = _lift_expr(s, scope, fn_names, self_name, task_name, record, renamer)
        x_e = _lift_expr(x, scope, fn_names, self_name, task_name, record, renamer)
        body = {"op": "==", "args": [{"op": "at", "args": [s_e, {"var": k}]}, x_e]}
        exists = {"exists": {"var": k, "lo": {"int": 0}, "hi": {"op": "len", "args": [s_e]}, "body": body}}
        return exists if e.ops[0] == "in" else {"op": "not", "args": [exists]}
    # length >= 2: a genuine relational chain (section 4.3's chain-desugared row)
    record.rewrites.append(Rewrite(rule="chain-desugared", line=e.line))
    parts = []
    for i, op in enumerate(e.ops):
        left = _lift_expr(e.operands[i], scope, fn_names, self_name, task_name, record, renamer)
        right = _lift_expr(e.operands[i + 1], scope, fn_names, self_name, task_name, record, renamer)
        parts.append({"op": op, "args": [left, right]})
    return _and(parts)


def _lift_quantifier(q: Quantifier, scope: Scope, fn_names: dict, self_name: str,
                      task_name: str, record: LiftRecord, renamer: "_Renamer") -> dict:
    got = bound_quantifier(q)
    if got is None:
        raise ValueError("lift_rewrite: unbounded quantifier reached rewrite "
                          "(a lift_classify bug: should have been refused)")
    binders = got["binders"]
    body_expr = got["body"]

    def build(i: int, inner_scope: Scope) -> dict:
        name, lo, hi, mem = binders[i]
        fresh = renamer.fresh(name, record, "quantbind")
        s2 = inner_scope.copy()
        if mem is not None:
            record.rewrites.append(Rewrite(rule="in-desugared", line=q.line))
            s_e = _lift_expr(mem, inner_scope, fn_names, self_name, task_name, record, renamer)
            lo_e = {"int": 0}
            hi_e = {"op": "len", "args": [s_e]}
            s2.renames[name] = fresh  # bound var itself unused directly; substitution below
            body_sub = _subst(body_expr, name, _AtHole(s_e, fresh))
        else:
            lo_e = _lift_expr(lo, inner_scope, fn_names, self_name, task_name, record, renamer)
            hi_e = _lift_expr(hi, inner_scope, fn_names, self_name, task_name, record, renamer)
            s2.renames[name] = fresh
            body_sub = body_expr
        if i + 1 == len(binders):
            inner = _lift_expr(body_sub, s2, fn_names, self_name, task_name, record, renamer)
        else:
            inner = build(i + 1, s2)
        key = "forall" if q.kind == "forall" else "exists"
        return {key: {"var": fresh, "lo": lo_e, "hi": hi_e, "body": inner}}

    return build(0, scope)


class _AtHole:
    """Sentinel substituted for a `k in s` binder: `_subst` replaces every
    `Ident(k)` in the body with `at(s, j)` for the fresh loop binder `j`
    that indexes `s` (section 4.4's `forall k | k in s :: P` row lifts to
    `forall j in [0, len(s)) . P[k := s[j]]`). `_lift_expr` intercepts this
    sentinel directly, before generic dispatch, and emits `{"op": "at",
    "args": [seq_expr_json, {"var": binder}]}` -- never the bare seq
    expression, which would substitute the whole sequence for the bound
    element."""
    def __init__(self, seq_expr_json: dict, binder: str):
        self.seq_expr_json = seq_expr_json
        self.binder = binder


def _subst(e: Expr, name: str, repl) -> Expr:
    import dataclasses as _dc
    if isinstance(e, Ident):
        return repl if e.name == name else e
    if hasattr(e, "__dataclass_fields__"):
        changes = {}
        for f in _dc.fields(e):
            val = getattr(e, f.name)
            newval = _subst_any(val, name, repl)
            if newval is not val:
                changes[f.name] = newval
        return _dc.replace(e, **changes) if changes else e
    return e


def _subst_any(val, name, repl):
    if isinstance(val, tuple):
        return tuple(_subst_any(v, name, repl) for v in val)
    if isinstance(val, list):
        return [_subst_any(v, name, repl) for v in val]
    if hasattr(val, "__dataclass_fields__"):
        return _subst(val, name, repl)
    return val


# ---------------------------------------------------------------------------
# Decreases (section 6 / decision 11), with the "stated" vs.
# "rprint-inferred" best-effort label documented in the module docstring.
# ---------------------------------------------------------------------------

def _guard_operands(cond: Expr):
    """For a while guard, return (kind, lo_like, hi_like) used only to spot
    section 6's two documented single-expr shapes; `None` if `cond` is not
    one of the recognised guard forms."""
    if isinstance(cond, Chain) and len(cond.ops) == 1 and cond.ops[0] in ("<", "<="):
        return ("lt", cond.operands[0], cond.operands[1])
    if isinstance(cond, Chain) and len(cond.ops) == 1 and cond.ops[0] in (">", ">="):
        return ("gt", cond.operands[1], cond.operands[0])
    return None


def _looks_rprint_inferred(dec: Expr, guard: Expr) -> bool:
    g = _guard_operands(guard)
    if g is None:
        return False
    _, lo, hi = g
    if isinstance(dec, type(dec)) and dec.__class__.__name__ == "Binary" and dec.op == "-":
        if _expr_eq(dec.left, hi) and _expr_eq(dec.right, lo):
            return True
        if isinstance(dec.right, IntLit) and dec.right.value == 0 and _expr_eq(dec.left, hi):
            return True
    return False


def _expr_eq(a: Expr, b: Expr) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, Ident):
        return a.name == b.name
    if isinstance(a, IntLit):
        return a.value == b.value
    return False  # conservative: anything more complex counts as "different"


def _loop_decreases(w: WhileStmt, dc: DecreasesClause, scope: Scope, fn_names, self_name,
                     task_name, record, renamer) -> dict:
    exprs = dc.exprs
    if len(exprs) == 1:
        e = exprs[0]
        origin = "rprint-inferred" if (not isinstance(w.cond, type(None))
                                        and _looks_rprint_inferred(e, w.cond)) else "stated"
        record.decreases_origin[f"loop@{w.line}"] = origin
        return _lift_expr(e, scope, fn_names, self_name, task_name, record, renamer)
    assigned = set()
    for n in walk(w.body):
        if isinstance(n, Assign):
            for t in n.targets:
                if t.kind == "name":
                    assigned.add(t.name)
    kept = [e for e in exprs if not (isinstance(e, Ident) and e.name not in assigned)]
    if len(kept) == 1:
        record.decreases_origin[f"loop@{w.line}"] = "projected"
        record.rewrites.append(Rewrite(rule="decreases-tuple-reduced", line=dc.line))
        return _lift_expr(kept[0], scope, fn_names, self_name, task_name, record, renamer)
    record.decreases_origin[f"loop@{w.line}"] = "guess:sum"
    record.rewrites.append(Rewrite(rule="guess:sum", line=dc.line))
    lifted = [_lift_expr(e, scope, fn_names, self_name, task_name, record, renamer) for e in kept]
    out = lifted[0]
    for nxt in lifted[1:]:
        out = {"op": "+", "args": [out, nxt]}
    return out


def _function_decreases(d: FunctionDecl, fn_scope: Scope, fn_names, record, renamer) -> dict:
    dcs = [s for s in d.specs if isinstance(s, DecreasesClause)]
    if not dcs:
        # No self-call, no decreases needed at all (section 6, function rules).
        return None
    dc = dcs[0]
    exprs = dc.exprs
    if len(exprs) == 1:
        record.decreases_origin[d.name or "?"] = "stated"
        return _lift_expr(exprs[0], fn_scope, fn_names, d.name or "", fn_names.get(d.name, d.name or ""), record, renamer)
    calls = [c for c in walk(d.body) if isinstance(c, Call)
             and isinstance(c.fn, Ident) and c.fn.name == d.name]
    param_names = [p.name for p in d.params]
    dropped = unchanged_at_every_call(param_names, calls, len(exprs))
    kept = [exprs[i] for i in range(len(exprs)) if i not in dropped]
    if len(kept) == 1:
        record.decreases_origin[d.name or "?"] = "projected"
        record.rewrites.append(Rewrite(rule="decreases-tuple-reduced", line=dc.line))
        return _lift_expr(kept[0], fn_scope, fn_names, d.name or "", fn_names.get(d.name, d.name or ""), record, renamer)
    record.decreases_origin[d.name or "?"] = "guess:sum"
    record.rewrites.append(Rewrite(rule="guess:sum", line=dc.line))
    lifted = [_lift_expr(e, fn_scope, fn_names, d.name or "", fn_names.get(d.name, d.name or ""), record, renamer) for e in kept]
    out = lifted[0]
    for nxt in lifted[1:]:
        out = {"op": "+", "args": [out, nxt]}
    return out


def _self_calls_json(node) -> bool:
    if isinstance(node, dict):
        if "call" in node and node["call"].get("fun") == _self_calls_json.target:
            return True
        return any(_self_calls_json(v) for v in node.values())
    if isinstance(node, list):
        return any(_self_calls_json(v) for v in node)
    return False


def _has_self_call(body: list, target: str) -> bool:
    _self_calls_json.target = target
    return any(_self_calls_json(s) for s in body)


# ---------------------------------------------------------------------------
# Statement lifting (section 4.5).
# ---------------------------------------------------------------------------

def _desugar_returns(stmts: tuple, tail: bool, ret_name: str, record: LiftRecord,
                      ret_names: Optional[tuple] = None) -> tuple:
    """Section 4.5's three `return` rows, applied before the generic
    statement lift ever sees a `ReturnStmt` in TAIL position: those three
    rows (bare `return;`, `return r;`, `return e;`, all in the body's own
    tail position) desugar away here and log as `tail-return` (18.2's
    single vocabulary name for all three). A non-tail `ReturnStmt` --
    early exit, SPEC.md 2026-09-08, LIFTER-DECISIONS.md row 21 -- is no
    longer refused by `classify`, and this function leaves it untouched
    (it falls through to the trailing `else: out.append(s)` below,
    unmatched by every `isinstance` check here); `_lift_stmt`'s own
    `ReturnStmt` branch turns it into t's `{"return": [ret, e]}`
    statement instead.

    Row 29 (2026-09-09): `ret_names`, given only for a pair-return
    method, is `(dafny a-name, dafny b-name)` -- a tail `return a, b;`
    (both out-parameters named back exactly, Dafny's own no-op sugar for
    "return with whatever they already hold") drops the same way a
    single-return `return r;` does; any OTHER tail `return e1, e2;`
    becomes ONE parallel `Assign` with both out-parameter names as
    targets, which `_lift_stmt`'s existing multi-target `Assign` branch
    (decision 22's own array-swap machinery) already lifts correctly
    with no further change -- `rewrite()` appends the actual `r := (a,
    b)` combine once, after every statement in the body has been lifted,
    so this function's own job stays exactly what it already was for a
    single return: normalise a tail return into an ordinary assignment,
    or drop it when it says nothing new."""
    out = []
    n = len(stmts)
    for i, s in enumerate(stmts):
        this_tail = tail and (i == n - 1)
        if isinstance(s, type(s)) and s.__class__.__name__ == "ReturnStmt" and this_tail:
            record.rewrites.append(Rewrite(rule="tail-return", line=s.line))
            if not s.values:
                continue  # bare `return;` -- dropped
            if ret_names is not None:
                oa, ob = ret_names
                v0, v1 = s.values[0], s.values[1]
                if (isinstance(v0, Ident) and v0.name == oa
                        and isinstance(v1, Ident) and v1.name == ob):
                    continue  # `return a, b;` -- both already final, dropped
                out.append(Assign(s.line, (_lhs_name(oa, s.line), _lhs_name(ob, s.line)),
                                   (v0, v1)))
                continue
            v = s.values[0]
            if isinstance(v, Ident) and v.name == ret_name:
                continue  # `return r;` -- dropped
            out.append(Assign(s.line, (_lhs_name(ret_name, s.line),), (v,)))
        elif isinstance(s, IfStmt):
            then2 = _desugar_returns(s.then, this_tail, ret_name, record, ret_names)
            if isinstance(s.else_, tuple):
                else2 = _desugar_returns(s.else_, this_tail, ret_name, record, ret_names)
            elif isinstance(s.else_, IfStmt):
                else2 = _desugar_returns((s.else_,), this_tail, ret_name, record, ret_names)[0]
            else:
                else2 = s.else_
            out.append(IfStmt(s.line, s.cond, tuple(then2), else2 if s.else_ is None or isinstance(s.else_, IfStmt) else tuple(else2)))
        elif isinstance(s, WhileStmt):
            out.append(WhileStmt(s.line, s.cond, s.specs, tuple(_desugar_returns(s.body, False, ret_name, record, ret_names))))
        elif isinstance(s, ForStmt):
            out.append(ForStmt(s.line, s.var, s.var_type, s.lo, s.direction, s.hi, s.specs,
                                tuple(_desugar_returns(s.body, False, ret_name, record, ret_names))))
        elif isinstance(s, BlockStmt):
            out.append(BlockStmt(s.line, tuple(_desugar_returns(s.body, False, ret_name, record, ret_names))))
        elif isinstance(s, LabelStmt):
            inner = _desugar_returns((s.stmt,), False, ret_name, record, ret_names)
            out.append(inner[0] if inner else s.stmt)
        else:
            out.append(s)
    return tuple(out)


def _desugar_breaks(stmts: tuple, ret_name: str, record: LiftRecord) -> tuple:
    """LIFTER-DECISIONS.md row 23 (2026-09-09): run right after
    `_desugar_returns`, on the body it already produced. `lift_classify.
    scan_breaks` -- the SAME function `classify` used, on the raw AST, to
    decide this method is liftable in the first place -- is recomputed
    here on the desugared body so the two never disagree; every break it
    accepts is replaced by a deep copy of its loop's continuation
    followed by a bare `return;`, which `_lift_stmt`'s own ReturnStmt
    branch turns into t's early exit `{"return": [ret, {"var": ret}]}`.
    The out-parameter's definite assignment on this path is Dafny's own
    guarantee (section 4.7's check already ran, on the RAW body, in
    classify -- a break landing on a still-unassigned path is refused
    before rewrite ever sees it, so nothing further to check here).
    `ret_name` is unused -- kept for signature symmetry with
    `_desugar_returns`; the injected ReturnStmt is always bare, and
    `_lift_stmt` derives the return's t-name itself from
    `scope.ret_name`. Because `_desugar_returns` already ran, the only
    ReturnStmt `scan_breaks` can find here is a genuine non-tail one
    (`_continuation_issue`'s trailing-ReturnStmt exemption is simply
    never exercised on this call -- the tail return it exempts already
    vanished or became an Assign)."""
    _issues, accepted = scan_breaks(stmts)
    replace: dict[int, tuple] = {}
    for node, _loop, cont in accepted:
        dup = tuple(copy.deepcopy(c) for c in cont)
        replace[id(node)] = dup + (ReturnStmt(node.line, ()),)
        record.rewrites.append(Rewrite(rule="break-as-return", line=node.line))
        if cont:
            record.rewrites.append(Rewrite(rule="break-continuation-duplicated", line=node.line))
    return _apply_break_rewrites(stmts, replace)


def _apply_break_rewrites(stmts: tuple, replace: dict) -> tuple:
    """Rebuilds `stmts`, splicing `replace[id(break_node)]` in place of
    every BreakStmt `_desugar_breaks` accepted (a break can expand to
    several statements -- its duplicated continuation plus a return --
    so this is a splice, not a 1-for-1 substitution); mirrors
    `_desugar_returns`'s own recursion shape exactly, since every other
    statement kind is left untouched."""
    out = []
    for s in stmts:
        if isinstance(s, BreakStmt) and id(s) in replace:
            out.extend(replace[id(s)])
        elif isinstance(s, IfStmt):
            then2 = _apply_break_rewrites(s.then, replace)
            if isinstance(s.else_, tuple):
                else2 = _apply_break_rewrites(s.else_, replace)
            elif isinstance(s.else_, IfStmt):
                else2 = _apply_break_rewrites((s.else_,), replace)[0]
            else:
                else2 = s.else_
            out.append(IfStmt(s.line, s.cond, tuple(then2), else2 if s.else_ is None or isinstance(s.else_, IfStmt) else tuple(else2)))
        elif isinstance(s, WhileStmt):
            out.append(WhileStmt(s.line, s.cond, s.specs, tuple(_apply_break_rewrites(s.body, replace))))
        elif isinstance(s, ForStmt):
            out.append(ForStmt(s.line, s.var, s.var_type, s.lo, s.direction, s.hi, s.specs,
                                tuple(_apply_break_rewrites(s.body, replace))))
        elif isinstance(s, BlockStmt):
            out.append(BlockStmt(s.line, tuple(_apply_break_rewrites(s.body, replace))))
        elif isinstance(s, LabelStmt):
            inner = _apply_break_rewrites((s.stmt,), replace)
            out.append(inner[0] if inner else s.stmt)
        else:
            out.append(s)
    return tuple(out)


def _lhs_name(name: str, line: int):
    from lift_ast import Lhs
    return Lhs(line, kind="name", name=name)


def _assigned_dafny_names(body) -> set[str]:
    names: set[str] = set()
    for n in walk(body):
        if isinstance(n, Assign):
            for t in n.targets:
                if t.kind == "name":
                    names.add(t.name)
    return names


def _lift_stmt(s: Stmt, scope: Scope, fn_names: dict, self_name: str,
               task_name: str, renamer: _Renamer, record: LiftRecord) -> list:
    cls = s.__class__.__name__
    if cls == "Assign":
        if len(s.targets) > 1:
            # Decision 22: a target can now be `x[i]` as well as `x`
            # (Clover_reverse's `a[i], a[hi-i] := a[hi-i], a[i];`). Every
            # right-hand side AND every index expression is evaluated in
            # the PRE-state (Dafny's simultaneous-assignment rule, the
            # same reason the existing name-only case routes through
            # fresh temporaries at all), so both are computed in this
            # first pass, before any write; the second pass then applies
            # the writes in order, each `update` correctly composing on
            # top of the last for two targets sharing one array (a swap
            # via two disjoint indices reads back its own pre-state
            # values, exactly as `_t_expr`/interp.py already model
            # `update`).
            record.rewrites.append(Rewrite(rule="parallel-assign-temps", line=s.line))
            out = []
            temps = []
            for i, (lhs, rhs) in enumerate(zip(s.targets, s.values)):
                base_name = lhs.base.name if lhs.kind == "index" else lhs.name
                tgt_t = scope.renames[base_name]
                # decision 22: an INDEX target's temp holds one ELEMENT
                # (always `int`, v1's only array/seq element type), never
                # the array's OWN type (`scope.types[tgt_t]` is `seq`) --
                # measured, DafnyPrograms_..._invertarray: without this
                # fix `fuzz_lower.check_wf` reads "update wants (seq, int,
                # int)" (a `seq`-typed temp fed into `update`'s value slot).
                ty = "int" if lhs.kind == "index" else scope.types.get(tgt_t, "int")
                if isinstance(rhs, NewRhs):
                    rhs_e = _lift_new_array(rhs, scope, fn_names, self_name, task_name, record, renamer)
                else:
                    rhs_e = _lift_expr(rhs, scope, fn_names, self_name, task_name, record, renamer)
                tmp = renamer.fresh(f"tmp{i}", record, "temp")
                scope.types[tmp] = ty
                out.append({"var": {"name": tmp, "type": ty, "init": rhs_e}})
                if lhs.kind == "index":
                    idx_e = _lift_expr(lhs.index, scope, fn_names, self_name, task_name, record, renamer)
                    temps.append((tgt_t, tmp, idx_e))
                else:
                    temps.append((tgt_t, tmp, None))
            for tgt_t, tmp, idx_e in temps:
                if idx_e is None:
                    out.append({"assign": [tgt_t, {"var": tmp}]})
                else:
                    out.append({"assign": [tgt_t, {"op": "update",
                                                     "args": [{"var": tgt_t}, idx_e, {"var": tmp}]}]})
            return out
        lhs = s.targets[0]
        rhs = s.values[0]
        if lhs.kind == "index":
            # Decision 22: `a[i] := e` -> `a := a[i := e]`. `a`'s current
            # t-name (whatever `scope.renames` maps its dafny name to --
            # the return, once a `modifies`-param body's priming
            # `<ret> := a;` has run; the local/return itself for the
            # alloc-fill shape) is both the read and the write side.
            tgt_t = scope.renames[lhs.base.name]
            idx_e = _lift_expr(lhs.index, scope, fn_names, self_name, task_name, record, renamer)
            rhs_e = _lift_expr(rhs, scope, fn_names, self_name, task_name, record, renamer)
            record.rewrites.append(Rewrite(rule="array-elem-assign-as-update", line=s.line))
            return [{"assign": [tgt_t, {"op": "update", "args": [{"var": tgt_t}, idx_e, rhs_e]}]}]
        tgt_t = scope.renames[lhs.name]
        if isinstance(rhs, Call) and isinstance(rhs.fn, Ident) and rhs.fn.name == self_name:
            args = [_lift_expr(a, scope, fn_names, self_name, task_name, record, renamer) for a in rhs.args]
            return [{"assign": [tgt_t, {"call": {"fun": task_name, "args": args}}]}]
        if isinstance(rhs, NewRhs):
            rhs_e = _lift_new_array(rhs, scope, fn_names, self_name, task_name, record, renamer)
        else:
            rhs_e = _lift_expr(rhs, scope, fn_names, self_name, task_name, record, renamer)
        return [{"assign": [tgt_t, rhs_e]}]

    if cls == "VarDeclStmt":
        out = []
        if s.init is None:
            for nm in s.names:
                ty = _t_type_of(nm.type)
                tname = renamer.fresh(nm.name, record, "local")
                scope.renames[nm.name] = tname
                scope.types[tname] = ty
                if nm.type is not None and nm.type.kind == "nat":
                    scope.nat.append(nm.name)
                # `var r: seq;` with no initialiser needs a seq-shaped
                # default (rows 25-27, 2026-09-09), not the int/bool
                # default below -- an empty literal, `{"op": "seq",
                # "args": []}`, since `[]` is t's own empty seq value.
                if ty == "seq":
                    default = {"op": "seq", "args": []}
                else:
                    default = {"bool": False} if ty == "bool" else {"int": 0}
                out.append({"var": {"name": tname, "type": ty, "init": default}})
                record.rewrites.append(Rewrite(rule="default-init", line=s.line))
                record.clauses_added.append(ClauseAdded(rule="default-init", text=f"{tname} := {default}"))
        else:
            for nm, rhs in zip(s.names, s.init):
                if isinstance(rhs, NewRhs):
                    # Decision 22: `var b := new int[n];` (or `var b:
                    # array<int> := new int[n];`) -- `nm.type` is often
                    # `None` (Dafny infers it), so `_t_type_of(None)`
                    # would default to "int"; the RHS shape is what says
                    # this is a seq local, regardless of what the
                    # declared type (if any) says.
                    rhs_e = _lift_new_array(rhs, scope, fn_names, self_name, task_name, record, renamer)
                    ty = "seq"
                else:
                    rhs_e = _lift_expr(rhs, scope, fn_names, self_name, task_name, record, renamer)
                    if nm.type is not None:
                        ty = _t_type_of(nm.type)
                    else:
                        # Rows 25-27: an UNTYPED local (`var r := [];`,
                        # `var r := r + [x];`) is exactly as common a
                        # Dafny style as a typed one, and its own
                        # initialiser -- a literal, a slice, a `+`
                        # concatenation -- is the only place its kind
                        # comes from; `_t_type_of(None)` used to default
                        # to "int" unconditionally, sound only because a
                        # seq-shaped initialiser was always refused
                        # before ever reaching here.
                        inferred = _rw_seq_kind(rhs, scope)
                        ty = inferred if inferred in ("int", "bool", "seq") else "int"
                tname = renamer.fresh(nm.name, record, "local")
                scope.renames[nm.name] = tname
                scope.types[tname] = ty
                if nm.type is not None and nm.type.kind == "nat":
                    scope.nat.append(nm.name)
                out.append({"var": {"name": tname, "type": ty, "init": rhs_e}})
        return out

    if cls == "IfStmt":
        cond_e = _lift_expr(s.cond, scope, fn_names, self_name, task_name, record, renamer)
        then_scope = scope.copy()
        then_out = []
        for st in s.then:
            then_out.extend(_lift_stmt(st, then_scope, fn_names, self_name, task_name, renamer, record))
        else_scope = scope.copy()
        else_out = []
        if isinstance(s.else_, tuple):
            for st in s.else_:
                else_out.extend(_lift_stmt(st, else_scope, fn_names, self_name, task_name, renamer, record))
        elif s.else_ is not None:  # nested IfStmt
            else_out.extend(_lift_stmt(s.else_, else_scope, fn_names, self_name, task_name, renamer, record))
        return [{"if": {"cond": cond_e, "then": then_out, "else": else_out}}]

    if cls == "WhileStmt":
        cond_e = _lift_expr(s.cond, scope, fn_names, self_name, task_name, record, renamer)
        invs = []
        for sp in s.specs:
            if sp.__class__.__name__ != "InvariantClause":
                continue
            src_e = _strip_null_checks(sp.expr, scope.null_drop_ids, record, sp.line)
            if src_e is None:
                continue
            invs.append(_lift_expr(src_e, scope, fn_names, self_name, task_name, record, renamer))
        assigned = _assigned_dafny_names(s.body)
        for dn in scope.nat:
            if dn in assigned:
                tn = scope.renames[dn]
                clause = _ge0(tn)
                if not _already_present(clause, invs):
                    invs.append(clause)
                    record.clauses_added.append(ClauseAdded(rule="nat-invariant-added", text=f"{tn} >= 0"))
                    record.rewrites.append(Rewrite(rule="nat-invariant-added", line=s.line))
        dcs = [sp for sp in s.specs if sp.__class__.__name__ == "DecreasesClause"]
        dec_e = _loop_decreases(s, dcs[0], scope, fn_names, self_name, task_name, record, renamer)
        body_scope = scope.copy()
        body_out = []
        for st in s.body:
            body_out.extend(_lift_stmt(st, body_scope, fn_names, self_name, task_name, renamer, record))
        return [{"while": {"cond": cond_e, "invariants": invs, "decreases": dec_e, "body": body_out}}]

    if cls == "ForStmt":
        record.rewrites.append(Rewrite(rule="for-desugared", line=s.line))
        lo_e = _lift_expr(s.lo, scope, fn_names, self_name, task_name, record, renamer)
        hi_e = _lift_expr(s.hi, scope, fn_names, self_name, task_name, record, renamer)
        i_t = renamer.fresh(s.var, record, "local")
        scope.types[i_t] = "int"
        out = []
        body_scope = scope.copy()
        body_scope.renames[s.var] = i_t
        user_invs = []
        for sp in s.specs:
            if sp.__class__.__name__ != "InvariantClause":
                continue
            src_e = _strip_null_checks(sp.expr, scope.null_drop_ids, record, sp.line)
            if src_e is None:
                continue
            user_invs.append(_lift_expr(src_e, body_scope, fn_names, self_name, task_name, record, renamer))
        if s.direction == "to":
            h_t = renamer.fresh("h", record, "local")
            scope.types[h_t] = "int"
            out.append({"var": {"name": h_t, "type": "int", "init": hi_e}})
            out.append({"var": {"name": i_t, "type": "int", "init": lo_e}})
            cond = {"op": "<", "args": [{"var": i_t}, {"var": h_t}]}
            invs = [{"op": "<=", "args": [lo_e, {"var": i_t}]},
                    {"op": "<=", "args": [{"var": i_t}, {"var": h_t}]}] + user_invs
            dec = {"op": "-", "args": [{"var": h_t}, {"var": i_t}]}
            body_out = []
            for st in s.body:
                body_out.extend(_lift_stmt(st, body_scope, fn_names, self_name, task_name, renamer, record))
            body_out.append({"assign": [i_t, {"op": "+", "args": [{"var": i_t}, {"int": 1}]}]})
            out.append({"while": {"cond": cond, "invariants": invs, "decreases": dec, "body": body_out}})
        else:
            out.append({"var": {"name": i_t, "type": "int", "init": hi_e}})
            cond = {"op": ">", "args": [{"var": i_t}, lo_e]}
            invs = [{"op": "<=", "args": [lo_e, {"var": i_t}]},
                    {"op": "<=", "args": [{"var": i_t}, hi_e]}] + user_invs
            dec = {"op": "-", "args": [{"var": i_t}, lo_e]}
            body_out = [{"assign": [i_t, {"op": "-", "args": [{"var": i_t}, {"int": 1}]}]}]
            for st in s.body:
                body_out.extend(_lift_stmt(st, body_scope, fn_names, self_name, task_name, renamer, record))
            out.append({"while": {"cond": cond, "invariants": invs, "decreases": dec, "body": body_out}})
        return out

    if cls == "BlockStmt":
        out = []
        for st in s.body:
            out.extend(_lift_stmt(st, scope, fn_names, self_name, task_name, renamer, record))
        return out

    if cls == "LabelStmt":
        return _lift_stmt(s.stmt, scope, fn_names, self_name, task_name, renamer, record)

    if cls in ("AssertStmt", "AssertByStmt", "CalcStmt", "RevealStmt"):
        record.clauses_dropped.append(ClauseDropped(rule="assert-dropped", count=1))
        record.rewrites.append(Rewrite(rule="assert-dropped", line=s.line))
        return []

    if cls == "ForallStmt":
        record.clauses_dropped.append(ClauseDropped(rule="assert-dropped", count=1))
        record.rewrites.append(Rewrite(rule="assert-dropped", line=s.line))
        return []

    if cls == "CallStmt":
        record.clauses_dropped.append(ClauseDropped(rule="lemma-call-dropped", count=1))
        record.rewrites.append(Rewrite(rule="lemma-call-dropped", line=s.line))
        return []

    if cls == "ReturnStmt":
        # Early exit (v1, SPEC.md, 2026-09-08): a non-tail `ReturnStmt`
        # reaches here unchanged (`_desugar_returns` only touches TAIL
        # returns; classify no longer refuses any other position --
        # LIFTER-DECISIONS.md row 21). `return e;` lifts `e`; a bare
        # `return;` means the out-parameter was assigned earlier on this
        # path (section 4.7's definite-assignment check confirmed it), so
        # it reads back as the return variable itself.
        if scope.pair_ret is not None:
            # Row 29: `a`/`b` still read as the plain BODY locals here
            # (`scope` at this point IS `body_scope`, `pair_view`
            # cleared -- see `Scope.pair_ret`'s own docstring), so
            # `_lift_expr` needs no special casing; only the RESULT is
            # pair-shaped, `{"return": ["r", {"op": "pair", ...}]}`.
            t_ret, oa, ob = scope.pair_ret
            if s.values:
                e0 = _lift_expr(s.values[0], scope, fn_names, self_name, task_name, record, renamer)
                e1 = _lift_expr(s.values[1], scope, fn_names, self_name, task_name, record, renamer)
            else:
                e0 = {"var": scope.renames[oa]}
                e1 = {"var": scope.renames[ob]}
            record.rewrites.append(Rewrite(rule="early-exit-return", line=s.line))
            return [{"return": [t_ret, {"op": "pair", "args": [e0, e1]}]}]
        t_ret = scope.renames[scope.ret_name]
        if s.values:
            e = _lift_expr(s.values[0], scope, fn_names, self_name, task_name, record, renamer)
        else:
            e = {"var": t_ret}
        record.rewrites.append(Rewrite(rule="early-exit-return", line=s.line))
        return [{"return": [t_ret, e]}]

    raise ValueError(f"lift_rewrite: no statement mapping for {s!r} (a lift_classify bug: "
                      f"this construct should have been refused before rewrite ran)")


# ---------------------------------------------------------------------------
# Gate (task["gate"], informational -- section 4.1's row).
# ---------------------------------------------------------------------------

def _compute_gate(spec_funs_out: list, task_has_decreases: bool, body_out: list) -> Optional[str]:
    if spec_funs_out or task_has_decreases:
        return "recursion"
    if _contains_key(body_out, "while"):
        return "loops"
    if _contains_key(body_out, "forall") or _contains_key(body_out, "exists"):
        return "quantifiers"
    return None


def _contains_key(node, key) -> bool:
    if isinstance(node, dict):
        if key in node:
            return True
        return any(_contains_key(v, key) for v in node.values())
    if isinstance(node, list):
        return any(_contains_key(v, key) for v in node)
    return False


# ---------------------------------------------------------------------------
# Function (spec_fun) lifting (sections 4.1/4.6/6/7).
# ---------------------------------------------------------------------------

def _lift_function(d: FunctionDecl, renamer: _Renamer, fn_names: dict, record: LiftRecord) -> dict:
    scope = Scope()
    params_out = []
    guard_parts = []
    for p in d.params:
        tname = renamer.fresh(p.name, record, "fnparam")
        scope.renames[p.name] = tname
        if p.type is not None and p.type.kind == "seq":
            ty = "seq"
        elif p.type is not None and p.type.kind == "bool":
            ty = "bool"
        else:
            ty = "int"
        scope.types[tname] = ty
        params_out.append({"name": tname, "type": ty})
        if p.type is not None and p.type.kind == "nat":
            guard_parts.append(_ge0(tname))
            record.rewrites.append(Rewrite(rule="spec-fun-totalised", line=p.line))

    result_nat = d.ret_type is not None and d.ret_type.kind == "nat"
    # `predicate` declares no `: T` at all (implicit `: bool`, lift_ast.py's
    # FunctionDecl docstring) -- `d.ret_type` is None for one, so testing
    # only `ret_type.kind == "bool"` fell through to "int" and emitted a
    # spec_fun whose declared result disagreed with its (bool) body,
    # caught by fuzz_lower.check_wf as "body type != result" (nitwit's
    # valid_base/nitness/is_max_nit, all predicates).
    result = "bool" if (d.is_predicate
                        or (d.ret_type is not None and d.ret_type.kind == "bool")) else "int"
    if result_nat:
        record.clauses_dropped.append(ClauseDropped(rule="nat-result-fact-dropped", count=1))
        record.rewrites.append(Rewrite(rule="nat-result-fact-dropped", line=d.line))

    for spec in d.specs:
        if isinstance(spec, RequiresClause):
            guard_parts.append(_lift_expr(spec.expr, scope, fn_names, d.name or "", fn_names.get(d.name, d.name or ""), record, renamer))
            record.rewrites.append(Rewrite(rule="spec-fun-totalised", line=spec.line))
        elif isinstance(spec, EnsuresClause):
            record.clauses_dropped.append(ClauseDropped(rule="function-ensures-dropped", count=1))
            record.rewrites.append(Rewrite(rule="function-ensures-dropped", line=spec.line))
        elif isinstance(spec, ReadsClause):
            pass  # already refused by classify if non-trivial

    body_e = _lift_expr(d.body, scope, fn_names, d.name or "", fn_names.get(d.name, d.name or ""), record, renamer)
    if guard_parts:
        default = {"bool": False} if result == "bool" else {"int": 0}
        body_e = {"ite": {"cond": _and(guard_parts), "then": body_e, "else": default}}

    dec = _function_decreases(d, scope, fn_names, record, renamer)
    if dec is None:
        # A spec_fun with no self-call needs no decreases (SPEC.md gate 3
        # requires it only for well-founded recursion); default to a
        # constant so SYNTAX.md's mandatory "decreases" field is present
        # without asserting a false termination fact about a non-recursive
        # function (any constant is trivially >= 0 and never decreases,
        # which the kernel accepts since it is never actually re-checked
        # across a call that doesn't exist).
        dec = {"int": 0}

    return {"name": fn_names[d.name], "params": params_out, "result": result,
            "decreases": dec, "body": body_e}


# ---------------------------------------------------------------------------
# RewriteResult and the top-level `rewrite` entry point.
# ---------------------------------------------------------------------------

@dataclass
class RewriteResult:
    task: dict
    record: LiftRecord


def rewrite(module: Module, plan: Liftable, source_path: str,
            rprint_sha256: str) -> RewriteResult:
    method = plan.method
    closure = plan.closure
    renamer = _Renamer()
    record = LiftRecord(source_path=source_path, method="", rprint_sha256=rprint_sha256)

    t_method = renamer.fresh(method.name, record, "method")
    task_name = f"{_sanitize_stem(source_path)}__{t_method}"
    record.method = t_method

    array_mutation, _array_mutation_issue = find_array_mutation(method, closure)
    mutated_param_name = (array_mutation.name if array_mutation is not None
                           and array_mutation.kind == "modifies-param" else None)
    # Row 29 (2026-09-09, SPEC.md "Pairs (v1)"): `classify` already
    # confirmed both out-parameters' types are ones this lifter carries
    # as a return and demoted anything array-mutation-shaped away from a
    # SECOND return (`pair_returns` and `mutated_param_name` above are
    # mutually exclusive by construction of `classify`'s own returns
    # section).
    pair_returns = plan.pair_returns
    # Decision 22 "alloc-fill": the SOURCE `new int[n]`'s size expression
    # `n`, re-derived (never re-decided -- `find_array_mutation` already
    # confirmed this exact allocation is the mapped one) here as a plain
    # Dafny AST `Expr`, parsed but not yet LIFTED (that needs a scope with
    # every relevant name already bound, built up over the rest of this
    # function; done once `body_scope` exists, near the bottom). A `seq`'s
    # length is not automatically invariant across a `while` loop the way
    # a real array's `.Length` is, so this feeds the loop-invariant fix
    # below (`_add_array_length_invariants`) that keeps the LOWERED task
    # itself provable -- Clover_array_product measured: without it, the
    # lowered method's own `ensures |c| == |a|` fails to verify, since
    # nothing states `|c|` is preserved across the loop that builds it.
    alloc_fill_size_expr = None
    if array_mutation is not None and array_mutation.kind == "alloc-fill" and method.body is not None:
        from lift_classify import _alloc_bindings, _looks_like_array_new, _new_array_size_text
        for _line, _name, rhs in _alloc_bindings(method):
            if _name == array_mutation.name and _looks_like_array_new(rhs):
                parsed = _new_array_size_text(rhs)
                if parsed is not None:
                    alloc_fill_size_expr = _parse_size_expr(parsed[1])
                break

    # Row 24 (2026-09-09): recompute the SAME `scan_null_checks` classify
    # already ran on this exact `method` object to decide it was
    # liftable, so the two stages never disagree (`_desugar_breaks`'s
    # pattern for row 23); `Scope.null_drop_ids` carries it to every
    # requires/ensures/invariant lifting site below.
    null_drop_ids = frozenset(id(m) for _, _, m in scan_null_checks(method))

    scope = Scope()
    scope.null_drop_ids = null_drop_ids
    params_out = []
    for p in method.params:
        tname = renamer.fresh(p.name, record, "param")
        scope.renames[p.name] = tname
        if p.type is not None and p.type.kind == "array":
            ty = "seq"
            if p.name != mutated_param_name:
                record.rewrites.append(Rewrite(rule="array-readonly-as-seq", line=p.line))
        else:
            ty = _t_type_of(p.type)
        scope.types[tname] = ty
        if p.type is not None and p.type.kind == "nat":
            scope.nat.append(p.name)
        params_out.append({"name": tname, "type": ty})

    if mutated_param_name is not None:
        # Decision 22 "modifies-param" (SPEC.md "Sequences as values
        # (v1)"): no Dafny `returns` at all (find_array_mutation/classify
        # guarantee this -- a method that already returns something was
        # demoted back to "no mutation found" in classify() and refused
        # there instead). The fresh return's name is the mutated array's
        # own dafny name with "_out" appended; `renamer.fresh` makes it
        # collision-free the same way every other name here is (appending
        # `_v`, `_v2`, ... if `<name>_out` is already taken), and the
        # rename map records the choice like any other rename.
        param_tname = scope.renames[mutated_param_name]
        t_ret = renamer.fresh(f"{mutated_param_name}_out", record, "return")
        ret_ty = "seq"
        ret_is_nat = False
        ret_is_char = False
        scope.types[t_ret] = ret_ty
        returns_out = [{"name": t_ret, "type": ret_ty}]
        record.rewrites.append(Rewrite(rule="array-mutation-fresh-return", line=method.line))
    elif pair_returns is not None:
        # Row 29: `r`'s own name is synthesised (there is no single
        # Dafny identifier for the combined pair the way a single
        # return's own out-parameter name already gives one) -- "r" is
        # exactly what the two hand-written SPEC.md tasks
        # (`divmod_pair`, `min_max`) already use, so `renamer.fresh`
        # starts there and only falls back to `r2`/`r3`/... on a real
        # collision. `a`/`b` (this function's own local names for
        # readability; the actual dafny identifiers are `ret_a.name`/
        # `ret_b.name`) become ORDINARY locals (`a_t`/`b_t`), never
        # `scope.renames`d to `t_ret` the way a single return's own
        # out-parameter is -- `requires`/`ensures` reach `r.0`/`r.1`
        # through `scope.pair_view` instead, set below, and the two are
        # combined into `r` only at the body's own exits (`_lift_stmt`'s
        # `ReturnStmt` case for an early exit, and the trailing combine
        # `rewrite()` appends after the body loop for every path that
        # simply reaches the end).
        ret_a, ret_b = pair_returns
        t_ret = renamer.fresh("r", record, "return")
        a_t = renamer.fresh(ret_a.name, record, "local")
        b_t = renamer.fresh(ret_b.name, record, "local")

        def _pair_component_ty(t: Optional[Type]) -> str:
            if t is not None and t.kind in ("seq", "string"):
                return "seq"
            if t is not None and t.kind == "bool":
                return "bool"
            return "int"  # int, nat

        a_ty = _pair_component_ty(ret_a.type)
        b_ty = _pair_component_ty(ret_b.type)
        a_is_nat = ret_a.type is not None and ret_a.type.kind == "nat"
        b_is_nat = ret_b.type is not None and ret_b.type.kind == "nat"
        scope.types[a_t] = a_ty
        scope.types[b_t] = b_ty
        ret_is_nat = False
        ret_is_char = False
        returns_out = [{"name": t_ret, "type": {"pair": [a_ty, b_ty]}}]
        scope.pair_view = {ret_a.name: (t_ret, "fst"), ret_b.name: (t_ret, "snd")}
        record.rewrites.append(Rewrite(rule="multi-return-pair-lifted", line=method.line))
    else:
        ret = method.returns[0]
        t_ret = renamer.fresh(ret.name, record, "return")
        scope.renames[ret.name] = t_ret
        scope.ret_name = ret.name
        ret_is_nat = ret.type is not None and ret.type.kind == "nat"
        ret_is_char = ret.type is not None and ret.type.kind == "char"
        if ret.type is not None and ret.type.kind in ("array", "seq", "string"):
            # Decision 22 "alloc-fill": the return itself (or a local
            # later assigned to it) is `new int[n]`/`new nat[n]`-bound;
            # its Dafny type says seq return, not `_t_type_of`'s default.
            # Rows 25-27 (2026-09-09): a Dafny `seq<int>`/`seq<nat>`
            # return (`classify` no longer refuses `seq-return` on
            # either element type) reads the same way; `_t_type_of`
            # already does this, but that helper is not called here --
            # this branch predates it and is kept explicit for the
            # `nat`-tracking `ret_is_nat` line above it. Row 28
            # (2026-09-09): `string` joins `array`/`seq` here for the
            # same reason.
            ret_ty = "seq"
        else:
            ret_ty = "bool" if (ret.type is not None and ret.type.kind == "bool") else "int"
        scope.types[t_ret] = ret_ty
        if ret_is_nat:
            scope.nat.append(ret.name)
        returns_out = [{"name": t_ret, "type": ret_ty}]

    # -- spec_funs: names first (so requires/ensures/body can all reference
    #    any closure function regardless of textual order), bodies next.
    fn_names: dict = {}
    fn_decls = [d for d in closure if isinstance(d, FunctionDecl)]
    for d in fn_decls:
        fn_names[d.name] = renamer.fresh(d.name, record, "function")
    spec_funs_out = [_lift_function(d, renamer, fn_names, record) for d in fn_decls]
    unused = [d for d in module.decls if isinstance(d, (FunctionDecl, LemmaDecl))
              and d is not method and d.name not in fn_names]
    if unused:
        record.clauses_dropped.append(ClauseDropped(rule="unused-function-dropped", count=len(unused)))
        for d in unused:
            record.rewrites.append(Rewrite(rule="unused-function-dropped", line=d.line))
    if any(isinstance(x, MethodDecl) and x.name == "Main" for x in module.decls):
        record.clauses_dropped.append(ClauseDropped(rule="main-dropped", count=1))

    # Decision 22: `len(t_ret) == array_len_expr`, the one fact a real
    # Dafny array's `.Length` gives for free (fixed by construction) but
    # a `seq` return does not -- computed once, here, so it can be BOTH
    # the task's own first ensures clause (measured necessary: Dafny
    # checks an ensures clause's well-definedness against `requires` and
    # EARLIER ensures only, never against what the body's loop proved,
    # so `s_out[i]`/`s[i]` bounded by `|s_out|` alone is "index out of
    # range" without this) AND the fact `_add_array_length_invariants`
    # prepends to every loop that touches the mutated seq (same
    # well-definedness rule, one level down: SPEC.md "each loop
    # invariant may assume earlier invariants in its list"). `scope` (not
    # `body_scope`, which does not exist yet) is enough for either shape:
    # the "modifies-param" reference is another PARAMETER's own length,
    # and the "alloc-fill" size expression is measured, on every program
    # this row's `find_array_mutation` accepts, to name only params.
    array_len_expr = None
    if array_mutation is not None:
        if mutated_param_name is not None:
            array_len_expr = {"op": "len", "args": [{"var": param_tname}]}
        elif alloc_fill_size_expr is not None:
            array_len_expr = _lift_expr(alloc_fill_size_expr, scope, fn_names, method.name,
                                        task_name, record, renamer)

    # -- requires: nat-param-guard first, then char-param-guard (row 28),
    # then array<nat> elements, then source
    requires_out = []
    for p in method.params:
        if p.type is not None and p.type.kind == "nat":
            tn = scope.renames[p.name]
            requires_out.append(_ge0(tn))
            record.clauses_added.append(ClauseAdded(rule="nat-param-guard", text=f"{tn} >= 0"))
            record.rewrites.append(Rewrite(rule="nat-param-guard", line=p.line))
    for p in method.params:
        if p.type is not None and p.type.kind == "char":
            tn = scope.renames[p.name]
            requires_out.append(_char_range(tn))
            record.clauses_added.append(ClauseAdded(rule="char-param-guard",
                                                     text=f"0 <= {tn} <= {_CHAR_MAX}"))
            record.rewrites.append(Rewrite(rule="char-param-guard", line=p.line))
    for p in method.params:
        if (p.type is not None and p.type.kind == "array" and len(p.type.args) == 1
                and p.type.args[0].kind == "nat"):
            tn = scope.renames[p.name]
            k = renamer.fresh("k", record, "quantbind")
            clause = {"forall": {"var": k, "lo": {"int": 0}, "hi": {"op": "len", "args": [{"var": tn}]},
                                  "body": {"op": ">=", "args": [{"op": "at", "args": [{"var": tn}, {"var": k}]}, {"int": 0}]}}}
            requires_out.append(clause)
            record.clauses_added.append(ClauseAdded(rule="nat-elements-requires", text=f"forall k. {tn}[k] >= 0"))
            record.rewrites.append(Rewrite(rule="nat-elements-requires", line=p.line))
    for p in method.params:
        if p.type is not None and (p.type.kind == "string" or _is_seq_of_char(p.type)):
            # Row 28's own analogue of `nat-elements-requires`: a string
            # is a t seq of PLAIN ints with no per-element bound (t has
            # none to give a bare seq -- decision 14's own gap, same
            # reasoning `nat-elements-requires` exists to close for
            # `array<nat>`), so without this the differential harness's
            # own per-point conversion of a string PARAMETER's sampled
            # seq<int> value back into a Dafny `string` (`k as char` per
            # element, needed since the source's own parameter is
            # genuinely `string`-typed, not `seq<int>`) can pick a
            # code point outside [0, 1114111] and CRASH the whole `dafny
            # run` process (measured directly, `trun.dfy`: "Unhandled
            # exception... Value does not fall within the expected
            # range"), not merely mis-compare.
            tn = scope.renames[p.name]
            k = renamer.fresh("k", record, "quantbind")
            elem = {"op": "at", "args": [{"var": tn}, {"var": k}]}
            body = {"op": "and", "args": [
                {"op": ">=", "args": [elem, {"int": 0}]},
                {"op": "<=", "args": [elem, {"int": _CHAR_MAX}]}]}
            clause = {"forall": {"var": k, "lo": {"int": 0},
                                  "hi": {"op": "len", "args": [{"var": tn}]}, "body": body}}
            requires_out.append(clause)
            record.clauses_added.append(ClauseAdded(
                rule="string-elements-requires", text=f"forall k. 0 <= {tn}[k] <= {_CHAR_MAX}"))
            record.rewrites.append(Rewrite(rule="string-elements-requires", line=p.line))
    for spec in method.specs:
        if isinstance(spec, RequiresClause):
            src_e = _strip_null_checks(spec.expr, scope.null_drop_ids, record, spec.line)
            if src_e is None:
                continue
            e = _lift_expr(src_e, scope, fn_names, method.name, task_name, record, renamer)
            parts = _split_top_and(e)
            requires_out.extend(parts)
            if len(parts) > 1:
                record.rewrites.append(Rewrite(rule="split-conjuncts", line=spec.line))

    # -- decision 22 "modifies-param": from here on `a` (the mutated
    # array's dafny name) means the RETURN by default -- requires above
    # already ran against the parameter's own name, so this is the
    # right moment to flip it. `old(a[k])`/`old(a[..])` in the ensures
    # below still need the parameter's ORIGINAL value, which is why
    # `param_tname` was captured before this line and not simply
    # discarded: `scope.old_array_param_tname` is `_lift_expr`'s only
    # remaining way to reach it.
    if mutated_param_name is not None:
        scope.old_array_name = mutated_param_name
        scope.old_array_param_tname = param_tname
        scope.renames[mutated_param_name] = t_ret
        scope.ret_name = mutated_param_name

    # -- ensures: nat-return-ensures first, then source
    # decision 22 "alloc-fill": `fresh(b)` may name the source's OWN
    # return (`b`), the only shape `fresh()` is ever accepted for
    # (`_array_mutation_accepted_ids` in lift_classify.py); a
    # "modifies-param" method has no Dafny return for `fresh()` to name
    # at all, so `fresh_ret_name` is `None` there and any `Fresh` node
    # would only ever reach `_lift_expr`'s own `{"bool": True}` fallback.
    fresh_ret_name = (method.returns[0].name
                       if mutated_param_name is None and method.returns else None)
    ensures_out = []
    if ret_is_nat:
        ensures_out.append(_ge0(t_ret))
        record.clauses_added.append(ClauseAdded(rule="nat-return-ensures", text=f"{t_ret} >= 0"))
        record.rewrites.append(Rewrite(rule="nat-return-ensures", line=method.line))
    if ret_is_char:
        # Row 28's own analogue of `nat-return-ensures` (see `_char_range`'s
        # own comment for why this is needed, not merely tidy).
        ensures_out.append(_char_range(t_ret))
        record.clauses_added.append(ClauseAdded(rule="char-return-guard",
                                                 text=f"0 <= {t_ret} <= {_CHAR_MAX}"))
        record.rewrites.append(Rewrite(rule="char-return-guard", line=method.line))
    if array_len_expr is not None:
        ensures_out.append({"op": "==", "args": [{"op": "len", "args": [{"var": t_ret}]}, array_len_expr]})
        record.clauses_added.append(ClauseAdded(rule="array-length-return-ensures",
                                                 text=f"len({t_ret}) == <the mutated array's own length>"))
        record.rewrites.append(Rewrite(rule="array-length-return-ensures", line=method.line))
    if pair_returns is not None:
        # Row 29's own analogue of `nat-return-ensures`, stated on the
        # PROJECTION (`r.0`/`r.1`) rather than on `t_ret` itself: a pair
        # has no order (SPEC.md), so `t_ret >= 0` is not even well-typed,
        # but each component's own non-negativity is exactly the same
        # fact decision 4 already states for a plain `nat` return.
        if a_is_nat:
            clause = _ge0_of({"op": "fst", "args": [{"var": t_ret}]})
            ensures_out.append(clause)
            record.clauses_added.append(ClauseAdded(rule="nat-return-ensures", text=f"{t_ret}.0 >= 0"))
            record.rewrites.append(Rewrite(rule="nat-return-ensures", line=method.line))
        if b_is_nat:
            clause = _ge0_of({"op": "snd", "args": [{"var": t_ret}]})
            ensures_out.append(clause)
            record.clauses_added.append(ClauseAdded(rule="nat-return-ensures", text=f"{t_ret}.1 >= 0"))
            record.rewrites.append(Rewrite(rule="nat-return-ensures", line=method.line))
    for spec in method.specs:
        if isinstance(spec, EnsuresClause):
            src_e = _strip_fresh_conjuncts(spec.expr, fresh_ret_name, record, spec.line)
            if src_e is None:
                continue
            src_e = _strip_null_checks(src_e, scope.null_drop_ids, record, spec.line)
            if src_e is None:
                continue
            e = _lift_expr(src_e, scope, fn_names, method.name, task_name, record, renamer)
            parts = _split_top_and(e)
            ensures_out.extend(parts)
            if len(parts) > 1:
                record.rewrites.append(Rewrite(rule="split-conjuncts", line=spec.line))

    # -- body
    pair_ret_names = (ret_a.name, ret_b.name) if pair_returns is not None else None
    desugared = _desugar_returns(method.body, True, scope.ret_name, record, ret_names=pair_ret_names)
    desugared = _desugar_breaks(desugared, scope.ret_name, record)
    body_out = []
    body_scope = scope.copy()
    if mutated_param_name is not None:
        # SPEC.md: "the body starts with `<ret> := a;` so every later
        # `a[i] := e` rewrites to an update of the return". `param_tname`
        # is the array's PARAMETER value; `t_ret` is the fresh return,
        # already the target of every `a`-reference in `body_scope`
        # (inherited from `scope` above) from here on.
        body_out.append({"assign": [t_ret, {"var": param_tname}]})
    elif pair_returns is not None:
        # Row 29: from here on `a`/`b` are plain locals (`pair_view`
        # cleared, `renames` pointed at them instead -- see
        # `Scope.pair_view`'s own docstring); Dafny leaves an
        # out-parameter uninitialised, so each gets decision 13's own
        # `default-init` value (0/false/[]) -- every reachable exit
        # already assigns both before it is read or the method returns
        # (Dafny's own definite-assignment rule, re-checked by
        # `classify`'s section-4.7 pass above, once per component), so
        # this default is never actually observed.
        body_scope.pair_view = {}
        body_scope.renames[ret_a.name] = a_t
        body_scope.renames[ret_b.name] = b_t
        body_scope.pair_ret = (t_ret, ret_a.name, ret_b.name)
        for nm, ty in ((a_t, a_ty), (b_t, b_ty)):
            default = {"op": "seq", "args": []} if ty == "seq" else (
                {"bool": False} if ty == "bool" else {"int": 0})
            body_out.append({"var": {"name": nm, "type": ty, "init": default}})
            record.rewrites.append(Rewrite(rule="default-init", line=method.line))
            record.clauses_added.append(ClauseAdded(rule="default-init", text=f"{nm} := {default}"))
    for s in desugared:
        body_out.extend(_lift_stmt(s, body_scope, fn_names, method.name, task_name, renamer, record))

    if pair_returns is not None:
        # Every path that reaches the end of the method combines the two
        # locals into the pair return (SPEC.md, LIFTER-DECISIONS.md row
        # 29); an early exit already built its own `{"return": ["r",
        # {"op": "pair", ...}]}` in `_lift_stmt`, so this fires exactly
        # once, for the fall-through/tail path alone.
        body_out.append({"assign": [t_ret, {"op": "pair",
                                              "args": [{"var": a_t}, {"var": b_t}]}]})
        record.rewrites.append(Rewrite(rule="multi-return-pair-combined", line=method.line))

    if array_mutation is not None and array_len_expr is not None:
        mutated_tname = body_scope.renames.get(array_mutation.name)
        if mutated_tname is not None:
            _add_array_length_invariants(body_out, mutated_tname, array_len_expr, record)

    task = {"t": 1, "name": task_name, "params": params_out, "returns": returns_out,
            "requires": requires_out, "ensures": ensures_out, "body": body_out}
    if spec_funs_out:
        task["spec_funs"] = spec_funs_out

    self_recursive = _has_self_call(body_out, task_name)
    if self_recursive:
        dec_e, origin = _method_level_decreases(method, scope, fn_names, task_name, record, renamer)
        task["decreases"] = dec_e
        record.decreases_origin[task_name] = origin

    gate = _compute_gate(spec_funs_out, self_recursive, body_out)
    if gate:
        task["gate"] = gate

    return RewriteResult(task=task, record=record)


def _method_level_decreases(method: MethodDecl, scope: Scope, fn_names: dict,
                             task_name: str, record: LiftRecord, renamer: _Renamer):
    dcs = [s for s in method.specs if isinstance(s, DecreasesClause)]
    if not dcs:
        return {"int": 0}, "stated"  # a lift_classify gap: should be rare/refused upstream
    dc = dcs[0]
    exprs = dc.exprs
    if len(exprs) == 1:
        return _lift_expr(exprs[0], scope, fn_names, method.name, task_name, record, renamer), "stated"
    # Mirror `_function_decreases`'s projection test (decision 11): a
    # component is kept only when it CHANGES at every self-call (i.e. is
    # not passed through unchanged), found by walking the method's own
    # self-calls -- never by looking at which names the body assigns
    # (params like mystery1/mystery2's `n`, `m` are never reassigned, so
    # that test dropped every component and crashed on an empty `lifted`
    # list; see LIFTER-DESIGN.md section 6 / decision 11).
    calls = [c for c in walk(method.body) if isinstance(c, Call)
             and isinstance(c.fn, Ident) and c.fn.name == method.name] if method.body is not None else []
    param_names = [p.name for p in method.params]
    dropped = unchanged_at_every_call(param_names, calls, len(exprs))
    kept = [exprs[i] for i in range(len(exprs)) if i not in dropped]
    if len(kept) == 1:
        record.rewrites.append(Rewrite(rule="decreases-tuple-reduced", line=dc.line))
        return _lift_expr(kept[0], scope, fn_names, method.name, task_name, record, renamer), "projected"
    if len(kept) == 0:
        # classify's pre-check (section 5's `lexicographic-decreases`) is
        # supposed to have refused this already; fall back to summing
        # every stated component rather than crashing if it did not.
        kept = list(exprs)
    record.rewrites.append(Rewrite(rule="guess:sum", line=dc.line))
    lifted = [_lift_expr(e, scope, fn_names, method.name, task_name, record, renamer) for e in kept]
    out = lifted[0]
    for nxt in lifted[1:]:
        out = {"op": "+", "args": [out, nxt]}
    return out, "guess:sum"
