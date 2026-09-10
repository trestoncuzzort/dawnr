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

  SEQUENCES: LITERALS, CONCATENATION, SLICES (2026-09-09, SPEC.md
  "Sequences: literals, concatenation, slices (v1)"). Three new Expr
  forms, each a kernel-native FStar.Seq form: `{"op": "seq", "args": [e1,
  ..., en]}` (`[e1, ..., en]`, n >= 0) is nested `Seq.append (Seq.create 1
  ei) ...`, bottoming out at a bare `Seq.create 1 en` for the last element
  (never an append-to-empty) and at the existing `Seq.createL #int []`
  spelling (the ground `_seq` literal's own, "Sequences as values") for
  n == 0; `s + t` with both operands seqs is `Seq.append s t`, the SAME
  `+` int addition already renders, dispatched by operand type in `ty()`
  exactly as `==` already is (`_pty`'s posture: one operator name, no new
  syntax); `s[a..b]` is `Seq.slice s a b`. `sx` (the seq-valued term
  renderer) grew a `_literal` helper plus the `"seq"`/`"+"`/`"slice"`
  cases; `ty()` grew a `"+"`-is-seq-when-its-first-operand-is check ahead
  of the ARITH fallthrough that used to claim every `+` unconditionally.
  No new lemma is invoked by name anywhere in this: `Seq.create`'s
  `lemma_index_create`, `Seq.append`'s `lemma_len_append` and
  `lemma_index_app1`/`lemma_index_app2`, and `Seq.slice`'s
  `lemma_len_slice`/`lemma_index_slice` (all four SMTPat'd on the literal
  terms in ulib/FStar.Seq.Base.fsti) fire the moment the term appears,
  the same "no assist needed" posture `Seq.upd`/`Seq.create`/`Seq.equal`
  already have. Measured 2026-09-09 on F* 2026.08.30 (P5.fst/P6.fst): a
  direct probe proving, for UNINTERPRETED int binders (not ground
  literals), the index-0/index-1/length facts about a 2-element seq built
  either `Seq.createL [e1;e2]` or `Seq.append (Seq.create 1 e1) (Seq.create
  1 e2)` verified for BOTH encodings with no assist -- this is not a case
  where one form fails -- so `_literal` uses the append/create1 form
  because it needs one spelling at every literal length rather than two
  (a one-element literal, the `r := r + [s[i]]` append idiom filter_pos
  measures, already has to be `Seq.create 1 e` on its own regardless, so
  building n>1 literals from the same pair costs nothing extra).
    DEFINEDNESS. `seq` and `+` cost nothing new to THIS file: neither
  emits a guard, because F*'s own signatures for `Seq.create`/`Seq.append`
  carry none (SPEC.md: a literal is defined iff every element is, a
  concatenation iff both operands are, exactly what evaluating the
  sub-expressions already costs). `slice` is the one that costs something,
  the same shape `at` already costs: `Seq.slice`'s own ulib signature is
  `#a:Type -> s:seq a -> i:nat -> j:nat{i <= j && j <= length s}`
  (FStar.Seq.Base.fsti), so `i:nat`/`j:nat` forces `0 <= a` and `0 <= b`
  and `j`'s refinement forces `a <= b <= len(s)`: a subtyping check the
  kernel is already forced to discharge from the ambient path condition,
  nothing re-derived or re-guarded here. Confirmed by probe (P7.fst):
  `Seq.slice s 0 (Seq.length s + 1)` on an unrefined `s` fails typing,
  Error 19, "Subtyping check failed ... Expected type j:
  Prims.nat{0 <= j && j <= FStar.Seq.Base.length s}", never a bare pass,
  while the same call with `0 <= a /\\ a <= b /\\ b <= Seq.length s` in
  scope verifies with no further help.
    The certificate path needed NO new code in this file: `lower_verus.py`
  (imported, the shared `certificate_formula`) gained a `defined()` case
  for `"slice"` the same day, from the same SPEC.md section, as part of
  its own column's pass on this construct; `_certificate` here already
  calls `lower_verus.certificate_formula` and renders whatever formula
  comes back through the existing `cx.prop(formula, {}, {})` call, exactly
  as it has since 2026-09-06, so tail's off-by-one twin (`s[2..len(s)]` on
  a length-1 `s`, an "undefined" witness) certifies and REFUTES with no
  code added here beyond the `sx`/`ty` cases above.
    MEASURED (`out/agent-fstar-seqops/`, F* 2026.08.30): tail (`r :=
  s[1..]`, loop-free) COUNTS, real VERIFIED, off-by-one twin REFUTED,
  witness s=[0] -> real [], twin "slice bounds [2..1] outside
  0 <= a <= b <= 1". filter_pos (`r := r + [s[i]]` inside a loop, `r := []`
  the initial literal) COUNTS, real VERIFIED, invariant-drop#1 twin
  REFUTED, witness exit at s=[], i=1, r=[1]. swap and reverse are BYTE-
  IDENTICAL to their prior `out/swap.fst`, `out/reverse.fst`,
  `out/swap_twin.fst`, `out/reverse_twin.fst` (`cmp`, all four), and a
  full `run_all` over every task in `tasks/*.json` (19 tasks) COUNTS with
  no REFUSED or flaked verdict, confirming the new `ty()`/`sx()` cases are
  additive and untaken by any previously committed task.

  PAIRS (2026-09-10, SPEC.md "Pairs"). `{"pair": [T1, T2]}` (T1, T2 one of
  "int"/"bool"/"seq") lowers to F*'s own tuple2, `T1 & T2`, over `int`,
  `bool` and `Seq.seq int` (`_tystr`, recursing one level into a pair's two
  components; T1/T2 are always base types, so it bottoms out immediately).
  `pair`/`fst`/`snd` cost NO reencoding: `(a, b)` is F*'s own tuple
  constructor and `fst`/`snd` are F*'s own named projections, spelled
  identically to t's op names, so no translation table is needed the way
  `ARITH`/`CMP` supply one for other ops. Measured (P1.fst, F* 2026.08.30):
  `fst (mk 3 4) == 3` and `snd (mk 3 4) == 4` both discharge by
  `assert_norm` with no assist, the same "no reencoding" posture DIV/MOD
  and `at` already carry, so `Mktuple2?._1`/`._2` (F*'s pattern-match-on-
  the-constructor spelling, also probed and also typechecks) was never
  needed: native `fst`/`snd` already discharge for free, which is as fast
  as an SMT encoding gets.
    PARENTHESIZATION. Measured directly (P2.fst/P3.fst): a BINDER needs no
  extra parens around a pair type at all -- `(p:int & int)` and `(p:Seq.seq
  int & int)` both parse correctly with no inner wrapping, because F* type
  APPLICATION binds tighter than the infix `&` (`Seq.seq int & int` parses
  only as `(Seq.seq int) & int`), exactly the same fact that already let a
  seq's two-token `Seq.seq int` sit bare inside a binder's own enclosing
  parens. A BARE position (a task's own `Pure`, a loop helper's `Pure`, an
  `either`) still needs exactly one wrapping pair of parens, the same rule
  `_pty` already enforced for `Seq.seq int` (P2.fst's `f2`, P3.fst's `f6`:
  `Pure (int & int) ...` and `Pure (Seq.seq int & int) ...` both verify, an
  unparenthesized `Pure int & int ...` was not probed because `_pty`'s
  existing "wrap when the string has a space" rule already covers it with
  no new logic). `_tystr` therefore never wraps a component itself (so a
  binder embedding stays exactly as bare as it always was); `_pty` wraps
  the WHOLE pair type at a bare position, unchanged from its `Seq.seq int`
  rule; and a new `_statecomp` wraps a pair component'S OWN `T1 & T2` (and
  only a pair's) when `gen_loop`'s multi-var loop state hand-builds a
  `&`-join of SEVERAL threaded variables -- needed because three
  `&`-joined tokens cannot tell a bare 3-tuple from a pair sitting beside a
  third value, while a seq's `Seq.seq int` is unambiguous there for the
  same application-binds-tighter reason and so is deliberately left
  unwrapped, or filter_pos's already-committed `state_ty` string, `(int &
  Seq.seq int)`, would have changed for no reason. No committed task
  threads a pair-typed variable through a multi-var loop state, but
  `_statecomp` exists so one could without silently misgrouping the tuple.
    EQUALITY. `==`/`!=` on two pairs render componentwise (SPEC.md: "the
  polymorphic `==` again"), NEVER as F*'s own structural `=`/`==` on the
  whole tuple, even though that was measured to exist and to work for an
  all-int or all-bool pair (P4.fst `ceq_int`/`ceq_bool`, `peq_int`): the
  reason is a Seq-typed component, where F*'s structural equality would
  recurse into a bare, non-extensional `==`/`=` on that component, the
  exact gap "Sequences as values" already measured and worked around with
  `Seq.equal`/`Seq.eq` for a bare seq `==`. So both `bx` (computational:
  `&&` of `Seq.eq`/`=` per component, P4.fst `ceq_seq`) and `prop` (spec:
  `/\\` of `Seq.equal`/`<==>`/`==` per component, P4.fst `peq_seq`)
  dispatch each of `fst`/`snd` by ITS OWN declared type, exactly as a bare
  seq `==` already dispatches on `ty()`, and reuse the identical
  `Seq.equal`/`Seq.eq` forms "Sequences as values" established -- no new
  seq-equality machinery, only a pair-shaped caller of the old one. No
  committed task compares two pairs directly (divmod_pair/min_max only
  project), so this path is measured by probe, not yet by a committed
  verdict.
    THE LOOP ENCODING needed no new machinery beyond the type-string
  helpers above: a pair-typed RETURN or LOCAL threads through `gen_loop`'s
  existing frame/state machinery (`fb`/`sb`/`state_ty`) exactly as an int,
  bool or seq one already does, because that machinery was already generic
  over "a type string to print in a binder" -- min_max's own `r` (a pair)
  is a FRAME variable (never assigned inside the loop body, so it rides
  along as a plain `(r:int & int)` binder, passed back unchanged at every
  recursive call, per the frame rule), which the frame/state split already
  handles with no pair-specific code path at all. `--admit_except`'s
  targeted certificate run is unchanged.
    THE PAIR-VALUED TERM. `px` is `sx`'s exact structural counterpart: a
  pair position is a variable (looked up through `env`, so a pair-typed
  local reassigned across an if-merge or a loop iteration renders its
  threaded term, not the bare name) or a `{"op": "pair", ...}` node, and
  NOTHING else -- no `ite`, no `call`, no seq op, no `fst`/`snd` of a pair
  (those project OUT of a pair, never build one) -- an honest ABSTAIN
  (`NotImplementedError`) for anything else, matching `sx`'s own posture
  for the identical gap (a seq-typed `ite` or self-call is not lowered
  either). `_render`/`_dummy` grew the matching pair case (`_dummy`
  recurses one level into a pair's two components' own dummies, e.g. `(0,
  0)` or `(false, (Seq.createL #int []))`), so a pair-typed slot is
  threaded through `exec_flow`'s per-var if-merge exactly like any other
  type, with no changes to `exec_flow` itself.
    THE CERTIFICATE. `_certificate` here needed NO new code: it already
  calls `lower_verus.certificate_formula` and renders whatever formula
  comes back through the existing `cx.prop(formula, {}, {})` call.
  `lower_verus.py` gained pair-awareness the same day, as part of its own
  column's pass on this construct (`_tlit(v, ty)`, `_to_py`, `_undef_
  obligation`'s new `tmap` parameter): a measured Pair witness value is a
  plain 2-element list, indistinguishable AS JSON from a same-shaped seq
  (interp.py's `_j`/`_tv`: "the runtime value of a pair must be DISTINCT
  from a seq", a distinction the JSON rendering alone cannot carry), so
  `_tlit` needed the declared type threaded down to tell them apart and
  substitute a genuine `{"op": "pair", "args": [...]}` node rather than a
  `{"_seq": [...]}` one. This file's own `px` -- built to accept only
  `"var"`/`op=="pair"` BEFORE that shared fix was measured -- is what makes
  the failure mode safe rather than silently wrong on any witness kind the
  shared formula does not yet cover for a pair (`lower_verus.py`'s own
  docstring names the gap: a pair-typed LOCAL in an "exit"/
  "preservation"/"undefined" witness still falls back to the untyped
  seq-shaped guess, "not exercised by any committed task"): had that
  substitution handed `px` a `{"_seq": [...]}` node standing in for a
  pair, `px` raises `NotImplementedError` (a non-`"var"`, non-`"pair"`
  node), `_certificate`'s existing `except (..., NotImplementedError)`
  catches it, and the twin costs a flip (UNPROVED, no certificate) rather
  than mis-rendering `fst`/`snd` of a `Seq.seq` term, which would be
  ill-typed, not merely unprovable. NAMED REFUSAL, never taken by either
  committed pair task: neither divmod_pair's `wrong-var` witness nor
  min_max's `collapse-if` witness needs it.
    MEASURED (`out/agent-fstar-pairs/`, F* 2026.08.30): divmod_pair (loop-
  free, `r := (x div y, x mod y)`) COUNTS, real VERIFIED, wrong-var twin
  REFUTED, witness x=1, y=1 -> real [1, 0], twin [0, 1] (the certificate's
  own ground term: `fst (0, 1)`/`snd (0, 1)`, a genuine tuple literal, not
  a seq). min_max (a loop keeping both bounds, `r := (lo, hi)` after it)
  COUNTS, real VERIFIED, collapse-if twin REFUTED, witness s=[0, 1] -> real
  [0, 1], twin [1, 1]. abs, swap, reverse, tail and filter_pos are BYTE-
  IDENTICAL to their prior `out/*.fst` (`cmp`, all ten real+twin files),
  confirming the new `ty()`/`sx()`/`bx()`/`prop()` cases and the `_tystr`/
  `_statecomp` refactor of every `TY[...]` lookup are additive and untaken
  by any previously committed task.

PAIRS RESIDUAL (2026-09-10). The fuzz family v1pairs (31 tasks) read fstar
verified/refuted on 21 of 31; the other 10 are named in
fuzz-pairs-residual-fstar.txt. Two distinct causes, both fixed here:
    KEYWORD RENAME. 7 of the 10 (fz_v1pairs_060/142/357/425/433/768/773,
  all the family's find-and-remember-the-value loop shape) ABSTAINED,
  "identifier 'val' is an F* keyword or lacks the lowercase initial F*
  requires for term names": the shape's local accumulator is always named
  `val`, a legal t identifier no t rule bars, and `_ck` refused it by
  spelling alone -- the exact failure mode the pre-existing `_loop`-suffix
  note already named and fixed for a different identifier class ("A
  lowering may refuse what it cannot express; it may not refuse a name it
  can rename"). THE RULE: `_rename_reserved(task, body)` (above `_ck`)
  renames every identifier `_ck` would refuse -- a RESERVED word or an
  uppercase initial -- to a fresh `t_`-prefixed spelling (`val` ->
  `t_val`), checked against `_collect_names(task) | _collect_names(body)`
  so a rename can never shadow a name already in use, with a numeric
  suffix on a further collision (`fresh_named`'s own rule). It runs ONCE,
  before `Ctx`/`gen_fun`/`gen_loop`/`exec_flow` ever see the task, over
  every declaration site `_ck` is called on today (task/spec_fun names,
  param/return names, spec_fun param names, a local `var` declaration, a
  quantifier's bound `var`) and rewrites every USE to match
  (`_rename_walk`, matched by JSON SHAPE -- a `{"var": ...}` reference, an
  `assign`/`return` target, a `call`'s `fun` -- never by a blind string
  substitution, because an op tag can legitimately spell a RESERVED word
  too: `{"op": "and"}`/`{"op": "not"}` are ordinary t op names on any task
  with a boolean AND/NOT, and a blind rewrite would have corrupted them).
  The twin's own witness and refutation certificate are deliberately left
  un-renamed (`lower()` builds a second, un-renamed `Ctx` for
  `_certificate` when a rename happened at all), since `w`'s keys are
  computed by the harness against the pristine task and a mismatch there
  would only ever cost `_certificate`'s own pre-existing safe flip.
  MEASURED (`out/agent-fstar-pairs2/`): all 7 now LOWER and read real
  VERIFIED (no more ABSTAIN); the twin reads UNPROVED rather than REFUTED
  on all 7 (a SEPARATE, pre-existing gap, left by name below), so the
  reading moved from `abstain / (twin not run)` to `verified / unproved`,
  not to COUNTS -- still a strictly more informative cell than an abstain,
  and every one of the 21 previously-passing tasks that need no rename get
  `_rename_reserved(task, body) is (task, body)` back (identity, not a
  copy) and lower BYTE-IDENTICAL to before (confirmed: `out/*.fst`,
  `divmod_pair`/`min_max`/`abs`/`swap`/`reverse`/`tail`/`filter_pos` real
  AND twin files regenerated through `harness.run_task` into
  `out/agent-fstar-pairs2/`, diffed against the committed `out/*.fst`,
  identical on every byte, and each still reads `verified / refuted` in
  AGREEMENT.md).
    REFLEXIVE ENSURES. The other 3 (fz_v1pairs_119/235/294, "proj_param":
  `r := fst(p) * snd(p)` / `fst(p) - snd(p)` / `fst(p) + snd(p)`, ensures
  literally `r == ` the same expression) read `malformed / refuted`: not a
  typing rejection at all -- the emitted file is well-typed and F* accepts
  it, exit 0, "All verification conditions discharged successfully" --
  but MEASURED directly (F* run kept in its own scratch dir, no
  `--log_queries` output produced): NO `queries-*.smt2` file is written,
  zero solver calls, because the postcondition is discharged purely by
  the elaborator's definitional equality between the returned term and
  itself. `verifiers/fstar.py`'s own zero-obligations rule (`discharged ==
  0` -> MALFORMED, "accepted, but the solver answered unsat for nothing,
  not a proof") then demotes it. Reproduced on a plain, pair-free
  `synth_mul(x, y) : Pure int (ensures fun r -> r == x * y) = x * y`: the
  identical MALFORMED, so this is not a pairs bug and not a `px`/
  parenthesisation gap (the instructions' first guess, ruled out by
  measurement, not assumption) -- it is a real limit of the kernel's own
  obligation-counting rule against exactly one shape of trivially-true
  postcondition, and there is no different F* spelling of `r == E` that
  forces an unneeded SMT call without either lying about what the file
  proves or padding in a content-free decoy `assert` whose only job is to
  make the counter happy -- both rejected as dishonest rather than fixed.
  THE FIX: `_reflexive_ensures` (above `gen_fun`) ABSTAINS instead --
  "ensures is a pure syntactic restatement of the returned expression" --
  on exactly this shape (task's sole ensures is `ret == E` or `E == ret`,
  and `E` renders, through the same dispatch the return expression itself
  used, to the IDENTICAL string), so the family's 3 REFUSED cells read
  `abstain` instead of the misleading `malformed / refuted` pairing (a
  real fix REPLACING a wrong-looking asymmetric verdict with an honest
  non-answer, per the instructions' "or refuse by name if it is a real
  limit"). Every one of the 9 previously-committed single-`==`-ensures
  tasks (digit_sum, is_prime, fib, factorial, gcd, sum_upto, count_matches,
  all_nonneg, contains -- all self-recursive with a spec_fun restating a
  DIFFERENT formula than the body computes, never a bare syntactic
  restatement) was checked directly: `_reflexive_ensures` returns False on
  all 9, so none of them abstain, and all 21 previously-committed tasks
  still COUNT with unchanged witnesses (`python3 lower_fstar.py`, full
  `tasks/*.json` sweep).
    BEFORE/AFTER, the 10 (fuzz_lower.py --tasks <the 10> --only fstar,
  --n 400 --seed 1 --jobs 8 --flake 3): fz_v1pairs_060/142/357/425/433/
  768/773 abstain -> verified/unproved (7); fz_v1pairs_119/235/294
  malformed/refuted -> abstain (3). The family's fstar verified/refuted
  count goes from 21/31 to 28/31 (the 7 newly-verified reals; the 3 move
  to an honest abstain, not a verified/refuted pair, by design).
    LEFT, BY NAME: the twin's UNPROVED reading on all 7 renamed tasks.
  MEASURED root cause (Fz_v1pairs_060's targeted `--admit_except` run,
  the certificate check `verifiers/fstar.py` runs once a real fails
  UNPROVED): Error 54, "bool is not a subtype of the expected type prop",
  on the certificate's own `(fst (true, 0)) <==> (...)` term -- `prop`'s
  existing bool-equality-via-`<==>` rule (documented at `Ctx.prop`'s own
  docstring) works fine when the bool term is a projection of an
  ALREADY-TYPE-ANNOTATED binder (`fst r` where `r : bool & int` from the
  task's own `Pure` signature), the shape every committed task uses, but
  not when it projects a bare, unascribed ground tuple literal like the
  certificate's own `(true, 0)` witness substitution -- F*'s b2t coercion
  for `fst`'s result apparently needs that outer type signal, which a
  Lemma-statement's ground literal does not supply the same way an
  ensures-lambda's bound parameter does. This is UNRELATED to the keyword
  rename (the formula never references the renamed local `val`/`t_val` at
  all; it substitutes ground values for the task's PAIR-TYPED RETURN, not
  for any loop-local) and predates it: it is `lower_verus.py`'s
  `certificate_formula`/this file's `Ctx.prop` pair-and-bool-ground-
  literal rendering, a DIFFERENT gap than either fix above, out of this
  pass's scope (this file's brief was the ABSTAIN and the malformed
  pairing, not the certificate), and left exactly as measured: `no_flip`,
  7, `{'unproved': 7}` (fuzz_lower.py's own findings.json), never faked
  toward REFUTED.
    CERTIFICATE FST/SND OF A GROUND PAIR (2026-09-10, closes this note's own
  "LEFT, BY NAME" line above). MEASURED root cause, reproduced directly
  (fz_v1pairs_060's twin, F* run kept in its own scratch dir, `--admit_except`
  targeted at `t_refutation_certificate` alone): Error 54, "bool is not a
  subtype of the expected type prop", the column landing on the `true` inside
  the certificate's own `(fst (true, 0)) <==> (...)` term, exactly as measured
  before. THE FIX: `_proj_pair(op, arg)` (a new module-level helper, placed
  just above `_render`) recognizes when a `fst`/`snd` operand is itself a
  `{"op": "pair", ...}` node -- the ONLY way `px`'s own contract lets that
  happen today is the certificate's ground-witness substitution,
  `lower_verus.py`'s `_tlit` -- and hands back the picked component directly:
  `fst (a, b)` and `a` (`snd (a, b)` and `b`) denote the same value for ANY
  `a`, `b`, an ordinary projection identity, not a certificate-only special
  case, and it needs no type ascription because there is no tuple literal left
  in the output to ascribe. All four fst/snd call sites (`sx`, `zx`, `bx`,
  `prop`) call it before falling back to their prior tuple-wrapping render,
  each recursing into ITS OWN method on the picked component (`prop` into
  `prop`, not `bx`, so a bool leaf keeps `prop`'s own True/False spelling
  rather than `bx`'s lowercase true/false, the exact distinction `prop`'s own
  docstring already draws).
    BEFORE/AFTER, the certificate line (fz_v1pairs_060_twin.fst): `(fst (true,
  0)) <==> (... <= (-1))) /\\ ((fst (true, 0)) ==> (... /\\ ((snd (true, 0))
  == ...)))`, Error 54, becomes `(True <==> (... <= (-1))) /\\ (True ==> (...
  /\\ (0 == ...)))`, no ascription anywhere, F* accepts, and the targeted
  `--admit_except` run discharges the certificate alone.
    MEASURED (`fuzz_lower.py --tasks <the 7> --only fstar --n 400 --seed 1
  --jobs 8 --flake 3`, F* 2026.08.30): fz_v1pairs_060/142/357/425/433/768/773
  all now read fstar VERIFIED/REFUTED (COUNTS), zero disagreements, zero
  twin-survived, zero no-flip -- the last gap this residual note named is
  closed. The family's fstar tally is now 28/31 fully COUNTS (the 21
  already-committed-shape tasks plus these 7), 3 honest `_reflexive_ensures`
  abstains (fz_v1pairs_119/235/294, unrelated, already fixed above), 0
  remaining ABSTAIN or malformed cells.
    BYTE-IDENTITY, checked directly: every one of the 21 committed
  `tasks/*.json`, run through `lower_fstar.lower(task, task["body"])` (the
  REAL source, no witness), matches its committed `out/<name>.fst` on every
  byte, confirming `_proj_pair` is reached ONLY through a certificate render
  -- no committed task's own real source hits it, since ordinary generated
  code only ever threads a pair-typed slot through `env` as a `"var"`, never
  rebuilds a literal `{"op": "pair", ...}` node just to immediately project
  it. `divmod_pair` and `min_max` (`harness.run_task` into
  `out/agent-fstar-cert/`, never `out/` root) both still COUNT (real VERIFIED,
  twin REFUTED, unchanged witnesses); their own twin CERTIFICATE TEXT changed
  (simplified: divmod_pair's `(fst (0, 1))`/`(snd (0, 1))` became bare
  `0`/`1`; min_max's `(fst (1, 1))`/`(snd (1, 1))` became bare `1`), since
  their pre-existing ground-literal certificates hit the identical `px` path,
  just never the bool-specific b2t failure (an int/seq-typed `fst`/`snd` of a
  ground literal already typechecked fine, P1.fst's own 2026-09-10
  measurement). The committed
  `out/divmod_pair_twin.fst`/`out/min_max_twin.fst` are therefore now stale
  relative to what this file emits; left unregenerated here, since this pass's
  brief was `lower_fstar.py` alone and the byte-identity check above is
  defined over real sources only, never the twin/certificate ones.

Statement bodies lower by symbolic execution to one expression (per-var
if-merge, the Rocq lowering's approach): every t body ends each path in an
assign, so the final environment entry for the return name IS the function
body, and a value computed under a branch stays under that branch's guard.

ABSTAINS (NotImplementedError, recorded and never faked): a quantifier in
computational position; more than one loop, nested loops, a loop under a
conditional, or a loop plus self-recursion in one body; a pair position
(`px`) holding anything but a variable or a `{"op": "pair", ...}` node --
no `ite`, no `call`, no seq/fst/snd op builds a pair (SPEC.md "Pairs",
2026-09-10), and this is also what keeps a still-uncovered shape of the
shared refutation certificate (see that section's note) a costed flip
rather than a wrong render; an ensures that is a pure syntactic
restatement of the returned expression (`_reflexive_ensures`, this file's
2026-09-10 residual-closing note below) -- F* discharges it with NO
solver query, which the fstar backend's own zero-obligations rule reads
as MALFORMED, a real limit of that counting rule and not a rendering gap.
Generated helper names are made fresh against the task's own strings, so a
task name is never refused for its spelling. An identifier that collides
with an F* keyword or carries an uppercase initial is no longer an abstain
at all: `_rename_reserved` (2026-09-10) renames it, consistently, before
any of this runs -- see that function's own module-level note.

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


def _tystr(t) -> str:
    """The F* type string for a t type: a bare string ("int"/"bool"/"seq")
    or a pair type `{"pair": [T1, T2]}` (SPEC.md "Pairs", 2026-09-10; T1,
    T2 are always base types, no pair of pairs, so the recursion below
    bottoms out in one step). `T1 & T2` is F*'s own tuple2 notation and the
    spelling this file emits, measured directly (P1-P3 probes, F*
    2026.08.30): `int & int`, `bool & bool`, `Seq.seq int & int` and
    `int & Seq.seq int` all typecheck with NO parens around a two-token
    component, in a binder (`(p:Seq.seq int & int)`), a bare `Pure` result
    type, and a Lemma statement alike, because F* type APPLICATION binds
    tighter than the infix `&`: `Seq.seq int & int` parses only as
    `(Seq.seq int) & int`, never `Seq.seq (int & int)`. So this function
    never wraps a component itself; `_pty` and `_statecomp` below are where
    a CALLER decides whether the resulting string needs parenthesizing for
    ITS OWN embedding context (a bare `Pure` position; a hand-built `&`-
    join of several state variables, where an inner pair's own `&` would
    otherwise be indistinguishable from the join's)."""
    if isinstance(t, dict):
        t1, t2 = t["pair"]
        return f"{_tystr(t1)} & {_tystr(t2)}"
    return TY[t]


def _pty(t) -> str:
    """`_tystr(t)`, parenthesized when it is more than one token (`Seq.seq
    int`, 2026-09-09; `T1 & T2`, 2026-09-10 "Pairs"), unlike a binder's
    `(name:_tystr(t))` where the enclosing parens already disambiguate it.
    Bare positions need this and binder positions must NOT get it, measured
    directly: `: Pure Seq.seq int (requires ...) (ensures ...)` fails to
    desugar, "Unexpected arguments to effect Prims.Pure" (F* 2026.08.30
    error 146, Pure's grammar takes exactly one type field before its
    `(requires ...)`/`(ensures ...)` clauses, so an unparenthesized
    two-token type swallows `int` as a second argument to the effect),
    while `: Pure (Seq.seq int) (requires ...) (ensures ...)` and `either
    (Seq.seq int) int` both verify; the same shape of probe (P2/P3, this
    file's 2026-09-10 pass) confirms `Pure (int & int) (requires ...)
    (ensures ...)` needs exactly the same one pair of parens and no more.
    TY/`_tystr` themselves stay bare so every existing `({name}:
    {_tystr(...)})` binder (params, spec_fun params, loop-frame binders) is
    untouched: those already sit inside their own enclosing parens
    (measured: `(p:int & int)` and `(p:Seq.seq int & int)` both parse with
    no inner parens, P2 f1/f5) and changing TY's/`_tystr`'s own value for a
    task with no seq or pair return/local would have changed
    abs.fst/first_even.fst/digit_sum.fst's bytes for no reason."""
    v = _tystr(t)
    return f"({v})" if " " in v else v


def _statecomp(t) -> str:
    """One component's own type string inside a hand-built `&`-join of
    SEVERAL loop state variables (`gen_loop`'s multi-var `state_ty`),
    parenthesized only when the component is ITSELF a pair (SPEC.md
    "Pairs"). `Seq.seq int` is unambiguous when `&`-joined with other
    components (application binds tighter than `&`, `_tystr`'s own note),
    so wrapping it would only add dead-weight parens and, worse, change
    filter_pos's already-committed `state_ty` string (`(int & Seq.seq
    int)`) for no reason; a pair component's own `T1 & T2`, joined the same
    way, IS ambiguous (three `&`-joined tokens cannot tell a bare 3-tuple
    from a pair sitting beside a third value), so it alone needs its own
    parens here. No committed task threads a pair-typed variable through a
    multi-var loop state yet; this exists so one could without silently
    misgrouping the tuple."""
    s = _tystr(t)
    return f"({s})" if isinstance(t, dict) else s


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
    #
    # KEYWORD RENAME (2026-09-10). This same principle applies to a task
    # identifier that IS a legal t name but happens to spell an F* keyword
    # ("val", "type", "and", ...) or carry an uppercase initial: `lower()`
    # now runs `_rename_reserved` first, over every param/return/spec_fun/
    # task name, every local `var` declaration and every quantifier's bound
    # `var`, before any of them ever reaches this function -- see that
    # function's own docstring for the rule and SPEC.md's fuzz-measured
    # cost of refusing instead (7 of the v1pairs family's 31 tasks, every
    # one for a local named `val`, a legal t identifier no t rule bars).
    # This check now fires only if that pass missed an occurrence: a
    # correctness backstop, not the honest limit it used to record.
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


# --------------------------------------------------------- keyword rename --
# 2026-09-10. Measured on the fuzz family v1pairs (31 tasks): 7 read fstar
# ABSTAIN, every one the identical message, "identifier 'val' is an F*
# keyword or lacks the lowercase initial F* requires for term names" --
# `_ck`'s honest refusal of a local the family's sentinel shape (a
# find-and-remember-the-value loop) always names `val`, a legal t
# identifier with no meaning in t and no rule against it. Refusing it cost
# the column every task that shape touches, for a spelling reason alone,
# exactly the failure mode the `_loop`-suffix note above already named and
# fixed for a DIFFERENT identifier class. The fix is the same one: rename,
# don't refuse.
#
# `_rename_reserved(task, body)` renames every identifier `_ck` would
# refuse -- a reserved F* word (RESERVED) or an uppercase initial -- to a
# fresh `t_`-prefixed spelling, BEFORE `Ctx` or any `gen_*`/`exec_*`
# function ever sees the task. `t_<name>` clears both refusals in the same
# move (it always starts with the lowercase `t`, regardless of what
# `<name>` itself was), and is checked against `_collect_names(task) |
# _collect_names(body)` -- the same superset `Ctx.fresh`/`fresh_named`
# already trust as "every string in scope" -- so a rename can never shadow
# a name the task already uses; a second bad name whose first-choice
# `t_`-spelling collides (with the task or with an EARLIER rename in the
# same pass) gets a numeric suffix, exactly `fresh_named`'s own collision
# rule.
#
# RENAMED, CONSISTENTLY: every place this file calls `_ck` today --
# task/spec_fun names, param/return names, spec_fun param names, a local
# `var` declaration's name, a quantifier's bound `var` -- is a DECLARATION
# site collected by `_declared_bad_names`; every USE of a declared name --
# a `{"var": ...}` reference (local or quantifier-bound), an `assign`/
# `return` statement's target, a `call`'s `fun` -- is rewritten to match by
# `_rename_walk`, structurally (matched by JSON SHAPE: "is this dict a
# variable reference, a local declaration, a quantifier, a call"), never
# by a blind string-value substitution: `_collect_names`'s "every string
# might be a name" posture is right for a FRESHNESS check (a false
# positive there only wastes a candidate name) and wrong for a REWRITE
# (`{"op": "and", ...}` and `{"op": "not", ...}` are both ordinary t op
# tags that happen to spell RESERVED words, on any task with a boolean AND
# or NOT, and a blind rewrite would corrupt them into a dead op the rest
# of this file cannot dispatch). `_rename_walk` touches only the six
# shapes above and recurses generically everywhere else (`args`,
# `then`/`else`, a loop's `cond`/`invariants`/`decreases`/`body`, a
# quantifier's own `lo`/`hi`/`body`), so a renamed identifier used ten
# calls deep inside a nested `if` is reached the same as one at the top,
# and an op tag, a type tag, or a `_shape`/`_family`/`_twin_op` fuzz-
# harness label is never touched because none of them is ever read out of
# one of those six shapes.
#
# NOT renamed: the twin's own measured witness `w` and the refutation
# certificate built from it. `_certificate`'s `lower_verus.certificate_
# formula(task, twin_body, w)` call and its own `cx.prop(formula, {}, {})`
# render keep using the ORIGINAL, un-renamed `task`/`body`/`witness` --
# `lower()` builds a SEPARATE, un-renamed `Ctx` for that one call when a
# rename happened at all -- because `w`'s keys are param/local names
# computed by the harness against the PRISTINE task, before this file ever
# sees it; renaming what `_certificate` reads would only ever cost a
# SAFE flip (its own `except Exception: return None` already means a
# mismatched lookup demotes a would-be REFUTED to UNPROVED, never fakes
# one), but there is no need to pay even that: the two Ctx values agree on
# every param and return already in the task (a name that needs no rename
# renames to itself), so the split costs nothing on every task that does
# not itself need a rename, and only a second cheap `Ctx(task)` construction
# on the few that do.
#
# MEASURED (out/agent-fstar-pairs2/, F* 2026.08.30): all 7 `val`-abstaining
# v1pairs tasks now LOWER (no more `_ck` ABSTAIN); see this file's
# 2026-09-10 dated note below (module docstring) for the fstar column's
# readings on the full residual-10 re-run.
def _needs_rename(name: str) -> bool:
    return name in RESERVED or not name[0].islower()


def _declared_in(node) -> set[str]:
    """Every LOCAL `var` declaration's name and quantifier bound `var`
    inside an expression/statement tree -- the two `_ck` call sites besides
    params/returns/spec_funs/the task's own name, which the caller already
    holds directly and does not need this walk for."""
    out: set[str] = set()
    if isinstance(node, dict):
        v = node.get("var")
        if isinstance(v, dict) and "name" in v:
            out.add(v["name"])
        for kind in ("forall", "exists"):
            q = node.get(kind)
            if isinstance(q, dict) and "var" in q:
                out.add(q["var"])
        for val in node.values():
            out |= _declared_in(val)
    elif isinstance(node, list):
        for val in node:
            out |= _declared_in(val)
    return out


def _declared_bad_names(task: dict, body: list) -> list[str]:
    """Every identifier `_ck` would refuse, declared anywhere in `task` or
    `body` (the body passed to THIS `lower()` call -- the real body or a
    twin's, whichever it is; a twin's structural mutations never introduce
    a declaration the real body lacks, but scanning the one actually being
    rendered rather than always `task["body"]` costs nothing and misses
    nothing either way). Sorted so the resulting rename is deterministic
    (stable across a real/twin pair of `lower()` calls, and across
    repeated runs) rather than depending on dict/set iteration order."""
    declared: set[str] = {task["name"]}
    for p in task["params"]:
        declared.add(p["name"])
    for r in task["returns"]:
        declared.add(r["name"])
    for sf in task.get("spec_funs", []):
        declared.add(sf["name"])
        for p in sf["params"]:
            declared.add(p["name"])
        declared |= _declared_in(sf["body"])
        if "decreases" in sf:
            declared |= _declared_in(sf["decreases"])
    declared |= _declared_in(task.get("requires", []))
    declared |= _declared_in(task.get("ensures", []))
    if "decreases" in task:
        declared |= _declared_in(task["decreases"])
    declared |= _declared_in(body)
    return sorted(n for n in declared if _needs_rename(n))


def _rename_walk(node, mapping: dict[str, str]):
    """`node` with every identifier `mapping` renames substituted at
    exactly the shapes listed in the module note above; see that note for
    why this is a structural (shape-matched) rewrite and not a blind
    string substitution."""
    if isinstance(node, list):
        return [_rename_walk(v, mapping) for v in node]
    if not isinstance(node, dict):
        return node
    if "var" in node:
        v = node["var"]
        if isinstance(v, dict):
            new_v = dict(v)
            new_v["name"] = mapping.get(v["name"], v["name"])
            if "init" in new_v:
                new_v["init"] = _rename_walk(new_v["init"], mapping)
            return {**node, "var": new_v}
        return {**node, "var": mapping.get(v, v)}
    if "assign" in node:
        tgt, expr = node["assign"]
        return {**node, "assign": [mapping.get(tgt, tgt),
                                   _rename_walk(expr, mapping)]}
    if "return" in node:
        tgt, expr = node["return"]
        return {**node, "return": [mapping.get(tgt, tgt),
                                   _rename_walk(expr, mapping)]}
    if "forall" in node or "exists" in node:
        kind = "forall" if "forall" in node else "exists"
        q = dict(node[kind])
        q["var"] = mapping.get(q["var"], q["var"])
        for k in ("lo", "hi", "body"):
            if k in q:
                q[k] = _rename_walk(q[k], mapping)
        return {**node, kind: q}
    if "call" in node:
        c = dict(node["call"])
        c["fun"] = mapping.get(c["fun"], c["fun"])
        if "args" in c:
            c["args"] = _rename_walk(c["args"], mapping)
        return {**node, "call": c}
    return {k: _rename_walk(v, mapping) for k, v in node.items()}


def _rename_reserved(task: dict, body: list) -> tuple[dict, list]:
    """(task, body) with every `_ck`-refused identifier replaced by a fresh
    `t_`-prefixed spelling (see the module note above), or the SAME objects
    back, unchanged, when nothing needs it -- so `lower(task, body, w) is
    (task, body)`-style identity holds for every task with no keyword-
    colliding or uppercase-initial identifier, i.e. every previously-
    committed task: this pass costs one extra scan and changes NOTHING
    downstream for them."""
    bad = _declared_bad_names(task, body)
    if not bad:
        return task, body
    used = _collect_names(task) | _collect_names(body)
    mapping: dict[str, str] = {}
    for n in bad:
        cand = f"t_{n}"
        if cand in used or cand in mapping.values():
            k = 1
            while f"{cand}{k}" in used or f"{cand}{k}" in mapping.values():
                k += 1
            cand = f"{cand}{k}"
        mapping[n] = cand
        used.add(cand)

    def rn(n: str) -> str:
        return mapping.get(n, n)

    new_task = dict(task)
    new_task["name"] = rn(task["name"])
    new_task["params"] = [{**p, "name": rn(p["name"])} for p in task["params"]]
    new_task["returns"] = [{**r, "name": rn(r["name"])} for r in task["returns"]]
    new_task["spec_funs"] = [
        {**sf, "name": rn(sf["name"]),
         "params": [{**p, "name": rn(p["name"])} for p in sf["params"]],
         "body": _rename_walk(sf["body"], mapping),
         **({"decreases": _rename_walk(sf["decreases"], mapping)}
            if "decreases" in sf else {})}
        for sf in task.get("spec_funs", [])]
    new_task["requires"] = _rename_walk(task.get("requires", []), mapping)
    new_task["ensures"] = _rename_walk(task.get("ensures", []), mapping)
    if "decreases" in task:
        new_task["decreases"] = _rename_walk(task["decreases"], mapping)
    new_task["body"] = _rename_walk(task["body"], mapping)
    new_body = _rename_walk(body, mapping)
    return new_task, new_body


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
        if op == "pair":
            # SPEC.md "Pairs" (2026-09-10): the type of `(a, b)` is the pair
            # of its two arguments' own types, computed structurally rather
            # than threaded down from a declared binder, exactly as every
            # other `ty()` case reads an expression's type off its own
            # shape.
            return {"pair": [self.ty(e["args"][0], local),
                             self.ty(e["args"][1], local)]}
        if op in ("fst", "snd"):
            pt = self.ty(e["args"][0], local)
            return pt["pair"][0 if op == "fst" else 1]
        if op in ("update", "fill", "seq", "slice"):
            return "seq"
        if op == "+" and self.ty(e["args"][0], local) == "seq":
            # SPEC.md "Sequences: literals, concatenation, slices": `+` is
            # polymorphic by operand type exactly as `==` already is, so
            # the ARITH table below (which only ever means int `+`) is
            # consulted only once a seq-typed left operand is ruled out.
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
        if op == "seq":
            return self._literal(e["args"], env, local)
        if op == "+":
            s, t = e["args"]
            return (f"(Seq.append {self.sx(s, env, local)} "
                    f"{self.sx(t, env, local)})")
        if op == "slice":
            s, a, b = e["args"]
            # SPEC.md: DEFINED IFF 0 <= a <= b <= len(s), the same shape of
            # obligation `at` gets from Seq.index's domain refinement.
            # F*'s own `Seq.slice` signature is
            #   #a:Type -> s:seq a -> i:nat -> j:nat{i <= j && j <= length s}
            # (ulib/FStar.Seq.Base.fsti), so `i:nat`/`j:nat` already forces
            # `0 <= a` and `0 <= b` and the refinement on `j` forces
            # `a <= b <= len(s)`: nothing here re-derives or re-guards what
            # that signature already requires, exactly the DIV/MOD and
            # `at`/`update`/`fill` posture. A slice whose bounds fail this
            # is therefore ill-typed at the call site, not a false ensures
            # -- confirmed by probe (P7.fst, see the 2026-09-09 "Sequences:
            # literals, concatenation, slices" note below): `Seq.slice s 0
            # (Seq.length s + 1)` on an unrefined `s` fails Error 19,
            # "Subtyping check failed ... Expected type j: Prims.nat{0 <= j
            # && j <= FStar.Seq.Base.length s}", while `Seq.slice s a b`
            # with `a b:int{0 <= a /\ a <= b /\ b <= Seq.length s}` in scope
            # verifies with no further help.
            return (f"(Seq.slice {self.sx(s, env, local)} "
                    f"{self.zx(a, env, local)} {self.zx(b, env, local)})")
        if op in ("fst", "snd"):
            # SPEC.md "Pairs" (2026-09-10): a seq-typed component reached
            # through `fst`/`snd` (`len`/`at` on it are unchanged, since
            # they consume this sx term the same way any other seq term is
            # consumed). `fst`/`snd` are F*'s own tuple2 projections, named
            # identically to t's own op names, so no translation table is
            # needed the way `ARITH`/`CMP` supply one. A literal pair
            # operand short-circuits to its own component (`_proj_pair`,
            # 2026-09-10 residual fix, this function's own module-level
            # note): the certificate's ground-witness substitution is the
            # only source of one, and this is what keeps a seq-typed
            # ground component out of a bare, unascribed tuple literal too.
            comp = _proj_pair(op, e["args"][0])
            if comp is not None:
                return self.sx(comp, env, local)
            return f"({op} {self.px(e['args'][0], env, local)})"
        raise NotImplementedError(f"seq position holds non-variable {e!r}")

    def px(self, e: dict, env: dict, local: dict) -> str:
        """Pair-valued term (SPEC.md "Pairs", 2026-09-10). A pair position
        is a variable, looked up through `env` exactly as sx/zx/bx already
        do (a pair-typed local or return can be reassigned to a fresh
        `pair(a, b)` term across an if-merge or a loop iteration, same as
        any other type), or a `{"op": "pair", ...}` node; nothing else
        builds a pair value (no pair of pairs, no seq of pairs -- SPEC.md
        "What v1 does not claim"), so a pair position is never itself the
        result of `fst`/`snd` (those project OUT of a pair, never INTO
        one), never a seq op, and, like `sx`'s own seq position, never a
        bare `ite` or a `call` -- an honest ABSTAIN (NotImplementedError)
        rather than a silent wrong lowering, exactly `sx`'s own posture for
        the parallel gap. This is also what makes the shared refutation
        certificate's gap SAFE rather than silently wrong (see this file's
        module docstring, the 2026-09-10 "Pairs" note): `lower_verus.py`'s
        `_tlit` has no ground literal for a Pair value distinct from a
        same-shaped seq (SPEC.md "Pairs": "the runtime value of a pair must
        be DISTINCT from a seq", interp.py's `Pair`/`_tv`), so a pair-typed
        value witness gets substituted in as a `{"_seq": [...]}` node --
        neither a `"var"` nor a `{"op": "pair", ...}` -- and this method
        refuses it here rather than rendering `fst`/`snd` of a `Seq.seq`
        term, which would be ill-typed, not merely unprovable."""
        if "var" in e:
            return env.get(e["var"], e["var"])
        op = e.get("op")
        if op == "pair":
            a, b = e["args"]
            ta, tb = self.ty(a, local), self.ty(b, local)
            return f"({_render(self, a, ta, env, local)}, " \
                   f"{_render(self, b, tb, env, local)})"
        raise NotImplementedError(f"pair position holds non-variable {e!r}")

    def _literal(self, args: list, env: dict, local: dict) -> str:
        """`[e1, ..., en]` (SPEC.md "Sequences: literals, concatenation,
        slices"), n >= 0. Rendered as nested `Seq.append (Seq.create 1 ei)
        ...`, bottoming out at a bare `Seq.create 1 en` for the last
        element rather than an append-to-empty. Measured 2026-09-09
        (P5.fst/P6.fst, F* 2026.08.30): a direct probe proving, for
        UNINTERPRETED int binders e1 e2 (not ground literals), both
        `Seq.index (Seq.createL [e1;e2]) 0/1 == e1/e2` and `Seq.length
        (Seq.createL [e1;e2]) == 2`, and the same three facts about
        `Seq.append (Seq.create 1 e1) (Seq.create 1 e2)`, verified with `()`
        for BOTH encodings, no assist needed either way -- so this is not a
        case where one form fails and the other doesn't. The nested
        append/create1 form is used anyway because it needs only one
        spelling, not two: a one-element literal (the `r := r + [s[i]]`
        append idiom `filter_pos` measures) already has to render as
        `Seq.create 1 e` on its own regardless of what an n>1 literal does,
        since `+`'s own seq case (below) is `Seq.append`, so building n>1
        literals from the same `Seq.append`/`Seq.create` pair means every
        literal, at every length, resolves to a term the `+` case, the
        `at`/`update`/`fill` case (SPEC.md "Sequences as values") and the
        ordinary lemma set (`lemma_index_create`, `lemma_len_append`,
        `lemma_index_app1`/`lemma_index_app2`, all SMTPat'd on the literal
        terms in ulib/FStar.Seq.Base.fsti) already cover, rather than adding
        `Seq.createL`'s separate `createL_post`/`seq_to_list` machinery for
        no measured benefit. The empty literal `[]` keeps the existing
        `Seq.createL #int []` spelling (the ground `_seq` literal's own,
        established 2026-09-06/09), since `Seq.append`/`Seq.create` has no
        zero-argument form of its own to fall back on."""
        if not args:
            return "(Seq.createL #int [])"
        head, *rest = args
        h = self.zx(head, env, local)
        if not rest:
            return f"(Seq.create 1 {h})"
        return f"(Seq.append (Seq.create 1 {h}) {self._literal(rest, env, local)})"

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
        if op in ("fst", "snd"):
            # SPEC.md "Pairs" (2026-09-10): an int-typed component reached
            # through `p.0`/`p.1`. `fst`/`snd` are F*'s own tuple2
            # projections, named identically to t's op names, so nothing
            # here re-derives what F* already gives for free (P1.fst,
            # measured 2026-09-10: `fst (mk 3 4) == 3` discharges by
            # `assert_norm` with no assist, the same "no reencoding" note
            # DIV/MOD and `at` already carry). A literal pair operand
            # short-circuits to its own component (`_proj_pair`, 2026-09-10
            # residual fix, its own module-level note): only the
            # certificate's ground-witness substitution ever hands `fst`/
            # `snd` a `{"op": "pair", ...}` operand instead of a `"var"`.
            comp = _proj_pair(op, e["args"][0])
            if comp is not None:
                return self.zx(comp, env, local)
            return f"({op} {self.px(e['args'][0], env, local)})"
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
        if op in ("fst", "snd"):
            # SPEC.md "Pairs": a bool-typed component reached through
            # `p.0`/`p.1` in computational position (an `if`/`and`/`or`
            # guard, never an ensures -- that path is `prop`'s own fst/snd
            # case below). A literal pair operand short-circuits to its
            # own component (`_proj_pair`, 2026-09-10 residual fix, its own
            # module-level note): only the certificate's ground-witness
            # substitution ever hands `fst`/`snd` a `{"op": "pair", ...}`
            # operand instead of a `"var"`.
            comp = _proj_pair(op, e["args"][0])
            if comp is not None:
                return self.bx(comp, env, local)
            return f"({op} {self.px(e['args'][0], env, local)})"
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
            if isinstance(t, dict):
                # SPEC.md "Pairs": componentwise, the polymorphic `==`
                # again. Rendered component-by-component rather than as
                # F*'s own structural `=` on the whole tuple (measured to
                # exist and work for an (int & int)/(bool & bool) pair,
                # P4.fst ceq_int/ceq_bool) because a Seq-typed component
                # needs `Seq.eq`'s decidable form exactly as a bare seq
                # `==` already does two cases up, and F*'s own tuple `=`
                # would recurse into a bare (non-decidable-for-seq)
                # equality on that component instead.
                t1, t2 = t["pair"]
                a_e, b_e = e["args"]
                pa, pb = self.px(a_e, env, local), self.px(b_e, env, local)
                fa, fb = f"(fst {pa})", f"(fst {pb})"
                sa, sb = f"(snd {pa})", f"(snd {pb})"
                fst_eq = (f"(Seq.eq {fa} {fb})" if t1 == "seq"
                          else f"({fa} = {fb})")
                snd_eq = (f"(Seq.eq {sa} {sb})" if t2 == "seq"
                          else f"({sa} = {sb})")
                core = f"({fst_eq} && {snd_eq})"
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
        if op in ("fst", "snd"):
            # SPEC.md "Pairs": a bool-typed component used directly as a
            # proposition (`ensures r.0`, T1 == "bool"). No committed task
            # exercises this -- divmod_pair/min_max project only int
            # components -- but it costs nothing beyond the same b2t
            # coercion the bare bool `"var"` case above already relies on,
            # PROVIDED the operand is a type-ascribed binder rather than a
            # bare ground tuple literal: a literal pair operand short-
            # circuits to its own component instead (`_proj_pair`,
            # 2026-09-10 residual fix, its own module-level note) -- this
            # is the branch the "PAIRS RESIDUAL" note's measured Error 54
            # came through (`(fst (true, 0)) <==> (...)`, the certificate's
            # own ground-witness substitution, the only source of a
            # `{"op": "pair", ...}` fst/snd operand today), and rendering
            # the picked component through `prop` itself rather than `bx`
            # keeps its own True/False spelling for a bool leaf instead of
            # `bx`'s lowercase true/false, exactly the distinction this
            # method's own docstring draws.
            comp = _proj_pair(op, e["args"][0])
            if comp is not None:
                return self.prop(comp, env, local)
            return f"({op} {self.px(e['args'][0], env, local)})"
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
            elif isinstance(t0, dict):
                # SPEC.md "Pairs": componentwise, the polymorphic `==`
                # again (two ints, two bools, two seqs, two pairs).
                # Dispatched per component exactly as `bx`'s own pair case
                # is, so a Seq-typed component gets `Seq.equal` (the prop
                # form) rather than F*'s own non-extensional `==`, and a
                # bool-typed component gets `<==>` rather than `==` (F*'s
                # `==` on `bool` is a decidable computational equality, not
                # itself a proposition needing coercion the way a bare
                # bool term does, but `<==>` reads the intent identically
                # and stays consistent with every other bool-equality case
                # in this method).
                t1, t2 = t0["pair"]
                a_e, b_e = e["args"]
                pa, pb = self.px(a_e, env, local), self.px(b_e, env, local)
                fa, fb = f"(fst {pa})", f"(fst {pb})"
                sa, sb = f"(snd {pa})", f"(snd {pb})"

                def _ceq(ty, x, y):
                    if ty == "seq":
                        return f"(Seq.equal {x} {y})"
                    if ty == "bool":
                        return f"({x} <==> {y})"
                    return f"({x} == {y})"

                core = f"({_ceq(t1, fa, fb)} /\\ {_ceq(t2, sa, sb)})"
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


def _proj_pair(op: str, arg: dict) -> dict | None:
    """fst/snd of a GROUND PAIR LITERAL (2026-09-10, closes the "PAIRS
    RESIDUAL" note's `unproved`-on-all-7 gap below). `arg`, the operand of
    a `fst`/`snd` node, is either a `"var"` or a `{"op": "pair", ...}`
    node (`px`'s own contract, this file's docstring on `px`); when it is
    the latter, `fst (a, b)` and `a` (`snd (a, b)` and `b`) denote the
    SAME value for ANY `a`, `b` -- an ordinary projection identity, true
    of every pair regardless of whether `a`/`b` are ground -- so the
    picked component can be handed back directly, with no `fst`/`snd` and
    no tuple left in the output at all. This is what the residual note's
    measured Error 54 needed: F*'s b2t coercion for `fst r`/`snd r`
    (`bx`'s and `prop`'s own fst/snd cases, both already documented there)
    discharges fine when `r` is a TYPE-ASCRIBED BINDER (every committed
    task's shape, `r : bool & int` from the task's own `Pure`), but not
    when the operand is a bare, unascribed ground tuple LITERAL -- exactly
    what the shared refutation certificate substitutes for a pair-typed
    witness (`lower_verus.py`'s `_tlit`, a `{"op": "pair", ...}` node
    built from ground `int`/`bool`/`_seq` leaves). MEASURED directly
    (Fz_v1pairs_060's own certificate line before this fix, F* run kept in
    a scratch dir, `--admit_except` targeted at the certificate lemma
    alone): `(fst (true, 0)) <==> (...)`, Error 54, "bool is not a subtype
    of the expected type prop", the column landing on the `true` inside
    the tuple literal, not on `fst` itself. Ascribing the literal
    (`((true, 0) <: bool & int)`) or `let`-binding it first would also
    have worked (both typecheck) but both leave a tuple construction in
    the output for the sole purpose of immediately taking it apart again;
    returning the component itself needs no ascription because there is
    no tuple literal left to ascribe. Nothing here inspects whether `a`/
    `b` are ground, so this is not a certificate-only special case, only a
    projection identity that happens to be the one place `px`'s own
    contract ever lets a `fst`/`snd` operand BE a `{"op": "pair", ...}`
    node in the first place: ordinary generated code threads a pair-typed
    slot through `env` as a `"var"` (the loop/if-merge machinery's own
    rule), so a literal pair immediately projected is a shape only the
    certificate's ground-witness substitution produces today."""
    if isinstance(arg, dict) and arg.get("op") == "pair":
        return arg["args"][0 if op == "fst" else 1]
    return None


def _render(cx: "Ctx", e: dict, t, env: dict, local: dict) -> str:
    """An assign/var-init/return right-hand side, dispatched on its t type
    (SPEC.md 2026-09-09: a seq is now a local/return type, not only a
    param), so a seq-typed slot is threaded through `env` exactly like an
    int or bool one, and a later `update`/`fill` sees the PREVIOUS value
    through `sx`'s own env lookup rather than the bare variable name.
    `t` a dict (SPEC.md "Pairs", 2026-09-10: `{"pair": [T1, T2]}`) dispatches
    to `px`, so a pair-typed slot is threaded through `env` exactly the
    same way -- this is the one call site both `exec_flow` (assign/var-init/
    return) and `Ctx.px` itself (a pair's own two components) share, so a
    pair-typed loop local or a pair nested one level inside `pair(a, b)`'s
    own arguments both resolve to the identical rule."""
    if t == "bool":
        return cx.bx(e, env, local)
    if t == "seq":
        return cx.sx(e, env, local)
    if isinstance(t, dict):
        return cx.px(e, env, local)
    return cx.zx(e, env, local)


def _dummy(t) -> str:
    """A throwaway, well-typed literal for a slot that types but is never
    read (SPEC.md "Early exit"'s unreached branch, and a loop's initial
    `env` before anything is threaded through it). `Seq.createL #int []`
    matches the empty-seq literal the certificate below already emits for
    `_seq: []`, rather than a second spelling of the same empty sequence.
    A pair type (SPEC.md "Pairs", 2026-09-10) recurses one level into its
    two components' own dummies -- T1/T2 are always base types, no pair of
    pairs, so this bottoms out immediately."""
    if t == "bool":
        return "false"
    if t == "seq":
        return "(Seq.createL #int [])"
    if isinstance(t, dict):
        t1, t2 = t["pair"]
        return f"({_dummy(t1)}, {_dummy(t2)})"
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
    # `_tystr` (not a bare `TY[...]` lookup): a param's own type may be a
    # pair (SPEC.md "Pairs", 2026-09-10, "A parameter, return or local
    # type"), and `_tystr("int"/"bool"/"seq")` reduces to exactly `TY[...]`
    # (byte-identical for every task with no pair param).
    bs = " ".join(f"({p['name']}:{_tystr(p['type'])})" for p in task["params"])
    args = " ".join(p["name"] for p in task["params"])
    return bs, args


def task_spec(cx: Ctx, task: dict) -> tuple[str, str]:
    """(requires proposition, ensures lambda) over params and the return."""
    reqs = [cx.prop(e, {}, {}) for e in task.get("requires", [])]
    ret = task["returns"][0]["name"]
    ens = [cx.prop(e, {}, {}) for e in task["ensures"]]
    return _conj(reqs), f"(fun {ret} -> {_conj(ens)})"


def _reflexive_ensures(cx: Ctx, task: dict, ret: str, ret_t, expr: str) -> bool:
    """True when the task's SOLE ensures clause is exactly `ret == E` (or
    `E == ret`) and `E` renders, by the same dispatch `expr` itself went
    through, to the IDENTICAL string as `expr` -- the function's own
    returned expression (SPEC.md v1pairs "proj_param" fuzz shape,
    2026-09-10: `ensures r == fst(p) * snd(p)` over `r := fst(p) * snd(p)`,
    with no other clause).

    MEASURED (P8, this pass, F* 2026.08.30, and reproduced on a plain,
    pair-free `synth_mul(x, y) = x * y` with `ensures r == x * y`, so this
    is not a pairs-specific gap): a file this shape produces is accepted by
    F* at exit 0 with the success line printed, yet NO `queries-*.smt2` log
    is written at all -- not zero UNSAT lines, zero SOLVER CALLS, because
    the postcondition is discharged purely by the elaborator's definitional
    equality between the returned term and itself, never reaching the SMT
    tactic. `verifiers/fstar.py`'s own zero-obligations rule (`discharged
    == 0` -> MALFORMED, "accepted, but the solver answered unsat for
    nothing, not a proof") then demotes a file the kernel fully accepted
    to MALFORMED. This is a real limit of that counting rule against this
    one shape of trivially-true postcondition, not a bug in this file's
    rendering (the emitted term is well-typed and exactly restates the
    task), and there is no different F* spelling of `r == E` that forces
    an unneeded SMT call without lying about what the file proves -- so
    `gen_fun` ABSTAINS on exactly this shape rather than emit a file this
    column's own backend is certain to misread as MALFORMED."""
    ens = task["ensures"]
    if len(ens) != 1 or ens[0].get("op") != "==":
        return False
    a, b = ens[0]["args"]
    if a == {"var": ret}:
        other = b
    elif b == {"var": ret}:
        other = a
    else:
        return False
    try:
        rendered = _render(cx, other, ret_t, {}, {})
    except (KeyError, NotImplementedError):
        return False
    return rendered == expr


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
    # _reflexive_ensures is kept as a record of the measurement below but no
    # longer gates emission (2026-09-10, the tenth sweep): as an abstain it
    # fired on eleven lifted tasks F* verified with obligations (isOdd,
    # isEven, hasOppositeSign, kthElement, quotient and six more), so the
    # column's honest reading of the zero-obligation shape stays the
    # verifier's own MALFORMED, a documented residual, not an abstain here.
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
    # `_tystr` (SPEC.md "Pairs", 2026-09-10): a frame or state variable's own
    # type can be a pair, and each sits inside its own binder parens here
    # exactly as a seq's two-token `Seq.seq int` already does (measured,
    # P2 f1/f5: `(p:int & int)` and `(p:Seq.seq int & int)` both parse with
    # no inner parens needed), so this is byte-identical to `TY[...]` for
    # every task with no pair frame/state variable.
    fb = "".join(f" ({v}:{_tystr(stys[v])})" for v in fvars)
    fargs = "".join(f" {v}" for v in fvars)
    sb = " ".join(f"({v}:{_tystr(stys[v])})" for v in svars)

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
        # `_statecomp`, not `_tystr`/`TY[...]`: a pair-typed state variable
        # joined here with `&` alongside others needs its OWN parens to
        # stay a distinguishable 2-tuple inside the join (SPEC.md "Pairs"),
        # while a seq's `Seq.seq int` does not (application binds tighter
        # than `&`) -- so this is byte-identical to the old `TY[...]` join
        # for every task with no pair state variable, filter_pos's `(int &
        # Seq.seq int)` included.
        state_ty = "(" + " & ".join(_statecomp(stys[v]) for v in svars) + ")"
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
    # KEYWORD RENAME (2026-09-10, see the note above `_needs_rename`): fix
    # up every `_ck`-refused identifier ONCE, before Ctx or any gen_*/
    # exec_* function sees the task, so the rest of this file never has to
    # know a rename happened. `r_task is task` (identity, not equality)
    # when nothing needed it, which is every previously-committed task.
    r_task, r_body = _rename_reserved(task, body)
    cx = Ctx(r_task)
    name = r_task["name"]
    mod = name[0].upper() + name[1:]
    parts = [f"module {mod}\n", "module Seq = FStar.Seq\n"]
    for sf in r_task.get("spec_funs", []):
        parts.append(emit_spec_fun(cx, sf))

    prefix, w, suffix = find_while(r_body)
    if w is not None and has_self_call(r_body, name):
        raise NotImplementedError(
            "fstar lowering: a body that both loops and self-recurses is "
            "not lowered yet")
    if w is not None:
        parts.append(gen_loop(cx, r_task, prefix, w, suffix))
    else:
        parts.append(gen_fun(cx, r_task, r_body))
    # Twin call sites pass the measured witness; real ones pass None, so a
    # real program never carries the name and can never be demoted by it.
    if witness is not None:
        # The certificate reads the witness `w` and the ORIGINAL task/body
        # -- never the renamed ones (see the module note above): `w`'s
        # keys are param/local names the harness computed against the
        # pristine task, and `_certificate`'s own except-clauses already
        # turn any mismatch into a safe flip, never a fake one, but a
        # rename would only ever cost that flip for no reason when the
        # un-renamed Ctx it needs is one cheap extra construction away.
        cert_cx = cx if r_task is task else Ctx(task)
        cert = _certificate(cert_cx, task, body, witness)
        if cert is not None:
            parts.append(cert)
    return "\n".join(parts)


if __name__ == "__main__":
    raise SystemExit(harness.run_all(sys.argv[1:], lower, fstar_backend,
                                     "fst"))
