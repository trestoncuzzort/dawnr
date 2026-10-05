# The round-4 student on rows built through the row gates, three seeds, scored on the corrected panels: registered before any of it trains

Registered 2026-10-05 05:37Z. Two things changed since the last student round
(`PREDICT-2026-10-04-teacher3-student.md`), and this round is the first to carry both.

1. **Round 4's documents.** The prompted Qwen3.5-27B on our own cards admitted 114 training documents and 124
   specification documents in six or seven kernels (`PREDICT-2026-10-04-teacher-round4-27b.md`), which by that
   round's rule join the pool for the next registered student round.
2. **The audit of 2026-10-05** (`DECONTAMINATION-2026-10-05.md`). The rows every earlier student trained on held 18
   of the clean 200 and 5 of the 100 dev problems under other names, 61 rows of MBPP-DFY lineage (GPL-3.0 at the
   source), and a same-behaviour program for 19 of the 33 "held-out" specification questions. The panels are now
   the clean 182 and the dev 95, and a row build ends at two gates.

## The rows (`~/scratch/teacher4/pool.sh` and `finalize.sh`; built 05:15Z to 05:34Z, before this registration, and nothing trained)

`sft-student-teacher4.jsonl`, **5,479 rows**, sha256 ccd49a66059662f4...:

| step | rows |
|---|---:|
| teacher3's rows (the published model's), byte for byte | 5,095 |
| + round 4's training documents through the pool's own route (112 of the 114 pass its gates again under their own names, by level 5 to 7: 2, 30, 80), with their spec-first rows | + 448 |
| + round 4's 124 specification documents as specification-given rows | + 124 |
| `t/heldout_audit.py --panels --refuse-gpl`: MBPP-DFY lineage (61 of the base's rows, 33 of the new specification rows) | - 94 |
| the same gate: two new rows are twins of held-out MBPP 167, which is still in the panel | - 2 |
| `t/spec_panel.py draw`: 40 new held-out specification questions, and every row that names one or behaves as one | - 87 |
| `t/student_rows.py leaks_heldout` against the old 33 and the new 40 (name, text, specification) | - 5 |
| `t/spec_panel.py check` against the clean specification panel (below) | - 0 |
| `t/heldout_audit.py` once more, with the wider panel (`PREDICT-2026-10-05-wider-reader.md`) | - 0 |
| | **5,479** |

4,963 of the base's rows stay and 516 of the 572 new ones. 445 rows match a problem that is already out of a panel
(the 18, the 5, the 32 of 2026-09-21); they cost no measurement and are kept, as the gate's rule says. The file passes
both gates as it stands (exit 0 and 0).

**The clean specification panel, 54 questions** (`~/scratch/teacher4/spec-panel-clean.jsonl`). The 14 of the old 33
that no row of the published model answers by behaviour (`t/spec_panel.py check` finds a row for the other 19), and
40 new ones: documents with a specification-given row, proved by all seven, no MBPP-DFY lineage, whose function at
most 4 rows held (134 eligible of 364), taken in the order of sha256("spec-panel-2026-10-05:" + document), their 87
rows removed. 18 of the 40 are APPS problems, 6 DafnyBench programs; they are rarer functions than the old 33 by
construction, so a lower score on them is expected and is the honest one. The published model trained on these 40 and
cannot be measured on them.

## Training and measurement

The shipped recipe exactly (`t/student_sft.py`, Qwen3.5-4B, rank 64, five epochs, rows up to 2,845 tokens), seeds 1,
2 and 3, each alone on one of the lab's cards 1 to 3, all free now. From each merged model, in this order:

- **the clean 182** by the shipped seeds' route (`t/spec_first.py --python 3`), graded with the scoreboard's
  instrument (the seven kernels, 1,000 draws from each task's own generator against MBPP+'s references, complete
  specifications only);
- **the 73 specification questions** (the old 33 and the new 40), one greedy answer each at full precision, the
  strict gates of `t/score_spec_given.py`, all seven kernels;
- **the wider 114** (`PREDICT-2026-10-05-wider-reader.md`), same route, pool v7.

## Predictions

- **U1.** The three seeds' mean on the clean 182 is at least 16 at one kernel and at least 10 by all seven (the
  published recipe's seeds read 18, 18, 14 and 12, 10, 8: means 16.7 and 10.0).
- **U2.** No seed proves fewer than 13 at one kernel or fewer than 8 by all seven.
- **U3.** On the new 40 specification questions every seed proves at least 20 by all seven; on the old 33 seed 1
  proves at least 26 (the published model at Q8_0: 27).

Section 1 is judged on these seeds by its own rule, on the panel of record: doubled when every seed proves at least
14 at one kernel and 10 by all seven (twice Phi-4-mini under `t`'s grammar on the clean 182, 7 and 5).

## The release rule, fixed now

The candidate is seed 1, whatever the seeds read. It is exported to Q8_0 and released, replacing `student-v5`, if
at Q8_0 through llama-server: **R1** at least 26 of the old 33 by all seven; **R2** at least 3 of the dev 95 proved on
complete specifications from one greedy answer; **R3** its own measurement above reads at least 17 and 9 on the clean
182. It would be the first release with no row of MBPP-DFY lineage and with rows that passed both gates. Its score on
the new 40 is reported with it and gates nothing this once: no model has been measured there before.

## What it cannot show

How much of any change is round 4's documents and how much the 148 rows the gates and the draw took out: both
changed at once, and the published recipe was not retrained on its own rows minus those. The prompted comparisons on
the specification panel and on the wider 114 are not in this round.
