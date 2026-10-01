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
