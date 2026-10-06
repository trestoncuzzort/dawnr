"""tshape.py: the type shapes a task uses, and which of them a lowering does not carry yet.

SPEC.md "Compositional types (v1)" (2026-10-06) made t's types an algebra: a pair of any two types, tuples, seq<T>
and set<T> over any element type. The seven lowerings carried a fixed list before that day (int, bool, seq, seq<seq>,
a pair of two base types, set, a declared datatype). A lowering that has not yet been written for a shape must
ABSTAIN WITH THE SHAPE NAMED (AGENTS rule 2: an honest refusal beats a false verdict), never emit a kernel source
that happens to typecheck as something else. `abstain_unless_carried(task, body, kernel)` is that refusal: it raises
NotImplementedError naming the first shape beyond the list, which run_par.py routes to the ABSTAIN cell. A lowering
that carries a shape removes it from its `carried` set here, so the matrix in AGREEMENT.md says, kernel by kernel,
what is lowered and what is not.
"""
from __future__ import annotations

V1_PAIR_SIDES = ("int", "bool", "seq")


def shape(t) -> str:
    """A type written as the notation writes it (seq<T>, (T1, T2, ...), set<T>, a datatype's name)."""
    if isinstance(t, dict) and len(t) == 1:
        (kind, inner), = t.items()
        if kind in ("pair", "tuple"):
            return "(%s)" % ", ".join(shape(c) for c in inner)
        if kind in ("seq", "set"):
            return "%s<%s>" % (kind, shape(inner))
        if kind == "datatype":
            return str(inner)
    return str(t)


def beyond_v1(t) -> str | None:
    """The first sub-shape of `t` outside what every lowering carried before 2026-10-06, named, or None."""
    if t in ("int", "bool", "seq", "set") or t == {"seq": "seq"}:
        return None
    if isinstance(t, dict) and len(t) == 1:
        (kind, inner), = t.items()
        if kind == "datatype":
            return None
        if kind == "pair" and all(c in V1_PAIR_SIDES for c in inner):
            return None
        return shape(t)
    return shape(t)


def declared_types(task: dict, body: list) -> list:
    """Every declared type in the task and this body: params, the return, spec_fun params and results, methods'
    and lemmas' params and returns, and every local `var`."""
    out = [p["type"] for p in task.get("params", [])] + [r["type"] for r in task.get("returns", [])]
    for f in task.get("spec_funs", []):
        out += [p["type"] for p in f.get("params", [])] + [f.get("result")]
    for m in task.get("methods", []) + task.get("lemmas", []):
        out += [p["type"] for p in m.get("params", [])] + [r["type"] for r in m.get("returns", [])]

    def walk(stmts):
        for s in stmts:
            if "var" in s:
                out.append(s["var"]["type"])
            elif "if" in s:
                walk(s["if"]["then"])
                walk(s["if"]["else"])
            elif "while" in s:
                walk(s["while"]["body"])
    walk(body)
    for m in task.get("methods", []):
        walk(m.get("body", []))
    return out


def uses_ops(body: list, task: dict, ops: set) -> set:
    """Which of `ops` the task's expressions use (requires, ensures, spec_funs, the body)."""
    found = set()

    def walk(e):
        if isinstance(e, dict):
            if e.get("op") in ops:
                found.add(e["op"])
            for v in e.values():
                walk(v)
        elif isinstance(e, list):
            for v in e:
                walk(v)
    walk(task.get("requires", []))
    walk(task.get("ensures", []))
    walk([f.get("body") for f in task.get("spec_funs", [])])
    walk(body)
    return found


def abstain_unless_carried(task: dict, body: list, kernel: str, carried: set = frozenset()) -> None:
    """Raise NotImplementedError naming the first declared shape beyond the pre-2026-10-06 list that `kernel`
    does not carry (`carried`: shape strings this lowering handles, as `shape()` writes them, or the wildcard
    "*" when it handles every shape), or the first tuple/proj operator when the kernel carries no tuples."""
    if "*" in carried:
        return
    for t in declared_types(task, body):
        s = beyond_v1(t)
        if s is not None and s not in carried:
            raise NotImplementedError(f"{kernel}: the type {s} is not lowered yet (SPEC.md 'Compositional types (v1)')")
    if not any(c.startswith("(") for c in carried):
        used = uses_ops(body, task, {"tuple", "proj"})
        if used:
            raise NotImplementedError(f"{kernel}: {', '.join(sorted(used))} is not lowered yet (SPEC.md 'Compositional types (v1)')")
