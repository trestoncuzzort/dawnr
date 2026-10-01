# Several answers a problem, and a second try after the gate's message: registered 2026-10-01 04:28Z

## Why, and what it stands on

One greedy answer per problem is the hardest way to use a model behind a gate. The gate makes
sampling safe: a wrong answer does not pass it however many are tried, so a problem can be asked
several times and the first proved answer kept. SAFE measures exactly this (arXiv:2410.15756,
4.2 and table 8, read from the HTML on 2026-10-01): Accuracy@1 is greedy; Accuracy@10 samples ten
outputs at temperature 0.7 and counts a task if any verifies; with self-debugging one more
sample is drawn from each failed answer and the verifier's message. Its 1.3B backbone after three
rounds reads 21.58 at one answer, 40.29 at ten and 27.34 with one debugging step.

Our shelf (`internal/research/r12-2026-09-21/inference-lit.md`) fetched the same result from the
code-generation side: Codex-85M 8.22 at one sample, 12.81 at ten; filtering samples on the visible
examples is the largest single gain (CodeT, APPS introductory 29.3 to 43.6). That plan was written
for the from-scratch model and never run on a pretrained student.

## The measurement

- **Model.** Qwen3.5-4B fine-tuned on the v4 rows (training now; the base the rule named), merged.
- **Problems.** The 100 dev problems. Nine cannot be passed by any task
  (`t/PREDICT-2026-10-01-base-model-selection.md`), so every count is of at most 91.
- **One answer.** Greedy, as every student so far (prompt `s1`, 1,024 new tokens).
- **Ten answers.** Ten sampled answer sets, temperature 0.7 (SAFE's), top-p 0.95 (ours: SAFE
  states none), seeds 1 to 10, decoded in batches by `t/student_generate.py`. Every answer is
  extracted and run on its problem's tests. Only answers that pass the tests go to the seven
  kernels (an answer that fails them counts at no level), then the specification check.
- **A second try.** `t/student_loop.py`: the greedy answer; where it does not pass parse,
  well-formedness and the tests, the gate's own message goes back with the attempt, in the words
  the 788 debugging rows used, and the student answers again, greedy; two such rounds. The
  kernels are not consulted inside the loop. The problem's tests are in the prompt already, so
  hearing which one failed tells the student nothing the question did not.
- **Instruments.** The repaired harness and specification check
  (`t/PREDICT-2026-10-01-spec-check-coverage.md`), for every arm alike.
- **Counting.** A problem counts at a level when some answer of the arm passes its tests, is
  proved by that many kernels with none refuting, and its specification agrees with the
  reference (`t/score_levels.py`, pooled over the arm's answer sets).

## Predictions

20. With ten answers the student passes the tests on at least one and a half times as many
    problems as with one. Falsified below 1.5 times.
21. With ten answers at least 2 more problems are proved by at least one kernel with the
    specification checked than with one. Falsified by fewer than 2 more.
22. The second try helps: after two repair rounds at least 1 problem passes the tests that the
    greedy answer failed. Falsified by none. (Our own record says a small model does not act on
    a parser message, `internal/ROADMAP-LOG.md` on the September rounds; SAFE says a model
    TRAINED on debugging pairs does. This student was.)
23. Ten answers beat the second try: more problems pass the tests with ten samples than after
    two repair rounds. Falsified otherwise.
