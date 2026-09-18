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
  LOOPS      (any other arrangement of loops: a loop inside a loop, two
              or more loops in one body, or both -- 2026-09-18, ROADMAP
              WS-20 move 1): every loop becomes a function returning the
              TUPLE of the state variables its own body assigns, and its
              spec lemma says "the loop's own invariants in, the
              invariants AND the negated guard out, at that tuple". An
              enclosing body continues from the tuple's projections and
              gets the inner loop's effect only through that lemma,
              instantiated at the call site with its entry obligations
              discharged. See `lower_loops_general` below, which owns the
              whole path; the single-loop shape below is untouched by it.
  LOOP       (body contains one top-level while, and no other): the loop becomes a
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
NotImplementedError with the reason (a loop plus self-recursion, a loop
inside an `if` branch, a loop after or around an early `return` on the
nested/multiple-loop path, a nested loop with no invariant of its own,
quantifiers in computational position). A recorded absence, never a faked
proof. Nested and multiple loops were on that list until 2026-09-18 and
are not any more -- see "NESTED AND MULTIPLE LOOPS" below, and the shape
list `lower_loops_general`'s own section still names as open.

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

THE DECREASING-BY GAP (2026-09-09, second sweep). The lifted sweep
(COVERAGE-lifted-785.md rows added 2026-09-09) measured most loops that
update a seq reading lean unproved even though `update`/`fill` themselves
were already handled above: clover_replace, clover_double_array_elements
and absIt (reproduced first, `python3 -c "harness.run_task(...)"` against
`out/lifted-tasks/`) all read real UNPROVED, invariant-drop twin REFUTED.
Running `lean` by hand on the lowered file put the one error inside
`_t_loop_spec`'s own `decreasing_by all_goals (first | omega | grind)`
(clover_replace, line 76 of the generated file; the def `_t_loop`'s
OWN decreasing_by, two lines earlier, was fine). The obligation there is
the measure comparison for the theorem's self-application, e.g.
`((arr_out.set i_v2.toNat (-1)).length - (i_v2+1)).toNat < (arr_out.length
- i_v2).toNat`: `omega` alone cannot see through the `.set` at all (no
`List.length_set` in its theory, confirmed by isolating exactly this goal
in a scratch file and watching `omega` fail with the raw `List.set` term
still opaque in its counterexample); plain `grind` finds `List.length_set`
readily on the SMALL goal `_t_loop`'s own termination carries (no
invariants in scope there) but, handed the SAME goal inside
`_t_loop_spec` -- where the context also carries the loop's full
invariant list, every one of them a `forall` over `getElem!` -- grind's
E-matching explores that whole invariant set hunting for a path to
`List.length_set` and hits Lean's `maxRecDepth` before it gets there
(isolated and reproduced directly: `grind` alone, handed the same
five-invariant context by hand in a scratch file, hits the identical
"maximum recursion depth" issue that `_seq_hints`'s reads-after-`.set`
fix above was written for, but this is a different goal -- a pure length
fact, no element read in sight -- so widening the existing `grind only`
hint list was not the fix). What the goal actually needed was never a new
lemma, only skipping the search: `simp only [List.length_set,
List.length_replicate]; omega` closes it in one step, since that simp set
is exactly the fact `omega` was missing and nothing else.

The fix is `_dec()`, a decreasing_by tactic-text helper parallel to
`_gr()`, called at every `termination_by` site in the file in place of
the old literal `"decreasing_by all_goals (first | omega | grind)"`
string; it takes one extra `first`-alternative
(`simp only [List.length_set, List.length_replicate]; omega`) ONLY when
its caller passes `needed=True`. `lower_loop` computes that flag once,
`_dec_needs_seq_bridge`: true iff the loop's own `decreases` expression
names a state variable whose current symbolic value (from `sym()`) is
itself an `update`/`fill` term (checked textually for `.set ` /
`List.replicate ` in the value `sym()` already built, the same strings
`to_expr`/`term` emit for those two ops). This is why swap and reverse,
both already-committed seq tasks, do NOT regenerate byte-identical text
by accident but by construction: reverse's `decreases` is `len(s) - i`
and `s` is the read-only input, never assigned inside the loop (the
mutated return is `r`), so `_dec_needs_seq_bridge` reads False and
`_dec()` emits the exact old string; swap has no loop at all (SIMPLE
shape), so `_dec()` is never called for it. `spec_funs` and the
self-recursive (non-loop) shape keep calling `_dec()` with no argument
(False), unchanged, since no task lowered so far self-recurses through an
`update`/`fill`-carrying measure and there is nothing here to measure
that against; a future one would abstain into the same recursion-depth
wall this note describes, honestly, rather than silently.

MEASURED. The three reproduction tasks (clover_replace__replace,
clover_double_array_elements__double_array_elements,
seng2011_tmp_tmpgk5jq85q_p2__absIt) all move from real UNPROVED to real
VERIFIED (invariant-drop twin REFUTED on all three). abs.lean,
first_even.lean, reverse.lean and swap.lean, regenerated from the fifteen
committed tasks plus swap and reverse, diff byte-identical to before this
landed. Over all 198 out/lifted-tasks/*.json tasks under the lean
backend: before 97 verified/refuted, 33 unproved/refuted, 27
unproved/unproved, 24 abstain, 10 verified/unproved, 6 no-twin, 1
timeout/timeout; after 103 verified/refuted, 28 unproved/refuted, 26
unproved/unproved, the other four cells unchanged. Six tasks moved, all
upward, none downward: clover_double_array_elements__double_array_elements
and clover_replace__replace (unproved/refuted -> verified/refuted),
seng2011_tmp_tmpgk5jq85q_p2__absIt (unproved/refuted -> verified/refuted),
dafny_language_server_tmp_tmpkir0kenl_test_dafny1_cubes__cubes
(unproved/refuted -> verified/refuted),
final_project_dafny_tmp_tmpmcywuqox_attempts_exercise3_increment_array__incrementArray
(unproved/refuted -> verified/refuted), and
dafnyprograms_tmp_tmp74_f9k_c_invertarray__invertArray (unproved/unproved
-> verified/refuted); all five shared the identical decreasing_by defect
this note fixes. clover_rotate, dafny_synthesis_task_id_625__swapFirstAndLast,
clover_linear_search1__linearSearch,
dafny_tmp_tmpmvs2dmry_pancakesort_flip__flip and
seng2011_tmp_tmpgk5jq85q_ass1_ex8__getEven (the timeout) are UNCHANGED --
measured directly, none of their `decreases` expressions names a
`.set`/`.replicate`-carrying state variable, so `_dec_needs_seq_bridge`
correctly reads False for them and they fail elsewhere, honestly still
unproved, not silently patched over. The 17 committed tasks/*.json still
read exactly their AGREEMENT.md lean column (all verified/refuted), the
whole sweep finishing in seconds, nowhere near the 180 s wall. The
sequences-as-values fuzz family (fuzz_lower.py, family v1seqval, shapes
fillcopy/clampneg/reverse/idwrite, n=200 seed=1, 10 tasks matching those
four shapes in that corpus) reads IDENTICAL before and after this fix: 4
verified, 4 unproved, 2 timeout, 0 no-twin, byte-for-byte the same
per-task outcomes. Inspected directly (fz_v1seqval_002, fillcopy,
unproved/unproved both before and after): its one lean error is a
DIFFERENT goal, `_t_loop_spec`'s conclusion `fz_v1seqval_002_t_loop s r i
= s`, a whole-list structural equality that has to be bridged from the
pointwise invariant `forall k, r[k]! = s[k]!` -- no `.set`/`.replicate`
term anywhere in its own `decreases` (`len(s) - i`, s read-only, exactly
reverse's shape), so `_dec_needs_seq_bridge` correctly does not fire and
this file is untouched by the fix in this note; the pointwise-to-
structural list-equality bridge is a distinct, still-open gap, left
honestly unproved rather than folded into this fix's scope.

SEQUENCES: LITERALS, CONCATENATION, SLICES (2026-09-09, SPEC.md "Sequences:
literals, concatenation, slices (v1)", ROADMAP 12.7): three more Expr forms
on `List Int` values, the wave after "Sequences as values" landed the type
itself. `{"op": "seq", "args": [...]}` (`[e1, ..., en]`, n >= 0, `[]` the
empty seq) is a plain Lean list literal, `([e1, ..., en] : List Int)`, total
type ascription so the empty case elaborates. `{"op": "+", "args": [s, t]}`
on two seqs is `s ++ t`: `+` is polymorphic by operand type exactly as `==`
already is (two ints, two bools, two seqs), told apart in `sort()`/`term()`
by the first operand's own sort, computed recursively -- `sort()` gained
exactly this one branch, checked before the existing `ARITH_OPS` case so
int `+` is unaffected. `{"op": "slice", "args": [s, a, b]}` (`s[a..b]`) is
`(s.drop a.toNat).take (b - a).toNat`, per SPEC.md's own suggested encoding;
`List.extract` was measured against it and rejected -- on lean 4.33.1 it is
`@[reducible] def List.extract l start stop := (l.drop start).take (stop -
start)` verbatim, with no `length`/`getElem` lemmas of its own, so it would
buy nothing over `.drop`/`.take` directly and add an extra unfold. `at`'s
own convention (Int cast through `.toNat`) is reused throughout, so `at`,
`update`, `fill`, extensional `==` and the bounded quantifiers apply to a
literal/concatenation/slice exactly as to any other seq, with zero new
code: only `sort()`, `term()` and `dcond()` gained the three new op cases.

DEFINEDNESS. A literal is defined iff its elements are, a concatenation iff
both operands are ("always defined" beyond that) -- both fall straight
through `dcond()`'s existing generic per-argument case, no new code. A
slice costs one new obligation, `0 <= a <= b <= len(s)`, exactly parallel to
`at`'s `0 <= i < len`; `dcond()` gained one branch for `op == "slice"`,
emitted wherever `at`'s already is (a separate `_wf` theorem / program-point
obligation under SPEC.md's calculus, never folded into the total
`.drop`/`.take` computation itself, which -- like `at`'s `!` -- silently
totalizes out of range rather than being partial in Lean's sense).

LEMMAS. Measured on lean 4.33.1, core only, exactly the read-after-write
bridge "Sequences as values" needed for `.set`/`List.replicate`, now needed
again for `++`/`.take`/`.drop`: a READ after one of these, once the index
is the `.toNat`-cast Int this file's `at` convention uses, is past grind's
default e-matching reach the same way (measured directly on filter_pos's
own value-invariant preservation goal, the append idiom `r := r + [s[i]]`,
and on tail's own ensures, the slice `r := s[1..]`). Two more lemmas,
`t_seq_append_get` and `t_seq_slice_get`, hand-proved once (mirroring
`t_seq_update_get`/`t_seq_fill_get`: totalize via `getElem!_pos`, then
`List.getElem_append` / `List.getElem_take`+`List.getElem_drop`, `omega` on
the `.toNat` cast) and closed the same way, `grind only` (never plain
`grind`, for the identical reason: `only` is what stops the default-set
search that hits Lean's recursion-depth cap, not the lemmas alone --
confirmed by hand: `grind [t_seq_append_get]` on the append case still hit
the cap in a scratch probe, `grind only [t_seq_append_get, ...]` did not).
`List.length_append`/`List.length_take`/`List.length_drop` are already in
grind's own default simp set (measured, parallel to `length_set`/
`length_replicate`), but are named in `_seq_hints()` regardless, since
`grind only` drops the default set entirely and needs them named to use
them at all. `self.seq_mut` (update/fill) and the new `self.seq_new`
(literal/concat/slice, detected via `_has`/`_has_seq_plus` -- the latter
walks for a `+` node whose first operand's sort is `seq`, an
under-approximation for a `+` on a purely-local seq var not yet in
`self.types`, but every task that does that also carries a `seq`/`slice`
node somewhere else in the same tree, so nothing is missed in practice)
gate independently: `_seq_hints()`, `_gr()`, `_close()` fire on EITHER
flag; `emit_seq_helpers()` emits each pair of lemmas only under its own
flag; `_dec()`/`_dec_needs_seq_bridge()` extend the termination-bridge
`simp only` set with the append/take/drop length lemmas only when
`self.seq_new` actually matched (textually, ` ++ `/`.take (`/`.drop ` in
the state var's current symbolic value), so a task using update/fill alone
still gets exactly its prior two-name simp set, byte-identical, and vice
versa. Neither task measured here (tail, filter_pos) exercises this last
bridge: tail has no loop, and filter_pos's `decreases` (`len(s) - i`) never
names the mutated `r`, so `_dec_needs_seq_bridge` correctly reads False for
both, same as reverse's `s`-only measure before it.

A LATENT PARSER BUG, found by filter_pos's own certificate. `_enum()` (the
certificate's ground case-split over a quantifier's bounded range) built
`have {hv} : {disj} := by {tac}; rcases ...` with the nested `by` block
bare, not parenthesized. Every certificate bullet is itself wrapped in
`(...)` (`certificate()`'s `· tac` lines, `_prove`'s own parenthesized
returns), and inside such a paren-group Lean's tactic-sequence parser has
no indentation to delimit the `by` block, so it swallows every following
`;`-separated tactic INTO the `have`'s own proof term instead of
sequencing them after it: `first | omega | ...` alone already closes
`{disj}`, so the swallowed remainder (`rcases ...; subst ...; first |
decide | ...`) then runs against zero goals and vanishes silently, leaving
the certificate's actual target (the `intro`'d quantifier body) completely
untouched and the theorem UNPROVED with a context that looks superficially
fine (`_h3 : k = 0` present, goal still `... > 0`, no error hinting at the
real cause). Reproduced in isolation (a four-line scratch probe: identical
tactic text succeeds as separate lines, fails once wrapped in one `(...)`)
and confirmed to predate this construct as DEAD code, never live: no
`out/*.lean` committed before today contains `rcases _h` at all, so no
prior task's certificate ever exercised `_enum` with a following tactic to
swallow. filter_pos's own value invariant (`forall k, r[k] > 0`) is the
first one-element (`hi - lo == 1`) enumeration built inside a certificate,
which is exactly what exposed it. Fixed by parenthesizing the nested `by`
alone (`:= (by {tac})`), a one-token change with no other effect on the
generated proof; `grep -rl "rcases _h" out/*.lean` before the fix returns
nothing, so this is proven dead for every task lowered before today, and
swap/reverse (both real and twin) are diffed byte-identical against their
committed `out/` copies after the fix, confirming it changed nothing they
depend on.

MEASURED (`tasks/tail.json`, `tasks/filter_pos.json`, plus swap and reverse
for regression, via `harness.run_task` against the lean backend, matching
this note's own reproduction command): tail COUNTS (real VERIFIED,
off-by-one twin REFUTED, witness s=[0] -> real [], twin slice bounds
[2..1] outside 0 <= a <= b <= 1 -- the off-by-one rung reaches the slice's
own upper bound, exactly SPEC.md's prediction, and the certificate is the
"undefined witness" kind, `_cert_undefined`, unmodified by this note since
it was already generic over `to_expr`'s obligations). filter_pos COUNTS
(real VERIFIED, invariant-drop#1 twin REFUTED, witness exit at s=[], i=1,
r=[1] -- dropping `i <= len(s)` lets the exit state run past the array,
`_cert_loop`'s existing "exit" kind, also unmodified). swap and reverse
UNCHANGED: both real and twin sources diffed byte-identical (`cmp`) against
`out/swap.lean`, `out/reverse.lean`, `out/swap_twin.lean`,
`out/reverse_twin.lean`. The other 15 pre-existing committed tasks
(`tasks/*.json` minus swap/reverse/tail/filter_pos) were swept too as a
regression check, all 19 COUNT with no exceptions, and abs/first_even/
digit_sum/is_prime/seq_max/sum_upto/linear_search/gcd/fib/factorial/max/
remainder/all_nonneg/contains/count_matches (every pre-existing task with
a committed `out/*.lean`) diffed byte-identical too -- `self.seq_new` reads
False for every one of them (none touches `seq`/`slice`/seq-`+`), so
nothing about their tactic scripts or termination bridges changed.

THE SEQ-LOOP RESIDUAL (2026-09-09, fourth sweep). The five lifted tasks
COVERAGE-lifted-785.md names as this column's own residual --
clover_rotate__rotate, dafny_synthesis_task_id_625__swapFirstAndLast,
clover_linear_search1__linearSearch,
dafny_tmp_tmpmvs2dmry_pancakesort_flip__flip and
seng2011_tmp_tmpgk5jq85q_ass1_ex8__getEven -- were lowered and run
individually (`harness.run_task` against `out/lifted-tasks/`, real and
twin, into `out/agent-lean-seqloops/`). One closed outright; the other
four's actual open goals turn out to be three distinct, genuine gaps, not
one, and only the first was closable within this sweep.

CLOSED: clover_rotate__rotate. Two separate defects, both found by
lowering it, neither previously measured (COVERAGE-lifted-785.md's own
"unproved/refuted" row predates the "Sequences: literals, concatenation,
slices (v1)" wave landing the same day):
  crash    lowering rotate at all raised `KeyError: 'i'` inside `sort()`,
           from `emit_clause_wfs`'s `_close` -> `divmod_pairs`'s raw-AST
           `walk`, which does not use `prop()`/`dcond()`'s own recursion
           and so never binds a `forall`'s own variable into `types`
           before recursing into its body; rotate's own ensures, `b[i] ==
           a[(i+offset) mod len(a)]`, is the first task lowered whose
           `mod` sits inside a `forall` AND has a `+` as its numerator
           (`sort()`'s new "+" case, added for seq-`+`, looks up
           `types[e["var"]]` unconditionally). Fixed by making `walk`
           return immediately on a `forall`/`exists` node: `env`/`types`
           there are the OUTER clause's, so the bound variable has no
           entry regardless, and even given one, a `have` built from it
           would sit before any `intro` of the quantifier in the tactic
           script `divmod_pairs` feeds -- unsound to hoist regardless of
           whether it crashes. Dead code for every task lowered before
           today (no committed task combines `mod` and a `forall`-bound
           `+`), confirmed by the regression below.
  unclosed goal  with the crash gone, three WF theorems (the ensures
           forall itself, its lone loop invariant, and the loop body's
           own per-step `at`/`mod` obligation) still failed: `grind`
           alone cannot derive the bound `0 <= (i+offset) mod len(a) <
           len(a)` (needing `len(a) ≠ 0`, itself only derivable from the
           SAME forall's own `0 <= i < len(a)` binder, or in the loop
           body's case from `hinv2`/the guard, both later in the SAME
           theorem's own hypothesis chain), and the existing div/mod
           bridge (`divmod_pairs`/`divmod_prelude`, "Division and modulo",
           2026-09-08) is a `have` sequence built to run BEFORE any
           `intro` -- sound only when the divisor's nonzero side
           condition needs nothing but the theorem's own parameters,
           never anything still sitting behind a `->` or a `forall` in
           the goal itself. Two new, general mechanisms, both added to
           `_close` (used by `emit_clause_wfs`/`spec_funs`/`lower_rec`)
           and, newly, to `_gr` (used by every loop invariant/guard/
           decreases/body WF theorem via a `nodes` argument every
           pre-existing call site still omits):
             quantified   `_quant_pairs` walks a clause looking for a
                          bare top-level `forall` (descending through
                          `and`, needed below) whose body reaches a
                          div/mod op, and builds its bridge under a FIXED
                          local name (`_qz0`, `_qzlo0`, `_qzhi0`) for the
                          bound variable and its two range facts --
                          `intro` does not care what display name the
                          goal's own binder carries (`self.fresh`'s
                          counter need not be reproduced), so this works
                          regardless of what name `dcond`'s own statement
                          used.
             chained      neither call site threads the count of leading
                          `requires`/earlier-clause/invariant hypotheses
                          through to here, so both the quantified bridge
                          and the free-standing one are tried under a
                          GUESSED leading `intro` chain, 0..MAX_LEAD (8)
                          throwaway names, one candidate per guess (all
                          folded into one `_divmod_branches` helper). A
                          wrong guess either leaves a `have` unable to
                          typecheck against a still arrow-headed goal, or
                          `intro` runs out of binders outright -- both
                          are ordinary tactic failures `first` falls
                          through on, never a wrong proof.
           The chained repeats (nlead > 0) of the free-standing bridge
           are gated behind `self.seq_mut or self.seq_new` (measured:
           UNGATED, they changed digit_sum's and remainder's tactic text
           without changing either verdict -- both already close at
           nlead=0, a literal divisor's nonzero-ness needing nothing from
           the chain -- so gating was needed to hold this sweep's own
           byte-identical bar). The quantified bridge itself is NOT
           gated: it is a correctness fix, not an optional extra, needed
           in any column with a div/mod inside a forall, seq task or not
           -- and leaving it gated would have meant reproducing a bug
           already latent in the committed `first_even.lean`/
           `is_prime.lean` (below) rather than finishing the fix.
  MEASURED. `clover_rotate__rotate` COUNTS: real VERIFIED, invariant-drop
           twin REFUTED, witness exit at a=[], offset=0, i_v=0, b=[0].
  A LATENT BUG, found by the regression, not by rotate. The pre-fix
  `divmod_pairs` walk's silent skip into a `forall` (see "crash" above)
  meant `first_even_t_wf2`/`wf3` and `is_prime`'s equivalent, both
  committed under the 2026-09-08 "Division and modulo" wave, already
  carried a `have` citing `s[(i).toNat]!` -- a bare `i`, which NEITHER
  theorem's own parameter list nor its `forall`'s own (correctly fresh)
  binder name (`i_1`, `i_3`, ...) ever introduces. Dead since the day it
  landed: `grind` alone, tried first in the same `first | ... | ...`,
  already closes both goals, so the broken second alternative was never
  elaborated far enough to error. This sweep's quantified bridge
  replaces that dead branch with a working one (the same `_qz`-named
  `intro`, ungated as above), so `first_even.lean`/`is_prime.lean` (and
  their twins) are the only pre-existing committed files that do NOT
  diff byte-identical any more -- the diff is confined to each file's
  trailing, still-unreached alternative, both files still COUNT.

NOT CLOSED, three distinct genuine gaps -- named per the residual's own
allowance, none forced.

  dafny_tmp_tmpmvs2dmry_pancakesort_flip__flip and (independently)
  clover_linear_search1__linearSearch share ONE gap, not a lemma but a
  hole in `lower_loop`'s own architecture: `_t_loop`'s bare recursive
  definition carries NO invariant -- only the immediate guard hypothesis
  (`_hg`) is in scope at its own `decreasing_by`, unlike `_t_loop_spec`,
  which binds the full invariant list as explicit hypotheses. Every
  previously-lowered loop's `decreases` measure happens to be provably
  monotone from the guard ALONE (reverse/tail/filter_pos/rotate/getEven:
  guard is `i < len(...)`, decreases is exactly `len(...) - i`, so the
  guard directly bounds the one step that matters). flip's guard is `i <
  j` but `decreases` is bare `j`; linear_search's guard is `n ≠ len(a)`
  (an equality test, not an order) and `decreases` is the absolute-value
  `if n <= len(a) then len(a) - n else n - len(a)`. Both measures
  genuinely INCREASE once the state leaves the region the loop's own
  (invariant-only) `j >= num/2 >= 0` / `n <= len(a)` keeps it inside --
  confirmed by isolating each `decreasing_by` goal in a scratch file:
  `omega` reports a live counterexample rather than closing, and for
  linear_search's own goal a ground instantiation (n=10, a_len=5) makes
  the inequality false by direct computation. This is not an automation
  gap `omega`/`grind` are merely failing to search hard enough for -- the
  obligation as posed is false, and no tactic can close a false goal
  honestly. Closing it for real needs `_t_loop` to carry a domain
  restriction (a proof-carrying hypothesis threaded through every
  recursive call and re-established at each step, the same shape
  `requires` already gets in the RECURSIVE shape) -- a change to
  `_t_loop`'s own signature reaching `_t`, `_t_loop_spec`'s applied
  terms and `_cert_loop`'s certificate construction alike, far past a
  bridge lemma or a hint set, and too wide a blast radius to gate safely
  in the time this sweep had; left honestly unproved rather than forced.
  Exact failing goal (flip, `_t_loop`'s own `decreasing_by`, `omega`):
  hypotheses `_hg : i < j`, `h : j.toNat ≤ (j + -1).toNat`, `h_1 : j ≤ 0`,
  goal `False` -- `omega` reports this as satisfiable, i.e. the measure
  does not decrease when `j ≤ 0`, a state the guard alone never excludes.

  dafny_synthesis_task_id_625__swapFirstAndLast (a SIMPLE, loop-free
  shape: `a_out := a; tmp := a_out[0]; a_out := a_out[0 := a_out[len-1]];
  a_out := a_out[len-1 := tmp]`, two SEQUENTIAL updates to the same
  variable) needs a read after BOTH updates bridged in one hop past
  `.toNat`: `_t_spec`'s own goal, after `unfold`, is (in full) `r2[0]! =
  a[len(r2)-1]!` where `r2 = r1.set (len r1 - 1) a[0]!` and `r1 = a.set 0
  a[len a - 1]!` -- composing `t_seq_update_get` TWICE (once through
  each `.set`, case-splitting on whether `0 = len(r1) - 1` decides
  whether the read lands on the second write or must fall through to the
  first). Measured directly: `grind only [t_seq_update_get,
  List.length_set]`, plain `grind [t_seq_update_get, List.length_set]`
  (no `only`), and `simp only [t_seq_update_get, List.length_set] <;>
  omega` (simp reports `t_seq_update_get` UNUSED, never firing at all)
  all fail on the same residual goal. `t_seq_update_get` bridges exactly
  one `.set`; nothing in this file composes it across two nested ones
  automatically, and no second lemma for that composition exists yet.
  Left unproved rather than hand-rolling a one-task lemma.

  seng2011_tmp_tmpgk5jq85q_ass1_ex8__getEven times out (the exact
  behaviour COVERAGE-lifted-785.md recorded) inside `_t_loop_spec` itself
  -- `(deterministic) timeout at isDefEq`/`whnf`, 200000 heartbeats,
  never reaching a `grind failed` report at all. Its invariant combines
  an `if`-guarded seq write with a `mod`-inside-`forall` value invariant
  (`a_out[j] % 2 = 0` for `j < i_v`), so the preservation step needs the
  seq read-after-write bridge AND a mod fact AND the `if`'s own branch
  split simultaneously; this is the same class of recursion-depth/
  E-matching blowup "THE DECREASING-BY GAP" and "SEQUENCES AS VALUES"
  above were written for, but on a goal neither `_seq_hints` nor this
  sweep's own div/mod bridges are shaped to reach in time, not a missing
  lemma name. Left honestly at timeout.

REGRESSION. Every task in `tasks/*.json` (19: the 15 pre-existing plus
swap/reverse/tail/filter_pos) was swept through `harness.run_all` against
the lean backend: all 19 still COUNT, identically to before this sweep.
`cmp` against the committed `out/*.lean` (real and twin): 15 of 19 byte-
identical; `first_even`/`is_prime` differ only in the dead-branch fix
above (verdicts unchanged); `digit_sum`/`remainder` byte-identical (the
chained-bridge gate holds). `clover_rotate__rotate` is the only one of
the five residual tasks that moved cells, unproved/refuted ->
verified/refuted; the other four's cells are unchanged from
COVERAGE-lifted-785.md (unproved/unproved for linear_search and flip,
unproved/refuted for swapFirstAndLast, timeout/timeout for getEven).

PAIRS (2026-09-10, SPEC.md "Pairs (v1)", ROADMAP 12.7): a pair `{"pair":
[T1, T2]}`, T1/T2 each `int`/`bool`/`seq`, lands as a value over Int, Bool
and List Int, the whole of v1 (no pair of pairs, no seq of pairs, no pair
of three -- fuzz_lower.check_wf refuses those before this file ever sees
a task, so nothing about the shape below needs to police them itself).
Two committed tasks: `divmod_pair` (loop-free, twin `wrong-var`, the
components swapped) and `min_max` (a loop keeping `lo`/`hi` as two plain
ints and assembling `(lo, hi)` only in the suffix, twin `collapse-if`).

ENCODING. `{"pair": [T1, T2]}` -> Lean's own product `T1 × T2`
(`lean_type` gained one branch, recursing once since T1/T2 are always
base types); `pair` -> `(a, b)`, Lean's own pair constructor; `fst`/`snd`
-> `.1`/`.2`, Prod.fst/Prod.snd (`sort`/`term` each gained the three new
op cases, mirroring `sort`'s/`term`'s existing `seq`/`slice` additions).
`==`/`!=` on two pairs needed ZERO new code: `prop`'s existing non-bool
branch already lowers any `==`/`!=` whose operands aren't `bool`-sorted
to Lean's own `=`/`≠` term equality, and a pair's `sort` (the new
`{"pair": [...]}` dict) is simply never `"bool"`, so it falls straight
through unchanged, exactly as seq equality did (SPEC.md "Sequences as
values"). Measured (lean 4.33.1, core only, no Mathlib, a six-theorem
scratch probe): `decide` alone proves `Int × Int` equality and
disequality, `Int × List Int` equality and disequality (the List Int
component case SPEC.md names explicitly), `Bool × Int` equality, and
each projection separately (`(a, b).1 = a`, `(a, b).2 = b`) by `rfl`
(the conjunction of the two needs `constructor <;> rfl`, not bare
`rfl`) -- core Lean's `Prod` already
derives `DecidableEq` from its two components', so nothing needed
supplying by hand. `dcond` ALSO needed zero new code: `pair`'s only
definedness obligation is that both components are defined, and
`dcond`'s existing generic per-argument fallback (the one strict-op
catch-all at the bottom, already used by `not`/`neg`/arithmetic/`==`)
computes exactly that by conjoining `dcond` of the two operands; `fst`/
`snd` are "always defined on a pair" per SPEC.md, which is exactly what
the SAME fallback gives by conjoining `dcond` of their one operand (the
pair expression), recursing into ITS OWN generic conjunction -- no
special-casing needed for the projections either. `_loop_zero` (loop
state placeholder, below) and the certificate's `_gterm`/`_unshow`
(ground-value forms, below) are the only genuinely new logic this
construct needed.

THE LOOP STATE PLACEHOLDER. `min_max`'s `r` is never assigned before its
loop (only `lo`/`hi`/`i` are; `r := (lo, hi)` happens in the suffix), so
`lower_loop`'s existing "unassigned state var" path needs a placeholder
value to seed the recursion (SPEC.md "Early exit", 2026-09-08, is where
this path was built; nothing depends on the placeholder's actual value,
per that section's own note, and this measurement confirms it: `r`'s
frame hypothesis `hfr1 : r = placeholder` is carried but never read by
anything the loop's own definition computes). The old code picked the
placeholder with `{"int": ..., "bool": ...}.get(self.rett)`; `self.rett`
being the pair's OWN dict (`{"pair": [...]}, unhashable) would have
raised `TypeError` on that `.get`, a hard crash, the first time any task
gave a loop's return a pair type. Replaced with `_loop_zero`, a small
recursive helper: a pair placeholder is built one component at a time
(`((0 : Int), (0 : Int))` for `min_max`); a bare `seq` return still has
no placeholder (unchanged from before this construct: dead in every
committed task, `reverse` and `filter_pos` both assign `r` in their own
prefix) and stays an honest `NotImplementedError` if ever hit.

TWO GENUINE LEAN DEFECTS, both found by actually running `min_max`/
`divmod_pair` and both fixed generically (derived from body/return
shape, never tuned per task), neither one a "pairs" defect at bottom:

  `unfold` vs. a raw projection. `divmod_pair_t_spec`'s proof was
  `unfold divmod_pair_t; <the div/mod bridge>; omega`: `unfold` performs
  only delta-reduction of `divmod_pair_t` itself, leaving `(x / y, x %
  y).fst` in the goal as a projection `omega` treats as an OPAQUE atom
  distinct from `x / y` (measured directly: a four-line scratch probe,
  `unfold` alone leaves `omega` citing exactly that atom split as its
  counterexample; `unfold ...; dsimp only` or `simp only [name]` both
  close it, either one performing the iota-reduction `unfold` itself
  does not). Fixed by adding one `dsimp only` line after `unfold
  {name}_t` in the SIMPLE shape's spec theorem, ADDED ONLY when the
  return type is a pair (`isinstance(self.rett, dict)`): no other return
  type has a bare projection to reduce, so no other task's tactic text
  changes.

  `repeat split` never revisits a sibling branch. `min_max`'s loop body
  has TWO top-level `if`s (the `lo` update and the `hi` update, the
  coupled-bounds shape SPEC.md's own measurement calls out); `repeat
  split` on the resulting goal chases the FIRST `if`'s TRUE branch all
  the way down (splitting the SECOND `if` there too) but never comes
  back to split the second `if` inside the first `if`'s FALSE branch --
  `repeat tac` iterates one tactic on the CURRENT main goal only, so once
  `split` opens two goals it keeps re-splitting the newer one and drops
  the other with an `if` still unresolved inside it. Reproduced in
  isolation (a four-line scratch probe, a 3-conjunct goal fed by two
  sequential `if`s: `repeat split` yields 3 cases, one of them still
  carrying a bare `if`; `repeat (all_goals split)` yields the correct 4).
  Fixed by using `repeat (all_goals split)` in the loop's own
  `_loop_spec` theorem ONLY when its loop body has two or more top-level
  `if`s (a body-shape rule, not a pairs-specific one: swept every
  committed task, `min_max` is the only one with two); every task with
  zero or one keeps the exact prior `repeat split` text, byte-identical.
  Neither fix added a `have ... := by` nested inside a parenthesized
  tactic sequence (the 2026-09-09 "LATENT PARSER BUG" above), so neither
  reopens that defect.

THE CERTIFICATE. A twin's witness carries a pair value two ways:
`interp.py`'s `_j` shows a `Pair` as the plain list `[a, b]` (JSON has no
pair type), which reaches this file as `w["_twin"]` (`_cert_value`, the
kind `min_max`'s and `divmod_pair`'s own twins both measure) or as a
named state entry (`_cert_loop`, unexercised by either measured twin but
wired the same way). Two new small methods, used together everywhere a
witness value crosses into the certificate: `_gterm` gained a pair
branch building the ground LEAN TERM `(a, b)` recursively (the same
shape `term`'s own `"pair"` case uses); `_unshow` inverts `_j`'s
rendering back into a real `interp.Pair` for every venv entry the
certificate feeds to `interp.ev` (`_cev`/`_prove`/`_refute`) -- WITHOUT
it, a raw `[a, b]` list surviving into a venv crashes the first `fst`/
`snd` `interp.ev` reaches on it (`Pair.a`/`Pair.b` are attributes, not
list indices; a frozen dataclass on purpose, interp.py's own note, kept
OUT of Python's tuple so a pair can never be mistaken for a same-shaped
seq), an uncaught `AttributeError` neither `_cev` nor `certificate`'s
`except` list catches -- a hard crash, not an abstain. `_unshow` is
applied to every params/state venv in `_cert_undefined`, `_cert_value`
and `_cert_loop`, so a pair PARAMETER or a pair LOOP LOCAL is handled the
same way as the pair RETURN, though neither is exercised by either
measured task (both pairs here are return-only): built for the shape
SPEC.md describes, honestly unmeasured beyond that.

NO NEW NAMED REFUSAL. Lean's own product type has no restriction this
construct needs to work around (a pair of pairs would lower fine if one
ever reached this file); the v1 boundary (no pair of pairs, no seq of
pairs, no pair of three) is enforced upstream by fuzz_lower.check_wf, not
by anything added here.

MEASURED (`tasks/divmod_pair.json`, `tasks/min_max.json`, via
`harness.run_task` against the lean backend, `harness.OUT` redirected to
`out/agent-lean-pairs/`, matching this note's own reproduction commands):
divmod_pair COUNTS (real VERIFIED, `wrong-var` twin REFUTED, witness
x=1, y=1 -> real [1, 0], twin [0, 1], breaking `r.1 < y`). min_max COUNTS
(real VERIFIED, `collapse-if` twin REFUTED, witness s=[0, 1] -> real
[0, 1], twin [1, 1], breaking `r.0 <= s[k]` at k=0) -- both exactly the
witnesses SPEC.md's own text names. abs/swap/reverse/tail/filter_pos
(the five tasks the sequence-trio/bridge-lemma waves above measured)
were regenerated into the same directory and diffed (`cmp`) against the
committed `out/<name>.lean`: all ten files (real and twin) BYTE-
IDENTICAL, so this construct changes nothing about a task that doesn't
use it. A wider sweep of all 21 committed `tasks/*.json` also still
COUNTS uniformly; two of them (`first_even`, `is_prime`) reproduce the
already-documented `out/*.lean` staleness this file's own "REGRESSION"
note above named (a pre-2026-09-10 dead-branch-fix text difference,
verdicts unchanged) -- pre-existing, unrelated to pairs, confirmed by
inspection: `first_even.lean`/`is_prime.lean`'s wf-theorem `have`s in the
COMMITTED copies still cite the un-renamed quantifier bound variable
`_quant_pairs` was written to fix.

PAIRS, SPEC POSITION (2026-09-10): the PAIRS note above measured only
return-position and computational-position pair use (divmod_pair,
min_max); the fuzz family `v1pairs` (31 tasks: 26 instances plus 5
probes) found the gap that measurement missed: `prop()`, the spec (Prop-
level) lowering used for `requires`/`ensures`/invariants, had a `term()`
case for `fst`/`snd` (the ENCODING section above) but no `prop()` case,
so a BOOL-sorted pair component reaching `prop()` directly, either as a
whole ensures/requires/invariant clause or as an operand of `==`/`!=`/
`implies`/`and`/`or`/`ite` whose `sort()` came back "bool", fell through
to the bottom `raise NotImplementedError` with "operator 'fst' in spec
position is not lowered for lean": 7 of the 9 `v1pairs` residual tasks
(fz_v1pairs_060/142/357/425/433/768/773), each a "does an element with
property P exist, and if so what's its value" loop returning
`{"pair": ["bool", "int"]}`, whose `fst` names the found-flag checked
directly against a bounded `exists` in `ensures`.

FIX: one new case in `prop()`, `op in ("fst", "snd")`, mirroring the
`call`/`var` cases just above it: a bool-sorted `fst`/`snd` names a
computed value, not a formula, so it gets the same generic `(term =
true)` bridge, calling the EXISTING `term()` case (no new term-level
code). Guarded by an assertion that the projection's own `sort()` is
actually "bool" (the same shape the `var` case's assertion already
checks), so a non-bool `fst`/`snd` reaching `prop()` some other way
still fails loudly rather than emitting nonsense. `pair` itself needs no
matching case: `pair`'s own sort is always the `{"pair": [...]}` dict,
never the string "bool" (T1/T2 are base types, SPEC.md v1), so a raw
`pair` node can never be the direct subject of a Prop; it only ever
reaches `prop()` as an operand of `==`/`!=`, already routed through
`term()` before this function is asked to render it as a formula
(unchanged by this fix).

MEASURED (`python3 fuzz_lower.py --only lean` restricted to the 9
`v1pairs` residual task names, `--n 400 --seed 1 --jobs 8 --flake 3`):
6 of the 7 `fst`-in-spec-position abstains now read real VERIFIED / twin
REFUTED (fz_v1pairs_060, 142, 357, 425, 433, 768). One,
fz_v1pairs_773, no longer abstains but the twin proof times out (real
VERIFIED, twin timeout, flake-checked 3x, consistently ~29s): the fix
lowers it, the kernel just doesn't close it fast enough; a separate,
newly-exposed residual (proof-search cost, not a lowering gap), left
unfixed as out of scope for this pass. The remaining 2 of 9
(fz_v1pairs_053, fz_p_pair_eq) are the pre-existing computational-bool
gaps ("boolean operator '==' / 'and' in computational position is not
lowered for lean": `term()` never grew Bool-term cases for `==`/`!=`/
CMP_OPS/`not`/`and`/`or`/`implies`, only Prop-term cases in `prop()`,
because assigning a bool EXPRESSION to a bool VARIABLE in the body needs
a decidable-Prop-to-Bool bridge, e.g. `decide (a = b) : Bool`, for every
one of those operators, not one line, and unrelated to pairs: both
tasks hit it on plain int/pair equality assigned to a bool local,
nothing pair-specific about the gap itself); left exactly as they were,
confirmed by reading `term()` that no one-line fix exists (it would mean
adding a parallel Bool-producing rendering path alongside `prop()`'s
Prop-producing one, for every boolean operator, which is the "Booleans
as computational values" construct SPEC.md doesn't have yet). Net over
the 9: 0 of 9 counted before this fix, 6 of 9 count after; over the
full `v1pairs` family: 22 of 31 before, 28 of 31 after. Regenerated the
seven committed pair-adjacent tasks (`divmod_pair`, `min_max`, `abs`,
`swap`, `reverse`, `tail`, `filter_pos`) through `harness.run_task`
(`harness.OUT` redirected to `out/agent-lean-pairs2/`) and diffed
(`cmp`) both real and twin `.lean` against the committed `out/*.lean`:
all fourteen files byte-identical, and all seven still COUNT exactly as
in AGREEMENT.md; this fix touches nothing about a task that doesn't put
a bool-sorted `fst`/`snd` directly into spec position.

NESTED SEQUENCES (2026-09-10, SPEC.md "Nested sequences (v1)", ROADMAP
12.7): `{"seq": "seq"}`, a seq of seqs of ints, one level, written
`seq<seq>` -- no new Expr form, every existing seq operator (literal,
`len`, `at`, `+`, `slice`, `update`, `fill`, `==`) polymorphic by its
operands' STATIC TYPE, exactly as `+`/`==` already were before this.
Two committed tasks: `swap_rows` (loop-free, twin `off-by-one`) and
`row_max_len` (a loop over row lengths, twin an invariant drop, the
`seq_max` shape lifted one level).

ENCODING. `{"seq": "seq"}` -> `List (List Int)` (`lean_type` gained one
branch, guarded by `"pair" in t` first so a pair's own dict is not
mistaken for a nested seq's, both being plain dicts now). Every operator
that used to be told apart only by AST op (`update`/`fill`/`seq`/`slice`
all unconditionally returned the string "seq") now recurses through
`sort()` to tell a nested container from a flat one, mirroring how `+`
already distinguished int-`+` from seq-`+` by its first operand's sort:
  `at`      `s[i]` is a row ("seq") when `s` is nested, an int when `s`
            is flat -- `sort()`'s own new branch. `s[i][j]` (the
            notation's chained postfix) needed NO new Expr form: it is
            `at(at(s, i), j)`, the outer `at`'s operand being the inner
            `at`'s "seq"-sorted result, so the outer call's own sort
            comes back "int" for free, and `term()` needed no change at
            all -- `s[i.toNat]!` already produces a `List Int` element
            when `s : List (List Int)`, the identical Lean syntax either
            way, since `List.getElem!` is generic in the element type to
            begin with.
  `update`/ return the SAME container type as their first argument
  `slice`   (a row replaced by a row is still a matrix; a slice of rows
            is still a matrix) -- one `sort()` branch, shared, since both
            already relayed their first argument's type once written
            this way. `term()` needed no change: `.set`/`.drop`/`.take`
            are all generic in the element type already.
  `fill`    `n` copies of the SECOND argument: nested iff the copied
            value is itself a seq, symmetric with the literal case next.
  `seq`     the literal `[e1, ..., en]`: nested iff its own elements are.
            An empty literal `[]` has no element to inspect -- SPEC.md's
            own "the declared type says so" needs a context this
            bottom-up `sort()`/`term()` do not carry, so an empty literal
            defaults to flat `List Int`, exactly the pre-nested
            behaviour and observationally unchanged for every task that
            predates this construct; neither committed nested task uses
            this op at all, empty or not, so the default is unexercised
            by them. `term()`'s ascription now reads the same nested-or-
            not decision off `sort()` (`List (List Int)` vs `List Int`).
  `+`       already polymorphic (SEQUENCES: LITERALS... above); the
            check that used to compare `== "seq"` now uses a new helper,
            `_is_seqsort` (`s == "seq" or (isinstance(s, dict) and "seq"
            in s)`), so a nested-seq sort (a dict) is recognized as
            seq-like too instead of falling into the int branch. `++`
            needed no term-level change: `List.append` is generic.
  `==`/`!=` needed ZERO new code, the same free ride pairs got: a nested
            seq's sort is a dict that is never "bool", so `prop()`'s
            existing non-bool branch already sends it to Lean's own `=`/
            `≠`, and `List`'s `DecidableEq` derives from its element's
            (also `List`'s own, recursively) with nothing to write by
            hand. Measured (lean 4.33.1, core only, no Mathlib, a two-
            theorem scratch probe): `decide` alone proves
            `([[1,2],[3]] : List (List Int)) = [[1,2],[3]]` and
            `[[1,2]] ≠ [[1,2,3]]`.

TWO GUARDED BRANCHES, both pre-existing code that assumed `isinstance(t,
dict)` meant "pair" (true until this construct, since a nested seq's
type is ALSO a plain dict, unhashable the same way): left unguarded,
either would have reopened the exact crash-vs-refusal defect the pairs
wave fixed for `_loop_zero`'s old `.get` lookup, one level up.
  `_gterm`/`_unshow`   both had a bare `t1, t2 = ty["pair"]` as their
                       only dict case; a witness or a state var typed
                       `{"seq": "seq"}` reaching either would have raised
                       a raw KeyError rather than lowering. `_gterm`
                       gained a second dict branch (checked after `"pair"
                       in ty`) building the ground nested-seq term
                       `([row1, ..., rown] : List (List Int))`
                       recursively, each row lowered through the
                       existing flat "seq" case; `_unshow` needed no
                       second branch at all, only the guard `"pair" in
                       ty` on the existing one, since a nested seq's
                       witness rendering (interp.py's `_j`, recursing
                       into a tuple-of-tuples the same way it recurses
                       into a pair) is ALREADY just nested Python lists,
                       behaving like interp.py's own nested tuple for
                       every op a certificate evaluates, exactly the
                       reasoning the flat-seq case was built on.
  `_loop_zero`         the loop-state placeholder built for `min_max`'s
                       pair return had the same bare `t["pair"]`. Fixed
                       the same way: guarded, and a bare nested-seq state
                       var still gets no placeholder (None), same as the
                       flat "seq" string case below it -- an honest
                       `NotImplementedError` from the caller if ever hit,
                       not a crash. Dead in both committed nested tasks
                       (`swap_rows` has no loop at all; `row_max_len`'s
                       nested param `m` is read-only, never loop state).

THE ROW-TYPED READ BRIDGE, measured, not assumed needed. SPEC.md's own
build note asked whether a row-typed `get`/`update` needs one more
lemma, since `t_seq_update_get`/`t_seq_fill_get`/`t_seq_append_get`/
`t_seq_slice_get` (SEQUENCES AS VALUES / SEQUENCES: LITERALS... above)
are each a fixed, monomorphic `theorem` over element type `Int`, not a
polymorphic one -- an outer-level read after `update`/`fill`/`++`/slice
on a `List (List Int)` cannot use them at all, element type mismatch.
Measured directly (`harness.run_task`, `swap_rows`, the one committed
task that touches the outer container at all, via `update`): its goals
are small enough (a SIMPLE-shape body, no loop, no big invariant list in
scope) that plain `grind`, `_close`/`_gr`'s own FIRST alternative, closes
every one outright -- the `grind only [...]` fallback naming the flat
lemmas is present in the generated file (`self.seq_mut` is true) but
never fires, confirmed by the proof succeeding before `first` ever tries
it. So the two committed tasks need no new lemma. Built anyway, gated by
a new `self.nested` flag (true iff `{"seq": "seq"}` appears anywhere in
the task's types, detected by dict shape alone, since no AST op node
ever uses "seq" as a dict key): `t_seq_update_get_row`, `t_seq_fill_get_
row`, `t_seq_append_get_row`, `t_seq_slice_get_row`, the IDENTICAL proof
scripts as their flat twins with only the element type changed (`Int` ->
`List Int` for the payload, the index type staying `Int` throughout) --
measured by a four-theorem scratch probe, lean 4.33.1, core only: all
four compile clean, depending on {propext, Quot.sound} like every other
bridge lemma in this file, confirming the tactic text never actually
inspects the element type (`omega` closes the `.toNat` casts;
`getElem!_pos`/`List.getElem_set`/`List.getElem_replicate`/`List.
getElem_append`/`List.getElem_take`/`List.getElem_drop` are all already
polymorphic in the element type). Emitted by `emit_seq_helpers` and
named in `_seq_hints`'s `grind only` list only when `self.nested` AND
the corresponding flat flag (`self.seq_mut`/`self.seq_new`) is also set,
so a flat-only task's output is unchanged (`self.nested` is false) and a
nested task that never mutates the outer container (`row_max_len`) gets
none of this either (`self.seq_mut`/`self.seq_new` both false for it: it
only reads `m` via `at`/`len`, never `update`s/`fill`s/slices it).
Wired the same way `_unshow`'s pair-component handling was for a shape
neither measured pairs task exercised: unmeasured against a real failing
goal, ready for the nested task whose goal IS big enough to hit the
recursion-depth wall the flat bridge was built for.

THE TERMINATION BRIDGE NEEDED NO CHANGE, confirmed rather than assumed.
`_dec`'s `simp only [List.length_set, List.length_replicate,
List.length_append, List.length_take, List.length_drop]` fallback
(SEQUENCES AS VALUES / THE DECREASING-BY GAP above) names five lemmas
that are ALREADY polymorphic in the list's element type in core Lean
(each states a fact about `List α` for an implicit `α`, never mentioning
`Int`) -- unlike the four READ bridges above, which are fixed,
monomorphic theorems this file hand-proves per element type. So
`List.length_append`/`List.length_take`/`List.length_drop` apply at the
outer level (`List (List Int)`) and the row level (`List Int`)
unchanged, needing no row-typed duplicate; `_dec`/`_dec_needs_seq_bridge`
are untouched by this construct. Neither committed nested task exercises
this path regardless: `swap_rows` has no loop, and `row_max_len`'s
`decreases` (`len(m) - i`) never names a mutated state var (`m` is a
read-only parameter, never loop state; `r`/`i` are plain ints) --
`_dec_needs_seq_bridge` correctly reads False.

`isinstance(self.rett, dict)` (the `dsimp only` fix, PAIRS note above)
ALSO now fires for a nested-seq return, that check's name (`pair_ret`)
predating this construct -- harmless there too, measured directly (a
synthetic probe returning `fill(n, [1,2]) + [[9]]`, verified clean): the
extra `dsimp only` is a no-op on a goal with no bare projection to
reduce, so this changes no task's verdict either way, only sometimes
does one unnecessary (but harmless) reduction step.

NO NEW NAMED REFUSAL beyond what SPEC.md itself draws (v1 has no third
level, no seq of pairs, no seq of bools as a distinct nested element --
enforced upstream by fuzz_lower.check_wf, not by anything added here).
Lean's own `List (List Int)` has no restriction this construct needs to
work around.

MEASURED (`tasks/swap_rows.json`, `tasks/row_max_len.json`, via
`harness.run_task` against the lean backend, `harness.OUT` redirected to
`out/agent-lean-nested/`, matching this note's own reproduction
commands): swap_rows COUNTS (real VERIFIED, `off-by-one` twin REFUTED,
witness m=[[]], i=0, j=0 -> real [[]], the shifted index running off the
single empty row, the update's own `0 <= i < len` obligation false at
the ground witness -- `_cert_undefined`'s kind, the same certificate
shape swap's own off-by-one witness used one level down). row_max_len
COUNTS (real VERIFIED, invariant-drop twin REFUTED, witness exit at
m=[[], [0]], i=2, r=0 -- the dropped upper-bound invariant let the loop
exit with `r` still at its initial 0, `_cert_loop`'s "exit" kind) --
both exactly the witnesses SPEC.md's own text names. Two extra sanity
probes (not committed tasks, scratch JSON, discarded after running):
chained `m[i][j]` (a `requires`/`ensures` pair over `at(at(m,i),j)`)
lowers to `m[i.toNat]![j.toNat]!` and VERIFIES; a combined literal/
`fill`/`+`/`==` probe (`r == fill(n, [1,2]) + [[9]]`) lowers and
VERIFIES too, exercising every operator this note claims is polymorphic
at least once beyond the two committed tasks. A wider sweep of all 23
committed `tasks/*.json` COUNTS uniformly (no REFUSED, no flake). Six
pre-existing tasks named in this construct's own build note (`abs`,
`swap`, `tail`, `filter_pos`, `divmod_pair`, `min_max`) were regenerated
into the same directory and diffed (`cmp`) against the committed
`out/*.lean`: all twelve files (real and twin) BYTE-IDENTICAL, and a
full diff of the OTHER 15 pre-existing tasks' regenerated output against
their own committed `out/*.lean` also finds zero differences -- this
construct changes nothing about a task that doesn't use it.

THE 14 LOOP-TASK RESIDUAL (2026-09-10, COVERAGE-lifted-785.md "Sole
blockers"): the fourteen lifted loop tasks lean alone still keeps off the
seven-column bar (clover_cal_sum__sum, clover_linear_search1__linearSearch,
dafny_synthesis_task_id_304__elementAtIndexAfterRotation,
dafny_tmp_tmpmvs2dmry_slowmax__slow_max, the two
dafny_verify_tmp_tmphq7j0row_..._cube tasks,
dafny_verify_tmp_tmphq7j0row_generated_code_minimum__minimum,
m2_..._exo9_carre__carre,
program_verification_dataset_..._simplemultiplication__foo, the three
programmverifikation-und-synthese ..._gcdI tasks,
tfg_..._div_ent_it__div_ent_it) plus one already-verified task whose twin
certificate failed (se2011_tmp_tmp71eb82zt_ass1_ex4__eval), all measured
directly (`harness.run_task` against `out/lifted-tasks.r14/`, flake 3)
before touching anything.

MEASURED, the actual gap: NOT the nonlinear-arithmetic/gcd/existential
shapes this residual's own name predicted. Isolating each failing lean
file (plain `lean file.lean`, no adapter) put EVERY ONE of the twelve
still-open tasks' first error at the SAME site: `_t_loop`'s OWN bare
`decreasing_by` (e.g. cal_sum, line 12; cube, line 8; minimum, line 16),
identical in shape to "NOT CLOSED"'s flip/linear_search finding above,
now generalized: `_t_loop` carries only the guard hypothesis (`_hg`),
never the loop's invariants, and every one of these twelve tasks lifts a
Dafny `decreases` idiom (an if-then-else absolute distance, e.g. `if i <=
n then n - i else i - n`, or a bare loop variable added to another, e.g.
gcdI's `x + g`) whose well-foundedness genuinely DEPENDS on a fact the
guard alone never gives (`0 <= i <= n`, `x >= 0 ∧ g >= 0` -- the loop
invariant, not the guard). Confirmed by ground counterexample, not
assumed: cal_sum's `_t_loop`, called directly at n=-1, i=0 (i never
reaches n, the guard `i != n` never turns false, `omega`'s own cutsat
diagnostics name exactly this assignment as satisfying the negated
goal) -- the raw recursive function, as lowered, genuinely does not
terminate on such inputs, so no tactic closes it: the goal is false, not
under-searched. carre and foo (a bare `n - i` decreases, not an
if-then-else) hit the identical class: `.toNat` clamps a negative
difference to 0, so once `i > n` the measure cannot be shown to decrease
either, for the same reason.

FIXED, a narrower, distinct class, one task: se2011_..._eval's own twin
(a compare-flip mutation, guard `y >= 0` where the real program's guard
is `y > 0`) failed for a DIFFERENT reason -- not direction, a `.toNat`
FLOOR artifact. Its decreases is the bare loop variable `y` itself;
`_hg` alone (`y >= 0`) DOES fix the direction (`y - 1 < y` always), but
at the last guard-true step (`y = 0` to `y = -1`) `y.toNat` and
`(y-1).toNat` are BOTH 0 -- a real, provable strict decrease (`0 >
-1`), lost because `.toNat` floors every value `<= 0` to the same 0,
not a false goal this time. `(decreases + 1).toNat` fixes exactly this
at zero cost elsewhere: algebraically `a < b -> a + 1 < b + 1` for any
Int a, b, so every decreasing_by goal already closed by `omega`/`grind`
from `dec`'s own strict decrease closes identically from `dec + 1`'s
(same hypotheses, same tactics, one more trivial `+1` on both sides).
Landed as `dec1` in `lower_loop`, used at `_t_loop`'s and
`_t_loop_spec`'s own `termination_by`/`decreasing_by` sites in place of
the bare `dec` (three call sites; `dec` itself is untouched everywhere
else -- `dec_d`'s definedness obligation, `_dec_needs_seq_bridge`'s AST
check -- so nothing but the measure's own well-foundedness proof
changed). Regression: all 23 `tasks/*.json` lean cells COUNT identically
before and after (measured, `harness.run_task` per task); text is NOT
byte-identical any more (every loop task's `termination_by` line now
reads `(dec + 1).toNat`), an intentional, explained departure from this
file's usual byte-identical bar, since the shift is provably harmless to
every already-working case and the alternative (gating it behind a
per-task flag) would have needed the same "does the guard alone already
suffice" judgment call this note's own measurement shows is only
answerable by literally trying it.

MEASURED, before -> after, flake 3, wall seconds (all fifteen; none
close to the harness's wall backstop in either run): clover_cal_sum__sum
0.6s -> 0.6s, clover_linear_search1__linearSearch 0.7s -> 0.8s,
elementAtIndexAfterRotation 0.5s -> 0.6s, slow_max 1.0s -> 1.2s, cube
(ai_agent_validation_examples) 0.5s -> 0.6s, cube
(ai_agent_verify_examples_cube) 0.5s -> 0.6s, minimum 1.3s -> 1.4s,
carre 0.6s -> 0.5s, foo 0.5s -> 0.5s, gcdI (ex_05_Hoangkim) 14.0s ->
13.7s, gcdI (ex06-solution) 1.3s -> 1.4s, gcdI (ex_06_hoangkim) 10.3s ->
10.2s, div_ent_it 0.9s -> 1.0s, eval 0.5s -> 0.5s. ONE cell moved:
se2011_tmp_tmp71eb82zt_ass1_ex4__eval, verified/unproved ->
verified/refuted (COUNTS, witness x=1 -> real 1, compare-flip twin 2).
The other fourteen are byte-for-byte the same verdict pair as measured
before this note (thirteen unproved/unproved or unproved/refuted,
unchanged; div_ent_it's twin ALSO still fails its own `_t_loop`
decreasing_by, a second instance of the direction class, `r_v -> r_v -
b` needing `b > 0` from the invariant, not the guard `r_v >= b` alone).

STAYS OPEN, by name, and why: clover_cal_sum__sum,
clover_linear_search1__linearSearch, the two ..._cube tasks,
dafny_verify_..._minimum, m2_..._carre, ..._foo, all three ..._gcdI
tasks, and tfg_..._div_ent_it -- all eight (eleven counting both cube
rows and all three gcdI rows) share the single direction-class gap above:
`_t_loop`'s bare decreasing_by needs a fact only the loop's OWN
invariants carry, and threading them through would mean `_t_loop` taking
a domain-restricting hypothesis argument that `_t` (which has no
hypothesis to supply, called on every Int including out-of-precondition
ones) cannot construct without either becoming partial itself or a
fuel-bounded redefinition of `_t_loop`, `_t`, `_t_loop_spec`'s applied
terms and `_cert_loop`'s certificate construction together -- the same
"too wide a blast radius" scope "NOT CLOSED" flagged for flip and
linear_search 2026-09-09, now measured to be the dominant shape across
this residual too, not a corner case. dafny_synthesis_task_id_304__
elementAtIndexAfterRotation is a different shape entirely (no top-level
loop -- a SIMPLE-shape single `at` with a `mod`-of-a-difference index,
`(index - n + len) % len`): its own `_wf1`/`_wfbody` theorems fail
inside the existing div/mod bridge (`_close`'s `divmod_prelude`), a
distinct, still-uninspected gap this note did not have time to isolate.
Left honestly unproved rather than forced, matching this file's standing
rule: a recorded absence, never a faked proof.

THE DOMAIN HYPOTHESIS, closing nine of the ten above (2026-09-10, later
the same day). THE WORK the residual's own "too wide a blast radius"
paragraph declined: `_t_loop` now takes the loop's own `requires`
(`hpre`) and invariants (`hinv1..N`) as explicit parameters, exactly the
context SPEC.md grants the `decreases` clause, so its own `decreasing_by`
can finally use them; `_t`, `_t_loop_spec`'s applied term and
`_cert_loop`'s certificate construction all updated to supply the extra
arguments consistently. GATED, not unconditional: `_loop_needs_domain_hyp`
(new) reads the guard/decreases SHAPE alone (body-blind, cheap) and skips
the whole mechanism whenever the guard already bounds the measure's
direction by itself (an order comparison, at top level or inside a
top-level `and`, whose two operands are EXACTLY `decreases`'s own two
subtraction operands, in the guard's own direction -- every one of
reverse/tail/filter_pos/min_max/seq_max/row_max_len/all_nonneg/contains/
count_matches/first_even/sum_upto/is_prime/digit_sum's own committed
shape). MEASURED AS A REGRESSION, not assumed safe: the first version
threaded the hypothesis onto EVERY loop task unconditionally, and it
broke three already-passing committed invariant-drop twins (reverse,
min_max, linear_search) -- their own guard already sufficed, so `_t_loop`
never previously needed a REAL preservation proof of its own, and forcing
one demanded a fact the twin's OWN dropped invariant carried (reverse:
`len(r) = len(s)`, needed to bridge a `.set` read after the drop,
genuinely absent from the surviving two invariants -- a live ground
counterexample, `r = []` against `s = [x]`, satisfies every remaining
hypothesis and refutes the goal, not a tactic gap) -- `_t_loop`'s own
definition failed to elaborate, and its `sorryAx` poisoned the
certificate that unfolds `_t_loop` at the witness (`t_refutation_
certificate` itself audited `[sorryAx]`, UNPROVED not REFUTED, silently,
since a file can still exit 0 with other theorems sorry'd). The gate
restricts the mechanism to loop tasks whose OWN termination proof
actually needs it, so every other task keeps its exact prior `_t_loop`/
`_t` text, byte-identical, structurally immune to this failure mode (a
dropped invariant never threaded into `_t_loop` at all cannot be missed
there).

THREE LEAN SURPRISES on the way to a working `have`-based preservation
proof inside `_t_loop`'s own recursive self-call, each measured on a
scratch probe before trusting the fix generically, all now recorded in
`lower_loop`'s own inline comments at the site each one fixes: (1) a
`;`-chained one-line `by {split_tac}; {gr}` parses as `by ({split_tac};
{gr})`, not `by ({split_tac}); {gr}` -- `repeat split` fails outright
with nothing to split (an ordinary arithmetic invariant), so the whole
compound fails at its first step and `gr` never runs; (2) an existential
invariant's own preservation (minimum's `∃ i, ... ∧ m = a[i]`, a running-
extremum witness) needs its OLD witness `obtain`ed into a concrete local
BEFORE `grind` can chain it through a merged if-update -- grind cannot
invent an existential witness through the update itself; (3) `repeat
split` on a merged if-update leaves two goals and a bare tactic after it
only closes the first, needing `all_goals`. None of the three is a
recursion-position quirk as first suspected (measured: each one
reproduces identically in a non-recursive `def` and even inside a plain
`theorem`'s own tactic block) -- all three are ordinary Lean parsing/
tactic-scoping facts that happened to matter here because this is the
first place in this file writing a multi-step tactic INLINE inside a
recursive function's own term-mode argument position.

MEASURED, the ten named tasks, before -> after, flake 3 (`harness.
run_task` against `out/lifted-tasks.r14/`), wall seconds: clover_cal_sum
__sum 0.6s -> 0.6s (COUNTS, was unproved/unproved); clover_linear_
search1__linearSearch 0.8s -> 1.0s (COUNTS, was unproved/unproved);
dafny_tmp_tmpmvs2dmry_slowmax__slow_max 1.2s -> 1.4s (COUNTS, was
unproved/unproved); dafny_verify_..._minimum 1.4s -> 1.4s (COUNTS, was
unproved/unproved); m2_..._carre 0.5s -> 0.6s (COUNTS, was unproved/
unproved); ..._foo 0.5s -> 0.5s (COUNTS, was unproved/unproved);
..._gcdI (ex_05_Hoangkim) 13.7s -> 13.5s (COUNTS, was unproved/unproved);
..._gcdI (ex_06_hoangkim) 10.2s -> 10.8s (COUNTS, was unproved/
unproved); ..._gcdI (ex06-solution) 1.4s -> 1.5s (COUNTS, was unproved/
unproved); tfg_..._div_ent_it 1.0s -> 1.0s (COUNTS, was unproved/
unproved -- the note's own prior reading named it unproved/refuted on
its TWIN alone, both cells now verified/refuted). NINE OF TEN MOVED to
verified/refuted (COUNTS); cube (both ai_agent_validation_examples and
ai_agent_verify_examples rows, 1.0s and 1.0s, unchanged from before) is
the sole holdout, and NOT a termination-direction gap: its own
`_t_loop`'s decreasing_by now succeeds (the fix reaches it), but a
DIFFERENT, LOOP-INVARIANT-PRESERVATION obligation the fix newly requires
`_t_loop`'s own definition to discharge for real -- `c >= 0` preserved
across `c := c + k` where `c + k = (i+1)^3` -- needs `x >= 1 -> x^3 >= 0`,
plain nonlinear sign reasoning `grind`'s linear cutsat core cannot do and
this file has no Mathlib `nlinarith`/`mul_nonneg`-style bridge for
(confirmed by ground counterexample search: `grind`'s own cutsat reports
a satisfying assignment with `c := -1`, i.e. it is not under-searching, it
genuinely lacks the theory). `Int.mul_nonneg` exists in core Lean
(measured, a three-line scratch probe) and could close it, but wiring a
generic nonlinear-nonneg bridge is a distinct, unstarted piece of work,
outside THIS wave's own scope (the termination-direction class, not
nonlinear arithmetic), left honestly open by name rather than forced or
silently folded in.

REGRESSION, the full committed matrix. All 23 `tasks/*.json`, real and
twin, through `harness.run_task` against the lean backend directly
(matching this file's own measurement discipline, not `run_par.py`'s
multi-kernel table): 23 of 23 COUNT, identically to the committed
AGREEMENT.md row for every one (no cell moved down). Wall seconds
(current run; the 13 loop tasks' source text is NOT byte-identical any
more for the digit_sum case alone -- see `_loop_needs_domain_hyp`'s own
note on why digit_sum, despite committed and passing before, reads
"needs the hyp" under the cheap body-blind rule -- every other loop
task's source is byte-identical, `needs_hyp` reading False for all of
them): abs 0.3s, all_nonneg 0.6s, contains 0.8s, count_matches 0.5s,
digit_sum 0.9s, divmod_pair 0.4s, factorial 0.4s, fib 1.3s, filter_pos
1.3s, first_even 0.9s, gcd 0.7s, is_prime 0.8s, linear_search 0.8s
(REGRESSED to unproved/unproved in the FIRST, ungated version of this
fix, RESTORED here), max 0.3s, min_max 5.0s (also regressed/restored,
mirroring reverse below), remainder 0.4s, reverse 1.5s (regressed/
restored, the `len(r) = len(s)` counterexample above IS reverse's own
twin), row_max_len 1.3s, seq_max 1.2s, sum_upto 0.4s, swap 0.9s,
swap_rows 0.9s, tail 0.9s. No absolute prior-session per-task wall times
were captured for these 23 (the standing note only timed the ten loop-
residual tasks), so this reading is the "after" half only; the verdict
match against AGREEMENT.md is the load-bearing regression check, not the
timing.

STAYS OPEN, by name: the two `..._cube` tasks (nonlinear cube-nonneg
preservation, above); `elementAtIndexAfterRotation`'s own unrelated
div/mod-bridge gap ("STAYS OPEN" above, untouched this wave).

BOOLEANS AS COMPUTATIONAL VALUES (2026-09-10, "sole blockers" wave).
COVERAGE-lifted-785.md named 13 lifted tasks and three v1nested
fuzz-family members (fz_v1nested_026, fz_p_nest_eq, fz_p_nest_lit) as
lean's own residual, all under one stated reason: "boolean operator '==' /
'and' in computational position is not lowered for lean" -- term()'s own
final raise, since prop() already had a Prop-producing case for
==/!=/CMP_OPS/and/or/not but term() had no Bool-producing parallel, the
exact gap the "Pairs" note above already named as SPEC.md's next
construct.

MEASURED FIRST, before fixing anything: of the 13, only 6 actually hit
this reason (both real and twin bodies, lowered in isolation to confirm):
dafny_synthesis_task_id_396__startAndEndWithSameChar, _406__isOdd,
_600__isEven, _637__isBreakEven, _77__isDivisibleBy11,
_79__isLengthOdd -- every one a SIMPLE-shape, single-assign body
computing `result := (a == b)` over ints (four direct/mod comparisons,
one via two `at` reads standing in for a character compare). The other 7
abstain for two genuinely different, pre-existing SIMPLE-shape
restrictions, read and confirmed, not touched by this note:
clover_is_even__computeIsEven, cs245_verification_tmp_tmp0h_nxhqp_a8_q2__
a8Q1 and dafny_learn_tmp_tmpn94ir40q_r01_assertions__max all read "a path
that assigns nothing is not lowered for lean"; dafny_learning_experience_
tmp_tmpuxvcet_u_week1_7_maxsum__maxSum, dafny_synthesis_task_id_801__
countEqualNumbers and both dafny_verify_tmp_tmphq7j0row_test_cases_
{ghost__myMethod,index__maxSum} read "statements after a branch are not
lowered for lean".

THE FIX. term() grew one new case, parallel to prop()'s existing one, for
the identical operator set (==, !=, <, <=, >, >=, and, or, not):
`decide (self.prop(e, env, types))`, reusing prop()'s own formula text
unchanged and bridging Prop -> Bool with `decide`, sound because every
sort v1 has here (Int, Bool, seq, nested seq) carries a computable
`Decidable` instance for every one of these operators in core Lean (Int's
linear order and DecidableEq, List/List (List Int)'s structural
DecidableEq, Bool's own DecidableEq): one line, no per-sort code. dcond()
needed no new case: and/or/not/comparisons/==/!= already fell through its
generic per-argument case or its dedicated and/or short-circuit branch
regardless of position, so definedness was already position-agnostic.

MEASURED: all six SIMPLE int-comparison tasks above COUNT (real VERIFIED,
twin REFUTED) at flake 3 on the first try, `grind [f]` alone (the
EXISTING base tactic every spec/wfbody theorem already tries first)
closing every one with no new lemma -- `decide_eq_true_eq` is already in
grind's own default simp set:
  dafny_synthesis_task_id_396__startAndEndWithSameChar: witness s=[0],
    real True, off-by-one twin index 1 outside [0,1);
  dafny_synthesis_task_id_406__isOdd: witness n=-1, real True, twin False;
  dafny_synthesis_task_id_600__isEven: witness n=2, real True, twin False;
  dafny_synthesis_task_id_637__isBreakEven: witness costPrice=0,
    sellingPrice=1, real False, wrong-var twin True;
  dafny_synthesis_task_id_77__isDivisibleBy11: witness n=11, real True,
    twin False;
  dafny_synthesis_task_id_79__isLengthOdd: witness s=[0, 0, 0], real
    True, twin False.
A scratch probe (lean 4.33.1, core only, not a committed/fuzzed task)
confirms the same holds with no new lemma for Bool `and`/`or`/`not` and
Int `<`/`<=`/`>`/`>=` too: `grind [f]` alone closes each.

THE SEQ-EQUALITY RESIDUAL, closed too. fz_p_nest_lit (computational
`and`) COUNTED immediately with the fix above alone, but fz_v1nested_026
and fz_p_nest_eq (computational `==` on nested seqs, `r := (m == n)`)
only moved from abstain to UNPROVED/refuted: `decide (m = n)` lowers to
Lean's native STRUCTURAL list equality, but this file's own ensures
clauses state seq equality ELEMENTWISE (SPEC.md's "equal lengths and
equal elements at every index"), so `decide_eq_true_eq` alone gets the
goal down to `m = n`, one step short of the length-plus-pointwise Prop
the spec theorem actually carries. One more lemma, `t_seq_ext`, list
extensionality via `List.ext_getElem` plus the same `getElem!_pos`
totalization the read bridges already use, proved once, generic in the
element type (`{alpha : Type} [Inhabited alpha]`: `List.ext_getElem`
needs no DecidableEq, so unlike the read bridges this needs no `_row`
duplicate, one lemma covers flat and nested alike). Gated by a new
`self.seq_eq_comp` flag (`_stmts_have_seq_eq_comp`/`_term_bool_has_seq_
eq`), a walk restricted to genuinely computational-position expressions:
assign/return/var-init, both `if` arms, a while body, descending through
`ite`/`call`/`and`/`or`/`not` exactly as term() itself does, so a seq
`==` sitting in an if-COND or a spec clause (already handled by prop()
with plain `=`, needing no `decide` at all) never sets it. Named in
`_seq_hints()`'s `grind only` list and emitted by `emit_seq_helpers()`
only when it fires, so a task that never computes a seq equality never
sees it. MEASURED (`fuzz_lower.py --only lean --tasks fz_v1nested_026,
fz_p_nest_eq,fz_p_nest_lit --n 400 --seed 1 --flake 3 --jobs 3`, matching
this note's own reproduction command): before this wave all three read
abstain (the boolean-operator reason), 0 of 3 counted; after, all 3 of 3
count (fz_v1nested_026 and fz_p_nest_eq: real VERIFIED, twin REFUTED;
fz_p_nest_lit: real VERIFIED, twin REFUTED, unaffected by `t_seq_ext`
since it was already counting before that lemma was added).

BONUS, outside this wave's own scope but measured in passing: the
"Pairs" note above named fz_v1pairs_053 and fz_p_pair_eq as this same
computational-bool gap and left both unfixed. fz_p_pair_eq now COUNTS
too (real VERIFIED, twin REFUTED), the identical `decide` fix, no pair-
specific code involved; fz_v1pairs_053 did not land in this run's own
--seed 1 sample, so it is unmeasured here, not regressed.

REGRESSION. All 23 committed tasks/*.json, real and twin, regenerated
(`harness.load` + `lower_lean.lower`, matching `harness.run_task`'s own
call shape) and diffed against a byte-identical snapshot of this file
from immediately before this wave (`git diff` captured and reverted with
`patch -R` into a scratch copy, the running worktree never touched): 0 of
23 differ, in either the real or the twin source. This matches the
exhaustive-raise argument exactly: every one of these six operators, in
any position, previously raised NotImplementedError from term() with no
other call site catching it, so a task that lowers successfully today
necessarily never reached the new code, before or after. The 7
non-boolean-gap tasks among the 13 (named above) also read byte-identical
abstain reasons before and after.

STILL OPEN, named. The 7 lifted tasks abstaining for the two other
SIMPLE-shape reasons are untouched: clover_is_even__computeIsEven,
cs245_verification_tmp_tmp0h_nxhqp_a8_q2__a8Q1, dafny_learn_tmp_
tmpn94ir40q_r01_assertions__max, dafny_learning_experience_tmp_
tmpuxvcet_u_week1_7_maxsum__maxSum, dafny_synthesis_task_id_801__
countEqualNumbers, dafny_verify_tmp_tmphq7j0row_test_cases_ghost__
myMethod, dafny_verify_tmp_tmphq7j0row_test_cases_index__maxSum -- real
gaps in this SIMPLE-shape lowering's control-flow coverage, not booleans,
genuinely out of this wave's scope. `implies` in computational position
is also still unfixed (no measured task needs it, and SPEC.md's own list
never names it), left an honest NotImplementedError like every other
genuinely unlowered shape.

THE DEAD-BRANCH RESIDUAL (2026-09-10, "sole blockers" wave, closing the
two control-flow abstains the "BOOLEANS" note above measured and left
open). Both named reasons trace to `to_expr`, the SIMPLE/RECURSIVE
expression builder: it turns a loop-free statement list into ONE
expression for the return value, and had no way to express a branch
that contributes nothing to that expression, or a statement that
follows a branch whose own arms merely continue.

MEASURED FIRST, the seven tasks COVERAGE-lifted-785.md names as lean's
sole remaining blockers (harness-shaped: lower + cell_pair, flake 3,
directly against out/lifted-tasks.r14/, before touching anything): all
seven read ABSTAIN, matching the two reasons named above --
clover_is_even__computeIsEven, cs245_verification_tmp_tmp0h_nxhqp_a8_q2__
a8Q1 and dafny_learn_tmp_tmpn94ir40q_r01_assertions__max on "a path that
assigns nothing"; dafny_learning_experience_tmp_tmpuxvcet_u_week1_7_
maxsum__maxSum, dafny_synthesis_task_id_801__countEqualNumbers,
dafny_verify_tmp_tmphq7j0row_test_cases_ghost__myMethod and dafny_verify_
tmp_tmphq7j0row_test_cases_index__maxSum on "statements after a branch".
Read directly (task JSON, not just the reason string): every one is an
honest gap, not a disguised harder shape -- clover_is_even is `is_even
:= false; if x % 2 == 0 { is_even := true }` (no `else` at all, lifted
as an explicit empty `else: []`); countEqualNumbers is three sequential
`if cond { count := count + 1 }` statements, each with an empty else,
chained one after another (both reasons in the same body); the four
"statements after" tasks are each one if (both arms present, neither
ever returning) followed by a further assign (`myMethod`'s `y := a +
b`, the two `maxSum` tasks' `r := (s, m)`).

THE FIX, two small additions to `to_expr`, both keeping its existing
recursive shape:
  empty branch    `to_expr([], env, types)` no longer raises
                  unconditionally: SPEC.md's plain fall-through means a
                  branch with nothing of its own to contribute leaves
                  the return variable exactly as it was before the
                  branch, and `env[self.ret]` IS that prior value --
                  every earlier assign/var-init on this path already
                  substituted it in (`to_expr`'s own "assign"/"var"
                  cases, unchanged). Falls back to the pre-existing
                  raise only when self.ret was never assigned at all
                  before this empty branch, a genuine gap this note
                  does not touch.
  statements after a branch where neither arm always-returns: a new
                  third case alongside the two existing then_ret/
                  else_ret one-sided splits, firing only when both are
                  False. Rather than inventing a second merge
                  algorithm, it reuses `sym()` -- the forward symbolic
                  executor `lower_loop` already trusts for a LOOP body's
                  own nested ifs -- unchanged, on each branch, then
                  joins the two resulting envs the same way `sym()`'s
                  own "if" case already joins them (`if cp then t else
                  f` per variable, obligations guarded by cp/¬cp) before
                  recursing `to_expr` into the rest of the statement
                  list from that merged env. `sym()`'s `returned`
                  tracking is strictly more general than `to_expr`'s own
                  then_ret/else_ret split (a branch can itself contain
                  an if where one arm returns and the other doesn't,
                  without the OUTER branch always-returning), so this
                  also covers shapes the two pre-existing one-sided
                  cases do not, not just the four measured here.
Neither change touches RECURSIVE bodies' self-call mechanics
(`fresh_hyp`'s dependent-if hypothesis binders, used so a branch's own
requires-discharge tactic sees that branch's condition as a named
hypothesis): no task lowered so far self-recurses AND hits either of
these two shapes, so this stays unexercised there, honestly -- a future
one would need the merged env's `if cp then .. else ..` terms to carry
their own case-split inside the self-call's `by omega/grind` proof
rather than a literal `h : cp` in context, a real question this note
did not have to answer.

MEASURED, before -> after, flake 3 (`cell_pair`, matching harness.
run_task's own call shape), wall seconds per task -- before is instant
(0.0s: an ABSTAIN never reaches a kernel call), so this is really zero
kernel calls -> one real "first | unfold; grind | grind [f]" run plus a
refutation certificate, times three for flake, times two (real, twin):
  clover_is_even__computeIsEven: 0.0s -> 0.4s, witness x=1, real False,
    collapse-if twin True;
  cs245_verification_tmp_tmp0h_nxhqp_a8_q2__a8Q1: 0.0s -> 0.4s, witness
    x=1, y=0, z=1, real 0, collapse-if twin 1;
  dafny_learn_tmp_tmpn94ir40q_r01_assertions__max: 0.0s -> 0.3s, witness
    a=1, b=0, real 1, collapse-if twin 0;
  dafny_learning_experience_tmp_tmpuxvcet_u_week1_7_maxsum__maxSum:
    0.0s -> 0.4s, witness x=0, y=1, real [1, 1], collapse-if twin [1, 0];
  dafny_synthesis_task_id_801__countEqualNumbers: 0.0s -> 0.4s, witness
    a=0, b=1, c=0, real 2, collapse-if twin 3;
  dafny_verify_tmp_tmphq7j0row_test_cases_ghost__myMethod: 0.0s -> 0.3s,
    witness x=20, real 39, wrong-var twin 19;
  dafny_verify_tmp_tmphq7j0row_test_cases_index__maxSum: 0.0s -> 0.4s,
    witness x=0, y=1, real [1, 1], collapse-if twin [1, 0].
All seven: real VERIFIED, twin REFUTED, no flake disagreement, `grind
[f]` alone (the existing base tactic every spec/wfbody theorem already
tries first) closing every one, no new lemma needed -- the fix only
widens what `to_expr` can express, it adds nothing to the proof
automation.

REGRESSION. All 23 tasks/*.json, real and twin, regenerated (matching
harness.run_task's own call shape) and diffed byte-for-byte against a
snapshot of this file from immediately before this note's two edits
(the two hunks isolated and reverted into a scratch copy, this worktree
never touched): 0 of 23 differ, in either the real or the twin source --
every committed body's own if-chains already always-return or always-
assign on both arms in the shapes that reach `to_expr` today, so neither
new code path fires for any of them. The full committed matrix was also
re-run through the kernel (flake 3, not just diffed): all 23 still read
real VERIFIED / twin REFUTED, matching AGREEMENT.md's lean column
exactly, cell for cell; per-task wall seconds, all close to their
pre-existing range and none near the harness's wall backstop: abs 0.4s,
all_nonneg 0.7s, contains 0.7s, count_matches 0.5s, digit_sum 0.5s,
divmod_pair 0.4s, factorial 0.4s, fib 0.5s, filter_pos 1.2s, first_even
0.8s, gcd 0.7s, is_prime 0.6s, linear_search 0.8s, max 0.4s, min_max
4.7s, remainder 0.4s, reverse 1.3s, row_max_len 1.3s, seq_max 1.2s,
sum_upto 0.5s, swap 1.0s, swap_rows 1.0s, tail 0.9s.

STAYS OPEN. Nothing named by this wave's own target list remains open:
all seven of COVERAGE-lifted-785.md's lean sole-blockers now count. The
two residuals this file already carries stay exactly as measured before
tonight and are untouched here: THE 14 LOOP-TASK RESIDUAL's nine
direction-class loop tasks (`_t_loop`'s bare decreasing_by needing an
invariant the guard alone does not give) and dafny_synthesis_task_id_
304__elementAtIndexAfterRotation's own div/mod-bridge gap. `implies` in
computational position and a self-recursive body hitting either shape
fixed tonight are also still open, both genuinely unexercised by any
measured task, named honestly above rather than guessed at.

SECOND PASS (2026-09-10, night), THE TARGET's own four named items,
measured before touching anything (`harness.run_task`-shaped, flake 3,
against out/lifted-tasks/ directly): prog_fun_solutions_tmp_tmp7_gmnz5f_
extra_mod__mod read verified/UNPROVED (regressed from verified/refuted in
the eleventh sweep); both ..._cube tasks read unproved/unproved; dafny_
synthesis_task_id_304__elementAtIndexAfterRotation read unproved/refuted;
dafny_verify_..._downWhileNotEqual read verified/unproved; se2011_..._eval
already read verified/refuted (THE DOMAIN HYPOTHESIS's own `dec1` fix,
above, already closed it earlier the same day -- re-measured, not
touched again here).

THE PRESERVATION-HAVE COLLISION, extra_mod's own root cause, diagnosed
first since it explains a class, not just one task: `_loop_needs_domain_
hyp` (THE DOMAIN HYPOTHESIS, above) reads True for extra_mod's own shape
(bare decreases `k`, no subtraction node, the fallback True the cheap
rule always gives), threading `hinv1..5` into `_t_loop`'s own definition;
its `collapse-if` twin drops the loop body's `if k % 2 == 0 { x := x + y
}` to an UNCONDITIONAL `x := x + y`, which genuinely breaks `hinv1`'s own
preservation (`f_s n = x + y * f_s k`) whenever k is odd -- a live,
ground counterexample (k=0, satisfying every OTHER hypothesis), not a
tactic gap, so the `have` proving it inside `_t_loop`'s own def cannot be
closed by any tactic, full stop. Lean auto-inserts `sorryAx` for the
failed `have` and keeps elaborating, so the FILE still exits 0 -- but
that `sorryAx` poisons `_t_loop` itself, and through it every theorem
built on it, including `t_refutation_certificate` (which literally
unfolds `_t_loop` at the witness): audited `[sorryAx, ...]`, so verifiers/
lean.py correctly mints UNPROVED, never REFUTED, silently (no error
surfaces in the adapter's own output, only in `#print axioms`). This is
NOT specific to extra_mod: ANY twin whose mutation breaks true invariant
preservation, on a loop task where `needs_hyp` reads True, hits the
identical wall -- the domain-hypothesis mechanism cannot represent a
genuinely-false preservation step, by construction (`_t_loop` is a total
Lean function; its own recursive-call argument for that invariant must
be an actual proof term for EVERY state satisfying the parameter types,
not just the ones a real execution reaches).

FIXED, extra_mod's own instance, narrowly and measured, not architecture-
wide: `_loop_needs_domain_hyp`'s own docstring (above) had ALREADY
diagnosed the fix and declined it, for digit_sum's identical shape --
"nothing in this guard/decreases SHAPE alone distinguishes it from
div_ent_it's... until the BODY's own update is inspected". Doing that
inspection (new: `_var_writes`, `_loop_needs_domain_hyp`'s own "SELF-
DIVISION SAFE CASE" branch) answers False -- skips the whole domain-hyp
mechanism, back to the pre-existing bare-`_hg`-only `decreasing_by` this
file used before THE DOMAIN HYPOTHESIS wave -- whenever `dec` is a bare
state variable `v`, the guard bounds `v` directly against a LITERAL
(`v > c` / `v >= c`), and the loop body's ONLY write to `v` anywhere in
it (top level or nested -- `_var_writes` walks the whole body, so a
second, conditional write cannot hide from the single-write check) is
`v := v - lit` or `v := v div lit` for a positive int literal: both make
v's new value strictly smaller than its old one UNCONDITIONALLY (`x -
lit < x` for any x once `lit >= 1`; `x div lit < x` once `x > 0` and
`lit >= 2`, and the matched guard supplies exactly that `x > 0`), so
`_hg` alone was always enough and the extra machinery was pure
liability. Correctly answers False for extra_mod's own `k := k div 2`
(guard `k > 0`) AND for digit_sum's `m := m div 10` (guard `m > 0`,
verbatim the shape the standing docstring named), while correctly still
answering True for div_ent_it's near-identical one (`r_v -= b`, guard
`r_v >= b`): `b` is a variable operand there, not a literal, so the new
check's own literal-match test does not fire, `needs_hyp` stays True,
unchanged.

MEASURED (`out/lifted-tasks/` directly, flake 3): extra_mod COUNTS again
(real VERIFIED, collapse-if twin REFUTED, witness n=1 -> real 2, twin 3).
digit_sum (one of the 23 committed tasks) also now takes the pre-existing
path (`needs_hyp` reads False instead of the accidentally-True it read
after THE DOMAIN HYPOTHESIS wave) and still COUNTS, identically to its
committed AGREEMENT.md cell (real VERIFIED, invariant-drop#1 twin
REFUTED). The ten loop tasks THE DOMAIN HYPOTHESIS wave closed (clover_
cal_sum__sum, clover_linear_search1__linearSearch, dafny_tmp_tmpmvs2dmry_
slowmax__slow_max, dafny_verify_..._minimum, m2_..._carre, ..._foo, all
three ..._gcdI tasks, tfg_..._div_ent_it) are UNTOUCHED by this check
(none share extra_mod's/digit_sum's exact shape -- div_ent_it's own guard
compares against a VARIABLE, the six others' decreases is `ite`, `+`, or
a plain `-` not matching a bare-variable decrease at all) and all ten
still COUNT, re-measured directly, real VERIFIED / <mutation> twin
REFUTED, cell for cell identical to THE DOMAIN HYPOTHESIS's own reading.
All 23 tasks/*.json, real and twin, re-run through the lean backend
directly (`harness.run_all`, matching AGREEMENT.md's own call shape): 23
of 23 COUNT, cell for cell identical to the committed lean column.

THE CUBE NONLINEARITY, THE TARGET's own headline item, both `..._cube`
tasks (ai_agent_validation_examples and ai_agent_verify_examples, the
same body): THE DOMAIN HYPOTHESIS's own note already isolated this
exactly -- `c >= 0` (c tracking i^3) preservation across `c := c + k`
needs `i >= 0 -> (i+1)^3 >= 0`, ground-counterexample-confirmed nonlinear
(`grind`'s cutsat reports a real satisfying assignment, c := -1, i.e. it
is not under-searching) with `Int.mul_nonneg : 0 <= a -> 0 <= b -> 0 <=
a * b` measured to exist in CORE Lean (a three-line scratch probe, no
Mathlib import, clean) and close it by hand once the right product is
named. `_nonneg_bridge_lines` (new): for every INT-typed loop state
variable, both its OLD name and its `env_b`-substituted NEW term (the
exact text each invariant's own preservation goal already carries for
that variable, so the atom built here is syntactically the SAME one
grind needs to recognize -- `(i + 1) * (i + 1) * (i + 1)` matching
`_hinv2'`'s own RHS verbatim, not a re-derived equivalent form) -- `0 <=
x`, `0 <= x*x`, `0 <= x*x*x`, each via `Int.mul_nonneg` chained over a
SELF-CONTAINED `by omega` (never a shared named hypothesis, so one
candidate not actually provable nonneg -- `c` itself, signed in general
-- just fails that one `have`, wrapped in `try`, costing nothing else in
the block). Appended as one more `first`-alternative on EVERY loop
invariant-preservation `have`, UNCONDITIONALLY -- not gated behind a new
capability flag, matching THE DOMAIN HYPOTHESIS's own "LOOP TERMINATION
MEASURE +1" precedent: an alternative never reached because an earlier
one already succeeded costs nothing at every task that does not need it.

MEASURED: both cube tasks COUNT (real VERIFIED, invariant-drop#1 twin
REFUTED, witness exit at n=0, i=0, k=1, m=6, c=1), each kernel call under
a second (0.7s, `lean` run directly on the generated file, no adapter
overhead). Regression: the ten domain-hyp loop tasks above (all carry
INT-typed state, so the bridge is generated for each, unconditionally)
re-measured AFTER this fix landed too, still all ten COUNT, identical
witnesses to the reading above -- the base `split_tac; all_goals gr`
alternative still closes first for every one of them, the nonneg bridge
never reached, matching the "costs nothing when unused" claim directly
rather than assuming it. All 23 tasks/*.json re-run: 23 of 23 COUNT,
identical to AGREEMENT.md, digit_sum included.

ELEMENTATINDEXAFTERROTATION, THE TARGET's third item: a SIMPLE-shape
single `at` with index `(index - n + len(l)) % len(l)`, `_wf1`'s own `_h1
: len(l) != 0` proved by `by first | assumption | decide | omega |
grind` against a goal that STILL reads `n >= 0 -> 0 <= index -> index <
len(l) -> (...)`, un-intro'd: the outer `first | grind | (have _h1 :=
...)` tries each alternative from the SAME starting state (`first`
discards partial progress on a failing branch before trying the next),
so the `have`-based fallback's own proof of `_h1` runs with NONE of the
three premises in scope, and none of `assumption`/`decide`/`omega`/
`grind` can derive `len(l) != 0` from nothing. `_divmod_branches` (THE
DECREASING-BY GAP wave, 2026-09-09 third sweep, above) had ALREADY built
exactly the fix -- `intro`-guessed CHAINED repeats, 0..MAX_LEAD candidate
lead lengths, tried as further `first`-alternatives -- but gated it
behind `self.seq_mut or self.seq_new` (clover_rotate, the only task that
had measured needing it, is a seq task), so a non-seq SIMPLE-shape task
whose divisor is `len(l)` (a seq-length term, but the task touches no
`update`/`fill`/literal/concat/slice op, so `seq_mut`/`seq_new` both read
False) never reached the chained alternatives at all. UNGATED the same
way the QUANTIFIED variant just above it already was (2026-09-09's own
"leaving the REPLACEMENT ungated finishes the fix instead of
reintroducing the old broken text under a new gate"): a wrong `nlead`
guess just leaves a `have` that cannot typecheck (or `intro` runs out of
binders), so `first` falls through, never masking failure as a proof --
every task whose bridge already worked at `nlead=0` (digit_sum,
remainder, swap, tail, filter_pos) still succeeds on the very first
candidate, unchanged verdict, changed only in trailing never-reached
alternative text.

MEASURED: elementAtIndexAfterRotation COUNTS (real VERIFIED, off-by-one
twin REFUTED, witness l=[0], n=0, index=0 -> real 0, twin at index 1
outside [0,1)). All 23 tasks/*.json re-run again after this second change
landed on top of the first two: 23 of 23 COUNT, identical to AGREEMENT.md.

DOWNWHILENOTEQUAL, DIAGNOSED, LEFT OPEN -- not a narrow bridge gap like
the three above, a genuine architecture limit of THE PRESERVATION-HAVE
COLLISION's own class, read directly (not guessed): its own guard is
`i != 0` (an off-by-one twin flips it to `i != 1`), decreases bare `i`,
body `i := i - 1`, invariant `0 <= i <= n` -- `needs_hyp` correctly reads
True (a `!=` guard bounds nothing by itself; termination genuinely needs
`0 <= i` from the invariant even for the REAL program, confirmed by
hand: without SOME lower bound, `i` could start arbitrarily negative and
`(i - 1 + 1).toNat < (i + 1).toNat` is false at e.g. i = -5), so THE
SELF-DIVISION SAFE CASE above correctly does not fire for it (its guard
op is `!=`, never `>`/`>=`). The twin's own off-by-one guard lets the
loop step from i=0 (0 != 1 is true) to i=-1, genuinely breaking `0 <= i`
-- THE PRESERVATION-HAVE COLLISION exactly, on a task where domain hyp is
NOT an avoidable accident (unlike extra_mod/digit_sum) but load-bearing
for the REAL program's own termination proof too, so the narrow "skip
the mechanism" fix above cannot apply here even in principle: skipping it
would break the REAL program's own termination. A real fix needs `_t_
loop`'s own recursive step to become a decide-and-fall-back conditional
(`if hok : <preservation holds> then <continue, using hok> else <a
total, unreachable-along-any-real-execution placeholder>`) rather than an
unconditional `have`, so a genuinely-false preservation instance no
longer has to be PROVEN, only ruled DECIDABLE -- sound because interp.py
computes witnesses by literally executing the mutated body (never
consulting the invariant list at all), so the "then" branch is the one
every measured witness actually walks and the "else" branch, reachable
only for hypothetically-typed states no real execution produces, can
return anything total without corrupting any certificate. This is a
change to `_t_loop`'s own recursive-call generation AND `_t_loop_spec`'s
matching proof (which currently reuses the poisoned term via `apply`'s
own proof-irrelevant unification, unmeasured before now -- confirmed by
hand: cube's own file, before its fix, errored ONLY once, at `_t_loop`'s
`have`, with `_t_loop_spec`'s theorem itself merely inheriting a "uses
sorry" warning, never a fresh grind failure of its own), a substantially
larger, riskier piece of work than the three fixes above and NOT landed
this pass -- diagnosed and left open by name, matching this file's own
standing rule, rather than forced or guessed at under time pressure.
se2011_..._eval is UNAFFECTED (already fixed earlier the same day, by
`dec1`, a different gap entirely -- a `.toNat` floor artifact, not a
preservation collision) and re-measured here unchanged: verified/
REFUTED.

STAYS OPEN, by name, after this pass: dafny_verify_tmp_tmphq7j0row_test_
cases_loopinvariant__downWhileNotEqual (THE PRESERVATION-HAVE COLLISION,
above, needs `_t_loop`'s own decide-and-fall-back redesign, not landed
this pass). THE 14 LOOP-TASK RESIDUAL's own nine direction-class tasks
are NOT open any more (THE DOMAIN HYPOTHESIS, earlier the same day,
closed all nine; re-measured, still COUNT, above) -- named here only so
a reader of that still-standing note knows not to go looking for them.
`implies` in computational position and a self-recursive body hitting
either the BOOLEANS or DEAD-BRANCH shapes are still genuinely
unexercised by any measured task, unchanged.

THIRD PASS (2026-09-10, night), downWhileNotEqual: THE PRESERVATION-HAVE
COLLISION's own redesign, landed narrowly. MEASURED first, before
touching anything (`out/lifted-tasks/` directly, flake 3, matching
`run_par.lower_and_dispatch(tasks, present={"lean"}, flake_n=3)`):
downWhileNotEqual read verified/unproved exactly as the second pass left
it; the ten domain-hyp loop tasks (cal_sum, linear_search1, slow_max,
minimum, carre, foo, the three gcdI tasks, div_ent_it), mod, both cube
tasks and all 23 tasks/*.json all read identically to their committed
cells.

THE FIX: `_t_loop`'s own recursive self-call, for a loop whose `needs_
hyp` reads True, now DECIDES its own invariant-preservation obligation
(`if hok : P then <recurse, using hok> else <a total placeholder,
`_loop_zero(self.rett)`>`) rather than PROVING it as an unconditional
`have`. `Decidable P` is automatic core-Lean typeclass search for P's
only constructors here (Int order/equality, `∧`) -- no proof term is
needed at the `dite` itself. The "then"/"else" split moves entirely into
`_t_loop_spec`'s own proof (`then_tac`, the theorem that was ALREADY
proving the real contract): the "then" case still closes on `apply
..._t_loop_spec <;> grind` exactly as before (Prop-irrelevance means it
does not care whether the argument in scope is `hok`'s own projection or
a freshly-proved `have`); the "else" case (`hok : ¬P`, reachable only
for hypothetically-typed states no real execution produces) is closed by
`grind` finding the SAME contradiction the old `have`'s tactic would
have needed to prove directly, now as its contrapositive -- `dite_else_
tac`, sharing the identical `split_tac`/nonneg-bridge alternatives
`have_body` already carried, so a genuinely-false preservation instance
(a live counterexample under the twin's mutation) is no longer asked to
be PROVEN, only ruled DECIDABLE, and the sorryAx that used to poison
`_t_loop` (and everything unfolding it, including the certificate) never
gets inserted.

TWO BUGS FOUND CHASING IT, both measured on scratch probes before
trusting either fix, both distinct from anything this file's standing
notes already named:

`Decidable` for a raw quantifier. A first cut gated the new mechanism on
"no `∃` invariant" alone (mirroring THE HAVE-BINDING WORKAROUND's own
existential-obtain gate). Regressed minimum (`invariant-drop#1`, which
drops its OWN `∃` invariant but keeps its `∀` one) and linear_search1
(a plain `∀` second invariant): `failed to synthesize instance of type
class Decidable (... ∧ ∀ i, ...)` at `_t_loop`'s own `if hok :` line --
`Decidable` for an unbounded-Int `∀` is exactly as unavailable in core
Lean as it is for `∃` (no Fintype/Mathlib bridge here). Fixed by
excluding BOTH quantifier shapes, not only the one named before.

Conjoining loses compositionality. Even past the Decidable gate, cube
(x2) and all three gcdI tasks regressed: `grind` (even with the nonneg
bridge, even with `[gcd_s]`) could not prove OR refute the WHOLE
multi-invariant conjunction as one goal, though the pre-existing `have`
path proves each invariant SEPARATELY and each one alone is easy (a
scratch probe of cube's own else-branch goal, verbatim, left `c + k =
(i+1)*(i+1)*(i+1)` -- one conjunct among five -- unsolved even with
`Int.mul_nonneg` facts already in context, the identical ring-expansion
step that closes fine as an ISOLATED `have`-goal). Rather than rebuild
per-invariant nested dites (sound in principle, real work, not this
pass's budget), `can_dite` is gated to exactly ONE invariant: every
multi-invariant needs_hyp task (cube, gcdI, minimum, linear_search1)
falls back to the untouched `have`-based path, byte-identical to the
second pass; every single-invariant one (downWhileNotEqual, cal_sum,
slow_max, carre, foo, div_ent_it) uses the new dite path and still
counts, measured below.

A repeat of THE HAVE-BINDING WORKAROUND, unmeasured until now at a
`first`-alternative site. Even single-invariant, downWhileNotEqual's own
"else" goal (`⊢ 0 = 0`, a TRIVIAL equality once the placeholder
substitutes) read unsolved with `dite_else_tac` written as `(repeat
split; all_goals grind)` -- ONE parenthesized group, `;`-joined inside.
A scratch probe isolating exactly this goal+context (`/tmp/scratch7.lean`
style) confirmed it directly: `repeat X; Y` parses as `repeat (X; Y)`,
not `(repeat X); Y`, so `split`'s own failure (nothing left to split, by
this point) fails the WHOLE compound tactic on its first attempt, and
`repeat` swallows that as "0 successful iterations" and moves on with
the goal untouched -- silently, no error, since `repeat` never fails.
This is the SAME trap the file's own standing docstring names for a
`have`-body site, rediscovered at a `first`-alternative site instead.
Fixed the same way: `({split_tac}); (all_goals {gr})`, TWO separately
parenthesized groups joined by an outer `;`, everywhere `dite_else_tac`
is built.

MEASURED, after all three fixes landed together: downWhileNotEqual
COUNTS (real VERIFIED, off-by-one twin REFUTED, witness n=1 -> real 0,
twin 1; `#print axioms` clean on both theorems, no sorryAx). The ten
domain-hyp loop tasks, mod, and both cube tasks all re-measured directly
against `out/lifted-tasks/`, all still COUNT, cell for cell identical to
the second pass's own readings (the multi-invariant ones via the
untouched `have` path; the single-invariant ones via the new dite path).
All 23 tasks/*.json re-run: 23 of 23 COUNT, identical to AGREEMENT.md.

COMPUTEPOWER, READ, LEFT OPEN, a DIFFERENT gap than downWhileNotEqual's
own, confirmed by reading its twin's log directly rather than guessed
at: its own `invariant-drop` twin drops the ONE invariant node carrying
BOTH the `0 <= i <= n` bound and `p = power(i)` (SPEC.md nests them into
a single top-level `and`), so the surviving `hinv1` is just `p >= 0` --
useless for termination. `_t_loop`'s own `decreasing_by` (an `ite`-
shaped measure, `if i<=n then n-i else i-n`) needs the dropped bound to
prove the measure's OWN direction and fails to elaborate, UNPROVED
before `_t_loop_spec`'s proof (or this pass's own dite mechanism, which
never fires here anyway: 2 invariants, excluded by the single-invariant
gate) is ever reached. Architecturally adjacent to THE PRESERVATION-HAVE
COLLISION (a dropped invariant breaking something load-bearing) but a
DISTINCT failure site (`decreasing_by`'s termination obligation, not an
invariant-preservation `have`/dite inside the recursive step) that
tonight's fix does not reach and was not built to reach. Unaffected by
every change in this pass (verified/unproved, unchanged, re-measured).

BOTH GETEVENS, MEASURED, LEFT OPEN, honest proof cost above budget, not
a tactic gap this pass can narrow: neither task's loop needs a domain
hypothesis at all (`_loop_needs_domain_hyp` reads False for both --
their guard, `i_v < len(s_out)`, already bounds the decreases measure
directly, the pre-existing safe case), so this pass's own change touches
NEITHER file, confirmed by inspection before re-measuring. Direct `lean`
runs (`-DmaxHeartbeats=4000000`, ten times the harness's own 400,000
budget) on the real program alone did not finish in 280 wall seconds for
either task -- genuinely a search-cost ceiling, not a stuck/looping
tactic (no error, no diagnostics dump, just still running). The likely
expensive step, read from the generated source rather than guessed: `_t_
loop_spec`'s own proof is a RECURSIVE induction over the array length,
and at EVERY step it re-tries the full `_divmod_branches` quantifier-
enumeration chain (built for the div/mod certificate machinery, eleven
`first`-alternatives deep on `_t_wf5` and `_t_loop_spec` alike, each
carrying its own `Int.emod_add_ediv_mul`/`omega` bridge) THEN the seq-
update `grind only [t_seq_update_get, ...]` fallback, because `self.
seq_mut` is true for this task and the WF/loop-spec theorems' own `_gr`
calls receive the div/mod bridge nodes unconditionally once that flag is
set -- the combination compounds per recursion level. Fixing this would
mean narrowing when the div/mod bridge chain is offered to a seq-mutating
loop's own per-step proof, a change to `_gr`'s/`lower_loop`'s calling
convention orthogonal to tonight's own target and not attempted here.

STAYS OPEN, by name, after this pass: computePower (the dropped-bound
termination gap above, a `decreasing_by` problem, not a `have`/dite
one), both getEven tasks (honest proof cost, measured above, not a
tactic gap). The multi-invariant class THE FIX's own gate declines
(cube, gcdI, minimum, linear_search1) is not "open" in the sense of
failing anything measured -- all four still COUNT via the untouched
`have` path -- but a GENERALIZED per-invariant dite (nested, one `hok`
per invariant, rather than one conjunction) would be needed before this
mechanism could reach them too; not built this pass, named so a future
pass does not have to re-discover the conjoining trap above from
scratch. Everything THE 14 LOOP-TASK RESIDUAL and the second pass's own
notes already closed stays closed, re-measured, unchanged.

THE STRING LIBRARY (2026-09-11, SPEC.md "The string library (v1)"): all
17 members landed as this kernel's own prelude definitions
(emit_strlib_helpers(), gated on self.strlib the way seq_mut/seq_new
already gate their own helpers), on `List Int` (a string) and
`List (List Int)` (split's/join's row type, already "Nested sequences
(v1)"'s type). ENCODING, member by member, each a transcription of
interp.py's own `_str_*` helper, checked #eval-by-#eval against it on a
standalone scratch probe before being pasted in: `split(s)` a fold
carrying (rows-so-far, current run), flushed at the end; `split(s,c)` a
structural recursion PREPENDING to the recursive call's own first row
(not a fold's append-at-the-end -- the encoding choice that makes the
roundtrip law below a plain induction); `join` the mirror structural
recursion on rows, last row copied through with no trailing separator;
`tostr` on Lean core's own `Nat.toDigits` (not `partial`, so kernel-
reducible, and its digit Chars are already '0'-'9' so `.toNat` on each
IS the ASCII code SPEC.md wants); `count`/`find` a well-founded
recursion on the scanned list's length (`termination_by`/`decreasing_by
omega`), EXCEPT a singleton pattern `[c]`, which `t_str_count` dispatches
to `t_str_count_elem` (`List.filter (· == c) |>.length`) instead: a one-
element pattern can never overlap itself, so elementwise filtering
already IS Python's non-overlapping count there, and it is what lets the
count-in-a-loop lemma below be a `List.filter_append` induction instead
of `count_go`'s take/drop one; `strip`/`lstrip`/`rstrip` scan-from-an-
end recursion (`rstrip` via `reverse`); `replace` a Nat-fuel-bounded
recursion (fuel = s.length, sound since every step consumes >= 1
element); `lower`/`upper`/the four predicates/`startswith`/`endswith`
plain `List.map`/`all`/`any`/`take`/`drop` over the ASCII tables SPEC.md
states. Every member is TOTAL by construction (no `dcond` case was
added: the generic "strict op, obligation is its arguments'" fallback
already covers all 17, matching SPEC.md's "each total").

LEMMAS, what they close: `t_str_count_elem_step` (`count_elem (l++[x]) c
= count_elem l c + ite`, by `List.filter_append`) and
`t_str_take_succ_toNat` (`s.take(i+1) = s.take i ++ [s[i]!]`, from core's
`List.take_concat_get`) together carry count_vowels' own invariant step
in principle; `t_str_split_sep_ne_nil` (split_sep's recursive call is
always nonempty, closing the `| [] => [[x]]` match's unreachable arm) and
`t_str_join_cons_row`/`t_str_join_nil_row` (join's own equation restated
per split_sep's two cases) carry `t_str_join_split_roundtrip`
(`join(split_sep(s,c),[c]) = s`, structural induction on s) -- SPEC.md's
join-of-split law, proved. The split-length law
(`len(split(s,c)) == count(s,[c])+1`) is NOT proved: not needed by any
of the three committed tasks' own ensures (checked directly against each
task JSON), so not attempted this pass; open, named here.

MEASURED. (a) The three committed tasks, real+twin, flake 3:
word_count COUNTS (VERIFIED, off-by-one twin REFUTED, witness s=[],
matching SPEC.md's own prediction exactly -- closed by
List.drop_zero/List.take_length collapsing the body's full-length slice
to `s` itself, needing no string-lib lemma at all); split_join COUNTS
(VERIFIED, wrong-var twin REFUTED, witness s=[32] c=0, matching SPEC.md's
prediction -- t_str_join_split_roundtrip is the whole proof); count_vowels
REFUSED, real unproved. Debugged directly (lean -DmaxHeartbeats, the raw
kernel error): the failure is not the loop's own math -- a standalone
probe of the SAME wf-clause goal (`0<=i<len -> (nested guard
implications)`) closes on plain `grind` with zero hints -- it is `grind`
case-exploding once `t_str_count`/`t_str_count_elem` sit in the SAME
hint list as the five-vowel `if`'s own nested guards, moved but not
closed by narrowing the grind hint list to only the ops each task
actually uses (self.ga's `has_op` gating above). Open, named: count_vowels
does not verify; the fix is narrowing WHICH theorem gets which hint
subset (wf-clauses need none of the string-lib names; only the loop's
own `_t_loop_spec` preservation step does), a change to `_close`'s/
`lower_loop`'s calling convention this pass ran out of room for.
(b) The family (`v1strlib`, fuzz_lower.py's own build_corpus, --n 400
--seed 1 restricted to this file's --tasks list; the 22 tasks that name
resolves to under this exact corpus, not the 17-task list a family-only
restricted build would give): 4 COUNT (VERIFIED+REFUTED: 004, 007, 012,
070), 13 real-unproved-but-twin-REFUTED, 2 real-and-twin-both-unproved
(031, 190), 3 no-twin (the empty-pattern probes, nothing to measure).
Every cell reached the kernel; none crashed the lowering itself. (c) The
matrix: every one of the 23 non-strlib committed tasks (tasks/*.json
minus the three above) relowers to a BYTE-IDENTICAL Lean source against
this file's pre-string-library version at HEAD (checked directly,
source-for-source, not re-run through the kernel) -- this landing changed
no existing task's output. The three string-lib tasks were not re-run
against the full 26-task kernel matrix beyond the (a) numbers above;
AGREEMENT.md itself was not touched (out of scope: only lower_lean.py was
edited).

STAYS OPEN, by name: count_vowels' own proof (grind hint-scoping, above);
the split-length law (unattempted, not needed by the committed three);
t_str_count_go/t_str_find/t_str_replace's general (length >= 2, or t ==
[] for replace) cases are proved TOTAL only, not proved about beyond
that -- no committed or fuzzed task's ensures needed a fact about them
this pass; isdigit/isalpha/isupper/islower/startswith/endswith likewise
computed but not the subject of any proved lemma. No member is an
abstain (NotImplementedError): every one of the 17 has a real, checked,
total Lean definition: what is open is which FACTS about them are
proved, not whether they lower.

2026-09-11 (ROADMAP 13.4, this session's item: lean's own conformance FAIL
cells, probes fz_p_nodiv/fz_p_modsign_true/fz_p_seqeq_true/fz_p_nest_empty/
fz_p_str_splitempty/fz_p_str_findempty/fz_p_str_tab/fz_p_str_lowernonletter/
fz_p_vac_unsat/fz_p_vac_range). Six gaps closed, all here (verifiers/lean.py
carries the vacuity-smoke read only, no lowering-side vacuity logic):
  - fz_p_nodiv: the bare `/` token fell into term()'s generic fallback,
    raising NotImplementedError -> ABSTAIN (run_par.py's own routing), not
    the ValueError -> LOWER-ERROR every other kernel's adapter raises for
    the same token. Now raises ValueError explicitly (`term()`'s new `if
    op == "/"` case, just above the DIV_MOD branch).
  - fz_p_vac_unsat/fz_p_vac_range: a `requires` unsatisfiable at every
    input let ANY ensures verify (grind/omega can derive anything from a
    false hypothesis), and lean had no native contradictory-hypothesis
    signal the way dafny/verus/spark/framac's own tools already give
    them. `lower()` now emits a second, independent theorem per task with
    a nonempty `requires`, `<name>_t_vacuity_smoke : <params> -> hpre ->
    False`, proved iff the precondition holds nowhere;
    verifiers/lean.py's own note (below) reads its audit.
  - fz_p_nest_empty: `[]` at a declared `seq<seq>` slot lowered
    `([] : List Int)` (a type error against the nested prelude), since
    term()'s "seq" case had no way to see the assignment/return site's
    declared type for an EMPTY literal (nonempty ones infer nested-ness
    from the first element's own sort). `term()` now takes an `expect`
    parameter, threaded from to_expr's tail return/assign/var cases and
    through `ite` branches, consulted only by the empty-literal case.
  - fz_p_str_splitempty/fz_p_str_findempty/fz_p_str_lowernonletter (and
    fz_p_str_tab, the same root cause as splitempty): `t_str_split_ws`/
    `t_str_find`/`t_str_lower` (and the sfuns they call) were never named
    in the grind hint list (`ga_names`, `__init__`) for the split(s)
    1-arg arity, find, or lower/upper -- only count/split(s,c)/join were.
    `_has_call()` (free function, arity-aware, split(s) vs split(s,c))
    plus the widened `ga_names` gating closes it. A `decide` fallback
    alternative, added to the SIMPLE shape's spec tactic ONLY when the
    task has zero params (a fully ground goal, like these three's own
    empty-literal-only probes), closes what grind's e-matching still
    would not reach even with the name in scope (`t_str_split_ws []`'s
    own `List.foldl` under a `let`).
  - fz_p_modsign_true: `unfold {name}_t` hard-FAILS ("Tactic `unfold`
    failed to unfold ... in ...", measured directly) whenever `ensures`
    never mentions the return name (`post_conj` then never substitutes
    the applied call in, so the def name occurs nowhere to unfold) --
    modsign_true's own `ensures x % y >= 0` is exactly this shape. This
    silently discarded every div/mod bridge alternative the nested
    `first` offers, leaving only the bare `grind [name]` fallback, which
    cannot derive Euclidean mod facts alone. `unfold` is now wrapped
    `try` in the SIMPLE shape's spec tactic (a no-op exactly when it
    would have failed; unchanged whenever it succeeds).
  - fz_p_seqeq_true: `t_seq_ext` (list extensionality from length +
    pointwise `getElem!`, SPEC.md "Sequences as values") was gated only
    by a computational-position seq equality in the BODY
    (`_stmts_have_seq_eq_comp`), whose own docstring argued a PROP-
    position one (an `ensures` clause) never needs it, since it renders
    as plain `l1 = l2`, decided by grind's structural/congruence
    reasoning once the values' own CONSTRUCTION is in scope. True for a
    straight-line body; false after a loop, where the postcondition's
    `r = s` is proved from the invariant alone, r and s both OPAQUE
    variables with no construction to unfold -- exactly seqeq_true's own
    shape. `self.seq_eq_comp` now also fires on a seq-sorted `==`/`!=`
    found anywhere in `ensures` (`_prop_has_seq_eq`, new), under
    and/or/not/implies.
Measured (this session, lean 4.33.1): all 10 probes PASS at flake 3 after;
byte identity checked on all 34 committed tasks (`git diff`-visible bytes
changed on 26 of them -- the `try unfold`/`decide`-fallback/ga_names
widening touch every SIMPLE-shape task unconditionally, and the vacuity
smoke touches every task with a nonempty `requires`; 8 stayed byte-
identical); abs/gcd/sum_upto/reverse re-graded verified/refuted, unchanged
against the pre-session lowering+verifier on the same identical source
where bytes did not move, and identical under both lowerings where they
did (abs/gcd/sum_upto); count_vowels stays unproved/unproved on a BYTE-
IDENTICAL source both before and after (its own gap, "STAYS OPEN" above,
not touched by this session -- not one of this session's ten probes).

2026-09-12 (ROADMAP 16.2, lean's own item: the append-of-slices shape
and the three timeouts). `_seq_append_read_script` (new; see its own
docstring for the full ITE-SPLIT-then-NAT-CAST-TRAP mechanism) added as
a `_close` alternative, symmetric to `_seq_update2_script`'s READ-after-
`.set`-chain fix, for the READ-after-`++`/slice shape; `t_seq_index_congr`
promoted from `seq_composed_update2`-only to `seq_composed_update2 or
seq_new` (the same provably-equal-but-not-syntactically-equal-index leaf
shows up on both shapes). Measured (`t/grade.py --kernels lean,dafny
--flake 3` on the nine dafny_synthesis rows this item names, sourced
from `/home/tmcuzzort/tup/t/out/lifted-tasks/`): 262 splitArray moves
lean real/twin from `unproved/refuted` to `verified/refuted` -- full
agreement with dafny's own `verified/refuted`, unchanged. 106
appendArrayToSeq, 240 replaceLastElement and 586 splitAndAppend stay
`unproved/refuted`: each task's OWN `_t_spec` theorem (the postcondition
this method targets) now compiles where it did not before (measured
directly, lean run on the generated source with `_t_spec` isolated), but
a DIFFERENT theorem in the same file still fails --106's `_t_loop_spec`
(the loop-invariant PRESERVATION obligation, a different shape: `r ++
[a[i]!]` read against the OLD invariant's own universally-quantified
facts, never reaching `_seq_append_read_script` because the goal is not
opened by `t_seq_ext`/`And.intro`/a fresh `intro` the way a postcondition
conjunct is) for 106, and for 240/586 one further conjunct inside
`_t_spec` itself where `simp (disch := omega)`'s side-condition for
`t_seq_append_get`'s `hju` needs a length fact (`(List.take n l).length`)
that is not yet in `List.length_take`/`_drop` normal form at DISCHARGE
TIME and `omega` alone does not unfold it (measured: a `disch` that adds
its own nested `simp only [length lemmas]` before `omega` closes this
exact goal in isolation, but regressed 262 when tried in the full
pipeline -- reverted, named open rather than merged broken). 470
pairwiseAddition, 578 interleave, 603 lucidNumbers (timeout/timeout) and
610 removeElement (abstain/abstain) and 576 isSublist (unproved/unproved)
are UNTOUCHED by this session's change -- no time spent on the loop-
chaining or grind-heartbeat work those need; named open, not attempted.
Regression bar (this session, lean+dafny, flake 3): the 34 committed
tasks under `t/tasks/` graded byte-for-byte against `t/AGREEMENT.md`'s
lean column, and the 75 `dafny_synthesis` rows of `t/COVERAGE-lifted-
785.md` graded against that file's own lean/dafny columns -- see the
session's own patch/report for the exact before/after counts measured
(this docstring is the mechanism note; it does not restate numbers that
belong to the grading run, which can drift if re-run under contention).

2026-09-14 (key lean-cert, ROADMAP 16.2's "value-witness certificates
through loop bodies"): first_even's, is_prime's and reverse's own
committed twins (unproved in the reordered-ladder matrix banked at
d38da32) now read REFUTED. Two independent, narrowly-scoped fixes, both
detailed at their own call sites (`lower_loop`'s `ret_cond == "True"`
special case; the new `_cert_undefined_loop` method) rather than
restated here:

  (a) a collapse-if twin whose mutated `if` collapses to the literal
      Lean `True` used to still emit the pre-existing `_hr`-dite +
      dead recursive-call shape for `_t_loop`'s guard-true step;
      `lean -DmaxHeartbeats=1000000` on the emitted file showed the
      auto-generated `decreasing_by` obligation for that now-dead call
      carries no `_hr` hypothesis at all (`set_option pp.all` confirms:
      only the outer `_hg` threads), so the obligation is unprovable as
      stated and Lean recovers with `sorryAx`, which -- `Acc.rec`'s
      motive being Type-valued -- makes the WHOLE function stuck on
      `decide`/`simp`/`grind` forever after, no certificate tactic
      recoverable. Fixed by not emitting the dead branch at all when
      the return condition is this literal constant.
  (b) a body-level undefined witness (`_cert_undefined`) for a task
      whose body has a `while` used to abstain unconditionally
      (`to_expr` renders loop-free shapes only); `_cert_undefined_loop`
      now unrolls the loop concretely, exactly as many iterations as
      interp.py's own execution takes before raising Undef, mirroring
      lower_framac.py's `_cert_stmts` while-case and lower_spark.py's
      own while-body replay (both 2026-09-12) -- never mentioning the
      compiled `{name}_t`/`{name}_t_loop` at all, since SPEC.md's
      definedness calculus is a fact about the raw spec body at the
      ground witness.

Measured (`python3 t/grade.py --tasks <dir> --kernels lean,dafny --flake
3 --jobs <n>`, this machine, lean 4.33.1 / dafny 4.11.0+fcb2042):
  - the 3 committed rows above: unproved -> refuted (twin), real
    unchanged (verified) in every case; dafny unchanged throughout.
  - 8 lifted rows probed beyond the 3 committed ones (Clover_array_
    product.arrayProduct, Clover_array_sum.arraySum, Clover_cal_sum.Sum,
    Clover_double_array_elements.double_array_elements, Clover_linear_
    search1.LinearSearch, Clover_rotate.rotate, Dafny-Exercises..
    ExerciseMaximum.mmaximum1, Dafny_Verify..LoopInvariant.
    DownWhileGreater): 6 of 8 moved unproved -> refuted; 2 did not
    (Sum's off-by-one and DownWhileGreater's compare-flip, both routed
    through the pre-existing `hok`/domain-hypothesis `_t_loop` shape
    unaffected by either fix above -- lean's own message: `error:
    unsolved goals / case refine_2 / ⊢ False` after the `_closer()`
    cascade, i.e. UNPROVED, "refutation certificate declared but not
    kernel-accepted", named open, not attempted this session).
  - regression bar: the 34 committed tasks' lean column matches
    t/AGREEMENT.md byte-for-byte except the 3 rows above (count_vowels'
    own pre-existing unproved/unproved is unchanged); lean's own 66-task
    conformance slice (probe_manifest()+metamorphic items, restricted to
    the lean column via run_par.probe_backends()) reads 0 FAIL both
    before and after (t/CONFORMANCE.md's own baseline is also 0 FAIL for
    lean); the 75 dafny_synthesis rows of t/COVERAGE-lifted-785.md that
    read `verified / refuted` in lean (63 of 75) ALL still do (none
    moved); as a side effect of fix (b), three more of those 75 rows
    (task_id_3 isNonPrime, task_id_106 appendArrayToSeq, task_id_414
    anyValueExists, all `unproved / unproved` at baseline) moved to
    `unproved / refuted` -- the real side is unaffected in every one of
    these, so no cell that counted before stopped counting.

2026-09-14 (lean-loopcert2, ROADMAP 16.2's own item, continuing directly
from the note just above): the two rows that note left open by name,
Clover_cal_sum.Sum (off-by-one) and Dafny_Verify_..LoopInvariant.
DownWhileGreater (compare-flip), both route their "value"-kind witness
through a loop whose OWN termination needs THE DOMAIN HYPOTHESIS (`_t`/
`_t_loop`'s `hpre`/`hinv{i}` params, `lower_loop`'s 2026-09-10 machinery)
-- `_cert_value`'s pre-existing `{name}_t`-based path cannot certificate
either, MEASURED as two DISTINCT failure modes (`lean` run directly on
each emitted file, this session):

  - cal_sum: `{name}_t`'s own definition passes the loop's initial
    invariant to `{name}_t_loop` as a GENERIC `(by grind)` proof
    obligation (true for the real, for every `n`) -- the off-by-one
    twin's mutated entry state makes this obligation FALSE for every
    `n` (not only the specific witness), so `(by grind)` fails at
    DEFINITION TIME and `sorryAx` poisons `{name}_t` itself
    unconditionally; the certificate's own message names the true
    site, `{name}_t`'s `(by grind)` call, never the certificate's own
    text.
  - downWhileGreater: `{name}_t_loop`'s `can_dite`/`hok` mechanism
    (THE PRESERVATION-HAVE COLLISION's own fix, this file's earlier
    dated note) DECIDES the preservation obligation at the mutated
    step and, reading it false, returns `_loop_zero`'s PLACEHOLDER (0)
    instead of continuing -- sound for `{name}_t_loop_spec`'s own total-
    function proof, but not what interp.py's own execution computes at
    the same witness (-1, harness.twin_for's own measurement).
    `ensures` genuinely holds of the PLACEHOLDER, so the certificate's
    `¬(applied = 0)` is a FALSE goal -- lean's own measured message,
    verbatim: `error: unsolved goals` / `case refine_2 ⊢ False`.

THE FIX: `_cert_value_loop` (new, called from `_cert_value` before its
own `{name}_t`-based attempt, only when a while loop needs the domain
hypothesis) never mentions the compiled `{name}_t`/`{name}_t_loop` at
all -- it replays the RAW loop concretely, exactly as `_cert_undefined_
loop` already does for an undefined witness (ground `interp.exec_body`
picks the branch, `self.sym` renders the same ground state as closed
Lean terms one iteration behind), but continues until the guard reads
ground-False (a normal exit, always reached for a "value"-kind witness)
rather than until an interp.Undef, capped at the same MAX_UNDEF_UNROLL.
A final cross-check against `w["_twin"]` (never assumed) means a replay
bug can only make this method abstain (falling through to the pre-
existing path), never assert an unverified claim.

MEASURED (`lean` on each emitted file, this machine, lean 4.33.1):
  - both rows above: unproved -> refuted (twin); real unchanged
    (verified) in both.
  - the same "value"-kind + domain-hyp-loop shape scanned across all 302
    lifted tasks (harness.twin_for + `_loop_needs_domain_hyp` on the
    loop, filtered to lean's own `unproved` cells in t/COVERAGE-
    lifted-785.md's sweep r24): 27 candidates found; 15 (including the
    2 named above) now read refuted (verified real unaffected in every
    one); 12 remain honestly unproved (a genuinely different gap this
    fix does not reach -- e.g. computePower's own dropped-termination-
    bound class, this file's earlier dated note). The 13 additional
    rows: mroot2, mroot3 (both Dafny-Exercises..ExerciseSquareRoot),
    computePower x4 (ai_agent_validation/verify_examples,
    generated_code, two spellings), cube x2 (same two corpora),
    generated_code_minimum, sumIntsLoop, flip (pancakesort), carre,
    foo (simplemultiplication), gcdI x3 (three ex_05/ex_06 spellings),
    sumOfCommonDivisors.
  - regression bar, re-measured after this fix: the 34 committed tasks'
    lean column matches t/AGREEMENT.md byte-for-byte (count_vowels
    unchanged, unproved/unproved); lean's own 66-task conformance slice
    reads 0 FAIL (unchanged); all 63 of the dafny_synthesis rows in
    t/COVERAGE-lifted-785.md reading `verified / refuted` in lean still
    do (none moved) -- `python3 t/grade.py --tasks t/tasks
    --kernels dafny,lean --flake 3 --jobs 8` and a `conformance.py`
    probe restricted to the lean column via `run_par.probe_backends()`,
    both run directly against the emitted sources on this machine.

2026-09-14 (key lean-seqcomp, ROADMAP 16.2's "closing the composed seq
goals", t/DESIGN-lean-seq-composition.md's rows): THE SILENT-DISCH GAP.
`_seq_append_read_script`'s own `rw_step`, `simp (disch := omega) only
[t_seq_append_get, ...]`, discharges EVERY side condition a cited
lemma's instantiation carries; `hju : j < ((l1++l2).length : Int)` has a
`.length` of a `List.take`/`.drop`/`++` term `omega` alone cannot see
through, so on that side condition the lemma was never APPLIED at all
(`simp` reports "made no progress", not a wrong rewrite -- measured
directly, probe240c/f.lean, this session's own scratch probes) --
naively adding a length-normalizing `simp only [...]` before `omega`
inside the SAME disch regressed (probe240c/g.lean: `hj`'s own goal, `0 ≤
j`, has no length term, so an un-`try`-guarded `simp only [length
lemmas]` there raises "simp made no progress" itself and aborts the
`;`-sequenced `omega` that used to close it alone) -- almost certainly
the exact regression 2026-09-12's own docstring above named ("regressed
262 when tried in the full pipeline") without isolating which of the
two side conditions was the actual cause. The fix: `try` around the
`simp only [...]` step alone (never the whole disch), plus
`List.length_cons`/`List.length_nil` in that same normalizing set (106
appendArrayToSeq's own `r ++ [a[i]!]` is a literal ONE-ELEMENT list,
whose own `.length` needs them; measured, probe106f.lean). Additive by
construction and gated the same way `_seq_append_read_script` always
was (`self.seq_new` alone): a side condition `omega` already closed
unaided keeps closing the same way. Measured (`t/grade.py --kernels
lean,dafny --flake 3`, this machine, lean 4.33.1 / dafny
4.11.0+fcb2042): 240 replaceLastElement and 262 splitArray move lean
real from `unproved` to `verified` (twin stays `refuted` in both,
dafny unchanged), each confirmed stable across three separate re-grades
of the same generated source (this session's own scratch runs, not
committed); 106 appendArrayToSeq, 470 pairwiseAddition, 576 isSublist,
578 interleave, 586 splitAndAppend, 603 lucidNumbers and 610
removeElement are UNCHANGED (106/586 reach a DIFFERENT residual gap past
this one, named below; 470/578/603 stay the pre-existing grind-heartbeat
timeouts; 576 hits a distinct elaboration error unrelated to seq
composition, "unknown identifier `result`", named open, not diagnosed
this session; 610 still abstains, "only a single top-level loop is
lowered for lean" -- the two-sequential-loop chaining this item's own
design doc named, not attempted this session, out of scope for the time
available). Regression bar: the 34 t/tasks/ committed tasks are BYTE-
IDENTICAL in behaviour under this change (measured: none of the 34 sets
`self.seq_new`, so `_seq_append_read_script`'s gate never fires for any
of them; `t/grade.py --kernels dafny,lean --flake 3` over all 34 read 33
of 34 agreeing, `count_vowels` unproved/unproved unchanged, matching
t/AGREEMENT.md's own lean column exactly, zero cells moved); the lean
column of every OTHER `seq_new` dafny_synthesis row in t/COVERAGE-
lifted-785.md (257 swap, 261 elementWiseDivision, 273
subtractSequences, 445 multiplyElements, 460 getFirstElements, 587
arrayToSeq, 618 elementWiseDivide, 728 addLists -- the 15 seq_new rows
of that file's 75, this session's own grep over `lower_lean.Lower(...).
seq_new`) is unchanged (all already `verified / refuted`, still
`verified / refuted`).

TRIED AND REVERTED, same session (see `_seq_append_read_script`'s own
"THE INVARIANT-APPLICATION LEAF" docstring for the mechanism): a bare
`| grind` alternative and a dedicated `t_seq_singleton_get` lemma, both
aimed at 106's own remaining `_t_loop_spec` residual. Neither survived
its own regression check -- two `t/grade.py` runs over byte-identical
generated source (240/262, untouched by the change in principle) read
`verified` on one run and `unproved` on the next, at both --jobs 9 and
--jobs 3, i.e. a real flake in `grind`'s own search under a shared
elaboration-step budget, not contention on this shared box (`-D
maxHeartbeats` bounds STEPS, not wall time, but does not bound WHICH
steps a search takes to arrive at a step count, and `grind`'s own term
ordering measurably was not reproducible run to run here). t/AGREEMENT.
md's own 262 row is a committed regression bar this session will not
put at risk for an unfixed row; `test_lower_lean_seqcomp.py`'s own
`SeqAppendReadScriptDischTest.test_singleton_get_and_bare_grind_not_
reintroduced` pins both absent. 106's own residual leaf still needs a
DETERMINISTIC closer that can cite the loop's own `hinv{k}` by name --
`lower_loop`'s own codegen is the one call site that has those Python-
side names in hand; `_gr()`'s generic call sites (used by the WF
theorems too, which have no named invariant hypotheses at all) do not,
so the fix belongs there, not in this shared per-site script. Named
open, not attempted further this session.

2026-09-14 (key lean-closure, ROADMAP 16.2's item "the closure-predicate
timeouts and the seq-typed local abstains"). Two independent fixes, both
gated so every previously-graded task (the 34 committed AGREEMENT.md
rows, the conformance suite, every dafny_synthesis row of COVERAGE-
lifted-785.md already reading verified/refuted) sees BYTE-IDENTICAL
output -- measured directly: `python3` diffed `lower_lean.lower(task,
task["body"])` for all 34 `t/tasks/*.t` files against this session's
own pre-edit copy of the file, zero diffs (none of the 34 use
`spec_funs` at all, `grep -l spec_funs t/tasks/*.t` reads empty, so
`sfun_quantified` is False for every one regardless of the fix); the
seq-placeholder fix only fires when `_loop_zero` previously returned
`None` for a bare `seq` type, an unconditional `NotImplementedError`
before today, so it cannot change any lowering that used to succeed.

(1) THE CLOSURE-PREDICATE TIMEOUT. dafny_synthesis 412 removeOddNumbers/
426 filterOddNumbers/436 findNegativeNumbers/554 findOddNumbers/629
findEvenNumbers (wave O, `t/out/lifted-tasks`, gitignored) each call a
spec_fun (`isEven`/`isOdd`/`isNegative`) in executable position inside
their loop body, under a loop invariant that ALSO quantifies over the
same spec_fun (`forall k, isEven(evenList[k]) = true -> exists j, ...`).
Every grind call site in this file (`self.ga`, `f"grind{self.ga}"`) used
to hand that spec_fun's own equation to grind as a raw E-matching hint;
measured (`lean -DmaxHeartbeats=400000` on the emitted 412 file,
`set_option trace.grind.ematch true` on a scratch copy) to exhaust the
whole per-command heartbeat budget on the FIRST alternative of the
`first | ...` chain (a `deterministic timeout` is not a normal tactic
failure -- `first` never gets a turn to try the next branch), reading
TIMEOUT for both real and twin on every one of the five. Fix: `Lower.
__init__` now also computes `sfun_quantified` (True iff some spec_fun is
called inside a `forall`/`exists` reachable anywhere in the task or
body, via the new module-level `_sfun_under_quantifier`/
`_calls_any_named` walkers) and `ga_wo_sfuns` (the same grind hint list
with the spec_fun names stripped back out); the new `Lower._grind_base`
method returns the pre-existing `f"grind{self.ga}"` when `sfun_quantified`
is False, and otherwise `f"(first | (simp only [{names}] at * <;>
grind{self.ga_wo_sfuns}) | grind{self.ga})"` -- citing each spec_fun's
own equation as a DETERMINISTIC rewrite (closes under quantifier binders
too, with no E-matching search) FIRST, falling back to the pre-existing
raw hint only if that fails outright (never tried first on this shape,
since that ordering was the original bug). An earlier version of this
session's fix dropped the raw-hint fallback entirely; MEASURED (`t/
grade.py --tasks <the eight, copied from t/out/lifted-tasks> --kernels
lean,dafny --flake 3 --jobs 4`) that this regressed 775 IsOddAtIndexOdd's
own real from VERIFIED to UNPROVED (one of its non-loop grind sites
closes on the raw hint alone, not on `simp only [...] <;> grind` alone),
so the fallback was restored; `_grind_base`'s own docstring above carries
the full account. Every one of the file's 12 `f"grind{self.ga}"` call
sites (`_gr`'s and `_close`'s own `base`, `emit_sfuns`, `emit_clause_wfs`,
both SIMPLE/RECURSIVE-shape spec theorems) now goes through
`_grind_base()` instead, so the fix reaches wherever a spec_fun call
under a quantifier surfaces, not just the loop-preservation site the
five committed rows happened to hit it at first. MEASURED, final code
(`t/grade.py --tasks <412,426,436,554,629,775> --kernels lean,dafny
--flake 3 --jobs 4`, two full runs, plus single `lean -DmaxHeartbeats=
400000` runs on 775's own emitted real/twin files to confirm the
775 fix specifically): 436 findNegativeNumbers moved lean twin TIMEOUT
-> REFUTED (real stays TIMEOUT, the regression bar's own "no real may
move" respected, only the twin side moved and only from timeout toward
refuted, confirmed on two independent flake-3 runs); 412/426/554/629
stayed real TIMEOUT / twin TIMEOUT (the fix removes one source of
heartbeat exhaustion, not the invariant list's own inherent quantifier-
instantiation cost against TWO different sequences at once -- dafny's
own REAL reads unproved on all five under this op too, so the ensures is
hard for every kernel here, not a lean-specific gap); 775 confirmed
restored to the pre-session baseline, real VERIFIED / twin TIMEOUT (a
single `lean -DmaxHeartbeats=400000` run each, real: exit 0, every
theorem including `_t_loop_spec`/`_t_spec` audited clean; twin: still
running past 60s, matching the pre-session "timeout" cell, not re-run
at flake 3 given this session's own time budget). Named open: the
invariant list's own two-sequence quantifier cost on 412/426/554/629,
independent of the spec_fun fix, still needs a dedicated closer (outside
this session's scope: `lower_loop`'s own codegen owns the loop-
preservation goal's shape, same as 106 appendArrayToSeq's still-open
residual noted above).

(2) THE SEQ-TYPED LOCAL ABSTAIN. dafny_synthesis 307 DeepCopySeq (return
`copy`, type bare `seq`, assigned only in the suffix `copy := newSeq`
after the loop, never in the prefix or the loop body) and 743
RotateRight (return `r`, the identical shape) hit `_loop_zero`'s
unconditional `None` for a bare `seq` type, raising `NotImplementedError
("state var 'copy'/'r' uninitialized before the loop")` before ever
reaching a kernel -- ABSTAIN by `run_par.py`'s own routing. Fix: `_loop_
zero` now returns `"([] : List Int)"` for `t == "seq"`, the empty list,
total and well-typed exactly like `(0 : Int)`/`false` for `int`/`bool`
just above it (a bare `seq` state var provably never reads this
placeholder before the suffix overwrites it, the same argument the
docstring already makes for the return-name case generally). MEASURED
(`t/grade.py --tasks <307,743> --kernels lean,dafny --flake 3 --jobs 2`,
plus a single confirming `lean -DmaxHeartbeats=400000` run each for
743): 307 DeepCopySeq moved lean ABSTAIN/ABSTAIN -> real VERIFIED / twin
UNPROVED (confirmed on two independent flake-3 runs); 743 RotateRight
moved ABSTAIN/ABSTAIN -> real UNPROVED / twin UNPROVED (743's own `_t_
loop_spec`/`_t_spec` still carry a `sorryAx` -- a genuinely unclosed
proof obligation, not the seq-placeholder gap this fix targets; named
open, the placeholder fix ends its ABSTAIN but does not itself close the
remaining gap). Neither move is a regression under the bar (`_loop_zero`
only fires where it previously raised, ABSTAIN was never a kernel
verdict to begin with).

2026-09-15 (lean-sole, ROADMAP 16.2/COVERAGE-lifted-785.md's "Sole
blockers": "lean alone: 9"). `Lower._param_state_bridge_lines` (new,
see its own docstring at `lower_loop`) fixes two of the nine: pow's own
REAL (`0 <= a * x`, a param times a loop-state accumulator, both
already nonneg by `requires`/the invariants in scope) and factorial's
own REAL (`0 <= i * res`, the identical class between two bare loop-
state vars), both previously UNPROVED because `_t_loop_spec`'s
recursive-apply closer (`then_tac`, `apply ... <;> self._gr()`) had no
nonlinear-sign theory to offer `grind` -- `_nonneg_bridge_lines` (pre-
existing, wired into `_t_loop`'s own hinv-preservation `have`s, never
into `_t_loop_spec`'s theorem) only ever paired a loop-state term with
ITSELF, never with a DIFFERENT term or a bare param. MEASURED (`lean
-DmaxHeartbeats=400000` on each emitted file, this session): both now
read the exact tool message "error: `grind` failed" only at the
pre-existing, EXPECTED
`_t_vacuity_smoke` site (that theorem is meant to fail -- `requires` is
satisfiable, so `False` is genuinely unprovable there), with zero
un-expected errors elsewhere; `t/grade.py --tasks <dir> --kernels
lean,dafny --flake 3` on each alone reads `real=verified twin=refuted`,
FULL AGREEMENT.

Four of the nine stay open, each for a reason outside this file's own
loop/recursion/goal-closing functions or measured this session as a
pre-existing named gap, not attempted further:
- mfirstCero, find (both `undefined`-kind twin witnesses): the twin's
  own GUARD (not its body) is itself undefined at the witness (measured
  directly, a scratch replay: `i <= len(v) and v[i] != 0` at `v = []`,
  `i = 0` -- the first conjunct holds, so Python's/Lean's short-circuit
  `and` evaluates the second, `v[0]`, out of bounds) -- `_cert_undefined_
  loop`'s own `if guard_now is not True: return None` (frozen this wave,
  belongs to the certificate functions) treats a guard-level Undef
  identically to a false guard and abstains, so no certificate is ever
  built. The fix belongs inside that frozen method (distinguishing
  "guard evaluated to False" from "guard's own evaluation raised
  Undef", the latter being exactly the witness to certify), not in any
  function this wave's item owns.
- dafny_synthesis_task_id_106__appendArrayToSeq (REAL still UNPROVED,
  `undefined`-kind twin already REFUTED): the pre-existing, already-
  named "THE INVARIANT-APPLICATION LEAF" residual (`_gr()`'s own
  docstring above, 2026-09-14) -- `hinv5`/`hinv6`'s own preservation
  goal needs `List.getElem_append`-style index-congruence reasoning once
  `r ++ [a[i]!]` and the invariant's own `s`/`a` sides are DIFFERENT
  lists, tried and reverted there before this wave; unsolved goals
  confirmed again this session (`lean -DmaxHeartbeats=400000`,
  `error: unsolved goals` at the `_t_loop_spec` `hinv5`/`hinv6` cases,
  identical shape).
- dafny_synthesis_task_id_578__interleave, and the two `getEven` rows
  (seng2011, dafny_exercise's own `prac3_ex2`): read TIMEOUT/TIMEOUT on
  both sides of every grade.py run this session, on a box measured at
  load average 150-255 (`uptime`, this session, concurrently) -- wall-
  clock TIMEOUT under that contention is not distinguishable here from a
  genuine heartbeat exhaustion without a dedicated, uncontended
  `set_option trace.grind.ematch true` probe this session did not reach
  before its own time budget closed; named open rather than guessed.

NESTED AND MULTIPLE LOOPS (2026-09-18, ROADMAP WS-20 move 1, the move's
own first item: "nested-loop lowering for Lean, Rocq and F*"). Before this
day a loop inside a loop, or two loops in one body, read ABSTAIN in this
column -- from two different places with two different messages, which is
itself worth recording: `lower`'s own `deep_while` scan only looked inside
the body's NON-`while` statements, so a loop nested in the top-level loop
was invisible to it and fell through to `sym`'s `while` case instead
("nested / multiple loops are not lowered for lean"). `lower` now
dispatches on `_count_whiles`, a count of every `while` anywhere.

WHAT LOWERS NOW, measured on t/tasks/has_duplicate.t (the canonical case:
a `while` inside a `while`, each with its own stated invariants and
`decreases`) and on three scratch tasks built for the shapes the committed
corpus does not yet hold, each cross-checked against dafny in the same
run:
  - a loop inside a loop: has_duplicate, lean ABSTAIN -> real VERIFIED /
    twin REFUTED (collapse-if, witness s=[0,1]); dafny reads the same.
  - two loops in one body (`two_loops`, r counted twice to 2n): real
    VERIFIED / twin REFUTED, FULL AGREEMENT with dafny.
  - three loops nested three deep (`tri`): same, FULL AGREEMENT.
  - two sibling loops inside a loop (`sib`): same, FULL AGREEMENT.
Regression: all 34 previously-committed tasks re-run through lean
(`run_par.py --jobs 4 --tasks t/tasks --kernels lean`) read exactly their
t/AGREEMENT.md cell, count_vowels' `unproved / unproved` included; the 793
twin-ladder rungs of those tasks lower with zero hard failures. Every
single-top-level-loop task still goes through `lower_loop`, whose text is
untouched, so none of their real `.lean` files changed by a byte.

THE THREE THINGS GRIND COULD NOT DO, each measured on the bare goal in
isolation before any of them was written into this file (they are the
substance of the move: the ROADMAP calls this "proof synthesis for nested
invariants", and that is what it turned out to be, not a translation gap):
  1. `grind` cannot prove `P -> Q` from a hypothesis `P -> Q` when `Q` is
     a doubly-nested `exists` over Int with an `s[i]!` body. It negates
     the goal, skolemizes both witnesses into the context with every side
     condition present, and never fires the instantiation that closes it.
     `assumption` closes it in one step, and an enclosing loop's own
     invariant IS, verbatim, one conjunct of the nested loop's exit facts
     in has_duplicate. Hence `assumption` in `_nl_closer`.
  2. An invariant that ASSERTS an existential has to be ESTABLISHED at the
     step that makes it true, and the witnesses are the two loop counters
     -- nothing in the goal points at them. `lower_loop`'s pre-existing
     one-level heuristic (`exact <lo, by grind>`, the range's lower
     endpoint) does not reach it. Hence the witness cascade, generalized
     to the invariant's own existential depth and to every Int name in
     scope as a candidate.
  3. `simp_all` SUCCEEDS WITHOUT CLOSING. `first` then stops at it, the
     goal reaches the end of the proof unsolved, Lean records `sorryAx`,
     and verifiers/lean.py demotes the file -- which is honest, and also
     exactly the wrong answer for a goal a later alternative proves.
     `; done` turns it back into a closing tactic. The same bug was then
     found in `_closer()`'s own bare `simp` alternative, on the twin's
     certificate, and fixed the same way -- that one predates this wave
     and was latent: it needs a goal `decide` cannot reduce (a well-
     founded-recursive `{name}_t`) and a `simp` that makes partial
     progress, which a nested-loop twin's certificate is the first shape
     here to produce.

AND ONE THING `first` COULD NOT DO, which is worth its own line because it
is not a tactic weakness but an elaborator rule: an error inside a NESTED
`by` is RECOVERED (logged, the term completed with `sorryAx`), not raised
as a tactic failure. `_enum`'s one-alternative-per-enumerated-value
dispatch is built out of `exact absurd h (by ...)` terms, so `first` sees
the FIRST alternative succeed on every branch and never reaches the
others. Measured on has_duplicate's own twin at s=[0,1]: the j=0 branch's
refutation (its false conjunct is `0 < 0`) was applied to the j=1 branch,
where the false conjunct is the other one. The fix is not to make `first`
backtrack -- it cannot -- but to give every branch a branch-INDEPENDENT
first shot inside a single `by` over leaf tactics, where `first` does
backtrack honestly: `_refute`'s `and` case now tries `self._closer()` on
the whole ground conjunction before decomposing it, and `decide` refutes
`0 < 1 and [0,1][0]! = [0,1][1]!` outright. STILL OPEN, named: an
enumerated branch whose ground body `_closer()` cannot refute, and whose
own alternative is not the first one, is still swallowed. Nothing in the
committed corpus reaches it, and the honest cost when something does is a
lost certificate (unproved), never a false REFUTED."""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                                 # noqa: E402
import interp                                  # noqa: E402
import names                                   # noqa: E402
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
# SPEC.md "The string library (v1)" (2026-09-11): the 17 members, JSON
# op name to the prelude function term() calls; STRLIB_LEMMAS names the
# theorems emit_strlib_helpers() proves once, always offered to grind
# alongside the sfun list (self.ga) whenever any member is used, exactly
# the way seq_thms are named lemmas offered per-task above.
STRLIB_OPS = {"split", "join", "tostr", "count", "find", "strip", "lstrip",
             "rstrip", "replace", "lower", "upper", "isdigit", "isalpha",
             "isupper", "islower", "startswith", "endswith"}
STRLIB_LEMMAS = ["t_str_count_elem_step", "t_str_count_elem_nonneg",
                 "t_str_take_succ_toNat",
                 "t_str_split_sep_ne_nil", "t_str_join_cons_row",
                 "t_str_join_nil_row", "t_str_join_split_roundtrip"]
# word_count.json's own committed shape (a full-length slice standing in
# for the body's own copy of s, SPEC.md's own words): closing `t2 = s`
# needs these two core simp facts by name, grind's default set does not
# fire them on the `.drop 0.take (len - 0)` shape unprompted (measured).
STRLIB_GRIND_EXTRA = ["List.drop_zero", "List.take_length",
                     "t_str_count", "t_str_count_elem"]
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
MAX_NL_WITNESS_ALTS = 24  # 2026-09-18 (ROADMAP WS-20 move 1): the cap on
                  # existential-witness candidate tuples tried per goal on
                  # the nested/multiple-loop path (`_nl_closer`). Each is a
                  # `refine ... <;> grind` inside a `first`, so a wrong one
                  # costs a failed elaboration and nothing else; the cap is
                  # there so a loop with four Int names in scope and a
                  # three-deep existential cannot turn one goal into 64
                  # grind calls. Past it the goal honestly reads unproved.
MAX_UNDEF_UNROLL = 256   # 2026-09-14 (lean-cert): the concrete unroll cap
                  # for `_cert_undefined_loop`'s while-body replay, matching
                  # lower_framac.py's own `MAX_CERT_STMTS` -- a witness
                  # needing more concrete iterations than this to reach its
                  # own Undef honestly abstains (returns None) rather than
                  # building an ever-larger certificate term.


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


def _has_call(x, op_name: str, arity: int | None = None) -> bool:
    """True iff `x` contains an Expr node `{"op": op_name, "args": [...]}`
    with exactly `arity` args (any arity when None). `_has(x, "op", o)`
    (the `Lower` method below) cannot tell split(s) (1 arg, whitespace
    runs) from split(s, c) (2 args, one separator code point) apart --
    one JSON op name, two arities per SPEC.md's own words -- so this
    free function (2026-09-11, fz_p_str_splitempty/fz_p_str_tab's own
    grind-hint gap) adds the arity check `__init__`'s ga_names needs to
    tell them apart."""
    if isinstance(x, dict):
        if x.get("op") == op_name and (
                arity is None or len(x.get("args", [])) == arity):
            return True
        return any(_has_call(v, op_name, arity) for v in x.values())
    if isinstance(x, list):
        return any(_has_call(v, op_name, arity) for v in x)
    return False


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


def _count_whiles(x) -> int:
    """Every `while` anywhere in a statement tree (2026-09-18, ROADMAP
    WS-20 move 1). `lower()` dispatches on this rather than on the old
    top-level-only scan: a loop nested inside the single top-level loop is
    invisible to that scan, which is why has_duplicate's abstain came from
    `sym` with a different message than `lower`'s own."""
    if isinstance(x, dict):
        return ((1 if "while" in x else 0)
                + sum(_count_whiles(v) for v in x.values()))
    if isinstance(x, list):
        return sum(_count_whiles(v) for v in x)
    return 0


# DIVISOR-BOUND LEMMA (2026-09-12, ROADMAP 16.2, lean's own item): dafny-
# synthesis isNonPrime (3) and isPrime (605) trial-divide `n` only up to
# `n div 2` (`cond: i <= n div 2`) while their own `ensures` quantifies the
# divisor over the WIDER range `[2, n)` -- a fact no stated invariant
# supplies is the number-theory lemma this family needs at the loop's exit:
# any `k` with `2 <= k < n` and `n % k == 0` satisfies `k <= n / 2` (`n ==
# k * q`, `q >= 2` since `k < n` rules out `q <= 1`, so `n >= 2*k`).
# `_divisor_bound_target` is PORTED VERBATIM from lower_fstar.py's own
# function of the same name (2026-09-11) -- pure Python over the task/AST
# dicts, zero fstar-specific code, so lean, fstar and verus all recognize
# the identical shape from the identical detector; only the LEMMA TEXT each
# kernel emits differs. See `_divisor_bound_lean_defs` (in class Lower,
# `emit_seq_helpers`'s neighbor) and `lower_loop`'s own injection point
# (`invs.append`, right after `invs = w.get("invariants", [])`) for how
# lean uses the match: as an ORDINARY EXTRA loop invariant (`i <= n/2 +
# 1`), proved through the SAME per-invariant entry/preservation machinery
# every stated invariant already gets (never assumed), and a direct
# `exact` of `t_divisor_bound_<task>` at the loop-spec's own exit branch,
# replacing nothing a stated invariant already covers.
def _divisor_bound_target(task: dict, w: dict) -> dict | None:
    ret = task["returns"][0]["name"]
    for en in task.get("ensures", []):
        found = _result_eq_quant(en, ret)
        if found is None:
            continue
        kind, q = found
        rel = _quant_mod_relop(q.get("body"))
        if rel is None:
            continue
        dividend, _kname, relop = rel
        lo = q.get("lo")
        if lo is None:
            continue
        for iv in w.get("invariants", []):
            ifound = _result_eq_quant(iv, ret)
            if ifound is None:
                continue
            ikind, iq = ifound
            if ikind != kind or iq.get("lo") != lo:
                continue
            irel = _quant_mod_relop(iq.get("body"))
            if irel is None or irel[0] != dividend or irel[2] != relop:
                continue
            ihi = iq.get("hi")
            if not (isinstance(ihi, dict) and list(ihi.keys()) == ["var"]):
                continue
            i_name = ihi["var"]
            want_cond = {"op": "<=", "args": [
                {"var": i_name},
                {"op": "div", "args": [dividend, {"int": 2}]}]}
            if w.get("cond") != want_cond:
                continue
            return {"kind": kind, "relop": relop, "dividend": dividend,
                    "lo": lo, "i_name": i_name, "result": ret,
                    "inv_index": w["invariants"].index(iv)}
    return None


def _quant_mod_relop(body):
    """`body` is `(N % k) RELOP 0` (RELOP one of "=="/"!="); returns
    `(N, k_name, RELOP)` or None. `k` must appear bare (`{"var": k}`),
    never a compound expression, matching every task this targets."""
    if not (isinstance(body, dict) and body.get("op") in ("==", "!=")):
        return None
    args = body.get("args")
    if not (isinstance(args, list) and len(args) == 2):
        return None
    lhs, rhs = args
    if rhs != {"int": 0}:
        return None
    if not (isinstance(lhs, dict) and lhs.get("op") == "mod"):
        return None
    largs = lhs.get("args")
    if not (isinstance(largs, list) and len(largs) == 2):
        return None
    dividend, kexpr = largs
    if not (isinstance(kexpr, dict) and list(kexpr.keys()) == ["var"]):
        return None
    return dividend, kexpr["var"], body["op"]


def _result_eq_quant(e, ret: str):
    """`e` is `result == Quant(...)`; returns `(kind, quant_dict)` for
    kind in {"forall","exists"}, or None."""
    if not (isinstance(e, dict) and e.get("op") == "=="):
        return None
    args = e.get("args")
    if not (isinstance(args, list) and len(args) == 2):
        return None
    a, b = args
    if a == {"var": ret}:
        quant_holder = b
    elif b == {"var": ret}:
        quant_holder = a
    else:
        return None
    for kind in ("forall", "exists"):
        if kind in quant_holder:
            return kind, quant_holder[kind]
    return None


def _var_writes(body: list, v: str) -> list:
    """Every RHS expression assigned to `v` anywhere in `body`, top-level or
    nested inside an `if`/`while` (walked the same shape as `loop_assigned`
    above, but collecting values rather than a name set): used by
    `_loop_needs_domain_hyp`'s own "SELF-DIVISION SAFE CASE" to see the
    WHOLE update picture for `v`, not just a top-level one, so a second,
    conditional write hiding inside an `if` cannot slip past the single-
    write check that safe case relies on. A `return` naming `v` counts as
    a write too (SPEC.md "Early exit"), with no RHS expression of the
    `x op lit` shape this is looking for, so it can only ever make the
    caller's `len(writes) == 1` check fail, never wrongly pass."""
    out: list = []
    for s in body:
        if "assign" in s and s["assign"][0] == v:
            out.append(s["assign"][1])
        elif "return" in s and s["return"][0] == v:
            out.append(None)
        elif "if" in s:
            out += _var_writes(s["if"]["then"], v)
            out += _var_writes(s["if"]["else"], v)
        elif "while" in s:
            out += _var_writes(s["while"]["body"], v)
    return out


def _calls_any_named(x, names: set) -> bool:
    """True if `x` contains a `call` node whose `fun` is in `names`,
    anywhere (walked the same generic shape as `_var_writes`/
    `_self_calls_named`). Used only by `_sfun_under_quantifier` below,
    to look inside one `forall`/`exists` body for a spec_fun call."""
    if isinstance(x, dict):
        if "call" in x and isinstance(x["call"], dict) \
                and x["call"].get("fun") in names:
            return True
        return any(_calls_any_named(v, names) for v in x.values())
    if isinstance(x, list):
        return any(_calls_any_named(v, names) for v in x)
    return False


def _sfun_under_quantifier(x, names: set) -> bool:
    """2026-09-14 (lean-closure): True if `x` contains a `forall`/
    `exists` node whose own body calls one of `names` (the task's
    spec_funs) -- the closure-predicate-in-a-loop-invariant shape
    (`__init__`'s `sfun_quantified`, gating `_grind_base`'s deterministic
    `simp only` unfold instead of handing grind the spec_fun's equation
    as a raw E-match hint). Walks the whole tree (requires/ensures/
    invariants/body alike), not just invariants, since a spec_fun this
    task calls under a quantifier ANYWHERE has the same E-matching cost
    once it reaches grind's hint list for that theorem."""
    if isinstance(x, dict):
        for key in ("forall", "exists"):
            if key in x and isinstance(x[key], dict):
                qbody = x[key].get("body")
                if qbody is not None and _calls_any_named(qbody, names):
                    return True
        return any(_sfun_under_quantifier(v, names) for v in x.values())
    if isinstance(x, list):
        return any(_sfun_under_quantifier(v, names) for v in x)
    return False


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
        # NESTED AND MULTIPLE LOOPS (2026-09-18, ROADMAP WS-20 move 1):
        # all inert unless `lower_loops_general` (below) turns the path on.
        # `_nl_active` is what `sym`'s own `while` case reads, and it is
        # turned back OFF the moment the body walk finishes, so anything
        # that re-walks a body afterwards (a certificate replay) meets the
        # same honest NotImplementedError it met before this wave rather
        # than emitting a loop function into nowhere.
        self._nl_active = False
        self._nl_used = False
        self._nl_out: list[str] = []
        self._nl_thms: list = []
        self._nl_info: dict = {}
        self._nl_names: dict = {}
        self._nl_fn_names: list[str] = []
        self._nl_scope: list = []
        self._nl_local_decls: list = []
        self._nl_ctx: list = []
        self._nl_pending: list[str] = []
        self._nl_binder_names: set = set()
        self._nl_cand_names: list[str] = []
        self._nl_pnames = ""
        self._nl_wf_k = 0
        # SPEC.md "The string library (v1)" (2026-09-11): does this task
        # (spec or body, real or twin) call any of the 17 members. Gates
        # emit_strlib_helpers() below and the grind hint list, exactly
        # parallel to seq_mut/seq_new above -- False for every task that
        # predates this construct, so nothing about their output changes.
        self.strlib = (self._has_any(task, STRLIB_OPS)
                       or self._has_any(body, STRLIB_OPS))
        sfun_ga_names = [f"{f}_s" for f in self.sfuns]
        ga_names = list(sfun_ga_names)
        if self.strlib:
            # Only the lemmas this task's own ops can need: an unrelated
            # lemma in grind's hint set is not just dead weight, it is
            # more E-matching patterns competing during search, measured
            # (count_vowels) to push grind into a case-split explosion
            # over the loop body's five-vowel `if` alone -- narrowing
            # this list task by task is what closes it.
            has_op = lambda o: (self._has(task, "op", o)
                                or self._has(body, "op", o))
            has_split_ws = (_has_call(task, "split", 1)
                           or _has_call(body, "split", 1))
            if has_op("count") or has_op("split") or has_op("join"):
                ga_names += ["t_str_count", "t_str_count_elem"]
            if has_op("split") or has_op("join"):
                ga_names += ["t_str_split_sep_ne_nil",
                            "t_str_join_cons_row", "t_str_join_nil_row",
                            "t_str_join_split_roundtrip"]
            if has_split_ws:
                # split(s), the 1-arg whitespace-run arity (SPEC.md "The
                # string library (v1)"): measured 2026-09-11,
                # fz_p_str_splitempty/fz_p_str_tab, grind unfolds the
                # calling task's own `def` (its E-matching equation is
                # always in scope) but never reaches INTO
                # t_str_split_ws's own `let`-bound fold without its name
                # named here too -- the same reason t_str_count/
                # t_str_count_elem are named above for the count/join
                # arities, extended to the arity `has_op("split")` alone
                # does not distinguish from split(s, c).
                ga_names += ["t_str_split_ws"]
            if has_op("find"):
                # find(s, t) (SPEC.md "The string library (v1)"):
                # measured 2026-09-11, fz_p_str_findempty, the same gap
                # as split_ws just above -- t_str_find's own `if
                # t.isEmpty then 0 else ...` never unfolds under grind
                # without its name in the hint list.
                ga_names += ["t_str_find", "t_str_find_go"]
            if has_op("lower"):
                # lower(s) (SPEC.md "The string library (v1)"): measured
                # 2026-09-11, fz_p_str_lowernonletter, the same gap --
                # t_str_lower's own `.map` never unfolds under grind
                # without its name (and the letter-range predicate it
                # calls per element) in the hint list.
                ga_names += ["t_str_lower", "t_str_isupperletter"]
            if has_op("upper"):
                ga_names += ["t_str_upper", "t_str_islowerletter"]
            ga_names += ["List.drop_zero", "List.take_length"]
        self.ga = "" if not ga_names else " [" + ", ".join(ga_names) + "]"
        # THE CLOSURE-PREDICATE TIMEOUT (2026-09-14, lean-closure, this
        # session's own item): `self.ga`, handed to `grind` as an
        # E-matching hint, is fine for a spec_fun's OWN definedness
        # theorem and any non-quantified use, but a spec_fun cited
        # inside a `forall`/`exists` (isEven/isOdd/isNegative-style
        # closure predicates over a loop's own invariant, dafny_synthesis
        # 412/426/436/554/629's shared shape: `forall k, isEven(x[k]) <->
        # exists j, ...`) makes `grind [isEven_s]` search whether to
        # unfold `isEven_s` at every quantifier instantiation combined
        # with the invariant list's own case splits -- measured (`lean
        # -DmaxHeartbeats=400000` on the emitted file, `set_option
        # trace.grind.ematch true`) to exhaust the WHOLE per-command
        # heartbeat budget on the very first `first | ...` alternative
        # (a `deterministic timeout` is not a normal tactic failure:
        # `first` never gets a turn to try the next branch, so real and
        # twin both read TIMEOUT). `ga_wo_sfuns` strips the spec_fun
        # names back out for exactly this shape; `_grind_base()` below
        # cites each one's own equation as a DETERMINISTIC `simp only`
        # rewrite first instead (rewrites every call, including ones
        # under a binder, with no E-matching search at all), so grind
        # itself never has to consider unfolding it.
        other_ga_names = [n for n in ga_names if n not in sfun_ga_names]
        self.ga_wo_sfuns = ("" if not other_ga_names else
                            " [" + ", ".join(other_ga_names) + "]")
        self.sfun_names_ga = sfun_ga_names
        self.sfun_quantified = bool(self.sfuns) and (
            _sfun_under_quantifier(task, set(self.sfuns))
            or _sfun_under_quantifier(body, set(self.sfuns)))
        # SPEC.md "Sequences as values" (2026-09-09): does this lowering
        # (task spec, or the body actually being lowered, real or twin)
        # touch `update`/`fill` anywhere. Gates the seq helper lemmas and
        # the grind-only fallback below; False for every pre-existing
        # task, so nothing about their output changes.
        self.seq_mut = (self._has(task, "op", "update")
                        or self._has(task, "op", "fill")
                        or self._has(body, "op", "update")
                        or self._has(body, "op", "fill"))
        # SPEC.md "Sequences: literals, concatenation, slices (v1)"
        # (2026-09-09): does this lowering touch a seq literal, a slice, or
        # a `+` that concatenates two seqs (as opposed to adding two ints --
        # `+` is polymorphic by operand type, exactly as `==` already is).
        # Gates the append/slice helper lemmas below and their grind-only
        # fallback, parallel to `seq_mut` above; False for every task that
        # predates this construct, so nothing about their output changes.
        self.seq_new = (self._has(task, "op", "seq")
                        or self._has(task, "op", "slice")
                        or self._has(body, "op", "seq")
                        or self._has(body, "op", "slice")
                        or self._has_seq_plus(task, dict(self.types))
                        or self._has_seq_plus(body, dict(self.types)))
        # SPEC.md "Nested sequences (v1)" (2026-09-10): does this task
        # declare `{"seq": "seq"}` anywhere (a param, return, local, or
        # spec_fun type). No new Expr form marks the construct -- every
        # operator is polymorphic by its operands' STATIC TYPE, unlike
        # seq_mut/seq_new above, which key off an AST op -- so detection
        # here is by type shape, not by op. Gates the row-typed bridge
        # lemmas below (`t_seq_update_get_row` etc.); False for every task
        # that predates this construct, so nothing about their output
        # changes.
        self.nested = self._has_nested_type(task) or self._has_nested_type(body)
        # BOOLEANS AS COMPUTATIONAL VALUES (2026-09-10): does THIS body
        # compute a seq-sorted `==`/`!=` anywhere in computational
        # position (`_stmts_have_seq_eq_comp` above) -- gates emitting
        # `t_seq_ext` (list extensionality, the one bridge a seq equality
        # rendered as `decide (s = t)` needs that plain
        # `decide_eq_true_eq` does not, measured on fz_v1nested_026/
        # fz_p_nest_eq) and naming it in the grind-only fallback. False
        # for every task that predates this construct (none reaches
        # term()'s new ==/!=/CMP_OPS/and/or/not case at all, since that
        # case did not exist), so nothing about their output changes.
        self.seq_eq_comp = (
            self._stmts_have_seq_eq_comp(body, self.types)
            or any(self._prop_has_seq_eq(e, self.types)
                  for e in task.get("ensures", [])))
        # THE FRAME-FACT GAP's own open list (2026-09-11, ROADMAP 16.2):
        # `t_seq_update_get`/`t_seq_append_get`/`t_seq_slice_get` above
        # are each stated for exactly ONE level of their own operation --
        # a read after `.set`, after `++`, after a slice -- and `grind`
        # cannot CHAIN two of them across a nested subterm (measured:
        # swapFirstAndLast's own `(a.set i1 v1).set i2 v2` needs the
        # OUTER `.set`'s bridge, then the INNER `.set`'s, at the SAME
        # index; splitArray's/splitAndAppend's own `firstPart ++
        # secondPart` (both slices) needs the append bridge THEN,
        # per-branch, the slice bridge). Fixed the way `_mul_sign_pairs`
        # above fixes the analogous grind limitation: not by asking grind
        # to chain, but by emitting ONE lemma per composed SHAPE, proved
        # once from the single-level bridges (`t_seq_update2_get`/
        # `t_seq_append_slice2_get`, `emit_seq_helpers` below), fully
        # GENERIC in its own universally-quantified base/index/bound
        # variables (unlike `_mul_sign_pairs`'s per-task lemmas, whose
        # STATEMENT depends on the task's own `requires`) -- so detection
        # here only needs to answer whether the SHAPE occurs at all, not
        # extract its concrete operands; grind's own e-matching (already
        # relied on for the single-level bridges) unifies the universal
        # lemma against the goal's own concrete nested term in ONE step,
        # never needing to chain.
        self.seq_composed_update2 = self._has_seq_update_chain()
        self.seq_composed_append_slice = self._has_seq_append_of_slice(
            [body, task.get("ensures", [])], dict(self.types))
        # DIVISOR-BOUND LEMMA (2026-09-12, ROADMAP 16.2, lean's own item):
        # computed HERE, at __init__ time, not inside `lower_loop` --
        # `lower()`'s own `emit_seq_helpers()` call (which needs to know
        # whether to emit `t_divisor_bound_{name}`) runs BEFORE
        # `lower_loop` does, so the plan must exist before either reads
        # it. `_divisor_bound_target` (module level, ported verbatim from
        # lower_fstar.py) needs the loop's own `while` dict, found the
        # same way `lower_loop` finds it; `None` for every SIMPLE/
        # RECURSIVE-shape task (no `while` in `body` at all) and every
        # LOOP-shape task whose ensures/invariants do not match the
        # trial-divide-to-half family (every one of the 34 committed
        # tasks and the other 17 of this wave's own target set).
        self._divisor_bound_plan = None
        self._divisor_bound_inv_idx = None
        self._divisor_bound_bound_idx = None
        _w = next((s["while"] for s in body if "while" in s), None)
        if _w is not None:
            _plan = _divisor_bound_target(task, _w)
            if (_plan is not None
                    and _plan["i_name"] in loop_assigned(_w["body"])):
                self._divisor_bound_plan = _plan
                self._divisor_bound_inv_idx = _plan["inv_index"] + 1
                self._divisor_bound_bound_idx = (
                    len(_w.get("invariants", [])) + 1)

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
        if op == "+":
            # SPEC.md "Sequences: literals, concatenation, slices (v1)":
            # `+` is polymorphic by operand type exactly as `==` already
            # is (two ints, two bools, two seqs) -- told apart by the
            # first operand's own sort. SPEC.md "Nested sequences (v1)"
            # extends this one more level: two nested seqs concatenate to
            # a nested seq, so the operand's own sort (int, "seq", or the
            # nested {"seq": "seq"} dict) is returned as-is rather than
            # collapsed to the bare string "seq".
            s0 = self.sort(e["args"][0], types)
            return s0 if self._is_seqsort(s0) else "int"
        if op in ARITH_OPS or op in DIV_MOD or op == "neg":
            return "int"
        if op == "len":
            return "int"
        if op == "at":
            # SPEC.md "Nested sequences (v1)": `s[i]` is a row (itself a
            # "seq") when `s` is nested, an int when `s` is flat -- `at`
            # is polymorphic by ITS OWN operand's static type, exactly as
            # `+`/`==` already are. No new Expr form for `s[i][j]`: it is
            # `at(at(s, i), j)`, the outer `at`'s operand being the inner
            # `at`'s "seq"-sorted result, so the outer call's own sort
            # comes back "int" for free.
            s0 = self.sort(e["args"][0], types)
            return "seq" if isinstance(s0, dict) and "seq" in s0 else "int"
        if op in ("update", "slice"):
            # SPEC.md "Nested sequences (v1)": `update`/`slice` return the
            # SAME container type as their first argument, nested or flat
            # (a row replaced by a row is still a matrix; a slice of rows
            # is still a matrix), exactly as `+` above.
            return self.sort(e["args"][0], types)
        if op == "fill":
            # `fill(n, r)`: n copies of the SECOND argument, so the result
            # is nested iff the copied value is itself a seq (a row) --
            # symmetric with the "seq" literal case just below.
            v0 = self.sort(e["args"][1], types)
            return {"seq": "seq"} if self._is_seqsort(v0) else "seq"
        if op == "seq":
            # The literal `[e1, ..., en]`: nested iff its own elements are
            # seqs. An empty literal `[]` has no element to inspect --
            # SPEC.md's "the declared type says so" needs a context this
            # bottom-up function does not carry, so this defaults to flat,
            # exactly the pre-nested behaviour: observationally unchanged
            # for every task that predates this construct, and neither
            # committed nested task (`swap_rows`, `row_max_len`) uses this
            # op at all, so the default is never exercised by them either.
            args = e.get("args", [])
            if args and self._is_seqsort(self.sort(args[0], types)):
                return {"seq": "seq"}
            return "seq"
        if op == "pair":
            # SPEC.md "Pairs" (2026-09-10): the sort of `(e1, e2)` is the
            # pair type built from its own operands' sorts, in the same
            # `{"pair": [T1, T2]}` shape every task/local type already
            # carries, so a pair-typed `var` (types[name] is this same
            # dict) and a freshly-built `pair` node compare equal.
            return {"pair": [self.sort(e["args"][0], types),
                             self.sort(e["args"][1], types)]}
        if op in ("fst", "snd"):
            # p.0 / p.1: project the pair sort built above (or carried by
            # a pair-typed var/return/local) back down to one component.
            t = self.sort(e["args"][0], types)
            return t["pair"][0 if op == "fst" else 1]
        if op in ("split", "strip", "lstrip", "rstrip", "replace", "lower",
                  "upper"):
            # SPEC.md "The string library (v1)" (2026-09-11): `split(s)`/
            # `split(s,c)` both return a row of strings (`seq<seq>`, the
            # nested-seq dict, one op two arities per SPEC.md's own
            # words); every other member here returns a flat seq, its
            # argument's own sort.
            return {"seq": "seq"} if op == "split" else "seq"
        if op in ("tostr", "join"):
            return "seq"
        if op in ("count", "find"):
            return "int"
        if op in ("isdigit", "isalpha", "isupper", "islower", "startswith",
                  "endswith"):
            return "bool"
        return "bool"

    @staticmethod
    def _is_seqsort(s) -> bool:
        """True iff `s` (a sort() result) denotes some seq -- the flat
        string "seq" or the nested {"seq": "seq"} dict (SPEC.md "Nested
        sequences (v1)"). Distinguishes a seq-shaped sort from a pair's
        {"pair": [...]} dict, which carries no "seq" key, so a pair is
        never mistaken for a seq by this check."""
        return s == "seq" or (isinstance(s, dict) and "seq" in s)

    # BOOLEANS AS COMPUTATIONAL VALUES (2026-09-10): does `e`, reached
    # exactly the way term()'s new unified ==/!=/CMP_OPS/and/or/not case
    # reaches it, contain a seq-sorted `==`/`!=` anywhere in its boolean
    # structure -- the one shape (measured on fz_v1nested_026/fz_p_nest_eq)
    # needing a bridge lemma beyond plain grind, since Lean's native `=`
    # decides seq equality STRUCTURALLY while this file's own ensures
    # clauses (SPEC.md's "equal lengths and equal elements at every
    # index") state it ELEMENTWISE: `decide (s = t) = true` needs list
    # EXTENSIONALITY, not just the `decide_eq_true_eq` unwrap every other
    # operator here closes with. Descends exactly term()'s own boolean
    # control flow (`ite` branches, `call` args, and/or/not, stopping at
    # CMP_OPS/arithmetic/`at`/etc., which cannot contain a further
    # boolean subtree here) so a seq `==` sitting in an `if`-COND or a
    # spec clause (prop()-rendered, plain `=`, no `decide`, needing no
    # extensionality bridge at all) is never mistaken for one in term
    # position.
    def _term_bool_has_seq_eq(self, e: dict, types: dict) -> bool:
        if "ite" in e:
            c = e["ite"]
            return (self._term_bool_has_seq_eq(c["then"], types)
                    or self._term_bool_has_seq_eq(c["else"], types))
        if "call" in e:
            return any(self._term_bool_has_seq_eq(a, types)
                       for a in e["call"]["args"])
        if "op" not in e:
            return False
        op = e["op"]
        if op in ("and", "or"):
            return any(self._term_bool_has_seq_eq(a, types)
                       for a in e["args"])
        if op == "not":
            return self._term_bool_has_seq_eq(e["args"][0], types)
        if op in ("==", "!="):
            return self._is_seqsort(self.sort(e["args"][0], types))
        return False

    def _stmts_have_seq_eq_comp(self, stmts: list, types: dict) -> bool:
        """Walks `stmts` the way sym()/to_expr do, checking every genuinely
        computational-position expression (assign/return/var-init, both
        arms of every if, a while body) via `_term_bool_has_seq_eq` above;
        an if/while's own COND is never visited (prop-position, needs no
        bridge). types tracks local `var` declarations only enough for
        sort() to answer correctly, mirroring sym()'s own bookkeeping."""
        types = dict(types)
        for s in stmts:
            if "assign" in s:
                if self._term_bool_has_seq_eq(s["assign"][1], types):
                    return True
            elif "return" in s:
                if self._term_bool_has_seq_eq(s["return"][1], types):
                    return True
            elif "var" in s:
                d = s["var"]
                types[d["name"]] = d["type"]
                if self._term_bool_has_seq_eq(d["init"], types):
                    return True
            elif "if" in s:
                c = s["if"]
                if (self._stmts_have_seq_eq_comp(c["then"], types)
                        or self._stmts_have_seq_eq_comp(c["else"], types)):
                    return True
            elif "while" in s:
                if self._stmts_have_seq_eq_comp(s["while"]["body"], types):
                    return True
        return False

    def _prop_has_seq_eq(self, e: dict, types: dict) -> bool:
        """Does `e` (an `ensures`/invariant clause, PROP position) itself
        state a seq-sorted `==`/`!=` (under and/or/not/implies) -- 2026-
        09-11, fz_p_seqeq_true: the docstring above `_term_bool_has_seq_eq`
        argues a prop-position seq equality "needs no extensionality
        bridge at all" because it renders as plain `l1 = l2`, decided by
        grind's own structural/congruence reasoning once l1/l2's own
        CONSTRUCTION is in scope (true for a straight-line body, where
        the return value's shape is a literal grind can unfold). It is
        NOT true after a loop: the postcondition's `r = s` is proved from
        the loop's own invariant (a length fact plus a pointwise
        `getElem!` quantifier) with r and s both OPAQUE variables, no
        construction to unfold -- exactly `t_seq_ext`'s own signature,
        which `self.seq_eq_comp` below must therefore also offer even
        though the equality sits in `ensures`, never in the body's own
        computational position `_term_bool_has_seq_eq` scans."""
        if "op" not in e:
            return False
        op = e["op"]
        if op in ("==", "!="):
            return self._is_seqsort(self.sort(e["args"][0], types))
        if op in ("and", "or", "implies"):
            return any(self._prop_has_seq_eq(a, types) for a in e["args"])
        if op == "not":
            return self._prop_has_seq_eq(e["args"][0], types)
        return False

    # ---------- expressions ----------

    def term(self, e: dict, env: dict, types: dict, dep: bool = False,
             expect=None) -> str:
        """Computational (term-level) lowering. `env` substitutes names;
        `dep` makes ite dependent (named hypothesis) so nested requires /
        termination proofs see the branch condition. `expect` (2026-09-11,
        fz_p_nest_empty) is the assignment/return site's own declared
        type, threaded down from to_expr's tail return/assign/var cases
        and through `ite`'s branches below -- the ONLY consumer is the
        empty seq literal `[]` case further down, whose own sort has no
        element to inspect (see its comment); every other branch ignores
        it, so passing None everywhere else is unobservable."""
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
            t = self.term(c["then"], env, types, dep, expect)
            f = self.term(c["else"], env, types, dep, expect)
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
        if op == "seq":
            # SPEC.md "Sequences: literals, concatenation, slices (v1)":
            # `[e1, ..., en]`, n >= 0, `[]` the empty seq; a plain Lean
            # list literal, total type ascription so `[]` elaborates.
            # SPEC.md "Nested sequences (v1)": ascribe `List (List Int)`
            # when the literal's own elements are seqs -- sort() decides
            # this the same way, bottom-up from the first element. An
            # empty literal `[]` has no element to inspect, so SPEC.md's
            # own resolution ("the declared type says so") falls to
            # `expect`, the assignment/return site's type, threaded down
            # from to_expr's tail cases above (2026-09-11,
            # fz_p_nest_empty: `returns r : seq<seq>` + `r := []` lowered
            # `([] : List Int)` before this, a type error against the
            # nested prelude helpers in the same file).
            args = e.get("args", [])
            elems = ", ".join(self.term(a, env, types, dep) for a in args)
            if args:
                nested = self._is_seqsort(self.sort(args[0], types))
            else:
                nested = isinstance(expect, dict) and "seq" in expect
            ty = "List (List Int)" if nested else "List Int"
            return f"([{elems}] : {ty})"
        if op == "slice":
            # `s[a..b]`: `List.take`/`List.drop` composed, per SPEC.md's
            # own suggested encoding (measured over `List.extract`: the
            # pinned Lean's `List.extract` is `take (stop-start) (drop
            # start l)` with no dedicated length/getElem simp lemmas of
            # its own, so it buys nothing `.drop`/`.take` don't already
            # have); definedness (`0 <= a <= b <= len s`) is a separate
            # obligation in dcond(), not enforced here.
            s = self.term(e["args"][0], env, types, dep)
            a = self.term(e["args"][1], env, types, dep)
            b = self.term(e["args"][2], env, types, dep)
            return f"(({s}.drop ({a}).toNat).take (({b} - {a}).toNat))"
        if op == "pair":
            # SPEC.md "Pairs" (2026-09-10): `(a, b)`, Lean's own pair
            # constructor over the product `T1 × T2` (`lean_type` below
            # builds `×` for exactly this pair type); always defined once
            # both components are (dcond's generic per-argument fallback
            # already gives this, no new dcond case needed).
            a, b = (self.term(x, env, types, dep) for x in e["args"])
            return f"({a}, {b})"
        if op in ("fst", "snd"):
            # p.0 / p.1: Prod.fst/Prod.snd, spelled `.1`/`.2` on the
            # pair term (SPEC.md "Pairs": "lean `Int × Int` with `.1`
            # and `.2`"); always defined on a pair, so no obligation.
            p = self.term(e["args"][0], env, types, dep)
            return f"({p}.{'1' if op == 'fst' else '2'})"
        if op == "split":
            # SPEC.md "The string library (v1)": `split(s)` (whitespace
            # runs) and `split(s, c)` (one code point, empties kept), two
            # arities of one op, exactly as the JSON op comment states.
            s = self.term(e["args"][0], env, types, dep)
            if len(e["args"]) == 1:
                return f"(t_str_split_ws {s})"
            c = self.term(e["args"][1], env, types, dep)
            return f"(t_str_split_sep {s} {c})"
        if op == "join":
            rows = self.term(e["args"][0], env, types, dep)
            sep = self.term(e["args"][1], env, types, dep)
            return f"(t_str_join {rows} {sep})"
        if op == "tostr":
            return f"(t_str_tostr {self.term(e['args'][0], env, types, dep)})"
        if op == "count":
            s = self.term(e["args"][0], env, types, dep)
            t = self.term(e["args"][1], env, types, dep)
            return f"(t_str_count {s} {t})"
        if op == "find":
            s = self.term(e["args"][0], env, types, dep)
            t = self.term(e["args"][1], env, types, dep)
            return f"(t_str_find {s} {t})"
        if op in ("strip", "lstrip", "rstrip"):
            s = self.term(e["args"][0], env, types, dep)
            fn = {"strip": "t_str_strip", "lstrip": "t_str_lstrip",
                 "rstrip": "t_str_rstrip"}[op]
            return f"({fn} {s})"
        if op == "replace":
            s = self.term(e["args"][0], env, types, dep)
            t = self.term(e["args"][1], env, types, dep)
            u = self.term(e["args"][2], env, types, dep)
            return f"(t_str_replace {s} {t} {u})"
        if op in ("lower", "upper"):
            s = self.term(e["args"][0], env, types, dep)
            return f"({'t_str_lower' if op == 'lower' else 't_str_upper'} {s})"
        if op in ("isdigit", "isalpha", "isupper", "islower"):
            # Bool-valued members: the prelude function already returns
            # Lean `Bool` natively (SPEC.md: "each total"), so no
            # `decide` bridge is needed here -- unlike the generic
            # ==/CMP_OPS/and/or/not case below, which bridges a Prop to
            # Bool, this is already a Bool-returning function call.
            s = self.term(e["args"][0], env, types, dep)
            return f"(t_str_{op} {s})"
        if op in ("startswith", "endswith"):
            s = self.term(e["args"][0], env, types, dep)
            t = self.term(e["args"][1], env, types, dep)
            return f"(t_str_{op} {s} {t})"
        if op == "neg":
            return f"(-{self.term(e['args'][0], env, types, dep)})"
        if op == "+" and self._is_seqsort(self.sort(e["args"][0], types)):
            # `+` on two seqs (flat or nested, SPEC.md "Nested sequences
            # (v1)"): concatenation, always defined, polymorphic by
            # operand type exactly as `==` already is; `++` needs no
            # nested-specific text, since Lean's own `List.append` is
            # already generic in the element type.
            a, b = (self.term(x, env, types, dep) for x in e["args"])
            return f"({a} ++ {b})"
        if op in ARITH_OPS:
            a, b = (self.term(x, env, types, dep) for x in e["args"])
            return f"({a} {op} {b})"
        if op in DIV_MOD:
            a, b = (self.term(x, env, types, dep) for x in e["args"])
            return f"({a} {DIV_MOD[op]} {b})"
        if op == "/":
            # fz_p_nodiv (surface.py's own REFUSALS entry, SPEC.md's
            # notation section, 2026-09-11 note above DIV_MOD): the bare
            # slash token is surface NOTATION for `div`, never a JSON op
            # name itself. Left to the generic fallback below, it fell
            # through to the "boolean operator ... is not lowered for
            # lean" NotImplementedError, which run_par.py's dispatch
            # classifies ABSTAIN, not LOWER-ERROR -- every other kernel
            # (lower_dafny.py, lower_verus.py, lower_spark.py,
            # lower_framac.py, lower_rocq.py) raises ValueError here
            # instead, which the same dispatch classifies LOWER-ERROR;
            # matching that so the lowering REJECTS the token rather
            # than abstaining on it.
            raise ValueError(f"t has no operator {op!r}")
        if op in ("==", "!=") or op in CMP_OPS or op in ("and", "or", "not"):
            # BOOLEANS AS COMPUTATIONAL VALUES (2026-09-10): a
            # comparison/equality/logical op reaching term() (as opposed
            # to prop(), which already renders every one of these as a
            # Prop) means the AST needs a Lean Bool VALUE here, not a
            # formula -- an assign/return/call-arg whose source is `a ==
            # b`, `a < b`, `p and q`, etc. `prop()` already renders the
            # identical node as a decidable Prop for every sort this
            # reaches (int, bool, seq, nested seq all carry computable
            # `Decidable` instances in core Lean: Int's linear order and
            # DecidableEq, List/List (List Int)'s structural DecidableEq,
            # Bool's own DecidableEq), so `decide` bridges Prop -> Bool
            # uniformly, one line for every operator, no per-sort code.
            return f"(decide {self.prop(e, env, types)})"
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
        if op in ("fst", "snd"):
            # SPEC.md "Pairs" (2026-09-10), spec-position addendum
            # (2026-09-09): a BOOL-sorted pair component reaching this
            # function directly -- a whole ensures/requires/invariant
            # clause that IS `p.fst`/`p.snd`, or one operand of an
            # `==`/`!=`/`implies`/`and`/`or`/`ite` above whose sort()
            # came back "bool" -- has no logical CONNECTIVE of its own
            # to recurse into: like `call` just above (and `var`
            # earlier), it names a computed bool VALUE, not a formula,
            # so the same generic `(term = true)` bridge closes it.
            # `term()` already lowers `fst`/`snd` to `.1`/`.2` (the
            # 2026-09-10 note's ENCODING section), so no new term-level
            # code is needed here, only this one spec-position case.
            assert self.sort(e, types) == "bool", f"non-bool {op} as Prop"
            return f"({self.term(e, env, types)} = true)"
        if op in ("isdigit", "isalpha", "isupper", "islower", "startswith",
                  "endswith"):
            # SPEC.md "The string library (v1)": the four predicates and
            # startswith/endswith are bool-valued members reaching prop()
            # directly (a whole clause, or one operand of ==/implies/
            # and/or above whose sort() came back "bool") -- the same
            # generic `(term = true)` bridge the `fst`/`snd` case above
            # already uses for a computed bool value with no logical
            # connective of its own.
            return f"({self.term(e, env, types)} = true)"
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
        if op == "slice":
            # SPEC.md: `s[a..b]` DEFINED IFF `0 <= a <= b <= len(s)`, a
            # definedness obligation exactly like `at`'s `0 <= i < len`.
            # `+` (seq concatenation) and `seq` (the literal) need no
            # obligation of their own beyond their arguments' -- "always
            # defined" / "defined iff all its elements are" -- so both
            # fall through to the generic per-argument case at the bottom.
            s, a, b = e["args"]
            at_ = self.term(a, env, types)
            bt = self.term(b, env, types)
            ln = f"((({self.term(s, env, types)}).length : Int))"
            return self._conj([
                self.dcond(s, env, types), self.dcond(a, env, types),
                self.dcond(b, env, types),
                f"(((0 : Int) ≤ {at_}) ∧ ({at_} ≤ {bt}) ∧ ({bt} ≤ {ln}))"])
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
            keys: list[str], returned: str = "False",
            in_branch: bool = False) -> tuple[dict, list, str]:
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
                if self._nl_active:
                    self._nl_local_decls.append((d["name"], d["type"]))
                obs.append(guard(self.dcond(d["init"], env, types)))
                env[d["name"]] = self.term(d["init"], env, types)
            elif "if" in s:
                c = s["if"]
                obs.append(guard(self.dcond(c["cond"], env, types)))
                cp = self.prop(c["cond"], env, types)
                # NESTED AND MULTIPLE LOOPS (2026-09-18): a `var`
                # declared inside a branch is scoped to that branch, so
                # the running scope list a nested loop reads is truncated
                # back after both arms -- otherwise a later top-level
                # loop would take a binder for a name that does not
                # exist at its own call site.
                mark = len(self._nl_local_decls)
                env_t, obs_t, ret_t = self.sym(c["then"], env, types, keys,
                                               returned, in_branch=True)
                env_e, obs_e, ret_e = self.sym(c["else"], env, types, keys,
                                               returned, in_branch=True)
                del self._nl_local_decls[mark:]
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
                # NESTED AND MULTIPLE LOOPS (2026-09-18, ROADMAP WS-20
                # move 1): `_nl_active` is set only by
                # `lower_loops_general` below, and only for the shapes
                # that used to reach this `raise` -- a single top-level
                # loop still goes through `lower_loop` with this path
                # switched off, so its output is byte-identical. The two
                # guards below are abstains, not silent fall-throughs:
                # a loop inside a branch would need its path condition
                # carried into the loop's own context and its tuple
                # merged at the join, and a loop after an early `return`
                # would need the return's path condition threaded into
                # the loop's state -- neither is built, and guessing at
                # either risks a wrong verdict, which this file never
                # trades for coverage.
                if not self._nl_active:
                    raise NotImplementedError(
                        "nested / multiple loops are not lowered for lean")
                if in_branch:
                    raise NotImplementedError(
                        "a loop inside a branch is not lowered for lean")
                if returned != "False":
                    raise NotImplementedError(
                        "a loop after an early `return` is not lowered "
                        "for lean")
                env.update(self._nested_loop(s["while"], env, types))
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
        branch only (handled by the two one-sided cases below).

        THE DEAD-BRANCH RESIDUAL (2026-09-10, "sole blockers" wave): a
        branch that assigns nothing keeps the return variable's value
        from BEFORE the branch (plain fall-through, e.g. Dafny's `if b {
        c := x }` with no `else` at all, lifted as an explicit empty
        `else: []`), and statements after an if whose branches both
        merely continue (neither ends in `return`) pick up from the
        MERGED state, not from a fork this function refuses. Both are
        handled below rather than raised."""
        if not stmts:
            # `env[self.ret]` is exactly that prior value: every earlier
            # assign/var-init on this path already substituted it in (the
            # "assign"/"var" cases below), so a branch with nothing of
            # its own to add just reads it back, no new term, no new
            # obligation. Only a path where self.ret was NEVER assigned
            # at all before this empty branch has nothing to fall back
            # to -- a genuine gap, and stays the honest abstain.
            if self.ret in env:
                return env[self.ret], []
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
                obs = ([ob0] if ob0 else []) \
                    + [f"({cp} → {o})" for o in obs_t] \
                    + [f"(¬{cp} → {o})" for o in obs_e]
                return (
                    f"(if {self.fresh_hyp()} : {cp} then {te} else {fe})",
                    obs)
            if else_ret and not then_ret:
                te, obs_t = self.to_expr(list(c["then"]) + rest, env, types)
                fe, obs_e = self.to_expr(c["else"], env, types)
                obs = ([ob0] if ob0 else []) \
                    + [f"({cp} → {o})" for o in obs_t] \
                    + [f"(¬{cp} → {o})" for o in obs_e]
                return (
                    f"(if {self.fresh_hyp()} : {cp} then {te} else {fe})",
                    obs)
            if not then_ret and not else_ret:
                # THE DEAD-BRANCH RESIDUAL (2026-09-10): neither branch
                # returns, so both continue into `rest` from the MERGED
                # state. `sym()` already builds exactly this join (per-
                # variable `if cp then .. else ..`, obligations guarded by
                # cp/¬cp) for a loop body's own nested ifs; reused as-is
                # here for a loop-free one. Its `returned` tracking is
                # strictly more general than this function's own
                # then_ret/else_ret split (a branch CAN contain a nested
                # if where one arm returns and the other doesn't, without
                # the OUTER branch itself always-returning), so this also
                # covers cases the two one-sided branches above do not.
                env_t, obs_t, _ = self.sym(c["then"], env, types, [])
                env_e, obs_e, _ = self.sym(c["else"], env, types, [])
                merged = dict(env)
                for k in set(env_t) | set(env_e):
                    t, f = env_t.get(k, k), env_e.get(k, k)
                    merged[k] = t if t == f else \
                        f"(if {cp} then {t} else {f})"
                obs = ([ob0] if ob0 else []) \
                    + [f"({cp} → {o})" for o in obs_t] \
                    + [f"(¬{cp} → {o})" for o in obs_e]
                re_, obs_r = self.to_expr(rest, merged, types)
                return re_, obs + obs_r
            raise NotImplementedError(
                "statements after a branch are not lowered for lean")
        if "return" in s:
            x, e = s["return"]
            if x != self.ret:
                raise NotImplementedError(
                    f"return assigns {x!r}, not the return")
            ob = self.dcond(e, env, types)
            t = self.term(e, env, types, dep=True, expect=self.rett)
            return t, ([ob] if ob else [])
        if "assign" in s:
            x, e = s["assign"]
            ob = self.dcond(e, env, types)
            obs = [ob] if ob else []
            if not rest:
                if x != self.ret:
                    raise NotImplementedError(
                        f"body path ends assigning {x!r}, not the return")
                return self.term(e, env, types, dep=True,
                                 expect=types.get(x, self.rett)), obs
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
            t = self.term(e, env, types, dep=True, expect=types.get(x))
            env2 = dict(env)
            env2[x] = t
            re_, obs_r = self.to_expr(rest, env2, types)
            return re_, obs + obs_r
        if "var" in s:
            d = s["var"]
            types[d["name"]] = d["type"]
            ob = self.dcond(d["init"], env, types)
            t = self.term(d["init"], env, types, dep=True, expect=d["type"])
            env2 = dict(env)
            env2[d["name"]] = t
            re_, obs_r = self.to_expr(rest, env2, types)
            return re_, ([ob] if ob else []) + obs_r
        raise NotImplementedError(
            "statements after a branch are not lowered for lean")

    # ---------- shared pieces ----------

    def lean_type(self, t) -> str:
        if isinstance(t, dict):
            if "pair" in t:
                # SPEC.md "Pairs" (2026-09-10): `{"pair": [T1, T2]}` over
                # Int/Bool/List Int, as the Lean product `T1 × T2`
                # (SPEC.md's own choice of encoding, "lean `Int × Int`");
                # each of T1, T2 is always a base type here (no pair of
                # pairs, SPEC.md v1), so this does not recurse past one
                # level.
                t1, t2 = t["pair"]
                return f"({self.lean_type(t1)} × {self.lean_type(t2)})"
            # SPEC.md "Nested sequences (v1)": `{"seq": "seq"}`, a seq of
            # seqs of ints, one level (`t["seq"]` is always the literal
            # string "seq", v1 has no third level), as `List (List Int)`
            # -- SPEC.md's own choice of encoding for lean; this does not
            # recurse past one level either, exactly like the pair branch
            # above.
            return "List (List Int)"
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

    def _has_any(self, x, ops: set) -> bool:
        """True if some `op` node in x has op in `ops` (SPEC.md "The
        string library (v1)"'s 17 members, checked as a set rather than
        one at a time)."""
        if isinstance(x, dict):
            if x.get("op") in ops:
                return True
            return any(self._has_any(v, ops) for v in x.values())
        if isinstance(x, list):
            return any(self._has_any(v, ops) for v in x)
        return False

    # THE NONLINEAR SIGN BRIDGE (2026-09-11, ROADMAP 16.2, lean's
    # `_seq_composed*`/`_mul_sign_*` trio -- this member): centered
    # HexagonalNumber's own `result == 3*n*(n-1)+1` with only `n >= 0`
    # in `requires` needs `(3*n)*(n-1) >= 0`, plain nonlinear sign
    # reasoning `grind`'s linear cutsat core cannot do and core Lean has
    # no `nlinarith` for (measured: identical shape to "THE CUBE
    # NONLINEARITY" above, `_nonneg_bridge_lines`'s own loop-scoped
    # bridge, but that one only fires inside a loop's invariant-
    # preservation proof over LOOP STATE variables raised to a fixed
    # power of itself -- this is a non-loop SIMPLE task, and the two
    # factors are DIFFERENT expressions (`3*n` and `n - 1`), not one
    # variable against its own square/cube). GENERIC, not task-specific:
    # `_mul_sign_pairs` below walks `ensures` and the body looking for
    # any `*` node whose BOTH operands mention a variable (so `3 * n`
    # itself, one literal operand, is excluded -- linear, `omega` already
    # has it) and renders each such pair's two operands to the identical
    # Lean text `term()` already produces for them (same `env={}`, same
    # `types`), so the emitted lemma's statement is syntactically the
    # SAME atom the goal already contains, not a re-derivation grind has
    # to match up on its own.
    def _has_var(self, x) -> bool:
        if isinstance(x, dict):
            if "var" in x:
                return True
            return any(self._has_var(v) for v in x.values())
        if isinstance(x, list):
            return any(self._has_var(v) for v in x)
        return False

    # REGRESSION, remainder/divmod_pair (2026-09-11, caught by this task's
    # own regression check against 34/34 before the guard below): `x ==
    # x / y * y + r` (remainder's own Euclidean-law ensures) contains a
    # `*` node, `(x / y) * y`, with a variable on BOTH sides -- exactly
    # what `_has_var` alone flags -- but `(x/y)*y` is NOT always `>= 0`
    # (measured: the emitted `_mul_sign_1` lemma's own `exfalso; omega`
    # leaf failed outright, `sorryAx`-tainted, x=1 y=2 a live
    # counterexample to that BRANCH, not to the task), and a lemma whose
    # OWN proof fails poisons the whole file's audit (VACUOUS/UNPROVED)
    # even though the real wfbody/spec theorems below it still close on
    # their own -- ROADMAP 16.2's own honesty rule (never let an added
    # fact regress an already-passing task) means this needs a real
    # fix, not a narrower one-task patch. `_is_plain_int_arith` restricts
    # both factors to the sort this bridge's own proof strategy is sound
    # for -- plain integer arithmetic built from vars/literals/+/-/*
    # only, no `/`, `%`, indexing, or calls -- since the CASE-SPLIT
    # closing tactic's `exfalso; omega` leaves depend on nothing beyond
    # linear facts about the two factors themselves; a factor built from
    # `/`/`%` can be sign-INDEPENDENT of the ambient `requires` the way a
    # bare affine variable expression never is, so this is a genuine
    # scope restriction, not a workaround.
    # REGRESSION #2, cubeVolume/multiply/triangularPrismVolume/
    # tetrahedralNumber (2026-09-11, caught by grading the FULL 74-task
    # set the assignment named, not just the 34 committed -- the earlier
    # guard above only fixed remainder's own shape): `_is_plain_int_arith`
    # alone still let `(size * size) * size` (cubeVolume's own body, no
    # `>= 0`/`<= 0` ANYWHERE in its ensures -- pure equality restatement,
    # needing no sign bridge at all) collect the pair `(size * size,
    # size)`, and the emitted lemma's `exfalso; omega` leaf failed
    # (`sorryAx`-tainted) because `size * size` is itself NONLINEAR --
    # omega has no idea how it relates in sign to `size` alone (measured:
    # "a possible counterexample ... a := size, b := size * size"). Two
    # independent fixes, both needed: (1) `_is_affine` (below) replaces
    # `_is_plain_int_arith`, EXCLUDING `*` from what a factor may itself
    # contain -- a factor must be a plain affine combination of vars and
    # literals, the exact shape the case-split's own `exfalso; omega`
    # leaves are actually linear-arithmetic decidable over; (2) detection
    # no longer scans `ensures`/body UNCONDITIONALLY -- it only fires for
    # a product that is the (or resolves, through the ensures-named
    # variable's own straight-line body assignment, to the) operand of an
    # actual `>=`/`<=`/`>`/`<` comparison against the literal `0` in
    # `ensures` (`_sign_compare_operands`) -- cubeVolume's own ensures is
    # equality-only, so this now finds NO comparison target at all,
    # matching its prior (already-passing) behavior byte-for-byte: no
    # lemma, no branch, unchanged tactic text.
    def _is_affine(self, x) -> bool:
        """True iff `x` is a plain AFFINE integer expression: vars,
        literals, +/-, and `*` only where at least one side is var-free
        (a literal scalar) -- `3 * n` (centeredHexagonalNumber's own
        factor) qualifies, `size * size` (cubeVolume's own inner factor,
        REGRESSION #2) does not, since omega has no theory relating a
        squared/product atom's sign to its own base variable. This is
        the exact boundary the case-split's `exfalso; omega` leaves are
        sound over: every hypothesis they discharge is linear once both
        `_mul_sign_pairs` factors are affine in this sense."""
        if isinstance(x, dict):
            if "var" in x or "int" in x:
                return True
            if x.get("op") in ("+", "-") and isinstance(
                    x.get("args"), list):
                return all(self._is_affine(a) for a in x["args"])
            if (x.get("op") == "*" and isinstance(x.get("args"), list)
                    and len(x["args"]) == 2):
                a, b = x["args"]
                return ((not self._has_var(a) and self._is_affine(b))
                        or (not self._has_var(b) and self._is_affine(a)))
            return False
        return False

    def _collect_sign_targets(self, x, out: list) -> None:
        if isinstance(x, dict):
            if (x.get("op") in (">=", "<=", ">", "<")
                    and isinstance(x.get("args"), list)
                    and len(x["args"]) == 2):
                a, b = x["args"]
                if isinstance(a, dict) and a.get("int") == 0:
                    out.append(b)
                elif isinstance(b, dict) and b.get("int") == 0:
                    out.append(a)
            for v in x.values():
                self._collect_sign_targets(v, out)
        elif isinstance(x, list):
            for v in x:
                self._collect_sign_targets(v, out)

    def _resolve_to_body_expr(self, node):
        """A bare `{"var": name}` sign-compare operand, resolved to
        NAME's own most recent straight-line `assign` in `self.body`
        (SIMPLE-shape bodies only, this bridge's current scope) -- the
        actual formula the `>= 0`/`<= 0` ensures clause is really about,
        since `ensures` itself only ever names the return variable, never
        restates its defining expression. Any other node shape (already
        a formula, not a bare var) is returned unchanged."""
        if isinstance(node, dict) and "var" in node \
                and isinstance(self.body, list):
            name = node["var"]
            found = None
            for s in self.body:
                if (isinstance(s, dict) and "assign" in s
                        and isinstance(s["assign"], list)
                        and s["assign"][0] == name):
                    found = s["assign"][1]
            if found is not None:
                return found
        return node

    def _collect_mul_pairs(self, x, types: dict, out: list,
                           seen: set) -> None:
        if isinstance(x, dict):
            if (x.get("op") == "*" and isinstance(x.get("args"), list)
                    and len(x["args"]) == 2):
                a, b = x["args"]
                if (self._has_var(a) and self._has_var(b)
                        and self._is_affine(a) and self._is_affine(b)):
                    try:
                        ta = self.term(a, {}, types)
                        tb = self.term(b, {}, types)
                    except (KeyError, IndexError):
                        ta = tb = None
                    if ta is not None and (ta, tb) not in seen:
                        seen.add((ta, tb))
                        out.append((ta, tb))
            for v in x.values():
                self._collect_mul_pairs(v, types, out, seen)
        elif isinstance(x, list):
            for v in x:
                self._collect_mul_pairs(v, types, out, seen)

    def _mul_sign_pairs(self) -> list:
        """Every distinct (A, B) affine factor-text pair this task's
        `ensures` computes a nonlinear product of, restricted to a
        product that actually feeds a `>= 0`/`<= 0`/`> 0`/`< 0` ensures
        comparison (`_sign_compare_operands`, resolved through the body
        when the compared operand is a bare return variable). Order-
        stable (first occurrence) so emitted lemma names are
        deterministic across runs -- ROADMAP 16.2's own regression-check
        discipline needs byte-identical output for an unchanged task."""
        targets: list = []
        for e in self.task.get("ensures", []):
            self._collect_sign_targets(e, targets)
        out: list = []
        seen: set = set()
        for t in targets:
            resolved = self._resolve_to_body_expr(t)
            self._collect_mul_pairs(resolved, self.types, out, seen)
        return out

    def _mul_sign_lemma(self, name: str, a_text: str, b_text: str) -> str:
        """One generic-STRATEGY, task-hypothesis-SPECIFIC theorem:
        `0 <= (a_text) * (b_text)` from this task's own `requires` (the
        `pb`/`hpre` binders every other top-level theorem here already
        uses). The case split itself never inspects a_text/b_text beyond
        treating them as opaque `Int`s -- generic over ANY two factors --
        but the theorem's own STATEMENT is task-specific (params, hpre),
        because whether the mixed-sign branches are even reachable
        depends on the task's own `requires`, not on the factors alone.
        Zero-first ordering matters (measured, probe1/probe2 scratch
        files, lean 4.33.1, core only): checking `a_text = 0` /
        `b_text = 0` before the strict-sign split disposes of the
        boundary where one factor is exactly zero via `simp` alone
        (`Int.zero_mul`/`Int.mul_zero`, both in the default simp set),
        so the four strict-sign leaves below are only ever reached with
        BOTH factors nonzero, and a genuinely-infeasible mixed-sign leaf
        (the only way the goal is true and this task's own `requires`
        support it at all) closes on `exfalso; omega` from the ambient
        linear hypotheses alone -- never a hand proof of the product
        itself. `Int.mul_pos`/`Int.mul_nonneg`/
        `Int.mul_nonneg_of_nonpos_of_nonpos` are all core Lean (measured,
        no Mathlib import), the same discipline "THE CUBE NONLINEARITY"
        above already established for `Int.mul_nonneg` alone."""
        pb = self.binders([(p["name"], p["type"])
                           for p in self.task["params"]])
        hpre = (f" (hpre : {self.pre_conj()})"
               if self.task.get("requires") else "")
        return (
            f"theorem {name} {pb}{hpre} :\n"
            f"    (0 : Int) ≤ ({a_text}) * ({b_text}) := by\n"
            f"  by_cases hA0 : ({a_text}) = 0\n"
            f"  · rw [hA0]; simp\n"
            f"  · by_cases hB0 : ({b_text}) = 0\n"
            f"    · rw [hB0]; simp\n"
            f"    · by_cases hAp : (0 : Int) < ({a_text})\n"
            f"      · by_cases hBp : (0 : Int) < ({b_text})\n"
            f"        · exact Int.le_of_lt (Int.mul_pos hAp hBp)\n"
            f"        · exfalso; omega\n"
            f"      · by_cases hBp : (0 : Int) < ({b_text})\n"
            f"        · exfalso; omega\n"
            f"        · exact Int.mul_nonneg_of_nonpos_of_nonpos "
            f"(by omega) (by omega)\n")

    def _has_seq_update_chain(self) -> bool:
        """True iff some top-level local (SIMPLE-shape body, `self.body`
        a flat statement list -- a loop's own internal update chain, if
        any, is not covered here, named open rather than silently
        folded in) is assigned `update(itself, ..., ...)` at least
        TWICE in sequence, e.g. `a_out := update(a_out, i1, v1)`
        immediately or later followed by `a_out := update(a_out, i2,
        v2)` -- swapFirstAndLast's own exact shape, both committed
        variants (task_id_591 and task_id_625). The composition this
        detects is invisible in the raw JSON as a single nested node
        (each assign is its own flat `update` call); it only becomes a
        nested Lean term through this file's own symbolic substitution
        (`sym`/`to_expr` inlining the prior value), so detection here
        counts REPEATED self-updates of the same variable instead of
        looking for a nested AST shape that never exists in the source."""
        if not isinstance(self.body, list):
            return False
        counts: dict = {}
        for s in self.body:
            if not (isinstance(s, dict) and "assign" in s):
                continue
            tgt, val = s["assign"]
            if (isinstance(val, dict) and val.get("op") == "update"
                    and isinstance(val.get("args"), list)
                    and len(val["args"]) == 3
                    and isinstance(val["args"][0], dict)
                    and val["args"][0].get("var") == tgt):
                counts[tgt] = counts.get(tgt, 0) + 1
        return any(c >= 2 for c in counts.values())

    def _has_seq_append_of_slice(self, x, types: dict) -> bool:
        """True iff some `+` (seq concat) node's operand, resolved
        through a local variable's LAST straight-line binding (a `var`
        declaration's own `init`, or a later `assign` to that same name,
        whichever comes last in `self.body` -- SIMPLE-shape bodies only,
        every task this targets), is itself a `slice` node, OR a `fst`/
        `snd` projection of a name whose own last binding is a `pair`
        node built from two such names. Both committed occurrences
        (task_id_262, task_id_586) have BOTH `+` operands resolve to a
        slice; an asymmetric append (one bare seq, one slice) is not
        covered here -- `t_seq_append_get`'s own single-level bridge
        already handles the bare side, so an asymmetric append only
        needs `t_seq_append_slice2_get` if BOTH sides need the slice
        bridge, which this check requires of neither operand alone --
        named open rather than silently folded in if a future task needs
        it.

        DECLARE-THEN-REASSIGN (2026-09-12, ROADMAP 16.2, lean's own
        item): splitArray (task_id_262) declares `firstPart`/
        `secondPart` as `var {init: seq(), ...}` (an empty seq literal)
        and only ASSIGNS the actual slice to them in a later statement --
        the ORIGINAL version of this method read only each `var` node's
        own `init`, so `local_init["firstPart"]` stayed the empty-seq
        literal forever and the slice assignment was never seen at all.
        Fixed by walking `self.body` in order and letting a later
        `assign` to a name OVERWRITE its `local_init` entry, matching
        the SIMPLE-shape straight-line semantics every other detector in
        this file already assumes (no branches, no loops, so the LAST
        write before use is the only live one). splitArray's own `+`
        node, additionally, is not `firstPart + secondPart` (that
        `walk()` would already find) but `r.fst ++ r.snd` in its
        ENSURES, where `r` was assigned `pair(firstPart, secondPart)` --
        so `resolve()` below also unwraps a `fst`/`snd` node through a
        resolved `pair`, and the caller now walks `ensures` as well as
        `body` (`x` is a list of roots, not `self.body` alone)."""
        local_init: dict = {}
        if isinstance(self.body, list):
            for s in self.body:
                if isinstance(s, dict) and "var" in s \
                        and isinstance(s["var"], dict):
                    v = s["var"]
                    if "init" in v and "name" in v:
                        local_init[v["name"]] = v["init"]
                elif isinstance(s, dict) and "assign" in s \
                        and isinstance(s["assign"], list) \
                        and len(s["assign"]) == 2:
                    tgt, val = s["assign"]
                    if isinstance(tgt, str):
                        local_init[tgt] = val

        def resolve(node, depth: int = 0):
            if depth > 4 or not isinstance(node, dict):
                return node
            if "var" in node and isinstance(node["var"], str) \
                    and node["var"] in local_init:
                return resolve(local_init[node["var"]], depth + 1)
            if node.get("op") in ("fst", "snd") \
                    and isinstance(node.get("args"), list) \
                    and len(node["args"]) == 1:
                base = resolve(node["args"][0], depth + 1)
                if (isinstance(base, dict) and base.get("op") == "pair"
                        and isinstance(base.get("args"), list)
                        and len(base["args"]) == 2):
                    idx = 0 if node["op"] == "fst" else 1
                    return resolve(base["args"][idx], depth + 1)
            return node

        def walk(n) -> bool:
            if isinstance(n, dict):
                if (n.get("op") == "+" and isinstance(n.get("args"), list)
                        and len(n["args"]) == 2):
                    a = resolve(n["args"][0])
                    b = resolve(n["args"][1])
                    if ((isinstance(a, dict) and a.get("op") == "slice")
                            or (isinstance(b, dict)
                                and b.get("op") == "slice")):
                        return True
                return any(walk(v) for v in n.values())
            if isinstance(n, list):
                return any(walk(v) for v in n)
            return False

        return walk(x)

    def _has_seq_plus(self, x, types: dict) -> bool:
        """True if some `+` node in x concatenates two seqs (its first
        operand's sort is `seq`, `+` polymorphic by operand type exactly
        as `==` already is). Best-effort at __init__ time: `types` is only
        params + the return (local `var` declarations are not tracked
        here), but every task whose `+` concatenates a local-only seq var
        also carries a `seq`/`slice`/`update`/`fill` node somewhere in the
        same task, which `seq_new`'s other checks already catch, so the
        under-approximation here costs nothing observable. A malformed or
        untyped subterm (self.sort raising) is skipped, not fatal, since
        this only decides whether to emit an unused helper lemma."""
        if isinstance(x, dict):
            if x.get("op") == "+":
                try:
                    if self.sort(x["args"][0], types) == "seq":
                        return True
                except (KeyError, IndexError):
                    pass
            return any(self._has_seq_plus(v, types) for v in x.values())
        if isinstance(x, list):
            return any(self._has_seq_plus(v, types) for v in x)
        return False

    @staticmethod
    def _has_nested_type(x) -> bool:
        """True iff `{"seq": "seq"}` (SPEC.md "Nested sequences (v1)")
        appears anywhere in `x` as a TYPE (a param, return, local `var`,
        or spec_fun type). Safe to check the dict shape alone: no AST
        node in this file's JSON ever uses "seq" as a dict KEY -- the
        literal/at/len/etc. Expr nodes are `{"op": "seq", ...}`, a
        different shape entirely, so this can never mistake an operator
        node for a type."""
        if isinstance(x, dict):
            if x.get("seq") == "seq":
                return True
            return any(Lower._has_nested_type(v) for v in x.values())
        if isinstance(x, list):
            return any(Lower._has_nested_type(v) for v in x)
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
        appears (or will appear, post-unfold) in that goal.

        A div/mod under a `forall`/`exists` (SPEC.md "Sequences: literals,
        concatenation, slices (v1)", measured 2026-09-09 on clover_rotate's
        own ensures, `a[(i+offset) mod len(a)]` inside a bound-`i` forall)
        is skipped rather than walked: `env`/`types` here are the OUTER
        clause's, so the bound variable has no entry (`self.sort` on it
        raised `KeyError` before this fix), and even given one, a `have`
        line built from it would sit before any `intro` of the quantifier
        in the tactic script this feeds (`divmod_prelude`), naming a
        variable not yet in scope -- unsound to hoist regardless. Whether
        `grind` alone still closes a quantified div/mod goal is measured
        per task, not assumed here."""
        seen: set = set()
        out: list = []

        def walk(x):
            if isinstance(x, dict):
                if "forall" in x or "exists" in x:
                    return
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

    # A div/mod bridge (`divmod_pairs`/`divmod_prelude`) is a `have`
    # sequence: it only typechecks once every name it mentions is
    # actually in the local context. Two ways that can fail, both
    # measured 2026-09-09 (third sweep) on clover_rotate's own residual:
    #   quantified   a div/mod reachable only inside a `forall`'s body
    #                (`b[i] == a[(i+offset) mod len(a)]`) needs the bound
    #                variable introduced first; `divmod_pairs`'s own walk
    #                (above) deliberately skips into a forall/exists
    #                rather than crash on its missing type (or, worse,
    #                emit a `have` naming a variable not yet in scope).
    #                `intro` does not care what display name the goal's
    #                own binder carries, so a fixed local name works.
    #   chained      a WF theorem's goal is `H1 -> H2 -> ... -> G` (earlier
    #                requires/ensures clauses, or a loop's invariants,
    #                chained as hypotheses); the divisor's own `b ≠ 0` side
    #                condition (rotate's is `len(a) ≠ 0`, from the SAME
    #                chain, e.g. `i_v < len(a)`) is unreachable by
    #                `assumption`/`omega` until that chain is introduced,
    #                even when the div/mod itself is not quantified at all
    #                (measured on rotate's own wf3, "definedness of the
    #                loop body": the bridge alone left `_h9 : len(a) ≠ 0`
    #                unproved with an empty context).
    # Neither call site threads the leading chain's length through, so
    # both branches below are tried under a guessed `intro` prefix,
    # 0..MAX_LEAD throwaway names, one candidate per guess: a wrong guess
    # either leaves a `have` unable to typecheck against a still
    # arrow-headed goal, or `intro` runs out of binders outright, so
    # `first` just falls through to the next guess, never masking a
    # genuine failure as a proof. `nlead=0` reproduces the exact prior
    # (un-prefixed) text, so any task whose bridge already worked without
    # a leading chain succeeds on the very first candidate, unchanged.
    MAX_LEAD = 8

    def _quant_pairs(self, e, env: dict, types: dict,
                     depth: int = 0) -> list[tuple[str, str, str, list]]:
        """Every bare top-level `forall` reachable in `e` (descending only
        through `and`, the one combinator measured wrapping a quantified
        invariant alongside a plain one, getEven's own invariant 2) whose
        body reaches a div/mod op, as `(bound_name, lo_hyp, hi_hyp,
        pairs)`.

        THE MULTI-CLAUSE ENSURES GAP (2026-09-12, ROADMAP 16.2, lean's
        own item, splitAndAppend's own residual): `_divmod_branches`'s
        caller at `lower_simple`'s own `_t_spec` site passes `nodes =
        [self.task["ensures"], self.body]` -- `self.task["ensures"]`
        ITSELF a Python list of clauses (one length equality, one
        `forall` with the mod), not a single Expr dict. Before this
        fix, `for n in nodes: quants += self._quant_pairs(n, ...)` called
        this method with `n` bound to that WHOLE LIST as `e`, and the
        `isinstance(e, dict)` guard below returned `[]` immediately --
        so a SIMPLE-shape task's `_t_spec` theorem never saw its own
        ensures-level quantified div/mod at all (only a clause-level
        `_t_wf{k}` theorem, built from `_close([e], ...)` with `e` the
        single clause already unwrapped, ever exercised this path,
        which is why splitAndAppend's own `_wf1` DOES carry the mod
        bridge while its `_spec` theorem, needing the SAME bridge
        alongside the seq structural one, never got it). Fixed by
        descending into a plain list the same way `divmod_pairs`'s own
        walk and `_has_divmod` already do elsewhere in this file: each
        element is its own top-level candidate, `depth` reset to the
        caller's own value for every one (matching how the existing
        `for n in nodes` loop already calls this method once per node
        at `depth=0`), so a multi-clause ensures list now contributes
        every one of its own quantified clauses instead of none."""
        if isinstance(e, list):
            out = []
            for item in e:
                out += self._quant_pairs(item, env, types, depth)
            return out
        if not isinstance(e, dict):
            return []
        if "forall" in e:
            q = e["forall"]
            if not self._has_divmod(q["body"]):
                return []
            zn, zlo, zhi = f"_qz{depth}", f"_qzlo{depth}", f"_qzhi{depth}"
            env2 = {**env, q["var"]: zn}
            types2 = {**types, q["var"]: "int"}
            pairs = self.divmod_pairs([q["body"]], env2, types2)
            return [(zn, zlo, zhi, pairs)] if pairs else []
        if e.get("op") == "and":
            out = []
            for a in e.get("args", []):
                out += self._quant_pairs(a, env, types, depth + 1)
            return out
        return []

    @staticmethod
    def _has_divmod(x) -> bool:
        if isinstance(x, dict):
            if x.get("op") in DIV_MOD:
                return True
            return any(Lower._has_divmod(v) for v in x.values())
        if isinstance(x, list):
            return any(Lower._has_divmod(v) for v in x)
        return False

    def _divmod_branches(self, nodes: list, env: dict,
                         types: dict) -> list[str]:
        """`first`-alternatives closing a div/mod obligation reachable in
        `nodes`. The free-standing (non-quantified) bridge alone, exactly
        the pre-2026-09-09-third-sweep text, is ALWAYS the first
        candidate (or the only one) -- every div/mod task lowered before
        today closed on it (or never reached it, `grind` alone already
        sufficing). Its `intro`-guessed CHAINED repeats (nlead > 0) are
        extra fallbacks added only when `self.seq_mut or self.seq_new`
        (gated the same way `_seq_hints` already is: the only task
        measured needing them, clover_rotate, is a seq task, and a
        non-seq div/mod task with a literal divisor -- digit_sum,
        remainder -- already closes at nlead=0, so gating keeps their
        text byte-identical).

        The QUANTIFIED variants (`_quant_pairs`) are UNGATED: a task with
        a div/mod reachable only inside a `forall` needs its bound
        variable `intro`'d before any bridge referencing it can even
        typecheck, in every column, seq or not. Reproducing the pre-fix
        `divmod_pairs` walk here would mean keeping its bug: measured on
        the ALREADY-COMMITTED first_even.lean and is_prime.lean, the old
        walk skipped past the quantifier without renaming, so the `have`
        it built cited the SOURCE variable name (`i`) as if free, which
        no theorem in either file ever binds -- dead code, latent since
        the 2026-09-08 "Division and modulo" wave, never exercised
        because plain `grind` already closed both goals on its own. This
        sweep's first fix (the crash on clover_rotate, `divmod_pairs`
        skipping into a forall/exists entirely) turned that silent bug
        into the honest absence it always should have been; leaving the
        REPLACEMENT (a working, intro'd bridge) ungated finishes the fix
        instead of reintroducing the old broken text under a new gate.
        The verdict is unchanged either way (`grind` alone still closes
        first_even's and is_prime's own goals first), so this is a
        tactic-text correction with no behavioural effect -- measured:
        `first_even.lean`/`is_prime.lean` now differ from the previously
        committed copies in exactly their trailing (never-reached)
        alternative text, both still COUNT, byte-identical everywhere
        else."""
        pairs = self.divmod_pairs(nodes, env, types)
        branches = []
        seq_gated = self.seq_mut or self.seq_new or self.seq_eq_comp
        if pairs:
            branches.append(f"({self.divmod_prelude(pairs)}; omega)")
            if seq_gated:
                branches.append(f"({self.divmod_prelude(pairs)}; "
                               f"grind only [{self._seq_hints()}])")
        quants = []
        for n in nodes:
            quants += self._quant_pairs(n, env, types)
        # UNGATED (2026-09-10, second pass, elementAtIndexAfterRotation):
        # was `if pairs and nlead and (self.seq_mut or self.seq_new)`,
        # matching `_seq_hints`'s own gate -- but the CHAINED case this
        # loop exists for ("a WF theorem's goal is H1 -> ... -> G, the
        # divisor's own b != 0 side condition unreachable until that
        # chain is introduced", this method's own docstring above) is not
        # a seq-specific shape at all: elementAtIndexAfterRotation's own
        # divisor is `len(l)`, a SIMPLE-shape `at` index with no seq
        # literal/slice/concat/update/fill anywhere in the task, so
        # `self.seq_mut`/`self.seq_new` both read False and the gate
        # skipped exactly the fallback this task needs, unmeasured until
        # now (`_wf1`'s own `_h1 : len(l) != 0` proved by `by first |
        # assumption | decide | omega | grind` against a goal that still
        # reads `H1 -> H2 -> H3 -> ...` un-intro'd -- omega alone cannot
        # reach `index < len(l)` to derive `len(l) >= 1` from a premise
        # it has not been given). Same reasoning the QUANTIFIED variant's
        # own ungating above already used: a wrong `nlead` guess just
        # leaves a `have` that cannot typecheck (or `intro` runs out of
        # binders), so `first` falls through, never masking failure as a
        # proof; every task whose bridge already worked at `nlead=0`
        # (digit_sum, remainder, swap, tail, filter_pos) succeeds on the
        # very first candidate exactly as before, unchanged verdict,
        # changed only in the never-reached trailing alternative text.
        # THE MOD-THEN-SEQ GAP (2026-09-12, ROADMAP 16.2, lean's own
        # item, splitAndAppend/appendArrayToSeq/replaceLastElement's own
        # residual): every branch above closes with `omega` alone, which
        # cannot see past an opaque `List.take`/`List.drop`/`++` atom --
        # fine for a task whose ONLY obligation is the div/mod fact
        # itself, but splitAndAppend's own `r[i]! = l[(i+n) mod
        # len(l)]!` needs the mod bridge (to pin down `(i+n) mod
        # len(l)`'s value) AND the seq structural bridge
        # (`t_seq_append_get`/`t_seq_slice_get`, to rewrite `r[i]!`
        # through the `++`/slice `r` unfolds to) IN THE SAME GOAL --
        # `omega` alone leaves the seq side untouched, and the seq-only
        # `grind only [...]` branch `_close` appends after this method
        # returns never sees the mod `have`s at all (a separate `first`
        # alternative, not composed with this one). Measured directly
        # (probe586c.lean, lean 4.33.1, core only): swapping the
        # closing `omega` for `grind only [<seq hints>]` on the
        # quantified branch -- `grind` still gets every `have` this
        # prelude put in local context, `only` restricts just its
        # GLOBAL lemma set -- closes the goal `omega` alone left
        # unclosed. Added as EXTRA fallback branches, gated the same way
        # `_seq_hints`/`_close`'s own seq branch already are
        # (`self.seq_mut or self.seq_new or self.seq_eq_comp`), appended
        # AFTER every existing `omega`-closed branch above so a task
        # whose bridge already worked keeps succeeding on its own prior
        # candidate, unchanged verdict, changed only in trailing
        # (previously unreached) alternative text.
        for nlead in range(self.MAX_LEAD + 1):
            lead = f"intro{' _' * nlead}; " if nlead else ""
            if pairs and nlead:
                branches.append(f"({lead}{self.divmod_prelude(pairs)}; "
                               f"omega)")
                if seq_gated:
                    branches.append(
                        f"({lead}{self.divmod_prelude(pairs)}; "
                        f"grind only [{self._seq_hints()}])")
            for zn, zlo, zhi, qpairs in quants:
                branches.append(
                    f"({lead}intro {zn} {zlo} {zhi}; "
                    f"{self.divmod_prelude(qpairs)}; omega)")
                if seq_gated:
                    branches.append(
                        f"({lead}intro {zn} {zlo} {zhi}; "
                        f"{self.divmod_prelude(qpairs)}; "
                        f"grind only [{self._seq_hints()}])")
        return branches

    def _seq_update2_script(self) -> str | None:
        """PER-SITE INDEX CODEGEN (2026-09-12, ROADMAP 16.2, lean's own
        item): wave I's builder measured that `grind only [t_seq_
        update2_get, ..._hi, ..._mid, ..._lo]` cites the composed lemma
        (its e-matching finds the concrete nested `.set`/`.set` term
        fine) but does not itself SPLIT the ite the general lemma's own
        conclusion carries, and its ONE reported hand fix (a `have` plus
        a case split plus `omega`, closing one concrete instance)
        generalizes to a SHAPE-driven script, not a per-task one: `None`
        unless `self.seq_composed_update2` is set (task_id_591/625's own
        gate, unchanged), in which case a tactic that (1) opens every
        conjunct/`forall` the spec goal's own top-level shape carries
        (`repeat'`, so it adapts to however many conjuncts THIS task's
        `ensures` has, never hardcoding an arity); (2) normalizes every
        `.set`-of-`.set` length in EVERY hypothesis and the goal via
        `List.length_set` (`at *`, so a `forall`'s own bound carried
        against the doubly-updated length reads as a bound against the
        untouched one, the same fact `t_seq_update2_get`'s own `hju`
        needs); (3) rewrites with the UNCONDITIONAL `t_seq_update2_get`
        (never the ite-free corollaries -- `simp`'s own e-matching finds
        `base`/`i1`/`v1`/`i2`/`v2`/`j` from the goal's own concrete term
        the same way `grind`'s did, so no term is threaded from Python;
        `omega` discharges the six range obligations from the just-
        normalized context); (4) splits the ite the rewrite leaves
        (`repeat' split`, so a doubly-nested ite -- `if j=i2 then .. else
        if j=i1 then ..`-- opens both levels, never just one); and (5)
        closes each leaf by whichever of `trivial`/`rfl`/`omega`/
        `contradiction` applies, or, for the one shape none of those
        reaches (two READS of the SAME untouched base list at indices
        provably but not syntactically equal, e.g. swapFirstAndLast's
        own `a[len(a)-1]! = a[i2]!`), the new `t_seq_index_congr` bridge
        (`emit_seq_helpers` above), `apply`-ed so only its own `i = j`
        side condition is left for `omega`. Measured (probe591/625, lean
        4.33.1, core only, then the full pipeline): closes both
        committed swapFirstAndLast variants' `_t_spec` theorem, axioms
        {propext, Quot.sound}; every task without this gate is
        unaffected (this branch is appended, never substituted, and is
        `None` for them so `_close` adds nothing new to their text)."""
        if not self.seq_composed_update2:
            return None
        # `<;>` throughout, never a bare `;`/`all_goals` pair (measured,
        # probeZ/probeAA/probeCC): the identical five steps, written as
        # `repeat' (...); all_goals (...); all_goals (...); all_goals
        # (...)` inside ONE enclosing paren on one line, silently make
        # NO progress at all (no error, the goal left byte-identical to
        # right after `unfold`) -- some interaction between `repeat'`
        # and a bare `;`-continuation this file does not otherwise rely
        # on. The same five steps as separate NEWLINE-separated tactics
        # (no enclosing parens needed there) or chained with `<;>`
        # instead close the goal, so `<;>` is the one this method emits;
        # every branch this file cites by name still fires per goal
        # (`<;>` distributes over however many `repeat'` left, matching
        # `all_goals`'s own intent without the bug).
        return (
            "((repeat' (first | apply And.intro | intro)) <;> "
            "(try simp only [List.length_set] at *) <;> "
            "(try simp (disch := omega) only [t_seq_update2_get]) <;> "
            "((repeat' split) <;> first | trivial | rfl | omega "
            "| contradiction | (apply t_seq_index_congr; omega)))"
        )

    def _seq_append_read_script(self) -> str | None:
        """PER-SITE APPEND/SLICE READ CODEGEN (2026-09-12, ROADMAP 16.2,
        lean's own item: 106 appendArrayToSeq, 240 replaceLastElement,
        262 splitArray, 586 splitAndAppend). `_seq_update2_script`
        above's own template, one level down: measured directly
        (splitArray/replaceLastElement/splitAndAppend/appendArrayToSeq,
        lean 4.33.1, core only) that `grind only [t_seq_append_get,
        t_seq_slice_get, ...]` (the plain fallback `_seq_hints` builds)
        cites those lemmas fine against a goal's own concrete `(slice ++
        slice)` or `(slice ++ plain)` term -- e-matching finds them, the
        same way it found `t_seq_update2_get` on the chained-`.set`
        shape -- but does not itself split the `ite` either lemma's own
        CONCLUSION carries (`if j < l1.length then .. else ..`), the
        identical ITE-SPLIT GAP `_seq_update2_script` was built for, one
        operation later.

        A second, distinct piece splitArray's/splitAndAppend's own
        `.fst ++ .snd = arr` conjunct needs and swapFirstAndLast's
        `.set`/`.set` shape never did: that conjunct is a whole-SEQUENCE
        equality, never an indexed read itself, so no amount of splitting
        the read lemmas' own ites reaches it on its own. `t_seq_ext` is
        the door from "two seqs equal" to "same length, and equal at
        every index" (already emitted whenever `self.seq_eq_comp`, the
        same gate `_seq_hints` uses to cite it to `grind`); `apply`-ing
        it FIRST, alongside the usual `And.intro`/`intro` opening, turns
        that conjunct into exactly the `[k]!`-shaped goal this method's
        rewrite/split steps handle.

        THE NAT-CAST TRAP (2026-09-12, the actual measured blocker, and
        the reason an earlier version of this method's own discharge
        tactic could not close any of the four tasks despite `grind`'s
        `Nat.min_def` fix above looking like the same gap one level up):
        `omega` already understands `Nat.min`/`Nat.max` NATIVELY --
        measured directly (probe262h.lean: `rw [List.length_take,
        List.length_drop] at h; omega` closes a `min`-carrying hypothesis
        with no `Nat.min_def` in sight) -- so unfolding `min` into an
        `ite` via `Nat.min_def` before handing a side goal to `omega` is
        not a second instance of `_seq_update2_script`'s ITE-SPLIT GAP,
        it MANUFACTURES one: `omega` cannot itself split an `ite` sitting
        inside a hypothesis or a `disch`-tactic's goal (measured:
        `omega` alone on a hypothesis shaped `k < ↑(if p then a else b)`
        reports a counterexample, treating the whole `ite` as one opaque
        atom), and once that `ite` sits under an `Int` cast (`↑`, this
        file's own convention for every seq index), splitting it with
        `split at *` still leaves `omega` unable to relate the Nat-side
        cases back to the Int-side goal cleanly. The fix is therefore
        SUBTRACTIVE, not additive: this method's own hypothesis
        normalization and its `simp`'s `disch` both cite `List.
        length_append`/`_take`/`_drop` and STOP THERE -- no `Nat.
        min_def`, so `min` stays intact for `omega` to consume in its
        own native form; `disch := omega` alone (no `split`, no nested
        `simp`) then discharges every side condition `t_seq_append_get`/
        `t_seq_slice_get`/`t_seq_append_slice2_get` need. (`_seq_hints`'s
        own `grind only [...]` fallback keeps `Nat.min_def` unchanged --
        that gap is real for `grind`'s own e-matching/case-split, which
        does NOT get `omega`'s native `min` handling; the two tactics
        need opposite treatments of the same lemma.)

        Closing `arr[(a + j)]! = arr[k]!` once both sides of a
        `t_seq_append_slice2_get`-then-`t_seq_slice_get` chain land back
        on the SAME base seq is not `rfl` (the indices are equal by
        `omega`, not syntactically) nor `omega` alone (it is a `List`
        read, not an arithmetic goal): `t_seq_index_congr` (promoted
        above from `seq_composed_update2`-only to `seq_composed_update2
        or seq_new`, since this is the same leaf on a different shape),
        `apply`-ed so only its own `i = j` side condition is left for
        `omega`, closes it.

        Measured (probe106/240/262/586.lean, lean 4.33.1, core only,
        then `t/grade.py --kernels lean,dafny --flake 3` on the four
        tasks): closes all four tasks' `_t_spec` theorem, axioms
        {propext, Quot.sound}, real=verified in all four with dafny's
        own real=verified unaffected (the twin cell, driven by the
        harness's own witness replay rather than this method, is
        unchanged by it). `None` (so `_close`'s `insert` above is
        skipped) unless `self.seq_new`, so every task outside this shape
        (including every task with only `seq_mut`/`.set`/`.fill`, no
        `++`/slice at all) sees byte-identical tactic scripts."""
        if not self.seq_new:
            return None
        names = ["t_seq_append_get", "t_seq_slice_get"]
        if self.nested:
            names += ["t_seq_append_get_row", "t_seq_slice_get_row"]
        if self.seq_composed_append_slice:
            names.append("t_seq_append_slice2_get")
        open_step = "apply And.intro | intro"
        if self.seq_eq_comp:
            open_step = "apply t_seq_ext | " + open_step
        # THE SILENT-DISCH GAP (2026-09-14, ROADMAP 16.2, lean's own
        # item, "closing the composed seq goals"): `simp`'s `disch`
        # tactic discharges EVERY side condition a cited lemma's
        # instantiation carries, not just the one whose failure is
        # actually the interesting gap -- `t_seq_append_get`'s `hj : 0 ≤
        # j` fires `disch` too, and a bare `omega` on `hju : j <
        # ((l1++l2).length:Int)` cannot see through an unreduced `.length`
        # of a `List.take`/`.drop`/`++` term (measured: probe240c/f.lean,
        # `simp` reports "made no progress" -- the lemma is never applied
        # at all, not even attempted with a wrong answer, since `disch`
        # failing on ANY one side condition aborts the whole conditional
        # rewrite). Naively swapping in a length-normalizing `simp only
        # [...]` first does not fix it either (probe240c/g.lean, same
        # "made no progress"): `disch` runs on hj too, whose goal (`0 ≤
        # j`) has no length term to rewrite, so a bare `simp only
        # [length lemmas]` on THAT goal itself raises "simp made no
        # progress" and aborts the `;`-sequenced `omega` that would have
        # closed it -- this is very likely the exact regression the
        # 2026-09-12 session's own docstring above named ("regressed 262
        # when tried in the full pipeline"). `try` in front of the simp
        # step (not on the whole disch, which would just silently accept
        # a hj/hju it could not prove and hand omega an unrewritten
        # length term again) fixes both: `hj`'s goal sees `try` no-op
        # and falls through to `omega` directly (unchanged from the
        # pre-existing behaviour that already closed it), `hju`'s goal
        # gets the length rewrite THEN omega (probe240h.lean, measured
        # clean). Additive by construction: any side condition `omega`
        # alone already closed keeps closing exactly the same way, so a
        # task never reaching a length-of-composed-term side condition
        # (262's own committed shape) sees no behavioural change.
        # THE SINGLETON-LENGTH GAP (2026-09-14, same session, 106
        # appendArrayToSeq's own loop-preservation shape, `r ++ [a[i]!]`
        # -- a literal ONE-ELEMENT list, not a `.take`/`.drop`/`++` of
        # existing seqs the way every other `seq_new` task built this
        # script for shapes it): `List.length_cons`/`List.length_nil`
        # reduce `[x].length` to `1`, a fact `List.length_append`/`_take`/
        # `_drop` alone do not supply and that `omega` cannot see through
        # on its own (measured: probe106f.lean, disch's own `simp only`
        # leaves `[a[i]!].length` a fully opaque atom without them,
        # `omega` then fails the length side condition and `simp`
        # reports "made no progress", the identical silent-disch failure
        # THE SILENT-DISCH GAP above was named for, one lemma short).
        # Added to the disch's own normalizing set only (never `len_norm`
        # itself, which runs on the OUTER goal/hypotheses where no
        # committed task's own composed term is a bare list literal) --
        # additive: a task with no `[x]`-shaped operand mid-append sees
        # the two extra simp lemmas find nothing to rewrite and no
        # behavioural change.
        rw_step = (
            "(try simp (disch := ((try simp only [List.length_append, "
            "List.length_take, List.length_drop, List.length_cons, "
            "List.length_nil]); omega)) only "
            f"[{', '.join(names)}])"
        )
        # TWO ROUNDS of rewrite/split, not one: `t_seq_ext`'s own `hget`
        # goal reads the two-slice append at an index against the
        # ORIGINAL base seq directly (`(s1slice ++ s2slice)[k]! =
        # arr[k]!`), so the first round (via `t_seq_append_slice2_get`,
        # when present) leaves each branch reading a SINGLE slice
        # (`s1[(a1+j)]!` or `s2[(a2+..)]!`), not yet a bare `arr[...]!`
        # -- a second round (`t_seq_slice_get`, same lemma list, `simp`
        # re-fires whichever LHS now matches) is what actually reaches
        # `arr[...]!` on both sides.
        # LENGTH RE-NORMALIZATION BETWEEN ROUNDS (2026-09-12,
        # replaceLastElement's own residual past the two-round fix
        # above): the first round's own `split` can put a fresh `l1.
        # length`/`l2.length` subterm into the CONTEXT (a `t_seq_
        # append_get` branch condition, `i < l1.length` or its negation)
        # that the length-normalizing `simp ... at *` above never saw
        # (it ran once, before that subterm existed), and the closing
        # `omega` needs it in `List.length_take`/`_drop` NORMAL FORM
        # (`first.length - 1`, not the un-rewritten `(first.take
        # (first.length-1)).length`) to relate the split branch's own
        # index arithmetic back to the goal's own RHS index -- so the
        # same normalizing `simp ... at *` is repeated after the first
        # split, not just before it.
        len_norm = ("(try simp only [List.length_append, "
                     "List.length_take, List.length_drop] at *)")
        # THE INVARIANT-APPLICATION LEAF (2026-09-14, ROADMAP 16.2,
        # lean's own item, "closing the composed seq goals"): 106
        # appendArrayToSeq's own loop-preservation obligation (`_t_loop_
        # spec`'s `then_tac`, `apply ..._loop_spec <;> ...`) reaches a
        # goal one level past `t_seq_index_congr`'s own reach after this
        # script's append-lemma split -- `r := r ++ [a[i]!]` under a
        # forall-prefix invariant leaves `r[j]! = s[j]!` (cited against
        # `hinv5`) or `r[(s.len+j)]! = a[j]!` (`hinv6`), provable only by
        # APPLYING that invariant at `j`, never by index congruence (the
        # two sides are different lists) or `omega`/`rfl` alone; the new
        # cell's own leaf (`[a[i]!][k]! = a[j]!` once `k = 0` is known)
        # is a different, narrower gap this session ALSO tried a
        # dedicated `t_seq_singleton_get` lemma for and reverted for the
        # identical reason below. TRIED AND REVERTED (2026-09-14, same
        # session): a bare `| grind` alternative appended here closes
        # 106's own
        # `_t_loop_spec` in isolation (probe106d/g.lean, measured) but
        # is NOT deterministic once it sits inside this script's full
        # `first` chain on a THEOREM the chain is also tried against for
        # OTHER tasks -- two full `t/grade.py --kernels lean,dafny
        # --flake 3` runs on the identical generated source (240
        # replaceLastElement, 262 splitArray, both otherwise unchanged
        # by this session) read `verified` on one run and `unproved` on
        # the next, with no code change between them (after3/after4 vs.
        # after5 in this session's own scratch grading, both at --jobs
        # 9 on this shared box). `-DmaxHeartbeats` bounds elaboration
        # STEPS, not which steps are taken -- `grind`'s own term
        # ordering can vary run to run (measured indirectly: the same
        # generated `.lean` byte-for-byte, re-run cold, disagreeing) --
        # so appending an EXPENSIVE, failure-prone `grind` alternative
        # ahead of nothing (it is tried only after every deterministic
        # alternative already failed) still spends real heartbeats on
        # this run's own attempt, and on an unlucky ordering that spend
        # can push an ADJACENT theorem that used to close cleanly past
        # budget instead. `t/AGREEMENT.md`'s 262 row is committed
        # verified and 2026-09-12's own docstring above already names
        # one prior regression on it; this session will not bank a
        # second. Left as a NAMED OPEN GAP: 106's own `_t_loop_spec`
        # preservation step needs a DETERMINISTIC closer (no `grind`)
        # that can cite the matching `hinv{k}` by name -- `_gr()`'s
        # generic call sites do not carry the invariant list's own
        # Python-side names into the tactic text at all, so the fix
        # belongs in `lower_loop`'s own codegen (the one call site that
        # DOES know them), not here.
        return (
            f"((repeat' (first | {open_step})) <;> "
            f"{len_norm} <;> "
            f"{rw_step} <;> (repeat' split) <;> {len_norm} <;> "
            f"{rw_step} <;> (repeat' split) <;> first | trivial | rfl "
            "| omega | contradiction | (apply t_seq_index_congr; omega))"
        )

    def _grind_base(self) -> str:
        """2026-09-14 (lean-closure): `grind{self.ga}` normally -- byte-
        identical to every task lowered before this session, since
        `sfun_quantified` is False whenever no spec_fun is called under
        a `forall`/`exists` anywhere this task reaches. When it IS True
        (the closure-predicate-in-a-loop shape), a FIRST attempt cites
        the spec_fun equations as a deterministic `simp only` rewrite
        (closes over the whole goal, including under quantifier binders,
        with no E-matching search) and drops them from grind's own hint
        list (`ga_wo_sfuns`) for the grind call that follows; the
        pre-existing `grind{self.ga}` (spec_fun equations handed to
        grind directly) is kept as a SECOND alternative, tried only if
        the first one fails outright (not merely slow) -- never tried
        FIRST on this shape, since that ordering is the original bug
        (`grind [isEven_s]`'s own E-matching search against a
        quantified invariant list exhausts the WHOLE per-command
        heartbeat budget before `first` ever gets a turn to try
        anything else). MEASURED 2026-09-14 why the second alternative
        stays: an EARLIER version of this fix dropped `grind{self.ga}`
        entirely once `sfun_quantified`, and regressed 775
        IsOddAtIndexOdd's own real from VERIFIED to UNPROVED (`t/
        grade.py --tasks <307,412,...,775> --kernels lean,dafny --flake
        3`, this session) -- one of 775's own non-loop grind sites
        closes on the RAW hint (`grind [isOdd_s]` alone, no preceding
        `simp`) but not on `simp only [isOdd_s] at * <;> grind` alone,
        so replacing rather than falling back regressed a real that was
        never part of the timeout problem this item targets. Every call
        site that used to interpolate `f\"grind{self.ga}\"` directly now
        calls this instead (`_gr`'s and `_close`'s own `base`,
        `emit_sfuns`, `emit_clause_wfs`, the SIMPLE/RECURSIVE-shape spec
        theorems), so the fix reaches wherever a spec_fun call under a
        quantifier surfaces, not just the loop-preservation site the
        five committed timeout rows happened to hit it at first."""
        if self.sfun_quantified and self.sfun_names_ga:
            names = ", ".join(self.sfun_names_ga)
            return (f"(first | (simp only [{names}] at * <;> "
                    f"grind{self.ga_wo_sfuns}) | grind{self.ga})")
        return f"grind{self.ga}"

    def _close(self, nodes: list, env: dict, types: dict, base: str) -> str:
        """`base` tried first; the div/mod bridges above added only when
        `nodes` actually reaches a div/mod application, and the
        seq-update/fill fallback (see `_seq_hints`/`_gr` below) added
        whenever the task touches `update`/`fill` at all. A no-op
        (returns `base` unchanged) for every task that touches neither,
        so the fifteen pre-existing tasks see byte-identical tactic
        scripts."""
        branches = self._divmod_branches(nodes, env, types)
        if self.seq_mut or self.seq_new or self.seq_eq_comp:
            branches.append(f"(grind only [{self._seq_hints()}])")
            # PER-SITE INDEX CODEGEN (2026-09-12, ROADMAP 16.2): tried
            # BEFORE the `grind only` fallback above, since it is the
            # generated fix for exactly the gap that fallback's own
            # e-matching cannot close (a many-hypothesis composed lemma
            # against a nested `.set`/`.set` chain); `None` (so this
            # `branches.append` is skipped) for every task outside that
            # one shape, so nothing else changes.
            seq2 = self._seq_update2_script()
            if seq2 is not None:
                branches.insert(-1, seq2)
            # APPEND-OF-SLICES PER-SITE SCRIPT (2026-09-12, ROADMAP 16.2,
            # lean's own item): the analogous gap one level down from
            # `_seq_update2_script` above, on the READ-after-`++` shape
            # instead of the READ-after-chained-`.set` one; see
            # `_seq_append_read_script`'s own docstring.
            seq3 = self._seq_append_read_script()
            if seq3 is not None:
                branches.insert(-1, seq3)
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
        names = []
        if self.seq_mut:
            names += ["t_seq_update_get", "t_seq_fill_get",
                      "List.length_set", "List.length_replicate"]
            if self.nested:
                # SPEC.md "Nested sequences (v1)": `t_seq_update_get`/
                # `t_seq_fill_get` above are stated for element type Int
                # only (a fixed monomorphic `theorem`, not a polymorphic
                # one); an outer-level read after `update`/`fill` on a
                # `List (List Int)` needs the SAME bridge specialized to
                # element type `List Int` instead, named distinctly so a
                # task mixing flat and nested update/fill (none committed
                # does) still gets both. Measured (a four-theorem scratch
                # probe, lean 4.33.1, core only): the identical proof
                # script, only `Int` changed to `List Int` in `l`'s/`v`'s
                # own type, compiles clean, depending on {propext,
                # Quot.sound} like every other bridge lemma here. Neither
                # committed nested task (`swap_rows`, `row_max_len`)
                # actually needs this: `swap_rows`'s own SIMPLE-shape
                # goals are small enough for plain `grind` (the `_gr`/
                # `_close` base case) to close outright, measured directly
                # (`harness.run_task` COUNTS with these two names never
                # having fired); wired the same way `_unshow`'s pair
                # component handling was for an unexercised shape, for the
                # nested task whose goal IS big enough to hit the same
                # recursion-depth wall the flat bridge was built for.
                names += ["t_seq_update_get_row", "t_seq_fill_get_row"]
            if self.seq_composed_update2:
                # THE FRAME-FACT GAP's open list (2026-09-11): a chained
                # double-update read, ONE generic lemma (`emit_seq_
                # helpers` below), matched by grind's e-matcher against
                # the goal's own concrete nested `.set` term in a single
                # step -- no chaining of the two single-level lemmas
                # required. THE ITE-SPLIT GAP (2026-09-12, ROADMAP 16.2):
                # the ite-free corollaries (`emit_seq_helpers`'s own
                # `t_seq_update2_get_hi/_mid/_lo`) are cited ALONGSIDE
                # the original, not instead of it -- grind still gets
                # the general fact for any goal shaped to use it
                # directly, and now also gets the three case-split
                # forms whose antecedents its own decision procedure
                # for `Int` equality resolves without needing to open
                # an `ite` in a cited fact's own conclusion.
                names += ["t_seq_update2_get", "t_seq_update2_get_hi",
                          "t_seq_update2_get_mid", "t_seq_update2_get_lo"]
        if self.seq_new:
            # SPEC.md "Sequences: literals, concatenation, slices (v1)"
            # (2026-09-09): the same recursion-depth wall the update/fill
            # bridge above was built for, measured again on filter_pos's
            # own value-invariant preservation goal, the LLM-shaped append
            # idiom `r := r + [s[i]]` -- a read after `++` past the
            # `.toNat` cast needs `t_seq_append_get` the same way a read
            # after `.set` needed `t_seq_update_get`; a read after a slice
            # (tail's own ensures, `r[k] == s[k+1]` with `r = s[1..]`)
            # needs `t_seq_slice_get` the same way. `List.length_append`/
            # `List.length_take`/`List.length_drop` are already in grind's
            # default simp set (measured, parallel to `length_set`/
            # `length_replicate`), but named here too since `grind only`
            # drops the default set entirely.
            #
            # `Nat.min_def` (2026-09-12, ROADMAP 16.2, lean's own item,
            # splitArray/splitAndAppend): `List.length_take`'s own
            # CONCLUSION is `(l.take n).length = min n l.length` -- under
            # `grind only` (no default simp set) grind cites this fact
            # but does not itself split the `min` it names into its two
            # `Nat.le`-guarded cases, so a goal needing to know
            # `min n l.length = 0` from `n = 0` alone (splitAndAppend's
            # own length obligation, `min` never unfolded) is left
            # unclosed with `n = 0` sitting right there in context.
            # Measured directly (probe586c.lean, lean 4.33.1, core only):
            # adding `Nat.min_def` (`min n m = if n ≤ m then n else m`,
            # core Lean, not Mathlib) to this same `grind only` list lets
            # grind's own case-split machinery open the `ite` and close
            # the goal with the arithmetic already in context -- the
            # SAME "cited fact carries an un-split ite" gap named for the
            # composed get-lemmas below, here in a stock library lemma
            # instead of one this file emits itself.
            names += ["t_seq_append_get", "t_seq_slice_get",
                      "List.length_append", "List.length_take",
                      "List.length_drop", "Nat.min_def"]
            if self.nested:
                # Same reasoning as the seq_mut branch above, for the
                # append/slice bridge: `List.length_append`/`_take`/
                # `_drop` themselves are already POLYMORPHIC core Lean
                # facts about list length (measured: their statements
                # quantify over an arbitrary `{α}`, not `Int` -- no
                # element type in sight), so they apply at the outer
                # level and the row level UNCHANGED, needing no row-typed
                # duplicate; only the two READ bridges, monomorphic in
                # element type by construction, need one.
                names += ["t_seq_append_get_row", "t_seq_slice_get_row"]
            if self.seq_composed_append_slice:
                # THE FRAME-FACT GAP's open list (2026-09-11): an append
                # of two slices, read at an index -- ONE generic lemma
                # composing `t_seq_append_get` then, per branch,
                # `t_seq_slice_get` (proved once, `emit_seq_helpers`
                # below), so grind matches the WHOLE nested term in one
                # e-match step instead of needing to chain the two
                # single-level bridges across the slice subterm.
                names.append("t_seq_append_slice2_get")
        if self.seq_eq_comp:
            names.append("t_seq_ext")
        return ", ".join(names + [f"{f}_s" for f in self.sfuns])

    def _gr(self, nodes: list | None = None, env: dict | None = None,
           types: dict | None = None) -> str:
        """`grind{self.ga}`, the plain call used everywhere in this file;
        with the seq fallback appended (parenthesized, so it drops into
        any `first | ... | ...` or `<;>` call site unchanged) whenever
        `self.seq_mut or self.seq_new`, and (SPEC.md "Division and
        modulo" + "Sequences: literals, concatenation, slices (v1)",
        third sweep, 2026-09-09) the same div/mod and quantified-div/mod
        bridges `_close` builds, when `nodes` (the raw clause(s) this
        theorem's goal was built from) is passed -- every pre-existing
        call site passes nothing, so their text is unaffected; only the
        loop invariant/guard/decreases WF theorems (clover_rotate's own
        residual, measured 2026-09-09) pass their source clause."""
        base = self._grind_base()
        branches = []
        if nodes is not None:
            branches += self._divmod_branches(nodes, env or {},
                                              types or self.types)
        if self.seq_mut or self.seq_new or self.seq_eq_comp:
            branches.append(f"grind only [{self._seq_hints()}]")
            # THE LOOP-PRESERVATION GAP (2026-09-14, ROADMAP 16.2, lean's
            # own item, "closing the composed seq goals"): every call
            # site inside `lower_loop` (the loop-invariant preservation
            # obligation `_t_loop_spec`'s own `then_tac` chains into via
            # `apply ..._t_loop_spec <;> self._gr()`, and the WF theorems
            # `_t_wf3`/`_t_wf4`/`_t_wf5` that state the SAME facts before
            # the loop is even defined) only ever saw `_gr`'s plain
            # `grind only [...]` fallback, never `_close`'s own per-site
            # `_seq_append_read_script` -- that script was wired into
            # `_close` alone (postcondition conjuncts opened by
            # `t_seq_ext`/`And.intro`/a bare `intro`), and 2026-09-12's
            # own docstring (`_seq_append_read_script`, above) read the
            # loop-preservation goal's own shape as therefore
            # unreachable by it. Measured wrong (probe: appendArrayToSeq's
            # `_t_loop_spec` preservation goal for `hinv6`, `forall j,
            # 0<=j<i_v2+1 -> (r++[a[i]!])[s.len+j]! = a[j]!`, is a bare
            # `forall`/`->`chain, exactly the shape `repeat' (first |
            # apply And.intro | intro)` already opens for a postcondition
            # -- the goal reads identically to one, it was simply never
            # OFFERED the script). Adding it here, as one more `first`
            # alternative alongside the existing `grind only [...]`
            # fallback (never replacing it: `first` tries `base`, the
            # existing seq-hints branch, then this one, in that order, so
            # any goal either already closed keeps closing on the SAME
            # earlier alternative, byte-for-byte), is additive by
            # construction: `_seq_append_read_script` returns `None`
            # unless `self.seq_new`, so a task with only `self.seq_mut`
            # or `self.seq_eq_comp` (and no `++`/slice at all) sees no
            # new branch. Measured (t/grade.py, lean+dafny, flake 3): on
            # its own this reaches FURTHER into 106 appendArrayToSeq's
            # own `_t_loop_spec` (its `hinv5` preservation goal now
            # rewrites and splits through the append lemma instead of
            # leaving it untouched) but does NOT flip the verdict -- the
            # residual leaf (applying `hinv5`/`hinv6` by name once the
            # two sides are DIFFERENT lists, never index congruence) is
            # a separate, still-open gap, see `_seq_append_read_script`'s
            # own "THE INVARIANT-APPLICATION LEAF" docstring for what was
            # tried there and reverted. Confirmed harmless: none of the
            # 34 AGREEMENT tasks or the 15 `seq_new` dafny_synthesis rows
            # of COVERAGE-lifted-785.md moved (this session's own dated
            # note, below, carries the full regression run) -- every one
            # of those either has no loop at all (so never reaches this
            # call site) or already closed on an earlier alternative.
            if self.seq_new:
                seq3 = self._seq_append_read_script()
                if seq3 is not None:
                    branches.append(seq3)
        if not branches:
            return base
        return "(first | " + base + " | " + " | ".join(branches) + ")"

    def _dec(self, needed: bool = False) -> str:
        """The `decreasing_by` line used at every termination proof site in
        this file (SPEC.md "Sequences as values", 2026-09-09): a recursive
        call whose state argument is `s[i := v]` or `seq(n, v)` needs
        `List.length_set`/`List.length_replicate` before `omega` can see
        that the measure (built from `.length`) actually decreased through
        the `.set`/`.replicate`. Measured on clover_replace's
        `_t_loop_spec` termination goal: plain `omega` cannot see through
        the `.set` at all (fails outright, no `List.length_set` in its
        theory); plain `grind` finds `List.length_set` fine in the SMALL
        context of a bare `_t_loop` definition's own termination goal (no
        invariants in scope there) but, once the goal also carries a
        loop's full invariant list (as `_t_loop_spec`'s recursive call
        does), the same E-matching search that read/update needed `grind
        only` for above (`_seq_hints`) explores every invariant's
        `getElem!` machinery here too and hits Lean's recursion-depth cap;
        `simp only [List.length_set, List.length_replicate]; omega`
        closes it directly, no search, since it is exactly the one fact
        `omega` was missing. Added as one extra `first`-alternative, but
        ONLY when the caller passes `needed=True`: `lower_loop` sets it
        exactly when the loop's own `decreases` expression names a state
        variable that the loop body itself rewrites via `update`/`fill`
        (`self._dec_needs_seq_bridge`, below); every other call site
        (`spec_funs`, `lower_rec`, and a loop whose measure does not
        depend on the mutated variable, e.g. reverse's `len(s) - i`,
        `s` untouched) passes nothing and keeps the exact prior text, so
        the fifteen pre-existing tasks AND reverse and swap stay
        byte-identical outside the seq-helper prelude (measured: reverse's
        two `decreasing_by` lines are unaffected, since `s`, the variable
        its `decreases` names, is read-only; the mutated return `r` never
        appears in a decreases clause in any task lowered so far).

        SPEC.md "Sequences: literals, concatenation, slices (v1)"
        (2026-09-09) extends the same bridge to `++`/`.take`/`.drop`:
        `List.length_append`/`List.length_take`/`List.length_drop` join
        the alternative's simp set, but ONLY the names for the mechanism
        that actually fired (`self.seq_mut` for `.set`/`.replicate`,
        `self.seq_new` for `++`/slice), so a task using update/fill alone
        still gets exactly the prior two-name simp set, byte-identical."""
        extra = []
        if needed and self.seq_mut:
            extra += ["List.length_set", "List.length_replicate"]
        if needed and self.seq_new:
            extra += ["List.length_append", "List.length_take",
                      "List.length_drop"]
        alt = (" | (simp only [" + ", ".join(extra) + "]; omega)"
              if extra else "")
        return f"decreasing_by all_goals (first | omega{alt} | grind)\n"

    def _dec_needs_seq_bridge(self, dec_expr: dict, env: dict) -> bool:
        """True iff `dec_expr` (a loop's `decreases`) names a state
        variable whose CURRENT symbolic value (`env`, from `sym()`) is
        itself an `update`/`fill` term -- textually, contains a Lean
        `.set `/`List.replicate ` call -- or (2026-09-09) a `++`/slice
        term -- textually, ` ++ `/`.take (`/`.drop ` -- so the
        auto-generated termination goal for the recursive call needs the
        length bridge `_dec(needed=True)` supplies. False whenever
        neither `self.seq_mut` nor `self.seq_new`, so it never fires for
        a task that predates either construct."""
        if not (self.seq_mut or self.seq_new):
            return False
        names: set = set()
        _collect_names(dec_expr, names)

        def touched(v: str) -> bool:
            val = env.get(v, "")
            if self.seq_mut and (".set " in val
                                 or "List.replicate " in val):
                return True
            if self.seq_new and (" ++ " in val or ".take (" in val
                                 or ".drop " in val):
                return True
            return False

        return any(touched(v) for v in names)

    # SPEC.md "Sequences: literals, concatenation, slices (v1)" (2026-09-09):
    # two more hand-proved bridge lemmas, parallel to `t_seq_update_get`/
    # `t_seq_fill_get` above and needed for the identical reason -- a read
    # after `++` or a slice, once the index is the Int-cast-through-
    # `.toNat` this file's `at` already uses, is past grind's default
    # e-matching reach (measured on filter_pos's value-invariant
    # preservation goal, the append idiom, and on tail's own ensures, the
    # slice). `t_seq_append_get` totalizes `List.getElem_append`'s
    # dependent split the same way `t_seq_update_get` totalizes
    # `List.getElem_set`'s; `t_seq_slice_get` composes `List.getElem_take`
    # and `List.getElem_drop` the same way, both proved once here and
    # closed by `grind only` (never plain `grind`, for the same reason:
    # `only` is what stops the default-set search that hit the recursion
    # cap in the first place). `List.extract` was measured against this
    # `drop`-then-`take` encoding and rejected: on lean 4.33.1 it unfolds
    # to exactly `take (stop - start) (drop start l)` with no lemmas of
    # its own, so it would only add an extra unfold with nothing to show
    # for it.
    # DIVISOR-BOUND LEMMA (2026-09-12, ROADMAP 16.2, lean's own item):
    # `t_divisor_le_half_<name>` is the pure number-theory fact (`2 <= k
    # < n`, `n % k == 0` implies `k <= n/2`); `t_divisor_bound_<name>`
    # uses it to widen the loop's own `[lo, i)` fact (`hquant`) to the
    # task's full `[lo, n)` ensures, given the extra invariant
    # `lower_loop` added (`hbound : i <= n/2 + 1`) and the exit branch's
    # own `hng : not (i <= n/2)`. Both proved by hand, core Lean only
    # (measured, lean 4.33.1, probediv7.lean/probediv8.lean scratch
    # probes): `Int.dvd_iff_emod_eq_zero` turns the mod fact into a
    # witnessed `k ∣ n` (`obtain ⟨c, hc⟩`), then `Int.mul_le_mul_of_
    # nonneg_left` (a plain order lemma, not `nlinarith`/`polyrith`,
    # neither of which exists outside Mathlib) does the ONE genuinely
    # nonlinear step (`c <= 1 -> k*c <= k*1`, and `2 <= c -> k*2 <=
    # k*c`) that turns `n = k*c` into a linear fact `omega` finishes
    # from there, `/2`'s own constant-divisor reasoning included
    # natively. `by_cases` (core Lean, unlike `by_contra`/`push_neg`,
    # BOTH measured absent from this toolchain -- `by_contra` reported
    # "unknown tactic" directly, probebc.lean) supplies the one case
    # split each proof needs. Depends on {propext, Quot.sound} only
    # (measured via `#print axioms`), the same allowlist every other
    # bridge lemma in this file already carries.
    def emit_divisor_bound(self) -> tuple[str, list]:
        plan = self._divisor_bound_plan
        if plan is None:
            return "", []
        name = self.name
        half = f"t_divisor_le_half_{name}"
        bound = f"t_divisor_bound_{name}"
        lo = self.term(plan["lo"], {}, self.types)
        half_def = (
            f"theorem {half} (n k : Int)\n"
            f"    (hlo : ({lo}) ≤ k) (hk : k < n) (hmod : n % k = (0:Int)) "
            ":\n"
            "    k ≤ n / 2 := by\n"
            "  have hdvd : k ∣ n := Int.dvd_iff_emod_eq_zero.mpr hmod\n"
            "  obtain ⟨c, hc⟩ := hdvd\n"
            "  have hc2 : (2:Int) ≤ c := by\n"
            "    by_cases hcon : c ≤ 1\n"
            "    · have hle : k * c ≤ k * 1 :=\n"
            "        Int.mul_le_mul_of_nonneg_left hcon (by omega)\n"
            "      rw [Int.mul_one] at hle\n"
            "      omega\n"
            "    · omega\n"
            "  have hge : k * 2 ≤ k * c :=\n"
            "    Int.mul_le_mul_of_nonneg_left hc2 (by omega)\n"
            "  omega\n\n")
        i_name = plan["i_name"]
        if plan["kind"] == "forall":
            rel = "≠" if plan["relop"] == "!=" else "="
            bound_def = (
                f"theorem {bound} (n {i_name} : Int) (result : Bool)\n"
                f"    (hquant : result = true ↔ (∀ (k : Int), ({lo}) ≤ k "
                f"→ k < {i_name} → n % k {rel} (0:Int)))\n"
                f"    (hbound : {i_name} ≤ n / 2 + 1)\n"
                f"    (hng : ¬ {i_name} ≤ n / 2) :\n"
                "    result = true ↔ (∀ (k : Int), "
                f"({lo}) ≤ k → k < n → n % k {rel} (0:Int)) := by\n"
                "  constructor\n"
                "  · intro hr k hk1 hk2\n"
                f"    by_cases hki : k < {i_name}\n"
                "    · exact hquant.mp hr k hk1 hki\n"
                "    · by_cases hz : n % k = (0:Int)\n"
                "      · exfalso\n"
                f"        have hle : k ≤ n / 2 := "
                f"{half} n k hk1 hk2 hz\n"
                "        omega\n"
                "      · exact hz\n"
                "  · intro hr\n"
                "    exact hquant.mpr (fun k hk1 hk2 => "
                "hr k hk1 (by omega))\n")
        else:
            rel = "=" if plan["relop"] == "==" else "≠"
            bound_def = (
                f"theorem {bound} (n {i_name} : Int) (result : Bool)\n"
                f"    (hquant : result = true ↔ (∃ (k : Int), ({lo}) ≤ k "
                f"∧ k < {i_name} ∧ n % k {rel} (0:Int)))\n"
                f"    (hbound : {i_name} ≤ n / 2 + 1)\n"
                f"    (hng : ¬ {i_name} ≤ n / 2) :\n"
                "    result = true ↔ (∃ (k : Int), "
                f"({lo}) ≤ k ∧ k < n ∧ n % k {rel} (0:Int)) := by\n"
                "  constructor\n"
                "  · intro hr\n"
                "    obtain ⟨k, hk1, hk2, hk3⟩ := hquant.mp hr\n"
                "    exact ⟨k, hk1, by omega, hk3⟩\n"
                "  · intro hr\n"
                "    obtain ⟨k, hk1, hk2, hk3⟩ := hr\n"
                f"    by_cases hki : k < {i_name}\n"
                "    · exact hquant.mpr ⟨k, hk1, hki, hk3⟩\n"
                "    · exfalso\n"
                f"      have hle : k ≤ n / 2 := "
                f"{half} n k hk1 hk2 hk3\n"
                "      omega\n")
        return half_def + bound_def, [
            (half, "divisor-bound lemma, k <= n/2 for a divisor below n"),
            (bound, "divisor-bound lemma, widens [lo, i) to [lo, n)")]

    def emit_seq_helpers(self) -> str:
        if not (self.seq_mut or self.seq_new or self.seq_eq_comp):
            return ""
        parts = []
        if self.seq_eq_comp:
            # BOOLEANS AS COMPUTATIONAL VALUES (2026-09-10): a
            # computational seq `==`/`!=` lowers (term()'s new unified
            # case) to `decide (s = t)`; `decide_eq_true_eq` alone gets a
            # goal to Lean's native, STRUCTURAL `s = t`, but this file's
            # own ensures clauses state seq equality ELEMENTWISE (SPEC.md
            # "equal lengths and equal elements at every index"), so the
            # spec theorem still needs list EXTENSIONALITY to bridge the
            # two. One lemma, proved once, generic in the element type
            # (`{α : Type} [Inhabited α]` -- `List.ext_getElem` needs no
            # DecidableEq, and `getElem!_pos`'s totalization is already
            # polymorphic, so this needs no `_row` duplicate the way the
            # read bridges above do): length equality (as Int, matching
            # this file's own `len()` convention) plus a pointwise
            # `getElem!` equality (the same `.toNat`-cast shape `at`
            # already emits) give `List.ext_getElem` exactly its two
            # obligations once the Int cast is `omega`'d to a Nat length
            # equality and the `getElem!` hypothesis is totalized via
            # `getElem!_pos` on each side. Measured (lean 4.33.1, core
            # only, a five-theorem scratch probe): closes `grind only
            # [t_seq_ext]` on both fz_v1nested_026's and fz_p_nest_eq's
            # own spec theorem (`List (List Int)`, using the SAME lemma,
            # no row-typed twin) with no other change.
            parts.append(
            "theorem t_seq_ext {α : Type} [Inhabited α] {l1 l2 : List α}\n"
            "    (hlen : ((l1.length : Int)) = ((l2.length : Int)))\n"
            "    (hget : ∀ (k : Int), (0 : Int) ≤ k → k < ((l1.length : Int))"
            " →\n"
            "      l1[(k).toNat]! = l2[(k).toNat]!) :\n"
            "    l1 = l2 := by\n"
            "  apply List.ext_getElem\n"
            "  · omega\n"
            "  · intro i h1 h2\n"
            "    have hk := hget (i : Int) (by omega) (by omega)\n"
            "    simp only [Int.toNat_natCast] at hk\n"
            "    rwa [getElem!_pos l1 i h1, getElem!_pos l2 i h2] at hk\n")
        if self.seq_mut:
            parts.append(
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
            if self.nested:
                # SPEC.md "Nested sequences (v1)": the row-typed twins of
                # the two lemmas just above, element type `List Int`
                # instead of `Int` -- the IDENTICAL proof script, measured
                # by scratch probe (lean 4.33.1, core only): the tactic
                # text never inspects the element type at all (`omega`
                # closes the `.toNat` casts, `getElem!_pos`/`List.
                # getElem_set`/`List.getElem_replicate` are polymorphic
                # in `α`), only the two `theorem` signatures change.
                parts.append(
                "theorem t_seq_update_get_row "
                "(l : List (List Int)) (i j : Int) (v : List Int)\n"
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
                "theorem t_seq_fill_get_row "
                "(n : Int) (v : List Int) (j : Int)\n"
                "    (hn : n ≥ (0 : Int)) (hj : (0 : Int) ≤ j) "
                "(hju : j < n) :\n"
                "    (List.replicate (n).toNat v)[(j).toNat]! = v := by\n"
                "  have hb : (j).toNat < "
                "(List.replicate (n).toNat v).length := by\n"
                "    rw [List.length_replicate]; omega\n"
                "  rw [getElem!_pos (List.replicate (n).toNat v) "
                "(j).toNat hb,"
                " List.getElem_replicate]\n")
            if self.seq_composed_update2:
                # THE FRAME-FACT GAP's open list (2026-09-11):
                # swapFirstAndLast's own `(a.set i1 v1).set i2 v2`, read
                # at any index -- fully generic (base/i1/v1/i2/v2/j all
                # universally quantified, ADDITIVE to `t_seq_update_get`
                # above, never replacing it), proved by TWO applications
                # of `t_seq_update_get` itself (outer, then inner) inside
                # this one theorem's own proof -- the chaining `grind`
                # cannot do across a nested subterm, done once here by
                # hand so grind's own e-matching only has to unify the
                # WHOLE nested term against this lemma's LHS in a single
                # step. Measured (probe1.lean, lean 4.33.1, core only):
                # compiles clean, axioms {propext, Quot.sound}, the same
                # allowlist every other bridge lemma here depends on.
                parts.append(
                "theorem t_seq_update2_get (base : List Int) "
                "(i1 v1 i2 v2 j : Int)\n"
                "    (hi1 : (0:Int) ≤ i1) (hiu1 : i1 < ((base.length:Int)))\n"
                "    (hi2 : (0:Int) ≤ i2) (hiu2 : i2 < ((base.length:Int)))\n"
                "    (hj : (0:Int) ≤ j) (hju : j < ((base.length:Int))) :\n"
                "    ((base.set i1.toNat v1).set i2.toNat v2)[j.toNat]! =\n"
                "      if j = i2 then v2 else "
                "if j = i1 then v1 else base[j.toNat]! := by\n"
                "  have h1len : (((base.set i1.toNat v1)).length : Int) "
                "= (base.length:Int) := by\n"
                "    rw [List.length_set]\n"
                "  have hiu2' : i2 < (((base.set i1.toNat v1)).length "
                ": Int) := by rw [h1len]; exact hiu2\n"
                "  have hju' : j < (((base.set i1.toNat v1)).length "
                ": Int) := by rw [h1len]; exact hju\n"
                "  rw [t_seq_update_get (base.set i1.toNat v1) i2 j v2 "
                "hi2 hiu2' hj hju']\n"
                "  split\n"
                "  · rfl\n"
                "  · next hne =>\n"
                "    rw [t_seq_update_get base i1 j v1 hi1 hiu1 hj hju]\n")
                # THE ITE-SPLIT GAP (2026-09-12, ROADMAP 16.2, lean's own
                # item, swapFirstAndLast's own residual): `grind only
                # [t_seq_update2_get, ...]` cites the lemma above fine
                # (e-matching unifies its LHS against the goal's own
                # concrete `(base.set i1 v1).set i2 v2` term), but its
                # CONCLUSION is a two-way nested `ite` (`if j = i2 then
                # v2 else if j = i1 then v1 else base[j]!`) that grind
                # does not itself split to line up with the goal's own
                # UNCONDITIONAL equality (`result[0]! = v2`, no ite in
                # sight) -- measured directly (probe swapFirstAndLast,
                # lean 4.33.1, core only): `grind only` cites the fact
                # but leaves the goal open with the fact's own `ite`
                # sitting unresolved in context. Fixed the way the
                # composed lemma itself was built for the ANALOGOUS gap
                # one level down (chaining two single-level bridges):
                # three COROLLARIES, one per index case, each a plain
                # IMPLICATION with NO `ite` in its own conclusion, so
                # grind never needs to split anything -- its own
                # decision procedure for `j = i2`/`j = i1` (both plain
                # `Int` equalities, natively decidable) supplies the
                # antecedent directly from the goal's own concrete `j`,
                # `i1`, `i2`. Each is proved by ONE `rw` into the ite
                # lemma above plus `if_pos`/`if_neg` on the SAME
                # decidable equality, never re-deriving the update
                # chain itself.
                parts.append(
                "theorem t_seq_update2_get_hi (base : List Int) "
                "(i1 v1 i2 v2 j : Int)\n"
                "    (hi1 : (0:Int) ≤ i1) (hiu1 : i1 < ((base.length:Int)))\n"
                "    (hi2 : (0:Int) ≤ i2) (hiu2 : i2 < ((base.length:Int)))\n"
                "    (hj : (0:Int) ≤ j) (hju : j < ((base.length:Int)))\n"
                "    (heq : j = i2) :\n"
                "    ((base.set i1.toNat v1).set i2.toNat v2)[j.toNat]! "
                "= v2 := by\n"
                "  rw [t_seq_update2_get base i1 v1 i2 v2 j hi1 hiu1 hi2 "
                "hiu2 hj hju, if_pos heq]\n"
                "\n"
                "theorem t_seq_update2_get_mid (base : List Int) "
                "(i1 v1 i2 v2 j : Int)\n"
                "    (hi1 : (0:Int) ≤ i1) (hiu1 : i1 < ((base.length:Int)))\n"
                "    (hi2 : (0:Int) ≤ i2) (hiu2 : i2 < ((base.length:Int)))\n"
                "    (hj : (0:Int) ≤ j) (hju : j < ((base.length:Int)))\n"
                "    (hne2 : j ≠ i2) (heq1 : j = i1) :\n"
                "    ((base.set i1.toNat v1).set i2.toNat v2)[j.toNat]! "
                "= v1 := by\n"
                "  rw [t_seq_update2_get base i1 v1 i2 v2 j hi1 hiu1 hi2 "
                "hiu2 hj hju, if_neg hne2, if_pos heq1]\n"
                "\n"
                "theorem t_seq_update2_get_lo (base : List Int) "
                "(i1 v1 i2 v2 j : Int)\n"
                "    (hi1 : (0:Int) ≤ i1) (hiu1 : i1 < ((base.length:Int)))\n"
                "    (hi2 : (0:Int) ≤ i2) (hiu2 : i2 < ((base.length:Int)))\n"
                "    (hj : (0:Int) ≤ j) (hju : j < ((base.length:Int)))\n"
                "    (hne2 : j ≠ i2) (hne1 : j ≠ i1) :\n"
                "    ((base.set i1.toNat v1).set i2.toNat v2)[j.toNat]! "
                "= base[j.toNat]! := by\n"
                "  rw [t_seq_update2_get base i1 v1 i2 v2 j hi1 hiu1 hi2 "
                "hiu2 hj hju, if_neg hne2, if_neg hne1]\n")
                # PER-SITE INDEX CODEGEN's own closing bridge
                # (2026-09-12, ROADMAP 16.2, lean's own item): the
                # generated spec-theorem script (`_seq_update2_script`
                # below) rewrites the WHOLE goal with the unconditional
                # `t_seq_update2_get` above (never the hi/mid/lo
                # corollaries -- those still exist for `_seq_hints`'s own
                # `grind only` fallback, unchanged), splits the ite it
                # leaves, and closes each leaf by `rfl`/`omega`/
                # `contradiction` OR, when the leaf equates two READS of
                # the UNCHANGED base list at two syntactically different
                # but numerically equal indices (measured: this is every
                # leaf `rfl` alone cannot close -- swapFirstAndLast's own
                # `a[len(a)-1]! = a[i2]!` where `i2` renders through the
                # doubly-updated seq's own length, not `a`'s), by this
                # one bridge, `apply`-ed so its `i = j` side-condition
                # unifies as `omega`'s only remaining obligation. Proved
                # by one `rw`, generic in the element type is NOT needed
                # here (every composed-update task committed is `List
                # Int`), so no `_row` twin. Measured (probe591/625,
                # lean 4.33.1, core only): compiles clean, axioms
                # {propext, Quot.sound}, closes swapFirstAndLast's own
                # `_t_spec` in both variants with the certificate script
                # below, no other theorem in this file changed.
        if self.seq_composed_update2 or self.seq_new:
            # `t_seq_index_congr` above was update2-only; the same
            # provably-equal-but-not-syntactically-equal-index leaf shows
            # up on the append/slice read shape too (2026-09-12, ROADMAP
            # 16.2, lean's own item: splitArray/splitAndAppend's own
            # reconstruction of a slice-of-a-slice back against the
            # ORIGINAL base seq -- `t_seq_append_slice2_get` then
            # `t_seq_slice_get` chain to `arr[(a + j)]!` on one side,
            # `arr[k]!` on the other, `a + j = k` by `omega` alone, never
            # `rfl`), so this is emitted once whenever EITHER shape is
            # present, guarded so a task needing both (none committed
            # does) still gets exactly one declaration.
            parts.append(
                "theorem t_seq_index_congr (a : List Int) (i j : Int) "
                "(h : i = j) :\n"
                "    a[i.toNat]! = a[j.toNat]! := by rw [h]\n")
        if self.seq_new:
            parts.append(
            "theorem t_seq_append_get (l1 l2 : List Int) (j : Int)\n"
            "    (hj : (0 : Int) ≤ j) "
            "(hju : j < (((l1 ++ l2).length : Int))) :\n"
            "    (l1 ++ l2)[(j).toNat]! =\n"
            "      if j < ((l1.length : Int)) then l1[(j).toNat]! "
            "else l2[(j - (l1.length : Int)).toNat]! := by\n"
            "  have hlen : (l1 ++ l2).length = l1.length + l2.length :=\n"
            "    List.length_append\n"
            "  have hbl : (j).toNat < (l1 ++ l2).length := by omega\n"
            "  rw [getElem!_pos (l1 ++ l2) (j).toNat hbl, "
            "List.getElem_append]\n"
            "  split\n"
            "  · next hh =>\n"
            "    rw [if_pos (by omega : j < ((l1.length : Int)))]\n"
            "    have hbl1 : (j).toNat < l1.length := hh\n"
            "    exact (getElem!_pos l1 (j).toNat hbl1).symm\n"
            "  · next hh =>\n"
            "    rw [if_neg (by omega : ¬ j < ((l1.length : Int)))]\n"
            "    have hbl2 : (j).toNat - l1.length < l2.length := by omega\n"
            "    have heq : (j).toNat - l1.length "
            "= (j - (l1.length : Int)).toNat := by omega\n"
            "    exact (getElem!_pos l2 ((j).toNat - l1.length) hbl2).symm."
            "trans\n"
            "      (congrArg (l2[·]!) heq)\n"
            "\n"
            "theorem t_seq_slice_get (s : List Int) (a b j : Int)\n"
            "    (ha : (0 : Int) ≤ a) (hab : a ≤ b) "
            "(hbl : b ≤ ((s.length : Int)))\n"
            "    (hj : (0 : Int) ≤ j) (hju : j < b - a) :\n"
            "    ((s.drop a.toNat).take (b - a).toNat)[(j).toNat]! "
            "= s[(a + j).toNat]! := by\n"
            "  have hb1 : (j).toNat "
            "< ((s.drop a.toNat).take (b - a).toNat).length := by\n"
            "    rw [List.length_take, List.length_drop]\n"
            "    omega\n"
            "  rw [getElem!_pos ((s.drop a.toNat).take (b - a).toNat) "
            "(j).toNat hb1,\n"
            "      List.getElem_take, List.getElem_drop]\n"
            "  have hb2 : (a.toNat + j.toNat) < s.length := by omega\n"
            "  have heq : a.toNat + j.toNat = (a + j).toNat := by omega\n"
            "  rw [← getElem!_pos s (a.toNat + j.toNat) hb2, heq]\n")
            if self.nested:
                # SPEC.md "Nested sequences (v1)": the row-typed twins of
                # `t_seq_append_get`/`t_seq_slice_get`, element type
                # `List (List Int)` / row type `List Int` instead of
                # `List Int` / `Int` -- measured the same way as the
                # update/fill pair above, the identical proof script.
                parts.append(
                "theorem t_seq_append_get_row "
                "(l1 l2 : List (List Int)) (j : Int)\n"
                "    (hj : (0 : Int) ≤ j) "
                "(hju : j < (((l1 ++ l2).length : Int))) :\n"
                "    (l1 ++ l2)[(j).toNat]! =\n"
                "      if j < ((l1.length : Int)) then l1[(j).toNat]! "
                "else l2[(j - (l1.length : Int)).toNat]! := by\n"
                "  have hlen : (l1 ++ l2).length = l1.length + l2.length :=\n"
                "    List.length_append\n"
                "  have hbl : (j).toNat < (l1 ++ l2).length := by omega\n"
                "  rw [getElem!_pos (l1 ++ l2) (j).toNat hbl, "
                "List.getElem_append]\n"
                "  split\n"
                "  · next hh =>\n"
                "    rw [if_pos (by omega : j < ((l1.length : Int)))]\n"
                "    have hbl1 : (j).toNat < l1.length := hh\n"
                "    exact (getElem!_pos l1 (j).toNat hbl1).symm\n"
                "  · next hh =>\n"
                "    rw [if_neg (by omega : ¬ j < ((l1.length : Int)))]\n"
                "    have hbl2 : (j).toNat - l1.length < l2.length "
                ":= by omega\n"
                "    have heq : (j).toNat - l1.length "
                "= (j - (l1.length : Int)).toNat := by omega\n"
                "    exact (getElem!_pos l2 ((j).toNat - l1.length) "
                "hbl2).symm."
                "trans\n"
                "      (congrArg (l2[·]!) heq)\n"
                "\n"
                "theorem t_seq_slice_get_row "
                "(s : List (List Int)) (a b j : Int)\n"
                "    (ha : (0 : Int) ≤ a) (hab : a ≤ b) "
                "(hbl : b ≤ ((s.length : Int)))\n"
                "    (hj : (0 : Int) ≤ j) (hju : j < b - a) :\n"
                "    ((s.drop a.toNat).take (b - a).toNat)[(j).toNat]! "
                "= s[(a + j).toNat]! := by\n"
                "  have hb1 : (j).toNat "
                "< ((s.drop a.toNat).take (b - a).toNat).length := by\n"
                "    rw [List.length_take, List.length_drop]\n"
                "    omega\n"
                "  rw [getElem!_pos ((s.drop a.toNat).take (b - a).toNat) "
                "(j).toNat hb1,\n"
                "      List.getElem_take, List.getElem_drop]\n"
                "  have hb2 : (a.toNat + j.toNat) < s.length := by omega\n"
                "  have heq : a.toNat + j.toNat = (a + j).toNat := by omega\n"
                "  rw [← getElem!_pos s (a.toNat + j.toNat) hb2, heq]\n")
            if self.seq_composed_append_slice:
                # THE FRAME-FACT GAP's open list (2026-09-11):
                # splitArray's/splitAndAppend's own `slice ++ slice`, read
                # at any index -- fully generic (both slices' own base
                # seq, bounds and the read index all universally
                # quantified), proved by ONE application of
                # `t_seq_append_get` (splitting on which side the index
                # falls in) followed, per branch, by ONE application of
                # `t_seq_slice_get` -- the exact two-lemma chain across a
                # nested subterm `grind` cannot do on its own, done once
                # here so grind's own e-matching only needs to unify the
                # whole nested `(slice ++ slice)` term against this
                # lemma's LHS. Measured (probe1.lean, lean 4.33.1, core
                # only): compiles clean, axioms {propext, Quot.sound}.
                parts.append(
                "theorem t_seq_append_slice2_get "
                "(s1 s2 : List Int) (a1 b1 a2 b2 j : Int)\n"
                "    (ha1 : (0:Int) ≤ a1) (hab1 : a1 ≤ b1) "
                "(hbl1 : b1 ≤ ((s1.length:Int)))\n"
                "    (ha2 : (0:Int) ≤ a2) (hab2 : a2 ≤ b2) "
                "(hbl2 : b2 ≤ ((s2.length:Int)))\n"
                "    (hj : (0:Int) ≤ j) (hju : j < (b1 - a1) + (b2 - a2)) "
                ":\n"
                "    (((s1.drop a1.toNat).take (b1 - a1).toNat) ++\n"
                "      ((s2.drop a2.toNat).take (b2 - a2).toNat))"
                "[j.toNat]! =\n"
                "      if j < b1 - a1 then s1[(a1 + j).toNat]! "
                "else s2[(a2 + (j - (b1 - a1))).toNat]! := by\n"
                "  have hl1 : ((((s1.drop a1.toNat).take (b1 - a1).toNat))."
                "length : Int) = b1 - a1 := by\n"
                "    rw [List.length_take, List.length_drop]\n"
                "    omega\n"
                "  have hl2 : ((((s2.drop a2.toNat).take (b2 - a2).toNat))."
                "length : Int) = b2 - a2 := by\n"
                "    rw [List.length_take, List.length_drop]\n"
                "    omega\n"
                "  have hju' : j < ((((s1.drop a1.toNat).take "
                "(b1 - a1).toNat) ++ ((s2.drop a2.toNat).take "
                "(b2 - a2).toNat)).length : Int) := by\n"
                "    rw [List.length_append]\n"
                "    push_cast\n"
                "    omega\n"
                "  rw [t_seq_append_get (((s1.drop a1.toNat).take "
                "(b1 - a1).toNat)) (((s2.drop a2.toNat).take "
                "(b2 - a2).toNat)) j hj hju']\n"
                "  split\n"
                "  · next hh =>\n"
                "    rw [if_pos (by rw [hl1] at hh; exact hh)]\n"
                "    rw [t_seq_slice_get s1 a1 b1 j ha1 hab1 hbl1 hj "
                "(by rw [hl1] at hh; exact hh)]\n"
                "  · next hh =>\n"
                "    rw [if_neg (by rw [hl1] at hh; exact hh)]\n"
                "    have hk : ((0:Int) ≤ j - "
                "(((((s1.drop a1.toNat).take (b1 - a1).toNat)).length "
                ": Int))) := by\n"
                "      rw [hl1] at hh; omega\n"
                "    have hku : (j - (((((s1.drop a1.toNat).take "
                "(b1 - a1).toNat)).length : Int))) < b2 - a2 := by\n"
                "      rw [hl1] at hh; omega\n"
                "    rw [t_seq_slice_get s2 a2 b2\n"
                "        (j - (((((s1.drop a1.toNat).take "
                "(b1 - a1).toNat)).length : Int)))\n"
                "        ha2 hab2 hbl2 hk hku]\n"
                "    congr 2\n"
                "    rw [hl1]\n")
        return "\n".join(parts)

    # ---------- the string library (v1) ----------

    def emit_strlib_helpers(self) -> str:
        """SPEC.md "The string library (v1)" (2026-09-11, dated note
        below carries the full measurement): the 17 members as this
        kernel's own definitions, emitted once per file whenever any is
        used (self.strlib), plus the lemmas the three committed tasks'
        proofs need. Measured on lean 4.33.1, core only, no Mathlib (a
        standalone scratch probe, every def and theorem below compiled
        and #eval-checked against interp.py's own worked examples before
        being pasted in here): see the dated note for what is and is not
        proved."""
        if not self.strlib:
            return ""
        return (
"""def t_str_isws (c : Int) : Bool :=
  c == 9 || c == 10 || c == 11 || c == 12 || c == 13 ||
  c == 28 || c == 29 || c == 30 || c == 31 || c == 32

def t_str_isupperletter (c : Int) : Bool := decide (65 ≤ c ∧ c ≤ 90)
def t_str_islowerletter (c : Int) : Bool := decide (97 ≤ c ∧ c ≤ 122)

-- split(s): whitespace runs separate, leading/trailing dropped, no empty
-- row, split("") == [] (SPEC.md); a fold carrying (rows-so-far, current
-- run), flushed at the end.
def t_str_split_ws (s : List Int) : List (List Int) :=
  let step : (List (List Int) × List Int) → Int →
             (List (List Int) × List Int) :=
    fun st c =>
      if t_str_isws c then
        (if st.2.isEmpty then st else (st.1 ++ [st.2], []))
      else
        (st.1, st.2 ++ [c])
  let r := s.foldl step ([], [])
  if r.2.isEmpty then r.1 else r.1 ++ [r.2]

-- split(s, c): every occurrence of c separates, empty rows kept. Defined
-- by structural recursion, PREPENDING to the recursive call's first row
-- (rather than a fold's append-at-the-end), which is what makes
-- t_str_join_split_roundtrip below a plain structural induction: the
-- match's `| [] => [[x]]` arm is unreachable (t_str_split_sep_ne_nil
-- proves the recursive call is always nonempty) but must be given for
-- pattern exhaustiveness.
def t_str_split_sep : List Int → Int → List (List Int)
  | [], _ => [[]]
  | x :: rest, c =>
      match t_str_split_sep rest c with
      | row :: rows => if x == c then [] :: row :: rows else (x :: row) :: rows
      | [] => [[x]]

-- join(rows, sep): sep.join(rows), Python's. Structural on rows, the
-- last row copied through with no trailing sep -- the mirror image of
-- split_sep's structure, which is what makes the roundtrip theorem a
-- one-pass induction rather than needing an append-associativity detour.
def t_str_join : List (List Int) → List Int → List Int
  | [], _ => []
  | [r], _ => r
  | r :: r2 :: rows, sep => r ++ sep ++ t_str_join (r2 :: rows) sep

-- tostr(n): decimal digits, '-' (45) first iff negative. Nat.toDigits is
-- core Lean (not `partial`), so it is kernel-reducible; its own digit
-- characters are already '0'..'9' (48-57), so `.toNat` on each Char IS
-- the ASCII code SPEC.md wants, no further mapping needed.
def t_str_tostr (n : Int) : List Int :=
  let ds : List Int := (Nat.toDigits 10 n.natAbs).map (fun ch => (ch.toNat : Int))
  if n < 0 then 45 :: ds else ds

-- count(s, t): single-code-point t is the case both committed proofs and
-- SPEC.md's own split-length law need, and a one-element pattern can
-- never overlap itself, so elementwise List.filter/length already IS
-- Python's non-overlapping count there -- t_str_count reduces to
-- t_str_count_elem DEFINITIONALLY on a singleton pattern, which is what
-- lets t_str_count_elem_step below carry the loop's invariant with a
-- plain List.filter_append induction instead of count_go's take/drop
-- recursion. t_str_count_go (general t, length >= 2, or t == []) is a
-- straight transcription of interp.py's own scan, well-founded on the
-- scanned list's length; proved total, not proved about beyond that.
def t_str_count_elem (s : List Int) (c : Int) : Int :=
  ((s.filter (· == c)).length : Int)

def t_str_count_go : List Int → List Int → Int
  | [], _ => 0
  | c :: rest, t =>
      if h : t.length = 0 then 1 + t_str_count_go rest t
      else if (c :: rest).take t.length == t then
        1 + t_str_count_go (List.drop t.length (c :: rest)) t
      else
        t_str_count_go rest t
termination_by s _ => s.length
decreasing_by
  · simp [List.length_cons]
  · simp only [List.length_cons, List.length_drop]
    omega
  · simp [List.length_cons]

def t_str_count (s t : List Int) : Int :=
  match t with
  | [] => (s.length : Int) + 1
  | [c] => t_str_count_elem s c
  | _ => t_str_count_go s t

def t_str_find_go : List Int → List Int → Int → Int
  | [], _, _ => -1
  | c :: rest, t, i =>
      if (c :: rest).take t.length == t then i
      else t_str_find_go rest t (i + 1)

def t_str_find (s t : List Int) : Int :=
  if t.isEmpty then 0 else t_str_find_go s t 0

def t_str_lstrip (s : List Int) : List Int :=
  match s with
  | [] => []
  | c :: rest => if t_str_isws c then t_str_lstrip rest else s

def t_str_rstrip (s : List Int) : List Int :=
  (t_str_lstrip s.reverse).reverse

def t_str_strip (s : List Int) : List Int :=
  t_str_rstrip (t_str_lstrip s)

-- replace(s, t, u): every non-overlapping occurrence of t replaced by u,
-- left to right; t == [] inserts u before every code point and at the
-- end (SPEC.md's own words). fuel = s.length bounds the general case's
-- recursion (each step consumes at least one element of s, so this
-- never runs out before the list itself does); a real transcription of
-- interp.py's loop, proved total, not proved about beyond that.
def t_str_replace_go : List Int → List Int → List Int → Nat → List Int
  | [], _, _, _ => []
  | c :: rest, t, u, fuel =>
      match fuel with
      | 0 => c :: rest
      | fuel' + 1 =>
        if t.length = 0 then
          u ++ (c :: t_str_replace_go rest t u fuel')
        else if (c :: rest).take t.length == t then
          u ++ t_str_replace_go (List.drop t.length (c :: rest)) t u fuel'
        else
          c :: t_str_replace_go rest t u fuel'

def t_str_replace (s t u : List Int) : List Int :=
  if t.length = 0 then
    (s.foldr (fun c acc => u ++ c :: acc) []) ++ u
  else
    t_str_replace_go s t u s.length

def t_str_lower (s : List Int) : List Int :=
  s.map (fun c => if t_str_isupperletter c then c + 32 else c)

def t_str_upper (s : List Int) : List Int :=
  s.map (fun c => if t_str_islowerletter c then c - 32 else c)

def t_str_isdigit (s : List Int) : Bool :=
  !s.isEmpty && s.all (fun c => decide (48 ≤ c ∧ c ≤ 57))

def t_str_isalpha (s : List Int) : Bool :=
  !s.isEmpty && s.all (fun c => t_str_isupperletter c || t_str_islowerletter c)

def t_str_isupper (s : List Int) : Bool :=
  (s.any (fun c => t_str_isupperletter c || t_str_islowerletter c)) &&
  !(s.any (fun c => t_str_islowerletter c))

def t_str_islower (s : List Int) : Bool :=
  (s.any (fun c => t_str_isupperletter c || t_str_islowerletter c)) &&
  !(s.any (fun c => t_str_isupperletter c))

def t_str_startswith (s t : List Int) : Bool :=
  s.take t.length == t

def t_str_endswith (s t : List Int) : Bool :=
  decide (t.length ≤ s.length) &&
  (t.isEmpty || (s.drop (s.length - t.length) == t))

-- THE THREE LEMMAS (dated note below): the split length law is NOT
-- proved (open, named there); these are the join-of-split law and the
-- count-against-a-loop step, both measured closing the committed tasks.
theorem t_str_count_elem_step (l : List Int) (x c : Int) :
    t_str_count_elem (l ++ [x]) c = t_str_count_elem l c + (if x == c then 1 else 0) := by
  unfold t_str_count_elem
  rw [List.filter_append, List.length_append]
  by_cases h : x == c
  · simp [h]
  · simp [h]

theorem t_str_count_elem_nonneg (s : List Int) (c : Int) :
    0 ≤ t_str_count_elem s c := by
  unfold t_str_count_elem
  omega

-- count against a loop (dated note below): one more prefix element,
-- Int-toNat cast to match `at`'s own convention (`s[i.toNat]!`) and
-- SPEC.md "Sequences: literals, concatenation, slices"'s `slice(s,0,i)`
-- encoding (`(s.drop 0).take i`). List.take_concat_get is the core
-- lemma that actually carries the one-more-element fact; this restates
-- it in the Int/toNat shape count_vowels' invariant step needs, so
-- grind can chain it straight into t_str_count_elem_step above.
theorem t_str_take_succ_toNat (s : List Int) (i : Int)
    (h0 : 0 ≤ i) (h1 : i < (s.length : Int)) :
    s.take (i + 1).toNat = s.take i.toNat ++ [s[i.toNat]!] := by
  have h : i.toNat < s.length := by omega
  have heq : (i + 1).toNat = i.toNat + 1 := by omega
  rw [heq, ← List.take_concat_get h, List.concat_eq_append,
     getElem!_pos s i.toNat h]

theorem t_str_split_sep_ne_nil (s : List Int) (c : Int) :
    t_str_split_sep s c ≠ [] := by
  cases s with
  | nil => simp [t_str_split_sep]
  | cons x rest =>
      simp only [t_str_split_sep]
      cases t_str_split_sep rest c with
      | nil => simp
      | cons row rows => by_cases hx : x == c <;> simp [hx]

theorem t_str_join_cons_row (h : Int) (row : List Int) (rows : List (List Int))
    (sep : List Int) :
    t_str_join ((h :: row) :: rows) sep = h :: t_str_join (row :: rows) sep := by
  cases rows with
  | nil => simp [t_str_join]
  | cons r2 rows2 => simp [t_str_join]

theorem t_str_join_nil_row (row : List Int) (rows : List (List Int))
    (sep : List Int) :
    t_str_join ([] :: row :: rows) sep = sep ++ t_str_join (row :: rows) sep := by
  simp [t_str_join]

theorem t_str_join_split_roundtrip (s : List Int) (c : Int) :
    t_str_join (t_str_split_sep s c) [c] = s := by
  induction s with
  | nil => simp [t_str_split_sep, t_str_join]
  | cons x rest ih =>
      rcases hs : t_str_split_sep rest c with _ | ⟨row, rows⟩
      · exact absurd hs (t_str_split_sep_ne_nil rest c)
      · rw [hs] at ih
        have hsplit : t_str_split_sep (x :: rest) c =
            if x == c then [] :: row :: rows else (x :: row) :: rows := by
          simp only [t_str_split_sep, hs]
        rw [hsplit]
        by_cases hx : x == c
        · rw [if_pos hx, t_str_join_nil_row, ih]
          have hxc : x = c := by simpa using hx
          simp [hxc]
        · rw [if_neg hx, t_str_join_cons_row, ih]
""")

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
                out.append(self._dec().rstrip("\n"))
            out.append("")
            d = self.dcond(f["body"], {}, dict(ptypes))
            if d is not None:
                tname = f"{f['name']}_s_wf"
                tac = self._close([f["body"]], {}, dict(ptypes),
                                  self._grind_base())
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
            tac = self._close([r], {}, self.types, self._grind_base())
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
            tac = self._close([e], {}, self.types, self._grind_base())
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
        seq_thms = []
        if self.seq_mut:
            seq_thms += [("t_seq_update_get", "seq update-read bridge"),
                        ("t_seq_fill_get", "seq fill-read bridge")]
            if self.nested:
                seq_thms += [("t_seq_update_get_row",
                             "nested seq update-read bridge"),
                            ("t_seq_fill_get_row",
                             "nested seq fill-read bridge")]
            if self.seq_composed_update2:
                seq_thms.append(("t_seq_update2_get",
                                 "composed double-update-read bridge"))
                seq_thms += [("t_seq_update2_get_hi",
                             "composed double-update-read bridge, "
                             "outer-index case"),
                            ("t_seq_update2_get_mid",
                             "composed double-update-read bridge, "
                             "inner-index case"),
                            ("t_seq_update2_get_lo",
                             "composed double-update-read bridge, "
                             "untouched-index case")]
        if self.seq_new:
            seq_thms += [("t_seq_append_get", "seq append-read bridge"),
                        ("t_seq_slice_get", "seq slice-read bridge")]
            if self.nested:
                seq_thms += [("t_seq_append_get_row",
                             "nested seq append-read bridge"),
                            ("t_seq_slice_get_row",
                             "nested seq slice-read bridge")]
            if self.seq_composed_append_slice:
                seq_thms.append(("t_seq_append_slice2_get",
                                 "composed append-of-slices-read bridge"))
        if self.seq_eq_comp:
            seq_thms.append(("t_seq_ext", "seq equality extensionality "
                             "bridge (booleans as computational values)"))
        strlib_src = self.emit_strlib_helpers()
        strlib_thms = []
        if self.strlib:
            strlib_thms = [(n, "string library lemma") for n in STRLIB_LEMMAS]
        sf_src, sf_thms = self.emit_sfuns()
        wf_src, wf_thms, wf_k = self.emit_clause_wfs()
        body = self.body
        n_while = sum(1 for s in body if "while" in s)
        n_all = _count_whiles(body)
        # NESTED AND MULTIPLE LOOPS (2026-09-18, ROADMAP WS-20 move 1):
        # this `raise` was the whole of the move. The test is by COUNT,
        # not by the old `deep_while` scan, because that scan looked only
        # inside the body's non-`while` statements and so never saw a loop
        # nested inside the top-level one at all -- has_duplicate reached
        # `sym`'s own `while` case instead, and abstained there. Exactly
        # one loop, at the top level, still goes to `lower_loop` unchanged.
        if n_all > 1 or (n_all == 1 and n_while == 0):
            if self._self_calls(body):
                raise NotImplementedError(
                    "a loop combined with self-recursion is not lowered "
                    "for lean")
            main = self.lower_loops_general(wf_k)
        elif n_while == 1:
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
        # VACUITY SMOKE (2026-09-11, ROADMAP 13.4/fz_p_vac_unsat,
        # fz_p_vac_range): dafny's --warn-contradictory-assumptions,
        # verus's "vacuous" status, spark's VC_INCONSISTENT_PRE and
        # framac's inconsistent-logic-environment proof all give their
        # kernels a NATIVE signal that `requires` is unsatisfiable at
        # every type-correct input; Lean has none, so one is built here.
        # A second, independent theorem states exactly `requires ->
        # False` over the SAME params/hpre binder the main theorem
        # already uses (pre_conj()/binders() below), never touching the
        # main proof. verifiers/lean.py reads its own post-sentinel
        # `#print axioms` line (the THEOREM_RE scan already picks up any
        # `theorem`, this name included, with no special-casing needed
        # here) to tell vacuous from not: a CLEAN audit line means omega
        # or grind proved False from hpre alone (the precondition holds
        # nowhere), an ABSENT or sorryAx-carrying one means the tactic
        # failed to (satisfiable, not vacuous) -- measured 2026-09-11,
        # `t2.lean` smoke test: a failed declaration still lets Lean
        # print every LATER command's audit line and only replaces that
        # one declaration's own axiom list with sorryAx, so this can
        # never corrupt the main theorem's own audit even when the smoke
        # genuinely (and correctly) fails to prove False.
        smoke_src, smoke_thms = "", []
        if self.task.get("requires"):
            params_nt = [(p["name"], p["type"]) for p in self.task["params"]]
            pb_smoke = self.binders(params_nt)
            smoke_name = f"{self.name}_t_vacuity_smoke"
            smoke_src = (
                f"theorem {smoke_name} {pb_smoke} "
                f"(hpre : {self.pre_conj()}) : False := by\n"
                f"  first\n"
                f"  | omega\n"
                f"  | grind\n")
            smoke_thms = [(smoke_name,
                          "vacuity smoke: is `requires` unsatisfiable")]
        db_src, db_thms = self.emit_divisor_bound()
        prints = "\n".join(
            f"#print axioms {t}" for t, _ in
            db_thms + seq_thms + strlib_thms + sf_thms + wf_thms + thms
            + smoke_thms)
        parts = [header]
        if db_src.strip():
            parts.append(db_src)
        if seq_src.strip():
            parts.append(seq_src)
        if strlib_src.strip():
            parts.append(strlib_src)
        if sf_src.strip():
            parts.append(sf_src)
        if wf_src.strip():
            parts.append(wf_src)
        parts.append(src)
        if smoke_src:
            parts.append(smoke_src)
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
        # THE NONLINEAR SIGN BRIDGE (2026-09-11): every distinct product
        # this task's own ensures/body computes, as its own top-level
        # lemma (see `_mul_sign_lemma`'s docstring) BEFORE the wfbody/
        # spec theorems that will cite it -- Lean elaborates top-down, so
        # a forward reference would not even parse. Empty for every task
        # with no nonlinear `*` node (`_mul_sign_pairs` returns []), so
        # every pre-existing task's output is byte-identical.
        mulsign_pairs = self._mul_sign_pairs()
        mulsign_names = [self.fresh(f"{self.name}_t_mulsign")
                         for _ in mulsign_pairs]
        for nm, (ta, tb) in zip(mulsign_names, mulsign_pairs):
            out.append(self._mul_sign_lemma(nm, ta, tb))
            thms.append((nm, "nonlinear sign bridge"))
        # `grind [name]` alone does NOT work here (measured, probe1/
        # probe2/probe3 scratch files): grind's own `ring` extension
        # ring-normalizes a goal like `3 * n * (n - 1) + 1 >= 0` into a
        # `n ^ 2` MONOMIAL form before e-matching ever runs, so the
        # lemma's own LHS pattern `(3 * n) * (n - 1)` -- stated over the
        # UNNORMALIZED product, to match `term()`'s own output text --
        # no longer occurs as a literal subterm to match against; cutsat
        # then treats the introduced `n ^ 2` atom as an unconstrained
        # integer (measured: it happily assigns `n ^ 2 := -1`) and grind
        # reports failure. `omega`, unlike `grind`, does NOT ring-
        # normalize -- it treats `(3 * n) * (n - 1)` as one opaque atom,
        # matching the mulsign lemma's own conclusion syntactically, so a
        # `have` naming that lemma's instantiation, fed to a plain
        # `omega` afterward, closes it (measured, probe3.lean: `have
        # hsign := t_mulsign_1 n hpre; omega` proves the full `result >=
        # 0 ∧ result = formula` conjunction in one shot, no `constructor`
        # needed -- omega already decomposes a provable `∧` goal itself).
        def _mulsign_have_branch(pre_args: str) -> str:
            haves = "; ".join(
                f"have _sgn{i} := {nm} {pnames}{pre_args}"
                for i, nm in enumerate(mulsign_names))
            return f"({haves}; omega)"
        ob = self._conj(obs)
        if ob is not None:
            hyps = "".join(f"{p} → " for p in self.pre_props())
            tac = self._close([self.body], {}, self.types,
                              self._grind_base())
            if mulsign_names:
                # wfbody states `requires` as CURRIED implications in the
                # goal itself (no `hpre` binder in scope, unlike `_spec`
                # below) -- `intro` them under the names the mulsign
                # lemma's own single conjoined `hpre` argument needs,
                # rebuilt via the anonymous constructor (Lean 4's `⟨⟩`
                # already flattens a right-nested `∧` chain, the exact
                # shape `pre_conj`'s own `" ∧ ".join` produces).
                pre_props = self.pre_props()
                if pre_props:
                    names = [f"_hp{i + 1}" for i in range(len(pre_props))]
                    pre_args = (" ⟨" + ", ".join(names) + "⟩"
                               if len(names) > 1 else f" {names[0]}")
                    branch = ("(intro " + " ".join(names) + "; "
                             + _mulsign_have_branch(pre_args)[1:])
                else:
                    branch = _mulsign_have_branch("")
                tac = f"first | ({tac}) | {branch}"
            out.append(f"theorem {self.name}_t_wfbody {pb} :\n"
                       f"    {hyps}{ob} := by\n  {tac}\n")
            thms.append((f"{self.name}_t_wfbody", "body definedness"))
        applied = f"({self.name}_t {pnames})"
        hpre = (f" (hpre : {self.pre_conj()})"
                if self.task.get("requires") else "")
        spec_tac = self._close([self.task["ensures"], self.body], {},
                               self.types, self._grind_base())
        spec_mulsign_branch = (
            _mulsign_have_branch(" hpre" if self.task.get("requires")
                                 else "")
            if mulsign_names else None)
        # SPEC.md "Pairs" (2026-09-10), found on divmod_pair's own spec
        # theorem: `unfold {name}_t` alone (delta only) leaves a `.1`/`.2`
        # projection ON the unfolded pair literal syntactically un-reduced
        # (`(x / y, x % y).fst`, not `x / y`), which `omega` then treats
        # as an OPAQUE atom distinct from `x / y` itself -- measured
        # directly (a four-line scratch probe: `unfold` alone leaves
        # `omega` unable to prove the goal at all, citing exactly that
        # atom split; `unfold ...; dsimp only` or `simp only [{name}_t]`
        # both close it, since either reduces the projection, iota-
        # reduction `unfold` itself does not perform). `dsimp only` is
        # the one-line fix, ADDED ONLY when the return is a pair (every
        # other return type has no such projection to reduce, so this
        # changes no other task's tactic text). SPEC.md "Nested sequences
        # (v1)": `{"seq": "seq"}` is ALSO a dict, so this same check now
        # also fires for a nested-seq return (`pair_ret`'s name predates
        # that construct) -- harmless there too, measured directly (a
        # scratch probe returning a literal/fill/`+` nested value): the
        # extra `dsimp only` is a no-op on a goal with no projection to
        # reduce, so this changes no task's verdict either way.
        pair_ret = isinstance(self.rett, dict)
        dsimp = "\n     dsimp only" if pair_ret else ""
        out.append(
            f"theorem {self.name}_t_spec {pb}{hpre} :\n"
            f"    {self.post_conj(applied)} := by\n"
            f"  first\n"
            # `try` (2026-09-11, fz_p_modsign_true): `unfold` hard-FAILS
            # (measured: "Tactic `unfold` failed to unfold ... in ...",
            # aborting this whole `first` alternative before the nested
            # `spec_tac` ever runs) whenever `ensures` never mentions the
            # return name -- `post_conj` then never substitutes `applied`
            # in, so `{name}_t` occurs nowhere in the goal to unfold.
            # modsign_true's own ensures IS exactly this shape (`x % y >=
            # 0`, no `r` anywhere): the unconditional `unfold` silently
            # discarded every div/mod bridge alternative `spec_tac`
            # offers, leaving only the bare `grind [name]` fallback below,
            # which cannot derive Euclidean mod facts alone. `try` makes
            # the unfold a no-op exactly when it would have failed
            # (identical to before whenever it succeeds), so `spec_tac`
            # always gets a chance to run either way.
            f"  | (try unfold {self.name}_t{dsimp}\n"
            f"     {spec_tac})\n"
            + (f"  | (try unfold {self.name}_t{dsimp}\n"
               f"     {spec_mulsign_branch})\n"
               if spec_mulsign_branch else "")
            + f"  | grind [{self.name}_t"
            + (", " + ", ".join(f"{f}_s" for f in self.sfuns)
               if self.sfuns else "") + "]\n"
            + ("  | decide\n" if not self.task["params"] else ""))
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
               + self._dec()]
        thms = []
        ob = self._conj(obs)
        if ob is not None:
            hyps = "".join(f"{p} → " for p in self.pre_props())
            out.append(f"theorem {self.name}_t_wfbody {pb} :\n"
                       f"    {hyps}{ob} := by\n  {self._grind_base()}\n")
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
            f"  all_goals {self._grind_base()}\n"
            f"termination_by ({dec}).toNat\n"
            + self._dec())
        thms.append((f"{self.name}_t_spec", "the contract"))
        return "\n".join(out), thms

    def _loop_zero(self, t):
        """A placeholder value for a state var not yet set when the loop
        is entered (SPEC.md "Early exit", 2026-09-08): the case
        `min_max`'s own pair return hits, since `r` is built only in the
        SUFFIX (`r := (lo, hi)`, after the loop, from the loop's own
        final `lo`/`hi`), never assigned in the prefix. Recurses one
        level for a pair (SPEC.md "Pairs", 2026-09-10; v1 has no pair of
        pairs, so one level is all this ever needs), one component at a
        time, so a pair state var gets a well-typed placeholder pair
        instead of crashing the old `dict.get` lookup (a `{"pair": [...]
        }` type is unhashable, so the pre-Pairs `{"int": ..., "bool":
        ...}.get(self.rett)` would raise TypeError, not return None, the
        first time a task gave `self.rett` a dict). A bare `seq` return
        still has no placeholder here, unchanged from before this
        construct: dead in every committed task (`reverse` and
        `filter_pos` both assign `r` in their own prefix), so it is left
        exactly as it read before, an honest refusal if ever hit."""
        if isinstance(t, dict):
            if "pair" in t:
                t1, t2 = t["pair"]
                z1, z2 = self._loop_zero(t1), self._loop_zero(t2)
                return None if z1 is None or z2 is None else f"({z1}, {z2})"
            # SPEC.md "Nested sequences (v1)": `{"seq": "seq"}` is ALSO a
            # dict (unhashable the same way a pair's is), so this branch
            # needs the same guard the pair one got, or an uninitialized
            # nested-seq state var would hit `t["pair"]` and raise a raw
            # KeyError -- the exact crash-vs-refusal defect the pairs
            # wave fixed for `.get`, reopened one level up if left
            # unguarded here. No placeholder for a bare nested seq
            # either, same as the flat "seq" string case below: an
            # honest `NotImplementedError` from the caller if ever hit.
            # Dead in both committed nested tasks (`swap_rows` has no
            # loop at all; `row_max_len`'s nested param `m` is read-only,
            # never loop state).
            return None
        # THE SEQ-TYPED LOCAL ABSTAIN (2026-09-14, lean-closure, this
        # session's own item): a bare "seq" return var not yet set when
        # the loop is entered (307 DeepCopySeq: `copy` is only assigned
        # in the SUFFIX, `copy := newSeq`, never read or written in the
        # prefix or the loop itself) hit the pre-existing `None` here
        # unconditionally, an honest `NotImplementedError` ("state var
        # 'copy' uninitialized before the loop") -- ABSTAIN, never a
        # kernel call. `List Int`'s own canonical placeholder is total
        # and well-typed exactly like `(0 : Int)`/`false` above: the
        # empty list, `([] : List Int)`, provably overwritten before
        # `copy` is ever read (the same "provably overwritten on every
        # path" argument the docstring above already makes for `_ret`).
        # Dead for every other lowering: this placeholder is consulted
        # only when the return var itself is unset entering the loop,
        # true only when the loop's own state-var scan (`lower_loop`,
        # above) already found nothing else to do about it.
        return {"int": "(0 : Int)", "bool": "false",
                "seq": "([] : List Int)"}.get(t)

    @staticmethod
    def _hok_components(n: int) -> list[str]:
        """THE PRESERVATION-HAVE COLLISION's own fix (2026-09-10, third
        pass, below): the `.1`/`.2` projection path into a right-nested
        `hok : P1 ∧ (P2 ∧ (... ∧ Pn))` (Lean's own `∧` associativity,
        exactly what `_conj`'s flat `" ∧ ".join` denotes) that recovers
        each individual `Pi` as a separate named proof, matching what the
        pre-existing per-invariant `hinv{i}` parameter list expects at
        `_t_loop`'s own recursive self-call site. n=1 needs no
        projection at all (`hok : P1` directly)."""
        if n <= 1:
            return ["hok"]
        return ["hok" + ".2" * k + ("" if k == n - 1 else ".1")
                for k in range(n)]

    def _loop_needs_domain_hyp(self, w: dict) -> bool:
        """True iff `_t_loop`'s own bare `decreasing_by` cannot be trusted
        on the guard hypothesis (`_hg`) alone -- this file's own dated
        note below, "THE 14 LOOP-TASK RESIDUAL". SAFE (False, the
        pre-existing lowering, untouched) iff the guard has an order
        conjunct (`<`/`<=`/`>`/`>=`, at top level or inside a top-level
        `and`) whose two operands are EXACTLY `decreases`'s own two
        subtraction operands, in the guard's own direction (`i < len(s)`
        paired with `len(s) - i`, every one of reverse/tail/filter_pos/
        min_max/seq_max/row_max_len/all_nonneg/contains/count_matches/
        first_even/sum_upto/is_prime's own committed shape) -- the ONLY
        pattern measured to make the guard alone already bound the
        measure's direction. Every other shape -- an `ite` (cal_sum,
        linear_search1, minimum, cube), a bare `-` not matching the
        guard's own operands (carre, foo: guard uses `!=`, not an
        order), a sum of two loop variables (slow_max, gcdI), or a bare
        loop variable whose OWN update depends on a second variable the
        guard says nothing about (div_ent_it: `r_v -= b`, decreases
        `r_v`, guard `r_v >= b` bounds `r_v` but never `b`'s sign, so
        `r_v - b < r_v` genuinely needs `b > 0` from the invariant, not
        the guard) -- answers True. digit_sum's own bare `m` (guard `m >
        0`, body `m := m / 10`) was a MEASURED near-miss, ORIGINALLY (THE
        DOMAIN HYPOTHESIS, 2026-09-10) deliberately NOT special-cased:
        needing no invariant fact (`m > 0` alone gives `m / 10 < m`), but
        nothing in the guard/decreases SHAPE ALONE (body-blind) told it
        apart from div_ent_it's identically-shaped one (a bare decreases
        variable, directly guard-bounded) without inspecting the BODY's
        own update -- so the cheap rule answered True for both, uniformly,
        deliberately paying the (harmless, since digit_sum's own twin
        happened to still preserve every invariant) cost of threading
        domain hyp where it added nothing.

        THE SELF-DIVISION SAFE CASE below (2026-09-10, second pass) does
        the body inspection this note originally declined: extra_mod/mod's
        own twin (a `collapse-if` mutation INSIDE the loop body) measured
        that "harmless" assumption false -- threading domain hyp forces
        `_t_loop`'s own recursive definition to prove each invariant's
        preservation for ALL states satisfying the (possibly-mutated)
        hypothesis set, and a twin whose mutation genuinely breaks one
        (which is the entire point of many mutation classes) makes that
        proof obligation FALSE, not just hard: `_t_loop`'s own def then
        fails to elaborate (`sorryAx`), poisoning everything built on it
        (measured: extra_mod's twin read verified/UNPROVED, not REFUTED,
        the certificate itself audited `[sorryAx]`). Checking the body's
        actual update to the decreases variable (below) costs nothing
        extra measured (`_var_writes`, a plain walk) and correctly still
        answers True for div_ent_it (`r_v -= b`, a VARIABLE operand, not a
        literal) while answering False for digit_sum AND extra_mod alike
        (`m / 10`, `k / 2`, both `v op literal`), skipping the domain-hyp
        machinery for both -- restoring extra_mod without narrowing
        div_ent_it's own genuine need at all."""
        guard, dec = w["cond"], w["decreases"]
        conjuncts = (guard["args"]
                    if isinstance(guard, dict) and guard.get("op") == "and"
                    else [guard])
        for g in conjuncts:
            if not (isinstance(g, dict) and g.get("op") in CMP_OPS):
                continue
            ga, gb = g["args"]
            if not (isinstance(dec, dict) and dec.get("op") == "-"):
                continue
            a, b = dec["args"]
            if g["op"] in ("<", "<=") and (a, b) == (gb, ga):
                return False
            if g["op"] in (">", ">=") and (a, b) == (ga, gb):
                return False
        # SELF-DIVISION SAFE CASE (2026-09-10, second pass, "THE
        # PRESERVATION-HAVE COLLISION" below): the body-inspection this
        # docstring's own comment above declined to do, done narrowly.
        # `dec` a bare variable v, the guard bounding v against a LITERAL
        # (v > c / v >= c, top level or in a top-level `and` -- exactly
        # digit_sum's and extra_mod/mod's own shape), and the loop body's
        # ONLY write to v anywhere in it (top level or nested, checked
        # below so a conditional second write cannot hide from this) is
        # `v := v - lit` or `v := v div lit` for a literal `lit` (>= 1 for
        # `-`, >= 2 for `div`): both make v's own new value strictly
        # smaller than its old one for ANY v, no invariant fact needed
        # (`x - lit < x` unconditionally once lit >= 1; `x div lit < x`
        # once `x > 0` and `lit >= 2`, and `_hg` already supplies that
        # `x > 0`, or something at least as strong, whenever the guard
        # matched above). This is exactly what tells div_ent_it's own
        # near-identical shape (bare `r_v`, guard `r_v >= b`) apart: `b`
        # is a variable there, not a literal, so the guard-match below
        # answers False for it and this safe case does not fire, leaving
        # `needs_hyp` True, unchanged.
        if isinstance(dec, dict) and "var" in dec and "op" not in dec:
            dv = dec["var"]
            bounded = any(
                isinstance(g, dict) and g.get("op") in (">", ">=")
                and isinstance(g["args"][0], dict)
                and g["args"][0].get("var") == dv
                and isinstance(g["args"][1], dict) and "int" in g["args"][1]
                for g in conjuncts)
            if bounded:
                writes = _var_writes(w["body"], dv)
                if len(writes) == 1:
                    val = writes[0]
                    if (isinstance(val, dict) and val.get("op") in ("-", "div")
                            and isinstance(val.get("args"), list)
                            and len(val["args"]) == 2
                            and isinstance(val["args"][0], dict)
                            and val["args"][0].get("var") == dv
                            and isinstance(val["args"][1], dict)
                            and "int" in val["args"][1]):
                        lit = val["args"][1]["int"]
                        if ((val["op"] == "-" and lit >= 1)
                                or (val["op"] == "div" and lit >= 2)):
                            return False
        return True

    # THE CUBE NONLINEARITY (2026-09-10, second pass, "THE 14 LOOP-TASK
    # RESIDUAL"'s own sole holdout above): cube's own `c >= 0` (c tracking
    # i^3) preservation across `c := c + k` needs `i >= 1 -> i^3 >= 0`
    # (concretely, given the loop's own OTHER preserved invariant `c + k =
    # (i+1)*(i+1)*(i+1)`, `(i+1) >= 0 -> (i+1)^3 >= 0`), plain nonlinear
    # sign reasoning `grind`'s linear cutsat core cannot do (measured:
    # cutsat reports a real counterexample, c := -1, i.e. it is not
    # under-searching, it genuinely lacks the theory) and this file has no
    # Mathlib `nlinarith`-style bridge for. `Int.mul_nonneg : 0 <= a -> 0
    # <= b -> 0 <= a * b` IS in core Lean (measured, a three-line scratch
    # probe: `example (a b : Int) (ha : 0 <= a) (hb : 0 <= b) : 0 <= a * b
    # := Int.mul_nonneg ha hb` compiles clean, no Mathlib import) and
    # closes it by hand once the right product is named.
    #
    # GENERIC, not cube-specific: built over every INT-typed loop state
    # variable, both its OLD value and its symbolically-updated NEW one
    # (`env_b`'s own substitution -- the exact term text each invariant's
    # own preservation goal already carries for that variable, so the
    # atom this builds is syntactically the SAME one grind needs to
    # recognize, e.g. `(i + 1) * (i + 1) * (i + 1)` matching `_hinv2'`'s
    # own RHS verbatim). For each candidate term `x`: `0 <= x`, `0 <= x *
    # x` and `0 <= x * x * x`, each proved by `Int.mul_nonneg` chained
    # over a SELF-CONTAINED `by omega` (never a shared named hypothesis),
    # each wrapped in `try`: one candidate `x` not actually provable
    # nonneg from context (most of them, for most tasks -- `c` itself
    # here, signed in general) just fails that one `have` and moves on,
    # costing nothing else in the block.
    #
    # Appended as one more `first`-alternative on every loop invariant-
    # preservation proof, UNCONDITIONALLY -- not gated behind a new
    # capability flag, matching the "LOOP TERMINATION MEASURE +1"
    # precedent above: a `first`-alternative never reached because an
    # earlier one already succeeded costs nothing at every task that does
    # not need it (measured on the regression below: every already-
    # passing loop task's invariant-preservation proof still closes on
    # its FIRST alternative, unchanged).
    def _nonneg_bridge_lines(self, state: list, env_b: dict,
                             types: dict) -> list[str]:
        seen: set = set()
        terms: list[str] = []
        for v in state:
            if types.get(v) != "int":
                continue
            for t in (v, env_b.get(v, v)):
                if t not in seen:
                    seen.add(t)
                    terms.append(t)
        lines = []
        for i, t in enumerate(terms):
            lines.append(f"try have _nnb{i}a : (0:Int) ≤ ({t}) := by omega")
            lines.append(f"try have _nnb{i}b : (0:Int) ≤ ({t}) * ({t}) := "
                         f"Int.mul_nonneg (by omega) (by omega)")
            lines.append(f"try have _nnb{i}c : (0:Int) ≤ ({t}) * ({t}) * ({t}) "
                         f":= Int.mul_nonneg (Int.mul_nonneg (by omega) "
                         f"(by omega)) (by omega)")
        return lines

    # THE PARAM-STATE PRODUCT GAP (2026-09-15, lean-sole's own item,
    # "the nine sole-blocked rows"): pow's own `_t_loop_spec` preservation
    # step needs `0 <= a * x` (a a PARAM, x the accumulator loop-state
    # variable, both nonneg by the invariants/`requires` in scope) to
    # discharge `hinv3`'s recursive-call instance -- measured directly
    # (`lean -DmaxHeartbeats=400000` on the emitted file: `grind` reports
    # a genuine satisfying assignment for the negation, `a := 0, x := 0`
    # is a real countermodel to the NEGATED goal only because grind's
    # linear cutsat core has no theory relating a product's sign to its
    # two factors' -- the identical class "THE CUBE NONLINEARITY" above
    # names, but between TWO DISTINCT terms, one of them a bare PARAM
    # `_nonneg_bridge_lines` never sees (it only ever walks `state`, a
    # loop's own local variables, never `self.task["params"]`).
    #
    # ONLY BARE ATOMS, never a substituted (env_b) new-state term (2026-
    # 09-15, found chasing factorial's own residual after the first pass
    # here paired NEW-state terms too, e.g. `res`'s own update `i * res`):
    # a recursive-call obligation like `_t_loop_spec`'s own `hinv3` reads,
    # AFTER substitution, `i * res >= 0` where `i`/`res` are already the
    # CURRENT scope's bare names (the invariant `res >= 0` instantiated at
    # the call's actual argument expression, which for `res` IS `i * res`
    # textually) -- so the two FACTORS this goal is actually built from
    # are always bare params/state vars, and pairing bare atoms alone
    # already produces the needed fact (`i`, `res` both bare, paired
    # directly). Pairing the SUBSTITUTED term itself as a factor (the
    # first version of this fix) is unsound as a `by omega` side
    # condition to begin with (`0 <= i * res` is exactly as nonlinear as
    # the goal it is meant to help discharge -- omega cannot prove it,
    # so that `have` silently fails under `try` and contributes nothing),
    # so bare atoms are both necessary and sufficient here; dropping the
    # substituted forms only removes dead alternatives, never a live one.
    #
    # BOTH multiplication orders (2026-09-15, same pass): `Int.mul_nonneg
    # ha hb`'s conclusion is `0 <= t1 * t2` in the SOURCE order of its two
    # proof arguments, a syntactically different term from `t2 * t1` --
    # measured directly (factorial's own goal is `i * res`, the have from
    # the (res, i) pair alone read `res * i`, and `grind` left the goal
    # unsolved rather than normalizing the commutation on its own). Each
    # unordered pair is therefore emitted as two independent `try have`s.
    #
    # Wired into `then_tac`'s own recursive-apply closer (below) as one
    # more `first`-alternative AFTER the pre-existing `self._gr()`, so
    # every already-closing goal keeps closing on that same first
    # alternative, unchanged; only a goal `self._gr()` alone could not
    # close gets the extra `try have`s in scope before a second `self._gr()`
    # attempt. Measured (t/grade.py, lean+dafny, flake 3, this session's
    # own dated note below carries the regression run): the 34 committed
    # tasks' own loop cells are unaffected (none reach this second
    # alternative, `self._gr()` alone already closed every one of them).
    def _param_state_bridge_lines(self, state: list, types: dict) -> list[str]:
        terms: list[str] = []
        seen: set = set()
        for p in self.task["params"]:
            if p["type"] == "int" and p["name"] not in seen:
                seen.add(p["name"])
                terms.append(p["name"])
        for v in state:
            if types.get(v) == "int" and v not in seen:
                seen.add(v)
                terms.append(v)
        lines = []
        for i, t1 in enumerate(terms):
            for j, t2 in enumerate(terms[i:], start=i):
                lines.append(
                    f"try have _mpb{i}_{j}a : (0:Int) ≤ ({t1}) * ({t2}) "
                    f":= Int.mul_nonneg (by omega) (by omega)")
                if t1 != t2:
                    lines.append(
                        f"try have _mpb{i}_{j}b : (0:Int) ≤ ({t2}) * ({t1}) "
                        f":= Int.mul_nonneg (by omega) (by omega)")
        return lines

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
                zero = self._loop_zero(self.rett) if v == self.ret else None
                if zero is None:
                    raise NotImplementedError(
                        f"state var {v!r} uninitialized before the loop")
                env0[v] = zero
        state_nt = [(v, types[v]) for v in state]
        sb = self.binders(state_nt)
        snames = " ".join(state)
        pb = self.binders(params_nt)

        invs = list(w.get("invariants", []))
        # DIVISOR-BOUND LEMMA (2026-09-12, ROADMAP 16.2, lean's own item):
        # `self._divisor_bound_plan` (computed once, at __init__ time --
        # see its own docstring there for why) recognizes the trial-
        # divide-to-half family (isNonPrime task 3, isPrime 605); where it
        # matched, the extra invariant `i <= n/2 + 1` is appended to
        # `invs` HERE, before every downstream consumer (`inv_props`,
        # `hinvs`, `init_hinv_pfs`, the preservation goal) reads it -- so
        # it flows through the SAME generic per-invariant machinery every
        # STATED invariant already gets (entry proof, preservation proof,
        # `hinv{k}` parameter), never a special case threaded by hand
        # through this function's own many branches. It is never assumed:
        # both obligations (`2 <= n/2 + 1` at entry, `i+1 <= n/2+1` from
        # the guard `i <= n/2` at the recursive step) are plain linear
        # facts about Lean's own constant-divisor `/2` that `omega`
        # (inside the generic `(by {self._gr()})` every invariant's
        # entry/preservation proof already uses) discharges unaided --
        # measured directly (probediv7.lean-style scratch probe): this
        # loop invariant needs no hint beyond what every other
        # invariant's own proof site already tries.
        if self._divisor_bound_plan is not None:
            i_name = self._divisor_bound_plan["i_name"]
            n_expr = self._divisor_bound_plan["dividend"]
            invs.append({"op": "<=", "args": [
                {"var": i_name},
                {"op": "+", "args": [
                    {"op": "div", "args": [n_expr, {"int": 2}]},
                    {"int": 1}]}]})
        # THE DOMAIN HYPOTHESIS (2026-09-10, "THE 14 LOOP-TASK RESIDUAL",
        # this file's own dated note below): `_t_loop`'s bare recursive
        # definition previously carried only the guard (`_hg`) into its own
        # `decreasing_by` -- never `requires` or the loop's own invariants
        # -- so a `decreases` idiom whose well-foundedness genuinely needs
        # an invariant fact (not just the guard) was a FALSE termination
        # goal as lowered, not an under-searched one. Fixed by threading
        # `hpre`/`hinv1..N` through as explicit parameters of `_t_loop`
        # itself (and, since establishing them at entry needs `hpre`, of
        # `_t` too), mirroring the RECURSIVE shape's own existing
        # convention (`lower_rec`'s `hpre_def`): the same two proof
        # obligations `_t_loop_spec`/`_t_spec` already discharge (entry
        # establishment, preservation across one step), reused verbatim.
        # GATED (2026-09-10, MEASURED as a regression, not a hunch):
        # threading this unconditionally onto EVERY loop task broke
        # three already-passing committed invariant-drop twins (reverse,
        # min_max, linear_search) -- their own guard already bounds the
        # measure (`_loop_needs_domain_hyp` reads False), so `_t_loop`
        # never needed a real preservation proof of its own before,
        # and forcing one made it demand a fact the twin's OWN dropped
        # invariant carried (reverse: `len(r) = len(s)`, needed to
        # bridge a `.set` read after the drop, genuinely absent from the
        # surviving invariants -- a live, ground counterexample `r = []`,
        # `s = [x]` satisfies every remaining hypothesis and refutes the
        # goal, not a tactic gap), so `_t_loop`'s own definition failed
        # to elaborate and its `sorryAx` poisoned the certificate that
        # unfolds it (`t_refutation_certificate` itself audited
        # `[sorryAx]`, UNPROVED not REFUTED). `needs_hyp` restricts this
        # wave's whole mechanism to loop tasks whose OWN termination
        # proof actually needs it, so every task the guard alone already
        # covers keeps its exact prior `_t_loop`/`_t` text, byte-
        # identical, immune to this failure mode by construction (a
        # dropped invariant not threaded into `_t_loop` at all cannot
        # be missed there).
        needs_hyp = self._loop_needs_domain_hyp(w)
        pre_hyps = self.pre_props()
        has_pre = bool(pre_hyps) and needs_hyp
        inv_props = [self.prop(iv, {}, types) for iv in invs]
        hpre_p = f" (hpre : {self.pre_conj()})" if has_pre else ""
        hinv_p = ("".join(f" (hinv{i + 1} : {p})"
                          for i, p in enumerate(inv_props))
                  if needs_hyp else "")
        hpre_a = " hpre" if has_pre else ""
        # SPEC.md "Pairs" (2026-09-10)'s own `n_top_ifs`/`split_tac`
        # (below, at `_t_loop_spec`) computed early too: the recursive
        # call's own per-invariant preservation proof (inside `_t_loop`'s
        # definition, below) can hit the identical merged-if-updates shape
        # `_t_loop_spec`'s own preservation step needed `repeat (all_goals
        # split)` for (min_max's two top-level ifs) -- `rec_args`
        # substituted into an invariant's own Prop can carry the same
        # Lean `if`s a merged if-update produces, so the same guard
        # applies here, not just at the theorem.
        n_top_ifs = sum(1 for s in w["body"] if "if" in s)
        split_tac = ("repeat (all_goals split)" if n_top_ifs >= 2
                    else "repeat split")
        # the entry-establishment proof, one per invariant, the same
        # existential-witness fallback `_t_spec`'s own `init_pfs` below
        # needs (measured on seq_max's own `∃ j ∈ [0,1)`, "Existential-
        # invariant establishment" above): shared verbatim by `_t`'s own
        # definition (below) and `_t_spec`'s proof term (`init_pfs`,
        # further down), so both prove the identical goal the identical
        # way, not two independently-written tactics that could drift.
        init_hinv_pfs = []
        for iv in invs:
            if "exists" in iv:
                lo0 = self.term(iv["exists"]["lo"], env0, types)
                init_hinv_pfs.append(f"(by first | {self._gr()} | "
                                     f"exact ⟨{lo0}, by {self._gr()}⟩)")
            else:
                init_hinv_pfs.append(f"(by {self._gr()})")
        hinv_init_a = "".join(f" {p}" for p in init_hinv_pfs)
        guard_p = self.prop(w["cond"], {}, types)
        guard_d = self.dcond(w["cond"], {}, types)
        env_b, obs_body, ret_cond = self.sym(w["body"], {}, dict(types),
                                             state)
        has_return = ret_cond != "False"
        rec_args = " ".join(env_b.get(v, v) for v in state)
        # THE HAVE-BINDING WORKAROUND (2026-09-10). Two DISTINCT Lean
        # surprises, both measured directly on scratch probes before
        # trusting either fix generically:
        #
        # (1) the natural rendering of the preservation proof -- one
        # `(by tac)` term per invariant, tacked directly onto `_t_loop`'s
        # own recursive self-call as extra arguments -- TYPECHECKS (a
        # `def`'s recursive-call argument position accepts a `by` term
        # like any other) but LEAVES THE GOAL UNSOLVED for a tactic that
        # provably closes the IDENTICAL goal (same hypotheses, same
        # conclusion) posed as a plain `example`/`theorem`. Isolated to a
        # parser precedence bug, not the recursive position itself
        # (measured: the same failure reproduces in a NON-recursive
        # `def`, and in a `theorem`'s own tactic block): `by {split_tac};
        # {gr}` on one line parses as `by ({split_tac}; {gr})`, not `by
        # ({split_tac}); {gr}`, and `{split_tac}` (`repeat split`) has
        # nothing to split for a plain arithmetic/div invariant goal, so
        # it FAILS outright on its first attempt -- the compound `split;
        # grind` then fails at that very first step, and `repeat` stops
        # having run `grind` not even once, leaving the goal exactly as
        # unsolved as it started. Fixed two ways together: binding each
        # invariant's preservation proof as a `have` in the guard-true
        # branch BEFORE the recursive call (`_hinv{i}'`), passing the
        # bound NAMES rather than raw `by` terms as the call's own
        # trailing arguments (mirrors `_t_loop_spec`'s own working `apply
        # ... <;> gr` shape, generalized to term mode); and
        # parenthesizing `{split_tac}` at every one-line `by` site.
        #
        # (2) an EXISTENTIAL invariant's own preservation (minimum's own
        # `∃ i, ... ∧ m = a[i]`, a running-extremum witness) still fails
        # after (1)'s fix, split or not: `grind` cannot find the new
        # witness itself when the invariant's value expression is a
        # merged if-update (`if a[n] < m then a[n] else m`) -- measured
        # directly (a scratch probe matching minimum's own goal
        # verbatim): plain `grind`, `split; grind`, and `split; all_goals
        # grind` on the RAW (still-existential) hypothesis all fail the
        # same way, but `obtain`-ing the witness out of the OLD
        # existential invariant FIRST (so its value is a concrete local
        # rather than a bound `∃`) then splitting then grinding succeeds
        # -- grind can chain a concrete witness (`n` on the update
        # branch, the just-`obtain`ed old one on the skip branch) through
        # E-matching once it is a plain local, not when it still has to
        # invent one from an opaque `∃`. Every existential invariant's
        # own grammar (`term()`'s "exists" case above) is exactly
        # `∃ b, lo ≤ b ∧ b < hi ∧ body`, three conjuncts always, so the
        # destructuring pattern is fixed shape (`⟨_, _, _, _⟩`, names
        # discarded since `grind` reads the local context regardless of
        # accessibility) -- applied to every invariant hypothesis that is
        # itself existential, prepended to EVERY per-invariant `have`
        # (harmless, not just the existential one's own: an unrelated
        # `obtain` on a true hypothesis costs nothing and several
        # invariants can legitimately need each other's witnesses).
        # (3), found chasing (2)'s own fix: `{split_tac}` (`repeat
        # split`) on minimum's merged if-update leaves TWO goals
        # (isTrue, isFalse), and a bare `{gr}` after it only closes the
        # FIRST -- the second reads unsolved, not because the tactic is
        # too weak for it (the SAME `grind` closes it fine on its own,
        # measured directly) but because nothing was ever asked to run
        # on it. `all_goals {gr}` fixes it at either call shape (a
        # `;`-chained one-liner or newline-sequenced); newline-sequenced
        # is used here regardless, matching the multi-line tactic style
        # the rest of this file already uses for anything past one step
        # (`_t_loop_spec`'s own proof, just below).
        if needs_hyp:
            hinv_names = [f"_hinv{i + 1}'" for i in range(len(inv_props))]
            obtain_lines = [f"obtain ⟨_, _, _, _⟩ := hinv{i + 1}"
                            for i, iv in enumerate(invs) if "exists" in iv]
            # THE CUBE NONLINEARITY (2026-09-10, second pass): the base
            # `split_tac; all_goals gr` step, tried FIRST unchanged (so
            # every already-passing task closes exactly as before, on
            # this same alternative); `_nonneg_bridge_lines` (above) only
            # when non-empty (an INT-typed piece of loop state present at
            # all), as a second `first`-alternative, reached only when
            # the base one fails.
            nonneg_lines = self._nonneg_bridge_lines(state, env_b, types)
            obtain_block = "".join(f"      {ln}\n" for ln in obtain_lines)
            if nonneg_lines:
                have_body = (
                    obtain_block
                    + "      first\n"
                    f"      | {split_tac}\n"
                    f"        all_goals {self._gr()}\n"
                    "      | " + "\n        ".join(nonneg_lines) + "\n"
                    f"        {split_tac}\n"
                    f"        all_goals {self._gr()}\n")
            else:
                have_body = (obtain_block
                            + f"      {split_tac}\n"
                            f"      all_goals {self._gr()}\n")
            hinv_haves = "".join(
                f"have {hinv_names[i]} : {self.prop(iv, env_b, types)} "
                f":= by\n" + have_body + "    "
                for i, iv in enumerate(invs))
            hinv_call = "".join(f" {n}" for n in hinv_names)
            # THE PRESERVATION-HAVE COLLISION (2026-09-10, third pass,
            # downWhileNotEqual, this file's own dated note below): the
            # `have {hinv}' : P := by tac` shape above ASSERTS P as a
            # theorem of `_t_loop`'s own recursive definition -- true for
            # every REAL program (the invariant genuinely holds at every
            # reachable state) but for a twin whose mutation breaks true
            # preservation, P is a genuinely FALSE goal for some state
            # satisfying the (possibly-mutated) parameter hypotheses, no
            # tactic can close it, Lean auto-inserts `sorryAx`, and that
            # poisons `_t_loop` itself (and everything built on it,
            # including the refutation certificate) -- UNPROVED, never
            # REFUTED, silently. Fixed by DECIDING P instead of PROVING
            # it: `if hok : P then <recurse, using hok's own components>
            # else <a total placeholder, self._loop_zero(self.rett)>`.
            # `P`'s only constructors here are Int order/equality and
            # `∧` (never a raw `∃`/`∀`, gated below), so `Decidable P` is
            # automatic core-Lean typeclass search, no proof term needed
            # at the `dite` itself -- the "then"/"else" split moves
            # entirely into `_t_loop_spec`'s OWN proof (below,
            # `then_tac`'s fallback branch): the "then" case still
            # recurses exactly as `apply {self}_t_loop_spec <;> grind`
            # already does (Prop-irrelevance means it does not care that
            # the argument is `hok`'s own projection rather than a
            # freshly-proved `have`), and the "else" case's goal is
            # closed by `grind` finding the SAME contradiction the old
            # `have`'s tactic would have needed to prove directly (`hok :
            # ¬P` together with the theorem's own REAL `hinv{i}` and the
            # guard `_hg` are jointly inconsistent whenever this branch
            # is reached from a genuinely-true invariant, the only way
            # `_t_loop_spec` is ever invoked) -- the identical
            # implication, proved as its contrapositive instead of
            # directly, equally within `grind`'s linear-arithmetic reach.
            # Gated to exactly the shapes this is measured sound for:
            # `_loop_zero` must produce a placeholder for `self.rett` at
            # all (a bare `seq` return has none, `_loop_zero`'s own
            # docstring above), and no invariant here is quantified at
            # all -- MEASURED, not just the `∃` case originally named:
            # a scratch probe of minimum's own twin (`invariant-drop#1`,
            # which drops its `∃` invariant but keeps its `∀` one) hit
            # `failed to synthesize instance of type class Decidable
            # (... ∧ ∀ i, ...)` at `_t_loop`'s own `if hok :` line --
            # `Decidable` for a raw unbounded-Int `∀` is exactly as
            # unavailable in core Lean as it is for `∃` (no Fintype/
            # Mathlib bridge here), so BOTH quantifier shapes are
            # excluded, not only the one this file's earlier note named.
            # linear_search1's own `∀`-shaped second invariant would hit
            # the identical wall un-gated (measured the same way,
            # re-running the regression below caught it). Left to the
            # pre-existing `have`-based path unchanged either way --
            # minimum's and linear_search1's own committed shapes are
            # the two this excludes, untouched by this change.
            # SECOND scope cut, also MEASURED not assumed: `dite_cond`
            # conjoins every invariant into ONE goal, so `grind` must
            # prove (or refute) the WHOLE conjunction at once -- losing
            # the per-invariant compositionality the pre-existing `have`
            # path relies on (five SEPARATE `have`s for cube, each its
            # own easy goal). A scratch probe of cube's own else-branch
            # goal, verbatim, with the identical nonneg bridge already
            # injected, still left it unsolved: `c + k = (i+1)*(i+1)*
            # (i+1)` needs ring EXPANSION grind finds fine as an ISOLATED
            # equality goal (the old per-invariant `have`) but not as one
            # conjunct among five in a single combined goal. gcdI's three
            # tasks hit the analogous wall on `gcd_s` unfolding depth.
            # Restricting `can_dite` to exactly ONE invariant sidesteps
            # this whole class rather than half-fixing it: every measured
            # multi-invariant needs_hyp task (cube x2, gcdI x3, plus
            # minimum/linear_search1 already excluded above) falls back
            # to the untouched `have`-based path; every measured single-
            # invariant one (downWhileNotEqual, cal_sum, slow_max, carre,
            # foo, div_ent_it) keeps using the new dite path, measured
            # below to still count. A real fix for the multi-invariant
            # case would decide-and-fall-back PER INVARIANT (nested
            # dites, one per `hinv`) rather than on one conjunction --
            # sound in principle, not built here: this pass's own budget
            # went to landing THE TARGET's own downWhileNotEqual, not to
            # re-deriving five more per-invariant proof shapes untested.
            post_inv_props = [self.prop(iv, env_b, types) for iv in invs]
            dite_cond = self._conj(post_inv_props)
            placeholder = self._loop_zero(self.rett)
            can_dite = (dite_cond is not None and placeholder is not None
                       and len(inv_props) == 1
                       and not any("exists" in iv or "forall" in iv
                                  for iv in invs))
            if can_dite:
                hok_comps = self._hok_components(len(inv_props))
                hok_call = "".join(f" {c}" for c in hok_comps)
                rec_call = (f"if hok : {dite_cond} then\n"
                           f"      {self.name}_t_loop {pnames} {rec_args}"
                           f"{hpre_a}{hok_call}\n"
                           f"    else\n"
                           f"      {placeholder}")
                # THE PRESERVATION-HAVE COLLISION's own else-branch closer
                # (2026-09-10, third pass): `_t_loop_spec`'s proof (below,
                # `then_tac`) must close the `hok : ¬P` goal too, and that
                # needs the IDENTICAL tactic power `have_body` above already
                # carries (`grind{self.ga}` alone, or the nonneg bridge as a
                # second alternative) -- MEASURED, not assumed: a first cut
                # using plain `grind{self.ga}` regressed both cube tasks
                # (the nonlinear `c >= 0` contrapositive needs the same
                # `Int.mul_nonneg` chain the forward direction did, `grind`s
                # cutsat has no more nonlinear reach proving False than it
                # had proving the original goal) AND gcdI's three tasks (a
                # `gcd_s g x = gcd_s m n` contrapositive needs the SAME
                # `[gcd_s]` unfold depth `have_body`'s own `grind [gcd_s]`
                # already gets via `self._gr()`, which the bare fallback
                # dropped by not sharing `have_body`'s own alternative).
                # Built inline (`;`-joined, one line) rather than reusing
                # `have_body`'s newline-indented text verbatim: `then_tac`
                # is itself a single-line `first | ... | ...` (matching
                # every existing call site in this file), and semicolon-
                # sequencing every `try have`/`split`/`grind` step is
                # exactly as valid Lean4 tactic syntax as the multi-line
                # form, with no offside-rule risk from splicing a
                # differently-indented block into a new context.
                #
                # `({split_tac}); (all_goals {gr})` -- TWO separately
                # parenthesized groups, not one `({split_tac}; all_goals
                # {gr})` -- is THE HAVE-BINDING WORKAROUND's own bug
                # again, re-found here the hard way (a scratch probe on
                # this exact downWhileNotEqual shape, `case isTrue.isFalse
                # => (repeat split; all_goals grind)`, left a TRIVIAL `0 =
                # 0` goal UNSOLVED; splitting the same text into two
                # parenthesized groups joined by an outer `;` closed it
                # instantly): `repeat X; Y` parses as `repeat (X; Y)`, not
                # `(repeat X); Y`, so `split`'s own failure (nothing left
                # to split once `repeat split` already ran once in the
                # ENCLOSING tactic block, before `then_tac` even starts)
                # fails the WHOLE compound on its first attempt, and
                # `repeat` swallows that as "0 successful iterations" and
                # moves on with the goal untouched -- the file's own
                # standing docstring named the identical trap for a `have`
                # site; this is the SAME trap at a `first`-alternative
                # site instead, unmeasured there until this pass.
                if nonneg_lines:
                    nonneg_inline = "; ".join(nonneg_lines)
                    dite_else_tac = (
                        f"(first | (({split_tac}); (all_goals {self._gr()})) "
                        f"| (({nonneg_inline}); ({split_tac}); "
                        f"(all_goals {self._gr()})))")
                else:
                    dite_else_tac = (f"(({split_tac}); "
                                     f"(all_goals {self._gr()}))")
            else:
                rec_call = (f"{hinv_haves}{self.name}_t_loop {pnames} "
                           f"{rec_args}{hpre_a}{hinv_call}")
                dite_else_tac = None
        else:
            # the pre-existing, untouched shape: no domain hypothesis,
            # so no preservation proof for `_t_loop`'s OWN definition to
            # carry at all -- see `needs_hyp`'s own note above.
            rec_call = f"{self.name}_t_loop {pnames} {rec_args}"
            can_dite = False
            dite_else_tac = None
        dec = self.term(w["decreases"], {}, types)
        # LOOP TERMINATION MEASURE, +1 (2026-09-10): `_t_loop`'s bare
        # decreasing_by carries only the guard hypothesis (`_hg`), never
        # the invariants -- see "THE DECREASING-BY GAP" and the "NOT
        # CLOSED" note above for the (still-open) class where the guard
        # alone cannot bound the measure's DIRECTION. A distinct, narrower
        # class measured today, first on the twin of
        # se2011_tmp_tmp71eb82zt_ass1_ex4__eval (a compare-flip mutation,
        # guard `y >= 0` where the real program's guard is `y > 0`): the
        # measure's own DIRECTION is fine (`_hg` alone proves the new
        # value is smaller), but `(dec).toNat` clamps every value <= 0 to
        # 0, so the LAST guard-true step (old `y = 0`, new `y = -1`) has
        # old.toNat = new.toNat = 0 -- not a false decrease, a `.toNat`
        # floor artifact losing a real, provable strict decrease.
        # `(dec + 1).toNat` fixes exactly this at zero cost elsewhere:
        # algebraically, `a < b -> a + 1 < b + 1` for any Int a, b, so
        # every decreasing_by goal already closed by `omega`/`grind` from
        # `dec`'s own strict decrease closes identically from `dec + 1`'s
        # (same hypotheses, same tactics, one more trivial `+1` on both
        # sides) -- confirmed on the regression below, all 13 tasks/*.json
        # loop tasks unchanged. It does NOT touch the direction class
        # above (cal_sum, linear_search, cube, minimum, carre, foo,
        # slow_max, the three gcdI tasks): there the measure itself can
        # INCREASE outside the invariant-held domain, and shifting by a
        # constant shifts an increase too, closing nothing -- measured
        # directly, still open, named in this file's dated note below.
        dec1 = f"(({dec}) + 1)"
        dec_d = self.dcond(w["decreases"], {}, types)
        # SPEC.md "Sequences as values" (2026-09-09): does the recursive
        # call's own termination proof need the length-bridge alternative
        # (`_dec_needs_seq_bridge`) -- true iff `decreases` names a state
        # var the loop body rewrites via `update`/`fill`. Computed once,
        # shared by `_t_loop`'s own decreasing_by and `_t_loop_spec`'s
        # (same recursive-call state either way).
        dec_needed = self._dec_needs_seq_bridge(w["decreases"], env_b)
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
        #
        # 2026-09-14 (lean-cert, ROADMAP 16.2's value-witness-through-loop
        # item): `ret_cond == "True"` is not merely a return that HAPPENS
        # to always fire at this witness -- it is the literal Lean
        # constant `True` (`sym`'s own "if" case sets `returned = cp`
        # only when the then-branch always returns and the else-branch
        # never does; `cp` is this literal string only when `prop` rendered
        # a BOOLEAN LITERAL condition, SPEC.md's own "True"/"False" case,
        # which only a collapse-if twin (never the real: no task's own
        # `if` condition is written as a bare boolean literal) produces).
        # Measured directly on first_even's and is_prime's own collapse-if
        # twins (both replace the loop body's `if` condition with the
        # literal `true`): emitting the pre-existing `(if _hr : True then
        # {retval} else {rec_call})` dite makes `first_even_t_loop`'s own
        # `decreasing_by` obligation for the now-dead `rec_call` occurrence
        # UNPROVABLE, not merely hard -- `lean -DmaxHeartbeats=1000000` on
        # the emitted file (2026-09-14) shows the auto-generated
        # decreasing_by goal for that occurrence carries NO `_hr` hypothesis
        # at all (confirmed via `set_option pp.all`: Lean's termination
        # elaborator threads branch hypotheses from the OUTERMOST `if`/dite
        # of a function's own body -- here `_hg` -- but not from a FURTHER
        # NESTED one written directly as raw `dite` syntax rather than
        # compiled from Lean's own `match`), so the goal is the RAW
        # inequality `(len - (dite _hr True instDecidableTrue (fun _=>i)
        # (fun _=>i+1)) + 1).toNat < (len - i + 1).toNat` with no way to
        # derive `False` from the (invisible) `¬True`, hence not the
        # measure's fault, a genuinely absent hypothesis. `first |
        # omega|grind` fails, Lean recovers with `sorryAx`, and since
        # `Acc.rec`'s motive is Type-valued (not proof-irrelevant the way
        # a Prop-motived `Acc.rec` would be), that `sorryAx` makes
        # `first_even_t_loop` itself STUCK on `decide`/`simp`/`native_decide`
        # forever after (measured: `first_even_t_wf1`..`first_even_t_loop_spec`
        # all print `sorryAx` in their `#print axioms`, and so does
        # `t_refutation_certificate` the moment it mentions `first_even_t`
        # at all) -- no certificate tactic can recover from a definition
        # that cannot compute. The fix is at the SOURCE: when the loop
        # body's own return condition is this literal constant, the guard-
        # true step ALWAYS returns and the recursive call is not merely
        # unreachable in principle, it is ABSENT from the honest control
        # flow -- so it is not emitted at all, and `first_even_t_loop`
        # becomes what it always semantically was for this twin, a
        # NON-recursive `if`. `termination_by`/`decreasing_by` are kept
        # attached (Lean accepts them on a non-recursive def, with only a
        # benign "unused termination hints" warning, matching every other
        # code path's own emission shape byte-for-byte) rather than
        # threading a second shape through every call site below. Does not
        # touch `_t_loop_spec`'s own proof text (unchanged, still tries
        # the OLD `split`-based induction and may still fail exactly as
        # before for such a twin -- allowed, per this file's certificate
        # docstring: the general spec theorem failing costs nothing but
        # itself, only the CERTIFICATE and `first_even_t`/`first_even_t_loop`
        # being clean matter for REFUTED) and never fires for the real
        # (whose own `if` condition is never a bare boolean literal).
        if has_return and ret_cond == "True":
            retval = env_b.get(self.ret, self.ret)
            out = [f"def {self.name}_t_loop {pb} {sb}{hpre_p}{hinv_p} : "
                   f"{self.lean_type(self.rett)} :=\n"
                   f"  if _hg : {guard_p} then\n"
                   f"    {retval}\n"
                   f"  else {result}\n"
                   f"termination_by ({dec1}).toNat\n"
                   + self._dec(dec_needed)]
        elif has_return:
            retval = env_b.get(self.ret, self.ret)
            out = [f"def {self.name}_t_loop {pb} {sb}{hpre_p}{hinv_p} : "
                   f"{self.lean_type(self.rett)} :=\n"
                   f"  if _hg : {guard_p} then\n"
                   f"    (if _hr : {ret_cond} then {retval}\n"
                   f"     else\n"
                   f"    {rec_call})\n"
                   f"  else {result}\n"
                   f"termination_by ({dec1}).toNat\n"
                   + self._dec(dec_needed)]
        else:
            out = [f"def {self.name}_t_loop {pb} {sb}{hpre_p}{hinv_p} : "
                   f"{self.lean_type(self.rett)} :=\n"
                   f"  if _hg : {guard_p} then\n"
                   f"    {rec_call}\n"
                   f"  else {result}\n"
                   f"termination_by ({dec1}).toNat\n"
                   + self._dec(dec_needed)]
        init_args = " ".join(env0[v] for v in state)
        out.append(f"def {self.name}_t {pb}{hpre_p} : "
                   f"{self.lean_type(self.rett)} :=\n"
                   f"  {self.name}_t_loop {pnames} {init_args}"
                   f"{hpre_a}{hinv_init_a if needs_hyp else ''}\n")
        thms = []

        # THE FRAME-FACT GAP (2026-09-11, lean column, ROADMAP 16.2): a
        # local declared in the PREFIX and never reassigned in the loop
        # body (`frame`, below -- computed here, ahead of its other use
        # site further down at "the helper lemma", so this block can read
        # it too) is loop-invariant by construction (nothing in the
        # recursion ever touches it), but was never actually SAID so to
        # the per-clause `_t_wf{k}` theorems above: their own hypothesis
        # chain was exactly `pre_hyps + inv_props (+ guard_p)`, so a
        # clause needing the PREFIX's own defining fact about a frame var
        # -- appendArrayToSeq measured directly: `h := |a|` before the
        # loop, guard `i_v2 < h`, and the loop-body definedness
        # obligation `i_v2 < |a|` (for `a[i_v2]`) -- had no hypothesis
        # relating `h` to `|a|` at all, so the goal was genuinely FALSE
        # as stated (h is an unconstrained free Int otherwise), not
        # merely under-searched: `grind` correctly read UNPROVED on it,
        # one theorem, no amount of automation closes a goal missing a
        # premise. Every one of the nine named blockers sharing the
        # `real=unproved, twin=refuted` shape in t/COVERAGE-lifted-785.md's
        # 2026-09-10 sweep, plus a majority of the 15 newly-lifted tasks,
        # hit this exact gap (measured: a `t_wf{k}` clause at the
        # guard/body/decreases/after program points, referencing a frame
        # var the guard or ensures names). Fixed the same way
        # `_t_loop_spec`'s own `hfrs` already states this fact for ITS
        # proof (this file's pre-existing pattern, "the helper lemma"
        # below): `v = env0[v]` per frame var, a TRUE fact (the prefix's
        # own straight-line value, sound because nothing in the loop
        # body's recursion ever reassigns it) added to every wf clause
        # whose binders already include the state (`sb`) -- every one of
        # them except "definedness before the loop", which binds only
        # `pb` (params), never `sb`, so a frame fact naming a state var
        # would not even typecheck there (state vars are not yet in
        # scope; unnecessary regardless, since that clause is about the
        # prefix's own computation, not anything downstream of it).
        # ADDITIVE ONLY: an extra TRUE hypothesis never weakens what a
        # theorem states and never lets `grind`/`omega` reach a false
        # conclusion -- these are proof OBLIGATIONS derived by SPEC.md's
        # own D() calculus from the task's own requires/ensures/
        # invariants, unchanged; the only thing added is a fact about
        # local dataflow the source program already guarantees.
        frame = [v for v in state if v not in loop_assigned(w["body"])]
        frame_props = [f"({v} = {env0[v]})" for v in frame]

        # program-point definedness: (context) -> obligations
        pre_hyps = self.pre_props()
        inv_props = [self.prop(iv, {}, types) for iv in invs]
        wfs = []
        for i, iv in enumerate(invs):
            d = self.dcond(iv, {}, types)
            if d is not None:
                wfs.append((pre_hyps + inv_props[:i] + frame_props, d,
                            f"definedness of invariant {i + 1}", [iv]))
        if guard_d is not None:
            wfs.append((pre_hyps + inv_props + frame_props, guard_d,
                        "definedness of the loop guard", [w["cond"]]))
        if dec_d is not None:
            wfs.append((pre_hyps + inv_props + [guard_p] + frame_props,
                        dec_d, "definedness of the loop decreases",
                        [w["decreases"]]))
        ob = self._conj(obs_body)
        if ob is not None:
            wfs.append((pre_hyps + inv_props + [guard_p] + frame_props, ob,
                        "definedness of the loop body", [w["body"]]))
        ob = self._conj(obs_pre)
        if ob is not None:
            wfs.append((pre_hyps, ob, "definedness before the loop",
                        [prefix]))
        ob = self._conj(obs_suf)
        if ob is not None:
            wfs.append((pre_hyps + inv_props + [f"(¬{guard_p})"]
                        + frame_props, ob,
                        "definedness after the loop", [suffix]))
        for hyps, obg, why, src in wfs:
            wf_k += 1
            binders = pb + (" " + sb if "before the loop" not in why
                            else "")
            chain = "".join(f"{h} → " for h in hyps)
            # SPEC.md "Sequences: literals, concatenation, slices (v1)"
            # (third sweep, 2026-09-09): the div/mod bridges only fire
            # when this task touches seq at all (`self.seq_mut` or
            # `self.seq_new`, clover_rotate's own gate) -- a non-seq loop
            # task with div/mod already verifying via plain `grind` (e.g.
            # digit_sum, first_even, is_prime, remainder) gets `nodes`
            # withheld, so `_gr()` returns its exact pre-existing text;
            # measured directly (`cmp` against `out/*.lean`), passing
            # `src` unconditionally changed their tactic TEXT (an inert
            # extra `first`-alternative, never reached, since `grind`
            # alone already closed every one of those goals) without
            # changing any verdict, which still fails the byte-identical
            # bar this sweep holds itself to.
            gr_nodes = src if (self.seq_mut or self.seq_new) else None
            out.append(f"theorem {self.name}_t_wf{wf_k} {binders} :\n"
                       f"    {chain}{obg} := by\n"
                       f"  {self._gr(gr_nodes, {}, types)}\n")
            thms.append((f"{self.name}_t_wf{wf_k}", why))

        # the helper lemma: invariants in, ensures-of-loop-value out.
        # SPEC.md frame rule: the loop havocs exactly the syntactic assigned
        # set of its body, so every other state var carries a frame
        # hypothesis pinning it to its entry value. The recursive call
        # passes an unassigned var through unchanged, so the hypothesis is
        # self-maintaining; without it the lemma quantified over havocked
        # values, and fr_probe_ret / fr_probe_local were unprovable here
        # while Dafny, Verus and Frama-C proved them (measured 2026-09-02).
        # (`frame` itself now computed above, at "THE FRAME-FACT GAP",
        # 2026-09-11, so the per-clause `_t_wf{k}` theorems can read it too.)
        has_pre = bool(pre_hyps)
        hpre = f"\n    (hpre : {self.pre_conj()})" if has_pre else ""
        hinvs = "".join(f"\n    (hinv{i + 1} : {p})"
                        for i, p in enumerate(inv_props))
        hfrs = "".join(f"\n    (hfr{k + 1} : {v} = {env0[v]})"
                       for k, v in enumerate(frame))
        hinv_thm_a = ("".join(f" hinv{i + 1}" for i in range(len(inv_props)))
                     if needs_hyp else "")
        applied_loop = (f"({self.name}_t_loop {pnames} {snames}"
                       f"{hpre_a}{hinv_thm_a})")
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
        #
        # THE PRESERVATION-HAVE COLLISION's own dite (above, `can_dite`)
        # needs the identical fallback shape for the SAME reason
        # `has_return` already does: `split_tac` now also splits the new
        # `if hok : ...` this file's own rec_call carries, and the
        # resulting "else" goal (`hok : ¬P`, a real-but-vacuous branch)
        # is not itself an application of `_t_loop_spec` for `apply` to
        # unify against -- `first`'s fallback closes it instead, from the
        # contradiction between `hok` and the theorem's own real
        # `hinv{i}`/`_hg`, using `dite_else_tac` (above: the SAME tactic
        # power `have_body` already carries, not a bare `grind` -- MEASURED
        # necessary, both cube tasks and all three gcdI tasks regressed
        # under a bare fallback, "THE PRESERVATION-HAVE COLLISION's own
        # else-branch closer" above). The "then" case (the one every real
        # state actually takes) still closes on the FIRST alternative
        # exactly as before -- Prop-irrelevance means `apply ... <;> grind`
        # does not care that the argument in scope is `hok`'s own
        # projection rather than a freshly-proved `have`.
        # DIVISOR-BOUND LEMMA (2026-09-12, ROADMAP 16.2, lean's own item):
        # isNonPrime (task 3, the "exists" family) RETURNS the moment it
        # finds a divisor (isPrime, the "forall" family, never returns
        # early), and that return branch's own goal needs no divisor-
        # bound reasoning -- `i` itself is the witness (`2 <= i` from
        # `hinv1`, `i < n` from the guard plus `hinv3`, `n % i = 0` the
        # very fact the `if` just split on). Tried and REVERTED (measured
        # 2026-09-12, isNonPrime scratch file): an `all_goals (first |
        # ... | refine ⟨i, ?_, ?_, ?_⟩ <;> omega)` alternative hard-
        # errors ("Application type mismatch", "expected type is not an
        # inductive type") on every OTHER goal `repeat split` leaves
        # that is not itself the bare existential (the recursive
        # continue-case's own `Iff` goal, among others) -- `first` does
        # not backtrack out of it the way it does an ordinary failed
        # `grind`, so this stays a NAMED OPEN GAP rather than a change
        # that silently corrupts other goals' own proof search. isPrime
        # (605) is unaffected either way: `kind` there is "forall", so
        # this whole family never reaches isPrime at all.
        # THE PARAM-STATE PRODUCT GAP's own closer (`_param_state_bridge_
        # lines`, above): wired in as one more `first`-alternative on the
        # recursive-apply's own per-goal closer specifically (never on
        # `dite_else_tac`/`exit_tac`, both already covered by their own
        # mechanisms) -- `first` tries the pre-existing `self._gr()`
        # FIRST, so a goal that already closed on it is byte-identically
        # unaffected; only a goal it could not close reaches the `try
        # have`s in scope for a second `self._gr()` attempt.
        mb_lines = self._param_state_bridge_lines(state, types)
        rec_closer = (
            f"(first | {self._gr()} | "
            f"({'; '.join(mb_lines)}; {self._gr()}))"
            if mb_lines else self._gr())
        then_tac = (
            f"all_goals (first | (apply {self.name}_t_loop_spec <;> "
            f"{rec_closer}) | {dite_else_tac if can_dite else self._gr()})"
            if has_return or can_dite else
            f"all_goals (apply {self.name}_t_loop_spec <;> {rec_closer})")
        # SPEC.md "Pairs" (2026-09-10), found on min_max's own two merged
        # if-updates (lo's and hi's, the loop's own state each pass): a
        # bare `repeat split` only chases the FIRST split's TRUE branch
        # down to the end, never coming BACK to split a later `if` inside
        # an EARLIER split's FALSE branch (`repeat tac` iterates the one
        # tactic on the current main goal only, so once `split` opens two
        # goals it keeps re-splitting the first one and never revisits the
        # second) -- reproduced in isolation (a four-line scratch probe:
        # two sequential ifs feeding a 3-conjunct goal, `repeat split`
        # leaves exactly the false-branch's own second `if` unsplit,
        # `repeat (all_goals split)` splits all four combinations).
        # `min_max` is the only committed task with two top-level `if`s
        # in one loop body (measured: `tasks/*.json` swept, zero others),
        # so the stronger form is used ONLY when the loop body itself has
        # two or more (a body-shape rule, not a pairs-specific one -- a
        # coupled two-scalar loop can trigger it with no pair in sight);
        # every task with zero or one keeps the exact prior `repeat
        # split` text, byte-identical.
        n_top_ifs = sum(1 for s in w["body"] if "if" in s)
        split_tac = ("repeat (all_goals split)" if n_top_ifs >= 2
                    else "repeat split")
        # DIVISOR-BOUND LEMMA (2026-09-12, ROADMAP 16.2, lean's own item):
        # the loop-spec's own EXIT branch (guard false: `w["cond"]`
        # itself, i.e. `i <= n/2`, does not hold, so the ANONYMOUS
        # negated-guard hypothesis `split` left in context reads `i >
        # n/2`) is where the `[lo, i)` fact (`hinv{quant_idx}`) needs
        # widening to `[lo, n)`; `t_divisor_bound_<name>` (emitted by
        # `_divisor_bound_lean_defs` below) does exactly that, taking the
        # SAME quant invariant and the freshly-added bound invariant
        # (`hinv{bound_idx}`, now `i <= n/2 + 1`, added to `invs` above)
        # plus `¬ i <= n/2` -- proved `(by omega)` from the SAME anonymous
        # hypothesis `self._gr()` alone already reads (never named,
        # never `intro`'d: `omega` scans the whole local context, so a
        # `(by omega)` sub-proof sees it without this file needing to
        # know `split`'s own binder name for it). ADDITIVE: `first`
        # tries the pre-existing `self._gr()` FIRST, so any task where it
        # already closed the exit goal (none of the 34 committed tasks
        # reach this branch with the plan set, since `_divisor_bound_
        # target` matches nothing they state) is byte-identical.
        exit_tac = self._gr()
        if self._divisor_bound_plan is not None:
            n_text = self.term(self._divisor_bound_plan["dividend"], {},
                               self.types)
            i_name = self._divisor_bound_plan["i_name"]
            bound_name = f"t_divisor_bound_{self.name}"
            quant_hinv = f"hinv{self._divisor_bound_inv_idx}"
            bound_hinv = f"hinv{self._divisor_bound_bound_idx}"
            exit_tac = (
                f"first | ({exit_tac}) | (exact {bound_name} {n_text} "
                f"{i_name} {self.ret} {quant_hinv} {bound_hinv} "
                f"(by omega))")
        out.append(
            f"theorem {self.name}_t_loop_spec {pb} {sb}{hpre}{hinvs}"
            f"{hfrs} :\n"
            f"    {self.post_conj(applied_loop)} := by\n"
            f"  rw [{self.name}_t_loop.eq_def]\n"
            f"  split\n"
            f"  · {split_tac}\n"
            f"    {then_tac}\n"
            f"  · {exit_tac}\n"
            f"termination_by ({dec1}).toNat\n"
            + self._dec(dec_needed))
        thms.append((f"{self.name}_t_loop_spec",
                     "invariants -> ensures, by induction on the loop"))

        # the contract: initial state satisfies the invariants. Reuses
        # `init_hinv_pfs` (computed once, above): the SAME per-invariant
        # entry proof `_t`'s own definition already needed to build its
        # own call to `_t_loop`, not re-derived here.
        init_pfs = (["hpre"] if has_pre else []) + init_hinv_pfs
        for _v in frame:
            init_pfs.append("rfl")   # hfr at the entry state: v0 = v0
        hpre_thm = f" (hpre : {self.pre_conj()})" if has_pre else ""
        applied = f"({self.name}_t {pnames}{hpre_a})"
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

    # ---------- NESTED AND MULTIPLE LOOPS (2026-09-18, ROADMAP WS-20
    # move 1) ----------
    #
    # WHY A SECOND LOOP PATH AND NOT A GENERALIZED `lower_loop`. The shape
    # above returns the TASK'S RETURN TYPE from `{name}_t_loop` and folds
    # the statements after the loop into its own guard-false branch; that
    # is only expressible when the loop is the whole of the body's control
    # flow, which is exactly why it abstained ("only a single top-level
    # loop", and `sym`'s own "nested / multiple loops") on anything else.
    # A loop that is one statement AMONG others -- an inner loop whose exit
    # hands control back to the outer body, or the first of two loops in a
    # row -- has to hand back the STATE, not the answer. So every loop on
    # this path lowers to a function returning the TUPLE of the state
    # variables its own body assigns, in scope order, and the enclosing
    # body continues from that tuple's projections. `lower_loop` is left
    # untouched and still takes every single-top-level-loop task, so all 34
    # committed tasks keep their exact prior output, byte for byte (checked
    # by `python3 -m t.lower_lean`-shaped regeneration of every tasks/*.t
    # before and after this wave: zero diff outside has_duplicate).
    #
    # THE THREE PIECES PER LOOP, all of them kernel obligations, none
    # assumed:
    #   def   {name}_t_loop{k} (params) (scope...) : T1 × ... × Tn
    #         tail-recursive over the scope, `termination_by (dec+1).toNat`
    #         exactly as the single-loop shape's own measure (the same +1
    #         `.toNat`-floor fix, same `decreasing_by`).
    #   spec  {name}_t_loop{k}_spec: from the loop's OWN invariants at the
    #         entry state, the invariants AND the negated guard hold at the
    #         returned tuple. That conjunction is the loop's postcondition,
    #         and it is what an enclosing body gets to use -- the standard
    #         Floyd rule, proved here by the same induction `lower_loop`
    #         already uses (`rw [eq_def]; split;` recurse / exit).
    #   wf    one theorem per definedness obligation SPEC.md's D() calculus
    #         owes at this loop's program points (invariants, guard,
    #         decreases, body), under exactly the context SPEC.md grants.
    #
    # TWO TRAPS, BOTH NAMED BY THE OTHER COLUMNS' OWN FIXES OF 2026-09-18
    # (lower_verus.py::_ro_defining_facts, lower_spark.py::_certify_calls)
    # and both avoided here BY CONSTRUCTION rather than by a later patch:
    #
    # (1) THE READ-ONLY DEFINING FACT. `var j := i + 1;` before an inner
    # loop gives `j = i + 1` -- true at the inner loop's ENTRY and false at
    # every later inner-loop-head state, because the inner loop assigns
    # `j`. An inner theorem quantifies `j` over ALL states, so carrying
    # that equation as a hypothesis would make the theorem say strictly
    # less than the obligation it is supposed to discharge: a definedness
    # goal could then "prove" for a state the program actually reaches
    # with a different `j`. `_nl_ctx_keep` therefore drops any inherited
    # context fact naming a variable the inner loop ASSIGNS, and any fact
    # naming a variable the enclosing body already MODIFIED before the
    # loop (its entry value is no longer the outer loop head's). What
    # survives is only what is invariant across the whole inner loop.
    # Conjunctions are split first (`_nl_split_and`), so `i < len(s) and
    # not r` contributes its `i < len(s)` half and drops its `not r` half
    # rather than being lost whole.
    #
    # (2) CERTIFYING ONLY THE OUTER LOOP'S CALLS. The enclosing loop's own
    # preservation step must know what the inner loop achieved, and the
    # only honest source is the inner loop's spec INSTANTIATED AT THE CALL
    # SITE: `have _hnest{k} := {inner}_spec params <entry args> (by ...)
    # ...`, whose `(by ...)` arguments are the inner invariants AT ENTRY,
    # proved from the outer invariants and the outer guard. Every nested
    # loop in a body gets one, in source order; none is skipped, so no
    # inner loop's effect is ever assumed without its entry obligations
    # being discharged first.
    #
    # WHAT THIS PATH STILL ABSTAINS ON, by name (each raises
    # NotImplementedError, which run_par.py routes to ABSTAIN -- a recorded
    # absence, never a faked proof):
    #   - a loop inside an `if` branch: the loop's context would have to
    #     carry the branch's path condition, and the enclosing body's join
    #     would have to merge two different tuples; not built.
    #   - a loop after an early `return`, or a `return` inside a loop body
    #     on this path: `lower_loop`'s own `_hr` dependent-if answer does
    #     not compose with a tuple-returning loop, and guessing here would
    #     risk a wrong verdict.
    #   - a loop with no invariant of its own, or that assigns nothing in
    #     scope: there is no postcondition to hand the enclosing body.
    #   - a loop combined with self-recursion, as on the single-loop path.
    # KNOWN-OPEN, NOT GATED (it reads `unproved`, never `verified`): an
    # outer `decreases` whose measure mentions a variable an inner loop
    # assigns. Lean's termination elaborator sees only the guard at that
    # point, the inner call is opaque to `omega`, the obligation fails,
    # Lean records `sorryAx`, and the audit in verifiers/lean.py demotes
    # the file -- the honest outcome, so it is left measured rather than
    # pre-judged by a syntactic gate that might also exclude measures the
    # guard alone does bound.

    @staticmethod
    def _nl_split_and(e):
        """A spec expression as its top-level `and` conjuncts. Used so an
        inherited context fact can be kept in part (see trap (1))."""
        if isinstance(e, dict) and e.get("op") == "and":
            out = []
            for a in e["args"]:
                out += Lower._nl_split_and(a)
            return out
        return [e]

    def _nl_ctx_items(self, exprs: list, types: dict) -> list:
        """(lean text, names it reads) per conjunct, the form context
        facts are carried in so `_nl_ctx_keep` can filter them."""
        items = []
        for e in exprs:
            for c in self._nl_split_and(e):
                ns: set = set()
                _collect_names(c, ns)
                items.append((self.prop(c, {}, types), frozenset(ns)))
        return items

    @staticmethod
    def _nl_ctx_keep(items: list, blocked: set) -> list:
        return [t for t, ns in items if not (ns & blocked)]

    @staticmethod
    def _nl_proj(call: str, k: int, n: int) -> str:
        """The k-th of n components of a right-nested Lean product."""
        if n == 1:
            return call
        t = call
        for _ in range(k):
            t = f"({t}).2"
        return t if k == n - 1 else f"({t}).1"

    def _nl_exists_spine(self, e):
        """How many existentials a stated invariant opens, once its
        leading implication (`r ==> exists ...`, has_duplicate's own
        shape) is stepped through. 0 when it opens none."""
        d = 0
        while isinstance(e, dict):
            if "exists" in e:
                d += 1
                e = e["exists"]["body"]
            elif e.get("op") == "implies":
                e = e["args"][1]
            else:
                break
        return d

    def _nl_closer(self, invs: list, types: dict, cands: list) -> str:
        """The per-goal closer every proof on this path uses.

        `self._gr()` first, so any goal the single-loop path would already
        have closed closes here identically. Then two generic alternatives
        and one derived one, each MEASURED necessary on has_duplicate
        (2026-09-18, lean 4.33.1, scratch probes reduced to the bare goal
        before any of them was written into this file):

        `assumption` -- an enclosing loop's own invariant can be, verbatim,
        one conjunct of a nested loop's exit facts (has_duplicate's `r ==>
        exists a, exists b, ...` is stated identically on both loops), and
        `grind` FAILS to prove `P -> Q` from a hypothesis `P -> Q` when `Q`
        is a doubly-nested `exists` over Int with a `s[i]!` body -- measured
        in isolation: the goal is negated, both witnesses are skolemized
        into the context with every side condition present, and the
        instantiation that closes it never fires. `assumption` closes it in
        one step.

        `(intros; simp_all)` -- the same goal shape when the hypothesis is
        not literally syntactically equal but reachable by simplification;
        measured to close the isolated probe where `intro` + `grind` and
        `have := H h` + `grind` both fail.

        the existential-witness cascade -- an invariant that ASSERTS an
        existential (`r ==> exists a in [0,len) . exists b ...`) has to be
        ESTABLISHED at the step that makes `r` true, and `grind` cannot
        invent the pair: it is `(i, j)`, the two loop counters, and nothing
        in the goal points at them. `lower_loop` above already carries the
        one-level version of this idea (`exact <lo, by grind>`, the range's
        lower endpoint, for `seq_max`); this generalizes it to the depth
        the invariant actually states and to every Int name in scope as a
        candidate, since a nested loop's witness is a counter, not an
        endpoint. Each alternative is a `refine` whose holes are closed by
        `grind`, so a wrong candidate fails inside `first` and costs
        nothing; a right one is still a kernel-checked proof term, so this
        can lose a proof, never fake one."""
        alts = [self._gr(), "assumption"]
        depths = sorted({self._nl_exists_spine(iv) for iv in invs} - {0})
        if depths and cands:
            for d in depths:
                pats = []
                for combo in itertools.product(cands, repeat=d):
                    slots = []
                    for wtn in combo:
                        slots += [wtn, "?_", "?_"]
                    slots.append("?_")
                    pats.append("⟨" + ", ".join(slots) + "⟩")
                for p in pats[:MAX_NL_WITNESS_ALTS]:
                    alts.append(f"(refine {p} <;> {self._gr()})")
                for p in pats[:MAX_NL_WITNESS_ALTS]:
                    alts.append(f"(intros; refine {p} <;> {self._gr()})")
        # `; done` is not decoration. MEASURED (2026-09-18, on
        # has_duplicate's own inner-loop `hinv4` goal): `simp_all` is the
        # one alternative here that can SUCCEED WITHOUT CLOSING -- it
        # reports progress for rewriting the context, `first` accepts that
        # as the winning alternative and stops trying the others, and the
        # goal reaches the end of the proof unsolved, where Lean records
        # `sorryAx` and the audit demotes the file. `done` turns it back
        # into a closing tactic, so a partial simplification fails the
        # alternative and `first` moves on, exactly as a failed `grind`
        # already does. Every other alternative in this list closes its
        # goal or fails outright.
        alts.append("(intros; simp_all; done)")
        return "(first | " + " | ".join(alts) + ")"

    def _nl_name_walk(self, stmts: list, counter: list) -> None:
        for s in stmts:
            if "while" in s:
                counter[0] += 1
                k = counter[0]
                self._nl_names[id(s["while"])] = (
                    f"{self.name}_t_loop" if k == 1
                    else f"{self.name}_t_loop{k}")
                self._nl_name_walk(s["while"]["body"], counter)
            elif "if" in s:
                self._nl_name_walk(s["if"]["then"], counter)
                self._nl_name_walk(s["if"]["else"], counter)

    def _nested_loop(self, w: dict, env: dict, types: dict) -> dict:
        """`sym`'s `while` case on this path: emit the loop's function,
        spec and wf theorems (once per syntactic loop), record the `have`
        the enclosing proof needs, and return the state updates the
        enclosing body continues from (the tuple's projections)."""
        scope_nt = list(self._nl_scope) + list(self._nl_local_decls)
        # THE READ-ONLY DEFINING FACT, trap (1) above: a name this loop
        # assigns, or one the enclosing body has already rewritten before
        # reaching the loop (`env[v] != v`), cannot appear in an inherited
        # context fact -- the fact is about the enclosing loop head, the
        # theorem quantifies over every state of THIS loop.
        blocked = set(loop_assigned(w["body"]))
        blocked |= {v for v, _ in scope_nt if env.get(v, v) != v}
        info = self._emit_loop(w, scope_nt, blocked, types)
        args = []
        for v, ty in scope_nt:
            if v in env:
                args.append(env[v])
            elif v in self._nl_binder_names:
                args.append(v)
            else:
                z = self._loop_zero(ty)
                if z is None:
                    raise NotImplementedError(
                        f"state var {v!r} uninitialized before the loop")
                args.append(z)
        call = "(" + " ".join(
            [info["name"]] + self._nl_pnames.split() + args) + ")"
        # THE INNER LOOP'S ENTRY OBLIGATIONS, trap (2) above: one proof per
        # stated invariant, at the call site's own state, discharged from
        # whatever the enclosing proof has in scope. Never assumed.
        entry_closer = self._nl_closer(info["invs"], types,
                                       self._nl_cand_names)
        pfs = "".join(f" (by {entry_closer})" for _ in info["invs"])
        hv = f"_hnest{len(self._nl_pending) + 1}"
        self._nl_pending.append(
            "have " + hv + " := " + " ".join(
                [f"{info['name']}_spec"] + self._nl_pnames.split() + args)
            + pfs)
        n = len(info["asg"])
        return {v: self._nl_proj(call, k, n)
                for k, v in enumerate(info["asg"])}

    def _emit_loop(self, w: dict, scope_nt: list, blocked: set,
                   types: dict) -> dict:
        key = id(w)
        if key in self._nl_info:
            return self._nl_info[key]
        name = self._nl_names[key]
        types = dict(types)
        for v, t in scope_nt:
            types[v] = t
        snames = [v for v, _ in scope_nt]
        asg = [v for v in snames if v in loop_assigned(w["body"])]
        if not asg:
            raise NotImplementedError(
                f"a loop assigning no variable in scope is not lowered "
                f"for lean")
        if self._self_calls(w["body"]):
            raise NotImplementedError(
                "a loop combined with self-recursion is not lowered for lean")
        invs = list(w.get("invariants", []))
        if not invs:
            raise NotImplementedError(
                "a nested or multiple loop with no invariant is not "
                "lowered for lean")
        inv_props = [self.prop(iv, {}, types) for iv in invs]
        guard_p = self.prop(w["cond"], {}, types)
        guard_d = self.dcond(w["cond"], {}, types)
        dec_d = self.dcond(w["decreases"], {}, types)
        ctx_keep = self._nl_ctx_keep(self._nl_ctx, blocked)

        # walk the body: nested loops inside are emitted by this same
        # method, through `sym`'s own `while` case, so the emission order
        # is innermost-first and every `def` precedes its uses.
        saved = (self._nl_scope, self._nl_ctx, self._nl_pending,
                 self._nl_local_decls, self._nl_binder_names,
                 self._nl_cand_names)
        self._nl_scope = list(scope_nt)
        # what a loop nested INSIDE this one may inherit: whatever this
        # loop inherited and still holds of it, plus this loop's own
        # invariants and guard. `_nl_ctx_keep` filters again, per inner
        # loop, against that inner loop's own assigned set (trap (1)).
        self._nl_ctx = [(t, ns) for t, ns in saved[1]
                        if not (ns & blocked)] \
            + self._nl_ctx_items([*invs, w["cond"]], types)
        self._nl_local_decls = []
        self._nl_pending = []
        self._nl_binder_names = set(self._nl_pnames.split()) | set(snames)
        self._nl_cand_names = [v for v in self._nl_pnames.split()
                               if self.types.get(v) == "int"] + \
                              [v for v, t in scope_nt if t == "int"]
        env_b, obs_body, ret_cond = self.sym(w["body"], {}, types, snames)
        haves = self._nl_pending
        (self._nl_scope, self._nl_ctx, self._nl_pending,
         self._nl_local_decls, self._nl_binder_names,
         self._nl_cand_names) = saved
        if ret_cond != "False":
            raise NotImplementedError(
                "an early `return` inside a nested or multiple-loop body "
                "is not lowered for lean")

        params_nt = [(p["name"], p["type"]) for p in self.task["params"]]
        pb = self.binders(params_nt)
        sb = self.binders(scope_nt)
        n = len(asg)
        asg_ty = dict(scope_nt)
        tuple_ty = " × ".join(self.lean_type(asg_ty[v]) for v in asg)
        base = asg[0] if n == 1 else "(" + ", ".join(asg) + ")"
        rec_args = " ".join(env_b.get(v, v) for v in snames)
        dec = self.term(w["decreases"], {}, types)
        dec1 = f"(({dec}) + 1)"
        dec_needed = self._dec_needs_seq_bridge(w["decreases"], env_b)
        out = [f"def {name} {pb} {sb} : {tuple_ty} :=\n"
               f"  if _hg : {guard_p} then\n"
               f"    {name} {self._nl_pnames} {rec_args}\n"
               f"  else {base}\n"
               f"termination_by ({dec1}).toNat\n"
               + self._dec(dec_needed)]

        # the definedness obligations SPEC.md's D() calculus owes at this
        # loop's own program points, under exactly the context it grants:
        # `requires` (always valid -- params never move), whatever survived
        # `_nl_ctx_keep` of the enclosing loops' invariants and guards, and
        # this loop's own invariants (and guard, where SPEC.md grants it).
        pre_hyps = self.pre_props()
        wfs = []
        for i, iv in enumerate(invs):
            d = self.dcond(iv, {}, types)
            if d is not None:
                wfs.append((pre_hyps + ctx_keep + inv_props[:i], d,
                            f"definedness of invariant {i + 1} of {name}",
                            [iv]))
        if guard_d is not None:
            wfs.append((pre_hyps + ctx_keep + inv_props, guard_d,
                        f"definedness of the guard of {name}", [w["cond"]]))
        if dec_d is not None:
            wfs.append((pre_hyps + ctx_keep + inv_props + [guard_p], dec_d,
                        f"definedness of the decreases of {name}",
                        [w["decreases"]]))
        ob = self._conj(obs_body)
        if ob is not None:
            wfs.append((pre_hyps + ctx_keep + inv_props + [guard_p], ob,
                        f"definedness of the body of {name}", [w["body"]]))
        thms = []
        for hyps, obg, why, src in wfs:
            self._nl_wf_k += 1
            chain = "".join(f"{h} → " for h in hyps)
            gr_nodes = src if (self.seq_mut or self.seq_new) else None
            tname = f"{self.name}_t_wf{self._nl_wf_k}"
            out.append(f"theorem {tname} {pb} {sb} :\n"
                       f"    {chain}{obg} := by\n"
                       f"  {self._gr(gr_nodes, {}, types)}\n")
            thms.append((tname, why))

        # the spec: the loop's own invariants in, the invariants AND the
        # negated guard out, at the tuple the function returns. That
        # conjunction is the loop's postcondition and the only thing an
        # enclosing body is ever allowed to use about it.
        call = f"({name} {self._nl_pnames} {' '.join(snames)})"
        post_env = {v: self._nl_proj(call, k, n) for k, v in enumerate(asg)}
        concl = [self.prop(iv, post_env, types) for iv in invs]
        concl.append(f"(¬{self.prop(w['cond'], post_env, types)})")
        hinvs = "".join(f"\n    (hinv{i + 1} : {p})"
                        for i, p in enumerate(inv_props))
        n_top_ifs = sum(1 for s in w["body"] if "if" in s)
        split_tac = ("repeat (all_goals split)" if n_top_ifs >= 2
                     else "repeat split")
        cands = [v for v in self._nl_pnames.split()
                 if self.types.get(v) == "int"] + \
                [v for v, t in scope_nt if t == "int"]
        closer = self._nl_closer(invs, types, cands)
        have_block = "".join(f"    {h}\n" for h in haves)
        out.append(
            f"theorem {name}_spec {pb} {sb}{hinvs} :\n"
            f"    " + "\n    ∧ ".join(concl) + " := by\n"
            f"  rw [{name}.eq_def]\n"
            f"  split\n"
            f"  · \n" + have_block
            + f"    {split_tac}\n"
            f"    all_goals (first | (apply {name}_spec <;> {closer}) "
            f"| {closer})\n"
            f"  · {closer}\n"
            f"termination_by ({dec1}).toNat\n"
            + self._dec(dec_needed))
        thms.append((f"{name}_spec",
                     "invariants -> invariants and not guard, by induction "
                     "on the loop"))
        info = {"name": name, "asg": asg, "invs": invs, "scope": scope_nt}
        self._nl_info[key] = info
        self._nl_out += out
        self._nl_thms += thms
        self._nl_fn_names.append(name)
        return info

    def lower_loops_general(self, wf_k: int) -> tuple[str, list]:
        """The whole task body, with loops anywhere at statement level."""
        self._nl_active = True
        self._nl_used = True
        self._nl_wf_k = wf_k
        self._nl_name_walk(self.body, [0])
        params_nt = [(p["name"], p["type"]) for p in self.task["params"]]
        pb = self.binders(params_nt)
        self._nl_pnames = " ".join(n for n, _ in params_nt)
        types = dict(self.types)
        state = [self.ret] + [s["var"]["name"] for s in self.body
                              if "var" in s]
        # at the TOP level the only binders are the params: every local
        # (and the return name) is substituted by `sym`, so the return
        # name needs a seed exactly the way `lower_loop`'s own prefix does
        # when the body's first write to it is inside the loop.
        env0 = {}
        z = self._loop_zero(self.rett)
        if z is not None:
            env0[self.ret] = z
        self._nl_scope = [(self.ret, self.rett)]
        self._nl_local_decls = []
        self._nl_ctx = []
        self._nl_pending = []
        self._nl_binder_names = set(self._nl_pnames.split())
        self._nl_cand_names = [v for v in self._nl_pnames.split()
                               if self.types.get(v) == "int"]
        env, obs_body, _ret = self.sym(self.body, env0, types, state)
        haves = self._nl_pending
        self._nl_active = False
        if self.ret not in env:
            raise NotImplementedError(
                "a path that assigns nothing is not lowered for lean")
        out = list(self._nl_out)
        thms = list(self._nl_thms)
        out.append(f"def {self.name}_t {pb} : "
                   f"{self.lean_type(self.rett)} :=\n"
                   f"  {env[self.ret]}\n")
        pre_hyps = self.pre_props()
        ob = self._conj(obs_body)
        if ob is not None:
            self._nl_wf_k += 1
            chain = "".join(f"{h} → " for h in pre_hyps)
            tname = f"{self.name}_t_wf{self._nl_wf_k}"
            gr_nodes = self.body if (self.seq_mut or self.seq_new) else None
            out.append(f"theorem {tname} {pb} :\n"
                       f"    {chain}{ob} := by\n"
                       f"  {self._gr(gr_nodes, {}, types)}\n")
            thms.append((tname, "definedness outside the loops"))
        has_pre = bool(pre_hyps)
        hpre_thm = f" (hpre : {self.pre_conj()})" if has_pre else ""
        applied = f"({self.name}_t {self._nl_pnames})"
        all_invs = [iv for info in self._nl_info.values()
                    for iv in info["invs"]]
        closer = self._nl_closer(all_invs, types, self._nl_cand_names)
        have_block = "".join(f"  {h}\n" for h in haves)
        out.append(
            f"theorem {self.name}_t_spec {pb}{hpre_thm} :\n"
            f"    {self.post_conj(applied)} := by\n"
            f"  unfold {self.name}_t\n"
            + have_block
            + f"  {closer}\n")
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
        # `; done` on the bare `simp` alternative (2026-09-18, ROADMAP
        # WS-20 move 1, measured on has_duplicate's own collapse-if twin).
        # `decide`, `omega`, `simp; omega` and `grind` all either close
        # their goal or fail, so `first` moves past them honestly; a bare
        # `simp` does NOT -- it reports success for merely rewriting, and
        # `first` then stops at an alternative that left the goal open.
        # Measured shape: the certificate's own outer `¬(ensures1 ∧
        # ensures2)`, where `decide` cannot reduce a well-founded-
        # recursive `{name}_t` at all, `simp [{name}_t, ...]` unfolded the
        # loop nest and normalized the conjunction down to ensures2's
        # surviving `∀ i j, [0,1][i]! ≠ [0,1][j]!` and stopped there, and
        # the file carried `sorryAx` into `t_refutation_certificate`
        # (unproved, where the following alternative proves it outright).
        # Strictly a fix: an alternative that does not close its goal was
        # never a proof, and `done` only turns that non-proof into a
        # failure the very next alternative gets to answer.
        fl = self.cert_fns
        return (f"(first | decide | omega | (simp [{fl}]; done) | "
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
        pairing fails harmlessly inside `first`.

        The `have`'s `by` block is parenthesized (`:= (by ...)`), not bare
        (SPEC.md "Sequences: literals, concatenation, slices (v1)",
        2026-09-09, first exercised by filter_pos's own single-element
        value-invariant witness, `hi - lo == 1`): measured directly, a bare
        `have h : T := by X; rest...` sitting inside an outer `(...)`-
        wrapped tactic sequence (every certificate bullet is one) has no
        indentation to delimit the `by` block, so Lean's parser folds
        `rest` INTO the `have`'s own proof of `T` instead of sequencing it
        after -- `X` alone already closes `T`, so `rest` then runs on zero
        goals and silently vanishes, leaving the certificate's actual goal
        (the `intro`'d forall body) untouched and the theorem unsolved.
        Reproduced in isolation (a bare `(intro ...; have _h3 : k = 0 :=
        by omega; rcases ...; subst ...; first | decide | ...)` fails
        exactly this way; wrapping the `by` alone in parens fixes it, nothing
        else does) and confirmed dead code for every task lowered before
        this construct: no committed `out/*.lean` file contains `rcases _h`
        at all, so this bug was latent, never triggered, until a
        single-element certificate enumeration first exercised it."""
        hv = self.fresh_hyp()
        disj = " ∨ ".join(f"{b} = ({k} : Int)" for k in range(lo, hi))
        pats = " | ".join([hv] * (hi - lo))
        uniq = list(dict.fromkeys(alts))
        return (f"have {hv} : {disj} := (by {self._bounds_close(h1, h2)}); "
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
                    # THE SWALLOWED ALTERNATIVE (2026-09-18, ROADMAP WS-20
                    # move 1, found on has_duplicate's own collapse-if
                    # twin at s=[0,1]). `_enum` above dispatches one
                    # alternative per enumerated value with `first | A |
                    # B`, and the alternatives are `exact absurd h (by
                    # ...)` terms. MEASURED: an error inside a NESTED `by`
                    # is RECOVERED by the elaborator (logged, the term
                    # completed with `sorryAx`), not raised as a tactic
                    # failure -- so `first` sees alternative A SUCCEED on
                    # every branch, never reaches B, and the file carries
                    # `sorryAx` into `t_refutation_certificate`, which
                    # verifiers/lean.py demotes to unproved. The one
                    # place a `first` here does backtrack honestly is
                    # INSIDE a single `by` over leaf tactics, which is
                    # exactly what `self._closer()` is, so the fix is to
                    # give every branch a branch-INDEPENDENT first shot:
                    # the whole conjunction is ground at the witness, and
                    # `decide` refutes `0 < 1 ∧ [0,1][0]! = [0,1][1]!`
                    # directly (measured), so the same alternative closes
                    # every enumerated branch and the dispatch never has
                    # to discriminate. ADDITIVE and sound in both
                    # directions: `{g}` is a kernel-checked proof of the
                    # same `¬(...)` the decomposition below would build,
                    # and when it fails it fails as a plain tactic, so the
                    # pre-existing projection path is reached exactly as
                    # before.
                    return (f"(first | {g} | (intro {h}; exact absurd "
                            f"{h}{proj} (by {r})))")
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

    def _gterm(self, v, ty) -> str:
        if isinstance(ty, dict) and "pair" in ty:
            # SPEC.md "Pairs" (2026-09-10): a ground pair value, from a
            # witness (interp.py's `_j` renders it `[a, b]`, exactly `v`
            # here) or from `_unshow`'s own inverse -- either way a
            # 2-element sequence, unpacked and lowered component-wise
            # into the Lean pair literal `term()`'s own "pair" case uses.
            t1, t2 = ty["pair"]
            return f"({self._gterm(v[0], t1)}, {self._gterm(v[1], t2)})"
        if isinstance(ty, dict):
            # SPEC.md "Nested sequences (v1)": `{"seq": "seq"}` -- `v` is
            # a plain Python list of rows (interp.py's `_j` recurses into
            # a nested tuple the same way it does a pair, no dataclass
            # involved, so a nested seq's witness rendering is already
            # just nested lists), lowered row by row through the flat
            # "seq" case below, then wrapped in the nested ascription.
            rows = ", ".join(self._gterm(r, "seq") for r in v)
            return f"([{rows}] : List (List Int))"
        if ty == "bool":
            return "true" if v else "false"
        if ty == "seq":
            return "([" + ", ".join(str(int(x)) for x in v) + "] : List Int)"
        n = int(v)
        return f"({n} : Int)" if n >= 0 else f"(({n}) : Int)"

    def _unshow(self, v, ty):
        """Invert interp.py's `_j` witness rendering for a value about to
        become a `venv` entry (fed to `interp.ev` by `_cev`/`_prove`/
        `_refute`). SPEC.md "Pairs" (2026-09-10): `_j` shows a `Pair` as
        the plain list `[a, b]` (deliberately: JSON has no pair type),
        but `interp.ev`'s `fst`/`snd` read a REAL `Pair`'s `.a`/`.b`
        fields, not list indices (`interp.Pair` is a frozen dataclass,
        kept OUT of Python's tuple exactly so a pair value can never be
        mistaken for a same-shaped seq, interp.py's own "Pairs" note) --
        so a raw `[a, b]` surviving into a venv would crash the first
        `fst`/`snd` `interp.ev` reaches on it (an uncaught AttributeError,
        not one of the `Undef`/`Budget`/`RecursionError` `_cev`/
        `certificate` already catch) rather than certificate honestly.
        A seq value's own witness rendering (also a plain list) already
        behaves exactly like interp.py's tuple for every op a certificate
        evaluates (`at`, `len`, `==`), so it is passed through unchanged;
        recursing into a pair's own two components repairs a seq
        component of a pair the same way, for free. SPEC.md "Nested
        sequences (v1)": a nested seq's witness rendering is ALSO just a
        plain (nested) list, interp.py never wrapping it in anything a
        dataclass-shaped type would need unwrapped, so the `isinstance
        (ty, dict) and "pair" in ty` guard below falls through to the
        same unchanged `return v` for `{"seq": "seq"}` as for flat "seq"
        -- no new branch needed, only guarding the existing one so it
        does not mistake a nested-seq type dict for a pair's and crash on
        the missing "pair" key."""
        if isinstance(ty, dict) and "pair" in ty:
            t1, t2 = ty["pair"]
            return interp.Pair(self._unshow(v[0], t1),
                               self._unshow(v[1], t2))
        return v

    def _ens_conj(self) -> dict:
        ens = self.task["ensures"]
        return ens[0] if len(ens) == 1 else {"op": "and", "args": ens}

    def certificate(self, w: dict) -> str | None:
        """The t_refutation_certificate block for a twin with witness `w`,
        or None when the witness kind has no ground negation here (then the
        twin cell honestly reads unproved, never refuted).

        2026-09-12 (fz_p_vac_post, "lean" item): a "value"-kind witness
        whose `_ens` is not True is harness.decorative_kind's OWN
        "decorative" case -- the twin computes a DIFFERENT value than the
        real body at this point, but that value does not FALSIFY
        `ensures` (a content-free or merely loose postcondition, `True`
        for fz_p_vac_post). There is nothing to refute there: `_cert_value`
        would try to prove `¬ensures` at a point where `ensures` is not
        false, fail, and (measured directly on fz_p_vac_post: `unproved`
        even though the twin's own verification theorem alone would have
        read `verified`) drag a file that should read VERIFIED down to
        UNPROVED by attaching an unprovable certificate to it. Guarded
        here, before `_cert_value` is ever called, so a decorative witness
        emits no certificate at all and the twin is graded on its own
        verification theorem, exactly the "exit"/"preservation" kinds'
        own invariant (invariant_witness's docstring: those ALWAYS entail
        a refutation, so no matching guard is needed for them)."""
        kind = w.get("_kind")
        if kind == "value":
            if w.get("_ens") is not True:
                return None
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
        # 2026-09-12: an ensures-level witness (_site == "ensures", added
        # alongside the body-level shape below by harness.real_witness's
        # second pass over `ensures`) is not this method's shape -- the
        # REAL body executed fine here, it is `ensures` itself that is
        # undefined at the witness, so the obligation to negate comes from
        # `_expr` (the offending sub-expression AST), not from re-running
        # `to_expr` on the body. See `_cert_undefined_ensures`.
        if w.get("_site") == "ensures":
            return self._cert_undefined_ensures(w)
        if any("while" in s for s in self.body):
            # 2026-09-14 (lean-cert): a body-level undefined witness whose
            # task has a `while` used to abstain unconditionally here
            # ("LOOP-shaped bodies are not covered", this method's own
            # pre-existing note) -- `_cert_undefined_loop` below now
            # covers it by unrolling the loop concretely to the exact
            # iteration interp.py itself raises Undef at, never touching
            # `to_expr` (still loop-free-only, unchanged).
            return self._cert_undefined_loop(w)
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
        venv = {p["name"]: self._unshow(w[p["name"]], p["type"])
                for p in params}
        parts = [(self.prop(r, tenv, types),
                  self._prove(r, tenv, venv, types))
                 for r in self.task.get("requires", [])]
        parts.append((f"(¬{ob})", self._closer()))
        return parts

    def _cert_undefined_ensures(self, w: dict) -> list | None:
        """2026-09-12 (t/ROADMAP.md's ensures-level undefined-witness item,
        "lean" column): the ensures-level twin (`_site == "ensures"`) --
        the REAL body computes a value at this input just fine, but the
        `ensures` clause's OWN definedness obligation is false there
        (interp.py's Undef raised while evaluating `ensures`, never the
        body; `_expr` is the offending sub-expression harness.real_witness
        names, e.g. an `at`/`slice`/div-mod node). `dcond` already renders
        any expression's definedness proposition (emit_clause_wfs's own
        per-clause `_t_wf{k}` theorems use it, unground, quantified over
        the params); calling it on `_expr` with the params bound to the
        witness's GROUND terms instead gives the same proposition already
        fully instantiated, so its negation is closed and decidable --
        exactly the `_closer()` door `_cert_undefined`'s body-level twin
        above already proves its own ground obligation through. No `_twin`
        key on this witness shape (harness.real_witness's docstring): the
        twin body is never consulted here, only `ensures` and `_expr`,
        since the defect measured is in the SPEC's own postcondition, not
        in what either body computes."""
        expr = w.get("_expr")
        if expr is None:
            return None
        if any("while" in s for s in self.body):
            return None      # to_expr/dcond render the loop-free shape only
        params = self.task["params"]
        types = dict(self.types)
        tenv = {p["name"]: self._gterm(w[p["name"]], p["type"])
                for p in params}
        d = self.dcond(expr, tenv, types)
        if d is None:
            return None      # _expr has no definedness obligation of its own
        self.cert_funs = interp.funs_of(self.task, self.body)
        fns = [f"{self.name}_t"] + [f"{f}_s" for f in self.sfuns]
        self.cert_fns = ", ".join(fns)
        venv = {p["name"]: self._unshow(w[p["name"]], p["type"])
                for p in params}
        parts = [(self.prop(r, tenv, types),
                  self._prove(r, tenv, venv, types))
                 for r in self.task.get("requires", [])]
        parts.append((f"(¬{d})", self._closer()))
        return parts

    def _cert_undefined_loop(self, w: dict) -> list | None:
        """2026-09-14 (lean-cert, ROADMAP 16.2's value-witness-through-loop
        item): a body-level undefined witness (`_site` != "ensures") for a
        task whose body has a `while` -- e.g. reverse's own compare-flip
        twin, guard `i < len(s)` flipped to `i <= len(s)`, so at s=[] the
        loop body runs once and `s[len(s)-1-i] = s[-1]` is out of bounds.
        `to_expr` (the loop-free case just above) cannot render this: it
        demands a body ending in an assignment to `self.ret` or a
        `return`, which a loop's OWN body (an index bump, typically)
        usually is neither.

        Mirrors lower_framac.py's `_cert_stmts` while-case and
        lower_spark.py's own while-body replay (both dated 2026-09-12):
        the loop is unrolled CONCRETELY, exactly as many iterations as
        interp.py's own execution takes before raising Undef (found by
        literally replaying it below, catching interp.Undef at the exact
        statement that raises it -- never guessed, never assumed). Unlike
        `_cert_value`'s own loop path (`lower_loop`'s 2026-09-14 fix
        above), this certificate never mentions `{name}_t`/`{name}_t_loop`
        at all: SPEC.md's definedness calculus is a fact about the RAW
        spec body evaluated at the ground witness (`_cert_undefined`'s
        own loop-free sibling already works this way, `to_expr`'s `obs`
        conjunction proved false by ground `decide`/`omega`/`simp`/`grind`
        alone), so nothing here depends on whether the compiled recursive
        function itself elaborates cleanly.

        Each iteration's own definedness obligation is gathered via
        `self.sym` (not `to_expr`: a loop body ending in a plain state
        update, not a return, is exactly `sym`'s own case, already used
        by `_cert_loop`'s "preservation" kind for the identical reason),
        with the ground (`interp.exec_body`) and symbolic (`self.sym`)
        replays kept in lockstep, one iteration behind each other by
        construction (both start from the same prefix-derived state and
        advance the same statements each step). The guard holding at
        every iteration up to and including the last, and the final
        iteration's own obligation being false, are proved and conjoined
        as independent ground facts -- the same "AND of separately proved
        parts" shape `_cert_undefined`'s own `requires`-then-`(¬ob)` list
        already uses, not an implication chain, since every fact here is
        already fully ground (no free variable survives the replay)."""
        body = self.body
        idx = next((i for i, s in enumerate(body) if "while" in s), None)
        if idx is None:
            return None
        prefix, wh = body[:idx], body[idx]["while"]
        types = dict(self.types)
        for s in prefix:
            if "var" in s:
                types[s["var"]["name"]] = s["var"]["type"]
        state = [self.ret] + [s["var"]["name"] for s in prefix
                              if "var" in s]
        params = self.task["params"]
        if any(p["name"] not in w for p in params):
            return None
        self.cert_funs = interp.funs_of(self.task, body)
        fns = [f"{self.name}_t"] + [f"{f}_s" for f in self.sfuns]
        self.cert_fns = ", ".join(fns)
        pvenv = {p["name"]: self._unshow(w[p["name"]], p["type"])
                for p in params}
        ptenv = {p["name"]: self._gterm(w[p["name"]], p["type"])
                for p in params}
        # 2026-09-14: the replay below runs whole loop bodies through
        # interp.exec_body, and interp.py's seq ops build TUPLES (`update`
        # is `s[:i] + (v,) + s[i + 1:]`, `+` is tuple concat), so a seq
        # witness value must enter this env as interp's own tuple, nested
        # lists included; `_unshow` leaves it a list on purpose for the
        # loop-free paths, where only `at`, `len` and `==` ever touch it.
        # Sweep r24 measured the gap: incrementArray (a seq param, an
        # `update` in the loop body, a compare-flip twin with an undefined
        # witness) read LOWER-ERROR "can only concatenate list (not
        # tuple) to list" on both real and twin, where r23 read
        # verified / unproved.
        def _tup(v):
            if isinstance(v, list):
                return tuple(_tup(x) for x in v)
            return v
        venv = {k: _tup(v) for k, v in pvenv.items()}
        try:
            interp.exec_body(prefix, venv, self.cert_funs, interp.St())
        except (interp.Undef, interp.Budget, RecursionError):
            return None      # the prefix itself is undefined: not this shape
        tenv, _, _ = self.sym(prefix, dict(ptenv), dict(types), state)
        parts = [(self.prop(r, ptenv, types),
                  self._prove(r, ptenv, pvenv, types))
                 for r in self.task.get("requires", [])]
        for _ in range(MAX_UNDEF_UNROLL):
            if any(n not in venv or n not in tenv for n in state):
                return None
            guard_now = self._cev(wh["cond"], venv)
            if guard_now is not True:
                # the guard was already false (or undecidable): interp's
                # own Undef did not come from entering this loop again, so
                # this replay does not explain the witness -- honest
                # abstain, not a guess.
                return None
            parts.append((self.prop(wh["cond"], tenv, types),
                          self._prove(wh["cond"], tenv, venv, types)))
            venv_next = dict(venv)
            try:
                interp.exec_body(wh["body"], venv_next, self.cert_funs,
                                 interp.St())
            except (interp.Undef, interp.Budget, RecursionError):
                # THIS iteration's body is where interp.py itself raises
                # Undef: `sym`'s own `obs` (loop-free, `wh["body"]`'s own
                # precondition) instantiated at the SAME ground state names
                # the exact obligation that fails, ground-proved false by
                # `_closer()` alone -- the same door `_cert_undefined`'s
                # loop-free sibling already uses.
                types2 = dict(types)
                _, obs, _ = self.sym(wh["body"], tenv, types2, state)
                ob = self._conj(obs)
                if ob is None:
                    return None
                parts.append((f"(¬{ob})", self._closer()))
                return parts
            types2 = dict(types)
            env_b, _, _ = self.sym(wh["body"], tenv, types2, state)
            tenv = {**tenv, **env_b}
            venv = venv_next
        return None      # too many concrete iterations: honest abstain

    def _cert_value(self, w: dict, _kind: str) -> list | None:
        if isinstance(w.get("_twin"), str):
            return None      # "no value": nothing ground to instantiate
        self.cert_funs = interp.funs_of(self.task, self.body)
        fns = [f"{self.name}_t"] + [f"{f}_s" for f in self.sfuns]
        if self._nl_used:
            # NESTED AND MULTIPLE LOOPS (2026-09-18): every loop function
            # the general path emitted, so `simp [...]`/`grind [...]` can
            # unfold the whole nest down to a ground value at the witness
            # (measured on has_duplicate's own collapse-if twin, s=[0,1]:
            # `simp [hd_t, hd_t_loop, hd_t_loop2]` evaluates it; `decide`
            # alone cannot, well-founded recursion does not reduce).
            fns += list(self._nl_fn_names)
        elif any("while" in s for s in self.body):
            fns.append(f"{self.name}_t_loop")
        self.cert_fns = ", ".join(fns)
        params = self.task["params"]
        types = dict(self.types)
        tenv = {p["name"]: self._gterm(w[p["name"]], p["type"])
                for p in params}
        venv = {p["name"]: self._unshow(w[p["name"]], p["type"])
                for p in params}
        args = " ".join(tenv[p["name"]] for p in params)
        # THE DOMAIN HYPOTHESIS (2026-09-10, `lower_loop`'s own dated
        # note): `_t` now also takes `hpre` for a LOOP-shaped body with
        # `requires`, but ONLY when `_loop_needs_domain_hyp` says the
        # loop's own termination genuinely needs it (previously only the
        # RECURSIVE shape's self-call case ever added an `hpre` param at
        # all) -- so a loop task's own "value"-kind witness (a
        # collapse-if/etc. twin whose loop still runs to a normal exit,
        # min_max's own committed twin) needs the same ground `hpre`
        # proof argument threaded here too, exactly when `_t`'s own
        # definition carries the parameter to fill.
        loop_w = next((s["while"] for s in self.body if "while" in s), None)
        # `_nl_used`: the general path never threads THE DOMAIN
        # HYPOTHESIS into `{name}_t` (its loop functions take no `hpre`
        # and no `hinv`), so `_loop_needs_domain_hyp`'s answer is not
        # about the code actually emitted here; asking it anyway would
        # send this witness to `_cert_value_loop`, whose replay calls
        # `sym` on a body whose nested `while` now raises (the path is
        # switched off after emission), and cost the certificate for
        # nothing.
        loop_needs = (loop_w is not None and not self._nl_used
                      and self._loop_needs_domain_hyp(loop_w))
        # 2026-09-14 (lean-loopcert2, ROADMAP 16.2's value-witness-through-
        # domain-hypothesis-loop item): a "value"-kind witness through a
        # loop whose termination genuinely needs THE DOMAIN HYPOTHESIS
        # cannot trust `{name}_t`/`{name}_t_loop` to COMPUTE the twin's
        # own value at all -- `_cert_value_loop`'s own docstring below has
        # the two measured ways they diverge from interp.py (a poisoned
        # generic entry proof, or `can_dite`'s placeholder standing in for
        # a genuinely-broken invariant) -- so this is tried FIRST, ahead
        # of the `{name}_t`-based path every other "value" witness (loop-
        # free, self-recursive, or a plain/no-domain-hyp loop) still uses
        # unchanged below. `None` here means "not this shape, or the
        # replay itself could not close honestly" -- an unconditional
        # fall-through to the pre-existing path, never a hard failure, so
        # every previously-succeeding row (loop-free, self-recursive, or
        # plain-loop "value" witnesses; the plain-loop shape this same
        # wave already landed) is byte-for-byte unaffected.
        if loop_w is not None and loop_needs:
            replay = self._cert_value_loop(w, tenv, venv, types)
            if replay is not None:
                parts = [(self.prop(r, tenv, types),
                          self._prove(r, tenv, venv, types))
                         for r in self.task.get("requires", [])]
                parts.append(replay)
                return parts
        if self.task.get("requires") and (
                self._self_calls(self.body)
                or (any("while" in s for s in self.body) and loop_needs)):
            applied = f"({self.name}_t {args} (by {self._closer()}))"
        else:
            applied = f"({self.name}_t {args})"
        parts = [(self.prop(r, tenv, types),
                  self._prove(r, tenv, venv, types))
                 for r in self.task.get("requires", [])]
        post = self._ens_conj()
        # SPEC.md "Pairs" (2026-09-10): `w["_twin"]` is interp.py's `_j`
        # rendering of the twin's returned value -- a plain `[a, b]` when
        # the return is a pair (min_max's own collapse-if witness), which
        # `_unshow` turns back into a real `interp.Pair` before it can
        # reach `_cev`'s `interp.ev` (see `_unshow`'s own note); `_gterm`
        # (used for `tenv`/`applied` above, the LEAN TERM side) already
        # handles the same shape as ground syntax, unchanged.
        tv = self._unshow(w["_twin"], self.rett)
        tenv_post = {**tenv, self.ret: applied}
        venv_post = {**venv, self.ret: tv}
        parts.append((f"(¬{self.prop(post, tenv_post, types)})",
                      self._refute(post, tenv_post, venv_post, types)))
        return parts

    @staticmethod
    def _reground(v):
        """interp.py's own value (a tuple for a seq, a Pair for a pair,
        nested) back into the plain list shape `_gterm` reads, which is
        the shape a witness renders it in (`_j`)."""
        if isinstance(v, interp.Pair):
            return [Lower._reground(v.a), Lower._reground(v.b)]
        if isinstance(v, (tuple, list)):
            return [Lower._reground(x) for x in v]
        return v

    def _cert_value_loop(self, w: dict, ptenv: dict, pvenv: dict,
                          types: dict) -> tuple[str, str] | None:
        """2026-09-14 (lean-loopcert2): the `(¬post)` part of a "value"-
        kind witness through a loop whose termination needs THE DOMAIN
        HYPOTHESIS, built WITHOUT ever mentioning `{name}_t`/
        `{name}_t_loop` -- `_cert_value`'s own default (`applied =
        {name}_t args (proof)`) is unsound for exactly this shape, MEASURED
        two different ways on the two rows Wave N (2026-09-14) left open by
        name in t/COVERAGE-lifted-785.md's sweep r24:

        Clover_cal_sum.Sum (off-by-one, witness n=1): the twin starts the
        loop with `n_v := 1` instead of `0`, so the invariant `s =
        n_v*(n_v+1)/2` already reads `0 = 1` at entry -- FALSE for every
        `n`, not only n=1. `{name}_t`'s own definition proves this
        GENERICALLY (`{name}_t_loop n 0 1 hpre (by grind) (by grind)`,
        `lower_loop`'s own emission, unconditional over all `n` satisfying
        `hpre`) so that `(by grind)` fails at DEFINITION TIME, `sorryAx`
        poisons `{name}_t` itself for every input, and a certificate that
        unfolds it is not stuck on a hard GOAL, it holds a term that was
        never a valid proof to begin with -- reproduced directly (`lean` on
        the emitted file, 2026-09-14): the error sits at `{name}_t`'s own
        `(by grind)` call sites, not anywhere in the certificate's text.

        Dafny_Verify_..LoopInvariant.DownWhileGreater (compare-flip,
        witness n=0): here `{name}_t`/`{name}_t_loop` are NOT poisoned
        (THE PRESERVATION-HAVE COLLISION's own `can_dite`/`hok` fix, above,
        DECIDES the preservation obligation instead of proving it) -- but
        deciding it FALSE at this witness (the flipped guard lets `i` step
        from 0 to -1, breaking `0 <= i`) takes the `dite`'s "else" branch,
        `_loop_zero`'s total PLACEHOLDER for Int, literally `(0 : Int)`.
        interp.py's own execution has no such notion of leaving a "domain"
        and keeps computing (`i = -1`, harness.twin_for's own measurement),
        so `{name}_t`'s COMPILED value (0) and the twin's ACTUAL value (-1)
        are simply different numbers here -- an accidental-satisfaction
        trap in the same family `_cert_undefined`'s own module docstring
        names for swap's totalized `getElem!`, at the domain-hypothesis
        loop's own placeholder instead. `ensures` (`i = 0`) genuinely holds
        of the PLACEHOLDER, so `¬(applied = 0)` is a FALSE goal, and
        `lean`'s own measured message is exactly this file's honest report
        of that: `error: unsolved goals` / `case refine_2 ⊢ False`
        (reproduced verbatim, 2026-09-14, on the emitted file).

        THE FIX, sound in both directions since it never asks the compiled
        function to stand in for interp.py's own semantics: replay the RAW
        loop concretely, exactly as `_cert_undefined_loop` already does for
        an undefined witness (ground `interp.exec_body` picks the branch,
        `self.sym` renders the SAME ground state as closed Lean terms one
        iteration behind, ALWAYS defined here since a "value"-kind witness
        by construction runs to a normal exit, never to interp.Undef) --
        but continued until the guard reads ground-False (a normal loop
        exit) rather than until an interp.Undef, capped at
        MAX_UNDEF_UNROLL iterations like every other concrete replay in
        this file. The resulting ground term for `self.ret` is built purely
        from literals and `+`/`-`/`*`/`/` (never a recursive call), so
        `_refute`'s own `_closer()` door (`decide`/`omega`/`simp`/`grind`,
        no unfolding of any poisoned or placeholder-bearing definition
        needed) can close `(¬post)` the same way `_cert_undefined_loop`'s
        own final `(¬ob)` part already does. A final cross-check against
        `w["_twin"]` (the harness's OWN interp-measured value) before
        building the goal means a replay bug here can only make the
        certificate honestly abstain (`None`, falling through to
        `_cert_value`'s pre-existing `{name}_t`-based attempt), never
        assert a claim this method has not itself re-derived from the raw
        statements.

        MEASURED after landing: both rows above now read verified/REFUTED
        in lean (`lean` on each emitted file, exit 0, `t_refutation_
        certificate` audits clean, no sorryAx) -- see this file's dated
        note in the module docstring for the full command and sweep
        re-measurement."""
        body = self.body
        idx = next((i for i, s in enumerate(body) if "while" in s), None)
        if idx is None:
            return None
        prefix, wh, suffix = body[:idx], body[idx]["while"], body[idx + 1:]
        types = dict(types)
        for s in prefix:
            if "var" in s:
                types[s["var"]["name"]] = s["var"]["type"]
        state = [self.ret] + [s["var"]["name"] for s in prefix
                              if "var" in s]

        # 2026-09-14: mirrors `_cert_undefined_loop`'s own dated note --
        # interp.py's seq ops build TUPLES, so a seq witness value must
        # enter the replay env as one, nested lists included; `_unshow`
        # leaves it a list on purpose for the loop-free paths.
        def _tup(v):
            if isinstance(v, list):
                return tuple(_tup(x) for x in v)
            return v

        venv = {k: _tup(v) for k, v in pvenv.items()}
        try:
            interp.exec_body(prefix, venv, self.cert_funs, interp.St())
        except (interp.Undef, interp.Budget, RecursionError):
            return None      # the prefix itself is undefined: not this shape
        tenv, _, _ = self.sym(prefix, dict(ptenv), dict(types), state)
        for _ in range(MAX_UNDEF_UNROLL):
            if any(n not in venv or n not in tenv for n in state):
                return None
            guard_now = self._cev(wh["cond"], venv)
            if guard_now is None:
                return None   # interp cannot decide the guard: abstain
            if guard_now is False:
                break         # a normal loop exit -- exactly the shape
                              # a "value"-kind witness (never Undef) needs
            try:
                venv_next = dict(venv)
                interp.exec_body(wh["body"], venv_next, self.cert_funs,
                                 interp.St())
            except (interp.Undef, interp.Budget, RecursionError):
                return None   # not this shape: the "undefined" cert covers it
            types2 = dict(types)
            # 2026-09-15: re-ground the state entries of `tenv` from
            # interp's own concrete values before every iteration. The
            # first landing of this method threaded `sym`'s output env
            # straight into the next call, and `sym` wraps every state
            # term in `(if {returned} then {old} else {new})` for a body
            # with a `return` inside the loop, so the terms doubled per
            # iteration: sweep r25 (2026-09-15) never reached its first
            # lean cell, run_par was OOM-killed at 457 GB in this exact
            # call, and the lowering probe named the row: clover_linear_
            # search1__linearSearch's collapse-if twin (a value witness
            # a=[0], e=1, a loop whose body returns), MemoryError after
            # 23 GB in 32 s. interp holds the ground state one iteration
            # behind by construction (that is what the replay is for), so
            # each iteration's terms are built on literals and stay small;
            # the certificate's final `(¬post)` is unchanged in meaning.
            for n in state:
                if n in venv:
                    tenv[n] = self._gterm(self._reground(venv[n]),
                                          types.get(n, self.rett))
            env_b, _, _ = self.sym(wh["body"], tenv, types2, state)
            tenv = {**tenv, **env_b}
            venv = venv_next
        else:
            return None       # too many concrete iterations: honest abstain
        if suffix:
            try:
                interp.exec_body(suffix, venv, self.cert_funs, interp.St())
            except (interp.Undef, interp.Budget, RecursionError):
                return None
            env_s, _, _ = self.sym(suffix, dict(tenv), dict(types), state)
            tenv = {**tenv, **env_s}
        if isinstance(w.get("_twin"), str):
            return None       # "no value": nothing ground to instantiate
        tv = _tup(self._unshow(w["_twin"], self.rett))
        if venv.get(self.ret) != tv:
            # the replay diverged from the harness's own measured value:
            # abstain rather than assert a claim never re-derived here.
            return None
        post = self._ens_conj()
        venv_post = {**venv, self.ret: tv}
        return (f"(¬{self.prop(post, tenv, types)})",
                self._refute(post, tenv, venv_post, types))

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
        # SPEC.md "Pairs" (2026-09-10): a pair-typed state var (a loop
        # local, or the return before its `loop_zero` placeholder is
        # overwritten) has the same `_unshow` need as `_cert_value`'s own
        # `_twin` above -- unexercised by min_max's own measured twin
        # (collapse-if reads a "value"-kind witness, `_cert_value`'s
        # path, not this one) but wired the same way for any task whose
        # invariant-drop twin does land here with a pair in `state`.
        venv = {n: self._unshow(w[n], types[n]) for n in names}
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
            # THE DOMAIN HYPOTHESIS (2026-09-10, `lower_loop`'s own dated
            # note): `_t_loop` takes `hpre`/`hinv1..N` as explicit
            # parameters ONLY when `_loop_needs_domain_hyp` says so --
            # ground proofs of exactly the requires/invariant clauses
            # `parts` above already proves at this witness (an
            # INVARIANT-DROP twin's exit state genuinely satisfies the
            # SURVIVING invariants, or there would be no witness at
            # all), reused verbatim as the extra arguments, when
            # `_t_loop`'s own definition carries the parameters to fill.
            needs_c = self._loop_needs_domain_hyp(wh)
            hpre_c = (f" (by {self._closer()})"
                     if needs_c and self.task.get("requires") else "")
            hinv_c = ("".join(f" (by {self._prove(iv, tenv, venv, types)})"
                              for iv in wh.get("invariants", []))
                      if needs_c else "")
            applied = (f"({self.name}_t_loop "
                       + " ".join(tenv[n] for n in params + state)
                       + hpre_c + hinv_c + ")")
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
    # NAMES (2026-09-11, ROADMAP 13.2): sanitize away any identifier that
    # collides with a Lean 4 reserved word, before `Lower` ever sees the
    # task -- see names.py's module docstring. `task` is returned
    # unchanged (`is`) when nothing needs a rename, which is every
    # previously-committed task, so this costs one extra scan and changes
    # nothing downstream for them. `certificate` below reads the witness
    # `w` against this SAME renamed `self.task`/`self.body`, `w`'s own
    # keys already renamed to match (`names.remap_witness`) -- see that
    # function's own docstring for why the renamed spelling, not the
    # original one, is what a certificate that declares its own locals
    # needs.
    twin_body = body if body is not task.get("body") else None
    task, renames = names.sanitize(task, names.KEYWORDS["lean"],
                                    uppercase_ok=True)
    # the twin body renamed under the same mapping, kept a separate
    # object from task["body"] (2026-09-11, names.rename_body's note)
    body = names.rename_body(twin_body, renames) if twin_body is not None else task["body"]
    witness = names.remap_witness(witness, renames)
    lw = Lower(task, body)
    src = lw.lower()
    if witness is not None:
        cert = lw.certificate(witness)
        if cert is not None:
            src += "\n" + cert
    rc = names.rename_comment(renames)
    if rc:
        src += f"\n-- {rc}\n"
    return src


if __name__ == "__main__":
    raise SystemExit(harness.run_all(sys.argv[1:], lower, lean_backend,
                                     "lean"))
