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


def empty_display_types(task: dict, body: list) -> dict:
    """id(node) -> the t type of every empty `[]`/`{}` display a declared type reaches (SPEC.md "Compositional
    types (v1)": the display takes the expected type): a local's or the return's declared type, a param's or a
    local's type on the other side of `==`/`!=`/union/inter/setminus or as the set of an `in`, through pair,
    tuple and seq displays and `ite` branches. A lowering uses it to type an empty display in a kernel whose
    inference will not (Dafny's `{}` under `|..|`, Verus's `Seq::empty()`/`Set::empty()`)."""
    scope = {p["name"]: p["type"] for p in task["params"]}
    scope[task["returns"][0]["name"]] = task["returns"][0]["type"]
    out: dict = {}

    def is_set(t):
        return t == "set" or (isinstance(t, dict) and set(t) == {"set"})

    def is_seq(t):
        return t == "seq" or (isinstance(t, dict) and set(t) == {"seq"})

    def note(e, ty):
        if not isinstance(e, dict) or ty is None:
            return
        if e.get("op") in ("set", "seq") and not e.get("args") and (is_set(ty) if e["op"] == "set" else is_seq(ty)):
            out[id(e)] = ty
        elif e.get("op") in ("pair", "tuple") and isinstance(ty, dict) and (set(ty) == {"pair"} or set(ty) == {"tuple"}):
            for a, t in zip(e["args"], list(ty.values())[0]):
                note(a, t)
        elif e.get("op") == "seq" and is_seq(ty):
            for a in e["args"]:
                note(a, "int" if ty == "seq" else ty["seq"])
        elif "ite" in e:
            note(e["ite"]["then"], ty)
            note(e["ite"]["else"], ty)

    def walk_expr(e, sc):
        # a `==`/`!=`/`in`/union-style use beside a typed name types the other side
        if not isinstance(e, dict):
            return
        if e.get("op") in ("==", "!=", "union", "inter", "diff") and len(e.get("args", [])) == 2:
            a, b = e["args"]
            for x, y in ((a, b), (b, a)):
                if isinstance(x, dict) and "var" in x and x["var"] in sc:
                    note(y, sc[x["var"]])
        if e.get("op") == "in" and len(e.get("args", [])) == 2 and isinstance(e["args"][1], dict) \
                and "var" in e["args"][1] and e["args"][1]["var"] in sc:
            st = sc[e["args"][1]["var"]]
            if is_set(st):
                note(e["args"][0], "int" if st == "set" else st["set"])
        for k in ("args",):
            for a in e.get(k, []) or []:
                walk_expr(a, sc)
        for k in ("ite", "forall", "exists"):
            if k in e:
                for v in e[k].values():
                    walk_expr(v, sc)

    def walk(stmts, sc):
        sc = dict(sc)
        for st in stmts:
            if "var" in st:
                note(st["var"]["init"], st["var"]["type"])
                walk_expr(st["var"]["init"], sc)
                sc[st["var"]["name"]] = st["var"]["type"]
            elif "assign" in st:
                note(st["assign"][1], sc.get(st["assign"][0]))
                walk_expr(st["assign"][1], sc)
            elif "return" in st:
                note(st["return"][1], sc.get(st["return"][0]))
                walk_expr(st["return"][1], sc)
            elif "if" in st:
                walk_expr(st["if"]["cond"], sc)
                walk(st["if"]["then"], sc)
                walk(st["if"]["else"], sc)
            elif "while" in st:
                walk_expr(st["while"]["cond"], sc)
                for inv in st["while"].get("invariants", []):
                    walk_expr(inv, sc)
                walk(st["while"]["body"], sc)
    for e in task.get("requires", []) + task.get("ensures", []):
        walk_expr(e, scope)
    walk(body, scope)
    return out
