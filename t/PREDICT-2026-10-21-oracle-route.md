# The student's own Python as the specification gate's oracle: registered 2026-10-21 07:00Z, before the run

From t/PREDICT-2026-10-21-spec-ceiling.md: the three-test SAFE gate keeps the right candidate for 19 of 63
problems at five candidates while a right one exists for 18 (and for 29 at twenty), and it loses 10 problems
that have one. The gate is the lever that needs no training. `t/spec_gate.py` already judges a specification
by the reference check with the student's own tested Python in the reference's place (Clover's doc2code edge,
arXiv:2310.17807; CodeT arXiv:2207.10397): agreement on at least 10 of 100 drawn inputs inside the requires,
the requires admitting at least half of the drawn inputs, and at least 60% of mutated outputs rejected.

## The change

`t/spec_first.py --oracle-gate`: after the three-test scoring (which stays recorded), every parsed candidate of
a problem with a tested Python solution is judged by `spec_gate.judge` with that Python (100 draws, no larger
inputs); the candidates that pass are the kept ones, most complete first, at most `--per-problem`. Nothing
else in the route changes. Default off: the frozen route is byte for byte what it was.

## Arms (v5, desktop, caches seeded from the control and the twenty-candidate run; graded in the kernel container)

- O17: the frozen budget with the oracle gate (`--python 3 --spec-samples 4 --per-problem 3 --samples 2 --oracle-gate`), tag `v5-20261021-oracle17`.
- O39: ten Python attempts and twenty candidates with the oracle gate (`--python 10 --spec-samples 19 --per-problem 3 --samples 2 --oracle-gate`), tag `v5-20261021-oracle39`; every stage-1 call is a cache hit, only the proof asks are new.
- Control: `v5-20261021-dev-desktop` (51 / 13 / 6 / 3), already graded.

## Predictions, with the numbers that falsify them

- **P1 (the gate at the frozen budget).** O17: problems with a kept specification at least 18 with fewer
  wrong ones among them, answered at least 14, clean at least 7, all-seven at least 3, no control problem lost.
  Clean 6 or fewer, or a lost problem, falsifies it.
- **P2 (the budget).** O39: kept at least 26, answered at least 18, clean at least 10, all-seven at least 5.
  Clean 9 or fewer falsifies it.
- **P3 (the oracle's own error).** Of the specifications the oracle keeps, at most 20% are removed by the grader's
  reference check (the student's Python can be wrong beyond the three tests). More than 20% falsifies it and
  prices the Python stage's own correctness.

## What decides the next row

P1 holds: the oracle gate replaces the three-test gate in the route of record (a release change with no
training). P2 holds: the budget curve is recorded and the 39-call point becomes the product's default where
time allows. P1 and P2 fail: the proof stage is the bottleneck for right specifications and the next row is
there. The training-side row for the absent half of the problems proceeds regardless.

## Result (2026-10-21 07:54Z): the gate alone changes nothing at 17 calls; the gate with the budget gains one clean answer at 39

Both arms generated on the desktop (stage-1 calls replayed from the control's and the twenty-candidate run's
caches), graded in the kernel container, paired by `t/recipes/v7_local_pair.py` (receipts
`release/evidence/v5-oracle17-2026-10-21.json`, `v5-oracle39-2026-10-21.json`). The evaluator records differ
from the control's grade in two files only, `t/spec_first.py` and `t/test_spec_first_oracle.py`, neither in the
grading path; a control re-grade under the current tree is queued so the receipt's own flag can say so.

| arm | Python | kept spec | answered | verified before the specification check | clean | all seven |
|---|---:|---:|---:|---:|---:|---:|
| control (three tests, 17 calls) | 51 | 18 | 13 | 8 | 6 | 3 |
| O17 (oracle gate, 17 calls) | 51 | 16 | 10 | 7 | 6 | 3 |
| O39 (oracle gate, 39 calls) | 63 | 28 | 16 | 9 | **7** | 3 |

- **P1 falsified.** At the frozen budget the oracle gate keeps 16 problems (18 before): it drops six
  specifications the three tests kept, every one of them "false at the Python's answer" and none of them clean
  under the control (186, 207, 337, 620, 67, 829), and it admits four right ones the three tests had dropped
  (621, 861, 864, 892), none of which the proof stage then converts in three attempts. Clean 6, the control's
  six problems, nothing lost.
- **P2 falsified, with the first gain of the day.** O39: 16 answered, clean 7, gained 270
  `sum_even_and_even_index` (Verus and Frama-C verify it, twin refuted), nothing lost; all-seven 3, the
  control's three. 150 `does_Contain_B` verifies under all seven kernels and is removed by the specification
  check again: the student's Python agrees with its wrong specification on negative inputs, so the oracle
  cannot see the error (the limit Clover states: an edge case the code, the tests and the specification all
  miss).
- **P3 falsified, narrowly.** The grader's reference check removed 2 of the 9 oracle-kept specifications that
  verified (150, 459; 708 has no twin): 22%, against 20% registered. The student's Python is wrong beyond the
  three tests about one time in five, and the oracle inherits that.

Reading. The oracle gate is a precision instrument (7 of 7 kept-and-verified at 17 calls are confirmed or
abstained, against 6 of 8 under three tests), not a recall one; the gain comes from the budget, and the budget's
gain is bounded by the proof stage, which converts 16 of 28 right specifications into an accepted answer and
7 of those 16 into a clean one. The route of record stays at 17 calls under the three-test gate until a
candidate meets the bar there. Two things follow: v7 (the decomposed-rows model, whose annotation sub-skill
is the proof stage's) under the same O39 route, running now; and the training-side row for the absent half of
the problems, with the Haiku scout's list `internal/research-2026-10-21/spec-skill-scout.md` read first.
