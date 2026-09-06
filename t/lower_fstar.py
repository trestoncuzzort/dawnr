#!/usr/bin/env python3
"""lower_fstar.py: lower t tasks (v0 and v1) to F*; the seventh kernel.

F*'s type system does most of t's work natively; this file records exactly
what is delegated to the kernel and what is refused:

  DEFINEDNESS. `at` lowers to FStar.Seq.index, whose domain refinement
  (i:nat{i < Seq.length s}) turns every t definedness obligation into a
  subtyping check discharged by the kernel under the path conditions F*'s
  VC generator already tracks, left-to-right through /\\, ==>, if-then-else,
  && and ||, which are t's rules (SPEC.md "Definedness"). Nothing is
  totalized: an unguarded `at` fails the file with number 19, never passes.

  LOOPS. F*'s pure fragment has no while statement, so a while loop lowers
  to a top-level `let rec <name>_loop` over params, the frame (mutable
  names the loop body never assigns, passed back unchanged so the caller
  keeps its own bindings, per SPEC.md's frame rule) and the threaded state
  (exactly the loop body's syntactic assigned set):
  requires = task requires + invariants in stated order (the twin operator
  depends on that order), ensures = invariants + negated guard over the
  returned state, decreases = the loop's required decreases clause.
  Termination is F*'s precedes check on the int measure, new value >= 0
  and < old at the recursive call under the guard, exactly t's
  obligation, discharged by the kernel (measured on the Shape probes,
  2026-08-31).

  RECURSION. spec_funs lower to `let rec ... : Tot ... (decreases m)`; a
  self-recursive task lowers to a `let rec` carrying its contract as Pure
  requires/ensures plus the task decreases clause. Self-calls stay in
  expression position: F* is a CBV expression language, so no hoisting and
  none of Dafny's lazy-position refusals are needed; the kernel applies
  the modular contract (callee requires proved at the site, ensures
  assumed of the result) at every call.

Statement bodies lower by symbolic execution to one expression (per-var
if-merge, the Rocq lowering's approach): every t body ends each path in an
assign, so the final environment entry for the return name IS the function
body, and a value computed under a branch stays under that branch's guard.

ABSTAINS (NotImplementedError, recorded and never faked): a quantifier in
computational position; more than one loop, nested loops, a loop under a
conditional, or a loop plus self-recursion in one body; identifiers that
collide with F* keywords, or carry an uppercase initial (F* term names are
lowercase). Generated helper names are made fresh against the task's own
strings, so a task name is never refused for its spelling.

Stdlib only, same reason as dataset_gate.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                                   # noqa: E402
import lower_verus                               # noqa: E402
from verifiers import fstar as fstar_backend     # noqa: E402

TY = {"int": "int", "bool": "bool", "seq": "Seq.seq int"}
CMP = {"<": "<", "<=": "<=", ">": ">", ">=": ">="}
ARITH = {"+": "+", "-": "-", "*": "*"}

RESERVED = {
    "abstract", "admit", "and", "assert", "assume", "attributes", "begin",
    "by", "calc", "class", "decreases", "default", "effect", "eliminate",
    "else", "end", "ensures", "exception", "exists", "false", "forall",
    "friend", "fun", "function", "if", "in", "include", "inline", "instance",
    "introduce", "irreducible", "let", "logic", "magic", "match", "module",
    "new", "noeq", "not", "of", "open", "opaque", "private", "rec",
    "requires", "returns", "then", "total", "true", "try", "type", "unfold",
    "unfoldable", "val", "when", "with",
}


def _ck(name: str) -> str:
    # The `_loop` suffix used to be refused here as well, to keep this
    # lowering's generated helper names clear of the task's own. That was
    # unnecessary and it cost a column: Ctx.fresh_named already guarantees
    # freshness by checking every string in the task and appending a counter,
    # so a task named `gt_width_loop` simply yields the helper
    # `gt_width_loop_loop`. Measured 2026-09-04: truth_fuzz's gt_width_loop
    # made fstar ABSTAIN, so one of seven columns declined to run for a
    # spelling reason and every claim resting on that row was quietly weaker
    # than it read. A lowering may refuse what it cannot express; it may not
    # refuse a name it can rename.
    if name in RESERVED or not name[0].islower():
        raise NotImplementedError(
            f"fstar lowering: identifier {name!r} is an F* keyword or lacks "
            f"the lowercase initial F* requires for term names")
    return name


def _collect_names(obj) -> set[str]:
    """Every string anywhere in the task JSON, a superset of every
    identifier in scope, so a name absent from it is fresh everywhere."""
    out: set[str] = set()
    if isinstance(obj, dict):
        for v in obj.values():
            out |= _collect_names(v)
    elif isinstance(obj, list):
        for v in obj:
            out |= _collect_names(v)
    elif isinstance(obj, str):
        out.add(obj)
    return out


def has_self_call(node, name: str) -> bool:
    if isinstance(node, dict):
        if "call" in node and node["call"].get("fun") == name:
            return True
        return any(has_self_call(v, name) for v in node.values())
    if isinstance(node, list):
        return any(has_self_call(v, name) for v in node)
    return False


class Ctx:
    """Per-task rendering context: name->t-type for everything in scope,
    the spec_fun/task call table, and a fresh-name supply."""

    def __init__(self, task: dict):
        self.task = task
        self.tys: dict[str, str] = {}
        for p in task["params"]:
            self.tys[_ck(p["name"])] = p["type"]
        for r in task["returns"]:
            self.tys[_ck(r["name"])] = r["type"]
        self.funs: dict[str, dict] = {}
        for sf in task.get("spec_funs", []):
            self.funs[_ck(sf["name"])] = {"params": sf["params"],
                                          "result": sf["result"]}
        self.funs[_ck(task["name"])] = {"params": task["params"],
                                        "result": task["returns"][0]["type"]}
        self._used = _collect_names(task)
        self._n = 0

    def fresh(self) -> str:
        while True:
            cand = f"t{self._n}"
            self._n += 1
            if cand not in self._used:
                self._used.add(cand)
                return cand

    def fresh_named(self, base: str) -> str:
        if base not in self._used:
            self._used.add(base)
            return base
        k = 1
        while f"{base}{k}" in self._used:
            k += 1
        self._used.add(f"{base}{k}")
        return f"{base}{k}"

    # ---------------------------------------------------------- typing ----
    def ty(self, e: dict, local: dict) -> str:
        if "int" in e:
            return "int"
        if "bool" in e:
            return "bool"
        if "var" in e:
            return local.get(e["var"]) or self.tys[e["var"]]
        if "forall" in e or "exists" in e:
            return "bool"
        if "ite" in e:
            return self.ty(e["ite"]["then"], local)
        if "call" in e:
            return self.funs[e["call"]["fun"]]["result"]
        op = e["op"]
        if op in ARITH or op in ("neg", "len", "at"):
            return "int"
        return "bool"

    def seq_var(self, e: dict, local: dict) -> str:
        """v1 sequences are param-position values: a seq position must be a
        seq-typed variable."""
        if "var" in e and (local.get(e["var"]) or self.tys.get(e["var"])) == "seq":
            return e["var"]
        if "_seq" in e:
            # A GROUND seq value, which only the refutation certificate below
            # produces: the witness substitutes a concrete sequence into a
            # seq-typed parameter. Nothing else in the lowering may reach
            # here, and the certificate is the one place a seq position is
            # not a variable.
            items = "; ".join(str(int(v)) for v in e["_seq"])
            return f"(Seq.createL #int [{items}])"
        raise NotImplementedError(f"seq position holds non-variable {e!r}")

    def call(self, e: dict, env: dict, local: dict) -> str:
        c = e["call"]
        info = self.funs[c["fun"]]
        parts = [c["fun"]]
        for formal, a in zip(info["params"], c["args"], strict=True):
            if formal["type"] == "seq":
                parts.append(self.seq_var(a, local))
            elif formal["type"] == "bool":
                parts.append(self.bx(a, env, local))
            else:
                parts.append(self.zx(a, env, local))
        return "(" + " ".join(parts) + ")"

    # ------------------------------------------------------- rendering ----
    def zx(self, e: dict, env: dict, local: dict) -> str:
        """Int-valued term; the same syntax serves spec and code in F*."""
        if "int" in e:
            n = e["int"]
            return f"({n})" if n < 0 else str(n)
        if "var" in e:
            return env.get(e["var"], e["var"])
        if "ite" in e:
            c = e["ite"]
            return (f"(if {self.bx(c['cond'], env, local)} "
                    f"then {self.zx(c['then'], env, local)} "
                    f"else {self.zx(c['else'], env, local)})")
        if "call" in e:
            return self.call(e, env, local)
        op = e.get("op")
        if op == "len":
            return f"(Seq.length {self.seq_var(e['args'][0], local)})"
        if op == "at":
            return (f"(Seq.index {self.seq_var(e['args'][0], local)} "
                    f"{self.zx(e['args'][1], env, local)})")
        if op == "neg":
            return f"(- {self.zx(e['args'][0], env, local)})"
        if op in ARITH:
            a, b = (self.zx(x, env, local) for x in e["args"])
            return f"({a} {ARITH[op]} {b})"
        raise ValueError(f"t -> fstar: not an int expression: {op!r}")

    def bx(self, e: dict, env: dict, local: dict) -> str:
        """Computational bool. && and || short-circuit in F* exactly as t's
        left-to-right definedness rules require."""
        if "bool" in e:
            return "true" if e["bool"] else "false"
        if "var" in e:
            return env.get(e["var"], e["var"])
        if "ite" in e:
            c = e["ite"]
            return (f"(if {self.bx(c['cond'], env, local)} "
                    f"then {self.bx(c['then'], env, local)} "
                    f"else {self.bx(c['else'], env, local)})")
        if "call" in e:
            return self.call(e, env, local)
        if "forall" in e or "exists" in e:
            raise NotImplementedError(
                "fstar lowering: a quantifier in computational position has "
                "no decidable lowering here")
        op = e["op"]
        if op in CMP:
            a, b = (self.zx(x, env, local) for x in e["args"])
            return f"({a} {CMP[op]} {b})"
        if op in ("==", "!="):
            t = self.ty(e["args"][0], local)
            rd = self.bx if t == "bool" else self.zx
            a, b = (rd(x, env, local) for x in e["args"])
            return f"({a} {'=' if op == '==' else '<>'} {b})"
        if op == "not":
            return f"(not {self.bx(e['args'][0], env, local)})"
        if op in ("and", "or"):
            glue = " && " if op == "and" else " || "
            return "(" + glue.join(self.bx(x, env, local)
                                   for x in e["args"]) + ")"
        if op == "implies":
            a, b = (self.bx(x, env, local) for x in e["args"])
            return f"((not {a}) || {b})"
        raise ValueError(f"t -> fstar: not a bool expression: {op!r}")

    def prop(self, e: dict, env: dict, local: dict) -> str:
        """Spec-position proposition. Bare bool terms coerce via b2t; bool
        equality renders as <==> so a bool var can equate a quantifier."""
        if "bool" in e:
            return "True" if e["bool"] else "False"
        if "var" in e:
            return env.get(e["var"], e["var"])
        if "forall" in e or "exists" in e:
            kind = "forall" if "forall" in e else "exists"
            q = e[kind]
            v = _ck(q["var"])
            lo = self.zx(q["lo"], env, local)
            hi = self.zx(q["hi"], env, local)
            # the bound variable shadows anything outer: strip it from the
            # substitution env so no outer term leaks under the binder
            env2 = {k: t for k, t in env.items() if k != v}
            local2 = dict(local, **{v: "int"})
            body = self.prop(q["body"], env2, local2)
            glue = "==>" if kind == "forall" else "/\\"
            return (f"({kind} ({v}:int). (({lo} <= {v}) /\\ ({v} < {hi})) "
                    f"{glue} {body})")
        if "ite" in e:
            c = e["ite"]
            cp = self.prop(c["cond"], env, local)
            return (f"(({cp} /\\ {self.prop(c['then'], env, local)}) "
                    f"\\/ ((~ {cp}) /\\ {self.prop(c['else'], env, local)}))")
        if "call" in e:
            return self.call(e, env, local)
        op = e["op"]
        if op == "not":
            return f"(~ {self.prop(e['args'][0], env, local)})"
        if op in ("and", "or"):
            glue = " /\\ " if op == "and" else " \\/ "
            return "(" + glue.join(self.prop(x, env, local)
                                   for x in e["args"]) + ")"
        if op == "implies":
            a, b = (self.prop(x, env, local) for x in e["args"])
            return f"({a} ==> {b})"
        if op in ("==", "!="):
            if self.ty(e["args"][0], local) == "bool":
                a, b = (self.prop(x, env, local) for x in e["args"])
                core = f"({a} <==> {b})"
            else:
                a, b = (self.zx(x, env, local) for x in e["args"])
                core = f"({a} == {b})"
            return core if op == "==" else f"(~ {core})"
        if op in CMP:
            a, b = (self.zx(x, env, local) for x in e["args"])
            return f"({a} {CMP[op]} {b})"
        raise ValueError(f"t -> fstar: not a spec expression: {op!r}")


# --------------------------------------------------------------------------
# statement-level symbolic execution (per-var if-merge, as in lower_rocq)
# --------------------------------------------------------------------------

def _decls(stmts: list) -> set[str]:
    out: set[str] = set()
    for s in stmts:
        if "var" in s:
            out.add(s["var"]["name"])
        elif "if" in s:
            out |= _decls(s["if"]["then"]) | _decls(s["if"]["else"])
    return out


def exec_straight(cx: Ctx, stmts: list, env: dict, local: dict) -> dict:
    """env maps mutable name -> term (absent = the name itself); local maps
    locals -> t type. Branch-declared locals do not escape their branch;
    a mutable first assigned inside a branch still merges."""
    env = dict(env)
    for s in stmts:
        if "assign" in s:
            v, e = s["assign"]
            t = local.get(v) or cx.tys[v]
            env[v] = (cx.bx(e, env, local) if t == "bool"
                      else cx.zx(e, env, local))
        elif "var" in s:
            d = s["var"]
            v = _ck(d["name"])
            assert v not in cx.tys and v not in local, f"redeclared {v}"
            local[v] = d["type"]
            env[v] = (cx.bx(d["init"], env, local) if d["type"] == "bool"
                      else cx.zx(d["init"], env, local))
        elif "if" in s:
            c = s["if"]
            cb = cx.bx(c["cond"], env, local)
            env_t = exec_straight(cx, c["then"], env, dict(local))
            env_e = exec_straight(cx, c["else"], env, dict(local))
            drop = _decls(c["then"]) | _decls(c["else"])
            for v in sorted((set(env_t) | set(env_e) | set(env)) - drop):
                tv, ev = env_t.get(v, v), env_e.get(v, v)
                env[v] = tv if tv == ev else f"(if {cb} then {tv} else {ev})"
        elif "while" in s:
            raise AssertionError("while must be split out before exec")
        else:
            raise ValueError(f"t -> fstar: no statement {list(s)!r}")
    return env


def loop_assigned(body: list) -> set:
    """Syntactic assigned set of a loop body, SPEC.md's frame rule: a while
    loop havocs exactly the variables assigned in its body."""
    out: set = set()
    for s in body:
        if "assign" in s:
            out.add(s["assign"][0])
        elif "if" in s:
            out |= loop_assigned(s["if"]["then"])
            out |= loop_assigned(s["if"]["else"])
        elif "while" in s:
            out |= loop_assigned(s["while"]["body"])
    return out


def find_while(body: list):
    """(prefix, while, suffix) for exactly one top-level while and none
    nested; (body, None, []) when no while at all. Same refusals as the
    Rocq lowering: a shape it cannot express is an ABSTAIN, not a guess."""
    def any_while(stmts):
        for s in stmts:
            if "while" in s:
                return True
            if "if" in s and (any_while(s["if"]["then"])
                              or any_while(s["if"]["else"])):
                return True
        return False

    for s in body:
        if "if" in s and (any_while(s["if"]["then"])
                          or any_while(s["if"]["else"])):
            raise NotImplementedError(
                "fstar lowering: a loop under a conditional is not lowered yet")
    idxs = [k for k, s in enumerate(body) if "while" in s]
    if not idxs:
        return body, None, []
    if len(idxs) > 1:
        raise NotImplementedError(
            "fstar lowering: more than one loop per body is not lowered yet")
    k = idxs[0]
    w = body[k]["while"]
    if any_while(w["body"]):
        raise NotImplementedError(
            "fstar lowering: nested loops are not lowered yet")
    return body[:k], w, body[k + 1:]


# --------------------------------------------------------------------------
# code generation
# --------------------------------------------------------------------------

def _conj(parts: list[str]) -> str:
    return "(" + " /\\ ".join(parts) + ")" if parts else "True"


def emit_spec_fun(cx: Ctx, sf: dict) -> str:
    local = {p["name"]: p["type"] for p in sf["params"]}
    for n in local:
        _ck(n)
    binders = " ".join(f"({p['name']}:{TY[p['type']]})" for p in sf["params"])
    body = (cx.bx(sf["body"], {}, local) if sf["result"] == "bool"
            else cx.zx(sf["body"], {}, local))
    if has_self_call(sf["body"], sf["name"]):
        dec = cx.zx(sf["decreases"], {}, local)
        return (f"let rec {sf['name']} {binders}\n"
                f"  : Tot {TY[sf['result']]} (decreases {dec})\n"
                f"= {body}\n")
    return f"let {sf['name']} {binders} : Tot {TY[sf['result']]} = {body}\n"


def param_binders(task: dict) -> tuple[str, str]:
    bs = " ".join(f"({p['name']}:{TY[p['type']]})" for p in task["params"])
    args = " ".join(p["name"] for p in task["params"])
    return bs, args


def task_spec(cx: Ctx, task: dict) -> tuple[str, str]:
    """(requires proposition, ensures lambda) over params and the return."""
    reqs = [cx.prop(e, {}, {}) for e in task.get("requires", [])]
    ret = task["returns"][0]["name"]
    ens = [cx.prop(e, {}, {}) for e in task["ensures"]]
    return _conj(reqs), f"(fun {ret} -> {_conj(ens)})"


def gen_fun(cx: Ctx, task: dict, body: list) -> str:
    """Straight-line/if body, possibly self-recursive (F* checks the
    decreases measure and applies the contract modularly at self-calls)."""
    name = task["name"]
    ret = task["returns"][0]["name"]
    ret_t = task["returns"][0]["type"]
    pb, _ = param_binders(task)
    req, ens = task_spec(cx, task)
    env = exec_straight(cx, body, {ret: "false" if ret_t == "bool" else "0"},
                        {})
    expr = env[ret]
    selfrec = has_self_call(body, name)
    dec = ""
    if selfrec:
        assert "decreases" in task, "self-recursive task without decreases"
        dec = f"\n    (decreases {cx.zx(task['decreases'], {}, {})})"
    return (f"let {'rec ' if selfrec else ''}{name} {pb}\n"
            f"  : Pure {TY[ret_t]}\n"
            f"    (requires {req})\n"
            f"    (ensures {ens}){dec}\n"
            f"= {expr}\n")


def gen_loop(cx: Ctx, task: dict, prefix: list, w: dict,
             suffix: list) -> str:
    name = task["name"]
    ret = task["returns"][0]["name"]
    ret_t = task["returns"][0]["type"]
    pb, pargs = param_binders(task)
    req, ens = task_spec(cx, task)
    lname = cx.fresh_named(f"{name}_loop")

    local: dict[str, str] = {}
    env_pre = exec_straight(
        cx, prefix, {ret: "false" if ret_t == "bool" else "0"}, local)
    # SPEC.md frame rule: the loop havocs exactly the syntactic assigned set
    # of its body. Only those variables are threaded through the recursion;
    # every other mutable name is a plain binder of the helper, passed back
    # unchanged at the recursive call, so the caller keeps its own binding
    # and no invariant is needed to preserve it. (Before 2026-09-02 every
    # mutable name was threaded and returned under an ensures that said only
    # invariants + not-guard, which proved the havoc-everything theorem:
    # fr_probe_ret / fr_probe_local failed here while Dafny, Verus and
    # Frama-C proved them.)
    mvars = [ret] + [s["var"]["name"] for s in prefix if "var" in s]
    hav = loop_assigned(w["body"])
    svars = [v for v in mvars if v in hav]
    fvars = [v for v in mvars if v not in hav]
    if not svars:
        raise NotImplementedError(
            "fstar lowering: loop body assigns nothing in scope")
    stys = {v: (local.get(v) or cx.tys[v]) for v in mvars}
    fb = "".join(f" ({v}:{TY[stys[v]]})" for v in fvars)
    fargs = "".join(f" {v}" for v in fvars)
    sb = " ".join(f"({v}:{TY[stys[v]]})" for v in svars)

    guard_b = cx.bx(w["cond"], {}, local)
    guard_p = cx.prop(w["cond"], {}, local)
    invs = [cx.prop(e, {}, local) for e in w.get("invariants", [])]
    dec = cx.zx(w["decreases"], {}, local)
    reqs = [cx.prop(e, {}, {}) for e in task.get("requires", [])]

    step_env = exec_straight(cx, w["body"], {}, dict(local))
    step = " ".join(step_env.get(v, v) for v in svars)
    env_post = exec_straight(cx, suffix, {}, dict(local))
    result = env_post.get(ret, ret)

    post = _conj(invs + [f"(~ {guard_p})"])
    if len(svars) == 1:
        loop_ty = TY[stys[svars[0]]]
        loop_ens = f"(fun {svars[0]} -> {post})"
        state_out = svars[0]
        bind = f"let {svars[0]}"
    else:
        loop_ty = "(" + " & ".join(TY[stys[v]] for v in svars) + ")"
        ob = cx.fresh()
        loop_ens = (f"(fun {ob} -> let ({', '.join(svars)}) = {ob} in "
                    f"{post})")
        state_out = "(" + ", ".join(svars) + ")"
        bind = f"let ({', '.join(svars)})"

    init = " ".join(env_pre.get(v, v) for v in svars)
    fbind = "".join(f"let {v} = {env_pre.get(v, v)} in\n  " for v in fvars)
    return (f"let rec {lname} {pb}{fb} {sb}\n"
            f"  : Pure {loop_ty}\n"
            f"    (requires {_conj(reqs + invs)})\n"
            f"    (ensures {loop_ens})\n"
            f"    (decreases {dec})\n"
            f"= if {guard_b}\n"
            f"  then {lname} {pargs}{fargs} {step}\n"
            f"  else {state_out}\n"
            f"\n"
            f"let {name} {pb}\n"
            f"  : Pure {TY[ret_t]}\n"
            f"    (requires {req})\n"
            f"    (ensures {ens})\n"
            f"= {fbind}{bind} = {lname} {pargs}{fargs} {init} in\n"
            f"  {result}\n")


# `witness` is the twin's measured witness (harness.twin_cached). Twin call
# sites pass it; this lowering does not use it yet.
# ------------------------------------------------ refutation certificate ----
# The shared certificate protocol (ROADMAP 10.7), adopted here 2026-09-06.
# Until then verifiers/fstar.py minted REFUTED from F* Error 19 alone, and
# Error 19 is "the SMT solver could not prove the query", which is a give-up
# signal and not a countermodel. 12.5's sweep measured the cost: 23 real
# programs read REFUTED that dafny verifies, every one a nat-typed loop. The
# door the 2026-09-02 purge closed in the other six columns was still open
# here because the fuzz corpus never failed an F* proof.
#
# So Error 19 now mints UNPROVED, and a twin earns REFUTED back the way every
# other column does: when the measured witness is expressible as a GROUND
# formula, this lowering appends one lemma named exactly
# t_refutation_certificate stating it, and verifiers/fstar.py mints REFUTED
# only when a targeted kernel run discharges that one lemma. A file carrying
# the name can never mint VERIFIED.
#
# The formula is not rebuilt here. It is `lower_verus`'s, imported, so the
# seven columns certify one formula and not seven readings of it: requires at
# the witness, and the ensures conjunction false at (input, r := the twin's
# measured result) for a value witness; for an exit witness the surviving
# invariants and the negated guard and the negated ensures at the measured
# loop-exit state. Preservation and undefined witnesses are not certificated
# and honestly read unproved.
#
# F*'s ground evaluator is `assert_norm`, the analogue of verus's
# compute_only: it normalises the proposition with no SMT fallback. Measured
# 2026-09-06 on F* 2026.08.30, Darwin arm64:
#   * a true ground certificate verifies, "All verification conditions
#     discharged successfully", exit 0;
#   * a FALSE one (the ensures stated false where it actually holds) is
#     rejected Error 19, "Failed to prove: Prims.l_False";
#   * on the real abs twin, whose own proof fails Error 19, the targeted run
#     `--admit_except '<Module>.t_refutation_certificate'` verifies the
#     certificate alone.
# So the certificate discriminates in both directions, which a give-up signal
# never did.

CERT_NAME = "t_refutation_certificate"


def _certificate(cx: Ctx, task: dict, twin_body: list, w: dict) -> str | None:
    """The appended t_refutation_certificate lemma for a measured twin
    witness, or None when the witness is not ground-certificatable.

    Returning None costs a flip (the cell reads unproved). It can never fake
    one, which is the only direction that matters here."""
    try:
        formula = lower_verus.certificate_formula(task, twin_body, w)
    except Exception:
        return None
    if formula is None:
        return None
    try:
        body = cx.prop(formula, {}, {})
    except (KeyError, TypeError, ValueError, NotImplementedError):
        return None
    return (
        "\n// Ground refutation certificate for the measured twin witness." \
        + "\n// assert_norm evaluates it with no SMT fallback; \n"
        + "// verifiers/fstar.py mints REFUTED only if a targeted run\n"
        + "// discharges this one lemma, and a file carrying this name\n"
        + "// can never mint VERIFIED." + "\n"
        + f"let {CERT_NAME} () : Lemma ({body})\n"
        + f"= assert_norm ({body})\n")


def lower(task: dict, body: list, witness: dict | None = None) -> str:
    cx = Ctx(task)
    name = task["name"]
    mod = name[0].upper() + name[1:]
    parts = [f"module {mod}\n", "module Seq = FStar.Seq\n"]
    for sf in task.get("spec_funs", []):
        parts.append(emit_spec_fun(cx, sf))

    prefix, w, suffix = find_while(body)
    if w is not None and has_self_call(body, name):
        raise NotImplementedError(
            "fstar lowering: a body that both loops and self-recurses is "
            "not lowered yet")
    if w is not None:
        parts.append(gen_loop(cx, task, prefix, w, suffix))
    else:
        parts.append(gen_fun(cx, task, body))
    # Twin call sites pass the measured witness; real ones pass None, so a
    # real program never carries the name and can never be demoted by it.
    if witness is not None:
        cert = _certificate(cx, task, body, witness)
        if cert is not None:
            parts.append(cert)
    return "\n".join(parts)


if __name__ == "__main__":
    raise SystemExit(harness.run_all(sys.argv[1:], lower, fstar_backend,
                                     "fst"))
