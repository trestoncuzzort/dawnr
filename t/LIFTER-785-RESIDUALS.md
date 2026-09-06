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

## Not a residual: the 25 `policy-gap:array` rows

`LIFTER-785.md`'s "Undecided rows (26)" is 25 rows reading `policy-gap:array`
plus the `problem6` row above. Those 25 are not a defect. They are the
standing consequence of LIFTER-DECISIONS row 1, which lifts a read-only
`array<int>` to a `seq` under stated conditions and refuses otherwise. A row
that fails those conditions is decided, not undecided; what is undecided is
whether to widen the rule, and that is Treston's call rather than the
lifter's.
