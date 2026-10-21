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

## Result (2026-10-21 07:00Z, desktop generation, evaluation `t/out/v5-repair-20261021/spec-ceiling.json`)

Tag `v5-20261021-spec20`: 980 scored candidates for 63 problems (the generation's SAFE gate kept 29 problems).

| k (attempts or candidates) | 1 | 2 | 3 | 5 | 10 | 20 |
|---|---:|---:|---:|---:|---:|---:|
| Python passes the tests (of 95) | 40 | 43 | 51 | 56 | 63 | |
| a reference-correct specification exists (of 63 with Python) | 12 | 14 | 16 | 18 | 24 | **29** |
| the SAFE gate keeps something (of 63) | 8 | 11 | 14 | 19 | 23 | 29 |

- **P1 holds**: 63 of 95 within ten attempts (51 within three; the curve is still rising at ten).
- **P2 falsified, narrowly**: 29 of 63 (46%), under the registered half (32). The curve is still rising at twenty
  (26 at twelve, 29 at twenty).
- **P3 holds**: the SAFE gate's kept candidates are reference-correct 73 of 93 times (78.5%).
- **P4 holds**: 10 problems have a reference-correct candidate that the gate does not put among its three kept:
  for 8 of them (42, 319, 350, 745, 747, 861, 864, 892) the gate keeps nothing at all, and for 2 (92, 829) it
  ranks a wrong candidate above the right one.
- Reference verdicts over the 980 candidates: 574 disagree, 294 agree, 58 no valid draws, 42 refused by the
  interpreter, 12 without a t value for the reference result. Of the 29 problems with a right candidate, 12 had
  it at the greedy sample and 18 within five.

Reading. The skill is present for just under half the problems that have Python and absent for the rest; the
three-test gate loses a third of the problems that have a right candidate; and the route's budget sits where
both curves are steep (three Python attempts, five candidates). Two levers need no training and are measured
next as one route row (t/PREDICT-2026-10-21-oracle-route.md): the student's own tested Python as the gate's
oracle in place of the three tests (`t/spec_gate.judge`, already built for the product's gate), at the frozen
17-call budget and at a 39-call budget. The training-side row for the absent half (teacher-written or
self-distilled specification rows, reference-checked) follows, with a Haiku scout's list on that issue
(`internal/research-2026-10-21/spec-skill-scout.md`) read first.
