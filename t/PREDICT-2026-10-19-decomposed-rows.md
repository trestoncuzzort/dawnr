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
expectation is small:** 481 rows on 4,089 is +12%, where ATLAS's gain came from seven rows per program and
2,751 new programs. The development funnel (v5: 194 specifications scored, 29 kept, 13 proved, 6 clean) says
the specification stage drops 85% before any proof is attempted, and these rows do not touch that stage.
The annotation sub-task gets its own held-out test so the sub-skill is measured whether or not the count moves.

## Data

- Input: `t/out/v6-20261018/corrected-data/training-rows.jsonl`, 4,089 rows, SHA-256
  `8aa1b7528363ebfa149e9b6a18ea9081c4904ff3d8687c240a9ea511d45c4794` (the corrective stage's input).
- Builder: `t/recipes/v7_decomposed_rows.py`. Annotation rows: every unique admitted program that loses at least
  one `invariant` or `assert` line (488 programs over 298 names); the stripped program is the question, the
  admitted program verbatim the answer, under the rows' own system message. `decreases` stays in the question:
  t's grammar requires a measure on every loop, and the first build of this day, which removed it, left 420 of
  455 questions unparseable; it was rebuilt before any training. One name in ten (29 names, 55 programs) is
  held out and never trained on.
- Output: `out/v7/v7-rows.jsonl`, 4,570 rows = 4,089 + 433 annotation + 48 specification, SHA-256
  `05f388b8d3ed763c7c5328e413885624b048c5e3d724ac28d9cefc87fd86159f`; held-out
  `out/v7/annotate-heldout.jsonl` (55 rows, `1ba4bd7c...`); counts in `out/v7/decomposition.json`.
- Audit: `t/heldout_audit.py --panels --refuse-gpl` on the output (result appended below before training).

## Recipe

Exactly v5/v6: Qwen3.5-4B, QLoRA NF4 rank 64 alpha 16 dropout 0.1, lr 2e-4, 5 epochs, max-len 2845, seed 1,
batch 1, grad-accum 16, `t/student_sft.py` at its pinned digest, on this laptop's 8 GB card with `--small-card`.
Output `t/out/v7-20261019/adapter`. Q8 export with the pinned converter; the frozen development protocol
(`t/recipes/v6_server_route.py` arguments, `t/recipes/v6-grade.sh`) on the 95-problem panel.

## Predictions, with the numbers that falsify them

- **P1 (the count).** Clean development answers ≥ 7 and all-seven ≥ 3 of 95 (the corrective stage's C2 floors,
  against v5's 6 and 3). Falsified by clean ≤ 6 or all-seven ≤ 2.
- **P2 (the sub-skill).** On the 55 held-out stripped programs, asked once greedily in the row's own words, the
  v7 student returns a program that parses, keeps every given line, and verifies under the Dafny kernel with
  its twin refuted on at least half (≥ 28); v5 on the same test scores lower. Falsified by v7 ≤ v5 or v7 < 28.
- **P3 (no regression).** Specification-given proofs by all seven ≥ 27 of 33 (the v6 floor V2). Falsified by ≤ 26.
- **P4 (what a null means).** If P1 fails and P2 holds, the annotation sub-skill was not the bottleneck and the
  next row targets the specification stage (85% dropped), by the repair turn (queue row 2) or the dense reward
  (row 3), not by more rows of this kind.

## Audit (2026-10-19 20:40Z, the rebuilt rows, before training)

`python3 t/heldout_audit.py --rows out/v7/v7-rows.jsonl --panels --refuse-gpl --jobs 4 --json out/v7/audit.json`:
4,570 rows, 3,242 distinct t programs, **0 rows flagged**; 67 rows match a problem already out of the panels
(`decontamination-rows-2026-10-05.json`), not refused, as in the parent snapshot. All 433 questions parse.

## Run (2026-10-20)

**Training** moved to Modal on the user's instruction ("do not run this locally", 2026-10-19 21:10Z): H100, the
exact recipe above (`t/recipes/v7_modal.py`), rows sha `05f388b8…` (4,460 of 4,570 used at max-len 2845), 1,395
steps in 14,584 s, final train loss 0.0644; manifest kind `v7-decomposed-rows-sft`. **Export** with the pinned
converter on Modal (`t/recipes/v7_modal_devrun.py --mode export`): `model-Q8_0.gguf`, sha `f3d994d5…`.

**Generation** could not run on Modal: gVisor supports neither bubblewrap nor Landlock, and `py_sandbox` refuses
to run model-written code unsandboxed. It ran on the home desktop `tlab` (RTX 4080, Ubuntu 24.04, real kernel;
set up the same day) with the frozen route and arguments of the Modal recipe
(`t/recipes/v7_desktop_gen.sh`, run on the desktop as `~/v7/v7-gen.sh`: `v6_server_route.py … --pool v5 --python 3 --spec-samples 4 --per-problem 3 --samples 2
--max-new 1024 --batch 16`, llama-server at the pinned commit `f1cee994` with CUDA, 8 slots, ctx 32768,
`enable_thinking: false`), identity `student-v7:f3d994d5…:llama-f1cee994…`. Ubuntu 24.04 blocks bubblewrap's
user namespaces; the first start died on `py_sandbox: no sandbox` and wrote nothing; `t/apparmor-bwrap.sh` fixed
it. One further restart (Ubuntu's `needrestart` restarted the unit behind an unrelated apt install) resumed from the
request cache under the same identity; the output files hold exactly one run's records (python 50, kept 11,
scored 197, raw 10). 08:49–08:54Z: **50 of 95 with a tested Python solution, 11 with a kept specification, 10
answered** (the v5 control's funnel: 51 Python, 13 answered).

**Grading** on Modal (`t/recipes/v7_modal_grade.py`, the engine's pinned kernels): the first attempt failed in
the `tests` step (`KeyError` on the first task id) because the grade image staged `t/` without `nl/`, which the
pool reads; fixed by mounting `nl/` as the serve image does. Result below when the re-run lands.

## Result (2026-10-20 09:45Z): P1 falsified; v5 stays installed

Seven-kernel grade on Modal (the engine's pinned kernels; evaluator hashes identical to the laptop grade of the
v5 control except the panel's path string), `score_levels --larger`, paired by `t/recipes/v7_local_pair.py`
against the v5 control graded 2026-10-19 (`t/out/v6-20261018/proof-results/v5-dev-local-full`):

| arm | Python | t answers | tests pass | ≥1 kernel (after the specification check) | all seven |
|---|---:|---:|---:|---:|---:|
| v5 control | 51 | 13 | 13 | **6** | **3** |
| v7 decomposed rows | 50 | 10 | 10 | **4** | **3** |

Paired clean: v5 6, v7 4, difference −2; gained none; lost 251 and 450 (neither reached a t answer under v7).
All-seven: the same three problems in both arms (476 `big_sum`, 549 `odd_Num_Sum`, 634 `even_Power_Sum`); 543
verifies under five kernels (SPARK tool error, Frama-C and F* abstain); 270 verifies under four but its
specification is false at a counterexample (the specification check removed it, 4 → 3 all-seven before/after).
The specification check: 6 of 10 agree with the problem's solution over 1,000 draws, 4 disagree (186, 270, 67,
708), 0 unchecked. **P1 (clean ≥ 7, all-seven ≥ 3): falsified** (clean 4 ≤ 6; all-seven 3 holds only as a tie).
Receipts: `t/out/v7-20261019/paired-v7-vs-v5.json`, `proof-results-v7/` (levels, verdicts, kernels, spec-check,
evaluator), `t/out/spec-experiment/v7-20261019-dev/` (the answer set with its kernel table).

What moved: nothing upward. The decomposed rows narrowed the funnel (t answers 13 → 10) and left the proof
stage where it was (the same three all-seven answers). **P3** (33 supplied specifications, all seven ≥ 27) was
not run: it is a promotion floor and the candidate is out on P1. **P2** (the annotation sub-skill, 55 held-out
rows, v7 vs v5 under the Dafny kernel) is measured below because P4 keys the next row on it.

## P2 (2026-10-20 09:57Z): holds — v7 passes 40 of 55, v5 passes 0 of 55

On the desktop (`t/recipes/v7_desktop_p2_annotate.sh`): each of the 55 held-out stripped programs asked once,
greedily, in its own words through the pinned server (identities `student-v7:f3d994d5…` and
`student-v5:d855000c…`, both `llama-f1cee994…`), verified by Dafny 4.11.0 (the engine image's pinned zip) with the
twin refuted. v7: 55 parse, 54 keep every given line, 41 verify, **40 pass** all three conditions. v5: 54 parse,
53 keep, 0 verify, **0 pass**. **P2 (v7 ≥ 28 and v7 > v5): holds.** Receipts `release/evidence/v7-p2-annotate-v7.json`,
`v7-p2-annotate-v5.json`; per-row records in `t/out/v7-20261019/p2-annotate/`.

**Reading, by P4.** P1 failed and P2 holds: the annotation sub-skill was learned (0 → 40 of 55) and was not the
bottleneck. The development count did not move because the specification stage still drops most problems before
any proof is attempted (t answers 13 → 10 here). The next row targets that stage — the repair turn (queue row 2) or
the dense reward (row 3) — not more rows of this kind. v5 remains the installed release.
