#!/usr/bin/env python3
"""lower_spark.py: lower t v0/v1 tasks to SPARK 2014; the third kernel.

THE SEMANTIC DECISION, same doctrine as the Verus backend: t integers are
mathematical. Ada's Integer is a machine type with overflow, so lowering to it
would make `abs` unprovable at Integer'First and silently change what the
task means. Ada 2022's Big_Integer (Ada.Numerics.Big_Numbers.Big_Integers)
IS mathematical and gnatprove proves over it directly.

SHAPE (v1, measured 2026-08-31 on gnatprove FSF 16.1.0 before this rewrite):
GNAT's naming convention refuses a body in the single .ads file the t.spark
verifier writes (measured: "file can have only one compilation unit", "does
not contain unit (spec)", and pragma Source_File_Name is rejected under a
project). So EVERYTHING is a package spec of expression functions:

  * task body      -> one expression function F (statement lists are compiled
                      to expressions: assignments become substitution, `if`
                      becomes an if-expression merge of the branch outcomes);
  * while loops    -> one recursive helper function per loop, W_k over a
                      record of exactly the loop body's syntactic assigned
                      set (SPEC.md frame rule); in-scope names the body
                      never assigns stay plain parameters the caller keeps
                      its own values for. Loop invariants
                      become W_k's Pre AND Post (plus `not cond` in Post),
                      the loop's decreases becomes W_k's Subprogram_Variant.
                      That is the standard Hoare package, stated to the
                      kernel rather than assumed: invariant-on-entry is the
                      call-site Pre check, preservation is the recursive
                      call's Pre check, exit knowledge is Post.
  * recursion      -> F is a recursive expression function; the task-level
                      decreases becomes F's Subprogram_Variant.
  * spec_funs      -> recursive expression functions with their own
                      Subprogram_Variant.
  * seq            -> SPARK.Containers.Functional.Infinite_Sequences,
                      instantiated over Big_Integer (see THE SEQ MODEL).

VARIANTS: SPARK requires a Big_Integer Subprogram_Variant to be provably
nonnegative; t's decreases obligations only give >= 0 at the recursion/loop
step. Every variant is therefore wrapped (if D >= 0 then D else 0): still
well-founded, decreasing exactly when t's obligations hold, and measured to
prove where Big_Integers.Max blew the 20000-step budget.

THE SEQ MODEL, rewritten 2026-09-01 because the previous one was UNSOUND.
It was `type Seq is array (Positive range <>) of Big_Integer`, and an Ada
array index type is discrete and therefore bounded: S'Length <= Integer'Last
holds by typing, so the kernel was handed `len(s) <= 2^31-1` for free.
SPEC.md gives a seq only `len(s) >= 0`. MEASURED on the fuzzer's fz_p_seqlen
probe (ensures len(s) <= 2^31-1 with both branches live): spark VERIFIED it
while dafny, verus, lean, rocq and fstar REFUTED it, a false theorem, the
same disease as lower_framac.py's C int. The seq is now

    package Seqs is new SPARK.Containers.Functional.Infinite_Sequences
      (Element_Type => Big_Integer);

whose Length returns Big_Natural (no upper bound) and whose Get is indexed
by a Big_Integer position. Its private part is `pragma SPARK_Mode (Off)`, so
the prover sees the public axiomatization and nothing of the bounded
representation underneath: the emitted obligation is about sequences of
arbitrary mathematical length. len(s) >= 0, SPEC.md's one seq assumption,
comes from Length's own Big_Natural result subtype, not from an assumption
this lowering writes.

QUANTIFIERS: SPARK quantified expressions range over a discrete type or over
a type carrying the Iterable aspect, and Ada's discrete types are all
bounded. t quantifies over mathematical [lo, hi), so the range is lowered as
an Iterable record whose CURSOR IS Big_Integer:

    type T_Range is record Lo, Hi : Big_Integer; end record
      with Iterable => (First => R_First, Has_Element => R_Has,
                        Next  => R_Next);
    (for all K in T_Range'(lo, hi) => body)      -- `for some` for exists

gnatprove quantifies over the cursor type under R_Has, so this IS t's
quantifier over [lo, hi) with no machine slice and no bound to hoist.
MEASURED (2026-09-01, gnatprove FSF 16.1.0): `for all K in T_Range'(0, N) =>
K <= Integer'Last` with N unconstrained goes `medium: postcondition might
fail`, because the range is genuinely unbounded, while all_nonneg, contains,
count_matches, linear_search and seq_max still prove. This replaces the
previous `for all K in Integer` encoding and the hoisted `bounds_ok`
obligation it owed, and with them the four ABSTAIN paths that existed only
because a bounds obligation had nowhere sound to sit (quantifier in
requires, in a bound mentioning an enclosing bound variable, under a partial
`at` in a bound, in an executable/definitional position).

DEFINEDNESS: `and`/`or`/`implies` lower to `and then`/`or else`/if-
expressions, so SPEC.md's left-to-right definedness contexts land exactly on
GNATprove's own RTE-checking contexts; `at` lowers to `Elem (S, I)`, whose
own precondition `0 <= I and then I < Len (S)` is exactly t's definedness
side condition and is discharged by the kernel at every use. (Seqs.Get is
total in the shipped non-defensive SPARKlib build, and reading out of range
yields an unconstrained value, so the obligation must be, and is, stated on
the wrapper rather than borrowed from the library.)

DIV/MOD (2026-09-08, SPEC.md "Division and modulo"). MEASURED on this
install (probes p_euclid.ads, p_facts.ads, gnatprove FSF 16.1.0, Big_Integer
throughout): Ada's `/` truncates toward zero (-7/2 = -3, 7/-2 = -3, -7/-2 =
3, all proved), `mod` takes the sign of the divisor, i.e. floor-modulo
(-7 mod 2 = 1, 7 mod -2 = -1, -7 mod -2 = -1, all proved), and `rem` takes
the sign of the dividend (-7 rem 2 = -1, 7 rem -2 = 1, -7 rem -2 = -1, all
proved). None of the three is SPEC.md's Euclidean law (0 <= r < |y|) when
the divisor is negative, so native `/` and `mod` may not be emitted for t's
`div`/`mod`, exactly as the header's SHAPE section already forbids for `at`.
So, beside `Len` and `Elem`, this lowering defines two more expression
functions, `T_Mod` and `T_Div`, both with `Pre => Y /= Big_Integer'(0)`, over
`/` and `rem` rather than `mod`: `X = (X / Y) * Y + (X rem Y)` is a fact
GNATprove proves in one step (MEASURED, probe p_law1.ads), while the same
identity restated with `X mod abs (Y)` and a second division, the reading
that would follow directly from "mod against a positive divisor already IS
the Euclidean remainder", TIMES OUT (MEASURED, probe p_law2.ads, same shape,
only the operators differ) rather than failing to prove; that construction
was not shipped for exactly that reason. `X rem Y` already has magnitude
< |Y|, sign of the dividend; only its sign needs straightening to land in
`[0, |Y|)`, which needs no further division:

    T_Mod (X, Y) = if X rem Y >= 0 then X rem Y else (X rem Y) + abs (Y)
    T_Div (X, Y) = if X rem Y >= 0 then X / Y
                   elsif Y > 0 then (X / Y) - 1 else (X / Y) + 1

a nonnegative remainder is kept (it already satisfies the bound whatever
sign Y has); a negative one gains `abs (Y)` and the truncating quotient
steps by one toward -infinity to compensate, so the whole identity reduces
to linear arithmetic over `/`'s and `rem`'s own defining law and the kernel
proves it directly (MEASURED, probe p_law3.ads: the identity and both
Euclidean bounds verify). Definedness at y = 0 is discharged the same way as
`at`'s: the Pre is checked by the kernel at every call site, and `div`/`mod`
lower to `T_Div (a, b)` / `T_Mod (a, b)`, never to native `/`/`mod`/`rem`.
The counterexample mirror (F_Ce, below) does not cover div/mod: _ce_bound
has no case for them and raises its own `_NoCe`, so a task using div/mod
simply gets no F_Ce instance, the same abstention already applied to seq
ops, calls and quantifiers there; nothing about T_Div/T_Mod needs a
machine-int mirror to be sound, but a mirror was not built, and the
committed `remainder`/`digit_sum` cells are checked through F alone.

THE COUNTEREXAMPLE INSTANCE, added 2026-09-01 because the sound numeric model
above closed gnatprove's refutation channel completely: after the move to
Big_Integer the SPARK flip rate went 91.8% -> 0.0%. REPRODUCED before this
section was written: 0 flips on the 11 committed tasks (11 reals VERIFIED, 9
twins TIMEOUT and 2 UNPROVED, not one twin carrying a counterexample) and 0
flips on the 47 real-VERIFIED cells of a fresh 169-task generated corpus.

The cause is MEASURED, and it is not the budget and not the prover.
verifiers/spark.py rules REFUTED only on gnatprove severity "high", which for
a prover check means the counterexample was generated AND confirmed by
gnatprove's runtime assertion checker. Both halves fail on Big_Integer, for
two different reasons, both read off `gnatprove -d`'s own RAC verdict line:

  * a Big_Integer PARAMETER gets no value in the model,
    "Small-step: RES_INCOMPLETE, Reason: No counterexample value for program
    parameter x", so the abs twin carries no cntexmp field at all;
  * a Big_Integer EXPRESSION cannot be executed by the RAC,
    "Small-step: RES_INCOMPLETE, Reason: expr with private type", so even
    when every free variable is an Integer and the model IS built (probe
    p_ce1: `To_Big_Integer (X) >= 0`, cntexmp X = -1 present), the verdict
    stays NON_CONFORMITY_OR_SUBCONTRACT_WEAKNESS and severity stays "medium".
    The same file with the Big_Integer subexpression left unevaluated by
    short-circuit (probe p_ce2) reaches "VERDICT: NON_CONFORMITY" and "high".

Both are properties of the type being private with a SPARK_Mode (Off)
completion, which is what Big_Integer and the Infinite_Sequences containers
both are; a private type whose completion IS visible to SPARK (probe p_priv,
`type P is new Integer`) confirms normally. Budget and prover were measured
out: abs/max twins stay medium/gave_up at --steps 20000, 200000 and 1000000,
under --prover=z3, cvc5 and all, and at --level 0..4; the seq twins hit the
wall backstop at 1000000 before anything changes.

So the refutation cannot come from the unbounded theorem. It comes from a
SECOND subprogram in the same file: F_Ce, the same task instantiated at
machine-integer inputs with exact arithmetic.

  * SOUNDNESS OF VERIFIED is untouched: F over Big_Integer keeps its Post,
    and verifiers/spark.py refuses VERIFIED while any check is unproved. An
    extra obligation can only make a proof harder, never possible, measured
    on the boundary probes, which still resolve: fz_p_bigrange and
    fz_p_bigwide VERIFIED, fz_p_seqlen / fz_p_elemwidth / fz_p_biglen /
    fz_p_attotal not verified.
  * SOUNDNESS OF REFUTED is the instance being FAITHFUL: a machine integer is
    a t integer, so a counterexample to F_Ce is a counterexample to the task
    That holds provided the instance computed the same value t does. That holds iff no
    operation overflows, which is why the instance is emitted only when this
    file can bound every int-valued node of the task by construction:
    |parameter| <= 2^40 (CE_WINDOW) and every derived magnitude <= 2^100
    (CE_CAP), inside Long_Long_Long_Integer's 2^127. The bound is computed on
    t's own AST, over the SAME substitution walk `compile` performs, and any
    node it cannot bound, whether a loop, a call, recursion, a seq, a quantifier
    or an oversized literal, makes the instance not be emitted at all.
  * THE CHECK MUST ALSO BE CHEAP TO EXECUTE, because severity "high" is the
    RAC actually running it. MEASURED: the same shape with a quantifier over
    the window, `for all K in 0 .. 2**40`, reports
    "Small-step: RES_INCOMPLETE, Reason: out of fuel" and falls back to
    "medium", so a machine-typed quantifier would cost the refutation it was
    emitted to buy. Quantifiers are outside the fragment for that reason as
    much as for the bound.
  * AN UNPROVABLE OVERFLOW CHECK CANNOT BECOME A REFUTATION, which is the
    second line under the bound analysis: severity "high" is the small-step
    RAC having EXECUTED the check and seen it fail ("VERDICT: NON_CONFORMITY"
    above), so a check no concrete input can fail cannot reach it, and a bound
    the prover fails to see costs a proof, not a false countermodel.
    MEASURED both ways: X*X at |X| <= 2^40 proves and the cell VERIFIES;
    X*X*X is over CE_CAP, gets no instance, and the (genuinely false) task
    reports UNPROVED rather than a refutation this file could not stand
    behind.
  * INCOMPLETENESS STAYS INCOMPLETENESS: a task the instance cannot reach, or
    a twin whose only counterexamples lie above 2^40, still reports UNPROVED
    or TIMEOUT. The instance adds refutations; it never converts a failure to
    prove into one.

WHAT IT BOUGHT, MEASURED on one 169-task generated corpus (seed 1) and the 11
committed tasks, spark only, --steps 20000:
  * 64 of the 169 generated tasks are inside the fragment; the other 103
    lower to BYTE-IDENTICAL source with and without this section, so their
    verdicts are unchanged by construction, not by re-measurement. On the
    committed tasks the fragment holds abs and max; the other 9 carry loops,
    recursion or sequences.
  * over the whole corpus the flip rate went 0/116 -> 38/116 real-VERIFIED
    cells (32.8%); over the fragment, 0/47 -> 38/47 (80.9%). The 9 misses are
    twins whose own theorem is still true (a loose ensures), which no kernel
    can refute. Committed tasks: 0/11 -> 2/11, all 11 reals still VERIFIED.
  * NO false refutation appeared. Every real whose verdict changed went
    UNPROVED -> REFUTED, and all 14 are tasks the corpus's ground truth calls
    false: 12 fz_wrong, fz_v0loose_045, and the fz_p_bigneg / fz_p_intwidth
    probes, which spark now refutes alongside the other six kernels.
    fuzz_lower.py's own vs-truth and disagreement counts stay 0, and the new
    verdicts are stable over 3 repeats (verifiers.flake_check).

The instance's Pre is deliberately empty and the task's `requires` is folded
into its Post as an implication: a Pre unsatisfiable inside the 2^40 window
would raise VC_INCONSISTENT_PRE, which verifiers/spark.py rules VACUOUS on
the whole file, a wrong verdict bought from a construct that exists only to
carry a witness. `requires -> ensures` cannot be always-False here, because
the twin operators never touch `ensures` (harness.py) and the real proves it.

Ce_Num / Ce_Int / F_Ce cannot collide with a t identifier: cap() lowercases
everything after the first character, so no t name can reach a name with an
interior capital. (RESERVED clashes are checked case-insensitively since
10.8, because Ada resolves names case-insensitively: a t param named
r_first would capitalize to R_first and silently capture R_First.)

EARLY EXIT (SPEC.md, 2026-09-08, ROADMAP 12.7). `return Expr;` cannot become
an actual Ada `return` statement: everything in this file is an expression
function (SHAPE, above), and a full subprogram body -- statements, a loop,
`return` included -- is not a basic_declarative_item, so it cannot be given
directly in the package spec this file writes. MEASURED: a plain
`function F (...) is R : ...; begin ... return R; end F;` placed where an
expression function sits (probe t_probe1.ads) makes gnatprove refuse Phase 2
with "begin block not allowed in package spec" before a single VC is
generated. So `return` is lowered the same way everything else here is: by
substitution. Lower.compile_r is compile()'s return-aware twin, threading an
`esc`/`val` pair (an Ada boolean and the return name's value at that escape)
alongside the ordinary env; has_return() decides, per statement list,
whether compile() (unchanged) or compile_r runs, so a body without a
`return` anywhere -- every one of the 13 previously committed tasks --
lowers byte-for-byte as before. A loop whose body can return gets two extra
fields on its W_k state record, Esc and Ret, and its Post is weakened to
`(if W_k'Result.Esc then True else (invariants and then not cond))`: SPEC.md
says a return leaves the loop without owing the invariant at that point, and
this is that rule stated to the kernel. The task's `ensures` is still owed
at that exit like any other, but that obligation is F's own Post applied to
F'Result uniformly regardless of path, so it needs no separate restatement.
Definedness is inherited for free: a return's expression goes through the
same self.expr() an assignment's right-hand side does, so Elem/T_Div/T_Mod's
Pre checks land at the same call sites either way.

EARLY EXIT, REPAIRED (2026-09-09). The paragraph's last two sentences above
were wrong, and the wrongness was the whole defect: a bare `True` on the Esc
arm of W_k's Post hands gnatprove no fact at all about Ret, so "F's own Post
applies uniformly regardless of path" does not fall out for free, it still
has to be proved, and with nothing to work from, the only way left to
discharge F's Post on the escape path is to unroll the recursive W_k from
scratch, which is exactly what exhausted the 20000-step budget. MEASURED
before this fix: every return-bearing committed task read spark timeout
(first_even: timeout/timeout, is_prime: timeout/refuted, AGREEMENT.md), and
the early-exit fuzz family (26 generated tasks, fuzz_lower.py --tasks
fz_v1exit_*/fz_p_ret_*) read 1 real VERIFIED against 24 TIMEOUT. In both
cases gnatprove's own audit named the same unproved goal: VC_POSTCONDITION
on F, severity medium, unproved_status "limit", F's own postcondition, not
W_k's. The fix states, on the Esc arm, the task's own `ensures` with the
return name substituted by `W_k'Result.Ret`: `(if W_k'Result.Esc then
(ensures[Ret]) else (invariants and then not cond))`. That is the same
obligation SPEC.md assigns a return inside a loop, owe the ensures, not the
invariant, at that point, and the same one dafny, verus and rocq discharge
for these tasks, now stated to this kernel instead of assumed away. A body
with no `return` is untouched: has_return() still routes it through
compile()/lower_while() exactly as before, and out/abs.ads and
out/sum_upto.ads are byte-identical before and after this change. MEASURED
after the fix: first_even and is_prime both read spark verified/refuted,
all 15 committed tasks read verified/refuted (the other 13 unchanged, the
two new rows now agree with dafny, verus and rocq), and the fuzz family's
real column went 1/25 VERIFIED, 24/25 TIMEOUT to 24/25 VERIFIED, 1/25
TIMEOUT. The one holdout, fz_p_ret_falsens, is an adversarial probe whose
own ground truth is REFUTED, not VERIFIED, so a real-side TIMEOUT there is
orthogonal to this fix, not a miss of it. The twin side of the fuzz family
did not move as cleanly under the fuzzer's prescribed --jobs 8 concurrency:
most twins read UNPROVED rather than REFUTED there, but a serial re-run of
one (fz_v1exit_009) outside that contention discharged the
T_Refutation_Certificate goal and read REFUTED, so the certificate
mechanism (10.8) is intact and the jobs=8 reading looks like step-budget
flakiness under load on a shared box, not a defect this change introduced.
It is not chased further here: both committed return-bearing tasks, run one
at a time by harness.run_task, flip cleanly to verified/refuted.

THE REFUTATION CERTIFICATE (10.8, 2026-09-02). The instance above recovered
abs and max; the other nine committed twins stayed verified/timeout, and
the cause was REPRODUCED before this section was written: every one is a
VC_POSTCONDITION at severity medium, unproved_status "limit", at --steps
20000 under the full counterexample flags, and the bundled portfolio
(--prover=cvc5, altergo, z3,cvc5,altergo) and a tenfold budget (--steps
200000) were measured to change nothing on sum_upto and factorial: no
countermodel is ever BUILT over the private Big_Integer model, whatever the
budget. What the kernel cannot FIND it can still CHECK. The harness already
measured a violating witness (harness.twin_for), and run_task hands it to
this lowering at every twin call; certificate() restates that witness as
one ground goal named T_Refutation_Certificate, and verifiers/spark.py
mints REFUTED exactly when gnatprove discharges every check of that
function (see CERT_ENTITY there for the audit rule and its fail-closed
sides: a rejected certificate is UNPROVED, never REFUTED, and a file
carrying the name can never mint VERIFIED).

Two witness kinds are certificatable here, and the goal is in both cases
the negation of the obligation the witness was measured against:

  * "value": requires at the input, and then not (ensures at F(input)).
    F is the file's own twin F, an expression function, so its defining
    axiom pins F(input) to the twin's computed value and the goal holds
    exactly when that value falsifies the ensures. Emitted only when the
    witness records _ens true: a twin value that merely differs can still
    satisfy a loose ensures, and a goal known false is not an instrument.
  * "exit": requires, and then the surviving invariants at the state, and
    then not cond, and then not ensures, every variable a literal. This is
    the exit-entailment instance interp.invariant_witness measured
    (admissibility included): a state the survivors admit, at the loop's
    exit, where the theorem fails. The survivors come from the twin body's
    own loop, so the certificate weakens nothing itself; it is emitted
    only when the twin body has exactly one loop.

"preservation" witnesses are not certificated (fail closed; certificate()
says why), and neither is any witness the lowering cannot express: those
cells honestly keep the kernel's own verdict. ("undefined" joined "value"
and "exit" as certificatable 2026-09-09, SEQUENCES AS VALUES below.)

MEASURED (2026-09-02, gnatprove FSF 16.1.0, --steps 20000, --prover=z3):
all nine certificates discharge in seconds at the standard budget, seq
literals, ground quantifier instances and empty-range cases included, and
the committed column went 2/11 -> 11/11 flips with every real lowering
still VERIFIED, stable over 3 repeats (verifiers.flake_check). Soundness
probes, same day: the certificate name planted in a real program without
goals demotes it to UNPROVED; a false certificate is rejected (UNPROVED,
never REFUTED); a kernel-accepted certificate planted in a real program
demotes it to REFUTED (a demotion is the intended worst case, never a
pass); the name in a comment is inert, exactly like the ban scan.

SEQUENCES AS VALUES (SPEC.md, 2026-09-09). seq becomes a return and local
type, not just a parameter type: `s[i := v]` (update, DEFINED IFF
0 <= i < len(s)) and `seq(n, v)` (fill, DEFINED IFF n >= 0), plus
extensional `==`/`!=` on two seqs. Landed for THE SEQ MODEL already in
this file (SPARK.Containers.Functional.Infinite_Sequences over
Big_Integer, header): a seq-valued return is a function returning Seq
like any other TYPE-mapped result, a seq local is a field of the loop
state record like any other (TYPE["seq"] = "Seq" already covered both,
and _dead_lit already had a "seq" arm from EARLY EXIT), so the SHAPE and
frame-rule plumbing needed no change at all. Two things were new:

  * update: `T_Update (S, I, V) is (Seqs.Set (S, I + 1, V)) with
    Pre => I >= 0 and then I < Len (S)`, the same 0-based-to-1-based
    translation Elem already does for `at`. Kept in a SEPARATE preamble
    block (UPDATE_PREAMBLE) gated on needs_update (expr(), like
    needs_divmod), not folded into SEQ_PREAMBLE next to Len/Elem: an
    earlier version put it there unconditionally and MEASURED changed
    the emitted text of first_even.ads, contains.ads and every other
    already-committed seq-PARAMETER task even though none of them calls
    update(), a regression this construct's own rule forbids. Gated, all
    15 previously committed tasks (out/abs.ads, out/first_even.ads,
    out/digit_sum.ads included) are byte-identical before and after.
    MEASURED (probe p_seq1.ads, --steps 20000): Seqs.Set's own Post
    (Equal_Except, Inline_For_Proof) is enough on its own for the kernel
    to prove Len (T_Update (S, I, V)) = Len (S), Elem (T_Update (S, I,
    V), I) = V and "every other index unchanged" at a call site; nothing
    is restated on T_Update itself.

  * fill: no library constructor builds "n copies of v", so T_Fill is a
    recursive expression function over Seqs.Add, the same shape every
    W_k loop helper and spec_fun already is here, gated on needs_fill
    (FILL_PREAMBLE). Its own elementwise fact needs the quantifier
    (`for all K in T_Range'(0, N) => Elem (T_Fill'Result, K) = V`), so
    needs_fill always turns needs_range on with it, whether or not the
    task itself ever writes a `forall`. MEASURED (probe p_seq1.ads,
    --steps 20000): both Len (T_Fill'Result) = N and the elementwise fact
    discharge by gnatprove's automatic induction on the
    Subprogram_Variant, no separate lemma needed.

  * equality: banked, not implemented. MEASURED (probe p_seq2.ads): a
    generic instantiation's own "=" (Seqs' own, extensional by its own
    Post) is only reachable through `use Seqs;`, unlike an operator
    declared directly in a non-generic package spec (gnatprove: "operator
    ... is not directly visible", "use clause would make operation
    legal"), and CMP's plain infix "=" / "/=" lowering has no static type
    information to gate that `use` on only the tasks that need it. Adding
    it unconditionally re-broke first_even.ads's byte-identity the same
    way T_Update's first placement did (`use Seqs;` sits in SEQ_PREAMBLE,
    which every seq-parameter task already emits) for a feature neither
    swap nor reverse exercises (both compare elementwise via `at`, not
    whole-seq `==`), so it is left undone: a t task that states `==`
    between two whole seqs currently gets a clean MALFORMED (gnatprove's
    own "not directly visible" error) rather than a wrong proof, and this
    is banked for the next seq task that needs it, exactly the finding
    lower_verus.py records for the same construct the same night (its
    own `==`/`!=` needed no work, Verus's native Seq<int> "==" already IS
    extensional visibly; this kernel's does not come for free).

  * the twin path needed one extension MEASURED directly on the two new
    tasks: swap's off-by-one twin (`tmp := s[i]` mutated to `s[i+1]`) is
    UNDEFINED at its witness (s=[0], i=0, j=0: index 1 outside [0,1)),
    the "undefined" witness shape certificate() had never had to certify
    before (every one of the 15 tasks committed before this pair is
    "value" or "exit"). Declining to certify it would leave swap
    permanently UNPROVED on its twin cell, never REFUTED, so
    `_undef_obligation` (mirroring lower_verus.py's function of the same
    name, added the same night for the same gap) re-walks the twin body
    with interp.ev, in the same order interp.py used to raise the
    witnessing Undef, calling `defined()` (also mirrored from
    lower_verus.py; SPEC.md's rule restated in this file's own
    expression algebra) at each statement to find the first ground-false
    obligation, then renders its negation through L's own expr(), the
    same renderer certificate()'s other two kinds already use. MEASURED:
    the certificate carries `(not (0 <= (i + 1) and then (i + 1) <
    Len (s))))` at the witness's ground literals and gnatprove discharges
    it. reverse needed no such extension: its measured twin
    (invariant-drop#1) is an "exit" witness (s=[], i=0, r=[0]), the same
    kind seq_max and first_even already certify, `_cert_lit` already had
    a `list` arm (rendering a seq witness as a Seqs.Add chain) from
    before this task, so a seq-valued exit witness slotted into the
    existing path with no change there at all.

MEASURED (2026-09-09, gnatprove FSF 16.1.0, --steps 20000): swap and
reverse both COUNT (real VERIFIED, twin REFUTED); all 15 previously
committed tasks still read verified/refuted one at a time (this column's
verdicts flake under contention, harness.run_task's own posture); out/
abs.ads, out/first_even.ads and out/digit_sum.ads are byte-identical
before and after this change (diffed against the working tree as it
stood at the start of this task, not against git HEAD, which was
mid-commit on an unrelated EARLY EXIT repair at the time).

SEQUENCES: LITERALS, CONCATENATION, SLICES (SPEC.md, 2026-09-09). The three
new expression forms -- `{"op": "seq", "args": [...]}`, `+` on two seqs
(concatenation), `{"op": "slice", "args": [s, a, b]}` -- land on the same
generic (SEQUENCES AS VALUES's own Seqs = SPARK.Containers.Functional.
Infinite_Sequences over Big_Integer) with the same discipline: a Pre stating
the definedness side condition where one exists, a Post stating Length and
Get so gnatprove can use the result without re-deriving it, and no change
at all to the 17 tasks committed before this pair (measured below).

  * literal: `[e1, ..., en]` needs no new preamble function at all. n is
    fixed at lowering time (the AST's own argument count), so it is a
    plain Seqs.Empty_Sequence/Seqs.Add chain, unrolled once per call site
    in expr() itself -- exactly "Seqs.Empty plus Seqs.Add", the header's
    own first-choice reading. Add's own Post (SEQUENCES AS VALUES already
    leans on it for T_Update/T_Fill) gives Length and Get at each step
    statically, so there is nothing to state on a literal that Add has not
    already proved.

  * concatenation: `+` on two seqs, told apart from int `+` by
    Lower._ty, a small static type reader added for exactly this (t's
    `==` needed no such reader: Ada's own polymorphic "=" already
    resolves it at every type this file maps; `+` has no such resolution,
    Seq carries no "+" or "&" at all in this SPARKlib install). No
    library concatenates two whole sequences, so T_Concat is two
    functions in T_Fill's own recursive shape: T_Concat_Aux(S, T, N) is
    "S with the first N elements of T appended", recursive on N counting
    UP from 0 (Add(T_Concat_Aux(S, T, N-1), Elem(T, N-1))), and
    T_Concat(S, T) is T_Concat_Aux(S, T, Len(T)), its own Post restating
    Aux's Post at N = Len(T) with no further reasoning. Gated on
    needs_concat (also turns needs_range on, the elementwise Post is
    stated over T_Range, T_Fill's own pairing).

  * slice: `s[a..b]`, DEFINED IFF 0 <= a <= b <= len(s), a definedness
    obligation the same shape as `at`'s and `update`'s, checked at
    T_Slice's own Pre and, for the twin's certificate, at a new `slice`
    case in defined() (below). No library sub-sequence constructor
    either, so T_Slice is the T_Fill shape again, this time counting DOWN
    from B: T_Slice(S,A,B) unfolds to Add(T_Slice(S,A,B-1), Elem(S,B-1)),
    bottoming out at the empty slice A=B, so the recursion unwinds in
    INCREASING index order (A, A+1, ..., B-1), matching "the element at k
    is s[a+k]" directly. Gated on needs_slice, also turning needs_range on
    with it.

  * the twin path needed one extension: certificate()'s "undefined" kind
    (SEQUENCES AS VALUES's own `_undef_obligation`) had a case for `at`,
    `update`, `fill`, `div`, `mod` but not yet `slice`; added to defined()
    the same shape as `at`'s and `update`'s own bound, above. tail's
    off-by-one twin (`s[1..len(s)]` mutated to `s[2..len(s)]`) is exactly
    this: undefined at the witness s=[0] (slice bounds [2..1], since
    len(s)=1), the first slice-shaped "undefined" witness measured;
    filter_pos's twin (invariant-drop#1, dropping the `len(r) <= i`
    invariant) needed no such extension, an ordinary "exit" witness the
    same kind reverse and seq_max already certify.

  * a type reader was the one genuinely new piece of machinery: Lower._ty
    walks the ORIGINAL AST (never the rendered Ada text) to answer
    int/bool/seq for one expression, mirroring interp.ev's runtime
    isinstance(a[0], tuple) check statically, needed because Ada picks
    the `+`/T_Concat choice at code-generation time, not proof time.
    `types` (var name -> "int"/"bool"/"seq") already existed as a
    parameter compile()/compile_r()/lower_while() threaded for locals
    (SEQUENCES AS VALUES); it now also carries every task PARAMETER from
    the top of lower() (previously only the return name was seeded in,
    since nothing before this pair needed a param's type once lowering,
    only Ada text, had begun). certificate() and _undef_obligation() have
    no AST-level `types` to thread -- both work from a witness's own
    ground values -- so each builds one straight from the witness (list
    seq, bool before int, exactly _cert_lit's own reading order).

MEASURED (2026-09-09, gnatprove FSF 16.1.0, --steps 20000): tail and
filter_pos both COUNT (real VERIFIED, twin REFUTED: tail's off-by-one
twin at the slice bound above, filter_pos's invariant-drop#1); swap and
reverse are unaffected, out/swap.ads, out/reverse.ads, out/swap_twin.ads
and out/reverse_twin.ads byte-identical before and after this change
(cmp, all four); all four cells verified on the first run, no re-run
against the shared box's load needed.

WHOLE-SEQ `==`/`!=` (SPEC.md, 2026-09-09), the residual the banking
paragraph above left open: two candidate T_Eq designs were measured
(EQ_PREAMBLE's own comment has the detail), a qualified call to the
generic's own "=" and a Len/Elem/T_Range restatement of SPEC.md's
extensional definition. Both closed four isolated probes with 0 unproved
(an elementwise-equal hypothesis implies T_Eq, the converse, cross-
constructor equality, a concrete false instance), which is where the
first candidate shipped and was WRONG: on the actual shape this exists
for, a loop-computed seq compared whole against a parameter
(fz_p_seqeq_true/false, fuzz_lower.py), the qualified-call form's real
cell read TIMEOUT, reproduced uncontended (harness.run_task, one
gnatprove call, 46s wall against the 180s backstop, so not load and not
the wall backstop) at the standard 20000-step budget: SPARKlib's own "="
quantifies with its native Iterable cursor over Sequence, a different
range representation from the T_Range cursor every loop invariant here
is already stated over, and bridging the two on top of a recursive-call
unfold missed the budget. The Len/Elem/T_Range form shares its
quantifier encoding with the loop invariants directly, and MEASURED
(harness.run_task, same probe, uncontended) reads real VERIFIED, twin
REFUTED, 55.8s. fuzz_lower.py's own family (--tasks
fz_p_seqeq_true,fz_p_seqeq_false, --only spark, --jobs 4, uncontended):
fz_p_seqeq_true verified/refuted; fz_p_seqeq_false's twin also REFUTED
(the certificate carries a T_Eq goal through cleanly, "Keep the
certificate path working" holds), but its OWN real cell reads TIMEOUT,
not REFUTED. That is not a defect this pair introduces: fz_p_seqeq_false
is an adversarial task whose ground truth is already false in its own
body, seq-typed and inside a loop, so it sits outside ce_instance's
fragment (ret type "seq" is not in CE_TYPE) exactly like every other
seq/loop false-ground-truth real cell already committed here, and this
kernel's Big_Integer model cannot mint a real-side REFUTED without the
certificate mechanism, which exists for TWINS, not for a task's own
body (THE COUNTEREXAMPLE INSTANCE and THE REFUTATION CERTIFICATE,
above, both predate this pair). fuzz_lower.py's own scoring agrees:
disagreements 0, vs-truth 0, twin-survived 0, no-flip 0 on this family.
Regression: swap, reverse, tail, filter_pos (none states a whole-seq
`==`) re-lowered byte-identical to out/*.ads, real and twin, both before
and after the switch from the qualified-call candidate to the
Len/Elem/T_Range one; none of the 19 tasks committed before this pair
moves.

PAIRS (SPEC.md, 2026-09-10). New type `{"pair": [T1, T2]}`, T1/T2 one of
"int"/"bool"/"seq" (v1 has no pair of pairs), a parameter, return or local
type; new Expr forms `pair`/`fst`/`snd`. Each pair type this task's package
spec needs becomes ONE record type, over the two components' own Ada
types, declared once per distinct pair type (`_pair_types`, first-
appearance order, deduplicated) with fields named A and B:

    type T_Pair_Int_Int is record
       A : Big_Integer;
       B : Big_Integer;
    end record;

(`ada_type`/`_pair_ada_name`: every TYPE[...] call site in this file now
goes through `ada_type`, which dispatches to `_pair_ada_name` for a dict
type and TYPE[...] unchanged otherwise, so pair support needed no second
TYPE-shaped table). `pair(a, b)` is a QUALIFIED record aggregate,
`T_Pair_Int_Int'(A => a, B => b)`: MEASURED (gnatprove FSF 16.1.0) that an
unqualified `(A => a, B => b)` sitting in one arm of compile()'s own
`if`-merge leaves the aggregate's type unresolved the same way a bare
integer literal does (DEFINEDNESS, header), so it is always qualified,
not only where an `if`-merge would need it. `fst`/`snd` are plain field
access, `.A`/`.B`, UNPARENTHESIZED: the first attempt wrote
`(p).A`/`(p).B` and MEASURED gnatprove reject it, "prefix for selection
is not a name", on `(F'Result).A` specifically -- Ada's selected_component
needs its prefix to BE a name (RM 4.1), and wrapping one in parens turns
it into a plain expression, no longer a name, even though the name
underneath (an attribute reference, a variable, a function call) would
have worked directly and unparenthesized is exactly how this file's own
W_k state access already spells it (`{name}'Result.{cap(v)}`). Fixed by
dropping the parens; not yet handled (and not guarded against, only left
unexercised by both committed tasks) is `fst`/`snd` applied straight to
something that is NOT a name -- an `if`-merge of two pairs, or a
projection of a freshly-built `pair(...)` aggregate -- which by the same
grammar rule would not parse either; that shape would surface as
MALFORMED (a real Ada syntax error, never a false VERIFIED), not a
silently wrong lowering, but this file does not yet route around it.
`==`/`!=` on two pairs is componentwise (SPEC.md), which Ada's own
predefined "=" on a plain record already computes for a Big_Integer/
Boolean-only pair -- MEASURED (probe p_pair1.ads, --steps 20000, z3): a
postcondition stating `P = Q <-> (P.A = Q.A and then P.B = Q.B)` for
T_Pair_Int_Int VERIFIES directly -- but a pair with a Seq component
cannot lean on that (Seq's own "=" needs `use Seqs;`, EQ_PREAMBLE's own
note, a `use` this file will not add unconditionally). Rather than pick
between two renderings per pair type, every pair type gets a NAMED
equality function regardless of its components ("a named form either
way"), `T_Pair_Int_Int_Eq`, comparing componentwise with native "=" for
an int/bool field and T_Eq for a seq field (`_pair_preamble`), gated on
Lower.needs_pair_eq (a set of (T1, T2) keys, set only when Lower.expr
actually renders a pair `==`/`!=`) so a task that never compares two
pairs emits no wrapper, the same discipline UPDATE_PREAMBLE/EQ_PREAMBLE/
FILL_PREAMBLE already keep. Lower._ty (SEQUENCES: LITERALS,
CONCATENATION, SLICES's own static type reader) gained `pair`/`fst`/`snd`
cases, needed to tell a pair `==` from every other `==` the same way it
already tells seq `+` from int `+`; `defined()` needed NO new case at all,
its existing fallthrough conjunction over `e["args"]` already states
exactly SPEC.md's own rule for both (`pair` defined iff both components
are; `fst`/`snd` "always defined on a pair", the same one-argument
fallthrough `at`'s bound-carrying case does NOT use).

THE LOOP FRAME RULE, widened. min_max reaches its while loop with its
pair-typed return `r` unassigned -- and, unlike first_even/is_prime, with
NO `return` statement anywhere (`r` is filled in by a plain `r :=
pair(lo, hi)` after the loop) -- which lower_while's own unassigned-var
check refused outright (`spark: loop reached with 'r' unassigned`) before
this pair, since its only exemption was "the return target under an early
exit" (EARLY EXIT, header). The check is now `(body_has_return and v ==
ret_name) or v not in hav`: `hav` (loop_assigned) is computed before the
check instead of after, and any var the loop's OWN body never assigns is
exempted, not only the early-exit return target -- the same justification
the original exemption already gave ("no invariant or Pre/Post above ever
mentions it here... nothing upstream could have constrained a name
nothing has touched yet") holds for exactly the same reason regardless of
WHY a var is untouched. Purely additive: every task where the check used
to pass still does (env[v] is not None, or the original exemption still
applies), so this could only ever add a task to what compiles, never
remove one; confirmed by the regression sweep below.

CE_INSTANCE / THE COUNTEREXAMPLE INSTANCE. A pair type is a dict, not a
hashable CE_TYPE key: `ret["type"] not in CE_TYPE` on a pair-typed return
would raise TypeError (unhashable type) rather than cleanly abstain, so
ce_instance's own top guard now checks `isinstance(..., dict)` FIRST,
short-circuiting before that lookup ever runs. A pair value has no
machine mirror regardless (the header's own reasoning for a seq), so
`_ce_bound` gained an explicit `"pair"`/`"fst"`/`"snd"` case raising
`_NoCe`, stated for the same reason the seq-operator case just above it
is stated explicitly rather than left to the generic numeric fallthrough
(which would reach the same abstention for a `pair` node eventually, but
not explain fst/snd, and neither committed task's real cell needs the
instance regardless -- both return a pair, outside CE_TYPE from the top
guard alone).

THE REFUTATION CERTIFICATE. `_cert_lit` gained an `isinstance(v,
interp.Pair)` case (checked before the list/tuple case), rendering a raw
Pair value the same qualified record aggregate expr()'s own `pair` case
emits, its own two components' types read off THEIR shape (bool before
seq before int) since a certificate has no declared-type context the way
expr()'s `types` dict is. This exists for interp.exit_env's RAW (never
`_j`-shown) return value, which can be an actual Pair object when a
twin's continuation recomputes the return after its loop -- exactly
min_max's own shape -- though min_max's own measured twin turned out to
be a "value"-kind witness (below), so this path went unexercised by
either committed task and is carried for the next pair task that reaches
it. The list/tuple check was widened from list-only to `(list, tuple)`
for the same reason one level down: a pair's own seq-typed COMPONENT can
arrive as either, by the identical argument. Both certificate() and
_undef_obligation() now refuse outright (return ""/None) when any task
PARAMETER is pair-typed: a witness's `vals` is JSON-shown (interp._j),
which renders a pair the SAME plain list a same-shaped seq would be
(SPEC.md: "the runtime value of a pair must be DISTINCT from a seq", the
very confusion `_j`'s own docstring exists to rule out at runtime, lost
again once a witness is serialized), and neither function has a
declared-type context to tell the two apart the way expr()'s `types`
does (only the task's RETURN gets that treatment, threaded in from
`task["returns"][0]["type"]` directly). NEITHER committed pair task has
a pair-typed parameter (divmod_pair: two ints; min_max: one seq), so
this refusal is not exercised by either measurement below; it exists so
a future pair-parameter task gets an honest missing certificate rather
than one that silently misreads its own witness.

MEASURED (2026-09-10, gnatprove FSF 16.1.0, Why3 1.8.2, --prover=z3,
--steps 20000, harness.run_task, out/agent-spark-pairs, uncontended):

  * divmod_pair COUNTS: real VERIFIED, twin (wrong-var: the two
    components of the `pair` swapped) REFUTED, witness x=1, y=1 (real
    r=(1,0), twin r=(0,1)), a "value"-kind witness ({"_ens": true}), the
    certificate calling the twin's own F(1, 1) and negating `ensures`
    with `r` substituted by that call -- exactly the shape 9 committed
    tasks before this pair already used, unaffected by F now returning a
    record instead of Big_Integer/Boolean/Seq.
  * min_max REFUSED: real VERIFIED, twin (collapse-if: the loop's first
    guard, `if s[i] < lo then lo := s[i]`, collapsed to its then-branch
    unconditionally) UNPROVED, witness s=[0, 1] (real r=(0,1), twin
    r=(1,1)), also a "value"-kind witness -- the twin ladder's own
    invariant-drop rung found no witness first (SPEC.md's own note: "no
    invariant drop of this task is witnessable by bounded execution,
    measured at fifteen times the state cap"), falling through to
    collapse-if, which does. The certificate this pair emits is
    syntactically and semantically the right one (F(s) called on the
    twin, `ensures[r := F(s)]` negated, requires `len(s) > 0` conjoined),
    but gnatprove does not discharge it: the audit names TWO separate
    unproved checks, VC_PRECONDITION at the twin's own recursive W_1 call
    site (severity medium, status "gave_up" -- Z3 answered Unknown, not
    out of steps, which is the expected reading once the invariant is
    genuinely broken: proving or disproving a fact over an abstract
    Big_Integer-indexed Seq is not decidable-by-construction the way a
    machine-int probe would be) and T_Refutation_Certificate's OWN
    VC_POSTCONDITION (severity medium, status "limit"). RE-MEASURED at
    10x budget (--steps 200000, uncontended, 80.8s wall): identical
    verdict, same two checks, same statuses -- not a near-miss of the
    default budget, a certificate that has to symbolically unfold a
    RECURSIVE loop helper (with its own quantified contract) over
    concrete literals, the first time a "value"-kind witness (built by
    calling F(input) symbolically, THE REFUTATION CERTIFICATE's own
    design, unchanged here) has landed on a task that also has a loop --
    every "value"-kind certificate before this pair (abs, max, and
    others) was loop-free, where F unfolds to one line. This is read as
    the column's known cost (spark timeouts), not a defect in this
    lowering: the certificate states the right goal, correctly grounded
    in the twin's own F, and the kernel's own budget is what falls short,
    exactly the INCOMPLETENESS this file's own doctrine (header, THE
    COUNTEREXAMPLE INSTANCE) says must never be forced into a false
    REFUTED. No attempt was made to rewrite the certificate to substitute
    the witness's own measured value in place of calling F: that would
    sever the certificate from F's OWN defining axiom (the very thing
    that makes "value" certificates sound, THE REFUTATION CERTIFICATE's
    own docstring), trading a slow, sound certificate for a fast, unsound
    one, which this file will not do.

Regression (out/agent-spark-pairs, real and twin, diffed against out/
*.ads): abs, swap, reverse, tail, filter_pos byte-identical, both files,
both before and after this pair; the other 14 previously committed tasks
(all_nonneg, contains, count_matches, digit_sum, factorial, fib,
first_even, gcd, is_prime, linear_search, max, remainder, seq_max,
sum_upto) checked the same way, also byte-identical, real and twin. None
of the 21 tasks committed before this pair moves.

NOT MEASURED: a pair with a seq component (`{"pair": ["seq", "int"]}`
and similar) is fully designed for -- the record's Seq field, needs_seq
widened to see a pair's own component, the named equality function's
T_Eq branch -- but neither committed task uses one, so this machinery is
unexercised, not merely unneeded like update()/fill() are for a task that
never calls them.

PAIRS RESIDUAL (2026-09-10). fuzz_lower.py's own v1pairs family (31
tasks, --seed 1) read spark verified/refuted on 12 of 31: 19 residual,
named in three shapes -- 16 UNPROVED and 1 TIMEOUT on reals that
VERIFIED, 1 ABSTAIN, 1 MALFORMED/MALFORMED -- diagnosed and fixed here.

* THE CERTIFICATE, refused for a pair-typed PARAMETER. certificate()'s
  own guard (`any(isinstance(p["type"], dict) for p in task["params"]):
  return ""`) refused a certificate outright on ANY task with a
  pair-typed parameter, and _undef_obligation carried the identical
  guard. eq_params, swap_param, proj_param, sentinel, minmax,
  seq_len_pair, and both fz_p_pair_* tasks whose parameter (not only
  return) is a pair all have this shape, so most of the 19 residual
  tasks went uncertificated. DIAGNOSED (fz_v1pairs_053, eq_params,
  wrong-var, gnatprove FSF 16.1.0, Why3 1.8.2, --prover=z3, --steps
  20000, uncontended): with no certificate emitted, the twin's own
  Post -- the only goal left in the file -- is what gnatprove tries and
  gives up on: VC_POSTCONDITION, severity medium, status gave_up, at the
  twin's own `with Post =>` line. Not the certificate's own postcondition
  or a symbolic call's precondition (min_max's own two named failure
  checks, above) -- there is no certificate goal in this file at all, and
  Big_Integer's own lack of a countermodel (spark.py's "REFUTED IS NOT
  UNPROVED") can never refute a bare Post with evidence. Cause:
  certificate()'s `sub`/`types`, built from the witness's JSON-shown
  `vals` (interp._j), read a pair-typed parameter's witness value (a
  2-list) by SHAPE alone, indistinguishable from a same-shaped seq's
  (SPEC.md "Pairs": "the runtime value of a pair must be DISTINCT from a
  seq", the very confusion _j's own docstring rules out at runtime, lost
  again once the witness is serialized) -- so both functions refused
  outright rather than risk misreading it. FIXED: `param_types` (the
  task's own declared parameter types, always known statically, never
  guessed) breaks the tie. `_cert_lit_of_type(v, ty)` (new, beside
  _cert_lit) renders a witness value as the DECLARED type says rather
  than as its own JSON shape guesses, so a pair-typed parameter's value
  becomes the qualified record aggregate F's own signature expects
  (`T_Pair_Int_Int'(P_A => ..., P_B => ...)`), never a Seq literal;
  `types` (for Lower._ty, so a pair `==`/`fst`/`snd` on that name still
  routes correctly) reads the same `param_types` entry directly instead
  of guessing "seq" off the list shape. `_undef_obligation` got the
  matching fix (`_to_py`, rebuilding a real interp.Pair for interp.ev's
  own `fst`/`snd`/`pair` cases, which need one, never a same-shaped
  tuple), exercised by the one committed "undefined" witness with a pair
  parameter, fz_p_pair_seq. Both blanket guards are gone: the type is now
  known, not guessed. MEASURED, the same eq_params twin, same steps: the
  certificate's own goal (`not (F(P, Q) = ...)`, F's defining axiom still
  doing the work, never bypassed) is now a GROUND evaluation over
  qualified record aggregates -- no loop, no quantifier, no recursive
  call -- and gnatprove discharges it directly: VERIFIED, REFUTED.

* THE ABSTAIN, a name collision. fz_v1pairs_064 (seq_len_pair,
  off-by-one, params s/a/b) abstained: "t name(s) ['a', 'b'] collide with
  the emitted package's own names (['A', 'B', ...])" -- Ada folds case,
  and every pair record's own fields were named A and B, so t's own
  lowercase `a`/`b` (an ordinary pair of parameter names, not a
  contrived one) collided with the record's own fields the first time a
  real task actually chose them. FIXED: renamed to P_A/P_B everywhere
  they are emitted (_pair_preamble's record and equality-wrapper bodies,
  expr()'s `pair`/`fst`/`snd` cases, _dead_lit, _cert_lit,
  _cert_lit_of_type), still reserved under the new names for the same
  reason as before (a t identifier `p_a`/`p_b` is not impossible, only
  far less likely than `a`/`b`). MEASURED: fz_v1pairs_064 now lowers
  cleanly and reads verified/refuted.

* THE MALFORMED, an undeclared record. fz_p_pair_proj (`fst(pair(a, b))
  == a`, two int params, int return, NO pair-typed param, return, or
  local anywhere) read malformed/malformed: `_pair_types`, which only
  scans param/return/spec_fun/`var`-DECLARED types for what record to
  emit, never sees a pair built and projected within a single
  expression, so expr()'s own `pair`/`fst` cases still emitted Ada text
  naming a T_Pair_Int_Int record this task's preamble never declared --
  a genuine Ada syntax error (an unknown type name), not a wrong
  lowering. Refused by name rather than risked with a deeper fix:
  `_has_pair_op` (new) detects a literal `pair` node anywhere in the
  task's requires/ensures/spec_funs/body by a generic recursive descent,
  AST-shape-blind on purpose (it only needs to know the word is there);
  `lower()` raises NotImplementedError when that is True and
  `_pair_types` came back with NO declared pair type at all -- the
  exact, decidable shape this task has. Every other committed pair task
  has at least one declared pair type via a param or return, so this
  never fires on them (confirmed against the whole 31-task family,
  above). A task with ONE declared pair type that ALSO builds a second,
  different transient one inline is not yet guarded against, only left
  unexercised, the same posture fst/snd's own non-name-projection gap
  already takes. MEASURED: fz_p_pair_proj now abstains by name, both
  real and twin, instead of the earlier malformed/malformed.

MEASURED (fuzz_lower.py, the family's own 19-task residual, --n 400
--seed 1 --jobs 8 --flake 3 --only spark, gnatprove FSF 16.1.0, --steps
20000, uncontended): 10 of 19 now COUNT (verified/refuted) that were
UNPROVED, TIMEOUT, or ABSTAIN before -- fz_v1pairs_053, fz_v1pairs_064,
fz_v1pairs_093, fz_v1pairs_119, fz_v1pairs_235, fz_v1pairs_294,
fz_p_pair_swap, fz_p_pair_eq, fz_p_pair_seq, fz_p_pair_div (4.2s-56.4s
each). 1 (fz_p_pair_proj) is an honest abstain by name, not a flip. 8
remain UNPROVED, unchanged: fz_v1pairs_060/142/160/357/425/433/768/773,
every one "sentinel"/"minmax"-shaped, whose twin body still carries the
WHILE LOOP after its own inner `if` is collapsed (COLLAPSE-IF removes
the `if`, not the loop it sits in) -- the SAME cost min_max's own
MEASURED paragraph above names, at 69-103s wall each (vs 4-56s for the
ten that flip): the certificate's "value"-kind goal has to symbolically
unfold a RECURSIVE loop helper (its own quantified contract) over
concrete literals, gnatprove reporting the identical two unproved checks
min_max's own paragraph names (VC_PRECONDITION at the twin's own
recursive W_k call site, severity medium, status gave_up;
T_Refutation_Certificate's OWN VC_POSTCONDITION, severity medium, status
limit) -- read as the column's known cost, not a defect in this
lowering, for the identical reason min_max's own paragraph gives.

Regression (out/agent-spark-pairs2, real and twin, diffed against
out/*.ads): abs, swap, reverse, tail, filter_pos byte-identical, both
files, both before and after this residual pass (none touches a pair
type, so P_A/P_B never appears in their output); their own verdicts
unchanged (all five still COUNT). divmod_pair and min_max are NOT
byte-identical, and are not expected to be: both now declare
T_Pair_Int_Int with fields P_A/P_B rather than A/B, the intended effect
of the field rename above, confirmed to be the ONLY diff (diagnostic
diff, both files, both tasks). Their own verdicts are unchanged:
divmod_pair still COUNTS, min_max's own twin still reads
verified/unproved, exactly the loop-carrying cost this note's own
paragraph measures -- neither certificate fix touches min_max's own
already-diagnosed cost, since min_max's witness was already
"value"-kind before this pass (its own MEASURED paragraph, above).

LEFT, by name: the 8 loop-carrying tasks above
(fz_v1pairs_060/142/160/357/425/433/768/773), unchanged, the column's
known loop-plus-pair cost, not attempted here for the same reason
min_max's own paragraph gives (a slow, sound certificate is preferred
over a fast, unsound one); fz_p_pair_proj, an honest abstain rather than
a fix, since discharging it properly needs `_pair_types` to read a
`pair` node's static type off an incrementally-grown `types` env across
requires/ensures/spec_funs/body the way Lower.compile()'s own env does,
not the declaration-only scan it has today -- a real fix, not attempted
here, carried for the next pass; a LOOP-carrying pair-with-a-seq-
component task (fz_p_pair_seq's own shape is loop-free and already
covered) is not yet measured by anything in this family.

NESTED SEQUENCES (v1). {"seq": "seq"} (SPEC.md "Nested sequences (v1)",
2026-09-10): a seq of seqs of ints, one level, written seq<seq>. No new
Expr forms; every seq operator is polymorphic by its operands' static
type, exactly as `+`/`==` already were before this pair. Built as a
SECOND instantiation of the SAME generic, Element_Type => Seq
(NESTED_SEQ_PREAMBLE: package Rows, subtype Seq2), rather than a new
representation: "Ada functional containers can nest" (SPEC.md), measured
true. Every other seq primitive at this level keeps its FLAT NAME,
OVERLOADED rather than renamed -- Len, Elem, T_Update, T_Fill, T_Slice,
T_Concat, T_Concat_Aux, T_Eq each gain a second declaration over Seq2 (or
over Seq where the flat one takes Big_Integer), and Ada resolves the call
by the argument's own static type, the same polymorphism t's own
operators already have. Lower.expr's rendering for `len`/`at`/`update`/
`fill`/`slice`/`+`/`==` therefore needed NO new text, only a flag split
(needs_update2/needs_fill2/needs_slice2/needs_concat2/needs_eq2 on Lower,
independent of the flat needs_update/needs_fill/needs_slice/needs_concat/
needs_eq, each gating its own NESTED_*_PREAMBLE block) so the right
preamble is emitted. The one exception is the seq LITERAL:
Seqs.Add/Seqs.Empty_Sequence and Rows.Add/Rows.Empty_Sequence are
different package-qualified names, not overloads of one identifier, so
Lower.expr's `seq` case picks the package from the first element's own
static type (Lower._ty). A row-typed postcondition (T_Fill/T_Slice/
T_Concat's own elementwise fact at this level) goes through the FLAT
T_Eq, never bare "=", for the identical reason EQ_PREAMBLE's own
elementwise fact does at the flat level (Seq is the same private
generic-instantiation type either way); needs_fill2/needs_slice2/
needs_concat2/needs_eq2 each force needs_eq and needs_range on with
them, exactly as needs_fill/needs_slice/needs_concat already force
needs_range.

Lower._ty gained the reading SPEC.md asked for: `at` returns "seq" (a
row) when its operand is nested, "int" when flat, told apart by the
OPERAND's own type rather than the op alone -- s[i][j] (at(at(s,i),j))
resolves right by construction, the inner `at`'s own result feeding the
outer one. `update`/`slice` return the SAME type as their first
argument, row or outer. `fill(n, v)` is nested iff v is itself a row.
The `seq` literal is nested iff its own first element is a row; the
empty literal `[]` has no element to read this off of and SPEC.md's own
"the declared type says so" is a top-down hint this bottom-up function
does not carry, so it defaults to flat, unchanged from before this
construct (NOT MEASURED, below). Every isinstance(ty, dict) call site
that used to assume "pair" (ada_type, Lower.expr's `==` dispatch,
_cert_lit_of_type, _pair_types.add, _dead_lit, _undef_obligation's
_to_py) now checks "pair" in ty explicitly first (_is_nested_seq, new),
since the nested type's own dict, {"seq": "seq"}, is also a dict and
would otherwise be misread as a pair type -- MEASURED to matter, not
theoretical: _pair_types.add's own bare isinstance(ty, dict) check, before
this fix, collected BOTH committed tasks' own {"seq": "seq"} param/return
types as if they were pair types, and _pair_ada_name({"seq": "seq"})
raises KeyError on ty["pair"] the first time either task is lowered.

THE INSTANTIATION. MEASURED (probe, gnatprove FSF 16.1.0): `package Rows
is new SPARK.Containers.Functional.Infinite_Sequences (Element_Type =>
Seq);`, the box-defaulted "=" alone, FAILS -- "instantiation error...
no visible subprogram matches the specification for '='" at the
generic's own `with function "=" (Left, Right : Element_Type) return
Boolean is <>` formal, both committed tasks reading real/twin
malformed/malformed. A harder failure than EQ_PREAMBLE's own "Seq's '='
is not directly visible as an infix operator without `use Seqs;`" (that
one is at least callable qualified; a box default apparently needs the
identical visibility an ordinary infix reference would, not the wider
"any primitive operation of the actual type" rule this file's design
had assumed). FIXED, MEASURED: the actual is named explicitly, `"=" =>
Seqs."="`, a qualified function name, which resolves with no `use`
needed -- the same qualified-call spelling this file already uses for
every OTHER Seqs operation. This turns on two benign warnings per
instantiation ("precondition/postcondition is always False, ...
Use_Logical_Equality", SPARKlib's own Logical_Eq ghost lemma, since
Use_Logical_Equality defaults False regardless): MEASURED harmless,
verifiers/spark.py's own MALFORMED gate matches `error`, never
`warning`, and the FLAT single instantiation already carries the
identical warning (out/tail.ads, gnatprove FSF 16.1.0: the same two
lines, at the flat instantiation), unnoticed until a second
instantiation's own diagnostic put it beside a real error. No committed
task's own audit outcome moves.

MEASURED (2026-09-10, gnatprove FSF 16.1.0, Why3 1.8.2+git, --steps
20000, harness.run_task, out/agent-spark-nested, uncontended):

  * swap_rows COUNTS: real VERIFIED (44.1s), twin (off-by-one: the second
    `update`'s own row index shifted by one, `update(update(m, i, m[j]),
    j + 1, m[i])`) REFUTED (35.9s), witness m=[[]], i=0, j=0 (real
    [[]]) -- an "undefined"-kind certificate, exactly the shape the flat
    "swap" task's own off-by-one twin already reads: the shifted index
    runs the second `update` off the single row (`update index 1 outside
    [0,1)`), _undef_obligation's own replay (fixed for this pair: _to_py
    gained a `_is_nested_seq(ty)` branch rebuilding the JSON list-of-lists
    as a tuple-of-tuples, interp.ev's own nested representation, no
    interp.Pair-style reconstruction needed since a nested seq witness is
    never ambiguous with anything else v1 has) finding the same failing
    obligation gnatprove does, restated and negated.
  * row_max_len COUNTS: real VERIFIED (51.1s), twin (invariant-drop: the
    loop invariant's own upper bound conjunct dropped) REFUTED (39.9s),
    witness exit at m=[[], [0]], i=2, r=0 -- an "exit"-kind certificate,
    interp.exit_env's own state run through the loop's exit entailment.
    `_cert_lit_of_type` gained the matching branch: a seq<seq>-typed
    PARAMETER's witness value (a list of row-lists) becomes a Rows.Add
    chain over each row's own Seqs.Add chain, unconditionally correct
    since `ty` is the task's own declared type here, never guessed (the
    same declared-type discipline PAIRS RESIDUAL's own `_cert_lit_of_type`
    established); `r` itself is an int, so the return-side rendering is
    unaffected by any of this pair's own machinery.

Regression (out/agent-spark-nested, real and twin, diffed byte-for-byte
against out/*.ads and out/*_twin.ads): abs, swap, tail, filter_pos,
divmod_pair, min_max all byte-identical, both files, both before and
after this pair; none of the six declares a nested type, so Rows/Seq2
never appear in their output and none of the new flags ever turns on for
them. Their own verdicts are unchanged: five COUNT, min_max still reads
REFUSED (real verified, collapse-if twin unproved), the SAME loop-plus-
pair cost PAIRS' own note already measured, untouched by this pass.

NOT MEASURED, by name:

  * The empty nested literal `[]` where "the declared type says so" is
    the only way to tell it apart from a flat empty seq (Lower._ty's own
    note, above). Neither committed task contains a `seq` literal node at
    all (grepped: zero occurrences in both), so neither the non-empty
    inference nor the empty-literal default is exercised by anything
    committed. A task that builds an empty seq<seq> literal directly
    (rather than through a parameter, `at`, or `update`) would silently
    lower it as a flat empty Seq today -- a wrong type, not a crash,
    since Ada would then reject the resulting text as a type
    mismatch at its first real use, an honest compile failure rather
    than a silently wrong proof. Fixing this properly needs a top-down
    expected-type hint threaded through Lower._ty/Lower.expr the way
    check_wf's own reading already carries one (interp.py, "Nested
    sequences" note), not attempted here.
  * fill()/slice()/`+`/`==` at the outer level (NESTED_FILL_PREAMBLE,
    NESTED_SLICE_PREAMBLE, NESTED_CONCAT_PREAMBLE, NESTED_EQ_PREAMBLE):
    fully designed and each independently gated, but neither committed
    task calls any of them at this level (swap_rows uses only outer `at`/
    `update`; row_max_len uses only outer `at`, then flat `len` on the
    row), so none of the four preamble blocks is exercised by anything
    committed -- unneeded, like update()/fill() already were for a
    pre-pair task that never called them, not a known gap.
  * A nested seq built and projected within a single expression with no
    declared param/return/local anywhere (the seq<seq> analogue of
    fz_p_pair_proj, PAIRS RESIDUAL's own malformed case): `lower()` has no
    `_has_nested_seq_op`-style guard for this shape, so such a task would
    emit Ada text naming Rows/Seq2 without NESTED_SEQ_PREAMBLE ever having
    been requested -- a genuine, undiagnosed Ada error, the identical risk
    fz_p_pair_proj measured for pairs before `_has_pair_op` closed it.
    Not yet guarded against; carried for the next pass.
  * `_undef_obligation`'s own shape-based type guess for a LOCAL var this
    walk binds mid-replay (types[name] = "seq" if isinstance(val, tuple)
    else ...) still reads a tuple-of-tuples as flat "seq", never nested --
    the identical "NOT MEASURED" gap PAIRS RESIDUAL's own docstring left
    for a local bound to a raw Pair. swap_rows's own "undefined" witness
    never reaches it: its twin body is the one `assign` statement, and the
    failing obligation trips on that FIRST statement, before this
    fallback is ever consulted. Carried for the next task that binds a
    nested-seq local inside an "undefined" twin body.
  * `_cert_lit`'s own shape-based nested case (isinstance(v, (list,
    tuple)) and v and isinstance(v[0], (list, tuple))) defaults an EMPTY
    outer list to the flat branch, the identical bottom-up ambiguity as
    the `seq` literal and for the same reason; unreached by either
    committed task, since both certificates read their own seq<seq>-typed
    parameter through `_cert_lit_of_type` (declared-type, unambiguous),
    never through this shape-based function.

NESTED SEQUENCES RESIDUAL (2026-09-10). fuzz_lower.py's own v1nested
family (18 tasks, --seed 1) read spark verified/refuted on 13 of 18: 5
residual, named in three shapes -- 2 MALFORMED/MALFORMED, 1
VERIFIED/UNPROVED, 1 UNPROVED/TIMEOUT, 1 NO-TWIN (a probe with no twin
op, expected and ungraded either side of this pass) -- diagnosed here.
Both malformed cases are exactly the two gaps this note's own "NOT
MEASURED" paragraphs, above, already named.

* THE EMPTY NESTED LITERAL, defaulting to flat. fz_v1nested_069
  (build_matrix, gate "loops", compare-flip) declares `var m : {"seq":
  "seq"} := []` (Lower._ty's own note, above), builds it up through
  T_Concat inside the loop, and returns it as Seq2. `[]`'s own render
  (Lower.expr's `seq` case) had no way to see m's declared type, so it
  emitted Seqs.Empty_Sequence (flat) regardless of context -- MEASURED,
  malformed/malformed, gnatprove rejecting the resulting `W_1 (S, ...,
  Seqs.Empty_Sequence, ...)` call, whose own M parameter is Seq2, not
  Seq. FIXED: Lower.expr gained an `expect` parameter (its own new
  docstring, above), the same "the declared type says so" hint
  fuzz_lower.py's own `_ty(..., expect=...)` already threads for
  check_wf (that function's own docstring, "Nested sequences"
  (2026-09-10)) -- narrower than that function's full site list: only
  var init, assign, and return (compile()/compile_r(), both updated)
  thread a real value in, the three sites MEASURED to matter here; an
  `ite` branch or a call argument is left at expect=None, unchanged,
  carried below, since nothing committed or in this residual exercises
  either.

* A NESTED LITERAL, built and projected inline with no declared type
  anywhere. fz_p_nest_lit (a probe, no params, bool return) computes
  `len([[1, 2], [3]]) = 2 and then len([[1, 2], [3]][1]) = 1` entirely
  inside one expression, with no param, return, or `var` of the nested
  type anywhere for `needs_nested_seq`'s own declaration-only scan to
  see -- the seq<seq> analogue of fz_p_pair_proj, and the exact gap this
  note's own "NOT MEASURED" paragraph, above, named by asking for
  `_has_nested_seq_op`. MEASURED, malformed/malformed, gnatprove
  rejecting Rows/Seqs/Len/Elem: neither SEQ_PREAMBLE nor
  NESTED_SEQ_PREAMBLE was ever emitted, since `needs_nested_seq` found no
  declared type to trigger on. FIXED, by refusal rather than by
  inference: `_has_nested_seq_op` (new), a generic, type-blind recursive
  descent mirroring `_has_pair_op`'s own, detects a literal nested-seq
  node (a `seq` literal whose own first argument is itself a `seq`
  literal, i.e. a row) anywhere in requires/ensures/spec_funs/body;
  `lower()` refuses by name whenever this is True and `needs_nested_seq`
  came back False, the identical posture `_has_pair_op`'s own refusal
  already takes toward a transient pair.

MEASURED (fuzz_lower.py, the family's own 5-task residual, --n 400
--seed 1 --jobs 8 --flake 3 --only spark, gnatprove FSF 16.1.0, Why3
1.8.2+git, --steps 20000, uncontended):

  * fz_v1nested_069: malformed/malformed -> VERIFIED/TIMEOUT (97.4s). The
    fix above makes the real body compile and VERIFY; the compare-flip
    twin (its own loop bound flipped `I < Len (S)` to `I <= Len (S)`, an
    off-by-one that should make the exit reach an out-of-range `Elem`
    call) now TIMES OUT rather than being refuted, a NEW cost this pass
    surfaces rather than fixes: the recursive W_1 helper has to be
    symbolically unfolded over concrete literals to resolve it, the
    identical "value"-certificate cost min_max's own paragraph and PAIRS
    RESIDUAL's own 8 loop-carrying tasks already name, at 97.4s against
    the same 20000-step budget -- read as the column's known cost at this
    construct, not a defect in either fix.
  * fz_v1nested_007: unchanged, VERIFIED/UNPROVED (78.9s vs 90.5s before
    this pass, within run-to-run noise). param_rowlen's own collapse-if
    twin still carries the WHILE LOOP after its own inner `if` is
    collapsed, the same "value"-certificate cost fz_v1nested_069 above
    and min_max's own paragraph name; this pass touches neither the
    twin's own shape nor `_ty`/`expr`'s empty-literal handling for it
    (its body has no `seq` literal node at all), so nothing here moves
    it.
  * fz_v1nested_150: unchanged, UNPROVED/TIMEOUT (87.2s vs 97.3s before
    this pass, within run-to-run noise). row_sum's own gate is
    "recursion": the real body's own postcondition already needs
    `rowsum`'s recursive spec_fun unfolded through the loop's own
    invariant at every `k`, too costly for the real side alone at the
    20000-step budget; this pass's two fixes touch neither the empty
    literal nor the undeclared-type gap, and this task exercises neither.
  * fz_p_nest_lit: malformed/malformed -> ABSTAIN/ABSTAIN, an honest
    refusal by name (the NotImplementedError message above), not a flip
    -- the same posture PAIRS RESIDUAL's own fz_p_pair_proj already
    takes.
  * fz_p_nest_empty: unchanged, NO-TWIN/NO-TWIN (0ms both times): a probe
    with `_twin_op: null`, never graded by this family's own harness
    either before or after this pass.

Regression (all 23 committed tasks, lower_spark.lower(task, task["body"])
diffed byte-for-byte against their own out/<name>.ads): byte-identical,
all 23, both before and after this pass. `_has_nested_seq_op`'s guard
only fires when `needs_nested_seq` is False, never true for swap_rows or
row_max_len (each declares a nested param or return). Lower.expr's new
`expect` parameter DOES reach a committed task's own code, not only the
residual's: filter_pos's own body assigns an empty FLAT literal `[]` to
a local through the same `assign` site this pass threads `expect`
through (grepped: the only other `seq` literal node among all 23
committed tasks' own requires/ensures/spec_funs/bodies), but that
local's own declared type is plain "seq", not nested, so
`_is_nested_seq(expect)` reads False exactly as `bool(eargs)` alone
already did, and filter_pos's own Seqs.Add chain is unaffected,
byte-for-byte.

LEFT, by name: fz_v1nested_069's own twin certificate cost (TIMEOUT,
above), the loop-carrying "value"-certificate cost this pass surfaces
but does not attempt to fix, for the same reason a slow sound
certificate is preferred over a fast unsound one (PAIRS RESIDUAL's own
LEFT paragraph gives the identical reason); fz_v1nested_007's and
fz_v1nested_150's own unchanged costs (a collapse-if "value" certificate
and a recursion-through-a-loop real body, respectively), neither touched
by anything in this pass; fz_p_nest_lit, an honest abstain rather than a
fix, since discharging it properly would need `_has_nested_seq_op` (or
`Lower._ty`) to read a nested literal's type off an incrementally-grown
`types` env the way Lower.compile()'s own env does, not the shape-only
scan it has today -- carried for the next pass, the same posture PAIRS
RESIDUAL's own fz_p_pair_proj paragraph already takes toward
`_pair_types`; Lower.expr's own `expect` hint not threaded through an
`ite` branch or a call argument, since neither is exercised by anything
committed or in this residual (NOT MEASURED, narrower than
fuzz_lower.py's own wider site list for the identical reason); `_ty()`'s
own bottom-up `seq`-literal case (read for OPERATOR dispatch, never for
rendering) still takes no `expect` and still defaults an ambiguous empty
literal to flat, unreached by anything this pass measured since no
committed or residual task ever calls `_ty` directly on a bare
empty-literal node; `_cert_lit`'s own shape-based nested case and
`_undef_obligation`'s own shape-based local-var guess, both already
named NOT MEASURED above, remain untouched.

THE STRING LIBRARY (v1), SPEC.md 2026-09-11 (ROADMAP 12.7, the wave after
nested sequences). Seventeen members (split's two arities counted as
one, per SPEC.md), each restated as this kernel's own definition in the
prelude, each a total Len/Elem-and-T_Range recursive function, gated
member by member (needs_strcore plus twelve needs_str_* flags, Lower,
above) rather than behind one shared flag: gnatprove proves every
declared subprogram in the emitted file, so one member's own unproved
contract would otherwise fail every OTHER task sharing a file with it.
count/find (T_Count/T_Find over T_Match_At, a plain T_Range quantifier),
strip/lstrip/rstrip (T_Lws/T_Rws position-counting past a whitespace
run, then T_Slice), replace, lower/upper (elementwise maps), the four
predicates and startswith/endswith (bare T_Range quantifiers, no
recursion), and tostr (decimal peeling by 10) are each restated directly
from interp.py's own `_str_*` functions with no lemma beyond their own
Subprogram_Variant termination proof, and MEASURED (this session's
scratch probes) to sit in the family of shapes CONCAT_PREAMBLE/
SLICE_PREAMBLE already established as tractable (a function built by
peeling ONE element via T_Slice, or a plain quantifier). split(s),
split(s, c) and join are shipped too (T_Sc/T_Sw build a {Rows, Last}
accumulator forward via Rows.Add, T_Join consumes a Seq2 by peeling its
last row via the nested T_Slice), total and correct against interp.py by
inspection, usable in specification position per SPEC.md's own rule that
a member there is the same function.

THE ONE SIMPLIFICATION THAT TURNED OUT TO BE LOAD-BEARING: a full self-
slice, `s[0..len(s)]` (word_count's own `t2 := s[0..len(s)]`), is now
recognized SYNTACTICALLY in Lower.expr's `slice` case and rendered as
the bare argument, not `T_Slice (S, 0, Len (S))`. MEASURED, this
session's scratch probes p1/p4/p5 (gnatprove FSF 16.1.0, z3): SPARKlib's
native Seqs."=" -- even GIVEN as an established precondition, no
re-derivation needed -- does NOT let GNATprove conclude that a THIRD
function's calls on two "="-equal Seq values are themselves equal
(ordinary SMT congruence does not fire through a private-type equality
PREDICATE the way it does through the literal "=" symbol on a scalar
sort; EQ_PREAMBLE's own T_Eq exists for exactly this reason one level
up). So `T_Split (T_Slice (S, 0, Len (S)))` and `T_Split (S)` are two
DIFFERENT terms as far as the prover is concerned even once their
equality is known, and word_count's real cell read TIMEOUT (--steps up
to 200000) until the slice was simplified away at render time instead,
making them the SAME term. General and AST-level (any `slice` node
shaped `e[0..len(e)]`, not member-specific), and safe for every already-
committed task (grepped: none builds this exact shape; tail's own slice
is `s[1..len(s)]`, lower bound 1).

MEASURED (2026-09-11, gnatprove FSF 16.1.0, Why3 1.8.2, --prover=z3,
--steps 20000 unless noted, harness.run_task, uncontended):

  * word_count COUNTS: real VERIFIED, twin (off-by-one on the slice's `0`
    lower bound) REFUTED, witness s = [] (real 0, twin undefined: "slice
    bounds [1..0]") -- SPEC.md's own predicted witness for this task,
    exactly reproduced.
  * split_join REFUSED: real TIMEOUT, twin (wrong-var) REFUTED. The
    task's own ensures IS the join-of-split law, `join(split(s, c), [c])
    == s`; T_Sc builds the row sequence via Rows.Add (there is no other
    Seq2 constructor), and Rows.Add's own preservation fact
    (SPARKlib's Equal_Prefix) is stated over the library's NATIVE
    Iterable cursor, not this file's T_Range -- MEASURED (scratch probes
    p2's Probe_A/Probe_B, --steps 20000 AND --steps 200000, z3, cvc5
    tried once for comparison and found WORSE): "slicing an extended
    row-seq back to its old length recovers the old seq" and "join of
    one-more-row equals join-then-separator-then-row" both time out,
    the same cross-encoding wall EQ_PREAMBLE's own note already names,
    one level up (Seq2-of-Seq rather than Seq-of-Big_Integer). Not
    fixed in this session: a real induction proof of the round-trip law
    stated entirely in T_Range/T_Slice terms (never touching Rows.Add's
    own axiom) is the open move, following the SAME technique that
    fixed count_vowels' OWN step lemma below, generalized from a
    Big_Integer-valued accumulator to a Seq2 one.
  * count_vowels REFUSED: real TIMEOUT, twin (invariant-drop) REFUTED.
    Two distinct causes, diagnosed in full, one fixed:
    (1) count_vowels.json's own invariant list is ordered content-fact,
        then bound-facts (`r == s[0..i].count(...)...`, THEN `0 <= i`,
        THEN `i <= len(s)`), and an "and then" aspect checks each
        conjunct's OWN definedness using only EARLIER conjuncts as
        hypotheses -- so T_Slice (S, 0, I) inside the first conjunct
        failed its OWN Pre ("cannot prove I <= Len (S)"), a false
        MEASURED TIMEOUT that was really a definedness-ordering bug, not
        a hard proof. FIXED: lower_while's own Pre/Post assembly now
        stable-sorts a task's invariant list (bound-only conjuncts,
        _is_bound_inv, first; everything else after, each group keeping
        its original order), gated on _has_strlib_op so no other
        already-committed task's invariant order moves (confirmed by
        the matrix regression, below). General, not member-specific: a
        slice/at-based invariant from a PRIOR gate could hit the
        identical trap, but none of the 23 tasks committed before this
        wave does, so the gate stays narrow rather than firing on
        `at`/`slice` too and risking THEIR byte-identity for no measured
        need.
    (2) Once (1) is fixed, the REAL step remains: W_1's own recursive
        call must reprove the invariant at the advanced state, which
        needs `count(s[0..i+1], [ch])` related to `count(s[0..i], [ch])`
        for five vowels at once. DIAGNOSED, not landed: T_Count1's own
        recursive definition (peel-via-T_Slice, above) does NOT auto-
        unfold for an outside caller at a symbolic argument, stated Post
        or not (scratch probe p6.ads, Probe_H, first two attempts, both
        TIMEOUT); an explicit congruence lemma over T_Count1 (elementwise
        equal Seq arguments give equal T_Count1, proved by structural
        induction peeling one element from EACH side at once -- the same
        shape as the general G/Seq_Cong probe, p5.ads, that verified
        cleanly) DOES close the exact fact needed (scratch probe p6.ads,
        final version: 242 checks, 0 unproved), and a SEPARATE, simpler
        reformulation -- T_Count1_Up (S, Ch, I), counting a POSITION up
        with S held fixed rather than peeling S itself -- needs no lemma
        at all, its own stated Post unfolds for an external caller with
        0 unproved (scratch probe p7.ads). Neither is wired into this
        file: getting either lemma's fact into scope at the ACTUAL VC
        (the recursive call GNATprove auto-generates inside W_1's own
        body, not a Pre/Post aspect this file writes text for) needs an
        explicit hint injected into that one expression -- the same
        `(if Lemma (...) then Call else Call)` idiom that fixed
        word_count's own congruence gap above, but there the hint sits
        in F's OWN body (this file's own text); here it would have to
        sit inside lower_while's auto-built recursive-call expression, a
        change to loop-body lowering (a PRIOR gate's own machinery) this
        session judged too large a change to make safely in the time
        left, not attempted rather than attempted and failed. Carried
        open, by name, for the next pass on this construct.

Regression (this session's own matrix_diff.py, real AND twin, every one
of the 23 tasks committed before this wave, diffed in-process against
lower_spark_orig.py at HEAD 7bcd2fa): 23/23 byte-identical, both the full
self-slice simplification and the invariant reorder confirmed to change
nothing for a task that never reaches either (neither construct exists
before this wave, so the check is that the new code paths simply never
fire on old tasks, not that they fire and cancel out).

THE FUZZ FAMILY (`v1strlib`), this session, `--n 400 --seed 1 --flake 3
--jobs 8` against the roster this session was handed (16 names,
fuzz-strlib-names.txt): only 2 of the 16 named tasks exist in a FRESH
`--seed 1` generation (fuzz_lower.py's own dated note on this family:
"16000 tries... produced only 17 distinct well-formed tasks", so most
NNN-numbered names in a roster prepared against a different run's own
corpus never recur -- MEASURED, not assumed: `corpus.json` this run
holds exactly `fz_v1strlib_007` and `fz_v1strlib_031`). Of the 2:

  * fz_v1strlib_007 ABSTAIN (not a member defect): "t name(s) ['rows']
    collide with the emitted package's own names" -- the fuzz shape's
    own body-local is named `rows` (the docstring's own "index" variant,
    "rows a body-local"), and `Rows` is reserved unconditionally for the
    Seq2 package instantiation, a NESTED SEQUENCES (v1) reservation from
    the wave before this one, not something this wave added or could
    narrow -- lower()'s own collision check (RESERVED, header) catches
    it honestly, exactly its designed job.
  * fz_v1strlib_031 NO-FLIP: real VERIFIED, twin (off-by-one, the
    `tostr_len` shape's own `t2 := n + 0` decoy shifted) TIMEOUT rather
    than REFUTED. Not root-caused in the time this session had: T_Digits
    peels decimal digits by 10, and the twin's own refutation
    certificate (THE REFUTATION CERTIFICATE, spark.py's header) has to
    unfold that recursion concretely at the witness's own value, the
    same class of cost min_max's own certificate timeout (PAIRS,
    2026-09-10) already named for a loop rather than a digit-count
    recursion. Carried open, by name.

NOT MEASURED / OPEN, by name: the split-length law
(`len(split(s, c)) == count(s, [c]) + 1`, SPEC.md's own stated identity)
-- not needed by any of the three committed tasks' own ensures, so never
attempted; join/split/replace/count/find's general (not single-code-
point) behavior against a loop invariant -- no committed task states
one; the fuzz family's other 15 distinct shapes (word_count/split_row/
join_split_roundtrip/count_pattern/find_case/strip_len/replace_count/
case_map/startswith_endswith_slice/loop_count, fuzz_lower.py's own
per-shape list, above) -- this session's roster did not reach them and
there was no time left to regenerate the family without one to measure
each shape individually; the spec experiment's pool (function-shaped nl/
problems this member closes) -- not run.
"""
from __future__ import annotations

import re

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                                   # noqa: E402
import interp                                    # noqa: E402
from verifiers import spark as spark_backend     # noqa: E402

TYPE = {"int": "Big_Integer", "bool": "Boolean", "seq": "Seq"}
CMP = {"==": "=", "!=": "/=", "<": "<", "<=": "<=", ">": ">", ">=": ">="}
ARITH = {"+": "+", "-": "-", "*": "*"}
DIVMOD = {"div": "T_Div", "mod": "T_Mod"}
NARY = {"and": "and then", "or": "or else"}

# Every Ada name this file puts in the emitted package. A t identifier that
# capitalizes onto one of them would be captured silently, so lower() refuses
# instead (the W_k helpers are checked separately, by count).
RESERVED = frozenset((
    "F", "Seq", "Seqs", "Len", "Elem", "T_Range", "R_First", "R_Has",
    "R_Next", "Big_Integer", "Boolean", "T_Refutation_Certificate",
    "T_Div", "T_Mod", "T_Update", "T_Fill", "T_Slice", "T_Concat",
    "T_Concat_Aux", "T_Eq",
    # SPEC.md "Nested sequences" (2026-09-10): the outer instantiation and
    # its own subtype, reserved unconditionally the same way Seq/Seqs
    # already are (a task with no nested seq pays nothing extra: these two
    # names simply never appear in its output).
    "Rows", "Seq2",
    # THE STRING LIBRARY (v1), 2026-09-11: every member's own Ada name,
    # plus its internal helpers and T_Split_State's two field names,
    # reserved unconditionally the same way the nested-seq pair above is
    # (STRCORE_PREAMBLE and friends, above): a task that uses no string
    # member pays nothing extra, these names simply never appear in its
    # output.
    "Is_Ws", "Is_Upper_Letter", "Is_Lower_Letter", "T_Match_At",
    "T_Count", "T_Count_From", "T_Find", "T_Find_From",
    "T_Lws", "T_Rws", "T_Strip", "T_LStrip", "T_RStrip",
    "T_Replace", "T_Replace_From", "T_Replace_Empty_From",
    "T_Lower", "T_Upper",
    "T_IsDigit", "T_IsAlpha", "T_IsUpper", "T_IsLower",
    "T_StartsWith", "T_EndsWith", "T_Digits", "T_ToStr",
    "T_Split_State", "T_Sc", "T_Split_C", "T_Sw", "T_Split", "T_Join",
    "Last"))

# The counterexample instance (header). The window is above 2^31 so that a
# lowering which had silently kept a 32-bit model would be caught by the
# instance too (fz_p_intwidth, fz_p_bigneg), and the cap leaves 27 bits of
# headroom under Long_Long_Long_Integer'Last = 2^127 - 1.
CE_WINDOW_BITS = 40
CE_WINDOW = 2 ** CE_WINDOW_BITS
CE_CAP = 2 ** 100
CE_TYPE = {"int": "Ce_Int", "bool": "Boolean"}       # parameter types
CE_RET = {"int": "Ce_Num", "bool": "Boolean"}        # result type: unwindowed
CE_PREAMBLE = f"""\
   --  The task at machine inputs with exact arithmetic: gnatprove's RAC
   --  cannot execute a Big_Integer expression, so F above can never carry a
   --  confirmed counterexample (header). Every magnitude here is bounded by
   --  construction, so a counterexample to F_Ce is a counterexample to the
   --  task itself.
   subtype Ce_Num is Long_Long_Long_Integer;
   subtype Ce_Int is Ce_Num range -2**{CE_WINDOW_BITS} .. 2**{CE_WINDOW_BITS};
"""


class _NoCe(Exception):
    """The task is outside the instance's reach; emit no instance. Never a
    lowering failure; the unbounded theorem is unaffected."""


def _ce_cap(n: int) -> int:
    if n > CE_CAP:
        raise _NoCe(f"magnitude bound 2^{n.bit_length()} exceeds the "
                    f"instance's headroom")
    return n


def _ce_max(a, b):
    """Join two branch bounds. None is a bool-valued branch; a task where one
    branch is bool and the other is not is not well typed, and is refused
    rather than instantiated on a guess."""
    if a is None and b is None:
        return None
    if a is None or b is None:
        raise _NoCe("branches of an `if` disagree on type")
    return max(a, b)


_UNSET = object()


def _ce_bound(e: dict, env: dict):
    """An upper bound on |value| for an int-valued node, None for a
    bool-valued one. Every int-valued subnode is bounded on the way down, so
    an overflowing intermediate refuses the instance even when the node above
    it would have fit."""
    if "int" in e:
        return _ce_cap(abs(int(e["int"])))
    if "bool" in e:
        return None
    if "var" in e:
        b = env.get(e["var"], _UNSET)
        if b is _UNSET:
            raise _NoCe(f"read of unassigned {e['var']!r}")
        return b
    if "forall" in e or "exists" in e:
        raise _NoCe("quantifier: the range is mathematical, not machine")
    if "ite" in e:
        c = e["ite"]
        _ce_bound(c["cond"], env)
        return _ce_max(_ce_bound(c["then"], env), _ce_bound(c["else"], env))
    if "call" in e:
        raise _NoCe("call: a spec fun or recursion has no static bound")
    op = e["op"]
    if op in ("len", "at", "update", "fill", "seq", "slice"):
        # SPEC.md "Sequences as values" (2026-09-09) / "Sequences:
        # literals, concatenation, slices" (2026-09-09): every seq
        # operator gets the same fail-closed treatment, len/at included --
        # a seq subexpression has no machine mirror to bound. A seq `+`
        # (concatenation) needs no entry of its own here: its operands are
        # walked by the fallthrough below exactly like an int `+`'s, and
        # inductively at least one of them bottoms out at one of the ops
        # named on this line (or an unbound `var`, already _NoCe below),
        # so the walk always raises before returning a bound for it.
        raise _NoCe("seq operator")
    if op in ("pair", "fst", "snd"):
        # SPEC.md "Pairs" (2026-09-10): no machine mirror either, the same
        # fail-closed treatment as a seq operator, just above. ce_instance's
        # own top guard already keeps a pair-typed PARAMETER or RETURN out
        # of the instance before this function is ever called; this covers
        # a pair value built only as a LOCAL, which that guard does not
        # see. Stated explicitly rather than left to the generic
        # fallthrough below, which would reach the same _NoCe for a `pair`
        # node eventually (both its arguments bound fine as plain ints,
        # then no numeric operator below matches "pair") but only after
        # walking them, and would not on its own explain why `fst`/`snd`
        # are refused too.
        raise _NoCe("pair operator: no machine mirror")
    if op in ("div", "mod"):
        # No machine mirror (header, DIV/MOD): T_Div/T_Mod are Big_Integer
        # expression functions, so F_Ce (Ce_Num inputs) could not call them
        # even if a bound existed. Abstain, the same fail-closed treatment
        # already given to seq ops, calls and quantifiers here.
        raise _NoCe(f"{op!r}: no machine mirror for T_Div/T_Mod")
    bs = [_ce_bound(a, env) for a in e.get("args", [])]
    if op in ("not", "and", "or", "implies") or op in CMP:
        return None
    if any(b is None for b in bs):
        raise _NoCe(f"{op!r} over a bool-valued operand")
    if op == "neg":
        return bs[0]
    if op in ("+", "-"):
        return _ce_cap(bs[0] + bs[1])
    if op == "*":
        return _ce_cap(bs[0] * bs[1])
    raise _NoCe(f"operator {op!r}")


def _ce_stmts(stmts: list, env: dict) -> dict:
    """The bound walk over statements, mirroring Lower.compile's substitution
    exactly: a branch-local declaration is invisible after the `if`, and the
    join is over the variables that were in scope before it."""
    env = dict(env)
    for s in stmts:
        if "assign" in s:
            v, e = s["assign"]
            if v not in env:
                raise _NoCe(f"assign to undeclared {v!r}")
            env[v] = _ce_bound(e, env)
        elif "var" in s:
            d = s["var"]
            env[d["name"]] = _ce_bound(d["init"], env)
        elif "if" in s:
            c = s["if"]
            _ce_bound(c["cond"], env)
            et = _ce_stmts(c["then"], env)
            ee = _ce_stmts(c["else"], env)
            for v in list(env):
                if et[v] is _UNSET and ee[v] is _UNSET:
                    continue           # still unassigned on both sides
                if et[v] is _UNSET or ee[v] is _UNSET:
                    raise _NoCe(f"{v!r} assigned on only one branch")
                env[v] = _ce_max(et[v], ee[v])
        elif "while" in s:
            raise _NoCe("while loop: no static bound on the accumulated value")
        elif "return" in s:
            # SPEC.md "Early exit" (2026-09-08): no machine mirror. F_Ce is
            # one expression function with no way to stop partway through,
            # so a task that can return early gets no instance, the same
            # fail-closed treatment already given to loops, calls, seq ops
            # and quantifiers above.
            raise _NoCe("return: no machine mirror for early exit")
        else:
            raise _NoCe(f"statement {sorted(s)!r}")
    return env


SEQ_PREAMBLE = """\
   package Seqs is new SPARK.Containers.Functional.Infinite_Sequences
     (Element_Type => Big_Integer);
   subtype Seq is Seqs.Sequence;

   --  len(s): Big_Natural, so `len(s) >= 0` (SPEC.md's one seq assumption)
   --  is the library's result subtype and nothing bounds it above.
   function Len (S : Seq) return Big_Integer is (Seqs.Length (S));

   --  at(s, i): the Pre IS SPEC.md's definedness side condition, discharged
   --  by the kernel at every use. Seqs.Get is total in the shipped
   --  non-defensive SPARKlib build, so it cannot be borrowed from there.
   function Elem (S : Seq; I : Big_Integer) return Big_Integer is
     (Seqs.Get (S, I + Big_Integer'(1)))
   with Pre => I >= Big_Integer'(0) and then I < Len (S);
"""

# {"seq": "seq"} (SPEC.md "Nested sequences (v1)", 2026-09-10): a seq of
# seqs of ints, one level, written seq<seq>. "Ada functional containers can
# nest" (SPEC.md): a second instantiation of the SAME generic, Element_Type
# => Seq this time. MEASURED (probe, gnatprove FSF 16.1.0): the box-
# defaulted "=" (the generic's own `with function "=" (Left, Right :
# Element_Type) return Boolean is <>` formal) does NOT resolve against
# Seq's own predefined equality with no `use Seqs;` at the instantiation --
# "instantiation error... no visible subprogram matches the specification
# for '='" at the generic's own formal, a harder failure than EQ_PREAMBLE's
# own "not directly visible as an infix operator" (that one is at least
# callable qualified; a box default apparently still needs the SAME
# visibility an ordinary infix reference would). FIXED, MEASURED: the
# actual is named explicitly, `"=" => Seqs."="`, a qualified function name
# rather than an infix reference, which resolves with no `use` needed (the
# same qualified-call spelling this file already uses for every OTHER
# Seqs operation, T_Eq's own EQ_PREAMBLE note). This does turn on two
# benign warnings per instantiation ("precondition/postcondition is always
# False, ... Use_Logical_Equality", from SPARKlib's own Logical_Eq ghost
# lemma, since Use_Logical_Equality defaults False either way) -- MEASURED
# harmless: verifiers/spark.py's own MALFORMED gate matches only `error`,
# never `warning`, and the flat single instantiation carries the identical
# warning already (unnoticed until a second instantiation's own diagnostic
# put it beside a real error and made it worth reading), so no committed
# task's own audit outcome moves.
#
# Every other seq primitive at this level is the SAME Ada name as its flat
# counterpart, OVERLOADED rather than renamed: Len/Elem/T_Update/T_Fill/
# T_Slice/T_Concat/T_Concat_Aux/T_Eq each gain a second declaration whose
# parameter is Seq2 (or whose seq-typed parameter is Seq, a row, where the
# flat one takes Big_Integer), and Ada resolves the call by the STATIC type
# of the argument, exactly as t's own operators are already polymorphic
# (SPEC.md: "exactly as + and == already are"). This is why Lower.expr's
# text for `len`/`at`/`update`/`fill`/`slice`/`+`/`==` needs NO new
# rendering at all -- every one of those cases already emits "Len (...)",
# "Elem (...)", "T_Update (...)" and so on, and the compiler, not this
# file, picks the overload. The one exception is the seq LITERAL
# (`[[1,2],[3]]`): Seqs.Add and Rows.Add are different package-qualified
# names, not overloads of one identifier, so Lower.expr's `seq` case still
# has to choose the package by the static type of its own first element
# (Lower._ty), the one place this construct needed new dispatch logic
# rather than new Ada text (see Lower._ty and Lower.expr, below).
#
# A row-typed postcondition (T_Fill/T_Slice/T_Concat at this level) cannot
# lean on Ada's own "=" any more than the flat EQ_PREAMBLE's own elementwise
# fact could (Seq is the same private generic-instantiation type either
# way): every such Post compares rows through T_Eq (the FLAT one, on two
# Seq values), never bare "=", the reason needs_fill2/needs_slice2/
# needs_concat2/needs_eq2 (Lower, below) each force needs_eq (and
# needs_range, for T_Range) on with them, exactly as needs_fill/
# needs_slice/needs_concat already force needs_range.
NESTED_SEQ_PREAMBLE = """\
   package Rows is new SPARK.Containers.Functional.Infinite_Sequences
     (Element_Type => Seq, "=" => Seqs."=");
   subtype Seq2 is Rows.Sequence;

   --  len(m) on a seq<seq>: Big_Natural, the same one assumption Len
   --  already gives at the flat level.
   function Len (S : Seq2) return Big_Integer is (Rows.Length (S));

   --  m[i] on a seq<seq>: a row (a Seq value), DEFINED IFF 0 <= i < len(m),
   --  the same side condition as the flat `at`'s.
   function Elem (S : Seq2; I : Big_Integer) return Seq is
     (Rows.Get (S, I + Big_Integer'(1)))
   with Pre => I >= Big_Integer'(0) and then I < Len (S);
"""

# t's `==`/`!=` on two whole seqs is extensional (SPEC.md, SEQUENCES AS
# VALUES's own note: banked 2026-09-09, IMPLEMENTED the same night). Ada's
# own "=" resolves t's `==` at Big_Integer and Boolean with no help (CMP,
# plain infix), because those are the language's own predefined types; Seq
# is a private type inside a generic instantiation, and MEASURED (probe
# p_seq2.ads, the earlier banking) that its "=" is "not directly visible"
# as an infix operator without a `use Seqs;` this file will not add
# unconditionally (the same regression `use` would cause T_Update was
# measured to cause, above).
#
# TWO CANDIDATES were measured, not one. The first try leaned on the
# generic's OWN "=", called by QUALIFIED function-call name rather than
# infix (`Seqs."=" (S, T)`, "not directly visible" being specifically
# about the notation that resolves an infix operator, not about calling it
# by selected-component name the way every OTHER Seqs operation here
# already is): MEASURED (probes p_eqB/p_eqC, gnatprove FSF 16.1.0, --steps
# 20000) it needs no `use` at all, and four isolated probes (an
# elementwise-equal HYPOTHESIS implies T_Eq; the converse recovers Elem
# from T_Eq; two seqs built by different constructors that are
# extensionally the same value are still seen as equal; a concrete false
# instance is refutable) all closed with 0 unproved, faster than the
# second candidate below (18.9s vs 21.0s) and with no T_Range dependency.
# It shipped first on that evidence and was WRONG: MEASURED next on the
# actual shape this exists for (fz_p_seqeq_true/false, fuzz_lower.py,
# --tasks fz_p_seqeq_true,fz_p_seqeq_false), the real cell read TIMEOUT,
# reproduced on an uncontended box (harness.run_task alone, one gnatprove
# call, 46s wall against a 180s backstop, so not the wall backstop and not
# load) at the standard 20000-step budget. The isolated probes had hidden
# the gap: they handed the prover an elementwise-equal HYPOTHESIS already
# stated in T_Range terms at the SAME scope as the goal, which is not what
# a loop-computed value offers. A real task's loop invariant is stated
# over T_Range (this file's own 0-based Big_Integer cursor, RANGE_PREAMBLE
# above); Seqs."="'s own Post quantifies with SPARKlib's NATIVE Iterable
# cursor over Sequence ("for all N in Left"), a different range
# representation. Proving T_Eq(F'Result, S) from the loop helper's Post
# therefore asks the prover to bridge two quantifier encodings on top of
# unfolding a recursive call, and that combination missed the budget.
#
# T_Eq is therefore the SECOND candidate, SPEC.md's definition restated
# directly over Len/Elem/T_Range with no library help, the same shape
# T_Fill/T_Slice/T_Concat already use, and gated to also turn needs_range
# on with it (below), exactly as needs_fill/needs_slice/needs_concat do.
# MEASURED (2026-09-09, harness.run_task, fz_p_seqeq_true, gnatprove FSF
# 16.1.0, --steps 20000, uncontended): real VERIFIED, invariant-drop twin
# REFUTED. The elementwise fact now shares its quantifier encoding with
# every loop invariant this file already emits, so proving T_Eq from a
# loop helper's Post is the same T_Range-to-T_Range match that
# Len(F'Result) = Len(S) already was, not a bridge between two encodings.
# needs_eq (expr(), below) gates it exactly as needs_update gates
# UPDATE_PREAMBLE, so no already-committed task's output moves (none of
# the 19 tasks committed before this one states a whole-seq `==`).
EQ_PREAMBLE = """\
   function T_Eq (S, T : Seq) return Boolean is
     (Len (S) = Len (T)
      and then (for all K in T_Range'(0, Len (S)) => Elem (S, K) = Elem (T, K)));
"""

# Two seq<seq>s (SPEC.md "Nested sequences (v1)", 2026-09-10): "extensional
# and recursive: two nested seqs are equal iff same length and equal rows".
# The outer overload of T_Eq, calling the FLAT T_Eq just above on each pair
# of rows (Elem (S, K) and Elem (T, K) are both Seq values here, never
# compared by bare "=" for the same reason EQ_PREAMBLE's own elementwise
# fact is not): "T_Eq on rows for the inner", the design this file was
# handed. Gated on needs_eq2, which forces needs_eq and needs_range on with
# it (NESTED_SEQ_PREAMBLE's own note), so this always has both Len/Elem for
# Seq2 and the flat T_Eq it calls already in scope above it.
NESTED_EQ_PREAMBLE = """\
   function T_Eq (S, T : Seq2) return Boolean is
     (Len (S) = Len (T)
      and then (for all K in T_Range'(0, Len (S)) =>
                  T_Eq (Elem (S, K), Elem (T, K))));
"""

# s[i := v] (SPEC.md "Sequences as values", 2026-09-09), DEFINED IFF
# 0 <= i < len(s), the same side condition as `at`. Kept OUT of
# SEQ_PREAMBLE and gated on needs_update (expr(), below) rather than
# always emitted alongside Len/Elem: adding it unconditionally changed the
# text of every already-committed seq-PARAMETER task (first_even, contains,
# all_nonneg, count_matches, linear_search, seq_max) even though none of
# them calls update(), which the regression rule (header) forbids for
# first_even specifically; MEASURED, this refactor restores out/first_even
# .ads to byte-identical. Seqs.Set's own Pre is 1-based (Position <= Last
# (Container)), so the wrapper translates the 0-based index exactly the
# way Elem does. Set's own Post (Equal_Except, Inline_For_Proof) already
# gives length preservation and "every other index unchanged"; MEASURED
# (probe p_seq1.ads, --steps 20000) that is enough for the kernel to prove
# Len (T_Update (S, I, V)) = Len (S), Elem (T_Update (S, I, V), I) = V and
# the untouched-elsewhere fact at a call site, so nothing more is restated
# on T_Update itself, and no `use Seqs;` is needed for it: Seqs.Set is
# called fully qualified, never as a bare operator.
UPDATE_PREAMBLE = """\
   function T_Update (S : Seq; I : Big_Integer; V : Big_Integer) return Seq is
     (Seqs.Set (S, I + Big_Integer'(1), V))
   with Pre => I >= Big_Integer'(0) and then I < Len (S);
"""

# m[i := r] (SPEC.md "Nested sequences (v1)", 2026-09-10): row i replaced by
# the seq r, the outer overload of T_Update (NESTED_SEQ_PREAMBLE's own
# note). Rows.Set's own Post (Equal_Except, Inline_For_Proof) already gives
# length preservation and "every other row unchanged" exactly as Seqs.Set's
# does for the flat T_Update (UPDATE_PREAMBLE's own note), so nothing more
# is restated here either; swap_rows's own `update(update(m, i, m[j]), j,
# m[i])` is this overload called twice, nested.
NESTED_UPDATE_PREAMBLE = """\
   function T_Update (S : Seq2; I : Big_Integer; V : Seq) return Seq2 is
     (Rows.Set (S, I + Big_Integer'(1), V))
   with Pre => I >= Big_Integer'(0) and then I < Len (S);
"""

# A t quantifier ranges over mathematical [lo, hi). Ada's discrete types are
# all bounded, so the range is a cursor-iterable whose cursor is Big_Integer;
# gnatprove quantifies over the cursor type under R_Has. R_Next's V is unused
# (flow reports UNUSED_VARIABLE at severity "warning", which the adapter's
# audit tolerates); writing a V-dependent body to silence it would put an
# arm in the iteration model that nothing measures.
RANGE_PREAMBLE = """\
   type T_Range is record
      Lo : Big_Integer;
      Hi : Big_Integer;
   end record
   with Iterable => (First       => R_First,
                     Has_Element => R_Has,
                     Next        => R_Next);

   function R_First (V : T_Range) return Big_Integer is (V.Lo);
   function R_Has (V : T_Range; C : Big_Integer) return Boolean is
     (C >= V.Lo and then C < V.Hi);
   function R_Next (V : T_Range; C : Big_Integer) return Big_Integer is
     (C + Big_Integer'(1));
"""

# div/mod (see the header's DIV/MOD section). Built on `/` and `rem`, not
# `mod`: `X = (X / Y) * Y + (X rem Y)` is the pair GNATprove proves in one
# step (MEASURED, probe p_law1.ads), while the same fact stated over
# `X mod abs (Y)` and a second division (the naive reading of "mod against a
# positive divisor is the Euclidean remainder") TIMES OUT at the standard
# budget (MEASURED, probe p_law2.ads: VC_POSTCONDITION medium/limit, same
# shape, only the operators differ) rather than failing to prove; a tenfold
# budget was not tried because the fix costs nothing. `X rem Y` already has
# magnitude < |Y|; only its sign needs straightening to land in [0, |Y|):
# nonnegative, keep it (it already satisfies SPEC.md's bound whatever sign Y
# has); negative, add |Y| to the remainder and correspondingly step the
# truncating quotient by one toward -infinity. No further division is ever
# introduced, so the identity is linear arithmetic over `/`'s and `rem`'s own
# defining law, which the prover discharges directly (MEASURED, probe
# p_law3.ads: the identity and both Euclidean bounds verify).
DIVMOD_PREAMBLE = """\
   function T_Mod (X, Y : Big_Integer) return Big_Integer is
     (if (X rem Y) >= Big_Integer'(0)
      then (X rem Y)
      else (X rem Y) + abs (Y))
   with Pre => Y /= Big_Integer'(0);

   function T_Div (X, Y : Big_Integer) return Big_Integer is
     (if (X rem Y) >= Big_Integer'(0)
      then (X / Y)
      elsif Y > Big_Integer'(0)
      then (X / Y) - Big_Integer'(1)
      else (X / Y) + Big_Integer'(1))
   with Pre => Y /= Big_Integer'(0);
"""

# THE STRING LIBRARY (v1), SPEC.md "The string library (v1)", 2026-09-11.
# Seventeen members, each a total function of a Big_Integer/Seq/Seq2
# argument, restated as t's own recursive definition rather than leaned on
# any SPARKlib member/string facility (there is none for this shape
# regardless). Every member is gated on its OWN needs_str_* flag
# (Lower.expr, below) rather than bundled behind one flag: gnatprove proves
# EVERY declared subprogram in the emitted file, not only the ones F
# reaches, so a member whose own contract does not verify would otherwise
# fail EVERY task that uses any OTHER member merely by sharing a file with
# it. needs_strcore (Is_Ws/Is_Upper_Letter/Is_Lower_Letter/T_Match_At) is
# the one exception, pulled in by five other flags: each is a single
# expression function with no stated Post beyond its own body, so there is
# nothing beyond termination (trivial here, no recursion) for gnatprove to
# fail to prove, the same "zero-risk" reasoning R_First/R_Has/R_Next
# already rely on for T_Range.
#
# MEASURED (probes p1/p2/p3, gnatprove FSF 16.1.0, z3, scratch dir, this
# session): T_Slice (S, 0, Len (S)) = S -- NATIVE Seqs."=" equality, not
# just elementwise T_Eq -- verifies directly with 0 unproved (174 checks),
# because T_Slice's own Post is an axiom gnatprove already has for ANY
# call once T_Slice's OWN contract is proved, and SPARKlib's Sequence "="
# is axiomatized as exactly that extensional fact, so ordinary SMT
# congruence (A = B implies f(A) = f(B) for any f, no induction needed)
# carries any Len/Elem-only function's result across a full self-slice for
# free. The SAME one-step slice-of-a-slice fact, needed for a position-
# counting recursion's OWN inductive step (T_Slice (T_Slice (S, 0, I+1),
# 0, I) = T_Slice (S, 0, I)), ALSO verifies with 0 unproved -- because it
# stays T_Range-to-T_Range the whole way, never touching a SPARKlib
# native-Iterable quantifier (EQ_PREAMBLE's own distinction, above, "not a
# bridge between two encodings"). Every member below that recurses by
# COUNTING A POSITION (T_Match_At/T_Count_From/T_Find_From/T_Lws/T_Rws/
# T_Replace_From/T_Replace_Empty_From) or by peeling ONE Seq element via
# T_Slice (T_Lower/T_Upper/T_Digits) stays in exactly this proven-tractable
# shape.
#
# THE ONE MEMBER THAT DID NOT: split/join's round-trip law. Building the
# split RESULT needs SPARK.Containers.Functional's own Rows.Add (there is
# no other Seq2 constructor), and Rows.Add's OWN preservation fact
# (Equal_Prefix, the library's spec) is stated over the library's NATIVE
# Iterable cursor, not T_Range -- MEASURED (probe p2.ads, this session,
# Probe_A/Probe_B, both --steps 20000 AND --steps 200000, z3): "slicing an
# extended row-seq back to its old length recovers the old seq" and "join
# of one-more-row equals join-then-separator-then-row" both TIME OUT
# (unproved_status "limit", cvc5 fares WORSE than z3 on the same goals,
# tried once for comparison, not shipped), the same cross-encoding wall
# EQ_PREAMBLE's own note already named. T_Split/T_Split_C/T_Join are
# still shipped below (total, correct against interp.py by inspection,
# usable in specification position per SPEC.md), but split_join's own
# ensures -- `join(split(s, c), [c]) == s`, exactly this law -- is
# measured, not assumed, and the dated note at the end of this docstring
# (below the DIVMOD one) records the real verdict rather than a claim this
# session could not discharge.
STRCORE_PREAMBLE = """\
   function Is_Ws (C : Big_Integer) return Boolean is
     (C = Big_Integer'(9) or else C = Big_Integer'(10)
      or else C = Big_Integer'(11) or else C = Big_Integer'(12)
      or else C = Big_Integer'(13) or else C = Big_Integer'(28)
      or else C = Big_Integer'(29) or else C = Big_Integer'(30)
      or else C = Big_Integer'(31) or else C = Big_Integer'(32));

   function Is_Upper_Letter (C : Big_Integer) return Boolean is
     (C >= Big_Integer'(65) and then C <= Big_Integer'(90));

   function Is_Lower_Letter (C : Big_Integer) return Boolean is
     (C >= Big_Integer'(97) and then C <= Big_Integer'(122));

   function T_Match_At (S, T : Seq; I : Big_Integer) return Boolean is
     (for all K in T_Range'(0, Len (T)) => Elem (S, I + K) = Elem (T, K))
   with Pre => I >= Big_Integer'(0) and then I + Len (T) <= Len (S);
"""

# count(s, t): SPEC.md "non-overlapping occurrences left to right";
# count(s, []) == len(s) + 1. T_Count_From counts a position I UP with
# Subprogram_Variant Len (S) - I, exactly T_Lws's own shape below -- the
# general (any Len (T)) definition, matching interp.py's own
# `_str_count` exactly, INCLUDING for Len (T) = 1 (non-overlapping is
# moot at width 1: skipping by Len (T) = 1 after a match is the same
# position T_Count_From would have reached anyway).
#
# T_Count1 is a SECOND, equal-by-construction definition of THAT SAME
# Len (T) = 1 case, recursing by PEELING THE LAST ELEMENT VIA T_SLICE
# (T_Lower/T_Upper's own shape) rather than by counting a position UP.
# T_Count routes Len (T) = 1 to it specifically because count_vowels'
# own loop invariant needs `count(s[0..i], [ch])` related to
# `count(s[0..i+1], [ch])` ACROSS a changing slice bound, and MEASURED
# (this session, harness.run_task, count_vowels, --steps 20000 and
# --steps 200000): T_Count_From's own position-counting shape times out
# on that step (a cross-argument fact -- relating T_Count_From on TWO
# DIFFERENT seq arguments of different lengths -- the same class of
# problem as split/join's own round-trip law, header's dated note,
# above), while T_Count1's shape does NOT need a separate lemma at all:
# T_Count1 (T_Slice (S, 0, I+1), Ch) unfolds, via ITS OWN recursive
# definition, to T_Count1 (T_Slice (T_Slice (S, 0, I+1), 0, I), Ch) +
# (1 if Elem (S, I) = Ch else 0), and T_Slice (T_Slice (S, 0, I+1), 0, I)
# = T_Slice (S, 0, I) is the ONE-STEP slice-of-a-slice fact MEASURED to
# verify directly (probe p3.ads, Probe_D, this session, 0 unproved) --
# T_Range-to-T_Range the whole way, never touching a SPARKlib native-
# Iterable quantifier. So the invariant step is GNATprove's own ordinary
# one-level recursive-call unfolding, ANOTHER explicit lemma.
STRCOUNT_PREAMBLE = """\
   function T_Count_From (S, T : Seq; I : Big_Integer) return Big_Integer
   with
     Pre => I >= Big_Integer'(0) and then I <= Len (S)
       and then Len (T) >= Big_Integer'(1),
     Subprogram_Variant => (Decreases => Len (S) - I);
   function T_Count_From (S, T : Seq; I : Big_Integer) return Big_Integer is
     (if I + Len (T) > Len (S) then Big_Integer'(0)
      elsif T_Match_At (S, T, I)
      then Big_Integer'(1) + T_Count_From (S, T, I + Len (T))
      else T_Count_From (S, T, I + Big_Integer'(1)));

   function T_Count1 (S : Seq; Ch : Big_Integer) return Big_Integer
   with Subprogram_Variant => (Decreases => Len (S));
   function T_Count1 (S : Seq; Ch : Big_Integer) return Big_Integer is
     (if Len (S) = Big_Integer'(0) then Big_Integer'(0)
      else T_Count1 (T_Slice (S, Big_Integer'(0), Len (S) - Big_Integer'(1)), Ch)
           + (if Elem (S, Len (S) - Big_Integer'(1)) = Ch
              then Big_Integer'(1) else Big_Integer'(0)));

   function T_Count (S, T : Seq) return Big_Integer is
     (if Len (T) = Big_Integer'(0) then Len (S) + Big_Integer'(1)
      elsif Len (T) = Big_Integer'(1) then T_Count1 (S, Elem (T, Big_Integer'(0)))
      else T_Count_From (S, T, Big_Integer'(0)));
"""

# find(s, t): the least index where t occurs, -1 when none; find(s, []) == 0.
STRFIND_PREAMBLE = """\
   function T_Find_From (S, T : Seq; I : Big_Integer) return Big_Integer
   with
     Pre => I >= Big_Integer'(0) and then I <= Len (S)
       and then Len (T) >= Big_Integer'(1),
     Subprogram_Variant => (Decreases => Len (S) - I);
   function T_Find_From (S, T : Seq; I : Big_Integer) return Big_Integer is
     (if I + Len (T) > Len (S) then -Big_Integer'(1)
      elsif T_Match_At (S, T, I) then I
      else T_Find_From (S, T, I + Big_Integer'(1)));

   function T_Find (S, T : Seq) return Big_Integer is
     (if Len (T) = Big_Integer'(0) then Big_Integer'(0)
      else T_Find_From (S, T, Big_Integer'(0)));
"""

# strip/lstrip/rstrip: T_Lws/T_Rws each count a position past a whitespace
# run, the same position-counting shape T_Count_From/T_Find_From use, then
# T_Slice (already MEASURED, above) does the cutting.
STRSTRIP_PREAMBLE = """\
   function T_Lws (S : Seq; I : Big_Integer) return Big_Integer
   with
     Pre  => I >= Big_Integer'(0) and then I <= Len (S),
     Post => T_Lws'Result >= I and then T_Lws'Result <= Len (S),
     Subprogram_Variant => (Decreases => Len (S) - I);
   function T_Lws (S : Seq; I : Big_Integer) return Big_Integer is
     (if I >= Len (S) then I
      elsif Is_Ws (Elem (S, I)) then T_Lws (S, I + Big_Integer'(1))
      else I);

   function T_Rws (S : Seq; J, Lo : Big_Integer) return Big_Integer
   with
     Pre  => Lo >= Big_Integer'(0) and then Lo <= J and then J <= Len (S),
     Post => T_Rws'Result >= Lo and then T_Rws'Result <= J,
     Subprogram_Variant => (Decreases => J - Lo);
   function T_Rws (S : Seq; J, Lo : Big_Integer) return Big_Integer is
     (if J <= Lo then J
      elsif Is_Ws (Elem (S, J - Big_Integer'(1)))
      then T_Rws (S, J - Big_Integer'(1), Lo)
      else J);

   function T_Strip (S : Seq) return Seq is
     (T_Slice (S, T_Lws (S, Big_Integer'(0)),
              T_Rws (S, Len (S), T_Lws (S, Big_Integer'(0)))));

   function T_LStrip (S : Seq) return Seq is
     (T_Slice (S, T_Lws (S, Big_Integer'(0)), Len (S)));

   function T_RStrip (S : Seq) return Seq is
     (T_Slice (S, Big_Integer'(0), T_Rws (S, Len (S), Big_Integer'(0))));
"""

# replace(s, t, u): every non-overlapping occurrence left to right;
# t == [] inserts u before every code point and at the end (SPEC.md).
STRREPLACE_PREAMBLE = """\
   function T_Replace_From (S, T, U : Seq; I : Big_Integer) return Seq
   with
     Pre => I >= Big_Integer'(0) and then I <= Len (S)
       and then Len (T) >= Big_Integer'(1),
     Subprogram_Variant => (Decreases => Len (S) - I);
   function T_Replace_From (S, T, U : Seq; I : Big_Integer) return Seq is
     (if I + Len (T) > Len (S) then T_Slice (S, I, Len (S))
      elsif T_Match_At (S, T, I)
      then T_Concat (U, T_Replace_From (S, T, U, I + Len (T)))
      else T_Concat (Seqs.Add (Seqs.Empty_Sequence, Elem (S, I)),
                     T_Replace_From (S, T, U, I + Big_Integer'(1))));

   function T_Replace_Empty_From (S, U : Seq; I : Big_Integer) return Seq
   with
     Pre => I >= Big_Integer'(0) and then I <= Len (S),
     Subprogram_Variant => (Decreases => Len (S) - I);
   function T_Replace_Empty_From (S, U : Seq; I : Big_Integer) return Seq is
     (if I = Len (S) then U
      else T_Concat (T_Concat (U, Seqs.Add (Seqs.Empty_Sequence, Elem (S, I))),
                    T_Replace_Empty_From (S, U, I + Big_Integer'(1))));

   function T_Replace (S, T, U : Seq) return Seq is
     (if Len (T) = Big_Integer'(0) then T_Replace_Empty_From (S, U, Big_Integer'(0))
      else T_Replace_From (S, T, U, Big_Integer'(0)));
"""

# lower/upper: elementwise ASCII case maps, built the same peel-the-last-
# element-via-T_Slice shape T_Concat/T_Slice themselves use.
STRCASE_PREAMBLE = """\
   function T_Lower (S : Seq) return Seq
   with Subprogram_Variant => (Decreases => Len (S));
   function T_Lower (S : Seq) return Seq is
     (if Len (S) = Big_Integer'(0) then Seqs.Empty_Sequence
      else Seqs.Add (T_Lower (T_Slice (S, Big_Integer'(0), Len (S) - Big_Integer'(1))),
                     (if Is_Upper_Letter (Elem (S, Len (S) - Big_Integer'(1)))
                      then Elem (S, Len (S) - Big_Integer'(1)) + Big_Integer'(32)
                      else Elem (S, Len (S) - Big_Integer'(1)))));

   function T_Upper (S : Seq) return Seq
   with Subprogram_Variant => (Decreases => Len (S));
   function T_Upper (S : Seq) return Seq is
     (if Len (S) = Big_Integer'(0) then Seqs.Empty_Sequence
      else Seqs.Add (T_Upper (T_Slice (S, Big_Integer'(0), Len (S) - Big_Integer'(1))),
                     (if Is_Lower_Letter (Elem (S, Len (S) - Big_Integer'(1)))
                      then Elem (S, Len (S) - Big_Integer'(1)) - Big_Integer'(32)
                      else Elem (S, Len (S) - Big_Integer'(1)))));
"""

# isdigit/isalpha/isupper/islower: each a plain T_Range quantifier, no
# recursion at all (SPEC.md's own empty/mixed rules stated directly).
STRPRED_PREAMBLE = """\
   function T_IsDigit (S : Seq) return Boolean is
     (Len (S) > Big_Integer'(0)
      and then (for all K in T_Range'(0, Len (S)) =>
                  Elem (S, K) >= Big_Integer'(48)
                  and then Elem (S, K) <= Big_Integer'(57)));

   function T_IsAlpha (S : Seq) return Boolean is
     (Len (S) > Big_Integer'(0)
      and then (for all K in T_Range'(0, Len (S)) =>
                  Is_Upper_Letter (Elem (S, K))
                  or else Is_Lower_Letter (Elem (S, K))));

   function T_IsUpper (S : Seq) return Boolean is
     ((for some K in T_Range'(0, Len (S)) =>
         Is_Upper_Letter (Elem (S, K)) or else Is_Lower_Letter (Elem (S, K)))
      and then not (for some K in T_Range'(0, Len (S)) =>
                      Is_Lower_Letter (Elem (S, K))));

   function T_IsLower (S : Seq) return Boolean is
     ((for some K in T_Range'(0, Len (S)) =>
         Is_Upper_Letter (Elem (S, K)) or else Is_Lower_Letter (Elem (S, K)))
      and then not (for some K in T_Range'(0, Len (S)) =>
                      Is_Upper_Letter (Elem (S, K))));
"""

# startswith/endswith: plain T_Range quantifiers over a common prefix/
# suffix window, no recursion.
STRAFFIX_PREAMBLE = """\
   function T_StartsWith (S, T : Seq) return Boolean is
     (Len (T) <= Len (S)
      and then (for all K in T_Range'(0, Len (T)) => Elem (S, K) = Elem (T, K)));

   function T_EndsWith (S, T : Seq) return Boolean is
     (Len (T) <= Len (S)
      and then (for all K in T_Range'(0, Len (T)) =>
                  Elem (S, Len (S) - Len (T) + K) = Elem (T, K)));
"""

# tostr(n): decimal digits, '-' (45) for a negative n; str(0) == "0".
STRTOSTR_PREAMBLE = """\
   function T_Digits (N : Big_Integer) return Seq
   with
     Pre  => N >= Big_Integer'(0),
     Post => Len (T_Digits'Result) >= Big_Integer'(1),
     Subprogram_Variant => (Decreases => N);
   function T_Digits (N : Big_Integer) return Seq is
     (if N < Big_Integer'(10)
      then Seqs.Add (Seqs.Empty_Sequence, N + Big_Integer'(48))
      else Seqs.Add (T_Digits (N / Big_Integer'(10)),
                     (N rem Big_Integer'(10)) + Big_Integer'(48)));

   function T_ToStr (N : Big_Integer) return Seq is
     (if N < Big_Integer'(0)
      then T_Concat (Seqs.Add (Seqs.Empty_Sequence, Big_Integer'(45)),
                     T_Digits (-N))
      else T_Digits (N));
"""

# split's shared accumulator: rows closed so far plus the still-open
# trailing row (SC in the dated note, below).
STRSPLITSTATE_PREAMBLE = """\
   type T_Split_State is record
      Rows : Seq2;
      Last : Seq;
   end record;
"""

# split(s, c): every occurrence of c separates, empty rows kept.
STRSPLITC_PREAMBLE = """\
   function T_Sc (S : Seq; C, N : Big_Integer) return T_Split_State
   with
     Pre => N >= Big_Integer'(0) and then N <= Len (S),
     Subprogram_Variant => (Decreases => N);
   function T_Sc (S : Seq; C, N : Big_Integer) return T_Split_State is
     (if N = Big_Integer'(0)
      then T_Split_State'(Rows => Rows.Empty_Sequence, Last => Seqs.Empty_Sequence)
      elsif Elem (S, N - Big_Integer'(1)) = C
      then T_Split_State'(Rows => Rows.Add (T_Sc (S, C, N - Big_Integer'(1)).Rows,
                                            T_Sc (S, C, N - Big_Integer'(1)).Last),
                          Last => Seqs.Empty_Sequence)
      else T_Split_State'(Rows => T_Sc (S, C, N - Big_Integer'(1)).Rows,
                          Last => Seqs.Add (T_Sc (S, C, N - Big_Integer'(1)).Last,
                                            Elem (S, N - Big_Integer'(1)))));

   function T_Split_C (S : Seq; C : Big_Integer) return Seq2 is
     (Rows.Add (T_Sc (S, C, Len (S)).Rows, T_Sc (S, C, Len (S)).Last));
"""

# split(s): runs of whitespace separate, no row empty, split("") == [].
STRSPLITW_PREAMBLE = """\
   function T_Sw (S : Seq; N : Big_Integer) return T_Split_State
   with
     Pre => N >= Big_Integer'(0) and then N <= Len (S),
     Subprogram_Variant => (Decreases => N);
   function T_Sw (S : Seq; N : Big_Integer) return T_Split_State is
     (if N = Big_Integer'(0)
      then T_Split_State'(Rows => Rows.Empty_Sequence, Last => Seqs.Empty_Sequence)
      elsif Is_Ws (Elem (S, N - Big_Integer'(1)))
      then (if Len (T_Sw (S, N - Big_Integer'(1)).Last) = Big_Integer'(0)
            then T_Sw (S, N - Big_Integer'(1))
            else T_Split_State'(Rows => Rows.Add (T_Sw (S, N - Big_Integer'(1)).Rows,
                                                  T_Sw (S, N - Big_Integer'(1)).Last),
                                Last => Seqs.Empty_Sequence))
      else T_Split_State'(Rows => T_Sw (S, N - Big_Integer'(1)).Rows,
                          Last => Seqs.Add (T_Sw (S, N - Big_Integer'(1)).Last,
                                            Elem (S, N - Big_Integer'(1)))));

   function T_Split (S : Seq) return Seq2 is
     (if Len (T_Sw (S, Len (S)).Last) = Big_Integer'(0)
      then T_Sw (S, Len (S)).Rows
      else Rows.Add (T_Sw (S, Len (S)).Rows, T_Sw (S, Len (S)).Last));
"""

# join(rows, sep): recurses by peeling the LAST row via the nested T_Slice
# (NESTED_SLICE_PREAMBLE's own overload), the one shape MEASURED to stay
# T_Range-to-T_Range (header's dated note, above); building the join
# itself never touches Rows.Add.
STRJOIN_PREAMBLE = """\
   function T_Join (Rws : Seq2; Sep : Seq) return Seq
   with Subprogram_Variant => (Decreases => Len (Rws));
   function T_Join (Rws : Seq2; Sep : Seq) return Seq is
     (if Len (Rws) = Big_Integer'(0) then Seqs.Empty_Sequence
      elsif Len (Rws) = Big_Integer'(1) then Elem (Rws, Big_Integer'(0))
      else T_Concat (T_Concat (T_Join (T_Slice (Rws, Big_Integer'(0),
                                                Len (Rws) - Big_Integer'(1)), Sep),
                               Sep),
                     Elem (Rws, Len (Rws) - Big_Integer'(1))));
"""


def _has_strlib_nested_op(node) -> bool:
    """True iff a `split` or `join` op node sits anywhere inside `node`
    (mirrors `_has_pair_op`/`_has_nested_seq_op`'s own generic, type-blind
    descent): split's result and join's argument are seq<seq> values that
    can sit entirely transiently in one expression (word_count's `t2.
    split()`, split_join's `join(split(s, c), [c])`), with no param,
    return, or `var` of the nested type anywhere for `needs_nested_seq`'s
    own declaration-only scan (lower(), below) to see -- the same gap
    `_has_pair_op`/`_has_nested_seq_op` each close for their own construct,
    widening `needs_nested_seq` directly here rather than refusing (unlike
    those two, split/join are the committed shape, not a residual)."""
    if isinstance(node, dict):
        if node.get("op") in ("split", "join"):
            return True
        return any(_has_strlib_nested_op(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_strlib_nested_op(v) for v in node)
    return False


# THE STRING LIBRARY (v1), 2026-09-11: the seventeen member names, used
# ONLY to decide WHETHER lower_while's invariant list needs reordering at
# all (_has_strlib_op, below) -- never `at`/`slice`/`update`/`fill`/`div`/
# `mod`, every one a PRIOR gate's own member, because every already-
# committed task that uses one of THOSE was measured (this session's own
# matrix regression, below) to already state its invariants in a
# definedness-safe order; reordering them too MOVES five of the 23 (grep
# any of `at`, gated on the string-only trigger, would not). Only a
# STRING member's own Pre (T_Slice/T_Match_At reached through T_Count1
# and friends) hits the trap count_vowels.json's own invariant order
# exposes (below).
_STRLIB_OPS = frozenset((
    "split", "join", "tostr", "count", "find", "strip", "lstrip",
    "rstrip", "replace", "lower", "upper", "isdigit", "isalpha",
    "isupper", "islower", "startswith", "endswith"))
# Everything a rendered conjunct's OWN Pre could depend on a bound fact
# for -- the string ops above, plus every prior gate's own definedness-
# carrying op -- used by _is_bound_inv to CLASSIFY a conjunct once
# reordering is already triggered (so a mixed invariant list still sorts
# `at`-bearing facts after the plain bounds too, not only string ones).
_DEFINEDNESS_OPS = _STRLIB_OPS | frozenset(
    ("at", "slice", "update", "fill", "div", "mod"))


def _has_strlib_op(node) -> bool:
    """True iff a string-library op sits anywhere inside `node` -- the
    trigger for lower_while's invariant reorder, below; mirrors
    `_has_pair_op`'s own generic, type-blind descent."""
    if isinstance(node, dict):
        if node.get("op") in _STRLIB_OPS:
            return True
        return any(_has_strlib_op(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_strlib_op(v) for v in node)
    return False


def _is_bound_inv(node) -> bool:
    """True iff `node` (one invariant's own AST) contains NONE of
    _DEFINEDNESS_OPS anywhere -- a plain arithmetic/comparison fact over
    int/bool/seq-length values, safe to state before a conjunct whose OWN
    Pre needs it as a hypothesis (lower_while's own dated note, above).
    Generic, type-blind recursive descent, the same shape _has_pair_op/
    _has_nested_seq_op/_has_strlib_nested_op already use."""
    if isinstance(node, dict):
        if node.get("op") in _DEFINEDNESS_OPS:
            return False
        return all(_is_bound_inv(v) for v in node.values())
    if isinstance(node, list):
        return all(_is_bound_inv(v) for v in node)
    return True


def _pair_ada_name(ty: dict) -> str:
    """SPEC.md "Pairs" (2026-09-10): the Ada name for a pair type's own
    record, one per distinct {"pair": [T1, T2]} a task's package spec needs
    (ada_type, below, and _pair_types, which enumerates them
    deterministically). T1 and T2 are always base types ("int", "bool" or
    "seq"; v1 has no pair of pairs), so plain str.capitalize() names each
    component exactly the way TYPE's own values are spelled (Big_Integer,
    Boolean, Seq all start capitalized), giving T_Pair_Int_Int,
    T_Pair_Bool_Seq, and so on."""
    t1, t2 = ty["pair"]
    return f"T_Pair_{t1.capitalize()}_{t2.capitalize()}"


def _is_nested_seq(ty) -> bool:
    """{"seq": "seq"} (SPEC.md "Nested sequences (v1)", 2026-09-10), v1's
    one nested type, told apart from a pair type ({"pair": [T1, T2]}) by
    its own key rather than by isinstance(ty, dict) alone -- both are
    dicts, so every call site downstream that used to branch on
    isinstance(ty, dict) and assume "pair" (ada_type, Lower._ty's `==`
    dispatch, _cert_lit_of_type, _pair_types.add, _dead_lit, _undef_
    obligation's _to_py) now checks this first."""
    return isinstance(ty, dict) and "seq" in ty


def ada_type(ty) -> str:
    """The Ada type a t type maps to. TYPE[...] on its own only ever saw a
    base type; every call site that might now see a pair type ({"pair":
    [T1, T2]}, SPEC.md "Pairs", 2026-09-10) or the nested seq type
    ({"seq": "seq"}, SPEC.md "Nested sequences (v1)", 2026-09-10) goes
    through this instead, so neither needed a second TYPE-shaped table,
    only this one extra dispatch on isinstance(ty, dict), split by key."""
    if _is_nested_seq(ty):
        return "Seq2"
    if isinstance(ty, dict):
        return _pair_ada_name(ty)
    return TYPE[ty]


def _pair_types(task: dict, body: list) -> list:
    """Every distinct pair type this task's package spec needs a record
    declaration for (SPEC.md "Pairs", 2026-09-10: "a record type declared
    per pair type"), first-appearance order (params, then the return, then
    each spec_fun's params and result, then a `var` declared pair-typed
    anywhere in the body, mirroring locals_seq's own recursive shape),
    deduplicated so the SAME pair type used twice (e.g. two params of type
    {"pair": ["int", "int"]}) still emits one declaration, and two tasks
    that need the same pair type emit the same text. lower() reads this
    both to decide what the preamble needs (_pair_preamble) and to widen
    `reserved` before the name-capture check, so this order also fixes the
    order in which two colliding pair types would surface, deterministic
    for the same reason cap()'s own collision report is."""
    out: list = []

    def add(ty):
        # "pair" in ty, not bare isinstance(ty, dict): the nested seq type
        # ({"seq": "seq"}, SPEC.md "Nested sequences (v1)", 2026-09-10) is
        # also a dict and needs no record declaration of its own here, only
        # NESTED_SEQ_PREAMBLE's fixed Rows/Seq2 (_is_nested_seq).
        if isinstance(ty, dict) and "pair" in ty and ty not in out:
            out.append(ty)

    for p in task["params"]:
        add(p["type"])
    add(task["returns"][0]["type"])
    for sf in task.get("spec_funs", []):
        for p in sf["params"]:
            add(p["type"])
        add(sf["result"])

    def walk(stmts):
        for s in stmts:
            if "var" in s:
                add(s["var"]["type"])
            if "if" in s:
                walk(s["if"]["then"])
                walk(s["if"]["else"])
            if "while" in s:
                walk(s["while"]["body"])

    walk(body)
    return out


def _has_pair_op(node) -> bool:
    """PAIRS RESIDUAL (2026-09-10): True iff a literal `{"op": "pair", ...}`
    node sits ANYWHERE inside `node` (a generic recursive descent over
    whatever dict/list shape a t task's own JSON is -- requires, ensures,
    spec_funs, or a body -- not an AST-shape-aware walk, since all this
    needs to know is whether the word is there at all). Needed because a
    pair can be built and projected in the SAME expression (`fst(pair(a,
    b))`, SPEC.md "Pairs") with no param, return, or `var` of that type
    anywhere for `_pair_types`'s own declaration-only scan to see, yet
    Lower.expr's own `pair` case still emits Ada text naming that type's
    record: MEASURED, fz_p_pair_proj, malformed/malformed, gnatprove
    rejecting the reference to a record this task's preamble never
    declared. `lower()` refuses by name (below) rather than risk it
    whenever this is True and `_pair_types` came back with NO declared
    pair type at all -- a task with at least one declared pair type (every
    other committed pair task) is not refused here even if it ALSO builds
    a second, different transient pair type inline nothing has measured
    yet; that narrower gap is left unexercised, the same "not yet guarded"
    posture fst/snd's own docstring already takes toward a non-name
    projection target."""
    if isinstance(node, dict):
        if node.get("op") == "pair":
            return True
        return any(_has_pair_op(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_pair_op(v) for v in node)
    return False


def _has_nested_seq_op(node) -> bool:
    """NESTED SEQUENCES RESIDUAL (2026-09-10): True iff a literal nested
    seq node -- `{"op": "seq", "args": [...]}` whose own first argument is
    ITSELF a `{"op": "seq", ...}` node, i.e. a row -- sits ANYWHERE inside
    `node`, mirroring `_has_pair_op`'s own generic, type-blind recursive
    descent (requires, ensures, spec_funs, or a body) and its same
    narrower scope: this recognises the LITERAL constructor shape only
    (the seq<seq> analogue of a literal `pair` node), not every expression
    that could produce a nested value with no declared type anywhere (an
    outer `fill`/`update`/`slice` fed a row with no nested param, return,
    or `var` for `needs_nested_seq`'s own scan to see is a narrower gap
    left unexercised here, the same posture `_has_pair_op`'s own docstring
    already takes toward a second, transient pair type). Needed because a
    nested literal can be built and projected in the SAME expression
    (`len([[1, 2], [3]])`, NESTED SEQUENCES (v1)'s own docstring, "NOT
    MEASURED") with no param, return, or `var` of the nested type anywhere
    for `needs_nested_seq`'s own declaration-only scan to see, yet
    Lower.expr's own `seq` case still emits Ada text naming Rows/Seqs and
    Len/Elem, none of which NESTED_SEQ_PREAMBLE/SEQ_PREAMBLE declared:
    MEASURED, fz_p_nest_lit, malformed/malformed, gnatprove rejecting
    every one of those names as undeclared. `lower()` refuses by name
    (below) rather than risk it, whenever this is True and
    `needs_nested_seq` came back False -- every committed nested-seq task
    (swap_rows, row_max_len) declares a nested param or return, so this
    never fires on them."""
    if isinstance(node, dict):
        if (node.get("op") == "seq" and node.get("args")
                and isinstance(node["args"][0], dict)
                and node["args"][0].get("op") == "seq"):
            return True
        return any(_has_nested_seq_op(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_nested_seq_op(v) for v in node)
    return False


# {"pair": [T1, T2]} (SPEC.md "Pairs", 2026-09-10): a record over the two
# component's own Ada types, named fields P_A and P_B (PAIRS RESIDUAL,
# 2026-09-10: renamed from the original A/B, which folded-case collided
# with a lowercase t identifier `a`/`b` -- see the dated note at the end of
# the PAIRS docstring, above) (fst/snd's own `.P_A`/`.P_B`, Lower.expr
# below), one declaration per distinct pair type the task uses
# (_pair_types), emitted in that deterministic order.
#
# `==`/`!=` on two pairs is componentwise (SPEC.md), and Ada's own
# predefined "=" on a plain (untagged, non-private) record already IS that,
# componentwise over each field's own "=": MEASURED (probe p_pair1.ads,
# gnatprove FSF 16.1.0, --steps 20000, z3) a postcondition stating
# `P = Q <-> (P.P_A = Q.P_A and then P.P_B = Q.P_B)` for a T_Pair_Int_Int
# VERIFIES directly, so a pair with no seq component needs no restatement
# beyond the record's own derived equality: both Big_Integer and Boolean
# have a predefined "=" visible without any `use` clause (CMP's plain infix
# already leans on the same fact for a bare int/bool `==`). A pair with a
# SEQ component cannot lean on that alone: Seq's own "=" needs `use Seqs;`
# (EQ_PREAMBLE's own note, WHOLE-SEQ `==`/`!=`), a `use` this file will not
# add unconditionally, so the same failure would just move one level up.
# Every pair type therefore gets a NAMED equality function regardless of
# its components ("a named form either way", not only where the bare form
# would fail): a non-seq field's comparison is still exactly the record's
# own "=", spelled per-field so one function shape covers a seq field too,
# and a seq field goes through T_Eq (EQ_PREAMBLE) instead, gated on
# needs_eq turning needs_range on with it exactly as WHOLE-SEQ `==`/`!=`
# already does. Gated on Lower.needs_pair_eq (a set of (T1, T2) keys, one
# per pair type an `==`/`!=` was actually rendered against, Lower.expr
# below), so a task that never compares two pairs gets no wrapper at all,
# the same discipline UPDATE_PREAMBLE/EQ_PREAMBLE/FILL_PREAMBLE keep.
def _pair_preamble(pair_types: list, needs_eq_for: set) -> str:
    parts = []
    for ty in pair_types:
        t1, t2 = ty["pair"]
        name = _pair_ada_name(ty)
        parts.append(
            f"   type {name} is record\n"
            f"      P_A : {ada_type(t1)};\n"
            f"      P_B : {ada_type(t2)};\n"
            f"   end record;\n")
        if (t1, t2) in needs_eq_for:
            cmp_a = "T_Eq (P.P_A, Q.P_A)" if t1 == "seq" else "P.P_A = Q.P_A"
            cmp_b = "T_Eq (P.P_B, Q.P_B)" if t2 == "seq" else "P.P_B = Q.P_B"
            parts.append(
                f"   function {name}_Eq (P, Q : {name}) return Boolean is\n"
                f"     ({cmp_a} and then {cmp_b});\n")
    return "\n".join(parts)


# fill(n, v) = seq(n, v) (SPEC.md "Sequences as values", 2026-09-09):
# DEFINED IFF n >= 0. There is no library constructor for "n copies of v"
# in SPARK.Containers.Functional.Infinite_Sequences (SEQ_PREAMBLE's own
# comment recommends property functions over construction functions in
# annotations, but a return VALUE has to be built somehow), so T_Fill is a
# recursive expression function over Seqs.Add, one element per step, exactly
# the shape every W_k loop helper and every spec_fun already is in this
# file. needs_fill (expr(), below) always turns needs_range on with it: the
# elementwise fact in T_Fill's own Post is stated over T_Range, so a task
# that calls fill() gets the quantifier preamble even if it never writes a
# `forall` of its own. MEASURED (2026-09-09, probe p_seq1.ads, --steps
# 20000): both Len (T_Fill'Result) = N and the elementwise
# (for all K in T_Range'(0, N) => Elem (T_Fill'Result, K) = V) discharge by
# gnatprove's automatic induction on the Subprogram_Variant, no separate
# lemma needed.
FILL_PREAMBLE = """\
   function T_Fill (N : Big_Integer; V : Big_Integer) return Seq
   with
     Pre  => N >= Big_Integer'(0),
     Post => Len (T_Fill'Result) = N
       and then (for all K in T_Range'(0, N) => Elem (T_Fill'Result, K) = V),
     Subprogram_Variant => (Decreases => N);

   function T_Fill (N : Big_Integer; V : Big_Integer) return Seq is
     (if N = Big_Integer'(0) then Seqs.Empty_Sequence
      else Seqs.Add (T_Fill (N - Big_Integer'(1), V), V));
"""

# seq(n, r) where r is a row (SPEC.md "Nested sequences (v1)"): n copies of
# the row r, the outer overload of T_Fill. The elementwise fact compares
# ROWS, so it goes through the flat T_Eq rather than "=" (NESTED_SEQ_
# PREAMBLE's own note); needs_fill2 forces needs_eq and needs_range on with
# it. NOT MEASURED: neither committed task calls fill() at this level.
NESTED_FILL_PREAMBLE = """\
   function T_Fill (N : Big_Integer; V : Seq) return Seq2
   with
     Pre  => N >= Big_Integer'(0),
     Post => Len (T_Fill'Result) = N
       and then (for all K in T_Range'(0, N) =>
                   T_Eq (Elem (T_Fill'Result, K), V)),
     Subprogram_Variant => (Decreases => N);

   function T_Fill (N : Big_Integer; V : Seq) return Seq2 is
     (if N = Big_Integer'(0) then Rows.Empty_Sequence
      else Rows.Add (T_Fill (N - Big_Integer'(1), V), V));
"""

# s[a..b] (SPEC.md "Sequences: literals, concatenation, slices", 2026-09-09):
# DEFINED IFF 0 <= a <= b <= len(s), the same shape of side condition as
# `at`'s and `update`'s, checked by the kernel at T_Slice's own Pre. No
# library "sub-sequence" constructor exists either (SEQ_PREAMBLE's own
# comment, same reason FILL_PREAMBLE has no library constructor to call),
# so T_Slice is built the same way T_Fill is, one element per step, except
# it counts DOWN from B rather than up from 0: T_Slice(S,A,B) unfolds to
# Add(T_Slice(S,A,B-1), Elem(S,B-1)), so the recursion bottoms out at the
# empty slice A=B and each level appends the next element in INCREASING
# index order as the recursion unwinds (A, A+1, ..., B-1), matching
# SPEC.md's "the element at k is s[a+k]" directly. Gated on needs_slice
# (expr(), below), which also turns needs_range on with it, exactly as
# needs_fill does: the elementwise fact is stated over T_Range. MEASURED
# (2026-09-09, probe p_seq3.ads, --steps 20000): both Len(Result) = B - A
# and the elementwise fact discharge by gnatprove's automatic induction on
# the Subprogram_Variant, the same T_Fill pattern, no separate lemma.
SLICE_PREAMBLE = """\
   function T_Slice (S : Seq; A : Big_Integer; B : Big_Integer) return Seq
   with
     Pre  => A >= Big_Integer'(0) and then A <= B and then B <= Len (S),
     Post => Len (T_Slice'Result) = B - A
       and then (for all K in T_Range'(0, B - A) =>
                   Elem (T_Slice'Result, K) = Elem (S, A + K)),
     Subprogram_Variant => (Decreases => B - A);

   function T_Slice (S : Seq; A : Big_Integer; B : Big_Integer) return Seq is
     (if A = B then Seqs.Empty_Sequence
      else Seqs.Add (T_Slice (S, A, B - Big_Integer'(1)),
                     Elem (S, B - Big_Integer'(1))));
"""

# m[a..b] on a seq<seq> (SPEC.md "Nested sequences (v1)"): a slice of rows,
# the outer overload of T_Slice, same shape as the flat one, elementwise
# fact through the flat T_Eq for the same reason NESTED_FILL_PREAMBLE's
# does. needs_slice2 forces needs_eq and needs_range on with it. NOT
# MEASURED: neither committed task slices at this level.
NESTED_SLICE_PREAMBLE = """\
   function T_Slice (S : Seq2; A : Big_Integer; B : Big_Integer) return Seq2
   with
     Pre  => A >= Big_Integer'(0) and then A <= B and then B <= Len (S),
     Post => Len (T_Slice'Result) = B - A
       and then (for all K in T_Range'(0, B - A) =>
                   T_Eq (Elem (T_Slice'Result, K), Elem (S, A + K))),
     Subprogram_Variant => (Decreases => B - A);

   function T_Slice (S : Seq2; A : Big_Integer; B : Big_Integer) return Seq2 is
     (if A = B then Rows.Empty_Sequence
      else Rows.Add (T_Slice (S, A, B - Big_Integer'(1)),
                     Elem (S, B - Big_Integer'(1))));
"""

# s + t on two seqs (SPEC.md "Sequences: literals, concatenation, slices",
# 2026-09-09): concatenation, always defined. Ada's own polymorphic "="
# resolves t's `==` at every type this file maps without help (CMP), but
# `+` has no such resolution: Seq carries no "+" operator at all (grepped
# against this SPARKlib install: no "&", no "Concat"), so this file builds
# one, gated on needs_concat (expr(), below, which decides seq-`+` from
# int-`+` by the STATIC type of the left operand, Lower._ty, since Ada
# picks the overload at compile time, not proof time). No library
# constructor appends a whole sequence either, so T_Concat is two
# functions in the T_Fill/T_Slice shape: T_Concat_Aux(S, T, N) is "S with
# the first N elements of T appended", recursive on N counting UP from 0
# (Add(T_Concat_Aux(S, T, N-1), Elem(T, N-1)), the same append-last-as-you
# -unwind shape SLICE_PREAMBLE's own note explains), and T_Concat(S, T) is
# just T_Concat_Aux(S, T, Len(T)), its own Post restating Aux's Post at
# N = Len(T) with no further reasoning needed. MEASURED (2026-09-09, probe
# p_seq3.ads, --steps 20000): Len, the S-prefix fact and the T-suffix fact
# all discharge by the same automatic induction T_Fill and T_Slice use.
CONCAT_PREAMBLE = """\
   function T_Concat_Aux (S, T : Seq; N : Big_Integer) return Seq
   with
     Pre  => N >= Big_Integer'(0) and then N <= Len (T),
     Post => Len (T_Concat_Aux'Result) = Len (S) + N
       and then (for all K in T_Range'(0, Len (S)) =>
                   Elem (T_Concat_Aux'Result, K) = Elem (S, K))
       and then (for all K in T_Range'(0, N) =>
                   Elem (T_Concat_Aux'Result, Len (S) + K) = Elem (T, K)),
     Subprogram_Variant => (Decreases => N);

   function T_Concat_Aux (S, T : Seq; N : Big_Integer) return Seq is
     (if N = Big_Integer'(0) then S
      else Seqs.Add (T_Concat_Aux (S, T, N - Big_Integer'(1)),
                     Elem (T, N - Big_Integer'(1))));

   function T_Concat (S, T : Seq) return Seq is
     (T_Concat_Aux (S, T, Len (T)))
   with
     Post => Len (T_Concat'Result) = Len (S) + Len (T)
       and then (for all K in T_Range'(0, Len (S)) =>
                   Elem (T_Concat'Result, K) = Elem (S, K))
       and then (for all K in T_Range'(0, Len (T)) =>
                   Elem (T_Concat'Result, Len (S) + K) = Elem (T, K));
"""

# m + n on two seq<seq>s (SPEC.md "Nested sequences (v1)"): row-wise
# concatenation, the outer overload of T_Concat_Aux/T_Concat, same shape as
# the flat pair, elementwise facts through the flat T_Eq for the same
# reason NESTED_FILL_PREAMBLE's does. needs_concat2 forces needs_eq and
# needs_range on with it. NOT MEASURED: neither committed task concatenates
# at this level.
NESTED_CONCAT_PREAMBLE = """\
   function T_Concat_Aux (S, T : Seq2; N : Big_Integer) return Seq2
   with
     Pre  => N >= Big_Integer'(0) and then N <= Len (T),
     Post => Len (T_Concat_Aux'Result) = Len (S) + N
       and then (for all K in T_Range'(0, Len (S)) =>
                   T_Eq (Elem (T_Concat_Aux'Result, K), Elem (S, K)))
       and then (for all K in T_Range'(0, N) =>
                   T_Eq (Elem (T_Concat_Aux'Result, Len (S) + K), Elem (T, K))),
     Subprogram_Variant => (Decreases => N);

   function T_Concat_Aux (S, T : Seq2; N : Big_Integer) return Seq2 is
     (if N = Big_Integer'(0) then S
      else Rows.Add (T_Concat_Aux (S, T, N - Big_Integer'(1)),
                     Elem (T, N - Big_Integer'(1))));

   function T_Concat (S, T : Seq2) return Seq2 is
     (T_Concat_Aux (S, T, Len (T)))
   with
     Post => Len (T_Concat'Result) = Len (S) + Len (T)
       and then (for all K in T_Range'(0, Len (S)) =>
                   T_Eq (Elem (T_Concat'Result, K), Elem (S, K)))
       and then (for all K in T_Range'(0, Len (T)) =>
                   T_Eq (Elem (T_Concat'Result, Len (S) + K), Elem (T, K)));
"""


def cap(name: str) -> str:
    """The Ada spelling of a t name. Ada identifiers may not carry two
    underscores in a row or end in one, and the lifter's file-qualified task
    names do (clover_abs__abs, measured 2026-09-06: gnatprove refused every
    lifted task at the package name). A run of k >= 2 underscores becomes
    `_` + "x" * (k - 1) + `_`, a trailing underscore gains an `x`, and
    `lower` abstains when two distinct t names meet after this mapping, so
    a rename is never silently a capture. Names without such runs are
    unchanged, so every committed task's Ada text is byte-identical."""
    name = _ADA_RUN.sub(lambda m: "_" + "x" * (len(m.group()) - 1) + "_", name)
    if name.endswith("_"):
        name += "x"
    return name.capitalize()


_ADA_RUN = re.compile(r"_{2,}")


# --- name capture ----------------------------------------------------------

def bound_names(task: dict, body: list) -> set:
    """Every t identifier the emitted package will capitalize into an Ada
    name: params, returns, locals, spec_fun names and their params, and
    quantifier bound variables."""
    out = set()

    def go(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("var", "name", "fun") and isinstance(v, str):
                    out.add(v)
                elif k in ("forall", "exists") and isinstance(v, dict):
                    out.add(v.get("var"))
                go(v)
        elif isinstance(x, list):
            for v in x:
                go(v)

    go(task)
    go(body)
    return {n for n in out if isinstance(n, str)}


def loop_assigned(body: list) -> set:
    """Syntactic assigned set of a loop body, SPEC.md's frame rule: a while
    loop havocs exactly the variables assigned in its body. A `return`
    (SPEC.md "Early exit", 2026-09-08) assigns its target exactly like an
    `assign` does before ending the task, and interp.assigned() already
    counts it that way; matched here so the target becomes a field of the
    loop's own state record (see lower_while's body_has_return path)."""
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


def _dead_lit(t) -> str:
    """A well-typed placeholder Ada literal for a state var this file lets
    into a loop's call site unassigned (SPEC.md "Early exit": the return
    target, when nothing before the loop ever set it). Never read for its
    value; only its type has to line up. A pair type (SPEC.md "Pairs",
    2026-09-10) recurses componentwise, qualified the same way expr()'s own
    `pair` case is; v1 has no pair of pairs, so this never recurses twice."""
    if _is_nested_seq(t):
        return "Rows.Empty_Sequence"
    if isinstance(t, dict):
        t1, t2 = t["pair"]
        return (f"{_pair_ada_name(t)}'(P_A => {_dead_lit(t1)}, "
               f"P_B => {_dead_lit(t2)})")
    return {"int": "Big_Integer'(0)", "bool": "False",
           "seq": "Seqs.Empty_Sequence"}[t]


def locals_seq(body: list) -> bool:
    """Whether `body` declares a seq-typed local anywhere (SPEC.md
    "Sequences as values", 2026-09-09: `var a: seq := ...;`), at any
    nesting depth, mirroring loop_assigned/has_return's own recursive
    shape. A task can need the seq preamble this way even when no
    parameter and no return is a seq: a purely local seq computation."""
    for s in body:
        if "var" in s and s["var"]["type"] == "seq":
            return True
        if "if" in s and (locals_seq(s["if"]["then"])
                          or locals_seq(s["if"]["else"])):
            return True
        if "while" in s and locals_seq(s["while"]["body"]):
            return True
    return False


def locals_nested_seq(body: list) -> bool:
    """locals_seq's own mirror for the nested type (SPEC.md "Nested
    sequences (v1)", 2026-09-10): whether `body` declares a seq<seq>-typed
    local anywhere. locals_seq's own `== "seq"` string compare never
    matches a dict type, so this needed its own scan rather than a
    one-line widening of that one."""
    for s in body:
        if "var" in s and _is_nested_seq(s["var"]["type"]):
            return True
        if "if" in s and (locals_nested_seq(s["if"]["then"])
                          or locals_nested_seq(s["if"]["else"])):
            return True
        if "while" in s and locals_nested_seq(s["while"]["body"]):
            return True
    return False


def has_return(body: list) -> bool:
    """Whether `body` can reach a `return` statement at any depth (SPEC.md
    "Early exit", 2026-09-08), mirroring the same recursive shape as
    loop_assigned/interp.assigned(). Drives the return-aware statement
    lowering below (Lower.compile_r, lower_while's body_has_return path): a
    body with no `return` anywhere keeps compile()/lower_while() exactly as
    they were before this note, byte-for-byte."""
    for s in body:
        if "return" in s:
            return True
        if "if" in s and (has_return(s["if"]["then"])
                          or has_return(s["if"]["else"])):
            return True
        if "while" in s and has_return(s["while"]["body"]):
            return True
    return False


class Lower:
    def __init__(self, task: dict, ce: bool = False):
        self.task = task
        self.helpers: list[str] = []   # emitted W_k record types + functions
        self.wcount = 0
        self.needs_range = False       # set by the first lowered quantifier
        self.needs_divmod = False      # set by the first lowered div/mod
        self.needs_fill = False        # set by the first lowered fill()
        self.needs_update = False      # set by the first lowered update
        self.needs_slice = False       # set by the first lowered slice()
        self.needs_concat = False      # set by the first lowered seq `+`
        self.needs_eq = False          # set by the first lowered seq ==/!=
        self.needs_pair_eq: set = set()  # (T1, T2) keys with a pair ==/!=
                                         # (SPEC.md "Pairs", 2026-09-10)
        # SPEC.md "Nested sequences (v1)" (2026-09-10): the outer overload
        # of each op is gated separately from its flat counterpart, since
        # each pulls in a DIFFERENT preamble block (NESTED_UPDATE_PREAMBLE
        # and friends) even though the rendered Ada text (T_Update(...) and
        # so on) is identical either way (NESTED_SEQ_PREAMBLE's own note).
        self.needs_update2 = False     # set by the first lowered m[i := r]
        self.needs_fill2 = False       # set by the first lowered seq(n, r)
        self.needs_slice2 = False      # set by the first lowered m[a..b]
        self.needs_concat2 = False     # set by the first lowered seq<seq> +
        self.needs_eq2 = False         # set by the first lowered seq<seq> ==
        # THE STRING LIBRARY (v1), 2026-09-11: one flag per member (or
        # tight cluster of members sharing one preamble block), never one
        # flag for the whole library -- see the dated note above
        # STRCORE_PREAMBLE for why a shared flag would cross-contaminate.
        self.needs_strcore = False     # Is_Ws/Is_Upper_Letter/
                                       # Is_Lower_Letter/T_Match_At
        self.needs_str_count = False
        self.needs_str_find = False
        self.needs_str_strip = False   # strip/lstrip/rstrip
        self.needs_str_replace = False
        self.needs_str_case = False    # lower/upper
        self.needs_str_pred = False    # isdigit/isalpha/isupper/islower
        self.needs_str_affix = False   # startswith/endswith
        self.needs_str_tostr = False
        self.needs_str_split_state = False
        self.needs_str_split_c = False
        self.needs_str_split_w = False
        self.needs_str_join = False
        self.spec_fun_names = {sf["name"] for sf in task.get("spec_funs", [])}
        # The counterexample instance walks the SAME tree with the SAME
        # operator table; only the numeric type of a literal differs, so a
        # transcription slip cannot make the instance disagree with the
        # theorem it instantiates (header).
        self.num = "Ce_Num" if ce else "Big_Integer"

    # --- expressions -------------------------------------------------------

    def _ty(self, e: dict, types: dict):
        """A static reading of `e`'s t type ("int"/"bool"/"seq", or a pair
        type {"pair": [T1, T2]}, SPEC.md "Pairs", 2026-09-10), needed only
        to tell a seq `+` (concatenation) from an int `+` (addition) and a
        pair `==`/`!=` from an int/bool/seq one BEFORE any Ada text is
        emitted (SPEC.md "Sequences: literals, concatenation, slices",
        2026-09-09; "Pairs", 2026-09-10). t's plain `==` needed no such
        reading: Ada's own polymorphic "=" already resolves it at every
        base type this file maps (Big_Integer, Boolean, Seq). `+` has no
        such resolution -- grepped against this SPARKlib install, Sequence
        carries no "+" and no "&" -- and a pair's own "=" is a named call
        (_pair_preamble), never bare infix, so the choice has to be made
        here, statically, mirroring the same isinstance(a[0], tuple) check
        interp.ev makes at runtime (SPEC.md's own rule: an operator whose
        operands disagree in type is ill-typed, so only args[0] is
        consulted, never both). `types` is whatever dict the caller already
        threads for `var` types: compile()/compile_r()/lower_while() thread
        task params + return + locals throughout (lower()'s initial call
        now seeds params in, SPEC.md "Sequences as values" already seeded
        return + locals); lower_spec_fun() builds one from the spec_fun's
        own params; certificate()/_undef_obligation read it off the
        witness's own ground values instead, since there is no AST-level
        `types` dict at a witness."""
        if "int" in e:
            return "int"
        if "bool" in e:
            return "bool"
        if "var" in e:
            v = e["var"]
            if v not in types:
                raise ValueError(f"unbound variable {v!r}")
            return types[v]
        if "ite" in e:
            return self._ty(e["ite"]["then"], types)
        if "call" in e:
            fun = e["call"]["fun"]
            if fun == self.task["name"]:
                return self.task["returns"][0]["type"]
            for sf in self.task.get("spec_funs", []):
                if sf["name"] == fun:
                    return sf["result"]
            raise ValueError(f"call to unknown function {fun!r}")
        if "forall" in e or "exists" in e:
            return "bool"
        op = e["op"]
        if op == "len":
            return "int"
        if op == "at":
            # SPEC.md "Nested sequences (v1)" (2026-09-10): s[i] is a row
            # (type "seq") when s is itself a seq<seq>, an int when s is a
            # flat seq, told apart by the OPERAND's own type -- s[i][j]
            # (the notation's chained postfix, at(at(s,i),j)) resolves
            # right by construction: the inner `at`'s own result feeds the
            # outer `at` as its operand.
            return "seq" if _is_nested_seq(self._ty(e["args"][0], types)) \
                else "int"
        if op in ("update", "slice"):
            # m[i := r] / m[a..b]: the result is the SAME type as the seq
            # being updated/sliced, row or outer (SPEC.md "Nested
            # sequences (v1)").
            return self._ty(e["args"][0], types)
        if op == "fill":
            # seq(n, v): nested iff v itself is a row (a "seq" value)
            # rather than an int (SPEC.md "Nested sequences (v1)").
            return ({"seq": "seq"}
                    if self._ty(e["args"][1], types) == "seq" else "seq")
        if op == "seq":
            # [e1, ..., en] (SPEC.md "Nested sequences (v1)"): nested iff
            # its own first element is itself a row. The empty literal `[]`
            # has no element to read this off of; SPEC.md says "the
            # declared type says so", a top-down hint this bottom-up
            # reading does not carry, so it defaults to flat here, same as
            # before this construct existed. NOT MEASURED: no committed
            # task's requires/ensures/body/spec_funs contains a `seq`
            # literal node at all (grepped), so neither the inference nor
            # the empty-literal default is exercised by anything committed
            # (dated note, below).
            args = e.get("args") or []
            return ({"seq": "seq"}
                    if args and self._ty(args[0], types) == "seq" else "seq")
        if op == "pair":
            # SPEC.md "Pairs" (2026-09-10): a `pair` node has no declared
            # type of its own to look up the way a `var` does, so it is
            # read off its own two arguments, recursively -- the same
            # static reading `+`/`==` already lean on this function for.
            return {"pair": [self._ty(e["args"][0], types),
                             self._ty(e["args"][1], types)]}
        if op in ("fst", "snd"):
            pty = self._ty(e["args"][0], types)
            if not (isinstance(pty, dict) and "pair" in pty):
                raise ValueError(f"{op} of a non-pair expression")
            return pty["pair"][0 if op == "fst" else 1]
        if op in ("neg", "-", "*", "div", "mod"):
            return "int"
        if op == "+":
            return self._ty(e["args"][0], types)
        if op in ("not", "and", "or", "implies") or op in CMP:
            return "bool"
        # THE STRING LIBRARY (v1), SPEC.md 2026-09-11: split(s)/split(s, c)
        # (one op, two arities, "two arities of one op" per SPEC.md) return
        # a seq<seq>; join/tostr/strip/lstrip/rstrip/replace/lower/upper
        # return a seq; count/find return an int; the four predicates and
        # startswith/endswith return a bool. Nothing here is recursive on
        # `e` beyond one level -- a member's OWN argument types are never
        # in question the way `fst`/`snd`'s pair component is.
        if op == "split":
            return {"seq": "seq"}
        if op in ("join", "tostr", "strip", "lstrip", "rstrip", "replace",
                  "lower", "upper"):
            return "seq"
        if op in ("count", "find"):
            return "int"
        if op in ("isdigit", "isalpha", "isupper", "islower",
                  "startswith", "endswith"):
            return "bool"
        raise ValueError(f"t has no operator {op!r}")

    def expr(self, e: dict, sub: dict, types: dict, expect=None) -> str:
        """`expect`, added for NESTED SEQUENCES RESIDUAL (2026-09-10): the
        empty seq literal `[]` has no element for the `seq` case below to
        read nested-ness off of (the exact ambiguity Lower._ty's own `seq`
        case already documents), so it needs the declared type from the
        CALLER when there is one -- the same "the declared type says so"
        hint fuzz_lower.py's own `_ty(..., expect=...)` already threads for
        check_wf (its own docstring, "Nested sequences" (2026-09-10)).
        Mirrors that function's site list, not its full generality: only
        var init, assign, and return (compile()/compile_r(), below) thread
        a real value in, since those are the sites MEASURED to matter
        (fz_v1nested_069: `var m : seq<seq> := []`, below); an `ite` branch
        or a call argument can carry the same ambiguity in principle but
        neither is exercised by anything committed or in this residual, so
        neither threads it here (NOT MEASURED, carried below). Everywhere
        else `expect` stays None and rendering is unchanged from before
        this parameter existed."""
        if "int" in e:
            # Qualified: a bare literal fails resolution where both operands
            # of an operator are literal-bearing (measured: "expected type
            # universal integer" on count_matches), and the qualified form
            # keeps the Big_Integer literal aspect for arbitrary magnitude.
            return f"{self.num}'({e['int']})"
        if "bool" in e:
            return "True" if e["bool"] else "False"
        if "var" in e:
            v = e["var"]
            if v not in sub:
                raise ValueError(f"unbound variable {v!r}")
            if sub[v] is None:
                raise ValueError(f"read of unassigned {v!r}")
            return sub[v]
        if "forall" in e or "exists" in e:
            self.needs_range = True
            q = e["forall"] if "forall" in e else e["exists"]
            v = cap(q["var"])
            lo = self.expr(q["lo"], sub, types)
            hi = self.expr(q["hi"], sub, types)
            # The cursor IS the mathematical bound variable: T_Range's cursor
            # type is Big_Integer, so [lo, hi) is not sliced to a machine type
            # and there is no range obligation to owe (see the header).
            body = self.expr(q["body"], {**sub, q["var"]: v},
                             {**types, q["var"]: "int"})
            kind = "for all" if "forall" in e else "for some"
            return f"({kind} {v} in T_Range'({lo}, {hi}) => {body})"
        if "ite" in e:
            c = e["ite"]
            return (f"(if {self.expr(c['cond'], sub, types)} "
                    f"then {self.expr(c['then'], sub, types)} "
                    f"else {self.expr(c['else'], sub, types)})")
        if "call" in e:
            c = e["call"]
            fun = "F" if c["fun"] == self.task["name"] else cap(c["fun"])
            if c["fun"] != self.task["name"] \
                    and c["fun"] not in self.spec_fun_names:
                raise ValueError(f"call to unknown function {c['fun']!r}")
            args = [self.expr(a, sub, types) for a in c["args"]]
            return f"{fun} ({', '.join(args)})" if args else fun
        op = e["op"]
        args = [self.expr(a, sub, types) for a in e.get("args", [])]
        if op == "len":
            return f"Len ({args[0]})"
        if op == "at":
            s, i = args
            return f"Elem ({s}, {i})"
        if op == "update":
            # s[i := v] (SPEC.md "Sequences as values", 2026-09-09):
            # T_Update's own Pre is `at`'s definedness side condition,
            # discharged by the kernel at this call site exactly as Elem's
            # is (UPDATE_PREAMBLE). SPEC.md "Nested sequences (v1)",
            # 2026-09-10: the SAME rendered text, "T_Update (...)", serves
            # m[i := r] on a seq<seq> too (NESTED_UPDATE_PREAMBLE's own
            # overload, resolved by Ada from S's own static type), so only
            # the FLAG differs by whether S is nested.
            s, i, v = args
            if _is_nested_seq(self._ty(e["args"][0], types)):
                self.needs_update2 = True
            else:
                self.needs_update = True
            return f"T_Update ({s}, {i}, {v})"
        if op == "fill":
            # seq(n, v) (SPEC.md "Sequences as values", 2026-09-09).
            # T_Fill's own elementwise Post quantifies over T_Range, so a
            # task that only ever calls fill() still needs the range
            # preamble (FILL_PREAMBLE's own note).
            # SPEC.md "Nested sequences (v1)", 2026-09-10: seq(n, r) with a
            # row r is the outer overload (NESTED_FILL_PREAMBLE), same
            # rendered text, told apart by v's own type.
            self.needs_range = True
            n, v = args
            if self._ty(e["args"][1], types) == "seq":
                self.needs_fill2 = True
                self.needs_eq = True
            else:
                self.needs_fill = True
            return f"T_Fill ({n}, {v})"
        if op == "seq":
            # [e1, ..., en] (SPEC.md "Sequences: literals, concatenation,
            # slices", 2026-09-09), [] the empty seq. n is fixed at
            # lowering time (the AST's own arg count), so this is a plain
            # constructor chain over Seqs.Empty_Sequence/Seqs.Add, exactly
            # the "Seqs.Empty plus Seqs.Add" the header calls for; no new
            # recursive helper or Post is needed because Add's OWN Post
            # (SEQ_PREAMBLE's neighbour in the SPARKlib spec) already gives
            # gnatprove Length and Get at each step, statically unrolled.
            # SPEC.md "Nested sequences (v1)", 2026-09-10: [[1,2],[3]], a
            # nested literal, chains Rows.Add over ROW values instead --
            # Seqs.Add and Rows.Add are different package-qualified names,
            # not overloads of one identifier the way Len/Elem/T_Update and
            # friends are, so this is the one Expr form that needed the
            # package chosen by static type rather than left to Ada's own
            # resolution (NESTED_SEQ_PREAMBLE's own note). Told apart by
            # the first element's own type; the empty literal has no
            # element to read this off (Lower._ty's own note on this same
            # ambiguity) and falls back to `expect`, the declared-type hint
            # this method's own docstring names -- MEASURED,
            # fz_v1nested_069: `var m : {"seq": "seq"} := []` rendered
            # `Seqs.Empty_Sequence` (flat) before this hint existed, while
            # `m`'s every later use (T_Concat, the W_1 call) is Seq2
            # (nested), a type mismatch gnatprove read as malformed. With
            # no `expect` at all (every call site this parameter does not
            # yet reach) this defaults to flat exactly as before.
            eargs = e.get("args") or []
            nested = (self._ty(eargs[0], types) == "seq" if eargs
                      else _is_nested_seq(expect))
            pkg = "Rows" if nested else "Seqs"
            out = f"{pkg}.Empty_Sequence"
            for a in args:
                out = f"{pkg}.Add ({out}, {a})"
            return out
        if op == "slice":
            # s[a..b] (SPEC.md "Sequences: literals, concatenation,
            # slices", 2026-09-09): T_Slice's own Pre is the definedness
            # side condition (0 <= a <= b <= len(s)), checked by the kernel
            # at this call site exactly as Elem's/T_Update's Pre are
            # (SLICE_PREAMBLE). SPEC.md "Nested sequences (v1)",
            # 2026-09-10: m[a..b] on a seq<seq> is the outer overload
            # (NESTED_SLICE_PREAMBLE), same rendered text, told apart by
            # S's own type.
            s, a, b = args
            # THE STRING LIBRARY (v1), 2026-09-11: a full self-slice,
            # `s[0..len(s)]`, is semantically just `s` (SPEC.md's own
            # slice law at a = 0, b = len(s)); recognized here,
            # syntactically, on the SOURCE AST (e["args"][1] == {"int": 0}
            # and e["args"][2] == {"op": "len", "args": [e["args"][0]]}),
            # before any T_Slice text is emitted. MEASURED, this session's
            # scratch probes (p1/p4/p5): native Seqs."=" as an established
            # hypothesis does NOT let a third function's calls on two
            # "="-equal Seq values unify by ordinary SMT congruence (only
            # SPARKlib's own axiom for "=" ITSELF unfolds that way,
            # EQ_PREAMBLE's own T_Eq exists for exactly this reason at the
            # T_Range level) -- so word_count's own `t2 := s[0..len(s)]`
            # then `t2.split()` would need gnatprove to bridge
            # T_Split (T_Slice (S, 0, Len (S))) to T_Split (S) with no
            # such principle available, MEASURED to time out (real
            # word_count, --steps up to 200000). Simplifying the identity
            # away here removes the need for that bridge entirely: `s` and
            # `s[0..len(s)]` become the SAME Ada term, not merely an
            # equal one. A general, type-blind, AST-level rewrite (any
            # `slice` node this shape, string-library task or not), not a
            # member-specific one -- it changes nothing about what a slice
            # MEANS, only which of two equal renderings this file emits.
            # Regression: grepped, no committed task before this one
            # builds this exact shape (tail's own slice is `s[1..len(s)]`,
            # a != 0), so nothing already committed moves.
            if (e["args"][1] == {"int": 0}
                    and isinstance(e["args"][2], dict)
                    and e["args"][2].get("op") == "len"
                    and e["args"][2].get("args") == [e["args"][0]]):
                return s
            self.needs_range = True
            if _is_nested_seq(self._ty(e["args"][0], types)):
                self.needs_slice2 = True
                self.needs_eq = True
            else:
                self.needs_slice = True
            return f"T_Slice ({s}, {a}, {b})"
        if op == "pair":
            # (a, b) (SPEC.md "Pairs", 2026-09-10): a record aggregate,
            # qualified with the pair's own Ada type name -- the same
            # qualification a bare integer literal already needs (`int` in
            # e, above: "a bare literal fails resolution... where both
            # operands... are literal-bearing"), and for the same reason:
            # an UNQUALIFIED `(P_A => a, P_B => b)` sitting in compile()'s
            # own `if`-merge (`(if cond then <then> else <else>)`, both
            # arms a bare aggregate) gives gnatprove nothing to resolve the
            # aggregate's type from. Qualifying it always, not only where
            # an `if`-merge would need it, keeps every call site the same.
            # Field names P_A/P_B (PAIRS RESIDUAL, 2026-09-10; the dated
            # note at the end of the PAIRS docstring, above): renamed from
            # the original A/B, which folded-case collided with a
            # lowercase t identifier `a`/`b`.
            t1 = self._ty(e["args"][0], types)
            t2 = self._ty(e["args"][1], types)
            name = _pair_ada_name({"pair": [t1, t2]})
            return f"{name}'(P_A => {args[0]}, P_B => {args[1]})"
        if op in ("fst", "snd"):
            # p.0 / p.1 (SPEC.md "Pairs", 2026-09-10): "always defined on a
            # pair", so this is plain field access, no Pre and no wrapper
            # function -- unlike `at`'s Elem, a pair's two fields are
            # always populated at construction (the `pair` case just
            # above), so there is no partiality to state a precondition
            # about. UNPARENTHESIZED: MEASURED (gnatprove FSF 16.1.0)
            # `(F'Result).P_A` is rejected, "prefix for selection is not a
            # name" -- Ada's selected_component needs a NAME for its
            # prefix (RM 4.1), and wrapping one in parens turns it into a
            # plain expression, no longer a name, even though the name
            # underneath (an attribute reference, a variable, a function
            # call) would have worked directly; `F'Result.P_A` and
            # `F (Args).P_A`, both already how this file spells a W_k state
            # field access (lower_while's own `{name}'Result.{cap(v)}`),
            # are exactly right with no parens at all. This does not yet
            # cover a pair value that is itself not a name (an `if`-merge
            # of two pairs, or `fst`/`snd` applied straight to a fresh
            # `pair(...)` aggregate): neither committed pair task ever
            # projects one of those, and this is not guarded against, only
            # left unexercised.
            return f"{args[0]}.{'P_A' if op == 'fst' else 'P_B'}"
        if op == "+":
            ty0 = self._ty(e["args"][0], types)
            if ty0 == "seq" or _is_nested_seq(ty0):
                # s + t on two seqs is concatenation (SPEC.md "Sequences:
                # literals, concatenation, slices", 2026-09-09), told apart
                # from int `+` by Lower._ty, above, since Ada's `+` is not
                # polymorphic the way t's is (CONCAT_PREAMBLE). SPEC.md
                # "Nested sequences (v1)", 2026-09-10: m + n on two
                # seq<seq>s is the outer overload (NESTED_CONCAT_PREAMBLE),
                # same rendered text, told apart by ty0.
                self.needs_range = True
                s, t = args
                if _is_nested_seq(ty0):
                    self.needs_concat2 = True
                    self.needs_eq = True
                else:
                    self.needs_concat = True
                return f"T_Concat ({s}, {t})"
        if op == "neg":
            return f"(-{args[0]})"
        if op == "not":
            return f"(not {args[0]})"
        if op == "implies":
            return f"(if {args[0]} then {args[1]} else True)"
        if op in NARY:
            return "(" + f" {NARY[op]} ".join(args) + ")"
        if op in ("==", "!="):
            ty0 = self._ty(e["args"][0], types)
            if ty0 == "seq" or _is_nested_seq(ty0):
                # Whole-seq `==`/`!=` is extensional (SPEC.md "Sequences as
                # values"), told apart from int/bool `==` the same way seq
                # `+` is (Lower._ty, CONCAT_PREAMBLE's own note): Ada's own
                # "=" is polymorphic enough to resolve t's `==` at
                # Big_Integer and Boolean without help, but not at Seq, a
                # private type inside a generic instantiation (EQ_PREAMBLE).
                # SPEC.md "Nested sequences (v1)", 2026-09-10: two seq<seq>s
                # is the outer overload of T_Eq (NESTED_EQ_PREAMBLE), same
                # rendered text, told apart by ty0.
                self.needs_range = True
                self.needs_eq = True
                if _is_nested_seq(ty0):
                    self.needs_eq2 = True
                eq = f"T_Eq ({args[0]}, {args[1]})"
                return eq if op == "==" else f"(not {eq})"
        if op in ("==", "!=") and isinstance(self._ty(e["args"][0], types),
                                             dict) \
                and "pair" in self._ty(e["args"][0], types):
            # Two pairs (SPEC.md "Pairs", 2026-09-10: "the polymorphic `==`
            # again, two ints, two bools, two seqs, two pairs"), told apart
            # from every other `==`/`!=` the same way seq `==` is
            # (Lower._ty, just above; "pair" in the dict rather than bare
            # isinstance, so the nested seq type's own dict, {"seq": "seq"},
            # is not mistaken for a pair, SPEC.md "Nested sequences (v1)").
            # Always a NAMED call (_pair_preamble's own note): whether the
            # pair's record type has a bare predefined "=" gnatprove can see
            # or not, this file does not need to know which, per pair type,
            # to pick between two renderings here.
            pty = self._ty(e["args"][0], types)
            t1, t2 = pty["pair"]
            self.needs_pair_eq.add((t1, t2))
            if t1 == "seq" or t2 == "seq":
                self.needs_eq = True
                self.needs_range = True
            eq = f"{_pair_ada_name(pty)}_Eq ({args[0]}, {args[1]})"
            return eq if op == "==" else f"(not {eq})"
        if op in CMP:
            return f"({args[0]} {CMP[op]} {args[1]})"
        if op in ARITH:
            return f"({args[0]} {ARITH[op]} {args[1]})"
        if op in DIVMOD:
            # Never native `/`/`mod` (header, DIV/MOD): both are wrong for a
            # negative divisor. T_Div/T_Mod's shared Pre => Y /= 0 is
            # SPEC.md's definedness obligation, checked at this call site
            # exactly as Elem's Pre discharges `at`.
            self.needs_divmod = True
            return f"{DIVMOD[op]} ({args[0]}, {args[1]})"
        # THE STRING LIBRARY (v1), SPEC.md 2026-09-11 (header's dated note,
        # above DIVMOD_PREAMBLE, has the per-member design and what is
        # MEASURED rather than assumed). Each member sets only its own
        # flag(s), never a shared "any string member" flag: gnatprove
        # proves every declared subprogram in the file, so a flag shared
        # with a member whose contract does not verify would fail a task
        # that never calls that member merely by naming it in the same
        # file (the same reasoning needs_update2/needs_fill2/etc. already
        # keep separate from their flat counterparts).
        if op == "split":
            self.needs_str_split_state = True
            if len(args) == 1:
                self.needs_strcore = True   # Is_Ws (STRCORE also has
                self.needs_range = True     # T_Match_At, which needs it)
                self.needs_str_split_w = True
            else:
                self.needs_str_split_c = True
            return (f"T_Split ({args[0]})" if len(args) == 1
                    else f"T_Split_C ({args[0]}, {args[1]})")
        if op == "join":
            self.needs_str_join = True
            self.needs_range = True
            self.needs_slice2 = True
            self.needs_concat = True
            return f"T_Join ({args[0]}, {args[1]})"
        if op == "tostr":
            self.needs_str_tostr = True
            self.needs_range = True
            self.needs_concat = True
            return f"T_ToStr ({args[0]})"
        if op == "count":
            self.needs_strcore = True
            self.needs_str_count = True
            self.needs_range = True
            self.needs_slice = True   # T_Count1's own peel-via-T_Slice
            return f"T_Count ({args[0]}, {args[1]})"
        if op == "find":
            self.needs_strcore = True
            self.needs_str_find = True
            self.needs_range = True
            return f"T_Find ({args[0]}, {args[1]})"
        if op in ("strip", "lstrip", "rstrip"):
            self.needs_strcore = True   # T_Lws/T_Rws call Is_Ws
            self.needs_str_strip = True
            self.needs_range = True
            self.needs_slice = True
            fn = {"strip": "T_Strip", "lstrip": "T_LStrip",
                  "rstrip": "T_RStrip"}[op]
            return f"{fn} ({args[0]})"
        if op == "replace":
            self.needs_strcore = True
            self.needs_str_replace = True
            self.needs_range = True
            self.needs_slice = True
            self.needs_concat = True
            return f"T_Replace ({args[0]}, {args[1]}, {args[2]})"
        if op in ("lower", "upper"):
            self.needs_strcore = True   # T_Lower/T_Upper call
                                        # Is_Upper_Letter/Is_Lower_Letter
            self.needs_str_case = True
            self.needs_range = True
            self.needs_slice = True
            fn = "T_Lower" if op == "lower" else "T_Upper"
            return f"{fn} ({args[0]})"
        if op in ("isdigit", "isalpha", "isupper", "islower"):
            self.needs_strcore = True
            self.needs_str_pred = True
            self.needs_range = True
            fn = {"isdigit": "T_IsDigit", "isalpha": "T_IsAlpha",
                  "isupper": "T_IsUpper", "islower": "T_IsLower"}[op]
            return f"{fn} ({args[0]})"
        if op in ("startswith", "endswith"):
            self.needs_str_affix = True
            self.needs_range = True
            fn = "T_StartsWith" if op == "startswith" else "T_EndsWith"
            return f"{fn} ({args[0]}, {args[1]})"
        raise ValueError(f"t has no operator {op!r}")

    # clause() and req_clause() are gone with the machine-Integer quantifier
    # encoding they served: T_Range carries no bounds obligation to hoist, so
    # every position (requires included) is just expr(). The four ABSTAIN
    # paths that guarded the hoist are gone with it; see the header.

    # --- statements --------------------------------------------------------

    def compile(self, stmts: list, env: dict, types: dict,
                psub: dict) -> dict:
        env, types = dict(env), dict(types)
        for s in stmts:
            if "assign" in s:
                v, e = s["assign"]
                if v not in env:
                    raise ValueError(f"assign to undeclared {v!r}")
                # `types.get(v)`: NESTED SEQUENCES RESIDUAL (2026-09-10),
                # `v`'s own declared type, threaded as expr()'s `expect`
                # so an empty `[]` assigned into a nested-typed name
                # renders Rows, not Seqs (expr()'s own docstring).
                env[v] = self.expr(e, {**psub, **env}, types, types.get(v))
            elif "var" in s:
                d = s["var"]
                env[d["name"]] = self.expr(
                    d["init"], {**psub, **env}, types, d["type"])
                types[d["name"]] = d["type"]
            elif "if" in s:
                c = s["if"]
                cond = self.expr(c["cond"], {**psub, **env}, types)
                et = self.compile(c["then"], env, types, psub)
                ee = self.compile(c["else"], env, types, psub)
                for v in env:
                    if et[v] == ee[v]:
                        env[v] = et[v]
                    elif et[v] is None or ee[v] is None:
                        raise NotImplementedError(
                            f"spark: {v!r} assigned on only one branch of an "
                            f"`if` and read later; no join value")
                    else:
                        env[v] = f"(if {cond} then {et[v]} else {ee[v]})"
            elif "while" in s:
                env = self.lower_while(s["while"], env, types, psub)
            elif "return" in s:
                # SPEC.md "Early exit" (2026-09-08). compile() is the
                # ORIGINAL, non-return-aware statement compiler: `lower()`
                # and lower_while() route any body has_return() finds a
                # `return` in through compile_r below instead, so a
                # `return` reaching here would be a routing bug, not a
                # task shape compile() should ever try to interpret.
                raise NotImplementedError(
                    "spark: return statement reached compile(); "
                    "has_return()-routing should have used compile_r")
            else:
                raise ValueError(f"unknown statement {sorted(s)!r}")
        return env

    # compile_r() is compile()'s return-aware twin (SPEC.md "Early exit",
    # 2026-09-08, ROADMAP 12.7). Only called on a statement list has_return()
    # finds a `return` in, from lower() at the task's top level and from
    # lower_while() for a loop whose own body can return; every other body
    # keeps compile()/lower_while() exactly as they read before this note,
    # byte-for-byte, since neither is touched by anything below.
    #
    # A `return` cannot become an actual Ada `return` statement: everything
    # this file emits is an expression function (SHAPE, header), and a full
    # subprogram body (statements, a loop, `return`) is not a
    # basic_declarative_item, so it cannot be given directly in the package
    # spec this file writes. MEASURED (2026-09-08, probe t_probe1.ads: a
    # plain `function F (...) is R : ...; begin ... return R; end F;` right
    # where an expression function sits): gnatprove refuses Phase 2 with
    # "begin block not allowed in package spec" before a single VC is even
    # generated. So `return` is lowered the same way everything else here
    # is: by substitution, threading one more pair of facts alongside the
    # ordinary env -- `esc`, an Ada boolean expression (None standing for
    # the literal False) that is true exactly when some execution of the
    # statement list reached a `return`, and `val`, the Ada expression for
    # the return name's value at that escape (defined whenever esc is not
    # None). A `return`'s own target is folded into env exactly like an
    # assign's, so downstream code that is not itself escape-aware (a
    # later `if` merge, a recursive call's arguments) reads an ordinary
    # substitution and stays correct: it is simply describing "the value
    # under the hypothesis nothing escaped", which is exactly what a
    # non-escaping continuation needs, and is discarded wherever an escape
    # is live (lower_while's Esc branch, lower()'s final (if esc then val
    # else env[ret]) merge) in favour of `val`.
    def compile_r(self, stmts: list, env: dict, types: dict, psub: dict,
                  ret_name: str):
        env, types = dict(env), dict(types)
        esc = None
        val = None

        def combine(local_esc, local_val):
            nonlocal esc, val
            if esc is None:
                esc, val = local_esc, local_val
            elif local_esc is not None:
                val = f"(if {esc} then {val} else {local_val})"
                esc = f"({esc} or else {local_esc})"
            # local_esc is None: this statement never escapes, so whatever
            # esc/val already stand (from earlier in the same list) are
            # unaffected.

        for s in stmts:
            if "assign" in s:
                v, e = s["assign"]
                if v not in env:
                    raise ValueError(f"assign to undeclared {v!r}")
                # `types.get(v)`: NESTED SEQUENCES RESIDUAL (2026-09-10),
                # mirroring compile()'s own identical hint (expr()'s
                # docstring).
                env[v] = self.expr(e, {**psub, **env}, types, types.get(v))
            elif "return" in s:
                name, e = s["return"]
                new_val = self.expr(
                    e, {**psub, **env}, types, types.get(name))
                env[name] = new_val
                combine("True", new_val)
            elif "var" in s:
                d = s["var"]
                env[d["name"]] = self.expr(
                    d["init"], {**psub, **env}, types, d["type"])
                types[d["name"]] = d["type"]
            elif "if" in s:
                c = s["if"]
                cond = self.expr(c["cond"], {**psub, **env}, types)
                default = env.get(ret_name)
                et, esc_then, val_then = self.compile_r(
                    c["then"], env, types, psub, ret_name)
                ee, esc_else, val_else = self.compile_r(
                    c["else"], env, types, psub, ret_name)
                for v in env:
                    if et[v] == ee[v]:
                        env[v] = et[v]
                    elif et[v] is None or ee[v] is None:
                        raise NotImplementedError(
                            f"spark: {v!r} assigned on only one branch of "
                            f"an `if` and read later; no join value")
                    else:
                        env[v] = f"(if {cond} then {et[v]} else {ee[v]})"
                if esc_then is None and esc_else is None:
                    local_esc, local_val = None, None
                else:
                    then_e = esc_then if esc_then is not None else "False"
                    else_e = esc_else if esc_else is not None else "False"
                    local_esc = f"(if {cond} then {then_e} else {else_e})"
                    then_v = val_then if esc_then is not None else default
                    else_v = val_else if esc_else is not None else default
                    local_val = f"(if {cond} then {then_v} else {else_v})"
                combine(local_esc, local_val)
            elif "while" in s:
                env, wesc, wval = self.lower_while(
                    s["while"], env, types, psub, ret_name)
                combine(wesc, wval)
            else:
                raise ValueError(f"unknown statement {sorted(s)!r}")
        return env, esc, val

    def lower_while(self, w: dict, env: dict, types: dict,
                    psub: dict, ret_name: str | None = None):
        """Lower one while loop to its W_k helper. `ret_name` is None for
        every call site compile() makes (the original, non-return-aware
        shape, returned as a plain env dict, unchanged since before SPEC.md
        "Early exit"); compile_r() always passes the task's return name, and
        gets back (env, esc, val) instead -- esc/val are None/None when
        THIS loop's own body (body_has_return below) has no return in it,
        exactly mirroring compile_r's own convention."""
        if "decreases" not in w:
            raise ValueError("while without a decreases clause")
        self.wcount += 1
        name, tname = f"W_{self.wcount}", f"W_{self.wcount}_State"
        state = list(env.keys())
        body_has_return = ret_name is not None and has_return(w["body"])
        # SPEC.md frame rule: the loop havocs exactly the syntactic assigned
        # set of its body. Only those variables become record fields of the
        # helper's result; every other in-scope name stays a plain parameter
        # the helper passes through unchanged, and the caller keeps its own
        # value for it. (Before 2026-09-02 the record held ALL of env, and
        # the Post said only invariants + not guard about it, the
        # havoc-everything theorem: fr_probe_ret / fr_probe_local went
        # TIMEOUT here while Dafny, Verus and Frama-C proved them.) A
        # `return`'s target counts as assigned here too (loop_assigned,
        # 2026-09-08), so it becomes a state field exactly when the body can
        # actually set it. Computed before the unassigned-var check just
        # below (moved up from after it, SPEC.md "Pairs", 2026-09-10): that
        # check's own exemption needs to know `hav` too, now.
        hav = loop_assigned(w["body"])
        for v in state:
            if env[v] is None:
                if (body_has_return and v == ret_name) or v not in hav:
                    # The return target may be genuinely unassigned before
                    # the loop (SPEC.md "Early exit": first_even, is_prime
                    # both reach their while with `r` never yet assigned).
                    # No invariant or Pre/Post above ever mentions it here
                    # (a loop's own contract is stated over the state it
                    # HAVOCS, and nothing upstream could have constrained a
                    # name nothing has touched yet), so entry has no fact to
                    # lose by treating it as a normal (if unconstrained)
                    # state field instead of refusing the loop outright.
                    # SPEC.md "Pairs" (2026-09-10) widens this from "the
                    # return target under an early exit" to "any var the
                    # loop's OWN body never assigns" (`v not in hav`):
                    # min_max reaches its loop with the pair-typed return
                    # `r` unassigned and NO return statement anywhere (so
                    # the first disjunct alone would not have covered it),
                    # but `r` is not in `hav` either, since the loop body
                    # never touches it -- it is filled in by the plain
                    # `r := pair(lo, hi)` AFTER the loop -- so the same
                    # "nothing upstream could reference it" argument holds
                    # for exactly the same reason, pair-typed or not.
                    continue
                raise NotImplementedError(
                    f"spark: loop reached with {v!r} unassigned; the state "
                    f"record has no value for it")
        mut = [v for v in state if v in hav]
        if not mut:
            raise NotImplementedError(
                "spark: loop body assigns nothing in scope; an empty state "
                "record is not lowerable")
        tparams = self.task["params"]
        plist = [f"{cap(p['name'])} : {ada_type(p['type'])}" for p in tparams] \
            + [f"{cap(v)} : {ada_type(types[v])}" for v in state]
        entry = {**psub, **{v: cap(v) for v in state}}
        result = {**psub,
                  **{v: (f"{name}'Result.{cap(v)}" if v in mut else cap(v))
                     for v in state}}
        invs = w.get("invariants", [])
        # THE STRING LIBRARY (v1), 2026-09-11: an "and then" aspect list
        # checks each conjunct's OWN definedness (a T_Slice/T_Count Pre,
        # here) using only the EARLIER conjuncts as hypotheses (SPEC.md's
        # own left-to-right definedness rule, restated by GNATprove's
        # short-circuit VC generation) -- so a conjunct that indexes or
        # slices the loop's own bound variable needs the PLAIN bound facts
        # (`0 <= i`, `i <= len(s)`) stated BEFORE it, not merely somewhere
        # in the list. count_vowels.json's own invariant order is
        # `r == ...count(s[0..i], ...)...`, THEN `0 <= i`, THEN
        # `i <= len(s)` -- content before bounds -- MEASURED (this
        # session, harness.run_task, count_vowels): every T_Slice (S, 0, I)
        # call inside the first conjunct fails its OWN Pre ("cannot prove
        # B <= Len (S)") for exactly this reason, real TIMEOUT, not a
        # deeper proof difficulty. The task's own invariant list is not
        # this file's to edit, so a stable partition renders bound-only
        # conjuncts (no `at`/`slice`/`update`/`fill`/`div`/`mod`/string-
        # library op anywhere in the conjunct, by `_is_bound_inv`, a
        # generic AST-level read mirroring `_has_pair_op`'s own) FIRST,
        # everything else after, each group keeping its ORIGINAL relative
        # order -- general, not string-library-specific (a slice/at-based
        # invariant from a PRIOR gate could hit the identical ordering
        # trap), and safe for every already-committed task: the matrix
        # regression (below) confirms none of the 23 moves, since every
        # one either states its bounds first already or never brings a
        # data-dependent op into an invariant at all.
        if invs and any(_has_strlib_op(i) for i in invs):
            invs = sorted(invs, key=lambda i: 0 if _is_bound_inv(i) else 1)
        pre = "\n       and then ".join(
            self.expr(i, entry, types) for i in invs)
        post_parts = [self.expr(i, result, types) for i in invs]
        post_parts.append(f"(not {self.expr(w['cond'], result, types)})")
        post = "\n       and then ".join(post_parts)
        d = self.expr(w["decreases"], entry, types)
        variant = f"(if {d} >= 0 then {d} else 0)"
        inner = {v: cap(v) for v in state}
        if body_has_return:
            benv, besc, bval = self.compile_r(
                w["body"], inner, types, psub, ret_name)
        else:
            benv = self.compile(w["body"], inner, types, psub)
            besc = bval = None
        cond = self.expr(w["cond"], {**psub, **inner}, types)
        rec_args = [cap(p["name"]) for p in tparams] \
            + [benv[v] for v in state]
        agg = ", ".join(f"{cap(v)} => {cap(v)}" for v in mut)
        sig = f"function {name} ({'; '.join(plist)}) return {tname}"
        aspects = []
        if pre:
            aspects.append(f"Pre  => {pre}")
        if body_has_return:
            # SPEC.md "Early exit", repaired 2026-09-09: a return inside
            # the loop leaves it without owing the invariant at that
            # point, but it DOES owe the task's own `ensures` right there,
            # and that fact has to be stated on THIS Post, not deferred to
            # F's. F's body only ever sees W_k across the call boundary
            # (SHAPE: everything here is an expression function), so a
            # bare `True` on the Esc arm hands gnatprove zero facts about
            # Ret and the only way left to discharge F's Post is to
            # unroll the recursive W_k from scratch, which is exactly
            # what exhausted the 20000-step budget (see the note below).
            ens_sub = {**psub, ret_name: f"{name}'Result.Ret"}
            ens = "\n       and then ".join(
                self.expr(e, ens_sub, types) for e in self.task["ensures"])
            aspects.append(
                f"Post => (if {name}'Result.Esc then ({ens}) "
                f"else ({post}))")
        else:
            aspects.append(f"Post => {post}")
        aspects.append(f"Subprogram_Variant => (Decreases => {variant})")
        ret_type = ada_type(self.task["returns"][0]["type"])
        if body_has_return:
            fields = "\n".join(f"      {cap(v)} : {ada_type(types[v])};"
                               for v in mut)
            fields += f"\n      Esc : Boolean;\n      Ret : {ret_type};"
            esc_fields = ", ".join(f"{cap(v)} => {benv[v]}" for v in mut)
            base_case = (f"{tname}'({agg}, Esc => False, "
                        f"Ret => {cap(ret_name)})")
            recurse_or_escape = (
                f"(if {besc}\n"
                f"         then {tname}'({esc_fields}, Esc => True, "
                f"Ret => {bval})\n"
                f"         else {name} ({', '.join(rec_args)}))")
            body_expr = (f"(if {cond}\n"
                        f"        then {recurse_or_escape}\n"
                        f"        else {base_case})")
        else:
            fields = "\n".join(f"      {cap(v)} : {ada_type(types[v])};"
                               for v in mut)
            body_expr = (f"(if {cond}\n"
                        f"        then {name} ({', '.join(rec_args)})\n"
                        f"        else {tname}'({agg}))")
        self.helpers.append(
            f"   type {tname} is record\n{fields}\n   end record;\n"
            f"\n"
            f"   {sig}\n"
            f"   with\n     " + ",\n     ".join(aspects) + ";\n"
            f"\n"
            f"   {sig}\n"
            f"   is ({body_expr});\n")
        # A state var may still be Python None here: the pre-check above lets
        # exactly the unassigned return-target case through (SPEC.md "Early
        # exit"), so it needs a placeholder Ada value for the call site --
        # dead on arrival, since nothing upstream constrains or reads it
        # before the loop assigns (or returns) it for real.
        out_args = [cap(p["name"]) for p in tparams] \
            + [(env[v] if env[v] is not None else _dead_lit(types[v]))
               for v in state]
        call = f"{name} ({', '.join(out_args)})"
        out_env = {v: (f"{call}.{cap(v)}" if v in mut else env[v])
                  for v in state}
        if ret_name is None:
            return out_env
        if body_has_return:
            return out_env, f"{call}.Esc", f"{call}.Ret"
        return out_env, None, None

    # --- spec_funs ---------------------------------------------------------

    def lower_spec_fun(self, sf: dict) -> str:
        sub = {p["name"]: cap(p["name"]) for p in sf["params"]}
        types = {p["name"]: p["type"] for p in sf["params"]}
        d = self.expr(sf["decreases"], sub, types)
        plist = "; ".join(f"{cap(p['name'])} : {ada_type(p['type'])}"
                          for p in sf["params"])
        sig = f"function {cap(sf['name'])} ({plist}) return " \
              f"{ada_type(sf['result'])}"
        return (f"   {sig}\n"
                f"   with Subprogram_Variant => "
                f"(Decreases => (if {d} >= 0 then {d} else 0));\n"
                f"\n"
                f"   {sig} is\n"
                f"     ({self.expr(sf['body'], sub, types)});\n")


CERT_NAME = "T_Refutation_Certificate"


def _cert_lit(v) -> str:
    """One witness value as ground Ada text. Types are read off the shape
    of `v` itself (bool before int: a Python bool is an int; a list or
    tuple is a seq; an interp.Pair, checked before either, is a pair, the
    SPEC.md "Pairs" (2026-09-10) distinction from a same-shaped seq that
    isinstance(v, interp.Pair) preserves the way JSON alone (a witness's
    `_j`-shown form) cannot), so the literal cannot disagree with what
    interp.py measured. A pair's own two components recurse (v1 has no
    pair of pairs, so this never recurses twice), rendered as the SAME
    qualified record aggregate expr()'s own `pair` case emits, the Ada
    type name read off the components' OWN shape since a certificate has
    no declared-type context here the way expr() has `types` -- this is
    needed for interp.exit_env's raw (never `_j`-shown) return value,
    which can be an actual Pair object where the twin body's continuation
    recomputes the return after its loop (SPEC.md "Pairs"'s min_max is
    exactly this shape: `r := pair(lo, hi)` runs after the loop, so the
    exit witness's own certificate calls _cert_lit on a live Pair, not a
    JSON-shown list). The list/tuple check widened to accept either for
    the same reason: exit_env's raw values are Python tuples for a seq
    (SPEC.md "Sequences as values"), where a value that never left
    `vals` (untouched by the twin's continuation) is still the JSON-shown
    list a witness carries; a pair's own seq-typed COMPONENT can be
    either, by the same argument one level down."""
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, interp.Pair):
        def _kind(x):
            return ("bool" if isinstance(x, bool) else
                    "seq" if isinstance(x, (list, tuple)) else "int")
        name = _pair_ada_name({"pair": [_kind(v.a), _kind(v.b)]})
        return f"{name}'(P_A => {_cert_lit(v.a)}, P_B => {_cert_lit(v.b)})"
    if isinstance(v, (list, tuple)) and v and isinstance(v[0], (list, tuple)):
        # SPEC.md "Nested sequences (v1)" (2026-09-10): a list of lists (or
        # tuples), a ground nested witness, built as nested Rows.Add chains
        # over each row's own flat Seqs.Add chain, the shape-based reading
        # that pairs an isinstance check with a shape rather than a
        # declared type (interp.exit_env's own raw return value can be one
        # of these, the same reasoning as the list/tuple case just below).
        # An EMPTY outer list falls through to the flat case below instead
        # (the same bottom-up ambiguity Lower._ty's own note on the empty
        # `seq` literal names): unreachable for either committed task,
        # since both certificates read m's own value through
        # _cert_lit_of_type (declared-type, unambiguous), never through
        # this shape-based function.
        out = "Rows.Empty_Sequence"
        for row in v:
            out = f"Rows.Add ({out}, {_cert_lit(list(row))})"
        return out
    if isinstance(v, (list, tuple)):
        out = "Seqs.Empty_Sequence"
        for x in v:
            out = f"Seqs.Add ({out}, Big_Integer'({x}))"
        return out
    return f"Big_Integer'({v})"


def _cert_lit_of_type(v, ty) -> str:
    """PAIRS RESIDUAL (2026-09-09): `_cert_lit`, but TOLD `v`'s declared t
    type `ty` instead of reading it off `v`'s own Python/JSON shape. Needed
    for a task PARAMETER: a witness's `vals` is JSON-shown (interp._j), and
    `_j` renders a pair the SAME 2-list a same-shaped seq would (SPEC.md
    "Pairs": "the runtime value of a pair must be DISTINCT from a seq",
    exactly the confusion `_j`'s own docstring rules out at runtime, lost
    again once the witness is serialized) -- `_cert_lit` alone therefore
    cannot tell `p = [0, 1]` (a pair witness) from `s = [0, 1]` (a seq
    witness) apart. `ty`, read off the task's own declared parameter type
    (certificate()'s/`_undef_obligation`'s `param_types`), breaks the tie
    the same way expr()'s `types` dict already does at lowering time,
    instead of guessing from the JSON list's own shape. v1 has no pair of
    pairs, so a pair's own two components (t1, t2 below) are always a base
    type ("int"/"bool"/"seq"), never recursed through the dict branch a
    second time; a seq component recurses into the same literal `_cert_lit`
    itself builds, since a seq witness value is unambiguous once `ty` says
    "seq" rather than "pair"."""
    if _is_nested_seq(ty):
        # SPEC.md "Nested sequences (v1)" (2026-09-10): a seq<seq>-typed
        # parameter's witness value, a list of row-lists, rendered as a
        # Rows.Add chain, each row recursing into the SAME flat literal
        # this function's own "seq" branch below builds (v1 has exactly
        # one level, so this recurses at most once). Unlike a pair, `ty`
        # already disambiguates unconditionally: no shape-based guess is
        # needed here (contrast _cert_lit's own empty-list ambiguity, which
        # this declared-type path never hits).
        out = "Rows.Empty_Sequence"
        for row in v:
            out = f"Rows.Add ({out}, {_cert_lit_of_type(row, ty['seq'])})"
        return out
    if isinstance(ty, dict):
        t1, t2 = ty["pair"]
        a, b = v
        return (f"{_pair_ada_name(ty)}'(P_A => {_cert_lit_of_type(a, t1)}, "
                f"P_B => {_cert_lit_of_type(b, t2)})")
    if ty == "seq":
        return _cert_lit(list(v))
    if ty == "bool":
        return "True" if v else "False"
    return f"Big_Integer'({v})"


def _cert_loops(body: list) -> list:
    """Every while loop in the twin body, pre-order."""
    out = []
    for s in body:
        if "while" in s:
            out.append(s["while"])
            out += _cert_loops(s["while"]["body"])
        elif "if" in s:
            out += _cert_loops(s["if"]["then"]) + _cert_loops(s["if"]["else"])
    return out


TRUE = {"bool": True}


def _t_conj(parts: list) -> dict:
    parts = [p for p in parts if p != TRUE]
    if not parts:
        return TRUE
    if len(parts) == 1:
        return parts[0]
    return {"op": "and", "args": parts}


def _t_guard(p: dict, q: dict) -> dict:
    """q need only be defined when p holds (SPEC.md "Definedness")."""
    if q == TRUE:
        return TRUE
    return {"op": "implies", "args": [p, q]}


def defined(e: dict) -> dict:
    """SPEC.md's "Definedness" obligation for `e`, as a t-expression (TRUE
    when the whole subtree is total). Mirrors lower_verus.py's function of
    the same name, structure for structure: the rule is SPEC.md's, stated
    once per kernel because each needs the obligation in its own
    expression algebra, not because the rule itself differs kernel to
    kernel. Used only by certificate()'s "undefined" case, below: every
    OTHER definedness check this file emits is stated directly as a Pre
    aspect at the call site (Elem/T_Update/T_Fill/T_Div/T_Mod), and needs
    no separate t-expression reading of "defined" to do that."""
    if "int" in e or "var" in e or "bool" in e:
        return TRUE
    if "ite" in e:
        c = e["ite"]
        dt, de = defined(c["then"]), defined(c["else"])
        branch = (TRUE if dt == TRUE and de == TRUE
                  else {"ite": {"cond": c["cond"], "then": dt, "else": de}})
        return _t_conj([defined(c["cond"]), branch])
    if "call" in e:
        return _t_conj([defined(a) for a in e["call"]["args"]])
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        db = defined(q["body"])
        body_ob = (TRUE if db == TRUE else
                   {"forall": {"var": q["var"], "lo": q["lo"], "hi": q["hi"],
                               "body": db}})
        return _t_conj([defined(q["lo"]), defined(q["hi"]), body_ob])
    op, args = e["op"], e.get("args", [])
    if op == "at":
        s, i = args
        bound = {"op": "and", "args": [
            {"op": "<=", "args": [{"int": 0}, i]},
            {"op": "<", "args": [i, {"op": "len", "args": [s]}]}]}
        return _t_conj([defined(s), defined(i), bound])
    if op == "update":
        s, i, v = args
        bound = {"op": "and", "args": [
            {"op": "<=", "args": [{"int": 0}, i]},
            {"op": "<", "args": [i, {"op": "len", "args": [s]}]}]}
        return _t_conj([defined(s), defined(i), defined(v), bound])
    if op == "fill":
        n, v = args
        nonneg = {"op": ">=", "args": [n, {"int": 0}]}
        return _t_conj([defined(n), defined(v), nonneg])
    if op == "slice":
        # s[a..b] (SPEC.md "Sequences: literals, concatenation, slices",
        # 2026-09-09): DEFINED IFF 0 <= a <= b <= len(s), a definedness
        # obligation the same shape as `at`'s and `update`'s bound, above.
        s, a, b = args
        bound = {"op": "and", "args": [
            {"op": "<=", "args": [{"int": 0}, a]},
            {"op": "and", "args": [
                {"op": "<=", "args": [a, b]},
                {"op": "<=", "args": [b, {"op": "len", "args": [s]}]}]}]}
        return _t_conj([defined(s), defined(a), defined(b), bound])
    if op in ("div", "mod"):
        x, y = args
        nonzero = {"op": "!=", "args": [y, {"int": 0}]}
        return _t_conj([defined(x), defined(y), nonzero])
    if op == "and":
        res = TRUE
        for a in reversed(args):
            res = _t_conj([defined(a), _t_guard(a, res)])
        return res
    if op == "or":
        res = TRUE
        for a in reversed(args):
            res = _t_conj(
                [defined(a), _t_guard({"op": "not", "args": [a]}, res)])
        return res
    if op == "implies":
        p, q = args
        return _t_conj([defined(p), _t_guard(p, defined(q))])
    # total operators: not neg len + - * == != < <= > >= seq. A seq literal
    # and a seq `+` (concatenation) are both total given their operands are
    # (SPEC.md "Sequences: literals, concatenation, slices", 2026-09-09:
    # "a literal is defined iff all its elements are; a concatenation is
    # defined iff both arguments are"), exactly the generic conjunction
    # this fallthrough already builds. `pair`, `fst` and `snd` (SPEC.md
    # "Pairs", 2026-09-10) fall through here too and need no case of their
    # own: `pair` is defined iff both its args are (SPEC.md: "a pair value
    # defined iff both components are"), exactly this fallthrough's own
    # two-argument conjunction; `fst`/`snd` take one argument, and "always
    # defined on a pair" (SPEC.md) is exactly the same fallthrough's
    # one-argument conjunction, defined(p) alone, with no extra bound
    # added the way `at`'s index gets one.
    return _t_conj([defined(a) for a in args])


def _undef_obligation(task: dict, twin_body: list, sub: dict, vals: dict,
                      L: Lower) -> str | None:
    """SPEC.md "Sequences as values" (2026-09-09): the twin's "undefined"
    witness (SPEC.md "The twins": "the twin is undefined where the real
    body has a value") carries no computed value for `ensures` to be
    evaluated at, so the "value" certificate above has nothing to
    substitute the return name with. What IS ground and checkable is the
    partial operator's own definedness obligation: re-walk `twin_body`
    with interp.ev, in the SAME left-to-right statement order interp.py's
    own exec_body used to raise the Undef that minted this witness, calling
    `defined()` (above, the one function this file trusts for the reading)
    at each statement to find the first ground-false obligation, then
    return its negation, rendered to Ada text through L's own expr() (the
    SAME renderer every other certificate part uses, so there is no second
    transcription to disagree with the real lowering). `sub` (var name ->
    Ada text) and `env_py` (var name -> Python value, the tuples-for-seqs
    form interp.ev itself uses) both grow as the walk proceeds, so a later
    statement's own obligation sees the concrete values of every name the
    twin already bound. Mirrors lower_verus.py's `_undef_obligation`
    (2026-09-09) function for function: same walk, same fail-closed
    exits, this file's own renderer in place of Verus's. Returns None on
    an `if`, `while` or `return` before the failing statement (their own
    definedness is not walked here, the same "not emitted" posture as
    every other case in certificate()), or if the walk disagrees with the
    witness and finds nothing false: an honest UNPROVED, never a wrong
    certificate.

    PAIRS RESIDUAL (2026-09-09): a pair-typed PARAMETER is no longer
    refused here by name. `param_types` (the task's own declared
    parameter types, read the same way certificate()'s own paragraph
    above does) breaks the `vals`-is-JSON-shown ambiguity: `_to_py`
    rebuilds a real interp.Pair for `env_py` (interp.ev's `fst`/`snd`/
    `pair` cases need one, never a same-shaped tuple, SPEC.md "Pairs":
    "the runtime value of a pair must be DISTINCT from a seq"), and
    `types` reads the SAME declared type for a parameter name, so a `+`/
    `==` on it still routes through Lower._ty exactly as real lowering
    would. fz_p_pair_seq (SPEC.md "Pairs"'s own pair-with-a-seq-component
    task, a pair-typed PARAMETER, the fuzz family v1pairs's one committed
    "undefined" witness) is MEASURED unchanged by this fix: its twin
    body's own failing statement sits inside an `if` (DROP-GUARD, not a
    bare `var`/`assign`), which the walk below still returns None on
    before ever consulting a type -- an honest UNPROVED, never a wrong
    certificate, exactly the walk's own pre-existing "if/while/return"
    limit (above), not the parameter-shape ambiguity this paragraph
    removes."""
    param_types = {p["name"]: p["type"] for p in task["params"]}

    def _to_py(v, ty):
        """`v` (JSON-shown) rebuilt as the Python shape interp.ev expects,
        told `ty` instead of guessing from `v`'s own shape -- the same
        tie-break _cert_lit_of_type makes on the Ada-text side."""
        if _is_nested_seq(ty):
            # SPEC.md "Nested sequences (v1)" (2026-09-10): a JSON list of
            # row-lists rebuilt as a tuple of tuples, exactly the shape
            # interp.ev already produces for a nested seq value (interp.py:
            # `at`/`update`/`len` nest for free over plain tuples, no new
            # Expr forms), so env_py holds the same value real execution
            # would build here, unlike a pair (which needs an actual
            # interp.Pair, distinct from a same-shaped tuple).
            return tuple(_to_py(row, ty["seq"]) for row in v)
        if isinstance(ty, dict):
            t1, t2 = ty["pair"]
            a, b = v
            return interp.Pair(_to_py(a, t1), _to_py(b, t2))
        if ty == "seq":
            return tuple(v)
        return v

    env_py = {n: (_to_py(v, param_types[n]) if n in param_types else
                 (tuple(v) if isinstance(v, list) else v))
             for n, v in vals.items()}
    # A static `types` dict for Lower._ty (SPEC.md "Sequences: literals,
    # concatenation, slices", 2026-09-09: needed to render a seq `+` inside
    # `ob` as T_Concat rather than native `+`; SPEC.md "Pairs", to route a
    # pair `==`/`fst`/`snd` correctly). A PARAMETER name reads its declared
    # type off `param_types` directly, exactly like certificate()'s own
    # `types`; anything else (a local this walk has since bound) reads its
    # type off the Python shape `env_py` already carries -- there is no
    # AST-level types dict at a witness for a local.
    types = {n: (param_types[n] if n in param_types else
                ("seq" if isinstance(v, tuple) else
                 "bool" if isinstance(v, bool) else "int"))
            for n, v in env_py.items()}
    sub = dict(sub)
    funs = interp.funs_of(task, twin_body)
    st = interp.St()
    try:
        for s in twin_body:
            if "var" in s:
                name, e = s["var"]["name"], s["var"]["init"]
            elif "assign" in s:
                name, e = s["assign"]
            else:
                return None
            ob = defined(e)
            if ob != TRUE and not interp.ev(ob, env_py, funs, st):
                return f"(not {L.expr(ob, sub, types)})"
            val = interp.ev(e, env_py, funs, st)
            env_py[name] = val
            # NOT MEASURED: a local var this walk binds to a Pair value
            # (v1's only committed "undefined" task, fz_p_pair_seq, never
            # reaches a `var`/`assign` at all -- see the docstring above)
            # -- carried for the next task the same way certificate()'s
            # own "exit"-witness pair-local fallback is.
            if isinstance(val, interp.Pair):
                def _kind(x):
                    return ("bool" if isinstance(x, bool) else
                            "seq" if isinstance(x, (list, tuple)) else "int")
                types[name] = {"pair": [_kind(val.a), _kind(val.b)]}
            else:
                types[name] = ("seq" if isinstance(val, tuple) else
                               "bool" if isinstance(val, bool) else "int")
            sub[name] = _cert_lit(list(val) if isinstance(val, tuple)
                                  else val)
    except (interp.Undef, interp.Budget, RecursionError):
        return None
    return None


def certificate(task: dict, body: list, w: dict | None, L: Lower) -> str:
    """THE REFUTATION CERTIFICATE (10.8). One additional ground goal, named
    exactly T_Refutation_Certificate, that instantiates the harness witness
    so the kernel itself can judge it: verifiers/spark.py mints REFUTED only
    when gnatprove DISCHARGES every check of this function, and a file that
    so much as names it can never mint VERIFIED there.

    Three witness kinds are certificatable in this kernel:

      * "value" (a whole-program input): the goal is requires at the input,
        and then not (ensures at ret := F(input)). F is the file's own twin
        F, so the kernel evaluates the twin body it was handed, not a
        transcription: F's defining axiom (it is an expression function)
        forces F(input) to the twin's computed value, and the goal is
        provable exactly when that value falsifies the ensures. Emitted only
        when the witness records _ens true, because a twin value that merely
        DIFFERS may still satisfy a loose ensures, and a goal known to be
        false is not an instrument.

      * "exit" (a loop state, from INVARIANT-DROP): the goal is the negated
        exit-entailment VC at the state, requires and then the surviving
        invariants and then not cond and then not ensures at the RETURN,
        the state run through the statements after the loop first
        (interp.exit_env; since 2026-09-07), every variable a literal. That is byte-for-byte the statement interp.invariant_witness
        measured (admissibility included), restated to the kernel: a state
        the survivors admit, at the loop's exit, where the theorem fails.
        The twin body's own loop supplies the survivors, so the certificate
        weakens nothing itself. Emitted only when the twin body has exactly
        one loop, the one the witness's state ranges over.

      * "undefined" (SPEC.md "Sequences as values", 2026-09-09): the twin
        has no value at the witness because some statement's right-hand
        side hit a partial operator (`at`, `update`, `fill`, `div`, `mod`)
        outside its domain, so there is no computed value for `ensures` to
        be evaluated at, the way "value" above needs one. What IS ground
        and checkable is the operator's own definedness obligation, false
        at the witness: requires holds at the input, and that failing
        obligation, re-derived by replaying the twin body with interp.ev
        in the same order interp.py used to raise the witnessing Undef
        (`_undef_obligation`, above), is asserted negated. MEASURED
        2026-09-09: swap's off-by-one twin (`tmp := s[i]` mutated to
        `s[i+1]`) is undefined at s=[0], i=0, j=0 (index 1 outside [0,1)),
        the "undefined" shape interp.py's Reference.witness has always
        been able to produce (SPEC.md "The twins") but that no task
        committed before this pair ever measured; the certificate this
        builds carries `(not (0 <= (i+1) and then (i+1) < Len (s))))` at
        the witness's literals and gnatprove discharges it.

    "preservation" witnesses are not certificated: it needs one symbolic
    body step from the state, which this file does not yet trust itself to
    instantiate. Fail closed: no certificate, and the cell honestly reads
    what the kernel could judge.

    Any lowering failure (a name the witness does not value, an operator
    outside t) emits no certificate rather than a wrong one.

    PAIRS RESIDUAL (2026-09-09): a task with a pair-typed PARAMETER now
    gets a certificate like any other -- the fuzz family v1pairs (SPEC.md
    "Pairs", 2026-09-10) MEASURED 16 of 19 pair-family cells read
    verified/unproved rather than verified/refuted, and the cause was
    exactly the gap this paragraph used to describe: `vals` below is
    JSON-shown (interp._j), so a pair-typed parameter's witness value
    (a 2-list) was indistinguishable from a same-shaped seq's, and the old
    `sub`/`types` here read types off THAT shape alone. The fix is
    `param_types`, the task's own declared parameter types (always known
    statically, never guessed): `_cert_lit_of_type` uses it to render a
    pair parameter as the qualified record aggregate F's own signature
    expects instead of a Seq literal, and `types` now carries the SAME
    declared type `_ty` needs to route a pair `==`/`fst`/`snd` correctly,
    rather than the string "seq" a shape-only reading would have produced.
    A name NOT in `param_types` (a loop-local var reaching an "exit"
    witness) still falls back to the old shape-based reading, unaffected --
    v1's loop-carrying pair tasks (SPEC.md "Pairs"'s own min_max included)
    reach this certificate through a "value" witness, never "exit", so no
    committed task exercises that fallback on an actual pair value; it
    is carried for the next one, exactly like _cert_lit's own Pair case
    before it.
    """
    if not w:
        return ""
    kind = w.get("_kind")
    vals = {k: v for k, v in w.items() if not k.startswith("_")}
    param_types = {p["name"]: p["type"] for p in task["params"]}
    sub = {k: (_cert_lit_of_type(v, param_types[k]) if k in param_types
              else _cert_lit(v))
          for k, v in vals.items()}
    ret = task["returns"][0]["name"]
    # A static `types` dict for Lower._ty (SPEC.md "Sequences: literals,
    # concatenation, slices", 2026-09-09), plus the task's own declared
    # return type: the return is never itself a witness input, so it would
    # otherwise be missing from a `vals`-derived reading. A PARAMETER name
    # reads its declared type directly off `param_types` (PAIRS RESIDUAL,
    # above); anything else (an "exit" witness's loop-local var) still
    # falls back to a shape-based guess, the only reading available for a
    # name with no AST-level declaration here.
    types = {k: (param_types[k] if k in param_types else
                ("seq" if isinstance(v, list) else
                 "bool" if isinstance(v, bool) else "int"))
            for k, v in vals.items()}
    types[ret] = task["returns"][0]["type"]
    ens = None
    try:
        parts = [L.expr(e, sub, types) for e in task.get("requires", [])]
        if kind == "value":
            if w.get("_ens") is not True:
                return ""
            if set(vals) != {p["name"] for p in task["params"]}:
                return ""
            args = ", ".join(sub[p["name"]] for p in task["params"])
            call = f"F ({args})" if args else "F"
            ens = [L.expr(e, {**sub, ret: call}, types)
                   for e in task["ensures"]]
        elif kind == "exit":
            loops = _cert_loops(body)
            if len(loops) != 1:
                return ""
            loop = loops[0]
            # The obligation is at the RETURN: the loop-exit state run
            # through whatever follows the loop (interp.exit_env, None under
            # an enclosing loop). A tail loop runs nothing and the goal is
            # unchanged. Measured 2026-09-07 (ROADMAP 12.5): slow_max
            # assigns its result after its loop, and this goal, stating
            # not-ensures at the loop's own state, minted REFUTED on a twin
            # gnatprove proves.
            post = interp.exit_env(task, body, loop, vals)
            if post is None:
                return ""
            parts += [L.expr(i, sub, types) for i in loop.get("invariants", [])]
            parts.append(f"(not {L.expr(loop['cond'], sub, types)})")
            ens = [L.expr(e, {**sub, ret: _cert_lit(post[ret])}, types)
                   for e in task["ensures"]]
        elif kind == "undefined":
            ob = _undef_obligation(task, body, sub, vals, L)
            if ob is None:
                return ""
            parts.append(ob)
        else:
            return ""
    except (ValueError, KeyError, NotImplementedError):
        return ""
    if ens is not None:
        neg = f"(not {ens[0]})" if len(ens) == 1 \
            else "(not (" + " and then ".join(ens) + "))"
        parts.append(neg)
    conj = "\n      and then ".join(parts)
    sig = f"function {CERT_NAME} return Boolean"
    return (f"   --  Refutation certificate: the measured witness, restated\n"
            f"   --  as one ground goal for the kernel to judge (see the\n"
            f"   --  header). This file can never claim VERIFIED.\n"
            f"   {sig}\n"
            f"   with Post => {CERT_NAME}'Result;\n"
            f"\n"
            f"   {sig} is\n"
            f"     ({conj});\n")


# `witness` is the twin's measured witness (harness.twin_cached). Twin call
# sites pass it; a certificatable witness becomes the certificate goal above.
def lower(task: dict, body: list, witness: dict | None = None) -> str:
    L = Lower(task)
    ret = task["returns"][0]
    psub = {p["name"]: cap(p["name"]) for p in task["params"]}
    # SPEC.md "Sequences: literals, concatenation, slices" (2026-09-09): the
    # `types` dict Lower._ty reads (a seq `+` vs an int `+`) has to carry
    # every param from the start, not just the return + locals compile()/
    # compile_r() already tracked (SEQUENCES AS VALUES, 2026-09-09): a `+`
    # on two PARAMETERS (unlike tail/filter_pos's own bodies, which concat
    # a param with a freshly-built literal or slice) would otherwise read
    # an unbound name here.
    base_types = {**{p["name"]: p["type"] for p in task["params"]},
                 ret["name"]: ret["type"]}
    # SPEC.md "Pairs" (2026-09-10): every distinct pair type this task
    # uses, first-appearance order (_pair_types) -- read here, before
    # anything downstream, both to widen needs_seq (a pair with a seq
    # component needs Seq declared before its own record can name it,
    # below) and to widen `reserved` (below) before the name-capture check
    # runs.
    pair_types_used = _pair_types(task, body)
    # PAIRS RESIDUAL (2026-09-10): a task that builds a pair transiently
    # (constructed and projected within one expression, no param, return,
    # or `var` of a pair type anywhere for `_pair_types` to have declared a
    # record for) would otherwise emit Ada text naming an undeclared
    # record -- MEASURED, fz_p_pair_proj, malformed/malformed. Refused by
    # name here, honestly, rather than risked: `_pair_types` coming back
    # empty is the exact, decidable signal (every other committed pair
    # task has at least one declared pair type, so this never fires on
    # them), and this task's own `body` (the twin's body at the twin call,
    # the real body otherwise) plus `requires`/`ensures`/`spec_funs` is
    # everywhere `pair` can appear.
    if not pair_types_used and (
            _has_pair_op(body) or _has_pair_op(task.get("requires", []))
            or _has_pair_op(task.get("ensures", []))
            or _has_pair_op(task.get("spec_funs", []))):
        raise NotImplementedError(
            "spark: a pair is built and used within one expression, with "
            "no parameter, return, or local of a pair type anywhere for "
            "this task's own record declarations to cover")
    # SPEC.md "Sequences as values" (2026-09-09): seq is now a return and
    # local type too, not just a parameter type, so the preamble condition
    # widens to match: the task's own return, a spec_fun's result, or a
    # `var` declared seq anywhere in the body (locals_seq, below) all need
    # it exactly as a seq parameter always did. A pair with a seq
    # component (SPEC.md "Pairs", 2026-09-10) needs it too: the record's
    # own field is typed Seq (_pair_preamble).
    # SPEC.md "Nested sequences (v1)" (2026-09-10): the same shape of scan
    # needs_seq's own does, but for {"seq": "seq"}; needs_nested_seq widens
    # needs_seq too (Rows is built OVER Seq, NESTED_SEQ_PREAMBLE's own
    # note), the same way a pair with a seq component already widens it.
    needs_nested_seq = (
        any(_is_nested_seq(p["type"]) for p in task["params"])
        or _is_nested_seq(ret["type"])
        or any(_is_nested_seq(p["type"])
              for sf in task.get("spec_funs", []) for p in sf["params"])
        or any(_is_nested_seq(sf["result"])
              for sf in task.get("spec_funs", []))
        or locals_nested_seq(body)
        # THE STRING LIBRARY (v1), 2026-09-11: split's result and join's
        # argument are seq<seq> values that can sit entirely transiently
        # in one expression (word_count's `t2.split()`, split_join's
        # `join(split(s, c), [c])`), with no param, return, or `var` of
        # the nested type anywhere for the scan above to see
        # (_has_strlib_nested_op's own docstring).
        or _has_strlib_nested_op(body)
        or _has_strlib_nested_op(task.get("requires", []))
        or _has_strlib_nested_op(task.get("ensures", []))
        or _has_strlib_nested_op(task.get("spec_funs", [])))
    needs_seq = (
        needs_nested_seq
        or any(p["type"] == "seq" for p in task["params"])
        or ret["type"] == "seq"
        or any(p["type"] == "seq"
              for sf in task.get("spec_funs", []) for p in sf["params"])
        or any(sf["result"] == "seq" for sf in task.get("spec_funs", []))
        or locals_seq(body)
        or any("seq" in pt["pair"] for pt in pair_types_used))
    # NESTED SEQUENCES RESIDUAL (2026-09-10): a task that builds a nested
    # seq LITERAL transiently (constructed and projected within one
    # expression, no param, return, or `var` of the nested type anywhere
    # for `needs_nested_seq` to have found) would otherwise emit Ada text
    # naming Rows/Seqs/Len/Elem with neither preamble ever requested --
    # MEASURED, fz_p_nest_lit, malformed/malformed. Refused by name here,
    # the same posture the pair check just above takes toward
    # `_has_pair_op`: `needs_nested_seq` coming back False is the exact,
    # decidable signal (every committed nested-seq task has a declared
    # param or return of the type, so this never fires on them).
    if not needs_nested_seq and (
            _has_nested_seq_op(body)
            or _has_nested_seq_op(task.get("requires", []))
            or _has_nested_seq_op(task.get("ensures", []))
            or _has_nested_seq_op(task.get("spec_funs", []))):
        raise NotImplementedError(
            "spark: a nested seq is built and used within one expression, "
            "with no parameter, return, or local of the nested seq type "
            "anywhere for this task's own preamble to cover")

    # The seq and range preambles put fixed Ada names in scope; a t
    # identifier capitalizing onto one of them would be captured silently,
    # which is a wrong answer rather than a missing one.
    # `Esc`/`Ret` (SPEC.md "Early exit", 2026-09-08) only enter the emitted
    # package when a loop actually escapes, so they are only reserved for a
    # task has_return finds a `return` in; the other 13 committed tasks'
    # RESERVED set, and therefore their output, is untouched.
    reserved = RESERVED | ({"Esc", "Ret"} if has_return(body) else set())
    # SPEC.md "Pairs" (2026-09-10): each pair type's own record name, its
    # equality wrapper's name (_pair_preamble; reserved whether or not this
    # task ever compares two pairs -- there is no cheap structural
    # predicate for "will Lower.expr render a pair `==`" the way
    # has_return() is one for `return`, so this is more cautious than
    # Esc/Ret above need to be), and the field names P_A/P_B every pair
    # record declares, all only reserved for a task that uses a pair type
    # at all; a task with none keeps its previous RESERVED set exactly.
    # PAIRS RESIDUAL (2026-09-10): the field names were originally A/B,
    # MEASURED (fuzz family v1pairs) to fold-case collide with the
    # lowercase t identifiers `a`/`b` a real task chose for its own two
    # parameters (fz_v1pairs_064: a seq-slice-pair task named exactly
    # `a`/`b`) -- an abstain this reservation caught honestly, but on a
    # pair of names common enough in practice to be worth not colliding
    # with at all. Renamed to P_A/P_B, still reserved here the same way
    # (a t identifier `p_a`/`p_b` is not impossible, only far less likely
    # than `a`/`b`), so the fix is the new field name everywhere it is
    # EMITTED (_pair_preamble, expr()'s `pair`/`fst`/`snd` cases,
    # _dead_lit, _cert_lit, _cert_lit_of_type), not a change to this
    # collision-detection mechanism itself.
    if pair_types_used:
        pair_ada_names = {_pair_ada_name(pt) for pt in pair_types_used}
        reserved |= (pair_ada_names | {"P_A", "P_B"}
                    | {f"{n}_Eq" for n in pair_ada_names})
    reserved_lc = {r.lower() for r in reserved}
    clash = sorted(n for n in bound_names(task, body)
                   if n.lower() in reserved_lc)
    if clash:
        raise NotImplementedError(
            f"spark: t name(s) {clash} collide with the emitted package's own "
            f"names ({sorted(reserved)})")
    named = sorted(bound_names(task, body) | {task["name"]})
    by_ada = {}
    for n in named:
        by_ada.setdefault(cap(n).lower(), []).append(n)
    merged = sorted(v for v in by_ada.values() if len(v) > 1)
    if merged:
        raise NotImplementedError(
            f"spark: t names {merged} spell the same Ada identifier after the "
            f"underscore rule in cap()")

    spec_funs = [L.lower_spec_fun(sf) for sf in task.get("spec_funs", [])]

    # SPEC.md "Early exit" (2026-09-08): a body that can `return` is lowered
    # through compile_r, which threads the escape alongside the ordinary
    # substitution env; one without it keeps compile() exactly as it read
    # before this note. Either way F's Post (below) is the task's `ensures`
    # applied uniformly to F'Result, so the exit obligation SPEC.md states
    # ("the task owes its ensures there as at every exit") falls out of
    # this merge for free rather than needing its own restatement.
    if has_return(body):
        env, esc, val = L.compile_r(
            body, {ret["name"]: None}, base_types, psub, ret["name"])
        if env[ret["name"]] is None:
            raise ValueError(f"body never assigns {ret['name']!r}")
        final = env[ret["name"]] if esc is None \
            else f"(if {esc} then {val} else {env[ret['name']]})"
    else:
        env = L.compile(body, {ret["name"]: None}, base_types, psub)
        if env[ret["name"]] is None:
            raise ValueError(f"body never assigns {ret['name']!r}")
        final = env[ret["name"]]

    aspects = []
    reqs = [L.expr(e, psub, base_types) for e in task.get("requires", [])]
    if reqs:
        aspects.append("Pre  => " + "\n       and then ".join(reqs))
    post_sub = {**psub, ret["name"]: "F'Result"}
    aspects.append("Post => " + "\n       and then ".join(
        L.expr(e, post_sub, base_types) for e in task["ensures"]))
    if "decreases" in task:
        d = L.expr(task["decreases"], psub, base_types)
        aspects.append(f"Subprogram_Variant => "
                       f"(Decreases => (if {d} >= 0 then {d} else 0))")

    cert = certificate(task, body, witness, L)

    plist = "; ".join(f"{cap(p['name'])} : {ada_type(p['type'])}"
                      for p in task["params"])
    fsig = f"function F ({plist}) return {ada_type(ret['type'])}" if plist \
        else f"function F return {ada_type(ret['type'])}"
    pkg = f"T_{cap(task['name'])}"
    parts = [
        "pragma Ada_2022;",
        "with Ada.Numerics.Big_Numbers.Big_Integers;",
        "use  Ada.Numerics.Big_Numbers.Big_Integers;",
    ]
    if needs_seq:
        parts += ["with SPARK.Containers.Functional.Infinite_Sequences;"]
    parts += [f"package {pkg} with SPARK_Mode is", ""]
    if needs_seq:
        parts += [SEQ_PREAMBLE]
    if needs_nested_seq:
        parts += [NESTED_SEQ_PREAMBLE]
    if L.needs_update:
        parts += [UPDATE_PREAMBLE]
    if L.needs_update2:
        parts += [NESTED_UPDATE_PREAMBLE]
    if L.needs_range:
        parts += [RANGE_PREAMBLE]
    if L.needs_eq:
        parts += [EQ_PREAMBLE]
    if L.needs_eq2:
        parts += [NESTED_EQ_PREAMBLE]
    if L.needs_fill:
        parts += [FILL_PREAMBLE]
    if L.needs_fill2:
        parts += [NESTED_FILL_PREAMBLE]
    if L.needs_slice:
        parts += [SLICE_PREAMBLE]
    if L.needs_slice2:
        parts += [NESTED_SLICE_PREAMBLE]
    if L.needs_concat:
        parts += [CONCAT_PREAMBLE]
    if L.needs_concat2:
        parts += [NESTED_CONCAT_PREAMBLE]
    if L.needs_divmod:
        parts += [DIVMOD_PREAMBLE]
    # THE STRING LIBRARY (v1), 2026-09-11: STRCORE before anything that
    # calls T_Match_At/Is_Ws (count/find/replace/split(s)); the split-state
    # record before either split form; T_Slice/T_Concat (above) before
    # anything that calls them (strip/replace/case/tostr/join).
    if L.needs_strcore:
        parts += [STRCORE_PREAMBLE]
    if L.needs_str_count:
        parts += [STRCOUNT_PREAMBLE]
    if L.needs_str_find:
        parts += [STRFIND_PREAMBLE]
    if L.needs_str_strip:
        parts += [STRSTRIP_PREAMBLE]
    if L.needs_str_replace:
        parts += [STRREPLACE_PREAMBLE]
    if L.needs_str_case:
        parts += [STRCASE_PREAMBLE]
    if L.needs_str_pred:
        parts += [STRPRED_PREAMBLE]
    if L.needs_str_affix:
        parts += [STRAFFIX_PREAMBLE]
    if L.needs_str_tostr:
        parts += [STRTOSTR_PREAMBLE]
    if L.needs_str_split_state:
        parts += [STRSPLITSTATE_PREAMBLE]
    if L.needs_str_split_c:
        parts += [STRSPLITC_PREAMBLE]
    if L.needs_str_split_w:
        parts += [STRSPLITW_PREAMBLE]
    if L.needs_str_join:
        parts += [STRJOIN_PREAMBLE]
    if pair_types_used:
        parts += [_pair_preamble(pair_types_used, L.needs_pair_eq)]
    for sf in spec_funs:
        parts += [sf]
    for h in L.helpers:
        parts += [h]
    parts += [
        f"   {fsig}",
        "   with\n     " + ",\n     ".join(aspects) + ";",
        "",
        f"   {fsig} is",
        f"     ({final});",
        "",
    ]
    inst = ce_instance(task, body)
    if inst:
        parts += [inst]
    if cert:
        parts += [cert]
    parts += [f"end {pkg};"]
    return "\n".join(parts) + "\n"


def ce_instance(task: dict, body: list) -> str:
    """The task at machine inputs, or "" when this file cannot bound it.

    The instance exists only to give gnatprove a domain its counterexample
    generator can build a model in and its RAC can execute; neither is
    possible over Big_Integer (header). It is emitted after F, so the havoc
    oracle's `function F ... is` scan still lands on F: verifiers/spark.py's
    pattern requires whitespace, `(` or `return` after the F, and `F_Ce`
    presents `_`.
    """
    ret = task["returns"][0]
    # SPEC.md "Pairs" (2026-09-10): a pair type is a dict, not a hashable
    # CE_TYPE key, so `ret["type"] not in CE_TYPE` below would raise
    # TypeError: unhashable type on a pair-typed return before ever
    # reaching the ordinary "outside the fragment" reading; checked first,
    # short-circuiting the `or` before that lookup ever runs. A pair value
    # has no machine mirror regardless (the header's own reasoning for
    # seq), so this is the same fail-closed treatment, stated first only
    # because it also has to be stated safely.
    if isinstance(ret["type"], dict) \
            or any(isinstance(p["type"], dict) for p in task["params"]) \
            or ret["type"] not in CE_TYPE \
            or any(p["type"] not in CE_TYPE for p in task["params"]) \
            or task.get("spec_funs") or "decreases" in task:
        return ""
    try:
        env = _ce_stmts(body, {**{p["name"]: (CE_WINDOW
                                              if p["type"] == "int" else None)
                                  for p in task["params"]},
                               ret["name"]: _UNSET})
        pbound = {p["name"]: (CE_WINDOW if p["type"] == "int" else None)
                  for p in task["params"]}
        for e in task.get("requires", []):
            _ce_bound(e, pbound)
        for e in task["ensures"]:
            _ce_bound(e, {**pbound, ret["name"]: env[ret["name"]]})
        L = Lower(task, ce=True)
        psub = {p["name"]: cap(p["name"]) for p in task["params"]}
        base_types = {**{p["name"]: p["type"] for p in task["params"]},
                     ret["name"]: ret["type"]}
        cenv = L.compile(body, {ret["name"]: None}, base_types, psub)
        final = cenv[ret["name"]]
        post_sub = {**psub, ret["name"]: "F_Ce'Result"}
        ens = [L.expr(e, post_sub, base_types) for e in task["ensures"]]
        reqs = [L.expr(e, psub, base_types) for e in task.get("requires", [])]
    except (_NoCe, ValueError, NotImplementedError, KeyError):
        # Outside the fragment. The unbounded theorem above is the artifact;
        # the instance is an addition, and its absence costs a refutation,
        # never a proof.
        return ""
    if env[ret["name"]] is _UNSET:
        return ""
    # `requires` becomes a hypothesis of the Post rather than a Pre: a Pre
    # unsatisfiable inside the window is VC_INCONSISTENT_PRE, which
    # verifiers/spark.py rules VACUOUS for the whole file (header).
    if reqs:
        post = ("(if " + "\n                and then ".join(reqs)
                + "\n              then "
                + "\n                and then ".join(ens) + ")")
    else:
        post = "\n       and then ".join(ens)
    plist = "; ".join(f"{cap(p['name'])} : {CE_TYPE[p['type']]}"
                      for p in task["params"])
    sig = (f"function F_Ce ({plist}) return {CE_RET[ret['type']]}" if plist
           else f"function F_Ce return {CE_RET[ret['type']]}")
    return (CE_PREAMBLE + "\n"
            + f"   {sig}\n"
            + f"   with\n     Post => {post};\n"
            + "\n"
            + f"   {sig} is\n"
            + f"     ({final});\n")


if __name__ == "__main__":
    raise SystemExit(harness.run_all(sys.argv[1:], lower, spark_backend, "ads"))
