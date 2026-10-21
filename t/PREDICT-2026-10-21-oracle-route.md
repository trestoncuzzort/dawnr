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
