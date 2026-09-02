#!/usr/bin/env python3
"""lower_dafny.py — lower t tasks (v0 and v1) to Dafny, verify both the task
and its broken twin, and refuse anything that does not flip.

    python3 t/lower_dafny.py            # all of t/tasks/*.json
    python3 t/lower_dafny.py abs        # one task

The verdict is Dafny's, never this file's. Exit codes are the measured ones
from dafny_verify.py (dafny 4.11.0): 0 verified, 2 parse/resolution, 4
verification failed. A task COUNTS only when the real lowering exits 0 and the
twin exits 4 — dafny_pairs.py's measured-flip rule. Everything else is refused
with the reason printed: twin-verifies means the spec is vacuous; real-fails
means the task is wrong; twin-malformed means the mutation broke syntax rather
than meaning and the witness would be about parsing, not proof.

v1 mapping, gate by gate (SPEC.md):
  quantifiers — t's bounded forall/exists over [lo,hi) lower to Dafny's native
    bounded quantifiers; `seq` is Dafny's seq<int>, `len` is |s|, `at` is s[i].
    Dafny's well-formedness checking discharges t's definedness obligations
    natively: `at` outside [0,len) is a verification error unless guarded, and
    &&/||/==>/ite/quantifier bodies are checked left-to-right / under-guard,
    exactly t's rules. Nothing is totalized.
  loops — t `while` lowers to Dafny while with invariant/decreases clauses;
    Dafny checks decreases >= 0 and strictly decreasing, t's obligation.
  recursion — spec_funs lower to Dafny `function` (pure, with decreases);
    a task self-call lowers to a call of the lowered METHOD, hoisted out of
    expression position into `var tmp := M(...);` statements (SPEC.md allows
    the hoist; evaluation is call-by-value left-to-right). Hoisting is refused
    (NotImplementedError, an ABSTAIN) when a self-call sits under a lazily
    evaluated position — quantifier body, ite branch, non-first and/or/implies
    argument — because unconditional evaluation there could smuggle in a
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
                f"self-call of {self_name!r} in spec position — t puts "
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
    """Every string anywhere in the task JSON — a superset of every identifier
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
    right, innermost first — call-by-value order) into `pre` as a
    `var tmp := Method(...);` statement. `lazy` marks positions Dafny/t do not
    unconditionally evaluate; a self-call there cannot be hoisted without
    evaluating it on paths that never owed its precondition, so it is an
    explicit ABSTAIN, not a wrong program."""
    if "call" in e and e["call"]["fun"] == ctx.self_name:
        if lazy:
            raise NotImplementedError(
                "dafny: self-call under a lazily-evaluated position "
                "(ite branch / short-circuit arg / quantifier body) — "
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


# `witness` is the twin's measured witness (harness.twin_cached). Twin call
# sites pass it; this lowering does not use it yet.
def lower(task: dict, body: list, witness: dict | None = None) -> str:
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
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import harness
    raise SystemExit(harness.run_all(sys.argv[1:], lower, dafny_backend, "dfy"))
