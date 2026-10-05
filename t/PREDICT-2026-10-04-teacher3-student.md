# The student on every admitted document, round 3's 129 APPS documents included, three seeds: registered before any of it trains

Registered 2026-10-04 13:36Z. The teacher2 round (v3's rows plus 598 rows from every document admitted through Bedrock
round 2 and the specification round) reads 23 and 13, then 27 and 13, at one kernel and by all seven for its seeds 1
and 3 (seed 2 is training). The prompted starting weights read 15 and 8 with 17 answers a problem
(`t/PREDICT-2026-10-04-size-curve.md`), so what the documents add is the part of the student this project made.
Bedrock round 3 (DeepSeek-V3.2 on the 2,165 remaining APPS training problems) admitted **129 documents** in six or
seven kernels (A2, `t/PREDICT-2026-10-04-teacher-round3-apps.md`), which by its rule join the pool for the next
registered student round. This is that round; nothing else changes.

## The rows (a rule fixed now; the counts are recorded when built, before training)

`~/scratch/teacher3/pool.sh`: the GPL-free teacher2 rows (the release-v4 candidate's, 4,579, sha256
1adba7e4a9df95d3...) byte for byte, then round 3's 129 admitted training documents through the pool's own route:
`extract --promote-header`, the problems' tests, the seven kernels on the lab under the tasks' own names, the
corrected specification check (1,000 draws, each task's own generator, MBPP+'s references), `t/graded_pool.py`'s
gates at one kernel and prompt s2, then `t/spec_first_rows.py` on those rows. Dropped: every row
`t/student_rows.py`'s `leaks_heldout` flags (a held-out question's vericoding stem, its program or specification,
or its specification without the `gate` line) and any row outside the training side.

## Training and measurement

The shipped recipe exactly (`t/student_sft.py`, Qwen3.5-4B at the snapshot v3 used, rank 64, five epochs, rows up to
2,845 tokens), seeds 1, 2 and 3, each alone on one of the lab's cards as it comes free (GPU 1 after the size curve's
fine-tuned 2B, GPU 2 after its 27B point, GPU 3 after teacher2's seed 2), each measured on the clean 200 by the shipped
seeds' route and script as soon as it has answered. A seed is graded with the instrument in force when it is graded:
if the case split (`t/PREDICT-2026-10-04-case-split.md`) is merged by then, the comparison sets are teacher2's seeds
regraded with it, and the cells the split decided are listed.

## Predictions

- **T1.** Each seed proves at least 18 of the clean 200 at one kernel and at least 11 by all seven.
- **T2.** The three seeds' mean by all seven is at least teacher2's three-seed mean.

Section 1 is judged on these seeds by its own rule: doubled when every seed proves at least 18 at one kernel and 14 by
all seven (twice Phi-4-mini under `t`'s grammar, 9 and 7).

## What it cannot show

Round 3's documents answer APPS problems, whose statements are stories and input formats rather than MBPP's one-line
requests; a gain, or none, says how far they transfer to MBPP and HumanEval. The base rows differ from teacher2's by
the 46 GPL-derived specification-given rows left out; the release-v4 candidate (seed 1 on exactly those base rows)
measures that difference for one seed.

## The rows as built, 2026-10-04 13:52Z (recorded 13:52:20Z, before any seed trains)

`sft-student-teacher3.jsonl`, **5,095 rows**, sha256 848fca29d9399ef9...: the release-v4 candidate's 4,579 byte for
byte, then 516: 129 graded rows (every admitted document; graded again on the lab under their own names, by level
5 to 7: 6, 37, 86) and their 387 spec-first rows (129 each of Python, specification and proof-from-Python). No row
dropped by the held-out check; none outside the training side. Predictions stand.

## Seed 2, 2026-10-04 19:54Z (`~/scratch/teacher3/levels-teacher3-seed2.md`; recorded 19:55Z)

Trained alone on GPU 2 (1,585 steps, final loss 0.0265): 111 problems with tested Python, 49 answered, all 49 pass
their tests; **27 proved by at least one prover, 25 by three, 20 by five, 18 by six, 15 by all seven**. Graded with the
case split, which decided three cells, all on 605 (lean unproved, fstar verified, rocq a timeout); no count at one
kernel or by all seven depends on them. The same seed on teacher2's rows: 24 and 15. T1 holds for seed 2.

## Seed 3, 2026-10-04 20:51Z (`~/scratch/teacher3/levels-teacher3-seed3.md`; recorded 20:52Z)

Trained alone on GPU 3 (1,585 steps, final loss 0.0265): 104 problems with tested Python, 41 answered, all 41 pass
their tests; **23 proved by at least one prover, 21 by three, 18 by five, 15 by six, 13 by all seven**. The same seed on
teacher2's rows: 27 and 13. T1 holds for seed 3.

## Amendment, 2026-10-04 22:52Z, before seed 1 is measured: its route, again, with two bounds the interpreter lacked

Seed 1 trained (1,585 steps, final loss 0.0267) and its clean-200 route was SIGKILLed twice, at 22:07Z and 22:44Z,
each time in the specification stage, the second time near 122 GB: a written specification joined a sequence with
itself inside a specification function, doubling it at every step, and `join` and `replace` were the two sequence
operations the interpreter let outgrow `MAX_SEQ` (the fault handler's traceback, `~/scratch/teacher3/pyfirst-1b.log`).
Both now raise `Budget` past `MAX_SEQ`, as `fill` and seq `+` already did, and `t/spec_quality.py` gives one
evaluation 60 s of wall clock (bfde8ba6). Seeds 2 and 3 finished the whole route in about 14 minutes, so neither bound
could have changed what they kept. Seed 1's route runs again with them, on the first of the lab's cards the teacher
round 4 frees; same model, command and ids. Predictions stand.

**Before seed 1 is measured, 01:13Z on 2026-10-05:** the second run (00:37Z) kept its memory at 2.6 GB, so the interpreter's
caps held, but its specification stage went 25 minutes without an answer: one slow specification, evaluated on every
test and every mutant at up to 60 s each. `t/spec_quality.py` now also bounds a whole specification's scoring (120 s,
past which it is unscorable) and gives one evaluation 10 s (7174b736). Rescored under these clocks, every one of the 871
specifications seeds 2 and 3 scored reads the same (the slowest took 0.08 s), so neither seed's measurement could have
moved. Seed 1's route runs a third time with them. Predictions stand.
