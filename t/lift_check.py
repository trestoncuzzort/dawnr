"""Check a lifted task against its source: the equivalence lemmas (section
9), the differential body run (section 10), and the reference-interpreter
third arm (section 18.5) -- all measured, none assumed.

Reads LIFTER-DESIGN.md sections 9 (the checker file's exact lemma shapes:
`L_fun_<name>`, `L_req`, `L_ens`, `L_inv_<k>`, the per-loop decreases
lemma), 10 (the differential harness: a `Main` that runs `<Method>_src`
and the lowered `<Method>` side by side under `dafny run FILE --no-verify`
over `interp.domain(task)`'s points, reporting `points=N bad=M`), 11
(validation plan -- what counts as a caught wrong lift), 18.3 (the
seeded-fault standing test this module's checker must catch: a wrong
`<==>`/`==>` reading, a sequenced parallel assignment, a dropped ensures
conjunct, a widened quantifier bound, a positive-for-negative literal, a
reached totalisation default, a negated loop guard, a dropped invariant),
18.4 (the inverse test against `lower_dafny.lower`, including its three
documented asymmetries), and 18.5 (the interp third arm and its
`interp-disagreement` / `arm-unavailable` outcomes). Also uses
`fuzz_lower.check_wf` (gate: a task this module is given must already
satisfy it, per the section-2 data-flow line "rewrite -> check_wf (must be
[])"; a non-empty result here is `check-wf-failed`, a lifter bug, never
silently patched), `interp.Reference`/`interp.domain` (the differential
domain and the interp arm's own values), `harness.twin_for` (the twin
rung and witness this module measures, not invents), `lower_dafny.lower`
(the lowering used both by the checker file's declaration 2 and by the
inverse test), and `verifiers/dafny.py` (the dafny invocation and outcome
classification style for verifying the checker file and running the
differential harness).

PROVENANCE NOTE on `source` (LIFTER-DECISIONS.md row 32, "do not trust a
lossy print of the source", 2026-09-12): `source: MethodDecl`'s own
requires/ensures/invariant/decreases are NOT trusted straight off
rprint's text by the time this module ever sees them. `lifter.py`'s
pipeline calls `lift_resolve.check_against_source(dfy_path, method)`
right after `lift_parse.gradable_methods` and before classify/rewrite/
this module -- it re-parses those same clauses from the ORIGINAL .dfy
file's own bytes (the exact grammar, a different token stream) and
corrects `method` IN PLACE wherever the two trees disagree (measured:
`dafny-synthesis_task_id_598` IsArmstrong, rprint drops the parens
around a divided operand of `*`, printing a DIFFERENT tree than the
source's own `(n / 100) * (n / 100) * (n / 100)`). So `L_req`/`L_ens`/
`L_inv_k` below already compare the LIFTED task against the SOURCE's own
text, never against rprint's print of it -- this module needed no lemma
change of its own once that correction ran upstream, since `source` IS
the corrected tree, not a second copy of it.

Architecture role (LIFTER-DESIGN.md section 2's table, copied verbatim):
    input: task JSON, source AST
    output: the checker .dfy (section 9), the differential harness .dfy
            (section 10), their verdicts
    MAY decide: `lift-check-failed` (lemma named), `lift-diff-failed`
                (input named)
    MAY NOT decide: to repair a failed lift

Section 2's data-flow line places this module after `fuzz_lower.check_wf`
and `interp.Reference` succeed: "rewrite -> fuzz_lower.check_wf (must be
[]) -> interp.Reference (must execute: >= 1 point, else `interp-no-point`
recorded, not a refusal) -> harness.twin_for (rung recorded, or twin
refusal recorded) -> checker file verified by dafny -> differential run ->
row." `check` below is that whole tail, from `check_wf` through the
differential run; `build_checker`/`build_differential` are its two
`.dfy`-producing sub-steps, exposed separately because the test plan
(section 12 test 4) verifies the checker file for `fatorial2` in isolation.

-----------------------------------------------------------------------
Implementation note on the source-closure printer (this module's own,
not lift_parse's)
-----------------------------------------------------------------------
Section 9 item 1 says the source's call-graph closure is renamed
"verbatim from rprint... textual on the rprint". `build_checker`'s own
signature, though, takes structured `lift_ast` nodes (`source:
MethodDecl`, `closure: tuple`), not the raw rprint string -- and
`lift_ast.py` (data only) stores no raw text for a `FunctionDecl` or
`MethodDecl`. So this module carries its own small Dafny-text printer
(`_print_expr`/`_print_stmt`/`_print_function_decl`/...) that walks the
structured AST and alpha-renames every `Ident`/`Call` whose name is a
closure declaration, which is semantically the textual rename section 9
describes (unambiguous identifiers, one name per declaration) without
requiring a raw-text field this module was not given. This printer is
private to `lift_check.py`; it is not `lift_parse.print_dafny` (that one
is reserved for the section-12/10(b) fixpoint test, never for lifting or
checking, per its own docstring) and it always fully parenthesises a
compound expression rather than tracking precedence, since the output is
read only by `dafny`, never by a person.
"""

from __future__ import annotations

import copy
import re
import subprocess
import tempfile
import time
import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from lift_ast import (
    LiftRecord, MethodDecl, FunctionDecl, Decl, Refusal, Param, Type, Star,
    Expr, IntLit, RealLit, BoolLit, CharLit, StringLit, Ident, Old, Fresh,
    Unary, Binary, NaryBool, Implies, Iff, Chain, IfExpr, Quantifier,
    SetDisplay, MapDisplay, SeqDisplay, Comprehension, TupleExpr, Call,
    Index, Slice, SeqUpdate, Member, Cast, TypeTest, Cardinality,
    RequiresClause, EnsuresClause, InvariantClause, ReadsClause,
    ModifiesClause, DecreasesClause,
    Assign, VarDeclStmt, AssignSuchThat, IfStmt, IfCaseStmt, WhileStmt,
    WhileCaseStmt, ForStmt, ReturnStmt, BreakStmt, ContinueStmt,
    AssertStmt, AssertByStmt, AssumeStmt, CalcStmt, ForallStmt, PrintStmt,
    ExpectStmt, RevealStmt, LabelStmt, CallStmt, BlockStmt,
)

import fuzz_lower
import interp
import harness
import lower_dafny
from verifiers import Outcome
from verifiers.dafny import DAFNY  # resolution only; never dafny.py's certificate logic

DEFAULT_TIMEOUT_S = 120.0
_TIMEOUT_SENTINEL = -9999

# Section 10(a)'s point cap (integrator fix 2026-09-06). Measured on
# dafny-synthesis_task_id_801 (CountEqualNumbers, 3 int params; interp's
# own domain for this task is exactly 2048 points, one of the 11 tasks
# whose full domain made `dafny run FILE --no-verify` time out): the OLD
# one-statement-per-point Main did not finish inside a 180s wall timeout
# at 2048 points (no `points=`/`bad=` line printed at all -- see
# `_build_differential_with_points`'s own docstring for the data-not-
# statements fix this constant sits alongside). Even with that fix,
# `dafny run`'s cost is superlinear in point count on the SAME task, same
# machine: 256 points 5.6s, 512 points 7.5s, 1024 points 26.2s, 2048
# points 87.0s (all `/usr/bin/time` wall-clock, compile+run together).
# 512 is the largest point count still comfortably inside a single-digit-
# times-ten-second budget, leaving headroom in the 120-200s per-file
# timeout for the checker's own dafny verify pass (section 9, ~1.1s
# measured on small files, more on a many-lemma file) and for four
# concurrent dafny processes contending on this shared box (house rule).
# A task with fewer points than this is unaffected (`points[:N]` is a
# no-op); the verdict names both M (the task's actual interp point count)
# and N (how many were actually run) so a capped row is never misread as
# a full-domain agreement.
DIFF_MAX_POINTS = 512


@dataclass
class CheckOutput:
    """`check`'s output: the two `.dfy` texts section 2's table names, plus
    `record` -- the SAME `LiftRecord` object passed in, mutated in place
    with `twin_rung`, `twin_witness`, `checker_verdicts`,
    `differential_verdict`, `dafny_exit_codes`, and `warnings` filled from
    what was actually measured (never predicted).

    `refusal` is `None` when every check that runs, passes; otherwise a
    `lift_ast.Refusal` with `stage="check"` and `reason` one of
    `check-wf-failed`, `lift-check-failed` (naming the failing lemma in
    `token`), or `lift-diff-failed` (naming the first differing input in
    `token`). A `twin-refused` outcome (`harness.twin_for` returning
    `(None, reason, None)`) is NOT this kind of refusal -- section 5's
    closing paragraph is explicit that a program which lifts and is
    refused at the twin is "in the fragment, cannot count", a different
    row from "out of the fragment"; `record.twin_rung` stays `None` and
    the twin's reason is recorded there, but `CheckOutput.refusal` stays
    `None` too unless a REAL check (check_wf, the checker lemmas, or the
    differential run) failed."""
    checker_dfy: str
    differential_dfy: str
    record: LiftRecord
    refusal: Optional[Refusal]
    interp_points: int
    interp_first_value: object


# ===========================================================================
# Type printing (source Dafny types, not t task types).
# ===========================================================================

def _print_type(t: Optional[Type]) -> str:
    if t is None:
        return "int"  # an untyped local (decision 13, default-init) prints as int
    if t.bits is not None:
        return f"bv{t.bits}"
    if t.kind == "id":
        base = t.name or "int"
    elif t.kind == "func":
        dom, cod = t.args
        return f"({_print_type(dom)}) -> {_print_type(cod)}"
    elif t.kind == "tuple":
        return "(" + ", ".join(_print_type(a) for a in t.args) + ")"
    else:
        base = t.kind
    suffix = "?" if t.nullable else ""
    if not t.args:
        return f"{base}{suffix}"
    return f"{base}{suffix}<{', '.join(_print_type(a) for a in t.args)}>"


def _is_nat_type(t: Optional[Type]) -> bool:
    """A primitive Dafny type's own keyword IS `kind` (measured against
    `lift_parse.parse`'s actual output: `nat`/`int`/`bool` all come back
    as `Type(kind=<keyword>, name=None)`; `kind == "id"` is reserved for a
    user-defined type name, per `Type`'s own docstring)."""
    return t is not None and t.kind == "nat"


def _is_bool_type(t: Optional[Type]) -> bool:
    return t is not None and t.kind == "bool"


def _lemma_param_type(t: Optional[Type]) -> str:
    """Section 9 items 4-6: lemma parameters are plain `int` (nat included)
    or `bool`; anything else (`seq<int>`, ...) is passed through as its own
    printed type (item 3's "Params of type seq<int> are passed as
    seq<int>")."""
    if t is None or _is_nat_type(t) or t.kind == "int":
        return "int"
    if _is_bool_type(t):
        return "bool"
    return _print_type(t)


def _print_param(p: Param) -> str:
    g = "ghost " if p.ghost else ""
    return f"{g}{p.name}: {_print_type(p.type)}"


def _print_binder(p: Param, rename: dict) -> str:
    """Like `_print_param`, but the bound name itself goes through
    `rename` too. A quantifier's own binder is a declaration, not a
    reference, so `_print_expr`'s plain `Ident` case never touches it --
    but `rename` (built by `_clause_rename` for a whole clause, not
    scoped per-quantifier) renames every occurrence of that name in the
    body when it collides with a lifted-side name (e.g. `k` -> `k_v`,
    recorded `collision` in the sidecar's rename_map). Printing the
    binder unrenamed then leaves the body referring to an identifier
    Dafny never bound (measured: Clover_max_array's L_ens, "unresolved
    identifier: k_v" -- the source's `forall k :: ... m >= a[k]` had its
    body's `k` renamed to `k_v` but its own `forall k` binder left as
    `k`)."""
    g = "ghost " if p.ghost else ""
    return f"{g}{rename.get(p.name, p.name)}: {_print_type(p.type)}"


# ===========================================================================
# Expression printing. Every compound expression is fully parenthesised;
# only atoms (literals, names, calls, indexing) are not. The output is
# read only by dafny, never by a person (module docstring).
# ===========================================================================

def _print_expr(e, rename: dict) -> str:
    if isinstance(e, IntLit):
        return str(e.value)
    if isinstance(e, RealLit):
        return e.text
    if isinstance(e, BoolLit):
        return "true" if e.value else "false"
    if isinstance(e, CharLit):
        # Row 28 (2026-09-09): `CharLit.text`/`StringLit.text` already
        # carry the surrounding quotes verbatim (`lift_parse.py`'s
        # tokenizer hands `tok_text = text[i:j]`, opening delimiter
        # through closing one INCLUSIVE), so re-wrapping in another pair
        # here double-quoted every one of them (`'a'` printed as `''a''`)
        # -- unreachable and untested before this row (every char/string
        # use refused earlier, at the type check), now load-bearing: the
        # checker file re-emits the SOURCE's own literal for its
        # equivalence lemmas, and a double-quoted one is a Dafny parse
        # error. `lift_parse.py`'s OWN `_print_expr` (a separate, unrelated
        # printer) already gets this right (`return e.text`, no
        # re-wrapping); this brings the two in line.
        return e.text
    if isinstance(e, StringLit):
        return e.text
    if isinstance(e, Ident):
        return rename.get(e.name, e.name)
    if isinstance(e, Old):
        return f"old({_print_expr(e.arg, rename)})"
    if isinstance(e, Fresh):
        return f"fresh({_print_expr(e.arg, rename)})"
    if isinstance(e, Unary):
        return f"({e.op}{_print_expr(e.arg, rename)})"
    if isinstance(e, Binary):
        return f"({_print_expr(e.left, rename)} {e.op} {_print_expr(e.right, rename)})"
    if isinstance(e, NaryBool):
        joiner = f" {e.op} "
        return "(" + joiner.join(_print_expr(a, rename) for a in e.args) + ")"
    if isinstance(e, Implies):
        return f"({_print_expr(e.left, rename)} ==> {_print_expr(e.right, rename)})"
    if isinstance(e, Iff):
        return f"({_print_expr(e.left, rename)} <==> {_print_expr(e.right, rename)})"
    if isinstance(e, Chain):
        parts = [_print_expr(e.operands[0], rename)]
        for op, operand in zip(e.ops, e.operands[1:]):
            parts.append(op)
            parts.append(_print_expr(operand, rename))
        return "(" + " ".join(parts) + ")"
    if isinstance(e, IfExpr):
        return (f"(if {_print_expr(e.cond, rename)} then "
                f"{_print_expr(e.then, rename)} else {_print_expr(e.else_, rename)})")
    if isinstance(e, Quantifier):
        binders = ", ".join(_print_binder(b, rename) for b in e.binders)
        rng = f" | {_print_expr(e.range, rename)}" if e.range is not None else ""
        return f"({e.kind} {binders}{rng} :: {_print_expr(e.body, rename)})"
    if isinstance(e, SetDisplay):
        return "{" + ", ".join(_print_expr(x, rename) for x in e.elems) + "}"
    if isinstance(e, MapDisplay):
        pairs = ", ".join(f"{_print_expr(k, rename)} := {_print_expr(v, rename)}"
                          for k, v in e.pairs)
        return "map[" + pairs + "]"
    if isinstance(e, SeqDisplay):
        return "[" + ", ".join(_print_expr(x, rename) for x in e.elems) + "]"
    if isinstance(e, Comprehension):
        binders = ", ".join(_print_binder(b, rename) for b in e.binders)
        rng = f" | {_print_expr(e.range, rename)}" if e.range is not None else ""
        if e.kind == "map" and e.value is not None:
            return f"map {binders}{rng} :: {_print_expr(e.body, rename)} := {_print_expr(e.value, rename)}"
        return f"{e.kind} {binders}{rng} :: {_print_expr(e.body, rename)}"
    if isinstance(e, TupleExpr):
        return "(" + ", ".join(_print_expr(x, rename) for x in e.elems) + ")"
    if isinstance(e, Call):
        fn = _print_expr(e.fn, rename)
        args = ", ".join(_print_expr(a, rename) for a in e.args)
        return f"{fn}({args})"
    if isinstance(e, Index):
        return f"{_print_expr(e.base, rename)}[{_print_expr(e.index, rename)}]"
    if isinstance(e, Slice):
        lo = _print_expr(e.lo, rename) if e.lo is not None else ""
        hi = _print_expr(e.hi, rename) if e.hi is not None else ""
        return f"{_print_expr(e.base, rename)}[{lo}..{hi}]"
    if isinstance(e, SeqUpdate):
        return (f"{_print_expr(e.base, rename)}[{_print_expr(e.index, rename)} "
                f":= {_print_expr(e.value, rename)}]")
    if isinstance(e, Member):
        return f"{_print_expr(e.base, rename)}.{e.name}"
    if isinstance(e, Cast):
        return f"({_print_expr(e.base, rename)} as {_print_type(e.type)})"
    if isinstance(e, TypeTest):
        return f"({_print_expr(e.base, rename)} is {_print_type(e.type)})"
    if isinstance(e, Cardinality):
        return f"|{_print_expr(e.arg, rename)}|"
    raise TypeError(f"lift_check._print_expr: unhandled node {type(e).__name__}")


def _print_exprlist_or_star(x, rename: dict) -> str:
    if isinstance(x, Star):
        return "*"
    return ", ".join(_print_expr(e, rename) for e in x)


def _print_rhs(r, rename: dict) -> str:
    if isinstance(r, Star):
        return "*"
    if hasattr(r, "text"):  # NewRhs
        return r.text
    return _print_expr(r, rename)


def _print_lhs(l, rename: dict) -> str:
    if l.kind == "name":
        return rename.get(l.name, l.name)
    if l.kind == "index":
        return f"{_print_expr(l.base, rename)}[{_print_expr(l.index, rename)}]"
    return f"{_print_expr(l.base, rename)}.{l.field}"


# ===========================================================================
# Statement printing.
# ===========================================================================

def _print_stmts(stmts, indent: int, rename: dict) -> list:
    out = []
    for s in stmts:
        out.extend(_print_stmt(s, indent, rename))
    return out


def _print_loopspec_line(spec, indent: int, rename: dict) -> str:
    ind = "  " * indent
    if isinstance(spec, InvariantClause):
        return f"{ind}invariant {_print_expr(spec.expr, rename)}"
    if isinstance(spec, DecreasesClause):
        return f"{ind}decreases {_print_exprlist_or_star(spec.exprs, rename)}"
    if isinstance(spec, ModifiesClause):
        return f"{ind}modifies {_print_exprlist_or_star(spec.exprs, rename)}"
    raise TypeError(f"lift_check: unhandled loop spec {type(spec).__name__}")


def _print_stmt(s, indent: int, rename: dict) -> list:
    ind = "  " * indent
    if isinstance(s, Assign):
        lhs = ", ".join(_print_lhs(t, rename) for t in s.targets)
        rhs = ", ".join(_print_rhs(v, rename) for v in s.values)
        return [f"{ind}{lhs} := {rhs};"]
    if isinstance(s, VarDeclStmt):
        g = "ghost " if s.ghost else ""
        names = ", ".join(_print_param(p) for p in s.names)
        if s.init is None:
            return [f"{ind}{g}var {names};"]
        vals = ", ".join(_print_rhs(v, rename) for v in s.init)
        return [f"{ind}{g}var {names} := {vals};"]
    if isinstance(s, AssignSuchThat):
        names = ", ".join(_print_param(p) for p in s.names)
        return [f"{ind}var {names} :| {_print_expr(s.cond, rename)};"]
    if isinstance(s, IfStmt):
        cond = "*" if isinstance(s.cond, Star) else _print_expr(s.cond, rename)
        lines = [f"{ind}if {cond} {{"]
        lines += _print_stmts(s.then, indent + 1, rename)
        if s.else_ is None:
            lines.append(f"{ind}}}")
        elif isinstance(s.else_, IfStmt):
            nested = _print_stmt(s.else_, indent, rename)
            lines.append(f"{ind}}} else " + nested[0].lstrip())
            lines += nested[1:]
        else:
            lines.append(f"{ind}}} else {{")
            lines += _print_stmts(s.else_, indent + 1, rename)
            lines.append(f"{ind}}}")
        return lines
    if isinstance(s, WhileStmt):
        cond = "*" if isinstance(s.cond, Star) else _print_expr(s.cond, rename)
        lines = [f"{ind}while {cond}"]
        for spec in s.specs:
            lines.append(_print_loopspec_line(spec, indent + 1, rename))
        lines.append(f"{ind}{{")
        lines += _print_stmts(s.body, indent + 1, rename)
        lines.append(f"{ind}}}")
        return lines
    if isinstance(s, ForStmt):
        vt = f": {_print_type(s.var_type)}" if s.var_type is not None else ""
        lines = [f"{ind}for {s.var}{vt} := {_print_expr(s.lo, rename)} "
                 f"{s.direction} {_print_expr(s.hi, rename)}"]
        for spec in s.specs:
            lines.append(_print_loopspec_line(spec, indent + 1, rename))
        lines.append(f"{ind}{{")
        lines += _print_stmts(s.body, indent + 1, rename)
        lines.append(f"{ind}}}")
        return lines
    if isinstance(s, ReturnStmt):
        if not s.values:
            return [f"{ind}return;"]
        return [f"{ind}return {', '.join(_print_expr(v, rename) for v in s.values)};"]
    if isinstance(s, BreakStmt):
        return [f"{ind}break{(' ' + s.label) if s.label else ''};"]
    if isinstance(s, ContinueStmt):
        return [f"{ind}continue{(' ' + s.label) if s.label else ''};"]
    if isinstance(s, AssertStmt):
        return [f"{ind}assert {_print_expr(s.cond, rename)};"]
    if isinstance(s, AssertByStmt):
        lines = [f"{ind}assert {_print_expr(s.cond, rename)} by {{"]
        lines += _print_stmts(s.proof, indent + 1, rename)
        lines.append(f"{ind}}}")
        return lines
    if isinstance(s, AssumeStmt):
        return [f"{ind}assume {_print_expr(s.cond, rename)};"]
    if isinstance(s, CalcStmt):
        return [s.text]
    if isinstance(s, ForallStmt):
        binders = ", ".join(_print_param(b) for b in s.binders)
        rng = f" | {_print_expr(s.range, rename)}" if s.range is not None else ""
        lines = [f"{ind}forall {binders}{rng} {{"]
        lines += _print_stmts(s.body, indent + 1, rename)
        lines.append(f"{ind}}}")
        return lines
    if isinstance(s, PrintStmt):
        args = _print_exprlist_or_star(s.args, rename)
        return [f"{ind}print {args};"]
    if isinstance(s, ExpectStmt):
        return [f"{ind}expect {_print_expr(s.cond, rename)};"]
    if isinstance(s, RevealStmt):
        return [f"{ind}{s.text}"]
    if isinstance(s, LabelStmt):
        inner = _print_stmt(s.stmt, indent, rename)
        inner[0] = f"{ind}{s.label}: " + inner[0].lstrip()
        return inner
    if isinstance(s, CallStmt):
        nm = rename.get(s.name, s.name)
        args = ", ".join(_print_expr(a, rename) for a in s.args)
        return [f"{ind}{nm}({args});"]
    if isinstance(s, BlockStmt):
        lines = [f"{ind}{{"]
        lines += _print_stmts(s.body, indent + 1, rename)
        lines.append(f"{ind}}}")
        return lines
    if isinstance(s, (IfCaseStmt, WhileCaseStmt)):
        raise TypeError(f"lift_check: {type(s).__name__} cannot appear in a "
                        "gradable method's closure (refused upstream)")
    raise TypeError(f"lift_check._print_stmt: unhandled node {type(s).__name__}")


# ===========================================================================
# Declaration printing (the closure's own functions/methods, alpha-renamed).
# ===========================================================================

def _print_fspec(spec, rename: dict) -> str:
    if isinstance(spec, RequiresClause):
        return f"  requires {_print_expr(spec.expr, rename)}"
    if isinstance(spec, EnsuresClause):
        return f"  ensures {_print_expr(spec.expr, rename)}"
    if isinstance(spec, ReadsClause):
        return f"  reads {_print_exprlist_or_star(spec.exprs, rename)}"
    if isinstance(spec, DecreasesClause):
        return f"  decreases {_print_exprlist_or_star(spec.exprs, rename)}"
    raise TypeError(f"lift_check: unhandled function spec {type(spec).__name__}")


def _print_mspec(spec, rename: dict) -> str:
    if isinstance(spec, ModifiesClause):
        return f"  modifies {_print_exprlist_or_star(spec.exprs, rename)}"
    return _print_fspec(spec, rename)


def _print_function_decl(fd: FunctionDecl, rename: dict) -> list:
    g = "ghost " if fd.ghost else ""
    kw = "predicate" if fd.is_predicate else "function"
    tp = f"<{', '.join(fd.type_params)}>" if fd.type_params else ""
    params = ", ".join(_print_param(p) for p in fd.params)
    name = rename.get(fd.name, fd.name)
    ret = "" if fd.is_predicate else f": {_print_type(fd.ret_type)}"
    lines = [f"{g}{kw} {name}{tp}({params}){ret}"]
    for sp in fd.specs:
        lines.append(_print_fspec(sp, rename))
    if fd.body is not None:
        lines.append("{")
        lines.append(f"  {_print_expr(fd.body, rename)}")
        lines.append("}")
    lines.append("")
    return lines


def _print_method_decl(md: MethodDecl, rename: dict) -> list:
    tp = f"<{', '.join(md.type_params)}>" if md.type_params else ""
    params = ", ".join(_print_param(p) for p in md.params)
    name = rename.get(md.name, md.name)
    returns = (f" returns ({', '.join(_print_param(p) for p in md.returns)})"
              if md.returns else "")
    lines = [f"method {name}{tp}({params}){returns}"]
    for sp in md.specs:
        lines.append(_print_mspec(sp, rename))
    if md.body is not None:
        lines.append("{")
        lines += _print_stmts(md.body, 1, rename)
        lines.append("}")
    lines.append("")
    return lines


def _closure_rename_map(source: MethodDecl, closure: tuple) -> dict:
    names = {d.name for d in closure if getattr(d, "name", None)}
    if source.name:
        names.add(source.name)
    return {n: f"{n}_src" for n in names}


# ===========================================================================
# t-task JSON expression printing (the LIFTED side's clause text). A small
# printer of its own: lower_dafny.lower renders a whole program, not one
# clause, and its own `expr`/`stmts` helpers are private to that module.
# ===========================================================================

def _fn_param_views(params) -> dict:
    """Row 28: a closure FUNCTION's own char/string-typed params, keyed
    by name, in `_view_text`'s vocabulary -- distinct from the METHOD
    -level `views` dict `_build_checker_parts` builds (a spec_fun's own
    parameter names are a separate scope with no reason to share a
    method param's name OR its type; a bug caught directly, measured:
    `dafny-synthesis_task_id_113` IsInteger's own `isDigit(c: char)`,
    `c` absent from the method-level `views` entirely since the METHOD
    itself has no `c` parameter, called the LIFTED spec_fun with a bare
    `char`-typed `c` and failed to resolve, "incorrect argument type for
    function parameter 'c' (expected int, found char)")."""
    out: dict = {}
    for p in params:
        if p.type is None:
            continue
        if p.type.kind == "char":
            out[p.name] = "char"
        elif p.type.kind == "string" or (p.type.kind == "seq" and len(p.type.args) == 1
                                          and p.type.args[0].kind == "char"):
            out[p.name] = "string"
    return out


def _view_text(name: str, views: dict) -> str:
    """The lifted side's own reference to a lemma-parameter `name`, when
    the lemma signature declares it in the SOURCE's own type rather than
    t's (decision 1's `array_view`, generalised by row 28 to `string`/
    `char`): `views[name]` is `\"array\"` (`(a[..])`, decision 1's own
    text, unchanged), `\"string\"` (a `seq<int>` VIEW of a string built by
    a bounded `seq(...)` comprehension: SPEC.md's own model says a string
    IS this sequence of code points, and `at`/`len`/`+`/slice/`==` on the
    substituted text then just work, exactly as `(a[..])` does for an
    array, since the substituted expression genuinely has Dafny type
    `seq<int>`) or `\"char\"` (`(c as int)`, always safe, row 28). Absent
    or any other value: the bare name, unchanged."""
    kind = views.get(name)
    if kind == "array":
        return f"({name}[..])"
    if kind == "string":
        return (f"(seq(|{name}|, (k: int) requires 0 <= k < |{name}| "
                 f"=> {name}[k] as int))")
    if kind == "char":
        return f"({name} as int)"
    return name


def _t_expr(e: dict, views: dict = {}) -> str:
    """`views` names the task's own params/return that a source type
    OTHER than t's own (`array<int>`, decision 1's `array-readonly-as-seq`,
    or `string`/`char`, row 28's own mapping) was lifted to: the checker
    lemma keeps ONE lemma parameter per such argument, typed to the
    SOURCE's own type so the source-side clause reads naturally, so a
    bare task-side reference to that name has to be VIEWED as its t
    shape instead -- `|a|` on an `array<int>` is a Dafny type error
    (measured: Clover_max_array's L_req/L_ens/L_inv/L_dec, "size operator
    expects a collection argument (instead got array<int>)"), and a
    string-typed `s[i]` is `char`, not the `int` the lifted clause means
    by `at`. `_view_text` does the one substitution every leaf reference
    needs; see its own docstring for the three shapes."""
    if "int" in e:
        return str(e["int"])
    if "bool" in e:
        return "true" if e["bool"] else "false"
    if "var" in e:
        return _view_text(e["var"], views)
    if "ite" in e:
        c = e["ite"]
        return (f"(if {_t_expr(c['cond'], views)} then {_t_expr(c['then'], views)} "
                f"else {_t_expr(c['else'], views)})")
    if "forall" in e or "exists" in e:
        kw = "forall" if "forall" in e else "exists"
        q = e[kw]
        joiner = "==>" if kw == "forall" else "&&"
        return (f"({kw} {q['var']}: int :: {_t_expr(q['lo'], views)} <= {q['var']} "
                f"< {_t_expr(q['hi'], views)} {joiner} {_t_expr(q['body'], views)})")
    if "call" in e:
        c = e["call"]
        args = ", ".join(_t_expr(a, views) for a in c["args"])
        return f"{c['fun']}({args})"
    op = e["op"]
    args = e.get("args", [])
    if op == "neg":
        return f"(-{_t_expr(args[0], views)})"
    if op == "not":
        return f"(!{_t_expr(args[0], views)})"
    if op == "len":
        return f"|{_t_expr(args[0], views)}|"
    if op == "at":
        return f"{_t_expr(args[0], views)}[{_t_expr(args[1], views)}]"
    if op in ("and", "or"):
        joiner = " && " if op == "and" else " || "
        return "(" + joiner.join(_t_expr(a, views) for a in args) + ")"
    if op == "implies":
        return f"({_t_expr(args[0], views)} ==> {_t_expr(args[1], views)})"
    if op in ("+", "-", "*", "<", "<=", ">", ">=", "==", "!="):
        return f"({_t_expr(args[0], views)} {op} {_t_expr(args[1], views)})"
    if op in ("div", "mod"):
        # SPEC.md "Division and modulo (v1)": Dafny's own `/` and `%` on
        # int are Euclidean too (measured on dafny 4.11.0), at the same
        # precedence as `*`, so `div`/`mod` print straight back to `/`/`%`.
        dfy_op = "/" if op == "div" else "%"
        return f"({_t_expr(args[0], views)} {dfy_op} {_t_expr(args[1], views)})"
    if op == "seq":
        # Rows 25-27 (2026-09-09, SPEC.md "Sequences: literals,
        # concatenation, slices (v1)"): `{"op": "seq", "args": [...]}` is
        # a Dafny sequence display, `[]` for no arguments. `+` on two
        # seqs needs no case of its own here: the "+" branch above
        # already prints `(a + b)`, valid Dafny for both int addition
        # and seq concatenation (t's own `+` is polymorphic the same
        # way, per SPEC.md).
        return "[" + ", ".join(_t_expr(a, views) for a in args) + "]"
    if op == "slice":
        return f"{_t_expr(args[0], views)}[{_t_expr(args[1], views)}..{_t_expr(args[2], views)}]"
    if op == "update":
        # Row 30 (2026-09-10, SPEC.md "Nested sequences (v1)"): `s[i :=
        # r]`, Dafny's own functional seq-update syntax -- the same
        # expression `lift_rewrite`'s `SeqUpdate` case (and decision 22's
        # `a[i] := e` statement rewrite) targets.
        return f"{_t_expr(args[0], views)}[{_t_expr(args[1], views)} := {_t_expr(args[2], views)}]"
    if op == "fill":
        # `fill(n, r)`: `n` copies of `r` (SPEC.md "Nested sequences
        # (v1)"; decision 22's own `new int[n]` reading uses the same
        # operator for a scalar fill). Dafny's `seq(n, _ => r)`.
        return f"seq({_t_expr(args[0], views)}, _ => {_t_expr(args[1], views)})"
    if op == "pair":
        # Row 29 (2026-09-09, SPEC.md "Pairs (v1)"): `{"op": "pair",
        # "args": [a, b]}` prints as Dafny's own native tuple literal
        # `(a, b)`, valid on this dafny (4.11.0) with no declaration
        # needed -- the ONE checker file this function's own output
        # feeds (the source-vs-lifted equivalence lemmas, never the
        # differential harness's own `lower_dafny.py`-produced program,
        # a separate code path) only ever needs a Dafny expression the
        # SMT solver can compare componentwise, and a native tuple gives
        # that for free (`==` on two Dafny tuples is componentwise,
        # matching SPEC.md's own `==`/`!=` on pairs). Independent of
        # whatever per-kernel representation `lower_dafny.py` chooses
        # for a FULL lowering (LIFTER-DECISIONS.md row 29's own
        # residual note): this row never calls that module.
        return f"({_t_expr(args[0], views)}, {_t_expr(args[1], views)})"
    if op in ("fst", "snd"):
        # `p.0`/`p.1`, Dafny's own native tuple projection (SPEC.md:
        # "dafny and verus tuples with .0 and .1"); parenthesised since
        # `p` is itself an arbitrary expression, not always a bare name.
        idx = "0" if op == "fst" else "1"
        return f"({_t_expr(args[0], views)}).{idx}"
    raise ValueError(f"lift_check._t_expr: unknown t operator {op!r}")


def _t_conj(exprs: list, views: dict = {}) -> str:
    if not exprs:
        return "true"
    return " && ".join(f"({_t_expr(e, views)})" for e in exprs)


def _conj_text(exprs: list, rename: dict) -> str:
    if not exprs:
        return "true"
    return " && ".join(f"({_print_expr(e, rename)})" for e in exprs)


def _and(parts: list) -> str:
    parts = [p for p in parts if p and p != "true"]
    if not parts:
        return "true"
    if len(parts) == 1:
        return parts[0]
    return "(" + " && ".join(parts) + ")"


def _task_loops(body: list) -> list:
    """Pre-order list of the lifted task's `while` dicts, matching the
    source AST's own pre-order loop walk (`_walk_source_loops`) index for
    index -- both walk depth-first, left-to-right, through `if`/`while`
    exactly the same way, so loop k in one is loop k in the other."""
    out = []

    def walk(stmts):
        for s in stmts:
            if "while" in s:
                out.append(s["while"])
                walk(s["while"]["body"])
            elif "if" in s:
                walk(s["if"]["then"])
                walk(s["if"].get("else", []))
    walk(body)
    return out


def _task_var_inits(body: list) -> dict:
    """Name -> init-expr dict for every `{"var": {"name", "init", ...}}`
    statement in the lifted task's body, pre-order through `if`/`while`
    (same walk shape as `_task_loops`). A `for`-desugared loop's own
    range-bound local (decision 15's `h_t := <hi>`) is declared exactly
    this way, and nowhere else -- it has no source-side counterpart, so
    the L_inv_k lemma's parameter for it (`extra_names` in
    `_build_checker_parts`) carries no fact tying its value to anything,
    making the loop's own <==> obligation state a claim about an
    arbitrary `h` rather than the one construction actually produces:
    genuinely false for an `h` the real run never takes (LIFTER-785-
    RESIDUALS.md's `FindMax`/`FindSmallest` shape, and 2026-09-12's 29-
    row `lift-check-failed` group's largest sub-shape both reduce to
    this), not merely hard for Dafny to automate on its own. This lookup
    lets the caller add `requires h == <the same init expr, printed>` --
    a fact the lift's own construction establishes once, stated, not
    invented, per decision 4."""
    out: dict = {}

    def walk(stmts):
        for s in stmts:
            if "var" in s and "init" in s["var"]:
                out[s["var"]["name"]] = s["var"]["init"]
            elif "while" in s:
                walk(s["while"]["body"])
            elif "if" in s:
                walk(s["if"]["then"])
                walk(s["if"].get("else", []))
    walk(body)
    return out


def _task_loop_scopes(body: list) -> list:
    """Pre-order list of the lifted task's own local-variable names in
    scope at each `while`, index-for-index with `_walk_source_loops` (same
    depth-first walk `_task_loops` uses). Needed because `crename` (a flat
    name->name overlay built from `record.rename_map`, see `_clause_rename`)
    cannot tell apart two source declarations that happen to share one
    name in different scopes -- measured on Clover_min_array: the source's
    two ensures-clause quantifier binders and its loop-local variable are
    ALL named `i`, so the renamer's rename_map holds one bare entry `i`
    (the first `i` it renamed, here a quantifier binder, -> `i_v`) and one
    `i#local` entry for the second (the loop local, -> `i_v2`); `crename`'s
    flat lookup always returns the bare entry, so `L_inv_0`'s signature
    named the loop-scope local `i_v` while the lifted invariant text
    (printed straight from the task JSON, which HAS the real lexical
    scoping) says `i_v2` -- two unrelated identifiers, `L_inv_0` reads
    "unresolved identifier: i_v2" and the whole checker file is tool_error.
    This walk instead reads the task's own local names off its body in the
    same declaration order the source's `VarDeclStmt`s are walked in, so
    the lemma signature can name each loop-scope local by what the task
    JSON already calls it -- no rename_map guess needed. Positional, like
    `_task_loops`; a `for`-loop's desugared range locals (decision 15) have
    no source-side declaration to align against and are not addressed
    here."""
    out = []

    def walk(stmts, sc):
        for s in stmts:
            if "var" in s:
                sc = sc + [s["var"]["name"]]
            elif "while" in s:
                out.append(list(sc))
                walk(s["while"]["body"], sc)
            elif "if" in s:
                walk(s["if"]["then"], sc)
                walk(s["if"].get("else", []), sc)
    walk(body, [])
    return out


def _walk_source_loops(source: MethodDecl) -> list:
    """Pre-order `(loop, scope)` pairs from the source method's body: every
    `WhileStmt`/`ForStmt`, and the `Param` list in scope there (the
    method's own params plus every local declared before that point on
    the path reaching it -- section 9 item 6's "every local in scope at
    the loop")."""
    out = []

    def walk(stmts, sc):
        for s in stmts:
            if isinstance(s, VarDeclStmt):
                sc = sc + list(s.names)
            elif isinstance(s, WhileStmt):
                out.append((s, list(sc)))
                walk(s.body, sc)
            elif isinstance(s, ForStmt):
                # The for-loop's OWN iteration variable is in scope for
                # ITS OWN invariants (Dafny allows `for i := lo to hi
                # invariant P(i)`), not only for a nested loop inside the
                # body -- appending it only on the recursive `walk` call
                # (as the code did before) left it out of `out`'s own
                # recorded scope, so `locals_in_scope` in
                # `_build_checker_parts` never carried it and the source
                # invariant's own `i` had no lemma parameter to bind to
                # (measured: dafny-synthesis_task_id_62's FindSmallest,
                # "unresolved identifier: i_v" in L_inv_0 -- the for's `i`
                # itself, crename-translated, never appeared in the
                # signature).
                vt = s.var_type or Type(line=s.line, kind="id", name="int")
                sc_here = sc + [Param(line=s.line, name=s.var, type=vt)]
                out.append((s, list(sc_here)))
                walk(s.body, sc_here)
            elif isinstance(s, IfStmt):
                walk(s.then, sc)
                if isinstance(s.else_, tuple):
                    walk(s.else_, sc)
                elif isinstance(s.else_, IfStmt):
                    walk((s.else_,), sc)
            elif isinstance(s, BlockStmt):
                walk(s.body, sc)
            elif isinstance(s, LabelStmt):
                walk((s.stmt,), sc)
            # AssertByStmt.proof, ForallStmt.body: ghost-only, hints
            # (section 9's "what the checker does NOT see"), never walked
            # for loops that would need a real-body lemma.
    walk(source.body or (), list(source.params))
    return out


def _clause_rename(source: MethodDecl, task: dict, rename: dict) -> dict:
    """The rename map used only when extracting the SOURCE's own
    requires/ensures/invariant/decreases EXPRESSIONS for a lemma body
    (never for printing a full declaration verbatim): the closure's
    `_src` renames, plus an overlay mapping the source's own param/return
    names onto the task's, positionally -- both sides of an equivalence
    lemma must share one name per variable, and section 9 item 1 ("params
    and locals keep their names") is about the CLOSURE's declarations
    staying byte-faithful when printed whole, not about clause text that
    is merged with the lifted task's own names inside one lemma."""
    overlay = dict(rename)
    for sp, tp in zip(source.params, task["params"]):
        if sp.name != tp["name"]:
            overlay[sp.name] = tp["name"]
    if source.returns:
        overlay[source.returns[0].name] = task["returns"][0]["name"]
    return overlay


def _param_overlay(rename: dict, record: LiftRecord, src_names, task_names,
                   src_ret=None, task_ret=None) -> dict:
    """`rename` already carries the closure's `_src` suffixing (function
    and method DECLARATION names); this only ever ADDS entries for
    variables (params, locals, the return) it does not already cover.
    `record.rename_map` also maps a source name onto a t name -- but for
    a closure declaration that mapping is `Fat` -> `fat` (the LIFTED
    spec_fun's own name, `_match_spec_fun`'s business), which is a
    DIFFERENT question from what this overlay answers ("what does a
    clause call `Fat_src` inside a lemma"); merging it in wholesale
    clobbers the `_src` mapping for exactly the names that need it, so a
    `rename_map` entry is only pulled in here for a name `rename` has
    nothing to say about (a param/local that needed sanitising, never a
    closure declaration)."""
    overlay = dict(rename)
    handled = set(rename)
    for sn, tn in zip(src_names, task_names):
        overlay[sn] = tn
        handled.add(sn)
    if src_ret is not None:
        overlay[src_ret] = task_ret
        handled.add(src_ret)
    for src_name, ren in record.rename_map.items():
        if src_name not in handled:
            overlay[src_name] = ren.t_name
    return overlay


def _clause_rename(source: MethodDecl, task: dict, record: LiftRecord,
                   rename: dict) -> dict:
    """The rename map used only when extracting the SOURCE's own
    requires/ensures/invariant/decreases EXPRESSIONS for a lemma body
    (never for printing a full declaration verbatim): the closure's
    `_src` renames, plus an overlay mapping the source's own param/return
    names onto the task's, positionally -- both sides of an equivalence
    lemma must share one name per variable, and section 9 item 1 ("params
    and locals keep their names") is about the CLOSURE's declarations
    staying byte-faithful when printed whole, not about clause text that
    is merged with the lifted task's own names inside one lemma. A local
    (not a param) defaults to the identity mapping (the common case,
    unless `record.rename_map` says otherwise) since it has no positional
    counterpart in `task["params"]` to align against."""
    task_ret_name = task["returns"][0]["name"]
    is_pair = (len(source.returns) == 2
               and isinstance(task["returns"][0].get("type"), dict)
               and "pair" in task["returns"][0]["type"])
    if is_pair:
        # Row 29: NEITHER of the source's two out-parameters has a
        # positional task-side counterpart of its own (`task["returns"]`
        # has exactly one entry, the pair) -- both map onto the SAME
        # lemma parameter's own PROJECTION instead, `r.0`/`r.1`, plain
        # text substitution (`_print_expr`'s `Ident` case does exactly
        # that, `rename.get(name, name)`, and `r.0`/`r.1` is already
        # valid Dafny -- no AST restructuring needed, the same reading
        # `_t_expr`'s new `fst`/`snd` cases print on the LIFTED side of
        # the very same lemma parameter).
        overlay = _param_overlay(
            rename, record,
            [p.name for p in source.params], [p["name"] for p in task["params"]])
        overlay[source.returns[0].name] = f"{task_ret_name}.0"
        overlay[source.returns[1].name] = f"{task_ret_name}.1"
        return overlay
    return _param_overlay(
        rename, record,
        [p.name for p in source.params], [p["name"] for p in task["params"]],
        source.returns[0].name if source.returns else None,
        task_ret_name)


def _split_array_post_state(e: Expr, array_name: str, post_ident: str) -> Expr:
    """Decision 22 "modifies-param": a COPY of `e` with every occurrence
    of `Ident(array_name)` OUTSIDE an `Old(...)` wrapper replaced by
    `Ident(post_ident)`. `array_name` is the one mutated array's source
    name (Dafny repeats this ONE identifier for both its pre- and
    post-state readings, `old(a[k])` and `a[k])`; `_print_expr` cannot
    tell those apart through a single flat rename dict, so this rewrites
    the AST first instead. Everything INSIDE `Old(...)` is left alone --
    `crename[array_name]` already means the parameter there (the ordinary
    positional param mapping `_clause_rename` sets up), and this checker
    lemma has no heap mutation of its own for `old(...)` to look past, so
    Dafny reads `old(a[k])` as plain `a[k]` regardless."""
    if isinstance(e, Old):
        return e
    if isinstance(e, Ident):
        return dataclasses.replace(e, name=post_ident) if e.name == array_name else e
    if not dataclasses.is_dataclass(e):
        return e
    changed = {}
    for f in dataclasses.fields(e):
        v = getattr(e, f.name)
        if isinstance(v, Expr):
            nv = _split_array_post_state(v, array_name, post_ident)
            if nv is not v:
                changed[f.name] = nv
        elif isinstance(v, tuple) and v and all(isinstance(x, Expr) for x in v):
            nv = tuple(_split_array_post_state(x, array_name, post_ident) for x in v)
            if nv != v:
                changed[f.name] = nv
    return dataclasses.replace(e, **changed) if changed else e


def _strip_fresh_src(exprs: list, ret_name: Optional[str]) -> list:
    """Decision 22 "alloc-fill": drop `fresh(b)` from the SOURCE ensures
    list before printing, `b` being the source's own return -- symmetric
    with `lift_rewrite._strip_fresh_conjuncts`, which already keeps it
    out of the LIFTED side. `fresh(...)` on an arbitrary lemma parameter
    (this checker lemma has no old-heap of its own) is not something
    Dafny evaluates the way it would inside the method that actually
    allocated `b`, so leaving it in on one side and not the other would
    make the two conjunctions compare unrelated things, not equivalent
    ones. A whole clause that IS `fresh(b)` is dropped outright; a
    top-level `&&` conjunct that is `fresh(b)` is stripped from its
    clause; anything else is untouched."""
    if ret_name is None:
        return exprs
    out = []
    for e in exprs:
        if isinstance(e, Fresh) and isinstance(e.arg, Ident) and e.arg.name == ret_name:
            continue
        if isinstance(e, NaryBool) and e.op == "&&":
            kept = [a for a in e.args
                    if not (isinstance(a, Fresh) and isinstance(a.arg, Ident) and a.arg.name == ret_name)]
            if not kept:
                continue
            out.append(kept[0] if len(kept) == 1 else dataclasses.replace(e, args=tuple(kept)))
            continue
        out.append(e)
    return out


def _expr_children(node):
    if not dataclasses.is_dataclass(node):
        return
    for f in dataclasses.fields(node):
        v = getattr(node, f.name)
        if isinstance(v, Expr):
            yield v
        elif isinstance(v, tuple):
            for x in v:
                if isinstance(x, Expr):
                    yield x
                elif isinstance(x, tuple):
                    for y in x:
                        if isinstance(y, Expr):
                            yield y


def _walk_exprs(e):
    """Every Expr node reachable from `e`, `e` included -- a Dafny-AST
    equivalent of `ast.walk`, driven generically off `dataclasses.fields`
    so it needs no per-node-type case list."""
    yield e
    for c in _expr_children(e):
        yield from _walk_exprs(c)


def _find_fun_calls(exprs: list, fd_names: set) -> list:
    """Every distinct `Call` to a closure function found anywhere in
    `exprs` (an invariant's, say), de-duplicated by (callee, printed
    argument list) so the same application is not hinted twice."""
    out, seen = [], set()
    for e in exprs:
        for node in _walk_exprs(e):
            if isinstance(node, Call) and isinstance(node.fn, Ident) \
                    and node.fn.name in fd_names:
                key = (node.fn.name, tuple(_print_expr(a, {}) for a in node.args))
                if key not in seen:
                    seen.add(key)
                    out.append(node)
    return out


def _call_guard(fd: FunctionDecl, call: Call, crename: dict) -> str:
    """The domain guard `fd`'s own `L_fun_<name>` lemma requires,
    specialised to one particular call site's argument expressions (a
    plain substitution of `call.args`' printed text for `fd.params`'
    names -- safe here since the substituted text only ever appears
    inside a freshly generated `if` guard immediately before the matching
    call, never re-parsed or nested further)."""
    arg_texts = [_print_expr(a, crename) for a in call.args]
    subst = dict(crename)
    for p, txt in zip(fd.params, arg_texts):
        subst[p.name] = txt
    nat_clause = _and([f"{txt} >= 0" for p, txt in zip(fd.params, arg_texts)
                       if _is_nat_type(p.type)])
    p_src = _conj_text([sp.expr for sp in fd.specs if isinstance(sp, RequiresClause)], subst)
    return _and([nat_clause, p_src])


def _match_spec_fun(fd: FunctionDecl, spec_funs: list, record: LiftRecord):
    """The lifted spec_fun this closure function became, or `None`. Tries
    `record.rename_map` first (the authority when the source name needed
    sanitising), then a case-insensitive exact name match (the common
    case: a source `Fat` becomes a lifted `fat`, section 4.8's casing,
    with no `Rename` entry logged since nothing was actually renamed for
    a keyword/collision reason)."""
    r = record.rename_map.get(fd.name)
    if r is not None:
        for f in spec_funs:
            if f["name"] == r.t_name:
                return f
    for f in spec_funs:
        if f["name"].lower() == (fd.name or "").lower():
            return f
    return None


# ===========================================================================
# build_checker (section 9).
# ===========================================================================

def _build_checker_parts(task: dict, source: MethodDecl, closure: tuple,
                         record: LiftRecord):
    """Shared by the public `build_checker` and `check`: returns (text,
    lemma_names) so `check` need not re-derive the lemma name list by
    re-parsing its own generated text."""
    rename = _closure_rename_map(source, closure)
    fdecls = [d for d in closure if isinstance(d, FunctionDecl)]
    mdecls = [d for d in closure if isinstance(d, MethodDecl)]

    lines = ["// Section 9 checker file: source closure (renamed _src) "
             "vs. the lifted task.", ""]
    for fd in fdecls:
        lines.extend(_print_function_decl(fd, rename))
    for md in mdecls:
        lines.extend(_print_method_decl(md, rename))

    lines.append(lower_dafny.lower(task, task["body"]))

    lemma_names = []
    ret = task["returns"][0]

    # Decision 22 (SPEC.md "Sequences as values (v1)"): the method's ONE
    # mutated/allocated array, if any, re-derived with the SAME shared
    # detector `lift_classify.py`/`lift_rewrite.py` use (never a second,
    # possibly-disagreeing analysis). `array_mutation_ret_name` is `None`
    # unless this checker file needs decision 22's own extra machinery.
    import lift_classify
    array_mutation, _ = lift_classify.find_array_mutation(source, closure)
    mutated_param = (next((p for p in source.params if p.name == array_mutation.name), None)
                     if array_mutation is not None and array_mutation.kind == "modifies-param"
                     else None)
    # Row 29 (2026-09-09, SPEC.md "Pairs (v1)"): a `multi-return`
    # source (`lift_rewrite.rewrite` already confirmed exactly two
    # out-parameters, both component types this lifter carries) has
    # NO single Dafny type of its own for a lemma parameter to declare
    # -- synthesised here as a `lift_ast.Type(kind="tuple", ...)`,
    # `_print_type`'s EXISTING tuple case (decision 11's own machinery,
    # for a stated `decreases` tuple) already renders that as Dafny's
    # own native `(T1, T2)`, the same notation `_t_expr`'s `pair`/`fst`/
    # `snd` cases print on the LIFTED side (both sides read the SAME
    # lemma parameter `r`, so they must agree on its printed type).
    pair_src = (source.returns if (len(source.returns) == 2
                and isinstance(task["returns"][0].get("type"), dict)
                and "pair" in task["returns"][0]["type"]) else None)
    # `ret_type_src`: the DAFNY type the checker lemma's RETURN parameter
    # should carry. Ordinarily the source's own declared return type; for
    # a "modifies-param" mutation (no Dafny return at all -- the fresh
    # return IS the mutated array's final state) it is that array's own
    # declared type instead, so the lemma parameter reads `array<int>`,
    # matching what the task's `seq` return actually stands for.
    ret_type_src = (mutated_param.type if mutated_param is not None
                    else (Type(line=source.line, kind="tuple",
                               args=(pair_src[0].type, pair_src[1].type))
                          if pair_src is not None
                          else (source.returns[0].type if source.returns else None)))
    # `fresh_ret_name`: the source's OWN return name, when this is
    # decision 22's "alloc-fill" shape (`returns (b: array<int>) ensures
    # fresh(b) && ...`) -- the one shape `fresh(...)` is dropped for, on
    # BOTH sides of the equivalence (the lifted side already never emits
    # it; `_strip_fresh_src` below keeps the source side symmetric, since
    # `fresh(b)` on an arbitrary, unrelated lemma parameter is not
    # something Dafny can evaluate the same way it would inside the
    # method that actually allocated `b`).
    fresh_ret_name = (source.returns[0].name
                      if array_mutation is not None and array_mutation.kind == "alloc-fill"
                      and source.returns else None)

    # Decision 1 (`array-readonly-as-seq`): a source `array<int>` param is
    # lifted to a task `seq<int>` param of the SAME name. The checker
    # lemmas (below) keep one parameter per argument, typed to the
    # SOURCE's type so the source clause reads naturally (`a.Length`,
    # `a[k]`); `views` names which task params/return that leaves typed
    # something OTHER than t's own shape in the lemma signature, and
    # WHICH other shape (`\"array\"`, `\"string\"`, `\"char\"`), so every
    # LIFTED-side reference to one of them must print as its t-shaped
    # view instead of bare -- `_t_expr`/`_t_conj`/`_view_text` do that
    # substitution. Decision 22 extends the array case to the RETURN too,
    # exactly the same way, whenever `ret_type_src` says it is an array
    # (both its shapes: the synthesized "modifies-param" return and the
    # "alloc-fill" return); row 28 (2026-09-09, SPEC.md "Strings as
    # sequences of code points (v1)") adds `string`/`char` params and
    # return, the same "one lemma parameter, typed to the source" reading.
    views: dict = {}
    for sp, tp in zip(source.params, task["params"]):
        if sp.type is None:
            continue
        if sp.type.kind == "array":
            views[tp["name"]] = "array"
        elif sp.type.kind == "string":
            views[tp["name"]] = "string"
        elif sp.type.kind == "char":
            views[tp["name"]] = "char"
    if ret_type_src is not None:
        if ret_type_src.kind == "array":
            views[ret["name"]] = "array"
        elif ret_type_src.kind == "string":
            views[ret["name"]] = "string"
        elif ret_type_src.kind == "char":
            views[ret["name"]] = "char"
    lifted_req = _t_conj(task.get("requires", []), views)

    # (3) L_fun_F per spec_fun whose closure function is found. `args`
    # (raw names) calls the SOURCE function, whose own params genuinely
    # carry the source's types; `lifted_args` (row 28: `_view_text` per
    # param) calls the LIFTED spec_fun, whose own signature is t's shape
    # throughout (`seq`/`int`) -- calling it with a bare `string`/`char`
    # -typed name would be a Dafny type error the way a bare `array<int>`
    # already was before decision 1's own `array_view` (untouched by this
    # row: no spec_fun taking an array param has been measured yet, so
    # `lifted_args` leaves that case as `args` did before, a pre-existing
    # gap this row does not claim to close).
    for fd in fdecls:
        f = _match_spec_fun(fd, task.get("spec_funs", []), record)
        if f is None:
            record.warnings.append(
                f"lift_check: no lifted spec_fun matches closure function {fd.name!r}")
            continue
        name = f"L_fun_{f['name']}"
        lemma_names.append(name)
        ps = ", ".join(f"{p.name}: {_lemma_param_type(p.type)}" for p in fd.params)
        args = ", ".join(p.name for p in fd.params)
        fd_views = _fn_param_views(fd.params)
        lifted_args = ", ".join(_view_text(p.name, fd_views) for p in fd.params)
        nat_clause = _and([f"{p.name} >= 0" for p in fd.params if _is_nat_type(p.type)])
        p_src = _conj_text([sp.expr for sp in fd.specs if isinstance(sp, RequiresClause)],
                           rename)
        lines.append(f"lemma {name}({ps})")
        if nat_clause != "true":
            lines.append(f"  requires {nat_clause}")
        if p_src != "true":
            lines.append(f"  requires {p_src}")
        fn_src = rename.get(fd.name, fd.name)
        lines.append(f"  ensures {fn_src}({args}) == {f['name']}({lifted_args})")
        lines.append("{ }")
        lines.append("")

    # Both L_req/L_ens/L_inv compare a SOURCE-clause conjunction (source's
    # own names) against a LIFTED-clause conjunction (task's own names,
    # printed straight from the JSON by `_t_expr`); the lemma signature
    # has to pick one name per variable, so it uses the TASK's names
    # (matching what `_t_expr` already prints) and `crename` translates
    # the SOURCE clause text onto those same names (`_clause_rename`:
    # positional param/return correspondence, `record.rename_map` wins
    # where a real rename was logged).
    crename = _clause_rename(source, task, record, rename)
    # Decision 22 "modifies-param": `crename[array_mutation.name]` (set by
    # `_clause_rename` above, positionally, like every other param) stays
    # the PARAMETER's own task name -- exactly right for `old(a[k])`,
    # which this lemma's own printing leaves untouched (`_print_expr`'s
    # `Old` case just recurses; nothing in a plain lemma body mutates `a`,
    # so Dafny reads `old(a[k])` as `a[k]` regardless). A NON-old
    # occurrence of `a` means the RETURN instead; since `_print_expr`
    # cannot tell the two apart through one flat rename dict (the source
    # text repeats the same identifier for both), `_split_array_post_state`
    # rewrites every non-old occurrence in the ensures/invariant Expr
    # TREES to a synthetic name first, and this is the one place that
    # synthetic name's translation is declared.
    post_ident = (f"__t22_{array_mutation.name}_post" if mutated_param is not None else None)
    if post_ident is not None:
        crename[post_ident] = ret["name"]
    src_params = list(source.params)
    task_params = task["params"]
    lem_ps = ", ".join(f"{tp['name']}: {_lemma_param_type(sp.type)}"
                       for sp, tp in zip(src_params, task_params))

    # Decision 22's own fixes on the LIFTED side (`lift_rewrite`'s
    # `array-length-return-ensures`, prepended to the task's own ensures,
    # and `_add_array_length_invariants`, prepended to every loop that
    # touches the mutated seq) both state `len(<something>) == <the
    # array's own fixed length>` -- a fact the SOURCE never has to state
    # (a real array's `.Length` is fixed by construction) and so an
    # asymmetry an L_ens/L_inv `<==>` would otherwise read as a genuine
    # disagreement. Granted via `requires` (the same technique
    # `nat_clause` already uses below, for the identical reason), it
    # lets Dafny discharge the LIFTED side's extra conjunct as
    # already-known rather than needing it independently derived.
    # `size_text`: the printed Dafny text of the array's own fixed
    # length, shared by both facts below (`ret['name']` for L_ens -- the
    # ONLY decision-22 name L_ens's signature ever declares -- and
    # `mutated_len_tname`, return OR loop-local, for L_inv, since a
    # "alloc-fill" local has not been copied to the return yet at any
    # loop that still mutates it).
    length_fact = "true"
    ens_length_fact = "true"
    mutated_len_tname = None
    if array_mutation is not None:
        mutated_len_tname = (ret["name"] if mutated_param is not None
                             else crename.get(array_mutation.name, array_mutation.name))
        if mutated_param is not None:
            size_text = f"{crename[array_mutation.name]}.Length"
        else:
            size_text = None
            for _line, _name, _rhs in lift_classify._alloc_bindings(source):
                if _name == array_mutation.name and lift_classify._looks_like_array_new(_rhs):
                    _parsed = lift_classify._new_array_size_text(_rhs)
                    if _parsed is not None:
                        import lift_rewrite
                        size_ast = lift_rewrite._parse_size_expr(_parsed[1])
                        size_text = _print_expr(size_ast, crename)
                    break
        if size_text is not None:
            length_fact = f"{mutated_len_tname}.Length == {size_text}"
            ens_length_fact = f"{ret['name']}.Length == {size_text}"

    # (4) L_req.
    lemma_names.append("L_req")
    type_clause = _and([f"{tp['name']} >= 0" for sp, tp in zip(src_params, task_params)
                        if _is_nat_type(sp.type)])
    src_req_conj = _conj_text(
        [sp.expr for sp in source.specs if isinstance(sp, RequiresClause)], crename)
    lines.append(f"lemma L_req({lem_ps})")
    lines.append(f"  ensures ({lifted_req}) <==> ({_and([type_clause, src_req_conj])})")
    lines.append("{ }")
    lines.append("")

    # (5) L_ens.
    lemma_names.append("L_ens")
    ret_lemma_ty = _lemma_param_type(ret_type_src)
    lem_ps_ens = lem_ps + (", " if lem_ps else "") + f"{ret['name']}: {ret_lemma_ty}"
    ens_exprs = [sp.expr for sp in source.specs if isinstance(sp, EnsuresClause)]
    ens_exprs = _strip_fresh_src(ens_exprs, fresh_ret_name)
    if post_ident is not None:
        ens_exprs = [_split_array_post_state(e, array_mutation.name, post_ident) for e in ens_exprs]
    src_ens_conj = _conj_text(ens_exprs, crename)
    if pair_src is not None:
        # Row 29's own analogue: a `nat` COMPONENT states its own
        # non-negativity on its own projection, `r.0`/`r.1`, never on
        # `r` itself (a pair has no order, SPEC.md) -- ANDed together
        # when both happen to be `nat` (measured population: 6 of the
        # 785 DafnyBench programs' `(nat, nat)` shape).
        ret_type_clause = _and(
            [f"{ret['name']}.{i} >= 0" for i, p in enumerate(pair_src) if _is_nat_type(p.type)])
    else:
        ret_type_clause = (f"{ret['name']} >= 0" if _is_nat_type(ret_type_src) else "true")
    lifted_ens = _t_conj(task.get("ensures", []), views)
    hint_lines = []
    for fd in fdecls:
        f = _match_spec_fun(fd, task.get("spec_funs", []), record)
        if f is None:
            continue
        binders = ", ".join(f"{p.name}: {_lemma_param_type(p.type)}" for p in fd.params)
        args = ", ".join(p.name for p in fd.params)
        fd_views = _fn_param_views(fd.params)
        lifted_args = ", ".join(_view_text(p.name, fd_views) for p in fd.params)
        nat_clause = _and([f"{p.name} >= 0" for p in fd.params if _is_nat_type(p.type)])
        p_src = _conj_text([sp.expr for sp in fd.specs if isinstance(sp, RequiresClause)],
                           rename)
        guard = _and([nat_clause, p_src])
        fn_src = rename.get(fd.name, fd.name)
        # `L_fun_{f['name']}(args)`: L_fun's OWN signature (`ps` above, in
        # its own defining loop) is typed to the SOURCE's params too, so
        # calling it with raw `args` is right, unlike the direct
        # `f['name'](...)` call just before it, which needs `lifted_args`.
        hint_lines.append(
            f"  forall {binders} | {guard} ensures "
            f"{fn_src}({args}) == {f['name']}({lifted_args}) {{ L_fun_{f['name']}({args}); }}")
    lines.append(f"lemma L_ens({lem_ps_ens})")
    lines.append(f"  requires {_and([lifted_req, ens_length_fact])}")
    lines.append(f"  ensures ({_and([ret_type_clause, ens_length_fact, src_ens_conj])}) <==> ({lifted_ens})")
    lines.append("{")
    lines.extend(hint_lines)
    lines.append("}")
    lines.append("")

    # (6) L_inv_k / decreases-equality per loop, pre-order.
    src_loops = _walk_source_loops(source)
    task_loops = _task_loops(task["body"])
    task_loop_scopes = _task_loop_scopes(task["body"])
    task_var_inits = _task_var_inits(task["body"])
    for k, (loop, scope) in enumerate(src_loops):
        lemma_names.append(f"L_inv_{k}")
        # `scope` (from `_walk_source_loops`) is seeded with `source.params`
        # and only ever appended to, so its first len(source.params) entries
        # are exactly the params (task-named below); anything after is a
        # true local, declared before this loop. Its printed name is NOT
        # always its source name identity: `crename` (via `_param_overlay`'s
        # rename_map fallback) is what the invariant TEXT is already
        # translated through (`src_inv` below), so the lemma's own
        # parameter LIST must use the same translation or a local that
        # collided into a real rename (measured: gcdI's own local `x`,
        # renamed `x_v` because the closure function `gcd(x, y)` claimed
        # `x` first) declares one name and the ensures clause references
        # another -- an undefined identifier, which reads as `tool_error`
        # on every lemma in the file, not just this one. Integrator fix
        # 2026-09-05, found via 05_PVS_gcdI's real checker output.
        #
        # `crename`'s flat, whole-clause rename_map lookup is not enough
        # for a LOOP LOCAL specifically: when a source name (e.g. `i`) is
        # reused for both a quantifier binder elsewhere in the method AND
        # this loop's own local variable, the renamer's rename_map holds
        # one bare entry for whichever it renamed first and a `#`-suffixed
        # entry for the second (LIFTER-DESIGN.md section 4.8), and
        # `crename` always resolves to the bare one -- not necessarily
        # this loop's local (measured: Clover_min_array's `i`, bare entry
        # `i_v` is the ensures clauses' quantifier binder, `i#local` ->
        # `i_v2` is the actual loop variable the lifted invariant text
        # names; using the bare entry named the lemma parameter `i_v` while
        # the printed lifted invariant said `i_v2`, an undefined
        # identifier). `_task_loop_scopes` reads the task's own local names
        # off its body in the same declaration order the source locals are
        # walked in, so `loop_crename` overrides just THIS loop's locals
        # with what the task JSON actually calls them, positionally --
        # exact, not a name-collision guess.
        locals_in_scope = list(scope[len(src_params):])
        true_local_names = task_loop_scopes[k] if k < len(task_loop_scopes) else []
        # A desugared `for` (decision 15, `for-desugared`) PREPENDS a
        # range-bound local (`h_t := <hi>`) that has no source-side
        # declaration at all -- only the loop's own counter, appended
        # last, corresponds to the source's own iteration variable. Align
        # from the END so the source's real locals pair with their real
        # task counterparts regardless of how many desugaring-only extras
        # come first (measured: dafny-synthesis_task_id_62's FindSmallest,
        # task scope `[h, i_v2]` against source scope `[i]` -- a left zip
        # would wrongly pair `i` with `h`). Extras with no source
        # counterpart are still real lemma parameters (the invariant text
        # references them, e.g. `i_v2 <= h`): decision 15's desugaring
        # always types them `int`.
        # Row 29 (2026-09-09, SPEC.md "Pairs (v1)"): a pair method's two
        # out-parameters are never in `locals_in_scope` (`_walk_source_
        # loops` seeds its scope from `source.params` alone, never
        # `source.returns` -- deliberately unchanged here, touching that
        # seed would also perturb the from-the-end `extra`/`aligned_names`
        # alignment below for every OTHER row's already-measured
        # programs), yet a loop that computes DIRECTLY into its own out-
        # parameters (no separate `lo`/`hi`-style locals -- CalDiv's own
        # shape: `x, y := 0, 191; while ... invariant 0 <= y && ...`)
        # references them there by name. `rewrite()` unconditionally
        # emits BOTH pair locals' own `var` declarations as the FIRST two
        # statements of the lifted body (before any source statement is
        # ever lifted), so `true_local_names[:2]` is guaranteed to be
        # their own task names for every loop this walk reaches,
        # regardless of nesting -- stripped off the front here so the
        # existing end-alignment heuristic runs on the REMAINING locals
        # exactly as it always has (identical to before this row for a
        # single-return task, `pair_src is None`), and reattached
        # explicitly, both to the lemma's own parameter list (`full_names`
        # /`full_types`, so the name is actually declared) and to
        # `loop_crename` (so the SOURCE clause text, which invariably
        # names the out-parameter directly, prints that same name back --
        # not `crename`'s own ensures-level `r.0`/`r.1` projection, wrong
        # here since `r` is not kept in sync during the loop, only
        # combined at the body's own exits, SPEC.md's "stays the local
        # a/b inside the body").
        pair_task_names = true_local_names[:2] if pair_src is not None else []
        rest_local_names = true_local_names[2:] if pair_src is not None else true_local_names
        extra = len(rest_local_names) - len(locals_in_scope)
        extra_names = rest_local_names[:extra] if extra > 0 else []
        aligned_names = rest_local_names[extra:] if extra > 0 else rest_local_names
        # Row (2026-09-12): each `extra_names` entry is a for-desugared
        # range-bound local with no source-side value at all -- `_task_
        # var_inits` recovers the one init expr decision 15's rewrite
        # always gives it, so the lemma can require it rather than leave
        # it a free int (see that helper's own docstring for why the
        # obligation is otherwise unprovable, not merely unautomated).
        extra_fact_list = [f"{n} == {_t_expr(task_var_inits[n], views)}"
                           for n in extra_names if n in task_var_inits]
        extra_fact = _and(extra_fact_list)
        loop_crename = dict(crename)
        for p, true_name in zip(locals_in_scope, aligned_names):
            loop_crename[p.name] = true_name
        if pair_src is not None and len(pair_task_names) == 2:
            loop_crename[pair_src[0].name] = pair_task_names[0]
            loop_crename[pair_src[1].name] = pair_task_names[1]
        full_names = ([tp["name"] for tp in task_params]
                      + pair_task_names
                      + extra_names
                      + [loop_crename.get(p.name, p.name) for p in locals_in_scope]
                      + [ret["name"]])
        full_types = ([sp.type for sp in src_params]
                      + ([pair_src[0].type, pair_src[1].type] if pair_src is not None else [])
                      + [Type(line=loop.line, kind="int", name=None) for _ in extra_names]
                      + [p.type for p in locals_in_scope] + [ret_type_src])
        ps_inv = ", ".join(f"{n}: {_lemma_param_type(t)}"
                           for n, t in zip(full_names, full_types))
        nat_clause = _and([f"{n} >= 0" for n, t in zip(full_names, full_types)
                          if _is_nat_type(t)])
        # decision 22: only usable when THIS loop's own lemma parameters
        # actually declare the mutated array's name (a loop textually
        # before its allocation would not, though none of the shapes
        # this row maps have one).
        this_length_fact = length_fact if (array_mutation is not None
                                           and mutated_len_tname in full_names) else "true"
        inv_exprs = [sp.expr for sp in loop.specs if isinstance(sp, InvariantClause)]
        if post_ident is not None:
            # decision 22: a mid-loop, non-`old` `a[k]` means the return's
            # CURRENT (so-far) value, same as in the ensures clause above.
            inv_exprs = [_split_array_post_state(e, array_mutation.name, post_ident) for e in inv_exprs]
        src_inv = _conj_text(inv_exprs, loop_crename)
        lifted_inv = (_t_conj(task_loops[k].get("invariants", []), views)
                     if k < len(task_loops) else "true")
        # Same reason as L_ens's forall hint (section 9 item 5, measured):
        # Dafny will not apply a spec_fun's equivalence lemma unprompted.
        # Here the loop's scope variables are already concrete lemma
        # parameters (not universally quantified), so a direct call
        # suffices in place of a forall.
        fd_names = {fd.name for fd in fdecls}
        inv_calls = _find_fun_calls(inv_exprs, fd_names)
        # Domain guards of every closure-function call embedded DIRECTLY in
        # the source invariant text (as opposed to one only invoked, under
        # its own guard, from a hint below): the source's own conjunction
        # calls e.g. `Potencia(b, e)` or `power(x, y0 - y)` unconditionally,
        # so Dafny requires that call's argument in the callee's domain --
        # `b >= 0`, `y0 - y >= 0` -- for the ensures clause to be well
        # -formed at all, for ANY (params, locals) satisfying just
        # `requires`. This is not always a plain nat-typing fact (`y0`,
        # `y` are bare `int` with a `requires y0 >= 0` in A8_Q1; nothing
        # here is typed `nat`), so it cannot be read off `_is_nat_type`;
        # it is exactly `_call_guard`'s computation, reused from the hint
        # loop below. The source's own successful verification (decision
        # 12) already proved this guard holds at every real loop head, so
        # naming it here states a fact the source's typing/domain
        # discipline established, per decision 4, not one this module
        # invents. Integrator fix 2026-09-06: seven L_inv_0 failures (one
        # of them the pre-existing `nat_clause`-only `b` case, still
        # covered here since `_call_guard` includes each callee param's
        # own nat-ness; six others -- A8_Q1, power, uiowa fibonacci,
        # TuringFactorial, climbing-stairs, rosetta factorial -- have no
        # nat-typed variable in play at all: "function precondition could
        # not be proved" / "value does not satisfy the subset constraints
        # of 'nat'" on the embedded call, confirmed from the dafny text
        # log on each, fixed by this same one-line generalisation).
        call_guard_list = []
        for call in inv_calls:
            fd_match = next(fd for fd in fdecls if fd.name == call.fn.name)
            g = _call_guard(fd_match, call, loop_crename)
            if g not in call_guard_list:
                call_guard_list.append(g)
        call_guards = _and(call_guard_list)
        inv_hints = []
        for call in inv_calls:
            fd_match = next(fd for fd in fdecls if fd.name == call.fn.name)
            f = _match_spec_fun(fd_match, task.get("spec_funs", []), record)
            if f is None:
                continue
            args = ", ".join(_print_expr(a, loop_crename) for a in call.args)
            guard = _call_guard(fd_match, call, loop_crename)
            call_line = f"L_fun_{f['name']}({args});"
            if guard == "true":
                inv_hints.append(f"  {call_line}")
            else:
                inv_hints.append(f"  if {guard} {{ {call_line} }}")
        lines.append(f"lemma L_inv_{k}({ps_inv})")
        # `nat_clause`/`call_guards` also belong in `requires`, not only
        # inside the ensures' left conjunct: a local that is nat-typed in
        # the source but never reassigned inside THIS loop gets no
        # `nat-invariant-added` clause on the lifted side (decision 5 only
        # appends for an ASSIGNED nat local), so the lifted conjunction on
        # its own says nothing about it -- leaving it a free, unconstrained
        # int lemma parameter makes the <==> false for a witness where it
        # is negative (measured: gcdI-adjacent 04_pot's own `b`, assigned
        # once before the loop from a nat param and never touched again,
        # produced a genuine, provably-false equivalence, not merely a
        # hard-to-automate one -- confirmed by patching just this line and
        # re-verifying: 11 verified, 0 errors, same file, same lemmas).
        # Integrator fix 2026-09-05; generalised to `call_guards` 2026-09-06
        # (see the comment above `call_guard_list`). Both are placed FIRST
        # in the ensures' left conjunct, ahead of `src_inv`, so Dafny's
        # left-to-right `&&` short-circuit (the same discipline L_req
        # already relies on) establishes them before `src_inv`'s embedded
        # calls are evaluated.
        lines.append(f"  requires {_and([lifted_req, nat_clause, call_guards, this_length_fact, extra_fact])}")
        lines.append(f"  ensures ({_and([nat_clause, call_guards, this_length_fact, extra_fact, src_inv])}) <==> ({lifted_inv})")
        if inv_hints:
            lines.append("{")
            lines.extend(inv_hints)
            lines.append("}")
        else:
            lines.append("{ }")
        lines.append("")

        dec_specs = [sp for sp in loop.specs if isinstance(sp, DecreasesClause)]
        loop_key = f"loop@{loop.line}"
        single_src_dec = (dec_specs and not isinstance(dec_specs[0].exprs, Star)
                          and len(dec_specs[0].exprs) == 1)
        single_lifted_dec = k < len(task_loops) and "decreases" in task_loops[k]
        if single_src_dec and single_lifted_dec:
            name = f"L_dec_{k}"
            lemma_names.append(name)
            src_dec = _print_expr(dec_specs[0].exprs[0], loop_crename)
            lifted_dec = _t_expr(task_loops[k]["decreases"], views)
            lines.append(f"lemma {name}({ps_inv})")
            dec_req = _and([this_length_fact, extra_fact])
            if dec_req != "true":
                lines.append(f"  requires {dec_req}")
            lines.append(f"  ensures ({src_dec}) == ({lifted_dec})")
            lines.append("{ }")
            lines.append("")
            record.decreases_origin.setdefault(loop_key, "checked")
        else:
            record.decreases_origin.setdefault(loop_key, "guess")

    return "\n".join(lines) + "\n", lemma_names


def build_checker(task: dict, source: MethodDecl, closure: tuple,
                   record: LiftRecord) -> str:
    """Build the section-9 checker `.dfy` text for `task` against `source`.

    Input: the t task JSON, the source method's AST (its call-graph
    closure, so spec_funs and helper functions can be alpha-renamed too),
    and the `LiftRecord` so far (read for `rename_map`/`decreases_origin`
    -- e.g. which loops got a `projected` vs. `guess:sum` measure, since
    the per-loop decreases lemma is only emitted for single-expression
    measures per section 9 item 6).

    Output: the checker file text, containing (section 9, in order): (1)
    the source's call-graph closure alpha-renamed by appending `_src` to
    every declaration name (params and locals keep their names); (2) the
    lifted task lowered via `lower_dafny.lower(task, task["body"])`,
    unmodified; (3) one `L_fun_<name>` lemma per spec_fun, with the
    `forall`-statement hint section 9 item 5 measured as required (without
    it, Dafny does not apply the spec_fun-equivalence lemma unprompted:
    10 verified 2 errors on Fatorial without the hint, 12 verified 0
    errors with it); (4) the `L_req` lemma; (5) the `L_ens` lemma; (6) per
    loop in pre-order, an `L_inv_<k>` lemma and (single-expression
    measures only) its decreases-equality lemma.

    This function only builds text; it never invokes dafny."""
    text, _ = _build_checker_parts(task, source, closure, record)
    return text


# ===========================================================================
# build_differential (section 10(a), plus 18.5's third-arm printing).
# ===========================================================================

def _dafny_literal(v, ty: str) -> str:
    if ty == "bool":
        return "true" if v else "false"
    if ty == "int":
        return str(v)
    if ty == "seq":
        return "[" + ", ".join(str(x) for x in v) + "]"
    raise ValueError(f"lift_check._dafny_literal: unknown t type {ty!r}")


def _param_names_types(task: dict) -> list:
    return [(p["name"], p["type"]) for p in task["params"]]


def build_differential(task: dict, source: MethodDecl, closure: tuple) -> str:
    """Build the section-10(a) differential harness `.dfy` text for `task`
    against `source`.

    Output: Dafny source declaring `<Method>_src` (the source's call-graph
    closure, alpha-renamed as in `build_checker`) and the lowered
    `<Method>` (via `lower_dafny.lower`), plus a `method Main()` that:
    for every point of `interp.domain(task)` satisfying the lifted
    `requires`, calls both methods, compares the results, and prints
    `points=N bad=M`; and (section 18.5) also prints the source's value at
    every point so `lift_check.check` can compare those, point by point,
    against `interp.Reference` on the lifted task, independent of this
    Dafny-vs-Dafny comparison. Seq-typed params are emitted as Dafny seq
    literals in the harness (section 10(a)). This function only builds
    text; the caller runs it with `dafny run FILE --no-verify` (section
    10(a): sound as a bounded test of VALUES ONLY -- invariants,
    decreases, and asserts are ghost and never execute, so this arm alone
    proves nothing about section 9's territory).

    The point list is `interp.Reference(task).points`: every point of
    `interp.domain(task, ...)` that already satisfies the lifted
    `requires` (`interp.Reference.__init__`'s own filter), which is what
    section 9 item "the same points interp's witness search uses" means.
    Computed fresh here (a pure function of `task`, so a caller such as
    `check` that already built its own `interp.Reference(task)` for the
    twin gets the identical point list back, just recomputed)."""
    points = interp.Reference(task).points
    return _build_differential_with_points(task, source, closure, points)


def _build_differential_with_points(task: dict, source: MethodDecl,
                                    closure: tuple, points: list) -> str:
    """Section 10(a), item (a)'s data-not-statements form (integrator fix
    2026-09-06): the OLD Main emitted one `{ var srcv := ...; ...}` block
    PER POINT, so N points meant N call statements for `dafny run` to
    parse and compile; measured on dafny-synthesis_task_id_801
    (CountEqualNumbers, 3 int params, interp's own domain is exactly 2048
    points): `dafny run --no-verify` on the old form did not finish inside
    a 180s wall timeout (no `points=`/`bad=` line printed at all). This
    form instead emits the points as DATA -- a `seq` of tuples (one tuple
    field per param; a bare `seq<T>` when there is exactly one param, no
    tuple needed) -- walked by ONE `while` loop that makes the two calls
    generically; `dafny run --no-verify` never proves anything about the
    loop (verification is skipped), so no invariant or decreases is
    needed for the loop to compile and run. Measured on the SAME task,
    same 2048 points, same machine: 8.7s compile+run (see
    DIFF_MAX_POINTS's own comment for the full before/after numbers this
    justifies)."""
    rename = _closure_rename_map(source, closure)
    fdecls = [d for d in closure if isinstance(d, FunctionDecl)]
    mdecls = [d for d in closure if isinstance(d, MethodDecl)]

    lines = ["// Section 10(a) / 18.5 differential harness: source vs. "
             "lifted, plus the source's printed values for the interp "
             "third arm.", ""]
    for fd in fdecls:
        lines.extend(_print_function_decl(fd, rename))
    for md in mdecls:
        lines.extend(_print_method_decl(md, rename))
    # Unlike the checker file (which never needs the source's own
    # STATEMENTS, section 9's closing paragraph), the differential harness
    # actually RUNS the source method, so it needs `source` itself printed
    # here too, alpha-renamed the same way as the rest of the closure.
    lines.extend(_print_method_decl(source, rename))
    lines.append(lower_dafny.lower(task, task["body"]))

    src_name = rename.get(source.name, source.name)
    lift_name = task["name"].capitalize()
    names_types = _param_names_types(task)
    n_params = len(names_types)

    # Row 28 (2026-09-09, SPEC.md "Strings as sequences of code points
    # (v1)"): `dafny run` prints/compares a `string`/`char` value in ITS
    # OWN shape ("abc", a bare character with no quoting), never t's
    # bracketed `seq<int>`/plain int (measured: tprint.dfy in the task's
    # own scratch notes -- `Id("abc")` prints `abc`, not `[97, 98, 99]`),
    # so `src_value_expr` below is always converted to t's shape BEFORE
    # printing/comparing, one bounded `seq(...)` comprehension per string
    # (always safe, `char as int` never fails) or one `as int` per char.
    ret_type_src0 = source.returns[0].type if source.returns else None

    def _ret_view(expr: str) -> str:
        """The source's own return value `expr`, converted to t's own
        shape for printing/comparing against `liftv`: decision 22's
        `array<int>` -> `expr[..]` (a seq view, unchanged from before this
        row); row 28's `string`/`seq<char>` -> a bounded `seq(...)`
        comprehension casting every element to `int` (always safe: `char
        as int` never fails, so this needs no range guard the way the
        PARAMETER direction, below, does); row 28's `char` -> `expr as
        int` (likewise always safe). Anything else is unchanged."""
        if ret_type_src0 is None:
            return expr
        is_seq_of_char = (ret_type_src0.kind == "seq" and len(ret_type_src0.args) == 1
                          and ret_type_src0.args[0].kind == "char")
        if ret_type_src0.kind == "array":
            return f"{expr}[..]"
        if ret_type_src0.kind == "string" or is_seq_of_char:
            return (f"(seq(|{expr}|, (k: int) requires 0 <= k < |{expr}| "
                     f"=> {expr}[k] as int))")
        if ret_type_src0.kind == "char":
            return f"({expr} as int)"
        return expr

    lines.append("method Main() {")
    if n_params == 0:
        # interp's domain for a 0-param method is degenerate (>= 1 trivial
        # point, never large: LIFTER-DECISIONS.md row 19, interp's own
        # domain), so the direct-call form costs nothing extra and needs
        # no data/loop machinery to represent zero-length tuples.
        lines.append("  var bad := 0;")
        lines.append("  var points := 0;")
        for i in range(len(points)):
            lines.append("  {")
            lines.append(f"    var srcv := {src_name}();")
            src_value_expr = _ret_view("srcv")
            lines.append(f"    var liftv := {lift_name}();")
            lines.append("    points := points + 1;")
            lines.append(f'    print {i}, " ", {src_value_expr}, " ", liftv, "\\n";')
            lines.append(f"    if {src_value_expr} != liftv {{ bad := bad + 1; }}")
            lines.append("  }")
    else:
        if n_params == 1:
            n0, ty0 = names_types[0]
            pts_ty = lower_dafny.TYPES[ty0]
            lit_list = [_dafny_literal(env0[n0], ty0) for env0, _real in points]
            call_args = "pts[i]"
        else:
            field_tys = ", ".join(lower_dafny.TYPES[ty] for _n, ty in names_types)
            pts_ty = f"({field_tys})"
            lit_list = []
            for env0, _real in points:
                fields = ", ".join(_dafny_literal(env0[n], ty) for n, ty in names_types)
                lit_list.append(f"({fields})")
            call_args = ", ".join(f"pts[i].{j}" for j in range(n_params))
        # Decision 1 (array-readonly-as-seq): the SOURCE method takes
        # array<int> where the task takes seq, so each such point is
        # materialised as a fresh array before the source call; the lifted
        # call keeps the seq. Measured 2026-09-06: without this every one of
        # the 16 array programs failed to resolve ("expected array<int>,
        # found seq<int>") and no tally was printed.
        array_view = frozenset(tp["name"] for sp, tp in zip(source.params, task["params"])
                               if sp.type is not None and sp.type.kind == "array")
        # Row 28: the SOURCE method takes `string`/`char` where the task
        # takes `seq`/`int`; each such point is converted before the
        # source call (a string via the same bounded `seq(...)`
        # comprehension `_ret_view` uses, a char via a plain `as char`),
        # the lifted call keeping the task's own `seq`/`int` shape
        # unchanged. Safe by construction: `char-param-guard`/
        # `string-elements-requires` (lift_rewrite.py) already keep every
        # sampled point's value(s) in `[0, 1114111]`, the one thing that
        # makes `as char` not crash (measured, `trun.dfy`).
        string_view = frozenset(tp["name"] for sp, tp in zip(source.params, task["params"])
                                if sp.type is not None
                                and (sp.type.kind == "string"
                                     or (sp.type.kind == "seq" and len(sp.type.args) == 1
                                         and sp.type.args[0].kind == "char")))
        char_view = frozenset(tp["name"] for sp, tp in zip(source.params, task["params"])
                              if sp.type is not None and sp.type.kind == "char")
        point_exprs = ["pts[i]"] if n_params == 1 else [f"pts[i].{j}" for j in range(n_params)]
        src_args = []
        materialise = []
        # Decision 22: the ONE array this source method mutates in place
        # under `modifies` (if any), re-derived from the same shared
        # detector the checker/rewriter use. When it applies, the source
        # call is a bare STATEMENT (a "modifies-param" method has NO
        # Dafny return to assign) and the value to compare is the
        # materialised argument array's post-call state, `arr{j}[..]`,
        # not a `srcv` that was never declared.
        import lift_classify
        array_mutation, _ = lift_classify.find_array_mutation(source, closure)
        mutated_arg_var = None
        for j, (pn, _ty) in enumerate(names_types):
            pe = point_exprs[j]
            if pn in array_view:
                materialise.append(f"    var arr{j} := new int[|{pe}|];")
                materialise.append(f"    var k{j} := 0;")
                materialise.append(f"    while k{j} < |{pe}| {{ arr{j}[k{j}] := {pe}[k{j}]; k{j} := k{j} + 1; }}")
                src_args.append(f"arr{j}")
                if array_mutation is not None and array_mutation.kind == "modifies-param" \
                        and pn == array_mutation.name:
                    mutated_arg_var = f"arr{j}"
            elif pn in string_view:
                materialise.append(
                    f"    var s{j} := seq(|{pe}|, (k: int) requires 0 <= k < |{pe}| "
                    f"=> {pe}[k] as char);")
                src_args.append(f"s{j}")
            elif pn in char_view:
                src_args.append(f"({pe} as char)")
            else:
                src_args.append(pe)
        lines.append(f"  var pts: seq<{pts_ty}> := [{', '.join(lit_list)}];")
        lines.append("  var bad := 0;")
        lines.append("  var points := 0;")
        lines.append("  var i := 0;")
        lines.append("  while i < |pts| {")
        lines.extend(materialise)
        if mutated_arg_var is not None:
            # decision 22 "modifies-param": no source return at all -- the
            # mutated argument array IS the observable, post-call.
            lines.append(f"    {src_name}({', '.join(src_args)});")
            src_value_expr = f"{mutated_arg_var}[..]"
        else:
            lines.append(f"    var srcv := {src_name}({', '.join(src_args)});")
            # decision 22 "alloc-fill" (array) / row 28 (string, char):
            # the source's own return type may not be t's own shape;
            # `_ret_view` converts it to one that compares against
            # `liftv` correctly.
            src_value_expr = _ret_view("srcv")
        lines.append(f"    var liftv := {lift_name}({call_args});")
        lines.append("    points := points + 1;")
        lines.append(f'    print i, " ", {src_value_expr}, " ", liftv, "\\n";')
        lines.append(f"    if {src_value_expr} != liftv {{ bad := bad + 1; }}")
        lines.append("    i := i + 1;")
        lines.append("  }")
    lines.append('  print "points=", points, " bad=", bad, "\\n";')
    lines.append("}")
    lines.append("")
    return "\n".join(lines) + "\n"


# ===========================================================================
# dafny invocation and output parsing (own copy: resolution only reused
# from verifiers/dafny.py, never its certificate-scanning logic).
# ===========================================================================

_RESULT_HEAD = re.compile(r"^Results for (\S+) \(([^)]*)\)\s*$")
_RESULT_OUTCOME = re.compile(r"^\s+Overall outcome:\s*(\S+)")
_FINISH_RE = re.compile(r"finished with (\d+) verified, (\d+) error")

_DAFNY_OUTCOME = {
    "Correct": Outcome.VERIFIED,
    "IncorrectProof": Outcome.UNPROVED,
    "Errors": Outcome.UNPROVED,
    "OutOfResource": Outcome.TIMEOUT,
    "TimedOut": Outcome.TIMEOUT,
    "Inconclusive": Outcome.TOOL_ERROR,
    "Skipped": Outcome.TOOL_ERROR,
}


def _run_dafny(args: list, timeout_s: float):
    """(exit_code, combined stdout+stderr). exit_code is `_TIMEOUT_SENTINEL`
    on the wall backstop, per every dafny call in this project needing one
    (house rule)."""
    if not DAFNY:
        raise RuntimeError(
            "dafny not found: set T_DAFNY or install to ~/.local/dafny/dafny "
            "(see verifiers/dafny.py's own resolution, reused here)")
    try:
        p = subprocess.run([DAFNY] + args, capture_output=True, text=True,
                           timeout=timeout_s)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") if isinstance(e.stdout, str) else ""
        err = (e.stderr or "") if isinstance(e.stderr, str) else ""
        return _TIMEOUT_SENTINEL, out + err


def _symbol_outcomes(out: str) -> list:
    lines = out.splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        m = _RESULT_HEAD.match(lines[i])
        if m:
            outcome = None
            for j in range(i + 1, min(i + 6, len(lines))):
                om = _RESULT_OUTCOME.match(lines[j])
                if om:
                    outcome = om.group(1)
                    break
            blocks.append((m.group(1), m.group(2), outcome))
        i += 1
    return blocks


def _extract_warnings(out: str) -> list:
    """Every `Warning` line dafny printed, verbatim (section 18.1:
    "Warnings are recorded in the sidecar and ignored" -- recorded here,
    ignored by every pass/fail decision in this module)."""
    return [line.strip() for line in out.splitlines() if "Warning" in line]


def _verify_checker(path: Path, lemma_names: list, timeout_s: float,
                    lowered_name: Optional[str] = None):
    """Runs `dafny verify` on `path`; returns (verdicts: dict[name,str],
    exit_code, all_ok: bool, first_failing_token: str|None,
    warnings: list[str], lowered_verdict: str|None).

    `lowered_name` is the symbol the checker file's lowered `<Method>`
    (item 2 of the file, `lower_dafny.lower`) is printed under. Its own
    Dafny verdict is returned separately as `lowered_verdict`, never
    folded into `verdicts`/`all_ok`/`first_bad`: decision 8 drops hints
    (asserts, lemma calls, function ensures, nat-result facts) the
    lowered method's proof needs, so its own body reading UNPROVED is an
    expected consequence of that decision, not evidence the LIFT is
    wrong (decision 17's "two columns" -- see LiftRecord.lowered_task_
    verdict). Only when EVERY error in the finish line is attributable to
    the lowered method's own body does this function still report
    `all_ok=True`; a genuine lemma failure is unaffected."""
    exit_code, out = _run_dafny(
        ["verify", str(path), "--allow-warnings", "--log-format", "text"],
        timeout_s)
    warnings = _extract_warnings(out)
    verdicts = {}
    if exit_code == _TIMEOUT_SENTINEL:
        for name in lemma_names:
            verdicts[name] = Outcome.TIMEOUT
        lowered_verdict = Outcome.TIMEOUT if lowered_name is not None else None
        return verdicts, exit_code, False, "timeout", warnings, lowered_verdict

    blocks = _symbol_outcomes(out)
    by_name: dict = {}
    for sym, kind, outcome in blocks:
        by_name.setdefault(sym, []).append((kind, outcome))

    all_ok = True
    first_bad = None
    for name in lemma_names:
        entries = by_name.get(name)
        if not entries:
            verdicts[name] = Outcome.TOOL_ERROR
            all_ok = False
            if first_bad is None:
                first_bad = name
            continue
        oc = entries[-1][1]
        mapped = _DAFNY_OUTCOME.get(oc, Outcome.TOOL_ERROR)
        verdicts[name] = mapped
        if mapped != Outcome.VERIFIED:
            all_ok = False
            if first_bad is None:
                first_bad = name

    lowered_verdict = None
    if lowered_name is not None:
        entries = by_name.get(lowered_name)
        if entries:
            lowered_verdict = _DAFNY_OUTCOME.get(entries[-1][1], Outcome.TOOL_ERROR)

    fin = _FINISH_RE.search(out)
    if fin is None:
        all_ok = False
        if first_bad is None:
            first_bad = "no-finish-line"
    else:
        n_errors = int(fin.group(2))
        if n_errors > 0 and first_bad is None:
            # errors the per-lemma scan didn't attribute (e.g. a closure
            # declaration's own well-formedness failed, a printer bug --
            # section 9's "N verified, 0 errors" is checked whole-file).
            # The lowered method's OWN symbol is excluded from this scan:
            # its failure is the kernel's, not the lift's (see docstring).
            culprit = None
            for sym, kind, outcome in blocks:
                if outcome != "Correct" and sym != lowered_name:
                    culprit = sym
                    break
            if culprit is not None:
                first_bad = culprit
                all_ok = False
            elif not (lowered_name is not None and lowered_verdict is not None
                     and lowered_verdict != Outcome.VERIFIED):
                # no lemma is bad and the lowered method isn't the (sole)
                # culprit either -- still an unattributed error.
                first_bad = "unattributed-error"
                all_ok = False
            # else: every error in the file belongs to the lowered task's
            # own kernel proof -- reported via `lowered_verdict`, not here.
    return verdicts, exit_code, all_ok, first_bad, warnings, lowered_verdict


# A `seq<int>` prints as `[1, 2, 3]` (measured: `dafny run`, spaces after
# every comma) -- decision 22's seq-returning tasks are the first ones
# through this harness whose printed VALUE can itself contain spaces, so
# a field is either one bracketed `[...]` token (no nested brackets: t's
# `seq<int>` elements are plain ints) or a bare `\S+` token, never a mix.
_FIELD = r"(\[[^\[\]]*\]|\S+)"
_POINT_RE = re.compile(r"^(\d+) " + _FIELD + r" " + _FIELD + r"\s*$")
_TALLY_RE = re.compile(r"points=(\d+) bad=(\d+)")


def _run_differential(path: Path, timeout_s: float):
    """Runs `dafny run FILE --no-verify`; returns (exit_code,
    printed_points: dict[int, (src_str, lift_str)], points_n, bad_n)."""
    exit_code, out = _run_dafny(["run", str(path), "--no-verify"], timeout_s)
    printed = {}
    for line in out.splitlines():
        m = _POINT_RE.match(line.strip())
        if m:
            printed[int(m.group(1))] = (m.group(2), m.group(3))
    tm = _TALLY_RE.search(out)
    points_n = int(tm.group(1)) if tm else len(printed)
    bad_n = int(tm.group(2)) if tm else -1
    return exit_code, printed, points_n, bad_n, out


def _parse_dafny_seq(printed: str) -> Optional[tuple]:
    """`"[1, 2, 3]"` -> `(1, 2, 3)`; `"[]"` -> `()`; `None` if `printed`
    is not bracket-delimited at all (a plain int/bool value)."""
    s = printed.strip()
    if not (s.startswith("[") and s.endswith("]")):
        return None
    inner = s[1:-1].strip()
    if not inner:
        return ()
    return tuple(int(x.strip()) for x in inner.split(","))


def _dafny_value_matches(printed: str, py_value) -> bool:
    if isinstance(py_value, bool):
        return printed == ("true" if py_value else "false")
    if isinstance(py_value, tuple):
        # decision 22: a seq-typed result (interp.py's own seq representation).
        parsed = _parse_dafny_seq(printed)
        return parsed is not None and parsed == tuple(py_value)
    if isinstance(py_value, int):
        return printed == str(py_value)
    return printed == str(py_value)


# ===========================================================================
# check (the full post-rewrite pipeline, section 2's data-flow line).
# ===========================================================================

def check(task: dict, source: MethodDecl, closure: tuple,
          record: LiftRecord, dfy_path: Path,
          timeout_s: float = DEFAULT_TIMEOUT_S) -> CheckOutput:
    """Run the full post-rewrite pipeline of section 2's data-flow line on
    one lifted method, mutating and returning `record`.

    Input: the t task JSON, the source method AST and its call-graph
    closure, the `LiftRecord` `lift_rewrite.rewrite` produced (mutated in
    place, per `CheckOutput.record`'s docs), a scratch `dfy_path` this
    function may use to write the checker/differential files dafny needs
    to read from disk (a temp file, per `verifiers/dafny.py`'s own
    pattern), and a wall-clock timeout applied to each dafny invocation.

    Steps, in the section-2 order: (1) `fuzz_lower.check_wf(task)` --
    must return `[]`; a non-empty result is `check-wf-failed`, refused
    immediately, nothing below runs. (2) `interp.Reference(task)` -- must
    have `>= 1` point in `.points`; zero points is `interp-no-point`,
    recorded on `record` (not this function's `refusal`: section 5 lists
    it as informational, not a lift refusal). (3) `harness.twin_for(task)`
    -- records `record.twin_rung` and `record.twin_witness`, or (a twin
    refusal: `no-witness`/`no-input`/`real-undefined`/`no-operator`/
    `candidate-budget`) leaves them `None` and records the reason on
    `record` (see `CheckOutput.refusal`'s docs: this is never this
    function's `refusal`). (4) `build_checker` then verify it with dafny
    (`verifiers/dafny.py`-style invocation) -- a failing or timed-out
    lemma is `lift-check-failed` naming that lemma, `record
    .checker_verdicts` filled per lemma regardless. (5) `build_differential`
    then run it (`dafny run FILE --no-verify`) -- any `bad > 0` point is
    `lift-diff-failed` naming the first differing input; `record
    .differential_verdict` set to the "agrees on N points" / "bad=M"
    string either way. (6) the interp third arm (18.5): compare the
    harness's printed source values to `interp.Reference` on the SAME
    domain, point by point; a mismatch here (with step 5 passing) is
    `interp-disagreement`, reported on `record` but pointed at interp or
    at `lower_dafny.lower`, never folded into `lift-diff-failed`
    (18.5's own words); a source method dafny cannot compile (a ghost
    method) skips this arm and `record` says `arm-unavailable`.

    Output: `CheckOutput` (the two `.dfy` texts, the mutated `record`, the
    overall `refusal` if any of steps 1, 4, or 5 failed, and the interp
    arm's point count / first value for section-13-style reporting).

    MAY decide: `lift-check-failed` (lemma named), `lift-diff-failed`
    (input named).

    MAY NOT decide: to repair a failed lift. No retry, no mechanical hint
    injection (`{:induction}`, calling every generated lemma) is ever
    attempted on a failing lemma -- LIFTER-DECISIONS.md decision 18 is
    explicit and unconditional ("Never. The checker never argues for the
    lifter; the row stays refused."); a `lift-check-failed`/`lift-diff
    -failed` row is a bug report against the lifter, not a puzzle this
    function tries to solve."""
    dfy_path = Path(dfy_path)

    # (1) check_wf gate.
    errs = fuzz_lower.check_wf(task)
    if errs:
        refusal = Refusal(reason="check-wf-failed", token="; ".join(errs),
                          line=0, stage="check")
        return CheckOutput(checker_dfy="", differential_dfy="", record=record,
                           refusal=refusal, interp_points=0, interp_first_value=None)

    # (2) interp.Reference.
    ref = interp.Reference(task)
    n_points = len(ref.points)
    first_value = ref.points[0][1] if ref.points else None
    if n_points == 0:
        record.warnings.append("interp-no-point")

    # (3) harness.twin_for.
    twin_body, tag_or_reason, witness = harness.twin_for(task)
    if twin_body is not None:
        record.twin_rung = tag_or_reason
        record.twin_witness = witness
    else:
        record.warnings.append(f"twin-refused:{tag_or_reason}")

    # (4) build the checker and verify it.
    checker_text, lemma_names = _build_checker_parts(task, source, closure, record)
    checker_path = dfy_path.with_name(dfy_path.stem + ".check.dfy")
    checker_path.write_text(checker_text, encoding="utf-8", newline="\n")
    lowered_name = task["name"].capitalize()  # matches lower_dafny.lower's own naming
    t0 = time.monotonic()
    verdicts, exit_code, all_ok, first_bad, warnings, lowered_verdict = _verify_checker(
        checker_path, lemma_names, timeout_s, lowered_name)
    record.checker_verdicts.update(verdicts)
    record.lowered_task_verdict = lowered_verdict
    record.dafny_exit_codes["verify-checker"] = exit_code
    record.warnings.extend(warnings)

    if not all_ok:
        token = first_bad if first_bad is not None else "unknown"
        refusal = Refusal(reason="lift-check-failed", token=token, line=0, stage="check")
        return CheckOutput(checker_dfy=checker_text, differential_dfy="", record=record,
                           refusal=refusal, interp_points=n_points,
                           interp_first_value=first_value)

    # (5) differential run. Section 10(a) is a BOUNDED test either way
    # (agreement on N points is never a proof of identity, design's own
    # words); DIFF_MAX_POINTS bounds it to a point count `dafny run`
    # actually finishes in this project's timeouts (see that constant's
    # comment for the measurement), taking the first N points in interp's
    # own shell order -- the same order `interp.Reference` already
    # produced them in, so this is a prefix, not a resample.
    diff_points = ref.points[:DIFF_MAX_POINTS]
    try:
        diff_text = _build_differential_with_points(task, source, closure, diff_points)
    except (TypeError, KeyError) as exc:
        # Row 30 (2026-09-10): a nested-seq param/return's own JSON type
        # is the compound `{"seq": "seq"}`, not a plain string -- if
        # `lower_dafny.TYPES` (owned by the concurrent nested-lowering
        # work this task's own caution names) does not yet have an entry
        # for it, the lookup itself raises (an unhashable dict key, or a
        # missing one) before `dafny run` is ever invoked. Recorded the
        # same way an unresolvable generated Main already is -- arm-
        # unavailable, never a refusal -- rather than crashing this
        # stage outright; the lemma-based checks above already ran and
        # stand on their own.
        record.differential_verdict = f"arm-unavailable: {type(exc).__name__}: {exc}"
        record.warnings.append("differential build raised before dafny ran (nested-seq type not yet in lower_dafny.TYPES)")
        return CheckOutput(checker_dfy=checker_text, differential_dfy="", record=record,
                           refusal=None, interp_points=n_points,
                           interp_first_value=first_value)
    diff_path = dfy_path.with_name(dfy_path.stem + ".diff.dfy")
    diff_path.write_text(diff_text, encoding="utf-8", newline="\n")
    d_exit, printed, points_n, bad_n, raw_out = _run_differential(diff_path, timeout_s)
    record.dafny_exit_codes["run-differential"] = d_exit
    record.warnings.extend(_extract_warnings(raw_out))

    if d_exit == _TIMEOUT_SENTINEL:
        record.differential_verdict = "timeout"
        refusal = Refusal(reason="lift-diff-failed", token="timeout", line=0, stage="check")
        return CheckOutput(checker_dfy=checker_text, differential_dfy=diff_text,
                           record=record, refusal=refusal, interp_points=n_points,
                           interp_first_value=first_value)

    if bad_n < 0:
        # No tally means the harness itself did not run (a resolution or
        # compile error in the generated Main, measured 2026-09-06 on the 16
        # array-as-seq programs before the array materialisation below was
        # added). That is the arm being unavailable, never evidence that the
        # lifted body differs from the source, so it is recorded, not refused;
        # the census table shows differential_verdict per row.
        first_err = next((ln.strip() for ln in (raw_out or "").splitlines()
                          if "Error" in ln), "no points=/bad= tally printed")
        record.differential_verdict = f"arm-unavailable: {first_err[:160]}"
        record.warnings.append("differential run printed no points=/bad= tally")
        diff_checked = False
    else:
        diff_checked = True

    if diff_checked and bad_n > 0:
        first_bad_i = next((i for i in sorted(printed)
                            if printed[i][0] != printed[i][1]), None)
        env0 = diff_points[first_bad_i][0] if first_bad_i is not None else {}
        record.differential_verdict = f"bad={bad_n} of {n_points} points"
        refusal = Refusal(reason="lift-diff-failed", token=repr(env0), line=0, stage="check")
        return CheckOutput(checker_dfy=checker_text, differential_dfy=diff_text,
                           record=record, refusal=refusal, interp_points=n_points,
                           interp_first_value=first_value)

    # Design section 10(a): "the report says 'agrees on N points'";
    # LIFTER-DECISIONS.md's charge to this fix is "the row must say
    # 'agrees on N points'" where N is a BOUNDED test -- M (`n_points`,
    # the task's full interp point count) names what was bounded away so
    # a capped row is never misread as full-domain agreement.
    #
    # Guarded on `diff_checked`, which it was not until 2026-09-06. The
    # arm-unavailable branch above sets its own verdict and this line then
    # overwrote it, so a run whose harness printed no tally at all came out
    # reading "agrees on 0 of 81 points". Measured over the 785: three
    # methods said that, and all three counted among the ones that pass
    # every check. An arm that did not run has not agreed with anything.
    if diff_checked:
        record.differential_verdict = f"agrees on {points_n} of {n_points} points"

    # (6) interp third arm (18.5), over the SAME capped points the
    # differential run actually executed (`printed`'s indices are
    # positions into `diff_points`, not into the uncapped `ref.points`).
    disagreement = None
    for i, (env0, real) in enumerate(diff_points):
        entry = printed.get(i)
        if entry is None:
            continue
        src_printed, _lift_printed = entry
        if not _dafny_value_matches(src_printed, real):
            disagreement = env0
            break
    if disagreement is not None:
        record.warnings.append(f"interp-disagreement:{disagreement!r}")

    return CheckOutput(checker_dfy=checker_text, differential_dfy=diff_text,
                       record=record, refusal=None, interp_points=n_points,
                       interp_first_value=first_value)


# ===========================================================================
# 18.3: the checker mutation test (T7). Eight seeded faults, each a task
# dict -> corrupted task dict (or None when this task has no site the
# fault applies to), plus a runner that feeds each through `check` and
# reports caught/seeded.
# ===========================================================================

def mut_iff_as_implies(task: dict) -> Optional[dict]:
    """A wrong `<==>`/`==>` reading: the first ensures clause shaped
    `{"op": "==", ...}` between two boolean-looking operands read as
    `implies` instead."""
    t = copy.deepcopy(task)
    for e in t.get("ensures", []):
        if e.get("op") == "==" and len(e.get("args", [])) == 2:
            e["op"] = "implies"
            return t
    return None


def mut_parallel_sequenced(task: dict) -> Optional[dict]:
    """A parallel assignment read as sequential: the first pair of
    consecutive `assign` statements (anywhere in the body, including
    inside a loop) where the second's right-hand side reads the name the
    first just wrote, swapped so the second reads the NEW value."""
    t = copy.deepcopy(task)

    def try_block(stmts):
        for i in range(len(stmts) - 1):
            a, b = stmts[i], stmts[i + 1]
            if "assign" in a and "assign" in b:
                name_a = a["assign"][0]
                if _refs_var(b["assign"][1], name_a):
                    stmts[i], stmts[i + 1] = stmts[i + 1], stmts[i]
                    return True
        for s in stmts:
            if "if" in s and (try_block(s["if"]["then"]) or try_block(s["if"].get("else", []))):
                return True
            if "while" in s and try_block(s["while"]["body"]):
                return True
        return False

    return t if try_block(t["body"]) else None


def _refs_var(e, name: str) -> bool:
    if isinstance(e, dict):
        if e.get("var") == name:
            return True
        return any(_refs_var(v, name) for v in e.values())
    if isinstance(e, list):
        return any(_refs_var(v, name) for v in e)
    return False


def mut_ensures_conjunct_dropped(task: dict) -> Optional[dict]:
    """An ensures conjunct dropped: drop one item from a multi-clause
    `ensures` list, or one `arg` from a top-level `and`."""
    t = copy.deepcopy(task)
    if len(t.get("ensures", [])) >= 2:
        t["ensures"].pop()
        return t
    if t.get("ensures") and t["ensures"][0].get("op") == "and" \
            and len(t["ensures"][0]["args"]) >= 2:
        t["ensures"][0]["args"].pop()
        return t
    return None


def _find_quantifier(e):
    if isinstance(e, dict):
        if "forall" in e or "exists" in e:
            return e
        for v in e.values():
            r = _find_quantifier(v)
            if r is not None:
                return r
    elif isinstance(e, list):
        for v in e:
            r = _find_quantifier(v)
            if r is not None:
                return r
    return None


def mut_quantifier_bound_widened(task: dict) -> Optional[dict]:
    """A quantifier bound widened by one: the first `forall`/`exists`
    anywhere in `requires`/`ensures`/every loop's `invariants`, its `hi`
    replaced by `hi + 1`."""
    t = copy.deepcopy(task)
    for pool in (t.get("requires", []), t.get("ensures", [])):
        for e in pool:
            q = _find_quantifier(e)
            if q is not None:
                key = "forall" if "forall" in q else "exists"
                q[key]["hi"] = {"op": "+", "args": [q[key]["hi"], {"int": 1}]}
                return t
    for w in _task_loops(t["body"]):
        for e in w.get("invariants", []):
            q = _find_quantifier(e)
            if q is not None:
                key = "forall" if "forall" in q else "exists"
                q[key]["hi"] = {"op": "+", "args": [q[key]["hi"], {"int": 1}]}
                return t
    return None


def _find_neg(e):
    if isinstance(e, dict):
        if e.get("op") == "neg":
            return e
        for v in e.values():
            r = _find_neg(v)
            if r is not None:
                return r
    elif isinstance(e, list):
        for v in e:
            r = _find_neg(v)
            if r is not None:
                return r
    return None


def mut_negative_literal_flip(task: dict) -> Optional[dict]:
    """A negative literal read as positive: the first `{"op": "neg", ...}`
    anywhere in the body, replaced by its bare (positive) argument."""
    t = copy.deepcopy(task)
    n = _find_neg(t["body"])
    if n is None:
        n = _find_neg(t.get("requires", [])) or _find_neg(t.get("ensures", []))
    if n is None:
        return None
    arg = n["args"][0]
    n.clear()
    n.update(arg)
    return t


def mut_totalisation_default_reached(task: dict) -> Optional[dict]:
    """A totalisation default reached on the domain: the first spec_fun
    with an `ite`-shaped body (decision 6's totalisation) has its
    then/else branches swapped, so the default value is produced on the
    wrong side of the domain guard."""
    t = copy.deepcopy(task)
    for f in t.get("spec_funs", []):
        b = f.get("body", {})
        if "ite" in b:
            c = b["ite"]
            c["then"], c["else"] = c["else"], c["then"]
            return t
    return None


def mut_loop_guard_negated(task: dict) -> Optional[dict]:
    """A negated loop guard: the first `while`'s `cond` wrapped in `not`
    (or, if already `not`, unwrapped -- either way, a negated guard)."""
    t = copy.deepcopy(task)
    loops = _task_loops(t["body"])
    if not loops:
        return None
    w = loops[0]
    cond = w["cond"]
    if isinstance(cond, dict) and cond.get("op") == "not":
        w["cond"] = cond["args"][0]
    else:
        w["cond"] = {"op": "not", "args": [cond]}
    return t


def mut_invariant_dropped(task: dict) -> Optional[dict]:
    """A dropped invariant: the first loop's first invariant removed."""
    t = copy.deepcopy(task)
    loops = _task_loops(t["body"])
    for w in loops:
        if w.get("invariants"):
            w["invariants"].pop(0)
            return t
    return None


T7_MUTATIONS = [
    ("iff-as-implies", mut_iff_as_implies),
    ("parallel-sequenced", mut_parallel_sequenced),
    ("ensures-conjunct-dropped", mut_ensures_conjunct_dropped),
    ("quantifier-bound-widened", mut_quantifier_bound_widened),
    ("negative-literal-flip", mut_negative_literal_flip),
    ("totalisation-default-reached", mut_totalisation_default_reached),
    ("loop-guard-negated", mut_loop_guard_negated),
    ("invariant-dropped", mut_invariant_dropped),
]


def run_t7(task: dict, source: MethodDecl, closure: tuple, dfy_dir: Path,
          timeout_s: float = DEFAULT_TIMEOUT_S) -> list:
    """Section 18.3's standing test: feed every applicable mutation of
    `T7_MUTATIONS` through `fuzz_lower.check_wf` then `check` (sections 9
    and 10), and report whether each was caught. A mutation not
    applicable to this particular task (no site of the shape it targets)
    is reported `seeded=False`, not silently skipped -- "0 wrong lifts
    over 785" must be a measurement of the checker, not of how many
    mutations happened to apply (18.3's own words)."""
    dfy_dir = Path(dfy_dir)
    # `check()` writes the checker/differential .dfy files as siblings of
    # the `dfy_path` it is given (`dfy_path.with_name(...)`), so the
    # directory a caller names here must exist before any mutation that
    # actually reaches `check()` (not every mutation does: "not-applicable"
    # and a check_wf failure both return before any file is written) --
    # integrator fix 2026-09-05, found via a FileNotFoundError on a T7
    # mutation that was the first one for its task to reach `check()`.
    dfy_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for name, fn in T7_MUTATIONS:
        corrupted = fn(task)
        if corrupted is None:
            results.append({"mutation": name, "seeded": False, "caught": None,
                            "how": "not-applicable"})
            continue
        errs = fuzz_lower.check_wf(corrupted)
        if errs:
            results.append({"mutation": name, "seeded": True, "caught": True,
                            "how": f"check-wf-failed:{errs[0]}"})
            continue
        rec = LiftRecord(source_path=str(dfy_dir), method=source.name or "",
                         rprint_sha256="0" * 64)
        out_path = dfy_dir / f"mut_{name.replace('-', '_')}"
        try:
            outcome = check(corrupted, source, closure, rec, out_path, timeout_s=timeout_s)
        except Exception as e:                                   # noqa: BLE001
            results.append({"mutation": name, "seeded": True, "caught": None,
                            "how": f"error:{e!r}"})
            continue
        caught = (outcome.refusal is not None
                 and outcome.refusal.reason in ("lift-check-failed", "lift-diff-failed"))
        how = outcome.refusal.reason if outcome.refusal is not None else "not-caught"
        results.append({"mutation": name, "seeded": True, "caught": caught, "how": how})
    return results


# ===========================================================================
# 18.4: the inverse test against lower_dafny. Written against
# lift_resolve/lift_parse/lift_classify/lift_rewrite's signatures; when any
# of them is still a stub (raises NotImplementedError), this reports
# "waits-for-integrator" at the exact stage that blocked it rather than
# guessing.
# ===========================================================================

def _fold_neg(e):
    """Integrator fix 2026-09-06 (18.4's first documented asymmetry): a
    negative literal round-trips as either `{"op":"neg","args":[{"int":
    k}]}` or `{"int": -k}`, chosen by whichever side's printer/parser
    last touched it (measured: 6 of 20 inverse-test mismatches over the
    committed tasks plus `fuzz_lower.build_corpus(20, seed=20260905)`
    were exactly this, e.g. `fz_wrong_002`'s
    `.body[...].assign[1].args[0].args`, one side carrying `args` at all
    and the other not). Folded to the literal form wherever it appears,
    on both sides, before any inverse-test comparison, so this printer
    choice is never mistaken for a lifter fault in either direction."""
    if isinstance(e, dict):
        if (e.get("op") == "neg" and isinstance(e.get("args"), list)
                and len(e["args"]) == 1):
            inner = e["args"][0]
            if isinstance(inner, dict) and set(inner.keys()) == {"int"}:
                return {"int": -inner["int"]}
        return {k: _fold_neg(v) for k, v in e.items()}
    if isinstance(e, list):
        return [_fold_neg(v) for v in e]
    return e


def _has_neg_literal(e) -> bool:
    """Whether `_fold_neg` would actually change `e` -- used only to
    report, per task item 3, "which normalisation fired", never to gate
    the comparison itself (folding always runs)."""
    if isinstance(e, dict):
        if (e.get("op") == "neg" and isinstance(e.get("args"), list)
                and len(e["args"]) == 1):
            inner = e["args"][0]
            if isinstance(inner, dict) and set(inner.keys()) == {"int"}:
                return True
        return any(_has_neg_literal(v) for v in e.values())
    if isinstance(e, list):
        return any(_has_neg_literal(v) for v in e)
    return False


def _flatten_assoc(e, op: str) -> list:
    """The leaf operands of a chain of nested (already `_canon_expr`-
    canonicalised) `{"op": op, "args": [a, b]}` binary nodes, left to
    right -- `op` is `"+"` or `"*"`, both associative AND commutative
    over t's integer domain, so a DIFFERENT grouping of the same chain
    (measured: `fuzz_lower.build_corpus(20, seed=20260905)`'s
    `fz_wrong_002`/`fz_v0if_013`, `(-2) * (2 * 11)` round-tripping as
    `((-2) * 2) * 11` -- Dafny's own grammar reprints and reparses `*` as
    strictly left-associative, so any right-grouped chain a generator
    built directly, never through dafny's own parser, cannot survive a
    round trip unchanged) carries no more meaning than and/or's own
    grouping does, which `_canon_expr` already discounts by sorting."""
    if (isinstance(e, dict) and e.get("op") == op
            and isinstance(e.get("args"), list) and len(e["args"]) == 2):
        out = []
        for a in e["args"]:
            out.extend(_flatten_assoc(a, op))
        return out
    return [e]


def _canon_expr(e):
    """Canonicalise a t expression for the inverse-test comparison:
    recursively sort the args of commutative `and`/`or` nodes, so the
    third documented asymmetry (nested binary and/or flattening to one
    n-ary node) cannot fail an otherwise-identical comparison over a
    grouping/order difference alone; the same treatment for `+`/`*`
    (never `-`: not associative or commutative), rebuilt as a canonical
    left-nested binary chain since t's own grammar stores them strictly
    binary (see `_flatten_assoc`)."""
    if isinstance(e, dict):
        out = {k: _canon_expr(v) for k, v in e.items()}
        if out.get("op") in ("and", "or") and isinstance(out.get("args"), list):
            out["args"] = sorted(out["args"], key=lambda x: repr(x))
        elif (out.get("op") in ("+", "*")
              and isinstance(out.get("args"), list) and len(out["args"]) == 2):
            leaves = sorted(_flatten_assoc(out, out["op"]), key=lambda x: repr(x))
            rebuilt = leaves[0]
            for leaf in leaves[1:]:
                rebuilt = {"op": out["op"], "args": [rebuilt, leaf]}
            return rebuilt
        return out
    if isinstance(e, list):
        return [_canon_expr(v) for v in e]
    return e


def _canon_task(task: dict) -> dict:
    t = _canon_expr(_fold_neg(copy.deepcopy(task)))
    t.pop("name", None)  # asymmetry 1: capitalise/lowercase round trip
    # Decision 16: "the 't' version field ... always 1" -- a fresh lift
    # always emits t:1 regardless of what an older, differently-versioned
    # committed task declared, so the version tag carries no round-trip
    # content of its own to compare.
    t.pop("t", None)
    t.pop("gate", None)  # a human-curated corpus category, never round-tripped
    # fuzz_lower.build_corpus staples its own bookkeeping onto a task dict
    # (`_family`, `_twin_op`, `_gt`, `_expect`, `_inv`, ...): fuzzer-side
    # metadata never fed to lower_dafny.lower and never reconstructed by
    # a round trip, not a lifter asymmetry.
    for k in [k for k in t if k.startswith("_")]:
        t.pop(k, None)
    return t


# ---------------------------------------------------------------------------
# Alpha-equivalence (18.4's second documented asymmetry, integrator fix
# 2026-09-06): the file-global renamer renames a LOCAL or a bound variable
# whenever its bare name collides with some other name anywhere in the
# whole rprint text, even across scopes that never interact -- measured:
# 14 of 20 inverse-test mismatches were exactly this (`i`/`i_v`/`i_v2` on
# a while-loop counter, `s`/`x` on a spec_fun's OWN params renamed to
# `s_v`/`x_v` because the ENCLOSING method happens to have same-named
# params in an entirely separate scope: `count_matches.json`). A plain
# JSON `==` after `_canon_task` cannot see past this, so `_alpha_equal_
# tasks` walks both (already `_canon_task`-normalised) trees in PARALLEL,
# building a bijection as it goes: params, returns, a spec_fun's OWN
# name, and the TYPE (never the name) of a spec_fun's OWN parameters at
# each position must match exactly (task item 3's "params, returns,
# spec_fun names and their parameter order must match exactly"); a
# spec_fun's own parameter NAMES, and every local/bound-variable name
# introduced by a `var` statement or a `forall`/`exists` binder, are
# free to differ as long as the SAME correspondence holds at every use
# (checked, never assumed: a name seen mapped one way and later required
# to map another way is a real mismatch, not a renaming). Method params/
# returns seed the bijection as the identity (they are never renamed);
# each spec_fun gets its OWN bijection, seeded fresh from its own
# params, so a name shared by coincidence between two scopes that never
# interact (`count_matches.json`'s `s`) cannot force a spurious clash.
# ---------------------------------------------------------------------------

class _AlphaMismatch(Exception):
    """Raised at the first point two (already `_canon_task`-normalised)
    trees are NOT alpha-equivalent; `path` names where, `a`/`b` the two
    values found there, for the caller to fold into its own diff report."""
    def __init__(self, path, a=None, b=None):
        super().__init__(path)
        self.path = path
        self.a = a
        self.b = b


def _alpha_expr(a, b, bindings: dict, rev: dict, path: str, renames: set) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            raise _AlphaMismatch(path, a, b)
        if "var" in a and isinstance(a["var"], str):
            # A USE (a DECLARATION -- a `var` statement or a quantifier
            # binder -- is handled by its own caller before recursing
            # into the scope the declared name is visible in, so by the
            # time an expression walk reaches a bare `{"var": x}` it is
            # always a reference to an already-bound name).
            na, nb = a["var"], b["var"]
            if na not in bindings or bindings[na] != nb:
                raise _AlphaMismatch(path, a, b)
            if na != nb:
                renames.add(f"{na}->{nb}")
            return
        if "forall" in a or "exists" in a:
            kw = "forall" if "forall" in a else "exists"
            qa, qb = a[kw], b[kw]
            if set(qa.keys()) != set(qb.keys()):
                raise _AlphaMismatch(path, a, b)
            _alpha_expr(qa["lo"], qb["lo"], bindings, rev, f"{path}.{kw}.lo", renames)
            _alpha_expr(qa["hi"], qb["hi"], bindings, rev, f"{path}.{kw}.hi", renames)
            na, nb = qa["var"], qb["var"]
            if nb in rev and rev[nb] != na:
                raise _AlphaMismatch(f"{path}.{kw}.var", na, nb)
            inner_b, inner_r = dict(bindings), dict(rev)
            inner_b[na] = nb
            inner_r[nb] = na
            _alpha_expr(qa["body"], qb["body"], inner_b, inner_r,
                       f"{path}.{kw}.body", renames)
            if na != nb:
                renames.add(f"{na}->{nb}")
            return
        for k in a:
            _alpha_expr(a[k], b[k], bindings, rev, f"{path}.{k}", renames)
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            raise _AlphaMismatch(f"{path}[len]", len(a), len(b))
        for i, (x, y) in enumerate(zip(a, b)):
            _alpha_expr(x, y, bindings, rev, f"{path}[{i}]", renames)
        return
    if a != b:
        raise _AlphaMismatch(path, a, b)


def _alpha_stmts(a_list: list, b_list: list, bindings: dict, rev: dict,
                 path: str, renames: set) -> None:
    """`bindings`/`rev` are mutated in place as `var` statements are
    walked, exactly matching Dafny's own scoping: a name declared here
    stays visible to every later statement in THIS list, but an `if`'s
    two branches and a `while`'s body each get their OWN copy (seeded
    from the current bindings) so a branch-local declaration cannot leak
    into its sibling or past the statement that opened the block."""
    if len(a_list) != len(b_list):
        raise _AlphaMismatch(f"{path}[len]", len(a_list), len(b_list))
    for i, (sa, sb) in enumerate(zip(a_list, b_list)):
        p = f"{path}[{i}]"
        if set(sa.keys()) != set(sb.keys()):
            raise _AlphaMismatch(p, sa, sb)
        if "assign" in sa:
            na, ea = sa["assign"]
            nb, eb = sb["assign"]
            if na not in bindings or bindings[na] != nb:
                raise _AlphaMismatch(f"{p}.assign[0]", na, nb)
            if na != nb:
                renames.add(f"{na}->{nb}")
            _alpha_expr(ea, eb, bindings, rev, f"{p}.assign[1]", renames)
        elif "return" in sa:
            # Early exit (v1, SPEC.md, 2026-09-08): a `return` names the
            # task's own return variable, never a local, so it is
            # compared exactly like `assign` above.
            na, ea = sa["return"]
            nb, eb = sb["return"]
            if na not in bindings or bindings[na] != nb:
                raise _AlphaMismatch(f"{p}.return[0]", na, nb)
            if na != nb:
                renames.add(f"{na}->{nb}")
            _alpha_expr(ea, eb, bindings, rev, f"{p}.return[1]", renames)
        elif "var" in sa:
            da, db = sa["var"], sb["var"]
            if da.get("type") != db.get("type"):
                raise _AlphaMismatch(f"{p}.var.type", da, db)
            _alpha_expr(da["init"], db["init"], bindings, rev, f"{p}.var.init", renames)
            na, nb = da["name"], db["name"]
            if nb in rev and rev[nb] != na:
                raise _AlphaMismatch(f"{p}.var.name", na, nb)
            bindings[na] = nb
            rev[nb] = na
            if na != nb:
                renames.add(f"{na}->{nb}")
        elif "if" in sa:
            ca, cb = sa["if"], sb["if"]
            _alpha_expr(ca["cond"], cb["cond"], bindings, rev, f"{p}.if.cond", renames)
            _alpha_stmts(ca["then"], cb["then"], dict(bindings), dict(rev),
                        f"{p}.if.then", renames)
            _alpha_stmts(ca["else"], cb["else"], dict(bindings), dict(rev),
                        f"{p}.if.else", renames)
        elif "while" in sa:
            wa, wb = sa["while"], sb["while"]
            _alpha_expr(wa["cond"], wb["cond"], bindings, rev, f"{p}.while.cond", renames)
            _alpha_expr(wa.get("invariants", []), wb.get("invariants", []),
                       bindings, rev, f"{p}.while.invariants", renames)
            _alpha_expr(wa["decreases"], wb["decreases"], bindings, rev,
                       f"{p}.while.decreases", renames)
            _alpha_stmts(wa["body"], wb["body"], dict(bindings), dict(rev),
                        f"{p}.while.body", renames)
        else:
            raise _AlphaMismatch(p, sa, sb)


def _alpha_equal_tasks(a: dict, b: dict) -> list:
    """Returns the sorted list of `"expected->got"` local/bound-variable
    renames actually used, or raises `_AlphaMismatch` at the first real
    difference. `a`/`b` must already be `_canon_task`-normalised."""
    renames: set = set()
    if a.get("params", []) != b.get("params", []):
        raise _AlphaMismatch(".params", a.get("params"), b.get("params"))
    if a.get("returns", []) != b.get("returns", []):
        raise _AlphaMismatch(".returns", a.get("returns"), b.get("returns"))
    bindings = {p["name"]: p["name"] for p in a.get("params", [])}
    bindings.update({r["name"]: r["name"] for r in a.get("returns", [])})
    rev = dict(bindings)

    a_funs, b_funs = a.get("spec_funs", []), b.get("spec_funs", [])
    if len(a_funs) != len(b_funs):
        raise _AlphaMismatch(".spec_funs[len]", len(a_funs), len(b_funs))
    for i, (fa, fb) in enumerate(zip(a_funs, b_funs)):
        p = f".spec_funs[{i}]"
        if set(fa.keys()) != set(fb.keys()):
            raise _AlphaMismatch(p, fa, fb)
        if fa.get("name") != fb.get("name"):
            raise _AlphaMismatch(f"{p}.name", fa.get("name"), fb.get("name"))
        pa, pb = fa.get("params", []), fb.get("params", [])
        if len(pa) != len(pb):
            raise _AlphaMismatch(f"{p}.params[len]", len(pa), len(pb))
        fbindings, frev = {}, {}
        for xa, xb in zip(pa, pb):
            if xa.get("type") != xb.get("type"):
                raise _AlphaMismatch(f"{p}.params.type", xa, xb)
            fbindings[xa["name"]] = xb["name"]
            frev[xb["name"]] = xa["name"]
            if xa["name"] != xb["name"]:
                renames.add(f"{xa['name']}->{xb['name']}")
        for k in fa:
            if k in ("name", "params"):
                continue
            _alpha_expr(fa[k], fb[k], fbindings, frev, f"{p}.{k}", renames)

    known = {"params", "returns", "spec_funs", "body"}
    for key in (set(a.keys()) | set(b.keys())) - known:
        _alpha_expr(a.get(key), b.get(key), bindings, rev, f".{key}", renames)

    _alpha_stmts(a["body"], b["body"], dict(bindings), dict(rev), ".body", renames)
    return sorted(renames)


def _task_self_calls(task: dict) -> bool:
    def rec(e):
        if isinstance(e, dict):
            if "call" in e and e["call"].get("fun") == task["name"]:
                return True
            return any(rec(v) for v in e.values())
        if isinstance(e, list):
            return any(rec(v) for v in e)
        return False
    return rec(task["body"])


def inverse_test(task: dict, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Section 18.4: `lift(rprint(lower_dafny.lower(task, task["body"])))`
    must equal `task` as canonical JSON, modulo the three documented
    asymmetries (name casing, a hoisted self-call local for recursive
    tasks, and and/or nesting -- `_canon_task` normalises the first and
    third; the second is handled by returning `status="recursive"` with
    an interp-domain comparison left to the caller rather than a JSON
    diff, per 18.4's own words: "the recursive tasks are compared by
    interp on the domain rather than by JSON"), PLUS two more this
    module's own measurement against the 11 committed tasks and
    `fuzz_lower.build_corpus(20, seed=20260905)` found necessary
    (integrator fix 2026-09-06, task item 3): a negative literal folded
    to one canonical form (`_fold_neg`) and a consistent alpha-renaming
    of locals/bound variables the file-global renamer applies across
    scopes that never interact (`_alpha_equal_tasks`) -- 20 of the 31
    raw mismatches were exactly these two; the remaining 2 turned out to
    be a fourth, previously-undocumented asymmetry of the SAME shape as
    the third (`+`/`*` are associative and commutative over t's integer
    domain exactly like `and`/`or` are, and Dafny's own grammar reprints
    a chain of either strictly left-associative regardless of how it was
    built), so `_canon_expr` normalises them the same way. A residual
    mismatch after all four is a real lifter fault, not a known
    round-trip artefact.

    Returns a dict with `status` one of: `"match"` (plus `normalized`,
    the fold/rename normalisations that actually fired, `[]` if none
    were needed), `"mismatch"` (plus `expected`/`got`/`diff_path`,
    `normalized` for whichever of the four fired but still left a real
    difference), `"recursive"` (plus `lowered_task`, the round tripped
    task, for the caller to compare via interp), or
    `"waits-for-integrator"` (plus `stage`, the first stub hit) when
    `lift_resolve.resolve`, `lift_parse.parse`/`gradable_methods`,
    `lift_classify.classify`, or `lift_rewrite.rewrite` is not
    implemented yet."""
    import lift_resolve
    import lift_parse
    import lift_classify
    import lift_rewrite

    dfy_text = lower_dafny.lower(task, task["body"])
    with tempfile.NamedTemporaryFile(suffix=".dfy", delete=False, mode="w",
                                     encoding="utf-8", newline="\n") as fh:
        fh.write(dfy_text)
        tmp_path = Path(fh.name)

    try:
        try:
            rr = lift_resolve.resolve(tmp_path, timeout_s)
        except NotImplementedError:
            return {"status": "waits-for-integrator", "stage": "lift_resolve.resolve"}
        if getattr(rr, "refusal", None) is not None:
            return {"status": "error", "stage": "resolve", "detail": rr.refusal}

        try:
            module = lift_parse.parse(rr.rprint_text)
        except NotImplementedError:
            return {"status": "waits-for-integrator", "stage": "lift_parse.parse"}

        try:
            methods = lift_parse.gradable_methods(module)
        except NotImplementedError:
            return {"status": "waits-for-integrator",
                   "stage": "lift_parse.gradable_methods"}

        want_name = task["name"].capitalize()
        method = next((m for m in methods if m.name == want_name), None)
        if method is None:
            return {"status": "error",
                   "detail": f"lowered method {want_name!r} not gradable after round trip"}

        try:
            plan = lift_classify.classify(module, method)
        except NotImplementedError:
            return {"status": "waits-for-integrator", "stage": "lift_classify.classify"}
        if isinstance(plan, Refusal):
            return {"status": "error",
                   "detail": f"round trip refused: {plan.reason} ({plan.token})"}

        try:
            rr2 = lift_rewrite.rewrite(module, plan, str(tmp_path), "0" * 64)
        except NotImplementedError:
            return {"status": "waits-for-integrator", "stage": "lift_rewrite.rewrite"}
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

    got_task = rr2.task
    if _task_self_calls(task):
        return {"status": "recursive", "lowered_task": got_task}
    a, b = _canon_task(task), _canon_task(got_task)
    normalized = []
    if _has_neg_literal(task) or _has_neg_literal(got_task):
        normalized.append("neg-literal-folded")
    if a == b:
        return {"status": "match", "normalized": normalized}
    try:
        renames = _alpha_equal_tasks(a, b)
    except _AlphaMismatch as e:
        return {"status": "mismatch", "expected": a, "got": b,
               "diff_path": e.path, "normalized": normalized}
    if renames:
        normalized.append("alpha-renamed:" + ",".join(renames))
    return {"status": "match", "normalized": normalized}
