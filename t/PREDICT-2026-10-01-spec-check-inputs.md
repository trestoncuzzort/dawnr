# The specification check drew every input from the first example: repair and re-measurement, registered 2026-10-01 10:31Z

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
