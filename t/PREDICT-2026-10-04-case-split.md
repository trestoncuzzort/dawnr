# The case split: a loop inside a branch, graded by lean, rocq and fstar; registered before any compared set is regraded

> **Correction, 2026-10-05:** counts on the clean 200 in this file include 18 problems that an audit of the training rows
> later took out of the panel. Every published row is restated on the clean 182 in
> [DECONTAMINATION-2026-10-05.md](DECONTAMINATION-2026-10-05.md).
> A second correction that day holds each specification to inputs larger than the examples as well; the rows are
> restated again in [LARGER-INPUTS-2026-10-05.md](LARGER-INPUTS-2026-10-05.md).

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

## Outcome, 2026-10-04 12:01Z (`~/scratch/cs-regrade/`: the lab's tables, `build.py`, the `-cs` copies, `verdicts-cs.json`)

The 57 cells graded on the lab from a checkout of 00716c53 in four minutes (11:55Z to 11:59Z). Lean, rocq, fstar on
each regraded task (real / twin):

| set | task | lean | rocq | fstar |
|---|---|---|---|---|
| v5 seed 1 | 201 | unproved / refuted | timeout / refuted | verified / refuted |
| v5 seed 2 | 47 | refuted / refuted | refuted / refuted | refuted / refuted |
| v5 seed 3 | 472 | verified / refuted | timeout / timeout | verified / refuted |
| v5 seed 3 | 605 | unproved / refuted | unproved / unproved | verified / refuted |
| v5 seed 3 | 741 | verified / refuted | verified / refuted | verified / refuted |
| shipped seed 1 | 552 | unproved / refuted | refuted / refuted | refuted / refuted |
| shipped seed 1 | 68 | verified / refuted | timeout / timeout | verified / refuted |
| shipped seed 2 | 552 | refuted / unproved | refuted / unproved | malformed / refuted |
| shipped seed 3 | 201 | verified / refuted | timeout / timeout | verified / refuted |
| shipped seed 3 | 605 | unproved / refuted | unproved / unproved | verified / refuted |
| teacher1 seed 1 | 3 | unproved / refuted | unproved / unproved | verified / refuted |
| teacher1 seed 1 | 741 | verified / refuted | verified / unproved | verified / refuted |
| teacher1 seed 3 | 605 | unproved / refuted | unproved / unproved | verified / refuted |
| teacher1 seed 3 | 741 | verified / refuted | verified / refuted | verified / refuted |
| teacher2 seed 1 | 345 | unproved / refuted | verified / refuted | verified / refuted |
| teacher2 seed 1 | 605 | unproved / refuted | unproved / unproved | verified / refuted |
| teacher2 seed 1 | 741 | verified / refuted | timeout / timeout | verified / refuted |
| teacher2 seed 3 | 605 | unproved / refuted | unproved / unproved | verified / refuted |
| Phi under the grammar s5 | 167 | refuted / refuted | refuted / refuted | refuted / refuted |

Every real read **refuted** here (47, 552 twice, 167) is a program the other four kernels already refute on both
sides, with a real witness the bounded scan found (an input where the program breaks its own `ensures`, or is
undefined): routed to its half, the witness gave the same refutation in the three kernels that could not read the
program before. No kernel contradicts another.

The clean 200, complete specifications, at least one kernel / three / five / six / all seven, before and after:

| set | before | after |
|---|---|---|
| Phi under t's grammar, 17 answers | 9 / 8 / 8 / 7 / 7 | 9 / 8 / 8 / 7 / 7 |
| v5 seed 3 | 15 / 13 / 9 / 9 / 7 | 15 / 13 / 11 / 10 / **8** |
| shipped seed 1 | 17 / 16 / 13 / 11 / 10 | 17 / 16 / 14 / 12 / 10 |
| shipped seed 3 | 17 / 15 / 12 / 11 / 8 | 17 / 15 / 13 / 11 / 8 |
| teacher1 seed 3 | 21 / 19 / 17 / 15 / 12 | 21 / 19 / 19 / 16 / **13** |
| teacher2 seed 1 | 23 / 20 / 14 / 13 / 13 | 23 / 20 / 17 / 15 / 13 |
| teacher2 seed 3 | 27 / 23 / 16 / 15 / 13 | 27 / 23 / 17 / 15 / 13 |

v5 seeds 1 and 2, the shipped seed 2 and teacher1's seed 1 change at no level; Phi prompted had no eligible cell.

- **K1 holds:** Phi under the grammar 9 and 7, prompted 3 and 3.
- **K2 holds:** no set loses a problem at any level.
- **K3 holds, exactly:** 2 of the 15 pairs outside the trial reach all seven (741 in v5 seed 3 and in teacher1 seed 3).
- **K4 holds:** all 57 cells read a verdict; none abstains.

**Section 1 on the regraded numbers:** unchanged. Phi stays at 9 and 7, so doubling still needs 18 and 14 for every
seed, and teacher2's seeds 1 and 3 stay at 13 by all seven. The split closes the gap it was built for, and the
kernels then show what is left: rocq times out on both sides of the loop half on four tasks (68, 201, 472, and 741
in teacher2 seed 1), and lean cannot prove the loop half of 605, 345, 201 and 3, where fstar proves it. Those are
the cells between teacher2's seeds and 14.

**What remains, diagnosed on the trial's lean files (not changed here; each would be its own registration).** Lean's
two failures on the loop halves are tactic gaps, not shapes: on 605 the preservation goal `found = true -> exists k
in [2, n). n % k == 0`, at the step where `found` becomes true because `n % d == 0`, needs the witness `d`, and the
closer has witness heuristics only for establishment (the range's lower end) and for carrying an old witness through
an update (the file's header notes both); on 345 `repeat split` also splits the `if` inside the ensures, so the
recursive lemma's conclusion no longer unifies in a branch the requires already rules out. Rocq's four are timeouts
on both sides of the loop half.

## Merged, and the last two sets regraded, 2026-10-04 (recorded 17:01Z)

Merged as 91f6e629 once teacher2's seed 2 and release v4's lab gradings were done. The same targeted regrade on the
sets graded just before the merge: teacher2's seed 2 (6 eligible tasks) and the release-v4 candidate (3), lean, rocq
and fstar on the lab. Rocq timed out or read unproved on every one, so neither gains a problem by all seven:

| set | before | after |
|---|---|---|
| teacher2 seed 2 | 24 / 21 / 17 / 16 / 15 | 24 / 21 / 19 / 17 / 15 |
| the release-v4 candidate | 23 / 18 / 15 / 14 / 13 | 23 / 18 / 17 / 15 / 13 |

The real program of 482 (seed 2) now reads refuted in rocq and fstar, as dafny, verus and framac already read it (a
real witness: undefined at `s=[65]`). Teacher2's three seeds therefore read 23, 24, 27 and 13, 15, 13 under either
instrument, which is the comparison `t/PREDICT-2026-10-04-teacher3-student.md` registered.

**Rocq's timeouts are not the budget (2026-10-04, recorded 23:14Z).** `coqc` alone on the trial's loop half of 741 (the
half rocq times out on for teacher2's seed 1 and teacher3's seed 3) had not finished after 900 s, five times the
verifier's 180 s backstop: the generated proof does not close, so a longer limit would not move these cells; the
rocq lowering's script for this loop shape is the work, as lean's two gaps above are.
