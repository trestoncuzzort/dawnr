# Prediction: per-person adapters (DAWNR-LEARNING.md), registered 2026-09-27 before the measured runs

Written and committed before any registered run starts (AGENTS.md rule 3).
What is measured and how is `locallm/dawnr_learning/measure.py`; the numbers
will be read by `locallm/dawnr_learning/summarize.py` from the run directory.

## What already ran (pilots, declared, not results)

Four pilot runs on the pilot person `eve` only (cur-snake names, no
semicolons, 4 spaces, if expressions, an Approach line, the tool shown), with
another problem order (`--problem-seed 99`), 2 or 3 sessions of 6 prompts, 6
train-side held-out prompts plus the 33 validation-side ones, 5 dev problems.
They exist to find bugs and choose the learning rate; `eve` is not part of any
registered result.

| pilot | style loss, held-out (base 2.42) | adherence (base 0.11) | answers passing the t tool (base 22 of 39) |
|---|---|---|---|
| lr 1e-3, no behaviour guard | 0.46 | 0.62 | **5** |
| lr 3e-4, behaviour guard | 1.78 | 0.12 | 23 |
| lr 1e-4, behaviour guard | 1.97 | 0.12 | 22 |
| lr 1e-3, behaviour guard | the first check (step 10) passed 2 of 8 guard prompts against the base's 7: refused | | |

What they bought: the behaviour guard (a loss of 0.46 on the person's style
sat beside 5 of 39 correct answers, so a loss alone cannot decide what to
keep), and the default learning rate 3e-4.

## The registered runs

Base: the chat mid-trained r12 core of the repair study's arm A seed 1337
(`ckpt.pt` sha256 5428768260c083e278b0e89720970e538793a92bbc4b41a838ebfa5b6fd58ddf,
92.9M parameters), its own conversations (sha256
6fa73333ccf1ea657fedb3a18b28f4eb8f03a239d2191f5422139078aab3a220: 325
training-side, 33 validation-side), the core's validation text as the
plain-code guard (sha256 c73c6af8f3fcdbdefc93babcfa536cf81bc2eb818b3732a01bb191068e0c31be).

Persons `ada`, `bo`, `cy`, `di` (persons.py). Four sessions of ten prompts,
twenty training-side held-out prompts (the fixed probe of the learning curve),
the validation-side conversations every person can write, eight behaviour-guard
prompts, 100 dev problems; problem seed 0; greedy, 640 new tokens; rank 8,
alpha 8, dropout 0.05, 25% replay, batch 8, 10 epochs (30 to 300 steps), a
check every 10 steps, patience 4.

| arm | learning rate | behaviour guard | seeds |
|---|---|---|---|
| A (the default) | 3e-4 | 8 prompts, at most 1 fewer pass than the base | 1, 2 |
| B | 1e-3 | none (the plain-code guard stays) | 1 |

## Predictions, each with the number that falsifies it

Arm A:

1. **The adapter fits its person.** Held-out loss of the person's own version of
   the reference answers is lower with their adapter than with the base for all
   4 persons in both seeds, with a median relative reduction of at least 20%.
   Falsified by any person-seed at or above the base, or a median under 20%.
2. **It is personal, not just any fine-tune.** On each person's style, that
   person's adapter has the lowest loss of the four adapters in at least 7 of
   the 8 person-seeds. Falsified at 6 or fewer.
3. **It does not change what dawnr writes much.** Adherence of greedy held-out
   answers to the person's preferences rises by less than 0.1 over the base for
   at least 3 of 4 persons in each seed. Falsified if 2 or more persons in a
   seed gain 0.1 or more (which would be the better outcome).
4. **dawnr does not get worse.** Answers passing the t tool on the held-out
   prompts: at least the base's count minus 3 for all 8 person-seeds; dev
   problems at least typed: at least the base's minus 5 for all 8; plain-code
   loss at most the base's plus 0.05 for all 8 (the guard enforces the last,
   so it checks the guard, it is not a finding). Falsified by any person-seed
   outside these.
5. **The behaviour guard acts.** At least 4 of the 32 sleeps of arm A end with
   the behaviour guard stopping them. Falsified at 3 or fewer.

Arm B:

6. **The style is adopted.** Adherence rises by at least 0.2 over the base for
   at least 3 of 4 persons. Falsified at 2 or fewer.
7. **Correctness collapses.** Answers passing the t tool on the held-out
   prompts fall by at least 5 below the base for at least 3 of 4 persons.
   Falsified at 2 or fewer.
8. **The person's cost goes up, not down.** Mean held-out edit cost is higher
   than the base's for at least 3 of 4 persons (a wrong answer is rewritten
   from the reference in full). Falsified at 2 or fewer.

Reported whatever they show: every number above, the per-feature adherence,
the cross matrix, the learning curve on the fixed probe after each sleep, each
sleep's guard decisions, and the canonical validation loss (which a style
legitimately raises, so it is reported and not judged).
