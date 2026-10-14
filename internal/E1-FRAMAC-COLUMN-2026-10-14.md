# Frama-C whole-task-column comparison: the adapter fix has an unintended regression (2026-10-14)

The engine-first Frama-C adapter fix behind E1's all-seven figure was checked by a registered
baseline-vs-patched comparison over the whole committed task column (114 tasks), same Frama-C install and
resource policy, clean isolated checkouts of upstream `18d79ef` (baseline) and the patched `7271e2e`. The
result is NOT a clean win.

## What changed (Frama-C cell = real / twin)

| | verified / refuted | vacuous / vacuous | abstain / abstain | timeout / refuted |
|---|--:|--:|--:|--:|
| baseline 18d79ef | 71 | 0 | 42 | 1 |
| patched 7271e2e | 58 | 14 | 42 | 0 |

**13 cells regressed from `verified / refuted` to `vacuous / vacuous`** (count_matches, count_pos_for,
cube, digit_sum, factorial, fib, filter_pos, gcd, gcd_of, largest, root_floor, sum_one, word_count), and
1 from `timeout / refuted` to `vacuous / vacuous` (double_all). These are not all recursive definitions —
`cube`, `digit_sum`, `word_count` are simple — so the smoke-suffix / negation changes make Frama-C ABSTAIN
(vacuous) on real programs it previously verified. That is a coverage regression.

**No soundness regression: 0 new verified twins.** The fix never makes Frama-C accept a wrong twin; every
delta is verify→vacuous (coverage lost), never refute→verify (soundness lost). This independently confirms
E1's robust claim — no kernel accepts a provably-wrong twin — on the whole column, not just the archived
pairs.

## Consequences (honest)

1. **The Frama-C adapter fix (`7271e2e`) is NOT safe to sync to dawnr/t main or upstream as-is** — it
   trades twin-refutation for 13 lost real verifications. It needs rework (the smoke/negation handling must
   not turn a provable real into vacuous). It stays engine-first and out of the published commits.
2. **E1's "Frama-C k7 0→96%, clean engine-first fix" framing was an overclaim.** The fix does move unproved
   twins to refuted (its intent), but it also regresses real coverage; the net paired-gate k7 figure
   (409/426) was measured under this mixed adapter, and some of the paired run's Frama-C "vacuous" cells are
   fix-induced regressions, not only recursive-definition abstentions. The honest statements that survive:
   (a) the fully-adjudicated direct-body matrix and its curve do not depend on this adapter; (b) **zero
   stable VERIFIED twins / 0 new verified twins — no soundness regression — holds and is now confirmed on
   the independent whole column**; (c) the all-seven *refutation* coverage figure is PROVISIONAL pending a
   clean Frama-C fix.

## Evidence
Registered prediction + both runs' per-task tables are retained at
`~/scratch/engine-framac-column-20261014-ddlxf3wh/` on the lab (RESULT.json, baseline-artifacts/,
patched-artifacts/). This comparison is separate from the 426-pair reproducibility experiment.
