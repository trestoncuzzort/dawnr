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

## Not a residual: the 25 `policy-gap:array` rows

`LIFTER-785.md`'s "Undecided rows (26)" is 25 rows reading `policy-gap:array`
plus the `problem6` row above. Those 25 are not a defect. They are the
standing consequence of LIFTER-DECISIONS row 1, which lifts a read-only
`array<int>` to a `seq` under stated conditions and refuses otherwise. A row
that fails those conditions is decided, not undecided; what is undecided is
whether to widen the rule, and that is Treston's call rather than the
lifter's.
