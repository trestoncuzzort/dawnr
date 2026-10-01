# The specification written first, with the student's own Python: registered 2026-10-01 04:49Z

## Why, and what it stands on

Measured tonight: given the specification, a fine-tuned 2B proves 19 of 33 unseen specifications
by all seven kernels; from English it proves 2 of 100, and 44 of the 50 specifications it writes
that can be checked are not the problem's. The step that fails is English to specification.

SAFE does not ask its model for that step cold (arXiv:2410.15756, 3.2, read from the HTML): its
specification model is given "the function's implementation and docstring", and its proof model
the function and the specification. The implementation carries the meaning. A student here has
no implementation to look at, in a language it has seen a few hundred examples of.

It does have one in a language it knows. Every problem in the pool comes with a Python solution,
and a pretrained model writes Python for problems like these without any training from us; a
Python solution can be checked by running the problem's tests. So the route is:

0. the student writes Python for the problem; it is run on the problem's tests inside a sandbox
   (`t/py_sandbox.py`: bubblewrap, no network, no home directory, no new processes; the shape is
   HumanEval's `execution.py`), and kept only if every test passes;
1. the student writes specifications from the problem, its tests and that Python (one greedy,
   four sampled at 0.7); each is scored on the problem's own tests by SAFE's two scores and kept
   at 80% Correctness and 60% Completeness, up to three (`t/spec_quality.py`: on 1,600 stored
   answers 81% of what these thresholds keep agrees with the reference);
2. each kept specification is put back as a specification-given question with the Python beside
   it (one greedy, two sampled), and an answer is taken when it parses, keeps the specification,
   is well formed and passes the tests;
3. the taken answers go to the seven kernels and the reference check like any others.

Translation from a language the model knows is the published way into one it does not:
MultiPL-T translates Python functions into a low-resource language with a code model, keeps a
translation only when translated tests pass, and fine-tunes on the tens of thousands of items
that survive (arXiv:2308.09895, abstract and section 4 read on 2026-10-01); AlphaVerus
bootstraps Verus from Dafny (arXiv:2412.06176). What differs here: they have tens of thousands
of validated items a language and we have a few hundred.

## Training rows

`t/spec_first_rows.py`, from every row of the graded training pool (training problems only; the
pool is rebuilt tonight with the answers that had never been graded): a `python` row (the
problem and its tests to its Python solution), a `spec` row (the problem, its tests and the
Python to the task with an empty body) and a `proof-py` row (the specification and the Python to
the finished task). They are added to the rows the v4 student had: the English rows (now under
prompt `s2`), the 476 specification-given rows and the 788 debugging rows. Same recipe and seed.

## The measurement

- **Pilot on the 2B**, because its v4 student is the matched control: same base, same recipe,
  rows differ. If the pilot's count beats the control's, the 4B (the base the rule named) is
  trained on the same rows next.
- The 100 dev problems (nine of which no task can pass), repaired harness and specification
  check, `t/spec_first.py --python 3`.
- Reported: problems with tested Python, with a kept specification, with a taken answer, and
  the levels table; beside it the same student's one greedy English answer through the same
  gate, and the v4 student's (53 valid, 5 tests, 2 proved, 1 by all seven).

## Predictions

26. The student's own Python passes the tests on at least 60 dev problems. Falsified below 60.
27. At least 20 dev problems get a kept specification. Falsified below 20.
28. At least 10 dev problems get a taken answer (the v4 student's greedy answers pass the tests
    on 5). Falsified below 10.
29. At least 5 dev problems are proved by at least one kernel with the reference check agreeing
    (the v4 student: 2). Falsified below 5.
