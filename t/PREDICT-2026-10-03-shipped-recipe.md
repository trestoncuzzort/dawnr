# The shipped recipe on the clean 200, three seeds: registered 2026-10-03 21:41Z, before any of it trains

## Why

Goal 1 (AMBITION.md section 1) has only ever been measured on the 4B on v5, whose rows hold 44 GPL-derived rows
and which no released model uses. The goal is to be met with the weights that ship. The shipped recipe is v3's
(`t/PREDICT-2026-10-02-release-v3.md`): v5's rows without the 44, with 83 permissive specification-given rows from
the corpus at six of seven kernels, 4,027 rows. Section 1 asks for three seeds, so the recipe is trained three
times: seed 1 is v3 itself (training on the lab's GPU 1 now), seed 2 trains on the desktop card now, seed 3 on the
first lab GPU that frees.

## The measurement

Exactly the v5 seeds' route (`~/scratch/replication/run.sh`): `t/spec_first.py --model <merged> --python 3` on the
clean 200 ids, `spec_experiment extract --promote-header`, `tests`, the passing answers graded in all seven kernels
on the lab, then the specification check with the corrected instrument registered at 21:39Z (each task's own
generator, 1,000 draws) and MBPP+'s references where they keep the problem's tests, scored with
`t/score_levels.py --min-completeness 0.6`. Phi-4-mini's sets and the v5 seeds are scored with the same instrument.

123. Each seed proves at least 15 of the clean 200 on complete specifications at one kernel and at least 6 at all
     seven.
124. The mean at all seven is within 1 of the v5 recipe's mean under the same instrument.

Section 1's judgement is then made on these three seeds against Phi-4-mini under the grammar, with the same
instrument: the shipped weights either meet the written bar or they do not.

## Amendment, 2026-10-03 21:57Z, before any seed is measured: all three seeds on the lab

Seed 2 started on the desktop card and ran at about 115 s a step, twelve times slower than v2 on the same card a
day earlier (9.7 s). The card's link now trains at 2.5 GT/s with ASPM L1 on: a kernel launch takes about 82 us and a
host-to-device copy runs at 0.31 GB/s. Seed 2 is stopped and moves to the lab: seeds 1, 2 and 3 all run on the lab's
GPU 1 (seed 1 is v3; seeds 2 and 3 train there side by side), with the lab's PyTorch 2.13. Predictions stand.
