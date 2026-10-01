# Specification repair with the gate's own witness: registered 2026-10-01 09:49Z

## Why, and what it stands on

The gate's specification stage (`t/PREDICT-2026-10-01-gate-without-reference.md`) refuses an
answer whose specification is false at the answer of the Python written beside the question, or
does not pin that answer down, and when it refuses it holds a concrete witness: the input, the
right output, and the clause that fails or the wrong output that is also accepted. Until now
that witness was thrown away.

- VeriMed (arXiv:2605.13817, HTML read 2026-10-01): repairing a model's formal answer with the
  solver's concrete counterexample in the prompt reaches 98.5%; a generic retry 58.5%; naming
  the violated requirement 80.0% (65 questions, up to five iterations). "The counterexample, not
  solver feedback in general, is what drives repair."
- SpecSyn (arXiv:2604.21570): a specification is strengthened by feeding back the mutated
  variants it fails to discriminate.
- SAFE (arXiv:2410.15756, 3.3): the gain from self-debugging comes from training on (attempt,
  checker's message, fix) triplets.
- Our own record: handed the gate's generic message, the fine-tuned 4B repaired 1 answer of 91
  (`t/PREDICT-2026-10-01-several-answers.md`, prediction 22).

## What is built

- **Rows** (`t/debug_rows.py --verdicts`): an earlier answer to a training problem that passes
  its tests on a wrong or weak specification, the witness in words, and the admitted answer as
  the fix. From today's training answers: 116 rows over 75 problems (70 wrong, 46 weak). No
  student has been trained on them; they go into the next row set.
- **The loop** (`t/spec_repair.py`): the test-passing answers of a route; what the stage passes
  is carried over; otherwise the first answer with a witness goes back in the rows' own words,
  one greedy repair and two sampled a round, two rounds; a repair is kept when the stage passes
  it. No reference solution is used. The answer set that comes out goes to the seven kernels and
  the reference check like any other.

The message, as the student sees it:

    It passes the tests, but its specification does not pin the answer down. For
    remove_upper('d') the answer is 'd', and the specification also accepts ''.

    Write the corrected task.

## The baseline, measured now

The 4B on v4 has never seen such a message (its 788 debugging rows carry parser, test and prover
messages). It is asked anyway, so the trained student has something to be compared with: the
4B on v4 at 4 bits on a CPU, the 100 dev problems, every test-passing answer of its dev sets as
candidates, the base model's Python beside each question (72 of 100). Counted before anything is
sent: 17 dev problems have a test-passing answer; 3 pass the stage untouched; 12 have a witness
to send back; 2 have none (one has no Python, one witness does not render).

49. Untrained on the witness, the student repairs at most 2 of the 12 (the stage passes a
    repair). Falsified by 3 or more.
50. No repair it does produce is refuted by a kernel or disagrees with the reference: the stage
    does not let a wrong repair through. Falsified by any repaired answer that the reference
    check calls wrong.
