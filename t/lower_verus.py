#!/usr/bin/env python3
"""lower_verus.py: lower t tasks (v0 and v1) to Verus; the second kernel.

THE SEMANTIC DECISION, made with a witness rather than by silence: t
integers are mathematical integers. Verus's `int` type IS mathematical, but
only in ghost/proof code; executable code uses machine ints with overflow
obligations. So every t task lowers to `proof fn`, which preserves t's
semantics exactly; the exec/i64 arm (with explicit range obligations) is a
later gate, opened when t grows machine-int types. Choosing exec now would
silently change what a t task MEANS between Dafny (int = mathematical) and
Verus, exactly the class of cross-backend semantic drift t exists to
surface, not commit.

v1 additions, and the two decisions they forced (both measured, not guessed):

LOOPS. Verus refuses `while` in proof mode ("cannot use while in proof or
spec mode", measured on 0.2026.08.30). Machine-checked iteration in ghost
code is done by recursion, so each t `while` is lowered to a recursive
helper proof fn, with requires = the invariants and ensures = the invariants over
the returned state plus the negated guard, decreases = the loop's own
measure. That IS t's loop rule (SPEC.md gate 2), enforced modularly: the
caller proves the invariants on entry (call-site requires), the helper
proves one iteration preserves them (recursive call's requires) and that
the measure is nonnegative and strictly decreasing (Verus's decreases
check), and after the loop the caller knows exactly invariants + !guard
(the helper's ensures, since proof fns are opaque) and nothing more. No exec
arm, no machine ints, no semantic drift.

DEFINEDNESS. Verus spec code is total: `Seq::index` out of bounds is an
unspecified value guarded only by `recommends`, which the kernel does not
enforce. A lowering that leaned on that would silently totalize `at`,
which SPEC.md declares wrong. So this lowering computes the definedness
condition D(e) of every expression it emits, the exact left-to-right
short-circuit rules of SPEC.md "Definedness", and makes Verus discharge
it: as an `assert` immediately before each body statement that needs one
(where the kernel has the path facts, guard, and invariants in context),
and as standalone well-formedness lemmas for spec positions (each requires
clause assuming the earlier ones; each ensures clause assuming requires
and earlier ensures; each loop invariant assuming the earlier invariants
in its list; each spec_fun body universally). Trivial conditions simplify
to true and are not emitted, so v0 output is untouched.

Body lowering: v0 tasks keep the original expression-oriented lowering,
byte-identical. v1 tasks lower as statements: returns become
definite-assignment `let mut` locals, the final expression returns the
return name, spec_funs become `spec fn ... decreases`, and a
self-recursive body becomes a recursive proof fn carrying the task's own
decreases measure.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                                   # noqa: E402
from verifiers import verus as verus_backend     # noqa: E402

BIN_OPS = {"==": "==", "!=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">=",
           "+": "+", "-": "-", "*": "*", "implies": "==>"}
NARY_OPS = {"and": "&&", "or": "||"}
TYPES = {"int": "int", "bool": "bool", "seq": "Seq<int>"}


_SUFFIX_INT = False   # v1 only: literals as `(7int)` so ite branches infer
                      # (measured: bare `1` in an ite arm is E0283); v0
                      # output stays byte-identical with bare literals.


def expr(e: dict) -> str:
    if "_seq" in e:
        # Private ground node, emitted only by the refutation certificate
        # builder below: a concrete Seq<int> literal from a measured witness.
        if not e["_seq"]:
            return "Seq::<int>::empty()"
        return "seq![" + ", ".join(f"({v}int)" for v in e["_seq"]) + "]"
    if "int" in e:
        return f"({e['int']}int)" if _SUFFIX_INT else str(e["int"])
    if "var" in e:
        return e["var"]
    if "bool" in e:
        return "true" if e["bool"] else "false"
    if "ite" in e:
        c = e["ite"]
        return (f"(if {expr(c['cond'])} {{ {expr(c['then'])} }}"
                f" else {{ {expr(c['else'])} }})")
    if "call" in e:
        c = e["call"]
        return f"{c['fun']}(" + ", ".join(expr(a) for a in c["args"]) + ")"
    if "forall" in e or "exists" in e:
        kind = "forall" if "forall" in e else "exists"
        q = e[kind]
        v, lo, hi, body = q["var"], expr(q["lo"]), expr(q["hi"]), expr(q["body"])
        rng = f"({lo} <= {v} && {v} < {hi})"
        if kind == "forall":
            return f"(forall|{v}: int| {rng} ==> {body})"
        return f"(exists|{v}: int| {rng} && {body})"
    op, args = e["op"], [expr(a) for a in e.get("args", [])]
    if op == "neg":
        return f"(-{args[0]})"
    if op == "not":
        return f"(!{args[0]})"
    if op == "len":
        return f"({args[0]}.len() as int)"
    if op == "at":
        return f"{args[0]}[{args[1]}]"
    if op in NARY_OPS:
        return "(" + f" {NARY_OPS[op]} ".join(args) + ")"
    if op in BIN_OPS:
        return f"({args[0]} {BIN_OPS[op]} {args[1]})"
    raise ValueError(f"t has no operator {op!r}")


# ----------------------------------------------------------------- v0 path
# byte-identical to the original lowering for "t": 0 tasks.

def body_expr(body: list, ret: str) -> str:
    """Statement body -> Verus expression, or refuse."""
    if len(body) == 1 and "assign" in body[0]:
        name, e = body[0]["assign"]
        assert name == ret, f"assign to {name}, expected {ret}"
        return expr(e)
    if len(body) == 1 and "if" in body[0]:
        c = body[0]["if"]
        return (f"if {expr(c['cond'])} {{ {body_expr(c['then'], ret)} }}"
                f" else {{ {body_expr(c['else'], ret)} }}")
    raise ValueError("t v0 -> verus: body not expressible as one expression")


def lower_v0(task: dict, body: list, witness: dict | None = None) -> str:
    ps = ", ".join(f"{p['name']}: int" for p in task["params"])
    r = task["returns"][0]["name"]
    ensures = ",\n        ".join(expr(e) for e in task["ensures"])
    requires = ",\n        ".join(expr(e) for e in task.get("requires", []))
    req = f"    requires\n        {requires}\n" if requires else ""
    return (
        "use vstd::prelude::*;\n\nverus! {\n\n"
        f"proof fn {task['name']}({ps}) -> ({r}: int)\n"
        f"{req}    ensures\n        {ensures},\n"
        "{\n"
        f"    {body_expr(body, r)}\n"
        "}\n\n} // verus!\n\nfn main() {}\n")


# -------------------------------------------------- definedness conditions
# D(e) per SPEC.md "Definedness": the exact left-to-right short-circuit
# rules, computed as a t expression so it is lowered by the same expr().

TRUE = {"bool": True}


def _conj(parts: list) -> dict:
    parts = [p for p in parts if p != TRUE]
    if not parts:
        return TRUE
    if len(parts) == 1:
        return parts[0]
    return {"op": "and", "args": parts}


def _guard(p: dict, q: dict) -> dict:
    """q need only be defined when p holds."""
    if q == TRUE:
        return TRUE
    return {"op": "implies", "args": [p, q]}


def defined(e: dict) -> dict:
    if "int" in e or "var" in e or "bool" in e:
        return TRUE
    if "ite" in e:
        c = e["ite"]
        dt, de = defined(c["then"]), defined(c["else"])
        branch = (TRUE if dt == TRUE and de == TRUE
                  else {"ite": {"cond": c["cond"], "then": dt, "else": de}})
        return _conj([defined(c["cond"]), branch])
    if "call" in e:
        return _conj([defined(a) for a in e["call"]["args"]])
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        db = defined(q["body"])
        body_ob = (TRUE if db == TRUE else
                   {"forall": {"var": q["var"], "lo": q["lo"], "hi": q["hi"],
                               "body": db}})
        return _conj([defined(q["lo"]), defined(q["hi"]), body_ob])
    op, args = e["op"], e.get("args", [])
    if op == "at":
        s, i = args
        bound = {"op": "and", "args": [
            {"op": "<=", "args": [{"int": 0}, i]},
            {"op": "<", "args": [i, {"op": "len", "args": [s]}]}]}
        return _conj([defined(s), defined(i), bound])
    if op == "and":
        res = TRUE
        for a in reversed(args):
            res = _conj([defined(a), _guard(a, res)])
        return res
    if op == "or":
        res = TRUE
        for a in reversed(args):
            res = _conj([defined(a), _guard({"op": "not", "args": [a]}, res)])
        return res
    if op == "implies":
        p, q = args
        return _conj([defined(p), _guard(p, defined(q))])
    # total operators: not neg len + - * == != < <= > >=
    return _conj([defined(a) for a in args])


def subst(e: dict, m: dict) -> dict:
    """Capture-avoiding substitution over a t expression: each mapped name
    is replaced by a new name (str) or a whole t expression (dict)."""
    if "var" in e:
        v = m.get(e["var"])
        if v is None:
            return e
        return {"var": v} if isinstance(v, str) else v
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


def _calls(e: dict, name: str) -> bool:
    if "call" in e:
        c = e["call"]
        if c["fun"] == name:
            return True
        return any(_calls(a, name) for a in c["args"])
    if "ite" in e:
        c = e["ite"]
        return any(_calls(c[k], name) for k in ("cond", "then", "else"))
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        return any(_calls(q[k], name) for k in ("lo", "hi", "body"))
    return any(_calls(a, name) for a in e.get("args", []))


def _body_calls(body: list, name: str) -> bool:
    for s in body:
        if "assign" in s and _calls(s["assign"][1], name):
            return True
        if "var" in s and _calls(s["var"]["init"], name):
            return True
        if "if" in s:
            c = s["if"]
            if (_calls(c["cond"], name) or _body_calls(c["then"], name)
                    or _body_calls(c["else"], name)):
                return True
        if "while" in s:
            w = s["while"]
            if (_calls(w["cond"], name) or _calls(w["decreases"], name)
                    or any(_calls(i, name) for i in w.get("invariants", []))
                    or _body_calls(w["body"], name)):
                return True
    return False


def _assigned(body: list) -> set:
    out = set()
    for s in body:
        if "assign" in s:
            out.add(s["assign"][0])
        elif "if" in s:
            out |= _assigned(s["if"]["then"]) | _assigned(s["if"]["else"])
        elif "while" in s:
            out |= _assigned(s["while"]["body"])
    return out


def _declared(body: list) -> set:
    out = set()
    for s in body:
        if "var" in s:
            out.add(s["var"]["name"])
        elif "if" in s:
            out |= _declared(s["if"]["then"]) | _declared(s["if"]["else"])
        elif "while" in s:
            out |= _declared(s["while"]["body"])
    return out


# ------------------------------------------------------------------ v1 path

def _has_nonlinear(e: dict) -> bool:
    """True iff e contains a product of two non-literal factors, the shape
    Verus's default solver profile (nonlinear arithmetic off, measured:
    sum_upto's invariant preservation fails without help) cannot decide."""
    if "ite" in e:
        return any(_has_nonlinear(e["ite"][k]) for k in ("cond", "then", "else"))
    if "call" in e:
        return any(_has_nonlinear(a) for a in e["call"]["args"])
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        return any(_has_nonlinear(q[k]) for k in ("lo", "hi", "body"))
    if "op" in e:
        if e["op"] == "*":
            a, b = e["args"]
            if "int" not in a and "int" not in b:
                return True
        return any(_has_nonlinear(a) for a in e.get("args", []))
    return False


def _sym(body: list, env: dict) -> dict | None:
    """Equational symbolic execution of a loop body: the effect of one
    iteration as a map from each variable to a t expression over the entry
    values, if-joins merged with ite. None when the body contains a nested
    while (its effect is not equational)."""
    env = dict(env)
    for s in body:
        if "assign" in s:
            n, e = s["assign"]
            env[n] = subst(e, env)
        elif "var" in s:
            v = s["var"]
            env[v["name"]] = subst(v["init"], env)
        elif "if" in s:
            c = subst(s["if"]["cond"], env)
            e1 = _sym(s["if"]["then"], env)
            e2 = _sym(s["if"]["else"], env)
            if e1 is None or e2 is None:
                return None
            env = {k: (e1[k] if e1[k] == e2[k] else
                       {"ite": {"cond": c, "then": e1[k], "else": e2[k]}})
                   for k in env}
        elif "while" in s:
            return None
    return env


def _prenex(e: dict, fresh) -> tuple[list[str], dict]:
    """Pull the foralls that defined() generated (they sit only in positive
    spine positions: conjuncts, guard consequents, ite branches, forall
    bodies) out to the front, renamed fresh, their [lo,hi) ranges turned
    into guards of the matrix. Sound because the binders are fresh and every
    hoisted forall is in a positive position. The point (measured): a
    definedness forall's body often has no function-application term, so
    Verus cannot infer a trigger for it, so hoisting the binder into the
    enclosing lemma's parameters removes the SMT quantifier entirely."""
    if "forall" in e:
        q = e["forall"]
        v = next(fresh)
        body = subst(q["body"], {q["var"]: v})
        bs, mat = _prenex(body, fresh)
        rng = {"op": "and", "args": [
            {"op": "<=", "args": [q["lo"], {"var": v}]},
            {"op": "<", "args": [{"var": v}, q["hi"]]}]}
        return [v] + bs, {"op": "implies", "args": [rng, mat]}
    if "ite" in e:
        c = e["ite"]
        bt, tm = _prenex(c["then"], fresh)
        be, em = _prenex(c["else"], fresh)
        if not bt and not be:
            return [], e
        return bt + be, {"ite": {"cond": c["cond"], "then": tm, "else": em}}
    if "op" in e and e["op"] == "and":
        bs, mats = [], []
        for a in e["args"]:
            b, m = _prenex(a, fresh)
            bs += b
            mats.append(m)
        return bs, {"op": "and", "args": mats}
    if "op" in e and e["op"] == "implies":
        p, q = e["args"]
        bs, qm = _prenex(q, fresh)
        if not bs:
            return [], e
        return bs, {"op": "implies", "args": [p, qm]}
    return [], e


class _V1:
    def __init__(self, task: dict):
        self.task = task
        self.name = task["name"]
        self.helpers: list[str] = []   # loop helper proof fns
        self.wf: list[str] = []        # definedness (well-formedness) lemmas
        self.loop_ix = 0

    # -- well-formedness lemmas ------------------------------------------
    def _wf_lemma(self, lname: str, params: list[tuple[str, str]],
                  context: list[dict], obligation: dict) -> None:
        if obligation == TRUE:
            return
        fresh = (f"t_q{i}" for i in range(1000))
        binders, obligation = _prenex(obligation, fresh)
        params = params + [(b, "int") for b in binders]
        ps = ", ".join(f"{n}: {t}" for n, t in params)
        req = ""
        if context:
            req = ("    requires\n        "
                   + ",\n        ".join(expr(c) for c in context) + ",\n")
        self.wf.append(
            f"proof fn {lname}({ps})\n{req}"
            "{\n"
            f"    assert({expr(obligation)});\n"
            "}\n")

    # -- statements ------------------------------------------------------
    def _assert_defined(self, e: dict, lines: list[str], ind: str) -> None:
        ob = defined(e)
        if ob != TRUE:
            lines.append(f"{ind}assert({expr(ob)});")

    def stmts(self, body: list, scope: dict, ind: str) -> list[str]:
        """scope: ordered {name: (verus_type, mutable)}. Returns lines."""
        lines: list[str] = []
        for s in body:
            if "assign" in s:
                name, e = s["assign"]
                assert name in scope and scope[name][1], \
                    f"assign to {name}, not a mutable name in scope"
                self._assert_defined(e, lines, ind)
                lines.append(f"{ind}{name} = {expr(e)};")
            elif "var" in s:
                v = s["var"]
                self._assert_defined(v["init"], lines, ind)
                scope[v["name"]] = (TYPES[v["type"]], True)
                lines.append(f"{ind}let mut {v['name']}: {TYPES[v['type']]}"
                             f" = {expr(v['init'])};")
            elif "if" in s:
                c = s["if"]
                self._assert_defined(c["cond"], lines, ind)
                lines.append(f"{ind}if {expr(c['cond'])} {{")
                lines += self.stmts(c["then"], dict(scope), ind + "    ")
                if c["else"]:
                    lines.append(f"{ind}}} else {{")
                    lines += self.stmts(c["else"], dict(scope), ind + "    ")
                lines.append(f"{ind}}}")
            elif "while" in s:
                lines += self.loop(s["while"], scope, ind)
            else:
                raise ValueError(f"t v1 -> verus: unknown statement {s!r}")
        return lines

    # -- loops: proof mode has no while (measured), so the loop rule is  --
    # -- encoded as a recursive helper lemma; see module docstring.      --
    def loop(self, w: dict, scope: dict, ind: str) -> list[str]:
        k = self.loop_ix
        self.loop_ix += 1
        invs = w.get("invariants", [])
        cond, dec = w["cond"], w["decreases"]
        for label, e in (("cond", cond), ("decreases", dec)):
            if defined(e) != TRUE:
                raise NotImplementedError(
                    f"verus: definedness obligation on loop {label} "
                    f"(partial `at` in guard position) not implemented")

        # invariant k may assume invariants 1..k-1 (SPEC.md definedness)
        allvars = [(n, t) for n, (t, _m) in scope.items()]
        for j, iv in enumerate(invs):
            self._wf_lemma(f"t_wf_{self.name}_l{k}_inv{j}", allvars,
                           invs[:j], defined(iv))

        assigned = _assigned(w["body"]) - _declared(w["body"])
        state = [n for n in scope if scope[n][1] and n in assigned]
        ro = [n for n in scope if n not in state]
        assert state, "loop body assigns nothing in scope, not lowerable"

        if len(state) == 1:
            m = {state[0]: "t_res"}
            res_ty = scope[state[0]][0]
            res_val = state[0]
        else:
            m = {v: f"t_res.{j}" for j, v in enumerate(state)}
            res_ty = "(" + ", ".join(scope[v][0] for v in state) + ")"
            res_val = "(" + ", ".join(state) + ")"

        hname = f"t_lp_{self.name}_{k}"
        ps = ", ".join(f"{n}: {scope[n][0]}" for n in ro + state)
        req = ""
        if invs:
            req = ("    requires\n        "
                   + ",\n        ".join(expr(i) for i in invs) + ",\n")
        ens = ([expr(subst(i, m)) for i in invs]
               + [f"(!{expr(subst(cond, m))})"])
        ens_s = ",\n        ".join(ens)

        # Invariants with nonlinear terms need Verus's sanctioned escape
        # hatch, assert ... by (nonlinear_arith) with explicit premises,
        # because the default solver profile has nonlinear arithmetic off
        # (measured; Dafny's does not). The premises are exactly t's
        # preservation rule: all invariants plus the guard at entry; the
        # conclusion is the invariant over the symbolic post-state.
        nl = [j for j, iv in enumerate(invs) if _has_nonlinear(iv)]
        old_lets, bridge = "", []
        if nl:
            entry = {v: {"var": f"t_old_{v}"} for v in state}
            env = _sym(w["body"], entry)
            if env is not None:
                old_lets = "".join(f"    let t_old_{v} = {v};\n"
                                   for v in state)
                prem = ",\n                ".join(
                    expr(subst(p, entry)) for p in invs + [cond])
                bridge = [
                    f"        assert({expr(subst(invs[j], env))})"
                    " by (nonlinear_arith)\n"
                    f"            requires\n                {prem},\n"
                    "        ;"
                    for j in nl]

        hscope = {n: (scope[n][0], n in state) for n in ro + state}
        inner = self.stmts(w["body"], hscope, "        ") + bridge
        shadows = "".join(f"    let mut {v} = {v};\n" for v in state)
        args = ", ".join(ro + state)
        self.helpers.append(
            f"proof fn {hname}({ps}) -> (t_res: {res_ty})\n"
            f"{req}    ensures\n        {ens_s},\n"
            f"    decreases {expr(dec)},\n"
            "{\n"
            f"{old_lets}{shadows}"
            f"    if {expr(cond)} {{\n"
            + "\n".join(inner) + "\n"
            f"        {hname}({args})\n"
            "    } else {\n"
            f"        {res_val}\n"
            "    }\n"
            "}\n")

        tmp = f"t_tmp{k}"
        lines = [f"{ind}let {tmp} = {hname}({args});"]
        if len(state) == 1:
            lines.append(f"{ind}{state[0]} = {tmp};")
        else:
            lines += [f"{ind}{v} = {tmp}.{j};" for j, v in enumerate(state)]
        return lines

    # -- whole task ------------------------------------------------------
    def emit(self, body: list) -> str:
        task = self.task
        params = [(p["name"], TYPES[p["type"]]) for p in task["params"]]
        rname = task["returns"][0]["name"]
        rtype = TYPES[task["returns"][0]["type"]]
        reqs = task.get("requires", [])
        enss = task["ensures"]

        # spec fns and their (universal) definedness lemmas
        spec_blocks = []
        for f in task.get("spec_funs", []):
            fps = ", ".join(f"{p['name']}: {TYPES[p['type']]}"
                            for p in f["params"])
            if defined(f["decreases"]) != TRUE:
                raise NotImplementedError(
                    "verus: definedness obligation on spec_fun decreases "
                    "not implemented")
            spec_blocks.append(
                f"spec fn {f['name']}({fps}) -> {TYPES[f['result']]}\n"
                f"    decreases {expr(f['decreases'])},\n"
                "{\n"
                f"    {expr(f['body'])}\n"
                "}\n")
            self._wf_lemma(f"t_wf_{self.name}_fn_{f['name']}",
                           [(p["name"], TYPES[p["type"]])
                            for p in f["params"]],
                           [], defined(f["body"]))

        # requires clause k assumes clauses 1..k-1; ensures clause k assumes
        # all requires and ensures 1..k-1 (SPEC.md definedness)
        for j, rq in enumerate(reqs):
            self._wf_lemma(f"t_wf_{self.name}_req{j}", params,
                           reqs[:j], defined(rq))
        for j, en in enumerate(enss):
            self._wf_lemma(f"t_wf_{self.name}_ens{j}",
                           params + [(rname, rtype)],
                           reqs + enss[:j], defined(en))

        if _body_calls(body, self.name) and "decreases" not in task:
            raise ValueError(
                "self-recursive body without a task-level decreases "
                "(SPEC.md gate 3 requires one)")
        dec = ""
        if "decreases" in task:
            if defined(task["decreases"]) != TRUE:
                raise NotImplementedError(
                    "verus: definedness obligation on task decreases "
                    "not implemented")
            dec = f"    decreases {expr(task['decreases'])},\n"

        scope = {n: (t, False) for n, t in params}
        scope[rname] = (rtype, True)
        main_lines = self.stmts(body, scope, "    ")

        ps = ", ".join(f"{n}: {t}" for n, t in params)
        req = ""
        if reqs:
            req = ("    requires\n        "
                   + ",\n        ".join(expr(e) for e in reqs) + ",\n")
        ens = ",\n        ".join(expr(e) for e in enss)
        main = (
            f"proof fn {self.name}({ps}) -> ({rname}: {rtype})\n"
            f"{req}    ensures\n        {ens},\n{dec}"
            "{\n"
            f"    let mut {rname}: {rtype};\n"
            + "\n".join(main_lines) + "\n"
            f"    {rname}\n"
            "}\n")

        blocks = spec_blocks + self.wf + self.helpers + [main]
        return ("use vstd::prelude::*;\n\nverus! {\n\n"
                + "\n".join(blocks)
                + "\n} // verus!\n\nfn main() {}\n")




# ------------------------------------------------ the refutation certificate
# Shared certificate protocol (2026-09-02, all columns). Verus surfaces NO
# signal separating a countermodel from incompleteness: Z3 runs with
# smt.mbqi false, so the check-sat for a genuinely false postcondition and
# for true nonlinear distributivity both come back "unknown" (measured, see
# verifiers/verus.py), and no flag prints a model. The adapter therefore
# never mints REFUTED from a bare verification failure. What it can trust
# is a proof it checked itself: when lowering a TWIN whose measured witness
# is expressible as a GROUND formula, this lowering appends one extra goal,
# named exactly t_refutation_certificate, that instantiates the spec at the
# concrete witness and asserts via assert(..) by (compute_only), ground
# kernel evaluation with no SMT fallback, that the obligation fails there.
# verifiers/verus.py mints REFUTED only when the kernel accepts that goal,
# and a file carrying the goal's name can never mint VERIFIED.
#
# What each witness kind certifies:
#   value (_ens True only): requires holds at the witness input and the
#     ensures conjunction is false at (input, r := the twin's measured
#     result). Recursive spec fns evaluate under compute_only with no
#     reveal_with_fuel (measured: fact(2), count over seq literals).
#   exit: the loop rule's post-loop obligation is false at the witness
#     state: requires and the twin's SURVIVING invariants hold, the guard
#     is false, and the ensures conjunction is false. The kept invariants
#     and guard are read off the twin body's own loop, found by diffing the
#     real body against the twin body, so the certificate always speaks
#     about the file it travels in. This is the negation of exactly the
#     obligation the lowered twin asks the kernel to prove: the loop helper
#     ensures only invariants plus the negated guard, and the witness state
#     is one interp._Admissible already screened as unrefusable.
#   preservation: would need one loop iteration replayed inside the
#     certificate; not emitted (no current twin produces this kind), so
#     such a cell honestly reads unproved.
#   undefined: the twin has no value at the witness, so there is no ground
#     ensures instance to evaluate; not emitted.
# Bounded quantifiers whose bounds are ground after witness substitution
# are unrolled here (finite conjunction/disjunction over the concrete
# range, capped) because compute_only cannot evaluate int quantifiers; the
# formula the kernel checks is fully ground. Anything outside these rules
# returns None and no certificate is emitted: a missing or rejected
# certificate can only cost a flip (UNPROVED), never fake one.

CERT_NAME = "t_refutation_certificate"
_UNROLL_CAP = 64


def _tlit(v):
    """A measured witness value as a t literal expression."""
    if isinstance(v, bool):
        return {"bool": v}
    if isinstance(v, int):
        return {"int": v}
    if isinstance(v, list) and all(
            isinstance(x, int) and not isinstance(x, bool) for x in v):
        return {"_seq": list(v)}
    raise ValueError(f"witness value {v!r} has no t literal")


def _gint(e) -> int:
    """Ground int value of a quantifier bound after witness substitution.
    Deliberately strict: anything unexpected raises, which refuses the
    certificate rather than emitting a wrong one."""
    if isinstance(e, dict) and "int" in e:
        return e["int"]
    op = e.get("op") if isinstance(e, dict) else None
    args = e.get("args", []) if isinstance(e, dict) else []
    if op == "len" and len(args) == 1 and "_seq" in args[0]:
        return len(args[0]["_seq"])
    if op == "neg" and len(args) == 1:
        return -_gint(args[0])
    if op in ("+", "-", "*") and len(args) == 2:
        a, b = _gint(args[0]), _gint(args[1])
        return a + b if op == "+" else (a - b if op == "-" else a * b)
    raise ValueError(f"quantifier bound not ground: {e!r}")


def _unroll(e: dict, budget: list) -> dict:
    """Replace bounded quantifiers (ground bounds) with finite conjunctions
    or disjunctions so compute_only can evaluate the result. budget is a
    one-element countdown over emitted instances; exhausting it raises and
    the certificate is refused."""
    if "forall" in e or "exists" in e:
        kind = "forall" if "forall" in e else "exists"
        q = e[kind]
        lo, hi = _gint(q["lo"]), _gint(q["hi"])
        insts = []
        for k in range(lo, hi):
            budget[0] -= 1
            if budget[0] < 0:
                raise ValueError("quantifier unroll budget exhausted")
            insts.append(_unroll(subst(q["body"], {q["var"]: {"int": k}}),
                                 budget))
        if not insts:
            return {"bool": kind == "forall"}
        if len(insts) == 1:
            return insts[0]
        return {"op": "and" if kind == "forall" else "or", "args": insts}
    if "ite" in e:
        c = e["ite"]
        return {"ite": {"cond": _unroll(c["cond"], budget),
                        "then": _unroll(c["then"], budget),
                        "else": _unroll(c["else"], budget)}}
    if "call" in e:
        c = e["call"]
        return {"call": {"fun": c["fun"],
                         "args": [_unroll(a, budget) for a in c["args"]]}}
    if "op" in e:
        return {"op": e["op"],
                "args": [_unroll(a, budget) for a in e.get("args", [])]}
    return e


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


def certificate_formula(task: dict, twin_body: list, w: dict) -> dict | None:
    """The certificate's FORMULA as a t expression, or None when the witness
    is not ground-certificatable under the rules in the section above.

    Factored out of `_certificate` 2026-09-06 so another column can certify
    the SAME formula rather than a second reading of it: lower_fstar.py
    imports this and renders it in F* syntax. Every rule in the section
    comment above therefore has one implementation, and a change to what a
    certificate MEANS lands in one place while each column keeps only its own
    syntax and its own ground-evaluation tactic."""
    return _cert_formula(task, twin_body, w)


def _cert_formula(task: dict, twin_body: list, w: dict) -> dict | None:
    kind = w.get("_kind")
    names = {k: v for k, v in w.items() if not k.startswith("_")}
    try:
        m = {n: _tlit(v) for n, v in names.items()}
        parts = [subst(rq, m) for rq in task.get("requires", [])]
        if kind == "value":
            if w.get("_ens") is not True:
                return None      # a drift a sound kernel may still accept
            tw = w.get("_twin")
            if not isinstance(tw, (bool, int, list)):
                return None
            m2 = dict(m)
            m2[task["returns"][0]["name"]] = _tlit(tw)
            parts = [subst(rq, m2) for rq in task.get("requires", [])]
            parts.append({"op": "not", "args": [
                _conj([subst(en, m2) for en in task["ensures"]])]})
        elif kind == "exit":
            loop = _twin_loop(task["body"], twin_body)
            if loop is None:
                return None
            parts += [subst(iv, m) for iv in loop.get("invariants", [])]
            parts.append({"op": "not", "args": [subst(loop["cond"], m)]})
            parts.append({"op": "not", "args": [
                _conj([subst(en, m) for en in task["ensures"]])]})
        else:
            return None          # preservation / undefined: see above
        return _unroll(_conj(parts), [_UNROLL_CAP])
    except (ValueError, KeyError, TypeError, IndexError):
        return None


def _certificate(task: dict, twin_body: list, w: dict) -> str | None:
    """The appended t_refutation_certificate block for a measured twin
    witness, or None when the witness is not expressible as a ground
    certificate under the rules in the section comment above."""
    formula = _cert_formula(task, twin_body, w)
    if formula is None:
        return None
    global _SUFFIX_INT
    saved = _SUFFIX_INT
    _SUFFIX_INT = True
    try:
        body = expr(formula)
    finally:
        _SUFFIX_INT = saved
    return (
        "\nverus!{\n\n"
        "// Ground refutation certificate for the measured twin witness.\n"
        "// The kernel evaluates it with no SMT fallback; verifiers/verus.py\n"
        "// mints REFUTED only if this one goal is accepted, and a file\n"
        "// carrying this name can never mint VERIFIED.\n"
        f"proof fn {CERT_NAME}()\n"
        "{\n"
        f"    assert({body}) by (compute_only);\n"
        "}\n\n"
        "} // verus!\n")


# `witness` is the twin's measured witness (harness.twin_cached). Twin call
# sites pass it; when it is present and ground-certificatable, the lowering
# appends the refutation certificate block (see the section above).
def lower(task: dict, body: list, witness: dict | None = None) -> str:
    global _SUFFIX_INT
    if task.get("t", 0) == 0:
        # v0 used to emit bare literals to keep its output byte-identical to
        # an earlier baseline. That is unsound as an emission rule: Verus
        # types a literal expression by inference, and an expression built
        # only from non-negative literals infers `nat`, which does not match
        # the `int` return. Measured 2026-09-04 on fz_v0if_141, where the
        # branch value `(3 * 1)` is rejected with E0308 expected int found
        # nat, while the metamorphic rewrite of the same value to
        # `((3 - 0) * 1)` introduces a subtraction, infers int, and verifies.
        # A lowering whose well-formedness depends on whether a constant
        # folds to something non-negative is not a lowering. v0 now suffixes
        # exactly as v1 does.
        _SUFFIX_INT = True
        try:
            src = lower_v0(task, body, witness=witness)
        finally:
            _SUFFIX_INT = False
    else:
        _SUFFIX_INT = True
        try:
            src = _V1(task).emit(body)
        finally:
            _SUFFIX_INT = False
    if witness is not None:
        cert = _certificate(task, body, witness)
        if cert:
            src += cert
    return src


if __name__ == "__main__":
    raise SystemExit(harness.run_all(sys.argv[1:], lower, verus_backend, "rs"))
