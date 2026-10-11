# Recover the v5 inputs and make the next comparison reproducible

Registered 2026-10-11 08:03Z, before generating any new comparison answer.

The requested next run needs the released v5 dataset, not just its specification-given subset.
Its recorded identity is 5,095 rows, SHA-256
`848fca29d9399ef91fcb867006e4ff42f60b53e9e2e084e4f1e93dae37811110`
([the original audit](decontamination-rows-2026-10-05.json)). Its six kinds are 933 English answers,
933 proofs beside Python, 839 specifications beside Python, 549 Python solutions, 639
specification-given proofs and 1,202 repairs. `student_rows.py` only builds the specification-given kind.

The restored lab, this checkout, release assets and the full Git history contain no copy of that
file or the scratch builders named in the registrations. The checkout was shallow; the history
search was repeated after fetching all 2,085 commits. The published weights are available and
their three checksums pass. An archive location has been requested while recovery continues.

`restore_run.restore_set(force=False)` recovers 10,563 replies from 33 committed answer sets.
Of these, 203 historically test-passing, proved candidates concern 88 current training problems;
110 were proved by all seven. Their task JSON files are absent, so reconstruction and current
checks are required before any becomes a new training row. Historical verdicts alone do not admit them.
This recovers part of the input chain, not the missing 5,095-row file.

## Work before another training bill

1. Preserve the exact training bytes with every new adapter, before model loading. Verify an optional
   expected hash before allocating a GPU. Refuse an output directory whose frozen data or row-selection
   settings differ, including on checkpoint resume. Record the hash of the bytes actually read, not a
   second reading of a possibly changed source file after training.
2. Retain the recovered archive inventory and a machine-readable identity requirement for v5. A
   missing or different dataset must refuse the claim of a matched rebuild; padding or repeating rows
   to reach 5,095 is not a reconstruction.
3. Measure the saved October 11 candidate against the released v5 weights under identical inference
   and grading settings. This establishes a current baseline while the input recovery is unresolved.

Sources read before implementation: `student_sft.py`, `student_rows.py`, `graded_pool.py`,
`spec_first_rows.py`, `debug_rows.py`, `restore_run.py`, the teacher3 and release-v5 registrations,
and `locallm/dawnr_pipeline.py`'s input fingerprints. The local research mirror is unavailable.

## Matched comparison, fixed before either model answers

Both models are Q8_0, served by the same lab llama.cpp binary (`f1cee9941`), on CPUs with GPU layers
set to zero, one slot and one request at a time, 8,192 context tokens, thinking disabled. Each arm
gets one greedy answer per question and at most 1,024 generated tokens. The problem prompt is `s2`,
which fixes the nested-type spelling already diagnosed in
[the earlier experiment](PREDICT-2026-10-01-several-answers.md). The given-specification prompt is
the exact saved 33-question panel's own prompt. No repairs or extra attempts enter either score.

Report the requested clean-200 problems and all 33 specifications. Also report clean-182, because
18 of the 200 appeared in v5's training data. Nineteen of the 33 specification functions also appeared
in v5 training; the full-33 score is qualified accordingly. Report the old clean-14 subset only if
its exact membership can be recovered; do not infer that membership from the new model's results.

Grading uses the existing seven-kernel path, original tests, 1,000 per-task-seeded reference draws,
the pinned MBPP+ corrections, completeness at least 0.6 and larger-input checks. Publish all answers,
stage counts, task-bound verdicts and paired outcomes. Unknown or partial evidence never becomes a pass.

**Prediction M1:** the small recovered-data candidate does not strictly exceed v5 on both clean-182
all-seven problems and all-33 all-seven specifications. A strict increase on both falsifies M1.
Call a measured win only if clean-182 improves and the specification count does not fall; report the
paired gains and losses, not just totals. This is one candidate and fixed panels already used before,
not independent confirmation or a reproduction of v5's historical 17-call Python-first route.

This comparison adds no cloud spend. CPU services have memory, core and wall-time limits and exit
after saving their answers. Another GPU training run waits for an explicit, audited dataset identity
and its own bounded run registration.

## Input preservation measured

`student_sft.py` now saves `training-rows.jsonl` and `training-data.json` before model imports,
and accepts `--sft-sha256`. The final receipt uses that frozen identity. Previously it reopened
the source after training to calculate the hash: changing the source during training could label
the trained model with bytes it had never read. Reuse checks the snapshot bytes, receipt, row limit
and token limit; legacy checkpoints without input evidence are refused by name.

The [real-data control](out/v5-rebuild-20261011/input-identity-control.json) freezes the prior
406-row input byte for byte and refuses it against v5's registered hash before model dependencies
can load. Thirty row, trainer and generation tests plus two subtests pass on the lab, including
source deletion, changed input, corrupted snapshot, changed selection, incomplete snapshot and
legacy-checkpoint refusals. No GPU is used for these checks.

The [full-history content search](out/v5-rebuild-20261011/history-data-search.json) hashes 1,088
reachable JSONL blobs, decompressing `.jsonl.gz` files first, and finds zero matches for the v5 hash.
This is stronger evidence than the initial filename search; it does not rule out an external backup.
