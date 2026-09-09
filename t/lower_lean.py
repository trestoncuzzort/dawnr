#!/usr/bin/env python3
"""lower_lean.py: lower t tasks (v0 and v1) to Lean 4; the proof-assistant kernel.

THE PROOF-ASSISTANT DIFFERENCE, made concrete: the lowering emits functions,
theorems stating every ensures clause with the return name replaced by the
applied function, and PROOFS. Lean has no SMT sidecar, so every verdict is the
kernel accepting (or rejecting) a proof term. The automation used is real and
kernel-checked: `omega` (linear integer arithmetic) and `grind` (congruence +
E-matching + case splits + linear arith, in core Lean since 4.22). No proof
term is hand-plumbed per task; every tactic script below is derived from the
BODY SHAPE by one rule, identically for every task:

  SIMPLE     (no loop, no self-call: all v0 tasks, and collapse-if twins
              whose recursion collapsed away): one function, one theorem,
              `unfold; grind`. The v0 lesson is kept: every script is a
              `first | ... | grind [f]` so a twin whose shape no longer fits
              the primary script fails on TRUTH (grind reasoning about the
              unfolded body), never on tactic shape.
  RECURSIVE  (body self-calls): the function takes the conjoined `requires`
              as a hypothesis argument, Lean-native partial functions, and
              every self-call discharges the callee's requires with a real
              `by omega/grind` proof; `termination_by (decreases).toNat`
              carries the t termination obligation. The theorem is itself
              recursive: it binds its own induction hypothesis as a `have`
              guarded by t's decreases obligation (0 <= smaller < current),
              then unfolds one step, splits the branches, and grinds, and the
              IH is the modular contract of every smaller call.
              (fun_induction was measured and refused: grind cannot bridge
              the dependent requires-proof argument across arithmetic
              normalization: gcd's `a - b` leaf never met its induction
              hypothesis.)
  LOOP       (body contains one top-level while): the loop becomes a
              tail-recursive function over the mutable state; the invariants
              become hypotheses of a recursive helper theorem, and the induction
              hypothesis is literally the invariant list. Guard-true steps
              re-enter the lemma at the symbolically-updated state (invariant
              preservation, by grind); guard-false discharges the ensures
              from invariants + ¬guard (by grind). Merged if-updates are
              pre-`split` so grind reasons per-branch. Measured: without the
              split, grind loses the existential-invariant preservation of
              seq_max in cutsat case explosions.

DEFINEDNESS IS NOT SILENTLY TOTALIZED. `at` is lowered to the total
`s[i.toNat]!` for computation, and the SPEC.md definedness obligations are
emitted as separate _wf theorems, one per non-trivially-defined clause /
program point, each proved under exactly the context SPEC.md grants it
(earlier requires; requires + earlier ensures; earlier invariants;
invariants + guard for the loop body, with short-circuit and taken-branch
rules built into the D() calculus below). A file only verifies if its
definedness obligations also prove.

Existential-invariant establishment gets one generic heuristic: if plain
grind fails, retry with the range's lower endpoint as witness (`exact ⟨lo,
by grind⟩`), needed because Int-literal toNat indices normalize away the
E-matching pattern grind would use to find the witness itself (measured on
seq_max's `∃ j ∈ [0,1)` at r = s[0]).

Every file ends with `#print axioms` per theorem; the adapter audits the list.

ABSTAIN policy: shapes this lowering cannot express honestly raise
NotImplementedError with the reason (multiple/nested loops, a loop plus
self-recursion, quantifiers in computational position). A recorded absence,
never a faked proof.

THE REFUTATION CERTIFICATE (2026-09-02, certificate protocol shared by all
columns): when lowering a TWIN with a measured witness, one extra theorem
named exactly t_refutation_certificate is emitted; verifiers/lean.py mints
REFUTED only when the kernel accepts it. The theorem states, at the
concrete witness, ground facts the kernel re-evaluates itself:
  value witness         requires holds at the input, and the ensures fails
                        at the twin function applied to that input;
  exit witness          requires, the surviving invariants, and the negated
                        guard hold at the loop state, and the ensures fails
                        at the loop function applied to that state, which
                        refutes the instance of {name}_t_loop_spec that the
                        surviving invariants were supposed to carry;
  preservation witness  requires, the surviving invariants and the guard
                        hold at the loop state, and one loop step (the
                        symbolic update expressions instantiated at the
                        state, re-evaluated by the kernel) breaks them.
Proofs are ground and kernel-checked: decide, omega, simp with explicit
names, grind with explicit names, plus enumeration of ground-bounded
quantifiers (native_decide stays banned). t/interp.py evaluation only
CHOOSES the proof path (which conjunct fails, which index witnesses); every
choice is then re-proved by the kernel, so a wrong choice can only cost the
certificate, never mint one. An undefined-kind witness (interp.py's Undef)
is certificated too, since 2026-09-09 (below) for loop-free bodies; for a
loop-shaped body it is still not: no ground negation is built there, and
the twin cell honestly reads unproved. A certificate the kernel rejects
also reads unproved; only kernel acceptance mints REFUTED, and a file
carrying the certificate name can never verify.

SEQUENCES AS VALUES (2026-09-09, SPEC.md "Sequences as values", ROADMAP
12.7): `seq` was already Gate 1's `List Int` (a read-only param); this
lands it as a return and local type, plus `update` (`s[i := v]`) and
`fill` (`seq(n, v)`). Measured on lean 4.33.1, core only, no Mathlib:
  native forms   `s[i := v]` -> `s.set (i).toNat v` (List.set); `seq(n, v)`
                 -> `List.replicate (n).toNat v`; both TOTAL like `at`
                 (List.set no-ops out of range, List.replicate clamps a
                 negative length to 0 via `.toNat`), so definedness is
                 owed the same separate way `at`'s `0 <= i < len` already
                 is: `update`'s obligation is `0 <= i < len(s)`, `fill`'s
                 is `n >= 0`, both in dcond().
  extensional == `List` equality is already Lean's native `=` (structural,
                 decidable, exactly SPEC.md's "equal lengths and equal
                 elements at every index"), and `prop()`'s `==`/`!=` already
                 fell through to term equality for any non-bool sort before
                 this landed, so seq equality needed no new code at all,
                 only `sort()` learning that `update`/`fill` denote `seq`
                 (they fell to its `bool` default before, which would have
                 misrouted a future `update(...) == s` through the Prop-iff
                 branch built for `bool`).
  lemmas         `List.length_set` and `List.length_replicate` are already
                 in grind's own default simp set (plain `grind` proves both
                 alone, measured). A READ after a set/replicate, once the
                 index is the Int-cast-through-`.toNat` this file's `at`
                 already uses, is not: grind finds `List.getElem?_set` /
                 `getElem!_pos` / `getElem!_neg` as candidates (visible in
                 its own diagnostics) but the search to fire them past the
                 cast layer hits Lean's recursion-depth cap before deciding
                 the index equality (measured on reverse's own
                 loop-preservation goal: `grind` and even `grind
                 [t_seq_update_get]` both hit the cap). Two lemmas proved
                 by hand once per file (`getElem!_pos` totalizes `!` to
                 plain `getElem`, then `List.getElem_set` / a `by_cases` on
                 the index plus `omega` on the `.toNat` cast, exactly what
                 grind was attempting) close it when handed to `grind only`
                 instead of `grind`: `only` matters as much as the lemmas,
                 since it stops grind from also re-exploring the same
                 default set whose search was the actual depth source.
                 Emitted (`emit_seq_helpers`) and used (`_gr`, the
                 grind-call-site replacement; `_close`'s new branch) only
                 when a task touches `update`/`fill` at all (`self.seq_mut`),
                 so the fifteen pre-existing tasks are unaffected -- diffed
                 byte-identical (abs, first_even, digit_sum) before and
                 after.
  to_expr bug    found by swap (a SIMPLE-shape body with two sequential
                 assigns to the same seq-typed return, `r := s[i := s[j]];
                 r := r[j := tmp];`): `to_expr`'s non-tail `assign`/`var`
                 case dropped the reassigned name from `env` and let the
                 Lean `let x := t; ...` it emits supply the value by
                 lexical shadowing, which the COMPUTED TERM sees but the
                 definedness OBLIGATIONS list does not, since `obs` is
                 flattened into one top-level conjunction outside every
                 `let`. A later obligation needing the reassigned value
                 (here, `update`'s own `0 <= i < len(r)` on the SECOND
                 assign to `r`) got a bare `r` with no binder in scope,
                 `swap_t_wfbody` read MALFORMED. Fixed by substituting the
                 term text into `env` instead of dropping it (matching
                 sym()'s own convention for loop bodies), so every later
                 reference is self-contained; the `let` is gone too, since
                 nothing needs it once substitution supplies the value.
                 Dead path for every pre-existing task (none has a
                 multi-statement SIMPLE/RECURSIVE body: each is a single
                 top-level `if` or a single `assign`), so this changes no
                 committed output either.
  undefined kind swap's own twin (OFF-BY-ONE) lands on an undefined-kind
                 witness (index 1 outside [0,1) at s=[0]): computing the
                 twin's TOTALIZED value and comparing to `ensures` (the
                 first approach tried) is unsound to rely on, since Lean's
                 chosen default for an out-of-range read (`getElem!_neg`'s
                 `default = 0`) happens to equal s's own element at this
                 particular witness, so the totalized twin computes a value
                 that ACCIDENTALLY still satisfies `ensures` here even
                 though the same twin is genuinely wrong elsewhere
                 (`swap_t [10,20] 0 0` computes `[20, 20]`, not the `[10,
                 20]` swapping index 0 with itself should give). The robust
                 certificate instead states that the twin's OWN
                 definedness obligation -- literally `to_expr`'s own `obs`,
                 the same conjunction `{name}_t_wfbody` states -- is FALSE
                 once instantiated at the witness's ground terms: that
                 obligation is SPEC.md's definedness calculus itself, so
                 the ground instance is false exactly when interp.py's
                 exec_body would raise Undef there, and being a closed,
                 fully computable proposition, `decide` alone closes its
                 negation, no reliance on which value a partial operator
                 happens to totalize to. `_cert_undefined` builds this;
                 still returns None (the pre-existing abstain) for a
                 loop-shaped body, since `to_expr` only renders the
                 loop-free shape.
  measured       swap and reverse both COUNT (`python3 lower_lean.py swap
                 reverse`, and via harness.run_task): swap real VERIFIED,
                 off-by-one twin REFUTED at s=[0], i=0, j=0 (real [0], twin
                 undefined -- index 1 outside [0,1)); reverse real
                 VERIFIED, invariant-drop#1 twin REFUTED at the loop-exit
                 state s=[], i=0, r=[0]. All 15 pre-existing tasks still
                 read exactly their AGREEMENT.md lean column (14
                 verified/refuted, is_prime verified/refuted too -- its
                 rocq column, not lean's, is the one that reads
                 unproved/unproved), and three representative outputs
                 (abs.lean, first_even.lean, digit_sum.lean) are
                 byte-identical to before this landed.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                                 # noqa: E402
import interp                                  # noqa: E402
from verifiers import lean as lean_backend     # noqa: E402

CMP_OPS = {"<": "<", "<=": "≤", ">": ">", ">=": "≥"}
ARITH_OPS = {"+", "-", "*"}
# div/mod (SPEC.md "Division and modulo", 2026-09-08): measured on lean
# 4.33.1, core only, no Mathlib: `(-7:Int)/2=-4`, `(-7:Int)%2=1`, `7/-2=-3`,
# `7%-2=1`, `-7/-2=4`, `-7%-2=1` all hold by `decide`, and the truncating and
# floor expectations fail, so Lean's native Int `/` and `%` (Int.ediv /
# Int.emod under the hood) already are SPEC.md's Euclidean law and the
# lowering emits them as-is, no reimplementation. But that native division is
# total (`x / 0 = 0`, `x % 0 = x` by definition), so t's undefinedness at
# y == 0 is not enforced by the kernel: dcond() below adds the `y ≠ 0`
# obligation for both, discharged the same way as `at`'s `0 <= i < len`, as
# a separate _wf theorem, never folded into the total computation.
DIV_MOD = {"div": "/", "mod": "%"}
# The Euclidean law and its range fact are core lemmas about Lean's native
# (already-Euclidean) Int `/` and `%`, but measured (2026-09-08, on
# remainder's own contract) NOT to carry a grind/simp e-matching pattern
# that fires on the ring-normalized `a / b * b` term a goal like remainder's
# actually has, so naming them in a grind hint list does not help: they are
# supplied as ordinary `have` hypotheses instead (divmod_prelude/_close
# below) and a closing `omega` does the rest, since omega is exactly linear
# arithmetic once the facts are local terms.
CERT_NAME = "t_refutation_certificate"         # the contract with the adapter
MAX_ENUM = 16     # ground quantifier enumeration cap; witness domains are
                  # small (interp ladders), so past this the generic closers
                  # get their chance and a miss honestly reads unproved


def _collect_names(x, out: set) -> None:
    if isinstance(x, dict):
        for k, v in x.items():
            if k in ("var", "fun", "name") and isinstance(v, str):
                out.add(v)
            elif k == "assign":
                out.add(v[0])
                _collect_names(v[1], out)
            else:
                _collect_names(v, out)
    elif isinstance(x, list):
        for v in x:
            _collect_names(v, out)


def loop_assigned(body: list) -> set:
    """Syntactic assigned set of a loop body, SPEC.md's frame rule: a while
    loop havocs exactly the variables assigned in its body. `return`
    (SPEC.md "Early exit", 2026-09-08) assigns its target the same as
    `assign` does, matching interp.py's `assigned()`: a loop whose only
    write to the task's return name is a `return` must not be given a
    frame hypothesis pinning that name to its entry value, since the
    return path changes it."""
    out: set = set()
    for s in body:
        if "assign" in s:
            out.add(s["assign"][0])
        elif "return" in s:
            out.add(s["return"][0])
        elif "if" in s:
            out |= loop_assigned(s["if"]["then"])
            out |= loop_assigned(s["if"]["else"])
        elif "while" in s:
            out |= loop_assigned(s["while"]["body"])
    return out


class Lower:
    """One instance per (task, body) pair. Everything derives from the JSON."""

    def __init__(self, task: dict, body: list):
        self.task, self.body = task, body
        self.name = task["name"]
        self.ret = task["returns"][0]["name"]
        self.rett = task["returns"][0]["type"]
        self.types: dict[str, str] = {p["name"]: p["type"]
                                      for p in task["params"]}
        self.types[self.ret] = self.rett
        self.sfuns = {f["name"]: f for f in task.get("spec_funs", [])}
        self.used: set[str] = {self.name}
        _collect_names(task, self.used)
        _collect_names(body, self.used)
        self.fresh_n = 0
        self.hyp_n = 0
        self.ga = ("" if not self.sfuns else
                   " [" + ", ".join(f"{f}_s" for f in self.sfuns) + "]")
        # SPEC.md "Sequences as values" (2026-09-09): does this lowering
        # (task spec, or the body actually being lowered, real or twin)
        # touch `update`/`fill` anywhere. Gates the seq helper lemmas and
        # the grind-only fallback below; False for every pre-existing
        # task, so nothing about their output changes.
        self.seq_mut = (self._has(task, "op", "update")
                        or self._has(task, "op", "fill")
                        or self._has(body, "op", "update")
                        or self._has(body, "op", "fill"))

    # ---------- naming ----------

    def fresh(self, base: str) -> str:
        while True:
            self.fresh_n += 1
            cand = f"{base}_{self.fresh_n}"
            if cand not in self.used:
                self.used.add(cand)
                return cand

    def fresh_hyp(self) -> str:
        self.hyp_n += 1
        return f"_h{self.hyp_n}"

    # ---------- sorts ----------

    def sort(self, e: dict, types: dict) -> str:
        if "int" in e:
            return "int"
        if "bool" in e:
            return "bool"
        if "var" in e:
            return types[e["var"]]
        if "forall" in e or "exists" in e:
            return "bool"
        if "ite" in e:
            return self.sort(e["ite"]["then"], types)
        if "call" in e:
            f = e["call"]["fun"]
            if f == self.name:
                return self.rett
            return self.sfuns[f]["result"]
        op = e["op"]
        if op in ARITH_OPS or op in DIV_MOD or op in ("neg", "len", "at"):
            return "int"
        if op in ("update", "fill"):
            return "seq"
        return "bool"

    # ---------- expressions ----------

    def term(self, e: dict, env: dict, types: dict, dep: bool = False) -> str:
        """Computational (term-level) lowering. `env` substitutes names;
        `dep` makes ite dependent (named hypothesis) so nested requires /
        termination proofs see the branch condition."""
        if "int" in e:
            n = e["int"]
            return f"({n} : Int)" if n >= 0 else f"(({n}) : Int)"
        if "bool" in e:
            return "true" if e["bool"] else "false"
        if "var" in e:
            return env.get(e["var"], e["var"])
        if "ite" in e:
            c = e["ite"]
            cp = self.prop(c["cond"], env, types)
            t = self.term(c["then"], env, types, dep)
            f = self.term(c["else"], env, types, dep)
            if dep:
                return f"(if {self.fresh_hyp()} : {cp} then {t} else {f})"
            return f"(if {cp} then {t} else {f})"
        if "call" in e:
            c = e["call"]
            args = " ".join(self.term(a, env, types, dep) for a in c["args"])
            if c["fun"] == self.name:
                pre = " (by first | omega | grind)" if self.task.get(
                    "requires") else ""
                return f"({self.name}_t {args}{pre})"
            return f"({c['fun']}_s {args})"
        if "forall" in e or "exists" in e:
            raise NotImplementedError(
                "bounded quantifier in computational position "
                "is not lowered for lean")
        op = e["op"]
        if op == "len":
            s = self.term(e["args"][0], env, types, dep)
            return f"((({s}).length : Int))"
        if op == "at":
            s = self.term(e["args"][0], env, types, dep)
            i = self.term(e["args"][1], env, types, dep)
            return f"({s}[({i}).toNat]!)"
        if op == "update":
            s = self.term(e["args"][0], env, types, dep)
            i = self.term(e["args"][1], env, types, dep)
            v = self.term(e["args"][2], env, types, dep)
            return f"({s}.set ({i}).toNat {v})"
        if op == "fill":
            n = self.term(e["args"][0], env, types, dep)
            v = self.term(e["args"][1], env, types, dep)
            return f"(List.replicate ({n}).toNat {v})"
        if op == "neg":
            return f"(-{self.term(e['args'][0], env, types, dep)})"
        if op in ARITH_OPS:
            a, b = (self.term(x, env, types, dep) for x in e["args"])
            return f"({a} {op} {b})"
        if op in DIV_MOD:
            a, b = (self.term(x, env, types, dep) for x in e["args"])
            return f"({a} {DIV_MOD[op]} {b})"
        raise NotImplementedError(
            f"boolean operator {op!r} in computational position "
            "is not lowered for lean")

    def prop(self, e: dict, env: dict, types: dict) -> str:
        """Spec (Prop-level) lowering."""
        if "bool" in e:
            return "True" if e["bool"] else "False"
        if "var" in e:
            v = env.get(e["var"], e["var"])
            assert types[e["var"]] == "bool", f"int var {e['var']} as Prop"
            return f"({v} = true)"
        if "forall" in e:
            q = e["forall"]
            b = self.fresh(q["var"])
            lo = self.term(q["lo"], env, types)
            hi = self.term(q["hi"], env, types)
            body = self.prop(q["body"], {**env, q["var"]: b},
                             {**types, q["var"]: "int"})
            return f"(∀ ({b} : Int), {lo} ≤ {b} → {b} < {hi} → {body})"
        if "exists" in e:
            q = e["exists"]
            b = self.fresh(q["var"])
            lo = self.term(q["lo"], env, types)
            hi = self.term(q["hi"], env, types)
            body = self.prop(q["body"], {**env, q["var"]: b},
                             {**types, q["var"]: "int"})
            return f"(∃ ({b} : Int), {lo} ≤ {b} ∧ {b} < {hi} ∧ {body})"
        if "ite" in e:
            c = e["ite"]
            cp = self.prop(c["cond"], env, types)
            t = self.prop(c["then"], env, types)
            f = self.prop(c["else"], env, types)
            return f"(({cp} → {t}) ∧ (¬{cp} → {f}))"
        if "call" in e:
            return f"({self.term(e, env, types)} = true)"
        op = e["op"]
        if op in ("==", "!="):
            a, b = e["args"]
            if self.sort(a, types) == "bool":
                pa, pb = self.prop(a, env, types), self.prop(b, env, types)
                core = f"({pa} ↔ {pb})"
            else:
                ta, tb = self.term(a, env, types), self.term(b, env, types)
                core = (f"({ta} = {tb})" if op == "=="
                        else f"({ta} ≠ {tb})")
                return core
            return core if op == "==" else f"(¬{core})"
        if op in CMP_OPS:
            a, b = (self.term(x, env, types) for x in e["args"])
            return f"({a} {CMP_OPS[op]} {b})"
        if op == "not":
            return f"(¬{self.prop(e['args'][0], env, types)})"
        if op == "implies":
            p, q = (self.prop(x, env, types) for x in e["args"])
            return f"({p} → {q})"
        if op in ("and", "or"):
            j = " ∧ " if op == "and" else " ∨ "
            return "(" + j.join(self.prop(x, env, types)
                                for x in e["args"]) + ")"
        raise NotImplementedError(f"operator {op!r} in spec position "
                                  "is not lowered for lean")

    # ---------- definedness (SPEC.md "Definedness", as a calculus) ----------

    @staticmethod
    def _conj(parts: list) -> str | None:
        parts = [p for p in parts if p is not None]
        if not parts:
            return None
        return parts[0] if len(parts) == 1 else "(" + " ∧ ".join(parts) + ")"

    def dcond(self, e: dict, env: dict, types: dict) -> str | None:
        """The proposition under which e is defined; None means True.
        Encodes left-to-right short-circuit for and/or/implies, taken-branch
        for ite, per-element for quantifier bodies, and 0 <= i < len for at."""
        if "int" in e or "bool" in e or "var" in e:
            return None
        guard = lambda p, d: None if d is None else f"({p} → {d})"  # noqa: E731
        if "ite" in e:
            c = e["ite"]
            cp = self.prop(c["cond"], env, types)
            return self._conj([
                self.dcond(c["cond"], env, types),
                guard(cp, self.dcond(c["then"], env, types)),
                guard(f"¬{cp}", self.dcond(c["else"], env, types))])
        if "forall" in e or "exists" in e:
            q = e["forall"] if "forall" in e else e["exists"]
            b = self.fresh(q["var"])
            env2 = {**env, q["var"]: b}
            types2 = {**types, q["var"]: "int"}
            lo = self.term(q["lo"], env, types)
            hi = self.term(q["hi"], env, types)
            db = self.dcond(q["body"], env2, types2)
            parts = [self.dcond(q["lo"], env, types),
                     self.dcond(q["hi"], env, types)]
            if db is not None:
                parts.append(f"(∀ ({b} : Int), {lo} ≤ {b} → {b} < {hi} "
                             f"→ {db})")
            return self._conj(parts)
        if "call" in e:
            return self._conj([self.dcond(a, env, types)
                               for a in e["call"]["args"]])
        op = e["op"]
        if op == "at":
            s, i = e["args"]
            it = self.term(i, env, types)
            ln = f"((({self.term(s, env, types)}).length : Int))"
            return self._conj([
                self.dcond(s, env, types), self.dcond(i, env, types),
                f"(((0 : Int) ≤ {it}) ∧ ({it} < {ln}))"])
        if op == "update":
            s, i, v = e["args"]
            it = self.term(i, env, types)
            ln = f"((({self.term(s, env, types)}).length : Int))"
            return self._conj([
                self.dcond(s, env, types), self.dcond(i, env, types),
                self.dcond(v, env, types),
                f"(((0 : Int) ≤ {it}) ∧ ({it} < {ln}))"])
        if op == "fill":
            n, v = e["args"]
            nt = self.term(n, env, types)
            return self._conj([
                self.dcond(n, env, types), self.dcond(v, env, types),
                f"({nt} ≥ (0 : Int))"])
        if op in DIV_MOD:
            x, y = e["args"]
            yt = self.term(y, env, types)
            return self._conj([
                self.dcond(x, env, types), self.dcond(y, env, types),
                f"({yt} ≠ (0 : Int))"])
        if op in ("and", "or"):
            def chain(args):
                if not args:
                    return None
                head, rest = args[0], args[1:]
                dh = self.dcond(head, env, types)
                dr = chain(rest)
                p = self.prop(head, env, types)
                if op == "or":
                    p = f"¬{p}"
                return self._conj([dh, guard(p, dr)])
            return chain(list(e["args"]))
        if op == "implies":
            p, q = e["args"]
            return self._conj([
                self.dcond(p, env, types),
                guard(self.prop(p, env, types),
                      self.dcond(q, env, types))])
        # strict ops: not, neg, len, arithmetic, comparisons, == / !=
        return self._conj([self.dcond(a, env, types)
                           for a in e.get("args", [])])

    # ---------- statements ----------

    def sym(self, stmts: list, env: dict, types: dict,
            keys: list[str], returned: str = "False") -> tuple[dict, list, str]:
        """Forward symbolic execution of a loop-free statement list.
        Returns (updated env over `keys`, definedness obligations each
        already guarded by its path condition, `returned`).

        `returned` (SPEC.md "Early exit", 2026-09-08) is itself a path
        condition: the Lean Prop text (default the literal `False`) that
        holds along exactly the paths that already hit a `return` before
        this point. Every effect below it is guarded by its negation, so
        a value a `return` set is frozen rather than overwritten by a
        later statement on the same path, and every obligation past it
        is only owed when that path in fact keeps running -- matching
        interp.py's exec_body, where a `return` ends the whole enclosing
        block. When the body never returns, `returned` stays the literal
        "False" throughout and every guard below is a no-op, so this is
        byte-identical to the pre-return lowering for every task without
        one."""
        obs: list = []
        env = dict(env)

        def guard(v):
            if v is None:
                return None
            return v if returned == "False" else f"(¬{returned} → {v})"

        for s in stmts:
            if "assign" in s:
                x, e = s["assign"]
                obs.append(guard(self.dcond(e, env, types)))
                new = self.term(e, env, types)
                env[x] = new if returned == "False" else (
                    f"(if {returned} then {env.get(x, x)} else {new})")
            elif "return" in s:
                x, e = s["return"]
                obs.append(guard(self.dcond(e, env, types)))
                new = self.term(e, env, types)
                env[x] = new if returned == "False" else (
                    f"(if {returned} then {env.get(x, x)} else {new})")
                returned = "True"
            elif "var" in s:
                d = s["var"]
                types[d["name"]] = d["type"]
                obs.append(guard(self.dcond(d["init"], env, types)))
                env[d["name"]] = self.term(d["init"], env, types)
            elif "if" in s:
                c = s["if"]
                obs.append(guard(self.dcond(c["cond"], env, types)))
                cp = self.prop(c["cond"], env, types)
                env_t, obs_t, ret_t = self.sym(c["then"], env, types, keys,
                                               returned)
                env_e, obs_e, ret_e = self.sym(c["else"], env, types, keys,
                                               returned)
                obs += [f"({cp} → {o})" for o in obs_t if o is not None]
                obs += [f"(¬{cp} → {o})" for o in obs_e if o is not None]
                for k in set(env_t) | set(env_e):
                    t, f = env_t.get(k, k), env_e.get(k, k)
                    env[k] = t if t == f else f"(if {cp} then {t} else {f})"
                if ret_t == ret_e:
                    returned = ret_t
                elif ret_t == "True" and ret_e == "False":
                    returned = cp
                elif ret_t == "False" and ret_e == "True":
                    returned = f"(¬{cp})"
                else:
                    returned = f"(({cp} → {ret_t}) ∧ (¬{cp} → {ret_e}))"
            elif "while" in s:
                raise NotImplementedError(
                    "nested / multiple loops are not lowered for lean")
            else:
                raise NotImplementedError(f"statement {list(s)} unknown")
        return env, [o for o in obs if o is not None], returned

    def _always_returns(self, stmts: list) -> bool:
        """True when every path through `stmts` ends in `return` (SPEC.md
        "Early exit", 2026-09-08: "A path may end in return instead of an
        assignment"). Used to tell, for an `if` with statements after it,
        which branch's tail is unreachable and which continues into the
        rest of the block."""
        if not stmts:
            return False
        s = stmts[-1]
        if "return" in s:
            return True
        if "if" in s:
            c = s["if"]
            return (self._always_returns(c["then"])
                    and self._always_returns(c["else"]))
        return False

    def to_expr(self, stmts: list, env: dict, types: dict) -> tuple[str, list]:
        """Loop-free body -> one expression computing the return value,
        with dependent ifs (branch hypotheses feed the requires/termination
        side proofs of self-calls). Returns (expr, definedness obligations).

        A `return` (SPEC.md "Early exit", 2026-09-08) outside any loop is
        just another way for a path to reach its final value: as the last
        statement of a branch it is the base case below (parallel to a
        tail `assign` to the return name); as the *other* branch of a
        non-tail `if`, that branch's value is the task's result on that
        path and the statements after the `if` are on the surviving
        branch only (handled by the two one-sided cases below)."""
        if not stmts:
            raise NotImplementedError(
                "a path that assigns nothing is not lowered for lean")
        s, rest = stmts[0], stmts[1:]
        if "if" in s:
            c = s["if"]
            ob0 = self.dcond(c["cond"], env, types)
            cp = self.prop(c["cond"], env, types)
            if not rest:
                te, obs_t = self.to_expr(c["then"], env, types)
                fe, obs_e = self.to_expr(c["else"], env, types)
                obs = ([ob0] if ob0 else []) \
                    + [f"({cp} → {o})" for o in obs_t] \
                    + [f"(¬{cp} → {o})" for o in obs_e]
                return (
                    f"(if {self.fresh_hyp()} : {cp} then {te} else {fe})",
                    obs)
            then_ret = self._always_returns(c["then"])
            else_ret = self._always_returns(c["else"])
            if then_ret and not else_ret:
                te, obs_t = self.to_expr(c["then"], env, types)
                fe, obs_e = self.to_expr(list(c["else"]) + rest, env, types)
            elif else_ret and not then_ret:
                te, obs_t = self.to_expr(list(c["then"]) + rest, env, types)
                fe, obs_e = self.to_expr(c["else"], env, types)
            else:
                raise NotImplementedError(
                    "statements after a branch are not lowered for lean")
            obs = ([ob0] if ob0 else []) \
                + [f"({cp} → {o})" for o in obs_t] \
                + [f"(¬{cp} → {o})" for o in obs_e]
            return (f"(if {self.fresh_hyp()} : {cp} then {te} else {fe})",
                    obs)
        if "return" in s:
            x, e = s["return"]
            if x != self.ret:
                raise NotImplementedError(
                    f"return assigns {x!r}, not the return")
            ob = self.dcond(e, env, types)
            t = self.term(e, env, types, dep=True)
            return t, ([ob] if ob else [])
        if "assign" in s:
            x, e = s["assign"]
            ob = self.dcond(e, env, types)
            obs = [ob] if ob else []
            if not rest:
                if x != self.ret:
                    raise NotImplementedError(
                        f"body path ends assigning {x!r}, not the return")
                return self.term(e, env, types, dep=True), obs
            # Substitute (not `let`-bind): a later statement's own
            # definedness obligation may need x's VALUE (e.g. `at`/`update`
            # needing len(x)), and obligations are combined into the wf
            # theorem's statement flat, outside any `let` this expression
            # nests -- a bare `let x := t; rest` would leave that later
            # obligation's occurrence of `x` referring to nothing once
            # flattened out of the let's scope. Substituting the term text
            # directly keeps every obligation self-contained, exactly as
            # sym() already does for loop bodies. (Dead path for the 15
            # pre-existing tasks: none reassigns a name and then needs its
            # value in a later obligation, so this changes no committed
            # output; first exercised by SPEC.md "Sequences as values",
            # 2026-09-09, e.g. swap's second `r := r[j := tmp]`.)
            t = self.term(e, env, types, dep=True)
            env2 = dict(env)
            env2[x] = t
            re_, obs_r = self.to_expr(rest, env2, types)
            return re_, obs + obs_r
        if "var" in s:
            d = s["var"]
            types[d["name"]] = d["type"]
            ob = self.dcond(d["init"], env, types)
            t = self.term(d["init"], env, types, dep=True)
            env2 = dict(env)
            env2[d["name"]] = t
            re_, obs_r = self.to_expr(rest, env2, types)
            return re_, ([ob] if ob else []) + obs_r
        raise NotImplementedError(
            "statements after a branch are not lowered for lean")

    # ---------- shared pieces ----------

    def lean_type(self, t: str) -> str:
        return {"int": "Int", "bool": "Bool", "seq": "List Int"}[t]

    def binders(self, names_types: list[tuple[str, str]]) -> str:
        return " ".join(f"({n} : {self.lean_type(t)})"
                        for n, t in names_types)

    def _has(self, x, key: str, val=None) -> bool:
        if isinstance(x, dict):
            if key in x and (val is None or x[key] == val):
                if key != "call" or val is None or x["call"]["fun"] == val:
                    return True
            if key == "call" and "call" in x and (
                    val is None or x["call"]["fun"] == val):
                return True
            return any(self._has(v, key, val) for v in x.values())
        if isinstance(x, list):
            return any(self._has(v, key, val) for v in x)
        return False

    def _self_calls(self, x) -> bool:
        if isinstance(x, dict):
            if "call" in x and isinstance(x["call"], dict) \
                    and x["call"].get("fun") == self.name:
                return True
            return any(self._self_calls(v) for v in x.values())
        if isinstance(x, list):
            return any(self._self_calls(v) for v in x)
        return False

    def pre_props(self) -> list[str]:
        return [self.prop(r, {}, self.types)
                for r in self.task.get("requires", [])]

    def pre_conj(self) -> str:
        return " ∧ ".join(self.pre_props())

    def post_conj(self, applied: str) -> str:
        env = {self.ret: applied}
        return "\n    ∧ ".join(self.prop(e, env, self.types)
                               for e in self.task["ensures"])

    # ---------- div/mod closing (SPEC.md "Division and modulo") ----------
    # Measured 2026-09-08 on remainder's own contract: grind's e-matching
    # does not fire on Int.emod_add_ediv_mul against the ring-normalized
    # `a / b * b` subterm it needs to rewrite (nor on the two range lemmas),
    # so a task whose spec states the Euclidean law itself (remainder's
    # ensures does, literally) leaves grind unable to close it even with
    # the lemma named as a hint. The fix is not a better hint: these three
    # core facts about Lean's native (already-Euclidean since measured
    # 4.33.1) `/` and `%` are supplied as ordinary hypotheses instead, and
    # a plain `omega` closes from there, which is pure linear arithmetic
    # once the facts are local terms. Applied only where the theorem's own
    # binder set already covers every free variable of the pair (params,
    # or params + loop state), never task-globally, so a spec_fun's own
    # _wf theorem never sees a stray loop-state variable it never bound.
    def divmod_pairs(self, nodes: list, env: dict, types: dict) -> list:
        """Every distinct (numerator, denominator) term pair reachable
        under a div/mod op in `nodes`, lowered under `env`/`types` exactly
        as the enclosing goal was, so the pair's own text matches what
        appears (or will appear, post-unfold) in that goal."""
        seen: set = set()
        out: list = []

        def walk(x):
            if isinstance(x, dict):
                if x.get("op") in DIV_MOD:
                    a, b = x["args"]
                    pair = (self.term(a, env, types),
                            self.term(b, env, types))
                    if pair not in seen:
                        seen.add(pair)
                        out.append(pair)
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)

        for n in nodes:
            walk(n)
        return out

    def divmod_prelude(self, pairs: list) -> str:
        """`have`-lines putting the Euclidean law and its two range facts
        into context, ground terms Lean already proves natively about its
        own `/` and `%` (Int.emod_add_ediv_mul, Int.emod_nonneg,
        Int.emod_lt, the last sign-agnostic via Int.natAbs, which omega
        normalizes on its own, so no case split on the divisor's sign is
        needed)."""
        lines = []
        for a, b in pairs:
            hne, h1, h2, h3 = (self.fresh_hyp(), self.fresh_hyp(),
                              self.fresh_hyp(), self.fresh_hyp())
            lines.append(f"have {hne} : {b} ≠ (0 : Int) := (by "
                        f"first | assumption | decide | omega | "
                        f"grind{self.ga})")
            lines.append(f"have {h1} := Int.emod_add_ediv_mul {a} {b}")
            lines.append(f"have {h2} := Int.emod_nonneg {a} {hne}")
            lines.append(f"have {h3} := Int.emod_lt {a} {hne}")
        return "; ".join(lines)

    def _close(self, nodes: list, env: dict, types: dict, base: str) -> str:
        """`base` tried first; a div/mod-priming + omega fallback added
        only when `nodes` actually contains a div/mod application, and the
        seq-update/fill fallback (see `_seq_hints`/`_gr` below) added
        whenever the task touches `update`/`fill` at all. A no-op (returns
        `base` unchanged) for every task that touches neither, so the
        fifteen pre-existing tasks see byte-identical tactic scripts."""
        pairs = self.divmod_pairs(nodes, env, types)
        branches = []
        if pairs:
            branches.append(f"({self.divmod_prelude(pairs)}; omega)")
        if self.seq_mut:
            branches.append(f"(grind only [{self._seq_hints()}])")
        if not branches:
            return base
        return "first | (" + base + ") | " + " | ".join(branches)

    # ---------- seq (update/fill) helper lemmas ----------
    # SPEC.md "Sequences as values" (2026-09-09): measured on lean 4.33.1,
    # core only. `List.length_set` and `List.length_replicate` are already
    # in grind's own default simp set (plain `grind` proves both alone),
    # but a READ after an update or a fill, once the index is an Int cast
    # through `.toNat` (this file's `at` convention), is not: grind finds
    # `List.getElem?_set`/`getElem!_pos`/`getElem!_neg` as candidates
    # (visible in its own diagnostics) but the search to actually fire
    # them past the `.toNat` cast layer hits Lean's recursion-depth cap
    # before it decides the index equality, measured on reverse's own
    # loop-preservation obligation. Two lemmas, proved by hand once
    # (`getElem!_pos` totalizes both sides to plain `getElem`, then
    # `List.getElem_set` / `List.getElem_replicate` plus `omega` on the
    # Nat/Int cast, exactly the reasoning grind was attempting), close it
    # when handed to `grind only`: `only` matters as much as the lemmas --
    # it stops grind from ALSO pulling in the same default simp set whose
    # search was the actual source of the depth blowup (plain `grind
    # [t_seq_update_get]` still hit the cap; `grind only [t_seq_update_get,
    # ...]` does not). Emitted only when `self.seq_mut`, so the
    # pre-existing tasks never see them.
    def _seq_hints(self) -> str:
        return ", ".join(
            ["t_seq_update_get", "t_seq_fill_get",
             "List.length_set", "List.length_replicate"]
            + [f"{f}_s" for f in self.sfuns])

    def _gr(self) -> str:
        """`grind{self.ga}`, the plain call used everywhere in this file;
        with the seq fallback appended (parenthesized, so it drops into
        any `first | ... | ...` or `<;>` call site unchanged) whenever
        `self.seq_mut`. Identical text to before otherwise."""
        base = f"grind{self.ga}"
        if not self.seq_mut:
            return base
        return f"(first | {base} | grind only [{self._seq_hints()}])"

    def emit_seq_helpers(self) -> str:
        if not self.seq_mut:
            return ""
        return (
            "theorem t_seq_update_get (l : List Int) (i j : Int) (v : Int)\n"
            "    (hi : (0 : Int) ≤ i) (hiu : i < ((l.length : Int)))\n"
            "    (hj : (0 : Int) ≤ j) (hju : j < ((l.length : Int))) :\n"
            "    (l.set (i).toNat v)[(j).toNat]! = "
            "if j = i then v else l[(j).toNat]! := by\n"
            "  have hbl : (j).toNat < (l.set (i).toNat v).length := by\n"
            "    rw [List.length_set]; omega\n"
            "  rw [getElem!_pos (l.set (i).toNat v) (j).toNat hbl, "
            "List.getElem_set]\n"
            "  split\n"
            "  · next hh =>\n"
            "    have heq : j = i := by omega\n"
            "    rw [if_pos heq]\n"
            "  · next hh =>\n"
            "    have hne : ¬ j = i := by omega\n"
            "    rw [if_neg hne]\n"
            "    have hbr : (j).toNat < l.length := by omega\n"
            "    exact (getElem!_pos l (j).toNat hbr).symm\n"
            "\n"
            "theorem t_seq_fill_get (n : Int) (v : Int) (j : Int)\n"
            "    (hn : n ≥ (0 : Int)) (hj : (0 : Int) ≤ j) (hju : j < n) :\n"
            "    (List.replicate (n).toNat v)[(j).toNat]! = v := by\n"
            "  have hb : (j).toNat < (List.replicate (n).toNat v).length"
            " := by\n"
            "    rw [List.length_replicate]; omega\n"
            "  rw [getElem!_pos (List.replicate (n).toNat v) (j).toNat hb,"
            " List.getElem_replicate]\n")

    # ---------- spec_funs ----------

    def emit_sfuns(self) -> tuple[str, list[tuple[str, str]]]:
        out, thms = [], []
        for f in self.task.get("spec_funs", []):
            ptypes = {p["name"]: p["type"] for p in f["params"]}
            pb = self.binders([(p["name"], p["type"]) for p in f["params"]])
            body = self.term(f["body"], {}, dict(ptypes), dep=True)
            rec = self._self_calls_named(f["body"], f["name"])
            out.append(f"def {f['name']}_s {pb} : "
                       f"{self.lean_type(f['result'])} :=\n  {body}")
            if rec:
                dec = self.term(f["decreases"], {}, dict(ptypes))
                out.append(f"termination_by ({dec}).toNat")
                out.append("decreasing_by all_goals (first | omega | grind)")
            out.append("")
            d = self.dcond(f["body"], {}, dict(ptypes))
            if d is not None:
                tname = f"{f['name']}_s_wf"
                tac = self._close([f["body"]], {}, dict(ptypes),
                                  f"grind{self.ga}")
                out.append(f"theorem {tname} {pb} :\n    {d} := by\n"
                           f"  {tac}\n")
                thms.append((tname, "definedness of spec_fun "
                             + f["name"]))
        return "\n".join(out), thms

    @staticmethod
    def _self_calls_named(x, name: str) -> bool:
        if isinstance(x, dict):
            if "call" in x and isinstance(x["call"], dict) \
                    and x["call"].get("fun") == name:
                return True
            return any(Lower._self_calls_named(v, name) for v in x.values())
        if isinstance(x, list):
            return any(Lower._self_calls_named(v, name) for v in x)
        return False

    # ---------- clause-level definedness theorems ----------

    def emit_clause_wfs(self) -> tuple[str, list[tuple[str, str]]]:
        out, thms, k = [], [], 0
        params_nt = [(p["name"], p["type"]) for p in self.task["params"]]
        reqs = self.task.get("requires", [])
        for i, r in enumerate(reqs):
            d = self.dcond(r, {}, self.types)
            if d is None:
                continue
            k += 1
            hyps = "".join(f"{self.prop(x, {}, self.types)} → "
                           for x in reqs[:i])
            tac = self._close([r], {}, self.types, f"grind{self.ga}")
            out.append(f"theorem {self.name}_t_wf{k} "
                       f"{self.binders(params_nt)} :\n    {hyps}{d} := by\n"
                       f"  {tac}\n")
            thms.append((f"{self.name}_t_wf{k}", f"definedness of requires "
                         f"clause {i + 1}"))
        ens = self.task["ensures"]
        eb = params_nt + [(self.ret, self.rett)]
        for i, e in enumerate(ens):
            d = self.dcond(e, {}, self.types)
            if d is None:
                continue
            k += 1
            hyps = "".join(f"{p} → " for p in self.pre_props())
            hyps += "".join(f"{self.prop(x, {}, self.types)} → "
                            for x in ens[:i])
            tac = self._close([e], {}, self.types, f"grind{self.ga}")
            out.append(f"theorem {self.name}_t_wf{k} "
                       f"{self.binders(eb)} :\n    {hyps}{d} := by\n"
                       f"  {tac}\n")
            thms.append((f"{self.name}_t_wf{k}", f"definedness of ensures "
                         f"clause {i + 1}"))
        return "\n".join(out), thms, k

    # ---------- the three shapes ----------

    def lower(self) -> str:
        header = (f"-- t task {self.name!r} -> lean4, generated by "
                  f"lower_lean.py; every verdict is the kernel's.\n")
        seq_src = self.emit_seq_helpers()
        seq_thms = ([("t_seq_update_get", "seq update-read bridge"),
                     ("t_seq_fill_get", "seq fill-read bridge")]
                    if self.seq_mut else [])
        sf_src, sf_thms = self.emit_sfuns()
        wf_src, wf_thms, wf_k = self.emit_clause_wfs()
        body = self.body
        n_while = sum(1 for s in body if "while" in s)
        deep_while = self._has([s for s in body if "while" not in s],
                               "while")
        if n_while > 1 or deep_while:
            raise NotImplementedError(
                "only a single top-level loop is lowered for lean")
        if n_while == 1:
            if self._self_calls(body):
                raise NotImplementedError(
                    "a loop combined with self-recursion is not lowered "
                    "for lean")
            main = self.lower_loop(wf_k)
        elif self._self_calls(body):
            main = self.lower_rec()
        else:
            main = self.lower_simple()
        src, thms = main
        prints = "\n".join(
            f"#print axioms {t}" for t, _ in
            seq_thms + sf_thms + wf_thms + thms)
        parts = [header]
        if seq_src.strip():
            parts.append(seq_src)
        if sf_src.strip():
            parts.append(sf_src)
        if wf_src.strip():
            parts.append(wf_src)
        parts.append(src)
        parts.append(prints + "\n")
        return "\n".join(parts)

    # SIMPLE: v0 straight-line + if bodies, and de-recursed twins.
    def lower_simple(self) -> tuple[str, list]:
        expr, obs = self.to_expr(self.body, {}, dict(self.types))
        params_nt = [(p["name"], p["type"]) for p in self.task["params"]]
        pb = self.binders(params_nt)
        pnames = " ".join(n for n, _ in params_nt)
        out = [f"def {self.name}_t {pb} : {self.lean_type(self.rett)} :=\n"
               f"  {expr}\n"]
        thms = []
        ob = self._conj(obs)
        if ob is not None:
            hyps = "".join(f"{p} → " for p in self.pre_props())
            tac = self._close([self.body], {}, self.types,
                              f"grind{self.ga}")
            out.append(f"theorem {self.name}_t_wfbody {pb} :\n"
                       f"    {hyps}{ob} := by\n  {tac}\n")
            thms.append((f"{self.name}_t_wfbody", "body definedness"))
        applied = f"({self.name}_t {pnames})"
        hpre = (f" (hpre : {self.pre_conj()})"
                if self.task.get("requires") else "")
        spec_tac = self._close([self.task["ensures"], self.body], {},
                               self.types, f"grind{self.ga}")
        out.append(
            f"theorem {self.name}_t_spec {pb}{hpre} :\n"
            f"    {self.post_conj(applied)} := by\n"
            f"  first\n"
            f"  | (unfold {self.name}_t\n"
            f"     {spec_tac})\n"
            f"  | grind [{self.name}_t"
            + (", " + ", ".join(f"{f}_s" for f in self.sfuns)
               if self.sfuns else "") + "]\n")
        thms.append((f"{self.name}_t_spec", "the contract"))
        return "\n".join(out), thms

    # RECURSIVE: body self-calls; requires becomes a hypothesis argument.
    def lower_rec(self) -> tuple[str, list]:
        if "decreases" not in self.task:
            raise NotImplementedError(
                "self-recursive body without a task decreases measure")
        expr, obs = self.to_expr(self.body, {}, dict(self.types))
        params_nt = [(p["name"], p["type"]) for p in self.task["params"]]
        pb = self.binders(params_nt)
        pnames = " ".join(n for n, _ in params_nt)
        has_pre = bool(self.task.get("requires"))
        hpre_def = f" (hpre : {self.pre_conj()})" if has_pre else ""
        dec = self.term(self.task["decreases"], {}, dict(self.types))
        out = [f"def {self.name}_t {pb}{hpre_def} : "
               f"{self.lean_type(self.rett)} :=\n  {expr}\n"
               f"termination_by ({dec}).toNat\n"
               f"decreasing_by all_goals (first | omega | grind)\n"]
        thms = []
        ob = self._conj(obs)
        if ob is not None:
            hyps = "".join(f"{p} → " for p in self.pre_props())
            out.append(f"theorem {self.name}_t_wfbody {pb} :\n"
                       f"    {hyps}{ob} := by\n  grind{self.ga}\n")
            thms.append((f"{self.name}_t_wfbody", "body definedness"))
        applied = (f"({self.name}_t {pnames} hpre)" if has_pre
                   else f"({self.name}_t {pnames})")
        hpre_thm = f" (hpre : {self.pre_conj()})" if has_pre else ""
        # the induction hypothesis, stated as a measure-guarded `have`: the
        # modular contract of every smaller call. (fun_induction is not used:
        # measured on gcd, grind cannot bridge the dependent proof argument
        # across arithmetic normalization; `simp only [self]` is not usable
        # inside a WF-recursive proof: the self-reference is a raw fixpoint
        # hypothesis. The guard is t's own decreases obligation: >= 0 and
        # strictly smaller.)
        primed = {p["name"]: self.fresh(p["name"])
                  for p in self.task["params"]}
        penv = dict(primed)
        pparams = " ".join(
            f"({primed[p['name']]} : {self.lean_type(p['type'])})"
            for p in self.task["params"])
        dec_p = self.term(self.task["decreases"], penv, dict(self.types))
        pre_p = " ∧ ".join(self.prop(r, penv, self.types)
                           for r in self.task.get("requires", []))
        hp = self.fresh("hpre") if has_pre else ""
        applied_p = (f"({self.name}_t {' '.join(primed.values())} {hp})"
                     if has_pre else
                     f"({self.name}_t {' '.join(primed.values())})")
        penv_post = {**penv, self.ret: applied_p}
        post_p = " ∧ ".join(self.prop(e, penv_post, self.types)
                            for e in self.task["ensures"])
        hyp_p = f" ({hp} : {pre_p})" if has_pre else ""
        fun_args = " ".join(primed.values()) + (f" {hp}" if has_pre else "")
        out.append(
            f"theorem {self.name}_t_spec {pb}{hpre_thm} :\n"
            f"    {self.post_conj(applied)} := by\n"
            f"  have _ih : ∀ {pparams}{hyp_p},\n"
            f"      (((0 : Int) ≤ ({dec_p})) ∧ (({dec_p}) < ({dec}))) →\n"
            f"      {post_p} :=\n"
            f"    fun {fun_args} _hm => {self.name}_t_spec {fun_args}\n"
            f"  rw [{self.name}_t.eq_def]\n"
            f"  repeat split\n"
            f"  all_goals grind{self.ga}\n"
            f"termination_by ({dec}).toNat\n"
            f"decreasing_by all_goals (first | omega | grind)\n")
        thms.append((f"{self.name}_t_spec", "the contract"))
        return "\n".join(out), thms

    # LOOP: one top-level while; invariants become the hypotheses of a
    # recursive helper theorem (the induction hypothesis, literally).
    def lower_loop(self, wf_k: int) -> tuple[str, list]:
        body = self.body
        idx = next(i for i, s in enumerate(body) if "while" in s)
        prefix, w, suffix = body[:idx], body[idx]["while"], body[idx + 1:]
        types = dict(self.types)
        params_nt = [(p["name"], p["type"]) for p in self.task["params"]]
        pnames = " ".join(n for n, _ in params_nt)

        # state = return var + every local declared before the loop
        state = [self.ret] + [s["var"]["name"] for s in prefix if "var" in s]
        env0, obs_pre, _ = self.sym(prefix, {}, types, state)
        for v in state:
            if v not in env0:
                # SPEC.md "Early exit" (2026-09-08): the return name need
                # not be set before the loop when the only writes to it
                # are a `return` inside the loop (or the suffix after it);
                # a placeholder zero-value seeds the recursion and is
                # provably overwritten on every path before it is read
                # (loop_assigned already excludes it from the frame set
                # in that case, so nothing depends on this placeholder).
                zero = {"int": "(0 : Int)", "bool": "false"}.get(
                    self.rett) if v == self.ret else None
                if zero is None:
                    raise NotImplementedError(
                        f"state var {v!r} uninitialized before the loop")
                env0[v] = zero
        state_nt = [(v, types[v]) for v in state]
        sb = self.binders(state_nt)
        snames = " ".join(state)
        pb = self.binders(params_nt)

        invs = w.get("invariants", [])
        guard_p = self.prop(w["cond"], {}, types)
        guard_d = self.dcond(w["cond"], {}, types)
        env_b, obs_body, ret_cond = self.sym(w["body"], {}, dict(types),
                                             state)
        has_return = ret_cond != "False"
        rec_args = " ".join(env_b.get(v, v) for v in state)
        dec = self.term(w["decreases"], {}, types)
        dec_d = self.dcond(w["decreases"], {}, types)
        if suffix:
            env_s, obs_suf, _ = self.sym(suffix, {}, dict(types), state)
            result = env_s.get(self.ret, self.ret)
        else:
            obs_suf, result = [], self.ret

        # a `return` inside the loop body (SPEC.md "Early exit",
        # 2026-09-08) makes the guard-true step a dependent if on
        # `ret_cond`, the SAME idiom already used for the guard `_hg` and
        # for every dependent branch in `to_expr`/`term`: no new outcome
        # type, so the invariant's own shape is untouched and only the
        # guard-true step of `_t_loop_spec` gains a second case. A body
        # with no `return` reaches `ret_cond == "False"` and this is
        # byte-identical to the pre-return lowering.
        if has_return:
            retval = env_b.get(self.ret, self.ret)
            out = [f"def {self.name}_t_loop {pb} {sb} : "
                   f"{self.lean_type(self.rett)} :=\n"
                   f"  if _hg : {guard_p} then\n"
                   f"    (if _hr : {ret_cond} then {retval}\n"
                   f"     else {self.name}_t_loop {pnames} {rec_args})\n"
                   f"  else {result}\n"
                   f"termination_by ({dec}).toNat\n"
                   f"decreasing_by all_goals (first | omega | grind)\n"]
        else:
            out = [f"def {self.name}_t_loop {pb} {sb} : "
                   f"{self.lean_type(self.rett)} :=\n"
                   f"  if _hg : {guard_p} then\n"
                   f"    {self.name}_t_loop {pnames} {rec_args}\n"
                   f"  else {result}\n"
                   f"termination_by ({dec}).toNat\n"
                   f"decreasing_by all_goals (first | omega | grind)\n"]
        init_args = " ".join(env0[v] for v in state)
        out.append(f"def {self.name}_t {pb} : "
                   f"{self.lean_type(self.rett)} :=\n"
                   f"  {self.name}_t_loop {pnames} {init_args}\n")
        thms = []

        # program-point definedness: (context) -> obligations
        pre_hyps = self.pre_props()
        inv_props = [self.prop(iv, {}, types) for iv in invs]
        wfs = []
        for i, iv in enumerate(invs):
            d = self.dcond(iv, {}, types)
            if d is not None:
                wfs.append((pre_hyps + inv_props[:i], d,
                            f"definedness of invariant {i + 1}"))
        if guard_d is not None:
            wfs.append((pre_hyps + inv_props, guard_d,
                        "definedness of the loop guard"))
        if dec_d is not None:
            wfs.append((pre_hyps + inv_props + [guard_p], dec_d,
                        "definedness of the loop decreases"))
        ob = self._conj(obs_body)
        if ob is not None:
            wfs.append((pre_hyps + inv_props + [guard_p], ob,
                        "definedness of the loop body"))
        ob = self._conj(obs_pre)
        if ob is not None:
            wfs.append((pre_hyps, ob, "definedness before the loop"))
        ob = self._conj(obs_suf)
        if ob is not None:
            wfs.append((pre_hyps + inv_props + [f"(¬{guard_p})"], ob,
                        "definedness after the loop"))
        for hyps, obg, why in wfs:
            wf_k += 1
            binders = pb + (" " + sb if "before the loop" not in why
                            else "")
            chain = "".join(f"{h} → " for h in hyps)
            out.append(f"theorem {self.name}_t_wf{wf_k} {binders} :\n"
                       f"    {chain}{obg} := by\n  {self._gr()}\n")
            thms.append((f"{self.name}_t_wf{wf_k}", why))

        # the helper lemma: invariants in, ensures-of-loop-value out.
        # SPEC.md frame rule: the loop havocs exactly the syntactic assigned
        # set of its body, so every other state var carries a frame
        # hypothesis pinning it to its entry value. The recursive call
        # passes an unassigned var through unchanged, so the hypothesis is
        # self-maintaining; without it the lemma quantified over havocked
        # values, and fr_probe_ret / fr_probe_local were unprovable here
        # while Dafny, Verus and Frama-C proved them (measured 2026-09-02).
        frame = [v for v in state if v not in loop_assigned(w["body"])]
        has_pre = bool(pre_hyps)
        hpre = f"\n    (hpre : {self.pre_conj()})" if has_pre else ""
        hinvs = "".join(f"\n    (hinv{i + 1} : {p})"
                        for i, p in enumerate(inv_props))
        hfrs = "".join(f"\n    (hfr{k + 1} : {v} = {env0[v]})"
                       for k, v in enumerate(frame))
        applied_loop = f"({self.name}_t_loop {pnames} {snames})"
        # guard-true step: with a `return` (SPEC.md "Early exit",
        # 2026-09-08), `repeat split` also splits the new `_hr` dependent
        # if, giving one goal per outcome -- the continue case still
        # recurses into the invariant (`apply ..._loop_spec <;> grind`),
        # but the return case's goal is `ensures` at the returned value
        # directly (no recursive call to apply), so it is owed straight
        # from the invariants, the guard and `_hr` by `grind` alone.
        # `first` tries the recursive shape and falls back to plain grind,
        # so this also covers any already-resolved merge-if goal exactly
        # as the no-return lowering did. A body with no `return` keeps
        # the original single-tactic line, byte-identical.
        then_tac = (
            f"all_goals (first | (apply {self.name}_t_loop_spec <;> "
            f"{self._gr()}) | {self._gr()})"
            if has_return else
            f"all_goals (apply {self.name}_t_loop_spec <;> {self._gr()})")
        out.append(
            f"theorem {self.name}_t_loop_spec {pb} {sb}{hpre}{hinvs}"
            f"{hfrs} :\n"
            f"    {self.post_conj(applied_loop)} := by\n"
            f"  rw [{self.name}_t_loop.eq_def]\n"
            f"  split\n"
            f"  · repeat split\n"
            f"    {then_tac}\n"
            f"  · {self._gr()}\n"
            f"termination_by ({dec}).toNat\n"
            f"decreasing_by all_goals (first | omega | grind)\n")
        thms.append((f"{self.name}_t_loop_spec",
                     "invariants -> ensures, by induction on the loop"))

        # the contract: initial state satisfies the invariants
        init_pfs = []
        if has_pre:
            init_pfs.append("hpre")
        for iv in invs:
            if "exists" in iv:
                lo0 = self.term(iv["exists"]["lo"], env0, types)
                init_pfs.append(f"(by first | {self._gr()} | "
                                f"exact ⟨{lo0}, by {self._gr()}⟩)")
            else:
                init_pfs.append(f"(by {self._gr()})")
        for _v in frame:
            init_pfs.append("rfl")   # hfr at the entry state: v0 = v0
        hpre_thm = f" (hpre : {self.pre_conj()})" if has_pre else ""
        applied = f"({self.name}_t {pnames})"
        out.append(
            f"theorem {self.name}_t_spec {pb}{hpre_thm} :\n"
            f"    {self.post_conj(applied)} := by\n"
            f"  first\n"
            f"  | (unfold {self.name}_t\n"
            f"     exact {self.name}_t_loop_spec {pnames} {init_args}\n"
            f"       " + " ".join(init_pfs) + ")\n"
            f"  | grind [{self.name}_t, {self.name}_t_loop"
            + (", " + ", ".join(f"{f}_s" for f in self.sfuns)
               if self.sfuns else "") + "]\n")
        thms.append((f"{self.name}_t_spec", "the contract"))
        return "\n".join(out), thms

    # ---------- the refutation certificate (twin lowering only) ----------
    # Ground proof generation: _prove(e) returns a one-line tactic proving
    # prop(e) at the witness, _refute(e) one proving its negation. Interp
    # evaluation picks the branch (which disjunct is true, which conjunct
    # fails, which index breaks a forall); the kernel then re-proves the
    # pick, so evaluation can lose a certificate but never fake one. Any
    # shape neither handles falls to _closer(), a cascade of kernel-checked
    # ground tactics; if that also misses, the kernel rejects the file and
    # the adapter mints UNPROVED, the honest price.

    def _closer(self) -> str:
        fl = self.cert_fns
        return (f"(first | decide | omega | simp [{fl}] | "
                f"(simp [{fl}]; omega) | grind [{fl}])")

    def _cev(self, e: dict, venv: dict):
        """Ground-evaluate a spec expression at the witness; None when the
        interpreter cannot decide it (the closers then get their chance)."""
        try:
            return interp.ev(e, venv, self.cert_funs, interp.St())
        except (interp.Undef, interp.Budget, RecursionError):
            return None

    def _bounds_close(self, h1: str, h2: str) -> str:
        """Close a goal from quantifier-range hypotheses: omega for literal
        bounds; a simp pass first when a bound is a List.length cast; simp
        alone when simp already closes the goal from a False hypothesis."""
        return (f"first | omega | (simp at {h1} {h2}; omega) | "
                f"(simp at {h1} {h2})")

    def _enum(self, b: str, lo: int, hi: int, h1: str, h2: str,
              alts: list[str]) -> str:
        """Case-split an Int bound over the ground range [lo, hi) and close
        every branch: each alternative is tried on each branch, and a wrong
        pairing fails harmlessly inside `first`."""
        hv = self.fresh_hyp()
        disj = " ∨ ".join(f"{b} = ({k} : Int)" for k in range(lo, hi))
        pats = " | ".join([hv] * (hi - lo))
        uniq = list(dict.fromkeys(alts))
        return (f"have {hv} : {disj} := by {self._bounds_close(h1, h2)}; "
                f"rcases {hv} with {pats} <;> subst {hv} <;> "
                "first | " + " | ".join(uniq))

    def _prove(self, e: dict, tenv: dict, venv: dict, types: dict) -> str:
        g = self._closer()
        if "forall" in e:
            q = e["forall"]
            lo, hi = self._cev(q["lo"], venv), self._cev(q["hi"], venv)
            if lo is None or hi is None or hi - lo > MAX_ENUM:
                return g
            b = self.fresh(q["var"])
            h1, h2 = self.fresh_hyp(), self.fresh_hyp()
            if hi <= lo:
                return (f"(intro {b} {h1} {h2}; "
                        f"{self._bounds_close(h1, h2)})")
            alts = []
            for k in range(lo, hi):
                t2 = {**tenv, q["var"]: self._gterm(k, "int")}
                v2 = {**venv, q["var"]: k}
                alts.append(self._prove(q["body"], t2, v2,
                                        {**types, q["var"]: "int"}))
            return (f"(intro {b} {h1} {h2}; "
                    + self._enum(b, lo, hi, h1, h2, alts) + ")")
        if "exists" in e:
            q = e["exists"]
            lo, hi = self._cev(q["lo"], venv), self._cev(q["hi"], venv)
            if lo is None or hi is None:
                return g
            for k in range(lo, hi):
                v2 = {**venv, q["var"]: k}
                if self._cev(q["body"], v2) is True:
                    t2 = {**tenv, q["var"]: self._gterm(k, "int")}
                    pb = self._prove(q["body"], t2, v2,
                                     {**types, q["var"]: "int"})
                    return (f"(exact ⟨({k} : Int), (by {g}), (by {g}), "
                            f"(by {pb})⟩)")
            return g
        if "ite" in e:
            c = e["ite"]
            vc = self._cev(c["cond"], venv)
            h = self.fresh_hyp()
            if vc is True:
                pt = self._prove(c["then"], tenv, venv, types)
                pc = self._prove(c["cond"], tenv, venv, types)
                return (f"(exact ⟨fun _ => (by {pt}), "
                        f"fun {h} => absurd (by {pc}) {h}⟩)")
            if vc is False:
                rc = self._refute(c["cond"], tenv, venv, types)
                pf = self._prove(c["else"], tenv, venv, types)
                return (f"(exact ⟨fun {h} => absurd {h} (by {rc}), "
                        f"fun _ => (by {pf})⟩)")
            return g
        op = e.get("op")
        if op == "and":
            parts = [self._prove(a, tenv, venv, types) for a in e["args"]]
            return ("(exact ⟨" + ", ".join(f"(by {p})" for p in parts)
                    + "⟩)")
        if op == "or":
            args = e["args"]
            for i, a in enumerate(args):
                if self._cev(a, venv) is True:
                    term = f"(by {self._prove(a, tenv, venv, types)})"
                    if i < len(args) - 1:
                        term = f"(Or.inl {term})"
                    for _ in range(i):
                        term = f"(Or.inr {term})"
                    return f"(exact {term})"
            return g
        if op == "implies":
            aa, bb = e["args"]
            h = self.fresh_hyp()
            if self._cev(aa, venv) is False:
                ra = self._refute(aa, tenv, venv, types)
                return f"(intro {h}; exact absurd {h} (by {ra}))"
            if self._cev(bb, venv) is True:
                return (f"(intro {h}; "
                        f"{self._prove(bb, tenv, venv, types)})")
            return g
        if op == "not":
            return self._refute(e["args"][0], tenv, venv, types)
        if op == "==" and self.sort(e["args"][0], types) == "bool":
            a, b = e["args"]
            va, vb = self._cev(a, venv), self._cev(b, venv)
            h = self.fresh_hyp()
            if va is True and vb is True:
                pa = self._prove(a, tenv, venv, types)
                pb = self._prove(b, tenv, venv, types)
                return (f"(exact ⟨fun _ => (by {pb}), "
                        f"fun _ => (by {pa})⟩)")
            if va is False and vb is False:
                ra = self._refute(a, tenv, venv, types)
                rb = self._refute(b, tenv, venv, types)
                return (f"(exact ⟨fun {h} => absurd {h} (by {ra}), "
                        f"fun {h} => absurd {h} (by {rb})⟩)")
            return g
        if op == "!=" and self.sort(e["args"][0], types) == "bool":
            iff = {"op": "==", "args": e["args"]}
            return self._refute(iff, tenv, venv, types)
        return g

    def _refute(self, e: dict, tenv: dict, venv: dict, types: dict) -> str:
        g = self._closer()
        if "forall" in e:
            q = e["forall"]
            lo, hi = self._cev(q["lo"], venv), self._cev(q["hi"], venv)
            if lo is None or hi is None:
                return g
            for k in range(lo, hi):
                v2 = {**venv, q["var"]: k}
                if self._cev(q["body"], v2) is False:
                    t2 = {**tenv, q["var"]: self._gterm(k, "int")}
                    rb = self._refute(q["body"], t2, v2,
                                      {**types, q["var"]: "int"})
                    h = self.fresh_hyp()
                    return (f"(intro {h}; exact absurd ({h} ({k} : Int) "
                            f"(by {g}) (by {g})) (by {rb}))")
            return g
        if "exists" in e:
            q = e["exists"]
            lo, hi = self._cev(q["lo"], venv), self._cev(q["hi"], venv)
            if lo is None or hi is None:
                return g
            b = self.fresh(q["var"])
            h = self.fresh_hyp()
            h1, h2, h3 = (self.fresh_hyp(), self.fresh_hyp(),
                          self.fresh_hyp())
            intro = (f"intro {h}; obtain ⟨{b}, {h1}, {h2}, {h3}⟩ := {h}; ")
            if hi <= lo:
                return f"({intro}{self._bounds_close(h1, h2)})"
            if hi - lo > MAX_ENUM:
                return g
            alts = []
            for k in range(lo, hi):
                v2 = {**venv, q["var"]: k}
                if self._cev(q["body"], v2) is not False:
                    return g
                t2 = {**tenv, q["var"]: self._gterm(k, "int")}
                rb = self._refute(q["body"], t2, v2,
                                  {**types, q["var"]: "int"})
                alts.append(f"(exact absurd {h3} (by {rb}))")
            return f"({intro}" + self._enum(b, lo, hi, h1, h2, alts) + ")"
        if "ite" in e:
            c = e["ite"]
            vc = self._cev(c["cond"], venv)
            h = self.fresh_hyp()
            if vc is True:
                pc = self._prove(c["cond"], tenv, venv, types)
                rt = self._refute(c["then"], tenv, venv, types)
                return (f"(intro {h}; exact absurd ({h}.1 (by {pc})) "
                        f"(by {rt}))")
            if vc is False:
                rc = self._refute(c["cond"], tenv, venv, types)
                rf = self._refute(c["else"], tenv, venv, types)
                return (f"(intro {h}; exact absurd ({h}.2 (by {rc})) "
                        f"(by {rf}))")
            return g
        op = e.get("op")
        if op == "and":
            args = e["args"]
            h = self.fresh_hyp()
            for j, a in enumerate(args):
                if self._cev(a, venv) is False:
                    proj = ".2" * j + (".1" if j < len(args) - 1 else "")
                    r = self._refute(a, tenv, venv, types)
                    return (f"(intro {h}; exact absurd {h}{proj} "
                            f"(by {r}))")
            return g
        if op == "or":
            args = e["args"]
            h = self.fresh_hyp()
            alts = []
            for a in args:
                if self._cev(a, venv) is not False:
                    return g
                alts.append(f"(exact absurd {h} (by "
                            + self._refute(a, tenv, venv, types) + "))")
            pats = " | ".join([h] * len(args))
            uniq = list(dict.fromkeys(alts))
            return (f"(intro {h}; rcases {h} with {pats} <;> "
                    "first | " + " | ".join(uniq) + ")")
        if op == "implies":
            aa, bb = e["args"]
            if self._cev(aa, venv) is True \
                    and self._cev(bb, venv) is False:
                pa = self._prove(aa, tenv, venv, types)
                rb = self._refute(bb, tenv, venv, types)
                h = self.fresh_hyp()
                return (f"(intro {h}; exact absurd ({h} (by {pa})) "
                        f"(by {rb}))")
            return g
        if op == "not":
            h = self.fresh_hyp()
            pa = self._prove(e["args"][0], tenv, venv, types)
            return f"(intro {h}; exact {h} (by {pa}))"
        if op == "==" and self.sort(e["args"][0], types) == "bool":
            a, b = e["args"]
            va, vb = self._cev(a, venv), self._cev(b, venv)
            h = self.fresh_hyp()
            if va is True and vb is False:
                pa = self._prove(a, tenv, venv, types)
                rb = self._refute(b, tenv, venv, types)
                return (f"(intro {h}; exact absurd ({h}.mp (by {pa})) "
                        f"(by {rb}))")
            if va is False and vb is True:
                pb = self._prove(b, tenv, venv, types)
                ra = self._refute(a, tenv, venv, types)
                return (f"(intro {h}; exact absurd ({h}.mpr (by {pb})) "
                        f"(by {ra}))")
            return g
        if op == "!=" and self.sort(e["args"][0], types) == "bool":
            h = self.fresh_hyp()
            iff = {"op": "==", "args": e["args"]}
            pi = self._prove(iff, tenv, venv, types)
            return f"(intro {h}; exact {h} (by {pi}))"
        return g

    def _gterm(self, v, ty: str) -> str:
        if ty == "bool":
            return "true" if v else "false"
        if ty == "seq":
            return "([" + ", ".join(str(int(x)) for x in v) + "] : List Int)"
        n = int(v)
        return f"({n} : Int)" if n >= 0 else f"(({n}) : Int)"

    def _ens_conj(self) -> dict:
        ens = self.task["ensures"]
        return ens[0] if len(ens) == 1 else {"op": "and", "args": ens}

    def certificate(self, w: dict) -> str | None:
        """The t_refutation_certificate block for a twin with witness `w`,
        or None when the witness kind has no ground negation here (then the
        twin cell honestly reads unproved, never refuted)."""
        kind = w.get("_kind")
        if kind == "value":
            build = self._cert_value
        elif kind in ("exit", "preservation"):
            build = self._cert_loop
        elif kind == "undefined":
            build = self._cert_undefined
        else:
            return None
        try:
            parts = build(w, kind)
        except (NotImplementedError, KeyError, StopIteration,
                interp.Undef, interp.Budget, RecursionError):
            return None
        if parts is None:
            return None
        lines = ["-- refutation certificate: the spec instantiated at the",
                 "-- measured witness; REFUTED is minted only if the kernel",
                 "-- accepts this proof (verifiers/lean.py).",
                 f"theorem {CERT_NAME} :",
                 "    " + "\n    ∧ ".join(s for s, _ in parts) + " := by"]
        if len(parts) == 1:
            lines.append(f"  {parts[0][1]}")
        else:
            lines.append("  refine ⟨" + ", ".join(["?_"] * len(parts))
                         + "⟩")
            lines += [f"  · {tac}" for _, tac in parts]
        lines.append(f"\n#print axioms {CERT_NAME}")
        return "\n".join(lines) + "\n"

    # ---------- undefined-kind witnesses (SPEC.md "Sequences as values",
    # 2026-09-09) ----------
    # An undefined-kind witness (interp.py's Undef: t's REAL semantics has
    # no value for the twin at this input) was previously abstained on
    # unconditionally: this lowering's `at`/`update`/`fill` are TOTAL, so
    # naively re-running the twin under totalized semantics and comparing
    # to `ensures` is unsound to rely on -- measured on swap's own
    # off-by-one twin (index 1 outside [0,1) at s=[0]), Lean's chosen
    # default (`getElem!_neg`'s `default = 0`) happens to equal s's own
    # element there, so the totalized twin computes a value that
    # ACCIDENTALLY still satisfies `ensures`, and no certificate exists at
    # that reading even though the same twin is genuinely wrong at other
    # inputs (`swap_t [10,20] 0 0` computes `[20,20]`, not the identity
    # `[10,20]` swapping index 0 with itself should give). The robust
    # certificate is not about a totalized VALUE at all: it is that the
    # twin's OWN definedness obligation -- the same conjunction emitted as
    # `{name}_t_wfbody`, from `to_expr`'s own `obs` -- is violated at the
    # witness. That obligation is exactly SPEC.md's definedness calculus,
    # so it is false at this ground point if and only if interp.py's
    # exec_body would raise Undef there, which is exactly the condition
    # `_kind == "undefined"` already recorded. Re-running `to_expr` with
    # the params bound to the witness's GROUND terms (instead of their
    # names) renders that same obligation already fully instantiated, so
    # its negation is a closed, decidable proposition the kernel checks by
    # `decide` alone: no case analysis, no reliance on which default value
    # a partial operator happens to totalize to. LOOP-shaped bodies are
    # not covered (returns None, the pre-existing abstain): `to_expr` only
    # renders the loop-free shape.
    def _cert_undefined(self, w: dict, _kind: str) -> list | None:
        if any("while" in s for s in self.body):
            return None
        params = self.task["params"]
        types = dict(self.types)
        tenv = {p["name"]: self._gterm(w[p["name"]], p["type"])
                for p in params}
        _, obs = self.to_expr(self.body, dict(tenv), types)
        ob = self._conj(obs)
        if ob is None:
            return None      # nothing was undefined along this ground path
        self.cert_funs = interp.funs_of(self.task, self.body)
        fns = [f"{self.name}_t"] + [f"{f}_s" for f in self.sfuns]
        self.cert_fns = ", ".join(fns)
        venv = {p["name"]: w[p["name"]] for p in params}
        parts = [(self.prop(r, tenv, types),
                  self._prove(r, tenv, venv, types))
                 for r in self.task.get("requires", [])]
        parts.append((f"(¬{ob})", self._closer()))
        return parts

    def _cert_value(self, w: dict, _kind: str) -> list | None:
        if isinstance(w.get("_twin"), str):
            return None      # "no value": nothing ground to instantiate
        self.cert_funs = interp.funs_of(self.task, self.body)
        fns = [f"{self.name}_t"] + [f"{f}_s" for f in self.sfuns]
        if any("while" in s for s in self.body):
            fns.append(f"{self.name}_t_loop")
        self.cert_fns = ", ".join(fns)
        params = self.task["params"]
        types = dict(self.types)
        tenv = {p["name"]: self._gterm(w[p["name"]], p["type"])
                for p in params}
        venv = {p["name"]: w[p["name"]] for p in params}
        args = " ".join(tenv[p["name"]] for p in params)
        if self._self_calls(self.body) and self.task.get("requires"):
            applied = f"({self.name}_t {args} (by {self._closer()}))"
        else:
            applied = f"({self.name}_t {args})"
        parts = [(self.prop(r, tenv, types),
                  self._prove(r, tenv, venv, types))
                 for r in self.task.get("requires", [])]
        post = self._ens_conj()
        tv = w["_twin"]
        tenv_post = {**tenv, self.ret: applied}
        venv_post = {**venv, self.ret: tv}
        parts.append((f"(¬{self.prop(post, tenv_post, types)})",
                      self._refute(post, tenv_post, venv_post, types)))
        return parts

    def _cert_loop(self, w: dict, kind: str) -> list | None:
        body = self.body
        idx = next(i for i, s in enumerate(body) if "while" in s)
        prefix, wh, suffix = body[:idx], body[idx]["while"], body[idx + 1:]
        types = dict(self.types)
        for s in prefix:
            if "var" in s:
                types[s["var"]["name"]] = s["var"]["type"]
        state = [self.ret] + [s["var"]["name"] for s in prefix
                              if "var" in s]
        self.cert_funs = interp.funs_of(self.task, body)
        fns = [f"{self.name}_t", f"{self.name}_t_loop"] \
            + [f"{f}_s" for f in self.sfuns]
        self.cert_fns = ", ".join(fns)
        params = [p["name"] for p in self.task["params"]]
        names = params + state
        if any(n not in w for n in names):
            return None
        tenv = {n: self._gterm(w[n], types[n]) for n in names}
        venv = {n: w[n] for n in names}
        parts = [(self.prop(r, tenv, types),
                  self._prove(r, tenv, venv, types))
                 for r in self.task.get("requires", [])]
        for iv in wh.get("invariants", []):
            parts.append((self.prop(iv, tenv, types),
                          self._prove(iv, tenv, venv, types)))
        guard = wh["cond"]
        if kind == "exit":
            parts.append((f"(¬{self.prop(guard, tenv, types)})",
                          self._refute(guard, tenv, venv, types)))
            applied = (f"({self.name}_t_loop "
                       + " ".join(tenv[n] for n in params + state) + ")")
            venv_post = dict(venv)
            if suffix:
                interp.exec_body(suffix, venv_post, self.cert_funs,
                                 interp.St())
            post = self._ens_conj()
            tenv_post = {**tenv, self.ret: applied}
            parts.append((f"(¬{self.prop(post, tenv_post, types)})",
                          self._refute(post, tenv_post, venv_post,
                                       types)))
        else:                                    # preservation
            parts.append((self.prop(guard, tenv, types),
                          self._prove(guard, tenv, venv, types)))
            types2 = dict(types)
            env_b, _, _ = self.sym(wh["body"], tenv, types2, state)
            step_tenv = {**tenv, **env_b}
            venv_step = dict(venv)
            interp.exec_body(wh["body"], venv_step, self.cert_funs,
                             interp.St())
            kept = wh.get("invariants", [])
            kinv = (kept[0] if len(kept) == 1
                    else {"op": "and", "args": kept})
            parts.append((f"(¬{self.prop(kinv, step_tenv, types2)})",
                          self._refute(kinv, step_tenv, venv_step,
                                       types2)))
        return parts


# `witness` is the twin's measured witness (harness.twin_cached); the real
# lowering never receives one. When present and certificatable it adds the
# t_refutation_certificate theorem, the only door to a lean REFUTED.
def lower(task: dict, body: list, witness: dict | None = None) -> str:
    lw = Lower(task, body)
    src = lw.lower()
    if witness is not None:
        cert = lw.certificate(witness)
        if cert is not None:
            src += "\n" + cert
    return src


if __name__ == "__main__":
    raise SystemExit(harness.run_all(sys.argv[1:], lower, lean_backend,
                                     "lean"))
