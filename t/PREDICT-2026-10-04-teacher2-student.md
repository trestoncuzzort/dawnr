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

## The rows as built, 2026-10-04 07:26:45Z (commit 52523806; before any seed trains, seed 1 started 07:26:54Z)

`sft-student-teacher2.jsonl`, 4,625 rows, sha256 ba80902ae004179e...: v3's 4,027 byte for byte, then 598: 111 graded
rows (21 from Bedrock round 1's training documents, 27 from round 2's, 63 from the specification round; by level 1 to
7: 5, 5, 5, 8, 5, 26, 57), 317 spec-first rows (97 Python, 109 specification, 111 proof-from-Python), and 170
specification-given rows from both rounds' admitted specification documents (distinct programs). Dropped as held-out
leaks by a stricter check than build_v5's, which a first build showed misses one (`t/PREDICT-2026-10-04-teacher1-student.md`,
the leak note): any row whose vericoding stem is a held-out question's, or whose specification matches one with the
header's gate line left out, besides build_v5's own check; 10 rows over six specifications (DA0455, DD0061, DD0077,
DD0680, DD0684, DD0752). Predictions stand.

## Amendment, 2026-10-04 07:50Z, before any seed is measured: where seeds 2 and 3 run

Seed 3 started on the lab's GPU 2 as soon as teacher1's seed 1 freed it (the first orchestrator would have waited for
teacher1's seed 2 too); seed 2 starts on GPU 1 when teacher1's seed 2 has answered there. Each seed is graded as soon
as it has answered. Same command, rows and seeds; predictions stand.

**Provenance note, 2026-10-04 07:52Z.** 46 of this round's appended specification-given rows are built from dafny-synthesis programs
(GPL-3.0 at the source, reached through DafnyBench), which every release leaves out; these seeds are measurements, not
release candidates (`t/PREDICT-2026-10-04-release-v4.md`, amendment).

## Seed 1, 2026-10-04 11:20Z (`~/scratch/teacher2/levels-teacher2-seed1.md`)

102 problems with tested Python, 42 answered, all 42 pass their tests; **23 proved by at least one prover, 20 by three,
14 by five, 13 by six, 13 by all seven**. Seed 1 on v3's rows alone: 17 and 10; with round 1's documents only: 19 and
8. Q1 holds for seed 1 (23 and 13).
