# The instrument's variance: a second training seed and a second sampling seed for v5. Registered 2026-10-22 07:23Z, before any grade

Four candidates trained this week from improved data landed at or below v5's development count (6 clean, 3 all-seven
of 95) by one to three problems: v6 corrective 6 / 2, v7 4 / 3, v8 4 / 1 (t/PREDICT-2026-10-18-v6.md,
-2026-10-19-decomposed-rows.md, -2026-10-21-v8-spec-rows.md). Each was read as falsified. Nobody has measured what a
training seed or a sampling seed alone does to a count of six on 95 problems; the locallm rounds of September saw 2 to 5
clean across nine seeds of one recipe (SCOREBOARD.md). Until the instrument's spread is known, those verdicts are readings
of noise as much as of data.

## Two arms, nothing else changed

- **Training seed.** v5's exact rows (`t/out/v6-20261018/training-rows.jsonl`, 4,189 rows, sha `e14f766f…`) and exact
  recipe (rank 64, alpha 16, dropout 0.1, lr 2e-4, 5 epochs, max-len 2845, batch 1, grad-accum 16, the pinned trainer
  and base) with `--seed 2` instead of 1, on the desktop at a 150 W cap (`t/recipes/v8_desktop_train.sh` with RUN and SEED,
  persistent unit `dawnr-v5s2-train`, 1,275 steps). Export on the laptop, both development arms on the laptop's GPU, grades
  in the desktop container, paired against the v5 control re-graded under the current tree (51 / 18 / 13 / 6 / 3) and
  against v5 under the 39-call oracle route (63 / 28 / 16 / 7 / 3).
- **Sampling seed.** v5 itself (the installed shards), the frozen route with `--seed-offset 1000` (every sampled attempt
  draws a different seed; the greedy attempts are unchanged and replay from the control's cache), generated on the laptop's
  GPU, graded in the desktop container, paired against the same control.

## Predictions, with the numbers that falsify them

- **P1 (training seed).** Seed 2 lands within one problem of v5 on both counts: clean 5 to 7, all-seven 2 to 4, and its
  all-seven set shares at least two problems with v5's three. A difference of two or more on either count falsifies it.
- **P2 (sampling seed).** The second decode lands within one of the control: clean 5 to 7, all-seven 2 to 4. A difference
  of two or more falsifies it.
- **P3 (what the week's verdicts were worth).** P1 and P2 hold: the panel resolves differences of two, and v7 (4 / 3) and
  v8 (4 / 1) were real losses; the corrected-data lineage is the suspect, and the next row trains v5's original rows plus
  the self-distilled rows (no corrected base). P1 or P2 falsified: the development panel cannot separate this week's
  candidates, and the protocol changes before the data does: three seeds per candidate, or the wider panels (the clean
  182, the development 95 plus the wider 111), with paired per-problem tests, before any candidate is called better or worse.

Sources: the week's PREDICT files; SCOREBOARD.md (round 11, nine seeds); the scout list on seed variance and
small-benchmark statistics, `internal/research-2026-10-22/variance-scout.md`, read before the protocol decision.
