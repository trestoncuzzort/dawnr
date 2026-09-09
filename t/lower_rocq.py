#!/usr/bin/env python3
"""lower_rocq.py: lower t tasks (v0 and v1) to the Rocq Prover; the fifth kernel.

v0 (`"t": 0`): function, theorem, and the uniform destruct-then-lia proof.
The shape is the original lowering's; the `if` condition accepts the full Exp
that SYNTAX.md's Stmt row permits, which the first version did not (35 of the
74 generated v0 fuzz tasks raised ValueError instead of lowering), and the
proof adds one boolean-reduction arm for the connectives that admits.

v1 (`"t": 1`) opens the three gates for this backend:

  MODEL. `seq` is lowered to the function+length pair (s : Z -> Z) (s_len : Z)
  with the hypothesis 0 <= s_len added to every statement in which s is in
  scope. Through 2026-09-08 `seq` was opaque and param-position only (just
  `len` and `at`); SPEC.md "Sequences as values (v1)" (2026-09-09) makes it
  a return and local type too and adds `update`/`fill` as expressions (see
  that date's own note, near the PRELUDE's t_upd/t_fill, for what changed).
  `at` is only ever *defined* inside [0, len), and every definedness
  obligation is emitted as its own lemma (Dafny-style well-formedness,
  discharged by the kernel, never silently totalized away; see the
  `<name>_def_k` lemmas below).

  LOOPS. A while loop becomes a structural Fixpoint over nat fuel on the
  tuple of mutable state, plus one lemma proved by induction on fuel: if the
  invariants hold and `decreases < Z.of_nat fuel`, the loop's output satisfies
  the invariants and the negated guard. The fuel account needs no separate
  nonnegativity argument: with fuel 0 the hypothesis says decreases < 0, and
  the guard must then be false or the task's own decreases-nonnegative
  obligation is violated, both discharged by the same engine. The theorem
  runs the loop at fuel S (Z.to_nat decreases0), always sufficient.

  EARLY EXIT (2026-09-08, SPEC.md "Early exit (v1)"). A loop body may
  contain `return`, so the Fixpoint's result is enriched to a pair (state
  tuple, bool): the bool is true exactly when some iteration returned. One
  step of exec_straight already computes the fully-guarded per-iteration
  state (a variable freezes at its old value on the returning branch, via
  the same if-then-else merge `if` uses for its two arms), so the same
  tuple feeds both outcomes of the fixpoint's inner `if returned`; no
  separate "kept going" state is ever computed. The induction lemma's
  conclusion becomes a disjunction: returned owes the task's ensures
  directly (from the invariant, the guard, and whichever branch condition
  set the flag; never the invariant, exactly as SPEC.md says a `return`
  does not owe it), not-returned owes the old invariant/frame conclusion
  unchanged. A loop with no `return` anywhere in its body takes the
  original single-outcome path verbatim (has_return/_DONE is empty), so
  this feature is additive: the other 13 tasks' generated Coq is
  unaffected. Scope: `return` is supported inside a loop's own body and in
  straight-line/if code with no loop at all (gen_plain needs no changes,
  since exec_straight's guarding handles it for free); a `return` in a
  loop's prefix or suffix is not threaded into skipping the loop itself,
  since no committed task needs it yet.

  Fixed 2026-09-09: is_prime read rocq unproved/unproved (every other task's
  rocq cell, first_even included, read as t/AGREEMENT.md's committed
  columns). coqc failed with "Tactic failure: unsolved t verification
  condition" on the return branch of is_prime_loop_spec, whose goal, after
  the guard/branch destructs and the induction step's own intro/subst, was
  `(true = true /\\ (false = true <-> (forall d, 2 <= d < n -> t_mod n d <>
  0))) \\/ ...` under hypotheses including `t_mod n d' = 0`, `2 <= d' < n`,
  and the invariant `forall k, 2 <= k < d' -> t_mod n k <> 0`: the hard
  direction needs False from instantiating the GOAL's own forall at `d'`,
  contradicting `t_mod n d' = 0`. Two things were wrong, both now fixed.
  First, t_go_ext (PRELUDE) tried its forall/Z-variable pairing exactly
  once, on the raw un-navigated goal, where the forall is not yet a
  hypothesis (it sits inside an un-split `<->`, unlike first_even's bare
  `\\/`); it is now a full t_go-shaped recursion (t_leaf_ext/t_go_ext) that
  retries the pairing at every leaf the `\\/`/`<->`/`->` navigation reaches.
  The induction step's OTHER arm, `apply IH; t_side`, had the identical gap
  proving invariant preservation (`forall k, 2 <= k < d + 1 -> t_mod n k <>
  0` from the old invariant plus `t_mod n d <> 0`); `t_side_ext` (POST_SF)
  gives that arm the same extended search. Second, the twin's own
  certificate (`_loop_cert`) had no candidate Z variable to pair a forall
  against at all: `specialize` bakes params and loop state in as Z
  LITERALS, so nothing of shape `y : Z` exists in context. `_forall_hints`
  computes a concrete witness the same way `interp.py` would (a bounded
  scan, not a proof search) and `pose (t_witK := literal)` exposes it as a
  `y : Z` candidate; `remember` was tried first and measured broken, since
  the equation it also introduces gets eaten by t_base's own `subst`
  catch-all before t_leaf_ext's pairing search ever runs. All three changes
  are confined to return-bearing loops (has_return), so a loop with no
  `return` never emits `t_dis_ext`/`t_side_ext`/`pose`d witnesses and its
  own generated proof text is unchanged; digit_sum and seq_max still verify
  in 6s and 95s respectively (both well inside the 180s wall), and the
  PRELUDE/POST_SF text they share with every task (t_go_ext/t_side_ext's
  own definitions) is the only byte difference in their .v files.
  Measured: is_prime now reads verified/refuted (real is_prime_t_spec
  verified, invariant-drop#1 twin refuted at n=4, d=4, exit r=false, i.e.
  the surviving `d >= 2 /\\ d <= n` invariant alone does not carry "4 is not
  prime"); first_even is unchanged (verified/refuted); all 15 committed
  tasks read verified/refuted, matching t/AGREEMENT.md's rocq column
  exactly. A 19-task early-exit fuzz sample (fz_lower.py, n=200, seed=1,
  the v1exit/p_ret family) showed no change before vs after: 16 real-
  verified/twin-unproved, 2 real-unproved, 1 wf-error, zero twins refuted,
  identical in both runs, since none of that particular sample's tasks
  happen to hit either of the two gaps this fix closes (their certificates
  fail earlier, for a different, pre-existing reason outside this fix's
  scope: `_try_cert_v1` never reaches `_loop_cert`'s hint search for them).

  RECURSION. spec_funs and self-recursive bodies become fuel Fixpoints with a
  wrapper at fuel S (Z.to_nat measure). Per spec_fun the generator emits a
  fuel-irrelevance lemma (any fuel above the declared measure computes the
  same value, which IS the termination theorem for the declared measure) and
  the defining-equation lemma used for rewriting. A self-recursive task gets
  a fuel-indexed spec lemma by induction on fuel; the induction hypothesis is
  exactly the modular contract of the self-call (callee requires proved at the
  call site by lia, callee ensures assumed), and the fuel bound is exactly the
  decreases obligation.

  PROOFS. One engine, generic over every task: invertible structural steps,
  deterministic saturation (merge seq-application arguments lia proves equal;
  resolve implications with leaf-provable antecedents; instantiate
  forall-hypotheses at seq-application arguments, E-matching lite), guarded
  case splits (lia-undecidable antecedents; equality of two seq-application
  arguments), then a shallow goal-directed search (witnesses, disjuncts,
  f_equal, backward chaining). Every discharge ends in the kernel: lia,
  assumption, congruence. A goal the engine cannot close fails with
  "Tactic failure: unsolved t verification condition", which the adapter
  classifies UNPROVED: the honest can't-prove, never a shape error and
  never a refutation. REFUTED has exactly one door, the
  witness-grounded t_refutation_certificate this file emits when the
  harness hands a measured twin witness it can ground.

Every file ends with `Print Assumptions`, so the axiom audit ships inside the
artifact. No Admitted, no Axiom: the adapter bans the tokens outright.

  DIVISION AND MODULO (2026-09-08). SPEC.md's `div`/`mod` are Euclidean; rocq
  9.2's native Z.div/Z.modulo are floor (measured: (-7)/2 = -4, (-7) mod 2 =
  1, 7/(-2) = -4, 7 mod (-2) = -1, (-7)/(-2) = 3, (-7) mod (-2) = -1, so the
  floor pair disagrees with Euclid on every negative-divisor case; Z.quot,
  Z.rem truncate instead and agree with neither). Per SPEC.md's rule that no
  lowering may emit a kernel's native `/` or `%` where the convention
  differs, this file never emits Z.div/Z.modulo for t's div/mod: it defines
  its own `t_mod x y := Z.modulo x (Z.abs y)` and `t_div x y := (x - t_mod x
  y) / y` in the preamble (PRELUDE, below), proves `t_mod_bound` (0 <= t_mod
  x y < |y| given y <> 0) and `t_div_mod_eq` (x = t_div x y * y + t_mod x y
  given y <> 0) there by reflexivity-checked ground facts plus
  Z.mod_pos_bound/Z.div_mod/Z.div_mul, and confirms the six Euclidean facts
  by vm_compute before relying on them. Neither t_div nor t_mod is
  transparent to lia (opaque Definitions, not notations), so the proof
  engine's saturation step t_dm1 asserts both lemmas into context, once per
  ground (x, y) pair it finds under `t_div`/`t_mod` in the goal or a
  hypothesis, discharging their `y <> 0` side condition the same way every
  other leaf goal is discharged here (t_leaf). Definedness at y == 0 is
  carried entirely by that side condition: `defs()` emits a `(y <> 0)`
  obligation for every `div`/`mod` node exactly where it emits `at`'s
  `(0 <= idx < len)` obligation, in the same *_def_k lemma calculus, proved
  by t_dis wherever the caller's requires/invariants/earlier ensures make it
  available (never inside t_mod/t_div themselves, which are total in Rocq:
  t_mod x 0 = x mod 0 = 0, t_div x 0 = x / 0 = 0, so totality there proves
  nothing about t's own undefinedness). `mod` collides with a Rocq notation
  token and cannot name a binder, so it joins RESERVED; `div` has no such
  collision (checked against coqc 9.2) and needs none.

  SEQUENCES AS VALUES (2026-09-09, SPEC.md "Sequences as values (v1)",
  ROADMAP 12.7). `seq` becomes a return and local type, and two new
  expressions land: `update` (s[i := v], DEFINED IFF 0 <= i < len(s)) and
  `fill` (seq(n, v), DEFINED IFF n >= 0). The representation decision was
  the function+length pair the file already had for params (a `list Z`
  rewrite would have touched param_binders, seq_fn, defs, emit_spec_funs,
  every gen_* and every certificate builder; the pointwise-redefinition
  route the SAME representation already supports touches far less, and
  SPEC.md leaves the choice to each lowering's own dated note). `update`
  is `t_upd f i v := fun k => if k =? i then v else f k` (same length as
  the inner seq, SPEC.md's own words: "the sequence equal to s at every
  index but i, where it holds v"); `fill` is `t_fill v := fun _ => v`.
  Both are opaque top-level Definitions, never Notations, exactly t_div/
  t_mod's own precedent (2026-09-08, above): cbn's whitelisted delta never
  unfolds them, and totality in Rocq (t_upd/t_fill are defined for every
  index) proves nothing about t's own undefinedness, which is carried
  entirely by defs()'s `(0 <= i < len(s))`/`(n >= 0)` obligations, emitted
  at every `update`/`fill` node exactly where `at`'s is emitted. Reading
  one back is a dedicated case-split tactic (t_upd_case, PRELUDE, mirrors
  t_ltb_case/t_eqb_case's three-branch shape) rather than unfolding: it
  fires on `context [t_upd ?f ?i ?v ?k]` regardless of whether `f` is a
  bare variable, so a NESTED update (swap's own `s[i := s[j]][j := tmp]`)
  reduces one layer per case split until the innermost `f` is a bare
  param/state variable, at which point the residual `f k` is `is_var`-
  headed again and t_sat1's existing merge/E-matching machinery picks it
  up unchanged; `t_fill`'s read (`t_fill_get`) is an unconditional rewrite,
  no case to split. A seq return or local occupies TWO env slots in
  exec_straight (its function, its length; `seq_slots` does the same
  expansion for a loop's state tuple that param_binders already did for
  params), and a seq return is TWO top-level Definitions, `<name>_t` and
  `<name>_t_len` (the function+length model has no single Coq value
  carrying both), unfolded together in the theorem's proof script.

  EQUALITY. `==`/`!=` on two seqs is extensional (SPEC.md: "equal lengths
  and equal elements at every index"), stated exactly that way in `prop()`
  (a length equation conjoined with a bounded forall over the shared
  length), since the function+length model assumes no functional
  extensionality anywhere in this file; a seq `==`/`!=` in COMPUTATIONAL
  position (bx()) has no decidable lowering here (no Fixpoint walks a
  symbolic length to compute a bool) and abstains, the same decision
  quantifiers-in-bx already make.

  TWINS. swap's mutant (off-by-one, `s[i]` read as `s[i+1]`) is refuted by
  an "undefined" witness (interp.py's Reference.witness caught the twin's
  own Undef): s=[0], i=0, j=0, `at index 1 outside [0,1)`. Since t_upd/
  t_fill/t_div/t_mod are all TOTAL in Rocq, an "undefined" witness has no
  twin VALUE for the old value-witness certificate machinery to restate;
  `_undef_cert`/`_first_undef`/`_first_undef_body` (new, this date, the
  same shape the dafny/verus/lean lowerings added the same night) instead
  replay the twin body in interp.ev's own left-to-right/short-circuit
  order and certify the NEGATION of the first at/update/fill/div/mod bound
  that fails, at the concrete witness, closed by `lia` on literals; no
  def_text, no reference to `<name>_t` at all. reverse's twin (dropping
  its one loop invariant) is refuted by an "exit" witness, s=[], i=0,
  r=[0]: `_loop_cert`'s existing machinery, extended for a seq state var
  the same way gen_loop's own Fixpoint was (seq_slots).

  MEASURED (2026-09-09, coqc/coqchk 9.2.0, this box). swap and reverse
  both read COUNTS. All 17 committed tasks (the 15 pre-existing plus these
  two) read verified/refuted, matching AGREEMENT.md's rocq column; wall
  times stayed inside the 180 s budget throughout (digit_sum 3.7 s,
  seq_max 67.6 s, first_even the slowest committed task at 50.2 s, swap
  3.4 s, reverse 3.3 s). Every task with no seq return/update/fill is
  byte-identical outside the shared PRELUDE text (diffed against out/
  abs.v, out/first_even.v, out/digit_sum.v, out/seq_max.v as they stood
  before this date's edit): abs (no seq at all) is untouched byte for
  byte; first_even/digit_sum/seq_max gain only the PRELUDE's t_upd/t_fill
  block (three pure insertions, no deletions, at the same three line
  numbers in each file), since none of the three touches `update`/`fill`.
  A `(Z -> Z) * Z * Z` state-tuple type also needed one grammar fix along
  the way: Coq's `->` binds looser than `*`, so an unparenthesized
  "Z -> Z * Z * Z" in a loop state tuple's type reads as the FUNCTION type
  "Z -> (Z * Z * Z)", not the intended product; reverse's own state tuple
  (r's function, r's length, i) hit this on the first attempt, fixed by
  parenthesizing only the slots whose type actually contains "->" (so a
  non-seq task's tuple type is untouched, confirmed by the same diff).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                                 # noqa: E402
import interp                                  # noqa: E402
from verifiers import rocq as rocq_backend     # noqa: E402

# --------------------------------------------------------------------------
# v0 path, frozen and identical to the original lowering.
# --------------------------------------------------------------------------

PROP_OPS = {"==": "=", "!=": "<>", "<": "<", "<=": "<=", ">": ">", ">=": ">=",
            "+": "+", "-": "-", "*": "*"}
BOOL_CMP = {"<": "<?", "<=": "<=?", "==": "=?"}
NARY = {"and": "/\\", "or": "\\/"}

# The cbn arm is reached only by a condition built with a boolean connective
# (SYNTAX.md's Stmt row puts a full Expr under `if`): the comparison destructs
# leave `negb true` / `false && _` behind, which lia cannot read. Whitelisted
# delta only, because a bare `simpl`/`cbn` here would unfold Z.add against the goal,
# the failure measured on the v1 loop lemma (fz_v1loop_007).
TACTIC = (
    "  intros; unfold {name}_t;\n"
    "  repeat match goal with\n"
    "  | |- context [?a <? ?b] => destruct (Z.ltb_spec a b)\n"
    "  | |- context [?a <=? ?b] => destruct (Z.leb_spec a b)\n"
    "  | |- context [?a =? ?b] => destruct (Z.eqb_spec a b)\n"
    "  | |- _ => progress (cbn [orb andb negb])\n"
    "  end; lia.\n")


def prop0(e: dict, ret_subst: str | None, ret_name: str) -> str:
    if "int" in e:
        return str(e["int"])
    if "var" in e:
        return ret_subst if ret_subst and e["var"] == ret_name else e["var"]
    op = e["op"]
    args = [prop0(a, ret_subst, ret_name) for a in e.get("args", [])]
    if op == "neg":
        return f"(-{args[0]})"
    if op == "not":
        return f"(~ {args[0]})"
    if op == "implies":
        return f"({args[0]} -> {args[1]})"
    if op in NARY:
        return "(" + f" {NARY[op]} ".join(args) + ")"
    if op in PROP_OPS:
        return f"({args[0]} {PROP_OPS[op]} {args[1]})"
    raise ValueError(f"t v0 has no operator {op!r}")


def cond_bool0(e: dict) -> str:
    """The decidable `bool` mirror of a v0 `if` condition.

    SYNTAX.md's Stmt row puts a full Expr under `if`, so every v0 operator
    that can be bool-typed belongs here: the six comparisons and the four
    connectives. Handling only the five order comparisons made 35 of the 74
    generated v0 tasks raise ValueError, which run_all records as LOWER-ERROR
    (measured 2026-09-01, rocq column of the fuzz corpus).
    """
    op = e.get("op")
    if op in BOOL_CMP:
        a, b = (prop0(x, None, "") for x in e["args"])
        return f"({a} {BOOL_CMP[op]} {b})"
    if op == ">":
        b, a = (prop0(x, None, "") for x in e["args"])
        return f"({a} <? {b})"
    if op == ">=":
        b, a = (prop0(x, None, "") for x in e["args"])
        return f"({a} <=? {b})"
    if op == "!=":
        a, b = (prop0(x, None, "") for x in e["args"])
        return f"(negb ({a} =? {b}))"
    if op == "not":
        return f"(negb {cond_bool0(e['args'][0])})"
    if op in ("and", "or"):
        sep = " && " if op == "and" else " || "
        return "(" + sep.join(cond_bool0(x) for x in e["args"]) + ")%bool"
    if op == "implies":
        a, b = (cond_bool0(x) for x in e["args"])
        return f"((negb {a}) || {b})%bool"
    # An int-valued operator under `if` is ill-typed rather than unsupported,
    # but the lowering is not the type checker: abstain, never guess.
    raise NotImplementedError(
        f"rocq lowering: no decidable boolean form for a v0 `if` condition "
        f"headed by {op!r}")


def body_expr0(body: list, ret: str) -> str:
    if len(body) == 1 and "assign" in body[0]:
        name, e = body[0]["assign"]
        assert name == ret, f"assign to {name}, expected {ret}"
        return prop0(e, None, "")
    if len(body) == 1 and "if" in body[0]:
        c = body[0]["if"]
        return (f"if {cond_bool0(c['cond'])} then {body_expr0(c['then'], ret)} "
                f"else {body_expr0(c['else'], ret)}")
    raise ValueError("t v0 -> rocq: body not expressible as one expression")


def lower_v0(task: dict, body: list, witness: dict | None = None) -> str:
    if witness is not None:
        cert = _v0_cert(task, body, witness)
        if cert is not None:
            return cert
    name, ret = task["name"], task["returns"][0]["name"]
    params = " ".join(p["name"] for p in task["params"])
    binder = " ".join(f"({p['name']} : Z)" for p in task["params"])
    applied = f"({name}_t {params})"
    post = " /\\ ".join(prop0(e, applied, ret) for e in task["ensures"])
    pre = " /\\ ".join(prop0(e, applied, ret) for e in task.get("requires", []))
    stmt = f"{pre} -> {post}" if pre else post
    return (
        "From Stdlib Require Import ZArith Lia.\n"
        "Open Scope Z_scope.\n\n"
        f"Definition {name}_t {binder} : Z := {body_expr0(body, ret)}.\n\n"
        f"Theorem {name}_t_spec : forall {binder}, {stmt}.\n"
        "Proof.\n"
        + TACTIC.format(name=name) +
        "Qed.\n\n"
        f"Print Assumptions {name}_t_spec.\n")


# --------------------------------------------------------------------------
# v1: shared tactic prelude (validated piece by piece against coqc 9.2
# before this generator existed; see the session's proto files).
# --------------------------------------------------------------------------

PRELUDE = r"""(* persistent resolution marker: survives destruction of what it records *)
Inductive t_done (P : Prop) : Prop := t_done_intro : t_done P.

Ltac t_leaf := solve [ lia | assumption | congruence | discriminate | (exfalso; lia) ].

(* succeeds iff some hypothesis has exactly type T *)
Ltac t_have T := match goal with H2 : ?T2 |- _ => constr_eq T T2 end.

(* succeeds iff t is a Z numeral literal *)
Ltac t_numeral t :=
  lazymatch t with
  | Z0 => idtac
  | Zpos _ => idtac
  | Zneg _ => idtac
  | _ => fail
  end.

(* replace u with v everywhere, provided lia proves them equal. Orientation
   is load-bearing twice over: when one term occurs inside the other the
   containing term must be the one replaced, or the merge re-creates its own
   trigger and t_base diverges (measured: merging i with i+1-1 the wrong way
   grew -1+1 chains without bound, count_matches' 180 s rocq timeout); and a
   numeral is never the term being replaced *)
Ltac t_merge a b :=
  first
  [ lazymatch b with context [a] => idtac end; replace b with a in * by lia
  | lazymatch a with context [b] => idtac end; replace a with b in * by lia
  | tryif (t_numeral b) then fail else idtac; replace b with a in * by lia
  | tryif (t_numeral a) then fail else idtac; replace a with b in * by lia
  ].

(* Case-split a decided Z boolean EVERYWHERE it occurs, hypotheses included.
   `destruct (Z.ltb_spec a b)` abstracts the conclusion only, so a boolean
   that structural inversion had already moved into a hypothesis was never
   split: 19 of the 24 bool-returning fuzz tasks refuted under rocq while six
   other kernels verified them (measured 2026-09-01). Replacing the boolean
   by its truth value reaches goal and hypotheses alike AND removes the match
   trigger, so the arm cannot re-fire, whereas a hypothesis-side `destruct` would
   loop, since it leaves the boolean standing in the hypothesis.
   Each split first tries the branch the context already decides: that costs
   two lia calls and saves a doubling of the goal, and it is what keeps the
   arms affordable in the hypothesis position, which is scanned only after
   every cheaper arm has failed. *)

(* boolean connectives left behind by a case split; whitelisted delta only,
   so Z arithmetic is never unfolded (the fz_v1loop_007 measurement below) *)
Ltac t_bred := cbn [orb andb negb].
Ltac t_bred_all := try (progress (cbn [orb andb negb] in * )).

Ltac t_ltb_case a b :=
  first
  [ replace (a <? b) with true in * by (symmetry; apply Z.ltb_lt; lia)
  | replace (a <? b) with false in * by (symmetry; apply Z.ltb_ge; lia)
  | let E := fresh "Eb" in
    assert (E : a < b \/ b <= a) by lia; destruct E as [E|E];
    [ replace (a <? b) with true in * by (symmetry; apply Z.ltb_lt; exact E)
    | replace (a <? b) with false in * by (symmetry; apply Z.ltb_ge; exact E) ]
  ]; t_bred_all.

Ltac t_leb_case a b :=
  first
  [ replace (a <=? b) with true in * by (symmetry; apply Z.leb_le; lia)
  | replace (a <=? b) with false in * by (symmetry; apply Z.leb_gt; lia)
  | let E := fresh "Eb" in
    assert (E : a <= b \/ b < a) by lia; destruct E as [E|E];
    [ replace (a <=? b) with true in * by (symmetry; apply Z.leb_le; exact E)
    | replace (a <=? b) with false in * by (symmetry; apply Z.leb_gt; exact E) ]
  ]; t_bred_all.

Ltac t_eqb_case a b :=
  first
  [ replace (a =? b) with true in * by (symmetry; apply Z.eqb_eq; lia)
  | replace (a =? b) with false in * by (symmetry; apply Z.eqb_neq; lia)
  | let E := fresh "Eb" in
    assert (E : a = b \/ a <> b) by lia; destruct E as [E|E];
    [ replace (a =? b) with true in * by (symmetry; apply Z.eqb_eq; exact E)
    | replace (a =? b) with false in * by (symmetry; apply Z.eqb_neq; exact E) ]
  ]; t_bred_all.

Ltac t_beq_case a b :=
  let E := fresh "Eb" in
  destruct (Bool.bool_dec a b) as [E|E];
  [ replace (Bool.eqb a b) with true in *
      by (symmetry; apply Bool.eqb_true_iff; exact E)
  | replace (Bool.eqb a b) with false in *
      by (symmetry; apply Bool.eqb_false_iff; exact E) ]; t_bred_all.

(* t_upd / t_fill (2026-09-09): SPEC.md "Sequences as values (v1)" adds
   `update` (s[i := v], DEFINED IFF 0 <= i < len(s)) and `fill` (seq(n, v),
   DEFINED IFF n >= 0) as expressions, not only parameters. The MODEL
   comment above keeps `seq` as the function+length pair (s : Z -> Z)
   (s_len : Z); `update` and `fill` extend that pair the same way t_div/
   t_mod extend `/`/`mod`: opaque top-level Definitions (never Notations,
   so cbn's whitelisted delta never unfolds them, exactly the div/mod
   precedent), read back by a dedicated case-split tactic rather than by
   unfolding. `t_upd f i v` is `fun k => if k =? i then v else f k`
   (SPEC.md: "the sequence equal to s at every index but i, where it holds
   v"); `t_fill v` is `fun _ => v`. Both are TOTAL in Rocq (t_upd f i v k
   is defined for every k, t_fill v k = v unconditionally), so as with
   t_div/t_mod, totality here proves nothing about t's own undefinedness:
   that is carried entirely by defs()'s own `(0 <= i < len(s))` / `(n >=
   0)` obligation, emitted at every `update`/`fill` node exactly where
   `at`'s is emitted, in the same *_def_k lemma calculus.

   `t_upd_case` mirrors `t_ltb_case`/`t_eqb_case`'s three-branch shape
   (try k = i directly by lia, try k <> i directly by lia, else split and
   recurse): a `context [t_upd ?f ?i ?v ?k]` match fires regardless of
   whether `f` is a bare variable, so it also fires on a NESTED update
   (`t_upd (t_upd s i (s j)) j tmp k`, swap's own shape), reducing it one
   layer at a time until the innermost `f` is a bare param/state variable,
   at which point the residual `f k` application is `is_var`-headed again
   and t_sat1's existing merge/E-matching arms pick it up unchanged
   (measured on probe_seq.v/probe5.v, 2026-09-09: nested and off-target
   reads both reduce to the expected literal or `s k` residual). `t_fill`'s
   read has no case to split (SPEC.md: fill(n,v) "the sequence of length n
   whose every element is v", unconditionally, so `t_fill_get` is a bare
   rewrite, cheap and always safe, kept in the same invertible tier as the
   boolean case-splits it sits beside. *)
Definition t_upd (f : Z -> Z) (i v : Z) : Z -> Z :=
  fun k => if k =? i then v else f k.

Definition t_fill (v : Z) : Z -> Z :=
  fun _ : Z => v.

Lemma t_fill_get : forall (v k : Z), t_fill v k = v.
Proof. reflexivity. Qed.

Ltac t_upd_case f i v k :=
  first
  [ replace (t_upd f i v k) with v in * by (replace k with i by lia;
      unfold t_upd; rewrite Z.eqb_refl; reflexivity)
  | replace (t_upd f i v k) with (f k) in * by (unfold t_upd;
      destruct (Z.eqb_spec k i); [lia|reflexivity])
  | let E := fresh "Eb" in
    assert (E : k = i \/ k <> i) by lia; destruct E as [E|E];
    [ replace (t_upd f i v k) with v in * by (subst; unfold t_upd;
        rewrite Z.eqb_refl; reflexivity)
    | replace (t_upd f i v k) with (f k) in * by (unfold t_upd;
        destruct (Z.eqb_spec k i); [congruence|reflexivity]) ]
  ].

(* invertible structural steps *)
Ltac t_inv1 :=
  match goal with
  | H : False |- _ => destruct H
  | H : _ /\ _ |- _ => destruct H
  | H : exists _, _ |- _ => destruct H
  | H : _ <-> _ |- _ => destruct H
  | H : _ \/ _ |- _ => destruct H
  | |- _ /\ _ => split
  | |- _ <-> _ => split
  | |- forall _, _ => intro
  | |- _ -> _ => intro
  | |- not _ => intro
  | |- context [?a <? ?b] => t_ltb_case a b
  | |- context [?a <=? ?b] => t_leb_case a b
  | |- context [?a =? ?b] => t_eqb_case a b
  | |- context [Bool.eqb ?a ?b] => t_beq_case a b
  | |- context [t_upd ?f ?i ?v ?k] => t_upd_case f i v k
  | |- context [t_fill ?v ?k] => rewrite (t_fill_get v k)
  | |- context [orb _ _] => progress t_bred
  | |- context [andb _ _] => progress t_bred
  | |- context [negb _] => progress t_bred
  | |- context [if true then _ else _] => progress t_bred
  | |- context [if false then _ else _] => progress t_bred
  | _ => progress subst
  (* hypothesis position last: a `context` scan over the whole context is the
     most expensive arm here, and by the time it is reached the goal-side arms
     have already established that the boolean is not in the conclusion. The
     splits reduce the connectives they expose in place (t_bred_all), so no
     hypothesis-side cbn arm is needed in this loop. *)
  | H : context [?a <? ?b] |- _ => t_ltb_case a b
  | H : context [?a <=? ?b] |- _ => t_leb_case a b
  | H : context [?a =? ?b] |- _ => t_eqb_case a b
  | H : context [Bool.eqb ?a ?b] |- _ => t_beq_case a b
  | H : context [t_upd ?f ?i ?v ?k] |- _ => t_upd_case f i v k
  | H : context [t_fill ?v ?k] |- _ => rewrite (t_fill_get v k) in H
  end.

(* deterministic saturation steps *)
Ltac t_sat1 :=
  match goal with
  (* merge var-headed application args that lia proves equal *)
  | H : context [?f ?a] |- context [?f ?b] =>
      is_var f; tryif (constr_eq a b) then fail else idtac; t_merge a b
  | H1 : context [?f ?a], H2 : context [?f ?b] |- _ =>
      is_var f; tryif (constr_eq a b) then fail else idtac; t_merge a b
  | |- context [?f ?a] =>
      is_var f;
      match goal with
      | |- context [?g ?b] =>
          constr_eq f g;
          tryif (constr_eq a b) then fail else idtac; t_merge a b
      end
  (* merge two Z variables lia proves equal: aligns nonlinear atoms (e.g.
     i'*(i'+1) with n*(n+1) once i' = n) that no linear step can relate *)
  | x : Z, y : Z |- _ =>
      tryif (constr_eq x y) then fail else idtac;
      replace x with y in * by lia
  (* resolve an implication whose antecedent is leaf-provable; keep H, pose B,
     and mark the implication done so re-destruction cannot re-fire it *)
  | H : ?A -> ?B |- _ =>
      tryif (t_have constr:(t_done (A -> B))) then fail else idtac;
      let D := fresh "D" in
      assert (D : A) by t_leaf;
      pose proof (t_done_intro (A -> B));
      pose proof (H D); clear D
  (* instantiate forall-hyps at args of var-headed applications (E-matching
     lite: the relevant terms are the indices at which a seq is inspected) *)
  | H : forall _ : Z, _ |- context [?f ?x] =>
      is_var f;
      let I := constr:(H x) in
      let T := type of I in
      tryif (t_have T) then fail else idtac;
      pose proof I
  | H : forall _ : Z, _, H2 : context [?f ?x] |- _ =>
      is_var f;
      let I := constr:(H x) in
      let T := type of I in
      tryif (t_have T) then fail else idtac;
      pose proof I
  end.

(* case-splitting saturation steps (kept last; each is presence-guarded) *)
Ltac t_split1 :=
  match goal with
  (* decide an arithmetic antecedent that lia cannot settle outright *)
  | H : ?A -> ?B |- _ =>
      tryif (t_have constr:(t_done (A -> B))) then fail else idtac;
      tryif (t_have constr:(~ A)) then fail else idtac;
      pose proof (t_done_intro (A -> B));
      let D := fresh "D" in
      assert (D : A \/ ~ A) by lia;
      destruct D as [D|D]; [ pose proof (H D); clear D | idtac ]
  (* decide equality of two var-headed application args (seq congruence);
     on the equal branch eliminate the variable side, never a numeral *)
  | H1 : context [?f ?a], H2 : context [?f ?b] |- _ =>
      is_var f;
      tryif (constr_eq a b) then fail else idtac;
      tryif (t_have constr:(a <> b)) then fail else idtac;
      tryif (t_have constr:(b <> a)) then fail else idtac;
      tryif (assert (a = b) by lia) then fail else idtac;
      tryif (assert (a <> b) by lia) then fail else idtac;
      let D := fresh "D" in
      assert (D : a = b \/ a <> b) by lia;
      destruct D as [D|D];
      [ first [ (is_var b; rewrite <- D in * ) | (is_var a; rewrite D in * ) | idtac ]
      | idtac ]
  | H1 : context [?f ?a] |- context [?f ?b] =>
      is_var f;
      tryif (constr_eq a b) then fail else idtac;
      tryif (t_have constr:(a <> b)) then fail else idtac;
      tryif (t_have constr:(b <> a)) then fail else idtac;
      tryif (assert (a = b) by lia) then fail else idtac;
      tryif (assert (a <> b) by lia) then fail else idtac;
      let D := fresh "D" in
      assert (D : a = b \/ a <> b) by lia;
      destruct D as [D|D];
      [ first [ (is_var b; rewrite <- D in * ) | (is_var a; rewrite D in * ) | idtac ]
      | idtac ]
  | |- context [?f ?a] =>
      is_var f;
      match goal with
      | |- context [?g ?b] =>
          constr_eq f g;
          tryif (constr_eq a b) then fail else idtac;
          tryif (t_have constr:(a <> b)) then fail else idtac;
          tryif (t_have constr:(b <> a)) then fail else idtac;
          tryif (assert (a = b) by lia) then fail else idtac;
          tryif (assert (a <> b) by lia) then fail else idtac;
          let D := fresh "D" in
          assert (D : a = b \/ a <> b) by lia;
          destruct D as [D|D];
          [ first [ (is_var b; rewrite <- D in * ) | (is_var a; rewrite D in * ) | idtac ]
          | idtac ]
      end
  end.

(* t_div / t_mod (2026-09-08): rocq 9.2's native Z.div and Z.modulo are
   FLOOR (measured: (-7)/2 = -4, (-7) mod 2 = 1, 7/(-2) = -4, 7 mod (-2) =
   -1, (-7)/(-2) = 3, (-7) mod (-2) = -1; Z.quot/Z.rem truncate instead),
   while SPEC.md's "Division and modulo (v1)" is Euclidean: for y <> 0,
   0 <= mod(x, y) < |y| and x = div(x, y) * y + mod(x, y). Neither native
   Rocq operator is the one door SPEC.md allows ("no lowering may emit a
   kernel's native `/` or `%` where that kernel's convention differs"), so
   this lowering defines its own pair in the kernel's own terms: t_mod
   folds the sign into the divisor before taking Z.modulo, which for a
   positive divisor already gives the Euclidean remainder in [0, |y|),
   and t_div is then the exact quotient of what's left. Both are total
   Rocq functions (t_mod x 0 = x mod 0 = 0 by Z.modulo's own convention,
   t_div x 0 = x / 0 = 0), so t's own y = 0 undefinedness is carried
   entirely by the `y <> 0` definedness obligation emitted below, in the
   same *_def_k calculus as `at`'s [0, len) obligation, never by these
   definitions pretending 0 is a legal divisor. *)
Definition t_mod (x y : Z) : Z := Z.modulo x (Z.abs y).
Definition t_div (x y : Z) : Z := (x - t_mod x y) / y.

Lemma t_mod_bound : forall x y : Z, y <> 0 -> 0 <= t_mod x y < Z.abs y.
Proof.
  intros x y Hy. unfold t_mod. apply Z.mod_pos_bound. lia.
Qed.

Lemma t_div_mod_eq : forall x y : Z, y <> 0 -> x = t_div x y * y + t_mod x y.
Proof.
  intros x y Hy.
  unfold t_div, t_mod in *.
  assert (Hb : Z.abs y <> 0) by lia.
  assert (Hdm : x = (Z.abs y) * (x / Z.abs y) + x mod (Z.abs y))
    by (apply Z.div_mod; exact Hb).
  set (k := x / Z.abs y) in *.
  set (r := x mod Z.abs y) in *.
  assert (Hxr : x - r = Z.abs y * k) by lia.
  rewrite Hxr.
  destruct (Z.abs_eq_or_opp y) as [Habs | Habs].
  - assert (Hq : k * y / y = k) by (apply Z.div_mul; exact Hy).
    replace (Z.abs y * k) with (k * y) by lia.
    rewrite Hq. lia.
  - assert (Hq : (-k) * y / y = -k) by (apply Z.div_mul; exact Hy).
    replace (Z.abs y * k) with ((-k) * y) by lia.
    rewrite Hq. lia.
Qed.

(* Saturation step for t_div/t_mod: neither is transparent to lia (each is
   an opaque-to-arithmetic Definition, not a notation), so a goal or
   hypothesis mentioning `t_div a b` or `t_mod a b` gets the two facts
   above asserted about that exact (a, b) once, guarded by t_have on the
   div_mod_eq instance itself so repeat cannot re-derive it forever. The
   `y <> 0` side condition is discharged the same way every other leaf
   obligation is here (t_leaf: lia / assumption / congruence / ...); when
   it is not yet provable, the assert fails, match backtracks to another
   occurrence or clause, and t_split1's case splits get a chance to make
   `b <> 0` available before t_dm1 is retried. *)
Ltac t_dm_derive a b :=
  tryif (t_have constr:(a = t_div a b * b + t_mod a b)) then fail else idtac;
  let Hb := fresh "Hb" in
  assert (Hb : b <> 0) by t_leaf;
  pose proof (t_div_mod_eq a b Hb);
  pose proof (t_mod_bound a b Hb).

Ltac t_dm1 :=
  match goal with
  | |- context [t_div ?a ?b] => t_dm_derive a b
  | H : context [t_div ?a ?b] |- _ => t_dm_derive a b
  | |- context [t_mod ?a ?b] => t_dm_derive a b
  | H : context [t_mod ?a ?b] |- _ => t_dm_derive a b
  end.

(* the leading lia closes contradictory contexts before the merge rules can
   see them: with False in scope lia proves any equality, and an equality
   merge under False would replace terms back and forth forever *)
Ltac t_base := repeat (first [ solve [ lia ] | t_inv1 | t_sat1 | t_dm1 | t_split1 ]).

(* goal-directed shallow search *)
Ltac t_go n :=
  t_base;
  first
  [ t_leaf
  | lazymatch n with
    | O => fail
    | S ?m =>
      first
      [ lazymatch goal with
        | |- exists _ : Z, _ =>
            first [ exists 0; t_go m
                  | multimatch goal with x : Z |- _ => exists x; t_go m end ]
        end
      | lazymatch goal with
        | |- _ \/ _ => first [ left; t_go m | right; t_go m ]
        end
      | lazymatch goal with
        | |- _ = _ => progress f_equal; t_go m
        end
      | multimatch goal with
        | H : _ |- _ => solve [ apply H; t_go m ]
        end
      ]
    end
  ].

Ltac t_vc0 := solve [ t_go 6%nat ].

(* Early exit (SPEC.md, 2026-09-08): closing a `return`'s ensures obligation
   from raw invariant/guard/branch-condition facts can need instantiating a
   `forall _ : Z, _` hypothesis at a witness that is not a seq application
   (t_sat1's own instantiation rule only reaches `f x` for a var-headed
   `f`, e.g. `s i`; an early-return branch's own equality, like `n mod d =
   0`, witnesses the negation of an invariant `forall d2, ... -> n mod d2
   <> 0` at `d`, and `t_mod n` is not a variable). t_go_ext tries every
   (forall-hypothesis, Z-variable) pair as a LAST resort, closing with
   t_base (deterministic saturation, which can itself resolve the
   freshly-posed `A -> B` once `A` is leaf-provable, t_sat1's own rule).

   Fixed 2026-09-09: the pair-search has to be reachable at EVERY leaf t_go
   would otherwise give up at, not only the outermost goal. is_prime's own
   ensures is a `<->` (unlike first_even's bare `\/`), so its return branch
   goal is `false = true <-> (forall d, ...)`: the needed forall is not a
   hypothesis until t_go's own `<->`/`->`-splitting (t_base's t_inv1) and
   its `\/` navigation have both run past it. The old t_go_ext tried the
   pair-search exactly once, on the RAW un-navigated goal, where no such
   hypothesis exists yet, so it never found the pair. t_leaf_ext replaces
   t_leaf as the base case of a t_go-shaped recursion (t_go_ext mirrors
   t_go verbatim, calling itself instead of t_go), so the pair-search is
   retried at every leaf the navigation reaches, in particular the one
   inside the iff's hard direction where the forall has just been
   introduced. This still cannot multiply into a full nested search: a
   pair's own attempt closes with t_base/t_leaf exactly as before, never a
   second t_go_ext. *)
Ltac t_leaf_ext :=
  first
  [ t_leaf
  | multimatch goal with
    | H : forall _ : Z, _ |- _ =>
        multimatch goal with
        | y : Z |- _ =>
            let I := constr:(H y) in
            let T := type of I in
            tryif (t_have T) then fail else idtac;
            solve [ pose proof I; t_base; t_leaf ]
        end
    end
  ].

Ltac t_go_ext n :=
  t_base;
  first
  [ t_leaf_ext
  | lazymatch n with
    | O => fail
    | S ?m =>
      first
      [ lazymatch goal with
        | |- exists _ : Z, _ =>
            first [ exists 0; t_go_ext m
                  | multimatch goal with x : Z |- _ => exists x; t_go_ext m end ]
        end
      | lazymatch goal with
        | |- _ \/ _ => first [ left; t_go_ext m | right; t_go_ext m ]
        end
      | lazymatch goal with
        | |- _ = _ => progress f_equal; t_go_ext m
        end
      | multimatch goal with
        | H : _ |- _ => solve [ apply H; t_go_ext m ]
        end
      ]
    end
  ].

Ltac t_sweep :=
  repeat (match goal with
          | |- context [?a <? ?b] => destruct (Z.ltb_spec a b)
          | |- context [?a <=? ?b] => destruct (Z.leb_spec a b)
          | |- context [?a =? ?b] => destruct (Z.eqb_spec a b)
          | |- context [Bool.eqb ?a ?b] => destruct (Bool.eqb_spec a b)
          | _ => progress (cbn [orb andb negb])
          end).
"""

# emitted after the spec_fun section, since t_eqs/t_eqs_h name their
# equation lemmas
POST_SF = r"""Ltac t_dis := first [ solve [ t_vc0 ] | solve [ t_eqs; t_vc0 ]
                          | solve [ t_eqs_h; t_vc0 ] ]
              || fail "unsolved t verification condition".
Ltac t_side := first [ assumption | solve [ lia ]
                     | solve [ t_vc0 ] | solve [ t_eqs; t_vc0 ]
                     | solve [ t_eqs_h; t_vc0 ] ].
(* Early exit (2026-09-08): t_dis with t_go_ext's extra witness-instantiation
   arm, used ONLY in a `return`-bearing loop's step_done=true proof branch
   (see gen_loop / PRELUDE's t_go_ext). t_go_ext tries the cheap t_go path
   first, so this costs a task with no `return` nothing: nothing it emits
   ever calls t_dis_ext. *)
Ltac t_dis_ext := first [ solve [ t_go_ext 6%nat ] | solve [ t_eqs; t_go_ext 6%nat ]
                        | solve [ t_eqs_h; t_go_ext 6%nat ] ]
              || fail "unsolved t verification condition".
(* Early exit, second half of the 2026-09-09 fix: the induction step's
   `apply IH; t_side` arm needs the SAME extra witness-instantiation pair
   search, not only the `intro Heq; ...; t_dis_ext` arm. is_prime's
   invariant is `forall k, 2 <= k < d -> n mod k <> 0`: the recurse
   (not-yet-done) branch has to extend it from `d` to `d + 1`, i.e. prove
   `forall k, 2 <= k < d + 1 -> n mod k <> 0` from the old invariant PLUS
   `n mod d <> 0` (the branch condition that let this iteration continue).
   Once `k` is introduced, closing `k < d \/ k = d` and, on the `k < d`
   side, applying the old invariant at `k`, is exactly the same
   var-headed-application gap `t_go_ext` exists for (`t_mod n` is not a
   variable, so `t_sat1`'s E-matching rule never reaches it): measured on
   is_prime, `apply IH; t_side` alone left exactly this goal unsolved
   (confirmed 2026-09-09 by instrumenting the two arms separately),
   distinct from and in addition to the return branch's own `<->` goal
   `t_dis_ext` alone was written for. `t_side_ext` swaps `t_side`'s
   `t_vc0`/`t_go` calls for `t_go_ext`; used only in the return-bearing
   loop's `apply IH` arm, so a task with no `return` still calls plain
   `t_side` unchanged. *)
Ltac t_side_ext := first [ assumption | solve [ lia ]
                     | solve [ t_go_ext 6%nat ] | solve [ t_eqs; t_go_ext 6%nat ]
                     | solve [ t_eqs_h; t_go_ext 6%nat ] ].
"""

RESERVED = {"at", "in", "fun", "if", "then", "else", "let", "forall", "exists",
            "match", "with", "end", "fix", "Prop", "Set", "Type", "fuel", "fu",
            "s_len", "mod", "rflag", "rf"}
# "mod" is a Rocq notation token (`_ mod _` from ZArith, active regardless of
# scope), so a t identifier literally named `mod` fails to parse as a binder;
# "div" carries no such notation and needs no reservation (checked against
# coqc 9.2, 2026-09-08).


def _ck(name: str) -> str:
    if (name in RESERVED or name.endswith("_len") or name.startswith("sf_")
            or name.startswith("t_")):
        # t_ is the certificate/tactic namespace (t_w_*, t_H, t_dis, ...)
        raise NotImplementedError(
            f"rocq lowering: identifier {name!r} collides with the lowering's "
            f"namespace")
    return name


class Ctx:
    """Expression lowering context for one task."""

    def __init__(self, task: dict):
        self.task = task
        self.tys: dict[str, str] = {}
        for p in task["params"]:
            self.tys[_ck(p["name"])] = p["type"]
        for r in task["returns"]:
            self.tys[_ck(r["name"])] = r["type"]
        self.sfres: dict[str, str] = {}
        self.sfparams: dict[str, list] = {}
        for sf in task.get("spec_funs", []):
            self.sfres[sf["name"]] = sf["result"]
            self.sfparams[sf["name"]] = sf["params"]
        self.sfres[task["name"]] = task["returns"][0]["type"]
        self.sfparams[task["name"]] = task["params"]
        # how to render a call to `fun`: fname -> prefix string; the callee's
        # args are appended. Defaults set by the shapes.
        self.callpre: dict[str, str] = {
            f: f"sf_{f}" for f in self.sfres if f != task["name"]}

    def ty(self, e: dict, local: dict[str, str]) -> str:
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
            return self.sfres[e["call"]["fun"]]
        op = e["op"]
        if op in ("+", "-", "*", "neg", "len", "at", "div", "mod"):
            return "int"
        if op in ("update", "fill"):
            return "seq"
        return "bool"

    # -- rendering helpers ------------------------------------------------
    def seq_fn(self, e: dict, env: dict, local: dict | None = None) -> tuple[str, str]:
        """(function term, length term) for a seq-VALUED expression e:
        `var` (a seq param, return or local), `update` (SPEC.md "s[i := v]
        denotes the sequence equal to s at every index but i, where it
        holds v; its length is len(s)": a pointwise redefinition of the
        inner seq's own function, same length term, unchanged) or `fill`
        (SPEC.md "the sequence of length n whose every element is v": the
        constant function `t_fill v`, length n). `at`'s own env
        substitution convention carries over unchanged: a var's fn/len can
        be a concrete instantiation (certificates substitute t_w_<v> and a
        literal length) via env, absent that the plain names. `t_upd`/
        `t_fill` are opaque top-level Definitions (PRELUDE, dated
        2026-09-09), read back by t_upd_case/t_fill_get inside the proof
        engine rather than by unfolding, the same convention as t_div/
        t_mod."""
        local = local or {}
        if "var" in e:
            v = e["var"]
            assert (local.get(v) or self.tys.get(v)) == "seq", f"{v} is not a seq"
            return env.get(v, v), env.get(v + "_len", f"{v}_len")
        if "ite" in e:
            c = e["ite"]
            cb = self.bx(c["cond"], env, local)
            fn_t, ln_t = self.seq_fn(c["then"], env, local)
            fn_e, ln_e = self.seq_fn(c["else"], env, local)
            return (f"(if {cb} then {fn_t} else {fn_e})",
                    f"(if {cb} then {ln_t} else {ln_e})")
        op = e.get("op")
        if op == "update":
            s, i, v = e["args"]
            fn_s, ln_s = self.seq_fn(s, env, local)
            idx = self.zx(i, env, local)
            val = self.zx(v, env, local)
            return f"(t_upd {fn_s} {idx} {val})", ln_s
        if op == "fill":
            n, v = e["args"]
            ln = self.zx(n, env, local)
            val = self.zx(v, env, local)
            return f"(t_fill {val})", ln
        raise ValueError(f"t v1 -> rocq: not a seq expression: {op!r}")

    def call(self, e: dict, env: dict, local: dict) -> str:
        c = e["call"]
        f, args = c["fun"], c["args"]
        parts = [self.callpre[f]]
        for formal, a in zip(self.sfparams[f], args, strict=True):
            if formal["type"] == "seq":
                fn, ln = self.seq_fn(a, env, local)
                parts += [fn, ln]
            elif formal["type"] == "bool":
                parts.append(self.bx(a, env, local))
            else:
                parts.append(self.zx(a, env, local))
        return "(" + " ".join(parts) + ")"

    def zx(self, e: dict, env: dict, local: dict) -> str:
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
            return self.seq_fn(e["args"][0], env, local)[1]
        if op == "at":
            fn, _ = self.seq_fn(e["args"][0], env, local)
            return f"({fn} {self.zx(e['args'][1], env, local)})"
        if op == "neg":
            return f"(- {self.zx(e['args'][0], env, local)})"
        if op in ("+", "-", "*"):
            a, b = (self.zx(x, env, local) for x in e["args"])
            return f"({a} {op} {b})"
        if op in ("div", "mod"):
            # SPEC.md "Division and modulo (v1)" is Euclidean; rocq's native
            # Z.div/Z.modulo are floor (measured, see t_div/t_mod's own
            # comment in PRELUDE), so the lowering never emits `/` or `mod`
            # here, only the kernel-local t_div/t_mod defined in the preamble.
            a, b = (self.zx(x, env, local) for x in e["args"])
            fn = "t_div" if op == "div" else "t_mod"
            return f"({fn} {a} {b})"
        raise ValueError(f"t v1 -> rocq: not an int expression: {op!r}")

    def bx(self, e: dict, env: dict, local: dict) -> str:
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
                "rocq lowering: a quantifier in computational position has no "
                "decidable lowering here")
        op = e["op"]
        if op in ("<", "<="):
            a, b = (self.zx(x, env, local) for x in e["args"])
            return f"({a} {'<?' if op == '<' else '<=?'} {b})"
        if op in (">", ">="):
            a, b = (self.zx(x, env, local) for x in e["args"])
            return f"({b} {'<?' if op == '>' else '<=?'} {a})"
        if op in ("==", "!="):
            t = self.ty(e["args"][0], local)
            if t == "seq":
                # SPEC.md "Sequences as values (v1)": seq `==`/`!=` are
                # extensional (equal lengths, equal elements at every
                # index), which is a Prop (a bounded forall), not a
                # decidable bool here: no Fixpoint walks a symbolic length
                # to compute one. `prop()` is where `==`/`!=` on two seqs
                # is actually needed (SPEC.md's own example, the `ensures
                # r == s` shape); a seq comparison in computational
                # position abstains rather than guessing, the same
                # decision quantifiers-in-bx already make above.
                raise NotImplementedError(
                    "rocq lowering: seq == / != in computational position "
                    "has no decidable lowering here")
            if t == "bool":
                a, b = (self.bx(x, env, local) for x in e["args"])
                core = f"(Bool.eqb {a} {b})"
            else:
                a, b = (self.zx(x, env, local) for x in e["args"])
                core = f"({a} =? {b})"
            return core if op == "==" else f"(negb {core})"
        if op == "not":
            return f"(negb {self.bx(e['args'][0], env, local)})"
        if op == "and":
            return "(" + " && ".join(self.bx(x, env, local)
                                     for x in e["args"]) + ")%bool"
        if op == "or":
            return "(" + " || ".join(self.bx(x, env, local)
                                     for x in e["args"]) + ")%bool"
        if op == "implies":
            a, b = (self.bx(x, env, local) for x in e["args"])
            return f"((negb {a}) || {b})%bool"
        raise ValueError(f"t v1 -> rocq: not a bool expression: {op!r}")

    def prop(self, e: dict, env: dict, local: dict | None = None) -> str:
        local = local or {}
        if "bool" in e:
            return "True" if e["bool"] else "False"
        if "var" in e:
            t = local.get(e["var"]) or self.tys[e["var"]]
            term = env.get(e["var"], e["var"])
            return f"({term} = true)" if t == "bool" else term
        if "forall" in e or "exists" in e:
            q = e.get("forall") or e.get("exists")
            v = q["var"]
            lo = self.zx(q["lo"], env, local)
            hi = self.zx(q["hi"], env, local)
            # the bound variable shadows anything outside it: strip it from
            # the substitution env so no outer term leaks under the binder
            env2 = {k: t for k, t in env.items() if k != v}
            local2 = dict(local, **{v: "int"})
            body = self.prop(q["body"], env2, local2)
            if "forall" in e:
                return f"(forall {v} : Z, {lo} <= {v} < {hi} -> {body})"
            return f"(exists {v} : Z, {lo} <= {v} < {hi} /\\ {body})"
        if "ite" in e:
            c = e["ite"]
            cp = self.prop(c["cond"], env, local)
            return (f"(({cp} /\\ {self.prop(c['then'], env, local)}) "
                    f"\\/ (~ {cp} /\\ {self.prop(c['else'], env, local)}))")
        if "call" in e:
            return f"({self.call(e, env, local)} = true)"
        op = e["op"]
        if op == "not":
            return f"(~ {self.prop(e['args'][0], env, local)})"
        if op == "and":
            return "(" + " /\\ ".join(self.prop(x, env, local)
                                      for x in e["args"]) + ")"
        if op == "or":
            return "(" + " \\/ ".join(self.prop(x, env, local)
                                      for x in e["args"]) + ")"
        if op == "implies":
            a, b = (self.prop(x, env, local) for x in e["args"])
            return f"({a} -> {b})"
        if op in ("==", "!="):
            t = self.ty(e["args"][0], local)
            if t == "bool":
                a, b = (self.prop(x, env, local) for x in e["args"])
                return (f"({a} <-> {b})" if op == "=="
                        else f"(~ ({a} <-> {b}))")
            if t == "seq":
                # SPEC.md "Sequences as values (v1)": "==" and "!=" apply
                # to two seqs extensionally: "equal lengths and equal
                # elements at every index." The function+length model has
                # no single Coq equality that means this (functional
                # extensionality is not assumed anywhere in this file), so
                # it is stated exactly as SPEC.md phrases it: a length
                # equation conjoined with a bounded forall over the
                # shorter representation's own length (both lengths are
                # already forced equal by the first conjunct, so either
                # works; the left operand's is used).
                fn_a, ln_a = self.seq_fn(e["args"][0], env, local)
                fn_b, ln_b = self.seq_fn(e["args"][1], env, local)
                core = (f"({ln_a} = {ln_b} /\\ "
                        f"(forall t_k : Z, 0 <= t_k < {ln_a} -> "
                        f"{fn_a} t_k = {fn_b} t_k))")
                return core if op == "==" else f"(~ {core})"
            a, b = (self.zx(x, env, local) for x in e["args"])
            return f"({a} = {b})" if op == "==" else f"({a} <> {b})"
        if op in ("<", "<=", ">", ">="):
            a, b = (self.zx(x, env, local) for x in e["args"])
            return f"({a} {op} {b})"
        raise ValueError(f"t v1 -> rocq: not a spec expression: {op!r}")

    # -- definedness obligations ------------------------------------------
    def defs(self, e: dict, ctx: list[str], binders: list[str],
             acc: list, env: dict, local: dict) -> None:
        """Collect (binders, hyps, concl) for every `at`, `div` and `mod` in
        e, honoring the SPEC's left-to-right / taken-branch definedness
        rules. concl is `(0 <= idx < len)` for `at`, `(y <> 0)` for `div`
        and `mod` (SPEC.md: "at y == 0 both are UNDEFINED, a definedness
        obligation exactly like `at` outside [0, len)")."""
        if "int" in e or "bool" in e or "var" in e:
            return
        if "forall" in e or "exists" in e:
            q = e.get("forall") or e.get("exists")
            v = q["var"]
            self.defs(q["lo"], ctx, binders, acc, env, local)
            self.defs(q["hi"], ctx, binders, acc, env, local)
            lo = self.zx(q["lo"], env, local)
            hi = self.zx(q["hi"], env, local)
            env2 = {k: t for k, t in env.items() if k != v}
            local2 = dict(local, **{v: "int"})
            self.defs(q["body"], ctx + [f"({lo} <= {v} < {hi})"],
                      binders + [f"({v} : Z)"], acc, env2, local2)
            return
        if "ite" in e:
            c = e["ite"]
            self.defs(c["cond"], ctx, binders, acc, env, local)
            cp = self.prop(c["cond"], env, local)
            self.defs(c["then"], ctx + [cp], binders, acc, env, local)
            self.defs(c["else"], ctx + [f"(~ {cp})"], binders, acc, env, local)
            return
        if "call" in e:
            for a in e["call"]["args"]:
                self.defs(a, ctx, binders, acc, env, local)
            return
        op = e["op"]
        if op == "at":
            self.defs(e["args"][0], ctx, binders, acc, env, local)
            self.defs(e["args"][1], ctx, binders, acc, env, local)
            _, ln = self.seq_fn(e["args"][0], env, local)
            idx = self.zx(e["args"][1], env, local)
            acc.append((list(binders), list(ctx), f"(0 <= {idx} < {ln})"))
            return
        if op == "update":
            # SPEC.md "Sequences as values (v1)": s[i := v], DEFINED IFF
            # 0 <= i < len(s), the same shape as `at`'s own obligation
            # (and, since `update` is itself a SeqExpr, its own inner `s`
            # may carry further obligations, e.g. a nested update).
            s, i, v = e["args"]
            self.defs(s, ctx, binders, acc, env, local)
            self.defs(i, ctx, binders, acc, env, local)
            self.defs(v, ctx, binders, acc, env, local)
            _, ln = self.seq_fn(s, env, local)
            idx = self.zx(i, env, local)
            acc.append((list(binders), list(ctx), f"(0 <= {idx} < {ln})"))
            return
        if op == "fill":
            # seq(n, v), DEFINED IFF n >= 0 (SPEC.md).
            n, v = e["args"]
            self.defs(n, ctx, binders, acc, env, local)
            self.defs(v, ctx, binders, acc, env, local)
            nn = self.zx(n, env, local)
            acc.append((list(binders), list(ctx), f"({nn} >= 0)"))
            return
        if op in ("div", "mod"):
            self.defs(e["args"][0], ctx, binders, acc, env, local)
            self.defs(e["args"][1], ctx, binders, acc, env, local)
            y = self.zx(e["args"][1], env, local)
            acc.append((list(binders), list(ctx), f"({y} <> 0)"))
            return
        if op == "len":
            self.defs(e["args"][0], ctx, binders, acc, env, local)
            return
        if op in ("and", "or"):
            path = list(ctx)
            for a in e["args"]:
                self.defs(a, path, binders, acc, env, local)
                p = self.prop(a, env, local)
                path = path + ([p] if op == "and" else [f"(~ {p})"])
            return
        if op == "implies":
            a, b = e["args"]
            self.defs(a, ctx, binders, acc, env, local)
            self.defs(b, ctx + [self.prop(a, env, local)], binders, acc,
                      env, local)
            return
        for a in e.get("args", []):
            self.defs(a, ctx, binders, acc, env, local)


# --------------------------------------------------------------------------
# statement-level symbolic execution
# --------------------------------------------------------------------------

def has_self_call(node, name: str) -> bool:
    if isinstance(node, dict):
        if "call" in node and node["call"].get("fun") == name:
            return True
        return any(has_self_call(v, name) for v in node.values())
    if isinstance(node, list):
        return any(has_self_call(v, name) for v in node)
    return False


def has_return(body: list) -> bool:
    """True iff `body` contains a `return` statement at any depth (through
    `if`/`while`). Early exit (SPEC.md, 2026-09-08): a loop whose body has no
    `return` is lowered exactly as before (v1's original single-outcome
    Fixpoint); one that does gets the two-outcome encoding in `gen_loop`."""
    for s in body:
        if "return" in s:
            return True
        if "if" in s and (has_return(s["if"]["then"])
                          or has_return(s["if"]["else"])):
            return True
        if "while" in s and has_return(s["while"]["body"]):
            return True
    return False


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
    """Return (prefix, while_stmt, suffix) if exactly one top-level while and
    none nested anywhere else; (body, None, []) if no while at all."""
    def any_while(stmts):
        for s in stmts:
            if "while" in s:
                return True
            if "if" in s and (any_while(s["if"]["then"])
                              or any_while(s["if"]["else"])):
                return True
        return False

    idxs = [k for k, s in enumerate(body) if "while" in s]
    for s in body:
        if "if" in s and (any_while(s["if"]["then"])
                          or any_while(s["if"]["else"])):
            raise NotImplementedError(
                "rocq lowering: a loop under a conditional is not lowered yet")
    if not idxs:
        return body, None, []
    if len(idxs) > 1:
        raise NotImplementedError(
            "rocq lowering: more than one loop per body is not lowered yet")
    k = idxs[0]
    w = body[k]["while"]
    if any_while(w["body"]):
        raise NotImplementedError(
            "rocq lowering: nested loops are not lowered yet")
    return body[:k], w, body[k + 1:]


# Early exit (SPEC.md, 2026-09-08): env's synthetic "has this path already
# returned" flag. Never a valid t identifier (see RESERVED/_ck), so it can
# never collide with a source variable; absent means "false", read back via
# env.get(_DONE, "false"). A body with no `return` anywhere never writes
# this key, so exec_straight's output (and everything built on it) is
# byte-identical to before `return` existed: the whole feature is additive.
_DONE = "__returned__"


def exec_straight(cx: Ctx, stmts: list, env: dict, local: dict,
                  defs_ctx: list[str] | None, defs_binders: list[str],
                  acc: list) -> dict:
    """Symbolic execution of straight-line + if statements. env maps mutable
    var -> term; local maps locals -> type (also recorded in cx.tys). When
    defs_ctx is not None, definedness obligations are collected along the
    path conditions.

    `return` (SPEC.md "Early exit"): sets the return name and marks _DONE
    true. Every assignment textually after a possibly-taken return is
    frozen on the paths where _DONE already holds, via the same
    if-then-else merge `if` already builds for its own two branches: `if
    __returned__ then <old value> else <this statement's new value>`. Since
    well-formedness bars anything from following a return WITHIN its own
    block, the only way _DONE can be a non-literal term (rather than a
    constant "true"/"false") reaching a later statement is that an
    enclosing `if` returned on one arm and not the other; the merge below
    already produces exactly that ITE for _DONE itself, so the freezing
    composes to any nesting depth for free. Definedness obligations for a
    statement that only runs on the surviving (non-returned) path are
    collected under the extra hypothesis `~ done`: a frozen variable's old
    value was already proved defined at the point it froze, so demanding
    it again here would be strictly stronger than necessary, and for a
    task with no `return` this adds nothing (`done` is the literal
    "false", so no hypothesis is added and no lemma text changes)."""
    env = dict(env)
    for s in stmts:
        done = env.get(_DONE, "false")
        cur_ctx = (None if defs_ctx is None else
                  (defs_ctx if done == "false"
                   else defs_ctx + [f"(~ ({done} = true))"]))
        if "assign" in s:
            v, e = s["assign"]
            assert v in env, f"assign to undeclared {v}"
            t = local.get(v) or cx.tys[v]
            if cur_ctx is not None:
                cx.defs(e, cur_ctx, defs_binders, acc, env, local)
            if t == "seq":
                # a seq var occupies TWO env slots (v, the function; v_len,
                # its length), exactly the params' own convention
                # (param_binders): the early-exit freeze below applies to
                # each slot separately, same rule as every other type.
                fn, ln = cx.seq_fn(e, env, local)
                old_fn, old_ln = env[v], env[v + "_len"]
                env[v] = fn if done == "false" else f"(if {done} then {old_fn} else {fn})"
                env[v + "_len"] = (ln if done == "false"
                                   else f"(if {done} then {old_ln} else {ln})")
            else:
                raw = (cx.bx(e, env, local) if t == "bool"
                      else cx.zx(e, env, local))
                env[v] = raw if done == "false" else f"(if {done} then {env[v]} else {raw})"
        elif "return" in s:
            v, e = s["return"]
            assert v in env, f"return to undeclared {v}"
            t = local.get(v) or cx.tys[v]
            if cur_ctx is not None:
                cx.defs(e, cur_ctx, defs_binders, acc, env, local)
            if t == "seq":
                fn, ln = cx.seq_fn(e, env, local)
                old_fn, old_ln = env[v], env[v + "_len"]
                env[v] = fn if done == "false" else f"(if {done} then {old_fn} else {fn})"
                env[v + "_len"] = (ln if done == "false"
                                   else f"(if {done} then {old_ln} else {ln})")
            else:
                raw = (cx.bx(e, env, local) if t == "bool"
                      else cx.zx(e, env, local))
                # true unconditionally: either this is the return that first
                # sets _DONE, or the statement is dead (done was already
                # true) and the guard below keeps `v` at its already-frozen
                # value.
                env[v] = raw if done == "false" else f"(if {done} then {env[v]} else {raw})"
            env[_DONE] = "true"
        elif "var" in s:
            d = s["var"]
            v = _ck(d["name"])
            assert v not in cx.tys and v not in local, f"redeclared {v}"
            local[v] = d["type"]
            cx.tys[v] = d["type"]
            if cur_ctx is not None:
                cx.defs(d["init"], cur_ctx, defs_binders, acc, env, local)
            # a fresh local has no prior value to freeze to; SPEC.md's
            # return leaves no statement of its own block to run after it,
            # and this lowering never carries a not-yet-declared local past
            # the point a return could matter (find_while/gen_loop only
            # feed `return`-bearing bodies to the loop-body path, where
            # `var` never appears), so no guard is needed here.
            if d["type"] == "seq":
                fn, ln = cx.seq_fn(d["init"], env, local)
                env[v] = fn
                env[v + "_len"] = ln
            else:
                env[v] = (cx.bx(d["init"], env, local) if d["type"] == "bool"
                          else cx.zx(d["init"], env, local))
        elif "if" in s:
            c = s["if"]
            if cur_ctx is not None:
                cx.defs(c["cond"], cur_ctx, defs_binders, acc, env, local)
            cp = cx.prop(c["cond"], env, local)
            cb = cx.bx(c["cond"], env, local)
            env_t = exec_straight(
                cx, c["then"], env, local,
                None if cur_ctx is None else cur_ctx + [cp],
                defs_binders, acc)
            env_e = exec_straight(
                cx, c["else"], env, local,
                None if cur_ctx is None else cur_ctx + [f"(~ {cp})"],
                defs_binders, acc)
            for v in set(env) | set(env_t) | set(env_e):
                base = env.get(v, "false" if v == _DONE else None)
                tv = env_t.get(v, base)
                ev = env_e.get(v, base)
                env[v] = tv if tv == ev else f"(if {cb} then {tv} else {ev})"
        elif "while" in s:
            raise AssertionError("while must be split out before exec")
        else:
            raise ValueError(f"t v1 -> rocq: no statement {list(s)!r}")
    return env


# --------------------------------------------------------------------------
# v1 code generation
# --------------------------------------------------------------------------

def seq_slots(names: list[str], stys: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    """Expand a list of LOGICAL loop-state variable names into Coq binder
    slots, a seq state var contributing two (`v`, its function; `v_len`,
    its length), int/bool contributing one, `v` itself; the same
    expansion `param_binders` does for params, needed here too now that
    SPEC.md's "Sequences as values (v1)" makes `seq` a return/local type
    (gen_loop's state tuple can carry one). Returns (slot names in loop-
    state order, slot -> Coq type text)."""
    slots, sty = [], {}
    for v in names:
        slots.append(v)
        sty[v] = rty(stys[v])
        if stys[v] == "seq":
            slots.append(v + "_len")
            sty[v + "_len"] = "Z"
    return slots, sty


def slot_owner(v: str, logical: list[str]) -> str:
    """Map an expanded slot name back to the LOGICAL (task-level) state
    variable it derives from: `v_len` for a seq state var `v` maps to `v`
    itself (SPEC.md's frame rule talks about the syntactic assigned SET,
    which only ever names `v`, never the synthetic length slot), anything
    else maps to itself."""
    if v.endswith("_len") and v[:-4] in logical:
        return v[:-4]
    return v


def param_binders(cx: Ctx) -> tuple[str, str]:
    """(binder text, arg text) with seq expanded to fn+len."""
    bs, args = [], []
    for p in cx.task["params"]:
        v = p["name"]
        if p["type"] == "seq":
            bs.append(f"({v} : Z -> Z) ({v}_len : Z)")
            args += [v, f"{v}_len"]
        elif p["type"] == "bool":
            bs.append(f"({v} : bool)")
            args.append(v)
        else:
            bs.append(f"({v} : Z)")
            args.append(v)
    return " ".join(bs), " ".join(args)


def len_hyps(cx: Ctx) -> list[str]:
    return [f"(0 <= {p['name']}_len)" for p in cx.task["params"]
            if p["type"] == "seq"]


def rty(t: str) -> str:
    """Coq type for a t type in a SINGLE-slot position (a t `seq` is never
    one Coq value here, the function+length model needs two; a caller with
    a seq in hand uses `seq_slots`/an explicit two-binder split instead of
    this, so `rty("seq")` names only the function half, "Z -> Z", the same
    half `param_binders` gives a seq param)."""
    if t == "bool":
        return "bool"
    if t == "seq":
        return "Z -> Z"
    return "Z"


def emit_def_lemmas(cx: Ctx, name: str, obls: list, extra_binders: str = "",
                    counter: list | None = None) -> str:
    out = []
    counter = counter if counter is not None else [0]
    pb, _ = param_binders(cx)
    for binders, hyps, concl in obls:
        counter[0] += 1
        k = counter[0]
        allb = " ".join(x for x in [pb, extra_binders, " ".join(binders)] if x)
        hs = len_hyps(cx) + hyps
        hyp_txt = "".join(f"  {h} ->\n" for h in hs)
        out.append(
            f"Lemma {name}_def_{k} : forall {allb},\n{hyp_txt}"
            f"  {concl}.\n"
            f"Proof. intros. t_dis. Qed.\n")
    return "\n".join(out)


def emit_spec_funs(cx: Ctx) -> str:
    """Fuel fixpoint + wrapper + irrelevance + equation lemma per spec_fun,
    plus t_eqs. Also collects definedness lemmas for spec_fun bodies."""
    task = cx.task
    chunks = []
    eqs = []
    counter = [0]
    for sf in task.get("spec_funs", []):
        f = sf["name"]
        res = rty(sf["result"])
        default = "false" if sf["result"] == "bool" else "0"
        # binders for the spec_fun's own params
        bs, args = [], []
        sf_tys = {}
        for p in sf["params"]:
            v = p["name"]
            sf_tys[v] = p["type"]
            if p["type"] == "seq":
                bs.append(f"({v} : Z -> Z) ({v}_len : Z)")
                args += [v, f"{v}_len"]
            else:
                bs.append(f"({v} : {rty(p['type'])})")
                args.append(v)
        btxt, atxt = " ".join(bs), " ".join(args)

        # body lowering: inside the fixpoint, self-calls use fuel `fu`
        saved_tys = dict(cx.tys)
        cx.tys.update(sf_tys)
        saved_pre = dict(cx.callpre)
        cx.callpre[f] = f"sf_{f}_fuel fu"
        body_fuel = (cx.bx(sf["body"], {}, {}) if sf["result"] == "bool"
                     else cx.zx(sf["body"], {}, {}))
        cx.callpre[f] = f"sf_{f}"
        body_plain = (cx.bx(sf["body"], {}, {}) if sf["result"] == "bool"
                      else cx.zx(sf["body"], {}, {}))
        measure = cx.zx(sf["decreases"], {}, {})
        sf_lens = [f"(0 <= {p['name']}_len)" for p in sf["params"]
                   if p["type"] == "seq"]

        # definedness obligations of the spec_fun body under its own path
        # conditions; the lemmas are emitted later, once t_dis exists
        obls: list = []
        cx.defs(sf["body"], [], [], obls, {}, {})
        cx._sf_obls = getattr(cx, "_sf_obls", [])
        for binders, hyps, concl in obls:
            cx._sf_obls.append((f, btxt, sf_lens, binders, hyps, concl))

        chunks.append(f"""Fixpoint sf_{f}_fuel (fuel : nat) {btxt} : {res} :=
  match fuel with
  | O => {default}
  | S fu => {body_fuel}
  end.

Definition sf_{f} {btxt} : {res} :=
  sf_{f}_fuel (S (Z.to_nat {measure})) {atxt}.

Lemma sf_{f}_fuel_irrel :
  forall (fuel fuel' : nat) {btxt},
  (Z.to_nat {measure} < fuel)%nat -> (Z.to_nat {measure} < fuel')%nat ->
  sf_{f}_fuel fuel {atxt} = sf_{f}_fuel fuel' {atxt}.
Proof.
  induction fuel as [|fu IH]; intros fuel' {atxt} Hf Hf'; [ lia | ].
  destruct fuel' as [|fu']; [ lia | ].
  cbn [sf_{f}_fuel]; t_sweep;
  repeat first [ reflexivity
               | solve [ lia ]
               | solve [ apply IH; repeat t_dm1; lia ]
               | f_equal ].
  all: fail "unsolved t verification condition".
Qed.

Lemma sf_{f}_eq :
  forall {btxt},
  sf_{f} {atxt} = {body_plain}.
Proof.
  intros; unfold sf_{f} at 1; cbn [sf_{f}_fuel]; t_sweep;
  repeat first [ reflexivity
               | solve [ lia ]
               | solve [ unfold sf_{f}; apply sf_{f}_fuel_irrel; repeat t_dm1; lia ]
               | f_equal ].
  all: fail "unsolved t verification condition".
Qed.
""")
        eqs.append(f"sf_{f}_eq")
        cx.tys = saved_tys
        cx.callpre = saved_pre
        cx.callpre[f] = f"sf_{f}"

    if eqs:
        eq_tac = " ".join(f"try rewrite {e};" for e in eqs)
        # t_eqs unfolds a spec_fun equation in the GOAL (needed when the
        # goal's own application is the one recursion's own step exposes,
        # e.g. count_matches: the loop's forward step lands on count(s,x,
        # i+1) in the goal, one unfold away from the invariant's count(s,x,
        # i)). t_eqs_h unfolds it in HYPOTHESES only (`in * |-`, never the
        # goal), needed the opposite way round: digit_sum's invariant `r +
        # dsum(m) = dsum(n)` carries the application at the OLD state in a
        # hypothesis, and it is that occurrence, not the goal's dsum(m/10)
        # at the NEW state, that one unfold away from closing the step.
        # Rewriting the wrong side (the goal's dsum(m/10)) only grows a
        # fresh, unrelated application and cannot converge, so both are
        # kept as separate `solve` alternatives in t_dis/t_side (below)
        # rather than combined: a rewrite that helps one shape is dead
        # weight, never harm, on the other, since `first` restores the
        # goal between alternatives (measured on digit_sum, 2026-09-08).
        eq_tac_h = " ".join(f"try rewrite {e} in * |-;" for e in eqs)
        chunks.append(f"Ltac t_eqs := {eq_tac} idtac.\n")
        chunks.append(f"Ltac t_eqs_h := {eq_tac_h} idtac.\n")
    else:
        chunks.append("Ltac t_eqs := idtac.\n")
        chunks.append("Ltac t_eqs_h := idtac.\n")
    return "\n".join(chunks)


def emit_sf_def_lemmas(cx: Ctx, counter: list) -> str:
    """Definedness lemmas for spec_fun bodies (emitted after t_dis exists)."""
    out = []
    for f, btxt, sf_lens, binders, hyps, concl in getattr(cx, "_sf_obls", []):
        counter[0] += 1
        k = counter[0]
        allb = " ".join(x for x in [btxt, " ".join(binders)] if x)
        hs = sf_lens + hyps
        hyp_txt = "".join(f"  {h} ->\n" for h in hs)
        out.append(
            f"Lemma {cx.task['name']}_def_{k} : forall {allb},\n{hyp_txt}"
            f"  {concl}.\n"
            f"Proof. intros. t_dis. Qed.\n")
    return "\n".join(out)


def spec_def_obls(cx: Ctx) -> tuple[list, list]:
    """Definedness obligations for requires and ensures (r universally
    quantified). Returns (req_obls, ens_obls)."""
    task = cx.task
    req_obls: list = []
    ctx: list[str] = []
    for e in task.get("requires", []):
        cx.defs(e, list(ctx), [], req_obls, {}, {})
        ctx.append(cx.prop(e, {}))
    ens_obls: list = []
    ectx = list(ctx)
    for e in task["ensures"]:
        cx.defs(e, list(ectx), [], ens_obls, {}, {})
        ectx.append(cx.prop(e, {}))
    return req_obls, ens_obls


def ensures_text(cx: Ctx, ret_binding) -> str:
    """`ret_binding` is either a bare Coq term (int/bool return, unchanged
    from before seq returns existed) or a dict binding the return's own
    env slots directly (`{ret: fn_term, ret + "_len": len_term}` for a seq
    return, mirroring how a seq PARAM already occupies two env slots)."""
    task = cx.task
    ret = task["returns"][0]["name"]
    env = dict(ret_binding) if isinstance(ret_binding, dict) else {ret: ret_binding}
    return " /\\ ".join(cx.prop(e, env) for e in task["ensures"])


def requires_arrows(cx: Ctx) -> str:
    return "".join(f"  {cx.prop(e, {})} ->\n"
                   for e in cx.task.get("requires", []))


def lens_arrows(cx: Ctx) -> str:
    return "".join(f"  {h} ->\n" for h in len_hyps(cx))


def header() -> str:
    return ("From Stdlib Require Import ZArith Bool Lia.\n"
            "Open Scope Z_scope.\n\n" + PRELUDE + "\n")


def lower_v1(task: dict, body: list, witness: dict | None = None) -> str:
    if witness is not None:
        cert = _try_cert_v1(task, body, witness)
        if cert is not None:
            return cert
    cx = Ctx(task)
    name = task["name"]
    ret = task["returns"][0]["name"]
    ret_t = task["returns"][0]["type"]
    pb, pargs = param_binders(cx)

    prefix, w, suffix = find_while(body)
    selfrec = has_self_call(body, name)
    if w is not None and selfrec:
        raise NotImplementedError(
            "rocq lowering: a body that both loops and self-recurses is not "
            "lowered yet")

    parts = [header()]
    parts.append(emit_spec_funs(cx))
    parts.append(POST_SF + "\n")

    counter = [0]
    parts.append(emit_sf_def_lemmas(cx, counter))
    req_obls, ens_obls = spec_def_obls(cx)
    parts.append(emit_def_lemmas(cx, name, req_obls, counter=counter))
    # a seq return owes the SAME two-binder expansion a seq param gets
    # (param_binders): the ens_obls lemmas below are schematic in the
    # return, so they need both the function AND its length in scope.
    rb = (f"({ret} : Z -> Z) ({ret}_len : Z)" if ret_t == "seq"
          else f"({ret} : {rty(ret_t)})")
    parts.append(emit_def_lemmas(cx, name, ens_obls, extra_binders=rb,
                                 counter=counter))

    if w is not None:
        parts.append(gen_loop(cx, prefix, w, suffix, counter))
    elif selfrec:
        parts.append(gen_rec(cx, body))
    else:
        parts.append(gen_plain(cx, body, counter))

    parts.append(f"\nPrint Assumptions {name}_t_spec.\n")
    return "\n".join(p for p in parts if p)


def gen_plain(cx: Ctx, body: list, counter: list) -> str:
    """Straight-line/if body, no loop, no self-call."""
    task = cx.task
    name = task["name"]
    ret = task["returns"][0]["name"]
    ret_t = task["returns"][0]["type"]
    pb, pargs = param_binders(cx)

    local: dict[str, str] = {}
    obls: list = []
    reqs = [cx.prop(e, {}) for e in task.get("requires", [])]
    if ret_t == "seq":
        env0 = {ret: "(fun _ : Z => 0)", ret + "_len": "0"}
    else:
        env0 = {ret: "false" if ret_t == "bool" else "0"}
    env = exec_straight(cx, body, env0, local, list(reqs), [], obls)
    def_txt = emit_def_lemmas(cx, name, obls, counter=counter)

    if ret_t == "seq":
        # SPEC.md "Sequences as values (v1)" makes `seq` a return type; the
        # function+length model has no single Coq value carrying both, so
        # a seq return is TWO top-level Definitions, `{name}_t` (the
        # function) and `{name}_t_len` (its length), the same split a seq
        # PARAM already gets via param_binders. ensures_text's dict form
        # binds both applied terms into the return's own two env slots
        # before rendering `ensures`.
        fn_expr, len_expr = env[ret], env[ret + "_len"]
        ens = ensures_text(cx, {ret: f"({name}_t {pargs})",
                                ret + "_len": f"({name}_t_len {pargs})"})
        return f"""{def_txt}
Definition {name}_t {pb} : Z -> Z := {fn_expr}.
Definition {name}_t_len {pb} : Z := {len_expr}.

Theorem {name}_t_spec :
  forall {pb},
{lens_arrows(cx)}{requires_arrows(cx)}  {ens}.
Proof.
  intros.
  unfold {name}_t, {name}_t_len.
  t_dis.
Qed.
"""

    expr = env[ret]
    ens = ensures_text(cx, f"({name}_t {pargs})")
    return f"""{def_txt}
Definition {name}_t {pb} : {rty(ret_t)} := {expr}.

Theorem {name}_t_spec :
  forall {pb},
{lens_arrows(cx)}{requires_arrows(cx)}  {ens}.
Proof.
  intros.
  unfold {name}_t.
  t_dis.
Qed.
"""


def gen_loop(cx: Ctx, prefix: list, w: dict, suffix: list,
             counter: list) -> str:
    task = cx.task
    name = task["name"]
    ret = task["returns"][0]["name"]
    ret_t = task["returns"][0]["type"]
    pb, pargs = param_binders(cx)
    reqs = [cx.prop(e, {}) for e in task.get("requires", [])]

    # prefix symbolic execution (definedness under requires)
    local: dict[str, str] = {}
    obls: list = []
    if ret_t == "seq":
        env0 = {ret: "(fun _ : Z => 0)", ret + "_len": "0"}
    else:
        env0 = {ret: "false" if ret_t == "bool" else "0"}
    env_pre = exec_straight(cx, prefix, env0, local, list(reqs), [], obls)

    # state variables: return + locals declared in the prefix, in order
    svars = [ret] + [s["var"]["name"] for s in prefix if "var" in s]
    stys = {v: (local.get(v) or cx.tys[v]) for v in svars}
    # SPEC.md "Sequences as values (v1)" lets a seq be a loop's return or a
    # prefix local: `svars_x` is the state tuple's own Coq SLOTS, a seq
    # state var expanding to two (its function, its length), the same
    # expansion param_binders already does for params (seq_slots).
    svars_x, slot_ty = seq_slots(svars, stys)
    id_env = {v: v for v in svars_x}

    guard_b = cx.bx(w["cond"], id_env, local)
    guard_p = cx.prop(w["cond"], id_env, local)
    dec = cx.zx(w["decreases"], id_env, local)
    invs = [cx.prop(e, id_env, local) for e in w.get("invariants", [])]

    # invariant definedness: each invariant assumes requires + earlier ones
    inv_ctx = list(reqs)
    sb = " ".join(f"({v} : {slot_ty[v]})" for v in svars_x)
    for e in w.get("invariants", []):
        iob: list = []
        cx.defs(e, list(inv_ctx), [], iob, id_env, local)
        obls += iob
        inv_ctx.append(cx.prop(e, id_env, local))
    # guard + decreases definedness under requires + invariants
    gob: list = []
    cx.defs(w["cond"], list(inv_ctx), [], gob, id_env, local)
    cx.defs(w["decreases"], list(inv_ctx), [], gob, id_env, local)
    obls += gob
    # loop body: definedness under requires + invariants + guard
    body_ctx = inv_ctx + [guard_p]
    step_env = exec_straight(cx, w["body"], id_env, dict(local),
                             list(body_ctx), [], obls)
    step_terms = " ".join(step_env[v] for v in svars_x)
    # Early exit (SPEC.md, 2026-09-08): step_env's synthetic _DONE entry is
    # the literal "false" unless w["body"] actually executed a `return`
    # (exec_straight only ever writes it after seeing one), so this is
    # exactly has_return(w["body"]) without a second traversal.
    step_done = step_env.get(_DONE, "false")
    if step_done != "false" and any(stys[v] == "seq" for v in svars):
        # Early exit's two-outcome Fixpoint (below) collapses the return
        # into `primed[0]`, one Coq slot; a seq state var needs two, so
        # that collapse is wrong for it. No committed task needs the
        # combination yet (reverse has no `return`; is_prime/first_even
        # have no seq), so this abstains rather than emitting it wrong.
        raise NotImplementedError(
            "rocq lowering: a seq-typed loop state with early exit ('return' "
            "in the loop body) is not lowered yet")

    # suffix (after the loop): requires + invariants + ~guard
    post_ctx = inv_ctx + [f"(~ {guard_p})"]
    env_post = exec_straight(cx, suffix, id_env, dict(local),
                             list(post_ctx), [], obls)
    result_term = env_post[ret]

    # the state-var definedness lemmas quantify over the state
    def_txt = emit_def_lemmas(cx, name, obls, extra_binders=sb,
                              counter=counter)

    # a seq slot's own type ("Z -> Z") is parenthesized before joining with
    # `*`: `->` binds LOOSER than `*` in Coq's grammar, so an
    # unparenthesized join reads "Z -> Z * Z * Z" as the FUNCTION type
    # "Z -> (Z * Z * Z)", not the intended product (Z -> Z) * Z * Z
    # (measured, 2026-09-09: reverse's state tuple hit exactly this). A
    # non-seq slot's type ("Z"/"bool") never needs the parens, so they are
    # added only where "->" is actually present, keeping every task with
    # no seq loop state byte-identical to before this existed.
    tup_ty = "(" + " * ".join(
        f"({slot_ty[v]})" if "->" in slot_ty[v] else slot_ty[v]
        for v in svars_x) + ")%type"
    tup = "(" + ", ".join(svars_x) + ")"
    primed = [v + "'" for v in svars_x]
    tup_p = "(" + ", ".join(primed) + ")"
    pat_p = primed[0]
    for v in primed[1:]:
        pat_p = f"[{pat_p} {v}]" if pat_p.startswith("[") else f"[{pat_p} {v}]"
    # left-nested destruct pattern: [[a b] c]
    pat_p = primed[0]
    for v in primed[1:]:
        pat_p = f"[{pat_p} {v}]"
    sb_p = " ".join(f"({v}' : {slot_ty[v]})" for v in svars_x)
    penv = {v: v + "'" for v in svars_x}
    invs_p = [cx.prop(e, penv, local) for e in w.get("invariants", [])]
    guard_pp = cx.prop(w["cond"], penv, local)
    dec0 = cx.zx(w["decreases"],
                 {**{v: env_pre[v] for v in svars_x}}, local)
    init_terms = " ".join(env_pre[v] for v in svars_x)

    lens = len_hyps(cx)
    n_lens, n_reqs, n_invs = len(lens), len(reqs), len(invs)
    hyp_names = ([f"Hl{k+1}" for k in range(n_lens)]
                 + [f"Hreq{k+1}" for k in range(n_reqs)]
                 + ["Hfuel"] + [f"Hinv{k+1}" for k in range(n_invs)])
    lemma_hyps = "".join(f"  {h} ->\n" for h in lens + reqs)
    inv_hyps = "".join(f"  {p} ->\n" for p in invs)
    # SPEC.md frame rule: the loop havocs exactly the syntactic assigned set
    # of its body, so the loop lemma's conclusion also carries one frame
    # equality per state var the body never assigns (its output component
    # equals its input; the Fixpoint threads it through unchanged, so the
    # same fuel induction proves it). Without these the final theorem knew
    # only invariants + negated guard about the tuple, the havoc-everything
    # reading: fr_probe_ret / fr_probe_local were unprovable here while
    # Dafny, Verus and Frama-C proved them (measured 2026-09-02).
    body_assigned = loop_assigned(w["body"])
    frame = [v for v in svars_x if slot_owner(v, svars) not in body_assigned]
    concl = " /\\ ".join(invs_p + [f"(~ {guard_pp})"]
                         + [f"{v}' = {v}" for v in frame])

    if ret_t == "seq":
        ens = ensures_text(cx, {ret: f"({name}_t {pargs})",
                                ret + "_len": f"({name}_t_len {pargs})"})
    else:
        ens = ensures_text(cx, f"({name}_t {pargs})")
    state_names = " ".join(svars_x)
    primed_names = " ".join(primed)
    param_names = pargs

    ini_asserts = "".join(
        f"  assert (Hini{k+1} : {cx.prop(e, {v: env_pre[v] for v in svars_x}, local)}) by t_dis.\n"
        for k, e in enumerate(w.get("invariants", [])))
    lens_intro = " ".join(f"Hl{k+1}" for k in range(n_lens))
    reqs_intro = " ".join(f"Hreq{k+1}" for k in range(n_reqs))
    ini_intro = " ".join(f"Hini{k+1}" for k in range(n_invs))

    # The induction step needs exactly one reduction: the fixpoint's own
    # iota step on `S fu`. `simpl` also unfolds Z.add against the goal,
    # measured on fz_v1loop_007, where `4 + i' * 1` became a raw match on the
    # binary positive, past which neither lia nor `apply IH` can go (six
    # kernels verified that task, rocq refuted it). Whitelisted delta keeps
    # the arithmetic in the form the induction hypothesis is stated in.

    if step_done == "false":
        # No `return` in this loop's body: identical to the lowering before
        # SPEC.md's early exit landed (2026-09-08).
        pose_args = " ".join(
            ["(S (Z.to_nat {d}))".format(d=dec0), param_names, init_terms,
             primed_names]
            + [f"Hl{k+1}" for k in range(n_lens)]
            + [f"Hreq{k+1}" for k in range(n_reqs)]
            + ["Hfb"]
            + [f"Hini{k+1}" for k in range(n_invs)]
            + ["Heq"])

        fixpoint_txt = f"""Fixpoint {name}_loop (fuel : nat) {pb} {sb} : {tup_ty} :=
  match fuel with
  | O => {tup}
  | S fu =>
      if {guard_b}
      then {name}_loop fu {pargs} {step_terms}
      else {tup}
  end.
"""
        if ret_t == "seq":
            # a seq return is TWO top-level Definitions (gen_plain's own
            # split, same reason: the function+length model has no single
            # Coq value carrying both), each re-destructuring the same
            # loop call; `unfold` below exposes both occurrences of that
            # identical call so one `destruct` in the theorem catches them
            # together (measured, 2026-09-09).
            def_lines = (
                f"Definition {name}_t {pb} : Z -> Z :=\n"
                f"  let '{tup} := {name}_loop (S (Z.to_nat {dec0})) {pargs} "
                f"{init_terms}\n  in {env_post[ret]}.\n\n"
                f"Definition {name}_t_len {pb} : Z :=\n"
                f"  let '{tup} := {name}_loop (S (Z.to_nat {dec0})) {pargs} "
                f"{init_terms}\n  in {env_post[ret + '_len']}.\n")
            unfold_line = f"unfold {name}_t, {name}_t_len."
        else:
            def_lines = (
                f"Definition {name}_t {pb} : {rty(ret_t)} :=\n"
                f"  let '{tup} := {name}_loop (S (Z.to_nat {dec0})) {pargs} "
                f"{init_terms}\n  in {result_term}.\n")
            unfold_line = f"unfold {name}_t."

        return f"""{def_txt}
{fixpoint_txt}
{def_lines}
Lemma {name}_loop_spec :
  forall (fuel : nat) {pb} {sb} {sb_p},
{lemma_hyps}  {dec} < Z.of_nat fuel ->
{inv_hyps}  {name}_loop fuel {pargs} {state_names} = {tup_p} ->
  ({concl}).
Proof.
  induction fuel as [|fu IH];
  intros {param_names} {state_names} {primed_names} {' '.join(hyp_names)};
  cbn [{name}_loop]; t_sweep;
  first [ solve [ apply IH; t_side ]
        | (let Heq := fresh "Heq" in
           intro Heq; inversion Heq; subst; clear Heq; t_dis)
        | fail 1 "unsolved t verification condition" ].
Qed.

Theorem {name}_t_spec :
  forall {pb},
{lens_arrows(cx)}{requires_arrows(cx)}  {ens}.
Proof.
  intros {param_names} {lens_intro} {reqs_intro}.
  {unfold_line}
  destruct ({name}_loop (S (Z.to_nat {dec0})) {pargs} {init_terms})
    as {pat_p} eqn:Heq.
  cbn beta iota.
  assert (Hfb : {dec0} < Z.of_nat (S (Z.to_nat {dec0}))) by lia.
{ini_asserts}  pose proof ({name}_loop_spec {pose_args}) as Hout.
  clear Hfb Heq {ini_intro}.
  t_dis.
Qed.
"""

    # Early exit (SPEC.md, 2026-09-08): w["body"] contains a `return`, so
    # the loop can end two ways, and the Fixpoint's result carries which
    # one happened as a second, bool component ("did this run end via
    # return"). `step_tup`/`step_done` (from exec_straight above) are
    # already the fully-guarded per-iteration outcome: on the branch that
    # returns, step_tup's `ret` component already holds the returned value
    # and every other component is frozen at its pre-step value (dead,
    # since a `true` step_done discards the continuation state below); on
    # the branch that doesn't, step_tup is exactly the old step_terms
    # tuple. So the SAME step_tup feeds both arms of the fixpoint's inner
    # `if`, and no separate "continued" state is ever computed.
    #
    # The induction lemma's conclusion becomes a disjunction on that flag:
    # returned (rflag' = true) owes the task's ensures directly, at the
    # invariant, the guard, and whichever branch condition step_done
    # encodes (never the loop invariant itself, which a `return` explicitly
    # does not owe per SPEC.md); not-returned (rflag' = false) owes exactly
    # the old invariant-preservation/frame conclusion. The final theorem's
    # `if rflag' then ret else <suffix>` collapses to whichever side Hout
    # gives it, via t_dis's own subst/if-reduction, so the true-side
    # obligation there is discharged the moment it lands (it IS the
    # lemma's own true-side conclusion, restated at `ret`'s primed name) --
    # all the actual proof burden sits inside {name}_loop_spec, in the one
    # new goal a `return` adds: closing ensures from raw invariant/guard/
    # branch-condition facts, which can need instantiating a `forall`
    # hypothesis at a witness the file's automation did not need before
    # (see t_go's new arm in PRELUDE, dated the same day).
    step_tup = "(" + ", ".join(step_env[v] for v in svars_x) + ")"
    ret_p = primed[0]
    ens_prime = ensures_text(cx, ret_p)
    rf, rfp = f"{name}_rf", f"{name}_rflag'"
    concl_full = f"(({rfp} = true /\\ {ens_prime}) \\/ ({rfp} = false /\\ ({concl})))"

    pose_args = " ".join(
        ["(S (Z.to_nat {d}))".format(d=dec0), param_names, init_terms,
         primed_names, rf]
        + [f"Hl{k+1}" for k in range(n_lens)]
        + [f"Hreq{k+1}" for k in range(n_reqs)]
        + ["Hfb"]
        + [f"Hini{k+1}" for k in range(n_invs)]
        + ["Heq"])

    return f"""{def_txt}
Fixpoint {name}_loop (fuel : nat) {pb} {sb} : ({tup_ty.removesuffix("%type")} * bool)%type :=
  match fuel with
  | O => ({tup}, false)
  | S fu =>
      if {guard_b}
      then (if {step_done} then ({step_tup}, true) else {name}_loop fu {pargs} {step_terms})
      else ({tup}, false)
  end.

Definition {name}_t {pb} : {rty(ret_t)} :=
  let '({tup}, {rf}) := {name}_loop (S (Z.to_nat {dec0})) {pargs} {init_terms} in
  if {rf} then {ret} else {result_term}.

Lemma {name}_loop_spec :
  forall (fuel : nat) {pb} {sb} {sb_p} ({rfp} : bool),
{lemma_hyps}  {dec} < Z.of_nat fuel ->
{inv_hyps}  {name}_loop fuel {pargs} {state_names} = ({tup_p}, {rfp}) ->
  {concl_full}.
Proof.
  induction fuel as [|fu IH];
  intros {param_names} {state_names} {primed_names} {rfp} {' '.join(hyp_names)};
  cbn [{name}_loop]; t_sweep;
  first [ solve [ apply IH; t_side_ext ]
        | (let Heq := fresh "Heq" in
           intro Heq; inversion Heq; subst; clear Heq; t_dis_ext)
        | fail 1 "unsolved t verification condition" ].
Qed.

Theorem {name}_t_spec :
  forall {pb},
{lens_arrows(cx)}{requires_arrows(cx)}  {ens}.
Proof.
  intros {param_names} {lens_intro} {reqs_intro}.
  unfold {name}_t.
  destruct ({name}_loop (S (Z.to_nat {dec0})) {pargs} {init_terms})
    as [{pat_p} {rf}] eqn:Heq.
  cbn beta iota.
  assert (Hfb : {dec0} < Z.of_nat (S (Z.to_nat {dec0}))) by lia.
{ini_asserts}  pose proof ({name}_loop_spec {pose_args}) as Hout.
  clear Hfb Heq {ini_intro}.
  t_dis_ext.
Qed.
"""


def gen_rec(cx: Ctx, body: list) -> str:
    task = cx.task
    name = task["name"]
    ret = task["returns"][0]["name"]
    ret_t = task["returns"][0]["type"]
    pb, pargs = param_binders(cx)
    default = "false" if ret_t == "bool" else "0"
    assert "decreases" in task, "self-recursive task without decreases"
    measure = cx.zx(task["decreases"], {}, {})

    reqs = [cx.prop(e, {}) for e in task.get("requires", [])]
    local: dict[str, str] = {}
    obls: list = []

    # fuel body: self-calls become {name}_fuel fu
    cx.callpre[name] = f"{name}_fuel fu"
    env0 = {ret: default}
    env = exec_straight(cx, body, env0, local, list(reqs), [], obls)
    body_fuel = env[ret]
    del cx.callpre[name]

    lens = len_hyps(cx)
    n_lens, n_reqs = len(lens), len(reqs)
    lens_reqs = "".join(f"  {h} ->\n" for h in lens + reqs)
    ens_fuel = ensures_text(cx, f"({name}_fuel fuel {pargs})")
    ens = ensures_text(cx, f"({name}_t {pargs})")
    eq_lines = "".join(f"  try rewrite sf_{sf['name']}_eq.\n"
                       for sf in task.get("spec_funs", []))
    hyps = " ".join([f"Hl{k+1}" for k in range(n_lens)]
                    + [f"Hreq{k+1}" for k in range(n_reqs)])

    return f"""Fixpoint {name}_fuel (fuel : nat) {pb} : {rty(ret_t)} :=
  match fuel with
  | O => {default}
  | S fu => {body_fuel}
  end.

Definition {name}_t {pb} : {rty(ret_t)} :=
  {name}_fuel (S (Z.to_nat {measure})) {pargs}.

Lemma {name}_fuel_spec :
  forall (fuel : nat) {pb},
  (Z.to_nat {measure} < fuel)%nat ->
{lens_reqs}  {ens_fuel}.
Proof.
  induction fuel as [|fu IH]; intros {pargs} Hf {hyps};
  [ exfalso; lia | ].
  cbn [{name}_fuel].
{eq_lines}  t_sweep;
  repeat first [ reflexivity
               | solve [ lia ]
               | solve [ apply IH; repeat t_dm1; lia ]
               | (lazymatch goal with |- _ /\\ _ => split end)
               | f_equal ].
  all: fail "unsolved t verification condition".
Qed.

Theorem {name}_t_spec :
  forall {pb},
{lens_arrows(cx)}{requires_arrows(cx)}  {ens}.
Proof.
  intros.
  unfold {name}_t.
  apply ({name}_fuel_spec (S (Z.to_nat {measure})));
  first [ lia | assumption ].
Qed.
"""


# --------------------------------------------------------------------------
# Refutation certificates (ROADMAP 10.7: the ONE door to REFUTED).
#
# When the harness hands a measured twin witness, the twin file is lowered
# as the twin PROGRAM (its definitions, unchanged) plus a single goal named
# t_refutation_certificate: the spec instantiated at the concrete witness,
# negated, proved by ground evaluation inside the kernel (cbv/reflexivity
# equations plus the file's own engine; no vm_compute, no native_compute,
# so the trust story is exactly the adapter's kernel-plus-coqchk one). The
# adapter mints REFUTED if and only if that goal is declared and the kernel
# accepted the file under the full audit discipline. A certificate the
# kernel rejects fails the file and mints UNPROVED, never REFUTED; a
# witness kind this lowering cannot ground (an "undefined" twin, or a
# value twin whose ensures still holds under the totalized seq model)
# yields no certificate and the cell honestly reads verified/unproved.
#
# Witness kinds and their certificate statements:
#   value        ~ (ensures at the concrete input, r := name_t <input>)
#   exit         ~ (forall params state, lens -> requires -> surviving
#                   invariants -> ~guard -> ensures[r := result]),
#                a kernel-checked countermodel to the exit entailment the
#                dropped invariant was carrying
#   preservation the same with the guard positive and the stepped
#                invariants as the conclusion
# --------------------------------------------------------------------------

CERT_NAME = "t_refutation_certificate"

T_FEED = r"""Ltac t_feed H :=
  repeat lazymatch type of H with
  | ?A -> ?B =>
      let D := fresh "t_D" in
      assert (D : A) by t_dis; specialize (H D); clear D
  end.
"""


def _zlit(v) -> str:
    n = int(v)
    return f"({n})" if n < 0 else str(n)


def _glit(v, ty: str) -> str:
    if ty == "bool":
        return "true" if v else "false"
    return _zlit(v)


def _seq_lambda(vals: list) -> str:
    if not vals:
        return "fun _ : Z => 0"
    expr = "0"
    for k in range(len(vals) - 1, -1, -1):
        expr = f"if t_k =? {k} then {_zlit(vals[k])} else ({expr})"
    return f"fun t_k : Z => {expr}"


def _fv(e, bound: set) -> set:
    """Free variables of a t expression."""
    if not isinstance(e, dict):
        return set()
    if "int" in e or "bool" in e:
        return set()
    if "var" in e:
        return set() if e["var"] in bound else {e["var"]}
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        return (_fv(q["lo"], bound) | _fv(q["hi"], bound)
                | _fv(q["body"], bound | {q["var"]}))
    if "ite" in e:
        c = e["ite"]
        return (_fv(c["cond"], bound) | _fv(c["then"], bound)
                | _fv(c["else"], bound))
    if "call" in e:
        out = set()
        for a in e["call"]["args"]:
            out |= _fv(a, bound)
        return out
    out = set()
    for a in e.get("args", []):
        out |= _fv(a, bound)
    return out


def _max_calls(e, known: set, out: list) -> list:
    """Maximal call nodes with every free var in `known`, skipping anything
    under a quantifier (rewrite cannot cross a binder; the engine handles
    those through t_eqs and seeded instantiation instead)."""
    if not isinstance(e, dict):
        return out
    if "call" in e and _fv(e, set()) <= known:
        out.append(e)
        return out
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        _max_calls(q["lo"], known, out)
        _max_calls(q["hi"], known, out)
        return out
    if "ite" in e:
        c = e["ite"]
        for x in (c["cond"], c["then"], c["else"]):
            _max_calls(x, known, out)
        return out
    if "call" in e:
        for a in e["call"]["args"]:
            _max_calls(a, known, out)
        return out
    for a in e.get("args", []):
        _max_calls(a, known, out)
    return out


def _falsified_conjunct(task: dict, body: list, env_py: dict) -> bool:
    """True iff some ensures conjunct evaluates cleanly False at env_py.
    Only then is the certificate's negation TRUE and provable; an Undef
    conjunct proves nothing, because the lowered (totalized-seq) model may
    satisfy it."""
    funs = interp.funs_of(task, body)
    for e in task["ensures"]:
        try:
            if not interp.ev(e, dict(env_py), funs, interp.St()):
                return True
        except Exception:                                   # noqa: BLE001
            continue
    return False


def _seq_witness_pieces(v: str, vals: list):
    """Coq pieces for a concrete seq value `vals` presented as `v` (a param
    OR a loop state var, SPEC.md "Sequences as values (v1)" makes both
    possible): (env entries for v/v_len, the t_w_<v> Definition line, the
    pointwise asserts that seed the engine's own instantiation arms, the
    `set` line giving the witness back a local name so is_var-gated
    saturation steps can see it, and the two spec_args a specialize/apply
    feeds in)."""
    fn = f"t_w_{v}"
    ln = _zlit(len(vals))
    env = {v: fn, v + "_len": ln}
    defline = f"Definition {fn} : Z -> Z := {_seq_lambda(vals)}.\n"
    ptw = [f"  assert (t_p_{v}_{k} : {fn} {k} = {_zlit(x)}) by reflexivity.\n"
           for k, x in enumerate(vals)]
    setline = f"  set ({v} := {fn}) in *.\n"
    return env, defline, ptw, setline, [fn, ln]


def _witness_env(task: dict, witness: dict):
    """(env_py, env_txt, seq_defs, ptw, spec_args) for the params. env_txt
    maps each param (and <seq>_len) to its concrete Coq term; ptw is the
    pointwise-fact asserts that seed the engine's instantiation arms."""
    env_py, env_txt, seq_defs, ptw, sets, spec_args = {}, {}, [], [], [], []
    for p in task["params"]:
        v = p["name"]
        if v not in witness:
            return None
        wv = witness[v]
        if p["type"] == "seq":
            vals = list(wv)
            env_py[v] = vals
            et, defline, ptwl, setl, sargs = _seq_witness_pieces(v, vals)
            env_txt.update(et)
            seq_defs.append(defline)
            ptw += ptwl
            # the engine's saturation arms guard on is_var, and a global
            # constant is not one: give the seq back its name as a local
            sets.append(setl)
            spec_args += sargs
        else:
            env_py[v] = wv
            env_txt[v] = _glit(wv, p["type"])
            spec_args.append(env_txt[v])
    return env_py, env_txt, seq_defs, ptw, sets, spec_args


def _call_asserts(cx, task, body, asts, env_py, env_render, in_hyp=None):
    """assert/rewrite lines computing every ground spec_fun application to
    its kernel-checked literal (cbv; reflexivity), so the closing engine
    never needs deep fuel unfolding."""
    funs = interp.funs_of(task, body)
    known = set(env_render)
    calls: list = []
    for e in asts:
        _max_calls(e, known, calls)
    lines, seen, k = [], set(), 0
    where = f" in {in_hyp}" if in_hyp else ""
    for cnode in calls:
        term = cx.call(cnode, env_render, {})
        if term in seen:
            continue
        seen.add(term)
        try:
            val = interp.ev(cnode, dict(env_py), funs, interp.St())
        except Exception:                                   # noqa: BLE001
            continue
        k += 1
        rt = cx.sfres[cnode["call"]["fun"]]
        lines.append(f"  assert (t_c{k} : {term} = {_glit(val, rt)}) "
                     f"by (cbv; reflexivity).\n")
        lines.append(f"  try rewrite t_c{k}{where}.\n")
    return lines


def _forall_hints(e, env: dict, funs: dict, out: list) -> None:
    """Early exit, twin side (2026-09-09): walk `e` and, for every
    forall/exists it contains, evaluate the quantifier at `env` and record a
    concrete Z witness: for a forall that comes out False, the first index
    that falsifies the body; for an exists that comes out True, the first
    index that satisfies it. is_prime's return-branch obligation needed a
    witness the Ltac side could not find on its own because `t_mod n` is
    not a variable (t_sat1's E-matching only reaches `f x` for var-headed
    `f`); the certificate's own hypotheses carry no candidate Z variable
    to pair a forall against either (params and state are baked in as Z
    LITERALS by `specialize`, per `_witness_env`/`_glit`, not left as
    variables), so t_go_ext's pairing search has nothing to try. This walk
    computes the missing candidate directly, the same way `interp.py`
    itself would decide the witness was valid in the first place: a bounded
    scan of a concrete range, not a proof search. Best-effort throughout
    (Undef/Budget/anything else is silently skipped): a hint that fails to
    compute costs nothing, since the certificate's own kernel-checked
    closing tactic is what actually has to accept whatever it is paired
    with; a wrong or missing hint just leaves the goal unproved, same as
    before this walk existed."""
    if not isinstance(e, dict):
        return
    if "forall" in e or "exists" in e:
        kind = "forall" if "forall" in e else "exists"
        q = e[kind]
        try:
            lo = interp.ev(q["lo"], env, funs, interp.St())
            hi = interp.ev(q["hi"], env, funs, interp.St())
            want = kind == "exists"
            for i in range(lo, hi):
                sub = dict(env)
                sub[q["var"]] = i
                if bool(interp.ev(q["body"], sub, funs, interp.St())) == want:
                    out.append(i)
                    break
        except Exception:                                   # noqa: BLE001
            pass
        _forall_hints(q["lo"], env, funs, out)
        _forall_hints(q["hi"], env, funs, out)
        return                      # q["body"]'s free var is bound, not env
    if "ite" in e:
        c = e["ite"]
        _forall_hints(c["cond"], env, funs, out)
        _forall_hints(c["then"], env, funs, out)
        _forall_hints(c["else"], env, funs, out)
        return
    if "call" in e:
        for a in e["call"]["args"]:
            _forall_hints(a, env, funs, out)
        return
    for a in e.get("args", []):
        _forall_hints(a, env, funs, out)


def _plain_def(cx, task, body):
    ret = task["returns"][0]["name"]
    ret_t = task["returns"][0]["type"]
    if ret_t == "seq":
        # _value_cert (the only caller that uses this def_text) abstains on
        # a seq return outright; matched here so this never builds a
        # def_text no caller can use.
        return None
    pb, _ = param_binders(cx)
    local: dict = {}
    env0 = {ret: "false" if ret_t == "bool" else "0"}
    env = exec_straight(cx, body, env0, local, None, [], [])
    return (f"Definition {task['name']}_t {pb} : {rty(ret_t)} := "
            f"{env[ret]}.\n")


def _rec_def(cx, task, body):
    name = task["name"]
    ret = task["returns"][0]["name"]
    ret_t = task["returns"][0]["type"]
    pb, pargs = param_binders(cx)
    default = "false" if ret_t == "bool" else "0"
    if "decreases" not in task:
        return None
    measure = cx.zx(task["decreases"], {}, {})
    cx.callpre[name] = f"{name}_fuel fu"
    local: dict = {}
    env = exec_straight(cx, body, {ret: default}, local, None, [], [])
    body_fuel = env[ret]
    del cx.callpre[name]
    return (f"Fixpoint {name}_fuel (fuel : nat) {pb} : {rty(ret_t)} :=\n"
            f"  match fuel with\n"
            f"  | O => {default}\n"
            f"  | S fu => {body_fuel}\n"
            f"  end.\n\n"
            f"Definition {name}_t {pb} : {rty(ret_t)} :=\n"
            f"  {name}_fuel (S (Z.to_nat {measure})) {pargs}.\n")


def _loop_def(cx, task, prefix, w, suffix):
    """The twin loop's Fixpoint + Definition (no lemmas), plus the pieces a
    loop certificate needs. Mirrors gen_loop's construction with the
    definedness collection off."""
    name = task["name"]
    ret = task["returns"][0]["name"]
    ret_t = task["returns"][0]["type"]
    pb, pargs = param_binders(cx)
    local: dict = {}
    if ret_t == "seq":
        env0 = {ret: "(fun _ : Z => 0)", ret + "_len": "0"}
    else:
        env0 = {ret: "false" if ret_t == "bool" else "0"}
    env_pre = exec_straight(cx, prefix, env0, local, None, [], [])
    svars = [ret] + [s["var"]["name"] for s in prefix if "var" in s]
    stys = {v: (local.get(v) or cx.tys[v]) for v in svars}
    # the SAME seq-slot expansion gen_loop uses (seq_slots/slot_owner),
    # since a certificate's twin loop is the same Fixpoint shape.
    svars_x, slot_ty = seq_slots(svars, stys)
    id_env = {v: v for v in svars_x}
    guard_b = cx.bx(w["cond"], id_env, local)
    step_env = exec_straight(cx, w["body"], id_env, dict(local), None, [], [])
    env_post = exec_straight(cx, suffix, id_env, dict(local), None, [], [])
    dec0 = cx.zx(w["decreases"], {v: env_pre[v] for v in svars_x}, local)
    init_terms = " ".join(env_pre[v] for v in svars_x)
    step_terms = " ".join(step_env[v] for v in svars_x)
    # parenthesize a seq slot's "Z -> Z" before joining with `*` (gen_loop's
    # own fix, same reason: "->" binds looser than "*" in Coq's grammar).
    tup_ty = "(" + " * ".join(
        f"({slot_ty[v]})" if "->" in slot_ty[v] else slot_ty[v]
        for v in svars_x) + ")%type"
    tup = "(" + ", ".join(svars_x) + ")"
    sb = " ".join(f"({v} : {slot_ty[v]})" for v in svars_x)
    fixpoint_txt = f"""Fixpoint {name}_loop (fuel : nat) {pb} {sb} : {tup_ty} :=
  match fuel with
  | O => {tup}
  | S fu =>
      if {guard_b}
      then {name}_loop fu {pargs} {step_terms}
      else {tup}
  end.
"""
    if ret_t == "seq":
        def_lines = (
            f"Definition {name}_t {pb} : Z -> Z :=\n"
            f"  let '{tup} := {name}_loop (S (Z.to_nat {dec0})) {pargs} "
            f"{init_terms}\n  in {env_post[ret]}.\n\n"
            f"Definition {name}_t_len {pb} : Z :=\n"
            f"  let '{tup} := {name}_loop (S (Z.to_nat {dec0})) {pargs} "
            f"{init_terms}\n  in {env_post[ret + '_len']}.\n")
    else:
        def_lines = (
            f"Definition {name}_t {pb} : {rty(ret_t)} :=\n"
            f"  let '{tup} := {name}_loop (S (Z.to_nat {dec0})) {pargs} "
            f"{init_terms}\n  in {env_post[ret]}.\n")
    text = fixpoint_txt + "\n" + def_lines
    return text, dict(svars=svars, svars_x=svars_x, stys=stys,
                      slot_ty=slot_ty, id_env=id_env, local=local,
                      step_env=step_env, env_post=env_post, sb=sb)


def _value_cert(cx, task, body, witness, def_text):
    """Certificate chunk for a whole-program value witness, or None."""
    name = task["name"]
    ret = task["returns"][0]["name"]
    ret_t = task["returns"][0]["type"]
    if not task["params"]:
        return None
    if ret_t == "seq":
        # A "value" witness kind's `_twin` is a single Python value
        # (`_glit`'s int/bool contract); a seq twin value is a tuple, which
        # would need the SAME two-slot (function, length) treatment the
        # real return already gets in gen_plain/gen_loop, plus a seq-
        # extensional `stmt`. No committed task needs it yet (swap's twin
        # is an "undefined" witness, `_undef_cert` below; reverse's is
        # "exit", `_loop_cert`), so this abstains rather than guessing.
        return None
    got = _witness_env(task, witness)
    if got is None:
        return None
    env_py, env_txt, seq_defs, ptw, sets, _ = got
    tv = witness.get("_twin")
    if tv == "no value":
        # the lowered twin returns the type's default on that path
        tv = False if ret_t == "bool" else 0
    if not isinstance(tv, (int, bool)):
        return None
    env_py[ret] = tv
    if not _falsified_conjunct(task, body, env_py):
        return None
    gargs = []
    for p in task["params"]:
        if p["type"] == "seq":
            gargs += [env_txt[p["name"]], env_txt[p["name"] + "_len"]]
        else:
            gargs.append(env_txt[p["name"]])
    applied = f"({name}_t {' '.join(gargs)})"
    env_stmt = dict(env_txt)
    env_stmt[ret] = applied
    stmt = " /\\ ".join(cx.prop(e, env_stmt) for e in task["ensures"])
    retlit = _glit(tv, ret_t)
    env_lit = dict(env_txt)
    env_lit[ret] = retlit
    lines = []
    if any(ret in _fv(e, set()) for e in task["ensures"]):
        lines.append(f"  assert (t_out : {applied} = {retlit}) "
                     f"by (cbv; reflexivity).\n")
        lines.append("  rewrite t_out.\n")
    lines += _call_asserts(cx, task, body, task["ensures"], env_py, env_lit)
    lines += sets
    return ("".join(seq_defs) + "\n" + def_text + "\n"
            f"(* The spec fails at the measured witness, "
            f"{harness.witness(witness)}: the kernel evaluates the twin "
            f"there and accepts the negation. *)\n"
            f"Theorem {CERT_NAME} :\n"
            f"  ~ ({stmt}).\n"
            "Proof.\n"
            + "".join(ptw) + "".join(lines) +
            "  t_dis.\n"
            "Qed.\n")


def _loop_cert(cx, task, prefix, w, suffix, witness):
    """Certificate chunk for an invariant-drop loop-state witness, or
    None."""
    kind = witness.get("_kind")
    ret = task["returns"][0]["name"]
    ret_t = task["returns"][0]["type"]
    def_text, L = _loop_def(cx, task, prefix, w, suffix)
    svars, stys = L["svars"], L["stys"]
    id_env, local = L["id_env"], L["local"]
    for v in svars:
        if v not in witness:
            return None
    pb, _ = param_binders(cx)
    invs = [cx.prop(e, id_env, local) for e in w.get("invariants", [])]
    guard_p = cx.prop(w["cond"], id_env, local)
    inv_arrows = "".join(f"  {p} ->\n" for p in invs)
    if kind == "exit":
        guard_arrow = f"  (~ {guard_p}) ->\n"
        if ret_t == "seq":
            concl = ensures_text(cx, {ret: L["env_post"][ret],
                                      ret + "_len": L["env_post"][ret + "_len"]})
        else:
            concl = ensures_text(cx, L["env_post"][ret])
        concl_asts = task["ensures"]
    elif kind == "preservation":
        if not w.get("invariants"):
            return None
        guard_arrow = f"  {guard_p} ->\n"
        concl = " /\\ ".join(cx.prop(e, L["step_env"], local)
                             for e in w.get("invariants", []))
        concl_asts = []
    else:
        return None
    got = _witness_env(task, witness)
    if got is None:
        return None
    env_py, env_g, seq_defs, ptw, sets, spec_args = got
    for v in svars:
        if v in env_py:
            return None            # a state var shadowing a param
        if stys[v] == "seq":
            vals = list(witness[v])
            env_py[v] = vals
            et, defline, ptwl, setl, sargs = _seq_witness_pieces(v, vals)
            env_g.update(et)
            seq_defs.append(defline)
            ptw += ptwl
            sets.append(setl)
            spec_args += sargs
        else:
            env_py[v] = witness[v]
            env_g[v] = _glit(witness[v], stys[v])
            spec_args.append(env_g[v])
    lines = []
    if kind == "exit" and not suffix:
        # ground the spec_fun applications of the instantiated conclusion
        lines = _call_asserts(cx, task, task["body"], concl_asts,
                              env_py, dict(env_g), in_hyp="t_H")
    # Early exit, twin side (2026-09-09): a return-bearing loop's ensures
    # can carry a forall/exists over a non-seq predicate (is_prime's
    # `forall d, 2 <= d < n -> n mod d <> 0`), and unlike the real
    # lowering's loop_spec, this certificate has no loop-state VARIABLE to
    # pair such a forall against: `specialize` bakes params and state in
    # as Z literals (`_witness_env`/`_glit`), so t_go_ext's own pairing
    # search (a forall hypothesis times a `y : Z` in context) finds no
    # candidate. `pose`ing each `_forall_hints` witness gives it one:
    # `match goal with y : Z |- _ => ...` matches a let-bound local
    # definition the same as a plain hypothesis (measured), and `lia`
    # sees straight through the let-binding to the literal, but a `pose`
    # carries no separate EQUALITY hypothesis for t_base's own `subst`
    # catch-all to consume. `remember` was tried first and measured
    # broken: it also introduces the value as `y : Z`, but as a genuine
    # equation (`t_wit0 = 2`), and t_inv1's `| _ => progress subst` (the
    # last, catch-all arm t_base falls to before t_sat1/t_dm1/t_split1 get
    # a turn) eliminates it immediately, before t_leaf_ext's pairing search
    # ever runs, leaving no `y : Z` candidate at all. `t_dis_ext` (not
    # plain `t_dis`) is then needed to actually try the pairing. Confined
    # to return-bearing loops (has_return), so a loop task with no
    # `return` gets neither the hint search nor the closer swap and its
    # twin is untouched byte-for-byte.
    wit_lines = ""
    closer = "t_dis"
    if has_return(w["body"]):
        funs = interp.funs_of(task, task["body"])
        hints: list = []
        for e in concl_asts:
            _forall_hints(e, dict(env_py), funs, hints)
        if kind == "preservation":
            for e in w.get("invariants", []):
                _forall_hints(e, dict(env_py), funs, hints)
        seen_h: set = set()
        for k, v in enumerate(hints):
            if v in seen_h:
                continue
            seen_h.add(v)
            wit_lines += f"  pose (t_wit{k} := ({_zlit(v)})%Z).\n"
        if wit_lines:
            closer = "t_dis_ext"
    return ("".join(seq_defs) + "\n" + def_text + "\n"
            f"(* The surviving loop annotations do not carry the spec: a "
            f"kernel-checked countermodel at the measured state, "
            f"{harness.witness(witness)}. *)\n"
            f"Theorem {CERT_NAME} :\n"
            f"  ~ (forall {pb} {L['sb']},\n"
            f"{lens_arrows(cx)}{requires_arrows(cx)}{inv_arrows}"
            f"{guard_arrow}"
            f"  {concl}).\n"
            "Proof.\n"
            + "".join(ptw) +
            "  intro t_H.\n"
            f"  specialize (t_H {' '.join(spec_args)}).\n"
            + "".join(lines) + "".join(sets) +
            "  t_feed t_H.\n"
            + wit_lines
            + f"  {closer}.\n"
            "Qed.\n")


def _first_undef(e, env: dict, funs: dict):
    """Walk `e` in interp.ev's own left-to-right/short-circuit order
    (SPEC.md "Definedness"); return the Coq NEGATION text of the first
    at/update/fill/div/mod bound it reaches that fails, concretely
    evaluated at `env` (params/state already bound to Python literals,
    interp.py's own representation), or None if `e` evaluates cleanly.
    `env` is not mutated. Used by `_undef_cert`, below, for an "undefined"
    witness kind (interp.py's Reference.witness caught an Undef evaluating
    the twin): SPEC.md's definedness is exactly what this file's own
    model does NOT enforce by construction (t_upd/t_fill/t_div/t_mod are
    all TOTAL Rocq functions, the same reason `at`'s own totality proves
    nothing about t's undefinedness, PRELUDE's own comment), so a
    certificate about an undefined witness cannot be a fact about the
    twin's VALUE (there is none); it is a fact about the specific bound
    the witness violates, replayed the same way interp.ev discovered it."""
    if not isinstance(e, dict):
        return None
    if "int" in e or "bool" in e or "var" in e:
        return None
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        r = _first_undef(q["lo"], env, funs)
        if r is not None:
            return r
        r = _first_undef(q["hi"], env, funs)
        if r is not None:
            return r
        lo = interp.ev(q["lo"], env, funs, interp.St())
        hi = interp.ev(q["hi"], env, funs, interp.St())
        for i in range(lo, hi):
            sub = dict(env)
            sub[q["var"]] = i
            r = _first_undef(q["body"], sub, funs)
            if r is not None:
                return r
        return None
    if "ite" in e:
        c = e["ite"]
        r = _first_undef(c["cond"], env, funs)
        if r is not None:
            return r
        cond = interp.ev(c["cond"], env, funs, interp.St())
        return _first_undef(c["then"] if cond else c["else"], env, funs)
    if "call" in e:
        for a in e["call"]["args"]:
            r = _first_undef(a, env, funs)
            if r is not None:
                return r
        return None
    op = e["op"]
    if op == "and":
        for a in e["args"]:
            r = _first_undef(a, env, funs)
            if r is not None:
                return r
            if not interp.ev(a, env, funs, interp.St()):
                break
        return None
    if op == "or":
        for a in e["args"]:
            r = _first_undef(a, env, funs)
            if r is not None:
                return r
            if interp.ev(a, env, funs, interp.St()):
                break
        return None
    if op == "implies":
        a, b = e["args"]
        r = _first_undef(a, env, funs)
        if r is not None:
            return r
        if interp.ev(a, env, funs, interp.St()):
            return _first_undef(b, env, funs)
        return None
    if op in ("at", "update"):
        s_e, i_e = e["args"][0], e["args"][1]
        r = _first_undef(s_e, env, funs)
        if r is not None:
            return r
        r = _first_undef(i_e, env, funs)
        if r is not None:
            return r
        s = interp.ev(s_e, env, funs, interp.St())
        i = interp.ev(i_e, env, funs, interp.St())
        if not (0 <= i < len(s)):
            return f"~ (0 <= {_zlit(i)} /\\ {_zlit(i)} < {_zlit(len(s))})"
        if op == "update":
            return _first_undef(e["args"][2], env, funs)
        return None
    if op == "fill":
        n_e, v_e = e["args"]
        r = _first_undef(n_e, env, funs)
        if r is not None:
            return r
        n = interp.ev(n_e, env, funs, interp.St())
        if n < 0:
            return f"~ ({_zlit(n)} >= 0)"
        return _first_undef(v_e, env, funs)
    if op in ("div", "mod"):
        a_e, b_e = e["args"]
        r = _first_undef(a_e, env, funs)
        if r is not None:
            return r
        r = _first_undef(b_e, env, funs)
        if r is not None:
            return r
        y = interp.ev(b_e, env, funs, interp.St())
        if y == 0:
            return "~ (0 <> 0)"
        return None
    for a in e.get("args", []):
        r = _first_undef(a, env, funs)
        if r is not None:
            return r
    return None


def _first_undef_body(stmts, env: dict, funs: dict):
    """Statement-level counterpart of `_first_undef`: walk a straight-
    line/if body in interp.exec_body's own order, mutating `env` exactly
    as it would, stopping at the first at/update/fill/div/mod bound that
    fails. Best-effort: a `while` (no committed task's "undefined" witness
    needs one, swap's mutant is straight-line) or anything else this does
    not recognize returns None, which `_undef_cert` reads as "cannot
    ground this one," the same honest abstention as every other opportunistic
    certificate builder here."""
    for s in stmts:
        if "assign" in s or "return" in s or "var" in s:
            if "assign" in s:
                v, e = s["assign"]
            elif "return" in s:
                v, e = s["return"]
            else:
                v, e = s["var"]["name"], s["var"]["init"]
            r = _first_undef(e, env, funs)
            if r is not None:
                return r
            env[v] = interp.ev(e, env, funs, interp.St())
            if "return" in s:
                return None
        elif "if" in s:
            c = s["if"]
            r = _first_undef(c["cond"], env, funs)
            if r is not None:
                return r
            cond = interp.ev(c["cond"], env, funs, interp.St())
            r = _first_undef_body(c["then"] if cond else c["else"], env, funs)
            if r is not None:
                return r
        else:
            return None            # "while": not needed by any committed
                                    # task's "undefined" witness yet
    return None


def _undef_cert(cx, task, body, witness):
    """Certificate chunk for an "undefined" witness kind (interp.py's
    Reference.witness caught an Undef evaluating the twin body), or None.
    SPEC.md's definedness rules are exactly what makes an out-of-range
    `at`/`update`, a negative `fill` length, or a zero `div`/`mod`
    divisor a t-level obligation the REAL lowering owes and the TWIN
    fails; nothing about the twin's totalized-in-Rocq VALUE at the
    witness is at stake, since t_upd/t_fill/t_div/t_mod are all total
    (PRELUDE's own comment). What is certified is the concrete bound
    itself, at the measured witness, by pure computation: `_first_undef`
    replays the twin body the same way interp.py found the witness in the
    first place (a bounded evaluation, not a proof search) and returns
    the negation of the first bound it fails; `lia` closes it on
    literals. Self-contained: no reference to `{name}_t` at all, so no
    def_text/Fixpoint is needed."""
    if not task["params"]:
        return None
    env_py: dict = {}
    for p in task["params"]:
        v = p["name"]
        if v not in witness:
            return None
        env_py[v] = tuple(witness[v]) if p["type"] == "seq" else witness[v]
    prefix, w, suffix = find_while(body)
    if w is not None:
        return None            # not needed by any committed task yet
    funs = interp.funs_of(task, body)
    fact = _first_undef_body(body, env_py, funs)
    if fact is None:
        return None
    return (
        f"(* The twin's own evaluation is undefined at the measured "
        f"witness, {harness.witness(witness)}: {witness.get('_twin')}. "
        f"SPEC.md's definedness rules make this the real lowering's "
        f"obligation and the twin's failure; this certifies that specific "
        f"bound's negation, at the concrete witness, by computation. *)\n"
        f"Theorem {CERT_NAME} :\n"
        f"  {fact}.\n"
        "Proof.\n"
        "  lia.\n"
        "Qed.\n")


def _try_cert_v1(task: dict, body: list, witness: dict):
    """Full certificate FILE for a v1 twin, or None. Opportunistic: any
    reason it cannot be built (an unsupported witness kind, an ensures the
    totalized model satisfies, an internal error) falls back to the normal
    lowering, whose failing proof reads UNPROVED. Losing a flip to honesty
    is the intended price; only a faked one is a failure."""
    try:
        wk = witness.get("_kind")
        if wk not in ("value", "exit", "preservation", "undefined"):
            return None
        cx = Ctx(task)
        prefix, w, suffix = find_while(body)
        selfrec = has_self_call(body, task["name"])
        if w is not None and selfrec:
            return None
        chunk = None
        if wk == "undefined":
            chunk = _undef_cert(cx, task, body, witness)
        elif wk in ("exit", "preservation"):
            if w is None:
                return None
            chunk = _loop_cert(cx, task, prefix, w, suffix, witness)
        else:
            if w is not None:
                def_text, _ = _loop_def(cx, task, prefix, w, suffix)
            elif selfrec:
                def_text = _rec_def(cx, task, body)
            else:
                def_text = _plain_def(cx, task, body)
            if def_text is not None:
                chunk = _value_cert(cx, task, body, witness, def_text)
        if chunk is None:
            return None
        parts = [header(), emit_spec_funs(cx), POST_SF + "\n", T_FEED, chunk,
                 f"\nPrint Assumptions {CERT_NAME}.\n"]
        return "\n".join(p for p in parts if p)
    except Exception:                                       # noqa: BLE001
        return None


def _subst_ints(e, sub: dict):
    if not isinstance(e, dict):
        return e
    if "var" in e:
        v = e["var"]
        return {"int": sub[v]} if v in sub else e
    out = {}
    for k, val in e.items():
        if isinstance(val, dict):
            out[k] = _subst_ints(val, sub)
        elif isinstance(val, list):
            out[k] = [_subst_ints(x, sub) for x in val]
        else:
            out[k] = val
    return out


def _v0_cert(task: dict, body: list, witness: dict):
    """Full certificate FILE for a v0 twin, or None (same contract as
    _try_cert_v1; v0 is all-Z, so the closer is plain lia on literals)."""
    try:
        if witness.get("_kind") != "value" or not task["params"]:
            return None
        if any(p["type"] != "int" for p in task["params"]):
            return None
        if task["returns"][0]["type"] != "int":
            return None
        name = task["name"]
        ret = task["returns"][0]["name"]
        tv = witness.get("_twin")
        if tv == "no value":
            tv = 0
        if not isinstance(tv, int) or isinstance(tv, bool):
            return None
        env_py = {p["name"]: witness[p["name"]] for p in task["params"]}
        env_py[ret] = tv
        if not _falsified_conjunct(task, body, env_py):
            return None
        expr = body_expr0(body, ret)
        lits = " ".join(_zlit(witness[p["name"]]) for p in task["params"])
        applied = f"({name}_t {lits})"
        sub = {p["name"]: witness[p["name"]] for p in task["params"]}
        post = " /\\ ".join(prop0(_subst_ints(e, sub), applied, ret)
                            for e in task["ensures"])
        binder = " ".join(f"({p['name']} : Z)" for p in task["params"])
        rew = ""
        if any(ret in _fv(e, set()) for e in task["ensures"]):
            rew = (f"  assert (t_out : {applied} = {_zlit(tv)}) "
                   f"by (cbv; reflexivity).\n"
                   f"  rewrite t_out.\n")
        return (
            "From Stdlib Require Import ZArith Lia.\n"
            "Open Scope Z_scope.\n\n"
            f"Definition {name}_t {binder} : Z := {expr}.\n\n"
            f"(* The spec fails at the measured witness, "
            f"{harness.witness(witness)}: the kernel evaluates the twin "
            f"there and accepts the negation. *)\n"
            f"Theorem {CERT_NAME} :\n"
            f"  ~ ({post}).\n"
            "Proof.\n" + rew +
            "  lia.\n"
            "Qed.\n\n"
            f"Print Assumptions {CERT_NAME}.\n")
    except Exception:                                       # noqa: BLE001
        return None


# `witness` is the twin's measured witness (harness.twin_cached). Twin call
# sites pass it; when a certificate can ground it, the twin file carries
# t_refutation_certificate instead of an unprovable spec theorem.
def lower(task: dict, body: list, witness: dict | None = None) -> str:
    if task.get("t") == 0:
        return lower_v0(task, body, witness=witness)
    return lower_v1(task, body, witness=witness)


if __name__ == "__main__":
    raise SystemExit(harness.run_all(sys.argv[1:], lower, rocq_backend, "v"))
