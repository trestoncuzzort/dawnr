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

## Outcome of the baseline, 2026-10-01 10:22Z (read at 10:33Z)

The 4B on v4 at 4 bits, the stage's witness in the rows' words, two rounds of one greedy and two
sampled repairs. Of 17 dev problems with a test-passing answer, 3 passed the stage untouched (113,
377, 727), 2 had no witness, 12 were sent back:

| round | sent back | repaired (the stage passes it) | replaced by a repair with a new witness | refused before the stage |
|---|---:|---:|---:|---|
| 1 | 12 | 0 | 6 | 10 fail a test, 10 do not parse, 2 not well formed |
| 2 | 12 | 2 | 5 | 14 do not parse, 8 fail a test |

The two repairs, through the seven kernels and the reference check:

- **807 (first odd number in a list)**: six kernels refute the program. Not shown.
- **67 (the nth Bell number)**: five kernels prove it, and the reference check as it then stood
  called it right and complete. It is a lookup table, wrong for every n from 11 to 55. The
  check drew every input from the first example (n = 2), so no draw went past 4; that fault is
  repaired and registered in `t/PREDICT-2026-10-01-spec-check-inputs.md`, and under the repaired
  check this answer disagrees with the reference.

49. **The untrained student repairs at most 2 of the 12: holds, at exactly 2**, and neither is a
    right answer.
50. **No repair is refuted by a kernel or wrong by the reference: falsified.** 807 is refuted;
    67 is wrong, which only the repaired check sees.

**Reading.** Handed a concrete witness it was never trained on, the student does not use it:
nothing it wrote in two rounds is right. VeriMed's gain is a frontier model's; for this student
the witness has to be taught first (the 116 specification rows built today go into the next row
set). The baseline also did what a baseline is for: its one apparent success exposed a hole in
the instrument every count rests on.

## Amendment, 2026-10-01 15:20Z, before the 4B on v6 exists: the trained student

The 4B on v6 trains on 79 rows that answer a specification witness with the fixed task
(`t/PREDICT-2026-10-01-v6.md`). The same loop, unchanged, is put to it on dev: every test-passing
answer of its greedy and Python-first dev sets as candidates, the base model's Python beside each
question, two rounds of one greedy and two sampled repairs, on the card between its own dev
measurements and the specification round. The repaired set goes through the seven kernels and the
reference check like any other. Why now: scoring the 611 well-formed specifications the 4B on v5 wrote
on dev (greedy and ten samples) by SAFE's two thresholds, 358 contradict the problem's own examples
(correctness below 0.8, 70 problems), 125 are too weak (completeness below 0.6, 28), 74 are kept (20)
and 54 cannot be scored: the specifications are mostly wrong, not merely weak, and the witness is
the one signal that names how.

51. The 4B on v6 repairs (the stage passes it) at least a third of the dev problems that have a
    witness to send back.
52. At least half of the problems it repairs are right by the reference on a complete specification.
