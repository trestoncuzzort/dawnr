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

## Result (2026-10-22 08:10Z): the sampling-seed arm falsifies P2

- The second decode of v5 (the same shards, route and panel; every sampled call under a different seed, the greedy calls
  replayed from the control's cache; generated on the laptop's GPU 07:23Z to 07:37Z, graded in the desktop container):
  54 Python, 11 t, **4 clean, 2 all-seven** against the control's 51 / 13 / 6 / 3. Paired: clean lost 543 and 634, gained
  none, 251 / 450 / 476 / 549 in both; all-seven lost 634, 476 and 549 in both. Receipt
  `release/evidence/v5-decode-seed-2026-10-22.json`.
- P2 falsified: two clean and one all-seven from the sampling seed alone, with nothing changed in the model or the data.
  The same model, run the way v8 was run (laptop generation, desktop grade), lands exactly on v8's clean count.
- P1 pending: the seed-2 training is at step 136/1275 of 1,275 (about 19 s a step, due near 14:10Z), then the laptop's
  tandem unit exports, generates and grades it. Its answer is recorded below when it lands; it no longer changes P3's branch.
- P3, the "either falsified" branch: the development panel cannot separate this week's candidates. v7's 4 / 3 and v8's
  4 / 1 sit within one decode of v5 itself. The test-fitting reading of v8 (the three-test gate's precision 0.785 to 0.515
  on the ceiling instrument, 20 candidates per problem) stands on its own, larger instrument and is not withdrawn; "v8 lost
  two clean problems" is withdrawn as a reading of noise.

## The protocol from here, in force before any more data

- Three decodes per candidate on the development panel (seed offsets 0, 1000, 2000), each graded in the desktop container.
  A candidate's number is its mean clean count and its per-problem success fraction over the three decodes. A candidate is
  called better or worse than the control only on the paired per-problem fractions (the sign of the paired difference on
  each problem, summed over the panel), never on one decode's count.
- Running now on the laptop's GPU (unit `dawnr-decode-protocol`, `t/recipes/decode_protocol_20261022.sh` over
  `t/recipes/decode_arm.sh`): v5's third decode (offset 2000) and v8's second and third (1000, 2000), about 40 minutes
  each; the log is `t/out/decode-arms.log`, the receipts `release/evidence/decode-<tag>.json`. These complete three decodes
  for v5 and for v8 and re-read the week's largest verdict under the protocol.
- Why one decode cannot do it: a count of six of 95 carries a binomial spread of about 2.4 problems by itself
  (sqrt(95 x 0.063 x 0.937)), and the published single-run spreads on code evaluations say the same
  (`internal/research-2026-10-22/variance-scout.md` rows 16 and 22: 2.2 to 6.0 points between runs, standard deviations
  0.33 to 1.49 points over reruns of a whole pipeline). A one-to-three problem difference is inside that.
- Training-side candidates: if P1 also lands outside one problem of v5, a candidate trained from new data needs two
  training seeds before a verdict (about 6.5 h each on the desktop at 150 W); route-side candidates (flags, prompts, gates)
  need only the three decodes. The clean 182 panel stays held out for the final reading and is not used in development.

## Result (2026-10-22 10:34Z): v5 and v8 under the three-decode protocol

Three decodes each (seed offsets 0, 1000, 2000; generated on the laptop's GPU except v5's first, which is the desktop
control; all graded in the desktop container), read by `t/recipes/three_decode_report.py`:

| model, count | decode 1 | decode 2 | decode 3 | mean | clean on all three | clean on at least one |
|---|---|---|---|---|---|---|
| v5, clean | 6 | 4 | 6 | 5.33 | 251, 450, 476, 549 | those plus 270, 543, 634 |
| v8, clean | 4 | 4 | 5 | 4.33 | 476, 543, 549 | those plus 251, 634 |
| v5, all-seven | 3 | 2 | 3 | 2.67 | 476, 549 | those plus 634 |
| v8, all-seven | 1 | 2 | 2 | 1.67 | 549 | that plus 634 |

Paired per problem, clean: v8 up on 543 (fraction +0.67), down on 251 (-0.33), 270 (-0.33) and 450 (-1.0); mean
difference -1.00 problems; exact sign test p 0.625; paired permutation test p 0.624. All-seven: one problem moved
(476, -1.0); p 1.0. Receipt `release/evidence/three-decode-v5-v8-2026-10-22.json`; the per-decode pairings
`release/evidence/decode-v5-20261022-seedoff2000.json`, `decode-v8-20261022-seedoff1000.json`,
`decode-v8-20261022-seedoff2000.json`.

Reading: v8 and v5 are not separable on this panel. The supportable statement is "v8 did not gain"; "v8 lost two
problems" is withdrawn. What the three decodes do show is a change in which problems come out, not in how many: v8
solves 543 on every decode (v5 on one of three) and never solves 450 (v5 on every decode); it reaches all-seven on 476
never (v5 always). A data row can move the reliable set sideways without moving the count.

What the panel can resolve from here: with about five reliably clean problems, the sign test needs about six problems
moving one way and none the other to reach p below 0.05 at three decodes. A candidate that gains fewer than that on 95
problems is read on the wider panels (the development 95 plus the wider 111) or with more decodes, and is never called
better or worse on the mean alone. P1 (the training seed) is still pending; it is recorded here when the seed-2 model is
graded.

## Result (2026-10-22 16:15Z): the training-seed arm, first decode

v5's exact rows and recipe with seed 2 (desktop, 150 W, 1,275 steps; export sha `407dd4a9…`), decoded once on the
laptop's GPU and graded in the desktop container: frozen route 50 Python, 9 t, **4 clean, 2 all-seven** against the
control's 51 / 13 / 6 / 3; paired clean lost 251 and 549, gained none, 450 / 476 / 543 / 634 in both; all-seven lost 549,
476 and 634 in both. The 39-call oracle route: 66 / 12 / 5 / 2 against 63 / 16 / 7 / 3, lost 270 and 549. Receipts
`release/evidence/v5s2-dev-2026-10-22.json`, `v5s2-oracle39-2026-10-22.json`.

On its first decode P1 is falsified by the same margin P2 was: the training seed alone moves the clean count by two,
on both routes. The seed-2 model's second and third decodes are running (the three-decode protocol); the paired
three-against-three reading of v5 and v5s2 is recorded below when they land, and it is the number that decides whether
a training-side candidate needs two training seeds before any verdict.
