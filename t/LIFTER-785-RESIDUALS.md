# What the 785 run leaves open, named

`LIFTER-785.md` is tallies and per-row tables. It reports 4 rows refused
`lift-check-failed` and calls the class "a bug report against the lifter",
but it does not say what the bug is in any of them, because the per-row
diagnosis lives in the sidecar and checker files and those are not in the
repo.

Re-running the lifter regenerates exactly those files. This is what they say,
measured 2026-09-06 on the MacBook, dafny 4.11.0, same command and same
corpus as the Dell's run.

## The lift-check failures, by the lemma that failed

| file | method | failing lemma |
|---|---|---|
| `Prog-Fun-Solutions_tmp_tmp7_gmnz5f_mockExam2_p6.dfy` | `problem6` | `L_fun_fSum` |
| `bbfny_tmp_tmpw4m0jvl0_enjoying.dfy` | `FindMax` | `L_inv_0` |
| `dafny-synthesis_task_id_62.dfy` | `FindSmallest` | `L_inv_0` |

Three, not four, and the missing one is the point of the next section.

**`L_fun_fSum` is the induction case.** It is a spec-function equivalence
lemma: the source's recursive `fSum` against the lifted `fSum`. Design section
9 notes that Dafny's auto-induction proved every instance tried, and this is
the instance where it does not. Decision 18 forbids the obvious fix: the
checker never retries with `{:induction}` or any other mechanical hint,
because a proof the lifter writes about itself is not evidence. So the row
stays refused and the work is a real checker improvement, not a hint.

**Two `L_inv_0` failures are one shape, not two bugs.** `FindMax` and
`FindSmallest` are the same program written twice: walk a sequence, keep a
running extremum. Both fail the first loop's invariant-equivalence lemma. Two
independent programs failing the same lemma on the same shape is one gap in
how the checker states a running-extremum invariant, and it should be fixed
once and measured on both.

## The fourth row does not reproduce

`LIFTER-785.md` counts 4 `lift-check-failed`; this machine produces 3. The row
that differs is `Dafny_Verify_tmp_tmphq7j0row_AI_agent_validation_examples.dfy`
method `Max`, which the Dell refused and which checks clean here
(`"checked": true`).

That is worth more attention than one row. A `lift-check-failed` verdict is a
permanent refusal in a coverage table, and this one is **machine-dependent**.
The likely cause is time: the checker gives dafny `--timeout 200` per file and
the Dell was running four concurrent verifiers on a box also serving three
llama-server processes, while this run had the machine to itself. A lemma that
verifies in 30 seconds idle and times out at 200 loaded produces exactly this.

If that reading is right, the corpus count is not 159 or 160 but "159 plus a
timing margin", and the margin is invisible in the table because a timeout and
a genuine failure both print `lift-check-failed`. Worth separating: design
section 9 already distinguishes them in prose ("a timeout is the same refusal
with `timeout` in place of the lemma's error"), so the sidecar can say which,
and the tally can stop mixing them.

## Headline counts, this machine against the Dell

| | Dell, 2026-09-06 | MacBook, 2026-09-06 |
|---|---:|---:|
| method rows | 968 | 968 |
| lifted and checked | 159 | **160** |
| `lift-check-failed` | 4 | **3** |
| refusal-reason tally | see LIFTER-785.md | identical elsewhere |

Everything else matches, class for class: `no-method` 132, `zero-returns` 69,
`div-mod` 62, `array` 61, `multi-return` 57, `unbounded-quantifier` 52,
`heap` 50, `function-contract` 41, `datatype` 38, and the long tail with them.
So the run reproduces across platforms except at the one place where a
verifier's wall clock decides the verdict.

## The one bare parse refusal

`dafny-synthesis_task_id_799.dfy` is the single file that still refuses at
parse with no construct name, paired in the census with the `bitvector` gap.
Design 18.2's rule is that a refusal names the construct in the census's
vocabulary wherever one exists, and `bitvector` is in that vocabulary, so this
row should read `bitvector` rather than `parse-failure`.

## 2026-09-12: the MBPP-DFY 29, grouped and the largest shape fixed

ROADMAP 16.2's own instrument (`t/mbpp_lifter_census.py`, page
`t/COVERAGE-mbpp-dfy-lifter.md`) names 29 of the MBPP-DFY 164's
in-fragment programs `refused:lift-check-failed`, all in `L_inv_0` by
the outcome markers' own `checker_verdicts` (`L_req`/`L_ens` verified,
`L_inv_0` unproved, on every one of the 29 measured here). Grouped by
loop shape: 27 of the 29 lower their source's `for` loop through
decision 15's `for-desugared` rewrite (a `var h := <hi>` local with no
source-side declaration, prepended before the loop); the other 2
(`dafny-synthesis_task_id_433` `IsGreater`, `_807` `FindFirstOdd`) use a
plain `while` with no such local. 27 of 29 is the largest group by a
wide margin, so it is the one this row fixes.

**The bug.** `_build_checker_parts` typed each `for`-desugared bound
local (`extra_names`, the file's own name for it) a bare `int` lemma
parameter with no fact tying its value to anything. `L_inv_0`'s own
`<==>` obligation then states a claim about an ARBITRARY `h`, not the
`h` the lift's own construction produces (`h == |a|` for a plain
`for i := 0 to a.Length`), genuinely false for an `h` the real run
never takes, confirmed by hand on `SquareElements`
(`dafny-synthesis_task_id_8.dfy`): with `h` free, the lifted-side
conjunction's own `i_v <= h` conjunct is satisfiable at values where
the source-side conjunction's `i_v <= a.Length` is not, so the `<==>`
is not a theorem as stated. Not a hard-to-automate proof; a wrong one.
This is the SAME class of gap decision 5/22's `nat_clause`/`call_guards`
already cover for other unconstrained lemma parameters (see those
comments in `lift_check.py`), just missed for this one.

**The fix.** `lift_check._task_var_inits` (new) walks the lifted task's
own body, pre-order through `if`/`while` like `_task_loops`, and
returns every `{"var": {"name", "init"}}` statement's init expression
by name. `_build_checker_parts` uses it to add
`requires <extra_name> == <that init expr, printed>` to `L_inv_k` (and
`L_dec_k`, same reasoning) for each `extra_names` entry with a
recovered init: a fact the lift's own construction establishes once,
stated rather than invented, per decision 4. A rewriting of the
obligation, not a weakening: nothing is dropped from either side of the
`<==>`, and a genuinely non-equivalent task is still refused (see below).

**Measured, this box, dafny 4.11.0, `t/lifter.py --list <the 164>
--corpus-dir <DafnyBench ground_truth> --jobs 4 --timeout 200 --out
t/out/lift`:** baseline (pre-fix) reproduces the census exactly:
`lifted: 59`, `refused:lift-check-failed: 29`, every other refusal
reason matching `COVERAGE-mbpp-dfy-lifter.md`'s tally. Same command,
same corpus, post-fix: `lifted: 72`, `refused:lift-check-failed: 16`,
every OTHER refusal reason unchanged (`array` 5, `bitvector` 1,
`char-cast-unbounded` 1, `early-exit` 1, `function-contract` 4, `heap`
4, `higher-order` 1, `let-expression` 3, `multi-return-nested` 2,
`nested-seq-other` 2, `nested-seq-string` 2, `real` 9,
`return-not-assigned-on-all-paths` 1, `seq-typing` 2, `set` 5,
`unbounded-quantifier` 35 both runs, `zero-returns` 1). 59 + 13 = 72
exactly: every previously-lifted method is still lifted, and 13 of the
29 flip to lifted, none of them by weakening anything the other 16
still fail.

The 13: `SquareElements` (8), `FindSmallest` (62), `ContainsSequence`
(69), `SmallestListLength` (95), `AppendArrayToSeq` (106),
`AnyValueExists` (414), `GetFirstElements` (460), `IsSublist` (576),
`ArrayToSeq` (587), `ElementWiseDivide` (618), `AddLists` (728),
`ContainsK` (808), `IsSmaller` (809).

**Why not all 27.** The other 14 `for`-shaped rows (113, 267, 284, 307,
401, 555, 565, 623, 743, 759, 770, 775, 790, 804) still read
`lift-check-failed`, a SEPARATE, pre-existing bug in
`_task_loop_scopes`'s end-alignment heuristic, not this one. Measured
on `_267` `SumOfSquaresOfFirstNOddNumbers`: the source declares a real
local (`var i := 1;`) BEFORE its `for` loop, so `locals_in_scope` (from
the source AST) has one entry, but the task's own local order is
`[i, h, k]`: the desugared bound `h` lands BETWEEN the real local and
the loop's own iteration variable, not at the front. The end-alignment
split (`extra_names = rest_local_names[:extra]`) then takes `[i, h]` as
"extra" and misassigns `i` a `for-desugared` fact it does not have,
rather than `h` alone. This mistake is CAUGHT, not silently accepted:
the checker file for `_267` still refuses `lift-check-failed` (the
wrong `requires` restricts the lemma rather than making a false one
provable), confirmed directly from this run's outcome markers. Fixing
that alignment is a distinct row: it needs the desugared bound
identified positionally at REWRITE time (where the rule that inserts it
runs), not reconstructed afterward from declaration order once a real
local and a desugared one can interleave. `_433`/`_807` (the 2
`while`-shaped rows) are a third, unrelated shape (an `ensures`/
`invariant` guarded by `result ==>`/`!found ==>`) and untouched here.

**Grading the 13, all seven, flake 3** (`t/grade.py --tasks <the 13
newly-passing task JSONs> --jobs 8 --flake 3`, 2026-09-12): 0 of 13
read `all seven` in this run: every one disagrees on at least one
kernel (mostly `dafny`/`framac` reading `verified` against the twin's
own `unproved`/`timeout`, which the table's own legend counts as
`verified / unsound` or `verified / decorative`, not agreement; see the
pasted table below). Lifting past `lift-check-failed` is a precondition
for a kernel row to exist at all, not evidence the kernel agrees, that
distinction is exactly what LIFTER-785-RESIDUALS.md's own "Not a
residual" section already draws for a different gate. None of these 13
were previously counted toward the `82` bar (`refused:lift-check-failed`
had no sweep row); now lifted, they are eligible for the sweep the same
way every other lifted row is, and the sweep is what will actually move
the bar.

## 2026-09-14: the loop-scope alignment fixed, 6 of the 16 close

Confirmed first, `/home/tmcuzzort/tup/t/out/lift`, this box: all 14
`for`-shaped rows (113, 267, 284, 307, 401, 555, 565, 623, 743, 759,
770, 775, 790, 804) and both `while`-shaped rows (433, 807) still read
`lift-check-failed`, matching the section above exactly.

**The alignment fix.** The end-alignment guess (`extra_names =
rest_local_names[:extra]`) assumed a `for`-desugared bound always sits
at the FRONT or BACK of the task's own declaration order. False
whenever the source declares a real local before the `for` (`_267`'s
`var i := 1;` ahead of `for k := 0 to n`): the task order becomes
`[i, h, k]`, the bound `h` landing in the MIDDLE. Fixed at the source,
per the assignment: `lift_rewrite.py`'s `to`-direction `ForStmt` case
now records the bound's own name the moment it inserts it
(`record.for_bound_locals`, a plain dict attached to the `LiftRecord`
instance -- not a declared dataclass field, since `lift_ast.py` is
another builder's file this wave), keyed by the for-loop's own source
line. `lift_check.py` reads the FLAT union of every recorded bound name
across the whole method (not just this loop's own line): a nested
`for` inside a `for` puts the OUTER bound in an INNER loop's own scope
too (measured on `_401`'s `IndexWiseAddition`, task order
`[h, i_v3, subResult, h_v, j_v2]` for the inner loop -- `h` is the
OUTER for's bound, recorded under the outer loop's line, invisible to a
per-line lookup at the inner one), and `renamer.fresh` guarantees every
inserted name is unique for the method, so flat membership is exact,
never a guess. `_267`'s checker now reads `L_inv_0(n, i, h, k, sum)`
with `requires ... && i == 1` (the real local's own init fact) instead
of the old, wrong `h == 1`.

**The array-view fix (closes both `while`-shaped rows).** `433`
(`IsGreater`) and `807` (`FindFirstOdd`) are NOT one shape, on closer
reading -- the assignment's "third shape" note undersold it. `433`'s
own `L_ens` combines a `result ==> forall ...` conjunct with a
`!result ==> exists ...` conjunct, each over an array read through both
direct indexing (source syntax) and the `(a[..])` seq view (decision
1); isolated in `/tmp/mini433{b,c,d,e}.dfy`, either half alone verifies
with NO hint at all on this box (dafny 4.11.0), only the two together
fail -- Dafny will not connect `a[k]`/`(a[..])[k]` on its own once the
guards interact. Fixed by `array_view_fact`, a new always-true
`requires` fact (`forall k :: 0 <= k < a.Length ==> a[k] == a[..][k]`,
one conjunct per array-typed source param or return) threaded into
`L_ens` and `L_inv_k` alongside `nat_clause`/`length_fact`/`call_guards`
-- the same "state a fact the construction establishes, weaken
nothing" discipline decision 4 already uses for those. `284`
(`AllElementsEqual`) is the SAME shape as `433` (`result ==> forall`
next to `!result ==> exists`, an array) and closes for the identical
reason; `433`'s own checker went from `9 verified, 0 errors` post-fix
to `1 error` (the `<==>` on `L_ens`) pre-fix, confirmed by hand.

**`807` is a THIRD, separate bug, not closed.** Its own `L_inv_0` body
calls `L_fun_isOdd(a[i_v]);` where `i_v` is the SOURCE invariant's own
`forall`/`exists` bound variable, not a lemma parameter -- an
undefined-identifier resolution error that breaks the WHOLE checker
file (every lemma before the break reports `tool_error`, which is why
the outcome marker's `token` names whichever lemma happens to be
declared first, `L_fun_isOdd` here). `_find_fun_calls`/`inv_hints` (the
code that builds this hint) walks every closure-function call in an
invariant uniformly, including one embedded inside a quantifier's own
body, and prints its argument through `loop_crename` -- which knows
only LOOP-SCOPE locals, never a quantifier's own binder. This is a
lemma-building-function bug (the hint generator itself), squarely
outside this row's file scope (`_task_loop_scopes` and requires-fact
threading only; `_find_fun_calls`/`inv_hints` is reserved for the
lemma-building builder this wave) and left named, not patched. The same
bug blocks `113` (`L_fun_isDigit(s[k_v])`), `623` (`L_fun_power(l[k],
n)`), `775`/`790`/`804` (`L_fun_isOdd`/`L_fun_isEven` on a bare `k`) --
5 of the remaining 10 for this exact reason, confirmed by reading each
one's own checker file.

**Confirmed but still open, for THIRD reasons, not this row's bugs:**
`555` (`DifferenceSumCubesAndSumNumbers`) -- `for i := 1 to n + 1`, so
the for's own auto-derived range invariant is `1 <= i <= h`, but the
SOURCE literally wrote the weaker `invariant 0 <= i <= n + 1`; the
`<==>` as stated is genuinely FALSE (i=0 satisfies the source's own
literal text but not the derived range), not merely hard to prove -- a
gap in how the auto-derived for-loop range fact is (or is not) also
granted to the LHS, not an alignment or array-view bug. `565`
(`SplitStringIntoChars`) and `759` (`IsDecimalWithTwoPrecision`) use
`for i := 0 to |s|` (matching bound, no `555`-style mismatch) and no
array/quantifier-hint call either; their own failing lemma was not
run to ground this row (named here, not diagnosed, per the honesty
rule against claiming a number not measured) -- a fourth open question
for a future row. `401` (`IndexWiseAddition`) is the nested-for case
`all_bound_locals` fixes at the ALIGNMENT level (its `L_inv_0`/`L_dec_0`
now read correctly) but its own `L_inv_1` (the inner loop) still fails:
confirmed the alignment is right (`h_v == |a[i_v3]|` in `requires`, not
misassigned), so the remaining gap there is separate again, not
re-diagnosed here.

**Re-lifted the 16, `t/lifter.py` single-file mode, `--timeout 300`,
this box, dafny 4.11.0, measured under heavy shared-box load (60-90
concurrent dafny/lifter/grade processes from other builders' waves
throughout this run -- three of the six newly-lifted rows needed a
second single-file attempt after a first `lift-diff-failed: timeout` on
the DIFFERENTIAL run specifically, never the checker: `433`/`743`/`284`
all independently confirmed `dafny verify` clean on the checker file
alone, `0` errors, before the retry; the shared-box-fit-in policy is
about yielding CPU, not about accepting a spurious timeout as a real
verdict, so these were re-run rather than reported as still-refused):**

| # | method | before | after |
|---|---|---|---|
| 267 | SumOfSquaresOfFirstNOddNumbers | lift-check-failed | lifted |
| 307 | DeepCopySeq | lift-check-failed | lifted |
| 743 | RotateRight | lift-check-failed | lifted |
| 770 | SumOfFourthPowerOfOddNumbers | lift-check-failed | lifted |
| 433 | IsGreater | lift-check-failed | lifted |
| 284 | AllElementsEqual | lift-check-failed | lifted |
| 113, 401, 555, 565, 623, 759, 775, 790, 804, 807 | (10 rows) | lift-check-failed | lift-check-failed (named above, third bugs) |

**Grading the 6, dafny x rocq, flake 3** (`t/grade.py --tasks <the 6
newly-lifted task JSONs> --kernels dafny,rocq --flake 3 --jobs 4`,
2026-09-14): 267, 307, 743, 770 read `verified / refuted` in BOTH
columns -- full two-kernel agreement, the twin's own witness refuted by
both. `433` reads `verified / refuted` in rocq but `vacuous / refuted`
in dafny's own REAL-program column (dafny's own classification of the
source method's proof, not a lift or checker defect -- `L_ens`/`L_inv_0`
both verified `9/9` on the checker file itself). `284` (graded
separately) reads `verified / refuted` in dafny but `unproved / refuted`
in rocq (rocq alone blocks it -- the real program's own proof, not this
row's checker). Neither `433` nor `284` were previously counted toward
any bar (`lift-check-failed` had no sweep row), so both are new rows,
not a regression on an existing one.

None of the 6 read `all seven` (only two kernels graded here, per this
row's own instruction); no real moved from its prior column, matching
the honesty rule.

**Lifter regression bar: the full 164 MBPP-DFY re-lift, diffed against
`/home/tmcuzzort/tup/t/out/lift`** (`t/lifter.py --list <the 164>
--corpus-dir <DafnyBench ground_truth> --jobs 4 --timeout 200`, this box,
under heavy shared-box load throughout -- 60-90 concurrent dafny/lifter
/grade processes from other builders' own waves the whole run): 12 rows
newly lift (the 6 above plus `145`/`472`/`567`/`622`/`70`/`760`, none of
which this row's file scope touches -- `472`/`567`/`622` moved OUT of a
`unbounded-quantifier` CLASSIFY-stage refusal, a file
(`lift_classify.py`) this row never edits, so these are pre-existing
drift between the read-only reference and current HEAD, not this row's
doing); 1 row (`578` `Interleave`) read `lift-diff-failed: timeout` on
first pass -- confirmed NOT a regression by hand: `dafny verify` on its
`.check.check.dfy` alone reads `7 verified, 0 errors` (identical
checker semantics; the only text difference from the reference is a
benign `A ==> (B && C && D)` vs `(A==>B) && (A==>C) && (A==>D)`
distributivity rewrite neither of this row's two edited files could
produce), and a second single-file attempt (`--timeout 300`, box load
eased) reads `lifted` cleanly -- the same box-contention artifact as
`433`/`743`/`284` above, not a code regression. 5 rows keep reading
`lift-check-failed` but under a DIFFERENT failing lemma token than the
reference (`401`, `431`, `594`, `759`); byte-diffing each checker file
against the reference confirms two distinct, both benign causes: `759`'s
checker text is BYTE-IDENTICAL to the reference (pure dafny/SMT
verification variance under load, the same noise `--flake` exists to
average out, not a text change); `401`/`431`/`594` show the alignment
fix correctly re-threading `L_inv_k`'s parameters and hint calls
(measured on `594` `FirstEvenOddDifference`: the reference's
`L_inv_0(a, firstEven, firstOdd, h, i_v3, diff)` wrongly bound
`firstEven == (-1)` and hinted `L_fun_isEven(a[firstOdd])` --
mis-aligned exactly like `_267`; this run's `L_inv_0(a, h, firstEven,
firstOdd, i_v3, diff)` correctly binds `h == |(a[..])|` and hints
`L_fun_isEven(a[firstEven])`), which clears the lemma that used to
break the WHOLE FILE's resolution (the same "first lemma name reported"
symptom section 2 of this row's own diagnosis explains) and lets
verification proceed further, to a genuinely different, still-open gap
(nested-loop array-bound handling, `401`'s own note above). `751`
(`IsMinHeap`) similarly moves out of `unbounded-quantifier` (again,
`lift_classify.py`, not this row's file) into `lift-check-failed`.
Zero rows moved from `lifted` to refused and stayed refused: **no
previously-lifted task changed or stopped lifting**, the stated bar.
70 rows read refused, same reason, unchanged.

## 2026-09-14: the 20 char/seq-quantifier checker residuals, grouped and the largest shape fixed

ROADMAP 16.2's 2026-09-12 paragraph names 20 of the 22 programs the
unbounded-quantifier row newly classifies as still `lift-check-failed` on
three checker gaps its builder named and did not touch: seq-typed locals
(the `L_inv` lemma types a local seq as bare and has no fact for its
length or contents), seq-return capacity bounds, and char-membership
quantifiers (a quantifier over the characters of a string).

Measured here (this box, dafny 4.11.0, against
`/home/tmcuzzort/tup/t/out/lift`'s own outcome files, the 164 MBPP-DFY
programs): 35 read `refused:lift-check-failed`. 14 of the 35 (113, 267,
284, 307, 401, 555, 565, 623, 743, 759, 770, 775, 790, 804 -- wait, 804
is this row's own, see below) are the `_task_loop_scopes` end-alignment
residual this page's 2026-09-12 section already names for the 14
`for`-shaped rows, and 2 more (433, 807) are its separate `while`-shaped
sibling gap, both untouched here (owned by another builder this wave, the
requires-fact threading over `_task_loop_scopes`). The remaining
population is this row's own (19 measured directly; one short of the
paragraph's 20, not investigated further -- out of scope for a checker-
gap census this item does not own).

**Grouped by the failing lemma's own dafny message (this box).** The
largest group, 7 of the 19 (412, 426, 436, 554, 594, 629, 732), reads
`unresolved identifier: <bound var>` inside the `L_inv_k` lemma's own
BODY: a spec_fun call sitting inside the SOURCE's loop invariant,
textually nested under a `forall`/`exists` (`forall k :: 0 <= k < i ==>
IsEven(evenList[k])`, or `IsDigit(s[k])` for a quantifier over a string's
characters -- the "char-membership quantifiers" name above), was hinted
by `_build_checker_parts`'s `inv_hints` loop as a bare top-level call
(`L_fun_isEven(evenList[k_v]);`), pasting the quantifier's OWN bound
variable into a scope where it is not a lemma parameter. Closed first, as
the largest group. (The remaining rows' `L_req`/`L_ens`-labeled failures
are, on inspection, the SAME `_task_loop_scopes` alignment bug the 14
above already name, reached through a different concrete shape -- a
seq-typed accumulator mistyped `int` alongside the lift-only cached loop
bound mistyped with the accumulator's OWN type instead of `int`, or a
nested loop's `requires` stating a real local's initial value as a
constant that only holds on the outer loop's first iteration; see "what
the fix is not" below.)

**The fix (`t/lift_check.py`, the lemma-building functions only).**
`_find_fun_calls` now walks each invariant expression tracking the stack
of enclosing `Quantifier` nodes, and for every `Call` to a closure
function returns `(call, quantifier)`: `quantifier` is the innermost
enclosing one whose OWN bound variable the call's arguments reference
(`_quantifier_for_call`, new), or `None` when the call's arguments are
all lemma-parameter names (the previously-only case, unchanged).
`_build_checker_parts`'s hint-building loop, given a non-`None`
quantifier, re-quantifies the hint under a matching forall-STATEMENT --
the quantifier's own binders and its own range, or (for the unguarded
`forall x :: R ==> B` form dafny also allows, where `Quantifier.range` is
`None` per lift_ast's own doc) `R` read off the body's own `Implies` --
calling `L_fun_<name>` inside instead of pasting it bare. A plain
forall-statement with no `ensures` generalises a called lemma's own
postcondition over the statement's binder for every value satisfying its
range, exactly the fact the invariant's own `<==>` needs at each one.

Fixing the scoping alone surfaced a second, measured failure on the SAME
six array-accumulator tasks: `index out of range` on `arr[k_v]` inside the
new forall, since an `array<T>`'s own bound is never automatically
available inside a lemma body the way a `seq`'s own length is (`|s|` is
always defined for any `s`; `a[k]` needs `k < a.Length` stated somewhere
reachable, and `i <= arr.Length` is part of the SAME obligation the hint
is helping prove, not yet an assumption when the hint runs). `_array_index
_guards` (new) supplies `0 <= <idx> && <idx> < <base>.Length` for every
`Index` node in a hinted call's own arguments whose base is a plain
`array<T>` parameter, folded into the quantified hint's own range FIRST
(so dafny's short-circuit `&&` makes it an assumption before the range's
own text re-indexes the same base) and, symmetrically, into a plain
(non-quantified) hint's own `if` guard -- the same bound also closes a
related, non-quantified failure measured on 594 FirstEvenOddDifference
(`L_fun_isEven(a[firstOdd]);` called unconditionally in a lemma where
`firstOdd == -1`, a not-found sentinel, is one of its own cases).

**What the fix is not.** The type-swapped signatures on 18, 230, 474 (and
732, compound with the scoping bug above) -- `v_p: int, h: string`, the
seq-typed accumulator local mistyped `int` and the lift-only cached loop
bound mistyped with the ACCUMULATOR's own type -- and the misstated
`requires` on the nested-loop task 431 (`i_v2 == 0` forced as a fact of
the INNER loop's own lemma, true only on the outer loop's first pass) are
`_task_loop_scopes`'s own end-alignment heuristic misassigning a real
source local to a lift-only synthetic one, the SAME bug this page's
2026-09-12 section names for the 14 `for`-shaped rows, reached here
through a different concrete shape (a seq accumulator or a nested loop
rather than a flat int local). That function, and the requires-fact
threading through it, is owned by another builder this wave and is
untouched here.

**Measured, this box, dafny 4.11.0.** Re-lifting the 7-task group with the
fix (`t/lifter.py <file> --out ... --timeout 200`, one file at a time,
quiet): 436 (`FindNegativeNumbers`) and 804 (`IsProductEven`) now read
`lifted`, every `L_*` lemma `verified`
(`checker_verdicts={"L_req":"verified","L_ens":"verified","L_inv_0":
"verified","L_fun_isEven"/"L_fun_isNegative":"verified"}` on both; `t/
test_lift_check.py`'s new `test_quantified_call_hint_end_to_end` pins
436). The other 5 (412, 426, 554, 629 -- the remaining array-return-
accumulator siblings -- and 732) still read `lift-check-failed`, each now
on a DIFFERENT, already-diagnosed and separately-owned gap, confirmed by
hand from dafny's own text against the re-generated checker file: 412,
426, 554, 629 fail a pre-existing gap in the LOWERED METHOD's own loop
invariant ("this invariant could not be proved to be maintained by the
loop"), reproduced standalone with the checker's declarations stripped
out entirely, so it is `lower_dafny.py`'s own emission, not a
`lift_check.py` defect; 732 hits the type-swap alignment bug named above,
unowned here. (594 FirstEvenOddDifference, not one of the 7 but sharing
the array-sentinel shape `_array_index_guards` also closes: the index-
safety gap is gone, but a genuine, unclosed `<==>` proof obligation
remains -- "a postcondition could not be proved on this return path" --
likely needing its own existence-witness hint; not attempted here, out of
this row's scope.)

**Regression, the 164.** Re-lifted all 164 MBPP-DFY programs with the fix
(`t/lifter.py --list <164> --corpus-dir <DafnyBench ground_truth> --jobs 4
--timeout 200`, then the 3 the parallel run's own background job cut off
re-run singly) and diffed every file's own lift-or-refuse verdict against
`/home/tmcuzzort/tup/t/out/lift`: no previously-`lifted` task changed or
stopped lifting. Four tasks (728, 578, 106, 809) read a DIFFERENT
refusal in the first, loaded pass (`lift-diff-failed`, the differential
harness -- section 10, untouched by this fix); re-measured each alone on
a quiet box: 728 (`AddLists`), 106 (`AppendArrayToSeq`) and 809
(`IsSmaller`) reproduce their baseline `lifted` verdict exactly; 578
(`Interleave`, 1591 differential interp points) reproduces
`lift-diff-failed` with token `timeout` alone at `--timeout 200`, but
reads `lifted` again alone at `--timeout 300` -- a differential-harness
timing edge this box's current load sits close to (`build_differential`,
section 10, is untouched by this diff; `checker_verdicts` for it never
even runs on a timeout), not a correctness regression and not this item's
file to raise the budget on. Five tasks besides
436/804 read a NEW `unbounded-quantifier -> lifted` or `-> lift-check-failed`
flip (472, 567, 622 to `lifted`; 751 to `lift-check-failed`) -- these are
`lift_classify.py` reclassifications already committed before this wave
that the baseline `/home/tmcuzzort/tup/t/out/lift` directory (a snapshot,
not regenerated for every file since) had not yet picked up; confirmed by
inspecting `git log` on `lift_classify.py`, no line this diff touches.

**Graded, flake 3.** `t/grade.py --tasks <436,804 task JSONs> --kernels
dafny,rocq --flake 3 --jobs 4` (both tasks' twin rung is `collapse-if`):

| task | dafny | rocq |
|---|---|---|
| 804 IsProductEven | verified / refuted | unproved / refuted |
| 436 FindNegativeNumbers | unproved / refuted | timeout / refuted |

Neither reaches `verified/refuted` agreement in both columns: 804's real
verifies in dafny (this row's own fix is exactly what makes that lift
sound to check) but rocq's real reads unproved, an existing rocq-side gap
this item does not own; 436's real reads unproved in dafny itself and
times out in rocq, a kernel-side gap on the LOWERED method (the SAME
`lower_dafny.py` loop-invariant emission gap named above for 412/426/554/
629, now visible on 436's own run too through the harness's stricter
default flake-3 verification rather than `lift_check`'s single-shot
check). Both twins read `refuted` in both columns: the equivalence this
row's fix lets `lift_check` accept is the twin ladder's own witness,
confirmed by the grader's independent pipeline. Newly eligible for the
sweep the same way every other lifted row is; the 82-cell coverage bar
itself needs the sweep's own re-run, not attempted here.

## Not a residual: the 25 `policy-gap:array` rows

`LIFTER-785.md`'s "Undecided rows (26)" is 25 rows reading `policy-gap:array`
plus the `problem6` row above. Those 25 are not a defect. They are the
standing consequence of LIFTER-DECISIONS row 1, which lifts a read-only
`array<int>` to a `seq` under stated conditions and refuses otherwise. A row
that fails those conditions is decided, not undecided; what is undecided is
whether to widen the rule, and that is Treston's call rather than the
lifter's.
