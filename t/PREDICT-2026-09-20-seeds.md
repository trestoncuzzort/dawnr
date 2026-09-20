# Seed predictions: is 3 clean a property of the recipe, or of one seed?

**Written 2026-09-20, before any r9 table was assembled.** The kernel cells for
`locallm-r9` and `locallm-r9-seed7` were computed on 2026-09-19 and left in
`/dev/shm/tup-grade/<tag>/kernels/`; `kernels.md` was never written for any of
the three arms, so no r9 number has been read by anyone. `t/out/` contains no
`score-r9`. This file exists because the handoff said these arms had no
registration and that someone should write one before reading their numbers.

## What is being measured

Three arms, one recipe: heads on the specification-checked pool, greedy
decoding, 232 held-out problems.

| arm | pretrained core |
|---|---|
| `locallm-r9` | seed 1337 |
| `locallm-r9-seed7` | seed 7 |
| `locallm-r9-seed42` | seed 42 |

They exist to answer **attack 3** on the headline: the tie with Phi-4-mini rests
on a single run of a single seed, and three answers is thin enough that a lucky
draw is a live explanation.

## The baseline they are measured against

From `t/out/score-r8.md`, same evaluator, same 232 problems:

| arm | well formed | tests pass | clean |
|---|---:|---:|---:|
| `locallm-r7b-headed2` (the headline) | 91 | 3 | **3** |
| `locallm-r8` | 142 | 2 | 2 |
| `locallm-r7b-greedy` | 149 | 2 | 2 |
| `phi4-mini-eval2-2026-09-19` | 12 | 6 | **3** |

## Predictions

1. **At least one of the three r9 arms scores 3 or more clean.** Falsified if
   all three score 2 or fewer. If the recipe cannot reproduce its own headline
   once in three tries, the tie was a draw from a distribution rather than a
   property of the method, and the README's claim needs the caveat sharpened
   rather than removed.
2. **Not all three score 3 or more.** Falsified if every arm reaches 3. Two
   clean answers separate every locallm arm measured so far, and at n=3 per arm
   the counting noise is comparable to the effect; unanimity would be a
   stronger result than anything else this project has produced and should not
   be assumed.
3. **The spread between the best and worst arm is at most 2 clean answers.**
   Falsified at a spread of 3 or more. This is the prediction that actually
   matters: a spread of 3 on a headline of 3 means the seed dominates the
   recipe, which is exactly what the factorial study found for the composition
   curriculum, where "the seed moves the score more than the treatment does".
4. **Every clean answer survives `spec_check.py`.** Falsified by any clean r9
   answer that disagrees with its problem. Every locallm arm in the table above
   is 100% on this column and Phi is not; it is the one column where this
   project is ahead, and a regression there costs more than a clean answer.
5. **Well-formed counts land between 80 and 160** for all three arms, the range
   every headed or greedy arm has occupied. Falsified outside it. A number
   below 80 means the splitter or a head is broken again, which has now
   happened three times and would be a bug report rather than a result.

## What would make me drop the headline

Prediction 3 is the one to watch. If the three arms come back at, say, 1, 3 and
4 clean, then `locallm-r7b-headed2`'s 3 is a sample from a wide distribution and
the honest statement is a mean with a spread, not "drew level with Phi". I would
rewrite `README.md` to report the mean across seeds and state the range, and
move the single-arm number to `SCOREBOARD.md` as one row among four.

If the arms come back tightly (say 2, 3, 3), the claim stands as written and
gains the seed evidence it currently lacks.

## What this cannot settle

Phi's 3 is also a single run. Nothing here reruns Phi across seeds, and Phi's
decoding was already greedy, so its number has no seed variance to measure in
the same sense. The comparison remains one arm of ours against one arm of
theirs; the seeds tell us about *our* stability, not about the gap.

---

## Note added 2026-09-20, after registration and before any table was read

The premise in "What is being measured" is wrong in one word. It says the three
arms share one recipe with the headline, "greedy decoding". The three r9 arms
do decode greedily: every one of their 232 records reads `temperature 0.0`.
`locallm-r7b-headed2` does not: all 232 of its records read `temperature 0.5,
top_k 20`, because `t/gen_fleet.sh` dropped the `--temperature 0` it was given
(see `CORRECTIONS.md`).

So these arms measure the seed variance of a greedy recipe, and the headline is
a sample from a 0.5 one. That makes prediction 3 harder to interpret, not
easier: a spread across greedy seeds says nothing directly about how much of
the headline's 3 was the draw. The honest reading, if the arms come back tight,
is that the RECIPE is stable under seed at temperature 0, and the headline's own
variance is still unmeasured.

The five predictions are left exactly as registered. Nothing here is changed to
fit what the numbers turn out to be.
