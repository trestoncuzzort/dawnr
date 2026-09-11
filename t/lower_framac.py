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
"""
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
    "count": "a general non-overlapping substring count has no "
             "recursive ACSL definition in this lowering yet; the "
             "length-1-pattern case `count_vowels` needs is not "
             "specialized either, on purpose (SPEC.md: a member in "
             "specification position is the same function, not a "
             "task-shaped instance of it).",
    "find": "the same gap as `count`: no recursive ACSL definition of a "
            "left-to-right substring search is lowered yet.",
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
            # every index. Both operands must be bare seq variables (the
            # same restriction `seq_var`/`at` already enforce: this
            # backend has no ACSL rendering of a raw `update`/`fill`
            # value outside a body assignment, see `term()`).
            a, b = seq_var(args[0], ctx.env), seq_var(args[1], ctx.env)
            an = ctx.seq_len.get(a, f"{a}_n")
            bn = ctx.seq_len.get(b, f"{b}_n")
            eq = (f"(({an} == {bn}) && "
                 f"(\\forall integer __k; 0 <= __k && __k < {an} "
                 f"==> {a}[__k] == {b}[__k]))")
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
            raise NotImplementedError(
                "spec_fun call in executable position (ACSL logic functions "
                "are not executable)")
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
            # `len(m[i])` in EXECUTABLE position (SPEC.md "Nested
            # sequences", 2026-09-10: `row_max_len`'s own body, `r = len(
            # at(m, 0))` and `if len(at(m, i)) > r`). Same formula
            # `_seq_len_render`'s matching ACSL-side case renders, over
            # the offsets array, since a row has no C value to
            # materialize first.
            base, idx = a0["args"]
            m = seq_var(base, env)
            i = cexpr(idx, env, funs, task_name, _div_style)
            return f"({m}_off[({i}) + 1] - {m}_off[({i})])"
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


def code_ats(e: dict, env: dict, uncond: bool = True) -> list:
    """Definedness obligations for every `at`, `div` and `mod` in an
    executable expression, as tagged tuples: `("at", seq, index-expr)`,
    `("nz", divisor-expr)`, or `("dm", div-or-mod-node)`. Unconditionally
    evaluated occurrences are returned (they get an assert in front of the
    statement); a conditionally evaluated one is refused, because emitting
    it without a dischargeable guard would silently totalize the operator
    as C UB (an unguarded `at` as out-of-bounds access, an unguarded
    `div`/`mod` as division by zero).

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
        out += code_ats(i["cond"], env, uncond)
        out += code_ats(i["then"], env, False)
        out += code_ats(i["else"], env, False)
        return out
    if "call" in e:
        for a in e["call"]["args"]:
            out += code_ats(a, env, uncond)
        return out
    if "op" not in e:
        return out
    op, args = e["op"], e.get("args", [])
    if op == "at":
        if not uncond:
            raise NotImplementedError(
                "conditionally evaluated `at` in executable position: "
                "definedness not dischargeable by a plain assert")
        out += code_ats(args[1], env, uncond)
        out.append(("at", seq_var(args[0], env), args[1]))
        return out
    if op in DIVMOD:
        if not uncond:
            raise NotImplementedError(
                "conditionally evaluated `div`/`mod` in executable "
                "position: definedness not dischargeable by a plain assert")
        out += code_ats(args[0], env, uncond)
        out += code_ats(args[1], env, uncond)
        out.append(("nz", args[1]))
        out.append(("dm", e))
        return out
    if op in ("and", "or"):
        out += code_ats(args[0], env, uncond)
        for a in args[1:]:
            out += code_ats(a, env, False)
        return out
    if op == "implies":
        out += code_ats(args[0], env, uncond)
        out += code_ats(args[1], env, False)
        return out
    for a in args:
        out += code_ats(a, env, uncond)
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
        if tag == "at":
            s, ix = rest
            out.append(f"{indent}/*@ assert 0 <= ({term(ix, ctx)}) "
                       f"&& ({term(ix, ctx)}) < {s}_n; */")
        elif tag == "nz":
            (yx,) = rest
            out.append(f"{indent}/*@ assert ({term(yx, ctx)}) != 0; */")
        else:                                      # "dm": bridging assert
            (node,) = rest
            if funs is not None and task_name is not None:
                # `_divmod_ternary_cexpr`, not `cexpr`: this text lands
                # inside an ACSL annotation, where the branch-free form
                # `cexpr` now renders for executable position is not even
                # legal ACSL (a `\prop` cannot multiply an `integer`), and
                # the ternary form is not smoke-tested here regardless
                # (see `_divmod_ternary_cexpr`'s docstring).
                out.append(f"{indent}/*@ assert "
                           f"({_divmod_ternary_cexpr(node, ctx.env, funs, task_name)}) == "
                           f"({term(node, ctx)}); */")
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

    def _copy_loop(src: str, off: str | None = None) -> list:
        idx_t = f"({off}) + __t" if off is not None else "__t"
        idx_k = f"({off}) + __k" if off is not None else "__k"
        return [
            f"{indent}/*@",
            f"{indent}  loop invariant 0 <= __k <= {xn};",
            f"{indent}  loop invariant \\forall integer __t; "
            f"0 <= __t < __k ==> {target}[__t] == {src}[{idx_t}];",
            f"{indent}  loop assigns __k, {target}[0 .. {xn} - 1];",
            f"{indent}  loop variant {xn} - __k;",
            f"{indent}*/",
            f"{indent}for (int __k = 0; __k < {xn}; __k++) "
            f"{target}[__k] = {src}[{idx_k}];",
        ]

    if "var" in e:
        src = seq_var(e, ctx.env)
        out += _copy_loop(src)
        if cap is not None:
            out.append(f"{indent}{cap} = {xn};")
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
    raise NotImplementedError(
        f"seq-typed assignment from operator {op!r}: v1's grammar only "
        f"assigns a bare seq variable, `update`, `fill`, `seq`, `slice`, "
        f"or `+` to a seq-typed name")


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


def stmts(body: list, ctx: Ctx, task_name: str, indent: str) -> list:
    out = []
    for s in body:
        if "assign" in s:
            name, e = s["assign"]
            assert name in ctx.env, f"assign to undeclared {name}"
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
                # NAMED REFUSAL, added 2026-09-10 (SPEC.md "Nested
                # sequences"): a seq<seq>-typed LOCAL is the identical gap
                # as a plain seq-typed local just above, for the same
                # reason (no requires-time bound to size a backing
                # buffer from), and would in any case need to BUILD a
                # fresh row set to initialize it, the same shape the
                # seq<seq> RETURN refusal in `lower()` already names.
                # Not exercised by either committed task.
                raise NotImplementedError(
                    "nested seq (seq<seq>) local variables are not "
                    "supported by this lowering; only a seq<seq> "
                    "PARAMETER, read via `len`/`at`, is supported")
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
        elif "if" in s:
            c = s["if"]
            out += at_asserts(c["cond"], ctx, indent, ctx.funs, task_name)
            out.append(f"{indent}if "
                       f"({cexpr(c['cond'], ctx.env, ctx.funs, task_name)}) "
                       f"{{")
            out += stmts(c["then"], ctx, task_name, indent + "  ")
            out.append(f"{indent}}} else {{")
            out += stmts(c["else"], ctx, task_name, indent + "  ")
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
            out += stmts(w["body"], ctx, task_name, indent + "  ")
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


def spec_fun_acsl(f: dict, funs: dict) -> list:
    """The recursive logic definition plus its measured termination lemmas
    (WP does not check logic-function termination itself; see docstring)."""
    env = {p["name"]: p["type"] for p in f["params"]}
    labeled = funs[f["name"]]["labeled"]
    lab = "{L}" if labeled else ""
    sig = []
    for p in f["params"]:
        if p["type"] == "seq":
            sig += [f"int *{p['name']}", f"integer {p['name']}_n"]
        else:
            sig.append(f"integer {p['name']}")
    body_ctx = Ctx(env, funs, ret=None, label="L")
    res = {"int": "integer", "bool": "boolean"}[f["result"]]
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
    twin_val = w.get("_twin")
    if is_pair:
        if not (isinstance(twin_val, list) and len(twin_val) == 2
               and all(isinstance(x, (bool, int)) for x in twin_val)):
            return None                # e.g. a pair with a seq component
    elif not isinstance(twin_val, (bool, int)):
        return None                    # no-value twins have no ground replay
    if CERT_FN in used or CERT_GOAL in used:
        return None                    # a task name would collide or forge
    if rett == "seq":
        return None                    # see the docstring above
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
                init = ", ".join(str(x) for x in vals) or "0"
                decls.append(f"  int {arr}[{max(len(vals), 1)}] = "
                             f"{{{init}}};")
                decls.append(f"  int *{p['name']} = {arr};")
                decls.append(f"  int {p['name']}_n = {len(vals)};")
                st[p["name"]] = vals
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
        _, dec = assigned_names(twin_body)
        names = [ret] + [d for d in dec if d != ret]
        if len(set(dec)) != len(dec) or set(dec) & set(st):
            return None                # flattening scopes would collide
        decls += [f"  {'struct ' + struct_name if is_pair and n == ret else 'int'}"
                 f" {n};" for n in names]
        body_out: list = []
        _cert_stmts(twin_body, Ctx(env, funs, ret=None, label="Here"),
                    st, task["name"], body_out, [0])
        if _tty(st.get(ret)) != _tty(w["_twin"]):
            return None                # replay disagrees with the witness
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
    certify)."""
    if w.get("_kind") != "undefined":
        return None
    names = {k: v for k, v in w.items() if not k.startswith("_")}
    # interp.py's own seq representation is a tuple; the witness's JSON
    # gives seqs as lists, so this is the one conversion point, mirrored
    # by `lower_verus.py`'s `_undef_obligation`.
    env_py = {n: (tuple(v) if isinstance(v, list) else v)
              for n, v in names.items()}
    ctx = Ctx(dict(env), funs, ret=None, label="Here")
    decls = []
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
                init = ", ".join(str(x) for x in vals) or "0"
                decls.append(f"  int {arr}[{max(len(vals), 1)}] = "
                             f"{{{init}}};")
                decls.append(f"  int *{p['name']} = {arr};")
                decls.append(f"  int {p['name']}_n = {len(vals)};")
            else:
                decls.append(f"  int {p['name']} = {_int_lit(int(v))};")
        ifuns = interp.funs_of(task, twin_body)
        st = interp.St()
        found = None
        for s in twin_body:
            if "var" in s:
                nm, e, ty = s["var"]["name"], s["var"]["init"], s["var"]["type"]
            elif "assign" in s:
                nm, e = s["assign"]
                ty = ctx.env.get(nm)
            else:
                return None                 # if/while/return: not walked
            ob = defs_t(e)
            if ob is not None and not interp.ev(ob, env_py, ifuns, st):
                found = ob
                break
            val = interp.ev(e, env_py, ifuns, st)
            if ty == "seq":
                return None                 # scope limit, see docstring
            if "var" in s:
                ctx = ctx.bind(nm, ty)
            env_py[nm] = val
            decls.append(f"  int {nm} = {_int_lit(int(val))};")
        if found is None:
            return None
    except (interp.Undef, interp.Budget, RecursionError, KeyError,
            ValueError, TypeError):
        return None
    goal = pred({"op": "not", "args": [found]}, ctx)
    lines = ["", "/*@ assigns \\nothing; */",
             f"void {CERT_FN}(void) {{", *decls,
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
            data_init = ", ".join(str(x) for x in data) or "0"
            off_init = ", ".join(str(x) for x in off)
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
            init = ", ".join(str(x) for x in vals) or "0"
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
    if kind == "value":
        return _value_certificate(task, twin_body, w, env, funs, used)
    if kind == "undefined":
        return _undef_certificate(task, twin_body, w, env, funs, used)
    if kind == "exit":
        return _exit_certificate(task, twin_body, w, env, funs, used)
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
    if is_nested_seq_type(rett):
        # NAMED REFUSAL, added 2026-09-10 (SPEC.md "Nested sequences").
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
            "no encoding in this lowering (the flat data+offsets "
            "encoding's CAPACITY machinery sizes one buffer against one "
            "bound, not a row-shaped offsets array against a second, "
            "data-dependent one); a seq<seq> PARAMETER, read via "
            "`len`/`at`, is supported")
    env = {p["name"]: p["type"] for p in task["params"]}
    env[ret] = rett

    funs = {}
    for f in task.get("spec_funs", []):
        funs[f["name"]] = {
            "params": f["params"], "result": f["result"],
            "labeled": any(p["type"] == "seq" for p in f["params"]),
            "is_task": False}
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
    if _has_wordcount(task) or _has_wordcount(body):
        header.append(T_WORDCOUNT_ACSL.rstrip("\n"))
    for f in task.get("spec_funs", []):
        header += spec_fun_acsl(f, funs)

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
    clauses += [f"  requires {pred(e, spec_ctx)};"
                for e in task.get("requires", [])]
    if "decreases" in task:
        clauses.append(f"  decreases ({term(task['decreases'], spec_ctx)});")
    if rett == "seq":
        # Only the return buffer's own elements are written; every seq
        # PARAM stays `\valid_read`-only and every scalar param/local is
        # a plain C local, never aliased into `ret`'s memory
        # (`\separated`, above).
        clauses.append(f"  assigns {ret}[0 .. {ret}_n - 1];")
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
               ("" if rett == "seq" else f"  int {ret};\n"))
    cfun_ret_ty = (f"struct {struct_name}" if pair_ty is not None else
                  "void" if rett == "seq" and not capacity_mode
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
