# Prediction: the style profile as a learner (arm P), registered 2026-09-27 before it runs

A second learner beside the adapter, added while the adapter arms of
`PREDICT-learning-2026-09-27.md` were running (their prediction is unchanged
and was committed before them). `locallm/dawnr_learning/profile.py` infers the
mechanical part of a person's taste (local naming, semicolons, indentation, the
if form, showing the checker's verdict) from their own edits by vote, CIPHER's
shape (Gao et al., arXiv:2404.15269) with no language model in the loop, and
rewrites dawnr's answers with semantics-preserving rewrites the t tool
re-checks. No weights change.

Arm P runs `measure_profile.py` on exactly the problems, persons, reactions,
fixed probe and base pass of the adapter arms (same run directory and
`base.json`); the base answers each prompt once, the profile is re-inferred
after every session and rewrites each answer before the person sees it. Nothing
of arm P has been run before this note (its unit tests use the persons on the
test's own program only). It is deterministic: one run, no seeds.

Predictions, each with the number that falsifies it:

1. **The taste is learned.** Adherence of the held-out answers to the person's
   preferences rises by at least 0.3 over the base for all 4 persons. Falsified
   by any person below 0.3.
2. **The person edits less.** Relative edit cost on the held-out prompts falls
   by at least 30% of the base's for bo, cy and di, and by at least 15% for ada,
   whose Approach line is free text the profile does not write. Falsified by any
   of them below its bar.
3. **dawnr is never made worse.** Held-out answers passing the t tool: exactly
   the base's count for all 4 persons; dev problems at least typed: exactly the
   base's count for all 4. Falsified by any difference.
4. **What it believes is true.** After the fourth session every decided
   dimension of every person's profile equals that person's real setting
   (persons.py), and naming, semicolons, indentation and the tool are decided
   for all 4. Falsified by one wrong value or one of those left undecided.

The limit, stated before the result: the synthetic persons' tastes lie inside
the profile's dimensions by construction, so a high score here says the
inference and the rewrites work, not that a real person's taste is covered.
The adapter arms remain the measurement of learning anything else.
