# The case split: a loop inside a branch, graded by lean, rocq and fstar; registered before any compared set is regraded

Across the seven student answer sets graded with the corrected instrument (the shipped seeds, teacher1's three,
teacher2's seed 1), the problems proved by at least one kernel but not by all seven lose most of their missing cells
to abstentions, and two lowering gaps cause nearly all of them: a quantifier in computational position (framac, lean
and rocq, 12 cells each) and **a loop inside a branch (lean, rocq and fstar, 7 cells each)**. The second is the
shape the student writes, a guard for the edge case with the loop in the `else` (`if n < 2 { r := false } else {
... while ... }`), because the loop's invariants do not hold on the edge case. The first adds no problem at all seven
in any set once the second is fixed; the second's upper bound, if every such cell verified, is 13 to 16 by all seven
for teacher2's seed 1, 12 to 14 for teacher1's seed 3, one more for two shipped seeds, and none for Phi.

## The change (commit 00716c53, branch `case-split`, not yet merged)

`t/run_par.py`: when lean, rocq or fstar abstains only because a loop sits inside a branch, and that branch is the
body's first top-level `if` with a loop in an arm, whose condition reads parameters only (a parameter is never
assigned, `check_wf` Gate 2) and uses only total operators (no `div`, `mod`, indexing, slices, calls or quantifiers),
the cell is graded as two tasks: `requires` plus the condition, with the `then` arm in place of the `if`; `requires`
plus its negation, with the `else` arm (the statements after the `if` dropped from a half whose arm always returns).
Dijkstra's rule for the conditional, wp(if E then S1 else S2, R) = (E => wp(S1, R)) and (not E => wp(S2, R)) for a
pure, defined E (fetched, research receipt bf9e04160124), says the task holds exactly when both halves do. A side is
verified when both halves are, refuted when either is (a half's region is where the original runs exactly its
statements; a twin's witness goes to the half whose guard holds at it); an unsplit side runs in both halves and must
agree with itself. Every cell that lowered before lowers byte-identically; none of the 39 committed tasks is
eligible, so `t/AGREEMENT.md` does not change. Tests: `t/test_run_par_case_split.py` (14), and the existing
`test_run_par_guards`, `test_twin_rule` and `test_cli` pass.

**A trial informed the code before this registration** (this machine's kernels, under the load of a running
assembly), on four tasks: teacher2 seed 1's 605, 345 and 741, and the shipped seed 1's 68. Each went from four kernels
to five or six: 345 to six (lean unproved), 605 to five (lean unproved; rocq unproved on both sides, the twin being
the whole `then` arm, which rocq could not refute), 68 and 741 to six (rocq timed out on both sides). None reached all
seven there. Those four are not predicted below.

## The regrade

On the lab, from a separate checkout of the branch, so the lab's own checkout keeps grading the measurements
registered before this change with the code they were registered with (teacher2's seed 2,
`t/PREDICT-2026-10-04-teacher2-student.md`; release v4's 33 given specifications, `t/PREDICT-2026-10-04-release-v4.md`):
`run_par.py --kernels lean,rocq,fstar` over every task of a compared set whose lean, rocq or fstar cell abstained for
this reason and to which the split applies: 19 tasks and 57 cells (Phi under the grammar: 1 task, `mbpp_167` in its
s5 set; Phi prompted: none; the v5 seeds 5; the shipped seeds 5; teacher1's 4; teacher2's seeds 1 and 3, 4; teacher2's
seed 2 is added when graded). The new cells are written into copies of the sets (tag suffix `-cs`) with every other
cell as graded, and scored with the same verdict files and `t/score_levels.py --min-completeness 0.6`. Both numbers
are reported for every set.

## Predictions

- **K1.** Phi's counts do not change: under the grammar 9 at one kernel and 7 by all seven, prompted 3 and 3.
- **K2.** No set loses a problem at any level.
- **K3.** Of the 15 eligible (set, problem) pairs outside the trial, at least 2 reach all seven.
- **K4.** At least half of the 57 cells read a verdict other than abstain (verified, refuted, unproved or timeout).

Section 1 is then judged again on the regraded numbers by its own rule (doubled when every seed proves at least twice
Phi's regraded counts at both levels), beside the judgement made on the registered instrument, which stands as made.
The teacher2 round's Q1 to Q3 are judged on the instrument they were registered with.
