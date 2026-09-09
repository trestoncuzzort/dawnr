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

  DIV/MOD (2026-09-08). `div` and `mod` lower to F*'s native `/` and `%`
  (Prims.op_Division, Prims.op_Modulus) on int. Measured on F* 2026.08.30:
  assert_norm proves (-7)/2 = -4, (-7)%2 = 1, 7/(-2) = -3, 7%(-2) = 1,
  (-7)/(-2) = 4 and (-7)%(-2) = 1, all six of SPEC.md's Euclidean facts, so
  the native operators need no reencoding. Definedness is discharged the
  same way `at` is: F*'s `/` and `%` type the divisor as `y:int{y <> 0}`,
  so `x / y` is not well-typed until the kernel proves `y <> 0` from the
  path condition, exactly the subtyping check `at` gets from Seq.index's
  refinement. Measured directly: a term `x / y` with `y` an unrefined int
  parameter fails to typecheck, and passes once `y <> 0` is in scope
  (a requires clause, an `if y <> 0` guard, or a refined binder). So the
  printer emits `(a / b)` and `(a % b)` with no extra guard, the same
  parenthesisation `*` gets, since F*'s `/` and `%` bind at the same
  precedence as `*`.

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

  EARLY EXIT (2026-09-08). A `return` inside the loop body (SPEC.md "Early
  exit") makes `<name>_loop`'s result an `either ret_t state_ty`, F*'s
  builtin sum type, instead of the bare state: `Inl v` when this call
  returned a value (never recursing further; the loop's invariant is not
  owed there), or `Inr s` when the guard went false and the loop exited
  normally with state `s` (invariant and negated guard, unchanged from
  before early exit existed). The value case's postcondition is literally
  the task's own `ensures` applied to the returned value, not a formula
  re-derived here: F*'s VC generator already carries the guard and the
  returning branch's own condition as hypotheses at that program point
  (they are the literal `if` nesting the recursive call sits under), so
  proving `ensures` there is the same kind of obligation the normal exit
  already discharges from the invariant and the negated guard. `exec_flow`
  (below `exec_straight`) computes that condition and value once, by
  symbolic execution parallel to the ordinary per-var if-merge: a `return`
  is always the last statement of its own block (SPEC.md), so an `if` that
  returns in one branch only changes what the SIBLINGS after it see, never
  what came before. A `return` outside any loop lowers the same way, in
  `gen_fun`: no `either`, just `if <condition> then <value> else
  <fallthrough>` in the function body. A `return` in a loop's prefix or
  suffix (not the loop body itself, and not a loop-free body) is not
  lowered: `exec_straight` abstains rather than drop it, since threading
  the outcome type there would also condition the loop call itself, which
  gen_loop does not build; no committed task needs it, both first_even and
  is_prime put their `return` directly in the loop body.

  RECURSION. spec_funs lower to `let rec ... : Tot ... (decreases m)`; a
  self-recursive task lowers to a `let rec` carrying its contract as Pure
  requires/ensures plus the task decreases clause. Self-calls stay in
  expression position: F* is a CBV expression language, so no hoisting and
  none of Dafny's lazy-position refusals are needed; the kernel applies
  the modular contract (callee requires proved at the site, ensures
  assumed of the result) at every call.

  SEQUENCES AS VALUES (2026-09-09, SPEC.md "Sequences as values"). `seq`
  becomes a return and local type, not only a param's; `update` (`s[i :=
  v]`) and `fill` (`seq(n, v)`) are new Expr forms; `==`/`!=` on two seqs
  are extensional. `TY["seq"]` already existed (`Seq.seq int`, Gate 1's
  own type), so params, spec_fun params and every binder needed no change;
  what a seq RETURN or LOCAL needed was `sx` (below `seq_var`, which it
  replaces), the seq-expression analogue of `zx`/`bx`, threaded through
  `env` in `exec_flow`'s assign/var/return cases exactly as an int or bool
  slot already was, plus `_dummy`/`_render` to dispatch a right-hand side
  on its t type instead of the old two-way bool/int ternary repeated at
  three call sites. Measured on F* 2026.08.30, no reencoding needed for
  either op: `Seq.upd s i v` and `Seq.create n v` both verify unassisted
  from an unrefined `s`/`n`/`i` given only the ambient `0 <= i < len(s)` /
  `n >= 0` requires (P1.fst probe), because `Seq.upd`'s index parameter is
  `n:nat{n < length s}` and `Seq.create`'s length is `nat`, the same
  domain-refinement subtyping check `at` and `div`/`mod` already get, and
  their own SMTPat'd index/length lemmas (`lemma_index_upd1/2`,
  `lemma_index_create`) are automatic, no assist needed. Extensional `==`
  is `Seq.equal`, NEVER F*'s own `==` on a `Seq.seq`: measured directly
  (P2.fst), `Seq.upd s i (Seq.index s i) == s` (bare `==`) fails to prove,
  Error 19, while `Seq.equal (Seq.upd s i (Seq.index s i)) s` and a second
  probe swapping two out-of-order updates both verify with `()`, no lemma
  invoked by name: `Seq.equal` is an opaque `Tot prop` whose own
  `lemma_eq_intro`/`lemma_eq_elim` carry SMTPat keyed on the literal term
  `Seq.equal s1 s2`, so writing that term at all triggers both directions
  (pointwise facts -> `equal`, `equal` -> propositional `==`) with nothing
  invoked here. The negative direction is NOT similarly automatic --
  proving two seqs are NOT `Seq.equal` (a real length mismatch) came back
  "incomplete quantifiers" (P2.neq_probe) -- so `!=` renders the same
  honest `(~ (Seq.equal a b))` and is left for the kernel to prove or not;
  no committed task needs it. The computational (non-spec) position uses
  `Seq.eq`, the DECIDABLE bool form for `int`'s `eqtype`, whose own
  postcondition is `r <==> Seq.equal a b`, so `bx`'s `==`/`!=` on seqs cost
  no separate proof either. One rendering bug this surfaced and fixed:
  `TY["seq"]` is two tokens (`Seq.seq int`) and a binder's enclosing parens
  hid that everywhere `seq` was only ever a PARAM type, but a bare `Pure
  {TY[ret_t]}` is not enclosed by anything -- measured, `Pure Seq.seq int
  (requires ..) (ensures ..)` fails to desugar, "Unexpected arguments to
  effect Prims.Pure" (F* error 146, P3.fst), while `Pure (Seq.seq int)
  ...` and `either (Seq.seq int) int` (P4.fst) both verify -- so `_pty`
  parenthesizes TY's value only at the three bare-type call sites (a
  task's own `Pure`, a single-state-var loop helper's `Pure`, and
  `outcome_ty`'s `either`) and TY itself stays bare, so abs.fst,
  first_even.fst and digit_sum.fst (no seq return/update) are byte-
  identical to before this change, diffed against a HEAD checkout.
    The twin path needed one more thing: swap's canonical twin (no `if`,
  so COLLAPSE-IF/NEGATE-COND/COMPARE-FLIP/BOUNDARY-SWAP all abstain; the
  first OFF-BY-ONE candidate is the `at(s, i)` in `tmp := s[i]`, mutated to
  `s[i+1]`) is a `_kind == "undefined"` witness (s=[0], i=0, j=0: the real
  body has a value, the twin's `s[1]` does not), which `lower_verus.py`'s
  shared `certificate_formula` did not certify when this file's own work
  started (measured first: swap REFUSED, "real verified, off-by-one twin
  unproved", F* Error 19 on the twin's own `Seq.index` subtyping check --
  SPEC.md's "nothing is totalized", never a bare pass, exactly as
  designed). `lower_verus.py` gained undefined-kind support the same day
  (`_undef_obligation`, re-walking the twin's statements with `interp.ev`);
  this file needed no code of its own for it beyond what was already
  there, because the certificate is still an ordinary t Expr tree and the
  same `cx.prop(formula, {}, {})` call already renders it. Measured after:
  swap COUNTS (witness s=[0], i=0, j=0 -> real [0], twin "at index 1
  outside [0,1)"), the certificate a ground fact with no seq-typed operand
  at all (the guard is stated over the index and the concrete length, not
  the sequence value), discharged by `assert_norm` with no SMT fallback
  exactly as the value/exit cases already were. Regression: all 15 pre-
  existing tasks' lowered output (`out/*.fst`, real and twin, byte for
  byte) is unchanged from a HEAD checkout, and all 17 tasks in
  `tasks/*.json` COUNT, the 15 old ones reading exactly AGREEMENT.md's
  fstar column (verified/refuted throughout).

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
ARITH = {"+": "+", "-": "-", "*": "*", "div": "/", "mod": "%"}


def _pty(t: str) -> str:
    """TY[t], parenthesized when it is more than one token (`Seq.seq int`,
    2026-09-09: a seq return/local's type, unlike a binder's `(name:TY[t])`
    where the enclosing parens already disambiguate it). Bare positions
    need this and binder positions must NOT get it, measured directly:
    `: Pure Seq.seq int (requires ...) (ensures ...)` fails to desugar,
    "Unexpected arguments to effect Prims.Pure" (F* 2026.08.30 error 146,
    Pure's grammar takes exactly one type field before its `(requires
    ...)`/`(ensures ...)` clauses, so an unparenthesized two-token type
    swallows `int` as a second argument to the effect), while `: Pure
    (Seq.seq int) (requires ...) (ensures ...)` and `either (Seq.seq int)
    int` both verify. TY itself stays bare so every existing `({name}:
    {TY[...]})` binder (params, spec_fun params, loop-frame binders) is
    untouched: those already sit inside their own enclosing parens and
    changing TY's own value for a task with no seq return/local would have
    changed abs.fst/first_even.fst/digit_sum.fst's bytes for no reason."""
    v = TY[t]
    return f"({v})" if " " in v else v


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
        if "_seq" in e:
            return "seq"
        if "var" in e:
            return local.get(e["var"]) or self.tys[e["var"]]
        if "forall" in e or "exists" in e:
            return "bool"
        if "ite" in e:
            return self.ty(e["ite"]["then"], local)
        if "call" in e:
            return self.funs[e["call"]["fun"]]["result"]
        op = e["op"]
        if op in ("update", "fill"):
            return "seq"
        if op in ARITH or op in ("neg", "len", "at"):
            return "int"
        return "bool"

    def sx(self, e: dict, env: dict, local: dict) -> str:
        """Seq-valued term. Through 2026-09-08 a seq position could only be
        a variable or a ground `_seq` literal (the certificate's own
        witness rendering); since 2026-09-09 ("Sequences as values", v1) a
        seq local or return can be REASSIGNED to a fresh `update`/`fill`
        term, exactly as an int local is, so a seq position is now any of:
        a variable, looked up through `env` like `zx`/`bx` already do (not
        just its bare name, which was fine only because no seq-typed
        assignment existed to shadow it); a ground `_seq` literal; or
        `update`/`fill` themselves, rendered to FStar.Seq's own `upd` and
        `create`. Both are used with no reencoding and no extra guard, the
        same posture DIV/MOD's note takes: `Seq.upd`'s index parameter is
        `n:nat{n < length s}` and `Seq.create`'s length parameter is `nat`,
        so `0 <= i < len(s)` (`update`) and `n >= 0` (`fill`) are, exactly
        like `at`'s domain refinement, subtyping checks the kernel is
        already forced to discharge from the ambient path condition:
        nothing here re-derives or re-guards what F*'s own signatures
        already require."""
        if "var" in e and (local.get(e["var"]) or self.tys.get(e["var"])) == "seq":
            return env.get(e["var"], e["var"])
        if "_seq" in e:
            # A GROUND seq value, which only the refutation certificate
            # below produces (a witness substituting a concrete sequence
            # into a seq-typed parameter or return) or a `fill`/`update`
            # tree that bottoms out at one.
            items = "; ".join(str(int(v)) for v in e["_seq"])
            return f"(Seq.createL #int [{items}])"
        op = e.get("op")
        if op == "update":
            s, i, v = e["args"]
            return (f"(Seq.upd {self.sx(s, env, local)} "
                    f"{self.zx(i, env, local)} {self.zx(v, env, local)})")
        if op == "fill":
            n, v = e["args"]
            return f"(Seq.create {self.zx(n, env, local)} {self.zx(v, env, local)})"
        raise NotImplementedError(f"seq position holds non-variable {e!r}")

    def call(self, e: dict, env: dict, local: dict) -> str:
        c = e["call"]
        info = self.funs[c["fun"]]
        parts = [c["fun"]]
        for formal, a in zip(info["params"], c["args"], strict=True):
            if formal["type"] == "seq":
                parts.append(self.sx(a, env, local))
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
            return f"(Seq.length {self.sx(e['args'][0], env, local)})"
        if op == "at":
            return (f"(Seq.index {self.sx(e['args'][0], env, local)} "
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
            if t == "seq":
                # Computational position: Seq.eq is the DECIDABLE bool
                # form (int is an eqtype), r <==> Seq.equal a b by its own
                # signature, so no separate proof is owed here beyond what
                # `Seq.eq`'s postcondition already gives the kernel.
                a, b = (self.sx(x, env, local) for x in e["args"])
                core = f"(Seq.eq {a} {b})"
                return core if op == "==" else f"(not {core})"
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
            t0 = self.ty(e["args"][0], local)
            if t0 == "bool":
                a, b = (self.prop(x, env, local) for x in e["args"])
                core = f"({a} <==> {b})"
            elif t0 == "seq":
                # Extensional equality (SPEC.md "Sequences as values"):
                # FStar.Seq.Base's `equal` is an opaque Tot prop, never F*'s
                # own `==` on seq (measured false: a bare `s1 == s2` between
                # two differently-built-but-pointwise-equal seqs is NOT
                # proved by the ambient upd/index/create SMT patterns alone,
                # 2026-09-09 probe P2.bare_eq_probe, Error 19). `equal`
                # itself carries the round trip as two SMTPat'd lemmas keyed
                # on the literal term `Seq.equal s1 s2`: lemma_eq_intro
                # turns "same length, same index everywhere" (already
                # ambient from upd/index/create's own patterns) into `equal
                # s1 s2`, and lemma_eq_elim turns `equal s1 s2` into F*'s
                # propositional `s1 == s2`. So rendering `==` as `Seq.equal`
                # gets both directions for free the moment the term appears
                # in the query; no lemma is invoked by name here. Measured
                # 2026-09-09: P2.noop_probe and P2.swap_swap_probe (two
                # pointwise-equal-but-differently-built seqs) both verify
                # with `()`, no assist. The POSITIVE direction only:
                # proving two seqs are NOT `Seq.equal` (a real length
                # mismatch, `!=`) is not similarly pattern-driven --
                # P2.neq_probe (create 2 v != create 3 v) came back
                # "incomplete quantifiers", UNPROVED at the default budget
                # -- so a `!=` on seqs is emitted the same honest way and
                # left for the kernel to prove or not; no committed task
                # needs it.
                a, b = (self.sx(x, env, local) for x in e["args"])
                core = f"(Seq.equal {a} {b})"
                return core if op == "==" else f"(~ {core})"
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


def _render(cx: "Ctx", e: dict, t: str, env: dict, local: dict) -> str:
    """An assign/var-init/return right-hand side, dispatched on its t type
    (SPEC.md 2026-09-09: a seq is now a local/return type, not only a
    param), so a seq-typed slot is threaded through `env` exactly like an
    int or bool one, and a later `update`/`fill` sees the PREVIOUS value
    through `sx`'s own env lookup rather than the bare variable name."""
    if t == "bool":
        return cx.bx(e, env, local)
    if t == "seq":
        return cx.sx(e, env, local)
    return cx.zx(e, env, local)


def _dummy(t: str) -> str:
    """A throwaway, well-typed literal for a slot that types but is never
    read (SPEC.md "Early exit"'s unreached branch, and a loop's initial
    `env` before anything is threaded through it). `Seq.createL #int []`
    matches the empty-seq literal the certificate below already emits for
    `_seq: []`, rather than a second spelling of the same empty sequence."""
    if t == "bool":
        return "false"
    if t == "seq":
        return "(Seq.createL #int [])"
    return "0"


# --------------------------------------------------------------- return ----
# Early exit (SPEC.md "Early exit", stated 2026-09-08). `exec_flow` is
# `exec_straight`'s generalisation: it threads a `(retcond, retval)` pair
# alongside the merged environment, so a `return` can be handled the same
# way an `if`-merge already is, with no new representation. `retcond` is a
# bx expression ("false" when no path taken so far returns, "true" when
# every path does, or an `if`-merge of the two otherwise); `retval` is the
# value the return statement computed, rendered like any assign's
# right-hand side, meaningful exactly where `retcond` holds and otherwise a
# well-typed placeholder (`dummy`) so every branch of every generated `if`
# still typechecks. A bare `return` is always the LAST statement of its own
# block (SPEC.md: "no statement of its own block may follow it"), so it
# never needs to skip over siblings; an `if` that returns in one branch is
# not necessarily last, so statements after it execute along the
# non-returning path only, via the recursive call on `stmts[idx + 1:]`.
def exec_flow(cx: Ctx, stmts: list, env: dict, local: dict, dummy: str):
    env = dict(env)
    for idx, s in enumerate(stmts):
        if "return" in s:
            name, e = s["return"]
            t = local.get(name) or cx.tys[name]
            val = _render(cx, e, t, env, local)
            return env, "true", val
        elif "assign" in s:
            v, e = s["assign"]
            t = local.get(v) or cx.tys[v]
            env[v] = _render(cx, e, t, env, local)
        elif "var" in s:
            d = s["var"]
            v = _ck(d["name"])
            assert v not in cx.tys and v not in local, f"redeclared {v}"
            local[v] = d["type"]
            env[v] = _render(cx, d["init"], d["type"], env, local)
        elif "if" in s:
            c = s["if"]
            cb = cx.bx(c["cond"], env, local)
            env_t, rc_t, rv_t = exec_flow(cx, c["then"], env, dict(local), dummy)
            env_e, rc_e, rv_e = exec_flow(cx, c["else"], env, dict(local), dummy)
            drop = _decls(c["then"]) | _decls(c["else"])
            merged = {}
            for v in sorted((set(env_t) | set(env_e) | set(env)) - drop):
                tv, ev = env_t.get(v, v), env_e.get(v, v)
                merged[v] = tv if tv == ev else f"(if {cb} then {tv} else {ev})"
            if rc_t == "false" and rc_e == "false":
                env = merged
                continue
            # `rc_e == "false"` (only `then` returns) collapses to `cb`
            # itself rather than `(if cb then true else false)`, and
            # likewise the other way; this is the shape both committed
            # early-exit tasks hit (`if cond { return } else {}`), so it
            # keeps the emitted term legible instead of double-wrapping.
            if rc_t == "true" and rc_e == "true":
                rc_if = "true"
            elif rc_e == "false":
                rc_if = cb
            elif rc_t == "false":
                rc_if = f"(not {cb})"
            else:
                rc_if = f"(if {cb} then {rc_t} else {rc_e})"
            if rc_e == "false":
                rv_if = rv_t
            elif rc_t == "false":
                rv_if = rv_e
            elif rv_t == rv_e:
                rv_if = rv_t
            else:
                rv_if = f"(if {cb} then {rv_t} else {rv_e})"
            rest_env, rc_rest, rv_rest = exec_flow(
                cx, stmts[idx + 1:], merged, local, dummy)
            if rc_if == "false":
                return rest_env, rc_rest, rv_rest
            if rc_rest == "false":
                return rest_env, rc_if, rv_if
            overall_rc = "true" if rc_if == "true" \
                else f"(if {rc_if} then true else {rc_rest})"
            overall_rv = rv_if if rv_if == rv_rest \
                else f"(if {rc_if} then {rv_if} else {rv_rest})"
            return rest_env, overall_rc, overall_rv
        elif "while" in s:
            raise AssertionError("while must be split out before exec")
        else:
            raise ValueError(f"t -> fstar: no statement {list(s)!r}")
    return env, "false", dummy


def exec_straight(cx: Ctx, stmts: list, env: dict, local: dict) -> dict:
    """env maps mutable name -> term (absent = the name itself); local maps
    locals -> t type. Branch-declared locals do not escape their branch;
    a mutable first assigned inside a branch still merges.

    A thin wrapper over `exec_flow` for the call sites that do not carry an
    outcome type to report a `return` through: a loop's prefix and suffix.
    SPEC.md lets a `return` appear inside an `if` there too (nothing bars it
    syntactically as long as it is the last statement of its own branch),
    but that would require the loop itself, and everything after it in the
    enclosing block, to run conditionally on "did the prefix already
    return" -- a shape gen_loop does not build. Abstain rather than drop
    the return's effect; the two committed early-exit tasks both put their
    `return` inside the loop body, which `exec_flow` handles directly."""
    env2, retcond, _ = exec_flow(cx, stmts, env, local, "0")
    if retcond != "false":
        raise NotImplementedError(
            "fstar lowering: a `return` in a loop's prefix or suffix is "
            "not lowered yet")
    return env2


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
    decreases measure and applies the contract modularly at self-calls).

    A `return` outside any loop (SPEC.md "Early exit") is exactly a return
    inside an `if` in straight-line code here: `exec_flow` reports it as
    `(retcond, retval)` and the function body becomes
    `if retcond then retval else <fallthrough>`, with F*'s own VC generator
    carrying every accumulated branch condition as a hypothesis when it
    checks the task's `ensures` at `retval`, the same way it already does
    for the fallthrough value."""
    name = task["name"]
    ret = task["returns"][0]["name"]
    ret_t = task["returns"][0]["type"]
    pb, _ = param_binders(task)
    req, ens = task_spec(cx, task)
    dummy = _dummy(ret_t)
    env, retcond, retval = exec_flow(cx, body, {ret: dummy}, {}, dummy)
    if retcond == "false":
        expr = env[ret]
    elif retcond == "true":
        expr = retval
    else:
        expr = f"(if {retcond} then {retval} else {env[ret]})"
    selfrec = has_self_call(body, name)
    dec = ""
    if selfrec:
        assert "decreases" in task, "self-recursive task without decreases"
        dec = f"\n    (decreases {cx.zx(task['decreases'], {}, {})})"
    return (f"let {'rec ' if selfrec else ''}{name} {pb}\n"
            f"  : Pure {_pty(ret_t)}\n"
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
    env_pre = exec_straight(cx, prefix, {ret: _dummy(ret_t)}, local)
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

    dummy = _dummy(ret_t)
    step_env, body_rc, body_rv = exec_flow(cx, w["body"], {}, dict(local), dummy)
    step = " ".join(step_env.get(v, v) for v in svars)
    env_post = exec_straight(cx, suffix, {}, dict(local))
    result = env_post.get(ret, ret)

    post = _conj(invs + [f"(~ {guard_p})"])
    if len(svars) == 1:
        state_ty = _pty(stys[svars[0]])
        state_out = svars[0]
    else:
        state_ty = "(" + " & ".join(TY[stys[v]] for v in svars) + ")"
        state_out = "(" + ", ".join(svars) + ")"

    init = " ".join(env_pre.get(v, v) for v in svars)
    fbind = "".join(f"let {v} = {env_pre.get(v, v)} in\n  " for v in fvars)

    if body_rc == "false":
        # No `return` in the loop body: unchanged since before early exit
        # existed. `state_out` doubles as both the plain recursive result
        # and, in exec_straight's merged environment, the destructuring
        # pattern bound by `bind` below.
        if len(svars) == 1:
            loop_ens = f"(fun {svars[0]} -> {post})"
            bind = f"let {svars[0]}"
        else:
            ob = cx.fresh()
            loop_ens = (f"(fun {ob} -> let ({', '.join(svars)}) = {ob} in "
                        f"{post})")
            bind = f"let ({', '.join(svars)})"
        return (f"let rec {lname} {pb}{fb} {sb}\n"
                f"  : Pure {state_ty}\n"
                f"    (requires {_conj(reqs + invs)})\n"
                f"    (ensures {loop_ens})\n"
                f"    (decreases {dec})\n"
                f"= if {guard_b}\n"
                f"  then {lname} {pargs}{fargs} {step}\n"
                f"  else {state_out}\n"
                f"\n"
                f"let {name} {pb}\n"
                f"  : Pure {_pty(ret_t)}\n"
                f"    (requires {req})\n"
                f"    (ensures {ens})\n"
                f"= {fbind}{bind} = {lname} {pargs}{fargs} {init} in\n"
                f"  {result}\n")

    # A `return` inside the loop body (SPEC.md "Early exit", 2026-09-08).
    # `<lname>` now yields ONE of two outcomes, encoded as F*'s builtin
    # `either`: `Inl v` when the body returned a value on this call (never
    # recursing further; the invariant is not owed there, only the task's
    # own `ensures`), or `Inr s` when the guard went false and the loop
    # exited normally with the same state `s` as before (the invariant and
    # negated guard, exactly as when there is no early exit). The value
    # case's postcondition is literally the task's own `ens` applied to the
    # returned value: F*'s VC generator already carries `guard_b` and the
    # returning branch's own condition (folded into `body_rc`/`body_rv` by
    # exec_flow) as hypotheses at that program point, from the `if guard_b
    # then (if body_rc then Inl body_rv else ...)` shape below, so proving
    # `ens body_rv` there is the same kind of obligation the normal exit
    # discharges from the invariant and the negated guard.
    outcome_ty = f"(either {_pty(ret_t)} {state_ty})"
    rvar = cx.fresh()
    loop_ens = (f"(fun res -> match res with "
                f"| Inl {rvar} -> ({ens} {rvar}) "
                f"| Inr {state_out} -> {post})")
    then_branch = f"(if {body_rc} then Inl {body_rv} else {lname} {pargs}{fargs} {step})"
    else_branch = f"Inr {state_out}"
    wvar = cx.fresh()
    return (f"let rec {lname} {pb}{fb} {sb}\n"
            f"  : Pure {outcome_ty}\n"
            f"    (requires {_conj(reqs + invs)})\n"
            f"    (ensures {loop_ens})\n"
            f"    (decreases {dec})\n"
            f"= if {guard_b}\n"
            f"  then {then_branch}\n"
            f"  else {else_branch}\n"
            f"\n"
            f"let {name} {pb}\n"
            f"  : Pure {_pty(ret_t)}\n"
            f"    (requires {req})\n"
            f"    (ensures {ens})\n"
            f"= {fbind}match {lname} {pargs}{fargs} {init} with\n"
            f"  | Inl {wvar} -> {wvar}\n"
            f"  | Inr {state_out} -> {result}\n")


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
# loop-exit state; for an undefined witness (SPEC.md "Sequences as values",
# 2026-09-09: the twin's own body hits `at`/`update`/`fill`/`div`/`mod`
# outside its domain before any ensures instance can even be stated) requires
# at the witness conjoined with the negated definedness obligation
# `lower_verus._undef_obligation` finds by re-walking the twin's statements
# with `interp.ev`. Preservation is still not certificated and honestly
# reads unproved.
#
# Measured 2026-09-09 on swap's canonical twin (OFF-BY-ONE on the `at(s, i)`
# in `tmp := s[i]`, mutated to `s[i+1]`; witness s=[0], i=0, j=0, undefined
# because `s[1]` is out of range): before lower_verus.py's undefined-kind
# support landed, `certificate_formula` returned None here and swap read
# REFUSED, "real verified, off-by-one twin unproved" (F* Error 19 on the
# twin's own `Seq.index` subtyping check -- SPEC.md's "nothing is
# totalized", never a bare pass). With it, the formula renders as a ground
# fact with no seq-typed operand at all (the guard is stated in terms of the
# index and the concrete length, not the sequence value, matching every
# other column's reading of this witness), `assert_norm` discharges it with
# no SMT fallback exactly as the value/exit cases already do, and swap COUNTS
# (witness s=[0], i=0, j=0 -> real [0], twin "at index 1 outside [0,1)").
# This file's `sx`'s `_seq` literal path is exercised only by `requires`'
# own `len(s)` here, not by anything the undefined case itself needed: no
# new rendering code in this file, the same `cx.prop(formula, {}, {})` call
# below carries it, because the formula is still an ordinary t Expr tree.
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
