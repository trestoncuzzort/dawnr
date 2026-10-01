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

## Amendment, 2026-10-01 04:35Z, before the 4B on v4 exists: a third arm, the specification first

**What was measured since.** Given the specification, the 2B student proves 19 of 33 unseen
specifications by all seven kernels (`t/PREDICT-2026-10-01-spec-given.md`). From English it
proves 1 to 3 of 100, and what fails is the specification. SAFE splits the work the same way
(arXiv:2410.15756, 3.2 and 3.3, read from the HTML): specifications are synthesized first and
kept only when they score at least 80% Correctness (the share of the problem's test cases they
hold on) and 60% Completeness (the share of mutated test cases they reject), up to three a
function; proofs are then synthesized for the kept specifications. Neither score needs a
reference solution.

**Is that filter any good here?** `t/spec_quality.py` computes the two scores from a problem's
own tests. On 1,600 stored answers that have a reference verdict: of the 1,084 specifications
the thresholds keep, 875 agree with the reference (81%); of the 443 dropped for Correctness, 425
disagree (96%); of the 73 dropped for Completeness, 28 disagree. It keeps 92% of the right
specifications and drops 66% of the wrong ones, with no reference.

**The arm.** No new training: the same 4B on v4, used twice.

1. Specifications: every well-formed task among the problem's eleven one-shot answers (the
   greedy one and the ten samples) gives up its body and is scored on the problem's own tests.
   Up to three distinct specifications a problem are kept, the most complete first.
2. Proofs: each kept specification is put to the student as a specification-given question, in
   the words it was trained on, once greedy and twice sampled at 0.7. An answer is taken when it
   parses, is well formed, carries the given specification unchanged (`t/spec_given.kept`) and
   passes the problem's tests; the first such answer is the problem's.
3. Those answers go to the seven kernels and the reference check like any others.

The arm's count for a problem is the best level among its own answers and the eleven one-shot
answers it started from, so it can only add to the ten-answer arm; what it adds is the measure.

24. At least 15 dev problems have a kept specification among their eleven one-shot answers.
    Falsified below 15.
25. The arm adds at least 2 problems proved by at least one kernel with the reference check
    agreeing, beyond the ten-answer arm. Falsified by fewer than 2.

## Amendment, 2026-10-01 05:22Z, before any answer of the 4B on v4 is read: a fourth arm, retrieved examples

Misu et al. (arXiv:2402.00247, abstract and section 3.4 read from the HTML on 2026-10-01) put
178 MBPP problems to GPT-4 for verified Dafny with specifications: 19% with a bare prompt, 10%
with the signature and tests, **58%** when the prompt carried the five most similar solved
problems, retrieved from 50 hand-written solutions by embedding similarity, with a step-by-step
decomposition. Similar solved examples in the prompt are the published lever for writing the
specification, and retrieval is a row of this project's own table that was built (a BM25 index,
`locallm/dawnr_retrieval/`) and never put in front of a model that can use it.

**The arm.** The same 4B on v4, no new training. For each dev problem the five most similar
training problems with a proved answer are retrieved by BM25 over the problem text (the pool as
it stood at 04:57Z: 548 answers over 288 training problems; one answer a problem, the one proved
by the most kernels) and shown as five question-and-answer turns before the question itself,
each in the words the student was trained on. One greedy answer. Through the same gate.

What differs from the paper: BM25, not an embedding model; a fine-tuned 4B, not GPT-4; no
step-by-step decomposition; one answer, not five tries.

26b. With retrieved examples the student passes the tests on more dev problems than its plain
    greedy answers do. Falsified if it passes the same number or fewer.
27b. It is proved by at least one kernel with the specification checked on at least 2 more
    problems than the plain greedy answers. Falsified by fewer than 2 more.

(Numbered 26b and 27b: 26 to 29 are taken by `t/PREDICT-2026-10-01-spec-first.md`.)

## Amendment, 2026-10-01 05:38Z, before any dev result of the 4B on v4 is read: which route goes to the held-out 200

Five ways of using the same student are about to be measured on dev (one greedy answer, ten
answers, ten answers and the specification first, retrieved examples, a second try), and a
sixth may follow (the student's own Python first, `t/PREDICT-2026-10-01-spec-first.md`). The
held-out 200 is to be used once. The choice is fixed now so it cannot follow the numbers:

- **The route** is the one with the most dev problems proved by at least one kernel with the
  reference check agreeing; ties go to the route with more problems proved by all seven, then
  to the one that asks the model fewer times a problem. Routes that share answers are counted
  as registered (ten answers includes the greedy one; the specification-first arm includes the
  eleven it starts from).
- **The student** is the 4B on whichever rows it was last trained on when the route is chosen.
- **The held-out run** is that route, unchanged, on the clean 200, once, with the repaired
  instruments; every level is reported.
- **The reference** (section 1 of `AMBITION.md`) is Phi-4-mini prompted under v5, given the
  same number of answers a problem through the same gate, sampled the same way, graded the
  same day. Its single greedy answer on record reads 4 tests passed and 1 proved of 200.
- The route is a property of the system, not of the model: the reference gets every answer the
  budget allows, and no stage that needs fine-tuning on `t`.
