"""Dafny let expressions, lowered by capture-avoiding substitution (2026-09-26).

Until this module the parser refused every let expression by name, and that was
the largest single refusal of the 2026-09-26 lift: 432 of the 1,886
vericoding-benchmark and HumanEval-Dafny programs.

WHAT A LET MEANS. The Dafny Reference Manual, section 9.31.7
(dafny.org/latest/DafnyRef/DafnyRef#sec-let-expression): `var x := e; body`
binds x to the value of e, and "the scope of the variable only extends to the
enclosed expression". Dafny expressions have no side effects and read one heap
state, so the binding is the beta-redex `(lambda x. body) e`, and its value is
`body[x := e]`, the textbook capture-avoiding substitution
(en.wikipedia.org/wiki/Lambda_calculus, "capture-avoiding substitution": at a
binder `y` that rebinds x, stop; at a binder `y` free in e, first rename y to a
fresh y' in its scope, then continue). Several bindings `var x, y := e1, e2;
body` are simultaneous: every right-hand side is read in the enclosing scope
(measured on dafny 4.11: `var x, y := y, x; x - y` at x=1, y=2 is 1), so they
substitute at once, never one after the other. Nested lets are lowered inside
out, so an inner binder that shadows an outer one keeps its own value
(`var x := 1; var x := x + 1; x` is 2, measured).

WHY SUBSTITUTION AND NOT A t BINDING. t has no let (SYNTAX.md, SPEC.md: an Expr
binds names only in forall and exists). Its one other abstraction, a spec_fun,
takes int and seq parameters and returns int or bool (SPEC.md "Gate 3"), is
spec-only, and adding one turns a task's gate to "recursion"; a let over a
bool, a pair or a nested seq, or one in a method body, would have no such
home, and a let lifted that way would change what the kernels are graded on.
So a let whose right-hand side is used more than once is duplicated, and the
duplication is recorded rather than hidden: `ScopeExpansion.census()` (the
sidecar's `let_substitution`) carries the size of every clause, body and
closure function before and after, in Expr nodes. On the 2026-09-26 corpus
516 of 849 bindings had a compound right-hand side used more than once.

WHAT IS REFUSED, BY NAME, and why each would change meaning under
substitution:
  let-such-that   `var x :| P; body`: a choice of some x with P, not a value.
  let-or-fail     `var x :- e; body`: IsFailure/PropagateFailure/Extract on a
                  failure-compatible datatype (manual 9.31.7), outside t.
  let-impure-rhs  a method call on the right (Dafny itself forbids one in an
                  expression; refused rather than trusted), or a right-hand
                  side that may read the heap (an index, a slice, a field or
                  `.Length`, a function call) whose variable sits under
                  `old`/`fresh`/`unchanged`/`allocated` in the body. `old(v)`
                  of a bound value is the value (dafny warns "old has no
                  effect"), but `old(a[0])` is the pre-state element:
                  `ensures var v := a[0]; old(v) == v` verifies after
                  `a[0] := a[0] + 1` and `ensures old(a[0]) == a[0]` does not
                  (both measured on dafny 4.11). Heap reads anywhere else are
                  safe: one expression reads one state.
  let-pattern     a tuple or datatype pattern (refused by the parser), or a
                  binder count that does not match the right-hand sides.
  let-substitution-blowup
                  a let whose substitution would produce more than
                  MAX_SUBSTITUTED_NODES Expr nodes (a chain of lets each used
                  twice doubles at every link); none on the 2026-09-26 corpus.
A refused let is left in place, unexpanded, and its reason is returned for
`lift_classify` to report; this module decides nothing about the rest of the
method.

A declaration with no let comes back as the SAME object, so a let-free program
lifts exactly as it did before this module existed.
"""
from __future__ import annotations

import copy
import dataclasses
import re
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Optional

from lift_ast import (
    Call, Comprehension, Decl, Expr, ForStmt, Fresh, Ident, Index, LetExpr, Lhs,
    Member, MethodDecl, Node, Old, Param, Quantifier, SeqUpdate, Slice,
)

# Calls whose argument is read in a state other than the current one, like `old`.
TWO_STATE_CALLS = frozenset({"unchanged", "allocated"})
# A chain of k lets each used twice copies its first right-hand side 2^k times. The
# 2026-09-26 corpus's largest whole-method result is 1,531 Expr nodes (growth at most
# 3.2x, median 1.02x over 303 methods), so a single let whose substitution would
# produce more than this is refused `let-substitution-blowup`, never built.
MAX_SUBSTITUTED_NODES = 100_000
# What may read the heap, conservatively: without types an index or a slice may be
# on an array, a member may be a field or `.Length`, a call may have a reads clause.
HEAP_READS = (Index, Slice, SeqUpdate, Member, Call)


# ------------------------------------------------------------------ walking --

def _walk(obj) -> Iterator[Node]:
    if isinstance(obj, Node):
        yield obj
        for f in dataclasses.fields(obj):
            if f.name != "line":
                yield from _walk(getattr(obj, f.name))
    elif isinstance(obj, (tuple, list)):
        for item in obj:
            yield from _walk(item)


def size(node) -> int:
    """Expr nodes in `node`: the census's measure of what a substitution copied."""
    return sum(1 for n in _walk(node) if isinstance(n, Expr))


def names_in(node) -> set[str]:
    """Every name `node` mentions or declares: identifiers, parameters, binders,
    locals, loop variables, declarations. A fresh name avoids all of them, so a
    renamed binder can never meet a name a later stage keys a map on."""
    out: set[str] = set()
    for n in _walk(node):
        if isinstance(n, Ident):
            out.add(n.name)
        elif isinstance(n, Param):
            out.add(n.name)
        elif isinstance(n, Lhs) and n.name:
            out.add(n.name)
        elif isinstance(n, ForStmt):
            out.add(n.var)
        elif isinstance(n, Decl) and n.name:
            out.add(n.name)
    return out


def _binding(node) -> Optional[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]]:
    """(bound names, fields in their scope, fields outside it) for a node that
    binds names inside an expression; None for every other node."""
    if isinstance(node, Quantifier):
        return tuple(b.name for b in node.binders), ("attrs", "range", "body"), ()
    if isinstance(node, Comprehension):
        names = tuple(b.name for b in node.binders)
        if node.kind == "seq":
            # seq(n, i => body): `range` holds the length n, read outside i's scope.
            return names, ("body",), ("range",)
        return names, ("range", "body", "value"), ()
    if isinstance(node, LetExpr):
        # A let is not recursive: its right-hand sides are read outside its binders.
        return tuple(b.name for b in node.binders), ("body",), ("rhs",)
    return None


def free_vars(node) -> set[str]:
    """The identifiers `node` reads that no binder inside it binds."""
    out: set[str] = set()
    _free(node, frozenset(), out)
    return out


def _free(node, bound: frozenset, out: set) -> None:
    if isinstance(node, Ident):
        if node.name not in bound:
            out.add(node.name)
        return
    if isinstance(node, (tuple, list)):
        for x in node:
            _free(x, bound, out)
        return
    if not isinstance(node, Node):
        return
    b = _binding(node)
    if b is not None:
        names, scoped, unscoped = b
        for f in unscoped:
            _free(getattr(node, f), bound, out)
        inner = bound | frozenset(names)
        for f in scoped:
            _free(getattr(node, f), inner, out)
        return
    for f in dataclasses.fields(node):
        if f.name != "line":
            _free(getattr(node, f.name), bound, out)


def _count_free(node, name: str) -> int:
    if isinstance(node, Ident):
        return 1 if node.name == name else 0
    if isinstance(node, (tuple, list)):
        return sum(_count_free(x, name) for x in node)
    if not isinstance(node, Node):
        return 0
    b = _binding(node)
    if b is not None:
        names, scoped, unscoped = b
        n = sum(_count_free(getattr(node, f), name) for f in unscoped)
        if name not in names:
            n += sum(_count_free(getattr(node, f), name) for f in scoped)
        return n
    return sum(_count_free(getattr(node, f.name), name)
               for f in dataclasses.fields(node) if f.name != "line")


def binder_uses(let: LetExpr, name: str) -> int:
    """Free occurrences of the binder `name` in `let`'s body: 0 means its value
    is never read and its right-hand side vanishes under substitution."""
    return _count_free(let.body, name)


def fresh_name(base: str, used: set[str]) -> str:
    """`base` with the lowest `_N` suffix no name in `used` has; an identifier
    in every language t lowers to (letters, digits, underscores, a letter
    first), whatever rprint printed (`gcd'`, a resolver's `_t#0`)."""
    stem = re.sub(r"[^A-Za-z0-9_]", "_", base)
    if not stem or not stem[0].isalpha():
        stem = "v" + stem
    n = 1
    while f"{stem}_{n}" in used:
        n += 1
    return f"{stem}_{n}"


# ------------------------------------------------------------- substitution --

def substitute(node, mapping: dict, used: Optional[set] = None):
    """`node[x1 := e1, ..., xn := en]`, simultaneous and capture-avoiding, with
    `mapping` = {x1: e1, ...}. Every inserted copy is a fresh deep copy (a tree
    stays a tree; later stages key maps on node identity). `used` is the set of
    names a fresh binder must avoid; it grows as binders are renamed. Returns
    `node` itself where nothing changed."""
    if used is None:
        used = names_in(node) | set(mapping)
        for v in mapping.values():
            used |= names_in(v)
    return _subst(node, mapping, used)


def _subst(node, mapping: dict, used: set):
    if not mapping:
        return node
    if isinstance(node, Ident):
        return copy.deepcopy(mapping[node.name]) if node.name in mapping else node
    if isinstance(node, tuple):
        new = tuple(_subst(x, mapping, used) for x in node)
        return node if all(a is b for a, b in zip(new, node)) else new
    if isinstance(node, list):
        new_list = [_subst(x, mapping, used) for x in node]
        return node if all(a is b for a, b in zip(new_list, node)) else new_list
    if not isinstance(node, Node):
        return node
    b = _binding(node)
    if b is not None:
        return _subst_binder(node, b, mapping, used)
    changes = {}
    for f in dataclasses.fields(node):
        if f.name == "line":
            continue
        v = getattr(node, f.name)
        nv = _subst(v, mapping, used)
        if nv is not v:
            changes[f.name] = nv
    return dataclasses.replace(node, **changes) if changes else node


def _subst_binder(node, binding, mapping: dict, used: set):
    names, scoped, unscoped = binding
    changes = {}
    for f in unscoped:
        v = getattr(node, f)
        nv = _subst(v, mapping, used)
        if nv is not v:
            changes[f] = nv
    # A binder that rebinds a substituted name ends that substitution here.
    inner = {k: v for k, v in mapping.items() if k not in names}
    scoped_values = {f: getattr(node, f) for f in scoped}
    scoped_free: set[str] = set()
    for sv in scoped_values.values():
        scoped_free |= free_vars(sv)
    live = {k: v for k, v in inner.items() if k in scoped_free}
    if live:
        incoming: set[str] = set()
        for v in live.values():
            incoming |= free_vars(v)
        renames: dict = {}
        binders = []
        for p in node.binders:
            if p.name in incoming:
                # The binder would capture a free name of what is substituted in:
                # rename it first (the alpha step), then substitute.
                new_name = fresh_name(p.name, used | incoming | scoped_free)
                used.add(new_name)
                renames[p.name] = Ident(p.line, new_name)
                binders.append(dataclasses.replace(p, name=new_name))
            else:
                binders.append(p)
        step = {**renames, **live}
        for f, sv in scoped_values.items():
            nsv = _subst(sv, step, used)
            if nsv is not sv:
                changes[f] = nsv
        if renames:
            changes["binders"] = tuple(binders)
    return dataclasses.replace(node, **changes) if changes else node


# ---------------------------------------------------------------- expansion --

@dataclass
class Expansion:
    """`node` with every lowerable let substituted away. `lets`: lets lowered;
    `max_uses`: the most free occurrences one bound variable had in its body
    once the lets inside that body were lowered, i.e. the most copies of one
    right-hand side the substitution made (`var a := e; var b := a + a; b * b`
    copies e four times);
    `lines`: the rprint line of each lowered let; `issues`: (line, reason,
    token) for each let left in place, the reason one of the four refusals in
    this module's docstring."""
    node: object = None
    lets: int = 0
    max_uses: int = 0
    lines: list = field(default_factory=list)
    issues: list = field(default_factory=list)


def expand(node, method_names: Iterable[str] = (), used: Optional[set] = None) -> Expansion:
    """Lower every let in `node` (an Expr, a statement, a declaration, or a tuple
    of them), innermost first. `method_names` are the program's methods, for the
    impure right-hand-side rule."""
    acc = Expansion()
    if used is None:
        used = names_in(node)
    acc.node = _expand(node, frozenset(method_names), used, acc)
    return acc


def _expand(node, method_names: frozenset, used: set, acc: Expansion):
    if isinstance(node, tuple):
        new = tuple(_expand(x, method_names, used, acc) for x in node)
        return node if all(a is b for a, b in zip(new, node)) else new
    if isinstance(node, list):
        new_list = [_expand(x, method_names, used, acc) for x in node]
        return node if all(a is b for a, b in zip(new_list, node)) else new_list
    if not isinstance(node, Node):
        return node
    changes = {}
    for f in dataclasses.fields(node):
        if f.name == "line":
            continue
        v = getattr(node, f.name)
        nv = _expand(v, method_names, used, acc)
        if nv is not v:
            changes[f.name] = nv
    node = dataclasses.replace(node, **changes) if changes else node
    if isinstance(node, LetExpr):
        return _lower(node, method_names, used, acc)
    return node


def _lower(let: LetExpr, method_names: frozenset, used: set, acc: Expansion):
    issue = let_issue(let, method_names)
    if issue is not None:
        acc.issues.append((let.line, issue[0], issue[1]))
        return let
    names = [b.name for b in let.binders]
    uses = [_count_free(let.body, n) for n in names]
    # Each free occurrence (one node) becomes a copy of its right-hand side.
    after = size(let.body) + sum(u * (size(r) - 1) for u, r in zip(uses, let.rhs))
    if after > MAX_SUBSTITUTED_NODES:
        acc.issues.append((let.line, "let-substitution-blowup", str(after)))
        return let
    acc.lets += 1
    acc.lines.append(let.line)
    acc.max_uses = max([acc.max_uses] + uses)
    return _subst(let.body, dict(zip(names, let.rhs)), used)


def let_issue(let: LetExpr, method_names: Iterable[str] = ()) -> Optional[tuple[str, str]]:
    """(reason, token) when `let` must not be lowered by substitution, else None."""
    if let.op == ":|":
        return "let-such-that", ":|"
    if let.op == ":-":
        return "let-or-fail", ":-"
    if len(let.binders) != len(let.rhs):
        return "let-pattern", "var"
    methods = frozenset(method_names)
    for r in let.rhs:
        for n in _walk(r):
            if isinstance(n, Call) and isinstance(n.fn, Ident) and n.fn.name in methods:
                return "let-impure-rhs", n.fn.name
    for b, r in zip(let.binders, let.rhs):
        if _reads_heap(r) and _free_under_two_state(let.body, b.name, False):
            return "let-impure-rhs", b.name
    return None


def _reads_heap(node) -> bool:
    """True when `node` may read the heap in the state it is evaluated in; a
    read already under its own `old(...)` is pinned to the pre-state and moves
    nowhere."""
    if isinstance(node, (Old, Fresh)):
        return False
    if isinstance(node, HEAP_READS):
        return True
    if isinstance(node, (tuple, list)):
        return any(_reads_heap(x) for x in node)
    if not isinstance(node, Node):
        return False
    return any(_reads_heap(getattr(node, f.name))
               for f in dataclasses.fields(node) if f.name != "line")


def _free_under_two_state(node, name: str, inside: bool) -> bool:
    """True when `name` occurs free in `node` inside an old/fresh/unchanged/
    allocated context."""
    if isinstance(node, Ident):
        return inside and node.name == name
    if isinstance(node, (tuple, list)):
        return any(_free_under_two_state(x, name, inside) for x in node)
    if not isinstance(node, Node):
        return False
    if isinstance(node, (Old, Fresh)):
        return _free_under_two_state(node.arg, name, True)
    if (isinstance(node, Call) and isinstance(node.fn, Ident)
            and node.fn.name in TWO_STATE_CALLS):
        return _free_under_two_state(node.args, name, True)
    b = _binding(node)
    if b is not None:
        names, scoped, unscoped = b
        if any(_free_under_two_state(getattr(node, f), name, inside) for f in unscoped):
            return True
        if name in names:
            return False
        return any(_free_under_two_state(getattr(node, f), name, inside) for f in scoped)
    return any(_free_under_two_state(getattr(node, f.name), name, inside)
               for f in dataclasses.fields(node) if f.name != "line")


@dataclass
class ScopeExpansion:
    """One gradable method and its call-graph closure with their lets lowered:
    the census of what was substituted, and the lets left in place."""
    method: MethodDecl
    closure: tuple
    lets: int = 0
    max_uses: int = 0
    lines: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    nodes_before: int = 0
    nodes_after: int = 0

    def census(self) -> dict:
        """The sidecar's `let_substitution`: {} when nothing was substituted."""
        if not self.lets:
            return {}
        return {"lets": self.lets, "max_uses": self.max_uses,
                "nodes_before": self.nodes_before, "nodes_after": self.nodes_after}


def expand_scope(method: MethodDecl, closure: tuple, method_names: Iterable[str] = ()) -> ScopeExpansion:
    """`expand` over a method and its closure together, so every fresh binder
    name is fresh for the whole scope a later stage renames over."""
    roots = (method,) + tuple(closure)
    used: set[str] = set()
    for r in roots:
        used |= names_in(r)
    acc = Expansion()
    new_roots = [_expand(r, frozenset(method_names), used, acc) for r in roots]
    out = ScopeExpansion(method=new_roots[0], closure=tuple(new_roots[1:]), lets=acc.lets,
                         max_uses=acc.max_uses, lines=list(acc.lines), issues=list(acc.issues))
    if acc.lets:
        out.nodes_before = sum(size(r) for r in roots)
        out.nodes_after = sum(size(r) for r in new_roots)
    return out
