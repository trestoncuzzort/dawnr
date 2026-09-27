# What r12 is predicted to show, registered before any seed trains

**Written 2026-09-27, before the fine-tune has run at any seed.** No r12 checkpoint
exists yet; `t/out/pretrain-r12-2026-09-25/wd0.8-lr1e-3-seed1337-desktop-best/` is
still training (`run.json` status `running` at the time this was written). This
file is the one-look registration `t/RUN-NEXT-locallm-r12.md` section E requires:
the 232 are looked at once per decision, and this is what falsifies the decision.

    seeds: 10
    metric: clean
    problems: decontam

(`metric: clean` and `problems: decontam` pin `t/compare_arms.py` to tests-pass-and-
clean on the 200 decontaminated problems -- section E's primary metric -- so a
later run cannot silently switch to a kinder count.)

## What the corpus is, frozen by its hash

`t/out/loop/corpus-r12-headed.txt`, sha256 `a8a382ebd3c731d5144267d0001d22595cd97
01c1a8d65cdc7a61e5492a1881e`: 499 documents, 272,163 bytes -- 431 lifted/committed
(clean in all seven kernels, 0 admitted with a gap; the regraded totals from
`t/LIFT-2026-09-26.md`'s 2026-09-27 update) plus 68 teacher-answer positives from
`t/out/loop/sft-r12-v5resolved.jsonl` (sha256 `fede669ce7b2036d2ff17ab4db0c203679
f14b63df4ca05a920ef14d7a5cc5ca`), which is `t/out/loop/sft-r12.jsonl` (sha256
`b891cc4046371a2b034ae91cbe54b2d938a54a367905299d36e2721a5419078e`, built by
`build-r12`) with 54 rows dropped that name a task_id in neither pool v3 nor v5
(an unindexed-APPS gap, not a decontamination hit; see section B's update in
`t/RUN-NEXT-locallm-r12.md`). 118 documents carry an English head.

## Arms

**Base** (r11, already graded, `t/DATA-r12.md` / `t/r12_data_queue.sh R11_TAGS`):
`locallm-r11-rerun, locallm-r11-s1, ..., locallm-r11-s9` -- 10 single fine-tunes of
the r9 recipe on `corpus-r8-headed.txt`, differing only in `--seed`. Reported by
`OVERNIGHT-2026-09-26.md`: 0 clean on the decontaminated 200 in eight of these
seeds, 2 in one.

**New** (r12, not yet run): `locallm-r12-s1, ..., locallm-r12-s10` -- the section C
recipe (document-boundary rows, dropout 0.1, dev-chosen stopping step, `--split-
seed 1337`) on `corpus-r12-headed.txt`, seeds 1 through 10. Both arms decoded
identically: `t/gen_fleet.sh`, `--temperature 0`, split-v5, graded by `t/grade_lab.
sh heldout` and scored by `t/score_heldout.py`.

## Predictions

"Clean" below means `t/score_heldout.py`'s clean count on the 200 decontaminated
problems (tests pass, and verified with the twin refuted in all seven kernels);
"written" excludes a clean answer that is a training document with names erased.

1. **The r12 arm's mean clean-200 count is greater than 0.** Today 0 of 10 r11
   seeds average above roughly 0.2 (2 of 200 in one seed, 0 in the other nine), and
   9 of the 10 arms measured anywhere in `t/RUN-NEXT-locallm-r12.md`'s "Where
   locallm actually stands" table are exactly 0. Falsified if all 10 r12 seeds
   score 0 clean on the 200: the corpus growth (194 to 499 documents, with the
   dev-chosen stopping step replacing "last step") would have bought nothing
   measurable.
2. **At least one r12 seed's clean-200 count is written, not merely clean** (its
   answer is not a training document with names erased). Falsified if every clean
   r12 answer on the 200 is a recitation: the point of moving off the 32
   contaminated problems is to see the model compute something, not repeat it
   with different names.
3. **`t/compare_arms.py --metric clean --problems decontam` returns INCONCLUSIVE,
   not ADOPT, for base vs. new at 10 seeds each.** Section E's own guidance is
   that a +1 difference is not resolvable at 232 problems and +2 needs 10-20
   seeds; the corpus and recipe changes are aimed at moving the count off zero,
   not at a coordinated multi-point swing that would clear the ADOPT bar (p <=
   .05 and the P(B>A) interval's upper bound above .75) this early. Falsified by
   ADOPT (the effect is larger than expected, which is good news, reported as
   such) or by NOT MEANINGFUL (the interval never separates from .5, which would
   mean nothing moved).
4. **The r12 arm's well-formed rate on all 232 does not fall below the r11 base
   arm's mean.** The document-boundary and dropout changes touch training
   dynamics, not the grammar the model was already emitting correctly; a drop
   here would mean a regression section C did not anticipate. Falsified if r12's
   mean well-formed count is lower than r11's mean well-formed count.
5. **Every r12 seed's dev-curve (`selection.json` beside each run) shows its
   chosen step at or before step 150.** r11 seed 1's validation loss stopped
   moving by step 100-150 while train loss kept falling (section C); if the
   dev-chosen stopping step (tests passed on 100 held-out-from-training MBPP
   problems, section C) picks a materially later step than validation did on the
   old recipe, that is itself a finding about whether test-based selection
   overfits slower or faster than loss-based selection, reported either way.

## What follows

If 1 holds and 3 is INCONCLUSIVE (the expected case): r12 is progress -- the first
non-recitation evidence of generalization -- but not yet a recipe change to adopt
over r11 by this test alone; the next round doubles the seed count on the arm that
looks better, per Dodge et al.'s expected-best-of-n framing already used in
`t/compare_arms.py`. If 1 fails: the corpus and recipe changes bought nothing this
round can measure, and the next lever is the pilot sampling of section D (self-
consistency across samples), not another single-sample recipe tweak. If 3 is
ADOPT: report it as the headline it would be, with the same skepticism section E
applies to any single look -- rerun the comparison at 20 seeds before repeating the
claim anywhere public, per Dodge et al. (arXiv:2002.06305, already the receipt
behind `--split-seed`, A7).
