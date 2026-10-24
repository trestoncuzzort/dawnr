# dawnr 6.1.0, candidate A: v5's own rows plus checked specifications and repair examples. Registered 2026-10-24, before training

Plan of record: `internal/RELEASE-6.0-PLAN.md`. Its section 2 found that every candidate since v5 trained on a
corrected set rather than v5's own rows, that the seed-2 "twin" did too, and that the 240-problem panel holds 34
problems v5's rows had matched. This candidate goes back to v5's own rows and adds only data that passed the strict
checks, so it is read against the published v5 on equal footing.

## The rows (receipt `release/evidence/release-6.1-candidate-a-rows-2026-10-24.json`)

- **Base:** v5's original 5,095 rows (SHA-256 `848fca29…`) audited under the standing policy
  (`t/heldout_audit.py --panels --refuse-gpl`): 62 rows refused (61 descend from MBPP-DFY, GPL-3.0 at the source; 1
  matches held-out problem 629 as a twin), then every other view of the refused problems removed
  (`t/recipes/student_row_families.py`, 9 more rows). 5,024 rows, `014e5a32…`, repeats kept exactly as v5 had them.
- **Added, built by `t/recipes/v8_spec_rows.py --pool v5` (problems with a specification row in the base skipped):**
  specification and Python rows from v9's strictly kept self-distilled specifications (508 rows) and from the two
  teachers' strictly kept specifications (670 rows; DeepSeek v3.2 on Bedrock, MIT, and a primed 9B), all re-checked
  at 1,000 draws with both mutant families at 90%; the repair traces, 232 from the student's own dropped candidates
  and 293 from the teachers'.
- **Total:** 6,727 rows, SHA-256 `2c2eff287493fd8774d1a71bc9e799ca4cc40f21fd9a1b082c17f8206f7351d8`; self-generated
  share 11%. Audit of the final file: 0 rows flagged; 730 rows match problems already out of the panels (not refused,
  the standing policy). Rows are not published in this repository; the receipt carries the hashes and counts.

## Recipe (v5's, unchanged)

Qwen/Qwen3.5-4B at `851bf6e8`, QLoRA NF4 with double quantisation and bf16 compute, rank 64, alpha 16, dropout 0.1,
lr 2e-4, 5 epochs, max-len 2845, batch 1, grad-accum 16, trainer `t/student_sft.py` sha `e43c27df…`. Seeds 1 and 2,
one after the other, on the desktop's RTX 4080 at its 150 W cap (`t/recipes/v8_desktop_train.sh`). Q8_0 export with
the pinned converter.

**Execution-location amendment, 2026-10-24, before either adapter completed:** the user reserved both local
machines for final testing, allowing the existing training to finish. Export and decodes move to approved cloud
GPU compute; seven-kernel grading runs in the frozen image on GitHub. This supersedes the original local
evaluation schedule. Rows, training recipe, decoding settings, panels and acceptance thresholds are unchanged.

## Predictions, with the numbers that falsify them (the plan's five conditions)

- **P1, the paired reading.** On the 206 unleaked development problems (the 95 plus `heldout_audit.wider_clean()`),
  the candidate's six decodes (two seeds, seed offsets 0, 1000, 2000) against the published v5's three, per problem
  (`t/recipes/three_decode_report.py`): more problems up than down and permutation p at or below 0.05. Anything else
  falsifies it. v5's reference: 19.33 clean per decode on the 206.
- **P2, the gate's precision.** At least 0.70 on the ceiling instrument (v5 0.785). Below falsifies it.
- **P3, given specifications.** At least 27 of the 33 proved by all seven kernels at Q8_0. 26 or fewer falsifies it.
- **P4, held-out, read once after P1 to P3 decide.** At least 17 of the clean 182 at one or more kernels and 12 at all
  seven, under `t/score_levels.py --larger`. Lower falsifies it.
- **P5, smooth on this laptop.** Median command time and peak memory within 10% of v5's on the same laptop, and no
  software thermal slowdown during the run, measured on the README's example commands from a clean checkout.

All five hold: this model ships as dawnr 6.1.0. P1 fails with the rest holding: the rows do not separate on 206 and
the next increment adds the Cohere teacher's rows (candidate B). P2 fails: the self-distilled rows teach test-fitting
on this base too and leave candidate B.

**The honest prior.** On the corrected base the same kinds of added rows read 7 clean on one decode against 4 for
their base, inside the noise. The bar here is strict and the week's readings make a pass less likely than a fail.
What this run settles either way is whether v5's own rows plus checked data beat v5 when nothing else changes.
