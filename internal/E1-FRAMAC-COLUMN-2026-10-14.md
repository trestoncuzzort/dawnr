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

**14 cells go to `vacuous / vacuous`: all are UNMEASURED-RECURSION abstentions.** The 13 that were
`verified / refuted` under baseline (count_matches, count_pos_for, cube, digit_sum, factorial, fib,
filter_pos, gcd, gcd_of, largest, root_floor, sum_one, word_count) plus double_all. Diagnosed directly via
the adapter's own extras: every one carries `"unmeasured_recursion": [<spec fun>]` (t_pow, fact, fibs, gcds,
dsum, t_wc, t_maxs/t_mins, count, dbl, …) and `"vacuity_instrument": "structural backstop"`. These are NOT
"simple" programs (an earlier draft of this note wrongly said cube/digit_sum/word_count were simple — they
each depend on a recursive spec fun). So this is NOT a smoke/negation bug: it is the patched adapter's
DELIBERATE well-foundedness conservatism — the `_wf_obligation` binding, intentionally not relaxed —
refusing to trust a recursive spec fun's axiomatization whose well-foundedness it has not measured. An
ill-founded recursive axiomatization can derive `\false` and prove anything vacuously, which is exactly the
hazard the backstop guards; the baseline verified these 13 by trusting the recursion without that check.

**No soundness regression: 0 new verified twins.** Every delta is verify→vacuous (a refusal), never
refute→verify. The adapter never accepts a wrong twin. This independently confirms E1's robust claim — no
kernel accepts a provably-wrong twin — on the whole column, not just the archived pairs.

## Consequences (honest, corrected)

1. **This is a sound-conservative policy, not a bug.** The patched adapter abstains (vacuous) on spec funs
   with unmeasured recursion instead of trusting their axiomatization — the AGENTS.md rule that an honest
   refusal beats a false verdict. Recovering the 13 would require relaxing the well-foundedness obligation,
   i.e. trusting unmeasured recursion, which is a soundness risk the project deliberately refuses. So the
   all-seven Frama-C coverage figure is not "provisional pending a bug fix" — it reflects this correct,
   deliberate recursion conservatism, and matches E1's paired "Frama-C vacuous on recursive definitions".
2. **The earlier "clean fix / 16 vacuous = recursion / 13 non-recursion regressions" wording is corrected**:
   the Frama-C vacuous cells, on both the paired set and the whole column, are the unmeasured-recursion
   structural abstentions. The fix also does its intended job (moving unproved twins to refuted) — but its
   coverage cost falls entirely on recursive spec funs, by design, soundly.
3. The remaining engineering question (not a correctness defect) is whether to MEASURE well-foundedness for
   these recursive spec funs (discharge the `_wf_obligation`) so Frama-C can soundly verify them instead of
   abstaining — a feature, to land engine-first with its own proof that it stays sound, not a regression fix.

## Evidence
Registered prediction + both runs' per-task tables are retained at
`~/scratch/engine-framac-column-20261014-ddlxf3wh/` on the lab (RESULT.json, baseline-artifacts/,
patched-artifacts/). This comparison is separate from the 426-pair reproducibility experiment.
