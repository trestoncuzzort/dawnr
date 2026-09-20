# Does specification completeness explain proven-but-wrong?

Registered before the measurement runs. The check itself is committed and its
soundness output is verified unchanged; what is untested is whether the new
number means anything.

## The claim under test

Every locallm round produces a large population of **proven but wrong** answers:
204, 91, 117 and 59 in rounds 4, 7, 7b and 8. All seven verifiers agree the
program satisfies the specification the model wrote, the sabotaged twin is
refuted, and the problem's own tests fail. The hypothesis, from
[arXiv 2603.17150](https://arxiv.org/html/2603.17150v1) and
[arXiv 2608.13077](https://arxiv.org/html/2608.13077), is that those
specifications are **weak**: true of the right answer and true of wrong answers
too, so proving them proves nothing about the problem.

`t/spec_check.py` now measures that directly. For each draw where the ensures
accepts the reference output, it mutates the output and asks whether the ensures
still holds. `completeness` is the fraction of wrong answers the specification
rejects; `weak` is true when it accepts any.

## The measurement

`python3 t/spec_check.py <tag> --pool v5 --n 100 --only all` over answer sets
already graded on the lab, then split each set's answers into two populations
using its existing `kernels.md` and `tests.json`:

- **clean**: tests pass and all seven verified with the twin refuted
- **proven but wrong**: all seven verified with the twin refuted, tests fail

Sets with enough of both to compare: `locallm-r7b-greedy` (149 well formed, 117
proven but wrong, 2 clean), `locallm-r4` (209, 204, 2), `locallm-r8` (142, 105,
2), `locallm-r7b-headed2` (91, 59, 3).

## Predictions

1. **Proven-but-wrong answers are weak at least three times as often as clean
   ones**, pooled across those four sets. Falsified below 3x. This is the claim
   that the metric explains the population.
2. **Mean completeness is lower for proven-but-wrong than for clean** in every
   one of the four sets individually. Falsified by any set where it is not.
3. **At least 20% of proven-but-wrong answers are weak.** Falsified below 20%,
   which would mean most of them write a strong specification of the wrong
   function rather than a weak one, and the fix is different.

## What each outcome means

If 1 and 3 hold, the training gate gains a completeness requirement and the
pool stops teaching the model that a weak specification is acceptable, which is
the filtering result [arXiv 2603.17150](https://arxiv.org/html/2603.17150v1)
reports as 3.6x proof accuracy for Auto-Verus.

If 3 fails, the population is *strong specifications of the wrong function* —
the model understood the problem incorrectly rather than specified it lazily —
and the fix is the prompt-example arm already implemented
(`internal/RESEARCH-NEXT-2026-09-20.md`), not a gate.

Either answer is worth the twenty minutes of CPU this costs, which is why it is
registered before it runs rather than after.

## The caveat that stays attached

A problem with more than one right answer can accept a mutated output
legitimately. `weak` is evidence with a witness, not a verdict, and any gate
built on it must be measured against the pool it would have rejected.
