# Decomposed rows at the exact v5 recipe: registered 2026-10-19 20:52Z, before training

Queue row 1 of `internal/RESEARCH-2026-10-19-number-one-fv.md`. The user's rule for v6 stands: the same recipe
as v5, better data. The data change here is a sub-task decomposition of the corrected v6 snapshot.

## What is taken, and from where

ATLAS (arXiv:2512.10173) turns 2,751 verified Dafny programs into 19,385 rows of six sub-tasks, and a 7B goes
32.4% to 56.9% on DafnyBench (pass@10). The October 2026 verifier-grounded RL paper (arXiv:2610.19298) finds the
largest 4B gain on the annotation sub-task (DafnyBench annotation repair 26.6% to 51.6%). The corrected snapshot
already holds four of ATLAS's six kinds: natural language to a whole task (graded 558, samples 48), natural
language plus a Python solution to a specification (spec 502, the route's own words), specification to body
(proof-py 567, corpus 451, teacher-spec 96) and repair after a failure (debug 552). It holds no annotation rows.
Of its 541 admitted specifications, 502 already had a specification row; 48 pairs were new. **The honest
expectation is small:** 503 rows on 4,089 is +12%, where ATLAS's gain came from seven rows per program and
2,751 new programs. The development funnel (v5: 194 specifications scored, 29 kept, 13 proved, 6 clean) says
the specification stage drops 85% before any proof is attempted, and these rows do not touch that stage.
The annotation sub-task gets its own held-out test so the sub-skill is measured whether or not the count moves.

## Data

- Input: `t/out/v6-20261018/corrected-data/training-rows.jsonl`, 4,089 rows, SHA-256
  `8aa1b7528363ebfa149e9b6a18ea9081c4904ff3d8687c240a9ea511d45c4794` (the corrective stage's input).
- Builder: `t/recipes/v7_decomposed_rows.py`. Annotation rows: every unique admitted program that loses at least
  one `invariant`, `decreases` or `assert` line outside a spec fun's header (514 programs over 312 names); the
  stripped program is the question, the admitted program verbatim the answer, under the rows' own system
  message. One name in ten (31 names, 59 programs) is held out and never trained on.
- Output: `out/v7/v7-rows.jsonl`, 4,592 rows = 4,089 + 455 annotation + 48 specification, SHA-256
  `c7d589aa5da601cb9bf831b7d7fe641bcc75e35e8e428e9694d6b5fe42d371a9`; held-out
  `out/v7/annotate-heldout.jsonl` (59 rows, `69dafe62...`); counts in `out/v7/decomposition.json`.
- Audit: `t/heldout_audit.py --panels --refuse-gpl` on the output (result appended below before training).

## Recipe

Exactly v5/v6: Qwen3.5-4B, QLoRA NF4 rank 64 alpha 16 dropout 0.1, lr 2e-4, 5 epochs, max-len 2845, seed 1,
batch 1, grad-accum 16, `t/student_sft.py` at its pinned digest, on this laptop's 8 GB card with `--small-card`.
Output `t/out/v7-20261019/adapter`. Q8 export with the pinned converter; the frozen development protocol
(`t/recipes/v6_server_route.py` arguments, `t/recipes/v6-grade.sh`) on the 95-problem panel.

## Predictions, with the numbers that falsify them

- **P1 (the count).** Clean development answers ≥ 7 and all-seven ≥ 3 of 95 (the corrective stage's C2 floors,
  against v5's 6 and 3). Falsified by clean ≤ 6 or all-seven ≤ 2.
- **P2 (the sub-skill).** On the 59 held-out stripped programs, asked once greedily in the row's own words, the
  v7 student returns a program that parses, keeps every given line, and verifies under the Dafny kernel with
  its twin refuted on at least half (≥ 30); v5 on the same test scores lower. Falsified by v7 ≤ v5 or v7 < 30.
- **P3 (no regression).** Specification-given proofs by all seven ≥ 27 of 33 (the v6 floor V2). Falsified by ≤ 26.
- **P4 (what a null means).** If P1 fails and P2 holds, the annotation sub-skill was not the bottleneck and the
  next row targets the specification stage (85% dropped), by the repair turn (queue row 2) or the dense reward
  (row 3), not by more rows of this kind.

## Audit (2026-10-19 20:32Z, before training)

`python3 t/heldout_audit.py --rows out/v7/v7-rows.jsonl --panels --refuse-gpl --jobs 4 --json out/v7/audit.json`:
4,592 rows, 3,259 distinct t programs, **0 rows flagged**; 66 rows match a problem already out of the panels
(`decontamination-rows-2026-10-05.json`), not refused, as in the parent snapshot.
