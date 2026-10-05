# The specification check drew every input from the first example: repair and re-measurement, registered 2026-10-01 10:31Z

> **Correction, 2026-10-05:** counts on the clean 200 in this file include 18 problems that an audit of the training rows
> later took out of the panel. Every published row is restated on the clean 182 in
> [DECONTAMINATION-2026-10-05.md](DECONTAMINATION-2026-10-05.md).

## What was found

The specification-repair baseline (`t/PREDICT-2026-10-01-spec-repair.md`) produced one answer
the instruments call right: MBPP 67, "find the nth Bell number", tests at n = 2, 10 and 56. The
answer is a lookup table. Its `ensures` says only that the result is one of eleven numbers, and
for every n from 11 to 55 it returns the value for 56. Five kernels prove it. The reference check
read "agrees on 100 draws, 81% of mutated outputs rejected", and the gate's own stage passed it.

Two causes, both measured on this answer:

1. **Every draw is shaped like the problem's first example.** `spec_check.draw` keeps a drawn
   input near the example it copies (2026-09-18, so that unstated preconditions carry over), and
   the check always handed it the first assertion's arguments. Here that is n = 2, so every draw
   fell in [0, 4], where the table is right. This project found the same failure once before, on
   2026-09-25, in `t/relabel.py` (eight copies of a lookup table admitted as relabels), and fixed
   it there only, by rotating the examples; the main check was left as it was.
2. **The mutants are wrong outputs near the right one.** A specification that never ties the
   result to the input ("r is one of these numbers") rejects most of them (81% here).

## What it stands on

- EvalPlus (github.com/evalplus/evalplus, `gen/__init__.py` and `gen/mut_gen.py`, fetched
  2026-10-01): input generation is seeded with ALL of a problem's inputs
  (`self.seed_pool = copy.deepcopy(inputs)`) and each new input mutates `random.choice(seed_pool)`.
- nl2postcond (arXiv:2310.01831, read 2026-10-01): a postcondition's completeness is the share of
  buggy PROGRAMS whose outputs it rejects on the test inputs; a program that answers another
  question is the simplest such program.

## The repair (`t/spec_check.py`)

1. Each draw is shaped like a random example among all of the problem's points whose argument
   kinds match the first (a problem with one example draws exactly as before).
2. A second mutant family: for each draw inside the `requires`, the solution's answers to the
   three previous draws, where they differ from this draw's answer, are put to the `ensures` as
   wrong answers for this input. Reported apart as `cross_completeness`.
3. One rule reads both families (`spec_check.complete`): a specification is complete when every
   family measured rejects at least 60% (SAFE's floor). It replaces the single-family test in the
   levels scorer, the training pool, the gate's stage, the specification round's keep rule, the
   gate scorer and the self-evaluation labels.

On MBPP 67 each repair alone catches the table: with all examples seeding the draws the check
reads "disagrees"; with the old draws the other-input family rejects 0% (`t/test_spec_check_inputs.py`).

## Re-measurement, and what is predicted before it runs

Every verdict is recomputed, because the draws change for every problem with more than one
example: the dev answer sets (on this machine), the 37 pretrained answer sets of the clean-200
pooled table (on the lab), and the 1,038 proved training answers of the gate measurement.

57. The 4B on v4's dev count on complete specifications is unchanged: 4 problems (113, 377, 727,
    892) with ten answers and the specification first, 2 with one answer. Falsified if it moves.
58. The pretrained pooled count on the clean 200 on complete specifications (48 by one kernel or
    more, 19 by all seven) falls by at most 3 and at most 1. Falsified by a larger fall.
59. Of the 823 proved training answers the reference called right and complete, at most 41 (5%)
    are not right under the repaired check. Falsified above 41.

The held-out rule, the held-out run and the reference's run use the repaired check, since none
of them has started; the 4B on v4's numbers the rule compares against are re-read under it.

## Outcome, 2026-10-01 10:36Z

Every verdict recomputed under the repaired check. Where an earlier check had found an input at
which a specification is false and the task's contents are the same, that disagreement is kept
(`spec_check.keep_witnesses`: a counterexample does not expire because a later check drew other
inputs; EvalPlus grows a problem's tests and never drops one). That kept 2 dev verdicts and 15
held-out ones.

| | before | after |
|---|---:|---:|
| the 4B on v4, dev, complete specification: one answer / ten / ten and the specification first | 2 / 3 / 4 | **2 / 3 / 4** |
| the prompted 9B, dev, complete specification | 2 | **0** |
| the 2B on v4, dev, complete specification | 2 | 2 |
| pretrained pooled, clean 200, complete specification, by one kernel or more | 48 | **47** |
| the same, by all seven | 19 | 19 |
| proved training answers right and complete by the reference | 823 of 1,038 | **790** |

57. **The 4B on v4's dev counts do not move: holds.** The same four problems.
58. **The clean-200 pooled count falls by at most 3, and at most 1 at seven: holds.** By one
    (problem 482, "one upper-case letter followed by lower-case letters", loses its only counted
    answer), and none at seven.
59. **At most 41 of the 823 right training answers stop being right: holds.** 33 by this
    count (790 right after, with the disagreements kept).

**The prompted 9B's two dev answers were both input-blind.** Problem 186's specification says
the answer is "Matched!" or "Not Matched!" without saying which; it was counted at six kernels,
and every other input's answer satisfies it. Problem 543's says the result is the number of
digits of the first argument and ignores the second; draws shaped like the first example (9875,
10) never carried into a new digit, and draws shaped like the second and third do.

**The gate without a reference, outcome B, under the repaired check**: of the 1,038 proved
training answers, 790 are right (76.1%, was 79.3%); the stage shows 682 and 644 of them are right
(**94.4%**, was 94.0%), 81.5% of the right answers. Prediction 42 (at least 95%) stays falsified.
