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

EARLY EXIT (2026-09-08, SPEC.md "Early exit"). `{"return": [ID, Expr]}`
lowers to Verus's own `return Expr;`, which is what the module's exec/proof
split already needed: the recursive loop helper's decreases and invariant
obligations attach to its OWN return, and Verus checks the ensures at
every return with no loop-invariant obligation there, exactly SPEC.md's
rule. Measured with two probes through the verus binary directly: an exec
fn with a native `while` (invariants, named return) accepts a `return`
inside the loop and checks the ensures at that exit only, never asking for
the invariant there (probe_ret_exec.rs); a recursive `proof fn` accepts
the same thing (probe_ret_proof.rs), which is what matters here since v1
loops already lower to recursion, never a native `while` (see LOOPS
above). A `return` directly in the task's own body emits a bare
`return Expr;` (`_V1.stmts`'s `wrap=None` case). A `return` inside a loop
is different: that loop's helper can no longer just return the state
tuple, since one call of it can end the whole task instead of one more
iteration, so `_may_return` flags any loop whose body returns (directly,
through an `if`, or through a nested loop's own already-wrapped result),
and such a helper's result becomes `(bool, return-type, state-tuple)`:
flag, the task's return value if set, the loop state otherwise. Its
ensures splits the same way -- the flagged branch owes the task's own
`ensures`, never the loop's invariants, matching the SPEC.md text above
verbatim -- and its call site propagates a set flag onward as a real
`return`, wrapped again if the call site is itself inside another such
loop (`_V1.loop`'s `wrap` parameter). The returned expression owes the
same `_assert_defined` (definedness asserts, div/mod bridging) as an
assign's right-hand side, added to `_V1.stmts`'s "return" case. `_assigned`
deliberately gets no "return" case (a return's target is not per-iteration
loop state, see its docstring); `_body_calls` and `_twin_loop` do, the
former for self-recursion detection, the latter needing none in practice
since a `return` statement carries no nested body to walk into. `_sym`
gives up (None) on a body containing a return, the same as it already
does for a nested while, so the nonlinear_arith bridge is skipped rather
than built from a post-state that free early exit makes non-equational.
The v0 path never sees a `return` (v1-only per SPEC.md); `body_expr`'s
existing fallback already refuses cleanly for any body it cannot express.

A second, unrelated fix rode in on top of this because is_prime.json's own
`forall d. 2<=d<n ==> n mod d != 0` needed it: unlike every prior committed
task's quantifiers, which index a Seq and so give Verus's automatic
trigger inference something to grab, this one is pure arithmetic and Verus
refused it outright ("Could not automatically infer triggers for this
quantifier"). `expr()`'s forall/exists case now supplies an explicit
`#![trigger n % d]` whenever the body has no indexable (`at`/`call`) term
of its own (`_has_indexable`, `_mod_div_trigger`); every prior task's
quantifiers keep their free automatic inference untouched, so all 13
previously committed tasks (v0 and v1 alike) still lower byte-identically.

SEQUENCES AS VALUES (2026-09-09, SPEC.md "Sequences as values (v1)"),
`update` (`s[i := v]`) and `fill` (`seq(n, v)`). Both are native in Verus's
own vstd, so `expr()` just calls the vstd method: `update` emits
`s.update(i, v)` (vstd::seq::Seq::update, measured, probe_update.rs: 0
errors alongside a bound-checked `requires`), `fill` emits
`Seq::new(n as nat, |_t_fill_i: int| v)` (vstd::seq::Seq::new takes a
`nat` length and a `FnSpec(int) -> A`; measured, probe_fill_int.rs: an
`int`-typed `n` with `n >= 0` in scope casts and verifies with no hint
needed, the same `as nat` cast `at`'s own `len()` already relies on in
the other direction). `TYPES["seq"]` (already `Seq<int>`, added ahead of
this task) needed no change: a `seq` return, local, and loop-state slot
were already generic over Verus type strings via `scope`'s `(type, mut)`
entries, so a `Seq<int>`-typed loop variable is framed by name exactly
like an `int` one, no code path cared which.

DEFINEDNESS. `Seq::index` and `Seq::update` share the same
`recommends`-only bound (measured, probe_update_oob.rs and
probe_update_oob2.rs): out of `[0, len)`, `update`'s own length
postcondition still holds (`s.update(i,v).len() == s.len()` verifies
unconditionally) but the ELEMENT at `i` is left unconstrained -- an
out-of-bound `s.update(i,v)[i] == v` fails to verify, the same
"unspecified, not undefined-in-Rust's-sense" shape `at` already gets in
this file, so `defined()`'s new "update" case owes `at`'s own bound
(`0 <= i < len(s)`) plus definedness of all three sub-expressions,
discharged by the same `_assert_defined` mechanism, no new machinery.
`fill`'s bound is native too but from the other side: `n as nat` for a
negative `n` does not trap, it silently produces length 0 (measured,
probe_fill_neg.rs: `Seq::new(n as nat, ...).len() == n` FAILS to verify
with no `n >= 0` in scope, so an unguarded `fill` would silently
totalize exactly the way SPEC.md forbids), so `defined()`'s "fill" case
owes `n >= 0` explicitly, the same shape as `div`/`mod`'s `y != 0`.

EXTENSIONAL EQUALITY. Costs nothing extra: measured directly
(probe_ext_eq.rs, `a.len()==b.len() && forall k. a[k]==b[k]` in
`requires`, bare `a == b` in `ensures`, 0 errors; probe_ext_eq3.rs, a
harder case with no given index facts at all,
`a.update(i,x).update(i,y) == a.update(i,y)`, also 0 errors unaided) --
Verus's `Seq<int>` compiles to Z3's native sequence sort in spec/proof
mode, where `==` already denotes real extensional equality at the SMT
level, not a derived or definitional one a lowering has to unlock with
`=~=` (Verus's own extensionality macro, probed too: identical results
with or without it, probe_ext_eq2.rs / probe_ext_eq3b.rs). So `BIN_OPS`
needed no seq-specific entry: `"==" -> "=="` and `"!=" -> "!="`, already
generic over int/bool, are exactly as sound for two `Seq<int>` operands
and neither swap nor reverse (v1's two committed seq tasks) even
exercises it directly (both specs compare elementwise via `at`), so this
finding is banked for the next seq task that states `==` between two
whole seqs, not exercised by either committed cell.

THE TWIN PATH surfaced a gap the construct's own witnesses hit
immediately: swap's measured twin (off-by-one on the `at` inside `tmp :=
s[i]`, mutated to `s[i+1]`) is UNDEFINED at its witness (s=[0], i=0,
j=0: index 1 outside [0,1)), the "_kind": "undefined" witness shape
interp.py's `Reference.witness` has always been able to produce (SPEC.md
"The twins": "the twin is undefined where the real body has a value" is
one of the two accepted value-changing witness shapes) but that this
file's certificate builder had never had to certify, since none of the
15 tasks committed before this one ever measured it (checked directly:
every one is "value" or "exit"). Declining to certify it would leave
swap permanently UNPROVED on its twin cell, never REFUTED, so
`_undef_obligation` closes it: re-walk the twin body with `interp.ev`,
in the same left-to-right order interp.py used to raise the Undef that
minted the witness, calling `defined()` (the one function this lowering
already trusts for its own asserts, so no second reading of what
"defined" means) at each statement to find the first ground-false
obligation, then emit its negation, substituted with the witness's
concrete values, as the certificate goal, joined with `parts` exactly
like the "value" and "exit" kinds already are. Measured on swap: the
obligation `0 <= (i+1) && (i+1) < len(s)` is false at the witness, the
certificate carries `assert(!(...)) by (compute_only)`, and
verifiers/verus.py accepted it, minting the REFUTED that made swap COUNT
(`off-by-one twin REFUTED`, witness s=[0], i=0, j=0). reverse needed no
such extension: its measured twin (invariant-drop#1) is an "exit"
witness (s=[], i=0, r=[0]), the same kind seq_max and first_even already
certify, and the ONLY change that mattered there was `_tlit` already
accepting a list of ints as a `{"_seq": [...]}` node (present ahead of
this task) and `expr()`'s existing `"_seq"` case (also already present)
rendering it as `seq![(0int)]`, so a seq-valued witness slots into the
existing "exit" certificate path with no new code.

Regression, measured 2026-09-09: `swap` and `reverse` COUNT (real
VERIFIED, twin REFUTED); all 15 previously committed tasks still read
`verified / refuted` in the verus column exactly as t/AGREEMENT.md
records, and `out/abs.rs`, `out/first_even.rs` and `out/digit_sum.rs`
(one v0, two v1 with a loop, chosen to cover both lowering paths) are
byte-identical before and after this change.

SEQUENCES: LITERALS, CONCATENATION, SLICES (2026-09-09, SPEC.md
"Sequences: literals, concatenation, slices (v1)"). Three new Expr forms,
each mapped straight onto a kernel-native form, measured with a probe file
before touching the lowering: `{"op": "seq", "args": [...]}` (`[e1, ...,
en]`) is vstd's own `seq!` macro, `s + t` on two seqs is Verus's native
`Add` impl for `Seq<int>` (`s.add(t)` under the hood, measured identical
either way, probe_seq_basic.rs), and `{"op": "slice", "args": [s, a, b]}`
(`s[a..b]`) is `s.subrange(a, b)` (vstd::seq::Seq::subrange). None of the
three needed a new BIN_OPS/NARY_OPS entry beyond `expr()`'s own "seq" and
"slice" cases: `+` was ALREADY in BIN_OPS, mapped to Rust's own `+`, and
Verus's operator overloading picks the `Seq<int>` impl or the `int` one by
the same operand types the SOURCE expression already carries, exactly as
SPEC.md states ("one operator name, polymorphic by the types of its
operands exactly as `==` already is") -- no dispatch this file has to do
itself. The empty literal renders as `Seq::<int>::empty()` rather than
`seq![]`, reusing the spelling the certificate builder's private `_seq`
ground node already had (`expr()`'s "_seq" case, present since "Sequences
as values"), so there are now two AST shapes ({"op":"seq","args":[]} from
a t task, {"_seq":[]} from a witness) that render identically rather than
two macros to keep in sync.

DEFINEDNESS. `seq` and `+` cost NOTHING new: both are total per SPEC.md
("a literal is defined iff all its elements are"; "a concatenation is
defined iff both arguments are"), which is exactly the formula `defined()`'s
existing catch-all already computes for every operator not given its own
case (`_conj([defined(a) for a in args])`) -- `+` was already routed
through it for the int/int case, and the seq/seq case asks the identical
question of the identical two arguments, so `defined()` needed no new
branch for either op. `slice` is the one that costs something: Verus's
`subrange` carries a `recommends`, not a `requires` (measured,
probe_subrange2.rs: an unguarded out-of-bound `s.subrange(0, 1)` on an
empty `s` compiles with only a "recommendation not met" NOTE, no error,
and critically does NOT totalize -- the very next line's
`assert(r.len() == 1)` genuinely FAILS to verify, so an unguarded slice is
neither rejected nor silently given the length its caller expects). A
lowering that emitted `subrange` bare would therefore neither catch a bad
slice (no requires to fail) nor prove anything false about it (no
totalized value to exploit): it would just read UNPROVED wherever the
bound actually matters, which is not the same failure as `at`'s but is the
same WRONGNESS SPEC.md's "Definedness" section forbids. So `defined()`
gets a "slice" case emitting the obligation the docstring above already
gives a name to: `0 <= a && a <= b && b <= len(s)`, discharged by the
existing `_assert_defined`/`_wf_lemma` machinery with no new plumbing,
the same shape as `at`'s two-conjunct bound with one more clause.

MEASURED, tasks/tail.json (`r := s[1..]`, loop-free) and
tasks/filter_pos.json (`r := r + [s[i]]` inside a loop, plus `r := []` for
the initial empty literal): both COUNT on first measurement, no lowering
fix needed beyond the `expr()`/`defined()` cases above. tail's twin
(off-by-one, `s[2..len(s)]` on a length-1 `s`) is an "undefined" witness
handled with NO new certificate code: `_undef_obligation` already replays
`defined()` over the twin body, and the new "slice" case is what it finds
false (witness s=[0]: `0 <= 2 && 2 <= 1 && 1 <= 1` fails on its middle
conjunct), so the certificate the existing machinery emits is
`!(0 <= (1+1) && (1+1) <= len(s) && len(s) <= len(s))`, ground, and Verus
accepts it under compute_only. filter_pos's twin is an ordinary
invariant-drop "exit" witness, the kind every loop task already
certifies; its exit state's `r` substitutes a seq literal (`seq![1int]`)
through the same `_tlit`/`expr()` path "Sequences as values" already
built. Neither task exercised `_gint`, `_tlit`, or `_unroll` beyond what
they already handled, so no certificate-builder code changed. swap and
reverse are BYTE-IDENTICAL to their prior `out/` sources (`cmp`, all four
files), confirming the two new `expr()`/`defined()` cases are additive
and untaken by any previously committed task. Cells (out/agent-verus-
seqops/, this run): tail COUNTS (real VERIFIED, twin REFUTED, witness
s=[0] -> slice bounds [2..1] outside 0<=a<=b<=1), filter_pos COUNTS (real
VERIFIED, twin REFUTED, invariant-drop#1, witness s=[], i=1, r=[1]), swap
and reverse unchanged (both COUNT, byte-identical sources). No kernel
trigger-inference gap was hit: tail's and filter_pos's foralls both index
a Seq (`r[k]`, `s[k+1]`) so `_has_indexable` already lets Verus's
automatic inference find them, same as every previously committed seq
task; `slice` itself needed no trigger case in `_has_indexable` or
`_mod_div_trigger` since no committed quantifier body contains one.

GUARD DEFINEDNESS (2026-09-09, the residual t/COVERAGE-lifted-785.md names:
"a `div`/`mod` in a loop guard is a definedness obligation ... verus ...
doesn't lower yet"). `loop()` used to raise NotImplementedError outright
whenever `defined(cond)` or `defined(decreases)` was non-trivial, which is
exactly what the two MBPP-DFY IsPrime tasks hit (`while i <= n / 2`, guard
and decreases both containing `n div 2`; the committed `is_prime` never
showed this because its own guard is `i * i <= n`, no div/mod at all).
Fixed the same way an ordinary statement's obligation is discharged: the
combined obligation `defined(cond) && defined(decreases)`, plus every
div/mod pair's Euclidean-law bridge (`_div_mod_law`, deduplicated across
`cond` and `decreases`), is emitted as the FIRST lines of the recursive
loop helper's own body, before the `if {cond} {...}` that is the only
place `cond` is ever evaluated. This covers every evaluation of the guard,
including the outermost one, since even the initial call from the loop's
own call site runs through this same helper body; no call-site or
`req_clauses` change was needed, since the assert is proved from the
helper's own `requires` (already every invariant in scope), the same
context an ordinary in-body `_assert_defined` already relies on. Trivial
(`_conj([defined(cond), defined(decreases)]) == TRUE`, true for every
previously committed loop task) emits nothing, so `is_prime`, `first_even`
and `tail` are byte-identical before and after this change (checked
directly, `cmp`, real and twin, all six files).

That fix turns the two IsPrime tasks' verdict from ABSTAIN into a real
kernel attempt, and surfaces a SECOND, separate residual: Verus's
automatic termination check for a `proof fn`'s recursive `decreases`
clause cannot discharge one containing `div` or `mod` at all, regardless
of provability. Measured by isolating the two loop clauses on a minimal
probe (`i <= n / 2` as the guard alone, decreases `n - i`: verifies;
decreases `(n / 2) - i` alone, guard linear: "could not prove
termination" at the recursive call; decreases `n % 5 - i` alone: same
failure; decreases `n * 2 - i`, a literal-multiplication analogue: no
termination error). No hint closes it: an explicit local `assert` of the
same nonneg/strict-decrease facts before the call, `#[verifier::nonlinear]`
on the helper, restating the guard or the Euclidean law as an extra
`requires` clause, and wrapping the division in its own non-recursive
`spec fn` (hoping the checker would treat it as an opaque call rather than
expanding it) were all tried and none changes the error. There is no
escape hatch to reach for either: `strings` on the installed
`rust_verify` binary (0.2026.08.30.b432e82) shows `decreases_by` and
`decreases_when` exist as attributes, but both carry the diagnostic "only
spec functions can use decreases_by/recommends_by" / "only spec functions
can use decreases_when" -- neither is available on a `proof fn`, which is
what every t loop helper is (see LOOPS above). Since the task's own
`decreases` is `n div 2 - i` and this lowering owes it verbatim, not a
kernel-friendlier equivalent (SPEC.md: `decreases` is an Expr like any
other, faithfully rendered, not re-derived), there is nothing left for
THIS lowering to do about it: `dafny_synthesis_task_id_3__isNonPrime` and
`dafny_synthesis_task_id_605__isPrime` both read verus unproved/unproved
(real and twin alike, `out/agent-verus-guard/`, PATH including
`~/.cargo/bin` so `rustup` resolves) -- the kernel's own message is
"could not prove termination" at the recursive call, not a fault in
either the real body or the invariant-drop twin, and not a defect in the
task's invariants either (nothing about the INVARIANTS blocks this; the
decreases clause alone does, independent of every other clause on the
loop). Measured (`cmp`, real and twin): `is_prime`, `first_even` and
`tail` are unaffected by either finding, byte-identical to their
committed `out/*.rs`.

RESOLVED 2026-09-11 (ROADMAP 16.2): the paragraph above's conclusion was
wrong about WHY the recursive call fails termination, reached from two
probes that do not actually match `isNonPrime`'s own shape. Isolated
again, precisely: `decreases (n / 2) - i` paired with `cond i <= n` (no
`/ 2` on the guard's own bound) is a GENUINELY UNSOUND measure -- the
guard stays true well past the point `(n/2) - i` goes negative, so
Verus is CORRECTLY refusing a decreases that fails its own SPEC.md
obligation ("`>= 0` whenever the guard holds"); that is the probe the old
paragraph called "decreases (n/2)-i alone, guard linear" and it proves
nothing about `isNonPrime`, whose guard and decreases are the ALIGNED
pair `cond: i <= n/2`, `decreases: (n/2) - i` (`>= 0` exactly whenever
the guard holds, by construction, exactly SPEC.md's own criterion). The
real defect is a translation artifact of how `loop()` encodes a `while`
as a self-checking recursive function: the recursive call at the bottom
of `if cond {...}` fires once MORE than the guard's own strict-decrease
budget allows whenever `cond` is `<=` (or otherwise lets the measure hit
exactly 0 while still true) -- the LAST such call passes a state whose
measure is `old_measure - 1`, and when `old_measure` was already 0 (the
final true evaluation of `i <= n/2`), that is -1, which Verus's `int`
decreases check requires to stay `>= 0` (this box's `rust_verify`,
confirmed on a from-scratch minimal probe, `probe_term.rs`/`probe_term2.rs`
in this session's scratch dir: `cond i<=n, decreases n-i` alone, no div
anywhere, fails with the identical "could not prove termination" the old
paragraph blamed on `div`/`mod` -- the div was never the cause). A strict
`<` guard never hits this (guard true implies the hi-i measure is >= 1,
so one decrement never goes negative), which is exactly why every
previously committed loop task -- ALL of them `<`, never `<=` -- never
surfaced it.

The fix costs nothing about fidelity: `decreases` is rendered as `(the
task's own Expr) + 1`, a CONSTANT SHIFT of the measure, not a different
one. SPEC.md's obligation on decreases ("`>= 0` whenever the guard holds
and strictly decreases") is a property of the FAMILY of valid measures,
not of one specific numeral; adding a constant preserves both clauses
identically (if `m >= 0` whenever guard holds, so is `m+1`; if `m`
strictly decreases each step, so does `m+1`) while giving Verus's
stricter-than-SPEC.md `int` check (which additionally wants the NEXT
call's measure to be `>= 0`, not just the CURRENT one) exactly the unit
of slack the `<=` boundary was missing. Nothing that changes what the
kernel checks moves: `requires`, `ensures`, `invariants` are byte-for-
byte what they were; only the auxiliary termination witness this
lowering hands Verus is different, the same category of accommodation
`_div_mod_law` and the nonlinear_arith bridges already are. Measured
2026-09-11: `isNonPrime` (3) and `isPrime` (605) both move
unproved/unproved -> verified/refuted; every previously committed
verus task's `out/*.rs` is unaffected in substance (the `+ (1int)`
suffix appears on every loop's `decreases` line now, including the
already-working `<` ones, where it is provably inert -- `is_prime`,
`first_even`, `tail` all still verify, `cmp` confirms real and twin
alike, only that one line differs byte-for-byte).

CORRECTION, same date (2026-09-11, a later pass this same day, ROADMAP
16.2's divisor-bound item): the "-> verified/refuted" claim just above
was premature -- termination was the only residual this pass had
isolated so far, but fixing it surfaces a SECOND, separate gap
underneath: the recursive helper's own `ensures` only carries the
invariant over `[lo, i)` at the loop's normal exit, while the task's own
`ensures` (and this file's own top-level wrapper) needs the WIDER `[lo,
n)` -- measured directly (`rust_verify` on the termination-fixed file
alone): "postcondition not satisfied" at the wrapper's trailing
`result`, not a termination error at all. Both tasks in fact read verus
real=unproved (not verified) until `_divisor_bound_target`/
`_divisor_bound_verus_defs` (below, near `class _V1`'s own `loop`
method) close it later this same day -- see that pair's own docstring
for the actual fix and the measurement that moves them to verified.

PAIRS (2026-09-10, SPEC.md "Pairs (v1)"). New type `{"pair": [T1, T2]}`
(T1, T2 one of "int"/"bool"/"seq") and three new Expr forms: `pair`
(construction), `fst`/`snd` (projection). Verus's own product type is the
kernel-native match, measured before writing any of this
(probe_pair_basic.rs): a `proof fn` taking and returning `(int, int)`,
with `.0`/`.1` projections in its own `ensures`, 0 errors -- so a pair
type needs NO declaration of its own here, unlike SPARK's per-pair-type
record or Lean's `Int x Int`, and it stays inside this file's one
existing semantic decision (module docstring, top): everything still
lowers to `proof fn` over mathematical `int`, a pair of two of those
included, no exec/machine-int arm. `_vty(ty)` replaces the flat
`TYPES[ty]` lookup at every site a t type resolves to a Verus one (a
param, a return, a local, and a spec_fun's own params/result, which
SPEC.md restricts to int/seq/bool so `_vty` there only ever falls
through to `TYPES` unchanged): a dict `{"pair": [T1, T2]}` renders `(V1,
V2)`, recursing at most one level since SPEC.md forbids a pair of pairs.
`expr()`'s three new cases are exactly the notation: `pair` is `(a, b)`,
`fst`/`snd` are `.0`/`.1`. `defined()` needed NO new case for any of the
three: SPEC.md's own words, "pair ... defined iff both components are"
and "fst/snd ... always defined on a pair" (given a well-typed operand,
check_wf's job and not this function's), are exactly the formula the
existing total-operator catch-all already computes for every op with no
case of its own, `_conj([defined(a) for a in args])` -- one argument for
`fst`/`snd`, two for `pair`.

EQUALITY (the one thing SPEC.md flags to measure: "`=~=` or a
componentwise form may be needed"). `BIN_OPS` already routes `==`/`!=`
through Rust's own operator on any two operands of the same emitted
type, so a pair needed no new entry there either, IF Verus's native
tuple `==` already means what SPEC.md wants. Measured directly:
`(a, b) == (c, d)` for two `int` components (probe_pair_eq_int.rs) and,
the harder case, for one `Seq<int>` component under a BARE `b == d`
hypothesis rather than an elementwise one (probe_pair_eq_seq_bare.rs, no
per-index fact given at all) both verify with 0 errors. So Verus's tuple
`==` is native structural equality composed from each field's OWN `==`
-- already extensional for `Seq<int>` at the Z3 level, the "EXTENSIONAL
EQUALITY" finding above -- and a pair costs NOTHING extra: no `=~=`, no
componentwise rewrite, the same free ride v1's seq `==` already gets.

LOOP FRAME RULE. A pair-typed local, return, or read-only parameter
needed no change to `loop()`: `scope` was already generic over Verus
type STRINGS (`(type, mutable)` per name), so a `(int, int)`-typed slot
frames by name exactly like an `int` or `Seq<int>` one, whether assigned
or carried read-only through the recursive helper's own parameter list,
with no code path caring which. min_max's own `r` (pair-typed, assigned
only after the loop, never inside it) exercises exactly the read-only
half of this for the first time: it rides through `t_lp_min_max_0`'s
parameters unmodified, present at all only because
`_invariant_candidates` always appends the return to a loop's in-scope
names.

EARLY EXIT. `_dummy(ty)` (the throwaway value a wrapped loop helper's
unused return/state slot needs, SPEC.md "Early exit") took a Verus type
STRING before this task; it now takes the t-level type instead (a base
name, or a pair dict) so it can recurse into a pair's own two components
the same way `_vty` does, rendering `(dummy1, dummy2)`. No committed
pair task carries a `return` inside a loop, so this path is unexercised
by measurement, only by construction; named here rather than left
silent.

THE CERTIFICATE EMITTER surfaced the one real ambiguity the construct
creates, on the FIRST measurement of either committed task: interp.py's
own witness encoding (`_j`) deliberately prints a Pair as a plain 2-list
("so a seq component ... prints as a list too rather than as a raw
tuple", interp.py's own docstring), so a pair of two ints is
INDISTINGUISHABLE, as JSON, from a length-2 seq of ints -- and BOTH
committed pair tasks' measured witnesses are exactly this shape:
divmod_pair's wrong-var twin, witness x=1, y=1, `_real` [1, 0], `_twin`
[0, 1]; min_max's collapse-if twin, witness s=[0, 1], `_real` [0, 1],
`_twin` [1, 1]. `_tlit`, which turns a witness value into a t literal for
the certificate formula, had no way to tell these apart from a seq
before this task (there was no pair for a seq to be ambiguous with); it
now takes an optional declared TYPE alongside the value -- `_cert_formula`
threads every param's and the return's own type through (`tmap`), the
two kinds it tracks -- and checks the UNAMBIGUOUS Python shapes first (an
interp.Pair or a runtime tuple, which only interp.exit_env's post-state
and `_undef_obligation`'s own interp.ev results ever carry, since neither
is ever JSON-round-tripped and so neither can collide) before falling
back to the type-directed decode of a plain list; `_to_py` is the
matching fix on `_undef_obligation`'s own input side, rebuilding a
witnessed PARAM back into an interp.Pair before replaying the twin body
through interp.ev. A loop-LOCAL's own type is not threaded either way
(neither function reconstructs the loop's scope), so a pair-typed local
in an "exit"/"undefined" witness still falls back to the untyped guess;
named here as a residual gap because neither committed pair task
exercises it (divmod_pair has no loop; min_max's only pair is its
return, assigned once after the loop, never a loop-local, and its landed
twin is "value"-kind, not "exit", exactly because -- per SPEC.md's own
text -- INVARIANT-DROP found no witness for it at fifteen times the
state cap).

MEASURED (out/agent-verus-pairs/, PATH including
~/.local/verus/verus-x86-linux so `verus` resolves and ~/.cargo/bin so
rustup does): divmod_pair COUNTS (real VERIFIED, wrong-var twin REFUTED,
witness x=1, y=1 -> real [1, 0], twin [0, 1], matching SPEC.md's own
committed witness exactly); min_max COUNTS (real VERIFIED, collapse-if
twin REFUTED, witness s=[0, 1] -> real [0, 1], twin [1, 1], also matching
SPEC.md, and confirming its own note that INVARIANT-DROP fell through
for this task with no witness). Regression (`cmp`, real and twin, every
file): all 19 previously committed tasks still COUNT and their
`out/<name>.rs` and `out/<name>_twin.rs` are byte-identical to before
this change -- the five this task named (abs, swap, reverse, tail,
filter_pos) and, beyond that, every other committed task (all_nonneg,
contains, count_matches, digit_sum, factorial, fib, first_even, gcd,
is_prime, linear_search, max, remainder, seq_max, sum_upto) -- so the
`TYPES[ty]` -> `_vty(ty)` refactor and `_tlit`'s new signature are
additive and untaken by anything committed before this task. No Verus
construct was refused: every SPEC.md "Pairs" form (the type, `pair`,
`fst`, `snd`, `==`/`!=`, a pair through the loop frame rule, and a
pair-valued witness through the certificate) lowers.

NESTED SEQUENCES (2026-09-10, SPEC.md "Nested sequences (v1)", ROADMAP
12.7). New type `{"seq": "seq"}`, a finite seq whose elements are seqs of
ints, `seq<seq>`; the elementary `"seq"` is unchanged. NO new Expr forms
(SPEC.md is explicit about this): every existing seq operator is
polymorphic by the static type of its operands, exactly as `+` and `==`
already are, and Verus's OWN `Seq<T>` is generic over its element type in
both exec and spec/proof code, so `Seq<Seq<int>>` needed no declaration
of its own here, the same free ride a pair type got. The one real
construction cost is `_vty(ty)`, which used to assume any dict-shaped
type was a pair (`ty["pair"]`, an unguarded KeyError on {"seq": "seq"} --
measured directly, the first swap_rows attempt crashed there before this
fix) and now checks the key first: `"seq" in ty` recurses one level and
wraps in `Seq<...>`, `"pair" in ty` is the existing case. `_dummy` had
the identical bug and got the identical fix (an unexercised nested-seq
case, since neither committed task has a `return` inside a loop -- see
below -- named by construction, the same posture this function already
took for a pair of pairs). Every OTHER site a t type reaches Verus
through (`scope`'s (type, mutable) entries, a loop's read-only and
assigned params, a spec_fun's own params/result) already goes through
`_vty`, so nothing else needed touching: the loop frame rule havocs a
nested-seq local, param, or return by NAME exactly like an `int` or
`Seq<int>` one, no code path caring which, confirmed by row_max_len's own
`m` riding read-only through `t_lp_row_max_len_0`'s parameter list
unmodified.

OPERATORS. `expr()`'s existing cases render every one with NO new
branches: `seq` (the literal) recurses into `seq![seq![..], ...]`
naturally since each row is itself rendered by the SAME "seq" case;
`len(s)` is `.len()` regardless of element type; `at(s, i)` (`s[i]`) and
the chained `s[i][j]` are the SAME `at`-of-`at` AST shape `expr()`'s "at"
case already renders as plain bracket indexing, `s[i][j]`, needing no
chain-aware code since Rust's own `[]` composes; `s + t`, `s[a..b]`
(`.subrange`), `update(s, i, r)` (`.update`), and `fill(n, r)`
(`Seq::new(n as nat, |_t_fill_i: int| r)`, `r` now row-typed rather than
int) are all the identical calls "Sequences as values" and "Sequences:
literals, concatenation, slices" already built, generic over Verus's own
generic `Seq<T>`. Measured directly before touching either committed
task (probe_nested_ops.rs, one proof fn exercising all eight forms plus
the empty-nested-literal spelling): 0 errors, verified 2. `defined()`
needed NO new case either: its existing "at"/"update"/"slice"/"fill"
cases already compute the chained obligation by ordinary recursive
composition -- `defined(at(at(m,i),j))` walks to
`defined(m) && defined(i) && 0<=i<len(m) && defined(j) && 0<=j<len(m[i])`,
which IS SPEC.md's stated rule for `s[i][j]` ("iff 0<=i<len(s) and
0<=j<len(s[i])") with no case written for it, exactly as the generic
composition already gave `at`'s single-index bound for free before this
task.

EQUALITY. SPEC.md flags this explicitly ("extensional and recursive: two
nested seqs are equal iff same length and equal rows") and this file's
own build note asked for `=~~=` (Verus's DEEP extensional-equality macro
for nested collections) to be measured rather than assumed. Measured
(probe_nested_eq.rs, five proof fns): bare `==` between two
`Seq<Seq<int>>` values already IS the SPEC.md recursive equality at the Z3
level with NO help needed -- two differently-built-but-equal nested
literals (`assert(a == b)`), `==` used as a hypothesis to derive a
per-row fact (`a == b |- a[k] == b[k]`), and the hard direction with no
given index fact at all (`a.len()==b.len() && forall k. a[k]==b[k] |- a
== b`) all verify with 0 errors, bare, and `=~~=` changes nothing
(probe fns 4 and 5 in the same file, one with plain `==`/`==` throughout
and one rewritten with `=~=`/`=~~=` throughout, both verify identically).
So nested seq `==` is exactly as free as flat seq `==` was ("EXTENSIONAL
EQUALITY" above): `BIN_OPS` needed no seq-of-seq-specific entry, and
`=~~=` is banked as measured-unnecessary rather than built, the same
outcome the flat case reached with `=~=`.

THE CERTIFICATE EMITTER needed real work, unlike the operators: a nested
seq's witness value collides with nothing at the Pair/seq level (SPEC.md
restricts v1 to no seq of pairs), but introduces its OWN ambiguity one
type up, discovered the same way Pairs' was -- by trying to certify the
first measured witness and watching it fail. interp.py already represents
a nested seq's runtime value as a tuple of tuples (`_j`'s own docstring:
"a row is itself a tuple ... a bare list(v) here would print a nested seq
as a list of TUPLES"), and a NONEMPTY one needs no type hint: its first
element is itself a tuple/list, unmistakable from a flat seq's own
elements (always ints). Only the EMPTY case collides -- `()` or `[]` is
indistinguishable, by shape alone, from an empty FLAT seq -- exactly the
Pair/seq shape one level down, so `_tlit` and `_to_py` both grew a
`"seq" in ty` branch alongside their existing `"pair" in ty` one (which
had to stop assuming any dict `ty` was a pair, the same unguarded-`ty
["pair"]` bug `_vty` had, since `_cert_formula`'s `tmap` now hands both
functions a `{"seq": "seq"}` type as often as a pair one): a new
nonempty case builds `{"_nested_seq": [row, ...]}` (each row a `{"_seq":
...}` node, so an empty ROW inside a nonempty outer literal -- swap_rows'
own witness, `m = [[]]` -- renders correctly for free through the
existing "_seq" case) and the empty case asks `ty` exactly once, `_tlit`
choosing `{"_nested_seq": []}` for `Seq::<Seq<int>>::empty()` where a
flat empty seq would have chosen `{"_seq": []}` for `Seq::<int>::empty()`.
`_to_py`'s matching rebuild recurses into `_to_py(row, "seq")` per row
before `interp.ev` replays the twin body, since a row LEFT as a JSON list
rather than converted to a tuple would silently fail every tuple-shaped
comparison `interp.ev` does on it -- unexercised by measurement on
divmod_pair/min_max (neither has a seq param at all) but load-bearing
here, since swap_rows' witness IS the "undefined" kind that walks
`_undef_obligation`'s `interp.ev` replay. `expr()` gained one ground node,
`"_nested_seq"`, rendering `seq![<row>, ...]` (or `Seq::<Seq<int>>::empty()`
when empty) by calling itself on each row -- the SAME recursive call that
already renders `"_seq"`, so no row-spelling logic is duplicated. `subst`
needed `"_nested_seq"` added to its ground-node passthrough (the same one
line `"_seq"` already had) or it would have tried `e["op"]` on a dict with
no such key. `_gint` needed one more case, `len` of a `"_nested_seq"`
node, alongside its existing `len`-of-`"_seq"`: row_max_len's own ensures
quantifies `forall k in [0, len(m))` and `_unroll` cannot iterate an
unground bound, so once `m` is substituted by its witness the outer row
count has to resolve the same way a flat seq's length already did. A
loop-LOCAL's own type is still not tracked past `_cert_formula`'s `tmap`
(neither this task's construct nor Pairs' own residual closes that gap),
named again for the same reason: not exercised by either committed
nested-seq task (swap_rows has no loop; row_max_len's only nested-seq
name is its read-only PARAM `m`, never reassigned).

MEASURED (out/agent-verus-nested/, PATH including ~/.cargo/bin so rustup
resolves and ~/.local/verus/verus-x86-linux so verus does): swap_rows
COUNTS on first measurement after the fixes above (real VERIFIED,
off-by-one twin REFUTED, witness m=[[]], i=0, j=0 -- the shifted index
`j+1` running off the single row, `at`'s own out-of-bound "undefined"
witness kind swap's own off-by-one twin already established, one level
up); row_max_len COUNTS on first measurement (real VERIFIED,
invariant-drop twin REFUTED, witness exit at m=[[], [0]], i=2, r=0 -- the
dropped upper-bound invariant letting the loop exit at i==len(m) with r
left at its initial row-0 length, 0, instead of the max row length, 1).
Regression (`cmp`, real and twin, every file): abs, swap, tail,
filter_pos, divmod_pair and min_max -- one v0, and five v1 tasks spanning
every prior seq/pair construct and loop shape -- all still COUNT with the
identical witnesses already on record, and their `out/<name>.rs` and
`out/<name>_twin.rs` are byte-identical to the committed ones, so the
`_vty`/`_dummy`/`_tlit`/`_to_py`/`_gint`/`expr`/`subst` changes above are
additive and untaken by anything committed before this task. No Verus
construct was refused: every SPEC.md "Nested sequences" form (the type,
the literal, `len`, `at`, the chained `s[i][j]`, `+`, the slice, `update`,
`fill`, `==`/`!=`, a nested seq through the loop frame rule, and a
nested-seq-valued witness through the certificate, undefined and exit
kinds alike) lowers.

NESTED SEQUENCES RESIDUAL (2026-09-10, fuzz family v1nested, 18 tasks: 13/18
read verus verified/refuted on the first measurement; this addition closes
the other 5, named in fuzz-nested-residual-verus.txt: fz_v1nested_026,
fz_v1nested_069, fz_v1nested_150, fz_p_nest_eq, fz_p_nest_empty).

fz_p_nest_empty: no-twin/no-twin, unaffected by anything below and left
exactly as measured -- SPEC.md's own empty-literal task, no twin operator
applies to a body with no comparison/arithmetic/loop for any mutator to
touch, expected and untouched.

fz_v1nested_069: BEFORE malformed/malformed (real and twin alike). Verus's
own error: `let mut m: Seq<Seq<int>> = Seq::<int>::empty();`, a bare type
mismatch (E0308) -- `expr()`'s "seq" op rendered EVERY empty literal
`Seq::<int>::empty()` unconditionally, with no way to know `m`'s own
declared type was `Seq<Seq<int>>`. Fixed by threading an optional `vty`
(the VERUS type string, not a t type) through `expr()`, used only by the
"seq" op's empty-args case, supplied at the three statement-level sites an
expression's own type is actually known: `stmts()`'s "assign" (from
`scope[name]`), "var" (from the declaration's own `_vty(v["type"])`), and
"return" (from `_vty(task["returns"][0]["type"])`). Fixing the mismatch
uncovered a SECOND, previously-masked issue once the file actually
compiled: "postcondition not satisfied", Verus itself reporting "low
confidence" in its own auto-chosen trigger for `forall k| ... m[k].len()
==1 && m[k][0]==s[k]` -- it picked the bare `s[k]` alone, which never
reconnects to `m` across the loop's own append (`m + seq![seq![s[i]]]`),
so the carried invariant could not be shown to survive one more
iteration. Fixed generally: `_at_roots_by_var` collects every DISTINCT
base sequence a forall/exists body indexes directly by its own bound
variable; when there are two or more AND the body also contains a
genuine chained read (`_has_chained_at`, `X[i][j]`, one nesting level
deep -- gating on this rather than on "two roots" alone matters, see
REGRESSION below), `expr()` now emits one INDEPENDENT `#![trigger ...]`
per distinct root instead of trusting Verus's own single-candidate pick.
AFTER: verified/unproved. The real body verifies outright. The twin
(`i < s.len()` weakened to `i <= s.len()`, running the loop one
iteration past the end) does NOT get certified REFUTED: harness.py's own
`_undef_obligation` walks a twin body's TOP-LEVEL statements only and
gives up (returns None) the first time it meets an "if", "while", or
"return" before the failing one, by its own docstring's admission ("not
special-cased to the first" statement, but never implemented for the
INSIDE of a loop either) -- fz_v1nested_069's own undefined access
(`s[i]` at `i==len(s)`) happens inside the while loop's body, the first
task, committed or measured, to land there, so no certificate is built
and the harness reports "unproved" rather than "REFUSED". Pre-existing
and general (loop bodies, not nested seqs, are what `_undef_obligation`
does not walk), and outside this file's own certificate-authoring
surface (`_undef_obligation` is a `harness.py` function, not one of
this file's) -- left named rather than patched, since fixing it means
teaching `_undef_obligation` to replay a WHILE loop's own iterations, a
materially larger change than this residual's own three lowering bugs.

fz_v1nested_026 and fz_p_nest_eq (identical shape, `_shape: eq_nested`):
BEFORE unproved/refuted. Verus's error: "postcondition not satisfied" on
`r == (len(m)==len(n) && forall k. m[k]==n[k])` where the body computes
`r = (m == n)` for `m, n: Seq<Seq<int>>`. The "EQUALITY" measurement on
record above showed bare `==` on `Seq<Seq<int>>` is already full
recursive equality at the Z3 level in the direction a proof GOAL needs;
this residual measured the OTHER direction: `m == n` in scope does NOT,
by itself, let Z3 conclude `forall k. m[k]==n[k]`, nor its negation
`m.len()!=n.len() || exists k. m[k]!=n[k]` (probe2.rs isolated the
failure to exactly the disequality half; probe4.rs showed
`assert(!(m =~= n));` fixes that half alone). probe6.rs found the
single, unconditional fix: `assert((m == n) == (m =~= n));`, which
resolves BOTH directions at once with no branch on which value `==`
took. Fixed generally: `_nested_eq_bridges` walks an expression for
every `==`/`!=` node whose both operands are nested-seq-typed
(`_nested_seq_operand_ty`, a var lookup or a same-type pass-through
through `+`/`slice`/`update`), and `_V1._assert_nested_eq` emits one such
bridge assert per distinct occurrence, called from the same three
statement sites `vty` is threaded from (assign, var-init, return).
AFTER: verified/refuted on both tasks, matching `_expect: verified` and
the row already on record for dafny/spark (also verified/refuted).

fz_v1nested_150: BEFORE unproved/unproved (every kernel in the row
struggled, not verus alone). Verus's error: "assertion failed" inside
`t_wf_fz_v1nested_150_fn_rowsum`, the spec_fun definedness lemma for
`rowsum(row, k) = if k<=0 {0} else {rowsum(row,k-1) + row[k-1]}`, checked
with NO hypothesis at all (`emit()`'s spec_fun loop passed `context=[]`
to `_wf_lemma` unconditionally) -- unlike count_matches' own
`count(s,x,n)`, whose ite condition self-guards BOTH ends in one clause
(`(n<=0) || (n>len(s))`), rowsum's `k<=0` guards only the base case, so
the lemma was asking Verus to prove `k>0 ==> k<=row.len()` for
COMPLETELY UNCONSTRAINED row and k -- false in general (row=Seq::empty(),
k=5 a trivial countermodel), even though the ONLY calls this task ever
makes (the loop invariant, the top-level ensures) stay within
0<=k<=len(row). Fixed generally, not by naming rowsum: `_spec_fn_domain_
context` walks a spec_fun's own body for `at`/`update` nodes indexing a
seq-typed PARAM at the decreases variable (`_walk_at_seq_params`), and
for each such param whose length its OWN `ite` conditions never already
mention anywhere (`_mentions_len` over every `_ite_conds` in the body --
count_matches' cond mentions `len(s)` directly, so nothing is added
there), adds `decreases <= len(param)` as the wf lemma's hypothesis
(probe150b.rs: this bound ALONE suffices -- the base case already gives
the lower bound `k>0` for free from the ite's own negated cond, so `0 <=
decreases` is never added standalone). AFTER: verified/unproved. The
real body verifies outright, closing the "every kernel struggled" row
for verus specifically. The twin (the same `<` -> `<=` boundary widening
as fz_v1nested_069, one loop iteration past the end) hits the IDENTICAL
`_undef_obligation` loop-walking gap named above, for the identical
reason (the undefined `row[k]` access is inside the while loop's own
body) -- named once here, not twice.

REGRESSION. The first version of both new fixes was NOT this narrow: an
unconditional `0 <= decreases` plus a length bound for every seq param a
body indexes (regardless of self-guarding) changed count_matches' and
digit_sum's own committed `t_wf_..._fn_...` lemmas (an extra `requires`
neither needed), and firing the multi-trigger on any two-distinct-root
forall (regardless of a chained read) changed swap's and swap_rows' own
committed foralls (an explicit trigger neither needed) -- caught by the
SAME regression method this file already uses throughout, comparing
every committed task's OWN `out/<name>.rs`, not by reasoning alone.
Narrowing both (the self-guard check via `_mentions_len`/`_ite_conds`;
the chained-read gate via `_has_chained_at`) restored byte-identity.
Regenerated (`lower_verus.lower(task, task["body"])`, compared against
the committed file) all 23 committed verus tasks -- abs, all_nonneg,
contains, count_matches, digit_sum, divmod_pair, factorial, fib,
filter_pos, first_even, gcd, is_prime, linear_search, max, min_max,
remainder, reverse, row_max_len, seq_max, sum_upto, swap, swap_rows,
tail -- all byte-identical to `out/<name>.rs`. swap_rows and row_max_len
additionally re-run through `harness.run_task` into
`out/agent-verus-nested2/`: both COUNT with the identical witnesses
already on record (swap_rows: m=[[]], i=0, j=0; row_max_len: exit at
m=[[], [0]], i=2, r=0), and all four files (`<name>.rs`/`<name>_twin.rs`
for both) are byte-identical to the committed ones.

LEFT, BY NAME. `_undef_obligation` (harness.py) does not walk into a
`while` (or `if`) body, so fz_v1nested_069's and fz_v1nested_150's twins
(both off-by-one loop-boundary widenings whose undefined access is
inside the loop) read verus verified/unproved rather than
verified/refuted: a pre-existing, general gap in the certificate
emitter's own statement walk, not a nested-seq defect, and not touched
here. fz_p_nest_empty is unaffected and untouched, as expected (no
comparison, arithmetic, or loop for any twin operator to apply to).

SOLE BLOCKERS, THE FIVE (2026-09-10, t/COVERAGE-lifted-785.md "Sole
blockers": the five lifted tasks verus alone kept out of the seven-column
bar). Measured first, not guessed: four read malformed/refuted (real
rejected before proof), one unproved/refuted (real rejected by the
prover). All five now COUNT.

THE FOUR MALFORMED (mfirstMaximum, mmaximum1, the two findMax tasks) are
ONE shape, named exactly by running each through `verus` directly before
touching any code: an "argmax" ensures, naming the CHAMPION INDEX rather
than the champion value, `forall k| ... ==> (a[FIXED] >= a[k])` where
FIXED is the loop's own running-best index (a tuple projection,
`t_res.0`/`t_res.1`, since the loop state is `(i, j)`) -- Verus's error is
"Could not automatically infer triggers for this quantifier", the same
message is_prime's own `n mod d` residual (2026-09-08 entry above) hit,
but a NEW cause: this file's existing `_has_indexable` already sees the
quantifier's `at(v, k)` term and so never even TRIES an explicit trigger
for it (its whole job is "does auto-inference have anything to grab"),
and Verus's auto-inference DOES have `v[k]` to grab -- it just fails
outright anyway, confirmed on a four-line probe (probe5.rs/probe6.rs/
probe7.rs) built before writing any fix: `v[p.0] >= v[k]` alone, no loop,
no proof body, still refused, and true whether the fixed index is a tuple
projection, a plain variable, or an arithmetic expression (`i0+1`), so
the trigger inference is confused by the SECOND, differently-indexed read
of the same seq, not by projections specifically. seq_max's own committed
`r >= s[j]` never hit this: its champion `r` is a VALUE, never an index
back into `s`, so there is no second read to interfere. Fixed generally:
`_has_fixed_at(body, v)` (a new function, walking the same shapes
`_at_roots_by_var` already does) is true when the quantifier body indexes
a seq at an expression that does not mention v at all (`_mentions_var`,
also new -- NOT a bare AST `!=` against `{"var": v}`, which an earlier
version of this fix used and which wrongly caught reverse's and tail's
own committed `s[len(s)-1-k]` / `s[k+1]`, indices that mention k without
being the bare variable, see REGRESSION below); when it fires alongside
at least one bound-var-indexed root (`_at_roots_by_var`, already built
for the "Nested sequences" trigger residual), `expr()`'s forall/exists
case now emits one explicit `#![trigger ...]` per root, the identical
mechanism and identical soundness argument (never removes a candidate
Verus's own inference would try, only adds the ones ambiguity hides) the
chained-read case already uses. Measured (`out/agent-verus-argmax/`):
all four now read real VERIFIED; three (mfirstMaximum, mmaximum1,
dafny_experiences' findMax) certify invariant-drop#2 REFUTED on the twin,
one (dafny_workout's findMax) the same, all COUNT.

THE FIFTH (hoareTripleReqEns) read unproved/refuted: `k_p == (k+2*i)+1`
with `requires k == i*i`, `ensures k_p == (i+1)*(i+1)` -- a straight-line
body, no loop at all, so none of the existing nonlinear machinery
(LOOPS' own invariant bridge, div/mod's `_div_mod_law`) is in the path:
Verus's error is a bare "postcondition not satisfied", its default
solver profile again having nonlinear arithmetic off (module docstring,
LOOPS) for a task-level `ensures`, not a loop invariant. Measured before
writing the fix (pht1.rs..pht4.rs): a bare assert with no hint fails, an
`assert(...) by (nonlinear_arith)` with no `requires` fails even with the
exact fact already assigned two lines above in the SAME proof fn (Verus's
nonlinear_arith solver sees only what its OWN `requires` list states, not
ambient context -- the identical two-step shape `_div_mod_law`'s own
docstring already documents: the requires clause is CHECKED against
ambient context by the default solver, then handed to the isolated
nonlinear solver as a premise), and substituting the return's own VALUE
expression for the return name in the ensures goal (so the goal never
mentions the return-name local at all) succeeds with just the task's own
`requires` as premises, no restatement of the return's value needed as an
extra one. Fixed generally, not by naming the task: `_nonlinear_ensures_
bridge` (new `_V1` method) emits this assert for every top-level `ensures`
clause `_has_nonlinear` flags, called from the two places a task-level
return happens -- `stmts`'s "return" case (the returned expression itself
is the value to substitute) and `emit`'s trailing `{rname}` for a body
with no explicit `return` (`_sym`'s own closed-form value over the whole
body, already built for LOOPS' invariant bridge; None, skipped, for a
body containing a `return` or `while`, so the two call sites never both
fire for one task). Guarded to skip entirely when the returned value
itself contains a `div`/`mod` (`_div_mod_pairs`), see REGRESSION: without
that guard this fires redundantly wherever `_div_mod_law` already
supplies the identity. Measured (`out/agent-verus-argmax/`): real
VERIFIED, off-by-one twin REFUTED (witness i=1, k=1 -> real 4, twin 5),
COUNTS.

REGRESSION. Both fixes' first versions were NOT this narrow, caught the
same way this file always catches it: comparing every committed task's
OWN `out/<name>.rs`, not by reasoning alone. An unguarded `_has_fixed_at`
(bare `!=` on the index AST instead of `_mentions_var`) added an
unneeded explicit trigger to reverse's and tail's own committed foralls
(`s[len(s)-1-k]`, `s[k+1]`, indices that mention k without being the bare
variable); an unguarded `_nonlinear_ensures_bridge` (no `_div_mod_pairs`
check) added a second, redundant nonlinear_arith assert to remainder's
and divmod_pair's own committed returns, both of which already verify
via `_div_mod_law` alone. Narrowing both (the mentions-check; the
div/mod-pairs guard) restored byte-identity. Regenerated
(`lower_verus.lower(task, task["body"])`, compared against the baseline
lowering) all 23 committed verus tasks -- abs, all_nonneg, contains,
count_matches, digit_sum, divmod_pair, factorial, fib, filter_pos,
first_even, gcd, is_prime, linear_search, max, min_max, remainder,
reverse, row_max_len, seq_max, sum_upto, swap, swap_rows, tail -- all
byte-identical. Seven of those (reverse, remainder, divmod_pair,
swap_rows, row_max_len, tail, is_prime -- spanning every prior
seq/pair/nested-seq/div-mod/loop shape) additionally re-run through
`harness.run_task` into `out/agent-verus-spotcheck/`: all seven COUNT
with the identical witnesses already on record.

t/COVERAGE-lifted-785.md's "Sole blockers" table is now stale for verus:
all five tasks it named read verus verified/refuted, none malformed or
unproved; regenerating that table is a coverage-script action, not a
lowering one, so left for the sweep that next regenerates it.

THE v1def FAMILY, THE UNDEF-WALK GAP, AND A TRIGGER GAP (2026-09-10,
reading /home/tmcuzzort/tup/t/out/reproduce-families/, the morning's
full-family fuzz reproduction). THE TARGET was v1def, 8 tasks (033, 049,
070, 103, 143, 209, 268, 295); 070 and 103 already counted. The prior
diagnosis for 033/049/143 (verified/unproved) named a single suspect,
"`_undef_obligation` does not walk while or if bodies" (this file's own
"LEFT, BY NAME" entry above) -- CONFIRMED for the "if" half by reading the
three twins' committed `.rs`: all three are COLLAPSE-IF twins, and
collapsing the `if (0<=x && x<len(s)) {...}` that used to guard `s[x]`
leaves the twin's new TOP-LEVEL statement an `if` whose own COND is
`s[x] >= 0`, undefined outside `[0, len(s))` -- never an assign/var
`_undef_obligation`'s old walk even looked at. `_undef_obligation` now
recurses into both `if` and `while`: an `if`'s cond is checked with
`defined()` before the concrete guard value (from the SAME `interp.ev`
replay the top-level walk already trusted) picks which branch to descend
into, and a `while`'s cond is checked the same way at the top of every
concrete iteration -- guard, body, guard, body, ... -- capped at
`interp.MAX_LOOP` like every other run in this codebase, so a body
statement several iterations in is checked against the CONCRETE state
that iteration actually reaches. This is the same gap
fz_v1nested_069's and fz_v1nested_150's own boundary-widening twins hit
(the undefined access one iteration inside the loop's own body,
this file's "LEFT, BY NAME" entry), so one walk fix closes both: measured
(`fuzz_lower.py --only verus --tasks ..., --n 400 --seed 1 --flake 3
--jobs 2/3`), all 8 v1def tasks and both named probes now read verus
verified/refuted, and the whole v1nested family (13 tasks, the 11 already
counting alongside these 2) is unaffected and all 13 count. A `return`
inside a loop is still not walked (`_GiveUp`, new): SPEC.md's early exit
is a separate residual, unexercised by any task this fix touches.

209/268/295 read malformed, not unproved -- a SEPARATE bug, measured with
its own quote before assuming the same cause: Verus's error is "Could not
automatically infer triggers for this quantifier", on the STATEMENT-level
`assert` `_assert_defined` emits for the `if`/`return` whose cond is a
`defined()`-rewritten forall, never on the `t_wf_..._ens0` copy of the
same obligation (`_prenex` already hoists THAT one's own binder into a
fresh lemma parameter, so it carries no forall at all -- checked directly,
all three tasks' wf lemmas compile clean before this fix). The body has
neither an indexable (`at`/`call`) nor a `div`/`mod` term for
`_has_indexable`/`_mod_div_trigger` to find, because `defined()`'s own
"at" case REPLACES the index expression with its bare bound check
(`0<=i && i<len(s)`), which is exactly the term automatic inference would
have grabbed. Measured before picking a fix (probe_trig1/2/3.rs, isolated
to 209's own obligation shape): `#![trigger i]` (the bound variable alone)
and `#![trigger (0 <= i)]` (a comparison) both get the identical "trigger
must be a function call, a field access, or arithmetic operator" refusal;
`#![trigger (i + 0)]` verifies with 0 errors. `expr()`'s forall/exists
case now falls back to `v + 0` (an AST node run through the same `expr()`
every other trigger term already goes through, so `_SUFFIX_INT` is
respected in both contexts) whenever neither existing trigger source
finds anything: always a legal arithmetic term, always mentions the bound
variable, and an additive identity that changes nothing the quantifier
proves. Measured: 209, 268 and 295 all go malformed -> verified (rows.json,
`['verified', 'refuted', True, ...]` on all three); every task with an
indexable or div/mod quantifier (every previously committed seq task,
is_prime) is untouched, since both existing branches fire before this new
`else` and neither reaches it.

REGRESSION, both fixes together: the full committed matrix (`grade.py
--tasks tasks/ --kernels verus --flake 3`, all 23 tasks in t/tasks/*.json)
reads verus verified/refuted on every task, matching t/AGREEMENT.md
exactly, neither better nor worse for any row. Both changes are additive
by construction -- the walk extension only fires where the old code
already gave up (None, "unproved"), so it can only turn an ABSTAIN into a
found obligation, never disturb a certificate the old top-level-only walk
already built; the trigger fallback only fires when Verus's own automatic
inference and this file's two existing explicit-trigger sources all find
nothing, which was previously a hard compile-time refusal on every task
that reached it, so there is no prior "unproved" or "refuted" verdict for
it to change into something worse.

LEFT, BY NAME (updated). `_undef_obligation` still does not walk a
`return`: any twin whose undefined access sits inside a loop or if body
that also returns before reaching it reads UNPROVED rather than REFUTED,
unexercised by anything measured today. `_undef_obligation`'s own
"Pairs" residual (a pair-typed LOCAL's type not tracked past entry) is
unchanged and unexercised by any task this note covers.

fstar AND framac, RE-MEASURED (same 10 tasks, `fuzz_lower.py --only
fstar,framac`), since the task description that named this residual
called the certificate "shared". Only fstar actually shares it
(`lower_fstar.py` imports and calls `lower_verus.certificate_formula`
directly, confirmed by reading its own import line): 033, 049, 070, 103,
143 and fz_v1nested_069 all move from real-verified/twin-UNPROVED to
real-verified/twin-REFUTED in fstar too, the identical improvement verus
got, from the identical fix, no fstar-side change needed. fz_v1nested_150
stays real-UNPROVED in fstar (a pre-existing fstar gap on this task's own
real body, unrelated to the twin certificate); 209/268/295 stay ABSTAIN
in fstar ("a quantifier in computational position has no decidable
lowering here", fstar's own REAL-side limitation on this shape, nothing
to do with `defined()`'s trigger-losing rewrite, which is a Verus-syntax
problem this fstar message is not). framac does NOT share this
certificate: `lower_framac.py` has its OWN separate `_undef_certificate`
(a parallel, independently-written function, not a call into this file,
confirmed by reading its own import list and by measurement) -- so
033/049/143's own framac cells are UNCHANGED, still real-verified/twin-
TIMEOUT exactly as before this fix, and 209/268/295/069/150 still ABSTAIN
on framac's own pre-existing, separate gaps (a quantifier in ACSL term
position; nested-seq RETURN; a non-variable seq position). Fixing
framac's own `_undef_certificate` the same way is out of this task's
scope (t/lower_verus.py and, only if the gap were there, t/harness.py;
it is in neither) and is named here as a residual for whoever next
touches lower_framac.py, not attempted.

2026-09-11, THE STRING LIBRARY (v1, SPEC.md "The string library (v1)").
All 17 members land as recursive `spec fn` definitions in `STRLIB_PRELUDE`
(module docstring above it carries the per-member encoding and the two
termination residuals `find`/`replace` needed, found and fixed on
0.2026.08.30.b432e82), emitted into a task's own module whenever
`_uses_strlib` finds any of the 17 op names -- costs nothing when unused
(measured, probe2.rs). No member is an abstain: every one type-checks and
is total by construction (interp.py's own algorithm shape, mirrored).

LEMMAS landed, each proved standalone before wiring in (probe3.rs,
probe4.rs, probe5.rs, all verified 0 errors): the split-join law
(`t_lemma_split_join_law`, with two helpers `t_lemma_split_c_nonempty`/
`t_lemma_join_cons`), `count`'s nonnegativity (`t_lemma_count_nonneg`),
and SPEC.md's own split-length law (`t_lemma_split_len_law`,
`len(s.split(c)) == s.count([c]) + 1`) -- the three lemmas this wave's
own brief named. Each is found by an AST-witness scan over a task's
`ensures` AND `body` (`_split_join_witnesses`, `_param_restricted_
witnesses`, with `_locals_map`/`_inline_vars` resolving a body-local
alias first, since the fuzz family states these laws through a local as
often as inline) and called as the FIRST statement of the task's own
proof fn -- restricted to arguments built from params alone
(`_only_params`) so the call is always legal at that position. A fourth,
generic bridge (`_full_slice_copy_var`) closes the "decoy full-length
slice" shape several fuzz members share (`t2 := s[0..len(s)]` standing in
for a copy of `s`): plain `Seq<int>` `==` is exactly as non-extensional
in Verus as `Seq<Seq<int>>`'s already was (the nested-seq wave's own
finding), so `t2 == s` needs the same `=~=` bridge `_assert_nested_eq`
already emits one type up.

MEASURED: (a) the three committed tasks, flake 3 -- `word_count` and
`split_join` VERIFIED/REFUTED, both twin witnesses matching SPEC.md's own
predicted ones exactly (`grade.py --tasks <the three> --kernels verus
--flake 3`); `count_vowels` is UNPROVED/refuted, a task-file defect this
lowering surfaces rather than routes around (below). (b) the family,
`fuzz_lower.py --only verus --n 400 --seed 1 --flake 3 --jobs 8` restricted
to the 17 saturated `fz_v1strlib_*` names (build_corpus's own indices for
these shapes shifted since `fuzz-strlib-names.txt` was written -- more
families were added upstream of `v1strlib` in the same RNG stream since;
this run's own `corpus.json` names are the current ones, re-derived by
calling `build_corpus` directly rather than trusting the stale file):
8 of 17 shapes VERIFIED/REFUTED, a ninth VERIFIED with a nonrefuting twin (`word_count`, `split_row_index`,
`count_one`, `count_two`, `join_split_roundtrip`, `split_row_len`,
`startswith_slice`, `endswith_slice`, and `tostr_len` VERIFIED/unproved --
the latter is SPEC's own documented `+nonrefuting` case, not a gap, see
`f_v1strlib`'s own docstring). (c) the committed matrix: every one of the
23 previously-committed tasks relowers BYTE-IDENTICAL to this change
(measured directly, `lower()` old vs new on all 23, 0 diffs) -- this
wave adds rows to AGREEMENT.md's table, it does not move any existing
cell, so no committed cell needed re-verification.

OPEN, by name, each a genuine proof gap rather than an abstain (the
members it needs are landed; only a further LEMMA is missing):
`case_map_lower`/`case_map_upper` (needs `s.isalpha() ==> r.isupper()`/
`islower()` as a consequence of the `lower`/`upper` map, not yet proved);
`find_case` (needs a "find returns the FIRST occurrence" positional
characterization lemma, distinct from `t_str_find`'s own definition);
`strip_len_lstrip`/`_rstrip`/`_strip` (needs `len(s.strip()) <= len(s)`);
`replace_count` (needs a count-after-replace relationship,
`s.replace([a],[b]).count([b]) == s.count([b]) + s.count([a])` under
`a != b`); `loop_count` and the COMMITTED `count_vowels` (needs a
"count of one appended code point" induction lemma,
`count(x ++ [y], [p]) == count(x, [p]) + (y == p ? 1 : 0)`, attempted
(probe4.rs) but not landed in the time this wave had -- the base case's
own definitional unfolding did not close under the asserts tried).
`count_vowels` carries a SECOND, separate defect independent of that
lemma: its own invariants are ordered value-then-range (`r == ...`
first, `0 <= i`/`i <= len(s)` after), backward from SPEC.md's own stated
rule ("Invariants are checked in order", line 141) -- confirmed directly
(a scratch copy with the range invariants moved first drops the
WF-ordering error entirely, leaving only the count-append gap above), so
this task is DEFECTIVE by SPEC.md's own definitional discipline as
currently committed, independent of anything this lowering could still
prove; reordering the committed task's own JSON is out of this file's
scope (t/lower_verus.py only).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                                   # noqa: E402
import interp                                    # noqa: E402
import names                                     # noqa: E402
from verifiers import verus as verus_backend     # noqa: E402

# DIVISION AND MODULO (2026-09-08, SPEC.md "Division and modulo (v1)").
# Measured on 0.2026.08.30.b432e82 with a six-fact probe on spec `int`
# (probe_div.rs): `assert(-7 / 2 == -4 && -7 % 2 == 1 && 7 / -2 == -3 &&
# 7 % -2 == 1 && -7 / -2 == 4 && -7 % -2 == 1)` verified with 0 errors, so
# Verus's native `/` and `%` on `int` ARE Euclidean, t's own convention:
# `div`/`mod` emit natively (BIN_OPS below), no kernel-terms redefinition
# needed. y == 0: a second probe (probe_div0.rs) shows `x / 0 == 0` and
# `x % 0 == 0` both FAIL to verify for symbolic x, so Verus's `/`/`%` are
# total in the type system (never a trap) but carry no known value at
# y == 0, the same "unspecified, not undefined-in-Rust's-sense" posture
# SMT-LIB gives division by zero. That is exactly what SPEC.md's
# definedness discipline needs: `defined()` below adds `y != 0` to a
# div/mod's obligation, the same shape as `at`'s bound, and every emission
# site asserts it before the value is used, so the y == 0 case is never
# actually reached by a proof this lowering emits; the operator's own
# totality is not relied on.
#
# The Euclidean defining law `x == (x div y) * y + (x mod y)` is native
# for the RANGE half (`0 <= x%y`, `x%y < y || x%y < -y`: probe_range.rs,
# 0 errors unaided) but NOT for the multiplicative half: Verus's default
# solver profile has nonlinear arithmetic off (see LOOPS in the module
# docstring), and `(x/y)*y` multiplies two non-literal terms, so
# probe_law.rs (`ensures x == (x/y)*y + (x%y)` alone) fails with
# "postcondition not satisfied". `_div_mod_law` below asserts that half
# explicitly via `by (nonlinear_arith) requires y != 0` (probe_law3.rs /
# probe_law4.rs, 0 errors; probe_law5.rs confirms the `requires` is a real
# obligation, not an assumption: drop the ambient `y != 0` and it reads
# "requires not satisfied"), emitted at every statement that introduces a
# div/mod term (`_assert_defined`), which is what makes `remainder`'s
# `ensures x == (x div y) * y + r` provable. `digit_sum` needed no such
# help: its recursive spec_fun never multiplies a div/mod result, so its
# loop-invariant preservation goes through on the native range facts and
# ordinary spec_fun unfolding alone.
BIN_OPS = {"==": "==", "!=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">=",
           "+": "+", "-": "-", "*": "*", "implies": "==>",
           "div": "/", "mod": "%"}
NARY_OPS = {"and": "&&", "or": "||"}
TYPES = {"int": "int", "bool": "bool", "seq": "Seq<int>"}

# THE STRING LIBRARY (v1), 2026-09-11 (SPEC.md "The string library (v1)").
# Every member is total (SPEC.md's own word), so `defined()` needed no new
# case for any of the 17 ops below: the existing catch-all ("total
# operators: not neg len + - * == != < <= > >=, and pair, fst, snd")
# already computes exactly the right formula -- AND of the arguments'
# definedness, nothing more -- for a total op with no case of its own,
# string ops included, measured the same way `fst`/`snd` were found to
# need no case. Each member lowers to a `spec fn` named `t_str_<member>`
# (or `t_str_<member>_ws`/`_c` for split's two arities, per SPEC.md "two
# arities of one op") in `STRLIB_PRELUDE` below, a fixed block of Verus
# source emitted once into a task's own module (prepended to its
# `spec_blocks`) whenever `_uses_strlib` finds any of these 17 op names
# anywhere in the task (params/requires/ensures/spec_funs/body) -- unused
# members cost nothing (an unreferenced `spec fn` is neither an
# obligation nor a proof, measured probe2.rs: 17 defined, 1 called,
# verified counts only the reachable one). Every member is a *recursive
# or structural* function over `Seq<int>` (`Seq<Seq<int>>` for split's
# result and join's argument), each one built to mirror interp.py's own
# reference algorithm shape-for-shape (front-to-back prefix recursion for
# `count`/`find`/`replace`/`split(s,c)`, a two-sided trim for
# `strip`, elementwise `cons` for `lower`/`upper`, an `any`/`all`-style OR/
# AND recursion for the four predicates) rather than reproved from a
# different algorithm, so the termination metric (`decreases s.len()`,
# or `decreases n` for `tostr`'s digit peeling) is the same one that made
# interp.py's own loops terminate. `split(s)` (whitespace) carries an
# explicit accumulator parameter (`t_str_split_ws_acc`, `cur`, the "word
# being built") since a *pure* recursive function has no mutable local to
# fold into -- exactly interp.py's own `_str_split_ws`'s `cur`, turned
# into a second formal parameter instead of a rebound local.
#
# TWO TERMINATION RESIDUALS, measured on 0.2026.08.30.b432e82
# (probe2.rs): `t_str_find` and `t_str_replace`'s own recursive helpers
# (`_from`/`_ne`) each need an explicit `if t.len() == 0` FIRST case
# inside the recursive definition itself, even though every CALLER already
# routes the empty-pattern case elsewhere (`t_str_find` docstring below,
# `t_str_replace`'s own dispatch) -- a `spec fn` is checked for
# termination against its FULL domain, not against how its callers happen
# to use it, and without that branch Verus's automatic decreases checker
# could not derive `s.len() >= 1` in the recursive `else` arm (the
# `subrange(1, ...)`'s own `recommends` came back "not met", `could not
# prove termination`, on `t.len()` alone with no branch pinning it
# nonzero) -- `t_str_count`, built with that branch already first
# (SPEC.md's own `count(s, []) == len(s)+1` clause put it there for a
# semantic reason, not a termination one), never hit this. Once each
# helper carried its own explicit `t.len() == 0` arm, both verified
# (probe2.rs: 18/18, 0 errors) with no other change.
#
# LEMMAS: two of the three committed tasks' ensures need a proof beyond
# the definitions' own unfolding. `word_count`'s (`r == len(t2.split())`,
# `t2 := s[0..len(s)]`) needed none: `s.subrange(0, s.len())` and `s` are
# proved equal by the SAME `==`/`=~=` extensionality bridge the nested-seq
# wave already emits at every statement (`_assert_nested_eq`, generalized
# below to ANY seq-typed `==`, not only `Seq<Seq<int>>` -- see
# `_assert_seq_eq`'s own docstring), so `split(t2) == split(s)` follows
# from `t2 == s` by ordinary congruence, no lemma needed.
#
# `split_join`'s law, `[c].join(s.split(c)) == s`, is NOT free: it is an
# induction over `s.len()`, proved once as `t_lemma_split_join_law` (with
# two small helper lemmas, `t_lemma_split_c_nonempty` -- `split(s,c)`
# always yields at least one row -- and `t_lemma_join_cons` -- joining a
# brand-new row onto the FRONT of a nonempty rows sequence peels off
# exactly that row plus one separator, the shape `split(s,c)`'s own
# `s[0]==c` case produces) all three proved and measured standalone
# (probe3.rs: 7/7, 0 errors) before landing here. `_split_join_witnesses`
# below finds this law's own AST shape in a task's ensures (`join(split(S,
# C), seq![C]) == S`, either operand order, S/C read off the AST rather
# than assumed to be named `s`/`c` so the SAME detector fires on
# `split_join.json` and the fuzz family's `join_split_roundtrip` shape
# alike) and `emit()` calls the lemma once per distinct (S, C) pair found,
# as the first statement of the task's own proof fn body, so its `ensures`
# becomes an established fact for everything after.
#
# `count_vowels`'s own loop invariant (`r == count(s[0..i],[97]) + ... +
# count(s[0..i],[117])`) is the one member NOT closed by a general lemma
# here: it needs a fact relating `count(x ++ [y], [p])` to `count(x, [p])`
# (append one code point, single-character pattern) at every step of the
# loop, which requires reaching INTO the while-loop lowering's own
# recursive-helper body (the point right before its self-call) rather
# than the task's top-level proof fn `emit()` controls -- named here as
# the wave's own open residual (this docstring's dated note carries the
# measurement); the member `count` itself is landed and lowers/verifies
# standalone (probe2.rs), only the LOOP LEMMA for this one task's proof is
# open.
STRLIB_OPS = {"split", "join", "tostr", "count", "find", "strip", "lstrip",
              "rstrip", "replace", "lower", "upper", "isdigit", "isalpha",
              "isupper", "islower", "startswith", "endswith"}

ROTATE_PRELUDE = """\
proof fn t_lemma_rotate_left(l: Seq<int>, n: int)
    requires
        0 <= n,
        n < l.len(),
    ensures
        forall|i: int| #![trigger (l[(i + n) % (l.len() as int)])]
            0 <= i && i < (l.len() as int) ==>
            ((l.subrange(n, l.len() as int) + l.subrange(0, n))[i]
             == l[(i + n) % (l.len() as int)]),
{
    let r = l.subrange(n, l.len() as int) + l.subrange(0, n);
    assert forall|i: int| #![trigger (l[(i + n) % (l.len() as int)])]
        0 <= i && i < (l.len() as int) implies
        (r[i] == l[(i + n) % (l.len() as int)]) by {
        if i < (l.len() as int) - n {
            assert(r[i] == l[n + i]);
            assert((i + n) % (l.len() as int) == i + n) by (nonlinear_arith)
                requires
                    0 <= i,
                    i < (l.len() as int) - n,
                    n >= 0,
                    n < (l.len() as int),
            ;
        } else {
            assert(r[i] == l[i - ((l.len() as int) - n)]);
            assert((i + n) % (l.len() as int) == i - ((l.len() as int) - n))
                by (nonlinear_arith)
                requires
                    0 <= i,
                    i < (l.len() as int),
                    i >= (l.len() as int) - n,
                    n >= 0,
                    n < (l.len() as int),
            ;
        }
    };
}
"""

STRLIB_PRELUDE = """\
spec fn t_ws(c: int) -> bool {
    (9 <= c && c <= 13) || (28 <= c && c <= 32)
}
spec fn t_is_upper(c: int) -> bool { 65 <= c && c <= 90 }
spec fn t_is_lower(c: int) -> bool { 97 <= c && c <= 122 }

spec fn t_str_split_ws_acc(s: Seq<int>, cur: Seq<int>) -> Seq<Seq<int>>
    decreases s.len(),
{
    if s.len() == 0 {
        if cur.len() == 0 { Seq::<Seq<int>>::empty() } else { seq![cur] }
    } else if t_ws(s[0]) {
        if cur.len() == 0 {
            t_str_split_ws_acc(s.subrange(1, s.len() as int), Seq::<int>::empty())
        } else {
            seq![cur] + t_str_split_ws_acc(s.subrange(1, s.len() as int), Seq::<int>::empty())
        }
    } else {
        t_str_split_ws_acc(s.subrange(1, s.len() as int), cur + seq![s[0]])
    }
}
spec fn t_str_split_ws(s: Seq<int>) -> Seq<Seq<int>> { t_str_split_ws_acc(s, Seq::<int>::empty()) }

spec fn t_str_split_c(s: Seq<int>, c: int) -> Seq<Seq<int>>
    decreases s.len(),
{
    if s.len() == 0 { seq![Seq::<int>::empty()] }
    else if s[0] == c {
        seq![Seq::<int>::empty()] + t_str_split_c(s.subrange(1, s.len() as int), c)
    } else {
        let rest = t_str_split_c(s.subrange(1, s.len() as int), c);
        seq![seq![s[0]] + rest[0]] + rest.subrange(1, rest.len() as int)
    }
}

spec fn t_str_join(rows: Seq<Seq<int>>, sep: Seq<int>) -> Seq<int>
    decreases rows.len(),
{
    if rows.len() == 0 { Seq::<int>::empty() }
    else if rows.len() == 1 { rows[0] }
    else { rows[0] + sep + t_str_join(rows.subrange(1, rows.len() as int), sep) }
}

spec fn t_str_udigits(n: int) -> Seq<int>
    decreases n,
{
    if n <= 9 { seq![n + 48] }
    else { t_str_udigits(n / 10) + seq![n % 10 + 48] }
}
spec fn t_str_tostr(n: int) -> Seq<int> {
    if n < 0 { seq![45] + t_str_udigits(-n) } else { t_str_udigits(n) }
}

spec fn t_str_count(s: Seq<int>, t: Seq<int>) -> int
    decreases s.len(),
{
    if t.len() == 0 { s.len() as int + 1 }
    else if s.len() < t.len() { 0 }
    else if s.subrange(0, t.len() as int) == t {
        1 + t_str_count(s.subrange(t.len() as int, s.len() as int), t)
    } else {
        t_str_count(s.subrange(1, s.len() as int), t)
    }
}

spec fn t_str_find_from(s: Seq<int>, t: Seq<int>, base: int) -> int
    decreases s.len(),
{
    if t.len() == 0 { base }
    else if s.len() < t.len() { -1 }
    else if s.subrange(0, t.len() as int) == t { base }
    else { t_str_find_from(s.subrange(1, s.len() as int), t, base + 1) }
}
spec fn t_str_find(s: Seq<int>, t: Seq<int>) -> int { t_str_find_from(s, t, 0) }

spec fn t_str_lstrip(s: Seq<int>) -> Seq<int>
    decreases s.len(),
{
    if s.len() == 0 { s }
    else if t_ws(s[0]) { t_str_lstrip(s.subrange(1, s.len() as int)) }
    else { s }
}
spec fn t_str_rstrip(s: Seq<int>) -> Seq<int>
    decreases s.len(),
{
    if s.len() == 0 { s }
    else if t_ws(s[s.len() as int - 1]) { t_str_rstrip(s.subrange(0, s.len() as int - 1)) }
    else { s }
}
spec fn t_str_strip(s: Seq<int>) -> Seq<int> { t_str_rstrip(t_str_lstrip(s)) }

spec fn t_str_replace_ins(s: Seq<int>, u: Seq<int>) -> Seq<int>
    decreases s.len(),
{
    if s.len() == 0 { u }
    else { u + seq![s[0]] + t_str_replace_ins(s.subrange(1, s.len() as int), u) }
}
spec fn t_str_replace_ne(s: Seq<int>, t: Seq<int>, u: Seq<int>) -> Seq<int>
    decreases s.len(),
{
    if t.len() == 0 { s }
    else if s.len() < t.len() { s }
    else if s.subrange(0, t.len() as int) == t {
        u + t_str_replace_ne(s.subrange(t.len() as int, s.len() as int), t, u)
    } else {
        seq![s[0]] + t_str_replace_ne(s.subrange(1, s.len() as int), t, u)
    }
}
spec fn t_str_replace(s: Seq<int>, t: Seq<int>, u: Seq<int>) -> Seq<int> {
    if t.len() == 0 { t_str_replace_ins(s, u) } else { t_str_replace_ne(s, t, u) }
}

spec fn t_str_lower(s: Seq<int>) -> Seq<int>
    decreases s.len(),
{
    if s.len() == 0 { s }
    else { seq![if t_is_upper(s[0]) { s[0] + 32 } else { s[0] }] + t_str_lower(s.subrange(1, s.len() as int)) }
}
spec fn t_str_upper(s: Seq<int>) -> Seq<int>
    decreases s.len(),
{
    if s.len() == 0 { s }
    else { seq![if t_is_lower(s[0]) { s[0] - 32 } else { s[0] }] + t_str_upper(s.subrange(1, s.len() as int)) }
}

spec fn t_all_digit(s: Seq<int>) -> bool
    decreases s.len(),
{
    if s.len() == 0 { true }
    else { 48 <= s[0] && s[0] <= 57 && t_all_digit(s.subrange(1, s.len() as int)) }
}
spec fn t_str_isdigit(s: Seq<int>) -> bool { s.len() > 0 && t_all_digit(s) }

spec fn t_all_alpha(s: Seq<int>) -> bool
    decreases s.len(),
{
    if s.len() == 0 { true }
    else { (t_is_upper(s[0]) || t_is_lower(s[0])) && t_all_alpha(s.subrange(1, s.len() as int)) }
}
spec fn t_str_isalpha(s: Seq<int>) -> bool { s.len() > 0 && t_all_alpha(s) }

spec fn t_any_letter(s: Seq<int>) -> bool
    decreases s.len(),
{
    if s.len() == 0 { false }
    else { t_is_upper(s[0]) || t_is_lower(s[0]) || t_any_letter(s.subrange(1, s.len() as int)) }
}
spec fn t_any_lower(s: Seq<int>) -> bool
    decreases s.len(),
{
    if s.len() == 0 { false }
    else { t_is_lower(s[0]) || t_any_lower(s.subrange(1, s.len() as int)) }
}
spec fn t_any_upper(s: Seq<int>) -> bool
    decreases s.len(),
{
    if s.len() == 0 { false }
    else { t_is_upper(s[0]) || t_any_upper(s.subrange(1, s.len() as int)) }
}
spec fn t_str_isupper(s: Seq<int>) -> bool { t_any_letter(s) && !t_any_lower(s) }
spec fn t_str_islower(s: Seq<int>) -> bool { t_any_letter(s) && !t_any_upper(s) }

spec fn t_str_startswith(s: Seq<int>, t: Seq<int>) -> bool {
    t.len() <= s.len() && s.subrange(0, t.len() as int) == t
}
spec fn t_str_endswith(s: Seq<int>, t: Seq<int>) -> bool {
    t.len() <= s.len() && (t.len() == 0 || s.subrange(s.len() as int - t.len() as int, s.len() as int) == t)
}

proof fn t_lemma_split_c_nonempty(s: Seq<int>, c: int)
    ensures t_str_split_c(s, c).len() >= 1,
    decreases s.len(),
{
    if s.len() == 0 {
    } else if s[0] == c {
        t_lemma_split_c_nonempty(s.subrange(1, s.len() as int), c);
    } else {
        t_lemma_split_c_nonempty(s.subrange(1, s.len() as int), c);
    }
}

proof fn t_lemma_join_cons(x: Seq<int>, rows: Seq<Seq<int>>, sep: Seq<int>)
    requires rows.len() >= 1,
    ensures t_str_join(seq![x] + rows, sep) == x + sep + t_str_join(rows, sep),
{
    let rows2 = seq![x] + rows;
    assert(rows2.len() == rows.len() + 1);
    assert(rows2[0] == x);
    assert(rows2.subrange(1, rows2.len() as int) =~= rows);
    assert(t_str_join(rows2, sep) == rows2[0] + sep + t_str_join(rows2.subrange(1, rows2.len() as int), sep));
}

proof fn t_lemma_join_prepend(x: Seq<int>, rows: Seq<Seq<int>>, sep: Seq<int>)
    requires rows.len() >= 1,
    ensures
        t_str_join(seq![x + rows[0]] + rows.subrange(1, rows.len() as int), sep)
            == x + t_str_join(rows, sep),
{
    let rows2 = seq![x + rows[0]] + rows.subrange(1, rows.len() as int);
    assert(rows2.len() == rows.len());
    if rows.len() == 1 {
        assert(rows2 =~= seq![x + rows[0]]);
        assert(t_str_join(rows2, sep) == x + rows[0]);
        assert(t_str_join(rows, sep) == rows[0]);
    } else {
        assert(rows2[0] == x + rows[0]);
        assert(rows2.subrange(1, rows2.len() as int) =~= rows.subrange(1, rows.len() as int));
        assert(t_str_join(rows2, sep) == rows2[0] + sep + t_str_join(rows2.subrange(1, rows2.len() as int), sep));
        assert(t_str_join(rows, sep) == rows[0] + sep + t_str_join(rows.subrange(1, rows.len() as int), sep));
    }
}

proof fn t_lemma_split_join_law(s: Seq<int>, c: int)
    ensures t_str_join(t_str_split_c(s, c), seq![c]) == s,
    decreases s.len(),
{
    if s.len() == 0 {
        assert(t_str_split_c(s, c) =~= seq![Seq::<int>::empty()]);
        assert(t_str_join(t_str_split_c(s, c), seq![c]) == Seq::<int>::empty());
        assert(s =~= Seq::<int>::empty());
    } else if s[0] == c {
        let rest = s.subrange(1, s.len() as int);
        t_lemma_split_join_law(rest, c);
        t_lemma_split_c_nonempty(rest, c);
        let rest_rows = t_str_split_c(rest, c);
        assert(t_str_split_c(s, c) =~= seq![Seq::<int>::empty()] + rest_rows);
        t_lemma_join_cons(Seq::<int>::empty(), rest_rows, seq![c]);
        assert(t_str_join(seq![Seq::<int>::empty()] + rest_rows, seq![c])
               == Seq::<int>::empty() + seq![c] + t_str_join(rest_rows, seq![c]));
        assert(t_str_join(rest_rows, seq![c]) == rest);
        assert(s =~= seq![c] + rest);
    } else {
        let rest = s.subrange(1, s.len() as int);
        t_lemma_split_join_law(rest, c);
        t_lemma_split_c_nonempty(rest, c);
        let rest_rows = t_str_split_c(rest, c);
        assert(t_str_split_c(s, c) =~= seq![seq![s[0]] + rest_rows[0]] + rest_rows.subrange(1, rest_rows.len() as int));
        t_lemma_join_prepend(seq![s[0]], rest_rows, seq![c]);
        assert(t_str_join(t_str_split_c(s, c), seq![c]) == seq![s[0]] + t_str_join(rest_rows, seq![c]));
        assert(t_str_join(rest_rows, seq![c]) == rest);
        assert(s =~= seq![s[0]] + rest);
    }
}

proof fn t_lemma_count_nonneg(s: Seq<int>, t: Seq<int>)
    ensures t_str_count(s, t) >= 0,
    decreases s.len(),
{
    if t.len() == 0 {
    } else if s.len() < t.len() {
    } else if s.subrange(0, t.len() as int) == t {
        t_lemma_count_nonneg(s.subrange(t.len() as int, s.len() as int), t);
    } else {
        t_lemma_count_nonneg(s.subrange(1, s.len() as int), t);
    }
}

proof fn t_lemma_split_len_law(s: Seq<int>, c: int)
    ensures t_str_split_c(s, c).len() == t_str_count(s, seq![c]) + 1,
    decreases s.len(),
{
    let t = seq![c];
    if s.len() == 0 {
        assert(t_str_split_c(s, c) =~= seq![Seq::<int>::empty()]);
        assert(t_str_count(s, t) == 0);
    } else if s[0] == c {
        let rest = s.subrange(1, s.len() as int);
        t_lemma_split_len_law(rest, c);
        t_lemma_split_c_nonempty(rest, c);
        assert(t_str_split_c(s, c) =~= seq![Seq::<int>::empty()] + t_str_split_c(rest, c));
        assert(t_str_split_c(s, c).len() == 1 + t_str_split_c(rest, c).len());
        assert(s.subrange(0, t.len() as int) =~= t);
        assert(t_str_count(s, t) == 1 + t_str_count(rest, t));
    } else {
        let rest = s.subrange(1, s.len() as int);
        t_lemma_split_len_law(rest, c);
        t_lemma_split_c_nonempty(rest, c);
        let rest_rows = t_str_split_c(rest, c);
        assert(t_str_split_c(s, c) =~= seq![seq![s[0]] + rest_rows[0]] + rest_rows.subrange(1, rest_rows.len() as int));
        assert(t_str_split_c(s, c).len() == rest_rows.len());
        assert(s.subrange(0, t.len() as int)[0] == s[0]);
        assert(t[0] == c);
        assert(t_str_count(s, t) == t_str_count(rest, t));
    }
}
"""


def _full_slice_copy_var(init: dict) -> str | None:
    """True (returning the base var's name) iff `init` is the "full-length
    slice standing in for a copy" shape SPEC.md's own `word_count` note
    names (`t2 := s[0..len(s)]`) -- `f_v1strlib`'s own docstring shows the
    SAME shape recurring across most of the family (word_count, split_row,
    count_pattern, strip_len, case_map), always a decoy local equal to a
    param by construction. Plain `==` between two `Seq<int>` values is not
    extensional in Verus any more than `Seq<Seq<int>>`'s already was (the
    nested-seq wave's own finding, `_assert_nested_eq`'s docstring): a
    string-lib call on `t2` needs `t2 == s` established via `=~=` before a
    downstream `split(t2) == split(s)` fact follows by congruence, exactly
    the bridge this function's caller (`stmts`'s "var" case) emits."""
    if init.get("op") != "slice":
        return None
    s, a, b = init["args"]
    if "var" not in s or a != {"int": 0}:
        return None
    if b.get("op") != "len" or b.get("args") != [s]:
        return None
    return s["var"]


def _locals_map(task: dict) -> dict:
    """name -> init Expr for every body-local `var` declaration in the
    task (through `if`/`while` nesting), one shallow pass -- what
    `_inline_vars` below substitutes so a lemma-witness search sees
    `join(split(s, c), ...)` even when the task's own body names the
    `split(s, c)` result through a local (`f_v1strlib`'s own
    `join_split_roundtrip`/`split_row` shapes: `rows := s.split(c)` then
    `r := [c].join(rows)`, never spelled inline)."""
    m: dict = {}

    def walk(body: list) -> None:
        for s in body:
            if "var" in s:
                v = s["var"]
                m[v["name"]] = v["init"]
            elif "if" in s:
                walk(s["if"]["then"])
                walk(s["if"].get("else", []))
            elif "while" in s:
                walk(s["while"]["body"])

    walk(task.get("body", []))
    return m


def _inline_vars(node, m: dict, depth: int = 3):
    """Returns a COPY of `node` with every leaf `{"var": NAME}` Expr (NAME
    a key of `m`) replaced by `m[NAME]`, up to `depth` substitutions deep
    (a body-local never refers to itself, so this always terminates; depth
    only bounds how many LEVELS of local-aliases-a-local this unwinds,
    generously past anything the fuzz family or the three committed tasks
    nest). A statement-position `{"var": {...}}` (a `var` DECLARATION, not
    a read) is untouched: its value is a dict, never a str, so the
    `isinstance` guard below only ever fires on the Expr form."""
    if depth <= 0:
        return node
    if isinstance(node, dict):
        v = node.get("var")
        if isinstance(v, str) and set(node.keys()) == {"var"} and v in m:
            return _inline_vars(m[v], m, depth - 1)
        return {k: _inline_vars(x, m, depth) for k, x in node.items()}
    if isinstance(node, list):
        return [_inline_vars(x, m, depth) for x in node]
    return node


def _op_terms(node, opname: str, arity: int, out: list) -> None:
    """Collects, into `out`, every `(args...)` of every node `{"op":
    opname, "args": [...]}` (with exactly `arity` args) found anywhere in
    `node` -- the same generic walk `_join_split_terms` already uses,
    parameterized on which op. Used for `count`/`split` witness-finding
    below: a task's own ensures/body is the only source of truth for
    which lemma instantiations a proof might need, so this reads the AST
    rather than guessing from the op name alone."""
    if isinstance(node, dict):
        if node.get("op") == opname and len(node.get("args", [])) == arity:
            out.append(tuple(node["args"]))
        for v in node.values():
            _op_terms(v, opname, arity, out)
    elif isinstance(node, list):
        for v in node:
            _op_terms(v, opname, arity, out)


def _param_restricted_witnesses(task: dict, opname: str, arity: int
                                 ) -> list[tuple[dict, ...]]:
    """`_op_terms` over the task's own `ensures` (the only place a lemma
    fact needs to be AVAILABLE, since that is what the proof fn's own
    postcondition must discharge), restricted to instantiations built
    from params alone (`_only_params`, same reasoning as
    `_split_join_witnesses`'s own docstring) so the lemma call `emit()`
    prepends is a legal first statement, deduplicated in ensures order."""
    pnames = {p["name"] for p in task.get("params", [])}
    lmap = _locals_map(task)
    inlined_ensures = _inline_vars(task.get("ensures", []), lmap)
    inlined_body = _inline_vars(task.get("body", []), lmap)
    found: list = []
    _op_terms(inlined_ensures, opname, arity, found)
    _op_terms(inlined_body, opname, arity, found)
    out: list[tuple[dict, ...]] = []
    seen: set = set()
    for args in found:
        if not all(_only_params(a, pnames) for a in args):
            continue
        key = tuple(repr(a) for a in args)
        if key in seen:
            continue
        seen.add(key)
        out.append(args)
    return out


def _uses_strlib(node) -> bool:
    """True iff `node` (a task dict, or any Expr/stmt/body sub-structure)
    mentions one of the 17 string-library op names anywhere -- params,
    requires, ensures, spec_funs, or body alike, found by one generic walk
    rather than per-field cases (the same shape `_body_calls` already
    uses for a single name). Costs nothing on the 23 previously committed
    non-string tasks (measured: none of their op names collide with
    `STRLIB_OPS`, so this returns False on all of them, unchanged
    output -- the byte-identity regression check in this file's own
    docstring)."""
    if isinstance(node, dict):
        if node.get("op") in STRLIB_OPS:
            return True
        return any(_uses_strlib(v) for v in node.values())
    if isinstance(node, list):
        return any(_uses_strlib(v) for v in node)
    return False


def _is_ground(e) -> bool:
    """True iff `e` (an Expr, or any nested part of one) contains no `var`
    reference anywhere -- a closed term over literals and operators alone.
    Used to gate `_strlib_ground_bridge` below: substituting a task's
    return name with its own closed-form value (`_sym`'s result over an
    env with no params bound) turns a probe's `ensures` into a term
    `compute_only` can actually decide, but only when every leaf is a
    literal, never when a param or loop-local escaped the substitution
    (a task with params, or a body `_sym` could not close, never reaches
    this predicate as True, so the bridge never fires there)."""
    if isinstance(e, dict):
        if "var" in e:
            return False
        return all(_is_ground(v) for v in e.values())
    if isinstance(e, list):
        return all(_is_ground(v) for v in e)
    return True


def _ro_defining_facts(ro: list[str], local_inits: dict[str, dict]
                        ) -> list[dict]:
    """2026-09-11 (ROADMAP 16.2, see `loop()`'s own note at the call
    site). For every name in `ro` (a loop helper's read-only parameters)
    that is a body-local `var` rather than a task param, and whose OWN
    initializer mentions only other names also in `ro` (so it is truly a
    fact about read-only state, never a stale reference to something the
    loop itself reassigns), returns the Expr `name == init`. `ro` always
    contains a local's initializer's own dependencies before the local
    itself in `scope`'s iteration order (a `var` cannot reference a name
    not yet declared), so this needs no fixpoint/ordering care -- one
    pass over `ro` suffices."""
    facts = []
    ro_set = set(ro)
    for n in ro:
        init = local_inits.get(n)
        if init is not None and _only_params(init, ro_set):
            facts.append({"op": "==", "args": [{"var": n}, init]})
    return facts


def _only_params(e: dict, pnames: set) -> bool:
    """True iff every leaf of e is a `var` naming one of the task's own
    params -- the condition under which a subexpression can be hoisted,
    unchanged, to the very first statement of the task's own proof fn
    body (before any body-local exists to make it mean something
    different)."""
    if "var" in e:
        return e["var"] in pnames
    if "int" in e or "bool" in e:
        return True
    if "op" in e:
        return all(_only_params(a, pnames) for a in e.get("args", []))
    return False


def _join_split_terms(node, out: list) -> None:
    """Collects, into `out`, every `join(split(S, C), seq![C2])` (C2 == C)
    subexpression found anywhere in `node` -- both `ensures` (the law
    stated directly, `split_join.json`'s own shape) and the `body` (a
    local computed by the SAME law and returned under a bare `r == s`
    ensures, the fuzz family's `join_split_roundtrip` shape, `f_v1strlib`'s
    own docstring) -- one generic walk rather than two separate cases,
    the same technique `_uses_strlib` already uses."""
    if isinstance(node, dict):
        if node.get("op") == "join":
            jrows, jsep = node.get("args", [None, None])
            if (isinstance(jrows, dict) and jrows.get("op") == "split"
                    and len(jrows.get("args", [])) == 2):
                s_e, c_e = jrows["args"]
                if (isinstance(jsep, dict) and jsep.get("op") == "seq"
                        and jsep.get("args") == [c_e]):
                    out.append((s_e, c_e))
        for v in node.values():
            _join_split_terms(v, out)
    elif isinstance(node, list):
        for v in node:
            _join_split_terms(v, out)


def _split_join_witnesses(task: dict) -> list[tuple[dict, dict]]:
    """SPEC.md "The string library (v1)" split-join law, `[c].join(s.split(
    c)) == s`: every DISTINCT `(S, C)` pair `_join_split_terms` finds
    anywhere in the task (`ensures` or `body` alike), restricted to pairs
    where both S and C are built from the task's own params only
    (`_only_params`) -- so the lemma call `emit()` prepends is always a
    legal FIRST statement, evaluated before any body-local shadows a
    name it mentions. Both committed shapes need no lemma they do not
    get: `split_join.json` states the law directly in `ensures`;
    `join_split_roundtrip` states only `r == s` in `ensures` and computes
    the law's own LHS in a body-local -- this function finds the SAME
    (s, c) pair either way, from the AST shape alone, not from where in
    the task it appears."""
    pnames = {p["name"] for p in task.get("params", [])}
    lmap = _locals_map(task)
    found: list = []
    _join_split_terms(_inline_vars(task.get("ensures", []), lmap), found)
    _join_split_terms(_inline_vars(task.get("body", []), lmap), found)
    out: list[tuple[dict, dict]] = []
    seen: set = set()
    for s_e, c_e in found:
        if not (_only_params(s_e, pnames) and _only_params(c_e, pnames)):
            continue
        key = (repr(s_e), repr(c_e))
        if key in seen:
            continue
        seen.add(key)
        out.append((s_e, c_e))
    return out


def _rotate_terms(node, rname: str, out: list) -> None:
    """ROTATE-LEFT INDEXING LAW (2026-09-11, ROADMAP 16.2, splitAndAppend).
    Collects every `(L, N)` pair for which `node` states, anywhere, the
    shape `forall|i| 0 <= i < len(L) ==> RNAME[i] == L[(i + N) % len(L)]`
    -- the standard "rotate a sequence left by N" indexing law, true of
    ANY seq L and int N with `0 <= N < len(L)` regardless of how RNAME
    was built (`l.subrange(n, l.len()) + l.subrange(0, n)` is the one
    concrete shape measured, splitAndAppend's own body, but the law
    itself only mentions L, N and the bound variable, so nothing here
    inspects the body at all -- same separation of concerns
    `_join_split_terms` already keeps between finding the LAW and finding
    what makes it hold). Both occurrences of `L` (the forall's own `hi`
    and the index expression's own divisor) and both occurrences of `L`'s
    `.len()` must be the SAME subexpression (`repr`-equal): a forall
    whose hi and mod-divisor disagree is not this law and is left alone
    (never raises, just contributes nothing, same policy `_join_split_
    terms` follows for a lookalike op it does not recognize)."""
    if isinstance(node, dict):
        q = node.get("forall")
        if isinstance(q, dict):
            body = q.get("body", {})
            if (body.get("op") == "==" and len(body.get("args", [])) == 2):
                lhs, rhs = body["args"]
                if (lhs.get("op") == "at" and lhs.get("args", [None])[0]
                        == {"var": rname}
                        and rhs.get("op") == "at"
                        and len(rhs.get("args", [])) == 2):
                    l_e, idx = rhs["args"]
                    hi = q.get("hi", {})
                    if (q.get("lo") == {"int": 0}
                            and hi.get("op") == "len"
                            and hi.get("args") == [l_e]
                            and idx.get("op") == "mod"
                            and len(idx.get("args", [])) == 2):
                        sum_e, div_e = idx["args"]
                        if (div_e.get("op") == "len"
                                and div_e.get("args") == [l_e]
                                and sum_e.get("op") == "+"
                                and len(sum_e.get("args", [])) == 2
                                and sum_e["args"][0] == {"var": q.get("var")}):
                            out.append((l_e, sum_e["args"][1]))
        for v in node.values():
            _rotate_terms(v, rname, out)
    elif isinstance(node, list):
        for v in node:
            _rotate_terms(v, rname, out)


def _rotate_witnesses(task: dict) -> list[tuple[dict, dict]]:
    """`_rotate_terms` over the task's own `ensures`, restricted to (L, N)
    built from params alone, same reasoning and same dedup discipline as
    `_split_join_witnesses` (whose docstring this mirrors)."""
    pnames = {p["name"] for p in task.get("params", [])}
    rname = task["returns"][0]["name"]
    found: list = []
    _rotate_terms(task.get("ensures", []), rname, found)
    out: list[tuple[dict, dict]] = []
    seen: set = set()
    for l_e, n_e in found:
        if not (_only_params(l_e, pnames) and _only_params(n_e, pnames)):
            continue
        key = (repr(l_e), repr(n_e))
        if key in seen:
            continue
        seen.add(key)
        out.append((l_e, n_e))
    return out


def _vty(ty) -> str:
    """The Verus type for a t type: TYPES[ty] for a base type name, or
    (SPEC.md "Pairs", 2026-09-10) the Rust tuple `(V1, V2)` for
    {"pair": [T1, T2]} -- Verus tuples are ordinary Rust tuples in both
    exec and spec/proof code (measured, probe_pair_basic.rs: a proof fn
    taking and returning `(int, int)`, `.0`/`.1` projections in its own
    `ensures`, 0 errors), so a pair type declares NO new Verus type the
    way SPARK needs a per-pair-type record or Lean needs `Int x Int`. T1
    and T2 are always base types (SPEC.md: no pair of pairs), so this
    recurses at most one level; or (SPEC.md "Nested sequences",
    2026-09-10) `Seq<Seq<int>>` for {"seq": "seq"} -- Verus's Seq is
    generic over its element type in both exec and spec/proof code, so a
    nested-seq type likewise declares nothing new, just one more `Seq<>`
    wrapped around the elementary one (measured, probe_nested_ops.rs: a
    proof fn over Seq<Seq<int>> params/locals, 0 errors). Two dict shapes
    reach here now, so the key decides which recursion applies rather
    than assuming "pair" the way this function used to (an unguarded
    `ty["pair"]` on {"seq": "seq"} raised a bare KeyError, measured
    2026-09-10 on the first swap_rows attempt, before this fix)."""
    if isinstance(ty, dict):
        if "seq" in ty:
            return f"Seq<{_vty(ty['seq'])}>"
        t1, t2 = ty["pair"]
        return f"({_vty(t1)}, {_vty(t2)})"
    return TYPES[ty]


_SUFFIX_INT = False   # v1 only: literals as `(7int)` so ite branches infer
                      # (measured: bare `1` in an ite arm is E0283); v0
                      # output stays byte-identical with bare literals.


def _has_indexable(e: dict) -> bool:
    """True iff e contains a Seq index (`at`) or a `call` anywhere -- the
    shapes Verus's automatic trigger inference picks up on its own for a
    quantifier body. Used only to decide whether a forall/exists needs an
    EXPLICIT trigger (see `_mod_div_trigger` and `expr()`'s forall/exists
    case); every committed task's quantifiers index a Seq, so this is true
    for all of them and none gets an explicit trigger it didn't already
    have (v0 and the pre-2026-09-08 v1 output are unaffected)."""
    if "op" in e:
        if e["op"] == "at":
            return True
        return any(_has_indexable(a) for a in e.get("args", []))
    if "call" in e:
        return True
    if "ite" in e:
        c = e["ite"]
        return any(_has_indexable(c[k]) for k in ("cond", "then", "else"))
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        return any(_has_indexable(q[k]) for k in ("lo", "hi", "body"))
    return False


def _mod_div_trigger(e: dict) -> dict | None:
    """First `mod`/`div` application in e, pre-order, or None. is_prime's
    ensures/invariant (SPEC.md "Early exit" corpus, 2026-09-08) is
    `forall d. 2<=d<n ==> n mod d != 0`: pure arithmetic, no Seq index or
    call, so Verus's automatic inference refuses it outright ("Could not
    automatically infer triggers for this quantifier", measured on
    is_prime.rs before this fix). `n mod d` is exactly the term that
    should fire the quantifier, so `expr()` supplies it explicitly via
    `#![trigger ...]` whenever `_has_indexable` says auto-inference has
    nothing else to go on."""
    if "op" in e:
        if e["op"] in ("mod", "div"):
            return e
        for a in e.get("args", []):
            r = _mod_div_trigger(a)
            if r is not None:
                return r
        return None
    if "call" in e:
        for a in e["call"]["args"]:
            r = _mod_div_trigger(a)
            if r is not None:
                return r
        return None
    if "ite" in e:
        c = e["ite"]
        for k in ("cond", "then", "else"):
            r = _mod_div_trigger(c[k])
            if r is not None:
                return r
        return None
    return None


def _at_roots_by_var(e: dict, v: str, out: dict) -> None:
    """Collects, into `out` (base seq name -> its `at(name, v)` node, one
    per distinct name, first occurrence kept), every DIRECT `at(X, v)`
    sub-term of e where X is a plain variable and the index is EXACTLY the
    bound variable v -- used by `expr()`'s forall/exists case below to
    decide whether Verus's own single-trigger auto-inference has more
    than one candidate to pick between. A chained read like `m[k][0]`
    does NOT add an entry for the outer `at` (its own "s" operand is
    itself an `at` node, not a plain var) but DOES add one for the inner
    `at(m, k)` via the recursive walk, exactly the root this file wants:
    the base sequence, not one of its elements. A nested forall/exists
    shadowing v starts a fresh binder, so only its own lo/hi (evaluated
    in the OUTER scope) can still mention the outer v; its body cannot."""
    if "op" in e:
        op, args = e["op"], e.get("args", [])
        if op == "at" and len(args) == 2:
            s, i = args
            if isinstance(s, dict) and "var" in s and i == {"var": v}:
                out.setdefault(s["var"], e)
        for a in args:
            _at_roots_by_var(a, v, out)
    elif "ite" in e:
        c = e["ite"]
        for k in ("cond", "then", "else"):
            _at_roots_by_var(c[k], v, out)
    elif "call" in e:
        for a in e["call"]["args"]:
            _at_roots_by_var(a, v, out)
    elif "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        for k in ("lo", "hi"):
            _at_roots_by_var(q[k], v, out)


def _mentions_var(e, v: str) -> bool:
    """True iff the bound variable v occurs anywhere in e -- a fully
    generic walk (dict values / list elements), since a t Expr JSON has no
    binding site besides forall/exists's own "var" key and t's bound
    names are never reused for an outer name in any construct this file
    handles (no shadowing worth tracking for this narrow a check, the same
    posture `_has_chained_at` already takes with its own generic walk).
    Used by `_has_fixed_at` to tell a genuinely FIXED index (`t_res.0`,
    unrelated to k) from one that merely isn't the BARE bound variable but
    still varies with it (`k + 1`, `len(s) - 1 - k`) -- reverse's and
    tail's own committed quantifiers index by exactly this second shape
    and must NOT be treated as fixed (see `_has_fixed_at`'s own
    docstring, REGRESSION below)."""
    if isinstance(e, dict):
        if e.get("var") == v:
            return True
        return any(_mentions_var(x, v) for x in e.values())
    if isinstance(e, list):
        return any(_mentions_var(x, v) for x in e)
    return False


def _has_fixed_at(e: dict, v: str) -> bool:
    """True iff e contains a Seq index `at(X, idx)` whose index does NOT
    mention the bound variable v AT ALL (`_mentions_var`) -- the shape
    measured (2026-09-10, the four "argmax" tasks named in the module
    docstring's dated note below) to confuse Verus's own single-candidate
    trigger inference when the SAME quantifier body ALSO indexes a seq
    directly by v: `forall k| ... ==> (a[FIXED] OP a[k])`, an ensures
    naming a champion INDEX rather than a champion VALUE. Measured
    directly (probe1.rs/probe5.rs/probe6.rs/probe7.rs): Verus refuses
    "Could not automatically infer triggers" outright, not merely a
    low-confidence pick (contrast the "Nested sequences" residual above,
    where auto-inference DOES pick something, just the wrong root) --
    true whether FIXED is a tuple projection (`t_res.0`), a plain
    variable, or an arithmetic expression (`i0 + 1`; probe7.rs), and true
    even when the fixed and bound reads index the SAME seq object, which
    is the only shape measured so far (SPEC.md v1 has no second seq for
    one to name here). seq_max's own `r >= s[j]` has no such second read
    (`r` is a VALUE, never an index into `s`), so this is false there;
    reverse's and tail's own `s[len(s)-1-k]` / `s[k+1]` index by an
    expression that MENTIONS k (not the bare variable, but not fixed
    either), so `_mentions_var` -- not a bare `!=` on the AST, which an
    earlier version of this function used and which changed both tasks'
    committed `out/*.rs` (an explicit trigger neither one needed, caught
    by the byte-identity regression check below) -- is what keeps this
    false for them. Walks the same shapes `_at_roots_by_var` does (args,
    ite, call, forall/exists lo/hi only, never a shadowing inner body)
    since a fixed-index read only matters as interference within the SAME
    scope v is bound in."""
    if "op" in e:
        op, args = e["op"], e.get("args", [])
        if op == "at" and len(args) == 2 and not _mentions_var(args[1], v):
            return True
        return any(_has_fixed_at(a, v) for a in args)
    if "ite" in e:
        c = e["ite"]
        return any(_has_fixed_at(c[k], v) for k in ("cond", "then", "else"))
    if "call" in e:
        return any(_has_fixed_at(a, v) for a in e["call"]["args"])
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        return any(_has_fixed_at(q[k], v) for k in ("lo", "hi"))
    return False


def _has_chained_at(e) -> bool:
    """True iff e contains a CHAINED read, `at(at(x, i), j)` (`x[i][j]`
    once rendered) -- a genuine nested-seq ELEMENT read, one nesting level
    deep, as opposed to two SEPARATE flat reads of two different
    sequences. Used to gate `expr()`'s forall/exists multi-trigger case
    (see its own comment) to the shape that actually needs it: a
    forall/exists body with two co-indexed roots but no chained read
    (swap's `r[k]==s[k]`, swap_rows' `r[k]==m[k]`) already verifies fine
    under Verus's own auto-inference, measured directly (both were
    committed and verified before this task touched anything)."""
    if isinstance(e, dict):
        if e.get("op") == "at":
            s = e["args"][0]
            if isinstance(s, dict) and s.get("op") == "at":
                return True
        return any(_has_chained_at(v) for v in e.values())
    if isinstance(e, list):
        return any(_has_chained_at(x) for x in e)
    return False


def expr(e: dict, vty: str | None = None) -> str:
    """`vty`, when given, is the VERUS type string (as `_vty` renders it,
    e.g. "Seq<Seq<int>>") that `e` is KNOWN to have from its own use site --
    threaded only to resolve the one ambiguity SPEC.md "Nested sequences"
    (2026-09-10) names ("[] is ambiguous between a plain seq and a seq<seq>
    with no rows, resolved by the declared type at the assignment"): the
    "seq" op's empty-args case below. Every other call site passes nothing
    (None), unaffected, since every other Expr form either has no such
    ambiguity or (the "_seq"/"_nested_seq" ground nodes the certificate
    emitter builds) already carries its own kind unambiguously. Found by
    construction, not by measurement first: the first swap_rows-family
    fuzz task with a `var` init of `seq()` typed Seq<Seq<int>> (this
    function's OLD unconditional "Seq::<int>::empty()") produced `let mut
    m: Seq<Seq<int>> = Seq::<int>::empty();`, a bare type mismatch (E0308)
    -- Verus's own error, not a proof failure -- confirmed on
    fz_v1nested_069 (`out/agent-verus-nested2/`), one of the two committed
    nested-seq tasks' OWN empty-literal call (row_max_len's `m` is a
    parameter, never locally re-initialized to `[]`; swap_rows' witness
    literal goes through `_tlit`'s already-typed path, not this one) so
    the mismatch was unexercised until this residual fuzz measurement."""
    if "_seq" in e:
        # Private ground node, emitted only by the refutation certificate
        # builder below: a concrete Seq<int> literal from a measured witness.
        if not e["_seq"]:
            return "Seq::<int>::empty()"
        return "seq![" + ", ".join(f"({v}int)" for v in e["_seq"]) + "]"
    if "_nested_seq" in e:
        # SPEC.md "Nested sequences" (2026-09-10): the "_seq" node one
        # level up, a concrete Seq<Seq<int>> witness value with each row
        # itself a (possibly empty) "_seq" node, so this renders as
        # `seq![<row>, <row>, ...]` with every row already correctly
        # spelled -- `Seq::<int>::empty()` for an empty row, `seq![...]`
        # otherwise -- by the SAME recursive expr() call that already
        # handles "_seq", no new row-rendering logic needed. The empty
        # outer case mirrors "_seq"'s own empty spelling one type up.
        if not e["_nested_seq"]:
            return "Seq::<Seq<int>>::empty()"
        return "seq![" + ", ".join(expr(r) for r in e["_nested_seq"]) + "]"
    if "int" in e:
        return f"({e['int']}int)" if _SUFFIX_INT else str(e["int"])
    if "var" in e:
        return e["var"]
    if "bool" in e:
        return "true" if e["bool"] else "false"
    if "ite" in e:
        c = e["ite"]
        return (f"(if {expr(c['cond'])} {{ {expr(c['then'], vty)} }}"
                f" else {{ {expr(c['else'], vty)} }})")
    if "call" in e:
        c = e["call"]
        return f"{c['fun']}(" + ", ".join(expr(a) for a in c["args"]) + ")"
    if "forall" in e or "exists" in e:
        kind = "forall" if "forall" in e else "exists"
        q = e[kind]
        v, lo, hi, body = q["var"], expr(q["lo"]), expr(q["hi"]), expr(q["body"])
        rng = f"({lo} <= {v} && {v} < {hi})"
        trig = ""
        roots: dict = {}
        _at_roots_by_var(q["body"], v, roots)
        if len(roots) >= 2 and _has_chained_at(q["body"]):
            # SPEC.md "Nested sequences" (2026-09-10) residual
            # (fz_v1nested_069): two or more DISTINCT base sequences
            # indexed by the same bound variable give Verus's own
            # single-candidate auto-inference more than one term to pick
            # between, and it can pick the one that does NOT connect back
            # to whichever sequence a surrounding proof actually needs
            # re-derived (measured: `forall k| ... m[k].len()==1 &&
            # m[k][0]==s[k]`, auto-chose the bare `s[k]` alone, "low
            # confidence" per Verus's own diagnostic, and the loop's
            # invariant then failed to carry across the append that grows
            # m -- an explicit trigger on `m[k]` alone fixed it, but so did
            # supplying BOTH `m[k]` and `s[k]` as independent trigger
            # groups, measured identically, 4/4 verified either way -- so
            # this emits one INDEPENDENT `#![trigger ...]` per distinct
            # root rather than guessing which one the proof needs, sound
            # for any number/type of co-indexed sequences since it never
            # removes a term Verus's own inference would have tried, only
            # adds the ones ambiguity was hiding). Gated on
            # `_has_chained_at` (a genuine CHAINED read, `X[k][j]`, one
            # nesting level deep) rather than firing on every 2-distinct-
            # roots body: swap's and swap_rows' own committed foralls
            # (`r[k]==s[k]`, `r[k]==m[k]`) ALSO have two distinct roots but
            # only ever single-level reads, and Verus's own auto-inference
            # already handles those fine (they were committed, verified,
            # before this task touched anything) -- an earlier,
            # ungated version of this check changed their committed
            # `out/*.rs` (an explicit trigger neither one needed),
            # breaking the byte-identity regression check below; gating on
            # the chained shape that actually distinguishes fz_v1nested_069
            # from swap/swap_rows restores it.
            trig = "".join(f" #![trigger {expr(t)}]" for t in roots.values())
        elif roots and _has_fixed_at(q["body"], v):
            # ARGMAX QUANTIFIER (2026-09-10, module docstring's dated note
            # below): a forall/exists body that indexes a seq BOTH by the
            # bound variable (>=1 root here) AND by something else fixed
            # in this scope (`_has_fixed_at`) -- "the champion so far
            # beats every k", `a[FIXED] OP a[k]` -- gets Verus's outright
            # "Could not automatically infer triggers" refusal, not merely
            # a poor pick, so the same explicit-trigger-per-root fix the
            # chained-read case above already applies closes it too: sound
            # for the identical reason (never removes a candidate Verus's
            # own inference would have tried), and additive, since no
            # previously committed quantifier has a second, fixed-index
            # read of a seq alongside its bound-variable one (seq_max's
            # champion is a VALUE, never re-indexed).
            trig = "".join(f" #![trigger {expr(t)}]" for t in roots.values())
        elif not _has_indexable(q["body"]):
            t = _mod_div_trigger(q["body"])
            if t is not None:
                trig = f" #![trigger {expr(t)}]"
            else:
                # BOUND-CHECK-ONLY QUANTIFIER (2026-09-10, the v1def fuzz
                # family's 209/268/295, malformed on the real: Verus's own
                # "Could not automatically infer triggers", quoted, at the
                # STATEMENT-level definedness
                # assert `_assert_defined` emits for an `if`/`return`
                # whose cond is a forall, never at the `_wf_lemma` copy of
                # the same obligation -- `_prenex` already hoists THAT
                # one's binder into a fresh lemma parameter, so its
                # emitted body carries no forall at all (measured: the
                # three tasks' `t_wf_..._ens0` lemmas compile clean before
                # this fix; only the inline assert, which `_prenex` never
                # touches, was malformed). This case's body has neither an
                # indexable NOR a div/mod term because `defined()`'s own
                # "at"/"update"/"slice" cases REPLACE the indexing
                # expression with its bare bound check (`0<=i && i<len`),
                # which is exactly what strips the term automatic
                # inference would have grabbed -- so this file must supply
                # SOME trigger itself. Measured directly on 209's own
                # obligation shape (probe_trig1.rs, `#![trigger i]`:
                # "trigger must be a function call, a field access, or
                # arithmetic operator", the bound variable alone does not
                # qualify; probe_trig3.rs, `#![trigger (0 <= i)]`: same
                # error, a comparison does not qualify either;
                # probe_trig2.rs, `#![trigger (i + 0)]`: 0 errors) --
                # `v + 0` is always a legal arithmetic term, always
                # mentions the bound variable, and changes nothing the
                # quantifier proves (an additive identity), so it is a
                # sound fallback for ANY forall/exists this branch reaches,
                # not just these three tasks' own shape. Regenerated
                # 209/268/295: all three go malformed -> verified; the
                # `_mod_div_trigger` branch above (is_prime) and every
                # `_has_indexable` branch (every committed seq/nested-seq
                # quantifier) are untouched, since both fire before this
                # `else` and neither task in this fuzz family reaches it.
                t = {"op": "+", "args": [{"var": v}, {"int": 0}]}
                trig = f" #![trigger {expr(t)}]"
        if kind == "forall":
            return f"(forall|{v}: int|{trig} {rng} ==> {body})"
        return f"(exists|{v}: int|{trig} {rng} && {body})"
    op, args = e["op"], [expr(a) for a in e.get("args", [])]
    if op == "neg":
        return f"(-{args[0]})"
    if op == "not":
        return f"(!{args[0]})"
    if op == "len":
        return f"({args[0]}.len() as int)"
    if op == "at":
        return f"{args[0]}[{args[1]}]"
    if op == "update":
        return f"{args[0]}.update({args[1]}, {args[2]})"
    if op == "fill":
        return f"Seq::new({args[0]} as nat, |_t_fill_i: int| {args[1]})"
    if op == "seq":
        # SPEC.md "Sequences: literals, concatenation, slices" (2026-09-09):
        # [e1, ..., en], n >= 0. `seq!` is vstd's own literal macro; the
        # empty case renders as `Seq::<int>::empty()` (measured,
        # probe_seq_basic.rs: both forms verify, and `seq![]` is not needed
        # since this file already has the empty-literal spelling from the
        # certificate builder's `_seq` node below). Each element is
        # rendered by `expr()` like any other operand, so a non-literal
        # element (filter_pos's `seq![s[i]]`) picks up the same suffixing
        # and indexing this file already emits everywhere else.
        #
        # The empty case is ambiguous one type up (SPEC.md "Nested
        # sequences", 2026-09-10): `[]` typed Seq<Seq<int>> at its own use
        # site must spell "Seq::<Seq<int>>::empty()", not the flat default
        # -- `vty` (see `expr`'s own docstring) carries exactly that,
        # threaded from the one statement-level site an empty literal's
        # type is actually known (`stmts`'s "var"/"assign"/"return").
        if not args:
            if vty == "Seq<Seq<int>>":
                return "Seq::<Seq<int>>::empty()"
            return "Seq::<int>::empty()"
        return "seq![" + ", ".join(args) + "]"
    if op == "slice":
        # s[a..b]: vstd's own `Seq::subrange`, measured (probe_seq_expr.rs,
        # probe_subrange2.rs). Its own `recommends` is NOT enforced by the
        # kernel (measured: an unguarded out-of-bound `subrange` compiles
        # with only a "recommendation not met" NOTE, and a false claim
        # about its result -- e.g. the length postcondition -- correctly
        # FAILS to verify rather than being handed a totalized value), so
        # this op carries no defaults of its own; `defined()`'s "slice"
        # case below is what actually keeps this lowering honest, exactly
        # as SPEC.md requires ("a definedness obligation ... exactly as
        # `at`").
        return f"{args[0]}.subrange({args[1]}, {args[2]})"
    if op == "pair":
        # SPEC.md "Pairs" (2026-09-10): (a, b), a Rust tuple, Verus's own
        # product type in exec and spec/proof code alike (measured,
        # probe_pair_basic.rs); no per-pair-type declaration is needed the
        # way SPARK or Lean need one.
        return f"({args[0]}, {args[1]})"
    if op == "split":
        # SPEC.md "The string library (v1)": split(s) (whitespace) and
        # split(s, c) (one code point) are "two arities of one op" --
        # `STRLIB_PRELUDE`'s own two spec fns, dispatched on arg count.
        return (f"t_str_split_ws({args[0]})" if len(args) == 1
                else f"t_str_split_c({args[0]}, {args[1]})")
    if op == "join":
        return f"t_str_join({args[0]}, {args[1]})"
    if op == "tostr":
        return f"t_str_tostr({args[0]})"
    if op == "count":
        return f"t_str_count({args[0]}, {args[1]})"
    if op == "find":
        return f"t_str_find({args[0]}, {args[1]})"
    if op == "strip":
        return f"t_str_strip({args[0]})"
    if op == "lstrip":
        return f"t_str_lstrip({args[0]})"
    if op == "rstrip":
        return f"t_str_rstrip({args[0]})"
    if op == "replace":
        return f"t_str_replace({args[0]}, {args[1]}, {args[2]})"
    if op == "lower":
        return f"t_str_lower({args[0]})"
    if op == "upper":
        return f"t_str_upper({args[0]})"
    if op == "isdigit":
        return f"t_str_isdigit({args[0]})"
    if op == "isalpha":
        return f"t_str_isalpha({args[0]})"
    if op == "isupper":
        return f"t_str_isupper({args[0]})"
    if op == "islower":
        return f"t_str_islower({args[0]})"
    if op == "startswith":
        return f"t_str_startswith({args[0]}, {args[1]})"
    if op == "endswith":
        return f"t_str_endswith({args[0]}, {args[1]})"
    if op == "fst":
        # p.0: always defined on a pair (`defined()`'s existing catch-all
        # already computes exactly SPEC.md's formula for this op, see its
        # comment below, so no new case was needed there).
        return f"{args[0]}.0"
    if op == "snd":
        return f"{args[0]}.1"
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
    if op == "update":
        s, i, v = args
        bound = {"op": "and", "args": [
            {"op": "<=", "args": [{"int": 0}, i]},
            {"op": "<", "args": [i, {"op": "len", "args": [s]}]}]}
        return _conj([defined(s), defined(i), defined(v), bound])
    if op == "fill":
        n, v = args
        nonneg = {"op": ">=", "args": [n, {"int": 0}]}
        return _conj([defined(n), defined(v), nonneg])
    if op == "slice":
        # s[a..b]: DEFINED IFF 0 <= a <= b <= len(s) (SPEC.md "Sequences:
        # literals, concatenation, slices", 2026-09-09), a definedness
        # obligation under these rules exactly as `at` outside [0, len) --
        # Verus's own `subrange` only carries a `recommends`, which the
        # kernel does not enforce (measured, see `expr()`'s "slice" case),
        # so this file owes the bound itself or a bad slice would silently
        # totalize. `seq` (the literal) and `+` (concatenation, on two
        # seqs as much as on two ints) need no case here: both are total
        # per SPEC.md ("a literal is defined iff all its elements are";
        # "a concatenation is defined iff both arguments are"), exactly the
        # formula the existing catch-all below already computes for every
        # total operator, `+` included.
        s, a, b = args
        bound = {"op": "and", "args": [
            {"op": "<=", "args": [{"int": 0}, a]},
            {"op": "<=", "args": [a, b]},
            {"op": "<=", "args": [b, {"op": "len", "args": [s]}]}]}
        return _conj([defined(s), defined(a), defined(b), bound])
    if op in ("div", "mod"):
        x, y = args
        nonzero = {"op": "!=", "args": [y, {"int": 0}]}
        return _conj([defined(x), defined(y), nonzero])
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
    # total operators: not neg len + - * == != < <= > >=, and (SPEC.md
    # "Pairs", 2026-09-10) pair, fst, snd: "pair" is defined iff both
    # components are, exactly the formula below; "fst"/"snd" are "always
    # defined on a pair", which given a well-typed operand (check_wf's job,
    # not this function's) is exactly defined(operand) alone, what the same
    # formula computes for a single-argument op. Neither needed its own
    # case.
    return _conj([defined(a) for a in args])


def _nested_seq_operand_ty(e: dict, scope: dict) -> str | None:
    """Best-effort VERUS type of e, precise enough ONLY to tell whether e
    is nested-seq-typed (`"Seq<Seq<int>>"`) -- the one fact
    `_nested_eq_bridges` below needs to decide whether a `==`/`!=` needs
    the extensionality bridge. `None` when undeterminable; never WRONG
    when it does answer, since every case here is either a direct `scope`
    lookup (a param or local's own declared type) or an operator whose
    result type is syntactically identical to one of its own operands'
    (`+`, `slice`, `update` all return the same seq type they operate on;
    `at` does not -- it strips one level of nesting -- so it is
    deliberately absent here rather than wrongly answering "nested" one
    level too high)."""
    if "var" in e:
        ent = scope.get(e["var"])
        return ent[0] if ent else None
    if "op" in e:
        op, args = e["op"], e.get("args", [])
        if op in ("+", "slice", "update") and args:
            return _nested_seq_operand_ty(args[0], scope)
    return None


def _nested_eq_bridges(e: dict, scope: dict, out: list) -> None:
    """SPEC.md "Nested sequences" (2026-09-10) residual: collects every
    `==`/`!=` node in e whose BOTH operands are nested-seq-typed, walking
    the same Expr shapes `_has_indexable` already walks. The one missing
    lemma this fuzz measurement found (fz_v1nested_026, fz_p_nest_eq,
    `_shape: eq_nested`): Verus's bare `==` on Seq<Seq<int>> already IS
    full recursive equality at the Z3 level in the direction a proof GOAL
    needs (measured, "EQUALITY" above), but NOT in the direction a
    HYPOTHESIS needs -- `m == n` in scope does not, by itself, let Z3
    conclude `forall k. m[k] == n[k]` or its negation `!(m=~=n) ==>
    m.len()!=n.len() || exists k. m[k]!=n[k]`, the two halves an `ensures`
    unfolding a nested-seq `==` into `len && forall` actually needs
    (measured: fz_v1nested_026.rs failed "postcondition not satisfied"
    with NO hint at all; probe2.rs isolated it to exactly the disequality
    half, probe4.rs confirmed `assert((m == n) == (m =~= n));` unlocks
    BOTH halves at once, unconditionally, no branch on which value `==`
    took). `stmts()` calls this at every assign/var-init/return whose
    value expression contains such a node, each occurrence bridged once."""
    if "op" in e:
        op, args = e["op"], e.get("args", [])
        if op in ("==", "!=") and len(args) == 2:
            a, b = args
            if (_nested_seq_operand_ty(a, scope) == "Seq<Seq<int>>"
                    and _nested_seq_operand_ty(b, scope) == "Seq<Seq<int>>"):
                out.append((a, b))
        for a in args:
            _nested_eq_bridges(a, scope, out)
    elif "ite" in e:
        c = e["ite"]
        for k in ("cond", "then", "else"):
            _nested_eq_bridges(c[k], scope, out)
    elif "call" in e:
        for a in e["call"]["args"]:
            _nested_eq_bridges(a, scope, out)
    elif "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        for k in ("lo", "hi", "body"):
            _nested_eq_bridges(q[k], scope, out)


def _walk_at_seq_params(e, seq_params: set, seen: set) -> None:
    """Collects, into `seen`, every name in `seq_params` that appears as
    the SEQ operand of an `at`/`update` node ANYWHERE inside e -- used by
    `_spec_fn_domain_context` below to find which of a spec_fun's OWN seq
    params its decreases variable indexes into. A plain untyped recursive
    walk (matching e's own dict/list shape rather than each Expr form by
    name, unlike `_has_indexable`/`_nested_eq_bridges` above) since the
    thing being hunted, `{"op": "at"/"update", "args": [{"var": name}, ..
    .]}`, can be nested arbitrarily deep under `ite`, `call`, `forall`, or
    a further `at`/`update`, and none of those wrapper shapes need their
    own case to find it."""
    if isinstance(e, dict):
        if e.get("op") in ("at", "update") and e.get("args"):
            s = e["args"][0]
            if isinstance(s, dict) and "var" in s and s["var"] in seq_params:
                seen.add(s["var"])
        for v in e.values():
            _walk_at_seq_params(v, seq_params, seen)
    elif isinstance(e, list):
        for x in e:
            _walk_at_seq_params(x, seq_params, seen)


def _ite_conds(e, out: list) -> None:
    """Collects, into `out`, the `cond` of every `ite` node in e (any
    depth), used by `_spec_fn_domain_context` to decide whether a
    recursive spec_fun already self-guards a given seq param's length
    somewhere in its own branching, before ever reaching Verus."""
    if isinstance(e, dict):
        if "ite" in e:
            c = e["ite"]
            out.append(c["cond"])
            _ite_conds(c["then"], out)
            _ite_conds(c["else"], out)
        else:
            for v in e.values():
                _ite_conds(v, out)
    elif isinstance(e, list):
        for x in e:
            _ite_conds(x, out)


def _mentions_len(e, pname: str) -> bool:
    """True iff `len(pname)` appears anywhere inside e."""
    if isinstance(e, dict):
        if e.get("op") == "len" and e.get("args") == [{"var": pname}]:
            return True
        return any(_mentions_len(v, pname) for v in e.values())
    if isinstance(e, list):
        return any(_mentions_len(x, pname) for x in e)
    return False


def _spec_fn_domain_context(f: dict) -> list[dict]:
    """SPEC.md gate 3 (2026-09-10 residual, fz_v1nested_150): a
    self-recursive spec_fun's own body-definedness lemma previously
    carried NO hypothesis at all (`context=[]` at its one call site in
    `emit()`), sound only when every `at`/`update` the body performs is
    ALREADY self-guarded on BOTH ends by its own `ite` condition --
    count_matches' own `count(s, x, n)` is (`(n<=0) || (n>len(s))` as ONE
    guard covers both the base case AND the out-of-range case at once, its
    OWN cond mentioning `len(s)` directly, so `defined(body)` reduces to
    TRUE unconditionally, no hypothesis needed) but rowsum(row, k)
    (`decreases k`, guarding only `k<=0`, its cond never mentioning
    `len(row)` at all) is not, measured directly:
    `t_wf_fz_v1nested_150_fn_rowsum`, an assert over UNCONSTRAINED row/k,
    failed ("assertion failed", row=Seq::empty(), k=5 a trivial
    countermodel) even though the REAL body, called only ever at
    0<=k<=len(row) (fz_v1nested_150's own loop invariant and its
    top-level ensures both establish exactly that, never anything wider),
    is perfectly well-defined in practice. The missing hint is exactly
    that relationship, derived from the spec_fun's OWN shape rather than
    any task's param names: for every seq-typed param the body actually
    reads/writes at an offset of `decreases` (`_walk_at_seq_params`)
    whose length its OWN `ite` conditions never already mention
    (`_mentions_len` false everywhere in `_ite_conds`), assume that
    param's length bounds `decreases` above -- narrowed to exactly the
    NOT-already-self-guarded case (rather than added unconditionally) so
    it stays a no-op, not merely a harmless one, wherever a spec_fun's own
    guard already covers it: measured directly, an EARLIER, unconditional
    version of this function changed count_matches' and digit_sum's
    committed `out/*.rs` (an extra `requires` neither needed), breaking
    the byte-identity regression check below; this narrower version adds
    nothing to either, restoring it. `0 <= decreases` alone is never
    added standalone either (probe150b.rs measured `k <= row.len()` by
    itself already sufficient -- the base-case ite arm already gives
    `k>0` for free in the recursive branch, so only the UPPER bound was
    ever missing)."""
    dec = f["decreases"]
    ctx = []
    seq_params = {p["name"] for p in f["params"] if p["type"] == "seq"}
    seen: set = set()
    _walk_at_seq_params(f["body"], seq_params, seen)
    conds: list = []
    _ite_conds(f["body"], conds)
    for pname in sorted(seen):
        if any(_mentions_len(c, pname) for c in conds):
            continue
        ctx.append({"op": "<=",
                     "args": [dec, {"op": "len", "args": [{"var": pname}]}]})
    return ctx


def subst(e: dict, m: dict) -> dict:
    """Capture-avoiding substitution over a t expression: each mapped name
    is replaced by a new name (str) or a whole t expression (dict)."""
    if "var" in e:
        v = m.get(e["var"])
        if v is None:
            return e
        return {"var": v} if isinstance(v, str) else v
    if "int" in e or "bool" in e or "_seq" in e or "_nested_seq" in e:
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
        if "return" in s and _calls(s["return"][1], name):
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
    # 2026-09-08 (SPEC.md "Early exit"): deliberately no `return` case. This
    # set feeds `loop()`'s choice of which scope names are ordinary loop
    # STATE, threaded through the recursive helper's arguments every
    # iteration. A `return`'s target is not that: it is produced at most
    # once, on the exit path, and `loop()` carries it through a separate
    # wrapped-result slot (see `_may_return` below), never as per-iteration
    # state. Folding it in here would double up the two mechanisms.
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


def _may_return(body: list) -> bool:
    """True iff `body` contains a `return` (SPEC.md "Early exit",
    2026-09-08), directly, inside an `if` branch, or inside a nested
    `while`'s body. The nested-loop case matters: a nested loop that may
    return already wraps ITS OWN result (see `loop()`), so the loop
    enclosing it also needs the wrapped-result treatment purely to
    propagate that outward, even though no `return` sits directly in its
    own body."""
    for s in body:
        if "return" in s:
            return True
        if "if" in s:
            if _may_return(s["if"]["then"]) or _may_return(s["if"].get("else") or []):
                return True
        if "while" in s:
            if _may_return(s["while"]["body"]):
                return True
    return False


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
    while (its effect is not equational), or, 2026-09-08 (SPEC.md "Early
    exit"), a `return`: an iteration that can escape the loop entirely has
    no single equational post-state either, so the nonlinear_arith bridge
    in `loop()` is skipped and preservation is left to Verus unaided (an
    UNPROVED cell there is not a failure, just no committed task needs
    both a nonlinear invariant and a `return` in the same loop yet)."""
    env = dict(env)
    for s in body:
        if "assign" in s:
            n, e = s["assign"]
            env[n] = subst(e, env)
        elif "return" in s:
            return None
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


def _div_mod_pairs(e: dict) -> list[tuple[dict, dict]]:
    """Every distinct (x, y) operand pair fed to a `div` or `mod`
    application anywhere in e, first-seen order, deduplicated by rendered
    Verus text (so `div(m, 10)` and a later `mod(m, 10)` in the same
    statement share one bridging fact, see _div_mod_law)."""
    seen: dict[tuple[str, str], tuple[dict, dict]] = {}

    def walk(n: dict) -> None:
        if "ite" in n:
            c = n["ite"]
            walk(c["cond"]); walk(c["then"]); walk(c["else"])
            return
        if "call" in n:
            for a in n["call"]["args"]:
                walk(a)
            return
        if "forall" in n or "exists" in n:
            q = n.get("forall") or n.get("exists")
            walk(q["lo"]); walk(q["hi"]); walk(q["body"])
            return
        if "op" in n:
            if n["op"] in ("div", "mod"):
                x, y = n["args"]
                seen.setdefault((expr(x), expr(y)), (x, y))
            for a in n.get("args", []):
                walk(a)

    walk(e)
    return list(seen.values())


def _div_mod_law(x: dict, y: dict, ind: str) -> str:
    """The Euclidean defining identity `x == (x div y) * y + (x mod y)`,
    established by nonlinear_arith. Measured 2026-09-08: Verus's default
    solver profile (nonlinear arithmetic off) cannot discharge this
    unaided (probe_law.rs: `ensures x == (x/y)*y + (x%y)` with `requires
    y != 0` alone, postcondition not satisfied) because `(x/y)*y`
    multiplies two non-literal terms, but `by (nonlinear_arith) requires
    y != 0 { }` / `requires y != 0;` both close it (probe_law3.rs,
    probe_law4.rs). The range half of the law, `0 <= x%y` and
    `x%y < y || x%y < -y`, is native (probe_range.rs, 0 errors, no hint
    needed) so only the multiplicative identity is asserted here. Sound
    and task-independent: it is a fact about `/` and `%` themselves, true
    for every y != 0, and the `requires` premise is exactly the
    definedness obligation this div/mod already owes (SPEC.md, `defined()`
    above), so it can never smuggle in a task's own obligation as a
    hypothesis; Verus still has to prove that premise from ambient facts
    (measured, probe_law5.rs: dropping the ambient `y != 0` turns this
    into "requires not satisfied")."""
    ident = {"op": "==", "args": [x, {"op": "+", "args": [
        {"op": "*", "args": [{"op": "div", "args": [x, y]}, y]},
        {"op": "mod", "args": [x, y]}]}]}
    nz = {"op": "!=", "args": [y, {"int": 0}]}
    return (f"{ind}assert({expr(ident)}) by (nonlinear_arith)\n"
            f"{ind}    requires\n{ind}        {expr(nz)},\n"
            f"{ind};")


def _dummy(ty) -> str:
    """A throwaway literal of t type `ty` (a base type name, or SPEC.md
    "Pairs" {"pair": [T1, T2]}), for the slot a wrapped loop helper's
    result (SPEC.md "Early exit", 2026-09-08) leaves unused: the return
    value when the call did not return, or the state tuple when it did.
    Its VALUE is never read (the ensures conditions each slot on the same
    flag that decided which one is meaningful); it only has to type-check.
    Takes the t-level type, not the resolved Verus string `_vty` produces,
    so a pair recurses into its own two components (always base types, no
    pair of pairs) and renders `(dummy1, dummy2)`, the same tuple literal
    `expr()`'s "pair" case emits. Built via `expr()` for the base cases so
    it picks up the same `_SUFFIX_INT` literal form (`0int`) v1 already
    emits everywhere else. (SPEC.md "Nested sequences", 2026-09-10):
    {"seq": "seq"} renders the empty nested seq, `expr()`'s own "_nested_seq"
    ground node with no rows -- the same choice `ty == "seq"` already makes
    one level down. Unexercised by either committed nested-seq task (neither
    carries a `return` inside a loop, the only slot this fills), named here
    by construction rather than left silent, same posture as this
    function's own pair-of-pair note before it."""
    if isinstance(ty, dict):
        if "seq" in ty:
            return expr({"_nested_seq": []})
        t1, t2 = ty["pair"]
        return f"({_dummy(t1)}, {_dummy(t2)})"
    if ty == "int":
        return expr({"int": 0})
    if ty == "bool":
        return expr({"bool": False})
    if ty == "seq":
        return expr({"_seq": []})
    raise ValueError(f"verus: no dummy literal for type {ty!r}")


# DIVISOR-BOUND LEMMA (2026-09-11, ROADMAP 16.2, divisor-bound item):
# dafny-synthesis isNonPrime (3) and isPrime (605) trial-divide `n` only up
# to `n div 2` (`cond: i <= n div 2`) while their own `ensures` quantifies
# the divisor over the WIDER range `[2, n)` -- the fact no stated invariant
# supplies is the number-theory lemma this family needs at the loop's
# exit: any `k` with `2 <= k < n` and `n % k == 0` satisfies `k <= n / 2`
# (`n == (n/k)*k`, and `n/k >= 2` since `k < n` rules out `n/k <= 1`, so
# `n >= 2*k`). Measured directly (`rust_verify` 0.2026.08.30.b432e82,
# `probe1.rs` this session): a plain `proof fn` for that fact, with the
# SAME `nonlinear_arith` bridge this file's own `_div_mod_law` already
# uses for every other div/mod obligation (assert the Euclidean identity
# first, by nonlinear_arith requiring the divisor nonzero, THEN the bound
# itself, by nonlinear_arith over that identity plus the ordinary
# hypotheses) -- verifies with no other assist.
#
# `_divisor_bound_target` recognizes the shape from the task's own AST
# (identical to `lower_fstar.py`'s own function of the same name, kept as
# a separate copy here since the two lowerings share no code -- see this
# file's own module docstring on that), so a task with none of it is
# untouched: an ensures `result == (forall|exists) k in [lo, N) . (N % k)
# RELOP 0`, a matching loop invariant of the SAME shape over `[lo, i)`
# (`i` the loop's own counter), and a guard `cond` exactly `i <= N div
# 2`. Where it matches, `loop()` (both call sites above) adds the derived
# exit-bound invariant `i <= N/2 + 1` and calls
# `t_divisor_bound_<task>` right at the loop's own normal (non-early-
# return) exit -- so every OTHER task's loop is byte-for-byte unchanged.
# Measured 2026-09-11: isNonPrime (3) and isPrime (605) move verus real
# unproved -> verified (twin unchanged, the twin ladder's own open item,
# not this column's -- `dafny_synthesis_task_id_3__isNonPrime` and
# `_605__isPrime` both read verus verified/unproved after, matching
# dafny's own verified/unsound reading on the same two).
def _quant_mod_relop(body):
    """`body` is `(N % k) RELOP 0` (RELOP "=="/"!="); returns `(N,
    k_name, RELOP)` or None. `k` must be a bare var, matching every task
    this targets."""
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
                    "lo": lo, "i_name": i_name, "result": ret}
    return None


def _divisor_bound_verus_defs(task_name: str, plan: dict) -> str:
    n = expr(plan["dividend"])
    lo = expr(plan["lo"])
    i = plan["i_name"]
    half = f"t_divisor_le_half_{task_name}"
    bound = f"t_divisor_bound_{task_name}"
    half_def = (
        f"proof fn {half}(n: int, k: int)\n"
        "    requires\n"
        f"        n >= 2,\n"
        f"        {lo} <= k,\n"
        f"        k < n,\n"
        f"        n % k == 0,\n"
        "    ensures\n"
        f"        k <= n / 2,\n"
        "{\n"
        "    assert(k != 0);\n"
        "    assert(n == (n / k) * k + n % k) by (nonlinear_arith)\n"
        "        requires\n"
        "            k != 0,\n"
        "    ;\n"
        "    assert(k <= n / 2) by (nonlinear_arith)\n"
        "        requires\n"
        f"            n >= 2,\n"
        f"            {lo} <= k,\n"
        f"            k < n,\n"
        f"            n % k == 0,\n"
        "            n == (n / k) * k + n % k,\n"
        "    ;\n"
        "}\n\n")
    pos = "!= 0" if plan["relop"] == "!=" else "== 0"
    neg = "== 0" if plan["relop"] == "!=" else "!= 0"

    def _forall_block(rel: str) -> str:
        return (
            f"        assert forall |k: int| #![trigger (n % k)] "
            f"({lo} <= k && k < n) implies (n % k {rel}) by {{\n"
            f"            if k < {i} {{\n"
            f"                assert(n % k {rel});\n"
            "            } else {\n"
            f"                if n % k == 0 {{\n"
            f"                    {half}(n, k);\n"
            "                }\n"
            "            }\n"
            "        }\n")

    def _exists_block(rel: str) -> str:
        return (
            f"        let {ivar} = choose |{ivar}: int| "
            f"#![trigger (n % {ivar})] ({lo} <= {ivar} && {ivar} < {i}) "
            f"&& (n % {ivar} {rel});\n"
            f"        assert({lo} <= {ivar} && {ivar} < n && n % {ivar} {rel});\n"
            f"        assert(exists |k: int| #![trigger (n % k)] "
            f"({lo} <= k && k < n) && (n % k {rel}));\n")
    ivar = "k_v"
    if plan["kind"] == "forall":
        # forall-not-a-divisor family (isPrime): true means "still no
        # divisor found" (widen the forall directly); false means a
        # divisor WAS found in [lo, i) (`neg`, i.e. `n % k_v == 0`), so
        # the exists-widen direction uses `neg`, not `pos`.
        result_true_block = _forall_block(pos)
        result_false_block = _exists_block(neg)
        quant_txt = (
            f"forall|k_v: int| #![trigger (n % k_v)] "
            f"(({lo} <= k_v) && (k_v < {i})) ==> ((n % k_v) {pos})")
        quant_full_txt = (
            f"forall|k: int| #![trigger (n % k)] "
            f"(({lo} <= k) && (k < n)) ==> ((n % k) {pos})")
    else:
        # exists-a-divisor family (isNonPrime): true means a divisor WAS
        # found in [lo, i) (`pos`, `n % k_v == 0`), widen directly; false
        # means none found (`neg`, the forall-not-a-divisor direction).
        result_true_block = _exists_block(pos)
        result_false_block = _forall_block(neg)
        quant_txt = (
            f"exists|k_v: int| #![trigger (n % k_v)] "
            f"(({lo} <= k_v) && (k_v < {i})) && ((n % k_v) {pos})")
        quant_full_txt = (
            f"exists|k: int| #![trigger (n % k)] "
            f"(({lo} <= k) && (k < n)) && ((n % k) {pos})")
    bound_def = (
        f"proof fn {bound}(n: int, {i}: int, result: bool)\n"
        "    requires\n"
        f"        n >= 2,\n"
        f"        {lo} <= {i},\n"
        f"        {i} <= (n / 2) + 1,\n"
        f"        !({i} <= n / 2),\n"
        f"        result == ({quant_txt}),\n"
        "    ensures\n"
        f"        result == ({quant_full_txt}),\n"
        "{\n"
        "    if result {\n"
        f"{result_true_block}"
        "    } else {\n"
        f"{result_false_block}"
        "    }\n"
        "}\n")
    return half_def + bound_def


class _V1:
    def __init__(self, task: dict):
        self.task = task
        self.name = task["name"]
        self.helpers: list[str] = []   # loop helper proof fns
        self.wf: list[str] = []        # definedness (well-formedness) lemmas
        self.loop_ix = 0
        # 2026-09-11 (ROADMAP 16.2), name -> defining Expr for every
        # body-local `var` seen so far in `stmts` (appendArrayToSeq's own
        # `h`, `let h = a.len()`). See `loop()`'s own note at its read of
        # this dict for why it exists.
        self.local_inits: dict[str, dict] = {}

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
        for x, y in _div_mod_pairs(e):
            lines.append(_div_mod_law(x, y, ind))

    def _assert_nested_eq(self, e: dict, scope: dict, lines: list[str],
                           ind: str) -> None:
        """SPEC.md "Nested sequences" (2026-09-10) residual, see
        `_nested_eq_bridges`'s own docstring for the measurement: one
        `assert` per DISTINCT nested-seq `==`/`!=` this statement's value
        expression contains, each unlocking BOTH directions of the
        Seq<Seq<int>> extensionality Z3 needs and neither `_assert_defined`
        nor `defined()` otherwise supplies (this is not a definedness
        obligation -- `==` on two well-typed seqs is always defined -- it
        is a PROOF hint, so it lives beside `_assert_defined` rather than
        inside it)."""
        pairs: list = []
        _nested_eq_bridges(e, scope, pairs)
        seen: set = set()
        for a, b in pairs:
            sa, sb = expr(a), expr(b)
            if (sa, sb) in seen:
                continue
            seen.add((sa, sb))
            lines.append(f"{ind}assert(({sa} == {sb}) == ({sa} =~= {sb}));")

    def _nonlinear_ensures_bridge(self, ret_val: dict, ind: str) -> list[str]:
        """TOP-LEVEL NONLINEAR ENSURES (2026-09-10, module docstring's dated
        note below, hoareTripleReqEns: `k_p == (i+1)*(i+1)` given
        `k == i*i`). LOOPS already bridges a nonlinear INVARIANT past
        Verus's default solver profile (nonlinear arithmetic off, module
        docstring "LOOPS") via `assert(...) by (nonlinear_arith) requires
        ...`; a nonlinear top-level `ensures` at the task's own return
        needs the identical escape hatch, just with no loop or symbolic
        post-state involved. Measured (pht2.rs/pht3.rs/pht4.rs): a bare
        `assert(goal)` (no hint) and `assert(goal) by (nonlinear_arith)`
        with NO requires clause, or with only the task's own `requires`
        restated but not the return's OWN value, all fail; substituting the
        return name in the ensures clause by its VALUE expression (this
        function's `ret_val`, so the goal reads e.g. `((k+2*i)+1) ==
        (i+1)*(i+1)` with no `k_p` left in it at all) and giving the
        task's own `requires` as the block's premises together suffice
        (pht4.rs, 0 errors) -- restating the return's own value as an
        EXTRA premise instead (pht1.rs) also works but is unnecessary, so
        this takes the simpler form. Called from the two places a
        task-level return happens: `stmts`'s "return" case (`wrap is
        None`, `ret_val` = the returned expression itself, exactly what
        Verus's own ensures check substitutes there too) and `emit`'s
        trailing `{rname}` (`ret_val` = `_sym`'s closed form for the
        return name over the whole body -- None, skipped there, when the
        body contains a `return` or `while`, per `_sym`'s own docstring;
        a body with an explicit `return` is covered at that return
        instead, never both). Only fires per ensures clause that
        `_has_nonlinear` flags, so every previously committed task (none
        of whose ensures multiplies two non-literal factors) emits none of
        this and is unaffected.

        Skipped ENTIRELY (`_div_mod_pairs(ret_val)` nonempty) when the
        returned value itself contains a `div`/`mod` application: measured
        on remainder and divmod_pair, both committed BEFORE this task and
        both with a nonlinear top-level ensures restating the Euclidean
        identity (`x == (x/y)*y + r`) that `_div_mod_law` already bridges
        from the SAME statement's own `_assert_defined` call -- an earlier,
        unguarded version of this function added a SECOND, redundant
        nonlinear_arith assert there, changing both tasks' committed
        `out/*.rs` with no proof gained (caught by the byte-identity
        regression check below, both already verified without it); this
        guard leaves that existing mechanism as the only bridge for a
        div/mod-shaped identity and reserves this one for a PURE
        multiplication ensures like hoareTripleReqEns's, which has no
        div/mod anywhere in its body."""
        if _div_mod_pairs(ret_val):
            return []
        lines = []
        reqs = self.task.get("requires", [])
        rname = self.task["returns"][0]["name"]
        for en in self.task["ensures"]:
            # 2026-09-11 (ROADMAP 16.2): centeredHexagonalNumber's two
            # ensures are `result == 3*n*(n-1)+1` (nonlinear on its face)
            # and `result >= 0` (NOT nonlinear on its face -- no
            # multiplication anywhere in "result >= 0" itself). The second
            # clause's actual proof obligation is nonlinear only once
            # `result` is read back as the value the body actually
            # assigned (3*n*(n-1)+1 >= 0), so checking `_has_nonlinear` on
            # `en` before substitution missed it and Verus's default
            # (linear-only) profile could not discharge the postcondition.
            # Checking the SUBSTITUTED goal instead catches both shapes:
            # a nonlinear term already spelled out in the ensures (the
            # previous case, hoareTripleReqEns, unaffected since
            # substituting the return name there does not remove the
            # multiplication) and one hidden behind the return value
            # (centeredHexagonalNumber, newly caught). Measured: 86 moves
            # unproved -> verified.
            goal_e = subst(en, {rname: ret_val})
            if not _has_nonlinear(goal_e):
                continue
            goal = expr(goal_e)
            req_s = ""
            if reqs:
                req_s = (f"{ind}    requires\n{ind}        "
                         + f",\n{ind}        ".join(expr(r) for r in reqs)
                         + ",\n")
            lines.append(f"{ind}assert({goal}) by (nonlinear_arith)\n{req_s}{ind};")
        return lines

    def _strlib_ground_bridge(self, ret_val: dict, ind: str) -> list[str]:
        """CONCRETE STRING-LIBRARY LITERALS (2026-09-11, fz_p_str_tab,
        fz_p_str_lowernonletter). `STRLIB_PRELUDE`'s recursive spec fns
        (`t_str_split_ws_acc`, `t_str_lower`, ...) are proved terminating
        by their own `decreases`, but that gives the SMT solver only
        axiom-style unfolding, gated by Verus's default recursion fuel: a
        goal that needs the definition unrolled three or six times over a
        LITERAL (no param, no loop, nothing for induction to hang on) is
        exactly the case that fuel is too shallow for. Measured directly:
        fz_p_str_tab (3-element split, 2 levels of recursion down each
        branch) and fz_p_str_lowernonletter (a 6-element `lower`, 6 levels)
        both read `postcondition not satisfied` from verus itself with no
        further diagnostic, on a file where every other proof obligation
        (all 23 of them) already verifies.

        The fix already lives in this file for nonlinear arithmetic
        (`_nonlinear_ensures_bridge`, immediately above): hand the solver a
        `compute_only` goal instead of asking it to unfold axioms on its
        own. `compute_only` interprets the recursive spec fns GROUND, no
        SMT, no fuel limit, so it is exactly the right instrument here --
        but only when the goal has nothing left to substitute: `ret_val`
        (`_sym`'s closed form for the return name, called with an EMPTY
        env exactly as the nonlinear bridge's caller does) must contain no
        `var` at all, checked by `_is_ground` below. A task with params
        (str_countempty, str_findempty, str_splitempty: general over a
        parameter `s`) fails that check and gets no bridge line, unchanged
        -- proved a different way already (SPEC.md's own stated identity,
        no recursion unfolding needed), and none of the 5 byte-identity
        tasks (abs, gcd, sum_upto, count_vowels, reverse) call any STRLIB_OP
        at all, so this method never runs for them."""
        lines = []
        rname = self.task["returns"][0]["name"]
        for en in self.task["ensures"]:
            goal_expr = subst(en, {rname: ret_val})
            if not _is_ground(goal_expr):
                continue
            lines.append(f"{ind}assert({expr(goal_expr)}) by (compute_only);")
        return lines

    def stmts(self, body: list, scope: dict, ind: str,
              wrap: str | None = None) -> list[str]:
        """scope: ordered {name: (verus_type, mutable)}. Returns lines.

        `wrap` (SPEC.md "Early exit", 2026-09-08) is None when `body` runs
        directly in the task's own proof fn: a `return` there is a bare
        Verus `return value;`, ending the task exactly as it ends the
        interpreter's exec_body. Inside a loop helper whose body may
        return (`_may_return`), `wrap` is instead the Verus expression for
        THAT helper's own state tuple, so a `return` there emits
        `return (true, value, wrap);` -- the helper's wrapped result, see
        `loop()` -- and a nested loop's own wrapped result is re-wrapped
        the same way at its call site below."""
        lines: list[str] = []
        for s in body:
            if "assign" in s:
                name, e = s["assign"]
                assert name in scope and scope[name][1], \
                    f"assign to {name}, not a mutable name in scope"
                self._assert_defined(e, lines, ind)
                self._assert_nested_eq(e, scope, lines, ind)
                lines.append(f"{ind}{name} = {expr(e, scope[name][0])};")
            elif "return" in s:
                rname, e = s["return"]
                assert rname == self.task["returns"][0]["name"], \
                    f"return names {rname}, expected {self.task['returns'][0]['name']}"
                self._assert_defined(e, lines, ind)
                self._assert_nested_eq(e, scope, lines, ind)
                rvty = _vty(self.task["returns"][0]["type"])
                if wrap is None:
                    lines += self._nonlinear_ensures_bridge(e, ind)
                    lines.append(f"{ind}return {expr(e, rvty)};")
                else:
                    lines.append(f"{ind}return (true, {expr(e, rvty)}, {wrap});")
            elif "var" in s:
                v = s["var"]
                self._assert_defined(v["init"], lines, ind)
                self._assert_nested_eq(v["init"], scope, lines, ind)
                vt = _vty(v["type"])
                scope[v["name"]] = (vt, True)
                self.local_inits[v["name"]] = v["init"]
                lines.append(f"{ind}let mut {v['name']}: {vt}"
                             f" = {expr(v['init'], vt)};")
                if _uses_strlib(self.task):
                    base = _full_slice_copy_var(v["init"])
                    if base is not None:
                        lines.append(f"{ind}assert({v['name']} =~= {base});")
            elif "if" in s:
                c = s["if"]
                self._assert_defined(c["cond"], lines, ind)
                lines.append(f"{ind}if {expr(c['cond'])} {{")
                lines += self.stmts(c["then"], dict(scope), ind + "    ", wrap)
                if c["else"]:
                    lines.append(f"{ind}}} else {{")
                    lines += self.stmts(c["else"], dict(scope), ind + "    ", wrap)
                lines.append(f"{ind}}}")
            elif "while" in s:
                lines += self.loop(s["while"], scope, ind, wrap)
            else:
                raise ValueError(f"t v1 -> verus: unknown statement {s!r}")
        return lines

    # -- loops: proof mode has no while (measured), so the loop rule is  --
    # -- encoded as a recursive helper lemma; see module docstring.      --
    def loop(self, w: dict, scope: dict, ind: str,
             wrap: str | None = None) -> list[str]:
        k = self.loop_ix
        self.loop_ix += 1
        invs = w.get("invariants", [])
        cond, dec = w["cond"], w["decreases"]

        # DIVISOR-BOUND EXIT WIDTH (2026-09-11, ROADMAP 16.2, divisor-bound
        # item, see `_divisor_bound_target`'s own docstring near
        # `t_divisor_bound_verus_defs` below): where the task matches the
        # trial-divide-to-half shape, the exit needs `i <= n/2 + 1` -- a
        # fact the task's own invariants never state but the loop body
        # implies (the recursive call only fires under the guard `i <=
        # n/2`, so the next `i` never exceeds `n/2 + 1`; the base case
        # `i == 2` satisfies it whenever `n >= 2`). Added here as an
        # ordinary EXTRA invariant, proved by the same invariant-
        # preservation VC every other invariant already gets (plain
        # linear arithmetic, no nonlinear_arith bridge needed) -- never a
        # task invariant, never weakening or restating one. A task with
        # no such shape gets `_divisor_bound_target` returning `None` and
        # this is a no-op, so every other loop's `invs` is unaffected.
        _dbt = _divisor_bound_target(self.task, w)
        if _dbt is not None:
            _n_bound = {"op": "+", "args": [
                {"op": "div", "args": [_dbt["dividend"], {"int": 2}]},
                {"int": 1}]}
            invs = invs + [{"op": "<=",
                             "args": [{"var": _dbt["i_name"]}, _n_bound]}]

        # GUARD DEFINEDNESS (2026-09-09, the residual COVERAGE-lifted-785.md
        # names: a `div`/`mod` in a loop guard -- `cond` or `decreases` --
        # is a definedness obligation neither of these two shared no-op
        # `TRUE` conditions the check used to require. `cond` and
        # `decreases` are each evaluated once per call of the recursive
        # helper below (`cond` by the `if` at its top, `decreases` by
        # Verus's own termination check over the same call), so their
        # combined obligation is asserted as the FIRST statement of the
        # helper body -- see `guard_pre` near the helper's own text --
        # which covers every evaluation, including the very first, since
        # even the outermost call site runs through this same body. That
        # assert is discharged from the helper's own `requires` (every
        # invariant already in scope there, see `req_clauses` below), the
        # identical mechanism an ordinary statement's `_assert_defined`
        # already uses; no separate wf lemma is needed since this is a
        # statement position, not a declarative one, and no call-site
        # change is needed either, since the assert lives inside the
        # callee. Trivial for every previously committed loop task
        # (`is_prime` included: its guard is `i * i <= n`, no div/mod) so
        # `guard_ob` there stays `TRUE` and nothing is emitted, keeping
        # `is_prime`, `first_even` and `tail` byte-identical.
        guard_ob = _conj([defined(cond), defined(dec)])
        guard_lines: list[str] = []
        if guard_ob != TRUE:
            guard_lines.append(f"    assert({expr(guard_ob)});")
        gd_pairs: dict[tuple[str, str], tuple[dict, dict]] = {}
        for e in (cond, dec):
            for x, y in _div_mod_pairs(e):
                gd_pairs.setdefault((expr(x), expr(y)), (x, y))
        for x, y in gd_pairs.values():
            guard_lines.append(_div_mod_law(x, y, "    "))
        guard_pre = "".join(line + "\n" for line in guard_lines)

        # 2026-09-11 (ROADMAP 16.2, appendArrayToSeq/arrayToSeq/addLists/
        # squareElements/elementWiseDivide/getFirstElements/
        # smallestListLength/findSmallest -- all `invariant-drop#N`
        # cells this session measured verus unproved on). `h`, in
        # appendArrayToSeq's own body, is `let h = a.len();` -- a
        # body-local declared ONCE before the loop and never assigned
        # inside it, so `loop()` already threads it through as a
        # READ-ONLY helper parameter (below, in `ro`). What it carried
        # NO fact about is the relationship `h == a.len()` itself: the
        # task's own invariants state `i_v2 <= h` and separately
        # `i_v2 <= a.len()`, never `h == a.len()`, so the recursive
        # helper's `if (i_v2 < h) { assert(i_v2 < a.len()) ...`
        # (needed before indexing `a[i_v2]`) had no way to connect the
        # two and Verus reported "assertion failed" even though the
        # fact is true at every call (h is exactly as read-only as any
        # task param: computed once, in scope, never reassigned by the
        # loop). `_ro_defining_facts` recovers this the same way
        # `req_clauses`/`inv_ctx` already recover a task-level
        # `requires`: an EXTRA true premise threaded into the helper,
        # not a restatement of the task's own contract. Restricted to
        # locals whose initializer mentions only OTHER read-only names
        # (never a loop-state variable, which could actually change) so
        # every fact added is provably an invariant of the recursion,
        # not an assumption. Measured 2026-09-11: all eight cells above
        # move unproved -> verified/refuted.
        assigned = _assigned(w["body"]) - _declared(w["body"])
        state = [n for n in scope if scope[n][1] and n in assigned]
        ro = [n for n in scope if n not in state]
        ro_facts = _ro_defining_facts(ro, self.local_inits)

        # invariant k may assume invariants 1..k-1 (SPEC.md definedness),
        # and, 2026-09-11 (ROADMAP 16.2, same cause as req_clauses below),
        # the task's own `requires`: an invariant's definedness can depend
        # on a read-only parameter fact true for the whole task (b[i]!=0
        # for every i, a.len()==b.len()) that is never itself restated as
        # an invariant. Without it the wf lemma for elementWiseDivision's
        # own invariant (forall k<i_v2, result[k]==a[k]/b[k], defined only
        # when b[k]!=0) had no way to see b[k]!=0 and Verus reported
        # "assertion failed" on the wf lemma even after req_clauses below
        # carried the same fact into the loop helper itself. Measured
        # 2026-09-11: elementWiseDivision, subtractSequences,
        # elementWiseSubtraction, multiplyElements, elementWiseModulo,
        # removeElement all needed this addition too (req_clauses alone
        # was not enough); harmless where unused, same reasoning as
        # req_clauses' own note.
        allvars = [(n, t) for n, (t, _m) in scope.items()]
        inv_ctx = list(self.task.get("requires", [])) + ro_facts
        for j, iv in enumerate(invs):
            self._wf_lemma(f"t_wf_{self.name}_l{k}_inv{j}", allvars,
                           inv_ctx + invs[:j], defined(iv))

        assert state, "loop body assigns nothing in scope, not lowerable"

        if len(state) == 1:
            state_ty = scope[state[0]][0]
            res_val = state[0]
        else:
            state_ty = "(" + ", ".join(scope[v][0] for v in state) + ")"
            res_val = "(" + ", ".join(state) + ")"

        # EARLY EXIT (2026-09-08, SPEC.md "Early exit"). A `return` inside
        # this loop's body -- directly, in an `if`, or through a nested
        # loop's already-wrapped result -- means one call of the recursive
        # helper can end the whole TASK instead of one more iteration, so
        # its result can no longer be just the state tuple: it becomes
        # (t_res.0: bool, did this call return?; t_res.1: the task's return
        # value if so; t_res.2: the loop state tuple if not). The ensures
        # splits the same way: on the return branch the task owes its own
        # `ensures` (substituting the return name), never the invariants,
        # exactly as SPEC.md states; on the other branch it owes
        # invariants + negated guard as before. Measured (probe_ret_proof.rs,
        # 2026-09-08): Verus accepts a native `return` inside a recursive
        # `proof fn` and checks the ensures at that exit with no
        # loop-invariant obligation -- the same rule probe_ret_exec.rs shows
        # for a native `while` in an exec fn with a named return.
        may_ret = _may_return(w["body"])
        base = "t_res.2" if may_ret else "t_res"
        if len(state) == 1:
            m = {state[0]: base}
        else:
            m = {v: f"{base}.{j}" for j, v in enumerate(state)}

        if may_ret:
            rname = self.task["returns"][0]["name"]
            rtty = self.task["returns"][0]["type"]
            rtype = _vty(rtty)
            res_ty = f"(bool, {rtype}, {state_ty})"
            m_ret = {rname: "t_res.1"}
            ens = ([f"t_res.0 ==> {expr(subst(en, m_ret))}"
                    for en in self.task["ensures"]]
                   + [f"(!t_res.0) ==> {expr(subst(iv, m))}" for iv in invs]
                   + [f"(!t_res.0) ==> (!{expr(subst(cond, m))})"])
            base_val = f"(false, {_dummy(rtty)}, {res_val})"
            # The return branch owes the task's OWN `ensures`, which may
            # read the task's `requires` (e.g. a bound on a parameter), so
            # those go into the helper's own requires alongside the
            # invariants; harmless when unused, since they hold at every
            # call site (established once at task entry, never reassigned).
            req_clauses = list(self.task.get("requires", [])) + ro_facts + invs
        else:
            res_ty = state_ty
            ens = ([expr(subst(i, m)) for i in invs]
                   + [f"(!{expr(subst(cond, m))})"])
            base_val = res_val
            # 2026-09-11 (ROADMAP 16.2, verus column): a loop body can carry
            # a proof obligation -- elementWiseDivision's b[i_v2] != 0
            # before the division, subtractSequences'/removeElement's
            # same-length index facts -- that follows only from the TASK's
            # own `requires` on a read-only parameter (a.len() == b.len(),
            # 0 <= k < s.len()), never restated as a loop invariant because
            # it is already true of every element, not just the ones seen
            # so far. The may_ret branch above already threads
            # self.task["requires"] into the helper for exactly this
            # reason; this branch used to omit it, so the recursive helper
            # had no way to know a precondition true at every call site
            # (ro parameters are never reassigned) and Verus reported
            # "assertion failed" for those obligations even though the
            # kernel had unconditionally true facts available at the
            # call. Measured 2026-09-11: elementWiseDivision (261),
            # subtractSequences (273), elementWiseSubtraction (282),
            # multiplyElements (445), elementWiseModulo (616) and
            # removeElement (610) all move unproved -> verified with this
            # one-line change; no other of the 34 committed verus cells
            # regresses (same requires were already true, just unused).
            req_clauses = list(self.task.get("requires", [])) + ro_facts + invs
        ens_s = ",\n        ".join(ens)

        hname = f"t_lp_{self.name}_{k}"
        ps = ", ".join(f"{n}: {scope[n][0]}" for n in ro + state)
        req = ""
        if req_clauses:
            req = ("    requires\n        "
                   + ",\n        ".join(expr(i) for i in req_clauses) + ",\n")

        # Invariants with nonlinear terms need Verus's sanctioned escape
        # hatch, assert ... by (nonlinear_arith) with explicit premises,
        # because the default solver profile has nonlinear arithmetic off
        # (measured; Dafny's does not). The premises are exactly t's
        # preservation rule: all invariants plus the guard at entry; the
        # conclusion is the invariant over the symbolic post-state. `_sym`
        # gives up (None) when the body may return, same as a nested while,
        # so this is skipped in that case; see `_sym`'s docstring.
        nl = [j for j, iv in enumerate(invs) if _has_nonlinear(iv)]
        old_lets, bridge = "", []
        if nl:
            entry = {v: {"var": f"t_old_{v}"} for v in state}
            env = _sym(w["body"], entry)
            if env is not None:
                old_lets = "".join(f"    let t_old_{v} = {v};\n"
                                   for v in state)
                # 2026-09-11 (ROADMAP 16.2, squareElements): `ro_facts`
                # (e.g. `h == a.len()`) are never substituted by `entry`
                # -- they are about READ-ONLY names the loop body cannot
                # change, true identically before and after one
                # iteration -- so they are appended unsubstituted,
                # exactly like `invs`/`cond` are substituted because
                # THEY range over STATE. Without this, the goal's own
                # `a[t_old_i_v]` (an index bound by `h`, not directly by
                # `a.len()`) had no bridge from `h` to `a.len()` inside
                # this specific nonlinear_arith block (req_clauses/inv_ctx
                # above cover every OTHER obligation in the helper, but
                # this bridge builds its own separate `requires` list).
                prem = ",\n                ".join(
                    [expr(subst(p, entry)) for p in invs + [cond]]
                    + [expr(f) for f in ro_facts])
                bridge = [
                    f"        assert({expr(subst(invs[j], env))})"
                    " by (nonlinear_arith)\n"
                    f"            requires\n                {prem},\n"
                    "        ;"
                    for j in nl]

        hscope = {n: (scope[n][0], n in state) for n in ro + state}
        inner = self.stmts(w["body"], hscope, "        ",
                            res_val if may_ret else None) + bridge
        shadows = "".join(f"    let mut {v} = {v};\n" for v in state)
        args = ", ".join(ro + state)
        self.helpers.append(
            f"proof fn {hname}({ps}) -> (t_res: {res_ty})\n"
            f"{req}    ensures\n        {ens_s},\n"
            f"    decreases ({expr(dec)}) + (2int),\n"
            "{\n"
            f"{old_lets}{shadows}{guard_pre}"
            f"    if {expr(cond)} {{\n"
            + "\n".join(inner) + "\n"
            f"        {hname}({args})\n"
            "    } else {\n"
            f"        {base_val}\n"
            "    }\n"
            "}\n")

        tmp = f"t_tmp{k}"
        lines = [f"{ind}let {tmp} = {hname}({args});"]
        if may_ret:
            if wrap is None:
                lines.append(f"{ind}if {tmp}.0 {{ return {tmp}.1; }}")
            else:
                lines.append(
                    f"{ind}if {tmp}.0 {{ return (true, {tmp}.1, {wrap}); }}")
            if len(state) == 1:
                lines.append(f"{ind}{state[0]} = {tmp}.2;")
            else:
                lines += [f"{ind}{v} = {tmp}.2.{j};" for j, v in enumerate(state)]
            # DIVISOR-BOUND CALL (2026-09-11, ROADMAP 16.2): reached only
            # when `t_tmp{k}.0` was false (the early return above already
            # took the other path), i.e. exactly the loop's own normal
            # exit -- the one place `result`/`i` carry only the `[lo, i)`
            # fact and the task's `ensures` needs the wider `[lo, n)`
            # one. `wrap is None` restricts this to the outermost loop
            # (every task this shape matches has exactly one, un-nested).
            if (wrap is None and _dbt is not None
                    and _dbt["result"] in state and _dbt["i_name"] in state):
                self.helpers.append(
                    _divisor_bound_verus_defs(self.name, _dbt))
                n_render = expr(_dbt["dividend"])
                lines.append(
                    f"{ind}t_divisor_bound_{self.name}"
                    f"({n_render}, {_dbt['i_name']}, {_dbt['result']});")
        else:
            if len(state) == 1:
                lines.append(f"{ind}{state[0]} = {tmp};")
            else:
                lines += [f"{ind}{v} = {tmp}.{j};" for j, v in enumerate(state)]
        return lines

    # -- whole task ------------------------------------------------------
    def emit(self, body: list) -> str:
        task = self.task
        params = [(p["name"], _vty(p["type"])) for p in task["params"]]
        rname = task["returns"][0]["name"]
        rtype = _vty(task["returns"][0]["type"])
        reqs = task.get("requires", [])
        enss = task["ensures"]

        # spec fns and their (universal) definedness lemmas. SPEC.md gate 3
        # restricts a spec_fun's own params/result to "int"|"seq"/"int"|
        # "bool" (never a pair), so `_vty` here only ever resolves a base
        # type name; it is used anyway for one lookup path instead of two.
        spec_blocks = []
        for f in task.get("spec_funs", []):
            fps = ", ".join(f"{p['name']}: {_vty(p['type'])}"
                            for p in f["params"])
            if defined(f["decreases"]) != TRUE:
                raise NotImplementedError(
                    "verus: definedness obligation on spec_fun decreases "
                    "not implemented")
            spec_blocks.append(
                f"spec fn {f['name']}({fps}) -> {_vty(f['result'])}\n"
                f"    decreases {expr(f['decreases'])},\n"
                "{\n"
                f"    {expr(f['body'])}\n"
                "}\n")
            self._wf_lemma(f"t_wf_{self.name}_fn_{f['name']}",
                           [(p["name"], _vty(p["type"]))
                            for p in f["params"]],
                           _spec_fn_domain_context(f), defined(f["body"]))

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

        # THE STRING LIBRARY (v1, 2026-09-11): the split-join law is not
        # free (`STRLIB_PRELUDE`'s own dated note), so a task whose
        # ensures states it gets one lemma call per distinct (s, c) pair
        # PREPENDED to its own proof fn body -- the lemma's `ensures`
        # then stands as an established fact for the rest of the proof,
        # same technique the well-formedness lemmas already use (call a
        # separately-proved fact into scope rather than re-deriving it).
        for s_e, c_e in _split_join_witnesses(task):
            main_lines = ([f"    t_lemma_split_join_law({expr(s_e)}, {expr(c_e)});"]
                          + main_lines)

        # ROTATE-LEFT (2026-09-11, ROADMAP 16.2, see `_rotate_witnesses`
        # and `ROTATE_PRELUDE`'s own docstrings): a task whose ensures
        # states the rotate-left indexing law gets the lemma call
        # prepended the same way the split-join law does, one call per
        # distinct (L, N) pair.
        for l_e, n_e in _rotate_witnesses(task):
            main_lines = ([f"    t_lemma_rotate_left({expr(l_e)}, {expr(n_e)});"]
                          + main_lines)

        # THE STRING LIBRARY (v1, 2026-09-11): two more facts an ensures
        # can need that neither `count`'s nor `split`'s own definition
        # hands over for free -- `count(s, t) >= 0` (measured, `f_v1strlib`'s
        # own `count_pattern` shape states it directly) and SPEC.md's own
        # split-length law, `len(s.split(c)) == s.count([c]) + 1`
        # (`split_row`'s `len` variant) -- each found the same way the
        # split-join law is (an AST witness restricted to params-only
        # arguments) and prepended the same way, harmless when unused
        # (an unused `ensures` fact costs nothing, the same property
        # `STRLIB_PRELUDE`'s own docstring already measured for an
        # unreferenced `spec fn`).
        for s_e, t_e in _param_restricted_witnesses(task, "count", 2):
            main_lines = ([f"    t_lemma_count_nonneg({expr(s_e)}, {expr(t_e)});"]
                          + main_lines)
        for s_e, c_e in _param_restricted_witnesses(task, "split", 2):
            main_lines = ([f"    t_lemma_split_len_law({expr(s_e)}, {expr(c_e)});"]
                          + main_lines)

        # TOP-LEVEL NONLINEAR ENSURES (2026-09-10, see
        # `_nonlinear_ensures_bridge`'s own docstring), the implicit-return
        # site: a body with no `return` statement ends via the trailing
        # `{rname}` expression below, so the bridge (already built into the
        # explicit "return" case in `stmts`) belongs here instead, using
        # `_sym`'s closed form for rname's final value -- None (skipped,
        # left to whichever `return` statement the body DOES have) when the
        # body contains one, or a `while` (per `_sym`'s own docstring); a
        # committed task with no nonlinear ensures never calls `_sym` here
        # at all (the `any(...)` guard), so this costs nothing additive.
        if any(_has_nonlinear(en) for en in enss):
            final_env = _sym(body, {})
            if final_env is not None and rname in final_env:
                main_lines += self._nonlinear_ensures_bridge(
                    final_env[rname], "    ")

        # CONCRETE STRING-LIBRARY LITERALS (2026-09-11, see
        # `_strlib_ground_bridge`'s own docstring): the same implicit-
        # return site as the nonlinear bridge just above, guarded by
        # `_uses_strlib` instead of `_has_nonlinear` so a task with no
        # string-library call (all 23 previously committed/measured
        # non-string tasks) never calls `_sym` here either.
        #
        # REAL ONLY (measured 2026-09-11): a TWIN whose ensures reads
        # false at this same ground literal turned this bridge's own
        # assert into the failure -- verus reports "expression simplifies
        # to false == true" on the bridge's line, not the "postcondition
        # not satisfied" the twin's own function is supposed to fail
        # with, so verifiers/verus.py's classifier (which wants that
        # exact failure on the ORIGINAL fn, plus the SEPARATE
        # t_refutation_certificate block succeeding) reads TOOL_ERROR /
        # MALFORMED instead of the REFUTED the twin's own certificate
        # mechanism (`_certificate` above) already mints correctly on its
        # own. `lower()` gives the real body the SAME object identity as
        # `task["body"]` (a twin body is always a freshly renamed copy,
        # `names.rename_body`'s own return), so that identity check is
        # what this file already uses (`twin_body = body if body is not
        # task.get("body") else None`) to tell the two cases apart, one
        # level up; this reads the same fact.
        if _uses_strlib(task) and body is task.get("body"):
            final_env = _sym(body, {})
            if final_env is not None and rname in final_env:
                main_lines += self._strlib_ground_bridge(
                    final_env[rname], "    ")

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

        strlib_blocks = [STRLIB_PRELUDE] if _uses_strlib(task) else []
        rotate_blocks = [ROTATE_PRELUDE] if _rotate_witnesses(task) else []
        blocks = (strlib_blocks + rotate_blocks + spec_blocks + self.wf
                  + self.helpers + [main])
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
#   undefined (2026-09-09, SPEC.md "Sequences as values"): the twin has no
#     value at the witness because some statement's right-hand side hit a
#     partial operator (`at`, `update`, `fill`, `div`, `mod`) outside its
#     domain before any `ensures` instance could even be stated, so there
#     is nothing to substitute the return name with. What IS ground and
#     checkable is the operator's own definedness obligation, which this
#     lowering's `defined()` already computes for every honest assert it
#     emits: requires holds at the witness, and that same obligation,
#     re-evaluated with interp.ev over the SAME statements in the SAME
#     order interp.py walked to raise the Undef that minted this witness
#     kind, is false. `_undef_obligation` below does the walk and returns
#     the first such false obligation, ground-substituted; None (no
#     certificate, an honest unproved) on an `if`, `while`, or `return`
#     before the failing statement, or if the walk disagrees with the
#     witness and finds nothing false.
# Bounded quantifiers whose bounds are ground after witness substitution
# are unrolled here (finite conjunction/disjunction over the concrete
# range, capped) because compute_only cannot evaluate int quantifiers; the
# formula the kernel checks is fully ground. Anything outside these rules
# returns None and no certificate is emitted: a missing or rejected
# certificate can only cost a flip (UNPROVED), never fake one.

CERT_NAME = "t_refutation_certificate"
_UNROLL_CAP = 64


def _tlit(v, ty=None):
    """A measured witness value as a t literal expression.

    Two call shapes reach this, and only one of them is ambiguous. Raw
    interp.py runtime values (interp.exit_env's post-state,
    _undef_obligation's interp.ev results) carry their own t type in the
    Python type itself: an interp.Pair is unmistakably a pair, a tuple is
    unmistakably a seq, so those two cases below need no `ty` and are
    handled first regardless of it. A witness dict's own values (built by
    interp._j for JSON) have already lost that distinction on purpose --
    SPEC.md "Pairs" (2026-09-10)/interp.py's `_j`: a Pair prints AS a
    2-list, "so a seq component ... prints as a list too rather than as a
    raw tuple" -- so a pair of two ints is INDISTINGUISHABLE, as plain
    JSON, from a length-2 seq of ints. Both divmod_pair's and min_max's own
    measured witnesses hit exactly this shape (`_real`/`_twin`: `[1, 0]`,
    `[0, 1]`, `[1, 1]`), so this is not a hypothetical: `_cert_formula`
    passes the value's declared t type (a param's or the return's, the
    only ones it tracks) whenever it has one, and only the untyped
    fallback below (an int list defaults to a seq, correct for every
    call site that predates pairs) is a guess.

    (SPEC.md "Nested sequences", 2026-09-10) adds a THIRD ambiguity, one
    level up from the Pair/seq one: a nested seq's runtime value is a
    tuple of tuples (interp.py), and a NONEMPTY one is unambiguous by its
    own shape alone -- its first element is itself a tuple/list, which a
    plain flat seq's never is -- so it needs no `ty` either, same posture
    as interp.Pair and a flat tuple above. Only the EMPTY case collides:
    `()` (or `[]`, JSON-decoded) is indistinguishable, by shape, from an
    empty flat seq, exactly the shape of the Pair/seq collision one type
    down, so THAT one case alone asks `ty`. swap_rows' own measured
    witness is exactly this shape (`m = [[]]`, an outer seq of one row,
    that row empty) -- the outer literal is nonempty (one row) so is read
    off its own shape, and the inner empty row is the flat-seq empty case,
    already handled below with no `ty` needed since a row's own type
    ("seq", never a dict) never reaches this ambiguity."""
    if isinstance(v, interp.Pair):
        t1, t2 = (ty["pair"] if isinstance(ty, dict) and "pair" in ty
                  else (None, None))
        return {"op": "pair", "args": [_tlit(v.a, t1), _tlit(v.b, t2)]}
    if isinstance(v, tuple):
        nested_ty = isinstance(ty, dict) and "seq" in ty
        if not v:
            return {"_nested_seq": []} if nested_ty else {"_seq": []}
        if isinstance(v[0], tuple):
            rows = []
            for row in v:
                if not all(isinstance(x, int) and not isinstance(x, bool)
                           for x in row):
                    raise ValueError(f"witness value {v!r} has no t literal")
                rows.append({"_seq": list(row)})
            return {"_nested_seq": rows}
        if not all(isinstance(x, int) and not isinstance(x, bool) for x in v):
            raise ValueError(f"witness value {v!r} has no t literal")
        return {"_seq": list(v)}
    if isinstance(ty, dict) and "pair" in ty:
        t1, t2 = ty["pair"]
        a, b = v
        return {"op": "pair", "args": [_tlit(a, t1), _tlit(b, t2)]}
    if isinstance(v, bool):
        return {"bool": v}
    if isinstance(v, int):
        return {"int": v}
    if isinstance(v, list):
        nested_ty = isinstance(ty, dict) and "seq" in ty
        if not v:
            return {"_nested_seq": []} if nested_ty else {"_seq": []}
        if all(isinstance(x, list) for x in v):
            rows = []
            for row in v:
                if not all(isinstance(x, int) and not isinstance(x, bool)
                           for x in row):
                    raise ValueError(f"witness value {v!r} has no t literal")
                rows.append({"_seq": list(row)})
            return {"_nested_seq": rows}
        if all(isinstance(x, int) and not isinstance(x, bool) for x in v):
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
    if op == "len" and len(args) == 1 and "_nested_seq" in args[0]:
        # SPEC.md "Nested sequences" (2026-09-10): the outer row count,
        # needed to unroll a `forall k in [0, len(m))` bound once `m` has
        # been substituted by its ground witness (row_max_len's own
        # ensures, both quantifiers). One row's own `len` (a "_seq" node
        # by then, from the row's own ground rendering) is already covered
        # by the case above.
        return len(args[0]["_nested_seq"])
    if op == "neg" and len(args) == 1:
        return -_gint(args[0])
    if op in ("+", "-", "*") and len(args) == 2:
        a, b = _gint(args[0]), _gint(args[1])
        return a + b if op == "+" else (a - b if op == "-" else a * b)
    if op in ("div", "mod") and len(args) == 2:
        # Same Euclidean rule as interp.py's ev() for "div"/"mod": the
        # unique q, r with a == q*b + r and 0 <= r < |b|. b == 0 is
        # undefined (SPEC.md), so it refuses rather than fabricating a
        # bound, the same fail-closed posture as every other case here.
        a, b = _gint(args[0]), _gint(args[1])
        if b == 0:
            raise ValueError("quantifier bound: division by zero")
        r = a % abs(b)
        return r if op == "mod" else (a - r) // b
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


def _to_py(v, ty=None):
    """The inverse of interp.py's `_j`: a witness value already JSON-decoded
    (an int, a bool, or a plain list) rebuilt into the runtime shape
    interp.ev expects (a tuple for a seq, an interp.Pair for a pair), using
    the same declared-type disambiguation `_tlit` needs and for exactly the
    same reason (SPEC.md "Pairs", 2026-09-10: a pair's own 2-list shape,
    from interp.py's `_j`, collides with a length-2 seq's). Without `ty`
    (a local's type is not tracked past this point, see `_undef_obligation`)
    a list defaults to a seq, the untyped guess every pre-Pairs caller of
    this shape already relied on.

    (SPEC.md "Nested sequences", 2026-09-10): {"seq": "seq"} rebuilds each
    row through this same function at the row's own type ("seq", a plain
    string), which hits the plain `list` fallback below and so becomes a
    tuple, not left as a list -- interp.ev's own nested-seq representation
    is a tuple of TUPLES (interp.py, `_j`'s docstring), and a tuple of
    lists is a different Python value that would silently fail every
    tuple-identity/equality check interp.ev does on it."""
    if isinstance(ty, dict) and "pair" in ty:
        t1, t2 = ty["pair"]
        a, b = v
        return interp.Pair(_to_py(a, t1), _to_py(b, t2))
    if isinstance(ty, dict) and "seq" in ty:
        return tuple(_to_py(row, "seq") for row in v)
    if isinstance(v, list):
        return tuple(v)
    return v


def _ensures_undef_obligation(task: dict, m: dict, names: dict,
                               tmap: dict | None = None,
                               ret_val=None) -> dict | None:
    """2026-09-12 (ROADMAP item "verus: the four ensures-level probes"):
    the ENSURES-LEVEL sibling of `_undef_obligation` above. The shape this
    guards against is `fz_p_at_oob`/`fz_p_at_neg`/`fz_p_at_zero`/
    `fz_p_attotal` (t/fuzz_lower.py): `s[len(s)]` (or `s[-1]`) appears only
    in `ensures`, never in the body, so the REAL body always returns a
    value and the twin obligation `_undef_obligation` walks (a twin BODY
    statement with no value) never fires -- the violation is in the
    postcondition's own definedness, not the body's.

    The intended input is harness.real_witness's own "_kind": "undefined",
    "_site": "ensures" shape (this module's docstring section above,
    2026-09-12): the witness IS a real-body undefined-ness, but sited in
    ensures rather than the body, with "_expr" naming the offending
    subexpression directly. That harness.real_witness change is not in
    this worktree (confirmed 2026-09-12: `harness.real_witness` here has
    no "_site"/"_expr" keys at all, grep found none), so `_cert_formula`'s
    "value" branch is where this actually gets exercised today: for these
    four probes, `Reference._breaks_ensures` (interp.py) catches the
    ensures-eval `Undef` and reports it as "breaks ensures" (its own
    docstring: "an ensures with no value is not satisfied"), so
    `real_witness` hands back a "_kind": "value", "_ens": True witness
    whose real and twin values are equal (there is no twin here at all --
    "_twin" is just `interp._j(got)`, the SAME concrete value `_real` is).
    Substituting that witness straight into "not ensures[m2]" as the
    "value" branch normally does re-embeds `s[len(s)]` unresolved into the
    certificate, which is not a certificate: Verus's `compute_only` cannot
    reduce an out-of-bounds `Seq::index`, so the real column read
    "unproved" (measured 2026-09-12, see this file's dated note below).
    This function is the fix, called FIRST from the "value" branch: it
    tries evaluating the ensures conjunction at the witness's own values
    with interp.ev (the same interpreter every other obligation in this
    file already trusts), and only when THAT raises interp.Undef -- the
    ensures itself has no value here, not merely a false one -- does it
    return a certificate at all, so a genuine value-differs-from-spec
    witness (every other "value" witness this file has ever measured)
    still falls through to the ordinary "not ensures[m2]" certificate
    unchanged.

    The certificate itself is `not(defined(ensures conjunction))`,
    substituted at `m` exactly as `_undef_obligation`'s twin-body
    obligation is substituted: `defined()` (this file's own function,
    used for every other definedness obligation this lowering emits) on
    an `at`/`slice`/`div`/`mod` node produces exactly the guarded bound
    the task instructions describe (`0 <= i < len(s)` for `at`, the
    analogous bound for `slice`, `y != 0` for `div`/`mod`) -- there is no
    second, independent notion of "definedness" introduced here, and no
    need to locate "_expr" by hand: `defined()` already walks the WHOLE
    ensures conjunction and short-circuits (via `_guard`) exactly where
    SPEC.md says a boolean connective's later operand's definedness lives
    "under" the earlier ones, so the single formula it returns already IS
    the obligation of whichever subexpression is guilty.

    `ret_val` (measured 2026-09-12, fz_p_attotal): the RETURN var's own
    witness value, needed here even though this obligation is not ABOUT
    the return value, because `defined()`'s "and"/"or"/"implies" cases
    guard a LATER clause's obligation on the FULL earlier clause (`_guard`
    below is called with the clause `a` itself, not `defined(a)`) --
    exactly interp.ev's own short-circuit "and"/"implies" order, per
    SPEC.md. fz_p_attotal's first two ensures clauses are
    `len(s)>0 ==> r==1` and `len(s)==0 ==> r==0`; both mention `r`, so
    `interp.ev`-ing them (both to decide the short-circuit AND to decide
    which `defined()` guard fires) needs `r` bound, even though `r` never
    appears in the actual undefined subexpression (`s[len(s)]`). Without
    it this function raised a SPURIOUS `interp.Undef` ("unbound r") on the
    very first `interp.ev(ens_conj, ...)` probe below -- which this
    function's own `except interp.Undef: pass` swallowed as if it were
    the genuine ensures-undefined case -- and then failed the same way a
    second time evaluating `ob` itself, landing in the final
    `except (interp.Undef, ...): return None`, so this function silently
    returned None and fz_p_attotal fell through to the ordinary
    "not ensures[m2]" certificate (which IS sound and was already REFUTED
    for the other three probes here, but for fz_p_attotal re-embeds the
    same unresolved `s[len(s)]` and reads "unproved", confirmed via
    /tmp scratch measurement before this fix)."""
    env_py = {n: _to_py(v, tmap.get(n) if tmap else None)
              for n, v in names.items()}
    ret_name = task["returns"][0]["name"]
    if ret_val is not None:
        env_py[ret_name] = _to_py(ret_val, tmap.get(ret_name) if tmap else None)
    funs = interp.funs_of(task, task["body"])
    st = interp.St()
    ens_conj = _conj(task["ensures"])
    try:
        interp.ev(ens_conj, env_py, funs, st)
        return None                # ensures evaluated cleanly: not this case
    except interp.Undef:
        pass
    except (interp.Budget, RecursionError):
        return None
    ob = defined(ens_conj)
    if ob == TRUE:
        return None                 # defined() found nothing to blame
    try:
        if interp.ev(ob, env_py, funs, st):
            return None             # defined() disagrees with the Undef above: refuse
    except (interp.Undef, interp.Budget, RecursionError):
        return None
    return {"op": "not", "args": [subst(ob, m)]}


class _GiveUp(Exception):
    """Internal signal only (2026-09-10): `_undef_obligation`'s walk met a
    `return` (or any statement it does not know), so replay cannot say
    what runs next -- caught by the same handler as `interp.Undef`/
    `interp.Budget`/`RecursionError`, all four meaning the identical
    thing to the caller: refuse, do not guess."""


def _undef_obligation(task: dict, twin_body: list, m: dict, names: dict,
                       tmap: dict | None = None) -> dict | None:
    """The negated definedness obligation of the twin body's first
    statement that has none, ground-substituted at the witness (SPEC.md
    "Sequences as values", 2026-09-09; see the "undefined" entry in the
    section comment above). Re-walks `twin_body` with interp.ev, in the
    SAME left-to-right, iteration-by-iteration order interp.py's own
    exec_body used to raise the Undef that minted this witness in the
    first place, so the statement this finds is the same one interp.py
    found; `defined()` is the identical function this lowering already
    trusts for every honest assert it emits, so there is no second,
    independent reading of what "defined" means. `m` (var name -> t
    literal) and `env_py` (var name -> Python value, the tuples-for-seqs
    form interp.ev itself uses) both grow as the walk proceeds, so a later
    statement's own obligation (`swap`'s off-by-one twin fails on its very
    first statement, so no committed task yet exercises this, but the
    mechanism is not special-cased to the first) sees the concrete values
    of every name the twin already bound.

    LOOP AND IF BODIES (2026-09-10, t/COVERAGE-lifted-785.md's own
    residual, this file's "LEFT, BY NAME" module-docstring entry above,
    and the v1def fuzz family's 033/049/143): this walk used to give up
    (return None) the moment it met an `if` or `while` BEFORE the failing
    statement, which read fz_v1nested_069's and fz_v1nested_150's
    boundary-widening twins (the bad access one iteration inside the
    loop's own body) and fz_v1def_033/049/143's collapse-if twins (the
    bad access is the COND of the `if` collapse-if left behind, once the
    guard that used to protect it is gone) as "verus unproved" rather than
    "REFUTED". Confirmed before fixing, not assumed: reading the three
    v1def twins' committed `.rs` showed COLLAPSE-IF replacing the outer
    `if (0<=x && x<len(s)) {...}` with its own then-branch UNWRAPPED, so
    the twin body's new top level is a single `if` whose OWN cond is
    `s[x] >= 0` -- undefined outside `[0,len(s))` -- never an assign or
    var this walk used to look for at all. So `walk` now recurses: an
    `if`'s cond is checked exactly like any other expression (`check`
    below) before the concrete guard value picks a branch to descend into;
    a `while`'s cond is checked the same way at the top of every
    iteration, in the SAME loop `interp.exec_body` itself runs (guard,
    body, guard, body, ..., capped at `interp.MAX_LOOP` like every other
    concrete run in this codebase), so a body statement three iterations
    in is checked with the CONCRETE state that iteration actually reaches,
    not the entry state -- this is what SPEC.md means by a loop-body
    obligation living "under the loop's invariants and guard": the
    invariants and guard are exactly what makes that later state REACHABLE
    at all, and a concrete replay reaches it by literally running the
    twin, the same authority every other obligation in this function
    already has, no separate invariant-tracking needed. A `return` still
    ends the walk with nothing found (`_GiveUp`, above) -- SPEC.md's early
    exit is not part of this residual, and no committed or targeted task
    exercises a return inside a loop whose twin is this "undefined" kind.

    `tmap` (SPEC.md "Pairs", 2026-09-10), when given, is the declared type
    of every PARAM (and the return) -- `_cert_formula` builds it and passes
    it here -- so a pair-shaped param starts life in `env_py` as a real
    interp.Pair rather than the untyped guess (`_to_py`, `_tlit`: a bare
    list defaults to a seq). A local's own type is not tracked past this
    point, so a pair-typed LOCAL a later statement introduces still falls
    back to the guess; not exercised by any committed task (divmod_pair
    has no loop and no pair param, min_max's only pair is its return,
    assigned once after the loop, and neither task's measured twin is this
    "undefined" kind in the first place -- see the module docstring's
    "Pairs" entry)."""
    tmap = tmap or {}
    env_py = {n: _to_py(v, tmap.get(n)) for n, v in names.items()}
    m = dict(m)
    funs = interp.funs_of(task, twin_body)
    st = interp.St()

    def check(e: dict) -> dict | None:
        ob = defined(e)
        if ob != TRUE and not interp.ev(ob, env_py, funs, st):
            return {"op": "not", "args": [subst(ob, m)]}
        return None

    def walk(body: list) -> dict | None:
        for s in body:
            if "var" in s:
                name, e = s["var"]["name"], s["var"]["init"]
            elif "assign" in s:
                name, e = s["assign"]
            elif "if" in s:
                c = s["if"]
                found = check(c["cond"])
                if found is not None:
                    return found
                branch = (c["then"] if interp.ev(c["cond"], env_py, funs, st)
                          else (c.get("else") or []))
                found = walk(branch)
                if found is not None:
                    return found
                continue
            elif "while" in s:
                w = s["while"]
                it = 0
                while True:
                    found = check(w["cond"])
                    if found is not None:
                        return found
                    if not interp.ev(w["cond"], env_py, funs, st):
                        break
                    found = walk(w["body"])
                    if found is not None:
                        return found
                    it += 1
                    if it > interp.MAX_LOOP:
                        raise interp.Budget("loop cap")
                continue
            else:
                raise _GiveUp()
            found = check(e)
            if found is not None:
                return found
            val = interp.ev(e, env_py, funs, st)
            env_py[name] = val
            m[name] = _tlit(val)
        return None

    try:
        return walk(twin_body)
    except (interp.Undef, interp.Budget, RecursionError, _GiveUp):
        return None


def _cert_formula(task: dict, twin_body: list, w: dict) -> dict | None:
    kind = w.get("_kind")
    names = {k: v for k, v in w.items() if not k.startswith("_")}
    # SPEC.md "Pairs" (2026-09-10): every PARAM's and the RETURN's own
    # declared type, so `_tlit` can tell a pair's 2-list shape (interp.py's
    # `_j`) apart from a length-2 seq's -- both divmod_pair's and
    # min_max's own measured witnesses are exactly this shape (`_real`/
    # `_twin`: `[1, 0]`, `[0, 1]`, `[1, 1]`). A loop LOCAL's type is not
    # tracked here (this function does not reconstruct the loop's scope),
    # so a pair-typed local in an "exit"/"preservation"/"undefined"
    # witness still falls back to the untyped guess; not exercised by
    # either committed pair task (see `_tlit` and `_undef_obligation`).
    tmap = {p["name"]: p["type"] for p in task["params"]}
    ret_type = task["returns"][0]["type"]
    tmap[task["returns"][0]["name"]] = ret_type
    try:
        m = {n: _tlit(v, tmap.get(n)) for n, v in names.items()}
        parts = [subst(rq, m) for rq in task.get("requires", [])]
        if kind == "value":
            if w.get("_ens") is not True:
                return None      # a drift a sound kernel may still accept
            tw = w.get("_twin")
            if not isinstance(tw, (bool, int, list)):
                return None
            m2 = dict(m)
            m2[task["returns"][0]["name"]] = _tlit(tw, ret_type)
            # ENSURES-LEVEL undefined (2026-09-12, see
            # `_ensures_undef_obligation`'s own docstring): tried first,
            # since a witness in this shape whose ensures has NO VALUE at
            # all (fz_p_at_oob/at_neg/at_zero/attotal) is not soundly
            # certified by "not ensures[m2]" below -- that re-embeds the
            # same undefined subexpression unresolved. Every other "value"
            # witness measured before this date evaluates its ensures
            # cleanly and falls straight through unchanged.
            ens_ob = _ensures_undef_obligation(task, m2, names, tmap, ret_val=tw)
            if ens_ob is not None:
                parts.append(ens_ob)
            else:
                parts = [subst(rq, m2) for rq in task.get("requires", [])]
                parts.append({"op": "not", "args": [
                    _conj([subst(en, m2) for en in task["ensures"]])]})
        elif kind == "exit":
            loop = _twin_loop(task["body"], twin_body)
            if loop is None:
                return None
            # The obligation is at the RETURN: the loop-exit state run
            # through whatever follows the loop (interp.exit_env, which is
            # None under an enclosing loop, where the exit re-enters it). A
            # tail loop runs nothing and the formula is what it always was.
            # Measured 2026-09-07 (ROADMAP 12.5): slow_max assigns z after
            # its loop, and a certificate stating not-ensures at the loop's
            # own z minted REFUTED on a twin every kernel proves.
            ret = task["returns"][0]["name"]
            post = interp.exit_env(task, twin_body, loop, names)
            if post is None:
                return None
            m2 = dict(m)
            m2[ret] = _tlit(post[ret], ret_type)
            parts += [subst(iv, m) for iv in loop.get("invariants", [])]
            parts.append({"op": "not", "args": [subst(loop["cond"], m)]})
            parts.append({"op": "not", "args": [
                _conj([subst(en, m2) for en in task["ensures"]])]})
        elif kind == "undefined":
            if w.get("_site") == "ensures" and isinstance(w.get("_expr"), dict):
                # harness.real_witness's ensures-level shape (2026-09-12): the
                # postcondition's own definedness obligation fails at the
                # witness, so the certificate is its negation, ground; the
                # body is not replayed (nothing in it is undefined).
                ob = defined(w["_expr"])
                if ob == TRUE:
                    return None
                parts.append({"op": "not", "args": [subst(ob, m)]})
            else:
                ob = _undef_obligation(task, twin_body, m, names, tmap)
                if ob is None:
                    return None
                parts.append(ob)
        else:
            return None          # preservation: see above
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
    # NAMES (2026-09-11, ROADMAP 13.2): sanitize away any identifier that
    # collides with a Verus/Rust reserved word, before either lowering
    # path renders anything -- see names.py's module docstring. `task` is
    # returned unchanged (`is`) when nothing needs a rename, which is
    # every previously-committed task. `_certificate` below runs on this
    # SAME renamed task/body, with `witness`'s own keys renamed to match
    # (`names.remap_witness`) -- see that function's own docstring.
    twin_body = body if body is not task.get("body") else None
    task, renames = names.sanitize(task, names.KEYWORDS["verus"],
                                    uppercase_ok=True)
    # the twin body renamed under the same mapping, kept a separate
    # object from task["body"] (2026-09-11, names.rename_body's note)
    body = names.rename_body(twin_body, renames) if twin_body is not None else task["body"]
    witness = names.remap_witness(witness, renames)
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
    rc = names.rename_comment(renames)
    if rc:
        src += f"\n// {rc}\n"
    return src


if __name__ == "__main__":
    raise SystemExit(harness.run_all(sys.argv[1:], lower, verus_backend, "rs"))
