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
