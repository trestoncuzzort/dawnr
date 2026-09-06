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
        return f"'{e.text}'"
    if isinstance(e, StringLit):
        return '"' + e.text.replace("\\", "\\\\").replace('"', '\\"') + '"'
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
        binders = ", ".join(_print_param(b) for b in e.binders)
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
        binders = ", ".join(_print_param(b) for b in e.binders)
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

def _t_expr(e: dict) -> str:
    if "int" in e:
        return str(e["int"])
    if "bool" in e:
        return "true" if e["bool"] else "false"
    if "var" in e:
        return e["var"]
    if "ite" in e:
        c = e["ite"]
        return (f"(if {_t_expr(c['cond'])} then {_t_expr(c['then'])} "
                f"else {_t_expr(c['else'])})")
    if "forall" in e or "exists" in e:
        kw = "forall" if "forall" in e else "exists"
        q = e[kw]
        joiner = "==>" if kw == "forall" else "&&"
        return (f"({kw} {q['var']}: int :: {_t_expr(q['lo'])} <= {q['var']} "
                f"< {_t_expr(q['hi'])} {joiner} {_t_expr(q['body'])})")
    if "call" in e:
        c = e["call"]
        args = ", ".join(_t_expr(a) for a in c["args"])
        return f"{c['fun']}({args})"
    op = e["op"]
    args = e.get("args", [])
    if op == "neg":
        return f"(-{_t_expr(args[0])})"
    if op == "not":
        return f"(!{_t_expr(args[0])})"
    if op == "len":
        return f"|{_t_expr(args[0])}|"
    if op == "at":
        return f"{_t_expr(args[0])}[{_t_expr(args[1])}]"
    if op in ("and", "or"):
        joiner = " && " if op == "and" else " || "
        return "(" + joiner.join(_t_expr(a) for a in args) + ")"
    if op == "implies":
        return f"({_t_expr(args[0])} ==> {_t_expr(args[1])})"
    if op in ("+", "-", "*", "<", "<=", ">", ">=", "==", "!="):
        return f"({_t_expr(args[0])} {op} {_t_expr(args[1])})"
    raise ValueError(f"lift_check._t_expr: unknown t operator {op!r}")


def _t_conj(exprs: list) -> str:
    if not exprs:
        return "true"
    return " && ".join(f"({_t_expr(e)})" for e in exprs)


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
                out.append((s, list(sc)))
                vt = s.var_type or Type(line=s.line, kind="id", name="int")
                walk(s.body, sc + [Param(line=s.line, name=s.var, type=vt)])
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
    return _param_overlay(
        rename, record,
        [p.name for p in source.params], [p["name"] for p in task["params"]],
        source.returns[0].name if source.returns else None,
        task["returns"][0]["name"])


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
    lifted_req = _t_conj(task.get("requires", []))

    # (3) L_fun_F per spec_fun whose closure function is found.
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
        nat_clause = _and([f"{p.name} >= 0" for p in fd.params if _is_nat_type(p.type)])
        p_src = _conj_text([sp.expr for sp in fd.specs if isinstance(sp, RequiresClause)],
                           rename)
        lines.append(f"lemma {name}({ps})")
        if nat_clause != "true":
            lines.append(f"  requires {nat_clause}")
        if p_src != "true":
            lines.append(f"  requires {p_src}")
        fn_src = rename.get(fd.name, fd.name)
        lines.append(f"  ensures {fn_src}({args}) == {f['name']}({args})")
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
    src_params = list(source.params)
    task_params = task["params"]
    lem_ps = ", ".join(f"{tp['name']}: {_lemma_param_type(sp.type)}"
                       for sp, tp in zip(src_params, task_params))

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
    ret_type_src = source.returns[0].type if source.returns else None
    ret_lemma_ty = _lemma_param_type(ret_type_src)
    lem_ps_ens = lem_ps + (", " if lem_ps else "") + f"{ret['name']}: {ret_lemma_ty}"
    src_ens_conj = _conj_text(
        [sp.expr for sp in source.specs if isinstance(sp, EnsuresClause)], crename)
    ret_type_clause = (f"{ret['name']} >= 0" if _is_nat_type(ret_type_src) else "true")
    lifted_ens = _t_conj(task.get("ensures", []))
    hint_lines = []
    for fd in fdecls:
        f = _match_spec_fun(fd, task.get("spec_funs", []), record)
        if f is None:
            continue
        binders = ", ".join(f"{p.name}: {_lemma_param_type(p.type)}" for p in fd.params)
        args = ", ".join(p.name for p in fd.params)
        nat_clause = _and([f"{p.name} >= 0" for p in fd.params if _is_nat_type(p.type)])
        p_src = _conj_text([sp.expr for sp in fd.specs if isinstance(sp, RequiresClause)],
                           rename)
        guard = _and([nat_clause, p_src])
        fn_src = rename.get(fd.name, fd.name)
        hint_lines.append(
            f"  forall {binders} | {guard} ensures "
            f"{fn_src}({args}) == {f['name']}({args}) {{ L_fun_{f['name']}({args}); }}")
    lines.append(f"lemma L_ens({lem_ps_ens})")
    lines.append(f"  requires {lifted_req}")
    lines.append(f"  ensures ({_and([ret_type_clause, src_ens_conj])}) <==> ({lifted_ens})")
    lines.append("{")
    lines.extend(hint_lines)
    lines.append("}")
    lines.append("")

    # (6) L_inv_k / decreases-equality per loop, pre-order.
    src_loops = _walk_source_loops(source)
    task_loops = _task_loops(task["body"])
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
        locals_in_scope = list(scope[len(src_params):])
        full_names = ([tp["name"] for tp in task_params]
                      + [crename.get(p.name, p.name) for p in locals_in_scope]
                      + [ret["name"]])
        full_types = ([sp.type for sp in src_params]
                      + [p.type for p in locals_in_scope] + [ret_type_src])
        ps_inv = ", ".join(f"{n}: {_lemma_param_type(t)}"
                           for n, t in zip(full_names, full_types))
        nat_clause = _and([f"{n} >= 0" for n, t in zip(full_names, full_types)
                          if _is_nat_type(t)])
        inv_exprs = [sp.expr for sp in loop.specs if isinstance(sp, InvariantClause)]
        src_inv = _conj_text(inv_exprs, crename)
        lifted_inv = (_t_conj(task_loops[k].get("invariants", []))
                     if k < len(task_loops) else "true")
        # Same reason as L_ens's forall hint (section 9 item 5, measured):
        # Dafny will not apply a spec_fun's equivalence lemma unprompted.
        # Here the loop's scope variables are already concrete lemma
        # parameters (not universally quantified), so a direct call
        # suffices in place of a forall.
        fd_names = {fd.name for fd in fdecls}
        inv_hints = []
        for call in _find_fun_calls(inv_exprs, fd_names):
            fd_match = next(fd for fd in fdecls if fd.name == call.fn.name)
            f = _match_spec_fun(fd_match, task.get("spec_funs", []), record)
            if f is None:
                continue
            args = ", ".join(_print_expr(a, crename) for a in call.args)
            guard = _call_guard(fd_match, call, crename)
            call_line = f"L_fun_{f['name']}({args});"
            if guard == "true":
                inv_hints.append(f"  {call_line}")
            else:
                inv_hints.append(f"  if {guard} {{ {call_line} }}")
        lines.append(f"lemma L_inv_{k}({ps_inv})")
        # `nat_clause` also belongs in `requires`, not only inside the
        # ensures' left conjunct: a local that is nat-typed in the source
        # but never reassigned inside THIS loop gets no `nat-invariant
        # -added` clause on the lifted side (decision 5 only appends for
        # an ASSIGNED nat local), so the lifted conjunction on its own
        # says nothing about it -- leaving it a free, unconstrained int
        # lemma parameter makes the <==> false for a witness where it is
        # negative (measured: gcdI-adjacent 04_pot's own `b`, assigned
        # once before the loop from a nat param and never touched again,
        # produced a genuine, provably-false equivalence, not merely a
        # hard-to-automate one -- confirmed by patching just this line and
        # re-verifying: 11 verified, 0 errors, same file, same lemmas).
        # Integrator fix 2026-09-05.
        lines.append(f"  requires {_and([lifted_req, nat_clause])}")
        lines.append(f"  ensures ({_and([nat_clause, src_inv])}) <==> ({lifted_inv})")
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
            src_dec = _print_expr(dec_specs[0].exprs[0], crename)
            lifted_dec = _t_expr(task_loops[k]["decreases"])
            lines.append(f"lemma {name}({ps_inv})")
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
    ret_ty = task["returns"][0]["type"]

    lines.append("method Main() {")
    lines.append("  var bad := 0;")
    lines.append("  var points := 0;")
    for i, (env0, _real) in enumerate(points):
        args = ", ".join(_dafny_literal(env0[n], ty) for n, ty in names_types)
        lines.append(f"  {{")
        lines.append(f"    var srcv := {src_name}({args});")
        lines.append(f"    var liftv := {lift_name}({args});")
        lines.append(f"    points := points + 1;")
        lines.append(f'    print {i}, " ", srcv, " ", liftv, "\\n";')
        cmp_ne = "srcv != liftv" if ret_ty != "bool" else "srcv != liftv"
        lines.append(f"    if {cmp_ne} {{")
        lines.append(f"      bad := bad + 1;")
        lines.append(f"    }}")
        lines.append(f"  }}")
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


def _verify_checker(path: Path, lemma_names: list, timeout_s: float):
    """Runs `dafny verify` on `path`; returns (verdicts: dict[name,str],
    exit_code, all_ok: bool, first_failing_token: str|None,
    warnings: list[str])."""
    exit_code, out = _run_dafny(
        ["verify", str(path), "--allow-warnings", "--log-format", "text"],
        timeout_s)
    warnings = _extract_warnings(out)
    verdicts = {}
    if exit_code == _TIMEOUT_SENTINEL:
        for name in lemma_names:
            verdicts[name] = Outcome.TIMEOUT
        return verdicts, exit_code, False, "timeout", warnings

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
            for sym, kind, outcome in blocks:
                if outcome != "Correct":
                    first_bad = sym
                    break
            if first_bad is None:
                first_bad = "unattributed-error"
            all_ok = False
    return verdicts, exit_code, all_ok, first_bad, warnings


_POINT_RE = re.compile(r"^(\d+) (\S+) (\S+)\s*$")
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


def _dafny_value_matches(printed: str, py_value) -> bool:
    if isinstance(py_value, bool):
        return printed == ("true" if py_value else "false")
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
    t0 = time.monotonic()
    verdicts, exit_code, all_ok, first_bad, warnings = _verify_checker(
        checker_path, lemma_names, timeout_s)
    record.checker_verdicts.update(verdicts)
    record.dafny_exit_codes["verify-checker"] = exit_code
    record.warnings.extend(warnings)

    if not all_ok:
        token = first_bad if first_bad is not None else "unknown"
        refusal = Refusal(reason="lift-check-failed", token=token, line=0, stage="check")
        return CheckOutput(checker_dfy=checker_text, differential_dfy="", record=record,
                           refusal=refusal, interp_points=n_points,
                           interp_first_value=first_value)

    # (5) differential run.
    diff_text = _build_differential_with_points(task, source, closure, ref.points)
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
        record.differential_verdict = "arm-unavailable"
        record.warnings.append("differential run printed no points=/bad= tally")
        refusal = Refusal(reason="lift-diff-failed", token="no-tally", line=0, stage="check")
        return CheckOutput(checker_dfy=checker_text, differential_dfy=diff_text,
                           record=record, refusal=refusal, interp_points=n_points,
                           interp_first_value=first_value)

    if bad_n > 0:
        first_bad_i = next((i for i in sorted(printed)
                            if printed[i][0] != printed[i][1]), None)
        env0 = ref.points[first_bad_i][0] if first_bad_i is not None else {}
        record.differential_verdict = f"bad={bad_n}"
        refusal = Refusal(reason="lift-diff-failed", token=repr(env0), line=0, stage="check")
        return CheckOutput(checker_dfy=checker_text, differential_dfy=diff_text,
                           record=record, refusal=refusal, interp_points=n_points,
                           interp_first_value=first_value)

    record.differential_verdict = f"agrees on {points_n} points"

    # (6) interp third arm (18.5).
    disagreement = None
    for i, (env0, real) in enumerate(ref.points):
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

def _canon_expr(e):
    """Canonicalise a t expression for the inverse-test comparison:
    recursively sort the args of commutative `and`/`or` nodes, so the
    third documented asymmetry (nested binary and/or flattening to one
    n-ary node) cannot fail an otherwise-identical comparison over a
    grouping/order difference alone."""
    if isinstance(e, dict):
        out = {k: _canon_expr(v) for k, v in e.items()}
        if out.get("op") in ("and", "or") and isinstance(out.get("args"), list):
            out["args"] = sorted(out["args"], key=lambda x: repr(x))
        return out
    if isinstance(e, list):
        return [_canon_expr(v) for v in e]
    return e


def _canon_task(task: dict) -> dict:
    t = _canon_expr(copy.deepcopy(task))
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
    interp on the domain rather than by JSON").

    Returns a dict with `status` one of: `"match"`, `"mismatch"` (plus
    `expected`/`got`), `"recursive"` (plus `lowered_task`, the round
    tripped task, for the caller to compare via interp), or
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
    if a == b:
        return {"status": "match"}
    return {"status": "mismatch", "expected": a, "got": b}
