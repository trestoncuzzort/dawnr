# v9: v5's own rows plus the strictly filtered self-distilled specifications. Registered 2026-10-22 11:00Z, before training

Step 1 of `internal/RESEARCH-2026-10-22-plateau.md`. v8 added 980 self-distilled rows to the corrected base and, on the
ceiling instrument, taught the student to pass the three-test gate while being wrong against the reference (gate
precision 0.785 to 0.515); under the three-decode protocol its count was not separable from v5's. The literature's
remedy for that failure is removing the weak specifications from the training set (arXiv:2605.30914) and keeping the
share of self-generated rows low (arXiv:2510.05133); curated rows moved 4B models where more rows did not
(arXiv:2603.15510).

## The rows

- The strict re-check (`t/recipes/v9_strict_specs.py`, `out/v9/strict.json`): the 1,103 candidates over 602 problems
  that the 100-draw check at SAFE's 60% floor had kept, re-checked at 1,000 draws with both mutant families required
  at 90%: 27 disagree with the reference outright (they had agreed on 100 draws), 69 reject fewer than 90% of the
  near-miss mutants, 22 more fall short on the cross family or on draws; 985 candidates over 536 problems survive (89%).
- On v5's own base (`t/out/v6-20261018/training-rows.jsonl`, 4,189 rows, sha `e14f766f…`, 288 problems with a
  specification row), 246 of the 536 problems already have a specification row and are skipped; 290 new problems add
  833 rows (543 specification rows, 290 Python rows), built by `t/recipes/v8_spec_rows.py` in the route's own words:
  5,022 rows, sha `f2611fdcc…` (`out/v9/v9-rows.jsonl`, `out/v9/rows.json`). Self-generated share 16.6%.
- Audit (10:47Z): `t/heldout_audit.py --rows out/v9/v9-rows.jsonl --panels --refuse-gpl`: 5,022 rows, 0 flagged; 38 rows
  match problems already out of the panels (the standing decontamination policy, not refused). Receipt
  `release/evidence/v9-rows-2026-10-22.json`. Training queued 10:50Z (desktop unit `dawnr-v9-train`, after the seed-2 run,
  which was at step 610 of 1,275); the laptop's `dawnr-v9-tandem` finishes it.

## Recipe (v5's, unchanged)

Rank 64, alpha 16, dropout 0.1, lr 2e-4, 5 epochs, max-len 2845, batch 1, grad-accum 16, seed 1; trainer
`t/student_sft.py` sha `e43c27df…`; base Qwen/Qwen3.5-4B at 851bf6e8; the desktop at a 150 W cap, started by a unit
that waits for the seed-2 run to finish (`dawnr-v9-train`, RUN=~/v9). Export on the laptop, three decodes on the
laptop's GPU (seed offsets 0, 1000, 2000), grades in the desktop container, the ceiling instrument (20 candidates per
development problem) for the gate's precision, `t/recipes/three_decode_report.py` against v5's three decodes.

## Predictions, with the numbers that falsify them

- **P1 (the gate's precision).** On the ceiling instrument v9's three-test gate precision is at least 0.70 (v5 0.785,
  v8 0.515). Below 0.60 falsifies it: strength filtering at this floor does not stop test-fitting.
- **P2 (the count).** v9's three-decode mean clean is at least 5.0 (v5 5.33, v8 4.33) and the paired reading against
  v5 has at least as many problems up as down. A mean under 4.5, or more problems down than up by two or more,
  falsifies it.
- **P3 (what it means).** P1 and P2 hold: the self-distilled rows are safe at this floor and expert iteration round
  two (the plateau note's step 3) builds on them. P1 falsified: the self-distilled rows are retired, and v10 (repair
  traces, arXiv:2507.02778, and the primed teacher's reference-correct specifications for problems the student fails)
  is built on v5's base alone. P1 holds and P2 falsified: the rows are honest but add nothing the panel can see, and
  the teacher rows, not more self-distillation, are the next data.

The honest prior: the strict filter removed 11% of the candidates, so v9 is close to v8 on v5's base, and v8 under the
protocol was "no gain". The reading that matters most here is P1, the precision, which v8 lost by a wide margin.

Sources: the plateau note and its four verified lists; arXiv:2605.30914; arXiv:2603.15510; arXiv:2510.05133;
arXiv:2410.15756 section 3.2; arXiv:2507.02778.

## Result (2026-10-23 01:55Z): the ceiling instrument and the oracle arm

v9 trained to completion on the desktop (1,535 steps, interrupted once at step 200 by a physical knock on the card and
resumed from its checkpoint; export sha `25a1c6e8…`). The ceiling instrument (20 specification candidates per development
problem the model solves in Python, each judged by the three-test gate and by the reference check at 200 draws,
`release/evidence/v9-ceiling-2026-10-23.json`):

| model | problems with Python | reference-correct specification within 1 / 5 / 20 candidates | gate kept / reference-correct | gate precision |
|---|---|---|---|---|
| v5 | 63 | 12 / 18 / 29 | 93 / 73 | 0.785 |
| v8 | 65 | 15 / 19 / 29 | 130 / 67 | 0.515 |
| v9 | 67 | 16 / 25 / 31 | 154 / 105 | 0.682 |

P1 (precision at least 0.70) is falsified by two hundredths, and its other clause did not fire (0.60 would have said the
strict floor does nothing). The reading in between: the strict floor recovered most of what v8 lost (0.515 to 0.682) while
v9 keeps more candidates and more correct ones than v5 (105 against 73), and it finds a correct specification sooner on
more problems (within five candidates on 25 problems against 18, within twenty on 31 against 29). The 39-call oracle route,
one decode: 67 Python, 22 t, 8 clean, 2 all-seven against v5's 63 / 16 / 7 / 3 (gained 449 and 708, lost 270; all-seven
lost 476), `release/evidence/v9-oracle39-2026-10-23.json`. The frozen-route counts (three decodes on the 240-problem panel,
against v5's six) are recorded below when the arms land.
