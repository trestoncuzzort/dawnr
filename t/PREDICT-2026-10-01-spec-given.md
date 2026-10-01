# The specification given: does a small student prove it? Registered 2026-10-01 02:42Z

## Why this, and what it stands on

Three bases from 1.5B to 4B, fine-tuned on 527 proved answers, each pass the tests on 4 of 100
dev problems and have 1 proved, specification-checked answer; 57 of 68 valid tasks the first two
wrote carry a specification that contradicts the problem (`t/PREDICT-2026-10-01-base-model-
selection.md`). The failing step is writing the specification from English.

Every published positive result read for this project supplies the specification: SAFE
(arXiv:2410.15756, a fine-tuned 1.3B backbone, 21.6% with one answer), AlphaVerus
(arXiv:2412.06176, "given only the specifications", 33% of Verified-HumanEval with a 70B model
and no fine-tuning), the vericoding benchmark (arXiv:2509.22908, 82% Dafny, 44% Verus, 27% Lean
with frontier models). None has a small model write the specification from English. So the
setting with a ladder under it is this one, and it has never been measured here.

What is ours and not theirs: a 2B student, 476 training examples where SAFE had thousands, and a
language none of these models had seen before tonight. Those are reasons to expect less.

## The held-out questions

`t/student_rows.py` (8f66e69b) on the r12 corpus, the project's own document split (hash,
`--split-seed 1338`, the seed the round registered): 476 documents train, 55 held out. Removed
from the 55: 14 whose problem has an answer in the English or debugging rows, 6 that are a
training document's program under another name, 2 that share a training document's
specification. **33 remain**: 19 lifted from the vericoding sources, 14 others; 15 are recursion
tasks, 11 have a loop, 15 have a spec fun. Checked on the built files: no training row of any
kind has a held-out program as its answer.

Limits, stated before any answer: 33 questions and one answer each, so two or three questions
are noise; the removal of overlaps is textual (the task's name normalised) and
`t/behavioural_decontam.py` was not run; these are lifted programs, a different mix from the
MBPP dev problems.

## The measurement

- **Student.** Qwen3.5-2B fine-tuned by `t/student_sft.py` (925c7734: the corrected loss) on
  `sft-student-v4.jsonl`, 1,791 rows: the 527 English rows with the task named as the prompt asks,
  476 specification-given rows from the train side, 788 debugging rows. Five epochs, rank 64,
  constant 2e-4, seed 1.
- **Matched control.** The Qwen3.5-2B student already trained on the 527 English rows alone
  (same base, same loss reduction, same prompt): it knows `t` and has never seen a
  specification-given question. The difference between the two is the training data.
- **Floor.** The untrained Qwen3.5-2B asked the same questions under the v5 system prompt (it has
  to be told the language; the prompts therefore differ, and this is a floor, not a control).
- **Asking.** Each of the 33 questions once, greedy, one at a time (no batching, so padding
  cannot move a near-tie token), 1,024 new tokens.
- **Scoring.** `t/spec_given.kept`: the answer must carry the question's name, parameters,
  results, requires, every given ensures and every given spec fun unchanged (cc0f3f64; an answer
  that redefines a given spec fun is refused). Kept answers that are well formed go to all seven
  kernels on the lab. Proved at level k: at least k kernels read `verified / refuted` and none
  refutes the program.
- **Also.** The v4 student answers the 100 dev problems as the earlier students did, through the
  same gate, to see whether the added rows change the English result.

## Predictions

9. The v4 student keeps the given specification on at least 25 of 33. Falsified below 25.
10. It is proved by at least one prover on at least 5 of 33. Falsified below 5.
11. The specification-given rows matter: it proves at least 3 more of the 33 than the matched
    control. Falsified otherwise.
12. On the 100 dev problems it passes the tests on at least 3 (the control passes 4): the added
    rows do not harm the English task. No gain is predicted there; nothing in these rows teaches
    writing the specification. Falsified below 3.

Tonight's record on predictions is five wrong, most of them too hopeful. These are set where a
miss in either direction is informative.

## Amendment, 2026-10-01 02:52Z, before any held-out question was asked: two counts, and a ceiling

**Both a name-strict and a name-normalised count are reported for every arm.** The scoring path
was exercised end to end on three TRAINING-side specification-given rows with a model that is not
in this registration (the English-only 1.5B student, on the CPU); no held-out question has been
asked of any model. One of its answers named the task differently from the question. Under the
registered rule that is "the specification was changed" and the answer stops there. The matched
control here was trained on answers that carry an invented `mbpp_<number>__` prefix (the earlier
students wrote one on 99 of 100 answers), so it may fail that gate on naming alone, and
prediction 11 could then hold because of a naming habit rather than because the
specification-given rows teach anything about proving. So `t/score_spec_given.py prepare` gains
`--normalise-name`: the answer is renamed to the question's task name, self-calls with it, before
the specification is compared. Tested: a redefined spec fun is still refused with the name
normalised. In the case that prompted this the answer had also changed the `ensures`, and it is
refused either way.

The predictions stay as written and are judged on the name-strict count, as registered. The
normalised count is printed beside it for each arm, and a prediction that holds on one count and
not the other is reported as exactly that.

**The ceiling is measured first.** The 33 questions' own corpus answers go through the same
scorer and the same seven kernels on the lab (started 02:46Z). Whatever they score is the most
any model can score on this instrument today; it is reported before any model's number. A row
the grader can build no sabotaged twin for is not run by the grader at all (`no-twin` in every
cell): it is counted apart as a missing measurement, not as unproved.

## The ceiling, measured 2026-10-01 02:54Z (before any model's answer)

The 33 questions' own corpus answers, passed through `t/score_spec_given.py` as if they were a
model's replies and then through all seven kernels on the lab (`--no-cache`, 4 cells, 6 minutes
42 seconds, 231 cells, 1,386 kernel runs, every verdict measured today):

| stage | of 33 |
|---|---:|
| a task block found, parses, carries the given specification, well formed | 33 |
| no sabotaged twin could be built (not graded) | 0 |
| a kernel refutes the program | 0 |
| no row came back | 0 |
| proved by at least one kernel | 33 |
| proved by all seven | 33 |

All 231 cells read `verified / refuted`. So the instrument can award 33 of 33 at every level, the
strict specification gate stops no correct answer, and the path from an answer to a level works
on answers known to be right. This is the ceiling for the reference bodies: a correct answer with
a different body can still time out in a kernel and land at a lower level, which is a fact about
proving it and not about the scorer.

## Amendment, 2026-10-01 03:10Z, before any model's answer: the order of the run, and a 4B arm

No held-out question has been asked of any model yet (the 2B is still training).

**Order.** The three arms are asked back to back under one hold of the card, and their kernel
runs then go to the lab together (4 cells each), where the first driver asked and graded one arm
at a time. The asks and the scoring are unchanged; the card is free about half an hour sooner.

**A 4B arm.** At 03:02Z the base-selection rule named Qwen3.5-4B the base
(`t/PREDICT-2026-10-01-base-model-selection.md`: 3 proved, specification-checked answers of 100
against 1 and 1, not separated statistically). It is trained on the same v4 rows with the same
recipe and seed, with one difference forced by the 16 GB card: rows longer than 2,845 tokens (the
longest the 4B has already trained on inside the card's memory) are dropped, 7 of 1,791. It then
answers the same 33 questions and the same 100 dev problems through the same gates. It starts
when the card is free, about 03:55Z, and takes about 80 minutes.

Predictions for the 4B arm, set before the 2B's results are known:

13. On the 33 questions the 4B on v4 is proved by at least one prover on at least as many as
    the 2B on v4. Falsified if it proves fewer.
14. On the 100 dev problems it reaches a valid task on at least 40 (the 4B on the 527 rows: 35).
    Falsified below 40.
15. On the 100 dev problems it has at least 3 answers proved by at least one prover with the
    specification checked (the 4B on the 527 rows: 3). Falsified below 3.
