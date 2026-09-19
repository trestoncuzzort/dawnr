# The floor did not move, so a factorial has nothing left to measure

Registered in [PREREG-learnability-2026-09-19.md](PREREG-learnability-2026-09-19.md)
before the run: one treatment, three seeds, run to find out whether the
factorial's measurement had any resolution left once its broken tasks were
removed. Output `t/out/learnability-2026-09-19`.

## What ran

`t/out/composition-2026-09-19-v5`, built with a wider parameter grid: 309
training tasks against 81, 4,139 training execution examples against 1,094, and
323 held-out tasks of which **0 are collapsible** -- every one requires
composing all of its stages. Baseline arm only, from the same frozen modern
4000-step checkpoints, 4000 updates at batch 8, same greedy single-candidate
response, same independent scorer.

## The result

| seed | eval_pattern | eval_depth | total | malformed / ill-formed | train seconds |
|---|---:|---:|---:|---:|---:|
| 1337 | 0 of 120 | 0 of 203 | **0 of 323** | 0 | 429 |
| 7 | 2 of 120 | 0 of 203 | **2 of 323** | 1 | 415 |
| 42 | 0 of 120 | 0 of 203 | **0 of 323** | 2 | 409 |

Individual tests tell the same story from closer up: 285 to 375 of 2,584
in-range tests pass, and 211 to 224 of the extrapolated ones, which is roughly
what writing *some* plausible program gets you. Whole tasks essentially never
come out right.

- **Prediction 1, at least 15% of held-out tasks at every seed: falsified**, at
  every seed, by two orders of magnitude at two of them.
- **Prediction 2, above zero on `eval_depth` at every seed: falsified.** Zero of
  203 three-stage tasks at all three seeds. Not one longer-than-trained program
  was ever produced correctly.
- **Prediction 3, three arms complete with finite losses: held.**

## What it means, stated as narrowly as the evidence allows

Quadrupling the training tasks and widening the parameter grid moved the score
from 2 of 102 to 0 of 323. The floor did not rise; removing the tasks that a
memorized single stage could pass took the score to zero and left it there.

So the blocker is upstream of any auxiliary objective **in this setup**, and
the setup is the whole of the claim: this initialization (the 91M modern
4000-step checkpoints), this curriculum, this budget, this one-greedy-candidate
decoding. Running four cells against a floor of zero would measure nothing, and
the factorial's null result is explained rather than merely reported: there was
no signal for a treatment to improve.

What follows is that **another factorial should be deferred**, not that the
curriculum is unlearnable or the direction is dead. Neither of those was
tested. A different initialization, a larger core, more candidates per task, or
a curriculum with a gentler gradient between its trained and held-out patterns
could each move the floor, and none of them has been tried.

What the run cost: 21 minutes of training for three arms. The pilot was worth
four minutes an arm precisely because the answer was this decisive.

## What it does not say

It says nothing about execution supervision in general, nothing about the
project's own pipeline data, and nothing about the seven-verifier gates. It is
one 91M core, one generated curriculum, one greedy candidate per task, one
budget. "Not learnable here, this way" is the whole finding; "not learnable" is
a different sentence that this run does not support.
