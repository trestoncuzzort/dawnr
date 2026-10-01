# A proof round on training problems that already have a right specification: registered 2026-10-01 05:08Z

## What this is

SAFE grows its proof data by rounds (arXiv:2410.15756, 3.3 and algorithm 1, read from the HTML):
the fine-tuned model is given specifications it has no proof for, writes proofs, the verifier
keeps the ones that verify, and the kept ones train the next model. The stopped teacher round
would have had a larger model write whole answers. This round asks the student for the half it
has been measured to do: given the specification, a fine-tuned 2B proves 19 of 33.

## The material, counted before anything is asked

298 training problems (62 MBPP, 224 APPS, 12 HumanEval) have no admitted answer and DO have,
somewhere in the 98 graded training-side answer sets, a specification that agrees with the
problem's reference on at least 10 drawn inputs under the repaired check: answers whose program
or proof failed and whose specification is right. For 210 of them a specification also passes
SAFE's test-based scores on the problem's own tests (`t/spec_quality.py`, 80% and 60%); those
are kept, at most three a problem, 281 in all. The other 88 are left out: a specification the
problem's own tests do not support is not one to train on, whatever the drawn inputs said.

All 210 are training problems (none held out, none in the dev split); nothing here touches a
measurement set. The yield is a count of training rows, not a score.

## The round

The 4B on v4 (the base the rule named), `t/spec_first.py --given-specs`: each specification as
a specification-given question, one greedy answer and two sampled at 0.7; an answer is taken
when it parses, keeps the specification, is well formed and passes the problem's tests; the
taken answers go to the seven kernels and the repaired reference check, and the admitted ones
join the pool by `t/graded_pool.py`'s rule (at least one kernel, none refuting, the
specification agreeing on at least 10 draws).

## Predictions

30. At least 40 of the 210 problems get a taken answer. Falsified below 40.
31. At least 20 are admitted to the pool. Falsified below 20.
