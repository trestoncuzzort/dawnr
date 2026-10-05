# The student on v3's rows plus every document admitted so far, three seeds: registered before any of it trains

> **Correction, 2026-10-05:** counts on the clean 200 in this file include 18 problems that an audit of the training rows
> later took out of the panel. Every published row is restated on the clean 182 in
> [DECONTAMINATION-2026-10-05.md](DECONTAMINATION-2026-10-05.md).

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

## Amendment, 2026-10-04 11:26Z, before seeds 2 and 3 are measured: seed 2 on its own card

Seed 1 finished and left the lab's GPU 3 idle while seed 2 shared GPU 1 with the release-v4 candidate at 15 s a step.
Seed 2 (step 538 of 1,440) was stopped and started again from step 0 alone on GPU 3 at 11:21:44Z (7.9 s a step), the
same model of card, with the same command, rows and seed; the stopped run's output is kept aside, not used. The
candidate continues alone on GPU 1. Predictions stand.

## Seed 3, 2026-10-04 11:47Z (`~/scratch/teacher2/levels-teacher2-seed3.md`)

Trained 1,440 steps (final loss 0.0258). 111 problems with tested Python, 57 with a kept specification, 48 answered,
all 48 pass their tests; **27 proved by at least one prover, 23 by three, 16 by five, 15 by six, 13 by all seven**.
The same seed on v3's rows alone: 17 and 8; with round 1's documents only: 21 and 12. Q1 holds for seed 3 (27 and
13). Q2 holds if seed 2 proves at least 7 by all seven, Q3 if it proves at least 1.

## Seed 2 and the outcome, 2026-10-04 16:49Z (`~/scratch/teacher2/levels-teacher2-seed2.md`; recorded 16:56Z)

Seed 2 (restarted alone on GPU 3, 1,440 steps, final loss 0.0256): 104 problems with tested Python, 52 with a kept
specification, 48 answered, all 48 pass their tests; **24 proved by at least one prover, 21 by three, 17 by five,
16 by six, 15 by all seven**.

| seed | v3's rows alone | plus round 1's documents (teacher1) | plus every admitted document (teacher2) |
|---|---:|---:|---:|
| 1 | 17 and 10 | 19 and 8 | 23 and 13 |
| 2 | 16 and 8 | 13 and 7 | 24 and 15 |
| 3 | 17 and 8 | 21 and 12 | 27 and 13 |
| mean | 16.7 and 8.7 | 17.7 and 9.0 | **24.7 and 13.7** |

- **Q1 holds:** every seed proves at least 17 at one kernel and 9 by all seven (23, 24, 27; 13, 15, 13).
- **Q2 holds:** the mean by all seven is 13.7, against at least 10.7.
- **Q3 holds:** 13.7 against teacher1's 9.0.
- **Section 1:** every seed is above Phi-4-mini under `t`'s grammar (9 and 7) at both levels, so it is beaten
  with every seed, by more than v3's rows did. Doubled needs every seed at 18 and 14: all three pass 18 at one kernel,
  seed 2 reaches 15 by all seven, and seeds 1 and 3 stop at 13. **Not doubled**, by one problem on two seeds.

**Reading.** 598 rows of admitted documents moved every seed past the spread three seeds of the same recipe had shown
(v3's rows: 16 to 17 and 8 to 10; these: 23 to 27 and 13 to 15), where teacher1's 182 rows had not. Against the
student's own starting weights prompted the same way (15 and 8, `t/PREDICT-2026-10-04-size-curve.md`), the rows add
8 to 12 at one kernel and 5 to 7 by all seven. The case split, regraded on seeds 1 and 3, left both at 13
(`t/PREDICT-2026-10-04-case-split.md`); seed 2's regrade follows the merge.
