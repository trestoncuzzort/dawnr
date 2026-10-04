# The student on v3's rows plus every document admitted so far, three seeds: registered before any of it trains

Registered while `t/PREDICT-2026-10-04-teacher1-student.md` is half measured (its seed 3, with round 1's 123 documents:
21 at one kernel and 12 at all seven, against 17 and 8 for the same seed on v3's rows alone). This round asks whether
more documents of the kinds that helped help more. It adds every document the gates have admitted since v3's rows were
built, and changes nothing else.

## The rows (a rule fixed now; counts recorded when built, before training)

`~/scratch/teacher2/pool.sh`: v3's 4,027 rows byte for byte, then:

- graded rows through `t/graded_pool.py`'s gates at one kernel, prompt s2, from three sets: Bedrock round 1's admitted
  training documents (`bedrock-teacher-verified`), round 2's (`bedrock-teacher2-verified`, graded on the lab under
  its own names and checked with the corrected specification check, as round 1's were), and the specification
  round's answers (`round2-specs-4b-v5`, its own verdicts); then `t/spec_first_rows.py` on those rows;
- both Bedrock rounds' admitted specification documents as specification-given rows, distinct programs (two
  teachers' different proofs of one specification are two rows), source `teacher-spec`;
- build_v5's checks: no row outside the training side, no row whose program or specification is one of the 33
  held-out questions.

## Training and measurement

Exactly as the teacher1 round: `t/student_sft.py` on the snapshot v3 used, seeds 1, 2 and 3, on the lab (seed 1 on
GPU 3 now; seeds 2 and 3 on GPUs 1 and 2 when the teacher1 seeds there are done), each measured on the clean 200 by
the shipped seeds' route and script.

## Predictions

- **Q1.** Each seed proves at least 17 of the clean 200 at one kernel and at least 9 by all seven.
- **Q2.** The three seeds' mean by all seven is at least 2 above v3's rows' mean (8.7), so at least 10.7.
- **Q3.** That mean is not below the teacher1 round's three-seed mean by all seven.

Section 1's judgement follows on these seeds against Phi-4-mini under the grammar (9 and 7): beaten when every seed is
above both, doubled when every seed proves at least 18 at one kernel and 14 by all seven.

## What it cannot show

It adds three kinds of document at once (more teacher training documents, the student's own specification-round
answers, more teacher specification documents), so a gain says the set helps, not which part.
