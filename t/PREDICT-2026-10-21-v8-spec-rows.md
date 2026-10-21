# v8: self-distilled specification rows at the exact v5 recipe: registered 2026-10-21 17:29Z, before training

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
- Candidates: `t/spec_first.py --reference-python --spec-samples 4 --specs-only` on the 2,597 training problems
  (tag `v5-20261021-selfdistill`, desktop, the installed v5): five candidates a problem (the ceiling run found 18
  of the 29 right ones within five and 24 within ten; ten would have cost seven more desktop hours before any
  training, and the cache lets a later pass extend to ten), kept by the three tests and then by the reference
  check at 100 draws. Prompts past the server's slot context (a few long problems) are refused and count as
  no candidate.
- The candidate run finished 2026-10-21 12:40Z: 602 of the 2,597 training problems have a specification kept by the
  three tests and the reference check (1,103 specifications; the reference check dropped 625 the tests had kept);
  `t/out/v5-repair-20261021/spec-experiment/v5-20261021-selfdistill/kept-specs.jsonl` (sha `549ca386…`).
- Rows built 2026-10-21 17:25Z by `t/recipes/v8_spec_rows.py` (report `out/v8/rows.json`): of the 602 problems, 256
  already had a specification row in the base and were skipped; the other 346 gave 637 specification rows (up to
  three a problem, the route's own cap) and 343 python rows; 980 rows added, output `out/v8/v8-rows.jsonl`, 5,069
  rows, sha `a279cc9a1b878865a447c61a67fc14250c39869c915e0cf7d3932ba6faf2cd03`.
- Audit `t/heldout_audit.py --rows out/v8/v8-rows.jsonl --panels --refuse-gpl --jobs 4` (2026-10-21 17:27Z,
  `out/v8/audit.json`): 5,069 rows, 3,428 distinct t programs, 0 rows flagged against the held-out and development
  panels; 35 rows match problems already out of the panels, not refused. Specification rows now cover 621 training
  problems (275 before).
- Teacher audition the same day (`teacher9b-20261021-spec`, Qwen3.5-9B at Q4 on the development panel, the ceiling
  instrument): Python for 83 of 95 problems (the student: 63) and zero usable specifications, because it has never
  seen the t language. A teacher needs the grammar and worked t examples in its prompt, or writes contracts in a
  language it knows for translation; the self-distilled rows do not depend on it.
- Primed audition the same evening (`teacher9b-20261021-primer`, the same model with `--spec-primer`, a syntax card
  and six worked examples from training problems, on the laptop's GPU): Python for 82 of 95; 249 candidates scored;
  reference-correct specifications for 15 problems (13 within five candidates), against the student's 29 within
  twenty; 9 of the 15 the student also gets, 6 it does not (5, 128, 328, 608, 905, 910), so the union is 35 of the
  panel. The primer makes the 9B a weak but complementary specification writer: a teacher row would add rows for
  about a tenth more problems, at ten candidates a problem; not before v8 is measured.

## Recipe

Training ran on a Modal H100 from 17:43Z to 19:30Z (steps 1 to 500, checkpoints 400 and 500 on the volume), was stopped
by the user over the charge. The laptop's RTX 5050 (8 GB) cannot resume it: `--small-card` swaps the paged 32-bit AdamW
for plain AdamW, whose state cannot load the paged optimizer's checkpoint (KeyError `exp_avg`, 20:25Z), and the exact
arguments need about 10.5 GB (out of memory at the first step, 20:32Z). The checkpoint is staged on the desktop
(`~/v8/adapter`, torch 2.9.1+cu129 like the H100), where `t/recipes/v8_desktop_train.sh` resumes it with the exact
arguments once the card holds, or the paid run resumes on Modal with the user's yes.


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
