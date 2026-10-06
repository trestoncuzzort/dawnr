# What r12 is predicted to show, registered before any seed trains

> **Correction, 2026-10-05:** counts on the clean 200 in this file include 18 problems that an audit of the training rows
> later took out of the panel. Every published row is restated on the clean 182 in
> [DECONTAMINATION-2026-10-05.md](DECONTAMINATION-2026-10-05.md).
> A second correction that day holds each specification to inputs larger than the examples as well; the rows are
> restated again in [LARGER-INPUTS-2026-10-05.md](LARGER-INPUTS-2026-10-05.md).

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

`t/out/loop/corpus-r12-headed.txt`, sha256 `12491a7f067ea0b96a6ee6217b9869c9d81e7439
04603f202109d8f878daf943`: 531 documents, 311,723 bytes -- 463 lifted/committed (435
lifted, 28 committed; clean in all seven kernels, 0 admitted with a gap; the 2026-09-28
totals from `t/LIFT-2026-09-26.md`) plus 68 teacher-answer positives from
`t/out/loop/sft-r12-v5resolved.jsonl` (sha256 `fede669ce7b2036d2ff17ab4db0c203679
f14b63df4ca05a920ef14d7a5cc5ca`), which is `t/out/loop/sft-r12.jsonl` (sha256
`b891cc4046371a2b034ae91cbe54b2d938a54a367905299d36e2721a5419078e`, built by
`build-r12`) with 54 rows dropped that name a task_id in neither pool v3 nor v5
(an unindexed-APPS gap, not a decontamination hit; see section B's update in
`t/RUN-NEXT-locallm-r12.md`). 147 documents carry an English head.

**Re-registered 2026-09-28, still before any seed trains.** No r12 checkpoint exists;
the core `best.pt` above is unchanged (2026-09-27 05:04, `run.json` status `stopped`
at its best, which the launcher accepts). The 2026-09-27 registration froze the
499-document build (sha256 `a8a382ebd3c731d5144267d0001d22595cd9701c1a8d65cdc7a61e5492a1881e`:
431 lifted/committed, 118 heads); the lifter rows and certificate fixes of 2026-09-27
and 2026-09-28 (seq-valued spec_funs, finite sets, datatypes, as-char casts under a
bound, the spec_fun-call certificates in Dafny and Frama-C) grew it to the build above,
same builder, same gates, same `--min-kernels 7`. The predictions below are unchanged;
prediction 1's document count reads the new total.

**Split seed 1338, recorded 2026-09-29 before any seed trained.** On the first launch
the trainer refused the recipe's `--split-seed 1337`: the hash split's holdout on this
corpus is 6.9% of the characters (46 of 531 documents), under the 8% floor for
`--val-frac 0.1`. Section C of `t/RUN-NEXT-locallm-r12.md` wrote the rule for this
case in advance (the next registered split seed is used and recorded): 1338 holds out
10.7% by characters, so every r12 arm trains with `--split-seed 1338`. The validation
holdout is the trainer's loss curve only; the held-out evaluation set (split-v5, the
232) and the dev split are untouched, and the predictions stand as written.

**The reply stop is the document terminator, recorded 2026-09-29 before any held-out
answer was scored.** Seed 1's first pass, under the old rule, decoded 832 replies
(600 dev, 232 held-out) and every one ran to the 1,200-token budget unparseable:
each holds a complete program, then a blank line, then text drifted from the
pretraining corpus. The cause is a mismatch between section C's `--doc-batches`
rows, which end every document with a blank line and nothing after it, and the
2026-09-25 stop rule, which waited for the *next document's head* after the blank
line, something a windows-trained model emits and a document-trained model never
does. The stop is now the blank line itself (`t/loop_locallm.py` REPLY_BOUNDARY;
no corpus document or committed task holds an internal blank line, measured). For
a reply that goes on to the next head the cut is the same byte as before, so the
base arm's answers are unaffected; seed 1's first-pass replies are kept aside in
the run record (`~/scratch/r12-s1-nostop` on the desktop, not scored) and its
stopping step and held-out answers are redone under the stop. The launcher also
records an answer set with no well-formed answer as 0 well-formed, 0 clean instead
of stopping the run. The predictions stand as written.

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
   score 0 clean on the 200: the corpus growth (194 to 531 documents, with the
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

**Amendment, 2026-09-30 19:17Z, before any seed trains on the new core: the New arm runs on r12's
core.** The 2026-09-29 launch trained three seeds on the sweep's core (`locallm-r12-s1` to `s3`)
and was paused after all three read 0 clean, spec checked, on the 200; they stay recorded as the
head-prompt control of the chat pipeline's registration and are not part of the New arm. r12 was
reframed the same day: its core is `t/out/dawnr-r12-core-2026-09-30/core`, registered and judged
in `t/PREDICT-2026-09-30-dawnr-r12-core.md` (3.7B English tokens, then 15,000 code steps; the
kept copy at step 14,000, code validation 1.140). The New arm is therefore `locallm-r12core-s1`
to `s10`: the section C recipe unchanged (300 steps, lr 3e-5, block 512, document rows, dropout
0.1, keep-every 50, dev-chosen stopping step, split seed 1338 as recorded above), initialised from
that core's `ckpt.pt` through the launcher's overrides (`R12_RUN_CORE`, `R12_RUN_CORE_READY`,
`R12_RUN_ARM=locallm-r12core`, outcomes in `t/out/r12core-outcomes.json`), decoded and graded as
registered (lab grading at 6 cells). The Base arm is unchanged. Predictions 1 to 5 stand as
written; prediction 6 of the core's registration (at least 1 clean, spec checked, on the 200 for
at least one seed) is what this round answers. The specification check applied at scoring is the
repaired one (commit 6159cd4a: string problems' references called with str arguments), which
moved no published count when every graded arm was re-scored.

