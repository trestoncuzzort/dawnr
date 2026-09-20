# Diagnostic: can the baseline learn to compose at all?

Registered before the run. This is a **diagnostic pilot, not a registered
factorial**: one treatment, three seeds, run to find out whether the
measurement has any resolution before spending another twelve arms on it.

## Why

The factorial ([FINDINGS](FINDINGS-factorial-2026-09-19.md)) put baseline at 2
of 102 held-out tasks at all three seeds while treatments scattered from 1 to 9,
so the seed moved the score more than the treatment did, and a 5-point effect
was undetectable. Worse, every correct answer in all twelve arms was on a task
a proper sub-sequence of its own stages already passed. Before re-running any
factorial, the floor has to move.

## What changes, and what does not

One thing changes: the curriculum's size and parameter diversity.
`t/out/composition-2026-09-19-v5`, built with `--grid wide --variants 24`, has
309 training tasks against 81, 4139 training execution examples against 1094,
and 323 held-out tasks of which **0 are collapsible**: every one requires
composing all of its stages. The wider grid is the point: when `cap` can take
any of seven thresholds, writing a memorized stage stops working and reading
the contract in the prompt becomes the only way to score.

Unchanged: the four-arm code, the frozen modern 4000-step initializations, 4000
updates at batch 8, context 512, the greedy 200-token single-candidate
response, and the independent scorer. Only the `baseline` arm runs, at seeds
1337, 7 and 42.

## Predictions

1. **Baseline solves at least 15% of held-out tasks at every seed.** Below that
   at any seed falsifies it. The comparison point is 2% on the old curriculum.
2. **Baseline is above zero on the `eval_depth` split at every seed**, meaning three
   stage programs, longer than anything trained.
3. All three arms complete with finite losses.

## What each outcome means

If prediction 1 holds, the factorial is worth re-running on this curriculum,
because a treatment effect of a few points would then be visible against a
floor well above zero. If it fails, the blocker is upstream of any auxiliary
objective, whether the curriculum, the response format or the 91M core itself, and
running four more cells against a floor of zero would measure nothing. Either
way the result is reported, and no arm is dropped for its score.
