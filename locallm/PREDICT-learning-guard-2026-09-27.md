# Prediction: a larger behaviour guard (arm C), registered 2026-09-27 before it runs

Written after arm A seed 1 finished for three persons and before arm C starts;
the predictions of `PREDICT-learning-2026-09-27.md` are unchanged.

**What arm A showed that makes this worth running.** For `cy`, the behaviour
guard passed 7 or 8 of its 8 training-side prompts at every check of every
sleep, so no sleep was stopped, while on the fixed probe (20 other
training-side prompts, never trained on by the adapter) the answers passing the
t tool fell 17, 17, 17, 12, 8 across the four sleeps, and on all 53 held-out
prompts 33 to 17 (dev problems at least typed: 37 to 21). The adapter learned
the style (adherence on the probe 0.81 to 0.98) and the guard did not see the
cost. Eight prompts with a tolerance of one is too small an instrument.

**Arm C** is arm A seed 1 with the one change: the behaviour guard asks 24
training-side prompts (`--guard-prompts 24`; the first 8 are arm A's, all 24
are drawn from the replay pool by the same hash and kept out of replay), with
the same tolerance of one. Everything else is identical: the problems, the
held-out set, the base pass (`base.json`), learning rate 3e-4, seed 1. It is
run with the code committed with this note.

Predictions, each with the number that falsifies it:

1. **The guard now sees it.** At least 12 of arm C's 16 sleeps end with the
   behaviour guard stopping them or refusing every state (arm A seed 1, when
   this was written: all 11 sleeps of ada, bo and di seen so far were stopped,
   none of cy's 4). Falsified at 11 or fewer.
2. **dawnr does not get worse.** Answers passing the t tool on the 53 held-out
   prompts: at least the base's 33 minus 3 for all 4 persons; dev problems at
   least typed: at least the base's 37 minus 5 for all 4. Falsified by any
   person outside these (arm A seed 1 was outside for cy).
3. **And so it learns less.** Adherence of the held-out answers rises by less
   than 0.1 over the base for every person, cy included (cy gained more than
   that in arm A). Falsified by any person gaining 0.1 or more.

What these would mean together, stated before the result: on this base, what
an adapter changes in dawnr's writing and what it costs in correctness move
together, and a guard strict enough to keep the second keeps nearly all of the
first.
