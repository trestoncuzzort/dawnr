#!/usr/bin/env python3
r"""lower_framac.py: lower t v0+v1 tasks to ACSL-annotated C; the sixth kernel.

THE SEMANTIC LINE, corrected 2026-09-01. The old one was WRONG, and the
error was a false theorem, not a wording slip. It read: "C's int is a machine
type, but WP WITHOUT -wp-rte reasons about the arithmetic mathematically, so
this lowering matches t's mathematical integers exactly." Only the
ARITHMETIC is mathematical without -wp-rte. The TYPING is not: WP's default
model constrains every C `int` with is_sint32, so `x <= 2^31-1` was granted
for free on every formal, every local and every seq element. SPEC.md says t
integers are mathematical and unbounded, so the emitted obligation was a
different, weaker theorem. MEASURED on the differential fuzzer: framac alone
VERIFIED fz_p_intwidth and fz_p_seqlen while six other kernels REFUTED them,
and an element-width probe (`ensures len(s) > 0 ==> s[0] <= 2^31-1`) proved
10/10 goals, twin refuted.

The fix is not in this file, and cannot be: ACSL's unbounded `integer` is a
LOGIC type, and Frama-C 33 rejects it for a ghost variable and for a ghost
function's parameters and result alike (both measured), so there is no C
program this lowering could emit whose program variables are unbounded. What
a C int MEANS to the prover is a model, and the model is a flag: the adapter
pins -wp-model Typed+nat (verifiers/framac.py, MODEL), WP's natural
arithmetic, under which a C integer carries no range hypothesis at all.
Everything below, the `int` formals, `int` locals, `int *s` elements and the
`int s_n` length, is therefore a mathematical integer, and the ACSL side already
used `integer` for spec-level quantities and bound variables. The two files
are one instrument: this C read under the default model is a proof of
something t did not ask.

The -wp-rte machine-int arm remains a later gate, not a silent default.

v1 mapping (measured on frama-c 33.0 / alt-ergo 2.4.3-free, 2026-08-31):

  seq        -> `int *s` plus a fresh length parameter `s_n`, with emitted
                preconditions `s_n >= 0` and `\\valid_read(s + (0 .. s_n-1))`.
  forall/    -> `\\forall integer i; lo <= i < hi ==> body` (and the && form
  exists        for exists). Bound vars are ACSL `integer`, mathematical.
  while      -> `loop invariant` per invariant (order preserved, because the twin
                depends on it), `loop assigns` (collected from the body),
                `loop variant` from the required decreases clause.
  spec_funs  -> recursive ACSL logic functions (`logic integer f(...) = ...`),
                with a `{L}` label parameter iff the fun reads a seq. WP does
                NOT check termination of recursive logic definitions (measured:
                `bad(n) = bad(n)+1` is accepted), so this lowering emits the
                decreases obligation itself: one `lemma f_terminates_k` per
                self-call, stating measure' >= 0 && measure' < measure under
                that call's path condition. Those lemmas are proof goals in
                the same file: unproved means REFUTED, not a shrug.
  recursion  -> a real recursive C function with an ACSL `decreases` clause;
                WP's variant PO at the call site is the termination proof
                (measured: `decreases 0` on factorial leaves the variant goal
                unproved).

DEFINEDNESS, honestly: `at` outside [0, len) is undefined in t. For
EXECUTABLE positions this lowering discharges it: every unconditionally
evaluated `at` in a statement gets a `/*@ assert 0 <= i < s_n; */` proof
obligation in front of the statement, and a conditionally evaluated `at` in
executable position is an explicit NotImplementedError (never silently
emitted as C UB). For SPEC positions (requires/ensures/invariants/spec_fun
bodies) WP's logic is total: an out-of-range s[i] denotes an UNCONSTRAINED
value under the memory model, so no proof can depend on any particular
out-of-range content, weaker than Dafny-style well-formedness checking,
stronger than totalizing to a fixed value. That gap is this backend's known
softness, recorded here rather than papered over.

DIV/MOD, added 2026-09-08. Measured convention: both ACSL's logic `/`/`%`
(over mathematical `integer`, no -wp-rte) and C's executable `/`/`%` under
-wp-model Typed+nat truncate toward zero, matching each other and the ACSL
manual's own definition, and matching neither SPEC.md's Euclidean
convention (probes acsl_div/acsl_floor: TIMEOUT on the six SPEC.md example
equalities; acsl_trunc and the executable c_div probe: VERIFIED on the same
six, truncating). So this lowering never emits a bare `/`/`%` for t's `div`
and `mod`: it defines them in the kernel's own truncating terms. ACSL side,
declared once per file that uses either op (T_DIVMOD_ACSL, emitted before
any spec_fun so spec_funs may use them):

    logic integer t_mod(integer x, integer y) =
      (x % y < 0) ? x % y + \\abs(y) : x % y;
    logic integer t_div(integer x, integer y) =
      (x % y < 0) ? (x / y) - (y > 0 ? 1 : -1) : x / y;

(truncating `%` carries the sign of x or is 0; shifting a negative
truncating remainder up by |y| gives the Euclidean remainder in [0, |y|),
and t_div is the truncating quotient with the matching -1/+1 correction.
Measured 2026-09-08: defining t_div as the exact division `(x -
t_mod(x, y)) / y` TIMEOUTs on the general identity `x == t_div(x,y)*y +
t_mod(x,y)` (alt-ergo cannot see the subtraction is a multiple of y
unaided); the correction form VERIFIES it, because it telescopes to WP's
own native `x == (x/y)*y + x%y` plus linear arithmetic, nothing
division-shaped left over.) `term()` renders `div`/`mod` as
`t_div`/`t_mod` calls; C executable position (`cexpr()`) inlines the same
formula with C's own `/`/`%` so the two sides stay syntactically parallel.
Definedness: y == 0 is undefined by SPEC.md, the same shape as `at`'s bound
check, so `defs()` adds `y != 0` to the domain obligation of any spec
expression containing `div`/`mod`, and executable position gets a
`/*@ assert (y) != 0; */` immediately before the statement (code_ats/
at_asserts, generalized to carry tagged `("at", ...)` and `("nz", ...)`
obligations; a conditionally evaluated `div`/`mod`, like a conditionally
evaluated `at`, is an explicit NotImplementedError rather than silent UB).
Unlike `at`, t_div/t_mod are themselves total at y == 0 (ACSL's own `/`/`%`
are, measured), so this obligation is owed to SPEC.md's semantics, not to
keeping the kernel from choking.

Bodies lower to statements: locals are C locals, the return name is a local
returned at the end, `bool` is C int 0/1 (spec side renders bool vars as
`x != 0` and bool equality as `<==>`). Every function gets `assigns
\\nothing;`, which is provable (t bodies never write memory) and is what
makes recursive calls modular.

RETURN, added 2026-09-08 (SPEC.md "Early exit"). `{"return": [ID, Expr]}`
lowers to a real C `return`: `Expr` sits in the same position as an
assignment's right-hand side, so `stmts()` gives it the same at_asserts
(the `at` bound, the `!= 0` divisor) before assigning it to the return
name and emitting `return <name>;`, from whatever `if`/`while` nesting it
sits at. This is exactly WP's rule and SPEC's: the postcondition is
checked at every return, and the loop invariant is not owed there, because
C's `return` leaves the loop without going through its header again.
Nothing may follow a `return` in its own block (well-formedness's job,
not this file's), so the statement after the enclosing `if` is dead only
on the branch that returned, never on the other, and no
-wp-smoke-dead-local-init goal is at risk THERE. `assigned_names()` counts
the return name as assigned, so a return inside a loop body puts it in
that loop's `loop assigns` frame like any other write. The certificate
replay (`_cert_stmts`) treats a replayed return as a stop signal threaded
back through `if`/`while`: since the replay is concrete, the state after
a return already holds the exact final values, so the certificate simply
emits no more C for the rest of the body (matching check_wf's refusal of
trailing statements) rather than emitting its own control-flow return
inside the always-`void` certificate function. Corrected 2026-09-09: see
RETURN SMOKE below, this claim was true only for the statement
IMMEDIATELY after the `if`, not for `lower()`'s own unconditional
trailing `return {ret};` after the whole body, which the paragraph did
not mention and which was the actual defect.

RETURN SMOKE and DIV/MOD SMOKE, both fixed 2026-09-09. Two unrelated
places in this file used to emit C that no input could reach, and both
read framac VACUOUS instead of VERIFIED because of the SAME downstream
mechanism: WP's dead-code smoke test does not always attach a NAMED goal
to the code point it dooms. Sometimes it does (a `wp_smoke_dead_code_sN`
entry in the JSON report, which `verifiers/framac.py`'s
`_UNREACHABLE_SMOKE` recognizes as "this is a fact about the body, not
vacuity", exactly as intended), and sometimes, MEASURED on both cases
below, it prints a bare `Warning: Failed smoke-test` at the source line
with no goal name in the report at all, which `_vacuity_smoke` fails
closed on ("doomed, but nothing named: refuse") because that adapter
cannot fix that file (RULES here restrict repair to this file only, and
regardless the honest failure-closed behaviour is correct on the goals it
CAN see; the fix is to stop handing it a goal it can't name).

(a) RETURN's own case: `lower()` closed every function body with an
unconditional `return {ret};` after the emitted statements, regardless of
whether the body already returned on every path. MEASURED on the
early-exit probe fz_p_ret_bothbranches (`if (x >= 0) return x; else
return -x;`, nothing after the `if`): the trailing `return r;` is dead
code on BOTH branches, not just one, and WP's smoke warning there named
nothing, scoring the file vacuous/vacuous. Fixed by `_always_returns()`
(mirrors lower_lean.py's helper of the same name): `lower()` now omits
the trailing `return {ret};` exactly when the body's own last statement,
or both branches of a trailing `if`, already return. A body with no
`return` at all, or one that leaves a path falling through, is
unaffected: abs.c and sum_upto.c (neither uses `return`) lower
byte-for-byte identical to before, measured by diff.

(b) DIV/MOD's case: `cexpr()`'s executable-position rendering of `div`
and `mod` used a C `?:` mirroring T_DIVMOD_ACSL's own ternary shape (the
truncating-to-Euclidean correction, selected by whether the truncating
remainder is negative). MEASURED on the lifted task extra_mod__mod (a
`while (k > 0)` loop with `k`'s invariant `k >= 0`, mod/div-ing by the
constant 2): once the invariant pins k's sign, the "truncating remainder
is negative" arm of that ternary is provably dead, and WP's per-arm smoke
check dooms it the same nameless way. Fixed by rendering `div`/`mod` in
executable position branch-free: `(rem < 0)` used directly as the C int
it already is (0 or 1) and multiplied into the correction term, instead
of selecting between two evaluated `?:` arms; no arm, no smoke target.
The ACSL side is unchanged in meaning: T_DIVMOD_ACSL's logic definitions
of t_div/t_mod keep the Euclidean law and the ternary shape (a `?:`
inside an ACSL annotation is never a WP smoke target, measured, so there
is nothing to fix there), and the "dm" bridging assert (`at_asserts`,
below) keeps rendering with that same ternary shape via
`_divmod_ternary_cexpr`, now `cexpr(..., _div_style="ternary")` threaded
recursively so a `div`/`mod` NESTED inside another one's x/y argument
stays ternary at every level too: the first version of this fix passed
`_div_style` only at the top call and let nested sub-expressions fall
back to the branch-free default, which rendered raw C boolean arithmetic
`(P) - (Q)` inside an ACSL annotation on the lifted task isArmstrong
(whose bridging assert nests `t_mod(t_div(n, 10), 10)`), and Frama-C
rejected it outright as MALFORMED ("invalid operands to binary -;
unexpected bool and bool") rather than scoring it vacuous or unproved.

MEASURED after both fixes: the 15-task committed regression (tasks/*.json)
reads identical to AGREEMENT.md's framac column, wall unchanged at
~120s total. The early-exit fuzz family (26 tasks: 22 fz_v1exit + 4
fz_p_ret_* probes, 1 a deliberate wf-error) moved from real counts
verified 22 / timeout 2 / vacuous 1 to verified 23 / timeout 2 / vacuous
0: the one vacuous cell was fz_p_ret_bothbranches, now verified. Of the
ten framac vacuous/vacuous rows in COVERAGE-lifted-785.md, nine used
div/mod and all nine stopped reading vacuous after the fix (seven now
verify outright; extra_mod2__mod2 reads an honest timeout;
isArmstrong reads an honest timeout, having also read MALFORMED under the
first, incompletely-threaded version of this fix). The tenth,
mockexam2_p5__problem5, uses neither `return` nor `div`/`mod` and stayed
vacuous unchanged: a real vacuous spec (recursive spec_fun, a
`gate: recursion` task) or a third instance of the same smoke-naming gap
in a shape this fix does not touch, not investigated further, RULES
having scoped this pass to the two named causes.

SEQ VALUES (`update`/`fill`), added 2026-09-09 (SPEC.md "Sequences as
values (v1)", ROADMAP 12.7). `seq` becomes a return type; `s[i := v]`
(DEFINED IFF `0 <= i < len(s)`) and `seq(n, v)` (DEFINED IFF `n >= 0`)
denote fresh seq VALUES, no aliasing, no mutation of the operand. C has no
sequence value at all, so this is a MEASURED encoding choice, not a
notational one, decided against the two new committed tasks (`swap`,
`update` only; `reverse`, `fill` plus a per-iteration `update`) by hand
with frama-c/WP before any of this file changed (RULES: measure first).

THE ENCODING, candidate (B) of the three the construct brief named (a
caller-provided output buffer with real memory stores, not an ACSL
`\\list`/axiomatised logic sequence carrying the value purely in the spec,
and not a ghost-only encoding). A seq PARAM was already `int *s, int s_n`
(read-only, `\\valid_read`); a seq RETURN gets the identical pair APPENDED
to the C signature as an OUTPUT parameter (`int *r, int r_n`), now
WRITABLE (`\\valid`, not `\\valid_read`) and `\\separated` from every other
seq buffer in scope (WP's Typed memory model does not assume two `int *`
formals of the same C type are non-overlapping on its own; measured on
the swap probe: dropping `\\separated` left `r[i] == s[j]` unprovable).
The C function itself becomes `void` (no scalar `\\result` for a seq
return; `ensures` renders `r`/`r_n` as plain names, matching an ordinary
seq param's rendering rather than substituting `\\result`), and every
`s[i := v]`/`seq(n, v)` assignment lowers to REAL C writes into the
target buffer, proved by WP's own points-to reasoning over ordinary
stores, nothing bespoke needed beyond that: `update`'s base, when it
names a DIFFERENT buffer than the target (swap's `r := s[i := ...]`, its
first write to `r`), is copied in first (a whole-buffer loop, invariant
`target[t] == base[t]` for `t` below the counter -- exactly "equal to `s`
at every index but `i`"); a SELF update (swap's `r := r[j := tmp]`,
reverse's per-iteration `r := r[i := ...]`) skips the copy, since the
target already holds what the base denotes; `fill` needs no prior value
and writes the whole buffer in one loop. `seq_assign_lines` (above
`assigned_names`) is the whole mechanism; `stmts()`'s `assign`/`return`
cases dispatch to it for a seq-typed target, `var` refuses a seq-typed
LOCAL outright (see below).

The return buffer's `requires \\valid(...)` bound and its pinned length
(`requires r_n == <len-expr>;`) must both be expressible in PARAMS alone
(ACSL's `requires` has no locals in scope), so `_seq_len_track` walks the
body BEFORE any C is emitted, propagating a symbolic length (a t Expr) per
seq name from the params outward: `update` preserves its base's length,
`fill`'s length is its own first argument, `if` requires both branches to
agree, `while` requires the tracked length to be unchanged by one static
pass through the body (an update-only loop, reverse's shape). Both
committed tasks resolve to `len(s)` this way. What this candidate CANNOT
express, found by construction rather than discovered late: a `fill`
whose length has no such closed form over params (built from a LOCAL with
no reduction to a param expression, or one that disagrees across
branches) has no buffer bound to hand the caller, and `lower()` raises
NotImplementedError rather than guess one. The task brief's other named
alternative, a `t_len_r` OUT-parameter the callee itself computes and
writes, would lift this for the LENGTH (the callee could report whatever
it computed) but not for the buffer's own VALIDITY bound, still owed to
the caller before the call and so still needing an expression fixed in
advance; not implemented, since neither committed task needs it.

A seq-typed LOCAL (`var a: seq := s;`, SPEC.md's other new position) is
NOT implemented: it would need its own backing storage with no external
contract to size it from (v1's scope rule keeps locals out of `ensures`,
so there is no requires-time bound to borrow the return's trick from),
and neither committed task declares one; `stmts()`'s `var` case refuses
it by name (NotImplementedError) rather than emit something unmeasured.
A recursive call to a seq-returning task is refused the same way
(`cexpr`'s `call` case): it would need a second output buffer this
lowering does not allocate, and no committed task recurses with a seq
return.

TWIN REFUTATION, the two new witness kinds. Before this construct,
`certificate()` minted REFUTED from exactly one witness shape (`_kind ==
"value"`, a whole-program input where the twin's computed value falsifies
`ensures`); an `undefined` or `exit` witness got no certificate at all,
an honest but weaker TIMEOUT/UNPROVED. swap's twin (OFF-BY-ONE on the
`at` inside its first statement) measures an `undefined` witness (`s=[0],
i=0, j=0`, the mutant reading `s[i+1]`, index 1 outside `[0,1)`);
reverse's twin (INVARIANT-DROP of its range-preservation invariant)
measures an `exit` witness (`s=[], i=0, r=[0]`), a LOOP STATE, not an
input. Both are now certified, `_undef_certificate` and
`_exit_certificate` (above `certificate`), mirroring the SAME night's
`lower_verus.py`/`lower_fstar.py` additions for the identical construct:

  `undefined`: re-walk the twin body with `interp.ev`, in the same
  left-to-right order `interp.py`'s own `exec_body` used to raise the
  `Undef` that minted this witness kind, using `defs_t` (a new function:
  the SAME rule `defs()` already renders to ACSL, restated as a t formula
  so `interp.ev` can decide it at the ground witness -- one definedness
  RULE, two renderings). The first statement whose obligation comes back
  false is the certificate: no C statement is replayed at all, since
  every name the obligation can mention is either a param (declared
  ground, exactly as the value-kind branch already declares params) or an
  int/bool local computed along the way (declared ground as the walk
  proceeds), so the obligation renders straight through `pred()`. A
  SEQ-typed intermediate local assigned before the failure refuses
  (materializing its snapshot needs the full replay this shortcut
  avoids); not exercised by swap, whose failure is the body's first
  statement, only documented for the next task that might need it.

  `exit`: `interp.invariant_witness`'s own obligation restated (the
  surviving invariants and `requires` hold, the guard is false, `ensures`
  is false). Unlike a `value` witness this state is not REACHED by
  running the function from its params (`_Admissible` screens for states
  a sound kernel cannot rule out, not for states an actual run passes
  through), so it is declared directly as ground C locals for every name
  the witness names -- params AND loop-scope locals alike, identical to
  how params are already declared -- and `_cert_stmts` (UNCHANGED)
  replays only the twin's mutated loop onward (`_loop_suffix`), which
  correctly computes zero further iterations when the witness already has
  the guard false, exactly reverse's own measured case. Scope limit: only
  a TOP-LEVEL loop is handled (`_twin_loop`/`_loop_suffix`, mirroring
  `lower_verus.py`'s `_twin_loop`); a loop nested under an `if` would need
  `interp.continuation`'s own search, unmeasured, not needed here.

  Neither new kind extends `_cert_stmts`/`_cert_cexpr` to render a
  seq-typed assignment's own C text (the copy/fill loops
  `seq_assign_lines` emits for real function bodies): an `update`/`fill`
  node reaching `_cert_cexpr` still hits its existing "no operator"
  `ValueError`, caught by `certificate`'s own exception handling exactly
  like any other unexpressible witness. Correct and unsurprising for both
  committed cells (swap's certificate never reaches a seq assignment;
  reverse's replays zero loop iterations), so extending it further was
  not measured and is left for whichever task needs it.

SCOPE, MEASURED rather than assumed. `_undef_certificate` and
`_exit_certificate` are GENERAL mechanisms -- neither is seq-specific --
and turning them on unconditionally was tried first: it changed 9 of the
15 already-committed tasks' twin cells (every framac `verified / timeout`
row in AGREEMENT.md) from an uncertified TIMEOUT to a certified REFUTED,
matching what every other kernel already reads there. That may well be a
sound improvement, but RULES scoped this pass to landing `update`/`fill`
and reading the two NEW tasks, not to re-measuring nine committed ones
outside a dated note of their own, so `certificate()` gates both new
kinds on the task returning a seq, which today picks out exactly
swap/reverse and leaves every pre-existing task's certificate path (and
verdict) untouched -- diffed byte-for-byte against the pre-change
lowering, real and twin, for all 15.

MEASURED: swap and reverse both COUNT (real VERIFIED, twin REFUTED) --
swap `off-by-one` witness `s=[0], i=0, j=0`, reverse `invariant-drop#1`
witness `exit at s=[], i=0, r=[0]`. The 15-task committed regression
reads identical to AGREEMENT.md's framac column (6 verified/refuted:
abs, factorial, fib, gcd, max, remainder; 9 verified/timeout: all_nonneg,
contains, count_matches, digit_sum, first_even, is_prime, linear_search,
seq_max, sum_upto), wall 125.4s for those 15, 139.6s for all 17.

THE SEQ-RETURN GATE, REMOVED, 2026-09-09 (later the same night). It
existed for exactly one reason, stated above: to keep that pass's own
17-task regression reading byte-for-byte as AGREEMENT.md recorded it,
while `update`/`fill` landed. `_undef_certificate` and
`_exit_certificate` were never seq-specific mechanisms; the gate was a
scoping decision for THAT pass, not a soundness boundary, and it was
left in place only because re-measuring nine already-committed cells was
out of scope for a pass about landing two new ones. This pass is that
re-measurement, done on its own terms: `certificate()` now dispatches
`undefined` and `exit` witnesses for ANY task, whatever its return type;
the `task["returns"][0]["type"] != "seq"` check is gone.

MEASURED. All 17 committed tasks' REAL programs are byte-identical to
the gated lowering (diffed `out/*.c` for every non-twin file, before and
after; zero differences) -- only twin files carrying a newly-certifiable
witness changed, by construction: removing a gate can only ever add a
certificate function to a twin, never touch the real program's C at all.
Cells: all 9 previously-uncertified `verified / timeout` rows (all_nonneg,
contains, count_matches, digit_sum, first_even, is_prime, linear_search,
seq_max, sum_upto) move to `verified / refuted`, all by the `exit` kind
(every one is an INVARIANT-DROP twin), matching the number measured and
quoted above when this was first tried. The 17-task framac column now
agrees with every other kernel's column in AGREEMENT.md: 16 of 17
verified/refuted (reverse reads verified/malformed, the coherence gate's
own doing, not this pass's).

The lifted-785 sweep (`out/lifted-tasks/*.json`, 198 tasks) moves the
same way at scale, measured by running every task through
`harness.run_task` (T_CELL_SERIAL=1, an outer 6-way task pool, so total
kernel concurrency stays at 6, never the 36 that an ungated outer pool
times `cell_pair`'s own 2*n=6 fan-out would reach). Framac column,
COVERAGE-lifted-785.md before -> measured after: verified/refuted 87 ->
125 (+38), verified/timeout 65 -> 14 (-51), timeout/timeout 16 -> 6
(-10), timeout/refuted 4 -> 14 (+10, the other end of the same 10 moves),
verified/unproved 2 -> 4 (+2: two `exit`-witness certificates the kernel
DECLARED but did not ACCEPT, `_cert_status`'s own audit demoting the cell
from an honest budget TIMEOUT to UNPROVED rather than minting a REFUTED
it cannot back -- the certificate discipline working exactly as
documented, not a regression in the counted metric, since neither
outcome is agreement). Every other category (no-twin/no-twin 6, abstain/
abstain 4, verified/vacuous 4, timeout/vacuous 3, verified/verified 5,
vacuous/vacuous 1, malformed/malformed 1) is unchanged, cell-for-cell:
none of those tasks reach `certificate()` with an `undefined` or `exit`
witness at all, so the gate's removal cannot touch them; a new
verified/malformed category (0 -> 11) also appears in this same commit,
the coherence gate's own doing, not this pass's -- of the 51 cells that
left verified/timeout, 38 landed on verified/refuted, 2 on
verified/unproved, and 11 on verified/malformed. 61 cells moved in total
(38 + 10 + 2 + 11); every move is verified/timeout or timeout/timeout
tightening to a certified verdict, or the coherence gate's own
verified/malformed, never the reverse.

SOUNDNESS of every moved cell rests on the same audit `verifiers/
framac.py` already runs for the seq-gated cells: `_cert_status` requires
exactly one `t_refutation_certificate`-named goal, declared AND proved,
plus every goal in its audit set (its enclosing function's own goals,
smoke tests included, plus every function-less global goal) also proved,
before minting REFUTED; a file merely carrying the certificate NAME can
never mint VERIFIED regardless. Corrected in place: an earlier draft of
this note claimed framac's adapter lacked dafny.py/verus.py/spark.py/
lean.py/fstar.py's explicit "coherence gate, 2026-09-07" (a file whose
own main goals ALL discharge alongside an accepted certificate reads
MALFORMED there, since a proof of the contract and a certified
counterexample to it cannot both be sound). That was wrong even as
written: this same pass adds the matching gate to
`verifiers/framac.py`'s `_all_obligations_proved(m, smoke)` branch --
when true and `cert_marked`+`accepted`, it now reads MALFORMED, not
REFUTED, exactly as the other six adapters do (see verifiers/framac.py's
own "coherence gate" comment). Exercised by all 11 of tonight's newly
verified/malformed cells above (see the SEQ-RETURN GATE accounting):
every one is `_all_obligations_proved` true, cert_marked, accepted, and
now MALFORMED.

SURPRISES. Four lifted tasks (mfirstCero, factorialOfLastDigit,
invertArray, fcul_exercises_10/find) raised a bare `NotImplementedError`
out of `lower()` when called on `task["body"]` directly through
`harness.run_task` -- a pre-existing limit in the REAL body's own
lowering (a conditionally-evaluated `at`/`div`/`mod` in a `while`
condition, or a `spec_fun` call in executable position), completely
unrelated to the certificate gate: the traceback bottoms out in
`stmts()`/`code_ats()` before `certificate()` is ever reached, so it
fires identically with the gate in place. COVERAGE-lifted-785.md already
reads these four `abstain / abstain`, which is `run_par.py`'s own
wrapper catching this same exception, not measured directly here since
RULES scoped this pass away from `run_par.py`/`run_all.py`; counted as
unchanged above (as of THIS pass -- see the WHILE-GUARD DEFINEDNESS note
below `at_asserts`/`stmts()`'s `while` case: invertArray's own abstain
was actually the UNCONDITIONAL case that note fixes, not the conditional
one this paragraph names, and it now lowers; the other three still
abstain for the reasons stated here, unchanged). Six more lifted tasks
that read `no-twin / no-twin` in COVERAGE-lifted-785.md print a REFUSED
reason from `harness.run_task` instead (twin_cached found no operator,
no input, or no witness) -- the identical refusal, before `certificate()`
runs at all, just a different label than the sweep driver's; also
counted as unchanged.

SEQ OPS (`seq`, `+` concatenation, `slice`), added 2026-09-09 (SPEC.md
"Sequences: literals, concatenation, slices (v1)", the wave after
"Sequences as values"). Three new Expr forms, landed within the SAME
buffer model the seq-value machinery already established: a seq PARAM is
`int *s, int s_n` (`\\valid_read`), a seq RETURN is a caller-provided
output buffer (`\\valid`, `\\separated`), and a value with no closed-form
length has no buffer to give it.

  A literal `[e1, ..., en]` (n >= 0) assigned to a seq-typed name is n
  individual stores, 0 for `[]` (`seq_assign_lines`'s new `seq` case): a
  FULL REPLACEMENT of the target's value, never additive.

  A slice `s[a..b]` in READ position (an argument to `at`/`len`, or
  nested inside another spec expression) is pure formula substitution,
  not a copy: `len(s[a..b])` renders as `(b) - (a)`, `s[a..b][k]` as
  `s[(a)+(k)]` (`_seq_len_render`/`_seq_at_render`, consumed by `term()`,
  and `defs()`'s new `slice`/`at`-on-a-slice cases for the definedness
  obligation `0 <= a <= b <= len(s)`, the same shape as `at`'s own
  bound). `r := s[a..b]` into the OUTPUT buffer (`tail`'s own shape,
  loop-free) IS a copy loop (real pointer arithmetic over real memory,
  `seq_assign_lines`'s `slice` case, `src[(a)+__k]` read into
  `target[__k]`), the buffer's length pinned exactly as `update`/`fill`
  already were, `_expr_seq_len`'s new `slice` case (`b - a`) resolving it
  through `_seq_len_track` with no other change needed: EXACT mode,
  unchanged machinery.

  `+` is polymorphic by operand type, exactly as `==` already was for
  seqs (`typ()`'s new case, checking the first operand's type): two ints
  add, two seqs concatenate. Assigned to a seq-typed name and
  self-referential on the left (`r := r + [x]`, the append idiom,
  `filter_pos`'s own shape, the LLM-shaped idiom the census counts) it
  needs the buffer's CAPACITY, not its exact length: `_ret_capacity`
  reads it straight off the task's own first `ensures` of the shape
  `len(ret) <= E`/`== E` (`filter_pos` states `len(r) <= len(s)`,
  `E = len(s)`) when `_seq_len_track` cannot resolve an exact length
  (the append sits inside a data-dependent `if`/`while`, so its own
  before/after check already, correctly, drops the name) -- a
  seq-returning task with neither a closed-form length nor such an
  `ensures` bound ABSTAINS, `NotImplementedError`, never guesses one.
  CAPACITY MODE: `requires {ret}_n == E;` pins the buffer's SIZE; the
  buffer's actual, data-dependent final length is tracked by a fresh
  LOCAL, `{ret}_len`, threaded through the body by a new `Ctx` field,
  `seq_len` (name -> the ACSL rendering of that seq's CURRENT length,
  overriding the default `{name}_n`): `{ret}_len` itself while still
  inside the function (a loop invariant, an inner `assign`'s definedness,
  ordinary local scope), `\\result` in the function's own post-state
  (`ensures` has no locals in scope, so the C function's return type
  becomes `int` in CAPACITY mode instead of `void`, `\\result` carrying
  the buffer's true final length -- no committed task returns both a seq
  and a scalar, so nothing clashes). An append is `r[r_len] = x; r_len =
  r_len + 1;` with the owed assert `r_len + <count> <= r_n` emitted
  first (`seq_assign_lines`'s new `+` case, self-referential only;
  non-self concatenation, e.g. a fresh `r := s + t`, is refused by name,
  not measured). `assigned_names` grew a `seq_caps` parameter so a loop
  that appends also frames its own length local in `loop assigns`
  (`stmts()`'s `while` case passes `ctx.seq_len`) -- the CAPACITY-mode
  local is real program state a loop writes, exactly like any other, and
  WP's frame check fails on an unlisted write exactly as it would for
  any other omitted name.

  Two measured hazards, both found by running frama-c, neither guessed:
  (1) `filter_pos`'s own `Loop assigns (2/2)` goal (proving the
  just-written `r + (r_len - 1)` lies inside `r`'s own valid range) read
  an honest Alt-Ergo STEP LIMIT with no implicit bound on `r_len` at all
  -- WP does not carry a per-statement `assert` across loop iterations,
  and the task's own invariants never state `r_len >= 0` (nothing else
  implies it either). Fixed by an IMPLICIT loop invariant, `0 <=
  {r_len};`, emitted whenever a loop's own frame carries a CAPACITY
  name's length local (`stmts()`'s `while` case) -- an encoding artifact,
  true by construction (the local only ever starts at 0 or a literal's
  own count and only increases), owed to WP, not to the task. (2) The
  matching UPPER bound, `r_len <= {ret}_n`, was tried first (the
  natural-looking `0 <= r_len <= r_n` pairing) and MEASURED WRONG: it
  made `filter_pos`'s postcondition `\\result <= len(s)` provable via
  `r_n == len(s)` alone, with no dependency on the task's own `i <=
  len(s)` invariant at all, so the `invariant-drop#1` twin (which drops
  exactly that invariant) verified in FULL -- both the twin's own
  contract and the certificate's negation of it accepted, the coherence
  gate correctly reading the file MALFORMED instead of the intended
  REFUTED. The upper bound is TASK semantics (on `filter_pos` it already
  follows from `i <= len(s)` and `len(r) <= i`, chained through `r_n ==
  len(s)`, exactly the chain an INVARIANT-DROP twin threatens), not an
  encoding artifact, and does not belong in an implicit invariant; only
  the lower bound does.

  `_undef_certificate`'s own definedness rule, `defs_t` (the t-Expr
  mirror of `defs()`, used to DECIDE a witness's failing obligation
  before any ACSL exists to check it against), grew matching `slice` and
  `at`-on-a-slice cases (`tail`'s twin, `off-by-one` on the slice's lower
  bound, measures an `undefined` witness, `s=[0]`, mutant slice bounds
  `[2..1]` outside `0 <= a <= b <= 1`): without them, `defs_t` fell to
  its generic fallthrough, silently missing the slice's own `0 <= a <= b
  <= len(s)` obligation (still SOUND -- `interp.ev`'s own bounds check
  still raises `Undef` for real when reached, and `_undef_certificate`'s
  broad `except` swallows that same exception -- just uncertified, a
  TIMEOUT-shaped miss rather than the intended REFUTED).

  MEASURED: `tail` and `filter_pos`, real and twin (COUNTS both,
  matching the SPEC section's own committed-task discussion): `tail`
  real VERIFIED, `off-by-one` twin REFUTED (`undefined` witness, the
  slice-bound case above); `filter_pos` real VERIFIED, `invariant-drop#1`
  twin REFUTED (`exit` witness, `s=[], i=1, r=[1]`, no new certificate
  mechanism needed -- CAPACITY mode's `\\result` rendering already
  applies to `_exit_certificate`'s own final `ensures` assert through the
  same `ctx.seq_len`-less `Ctx` it always built, which happens to be
  correct there since that ctx's `r_n` IS the witness's own declared
  array length, not the real function's capacity). The 15 previously
  committed tasks plus `swap`/`reverse` (17 total, AGREEMENT.md's framac
  column) diff byte-for-byte identical, real and twin, to the
  pre-construct lowering: `reverse` stays exactly `real verified /
  invariant-drop#1 twin malformed`, the coherence-gate case the seq-value
  wave's own dated note already recorded, untouched by this wave (its
  body uses `fill`/`update` only, never `seq`/`+`/`slice`).

  NOT implemented, found by construction rather than assumed: a slice
  assigned into a CAPACITY-mode buffer (no committed task); concatenation
  whose left operand is not the assignment's own target, i.e. a fresh `r
  := s + t` neither operand self-referential (`_expr_seq_len`'s `+` case
  resolves this correctly for EXACT mode when both operands are
  independently closed-form, but `seq_assign_lines`'s `+` case still
  refuses to WRITE one, by name, since no committed task needs the C
  text); an append whose source is neither a bare seq variable nor a
  `seq` literal; a `seq`/`slice`/seq-typed `+` reaching ACSL term
  position directly rather than through `at`/`len` or a body assignment
  (`term()`'s new refusals, mirroring `update`/`fill`'s pre-existing
  one). Each raises `NotImplementedError` by name, never guesses.

WHILE-GUARD DEFINEDNESS, added 2026-09-09, the eighth sweep's residual
(COVERAGE-lifted-785.md): the two MBPP-DFY tasks (`dafny_synthesis_
task_id_3__isNonPrime`, `dafny_synthesis_task_id_605__isPrime`) loop on
`while i <= n / 2`, and this lowering used to ABSTAIN on any `at`/`div`/
`mod` appearing unconditionally in a `while` guard, full stop: there was
no single statement its definedness assert could go in front of. Fixed in
`stmts()`'s `while` case and mirrored in `_cert_stmts()`'s (see the dated
comments there): the guard's `at_asserts` are now emitted twice, once
immediately before the `while` (the first evaluation) and once as the
first statement of the loop body (every later evaluation, justified by
the same induction the loop invariant itself relies on -- see the
comment at the fix site for the full argument). MEASURED (both lifted
tasks, plus is_prime/first_even/filter_pos as a regression check, via
harness.run_task with OUT pointed at out/agent-framac-guard):

  - is_prime, first_even, filter_pos: byte-identical C, real and twin,
    to the pre-fix `out/*.c` (their guards have no `at`/`div`/`mod`, so
    `at_asserts` returns `[]` at both new call sites and nothing changes
    structurally -- confirmed by `cmp`, not just by construction).
  - Both lifted tasks: the ABSTAIN is gone, real C is now emitted, and
    the new guard-definedness asserts (the divisor-nonzero check and the
    raw/logic bridging assert for `n / 2`) both discharge in the
    milliseconds range (Qed or fast Alt-Ergo) on every run -- the fix
    itself works exactly as measured on is_prime's existing `if`-position
    analog. But the outcome is `timeout / timeout`, not the hoped
    `verified / refuted`, for two SEPARATE reasons this fix does not
    touch and did not introduce:
    1. The real function's own trailing `ensures` (unchanged by this
       fix) needs a fact neither of the new asserts states or implies:
       no divisor of `n` lies in `(n/2, n)`. That is genuinely harder
       than anything div/mod definedness requires (it is nonlinear,
       needs `n = d*q` reasoning for a non-constant `d`), and alt-ergo
       does not close it within any budget tried, [Timeout]/[Stepout]
       alike at 10s/20000 steps (the pinned budget), 60s/200000 steps,
       and 300s/500000 steps (all three tried by hand, same goal name
       `..._ensures` failing every time, well under a second of actual
       solver work reported each try -- a wall/step ceiling never
       reached, not a close call). Consistent with the wider census:
       COVERAGE-lifted-785.md already reads this same real function
       unproved or timeout on five of the other six kernels (verus,
       spark, lean, rocq, fstar); only dafny's automation closes it.
    2. Independently, the invariant-drop twin's witness for both tasks
       is kind `"preservation"` (measured: `harness.twin_cached` on
       both), the one witness kind `certificate()`'s dispatch does not
       cover ("return None # preservation: see the section note",
       above `_exit_certificate`) -- so REFUTED is structurally
       unreachable for this twin regardless of how the real function
       fares; its outcome is whatever WP naturally does with the
       dropped invariant, which is also TIMEOUT here (the same `ensures`
       goal, plus one more Stepout goal the drop exposes).
  Neither gap is this fix's to close (a certificate mechanism for
  `preservation` witnesses, and whatever hint alt-ergo would need for
  the divisor-range fact, are each their own measured pass), so this note
  reports the honest cells rather than the hoped ones: `timeout /
  timeout` for both, up from `abstain / abstain`, the ABSTAIN itself
  eliminated as designed.

PAIRS, added 2026-09-10 (SPEC.md "Pairs", ROADMAP 12.7, the wave after the
sequence trio). New type `{"pair": [T1, T2]}`, T1/T2 one of "int"/"bool"/
"seq"; new Expr forms `pair`/`fst`/`snd`. C has no product value either
(the seq value machinery section's own opening line), so this is a
second MEASURED encoding choice, decided by hand with frama-c/WP BEFORE
`_pair_field_c`/`_pair_struct_name`/the "pair"/"fst"/"snd" cases below
were written (RULES: measure first), against exactly the construct
brief's two named candidates:

  (a) a struct returned BY VALUE, `struct t_pair_T1_T2 { int a; int b; };`
      (this backend's own `int`, the C type it already picks for every
      mathematical-integer value under the pinned Typed+nat model, not a
      `long`; a bool component costs nothing extra, since bool is already
      C int 0/1 here), the contract stated on `\result.a`/`\result.b`.
  (b) two `long *ra, long *rb` out-parameters with `assigns *ra, *rb` and
      `\valid` requires, the contract on `*ra`/`*rb`.

Candidate (a) was tried first, by hand, on divmod_pair: a probe with
exactly the shape `lower()` now emits (the struct declared before the
ACSL block, the contract's three `ensures` on `\result.a`/`\result.b`,
the body one compound-literal assignment `r = (struct t_pair_int_int){
<div-expr>, <mod-expr> };` with the same branch-free div/mod rendering
and bridging asserts every other task already gets) scored the REAL
function 11/11 goals proved outright (`Qed 3, Alt-Ergo 6, Terminating 1,
Unreachable 1`; corrected in place, first recorded as 10/10, undercounted
by one -- the committed lowering's own re-run below reads the same
11/11), and a hand-written refutation certificate for the
`wrong-var` twin (ground state `x=1, y=1`, exactly SPEC.md's own witness)
scored its named goal `t_refutation_certificate` VALID, every other goal
in the certificate's own audit set proved alongside it, with the twin's
own three `ensures` left honestly STEPOUT (genuinely false in general,
never touched by the twin mutation rule). Candidate (a) worked outright,
so candidate (b) was never built: there was nothing left for two
out-parameters to fix. Kept for that reason alone, not for any
architectural preference between the two.

MEASURED after `lower()`/`_value_certificate`/`cexpr`/`_cert_cexpr`/
`_cev`/`term`/`pred`/`typ` grew their pair cases, via `harness.run_task`
into a scratch OUT (never the committed `out/` tree, RULES): both
committed tasks COUNT on the first run, no debugging needed after the
hand probe.

  `divmod_pair` (loop-free): real VERIFIED. Corrected in place: this was
  first recorded as 10/10 goals, identical to the hand probe; re-run
  against the same code, it reads 11/11 (`Terminating 1, Unreachable 1,
  Qed 3, Alt-Ergo 6`), the hand probe undercounted by one. Twin
  `wrong-var` (the pair's two components swapped, `harness.py`'s own new
  twin-ladder move for this construct, SPEC.md "The twins") REFUTED via
  `_value_certificate` (a `value`-kind witness -- divmod_pair has no
  loop, so the whole function is one straight-line replay, exactly like
  every scalar-returning value-witness task already in AGREEMENT.md):
  witness `x=1, y=1 -> real [1, 0], twin [0, 1]`, the exact point and
  pair values SPEC.md's own committed-task paragraph names. Corrected in
  place: first recorded as 15/18 goals; re-run reads 16/19 (`Terminating
  2, Unreachable 2, Qed 9, Alt-Ergo 3, Timeout 3`) (the twin's own three
  `ensures` stepout, honestly; the certificate's own six goals -- four
  branch-decision asserts, one `assigns`, the named refutation assert --
  all valid).

  `min_max` (a loop keeping both bounds): real VERIFIED. Corrected in
  place: first recorded as 29/29 goals; re-run reads 35/35 (`Terminating
  1, Unreachable 1, Qed 19, Alt-Ergo 14`), the `\result.a`/`\result.b`
  projections reaching cleanly through all four quantified `ensures` and
  through the loop's own invariants (which never mention the pair at all
  -- `r` is assigned once, after the loop, so the loop frame rule needs
  no pair-typed case and none was written; found by inspection of both
  committed tasks, not measured as a gap). Twin `collapse-if` (the first
  guard collapsed, an ordinary value-changing mutation, not
  INVARIANT-DROP: SPEC.md's own note that no invariant drop of this task
  is witnessable by bounded execution is a fact about THIS task, not
  about pairs) REFUTED via the SAME `_value_certificate` path as
  divmod_pair, this time replaying a real (unrolled) loop at the
  witness: `s=[0, 1] -> real [0, 1], twin [1, 1]`. Corrected in place:
  first recorded as 45/46 goals; re-run reads 51/52 (`Terminating 2,
  Unreachable 2, Qed 33, Alt-Ergo 14, Timeout 1`) (one loop-invariant
  preservation goal the collapsed guard genuinely breaks, stepout; the
  certificate's own seventeen goals -- eight branch/loop-exit asserts,
  seven split `assigns` goals, the named refutation assert -- all
  valid).

THE ENCODING, mechanically: `pair(a, b)` is a C99 compound literal,
`(struct t_pair_T1_T2){a, b}` (`cexpr`'s and `_cert_cexpr`'s new "pair"
cases; `_cert_cexpr`'s is the one actually exercised by divmod_pair,
since its pair has a `div`/`mod` nested inside it and so never takes
`_cert_cexpr`'s `_has_divmod`-false shortcut to plain `cexpr`). `fst`/
`snd` are plain field reads, `.a`/`.b`, identical in ACSL (`term()`'s new
"fst"/"snd" case, reached by BOTH tasks' `ensures`, never by an
executable body since neither committed task projects a pair outside its
spec) and in C (`cexpr`'s and `_cert_cexpr`'s matching cases, unexercised
by either committed BODY but written for the same completeness reason
`_cev`'s "update"/"fill" cases already are). `pair(...)` itself has no
ACSL term rendering (`term()` raises NotImplementedError by name,
mirroring `update`/`fill`'s identical restriction): it is consumed
exclusively as the whole right-hand side of a body assignment to a
pair-typed name, exactly like a seq value, and neither committed task's
spec constructs one directly. `==`/`!=` on two pairs is COMPONENTWISE
(`pred()`'s new branch): ACSL has no struct equality this backend would
trust (a struct's bitwise/representation equality, even if WP accepted
one, is not the value equality SPEC.md means), so this rewrites `p == q`
to `fst(p)==fst(q) && snd(p)==snd(q)` as fresh Exprs and recurses through
`pred()` itself -- one equality rule used twice rather than duplicated,
and correct for a seq or bool component for free, since the recursive
call already knows how to render THOSE equalities extensionally/`<==>`.
The loop frame rule needed no change: neither committed task assigns a
pair-typed name inside a loop (`r` is written once, after `min_max`'s
loop), so `assigned_names`/`_assigns_target` never see one; a task that
DID would need a pair-typed case in `_assigns_target` this file does not
have, a real gap left for whichever task needs it, not silently claimed
covered.

`_value_certificate`'s ground-replay machinery (`_cev`, `_tty`) grew a
"pair" case each: `_cev` represents a pair value as a plain 2-element
Python list (the SAME shape `interp.py`'s own `_j` gives a witness's pair
value, so a replayed `st[ret]` compares straight against `w["_twin"]`
with no conversion step, mirroring how `_cev`'s pre-existing "update"/
"fill" cases already represent a seq value as a plain list); `_tty` tags
any `list` "pair" (safe: a seq-returning task is excluded from
`_value_certificate` before either side of a `_tty` comparison is built,
unchanged by this construct, so no seq value ever reaches this tagging
alongside a pair one). The certificate's own declaration loop (`decls`)
now declares the RETURN name with the struct type when the task returns
a pair, `int` for everything else (params, other locals) exactly as
before.

NAMED REFUSAL: a pair with a seq component. `_pair_field_c` raises
NotImplementedError the moment a component is "seq", named plainly in
the exception text rather than guessed past: a struct field returned BY
VALUE has no memory to back a fresh buffer's storage, and CAPACITY
mode's own machinery (a length-tracking local threaded through
`Ctx.seq_len`) has nothing to attach itself to inside a struct field
either -- exactly the SPEC.md section's own prediction ("very likely a
NAMED refusal in this column"), confirmed by construction rather than by
running anything (no committed task has one to run). NOT implemented,
also found by construction and also refused by name rather than silently
wrong: a pair-typed PARAMETER or LOCAL (both committed tasks use a pair
only as a RETURN; `stmts()`'s `var` case has no pair branch and
`lower()`'s `cparams` loop has no pair-typed-param branch, so either
would need its own measured probe, not attempted here); a recursive call
to a pair-returning task (mirrors the existing seq-return recursion
refusal, `cexpr`'s "call" case, unextended); a pair of pairs (SPEC.md
itself excludes this) and a pair-valued spec_fun result (SPEC.md's own
SpecFun grammar restricts `result` to "int"/"bool", so this can never
arise from a well-formed task).

REGRESSION, measured by diff, not by re-running frama-c (the C text is
byte-identical, and frama-c is deterministic on identical input; this is
the same discipline `_always_returns`'s note above uses for abs.c/
sum_upto.c): `abs`, `swap`, `reverse`, `tail`, `filter_pos` -- one task
from each pre-pair construct wave -- lowered again (real and twin, ten
files) into a scratch OUT and `cmp`-diffed against the committed `out/
*.c` this pass did not otherwise touch. All ten are byte-identical to
before this construct; every new "pair"/"fst"/"snd" case added above is
reached only when `typ()` actually returns a pair-shaped dict somewhere
in the task, which none of these five ever produce.

PAIRS RESIDUAL, framac, fixed and measured 2026-09-10. The fuzz family
`v1pairs` (31 tasks) read framac verified/refuted on 13 of 31 the day
this construct landed; 18 did not (named in the residual list, corpus
and readings in `fuzz-pairs/corpus.json`/`rows.json`). Two defects, one
already found by construction above (`_pair_field_c`'s own section
comment, before this note) and fixed here:

1. A pair-typed PARAMETER or LOCAL used to fall through `lower()`'s
   `cparams` loop and `stmts()`'s `var` case into the plain `int` branch
   -- a SILENT WRONG lowering (a struct-shaped value declared as a bare
   `int`), read by frama-c as MALFORMED the moment a field was read off
   it, on 9 of the 18. Fixed: both are now the struct BY VALUE, exactly
   the RETURN's own encoding (`_pair_types_needed`, new, finds every
   pair shape a task's C needs a struct for -- params, return, locals,
   and a `pair(...)` built and projected without ever being bound to a
   name, `fz_p_pair_proj`'s own shape -- so `lower()`'s header declares
   all of them, not only the return's). MEASURED, not assumed: a struct
   parameter works in WP's Typed model the same way the struct return
   already did. Fixing the parameter case exposed a SECOND malformed
   cause on the same task family, invisible until the first was fixed:
   `p == q` on two pair-typed PARAMETERS in executable position
   (`fz_v1pairs_053`'s `eq_params` shape) used to fall through `cexpr`'s
   generic `==`/`CMP` dispatch to a bare C `==` on two now-`struct`
   operands, not legal C for an aggregate type. Fixed the same way
   `pred()`'s own componentwise branch already handles pair equality in
   ACSL, mirrored into executable C.

2. `fst`/`snd` in PREDICATE position when the projection's own type is
   bool (`ensures r.0 == (\exists ...)`, the found/val idiom) crashed
   `pred()` outright, `ValueError: no predicate form for operator
   'fst'`, on the other 7 of the 18 (read framac `lower-error`, an
   unhandled crash, not an honest refusal). Fixed: `pred()` gained the
   same `!= 0` bool convention its own `var` case already applies to a
   bare bool-typed C name, applied to the field read instead.

MEASURED after both fixes (`fuzz_lower.py --only framac` on the 18,
never re-predicted): 8 of the 9 malformed tasks now COUNT (verified /
refuted); the ninth, `fz_p_pair_eq`, and one more discovery below stay
short of counting, for reasons that are not this construct's own defect
to fix. All 7 `lower-error` tasks, despite the crash itself being fixed,
still read ABSTAIN, not counted -- their `if (!found && s[i] <= -1)`
guard trips `code_ats`'s conservative, pre-existing, entirely
pairs-unrelated refusal of a conditionally-evaluated `at` inside a
short-circuit `and`'s second conjunct (the same guard the WHILE-GUARD
DEFINEDNESS note above fixed for a WHILE condition, never for an IF
condition's later conjunct). That `i` is in bounds here regardless of
`found` is true of THIS idiom, not something `code_ats`'s
statement-local, no-invariant-lookup rule can see in general, and
loosening it generically risks exactly the unsound totalization the
rule exists to prevent for a genuinely guard-dependent `at`/`div`. Left
a named abstain, not attempted: a real fix needs the invariant in scope
at the point `code_ats` decides, a bigger change than this residual
measurement's mandate, and this file's own crash-to-abstain fix (item 2
above) already turned a bug into an honest refusal, which is the
improvement that was this task's to make.

The two ALREADY-named abstains (a pair with a seq component, `_pair_
field_c`'s own refusal; a seq position holding `fst(p)`, `seq_var`'s
own refusal) are unchanged and confirmed still correct by this
measurement (`fz_v1pairs_064`, `fz_p_pair_seq`): neither fix above
touches either path, and no small fix presents itself for either (a
struct field still cannot back a fresh buffer; a seq operand still
cannot be a non-variable projection without a rule change to
`seq_var`'s own domain, `at`/`update`'s own restriction, not a pairs
one).

One further, ALSO not-this-file's-to-fix discovery, on `fz_p_pair_eq`
(`fst(p)==fst(q) and snd(p)==snd(q)`, an ordinary int-typed `and` from
the TASK's own source, nothing pair-specific about the `and` node
itself): its wrong-var twin's certificate REPLAYS that `and` with
LITERAL struct components substituted, and one conjunct becomes
Qed-decidably false outright, making the `&&`'s "second conjunct
evaluated" arm provably dead -- correctly DOOMED, the harmless finding
`_all_obligations_proved` already exempts on the ordinary VERIFIED path
everywhere in this file, but `verifiers/framac.py`'s own certificate
audit (`_cert_status`) has no matching exemption for a doomed smoke goal
inside the certificate function itself, so the certificate was rejected
(UNPROVED, not REFUTED) for a reason that has nothing to do with
whether the refutation holds. MEASURED directly against the kernel's
own `-wp-report-json` (not inferred): `t_certificate`'s own smoke goals
`passed: false, verdict: valid` -- confirmed doomed, confirmed
harmless, confirmed still rejected by `_cert_status`'s `ok()` check.
This is a `verifiers/framac.py` gap, general to any certificate whose
ground literals happen to decide one operand of ANY `and`/`or`
(nothing pairs-specific about it, and this file may only be edited
here), so it is named and left, not patched around. The SAME shape DID
get fixed where it was this file's own new code causing it:
`fz_v1pairs_053`'s certificate hit the identical doomed-smoke rejection
via THIS construct's own new componentwise pair-equality rewrite (`p ==
q` mutated by wrong-var to the reflexive `q == q`), and there a
branch-free rewrite was this file's to make (see the BRANCH-FREE
comment on `cexpr`'s pair `==`/`!=` case, above `_pair_struct_name`'s
call sites): a plain bitwise `&` on the two already-0/1 componentwise
comparisons, safe because both `fst`/`snd` are unconditionally defined
on a pair (unlike the general `and`/`or` case, where `code_ats`'s
short-circuit really is load-bearing), giving WP no branch to find
dead. That fix, and only that one, is why `fz_v1pairs_053` counts and
`fz_p_pair_eq` does not.

Net measured, framac column: 13/31 before this pass, 21/31 after (8 of
the 18-residual now verified/refuted); 7 abstain on the conditionally-
evaluated-`at` gap above, 2 abstain unchanged (seq component), 1 stays
verified/unproved (the certificate smoke gap above, not this file's
alone to close).

REGRESSION, this pass, same discipline as above: `divmod_pair`,
`min_max`, `abs`, `swap`, `reverse`, `tail`, `filter_pos` -- the two
committed pair tasks plus one from each earlier construct wave --
relowered (real and twin) via `harness.run_task` into a scratch
`out/agent-framac-pairs2` (never `out/` itself) and `diff`-checked
against the committed `out/*.c`. All fourteen files byte-identical;
every reading matches AGREEMENT.md's own framac column unchanged,
`reverse`'s own already-documented `verified / malformed` included.

NESTED SEQUENCES (v1), added 2026-09-10 (SPEC.md "Nested sequences
(v1)", ROADMAP 12.7, the wave after pairs). New type `{"seq": "seq"}`,
written `seq<seq>`: a seq whose elements are seqs of ints, one level.
No new Expr forms: every seq operator (the literal, `len`, `at`, `+`,
`slice`, `update`, `fill`, `==`) is polymorphic by its operands' own
static type, exactly as `+`'s int/seq split and pairs' `==` already
are; `s[i]` is a row, itself a seq value, and `s[i][j]` is the
notation's own chained `at(at(s, i), j)`.

C has no nested sequence value any more than it has a plain one, so
this is a further MEASURED encoding choice (the construct brief's own
two named candidates for this column: "a named refusal or a flat
encoding"), measured first on `row_max_len`, a nested seq PARAMETER
read only through `len`/`at`, never built, before `swap_rows`, this
construct's one BUILDING task, was attempted at all: read before
build, RULES' own order.

THE ENCODING: a flat buffer of ints plus an offsets array, `int
*m_data, int *m_off, int m_n` for a seq<seq> parameter `m`. Row `i` is
`m_data[m_off[i] .. m_off[i+1])`; `m_n` is the ROW COUNT, deliberately
reusing this backend's existing `{name}_n` convention (a plain seq's
`_n` is its element count) instead of a fresh name, because that is
what lets `at_asserts`'s existing "at" tag, `defs()`'s existing "at"
case, and `_seq_len_render`'s existing bare-variable fallback all
handle `m`'s OUTER dimension (`len(m)`, `at(m, i)`'s own `0 <= i <
m_n` bound) with no change at all, confirmed by running both committed
tasks, not merely hoped. `seq_var()` was widened once, to recognize a
seq<seq>-typed variable alongside a plain seq one (see its own
docstring), and that single change is what lets all three of those
pre-existing code paths pick up the nested case for free. Three
implicit `requires` this lowering adds that no committed task's own
`requires` states: `m_n >= 0`, `\valid_read(m_off + (0 .. m_n))`
(`m_off` carries `m_n + 1` entries), `m_off[0] >= 0`, a
monotone-offsets `\forall integer __t; 0 <= __t < m_n ==> m_off[__t]
<= m_off[__t + 1]`, and `\valid_read(m_data + (0 .. m_off[m_n] - 1))`.
Unlike the seq-trio's own CAPACITY mode, whose implicit lower bound is
a LOOP INVARIANT because it is a fact about a LOCAL a loop body
writes, these are all `requires`-time facts about the CALLER's own
array with no loop in the way, so none of them needs an invariant of
its own. Collision checks mirror the plain seq's own `{s}_n` check,
extended to all three synthesized names, `{m}_data`/`{m}_off`/`{m}_n`.

The only NEW rendering this construct adds is a ROW's LENGTH: `len(
m[i])` renders as `(m_off[(i) + 1] - m_off[(i)])`, both in ACSL
(`_seq_len_render`'s new "at" case) and in executable C (`cexpr()`'s
and `_cert_cexpr()`'s matching "len" cases), a formula substitution
over the offsets array, never a copy, the identical move
`_seq_len_render`'s own pre-existing "slice" case already makes for
`len(s[a..b])`. A bare ROW VALUE (`m[i]` reaching `at`'s own base, the
chained `m[i][j]`, or `m[i]` reaching ACSL term position or executable
position directly, never wrapped in `len`) has no rendering at all:
`_seq_at_render`, `cexpr()`'s "at" case, and `_cert_cexpr()`'s "at"
case each check the base's own type and raise NotImplementedError by
name, rather than let `seq_var`'s pre-existing "non-variable" refusal
fire on the wrong operand, or worse, silently reference a bare `m`
this encoding never declares as a C name. Not exercised by either
committed task (`row_max_len` only ever wraps `at(m, i)` in `len`),
written for the same completeness reason `_cev`'s "update"/"fill"
cases already are.

MEASURED on `row_max_len` (`harness.run_task`, `out/agent-framac-
nested`): real VERIFIED, 23/23 goals (Qed 12, Alt-Ergo 9, Terminating
1, Unreachable 1, Smoke Tests 5/5). Twin `invariant-drop` (the dropped
upper-bound invariant, "every row's length is at most `r`") REFUTED
via `_exit_certificate`, witness `m=[[], [0]], i=2, r=0`, SPEC.md's own
predicted witness matched exactly: 25/26 goals, the twin's own
`ensures` an honest Stepout (genuinely false in general, untouched by
the twin mutation rule), the certificate's own goal
`t_refutation_certificate` proved alongside every other goal in its
audit set, 5/5 smoke tests.

`_exit_certificate` grew one nested-seq case: declaring a witness's
nested value as a ground DATA array plus a ground OFFSETS array, built
directly from the witness's own rows, the same flattening THE ENCODING
above describes for a real parameter. That is the ONLY change the
certificate machinery needed. `_cev`'s own "at"/"len" cases needed
none, found by inspection rather than assumed: Python's `len()`/
indexing already compose correctly over a nested list with no
seq-specific code at all, so `_cev`'s generic `at`/`len` ground
semantics already computed a row's length correctly before this
construct existed; only the DECLARATION of a nested ground value into
C needed new code.

NAMED REFUSAL: `swap_rows`, this construct's one BUILDING task (`r :=
update(update(m, i, m[j]), j, m[i])`), refuses wholesale at its own
RETURN, before any C is emitted for it at all (`lower()`'s own check,
immediately after reading the return type). A seq<seq> RETURN needs to
BUILD a fresh row set, and this backend's flat data+offsets encoding
has nothing to build one into: the seq VALUE machinery's own CAPACITY
mode sizes ONE buffer's element count against ONE `ensures`-stated
bound (`_ret_capacity`), and a built seq<seq> return would need a
SECOND, independent bound for the offsets array's own row count
(data-dependent the moment a row is appended rather than merely
replaced), plus a data-dependent SUM of row lengths for the data
array's own size; neither composes over the existing single-buffer
machinery, and neither is stated by any committed task's `ensures`.
Exactly the outcome SPEC.md's own "Nested sequences" section predicted
for this column, "a named refusal or a flat encoding ... measured
first": the flat encoding measures out for READING, not for BUILDING.

Also named, by construction rather than measured against a real task
(neither committed task needs any of these): a seq<seq>-typed LOCAL
(`stmts()`'s "var" case, mirroring the plain seq-typed local's own
pre-existing refusal); a seq<seq>-typed ASSIGN target (`stmts()`'s
"assign" case, guarding the one remaining way a built nested value
could reach C, reassigning a parameter in place); a row VALUE reaching
`at`'s own base or ACSL/executable term position directly rather than
through `len` (the chained `m[i][j]`, or a row passed onward), which
falls through to `seq_var`'s pre-existing "non-variable" restriction
the moment it is not a bare variable, and is refused by name at each
of the three rendering points above when it IS one.

REGRESSION, measured by diff, not by re-running frama-c (the same
discipline the PAIRS note above uses for its own five-task check: the
C text is byte-identical, and frama-c is deterministic on identical
input): `abs`, `swap`, `tail`, `filter_pos`, `divmod_pair`, `min_max`,
one task from each pre-nested-sequences construct wave, relowered
(real and twin, twelve files) into a scratch
`out/agent-framac-nested-regress` (never `out/` itself) and diffed
against the committed `out/*.c`. All twelve files byte-identical: none
of these six tasks has a seq<seq>-typed name anywhere, so `typ()`'s
new `at` branch, `seq_var`'s widened check, and every new rendering
case above are reached by none of them, and the file's existing
behaviour for a plain seq, a pair, or neither is unaffected.

THE BUFFER-LENGTH GATE and THE INT-LITERAL GATE, both 2026-09-10, the
tenth sweep's own residual (COVERAGE-lifted-785.md, "Sole blockers"):
framac was the only column keeping 11 lifted-785 tasks out of the
seven-kernel bar, six `verified / malformed`, two `verified / unproved`,
one `verified / timeout`, two `abstain / abstain`. Measured against each
task's own twin file before touching anything, not assumed from the
category label.

THE BUFFER-LENGTH GATE fixes the six malformed tasks (double_array_
elements, replace, cmsc433's reverse, cubes, incrementArray, absIt), all
a fill/self-update seq return (EXACT mode, `_seq_len_track` resolves
`{ret}_n` to a closed form over params) whose `exit`-kind twin witness
(`interp.invariant_witness` dropping the task's own `len(ret)==len(...)`
invariant) sets the return's length to something other than the C
encoding's own `requires`-pinned value (double_array_elements: `s=[0]`
but witness `s_out=[]`, i.e. length 0 against `requires s_out_n ==
s_n == 1`). MEASURED (frama-c's own `-wp-report-json`, not inferred):
all six read `39/39`-shaped goal counts, certificate declared AND
accepted, MALFORMED via `verifiers/framac.py`'s coherence gate -- because
`{ret}_n` is fixed once at call entry in this encoding, never loop
state, `ensures {ret}_n == <len-expr>` is provable from `requires` alone
regardless of which loop invariant the twin dropped, so the WHOLE twin
verifies alongside the certificate: two accepted contradictions, refuting
nothing. Forcing the certificate's declared length to match `requires`
instead of the witness (tried first) does not produce REFUTED either: it
makes the certificate's own final assert unprovable (the surviving
content invariants plus `requires` already entail `ensures` at every
length-consistent exit, on every task measured), moving the cell to
`verified / unproved`, not `verified / refuted` -- REFUTED is genuinely
unreachable here, the mutation is a C-level no-op, same shape as the
`preservation` witness kind's own already-documented gap. `_exit_
certificate` (new: `_cert_ground_len`, re-deriving the witness's pinned
length the SAME way `lower()` does via `_seq_len_track`) now DECLINES
the certificate the moment the witness disagrees with that pinned
length, rather than emit one this adapter can only read as MALFORMED.
MEASURED after the fix, same six files, frama-c re-run: all six now read
`verified / verified` (real and twin C are, and remain, byte-identical
to before this fix -- diffed -- only the twin's certificate function
is now absent). Not the hoped `verified / refuted` -- honestly
unreachable, as measured above -- but out of MALFORMED and no longer
carrying a certificate this adapter cannot back soundly. CAPACITY mode
(filter_pos's own shape, length IS real loop state there) is untouched
by construction: the gate only fires when `_seq_len_track` resolves an
EXACT-mode length for the return at all, confirmed by relowering
filter_pos itself, byte-identical, still `verified / refuted`.

THE INT-LITERAL GATE fixes the two unproved tasks (both named `main_v`,
one dataset_C, one Generated_Code, byte-identical bodies): an `exit`
witness with `k = 2147483647` (INT_MAX) and `j = k + 1 = 2147483648`,
declared verbatim as `int j = 2147483648;` in the certificate. MEASURED
(a two-line probe, `int j = 2147483648; /*@ ensures \result ==
2147483648 */`): frama-c's C front-end types a decimal literal that
overflows `int` as the next type that fits (`long`), and initializing
`int j` from it is a narrowing conversion WP's own normalization does
NOT treat as the identity -- `[Stepout]` on a goal named `typed_nat_
..._ensures`, the exact shape that read both certificates' own
`typed_nat_t_certificate_assert` UNPROVED. This is a C LITERAL typing
fact, unrelated to THE SEMANTIC LINE's own -wp-rte/Typed+nat arithmetic
point above: an EXPRESSION built from two in-range literals carries no
such restriction (MEASURED, same probe: `int j = 2147483647 + 1;` scores
`4/4`, Qed, `\result == 2147483648` proved outright). Fixed by `_int_lit`
(new), which renders any ground int as a plain decimal when it fits
`int`'s 32-bit range and as a recursive `(INT_MAX + (...))` /
`(INT_MIN - (...))` sum otherwise, applied at all four sites this file
declares a ground int from a witness (`_value_certificate`'s param and
local loops, `_undef_certificate`'s param and replay-local loops,
`_exit_certificate`'s plain-int case). MEASURED: both tasks now read
`verified / refuted`, kernel-accepted certificate, `t_certificate`. The
other three certificate builders' own literal declarations were not
separately exercised by any measured witness (none in the 23-task
committed regression or the eight lifted tasks above hits an out-of-
range ground int through them), so this is a general robustness fix
applied uniformly rather than four separately-measured ones; in-range
values (everything previously measured) render byte-identically
(`_int_lit` is `str(n)` unchanged whenever `n` fits `int`), confirmed by
the regression below.

MEASURED, the regression bar (RULES): all 23 committed tasks (t/tasks/
*.json), framac column, relowered (real and twin) via `harness.run_task`
and diffed/re-verified against the pre-fix lowering. 20 read `verified /
refuted` before and after, byte-identical real AND twin C (abs,
all_nonneg, contains, count_matches, digit_sum, divmod_pair, factorial,
fib, filter_pos, first_even, gcd, is_prime, linear_search, max, min_max,
remainder, row_max_len, seq_max, sum_upto, swap, tail); swap_rows reads
its own already-documented ABSTAIN unchanged (a seq<seq> RETURN, a
different construct's named refusal, untouched by either gate). `reverse`
moves `verified / malformed` -> `verified / verified`: the SAME buffer-
length mismatch as the six lifted tasks above (`invariant-drop#1` twin,
witness `a=[], r=[0]`), previously accepted into the committed matrix as
a documented MALFORMED cell (the seq-value wave's own dated note),
correctly caught by the same gate -- same root cause, same fix, one cell
better, zero cells worse.

MEASURED, the eight targeted lifted-785 tasks: six MALFORMED -> VERIFIED
(honest `verified / verified`, THE BUFFER-LENGTH GATE); two UNPROVED ->
`verified / refuted`, COUNTING (THE INT-LITERAL GATE). Real programs
byte-identical to before both fixes on all eight, diffed. The remaining
three of the eleven "Sole blockers" were left alone, as scoped: the two
`abstain / abstain` tasks (factorialOfLastDigit, ghost/Triple) both
refuse on "spec_fun call in executable position" -- a real, substantial
feature gap (a recursive ACSL logic function has no C counterpart to
call from executable code; would need its own real C function mirroring
the spec_fun, not a small gap), unrelated to either gate here and left
untouched; the one `verified / timeout` (PVS/ex07_Hoangkim's swap)
carries an `undefined`-kind (off-by-one) twin, not `exit`, so neither
gate's own code path is ever reached for it (confirmed: relowered,
byte-identical to before, still timeout, budget exhausted on the real
function's own `typed_nat_..._8`/`..._9` goals -- a different, harder
cause this pass did not touch, per RULES).

THE TRACKED-LENGTH ENCODING, 2026-09-10, second pass: the design question
THE BUFFER-LENGTH GATE left open, on the seven `verified / verified`
lifted tasks (double_array_elements, replace, cmsc433's reverse,
incrementArray x2, cubes, absIt), all the identical fill/self-update
shape (a whole-buffer copy, then a self-update loop, the task's own
FIRST loop invariant a length equality). MEASURED FIRST BY HAND, per
RULES, before any lowering code changed: two raw C+ACSL probes mirroring
double_array_elements, real and an invariant-dropped twin, frama-c run
directly. Plain EXACT-mode rendering (`{ret}_n` bare, WP's frame rule
auto-preserving an unlisted local across a loop that never assigns it)
reproduced the gate's own vacuity exactly (twin 33/33, fully verified).
Routing `len(ret)` through a fresh loop-tracked local AND forcing that
local into the self-update loop's OWN `loop assigns` (nothing else)
flipped it: real still 35/35, twin's `ensures` plus two invariant-
preservation goals read an honest `[Stepout]`, the dropped invariant now
load-bearing. Implemented as `_ret_written_in_loop` (new) gating a
TRACKED-EXACT sub-case of the existing CAPACITY mode (same `ctx.seq_len`
threading, `\result` post-state, `int`-returning C function the append
idiom's own CAPACITY use already has; the one difference is the tracked
local STARTS at the closed form EXACT mode already computed, `ret_decl`'s
new initialized-declaration branch, rather than growing from 0) --
`lower()`'s own existing `assigned_names(w["body"], ctx.seq_len)`
piggyback (an assign TARGET that is also a `ctx.seq_len` KEY pulls its
length local into the frame too) already does the loop-assigns forcing
with no new code at all, confirmed by the hand probe's own negative
control (the same twin WITHOUT that forcing verified in full, 33/33,
reproducing the vacuity). `_exit_certificate`'s own BUFFER-LENGTH GATE
decline (THE BUFFER-LENGTH GATE, above) is skipped for exactly this
shape (`_ret_written_in_loop` on the twin body, mirroring `lower()`'s own
test): the coherence conflict that decline existed to avoid (the twin's
OWN `ensures` provable from `requires` alone, contradicting an accepted
certificate) cannot arise once `ensures` no longer references the
`requires`-pinned constant at all.

MEASURED, all seven, real and twin, `harness.run_task` into a scratch
OUT: all seven move `verified / verified` -> `verified / refuted`,
COUNTING, 7-13s each (baseline plain-EXACT wall was ~9-10s each, so no
material cost). The REALS did not lose -- the fallback RULES asked for
("if the reals lose... keep the pinned mode and record verified/verified
... with the measurement") was not needed, this landed clean on the
first lowering-code attempt, the hand probe having already de-risked the
mechanism. All seven now clear all seven kernels: this MOVES THE
COLUMN'S OWN TARGET, framac keeping 16 lifted tasks out of the bar, down
by seven to 9 (the remaining nine named individually elsewhere in this
note).

Applies to any seq return with this shape, not only the seven named:
scanning every lifted-785 task for `ret_written_in_loop` (the same test
`lower()` now runs) found 21 total. Of the other 14, MEASURED
(`harness.run_task`, not merely inspected): `pancakesort_flip__flip`
(already `verified / refuted` under plain EXACT mode, a DIFFERENT twin
shape than the length-drop this fix targets) stays `verified / refuted`
unchanged -- the regression bar this fix owes even outside the 23
committed tasks; `Clover_array_product__arrayProduct` (also
`verified / verified` before, same shape as the seven) moves to
`verified / refuted` too, a bonus not required by RULES but consistent
with the mechanism being general rather than the seven's own special
case. The remaining twelve (mostly more `verified / verified` instances
of the identical shape, two `timeout / timeout`, one `malformed /
malformed`) were not individually re-run this pass -- time-boxed, per
RULES' two-hour aim -- and are left for the next sweep or a future pass
to confirm; nothing measured here suggests any of them would move
adversely, since the mechanism only ever ADDS a real obligation
(`loop assigns` widened to a local nothing writes) to a REAL program that
already verified under the strictly weaker plain-EXACT rendering, never
removes one.

REGRESSION, the bar (RULES): all 23 committed tasks (`t/tasks/*.json`),
framac column, relowered (real and twin) via `harness.run_task` into a
scratch OUT. 20 read `verified / refuted` before and after, unaffected
(none has a seq return written inside a loop with a matching EXACT-mode
length, `abs` through `tail`, `swap`/`swap_rows` included -- `swap`'s own
seq return is loop-free, `_ret_written_in_loop` false, so plain EXACT
rendering is exactly as before, confirmed by the unchanged witness/
outcome). `swap_rows` reads its own already-documented ABSTAIN unchanged
(a seq<seq> return, a different construct's refusal, untouched).
`reverse` moves `verified / verified` -> `verified / refuted`: the exact
seven-task mechanism above, one committed cell better, zero worse.

BRANCH-FREE AND/OR (`_cert_cexpr`, `_has_partial_op`, both new), the same
pass: the two `verified / unproved` lifted tasks (hasOppositeSign,
isMonthWith30Days) were READ first, per RULES ("read the twin's
certificate; read the log"), not assumed. Both are loop-free, spec_fun-
free, a single ground `&&`/`||` of plain comparisons (`a=0` decides
`a<=0` outright). `-wp-report-json`, not inferred: the certificate's OWN
smoke goals (`typed_nat_t_certificate_wp_smoke_dead_code_s34/35/36` on
hasOppositeSign) read `Failed`/`Doomed` -- the SAME shape the PAIRS
RESIDUAL section's own `fz_p_pair_eq` finding already named as a general
`verifiers/framac.py` gap ("`_cert_status` has no matching exemption for
a doomed smoke goal inside the certificate function itself... nothing
pairs-specific about it, and this file may only be edited here"), here
hitting an ordinary `and`/`or` with no pairs and no div/mod involved at
all. That earlier note also names the ONE fix shape this file itself can
make: rewrite the ground-replayed operator branch-free so WP has no
short-circuit arm to find dead, exactly as `cexpr()`'s own pair `==`
case already does. Extended here, narrowly: `_cert_cexpr` now renders
`and`/`or` as bitwise `&`/`|` on its two (already 0/1) operands
WHENEVER NEITHER OPERAND CONTAINS A PARTIAL OPERATOR (`_has_partial_op`:
`at`/`div`/`mod`/`update`/`fill`/a call) -- the same safety condition the
pairs fix already relied on ("both fst/snd are unconditionally defined"),
generalized and named rather than re-derived per construct. Gated,
deliberately: the general `and`/`or` case, where a later operand's
definedness genuinely depends on an earlier one's truth
(`i < len(s) and at(s, i) > 0`), keeps its real C `&&`/`||` in EVERY
OTHER path (`cexpr()` itself, used for the real/twin function bodies,
is untouched; only the certificate's OWN ground replay, where every name
is already concrete and nothing can be out of bounds by the time
`_cert_cexpr` is asked to render it at all for an operand that clears
this check, gets the rewrite). MEASURED: both tasks move
`verified / unproved` -> `verified / refuted`, COUNTING. Regression: the
same 23-task run above (already re-verified after both fixes together)
shows no task whose certificate has an `and`/`or` with a partial operator
anywhere in either arm (`divmod_pair`, the only committed task with both
div/mod and a pair, has no `and`/`or` in its certificate replay at all)
taking the new path; all 23 read identical to the tracked-length note's
own regression above.

VACUOUS-3, read and diagnosed, not fixed (RULES: "decide whether the
lowering or the twin is at fault; fix only the lowering side, name the
rest"). The three `verified / vacuous` lifted tasks (both `main_v`
tasks, `countToAndReturnN`) share one shape: a scalar/pair loop, COMPARE-
FLIP on the guard (`i < x` -> `i <= x`), and the TASK's OWN loop
invariant `0 <= i <= x` (never touched by the twin operator, carried
over verbatim) becomes FALSE at the loop's actual exit under the
flipped guard (it now runs one iteration past `i == x`). `-wp-report-
json`, not inferred: the post-loop statement is scored `(Doomed)`,
`property` field `..._wp_smoke_dead_code_s13` (correctly classed
UNREACHABLE, not hypothesis vacuity, by `_UNREACHABLE_SMOKE`'s own
pattern) -- but `verifiers/framac.py`'s `_vacuity_smoke` extracts the
doomed goal's NAME from the console text via `_DOOMED_GOAL`
(`typed_nat_..._6`, a bare numeral, no smoke-class substring at all: the
class lives ONLY in the JSON `property` field, never in the printed goal
id), so `_UNREACHABLE_SMOKE.search` on that text finds nothing and the
file is misread VACUOUS. Separately, and correctly, one genuine
invariant-preservation goal (`..._8_preserved`) reads an honest
`[Stepout]` -- the twin really is broken, exactly as intended -- and the
certificate's OWN goals (checked directly, `t_certificate_assert*` all
`valid`) would mint REFUTED cleanly were the file not misclassified
first. This is NOT this lowering's defect: the task's own invariant is
rendered faithfully, the mutation is unmodified by construction (RULES:
"the twin never touches requires, ensures, spec_funs, or decreases" --
and the invariant list is body, not spec, but IS carried verbatim by
every twin operator here, COMPARE-FLIP included), and no C this file
could emit changes which console substring frama-c prints for a doomed
goal's bare id. Named for whichever pass next touches
`verifiers/framac.py`: teach `_vacuity_smoke`/`_DOOMED_GOAL` to read the
JSON report's `property` field (already parsed elsewhere in this same
adapter for other purposes) instead of, or alongside, the console text's
goal id. Left alone here, per RULES' file scope.

ABSTAIN-3, measured against the mandate ("if it does not land within an
hour, leave the abstain and name it") and NOT landed, left unchanged.
First correction to the prompt's own labeling, read directly rather than
assumed: of the three named, only TWO (factorialOfLastDigit, ghost/
Triple) actually abstain on "spec_fun call in executable position";
`mfirstCero` has NO spec_funs at all (confirmed: `task["spec_funs"] ==
[]`) and abstains on a DIFFERENT, unrelated gap ("conditionally evaluated
`at` in executable position: definedness not dischargeable by a plain
assert", `code_ats`'s own pre-existing short-circuit restriction, the
same class the pairs-residual note's `fz_v1pairs` finding already
names) -- out of this measurement's scope, left exactly as before, not
touched. For the other two: implementing a real C function per spec_fun
(a plain `int`/`bool` function mirroring the logic function's own `ite`
body via a C ternary, `requires`/`ensures \result == f(...)` bridging it
to the ACSL logic definition already emitted, and for the recursive case
(`factorial`) a `decreases` clause on the C function whose WP variant
obligation IS the termination proof, mirroring how a real recursive t
function already works per this file's own `recursion` mapping in the
module's opening section) needs at minimum: `cexpr()`/`_cert_cexpr`
support for `ite` in EXECUTABLE position (today only a spec-position
`term()` case exists), a new emission site in `lower()` alongside
`spec_fun_acsl`, and a new dispatch in `stmts()`'s/`cexpr()`'s `call`
case for a spec_fun name specifically (today an unconditional
NotImplementedError). Scoped out this pass: implementing AND regression-
testing that safely (every spec_fun-bearing task, committed and lifted,
non-recursive and recursive) does not fit the remaining budget honestly,
so nothing was written for it -- the abstain stays exactly as before,
named here rather than attempted partially and left inconsistent.

FILL DEFINEDNESS, fixed 2026-09-10, the morning fuzz reproduction's own
ground-truth finding. `reproduce.sh --families`'s combined run
(out/reproduce-families/) put one real gap on this column alone: the
probe `fz_p_fill_neg` (`requires n <= 100; r := fill(n, 0); ensures
len(r) == n`) is undefined at `n = -1` by SPEC.md ("fill ... DEFINED IFF
n >= 0"; `requires n <= 100` admits it, an "Undefined requires
(normative)" shape), every other kernel left it unproved (dafny, verus,
spark, lean, fstar: real unproved; rocq: real AND twin unproved), and
framac alone VERIFIED it, 14/14 goals.

READ FIRST, not assumed: `defs()`'s own `fill` case (above `pred()`)
already states the RULE, `n >= 0`, for a `fill` reached from a spec
position, and `seq_assign_lines`'s `fill` case (below `assigned_names`)
already emits `/*@ assert (n) >= 0; */` in EXECUTABLE position, the exact
same shape `at`'s bound check and `div`/`mod`'s `y != 0` check already
use. Both were present before this fix; the probe still verified anyway,
so the obligation this file already emits was not the gap -- something
downstream was making it FREE rather than PROVEN. MEASURED directly
(`frama-c`/WP on the probe's own generated C, before touching this
file): the seq-return clause block (`lower()`, just above `all_seqs.
append(ret)`) stated `requires {ret}_n >= 0;` UNCONDITIONALLY, immediately
before pinning `requires {ret}_n == <len-expr>;`. For `fill`'s own
count read straight off a bare int param (`ret_len_expr` = `n`, no other
`requires` constraining it), those two clauses TOGETHER are exactly
`requires n >= 0;` restated through the buffer's own bookkeeping name --
sound whenever `ret_len_expr` is independently nonnegative from some
OTHER clause already in scope (every committed seq-return task: `len(s)`
chains to `s`'s own `requires s_n >= 0;`, `tail`'s slice `b - a` chains
to the task's own `0 <= a <= b`, CAPACITY's `E` chains to an existing
seq length the same way), but for `fz_p_fill_neg` it silently ADDS `n >=
0` to the function's ASSUMED preconditions instead of leaving it the
proof obligation `defs()`/`seq_assign_lines` already meant to state:
totalizing the negative count by widening the contract's own domain, not
by giving the partial operator a fixed value. Two disjuncts SPEC.md's
own gap-hunting rubric names ("emits no definedness obligation ... or
its encoding totalizes"); measured to be the second one, the obligation
WAS emitted, its proof was just handed to it for free by a clause this
lowering added for an unrelated reason (sizing the buffer for `\valid`).

FIXED: the unconditional `requires {ret}_n >= 0;` line is gone (see the
comment left in its place, `lower()`, above `all_seqs.append(ret)`,
for the full reasoning); `\valid({ret} + (0 .. {ret}_n - 1))` needs no
companion sign assumption of its own, since ACSL's range `(0 ..
{ret}_n - 1)` is simply empty, and `\valid` over an empty range
vacuously true, whenever `{ret}_n <= 0` (measured on the same probe: the
file still parses and every OTHER goal discharges identically with the
line removed). MEASURED after the fix, `frama-c` on the probe directly:
13/14 goals, the domain assert `/*@ assert (n) >= 0; */` itself reading
an honest `[Timeout]` (Presburger-decidable but genuinely FALSE in
general, `n = -1` a counterexample; Alt-Ergo has no way to report
"provably invalid", only "not proved") -- the file is no longer
VERIFIED, having lost exactly the free hypothesis that was granting it.

MEASURED, `fuzz_lower.py --only framac --tasks fz_p_fill_neg --n 400
--seed 1 --flake 3 --jobs 2` (both readings flake-stable, `agreed=True`):
before, real `verified` / twin `timeout` (`vs-truth`: 1, `fz_p_fill_neg
expected=refuted got={'framac': 'verified'}`); after, real `timeout` /
twin `timeout` (`vs-truth`: 0). The probe now reads unproved (never
verified), matching the RULES bar; not REFUTED (no certificate mechanism
in this file targets a `requires`-only definedness gap of this shape,
the twin here being the SAME body under the SAME broken contract, not a
mutation), which is an honest, not a certified, non-agreement, exactly
like `033`/`049`/`143` below already read on the definedness family.

REGRESSION, MEASURED both ways, not assumed from the clause's own
narrow scope: (a) the 23 committed tasks (`t/tasks/*.json`), framac
column, `harness.run_task`: all 22 non-abstaining tasks (`swap_rows`
unaffected, its own already-documented seq<seq>-return refusal fires
before this clause block is ever reached) read `COUNTS` (verified real,
refuted twin) before and after, identical operator and witness on every
one -- byte-diffed the four SEQ-RETURN tasks specifically (`filter_pos`,
`reverse`, `swap`, `tail`, real and twin, eight files): each one differs
from the pre-fix lowering by EXACTLY the one dropped `requires {ret}_n >=
0;` line and nothing else, confirming the fix touches no other clause,
and frama-c's own verdict is unchanged on all eight because each of
those four tasks' `ret_len_expr` was already independently pinned
nonnegative by another `requires` in scope, exactly as reasoned above.
`AGREEMENT.md`'s own committed matrix (2026-09-10 10:49Z) matches this
run cell-for-cell. (b) the v1def fuzz family (8 tasks) plus the probe,
`--flake 3`, before and after: `fz_v1def_070`/`103` (`verified /
refuted`, unaffected -- both are `int`-returning tasks, never reaching
the seq-return clause block this fix touches at all) and `fz_v1def_
033`/`049`/`143` (`verified / timeout`, unaffected, see the DEFINEDNESS
TWIN CERTIFICATE note below) read byte-for-byte the same before and
after on every cell.

DEFINEDNESS TWIN CERTIFICATE (033/049/143), READ AND DIAGNOSED, not
fixed, per this pass's own scope. All three share one shape: `collapse-
if` drops an outer bounds-checking `if`, leaving a BARE, un-nested `if
(at(s, x) >= 0) ... else ...` as the twin body's own single top-level
statement -- an honest `undefined`-kind witness (`interp.exec_body`
raises `Undef` reaching `at(s, x)` with `x` now unconstrained). Read
directly, not inferred: `fz_v1def_033_twin.c` (`out/reproduce-families/`)
carries NO certificate function at all, only the plain twin lowering,
and its own unconditional `/*@ assert 0 <= (x) && (x) < s_n; */` (this
file's own `at`-bound obligation, correctly emitted) is genuinely
undischargeable with no `requires` constraining `x` -- an honest
`[Timeout]`, not a false VERIFIED, so this is NOT the FILL DEFINEDNESS
bug's own shape (nothing here is granted for free); it is a MISSING
certificate, the file scoring `verified / timeout` where a sound
`verified / refuted` is available but not reached. `_undef_certificate`
(above `_twin_loop`) is the reason: its own walk over `twin_body`
recognizes only a top-level `"var"`/`"assign"` statement (`for s in
twin_body: ... else: return None # if/while/return: not walked`,
DOCUMENTED already, its own scope limit) and returns `None` -- no
certificate -- the instant the twin's top-level statement is an `if`,
exactly what `collapse-if` leaves behind here. `fz_v1def_070`/`103`
count instead because THEIR `collapse-if` twins reduce the outer `if`
away entirely (the surviving branch is a single bare `r = 1;`), so the
walk's `"assign"` case fires directly -- a shallower shape the same
walker already handles, not evidence the walker handles `if` bodies in
general. This is the SAME NAMED gap `lower_verus.py`'s own
`_undef_obligation` (a harness-adjacent, per-backend helper, not
literally `harness.py` itself, but the identical shape, independently
implemented in every backend that has one, per this construct's own
section comment above `_undef_certificate`) already documents as "does
not walk into a loop or if body" -- confirmed here to be the live cause
for 3 of the 8 v1def cells, not merely a suspected one. Per RULES this
pass: named, not fixed (extending a certificate walker to recurse into
an `if`'s own branches is the class of change owned by whichever pass
next touches that shared shape across backends, not a one-file
definedness-fill fix); `033`/`049`/`143` stay `verified / timeout`,
unchanged before and after, exactly as measured above.

QUANTIFIER ABSTAIN (209/268/295), READ AND DIAGNOSED, not landed, same
scope discipline. All three read `abstain`, reason `"quantifier in ACSL
term position"` -- `term()`'s own `ite` case (above `_conj`) calls
`term(i['cond'], ctx)` on the ite's guard, and when that guard is itself
a `\forall`/`\exists` (all three tasks' bodies are `if (forall i;
range; P(i)) then r=1 else r=0`, mirrored verbatim into their own
`ensures`), `term()` raises `NotImplementedError("quantifier in ACSL
term position")` by name rather than render one, since a quantifier
produces an ACSL `\prop`, not a `term`, and `term()`'s "ite" case had
never been asked to bridge the two. READ, not assumed: is this
restriction honest (ACSL genuinely cannot express it) or merely
unmeasured? A direct probe (`frama-c`, `\result == ((\forall integer i;
0 <= i < n ==> s[i] >= 0) ? 1 : 0)`) PARSES and schedules goals cleanly
-- ACSL's conditional operator IS polymorphic over a `\prop` condition,
confirmed by running it, not by reading the manual -- so `term()`'s
outright refusal is NOT a real ACSL limitation, only an unmeasured gap
in this file, and `pred()`'s own "ite" case (above) already renders a
COND through `pred()`, not `term()`, and already handles `\forall`/
`\exists` correctly (its own "forall"/"exists" branch), so the fix
shape is a one-line swap (route `term()`'s ite-cond through `pred()`
instead of `term()` -- ite's cond is always bool-typed by the language's
own type system, exactly the invariant `pred()`'s dispatch already
assumes everywhere else it is called, so this is a strict
generalization with no case it could newly mis-render).

MEASURED before landing it (RULES: measure first) that this fix alone
would not move any of the three: patched in isolation and run directly
against `fz_v1def_209`'s own task, `lower()` proceeds past the ensures
clause exactly as expected and then raises a SECOND, DIFFERENT
NotImplementedError out of `stmts()`/`cexpr()`'s own body processing --
`"bounded quantifier in executable position"` (`cexpr()`, above
`_divmod_ternary_cexpr`) -- because these three tasks' BODY, not only
their `ensures`, branches on the identical `\forall`/`\exists`
(`if (forall ...) { r := 1; } else { r := 0; }`), and C has no
executable quantifier: discharging THAT gap needs compiling a bounded
quantifier into real, looping C (or an unrolled equivalent), a new
construct on the scale of the seq-value or nested-sequence waves above,
not a one-line rendering fix, and unmeasured. Landing the term-position
half alone would only rename the abstain reason these three tasks read,
never move a single verdict, so nothing was changed in this file for
either gap: both are named here, term-position honest-but-insufficient,
executable-position the real, substantially-sized blocker, left for
whichever pass takes up quantifier compilation. `fz_v1def_209/268/295`
read `abstain`, `"quantifier in ACSL term position"`, unchanged before
and after, confirmed by both fuzz runs above.

THE STRING LIBRARY, 2026-09-11 (SPEC.md "The string library (v1)",
ROADMAP 12.7, the wave after nested sequences). Seventeen members
(`split` two arities of one op, SPEC.md's own count); this pass lands
ONE, and names every other reachable position a NotImplementedError
abstain (`STRLIB_ABSTAIN`, above `_strlib_abstain`) rather than guess at
any of them, per this file's own discipline.

LANDED: `len(s.split())`, word_count's own shape and the only string-lib
use in any committed task that needs no SECOND unlanded member alongside
it. `t_wc{L}(s, n)` (T_WORDCOUNT_ACSL) is a recursive ACSL logic
function over the PREFIX length `n`, counting RUN STARTS (a
non-whitespace code point at `i` with `i == 0` or a whitespace one at `i
- 1`) rather than materializing any row -- the same "formula, not a
copy" move `_seq_len_render`'s existing `len(m[i])` case already makes
for a nested seq's row length. Whitespace is the measured 10-codepoint
set (SPEC.md's own words, `WS_CODEPOINTS`), never Python's `str.isspace`
(this kernel enumerates them, same reason interp.py gives). The
executable side, `t_wc_c`, is a real C loop with two invariants (the
index range, and `wc == t_wc(s, i)`) and a `lemma t_wc_terminates` for
`t_wc`'s own well-foundedness obligation (`_wf_obligation`'s own naming
convention, `{name}_terminates`).

MEASURED (frama-c 33.0 / alt-ergo 2.4.3-free, 2026-09-11), the one real
lemma this pass needed, named in THE WORK as "the split length law": a
FIRST version tracked `prevws` (whether the PRIOR code point was
whitespace) as loop STATE, one more invariant relating it to `is_ws(s[i
- 1])` through a separate ACSL `predicate is_ws`. That invariant's own
PRESERVATION goal TIMED OUT at every budget tried, up to 20,000,000
steps / 60s per goal (`typed_nat_t_wc_c_loop_invariant_2_preserved`),
and moving the same difficulty around (splitting the invariant, folding
`prevws` into a freshly-recomputed local instead of loop state) only
relocated which goal timed out, never removed it -- Alt-Ergo could not
connect the `is_ws` PREDICATE's unfold to the executable `?:` chain
computing the same fact, even though the two say the identical thing.
The fix that actually worked: delete `is_ws` as a separate symbol
entirely and write the same 10-way disjunction OUT, INLINE, at every
site (`_ws_or`, above `T_WORDCOUNT_ACSL`) -- the recursive definition,
the loop invariant (now just `wc == t_wc(s, i)`, the range, nothing
about a previous character), and the executable `?:` chain are now
syntactically the SAME formula up to the substituted term, and every
goal in the file (43/43 by hand at a raised budget, 74/74 including
smoke tests through `verifiers/framac.py`'s own `verify()` at its
DEFAULT budget) discharges Qed or a sub-250ms Alt-Ergo call. The lesson,
stated for whichever member needs a whitespace/character-class test
next (`strip`/`lstrip`/`rstrip`/`isalpha`/... all name one in
`STRLIB_ABSTAIN`): a named ACSL `predicate` for a flat disjunction of
equalities is not free here, inline it.

FIXED ALONGSIDE (not a string-lib member itself, but load-bearing for
word_count, which was blocked on it before any split-count logic even
ran): `stmts()`'s `var` case previously refused EVERY seq-typed local
outright ("seq-typed local variables are not supported... neither
committed task declares one" -- true when written, stale the moment
word_count and split_join were committed, since both declare one).
`_slice_alias_base` generalizes it to any local initialized from a
slice of a bare seq variable, `v := s[a..b]`: never a copy, an ALIAS
(`int *v = s + a; int v_n = b - a;`), honest because a slice of a
contiguous C array IS contiguous (SPEC.md "Sequences... slices":
`s[a..b]`'s element `k` is `s[a + k]`), with the slice's own domain
obligation (`0 <= a <= b <= len(s)`) still emitted by the SAME
`at_asserts` call every other slice read already gets. This is what
lets word_count's OFF-BY-ONE twin (`s[1..len(s)]`, SPEC.md's own
predicted shape) lower AT ALL rather than crash before reaching split:
its domain obligation is unprovable in general, exactly the UNDEFINED
half of its certificate at the witness `s = []` (`slice bounds
[1..0]`). A local from anything ELSE (a string-lib member's result,
`update`/`fill`, a nested seq/pair) still hits the general refusal,
unchanged in shape.

MEASURED, the three committed tasks, `harness.run_task` (flake 3):
word_count COUNTS (real VERIFIED, off-by-one twin REFUTED, witness `s =
[]`, matching SPEC.md's own prediction exactly, including the witness).
split_join REFUSED, and not by a string member at all: `lower()` refuses
it before any statement of the body is lowered, in `_ret_capacity`'s
pre-existing return-length gap (a `seq` return whose length no `ensures`
bounds has no buffer to size), the same NotImplementedError the family's
seq-returning shapes read; `strip`/`join` are named abstains (below) but
this task never reaches them (an independent re-measurement traced the
single frame on 2026-09-11; the first version of this note cited
`seq_assign_lines`'s fallback, which is not on the path). count_vowels REFUSED: `count` is a named abstain (below),
reached through this pass's own `_strlib_abstain` in ACSL term
position.

The committed matrix (26 tasks under `t/tasks/*.json`): relowered every
task under both this file and the pre-wave `git show HEAD:t/lower_framac.py`
and diffed. The 23 tasks that use no string-lib member are BYTE-IDENTICAL,
0 diffs -- this pass's every change is gated behind a new op name or a
seq-typed local, neither reachable from an unrelated task. The 3
string-lib tasks (word_count/split_join/count_vowels) are the only ones
whose lowered source changed, from a hard crash (word_count, split_join:
"seq-typed local variables are not supported"; count_vowels: "t has no
operator 'count'", `ValueError`) to either a real result (word_count) or
a clean, named `NotImplementedError` abstain (the other two) -- strictly
an improvement in honesty even where it is not yet a verdict.

ABSTAINED, each a `NotImplementedError` named in `STRLIB_ABSTAIN` (with
its own one-line reason) and reachable from ACSL term position, ACSL
predicate position, and (for `split`/`join` specifically, via
`seq_assign_lines`'s pre-existing generic fallback, reached only by a
task whose return length is bounded) a seq-typed assignment's
right-hand side: `join` (no backing-buffer construction for a rebuilt
seq); `strip`/`lstrip`/`rstrip` (a variably-shorter output seq has no
sized buffer -- no `ensures`-stated CAPACITY bound the general member
could size against, CAPACITY mode's own pre-existing gap); `replace` (a
variably longer-or-shorter output, and no non-overlapping-match scan
either); `tostr` (output length depends on `n`'s own runtime digit
count); `count`/`find` (no recursive ACSL definition of a general
non-overlapping/left-to-right substring scan is written yet -- the
length-1-pattern specialization count_vowels would settle for is
deliberately NOT taken, since SPEC.md states a member in specification
position is the SAME function, not a task-shaped instance of it);
`lower`/`upper` (an output the same length as its input, but no case-map
codegen is wired into `seq_assign_lines` for it); `isdigit`/`isalpha`/
`isupper`/`islower`/`startswith`/`endswith` (bool-returning, no buffer
issue at all, simply not reached by either committed task and left for
the next pass -- the cheapest remaining members, since each is a direct
`\forall`/`\exists` over an ASCII-range or a fixed-prefix/suffix
comparison with no lemma this pass's own budget could confirm was
needed). `split(s, c)` (the two-argument form) is abstained wherever it
is NOT `len`'s own direct one-argument argument: the row set it denotes
has no backing buffer in this encoding (the same "flat data+offsets has
nothing to build a fresh row set INTO" gap `lower()`'s own nested-seq
RETURN refusal names), and split_join's `join(split(s, c), [c])` needs
exactly that row set materialized, not merely counted.

OPEN, by name, for the next pass: split_join's own two members
(`join`, and `split` in its two-argument, row-materializing form) and
the "join-of-split law" lemma THE WORK names for it; count_vowels' own
`count` and the "count against a loop" incremental lemma; every other
un-landed member above. The fuzz family `v1strlib` (`fuzz_lower.py
--only framac`) was run over the 17 named cells at `--n 400 --seed 1
--flake 3 --jobs 8`; its own per-task outcome is recorded where this
pass's own measurement run wrote it (this file makes no claim about
that run's numbers beyond what it actually printed, HANDOFF/session
notes carry the log path).

CONFORMANCE 2026-09-11 (ROADMAP 13.4, the framac column's own 15-probe
assignment: elemwidth, seqeq_false, lit_empty, concat_len, lit_index,
pair_seq, nest_cell, nest_lit, nest_eq, nest_empty, str_splitempty,
str_countempty, str_findempty, str_tab, str_lowernonletter). Two closed,
both certificate bugs, not proof gaps: `fz_p_elemwidth` (real=unproved,
expected refuted) and `fz_p_seqeq_false` (real=timeout, expected refuted)
both root-caused to `_value_certificate`/`_undef_certificate`/
`_exit_certificate` declaring a ground SEQ ARRAY's elements with plain
`str(x)` instead of `_int_lit(x)` (THE INT-LITERAL GATE above covered
only the four plain-int sites it names, never the three seq/nested-seq
array-literal sites): `int t_cert_s[1] = {2147483648};` is not the value
2^31 under C's own literal-typing rule THE INT-LITERAL GATE measures
(frama-c casts it, `(int)2147483648`, a narrowing conversion WP's
Typed+nat does not treat as the identity), so the certificate replayed
at the WRONG ground value and its own `t_refutation_certificate` goal
read Stepout. Fixed by routing all five array-literal join sites through
`_int_lit` (measured: `fz_p_elemwidth` and `fz_p_seqeq_false` now read
`refuted / refuted`, kernel-accepted certificate). Separately,
`_value_certificate`'s stated seq-RETURN refusal (its own docstring:
"a documented gap ... fixing it needs its own measured probe this
construct wave did not need") is now measured (`fz_p_seqeq_false`'s real
IS a seq return) and closed WITHOUT the replay that docstring assumed
a fix would need: a VALUE witness's `_twin` is already the real body's
own trusted final value (harness.real_witness, computed independently by
interp.py's bounded scan), so the seq-return case declares `ret` as a
concrete backing array straight from that value (the same shape a seq
PARAM's witness already gets) rather than replaying `_cert_stmts` over
seq-typed assign/var statements (which render every local as a scalar
`n = rhs;`, wrong C for an array, and remain unfixed for that reason:
a seq-typed LOCAL mutated mid-body and then read back before return
still has no certificate route, unmeasured by any of this pass's probes).

The other 13 stay OPEN, named with the kernel's own exact abstain text
(measured directly, `lower_framac.lower(task, task["body"],
witness=harness.real_witness(task))`, 2026-09-11):

  fz_p_concat_len, fz_p_lit_index, fz_p_nest_cell, fz_p_nest_eq:
    "seq position holds non-variable {...}" -- `seq_var` (above) requires
    an `at`/`len`/`update`/`fill` argument to be a bare seq-typed
    variable; `s+u` (concat_len), a bare seq literal `[3,5,7]`
    (lit_index), and `at(m,i)`/`at(m,k)` used AS the seq argument of an
    outer `at` (nest_cell, nest_eq, one level of nested-seq indexing) are
    all seq-VALUED EXPRESSIONS in that position, not variables. Closing
    this needs either a temporary backing buffer materialized per such
    expression (concat_len, lit_index: a real allocation problem, no
    stack size is known statically for an arbitrary concat/literal in
    spec position) or, for the nested-seq row case specifically
    (nest_cell, nest_eq), a derived ACSL expression over the existing
    `m_data`/`m_off` encoding (`m_data[m_off[i] + j]`, no new buffer
    needed) -- a real, scoped fix, but its own measured probe and design
    pass, not attempted here for lack of that measurement.
  fz_p_nest_lit:
    "conditionally evaluated `at` in executable position: definedness
    not dischargeable by a plain assert" -- an `if`-guarded nested-seq
    element read where the guard is not syntactically identical to the
    `at`'s own bounds check; the general conditional-definedness gate
    `stmts()` already states for the plain-seq case, unclosed here for
    the nested-seq one either.
  fz_p_pair_seq:
    "a pair with a seq component is refused by this lowering: a struct
    field returned BY VALUE has no clean ACSL value semantics for a
    buffer pointer plus a length" -- a named, load-bearing architectural
    refusal (see the PAIRS section above `_pair_field_c`): closing it
    changes the pair ENCODING itself (a struct field cannot own a
    pointer+length pair that outlives the struct's own scope the way a
    plain seq param/return does), not a local fix to one probe.
  fz_p_nest_empty, fz_p_str_splitempty:
    "nested seq (seq<seq>) RETURN: building a fresh row set has no
    encoding in this lowering" -- `lower()`'s own named refusal (its
    docstring above, unchanged): the flat data+offsets encoding sizes
    ONE buffer against ONE bound; a built seq<seq> return needs the
    offsets array's own count sized against a SECOND, independent bound.
  fz_p_str_countempty:
    "string library member `count` reaching executable position: a
    general non-overlapping substring count has no recursive ACSL
    definition in this lowering yet" -- OPEN, by name, in THE WORK
    section above already (unchanged by this pass).
  fz_p_str_findempty:
    "string library member `find` reaching executable position: ... no
    recursive ACSL definition of a left-to-right substring search is
    lowered yet" -- same family as `count`, also pre-existing and named.
  fz_p_str_tab:
    "nested seq (seq<seq>) local variables are not supported by this
    lowering; only a seq<seq> PARAMETER, read via `len`/`at`, is
    supported" -- `str_tab`'s own body declares a seq<seq>-typed LOCAL
    (THE ENCODING note's own stated scope limit, unchanged).
  fz_p_str_lowernonletter:
    "seq return 'r''s length is not statically determinable from the
    task's params ... and no `ensures` ... gives a CAPACITY bound either"
    -- `_ret_capacity` (above) reads a bound directly off one `ensures`
    shape; `str_lowernonletter`'s own `ensures` states none, so CAPACITY
    mode has nothing to size the output buffer's `requires` against.

Regression, all 34 committed tasks under t/tasks (not a sample): every
one lowers BYTE-IDENTICAL before and after this pass's fix (diffed
directly against `git show HEAD:t/lower_framac.py`'s own `lower()`, same
witness both sides). The five named for this pass (abs, gcd, sum_upto,
count_vowels, reverse) at flake 3: abs, gcd, reverse, sum_upto all
`verified/refuted` (byte-identical, unaffected); count_vowels stays
`abstain` (the string-library gap named above, unchanged either side).

ROADMAP 13.4, framac-fast, 2026-09-11. `fz_p_at_body`'s undefined witness
carries no `_site`/`_expr`/`_value` (`harness.real_witness` found the
undefined `at` inside the BODY, not the `ensures`), so it reached
`_undef_certificate`, whose ground replay walked only straight-line
`var`/`assign` statements and returned None the moment it met the body's
first (and, for `at_body`, only) top-level `if` -- a documented scope
limit ("if/while/return: not walked"), never exercised because no
committed task's undefined witness needed it. `_undef_certificate` now
descends into `if`, resolving each condition against the accumulated
ground state exactly THE CERTIFICATE's other replay (`_cert_stmts`) does
for the value/exit kinds: `interp.ev` decides which arm is live, an
`/*@ assert cond; */` (or its negation) is emitted for the untaken arm,
and the walk continues into the taken one. A mis-decided branch cannot
mint a certificate, only fail one (that assert becomes a real WP goal); a
correctly-decided one lets `at_body`'s own `0 <= s_n && s_n < s_n`
obligation (always false, `s_n = 0` at the witness) reach the certificate
exactly as `at_oob`/`at_neg`/`at_zero`/`attotal`'s ensures-level witnesses
already do. Measured: `fz_p_at_body` x framac moves real TIMEOUT ->
REFUTED (the probe's own expectation), the four siblings' certificates
unchanged (byte-identical `t_certificate` bodies, confirmed by re-running
them through this file), and the six committed tasks named two paragraphs
above regrade identically (abs/gcd/reverse/sum_upto verified/refuted,
count_vowels/split_join abstain, all byte-identical), since none of their
witnesses is `_kind == "undefined"` and the new `if`-branch never fires
for them. The same pass proposed a verifier-side route for `fz_p_badrec`,
`fz_p_badrec2`, `fz_p_badvariant`, `fz_p_biglen` and `fz_p_seqlen` (each
expected `rejected`, each reading TIMEOUT or VACUOUS here): re-ask every
goal alt-ergo spun on with `-wp-prover qed` alone and read Qed's `Unknown`
as UNPROVED. Not merged: WP runs Qed before alt-ergo on every goal, so a
goal alt-ergo spun on is by construction one Qed could not close, and its
`Unknown` adds nothing; that is a TIMEOUT relabeled. Measured at the merge
(2026-09-11, alt-ergo 2.4.3 and Z3 4.8.12 through a private why3 config,
`Typed+nat`, an axiom-free file): `lemma l: 0 < 0;` reads `Stepout`
under alt-ergo and `Timeout` under Z3, so no prover status this column
can reach names a false ground fact, the doctrine this file already holds
for REFUTED. The five stay open; the honest route is the one REFUTED
already takes, a witness the harness computes (a measure that fails to
decrease at a concrete input) replayed as a ground certificate Qed proves,
and that is the next framac item by name.

SEQ VALUE, executable position (2026-09-11, ROADMAP 13.4, the framac-seq
item). THE ENCODING above (candidate B, a caller-provided output buffer)
already gives a seq VARIABLE a C representation; the thirteen abstains
this pass measured (fz_p_lit_empty, fz_p_concat_len, fz_p_lit_index,
fz_p_pair_seq, fz_p_nest_cell, fz_p_nest_lit, fz_p_nest_eq,
fz_p_nest_empty, fz_p_str_splitempty, fz_p_str_countempty,
fz_p_str_findempty, fz_p_str_tab, fz_p_str_lowernonletter) were every
place a seq-VALUED EXPRESSION (a literal, a concat, a nested cell, a
row, a string-library result), not a bare seq variable, reached
`seq_var`'s own "non-variable" refusal -- in FOUR distinct rendering
sites this pass had to patch together, not one: `cexpr` (the executable
C VALUE), `code_ats`/`at_asserts` (the executable definedness assert in
front of the statement), `term`/`_seq_len_render`/`_seq_at_render` (the
`ensures`/ACSL TERM rendering of the SAME expression), and `defs` (the
`ensures`'s own DEFINEDNESS obligation) -- a seq expression appearing in
an `ensures` reaches all four, and missing any one still abstains the
whole task. The design decision, taken in this pass, is: NEVER
materialize a literal/concat/slice/nested-cell into a fresh buffer
first; render each as a closed-form C expression instead, reusing
memory THE ENCODING already owns:
  - a `seq` literal `[e0, ..., en-1]` indexed by `at`: a C99 compound
    literal, `((int[]){e0, ..., en-1})[k]` -- stack-scoped, no malloc,
    capacity exactly the literal's own element count (`cexpr`'s `at`
    case; the matching bounds-check tag is `code_ats`'s new `"atn"`).
  - `len` of a literal/slice/concat expression that is never assigned
    to a buffer (`fz_p_concat_len`'s `len(s + u)`): a closed-form sum/
    difference of the operands' own `_n` fields, `_seq_val_len_c`,
    never touching memory.
  - `[] + e` assigned to a seq-typed target: SPEC.md's own identity
    (`len([]) == 0`), folded to a plain `target := e` copy in
    `seq_assign_lines`, landing regardless of whether the target is
    EXACT- or CAPACITY-tracked (the pre-existing CAPACITY-only `+`
    restriction is for the APPEND idiom specifically, an orthogonal
    case this identity bypasses rather than loosens).
  - a nested seq's CELL, `at(at(m, i), j)` (`m[i][j]`): THE ENCODING's
    own flat data+offsets pair already has the value, `m_data[m_off[i]
    + j]`, no row ever materialized -- landed in all four rendering
    sites (`cexpr`, `code_ats`'s new `"atrow"` bounds tag, `_seq_at_
    render`, `defs`).
  - `len([e0,...])` in ACSL TERM position (`fz_p_lit_empty`'s own
    `ensures len([]) == 0`): `_seq_len_render` gained the same literal
    case `cexpr`'s `len` already has.

Landed, measured real=verified matching `_expect` (framac column,
`conformance.py`'s own manifest, before 46/66 PASS, after 49/66,
`git diff` isolates each site): fz_p_lit_empty, fz_p_lit_index,
fz_p_concat_len -- all three of "literal" and "concat", the pass's own
first two items in the stated order.

Also landed, NOT a new capability but a SAFETY fix surfaced while
reaching for "nested": `cexpr`'s `==`/`!=` on two seq- or nested-seq-
typed operands used to fall through to `ARITH`/`CMP`'s generic
"render both sides, glue with the C operator" path, which for a BARE
seq variable renders `s == t` as raw C POINTER comparison -- never
extensional, silently WRONG, the exact hazard this file's own honesty
rules exist to prevent. No committed task or prior probe reached it (a
seq/nested-seq `==` previously only ever appeared in `ensures`, which
`pred()`'s own matching branch already renders correctly); reached for
the first time by `fz_p_nest_eq`'s body, `r := (m == n)`. Fixed by an
explicit `NotImplementedError` (an honest abstain, not a guessed loop:
extensional equality needs a `\forall`-shaped walk over both buffers,
which is a STATEMENT, not a value `cexpr` can return inline) rather
than by teaching `cexpr` a loop-based rendering this pass did not
measure.

Stopped here, each named by the kernel's own exact abstain/WP message,
none relabeled: "nested" beyond the cell case, "pair", and "string
members" (this pass's own remaining order) all sit behind gaps this
pass's seq-VALUE-representation fix does not reach:
  - fz_p_nest_cell, fz_p_nest_lit: reach a DIFFERENT, pre-existing,
    orthogonal gap once the seq-value abstain itself is cleared --
    `code_ats`'s own "conditionally evaluated `at` in executable
    position: definedness not dischargeable by a plain assert" (an
    `at`/`len(at(...))` sitting in a LATER conjunct of `and`/`or`,
    conservatively refused because a later conjunct's safety can
    depend on an earlier one, C's own short-circuit semantics --
    unrelated to how a seq VALUE is represented, not touched by this
    pass).
  - fz_p_nest_eq: `pred()`'s seq-equality branch (`ensures ... at(m, k)
    == at(n, k)`, ROW equality inside a `\forall`) still calls
    `seq_var` on an `at(...)` node directly; even were that rendered
    (a `_seq_at_render`-shaped row-data read, not attempted this pass),
    the BODY's own `r := (m == n)` would still hit this pass's own new
    safety refusal above -- both sides of the cell must land, and
    neither does.
  - fz_p_nest_empty, fz_p_str_splitempty: "nested seq (seq<seq>)
    RETURN: building a fresh row set has no encoding in this lowering"
    -- a nested seq RETURN needs a SECOND, row-shaped CAPACITY bound
    (an offsets array sized against its own data-dependent count, on
    top of the data array's own), which THE ENCODING's CAPACITY
    machinery (`_ret_capacity`) was built for exactly one dimension;
    extending it to two is a fresh design, not a rendering-site fix.
  - fz_p_str_tab: "nested seq (seq<seq>) local variables are not
    supported by this lowering; only a seq<seq> PARAMETER ... is
    supported" -- a nested-typed LOCAL has nowhere to live in THE
    ENCODING at all (no param slot, no return-buffer machinery either);
    same missing dimension as the RETURN gap above, from the other
    side.
  - fz_p_str_countempty, fz_p_str_findempty: "string library member
    `count`/`find` reaching executable position: a general non-
    overlapping substring count has no recursive ACSL definition in
    this lowering yet" -- pre-existing, named in THE WORK section
    above; `count`/`find` need a NEW ACSL logic function (a recursive
    substring search/count), not a seq-value rendering fix.
  - fz_p_str_lowernonletter: "seq return 'r''s length is not
    statically determinable from the task's params ... and no
    `ensures` ... gives a CAPACITY bound either" -- `lower(...)` is not
    in `_expr_seq_len`'s recognized op set (it preserves its argument's
    length, an easy addition), but `lower`/`upper` also have no
    EXECUTABLE rendering at all in `seq_assign_lines` (no per-element
    ACSL letter-range predicate + C loop exists for them yet); the
    CAPACITY message is the FIRST wall reached, not the only one.
  - fz_p_pair_seq: "a pair with a seq component is refused by this
    lowering: a struct field returned BY VALUE has no clean ACSL value
    semantics" -- named and scoped out deliberately at `_pair_field_c`
    (this file's own pair-value-machinery section), a struct-encoding
    redesign (a seq component would need its own pointer+length pair
    INSIDE the struct, changing how every pair-typed param/return is
    passed), well outside a rendering-site fix.

Cost of what landed: the compound-literal `at` rendering is bounded by
construction (a literal's own syntactic element count, no malloc, no
runtime size); the nested-cell rendering adds no new state, only reads
THE ENCODING's own existing `m_data`/`m_off` arrays through a second
level of indexing; the `[] + e` identity and the `len`-of-concat/slice
closed form add no new C code shape at all, only new algebra over
existing `_n` fields. None of the four rendering sites this pass
touched (`cexpr`, `code_ats`/`at_asserts`, `_seq_len_render`/
`_seq_at_render`, `defs`) gained a new representation; every fix is a
new CASE recognized by an EXISTING one.

THE MEASURE WITNESS CERTIFICATE, 2026-09-11 (ROADMAP 13.4, framac-measure).
`fz_p_badrec`, `fz_p_badrec2`, `fz_p_badvariant` (fuzz_lower.py's own
"well-definedness IS the termination obligation" family, SPEC.md gate 3)
each break a `decreases`/loop-variant obligation this file has always
emitted as a lemma (`f_terminates_k` for a spec_fun's self-call, the
loop's own `loop variant` PO) but never certified: the note directly
above THE SEMANTIC LINE (top of this file) MEASURED that alt-ergo 2.4.3
reads Stepout and Z3 4.8.12 reads Timeout on the naked false lemma these
three probes reduce to (`0 < 0` for `fz_p_badrec` at its own witness), so
no prover status this column can reach names the fact false -- the exact
gap the value/undefined/exit certificates above already closed for a
false `ensures`, unclosed here until now for a false measure.

The fix is the same doctrine, restated for a new witness kind. Two new
pieces do the work and neither lives in this file:
  - interp.MeasureViolation (interp.py): raised, opt-in only
    (`St(check_measures=True)`), by `ev`'s spec_fun "call" case and
    `exec_body`'s "while" case, the first time a concrete recursive call
    or loop iteration's measure fails "strictly below the caller's, and
    the caller's non-negative" -- the well-foundedness rule stated once,
    checked at both sites, never assumed satisfied because a lemma about
    it was emitted.
  - harness.real_witness (harness.py): catches it in the SAME two scans
    that already catch `Undef` (evaluating `ensures`, and re-executing
    the body), with `check_measures=True` set ONLY on those scans' own
    `St` (interp.Reference's own value-computing scan is untouched, so
    every existing witness kind and every committed task's `real_witness
    is None` measurement is unaffected -- checked directly, see the
    dated note in harness.py and t/test_real_witness.py's new cases).

`_measure_certificate` (below, alongside `_value_certificate` and
`_undef_certificate`) needs no replay of the body at all: the witness's
`_caller_measure`/`_callee_measure` are ALREADY the two ground integers
interp.ev computed while walking the real execution, so the certificate
is the bare arithmetic fact itself, `assert t_refutation_certificate:
!((caller >= 0) && (callee < caller))`, at those two literals
(`_int_lit`, THE INT-LITERAL GATE's own routine, in case either measure
falls outside `int`'s 32-bit range). MEASURED (frama-c 33.0 / alt-ergo
2.4.3-free / Z3 4.8.12, 2026-09-11): all three probes' real column now
reads `refuted / rejected` (`_measure_certificate` accepted, matching
conformance.py's REJECTED_OK) where it previously read `unproved /
rejected` (the emitted termination lemma was the only route, and no
prover status on it ever named the fact false); the twin side of each
cell is unaffected (no probe in this family has a twin: `harness.
twin_cached` refuses all three on "no-operator"/"no-witness", so only
the real's own column moves). The other six kernels' verdicts on these
three probes are unchanged by this file (each rejects a bad measure
through its own, independent check; framac is the only column this
patch touches), and this file's dispatch (`certificate()`) still returns
None, exactly as before, for a witness kind it does not recognize -- a
lowering handed a witness shape it does not know still lowers the real
plainly, as it always has.

THE WITHHELD-DEFINITION CERTIFICATE, 2026-09-11 (ROADMAP 13.4,
framac-axiom, worktree /home/tmcuzzort/tup/.claude/worktrees/
wf_127b4bf3-1c9-1). The note directly above ("THE MEASURE WITNESS
CERTIFICATE") ends honestly unfinished for two of its own three probes:
`_measure_certificate` reads REFUTED on `fz_p_badvariant` (a loop's own
variant) but verifiers/framac.py's module docstring records
`fz_p_badrec`/`fz_p_badrec2` (a spec_fun's own `decreases`) staying
VACUOUS before AND after that patch, for a reason unrelated to the
certificate: `spec_fun_acsl` (below) renders EVERY spec_fun as a full
recursive ACSL definition, `logic integer g(integer n) = <body>;`, and WP
assumes a `logic ... = ...` definition as an AXIOM without checking that
its recursion terminates (this function's own docstring line, unchanged
by this patch). `fz_p_badrec`'s `g(n) = g(n) + 1` at `decreases 0` is an
axiom with no solution -- MEASURED (frama-c 33.0, 2026-09-11):
`verifiers.framac._recursive_defs`/`_consistency_probe` (its own
"-wp-fct smoke" instrument) reads this inconsistent BEFORE the file ever
reaches goal generation, so `_vacuity_smoke` scores the whole file
VACUOUS and the certificate goal -- proved, if it were ever reached -- is
never asked about. A certificate is a proof INSIDE a theory; an
inconsistent theory proves everything, so a certificate accepted there
would prove nothing new, and the fix is not to the certificate at all.

The fix: withhold the definition. `lower()` (below) reads the witness's
own `_kind`/`_site` -- set by harness.real_witness exactly as THE MEASURE
WITNESS CERTIFICATE note describes, `_site` a spec_fun's NAME when a
recursive CALL is where the measure broke (interp.MeasureViolation's own
two raise sites; a loop's `_site` is turned into an int index before this
file ever sees it, so `fz_p_badvariant`'s witness names no function and
nothing here withholds anything for it, unchanged) -- and passes
`declare_only=True` to `spec_fun_acsl` for exactly that one function on
this one task. The emitted ACSL becomes a bare declaration, `logic
integer g(integer n);`, no `=`, no body, no termination lemma: this is
SOUND, not merely convenient, because the witness IS the task's own
`decreases` failing at a concrete input the harness computed and
`_measure_certificate` already restates as ground arithmetic (see that
function's own docstring) -- the recursive equation a full definition
would axiomatize is not well founded, so there is no fact to axiomatize
honestly, and none is. A declaration still gives every `ensures`/`term`
call to `g` a signature to typecheck against (ACSL elaborates a call from
the signature alone), and verifiers/framac.py's own `_LOGIC_DEF` regex
requires a trailing `=` to call a block a "definition" at all (its own
comment: "never a bare declaration: only definitions are assumed as
axioms, and only those can make the theory inconsistent") -- so a
declared-only `g` is invisible to `_recursive_defs`/the consistency
probe: no axiom is emitted, so there is nothing for WP to doom, and the
certificate goal is reached and checked exactly as
`_measure_certificate`'s own docstring already argues it should be.
Withheld ONLY for the function the witness names, ONLY when the
witness's `_kind` is "measure": every other spec_fun on the same task,
and every task with no such witness (every committed task under t/tasks,
`test_real_witness.py`'s own claim, reconfirmed here by lowering all 34
with and without an explicit `witness=None` and diffing byte for byte --
`test_framac_measure_axiom.py`'s `committed_recursive_tasks_are_byte_
identical`), still gets the full recursive definition, unchanged.

MEASURED, 2026-09-11 (frama-c 33.0 / alt-ergo 2.4.3-free / Z3 4.8.12,
python3 test_framac_measure_axiom.py and the conformance/AGREEMENT
re-runs their own dated notes below record): `fz_p_badrec`/
`fz_p_badrec2`'s real column moves `vacuous -> refuted`, each carrying
the witness's own two ground measures verbatim in its emitted C (`!((0
>= 0) && (0 < 0))` for badrec, `!((1 >= 0) && (2 < 1))` for badrec2);
`fz_p_badvariant`'s cell is untouched (still `refuted / refuted`, no
spec_fun on that task to withhold anything for). t/conformance.py's full
66-task manifest, framac column only, moves FAIL cells 12 -> 10 (exactly
these two rows; every other FAIL/PASS cell, and every other row's own
source text, byte-identical before and after -- diffed, not eyeballed).
The 34 committed tasks under t/tasks (gcd, sum_upto, factorial, fib,
digit_sum, is_prime, contains, count_matches among them, and every task
carrying a spec_fun) lower to byte-identical C both before and after this
patch, real and twin, because none carries a witness for `real_witness`
to find (each is a correct, committed program); graded again at flake 3
against t/AGREEMENT.md's own recorded cells for the eight named
recursive tasks, unchanged (`verified / refuted` throughout). The other
six kernels are untouched by this patch (it edits only this file's
`spec_fun_acsl` and its one call site in `lower()`) and were not
re-measured for that reason, not by assumption -- reading the diff is
the check.

FRAMAC-SEQ2, ROADMAP 13.4, 2026-09-11 (worktree
/home/tmcuzzort/tup/.claude/worktrees/wf_09045dfc-4fd-2). The ten seq
cells above, taken in the stated order, land the FIRST item only and
stop there, each remaining cell named by the kernel's own exact
message, unchanged from before this pass (measured both sides,
`python3 <scratchpad>/framac-seq2/measure.py before` then `after2`,
`<scratchpad>` = /tmp/claude-1004/-home-tmcuzzort/b04a1fce-9e33-441b-
804f-aa0d13f350ee/scratchpad):

  LANDED: `count`/`find` (SPEC.md "The string library (v1)"), general
  recursive ACSL definitions in EXECUTABLE position (T_STRFIND_ACSL,
  `_has_countfind`, the new `cexpr` branch immediately before
  `_strlib_abstain`'s call). `fz_p_str_countempty` and
  `fz_p_str_findempty` both move real ABSTAIN -> VERIFIED (matching
  `_expect`), the only two of the ten this pass reaches. The receiver
  must be a bare seq-typed variable and the pattern either a bare
  seq-typed variable or the empty literal `[]` (an empty pattern needs
  no real buffer: `\valid_read(t + (0 .. -1))` is vacuously true of any
  pointer, so the receiver's own pointer stands in at length 0); a
  non-empty literal, concat, or slice pattern is a NAMED remaining gap
  (the `cexpr` branch's own `NotImplementedError`, not reached by
  either probe). `count`/`find` in ACSL TERM or PREDICATE position (a
  `requires`/`ensures`/invariant calling either symbolically, e.g.
  `count_vowels`'s own `ensures`) is UNCHANGED, still the
  `STRLIB_ABSTAIN` refusal, its message updated only to say
  "specification position", not "no recursive ACSL definition ...
  yet" (false now that one exists for executable position).

  MEASURED obstacle, not guessed: `count(s, []) == len(s) + 1`
  (SPEC.md's own identity) does not follow from `t_count_c`'s own
  proved contract (`\result == t_count(s, ns, t, nt, 0)`, the general
  recursive value) by a single call -- that is an INDUCTION over the
  start index with no fixed bound, which Alt-Ergo 2.4.3 cannot perform
  from one ground instantiation of an uninterpreted recursive logic
  function. A `lemma` stating the closed form directly, quantified
  over the start index, TIMED OUT at the pinned budget (20,000,000
  steps / 60s), the same failure mode T_WORDCOUNT_ACSL's own note
  above measured for `is_ws` as a separate predicate symbol. The fix:
  `t_countempty_rec`, a RECURSIVE C FUNCTION (not a lemma, not a loop)
  with a `decreases` clause and a two-part `ensures` (the closed form
  AND the bridge to `t_count`) -- Frama-C's own proof obligations for a
  recursive function are checked by well-founded induction on its
  `decreases` measure, so the recursive call's own contract becomes
  the induction hypothesis for free and each step needs only ONE
  unfold of `t_count`'s defining equation. `find(s, []) == 0` needed no
  such helper: it is a single unfold at the start index (`t_eqat` over
  an empty range is vacuously true there), which Alt-Ergo already
  discharges directly from `t_find_c`'s own contract. Standalone
  verification, before wiring into the dispatch (frama-c 33.0 /
  alt-ergo 2.4.3-free, /tmp/claude-1004/-home-tmcuzzort/b04a1fce-9e33-
  441b-804f-aa0d13f350ee/scratchpad/framac-seq2/t_strfind.c):
  `t_find_c`, `t_count_c`, `t_countempty_rec` and both empty-pattern
  harness functions, 103/103 goals, Qed and Alt-Ergo only, smoke
  31/31.

  STOPPED, unreached this pass, each still the kernel's own exact
  message (byte-identical to before, `measure.py`'s "before" and
  "after2" runs both attached under that same scratchpad directory):
  fz_p_nest_cell, fz_p_nest_lit ("conditionally evaluated `at` in
  executable position: definedness not dischargeable by a plain
  assert"), fz_p_nest_eq ("seq position holds non-variable
  {'op': 'at', ...}"), fz_p_nest_empty, fz_p_str_splitempty ("nested
  seq (seq<seq>) RETURN: building a fresh row set has no encoding in
  this lowering"), fz_p_str_tab ("nested seq (seq<seq>) local
  variables are not supported by this lowering"), fz_p_str_lowernonletter
  ("seq return 'r''s length is not statically determinable ...");
  fz_p_pair_seq ("a pair with a seq component is refused by this
  lowering"). Items 2 through 6 of the stated order (the executable
  `lower`/`upper` with a length bound, the guarded definedness assert,
  the extensional-equality loop, nested locals/return, the pair-with-
  seq redesign) are none of them attempted; each is a fresh design,
  not a rendering-site fix, per THE WORK's own scoping above.

  REGRESSION, measured both sides: all 34 committed tasks under
  t/tasks, framac column, `python3 grade.py --tasks tasks --kernels
  framac,dafny --flake 3 --jobs 8`: byte-identical to
  t/AGREEMENT.md's own framac column, 31 `verified/refuted`, 3
  `abstain/abstain` (count_vowels, split_join, swap_rows -- none use
  `count`/`find` in executable position, count_vowels's own `count`
  calls are all in its `ensures`/loop invariant, ACSL term position,
  untouched), sum_upto and reverse both keeping their `invariant-drop`
  refuted twin. The framac column of the ROADMAP 13.4 conformance
  suite (66 probes, `probe_manifest()`/`run_items()` restricted to
  framac via `run_par.probe_backends()`'s own `present` filter, the
  script is /tmp/claude-1004/-home-tmcuzzort/b04a1fce-9e33-441b-804f-
  aa0d13f350ee/scratchpad/framac-seq2/conf_framac.py): 51/66 PASS
  before this pass's edit (git show HEAD:t/lower_framac.py restored
  for that one run), 53/66 PASS after, the two new PASSes being
  exactly fz_p_str_countempty and fz_p_str_findempty (diffed field by
  field between the two runs' JSON, `conf-before.json`/`conf-
  after.json` under that same scratchpad directory) -- no other
  cell's verdict moved either direction, no PASS lost.

  ROADMAP 16.2's own framac rows (t/COVERAGE-lifted-785.md,
  2026-09-10, RE-MEASURED 2026-09-11 rather than trusted: `python3
  grade.py --tasks <task-set> --kernels framac,dafny --flake 3 --jobs
  8`, twelve named tasks copied from the 59-lifted set into
  /tmp/claude-1004/-home-tmcuzzort/b04a1fce-9e33-441b-804f-aa0d13f350ee
  /scratchpad/framac-seq2/roadmap162-tasks, byte-identical result
  before and after this pass's edit, `r162-before/table.md` vs
  `r162-after/table.md` under that scratchpad differing only in their
  timestamp header): none of the twelve calls `count`/`find` anywhere,
  so none of the abstain/malformed/timeout cells named in ROADMAP 16.2
  moves. One drift from the 2026-09-10 row, honestly named rather than
  silently inherited: `dafny_synthesis_task_id_257__swap` reads
  `verified / refuted` (agreement) at this measurement, not the
  `verified / timeout` ROADMAP 16.2 groups it under alongside 591 and
  625 -- 591 and 625 both DO still read `verified / timeout` here,
  unchanged; 257 itself is not a framac blocker any more (a kernel
  change since 2026-09-10 the ROADMAP row was never updated for, not
  a change this pass made -- confirmed by running the SAME "before"
  file, `git show HEAD:t/lower_framac.py`, and seeing 257 already
  agree there). The other eleven: 240/262/577/586 still ABSTAIN
  (seq-concat-into-exact-length-return, pair-with-seq, spec_fun-in-
  executable-position, seq-concat-with-a-non-target left operand --
  four DISTINCT gaps, none of them `count`/`find`); 470 still
  MALFORMED; 591/625 still `verified / timeout`; 3/605 still
  `timeout / timeout`; 598/86 still `timeout / refuted` -- none of
  these nine reached by this pass's own scope (T_STRFIND_ACSL touches
  only `count`/`find`), named here rather than attempted, since fixing
  any of them is a fresh, unrelated gap (a length-bound redesign, a
  struct redesign, a spec_fun-inlining decision, or a proof-budget/
  strategy investigation into an existing TIMEOUT, none of them the
  ten-cell order this pass follows). The 15 `ds15-new` tasks (the same
  scratchpad's `roadmap162-tasks-15`) measured the same way, same
  result: byte-identical before/after, none call `count`/`find`.

FRAMAC-SEQ3, ROADMAP 13.4, 2026-09-11 (worktree
/home/tmcuzzort/tup/.claude/worktrees/wf_127b4bf3-1c9-2). The eight
abstaining seq cells named for this round, taken in the stated order
(fz_p_nest_cell, fz_p_nest_lit; fz_p_nest_eq; fz_p_nest_empty,
fz_p_str_splitempty; fz_p_str_tab; fz_p_str_lowernonletter;
fz_p_pair_seq): item 1 (fz_p_nest_cell, fz_p_nest_lit) LANDS; the other
six STOP at the same design boundary FRAMAC-SEQ2's own note above
already drew for them, each remeasured (unchanged) rather than trusted.

  LANDED, item 1: GUARDED DEFINEDNESS (`code_ats`'s own docstring above
  has the design). `fz_p_nest_cell`'s and `fz_p_nest_lit`'s own measured
  message before this pass, byte-identical both, `python3
  <scratchpad>/framac-seq3/measure.py` (`<scratchpad>` =
  /tmp/claude-1004/-home-tmcuzzort/b04a1fce-9e33-441b-804f-aa0d13f350ee
  /scratchpad): "conditionally evaluated `at` in executable position:
  definedness not dischargeable by a plain assert" -- both bodies put
  `at(m, i)`'s own row read inside a LATER conjunct of an `and` guard
  (`_ncg`'s fourth conjunct `j < len(at(m, i))`, only safe to evaluate
  once the first two conjuncts, `i`'s own bound, already hold), and
  `code_ats` used to REFUSE any `at`/`div`/`mod` reached under such a
  guard outright rather than risk an unconditional assert that would be
  unsound off that guard. The fix threads the accumulated guard (the
  tuple of Expr conditions C's own short-circuit `&&`/`||`/`==>`/`?:`
  already established true by the time a later operand is reached) down
  through `code_ats` instead of collapsing it to a plain "reached
  unconditionally or not at all" boolean, and `at_asserts` renders a
  non-empty guard as an ACSL implication, `(guard) ==> (bound)`, so the
  bound is demanded only on the path where the operator is actually
  evaluated -- never weaker than the obligation actually is (an
  unconditionally reached `at` still gets the exact same bare assert as
  before, guard `()`), never stronger either (a guard that is FALSE at
  some input leaves that input's own bound obligation vacuously
  discharged, exactly C's own semantics). `fz_p_nest_lit` additionally
  reached a second, narrower gap once the guard fix cleared its own:
  `len(at([[1,2],[3]], k))` (a row's length, read off a nested SEQ
  LITERAL rather than a variable) had no executable rendering at all
  (`cexpr`'s `len`/`at` case called `seq_var` on the literal base and
  raised "seq position holds non-variable"); fixed the same way item 1
  of FRAMAC-SEQ2 fixed `at` of a plain literal, a C99 compound literal
  of each row's own (compile-time-constant) length, indexed by `k`.
  MEASURED, real=verified matching `_expect` both (frama-c 33.0/alt-ergo
  2.4.3-free/Z3 4.8.12): `fz_p_nest_cell` and `fz_p_nest_lit` both
  `verified / timeout` after this pass (before: `abstain / abstain`);
  the twin's own TIMEOUT is an honest "no proof" (REJECTED_OK's own
  vocabulary), not a claimed refutation, and is not this pass's own
  scope to chase (neither probe's `_expect` is "rejected", so the twin
  column is not graded by `conformance.py`'s own rule, `grade()`'s
  docstring above, comparing the real outcome only).

  STOPPED, unreached this pass, each still the kernel's own exact
  message (byte-identical to before, `measure.py`'s own output, this
  pass's own commit of it): `fz_p_nest_eq` ("seq position holds
  non-variable {'op': 'at', 'args': [{'var': 'm'}, {'var': 'k'}]}" --
  `pred()`'s row-equality branch calling `seq_var` on an `at(...)` node
  directly, ROADMAP 13.4's own item 2, "a C loop computing the equality
  with its own invariant the kernel proves", a fresh statement-shaped
  rendering path `cexpr` cannot return inline, not a rendering-site
  patch); `fz_p_nest_empty` and `fz_p_str_splitempty` ("nested seq
  (seq<seq>) RETURN: building a fresh row set has no encoding in this
  lowering ..."; item 3, a second CAPACITY dimension); `fz_p_str_tab`
  ("nested seq (seq<seq>) local variables are not supported by this
  lowering ..."; item 4, the same dimension from the local side);
  `fz_p_str_lowernonletter` ("seq return 'r''s length is not statically
  determinable ..."; item 5, an executable `lower` with a length bound);
  `fz_p_pair_seq` ("a pair with a seq component is refused by this
  lowering ..."; item 6, the buffer-encoded pair return). Each is the
  fresh design FRAMAC-SEQ2's own note above already named it as, not a
  rendering-site fix the four sites this pass owns (`cexpr`, `code_ats`/
  `at_asserts`, `term`/`_seq_len_render`/`_seq_at_render`, `defs`) can
  close alone; none attempted here for the same reason, not a new one.

  REGRESSION, measured both sides (`<scratchpad>/framac-seq3/
  conf_framac.py before`/`after`, `probe_manifest()`/`run_items()`
  restricted to framac): 54/66 PASS before this pass's edit, 56/66 PASS
  after, diffed field by field between `conf-before.json`/`conf-
  after.json` -- the only two cells that moved are `fz_p_nest_cell` and
  `fz_p_nest_lit`, both FAIL->PASS, no PASS lost either direction. The 34
  committed tasks under t/tasks, framac column, `python3 grade.py
  --tasks tasks --kernels framac,dafny --flake 3 --jobs 8`: byte-
  identical to t/AGREEMENT.md's own framac column, cell for cell (31
  `verified/refuted`, 3 `abstain/abstain` -- count_vowels, split_join,
  swap_rows -- none of the 34 reaches either of this pass's own two
  changed sites: no committed task's `at`/`div`/`mod` sits behind a
  LATER `and`/`or`/`implies` conjunct, and none declares a nested seq
  literal).

FRAMAC-SEQ4, ROADMAP 13.4, 2026-09-12 (worktree
/home/tmcuzzort/tup/.claude/worktrees/wf_092dca46-e41-1). The six seq
cells FRAMAC-SEQ3's own note above left STOPPED (fz_p_nest_eq;
fz_p_nest_empty, fz_p_str_splitempty; fz_p_str_tab;
fz_p_str_lowernonletter; fz_p_pair_seq), taken in the stated order:
none of the six moves cell-to-verified this pass, each remeasured
(`python3 <scratchpad>/framac-seq4/measure.py`, `<scratchpad>` =
/tmp/claude-1004/-home-tmcuzzort/b04a1fce-9e33-441b-804f-aa0d13f350ee/
scratchpad) rather than trusted, and one genuine rendering-site bug
`pred()` had on the FIRST of the six is fixed along the way, named
below rather than claimed as a landed cell since it does not move
fz_p_nest_eq's own outcome.

  FIXED, not a landed cell: `pred()`'s `t0 == "seq"` branch (ACSL
  predicate position's extensional `==`/`!=`) used to require BOTH
  operands to be bare seq variables via `seq_var(args[0], ...)` /
  `seq_var(args[1], ...)`, pasting `{v}_n`/`v[__k]` directly. That is
  too narrow the moment a "seq"-typed operand is a ROW extracted from a
  nested seq rather than a bare variable -- `at(m, k)`, itself
  "seq"-typed by `typ()`'s own polymorphism (SPEC.md "Nested
  sequences") -- which is exactly the shape `fz_p_nest_eq`'s own
  `ensures` states ("two nested seqs are equal iff same length and
  equal rows"): `\forall k; ... at(m, k) == at(n, k)`. MEASURED before
  this fix (frama-c 33.0, `harness.real_witness` plus
  `lower_framac.lower` standalone): `fz_p_nest_eq` raised
  `NotImplementedError: seq position holds non-variable {'op': 'at',
  'args': [{'var': 'm'}, {'var': 'k'}]}` out of `pred()`, i.e. before
  WP ever saw a goal -- a lowering CRASH on the `ensures` clause
  itself, not an honest ABSTAIN naming a real gap. The fix routes both
  operands through `_seq_len_render`/`_seq_at_render` (their own
  READ-position rules) instead of `seq_var` directly: both already
  reduce to the exact same `{v}_n`/`v[__k]` for a bare seq variable
  (verified by inspection, not merely hoped: `_seq_len_render`'s own
  fallback path IS `ctx.seq_len.get(seq_var(e, ctx.env), ...)`, the
  same call the old code made inline), and `_seq_at_render`'s own
  "at(nested, i)" case -- built for `fz_p_nest_cell`'s `m[i][j]` in
  FRAMAC-SEQ3 -- already renders indexing INTO a row the identical
  formula way when the row itself (`at(m, k)`) is passed as `e` and the
  comparison's own quantified index as `k_render`: `m_data[m_off[k] +
  __k]`, no row ever materialized. So `fz_p_nest_eq`'s `ensures` now
  renders cleanly (MEASURED, same standalone call, no exception).

  STILL ABSTAIN, item 1 (fz_p_nest_eq): the crash moved, the outcome
  did not. The task's BODY computes `r := (m == n)` directly (extensional
  seq equality assigned to a bool-typed name, EXECUTABLE position, not
  only inside the `ensures` the fix above now handles), which reaches
  `cexpr`'s own pre-existing named refusal, unchanged by this pass
  (`==`/`!=` case, "SEQ VALUE, executable position, item 4"): MEASURED
  after this fix, `fz_p_nest_eq: NotImplementedError: seq extensional
  equality (==/!=) reaching executable position directly (assigned to a
  bool-typed name, not used only in an `ensures`/ACSL predicate): this
  lowering has no C VALUE rendering for it, only a loop would compute
  it, and this pass does not build one` -- byte-identical wording to
  `cexpr`'s own docstring there, unmoved because this pass makes no
  change to `cexpr`'s executable-value path. This is the design
  boundary ROADMAP 13.4's own item 2 already named ("a C loop computing
  the equality with its own invariant the kernel proves") and where
  this pass stops for this cell: `cexpr` returns a single C VALUE
  expression string with no way to emit a preceding STATEMENT (a loop
  with its own invariant) from inside that return, so closing item 2
  needs a new statement-shaped rendering path threaded through
  `stmts()`'s own assignment codegen, not an edit to any of the four
  sites this pass owns (`cexpr`, `code_ats`/`at_asserts`,
  `term`/`_seq_len_render`/`_seq_at_render`, `defs`) -- a fresh
  design, not attempted here, named rather than guessed at.

  STOPPED, unreached this pass, each remeasured (byte-identical to
  FRAMAC-SEQ3's own note, `measure.py`'s output above): `fz_p_nest_empty`
  and `fz_p_str_splitempty` ("nested seq (seq<seq>) RETURN: building a
  fresh row set has no encoding in this lowering ..."; the second,
  row-shaped CAPACITY dimension FRAMAC-SEQ2's own note already named,
  a fresh design over the seq value machinery section, not a rendering
  site); `fz_p_str_tab` ("nested seq (seq<seq>) local variables are not
  supported by this lowering ..."; the same dimension from the local
  side); `fz_p_str_lowernonletter` ("seq return 'r''s length is not
  statically determinable ..."; an executable `lower` with a length
  bound equal to the input's, a fresh CAPACITY design of its own, not a
  rendering-site fix either); `fz_p_pair_seq` ("a pair with a seq
  component is refused by this lowering ..."; the buffer-encoded pair
  return, `_pair_field_c`'s own certificate territory this pass's
  scope excludes -- another builder's file this wave, untouched here
  in any case). None of the four is attempted: each is the identical
  fresh-design gap FRAMAC-SEQ2 and FRAMAC-SEQ3 already scoped out of a
  rendering-site patch, and this pass's own four owned sites (the same
  ones just listed) have nothing left in them to try for any of the
  four without first building the second CAPACITY dimension, the
  nested-local storage, the length-bound design, or the pair-with-seq
  encoding respectively -- none of which is a `cexpr`/`code_ats`/
  `at_asserts`/`term`/`_seq_len_render`/`_seq_at_render`/`defs` edit.

  REGRESSION, measured both sides: the 34 committed tasks under
  t/tasks, framac column, `python3 grade.py --tasks tasks --kernels
  framac,dafny --flake 3 --jobs 8`: byte-identical to t/AGREEMENT.md's
  own framac column, cell for cell (31 `verified/refuted`, 3
  `abstain/abstain` -- count_vowels, split_join, swap_rows, none of the
  34 reaching `pred()`'s seq `==` branch on a row-extracted operand).
  The framac column of the ROADMAP 13.4 conformance suite (66 probes,
  `probe_manifest()`/`run_items()` restricted to framac,
  `<scratchpad>/framac-seq4/conf_framac.py before`/`after`): 58/66 PASS
  both before and after this pass's edit, diffed field by field between
  `conf-before.json`/`conf-after.json` -- ZERO cells differ (the
  `pred()` fix is invisible to every one of the 66 probes' own outcome,
  since `fz_p_nest_eq` is the only one reaching the fixed branch on a
  row operand and its own cell stays ABSTAIN either side, moved from a
  crash to a named refusal, not to a PASS). ROADMAP 16.2's own named
  framac cells (t/COVERAGE-lifted-785.md, r20: 240, 262, 414, 576, 577,
  586, 603, 69, 470, copied into `<scratchpad>/framac-seq4/
  roadmap162-tasks`, graded `python3 grade.py --tasks
  roadmap162-tasks --kernels framac,dafny --flake 3 --jobs 8`): all
  nine read the SAME message as before this pass's edit (240 the
  exact-length-return concat gap, 262 and 69 read through this pass's
  own fixed `pred()` branch with no change since neither reaches it --
  262 is the pair-with-seq refusal, 69 is `cexpr`'s own executable-
  equality refusal, the same one `fz_p_nest_eq` reaches; 414 a bounded
  quantifier in executable position; 576 the same executable-equality
  refusal as 69; 577 a spec_fun call in executable position; 586 a
  non-target left-operand concat; 603 a length bound the `ensures`
  cannot supply; 470 malformed), none of them this pass's own scope
  (T_STRFIND_ACSL/FRAMAC-SEQ2/3 already named these as distinct,
  unrelated gaps). Nothing in the 34-row AGREEMENT.md matrix or the 462-
  probe conformance suite's other six columns is touched by this
  pass's edit (one function, `pred()`'s own `==`/`!=` `t0 == "seq"`
  case, in this one file).

2026-09-12, ROADMAP 16.2 framac-3 ("frame facts in loop bodies, the
sweep abstains, then the seq design cells"): the first of the three
named timeouts, appendArrayToSeq (task 106), turned out to be TWO
separate gaps, both fixed here, not the one the wave-I note guessed.
(1) THE FRAME-FACT GAP, `stmts()`'s own new docstring above its
definition: a scalar local declared before a `while` and never
reassigned inside that loop's body (`h := len(a);`) is now stated as an
equality `loop invariant`. Additive only, threaded through `_prefix`
with C-scoping copy semantics (an `if`-branch or a loop body gets its
own copy, never leaking a fact back out or across siblings). (2) THE
CAPACITY-MODE BARE-SEQ-ASSIGN BUG, `seq_assign_lines`'s `"var" in e`
branch: `target := src` (a bare seq copy, `r := s;`) used `target`'s
own buffer CAPACITY as both the copy bound and the fresh length-local
value; correct only in EXACT mode. Under CAPACITY mode (a later
append into the same buffer) this over-read `src` and set the
length-local to a value larger than what was actually copied, so the
task's own `len(r) == len(s) + i_v2` invariant was FALSELY stated at
loop entry -- not a search budget problem, an unsound premise alt-ergo
correctly could not prove. Fixed to use `src`'s own logical length in
CAPACITY mode; EXACT mode (`bound=None`) is byte-identical to before.
MEASURED (t/grade.py --tasks <106,460,86 copied from
t/out/lifted-tasks/> --kernels framac,dafny --flake 3 --jobs 6, this
worktree): 106 appendArrayToSeq framac real=timeout -> verified,
agreeing with dafny's verified/refuted; twin unaffected (refuted
throughout, `flake_check` unchanged). The frame-fact fix ALONE did not
move 106 (measured as an intermediate step: same two goals timed out,
`loop_2_preserved`/`loop_6_established`, byte-identical failing-goal
names before and after that fix alone) -- it was goal `loop_6_established`
that actually turned out FALSE, not merely hard, once (2) above was
found by hand-tracing WP's own goal name back to its source invariant.
The frame-fact fix is kept anyway: additive, sound, and the shape wave
I's note named (a guard/decreases/body definedness obligation needing a
prefix constant) does occur elsewhere in this lowering even though it
was not what blocked 106 specifically; no regression on the 34-task
AGREEMENT.md matrix (framac column re-measured, byte-identical, all 31
verified/refuted plus the 3 named abstains) or the 66-item conformance
manifest's framac column (0 of 66 cells changed, measured against a
byte-identical copy of this file's pre-wave state, framac column only
per this file's own regression-bar instructions).

The other two named timeouts are NOT frame-fact gaps, measured directly
by hand-tracing WP's own failing goal name (frama-c -wp-report-json)
rather than assumed from the wave-I note:
  - 86 centeredHexagonalNumber HAS NO LOOP AT ALL (`result = 3*n*(n-1)+1;
    return result;`, no while, no prefix local to state a fact about).
    Its lone timeout is `..._t_2`, the second `ensures` (`\result >= 0`),
    a NONLINEAR arithmetic goal (`n*(n-1) >= 0` for `n >= 0`) alt-ergo
    2.4.3 cannot discharge at the pinned budget without a case-split
    hint -- the same class of gap wave I's own note named for
    isNonPrime/isPrime's divisor-bound lemma ("alt-ergo 2.4.3 cannot
    discharge the product fact ... at fifty times the pinned budget").
    Not attempted here: a nonlinear-hint mechanism is a different,
    larger design than a loop-body frame fact, out of this pass's named
    scope. Exact message: "timeout budget exhausted on
    typed_nat_dafny_synthesis_task_id_86_centeredHexagonalNumber_t_2".
  - 460 getFirstElements DOES have the `h == lst_n` frame fact (emitted
    by fix (1) above) but still times out, on THREE goals: `ensures_2`
    (the final forall over `result`), `loop_5_preserved` (the loop's own
    forall invariant, `result[j] == lst_data[lst_off[j]]`), and
    `assert_2` (the capacity bound `result_len + 1 <= result_n`) -- a
    doubly-indexed quantifier (`lst_off[j]`, then `lst_data` at that
    offset) alt-ergo cannot instantiate at the pinned budget even with
    every scalar fact already known; a genuinely different capability
    gap (quantifier triggering/instantiation, not a missing premise) not
    attempted here. Exact message: "timeout budget exhausted on
    typed_nat_dafny_synthesis_task_id_460_getFirstElements_t_ensures_2,
    ..._loop_5_preserved, ..._assert_2".

The nine named abstains/malformed (COVERAGE-lifted-785.md r21) were
each re-measured against this wave's own edited file (`lower_framac.lower`
called directly on the copied task JSON; none of the nine's lowering
path touches `seq_assign_lines`'s `"var" in e` branch or a `while`
this wave's frame-fact loop touches, so none moved and none was
expected to): 240 replaceLastElement and 586 splitAndAppend, the
pre-existing named seq-concatenation refusals (EXACT-length return,
non-target left operand); 262 splitArray, the pair-with-seq-component
refusal; 414 anyValueExists and 576 isSublist/69 containsSequence, the
pre-existing bounded-quantifier/seq-equality executable-position
refusals; 577 factorialOfLastDigit, the spec_fun-in-executable-position
refusal; 603 lucidNumbers, the no-CAPACITY-bound refusal. 470
pairwiseAddition is confirmed MALFORMED at the frama-c level itself
(not this wave's own code): `frama-c -wp ...` on its own emitted C
aborts parsing with "invalid operands to binary -; unexpected \U0001d539
and \U0001d539. Ignoring code annotation" / "Frama-C aborted: invalid
user input" at the `t_div`-defining assert (line 24 of the emitted
file), an ACSL TYPE error (boolean subtraction, valid as plain C,
rejected in ACSL logic position) in the div/mod bridging assert this
lowering already emits for every div/mod task -- a distinct, pre-
existing lowering bug this pass diagnosed but did not fix (out of this
pass's named scope, "frame facts in loop bodies").

ROADMAP 13.4's six seq design cells (nest_eq, nest_empty,
str_splitempty, str_tab, str_lowernonletter, pair_seq) were NOT
reached this pass: the design stopped at the sweep abstains above,
each requiring its own new rendering mechanism (a second capacity
dimension for nested returns, an executable seq-equality loop, a
length bound derived differently), not a scoped extension of the
frame-fact/capacity fixes landed here. Named, not attempted.

FRAMAC-NESTED, ROADMAP 13.4 item (a), 2026-09-12 (worktree
/home/tmcuzzort/tup/.claude/worktrees/wf_2056d1d0-df2-2). Item (a) of
the design order this pass's own task named ("the extensional seq
equality loop in executable position ... a statement-shaped rendering
path stmts() emits before the assignment, a C loop with its own
invariant WP proves, its result assigned to the bool target"), built
against the three cells named for it: fz_p_nest_eq (nested seq<seq>
PARAMETERs), 576 IsSublist and 69 ContainsSequence (flat seq operands,
a slice and a nested-seq row respectively).

BUILT: `_seq_eq_top`/`_seq_eq_operand_c`/`_seq_eq_loop`/`_seq_eq_value`
(new functions, just above `stmts()`), wired into `stmts()`'s
"assign"/"return"/"if" branches (the three call sites that used to hand
`cexpr()`'s return value straight to a C assignment or an `if` header,
none of them able to accept a preceding STATEMENT from inside `cexpr`'s
own return). `cexpr`'s own named refusal (SEQ VALUE, executable
position, item 4) is UNCHANGED text for every shape this pass does not
recognize (a seq literal or `+` concatenation operand): `_seq_eq_top`
gates which `==`/`!=` nodes route to the new loop machinery at all, so
`cexpr` still raises, unmoved, for anything `_seq_eq_operand_c` cannot
turn into a pointer/length pair.

MEASURED (frama-c 33.0 / alt-ergo 2.4.3-free, 2026-09-12, `python3
grade.py --tasks <dir> --kernels framac,dafny --flake 3 --jobs 4/8`,
task JSON copied from `t/out/lifted-tasks/` into
/tmp/claude-1004/-home-tmcuzzort/b04a1fce-9e33-441b-804f-aa0d13f350ee/
scratchpad/framac-nested/roadmap-tasks, and `fuzz_lower.py --n 0 --only
framac --tasks fz_p_nest_eq,... --flake 3` for the probe itself):

  LANDED to a full agreement cell: 576 IsSublist, `abstain / abstain`
  -> `verified / refuted`, matching dafny's own `verified / refuted`
  cell exactly (`compare-flip#1`, `sub=[], main_v=[] -> real False,
  twin slice bounds [1..1] outside 0 <= a <= b <= 0`). The 66-probe
  conformance manifest and the 34-task AGREEMENT.md matrix do not
  contain this task (it is a ROADMAP 16.2 lifted-sweep row, not a
  committed task or a fuzz probe), so this is a NEW pass, not a moved
  cell in either of those two files; ROADMAP 16.2/COVERAGE-lifted-785.md
  itself is not this pass's file to edit.

  MOVED, not landed: `fz_p_nest_eq` (the 66-item framac conformance
  manifest's own probe), `abstain -> timeout` (real AND twin both
  timeout; the manifest still reads this cell FAIL either side, byte-
  identical PASS/FAIL split before/after, 58/66 both times, diffed
  field by field). Traced by hand (`frama-c -wp ... fz_p_nest_eq.c`,
  no `-wp-fct` restriction): 19/22 goals proved, 3 TIMEOUT --
  `..._ensures`, `..._loop_invariant_2_preserved` (the outer row loop's
  own doubly-quantified invariant, `\forall k; ... && (\forall j; ...)`,
  preserved across one more row), `..._loop_invariant_3_preserved` (the
  inner cell loop's own, preserved across one more cell). The nested
  case's own invariant asks alt-ergo to re-derive a `\forall`-inside-
  `\forall` fact for the OLD prefix `[0, i)` from the SAME hypothesis
  while also folding in the freshly-proved fact for index `i` -- a
  doubly-quantified instantiation problem, the same capability gap
  already named for task 460 getFirstElements above ("a doubly-indexed
  quantifier ... alt-ergo cannot instantiate ... at the pinned budget
  even with every scalar fact already known ... not attempted here").
  RULES forbids raising the pinned budget to chase it, so this is
  reported as the honest TIMEOUT it is, not relabeled and not silently
  left at the OLD "abstain" text: an abstain hid a construct this
  lowering had no rendering for at all; a timeout says the rendering
  exists and the kernel could not close its own proof obligation at the
  pinned budget, a materially different, more honest claim.

  MOVED, not landed: 69 ContainsSequence, `abstain -> timeout` (real
  AND twin), traced the same way: `..._loop_4_preserved` (the outer
  loop's own `\exists k; ... && \forall __k; ...` invariant,
  preservation), `..._ensures`, `..._loop_7_preserved` (the inner
  equality loop's, folded into the outer's own `preserved` goal since
  the inner loop's `__seq_eq0`/`__seq_eq0_i` are declared fresh each
  outer iteration). The task's own spec states a REAL existential
  (`result != 0 <==> \exists ...`), not the near-tautological
  `\exists ... ==> \true` IsSublist's own `ensures` happens to state
  (which is why IsSublist's outer invariant preservation was
  Qed/Alt-Ergo-cheap: proving an implication whose consequent is
  literally `\true` costs nothing), so this is the same doubly-
  quantified (`\exists` this time, not `\forall`, but the same
  instantiation shape) capability gap as fz_p_nest_eq's own, not a
  bug this pass's four owned sites can close.

  FIXED ALONG THE WAY, not a landed cell of its own but what actually
  let IsSublist's real=verified / twin=refuted cell close at all:
  `_undef_certificate`'s `walk()` (a certificate-replay function this
  pass never intended to touch) had a SCALAR RE-DECLARATION bug,
  dormant until this pass's own fix let IsSublist's framac lowering
  succeed for the first time (before, the whole task ABSTAINED before
  any certificate was ever built, so `walk()` never saw a real
  multi-iteration loop). The old code keyed the C `int` prefix off
  `"var" in s` alone: an "assign" to the RETURN name (`result`, never a
  "var" statement anywhere in v1) got NO declaration on its own first
  assignment (an undeclared-identifier reference), and an "assign"
  REASSIGNING a "var" name across this replay's own unrolled loop
  iterations (`i_v`, incremented once per concrete pass) got a FRESH
  `int` every time, "redefinition of 'i_v' in the same scope" (frama-c's
  own exact parse error, measured before this fix on IsSublist's
  compare-flip twin certificate). Fixed with a `declared: set`
  (seeded with the task's own param names before `walk` runs), keyed
  on the NAME's own first sight in this call regardless of which
  statement kind assigned it: `int {nm} = ...;` once, per name, `{nm} =
  ...;` every time after. MEASURED: IsSublist's twin cert now reads
  `t_refutation_certificate` proved, `real=verified twin=refuted`,
  matching `_expect`; no other certificate shape this pass touched
  changes (the 34-task AGREEMENT.md matrix and the 66-cell conformance
  manifest's framac column are both BYTE-IDENTICAL before/after this
  whole pass, this fix included, diffed field by field -- see the
  REGRESSION paragraph below).

  STOPPED, unreached by design (out of item (a)'s own stated operand
  scope, `_seq_eq_operand_c`'s own named refusal, not guessed at): a
  seq LITERAL or `+` concatenation operand of a top-level `==`/`!=`
  reaching this loop. No committed/fuzzed/lifted task measured needs
  this shape yet.

  ITEMS (b)/(c)/(d) of this pass's own stated build order (the second
  CAPACITY dimension for a nested seq<seq> RETURN/LOCAL,
  fz_p_nest_empty/fz_p_str_splitempty/fz_p_str_tab; an executable
  `lower`/`upper` bounded by the input's own length, fz_p_str_
  lowernonletter; a pair-with-a-seq-component RETURN through the
  buffer encoding, fz_p_pair_seq) were NOT attempted this pass: item
  (a) alone (the statement-shaped rendering path new to this file, plus
  the certificate bug it exposed) filled this pass's own scope, and
  each of (b)/(c)/(d) is its own fresh design over a DIFFERENT part of
  the seq value machinery (the capacity/offsets encoding, an
  executable-length-bound rule, `_pair_field_c`'s own struct
  territory), not a further extension of the equality-loop machinery
  item (a) built. Each STILL reads its own exact pre-existing message,
  remeasured (byte-identical to FRAMAC-SEQ4's own note above,
  `fuzz_lower.py --tasks fz_p_nest_empty,fz_p_str_splitempty,fz_p_str_tab,
  fz_p_str_lowernonletter,fz_p_pair_seq --only framac --n 0 --flake 3`):
  `fz_p_nest_empty` and `fz_p_str_splitempty`, "nested seq (seq<seq>)
  RETURN: building a fresh row set has no encoding in this lowering
  ..."; `fz_p_str_tab`, "nested seq (seq<seq>) local variables are not
  supported by this lowering ..."; `fz_p_str_lowernonletter`, "seq
  return 'r''s length is not statically determinable ..."; `fz_p_pair_
  seq`, "a pair with a seq component is refused by this lowering ...".
  The sweep's own six named abstains for this design order (240
  replaceLastElement, 586 splitAndAppend, 577 factorialOfLastDigit, 603
  lucidNumbers, 414 anyValueExists, and 576/69 -- now landed/moved,
  above) are likewise untouched by items (b)/(c)/(d)'s absence: none of
  414/577/603/240/586 reaches ANY of this pass's own four owned sites
  (`_seq_eq_top`/`_seq_eq_operand_c`/`_seq_eq_loop`/`_seq_eq_value`,
  `_undef_certificate`'s `walk()`) either, so none is expected to move
  and none does; 414 anyValueExists in particular is named by this
  pass's own task as sharing item (a)'s executable-quantifier-loop
  shape ("a bounded quantifier in executable position, the same loop
  path as (a)") but was not itself built this pass: a `\forall`/`\exists`
  reaching EXECUTABLE position (not compared against another seq) is a
  DIFFERENT node shape than the `==`/`!=` this pass's own `_seq_eq_top`
  gates on, sharing only the general STATEMENT-shaped-loop mechanism in
  spirit, not any code path this pass actually wrote; remeasured
  unchanged, "bounded quantifier in executable position" (exact
  wording preserved from before this pass, `fuzz_lower.py`/`grade.py`
  reaching the pre-existing refusal site, untouched by this pass's own
  four edits).

  REGRESSION, measured both sides (before = `git show HEAD:t/
  lower_framac.py` at this pass's own start commit, copied to
  /tmp/claude-1004/-home-tmcuzzort/b04a1fce-9e33-441b-804f-aa0d13f350ee/
  scratchpad/framac-nested/before-t/lower_framac.py, run inside a full
  copy of `t/` so every import resolves identically): the 34 committed
  tasks under t/tasks, framac column, `python3 grade.py --tasks tasks
  --kernels framac,dafny --flake 3 --jobs 6`: table.md BYTE-IDENTICAL
  before/after except the timestamp header (31 `verified/refuted`, 3
  `abstain/abstain` -- count_vowels, split_join, swap_rows -- unchanged,
  none of the 34 reaches `_seq_eq_top`/`_seq_eq_operand_c`/
  `_seq_eq_loop`/`_seq_eq_value` or the certificate `declared`-set fix:
  no committed task compares two seqs with a bare `==`/`!=` in
  executable position, and no committed task's certificate replay hits
  the RETURN-name-first-assignment or reassigned-"var"-across-
  iterations shapes the certificate bug needed). The 66-item framac
  conformance manifest (own scratchpad script,
  /tmp/claude-1004/-home-tmcuzzort/b04a1fce-9e33-441b-804f-aa0d13f350ee/
  scratchpad/framac-nested/conf_framac.py, `run_par.BACKENDS` restricted
  to framac, `conformance.build_manifest()`/`run_items()`/`grade()`
  called directly): 58/66 PASS both before and after, PASS/FAIL split
  identical cell for cell (fz_p_nest_eq is the only cell whose own
  RAW OUTCOME text differs, `abstain -> timeout`, both sides still
  scored FAIL, matching `_expect` neither before nor after). The 66
  `dafny_synthesis_*` rows of t/COVERAGE-lifted-785.md that read
  `verified / refuted` in the framac column TODAY (grepped from the
  live file, copied into /tmp/claude-1004/-home-tmcuzzort/b04a1fce-9e33-
  441b-804f-aa0d13f350ee/scratchpad/framac-nested/ds-verified-refuted-
  tasks, `python3 grade.py --tasks <dir> --kernels framac --min-kernels
  1 --flake 3 --jobs 8`): table.md BYTE-IDENTICAL before/after (none of
  the 66 is 576 or 69, neither of which reads `verified/refuted` in
  that file today; the two pre-existing TIMEOUTs among the 66, 460
  getFirstElements and 86 centeredHexagonalNumber, stay `timeout/
  refuted` both sides, unmoved, unchanged from wave J's own note
  above). `test_framac_seq4.py`'s own two tests for `fz_p_nest_eq`
  UPDATED this pass (it asserted the OLD "abstain on executable
  equality" outcome by name; that text no longer applies once item (a)
  gives it a real rendering) rather than left to fail; a new file,
  `test_framac_nested.py`, adds six tests for this pass's own three
  cells and the certificate fix, all six embedding their own task JSON
  (IsSublist/ContainsSequence's own bodies, copied verbatim from
  `t/out/lifted-tasks/`, since that directory is generated data, not
  part of this repo's checked-in tree) so they run without depending on
  a lifted-sweep set being present on disk; `python3 t/test_framac_
  seq4.py` and `python3 t/test_framac_nested.py` both read all tests
  passing, and every other `test_framac_*.py` file in this repo (frame_
  fact, measure_axiom, while_cert) is unmoved, also all passing.

  OPEN, named rather than attempted (this pass's own scope was item (a)
  alone): items (b), (c), (d) of the stated build order (a second
  CAPACITY dimension for nested seq<seq> RETURN/LOCAL; an executable
  `lower`/`upper` bounded by the input's own length; a pair-with-a-
  seq-component RETURN through the buffer encoding) and the design's own
  five stated abstains unrelated to item (a) (240 replaceLastElement,
  586 splitAndAppend, 577 factorialOfLastDigit, 603 lucidNumbers, 414
  anyValueExists) -- each still reads the exact message quoted above,
  none attempted, none a rendering-site fix this pass's four owned
  sites (`_seq_eq_top`, `_seq_eq_operand_c`, `_seq_eq_loop`,
  `_seq_eq_value`) could close alone. Additionally, WITHIN item (a)'s
  own now-built machinery: the nested (fz_p_nest_eq) and doubly-
  quantified-`\exists` (69 ContainsSequence) shapes both TIMEOUT at the
  pinned alt-ergo budget rather than verify, a proof-engineering gap
  (quantifier instantiation, not a missing rendering) this pass does
  not chase further, matching the identical gap already named and left
  open for task 460 above.

FRAMAC-NESTED, DESIGN-framac-nested-seq.md, 2026-09-14 (worktree
/home/tmcuzzort/tup/.claude/worktrees/wf_9a0a9ebc-9de-6). Takes up items
(b)/(c)/(d) named OPEN just above: a second capacity dimension for a
seq<seq> RETURN/LOCAL (sections 1-3), an executable `lower`/`upper`
(section 4), and re-checks the two cells wave K's item (a) moved from
abstain to timeout (`fz_p_nest_eq`, 69 ContainsSequence, section 6 of
this task's own instructions). `swap_rows`'s general BUILD problem
(section 3's `split`/`update` scanning loop, a genuinely data-dependent
row count) was NOT attempted: every task actually measured this pass
builds its nested value from a COMPILE-TIME CONSTANT, so the narrower
fold below closes them without the general loop machinery section 3
describes; a real runtime build (`swap_rows`'s own shape) still hits
the unchanged wholesale refusal, named below.

CLOSED, three of the six FAIL cells DESIGN-framac-nested-seq.md's own
task named (`t/CONFORMANCE.md`'s eight framac FAIL cells today: biglen
and seqlen open by design, stay; pair_seq/nest_eq/nest_empty/
str_splitempty/str_tab/str_lowernonletter were the six targets):

  `fz_p_nest_empty`, `fz_p_str_splitempty` (sections 1-3, a seq<seq>
  RETURN): `_ret_nested_fold`/`_fold_nested_rows` (new, above
  `_ret_capacity`) constant-fold `ret`'s own single build statement
  (`[]`, or `split([])`, replaying `split`'s own semantics through
  `interp._str_split_ws` so the fold can never disagree with the real
  program) to concrete Python rows at LOWERING TIME, closing BOTH
  capacities (row count, total element count) to integer LITERALS --
  `lower()`'s own nested-RETURN branch then emits the flat data+offsets
  triple as OUTPUT parameters (`{ret}_data`, `{ret}_off`, `{ret}_n`,
  THE ENCODING's own naming, reused for a RETURN) with `requires
  {ret}_n == ROWS`, `requires \valid({ret}_off + (0 .. {ret}_n))`,
  `requires \valid({ret}_data + (0 .. DATA - 1))`, and a BODY of
  individual literal stores (no loop, exactly `seq_assign_lines`'s own
  `lower`/`upper` literal-fold precedent below), bypassing `stmts()`
  entirely since the fold already consumed the whole (one-statement)
  body. `swap_rows`'s own multi-statement, data-dependent shape never
  folds and falls straight through to the SAME wholesale refusal as
  before, its message text updated to say so by name.

  `fz_p_str_lowernonletter` (section 4, an executable `lower`/`upper`):
  three small, independent additions close it, none of them the general
  two-capacity machinery above (this probe's return length equals its
  bare input's, `_expr_seq_len`'s existing single-dimension resolution
  already covers it once taught the new op): (1) `_expr_seq_len` gains
  a `lower`/`upper` case, passing the length question straight through
  to the operand (pointwise, never adds/drops an element); (2)
  `seq_assign_lines` gains a `lower`/`upper` case, T_CASE_ACSL (new,
  alongside T_DIVMOD_ACSL) declaring `t_lower_c`/`t_upper_c` once per
  file that needs either, a bare-variable source getting a real copy
  loop (invariant `target[t] == t_lower_c(src[t])`) and a fully-literal
  source (this probe's own shape, `lower([32, 64, 91, 96, 123,
  1000000])`) folded at Python level to its already-computed constant
  result and re-dispatched through the pre-existing `seq`-literal case,
  needing no runtime loop at all; (3) `_seq_at_render` gains a `seq`
  LITERAL case (a nested ternary case-split over the literal's own
  fixed index set), needed only because this probe's `ensures` compares
  the whole return AGAINST a literal (`r == [32, ...]`), `pred()`'s
  seq `==` branch reading each side through `_seq_at_render`.

  `fz_p_str_tab` (a seq<seq>-typed LOCAL, section 1's other half):
  `stmts()`'s `var` case now tries `_fold_nested_rows` on a nested-typed
  local's own initializer before refusing; when it folds (this probe's
  `rows := split([65, 9, 66])`), the local becomes two plain, literally-
  initialized C arrays (`int rows_data[2] = {65, 66}; int rows_off[3] =
  {0, 1, 2}; int rows_n = 2;`) and NO ACSL clause at all, "no VLA, no
  malloc" made real by both dimensions being compile-time constants
  already, never a `requires` a caller owes (a LOCAL has no caller).
  This closes the LOCAL-declaration gap the cell's old abstain message
  named -- but the cell as a whole STILL abstains, because its body then
  reads those rows back through `==` nested inside `and`
  (`len(rows)==2 and at(rows,0)==[65] and at(rows,1)==[66]`), never a
  bare top-level comparison `_seq_eq_top` (wave K's item (a), 2026-09-
  12) recognizes -- a genuinely different, deeper gap this pass does not
  chase (it is exactly item (a)'s own stated scope boundary, "==
  nested inside `and`", not this pass's own named build order). Kept
  anyway: real, additive progress (a previously-impossible declaration
  now renders), and the cell's abstain message is now ACCURATE (names
  the true remaining blocker) rather than stale.

  MEASURED (frama-c 33.0 / alt-ergo 2.4.3-free, 2026-09-14,
  `verifiers.framac.verify` called directly on each lowered `.c` file):
  `fz_p_nest_empty` 5/5 goals proved, VERIFIED; `fz_p_str_splitempty`
  69/69 goals proved (includes an unused, harmless `t_wc`/`t_wc_c`
  declaration, `_has_wordcount`'s own over-inclusive-by-design walk
  firing on `split`'s presence regardless of reachability, pre-existing
  behaviour, not touched here), VERIFIED; `fz_p_str_lowernonletter`
  reads `verified / refuted` end to end via `fuzz_lower.py --n 0 --only
  framac --tasks fz_p_str_lowernonletter --flake 3` (the twin ladder DID
  find a compare-flip candidate here, unlike the two no-twin RETURN
  cells), matching `_expect` exactly.

STOPPED, named rather than attempted: `fz_p_pair_seq` (a pair with a
seq component) is UNCHANGED, out of this pass's own scope (its own
section 5 needs `_pair_field_c`'s struct-by-value encoding to grow a
buffer-pointer-plus-length component, a different problem from either
the nested-seq fold or the case-map loop this pass actually built, and
no time remained to design it this pass); `dafny_synthesis` 262
splitArray (section 5's committed target) was never reached for the
same reason. The sweep rows 240 replaceLastElement and 586
splitAndAppend (section 3's "if their concat shapes fall out") were
checked directly against a copy of their own lifted JSON and still read
their PRE-EXISTING named refusal (the seq-concatenation EXACT-length-
return / non-target-left-operand gaps `seq_assign_lines`'s own `+`
case already names, untouched by anything this pass built): neither
task's own body is a `lower`/`upper` call or a compile-time-constant
nested seq<seq> build, so neither reaches any of this pass's four new
sites; not moved, not expected to move.

`fz_p_nest_eq` and 69 ContainsSequence (this task's own section 6 item,
"read WP's goal report and close them ... or name the goal"): RE-
CHECKED by hand-tracing WP's own goal report again (`frama-c -wp ...`
directly on each, no `-wp-fct` restriction, same command wave K's own
note above already used) rather than assumed unchanged: BOTH STILL
TIMEOUT, the exact same failing goal NAMES as wave K's own note records
(`fz_p_nest_eq`: `..._ensures`, `..._loop_invariant_2_preserved`,
`..._loop_invariant_3_preserved`; 69 ContainsSequence:
`..._loop_4_preserved`, `..._ensures`, `..._loop_7_preserved`), because
nothing this pass built touches `_seq_eq_top`/`_seq_eq_operand_c`/
`_seq_eq_loop`/`_seq_eq_value` (the four sites wave K's own item (a)
owns) at all -- this pass's own four new sites are a DIFFERENT four
(`_expr_seq_len`, `_seq_at_render`, `seq_assign_lines`, `stmts()`'s
`var` case, plus `_ret_nested_fold`/`_fold_nested_rows` in `lower()`
itself). The gap itself is UNCHANGED and confirmed, not merely assumed:
a doubly-quantified (`\forall`-inside-`\forall` for nest_eq, `\exists`-
inside-`\forall` for ContainsSequence) instantiation problem alt-ergo
2.4.3 cannot close at the pinned budget even with every scalar fact
already known, the same capability class already named for task 460
getFirstElements and task 86 centeredHexagonalNumber; RULES forbids
raising the pinned budget to chase it, so both stay the honest TIMEOUT
they already were, not relabeled.

REGRESSION. The 34 committed tasks under t/tasks: `lower()` called
directly on each (this worktree's `lower_framac.py` vs. `git show
HEAD:t/lower_framac.py`, loaded as a separate module so both run in the
same process against the same task JSON) -- 33 of 34 BYTE-IDENTICAL;
the 34th, `swap_rows`, differs ONLY in its abstain message's own text
(both sides still raise `NotImplementedError`, ABSTAIN both before and
after -- the message was reworded to say a compile-time-constant nested
return now lowers, which `swap_rows`'s own data-dependent one still
does not). Since frama-c is deterministic on identical C input, this
byte-identity stands in for re-running the kernel on the 33 unaffected
tasks: the AGREEMENT.md framac column (31 `verified/refuted`, 3
`abstain/abstain`) is unmoved cell for cell. The 66-item framac
conformance manifest (own scratchpad script, `conformance.
probe_manifest()`/`run_items()`/`grade()` called directly, `present`
filtered to framac alone, flake 3): 48 PASS / 5 FAIL, up from 45 PASS /
8 FAIL before this pass (the three closed cells above, each moving from
FAIL to PASS; the five still-FAIL cells -- biglen, seqlen (open by
design), pair_seq, nest_eq, str_tab -- read the identical (real, twin)
pair before and after, confirmed by rerunning the SAME script against a
copy of the pre-pass file). The 302-task lifted corpus
(`/home/tmcuzzort/tup/t/out/lifted-tasks/`, read-only): `lower()` called
directly on all 302 (same before/after-module technique as the 34
committed tasks) -- 301 of 302 BYTE-IDENTICAL; the one exception,
`dafny-language-server_tmp_tmpkir0kenl_Test_tutorial_maximum.Maximum`
(not a `dafny_synthesis`-prefixed row, so outside this task's own
pinned regression set), moves from ABSTAIN ("seq position holds
non-variable", a bare `values != []` requires) to a full lowering, an
UNPLANNED but strictly positive side effect of `_seq_at_render`'s new
literal-`seq` case (the same rendering `fz_p_str_lowernonletter`'s
`ensures` needed); not investigated further for a kernel verdict, named
here rather than silently absorbed. None of the four nested-seq-typed
tasks already in the 302 (`460 getFirstElements`, `95
SmallestListLength`, `792 CountLists`, `69 ContainsSequence`, all
seq<seq> PARAMETERS, read only) declares a nested seq<seq> RETURN or
LOCAL or calls `lower`/`upper`, confirmed by direct inspection of each
task's own JSON, so none of this pass's new code paths is even reached
by any of them -- the dafny_synthesis rows of t/COVERAGE-lifted-785.md
that read `verified`/`refuted` in the framac column are therefore
PROVABLY unmoved, not merely unmeasured.

Tests: `test_framac_seq4.py`'s `the_other_five_seq_cells_are_unmoved`
UPDATED (it asserted the OLD abstain text for `fz_p_nest_empty`/
`fz_p_str_splitempty`/`fz_p_str_lowernonletter`/`fz_p_str_tab`, three of
which no longer abstain at all and the fourth of which abstains for a
different, deeper reason now); every other test in that file and in
`test_framac_nested.py`/`test_framac_frame_fact.py`/`test_framac_
while_cert.py`/`test_framac_measure_axiom.py` passes unchanged (`python3
t/test_framac_*.py` for each, run from `t/`).

FRAMAC-CLOSURE, 2026-09-14 (sweep r25's five sole-framac-blocker rows,
dafny-synthesis 412/426/436/554/629). Each calls a spec_fun predicate
(isEven, isOdd or isNegative) from an `if` inside its loop, EXECUTABLE
position, and `cexpr`'s "call" case abstained unconditionally on any
non-self call ("spec_fun call in executable position (ACSL logic
functions are not executable)"), exactly the gap the module docstring's
own ABSTAIN-3 note (above) named and left undone. FIXED for the
NON-RECURSIVE, all-int-parameter case (`_spec_fun_c`, new, next to
`spec_fun_acsl`): the spec_fun is mirrored as a plain C function
`{name}_c` whose body is the SAME expression rendered through `cexpr`
(C, not ACSL `term`) and whose contract states it agrees with the logic
function at every call (`\result == f(args)` for an int result,
`(\result != 0) <==> f(args)` for a bool one); `lower()` emits the
mirror unconditionally for every eligible spec_fun (the T_DIVMOD_ACSL/
T_CASE_ACSL pattern, over-inclusive by design), and `cexpr`'s "call"
case now dispatches to `{name}_c(args)` for an eligible non-task call
instead of raising. The ACSL side is UNCHANGED: every `requires`/
`ensures`/invariant naming the spec_fun symbolically still calls the
plain logic function `spec_fun_acsl` already emits, so nothing here
touches, weakens, or restates what the task's own spec says. Eligible:
no seq-typed parameter, no self-recursion (`self_calls`, reused).
INELIGIBLE spec_funs -- `factorialOfLastDigit`'s and `Triple`'s own
recursive `factorial`, the general case the ABSTAIN-3 note sketches and
scopes out -- still abstain with the IDENTICAL original message via the
eligibility check at the call site, UNCHANGED.

MEASURED (frama-c 33.0 / alt-ergo 2.4.3-free, this worktree,
2026-09-14): a standalone probe task (`pickEvenOrOne`, a scalar-only
`ensures isEven(n) ==> r == 1` calling `isEven` from an `if` in
executable position, run directly through `lower()`/`verify()`, not
committed) measures the mirror mechanism itself sound -- 12 of 13 goals
Proved (Qed/Alt-Ergo), including `isEven_c`'s own `ensures (\result !=
0) <==> isEven(n)` contract and the caller's `ensures` that depends on
it; the one Timeout is an unrelated `assigns` frame-condition goal this
minimal probe's own uninitialized-then-assigned local triggers, not a
spec_fun-mirroring goal. On the five actual sweep rows (412/426/436/
554/629), grading them directly (`python3 t/grade.py --tasks <copy of
the five> --kernels framac,dafny --flake 3`) shows the "spec_fun call in
executable position" abstain is GONE on every one, replaced by a
SECOND, unrelated framac abstain that was always one layer beneath it:
"seq return '<name>''s length is not statically determinable from the
task's params ... no `ensures` ... gives a CAPACITY bound either" --
each task filters `arr` into a variable-length output seq with no
`ensures`-stated size bound (`_ret_capacity`'s own pre-existing gap,
unrelated to spec_fun calls, and a materially bigger feature: the bound
IS derivable, but only by combining two of the loop's OWN invariants
transitively, `len(evenList) <= i_v2 <= h`, which `_ret_capacity` does
not look at today since it reads only `ensures`). Named rather than
silently absorbed: this pass's own scope (spec_fun-in-executable-
position) is closed and MEASURED sound; the CAPACITY-bound-from-
invariants gap is a distinct, larger item for whoever takes it next.

Regression, measured this worktree: none of the 34 committed tasks
(t/AGREEMENT.md) declares any spec_fun (`grep spec_fun t/tasks/*.t` ->
no match), so this change touches ZERO committed-task cells by
construction; `python3 t/grade.py --tasks t/tasks --kernels framac,dafny
--flake 3` shows every real cell unchanged (verified, or the same three
pre-existing ABSTAINs -- count_vowels, split_join, swap_rows -- all
unrelated to spec_funs). The conformance suite's framac column
(`conformance.build_manifest`/`run_items`/`grade` restricted to the
framac backend alone) reads 61 of 66 PASS, the SAME five FAIL cells as
before this pass (fz_p_biglen, fz_p_seqlen, fz_p_pair_seq, fz_p_nest_eq,
fz_p_str_tab) -- no PASS lost, no new FAIL. The dafny_synthesis rows of
t/COVERAGE-lifted-785.md that read verified/refuted in the framac column
are unmoved BY CONSTRUCTION, not merely unmeasured: `cexpr`'s "call"
case only reaches its NEW branch when `c["fun"] != task_name`, a
position that unconditionally raised NotImplementedError (ABSTAIN)
before this pass on every single task that hit it -- a cell already
reading verified or refuted never executed that branch's old code at
all, so it cannot be affected by widening what that branch now accepts.

SEQ-TYPED LOCAL, measured, NOT CLOSED, 2026-09-14 (sweep r25's other two
sole-framac-blocker rows, dafny-synthesis 307 deepCopySeq and 743
rotateRight). Exact message (`python3 t/grade.py` on each, unchanged by
this pass): "seq-typed local variables are not supported by this
lowering except the slice-ALIAS shape (`v := s[a..b]`, word_count's own
case and its own OFF-BY-ONE twin); no requires-time bound sizes a fresh
backing buffer for any other initializer". Both tasks declare a PLAIN
(not seq<seq>) seq-typed LOCAL (`newSeq`/`rotated`), initialize it to
`[]`, build it via the SAME per-iteration append idiom the RETURN's own
CAPACITY machinery already supports (`local := local + [row]` inside the
loop), and copy it into the actual return (`copy := newSeq`/`r :=
rotated`) as the body's LAST statement. t/DESIGN-framac-nested-seq.md's
own "seq-local encoding" (section 1, "A seq<seq> LOCAL is the same
triple as extra caller-provided scratch parameters") is written for a
NESTED (seq<seq>) local specifically, matching section 1's own opening
line ("The representation is the one a parameter already has") and
section 6's regression list ("the seq<seq> parameter encoding"); neither
307 nor 743 declares a seq<seq>-typed anything (both `s`/`l`/`copy`/`r`/
`newSeq`/`rotated` are plain `seq`, confirmed by direct inspection of
each task's own JSON params/returns/body). So the design's own encoding
reaches ZERO cases here: it is not that the encoding was applied and
fell short, but that its scope (seq<seq>) does not cover what these two
tasks need (a plain seq-typed local later copied whole into the
return). Closing THIS gap would need a different, narrower move than
the design describes -- recognizing a seq-typed local whose only use is
the RETURN's own append idiom, then copying to the return unmodified at
the end, and building directly into the return's own buffer instead of
a separate local one (no new CAPACITY dimension, no new buffer) -- not
attempted this pass: it is a real, separate mechanism (a local-to-return
aliasing analysis over the body, not a rendering gap), left named for
whoever takes it next rather than guessed at under the remaining
budget."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                                   # noqa: E402
import interp                                    # noqa: E402
import names as t_names                          # noqa: E402
from verifiers import framac as framac_backend   # noqa: E402

ARITH = {"+": "+", "-": "-", "*": "*"}
CMP = {"==": "==", "!=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">="}
DIVMOD = ("div", "mod")

# t_div/t_mod (2026-09-08): SPEC.md's Euclidean div/mod, defined in this
# kernel's own truncating terms (measured below, ACSL DIVISION section).
# Both ACSL's logic `/`/`%` and C's executable `/`/`%` under -wp-model
# Typed+nat truncate toward zero (measured: acsl_trunc / c_div probes both
# VERIFIED on the six SPEC.md examples, acsl_div and acsl_floor both
# TIMEOUT), so truncating `%` carries the sign of x (or is 0), and the
# Euclidean remainder is the truncating one shifted up by |y| exactly when
# it is negative. t_div is the truncating quotient with the matching -1/+1
# correction (sign of y), NOT `(x - t_mod(x, y)) / y`: that exact-division
# form measured a TIMEOUT on the general identity `x == t_div(x,y)*y +
# t_mod(x,y)` (alt-ergo cannot see the subtraction is a multiple of y
# without help), while the correction form measured VERIFIED, because it
# telescopes to WP's own native division identity `x == (x/y)*y + x%y`
# plus linear arithmetic on the correction/adjustment terms, nothing
# division-shaped left to prove.
T_DIVMOD_ACSL = (
    "/*@\n"
    "  logic integer t_mod(integer x, integer y) =\n"
    "    (x % y < 0) ? x % y + \\abs(y) : x % y;\n"
    "  logic integer t_div(integer x, integer y) =\n"
    "    (x % y < 0) ? (x / y) - (y > 0 ? 1 : -1) : x / y;\n"
    "*/\n"
)


def _has_divmod(x) -> bool:
    """Whether `div`/`mod` occurs anywhere in a task/body structure (spec or
    executable position); over-inclusive on purpose, an unused ACSL logic
    definition costs nothing and this only gates whether t_div/t_mod are
    declared at all."""
    if isinstance(x, dict):
        if x.get("op") in DIVMOD:
            return True
        return any(_has_divmod(v) for v in x.values())
    if isinstance(x, list):
        return any(_has_divmod(v) for v in x)
    return False


# T_CASE_ACSL, added 2026-09-14 (DESIGN-framac-nested-seq.md section 4,
# "an executable lower and upper"): the ACSL side of `lower`/`upper`'s own
# case map, matching `interp.py`'s `_is_upper_letter`/`_is_lower_letter`
# (65-90, 97-122) and `seq_assign_lines`'s C ternary for the same op
# byte-for-byte, so the loop invariant `target[t] == t_lower_c(src[t])`
# and the C store it is proving each iteration are the SAME formula, one
# written in ACSL logic and the other in executable C, not two
# independent guesses that happen to agree.
T_CASE_ACSL = (
    "/*@\n"
    "  logic integer t_lower_c(integer c) =\n"
    "    (65 <= c && c <= 90) ? c + 32 : c;\n"
    "  logic integer t_upper_c(integer c) =\n"
    "    (97 <= c && c <= 122) ? c - 32 : c;\n"
    "*/\n"
)


def _has_caselower(x) -> bool:
    """Whether `lower`/`upper` occurs anywhere in a task/body structure,
    the same over-inclusive walk `_has_divmod` uses (an unused ACSL logic
    definition costs nothing)."""
    if isinstance(x, dict):
        if x.get("op") in ("lower", "upper"):
            return True
        return any(_has_caselower(v) for v in x.values())
    if isinstance(x, list):
        return any(_has_caselower(v) for v in x)
    return False


# THE STRING LIBRARY (v1), 2026-09-11 (SPEC.md "The string library (v1)",
# ROADMAP 12.7, the wave after nested sequences). Seventeen members, one
# op each (`split` two arities of one op, per SPEC.md's own count); this
# pass lands exactly one, `len(s.split())` (word_count's own shape, the
# ONLY use of any string-lib member in any committed task that does not
# also need a second member this pass does not land), and names every
# other reachable position as an abstain rather than guess at it. The
# type table below is needed even for an abstained op: `typ()` must
# report SPEC.md's own result type for each so a caller (`pred()`'s `==`
# dispatch is the one that matters here) routes to the CORRECT branch
# before the abstain fires, not a wrong one that happens to also raise.
STRLIB_SEQ_RESULT = ("split", "join", "tostr", "strip", "lstrip", "rstrip",
                     "replace", "lower", "upper")
STRLIB_INT_RESULT = ("count", "find")
STRLIB_BOOL_RESULT = ("isdigit", "isalpha", "isupper", "islower",
                      "startswith", "endswith")

STRLIB_ABSTAIN = {
    "split": "a row set (seq<seq>) has no backing buffer in this "
             "lowering's encoding; only `len(s.split())`'s own row-COUNT "
             "formula is lowered (T_WORDCOUNT_ACSL below), reached "
             "before this check via `_seq_len_render`/`cexpr`'s own "
             "special case for `len` applied directly to a one-argument "
             "`split`. `split(s, c)`'s two-argument form, and either "
             "arity reaching any OTHER position (not `len`'s own "
             "argument), are not lowered.",
    "join": "joining a seq<seq> of rows into a seq has no backing-buffer "
            "construction in this lowering.",
    "strip": "a variably-shorter output seq has no sized buffer in this "
             "lowering (no `ensures`-stated capacity bound the general "
             "member could size a buffer against, the same gap CAPACITY "
             "mode's own docstring names for a data-dependent length).",
    "lstrip": "the same gap as `strip`: a variably-shorter output seq has "
              "no sized buffer here.",
    "rstrip": "the same gap as `strip`: a variably-shorter output seq has "
              "no sized buffer here.",
    "replace": "a variably longer-or-shorter output seq has no sized "
               "buffer here, and no non-overlapping-match scan is "
               "lowered for it either.",
    "tostr": "the output length depends on `n`'s own runtime digit "
             "count (plus a leading `-`), which this lowering has no "
             "static bound for.",
    "count": "reaching ACSL TERM or PREDICATE position (a `requires`/"
             "`ensures`/invariant calling `count` symbolically): the "
             "recursive ACSL definition (T_STRFIND_ACSL, ROADMAP 13.4, "
             "framac-seq2) is wired only to EXECUTABLE position "
             "(`cexpr`'s own `count`/`find` case, checked before this "
             "abstain fires); a spec-position occurrence has no ACSL "
             "TERM rendering yet.",
    "find": "the same gap as `count`, spec position only: reaching ACSL "
            "TERM or PREDICATE position has no rendering; EXECUTABLE "
            "position is lowered (T_STRFIND_ACSL).",
    "lower": "an output seq the same length as its input has no "
             "lowering here yet: no case-map codegen is wired into the "
             "seq-assignment machinery (`seq_assign_lines`) for it.",
    "upper": "the same gap as `lower`: no case-map codegen is wired "
             "into the seq-assignment machinery for it.",
    "isdigit": "no lowering yet; not reached by either committed task, "
               "left for the next pass.",
    "isalpha": "no lowering yet; not reached by either committed task, "
               "left for the next pass.",
    "isupper": "no lowering yet; not reached by either committed task, "
               "left for the next pass.",
    "islower": "no lowering yet; not reached by either committed task, "
               "left for the next pass.",
    "startswith": "no lowering yet; not reached by either committed "
                  "task, left for the next pass.",
    "endswith": "no lowering yet; not reached by either committed task, "
                "left for the next pass.",
}


def _strlib_abstain(op: str, where: str) -> None:
    """Raise the named abstain for string-lib member `op` reaching
    rendering position `where`, or do nothing for an op this file does
    not know (every OTHER operator's own dispatch handles or refuses
    itself). Never called for `split` reached as `len`'s own direct
    argument: that path is intercepted earlier, inside `_seq_len_render`
    and `cexpr`'s `len` case, before either function's generic op
    dispatch (where this is called from) is reached at all."""
    if op in STRLIB_ABSTAIN:
        raise NotImplementedError(
            f"string library member `{op}` reaching {where}: "
            f"{STRLIB_ABSTAIN[op]} (SPEC.md \"The string library (v1)\", "
            f"2026-09-11)")


# t_wc (2026-09-11): Python's `str.split()` with NO argument, the row
# COUNT only (`len(s.split())`, word_count's own shape and the only
# string-lib use in any committed task this pass lowers). Whitespace is
# the 10 ASCII code points test_strlib.py's own parity test measured (9
# to 13, tab/LF/VT/FF/CR, and 28 to 31, FS/GS/RS/US, plus 32, space),
# never Python's own `str.isspace()` (this kernel enumerates them, same
# as interp.py's own reason: nothing here calls `chr()` or `str.isspace`
# itself). A word is a maximal run of non-whitespace code points;
# `t_wc(s, n)` counts them by counting RUN STARTS (`s[i]` non-whitespace
# and either `i == 0` or `s[i - 1]` whitespace) over the PREFIX of length
# `n`, recursing down from `n` so the executable loop below can carry it
# as a running invariant, `wc == t_wc(s, i)`, with NO row ever
# materialized -- the length formula IS the lowering, exactly the move
# `_seq_len_render`'s existing `len(m[i])` case already makes for a
# nested seq's row length (a formula over the offsets array, never a
# copy). MEASURED (frama-c 33.0 / alt-ergo 2.4.3-free, 2026-09-11):
# `t_wc_c` itself (its `ensures \result == t_wc(s, n)` contract, the
# loop's three invariants, and the emitted `t_wc_terminates` well-
# foundedness lemma) is a self-contained file with no task in it; run
# standalone through `verify()` alongside `T_DIVMOD_ACSL`'s own
# ACSL block, all of its goals PROVED (see the module docstring's own
# 2026-09-11 note for the count).
WS_CODEPOINTS = (9, 10, 11, 12, 13, 28, 29, 30, 31, 32)


def _ws_or(term: str) -> str:
    """The 10-codepoint whitespace disjunction (SPEC.md "The string
    library (v1)", 2026-09-11) over ACSL/C term `term`, INLINED (no
    `is_ws` predicate symbol): measured 2026-09-11, a separate `predicate
    is_ws(integer x) = ...` cost `t_wc_c`'s own loop-invariant
    preservation goal a TIMEOUT even at a 20,000,000-step / 60s budget
    (Alt-Ergo apparently unable to connect the predicate's unfold to the
    executable `?:` chain cheaply), while this same disjunction written
    out flat, at every site, everywhere (the recursive definition, the
    loop invariant, and the executable `?:` chain alike, so every
    occurrence is syntactically the SAME formula up to the substituted
    term) discharges every goal, Qed or a sub-100ms Alt-Ergo call."""
    return " || ".join(f"(({term}) == {c})" for c in WS_CODEPOINTS)


T_WORDCOUNT_ACSL = (
    "/*@\n"
    "  logic integer t_wc{L}(int *s, integer n) =\n"
    "    n <= 0 ? 0 :\n"
    f"    t_wc(s, n - 1) + ((!({_ws_or('s[n - 1]')}) &&\n"
    f"                       (n - 1 == 0 || ({_ws_or('s[n - 2]')}))) ? 1 : 0);\n"
    "  lemma t_wc_terminates:\n"
    "    \\forall int *s, integer n; n > 0 ==> (n - 1) < n && (n - 1) >= 0;\n"
    "*/\n"
    "/*@\n"
    "  requires n >= 0 && \\valid_read(s + (0 .. n - 1));\n"
    "  assigns \\nothing;\n"
    "  ensures \\result == t_wc(s, n);\n"
    "*/\n"
    "int t_wc_c(int *s, int n) {\n"
    "  int i = 0, wc = 0;\n"
    "  /*@\n"
    "    loop invariant 0 <= i <= n;\n"
    "    loop invariant wc == t_wc(s, i);\n"
    "    loop assigns i, wc;\n"
    "    loop variant n - i;\n"
    "  */\n"
    "  while (i < n) {\n"
    f"    int isw = ({_ws_or('s[i]')}) ? 1 : 0;\n"
    f"    int prevws = (i == 0) ? 1 : (({_ws_or('s[i - 1]')}) ? 1 : 0);\n"
    "    if (!isw && prevws) wc = wc + 1;\n"
    "    i = i + 1;\n"
    "  }\n"
    "  return wc;\n"
    "}\n"
)


def _has_wordcount(x) -> bool:
    """Whether `split` with exactly ONE argument (SPEC.md's no-arg
    `s.split()`, not `s.split(c)`) occurs anywhere, the same
    over-inclusive walk `_has_divmod` uses."""
    if isinstance(x, dict):
        if x.get("op") == "split" and len(x.get("args", ())) == 1:
            return True
        return any(_has_wordcount(v) for v in x.values())
    if isinstance(x, list):
        return any(_has_wordcount(v) for v in x)
    return False


def _wordcount(s: list) -> int:
    """Python replay of `t_wc`, used only by `_cev` (certificate ground
    evaluation, which has no C/ACSL to run): the number of maximal
    non-whitespace runs in `s`, by the same running-prevws walk."""
    wc, prevws = 0, True
    for x in s:
        isw = x in WS_CODEPOINTS
        if not isw and prevws:
            wc += 1
        prevws = isw
    return wc


# framac-seq2, ROADMAP 13.4, 2026-09-11: `count`/`find` (SPEC.md "The
# string library (v1)"), general recursive ACSL definitions, EXECUTABLE
# position only (spec/term/predicate position stays the STRLIB_ABSTAIN
# gap below, unchanged). `t_eqat` is the substring-match predicate at
# one start index (a bounded `\forall`, not itself recursive: it only
# ever ranges over `0 <= k < nt`, a fixed-width comparison, so WP proves
# it directly with no induction, the same shape `fz_p_nest_eq`'s row
# equality already uses). `t_find`/`t_count` are then a LEFT-TO-RIGHT
# scan over the start index, recursing forward: `t_find` stops at the
# first match (`find(s, t)`'s own SPEC.md rule, `-1` when none);
# `t_count` advances by `nt` past a match (non-overlapping,
# `count(s, t)`'s own rule) and by 1 past a miss, and at `nt == 0` this
# same general formula ALREADY gives the right count with no special
# case: `t_eqat` over an empty range (`0 <= k < 0`) is vacuously true,
# so every one of the `ns + 1` start positions 0..ns matches and the
# scan advances by 1 (`nt > 0 ? nt : 1` is 1 there), landing on
# `count(s, []) == len(s) + 1` (SPEC.md's own identity) by construction,
# not by a case split on `nt`. `t_find_c`/`t_count_c` are the matching
# executable loops (an inner loop for `t_eqat` itself, an outer one
# whose invariant carries the recursive value at the CURRENT index equal
# to the recursive value at the START index, exactly `t_wc_c`'s own
# `wc == t_wc(s, i)` shape one level up).
#
# MEASURED (frama-c 33.0 / alt-ergo 2.4.3-free, 2026-09-11, standalone
# file, /tmp/claude-1004/-home-tmcuzzort/b04a1fce-9e33-441b-804f-
# aa0d13f350ee/scratchpad/framac-seq2/t_strfind.c): `t_find_c`,
# `t_count_c` and two harness functions instantiating each at the
# EMPTY-pattern case (`fz_p_str_findempty`'s and `fz_p_str_countempty`'s
# own shape) all PROVED, 103/103 goals, Qed and Alt-Ergo only, no
# smoke lost (31/31). One genuine obstacle, not a guess: proving
# `count(s, [], 0) == len(s) + 1` in closed form from `t_count`'s
# general recursive definition alone is an INDUCTION over the start
# index that Alt-Ergo cannot discharge from a single call to the
# already-proved `t_count_c` (no induction principle over an
# uninterpreted recursive logic function reachable from one ground
# instantiation) -- attempted first as a standalone `lemma` quantified
# over the start index, which TIMED OUT at the same budget T_WORDCOUNT
# ACSL's own note above cites (20,000,000 steps / 60s). The fix: state
# the SAME fact as a RECURSIVE C FUNCTION's own two-part `ensures`
# instead of a bare lemma (`t_countempty_rec` below) -- Frama-C's own
# proof obligations for a recursive function ARE checked by well-founded
# induction on its `decreases` measure (this file's own T_DIVMOD_ACSL
# note: "recursive logic functions unfolding at ground arguments... in
# 6ms" is the same mechanism), so the recursive call's own contract
# becomes the induction hypothesis for free and each step needs only ONE
# unfold of `t_count`'s own defining equation, which Alt-Ergo closes in
# milliseconds. `t_countempty_rec` is emitted unconditionally alongside
# `t_count_c` (not gated on any one task's own pattern literal being
# empty) because it restates SPEC.md's own general law, `count(s, []) ==
# len(s) + 1`, true of every `s`, not a task-shaped instance of it.
T_STRFIND_ACSL = (
    "/*@\n"
    "  predicate t_eqat{L}(int *s, int *t, integer i, integer nt) =\n"
    "    \\forall integer k; 0 <= k < nt ==> s[i + k] == t[k];\n"
    "\n"
    "  logic integer t_find{L}(int *s, integer ns, int *t, integer nt,\n"
    "                          integer i) =\n"
    "    i > ns - nt ? -1 :\n"
    "    (t_eqat(s, t, i, nt) ? i : t_find(s, ns, t, nt, i + 1));\n"
    "\n"
    "  logic integer t_count{L}(int *s, integer ns, int *t, integer nt,\n"
    "                           integer i) =\n"
    "    i > ns - nt ? 0 :\n"
    "    (t_eqat(s, t, i, nt) ?\n"
    "       1 + t_count(s, ns, t, nt, i + (nt > 0 ? nt : 1))\n"
    "     : t_count(s, ns, t, nt, i + 1));\n"
    "\n"
    "  lemma t_find_terminates:\n"
    "    \\forall int *s, integer ns, int *t, integer nt, integer i;\n"
    "      i <= ns - nt ==> (i + 1) > i;\n"
    "  lemma t_count_terminates:\n"
    "    \\forall int *s, integer ns, int *t, integer nt, integer i;\n"
    "      i <= ns - nt ==>\n"
    "        (i + 1) > i && (i + (nt > 0 ? nt : 1)) > i;\n"
    "*/\n"
    "/*@\n"
    "  requires ns >= 0 && nt >= 0 && \\valid_read(s + (0 .. ns - 1));\n"
    "  requires \\valid_read(t + (0 .. nt - 1));\n"
    "  assigns \\nothing;\n"
    "  ensures \\result == t_find(s, ns, t, nt, 0);\n"
    "*/\n"
    "int t_find_c(int *s, int ns, int *t, int nt) {\n"
    "  int i = 0;\n"
    "  /*@\n"
    "    loop invariant 0 <= i;\n"
    "    loop invariant t_find(s, ns, t, nt, 0) == t_find(s, ns, t, nt, i);\n"
    "    loop assigns i;\n"
    "    loop variant ns - nt + 1 - i;\n"
    "  */\n"
    "  while (i <= ns - nt) {\n"
    "    int match = 1;\n"
    "    int k = 0;\n"
    "    /*@\n"
    "      loop invariant 0 <= k <= nt;\n"
    "      loop invariant match == (t_eqat(s, t, i, k) ? 1 : 0);\n"
    "      loop assigns k, match;\n"
    "      loop variant nt - k;\n"
    "    */\n"
    "    while (k < nt) {\n"
    "      if (s[i + k] != t[k]) { match = 0; break; }\n"
    "      k = k + 1;\n"
    "    }\n"
    "    if (match) return i;\n"
    "    i = i + 1;\n"
    "  }\n"
    "  return -1;\n"
    "}\n"
    "/*@\n"
    "  requires ns >= 0 && nt >= 0 && \\valid_read(s + (0 .. ns - 1));\n"
    "  requires \\valid_read(t + (0 .. nt - 1));\n"
    "  assigns \\nothing;\n"
    "  ensures \\result == t_count(s, ns, t, nt, 0);\n"
    "*/\n"
    "int t_count_c(int *s, int ns, int *t, int nt) {\n"
    "  int i = 0, c = 0;\n"
    "  /*@\n"
    "    loop invariant 0 <= i;\n"
    "    loop invariant t_count(s, ns, t, nt, 0) ==\n"
    "                   c + t_count(s, ns, t, nt, i);\n"
    "    loop assigns i, c;\n"
    "    loop variant ns - nt + 1 - i;\n"
    "  */\n"
    "  while (i <= ns - nt) {\n"
    "    int match = 1;\n"
    "    int k = 0;\n"
    "    /*@\n"
    "      loop invariant 0 <= k <= nt;\n"
    "      loop invariant match == (t_eqat(s, t, i, k) ? 1 : 0);\n"
    "      loop assigns k, match;\n"
    "      loop variant nt - k;\n"
    "    */\n"
    "    while (k < nt) {\n"
    "      if (s[i + k] != t[k]) { match = 0; break; }\n"
    "      k = k + 1;\n"
    "    }\n"
    "    if (match) { c = c + 1; i = i + (nt > 0 ? nt : 1); }\n"
    "    else { i = i + 1; }\n"
    "  }\n"
    "  return c;\n"
    "}\n"
    "/*@\n"
    "  requires 0 <= i <= ns + 1;\n"
    "  decreases ns + 1 - i;\n"
    "  assigns \\nothing;\n"
    "  ensures \\result == ns + 1 - i;\n"
    "  ensures \\result == t_count(s, ns, s, 0, i);\n"
    "*/\n"
    "int t_countempty_rec(int *s, int ns, int i) {\n"
    "  if (i > ns) return 0;\n"
    "  return 1 + t_countempty_rec(s, ns, i + 1);\n"
    "}\n"
)


def _has_countfind(x) -> bool:
    """Whether `count`/`find` (SPEC.md "The string library (v1)") occurs
    anywhere, the same over-inclusive walk `_has_divmod`/`_has_wordcount`
    use."""
    if isinstance(x, dict):
        if x.get("op") in ("count", "find"):
            return True
        return any(_has_countfind(v) for v in x.values())
    if isinstance(x, list):
        return any(_has_countfind(v) for v in x)
    return False


_PARTIAL_OPS = {"at", "div", "mod", "update", "fill", "call"}


def _has_partial_op(x) -> bool:
    """Whether `at`/`div`/`mod`/`update`/`fill`/a call occurs anywhere in an
    expression -- the same over-inclusive walk as `_has_divmod`, used by
    `_cert_cexpr`'s "and"/"or" case (2026-09-10, second pass) to decide
    whether a short-circuit is load-bearing for THIS operand: an operand
    built purely from comparisons/arithmetic/vars/bools/pair projections
    has no partial operator whose definedness the other operand's truth
    could protect, so evaluating it unconditionally is safe; one that
    contains any of these might not be (`i < len(s) and at(s, i) > 0`,
    where the `at` is defined only because the guard passed)."""
    if isinstance(x, dict):
        if x.get("op") in _PARTIAL_OPS:
            return True
        return any(_has_partial_op(v) for v in x.values())
    if isinstance(x, list):
        return any(_has_partial_op(v) for v in x)
    return False


# ---------------------------------------------------------------- typing ----

SEQOPS = ("update", "fill")


def typ(e: dict, env: dict, funs: dict):
    """Type of an expression: 'int' | 'bool' | 'seq' | {'pair': [T1, T2]}.

    SPEC.md "Pairs" (2026-09-10) is the one construct whose type is not a
    bare string: a pair's own type carries its two component types, so a
    `var` of pair type already returns the dict `env` holds for it (no
    special case needed, `env[e["var"]]` is whatever the task declared),
    `{"op": "pair", ...}` builds a fresh `{"pair": [T1, T2]}` from its two
    operands' own types, and `fst`/`snd` project one component back out
    (`typ`'s only two callers that must now expect a dict back are
    `pred()`'s `==`/`!=` dispatch, which gains a pair branch below it, and
    this function's own recursion)."""
    if "int" in e:
        return "int"
    if "bool" in e:
        return "bool"
    if "var" in e:
        return env[e["var"]]
    if "forall" in e or "exists" in e:
        return "bool"
    if "ite" in e:
        return typ(e["ite"]["then"], env, funs)
    if "call" in e:
        return funs[e["call"]["fun"]]["result"]
    op = e["op"]
    if op in SEQOPS:
        return "seq"
    if op in STRLIB_SEQ_RESULT:
        # SPEC.md "The string library (v1)" (2026-09-11): the seq/seq<seq>
        # -returning members. Not all of these have a LOWERING (most are a
        # named abstain, `STRLIB_ABSTAIN` below), but `typ()` must still
        # report their correct SPEC.md result type rather than fall
        # through to this function's own "bool" default, or a caller like
        # `pred()`'s `==` dispatch would route a comparison against one
        # through the wrong branch before ever reaching the abstain.
        return "seq"
    if op in STRLIB_INT_RESULT:
        return "int"
    if op in STRLIB_BOOL_RESULT:
        return "bool"
    if op == "seq" or op == "slice":
        # SPEC.md "Sequences: literals, concatenation, slices" (2026-09-09):
        # a literal `[e1, ..., en]` and a slice `s[a..b]` both denote seq
        # values, exactly like `update`/`fill`.
        return "seq"
    if op == "+":
        # `+` is polymorphic by operand type, exactly as `==` already is
        # for seqs (SPEC.md, same section): two seqs concatenate, two ints
        # add. The first operand's type decides which (ill-typed mixes are
        # not this lowering's job to reject; t's own well-formedness check
        # is).
        return "seq" if typ(e["args"][0], env, funs) == "seq" else "int"
    if op == "pair":
        return {"pair": [typ(e["args"][0], env, funs),
                         typ(e["args"][1], env, funs)]}
    if op in ("fst", "snd"):
        pt = typ(e["args"][0], env, funs)
        return pt["pair"][0 if op == "fst" else 1]
    if op == "at":
        # SPEC.md "Nested sequences" (2026-09-10): `at` is polymorphic by
        # its BASE's own type, exactly as `+`/`==` already are by their
        # operands': `at(m, i)` on a seq<seq> `m` is a ROW, itself a
        # "seq" value (`m[i][j]` is the chained `at(at(m, i), j)`, an int
        # again); `at` on a plain "seq" stays "int", unchanged.
        bt = typ(e["args"][0], env, funs)
        return "seq" if is_nested_seq_type(bt) else "int"
    if op in ("len", "neg") or op in ARITH or op in DIVMOD:
        return "int"
    return "bool"                                # cmp, and, or, not, implies


def is_nested_seq_type(t) -> bool:
    """SPEC.md "Nested sequences" (2026-09-10): the type `{"seq": "seq"}`,
    a seq whose elements are seqs of ints, one level. A plain dict check
    (mirrors how a pair's type, `{"pair": [T1, T2]}`, is already told
    apart from a bare "int"/"bool"/"seq" string)."""
    return isinstance(t, dict) and t.get("seq") == "seq"


def seq_var(e: dict, env: dict) -> str:
    """A seq-position expression must be a seq-typed variable (v1:
    sequences are param/return/local-position VALUES, but `at`'s and
    `update`'s own SeqExpr argument is still always a bare variable, never
    a nested `update`/`fill`/`at`; `stmts()`'s seq-assignment codegen is
    where `update`/`fill` themselves are consumed, always as the WHOLE
    right-hand side of an assignment to a seq-typed name, never nested
    inside another expression).

    Extended 2026-09-10 (SPEC.md "Nested sequences") to also accept a
    seq<seq>-typed variable: `m` in `len(m)`/`at(m, i)`/the loop guard's
    `i < len(m)` is a bare variable exactly like a plain seq's own `s`,
    only its C encoding differs (the flat data+offsets pair, THE ENCODING
    note below `assigned_names`), which every caller of `seq_var` renders
    by checking the variable's OWN type, not by this function returning
    anything different."""
    if "var" in e:
        t = env.get(e["var"])
        if t == "seq" or is_nested_seq_type(t):
            return e["var"]
    raise NotImplementedError(f"seq position holds non-variable {e!r}")


def _seq_val_len_c(e: dict, env: dict, funs: dict, task_name: str,
                   _div_style: str = "bf") -> str:
    """SEQ VALUE, executable position, item 2 (concat)/item 3 (slice),
    2026-09-11 (framac-seq): the C length expression for a seq-VALUED
    expression `e` that is never materialized into a buffer (only
    `len(e)` is wanted, `fz_p_concat_len`'s own shape, `r := len(s + u)`
    with no seq-typed local or return in sight), a closed form exactly
    `_expr_seq_len` already computes at the t-Expr level for the
    `requires`-time CAPACITY bound -- this is that same arithmetic
    rendered as a C int expression instead, for a bare variable (its
    `_n` field), a `seq` literal (its own element count), a `slice`
    (`hi - lo`) or a `+` (the sum of both operands', recursively). Never
    reached for `update`/`fill` (SPEC.md's own grammar restricts those to
    the whole right-hand side of a seq-typed assignment, `seq_assign_lines`
    above, never nested inside a `len(...)`)."""
    if "var" in e:
        v = seq_var(e, env)
        return f"{v}_n"
    op = e.get("op")
    if op == "seq":
        return str(len(e.get("args", ())))
    if op == "slice":
        _, lo, hi = e["args"]
        lo_c = cexpr(lo, env, funs, task_name, _div_style)
        hi_c = cexpr(hi, env, funs, task_name, _div_style)
        return f"(({hi_c}) - ({lo_c}))"
    if op == "+":
        left, right = e["args"]
        left_c = _seq_val_len_c(left, env, funs, task_name, _div_style)
        right_c = _seq_val_len_c(right, env, funs, task_name, _div_style)
        return f"(({left_c}) + ({right_c}))"
    raise NotImplementedError(
        f"len() of seq expression {e!r} in executable position: only a "
        f"seq variable, `seq` literal, `slice`, or `+` concatenation has "
        f"a closed-form length by this lowering")


def _slice_alias_base(init: dict, env: dict):
    """SPEC.md "The string library (v1)" (2026-09-11): word_count's own
    committed task declares a seq-typed local from a slice, `t2 :=
    s[0..len(s)]`, "a full-length slice standing in for the loop-free
    body's own copy of s" (the task's own comment in SPEC.md), and its
    OFF-BY-ONE twin (SPEC.md "Tasks... measured via harness.twin_cached")
    mutates the literal `0` to `1`, `t2 := s[1..len(s)]`, a genuine
    SUB-range. Both need a lowering, and neither needs a COPY: a slice of
    a contiguous C array is itself contiguous (`s[a..b]`'s element `k` is
    `s[a + k]`, SPEC.md "Sequences: literals, concatenation, slices"), so
    `stmts()`'s `var` case below aliases in EVERY case, general to any
    `a`/`b`: `int *t2 = s + a; int t2_n = b - a;`, the same pointer-offset
    move `_seq_at_render`'s/`_seq_len_render`'s own existing slice cases
    already make for a slice reaching `at`/`len` directly, generalized to
    a slice BOUND to a name. `stmts()`'s own `at_asserts` call on `init`
    (unchanged, still runs before the alias declaration) is what makes
    this honest on an ill-formed slice: it emits the domain assert `0 <=
    a <= b <= len(s)` as a real proof obligation, unprovable in general
    for the twin's `s[1..len(s)]` (false at the witness `s = []`), which
    is exactly the UNDEFINED half of the twin's own certificate
    (`witness=w` on the twin's `lower()` call), not a silent wrong
    pointer. Returns `(base_var, lo_expr, hi_expr)` when `init` is a
    slice of a bare seq variable, else None (any other seq-local
    initializer, e.g. a string-lib member's result, is not aliased and
    falls through to the general "seq-typed local variables are not
    supported" refusal, unchanged)."""
    if init.get("op") != "slice":
        return None
    base, lo, hi = init["args"]
    if "var" not in base or env.get(base["var"]) != "seq":
        return None
    return base["var"], lo, hi


def _seq_len_render(e: dict, ctx) -> str:
    """ACSL rendering of `len(e)`, `e` a READ-position SeqExpr: a bare seq
    variable (the ordinary case, `{s}_n` unless `ctx.seq_len` overrides it
    for a capacity-tracked return, see the seq value machinery section) or
    a `slice` (2026-09-09, SPEC.md "Sequences: literals, concatenation,
    slices"). A slice's length is pure formula substitution (`s[a..b]` has
    length `b - a` by definition): no backing buffer is needed for this
    rendering since ACSL terms are logic, not memory, unlike a slice
    materialized into an OUTPUT buffer (`seq_assign_lines`'s `slice`
    case), which is real pointer arithmetic over real memory."""
    if e.get("op") == "seq":
        # SEQ VALUE, executable position, item 1 (literal), 2026-09-11
        # (framac-seq): `len([e0, ..., en-1])` in ACSL TERM position
        # (`fz_p_lit_empty`'s own `ensures len([]) == 0`) is its own
        # element count, formula substitution exactly like `slice`'s case
        # below, never a materialized buffer.
        return str(len(e.get("args", ())))
    if e.get("op") == "slice":
        _, lo, hi = e["args"]
        return f"(({term(hi, ctx)}) - ({term(lo, ctx)}))"
    if e.get("op") == "at":
        # `len(m[i])` (SPEC.md "Nested sequences", 2026-09-10): `m[i]` is
        # a ROW, itself a seq value, and this backend has no C VALUE for
        # a bare row (THE ENCODING note below `assigned_names`), so its
        # length is rendered directly as a formula over `m`'s own
        # offsets array, never by materializing the row first: row `i`
        # is `m_data[m_off[i] .. m_off[i+1])`, so its length is exactly
        # `m_off[i+1] - m_off[i]`, the same "formula substitution, not a
        # copy" move `slice`'s own case above already makes. Guarded to
        # only the nested-base shape: `at` on a PLAIN seq is int-typed
        # (`typ()`'s own polymorphism), and `len` of an int can never
        # arise from a well-typed task, so reaching here with a
        # non-nested base would be a caller bug, not a task this
        # lowering must accept.
        base, idx = e["args"]
        if not is_nested_seq_type(typ(base, ctx.env, ctx.funs)):
            raise NotImplementedError(
                "`len(at(...))` with a non-nested-seq base: `at` on a "
                "plain seq is int-typed and has no length")
        m, i = seq_var(base, ctx.env), term(idx, ctx)
        return f"({m}_off[({i}) + 1] - {m}_off[({i})])"
    if e.get("op") == "split" and len(e.get("args", ())) == 1:
        # `len(s.split())` (SPEC.md "The string library (v1)", 2026-09-11,
        # word_count's own shape): the row COUNT formula, `t_wc` (see its
        # own section comment above `_has_wordcount`), never a
        # materialized row set -- the same "formula, not a copy" move
        # this function's own `at`/`slice` cases already make. Guarded
        # to exactly one argument: `len(s.split(c))`'s two-argument form
        # falls through to the generic `v = seq_var(e, ...)` line below,
        # which raises on a non-variable (`split` is not a bare seq
        # var), the correct refusal shape for a case this pass does not
        # lower.
        base = e["args"][0]
        v = seq_var(base, ctx.env)
        n = ctx.seq_len.get(v, f"{v}_n")
        return f"t_wc({v}, {n})"
    v = seq_var(e, ctx.env)
    return ctx.seq_len.get(v, f"{v}_n")


def _seq_at_render(e: dict, k_render: str, ctx) -> str:
    """ACSL rendering of `at(e, k)`, `e` a READ-position SeqExpr and
    `k_render` the already-rendered index term. A slice's element `k` is
    the base's element `a + k` (`s[a..b][k] == s[a+k]`, SPEC.md's own
    definition), again a formula rewrite, not a copy.

    NAMED REFUSAL, added 2026-09-10 (SPEC.md "Nested sequences"): `e`
    itself a seq<seq> means this call is being asked to render a ROW
    VALUE (`m[i]` reaching `at`/a further `at` as ITS OWN base, i.e. the
    chained element read `m[i][j]`, or `m[i]` reaching ACSL term position
    on its own). Neither committed task needs this (`row_max_len` only
    ever wraps `at(m, i)` in `len`, `_seq_len_render`'s own new case
    above; `swap_rows`, which would, is refused wholesale at its RETURN,
    see `lower()`), and the flat data+offsets encoding has no backing
    memory for a bare row value the way a plain seq's row already is one
    (an `int *`/length pair) -- only the row's LENGTH has a formula here,
    never the row itself. Falls through to `seq_var`'s own generic
    refusal below when `e` is not even a bare variable (the pre-existing
    behaviour for a chained `at`, unchanged)."""
    if e.get("op") == "slice":
        s, lo, _ = e["args"]
        return f"{seq_var(s, ctx.env)}[({term(lo, ctx)}) + ({k_render})]"
    if e.get("op") == "seq":
        # FRAMAC-NESTED, added 2026-09-14 (DESIGN-framac-nested-seq.md
        # section 4, `fz_p_str_lowernonletter`'s own `ensures r ==
        # [32, 64, ...]`): a seq LITERAL has no backing buffer, so its
        # element `k` is a formula, not a memory read, exactly the
        # "formula substitution, not a copy" move `_seq_len_render`'s
        # own `seq` case already makes for `len` of the same shape.
        # Rendered as a case split over the literal's own fixed index
        # set (`k == 0 ? e0 : (k == 1 ? e1 : ... : e_last)`), total for
        # any `k` in `[0, len)` (the only range any caller of
        # `_seq_at_render` ever asks about, since `at`'s own bounds
        # obligation is enforced separately, at the call site) and,
        # for `k` out of range, silently falls to the last element --
        # ACSL logic is total, so SOME value is owed even though v1's
        # own `at` is undefined out of range and no proof ever depends
        # on this branch's particular fallback value.
        args_ = e.get("args", ())
        if not args_:
            return "0"
        expr = term(args_[-1], ctx)
        for i in range(len(args_) - 2, -1, -1):
            expr = f"(({k_render}) == {i} ? ({term(args_[i], ctx)}) : ({expr}))"
        return expr
    if (e.get("op") == "at"
            and is_nested_seq_type(typ(e["args"][0], ctx.env, ctx.funs))):
        # SEQ VALUE, executable position, item 4 (nested), 2026-09-11
        # (framac-seq): `at(at(m, i), j)` -- `m[i][j]` -- IN ACSL TERM
        # POSITION (`fz_p_nest_cell`'s own `ensures ... r == at(at(m, i),
        # j)`), the same formula `cexpr`'s matching case (added
        # alongside this one) renders for the executable C statement:
        # cell `j` of row `i` is `m_data[m_off[i] + j]` directly, no row
        # buffer ever materialized. Guarded to exactly this shape (the
        # OUTER `at`'s base is ANOTHER `at` whose own base is nested);
        # `e` itself being nested (a bare row, no further indexing) stays
        # the NAMED REFUSAL below, unchanged.
        m, i_e = e["args"]
        mv = seq_var(m, ctx.env)
        i_c = term(i_e, ctx)
        return f"{mv}_data[({mv}_off[({i_c})]) + ({k_render})]"
    if is_nested_seq_type(typ(e, ctx.env, ctx.funs)):
        raise NotImplementedError(
            "nested seq (seq<seq>): a ROW reaching `at`'s own base, or "
            "ACSL term position directly, has no rendering in the flat "
            "data+offsets encoding; only `len(m[i])` (a row's LENGTH) is "
            "supported, via `_seq_len_render`'s own `at` case")
    return f"{seq_var(e, ctx.env)}[{k_render}]"


# ---------------------------------------------------------- ACSL (spec) -----

class Ctx:
    """Rendering context for ACSL: env (name->type), funs (spec_fun table +
    the task itself), ret (return name to render as \\result, or None),
    label (the memory label attached to labeled logic-fun calls), and
    seq_len (2026-09-09: name -> ACSL rendering of that seq's CURRENT
    length, overriding the default `{name}_n`; empty for every seq return
    whose length is pinned exactly, see `_expr_seq_len`/`lower()`, and
    non-empty only for a CAPACITY-tracked return -- `\\result` in the
    function's own post-state (`ensures`), the running local `r_len` while
    still inside the body (invariants can see a local; `ensures` cannot),
    see the seq value machinery section's CAPACITY discussion)."""
    def __init__(self, env, funs, ret=None, label="Here", seq_len=None):
        self.env, self.funs, self.ret, self.label = env, funs, ret, label
        self.seq_len = seq_len or {}

    def bind(self, name, ty):
        env2 = dict(self.env)
        env2[name] = ty
        return Ctx(env2, self.funs, self.ret, self.label, self.seq_len)


def acsl_call(c: dict, ctx: Ctx) -> str:
    fun = c["fun"]
    info = ctx.funs[fun]
    if info.get("is_task"):
        raise NotImplementedError(
            "task self-call in spec position (v1 specs are anchored by "
            "spec_funs, never the task's own name)")
    parts = []
    for p, a in zip(info["params"], c["args"], strict=True):
        if p["type"] == "seq":
            s = seq_var(a, ctx.env)
            parts += [s, f"{s}_n"]
        else:
            parts.append(term(a, ctx))
    lab = f"{{{ctx.label}}}" if info["labeled"] else ""
    return f"{fun}{lab}({', '.join(parts)})"


def _gap(rendered: str) -> str:
    """A space when the operand already starts with a minus, so unary minus
    on a negative renders as `- -2` and not `--2`.

    C reads `--` as the decrement operator, so `-(--2)` is not double
    negation, it is a predecrement of a literal and frama-c rejects the file
    with a User Error. Measured 2026-09-04: the metamorphic double-negation
    rewrite produced exactly that on 10 cells, every one framac, every one
    scored malformed. The same hazard exists for `+ +` and it is spelled the
    same way here."""
    return " " + rendered if rendered[:1] in "-+" else rendered


def term(e: dict, ctx: Ctx) -> str:
    """ACSL term. int-typed terms are `integer`-valued; bool-typed terms are
    ACSL boolean terms (comparisons / && / || / ! coerce in term position,
    measured on the count spec_fun's guard)."""
    if "int" in e:
        return str(e["int"])
    if "bool" in e:
        return "\\true" if e["bool"] else "\\false"
    if "var" in e:
        n = e["var"]
        base = "\\result" if n == ctx.ret else n
        return f"({base} != 0)" if ctx.env[n] == "bool" else base
    if "ite" in e:
        i = e["ite"]
        return (f"(({term(i['cond'], ctx)}) ? ({term(i['then'], ctx)}) "
                f": ({term(i['else'], ctx)}))")
    if "call" in e:
        return acsl_call(e["call"], ctx)
    if "forall" in e or "exists" in e:
        raise NotImplementedError("quantifier in ACSL term position")
    op, args = e["op"], e.get("args", [])
    _strlib_abstain(op, "ACSL term position")
    if op == "len":
        return _seq_len_render(args[0], ctx)
    if op == "at":
        return _seq_at_render(args[0], term(args[1], ctx), ctx)
    if op in ("fst", "snd"):
        # p.0 / p.1 (SPEC.md "Pairs", 2026-09-10): this backend's pair
        # value IS a C struct (see the pair value machinery section,
        # `_pair_struct_name`), so the projection is a plain ACSL field
        # access on whatever `term(args[0], ctx)` already renders for the
        # pair-typed operand -- a bare name (a var, `\result` included via
        # the `var` case above) in both committed tasks, but the
        # rendering is generic over any pair-typed term this backend can
        # otherwise express (never `pair(...)` itself, see below).
        field = "a" if op == "fst" else "b"
        return f"({term(args[0], ctx)}).{field}"
    if op == "pair":
        # A `pair(...)` node has no ACSL TERM rendering, the same gap
        # `update`/`fill`/a seq literal already have and for the same
        # reason: this backend's pair value is a C struct construction
        # (`(struct t_pair_T1_T2){a, b}`, a C99 compound literal), which
        # is executable-C syntax, not ACSL logic syntax, and is consumed
        # exclusively as the whole right-hand side of a body assignment
        # to a pair-typed name (`stmts()`'s ordinary, non-seq assign
        # case, via `cexpr()`). Neither committed task constructs a pair
        # directly inside `requires`/`ensures`/an invariant (both only
        # ever project `fst`/`snd` of the RETURN there), so this is a
        # stated scope limit, not a silently wrong lowering.
        raise NotImplementedError(
            "`pair` has no ACSL term rendering (this backend's pair value "
            "is a C struct construction, executable-C syntax, not ACSL "
            "logic); pair values may only be produced as the right-hand "
            "side of a body assignment to a pair-typed name")
    if op == "neg":
        return f"(-{_gap(term(args[0], ctx))})"
    if op == "not":
        return f"(!{term(args[0], ctx)})"
    if op == "implies":
        return f"((!({term(args[0], ctx)})) || ({term(args[1], ctx)}))"
    if op in ("and", "or"):
        glue = " && " if op == "and" else " || "
        return "(" + glue.join(term(a, ctx) for a in args) + ")"
    if op in DIVMOD:
        fn = "t_div" if op == "div" else "t_mod"
        return f"{fn}({term(args[0], ctx)}, {term(args[1], ctx)})"
    if op in SEQOPS:
        # `update`/`fill` (2026-09-09) denote a fresh seq VALUE, and this
        # backend has no ACSL rendering of a bare seq value: it only ever
        # renders a seq through `len`/`at`/extensional `==`, all of which
        # need a real backing C array, and `update`/`fill` themselves are
        # consumed exclusively as the whole right-hand side of an
        # assignment to a seq-typed name (`stmts()`'s seq-assignment
        # codegen), never nested inside a spec/term position. Reaching
        # here means one appeared somewhere this lowering does not (yet)
        # give a seq value a term rendering, e.g. inside `requires` or
        # `ensures` directly rather than a body assignment.
        raise NotImplementedError(
            f"`{op}` has no ACSL term rendering (no backing buffer here); "
            f"seq values may only be produced as the right-hand side of a "
            f"body assignment to a seq-typed name")
    if op == "seq":
        # A literal `[e1, ..., en]` (2026-09-09) is the same shape as
        # `update`/`fill` above: it denotes a fresh seq value with no
        # backing buffer at this position, so it has no term rendering
        # except as the whole right-hand side of a body assignment.
        raise NotImplementedError(
            "`seq` (a literal) has no ACSL term rendering (no backing "
            "buffer here); seq values may only be produced as the "
            "right-hand side of a body assignment to a seq-typed name")
    if op == "slice" and typ(e, ctx.env, ctx.funs) == "seq":
        # A slice reaching TERM position directly (not as `at`/`len`'s own
        # operand, handled above by `_seq_len_render`/`_seq_at_render`) is
        # the same gap: no backing buffer for a bare seq value.
        raise NotImplementedError(
            "`slice` reaching ACSL term position directly has no "
            "rendering; this lowering only supports a slice in READ "
            "position as `at`'s or `len`'s own argument, or as the whole "
            "right-hand side of a body assignment to a seq-typed name")
    if op == "+" and typ(e, ctx.env, ctx.funs) == "seq":
        # Concatenation (2026-09-09), the seq-typed half of the
        # polymorphic `+`: same gap again, never silently treated as int
        # addition (ARITH's own `+` below would render two POINTERS with
        # `+`, a different and wrong theorem).
        raise NotImplementedError(
            "seq concatenation (`+`) has no ACSL term rendering (no "
            "backing buffer here); seq values may only be produced as "
            "the right-hand side of a body assignment to a seq-typed name")
    if op in ARITH or op in CMP:
        o = ARITH.get(op) or CMP[op]
        return f"({term(args[0], ctx)} {o} {term(args[1], ctx)})"
    raise ValueError(f"t has no operator {op!r}")



def _conj(parts):
    parts = [x for x in parts if x is not None]
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else "(" + " && ".join(parts) + ")"


def defs(e: dict, ctx: Ctx):
    """SPEC.md definedness of a spec expression, as an ACSL predicate that
    must be PROVEN, or None when trivially defined.

    ACSL's logic is total: an out-of-range s[i] denotes an unconstrained
    value, so `s[-1] == s[-1]` proves by reflexivity and the obligation t
    requires vanishes. Measured 2026-09-01 (ground-truth wave): four false
    theorems about undefined elements scored VERIFIED, the only kernel of
    seven to accept them. The lowering therefore emits the domain
    obligation itself, following SPEC's own evaluation order: `and`, `or`,
    `implies` and `ite` guard the definedness of what they may not
    evaluate, and a quantifier body must be defined at EVERY range point,
    for exists as much as forall.

    Residual, stated rather than hidden: spec_fun bodies are axiomatized
    as total ACSL logic functions, so an `at` INSIDE a spec_fun applied
    outside its guarded range keeps the reflexivity hole; the committed
    tasks guard their ranges, and hostile tasks are the ground-truth
    fuzzer's beat.

    `div`/`mod` (2026-09-08) is t's second partial operator: SPEC.md leaves
    both undefined at y == 0, so the domain obligation emitted here is
    `y != 0`, the same shape as `at`'s bound check. t_div/t_mod (see
    T_DIVMOD_ACSL above) are themselves total ACSL logic functions, well
    defined at y == 0 too (ACSL's own `/`/`%` are, measured), so nothing
    breaks if this obligation goes undischarged; it is emitted purely
    because SPEC.md says y == 0 is undefined, not because the kernel would
    otherwise crash.
    """
    if "int" in e or "bool" in e or "var" in e:
        return None
    if "ite" in e:
        i = e["ite"]
        c = pred(i["cond"], ctx)
        dt, de = defs(i["then"], ctx), defs(i["else"], ctx)
        return _conj([defs(i["cond"], ctx),
                      None if dt is None else f"(({c}) ==> {dt})",
                      None if de is None else f"((!({c})) ==> {de})"])
    if "forall" in e or "exists" in e:
        q = e["forall"] if "forall" in e else e["exists"]
        # Fresh binder, so the defs guard never re-binds the name the
        # enclosing \\exists or \\forall from pred() already uses. On the
        # exists definedness witness Why3/Alt-Ergo fails either way with
        # "bound variable in of_term" (measured 2026-09-02, with and
        # without the rename); that lands as TOOL_ERROR, which is ok=False
        # and never evidence, so the witness still cannot score VERIFIED.
        fresh = q["var"] + "_d"
        c2 = ctx.bind(fresh, "int")
        db = defs(subst(q["body"], {q["var"]: {"var": fresh}}), c2)
        rng = (f"({term(q['lo'], ctx)}) <= {fresh} "
               f"&& {fresh} < ({term(q['hi'], ctx)})")
        return _conj([defs(q["lo"], ctx), defs(q["hi"], ctx),
                      None if db is None else
                      f"(\\forall integer {fresh}; ({rng}) ==> {db})"])
    if "call" in e:
        return _conj([defs(a, ctx) for a in e["call"].get("args", [])])
    op, args = e["op"], e.get("args", [])
    if op == "at":
        i = term(args[1], ctx)
        base = args[0]
        if base.get("op") == "slice":
            # `at` on a slice (2026-09-09, read position): defined iff the
            # SLICE itself is (its own `0 <= a <= b <= len(s)` domain,
            # picked up via `defs(base, ctx)` below hitting the `slice`
            # case) AND the index is within the slice's own length, `b -
            # a`, not the base's.
            n = _seq_len_render(base, ctx)
            return _conj([defs(base, ctx), defs(args[1], ctx),
                          f"(0 <= ({i}) && ({i}) < {n})"])
        if (base.get("op") == "at"
                and is_nested_seq_type(typ(base["args"][0], ctx.env, ctx.funs))):
            # SEQ VALUE, executable position, item 4 (nested), 2026-09-11
            # (framac-seq): `at(at(m, i), j)`'s own DEFINEDNESS obligation
            # (`fz_p_nest_cell`'s `ensures`) is bounded by ROW i's length,
            # the same `m_off[i + 1] - m_off[i]` formula `_seq_at_render`'s
            # matching case (and `cexpr`'s) already use, not
            # `seq_var(base, ...)`, which raises on a non-variable base.
            mv = seq_var(base["args"][0], ctx.env)
            ib = term(base["args"][1], ctx)
            n = f"({mv}_off[({ib}) + 1] - {mv}_off[({ib})])"
            return _conj([defs(base, ctx), defs(args[1], ctx),
                          f"(0 <= ({i}) && ({i}) < {n})"])
        n = ctx.seq_len.get(seq_var(base, ctx.env),
                            f"{seq_var(base, ctx.env)}_n")
        return _conj([defs(args[1], ctx), f"(0 <= ({i}) && ({i}) < {n})"])
    if op == "slice":
        # s[a..b]: DEFINED IFF 0 <= a <= b <= len(s) (SPEC.md "Sequences:
        # literals, concatenation, slices", 2026-09-09), the same
        # obligation shape as `at`'s own bound, over the whole range
        # rather than a point. Reached both directly (a slice used as a
        # whole spec expression, e.g. inside `at`/`len`'s own definedness
        # above) and via the generic fallthrough at the bottom of this
        # function (a literal's or concatenation's own defs already walk
        # every arg, and a slice inside either would land here too).
        s_e, lo, hi = args
        lo_t, hi_t = term(lo, ctx), term(hi, ctx)
        n = seq_var(s_e, ctx.env)
        nlen = ctx.seq_len.get(n, f"{n}_n")
        return _conj([defs(lo, ctx), defs(hi, ctx),
                      f"(0 <= ({lo_t}) && ({lo_t}) <= ({hi_t}) "
                      f"&& ({hi_t}) <= {nlen})"])
    if op == "update":
        # SPEC.md "Sequences as values" (2026-09-09): `s[i := v]` is
        # DEFINED IFF `0 <= i < len(s)`, the identical shape as `at`'s own
        # bound, over the update's base seq rather than a read.
        i = term(args[1], ctx)
        n = seq_var(args[0], ctx.env) + "_n"
        return _conj([defs(args[1], ctx), defs(args[2], ctx),
                      f"(0 <= ({i}) && ({i}) < {n})"])
    if op == "fill":
        # `seq(n, v)` is DEFINED IFF `n >= 0`.
        n = term(args[0], ctx)
        return _conj([defs(args[0], ctx), defs(args[1], ctx),
                      f"(({n}) >= 0)"])
    if op in DIVMOD:
        y = term(args[1], ctx)
        return _conj([defs(args[0], ctx), defs(args[1], ctx),
                      f"(({y}) != 0)"])
    if op in ("and", "or", "implies"):
        acc, guards = [defs(args[0], ctx)], []
        for k, a in enumerate(args[1:], 1):
            prev = args[k - 1] if op != "implies" else args[0]
            g = pred(prev, ctx)
            if op == "or":
                g = f"!({g})"
            d = defs(a, ctx)
            guards.append(g)
            if d is not None:
                acc.append("((" + " && ".join(guards) + f") ==> {d})")
        return _conj(acc)
    return _conj([defs(a, ctx) for a in args])


def pred(e: dict, ctx: Ctx) -> str:
    """ACSL predicate (for requires/ensures/invariants/asserts/lemmas)."""
    if "bool" in e:
        return "\\true" if e["bool"] else "\\false"
    if "var" in e:
        n = e["var"]
        base = "\\result" if n == ctx.ret else n
        return f"({base} != 0)"                  # bool-typed C variable
    if "forall" in e or "exists" in e:
        kind = "forall" if "forall" in e else "exists"
        q = e[kind]
        c2 = ctx.bind(q["var"], "int")
        rng = (f"({term(q['lo'], ctx)}) <= {q['var']} "
               f"&& {q['var']} < ({term(q['hi'], ctx)})")
        body = pred(q["body"], c2)
        glue = "==>" if kind == "forall" else "&&"
        return f"(\\{kind} integer {q['var']}; ({rng}) {glue} ({body}))"
    if "ite" in e:
        i = e["ite"]
        c = pred(i["cond"], ctx)
        return (f"((({c}) && ({pred(i['then'], ctx)})) "
                f"|| ((!({c})) && ({pred(i['else'], ctx)})))")
    if "call" in e:
        return f"({acsl_call(e['call'], ctx)} == \\true)"
    op, args = e["op"], e.get("args", [])
    _strlib_abstain(op, "ACSL predicate position")
    if op == "not":
        return f"(!{pred(args[0], ctx)})"
    if op == "implies":
        return f"({pred(args[0], ctx)} ==> {pred(args[1], ctx)})"
    if op in ("and", "or"):
        glue = " && " if op == "and" else " || "
        return "(" + glue.join(pred(a, ctx) for a in args) + ")"
    if op in ("==", "!="):
        t0 = typ(args[0], ctx.env, ctx.funs)
        if t0 == "bool":
            eq = f"({pred(args[0], ctx)} <==> {pred(args[1], ctx)})"
            return eq if op == "==" else f"(!{eq})"
        if t0 == "seq":
            # `==`/`!=` on two seqs is EXTENSIONAL (SPEC.md "Sequences as
            # values", 2026-09-09): equal lengths and equal elements at
            # every index. Rendered through `_seq_len_render`/
            # `_seq_at_render` (their own READ-position rules), not a
            # bare `seq_var` name pasted directly: both already cover a
            # bare seq variable (`{v}_n`/`v[__k]`, this branch's original
            # and only case before 2026-09-12), and `_seq_at_render`'s
            # own "at(nested, i)" case (added for `fz_p_nest_cell`,
            # `m[i][j]`) already renders indexing INTO a ROW the same
            # formula way, so passing it a ROW EXPRESSION `at(m, i)`
            # itself as `e` (this call's `k_render` binding the
            # comparison's own quantified index, not `at`'s inner one)
            # falls into that exact case and reads the row's cell as
            # `m_data[m_off[i] + __k]`, no row ever materialized. FIXED
            # 2026-09-12 (ROADMAP 13.4, framac-seq4): `fz_p_nest_eq`
            # ("two nested seqs are equal iff same length and equal
            # rows") states this exact shape in its own `ensures`, one
            # extensional seq `==` per ROW, `at(m, k) == at(n, k)` under
            # a `\forall k`, and used to reach this branch's old
            # `seq_var(args[0], ...)` call with `args[0]` a non-variable
            # `at(...)` node, `NotImplementedError: seq position holds
            # non-variable {...}` (MEASURED, frama-c 33.0, before this
            # patch: `fz_p_nest_eq` real ABSTAIN). No executable C loop
            # is needed here (ROADMAP 13.4's item 2 named one, but this
            # call site is `pred()`, ACSL PREDICATE position -- pure
            # logic, not memory -- not `cexpr`'s executable-value
            # position, which still refuses the same shape by name,
            # unchanged, see its own `==`/`!=` case above).
            an = _seq_len_render(args[0], ctx)
            bn = _seq_len_render(args[1], ctx)
            eq = (f"(({an} == {bn}) && "
                 f"(\\forall integer __k; 0 <= __k && __k < {an} "
                 f"==> {_seq_at_render(args[0], '__k', ctx)} == "
                 f"{_seq_at_render(args[1], '__k', ctx)}))")
            return eq if op == "==" else f"(!{eq})"
        if isinstance(t0, dict) and "pair" in t0:
            # `==`/`!=` on two pairs is COMPONENTWISE (SPEC.md "Pairs",
            # 2026-09-10: "the polymorphic `==` again, two ints, two
            # bools, two seqs, two pairs"). ACSL has no struct equality
            # worth relying on here (this backend's struct is a plain C
            # aggregate with no logic-level `==`, and even if WP accepted
            # one it would be bitwise/representation equality, not the
            # componentwise value equality SPEC.md means), so this
            # rewrites to a conjunction of the two projections' own
            # equality and recurses through `pred()` again: `fst`/`snd`
            # are ordinary Exprs, so if a component is itself a seq or a
            # bool the recursive call picks up EXTENSIONAL or `<==>`
            # equality exactly as it would for a bare seq/bool variable,
            # one rule for `==` used twice rather than two.
            a, b = args
            fst_eq = {"op": "==", "args": [{"op": "fst", "args": [a]},
                                           {"op": "fst", "args": [b]}]}
            snd_eq = {"op": "==", "args": [{"op": "snd", "args": [a]},
                                           {"op": "snd", "args": [b]}]}
            eq = pred({"op": "and", "args": [fst_eq, snd_eq]}, ctx)
            return eq if op == "==" else f"(!{eq})"
        return f"({term(args[0], ctx)} {CMP[op]} {term(args[1], ctx)})"
    if op in CMP:
        return f"({term(args[0], ctx)} {CMP[op]} {term(args[1], ctx)})"
    if op in ("fst", "snd"):
        # PAIRS, extended 2026-09-10 (fuzz family v1pairs, the found/val
        # idiom: `ensures r.0 == (\exists ...)`, a `(bool, int)` return's
        # bool component projected directly into predicate position, not
        # nested under a comparison `pred()` already dispatches on `t0`
        # for). Before this case, `pred()` had no "fst"/"snd" branch at
        # all and fell through to the bottom `raise`, a lowering CRASH
        # (measured: `ValueError: no predicate form for operator 'fst'`
        # on 7 of the 18-task framac residual, every one this exact
        # shape) rather than a proof result. `term()`'s own "fst"/"snd"
        # case already renders the projection as a plain ACSL field
        # read, `(p).a`/`(p).b` (int-valued: this backend's field is
        # always C `int`, the bool-as-0/1 convention that already lets a
        # bool component cost nothing extra); reaching this branch at
        # all means the projection's OWN type is bool (an int-typed
        # projection is only ever consumed inside a comparison, which
        # `pred()`'s `==`/`CMP` cases above already route through
        # `term()`, never here), so this applies the SAME `!= 0` bool
        # convention the `var` case above already applies to a bare
        # bool-typed C name, to the field read instead of the name.
        field = "a" if op == "fst" else "b"
        return f"(({term(args[0], ctx)}).{field} != 0)"
    raise ValueError(f"no predicate form for operator {op!r}")


# ------------------------------------------------------------- C (code) -----
#
# PAIRS (SPEC.md "Pairs", 2026-09-10, ROADMAP 12.7). C has no product value
# either, so this is a second MEASURED encoding choice next to seq's own
# (the seq value machinery section, above): a struct returned/held BY
# VALUE, `struct t_pair_T1_T2 { int a; int b; };`, one field per component,
# both fields plain C `int` (this backend's own bool-as-int-0/1 convention
# already applies before a pair's own encoding does anything, so a bool
# component costs nothing extra: `_pair_field_c` below is the identity on
# both "int" and "bool"). MEASURED by hand (frama-c/WP) on divmod_pair
# BEFORE this code was written (RULES: measure first): a hand-written
# probe in exactly this shape (the contract stated on `\result.a`/
# `\result.b`, the body a plain compound-literal assignment) scored the
# real function 10/10 goals proved and a hand-written refutation
# certificate (the shape `_value_certificate` below now emits generally)
# scored its own named goal VALID under the pinned budget -- candidate (a)
# of the two the construct brief named, kept because it worked outright;
# candidate (b) (two `long *ra, long *rb` out-parameters) was never built,
# since there was nothing left for it to fix. `pair(a, b)` is a C99
# compound literal, `(struct t_pair_T1_T2){a, b}`; `fst`/`snd` are plain
# field reads, `.a`/`.b`, on both the C and the ACSL side (`\result.a` is
# exactly SPEC's own suggested rendering); `==`/`!=` on two pairs is
# componentwise (`pred()`'s own new branch, above), since ACSL has no
# struct equality this backend would trust (a bitwise/representation
# equality on a struct is not the value equality SPEC.md means, and this
# backend never asks WP for one).
#
# T1/T2 are restricted to "int"/"bool" by this backend, not by SPEC.md
# (which also allows "seq"): a pair with a seq component has no clean
# value semantics in a struct returned BY VALUE, since a seq is itself a
# caller-provided buffer PLUS a length (the seq value machinery section),
# and a struct field can hold neither a fresh buffer's storage nor a
# second, independent `\valid`/`\separated` obligation the caller could
# size in advance the way a bare seq return's own `{ret}_n` already is.
# CAPACITY mode's own machinery (a length-tracking local threaded through
# `Ctx.seq_len`) has nothing to attach itself to inside a struct field
# either. So `_pair_field_c` raises NotImplementedError BY NAME the
# moment a "seq" component is seen, never guessing a struct layout for it;
# neither committed task has one (`divmod_pair`, `min_max`: both
# `(int, int)`).
#
# FIXED 2026-09-10 (the framac fuzz family v1pairs's own 18-task residual,
# measured on the fuzz corpus, not on a committed task): a pair-typed
# PARAMETER or LOCAL. Both committed tasks use a pair only as a RETURN,
# and until this fix neither `stmts()`'s `var` case nor `lower()`'s
# `cparams` loop had a pair-typed branch to reach -- not a named
# NotImplementedError either, the thing this section's own discipline
# promises, but a silent WRONG lowering: `cparams` fell through its
# `else` and declared the struct-typed parameter as plain `int`, and
# `stmts()`'s `var` case did the identical wrong thing for a local, so
# every `.a`/`.b` field read or `fst`/`snd` projection on that name
# compiled to a C error on a plain `int` ("request for member ... in
# something not a structure"), read by frama-c as MALFORMED (9 of the 18)
# rather than refused by this file's own naming discipline. Both are now
# a struct passed/declared BY VALUE, exactly the RETURN's own encoding
# (`_pair_types_needed` below finds every distinct pair shape the task's
# C needs a struct for -- params, return, locals, and a `pair(...)`
# built and projected inline without ever being bound to a name,
# `fz_p_pair_proj`'s own shape -- so `lower()`'s header declares all of
# them, not only the return's). MEASURED (`fuzz_lower.py --only framac`
# on the residual): a struct parameter works in WP's Typed model the
# same way the struct return already did, no separate probe needed.
# Fixing the parameter case also exposed a second, previously
# unreachable defect on the SAME task family: `p == q` on two pair-typed
# PARAMETERS in EXECUTABLE position (`fz_v1pairs_053`'s `eq_params`
# shape) used to fall through `cexpr()`'s generic CMP dispatch to a bare
# C `==` on two `int`s (silently wrong, the params being mis-declared
# already hid it); once declared as structs, that same fallthrough would
# emit `p == q` on two STRUCTS, which is not legal C for an aggregate
# type -- `cexpr()` now has a componentwise `==`/`!=` case mirroring
# `pred()`'s own (below), so this is fixed rather than traded for a
# different malformed cause.
#
# Still NOT implemented, found by construction, kept as a named refusal
# because nothing in the framac residual needs it measured: a pair
# inside another pair's component (SPEC.md itself excludes this, "no
# pair of pairs"); a pair-valued spec_fun result (SPEC.md's own SpecFun
# grammar restricts `result` to "int"/"bool", so this never arises); a
# recursive call to a pair-returning task (SPEC.md "Gate 3" self-calls
# are unmeasured for pairs, mirroring the seq-return recursion refusal
# above). The loop frame rule needed NO change for a pair-typed name
# assigned inside a loop, on inspection rather than by construction:
# SPEC.md says plainly "the loop frame rule havocs a pair variable by
# name," and `_assigns_target`'s existing fallback (a bare name, for
# anything not seq-typed) already IS that: a pair is always assigned as
# one whole struct value by this lowering, never field-by-field, so the
# same `assigns p;` that already covers an int or bool local covers a
# pair one too. Nothing to fix, and nothing left silently unclaimed.


def _pair_field_c(t) -> str:
    """The C field type a pair component of t-type `t` gets: `int` for
    both "int" and "bool" (this backend's existing bool-as-int-0/1
    convention). Raises NotImplementedError by name for "seq" (see the
    section comment above) and for anything else unexpected (a nested
    pair; SPEC.md already excludes it, so reaching this is a bug, not a
    task this lowering merely declines)."""
    if t in ("int", "bool"):
        return "int"
    if t == "seq":
        raise NotImplementedError(
            "a pair with a seq component is refused by this lowering: a "
            "struct field returned BY VALUE has no clean ACSL value "
            "semantics for a buffer pointer plus a length (see the PAIRS "
            "section comment above `_pair_field_c`)")
    raise NotImplementedError(f"pair component type {t!r} not supported")


def _pair_struct_name(t1, t2) -> str:
    """`t_pair_{T1}_{T2}`, the struct type name for a `{"pair": [T1, T2]}`
    t-type. Validates both components via `_pair_field_c` first (raising
    its NotImplementedError, never silently naming a struct this lowering
    could not actually declare a sound field for)."""
    _pair_field_c(t1)
    _pair_field_c(t2)
    return f"t_pair_{t1}_{t2}"


def _pair_local_types(body: list) -> dict:
    """name -> declared type for every LOCAL `var` statement in `body`,
    walked recursively into `if`/`while` branches -- the same statement
    shape `assigned_names` already walks for its own (name-only) purpose,
    kept here as a separate small function since this one needs the
    declared TYPE, not just the name."""
    out = {}
    for s in body:
        if "var" in s:
            out[s["var"]["name"]] = s["var"]["type"]
        elif "if" in s:
            out.update(_pair_local_types(s["if"]["then"]))
            out.update(_pair_local_types(s["if"]["else"]))
        elif "while" in s:
            out.update(_pair_local_types(s["while"]["body"]))
    return out


def _pair_types_needed(task: dict, body: list, env: dict, funs: dict
                       ) -> list:
    """Every distinct `(T1, T2)` this task's C needs a `struct
    t_pair_T1_T2` declared for, added 2026-09-10 alongside the
    parameter/local fix above `_pair_field_c`: a pair-typed RETURN alone
    (`lower()`'s previous check) is not enough once a pair can also be a
    PARAMETER, a LOCAL, or built and immediately projected without ever
    being bound to a name at all (`fz_p_pair_proj`'s `fst((a, b))`, a
    plain int-typed task with no pair-typed name anywhere in its
    signature). So this gathers from every source a pair type can come
    from: every pair-typed parameter, the return if it is one, every
    pair-typed local (`_pair_local_types` above), and every `pair(...)`
    construction node found anywhere in the body, its own component
    types read off via `typ()` against a FULL env (params, return, and
    every local `_pair_local_types` found, regardless of where in the
    body a name is declared relative to where it is used -- a name's
    TYPE does not depend on statement order the way its VALUE does, and
    `typ()` only ever needs the former). Order is first-occurrence,
    duplicates dropped (a `dict` used as an ordered set, no value read
    back out of it); `lower()`'s header declares one `struct` line per
    entry, before anything in the file can use it."""
    full_env = dict(env)
    full_env.update(_pair_local_types(body))
    seen: dict = {}
    for p in task["params"]:
        if isinstance(p["type"], dict) and "pair" in p["type"]:
            seen[tuple(p["type"]["pair"])] = True
    rett = task["returns"][0]["type"]
    if isinstance(rett, dict) and "pair" in rett:
        seen[tuple(rett["pair"])] = True
    for t in full_env.values():
        if isinstance(t, dict) and "pair" in t:
            seen[tuple(t["pair"])] = True

    def scan(x):
        if isinstance(x, dict):
            if x.get("op") == "pair":
                t1 = typ(x["args"][0], full_env, funs)
                t2 = typ(x["args"][1], full_env, funs)
                seen[(t1, t2)] = True
            for v in x.values():
                scan(v)
        elif isinstance(x, list):
            for v in x:
                scan(v)
    scan(body)
    return list(seen.keys())


def cexpr(e: dict, env: dict, funs: dict, task_name: str,
         _div_style: str = "bf") -> str:
    """`_div_style` picks how a `div`/`mod` node renders: "bf" (the
    default, branch-free, safe in executable C position) or "ternary"
    (ACSL-annotation-safe, see `_divmod_ternary_cexpr` below). It is
    threaded through every recursive call so a `div`/`mod` nested ANYWHERE
    inside the expression (not only at the top) picks up the same style;
    the isArmstrong probe (2026-09-09) measured why this matters: its
    `t_mod(t_div(n, 10), 10)` bridging assert has a div node nested inside
    a mod node's `x` argument, and rendering the inner one branch-free
    while the outer stayed ternary put raw C boolean arithmetic (`(P) -
    (Q)`) inside an ACSL annotation, which Frama-C rejects as MALFORMED
    ("invalid operands to binary -; unexpected bool and bool") rather
    than a smoke or proof failure."""
    if "int" in e:
        return str(e["int"])
    if "bool" in e:
        return "1" if e["bool"] else "0"
    if "var" in e:
        return e["var"]
    if "forall" in e or "exists" in e:
        raise NotImplementedError("bounded quantifier in executable position")
    if "ite" in e:
        i = e["ite"]
        return (f"(({cexpr(i['cond'], env, funs, task_name, _div_style)}) "
                f"? ({cexpr(i['then'], env, funs, task_name, _div_style)}) "
                f": ({cexpr(i['else'], env, funs, task_name, _div_style)}))")
    if "call" in e:
        c = e["call"]
        if c["fun"] != task_name:
            # FRAMAC-CLOSURE, added 2026-09-14 (sweep r25's five sole-
            # framac-blocker rows, 412/426/436/554/629: each calls a
            # spec_fun predicate -- isEven, isOdd or isNegative -- from
            # inside its loop's `if` condition, executable position, not
            # ACSL. `_spec_fun_c` (below `spec_fun_acsl`) mirrors an
            # ELIGIBLE spec_fun as a plain C function `{name}_c`, called
            # here instead of raising; `lower()` emits that mirror's
            # definition into the header for every spec_fun that
            # qualifies (see `_spec_fun_c`'s own docstring for the
            # eligibility rule -- no seq-typed param, no self-recursion).
            # An INELIGIBLE spec_fun call still raises exactly the
            # original message, unchanged: no committed task (t/AGREEMENT
            # .md's 34) declares any spec_fun at all, so this widening
            # touches only the lifted corpus, never the regression bar.
            sf = funs.get(c["fun"])
            if (sf is None or sf.get("is_task")
                    or any(p["type"] == "seq" for p in sf["params"])
                    or not sf.get("executable")):
                raise NotImplementedError(
                    "spec_fun call in executable position (ACSL logic "
                    "functions are not executable)")
            cargs = ", ".join(
                cexpr(a, env, funs, task_name, _div_style) for a in c["args"])
            return f"{c['fun']}_c({cargs})"
        if funs[task_name]["result"] == "seq":
            # A seq-returning task (2026-09-09) is lowered to a `void` C
            # function with an output buffer parameter (see the seq value
            # machinery section), so it has no C VALUE this expression
            # position could hold; a recursive call to one would need a
            # second buffer for the callee's own return, which this
            # lowering does not allocate. Neither committed task recurses.
            raise NotImplementedError(
                "recursive call to a seq-returning task is not supported "
                "by this lowering (no C value-position representation "
                "for a seq)")
        parts = []
        for p, a in zip(funs[task_name]["params"], c["args"], strict=True):
            if p["type"] == "seq":
                s = seq_var(a, env)
                parts += [s, f"{s}_n"]
            else:
                parts.append(cexpr(a, env, funs, task_name, _div_style))
        return f"{task_name}_t({', '.join(parts)})"
    op, args = e["op"], e.get("args", [])
    if op in ("count", "find"):
        # framac-seq2, ROADMAP 13.4, 2026-09-11: `count(s, t)`/`find(s, t)`
        # in EXECUTABLE position (T_STRFIND_ACSL above), checked before
        # `_strlib_abstain` fires so a general receiver/pattern pair
        # reaches the prelude's `t_count_c`/`t_find_c` rather than the
        # blanket "no recursive ACSL definition" refusal. The receiver
        # `s` must be a bare seq-typed variable (`seq_var`'s own scope,
        # unchanged); the pattern `t` is either a bare seq-typed
        # variable too, or the EMPTY literal `[]` (SPEC.md's own
        # `count(s, []) == len(s) + 1` / `find(s, []) == 0` identities,
        # the two probes this pass measures) -- an empty pattern needs
        # no real buffer, since `\valid_read(t + (0 .. -1))` is vacuously
        # true of ANY pointer, so `s`'s own pointer stands in at length
        # 0. A non-empty LITERAL pattern (a `[e0, ...]` with elements, a
        # concat, a slice) is not lowered: that needs a materialized
        # buffer for the pattern this pass does not build, named below
        # rather than guessed at.
        s_e, t_e = args
        sv = seq_var(s_e, env)
        empty_pattern = t_e.get("op") == "seq" and not t_e.get("args")
        if not empty_pattern and "var" not in t_e:
            raise NotImplementedError(
                f"string library member `{op}` reaching executable "
                f"position with a non-variable, non-empty pattern "
                f"{t_e!r}: only a seq-typed variable or the empty "
                f"literal `[]` has a backing buffer for the pattern in "
                f"this lowering")
        if op == "count" and empty_pattern:
            # `t_count_c`'s own contract only gives the RECURSIVE value
            # `t_count(s, ns, t, 0, 0)`, not the closed form `ns + 1`
            # SPEC.md states and a task's `ensures` may need; that
            # closed form is an induction over the start index Alt-Ergo
            # cannot perform from one ground call (T_STRFIND_ACSL note
            # above), so the empty-pattern case renders through
            # `t_countempty_rec` instead, whose own `ensures` carries
            # BOTH the closed form and the bridge back to `t_count`.
            return f"t_countempty_rec({sv}, {sv}_n, 0)"
        if empty_pattern:
            t_ptr, t_n = sv, "0"
        else:
            tv = seq_var(t_e, env)
            t_ptr, t_n = tv, f"{tv}_n"
        fn = "t_find_c" if op == "find" else "t_count_c"
        return f"{fn}({sv}, {sv}_n, {t_ptr}, {t_n})"
    _strlib_abstain(op, "executable position")
    if op == "len":
        a0 = args[0]
        if a0.get("op") == "split" and len(a0.get("args", ())) == 1:
            # `len(s.split())` in EXECUTABLE position (SPEC.md "The
            # string library (v1)", 2026-09-11, word_count's own body,
            # `r := len(t2.split())`): calls the prelude's `t_wc_c`
            # helper (T_WORDCOUNT_ACSL), whose own contract
            # (`ensures \result == t_wc(s, n)`) is what lets the task's
            # `ensures r == len(s.split())` (an ACSL TERM position,
            # `_seq_len_render`'s matching case) discharge against this
            # call's return value.
            base = a0["args"][0]
            v = seq_var(base, env)
            return f"t_wc_c({v}, {v}_n)"
        if a0.get("op") == "at":
            base, idx = a0["args"]
            if base.get("op") == "seq":
                # SEQ VALUE, executable position, item 1b (nested
                # literal row length), 2026-09-11 (ROADMAP 13.4,
                # framac-seq3): `len([[1, 2], [3]][k])`
                # (`fz_p_nest_lit`'s own shape) is `len(at(literal, k))`
                # where the ROW SELECTED never needs a C value of its
                # own, only its element count -- each row of a nested
                # LITERAL is itself a literal, so every row's length is
                # a compile-time constant; a C99 compound literal of
                # those constants, indexed by `k`, is the same bounded,
                # stack-scoped idiom `at([e0,...],k)` already uses for a
                # plain literal (`op == "seq"` case below), one level up.
                lens = ", ".join(str(len(row.get("args", ())))
                                 for row in base.get("args", ()))
                i = cexpr(idx, env, funs, task_name, _div_style)
                return f"((int[]){{{lens}}})[{i}]"
            # `len(m[i])` in EXECUTABLE position (SPEC.md "Nested
            # sequences", 2026-09-10: `row_max_len`'s own body, `r = len(
            # at(m, 0))` and `if len(at(m, i)) > r`). Same formula
            # `_seq_len_render`'s matching ACSL-side case renders, over
            # the offsets array, since a row has no C value to
            # materialize first.
            m = seq_var(base, env)
            i = cexpr(idx, env, funs, task_name, _div_style)
            return f"({m}_off[({i}) + 1] - {m}_off[({i})])"
        if "var" not in a0:
            # SEQ VALUE, executable position, item 2 (concat)/item 3
            # (slice), 2026-09-11 (framac-seq): `len` of an unmaterialized
            # seq expression (a literal, slice, or `+`, `fz_p_concat_len`'s
            # own shape) never needs the buffer itself, only a closed-form
            # count -- see `_seq_val_len_c`.
            return _seq_val_len_c(a0, env, funs, task_name, _div_style)
        return f"{seq_var(a0, env)}_n"
    if op == "at":
        # NAMED REFUSAL, added 2026-09-10: a nested seq's ROW reaching
        # `at` in executable position directly (not `len`'s own operand,
        # handled above) has no C representation (THE ENCODING note
        # below `assigned_names`) -- rendering it as `m[i]` would be a
        # SILENT WRONG lowering (`m` is never declared as a bare `int *`
        # in this encoding, only `m_data`/`m_off`/`m_n` are), so this
        # checks the base's own type rather than let a malformed C
        # reference through.
        base = args[0]
        if is_nested_seq_type(typ(base, env, funs)):
            raise NotImplementedError(
                "nested seq (seq<seq>) `at` reaching executable position "
                "directly (not wrapped in `len`): a row VALUE has no C "
                "representation in the flat data+offsets encoding, only "
                "its LENGTH does, via `len(m[i])`")
        if (base.get("op") == "at"
                and is_nested_seq_type(typ(base["args"][0], env, funs))):
            # SEQ VALUE, executable position, item 4 (nested), 2026-09-11
            # (framac-seq): `at(at(m, i), j)` -- `m[i][j]` -- is a CELL of
            # a nested seq's row, `fz_p_nest_cell`'s own shape (the row
            # itself, `at(m, i)` alone, has no C value and stays refused
            # above; only a further `at` consuming that row as ANOTHER
            # `at`'s base is handled here). The flat data+offsets encoding
            # (THE ENCODING note below `assigned_names`) puts row `i`'s
            # elements at `m_data[m_off[i] .. m_off[i+1] - 1]`, so cell
            # `j` of that row is `m_data[m_off[i] + j]` directly, no row
            # buffer ever materialized.
            m, i_e = base["args"]
            mv = seq_var(m, env)
            i_c = cexpr(i_e, env, funs, task_name, _div_style)
            j_c = cexpr(args[1], env, funs, task_name, _div_style)
            return f"{mv}_data[({mv}_off[{i_c}]) + ({j_c})]"
        if base.get("op") == "seq":
            # SEQ VALUE, executable position, item 1 (literal), 2026-09-11
            # (framac-seq): `at([e0, ..., en-1], k)` -- `fz_p_lit_index`'s
            # own shape, `[3, 5, 7][1]` -- has no seq-typed C variable to
            # index (the literal is never assigned anywhere first), so
            # this renders a C99 compound literal in place, `((int[]){e0,
            # ..., en-1})[k]`: a bounded, stack-scoped array with exactly
            # the literal's own element count as its capacity, no malloc,
            # indexed by the ordinary `at`-bounds assert `at_asserts`
            # already emits in front of this statement from `code_ats`'s
            # own `"at"` tag (unchanged: that tag's `seq_var(args[0],
            # env)` call is why item 1 could not land without ALSO
            # teaching `seq_var` this shape -- see `code_ats`'s own `at`
            # case, patched alongside this one).
            elems = ", ".join(
                cexpr(a, env, funs, task_name, _div_style)
                for a in base.get("args", ()))
            k_c = cexpr(args[1], env, funs, task_name, _div_style)
            return f"((int[]){{{elems}}})[{k_c}]"
        return (f"{seq_var(base, env)}"
                f"[{cexpr(args[1], env, funs, task_name, _div_style)}]")
    if op == "pair":
        # (a, b) (SPEC.md "Pairs", 2026-09-10): a C99 compound literal for
        # this backend's struct-by-value encoding (see the section
        # comment above `_pair_field_c`). `typ()` gives the two
        # component t-types (never re-derived from `e` itself, since a
        # pair's own declared type is not carried on the AST node, only
        # inferable from its arguments, exactly as `+`'s seq/int dispatch
        # already infers from its first operand).
        t1 = typ(args[0], env, funs)
        t2 = typ(args[1], env, funs)
        sname = _pair_struct_name(t1, t2)
        a_c = cexpr(args[0], env, funs, task_name, _div_style)
        b_c = cexpr(args[1], env, funs, task_name, _div_style)
        return f"(struct {sname}){{{a_c}, {b_c}}}"
    if op in ("fst", "snd"):
        # p.0 / p.1: a plain field read on whatever `cexpr` already
        # renders for the pair-typed operand.
        field = "a" if op == "fst" else "b"
        return f"({cexpr(args[0], env, funs, task_name, _div_style)}).{field}"
    if op == "neg":
        return f"(-{_gap(cexpr(args[0], env, funs, task_name, _div_style))})"
    if op == "not":
        return f"(!{cexpr(args[0], env, funs, task_name, _div_style)})"
    if op == "implies":
        a, b = (cexpr(x, env, funs, task_name, _div_style) for x in args)
        return f"((!({a})) || ({b}))"
    if op in ("and", "or"):
        glue = " && " if op == "and" else " || "
        return ("(" + glue.join(cexpr(a, env, funs, task_name, _div_style)
                                for a in args) + ")")
    if op in DIVMOD:
        xc = cexpr(args[0], env, funs, task_name, _div_style)
        yc = cexpr(args[1], env, funs, task_name, _div_style)
        rem = f"(({xc}) % ({yc}))"
        if _div_style == "ternary":
            # ACSL-annotation-safe, see `_divmod_ternary_cexpr`: the
            # pre-2026-09-09 shape, syntactically parallel to
            # T_DIVMOD_ACSL's own definition.
            if op == "mod":
                return (f"({rem} < 0 ? {rem} + "
                        f"(({yc}) < 0 ? -({yc}) : ({yc})) : {rem})")
            quo = f"(({xc}) / ({yc}))"
            return (f"({rem} < 0 ? {quo} - (({yc}) > 0 ? 1 : -1) : {quo})")
        # BRANCH-FREE, corrected 2026-09-09 (see the DIV/MOD SMOKE note
        # below): C's `/`/`%` truncate toward zero (measured, see
        # T_DIVMOD_ACSL), and the correction from truncating to Euclidean
        # used to be a C `?:` matching t_mod/t_div's own ternary shape.
        # That ternary is a live branch in EXECUTABLE position, and once a
        # task's invariants pin the sign of x or y (x >= 0 in a loop, a
        # fixed positive y), one arm becomes provably unreachable and
        # -wp-smoke-tests dooms it. So this rendering never emits `?:`:
        # `(cond)` used as a C int is already 0 or 1 with no branch node,
        # and the correction term is built by arithmetic on that 0/1
        # value instead of by selecting between two evaluated arms.
        neg = f"({rem} < 0)"          # 0 or 1, not a branch
        y_neg = f"(({yc}) < 0)"       # 0 or 1
        if op == "mod":
            abs_y = f"((1 - 2 * {y_neg}) * ({yc}))"
            return f"({rem} + {neg} * {abs_y})"
        quo = f"(({xc}) / ({yc}))"
        y_pos = f"(({yc}) > 0)"       # 0 or 1
        sign_y = f"({y_pos} - {y_neg})"          # 1 or -1 (y != 0)
        return f"({quo} - {neg} * {sign_y})"
    if op in ("==", "!="):
        t0 = typ(args[0], env, funs)
        if t0 == "seq" or is_nested_seq_type(t0):
            # SEQ VALUE, executable position, item 4 (nested), 2026-09-11
            # (framac-seq): NAMED REFUSAL, not a silent wrong answer.
            # `==`/`!=` on two seqs is EXTENSIONAL (`pred()`'s own
            # matching branch, used for `ensures`/ACSL predicate
            # position), which needs a `\forall`-shaped comparison this
            # function cannot render as a single C VALUE expression (no
            # loop belongs inside `cexpr`'s own return, and a bare `s ==
            # t` on two `int *` operands would be C POINTER identity, a
            # completely different and WRONG relation this lowering must
            # never emit silently). Measured reaching here for the first
            # time by `fz_p_nest_eq` (SPEC.md "Nested sequences"), whose
            # body computes `r := (m == n)` directly rather than through
            # an `if`/`ensures` case split; no committed task assigns a
            # bare seq `==`/`!=` to a bool-typed name, so this raises
            # rather than guess a loop-based rendering this pass did not
            # measure.
            raise NotImplementedError(
                "seq extensional equality (==/!=) reaching executable "
                "position directly (assigned to a bool-typed name, not "
                "used only in an `ensures`/ACSL predicate): this "
                "lowering has no C VALUE rendering for it, only a loop "
                "would compute it, and this pass does not build one")
        if isinstance(t0, dict) and "pair" in t0:
            # PAIRS, extended 2026-09-10: `p == q` in EXECUTABLE position
            # (SPEC.md's polymorphic `==`, `fz_v1pairs_053`'s own
            # `eq_params` shape, one of the 9 tasks that used to read
            # framac malformed/malformed). C has no struct `==` this
            # lowering trusts here any more than `pred()`'s own
            # componentwise ACSL branch above does (a plain C struct
            # comparison is not even legal syntax for an aggregate
            # type, so left unhandled this would have kept emitting
            # `(p == q)` on two `struct` operands once the cparams fix
            # below gave them a real struct type -- a SECOND malformed
            # cause on the same task, only visible once the first one
            # was fixed). Componentwise, the same rule `pred()`'s own
            # branch above uses.
            #
            # BRANCH-FREE, not `cexpr()`'s ordinary "and" (`&&`):
            # MEASURED on `fz_v1pairs_053`'s own wrong-var twin (`p == q`
            # mutated to `q == q`, a certificate whose replay substitutes
            # LITERAL struct values for `p`/`q`): a plain `&&` gives WP's
            # smoke-test instrumentation a real CFG branch (the "first
            # conjunct false, second never evaluated" arm), and once the
            # first conjunct is a REFLEXIVE or otherwise Qed-decidable
            # comparison on ground literals, that arm is provably dead --
            # correctly DOOMED, the harmless finding `_all_obligations_
            # proved` already exempts everywhere else, but the
            # certificate's own audit (`_cert_status`, `verifiers/
            # framac.py`) has no matching exemption for a doomed smoke
            # goal INSIDE the certificate function itself, so the
            # refutation certificate was rejected (UNPROVED, not
            # REFUTED) for a reason that has nothing to do with whether
            # the refutation itself holds. Both `fst`/`snd` projections
            # are ALWAYS DEFINED on a pair (SPEC.md's own words), with no
            # side effect either, so unlike the general `and`/`or` case
            # (`code_ats`'s conservative refusal exists because a SECOND
            # conjunct's safety can genuinely depend on the first, `at`/
            # `div` being the reason `&&` must short-circuit there) there
            # is nothing here for short-circuiting to protect: `&`
            # (bitwise, on two already-0/1 C ints) gives the identical
            # boolean VALUE with no implicit branch for a smoke test to
            # find dead, the same branch-free-over-a-real-C-operator
            # move the DIVMOD section above already made for the
            # identical reason (see its own "BRANCH-FREE, corrected
            # 2026-09-09" comment). Scope: this rewrite only, not
            # `cexpr()`'s general "and"/"or" case, which stays `&&`/`||`
            # everywhere else in this file, short-circuiting exactly
            # where that is load-bearing for safety.
            a, b = args
            fst_eq = {"op": "==", "args": [{"op": "fst", "args": [a]},
                                           {"op": "fst", "args": [b]}]}
            snd_eq = {"op": "==", "args": [{"op": "snd", "args": [a]},
                                           {"op": "snd", "args": [b]}]}
            fc = cexpr(fst_eq, env, funs, task_name, _div_style)
            sc = cexpr(snd_eq, env, funs, task_name, _div_style)
            eq = f"({fc} & {sc})"
            return eq if op == "==" else f"(!{eq})"
    if op in ARITH or op in CMP:
        o = ARITH.get(op) or CMP[op]
        return (f"({cexpr(args[0], env, funs, task_name, _div_style)} {o} "
                f"{cexpr(args[1], env, funs, task_name, _div_style)})")
    raise ValueError(f"t has no operator {op!r}")


def _divmod_ternary_cexpr(e: dict, env: dict, funs: dict,
                          task_name: str) -> str:
    """`cexpr()` with `_div_style="ternary"`, kept for exactly one use: the
    "dm" bridging assert (see `at_asserts` below), which sits inside an
    ACSL annotation, not executable C. Measured 2026-09-09: a `?:` inside
    `/*@ assert ... */` is never a WP smoke target (the doomed goals on
    fz_p_ret_bothbranches and the extra_mod lifted task both named the
    bare C statement's line, never the assert's own line, for the
    identical ternary shape), so there is no reason to also make this one
    branch-free, and every reason not to: staying ternary at EVERY
    nesting level (not only the top one) keeps this ACSL-legal (a `\\prop`
    like `x % y < 0` cannot be multiplied into an `integer`, which is
    exactly how isArmstrong's nested `t_mod(t_div(n, 10), 10)` bridging
    assert failed to parse before `_div_style` started threading through
    every recursive `cexpr` call) and syntactically parallel to
    T_DIVMOD_ACSL's own definition, which is what keeps the bridging
    equality a near-syntactic unfold rather than a fresh arithmetic
    proof. The default `cexpr(..., _div_style="bf")` (used everywhere
    else, including for any executable-position operand of a call whose
    surrounding context is this ternary form) is the branch-free one;
    this helper must never be used for code that becomes part of an
    executable C statement."""
    return cexpr(e, env, funs, task_name, _div_style="ternary")


def code_ats(e: dict, env: dict, guard: tuple = ()) -> list:
    """Definedness obligations for every `at`, `div` and `mod` in an
    executable expression, as tagged tuples: `("at", seq, index-expr,
    guard)`, `("nz", divisor-expr, guard)`, or `("dm", div-or-mod-node,
    guard)`. `guard` is the tuple of Expr conditions (each already TRUE at
    this point of the walk) that C's own short-circuit evaluation puts
    between the top of the statement and this occurrence; empty means
    "unconditionally reached" (evaluated no matter what the statement's
    own guards decide), exactly the `uncond=True` case this parameter
    replaces.

    GUARDED DEFINEDNESS, 2026-09-11 (ROADMAP 13.4, framac-seq3, item 1).
    Before this pass, a conditionally evaluated occurrence (`guard`
    non-empty) was REFUSED outright (`fz_p_nest_cell`/`fz_p_nest_lit`'s
    own measured message, "definedness not dischargeable by a plain
    assert"): emitting an unconditional assert in front of the whole
    statement would be UNSOUND (it would demand the bound hold even on
    the branch where the operator is never evaluated, e.g. `at(m, i)` at
    `i` out of range on the branch that never reads it) and there was no
    conditional form to fall back on. The fix threads the accumulated
    guard down through every `and`/`or`/`implies`/`ite` node -- the
    SAME set of C short-circuit operators `defs()` (the ACSL predicate
    side, its own docstring above unchanged) already threads a matching
    guard through -- and lets `at`/`div`/`mod` attach whatever guard is
    live at the point they are reached instead of raising. `at_asserts`
    (below) renders an empty guard exactly as before (byte-identical:
    every existing unconditional occurrence, on every committed task and
    prior probe, still reaches guard `()`) and a non-empty one as an
    ACSL implication, `(guard) ==> (bound)`, discharged only on the path
    where the operator is actually evaluated.

    "dm", added 2026-09-08 alongside `return`: MEASURED on is_prime, whose
    `return` sits behind `if (n % d == 0)`. WP proves `t_mod(n,d) == 0` as
    a hypothesis instantly when it is stated as a logic call (probe:
    `requires t_mod(n,d)==0` discharges the postcondition's existential in
    under 20ms), but times out (20000 steps, 60s wall) when the only
    hypothesis is the raw inlined C ternary `cexpr` renders for `mod`
    (same value, unfolds to the same formula by `t_mod`'s own definition,
    measured equal in isolation in under 15ms): the postcondition's
    `\\exists`/negated-`\\forall` needs a GROUND `t_mod(n, d)` term to
    match its trigger and instantiate `d`, and the raw ternary alone never
    puts that logic-shaped term anywhere in scope. So a `div`/`mod` node
    now also gets a value-bridging assert, `(raw expr) == (logic call)`,
    giving WP the exact term its own quantifiers need without changing
    what is proved, only what is available to prove it with."""
    out = []
    if "ite" in e:
        i = e["ite"]
        out += code_ats(i["cond"], env, guard)
        out += code_ats(i["then"], env, guard + (i["cond"],))
        out += code_ats(i["else"], env,
                        guard + ({"op": "not", "args": [i["cond"]]},))
        return out
    if "call" in e:
        for a in e["call"]["args"]:
            out += code_ats(a, env, guard)
        return out
    if "op" not in e:
        return out
    op, args = e["op"], e.get("args", [])
    if op == "at":
        out += code_ats(args[1], env, guard)
        base = args[0]
        if "var" in base:
            out.append(("at", seq_var(base, env), args[1], guard))
        elif base.get("op") == "seq":
            # SEQ VALUE, executable position, item 1 (literal),
            # 2026-09-11 (framac-seq): a literal base's own bound is its
            # element count, a plain int, never a `{name}_n` identifier
            # (see `cexpr`'s matching `at`/`op == "seq"` case, which this
            # tag's own bounds-check assert must agree with).
            out.append(("atn", len(base.get("args", ())), args[1], guard))
        elif (base.get("op") == "at"
              and is_nested_seq_type(typ(base["args"][0], env, None))):
            # SEQ VALUE, executable position, item 4 (nested), 2026-09-11
            # (framac-seq): `at(at(m, i), j)`'s bounds check is against
            # ROW i's length, `m_off[i + 1] - m_off[i]` (THE ENCODING),
            # not a `{name}_n` identifier either (see `cexpr`'s matching
            # case).
            m, i_e = base["args"]
            out.append(("atrow", seq_var(m, env), i_e, args[1], guard))
        else:
            out.append(("at", seq_var(base, env), args[1], guard))
        return out
    if op in DIVMOD:
        out += code_ats(args[0], env, guard)
        out += code_ats(args[1], env, guard)
        out.append(("nz", args[1], guard))
        out.append(("dm", e, guard))
        return out
    if op in ("and", "or"):
        out += code_ats(args[0], env, guard)
        seen = [args[0]]
        for a in args[1:]:
            if op == "and":
                g2 = guard + tuple(seen)
            else:
                g2 = guard + tuple({"op": "not", "args": [x]} for x in seen)
            out += code_ats(a, env, g2)
            seen.append(a)
        return out
    if op == "implies":
        out += code_ats(args[0], env, guard)
        out += code_ats(args[1], env, guard + (args[0],))
        return out
    for a in args:
        out += code_ats(a, env, guard)
    return out


def at_asserts(e: dict, ctx: Ctx, indent: str, funs=None,
               task_name: str | None = None) -> list:
    """`funs`/`task_name` are given by callers that emit real, branching C
    (stmts()): they let the "dm" tag add the raw/logic bridging assert
    (see code_ats). The certificate replay (_cert_stmts) calls this
    without them, deliberately: its own `_cert_cexpr` already resolves
    every div/mod to a branch-free ground form, and rendering one through
    plain `cexpr` here would put a live ternary back into the certificate,
    exactly the dead-code-smoke hazard `_cert_cexpr`'s docstring measured
    and fixed."""
    out = []
    for tag, *rest in code_ats(e, ctx.env):
        *rest, guard = rest
        body = None
        if tag == "at":
            s, ix = rest
            body = (f"0 <= ({term(ix, ctx)}) "
                    f"&& ({term(ix, ctx)}) < {s}_n")
        elif tag == "atn":
            # SEQ VALUE, executable position, item 1 (literal), 2026-09-11
            # (framac-seq): a literal base's bound is its own element
            # count `n`, a plain int (`code_ats`'s matching `"atn"` case).
            n, ix = rest
            body = (f"0 <= ({term(ix, ctx)}) "
                    f"&& ({term(ix, ctx)}) < {n}")
        elif tag == "atrow":
            # SEQ VALUE, executable position, item 4 (nested), 2026-09-11
            # (framac-seq): a nested cell's bound is its own row's length,
            # `m_off[i + 1] - m_off[i]` (`code_ats`'s matching `"atrow"`
            # case).
            m, i_e, ix = rest
            i_c = term(i_e, ctx)
            body = (f"0 <= ({term(ix, ctx)}) "
                    f"&& ({term(ix, ctx)}) < "
                    f"({m}_off[({i_c}) + 1] - {m}_off[({i_c})])")
        elif tag == "nz":
            (yx,) = rest
            body = f"({term(yx, ctx)}) != 0"
        else:                                      # "dm": bridging assert
            (node,) = rest
            if funs is not None and task_name is not None:
                # `_divmod_ternary_cexpr`, not `cexpr`: this text lands
                # inside an ACSL annotation, where the branch-free form
                # `cexpr` now renders for executable position is not even
                # legal ACSL (a `\prop` cannot multiply an `integer`), and
                # the ternary form is not smoke-tested here regardless
                # (see `_divmod_ternary_cexpr`'s docstring).
                body = (f"({_divmod_ternary_cexpr(node, ctx.env, funs, task_name)}) == "
                       f"({term(node, ctx)})")
        if body is None:
            continue
        if not guard:
            out.append(f"{indent}/*@ assert {body}; */")
        else:
            # GUARDED DEFINEDNESS, 2026-09-11 (ROADMAP 13.4, framac-seq3,
            # item 1): `code_ats`'s own docstring above. `guard` is a
            # tuple of Expr conditions, each already established true by
            # the enclosing `if`/`and`/`or`/`implies` structure at the
            # point this occurrence is reached; renders each through
            # `pred()` (the ACSL predicate side, so a bool-typed C guard
            # gets the `!= 0` convention `pred`'s own `var` case already
            # applies) and states the bound only as a consequence, never
            # unconditionally.
            cond = " && ".join(f"({pred(g, ctx)})" for g in guard)
            out.append(f"{indent}/*@ assert ({cond}) ==> ({body}); */")
    return out


# --------------------------------------------------- seq value machinery ----
#
# THE ENCODING (2026-09-09, SPEC.md "Sequences as values"). C has no
# sequence value at all, so every column measures its own answer to what a
# `seq` local/return IS in C; this one is measured on the two committed
# tasks below (`swap`'s `update`, `reverse`'s `fill` + loop `update`) with
# a hand-written probe verified by frama-c/WP BEFORE this code was written
# (RULES: measure first). A seq PARAM was already `int *s, int s_n`
# (read-only, `\valid_read`); a seq RETURN gets the SAME pair appended to
# the C signature as an OUTPUT parameter (`int *r, int r_n`), caller
# writable (`\valid`), separated from every other seq buffer
# (`\separated`), and its length pinned by a `requires {r}_n ==
# <len-expr>;` where <len-expr> is the return's length computed
# STATICALLY from the body (`_seq_len_track`, below) and rendered in
# PARAMS-only terms (ACSL `requires` has no locals in scope). This is
# candidate (B) of the three the task brief named (a caller-provided
# output buffer, not an ACSL `\list`/axiomatised logic sequence, and not a
# ghost-only encoding): every `s[i := v]`/`seq(n, v)` becomes a REAL
# memory store into that buffer, proven by WP's own points-to reasoning
# over ordinary C writes, nothing bespoke.
#
# What this candidate CANNOT express, stated rather than discovered late:
# the return buffer's requires-time validity bound must be a term over
# PARAMS ALONE (ACSL's `requires` scope), so a `fill` whose length is not
# reducible, by `_seq_len_track`, to an expression over the task's own
# params (an index expression built from other LOCALS with no closed form
# in terms of params, or a length that differs across `if`/`while`
# branches) has no buffer size to request from the caller and this
# lowering refuses the task (NotImplementedError) rather than guess one.
# The measured alternative from the task brief, a `t_len_r` OUT-parameter
# the callee itself WRITES, would lift that restriction for the LENGTH
# (the callee could compute and report it), but not for the buffer's own
# VALIDITY bound, which is still owed to the caller before the call and so
# still needs an expression fixed in advance; not implemented, since
# neither committed task needs it (both `update` and `fill` here reduce to
# `len(s)`, a bare param length).
#
# A seq-typed LOCAL (`var a: seq := s;`, SPEC.md's other new position) is
# NOT implemented: it would need its own backing storage with no external
# contract to size it from (v1's own scope rule keeps locals out of
# `ensures`, so there is no requires-time bound to borrow), and neither
# committed task declares one. `stmts()`'s `var` case refuses it by name.


def _expr_seq_len(e: dict, lens: dict) -> dict | None:
    """The t Expr for the length of the seq value `e` denotes, given the
    lengths already tracked for every seq name in scope (`lens`), or None
    when `e`'s length cannot be determined this way (SPEC.md's grammar:
    a seq-typed assignment's right-hand side is a bare seq variable,
    `update`, `fill`, a `seq` literal, a `slice`, or a `+` concatenation;
    `update` preserves its base's length, `fill`'s length is its own
    first argument, a literal's length is its own element count, a
    slice's is `b - a`, a concatenation's is the sum of its two operands'
    -- each resolved recursively, so `[]  + [x]` or `s[0..k] + t`
    resolve exactly as a bare literal or slice would; a variable's length
    is whatever is already tracked for it).

    2026-09-09 (SPEC.md "Sequences: literals, concatenation, slices"):
    `seq`/`slice`/`+` added alongside the pre-existing `update`/`fill`.
    Extending `+` here is SAFE for the append idiom (`r := r + [x]`,
    self-referential, `filter_pos`'s own shape) even though it can, on a
    SINGLE static pass, resolve to a numeric value (e.g. `r`'s tracked
    length 0 plus a length-1 literal, giving 1): the append always sits
    inside a data-dependent `if`/`while` whose own branch- or
    iteration-count disagreement already drops the name from `lens`
    (`_seq_len_track`'s `if`/`while` handling, unchanged), so this
    extension never lets a genuinely unbounded append masquerade as a
    closed form; it only lets a LOOP-FREE concatenation of two
    already-resolved operands (e.g. `r := s + t`, neither self-referential
    nor inside a loop) resolve exactly, which no committed task needs but
    which costs nothing extra to support correctly."""
    if "var" in e:
        return lens.get(e["var"])
    if "op" not in e:
        return None
    op = e["op"]
    if op == "update":
        base = e["args"][0]
        return lens.get(base.get("var")) if "var" in base else None
    if op == "fill":
        return e["args"][0]
    if op == "seq":
        return {"int": len(e["args"])}
    if op == "slice":
        _, lo, hi = e["args"]
        return {"op": "-", "args": [hi, lo]}
    if op == "+":
        a_len = _expr_seq_len(e["args"][0], lens)
        b_len = _expr_seq_len(e["args"][1], lens)
        if a_len is None or b_len is None:
            return None
        return {"op": "+", "args": [a_len, b_len]}
    if op in ("lower", "upper"):
        # FRAMAC-NESTED, added 2026-09-14 (DESIGN-framac-nested-seq.md
        # section 4, "an executable lower and upper"): `lower(x)`/
        # `upper(x)` is a pointwise case-map over `x`'s own elements
        # (SPEC.md's own words, "leaves every non-letter code point
        # unchanged"), never adding or dropping an element, so its
        # length is exactly `x`'s own -- resolved recursively exactly
        # like `update`'s own base-length passthrough above, whether `x`
        # is a bare variable, a literal, a slice, or itself already
        # resolved by this same function.
        return _expr_seq_len(e["args"][0], lens)
    return None


def _seq_len_track(body: list, lens: dict) -> None:
    """Extends `lens` (seq name -> t Expr for its current length) by
    walking `body`'s seq-typed assignments in program order. `if` requires
    both branches to agree (structurally equal Exprs, or both silent) on
    every name's length, since the length feeds a `requires` clause that
    must hold on every path; `while` requires the loop body to leave every
    tracked length UNCHANGED (an update-only loop, like reverse's), since a
    length that only holds after N iterations has no single closed form
    before the call. Either mismatch drops the name from `lens` rather
    than raising: the caller (`lower()`) raises only if the RETURN's own
    length is what came up unresolved, so an untracked length elsewhere in
    the body (of no interest to any `requires`) is not an error here."""
    for s in body:
        if "assign" in s:
            name, e = s["assign"]
            new = _expr_seq_len(e, lens)
            if new is not None:
                lens[name] = new
            else:
                lens.pop(name, None)
        elif "return" in s:
            name, e = s["return"]
            new = _expr_seq_len(e, lens)
            if new is not None:
                lens[name] = new
            else:
                lens.pop(name, None)
        elif "var" in s:
            pass                       # seq locals are refused elsewhere
        elif "if" in s:
            then_lens, else_lens = dict(lens), dict(lens)
            _seq_len_track(s["if"]["then"], then_lens)
            _seq_len_track(s["if"]["else"], else_lens)
            for k in set(then_lens) | set(else_lens):
                if then_lens.get(k) == else_lens.get(k) and k in then_lens:
                    lens[k] = then_lens[k]
                else:
                    lens.pop(k, None)
        elif "while" in s:
            inner = dict(lens)
            _seq_len_track(s["while"]["body"], inner)
            for k, v in list(lens.items()):
                if inner.get(k) != v:
                    lens.pop(k, None)


def _fold_int_list(e: dict) -> list | None:
    """A plain-seq LITERAL `e` (`{"op": "seq", "args": [...]}`) as a
    Python list of ints, iff every element is itself a literal `{"int":
    v}` node; None for a variable, an op, or any non-literal element.
    FRAMAC-NESTED, added 2026-09-14 (DESIGN-framac-nested-seq.md sections
    1-3): the building block `_fold_nested_rows` (below) uses to
    constant-fold a nested seq<seq> RETURN/LOCAL's build expression at
    LOWERING TIME rather than emit runtime machinery for a shape none of
    this pass's own three named cells needs at runtime -- the same move
    `seq_assign_lines`'s own `lower`/`upper` literal fold makes for a
    flat seq."""
    if e.get("op") != "seq":
        return None
    out = []
    for a in e.get("args", ()):
        if "int" not in a:
            return None
        out.append(a["int"])
    return out


def _fold_nested_rows(e: dict) -> list | None:
    """A nested seq<seq> expression `e`'s rows as Python lists of ints,
    constant-folded at LOWERING TIME, or None when `e` is not one of the
    two shapes this pass's own named cells build: a literal nested seq
    (`[]`, the empty case `fz_p_nest_empty` needs, or, more generally, a
    literal of literal rows) or `split(s)` with `s` itself a fully
    literal plain seq (`fz_p_str_splitempty`'s own `split([])`).
    `split`'s own one-argument (whitespace) semantics are replayed
    EXACTLY through `interp._str_split_ws`, the same function
    `interp.py`'s own reference evaluator calls for the identical AST
    node, so this fold can never disagree with what running the real
    program would compute. Anything else (a seq<seq> PARAMETER variable,
    `update`, a two-argument `split(s, sep)`) returns None, `lower()`'s
    own signal to fall through to the wholesale runtime-build refusal,
    unchanged."""
    op = e.get("op")
    if op == "seq":
        rows = []
        for a in e.get("args", ()):
            r = _fold_int_list(a)
            if r is None:
                return None
            rows.append(r)
        return rows
    if op == "split" and len(e.get("args", ())) == 1:
        flat = _fold_int_list(e["args"][0])
        if flat is None:
            return None
        return [list(r) for r in interp._str_split_ws(tuple(flat))]
    return None


def _ret_nested_fold(body: list, ret: str) -> list | None:
    """Finds the single top-level `assign`/`return` to `ret` in `body`
    and constant-folds its own value via `_fold_nested_rows`, or None
    when there is not EXACTLY one such statement (a loop or an `if`
    writing `ret` on different paths is out of this pass's own scope,
    named by `lower()`'s own wholesale refusal, not guessed at) or that
    one statement's value does not fold. Scoped to this pass's own two
    named RETURN cells (`fz_p_nest_empty`, `fz_p_str_splitempty`), both
    single-statement bodies -- `lower()` skips calling `stmts()` on
    `body` entirely for a folded nested return (there is nothing left to
    lower once the whole function is one constant-folded assignment), so
    `body` is required to be EXACTLY that one statement, not merely to
    contain it, or this returns None and `lower()` falls through to the
    wholesale runtime-build refusal rather than silently dropping any
    OTHER statement a longer body might have. `swap_rows`'s own multi-
    statement BUILDING shape never matches (its `update` calls are not
    `_fold_nested_rows` shapes to begin with, len(body) > 1 besides) and
    falls through regardless."""
    if len(body) != 1:
        return None
    s = body[0]
    if "assign" in s and s["assign"][0] == ret:
        e = s["assign"][1]
    elif "return" in s and s["return"][0] == ret:
        e = s["return"][1]
    else:
        return None
    return _fold_nested_rows(e)


def _ret_capacity(task: dict, ret: str) -> dict | None:
    """CAPACITY, 2026-09-09 (the append idiom, `r := r + [x]`). When a seq
    RETURN's exact length has no closed form over the params
    (`_seq_len_track` above failed to resolve it, `filter_pos`'s own
    shape: a while loop appends conditionally, so no single static length
    survives the loop's own before/after check), the return buffer still
    needs SOME `requires`-time bound to size its `\\valid`/`\\separated`
    obligations from -- not the true final length (data-dependent, known
    only at runtime), but a CAPACITY the true length never exceeds. This
    is exactly what the task's own `ensures` already states, because the
    whole point of stating `len(r) <= len(s)` (or `== `) is to bound the
    result: the first `ensures` of the shape `len(ret) <= E` or `len(ret)
    == E` gives E, read directly off the task rather than re-derived,
    since the task author already proved (informally) that E bounds the
    append loop's own iteration count. None when no such ensures exists,
    the caller's (`lower()`'s) signal to abstain rather than guess a
    buffer size."""
    def is_len_ret(e):
        return (isinstance(e, dict) and e.get("op") == "len"
                and e.get("args", [{}])[0].get("var") == ret)
    for e in task.get("ensures", []):
        if e.get("op") in ("<=", "==") and "args" in e:
            a, b = e["args"]
            if is_len_ret(a):
                return b
    return None


def seq_assign_lines(target: str, e: dict, ctx: Ctx, indent: str,
                     funs: dict, task_name: str) -> list:
    """C statements implementing `target := e`, `target` a seq-typed name,
    `e` a bare seq variable (a full copy), `update`, `fill`, a `seq`
    literal, a `slice`, or `+` (concatenation, added 2026-09-09). Every one
    of these writes `target`'s buffer through real memory stores:
    `update`'s base operand, when it names a DIFFERENT buffer than
    `target` (swap's `r := s[i := ...]`, its first write to `r`), is
    copied in first, a whole-buffer loop with invariant `target[t] ==
    base[t]` for `t` below the loop counter, exactly SPEC.md's "equal to
    `s` at every index but `i`"; a SELF update (`r := r[j := tmp]`,
    swap's second write, and reverse's per-iteration `r := r[i := ...]`)
    skips the copy, since `target` already holds exactly what `base`
    denotes. `fill` never reads a prior value, so the whole buffer is
    written by one loop, no copy. Measured 2026-09-09 by hand (frama-c/WP)
    on both tasks in exactly this shape before this function was written
    (RULES: measure first).

    `seq`/`slice`/`+`, added the same night for SPEC.md "Sequences:
    literals, concatenation, slices": a literal is `len(args)` individual
    stores (0 for `[]`); a slice is a copy loop reading `src[a + __t]`
    instead of `src[__t]`, the buffer's length pinned exactly as today
    from the ensures (`tail`'s shape, EXACT mode, `ctx.seq_len` empty for
    `target`); `+` is the append idiom, `r := r + [...]` (or, more
    generally, `r := r + t` for a bare seq `t`) -- CAPACITY mode only
    (`target in ctx.seq_len`, see the seq value machinery section's
    CAPACITY discussion and `_ret_capacity`), self-referential on the
    left by construction (only `filter_pos`'s own shape is measured; a
    non-self-referential `+`, e.g. a fresh `r := s + t` neither operand
    being `target`, is not implemented, since no committed task needs
    it). `ctx.seq_len[target]` names the LOCAL tracking the buffer's
    CURRENT logical length (`r_len`); an append emits the SPEC's own
    obligation, `r_len + <appended count> <= r_n`, before writing, and
    advances `r_len` by that count afterward -- `r[r_len] = x; r_len =
    r_len + 1;` for the measured singleton-literal shape."""
    out = []
    xn = f"{target}_n"
    cap = ctx.seq_len.get(target)          # the length-local, CAPACITY mode

    def _copy_loop(src: str, off: str | None = None,
                   bound: str | None = None) -> list:
        idx_t = f"({off}) + __t" if off is not None else "__t"
        idx_k = f"({off}) + __k" if off is not None else "__k"
        n = bound if bound is not None else xn
        return [
            f"{indent}/*@",
            f"{indent}  loop invariant 0 <= __k <= {n};",
            f"{indent}  loop invariant \\forall integer __t; "
            f"0 <= __t < __k ==> {target}[__t] == {src}[{idx_t}];",
            f"{indent}  loop assigns __k, {target}[0 .. {xn} - 1];",
            f"{indent}  loop variant {n} - __k;",
            f"{indent}*/",
            f"{indent}for (int __k = 0; __k < {n}; __k++) "
            f"{target}[__k] = {src}[{idx_k}];",
        ]

    if "var" in e:
        # CAPACITY-MODE BARE-SEQ ASSIGN BUG (2026-09-12, ROADMAP 16.2,
        # appendArrayToSeq's `r := s;` before its own append loop): under
        # EXACT mode (`cap is None`) `target`'s own declared size `xn`
        # already equals the assigned value's length by construction (no
        # committed task before this one paired a bare-seq assign with a
        # LATER capacity-tracked append into the same buffer), so using
        # `xn` as the copy bound and as the fresh length value was
        # correct there. Under CAPACITY mode `xn` is the buffer's full
        # PHYSICAL capacity (`r_n == s_n + a_n` here), not `src`'s own
        # logical length -- copying `xn` elements out of `src` reads past
        # `src`'s own `\valid_read` range whenever `src` is shorter than
        # the buffer, and setting the length-local to `xn` afterward lies
        # about how much of the buffer actually holds `src`'s data,
        # exactly the state `appendArrayToSeq`'s loop invariant `len(r)
        # == len(s) + i_v2` needs true at `i_v2 == 0` and could not get.
        # Fixed: the copy bound and the length-local's new value are both
        # `src`'s own logical length (`ctx.seq_len` if `src` is itself
        # capacity-tracked, else its plain `{src}_n`) whenever this
        # assign is capacity-tracked; EXACT mode is untouched (`bound`
        # stays `None`, `_copy_loop` falls back to `xn` exactly as
        # before, so every already-committed EXACT-mode task's C is
        # byte-identical).
        src = seq_var(e, ctx.env)
        src_len = ctx.seq_len.get(src, f"{src}_n")
        out += _copy_loop(src, bound=(src_len if cap is not None else None))
        if cap is not None:
            out.append(f"{indent}{cap} = {src_len};")
        return out
    op, args = e["op"], e["args"]
    if op == "update":
        src = seq_var(args[0], ctx.env)
        out += at_asserts(args[1], ctx, indent, funs, task_name)
        out += at_asserts(args[2], ctx, indent, funs, task_name)
        ic = cexpr(args[1], ctx.env, funs, task_name)
        out.append(f"{indent}/*@ assert 0 <= ({ic}) && ({ic}) < {src}_n; */")
        if src != target:
            out += _copy_loop(src)
        vc = cexpr(args[2], ctx.env, funs, task_name)
        out.append(f"{indent}{target}[{ic}] = {vc};")
        return out
    if op == "fill":
        out += at_asserts(args[0], ctx, indent, funs, task_name)
        out += at_asserts(args[1], ctx, indent, funs, task_name)
        nc = cexpr(args[0], ctx.env, funs, task_name)
        out.append(f"{indent}/*@ assert ({nc}) >= 0; */")
        vc = cexpr(args[1], ctx.env, funs, task_name)
        out += [
            f"{indent}/*@",
            f"{indent}  loop invariant 0 <= __k <= {xn};",
            f"{indent}  loop invariant \\forall integer __t; "
            f"0 <= __t < __k ==> {target}[__t] == ({vc});",
            f"{indent}  loop assigns __k, {target}[0 .. {xn} - 1];",
            f"{indent}  loop variant {xn} - __k;",
            f"{indent}*/",
            f"{indent}for (int __k = 0; __k < {xn}; __k++) "
            f"{target}[__k] = {vc};",
        ]
        return out
    if op == "slice":
        # `r := s[a..b]` into the OUTPUT buffer (2026-09-09, `tail`'s own
        # shape): a copy loop reading `src[a + __t]`, the buffer's length
        # pinned exactly as today from the ensures (`_expr_seq_len`'s new
        # `slice` case gives `b - a`, EXACT mode). CAPACITY mode is not
        # exercised by any committed task (a slice assigned into a
        # counted return) but is handled the same way `var`'s copy is,
        # above: whatever the buffer's current length local tracks, a
        # full replacement sets it to the number of elements this loop
        # actually wrote, `xn`.
        s_e, lo, hi = args
        out += at_asserts(lo, ctx, indent, funs, task_name)
        out += at_asserts(hi, ctx, indent, funs, task_name)
        src = seq_var(s_e, ctx.env)
        lo_c = cexpr(lo, ctx.env, funs, task_name)
        hi_c = cexpr(hi, ctx.env, funs, task_name)
        out.append(f"{indent}/*@ assert 0 <= ({lo_c}) && ({lo_c}) <= "
                   f"({hi_c}) && ({hi_c}) <= {src}_n; */")
        out += _copy_loop(src, off=lo_c)
        if cap is not None:
            out.append(f"{indent}{cap} = {xn};")
        return out
    if op == "+":
        # `r := r + [...]` (2026-09-09, the append idiom, `filter_pos`'s
        # own shape) or, more generally, `r := r + t` for a bare seq `t`:
        # CAPACITY mode only, self-referential on the left. See this
        # function's own docstring for what is and is not measured here.
        #
        # SEQ VALUE, executable position, item 1 (literal), 2026-09-11
        # (framac-seq): `[] + e` is `e` by SPEC.md's own concatenation
        # identity (len([]) == 0, so every index of the result shifts by
        # nothing) -- a FULL REPLACEMENT of `target`, not an append, so it
        # is handled BEFORE the CAPACITY-only restriction below rather
        # than falling into it: whether `target` is EXACT- or CAPACITY-
        # tracked, `[] + e` writes exactly `e`'s own elements, the same
        # copy this function's own `"var" in e` branch (above) already
        # emits for a bare `target := e`. Only the LEFT operand being the
        # empty literal is recognized (`e + []`, the identity's mirror, is
        # not measured by any committed probe or task, so it is left
        # alone rather than guessed at).
        left0 = args[0]
        if left0.get("op") == "seq" and not left0.get("args"):
            return seq_assign_lines(target, args[1], ctx, indent, funs,
                                    task_name)
        if cap is None:
            raise NotImplementedError(
                "seq concatenation assigned to an EXACT-length return "
                "(its length already pinned by `requires` from "
                "`_seq_len_track`) is not implemented by this lowering; "
                "only the append idiom into a CAPACITY-tracked buffer "
                "(`_ret_capacity`) is measured")
        left, right = args
        if not ("var" in left and left["var"] == target):
            raise NotImplementedError(
                "seq concatenation whose left operand is not the "
                "assignment's own target is not implemented by this "
                "lowering; only the append idiom `r := r + ...` is "
                "measured")
        if "var" in right:
            src = seq_var(right, ctx.env)
            cnt = f"{src}_n"
            out.append(f"{indent}/*@ assert ({cap}) + ({cnt}) <= "
                       f"{xn}; */")
            out += [
                f"{indent}/*@",
                f"{indent}  loop invariant 0 <= __k <= {cnt};",
                f"{indent}  loop invariant \\forall integer __t; "
                f"0 <= __t < __k ==> "
                f"{target}[({cap}) + __t] == {src}[__t];",
                f"{indent}  loop assigns __k, "
                f"{target}[({cap}) .. {xn} - 1];",
                f"{indent}  loop variant {cnt} - __k;",
                f"{indent}*/",
                f"{indent}for (int __k = 0; __k < {cnt}; __k++) "
                f"{target}[({cap}) + __k] = {src}[__k];",
            ]
            out.append(f"{indent}{cap} = ({cap}) + ({cnt});")
            return out
        if right.get("op") == "seq":
            for a in right["args"]:
                out += at_asserts(a, ctx, indent, funs, task_name)
            n = len(right["args"])
            out.append(f"{indent}/*@ assert ({cap}) + {n} <= {xn}; */")
            for k, a in enumerate(right["args"]):
                vc = cexpr(a, ctx.env, funs, task_name)
                out.append(f"{indent}{target}[({cap}) + {k}] = {vc};")
            out.append(f"{indent}{cap} = ({cap}) + {n};")
            return out
        raise NotImplementedError(
            f"append source {right!r}: only a bare seq variable or a "
            f"`seq` literal is implemented as the right operand of `+` "
            f"by this lowering")
    if op == "seq":
        # `[e1, ..., en]` (2026-09-09): n individual stores, 0 for `[]`.
        # A FULL REPLACEMENT of `target`'s value (never additive; the
        # append idiom is expressed through `+`, above), so a
        # CAPACITY-tracked target's length local is set to n directly,
        # not advanced.
        for a in args:
            out += at_asserts(a, ctx, indent, funs, task_name)
        n = len(args)
        if cap is not None:
            out.append(f"{indent}/*@ assert {n} <= {xn}; */")
        for k, a in enumerate(args):
            vc = cexpr(a, ctx.env, funs, task_name)
            out.append(f"{indent}{target}[{k}] = {vc};")
        if cap is not None:
            out.append(f"{indent}{cap} = {n};")
        return out
    if op in ("lower", "upper"):
        # FRAMAC-NESTED, added 2026-09-14 (DESIGN-framac-nested-seq.md
        # section 4, "an executable lower and upper"). `r := lower(x)`/
        # `r := upper(x)`: an output the SAME length as `x` (this
        # function's own caller, `lower()`, resolved that length via
        # `_expr_seq_len`'s new `lower`/`upper` case, EXACT mode, no new
        # CAPACITY bound), one loop mapping each cell through the same
        # ternary T_CASE_ACSL states, invariant `target[t] ==
        # t_lower_c(src[t])` (or `t_upper_c`) for `t` below the counter.
        #
        # Two source shapes, both measured: `fz_p_str_lowernonletter`'s
        # own probe body is `r := lower([32, 64, 91, 96, 123, 1000000])`,
        # a fully LITERAL argument with no backing buffer at all (no
        # `{v}_n`/`{v}` pair for a copy loop to read from) -- folded at
        # LOWERING TIME instead: the case map is applied to each literal
        # element in Python (both sides see the identical constant, C's
        # `int` and ACSL's `integer` agreeing on every value in this
        # file's own arithmetic, see THE SEMANTIC LINE above), then
        # re-dispatched through the `"seq"` literal case just above,
        # which is already measured and needs no new mechanism. A bare
        # seq VARIABLE argument (the general case the design order names
        # for a real string-lib caller) gets the real copy loop, reading
        # `src[__k]` and writing `target[__k]` through the executable
        # mirror of T_CASE_ACSL's own ternary.
        src_e = args[0]
        if src_e.get("op") == "seq" and all("int" in a for a in
                                            src_e.get("args", ())):
            def _map1(v: int) -> int:
                if op == "lower":
                    return v + 32 if 65 <= v <= 90 else v
                return v - 32 if 97 <= v <= 122 else v
            mapped = {"op": "seq",
                     "args": [{"int": _map1(a["int"])}
                              for a in src_e["args"]]}
            return seq_assign_lines(target, mapped, ctx, indent, funs,
                                    task_name)
        if "var" not in src_e:
            raise NotImplementedError(
                f"string library member `{op}` reaching the seq-"
                f"assignment machinery with source {src_e!r}: only a "
                f"bare seq variable or a fully-literal seq argument is "
                f"lowered")
        src = seq_var(src_e, ctx.env)
        cmap = (f"(65 <= ({src}[__k]) && ({src}[__k]) <= 90) ? "
               f"({src}[__k]) + 32 : ({src}[__k])") if op == "lower" else (
               f"(97 <= ({src}[__k]) && ({src}[__k]) <= 122) ? "
               f"({src}[__k]) - 32 : ({src}[__k])")
        fn = "t_lower_c" if op == "lower" else "t_upper_c"
        out += [
            f"{indent}/*@",
            f"{indent}  loop invariant 0 <= __k <= {src}_n;",
            f"{indent}  loop invariant \\forall integer __t; "
            f"0 <= __t < __k ==> {target}[__t] == {fn}({src}[__t]);",
            f"{indent}  loop assigns __k, {target}[0 .. {xn} - 1];",
            f"{indent}  loop variant {src}_n - __k;",
            f"{indent}*/",
            f"{indent}for (int __k = 0; __k < {src}_n; __k++) "
            f"{target}[__k] = {cmap};",
        ]
        if cap is not None:
            out.append(f"{indent}{cap} = {src}_n;")
        return out
    raise NotImplementedError(
        f"seq-typed assignment from operator {op!r}: v1's grammar only "
        f"assigns a bare seq variable, `update`, `fill`, `seq`, `slice`, "
        f"`lower`, `upper`, or `+` to a seq-typed name")


def assigned_names(body: list, seq_caps: dict | None = None
                   ) -> tuple[list, list]:
    """(assign targets, locals declared) in order, recursively. `seq_caps`
    (2026-09-09, `ctx.seq_len`: return-name -> its length-tracking local)
    makes an assignment to a CAPACITY-tracked seq return also count as an
    assignment to that local, so the loop that assigns it (`filter_pos`'s
    own shape) correctly frames both in its `loop assigns` (see `stmts()`'s
    `while` case, the only caller of this function): the local is real C
    state the loop writes (`r_len = r_len + 1;`), just as `r`'s own
    buffer is, and WP's frame check fails on an unlisted write exactly as
    it would for any other omitted name."""
    seq_caps = seq_caps or {}
    hit, dec = [], []
    for s in body:
        if "assign" in s:
            n = s["assign"][0]
            hit.append(n)
            if n in seq_caps:
                hit.append(seq_caps[n])
        elif "return" in s:
            n = s["return"][0]
            hit.append(n)
            if n in seq_caps:
                hit.append(seq_caps[n])
        elif "var" in s:
            dec.append(s["var"]["name"])
        elif "if" in s:
            for br in (s["if"]["then"], s["if"]["else"]):
                h, d = assigned_names(br, seq_caps)
                hit += h
                dec += d
        elif "while" in s:
            h, d = assigned_names(s["while"]["body"], seq_caps)
            hit += h
            dec += d
    return hit, dec


def _ret_written_in_loop(body: list, ret: str) -> bool:
    """True iff `ret` is an assignment target somewhere inside a `while`
    loop of `body` (nested inside an `if` is fine: `assigned_names`
    already recurses through those, and so does the `if`-branch above).
    THE TRACKED-LENGTH ENCODING (2026-09-10, second pass) uses this to
    pick out the fill/self-update shape the design question named: a seq
    return whose EXACT-mode length (`ret in lens`, `_seq_len_track`) is a
    closed form over params, but which a loop actually mutates in place,
    as opposed to a loop-free EXACT shape like `tail`'s slice (no while
    loop touches the return at all, so this is False there and the
    ORIGINAL plain-EXACT rendering, `{ret}_n` bare, is unaffected)."""
    for s in body:
        if "while" in s:
            hit, _ = assigned_names(s["while"]["body"])
            if ret in hit or _ret_written_in_loop(s["while"]["body"], ret):
                return True
        elif "if" in s:
            if (_ret_written_in_loop(s["if"]["then"], ret)
                    or _ret_written_in_loop(s["if"]["else"], ret)):
                return True
    return False


def _assigns_target(n: str, ctx: Ctx) -> str:
    """One name's own `loop assigns`/entry, a bare name for int/bool, the
    whole element range for a seq (its POINTER never changes, only what it
    points to; naming the bare pointer here would claim WP need not track
    that the pointee changes at all, which is false for every task that
    mutates a seq inside a loop, `reverse` included)."""
    return f"{n}[0 .. {n}_n - 1]" if ctx.env.get(n) == "seq" else n


# -------------------------------------------- seq extensional equality -----
#
# FRAMAC-NESTED, ROADMAP 13.4 item (a), 2026-09-12 (the design order's
# design note above `lower_framac`'s own docstring names the three cells:
# fz_p_nest_eq, 576 isSublist, 69 containsSequence). `cexpr`'s own
# `==`/`!=` case (SEQ VALUE, executable position, item 4) already refuses
# a bare seq-typed `==`/`!=` reaching EXECUTABLE position by name, because
# a single C VALUE expression cannot render an extensional (`\forall`
# -shaped) comparison and a bare pointer `==` would be a silently WRONG
# substitute (C pointer identity, not SPEC's elementwise equality). This
# section gives `stmts()` a STATEMENT-shaped alternative: a C loop with
# its own ACSL loop invariant, computing the comparison into a fresh
# bool-int temp `stmts()` can then use exactly where `cexpr()`'s return
# value would have gone (an `if` condition, an assign/return
# right-hand-side) -- never an edit to `cexpr` itself, since `cexpr` has
# no way to emit a preceding statement from inside its own return.
_SEQ_EQ_CTR = [0]


def _seq_eq_operand_c(e: dict, ctx: Ctx, funs: dict, task_name: str):
    """(pointer-expr, length-expr, domain-assert-list) for a flat
    ("seq"-typed) EXECUTABLE-position read operand of the equality loop
    below. Three shapes, the ones this pass's own three named cells
    actually need, each MEASURED against the real lifted task JSON before
    being written (isSublist's `main_v[i_v .. i_v+len(sub)]`,
    containsSequence's `at(list, i_v)` where `list` is a seq<seq>
    parameter): a bare seq variable (`{v}_n` elements at `{v}` itself,
    already `\\valid_read` by that parameter's own `requires`); a slice of
    one (`{base} + lo` .. `hi - lo` elements, its own domain obligation
    `0 <= lo <= hi <= len(base)` returned as asserts since no `at`
    wraps it here for `code_ats`/`at_asserts` to pick up); or a ROW of a
    nested seq<seq> PARAMETER (`at(m, i)`, THE ENCODING's own
    `{m}_data + {m}_off[i]` .. `{m}_off[i+1] - {m}_off[i]` elements, its
    own domain obligation `0 <= i < len(m)`). Anything else (a seq
    literal or a `+` concatenation operand) is a named NotImplementedError,
    not guessed at: none of this pass's own three cells needs one, and
    guessing a rendering un-measured against a real task is exactly what
    RULES forbids."""
    if "var" in e:
        v = seq_var(e, ctx.env)
        return v, f"{v}_n", []
    op = e.get("op")
    if op == "slice":
        base, lo, hi = e["args"]
        if "var" not in base:
            raise NotImplementedError(
                "seq extensional equality loop: a slice operand's own "
                "base is not a bare seq variable, out of this pass's own "
                "scope (fz_p_nest_eq/isSublist/containsSequence, the "
                "only three cells measured)")
        bv = seq_var(base, ctx.env)
        lo_c = cexpr(lo, ctx.env, funs, task_name)
        hi_c = cexpr(hi, ctx.env, funs, task_name)
        dom = [f"0 <= ({lo_c})", f"({lo_c}) <= ({hi_c})",
               f"({hi_c}) <= {bv}_n"]
        return f"({bv} + ({lo_c}))", f"(({hi_c}) - ({lo_c}))", dom
    if op == "at":
        base, idx = e["args"]
        if "var" in base and is_nested_seq_type(ctx.env.get(base["var"])):
            nv = seq_var(base, ctx.env)
            idx_c = cexpr(idx, ctx.env, funs, task_name)
            dom = [f"0 <= ({idx_c})", f"({idx_c}) < {nv}_n"]
            return (f"({nv}_data + {nv}_off[{idx_c}])",
                    f"({nv}_off[({idx_c}) + 1] - {nv}_off[{idx_c}])", dom)
    raise NotImplementedError(
        "seq extensional equality loop: only a bare seq variable, a "
        "slice of one, or a row of a nested seq<seq> PARAMETER has an "
        "executable-position pointer/length by this pass; a seq literal "
        "or `+` concatenation operand is a named remaining gap")


def _seq_eq_top(e: dict, ctx: Ctx) -> bool:
    """True iff `e` is a top-level `==`/`!=` between two seq-typed (flat
    or nested seq<seq>) operands -- the one shape `_seq_eq_loop` renders,
    distinguished from every other `==`/`!=` (int, bool, pair) `cexpr`
    already renders as a plain C value with no loop needed."""
    if e.get("op") not in ("==", "!="):
        return False
    t0 = typ(e["args"][0], ctx.env, ctx.funs)
    return t0 == "seq" or is_nested_seq_type(t0)


def _seq_eq_loop(e: dict, ctx: Ctx, indent: str, funs: dict, task_name: str):
    """Renders `e` (`_seq_eq_top(e, ctx)` already true) as a C loop with
    its own ACSL loop invariant computing the extensional comparison into
    a fresh bool-int temp, returning `(statement-lines, c-value-expr)`
    where `c-value-expr` is what `stmts()` substitutes at the call site
    (an `if` condition, an assign/return right-hand side) in place of the
    single value `cexpr` cannot produce. `!=` negates the temp at the
    call site (`!{tmp}`), never inside this function, so the loop itself
    and its invariant always state the positive (`==`) fact, one shape to
    get right rather than two.

    NESTED (fz_p_nest_eq's own `r := (m == n)`, both bare seq<seq>
    PARAMETER variables -- a computed nested value is a fresh, unrelated
    gap this pass does not attempt, matching `_seq_eq_operand_c`'s own
    named scope): an outer loop over row index `i`, each iteration first
    comparing the two rows' lengths (THE ENCODING's own offsets
    difference) and then, only if those agree, an INNER loop comparing
    every cell of that one row -- two real C loops, each with its own WP
    invariant, rather than a nested `\\forall` inside a single loop
    invariant (WP proves a loop's OWN invariant only across that loop's
    own iterations; a nested `\\forall` over an inner range that a single
    outer loop-invariant states as already fully checked is exactly the
    shape the outer loop's `loop invariant` conjunct below asks WP to
    carry forward, unchanged by the inner loop's own local `i2`/`__cell`
    names, which never escape their own block).

    FLAT (isSublist's `sub == main_v[i..i+len(sub)]`, containsSequence's
    `sub == at(list, i_v)`): one loop, comparing pointer-plus-length pairs
    `_seq_eq_operand_c` returns for each operand, structurally the flat
    case's SAME shape as the nested case's own inner loop (kept as one
    helper-free block below rather than factored through the nested case's
    inner-loop code, since the two need different index/name plumbing --
    the nested case's inner loop is generated per outer iteration, this
    one only once)."""
    n = _SEQ_EQ_CTR[0]
    _SEQ_EQ_CTR[0] += 1
    eq, i = f"__seq_eq{n}", f"__seq_eq{n}_i"
    out = []
    a_e, b_e = e["args"]
    ta = typ(a_e, ctx.env, ctx.funs)
    if is_nested_seq_type(ta):
        if "var" not in a_e or "var" not in b_e:
            raise NotImplementedError(
                "seq extensional equality loop: a nested-seq (seq<seq>) "
                "operand must be a bare PARAMETER variable, not a "
                "computed row set; out of this pass's own scope "
                "(fz_p_nest_eq, the only nested cell measured)")
        av, bv = seq_var(a_e, ctx.env), seq_var(b_e, ctx.env)
        rl, rr = f"{eq}_rl", f"{eq}_rr"
        i2 = f"{i}2"
        row_eq = (f"({av}_off[__k + 1] - {av}_off[__k]) == "
                 f"({bv}_off[__k + 1] - {bv}_off[__k]) && "
                 f"(\\forall integer __j; 0 <= __j < "
                 f"({av}_off[__k + 1] - {av}_off[__k]) ==> "
                 f"{av}_data[{av}_off[__k] + __j] == "
                 f"{bv}_data[{bv}_off[__k] + __j])")
        out.append(f"{indent}int {i} = 0;")
        out.append(f"{indent}int {eq} = ({av}_n == {bv}_n);")
        out.append(f"{indent}/*@")
        out.append(f"{indent}  loop invariant 0 <= {i} <= {av}_n;")
        out.append(f"{indent}  loop invariant {i} <= {bv}_n;")
        out.append(f"{indent}  loop invariant {eq} == 1 ==> "
                  f"(\\forall integer __k; 0 <= __k < {i} ==> "
                  f"({row_eq}));")
        out.append(f"{indent}  loop assigns {i}, {eq};")
        out.append(f"{indent}  loop variant {av}_n - {i};")
        out.append(f"{indent}*/")
        out.append(f"{indent}while ({eq} && {i} < {av}_n) {{")
        out.append(f"{indent}  int {rl} = {av}_off[{i} + 1] - {av}_off[{i}];")
        out.append(f"{indent}  int {rr} = {bv}_off[{i} + 1] - {bv}_off[{i}];")
        out.append(f"{indent}  if ({rl} != {rr}) {{")
        out.append(f"{indent}    {eq} = 0;")
        out.append(f"{indent}  }} else {{")
        out.append(f"{indent}    int {i2} = 0;")
        out.append(f"{indent}    /*@")
        out.append(f"{indent}      loop invariant 0 <= {i2} <= {rl};")
        out.append(f"{indent}      loop invariant {eq} == 1 ==> "
                  f"(\\forall integer __j; 0 <= __j < {i2} ==> "
                  f"{av}_data[{av}_off[{i}] + __j] == "
                  f"{bv}_data[{bv}_off[{i}] + __j]);")
        out.append(f"{indent}      loop assigns {i2}, {eq};")
        out.append(f"{indent}      loop variant {rl} - {i2};")
        out.append(f"{indent}    */")
        out.append(f"{indent}    while ({eq} && {i2} < {rl}) {{")
        out.append(f"{indent}      if ({av}_data[{av}_off[{i}] + {i2}] != "
                  f"{bv}_data[{bv}_off[{i}] + {i2}]) {{")
        out.append(f"{indent}        {eq} = 0;")
        out.append(f"{indent}      }}")
        out.append(f"{indent}      {i2} = {i2} + 1;")
        out.append(f"{indent}    }}")
        out.append(f"{indent}  }}")
        out.append(f"{indent}  {i} = {i} + 1;")
        out.append(f"{indent}}}")
        return out, eq
    ap, alen, adom = _seq_eq_operand_c(a_e, ctx, funs, task_name)
    bp, blen, bdom = _seq_eq_operand_c(b_e, ctx, funs, task_name)
    for d in adom + bdom:
        out.append(f"{indent}/*@ assert {d}; */")
    out.append(f"{indent}int {i} = 0;")
    out.append(f"{indent}int {eq} = (({alen}) == ({blen}));")
    out.append(f"{indent}/*@")
    out.append(f"{indent}  loop invariant 0 <= {i} <= ({alen});")
    out.append(f"{indent}  loop invariant {i} <= ({blen});")
    out.append(f"{indent}  loop invariant {eq} == 1 ==> "
              f"(\\forall integer __j; 0 <= __j < {i} ==> "
              f"({ap})[__j] == ({bp})[__j]);")
    out.append(f"{indent}  loop assigns {i}, {eq};")
    out.append(f"{indent}  loop variant ({alen}) - {i};")
    out.append(f"{indent}*/")
    out.append(f"{indent}while ({eq} && {i} < ({alen})) {{")
    out.append(f"{indent}  if (({ap})[{i}] != ({bp})[{i}]) {{")
    out.append(f"{indent}    {eq} = 0;")
    out.append(f"{indent}  }}")
    out.append(f"{indent}  {i} = {i} + 1;")
    out.append(f"{indent}}}")
    return out, eq


def _seq_eq_value(e: dict, ctx: Ctx, indent: str, funs: dict,
                  task_name: str):
    """`_seq_eq_loop` plus the `!=` negation, in one call for the three
    `stmts()` call sites (assign/return right-hand side, `if` condition)
    that substitute its result where a single `cexpr()` value would
    otherwise go."""
    lines, tmp = _seq_eq_loop(e, ctx, indent, funs, task_name)
    return lines, (f"(!{tmp})" if e["op"] == "!=" else tmp)


def stmts(body: list, ctx: Ctx, task_name: str, indent: str,
          _prefix: dict | None = None) -> list:
    # THE FRAME-FACT GAP, framac column (2026-09-12, ROADMAP 16.2): a
    # scalar local declared in the PREFIX (this statement list, before
    # some later `while`) and never reassigned inside that loop's body is
    # loop-invariant by construction (C scoping means nothing in the loop
    # can touch it unless it is an assignment target, and `assigned_names`
    # already computes that set), but was never SAID to WP as a `loop
    # invariant`. Measured directly on appendArrayToSeq (`h := a_n;`
    # before the loop, guard `i_v2 < h`, body assert `i_v2 < a_n` for
    # `a[i_v2]`): the invariant list already carries `i_v2 <= a_n` (the
    # task's own), so the assert needs only `i_v2 != a_n`, which follows
    # from the guard `i_v2 < h` exactly when `h == a_n` is known -- and it
    # wasn't, so WP saw a genuinely underdetermined `h` and alt-ergo timed
    # out searching for a proof of a goal that was one missing premise
    # from being false. `_prefix` accumulates {name: init-expr} for every
    # scalar (`int`/`bool`) local declared by a plain `var` statement seen
    # so far IN THIS CALL's own statement list (mirrors C scoping: a
    # recursive call for an `if`-branch or a `while`-body gets a COPY, so
    # a local declared inside one branch never leaks to its sibling or
    # back out, and a local declared inside the loop body itself never
    # becomes a fact about the loop it is declared in). A name is dropped
    # from `_prefix` the moment this same list reassigns it (`assign`),
    # so only a name that is TRULY never written again carries a fact
    # forward. At a `while`, every surviving name not in that loop's own
    # `assigned_names` hit-set gets `loop invariant {name} == {its own
    # defining expression, rendered now}` -- ADDITIVE ONLY: a TRUE
    # equality (the prefix's own straight-line computation, unchanged by
    # anything the loop's recursion can reach) never weakens an existing
    # obligation and never lets WP discharge a goal that does not
    # actually follow from the task's own requires/ensures/invariants;
    # it only gives WP a premise the source program already guarantees
    # but this lowering used to withhold.
    prefix = dict(_prefix) if _prefix is not None else {}
    out = []
    for s in body:
        if "assign" in s:
            name, e = s["assign"]
            assert name in ctx.env, f"assign to undeclared {name}"
            prefix.pop(name, None)
            if is_nested_seq_type(ctx.env[name]):
                # NAMED REFUSAL, added 2026-09-10 (SPEC.md "Nested
                # sequences"): the only seq<seq>-typed names `ctx.env` can
                # ever hold are the task's own PARAMETERS (a seq<seq>
                # RETURN is refused wholesale in `lower()`, and a
                # seq<seq>-typed `var` local is refused just below, in
                # this same function), so this guards the one remaining
                # way a BUILT nested value could reach C: reassigning a
                # parameter in place. Same gap as the RETURN case, same
                # reason (no CAPACITY-style machinery for a second,
                # row-shaped dimension), stated here rather than left to
                # fall into the plain `else` below, which would try to
                # `cexpr()` an `update`/`fill`/`seq` node this backend has
                # no executable rendering for at all and fail with a
                # generic "no operator" `ValueError` instead of a named
                # reason.
                raise NotImplementedError(
                    "nested seq (seq<seq>) assignment target: building a "
                    "row set has no encoding in this lowering (see the "
                    "seq<seq> RETURN refusal in `lower()`); only a "
                    "seq<seq> PARAMETER, read via `len`/`at`, is supported")
            if ctx.env[name] == "seq":
                out += seq_assign_lines(name, e, ctx, indent, ctx.funs,
                                        task_name)
            elif _seq_eq_top(e, ctx):
                # FRAMAC-NESTED, ROADMAP 13.4 item (a), 2026-09-12:
                # fz_p_nest_eq's own `r := (m == n)` -- a bare seq
                # extensional `==`/`!=` assigned directly to a bool-typed
                # name, `cexpr`'s own named refusal there (SEQ VALUE,
                # executable position, item 4) -- now has a
                # statement-shaped rendering instead of a single C value.
                out += at_asserts(e, ctx, indent, ctx.funs, task_name)
                lines, val = _seq_eq_value(e, ctx, indent, ctx.funs,
                                          task_name)
                out += lines
                out.append(f"{indent}{name} = {val};")
            else:
                out += at_asserts(e, ctx, indent, ctx.funs, task_name)
                out.append(f"{indent}{name} = "
                           f"{cexpr(e, ctx.env, ctx.funs, task_name)};")
        elif "return" in s:
            # Early exit (v1, 2026-09-08): `Expr` is in the same position as
            # an assignment's right-hand side, so it owes the same
            # definedness asserts (the `at` bound, the `!= 0` divisor). A
            # real C `return` then ends the function immediately, from
            # whatever nesting depth of `if`/`while` it sits at, which is
            # exactly SPEC's rule: WP proves `ensures` at every return and
            # never demands the enclosing loop's invariant there, because
            # the loop is simply not reached again. Nothing may follow this
            # statement in its own block (well-formedness's job, not this
            # file's), so no dead-code smoke goal can arise from it: the
            # code after the enclosing `if` remains reachable on the other
            # branch, never on this one.
            #
            # A seq-typed return (2026-09-09) has no scalar C `return`
            # value at all: `lower()` gives it an output buffer parameter
            # instead (see the seq value machinery section), so an early
            # exit writes that buffer the same way an ordinary assignment
            # to it would and then leaves with a bare, void `return;`.
            name, e = s["return"]
            assert name in ctx.env, f"return of undeclared {name}"
            if ctx.env[name] == "seq":
                out += seq_assign_lines(name, e, ctx, indent, ctx.funs,
                                        task_name)
                # CAPACITY mode (2026-09-09): the C function's own
                # `\result` carries the buffer's actual final logical
                # length (see the seq value machinery section's CAPACITY
                # discussion), so an early exit returns the length local
                # `ctx.seq_len` names for this target instead of a bare,
                # void `return;`. Not exercised by any committed task
                # (neither `tail` nor `filter_pos` returns the seq early)
                # but kept correct rather than left to crash or lie.
                if name in ctx.seq_len:
                    out.append(f"{indent}return {ctx.seq_len[name]};")
                else:
                    out.append(f"{indent}return;")
            elif _seq_eq_top(e, ctx):
                # FRAMAC-NESTED, ROADMAP 13.4 item (a), 2026-09-12: same
                # rendering as the "assign" branch above, for an early-
                # exit `return` whose expression is a bare seq
                # extensional `==`/`!=`. Not exercised by any of this
                # pass's own three measured cells (none returns one
                # early), kept correct rather than left to fall through
                # to `cexpr`'s own named refusal for the same reason the
                # "assign" branch is not left to either.
                out += at_asserts(e, ctx, indent, ctx.funs, task_name)
                lines, val = _seq_eq_value(e, ctx, indent, ctx.funs,
                                          task_name)
                out += lines
                out.append(f"{indent}{name} = {val};")
                out.append(f"{indent}return {name};")
            else:
                out += at_asserts(e, ctx, indent, ctx.funs, task_name)
                out.append(f"{indent}{name} = "
                           f"{cexpr(e, ctx.env, ctx.funs, task_name)};")
                out.append(f"{indent}return {name};")
        elif "var" in s:
            v = s["var"]
            if v["type"] == "seq":
                slice_alias = _slice_alias_base(v["init"], ctx.env)
                if slice_alias is None:
                    # SPEC.md allows a seq-typed LOCAL (`var a: seq :=
                    # s;`); this lowering implements only the slice-ALIAS
                    # shape above (`_slice_alias_base`), not a general
                    # one: any other initializer (a string-lib member's
                    # result, `update`/`fill`, ...) has no requires-time
                    # bound to size a fresh backing buffer from, so this
                    # is a stated scope limit, not a silent gap.
                    raise NotImplementedError(
                        "seq-typed local variables are not supported by "
                        "this lowering except the slice-ALIAS shape "
                        "(`v := s[a..b]`, word_count's own case and its "
                        "own OFF-BY-ONE twin); no requires-time bound "
                        "sizes a fresh backing buffer for any other "
                        "initializer")
                base_var, lo, hi = slice_alias
                # The slice's own domain obligation, `0 <= a <= b <=
                # len(s)`, exactly as any other read of a slice already
                # gets (`at_asserts`, unchanged): for the OFF-BY-ONE
                # twin's `s[1..len(s)]` this is the UNDEFINED half of its
                # own certificate at the witness `s = []` (`slice bounds
                # [1..0]`, SPEC.md's own words for this exact twin), not
                # a silent bad pointer.
                out += at_asserts(v["init"], ctx, indent, ctx.funs,
                                  task_name)
                lo_c = cexpr(lo, ctx.env, ctx.funs, task_name)
                hi_c = cexpr(hi, ctx.env, ctx.funs, task_name)
                out.append(f"{indent}int *{v['name']} = "
                           f"{base_var} + ({lo_c});")
                out.append(f"{indent}int {v['name']}_n = "
                           f"({hi_c}) - ({lo_c});")
                ctx = ctx.bind(v["name"], "seq")
                continue
            if is_nested_seq_type(v["type"]):
                # FRAMAC-NESTED, added 2026-09-14 (DESIGN-framac-nested-
                # seq.md section 1, "a seq<seq> ... LOCAL"). A
                # seq<seq>-typed LOCAL still has no requires-time bound
                # to size a fresh backing buffer from for a genuinely
                # data-dependent build, exactly the seq<seq> RETURN
                # refusal's own reasoning (`lower()`, unchanged) -- but
                # `fz_p_str_tab`'s own local (`rows := split([65, 9,
                # 66])`) is, like `fz_p_nest_empty`/`fz_p_str_splitempty`
                # before it, a COMPILE-TIME CONSTANT: `_fold_nested_rows`
                # folds it to concrete Python rows and this declares a
                # real C array LOCAL sized by that constant, "no VLA, no
                # malloc" (the design's own words) because there is
                # nothing left to size dynamically -- both dimensions
                # are literal C array-length constants, not `requires`
                # obligations the caller owes at all (a LOCAL, unlike a
                # RETURN, has no caller to state one to), so no ACSL
                # clause is needed here, only the declarations
                # themselves. A row's own contents are individual
                # literal initializer entries, the same "no loop needed"
                # move `_ret_nested_fold`'s own RETURN case makes.
                rows = _fold_nested_rows(v["init"])
                if rows is None:
                    raise NotImplementedError(
                        "nested seq (seq<seq>) local variables are not "
                        "supported by this lowering beyond a "
                        "compile-time-constant value "
                        "(`_fold_nested_rows`, added 2026-09-14); only a "
                        "seq<seq> PARAMETER, read via `len`/`at`, is "
                        "supported for a genuinely data-dependent value")
                nm = v["name"]
                flat = [x for row in rows for x in row]
                offs = [0]
                acc = 0
                for row in rows:
                    acc += len(row)
                    offs.append(acc)
                data_init = ("{" + ", ".join(str(x) for x in flat) + "}"
                            if flat else "{0}")
                off_init = "{" + ", ".join(str(x) for x in offs) + "}"
                out.append(f"{indent}int {nm}_data[{max(1, len(flat))}] "
                           f"= {data_init};")
                out.append(f"{indent}int {nm}_off[{len(rows) + 1}] = "
                           f"{off_init};")
                out.append(f"{indent}int {nm}_n = {len(rows)};")
                ctx = ctx.bind(nm, v["type"])
                continue
            out += at_asserts(v["init"], ctx, indent, ctx.funs, task_name)
            ctx = ctx.bind(v["name"], v["type"])
            if isinstance(v["type"], dict) and "pair" in v["type"]:
                # PAIRS, extended 2026-09-10: a pair-typed LOCAL (`var p:
                # (int, int) := ...;`), one of the two gaps the section
                # comment above `_pair_field_c` named by construction
                # ("stmts()'s `var` case has no pair-typed branch"). No
                # committed or fuzzed task declares one yet (found by
                # scanning the whole v1pairs corpus, not measured on a
                # real cell), so this is written for the same reason
                # `_cev`'s "update"/"fill" cases are: a complete rule, not
                # a rule stopped at the first task that happens to need
                # it. Declared as the struct type, by-value, exactly like
                # a pair-typed RETURN or PARAMETER; `_pair_struct_name`
                # still raises BY NAME for a seq component, so this
                # inherits that same named refusal rather than widening
                # it.
                sname = _pair_struct_name(*v["type"]["pair"])
                out.append(f"{indent}struct {sname} {v['name']} = "
                           f"{cexpr(v['init'], ctx.env, ctx.funs, task_name)};")
            else:
                out.append(f"{indent}int {v['name']} = "
                           f"{cexpr(v['init'], ctx.env, ctx.funs, task_name)};")
                # THE FRAME-FACT GAP (see this function's own docstring
                # comment above): a scalar local's defining expression is
                # remembered, straight-line, so a later `while` in this
                # same statement list can state it as a loop invariant if
                # nothing in that loop reassigns the name.
                prefix[v["name"]] = v["init"]
        elif "if" in s:
            c = s["if"]
            out += at_asserts(c["cond"], ctx, indent, ctx.funs, task_name)
            if _seq_eq_top(c["cond"], ctx):
                # FRAMAC-NESTED, ROADMAP 13.4 item (a), 2026-09-12:
                # isSublist's `if (sub == main_v[i..i+len(sub)])` and
                # containsSequence's `if (sub == at(list, i_v))` -- a
                # bare seq extensional `==`/`!=` reaching an `if`
                # CONDITION directly, `cexpr`'s own named refusal there
                # (SEQ VALUE, executable position, item 4) once more.
                # `at_asserts` above already covers any `at`/`div`/`mod`
                # nested inside the comparison's own operands (e.g. a
                # slice bound), unchanged; the loop's OWN domain asserts
                # (a slice/row operand's own bound) are emitted by
                # `_seq_eq_loop` itself.
                lines, cond_c = _seq_eq_value(c["cond"], ctx, indent,
                                             ctx.funs, task_name)
                out += lines
            else:
                cond_c = cexpr(c["cond"], ctx.env, ctx.funs, task_name)
            out.append(f"{indent}if ({cond_c}) {{")
            out += stmts(c["then"], ctx, task_name, indent + "  ",
                        dict(prefix))
            out.append(f"{indent}}} else {{")
            out += stmts(c["else"], ctx, task_name, indent + "  ",
                        dict(prefix))
            out.append(f"{indent}}}")
        elif "while" in s:
            w = s["while"]
            # WHILE-GUARD DEFINEDNESS, added 2026-09-09 (the eighth sweep's
            # residual, COVERAGE-lifted-785.md: the two MBPP-DFY
            # IsPrime/IsNonPrime tasks loop on `while i <= n / 2`). A
            # `div`/`mod`/`at` in the GUARD is evaluated once before the loop
            # and once more per iteration, and unlike every other position
            # this lowering handles (`if` conditions, assignments, returns),
            # the guard's own evaluation precedes the loop body, not a
            # statement inside it -- there was no single statement its
            # assert could go in front of, so this lowering used to ABSTAIN
            # (NotImplementedError) on any such guard rather than emit an
            # under-checked one.
            #
            # The fix: emit the same `at_asserts` twice. Once immediately
            # before the `while` -- this discharges the guard's FIRST
            # evaluation, proved from whatever state the code before the
            # loop established. And once as the FIRST statement of the loop
            # body -- this discharges every LATER evaluation, because WP's
            # own loop-preservation step already proves "loop invariant &&
            # cond" generically for an arbitrary reachable loop-head state
            # (not just the concrete one that happened to enter this
            # iteration), so an assert stated there under that same
            # hypothesis pair is proved for every state a later guard
            # re-evaluation will actually see, by the same induction the
            # invariant itself relies on. MEASURED on both lifted tasks
            # (divisor a literal `2`, never zero): this placement is what WP
            # proves; the alternative the residual note flagged as a
            # fallback (the assert as the LAST statement of the body
            # instead, after the increment) was not needed. A guard whose
            # divisor could reach zero, or an `at` whose index could leave
            # bounds, now reads UNPROVED at this assert rather than letting
            # unchecked C UB through silently -- the gap this fix closes.
            guard_ats_pre = at_asserts(w["cond"], ctx, indent, ctx.funs,
                                       task_name)
            guard_ats_body = at_asserts(w["cond"], ctx, indent + "  ",
                                        ctx.funs, task_name)
            ann = [f"{indent}  loop invariant {pred(i, ctx)};"
                   for i in w.get("invariants", [])]
            hit, dec = assigned_names(w["body"], ctx.seq_len)
            frame = [n for n in dict.fromkeys(hit) if n not in dec]
            # THE FRAME-FACT GAP, framac column (2026-09-12, ROADMAP
            # 16.2, see this function's own docstring comment above for
            # the full account): every scalar prefix local this loop's
            # own `hit` set never assigns is stated as an equality loop
            # invariant, pinning it to its own straight-line defining
            # expression. `hit` (not `frame`, which also drops names this
            # loop merely re-declares as its own locals) is the right
            # test: a name the loop assigns even once is exactly the
            # thing WP already treats as havocked, so no prefix fact
            # about it would be sound to state as an invariant.
            for pn, pinit in prefix.items():
                if pn not in hit:
                    ann.append(f"{indent}  loop invariant {pn} == "
                               f"{cexpr(pinit, ctx.env, ctx.funs, task_name)};")
            # CAPACITY mode's implicit LOWER bound (2026-09-09): `0 <=
            # r_len` is a MATHEMATICAL fact about any seq's length (never
            # negative), true by construction of the encoding itself
            # (`r_len` only ever starts at 0 or a literal's own element
            # count, and only ever increases), but WP does not know it
            # carries across loop iterations unless it is stated as an
            # invariant too. MEASURED on `filter_pos`: omitting it left
            # `Loop assigns (2/2)` (proving the just-written location `r +
            # (r_len - 1)` lies inside `r`'s own `\valid`-ed range) an
            # honest ALT-ERGO STEP LIMIT, because that lower bound has no
            # other source (the task's own invariants never state it;
            # nothing about `i`'s own bound implies it).
            #
            # Deliberately NOT the matching upper bound `r_len <= {n}_n`:
            # that one is TASK semantics, not an encoding artifact -- on
            # `filter_pos` it already follows from the task's OWN stated
            # invariants (`i <= len(s)` and `len(r) <= i`, chained through
            # `r_n == len(s)`), exactly the chain an INVARIANT-DROP twin
            # threatens. MEASURED: adding it here anyway (tried first, the
            # natural-looking `0 <= r_len <= r_n` pairing) made the loop's
            # own `assigns` goal `Qed`-trivial to `true` even with `i <=
            # len(s)` dropped, since `r_len <= r_n` alone (not via `i`)
            # already closes the postcondition `\result <= len(s)` (`r_n
            # == len(s)` by `requires`) -- an ENCODING artifact standing
            # in for task semantics the mutation was supposed to remove,
            # which made the twin verify in FULL and the file read
            # MALFORMED (both the twin's own contract and the
            # certificate's negation of it accepted, a contradiction) in
            # place of the intended REFUTED. Emitted only for a capacity
            # name whose length local this loop's own `frame` already
            # carries (it actually writes it), never blanket for every
            # capacity-tracked return in scope.
            for n, ln in ctx.seq_len.items():
                if ln in frame:
                    ann.append(f"{indent}  loop invariant 0 <= {ln};")
            targets = [_assigns_target(n, ctx) for n in frame]
            ann.append(f"{indent}  loop assigns "
                       f"{', '.join(targets) if targets else chr(92) + 'nothing'};")
            ann.append(f"{indent}  loop variant ({term(w['decreases'], ctx)});")
            out += guard_ats_pre
            out.append(f"{indent}/*@")
            out += ann
            out.append(f"{indent}*/")
            out.append(f"{indent}while "
                       f"({cexpr(w['cond'], ctx.env, ctx.funs, task_name)}) "
                       f"{{")
            out += guard_ats_body
            out += stmts(w["body"], ctx, task_name, indent + "  ",
                        dict(prefix))
            out.append(f"{indent}}}")
        else:
            raise ValueError(f"t has no statement {s!r}")
    return out


# ------------------------------------------------- spec_fun termination -----

def subst(e: dict, m: dict) -> dict:
    if "var" in e:
        return m.get(e["var"], e)
    if "int" in e or "bool" in e:
        return e
    if "ite" in e:
        i = e["ite"]
        return {"ite": {k: subst(i[k], m) for k in ("cond", "then", "else")}}
    if "call" in e:
        c = e["call"]
        return {"call": {"fun": c["fun"],
                         "args": [subst(a, m) for a in c["args"]]}}
    for kind in ("forall", "exists"):
        if kind in e:
            q = e[kind]
            m2 = {k: v for k, v in m.items() if k != q["var"]}
            return {kind: {"var": q["var"], "lo": subst(q["lo"], m),
                           "hi": subst(q["hi"], m),
                           "body": subst(q["body"], m2)}}
    return {"op": e["op"], "args": [subst(a, m) for a in e.get("args", [])]}


def self_calls(e: dict, fun: str, path: list) -> list:
    """(args, path-conditions) for every self-call, path tracked through the
    definedness-relevant branching structure (ite branches, and/or/implies
    short-circuit)."""
    out = []
    if "ite" in e:
        i = e["ite"]
        out += self_calls(i["cond"], fun, path)
        out += self_calls(i["then"], fun, path + [i["cond"]])
        out += self_calls(i["else"], fun,
                          path + [{"op": "not", "args": [i["cond"]]}])
        return out
    if "call" in e:
        c = e["call"]
        for a in c["args"]:
            out += self_calls(a, fun, path)
        if c["fun"] == fun:
            out.append((c["args"], path))
        return out
    for kind in ("forall", "exists"):
        if kind in e:
            q = e[kind]
            for sub in (q["lo"], q["hi"], q["body"]):
                out += self_calls(sub, fun, path)
            return out
    if "op" not in e:
        return out
    op, args = e["op"], e.get("args", [])
    if op in ("and", "or"):
        seen = []
        for a in args:
            out += self_calls(a, fun, path + seen)
            g = a if op == "and" else {"op": "not", "args": [a]}
            seen = seen + [g]
        return out
    if op == "implies":
        out += self_calls(args[0], fun, path)
        out += self_calls(args[1], fun, path + [args[0]])
        return out
    for a in args:
        out += self_calls(a, fun, path)
    return out


def spec_fun_acsl(f: dict, funs: dict, declare_only: bool = False) -> list:
    """The recursive logic definition plus its measured termination lemmas
    (WP does not check logic-function termination itself; see docstring).

    WITHHELD DEFINITION, 2026-09-11 (ROADMAP 13.4, framac-axiom): when
    `declare_only` is set (`lower()` sets it for exactly the spec_fun a
    "measure"-kind witness names, harness.real_witness/interp.
    MeasureViolation), this emits a bare ACSL declaration -- `logic
    {res} {name}(...);`, no `= body`, no termination lemmas -- instead of
    the recursive definition below. See the module docstring's dated note
    "THE WITHHELD-DEFINITION CERTIFICATE" for why this is sound: the
    witness is the harness's own concrete counterexample to this exact
    function's `decreases`, confirmed by `_measure_certificate`'s ground
    arithmetic, so the recursive equation the full definition would axiomatize
    is not well founded (`g(n) = g(n) + 1` at `decreases 0` has no
    solution) -- WP assumes a `logic ... = ...` definition as an axiom
    without checking termination (this function's own un-withheld
    branch's docstring line above), and an axiom asserting a
    non-well-founded equation makes the whole ACSL theory inconsistent,
    read as VACUOUS by verifiers/framac.py's `_vacuity_smoke`/consistency
    probe before the certificate goal is ever reached (see
    verifiers/framac.py's own module docstring, "MEASURE WITNESS"
    section, and this file's own module docstring's "THE
    WITHHELD-DEFINITION CERTIFICATE" note for the measured before/after
    -- t/CONFORMANCE.md itself is not this worktree's file to update, so
    it still reads the pre-patch 450 of 462 until whoever owns it
    regenerates it). A bare declaration still gives every `ensures`/`term`
    call site naming `g` something to typecheck against (ACSL only needs
    the signature to elaborate a call), and `verifiers/framac.py`'s own
    `_LOGIC_DEF` regex requires a trailing `=` to call a block a
    "definition" at all, so a declared-only `g` is invisible to the
    consistency probe: no axiom, nothing to doom. Termination lemmas are
    skipped too -- there is no defining equation left for them to reason
    about, and this file already knows (from the witness) that no proof
    of termination exists to state. Withheld ONLY for the one function
    the witness names, ONLY when the witness's kind is "measure": every
    other spec_fun on the same task (and every task with no such witness)
    still gets its full recursive definition, byte-identical to before."""
    env = {p["name"]: p["type"] for p in f["params"]}
    labeled = funs[f["name"]]["labeled"]
    lab = "{L}" if labeled else ""
    sig = []
    for p in f["params"]:
        if p["type"] == "seq":
            sig += [f"int *{p['name']}", f"integer {p['name']}_n"]
        else:
            sig.append(f"integer {p['name']}")
    res = {"int": "integer", "bool": "boolean"}[f["result"]]
    if declare_only:
        return [f"/*@ logic {res} {f['name']}{lab}({', '.join(sig)}); */"]
    body_ctx = Ctx(env, funs, ret=None, label="L")
    lines = [f"/*@ logic {res} {f['name']}{lab}({', '.join(sig)}) =",
             f"      {term(f['body'], body_ctx)};", "*/"]
    quant = ", ".join(
        (f"int *{p['name']}, integer {p['name']}_n"
         if p["type"] == "seq" else f"integer {p['name']}")
        for p in f["params"])
    for k, (args, path) in enumerate(self_calls(f["body"], f["name"], []), 1):
        m = {p["name"]: a for p, a in zip(f["params"], args, strict=True)}
        measure = term(f["decreases"], body_ctx)
        measure2 = term(subst(f["decreases"], m), body_ctx)
        concl = f"(({measure2}) >= 0 && ({measure2}) < ({measure}))"
        guard = " && ".join(f"({pred(p, body_ctx)})" for p in path)
        prop = f"({guard}) ==> {concl}" if guard else concl
        lines += [f"/*@ lemma {f['name']}_terminates_{k}{lab}:",
                  f"      \\forall {quant};",
                  f"      {prop};", "*/"]
    return lines


def _spec_fun_c(f: dict, funs: dict) -> list:
    """FRAMAC-CLOSURE, added 2026-09-14 (sweep r25's five sole-framac-
    blocker rows, dafny-synthesis 412/426/436/554/629: each calls a
    spec_fun predicate -- isEven, isOdd or isNegative -- from inside its
    loop, EXECUTABLE position, e.g. `if isEven(arr[i])`). A spec_fun is
    an ACSL logic function (`spec_fun_acsl`, above), not C, so such a
    call has no C counterpart to invoke; `cexpr`'s "call" case raised an
    unconditional NotImplementedError for exactly this before this pass
    (the module docstring's own ABSTAIN-3 note names the design this
    function fills in). Fixed by mirroring the spec_fun as a SECOND,
    plain C function (`{name}_c`, this function's return value): its
    BODY is the spec_fun's own expression rendered through `cexpr` (C,
    not ACSL `term`), and its CONTRACT states it agrees with the logic
    function everywhere it is called -- `\\result == f(args)` for an
    int-result spec_fun, `(\\result != 0) <==> f(args)` for a bool-
    result one (ACSL's `boolean` and C's 0/1 `int` are different types,
    so a bare `==` would not typecheck). The call site (`cexpr`'s "call"
    case) then emits `{name}_c(args)` for a call to this spec_fun
    reaching executable position; every OTHER position (a `requires`/
    `ensures`/loop invariant naming the spec_fun symbolically) is
    UNCHANGED, still the plain logic-function call `spec_fun_acsl`
    already renders -- nothing here touches, weakens, or duplicates what
    the task's own spec states, exactly SPEC.md's twin-safety rule ("the
    twin never touches requires, ensures, spec_funs, or decreases").

    Eligibility (checked by the caller, `funs[name]["executable"]`, set
    in `lower()`'s `funs` construction): no seq-typed PARAMETER (this
    function's C signature has none to mirror `spec_fun_acsl`'s own
    buffer-pointer ACSL signature against; unexercised by any lifted
    task's spec_fun, named rather than guessed at) and NOT self-
    recursive (a recursive spec_fun's mirror would need its own
    `decreases`-backed WP termination obligation, the general design the
    module docstring's ABSTAIN-3 note sketches for `factorial` and
    leaves undone; `factorialOfLastDigit`/`Triple`, the two lifted tasks
    that would need it, are UNCHANGED by this function, still abstaining
    with the identical original message via the ineligibility check at
    the call site). None of the 34 committed tasks (t/AGREEMENT.md)
    declares any spec_fun at all (confirmed: `grep spec_fun t/tasks/
    *.t` -> no match), so this widening reaches only the lifted corpus,
    never the regression bar's own 34-task column."""
    params_c = ", ".join(f"int {p['name']}" for p in f["params"])
    env = {p["name"]: p["type"] for p in f["params"]}
    body_c = cexpr(f["body"], env, funs, f["name"])
    args_acsl = ", ".join(p["name"] for p in f["params"])
    if f["result"] == "bool":
        contract = f"(\\result != 0) <==> {f['name']}({args_acsl})"
    else:
        contract = f"\\result == {f['name']}({args_acsl})"
    return [
        "/*@",
        f"  ensures {contract};",
        "*/",
        f"int {f['name']}_c({params_c}) {{ return {body_c}; }}",
    ]


# ------------------------------------------------ refutation certificate ----
#
# THE CERTIFICATE (shared protocol, ROADMAP 10.7): WP with alt-ergo never
# distinguishes a false goal from a hard one (verifiers/framac.py records the
# side-by-side measurement), so the adapter no longer mints REFUTED from an
# unproved goal. To EARN a twin refutation, the twin file carries a second
# function that replays the twin computation at the measured witness input as
# straight-line ground code, ending in one ACSL assert named exactly
# t_refutation_certificate: the negation of the instantiated ensures
# (definedness guards included, since t counts an undefined ensures as
# unsatisfied). The adapter mints REFUTED only when the kernel accepts that
# assert AND every other goal of the certificate function; a rejected
# certificate is UNPROVED, never REFUTED.
#
# Branch discipline, measured 2026-09-02: a ground-decided `if` in the
# certificate makes its untaken arm dead code, and -wp-smoke-tests fails the
# dead-code smoke goal (`Failed smoke-test` on cert_deadif.c), which scores
# the whole file VACUOUS. So the certificate contains NO branches at all:
# every `if` is resolved to the taken arm behind an emitted
# `/*@ assert cond; */` (or its negation), and every `while` is unrolled to
# its measured trace, one `assert cond;` per iteration plus a final
# `assert !cond;`. Each branch decision is therefore a kernel-checked goal:
# if the lowering's replay disagrees with the program, some assert fails,
# the certificate is rejected, and the file honestly reads UNPROVED. A
# mis-replay can never mint, only fail.
#
# Scope, stated rather than stretched: a whole-program `value` witness whose
# twin value falsifies `ensures` (_ens is True) is certificatable by
# `_value_certificate`, straight-line ground replay from the params, exactly
# as above. A twin body carrying a task self-call (recursion has no bounded
# ground unrolling here) is skipped there. Skipping means the twin cell reads
# timeout/unproved and the flip is honestly lost.
#
# Two more kinds, added 2026-09-09 for SPEC.md "Sequences as values" (the
# construct that also added `update`/`fill`, whose committed tasks measure
# one of each):
#
#   `undefined` (`_undef_certificate`): the twin has NO VALUE at the
#   witness, because some statement's right-hand side hit a partial
#   operator (`at`, `update`, `fill`, `div`, `mod`) outside its domain
#   before `ensures` could even be instantiated. What is ground and
#   checkable is the operator's OWN definedness obligation: re-walk the
#   twin body with `interp.ev`, in the same left-to-right order
#   `interp.py`'s own `exec_body` used to raise the `Undef` that minted
#   this witness kind, using `defs_t` (the SAME definedness rule `defs()`
#   already renders to ACSL, restated as a t formula so `interp.ev` can
#   decide it), and certify the negation of the first one that comes back
#   false. Unlike the value-kind certificate, no C statement is replayed:
#   every name the obligation can mention is either a task param (declared
#   ground, exactly as the value-kind branch already declares them) or an
#   int/bool local computed along the way (declared ground as the walk
#   proceeds), so the obligation renders straight through this file's own
#   `pred()`. A SEQ-typed intermediate local assigned before the failing
#   statement refuses (materializing its snapshot would need the full
#   replay this shortcut exists to avoid); swap's own undefined witness
#   fails on the body's FIRST statement, so this is not exercised there,
#   only documented for the next task that might need it.
#
#   `exit` (`_exit_certificate`): interp.invariant_witness's own
#   obligation restated: a loop STATE where the surviving invariants hold,
#   the guard is false, but `ensures` is false there. Unlike a `value`
#   witness this state is not REACHED by running the function from its
#   params (`_Admissible` screens for states a sound kernel cannot rule
#   out, not for states an actual run passes through), so it is declared
#   directly as ground C locals -- every name the witness names, params
#   and loop-scope locals alike, the same declare-a-ground-array-or-int
#   shape the value-kind branch already uses for params -- and
#   `_cert_stmts` (unmodified) replays only the twin's mutated loop onward
#   (`_loop_suffix`), which correctly computes zero further iterations
#   when the witness already has the guard false, exactly reverse's own
#   measured case. Scope limit: only a TOP-LEVEL loop (not nested under an
#   `if`) is handled; no committed task's exit witness has needed more.
#
# Both new kinds reuse `_cert_stmts`/`_cev`/`_cert_cexpr` only where those
# already work (ground replay of ordinary, non-seq-assigning statements);
# neither extends them to emit a seq-typed assignment's C text (the copy
# and fill loops `seq_assign_lines` renders for the REAL/twin function
# bodies): an update/fill node reaching `_cert_cexpr` still raises its
# existing `ValueError` for an unrecognized operator, caught by
# `certificate`'s dispatcher exactly like every other unexpressible
# witness, and that cell honestly reads unproved rather than certifying
# something unmeasured.

# --------------------------------------- the divisor-bound lemma -----
#
# DIVISOR-BOUND LEMMA (2026-09-12, ROADMAP 16.2, framac-cert): ported from
# `lower_verus.py`/`lower_fstar.py`'s own functions of the same name
# (2026-09-11), restated over THIS file's own t-AST access (`exists`/
# `forall` dict keys carrying `body`/`hi`/`lo`/`var`, not the other two
# files' SeqExpr-shaped helpers) and emitted as ACSL, not Rust/F* text.
# dafny-synthesis isNonPrime (3) and isPrime (605) trial-divide `n` only
# up to `n div 2` while their own `ensures` quantifies the divisor over
# the WIDER range `[lo, n)` -- the fact no stated loop invariant supplies
# is the number-theory lemma this family needs at the loop's exit: any
# `k` with `lo <= k < n` and `n mod k == 0` satisfies `k <= n div 2`
# (`n == (n div k) * k`, and `n div k >= 2` since `k < n` rules out
# `n div k <= 1`, so `n >= 2*k`). Restated here as the single COMPOUND
# fact the goal actually needs (widening the loop's own `[lo, i)`
# existential/universal to the full `[lo, n)` one the `ensures` states),
# rather than the two-step bare bound `lower_verus.py` uses plus an
# explicit forall-rewrite proof: alt-ergo is an UNTRIGGERED, ground-term
# driven prover (unlike Z3, the engine behind Verus/Dafny, which needs
# hand triggers for exactly this shape, `lower_verus.py`'s own dated
# note), so a single lemma already stated as an `<==>` over `[lo, n)`
# and `[lo, i)` lets it instantiate at the two ground integers already
# in the goal's own context (the function's `n`, the loop's own final
# `i`) with no explicit trigger syntax to write (ACSL/WP has none).
#
# `_divisor_bound_target` recognizes the shape from the task's own AST:
# an `ensures` of the form `result == (forall|exists) k in [lo, N) .
# (N mod k) RELOP 0`, a matching loop invariant of the SAME shape over
# `[lo, i)` (`i` the loop's own counter), and a guard `cond` exactly
# `i <= N div 2`. A task with none of it is untouched.
#
# NOT WIRED into `lower()`, measured 2026-09-12 (see the dated note just
# above the `spec_fun_acsl` header loop in `lower()`, where a hook that
# called these two functions was tried and then removed): the compound
# lemma this function builds is syntactically sound ACSL, but alt-ergo
# 2.4.3 -- this backend's pinned prover, with no `nonlinear_arith`-style
# escape hatch -- cannot discharge ANY of the nonlinear integer-product
# reasoning the divisor bound needs, confirmed on inputs far simpler
# than the compound lemma itself (probe1.c/probe2.c/probe3.c). Kept
# here, unused, as the measured shape of the fix rather than deleted,
# so a later session with a different pinned prover (or a hand-supplied
# Coq/Alt-Ergo proof script, out of this wave's scope) has the target
# already named.
def _quant_mod_relop_t(body: dict):
    """`body` is `(N mod k) RELOP 0` (RELOP "=="/"!="); returns `(N,
    k_name, RELOP)` or None. `k` must be a bare var, matching every task
    this targets (mirrors `lower_verus.py`'s function of the same
    purpose, over this file's own dict shapes)."""
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


def _result_eq_quant_t(e: dict, ret: str):
    """`e` is `result == Quant(...)` (either operand order); returns
    `(kind, quant_dict)` for kind in {"forall", "exists"}, or None."""
    if not (isinstance(e, dict) and e.get("op") == "=="):
        return None
    args = e.get("args")
    if not (isinstance(args, list) and len(args) == 2):
        return None
    a, b = args
    if a == {"var": ret}:
        qh = b
    elif b == {"var": ret}:
        qh = a
    else:
        return None
    for kind in ("forall", "exists"):
        if kind in qh:
            return kind, qh[kind]
    return None


def _loops_in(body: list):
    """Every `while` node in `body`, at any depth under `if` (not into
    another `while`'s own body: no committed or targeted task nests one
    trial-divide loop inside another)."""
    for s in body:
        if "while" in s:
            yield s["while"]
        elif "if" in s:
            yield from _loops_in(s["if"]["then"])
            yield from _loops_in(s["if"].get("else") or [])


def _divisor_bound_target(task: dict, real_body: list) -> dict | None:
    ret = task["returns"][0]["name"]
    for en in task.get("ensures", []):
        found = _result_eq_quant_t(en, ret)
        if found is None:
            continue
        kind, q = found
        rel = _quant_mod_relop_t(q.get("body"))
        if rel is None:
            continue
        dividend, _kname, relop = rel
        lo = q.get("lo")
        if lo is None:
            continue
        for w in _loops_in(real_body):
            for iv in w.get("invariants", []):
                ifound = _result_eq_quant_t(iv, ret)
                if ifound is None:
                    continue
                ikind, iq = ifound
                if ikind != kind or iq.get("lo") != lo:
                    continue
                irel = _quant_mod_relop_t(iq.get("body"))
                if irel is None or irel[0] != dividend or irel[2] != relop:
                    continue
                ihi = iq.get("hi")
                if not (isinstance(ihi, dict)
                       and list(ihi.keys()) == ["var"]):
                    continue
                i_name = ihi["var"]
                want_cond = {"op": "<=", "args": [
                    {"var": i_name},
                    {"op": "div", "args": [dividend, {"int": 2}]}]}
                if w.get("cond") != want_cond:
                    continue
                return {"kind": kind, "relop": relop, "dividend": dividend,
                        "lo": lo, "i_name": i_name}
    return None


def _free_vars_t(e: dict, out: set) -> None:
    if "var" in e:
        out.add(e["var"])
        return
    if "int" in e or "bool" in e:
        return
    if "ite" in e:
        i = e["ite"]
        _free_vars_t(i["cond"], out)
        _free_vars_t(i["then"], out)
        _free_vars_t(i["else"], out)
        return
    for a in e.get("args", []):
        _free_vars_t(a, out)


def _divisor_bound_lemma_acsl(task: dict, plan: dict, env: dict,
                              funs: dict) -> str | None:
    """The lemma's ACSL text (a standalone global block, not attached to
    any function), or None if the plan's own dividend/lo mix in a name
    not in `env` (never true for either committed target, guarded so a
    future shape this was not measured against declines rather than
    emits unchecked text). `env`/`funs` are the task's own (already built
    by `lower()` before this is called), so `term()`/`pred()` resolve
    `n`/`i`'s types exactly as every other ACSL text in this file does;
    reusing the REAL identifier names as the lemma's own bound variables
    (rather than minting fresh ones) is what lets alt-ergo's ground-term
    instantiation find them at the use site with no trigger hint."""
    dividend, lo, i_name = plan["dividend"], plan["lo"], plan["i_name"]
    kv = "t_dvk"
    free: set = set()
    _free_vars_t(dividend, free)
    _free_vars_t(lo, free)
    if any(n not in env for n in free):
        return None                    # a dividend/lo naming an unknown var
    # `i_name` is the loop's OWN counter, a local `_divisor_bound_target`
    # already confirmed is compared (`<=`) against a `div` expression and
    # used as a quantifier's `hi` bound -- always an int, but never a
    # PARAMETER, so `env` (params + return only, built above this
    # function's own call site in `lower()`) never carries it; added here
    # rather than expecting the caller to.
    lemma_env = dict(env)
    lemma_env.setdefault(i_name, "int")
    bound_names = sorted(free | {i_name})
    ctx = Ctx(lemma_env, funs, ret=None, label="Here")
    body_e = {"op": plan["relop"], "args": [
        {"op": "mod", "args": [dividend, {"var": kv}]}, {"int": 0}]}
    wide = {plan["kind"]: {"body": body_e, "hi": dividend, "lo": lo,
                          "var": kv}}
    narrow = {plan["kind"]: {"body": body_e, "hi": {"var": i_name},
                             "lo": lo, "var": kv}}
    # Both `wide`/`narrow` are bool-typed (`typ()`'s own "forall"/"exists"
    # case), so `pred()`'s "==" case renders this as `<==>`, exactly the
    # ACSL connective a lemma states -- one `pred()` call over a single
    # t-Expr tree, the same construction every other ACSL text in this
    # file uses, rather than hand-formatted `t_div`/`<==>` text that
    # could drift from what `pred()`/`term()` actually emit elsewhere.
    guard_e = {"op": "and", "args": [
        {"op": ">=", "args": [dividend, {"int": 2}]},
        {"op": ">", "args": [{"var": i_name},
                             {"op": "div", "args": [dividend, {"int": 2}]}]}]}
    iff_e = {"op": "==", "args": [wide, narrow]}
    body_p = pred({"op": "implies", "args": [guard_e, iff_e]}, ctx)
    decl = "integer " + ", ".join(bound_names)
    lemma_name = f"t_divisor_bound_{task['name']}"
    return (f"/*@ lemma {lemma_name}:\n"
           f"  \\forall {decl}; {body_p};\n"
           "*/")


CERT_FN = "t_certificate"
CERT_GOAL = "t_refutation_certificate"
MAX_CERT_STMTS = 256


class _CertSkip(Exception):
    """This witness cannot be expressed as a ground certificate; the twin
    file is emitted without one (never a hard failure)."""


def _cev(e: dict, st: dict):
    """Ground evaluation of an EXECUTABLE t expression at concrete state,
    used only to pick branches and count loop iterations. Every decision it
    makes is re-emitted as a kernel goal, so a slip here rejects the
    certificate rather than corrupting it."""
    if "int" in e:
        return e["int"]
    if "bool" in e:
        return e["bool"]
    if "var" in e:
        if e["var"] not in st:
            raise _CertSkip(f"unassigned variable {e['var']} read")
        return st[e["var"]]
    if "ite" in e:
        i = e["ite"]
        return _cev(i["then"] if _cev(i["cond"], st) else i["else"], st)
    if "call" in e:
        raise _CertSkip("call in executable position")
    if "forall" in e or "exists" in e:
        raise _CertSkip("quantifier in executable position")
    op, args = e["op"], e.get("args", [])
    if op == "len":
        a0 = args[0]
        if a0.get("op") == "split" and len(a0.get("args", ())) == 1:
            # `len(s.split())` (SPEC.md "The string library (v1)",
            # 2026-09-11): `_wordcount`, the same running-prevws walk
            # `t_wc`/`t_wc_c` compute, so a witness replay of
            # word_count's real body agrees with the C the kernel
            # actually checks.
            return _wordcount(_cev(a0["args"][0], st))
        return len(_cev(args[0], st))
    if op == "at":
        s, i = _cev(args[0], st), _cev(args[1], st)
        if not 0 <= i < len(s):
            raise _CertSkip("undefined at in replay")
        return s[i]
    if op == "update":
        # SPEC.md "Sequences as values" (2026-09-09), interp.py's own
        # ground rule: a fresh list, `s` unchanged, DEFINED IFF
        # `0 <= i < len(s)`, `at`'s own bound. Not currently reached by
        # `_cert_stmts`/`_cert_cexpr` (neither renders a seq-typed
        # assignment's C text; see the seq value machinery section), kept
        # here only so `_cev` itself stays a complete, honest ground
        # semantics for every t operator, the same reason `at` is here at
        # all rather than only where it happens to be used today.
        s, i, v = (_cev(args[0], st), _cev(args[1], st), _cev(args[2], st))
        if not 0 <= i < len(s):
            raise _CertSkip("undefined update in replay")
        return s[:i] + [v] + s[i + 1:]
    if op == "fill":
        n, v = _cev(args[0], st), _cev(args[1], st)
        if n < 0:
            raise _CertSkip("undefined fill in replay")
        return [v] * n
    if op == "pair":
        # SPEC.md "Pairs" (2026-09-10): a pair value, defined iff both
        # components are (both already evaluated above by the time this
        # line runs). Represented as a plain 2-element Python list, the
        # SAME shape `interp.py`'s own `_j` gives a witness's pair value
        # (`[a, b]`, never `interp.Pair`, so `_tty` below can compare a
        # replayed pair straight against `w["_twin"]` with no conversion
        # step) -- distinct in practice from a seq value only because the
        # two are never compared against each other here (a task's
        # RETURN type, fixed before any replay starts, already says which
        # one `st[ret]` must be).
        return [_cev(args[0], st), _cev(args[1], st)]
    if op in ("fst", "snd"):
        p = _cev(args[0], st)
        return p[0 if op == "fst" else 1]
    if op in DIVMOD:
        # SPEC.md Euclidean div/mod, same ground formula as interp.py: the
        # Python `%` with an absolute-value modulus already returns the
        # Euclidean remainder (always in [0, |y|)), so the quotient falls
        # out of the division law exactly.
        x, y = _cev(args[0], st), _cev(args[1], st)
        if y == 0:
            raise _CertSkip(f"undefined {op} in replay")
        r = x % abs(y)
        return r if op == "mod" else (x - r) // y
    if op == "neg":
        return -_cev(args[0], st)
    if op == "not":
        return not _cev(args[0], st)
    if op == "and":
        return all(_cev(a, st) for a in args)
    if op == "or":
        return any(_cev(a, st) for a in args)
    if op == "implies":
        return (not _cev(args[0], st)) or _cev(args[1], st)
    if op in ARITH:
        a, b = _cev(args[0], st), _cev(args[1], st)
        return {"+": a + b, "-": a - b, "*": a * b}[op]
    if op in CMP:
        a, b = _cev(args[0], st), _cev(args[1], st)
        return {"==": a == b, "!=": a != b, "<": a < b, "<=": a <= b,
                ">": a > b, ">=": a >= b}[op]
    raise _CertSkip(f"no ground evaluation for operator {op!r}")


def _cert_cexpr(e: dict, ctx: Ctx, st: dict, funs: dict, name: str,
                asserts: list, ind: str) -> str:
    """cexpr(), specialized for the certificate replay: every `div`/`mod`
    is rendered branch-free (no C ternary), the ground-decided condition
    going to `asserts` instead.

    Measured 2026-09-08 on remainder's wrong-var twin (x -> y makes the
    mod `y % y`, always 0): cexpr()'s ternary form for div/mod put a live
    `?:` in the certificate function, and -wp-smoke-dead-local-init flagged
    its now-unreachable positive-remainder arm as dead code
    (typed_nat_t_certificate_wp_smoke_dead_code_s24/s25). Ordinary dead
    code in a t function is fine (`_all_obligations_proved` subtracts smoke
    tallies), but the certificate's OWN audit (`_cert_status`) requires
    every goal of its enclosing function proved with no such exemption, so
    a live ternary there can never mint, only fail (the certificate
    section docstring's branch discipline, now extended to div/mod). The
    fix mirrors how `if`/`while` are unrolled: resolve the ternary at the
    ground state, assert the resolved condition (a real, Qed-checked goal,
    not an assumption), and emit only the taken arm.

    BRANCH-FREE AND/OR, added 2026-09-10 (second pass), the SAME doomed-
    smoke shape as div/mod's own case above, found on two lifted tasks
    (hasOppositeSign, isMonthWith30Days, both a straight-line ground `&&`/
    `||` of plain comparisons, no loop, no div/mod at all): once every
    name is ground, one operand can decide the whole expression outright
    (`a=0` makes `a <= 0` Qed-true, so `&&`'s right operand's evaluation
    reads DOOMED by -wp-smoke-tests exactly as a live div/mod ternary arm
    did), and `_cert_status`'s audit has no exemption for a doomed smoke
    goal inside the certificate function itself (the SAME
    verifiers/framac.py gap the PAIRS section's own `fz_p_pair_eq` note
    names as general, not this file's alone to close, and which THAT
    construct's own componentwise `==` rewrite already worked around the
    same way here: bitwise `&`/`|` on two already-0/1 values gives WP no
    branch to find dead). Gated by `_has_partial_op`, not applied
    unconditionally: the general `and`/`or` case (`code_ats`'s own
    conditionally-evaluated-`at`/`div` discipline, the WHILE-GUARD
    DEFINEDNESS and pairs-residual notes elsewhere in this file) is
    load-bearing precisely when a later operand's definedness depends on
    an earlier one's truth (`i < len(s) and at(s, i) > 0`), so this only
    fires when NEITHER operand contains an `at`/`div`/`mod`/`update`/
    `fill`/call -- both hasOppositeSign and isMonthWith30Days qualify
    (pure comparisons over ground ints), and no committed or previously-
    measured lifted task loses its short-circuit here, since one
    containing a partial operator anywhere falls through to the ordinary
    path below unchanged."""
    if e.get("op") in ("and", "or") and not _has_partial_op(e):
        a_c = _cert_cexpr(e["args"][0], ctx, st, funs, name, asserts, ind)
        b_c = _cert_cexpr(e["args"][1], ctx, st, funs, name, asserts, ind)
        return f"(({a_c}) {'&' if e['op'] == 'and' else '|'} ({b_c}))"
    if not _has_divmod(e):
        return cexpr(e, ctx.env, funs, name)
    if "ite" in e:
        raise _CertSkip("`ite` in executable position within the "
                        "certificate replay")
    if "call" in e:
        raise _CertSkip("call in executable position within the "
                        "certificate replay")
    op, args = e["op"], e.get("args", [])
    if op in DIVMOD:
        x_e, y_e = args
        xc = _cert_cexpr(x_e, ctx, st, funs, name, asserts, ind)
        yc = _cert_cexpr(y_e, ctx, st, funs, name, asserts, ind)
        xv, yv = _cev(x_e, st), _cev(y_e, st)
        if yv == 0:
            raise _CertSkip(f"undefined {op} in replay")
        qv = abs(xv) // abs(yv)
        if (xv < 0) != (yv < 0):
            qv = -qv
        rv = xv - qv * yv                       # C-truncating remainder
        rem = f"(({xc}) % ({yc}))"
        neg = rv < 0
        asserts.append(f"{ind}/*@ assert {rem} {'<' if neg else '>='} 0; */")
        if op == "mod":
            if not neg:
                return rem
            ysign_neg = yv < 0
            asserts.append(f"{ind}/*@ assert ({yc}) "
                           f"{'<' if ysign_neg else '>'} 0; */")
            return f"({rem} + ({f'-({yc})' if ysign_neg else yc}))"
        quo = f"(({xc}) / ({yc}))"
        if not neg:
            return quo
        ysign_pos = yv > 0
        asserts.append(f"{ind}/*@ assert ({yc}) "
                       f"{'>' if ysign_pos else '<'} 0; */")
        return f"({quo} - ({'1' if ysign_pos else '-1'}))"
    if op == "len":
        a0 = args[0]
        if a0.get("op") == "at":
            # `len(m[i])` inside a certificate replay (`row_max_len`'s
            # own exit-witness twin, see `_exit_certificate`'s nested-seq
            # declarations below): the same offsets-array formula
            # `cexpr()`'s matching case renders, threaded through
            # `_cert_cexpr` so a `div`/`mod` nested inside the row index
            # still resolves branch-free at every level (mirrors why
            # `_div_style` itself threads recursively, PAIRS section
            # above).
            base, idx = a0["args"]
            m = seq_var(base, ctx.env)
            i = _cert_cexpr(idx, ctx, st, funs, name, asserts, ind)
            return f"({m}_off[({i}) + 1] - {m}_off[({i})])"
        return f"{seq_var(a0, ctx.env)}_n"
    if op == "at":
        base = args[0]
        if is_nested_seq_type(typ(base, ctx.env, funs)):
            raise _CertSkip(
                "nested seq (seq<seq>) `at` reaching certificate replay "
                "directly (not wrapped in `len`)")
        return (f"{seq_var(base, ctx.env)}"
                f"[{_cert_cexpr(args[1], ctx, st, funs, name, asserts, ind)}]")
    if op == "pair":
        # divmod_pair's own case: `pair(div(x, y), mod(x, y))` has a
        # `div`/`mod` node nested inside it, so this branch (not
        # `cexpr()`'s, taken only when `_has_divmod(e)` is false) is what
        # actually renders it during certificate replay; same struct
        # compound literal `cexpr()`'s own "pair" case builds, ground-
        # decided component text threaded through instead.
        t1 = typ(args[0], ctx.env, funs)
        t2 = typ(args[1], ctx.env, funs)
        sname = _pair_struct_name(t1, t2)
        a_c = _cert_cexpr(args[0], ctx, st, funs, name, asserts, ind)
        b_c = _cert_cexpr(args[1], ctx, st, funs, name, asserts, ind)
        return f"(struct {sname}){{{a_c}, {b_c}}}"
    if op in ("fst", "snd"):
        field = "a" if op == "fst" else "b"
        return f"({_cert_cexpr(args[0], ctx, st, funs, name, asserts, ind)}).{field}"
    if op == "neg":
        sub = _cert_cexpr(args[0], ctx, st, funs, name, asserts, ind)
        return f"(-{_gap(sub)})"
    if op == "not":
        sub = _cert_cexpr(args[0], ctx, st, funs, name, asserts, ind)
        return f"(!{sub})"
    if op == "implies":
        a, b = (_cert_cexpr(x, ctx, st, funs, name, asserts, ind)
                for x in args)
        return f"((!({a})) || ({b}))"
    if op in ("and", "or"):
        glue = " && " if op == "and" else " || "
        return "(" + glue.join(_cert_cexpr(a, ctx, st, funs, name, asserts,
                                           ind) for a in args) + ")"
    if op in ARITH or op in CMP:
        o = ARITH.get(op) or CMP[op]
        a = _cert_cexpr(args[0], ctx, st, funs, name, asserts, ind)
        b = _cert_cexpr(args[1], ctx, st, funs, name, asserts, ind)
        return f"({a} {o} {b})"
    raise ValueError(f"t has no operator {op!r}")


def _cert_stmts(body: list, ctx: Ctx, st: dict, name: str,
                out: list, count: list) -> tuple:
    """Branch-free replay of `body` at state `st`: straight-line C plus one
    assert per branch decision. Locals are predeclared by the caller, so a
    `var` statement lands as a plain assignment (an unrolled loop iteration
    would otherwise redeclare it).

    Returns `(ctx, stopped)`. `stopped` is True once a `return` (SPEC.md
    "Early exit", 2026-09-08) has been replayed: `st` already holds the
    exact final ground values interp.py would compute (the replay is
    concrete, so nothing after a return can change them, the same fact
    that lets check_wf refuse a statement after one), so this function
    simply stops emitting C for the rest of `body` and every enclosing
    caller propagates the flag and stops too, rather than emitting a
    literal C `return` inside the certificate (which stays `void` and
    reaches its closing assert unconditionally either way)."""
    ind = "  "
    for s in body:
        count[0] += 1
        if count[0] > MAX_CERT_STMTS:
            raise _CertSkip("replay exceeds the statement cap")
        if "assign" in s:
            n, e = s["assign"]
            out += at_asserts(e, ctx, ind)
            dm_asserts: list = []
            rhs = _cert_cexpr(e, ctx, st, ctx.funs, name, dm_asserts, ind)
            out += dm_asserts
            out.append(f"{ind}{n} = {rhs};")
            st[n] = _cev(e, st)
        elif "return" in s:
            n, e = s["return"]
            out += at_asserts(e, ctx, ind)
            dm_asserts: list = []
            rhs = _cert_cexpr(e, ctx, st, ctx.funs, name, dm_asserts, ind)
            out += dm_asserts
            out.append(f"{ind}{n} = {rhs};")
            st[n] = _cev(e, st)
            return ctx, True
        elif "var" in s:
            v = s["var"]
            out += at_asserts(v["init"], ctx, ind)
            ctx = ctx.bind(v["name"], v["type"])
            dm_asserts: list = []
            rhs = _cert_cexpr(v["init"], ctx, st, ctx.funs, name,
                              dm_asserts, ind)
            out += dm_asserts
            out.append(f"{ind}{v['name']} = {rhs};")
            st[v["name"]] = _cev(v["init"], st)
        elif "if" in s:
            c = s["if"]
            out += at_asserts(c["cond"], ctx, ind)
            g = pred(c["cond"], ctx)
            taken = _cev(c["cond"], st)
            out.append(f"{ind}/*@ assert {g if taken else f'(!{g})'}; */")
            ctx, stopped = _cert_stmts(c["then"] if taken else c["else"],
                                       ctx, st, name, out, count)
            if stopped:
                return ctx, True
        elif "while" in s:
            # WHILE-GUARD DEFINEDNESS (2026-09-09, see `stmts()`'s own
            # `while` case for the full note): this replay is already fully
            # UNROLLED (each concrete pass through the Python loop below is
            # one literal guard re-evaluation in the emitted straight-line
            # C), so, unlike `stmts()`, there is no ambiguity about
            # "before the loop" vs. "top of the body" -- `at_asserts` goes
            # immediately before EVERY concrete evaluation of `w["cond"]`,
            # the continuation checks and the final exit check alike, each
            # discharged from exactly the accumulated state at that point
            # (the same discipline `assign`/`return`/`if` already use
            # above). No `code_ats`-driven refusal is needed any more: a
            # divisor that could concretely be zero, or an index that could
            # concretely leave bounds, now fails at its own `at_asserts`
            # line rather than skipping the whole certificate.
            w = s["while"]
            g = pred(w["cond"], ctx)
            stopped = False
            while True:
                out += at_asserts(w["cond"], ctx, ind)
                if not _cev(w["cond"], st):
                    out.append(f"{ind}/*@ assert (!{g}); */")
                    break
                count[0] += 1
                if count[0] > MAX_CERT_STMTS:
                    raise _CertSkip("replay exceeds the statement cap")
                out.append(f"{ind}/*@ assert {g}; */")
                ctx, stopped = _cert_stmts(w["body"], ctx, st, name, out,
                                           count)
                if stopped:
                    break
            if stopped:
                return ctx, True
        else:
            raise _CertSkip(f"no replay for statement {s!r}")
    return ctx, False


def _tty(v):
    """Value tagged with its t type (bool is not int; interp._tv precedent,
    restated locally so this file keeps importing nothing of interp's).

    "pair", added 2026-09-10 (SPEC.md "Pairs"): `_cev`'s own "pair" case
    (above) and a witness's `_twin`/`_real` (`interp._j`'s rendering) both
    give a pair value as a plain 2-element list, so tagging any `list`
    this way is enough to compare them -- no seq value ever reaches this
    function alongside one (a seq-returning task is excluded from
    `_value_certificate` before either side of the comparison is built,
    unchanged by this construct)."""
    if isinstance(v, bool):
        return ("bool", v)
    if isinstance(v, list):
        return ("pair", v)
    return ("int", v)


def _value_certificate(task: dict, twin_body: list, w: dict,
                       env: dict, funs: dict, used: set) -> str | None:
    """The VALUE-kind certificate function's source text, or None with the
    reason left to the caller's honesty: only a certifiable witness earns
    one. Unchanged by the 2026-09-09 seq construct: neither committed task
    of that wave reaches this branch (swap's witness is `undefined`,
    reverse's is `exit`), and a seq-typed RETURN still refuses here rather
    than emit the plain `int {n};` this function's OWN decls would give it
    (wrong for a pointer+length pair) -- a documented gap, not a silent
    one, matching RULES ("measure before designing"): fixing it needs its
    own measured probe this construct wave did not need.

    PAIRS, extended 2026-09-10: `divmod_pair`'s own `wrong-var` twin IS a
    value witness (loop-free, so the whole function is one straight-line
    replay) and IS how that task counts (framac has no other route to
    REFUTED here; the twin's own contract just times out otherwise, the
    same shape every other value-changing twin in AGREEMENT.md has). A
    pair-typed return's witness value is a 2-element list (`interp._j`'s
    rendering, restated as `_tty`'s new "pair" tag above), never a bare
    bool/int, so the ground-replay gate below now accepts EITHER shape
    and the return-and-locals declaration loop declares the struct type
    for `ret` specifically (every other declared name -- params, other
    locals -- is still a plain `int`, unaffected)."""
    if w.get("_kind") != "value" or w.get("_ens") is not True:
        return None                    # loop-state or non-falsifying witness
    ret, rett = task["returns"][0]["name"], task["returns"][0]["type"]
    is_pair = isinstance(rett, dict) and "pair" in rett
    # SEQ RETURN, closed 2026-09-11 (fz_p_seqeq_false, ROADMAP 13.4): the
    # gap this docstring named above is a REPLAY gap, not a certificate
    # one -- `_cert_stmts` renders every "assign"/"var" as a plain scalar
    # `n = rhs;`, wrong C for a seq-typed name (an array cannot be
    # assigned by name), so a seq return was refused wholesale rather
    # than emitted unsoundly. But the VALUE witness's `_twin` is already
    # the REAL body's own trusted final value (computed by interp.py's
    # bounded scan, harness.real_witness, independent of this file
    # entirely), so nothing here needs to RE-DERIVE it by replaying the
    # body at all: declaring `r` as a concrete backing array straight
    # from the witness (the exact shape a seq PARAM's witness already
    # gets a few lines below, and `_exit_certificate`'s own seq-local
    # case) and asserting the negated `ensures` at those ground values is
    # a strictly smaller, still-sound certificate -- the replay steps
    # this skips were never load-bearing for the FINAL assert, only for
    # deriving a value this witness already carries.
    is_seq_ret = rett == "seq"
    twin_val = w.get("_twin")
    if is_pair:
        if not (isinstance(twin_val, list) and len(twin_val) == 2
               and all(isinstance(x, (bool, int)) for x in twin_val)):
            return None                # e.g. a pair with a seq component
    elif is_seq_ret:
        if not (isinstance(twin_val, list)
               and all(isinstance(x, int) and not isinstance(x, bool)
                       for x in twin_val)):
            return None                # a bool-seq or non-ground value
    elif not isinstance(twin_val, (bool, int)):
        return None                    # no-value twins have no ground replay
    if CERT_FN in used or CERT_GOAL in used:
        return None                    # a task name would collide or forge
    struct_name = None
    if is_pair:
        try:
            struct_name = _pair_struct_name(*rett["pair"])
        except NotImplementedError:
            return None                # a pair-of-seq return, refused
    st, decls = {}, []
    try:
        for p in task["params"]:
            if p["name"] not in w:
                return None
            v = w[p["name"]]
            if p["type"] == "seq":
                # ACSL has no implicit array-to-pointer conversion
                # (measured: a logic call over a local array is refused as
                # annot-error), so the array gets a fresh backing name and
                # the seq name is bound as the pointer, exactly the shape
                # the twin function's own parameter has.
                arr = f"t_cert_{p['name']}"
                if arr in used:
                    return None
                vals = [int(x) for x in v]
                init = ", ".join(_int_lit(x) for x in vals) or "0"
                decls.append(f"  int {arr}[{max(len(vals), 1)}] = "
                             f"{{{init}}};")
                decls.append(f"  int *{p['name']} = {arr};")
                decls.append(f"  int {p['name']}_n = {len(vals)};")
                st[p["name"]] = vals
            elif is_nested_seq_type(p["type"]):
                # NESTED SEQ PARAM, added 2026-09-12 (ROADMAP 16.2,
                # framac-cert, task 792 countLists): the flat
                # data+offsets pair `lower()`'s own `cparams` loop
                # already gives this parameter in the twin's C signature
                # (THE ENCODING, same file, `is_nested_seq_type` branch
                # a few thousand lines below -- read, not edited, here),
                # so a witness's row list is declared the identical way:
                # `_off` holds `n+1` cumulative row-length prefixes
                # (`_off[0] == 0`, `_off[i+1] - _off[i]` row i's length,
                # matching `_seq_len_render`'s own nested "at" formula),
                # `_data` the rows flattened in order. `st[p['name']]`
                # stays the RAW row list (`_cev`'s "len" case just calls
                # Python `len()` on it for `len(lists)`, the only nested-
                # seq operator this task's straight-line replay needs;
                # a task reading an actual ROW's own cells would need
                # more, left untried since nothing measured needs it).
                if not (isinstance(v, list)
                       and all(isinstance(r, list) for r in v)):
                    return None            # not a ground row-list witness
                data_arr = f"t_cert_{p['name']}_data"
                off_arr = f"t_cert_{p['name']}_off"
                if data_arr in used or off_arr in used:
                    return None
                flat: list = []
                offs = [0]
                for row in v:
                    flat.extend(int(x) for x in row)
                    offs.append(len(flat))
                data_init = ", ".join(_int_lit(x) for x in flat) or "0"
                off_init = ", ".join(_int_lit(x) for x in offs)
                decls.append(f"  int {data_arr}[{max(len(flat), 1)}] = "
                             f"{{{data_init}}};")
                decls.append(f"  int *{p['name']}_data = {data_arr};")
                decls.append(f"  int {off_arr}[{len(offs)}] = "
                             f"{{{off_init}}};")
                decls.append(f"  int *{p['name']}_off = {off_arr};")
                decls.append(f"  int {p['name']}_n = {len(v)};")
                st[p["name"]] = v
            elif isinstance(p["type"], dict) and "pair" in p["type"]:
                # PAIRS, extended 2026-09-10 (the parameter fix above
                # `_pair_field_c`): a pair-typed PARAMETER's witness
                # value is a 2-element list, the exact shape a pair-typed
                # RETURN's own witness already has (`_tty`'s "pair" tag
                # above; `interp._j`'s rendering for either). Declared as
                # a ground struct-by-value local via a compound literal,
                # the same construction `cexpr()`'s own "pair" case
                # builds for the REAL/twin bodies. Before this branch, a
                # pair-typed param fell into the plain `else` below and
                # tried to format a 2-element LIST as a C `int`
                # initializer -- never reached by `divmod_pair`/`min_max`
                # (neither has a pair-typed param), so this is a gap this
                # fix closes rather than a regression it introduces.
                if not (isinstance(v, list) and len(v) == 2):
                    return None            # not a ground pair witness
                try:
                    psname = _pair_struct_name(*p["type"]["pair"])
                except NotImplementedError:
                    return None            # a pair-of-seq param, refused
                a0 = int(v[0]) if isinstance(v[0], bool) else v[0]
                b0 = int(v[1]) if isinstance(v[1], bool) else v[1]
                decls.append(f"  struct {psname} {p['name']} = "
                             f"(struct {psname}){{{a0}, {b0}}};")
                st[p["name"]] = v
            else:
                decls.append(f"  int {p['name']} = {_int_lit(int(v))};")
                st[p["name"]] = v
        body_out: list = []
        if is_seq_ret:
            # No replay (see the note above `is_seq_ret`): declare `ret`
            # as a concrete backing array straight from the trusted
            # witness value, the same arr+pointer+length shape a seq
            # PARAM's witness gets above.
            arr = f"t_cert_{ret}"
            if arr in used or f"{ret}_n" in used:
                return None
            r_vals = [int(x) for x in twin_val]
            init = ", ".join(_int_lit(x) for x in r_vals) or "0"
            decls.append(f"  int {arr}[{max(len(r_vals), 1)}] = "
                         f"{{{init}}};")
            decls.append(f"  int *{ret} = {arr};")
            decls.append(f"  int {ret}_n = {len(r_vals)};")
            st[ret] = r_vals
        else:
            _, dec = assigned_names(twin_body)
            names = [ret] + [d for d in dec if d != ret]
            if len(set(dec)) != len(dec) or set(dec) & set(st):
                return None            # flattening scopes would collide
            decls += [f"  {'struct ' + struct_name if is_pair and n == ret else 'int'}"
                     f" {n};" for n in names]
            _cert_stmts(twin_body, Ctx(env, funs, ret=None, label="Here"),
                        st, task["name"], body_out, [0])
            if _tty(st.get(ret)) != _tty(w["_twin"]):
                return None            # replay disagrees with the witness
    except (_CertSkip, NotImplementedError, ValueError, KeyError,
            TypeError, RecursionError):
        return None
    ctx = Ctx(env, funs, ret=None, label="Here")
    pieces = []
    for e in task["ensures"]:
        d, p = defs(e, ctx), pred(e, ctx)
        pieces.append(f"({p})" if d is None else f"((({d}) && ({p})))")
    lines = ["", "/*@ assigns \\nothing; */",
             f"void {CERT_FN}(void) {{", *decls, *body_out,
             f"  /*@ assert {CERT_GOAL}: !({' && '.join(pieces)}); */",
             "  return;", "}", ""]
    return "\n".join(lines)


# ---------------------------------------- definedness, as a t formula -----
#
# `defs()` (above, ACSL section) renders SPEC.md's definedness rule to ACSL
# text. `_undef_certificate` (below) needs the SAME rule as a t Expr
# instead, so `interp.ev` can DECIDE it at a ground witness state before
# any ACSL exists to check it against: one rule, two renderings, never two
# readings of what "defined" means.

def _t_and(parts):
    parts = [p for p in parts if p is not None]
    if not parts:
        return None
    r = parts[0]
    for p in parts[1:]:
        r = {"op": "and", "args": [r, p]}
    return r


def defs_t(e: dict):
    """`defs()`'s rule, restated as a t Expr (or None, trivially defined)
    instead of ACSL text. Mirrors `defs()` case for case; a `call` or
    quantifier inside an EXECUTABLE expression cannot occur (v1's grammar
    keeps both out of executable position, `code_ats` already assumes
    it), so unlike `defs()` (which also serves quantifier/call-carrying
    SPEC positions) this only needs the executable-expression subset."""
    if "int" in e or "bool" in e or "var" in e:
        return None
    if "ite" in e:
        i = e["ite"]
        dt, de = defs_t(i["then"]), defs_t(i["else"])
        return _t_and([defs_t(i["cond"]),
                       None if dt is None else
                       {"op": "implies", "args": [i["cond"], dt]},
                       None if de is None else
                       {"op": "implies",
                        "args": [{"op": "not", "args": [i["cond"]]}, de]}])
    op, args = e["op"], e.get("args", [])
    if op == "at":
        # `s` may itself be a `slice` (2026-09-09, read position: `at`'s
        # own bound is relative to the slice's length, `defs_t(s)` below
        # picking up the slice's OWN domain obligation, `0 <= a <= b <=
        # len(base)`, when it is one; a no-op (`None`) when `s` is the
        # ordinary bare variable).
        s = args[0]
        bound = {"op": "and", "args": [
            {"op": "<=", "args": [{"int": 0}, args[1]]},
            {"op": "<", "args": [args[1], {"op": "len", "args": [s]}]}]}
        return _t_and([defs_t(s), defs_t(args[1]), bound])
    if op == "slice":
        # s[a..b]: DEFINED IFF 0 <= a <= b <= len(s) (SPEC.md "Sequences:
        # literals, concatenation, slices", 2026-09-09), mirroring `defs`
        # ACSL-side case for case.
        s, lo, hi = args
        bound = {"op": "and", "args": [
            {"op": "and", "args": [
                {"op": "<=", "args": [{"int": 0}, lo]},
                {"op": "<=", "args": [lo, hi]}]},
            {"op": "<=", "args": [hi, {"op": "len", "args": [s]}]}]}
        return _t_and([defs_t(lo), defs_t(hi), bound])
    if op == "update":
        s = args[0]
        bound = {"op": "and", "args": [
            {"op": "<=", "args": [{"int": 0}, args[1]]},
            {"op": "<", "args": [args[1], {"op": "len", "args": [s]}]}]}
        return _t_and([defs_t(args[1]), defs_t(args[2]), bound])
    if op == "fill":
        return _t_and([defs_t(args[0]), defs_t(args[1]),
                       {"op": ">=", "args": [args[0], {"int": 0}]}])
    if op in DIVMOD:
        return _t_and([defs_t(args[0]), defs_t(args[1]),
                       {"op": "!=", "args": [args[1], {"int": 0}]}])
    if op in ("and", "or", "implies"):
        acc, guards = [defs_t(args[0])], []
        for k, a in enumerate(args[1:], 1):
            prev = args[k - 1] if op != "implies" else args[0]
            g = prev if op != "or" else {"op": "not", "args": [prev]}
            d = defs_t(a)
            guards.append(g)
            if d is not None:
                gexpr = guards[0]
                for gg in guards[1:]:
                    gexpr = {"op": "and", "args": [gexpr, gg]}
                acc.append({"op": "implies", "args": [gexpr, d]})
        return _t_and(acc)
    return _t_and([defs_t(a) for a in args])


def _undef_certificate(task: dict, twin_body: list, w: dict,
                       env: dict, funs: dict, used: set) -> str | None:
    """The certificate for an `undefined`-kind witness (SPEC.md "Sequences
    as values", 2026-09-09; see the section comment above and
    `lower_verus.py`'s `_undef_obligation`, added the same night for the
    same construct). None when the witness cannot be replayed this way at
    all: an obstacle `interp.ev` cannot get past (a call, budget,
    recursion), a name the witness does not cover, or a body that replays
    to the end without ever finding a false obligation (the witness and
    this walk disagreeing means the witness is not this walk's to
    certify).

    `if` DESCENT, added 2026-09-11 (ROADMAP 13.4, framac-fast): the walk
    used to stop at the body's first `if` ("not walked", the docstring's
    own words for the gap, never exercised because no committed task's
    undefined witness needed it). `fz_p_at_body`'s does: an unguarded `at`
    sits inside a `then`-branch one level deep. The walk now follows the
    branch `interp.ev` actually takes on `w`'s own params, exactly THE
    CERTIFICATE's no-branches discipline (`_cert_stmts`'s own `if` case,
    same ground condition, same `assert cond;`/`assert (!cond);` emitted
    in place of the untaken arm): a mis-decided branch cannot mint anything
    it only fails a false assert under WP, never certifies past it."""
    if w.get("_kind") != "undefined":
        return None
    names = {k: v for k, v in w.items() if not k.startswith("_")}
    # interp.py's own seq representation is a tuple; the witness's JSON
    # gives seqs as lists, so this is the one conversion point, mirrored
    # by `lower_verus.py`'s `_undef_obligation`.
    env_py = {n: (tuple(v) if isinstance(v, list) else v)
              for n, v in names.items()}
    ctx = Ctx(dict(env), funs, ret=None, label="Here")
    code = []
    seq_decls: set = set()   # local (non-param) seq names already given a
                              # C array declaration by the walk below
    # SCALAR RE-DECLARATION BUG, found 2026-09-12 (FRAMAC-NESTED, see
    # `walk`'s own "var"/"assign" branch below for the full note):
    # `declared` tracks every scalar name this certificate has already
    # given a C `int` declaration to (seeded with the task's own params
    # just below, before `walk` ever runs, since those get their `int`
    # declaration from the separate loop right before `walk` is called,
    # not from `walk` itself), so a NAME'S OWN FIRST assignment inside
    # `walk` -- whether that assignment arrives as a "var" statement (a
    # genuinely fresh local) or as an "assign" to the task's RETURN name
    # (never a "var" statement anywhere, `result` here, since v1 gives a
    # function's return name no declaring statement of its own, only
    # `assign`/`return` targets) -- gets the declaring `int` exactly
    # once, and every later assignment to that same name, by either
    # statement kind, gets a plain reassignment. Neither `"var" in s`
    # alone (declares `result` never, the bug this comment's own fix
    # replaces) nor "declare every assign" (redeclares a loop's own
    # reassigned locals, isSublist's own `i_v`/`result` across
    # iterations, the ORIGINAL bug this whole note is about) is right;
    # this set is the one piece of state that answers "have I, this
    # call, already emitted this name's own `int`?" correctly for both.
    declared: set = {p["name"] for p in task["params"]}

    def walk(body: list, ctx: Ctx):
        """(found_undefined_obligation_or_None, ctx). Mutates `env_py` and
        `code` (param/local decls and ground `if`-branch asserts, in
        emission order) as it goes; raises on anything not walked (`while`,
        `return`, a seq-typed intermediate local), caught by the caller
        exactly as the old flat loop's `return None` sites were."""
        for s in body:
            if "var" in s:
                nm, e, ty = s["var"]["name"], s["var"]["init"], s["var"]["type"]
            elif "assign" in s:
                nm, e = s["assign"]
                ty = ctx.env.get(nm)
            elif "if" in s:
                c = s["if"]
                ob = defs_t(c["cond"])
                if ob is not None and not interp.ev(ob, env_py, ifuns, st):
                    return ob, ctx
                taken = interp.ev(c["cond"], env_py, ifuns, st)
                g = pred(c["cond"], ctx)
                code.append(f"  /*@ assert {g if taken else f'(!{g})'}; */")
                found, ctx = walk(c["then"] if taken else c["else"], ctx)
                if found is not None:
                    return found, ctx
                continue
            elif "while" in s:
                # WHILE DESCENT, added 2026-09-12 (ROADMAP 16.2,
                # framac-cert): mirrors the `if` case just above and
                # `_cert_stmts`'s own while-unrolling (2026-09-09) --
                # concrete guard, one `assert`/`assert (!...)` per
                # evaluation, `interp.ev` (not a symbolic walk) deciding
                # which way each iteration goes, so a mis-decided
                # iteration cannot mint anything, only fail a false
                # assert under WP. Traced from task 610 removeElement
                # (t/COVERAGE-lifted-785.md r20): a compare-flip twin's
                # undefined `v[i_v2]` access (`i_v2` reaching `v_n` one
                # pass early) sits inside the loop's OWN body, past the
                # point the old flat walk gave up (`raise ValueError`
                # below, the same "not walked" signal `lower_verus.py`'s
                # `_undef_obligation` docstring named for the identical
                # gap: "loop bodies... not walked"). Capped at
                # `interp.MAX_LOOP` exactly like `interp.exec_body`'s own
                # while case, so a non-terminating replay raises
                # `interp.Budget` (already in the caller's except tuple)
                # rather than looping the certificate builder itself.
                w = s["while"]
                it = 0
                while True:
                    ob = defs_t(w["cond"])
                    if ob is not None and not interp.ev(ob, env_py, ifuns,
                                                        st):
                        return ob, ctx
                    taken = interp.ev(w["cond"], env_py, ifuns, st)
                    g = pred(w["cond"], ctx)
                    code.append(f"  /*@ assert "
                               f"{g if taken else f'(!{g})'}; */")
                    if not taken:
                        break
                    found, ctx = walk(w["body"], ctx)
                    if found is not None:
                        return found, ctx
                    it += 1
                    if it > interp.MAX_LOOP:
                        raise interp.Budget("loop cap")
                continue
            else:
                raise ValueError(f"undef-certificate: statement {s!r} "
                                 "not walked (return)")
            ob = defs_t(e)
            if ob is not None and not interp.ev(ob, env_py, ifuns, st):
                return ob, ctx
            val = interp.ev(e, env_py, ifuns, st)
            if ty == "seq":
                # SEQ-LOCAL DECLARATION, added 2026-09-12 (ROADMAP 16.2,
                # framac-cert, task 610 removeElement): a bare `fill`
                # (fresh buffer) or a self-referential `update` (one
                # element write) is declared/mutated with the SAME plain
                # C `int` array + `_n` length pair a seq PARAM already
                # gets (the loop below this function, `t_cert_<name>` /
                # `<name>` / `<name>_n`) -- what `_seq_len_render`
                # (`pred`'s own "len" case, untouched here) renders
                # `len(<name>)` to is exactly `<name>_n`, so a later
                # obligation naming this local (610's own `0 <= i_v2 &&
                # i_v2 < len(v)`, found INSIDE the while loop below) has
                # something to mean. `fill` declares the array (and its
                # length) once; `update` overwrites one element in place
                # (t's seqs are fixed-length once created, so `_n` is
                # never re-declared). Anything else assigned to a
                # seq-typed name (a slice, a concat, a SECOND independent
                # `fill`) still declines outright, unchanged from the
                # older blanket refusal: re-rendering an arbitrary seq
                # expression mid-walk is the `_cert_stmts` engine's job,
                # not this lighter-weight one's.
                op = e.get("op")
                if nm not in seq_decls:
                    # First sight of this seq-typed name: ANY expression
                    # that reaches here (`fill`, or a bare copy of
                    # another seq like swapFirstAndLast's own `a_out =
                    # a`, SEE NOTE ABOVE -- generalized 2026-09-12 past
                    # `fill` alone once 591/625's own first statement
                    # measured as the identical gap under a different
                    # RHS shape) is declared from `val`, the concrete
                    # tuple `interp.ev` already computed for it, exactly
                    # the way a seq PARAM is declared below.
                    vals = [int(x) for x in val]
                    arr = f"t_cert_{nm}"
                    if arr in used:
                        raise ValueError(f"seq-local cert array {arr!r} "
                                         "collides with a task name")
                    init = ", ".join(_int_lit(x) for x in vals) or "0"
                    code.append(f"  int {arr}[{max(len(vals), 1)}] = "
                               f"{{{init}}};")
                    code.append(f"  int *{nm} = {arr};")
                    code.append(f"  int {nm}_n = {len(vals)};")
                    seq_decls.add(nm)
                elif (op == "update" and nm in seq_decls and
                      e["args"][0].get("var") == nm):
                    idx = interp.ev(e["args"][1], env_py, ifuns, st)
                    new_v = interp.ev(e["args"][2], env_py, ifuns, st)
                    code.append(f"  {nm}[{_int_lit(int(idx))}] = "
                               f"{_int_lit(int(new_v))};")
                else:
                    raise ValueError("seq-typed intermediate local: "
                                     "shape not walked (only a fresh "
                                     "fill or a self-update, see "
                                     "the seq-local declaration note)")
                if "var" in s:
                    ctx = ctx.bind(nm, ty)
                env_py[nm] = val
                continue
            if "var" in s:
                ctx = ctx.bind(nm, ty)
            # SCALAR RE-DECLARATION BUG, found 2026-09-12 (FRAMAC-NESTED,
            # ROADMAP 13.4 item (a); isSublist's own while loop, walked
            # here for the first time once the extensional-equality
            # loop above let this task's framac lowering succeed at
            # all): this used to key off `"var" in s` alone, giving `int
            # {nm} = ...;` to a "var" statement and a bare `{nm} =
            # ...;` to an "assign" -- wrong on BOTH sides of that split.
            # An "assign" to the RETURN name (`result`, never a "var"
            # statement anywhere in v1: a function's return gets no
            # declaring statement of its own) got the bare form on its
            # OWN first assignment, an undeclared-identifier error; an
            # "assign" REASSIGNING a "var" name across loop iterations
            # this replay unrolls (`i_v`, isSublist's own shape) got the
            # `int`-prefixed form every time, a "redefinition of '{nm}'
            # in the same scope" PARSE ERROR (frama-c's own exact
            # message, measured on isSublist's twin certificate) from
            # the second iteration on, since C has no re-`int` inside
            # one block. `declared` (this function's own set, seeded
            # with the task's params before `walk` is ever called) is
            # the one piece of state that actually answers "has THIS
            # NAME been given its own `int` yet by this certificate,
            # regardless of which statement kind first assigned it":
            # declare once, on whichever statement (var or assign) is
            # the name's own first sight, plain-assign every time after.
            if nm not in declared:
                code.append(f"  int {nm} = {_int_lit(int(val))};")
                declared.add(nm)
            else:
                code.append(f"  {nm} = {_int_lit(int(val))};")
            env_py[nm] = val
        return None, ctx

    try:
        for p in task["params"]:
            if p["name"] not in names:
                return None
            v = names[p["name"]]
            if p["type"] == "seq":
                arr = f"t_cert_{p['name']}"
                if arr in used:
                    return None
                vals = [int(x) for x in v]
                init = ", ".join(_int_lit(x) for x in vals) or "0"
                code.append(f"  int {arr}[{max(len(vals), 1)}] = "
                            f"{{{init}}};")
                code.append(f"  int *{p['name']} = {arr};")
                code.append(f"  int {p['name']}_n = {len(vals)};")
            else:
                code.append(f"  int {p['name']} = {_int_lit(int(v))};")
        ifuns = interp.funs_of(task, twin_body)
        st = interp.St()
        found, ctx = walk(twin_body, ctx)
        if found is None:
            return None
    except (interp.Undef, interp.Budget, RecursionError, KeyError,
            ValueError, TypeError):
        return None
    goal = pred({"op": "not", "args": [found]}, ctx)
    lines = ["", "/*@ assigns \\nothing; */",
             f"void {CERT_FN}(void) {{", *code,
             f"  /*@ assert {CERT_GOAL}: {goal}; */",
             "  return;", "}", ""]
    return "\n".join(lines)


def _twin_loop(real_body: list, twin_body: list) -> dict | None:
    """The single `while` (in `twin_body`) whose invariant list the twin
    changed, or None; mirrors `lower_verus.py`'s helper of the same name
    (also added tonight for this construct). `is` identity would be
    truer to intent, but `real_body`/`twin_body` are independent JSON
    trees here (unlike verus's in-process mutation), so equality is what
    is available and what INVARIANT-DROP's own edit (delete one entry
    from one loop's `invariants` list, nothing else) makes sufficient."""
    diffs: list = []

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


def _loop_suffix(body: list, loop: dict) -> list | None:
    """`body[i:]` where `body[i]["while"] is loop`, i.e. the mutated loop
    plus everything after it in the SAME block, ready to hand to
    `_cert_stmts`. None when `loop` is not a top-level statement of
    `body`: a loop nested under an `if` needs `interp.continuation`'s own
    search for what runs after it, which no committed task's exit witness
    has needed (reverse's loop is the whole method), so it is a stated
    scope limit rather than an attempted, unmeasured generalisation."""
    for i, s in enumerate(body):
        if "while" in s and s["while"] is loop:
            return body[i:]
    return None


_INT32_MIN, _INT32_MAX = -2147483648, 2147483647


def _int_lit(n: int) -> str:
    """A C integer-constant EXPRESSION guaranteed to evaluate (under
    WP's mathematical, non-`-wp-rte` arithmetic, THE SEMANTIC LINE above)
    to exactly `n`, for `n` a plain Python int of any size. Added
    2026-09-10 (THE INT-LITERAL GATE, below). A bare `str(n)` is correct
    and unchanged for `n` in `int`'s own 32-bit range; outside it, a raw
    decimal token is unsafe REGARDLESS of WP's math model, because a
    literal that does not fit `int` is a C FRONT-END typing fact (the
    literal is typed as the next integer type that fits, `long` here,
    before WP ever sees an expression to reason about mathematically),
    and initializing an `int` from it goes through an implicit narrowing
    conversion Frama-C's own normalization does not treat as the identity
    (MEASURED, probe2.c: `int j = 2147483648;` with `ensures \\result ==
    2147483648` scores `[Stepout]` on the goal `typed_nat_..._ensures`,
    the exact shape that read the two lifted `main_v` tasks' certificates
    UNPROVED, `typed_nat_t_certificate_assert`). The fix decomposes `n`
    into a sum/difference of in-range literals instead: `2147483647 + 1`
    for `n = 2147483648`, MEASURED (same probe, same `ensures`) to score
    `4 / 4`, Qed -- an ordinary C `+` expression carries no such front-end
    typing restriction, and WP's own arithmetic on it is exactly the
    mathematical rule THE SEMANTIC LINE already documents. Recursive so
    no single step's magnitude ever needs to exceed `INT32_MAX`."""
    if _INT32_MIN <= n <= _INT32_MAX:
        return str(n)
    if n > _INT32_MAX:
        return f"({_INT32_MAX} + ({_int_lit(n - _INT32_MAX)}))"
    return f"({_INT32_MIN} - ({_int_lit(_INT32_MIN - n)}))"


def _cert_ground_len(e: dict, w: dict):
    """Ground-evaluate a length Expr in the shape `_expr_seq_len`/
    `_seq_len_track` produce (`len(var)`, an `int` literal, or `+`/`-` of
    such) against a witness dict, or None when a leaf name is not in `w`
    (or not a list there). Used only by THE BUFFER-LENGTH GATE below to
    check a witness against the C encoding's own pinned length, never to
    render anything."""
    if "int" in e:
        return e["int"]
    op = e.get("op")
    if op == "len":
        v = e["args"][0]
        if "var" in v:
            val = w.get(v["var"])
            return len(val) if isinstance(val, list) else None
        return None
    if op in ("+", "-") and "args" in e:
        a = _cert_ground_len(e["args"][0], w)
        b = _cert_ground_len(e["args"][1], w)
        if a is None or b is None:
            return None
        return a + b if op == "+" else a - b
    return None


def _exit_certificate(task: dict, twin_body: list, w: dict,
                      env: dict, funs: dict, used: set) -> str | None:
    """The certificate for an `exit`-kind witness (`interp.invariant_
    witness`'s own obligation, restated: the surviving invariants and
    `requires` hold, the loop guard is false, but `ensures` is false).
    Unlike a `value` witness this state is not reached by running the
    function from its params (`_Admissible` screens for states a sound
    kernel cannot rule out, not for states an actual run passes through),
    so it is declared directly as ground C locals for every name the
    witness names -- params AND loop-scope locals alike, the identical
    declare-a-ground-array-or-int shape `_value_certificate` already uses
    for params -- and `_cert_stmts` (unmodified) replays only the twin's
    mutated loop onward. See `_loop_suffix` for the one scope limit
    (top-level loops only).

    THE BUFFER-LENGTH GATE, added 2026-09-10. A seq RETURN's length is not
    loop state in this C encoding (THE ENCODING, above `assigned_names`):
    EXACT mode pins `requires {ret}_n == <len-expr over params>` ONCE, at
    call entry, so `{ret}_n` cannot vary across the function body at all,
    let alone across one loop's iterations. `interp.invariant_witness`
    does not know this -- it works over t's own AST, where `len(ret)` is
    an ordinary piece of loop state exactly as droppable as any other
    invariant conjunct -- so when the dropped invariant is (or implies) a
    length-equality fact, the ladder can return an `exit` witness whose
    seq-return length disagrees with the params' own pinned length (
    MEASURED on six lifted tasks, all fill/self-update seq returns, e.g.
    double_array_elements: `s=[0]` but the witness's `s_out=[]`, i.e.
    `s_out_n=0` against the encoding's own `requires s_out_n == s_n == 1`).
    Declaring that witness as ground C locals (the plain path below) is
    not merely imprecise, it is UNSOUND: the resulting `s_out_n` never
    varies with the loop's own guard in the real function AT ALL, so
    `ensures {ret}_n == <len-expr>` is provable from `requires` alone,
    independent of whatever loop invariant was dropped -- the WHOLE
    twin's own contract then verifies in full alongside the certificate,
    and `verifiers/framac.py`'s coherence gate correctly refuses to mint
    REFUTED from two accepted contradictions, reading the file MALFORMED
    instead (measured: all six read `39/39` goals proved, certificate
    accepted, MALFORMED). This is not this backend's bug to paper over by
    forcing `{ret}_n` to match the pinned length instead: doing so was
    tried, and it makes the certificate's own final assert UNPROVABLE
    (once length is forced consistent, the surviving content invariants
    plus `requires` already entail `ensures` at every admissible exit,
    for every task measured), moving the cell to `verified / unproved`,
    not `verified / refuted` -- because REFUTED is genuinely, structurally
    unreachable here: a mutation that only the LENGTH invariant's C
    rendering can express, and that rendering is a `requires`-time
    constant, is a NO-OP mutation at the C level, same shape as the
    `preservation` witness kind's own already-documented gap (see the
    section note above). So this gate does the honest thing instead:
    check the witness's seq-RETURN length against the SAME `_seq_len_
    track` computation `lower()` uses to pin `requires {ret}_n == ...`,
    and DECLINE (return None, the same signal every other unbuildable
    certificate in this file already uses) the moment they disagree,
    rather than emit a certificate `verifiers/framac.py` can only read as
    MALFORMED. A decline here means no certificate function is added at
    all, and the twin file the caller already had before this gate
    (identical real/twin C, one dropped loop-invariant line) is exactly
    what MEASURED as fully VERIFIED on all six tasks: the honest reading
    becomes `verified / verified` ("the twin is broken on this witness
    and the kernel accepted it anyway" is not even true here -- the
    kernel is RIGHT that the twin verifies, because at the C level it
    really does compute what the real function computes; the twin's own
    weakness is invisible to this encoding), moving the cell out of
    MALFORMED without pretending to a REFUTED this gate cannot honestly
    back. CAPACITY mode (`ret` absent from `_seq_len_track`'s own `lens`,
    filter_pos's own shape) is untouched: its length IS real loop state
    (a fresh local, `ctx.seq_len`), so an `exit` witness disagreeing with
    it is exactly the kind of thing this gate exists to let through, and
    filter_pos's own committed `verified / refuted` cell (byte-identical
    C, diffed) confirms this branch never fires for it."""
    if w.get("_kind") != "exit":
        return None
    if CERT_FN in used or CERT_GOAL in used:
        return None
    loop = _twin_loop(task["body"], twin_body)
    if loop is None:
        return None
    suffix = _loop_suffix(twin_body, loop)
    if suffix is None:
        return None
    names = {k: v for k, v in w.items() if not k.startswith("_")}
    ret0 = task["returns"][0]
    # THE TRACKED-LENGTH ENCODING (2026-09-10, second pass, see the note
    # in `lower()` above `assigned_names`): the gate below exists because
    # in PLAIN EXACT mode `{ret}_n` is a `requires`-pinned constant, so a
    # witness whose seq-return length disagrees with it cannot be
    # declared as ground C without contradicting the twin's OWN
    # `requires`-derivable `ensures {ret}_n == ...`, which is exactly the
    # coherence conflict THE BUFFER-LENGTH GATE was written to avoid.
    # TRACKED-EXACT mode removes the conflict at its root: `lower()`
    # routes `len(ret)` through a loop-tracked local (`ctx.seq_len`) for
    # precisely this shape, so the twin's own `ensures` is no longer
    # `requires`-derivable at all (MEASURED, the hand probe cited in
    # `lower()`'s own note: the twin's `ensures` and two invariant-
    # preservation goals read [Stepout]) -- there is no longer a second,
    # contradictory proof of the twin's contract for a certificate to
    # collide with, so the decline below is skipped for exactly this
    # shape, `_ret_written_in_loop` mirroring `lower()`'s own test.
    if ret0["type"] == "seq" and ret0["name"] in names \
            and isinstance(names[ret0["name"]], list) \
            and not _ret_written_in_loop(twin_body, ret0["name"]):
        lens = {p["name"]: {"op": "len", "args": [{"var": p["name"]}]}
                for p in task["params"] if p["type"] == "seq"}
        _seq_len_track(twin_body, lens)
        pinned = lens.get(ret0["name"])
        if pinned is not None:
            want = _cert_ground_len(pinned, names)
            if want is not None and want != len(names[ret0["name"]]):
                return None            # THE BUFFER-LENGTH GATE, see above
    ctx_env = dict(env)
    decls, st = [], {}
    for n, v in names.items():
        if f"t_cert_{n}" in used:
            return None
        if is_nested_seq_type(env.get(n)):
            # NESTED SEQ WITNESS, added 2026-09-10 (SPEC.md "Nested
            # sequences"): `row_max_len`'s own invariant-drop twin (exit
            # entailment at `m = [[], [0]]`). The witness's nested value
            # is a ground Python list of lists (`interp._j`'s rendering,
            # the same shape `_cev`'s own "at"/"len" cases already handle
            # generically -- no `_cev` change was needed for this
            # construct, only its DECLARATION here); this declares it the
            # SAME WAY the real/twin C bodies see a seq<seq> parameter
            # (THE ENCODING note in `lower()`'s `nested_seqs` requires
            # loop): a ground DATA array (every row's elements
            # concatenated in order) and a ground OFFSETS array (`n + 1`
            # entries, `off[i]` the start of row `i`), built directly
            # from the witness's own rows rather than reusing any
            # runtime flattening helper (there is none; this is the one
            # place a nested witness value is ever turned into C).
            if not (isinstance(v, list) and all(isinstance(r, list)
                                               for r in v)):
                return None                # not a ground nested-seq witness
            if f"t_cert_{n}_data" in used or f"t_cert_{n}_off" in used:
                return None
            data: list = []
            off = [0]
            for row in v:
                data.extend(int(x) for x in row)
                off.append(len(data))
            data_arr, off_arr = f"t_cert_{n}_data", f"t_cert_{n}_off"
            data_init = ", ".join(_int_lit(x) for x in data) or "0"
            off_init = ", ".join(_int_lit(x) for x in off)
            decls.append(f"  int {data_arr}[{max(len(data), 1)}] = "
                         f"{{{data_init}}};")
            decls.append(f"  int {off_arr}[{len(off)}] = {{{off_init}}};")
            decls.append(f"  int *{n}_data = {data_arr};")
            decls.append(f"  int *{n}_off = {off_arr};")
            decls.append(f"  int {n}_n = {len(v)};")
            ctx_env[n] = {"seq": "seq"}
            st[n] = [list(row) for row in v]
        elif isinstance(v, list):
            arr = f"t_cert_{n}"
            vals = [int(x) for x in v]
            init = ", ".join(_int_lit(x) for x in vals) or "0"
            decls.append(f"  int {arr}[{max(len(vals), 1)}] = {{{init}}};")
            decls.append(f"  int *{n} = {arr};")
            decls.append(f"  int {n}_n = {len(vals)};")
            ctx_env[n] = "seq"
            st[n] = vals
        elif isinstance(v, bool):
            decls.append(f"  int {n} = {int(v)};")
            ctx_env[n] = "bool"
            st[n] = v
        else:
            decls.append(f"  int {n} = {_int_lit(v)};")
            ctx_env[n] = "int"
            st[n] = v
    ctx = Ctx(ctx_env, funs, ret=None, label="Here")
    body_out: list = []
    try:
        _cert_stmts(suffix, ctx, st, task["name"], body_out, [0])
    except (_CertSkip, NotImplementedError, ValueError, KeyError, TypeError,
            RecursionError):
        return None
    ret = task["returns"][0]["name"]
    if ret not in st:
        return None
    ectx = Ctx(env, funs, ret=None, label="Here")
    pieces = []
    for e in task["ensures"]:
        d, p = defs(e, ectx), pred(e, ectx)
        pieces.append(f"({p})" if d is None else f"((({d}) && ({p})))")
    lines = ["", "/*@ assigns \\nothing; */",
             f"void {CERT_FN}(void) {{", *decls, *body_out,
             f"  /*@ assert {CERT_GOAL}: !({' && '.join(pieces)}); */",
             "  return;", "}", ""]
    return "\n".join(lines)


def _measure_certificate(task: dict, twin_body: list, w: dict,
                         env: dict, funs: dict, used: set) -> str | None:
    """ROADMAP 13.4, framac-measure, 2026-09-11: the certificate for a
    "measure"-kind witness (harness.real_witness / interp.MeasureViolation
    -- see both docstrings), the module docstring's note above this
    file's THE SEMANTIC LINE section and the one above `_value_certificate`
    and `_undef_certificate` (`certificate()`'s own doctrine: REFUTED is
    minted from a certificate the harness computes and the kernel checks,
    never from a prover status). MEASURED, not assumed (2026-09-11):
    alt-ergo 2.4.3 reads Stepout and Z3 4.8.12 reads Timeout on the naked
    lemma `0 < 0` in an axiom-free file (this file's module docstring),
    so no prover status on the emitted termination lemma
    (`f_terminates_k`, or the loop's own `loop variant` PO) names a false
    fact honestly -- a real timeout or a real "no fact was false" both
    read as unproved noise. The fix already used for a false `ensures` is
    the same fix here: replay the witness's own two GROUND integers
    (`_caller_measure`, `_callee_measure`, computed independently by
    interp.py's bounded scan, not re-derived here) as C constants and
    assert the concrete arithmetic fact the well-foundedness rule needs
    -- `0 <= caller && callee < caller` -- is FALSE at exactly these two
    numbers. Pure ground arithmetic, no axiom, no call, no loop: Qed
    proves it or the numbers are wrong.

    Unlike `_value_certificate`, no replay of `twin_body` at all: a
    measure witness's two numbers are ALREADY the trusted final values
    (interp.ev evaluated the `decreases` expression itself while walking
    the real execution), so there is nothing here to re-derive them
    from -- the certificate is the comparison alone, exactly as small as
    the fact it proves.

    None (no certificate, honestly) when the witness is not this kind, a
    name collides, or the two measures are not both plain ints (a
    malformed witness this file did not build and will not certify)."""
    if w.get("_kind") != "measure":
        return None
    if CERT_FN in used or CERT_GOAL in used:
        return None
    caller_m, callee_m = w.get("_caller_measure"), w.get("_callee_measure")
    if (not isinstance(caller_m, int) or isinstance(caller_m, bool)
           or not isinstance(callee_m, int) or isinstance(callee_m, bool)):
        return None                    # not the ground-int shape this builds
    fact = f"(({_int_lit(caller_m)} >= 0) && ({_int_lit(callee_m)} < {_int_lit(caller_m)}))"
    lines = ["", "/*@ assigns \\nothing; */",
             f"void {CERT_FN}(void) {{",
             f"  /*@ assert {CERT_GOAL}: !{fact}; */",
             "  return;", "}", ""]
    return "\n".join(lines)


def certificate(task: dict, twin_body: list, w: dict,
                env: dict, funs: dict, used: set) -> str | None:
    """The certificate function's source text, or None with the reason
    left to the caller's honesty: only a certifiable witness earns one.
    Dispatches on `w["_kind"]`; see the section comment above for what
    each kind needs and does not (yet) cover.

    `undefined` and `exit` apply to ANY task, whatever its return type
    (UNGATED 2026-09-09: the seq-return gate landed the same night as
    `update`/`fill` purely to keep that night's 15-task regression reading
    byte-for-byte as AGREEMENT.md recorded it, not because either
    mechanism is seq-specific -- an `undefined` witness can come from a
    bare `at`/`div`/`mod`, an `exit` witness from any INVARIANT-DROP twin,
    on a scalar-returning task exactly as on a seq-returning one). Removing
    the gate was measured, not assumed: over the 17 committed tasks it
    turns 9 of the 9 `verified / timeout` cells into `verified / refuted`
    (all_nonneg, contains, count_matches, digit_sum, first_even, is_prime,
    linear_search, seq_max, sum_upto), every real program's C staying
    byte-identical to the gated lowering (checked task-by-task; only the
    twin file's certificate function changes). See the dated note below
    `lower()` for the full measurement, including the lifted-785 sweep."""
    if w is None:
        return None
    if CERT_FN in used or CERT_GOAL in used:
        return None                    # a task name would collide or forge
    kind = w.get("_kind")
    if kind == "undefined" and w.get("_site") == "ensures":
        # 2026-09-12: an ensures undefined at the witness. The body has a
        # value there (the witness carries it as _value), and this lowering
        # refuted these probes before the ensures-level shape existed through
        # the VALUE certificate plus its own defs() companions; replaying the
        # body as an undefined witness built nothing and timed out (the pass
        # 2 gate), so the value certificate is the door.
        if "_value" not in w:
            return None
        w2 = {**w, "_kind": "value", "_real": w["_value"], "_twin": w["_value"], "_ens": True}
        return _value_certificate(task, twin_body, w2, env, funs, used)
    if kind == "value":
        return _value_certificate(task, twin_body, w, env, funs, used)
    if kind == "undefined":
        return _undef_certificate(task, twin_body, w, env, funs, used)
    if kind == "exit":
        return _exit_certificate(task, twin_body, w, env, funs, used)
    if kind == "measure":
        return _measure_certificate(task, twin_body, w, env, funs, used)
    return None                        # preservation: see the section note


# -------------------------------------------------------------- lowering ----

def _always_returns(body: list) -> bool:
    """True when every path through `body` ends in `return` (SPEC.md
    "Early exit", 2026-09-08). Mirrors lower_lean.py's `_always_returns`:
    a path ends the block either with a `return` statement or with an
    `if` whose two branches both always return. Used by `lower()` to
    decide whether the function body already covers every path, so the
    unconditional trailing `return {ret};` this lowering used to emit
    after the body is skipped rather than left as dead code (see the
    DIV/MOD SMOKE / RETURN SMOKE note above `lower`)."""
    if not body:
        return False
    s = body[-1]
    if "return" in s:
        return True
    if "if" in s:
        c = s["if"]
        return _always_returns(c["then"]) and _always_returns(c["else"])
    return False


# `witness` is the twin's measured witness (harness.twin_cached). Twin call
# sites pass it; when it is certifiable, the emitted file carries the
# refutation certificate (see the section above).
def lower(task: dict, body: list, witness: dict | None = None) -> str:
    # FRAMAC-NESTED, 2026-09-12: `_SEQ_EQ_CTR` names the temps the
    # extensional seq equality loop above declares (`__seq_eq0`,
    # `__seq_eq1`, ...) uniquely WITHIN one call to `lower()`; reset here
    # so two calls in the same process (real then twin, or two different
    # tasks under one `--jobs` worker) never share a counter value, which
    # would still be sound C (each call emits its own fresh file) but
    # would make two different calls' emitted names needlessly depend on
    # how many equality loops a PRIOR, unrelated call happened to emit.
    _SEQ_EQ_CTR[0] = 0
    # NAMES (2026-09-11, ROADMAP 13.2): sanitize away any identifier that
    # collides with a C/ACSL reserved word, before anything below ever
    # sees the task -- see names.py's module docstring (imported as
    # `t_names` here, since this file's own certificate code already uses
    # a local `names` dict for the witness's own name->value map).
    # `task`/`body` are returned unchanged (`is`) when nothing needs a
    # rename, which is every previously-committed task, so this costs one
    # extra scan and changes nothing downstream for them. `certificate`
    # below runs on this SAME renamed task/body/env/funs/used, with
    # `witness`'s own keys renamed to match (`t_names.remap_witness`):
    # this file's own certificate declares fresh C LOCALS spelled after
    # the witness's own keys (`int {n} = ...;`), so building it against
    # an un-renamed witness/task -- this file's first cut, MEASURED
    # 2026-09-11 on probe_names_framac -- emitted literally `int int =
    # 0;` for a param named `int`, well-formed C nowhere. See
    # `remap_witness`'s own docstring.
    twin_body = body if body is not task.get("body") else None
    task, renames = t_names.sanitize(task, t_names.KEYWORDS["framac"],
                                     uppercase_ok=True)
    # the twin body renamed under the same mapping, kept a separate
    # object from task["body"] (2026-09-11, names.rename_body's note)
    body = t_names.rename_body(twin_body, renames) if twin_body is not None else task["body"]
    witness = t_names.remap_witness(witness, renames)
    name, ret = task["name"], task["returns"][0]["name"]
    rett = task["returns"][0]["type"]
    nested_return_rows = None
    if is_nested_seq_type(rett):
        nested_return_rows = _ret_nested_fold(body, ret)
    if is_nested_seq_type(rett) and nested_return_rows is None:
        # NAMED REFUSAL, added 2026-09-10 (SPEC.md "Nested sequences").
        # FRAMAC-NESTED, added 2026-09-14 (DESIGN-framac-nested-seq.md
        # sections 1-3): reached only when `_ret_nested_fold` above could
        # NOT constant-fold `ret`'s own build expression; see that
        # function's own docstring and `_fold_nested_rows` for the two
        # named cells (`fz_p_nest_empty`, `fz_p_str_splitempty`) that
        # NOW skip this refusal entirely, both building their nested
        # return from a compile-time constant (`[]`, or SPEC.md's own
        # `split("") == []`), never reaching a runtime BUILD this
        # backend still has no encoding for. `swap_rows`'s own shape (a
        # genuine runtime build from a seq<seq> PARAMETER) is not
        # constant and still falls straight through to this same
        # refusal, unchanged.
        # Measured against `row_max_len` (a nested seq PARAMETER, read
        # only) first, per RULES, before this construct's own committed
        # BUILDING task, `swap_rows`, was even attempted: a seq<seq>
        # RETURN needs to BUILD a fresh row set (`update`'s own two
        # nested calls, `swap_rows`'s body), and this backend's flat
        # data+offsets encoding (THE ENCODING note below
        # `assigned_names`) has nothing to build one INTO. The offsets
        # array itself is a second, row-shaped dimension the seq VALUE
        # machinery's own CAPACITY mode (a length-tracking LOCAL threaded
        # through `Ctx.seq_len`, sized against a single `ensures`-stated
        # bound) does not compose over: CAPACITY mode sizes ONE buffer's
        # element count against ONE bound; a built seq<seq> return would
        # need the OFFSETS array's own count (the number of rows, itself
        # data-dependent when a row is appended rather than merely
        # replaced) sized against a second, independent bound no
        # committed task's `ensures` states, and the DATA array's total
        # size sized against a data-dependent SUM of row lengths, not a
        # single scalar. Refused by name, exactly as SPEC.md's own
        # "Nested sequences" section predicted for this column ("a named
        # refusal or a flat encoding ... measured first"): swap_rows,
        # this construct's one building task, hits this refusal at the
        # earliest possible point, before any C is emitted for it at
        # all. A seq<seq> PARAMETER, read only through `len`/`at`
        # (`row_max_len`'s own shape), is supported below.
        raise NotImplementedError(
            "nested seq (seq<seq>) RETURN: building a fresh row set has "
            "no encoding in this lowering beyond a compile-time-constant "
            "value (`_ret_nested_fold`/`_fold_nested_rows`, added "
            "2026-09-14); the flat data+offsets encoding's CAPACITY "
            "machinery sizes one buffer against one bound, not a "
            "row-shaped offsets array against a second, data-dependent "
            "one, for a genuinely data-dependent build; a seq<seq> "
            "PARAMETER, read via `len`/`at`, is supported")
    env = {p["name"]: p["type"] for p in task["params"]}
    env[ret] = rett

    funs = {}
    for f in task.get("spec_funs", []):
        # "executable" (framac-closure, 2026-09-14): whether this
        # spec_fun QUALIFIES for a C mirror function (`_spec_fun_c`,
        # below), so `cexpr`'s "call" case can lower a call to it
        # reaching executable position instead of abstaining. Eligible:
        # no seq-typed param (`_spec_fun_c` has no buffer-pointer C
        # signature to mirror one against) and not self-recursive (a
        # recursive spec_fun's C mirror would need its OWN `decreases`-
        # backed termination obligation, ROADMAP's own note on
        # factorialOfLastDigit/Triple, not attempted by this pass).
        funs[f["name"]] = {
            "params": f["params"], "result": f["result"],
            "labeled": any(p["type"] == "seq" for p in f["params"]),
            "is_task": False,
            "executable": (
                not any(p["type"] == "seq" for p in f["params"])
                and not self_calls(f["body"], f["name"], []))}
    funs[name] = {"params": task["params"], "result": rett,
                  "labeled": False, "is_task": True}

    seqs = [p["name"] for p in task["params"] if p["type"] == "seq"]
    nested_seqs = [p["name"] for p in task["params"]
                  if is_nested_seq_type(p["type"])]
    used = set()

    def names_in(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("var", "name", "fun") and isinstance(v, str):
                    used.add(v)
                names_in(v)
        elif isinstance(x, list):
            for v in x:
                names_in(v)
    names_in(task)
    names_in(body)
    for s in seqs:
        if f"{s}_n" in used:
            raise NotImplementedError(
                f"name {s}_n collides with the fresh length parameter "
                f"for seq {s}")
    for m in nested_seqs:
        for suffix in ("_data", "_off", "_n"):
            if f"{m}{suffix}" in used:
                raise NotImplementedError(
                    f"name {m}{suffix} collides with a fresh parameter "
                    f"this lowering synthesizes for nested seq {m}")

    # PAIRS (SPEC.md "Pairs", 2026-09-10): a pair-typed RETURN's struct
    # type must be declared before anything in the file uses it (the
    # contract's `\result.a`/`\result.b`, the function's own C prototype,
    # and, when this task's twin is certifiable, the appended certificate
    # function's own local of the same type) -- see the section comment
    # above `_pair_field_c`. `pair_ty`/`struct_name` stay RETURN-specific
    # (both committed tasks build their pair only as the return's own
    # final value, and `ret_decl`/`cfun_ret_ty`/the certificate below all
    # still key off exactly this), kept byte-identical for both.
    pair_ty = rett if isinstance(rett, dict) and "pair" in rett else None
    struct_name = (_pair_struct_name(*pair_ty["pair"])
                  if pair_ty is not None else None)

    # FIXED 2026-09-10, alongside the parameter/local fix above
    # `_pair_field_c`: a pair can also arrive as a PARAMETER, a LOCAL, or
    # a `pair(...)` built and immediately projected without ever being
    # bound to a name (`fz_p_pair_proj`), none of which the RETURN-only
    # check above ever saw. `_pair_types_needed` finds every distinct
    # shape actually used; only the ones NOT already covered by the
    # return's own struct (declared above, unchanged) get a second
    # declaration line, so a non-pair task or a pair-RETURN-only task
    # (every task this backend already had before today) emits the exact
    # same header as before, byte for byte.
    declared_pairs = {tuple(pair_ty["pair"])} if pair_ty is not None else set()
    extra_pair_types = [pt for pt in _pair_types_needed(task, body, env, funs)
                        if pt not in declared_pairs]

    header = []
    if pair_ty is not None:
        header.append(f"struct {struct_name} {{ int a; int b; }};")
    for pt in extra_pair_types:
        header.append(f"struct {_pair_struct_name(*pt)} {{ int a; int b; }};")
    if _has_divmod(task) or _has_divmod(body):
        header.append(T_DIVMOD_ACSL.rstrip("\n"))
    if _has_caselower(task) or _has_caselower(body):
        header.append(T_CASE_ACSL.rstrip("\n"))
    if _has_wordcount(task) or _has_wordcount(body):
        header.append(T_WORDCOUNT_ACSL.rstrip("\n"))
    if _has_countfind(task) or _has_countfind(body):
        header.append(T_STRFIND_ACSL.rstrip("\n"))
    # WITHHELD DEFINITION (2026-09-11, ROADMAP 13.4, framac-axiom): a
    # "measure"-kind witness names, in `_site`, the exact spec_fun whose
    # own `decreases` the harness caught failing at a concrete input
    # (interp.MeasureViolation's "call" site; see spec_fun_acsl's own
    # docstring for why the definition is withheld rather than merely
    # certified). `_site` is a string ONLY for that call-site shape (a
    # loop's own site is turned into an int index by harness.py before
    # this file ever sees it -- fz_p_badvariant's witness, unaffected),
    # and is checked against `funs` (not merely truthy) so a witness
    # whose `_site` happens to collide with the task's OWN name (a
    # spec_fun call from inside a self-recursive task body; is_task is
    # True there) never withholds the task's own C function.
    measure_fn = None
    if witness is not None and witness.get("_kind") == "measure":
        site = witness.get("_site")
        if isinstance(site, str) and site in funs and not funs[site]["is_task"]:
            measure_fn = site
    for f in task.get("spec_funs", []):
        header += spec_fun_acsl(f, funs, declare_only=(f["name"] == measure_fn))
    # FRAMAC-CLOSURE, 2026-09-14: an ELIGIBLE spec_fun (see `_spec_fun_c`'s
    # own docstring) also gets its C mirror emitted here, unconditionally
    # (like T_DIVMOD_ACSL/T_CASE_ACSL, over-inclusive by design -- an
    # unused C function costs nothing), so a call reaching executable
    # position anywhere in the body (`cexpr`'s "call" case, above) finds
    # `{name}_c` already declared. A withheld-definition spec_fun
    # (`f["name"] == measure_fn`) is skipped: its logic function has no
    # `= body` for `_spec_fun_c` to mirror as C, and the measure witness
    # already proves ITS own call site refutes via the certificate, not
    # this mirror.
    for f in task.get("spec_funs", []):
        if funs[f["name"]]["executable"] and f["name"] != measure_fn:
            header += _spec_fun_c(f, funs)

    # DIVISOR-BOUND LEMMA, tried and MEASURED NOT WIRED, 2026-09-12
    # (ROADMAP 16.2, framac-cert; `_divisor_bound_target`/
    # `_divisor_bound_lemma_acsl`, below `spec_fun_acsl`, are the
    # would-be hook's two functions, kept for the record but not called
    # here). dafny-synthesis isNonPrime (3) / isPrime (605) real-side
    # `timeout` is WP's Stepout on exactly the goal the divisor-bound
    # fact (any `k` with `lo<=k<n` and `n mod k==0` satisfies `k<=n/2`)
    # would close -- `lower_verus.py`/`lower_fstar.py`'s own dated notes
    # close the identical gap on their own kernels, both via an EXPLICIT
    # nonlinear-arithmetic solver call (Z3's `by (nonlinear_arith)`,
    # neither file's default profile) this file's pinned prover, alt-ergo
    # 2.4.3, has no equivalent of. MEASURED directly (probe1.c/probe2.c/
    # probe3.c, this session): even the FLATTENED, hint-free core fact
    # `q >= 2 && k >= 2 && n == q * k ==> 2 * k <= n` -- a single
    # multiplication, no division/modulo, no case split -- reads
    # `[Stepout]` at the pinned budget (`-wp-steps 20000 -wp-timeout
    # 10`) AND at 50x the budget (`-wp-steps 1000000 -wp-timeout 60`,
    # tried once to rule out "merely slow"): alt-ergo 2.4.3 does not
    # discharge a two-variable integer product here at all, hint or no
    # hint, so no ACSL lemma text this file could emit closes it within
    # the pinned toolchain -- an honest, named gap (RULES: "a timeout
    # closes only by a proof inside the pinned budget"), not something
    # the divisor-bound lemma below can be made to paper over.

    # A seq RETURN's length, computed statically from the body (seq value
    # machinery section, above `assigned_names`): needed at requires-time,
    # before the function runs, to size the caller-provided output
    # buffer's `\valid`/`\separated` bound. `body` (the REAL or the TWIN
    # body, whichever this call is lowering) is what is walked, since it
    # is what actually determines the length that particular C function
    # writes; the real and twin lowerings of the same task can therefore
    # legitimately compute different (but here, on both committed tasks,
    # equal) length expressions.
    #
    # CAPACITY mode, added 2026-09-09 (SPEC.md "Sequences: literals,
    # concatenation, slices", the append idiom `r := r + [x]`,
    # `filter_pos`'s own shape): when the exact length has no closed form
    # (the append sits inside a data-dependent `if`/`while`, so
    # `_seq_len_track`'s own before/after check drops it, exactly as
    # designed), `_ret_capacity` reads a CAPACITY bound E directly off the
    # task's first `ensures` of the shape `len(ret) <= E`/`== E` and pins
    # `requires {ret}_n == E` as the buffer's SIZE, not its final content
    # length. The buffer's actual, data-dependent final length is tracked
    # by a fresh LOCAL, `{ret}_len`, threaded through the body via
    # `ctx.seq_len` ({ret: "{ret}_len"} while still inside the function,
    # where `len(ret)` in a loop invariant renders as that local; {ret:
    # "\\result"} in the function's own post-state, where `ensures` -- no
    # locals in scope there -- reads the SAME final count off the C
    # function's own return value instead, so the C function itself
    # becomes non-void, `int`, in CAPACITY mode, holding the buffer's true
    # length rather than a scalar answer (no committed task returns both a
    # seq and a scalar, so there is no clash to resolve here). EXACT mode
    # (`ret in lens`, `tail`'s own shape, unchanged from before this
    # construct) leaves `ctx.seq_len` empty everywhere, `{ret}_n` meaning
    # exactly what it always has.
    # THE TRACKED-LENGTH ENCODING, added 2026-09-10 (second pass), THE
    # BUFFER-LENGTH GATE's own design question. EXACT mode's plain
    # rendering (`ret in lens`, `{ret}_n` bare everywhere) is correct but
    # makes any TASK-declared length-equality loop invariant
    # (`len(ret)==len(s)`, the shape all six lifted-785 tasks the first
    # pass's gate covered, plus `reverse`, all share) `requires`-derivable
    # and therefore vacuous to drop: an INVARIANT-DROP twin that removes
    # exactly that conjunct is a NO-OP at the C level (measured, THE
    # BUFFER-LENGTH GATE's own note above `_exit_certificate`), so
    # REFUTED is structurally unreachable there and the gate's honest
    # answer was `verified / verified`. `ret_written_in_loop` picks out
    # the shape the design question names (a loop that FILLS or
    # SELF-UPDATES the return in place, `_ret_written_in_loop`, as
    # opposed to a loop-free EXACT shape like `tail`'s slice, where there
    # is no loop invariant to make real in the first place): for exactly
    # that shape, this now reuses CAPACITY mode's own machinery
    # (`ctx.seq_len` threading, `\result` in post-state, an `int`-
    # returning C function) with the SAME closed-form bound EXACT mode
    # already computed (`ret_len_expr`, still pinning the buffer's own
    # `requires {ret}_n == ...`, needed for `\valid` regardless of
    # anything below) -- the one difference from the append idiom's own
    # CAPACITY use is that the tracked local starts at that closed form
    # (`ret_decl` below), not at an accumulating 0, because nothing here
    # grows it; the loop merely needs the TASK's own length invariant
    # threaded through `ctx.seq_len` to become a real preservation
    # obligation instead of a `requires`-derivable one. MEASURED first by
    # hand (frama-c directly on a two-loop probe mirroring this exact
    # shape, real and an invariant-dropped twin, before this code was
    # written, RULES' own order): the real program still verifies in
    # full (35/35 goals) with the tracked local forced into the
    # self-update loop's own `loop assigns` (see `assigned_names`'s
    # `seq_caps` piggyback below, already doing exactly this for any
    # assignment TARGET that is also a `ctx.seq_len` key, unchanged code)
    # -- WITHOUT that forcing, the same probe's twin verified in full too
    # (33/33, the identical vacuity this whole gate exists to fix: WP's
    # frame rule auto-preserves an unlisted local's value across a loop
    # it does not otherwise assign, so the dropped invariant stayed
    # unneeded) -- WITH it, the twin's own `ensures` and two invariant-
    # preservation goals read an honest [Stepout] (4 goals), the real
    # program unaffected. See the dated note below `assigned_names` for
    # the seven-task measurement this enabled.
    ret_len_expr = None
    capacity_mode = False
    tracked_exact = False
    LEN = f"{ret}_len"
    if rett == "seq":
        lens = {s: {"op": "len", "args": [{"var": s}]} for s in seqs}
        _seq_len_track(body, lens)
        if ret in lens:
            ret_len_expr = lens[ret]
            if _ret_written_in_loop(body, ret):
                capacity_mode = True
                tracked_exact = True
        else:
            capacity_mode = True
            ret_len_expr = _ret_capacity(task, ret)
            if ret_len_expr is None:
                raise NotImplementedError(
                    f"seq return {ret!r}'s length is not statically "
                    f"determinable from the task's params (needed to size "
                    f"its output buffer's `requires`), and no `ensures` "
                    f"of the shape `len({ret}) <= E` or `== E` gives a "
                    f"CAPACITY bound either; see the seq value machinery "
                    f"section above `assigned_names` and `_ret_capacity`")
        if capacity_mode and LEN in used:
            raise NotImplementedError(
                f"name {LEN} collides with the synthetic length-"
                f"tracking local this lowering needs for the "
                f"CAPACITY-tracked return {ret}")

    body_seq_len = {ret: LEN} if capacity_mode else {}
    spec_ctx = Ctx(env, funs, ret=None, label="Here")
    post_ctx = Ctx(env, funs, ret=(ret if rett != "seq" else None),
                   label="Here",
                   seq_len=({ret: "\\result"} if capacity_mode else {}))
    clauses = []
    all_seqs = list(seqs)
    for s in seqs:
        clauses.append(f"  requires {s}_n >= 0;")
        clauses.append(f"  requires \\valid_read({s} + (0 .. {s}_n - 1));")
    for m in nested_seqs:
        # THE ENCODING (SPEC.md "Nested sequences", 2026-09-10, measured
        # first on `row_max_len`, a nested seq PARAMETER read only,
        # before `swap_rows`'s BUILDING shape was even attempted, per
        # RULES): a seq<seq> parameter is a flat buffer of ints plus an
        # offsets array, `const int *m_data, const int *m_off, int m_n`
        # (`const` dropped here since this backend already renders every
        # seq param's own element type as plain, non-const `int *`, the
        # `\valid_read` requires below being what actually keeps it
        # read-only to WP, not the C qualifier). `m_n` is the ROW COUNT,
        # reusing this backend's existing `{name}_n` convention (a plain
        # seq's `_n` is its element count; a nested seq's `_n` is its row
        # count) rather than inventing a second name -- this is what lets
        # `at_asserts`'s existing "at" tag, `defs()`'s existing "at" case
        # and `_seq_len_render`'s existing bare-var fallback ALL handle
        # `m`'s OUTER dimension (`len(m)`, `at(m, i)`'s own bound) with
        # NO changes at all, verified by inspection, not merely hoped:
        # every one of those already renders `0 <= i < {v}_n` /
        # `ctx.seq_len.get(v, f"{v}_n")` off of `seq_var`'s own return,
        # and `seq_var` now recognizes a seq<seq> variable exactly as it
        # already recognized a plain seq one (see `seq_var`'s own
        # docstring). Row `i` is `m_data[m_off[i] .. m_off[i+1])`, so
        # `m_off` has `m_n + 1` entries (index `m_n` is the total data
        # length, `off[0]` the first row's own start, not assumed 0);
        # `\valid_read` and the MONOTONE-OFFSETS requires below are
        # exactly what the construct brief asked this lowering to add
        # IMPLICITLY (a task's own `requires` never states either, and
        # neither committed task's `requires`/`ensures` mentions `m_off`
        # at all): without monotonicity a row's own length,
        # `m_off[i+1] - m_off[i]` (`_seq_len_render`'s new "at" case,
        # ACSL side; `cexpr()`'s matching case, executable side), could
        # be NEGATIVE, which is not a memory-safety hole (ACSL's logic is
        # total, `defs()`'s own docstring) but would be a wrong theorem
        # about `len(m[i])` on a task whose real `requires` never
        # constrains the encoding's own housekeeping array. `m_off[0] >=
        # 0` anchors the first row's start (monotonicity alone would let
        # every offset be pinned by an arbitrarily negative first entry);
        # both are requires-time facts about the CALLER's own array,
        # never proof obligations the body's own code must discharge, so
        # neither needs an invariant, unlike CAPACITY mode's implicit
        # LOWER bound on a length LOCAL a loop body actually writes (the
        # seq-trio note's own CAPACITY discussion, above `assigned_names`
        # / in `stmts()`'s `while` case) -- there is no loop here to
        # requires-time facts to survive, they are simply given.
        clauses.append(f"  requires {m}_n >= 0;")
        clauses.append(f"  requires \\valid_read({m}_off + (0 .. {m}_n));")
        clauses.append(f"  requires {m}_off[0] >= 0;")
        clauses.append(
            f"  requires \\forall integer __t; 0 <= __t < {m}_n "
            f"==> {m}_off[__t] <= {m}_off[__t + 1];")
        clauses.append(f"  requires \\valid_read({m}_data + "
                       f"(0 .. {m}_off[{m}_n] - 1));")
    if rett == "seq":
        # The return's own buffer: caller-provided, WRITABLE (`\valid`,
        # not `\valid_read`), and pinned to the length the body's own
        # writes will actually produce (`ret_len_expr`, rendered here in
        # PARAMS-only terms, exactly what ACSL's `requires` scope allows).
        #
        # FILL DEFINEDNESS, fixed 2026-09-10 (see this file's own dated
        # note below `assigned_names`): this clause set used to also
        # state `requires {ret}_n >= 0;` unconditionally, BEFORE the
        # length-pinning line below it. That is sound whenever
        # `ret_len_expr` is already provably nonnegative from some OTHER
        # requires already in `clauses` (every committed task: `len(s)`
        # chains to `s`'s own `{s}_n >= 0`, a slice's `b - a` chains to
        # the task's own `0 <= a <= b`, CAPACITY's `E` chains to an
        # existing seq length the same way) -- but when `ret_len_expr`
        # is NOT so constrained (`fill`'s own count read straight off a
        # bare int param, `fz_p_fill_neg`'s `r := fill(n, 0)` with only
        # `requires n <= 100`), stating it here ANYWAY silently ADDS
        # `n >= 0` to the function's assumed preconditions rather than
        # leaving it a proof obligation: paired with `requires {ret}_n ==
        # n` below, `{ret}_n >= 0` is exactly `n >= 0` restated, and SPEC.md
        # says `fill` is undefined, not requires-excluded, at a negative
        # count the task's own `requires` lets through. MEASURED
        # (`frama-c`/WP directly, the probe before touching this file):
        # with the line present, `fz_p_fill_neg_t` reads 14/14 goals
        # proved, the FALSE theorem "well-defined at every n <= 100"
        # VERIFIED; with it removed, the very same `/*@ assert (n) >= 0;
        # */` this file already emits in `seq_assign_lines`'s own `fill`
        # case (below `stmts()`) becomes a REAL, undischargeable goal
        # (`[Timeout]`, 13/14), because nothing else in scope entails
        # `n >= 0` -- the domain check finally has teeth instead of being
        # granted by the very clause meant only to size a buffer.
        # `\valid({ret} + (0 .. {ret}_n - 1))` needs no companion sign
        # assumption of its own: ACSL's range `(0 .. {ret}_n - 1)` is
        # simply empty, and `\valid` over an empty range vacuously true,
        # whenever `{ret}_n <= 0`, measured on the same probe (parses and
        # discharges the same way with or without the dropped line).
        clauses.append(f"  requires \\valid({ret} + (0 .. {ret}_n - 1));")
        clauses.append(f"  requires {ret}_n == "
                       f"{term(ret_len_expr, spec_ctx)};")
        all_seqs.append(ret)
    elif nested_return_rows is not None:
        # FRAMAC-NESTED, added 2026-09-14 (DESIGN-framac-nested-seq.md
        # sections 1-2): the return's own two buffers, both
        # caller-provided and WRITABLE (`\valid`, not `\valid_read`),
        # sized by the two capacities `_ret_nested_fold` already
        # resolved to closed-form INTEGER LITERALS -- ROWS (the row
        # count, pinned into `{ret}_n` exactly the way a plain seq
        # return's EXACT mode pins `{ret}_n`, THE ENCODING's own row-
        # count convention for a nested seq PARAMETER reused here for a
        # RETURN) and DATA (the total element count, needed only to size
        # `{ret}_data`'s own `\valid`, never a separate C parameter: no
        # loop or `\result` reads it back, since both counts are already
        # literals, not something the body computes at runtime).
        ret_rows = len(nested_return_rows)
        ret_data = sum(len(r) for r in nested_return_rows)
        clauses.append(f"  requires {ret}_n >= 0;")
        clauses.append(f"  requires {ret}_n == {ret_rows};")
        clauses.append(f"  requires \\valid({ret}_off + (0 .. {ret}_n));")
        clauses.append(f"  requires \\valid({ret}_data + "
                       f"(0 .. {ret_data} - 1));")
    for k, a in enumerate(all_seqs):
        for b in all_seqs[k + 1:]:
            # No two seq buffers may alias: swap's copy-then-write and
            # reverse's fill both read one buffer while writing another,
            # and WP's Typed memory model does not assume distinct `int *`
            # formals are non-overlapping on its own (measured: two params
            # of the same C type CAN alias under Typed unless told
            # otherwise).
            clauses.append(f"  requires \\separated({a} + (0 .. {a}_n - 1), "
                           f"{b} + (0 .. {b}_n - 1));")
    # DEFINEDNESS OF `requires` ITSELF, added 2026-09-11 (ROADMAP 13.4,
    # fz_p_divreq0). `ensures` already gets its `defs()` obligation folded
    # into the GOAL two blocks below (`ensures (d) && (p);`); `requires`
    # had none, only the raw predicate. That is silently unsound for a
    # requires whose own truth value is UNDEFINED rather than merely
    # false: t_div/t_mod are TOTAL ACSL logic functions (this file's own
    # T_DIVMOD_ACSL note), so `requires x / 0 == 0` renders as `requires
    # t_div(x, 0) == 0`, a predicate WP can evaluate to true or false
    # under its own total convention -- never the contradiction SPEC.md
    # says a `y == 0` divisor actually is. MEASURED (t/CONFORMANCE.md,
    # fz_p_divreq0, 2026-09-11 run): every other kernel read the real
    # unproved/refuted on this task; framac alone VERIFIED it, 14/14
    # goals, because nothing in the emitted contract ever asked WP to
    # prove the divisor nonzero. Emitting `defs(e)` here as an ADDITIONAL
    # `requires` clause -- an assumed hypothesis, exactly the shape
    # fz_p_vac_unsat/fz_p_vac_range's literally-false requires already
    # trips `_vacuity_smoke`'s existing `wp_smoke_default_requires` doomed-
    # goal detection on -- makes the combined hypothesis set for
    # fz_p_divreq0 read `t_div(x, 0) == 0 && (0) != 0`, contradictory by
    # construction (the second conjunct is literally false whenever the
    # divisor is a literal 0, and a genuine, checkable side condition
    # whenever it is a symbolic expression that MAY be zero), so WP's own
    # smoke test fires and the file reads VACUOUS rather than VERIFIED --
    # the same outcome fz_p_vac_unsat/fz_p_vac_range already read, not a
    # new mechanism. `defs()` for a requires with no partial operator
    # (the overwhelming majority: every committed task) returns None, so
    # this adds nothing there; unchanged by construction.
    for e in task.get("requires", []):
        d = defs(e, spec_ctx)
        if d is not None:
            clauses.append(f"  requires {d};")
        clauses.append(f"  requires {pred(e, spec_ctx)};")
    if "decreases" in task:
        clauses.append(f"  decreases ({term(task['decreases'], spec_ctx)});")
    if rett == "seq":
        # Only the return buffer's own elements are written; every seq
        # PARAM stays `\valid_read`-only and every scalar param/local is
        # a plain C local, never aliased into `ret`'s memory
        # (`\separated`, above).
        clauses.append(f"  assigns {ret}[0 .. {ret}_n - 1];")
    elif nested_return_rows is not None:
        # FRAMAC-NESTED, added 2026-09-14: the return's own two buffers
        # only, the same "only the return buffer's own elements" rule
        # above, over both the offsets array and the data array.
        clauses.append(f"  assigns {ret}_off[0 .. {ret}_n], "
                       f"{ret}_data[0 .. {ret_data} - 1];")
    else:
        clauses.append("  assigns \\nothing;")
    for e in task["ensures"]:
        d = defs(e, post_ctx)
        body_p = pred(e, post_ctx)
        clauses.append(f"  ensures {body_p};" if d is None else
                       f"  ensures ({d}) && ({body_p});")

    cparams = []
    for p in task["params"]:
        if p["type"] == "seq":
            cparams += [f"int *{p['name']}", f"int {p['name']}_n"]
        elif is_nested_seq_type(p["type"]):
            # THE ENCODING (2026-09-10): the flat data+offsets triple, see
            # the `nested_seqs` requires loop above for the full measured
            # rationale.
            cparams += [f"int *{p['name']}_data", f"int *{p['name']}_off",
                       f"int {p['name']}_n"]
        elif isinstance(p["type"], dict) and "pair" in p["type"]:
            # FIXED 2026-09-10 (see the section comment above
            # `_pair_field_c`): before this branch existed, a pair-typed
            # PARAMETER fell into the plain `else` below and was declared
            # `int`, a silent wrong lowering (a struct-shaped value
            # handed to the function as a bare `int`), read by frama-c as
            # MALFORMED the moment the body or contract read a field off
            # it. Passed BY VALUE, exactly the RETURN's own encoding
            # (candidate (a) from the section comment above
            # `_pair_field_c`'s pair value machinery, measured to work
            # for a return; MEASURED again here for a parameter,
            # `fuzz_lower.py --only framac` on the residual, since WP's
            # Typed model treating a value parameter and a value return
            # alike is not something this file assumes without running
            # it).
            sname = _pair_struct_name(*p["type"]["pair"])
            cparams.append(f"struct {sname} {p['name']}")
        else:
            cparams.append(f"int {p['name']}")
    if rett == "seq":
        cparams += [f"int *{ret}", f"int {ret}_n"]
    elif nested_return_rows is not None:
        # FRAMAC-NESTED, added 2026-09-14: the same flat data+offsets
        # triple THE ENCODING already uses for a nested seq<seq>
        # PARAMETER, appended as OUTPUT parameters exactly the way a
        # plain seq return appends `int *{ret}, int {ret}_n` above.
        cparams += [f"int *{ret}_data", f"int *{ret}_off", f"int {ret}_n"]

    if nested_return_rows is not None:
        # FRAMAC-NESTED, added 2026-09-14: the whole function body IS
        # the fold (`_ret_nested_fold` required `body` to be exactly one
        # statement), so nothing is handed to `stmts()` at all -- one
        # literal store per element (`r_data`), one per row boundary
        # (`r_off`), the same "individual stores, no loop" move
        # `seq_assign_lines`'s own `seq`-literal case makes for a flat
        # seq, just over two buffers instead of one.
        body_lines = []
        off = 0
        for k, row in enumerate(nested_return_rows):
            body_lines.append(f"  {ret}_off[{k}] = {off};")
            for j, v in enumerate(row):
                body_lines.append(f"  {ret}_data[{off + j}] = {v};")
            off += len(row)
        body_lines.append(f"  {ret}_off[{len(nested_return_rows)}] = {off};")
    else:
        body_lines = stmts(body, Ctx(env, funs, ret=None, label="Here",
                                     seq_len=body_seq_len),
                           name, "  ")
    # `certificate` reads the witness `w` against this SAME renamed
    # task/body/env/funs/used, `w`'s own keys already renamed to match
    # (`t_names.remap_witness`, above) -- see that function's own
    # docstring for why this file's certificate specifically needs the
    # renamed spelling in its own declarations, not the original one.
    cert = (certificate(task, body, witness, env, funs, used)
            if witness is not None else None)
    # RETURN SMOKE, fixed 2026-09-09 (see the note above `lower`): when
    # every path of `body` already ends in `return`, the trailing
    # `return {ret};` this lowering used to append unconditionally is dead
    # code no input reaches, and -wp-smoke-tests dooms it with no goal
    # name attached (a bare source-line warning, not a named
    # `wp_smoke_dead_code_sN` goal), which `verifiers/framac.py`'s
    # `_vacuity_smoke` fails closed on. So it is omitted precisely when
    # `_always_returns(body)` says the body needs it least: every other
    # body (no `return` at all, or a `return` that leaves a path falling
    # through) still gets it, unchanged.
    #
    # A seq return (2026-09-09) is `void` in EXACT mode: the "return
    # value" already lives in the caller-provided buffer, so no trailing
    # statement is ever needed, `return;` or otherwise -- a body that
    # falls off the end having already written every element it owes is
    # exactly correct, and a body with its own early `return;` (see
    # `stmts()`) needs nothing after it either.
    #
    # CAPACITY mode (2026-09-09) is `int` instead: the buffer's actual
    # final logical length has nowhere else externally visible to live
    # (see the note above this function's Ctx construction), so it is
    # the C function's own scalar return value, and the fall-through tail
    # -- omitted, like the scalar case, exactly when `_always_returns`
    # already covers every path with an explicit `return` -- reports the
    # length LOCAL `{ret}_len` rather than the seq name itself.
    if rett == "seq" and not capacity_mode:
        tail = ""
    elif rett == "seq":
        tail = "" if _always_returns(body) else f"  return {LEN};\n"
    elif nested_return_rows is not None:
        # FRAMAC-NESTED, added 2026-09-14: `void`, the same "return
        # value already lives in the caller-provided buffer" rule as a
        # plain seq return's EXACT mode, above -- both counts are
        # already pinned by `requires`, nothing left to report back.
        tail = ""
    else:
        tail = "" if _always_returns(body) else f"  return {ret};\n"
    # PAIRS (2026-09-10): a pair-typed RETURN's local and the function's
    # own C prototype are both the struct type declared in `header`
    # above (never `int`); `pair_ty`/`struct_name` are None for every
    # other task, so both branches below are no-ops there and every
    # non-pair task's C is unaffected byte-for-byte.
    # TRACKED-EXACT (see above): the local starts AT the closed form
    # EXACT mode already computed (`ret_len_expr`, over params only, so
    # this is well-defined at function entry regardless of what the body
    # does afterward), not at 0 -- unlike the append idiom's own
    # CAPACITY use, nothing here grows it; the point is only to make the
    # TASK's own length invariant a real preservation obligation instead
    # of a `requires`-derivable one.
    ret_decl = (f"  struct {struct_name} {ret};\n" if pair_ty is not None else
               f"  int {LEN} = {cexpr(ret_len_expr, env, funs, name)};\n"
               if tracked_exact else
               f"  int {LEN};\n" if capacity_mode else
               "" if nested_return_rows is not None else
               ("" if rett == "seq" else f"  int {ret};\n"))
    cfun_ret_ty = (f"struct {struct_name}" if pair_ty is not None else
                  "void" if rett == "seq" and not capacity_mode
                  else "void" if nested_return_rows is not None
                  else "int")
    rc = t_names.rename_comment(renames)
    return ("\n".join(header) + ("\n" if header else "")
            + "/*@\n" + "\n".join(clauses) + "\n*/\n"
            + f"{cfun_ret_ty} {name}_t({', '.join(cparams)}) {{\n"
            + ret_decl
            + "\n".join(body_lines) + "\n"
            + tail + "}\n"
            + (cert or "")
            + (f"\n// {rc}\n" if rc else ""))


if __name__ == "__main__":
    raise SystemExit(harness.run_all(sys.argv[1:], lower, framac_backend, "c"))
