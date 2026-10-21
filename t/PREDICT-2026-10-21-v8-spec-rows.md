# v8: self-distilled specification rows at the exact v5 recipe (draft, to be registered before training)

The specification stage is the bottleneck (t/PREDICT-2026-10-21-spec-ceiling.md): the student writes a
reference-correct specification for 29 of 63 problems within twenty candidates and for 18 within five, and its
specification-writing data covers 305 of 2,597 training problems. This row adds, for training problems the data
does not cover, the student's own candidates that the reference check admits, and trains the same recipe on the
corrected v5 snapshot plus those rows. v7's rows are not the base: under both gates v7's specification stage is
narrower than v5's (t/PREDICT-2026-10-21-oracle-route.md).

## What is taken, and from where

- STaR (arXiv:2203.14465) and V-STaR (arXiv:2402.06457): a model's own correct samples become its training data;
  here "correct" is decided by the reference check (agreement with the problem's solution on drawn inputs, 60% of
  mutated outputs rejected, `spec_first.reference_keeps`), never by a model.
- SAFE (arXiv:2410.15756, 3.2): the three-test gate that the candidates pass first, and up to three
  specifications a function.
- The rows are built in the route's own words by `spec_first_rows.build_from_specs`
  (`t/recipes/v8_spec_rows.py`), the same shape as the 550 existing specification rows.

## Data (filled in before training)

- Base: `t/out/v6-20261018/corrected-data/training-rows.jsonl`, 4,089 rows, sha `8aa1b7528363…` (the corrected
  v5 snapshot of 2026-10-18; 305 problems with a specification row).
- Candidates: `t/spec_first.py --reference-python --spec-samples 9 --specs-only` on the 2,597 training problems
  (tag `v5-20261021-selfdistill`, desktop, the installed v5): ten candidates a problem, kept by the three tests
  and then by the reference check at 100 draws.
- Added rows: TO FILL (problems, spec rows, python rows), output `out/v8/v8-rows.jsonl`, sha TO FILL,
  `t/heldout_audit.py --panels --refuse-gpl` on the output: TO FILL.

## Recipe

`t/recipes/v8_desktop_train.sh`: the exact v5 recipe as run for v7 (`t/recipes/v7_modal.py`: rank 64, alpha 16,
dropout 0.1, lr 2e-4, 5 epochs, max-len 2845, seed 1, batch 1, grad-accum 16) with the pinned trainer
(`t/student_sft.py` sha e43c27df…) and base (Qwen/Qwen3.5-4B @ 851bf6e8), on the desktop's RTX 4080 (the
two-step smoke run of 2026-10-21 08:39Z: 13.5 s a step, no chunked loss needed). Export by `t/recipes/v6_export.py`
with the pinned converter; generation on the desktop; the seven-kernel grade in the desktop container.

## Predictions, with the numbers that falsify them

- **P1 (the development verdict, the frozen 17-call route).** Clean at least 7 and all-seven at least 3 on the
  95-problem panel, paired against the v5 control (51 / 13 / 6 / 3), no control problem lost. Clean 6 or fewer,
  or a lost problem, falsifies it.
- **P2 (the sub-skill).** On a twenty-candidate stage-1 run with ten Python attempts (the ceiling instrument,
  `t/recipes/spec_ceiling.py`), problems with a reference-correct specification within five candidates at least
  25 (v5: 18) and within twenty at least 36 (v5: 29). Either below falsifies it.
- **P3 (under the 39-call oracle route).** Clean at least 9 (v5: 7), all-seven at least 4. Clean 8 or fewer
  falsifies it.
- **P4 (what decides the next row).** P2 holds and P1 fails: the proof stage is next (the annotation and
  repair sub-skills, dense reward). P2 fails: self-distillation did not move the skill; the next data is a
  teacher's (an open-weight model run locally, `internal/research-2026-10-21/teacher-scout.md`). P1 holds: v8
  qualifies for the promotion floor (33 supplied specifications, all seven at least 27) before release.
