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

  PRELUDE DELTA: 115 lines, all inserted immediately after
  `t_seq_eqb_case`'s own closing `]; t_bred_all.` (113 lines: the dated
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

  PRELUDE DELTA: 64 lines, all inserted immediately after
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
  confirms the ONLY changes reaching any of these six are the 64-line
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
  let E := fresh "Es" in
  destruct (Sumbool.sumbool_of_bool (t_seq_eqb n f g)) as [E|E];
  [ let F := fresh "Ef" in
    pose proof (proj1 (t_seq_eqb_spec n f g) E) as F;
    replace (t_seq_eqb n f g) with true in * by (symmetry; exact E)
  | let F := fresh "Ef" in
    assert (F : ~ (forall k : Z, 0 <= k < n -> f k = g k))
      by (intros Hc; apply (proj2 (t_seq_eqb_spec n f g)) in Hc; congruence);
    replace (t_seq_eqb n f g) with false in * by (symmetry; exact E)
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
  | H : context [t_app ?f ?g ?n ?k] |- _ => t_app_case f g n k
  | H : context [t_slice ?f ?a ?k] |- _ => rewrite (t_slice_get f a k) in H
  | H : context [t_seq_eqb ?n ?f ?g] |- _ => t_seq_eqb_case n f g
  | H : context [t_pair_eqb ?eqA ?eqB ?p ?q] |- _ => t_pair_eqb_case eqA eqB p q
  | H : context [t_nupd ?f ?i ?v ?k] |- _ => t_nupd_case f i v k
  | H : context [t_napp ?f ?g ?n ?k] |- _ => t_napp_case f g n k
  | H : context [t_nslice ?f ?a ?k] |- _ => rewrite (t_nslice_get f a k) in H
  | H : context [t_nseq_eqb ?n ?f ?g] |- _ => t_nseq_eqb_case n f g
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
        if op in ("-", "*", "neg", "len", "div", "mod"):
            return "int"
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
        raise NotImplementedError(
            f"rocq lowering: nested seq op {op!r} is refused (only var/"
            f"ite/update/seq/+/slice are built at the outer level; "
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
        (SPEC.md "Pairs (v1)": a component is "int", "bool" or "seq"; a
        seq component is a NAMED REFUSAL here, `pair_comp_ty`'s own
        comment, since it would need a second, incompatible seq encoding).
        Used only by `px`'s `pair` case, to render each of the two
        arguments to `{"op": "pair", ...}` per its OWN type."""
        t = self.ty(e, local)
        if isinstance(t, dict):
            return self.px(e, env, local)
        if t == "bool":
            return self.bx(e, env, local)
        if t == "seq":
            raise NotImplementedError(
                "rocq lowering: a pair component of type seq is refused "
                "(see pair_comp_ty)")
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
    Z/bool; a "seq" component is a NAMED REFUSAL, not a silent guess.
    SPEC.md's own rocq survey (the "Pairs (v1)" section, just before "The
    twins") already names this kernel's product `Z * Z`, one instance of
    the general rule stated there: "or a named refusal where the memory
    model or a seq component costs the certificate." A seq is TWO Coq
    slots here, not one (MODEL, above: the function+length pair), so it
    has no single Coq value a `T1 * T2` product could hold as one
    component without a second, incompatible seq encoding this file does
    not otherwise use; refusing it loudly here is cheaper and safer than
    inventing one for a shape no committed task needs."""
    if t == "int":
        return "Z"
    if t == "bool":
        return "bool"
    raise NotImplementedError(
        f"rocq lowering: a pair component of type {t!r} is refused "
        f"(SPEC.md's own rocq product is Z * Z; a seq component would "
        f"need a second seq encoding this file does not have)")


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


def header() -> str:
    return ("From Stdlib Require Import ZArith Bool Lia.\n"
            "Open Scope Z_scope.\n\n" + PRELUDE + "\n")


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
    if ret_t == "seq":
        # _value_cert (the only caller that uses this def_text) abstains on
        # a seq return outright; matched here so this never builds a
        # def_text no caller can use.
        return None
    pb, _ = param_binders(cx)
    local: dict = {}
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
    if ret_t == "seq" or (isinstance(ret_t, dict) and "seq" in ret_t):
        # A "value" witness kind's `_twin` is a single Python value
        # (`_glit`'s int/bool contract); a seq twin value is a tuple, which
        # would need the SAME two-slot (function, length) treatment the
        # real return already gets in gen_plain/gen_loop, plus a seq-
        # extensional `stmt`. No committed task needs it yet (swap's twin
        # is an "undefined" witness, `_undef_cert` below; reverse's is
        # "exit", `_loop_cert`; swap_rows', SPEC.md "Nested sequences
        # (v1)"'s own committed loop-free task, is ALSO "undefined"), so
        # this abstains rather than guessing, the SAME reason extended to
        # a nested return.
        return None
    got = _witness_env(task, witness)
    if got is None:
        return None
    env_py, env_txt, seq_defs, ptw, sets, _ = got
    tv = witness.get("_twin")
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
