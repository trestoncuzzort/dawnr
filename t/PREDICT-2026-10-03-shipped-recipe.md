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

## Amendment, 2026-10-03 23:05Z, before any seed is measured: the Python step's sandbox on the lab

Seed 1's `spec_first.py --python 3` stopped at its first model-written solution: the lab's Ubuntu 24.04 restricts
the user namespaces bubblewrap needs, an AppArmor profile would need root there, and `t/py_sandbox.py` runs no
model-written code without a sandbox (it raised, nothing was produced, nothing was graded). On the lab the step now
runs under the Landlock backend (`t/landlock_exec.py`, chosen by `t/sandbox.conf` there): the same interpreter, the
same read-only system folders and limits, with calls that would reach outside refused rather than hidden. Measured
before this amendment, on the desktop where both run: the v5 seeds' 322 accepted solutions on their own tests, on a
neighbouring problem's tests, and cut in half (966 cases) give the same result under both, 0 different. The
generation is unchanged (`~/.venv-t-train`, the reference PyTorch kernels, as the v5 seeds' `~/.venv-t` had).
Seed 1's Python step is run again on GPU 1; seeds 2 and 3 take it when their training ends. Predictions stand.

## Seed 1, 2026-10-03 23:59Z (`~/scratch/shipped/levels-seed1.md`)

Seed 1 (v3's weights), the clean 200, complete specifications, the corrected instrument: 37 reach a task, 37
pass their tests, 17 proved by at least one prover, 16 by three, 13 by five, 11 by six, **10 by all seven**. For
seed 1, prediction 123 holds (17 and 10 against 15 and 6). 124 waits for all three seeds; at all seven seed 1 is
2.7 above the v5 recipe's mean (7.3), more than the 1 the prediction allows, in the direction of the shipped rows.
