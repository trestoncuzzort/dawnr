# The specification stage's ceiling at 4B: registered 2026-10-21 06:38Z, before the run

A diagnostic, not a candidate. The repair turn (t/PREDICT-2026-10-21-repair-turn.md) and two more samples both
left the clean count at 6 of 95, and the two candidates that passed the three tests and the kernels still failed
the problem. Before choosing between the training-side rows (self-distilled specification rows, teacher-written
rows, the dense reward) one number decides: does the student write a reference-correct specification at all
when given enough tries, or is the skill absent? The same run prices the Python stage's budget.

## The run

v5 (the installed release) on the desktop, the frozen route's stage 1 only (`--specs-only`), with `--python 10`
(ten Python attempts instead of three) and `--spec-samples 19` (twenty specification candidates instead of five),
tag `v5-20261021-spec20`, cache seeded from the control so the first three Python attempts and the first five
specification candidates are the control's own. No proofs are asked; no kernel runs.

Evaluation (`t/recipes/spec_ceiling.py`): every scored candidate of every problem is judged twice, by the
route's own SAFE gate (three tests, thresholds 0.8 and 0.6, the scores already in `scored-specs.jsonl`) and by
the reference check (`spec_check.check_task`, 200 draws against the problem's solution, mutant completeness at
0.6, the training-side keep rule `spec_first.reference_keeps`). The reference check is an evaluation
instrument here, never part of the route.

## Predictions, with the numbers that falsify them

- **P1 (the Python stage is under-budgeted).** At least 60 of 95 problems have a passing Python solution within
  ten attempts (51 within three). Fewer than 60 falsifies it.
- **P2 (the skill is present and under-selected).** Of the problems with a passing Python solution, at least half
  have a reference-correct specification among their twenty candidates. Under half falsifies it: the skill is
  weak, and more samples or a better selector cannot supply what is not there.
- **P3 (the three-test gate is precise).** At least 70% of the candidates the SAFE gate keeps are reference-correct
  (81% on 1,600 stored answers on 2026-10-01).
- **P4 (the selection gap).** At least 5 problems have a reference-correct candidate that the gate does not rank
  among its three kept, or keep at all. Fewer than 5 falsifies it.

## What decides the next row

P2 holds: the next row is on the selection and data side, self-distilled specification rows for training
problems (sample twenty, keep the reference-correct ones, the training-side instrument) and the student's own
tested Python as the inference-time oracle (`t/spec_gate.py` already passes it to `spec_check.check_task`), with
the budget moved toward the stages P1 and P2 price. P2 fails: the next row is teacher-written specifications
for the training problems (an MIT-licensed teacher, reference-checked) or the dense reward (queue row 3).
