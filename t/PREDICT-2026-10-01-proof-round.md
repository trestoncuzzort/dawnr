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

## Amendment, 2026-10-01 05:28Z, before anything is asked: 63 more problems

The 298 were found among answers the specification check had already seen, and it sees only
answers that reached a kernel table. A scan of every other valid task in the training-side sets
(1,253 specifications of still-unsolved training problems that had never been checked, most from
answers that fail their tests) took a specification when it passes the test-based scores AND
agrees with the reference on at least 10 of 100 draws: 770 fall to the test-based scores, 335
disagree with the reference, 71 are taken, for 63 more problems. The round is now 273 training
problems and 352 specifications. Predictions 30 and 31 stay as written (their thresholds were
set for 210; they are now easier to meet by a quarter, and the outcome will say how many of each
count come from the 63).

## Amendment, 2026-10-01 07:01Z: a second pass on the problems the first pass left

The first pass (one greedy answer and two sampled for each of 352 specifications) took an
answer on 167 of the 273 problems: 135 on the greedy answer, 25 more on the first sample, 7 more
on the second. Those 167 are with the kernels now. Prediction 30 (at least 40 taken) holds on
the first pass alone.

The card is free for about three quarters of an hour before the next training can start (it
waits for these answers to be graded), so the 106 problems left get six more sampled answers a
specification, same temperature, as a second answer set (`round1b-proofs-4b-v4`). Same gates,
same admission rule. The falling yield of the first pass (135, 25, 7) says to expect few.

32. The second pass takes an answer on at most 20 of the 106. Falsified by more than 20.
