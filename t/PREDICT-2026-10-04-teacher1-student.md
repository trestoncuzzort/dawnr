# The student on v3's rows plus the Bedrock teacher's documents, three seeds: registered before any of it trains

Registered 2026-10-04 01:30Z, while the teacher round's documents are still being graded
(`t/PREDICT-2026-10-03-teacher-round-bedrock.md`). RL left every unseen measurement where it was
(`t/PREDICT-2026-10-01-rl-on-the-student.md`, outcome), and every measurement since 2026-09-30 says the student
lacks documents that reach the top tier. This round adds the teacher's and changes nothing else.

## The rows (a rule fixed now; the counts are recorded when built, before training)

`~/scratch/bedrock/pool.sh`: v3's 4,027 rows (`sft-student-v5-0750-nogpl-k6.jsonl`, sha256 b2fbb089...) byte for
byte, then appended:

- the teacher's training documents the round admitted (clean in at least six kernels), through the pool's own
  route: `extract --promote-header`, `tests`, the seven kernels on the lab, the corrected specification check
  (1,000 draws, each task's own generator, MBPP+'s references), and `t/graded_pool.py`'s gates at one kernel and
  prompt s2 (the settings v3's graded rows were built with); then `t/spec_first_rows.py` on those rows;
- the teacher's specification documents the round admitted (clean in at least six kernels), as
  specification-given rows (`t/student_rows.py`'s `row_for`, source `teacher-spec`);
- with build_v5's checks: no row for a problem outside the training side, and no row whose program or
  specification (name normalised) is one of the 33 held-out specification-given questions.

## The training and the measurement

The shipped recipe's exactly (`t/student_sft.py`, Qwen3.5-4B at the snapshot v3 used, rank 64, five epochs, rows up
to 2,845 tokens), seeds 1, 2 and 3, on the lab (seeds 1 and 2 side by side on GPU 2, seed 3 on GPU 3 beside the
specification round). Each is measured on the clean 200 exactly as the shipped seeds are
(`t/PREDICT-2026-10-03-shipped-recipe.md`): `spec_first.py --python 3` (the Landlock sandbox on the lab),
`extract --promote-header`, `tests`, the seven kernels on the lab, the corrected specification check, scored
with `t/score_levels.py --min-completeness 0.6`.

## Predictions

- **S1.** Each seed proves at least 15 of the clean 200 on complete specifications at one kernel and at least 8
  by all seven.
- **S2.** The three seeds' mean by all seven is at least 1 above the shipped recipe's three-seed mean under the
  same instrument (its seed 1: 10).

Section 1's judgement is then made on these three seeds against Phi-4-mini under the grammar (9 at one kernel,
7 by all seven, same instrument): beaten when every seed is above it at both, doubled when every seed proves at
least 18 at one kernel and 14 by all seven. Either is reported as it falls.

## What it cannot show

The teacher has read the public MBPP and HumanEval and its training documents answer training problems, never the
clean 200 (their ids are excluded at the source, and the rows are checked again). A gain here says documents of
this kind help; it does not say which of the two kinds (training documents or specification documents) did it.
