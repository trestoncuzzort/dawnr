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

  SEQUENCES: LITERALS, CONCATENATION, SLICES (2026-09-09, SPEC.md
  "Sequences: literals, concatenation, slices (v1)", ROADMAP 12.7, the
  wave right after "Sequences as values" above). Three new expressions:
  `seq` (the literal `[e1, ..., en]`, n >= 0, `[]` the empty seq), `+` on
  two seqs (concatenation, the SAME token as int `+`, polymorphic by
  operand type exactly as `==` already is), and `slice` (`s[a..b]`,
  DEFINED IFF `0 <= a <= b <= len(s)`).

  REPRESENTATION. Still the function+length pair; no new representation
  decision needed, only two more operators in it and one that needs none
  at all. `t_app f g n := fun k => if k <? n then f k else g (k - n)` and
  `t_slice f a := fun k => f (a + k)` are opaque top-level Definitions,
  the SAME shape t_upd/t_fill/t_div/t_mod already have (never Notations,
  so cbn's whitelisted delta never unfolds them; TOTAL in Rocq, so
  totality proves nothing about t's own undefinedness, carried entirely by
  defs()'s own obligations). The LITERAL gets no opaque Definition of its
  own at all: since a literal's arity n is always a concrete Python int at
  lowering time (the AST node has exactly that many arguments, never a
  symbolic count), `seq_fn` builds it as a chain of `t_upd` over `t_fill
  0` (index 0 first, ..., n - 1 last; `[]` is bare `t_fill 0` at length
  0), reusing t_upd/t_fill and their reading tactics VERBATIM. This is the
  cheapest possible design: zero new PRELUDE surface for the operator the
  census measures as most common (27 of 643 gradable DafnyBench programs
  start a sequence from `[]`; a literal is needed by 8,599 of the 24,748
  nl/ problems), riding entirely on machinery "Sequences as values"
  already proved out on swap's nested update.

  TACTICS. `t_app_case` mirrors `t_upd_case`'s three-branch shape (try
  `k < n` directly by lia, try `n <= k` directly by lia, else split on
  `k <? n` and recurse): it has no `is_var` guard on `f`/`g` (t_upd_case's
  own precedent), so it fires on a NESTED t_app/t_upd exactly as
  t_upd_case already does on a nested update, one layer per case split,
  until the innermost function is `t_fill` (t_fill_get) or a bare
  param/state variable (t_sat1's existing merge/E-matching arms).
  `t_slice` needs no case split at all: SPEC.md's own definition is an
  unconditional index shift, so `t_slice_get` is a bare rewrite, the same
  shape `t_fill_get` already has. Both join t_inv1's match, goal and
  hypothesis position, immediately after t_upd/t_fill's own entries.

  DEFINEDNESS. `seq` (the literal) and `+` (concatenation) add no
  obligation of their own: SPEC.md says a literal is defined iff every
  element is and a concatenation iff both operands are, which is exactly
  what falling through to `defs()`'s existing generic per-argument
  recursion already gives, so those two cost nothing new in the *_def_k
  lemma calculus. `slice` is the one that costs something: every `slice`
  node emits `(0 <= a <= b <= len(s))` as its own lemma, in the same
  calculus as `at`'s `(0 <= idx < len)`, one more `Lemma <name>_def_k` per
  slice site the caller's requires/invariants/earlier ensures must make
  provable. `_first_undef` (the twin certificate side) gets the matching
  case, replaying interp.ev's own bound at the concrete witness and
  returning its negation; `seq`/`+` again need no case of their own there,
  falling to the existing generic per-argument walk, which already visits
  arguments in interp.ev's own left-to-right order.

  MEASURED (2026-09-09, coqc 9.2.0, this box, tasks/tail.json and
  tasks/filter_pos.json, both real vs twin). tail (loop-free: `r :=
  s[1..len(s)]`) reads real VERIFIED (0.54 s) / twin REFUTED (0.51 s): the
  twin ladder's only body-level OFF-BY-ONE candidate is the slice's own
  literal `1`, and the chosen mutant (`s[2..len(s)]`) is UNDEFINED at the
  measured witness s=[0] (slice bounds [2..1] outside `0 <= a <= b <=
  1`), so the twin's certificate is `_undef_cert` extended with this
  file's new `slice` case in `_first_undef`, no def_text, no reference to
  `tail_t` at all, the same shape swap's own undefined witness already
  established. filter_pos (a loop appending `r := r + [s[i]]` under `if
  s[i] > 0`) reads real VERIFIED (0.69 s) / twin REFUTED (0.52 s): the
  chosen mutant is invariant-drop#1 (dropping `0 <= i`, the first
  invariant), an "exit" witness at s=[], i=1, r=[1] (a state the surviving
  invariants and the negated guard admit but the task's own ensures does
  not), so the twin's certificate is `_loop_cert`'s EXISTING machinery,
  unmodified: the concatenation and literal inside the loop body only
  ever reach `seq_fn`, never a new code path in the certificate builders
  themselves. Neither committed task exercises `t_app_case`'s nested-
  update-shaped recursion or a literal with more than one element, so
  those remain measured only by construction (the same proof shape
  t_upd_case already carries, re-timed) and the fuzz family SPEC.md names
  (v1seqops), not yet run.

  swap and reverse (out/agent-rocq-seqops/{swap,reverse}{,_twin}.v vs the
  out/{swap,reverse}{,_twin}.v this file's PRIOR run produced, diffed with
  `diff`, not literal `cmp`): all four files gain ONLY this date's PRELUDE
  block (t_app/t_slice + t_app_case/t_slice_get, 73 inserted lines, zero
  deleted, at the same point in each file, right after t_upd_case),
  exactly the "pure insertions, no deletions" shape the 2026-09-09
  "Sequences as values" note above already established for first_even/
  digit_sum/seq_max when t_upd/t_fill first landed; outside that shared,
  file-wide PRELUDE growth every byte is unchanged, since neither task's
  body reaches `seq`, `+`, or `slice`. Both still read COUNTS (rc=0,
  swap.v 0.57 s / swap_twin.v 0.54 s, reverse.v 0.68 s / reverse_twin.v
  0.55 s), matching their prior measurement.

  THE RESIDUAL: seq `==`/`!=` IN COMPUTATIONAL POSITION (2026-09-09).
  EQUALITY, above, only ever put seq `==`/`!=` in Prop position (`prop()`'s
  extensional forall); `bx()` abstained on the same operator in a
  computational `if`/loop-guard position ("no Fixpoint walks a symbolic
  length to compute a bool"). `t_seq_eqb (n : Z) (f g : Z -> Z) : bool`
  (PRELUDE, joins t_upd/t_fill/t_app/t_slice/t_div/t_mod's own opaque-
  Definition-plus-reading-tactic shape) closes it: a Fixpoint over
  `Z.to_nat n` (an auxiliary `t_seq_eqb_nat` indexed by nat and folded with
  `andb`/`Z.eqb`, the SAME fuel-over-`Z.to_nat` idiom this file's loop and
  recursion Fixpoints already use), proved correct by `t_seq_eqb_spec :
  t_seq_eqb n f g = true <-> (forall k, 0 <= k < n -> f k = g k)`
  unconditionally (n < 0 makes both sides vacuously true, so no `0 <= n`
  side condition is needed) via one auxiliary induction lemma,
  `t_seq_eqb_nat_spec`. `bx()` now lowers `s == t` to `(len s =? len t) &&
  t_seq_eqb (len s) s t` (negated by `negb` for `!=`), the length check
  first since `t_seq_eqb`'s own length argument is only meaningful once the
  two seqs actually match; the proof side reads it back with
  `t_seq_eqb_case` (PRELUDE), joined into t_inv1's match immediately after
  `t_slice`'s own two entries, goal and hypothesis position: an
  unconditional two-way split via `Sumbool.sumbool_of_bool` (no "try
  directly by lia" shortcut, unlike t_ltb_case/t_eqb_case, since whether two
  whole seqs agree is not lia-decidable from raw context), `replace ... in
  *` rewriting every occurrence the same way every other case-split tactic
  here does, `t_seq_eqb_spec` turning the true branch into a `forall k, ...`
  fact for `t_sat1`'s existing E-matching arms and the false branch into
  that fact's negation via the iff's contrapositive, so the false-branch
  case closes by the same `H : A -> False, D : A |- _` resolution `t_sat1`
  already has for every other implication hypothesis. One sharp edge, found
  by compiling a standalone PRELUDE probe before touching this file: `Ltac
  name args := ... assert (F : ...) by (intro H; ...H...)` (singular
  `intro`) fails to elaborate ("H was not found") when `H` is later
  referenced inside the SAME `by`-clause, reproduced in isolation down to
  zero Ltac arguments (coqc 9.2.0, this box); `intros H` (plural) does not
  have this bug, so `t_seq_eqb_case`'s false-branch assert uses `intros Hc`
  rather than the `intro Heq` singular form the file's generated (not
  hand-written PRELUDE) proof text uses elsewhere without incident.

  MEASURED (2026-09-09, coqc 9.2.0, this box, harness.run_task, `verifiers.
  rocq`). A scratch probe (not committed to tasks/: params s, t : seq,
  requires len(s) == len(t), body `if s == t then r := 1 else r := 0`,
  ensures `r == 1 <-> (forall k, 0 <= k < len(s) -> s[k] == t[k])`) reads
  COUNTS in out/agent-rocq-seqeq/ (real VERIFIED, collapse-if twin REFUTED,
  witness s=[0], t=[1]: real returns 0, the twin that drops the `if` and
  always takes the then-branch returns 1), 2.5 s total. The six-task
  regression (swap, reverse, tail, filter_pos, seq_max, is_prime; none of
  whose bodies use seq `==`/`!=` in computational position, all of whose
  ENSURES already used the extensional `prop()` form before this change)
  reads COUNTS unchanged in out/agent-rocq-seqeq/, matching AGREEMENT.md's
  rocq column exactly: swap 3.6 s, reverse 3.7 s, tail 2.6 s, filter_pos
  3.1 s, seq_max 77.2 s, is_prime 6.6 s, all inside the 180 s budget. Every
  file in that six-task set gains ONLY this date's PRELUDE block (105
  inserted lines, zero deleted: the 103-line t_seq_eqb block plus one line
  each for its two t_inv1 match-arm entries), at the same three points in
  every file (diffed against out/swap.v and out/is_prime.v, this file's
  PRIOR run), the same "pure insertions, no deletions" shape every PRELUDE
  growth this file has made all carries; source outside that shared block
  is byte-identical, since none of the six reaches `==`/`!=` on a seq in
  computational position.

  PAIRS (v1) (2026-09-10, SPEC.md "Pairs (v1)", ROADMAP 12.7, the wave
  right after strings). New type `{"pair": [T1, T2]}`, T1/T2 each "int",
  "bool" or "seq"; new Expr forms `pair`/`fst`/`snd`. Two committed tasks:
  divmod_pair (loop-free, `r := (x div y, x mod y)`) and min_max (a loop
  keeping both bounds, `r := (lo, hi)` in the suffix, `r` itself untouched
  by the loop body).

  MODEL. A pair is ONE Coq value here, `pair_ty`'s product `(T1 * T2)%type`
  (`pair_comp_ty` maps "int" -> Z, "bool" -> bool), never seq's own two-slot
  fn/len split, so it costs param_binders/seq_slots/rty one more branch
  each, not a new expansion rule. NAMED REFUSAL: a pair component of type
  "seq" raises NotImplementedError, in `pair_comp_ty` and mirrored in
  `Ctx.comp_term` (the `pair`-literal builder) and `pair_comp_eq_fn`
  (t_pair_eqb's component-equality lookup). SPEC.md's own rocq survey
  already names this kernel's product `Z * Z` and anticipates exactly this
  choice ("or a named refusal where... a seq component costs the
  certificate"): embedding seq's fn/len pair AS a product component would
  need a second, incompatible seq encoding this file does not otherwise
  have, for a shape no committed task needs. `pair`/`fst`/`snd` render
  through a new `Ctx.px` (the pair-TERM analogue of `seq_fn`, returning one
  Coq term, not two) and `Ctx.comp_term` (dispatches a pair argument to
  zx/bx/px by its own type); `zx`/`bx` each gained a `fst`/`snd` arm calling
  `px` on the projected pair. `fst`/`snd` `RESERVED` (the identifier
  namespace, not the AST op): not Rocq keywords, so a t identifier of the
  same name would PARSE, shadowing the library name, rather than fail;
  reserving "fst", "snd", "pair" turns that into an immediate, named `_ck`
  refusal instead of a confusing type error the moment generated code
  applies the (now shadowed) `fst`/`snd` to a pair term.

  EQUALITY. `==`/`!=` on two pairs is componentwise (SPEC.md: "the
  polymorphic == again"). In Prop position (`prop()`), stated directly, a
  plain Coq `=` per int component, the bool "= true"-and-`<->` form already
  used for a bare bool, no new PRELUDE surface. In COMPUTATIONAL position
  (`bx()`), the same gap `t_seq_eqb` closed for seq: `t_pair_eqb` (PRELUDE),
  GENERIC over the two component equality functions (`{A B : Type} (eqA :
  A -> A -> bool) (eqB : B -> B -> bool)`), `t_pair_eqb_spec` proved once
  for ANY correct eqA/eqB, `t_pair_eqb_case` (mirrors `t_seq_eqb_case`'s
  unconditional two-way split; no "try lia" shortcut) `first`-trying the
  two component-equality lemmas this file actually generates (`Z.eqb_eq`,
  `Bool.eqb_true_iff`), joined into `t_inv1`'s match immediately after
  `t_seq_eqb`'s own two entries. `pair_comp_eq_fn` chooses Z.eqb/Bool.eqb
  per component type at lowering time (the same refusal as `pair_comp_ty`
  for "seq"); neither committed task's ensures uses a WHOLE-pair `==`
  (both compare via `fst`/`snd`), so `t_pair_eqb` is measured only by
  construction, standalone-probed against coqc 9.2.0 before this file was
  touched (Z*Z and a Sumbool sanity goal, both compiled clean).

  THE t_inv1 COST FINDING (2026-09-10). `fst (a, b)` needs `fst` itself
  unfolded before the literal pair's own iota step can fire (`cbn beta
  iota` alone leaves it untouched; `cbn [fst snd]` reduces it), the same
  non-negotiable delta step t_div/t_mod's own case-split tactics give
  those two names. The FIRST attempt put this delta step INSIDE `t_inv1`
  itself, as two more `context [...]` match arms, the same shape every
  other structural-reduction arm here has. MEASURED WRONG: min_max then
  read REFUSED, real TIMEOUT (a direct `coqc` run measured past 200 s and
  still not done) where divmod_pair (no loop, no quantifier) read COUNTS
  in seconds. `t_inv1` sits inside `t_base`, which `t_go`'s depth-6
  `multimatch` search calls at EVERY branch it explores; two more arms
  tried, and re-scanned on every `repeat` iteration, at every node of an
  already large forall/exists-heavy search (min_max's ensures/invariants
  carry four) compounds, where the same two arms cost nothing on a small
  goal like divmod_pair's. FIX: pull the delta step OUT of the hot
  per-call tactic entirely. `gen_plain`/`gen_loop`/`_value_cert` each emit
  ONE explicit `cbn [fst snd].` line instead, exactly where a literal pair
  first becomes visible in THEIR OWN proof script (right after `unfold
  {name}_t.`, or after the loop's own `cbn beta iota.`, or after a
  certificate's `rewrite t_out.`), gated on a new `_has_pair(task)` walk
  (params, returns, `var` locals) so a task with no pair anywhere emits
  BYTE-IDENTICAL proof text to before pairs existed: one reduction, done
  once, before `t_dis`'s search even starts, rather than a pattern tried
  at every one of its many nodes.

  PRELUDE DELTA: 116 lines, all inserted immediately after
  `t_seq_eqb_case`'s own closing `]; t_bred_all.` (114 lines: the dated
  comment above `t_pair_eqb`, `Definition t_pair_eqb`, `Lemma
  t_pair_eqb_spec`, `Ltac t_pair_eqb_case`) plus 2 lines for `t_inv1`'s two
  new match-arm entries (goal position, hypothesis position), zero
  deletions, the same "pure insertions" shape every PRELUDE growth here
  has had. No `fst`/`snd` arm was added to `t_inv1` (the cost finding
  above): that reduction is a per-task, `_has_pair`-gated proof-script
  line, not PRELUDE, so it costs a task with no pair anywhere nothing at
  all, textually or in search time.

  MEASURED (2026-09-10, coqc 9.2.0, this box, harness.run_task,
  `verifiers.rocq`, out/agent-rocq-pairs/). divmod_pair reads COUNTS (real
  VERIFIED, wrong-var twin REFUTED, witness x=1, y=1 -> real [1, 0], twin
  [0, 1]), reproduced identically across every run in this session.

  min_max is LOAD-SENSITIVE on this shared box: three runs of
  BYTE-IDENTICAL generated Coq read three different verdicts. The first
  (the t_inv1-arm design above, since replaced) read REFUSED, real TIMEOUT
  (a direct `coqc` run measured past 200 s, killed, still not done),
  collapse-if twin REFUTED. After the fix, one run read REFUSED, real
  VERIFIED, collapse-if twin UNPROVED; a second run of the SAME generated
  source, minutes later, read REFUSED, real TIMEOUT again, `uptime`
  showing a load average of 63 on this box's 120 cores at that moment (a
  21-task matrix run, 16 jobs, sharing the machine and itself the source
  of that load). min_max's witness throughout: s=[0, 1] -> real [0, 1],
  twin [1, 1] (real keeps lo=0 since 0 is never replaced; the collapse-if
  twin drops the guard on the lo-update and always takes `s[i]`, giving
  lo=hi=1, which breaks `forall k, r.0 <= s[k]` at k=0). No run in this
  session produced real VERIFIED and twin REFUTED together, the flip
  proper; every reading fell to REFUSED by one side or the other, never
  by a wrong one. The matrix's own run (flake 3, rocq column) is the
  reading of record for min_max, not any run in this file's own session:
  the 180 s wall clock this kernel's verifier enforces is a real budget on
  a shared box, and min_max's proof (four forall/exists ensures/invariants
  plus the pair projections) sits close enough to it that which side of
  the line it lands on is a fact about the box's OTHER tenants at that
  moment, not about this lowering's correctness, which the VERIFIED and
  the two matching REFUTED readings above already established once each.

  THE v1pairs RESIDUAL (2026-09-10). The fuzz family `v1pairs` (31 tasks,
  `fuzz_lower.py`) read rocq verified/refuted on 19 of 31; the 12 that did
  not split into three unrelated causes, none of them the pair-rendering
  machinery itself (`px`/`comp_term`/`t_pair_eqb` all read correct on
  every one of these 12, once reached).

  (1) NINE read unproved/refuted (real does not prove, twin does refute):
  `fz_v1pairs_053` (eq_params: two pair PARAMS, ensures `fst p = fst q /\\
  snd p = snd q`), `fz_p_pair_proj` (the projection probe: `fst (pair a
  b)) = a`, no pair-typed name anywhere), and seven `sentinel`-shape tasks
  (`fz_v1pairs_060/142/357/425/433/768/773`: a loop keeping a `found` bool
  and a `val` int, `r := pair(found, val)` in the suffix, ensures phrased
  `fst r == exists ...`). Two SEPARATE gaps, not one:

    (a) `fz_p_pair_proj` has no dict-typed param/return/local anywhere (a,
    b, r are all plain ints; the pair is built and projected INLINE), so
    the old `_has_pair` (a TYPE walk only) read False and never emitted
    `cbn [fst snd].`; `fst (a, b)` sat stuck in front of `t_dis` (MEASURED,
    standalone: `unfold ...; t_dis.` alone left `fst (a, b) = a` unsolved,
    `cbn [fst snd]. t_dis.` closed it). FIX: `_expr_has_pair`, an
    expression-level walk for a `pair`/`fst`/`snd` node anywhere in
    requires/ensures/body (not just a declared type), folded into
    `_has_pair` alongside its existing type walk.

    (b) `fz_v1pairs_053`'s `p`/`q` ARE pair-typed params, so `_has_pair`
    already emitted `cbn [fst snd].` -- a NO-OP on an opaque variable
    (`fst`/`snd` iota-reduce only against a literal `(_, _)`, never a bound
    name), so `fst p`/`fst q` stayed stuck regardless (MEASURED: `cbn [fst
    snd]. t_dis.` alone still left the goal unsolved). `t_pair_eqb_spec`
    only relates `t_pair_eqb ... p q = true` to WHOLE-pair equality `p =
    q`, not the componentwise form the ensures states, so `t_dis` would
    additionally need `p = q <-> fst p = fst q /\\ snd p = snd q` from an
    opaque `p`, which no generic search here derives. FIX:
    `_pair_param_destruct`, `destruct {p}.` (no `as` clause) for every
    pair-typed PARAM, right after `intros.` and before `unfold`, in
    `gen_plain` and both `gen_loop` theorem scripts; this ALSO fixes
    `fz_p_pair_proj`'s cousin shapes should a future pair param appear in
    a loop task. MEASURED: `destruct p; destruct q.` before the existing
    `cbn [fst snd]. t_dis.` closes `eq_params`.

    The seven `sentinel` tasks are NEITHER of these: by the time `t_dis`
    runs, `cbn [fst snd]` (already gated on `_has_pair`, a dict-typed
    return here) has ALREADY correctly reduced every `fst`/`snd` of the
    literal returned pair down to the bare `found`/`found'` local
    (confirmed by instrumenting the generated proof directly -- the goal
    at that point is stated over `found'`/`val'`, no `fst`/`snd` left
    anywhere). This is NOT a pairs bug: `t_sweep` case-splits `<?`/`<=?`/
    `=?`/`Bool.eqb` comparisons but never a bare boolean VARIABLE gating
    an `if` (`if negb found && (s i <=? -1) then true else found`), so
    `found`'s value stays syntactically opaque through the per-step
    invariant-preservation proof: `apply IH; t_side` fails (the new-state
    invariant obligations still mention the un-reduced `if`), `inversion
    Heq` does not apply to a recursive call, and the induction step is
    left unsolved -- MEASURED: unpatched, `coqc` fails INSIDE
    `{name}_loop_spec`'s own `Qed`, not the outer theorem. `is_prime`'s
    own bool RETURN never trips this only because it is never REASSIGNED
    inside the loop body (early exit's `return`, which `loop_assigned`
    does not count as an assignment). FIX: `_bool_state_assigned` (loop
    state vars that are bool-typed AND actually reassigned in the body);
    `destruct {vars};` spliced into the existing one-line `cbn
    [{name}_loop]; t_sweep;` (pre-state names, before `t_sweep`, so its own
    comparison splits finish reducing every nested `if`), and `destruct
    {vars}';` spliced onto the theorem's own closing `t_dis`/`t_dis_ext`
    call (primed names, for the exit-time value). MEASURED WRONG first:
    putting the primed destruct on ITS OWN period-terminated line before a
    separate `t_dis.` compiled to "Attempt to save an incomplete proof" on
    every one of the seven (`destruct` on a bool makes two subgoals; a
    period ends the tactic, so the freestanding `t_dis.` next only closes
    the FIRST one) -- fixed by chaining both destructs with `;` onto the
    tactic they gate, the same splice `_has_pair`'s own `pair_line` never
    needed because it never branches.

  (2) ONE crash: `fz_v1pairs_064`, return type `{"pair": ["seq", "int"]}`,
  `ValueError: t v1 -> rocq: not a seq expression: 'fst'`. `pair_comp_ty`'s
  named refusal for a seq component already covers a PARAM (`param_binders`
  calls it at the top of `lower_v1`) and a literal `pair` build
  (`comp_term`), but not a RETURN: `lower_v1` only calls `rty(ret_t)` for
  the return's own binder well AFTER `spec_def_obls` has already walked
  ensures, so ensures' own `len(fst(r))` reaches `zx`'s "len" case, then
  `seq_fn(fst(r), ...)`, which has no `fst`/`snd` arm and raised a bare
  ValueError -- a crash, not the named abstain every other seq-component
  path gets. FIX: `_check_pair_types`, walking every param/return/local
  pair type and calling `pair_ty` on each (the SAME check `param_binders`/
  `rty` already make, just early and unconditional), called as the FIRST
  line of `lower_v1`, before `_try_cert_v1`'s own try/except could swallow
  the same check silently or anything else could reach it a different way.
  `fz_v1pairs_064` now reads a clean `abstain` with `pair_comp_ty`'s own
  message, the same shape `fz_p_pair_seq` (a PARAM with a seq component)
  already had.

  (3) ONE timeout: `fz_v1pairs_160`, `minmax` shape, structurally IDENTICAL
  to the committed `min_max` task (same params/returns/requires/body
  shape, diffed by hand). None of this date's fixes touch it: no pair
  param, no inline pair literal outside a declared return, no bool state
  var (`lo`/`hi`/`i` are all int) -- confirmed by `out/agent-rocq-pairs2/
  min_max.v` reading byte-identical to the prior `out/min_max.v`. Measured
  ALONE (no other coqc on the box) at load average 6-16 on this box's 120
  cores (this box's own earlier min_max flake was measured at 63): still
  TIMEOUT at 200 s, and again at 500 s, nearly three times the kernel's
  180 s budget. Unlike the earlier min_max note (one favorable run read
  real VERIFIED within budget), no run this session got a favorable one at
  ANY timeout tried, under load lower than the one previously blamed. This
  reads as PROOF COST, not primarily load: `minmax`'s four forall/exists
  ensures/invariants over an array plus two pair projections is close
  enough to (or past) the budget's edge that this box's own baseline,
  unloaded cost -- not merely a busy neighbor -- may already be the
  dominant term. Left AS TIMEOUT, unresolved: shrinking that search is a
  `t_go`/`t_base` question, out of this residual's scope.

  WHAT STAYS AN ABSTAIN, BY NAME: `fz_p_pair_seq` (a PARAM with a seq
  component, `pair_comp_ty`'s named refusal, already correct before this
  date; unchanged by any fix here) and `fz_v1pairs_064` (above, now
  correct rather than a crash). Both are the SAME refusal, `pair_comp_ty`,
  reached from different sites.

  MEASURED, before/after (`fuzz_lower.py --tasks <these 12> --only rocq
  --n 400 --seed 1 --flake 3`, coqc 9.2.0, this box): before, 9 unproved/
  refuted + 1 crash + 1 timeout + 1 (already-correct) abstain; after, 9 of
  those 9 read verified/refuted, the crash reads abstain, the timeout is
  unchanged, the pre-existing abstain is unchanged. Regenerated into
  `out/agent-rocq-pairs2/` via `harness.run_task`: `divmod_pair`, `abs`,
  `swap`, `reverse`, `tail`, `filter_pos` all read COUNTS exactly as
  `out/<name>.v` already did, and diff BYTE-IDENTICAL to `out/<name>.v`
  (none of the three fixes above touches any of the six: no pair param, no
  inline pair op beyond an already-typed one, no bool loop state
  reassigned in a body); `min_max` reads REFUSED (real timeout, collapse-if
  twin refuted) again, also byte-identical to `out/min_max.v`, the same
  load-sensitive/proof-cost reading as (3) above, not a regression.

  NESTED SEQUENCES (v1) (2026-09-10, SPEC.md "Nested sequences (v1)",
  ROADMAP 12.7, the wave after pairs). New type `{"seq": "seq"}`, a seq
  of seqs of ints, one level; NO new Expr forms, every operator
  polymorphic by its operands' static type. Two committed tasks:
  swap_rows (loop-free, `r := update(update(m, i, m[j]), j, m[i])`) and
  row_max_len (a loop keeping the longest row length).

  THE ENCODING, AND WHAT DECIDED IT. SPEC.md's own text offered two
  routes: a function from an index to a (function, length) pair, or
  `list (list Z)`. This lowering keeps the function-pair route: a nested
  seq is the SAME two-slot (fn, len) convention every seq already has
  here, only the fn's codomain changes from `Z` to `((Z -> Z) * Z)` (an
  outer index to a literal Coq pair of a row's own function and length).
  The choice was NOT settled by building both ends-to-end and timing
  swap_rows on each: a full `list (list Z)` implementation would need
  its own `nth`/update/equality machinery, duplicating everything
  `seq_fn`'s function+length model already proves once (`t_upd`,
  `t_fill`, `t_app`, `t_slice`, `t_seq_eqb`, and their reading tactics),
  a second, incompatible seq encoding PAIRS (v1)'s own note already
  named the reason to refuse for a pair's seq component; building it in
  full to get a timing number was judged not worth the context/time this
  session had left, so the decision rests on that architectural
  asymmetry (measured cost of ADDING one opaque Definition, `t_nupd`, at
  a new codomain vs. measured cost of building an entire second
  representation from nothing), not on a run pair, and is reported here
  as such rather than dressed up as a timing comparison that did not
  happen. What WAS measured is the function-pair route's own real cost,
  end to end, on both committed tasks (below).

  BUILD. `Ctx.nested_fn` (mirrors `seq_fn` exactly: `var`/`ite` are
  seq_fn's own cases verbatim, since the naming convention, `v`/`v_len`
  env slots, does not change, only the codomain) renders `update(m, i,
  r)`: the row `r`'s own (fn, len) becomes a literal Coq pair via
  `seq_fn` (a row IS an ordinary seq value, so every row-level operator
  -- `at`, `len`, `==` -- reaches it through the prelude's EXISTING
  definitions unchanged, exactly as this task's brief asked), and
  `t_nupd` (PRELUDE, `t_upd`'s own three-branch case-split shape,
  monomorphic at the row-pair codomain rather than a generic `{A :
  Type}` `t_upd`, so no existing seq task's PRELUDE text changes shape,
  only grows) rewrites the outer function at that index. `seq_fn` itself
  gains one new case, `at` on a nested container: `s[i]` is a row, read
  as `(fst (rows i), snd (rows i))` out of the outer value's own "rows"
  function; `Ctx.ty`'s `at`/`update` dispatch is generalized the same
  half-step `+` already had (the container's own type decides the
  result, not a hardcoded string), so a PLAIN seq's `at`/`update` is
  unchanged (confirmed by the regression below, not merely asserted).
  `s[i][j]` (chained) needs no code of its own: it is `at(at(m, i), j)`,
  and `seq_fn`'s new "at" case composed with `zx`'s EXISTING "at" case
  (unchanged) already reduces the outer `at` to a row's own (fn, len)
  before the inner `at` ever runs, the same multi-layer composition
  `t_upd_case`'s own nested-update precedent already established for a
  different pair of operators. `defs()` needed one small, not zero,
  fix (the census this file's own research pass ran first claimed
  otherwise): its `at`/`update` cases call a length-lookup that must
  route through `nested_fn` when the container is nested, `seq_fn`
  otherwise (`Ctx.outer_fn`, a two-line dispatcher, used at both defs()
  sites and at `zx`'s "len" case, which had the identical gap: `len(m)`
  on a bare nested var crashed with `seq_fn`'s own "is not a seq"
  assert before this fix). `rty`/`param_binders`/`seq_slots`/`len_hyps`
  each gained one nested branch, the same two-binder shape a plain seq
  already gets, so a nested LOOP LOCAL (this task's own brief) is
  supported by construction through the SAME generic machinery, not a
  special case: neither committed task declares one (row_max_len's `m`
  is a read-only param, never loop state), so this is measured only by
  construction, matched to the identical stance PAIRS (v1) already took
  for its own untested pair-param path. `exec_straight`'s three
  statement kinds (assign/return/var) each gained the identical nested
  branch, checked BEFORE the generic pair branch (a nested type is a
  dict too); every `isinstance(t, dict)` site written for pairs before
  this date was audited and narrowed to `"pair" in t` where treating a
  nested type as a pair would crash or misfire (`_check_pair_types`,
  `_pair_param_destruct`, `_has_pair`'s own type walk, `_glit`,
  `_to_interp_value`): `_pair_param_destruct`'s old filter would have
  tried `destruct m.` on an opaque nested param, meaningless on a
  function type, had this not been caught.

  EXTENSIONAL EQUALITY: A NAMED REFUSAL. Neither committed task's
  ensures ever compares two WHOLE nested seqs (`r[i] == m[j]` is a
  ROW-level `==`, an ordinary seq comparison already handled by
  `t_seq_eqb`/`prop`'s existing extensional form, no new code), so
  `t_nseq_eqb` (an outer recursion whose own "leaf" equality is
  `t_seq_eqb` rather than `Z.eqb`) was not built: SPEC.md's own
  construct note permits this ("if the encoding needs one"), and
  building an unmeasured second layer of recursion, untested against
  any committed task or any coqc run, was judged worse than a clean,
  named gap. `Ctx.nested_fn` raises `NotImplementedError` for `fill`,
  `+`, `slice` and a nested LITERAL at the outer level for the same
  reason: three more opaque Definitions (`t_nfill`, `t_napp`,
  `t_nslice`) at a codomain nothing exercises would be unmeasured
  surface, not growth. `_nested_witness_pieces` (the certificate side,
  below) proves a witness ROW's LENGTH reachable through `snd`; a row's
  own ELEMENTS through `fst`, from a witness, is the same kind of named
  gap (the REAL lowering's own `s[i][j]` rendering is unaffected and
  correct either way, per the composition above).

  THE t_inv1 COST FINDING, EXTENDED. `t_nupd_case` joins `t_inv1`'s
  match exactly where `t_upd_case` does (an ordinary case-split arm,
  the SAME tier every other seq/pair reading tactic already sits in,
  not the expensive "two more context arms tried at every search node"
  shape PAIRS (v1) measured and rejected). The genuinely new finding:
  reading an in-range `t_nupd` produces a literal Coq pair `v` in
  place, and `seq_fn`'s own rendering wraps that read in `fst (...)`/
  `snd (...)`, so the residue right after a successful case split is
  `fst (rf, rl)`/`snd (rf, rl)`, PAIRS (v1)'s OWN "loose fst/snd" gap,
  not a new one -- but appearing MID-SEARCH, inside `t_nupd_case`'s own
  case split, not right after `unfold` the way a literal `pair`
  expression already is. An upfront `cbn [fst snd]` line (the existing
  `_has_pair`-gated mechanism, `_has_nested` added alongside it at the
  same three sites for exactly this reason) is a NO-OP here: MEASURED
  WRONG once, directly, before landing the fix (swap_rows read real
  UNPROVED with only the upfront line, `unfold; cbn [fst snd]; t_dis`
  leaving the goal unsolved, since no literal pair exists yet at that
  point in the proof). FIX: `t_nupd_case`'s own two "in range" branches
  each end with `; cbn [fst snd] in *` (PRELUDE), chained onto the
  `replace` that already fires only when the tactic's own specific
  `t_nupd` pattern matched -- the same cost tier `t_pair_eqb_case`'s own
  trailing `; t_bred_all.` already sits in, not a new scanning arm tried
  everywhere. Re-measured after the fix: swap_rows reads COUNTS (below).
  A second, DIFFERENT instance of the same family surfaced in the
  certificate (`_loop_cert`, row_max_len's witness): asserting the
  outer pointwise fact in the "natural" pair-typed shape (`t_w_m k =
  (row_fn, row_len)`) needs the SAME post-hoc `cbn [fst snd]` step, but
  AFTER `set` folds the witness's name into the goal, an ordering no
  single `cbn` placement gets right either before or after `set` (MEASURED
  WRONG a second time: an upfront `cbn [fst snd] in *` right before
  `t_feed`/`t_dis` was ALSO a no-op, since `m k` is not yet a literal
  pair at that point either). FIX, this time not a delta step at all but
  a SHAPE change: `_nested_witness_pieces` asserts the fact ALREADY
  PROJECTED, `snd (t_w_m k) = len(row k)` (an int equation, provable by
  bare `reflexivity`, Coq computing straight through the transparent
  witness Definition and `snd`'s own iota step in one pass), the EXACT
  syntactic shape a plain seq's own pointwise fact already has, rather
  than a pair-shaped fact needing a further reduction step at all. Both
  fixes are dated findings about WHERE a delta step belongs, not new
  costs: neither adds a match arm anywhere, and both are confined to
  code paths a task with no nested seq never reaches.

  MEASURED (2026-09-10, coqc 9.2.0, this box, harness.run_task,
  out/agent-rocq-nested/). swap_rows reads COUNTS (real VERIFIED, twin
  REFUTED, 3.5 s total): the off-by-one twin shifts `m[j]`'s index by
  one, undefined at the measured witness m=[[]], i=0, j=0 (the single
  empty row's own bound, `0 <= 1 < 1`, false), certified by
  `_undef_cert`'s EXISTING `at`/`update` recursion (`_first_undef`),
  changed not at all: it already walks `interp.ev`'s own left-to-right
  order and Python `len`, depth-agnostic, needing only one fix
  elsewhere in the same certificate (`env_py`'s witness conversion now
  tuples BOTH levels for a nested param, matching interp.py's own
  tuple-of-tuples convention, the same one line the note near
  `_undef_cert` names). row_max_len reads COUNTS (real VERIFIED, twin
  REFUTED, witness exit at m=[[], [0]], i=2, r=0, 86.8 s total under
  this run's own 3-way flake_check concurrency on a box measured at load
  average 16.7 at the time, well inside the 180 s per-call wall; it did
  NOT time out and needed no isolated re-measurement). Both witnesses
  match SPEC.md's own construct note exactly (swap_rows' "shifted index
  running off the single row", row_max_len's "dropped upper bound
  letting the loop exit with r = 0").

  PRELUDE DELTA: 61 lines, all inserted immediately after
  `t_pair_eqb_case`'s own closing `]; t_bred_all.` (the dated comment,
  `Definition t_nupd`, `Ltac t_nupd_case`) plus 2 lines for `t_inv1`'s
  two new match-arm entries (goal position, hypothesis position), zero
  deletions, the same pure-insertion shape every PRELUDE growth here has
  had.

  REGRESSION. Regenerated into out/agent-rocq-nested/: abs, swap, tail,
  filter_pos, divmod_pair, min_max all read COUNTS (abs) or COUNTS
  (swap, tail, filter_pos, divmod_pair) with the SAME operator and
  witness named in each one's own prior dated note above, verbatim
  (e.g. divmod_pair's wrong-var twin at x=1, y=1, filter_pos's exit
  witness at s=[], i=1, r=[1]); min_max reads REFUSED, real TIMEOUT
  again, the SAME load-sensitive/proof-cost reading (3) of the v1pairs
  residual already established, not a regression (this run's own six-
  task loop shared the box with three concurrent flake_check calls per
  cell). A literal byte-diff against `out/<name>.v` could not serve as
  the controlled comparison it has for every prior wave THIS time: a
  concurrent process in this shared session regenerated the default
  `out/` directory, using this same file mid-edit, partway through this
  measurement, overwriting the pre-edit baseline before the diff ran (a
  fact about this shared box's other tenants, not about this lowering,
  the same caveat MEASURED already carries for min_max's own load-
  sensitivity). What stands instead: `out/agent-rocq-nested/<name>.v`
  and the now-regenerated `out/<name>.v` agree byte for byte on all six
  (self-consistent, deterministic output), and a direct code-path trace
  confirms the ONLY changes reaching any of these six are the 63-line
  PRELUDE growth and the `_has_pair`/`_has_nested` OR-gate at three
  `pair_line` sites, which is provably a no-op for all six (`_has_nested`
  is a pure type walk over `{"seq": "seq"}`, absent from every one of
  them) -- the same conclusion the (now unavailable) diff would have
  shown, reached by reading the code that ran rather than the file it
  would have produced.

  THE v1nested RESIDUAL (2026-09-10). The fuzz family `v1nested` (18
  tasks) read rocq verified/refuted on 6 of 18; the 12 misses split, by
  ROOT CAUSE rather than by symptom, into six fixes.

  (1) FOUR CRASHES, all `t["pair"]`'s own bare KeyError/AssertionError,
  never `pair_ty`-gated the way every other pair-type site already is.
  `fz_v1nested_026`/`fz_p_nest_eq` (`eq_nested`, `r := m == n` on two
  WHOLE nested seqs): `bx()`/`prop()`'s own `==`/`!=` dispatch read
  `isinstance(t, dict)` as "this is a pair" unconditionally, so a nested
  seq's `{"seq": "seq"}` dict crashed `t["pair"]` with `KeyError: 'pair'`
  before ever reaching `t == "seq"`'s own extensional branch just below.
  FIX: both dispatches gate the pair branch on `"pair" in t` (the exact
  guard `_check_pair_types`'s own `check()` already uses for the
  identical reason) and gain a NEW nested branch (below, (3)). `fz_v1-
  nested_054` (`slice_rows`, `r := slice(m, a, b)`, `m` nested): `defs()`'s
  own "slice" case computed the definedness bound's length with a bare
  `self.seq_fn(s, ...)`, never `outer_fn` -- the SAME dispatch `at`'s and
  `update`'s own defs() cases already route through `outer_fn`, `slice`'s
  was simply missed when nested seqs were built -- so a nested `s` hit
  `seq_fn`'s own "is not a seq" assert. FIX: one word, `seq_fn` ->
  `outer_fn`. `fz_p_nest_lit` (`nested_lit`, an INLINE `len(seq(seq(1,
  2), seq(3)))`, no declared nested type anywhere): `Ctx.ty`'s own "seq"/
  "slice"/"fill" arm returned the bare string "seq" unconditionally,
  never inspecting whether the literal's own rows are themselves seq-
  valued, so `outer_fn` misrouted a nested literal to `seq_fn`, which
  has no case for a "seq"-valued ARGUMENT and raised `ValueError: not an
  int expression: 'seq'`. FIX: `ty()`'s "seq" case now inspects its
  first argument's own type (nested iff it is itself seq-valued; an
  EMPTY literal stays ambiguous, resolved by the caller's declared-type
  dispatch exactly as SPEC.md says, never by this method); `ty()`'s
  "slice" case now propagates its container's own nesting the same
  half-step `at`/`+` already have.

  (2) ONE MALFORMED, `fz_v1nested_007` (`param_rowlen`, a loop, `m`
  nested): coqc's own error, read directly (`coqc` was reachable via
  `~/.opam/default/bin`, not on this session's default PATH), was "The
  term 'true' has type 'bool' while it is expected to have type 'Z ->
  bool'": `_value_cert`'s own `gargs` loop (the witness-substituted CALL
  to `{name}_t` inside the refutation certificate) checked `p["type"] ==
  "seq"` to decide a two-slot (fn, len) expansion, the same bare-string
  check (1) already found and fixed twice over; a nested param's own
  `_len` argument was silently DROPPED, one argument short of `{name}_
  t`'s real signature. FIX: the same `isinstance(dict) and "seq" in t`
  OR-guard as everywhere else.

  (3) WHOLE-NESTED `==`/`!=` IN COMPUTATIONAL POSITION, the gap the
  original NESTED SEQUENCES (v1) note (above) named and left unbuilt
  ("neither committed task's ensures ever compares two WHOLE nested
  seqs") -- this family's `eq_nested` shape does, in the BODY (`r := m
  == n`, a bool), not only the ensures. `t_nseq_eqb` (PRELUDE, dated
  note near `t_napp`, below) is `t_seq_eqb`'s own outer analogue: the
  same bounded Fixpoint, but each "leaf" is a ROW comparison (length
  ANDed with `t_seq_eqb` over the row's own elements) rather than
  `Z.eqb`, reusing `t_seq_eqb` rather than a second hand-written
  recursion. `bx()`/`prop()` each gained one new dict-typed branch
  (`t.get("seq") == "seq"`), `prop()`'s the same forall-of-forall shape
  `fz_p_nest_eq`'s own ensures already states by hand (one conjunct per
  row) SPEC.md's rule restated at two levels instead of one.

  (4) THE NAMED REFUSALS THIS FAMILY USES: `+` (`concat_nested`, `r :=
  m + n`), `slice` (`slice_rows`), and the outer LITERAL (`nested_lit`,
  `fz_p_nest_lit`, `fz_p_nest_empty`) -- three of the four operators
  `Ctx.nested_fn`'s own dated note (above) named as unexercised
  refusals. Built the same way `update` already was: `t_napp`/
  `t_nslice` are `t_app`/`t_slice` at the row-pair codomain, monomorphic,
  Ltac copied verbatim (PRELUDE, dated note near `t_napp`); the LITERAL
  is `t_nupd` chained over a base row never read at any assigned index,
  needing no new opaque Definition, the exact reasoning `seq_fn`'s own
  literal already uses for `t_fill 0`. Neither `t_napp_case` nor
  `t_nslice_get` exposes a bare literal pair (their branches are still-
  symbolic applications or a reindex, never a `(rf, rl)` literal), so
  both join `t_inv1`'s match as a PLAIN case-split arm -- no delta step
  added to `t_inv1`'s hot match; the literal's own delta step is
  `t_nupd_case`'s existing `cbn [fst snd] in *`, unchanged. `fill`
  stays the one refusal actually left: no task in this family builds an
  outer `fill`, so `t_nfill` stays unwritten, the same "unmeasured
  surface" reasoning the original note gave for all three.

  `fill` was the FOURTH name on this task's own list ("outer fill, +,
  slice, literal, whole-nested =="); a `grep` of every task's own AST
  confirms zero uses of an outer `fill` anywhere in the 18-task family,
  so it is left exactly where (4)'s own note leaves it.

  (5) TWO LATENT BUGS THIS RESIDUAL EXPOSED, NEITHER SPECIFIC TO
  NESTING. `emit_def_lemmas` (and its `emit_spec_funs` twin) rendered
  `forall {allb},` unconditionally; a param-less task with a ground
  obligation (no bound `binders` either -- `fz_p_nest_lit`'s own `at` on
  a literal index) makes `allb` empty, so `forall ,` is a bare keyword
  with no binder, a Coq syntax error, MALFORMED. `gen_plain`'s three
  `Theorem {name}_t_spec : forall {pb},` sites have the identical shape
  for a param-less task's own top-level correctness theorem. FIX (both):
  omit the whole `forall ..., ` line when there is nothing to bind;
  every task with a param or a bound variable renders byte-identical to
  before. Neither of these was reachable before this residual: every
  prior committed/fuzzed task had at least one param.

  (6) `gen_loop` HAD ONLY HALF OF NESTED RETURNS. `gen_plain` already
  special-cased a nested return's own placeholder env0 and its two-
  Definition (fn, len) split; `gen_loop` had the placeholder (added
  here, MEASURED first as `fz_v1nested_069`'s own abstain,
  "default_term has no single-slot default for a nested seq") but not
  the SECOND half: its own `ens`/`def_lines` construction still checked
  bare `ret_t == "seq"`, so a nested RETURN threaded through a LOOP
  (`build_matrix`'s own `m`, assigned to `r` only in the suffix) left
  `r_len` unsubstituted in the rendered ensures -- a bare, unbound name,
  "The reference r_len was not found in the current environment",
  MALFORMED. FIX: both a nested env0 branch and a nested `ens`/
  `def_lines` branch, each the SAME two-Definition split `gen_plain`
  already has.

  MEASURED, before/after (`fuzz_lower.py --tasks <these 12> --only rocq
  --n 400 --seed 1 --flake 3`, coqc 9.2.0, this box, reached via
  `~/.opam/default/bin`, not this session's default PATH). Before: 4
  lower-error crashes (`fz_v1nested_026`/`054`, `fz_p_nest_lit`/`eq`), 4
  abstains (`fz_v1nested_069`/`078`/`115`/`606`), 1 verified/malformed
  (`fz_v1nested_007`), 1 unproved/unproved (`fz_v1nested_150`), 1
  verified/unproved (`fz_v1nested_182`), 1 no-twin/no-twin (`fz_p_nest_
  empty`). After: FOUR now read verified/refuted in full --
  `fz_v1nested_007`/`026`/`054` and `fz_p_nest_eq`, every one of them a
  crash or MALFORMED before. FIVE more now read verified/unproved,
  upgraded from a crash, an abstain, or MALFORMED to a correct REAL
  program whose TWIN is not (yet) certified false: `fz_v1nested_069`/
  `078`/`115`/`606` and `fz_p_nest_lit`. THREE are unchanged, out of
  scope for this residual (none uses `+`/`slice`/the literal/whole-
  nested `==`): `fz_v1nested_150` (unproved/unproved, a `rowsum` spec_fun
  call composed with a nested `at` -- a proof-strength gap, not a
  lowering crash), `fz_v1nested_182` (verified/unproved, 41.2 s real --
  the SAME load-sensitive/proof-cost reading the v1pairs residual (above)
  already measured for `min_max`, not a regression), and `fz_p_nest_
  empty` (no-twin/no-twin -- `harness.twin_cached` finds no mutation for
  a body with nothing but one literal assign, a corpus/harness limit no
  lowering fix can reach, unconditionally the same for every backend).

  WHY the five verified/unproved cells are not verified/refuted, NAMED
  rather than guessed at (each traced to its own witness `_kind` and the
  specific certificate function that declines it): `fz_v1nested_078`/
  `606`/`fz_p_nest_lit` have a "value"-kind witness but ZERO params
  (`nested_lit`'s own shape, a return-only task), and `_value_cert`'s
  own first line is `if not task["params"]: return None` -- built for a
  witness that substitutes PARAMS, with no hook yet for a body-only
  mutation; `fz_v1nested_115`'s witness is ALSO "value"-kind, but its
  RETURN is nested, and `_value_cert` already had a NAMED abstain for
  exactly that shape before this date ("a seq twin value is a tuple...
  this abstains rather than guessing, the SAME reason extended to a
  nested return"), simply never exercised until `concat_nested`;
  `fz_v1nested_069`'s witness is "undefined"-kind, but `_undef_cert`'s
  own second line is `if w is not None: return None  # not needed by
  any committed task yet` -- built for a loop-free body, and `build_
  matrix` is this family's first loop task with an undefined-kind twin.
  None of these three gaps is a nested-SEQ bug specifically (a plain-seq
  param-less/nested-return/loop-undefined task would hit the identical
  wall); none is touched by this date's fix, which built the FOUR named
  operators the family uses, not a new certificate shape.

  PRELUDE DELTA: MEASURED by regenerating swap_rows/row_max_len/swap/
  tail/filter_pos/divmod_pair/min_max into `out/agent-rocq-nested2/` via
  `harness.run_task` and diffing against `out/<name>.v`: 151 inserted
  lines on all seven (zero deletions, three diff hunks each -- 145 lines
  for the `t_napp`/`t_nslice`/`t_nseq_eqb` block and its dated comment,
  3 + 3 for `t_inv1`'s new match-arm pairs, goal and hypothesis
  position), byte-identical otherwise; `abs` (a v0 task, `lower_v0`,
  untouched by any fix here) is byte-identical outright. The same pure-
  insertion shape every PRELUDE growth here has had.

  REGRESSION. All eight reads exactly reproduce their own prior dated
  note's witness, unchanged: `swap_rows`/`row_max_len` (COUNTS, this
  note's own MEASURED paragraph above, byte for byte) and `abs`/`swap`/
  `tail`/`filter_pos`/`divmod_pair` (COUNTS, each one's own witness
  verbatim, e.g. `divmod_pair`'s wrong-var twin at x=1, y=1)/`min_max`
  (REFUSED, real TIMEOUT again, the same load-sensitive reading already
  established, not a regression). The diff against `out/<name>.v`
  (PRELUDE DELTA, above) is the controlled comparison this time (unlike
  the v1nested wave's own note, where a concurrent process had
  overwritten the baseline): all seven v1 tasks differ from `out/
  <name>.v` by EXACTLY the 151-line PRELUDE insertion and nothing else;
  `abs` (v0) is byte-identical outright.

  WHAT STAYS AN ABSTAIN OR UNCHANGED, BY NAME: `fill` at the nested
  outer level (`t_nfill`, unbuilt, unexercised by this family, (4)
  above); `fz_v1nested_150` (`rowsum` spec_fun composed with a nested
  `at`, a proof-strength gap); `fz_v1nested_182` (load-sensitive proof
  cost, the v1pairs residual's own `min_max` finding again); `fz_p_
  nest_empty` (harness `no-twin`, no lowering fix reaches it); and the
  three named certificate gaps just above (`_value_cert`'s param-less
  and nested-return abstains, `_undef_cert`'s loop-free-only abstain) --
  none of which this date's fix was scoped to close.

  THE NINE SOLE-BLOCKERS (2026-09-10, COVERAGE-lifted-785.md's tenth
  sweep, "Sole blockers": rocq alone keeps 9 of the 72 six-of-seven
  lifted tasks out of all seven). MEASURED (coqc 9.2.0, this box,
  harness.run_task, flake 3, one task at a time, load average 17-52
  across the session): six of nine now read COUNTS; three stay open,
  named below. Four gaps, all found by reading the failing .v directly
  (`Show`/`idtac` probes on scratch copies, never guessed at) rather
  than by pattern-matching the error text against a prior note.

  (1) FOUR read verified/unproved (real proves, the twin's own
  `_loop_cert` certificate does not): `clover_min_array__minArray`,
  `dafny_tmp_tmpv_d3qi10_2_min__minArray` (the same minArray shape
  twice, isomorphic up to renaming), `mieic...calcR`, `program_
  verification_dataset...sumto_sol__sumUpTo`. Two separate causes, both
  in `_loop_cert`, both now COUNTS:

    (a) minArray's own invariant ladder keeps `exists x_v, 0 <= x_v <
    i_v2 /\\ r = a[x_v]` when the twin drops the FORALL invariant next to
    it; that exists is an ANTECEDENT of the certificate's `t_H` (part of
    `inv_arrows`), and `specialize`/`_glit` bakes every param and
    loop-state value into a Z LITERAL the same way is_prime's own
    2026-09-09 fix found for a forall in the certificate's GOAL --
    `t_go`'s built-in existential arm ("try 0, else any bound `x : Z`
    already in context") had no non-zero candidate to try, so `t_feed`'s
    `assert (D : A) by t_dis` silently failed to strip that one arrow,
    leaving `t_H` un-stripped and the closing `t_dis` unprovable (MEASURED:
    a `t_base; Show` probe on a scratch copy showed exactly this, `t_H`
    still an implication chain after `t_feed`). FIX: `_loop_cert` gets a
    new `elif kind == "exit":` branch (has_return's own `if` above is
    untouched) that scans `_forall_hints` over BOTH `concl_asts` and the
    invariants (has_return's scan only widens to invariants for `kind ==
    "preservation"`, where they ARE the goal, not an antecedent) and
    `pose`s the witnesses BEFORE `t_feed t_H`, not after: they have to be
    visible to `t_feed`'s OWN internal `t_dis` calls, not only to the
    final closing tactic. MEASURED that plain `t_go` (via plain `t_dis`)
    already closes it once the candidate exists -- a witness VALUE was
    missing, not a forall-hypothesis PAIRING -- so `closer` stays `t_dis`,
    never escalated to `t_go_ext`'s more expensive search.

    (b) calcR/sumUpTo both keep a spec_fun invariant, `r == ghost_fn(i)`
    (`r_v`/`sum_up_to`), through their own twin ladder; `_call_asserts`
    (the certificate's own ground-and-rewrite pass) scanned only
    `concl_asts` (`task["ensures"]`, which mentions the spec_fun applied
    to the PARAM `n`, never the loop-state var `i`), so the surviving
    invariant's own `sf_r_v i`/`sf_sum i` was left un-grounded: `t_feed`
    tried to prove `r = (sf_r_v i)` from the witness's own literal `r`
    with no ground fact to rewrite it to and no fuel-unfolding path a
    depth-6 `t_go` takes through an opaque Fixpoint application (MEASURED:
    `coqc` alone, "unsolved t verification condition" right there). FIX:
    widen the scanned asts to `concl_asts + w.get("invariants", [])`;
    `env_py` already carries the state var's own witness value by that
    point (the per-svar loop just above in `_loop_cert`), so the SAME
    ground-and-rewrite machinery the conclusion already had now reaches
    the invariant too. Costs nothing when neither mentions a spec_fun call
    (every committed task's own invariant, `sum_upto`'s closed-form `2*r
    == i*(i+1)` included, has none).

  (2) THREE read unproved/refuted (the real does not prove; found by
  reading each failing .v's own error directly): `dafny_verify...
  upWhileLess`, `software_building...aula2__m3` now read verified/
  refuted; `...aula2__mystery1` stays open, below.

    upWhileLess (`i := 0; while i < n: i := i + 1; ensures i == n`) is
    the FIRST committed-or-lifted loop task with exactly ONE loop state
    variable, and it exposed two latent `gen_loop` bugs at once, both
    invisible until now because every prior loop task's state was a 2+
    tuple (a genuine Coq pair, one constructor):

      - the induction lemma's non-recursing branch script is `intro Heq;
        inversion Heq; subst; clear Heq; t_dis`. For a BARE Z (or bool)
        equation (no tuple to inject), `inversion Heq` duplicates it into
        a fresh hypothesis and `subst` then consumes and auto-clears the
        ORIGINAL `Heq` itself (MEASURED, a 6-line standalone probe: `Heq,
        H : i = i'` after `inversion`, then only `H : i' = i'` survives
        `subst`, `Heq` already gone) -- so the scripted `clear Heq`
        errored "No such hypothesis", caught by `first` as that whole
        branch's failure, falling through to `fail`, discarding a goal
        `t_dis` could otherwise have closed outright. FIX: `try clear
        Heq`, both here and in the early-exit sibling script (untested by
        any committed/lifted task yet, fixed defensively, same reasoning,
        `try` costs a passing task nothing).

      - the theorem's own `destruct ({name}_loop ...) as {pat_p} eqn:Heq`
        needs a full DISJUNCTIVE pattern whenever the destructed value's
        type has more than one constructor; `pat_p` is a bracket pattern
        `[a' b']` for 2+ state vars (a genuine product, ONE constructor,
        exactly right), but for exactly one var it is a BARE name, and
        `destruct` on a bare Z (3 ctors) or bool (2 ctors) value with a
        flat, non-disjunctive pattern is a Coq syntax error --
        "Disjunctive/conjunctive introduction pattern expected", MEASURED
        directly (a 9-line standalone probe reproduces it on a bare `Z`
        AND, separately, on a single-var PAIR-typed value too, so the fix
        is keyed on the STATE-VAR COUNT, not the type). This error had
        been fully MASKED until the `try clear Heq` fix above landed: the
        loop_spec Lemma failed first, so coqc never reached this theorem
        at all. FIX: `remember ... as {pat_p} eqn:Heq; symmetry in Heq`
        (never case-splits, so it is correct regardless of constructor
        count) in place of `destruct`, gated on exactly one state var; a
        2+-var task's own destruct text is untouched, byte for byte.

    m3 (`z := (x == y); ensures z -> x == y`) failed for an unrelated
    THIRD reason, in `gen_plain` rather than `gen_loop`: its own script
    is `intros. unfold {name}_t. t_dis.`. `unfold` (bare, no `in *`)
    rewrites the GOAL only, and since `intros` ran first, the return
    variable's own truth, used as the ANTECEDENT of ensures' top-level
    `implies` (`(m3_t x y = true) -> x = y`), became a HYPOTHESIS that
    still held the opaque, un-unfolded `m3_t x y` name -- MEASURED with a
    `t_base; Show` probe: `H : m3_t x y = true` sitting stuck, nothing
    left for the search engine to open. FIX: swap the order to `unfold
    {name}_t. intros. ...` in all three `gen_plain` template branches
    (plain, seq-return, nested-seq-return); `unfold` needs nothing
    introduced first (it rewrites under any remaining foralls/arrows
    exactly the same), so this is a pure reordering, never wrong for a
    task whose ensures has no such leading implication (every gen_plain
    task in the committed matrix, confirmed by the regression below).

  (3) COMPUTESUM (`m2...computeSum`), read unproved/unproved originally,
  now reads verified/refuted TWIN, real still unproved: fix (1)(b) above
  (the `_call_asserts` widening) applies here too (its own invariant is
  `s == sum(i)`), so the twin side is now COUNTS-shaped; the REAL side's
  own induction step needs `s + i + 1 = sum(i + 1)` from `s = sum i`
  (the invariant, kept in context) and `sum`'s defining equation
  (`sf_sum_eq`, already in PRELUDE, already tried via `t_side`'s own
  `t_eqs` fallback) -- but rewriting `sf_sum_eq` at `sum(i+1)` leaves
  `sum (i + 1 - 1)` in the goal, syntactically DIFFERENT from `sum i` in
  the invariant hypothesis (lia atomizes an opaque application whole and
  never simplifies ARGUMENT arithmetic inside one), and `t_sat1`'s own
  merge rule ("merge var-headed application args that lia proves equal")
  requires `is_var` on the head symbol, which a global spec_fun constant
  like `sf_sum` never is. Left UNPROVED, named: reconciling this needs
  extending the merge machinery to global spec_fun symbols with
  arithmetic-normalized arguments, a proof-engine change with its own
  regression surface across every spec_fun task, out of this session's
  scope.

  (4) MYSTERY1 (`software_building...aula2__mystery1`, self-recursive,
  `res := m` at `n = 0`, else `res := 1 + mystery1(n - 1, m)`, ensures
  `res >= 0 /\\ n + m == res`, no spec_fun anywhere) stays unproved/
  refuted, UNCHANGED. `gen_rec`'s induction step closes with `apply IH;
  repeat t_dm1; lia`, which only unifies when the caller's own recursive
  shape mirrors a companion spec_fun's defining equation exactly
  (factorial/fib/gcd's own `eq_lines`, `try rewrite sf_X_eq`, makes `r`'s
  own recursive structure match `apply IH`'s target); mystery1 has no
  spec_fun at all, and wraps the self-call's result in an extra `1 + `,
  so `apply IH`'s conclusion (a bare `(fuel_fn fu n' m >= 0) /\\ (n' + m =
  fuel_fn fu n' m)`) never unifies with a goal shaped `(1 + fuel_fn fu
  (n-1) m >= 0) /\\ (n + m = 1 + fuel_fn fu (n-1) m)` (CONFIRMED by
  isolating the base/step goals with bullets on a scratch copy: the base
  case closes by bare `t_dis`, the step case's `apply IH; t_side` leaves
  the goal exactly as printed). A real fix needs `gen_rec` to track each
  self-call SITE's own concrete arguments (the way `_call_asserts`
  already tracks spec_fun call sites) and `pose proof (IH <args>)` +
  `t_feed`-style antecedent discharge there, rather than a bare `apply`;
  not attempted this session (a new argument-tracking pass through
  `exec_straight`'s self-call substitution, non-trivial regression
  surface against factorial/fib/gcd's own working `apply IH` path).

  (5) MAX (`seng2011...flex_ex2__max`), read timeout/refuted originally,
  UNCHANGED, re-measured alone (no other coqc on the box at the time):
  real TIMEOUT again at the 180 s wall (3-way flake, ~3 min total), twin
  still REFUTED. Structurally the SAME shape the min_max load-sensitivity
  finding (2026-09-10, PAIRS (v1), above) already established: a forall
  PLUS an exists invariant over an array, four-plus quantified
  conjuncts near the search budget's edge. Left AS TIMEOUT, unresolved,
  per this session's own "only if cheap" instruction: no lowering gap
  was found, and shrinking `t_go`/`t_base`'s own search cost is out of
  this residual's scope, the same call min_max's own note already made.

  REGRESSION (`t/tasks/*.json`, all 23, flake 3, one cell at a time,
  `run_par.lower_and_dispatch`, jobs=1): 22 of 23 read verified/refuted,
  matching AGREEMENT.md's rocq column exactly, byte for byte in outcome;
  `min_max` reads timeout/refuted again, the SAME load-sensitive reading
  AGREEMENT.md already records, not a regression. No committed task's
  own witness or timing class changed. `factorial`/`fib`/`gcd` (the three
  existing `gen_rec` tasks) confirm mystery1's own gap above is
  scope-limited to the no-companion-spec_fun shape, not a break in the
  working `apply IH` path itself.

  WHAT STAYS OPEN, BY NAME: `m2...computeSum` (real unproved -- the
  spec_fun-argument-normalization gap in (3) above; its TWIN now reads
  refuted, an improvement banked); `...aula2__mystery1` (real unproved --
  the no-companion-spec_fun self-recursion gap in (4)); `seng2011...
  flex_ex2__max` (real timeout -- the load-sensitive/proof-cost reading
  in (5), min_max's own precedent repeated). Six of the nine sole-blocker
  tasks now read COUNTS; these three do not, each for a distinct, named
  reason, none of them a lowering crash or a masked error.

  THE EIGHT SOLE-BLOCKERS, SECOND PASS (2026-09-10, COVERAGE-lifted-785.md's
  TWELFTH sweep, sweep-785-r16, "Sole blockers": rocq alone now keeps 8 of
  the 72 six-of-seven lifted tasks out of all seven -- the set shifted from
  the tenth sweep's nine above: upWhileLess, m3, minArray x2, calcR,
  sumUpTo left the list (fixed above), tetrahedralNumber/f1a__f/ghost__m/
  is_even/max_nit entered it, newly lifted or newly counting in six).
  MEASURED (coqc 9.2.0, this box, harness.run_task, flake 3, one task at a
  time, load average 7-52 across the session): two are now COUNTS by a
  certificate fix, one is now COUNTS by a proof-engine fix, one is a
  correct abstain (not a bug), two stay unproved (their exact stuck goal
  quoted, not guessed at, below), one stays timeout (unchanged, per this
  session's own "only if cheap" instruction, and unaffected by either fix:
  neither task has a spec_fun, a pair, a nested seq, or a bool-typed loop
  state var reassigned in its body, so no code path either fix touches is
  ever reached for it).

  (1) THE PARAMETERLESS CERTIFICATE GAP, closed for BOTH tasks it named:
  `dafny_tmp_tmp0wu8wmfr_tests_f1a__f` (`r := 0; ensures r <= 0`) and
  `dafny_verify_tmp_tmphq7j0row_test_cases_ghost__m` (`r := 29; ensures
  r == 29`) both read verified/unproved: `_value_cert`'s own first line,
  `if not task["params"]: return None`, refused to even ATTEMPT a
  certificate for a param-less task, so the twin (whose off-by-one mutant
  changes the literal, `f`'s `0` to `1`, `m`'s `29` to `30`, MEASURED by
  reading `out/..._twin.v`'s own `Definition ..._t  : Z := 1.` against the
  real's `:= 0.`) fell through to the ordinary proof script, which cannot
  prove a FALSE spec and correctly reads UNPROVED rather than REFUTED.
  Nothing downstream needed a param: `_witness_env`'s own `for p in
  task["params"]` loop is a no-op on an empty list (env_py/env_txt/etc.
  come back empty, exactly what a param-less task needs), `_plain_def`
  already rendered a correct nullary `Definition {name}_t  : Z := ...`
  for this exact shape (unchanged, confirmed by the twin `.v` already on
  disk before this fix), and the `gargs` loop building the certificate's
  own witness-substituted call is empty for an empty params list, giving
  `applied = "(name_t )"` -- a bare identifier in one extra pair of
  parens, valid Coq syntax, MEASURED to compile clean. FIX: delete the
  guard; the seq-return abstain immediately below it (unrelated, a named
  gap of its own) is untouched. MEASURED: both tasks now read COUNTS
  (`harness.run_task`, off-by-one twin, `f`: witness -> real 0, twin 1;
  `m`: witness -> real 29, twin 30). No committed task in t/tasks/*.json
  has an empty `params` list (checked directly), so this is a pure
  addition: every committed task's own witness-certificate code path is
  unreached by this change, confirmed by the regression below reproducing
  every committed task's own witness verbatim.

  (2) THE SPEC_FUN ARGUMENT-ARITHMETIC GAP, closed for `m2...computeSum`,
  read AND STILL closed for its twin (the 2026-09-09/-10 first-pass note
  above, (3), already banked the twin side via `_call_asserts`'s widening;
  this pass closes the REAL side that note left open, named as a proof-
  engine change out of scope for that session). Read directly (coqc on
  `out/m2..._computeSum.v`, the unpatched loop_spec Lemma): the induction
  step's `apply IH; t_side` arm needs `s + i + 1 = sf_sum (i + 1)` from
  the invariant `s = sf_sum i`; `t_eqs`'s bare `rewrite sf_sum_eq` turns
  the goal's `sf_sum (i + 1)` into `... + sf_sum (i + 1 - 1)`, NOT `...  +
  sf_sum i` -- lia proves `i + 1 - 1 = i`, but `t_sat1`'s only merge rule
  for two occurrences of the SAME head applied to lia-equal arguments
  requires `is_var f` on that head, and `sf_sum` is a global Definition,
  never a variable, so the two `sf_sum` applications never unify and the
  goal is left exactly as printed (CONFIRMED with a standalone `t_base;
  Show` probe on a scratch copy of the generated `.v`, isolating this one
  goal with bullets: the base case closes by plain `t_dis`, the step
  case's `apply IH; t_side` alone leaves `s + i + 1 = sf_sum (i + 1 - 1
  + 1) `-shaped -- read literally off the probe, not paraphrased). FIX:
  `emit_spec_funs` (the generator, not a hand-written PRELUDE tactic) now
  appends one `repeat match goal with |- context [sf_{f} ?x] => progress
  ring_simplify x end;` per spec_fun to `t_eqs`'s own chain (goal
  position) and the hypothesis-targeted twin (`ring_simplify x in H`) to
  `t_eqs_h`'s, right after the existing `try rewrite sf_{f}_eq;` for that
  spec_fun. `ring_simplify` normalizes a Z-ring argument wherever it sits
  (turning `i + 1 - 1` into literally `i`, matching the invariant's own
  term byte for byte, after which `t_sat1`'s existing machinery -- or in
  computeSum's case bare `lia`/`congruence` on the now-matching equation
  -- closes the rest); `progress` makes a no-op harmless (a task whose own
  recursion needs no normalization, or whose argument is already a bare
  variable, loses nothing and gains nothing textually different from
  before this fix, MEASURED against factorial/fib/gcd/digit_sum/
  count_matches below). GUARDED, not universal: only a spec_fun with
  EXACTLY ONE "int"-typed param gets this treatment (`sf["params"]` a
  singleton `"int"`), checked directly against the spec_fun's own JSON
  shape at generation time, never a bare string check -- a spec_fun with a
  seq param (count_matches' `count`, whose first bound variable under the
  naive one-wildcard pattern `sf_count ?x` would be the seq's own `Z -> Z`
  FUNCTION, not a ring element, and `ring_simplify` on a function term is
  not merely a no-op but an outright error, unguarded by `try`) or two-
  plus int params (gcd's `gcds`, where a single wildcard would bind only
  the first of two arguments arbitrarily) is left exactly as before,
  bare-rewrite-only, confirmed byte-identical by the regression below.
  MEASURED (`harness.run_task`, flake 3): computeSum now reads COUNTS in
  full (real VERIFIED, invariant-drop twin REFUTED, witness exit at n=0,
  i=1, s=1) where the first pass left it unproved/refuted.

  (3) TWO STAY UNPROVED, BOTH READ DIRECTLY, BOTH TRACED TO A GAP THIS
  FIX DOES NOT CLOSE, NOT ATTEMPTED FURTHER ONCE THE ATTEMPT MEASURED
  UNSAFE:

    `dafny_verify_tmp_tmphq7j0row_dataset_error_data_real_error_iseven_
    success_1__is_even` (`i := 0; r := true; while i < n: r := !r; i :=
    i + 1; ensures r == even(n)`, `even` a spec_fun with exactly one int
    param -- eligible for fix (2) above, and it fires: `t_eqs` DOES
    normalize `sf_even (i + 1 - 1)` to `sf_even i` (CONFIRMED with the
    same standalone-probe technique as computeSum). What remains after
    normalization is a DIFFERENT gap: the goal is `sf_even (i + 1) = true`
    where the usable fact is `Hinv2 : false = true <-> sf_even i = true`
    (i.e. `sf_even i = false`) -- a BOOL equality, not a Z one. Closing it
    needs `sf_even i`, an OPAQUE bool-valued application, case-split into
    its two constructors (`destruct (sf_even i)` or equivalent), which
    nothing in `t_inv1`/`t_sat1` does for an arbitrary bool-headed
    application (only a decidable Z-comparison notation or a NAMED
    function like `t_upd`/`Bool.eqb` gets a case-split arm; a bare spec_fun
    boolean is neither, the same gap the 2026-09-10 PAIRS/v1pairs residual
    already named for a bool STATE VAR reassigned in a loop body,
    `_bool_state_assigned`, extended here to a bool spec_fun RESULT rather
    than a state var). ATTEMPTED: a new `t_sat1` arm, `H : ?X = true |-
    context [?X] => rewrite H` (symmetric for `= false`), meant to
    propagate a ground bool fact into any matching goal occurrence
    regardless of head shape. MEASURED UNSAFE before it was tried on
    is_even itself: on max_nit (below), the SAME rule, reached through
    `t_base`'s own `repeat`, landed the search on a goal of `false = true`
    -- a FALSE residual, meaning the rule (or its interaction with
    `t_split1`'s own case-splitting, which backtracks over `a = b \\/ a <>
    b` and can pick either branch) fired on the WRONG occurrence somewhere
    in the loop and corrupted the proof state rather than helping it,
    confirmed by `match goal with |- ?G => idtac G end` printing the
    nonsensical goal directly. This is exactly the "regression surface
    across every spec_fun task" the first pass's computeSum note already
    warned a proof-engine change of this shape would have; NOT landed,
    reverted (never applied to this file, only tried in scratch copies
    under /tmp), left open. is_even's real side is UNPROVED; its twin
    still reads REFUTED (invariant-drop, unaffected, unchanged from the
    first pass).

    `nitwit_tmp_tmplm098gxz_nit__max_nit` (`nmax := b - 1`; ensures
    `nmax >= 0 /\\ nitness(b, nmax) /\\ is_max_nit(b, nmax)`, three
    spec_funs, `is_max_nit`/`nitness` two int params each -- INELIGIBLE for
    fix (2), correctly untouched by it). Read directly: `nmax >= 0` and
    `is_max_nit(b, nmax) = true` both close by the UNCHANGED engine (`t_dis`
    alone); `nitness(b, nmax) = true` does not. `nitness`'s own body is
    `if (b_v3>=0 /\\ n>=0 /\\ valid_base(b_v3)) then (0<=n /\\ n<b_v3)
    else
    false`; after `t_eqs` unfolds it, the goal contains a bare, still-
    opaque `sf_valid_base b`, and the hypothesis `sf_valid_base b = true`
    (the task's own `requires valid_base(b)`) states EXACTLY that value,
    for the EXACT same argument, no arithmetic offset at all -- yet nothing
    substitutes it in, the identical `is_var`-guard gap fix (2) closes for
    an ARGUMENT mismatch, here blocking a bare GROUND-FACT substitution
    instead. A manual, bulleted proof (`rewrite sf_nitness_eq.` then
    exactly the `H : sf_valid_base b = true |- context [sf_valid_base b]
    => rewrite H` step, then `t_dis`) DOES close it, confirmed directly;
    automating that same step hit the identical unsafe-generalization wall
    documented just above (the same attempted `t_sat1` rule, tried here
    FIRST, is what produced the `false = true` residual that then ruled it
    out for is_even too). Left open, real UNPROVED; twin still REFUTED
    (off-by-one, unaffected, unchanged from the first pass).

  (4) THE ABSTAIN, READ, NOT A BUG: `dafny_synthesis_task_id_80__
  tetrahedralNumber` (`t_v := n*(n+1)*(n+2) / 6`, ensures the identical
  expression back -- otherwise a trivial reflexivity-shaped task). Lowering
  raises `NotImplementedError: rocq lowering: identifier 't_v' collides
  with the lowering's namespace`, from `_ck` (the RESERVED/`_len`/`sf_`/
  `t_`-prefix check every param and return name passes through in `Ctx.
  __init__`): the task's OWN return variable is named `t_v`, colliding with
  `t_` (the file's own certificate/tactic namespace prefix, `t_w_*`, `t_H`,
  `t_dis`, ...). This is the SAME named, intentional refusal every other
  RESERVED-collision case in this file already takes (`fst`/`snd`/`pair`'s
  own 2026-09-10 note, above, gives the identical reasoning: silently
  parsing and shadowing a load-bearing name would be worse than a clean,
  immediate abstain). Not attempted: relaxing the reservation would need
  either a hygienic per-identifier rename scheme (a wider, unmeasured
  change touching every binder site in this file) or narrowing `t_` to
  the SPECIFIC names actually used (`t_w_`, `t_H`, `t_dis`, ... rather than
  the whole prefix), neither of which this session's scope covers for one
  task; correctly abstain, unchanged.

  (5) THE TIMEOUT, UNCHANGED, NOT RE-MEASURED THIS PASS BECAUSE NOTHING
  IN EITHER FIX CAN REACH IT: `seng2011_tmp_tmpgk5jq85q_flex_ex2__max`
  (no spec_funs, no pair, no nested seq, no bool loop state reassigned --
  confirmed directly from its own JSON) is the SAME load-sensitive/
  proof-cost reading the first pass's own (5) already established (a
  forall-plus-exists ensures over a seq, near the 180 s budget's edge,
  min_max's own precedent). Re-running it costs three-plus minutes of
  wall clock on a shared box for a task neither of this pass's fixes
  could possibly change; left exactly as read, per this session's own
  "leave unless the cause is cheap" instruction.

  REGRESSION (`t/tasks/*.json`, all 23, flake 3, one cell at a time,
  `run_par.lower_and_dispatch`, jobs=1, present={"rocq"}), run TWICE: once
  against fix (1) alone (baseline, confirming the parameterless-certificate
  change touches nothing else), once against both fixes together. Both
  runs: 22 of 23 read verified/refuted, matching AGREEMENT.md's rocq
  column exactly, byte for byte in outcome and witness (e.g. divmod_pair's
  wrong-var twin at x=1, y=1, swap's undefined witness at s=[0], i=0, j=0,
  tail's slice-bounds witness); `min_max` reads timeout/refuted both times,
  the SAME load-sensitive reading AGREEMENT.md already records, not a
  regression. `digit_sum` (uses `t_eqs_h`, the hypothesis-position half of
  fix (2), single int param `dsum`), `factorial`/`fib` (single int param
  each), `gcd` (two int params, INELIGIBLE, confirmed untouched), and
  `count_matches` (a seq param, INELIGIBLE, confirmed untouched) all read
  their own prior witness unchanged. No committed task's own witness or
  timing class changed by either fix.

  WHAT STAYS OPEN, BY NAME, SECOND PASS: `dafny_verify_tmp_tmphq7j0row_
  dataset_error_data_real_error_iseven_success_1__is_even` (real unproved
  -- a bool-headed spec_fun result needs a case split nothing here
  provides, (3) above; an attempted general fix measured UNSAFE and was
  not landed); `nitwit_tmp_tmplm098gxz_nit__max_nit` (real unproved -- a
  ground spec_fun fact needs propagating past an `is_var` guard, the SAME
  family of gap, same unsafe attempt, (3) above); `m2...computeSum`'s twin
  and self-recursion sibling `...aula2__mystery1` (real unproved, THE
  no-companion-spec_fun self-recursion gap the first pass's own (4) named,
  untouched by anything in this pass: no spec_fun exists for `apply IH`'s
  merge machinery to reach in the first place); `seng2011...flex_ex2__max`
  (real timeout, unchanged, (5) above). Of the eight sole-blocker tasks
  named at the top of this note, THREE now read COUNTS in full (f1a__f,
  ghost__m, computeSum) and one is a correct, unchanged abstain
  (tetrahedralNumber, not a defect); four stay open, each traced to its
  own directly-read stuck goal, none of them a lowering crash or a masked
  error.

  THE SIX SOLE-BLOCKERS, THIRD PASS (2026-09-10, COVERAGE-lifted-785.md's
  THIRTEENTH sweep: rocq alone keeps 6 of the 72 six-of-seven lifted tasks
  out of all seven -- tetrahedralNumber, is_even, invertArray, max_nit,
  max, mystery1). ONE now reads COUNTS; the other five stay exactly as
  read, four of them unchanged from the second pass above and named there
  already, one (invertArray) re-measured alone as instructed and found to
  read the same.

  MAX_NIT, CLOSED. Both gaps this session's own brief named --
  `nitness`'s `sf_valid_base b` (a ground fact needing SUBSTITUTION) and
  is_even's `sf_even i` (a bool-headed application needing a CASE SPLIT)
  -- trace to the identical root cause: `t_sat1`'s merge/E-matching arms
  all require `is_var` on the applied head, and a global spec_fun
  Definition never is one, so nothing propagates a fact ABOUT a spec_fun
  application, ground or derived, to another occurrence of the SAME
  application. A prior session's attempt at a fully generic fix, `H : ?X
  = true |- context [?X] => rewrite H`, is named in this file's own
  second-pass note as MEASURED UNSAFE (an unguarded head can fire on a
  state-variable equality at the wrong occurrence and corrupt an
  unrelated goal). Built instead, the narrow version the brief asked for:
  one match arm PER bool-result spec_fun, keyed on that spec_fun's own
  Coq constant name (`sf_{f}`, never a variable, never any OTHER task's
  spec_fun) --

    | H : sf_valid_base ?a0 = true |- context [sf_valid_base ?a0] =>
        rewrite H

  (and the `= false` / hypothesis-position twins) -- generated per task
  from `bool_sf`, the (name, Coq-arity) list `emit_spec_funs` now builds
  alongside `norm_names` (fix (2)'s own `ring_simplify` list, the SAME
  shape, one row earlier in the file). `?a0 .. ?a{k-1}` binds the
  spec_fun's own Coq arguments (a seq param counts as two, matching
  `atxt`); no arity or param-type guard is needed the way `ring_simplify`
  needed one, since a plain `rewrite` is safe for any shape -- a
  mismatched arity or type simply never unifies, and `repeat match ...
  end` with zero firings is a no-op, never an error. Joined into `t_eqs`
  (goal position, chained after the existing unfold/`ring_simplify`
  steps, so it meets whatever THOSE already exposed) and `t_eqs_h`
  (hypothesis position) the same way fix (2)'s own norm/norm_h pair is.
  MEASURED alone this closed HALF of max_nit: `nitness`'s own conjunct,
  once `sf_nitness_eq` unfolds it, exposes `sf_valid_base b` in the GOAL,
  substituted to `true` by the new arm -- but the surviving goal (`0 <=?
  b - 1` is not lia-decidable from `b >= 0` alone) still needed the
  ARITHMETIC `valid_base` is opaque about (`b >= 2`), which only
  unfolding `valid_base`'s own equation IN THE HYPOTHESIS (`t_eqs_h`)
  exposes -- and `t_dis`/`t_side` had never tried `t_eqs` and `t_eqs_h`
  TOGETHER on the same goal, only as mutually exclusive alternatives (the
  digit_sum note explains why combining them at the SAME occurrence can
  grow a rewrite without converging; here they target DISJOINT
  occurrences of the same spec_fun, goal vs. hypothesis, so there is no
  such chain). Added one more `solve [...]` alternative, tried LAST, to
  both `t_dis` and `t_side`: `solve [ t_eqs; t_eqs_h; t_vc0 ]`. Together,
  MEASURED (`harness.run_task`, flake 3, alone): max_nit now reads
  VERIFIED/REFUTED (off-by-one twin, witness b=2, real 1 vs twin 0),
  where the second pass left it unproved/refuted. Every task that already
  closed via `t_vc0`, `t_eqs;t_vc0`, or `t_eqs_h;t_vc0` alone reaches
  neither new alternative, unchanged.

  IS_EVEN: ATTEMPTED FURTHER, MEASURED WORSE, REVERTED. The ground arms
  above run ONCE, before `t_vc0`/`t_base` ever starts searching, so they
  never see a fact `t_base`'s own saturation loop has not derived yet --
  and is_even's own `sf_even i = true` is exactly such a fact, derived
  MID-SEARCH by `t_sat1`'s PRE-EXISTING "resolve an implication whose
  antecedent is leaf-provable" rule acting on the loop invariant once `r`
  is a concrete literal (`true = true <-> sf_even i = true` poses `sf_even
  i = true`). Tried: the identical ground arms, ALSO emitted as a new
  `t_sf_ground`, dispatched from `t_base`'s own `repeat (first [...])`
  via `Ltac t_base ::= ...` (Coq's redefinition form; MEASURED to work at
  top level, a later definition's own callers picking up the LATEST bound
  tactic even when they were themselves defined earlier -- confirmed with
  a 6-line standalone probe before touching this file), guarded to fire
  only when `bool_sf` is non-empty so every task without a bool spec_fun
  keeps `t_base`'s PRELUDE-static definition, untouched. MEASURED: this
  reached the derived fact and DID progress the goal one step further
  (`negb (sf_even i) = true` rewrites to `negb true = true`, i.e. `false
  = true`, a `congruence`-shaped contradiction) -- but it did not CLOSE
  is_even, and it cost real time getting there: is_even's own real side
  went from a clean UNPROVED to TIMEOUT, the widened `t_base` search
  (one more alternative tried on every `first`, every `repeat` round, of
  every goal in the file) spending the 180s wall without finishing. Not a
  correctness regression (no committed or lifted task's VERDICT changed
  for the worse, confirmed below), but a proof-cost one on the very task
  it targeted, for zero proof gained -- reverted before landing; the diff
  this session keeps has no `t_sf_ground`, no `Ltac t_base ::=`, and
  `is_even` reads exactly what it read before this pass, UNPROVED/REFUTED
  (re-confirmed after the revert, not assumed). Left open, same gap
  named in the second pass above: a bool-headed spec_fun application
  needs a genuine case split (`destruct (sf_even i)`-shaped), which
  substitution alone -- narrow or general -- does not provide once the
  needed fact is not literally sitting in a hypothesis the SAME shape
  reaches.

  INVERTARRAY, RE-MEASURED ALONE AS INSTRUCTED: still TIMEOUT/REFUTED,
  the SAME reading COVERAGE-lifted-785.md already records, not a
  regression. This task has no spec_fun at all (gate "loops", a plain
  seq in/seq out reversal with three `forall` invariants and one `div`),
  so nothing either change above could possibly touch it; read directly
  (no probe needed, its own three-forall-plus-div shape and the box's own
  load average 14-21 across this session's later measurements is the
  same "near the search budget's edge" reading `max`/`min_max` already
  established for a different task), no lowering gap found, left exactly
  as read, per this session's own "leave unless the cause is cheap"
  instruction.

  MAX, MYSTERY1, TETRAHEDRALNUMBER: untouched, named, unchanged from the
  second pass above (`max`: real timeout, load-sensitive proof cost;
  `mystery1`: real unproved, the no-companion-spec_fun self-recursion gap
  `apply IH` cannot bridge; `tetrahedralNumber`: a correct, intentional
  `t_v`-collides-with-`t_`-namespace abstain, not a defect). None of this
  pass's two changes (the ground-fact substitution fix, landed; the
  `t_base`/`t_sf_ground` widening, attempted and reverted) reaches any of
  the three: no spec_fun (max), no bool spec_fun (mystery1 has none at
  all), or lowering never runs far enough to reach either tactic
  (tetrahedralNumber's own `_ck` refusal fires before any proof script is
  even generated).

  REGRESSION (`t/tasks/*.json`, all 23, flake 3, `run_par.lower_and_
  dispatch`, jobs=1, present={"rocq"}): 22 of 23 read verified/refuted,
  matching AGREEMENT.md's rocq column exactly, byte for byte in outcome
  and witness (divmod_pair's wrong-var twin at x=1,y=1; swap's undefined
  witness at s=[0],i=0,j=0; tail's slice-bounds witness; every other task
  the same); `min_max` reads timeout/refuted, the SAME load-sensitive
  reading AGREEMENT.md already records, not a regression. Also re-run,
  the other three lifted tasks with a bool-result spec_fun besides
  max_nit/is_even (`nit_add`, `nit_increment`, the only other lifted
  tasks `bool_sf` is ever non-empty for): both read unproved/refuted,
  identical to COVERAGE-lifted-785.md's own row for each, unchanged. Spot-
  checked two lifted tasks with an INT-only spec_fun (`bool_sf` empty,
  the ground arms a no-op string) for a lowering crash or shape change:
  neither errored, both lowered and dispatched normally (ComputeFact
  unproved/refuted, sum verified/refuted), consistent with `bool_sf`
  empty being a pure no-op as designed.

  NET: rocq's sole-blocker count moves from 6 to 5 (max_nit leaves the
  list); tetrahedralNumber, is_even, invertArray, max, mystery1 remain,
  each for a distinct, already-named reason, none of them a lowering
  crash, a masked error, or a regression against the committed matrix.

  CONFORMANCE.md's rocq FAIL cells, own column (2026-09-11, ROADMAP 13.4,
  fz_p_ret_falsens/fz_p_seqeq_false/fz_p_vac_unsat/fz_p_vac_range). Two
  gaps closed here (both in `_loop_def`/`_value_cert`, this file; the
  vacuity gap is entirely in verifiers/rocq.py, its own dated note):

  EARLY-EXIT VALUE CERTIFICATES. `_loop_def` (a certificate's own twin-
  loop Fixpoint builder) had no early-exit model at all: a `return` inside
  a witnessed loop was silently DROPPED, computing the loop's post-exit
  state instead of the returned value -- the wrong value at a witness
  whose whole point IS the early exit. `_try_cert_v1` catches whatever
  followed (a wrong `cbv; reflexivity` or an outright exception) and
  falls back to None, so the certificate was never built and the fallback
  plain lowering tried to prove the task's `ensures` UNIVERSALLY, false
  by construction for fz_p_ret_falsens (an adversarial probe) -- UNPROVED,
  never REFUTED. Fixed by mirroring `gen_loop`'s own early-exit branch
  (the two-outcome `(state, bool)` Fixpoint, gated on the SAME `_DONE`-
  derived `step_done` gen_loop already computes) inside `_loop_def`,
  minus the induction lemma a certificate's `cbv`-at-the-witness proof
  never needs. `fz_p_ret_falsens` moves unproved/unproved -> refuted/
  refuted (real, matching its twin).

  SEQ-RETURN VALUE CERTIFICATES. `_value_cert` abstained outright on any
  seq-typed return ("no committed task needs it yet"); `fz_p_seqeq_false`
  does (SPEC.md's own `r == s` extensional seq equality, refuted at a
  concrete witness s=[0], real r=[1]). Added a seq-return branch: the
  `stmt` (the negated ensures) is built exactly as `cx.prop` already
  renders any seq `==`, unchanged; only the PROOF is bespoke, since
  `t_dis`'s generic search has no arm for a seq-extensional `forall` (the
  reason the whole ensures reads UNPROVED without a certificate).
  `decompose [and]` flattens the conjunction WITHOUT reducing anything
  first (a standalone probe measured `cbv` before decompose unfolding
  `Z.le`/`Z.lt` into raw positive-number matches the `repeat match`
  pattern no longer recognises -- MEASURED WRONG, read UNPROVED, "Cannot
  find witness"); the length-equality hypothesis decompose leaves
  UNREDUCED is exactly what the specialize step's own `ltac:(lia)` bound
  proof needs (lia substitutes through a symbolic-atom equality with no
  reduction). The differing index is computed in Python from the actual
  witness values (a real index when the ensures compares `ret` against a
  seq param, else 0, still correct whenever a LENGTH mismatch alone
  closes the goal). `fz_p_seqeq_false` moves unproved/refuted -> refuted/
  refuted (real).

  BYTE IDENTITY. Both fixes sit entirely behind `witness is not None` in
  `lower()`'s own dispatch (`_loop_def`/`_value_cert` are reachable only
  from `_try_cert_v1`, itself only tried when a witness is present); a
  committed task's plain lowering (`witness=None`, every `run_par`/
  `grade.py` call for a committed `t/tasks/*.t`) never enters either
  changed function. MEASURED: all 34 `t/tasks/*.t`, relowered before and
  after both fixes, byte-identical (`diff -rq`, zero differences); the
  five-task regression (abs, gcd, sum_upto, count_vowels, reverse, flake
  3) reads verified/refuted for every one, matching AGREEMENT.md's rocq
  column and CONFORMANCE.md's committed rows exactly, witness included.

  STILL OPEN, NAMED, NOT ATTEMPTED HERE OR REVERTED AFTER MEASURING
  UNSAFE. fz_p_pair_seq: `pair_comp_ty`'s own NAMED refusal (this file's
  PAIRS (v1) note, above) for a seq pair-component; unchanged, abstain/
  abstain. fz_p_str_splitempty (unproved with the same message, measured by the
  independent check on 2026-09-11 and omitted from this note's first
  draft), fz_p_str_countempty/fz_p_str_findempty/fz_p_str_tab/
  fz_p_str_lowernonletter: all five need a NEW general fact (count(s,[])
  == len(s)+1, find(s,[])==0, or a from-scratch ground computation of
  `split`/`lower` on a literal) that `t_dis`'s search has no rule for;
  coqc's own message on every one is identical: "Tactic failure: unsolved
  t verification condition." A fix WAS built and MEASURED to work
  (t_count_list_empty/t_find_list_empty/t_list_zero, three lemmas plus
  four t_inv1 match arms) but then REVERTED: PRELUDE (`header()`'s own
  text, everything from `t_leaf` through `POST_SF`) is ONE block emitted
  UNCONDITIONALLY for every task regardless of features used (measured:
  adding those lines moved EVERY committed task's lowered bytes, 32 of
  34, divmod_pair -- no string-lib member anywhere in it -- included),
  not the per-task-gated (`_has_strlib`-style) growth this file's other
  PRELUDE additions are. Closing this gap without moving a committed
  cell needs the SAME gating discipline applied to `header()`'s own
  assembly, not merely to the new lemmas' content; left for that pass.

  ENSURES-LEVEL UNDEFINEDNESS (2026-09-12, ROADMAP 13.4, "the four
  ensures-level probes"): fz_p_at_oob/_at_neg/_at_zero have a TOTAL body
  (they only branch on `len(s)`) and an unguarded `at` inside `ensures`
  itself, so the real program is undefined there at every input, not in
  the body -- the body-level "undefined" witness class `_undef_cert`
  (below) already certifies does not apply; nothing in the body is
  undefined for `_first_undef_body` to find. harness.real_witness in
  this worktree has no ensures-level case of its own (its two loops
  only catch an Undef the BODY raises); its FIRST loop's
  `ref._breaks_ensures` does happen to catch the Undef `ensures`
  itself raises here, but reports it as a "value"-kind witness with
  `_ens` True and `_real`/`_twin` both the real body's own (irrelevant)
  return value, a shape `_value_cert` cannot turn into a certificate
  (the totalized `at` makes the totalized `==` trivially TRUE, nothing
  false to prove) -- MEASURED: `_try_cert_v1` returns None for all
  three, `lower()`'s normal fallback then reads UNPROVED, not REFUTED.
  Fixed with a purely local addition, `_real_ensures_undef_witness`
  (below `_first_undef_body`): the SAME bounded interp.domain scan
  real_witness's own second loop runs, but checking each `ensures`
  clause (not the body) for Undef after the body completes, returning
  the class this file's task instructions describe -- `_kind`
  "undefined", `_real` "no value", `_site` "ensures", `_expr` the
  offending clause, no `_twin` -- consumed by a new branch in
  `_undef_cert` that runs `_first_undef` on `_expr` directly (the body
  has nothing to walk) instead of `_first_undef_body`'s statement scan.
  `lower()` tries this AFTER its existing witness-first attempt comes
  back empty (real_witness's quirky "value" witness included), on the
  real side only. Measured: fz_p_at_oob/_at_neg/_at_zero all move
  real UNPROVED -> REFUTED (matching `_expect`); fz_p_at_body
  (genuinely body-level undefined) is unchanged, already REFUTED
  before this pass. Byte identity: all 34 committed t/tasks/*.t
  lowered before and after hash IDENTICAL (the new scan returns None
  for every one of them, the fallback never fires). t/verifiers/rocq.py
  needed NO change: its REFUTED door is already "the declared goals
  include t_refutation_certificate, kernel-proved" regardless of which
  class of fact that theorem states, so the new certificate reads
  REFUTED through the exact door twin refutations already use,
  matching framac's own defs()-companion behaviour on this class per
  this task's own instructions. Not attempted this pass, left open by
  name: the PRELUDE feature-gating split (the paragraph just above)
  and the five string-library probes it blocks
  (fz_p_str_countempty/_findempty/_splitempty/_tab/_lowernonletter) --
  out of scope for "the four ensures-level probes," not touched here.

  THE PRELUDE FEATURE-GATING SPLIT, DONE (2026-09-12, ROADMAP 13.4:
  "rocq: the prelude by feature, then its string facts"). The gap named
  just above is closed: `header()` now takes `(task, body)` and calls
  `_uses_strlib` (`lower_fstar.py`'s own gate, ported verbatim -- a
  generic dict/list walk for an `{"op": <member>, ...}` node whose op is
  in `STRLIB_OPS`, run over both the task dict and the body list) to
  decide whether to splice in `_STRLIB_DEFS`/`_STRLIB_GOAL_ARMS`/
  `_STRLIB_HYP_ARMS` -- the three places, found by textual boundary
  (this file's own "insert only" convention for every prior PRELUDE
  growth), where "The string library (v1)" added text to the old
  monolithic `PRELUDE`: the bridge Definitions/Lemmas block
  (`seq_to_list` through `endswith_list`), `t_inv1`'s goal-side match
  arms (right before its `| _ => progress subst` catch-all), and its
  hypothesis-side mirrors (right before `t_inv1`'s closing `end.`).
  `PRELUDE_CORE_1`..`PRELUDE_CORE_4` are the four surrounding chunks,
  always emitted, byte-identical to their slice of the old `PRELUDE`.

  MEASURED (relower all 34 committed `t/tasks/*.t`, rocq, before this
  date's `lower_rocq.py` vs after, `diff -rq`): 29 of 34 lose EXACTLY
  the string block (each a clean 3-hunk pure deletion, zero additions,
  matching `_STRLIB_DEFS`/`_STRLIB_GOAL_ARMS`/`_STRLIB_HYP_ARMS`'s own
  three text ranges one for one); 5 are untouched byte-identical
  (`abs.t`/`max.t`, both `t: 0` tasks that never call `header()` at
  all, plus `count_vowels.t`/`split_join.t`/`word_count.t`, the three
  committed tasks that DO use a string-library member, so the gate
  keeps the block for them). `t/grade.py --tasks <the ten named tasks>
  --kernels rocq --flake 3` (single kernel, so grade.py's own two-
  kernel agreement door REFUSES to write a table -- read per task via
  `t/cli.py verify --kernels rocq` instead) reproduces AGREEMENT.md's
  rocq column exactly for all ten: abs/gcd/sum_upto/count_vowels/
  reverse/word_count/divmod_pair verified/refuted, split_join verified/
  unproved, min_max verified/refuted at a wide-enough timeout budget
  (AGREEMENT.md's own "timeout" cell -- this box is slow enough that
  cli.py's default per-call budget alone reads REFUSED there, not a
  regression), row_max_len verified/refuted (needed close to 590s wall
  on this shared box before this pass's SMALLER file, unrelated to the
  gating: the same task under the OLD ungated `lower_rocq.py`, carrying
  MORE unrelated text, cannot be faster).

  THE STRING FACTS, THREE OF FIVE. `fz_p_str_countempty`/
  `_findempty`/`_splitempty` (fuzz_lower.probes(), graded the same way
  conformance.py's `probe_manifest()`/`run_items()` would restrict to
  rocq: build each probe's real/twin sources with `lower_rocq.lower`,
  verify with `verifiers.rocq.verify` via `verifiers.cell_pair`) move
  UNPROVED -> VERIFIED. SPEC.md's own closed-form identities for an
  EMPTY pattern are already a Fixpoint BASE CASE (`count_go`'s `t = []`
  arm returns `Z.of_nat (length s) + 1` directly; `find_go`'s returns
  `i`, called at `i = 0`; `split_ws_acc`'s `s = []` arm returns `[]`
  when the accumulator is also `[]`) -- `t_count_list_empty`/
  `t_find_list_empty`/`split_ws_list_empty` are each `reflexivity`, one
  unfold, not a hard proof once `t_dis`'s search had a rule reaching
  for them. The empty-seq ARGUMENT renders as the generic bridge
  `t_list ?g 0`, not a bare `[]` literal (`fz_p_str_countempty`'s own
  `s.count([])`'s second argument, the seq literal `[]`, still goes
  through `seq_fn`/`t_list` like any other seq), so `t_list_zero`
  (`t_list f 0 = []`, `Z.to_nat 0` a literal `O` by construction) has
  to fire FIRST, in both `t_inv1` polarities, before the three empty-
  pattern facts can match; `split_ws_list`'s own result additionally
  left a bare `length (@nil ?A)` in the goal once reduced (`A` left
  polymorphic on purpose -- the nested seq<seq> case needs `@nil (list
  Z)`, not `@nil Z`, a MEASURED miss on the first attempt: a
  `@nil Z`-typed arm never matched `length (@nil (list Z))`, and
  `t_dis` read UNPROVED with no other symptom until `Show` after a
  manual `t_base` repeat isolated the exact stuck goal), closed by one
  more arm, `cbn [length]`, since `length` itself is not one of this
  file's opaque functions.

  ALL FIVE OF FIVE, DONE (2026-09-11, ROADMAP 13.4's rocq item).
  `fz_p_str_lowernonletter` needed exactly the `map_nth`-shaped pointwise
  bridge named above (`t_of_list_lower_get`/`length_lower_list_t`, this
  file's own "lower / upper / ..." section) PLUS one more thing the note
  above did not anticipate: `lower_c` (a plain `Definition`, not a
  Notation) is opaque to `t_leaf`'s `lia`/`assumption`/`congruence`/
  `discriminate`, and MEASURED, `cbn [lower_c]`/`cbn [is_upper_letter]`
  (the name-whitelist form) does NOT inline either on this Rocq (9.2) --
  confirmed standalone (`Goal (if is_ws 65 then 1 else 2) = 2. cbn
  [is_ws].` leaves `is_ws` standing; `unfold is_ws` inlines it in one
  step). The fix is `unfold lower_c, is_upper_letter` (not `cbn`),
  feeding the exposed `<=?`/`&&`/`if` back into `t_leb_case`/`t_bred`'s
  own EXISTING arms rather than trying to re-derive a computation step
  of their own.

  `fz_p_str_tab` needed the SAME `unfold`-not-`cbn` fix for `is_ws` (a
  length-3 literal reified to its 3 concrete elements by a new
  `t_list_lit3` lemma, the same one-length-special-case shape
  `t_list_singleton` already has for length 1), PLUS a SEPARATE, more
  consequential gap: `t_seq_eqb_case` (PRELUDE_CORE_2, ALWAYS present,
  not gated to the string block) unconditionally `destruct`s into two
  branches without first trying the cheap ground-computation route
  `t_ltb_case`/`t_leb_case`/`t_eqb_case` already have (their own leading
  `replace ... by lia` arm) -- for a fully CLOSED `t_seq_eqb n f g`
  (fz_p_str_tab's own shape, no parameter anywhere), `destruct` still
  produces BOTH goals (Coq does not decide which constructor "actually"
  holds until something forces the reduction), and the "false" branch's
  own evidence, once ground `f`/`g` are genuinely equal, is a
  self-contradictory `~ (forall k, ...)` this file's search cannot
  discharge (finding a witness needs `intros`+`lia`+`reflexivity`, not
  `t_go`'s `apply H` step, which needs the goal to already BE `False`).
  MEASURED: fz_p_str_tab timed out past 90 s on this shared box without
  a `reflexivity`-first fast path in `t_seq_eqb_case`; adding one closes
  it in low single-digit seconds, and is safe everywhere else the same
  way the other case-split tactics' own leading `lia`-arm already is
  (`reflexivity` failing on a non-ground pair falls straight through to
  the original three-branch `destruct`, unchanged).

  `fz_p_pair_seq` moves abstain/abstain -> verified/unproved.
  `pair_comp_ty`'s own refusal (just below) is LIFTED for a seq
  component: `((Z -> Z) * Z)`, the model's own (function, length) pair
  wrapped as ONE Coq value -- exactly `Ctx.nested_fn`'s own row codomain,
  one level up. Measured CONTAINED, as this note's prior pass hoped:
  `pair_ty`, `param_binders` and `Ctx.ty`'s `fst`/`snd` case all already
  route through `pair_comp_ty` (or, for `ty()`, generically through the
  declared pair type) with NO other change; the one real gap was
  `Ctx.seq_fn`, which had no `fst`/`snd` case at all (a seq PROJECTED
  out of a pair reached `seq_fn`'s bare `raise ValueError`, not this
  refusal) -- one new case there, mirroring `nested_fn`'s own `at` case
  (a literal Coq pair read back via `fst`/`snd`), closes it.
  `pair_comp_eq_fn` is UNCHANGED, still a named refusal (SPEC.md's pair
  `==`/`!=` needs a two-argument decidable equality per component,
  `t_seq_eqb`'s own shape takes a length as a THIRD argument; unneeded
  by `fz_p_pair_seq`, which never compares two pairs, so left exactly as
  it was, its own separate, still-real, gap).

  TWIN SIDE, NOT ATTEMPTED, NAMED. `fz_p_str_lowernonletter` and
  `fz_p_pair_seq` now read verified/UNPROVED rather than the REFUTED a
  wrong-var mutation should in principle certify: MEASURED, their twin
  `.v` files carry the SAME `_t_spec` theorem shape as the real (no
  `t_refutation_certificate` goal), meaning `harness.real_witness`'s own
  witness-grounding route did not produce a certificate this lowering's
  refutation-certificate builder (this file's own "Refutation
  certificates" section, ROADMAP 10.7) can grow into a proof for THESE
  two witness shapes (a forall-over-range ensures for the first, a
  guarded `at` through a pair projection for the second) -- an HONEST
  verified/unproved reading per that section's own stated convention
  ("a witness kind this lowering cannot ground ... yields no certificate
  and the cell honestly reads verified/unproved"), not a regression: the
  REAL side is what ROADMAP 13.4 named as this item's own open cell, and
  it is fixed; the twin side is a separate, not-yet-attempted gap, named
  here rather than silently left. `fz_p_str_tab`'s own twin, by
  contrast, DOES read refuted (MEASURED): its witness is a plain "at an
  out-of-guard index" shape the certificate builder already grounds.

ROADMAP 16.2, rocq's own rows, 2026-09-11. Re-measured before touching
anything (t/COVERAGE-lifted-785.md's own rocq cells, dated 2026-09-10,
were a day stale): the 59-task ds59-lifted set and the 15-task ds15-new
set, both graded in rocq+dafny at flake 3. Three real causes, largest
first, each fixed in the lowering/prelude, never by relabeling a verdict:

  1. INVARIANT-DROP, EXIT WITNESS, 8 of 15 ds15-new tasks (appendArrayToSeq,
     arrayToSeq, getFirstElements, elementWiseDivide, addLists,
     squareElements, findSmallest, smallestListLength; two more,
     containsK/isSmaller, PRESERVATION-witness siblings out of this wave's
     scope, turned out to share the cause and were fixed as a side effect).
     Shared shape: a prefix-declared int local (`h := |a|`) held fixed as
     the loop's own upper bound while another variable walks up to it.
     `gen_loop`'s invariant set never carried `h = a_len` -- only ever
     `i < h` (the guard) and `i <= |a|` (a sibling invariant) separately --
     so the loop body's own array-index definedness lemma (needing the
     STRICT `i < a_len`) had no way to combine them. Fixed by threading one
     synthetic `h == <its own init expression>` invariant per such local,
     through the SAME `cx.prop`/`cx.defs` calls (and `invariants_ast` list)
     every other invariant already goes through -- gated on the shape
     itself (a prefix int local the loop body never reassigns), so a task
     without one computes an empty list and renders byte-identical to
     before this existed. All 8 read real=unproved before, verified after
     (grade.py, flake 3, measured).

  2. NO CERTIFICATE REACHABLE, PLAIN SEQ RETURN, 1 task (swap, task_id_257).
     `_plain_def`'s seq-return branch bailed outright with a comment
     ("_value_cert ... abstains on a seq return outright") that was true
     the day it was written and stale since: `_value_cert` grew a seq
     branch (SPEC.md "Sequences as values (v1)", ROADMAP 13.4,
     fz_p_seqeq_false, 2026-09-11) that WANTS exactly the two-Definition
     (function half, length half) split `_plain_def` refused to build. A
     loop-free, non-recursive task with a seq return and a "value" witness
     had no certificate path at all -- `_try_cert_v1` returned None from
     `def_text is None` before ever reaching `_value_cert` -- so the twin
     fell back to the plain unprovable theorem: real=verified/twin=
     UNPROVED, not the REFUTED its own measured witness (a=0, b=1: real
     [1, 0], twin [0, 0]) already supports. Fixed by giving `_plain_def`
     the same split `gen_plain`/`gen_loop` already build. A second,
     smaller gap surfaced once the certificate was reachable at all:
     `_value_cert`'s seq-branch proof script only reduces a FORALL-shaped
     falsifying conjunct (`repeat match ... specialize ... cbv in H`); a
     concrete-index equation against a scalar (`result[0] == b`, swap's
     own shape, never wrapped in a forall) survived `decompose` unreduced,
     an opaque application `lia` cannot see through. One unconditional
     `cbv in *` between the match and the closing `lia` closes it, a
     no-op for the forall-shaped case (already `cbv`'d per-hit).

  3. NONLINEAR ARITHMETIC, 1 task (centeredHexagonalNumber): `3 * n *
     (n - 1) + 1 >= 0`, a product of two variables, is outside `lia`'s
     Presburger fragment; `nia` alone closes it (confirmed standalone).
     NOT added to the shared POST_SF prelude every task gets: MEASURED
     WRONG twice on the way here. Bare `nia` sent isPrime's own mod-
     shaped, genuinely unprovable goal into a search long enough to blow
     the whole file's 180s wall backstop by itself, turning a fast,
     honest UNPROVED into a TIMEOUT. Bounding that one call with `timeout
     5` still did, for isPrime AND containsSequence, from the ACCUMULATED
     cost of many bounded-but-failing 5s attempts across one file's many
     `t_dis` call sites. The fix actually landed: a SEPARATE prelude,
     POST_SF_NIA, spliced in only when `_has_nonlinear_mul(task)` finds a
     genuine variable-times-variable product (`n * 2` is ordinary linear
     arithmetic and does not trip it) -- every other task, isPrime and
     containsSequence included, keeps the original POST_SF, byte-
     identical, same discipline `_has_strlib`'s own gate already keeps.

  NOT ATTEMPTED, NAMED. task_id_586 (splitAndAppend, a rotate-by-`n mod
  |l|` shape): real=unproved, coqc's own "unsolved t verification
  condition" on the main theorem, needing case-split reasoning between
  `t_slice`/`t_app`'s own boundary and `t_mod`'s two cases that no
  existing tactic combination reaches -- a genuine capability gap, not a
  quick fix, left honest rather than papered over. task_id_262
  (splitArray, ABSTAIN: "a pair component of type seq is refused"),
  task_id_610 (removeElement, ABSTAIN: "more than one loop per body is
  not lowered yet") and task_id_80 (tetrahedralNumber, ABSTAIN:
  "identifier 't_v' collides with the lowering's namespace") are three
  separate, already-honest lowering-completeness gaps (a genuine `t_`
  literal user identifier colliding with the tactic/certificate
  namespace's own reserved prefix, in the last case), each its own
  feature to add, not this wave's cause. task_id_605 (isPrime) and
  task_id_598 (isArmstrong) keep their pre-existing timeout readings:
  isPrime's own goal is genuinely outside every tactic tried (see item 3
  above); isArmstrong's nonlinear cubic terms interacting with three
  chained div/mod occurrences were not attempted, named rather than
  guessed at. task_id_126 (sumOfCommonDivisors) and the twin sides of
  task_id_3, task_id_605, task_id_69, task_id_808 and task_id_809 are the
  PRESERVATION-witness family this wave's own brief named out of scope
  ("another builder's").

  Measured after (grade.py, flake 3): every task of both sets, the 34
  committed tasks against t/AGREEMENT.md's own rocq column cell for cell
  (no regression), and the rocq column of t/CONFORMANCE.md's own suite,
  before and after, diffed (0 FAIL cells lost or gained). See this
  session's own patch/report for the exact cells.

ROCQ-3, 2026-09-12 (ROADMAP 16.2's rocq item: "pair of seq, multi-loop,
the t_ collision, rotate by mod"). Two of the four closed, both grade.py-
confirmed (`--tasks <dir> --kernels rocq,dafny --flake 3`), one left named
rather than guessed, one out of this session's own item list:

  1. task_id_262 splitArray, ABSTAIN -> real=verified/twin=refuted. The
     ABSTAIN's own message ("a pair component of type seq is refused")
     was stale: `pair_comp_ty` already gives a seq pair COMPONENT a Coq
     TYPE, `((Z -> Z) * Z)` (ROADMAP 13.4, fz_p_pair_seq, a PARAM), but
     `comp_term` -- the only caller that builds a pair-VALUED TERM, `px`'s
     `pair` op, `r := (firstPart, secondPart)` -- still raised outright
     for a seq component, never revisited once `pair_comp_ty`'s own type
     side landed and never exercised by fz_p_pair_seq (a param is never
     built via a `pair` literal). Fixed by rendering the component as
     `(fn, len)`, `seq_fn`'s own (function, length) pair, the exact shape
     `seq_fn`'s existing `fst`/`snd` case already reads back OUT of a
     pair the other direction. dafny's own cell already read verified/
     refuted (off-by-one, arr=[], l=0); rocq now matches it exactly, same
     witness.

  2. task_id_80 tetrahedralNumber, ABSTAIN -> real=verified/twin=refuted.
     The task's own return is named `t_v`, colliding with this file's
     `t_`-prefixed certificate/tactic namespace (`_ck`'s RESERVED/prefix/
     suffix check, `Ctx.__init__`). `lower()`'s own `t_names.sanitize`
     call already renames away every `t_names.KEYWORDS["rocq"]` collision
     (Rocq's own reserved words) before `Ctx` ever runs, but `_ck`'s rule
     is a DIFFERENT, private convention that list never encoded, so
     `t_v` sailed through unrenamed and hit `_ck`'s raise. Fixed the way
     the file's own prior note said it could be (rather than widening
     `_ck` itself, which changes what counts as reserved for every other
     caller of `_ck` directly): computing the task's own declared names
     that WOULD trip `_ck` (prefix/suffix/RESERVED, the exact predicate
     `_ck` already uses) and folding them into `sanitize`'s `reserved`
     set for this one task -- `sanitize` does not care whether a name is
     in `reserved` because it is a language keyword or because it is
     this file's own private collision, so the existing rename mechanism,
     rename-map comment, and witness remap all apply unchanged. dafny's
     own cell already read verified/refuted (off-by-one, n=2); rocq now
     matches it, same witness.

  NOT ATTEMPTED, NAMED (both real capability gaps, not quick fixes):
  task_id_610 removeElement, ABSTAIN, unchanged ("more than one loop per
  body is not lowered yet"): `find_while`/`gen_loop` build ONE Fixpoint
  per task, deriving its own initial state from a straight-line prefix;
  removeElement's own body is two SEQUENTIAL top-level while loops
  sharing one index variable (loop 1 copies indices `[0, k)`, loop 2
  continues the SAME `i_v2` through `[k, len(s))`), which needs a second
  loop's own Fixpoint fed the FIRST loop's own final state as its initial
  one -- a genuine architectural extension to `gen_loop`'s single-loop
  shape (chained loop specs, not a bigger single Fixpoint), not
  attempted this session: the risk of a half-composed proof obligation
  reading VERIFIED on an unsound premise is exactly the failure this
  file's own honesty rules exist to keep out, and confirming a chained
  construction sound needs more room than this session had. task_id_586
  splitAndAppend stays real=unproved/twin=refuted, unchanged (a rotate-
  by-`n mod |l|` shape needing a case split between `t_slice`/`t_app`'s
  own boundary and `t_mod`'s two cases no tactic combination here
  reaches, named already by the pass above this one); not re-attempted,
  no new tactic tried.

  task_id_414 anyValueExists's own ABSTAIN ("a quantifier in
  computational position has no decidable lowering here") surfaced in
  this session's own before/after grading but is OUT OF this item's list
  (ROADMAP 16.2 names it separately) and needs its own feature (a
  decidable bounded-quantifier instance), not touched here.

  REGRESSION (grade.py --flake 3): the 34 committed tasks in rocq (and
  dafny, for a same-run cross-check) against t/AGREEMENT.md's own rocq
  column, cell for cell -- 33 of 34 read verified/refuted unchanged,
  min_max reads timeout/refuted unchanged (AGREEMENT.md's own recorded
  reading, a load-sensitive cell this session's fixes cannot reach: no
  pair, no `t_`-collision, no second loop, no rotate-by-mod in it). The
  rocq column of the full conformance manifest (conformance.build_manifest
  + run_items + grade, restricted to the rocq column only, flake 3): 66
  items, 0 FAIL before this session's changes, 0 FAIL after -- no PASS
  lost or gained. `python3 -m unittest test_lower_rocq`: 14 of 14, the 4
  new (`PairOfSeqComponentTest`, `TPrefixCollisionRenameTest`) plus the
  10 already there.

ROCQ-4, 2026-09-12 (ROADMAP 16.2's rocq item: "two sequential loops,
rotate by mod, the primes, the pair twin" -- tasks 610 removeElement, 586
splitAndAppend, 470 pairwiseAddition, 576 isSublist, 126
sumOfCommonDivisors, 3 isNonPrime, 605 isPrime, from
COVERAGE-lifted-785.md's own sweep-r21 findings). One classification bug
fixed in `t/verifiers/rocq.py` (this session's other file), everything
else measured and named rather than guessed at; no lowering feature in
`lower_rocq.py` itself changed this session.

  FIXED. task_id_126 sumOfCommonDivisors's own real side read MALFORMED
  (coqc's raw message `Error: No applicable tactic.`, one of
  `_loop_spec`'s `first [...]` branches raising before its own trailing
  `fail 1 "unsolved t verification condition"` is ever reached) though
  the file parses and resolves fine and only a LATER tactic script ran
  out of applicable branches on one goal -- the same "the engine stopped
  without a countermodel" event `UNPROVED_MARKS`'s four existing strings
  ("Tactic failure", "Cannot find witness", "Unable to unify",
  "unsolved") already name, previously falling through the unnamed
  catch-all two lines under `MALFORMED_MARKS` in `verify()`. Fixed by
  adding "No applicable tactic" to `UNPROVED_MARKS` (`verifiers/rocq.py`,
  see that file's own docstring and comment for the full account and a
  standalone-probe citation of the exact message). Measured directly
  (`verifiers.rocq.verify` on the task's own lowered `.v`, before/after):
  real malformed -> unproved, twin unchanged at refuted. A new
  regression test, `test_lower_rocq.NoApplicableTacticIsUnprovedTest`,
  reproduces the exact coqc message from a minimal `first [...]` with no
  branch's own `fail` message (standalone-probe-confirmed: Rocq 9.2
  raises `Error: No applicable tactic.` verbatim when every alternative
  of a `first` fails silently) so the fix stays covered independent of
  task_id_126's own proof script.

  MEASURED, NOT FIXED (each read the same both before and after the one
  fix above; no lowering change attempted for any of these, so none of
  their sources moved):
    - task_id_610 removeElement: ABSTAIN, unchanged ("rocq lowering: more
      than one loop per body is not lowered yet"). Its body is two
      SEQUENTIAL top-level while loops sharing one index variable, which
      needs `gen_loop`'s single-Fixpoint-per-task architecture extended
      to chain a second loop's own Fixpoint off the first loop's exit
      state (lower_fstar.py's `gen_loop_chain`, 2026-09-12, is the
      existing precedent for exactly two loops in another kernel) --
      confirmed, by reading `find_while`/`gen_loop` this session, to be
      a genuine multi-day architectural gap, not a quick fix: a
      half-composed chain that reads VERIFIED on an unsound premise (the
      second loop's own initial-state facts not actually proved from the
      first loop's real exit) is exactly the failure this file's honesty
      rules exist to keep out, and confirming a chained construction
      sound needs substantially more room than a classification fix.
    - task_id_586 splitAndAppend: real=unproved (coqc: "Tactic failure:
      unsolved t verification condition" on the main theorem), twin=
      refuted, unchanged. A rotate-by-`n mod |l|` shape needs a case
      split between `t_slice`/`t_app`'s own index boundary and `t_mod`'s
      two-case reading (`0 <= t_mod x y < |y|` from `t_mod_bound`, but
      WHICH of `t_slice`'s two arms a shifted index lands in still needs
      its own lemma joining the two) that no existing tactic combination
      in the PRELUDE's seq block reaches; ROADMAP 16.2's own brief names
      the fix (write the joining lemma in the prelude's seq block and
      wire it into `t_inv1`'s tactic match) but building and confirming
      it sound was not attempted this session, named rather than
      guessed at.
    - task_id_470 pairwiseAddition: real=verified, twin=TIMEOUT
      (unchanged; AGREEMENT.md does not carry this row, so there is no
      committed baseline to regress). Read the twin's own `.v`
      (`t_refutation_certificate`): `specialize (t_H t_w_a 0 t_w_result
      1 0); ...; t_feed t_H; t_dis` needs `t_div 0 2 = 0` (from
      `t_w_a`'s own `a_len := 0` substitution) to contradict the fed
      conclusion's `1 = t_div a_len 2`, a ground `t_div`/`t_mod` pair the
      file's own delta-whitelisted `cbv` path is DESIGNED to compute
      (see this file's own note on `t_div`/`t_mod`'s "GROUND (x, y) pair"
      detection, above) -- but `t_feed` must also discharge the
      certificate's own `forall k, 0 <= k < i_v -> ...` hypothesis at
      `i_v = 0` (vacuously true) before `t_dis` is even reached, and
      which of the two steps spins was not isolated this session (no
      `-time`/profiling run attempted); named as coqc's own wall
      backstop firing on this one theorem, not diagnosed further.
    - task_id_576 isSublist: real=unproved, twin=unproved, unchanged.
      Its own ensures is `(exists ...) -> True` (vacuously provable), so
      the failure is NOT the final theorem (which discharges fine) but
      `_loop_spec`'s own invariant-preservation step: coqc's exact
      message, re-measured standalone this session, is `Error: Tactic
      failure: unsolved t verification condition.` at the SAME `first
      [...]`'s `t_side`/`t_dis` combination named for task_id_126 and
      task_id_586 above, on a goal this session did not isolate further
      (the loop carries a `t_slice`-under-`exists` invariant, plausibly
      the same family of case-split gap as splitAndAppend's, but this
      was not confirmed by reading the specific failing goal).
    - task_id_605 isPrime and task_id_3 isNonPrime: real=unproved and
      real=timeout respectively (this session's own re-measurement;
      flake_check's noise floor plausibly swaps which of the two reads
      which run to run, both genuinely hard), twin=refuted for both,
      unchanged. ROADMAP 16.2's own brief names a divisor-bound lemma
      "of lower_fstar.py and lower_verus.py, proved in a prelude block
      gated by feature" as the fix; that lemma was not located and
      ported to `lower_rocq.py` this session (no prelude change made),
      so this stays a named gap, not a diagnosed-and-declined one.

  REGRESSION (grade.py --tasks tasks --kernels rocq,dafny --flake 3, the
  34 committed tasks): 34 of 34 read the SAME cell as AGREEMENT.md's own
  rocq column both before and after `verifiers/rocq.py`'s fix (33
  verified/refuted, min_max timeout/refuted) -- none of the 34 committed
  `.v` sources exercise the `else MALFORMED` catch-all this session
  touched, so none of their outcomes could move either way; this is a
  true regression check (measured twice, before and after, not inferred
  from the fix's own description). The rocq column of the full
  conformance manifest (conformance.build_manifest + run_items + grade,
  restricted to the rocq column only, flake 3, a standalone script
  mirroring `conformance.py main()`'s own driver calls): 66 items, 0
  FAIL before, 0 FAIL after -- no PASS lost or gained.
  `python3 -m unittest test_lower_rocq`: 15 of 15 (14 pre-existing plus
  `NoApplicableTacticIsUnprovedTest`).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                                 # noqa: E402
import interp                                  # noqa: E402
import names as t_names                        # noqa: E402
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

PRELUDE_CORE_1 = r"""(* persistent resolution marker: survives destruction of what it records *)
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

(* t_app / t_slice (2026-09-09): SPEC.md "Sequences: literals, concatenation,
   slices (v1)" adds `seq` (the literal `[e1, ..., en]`), `+` on two seqs
   (concatenation, the SAME operator token as int `+`, polymorphic by
   operand type exactly as `==` already is: `Ctx.ty` decides which one a
   `+` node is BEFORE `seq_fn`/`zx` is ever called on it, so this file
   never needs to case on operand type inside a single emitted term) and
   `slice` (s[a..b], DEFINED IFF 0 <= a <= b <= len(s)). Two more pieces of
   the same function+length model t_upd/t_fill already gave `update`/
   `fill` (2026-09-09, above): `t_app f g n` is the seq whose first `n`
   elements are `f`'s and whose rest are `g`'s, shifted (SPEC.md: "the
   sequence of length len(s) + len(t) whose element at i is s[i] for
   i < len(s) and t[i - len(s)] otherwise"); `t_slice f a` is `f` reindexed
   by `a` (SPEC.md: "the sequence of length b - a whose element at k is
   s[a + k]", the length itself computed at the call site as `b - a`, not
   carried by `t_slice`). Both are opaque top-level Definitions, never
   Notations (t_div/t_mod's own precedent): TOTAL in Rocq, so as with every
   other opaque seq op here, totality proves nothing about t's own
   undefinedness. `+`'s SPEC.md text is "always defined" (no obligation of
   its own; `defs()` still walks both operands for THEIR obligations, e.g.
   an `at` nested inside one), while `slice`'s `0 <= a <= b <= len(s)` is a
   definedness obligation in the same *_def_k calculus as `at`'s own
   `(0 <= idx < len)`, emitted at every `slice` node (`defs()`, below).

   `t_app_case` mirrors `t_upd_case`'s three-branch shape (try in-range
   directly by lia, try out-of-range directly by lia, else split and
   recurse on `k <? n`), the same `t_ltb_case` shape the boolean case
   splits already use, so it also fires on a NESTED t_app/t_upd (a
   concatenation of two literals, or a literal appended to a slice) one
   layer at a time, exactly the precedent `t_upd_case`'s own comment
   states for a nested update. `t_slice` needs no case split to read: SPEC.md's
   own definition is an unconditional index shift, no branch, so
   `t_slice_get` is a bare rewrite, the same shape `t_fill_get` already
   has.

   The LITERAL `seq(e1, ..., en)` itself gets no new opaque Definition or
   reading tactic at all: since n is always a concrete count at lowering
   time (the AST literal has exactly that many arguments), `seq_fn` builds
   it as a chain of `t_upd`s over `t_fill 0` (index 0 first, then 1, ...,
   then n - 1; `[]` is bare `t_fill 0` at length 0, its function value
   never read since nothing is in range), reusing t_upd_case/t_fill_get
   verbatim, the same multi-layer reduction swap's own nested update
   already exercises (probe_seq.v/probe5.v, 2026-09-09). *)
Definition t_app (f g : Z -> Z) (n : Z) : Z -> Z :=
  fun k => if k <? n then f k else g (k - n).

Definition t_slice (f : Z -> Z) (a : Z) : Z -> Z :=
  fun k => f (a + k).

Lemma t_slice_get : forall (f : Z -> Z) (a k : Z), t_slice f a k = f (a + k).
Proof. reflexivity. Qed.

Ltac t_app_case f g n k :=
  first
  [ replace (t_app f g n k) with (f k) in * by (unfold t_app;
      replace (k <? n) with true by (symmetry; apply Z.ltb_lt; lia);
      reflexivity)
  | replace (t_app f g n k) with (g (k - n)) in * by (unfold t_app;
      replace (k <? n) with false by (symmetry; apply Z.ltb_ge; lia);
      reflexivity)
  | let E := fresh "Eb" in
    assert (E : k < n \/ n <= k) by lia; destruct E as [E|E];
    [ replace (t_app f g n k) with (f k) in * by (unfold t_app;
        replace (k <? n) with true by (symmetry; apply Z.ltb_lt; exact E);
        reflexivity)
    | replace (t_app f g n k) with (g (k - n)) in * by (unfold t_app;
        replace (k <? n) with false by (symmetry; apply Z.ltb_ge; exact E);
        reflexivity) ]
  ].

(* t_seq_eqb (2026-09-09): SPEC.md "Sequences as values (v1)" makes `==`/
   `!=` on two seqs extensional (EQUALITY, above: a length equation
   conjoined with a bounded forall), which `prop()` already states directly
   since a Prop admits an unbounded forall; a seq `==`/`!=` in COMPUTATIONAL
   position (`bx()`) had no decidable lowering (the file's own EQUALITY
   comment: "no Fixpoint walks a symbolic length to compute a bool") and
   abstained. `t_seq_eqb` is that Fixpoint: a bounded recursion over
   `Z.to_nat n` (the SAME fuel-over-`Z.to_nat` idiom every loop/recursion
   Fixpoint in this file already uses, never a fresh recursion principle),
   comparing index `n - 1` down to `0` with `Z.eqb`, folded by `andb`. It is
   an opaque top-level Definition (never a Notation), the SAME shape t_upd/
   t_fill/t_app/t_slice/t_div/t_mod already have: cbn's whitelisted delta
   never unfolds it, and totality in Rocq (t_seq_eqb is defined for every n,
   f, g, including n < 0, where it is vacuously `true`) proves nothing about
   t's own use of it, which `bx()` only ever applies to a length already
   known nonnegative (MODEL, above: `0 <= s_len` accompanies every seq in
   scope).

   `t_seq_eqb_spec` is the two-directions-at-once statement `bx()` and the
   proof engine both need: `t_seq_eqb n f g = true <-> (forall k, 0 <= k <
   n -> f k = g k)`, proved unconditionally (no `0 <= n` side condition:
   both sides are vacuously true when n < 0, so the iff holds either way,
   one fewer obligation for `t_seq_eqb_case` below to discharge). It rests
   on an auxiliary lemma over the nat-indexed recursion,
   `t_seq_eqb_nat_spec`, by induction on the fuel; `t_seq_eqb_spec` itself
   case-splits only on the sign of n to relate `Z.of_nat (Z.to_nat n)` to
   n (`Z.to_nat`'s own definition: the `Zneg` case is `O` by construction,
   proved by `reflexivity`, not a library lemma whose exact name would need
   trusting).

   `t_seq_eqb_case` mirrors `t_beq_case`'s shape (an unconditional two-way
   split, no "try directly by lia" shortcut: unlike `t_ltb_case`/`t_eqb_case`,
   whether two whole seqs agree is not a fact lia can decide from raw
   context, however deep the case-split arms tried): `Sumbool.sumbool_of_bool`
   turns the boolean into a `{= true} + {= false}` disjunction, `replace ...
   in *` (the file's own convention throughout, `t_ltb_case` on down) then
   rewrites every occurrence in goal and hypotheses alike, and
   `t_seq_eqb_spec` immediately turns the true branch into the usable
   `forall k, ...` fact (`apply ... in`, the same move `t_dm1` makes with
   `t_div_mod_eq`) so `t_sat1`'s existing E-matching arms can instantiate it
   at whatever seq-application argument the goal needs; the false branch
   gets the fact's NEGATION the same way (through the iff's
   contrapositive), which is exactly what closes the false-branch case in
   the probe below, by the same `H : A -> False, D : A |- _` resolution
   step `t_sat1` already has for every other implication hypothesis. Joins
   t_inv1's match immediately after `t_slice`'s own two entries, goal and
   hypothesis position, ending in `t_bred_all` like every other boolean
   case-split tactic here (t_ltb_case/t_leb_case/t_eqb_case/t_beq_case),
   since `t_seq_eqb` typically sits inside the `andb` `bx()` composes it
   into (`(len s =? len t) && t_seq_eqb (len s) s t`) and that andb needs
   reducing once both operands are literals. *)
Fixpoint t_seq_eqb_nat (m : nat) (f g : Z -> Z) : bool :=
  match m with
  | O => true
  | S m' => andb (Z.eqb (f (Z.of_nat m')) (g (Z.of_nat m'))) (t_seq_eqb_nat m' f g)
  end.

Definition t_seq_eqb (n : Z) (f g : Z -> Z) : bool :=
  t_seq_eqb_nat (Z.to_nat n) f g.

Lemma t_seq_eqb_nat_spec : forall (m : nat) (f g : Z -> Z),
  t_seq_eqb_nat m f g = true <->
  (forall k : Z, 0 <= k < Z.of_nat m -> f k = g k).
Proof.
  induction m as [| m' IH]; intros f g; cbn [t_seq_eqb_nat].
  - split; [ intros _ k Hk; exfalso; lia | intros _; reflexivity ].
  - rewrite Bool.andb_true_iff, Z.eqb_eq.
    split.
    + intros [Hfg Hrec] k Hk.
      destruct (Z.eq_dec k (Z.of_nat m')) as [->|Hne].
      * exact Hfg.
      * apply (proj1 (IH f g) Hrec). lia.
    + intros H. split.
      * apply H. lia.
      * apply (proj2 (IH f g)). intros k Hk. apply H. lia.
Qed.

Lemma t_seq_eqb_spec : forall (n : Z) (f g : Z -> Z),
  t_seq_eqb n f g = true <-> (forall k : Z, 0 <= k < n -> f k = g k).
Proof.
  intros n f g. unfold t_seq_eqb. rewrite t_seq_eqb_nat_spec.
  destruct (Z.le_gt_cases 0 n) as [Hn | Hn].
  - replace (Z.of_nat (Z.to_nat n)) with n by lia. reflexivity.
  - assert (Hz : Z.to_nat n = 0%nat).
    { destruct n as [| p | p].
      - exfalso; lia.
      - exfalso; lia.
      - reflexivity. }
    rewrite Hz. split; intros _ k Hk; exfalso; lia.
Qed.

Ltac t_seq_eqb_case n f g :=
  first
  [ (* ROADMAP 13.4, 2026-09-11: a GROUND `n`/`f`/`g` (fz_p_str_tab's own
       shape: every argument closed, no parameter anywhere) decides by
       plain computation; tried first, the same "try the cheap direct
       route before destructing" convention `t_ltb_case`/`t_leb_case`/
       `t_eqb_case` already have (their own leading `replace ... by
       lia` arms) just above. Without this, `destruct
       (Sumbool.sumbool_of_bool ...)` below still produces BOTH goals
       for a ground, actually-true `t_seq_eqb n f g` (the ONE constructor
       Coq's own conversion checker would pick is not decided until
       something forces it), and the "false" branch's own evidence is a
       `~ (forall k, ...)` this file's search cannot discharge (finding
       a witness needs `intros`+`lia`+`reflexivity`, not `t_go`'s
       `apply H` step) -- MEASURED: fz_p_str_tab timed out past 90 s on
       this shared box without this arm, closes in seconds with it. *)
    replace (t_seq_eqb n f g) with true in * by reflexivity
  | replace (t_seq_eqb n f g) with false in * by reflexivity
  | let E := fresh "Es" in
    destruct (Sumbool.sumbool_of_bool (t_seq_eqb n f g)) as [E|E];
    [ let F := fresh "Ef" in
      pose proof (proj1 (t_seq_eqb_spec n f g) E) as F;
      replace (t_seq_eqb n f g) with true in * by (symmetry; exact E)
    | let F := fresh "Ef" in
      assert (F : ~ (forall k : Z, 0 <= k < n -> f k = g k))
        by (intros Hc; apply (proj2 (t_seq_eqb_spec n f g)) in Hc; congruence);
      replace (t_seq_eqb n f g) with false in * by (symmetry; exact E)
    ]
  ]; t_bred_all.

(* t_pair_eqb (2026-09-10): SPEC.md "Pairs (v1)" makes `==`/`!=` on two
   pairs componentwise (EQUALITY: "the polymorphic == again, two ints, two
   bools, two seqs, two pairs"), which `prop()` states directly (a plain
   Coq `=`/`<->` per component, the same shape `prop()` already gives a
   bare int/bool equality); a pair `==`/`!=` in COMPUTATIONAL position
   (`bx()`) needs a decidable bool, the same gap `t_seq_eqb` closed for
   seq. `t_pair_eqb` is GENERIC over the two component equality functions
   (this file's own `pair_comp_ty`/`_pair_eq_fn` only ever instantiate it
   with `Z.eqb`/`Bool.eqb`, since a pair component of type seq is refused
   there, SPEC.md's own rocq survey naming this kernel's product `Z * Z`;
   the shape below composes with `t_seq_eqb` exactly the same way had that
   refusal not been made, so the generic definition costs nothing extra
   now and nothing has to change here if a future note lifts it):
   `t_pair_eqb eqA eqB (a, b) (a', b') = andb (eqA a a') (eqB b b')`, the
   pointwise AND of each component's own equality test, the same shape
   `t_seq_eqb_spec`'s own `andb (Z.eqb ...) (t_seq_eqb_nat ...)` step
   already has. `t_pair_eqb_spec` is a fact about ANY `eqA`/`eqB` with the
   right correctness hypothesis, proved ONCE, generically, by destructing
   both pairs and unfolding (`cbn [fst snd]`, the same delta the loose
   `fst`/`snd` case below needs, folded into `unfold` here since the
   pattern is a literal pair immediately after `intros`).

   `t_pair_eqb_case` mirrors `t_seq_eqb_case`'s unconditional two-way split
   (no "try lia" shortcut: whether two pairs agree is no more lia-decidable
   than whether two seqs do): `Sumbool.sumbool_of_bool` turns the boolean
   into a `{= true} + {= false}` disjunction, then `first` tries each of
   the two component-equality lemmas this file actually generates
   (`Z.eqb_eq`, `Bool.eqb_true_iff`) in every position, since the tactic
   has no direct way to look up which "_spec" lemma matches an arbitrary
   `eqA` term short of trying the ones in use; `replace ... in *` then
   rewrites every occurrence, the file's own convention throughout. Joins
   t_inv1's match immediately after `t_seq_eqb`'s own two entries, goal and
   hypothesis position.

   LOOSE `fst`/`snd` (2026-09-10): unlike `t_upd`/`t_seq_eqb`/etc, which
   stay opaque behind a dedicated case-split tactic of their own, `fst` and
   `snd` are Coq's OWN library functions applied directly to a pair TERM
   (`px()`'s rendering: `(a, b)` for a `pair` node, a bare var/`ite` term
   otherwise) wherever the lowering builds a pair value, e.g.
   `divmod_pair`'s `Definition divmod_pair_t x y := (t_div x y, t_mod x
   y)`, or a loop return whose suffix rebuilds one from two locals
   (`min_max`'s `(lo, hi)`, itself reached only after `cbn beta iota`
   reduces the loop's own destructure). `fst`/`snd` are defined by pattern
   match, so `fst (a, b)` needs `fst` ITSELF unfolded before the literal
   pair's own iota step can fire (confirmed standalone: `cbn beta iota`
   alone leaves `fst (a, b)` untouched, `cbn [fst snd]` reduces it to `a`),
   the same non-negotiable delta step `t_div`/`t_mod`'s own case-split
   tactics give those two names.

   MEASURED 2026-09-10: the first attempt put this delta step INSIDE
   `t_inv1` itself, as two more `context [...]` match arms (mirroring
   every other structural-reduction arm here). min_max then read REFUSED
   (real TIMEOUT past the 180 s wall clock; a direct `coqc` run measured
   over 200 s and still not done) where divmod_pair (no loop, no
   quantifier) read COUNTS in seconds: `t_inv1` sits inside `t_base`,
   which `t_go`'s depth-6 `multimatch` search calls at EVERY branch it
   explores, so two more arms tried (and, worse, re-scanned on every
   `repeat` iteration) at every node of an already large forall/exists-
   heavy search compounds, where it costs nothing on a small goal like
   divmod_pair's. The fix is NOT to fold `fst`/`snd` into the hot per-call
   tactic at all: `gen_plain`/`gen_loop`/`_value_cert` each emit ONE
   explicit `cbn [fst snd].` line, exactly where a literal pair first
   becomes visible in THEIR OWN proof script (right after `unfold
   {name}_t.`, or after the loop's own `cbn beta iota.`, or after a
   certificate's `rewrite t_out.`), conditioned on `_has_pair(task)` so a
   task with no pair anywhere emits byte-identical proof text to before
   pairs existed. One reduction, done once, before `t_dis`'s search even
   starts, rather than a pattern tried (and failing to match, or matching
   nothing new) at every one of its many nodes. Re-measured after the
   fix: min_max reads COUNTS well inside budget (see this file's own
   dated measurement note near `lower_v1`). *)
Definition t_pair_eqb {A B : Type} (eqA : A -> A -> bool) (eqB : B -> B -> bool)
  (p q : A * B) : bool :=
  andb (eqA (fst p) (fst q)) (eqB (snd p) (snd q)).

Lemma t_pair_eqb_spec :
  forall (A B : Type) (eqA : A -> A -> bool) (eqB : B -> B -> bool),
  (forall a a' : A, eqA a a' = true <-> a = a') ->
  (forall b b' : B, eqB b b' = true <-> b = b') ->
  forall p q : A * B,
  t_pair_eqb eqA eqB p q = true <-> p = q.
Proof.
  intros A B eqA eqB HA HB [a b] [a' b'].
  unfold t_pair_eqb; cbn [fst snd].
  rewrite Bool.andb_true_iff, HA, HB.
  split.
  - intros [-> ->]; reflexivity.
  - intros H; inversion H; subst; split; reflexivity.
Qed.

Ltac t_pair_eqb_case eqA eqB p q :=
  let E := fresh "Ep" in
  destruct (Sumbool.sumbool_of_bool (t_pair_eqb eqA eqB p q)) as [E|E];
  [ let F := fresh "Fp" in
    first
    [ pose proof (proj1 (t_pair_eqb_spec _ _ eqA eqB Z.eqb_eq Z.eqb_eq p q) E) as F
    | pose proof (proj1 (t_pair_eqb_spec _ _ eqA eqB Z.eqb_eq Bool.eqb_true_iff p q) E) as F
    | pose proof (proj1 (t_pair_eqb_spec _ _ eqA eqB Bool.eqb_true_iff Z.eqb_eq p q) E) as F
    | pose proof (proj1 (t_pair_eqb_spec _ _ eqA eqB Bool.eqb_true_iff Bool.eqb_true_iff p q) E) as F
    ];
    replace (t_pair_eqb eqA eqB p q) with true in * by (symmetry; exact E)
  | let F := fresh "Fp" in
    assert (F : p <> q)
      by (intros Hc;
          first
          [ apply (proj2 (t_pair_eqb_spec _ _ eqA eqB Z.eqb_eq Z.eqb_eq p q)) in Hc
          | apply (proj2 (t_pair_eqb_spec _ _ eqA eqB Z.eqb_eq Bool.eqb_true_iff p q)) in Hc
          | apply (proj2 (t_pair_eqb_spec _ _ eqA eqB Bool.eqb_true_iff Z.eqb_eq p q)) in Hc
          | apply (proj2 (t_pair_eqb_spec _ _ eqA eqB Bool.eqb_true_iff Bool.eqb_true_iff p q)) in Hc
          ];
          congruence);
    replace (t_pair_eqb eqA eqB p q) with false in * by (symmetry; exact E)
  ]; t_bred_all.

(* t_nupd (2026-09-10): SPEC.md "Nested sequences (v1)" makes seq<seq> a
   parameter, return or local type -- a finite sequence of ROWS, each row
   an ordinary seq value. The OUTER value keeps the SAME function+length
   pair every seq already has (MEASURED against a `list (list Z)`
   alternative on swap_rows, this date; see `Ctx.nested_fn`'s own dated
   note, below, for the comparison and why this route won): a function
   from an index to a ROW, where a row is encoded as a Coq PAIR of that
   row's own (function, length) -- `Z -> ((Z -> Z) * Z)` -- so `at` on the
   outer level reads a literal pair back out through `fst`/`snd`, exactly
   the shape PAIRS (v1) already built a reduction step for.

   `t_nupd` is `t_upd` at that one codomain, monomorphic: never a generic
   `{A : Type}` `t_upd`, which would rewrite EVERY existing seq task's
   PRELUDE text (the opposite of every PRELUDE growth so far in this
   file, each a pure insertion). `t_nupd_case` copies `t_upd_case`'s own
   three-branch shape verbatim at the new codomain (Ltac's `replace`/
   `unfold` steps never inspected the codomain type, so the copy is
   mechanical); it joins `t_inv1`'s match exactly where `t_upd_case` does,
   goal and hypothesis position, so a NESTED `t_nupd` (a future task
   updating two rows) reduces one layer per case split the same way a
   nested `t_upd` already does.

   A read that hits `t_nupd`'s "in range" branch substitutes the literal
   row PAIR `(rf, rl)` for the whole application; `seq_fn`'s own new "at"
   case (Ctx, below) wraps that application in `fst (...)`/`snd (...)` to
   pull out the row's function/length, so the result right after
   `t_nupd_case` fires is `fst (rf, rl)` / `snd (rf, rl)`, a literal pair
   under a projection -- PAIRS (v1)'s own "LOOSE fst/snd" gap, not a new
   one. Rather than a second `cbn [fst snd]` gate, `_has_nested(task)` (a
   pure TYPE walk: SPEC.md adds no new Expr form here, so there is no
   inline-literal case `_expr_has_pair` had to catch for pairs) joins
   `_has_pair` at the SAME three `pair_line` gates (`gen_plain`,
   `gen_loop`, `_value_cert`), since both features need the identical
   line and PAIRS (v1)'s own cost finding already proved folding it into
   `t_inv1` itself is the wrong place to put it.

   `t_nfill`/`t_napp`/`t_nslice` and a nested LITERAL are a NAMED REFUSAL
   (`Ctx.nested_fn`, below): neither committed task needs a nested
   `fill`, `+`, `slice`, or `[[..], ..]` literal, and three more opaque
   Definitions at a codomain nothing exercises would be unmeasured
   surface, not growth. *)
Definition t_nupd (f : Z -> ((Z -> Z) * Z)) (i : Z) (v : (Z -> Z) * Z)
  : Z -> ((Z -> Z) * Z) :=
  fun k => if k =? i then v else f k.

Ltac t_nupd_case f i v k :=
  first
  [ replace (t_nupd f i v k) with v in * by (replace k with i by lia;
      unfold t_nupd; rewrite Z.eqb_refl; reflexivity);
    cbn [fst snd] in *
  | replace (t_nupd f i v k) with (f k) in * by (unfold t_nupd;
      destruct (Z.eqb_spec k i); [lia|reflexivity])
  | let E := fresh "Eb" in
    assert (E : k = i \/ k <> i) by lia; destruct E as [E|E];
    [ replace (t_nupd f i v k) with v in * by (subst; unfold t_nupd;
        rewrite Z.eqb_refl; reflexivity);
      cbn [fst snd] in *
    | replace (t_nupd f i v k) with (f k) in * by (unfold t_nupd;
        destruct (Z.eqb_spec k i); [congruence|reflexivity]) ]
  ].

(* t_napp / t_nslice / t_nseq_eqb (2026-09-10, the v1nested RESIDUAL):
   the three named refusals `Ctx.nested_fn`'s own dated note above lists
   as unexercised (`fill`, `+`, `slice`) turn out NOT all unexercised --
   the fuzz family built to grade this construct DOES use `+`
   (`concat_nested`) and `slice` (`slice_rows`) at the outer level, and
   also compares two WHOLE nested seqs with `==` in COMPUTATIONAL
   position (`eq_nested`, the gap the note near `t_seq_eqb`'s own
   "Neither committed task's ensures..." paragraph named but left
   unbuilt). `fill` alone stays unexercised (no task in the family builds
   an outer `fill`) and stays a named abstain, `t_nfill` never written.

   `t_napp`/`t_nslice` are `t_app`/`t_slice` at the row-pair codomain,
   monomorphic exactly as `t_nupd` is at `t_upd`'s: the Ltac steps never
   inspect the codomain, so `t_napp_case`/`t_nslice_get` are `t_app_case`/
   `t_slice_get` copied verbatim at the new type. Neither one's own
   case-split arm produces a bare literal pair the way `t_nupd_case`'s
   "in range" branch does (`t_napp_case`'s two branches are `f k`/
   `g (k - n)`, still-symbolic applications, not a `(rf, rl)` literal;
   `t_nslice_get` is a bare reindex, same shape), so neither needs its
   own `cbn [fst snd]` delta step: they slot into `t_inv1`'s match as a
   plain case-split arm, the same tier `t_app_case`/`t_slice_get`
   already sit in, keeping delta steps entirely OUT of `t_inv1`'s hot
   match (the outer LITERAL still gets its fix from `t_nupd_case`'s own
   existing `cbn [fst snd] in *`, since a literal is a `t_nupd` chain).

   `t_nseq_eqb` is `t_seq_eqb`'s own outer analogue: the SAME bounded
   Fixpoint over `Z.to_nat n`, but its "leaf" comparison at each outer
   index is no longer `Z.eqb` -- it is the row's own LENGTH (`Z.eqb`)
   ANDed with the row's own ELEMENTS, decided by `t_seq_eqb` itself (a
   row IS an ordinary seq value), reusing the existing Fixpoint rather
   than writing a second recursion. `t_nseq_eqb_spec` states the read-
   back fact ALREADY PROJECTED (`snd (f k) = snd (g k) /\ (forall j, ...
   fst (f k) j = fst (g k) j)`), never the raw pair `f k = g k` --
   `_nested_witness_pieces`'s own dated finding, applied here before any
   proof was measured wrong, rather than after: a raw-pair fact would
   need a further `cbn [fst snd]` step no single placement gets right
   either before or after `t_dis`'s own rewrite (that finding's own
   reasoning, unchanged). `t_nseq_eqb_case` mirrors `t_seq_eqb_case`'s
   unconditional two-way split (no "try by lia" shortcut: whether two
   nested seqs agree is no more lia-decidable than whether two flat seqs
   do) and joins `t_inv1`'s match immediately after `t_seq_eqb_case`'s
   own two entries, goal and hypothesis position, ending in `t_bred_all`
   like every other boolean case-split tactic here -- one new match arm,
   not a delta step, so `t_inv1`'s own per-branch cost is unchanged for
   every task that never builds a nested `==`. *)
Definition t_napp (f g : Z -> ((Z -> Z) * Z)) (n : Z)
  : Z -> ((Z -> Z) * Z) :=
  fun k => if k <? n then f k else g (k - n).

Definition t_nslice (f : Z -> ((Z -> Z) * Z)) (a : Z)
  : Z -> ((Z -> Z) * Z) :=
  fun k => f (a + k).

Lemma t_nslice_get : forall (f : Z -> ((Z -> Z) * Z)) (a k : Z),
  t_nslice f a k = f (a + k).
Proof. reflexivity. Qed.

Ltac t_napp_case f g n k :=
  first
  [ replace (t_napp f g n k) with (f k) in * by (unfold t_napp;
      replace (k <? n) with true by (symmetry; apply Z.ltb_lt; lia);
      reflexivity)
  | replace (t_napp f g n k) with (g (k - n)) in * by (unfold t_napp;
      replace (k <? n) with false by (symmetry; apply Z.ltb_ge; lia);
      reflexivity)
  | let E := fresh "Eb" in
    assert (E : k < n \/ n <= k) by lia; destruct E as [E|E];
    [ replace (t_napp f g n k) with (f k) in * by (unfold t_napp;
        replace (k <? n) with true by (symmetry; apply Z.ltb_lt; exact E);
        reflexivity)
    | replace (t_napp f g n k) with (g (k - n)) in * by (unfold t_napp;
        replace (k <? n) with false by (symmetry; apply Z.ltb_ge; exact E);
        reflexivity) ]
  ].

Fixpoint t_nseq_eqb_nat (m : nat) (f g : Z -> ((Z -> Z) * Z)) : bool :=
  match m with
  | O => true
  | S m' =>
      let k := Z.of_nat m' in
      andb (andb (Z.eqb (snd (f k)) (snd (g k)))
                 (t_seq_eqb (snd (f k)) (fst (f k)) (fst (g k))))
           (t_nseq_eqb_nat m' f g)
  end.

Definition t_nseq_eqb (n : Z) (f g : Z -> ((Z -> Z) * Z)) : bool :=
  t_nseq_eqb_nat (Z.to_nat n) f g.

Lemma t_nseq_eqb_nat_spec : forall (m : nat) (f g : Z -> ((Z -> Z) * Z)),
  t_nseq_eqb_nat m f g = true <->
  (forall k : Z, 0 <= k < Z.of_nat m ->
     snd (f k) = snd (g k) /\
     (forall j : Z, 0 <= j < snd (f k) -> fst (f k) j = fst (g k) j)).
Proof.
  induction m as [| m' IH]; intros f g; cbn [t_nseq_eqb_nat].
  - split; [ intros _ k Hk; exfalso; lia | intros _; reflexivity ].
  - rewrite Bool.andb_true_iff, Bool.andb_true_iff, Z.eqb_eq.
    split.
    + intros [[Hlen Hrow] Hrec] k Hk.
      destruct (Z.eq_dec k (Z.of_nat m')) as [->|Hne].
      * split.
        -- exact Hlen.
        -- apply (proj1 (t_seq_eqb_spec _ _ _)). exact Hrow.
      * apply (proj1 (IH f g) Hrec). lia.
    + intros H. split.
      * split.
        -- destruct (H (Z.of_nat m') ltac:(lia)) as [Hlen _]. exact Hlen.
        -- apply (proj2 (t_seq_eqb_spec (snd (f (Z.of_nat m')))
                     (fst (f (Z.of_nat m'))) (fst (g (Z.of_nat m'))))).
           destruct (H (Z.of_nat m') ltac:(lia)) as [_ Hrow]. exact Hrow.
      * apply (proj2 (IH f g)). intros k Hk. apply H. lia.
Qed.

Lemma t_nseq_eqb_spec : forall (n : Z) (f g : Z -> ((Z -> Z) * Z)),
  t_nseq_eqb n f g = true <-> (forall k : Z, 0 <= k < n ->
     snd (f k) = snd (g k) /\
     (forall j : Z, 0 <= j < snd (f k) -> fst (f k) j = fst (g k) j)).
Proof.
  intros n f g. unfold t_nseq_eqb. rewrite t_nseq_eqb_nat_spec.
  destruct (Z.le_gt_cases 0 n) as [Hn | Hn].
  - replace (Z.of_nat (Z.to_nat n)) with n by lia. reflexivity.
  - assert (Hz : Z.to_nat n = 0%nat).
    { destruct n as [| p | p].
      - exfalso; lia.
      - exfalso; lia.
      - reflexivity. }
    rewrite Hz. split; intros _ k Hk; exfalso; lia.
Qed.

Ltac t_nseq_eqb_case n f g :=
  let E := fresh "Es" in
  destruct (Sumbool.sumbool_of_bool (t_nseq_eqb n f g)) as [E|E];
  [ let F := fresh "Ef" in
    pose proof (proj1 (t_nseq_eqb_spec n f g) E) as F;
    replace (t_nseq_eqb n f g) with true in * by (symmetry; exact E)
  | let F := fresh "Ef" in
    assert (F : ~ (forall k : Z, 0 <= k < n ->
                     snd (f k) = snd (g k) /\
                     (forall j : Z, 0 <= j < snd (f k) ->
                        fst (f k) j = fst (g k) j)))
      by (intros Hc; apply (proj2 (t_nseq_eqb_spec n f g)) in Hc;
          congruence);
    replace (t_nseq_eqb n f g) with false in * by (symmetry; exact E)
  ]; t_bred_all.

"""
# The string library (v1) bridge Definitions/Lemmas: seq_to_list through
# endswith_list, byte-identical to the old PRELUDE's own slice.
_STRLIB_DEFS = r"""(* ============================================================
   THE STRING LIBRARY (v1), 2026-09-11.  SPEC.md "The string library
   (v1)": seventeen members over the code-point seq (and seq<seq> for
   split/join), Python's semantics exactly (interp.py's _str_* family is
   the reference this was checked against member by member).

   ENCODING. The function+length model (MODEL, above) has no induction
   principle worth the name: `s : Z -> Z` is opaque, so no Coq recursion
   can walk it structurally. Every member here is instead proved over an
   honest Coq `list Z` (a row of a nested seq: `list (list Z)`), reached
   by a BRIDGE pair: `t_list f len` (`seq_to_list`, fuel = `Z.to_nat len`,
   collecting `f 0, f 1, ..., f (len-1)` via `++` so a `len+1` step is a
   `++ [f len]` snoc BY CONSTRUCTION, `t_list_snoc`) turns a seq into a
   list; `t_of_list l` (`fun k => nth (Z.to_nat k) l 0`) turns a list back
   into a seq function. `t_nlist`/`t_of_nested` are the same pair one
   level up, `Z -> ((Z -> Z) * Z)` for a nested seq (the same codomain
   "Nested sequences (v1)" already gave `rty`). Four round-trip lemmas
   make the bridge honest rather than assumed: `t_of_list_get` (read a
   built seq back at a point in range), `t_list_of_list`/`t_nlist_of_nested`
   (list -> seq -> list is the identity), `t_list_ext`/`t_list_slice0`
   (a seq congruent on `[0, len)` builds the same list; a `slice(s, 0, n)`
   builds the SAME list `s` itself does, the fact word_count's own proof
   turns out to need and nothing deeper about `split` at all). Every
   member is then an ordinary Coq function of `list Z`/`list (list Z)`,
   called by wrapping its seq-valued arguments in `t_list`/`t_nlist` and
   its result back out through `t_of_list`/`t_of_nested` (`seq_fn`'s and
   `nested_fn`'s new `join`/`split`/`strip`/... cases, below in this
   file's Python).

   MEMBERS. `split(s)` (whitespace runs, `split_ws_list`/`split_ws_acc`,
   an explicit accumulator so the recursion matches interp.py's own
   left-to-right `out,cur` loop one line at a time) and `split(s, c)`
   (`split_sep_list`, a plain structural recursion, PROVED against
   `join`: `split_join_law`, `join_list (split_sep_list s c) [c] = s`
   for every `s`,`c`, by induction on `s` -- this is split_join's own
   ensures, verbatim). `join(rows, sep)` (`join_list`). `tostr(n)`
   (`t_tostr`/`digits_of_nat`, fuel-bounded decimal digits, sign at 45).
   `count(s, t)` (`t_count_list`/`count_go`, fuel = `S (length s)`,
   non-overlapping left to right exactly as `_str_count`; PROVED equal,
   for a ONE-CODE-POINT pattern only, to a plain structural counter
   `count_occ1` (`t_count_list_singleton`), because that is the shape
   count_vowels' own five `count(_, [v])` calls need and a general
   non-overlapping-match snoc lemma is a materially bigger proof this
   wave does not attempt -- named open, below). `find(s, t)` shares
   `count`'s `is_prefix`/fuel shape (`t_find_list`), unproved beyond its
   own definition (no committed task's ensures reaches it). `strip`/
   `lstrip`/`rstrip` (`strip_list`/`lstrip_list`/`rstrip_list`, the
   latter `rev`-then-`lstrip`-then-`rev`, SPEC.md's own two-sided
   definition literally). `replace(s, t, u)` (`t_replace_list`, the
   empty-pattern case (`replace_empty`, "insert u before every code
   point and at the end") kept syntactically separate from the fuel/
   `is_prefix` non-empty case (`replace_go`), the same split
   `_str_replace` itself makes). `lower`/`upper` (`lower_list`/
   `upper_list`, `map` over the ASCII case maps `lower_c`/`upper_c`).
   `isdigit`/`isalpha`/`isupper`/`islower` (`isdigit_list`/.../
   `islower_list`, the empty-string and mixed-case rules SPEC.md states).
   `startswith`/`endswith` (`startswith_list`/`endswith_list`, `is_prefix`
   reused, `endswith` via `skipn` to the tail of matching length).

   LEMMAS FOR THE THREE TASKS. `word_count`: `t_list_slice0` alone (its
   `t2 := s[0..len(s)]` builds the identical list `s` itself would, so
   `len(t2.split()) = len(s.split())` is congruence, not a fact about
   `split`). `split_join`: `t_list_singleton` (the literal `seq([c])`'s
   own list is `[c]`), `t_nlist_of_nested` (the round trip `split`'s own
   nested-seq wrapping and `join`'s own unwrapping cancel), and
   `split_join_law` itself; the second ensures's extensional seq equality
   (`EQUALITY`, `prop()`) then needs only `t_list_length`/`Z2Nat.id` for
   the length conjunct and `t_of_list_get` for the pointwise one, both
   already generic. `count_vowels`: `t_count_slice_step` (built from
   `t_list_snoc` + `t_count_list_singleton` + `count_occ1_snoc`), one
   fact -- "growing the slice by one either does or doesn't add one to a
   single code point's count" -- reused five times, once per vowel, by
   the SAME t_inv1 arm below.

   WHAT STAYS OPEN, BY NAME: `count`/`find`/`replace` on a
   MULTI-code-point pattern have no proved property here (the fuel/
   `is_prefix` machinery is written to interp.py's own semantics and
   MEASURED by the family below, but no lemma relates it to anything
   else); `tostr` has no lemma at all (no committed task's ensures
   reaches it); `strip`/`lower`/`upper`/`isX`/`startswith`/`endswith`
   likewise carry their definitions only. None of these is a
   `NotImplementedError` abstain -- every member above IS the function
   SPEC.md states, called from `seq_fn`/`nested_fn`/`zx`/`bx`/`prop`
   exactly where its arity puts it -- the open items are proof debt on
   arbitrary fuzzed programs, not missing semantics; MEASURED, below,
   is what that debt costs on the three committed tasks and the
   `v1strlib` family.

   MEASURED (2026-09-11, `t/lower_rocq.py test1.py word_count split_join
   count_vowels`, and `fuzz_lower.py --only rocq`, the full `v1strlib`
   family at `--n 400 --seed 1 --flake 3 --jobs 8`, 17 tasks -- the
   pre-supplied name list this wave's own instructions carried did not
   reproduce under this worktree's `build_corpus(400, 1)`, a family
   ordering/count difference from whatever run produced it; the 17 names
   `build_corpus` actually draws at that seed were used instead, same
   n/seed/flake/jobs):

   - word_count: COUNTS (real VERIFIED, off-by-one twin REFUTED).
   - count_vowels: COUNTS (real VERIFIED, invariant-drop twin REFUTED) --
     needed one addition beyond the members themselves: `gen_loop`'s
     per-invariant definedness context was sequential-prefix-only (each
     invariant's own `at`/`slice`/`div`/`mod` obligation saw only EARLIER
     invariants), which every task built before this wave never exposed,
     since their own `at`/`slice` always sat under a `forall` whose OWN
     binder supplied its range (`row_max_len`/`seq_max`/etc.); count_vowels'
     invariant is a bare (non-quantified) equation whose `slice(s, 0, i)`
     needs sibling invariants (`0 <= i`, `i <= len(s)`) regardless of list
     order. Widened to ALL sibling invariants, gated behind `_has_strlib`
     (new) so a task that uses no string-library member takes the
     ORIGINAL code path, unchanged.
   - split_join: REFUSED, real VERIFIED, wrong-var twin unproved -- a
     PRE-EXISTING, general gap this wave did not close: `_value_cert`
     abstains on a seq return outright (its own comment: "no committed
     task needs it yet"), so a loop-free task with a seq return and a
     VALUE-kind twin witness has no certificate route and falls back to
     the full symbolic proof of the (false) twin ensures, which correctly
     fails to prove rather than fails to REFUTE -- unrelated to any of
     the 17 members (it would hit ANY future seq-returning committed task
     with this witness shape), named here rather than patched under this
     wave's own time budget.
   - v1strlib family (17 fuzzed tasks, arbitrary member combinations):
     ZERO lowering crashes (`ty`/`seq_fn`/`nested_fn`/`zx`/`bx`/`prop`
     dispatch on all seventeen ops without exception on every task the
     family drew) and ZERO disagreements/vs-truth mismatches. 4 of 17
     real lowerings VERIFIED (fz_v1strlib_004/007/070/190); of those, 2
     had their twin REFUTED (004, 190) and 2 (007, 070) had an
     unproved twin (the same seq-return-value-witness gap named above).
     The other 13 real lowerings read UNPROVED: the lemmas landed here
     are the three committed tasks' own needs (the split/join round trip,
     the count-of-a-growing-slice step, the slice-congruence fact), not
     a general algebra for every member combination a fuzzed program can
     build; a MULTI-code-point `count`/`find`/`replace`, an arbitrary
     `strip`/`lower`/`upper`/`isX` composed with another member, or a
     `split`/`join` law with anything but a literal one-code-point
     separator has no lemma here to discharge it, so `t_dis`'s search
     exhausts and the file reads unproved rather than fakes a Qed --
     named, not silent, the same "abstain honestly" rule as an outright
     refusal.
   - Matrix regression (relower every non-string task in `t/tasks/*.json`
     against `git show HEAD:t/lower_rocq.py`, diff): all 23 non-string
     tasks' generated Coq is BYTE-IDENTICAL from their first `Definition`/
     `Lemma ..._def_1`/`Fixpoint` onward; the only difference anywhere is
     the shared PRELUDE's own growth (this date's insertion, zero
     deletions), the same "PRELUDE DELTA, task text otherwise byte-
     identical" shape every prior wave's own dated note already
     established. Since the generated Coq is unchanged, so is every cell
     `t/AGREEMENT.md` already commits for those 23 tasks. *)


(* ============ bridge: seq (fn,len) <-> list Z ============ *)
Fixpoint seq_to_list (f : Z -> Z) (fuel : nat) : list Z :=
  match fuel with
  | O => []
  | S n => seq_to_list f n ++ [f (Z.of_nat n)]
  end.

Lemma length_seq_to_list : forall f fuel, length (seq_to_list f fuel) = fuel.
Proof.
  induction fuel as [|n IH]; simpl.
  - reflexivity.
  - rewrite length_app, IH. simpl. lia.
Qed.

Lemma seq_to_list_ext : forall fuel f g,
  (forall k, (0 <= k < Z.of_nat fuel)%Z -> f k = g k) ->
  seq_to_list f fuel = seq_to_list g fuel.
Proof.
  induction fuel as [|n IH]; intros f g H.
  - reflexivity.
  - simpl. rewrite (IH f g); [ rewrite (H (Z.of_nat n)) by lia; reflexivity | ].
    intros k Hk. apply H. lia.
Qed.

Lemma nth_seq_to_list : forall fuel f k,
  (0 <= k < Z.of_nat fuel)%Z -> nth (Z.to_nat k) (seq_to_list f fuel) 0 = f k.
Proof.
  induction fuel as [|n IH]; intros f k Hk.
  - lia.
  - simpl. destruct (Z.eq_dec k (Z.of_nat n)) as [E|NE].
    + subst k. rewrite Nat2Z.id.
      rewrite app_nth2 by (rewrite length_seq_to_list; lia).
      rewrite length_seq_to_list. replace (n - n)%nat with O by lia. reflexivity.
    + assert (Hk' : (0 <= k < Z.of_nat n)%Z) by lia.
      rewrite app_nth1.
      * apply IH. exact Hk'.
      * rewrite length_seq_to_list.
        assert (Z.to_nat k < n)%nat.
        { assert (k < Z.of_nat n)%Z by lia.
          assert (Z.to_nat k < Z.to_nat (Z.of_nat n))%nat by lia.
          rewrite Nat2Z.id in H0. lia. }
        lia.
Qed.

Definition t_list (f : Z -> Z) (len : Z) : list Z := seq_to_list f (Z.to_nat len).
Definition t_of_list (l : list Z) : Z -> Z := fun k => nth (Z.to_nat k) l 0.

Lemma t_list_length : forall f len, length (t_list f len) = Z.to_nat len.
Proof. intros. unfold t_list. apply length_seq_to_list. Qed.

(* ROADMAP 13.4, 2026-09-12 ("rocq: the prelude by feature, then its string
   facts"): the bridge's own zero-length case, `t_list f 0 = []` -- fuel
   `Z.to_nat 0` reduces to `O` by CONSTRUCTION (`Z.to_nat`'s own definition
   on a nonnegative literal), so `seq_to_list f O` is the Fixpoint's base
   case, `reflexivity` alone. Needed by `t_count_list_empty`/
   `t_find_list_empty` below wherever SPEC.md's own `count(s,[])`/
   `find(s,[])` identity is rendered over the GENERIC `t_list fn_t 0`
   bridge term the empty-seq literal argument produces, not a bare `[]`. *)
Lemma t_list_zero : forall f, t_list f 0 = [].
Proof. intros f. reflexivity. Qed.

Lemma t_list_ext : forall f g len,
  (forall k, 0 <= k < len -> f k = g k) -> t_list f len = t_list g len.
Proof.
  intros f g len H. unfold t_list. apply seq_to_list_ext.
  intros k Hk. apply H. lia.
Qed.

Lemma t_of_list_get : forall f n k, 0 <= k < n -> t_of_list (t_list f n) k = f k.
Proof.
  intros f n k Hk. unfold t_of_list, t_list.
  apply nth_seq_to_list.
  rewrite Z2Nat.id by lia. lia.
Qed.

Lemma t_list_of_list : forall (l : list Z), t_list (t_of_list l) (Z.of_nat (length l)) = l.
Proof.
  intros l. unfold t_list, t_of_list. rewrite Nat2Z.id.
  induction l as [|x l' IH] using rev_ind.
  - reflexivity.
  - rewrite length_app. simpl length.
    replace (length l' + 1)%nat with (S (length l')) by lia.
    simpl seq_to_list.
    f_equal.
    + transitivity (seq_to_list (fun k => nth (Z.to_nat k) l' 0) (length l')).
      * apply seq_to_list_ext. intros k Hk. apply app_nth1. lia.
      * exact IH.
    + f_equal. rewrite Nat2Z.id.
      rewrite app_nth2 by lia.
      replace (length l' - length l')%nat with O by lia.
      reflexivity.
Qed.

Lemma t_list_slice0 : forall f n, t_list (t_slice f 0) n = t_list f n.
Proof.
  intros f n. apply t_list_ext. intros k Hk.
  rewrite t_slice_get. reflexivity.
Qed.

Lemma t_list_snoc : forall f len, 0 <= len -> t_list f (len + 1) = t_list f len ++ [f len].
Proof.
  intros f len Hlen. unfold t_list.
  replace (Z.to_nat (len + 1)) with (S (Z.to_nat len)) by lia.
  simpl. rewrite Z2Nat.id by lia. reflexivity.
Qed.

(* t_upd/t_fill already defined above in the shared PRELUDE (t_upd/t_fill,
   SPEC.md "Sequences as values (v1)"); reused here unchanged. *)
Lemma t_list_singleton : forall c, t_list (t_upd (t_fill 0) 0 c) 1 = [c].
Proof.
  intro c. unfold t_list, t_upd, t_fill. simpl. reflexivity.
Qed.

(* ROADMAP 13.4, 2026-09-11: fz_p_str_tab's own literal, a length-3 seq
   reified to its 3 concrete elements -- the same one-length-special-case
   shape as t_list_singleton just above (length 1), generic in f so a
   different length-3 literal pays the same lemma. *)
Lemma t_list_lit3 : forall f, t_list f 3 = [f 0; f 1; f 2].
Proof. intros f. unfold t_list. simpl. reflexivity. Qed.

(* ============ nested: seq<seq> (fn: Z -> ((Z->Z)*Z), len) <-> list (list Z) ============ *)
Fixpoint nested_to_list (f : Z -> ((Z -> Z) * Z)) (fuel : nat) : list (list Z) :=
  match fuel with
  | O => []
  | S n => nested_to_list f n ++ [t_list (fst (f (Z.of_nat n))) (snd (f (Z.of_nat n)))]
  end.
Definition t_nlist (f : Z -> ((Z -> Z) * Z)) (len : Z) : list (list Z) :=
  nested_to_list f (Z.to_nat len).
Definition t_of_nested (rows : list (list Z)) : Z -> ((Z -> Z) * Z) :=
  fun k => let row := nth (Z.to_nat k) rows [] in (t_of_list row, Z.of_nat (length row)).

Lemma length_nested_to_list : forall f fuel, length (nested_to_list f fuel) = fuel.
Proof.
  induction fuel as [|n IH]; simpl; [reflexivity|].
  rewrite length_app, IH. simpl. lia.
Qed.

Lemma nth_nested_to_list : forall fuel f k,
  (0 <= k < Z.of_nat fuel)%Z ->
  nth (Z.to_nat k) (nested_to_list f fuel) [] =
    t_list (fst (f k)) (snd (f k)).
Proof.
  induction fuel as [|n IH]; intros f k Hk.
  - lia.
  - simpl. destruct (Z.eq_dec k (Z.of_nat n)) as [E|NE].
    + subst k. rewrite Nat2Z.id.
      rewrite app_nth2 by (rewrite length_nested_to_list; lia).
      rewrite length_nested_to_list. replace (n - n)%nat with O by lia. reflexivity.
    + assert (Hk' : (0 <= k < Z.of_nat n)%Z) by lia.
      rewrite app_nth1.
      * apply IH. exact Hk'.
      * rewrite length_nested_to_list.
        assert (Z.to_nat k < n)%nat.
        { assert (k < Z.of_nat n)%Z by lia.
          assert (Z.to_nat k < Z.to_nat (Z.of_nat n))%nat by lia.
          rewrite Nat2Z.id in H0. lia. }
        lia.
Qed.

Lemma t_nlist_of_nested : forall (X : list (list Z)),
  t_nlist (t_of_nested X) (Z.of_nat (length X)) = X.
Proof.
  intros X. unfold t_nlist, t_of_nested. rewrite Nat2Z.id.
  induction X as [|row X' IH] using rev_ind.
  - reflexivity.
  - rewrite length_app. simpl length.
    replace (length X' + 1)%nat with (S (length X')) by lia.
    simpl nested_to_list.
    f_equal.
    + rewrite <- IH at 2.
      assert (Hgen : forall (fuel:nat), (fuel <= length X')%nat ->
        nested_to_list (fun k => (t_of_list (nth (Z.to_nat k) (X' ++ [row]) []),
                                   Z.of_nat (length (nth (Z.to_nat k) (X' ++ [row]) []))))
                        fuel
        = nested_to_list (fun k => (t_of_list (nth (Z.to_nat k) X' []),
                                     Z.of_nat (length (nth (Z.to_nat k) X' []))))
                          fuel).
      { induction fuel as [|m IHm]; intros Hle; simpl; [reflexivity|].
        f_equal.
        - apply IHm. lia.
        - assert (Hm : (m < length X')%nat) by lia.
          rewrite Nat2Z.id.
          rewrite app_nth1 by exact Hm.
          reflexivity. }
      apply Hgen. lia.
    + rewrite Nat2Z.id.
      rewrite app_nth2 by lia.
      replace (length X' - length X')%nat with O by lia.
      simpl. rewrite t_list_of_list. reflexivity.
Qed.
Fixpoint split_sep_list (s : list Z) (c : Z) : list (list Z) :=
  match s with
  | [] => [[]]
  | x :: rest =>
    if x =? c then [] :: split_sep_list rest c
    else match split_sep_list rest c with
         | [] => [[x]]
         | row :: more => (x :: row) :: more
         end
  end.

Lemma split_sep_nonempty : forall s c, split_sep_list s c <> [].
Proof.
  induction s as [|x rest IH]; intro c; simpl.
  - discriminate.
  - destruct (x =? c).
    + discriminate.
    + destruct (split_sep_list rest c) as [|row more] eqn:E; discriminate.
Qed.

Lemma split_sep_eq_step : forall x rest c,
  x = c -> split_sep_list (x :: rest) c = [] :: split_sep_list rest c.
Proof. intros x rest c E. simpl. rewrite E, Z.eqb_refl. reflexivity. Qed.

Lemma split_sep_neq_step : forall x rest c row more,
  x <> c -> split_sep_list rest c = row :: more ->
  split_sep_list (x :: rest) c = (x :: row) :: more.
Proof.
  intros x rest c row more NE E. simpl.
  rewrite (proj2 (Z.eqb_neq x c) NE). rewrite E. reflexivity.
Qed.

Fixpoint join_list (rows : list (list Z)) (sep : list Z) : list Z :=
  match rows with
  | [] => []
  | row :: rest =>
    match rest with
    | [] => row
    | _ :: _ => row ++ sep ++ join_list rest sep
    end
  end.

Lemma join_one_step : forall row sep, join_list [row] sep = row.
Proof. reflexivity. Qed.

Lemma join_cons_step : forall row row2 more sep,
  join_list (row :: row2 :: more) sep = row ++ sep ++ join_list (row2 :: more) sep.
Proof. reflexivity. Qed.

Lemma split_join_law : forall s c, join_list (split_sep_list s c) [c] = s.
Proof.
  induction s as [|x rest IH]; intro c.
  - reflexivity.
  - specialize (IH c).
    destruct (Z.eq_dec x c) as [E|NE].
    + rewrite (split_sep_eq_step x rest c E).
      pose proof (split_sep_nonempty rest c) as Hne.
      destruct (split_sep_list rest c) as [|row more] eqn:Etl.
      * congruence.
      * rewrite (join_cons_step [] row more [c]).
        rewrite IH. subst c. reflexivity.
    + pose proof (split_sep_nonempty rest c) as Hne.
      destruct (split_sep_list rest c) as [|row more] eqn:Etl.
      * congruence.
      * rewrite (split_sep_neq_step x rest c row more NE Etl).
        destruct more as [|row2 more2].
        -- rewrite (join_one_step row [c]) in IH.
           rewrite (join_one_step (x :: row) [c]).
           rewrite IH. reflexivity.
        -- rewrite (join_cons_step row row2 more2 [c]) in IH.
           rewrite (join_cons_step (x :: row) row2 more2 [c]).
           rewrite <- app_comm_cons.
           rewrite IH. reflexivity.
Qed.
Fixpoint count_occ1 (s : list Z) (c : Z) : Z :=
  match s with
  | [] => 0
  | x :: rest => (if x =? c then 1 else 0) + count_occ1 rest c
  end.

Lemma count_occ1_snoc : forall l x c,
  count_occ1 (l ++ [x]) c = count_occ1 l c + (if x =? c then 1 else 0).
Proof.
  induction l as [|y l' IH]; intros x c; simpl.
  - lia.
  - rewrite IH. lia.
Qed.

(* general count, matching interp.py's _str_count: non-overlapping,
   left to right; count(s, []) = len(s) + 1 *)
Fixpoint is_prefix (p l : list Z) : bool :=
  match p with
  | [] => true
  | x :: prest =>
    match l with
    | [] => false
    | y :: lrest => (x =? y) && is_prefix prest lrest
    end
  end.

Fixpoint count_go (fuel : nat) (s t : list Z) : Z :=
  match fuel with
  | O => 0
  | S f =>
    match t with
    | [] => Z.of_nat (length s) + 1
    | _ :: _ =>
      if is_prefix t s then 1 + count_go f (skipn (length t) s) t
      else match s with
           | [] => 0
           | _ :: srest => count_go f srest t
           end
    end
  end.

Definition t_count_list (s t : list Z) : Z := count_go (S (length s)) s t.

(* find(s, t): the least index t occurs at, -1 when none, find(s,[])=0
   (SPEC.md), reusing count_go's own fuel/is_prefix shape but returning
   an index instead of a running total. *)
Fixpoint find_go (fuel : nat) (s t : list Z) (i : Z) : Z :=
  match fuel with
  | O => -1
  | S f =>
    match t with
    | [] => 0
    | _ :: _ =>
      if is_prefix t s then i
      else match s with
           | [] => -1
           | _ :: srest => find_go f srest t (i + 1)
           end
    end
  end.
Definition t_find_list (s t : list Z) : Z := find_go (S (length s)) s t 0.

(* ROADMAP 13.4, 2026-09-12: SPEC.md's own two closed-form identities for
   an EMPTY pattern, both already a base case of the Fixpoint that defines
   them (`count_go`'s `t = []` arm returns `Z.of_nat (length s) + 1`
   directly; `find_go`'s does `i`, called at `i = 0` by `t_find_list`), so
   fixing `t = []` reduces the whole call by ONE unfold -- `reflexivity`,
   no induction on `s` needed (this is exactly why `count`/`find`'s
   fz_p_str_countempty/fz_p_str_findempty probes read UNPROVED before this
   date: `t_dis`'s search had no rule reaching for either fact, not that
   either needed a hard proof once reached). *)
Lemma t_count_list_empty : forall s, t_count_list s [] = Z.of_nat (length s) + 1.
Proof. intros s. reflexivity. Qed.

Lemma t_find_list_empty : forall s, t_find_list s [] = 0.
Proof. intros s. reflexivity. Qed.

Lemma is_prefix_singleton : forall c s,
  is_prefix [c] s = match s with [] => false | y :: _ => c =? y end.
Proof.
  intros c [|y s']; simpl; [reflexivity | apply andb_true_r].
Qed.

Lemma count_go_singleton : forall fuel s c,
  (length s < fuel)%nat -> count_go fuel s [c] = count_occ1 s c.
Proof.
  induction fuel as [|f IH]; intros s c Hfuel.
  - simpl in Hfuel. lia.
  - destruct s as [|x rest].
    + reflexivity.
    + simpl. rewrite andb_true_r.
      destruct (Z.eqb_spec c x) as [E|NE].
      * subst. rewrite Z.eqb_refl. simpl.
        rewrite IH by (simpl in Hfuel; lia). lia.
      * simpl. rewrite (proj2 (Z.eqb_neq x c) (not_eq_sym NE)).
        rewrite IH by (simpl in Hfuel; lia). lia.
Qed.

Lemma t_count_list_singleton : forall s c, t_count_list s [c] = count_occ1 s c.
Proof. intros s c. unfold t_count_list. apply count_go_singleton. lia. Qed.

Lemma t_count_slice_step : forall g i c, 0 <= i ->
  t_count_list (t_list (t_slice g 0) (i + 1)) [c] =
  t_count_list (t_list (t_slice g 0) i) [c] + (if g i =? c then 1 else 0).
Proof.
  intros g i c Hi.
  rewrite (t_list_snoc (t_slice g 0) i Hi).
  rewrite t_count_list_singleton.
  rewrite count_occ1_snoc.
  rewrite <- t_count_list_singleton.
  rewrite t_slice_get.
  replace (0+i) with i by lia.
  reflexivity.
Qed.

(* count_vowels' own generated shape (2026-09-11, MEASURED): a loop
   invariant over `slice(s, 0, i)` always renders the length as `i - 0`
   (`seq_fn`'s "slice" case, `hi - lo`, never arithmetically simplified),
   so the induction step's substituted next-state invariant is literally
   `i + 1 - 0`, not `i + 1` -- t_count_slice_step's own pattern needs a
   `- 0`-aware twin rather than a smarter t_inv1 match, since rewriting
   `t_list (t_slice _ 0) _` unconditionally (t_list_slice0's own arm,
   below) would otherwise consume the very structure this one needs
   first. A SECOND race the same way: the pattern's own second argument
   (the one-code-point literal `seq([c])`) reaches this goal as the RAW
   `t_list (t_upd (t_fill 0) 0 c) 1` build, not yet the `[c]` list this
   lemma's own proof works over (`t_list_singleton` turns one into the
   other) -- stating the LHS/RHS in that raw form directly, rather than
   depending on `t_list_singleton` having already fired on this one
   occurrence, is what keeps this arm's own match from losing that race
   too (MEASURED: the `[c]`-typed version above left the raw form
   standing whenever `t_list_slice0`'s own arm reached the `t_slice`
   wrapper on ONE side first, on the very same iteration `t_list_singleton`
   would have fired the other). *)
Lemma t_count_slice_step0 : forall g i c, 0 <= i ->
  t_count_list (t_list (t_slice g 0) (i + 1 - 0)) (t_list (t_upd (t_fill 0) 0 c) 1) =
  t_count_list (t_list (t_slice g 0) (i - 0)) (t_list (t_upd (t_fill 0) 0 c) 1)
  + (if g i =? c then 1 else 0).
Proof.
  intros g i c Hi.
  rewrite (t_list_singleton c).
  replace (i + 1 - 0) with (i + 1) by lia.
  replace (i - 0) with i by lia.
  apply t_count_slice_step. exact Hi.
Qed.

(* count_vowels' loop-ENTRY obligation (2026-09-11, MEASURED): the very
   first invariant check, `slice(s, 0, 0)`, renders as `0 - 0` (the same
   un-simplified `hi - lo` `seq_fn`'s "slice" case always emits); an
   empty slice's count against any one code point is 0, a fact `t_slice`/
   `t_list`/`count_go` are never unfolded far enough by this file's own
   delta-avoiding convention to reach on their own. *)
Lemma t_count_slice_zero : forall g c,
  t_count_list (t_list (t_slice g 0) (0 - 0)) (t_list (t_upd (t_fill 0) 0 c) 1) = 0.
Proof.
  intros g c.
  rewrite (t_list_singleton c).
  rewrite t_count_list_singleton.
  replace (0 - 0) with 0 by lia.
  reflexivity.
Qed.

(* ============ split(s) on whitespace runs ============ *)
Definition is_ws (c : Z) : bool :=
  (c =? 9) || (c =? 10) || (c =? 11) || (c =? 12) || (c =? 13)
  || (c =? 28) || (c =? 29) || (c =? 30) || (c =? 31) || (c =? 32).

Fixpoint split_ws_acc (s cur : list Z) : list (list Z) :=
  match s with
  | [] => match cur with [] => [] | _ => [cur] end
  | x :: rest =>
    if is_ws x then
      (match cur with [] => split_ws_acc rest [] | _ => cur :: split_ws_acc rest [] end)
    else split_ws_acc rest (cur ++ [x])
  end.
Definition split_ws_list (s : list Z) : list (list Z) := split_ws_acc s [].

(* ROADMAP 13.4, 2026-09-12: split("") == [] (SPEC.md), the accumulator's
   own base case (`cur = []` at `s = []`) -- reflexivity, one unfold,
   same shape as `t_count_list_empty`/`t_find_list_empty` above. *)
Lemma split_ws_list_empty : split_ws_list [] = [].
Proof. reflexivity. Qed.

(* ============ tostr(n) ============ *)
Fixpoint digits_of_nat (fuel : nat) (n : nat) : list Z :=
  match fuel with
  | O => []
  | S f => if Nat.eqb n 0 then [] else digits_of_nat f (n / 10) ++ [Z.of_nat (n mod 10) + 48]
  end.

Definition t_tostr (n : Z) : list Z :=
  if n =? 0 then [48]
  else if n <? 0 then 45 :: digits_of_nat (S (Z.to_nat (Z.abs n))) (Z.to_nat (Z.abs n))
  else digits_of_nat (S (Z.to_nat n)) (Z.to_nat n).

(* ============ strip / lstrip / rstrip ============ *)
Fixpoint lstrip_list (s : list Z) : list Z :=
  match s with
  | [] => []
  | x :: rest => if is_ws x then lstrip_list rest else s
  end.

Definition rstrip_list (s : list Z) : list Z := rev (lstrip_list (rev s)).
Definition strip_list (s : list Z) : list Z := rstrip_list (lstrip_list s).

(* ============ replace(s, t, u) ============ *)
Fixpoint replace_empty (s u : list Z) : list Z :=
  match s with
  | [] => u
  | x :: rest => u ++ x :: replace_empty rest u
  end.

Fixpoint replace_go (fuel : nat) (s t u : list Z) : list Z :=
  match fuel with
  | O => []
  | S f =>
    match s with
    | [] => []
    | x :: srest =>
      if is_prefix t s then u ++ replace_go f (skipn (length t) s) t u
      else x :: replace_go f srest t u
    end
  end.

Definition t_replace_list (s t u : list Z) : list Z :=
  match t with
  | [] => replace_empty s u
  | _ => replace_go (S (length s)) s t u
  end.

(* ============ lower / upper / isdigit / isalpha / isupper / islower ============ *)
Definition is_upper_letter (c : Z) : bool := (65 <=? c) && (c <=? 90).
Definition is_lower_letter (c : Z) : bool := (97 <=? c) && (c <=? 122).

Definition lower_c (c : Z) : Z := if is_upper_letter c then c + 32 else c.
Definition upper_c (c : Z) : Z := if is_lower_letter c then c - 32 else c.

Definition lower_list (s : list Z) : list Z := map lower_c s.
Definition upper_list (s : list Z) : list Z := map upper_c s.

(* ROADMAP 13.4, 2026-09-11: fz_p_str_lowernonletter's own gap -- a
   pointwise (map_nth-shaped) bridge relating `nth k (lower_list l)` to
   `lower_c (nth k l)`, closing the complication `map_nth` itself carries
   (its default-value side condition) by observing `lower_c 0 = 0`, so the
   same `0` default on both sides of the bridge lets `map_nth` apply
   directly. `t_of_list_lower_get` is `t_of_list_get` (PRELUDE_CORE_1,
   above the string block) with one `lower_list` layer read through, same
   proof shape (`nth_seq_to_list` under `Z2Nat.id`). *)
Lemma lower_c_zero : lower_c 0 = 0.
Proof. reflexivity. Qed.

Lemma t_of_list_lower_get : forall f n k, 0 <= k < n ->
  t_of_list (lower_list (t_list f n)) k = lower_c (f k).
Proof.
  intros f n k Hk.
  unfold t_of_list, lower_list, t_list.
  replace 0 with (lower_c 0) by (symmetry; apply lower_c_zero).
  rewrite (map_nth lower_c (seq_to_list f (Z.to_nat n)) 0 (Z.to_nat k)).
  f_equal.
  apply nth_seq_to_list.
  rewrite Z2Nat.id by lia. lia.
Qed.

Lemma length_lower_list_t : forall f n, length (lower_list (t_list f n)) = Z.to_nat n.
Proof. intros f n. unfold lower_list. rewrite length_map. apply t_list_length. Qed.

Fixpoint isdigit_go (s : list Z) : bool :=
  match s with
  | [] => true
  | x :: rest => (48 <=? x) && (x <=? 57) && isdigit_go rest
  end.
Definition isdigit_list (s : list Z) : bool :=
  match s with [] => false | _ => isdigit_go s end.

Fixpoint isalpha_go (s : list Z) : bool :=
  match s with
  | [] => true
  | x :: rest => (is_upper_letter x || is_lower_letter x) && isalpha_go rest
  end.
Definition isalpha_list (s : list Z) : bool :=
  match s with [] => false | _ => isalpha_go s end.

Fixpoint has_letter (s : list Z) : bool :=
  match s with
  | [] => false
  | x :: rest => is_upper_letter x || is_lower_letter x || has_letter rest
  end.
Fixpoint has_lower (s : list Z) : bool :=
  match s with
  | [] => false
  | x :: rest => is_lower_letter x || has_lower rest
  end.
Fixpoint has_upper (s : list Z) : bool :=
  match s with
  | [] => false
  | x :: rest => is_upper_letter x || has_upper rest
  end.
Definition isupper_list (s : list Z) : bool := has_letter s && negb (has_lower s).
Definition islower_list (s : list Z) : bool := has_letter s && negb (has_upper s).

(* ============ startswith / endswith ============ *)
Definition startswith_list (s t : list Z) : bool := is_prefix t s.
Definition endswith_list (s t : list Z) : bool :=
  (length t <=? length s)%nat &&
  is_prefix t (skipn (length s - length t) s).
"""
PRELUDE_CORE_2 = r"""(* invertible structural steps *)
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
  | |- context [t_app ?f ?g ?n ?k] => t_app_case f g n k
  | |- context [t_slice ?f ?a ?k] => rewrite (t_slice_get f a k)
  | |- context [t_seq_eqb ?n ?f ?g] => t_seq_eqb_case n f g
  | |- context [t_pair_eqb ?eqA ?eqB ?p ?q] => t_pair_eqb_case eqA eqB p q
  | |- context [t_nupd ?f ?i ?v ?k] => t_nupd_case f i v k
  | |- context [t_napp ?f ?g ?n ?k] => t_napp_case f g n k
  | |- context [t_nslice ?f ?a ?k] => rewrite (t_nslice_get f a k)
  | |- context [t_nseq_eqb ?n ?f ?g] => t_nseq_eqb_case n f g
  | |- context [orb _ _] => progress t_bred
  | |- context [andb _ _] => progress t_bred
  | |- context [negb _] => progress t_bred
  | |- context [if true then _ else _] => progress t_bred
  | |- context [if false then _ else _] => progress t_bred
"""
# t_inv1's string-specific goal-side match arms, spliced in right before
# the `| _ => progress subst` catch-all (PRELUDE_CORE_3, below).
_STRLIB_GOAL_ARMS = r"""  (* THE STRING LIBRARY (v1), 2026-09-11 (STRLIB's own dated note,
     above): the bridge/round-trip rewrites the three committed tasks'
     proofs need, each fired wherever its LHS pattern matches, the same
     "opaque function, read back by a dedicated rewrite" shape t_upd/
     t_app/t_slice already have above. `t_list_slice0` is word_count's
     entire proof (a congruence, nothing about `split` itself);
     `t_count_slice_step` is count_vowels' loop-preservation step, fired
     once per vowel by the SAME arm; the next four chain split_join's
     `join(split(s,c),[c]) == s` down to `t_list s s_len = t_list s
     s_len` (round trip the nested wrap/unwrap, turn the literal `[c]`
     seq into a list literal, apply the join-of-split law, then the
     length/pointwise halves of `==`'s own extensional reading). *)
  | |- context [t_count_list (t_list (t_slice ?g 0) (0 - 0)) (t_list (t_upd (t_fill 0) 0 ?c) 1)] =>
      rewrite (t_count_slice_zero g c)
  | |- context [t_count_list (t_list (t_slice ?g 0) (?i + 1 - 0)) (t_list (t_upd (t_fill 0) 0 ?c) 1)] =>
      rewrite (t_count_slice_step0 g i c) by lia
  | |- context [t_count_list (t_list (t_slice ?g 0) (?i + 1)) [?c]] =>
      rewrite (t_count_slice_step g i c) by lia
  | |- context [t_list (t_slice ?f 0) ?n] => rewrite (t_list_slice0 f n)
  | |- context [t_nlist (t_of_nested ?X) (Z.of_nat (length ?X))] =>
      rewrite (t_nlist_of_nested X)
  | |- context [t_list (t_upd (t_fill 0) 0 ?c) 1] =>
      rewrite (t_list_singleton c)
  | |- context [join_list (split_sep_list ?l ?c) [?c]] =>
      rewrite (split_join_law l c)
  | |- context [length (t_list ?f ?n)] => rewrite (t_list_length f n)
  | |- context [t_of_list (t_list ?f ?n) ?k] =>
      rewrite (t_of_list_get f n k) by lia
  (* ROADMAP 13.4, 2026-09-12: count(s,[])/find(s,[]) -- the empty-pattern
     argument is rendered as the generic bridge `t_list ?g 0`, not a bare
     `[]` literal, so the zero-length collapse fires FIRST (`t_list_zero`)
     and only then does `t_list ?s2 0` read as `[]` for
     `t_count_list_empty`/`t_find_list_empty` to match. *)
  | |- context [t_list ?g 0] => rewrite (t_list_zero g)
  | |- context [t_count_list ?s []] => rewrite (t_count_list_empty s)
  | |- context [t_find_list ?s []] => rewrite (t_find_list_empty s)
  | |- context [split_ws_list []] => rewrite split_ws_list_empty
  | |- context [length (@nil ?A)] => cbn [length]
  (* ROADMAP 13.4, 2026-09-11: fz_p_str_lowernonletter -- the pointwise
     bridge through `lower_list`, `t_of_list_lower_get`/`length_lower_list_t`
     above, mirroring `t_of_list_get`/`t_list_length` (this same file, just
     above) with one `lower_list` layer read through. *)
  | |- context [t_of_list (lower_list (t_list ?f ?n)) ?k] =>
      rewrite (t_of_list_lower_get f n k) by lia
  | |- context [length (lower_list (t_list ?f ?n))] =>
      rewrite (length_lower_list_t f n)
  (* ROADMAP 13.4, 2026-09-11: `lower_c` is opaque to `t_leaf` (lia/
     assumption/congruence/discriminate never unfold a Definition), so
     the pointwise bridge above leaves goals like `lower_c 1000000 =
     1000000` unsolved. `cbn [is_upper_letter]` alone does NOT inline
     `is_upper_letter` on this Rocq (9.2) -- the SAME measured quirk
     `split_ws_list`'s own arm above works around with `unfold`, not
     `cbn`'s name-whitelist form -- so `unfold` BOTH names here, feeding
     the exposed `<=?`/`&&`/`if` back into `t_leb_case`/`t_bred`'s own
     existing arms (just above and below, PRELUDE_CORE_2) the same way
     any other boolean guard already reduces; those decide `65 <=? c`/
     `c <=? 90` outright once `c` is a literal (`t_upd_case` has already
     read the surrounding chain back to one by the time this arm's turn
     comes), landing on `c = c`, closed by `t_base`'s own leading
     `solve [lia]` try. *)
  | |- context [lower_c ?c] => unfold lower_c, is_upper_letter
  (* ROADMAP 13.4, 2026-09-11: fz_p_str_tab -- a length-3 seq literal
     reified to its 3 concrete elements (`t_list_lit3` above). `t_list
     ?f 3` only ever arises from a LITERAL 3-element seq (`seq_fn`'s own
     "seq" case: the length term is a bare Python-emitted numeral only
     for a literal, never a parameter's `_len`), so `f` is always a
     `t_upd`-over-`t_fill` chain built from CONCRETE code points here,
     not a name to preserve opaque for `t_upd_case`'s later reuse
     elsewhere; unfolding `t_upd`/`t_fill` too lets `cbn` finish the
     whole computation in one pass (`is_ws`'s ten `Z.eqb` disjuncts
     decide outright on a literal) instead of routing three elements'
     worth of `is_ws` through the generic (and here unnecessary) case-
     split engine, measured to time out on this shared box. *)
  | |- context [split_ws_list (t_list ?f 3)] => rewrite (t_list_lit3 f)
  (* `cbn [is_ws]` alone does NOT unfold `is_ws c` on this Rocq (9.2):
     measured directly (`if is_ws 65 then _ else _` under `cbn [is_ws]`
     leaves `is_ws` standing, `unfold is_ws` inlines it in one step) --
     `unfold` first, THEN `simpl` to finish the whole computation
     (`split_ws_acc`'s recursion, `t_upd`/`t_fill`'s reads, and every
     `is_ws`/`Z.eqb` decision on now-concrete code points), same recipe
     as `t_list_singleton` above (`unfold ...; simpl; reflexivity`). *)
  | |- context [split_ws_list (?a :: ?b :: ?c :: nil)] =>
      unfold split_ws_list, split_ws_acc, is_ws, t_upd, t_fill; simpl
"""
PRELUDE_CORE_3 = r"""  | _ => progress subst
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
  | H : context [t_app ?f ?g ?n ?k] |- _ => t_app_case f g n k
  | H : context [t_slice ?f ?a ?k] |- _ => rewrite (t_slice_get f a k) in H
  | H : context [t_seq_eqb ?n ?f ?g] |- _ => t_seq_eqb_case n f g
  | H : context [t_pair_eqb ?eqA ?eqB ?p ?q] |- _ => t_pair_eqb_case eqA eqB p q
  | H : context [t_nupd ?f ?i ?v ?k] |- _ => t_nupd_case f i v k
  | H : context [t_napp ?f ?g ?n ?k] |- _ => t_napp_case f g n k
  | H : context [t_nslice ?f ?a ?k] |- _ => rewrite (t_nslice_get f a k) in H
  | H : context [t_nseq_eqb ?n ?f ?g] |- _ => t_nseq_eqb_case n f g
"""
# t_inv1's string-specific hypothesis-side match arms, spliced in right
# before t_inv1's closing `end.` (PRELUDE_CORE_4, below).
_STRLIB_HYP_ARMS = r"""  (* THE STRING LIBRARY (v1), 2026-09-11: hypothesis-position mirrors of
     the goal-side arms just above. *)
  | H : context [t_count_list (t_list (t_slice ?g 0) (0 - 0)) (t_list (t_upd (t_fill 0) 0 ?c) 1)] |- _ =>
      rewrite (t_count_slice_zero g c) in H
  | H : context [t_count_list (t_list (t_slice ?g 0) (?i + 1 - 0)) (t_list (t_upd (t_fill 0) 0 ?c) 1)] |- _ =>
      rewrite (t_count_slice_step0 g i c) in H by lia
  | H : context [t_count_list (t_list (t_slice ?g 0) (?i + 1)) [?c]] |- _ =>
      rewrite (t_count_slice_step g i c) in H by lia
  | H : context [t_list (t_slice ?f 0) ?n] |- _ => rewrite (t_list_slice0 f n) in H
  | H : context [t_nlist (t_of_nested ?X) (Z.of_nat (length ?X))] |- _ =>
      rewrite (t_nlist_of_nested X) in H
  | H : context [t_list (t_upd (t_fill 0) 0 ?c) 1] |- _ =>
      rewrite (t_list_singleton c) in H
  | H : context [join_list (split_sep_list ?l ?c) [?c]] |- _ =>
      rewrite (split_join_law l c) in H
  | H : context [length (t_list ?f ?n)] |- _ => rewrite (t_list_length f n) in H
  | H : context [t_of_list (t_list ?f ?n) ?k] |- _ =>
      rewrite (t_of_list_get f n k) in H by lia
  (* ROADMAP 13.4, 2026-09-12: hypothesis-position mirrors of the three
     goal-side arms just above. *)
  | H : context [t_list ?g 0] |- _ => rewrite (t_list_zero g) in H
  | H : context [t_count_list ?s []] |- _ => rewrite (t_count_list_empty s) in H
  | H : context [t_find_list ?s []] |- _ => rewrite (t_find_list_empty s) in H
  | H : context [split_ws_list []] |- _ => rewrite split_ws_list_empty in H
  | H : context [length (@nil ?A)] |- _ => cbn [length] in H
  (* ROADMAP 13.4, 2026-09-11: hypothesis-position mirrors of the two
     string-fact pairs just above (fz_p_str_lowernonletter/fz_p_str_tab). *)
  | H : context [t_of_list (lower_list (t_list ?f ?n)) ?k] |- _ =>
      rewrite (t_of_list_lower_get f n k) in H by lia
  | H : context [length (lower_list (t_list ?f ?n))] |- _ =>
      rewrite (length_lower_list_t f n) in H
  | H : context [lower_c ?c] |- _ => unfold lower_c, is_upper_letter in H
  | H : context [split_ws_list (t_list ?f 3)] |- _ => rewrite (t_list_lit3 f) in H
  | H : context [split_ws_list (?a :: ?b :: ?c :: nil)] |- _ =>
      unfold split_ws_list, split_ws_acc, is_ws, t_upd, t_fill in H; simpl in H
"""
PRELUDE_CORE_4 = r"""  end.

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

# PRELUDE FEATURE-GATING (2026-09-12, ROADMAP 13.4, "rocq: the prelude by
# feature, then its string facts"). Until this date `header()` emitted the
# WHOLE PRELUDE text (`t_leaf` through the div/mod section, `t_inv1`'s
# string-specific match arms included) for EVERY task regardless of
# features used -- the reason a fix for the five string probes below was
# built and MEASURED to work on 2026-09-11 (see this file's own module
# docstring, "STILL OPEN... PRELUDE feature-gating split") and then
# REVERTED: it moved 32 of 34 committed tasks' lowered bytes, divmod_pair
# (no string-lib member anywhere in it) included.
#
# `_uses_strlib` below is `lower_fstar.py`'s own `_uses_strlib` gate,
# ported verbatim (a generic dict/list walk for an `{"op": <member>, ...}`
# node whose op is in `STRLIB_OPS`, run over the task dict AND the body
# list so a member reachable through params/returns/requires/ensures/
# spec_funs/body alike is found without four separate walkers). The
# string library's own PRELUDE text sits in exactly three places, all
# discovered by textual boundary (this file's "insert only" convention
# for every prior PRELUDE growth, STRLIB's own dated note above): the
# bridge Definitions/Lemmas block (`seq_to_list` through `endswith_list`,
# `_STRLIB_DEFS`), the goal-side `t_inv1` match arms right before its
# `| _ => progress subst` catch-all (`_STRLIB_GOAL_ARMS`), and the
# hypothesis-side mirrors right before `t_inv1`'s closing `end.`
# (`_STRLIB_HYP_ARMS`). `header()` now splices these in only when
# `_uses_strlib` says the task needs them; `PRELUDE_CORE_*` are the four
# surrounding chunks, always emitted, byte-identical to their slice of
# the old monolithic `PRELUDE`. `t_inv1`'s core arms are untouched --
# dropping only the string arms for a non-string task changes nothing
# about which core arm fires first, since Ltac's `match goal` tries
# patterns top to bottom and a dropped arm's pattern (`t_list`,
# `t_count_list`, `split_sep_list`, ...) can never match a goal that
# mentions none of those names.
#
# MEASURED (relower_before_after.py, this worktree, 2026-09-12): all 34
# committed `t/tasks/*.t` relowered before and after this change; the 26
# with no string-library member anywhere lose exactly the string block
# (dated note recorded separately names the byte deltas and the eight
# that keep it). `grade.py --tasks <dir> --kernels rocq --flake 3` on
# abs/gcd/sum_upto/count_vowels/reverse/min_max/word_count/split_join/
# divmod_pair/row_max_len recorded against AGREEMENT.md's rocq column in
# the same dated note.

def _uses_strlib(obj) -> bool:
    """True iff `obj` (a task dict, a body list, or any nested JSON-like
    structure this file's AST is built from) contains an `{"op": <member>,
    ...}` node for one of the string library's members (`STRLIB_OPS`,
    below). Ported from `lower_fstar.py`'s own `_uses_strlib`: a generic
    dict/list walk, not the AST's own shape, so a member reachable through
    params/returns/requires/ensures/spec_funs/body alike is found without
    four separate walkers."""
    if isinstance(obj, dict):
        if obj.get("op") in STRLIB_OPS:
            return True
        return any(_uses_strlib(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_uses_strlib(v) for v in obj)
    return False

def header(task: dict | None = None, body: list | None = None) -> str:
    # List/ListNotations (2026-09-11, "The string library (v1)"): the
    # string members are proved over Coq's own `list Z`/`list (list Z)`
    # (STRLIB's own dated note, PRELUDE, near `seq_to_list`), the first
    # thing in this file to need the stdlib List module at all -- kept
    # unconditionally (`import` costs nothing a non-string task pays for
    # in proof search) even though the module itself is now gated.
    strlib = (task is not None and _uses_strlib(task)) or (body is not None and _uses_strlib(body))
    parts = ["From Stdlib Require Import ZArith Bool Lia List.\n"
             "Import ListNotations.\n"
             "Open Scope Z_scope.\n\n",
             PRELUDE_CORE_1]
    if strlib:
        parts.append(_STRLIB_DEFS)
    parts.append(PRELUDE_CORE_2)
    if strlib:
        parts.append(_STRLIB_GOAL_ARMS)
    parts.append(PRELUDE_CORE_3)
    if strlib:
        parts.append(_STRLIB_HYP_ARMS)
    parts.append(PRELUDE_CORE_4)
    parts.append("\n")
    return "".join(parts)

# emitted after the spec_fun section, since t_eqs/t_eqs_h name their
# equation lemmas
# THE COMBINED t_eqs;t_eqs_h ALTERNATIVE (2026-09-10, max_nit, joining the
# ground-fact substitution fix above): t_eqs and t_eqs_h were, until now,
# mutually EXCLUSIVE alternatives (a goal-side unfold OR a hypothesis-side
# unfold, never both in the same attempt, digit_sum's own note above
# explains why combining them at the SAME occurrence can grow a rewrite
# without converging). max_nit needs both at once, on DIFFERENT
# occurrences of the SAME spec_fun (`valid_base`): nitness's own equation,
# unfolded in the GOAL, exposes `sf_valid_base b` there, which the ground
# fix above substitutes to `true` from the ambient `sf_valid_base b =
# true` hypothesis (never consuming it); the remaining case split (the
# goal's `0 <=? b - 1` is not lia-decidable from `b >= 0` alone) needs the
# ARITHMETIC valid_base is opaque about (`b >= 2`), which only unfolding
# valid_base's OWN equation IN THAT HYPOTHESIS (t_eqs_h's job) exposes.
# Neither alone closes it; `t_eqs; t_eqs_h` in sequence does (MEASURED,
# `harness.run_task`, below), since each targets a disjoint occurrence
# (goal vs. hypothesis) and neither's rewrite output is the other's
# input, so there is no growing chain to fail to converge. Added as ONE
# MORE `solve [...]` alternative, tried last, so every task that already
# closes via `t_vc0`, `t_eqs;t_vc0`, or `t_eqs_h;t_vc0` alone reaches this
# new alternative never, unchanged byte for byte.
POST_SF = r"""Ltac t_dis := first [ solve [ t_vc0 ] | solve [ t_eqs; t_vc0 ]
                          | solve [ t_eqs_h; t_vc0 ]
                          | solve [ t_eqs; t_eqs_h; t_vc0 ] ]
              || fail "unsolved t verification condition".
Ltac t_side := first [ assumption | solve [ lia ]
                     | solve [ t_vc0 ] | solve [ t_eqs; t_vc0 ]
                     | solve [ t_eqs_h; t_vc0 ]
                     | solve [ t_eqs; t_eqs_h; t_vc0 ] ].
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

# ROADMAP 16.2, 2026-09-11: a SEPARATE prelude, spliced in only for a task
# `_has_nonlinear_mul` finds (below), never POST_SF itself, whose `t_dis`
# gets one more fallback: `solve [ timeout 5 nia ]`, tried LAST, after
# every `t_vc0` variant has already failed. `t_base`'s own leaf (`lia`) is
# Presburger-only, so a genuinely nonlinear goal -- centeredHexagonalNumber's
# `3 * n * (n - 1) + 1 >= 0`, a product of two VARIABLES, not a variable
# times a literal -- left `t_dis` with nothing that could ever close it;
# confirmed standalone (`nia` alone closes exactly this goal, `lia` alone
# does not) before adding it. Tried only after `t_vc0`'s own alternatives,
# so this variant's own `t_dis` costs a task whose obligations are all
# Presburger nothing beyond one failed `nia` attempt -- which is exactly
# why this is NOT spliced into every task's prelude (POST_SF, unchanged,
# is): `t_dis` is called at every def-lemma, invariant and step site in a
# file, often dozens of times, and `timeout 5` bounds a SINGLE attempt, not
# the sum of every attempt across a whole file. MEASURED WRONG twice
# before landing here: bare `nia` (no timeout) sent isPrime's own mod-
# shaped, genuinely UNPROVABLE goal into a search long enough to blow the
# file's 180s wall backstop by itself; `timeout 5 nia` added to POST_SF
# UNCONDITIONALLY still did, for isPrime and containsSequence, purely from
# the ACCUMULATED cost of many bounded-but-still-failing attempts across
# one file's many `t_dis` call sites (each paying its own 5s before
# `first` moves on) -- both real regressions this file's own history
# should not repeat. Gating on `_has_nonlinear_mul` closes the actual gap
# (centeredHexagonalNumber) while leaving every task with no genuine
# variable-times-variable term (isPrime, containsSequence, every task
# committed through 2026-09-10, and the string/pairs/nested-seq/early-exit
# waves after it) on the ORIGINAL POST_SF, byte-identical proof text --
# the same "a task that does not use it pays nothing" discipline the
# string-library block already keeps (`_has_strlib`, gen_loop's own
# `def_ctx`).
POST_SF_NIA = POST_SF.replace(
    'Ltac t_dis := first [ solve [ t_vc0 ] | solve [ t_eqs; t_vc0 ]\n'
    '                          | solve [ t_eqs_h; t_vc0 ]\n'
    '                          | solve [ t_eqs; t_eqs_h; t_vc0 ] ]\n'
    '              || fail "unsolved t verification condition".',
    'Ltac t_dis := first [ solve [ t_vc0 ] | solve [ t_eqs; t_vc0 ]\n'
    '                          | solve [ t_eqs_h; t_vc0 ]\n'
    '                          | solve [ t_eqs; t_eqs_h; t_vc0 ]\n'
    '                          | solve [ timeout 5 nia ] ]\n'
    '              || fail "unsolved t verification condition".')
assert POST_SF_NIA != POST_SF, "POST_SF_NIA gate: t_dis text not found"


def _has_nonlinear_mul(task: dict) -> bool:
    """True iff some `*` in requires/ensures/body has NEITHER side a
    literal int -- a genuine variable-times-variable product `lia` cannot
    reach, the one shape POST_SF_NIA's extra `nia` fallback exists for.
    `n * 2` or `3 * n` (a variable times a CONSTANT) is already ordinary
    Presburger arithmetic; only a case like `n * (n - 1)` (centered
    polygonal numbers' own shape) trips this."""
    def walk(e) -> bool:
        if not isinstance(e, dict):
            return False
        if e.get("op") == "*":
            args = e.get("args", [])
            if len(args) == 2 and not any(
                    isinstance(a, dict) and "int" in a for a in args):
                return True
        for v in e.values():
            if isinstance(v, dict):
                if walk(v):
                    return True
            elif isinstance(v, list):
                for item in v:
                    if walk(item):
                        return True
        return False
    return (any(walk(e) for e in task.get("requires", []))
            or any(walk(e) for e in task.get("ensures", []))
            or walk({"body": task.get("body", [])}))

RESERVED = {"at", "in", "fun", "if", "then", "else", "let", "forall", "exists",
            "match", "with", "end", "fix", "Prop", "Set", "Type", "fuel", "fu",
            "s_len", "mod", "rflag", "rf", "fst", "snd", "pair"}
# "fst"/"snd"/"pair" (SPEC.md "Pairs (v1)", 2026-09-10): not Rocq keywords,
# only ordinary library identifiers, so a t identifier of the same name
# would PARSE (as a binder shadowing the library name) rather than fail;
# reserving it turns that into an immediate, named `_ck` refusal instead of
# a confusing type error the moment generated code applies the (now
# shadowed) library `fst`/`snd` to a pair term.
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
        if op == "+":
            # SPEC.md "Sequences: literals, concatenation, slices (v1)":
            # `+` is polymorphic by operand type exactly as `==` already
            # is (two ints, two seqs); a `+` whose left operand is a seq
            # is concatenation, the same rule `bx`/`prop`'s own `==`
            # dispatch already uses. Nested sequences (v1) residual
            # (2026-09-10): a nested left operand (`concat_nested`'s own
            # `r := m + n`) is nested too, the same half-step `at` already
            # took just below, not the bare "seq" string equality check
            # this arm had before, which read a nested `+` as "int" and
            # crashed downstream.
            t0 = self.ty(e["args"][0], local)
            if isinstance(t0, dict) and "seq" in t0:
                return t0
            return "seq" if t0 == "seq" else "int"
        if op == "at":
            # SPEC.md "Nested sequences (v1)": `at` on a NESTED container
            # (`m[i]`) is a ROW, itself a seq value, not an int; `ty()` on
            # the container already returns the raw declared dict for a
            # `var` (self.tys stores the task's own JSON type), so this
            # only needs one extra check ahead of the int-returning group
            # below.
            ct = self.ty(e["args"][0], local)
            return "seq" if (isinstance(ct, dict) and "seq" in ct) else "int"
        if op in ("-", "*", "neg", "len", "div", "mod", "count", "find"):
            # THE STRING LIBRARY (v1), 2026-09-11: `count`/`find` are the
            # library's own two int-returning members (SPEC.md), joined
            # to the existing int group.
            return "int"
        if op == "split":
            # THE STRING LIBRARY (v1): `split(s)`/`split(s, c)`, two
            # arities of one op (SPEC.md), both return a LIST OF ROWS,
            # the nested-seq dict shape `ty()`'s own "seq" literal arm
            # already uses for a nested container.
            return {"seq": "seq"}
        if op in ("join", "tostr", "strip", "lstrip", "rstrip", "replace",
                  "lower", "upper"):
            # `join`/`tostr`/`strip`/`lstrip`/`rstrip`/`replace`/`lower`/
            # `upper`: every other seq-VALUED member (SPEC.md); `isdigit`/
            # `isalpha`/`isupper`/`islower`/`startswith`/`endswith` need
            # no arm here at all, since they fall through to this
            # method's own "bool" default just below, already correct.
            return "seq"
        if op == "update":
            # SPEC.md "Nested sequences (v1)": `update(m, i, r)` (row `i`
            # replaced) has the SAME type as its own first argument, seq
            # or nested seq alike; a plain seq update already returned
            # "seq" here, which IS its first argument's type, so this is
            # a generalization, not a behavior change, for every existing
            # (plain) `update` node.
            return self.ty(e["args"][0], local)
        if op == "seq":
            # Nested sequences (v1) residual (2026-09-10): a LITERAL's own
            # row arguments are themselves seq-valued when it is a nested
            # literal (`nested_lit`'s `[[..], ..]` shape); an EMPTY
            # literal (`[]`) stays ambiguous here exactly as SPEC.md says
            # ("resolved by the declared type at the assignment"), never
            # by this method: `fz_p_nest_empty`'s `r := seq()` reaches
            # `nested_fn` through `r`'s own declared type at the assign
            # site (exec_straight), not through this arm.
            args = e.get("args", [])
            if args:
                t0 = self.ty(args[0], local)
                if t0 == "seq" or (isinstance(t0, dict) and "seq" in t0):
                    return {"seq": "seq"}
            return "seq"
        if op == "slice":
            # Nested sequences (v1) residual (2026-09-10): a slice of a
            # nested container (`slice_rows`' own `r := slice(m, a, b)`)
            # is nested too, the same container-decides-the-result rule
            # `at`/`+` already have.
            ct = self.ty(e["args"][0], local)
            return ct if (isinstance(ct, dict) and "seq" in ct) else "seq"
        if op == "fill":
            # `fill`'s own element is always an int component (SPEC.md);
            # a nested fill is the named refusal `Ctx.nested_fn` still
            # raises for, unexercised by this family (below), so this
            # stays plain.
            return "seq"
        if op == "pair":
            # SPEC.md "Pairs (v1)": `{"op": "pair", "args": [a, b]}` has no
            # declared type of its own (unlike a `var`); its type is
            # exactly the pair of its two arguments' own types.
            return {"pair": [self.ty(e["args"][0], local),
                             self.ty(e["args"][1], local)]}
        if op in ("fst", "snd"):
            t = self.ty(e["args"][0], local)
            return t["pair"][0 if op == "fst" else 1]
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
        t_mod. `seq` (SPEC.md "Sequences: literals, concatenation, slices
        (v1)"), the literal, is a chain of t_upd over t_fill 0, no new
        opaque Definition; `+` on two seqs is t_app, `slice` is t_slice,
        both the SAME opaque-Definition-plus-reading-tactic shape as
        t_upd/t_fill (PRELUDE)."""
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
        if op == "at":
            # SPEC.md "Nested sequences (v1)": s[i] on a NESTED s is a
            # ROW, itself a seq value (Ctx.ty already decided this node
            # is seq-typed before seq_fn was called on it, same
            # convention as `+`'s own dispatch). The row's (fn, len) is
            # read out of the outer value's own "rows" function
            # (Ctx.nested_fn, below) at the projected pair it returns:
            # `fst`/`snd` of that application, the same delta step
            # PAIRS (v1) already built a `cbn [fst snd]` gate for
            # (`_has_nested`, joined to `_has_pair`'s own three sites).
            container, idx_e = e["args"]
            rows, _ = self.nested_fn(container, env, local)
            idx = self.zx(idx_e, env, local)
            return f"(fst ({rows} {idx}))", f"(snd ({rows} {idx}))"
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
        if op == "seq":
            # SPEC.md "Sequences: literals, concatenation, slices (v1)":
            # [e1, ..., en], every argument an int, the k-th argument is
            # the k-th element (0-indexed), n >= 0 with [] the empty seq
            # (len([]) == 0). n is always a concrete Python int here (the
            # AST literal has exactly that many arguments), so this needs
            # no new opaque Definition or reading tactic: it builds a
            # chain of t_upd over t_fill 0 (index 0 first, ..., n - 1
            # last), reusing t_upd_case/t_fill_get verbatim (PRELUDE's own
            # comment, "the LITERAL... gets no new opaque Definition").
            fn = "(t_fill 0)"
            for k, a in enumerate(e["args"]):
                val = self.zx(a, env, local)
                fn = f"(t_upd {fn} {k} {val})"
            return fn, str(len(e["args"]))
        if op == "+":
            # SPEC.md: `+` on two seqs is concatenation (Ctx.ty already
            # decided this node is seq-typed before seq_fn was called on
            # it). t_app is the PRELUDE's own opaque Definition + case-
            # split tactic (t_app_case), the same shape t_upd/t_fill/
            # t_div/t_mod already have.
            s, t = e["args"]
            fn_s, ln_s = self.seq_fn(s, env, local)
            fn_t, ln_t = self.seq_fn(t, env, local)
            return f"(t_app {fn_s} {fn_t} {ln_s})", f"({ln_s} + {ln_t})"
        if op == "slice":
            # SPEC.md: s[a..b], elements a..b-1, length b - a. t_slice is a
            # plain index shift (PRELUDE); the inner seq's own length is
            # not needed to build the slice's fn/len pair, only for its
            # definedness obligation (`defs()`, below, computes it itself).
            s, a, b = e["args"]
            fn_s, _ = self.seq_fn(s, env, local)
            av = self.zx(a, env, local)
            bv = self.zx(b, env, local)
            return f"(t_slice {fn_s} {av})", f"({bv} - {av})"
        if op in ("join", "tostr", "strip", "lstrip", "rstrip", "replace",
                  "lower", "upper"):
            # THE STRING LIBRARY (v1), 2026-09-11 (STRLIB's own dated
            # note, PRELUDE): every seq-VALUED member is built the same
            # way, list-of-Z in, list-of-Z out, `t_of_list`/`length`
            # turning the result back into this file's (fn, len) pair
            # (the SAME bridge `at` on a nested container already uses
            # via `fst`/`snd`, one level down). `join`'s first argument
            # is a nested seq (rows), read via `nested_fn`/`t_nlist`
            # rather than `seq_fn`/`t_list`; every other argument here is
            # a plain seq or (`tostr`) an int.
            if op == "join":
                rows_e, sep_e = e["args"]
                rows_fn, rows_len = self.nested_fn(rows_e, env, local)
                sep_fn, sep_len = self.seq_fn(sep_e, env, local)
                res = (f"(join_list (t_nlist {rows_fn} {rows_len}) "
                       f"(t_list {sep_fn} {sep_len}))")
            elif op == "tostr":
                n = self.zx(e["args"][0], env, local)
                res = f"(t_tostr {n})"
            elif op in ("strip", "lstrip", "rstrip", "lower", "upper"):
                fname = {"strip": "strip_list", "lstrip": "lstrip_list",
                         "rstrip": "rstrip_list", "lower": "lower_list",
                         "upper": "upper_list"}[op]
                fn_s, ln_s = self.seq_fn(e["args"][0], env, local)
                res = f"({fname} (t_list {fn_s} {ln_s}))"
            else:
                assert op == "replace"
                s, t, u = e["args"]
                fn_s, ln_s = self.seq_fn(s, env, local)
                fn_t, ln_t = self.seq_fn(t, env, local)
                fn_u, ln_u = self.seq_fn(u, env, local)
                res = (f"(t_replace_list (t_list {fn_s} {ln_s}) "
                       f"(t_list {fn_t} {ln_t}) (t_list {fn_u} {ln_u}))")
            return f"(t_of_list {res})", f"(Z.of_nat (length {res}))"
        if op in ("fst", "snd"):
            # ROADMAP 13.4, 2026-09-11 (fz_p_pair_seq): a seq PROJECTED out
            # of a pair (`pair_comp_ty`'s new "seq" case, above: the
            # component is ONE Coq value, `((Z -> Z) * Z)`, the model's
            # own (function, length) pair). `Ctx.ty` already decided this
            # node is seq-typed before `seq_fn` was called on it (the
            # SAME convention `at`'s nested-seq case and `+`/`slice`
            # already rely on); `px` renders the pair term itself (a
            # `var` for a pair PARAMETER, `fz_p_pair_seq`'s own shape),
            # `fst`/`snd` of THAT reads the projected component's own
            # (fn, len) pair value back, then this function's OWN
            # `fst`/`snd` pulls the two slots apart -- the same two-step
            # "pair term, then this codomain's own projection" shape
            # `nested_fn`'s `at` case already has for a row.
            comp = self.px(e["args"][0], env, local)
            proj = f"({op} {comp})"
            return f"(fst {proj})", f"(snd {proj})"
        raise ValueError(f"t v1 -> rocq: not a seq expression: {op!r}")

    def nested_fn(self, e: dict, env: dict, local: dict | None = None
                  ) -> tuple[str, str]:
        """(rows-function term, outer-length term) for a NESTED-seq-VALUED
        expression e (SPEC.md "Nested sequences (v1)"). The naming
        convention is `seq_fn`'s own (`v`/`v_len` env slots), unchanged;
        only the CODOMAIN differs, `Z -> ((Z -> Z) * Z)` in place of
        `Z -> Z`, so a nested `var`/`ite` case is `seq_fn`'s own case
        verbatim. `update` (SPEC.md: "row i replaced by the seq r") turns
        the row `r`'s own (fn, len) into a literal Coq PAIR via `seq_fn`
        (a row IS an ordinary seq value) and rewrites the outer function
        at that one index with `t_nupd` (PRELUDE, `t_upd`'s own shape at
        this codomain); the outer length is unchanged, `seq_fn`'s own
        `update` case's same rule. `fill`, `+`, `slice` and the nested
        LITERAL at the outer level are a NAMED REFUSAL: neither committed
        task needs an outer `fill`/`+`/`slice`/`[[..], ..]` literal (SPEC.md
        "Nested sequences (v1)" 's own dated note lists them as
        polymorphic obligations, but building three more untested opaque
        Definitions at a codomain nothing exercises is unmeasured
        surface, not growth; see this method's own module-level dated
        note, near `t_nupd`, for the fuller reasoning)."""
        local = local or {}
        if "var" in e:
            v = e["var"]
            t = local.get(v) or self.tys.get(v)
            assert isinstance(t, dict) and t.get("seq") == "seq", \
                f"{v} is not a nested seq"
            return env.get(v, v), env.get(v + "_len", f"{v}_len")
        if "ite" in e:
            c = e["ite"]
            cb = self.bx(c["cond"], env, local)
            fn_t, ln_t = self.nested_fn(c["then"], env, local)
            fn_e, ln_e = self.nested_fn(c["else"], env, local)
            return (f"(if {cb} then {fn_t} else {fn_e})",
                    f"(if {cb} then {ln_t} else {ln_e})")
        op = e.get("op")
        if op == "update":
            s, i, r = e["args"]
            fn_s, ln_s = self.nested_fn(s, env, local)
            idx = self.zx(i, env, local)
            row_fn, row_len = self.seq_fn(r, env, local)
            return f"(t_nupd {fn_s} {idx} ({row_fn}, {row_len}))", ln_s
        if op == "seq":
            # Nested sequences (v1) residual (2026-09-10): the outer
            # LITERAL, `[[..], ..]` (`nested_lit`'s own shape). Each
            # argument is itself a plain-seq row (`seq_fn`), so this is
            # `seq_fn`'s own literal-building chain one level up: a chain
            # of `t_nupd` (already PRELUDE) over a base outer function
            # that is never read at any index the chain actually assigns,
            # the SAME reasoning `seq_fn`'s own "seq" case already gives
            # for `t_fill 0` as ITS base -- no new opaque Definition
            # needed for the base either.
            fn = "(fun _ : Z => ((fun _ : Z => 0), 0))"
            for k, row_e in enumerate(e["args"]):
                row_fn, row_len = self.seq_fn(row_e, env, local)
                fn = f"(t_nupd {fn} {k} ({row_fn}, {row_len}))"
            return fn, str(len(e["args"]))
        if op == "+":
            # Nested sequences (v1) residual (2026-09-10): concatenation
            # of two nested seqs (`concat_nested`'s own `r := m + n`),
            # `t_napp`'s own outer-codomain twin of `seq_fn`'s `t_app`
            # (PRELUDE).
            s, t = e["args"]
            fn_s, ln_s = self.nested_fn(s, env, local)
            fn_t, ln_t = self.nested_fn(t, env, local)
            return f"(t_napp {fn_s} {fn_t} {ln_s})", f"({ln_s} + {ln_t})"
        if op == "slice":
            # Nested sequences (v1) residual (2026-09-10): a row-slice of
            # a nested seq (`slice_rows`' own `r := slice(m, a, b)`),
            # `t_nslice`'s own outer-codomain twin of `seq_fn`'s
            # `t_slice` (PRELUDE).
            s, a, b = e["args"]
            fn_s, _ = self.nested_fn(s, env, local)
            av = self.zx(a, env, local)
            bv = self.zx(b, env, local)
            return f"(t_nslice {fn_s} {av})", f"({bv} - {av})"
        if op == "split":
            # THE STRING LIBRARY (v1), 2026-09-11: `split(s)` (whitespace
            # runs) and `split(s, c)` (one code point, empty rows kept),
            # two arities of one op (SPEC.md), both nested-seq-VALUED;
            # `t_of_nested`/`length` turn the Coq `list (list Z)` result
            # back into this codomain's (fn, len) pair, the same bridge
            # `seq_fn`'s new string-member cases use one level down.
            args = e["args"]
            fn_s, ln_s = self.seq_fn(args[0], env, local)
            if len(args) == 1:
                res = f"(split_ws_list (t_list {fn_s} {ln_s}))"
            else:
                c = self.zx(args[1], env, local)
                res = f"(split_sep_list (t_list {fn_s} {ln_s}) {c})"
            return f"(t_of_nested {res})", f"(Z.of_nat (length {res}))"
        raise NotImplementedError(
            f"rocq lowering: nested seq op {op!r} is refused (only var/"
            f"ite/update/seq/+/slice/split are built at the outer level; "
            f"`fill` is the sole refusal left here, unexercised by this "
            f"family; see Nested sequences (v1)'s dated note near "
            f"t_nupd)")

    def outer_fn(self, e: dict, env: dict, local: dict | None = None
                 ) -> tuple[str, str]:
        """(fn, len) for an expression `e` of EITHER seq shape, dispatched
        on `Ctx.ty` (SPEC.md "Nested sequences (v1)"): `seq_fn` for a
        plain seq, `nested_fn` for a nested one. `len(e)` (zx's own "len"
        case) needs only the length half regardless of which; `defs()`'s
        `at`/`update` obligations need the same dispatch to find the
        right container's own length bound (row_max_len's `len(m[k])`
        forall and swap_rows' `update(m, i, ...)` both reach a nested
        container this way)."""
        local = local or {}
        ct = self.ty(e, local)
        if isinstance(ct, dict) and "seq" in ct:
            return self.nested_fn(e, env, local)
        return self.seq_fn(e, env, local)

    def comp_term(self, e: dict, env: dict, local: dict) -> str:
        """A pair COMPONENT's own Coq term, dispatched on `e`'s type
        (SPEC.md "Pairs (v1)": a component is "int", "bool" or "seq").
        Used only by `px`'s `pair` case, to render each of the two
        arguments to `{"op": "pair", ...}` per its OWN type.

        ROCQ-3, 2026-09-12 (splitArray, `fz_p_pair_seq` is a PARAM, never
        a `pair` literal, so this branch was never exercised until now):
        `pair_comp_ty`'s own "seq" case already gives a seq component ONE
        Coq value, `((Z -> Z) * Z)`, the model's own (function, length)
        pair; `seq_fn`'s `fst`/`snd` case (ROADMAP 13.4) already reads
        that shape back out of a pair. Building it is the same pair,
        literally: `seq_fn(e)` gives the (fn, len) Coq terms, wrapped as
        one Coq tuple `(fn, len)`, matching `pair_comp_ty("seq")`
        exactly. The stale refusal this replaces predates that seq_fn
        case and was never revisited once it landed."""
        t = self.ty(e, local)
        if isinstance(t, dict):
            return self.px(e, env, local)
        if t == "bool":
            return self.bx(e, env, local)
        if t == "seq":
            fn, ln = self.seq_fn(e, env, local)
            return f"({fn}, {ln})"
        return self.zx(e, env, local)

    def px(self, e: dict, env: dict, local: dict) -> str:
        """The Coq TERM for a pair-VALUED expression e (SPEC.md "Pairs
        (v1)"): `var` (a pair param, return or local, ALWAYS one Coq
        value here, never seq's own two-slot split), `ite` (mirrors
        zx/bx/seq_fn's own if-then-else construction), `pair` (`(a, b)`,
        each component rendered per its own type via `comp_term`), `fst`/
        `snd` of a pair-of-pairs (not in v1 per SPEC.md, "not in v1: a
        pair of pairs"; kept here only because `ty()` already computes
        the right component type generically and refusing it would need
        a special case this file's own type checker is not, so it is left
        to whatever Coq itself does with it, which is nothing: no
        committed task and no SYNTAX.md form builds one)."""
        if "var" in e:
            v = e["var"]
            return env.get(v, v)
        if "ite" in e:
            c = e["ite"]
            cb = self.bx(c["cond"], env, local)
            return (f"(if {cb} then {self.px(c['then'], env, local)} "
                    f"else {self.px(c['else'], env, local)})")
        op = e.get("op")
        if op == "pair":
            a, b = e["args"]
            return f"({self.comp_term(a, env, local)}, {self.comp_term(b, env, local)})"
        if op in ("fst", "snd"):
            inner = self.px(e["args"][0], env, local)
            return f"({op} {inner})"
        raise ValueError(f"t v1 -> rocq: not a pair expression: {op!r}")

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
            return self.outer_fn(e["args"][0], env, local)[1]
        if op == "at":
            fn, _ = self.seq_fn(e["args"][0], env, local)
            return f"({fn} {self.zx(e['args'][1], env, local)})"
        if op in ("fst", "snd"):
            # SPEC.md "Pairs (v1)": `fst`/`snd` project; this arm is
            # reached when the projection's component type is "int" (the
            # caller already knows this via `ty()`), rendered as Coq's own
            # `fst`/`snd` applied to the pair's own term (`px`).
            inner = self.px(e["args"][0], env, local)
            return f"({op} {inner})"
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
        if op in ("count", "find"):
            # THE STRING LIBRARY (v1), 2026-09-11: `s.count(t)`/`s.find(t)`
            # (SPEC.md), both int-valued, both built the same way `at`'s
            # own zx() case reads a seq's function half: `t_list` bridges
            # each argument into a Coq list, `t_count_list`/`t_find_list`
            # (PRELUDE) do the rest.
            s, t = e["args"]
            fn_s, ln_s = self.seq_fn(s, env, local)
            fn_t, ln_t = self.seq_fn(t, env, local)
            cfn = "t_count_list" if op == "count" else "t_find_list"
            return f"({cfn} (t_list {fn_s} {ln_s}) (t_list {fn_t} {ln_t}))"
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
        if op in ("fst", "snd"):
            # Same projection as zx's own arm, reached here when the
            # component type is "bool".
            inner = self.px(e["args"][0], env, local)
            return f"({op} {inner})"
        if op in ("<", "<="):
            a, b = (self.zx(x, env, local) for x in e["args"])
            return f"({a} {'<?' if op == '<' else '<=?'} {b})"
        if op in (">", ">="):
            a, b = (self.zx(x, env, local) for x in e["args"])
            return f"({b} {'<?' if op == '>' else '<=?'} {a})"
        if op in ("==", "!="):
            t = self.ty(e["args"][0], local)
            if isinstance(t, dict) and "pair" in t:
                # SPEC.md "Pairs (v1)": `==`/`!=` on two pairs is
                # componentwise, "the polymorphic == again"; in
                # COMPUTATIONAL position this needs a decidable bool,
                # PRELUDE's `t_pair_eqb` (generic over the two component
                # equality functions, `pair_comp_eq_fn` choosing Z.eqb/
                # Bool.eqb per this kernel's own refusal of a seq
                # component), the same gap `t_seq_eqb` closes for seq.
                t1, t2 = t["pair"]
                pa = self.px(e["args"][0], env, local)
                pb = self.px(e["args"][1], env, local)
                eqA, eqB = pair_comp_eq_fn(t1), pair_comp_eq_fn(t2)
                core = f"(t_pair_eqb {eqA} {eqB} {pa} {pb})"
                return core if op == "==" else f"(negb {core})"
            if isinstance(t, dict) and t.get("seq") == "seq":
                # Nested sequences (v1) residual (2026-09-10): `==`/`!=`
                # on two WHOLE nested seqs in COMPUTATIONAL position
                # (`eq_nested`'s own `r := m == n`; the crash this closes
                # was `t["pair"]`'s own KeyError on this dict, reached
                # before the `"pair" in t` guard above existed).
                # PRELUDE's `t_nseq_eqb` decides it: outer length equality
                # first, then a bounded Fixpoint comparing row lengths
                # AND each row's own elements via `t_seq_eqb` (a row IS
                # an ordinary seq value), the outer analogue of
                # `t_seq_eqb` itself.
                rows_a, ln_a = self.nested_fn(e["args"][0], env, local)
                rows_b, ln_b = self.nested_fn(e["args"][1], env, local)
                core = (f"(({ln_a} =? {ln_b}) && "
                        f"t_nseq_eqb {ln_a} {rows_a} {rows_b})")
                return core if op == "==" else f"(negb {core})"
            if t == "seq":
                # The residual (2026-09-09): seq `==`/`!=` in COMPUTATIONAL
                # position used to abstain outright (no Fixpoint walked a
                # symbolic length to compute a bool; `prop()`'s extensional
                # forall, above, only ever landed in Prop position). PRELUDE's
                # `t_seq_eqb` (a bounded Fixpoint over `Z.to_nat` of the
                # shared length, same idiom as every loop/recursion Fixpoint
                # in this file) makes it decidable: lengths first (cheap,
                # `Z.eqb`, short-circuits the general case, and is what makes
                # `t_seq_eqb`'s own length argument meaningful when the two
                # seqs are not equal length to begin with), then `t_seq_eqb`
                # over the shared length, `&&`'d together. `t_seq_eqb_spec`
                # (PRELUDE) is what lets the proof engine read this back
                # (`t_seq_eqb_case`, joined into t_inv1's match beside
                # t_upd_case/t_app_case).
                fn_a, ln_a = self.seq_fn(e["args"][0], env, local)
                fn_b, ln_b = self.seq_fn(e["args"][1], env, local)
                core = f"(({ln_a} =? {ln_b}) && t_seq_eqb {ln_a} {fn_a} {fn_b})"
                return core if op == "==" else f"(negb {core})"
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
        if op in ("isdigit", "isalpha", "isupper", "islower",
                  "startswith", "endswith"):
            # THE STRING LIBRARY (v1), 2026-09-11: the library's six
            # bool-VALUED members (SPEC.md), each a decidable Coq
            # `bool` function of the underlying list(s) already
            # (`isdigit_list`/.../`endswith_list`, PRELUDE), so no
            # `t_seq_eqb`-style extra decision procedure is needed here.
            fname = {"isdigit": "isdigit_list", "isalpha": "isalpha_list",
                     "isupper": "isupper_list", "islower": "islower_list",
                     "startswith": "startswith_list",
                     "endswith": "endswith_list"}[op]
            fn_s, ln_s = self.seq_fn(e["args"][0], env, local)
            if op in ("startswith", "endswith"):
                fn_t, ln_t = self.seq_fn(e["args"][1], env, local)
                return (f"({fname} (t_list {fn_s} {ln_s}) "
                        f"(t_list {fn_t} {ln_t}))")
            return f"({fname} (t_list {fn_s} {ln_s}))"
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
        if op in ("fst", "snd"):
            # SPEC.md "Pairs (v1)": a bare `fst`/`snd` reaches Prop position
            # only when its own component type is "bool" (gate 1: a
            # standalone Prop-position term must be boolean); zx/bx/px
            # handle the int/pair cases, which only ever appear NESTED
            # inside a comparison/`pair`, never bare here. Not exercised by
            # either committed task (both pairs are (int, int)).
            assert self.ty(e, local) == "bool"
            inner = self.px(e["args"][0], env, local)
            return f"({op} {inner} = true)"
        if op in ("==", "!="):
            t = self.ty(e["args"][0], local)
            if t == "bool":
                a, b = (self.prop(x, env, local) for x in e["args"])
                return (f"({a} <-> {b})" if op == "=="
                        else f"(~ ({a} <-> {b}))")
            if isinstance(t, dict) and "pair" in t:
                # SPEC.md "Pairs (v1)": == on two pairs is componentwise,
                # "the polymorphic == again"; a Prop admits an unbounded
                # per-component equality directly (Z `=` for an int
                # component, the same bool `<->`-of-"= true" form used
                # just above for a standalone bool, mirroring t's OWN
                # equality rules component by component), no decidable
                # bool needed here (that is bx()'s job, via t_pair_eqb).
                t1, t2 = t["pair"]
                a, b = e["args"]
                pa, pb = self.px(a, env, local), self.px(b, env, local)

                def ceq(ct: str, x: str, y: str) -> str:
                    if ct == "bool":
                        return f"(({x} = true) <-> ({y} = true))"
                    return f"({x} = {y})"

                core = (f"({ceq(t1, f'(fst {pa})', f'(fst {pb})')} /\\ "
                        f"{ceq(t2, f'(snd {pa})', f'(snd {pb})')})")
                return core if op == "==" else f"(~ {core})"
            if isinstance(t, dict) and t.get("seq") == "seq":
                # Nested sequences (v1) residual (2026-09-10): two nested
                # seqs are equal iff same outer length and every row equal
                # (`fz_p_nest_eq`'s own ensures states exactly this shape,
                # one conjunct per row rather than the raw `m == n` the
                # body computes). Same forall-of-forall as the plain-seq
                # rule just below, one level deeper: the outer forall's
                # body is the row's own length equation conjoined with an
                # inner forall over the row's own elements (a row IS an
                # ordinary seq value, `nested_fn`'s "rows" function).
                rows_a, ln_a = self.nested_fn(e["args"][0], env, local)
                rows_b, ln_b = self.nested_fn(e["args"][1], env, local)
                core = (
                    f"({ln_a} = {ln_b} /\\ "
                    f"(forall t_k : Z, 0 <= t_k < {ln_a} -> "
                    f"snd ({rows_a} t_k) = snd ({rows_b} t_k) /\\ "
                    f"(forall t_j : Z, 0 <= t_j < snd ({rows_a} t_k) -> "
                    f"fst ({rows_a} t_k) t_j = fst ({rows_b} t_k) t_j)))")
                return core if op == "==" else f"(~ {core})"
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
        if op in ("isdigit", "isalpha", "isupper", "islower",
                  "startswith", "endswith"):
            # THE STRING LIBRARY (v1), 2026-09-11: the same six bool
            # members as `bx()`'s own arm, reached here in SPEC position
            # (a `requires`/`ensures`/invariant), stated as `= true`
            # exactly the way a spec-position `call` already is just
            # above.
            return f"({self.bx(e, env, local)} = true)"
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
            _, ln = self.outer_fn(e["args"][0], env, local)
            idx = self.zx(e["args"][1], env, local)
            acc.append((list(binders), list(ctx), f"(0 <= {idx} < {ln})"))
            return
        if op == "update":
            # SPEC.md "Sequences as values (v1)": s[i := v], DEFINED IFF
            # 0 <= i < len(s), the same shape as `at`'s own obligation
            # (and, since `update` is itself a SeqExpr, its own inner `s`
            # may carry further obligations, e.g. a nested update). SPEC.md
            # "Nested sequences (v1)" extends this unchanged to a nested
            # `s`: only the LENGTH lookup needs to route through
            # `nested_fn` instead of `seq_fn` when `s` is itself nested
            # (an outer update's `i` bound is the OUTER length, same rule
            # either way).
            s, i, v = e["args"]
            self.defs(s, ctx, binders, acc, env, local)
            self.defs(i, ctx, binders, acc, env, local)
            self.defs(v, ctx, binders, acc, env, local)
            _, ln = self.outer_fn(s, env, local)
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
        if op == "slice":
            # SPEC.md "Sequences: literals, concatenation, slices (v1)":
            # s[a..b], DEFINED IFF 0 <= a <= b <= len(s), a definedness
            # obligation under the same rules as `at`'s own `(0 <= idx <
            # len)`, emitted here exactly where `at`'s is. `seq` (the
            # literal) and `+` (concatenation on two seqs) get no case of
            # their own: SPEC.md says a literal is defined iff every
            # element is and a concatenation iff both operands are,
            # nothing more, so they fall through to the generic recursion
            # below, which is exactly that.
            s, a, b = e["args"]
            self.defs(s, ctx, binders, acc, env, local)
            self.defs(a, ctx, binders, acc, env, local)
            self.defs(b, ctx, binders, acc, env, local)
            # Nested sequences (v1) residual (2026-09-10): `s`'s own
            # length lookup must route through `nested_fn` when `s` is
            # nested (`outer_fn`'s dispatch, the same fix `update`'s own
            # case above already has); the un-dispatched `seq_fn` here
            # crashed with `seq_fn`'s own "is not a seq" assert on a
            # nested `s` (MEASURED, `slice_rows`' own `r := slice(m, a,
            # b)`, `m` nested).
            _, ln = self.outer_fn(s, env, local)
            av = self.zx(a, env, local)
            bv = self.zx(b, env, local)
            acc.append((list(binders), list(ctx),
                        f"(0 <= {av} /\\ {av} <= {bv} /\\ {bv} <= {ln})"))
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
            elif isinstance(t, dict) and "seq" in t:
                # SPEC.md "Nested sequences (v1)": the SAME two-slot
                # convention as a plain seq (above), only via `nested_fn`
                # instead of `seq_fn` (the codomain differs, not the
                # bookkeeping); checked BEFORE the generic pair branch
                # below, since a nested type is a dict too.
                fn, ln = cx.nested_fn(e, env, local)
                old_fn, old_ln = env[v], env[v + "_len"]
                env[v] = fn if done == "false" else f"(if {done} then {old_fn} else {fn})"
                env[v + "_len"] = (ln if done == "false"
                                   else f"(if {done} then {old_ln} else {ln})")
            elif isinstance(t, dict):
                # SPEC.md "Pairs (v1)": a pair is ONE Coq value here (never
                # seq's two-slot split), so the freeze below is the same
                # single-slot rule int/bool already have.
                raw = cx.px(e, env, local)
                env[v] = raw if done == "false" else f"(if {done} then {env[v]} else {raw})"
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
            elif isinstance(t, dict) and "seq" in t:
                # SPEC.md "Nested sequences (v1)": same two-slot rule as
                # the assign case above, via `nested_fn`.
                fn, ln = cx.nested_fn(e, env, local)
                old_fn, old_ln = env[v], env[v + "_len"]
                env[v] = fn if done == "false" else f"(if {done} then {old_fn} else {fn})"
                env[v + "_len"] = (ln if done == "false"
                                   else f"(if {done} then {old_ln} else {ln})")
            elif isinstance(t, dict):
                raw = cx.px(e, env, local)
                env[v] = raw if done == "false" else f"(if {done} then {env[v]} else {raw})"
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
            elif isinstance(d["type"], dict) and "seq" in d["type"]:
                # SPEC.md "Nested sequences (v1)": a nested LOCAL, the
                # loop-encoding shape this construct's own dated note
                # asks for; measured only by construction (neither
                # committed task declares one), the same two-slot rule as
                # a nested param/return, via `nested_fn`.
                fn, ln = cx.nested_fn(d["init"], env, local)
                env[v] = fn
                env[v + "_len"] = ln
            elif isinstance(d["type"], dict):
                env[v] = cx.px(d["init"], env, local)
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
        t = stys[v]
        if t == "seq" or (isinstance(t, dict) and "seq" in t):
            # SPEC.md "Nested sequences (v1)": a nested loop-state var owes
            # the same second `_len` slot a plain seq's already does (the
            # loop encoding this construct's own dated note asks for;
            # measured only by construction, neither committed task
            # carries a nested loop-state var).
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
    """(binder text, arg text) with seq expanded to fn+len; a pair (SPEC.md
    "Pairs (v1)") is one binder, `pair_ty`'s product, no committed task
    uses a pair PARAM yet (both divmod_pair and min_max only return one),
    so this arm is measured only by construction."""
    bs, args = [], []
    for p in cx.task["params"]:
        v = p["name"]
        if p["type"] == "seq":
            bs.append(f"({v} : Z -> Z) ({v}_len : Z)")
            args += [v, f"{v}_len"]
        elif isinstance(p["type"], dict) and "seq" in p["type"]:
            # SPEC.md "Nested sequences (v1)": a nested param is the same
            # two-binder split a plain seq gets, only over the row-pair
            # codomain (`rty`'s own new nested branch, below).
            bs.append(f"({v} : {rty(p['type'])}) ({v}_len : Z)")
            args += [v, f"{v}_len"]
        elif p["type"] == "bool":
            bs.append(f"({v} : bool)")
            args.append(v)
        elif isinstance(p["type"], dict):
            bs.append(f"({v} : {pair_ty(p['type'])})")
            args.append(v)
        else:
            bs.append(f"({v} : Z)")
            args.append(v)
    return " ".join(bs), " ".join(args)


def len_hyps(cx: Ctx) -> list[str]:
    return [f"(0 <= {p['name']}_len)" for p in cx.task["params"]
            if p["type"] == "seq"
            or (isinstance(p["type"], dict) and "seq" in p["type"])]


def pair_comp_ty(t: str) -> str:
    """Coq type of one pair COMPONENT (SPEC.md "Pairs (v1)": T1/T2 are each
    "int", "bool" or "seq"). This kernel maps "int"/"bool" straight to
    Z/bool; a "seq" component is `((Z -> Z) * Z)`, the model's own
    function+length pair (above) wrapped as ONE Coq value instead of two
    separate binders -- unlike a top-level seq PARAM (which needs two
    slots at the Gallina binder list itself, `param_binders`' own two-
    binder split), a seq NESTED one level inside another pair needs only
    ONE slot at that outer level, since the outer pair's own single Coq
    binder already provides the wrapping value pairs need one Coq value
    for; `fst`/`snd` of the outer pair reads (fn, len) back the same way
    `Ctx.nested_fn`'s own row codomain already does for a nested SEQ
    (`Z -> ((Z -> Z) * Z)`, the ROW-level version of this exact idea:
    each row is a Coq pair of the row's own (function, length), which is
    exactly `pair_comp_ty("seq")`'s result here, one level up).

    ROADMAP 13.4, 2026-09-11 (fz_p_pair_seq): measured CONTAINED --
    `pair_ty` (this file's product-type builder, just below) already
    calls `pair_comp_ty` on each component with no other change needed,
    `param_binders` already renders ANY pair-typed param as one binder
    via `pair_ty` regardless of what is inside it, and `Ctx.ty`'s
    `fst`/`snd` case already reads a component's type generically
    (`t["pair"][0 if op == "fst" else 1]`) with no pair-of-pairs-shaped
    special case to add. The one REAL gap was `Ctx.seq_fn`, which had no
    `fst`/`snd` case at all (a seq-VALUED projection out of a pair
    reached `seq_fn`'s own final `raise ValueError`, not this refusal);
    `seq_fn`'s new case, below, closes it the same way `nested_fn`'s
    `at` case already reads a row's own (fn, len) out of a literal Coq
    pair via `fst`/`snd`. `pair_comp_eq_fn`, just below, is UNCHANGED
    (still a named refusal): SPEC.md's `==`/`!=` on two pairs needs a
    DECIDABLE bool equality per component, and a seq's own equality is
    `t_seq_eqb` (a three-argument function taking the length alongside
    both sides, not the two-argument shape `t_pair_eqb` is generic
    over) -- `fz_p_pair_seq` itself never compares two pairs, so this
    is left exactly as it was, its own separate, still-real, gap."""
    if t == "int":
        return "Z"
    if t == "bool":
        return "bool"
    if t == "seq":
        return "((Z -> Z) * Z)"
    raise NotImplementedError(
        f"rocq lowering: a pair component of type {t!r} is refused "
        f"(SPEC.md's own rocq product is Z * Z or, for a seq component, "
        f"((Z -> Z) * Z); no other component shape is built)")


def pair_comp_eq_fn(t: str) -> str:
    """The PRELUDE's `t_pair_eqb` component equality function for pair
    component type `t` ("int" -> Z.eqb, "bool" -> Bool.eqb); mirrors
    `pair_comp_ty`'s own refusal for "seq"."""
    if t == "int":
        return "Z.eqb"
    if t == "bool":
        return "Bool.eqb"
    raise NotImplementedError(
        f"rocq lowering: t_pair_eqb has no component equality for pair "
        f"component type {t!r} (a seq pair component is refused; see "
        f"pair_comp_ty)")


def pair_ty(t: dict) -> str:
    """Coq type for a pair type `{"pair": [T1, T2]}`: the product
    `(T1 * T2)%type` SPEC.md's own dated note names for this kernel,
    T1/T2 each `pair_comp_ty`'s Coq type. A pair occupies exactly ONE Coq
    slot (never seq's two), so a caller reaches this the same way it
    reaches "Z"/"bool" (param_binders/rty), never seq_slots' own
    two-binder expansion."""
    t1, t2 = t["pair"]
    return f"({pair_comp_ty(t1)} * {pair_comp_ty(t2)})"


def default_term(t) -> str:
    """A type-correct PLACEHOLDER Coq term for a not-yet-assigned return,
    the SAME role "0"/"false" already play in gen_plain/gen_loop/_plain_def/
    _rec_def/_loop_def's own env0: a pair recurses componentwise so a
    pair-typed return that is only ever assigned in a loop's SUFFIX
    (min_max: `r` never appears inside the loop body itself, only in the
    state tuple's own frame) still carries a term of the RIGHT Coq type
    through the Fixpoint before its real value lands. seq is out of scope
    here (its own two-slot convention is the caller's job, since it needs
    two env entries, not one)."""
    if isinstance(t, dict) and "seq" in t:
        # SPEC.md "Nested sequences (v1)": out of scope here too, same
        # reason a plain "seq" already is (two env slots, not one); no
        # caller reaches this branch (gen_plain/gen_loop special-case a
        # nested return's env0 themselves, mirroring their own existing
        # seq special case).
        raise NotImplementedError(
            "rocq lowering: default_term has no single-slot default for "
            "a nested seq; the caller must build its own two-slot env0")
    if isinstance(t, dict):
        t1, t2 = t["pair"]
        return f"({default_term(t1)}, {default_term(t2)})"
    return "false" if t == "bool" else "0"


def rty(t) -> str:
    """Coq type for a t type in a SINGLE-slot position (a t `seq` is never
    one Coq value here, the function+length model needs two; a caller with
    a seq in hand uses `seq_slots`/an explicit two-binder split instead of
    this, so `rty("seq")` names only the function half, "Z -> Z", the same
    half `param_binders` gives a seq param). A pair type (SPEC.md "Pairs
    (v1)", a dict `{"pair": [T1, T2]}`) IS one Coq value here, `pair_ty`'s
    product, since (unlike seq) nothing about this kernel's pair
    representation needs a second slot."""
    if isinstance(t, dict) and "seq" in t:
        # SPEC.md "Nested sequences (v1)": a nested seq is never one Coq
        # value here either (the SAME two-slot reason a plain "seq"
        # names only its function half below); this names the function
        # half's own type, `Z -> ((Z -> Z) * Z)`, an outer index to a
        # literal Coq pair of a row's own (function, length).
        return "Z -> ((Z -> Z) * Z)"
    if isinstance(t, dict):
        return pair_ty(t)
    if t == "bool":
        return "bool"
    if t == "seq":
        return "Z -> Z"
    return "Z"


STRLIB_OPS = {"split", "join", "tostr", "count", "find", "strip", "lstrip",
              "rstrip", "replace", "lower", "upper", "isdigit", "isalpha",
              "isupper", "islower", "startswith", "endswith"}


def _expr_has_strlib(e) -> bool:
    """True iff a string-library op (SPEC.md "The string library (v1)",
    2026-09-11) appears anywhere inside expression `e`. Used only to gate
    `gen_loop`'s widened per-invariant definedness context (below,
    near `inv_ctx`): a task built before this wave never trips that gate,
    so its generated proof text is untouched, byte for byte."""
    if not isinstance(e, dict):
        return False
    if e.get("op") in STRLIB_OPS:
        return True
    if any(_expr_has_strlib(a) for a in e.get("args", [])):
        return True
    if "ite" in e:
        c = e["ite"]
        return (_expr_has_strlib(c["cond"]) or _expr_has_strlib(c["then"])
                or _expr_has_strlib(c["else"]))
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        return (_expr_has_strlib(q["lo"]) or _expr_has_strlib(q["hi"])
                or _expr_has_strlib(q["body"]))
    if "call" in e:
        return any(_expr_has_strlib(a) for a in e["call"]["args"])
    return False


def _has_strlib(task: dict) -> bool:
    """True iff `task` uses a string-library member anywhere: `requires`,
    `ensures`, or the body (through `if`/`while`, a `var` init, an
    `assign`, or a `return`). SPEC.md "The string library (v1)",
    2026-09-11."""
    if any(_expr_has_strlib(e) for e in task.get("requires", [])):
        return True
    if any(_expr_has_strlib(e) for e in task.get("ensures", [])):
        return True

    def walk(stmts: list) -> bool:
        for s in stmts:
            if "var" in s and _expr_has_strlib(s["var"]["init"]):
                return True
            if "assign" in s and _expr_has_strlib(s["assign"][1]):
                return True
            if "return" in s and _expr_has_strlib(s["return"][1]):
                return True
            if "if" in s:
                c = s["if"]
                if (_expr_has_strlib(c["cond"]) or walk(c["then"])
                        or walk(c["else"])):
                    return True
            if "while" in s:
                w = s["while"]
                if (_expr_has_strlib(w["cond"])
                        or _expr_has_strlib(w["decreases"])
                        or any(_expr_has_strlib(e)
                               for e in w.get("invariants", []))
                        or walk(w["body"])):
                    return True
        return False

    return walk(task["body"])


def _expr_has_pair(e) -> bool:
    """True iff a `pair`/`fst`/`snd` node appears anywhere inside expression
    `e` (SPEC.md "Pairs (v1)"). `_has_pair`'s own TYPE walk (a dict type on
    a param/return/local) MISSED a pair built and immediately projected
    INLINE, tied to no declared pair type anywhere: `fz_p_pair_proj`
    (2026-09-10, the fuzz corpus's own projection probe), `r := fst (pair
    (a, b))` with `a`, `b`, `r` all plain ints, has no dict type on any
    param/return/local, so the old `_has_pair` read False, `gen_plain`
    emitted no `cbn [fst snd].`, and `fst (a, b)` sat stuck in front of
    `t_dis`'s search (MEASURED, standalone: `unfold ...; t_dis.` alone left
    `fst (a, b) = a` unsolved; adding `cbn [fst snd].` before `t_dis` closed
    it). This expression-level walk catches that case too, alongside every
    shape `_has_pair`'s own type walk already covers."""
    if not isinstance(e, dict):
        return False
    if e.get("op") in ("pair", "fst", "snd"):
        return True
    if any(_expr_has_pair(a) for a in e.get("args", [])):
        return True
    if "ite" in e:
        c = e["ite"]
        return (_expr_has_pair(c["cond"]) or _expr_has_pair(c["then"])
                or _expr_has_pair(c["else"]))
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        return (_expr_has_pair(q["lo"]) or _expr_has_pair(q["hi"])
                or _expr_has_pair(q["body"]))
    if "call" in e:
        return any(_expr_has_pair(a) for a in e["call"]["args"])
    return False


def _has_pair(task: dict) -> bool:
    """True iff `task` uses a pair (SPEC.md "Pairs (v1)") anywhere: a
    declared TYPE (a param, a return, or a `var` local in the body) OR an
    inline `pair`/`fst`/`snd` EXPRESSION (`_expr_has_pair`, 2026-09-10
    addition: a literal pair built and projected without ever being bound
    to a dict-typed name, missed by the type walk alone; see
    `_expr_has_pair`'s own note). `gen_plain`/`gen_loop`/`_value_cert` use
    this to decide whether their shared proof-script TEMPLATE needs one
    extra `cbn [fst snd].` line: `fst`/`snd` applied to a literal pair
    (PRELUDE's own dated note, "LOOSE fst/snd") needs that one delta step
    before `t_dis`'s search can see through it, measured cheapest as ONE
    explicit line at the point a literal pair first appears, never as a
    tactic tried on every node of the search (measured 2026-09-10: folding
    it into `t_inv1` instead made min_max time out). Conditioned so a task
    with no pair anywhere (all committed tasks before divmod_pair/min_max)
    emits BYTE-IDENTICAL proof text to before pairs existed: this walk
    returning False costs nothing downstream."""
    def has(t) -> bool:
        # SPEC.md "Nested sequences (v1)" is ALSO a dict type
        # ({"seq": "seq"}); `_has_pair` answers a pair-specific question
        # (its OWN `cbn [fst snd]` gate happens to be the same line
        # `_has_nested`, below, needs too, but the two walks stay
        # separate so each names what it actually found).
        return isinstance(t, dict) and "pair" in t

    if any(has(p["type"]) for p in task["params"]):
        return True
    if any(has(r["type"]) for r in task["returns"]):
        return True
    if any(_expr_has_pair(e) for e in task.get("requires", [])):
        return True
    if any(_expr_has_pair(e) for e in task.get("ensures", [])):
        return True

    def walk(stmts: list) -> bool:
        for s in stmts:
            if "var" in s and (has(s["var"]["type"])
                                or _expr_has_pair(s["var"]["init"])):
                return True
            if "assign" in s and _expr_has_pair(s["assign"][1]):
                return True
            if "return" in s and _expr_has_pair(s["return"][1]):
                return True
            if "if" in s:
                c = s["if"]
                if (_expr_has_pair(c["cond"]) or walk(c["then"])
                        or walk(c["else"])):
                    return True
            if "while" in s:
                w = s["while"]
                if (_expr_has_pair(w["cond"])
                        or _expr_has_pair(w["decreases"])
                        or any(_expr_has_pair(e)
                               for e in w.get("invariants", []))
                        or walk(w["body"])):
                    return True
        return False

    return walk(task["body"])


def _expr_has_nested(e) -> bool:
    """True iff an inline nested-seq LITERAL appears anywhere inside
    expression `e` (SPEC.md "Nested sequences (v1)" residual, 2026-09-10):
    a `{"op": "seq", "args": [...]}` node whose own arguments are
    THEMSELVES seq literals. `_has_nested`'s own TYPE walk (a dict type
    on a param/return/local) MISSED a nested literal built and used
    entirely inline, tied to no declared nested type anywhere:
    `fz_p_nest_lit` (the fuzz corpus's own nested-literal probe) has no
    param and a plain BOOL return, so the old `_has_nested` read False,
    `gen_plain` emitted no `cbn [fst snd].`, and the literal's own
    `t_nupd`-chain read-back (`t_nupd_case`'s "in range" branch) left a
    bare `fst`/`snd` of a literal pair stuck in front of `t_dis`'s
    search -- the exact gap `_expr_has_pair` closed for an inline pair,
    mirrored here for an inline nested literal. Syntactic, not a full
    type walk (no `local` in scope here): sufficient for every nested
    literal this family builds (each row is itself an inline `seq`
    literal), not for a literal whose rows are seq-typed VARIABLES
    instead -- that shape is still caught by `_has_nested`'s own type
    walk, since a seq/nested-typed name reaching such a literal must
    itself be declared somewhere."""
    if not isinstance(e, dict):
        return False
    if e.get("op") == "seq" and any(
            isinstance(a, dict) and a.get("op") == "seq"
            for a in e.get("args", [])):
        return True
    if any(_expr_has_nested(a) for a in e.get("args", [])):
        return True
    if "ite" in e:
        c = e["ite"]
        return (_expr_has_nested(c["cond"]) or _expr_has_nested(c["then"])
                or _expr_has_nested(c["else"]))
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        return (_expr_has_nested(q["lo"]) or _expr_has_nested(q["hi"])
                or _expr_has_nested(q["body"]))
    if "call" in e:
        return any(_expr_has_nested(a) for a in e["call"]["args"])
    return False


def _has_nested(task: dict) -> bool:
    """True iff `task` declares a NESTED seq type ({"seq": "seq"},
    SPEC.md "Nested sequences (v1)") anywhere: a param, a return, or a
    `var` local, OR builds one as an inline literal (`_expr_has_nested`,
    2026-09-10 residual addition: SPEC.md adds no new Expr FORM for
    nesting, but the existing `seq` literal form can still be used
    free-floating, tied to no declared nested type, the same gap
    `_expr_has_pair` closed for pairs; see `_expr_has_nested`'s own
    note). Joins `_has_pair` at gen_plain/gen_loop/_value_cert's shared
    `pair_line` gate (both features need the identical `cbn [fst snd]`
    line, PAIRS (v1)'s own cost finding already having proved it must
    live there and not in `t_inv1`); a task with neither construct still
    emits byte-identical proof text to before either existed."""
    def has(t) -> bool:
        return isinstance(t, dict) and "seq" in t

    if any(has(p["type"]) for p in task["params"]):
        return True
    if any(has(r["type"]) for r in task["returns"]):
        return True
    if any(_expr_has_nested(e) for e in task.get("requires", [])):
        return True
    if any(_expr_has_nested(e) for e in task.get("ensures", [])):
        return True

    def walk(stmts: list) -> bool:
        for s in stmts:
            if "var" in s and (has(s["var"]["type"])
                                or _expr_has_nested(s["var"]["init"])):
                return True
            if "assign" in s and _expr_has_nested(s["assign"][1]):
                return True
            if "return" in s and _expr_has_nested(s["return"][1]):
                return True
            if "if" in s:
                c = s["if"]
                if (_expr_has_nested(c["cond"]) or walk(c["then"])
                        or walk(c["else"])):
                    return True
            if "while" in s:
                w = s["while"]
                if (_expr_has_nested(w["cond"])
                        or _expr_has_nested(w["decreases"])
                        or any(_expr_has_nested(e)
                               for e in w.get("invariants", []))
                        or walk(w["body"])):
                    return True
        return False

    return walk(task["body"])


def _check_pair_types(task: dict) -> None:
    """Validate every pair type declared anywhere in `task` (a param, a
    return, or a `var` local, the same walk `_has_pair` makes) BEFORE any
    other lowering step runs, by calling `pair_ty` on each one (raising
    `pair_comp_ty`'s own named NotImplementedError for a seq component).

    A PARAM's own seq-component pair is already caught this way, just
    later: `param_binders` calls `pair_ty` on every param at the top of
    `lower_v1`. A RETURN's is not caught early enough: `lower_v1` only
    calls `rty(ret_t)` for the return's own binder well AFTER
    `spec_def_obls` has already walked requires/ensures, so `len`/`at`
    applied to a seq-typed projection of such a return (`fst`/`snd` of it)
    reaches `zx`'s "len"/"at" case, then `seq_fn`, which has no `fst`/`snd`
    arm and raises a bare ValueError there: a crash the harness records as
    "lower-error" rather than the named "abstain" every OTHER seq-
    component path already gets (MEASURED 2026-09-10, fz_v1pairs_064,
    return type `{"pair": ["seq", "int"]}`: ensures' own `len(fst(r))`
    crashed inside `spec_def_obls`, `ValueError: t v1 -> rocq: not a seq
    expression: 'fst'`, before `rty(ret_t)` ever ran to refuse it
    properly). Calling `pair_ty` on every pair type in the task, ONCE,
    before `lower_v1` does anything else, makes the refusal fire the same
    way no matter where the seq component sits (param, return or local) or
    which expression would otherwise reach it first."""
    def check(t) -> None:
        # SPEC.md "Nested sequences (v1)" is ALSO a dict type; `pair_ty`
        # only knows how to read a `{"pair": [...]}` shape, so this must
        # skip a nested seq type rather than crash on `t["pair"]`.
        if isinstance(t, dict) and "pair" in t:
            pair_ty(t)

    for p in task["params"]:
        check(p["type"])
    for r in task["returns"]:
        check(r["type"])

    def walk(stmts: list) -> None:
        for s in stmts:
            if "var" in s:
                check(s["var"]["type"])
            if "if" in s:
                walk(s["if"]["then"])
                walk(s["if"]["else"])
            if "while" in s:
                walk(s["while"]["body"])

    walk(task["body"])


def _bool_state_assigned(svars: list, stys: dict, body_assigned: set) -> list:
    """Loop STATE variables (SPEC.md's own `svars`: the return plus every
    prefix local) that are both bool-typed AND actually reassigned inside
    the loop body (`loop_assigned`'s own set) -- e.g. a sentinel `found`
    flag, never a frozen passthrough like `is_prime`'s own bool RETURN
    (only ever `return`-ed, never `assign`-ed inside the loop body, so
    `loop_assigned` never names it).

    THE FINDING (2026-09-10, fuzz family v1pairs, the "sentinel" shape:
    `found`/`val` locals, `r := pair(found, val)` in the suffix, ensures
    phrased as `fst(r) == exists ...`/`fst(r) -> exists ... /\\ snd(r) =
    ...`). By the time `t_dis` runs, `cbn [fst snd]` (gated on `_has_pair`)
    has ALREADY correctly reduced every `fst`/`snd` of the literal returned
    pair down to the bare `found`/`found'` local (confirmed by instrumenting
    the generated proof directly: the goal at that point is already stated
    over `found'`/`val'`, no `fst`/`snd` left anywhere) -- so this is NOT a
    pairs bug. The actual gap: `t_sweep` case-splits `<?`/`<=?`/`=?`/
    `Bool.eqb` comparisons but never a bare boolean VARIABLE gating an
    `if` (`if negb found && (s i <=? -1) then true else found`), so
    `found`'s own value stays syntactically opaque through the whole
    per-step invariant-preservation proof: `apply IH; t_side` fails on the
    new-state invariant obligations (they still mention the un-reduced
    `if`), the `inversion Heq` fallback does not apply to a recursive call
    (not a base-case constructor equation), and the induction step is left
    unsolved (MEASURED: `coqc` on the untouched lowering fails inside
    `{name}_loop_spec`'s own `Qed`, NOT the outer theorem). Destructing the
    PRE-state bool var (`destruct found.`) before `t_sweep` lets every
    nested `if` on it collapse to a literal in each of the two branches,
    where `t_sweep`'s own comparison splits then finish the job (MEASURED:
    adding exactly this one `destruct` closes `{name}_loop_spec`). The
    outer theorem needs the SAME destruct on the PRIMED (post-loop) name,
    right before its own closing `t_dis`/`t_dis_ext`, for the identical
    reason applied to the exit-time value (MEASURED: `destruct found';
    t_dis.` in place of the bare `t_dis.` closes it).

    This is a GENERIC bool-state gap, not a pairs one -- `is_prime`'s own
    bool return never trips it only because `is_prime` never REASSIGNS
    that return inside the loop body (early exit's own `return`, which
    `loop_assigned` does not count), so `bool_state_assigned` reads empty
    for it and every other pre-pairs committed task, the same zero-cost-
    when-absent shape `_has_pair` already has: a task with no bool state
    var actually assigned in its own loop body emits BYTE-IDENTICAL proof
    text to before this fix existed. Named `_bool_state_assigned`, not
    folded into `_has_pair`, because it answers a different question (a
    bool VALUE gap, not a pair one) and is gated on its own, narrower
    condition (assigned-in-body, not merely bool-typed) so it does not
    touch a frozen bool passthrough like `is_prime`'s."""
    return [v for v in svars if stys[v] == "bool" and v in body_assigned]


def _pair_param_destruct(task: dict) -> str:
    """`  destruct {p}.\\n` for every pair-typed PARAM, meant right after
    `intros.` and before `unfold`; "" for a task with no pair param (byte-
    identical to before this fix existed).

    THE FINDING (2026-09-10, fuzz family v1pairs, the `eq_params` shape:
    ensures `fst p = fst q /\\ snd p = snd q` from two pair-typed params
    `p`, `q`). `_has_pair` already gates ONE `cbn [fst snd].` line for such
    a task (it has dict-typed params), but that line is a no-op on an
    OPAQUE param: `fst`/`snd` only iota-reduce against a LITERAL pair
    constructor `(_, _)`, never a bound variable, so `fst p`/`fst q` stay
    stuck in front of `t_dis` regardless (MEASURED, standalone: `cbn [fst
    snd]. t_dis.` alone left exactly this goal unsolved). `t_pair_eqb_spec`
    only relates `t_pair_eqb ... p q = true` to WHOLE-pair equality `p =
    q`, not to the componentwise form the ensures states, so `t_dis` would
    additionally need `p = q <-> fst p = fst q /\\ snd p = snd q`, a fact no
    generic E-matching/lia search here derives from an opaque `p`.
    `destruct p.` (no `as` clause: nothing downstream refers to the fresh
    component names) turns `p` into a literal pair EVERYWHERE it occurs --
    inside the still-to-be-unfolded function body AND inside the ensures
    clause alike -- so the EXISTING `cbn [fst snd].` step (unchanged) then
    reduces every `fst p`/`snd p` to its own atomic component (MEASURED:
    adding this one `destruct` per pair param, before `unfold`, closes
    eq_params). No committed task uses a pair PARAM yet (`param_binders`'s
    own note), so this is measured only by construction against the fuzz
    corpus, not either committed pair task."""
    # SPEC.md "Nested sequences (v1)" params are ALSO dict-typed but are
    # NOT pairs: `destruct m.` on an opaque nested param (a function) is
    # meaningless (and would fail), so this filter must name pairs only.
    names = [p["name"] for p in task["params"]
             if isinstance(p["type"], dict) and "pair" in p["type"]]
    return "".join(f"  destruct {n}.\n" for n in names)


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
        # Nested sequences (v1) residual (2026-09-10): a param-less task
        # with a ground obligation (no bound `binders` either,
        # `fz_p_nest_lit`'s own `at` on a constant index) makes `allb`
        # empty; `forall {allb},` then renders as "forall ," -- a Coq
        # syntax error, MALFORMED (MEASURED). Every task with at least
        # one param or bound variable is unaffected (`allb` non-empty,
        # byte-identical to before).
        fa = f"forall {allb},\n" if allb else ""
        out.append(
            f"Lemma {name}_def_{k} : {fa}{hyp_txt}"
            f"  {concl}.\n"
            f"Proof. intros. t_dis. Qed.\n")
    return "\n".join(out)


def emit_spec_funs(cx: Ctx) -> str:
    """Fuel fixpoint + wrapper + irrelevance + equation lemma per spec_fun,
    plus t_eqs. Also collects definedness lemmas for spec_fun bodies."""
    task = cx.task
    chunks = []
    eqs = []
    # THE GROUND-FACT SUBSTITUTION GAP (2026-09-10, COVERAGE-lifted-785.md's
    # thirteenth sweep, max_nit): `nitness`'s own body, once unfolded by
    # `t_eqs`, exposes a bare `sf_valid_base b` -- the SAME argument, no
    # arithmetic offset, as the task's own `requires valid_base(b)`
    # hypothesis (`sf_valid_base b = true` after `intros`) -- yet nothing
    # substitutes it: `t_sat1`'s merge/E-matching arms all require `is_var`
    # on the applied head, and a global spec_fun Definition never is one
    # (the SAME gap fix (2)'s `ring_simplify`, above, closes for argument
    # ARITHMETIC, not for a ground VALUE). A prior attempt at a fully
    # generic rule, `H : ?X = true |- context [?X] => rewrite H`, is
    # named in this file's own note as MEASURED UNSAFE: unguarded, it can
    # fire on a state-variable equality (`r = true`) at the wrong
    # occurrence and corrupt an unrelated goal into a false residual. This
    # is the narrow version: one match arm PER bool-result spec_fun, keyed
    # on that spec_fun's own Coq constant name (`sf_{f}`, never a
    # variable), so it can only ever fire on a literal application of a
    # global spec_fun Definition this task actually declares -- never on a
    # state var, a loop-primed name, or any other head shape. `bool_sf`
    # collects (name, arity) here, arity counted in Coq ARGUMENTS (a seq
    # param is function+length, two), the same count `atxt` below builds
    # from.
    bool_sf: list[tuple[str, int]] = []
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
        if sf["result"] == "bool":
            bool_sf.append((f, len(args)))

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
        # 2026-09-10 (COVERAGE-lifted-785.md's twelfth sweep, computeSum):
        # a bare `rewrite sf_X_eq` leaves the recursive step's own
        # argument ARITHMETIC unnormalized (`sf_sum (i + 1)` rewrites to
        # `i + sf_sum (i + 1 - 1)`, not `i + sf_sum i`), syntactically
        # different from the invariant's own `sf_sum i` even though lia
        # proves the two arguments equal; `t_sat1`'s merge rule never
        # reaches it (its `is_var f` guard is for a var-headed seq
        # application, and a global spec_fun constant is never one, the
        # same gap this file's own docstring already named for computeSum
        # and is_even). `ring_simplify` on the argument closes exactly
        # this gap: Z is the only ring a spec_fun's own argument ranges
        # over, `progress` makes it a no-op (never an error) wherever the
        # argument is already ring-normal (a bare variable included), and
        # it is confined to a single-int-param spec_fun (`sf["params"]`
        # is exactly one `"int"`) so it never fires `ring_simplify` on a
        # seq's own (function, length) pair (count_matches' `s`) or picks
        # one of two int arguments arbitrarily (gcd's `gcds`) -- both stay
        # bare-rewrite-only, byte-identical to before. MEASURED: closes
        # computeSum's real side (`s = sf_sum i` invariant, argument
        # arithmetic only, no further gap); does NOT close is_even's real
        # side alone (`r = true <-> sf_even i = true`, an opaque BOOL
        # spec_fun result needs a case split no saturation step here
        # makes, a different, unresolved gap, left open by name in this
        # date's note). One `repeat match` per single-int-param spec_fun,
        # chained after the existing rewrite; goal position joins t_eqs,
        # hypothesis position (`ring_simplify ... in H`) joins t_eqs_h,
        # the same goal/hypothesis split this file already keeps
        # (digit_sum's own note, above).
        norm_names = [f"sf_{sf['name']}" for sf in task.get("spec_funs", [])
                      if len(sf["params"]) == 1
                      and sf["params"][0]["type"] == "int"]
        norm = " ".join(
            f"repeat match goal with |- context [{n} ?x] => "
            f"progress ring_simplify x end;" for n in norm_names)
        norm_h = " ".join(
            f"repeat match goal with H : context [{n} ?x] |- _ => "
            f"progress ring_simplify x in H end;" for n in norm_names)
        # THE GROUND-FACT SUBSTITUTION FIX itself (2026-09-10, above): one
        # match arm per bool-result spec_fun, keyed on its own Coq constant
        # name, propagating a literal `sf_{f} <args> = true` (or `= false`)
        # hypothesis into any occurrence of the SAME application (same
        # args, syntactically, after whatever unfolding `eq_tac`/`norm`
        # already did) anywhere it appears. `?a0 .. ?a{k-1}` binds the
        # spec_fun's own Coq-level arguments (a seq param counts as two,
        # matching `atxt`'s own count above); `rewrite H` is a plain
        # substitution, no arithmetic, so this needs no `ring_simplify`-
        # style arity/type guard the way fix (2) did -- it is safe for
        # every arity and every param type, including a seq param's
        # function/length pair, since a mismatched shape simply never
        # unifies and `repeat match ... end` with zero firings is a no-op,
        # never an error. Goal position joins t_eqs (chained after `norm`,
        # so an already-unfolded/normalized occurrence is what it meets);
        # hypothesis position (`rewrite H in H2`) joins t_eqs_h the same
        # way `ring_simplify ... in H` does above. A task with no
        # bool-result spec_fun (`bool_sf` empty) gets the empty string
        # here, byte-identical to before this fix.
        def _ap(n: int) -> str:
            return " ".join(f"?a{i}" for i in range(n))
        ground_arms, ground_arms_h = [], []
        for fname, arity in bool_sf:
            term = f"sf_{fname} {_ap(arity)}".rstrip()
            ground_arms.append(
                f"| H : {term} = true |- context [{term}] => rewrite H ")
            ground_arms.append(
                f"| H : {term} = false |- context [{term}] => rewrite H ")
            ground_arms_h.append(
                f"| H : {term} = true, H2 : context [{term}] |- _ => "
                f"rewrite H in H2 ")
            ground_arms_h.append(
                f"| H : {term} = false, H2 : context [{term}] |- _ => "
                f"rewrite H in H2 ")
        ground = ("repeat match goal with " + "".join(ground_arms) + "end;"
                  if ground_arms else "")
        ground_h = ("repeat match goal with " + "".join(ground_arms_h)
                    + "end;" if ground_arms_h else "")
        chunks.append(f"Ltac t_eqs := {eq_tac} {norm} {ground} idtac.\n")
        chunks.append(f"Ltac t_eqs_h := {eq_tac_h} {norm_h} {ground_h} idtac.\n")
        # ATTEMPTED AND REVERTED (2026-09-10, is_even): a second half of
        # this fix tried putting the identical ground arms inside a new
        # `t_sf_ground`, dispatched from `t_base`'s own `repeat (first
        # [...])` via `Ltac t_base ::= ...` (Coq's redefinition form,
        # confirmed to work at top level), so a fact `t_sat1`'s PRE-
        # EXISTING "leaf-provable antecedent" rule derives MID-SEARCH
        # (is_even's own `sf_even i = true`, from the loop invariant once
        # `r` is a concrete literal) would be available to the SAME
        # substitution, not only one asserted before `t_vc0` starts
        # (max_nit's own shape). MEASURED: this did not close is_even --
        # it turned a clean UNPROVED into TIMEOUT instead, the widened
        # `t_base` search costing real wall time across every one of its
        # `repeat` rounds for every goal in the file, on every bool-
        # spec_fun task, for no proof gained. Reverted before landing (the
        # diff below never touches this file): the ground fix stays
        # exactly what MEASURED clean, `t_eqs`/`t_eqs_h`'s own one-shot
        # arms plus the `t_eqs; t_eqs_h; t_vc0` alternative in `t_dis`/
        # `t_side` below, which is what closes max_nit. is_even is left
        # open, unchanged from before this session, named in this file's
        # dated note below.
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
        # Same "forall ," fix as emit_def_lemmas' own (2026-09-10): a
        # param-less spec_fun with a ground obligation would otherwise
        # render an empty binder list; unexercised by this family's own
        # `rowsum` (which has params), fixed here for the identical
        # reason regardless.
        fa = f"forall {allb},\n" if allb else ""
        out.append(
            f"Lemma {cx.task['name']}_def_{k} : {fa}{hyp_txt}"
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


def lower_v1(task: dict, body: list, witness: dict | None = None) -> str:
    # SPEC.md "Pairs (v1)": validate every pair type in the task FIRST,
    # unconditionally, before `_try_cert_v1`'s own try/except (which would
    # silently swallow the SAME check and just fall back) or anything else
    # gets a chance to reach a seq-component pair a different way and raise
    # the wrong exception (`_check_pair_types`'s own dated note, 2026-09-10:
    # fz_v1pairs_064's `{"pair": ["seq", "int"]}` return crashed inside
    # `spec_def_obls` with a bare ValueError before this existed).
    _check_pair_types(task)
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

    parts = [header(task, body)]
    parts.append(emit_spec_funs(cx))
    parts.append((POST_SF_NIA if _has_nonlinear_mul(task) else POST_SF) + "\n")

    counter = [0]
    parts.append(emit_sf_def_lemmas(cx, counter))
    req_obls, ens_obls = spec_def_obls(cx)
    parts.append(emit_def_lemmas(cx, name, req_obls, counter=counter))
    # a seq return owes the SAME two-binder expansion a seq param gets
    # (param_binders): the ens_obls lemmas below are schematic in the
    # return, so they need both the function AND its length in scope.
    # SPEC.md "Nested sequences (v1)": a nested return owes the SAME
    # two-binder expansion, only at rty's nested (row-pair) codomain.
    if ret_t == "seq" or (isinstance(ret_t, dict) and "seq" in ret_t):
        rb = f"({ret} : {rty(ret_t)}) ({ret}_len : Z)"
    else:
        rb = f"({ret} : {rty(ret_t)})"
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
    elif isinstance(ret_t, dict) and "seq" in ret_t:
        # SPEC.md "Nested sequences (v1)": the nested analogue of the
        # plain-seq default just above, an outer function returning an
        # empty row at every index, outer length 0.
        env0 = {ret: "(fun _ : Z => ((fun _ : Z => 0), 0))",
               ret + "_len": "0"}
    else:
        env0 = {ret: default_term(ret_t)}
    env = exec_straight(cx, body, env0, local, list(reqs), [], obls)
    def_txt = emit_def_lemmas(cx, name, obls, counter=counter)

    if isinstance(ret_t, dict) and "seq" in ret_t:
        # SPEC.md "Nested sequences (v1)": a nested return is the SAME
        # two-Definition split a plain seq return gets just below
        # (function half, length half), only at the row-pair codomain
        # (`rty`'s own nested branch). swap_rows is the committed task
        # on this path (loop-free, `update(update(m, i, m[j]), j, m[i])`).
        fn_expr, len_expr = env[ret], env[ret + "_len"]
        ens = ensures_text(cx, {ret: f"({name}_t {pargs})",
                                ret + "_len": f"({name}_t_len {pargs})"})
        pdestr = _pair_param_destruct(task)
        # SPEC.md "Nested sequences (v1)": `t_nupd_case` reading back an
        # in-range write leaves a literal Coq pair under `fst`/`snd`
        # (`seq_fn`'s new "at" case's own rendering), the SAME delta step
        # PAIRS (v1) built `cbn [fst snd]` for; `_has_nested` joins
        # `_has_pair` at this gate (both want the identical line).
        pair_line = ("  cbn [fst snd].\n"
                    if _has_pair(task) or _has_nested(task) else "")
        # Nested sequences (v1) residual (2026-09-10): `forall {pb},` with
        # an EMPTY `pb` (a param-less task, `nested_lit`'s own shape) is
        # "forall ," -- a Coq syntax error, MALFORMED (MEASURED, this
        # branch is unreached by any param-less task, but the identical
        # pattern just below IS, `fz_p_nest_lit`; fixed uniformly here
        # too rather than leaving one of three identical branches wrong).
        fa = f"forall {pb},\n" if pb else ""
        return f"""{def_txt}
Definition {name}_t {pb} : {rty(ret_t)} := {fn_expr}.
Definition {name}_t_len {pb} : Z := {len_expr}.

Theorem {name}_t_spec :
  {fa}{lens_arrows(cx)}{requires_arrows(cx)}  {ens}.
Proof.
  unfold {name}_t, {name}_t_len.
  intros.
{pdestr}{pair_line}  t_dis.
Qed.
"""

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
        # SPEC.md "Pairs (v1)": destruct every pair-typed PARAM right after
        # `intros.`, before `unfold` (`_pair_param_destruct`'s own dated
        # note, 2026-09-10: an opaque param's `fst`/`snd` never reduces on
        # its own). Empty for every task without one, byte-identical.
        pdestr = _pair_param_destruct(task)
        fa = f"forall {pb},\n" if pb else ""
        return f"""{def_txt}
Definition {name}_t {pb} : Z -> Z := {fn_expr}.
Definition {name}_t_len {pb} : Z := {len_expr}.

Theorem {name}_t_spec :
  {fa}{lens_arrows(cx)}{requires_arrows(cx)}  {ens}.
Proof.
  unfold {name}_t, {name}_t_len.
  intros.
{pdestr}  t_dis.
Qed.
"""

    expr = env[ret]
    ens = ensures_text(cx, f"({name}_t {pargs})")
    # SPEC.md "Pairs (v1)": one `fst`/`snd` delta step, ONCE, right where
    # `unfold` first exposes a literal pair; PRELUDE's "LOOSE fst/snd" note
    # (2026-09-10) explains why this is a plain proof-script line and not a
    # `t_inv1` match arm. `_has_pair` is False for every task before pairs
    # existed, so this line is absent there, byte-identical to before.
    # `_has_nested` (SPEC.md "Nested sequences (v1)") joins the same gate:
    # both features want the identical `cbn [fst snd]` line.
    pair_line = ("  cbn [fst snd].\n"
                if _has_pair(task) or _has_nested(task) else "")
    # SPEC.md "Pairs (v1)": destruct every pair-typed PARAM right after
    # `intros.`, before `unfold` (`_pair_param_destruct`'s own dated note,
    # 2026-09-10, `eq_params`: an opaque param's `fst`/`snd` never reduces
    # on its own, so the EXISTING `cbn [fst snd]` above is a no-op on it
    # without this). Empty for every task without a pair param.
    pdestr = _pair_param_destruct(task)
    # Nested sequences (v1) residual (2026-09-10): a param-less task
    # (`fz_p_nest_lit`, the fuzz corpus's own nested-literal probe, zero
    # params) makes `pb` empty; `forall {pb},` then renders as the bare
    # keyword with no binder, "forall ," -- a Coq syntax error, the
    # harness's own MALFORMED reading (MEASURED). Omitting the whole
    # `forall ... ,` line when there is nothing to bind keeps every task
    # WITH a param byte-identical (`fa` is `forall {pb},\n` exactly as
    # before whenever `pb` is non-empty).
    fa = f"forall {pb},\n" if pb else ""
    return f"""{def_txt}
Definition {name}_t {pb} : {rty(ret_t)} := {expr}.

Theorem {name}_t_spec :
  {fa}{lens_arrows(cx)}{requires_arrows(cx)}  {ens}.
Proof.
  unfold {name}_t.
  intros.
{pdestr}{pair_line}  t_dis.
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
    # SPEC.md "Pairs (v1)": one `fst`/`snd` delta step, ONCE, right after
    # the loop's own `cbn beta iota.` first exposes a literal pair
    # (PRELUDE's "LOOSE fst/snd" note, 2026-09-10, explains why this is a
    # plain proof-script line and not a `t_inv1` match arm). Empty (so
    # byte-identical to before pairs existed) for every task without one.
    # `_has_nested` (SPEC.md "Nested sequences (v1)") joins the same gate:
    # row_max_len reads a nested PARAM (`m[i]`, via `seq_fn`'s new "at"
    # case) inside this loop's body/invariants, so this line is present
    # for it even though it never itself constructs a literal row pair
    # (m is never reassigned); harmless when the pattern is absent, `cbn`
    # over an empty target set is a no-op.
    pair_line = ("  cbn [fst snd].\n"
                if _has_pair(task) or _has_nested(task) else "")

    # prefix symbolic execution (definedness under requires)
    local: dict[str, str] = {}
    obls: list = []
    if ret_t == "seq":
        env0 = {ret: "(fun _ : Z => 0)", ret + "_len": "0"}
    elif isinstance(ret_t, dict) and "seq" in ret_t:
        # Nested sequences (v1) residual (2026-09-10): `gen_plain` already
        # special-cases a nested return's env0 this way (an outer function
        # returning an empty row at every index, outer length 0);
        # `gen_loop` was missing the same branch, so a LOOP with a nested
        # RETURN (`build_matrix`'s own `m`, threaded to `r` only in the
        # suffix) fell to `default_term`, which names this exact gap and
        # abstains rather than guessing (MEASURED, `fz_v1nested_069`).
        env0 = {ret: "(fun _ : Z => ((fun _ : Z => 0), 0))",
               ret + "_len": "0"}
    else:
        env0 = {ret: default_term(ret_t)}
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

    # ROADMAP 16.2, 2026-09-11: a prefix-declared INT local the loop body
    # never reassigns (upWhileLess's `h := |a|`, held fixed as the loop
    # bound while `i_v2` walks up to it) is invariant across every
    # iteration, equal to whatever expression initialized it -- true
    # whether or not the task's own author wrote that fact down as one of
    # `w["invariants"]`. Measured: appendArrayToSeq, arrayToSeq,
    # getFirstElements, elementWiseDivide, addLists, squareElements,
    # findSmallest, smallestListLength (8 of the 15 lifted 2026-09-10
    # tasks) all share exactly this shape, and all eight read real=
    # unproved before this fix: coqc's own "Tactic failure: unsolved t
    # verification condition" on the loop body's OWN definedness lemma
    # (`_def_9`-style, indexing the source array at the loop's running
    # index) needs `i_v2 < a_len` from the guard's `i_v2 < h` PLUS `h =
    # a_len`, and nothing upstream of this fix ever stated `h = a_len` at
    # all: `h`'s own invariants only ever bound it against `i_v2`
    # (`i_v2 <= h`), never against its own defining expression. The fix
    # threads one synthetic invariant per such local -- `h == a_len` here,
    # rendered through the SAME `cx.prop`/`cx.defs` calls every other
    # invariant already goes through below, so it gets the same
    # definedness check, the same per-step preservation proof (trivial:
    # the loop body never touches `h`, so the Fixpoint's induction closes
    # `h' = a_len` for free), and the same initial-state assertion,
    # costing nothing new anywhere those already succeed. A task with no
    # such local (every committed task through 2026-09-10) computes an
    # empty list here and renders byte-identical to before this existed.
    #
    # MEASURED WRONG once (2026-09-11), fixed by the `not has_return`
    # guard below: containsSequence/containsK/isSmaller (the PRESERVATION-
    # witness family, ROADMAP 16.2's own brief naming these three "another
    # builder's", out of this fix's scope) share the identical `h := |a|`
    # prefix shape but ALSO have a `return` inside the loop body, so their
    # `t_dis_ext`/`t_side_ext` proofs run PRELUDE's witness-instantiation
    # search (t_go_ext: "every (forall-hypothesis, Z-variable) pair"),
    # whose cost is sensitive to the hypothesis COUNT. Adding one more
    # (trivially true, `h = a_len`) hypothesis to that search's context
    # cost containsSequence nothing in correctness but ~60x its own wall
    # time (0.9s, honest UNPROVED -> 60s+ TIMEOUT, same file otherwise
    # byte-identical, MEASURED both ways) with no compensating win (the
    # real gap there is the preservation family's own, untouched by this
    # fix either way). None of the 8 target tasks (appendArrayToSeq and
    # siblings) has a `return` in its loop body, so this guard costs them
    # nothing; `has_return` is the exact predicate `gen_loop`'s own
    # early-exit branch (below) already uses to pick its Fixpoint shape.
    _body_assigned = loop_assigned(w["body"])
    _extra_invs = [] if has_return(w["body"]) else [
        {"op": "==", "args": [{"var": s["var"]["name"]}, s["var"]["init"]]}
        for s in prefix
        if "var" in s
        and s["var"].get("type") == "int"
        and s["var"]["name"] not in _body_assigned
    ]
    invariants_ast = list(w.get("invariants", [])) + _extra_invs

    guard_b = cx.bx(w["cond"], id_env, local)
    guard_p = cx.prop(w["cond"], id_env, local)
    dec = cx.zx(w["decreases"], id_env, local)
    invs = [cx.prop(e, id_env, local) for e in invariants_ast]

    # invariant definedness: each invariant assumes requires + earlier ones.
    # THE STRING LIBRARY (v1), 2026-09-11: count_vowels' own invariant is
    # a bare (non-quantified) equation whose embedded `slice(s, 0, i)`
    # needs `0 <= i <= len(s)`, but those bounds are SIBLING invariants
    # listed AFTER it, not derivable from "requires + earlier ones" alone
    # (unlike row_max_len/seq_max/etc.'s own `at`, always under a
    # `forall` whose OWN binder already supplies its range, defs()'s
    # "forall" case, untouched). Since every invariant in a while loop
    # holds SIMULTANEOUSLY (not a dependency chain), widening the
    # definedness context to every sibling invariant -- not only the
    # ones textually before it -- is the semantically correct rule; it
    # is applied ONLY when the task uses a string-library member
    # (`_has_strlib`), so a task built before this wave keeps its
    # ORIGINAL sequential-prefix context, byte-identical proof text.
    inv_ctx = list(reqs)
    def_ctx = list(reqs) + invs if _has_strlib(task) else None
    sb = " ".join(f"({v} : {slot_ty[v]})" for v in svars_x)
    for e in invariants_ast:
        iob: list = []
        cx.defs(e, list(def_ctx) if def_ctx is not None else list(inv_ctx),
                [], iob, id_env, local)
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
    invs_p = [cx.prop(e, penv, local) for e in invariants_ast]
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
    body_assigned = _body_assigned
    frame = [v for v in svars_x if slot_owner(v, svars) not in body_assigned]
    concl = " /\\ ".join(invs_p + [f"(~ {guard_pp})"]
                         + [f"{v}' = {v}" for v in frame])

    # SPEC.md "Pairs (v1)" residual (2026-09-10): a bool loop-state var
    # actually reassigned in the body (a sentinel `found` flag) needs a
    # `destruct` before `t_sweep` sees it, and again on the PRIMED name
    # right before the theorem's own closing `t_dis`/`t_dis_ext`
    # (`_bool_state_assigned`'s own dated note: NOT a pairs bug, but every
    # fuzzed task that trips it also returns a pair, so it is gated and
    # fixed here). Empty for every task without one (every pre-pairs
    # committed task, `is_prime` included, and both committed pair tasks):
    # byte-identical proof text.
    # `bool_destruct` is spliced INTO the existing one-line
    # "cbn [...]; t_sweep;" (as " destruct ...;"), not onto its own line,
    # so the empty case renders BYTE-IDENTICAL to before this fix existed
    # (the same discipline `pair_line`/`pdestr` keep by owning their own
    # line instead).
    # `destruct` on a bool produces TWO subgoals; `bool_destruct_p` must
    # stay semicolon-chained onto the SAME `t_dis`/`t_dis_ext` call rather
    # than owning its own period-terminated line, or only the FIRST
    # resulting subgoal gets closed and `Qed` reports an incomplete proof
    # on the second (MEASURED WRONG, 2026-09-10: a period-separated
    # `destruct found'.` followed by a bare `t_dis.` on the next line
    # compiled to exactly this "Attempt to save an incomplete proof"
    # error on every sentinel-shape task; fixed by chaining with `;`
    # instead, mirroring `bool_destruct`'s own inline splice above).
    bool_assigned = _bool_state_assigned(svars, stys, body_assigned)
    bool_destruct = (" destruct " + ", ".join(bool_assigned) + ";"
                      if bool_assigned else "")
    bool_destruct_p = ("destruct "
                        + ", ".join(v + "'" for v in bool_assigned) + "; "
                        if bool_assigned else "")
    # SPEC.md "Pairs (v1)": destruct every pair-typed PARAM right after
    # `intros.`, before `unfold` (`_pair_param_destruct`'s own dated note,
    # 2026-09-10). Empty for a task with no pair param (both committed
    # loop tasks, min_max included, have none).
    pdestr = _pair_param_destruct(task)

    if ret_t == "seq" or (isinstance(ret_t, dict) and "seq" in ret_t):
        # Nested sequences (v1) residual (2026-09-10): a nested RETURN
        # from a LOOP (`build_matrix`'s own `m`, threaded to `r` only in
        # the suffix) is the SAME two-Definition split a plain seq return
        # already gets here; the plain `== "seq"` check missed it (a dict
        # never equals the string "seq"), so `ret_t`'s own `_len` half
        # was never substituted into `ens` at all, leaving a bare, unbound
        # `r_len` in the rendered Theorem -- "The reference r_len was not
        # found in the current environment", the harness's own MALFORMED
        # reading (MEASURED, `fz_v1nested_069`).
        ens = ensures_text(cx, {ret: f"({name}_t {pargs})",
                                ret + "_len": f"({name}_t_len {pargs})"})
    else:
        ens = ensures_text(cx, f"({name}_t {pargs})")
    state_names = " ".join(svars_x)
    primed_names = " ".join(primed)
    param_names = pargs

    ini_asserts = "".join(
        f"  assert (Hini{k+1} : {cx.prop(e, {v: env_pre[v] for v in svars_x}, local)}) by t_dis.\n"
        for k, e in enumerate(invariants_ast))
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
        elif isinstance(ret_t, dict) and "seq" in ret_t:
            # Nested sequences (v1) residual (2026-09-10): the SAME two-
            # Definition split just above, only at `rty(ret_t)`'s nested
            # codomain rather than the plain seq's "Z -> Z" (`gen_plain`'s
            # own nested branch already does this; `gen_loop` was missing
            # it, `fz_v1nested_069`'s own MALFORMED reading above).
            def_lines = (
                f"Definition {name}_t {pb} : {rty(ret_t)} :=\n"
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

        # 2026-09-10, upWhileLess: `destruct t as <bare name> eqn:Heq`
        # needs a full DISJUNCTIVE pattern (one sub-pattern per
        # constructor) whenever the destructed type has more than one
        # constructor -- MEASURED, a standalone probe on a bare `Z`
        # result: "Error: Disjunctive/conjunctive introduction pattern
        # expected." `pat_p` is a bracket pattern `[a' b']` (2+ state
        # vars, a genuine pair/product with exactly ONE constructor, so a
        # flat list of sub-names is exactly right) in every task built so
        # far, since every prior loop task has 2+ state vars; upWhileLess
        # is the first with exactly one (`i`), where `pat_p` is a BARE
        # name and the destructed value's own type (Z here, same story
        # for bool) has 3 (or 2) constructors, not 1 -- confirmed the
        # same break for a single-var PAIR-typed state too (probed
        # separately), so the fix is keyed on the STATE-VAR COUNT, not
        # the type. `remember` never case-splits (it only names the term
        # and records the equation), so it is correct regardless of how
        # many constructors the type has; its own equation direction is
        # backwards from `destruct ... eqn:`'s convention (`i' = t`, not
        # `t = i'`), fixed by one `symmetry in Heq` right after so every
        # downstream use of `Heq` (the `pose_args` forwarding it into
        # `{name}_loop_spec`, the final `clear`) is unchanged. A 2+-var
        # task's own destruct text is untouched, byte for byte.
        if len(svars_x) == 1:
            destruct1_txt = (
                f"  remember ({name}_loop (S (Z.to_nat {dec0})) {pargs} "
                f"{init_terms})\n    as {pat_p} eqn:Heq.\n  symmetry in Heq.\n")
        else:
            destruct1_txt = (
                f"  destruct ({name}_loop (S (Z.to_nat {dec0})) {pargs} "
                f"{init_terms})\n    as {pat_p} eqn:Heq.\n")

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
  cbn [{name}_loop];{bool_destruct} t_sweep;
  (* `try clear Heq`, not a bare `clear Heq` (2026-09-10, upWhileLess: a
     ONE-Z-variable loop state, the only committed/lifted shape so far
     small enough to expose this): when the non-recursing branch's own
     equation is between two bare Z variables (no tuple/pair to inject),
     `inversion Heq` duplicates it into a fresh `H` and `subst` then
     consumes and auto-clears the ORIGINAL `Heq` itself (MEASURED,
     standalone probe), so the following bare `clear Heq` errored "No
     such hypothesis", caught by `first` as this branch's own failure and
     silently falling through to the final `fail`, discarding a goal
     `t_dis` could otherwise close outright. A 2+-variable state tuple's
     `Heq` is a genuine constructor-vs-constructor equation `inversion`
     does not eat this way, which is why every task built before this one
     never exposed it. *)
  first [ solve [ apply IH; t_side ]
        | (let Heq := fresh "Heq" in
           intro Heq; inversion Heq; subst; try clear Heq; t_dis)
        | fail 1 "unsolved t verification condition" ].
Qed.

Theorem {name}_t_spec :
  forall {pb},
{lens_arrows(cx)}{requires_arrows(cx)}  {ens}.
Proof.
  intros {param_names} {lens_intro} {reqs_intro}.
{pdestr}  {unfold_line}
{destruct1_txt}  cbn beta iota.
{pair_line}  assert (Hfb : {dec0} < Z.of_nat (S (Z.to_nat {dec0}))) by lia.
{ini_asserts}  pose proof ({name}_loop_spec {pose_args}) as Hout.
  clear Hfb Heq {ini_intro}.
  {bool_destruct_p}t_dis.
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
  cbn [{name}_loop];{bool_destruct} t_sweep;
  (* `try clear Heq`: the same fix as the non-return `gen_loop` branch
     above, applied here defensively (this shape's own equation is always
     a genuine pair `(state, bool)`, never a bare Z=Z, so no committed or
     lifted task has exercised the failure here yet; `try` costs a
     passing task nothing either way). *)
  first [ solve [ apply IH; t_side_ext ]
        | (let Heq := fresh "Heq" in
           intro Heq; inversion Heq; subst; try clear Heq; t_dis_ext)
        | fail 1 "unsolved t verification condition" ].
Qed.

Theorem {name}_t_spec :
  forall {pb},
{lens_arrows(cx)}{requires_arrows(cx)}  {ens}.
Proof.
  intros {param_names} {lens_intro} {reqs_intro}.
{pdestr}  unfold {name}_t.
  destruct ({name}_loop (S (Z.to_nat {dec0})) {pargs} {init_terms})
    as [{pat_p} {rf}] eqn:Heq.
  cbn beta iota.
{pair_line}  assert (Hfb : {dec0} < Z.of_nat (S (Z.to_nat {dec0}))) by lia.
{ini_asserts}  pose proof ({name}_loop_spec {pose_args}) as Hout.
  clear Hfb Heq {ini_intro}.
  {bool_destruct_p}t_dis_ext.
Qed.
"""


def gen_rec(cx: Ctx, body: list) -> str:
    task = cx.task
    name = task["name"]
    ret = task["returns"][0]["name"]
    ret_t = task["returns"][0]["type"]
    pb, pargs = param_binders(cx)
    default = default_term(ret_t)
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


def _glit(v, ty) -> str:
    """A concrete t VALUE (interp.py's own JSON-shown shape: an int/bool
    literal, or, for a pair, `_j`'s nested 2-list `[a, b]`) rendered as a
    Coq literal term. A pair type recurses componentwise into the SAME
    `(a, b)` notation `px()`'s own `pair` case builds."""
    if isinstance(ty, dict) and "seq" in ty:
        raise NotImplementedError(
            "rocq lowering: _glit has no literal form for a nested seq; "
            "a nested value's witness goes through _nested_witness_pieces")
    if isinstance(ty, dict):
        t1, t2 = ty["pair"]
        return f"({_glit(v[0], t1)}, {_glit(v[1], t2)})"
    if ty == "bool":
        return "true" if v else "false"
    return _zlit(v)


def _to_interp_value(v, ty):
    """The reverse direction of `_glit`'s JSON shape: convert a witness
    value (SPEC.md/interp.py's `_j`, a plain int/bool or a nested 2-list
    for a pair) back into the runtime value `interp.ev` itself expects
    (`interp.Pair`, recursing on components; int/bool unchanged). Needed
    wherever a witness value re-enters `interp.ev`/`interp.funs_of`-driven
    evaluation (`_falsified_conjunct`, `_call_asserts`), since `interp.py`'s
    `fst`/`snd` read `.a`/`.b` off an actual `Pair`, never a bare list."""
    if isinstance(ty, dict) and "seq" in ty:
        raise NotImplementedError(
            "rocq lowering: _to_interp_value has no form for a nested "
            "seq; nested witnesses are built directly as Python lists of "
            "lists (interp.py's own tuple-of-tuples convention), never "
            "through this pair-shaped helper")
    if isinstance(ty, dict):
        t1, t2 = ty["pair"]
        return interp.Pair(_to_interp_value(v[0], t1), _to_interp_value(v[1], t2))
    return v


def _pair_default_py(t):
    """The Python-VALUE counterpart of `default_term`: the type's own
    default (0/False, recursing on a pair) in interp.py's JSON shape, used
    when a witness's `_twin` is "no value" (Reference.witness's own
    convention for a lowered path that assigns nothing) and `_value_cert`
    still needs SOME concrete value of the right type to check `ensures`
    against."""
    if isinstance(t, dict):
        t1, t2 = t["pair"]
        return [_pair_default_py(t1), _pair_default_py(t2)]
    return False if t == "bool" else 0


def _seq_lambda(vals: list) -> str:
    if not vals:
        return "fun _ : Z => 0"
    expr = "0"
    for k in range(len(vals) - 1, -1, -1):
        expr = f"if t_k =? {k} then {_zlit(vals[k])} else ({expr})"
    return f"fun t_k : Z => {expr}"


def _nested_lambda(row_terms: list) -> str:
    """SPEC.md "Nested sequences (v1)": the outer-level analogue of
    `_seq_lambda`, same if-chain shape over `t_k`, but each LEAF is a
    literal Coq PAIR `(row_fn, row_len)` (a row's own already-built
    `t_w_<v>_r<k>` Definition name and its length) instead of `_zlit`'s
    bare int, matching `t_nupd`'s own codomain `(Z -> Z) * Z`."""
    if not row_terms:
        return "fun _ : Z => ((fun _ : Z => 0), 0)"
    expr = "((fun _ : Z => 0), 0)"
    for k in range(len(row_terms) - 1, -1, -1):
        fn, rlen = row_terms[k]
        expr = f"if t_k =? {k} then ({fn}, {_zlit(rlen)}) else ({expr})"
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


def _nested_witness_pieces(v: str, rows: list):
    """Coq pieces for a concrete NESTED seq value `rows` (a list of int
    lists) presented as `v` (SPEC.md "Nested sequences (v1)"), the
    two-level analogue of `_seq_witness_pieces`: one `t_w_<v>_r<k>`
    Definition per ROW (`_seq_lambda`, reused verbatim, a row IS an
    ordinary seq value), then an outer function `t_w_<v>` mapping an
    index to the literal pair `(t_w_<v>_r<k>, len(row k))`, built with
    `_nested_lambda`'s own pair-leaf if-chain. row_max_len (the committed
    loop task carrying this construct) reads this via its nested PARAM
    `m`, never a loop-state var, through `_loop_cert`'s own `_witness_env`
    call.

    THE POINTWISE FACT'S OWN SHAPE (2026-09-10, row_max_len's own
    certificate). `_seq_witness_pieces`'s plain-seq pointwise fact is
    `t_p_<v>_<k> : fn k = literal`, an INT equation the same shape
    `forall`-hypotheses over `f k` already E-match against. Asserting the
    OUTER analogue `t_w_<v> k = (row_fn, row_len)` (a PAIR equation) does
    NOT compose the same way: row_max_len's own invariants/ensures never
    read the outer application bare, only through `snd (m k)` (a row's
    LENGTH, `zx`'s "len" case composed with `seq_fn`'s new "at" case), so
    after `set` folds the witness's name to `m`, the search would need to
    rewrite `m k` to the literal pair FIRST and only THEN reduce
    `snd (literal pair)`, a two-step sequence no existing arm performs in
    that order (MEASURED WRONG: an outer `cbn [fst snd] in *` placed
    before `t_feed`/`t_dis`, mirroring `t_nupd_case`'s own fix, is a
    no-op here, since `m k` is not yet a literal pair at that point --
    the rewrite via the pointwise fact is exactly the step `t_dis`'s own
    search would still have to perform afterward, and nothing here
    prompts a SECOND reduction pass once it does). The fix is to assert
    the fact ALREADY PROJECTED to the shape row_max_len's own ensures
    actually uses: `t_p_<v>_<k> : snd (t_w_<v> k) = len(row k)`, an INT
    equation (provable by `reflexivity`: Coq computes straight through
    the transparent `t_w_<v>`/`t_nested_lambda` if-chain and `snd`'s own
    iota step in one pass), which becomes `snd (m k) = len(row k)` after
    `set`, the EXACT syntactic shape `forall k, ... snd (m k) <= r`
    already carries -- no extra reduction step needed at all, matching
    the plain-seq case's own shape rather than extending it. NAMED
    LIMITATION: this proves a witness ROW's LENGTH reachable through
    `snd`; a row's own ELEMENTS through `fst` (SPEC.md's `s[i][j]`) are
    not wired into a loop CERTIFICATE's witness this way, since no
    committed task's invariant/ensures reads one -- `seq_fn`'s own "at"
    case still renders `s[i][j]` correctly wherever it appears in the
    REAL lowering's own proof (gen_plain/gen_loop, unaffected by this),
    only a hypothetical future certificate needing row CONTENT through a
    witness would need a matching `fst`-shaped pointwise fact added
    here."""
    row_defs = []
    row_terms = []
    for k, row in enumerate(rows):
        fn = f"t_w_{v}_r{k}"
        row_defs.append(f"Definition {fn} : Z -> Z := {_seq_lambda(row)}.\n")
        row_terms.append((fn, len(row)))
    outer_fn = f"t_w_{v}"
    outer_def = (f"Definition {outer_fn} : Z -> ((Z -> Z) * Z) := "
                f"{_nested_lambda(row_terms)}.\n")
    ln = _zlit(len(rows))
    env = {v: outer_fn, v + "_len": ln}
    ptw = [f"  assert (t_p_{v}_{k} : snd ({outer_fn} {k}) = {_zlit(rlen)}) "
           f"by reflexivity.\n"
           for k, (_, rlen) in enumerate(row_terms)]
    setline = f"  set ({v} := {outer_fn}) in *.\n"
    return env, "".join(row_defs) + outer_def, ptw, setline, [outer_fn, ln]


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
        elif isinstance(p["type"], dict) and "seq" in p["type"]:
            # SPEC.md "Nested sequences (v1)": a nested param's witness
            # value is a Python list of lists (interp.py's own JSON
            # shape); `_nested_witness_pieces` is `_seq_witness_pieces`'s
            # own two-level analogue.
            rows = [list(r) for r in wv]
            env_py[v] = rows
            et, defline, ptwl, setl, sargs = _nested_witness_pieces(v, rows)
            env_txt.update(et)
            seq_defs.append(defline)
            ptw += ptwl
            sets.append(setl)
            spec_args += sargs
        else:
            # SPEC.md "Pairs (v1)": a pair PARAM's witness value is `_j`'s
            # nested 2-list; `_to_interp_value` is the identity for int/
            # bool, so this is unchanged for every non-pair param (no
            # committed task has a pair PARAM yet, both divmod_pair and
            # min_max only return one, so this arm is measured only by
            # construction).
            env_py[v] = _to_interp_value(wv, p["type"])
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
    pb, _ = param_binders(cx)
    local: dict = {}
    if ret_t == "seq":
        # ROADMAP 16.2, 2026-09-11: `_value_cert`'s "Sequences as values
        # (v1)" branch (SPEC.md, ROADMAP 13.4, fz_p_seqeq_false) wants
        # exactly the two-Definition split `gen_plain`/`gen_loop` already
        # build for a plain-seq return -- a function half (`_t`) and a
        # length half (`_t_len`) -- and calls both `{name}_t` and
        # `{name}_t_len` by name. This function used to bail outright on
        # `ret_t == "seq"` with a comment saying its only caller
        # (`_value_cert`) "abstains on a seq return outright", true the
        # day it was written but stale since `_value_cert` grew that
        # branch: a PLAIN (loop-free), non-recursive task with a seq
        # return and a "value" witness -- swap's own shape, `[b, a]` --
        # had no certificate reachable at all, `_try_cert_v1` returning
        # None from `def_text is None` alone before ever reaching
        # `_value_cert`, and the twin fell back to the plain unprovable
        # theorem: real=verified/twin=UNPROVED, not the honest REFUTED
        # the measured witness (a=0, b=1: real [1,0], twin [0,0]) already
        # supports. Mirrors `gen_plain`'s own plain-seq env0/split
        # exactly; a task with a loop or a self-call never reaches this
        # branch (`_loop_def`/`_rec_def` own those), so nothing about
        # them changes.
        env0 = {ret: "(fun _ : Z => 0)", ret + "_len": "0"}
        env = exec_straight(cx, body, env0, local, None, [], [])
        return (f"Definition {task['name']}_t {pb} : Z -> Z := "
                f"{env[ret]}.\n"
                f"Definition {task['name']}_t_len {pb} : Z := "
                f"{env[ret + '_len']}.\n")
    env0 = {ret: default_term(ret_t)}
    env = exec_straight(cx, body, env0, local, None, [], [])
    return (f"Definition {task['name']}_t {pb} : {rty(ret_t)} := "
            f"{env[ret]}.\n")


def _rec_def(cx, task, body):
    name = task["name"]
    ret = task["returns"][0]["name"]
    ret_t = task["returns"][0]["type"]
    pb, pargs = param_binders(cx)
    default = default_term(ret_t)
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
        env0 = {ret: default_term(ret_t)}
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
    # Early exit (2026-09-11, ROADMAP 13.4 / fz_p_ret_falsens): a
    # certificate's twin loop is the SAME Fixpoint shape gen_loop emits
    # for verification, `return`-in-loop included -- a value witness for
    # a return-bearing loop (the real body's own bounded-scan witness, or
    # a twin's) needs the identical two-outcome (state, returned-flag)
    # Fixpoint gen_loop's step_done-!=-"false" branch builds, mirrored
    # here WITHOUT the induction lemma (`_value_cert` grounds the whole
    # thing by `cbv; reflexivity` at the witness's own literal arguments,
    # no induction needed). Before this, a return-bearing loop's witness
    # fell through `_loop_def`'s single-outcome model (which silently
    # drops the early return and computes the loop's POST-exit state
    # instead, the wrong value at a witness whose whole point is the
    # early exit), _try_cert_v1's broad except caught whatever followed,
    # cert building returned None, and the fallback plain lowering then
    # tried to prove the task's `ensures` UNIVERSALLY -- false by
    # construction for an adversarial probe like fz_p_ret_falsens -- so
    # the real read UNPROVED, never REFUTED. Gated on the SAME
    # `_DONE`-derived `step_done` gen_loop reads (`exec_straight` already
    # computes it above), and the same seq-state abstain gen_loop raises
    # NotImplementedError for (returning None here instead, since a
    # cert's own gap is an opportunistic abstain, not a hard refusal):
    # `_try_cert_v1`'s caller falls back to the normal lowering exactly
    # as it always has whenever a certificate cannot be built.
    step_done = step_env.get(_DONE, "false")
    if step_done != "false" and any(stys[v] == "seq" for v in svars):
        return None
    # parenthesize a seq slot's "Z -> Z" before joining with `*` (gen_loop's
    # own fix, same reason: "->" binds looser than "*" in Coq's grammar).
    tup_ty = "(" + " * ".join(
        f"({slot_ty[v]})" if "->" in slot_ty[v] else slot_ty[v]
        for v in svars_x) + ")%type"
    tup = "(" + ", ".join(svars_x) + ")"
    sb = " ".join(f"({v} : {slot_ty[v]})" for v in svars_x)
    if step_done == "false":
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
    else:
        # ret_t is neither "seq" nor a nested-seq dict here (the guard
        # above already abstained on any seq-typed STATE var when a
        # return is present; the RETURN's own type, ret_t, is what
        # `rty(ret_t)` names below -- int/bool/pair, gen_loop's own
        # early-exit branch covers exactly this set).
        rf = f"{name}_rf"
        step_tup = "(" + ", ".join(step_env[v] for v in svars_x) + ")"
        fixpoint_txt = f"""Fixpoint {name}_loop (fuel : nat) {pb} {sb} : ({tup_ty.removesuffix("%type")} * bool)%type :=
  match fuel with
  | O => ({tup}, false)
  | S fu =>
      if {guard_b}
      then (if {step_done} then ({step_tup}, true) else {name}_loop fu {pargs} {step_terms})
      else ({tup}, false)
  end.
"""
        def_lines = (
            f"Definition {name}_t {pb} : {rty(ret_t)} :=\n"
            f"  let '({tup}, {rf}) := {name}_loop (S (Z.to_nat {dec0})) "
            f"{pargs} {init_terms} in\n"
            f"  if {rf} then {ret} else {env_post[ret]}.\n")
    text = fixpoint_txt + "\n" + def_lines
    return text, dict(svars=svars, svars_x=svars_x, stys=stys,
                      slot_ty=slot_ty, id_env=id_env, local=local,
                      step_env=step_env, env_post=env_post, sb=sb)


def _value_cert(cx, task, body, witness, def_text):
    """Certificate chunk for a whole-program value witness, or None.

    2026-09-10 (COVERAGE-lifted-785.md's twelfth sweep, the two
    parameterless sole blockers, f1a__f and ghost__m): a param-less task
    was refused outright by the guard this replaces. Nothing downstream
    actually needs a param: `_witness_env` already returns empty
    env_py/env_txt/etc. for an empty `task["params"]` (its `for p in
    task["params"]` loop just does not run), `_plain_def` already renders
    a correct nullary `Definition {name}_t  : Z := ...` for exactly this
    shape (matched byte for byte by the twin `.v` already on disk before
    this fix, e.g. `f1a__f`'s own `Definition ..._f_t  : Z := 1.`), and
    the `gargs` loop just below is empty for an empty params list, giving
    `applied = "(name_t )"`, a bare identifier in extra parens, valid
    Coq syntax. The one thing that WAS missing is exactly this function's
    own refusal to try; every task with at least one param is unaffected
    (this guard never fired for one)."""
    name = task["name"]
    ret = task["returns"][0]["name"]
    ret_t = task["returns"][0]["type"]
    if isinstance(ret_t, dict) and "seq" in ret_t:
        # A NESTED seq return's witness `_twin` is a list of lists
        # (interp.py's own tuple-of-tuples convention); no committed or
        # fuzzed task needs a value-witness certificate at that shape yet
        # (build_matrix's own witnesses are all "undefined"-kind), so this
        # still abstains rather than guessing -- the plain-`seq` case just
        # below is the one SPEC.md's own probe (fz_p_seqeq_false) needs.
        return None
    got = _witness_env(task, witness)
    if got is None:
        return None
    env_py, env_txt, seq_defs, ptw, sets, _ = got
    tv = witness.get("_twin")
    if ret_t == "seq":
        # SPEC.md "Sequences as values (v1)" / ROADMAP 13.4
        # (fz_p_seqeq_false, 2026-09-11): a "value" witness's `_twin` for
        # a plain seq return is a Python list (interp.py's own JSON
        # shape, `_j`'s tuple-to-list); the real return already gets the
        # SAME two-slot (function, length) treatment every seq value
        # here does (`def_text`, built by `_loop_def`/callers upstream),
        # so the only new work is (1) `env_py[ret]` as the tuple
        # `interp.ev` expects, so `_falsified_conjunct` can decide
        # whether this witness is actually a refutation, and (2) a
        # bespoke proof script -- `t_dis`'s generic search has no arm for
        # a seq-extensional forall (that gap is exactly why the WHOLE
        # ensures reads UNPROVED without a certificate), so this builds
        # one directly: `decompose [and]` flattens every `/\\` SPEC.md's
        # `==`-on-seq rule nests in WITHOUT reducing anything first (a
        # standalone probe measured `cbv` here BEFORE decompose unfolding
        # `Z.le`/`Z.lt` into raw positive-number `match`es, which the
        # `repeat match` below's `_ <= t_k < _` pattern no longer
        # recognises syntactically -- MEASURED WRONG, fz_p_seqeq_false's
        # own certificate read UNPROVED, "Cannot find witness"); the
        # UNREDUCED length-equality hyp decompose already produces
        # (`AppliedLen = literal`) is exactly what the `repeat match`'s
        # own `ltac:(lia)` bound proof needs (lia substitutes through a
        # symbolic-atom equality without any reduction), so `cbv`
        # narrows to just the one SPECIALIZED hyp (a plain function
        # application at a literal index, safe to fully ground) after
        # each match. `repeat match` finds the resulting
        # `forall t_k, lo <= t_k < hi -> fnA t_k = fnB t_k` hypothesis
        # (if any -- a pure length mismatch needs none) and instantiates
        # it at ONE concrete index this file computes in Python, a real
        # differing index when the ensures compares `ret` against a seq
        # PARAM whose own witness value is known, else 0 (still correct
        # whenever the two seqs' LENGTHS already differ, since that
        # conjunct alone closes the goal without ever reaching the
        # forall).
        if not isinstance(tv, list):
            return None
        env_py[ret] = tuple(tv)
        if not _falsified_conjunct(task, body, env_py):
            return None
        gargs = []
        for p in task["params"]:
            if p["type"] == "seq" or (isinstance(p["type"], dict)
                                       and "seq" in p["type"]):
                gargs += [env_txt[p["name"]], env_txt[p["name"] + "_len"]]
            else:
                gargs.append(env_txt[p["name"]])
        applied_fn = f"({name}_t {' '.join(gargs)})"
        applied_len = f"({name}_t_len {' '.join(gargs)})"
        env_stmt = dict(env_txt)
        env_stmt[ret] = applied_fn
        env_stmt[ret + "_len"] = applied_len
        stmt = " /\\ ".join(cx.prop(e, env_stmt) for e in task["ensures"])
        idx = 0
        for e in task["ensures"]:
            if e.get("op") not in ("==", "!="):
                continue
            a, b = e["args"]
            other = None
            if a == {"var": ret} and isinstance(b, dict) and "var" in b:
                other = b["var"]
            elif b == {"var": ret} and isinstance(a, dict) and "var" in a:
                other = a["var"]
            if (other is not None and isinstance(env_py.get(other), tuple)):
                ov = list(env_py[other])
                for i in range(min(len(tv), len(ov))):
                    if tv[i] != ov[i]:
                        idx = i
                        break
                break
        # ROADMAP 16.2, 2026-09-11 (swap's own witness, a=0, b=1): the
        # `repeat match` above only reaches a FORALL-shaped conjunct (two
        # seq params compared pointwise); a conjunct that is itself a
        # concrete-index equation against a scalar (`result[0] == b`,
        # never wrapped in a `forall`) is left exactly as `decompose`
        # produced it -- an unreduced application of `{name}_t`/`t_upd`/
        # `t_fill` at literal arguments, which `lia` cannot see through
        # (it treats an opaque function application as an atom, not a
        # number). One `cbv in *` between the match and the closing
        # `lia`, unconditional and free of any `_kind`/witness-shape
        # gate, reduces every surviving hypothesis (the `forall`-derived
        # ones already `cbv`'d above are idempotent under a second pass)
        # to literal numerals at these concrete literal arguments, which
        # is exactly what let this same idiom already close the plain
        # (non-seq) `_v0_cert`/`_undef_cert` certificates by `lia` alone.
        # A task whose falsifying conjunct WAS already forall-shaped
        # (row_max_len, seq_max) already had every hypothesis reduced by
        # the match's own per-hit `cbv in H`, so this second, blanket
        # pass is a no-op for them, confirmed by the unchanged AGREEMENT
        # regression below.
        proof = (
            "Proof.\n"
            "  intro t_H.\n"
            "  decompose [and] t_H; clear t_H.\n"
            "  repeat match goal with\n"
            "  | H : forall t_k : Z, _ <= t_k < _ -> _ = _ |- False =>\n"
            f"      specialize (H {_zlit(idx)} ltac:(lia)); cbv in H\n"
            "  end.\n"
            "  cbv in *.\n"
            "  lia.\n"
            "Qed.\n")
        return ("".join(seq_defs) + "\n" + def_text + "\n"
                f"(* The spec fails at the measured witness, "
                f"{harness.witness(witness)}: the kernel evaluates the "
                f"twin there and accepts the negation. *)\n"
                f"Theorem {CERT_NAME} :\n"
                f"  ~ ({stmt}).\n" + proof)
    if isinstance(ret_t, dict):
        # SPEC.md "Pairs (v1)": a pair return's witness `_twin` is `_j`'s
        # nested 2-list `[a, b]` (interp.py's own Pair-to-JSON shape), not
        # `_glit`'s bare int/bool contract; divmod_pair's wrong-var twin
        # and min_max's collapse-if twin both always assign `r` before
        # returning (neither has a path that leaves it unset), so "no
        # value" is not measured here, but `_pair_default_py` covers it the
        # same way "false"/0 already do for bool/int.
        if tv == "no value":
            tv = _pair_default_py(ret_t)
        if not isinstance(tv, list):
            return None
    else:
        if tv == "no value":
            # the lowered twin returns the type's default on that path
            tv = False if ret_t == "bool" else 0
        if not isinstance(tv, (int, bool)):
            return None
    env_py[ret] = _to_interp_value(tv, ret_t)
    if not _falsified_conjunct(task, body, env_py):
        return None
    gargs = []
    for p in task["params"]:
        if p["type"] == "seq" or (isinstance(p["type"], dict)
                                   and "seq" in p["type"]):
            # Nested sequences (v1) residual (2026-09-10): a nested param
            # is the SAME two-slot (fn, len) split a plain seq already
            # gets here; the plain `== "seq"` string check missed it
            # (a dict never equals the string "seq"), so a nested param's
            # own `_len` arg was silently DROPPED from this call, one
            # argument short of `{name}_t`'s own signature -- a Coq type
            # error ("has type bool while it is expected to have type
            # Z -> bool"), the harness's own MALFORMED reading (MEASURED,
            # `fz_v1nested_007`).
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
        if isinstance(ret_t, dict):
            # SPEC.md "Pairs (v1)": `rewrite t_out` just planted the
            # literal pair `retlit` where `applied` stood; one `fst`/`snd`
            # delta step, here, once (PRELUDE's "LOOSE fst/snd" note,
            # 2026-09-10: NOT a `t_inv1` match arm, measured too slow
            # inside that hot per-branch tactic on a loop-shaped task).
            lines.append("  cbn [fst snd].\n")
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
        # ground the spec_fun applications of the instantiated conclusion,
        # AND of any surviving invariant (2026-09-10, calcR/sum_up_to
        # shape): an invariant like `r == sum_up_to(i)` is an ANTECEDENT
        # of t_H (inv_arrows, above), not the conclusion, so `_call_asserts`
        # scanning `concl_asts` alone (task["ensures"], which only ever
        # mentions the PARAM `n`, never the loop-state var `i`) never
        # reaches it: `t_feed`'s own `assert (D : A) by t_dis` was left to
        # prove `r = (sf_r_v i)` from a bare `t_dis`, with no ground fact
        # to rewrite it to and no fuel-unfolding path a depth-6 t_go search
        # takes on an opaque Fixpoint application, MEASURED unproved on
        # both mieic...calcR and sumto_sol...SumUpTo. `env_py` already
        # carries the state var's own witness value here (the per-svar
        # loop just above this one), so widening the scanned asts to
        # `concl_asts + invariants` costs nothing when neither mentions a
        # spec_fun call (every committed task's own invariant, sum_upto's
        # own closed-form `2*r == i*(i+1)` included, has none), and gives
        # the surviving invariant the identical ground-and-rewrite
        # treatment the conclusion already had.
        lines = _call_asserts(cx, task, task["body"],
                              concl_asts + w.get("invariants", []),
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
    wit_before_feed = ""
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
    elif kind == "exit":
        # 2026-09-10, minArray shape: an "exit" witness's own SURVIVING
        # invariant can be an existential t_feed must discharge as an
        # ANTECEDENT (minArray's invariant #3, `exists x_v, 0 <= x_v <
        # i_v2 /\ r = a[x_v]`, kept when invariant #2, the forall, is the
        # one the twin ladder drops): the exact same "no candidate Z
        # variable" gap has_return's own note above names for a forall in
        # the GOAL, here for an exists in an ANTECEDENT instead --
        # `specialize`/`_glit` bakes every param and loop-state value into
        # a Z LITERAL, so t_go's built-in existential arm ("try 0, else
        # any bound `x : Z` already in context") has no non-zero
        # candidate to try and the antecedent goes unproved, MEASURED:
        # `t_feed`'s own `assert (D : A) by t_dis` swallows the failure
        # silently (`repeat lazymatch ... | ?A -> ?B => ...`  simply
        # never fires for that arrow), leaving t_H an un-stripped
        # implication and the closing `t_dis` call unprovable -- the same
        # symptom ("unsolved t verification condition") the calcR/
        # sum_up_to fix above closes for a different reason. `pose`ing
        # each `_forall_hints` witness, scanned over BOTH concl_asts and
        # the invariants (the antecedents here, unlike has_return's own
        # scan, which only widens to invariants for kind == "preservation"
        # where they ARE the goal), gives `t_go`'s exists-arm the missing
        # candidate; MEASURED that plain `t_go` (not `t_go_ext`) already
        # closes it once the candidate exists (a witness *value*, not a
        # forall-hypothesis *pairing*, is what was missing), so `closer`
        # stays `t_dis`, unescalated. The poses must land BEFORE
        # `t_feed t_H`, not after (has_return's own placement): they are
        # needed by `t_feed`'s OWN internal `t_dis` calls that prove each
        # antecedent, not only by the closing tactic after feeding is
        # done. Scoped to `kind == "exit"` and `not has_return` (the `if`
        # above already owns every `has_return` task, whatever its kind),
        # so a `preservation`-kind or return-bearing task's generated
        # proof text is completely unchanged, byte for byte.
        funs = interp.funs_of(task, task["body"])
        hints: list = []
        for e in concl_asts:
            _forall_hints(e, dict(env_py), funs, hints)
        for e in w.get("invariants", []):
            _forall_hints(e, dict(env_py), funs, hints)
        seen_h: set = set()
        for k, v in enumerate(hints):
            if v in seen_h:
                continue
            seen_h.add(v)
            wit_lines += f"  pose (t_wit{k} := ({_zlit(v)})%Z).\n"
        wit_before_feed, wit_lines = wit_lines, ""
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
            + "".join(lines) + "".join(sets)
            + wit_before_feed +
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
    if op == "slice":
        # SPEC.md "Sequences: literals, concatenation, slices (v1)":
        # s[a..b], DEFINED IFF 0 <= a <= b <= len(s), interp.ev's own
        # bound (matching `at`/`update`'s pattern above); `seq` (the
        # literal) and `+` (concatenation) carry no bound of their own
        # (interp.ev evaluates every argument unconditionally, left to
        # right, and returns), so they fall to the generic recursion
        # below, in that same order.
        s_e, lo_e, hi_e = e["args"]
        r = _first_undef(s_e, env, funs)
        if r is not None:
            return r
        r = _first_undef(lo_e, env, funs)
        if r is not None:
            return r
        r = _first_undef(hi_e, env, funs)
        if r is not None:
            return r
        s = interp.ev(s_e, env, funs, interp.St())
        lo = interp.ev(lo_e, env, funs, interp.St())
        hi = interp.ev(hi_e, env, funs, interp.St())
        if not (0 <= lo <= hi <= len(s)):
            return (f"~ (0 <= {_zlit(lo)} /\\ {_zlit(lo)} <= {_zlit(hi)} "
                    f"/\\ {_zlit(hi)} <= {_zlit(len(s))})")
        return None
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


def _real_ensures_undef_witness(task):
    """2026-09-12 (rocq, the four ensures-level probes): a local stand-in
    for harness.real_witness's own ensures-level case (ROADMAP 13.4's
    documented shape) when that change is not yet in this worktree.
    real_witness's second loop catches an Undef raised evaluating the
    REAL body itself; it does NOT catch one raised evaluating `ensures`
    afterward (fz_p_at_oob/_at_neg/_at_zero: the body is total, only the
    unguarded `at` in `ensures` is undefined at every input), so those
    three probes reach `lower()` with witness=None from both run_par.py
    and conformance.py's own no-twin path. This repeats real_witness's
    exact search (interp.domain over MAX_POINTS, `requires`-filtered,
    Undef/Budget/RecursionError skipped the same way) but adds the one
    missing step: after the real body runs to a value, evaluate each
    `ensures` clause and catch Undef there too. On a hit, returns the
    shape SPEC.md's ensures-level class carries: `_kind` "undefined" and
    `_real` "no value" as the body-level case already does, plus `_site`
    "ensures" (this file's own `_undef_cert`, below, dispatches on it)
    and `_expr`, the offending clause's own AST node, so `_undef_cert`
    can run `_first_undef` on THAT expression directly instead of
    walking the body (the body has nothing to find). No `_twin` key:
    there is no twin here, only the real disagreeing with its own
    contract. None when no such point exists in the scanned domain,
    which is every task outside this probe family -- t/test_real_witness.py
    style safety: a well-formed task's ensures is never undefined at a
    point its own real body reaches, so this returns None for all eight
    byte-identity tasks (measured, see this file's 2026-09-12 note near
    `lower`)."""
    names = interp._names(task)
    funs = interp.funs_of(task, task["body"])
    req = task.get("requires", [])
    ret = task["returns"][0]["name"]
    for env0 in interp.domain(task, names, interp.MAX_POINTS):
        st = interp.St()
        try:
            if not all(interp.ev(c, env0, funs, st) for c in req):
                continue
        except (interp.Undef, interp.Budget, RecursionError):
            continue
        env = dict(env0)
        env[ret] = None
        try:
            interp.exec_body(task["body"], env, funs, st)
        except (interp.Undef, interp.Budget, RecursionError):
            continue
        for e in task.get("ensures", []):
            try:
                interp.ev(e, env, funs, interp.St())
            except interp.Undef:
                w = interp._shown(env0)
                w.update(_kind="undefined", _real="no value",
                         _site="ensures", _expr=e)
                return w
            except (interp.Budget, RecursionError):
                continue
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
        # SPEC.md "Nested sequences (v1)": a nested param's witness is a
        # list of lists (interp.py's own JSON shape); tupling both levels
        # matches interp.py's own tuple-of-tuples convention for a
        # nested value, the same reason a plain seq witness is tupled
        # just below. swap_rows (the committed loop-free task carrying
        # this construct) is the case this line was written for: its
        # off-by-one twin's undefined witness is `_first_undef`'s own
        # "at"/"update" recursion (unchanged: it walks `interp.ev`'s own
        # left-to-right order and Python `len`, depth-agnostic already).
        if p["type"] == "seq":
            env_py[v] = tuple(witness[v])
        elif isinstance(p["type"], dict) and "seq" in p["type"]:
            env_py[v] = tuple(tuple(row) for row in witness[v])
        else:
            env_py[v] = witness[v]
    funs = interp.funs_of(task, body)
    if witness.get("_site") == "ensures":
        # 2026-09-12 (rocq, the four ensures-level probes): the offending
        # expression lives in `ensures`, not the body -- the body itself
        # is total (fz_p_at_oob/_at_neg/_at_zero all branch on `len(s)`
        # only), so `_first_undef_body`'s statement walk finds nothing to
        # report; it is not even called. Run the (well-defined) body to
        # get the same env `ensures` itself sees -- `_expr` is one of
        # `task["ensures"]`'s own clauses (`_real_ensures_undef_witness`,
        # above), so it can reference the return variable -- then hand
        # `_expr` straight to `_first_undef`, exactly the walk the
        # body-level case uses, just rooted at a different AST node.
        st = interp.St()
        try:
            interp.exec_body(body, env_py, funs, st)
        except Exception:                                     # noqa: BLE001
            return None
        expr = witness.get("_expr")
        if expr is None:
            return None
        fact = _first_undef(expr, env_py, funs)
        if fact is None:
            return None
        return (
            f"(* The REAL's own `ensures` is undefined at the measured "
            f"witness, {harness.witness(witness)}: no value. SPEC.md's "
            f"definedness rules make this a defect in the task's own "
            f"postcondition, never a totalized value to compare against a "
            f"twin (there is none here); this certifies that specific "
            f"bound's negation, at the concrete witness, by computation. *)\n"
            f"Theorem {CERT_NAME} :\n"
            f"  {fact}.\n"
            "Proof.\n"
            "  lia.\n"
            "Qed.\n")
    prefix, w, suffix = find_while(body)
    if w is not None:
        return None            # not needed by any committed task yet
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
        post_sf = POST_SF_NIA if _has_nonlinear_mul(task) else POST_SF
        parts = [header(task, body), emit_spec_funs(cx), post_sf + "\n", T_FEED, chunk,
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
    # NAMES (2026-09-11, ROADMAP 13.2): sanitize away any identifier that
    # collides with a Rocq reserved word, before `lower_v0`/`lower_v1`
    # ever see the task -- see names.py's module docstring. The rename
    # prefix is `tn_`, not the other six lowerings' `t_`: lower_rocq's
    # OWN `_ck` (RESERVED, above) already refuses any identifier starting
    # with `t_` outright, unconditionally, as that lowering's own
    # certificate/tactic namespace (`t_w_*`, `t_H`, `t_dis`, ...) -- a
    # `t_`-prefixed rename would collide with that same backstop the
    # moment `_ck` next saw it, exactly the failure this pass exists to
    # avoid. `task`/`body` are returned unchanged (`is`) when nothing
    # needs a rename, which is every previously-committed task.
    #
    # `_v0_cert`/`_try_cert_v1` (below `lower_v0`/`lower_v1`) read the
    # witness `w` against this SAME renamed task/body, `w`'s own keys
    # already renamed to match (`t_names.remap_witness`) -- both build
    # Coq LOCALS (`set`/`pose`) spelled after the witness's own keys, so,
    # exactly like lower_framac.py (see `remap_witness`'s own docstring,
    # MEASURED there), they need the renamed spelling, not the original
    # one. The certificate path is tried BEFORE `lower_v0`/`lower_v1`
    # (mirroring their own witness-first early return) rather than
    # through them: `lower_v0`/`lower_v1` are then called with
    # `witness=None` so they never redo that attempt.
    # ROCQ-3, 2026-09-12 (tetrahedralNumber, `t_v`): `_ck`'s own RESERVED
    # set and its `t_`/`sf_`-prefix, `_len`-suffix rule (this file's
    # certificate/tactic namespace, not Rocq's own keywords) are NOT the
    # same set `t_names.KEYWORDS["rocq"]` sanitizes against -- that list
    # is only the language's reserved words, so a task whose own return
    # is named `t_v` sailed past `t_names.sanitize` unrenamed and hit
    # `_ck`'s raise the moment `Ctx.__init__` ran. Folding the ACTUAL
    # declared names that would trip `_ck` (computed here, per task, the
    # same way `_ck` itself decides) into `sanitize`'s `reserved` set
    # gives them the identical rename `t_names.sanitize` already gives
    # every KEYWORDS collision (exact-match lookup: `sanitize` does not
    # care whether a name landed in `reserved` because it IS a keyword or
    # because it happens to match a name this file's harness computed),
    # so `_ck` sees only the renamed, `tn_`-prefixed spelling and never
    # raises for a user identifier again -- its raise is now reachable
    # only by an actual lowering-internal name collision, its original,
    # narrower purpose. MEASURED at the merge (2026-09-12): with the task
    # name excluded below, no committed task's binders start with
    # `t_`/`sf_` or end `_len` or hit RESERVED (test_names.py's 26-task
    # byte-identity check passes), so this pass renames nothing beyond
    # `t_v` and stays exactly the KEYWORDS-only pass for every one of them.
    ns_declared = t_names._declared_names(task, task.get("body", []))
    prefix_bad = {n for n in ns_declared
                  if n.startswith("t_") or n.startswith("sf_")
                  or n.endswith("_len") or n in RESERVED}
    # The task's own name is never passed through `_ck` (it names the
    # module, not a binder), so it must not be in this set: with it in,
    # the committed task row_max_len (its name ends in _len) was renamed
    # tn_row_max_len for no collision at all, breaking the names pass's
    # byte-identity contract for committed tasks (test_names.py, caught
    # at the merge, 2026-09-12).
    prefix_bad.discard(task.get("name"))
    twin_body = body if body is not task.get("body") else None
    task, renames = t_names.sanitize(
        task, t_names.KEYWORDS["rocq"] | prefix_bad,
        uppercase_ok=True, prefix="tn_")
    # the twin body renamed under the same mapping, kept a separate
    # object from task["body"] (2026-09-11, names.rename_body's note)
    body = t_names.rename_body(twin_body, renames) if twin_body is not None else task["body"]
    witness = t_names.remap_witness(witness, renames)
    rc = t_names.rename_comment(renames)
    if witness is not None:
        cert = (_v0_cert(task, body, witness)
               if task.get("t") == 0 else
               _try_cert_v1(task, body, witness))
        if cert is not None:
            return cert + (f"\n(* {rc} *)\n" if rc else "")
    # 2026-09-12 (rocq, the four ensures-level probes): a local stand-in
    # for harness.real_witness's own ensures-level case, tried on the real
    # side only (twin_body is None) and only once the ABOVE attempt has
    # come back empty -- see `_real_ensures_undef_witness`'s docstring on
    # why it must run even when the caller DID supply a witness: unmodified
    # harness.real_witness's own first loop (`ref._breaks_ensures`) already
    # catches the Undef raised evaluating `ensures` at fz_p_at_oob/_at_neg/
    # _at_zero's witness, but reports it as a "value"-kind witness with
    # `_ens` True and `_real`/`_twin` both the real's own (irrelevant, the
    # `ensures` never reads `r`) return value -- not the "undefined"/
    # "ensures"-site shape `_undef_cert` needs, so `_try_cert_v1` above
    # dispatches it to `_value_cert`, which has no totalized falsehood to
    # find (the totalized `at` makes the `==` trivially TRUE) and returns
    # None, `cert` stays None, and this is reached. Built from the
    # ALREADY-renamed `task`/`body` above, so no `t_names.remap_witness`
    # pass of its own. None for every other task (measured: all eight
    # byte-identity tasks below), so this changes nothing for them beyond
    # one extra, harmless domain scan.
    if twin_body is None:
        ew = _real_ensures_undef_witness(task)
        if ew is not None:
            cert = (_try_cert_v1(task, body, ew)
                    if task.get("t") != 0 else None)
            if cert is not None:
                return cert + (f"\n(* {rc} *)\n" if rc else "")
    src = (lower_v0(task, body, witness=None) if task.get("t") == 0 else
          lower_v1(task, body, witness=None))
    if rc:
        src += f"\n(* {rc} *)\n"
    return src


if __name__ == "__main__":
    raise SystemExit(harness.run_all(sys.argv[1:], lower, rocq_backend, "v"))
