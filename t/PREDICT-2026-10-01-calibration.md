# Does the student know when its answer is right? Registered 2026-10-01 10:26Z

## What this is

`AMBITION.md` lists "to know when it is right" with calibration not started. The gate is this
project's answer to that question: an answer is shown with a proof and what stands behind its
specification, or refused. This measures the other half the row names, the model's own belief
about its answer, against the gate's and the reference's verdicts, so the two can be compared on
the same answers.

## What it stands on

Kadavath et al., "Language Models (Mostly) Know What They Know" (arXiv:2207.05221, the paper's
text read 2026-10-01): the model is shown a question and a proposed answer and asked "Is the
proposed answer: (A) True (B) False"; P(True) is the probability on (A). They report AUROC
(chance 0.5), the expected calibration error over 10 equal-count bins, the Brier score, and the
accuracy of the answers the model calls true against all of them. "Calibration of P(True) is
relatively poor zero-shot, but it improves few-shot"; judging long-form answers (code) gains less
from extra context than short answers; small models' code samples are almost always wrong.

## The measurement (`t/self_eval.py`)

- **Judge**: the 4B on v4 itself, at Q8_0 (llama.cpp, the lab's CPU), in its own chat template,
  the assistant turn prefilled to "The proposed answer is: (", P(True) = p(A) / (p(A) + p(B))
  from the next token's probabilities.
- **Judged**: every valid task the same student wrote for the 100 dev problems in its eleven
  one-shot answer sets: 426 answers, shown under the name the question asked for.
- **Ground truth** (the instruments, not the model): RIGHT when it passes its tests, at least one
  kernel proves it and none refutes it, and its specification agrees with the reference and
  rejects at least 60% of mutated outputs. 25 of the 426 are right, on 3 problems; 95 pass their
  tests; the gate (tests, a proof and the stage with the base model's Python) shows 21, all right.
- **Two variants**: zero-shot, and four-shot with examples from training problems only (two right
  answers, one that fails its tests, one whose specification both the reference and the base
  model's Python call wrong; `t/self_eval.py` refuses a shot from a judged problem).

Limit, stated first: the 25 right answers sit on 3 problems, so a P(True) that only tracks how
easy a problem is can score well. The tests-pass label (95 answers over more problems) is
reported beside it.

## Predictions

54. Zero-shot, P(True) separates the right answers from the rest with AUROC below 0.75.
    Falsified at 0.75 or above.
55. Four-shot calibrates better: its expected calibration error is lower than zero-shot's.
    Falsified otherwise.
56. Neither variant does what the gate does: of the 21 answers each rates most likely true, fewer
    than 21 are right. Falsified if all 21 are right.
