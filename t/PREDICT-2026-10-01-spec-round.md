# A specification round on training problems, from their own Python: registered 2026-10-01 08:02Z

## What this is

The proof round used up the right specifications that were on record: 273 training problems had
one and no admitted answer, and 31 of them are now in the pool. 2,035 training problems are left
with no admitted answer and no right specification anywhere in the record (1,871 APPS, 111 MBPP,
53 HumanEval). Every one of them has a Python solution and tests.

SAFE grows specifications the same way it grows proofs (arXiv:2410.15756, 3.2, read from the
HTML): the model is given a function's implementation and docstring, writes specifications, the
ones that hold on at least 80% of the test cases and reject at least 60% of mutated ones are
kept, up to three a function, and the kept ones train the next model. The student being trained
now (the 4B on v5) is the first here taught to do that step: 601 of its rows go from a problem,
its tests and its Python solution to the task with an empty body.

## The round

`t/spec_first.py --reference-python` on the 2,035 problems, with the 4B on v5: the problem, its
tests and its own Python solution in the prompt; one greedy specification and four sampled at
0.7. A specification is kept when it passes the test-based scores (`t/spec_quality.py`, 80% and
60%) and also agrees with the Python solution on at least 10 of 100 drawn inputs under the
repaired check; up to three a problem. Then, for each kept specification, the proof as a
specification-given question with the Python beside it (one greedy, two sampled), taken when it
parses, keeps the specification, is well formed and passes the tests; taken answers go to the
seven kernels and are admitted by `t/graded_pool.py`'s rule.

The reference check is used here because these are training problems and their solutions are
training material. The route refuses any problem outside the training side by name
(`--reference-python`, tested). Nothing here touches dev or the held-out 200.

What it yields, in order of how much there will be: specification rows (a kept specification is
a training example for specification writing whether or not it is ever proved), then problems
with a test-passing program, then admitted answers.

## Predictions

36. At least 200 of the 2,035 problems get a kept specification. Falsified below 200.
37. At least 60 get a taken answer. Falsified below 60.
38. At least 15 are admitted to the pool. Falsified below 15.

The record so far for scale: with no Python in view the 4B on v4 wrote a test-supported
specification for 9 dev problems of 100 in eleven tries; given a right specification for an
unsolved training problem it wrote a test-passing program six times in ten and a proof one time
in ten.

## Amendment, 2026-10-01 08:18Z, before the round has started: a kept specification must also be complete

The keep rule above asks that a specification agree with the Python solution on at least 10
drawn inputs. Agreement lets a weak specification through
(`t/PREDICT-2026-10-01-several-answers.md`, the correction of 08:16Z), and a weak specification
is the opposite of a training example for specification writing. So the reference filter also
asks that the specification reject at least 60% of the mutated outputs judged on those inputs
(`t/spec_first.reference_keeps`; SAFE's floor, arXiv:2410.15756 3.2), and admission to the pool
asks the same (`t/graded_pool.py`, `spec-too-weak`). Predictions 36 to 38 keep their numbers and
are judged under this stricter rule.


## Amendment, 2026-10-01 14:16Z, before the round has started: the student

The round was registered with the 4B on v5. The 4B on v6 will exist before the card is free for it
(it trains after the held-out reference, `t/PREDICT-2026-10-01-v6.md`), so the round runs with the 4B
on v6, and with the 4B on v5 only if v6 fails to train. Predictions 36 to 38 are unchanged.

## Amendment, 2026-10-01 19:13Z, before the round has generated anything: back to the 4B on v5

The amendment of 14:16Z moved the round to the 4B on v6. Measured since (`t/PREDICT-2026-10-01-v6.md`, part 3),
v6 is worse at both halves of the round's task: given a specification it proves 26 of 33 by all seven where v5
proves 28, and from tested Python it keeps a specification on 10 dev problems where v5 keeps 15. The round
runs with the measured-best student for it, the 4B on v5. Predictions 36 to 38 are unchanged.

## Amendment, 2026-10-02 02:10Z, after a failed start that asked nothing: eight long references left out

The round started at 02:05Z with the 4B on v5 and stopped on its first batch: the card ran out of memory
(15.28 of 15.57 GiB in use). Its batches of 16 are padded to their longest prompt, and one problem's reference
Python is 289,048 characters (an embedded data table). 8 of the 2,035 problems have a reference over 3,000
characters (4 over 10,000); the student trained on rows of at most 2,845 tokens and never saw such a prompt.
They are left out: 2,027 problems. No specification was written and no answer taken in the failed start.
Predictions 36 to 38 are unchanged. It reruns after the RL run's card work.

## Amendment, 2026-10-02 02:14Z, before any specification is kept: prompts capped, smaller batches

The rerun of 02:10Z was stopped by hand three minutes in, before writing anything: long problem statements
remain (prompts up to 59,345 characters; dev prompts are at most 1,019), and a batch is padded to its longest
prompt. Problems whose whole prompt (statement, tests and reference Python) is over 6,000 characters are left out
(12 more: 2,015 problems), and the round runs at batch 8 instead of 16. Predictions 36 to 38 are unchanged.
