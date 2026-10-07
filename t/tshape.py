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

import copy

V1_PAIR_SIDES = ("int", "bool", "seq")


def shape(t) -> str:
    """A type written as the notation writes it (seq<T>, (T1, T2, ...), set<T>, a datatype's name)."""
    if isinstance(t, dict) and len(t) == 1:
        (kind, inner), = t.items()
        if kind in ("pair", "tuple"):
            return "(%s)" % ", ".join(shape(c) for c in inner)
        if kind in ("seq", "set"):
            return "%s<%s>" % (kind, shape(inner))
        if kind == "map":
            return "map<%s, %s>" % (shape(inner[0]), shape(inner[1]))   # SPEC.md "Maps (v1)" (2026-10-06)
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


def abstain_unless_carried(task: dict, body: list, kernel: str, carried: set = frozenset(),
                           lib: frozenset = frozenset()) -> None:
    """Raise NotImplementedError naming the first declared shape beyond the pre-2026-10-06 list that `kernel`
    does not carry (`carried`: shape strings this lowering handles, as `shape()` writes them, or the wildcard
    "*" when it handles every shape), or the first tuple/proj operator when the kernel carries no tuples."""
    body = body or []   # a lowering is called with body=None for a task whose ladder found no twin (lean's methods probe)
    if "*" in carried:
        if "real" not in carried:
            abstain_on_reals(task, body, kernel)
        return
    for t in declared_types(task, body):
        s = beyond_v1(t)
        if s is not None and s not in carried:
            raise NotImplementedError(f"{kernel}: the type {s} is not lowered yet (SPEC.md 'Compositional types (v1)')")
    if not any(c.startswith("(") for c in carried):
        used = uses_ops(body, task, {"tuple", "proj"})
        if used:
            raise NotImplementedError(f"{kernel}: {', '.join(sorted(used))} is not lowered yet (SPEC.md 'Compositional types (v1)')")
    if "real" not in carried:
        abstain_on_reals(task, body, kernel)
    abstain_on_library(task, body, kernel, lib)
    if "comp" not in carried and has_comprehension(task, body, under_reduction_ok="comp-reduction" in carried):
        raise NotImplementedError(f"{kernel}: comprehensions are not lowered yet (SPEC.md 'Comprehensions (v1)')")
    if "exit" not in carried:
        abstain_on_exits(task, body, kernel)
    if "strlib2" not in carried and strlib2_used(task, body):
        raise NotImplementedError(f"{kernel}: the string library's second wave is not lowered yet "
                                  f"(SPEC.md 'The string library (v2)')")
    if "collection-quant" not in carried and collection_quantified(task, body):
        raise NotImplementedError(f"{kernel}: a quantifier over a set's or seq's elements is not lowered yet "
                                  f"(SPEC.md 'Quantifiers over a collection')")


def desugar_seq_quants(task: dict, body: list) -> tuple[dict, list]:
    """SPEC.md "Quantifiers over a collection" (2026-10-07): `forall x in S . P` over a SEQ S is exact sugar for
    `forall i in [0, len(S)) . P[x := S[i]]`, the index form every kernel's automation is built around (a membership
    range over a seq leaves Dafny and Verus a witness index to find, measured on a loop probe). Rewritten here, before
    any lowering sees the task, so all seven state it; a set range is left as it is. Returns (task, body) themselves
    when nothing is rewritten, so a task with no such quantifier lowers byte for byte as before."""
    import check_wf
    funs = {f["name"]: f for f in task.get("spec_funs", [])}
    dtypes = {d["name"]: d for d in task.get("datatypes", [])}
    taken = set()

    def names(x):
        if isinstance(x, dict):
            for v in x.values():
                names(v)
        elif isinstance(x, list):
            for v in x:
                names(v)
        elif isinstance(x, str):
            taken.add(x)
    names(task)
    names(body)
    ctr = [0]

    def fresh() -> str:
        while True:
            ctr[0] += 1
            n = f"qi{ctr[0]}"
            if n not in taken:
                taken.add(n)
                return n

    def sub(x, m: dict):
        if isinstance(x, list):
            return [sub(v, m) for v in x]
        if not isinstance(x, dict):
            return x
        if "var" in x and isinstance(x["var"], str) and len(x) == 1:
            return m.get(x["var"], x)
        for k in ("forall", "exists"):
            if isinstance(x.get(k), dict):
                q = x[k]
                inner = {a: b for a, b in m.items() if a != q["var"]}
                return {k: {kk: (sub(vv, inner) if kk == "body" else sub(vv, m) if kk != "var" else vv)
                            for kk, vv in q.items()}}
        if "comp" in x:
            c = x["comp"]
            inner = {a: b for a, b in m.items() if a != c["var"]}
            return {"comp": {kk: (sub(vv, inner) if kk in ("cond", "body") else sub(vv, m) if kk != "var" else vv)
                             for kk, vv in c.items()}}
        if "lam" in x:
            inner = {a: b for a, b in m.items() if a not in x["lam"]["vars"]}
            return {"lam": {"vars": x["lam"]["vars"], "body": sub(x["lam"]["body"], inner)}}
        if "match" in x:
            mm = x["match"]
            return {"match": {"scrutinee": sub(mm["scrutinee"], m),
                              "arms": [{**a, "body": sub(a["body"], {k: v for k, v in m.items()
                                                                        if k not in (a.get("binders") or [])})}
                                       for a in mm["arms"]]}}
        return {k: sub(v, m) for k, v in x.items()}

    def walk(x, env: dict):
        if isinstance(x, list):
            return [walk(v, env) for v in x]
        if not isinstance(x, dict):
            return x
        for k in ("forall", "exists"):
            if isinstance(x.get(k), dict) and "in" in x[k]:
                q = x[k]
                rng = walk(q["in"], env)
                try:
                    rt, errs = check_wf.expression_type(rng, dict(env), functions=funs, datatypes=dtypes)
                except Exception:                     # noqa: BLE001  (an untypeable range stays as written)
                    rt, errs = None, ["?"]
                is_seq = not errs and (rt == "seq" or (isinstance(rt, dict) and set(rt) == {"seq"}))
                el = ("int" if rt == "seq" else rt["seq"]) if is_seq else "int"
                body = walk(q["body"], {**env, q["var"]: el})
                if not is_seq:
                    return {k: {"var": q["var"], "in": rng, "body": body}}
                i = fresh()
                return {k: {"var": i, "lo": {"int": 0}, "hi": {"op": "len", "args": [rng]},
                            "body": sub(body, {q["var"]: {"op": "at", "args": [rng, {"var": i}]}})}}
        return {kk: walk(vv, env) for kk, vv in x.items()}

    if not collection_quantified(task, body):
        return task, body
    env = {p["name"]: p["type"] for p in task["params"]}
    env.update({r["name"]: r["type"] for r in task["returns"]})

    def locals_of(stmts):
        for st in stmts or []:
            if isinstance(st, dict):
                if "var" in st and isinstance(st["var"], dict):
                    env.setdefault(st["var"]["name"], st["var"]["type"])
                for v in st.values():
                    if isinstance(v, (list, dict)):
                        locals_of(v if isinstance(v, list) else [v])
    locals_of(body)
    new = dict(task)
    for k in ("requires", "ensures", "decreases"):
        if k in task:
            new[k] = walk(task[k], env)
    new["spec_funs"] = [{**f, "body": walk(f["body"], {**env, **{p["name"]: p["type"] for p in f["params"]}})}
                        for f in task.get("spec_funs", [])]
    if "spec_funs" not in task:
        del new["spec_funs"]
    for key in ("lemmas", "methods"):
        if key in task:
            new[key] = [walk(x, {**env, **{p["name"]: p["type"] for p in x.get("params", [])}}) for x in task[key]]
    new_body = walk(body, env)
    if "body" in task:
        # the real body stays the same object as task["body"]: a lowering tells real from twin by identity
        new["body"] = new_body if body is task["body"] else walk(task["body"], env)
    return new, new_body


def collection_quantified(task: dict, body: list) -> bool:
    """Does any quantifier in the task or body range over a set's or seq's elements (SPEC.md "Quantifiers over a
    collection", 2026-10-07)?"""
    def walk(x) -> bool:
        if isinstance(x, dict):
            for k in ("forall", "exists"):
                if isinstance(x.get(k), dict) and "in" in x[k]:
                    return True
            return any(walk(v) for v in x.values())
        if isinstance(x, list):
            return any(walk(v) for v in x)
        return False
    return walk(body) or walk({k: v for k, v in task.items() if k != "body"})


LIB_OPS = frozenset({"min", "max", "abs", "sum", "gcd", "pow", "isqrt", "rev", "sort",
                     "any", "all", "toset",    # SPEC.md "Reductions (v1)" (2026-10-06)
                     "isint", "toint",         # SPEC.md "The string library (v2)" (2026-10-06)
                     "fold", "sort_by", "max_by", "min_by"})   # SPEC.md "Higher-order calls (v1)" (2026-10-06)
STRLIB2_OPS = frozenset({"index", "rfind", "zfill", "center", "ljust", "rjust", "capitalize", "swapcase", "title",
                         "isspace", "isalnum", "splitlines", "partition"})


def _scope_of(task: dict, body: list) -> dict:
    """name -> declared type over params, the return, locals anywhere and spec_fun params (shadowing ignored)."""
    out = {p["name"]: ("seq" if p["type"] == "array" else p["type"]) for p in task.get("params", [])}   # Heap (v1)
    for r in task.get("returns", []):
        out[r["name"]] = r["type"]
    for f in task.get("spec_funs", []):
        for p in f.get("params", []):
            out.setdefault(p["name"], p["type"])

    def walk(stmts):
        for st in stmts or []:
            if "var" in st:
                out[st["var"]["name"]] = st["var"]["type"]
            elif "if" in st:
                walk(st["if"]["then"])
                walk(st["if"]["else"])
            elif "while" in st:
                walk(st["while"]["body"])
    walk(body)
    for m in task.get("methods", []):
        walk(m.get("body", []))
    return out


def seq_membership_used(task: dict, body: list) -> bool:
    """Whether an `in` node's right operand is a seq (SPEC.md "The library (v1)": membership in a seq), typed
    with check_wf under the task's declared names; an operand that cannot be typed reads as not a seq."""
    import check_wf
    scope = _scope_of(task, body)
    funs = {f["name"]: f for f in task.get("spec_funs", [])}
    found = []

    def walk(e):
        if isinstance(e, dict):
            if e.get("op") == "in" and len(e.get("args", [])) == 2:
                try:
                    t, errs = check_wf.expression_type(e["args"][1], dict(scope), functions=funs)
                except Exception:                           # noqa: BLE001
                    t = None
                if t == "seq" or (isinstance(t, dict) and "seq" in t):
                    found.append(e)
            for v in e.values():
                walk(v)
        elif isinstance(e, list):
            for v in e:
                walk(v)
    walk(task.get("requires", []))
    walk(task.get("ensures", []))
    walk([f.get("body") for f in task.get("spec_funs", [])])
    walk(body or [])
    return bool(found)


def abstain_on_library(task: dict, body: list, kernel: str, carried: frozenset = frozenset()) -> None:
    """Raise NotImplementedError naming the first library function (SPEC.md "The library (v1)", 2026-10-06) the
    task uses that `kernel` does not carry (`carried`: the op names its lowering emits definitions for, and
    "in" when it carries membership in a seq)."""
    used = sorted(uses_ops(body or [], task, LIB_OPS - set(carried)))
    if used:
        raise NotImplementedError(f"{kernel}: {', '.join(used)} is not lowered yet (SPEC.md 'The library (v1)')")
    if "maxs" not in carried and _extrema_of_one(task, body):
        # SPEC.md "Reductions (v1)" (2026-10-06): max(s)/min(s) of one argument are their own library shape
        raise NotImplementedError(f"{kernel}: max/min of one argument are not lowered yet (SPEC.md 'Reductions (v1)')")
    if "in" not in carried and seq_membership_used(task, body):
        raise NotImplementedError(f"{kernel}: membership in a seq is not lowered yet (SPEC.md 'The library (v1)')")


def _extrema_of_one(task: dict, body: list) -> bool:
    """Whether a max(s) or min(s) of one argument occurs in the body or the task's spec (SPEC.md "Reductions (v1)")."""
    def walk(x) -> bool:
        if isinstance(x, dict):
            if x.get("op") in ("min", "max") and len(x.get("args", [])) == 1:
                return True
            return any(walk(v) for v in x.values())
        return isinstance(x, list) and any(walk(v) for v in x)
    return walk(body or []) or walk(task.get("requires", [])) or walk(task.get("ensures", [])) \
        or walk(task.get("spec_funs", [])) or walk(task.get("methods", []))


def strlib2_used(task: dict, body: list) -> bool:
    """Whether the task uses a second-wave string member (SPEC.md "The string library (v2)", 2026-10-06): one of
    STRLIB2_OPS, a strip with a character set, or a split with a sequence separator (told by the argument's type)."""
    import check_wf
    scope = _scope_of(task, body)
    funs = {f["name"]: f for f in task.get("spec_funs", [])}

    def walk(x) -> bool:
        if isinstance(x, dict):
            op, args = x.get("op"), x.get("args", [])
            if op in STRLIB2_OPS:
                return True
            if op in ("strip", "lstrip", "rstrip") and len(args) == 2:
                return True
            if op == "split" and len(args) == 2:
                try:
                    t, errs = check_wf.expression_type(args[1], dict(scope), functions=funs)
                except Exception:                           # noqa: BLE001
                    t, errs = None, ["?"]
                if not errs and t == "seq":
                    return True
            return any(walk(v) for v in x.values())
        return isinstance(x, list) and any(walk(v) for v in x)
    return walk(body or []) or walk(task.get("requires", [])) or walk(task.get("ensures", [])) \
        or walk(task.get("spec_funs", [])) or walk(task.get("methods", []))


def has_exit(task: dict, body: list) -> bool:
    """Whether this body or a method's holds a `break`, a `continue` or a `while true` (SPEC.md "Early exits (v1)",
    2026-10-06)."""
    def walk(x) -> bool:
        if isinstance(x, dict):
            if "break" in x or "continue" in x:
                return True
            if "while" in x and isinstance(x["while"], dict) and x["while"].get("cond") == {"bool": True}:
                return True
            return any(walk(v) for v in x.values())
        return isinstance(x, list) and any(walk(v) for v in x)
    return walk(body or []) or walk(task.get("methods", []))


def _rename_var(x, old: str, new: str):
    if isinstance(x, list):
        return [_rename_var(v, old, new) for v in x]
    if not isinstance(x, dict):
        return x
    if x.get("var") == old:
        return {**x, "var": new}
    return {k: _rename_var(v, old, new) for k, v in x.items()}


def desugar_par(task: dict, body: list) -> tuple:
    """SPEC.md "Concurrency (v1)" (PREDICT T47): each `parallel for i in [lo, hi)` as the sequential `for` it equals
    under `par-race`: `var i := lo; while i < hi invariant lo <= i and i <= hi, ... decreases hi - i { body;
    i := i + 1; }`. The index is renamed when another declaration in the body already has its name, so two parallel
    loops in one block declare two variables. The real body stays the same object as task["body"]."""
    def has(x) -> bool:
        if isinstance(x, dict):
            return "par" in x or any(has(v) for v in x.values())
        return isinstance(x, list) and any(has(v) for v in x)
    if not has(body or []) and not has(task.get("body") or []):
        return task, body
    names: set = set()

    def declared(x):
        if isinstance(x, dict):
            if "var" in x and isinstance(x["var"], dict):
                names.add(x["var"]["name"])
            if "par" in x and isinstance(x["par"], dict):
                names.add(x["par"]["var"])
            for v in x.values():
                declared(v)
        elif isinstance(x, list):
            for v in x:
                declared(v)
    counter = [0]

    def one(stmts: list) -> list:
        out = []
        for st in stmts:
            if "par" in st:
                w = st["par"]
                counter[0] += 1
                i = w["var"]
                if i in seen:
                    i2 = f"{i}_p{counter[0]}"
                    w = _rename_var(w, i, i2)
                    w["var"] = i2
                    i = i2
                seen.add(i)
                iv = {"var": i}
                out.append({"var": {"name": i, "type": "int", "init": copy.deepcopy(w["lo"])}})
                out.append({"while": {
                    "cond": {"op": "<", "args": [iv, copy.deepcopy(w["hi"])]},
                    "invariants": [{"op": "<=", "args": [copy.deepcopy(w["lo"]), iv]},
                                   {"op": "<=", "args": [iv, copy.deepcopy(w["hi"])]}] + copy.deepcopy(w["invariants"]),
                    "decreases": {"op": "-", "args": [copy.deepcopy(w["hi"]), iv]},
                    "body": one(copy.deepcopy(w["body"])) + [{"assign": [i, {"op": "+", "args": [iv, {"int": 1}]}]}]}})
            elif "if" in st:
                f = st["if"]
                out.append({"if": {**f, "then": one(f["then"]), "else": one(f.get("else", []))}})
            elif "while" in st:
                out.append({"while": {**st["while"], "body": one(st["while"]["body"])}})
            else:
                if "var" in st and isinstance(st["var"], dict):
                    seen.add(st["var"]["name"])
                out.append(st)
        return out
    seen: set = {p["name"] for p in task.get("params", [])} | {r["name"] for r in task.get("returns", [])}
    new_body = one(body or [])
    new = dict(task)
    if "body" in task:
        seen = {p["name"] for p in task.get("params", [])} | {r["name"] for r in task.get("returns", [])}
        counter[0] = 0
        new["body"] = new_body if body is task["body"] else one(task["body"])
    return new, new_body


def has_float(task: dict, body: list) -> bool:
    """Whether the task or this body names the float type or a float operation (SPEC.md "Floats (v1)", PREDICT T48)."""
    def ftype(t) -> bool:
        if t == "float":
            return True
        if isinstance(t, dict):
            return any(ftype(v) for v in t.values())
        return isinstance(t, list) and any(ftype(v) for v in t)

    def walk(x) -> bool:
        if isinstance(x, dict):
            if ftype(x.get("type")) or ftype(x.get("result")) or x.get("op") in ("float", "sqrt"):
                return True
            return any(walk(v) for v in x.values())
        return isinstance(x, list) and any(walk(v) for v in x)
    return walk([task.get("params"), task.get("returns"), task.get("requires"), task.get("ensures"),
                 task.get("spec_funs"), task.get("methods"), task.get("lemmas"), body or []])


def abstain_on_floats(task: dict, body: list, kernel: str) -> None:
    if has_float(task, body):
        raise NotImplementedError(f"{kernel}: floats are not lowered yet (SPEC.md 'Floats (v1)')")


def has_heap(task: dict) -> bool:
    """Whether the task has an array parameter (SPEC.md "Heap (v1)", PREDICT T46)."""
    return any(p.get("type") == "array" for p in task.get("params", []))


def abstain_on_heap(task: dict, kernel: str) -> None:
    if has_heap(task):
        raise NotImplementedError(f"{kernel}: arrays by reference are not lowered yet (SPEC.md 'Heap (v1)')")


def abstain_on_exits(task: dict, body: list, kernel: str) -> None:
    if has_exit(task, body):
        raise NotImplementedError(f"{kernel}: break, continue and while-true loops are not lowered yet "
                                  f"(SPEC.md 'Early exits (v1)')")


# PREDICT T44: `break` and `continue` rewritten away, once for every kernel that writes a loop as a recursive function
# and already carries `return` inside a loop (SPEC.md "Early exit (v1)"). Receipt 28d3ddecb054.
# - `continue` ends the iteration: what follows it on its path never runs, so the rest of the body moves into the
#   other branch of each `if` on that path (`_skip_rest`). The iteration ends in the same state, where the invariants
#   and `decreases` are owed exactly as at the `continue`.
# - `break` leaves the loop, and what runs next is the loop's continuation: the rest of the task body after it. So a
#   `break` becomes that continuation followed by `return` (`_walk`); a `return` inside a loop owes the task's
#   `ensures` and not the invariant, which is the `break` rule. A loop inside another loop's body has the rest of that
#   body and then the next iteration as its continuation, which no statement list says; its `break` is refused by
#   name, unless the rest of that body ends in `return` and holds no `continue`.
# `while true` is left as it is. The rewrite is checked against the interpreter (test_exits_desugar.py).

def _is_exit(s: dict, key: str) -> bool:
    return isinstance(s, dict) and key in s and s[key] is True


def _level_has(stmts: list, key: str) -> bool:
    """Whether `stmts` holds a `break`/`continue` of the loop whose body they are in: through `if`s, never inside a
    nested loop."""
    for s in stmts:
        if _is_exit(s, key):
            return True
        if "if" in s and (_level_has(s["if"]["then"], key) or _level_has(s["if"].get("else", []), key)):
            return True
    return False


def _ends(stmts: list) -> bool:
    """Whether control never runs past the end of `stmts`: it ends in `return`, or in an `if` whose branches both do."""
    if not stmts:
        return False
    s = stmts[-1]
    if "return" in s:
        return True
    return "if" in s and _ends(s["if"]["then"]) and _ends(s["if"].get("else", []))


def _walk(stmts: list, cont, brk, ret: str) -> list:
    """`stmts` with every `break` replaced. `cont`: the statements that run after `stmts` up to the task's end, or None
    inside a loop body, where it is unknown. `brk`: what a `break` at this level becomes, or None outside any loop."""
    out = []
    for i, s in enumerate(stmts):
        rest = stmts[i + 1:]
        if cont is not None:
            here = rest + cont
        else:
            here = rest if _ends(rest) and not _level_has(rest, "continue") else None
        if _is_exit(s, "break"):
            if brk is None:
                raise NotImplementedError(
                    "a `break` of a loop nested in another loop's body (SPEC.md 'Early exits (v1)', PREDICT T44): its "
                    "continuation is the rest of the outer iteration, which this lowering does not write as statements")
            return out + brk
        if "if" in s:
            f = s["if"]
            out.append({"if": {**f, "then": _walk(f["then"], here, brk, ret),
                               "else": _walk(f.get("else", []), here, brk, ret)}})
        elif "while" in s:
            w = s["while"]
            inner = None
            if here is not None:
                k = _walk(copy.deepcopy(here), [], brk, ret)
                if not _ends(k):
                    # the continuation's last assignment to the return name becomes the `return` itself
                    last = k[-1] if k else None
                    if last is not None and "assign" in last and last["assign"][0] == ret:
                        k = k[:-1] + [{"return": [ret, last["assign"][1]]}]
                    else:
                        k = k + [{"return": [ret, {"var": ret}]}]
                inner = k
            out.append({"while": {**w, "body": _walk(w["body"], None, inner, ret)}})
        else:
            out.append(s)
    return out


def _skip_rest(stmts: list, rest: list) -> list:
    """`stmts` followed by `rest`, where a `continue` at this level skips everything after it, `rest` included."""
    out = []
    for i, s in enumerate(stmts):
        if _is_exit(s, "continue"):
            return out
        if "return" in s:
            return out + [s]
        if "if" in s and _level_has([s], "continue"):
            k = _skip_rest(stmts[i + 1:], rest)
            f = s["if"]
            return out + [{"if": {**f, "then": _skip_rest(f["then"], k), "else": _skip_rest(f.get("else", []), k)}}]
        out.append(s)
    return out if _ends(out) else out + rest


def _continues(stmts: list) -> list:
    out = []
    for s in stmts:
        if out and "while" in out[-1] and out[-1]["while"].get("cond") == {"bool": True}:
            # after the rewrite a `while true` has no `break` left, so nothing after it runs: the statements are
            # dropped (measured: Frama-C's smoke test flags the dead `r := i` after find_zero's loop)
            break
        if "if" in s:
            f = s["if"]
            out.append({"if": {**f, "then": _continues(f["then"]), "else": _continues(f.get("else", []))}})
        elif "while" in s:
            w = s["while"]
            out.append({"while": {**w, "body": _skip_rest(_continues(w["body"]), [])}})
        else:
            out.append(s)
    return out


def desugar_exits(task: dict, body: list) -> tuple:
    """(task, body) with no `break` and no `continue` in `body` or in `task["body"]` (PREDICT T44, the comment above), or
    both as they are when `body` has neither. The real body stays the same object as `task["body"]`, as
    `desugar_seq_quants` keeps it: a lowering tells real from twin by identity. A method body with either, or a `break`
    in a task of several returns, is refused by name."""
    def any_exit(x) -> bool:
        if isinstance(x, dict):
            return _is_exit(x, "break") or _is_exit(x, "continue") or any(any_exit(v) for v in x.values())
        return isinstance(x, list) and any(any_exit(v) for v in x)
    if not any_exit(body or []) and not any_exit(task.get("body") or []):
        return task, body
    if any_exit(task.get("methods", [])):
        raise NotImplementedError("a `break` or `continue` in a method body is not lowered yet "
                                  "(SPEC.md 'Early exits (v1)', PREDICT T44)")
    if len(task["returns"]) != 1:
        raise NotImplementedError("a `break` in a task with several returns: `return` names one "
                                  "(SPEC.md 'Early exits (v1)', PREDICT T44)")
    import check_wf

    def one(b: list) -> list:
        if not any_exit(b or []):
            return b
        out = _continues(_walk(copy.deepcopy(b), [], None, task["returns"][0]["name"]))
        errs = check_wf.check_wf({**task, "body": out})
        if errs and not check_wf.check_wf({**task, "body": b}):
            raise NotImplementedError(
                f"the rewrite of `break`/`continue` (PREDICT T44) gives an ill-formed body: {errs[0]}")
        return out
    new_body = one(body)
    new = dict(task)
    if "body" in task:
        new["body"] = new_body if body is task["body"] else one(task["body"])
    return new, new_body


def has_comprehension(task: dict, body: list, under_reduction_ok: bool = False) -> bool:
    """Whether the task or this body holds a `comp` node (SPEC.md "Comprehensions (v1)", 2026-10-06). With
    `under_reduction_ok`, a comprehension over a seq that is the one argument of any/all does not count (a kernel that
    states any/all over a predicate carries it, SPEC.md "Reductions (v1)"); one inside its parts still does."""
    def walk(x) -> bool:
        if isinstance(x, dict):
            a = x.get("args", [])
            if (under_reduction_ok and x.get("op") in ("any", "all") and len(a) == 1 and isinstance(a[0], dict)
                    and "comp" in a[0] and "seq" in a[0]["comp"]):
                c = a[0]["comp"]
                return walk(c["seq"]) or walk(c["cond"]) or walk(c["body"])
            return "comp" in x or any(walk(v) for v in x.values())
        return isinstance(x, list) and any(walk(v) for v in x)
    return walk(body or []) or walk(task.get("requires", [])) or walk(task.get("ensures", [])) \
        or walk(task.get("spec_funs", [])) or walk(task.get("methods", []))


def mentions_real(t) -> bool:
    """Whether a type is `real` or has a `real` component or element anywhere."""
    if t == "real":
        return True
    if isinstance(t, dict):
        return any(mentions_real(c) for v in t.values() for c in (v if isinstance(v, list) else [v]))
    return False


def abstain_on_reals(task: dict, body: list, kernel: str) -> None:
    """Raise NotImplementedError naming reals when the task declares a real anywhere, uses real(x)/floor/ceil, or
    writes a real literal (SPEC.md "Exact rationals (v1)", 2026-10-06): a kernel with no exact rationals, or one
    whose lowering is not written yet, abstains by name rather than emit a source that typechecks as something
    else."""
    body = body or []
    if any(mentions_real(t) for t in declared_types(task, body)):
        raise NotImplementedError(f"{kernel}: real numbers are not lowered yet (SPEC.md 'Exact rationals (v1)')")
    used = uses_ops(body, task, {"toreal", "floor", "ceil"})

    def has_rat(x):
        if isinstance(x, dict):
            return "rat" in x or any(has_rat(v) for v in x.values())
        return isinstance(x, list) and any(has_rat(v) for v in x)
    if used or has_rat(body) or has_rat(task.get("ensures", [])) or has_rat(task.get("requires", [])) \
            or has_rat(task.get("spec_funs", [])):
        raise NotImplementedError(f"{kernel}: real numbers are not lowered yet (SPEC.md 'Exact rationals (v1)')")

def empty_display_types(task: dict, body: list) -> dict:
    """id(node) -> the t type of every empty `[]`/`{}` display a declared type reaches (SPEC.md "Compositional
    types (v1)": the display takes the expected type): a local's or the return's declared type, a param's or a
    local's type on the other side of `==`/`!=`/union/inter/setminus or as the set of an `in`, through pair,
    tuple and seq displays and `ite` branches. A lowering uses it to type an empty display in a kernel whose
    inference will not (Dafny's `{}` under `|..|`, Verus's `Seq::empty()`/`Set::empty()`)."""
    body = body or []
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
        elif e.get("op") == "mapdisp" and not e.get("args") and isinstance(ty, dict) and set(ty) == {"map"}:
            out[id(e)] = ty          # SPEC.md "Maps (v1)" (2026-10-06): map[] takes the expected map type
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
