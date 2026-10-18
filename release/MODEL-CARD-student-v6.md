# Dawnr v6 candidate (unreleased)

This candidate has completed training and failed to improve on v5 in development.
The installed release remains student-v5 until the matched evaluation and
release checks pass. The [registered comparison](../t/PREDICT-2026-10-18-v6.md)
defines the acceptance conditions.

## Training

The base is Qwen/Qwen3.5-4B at revision
`851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`. The candidate starts with v5's
QLoRA recipe: NF4 with double quantization and bf16 compute, rank 64, alpha 16,
dropout 0.1, all linear layers, learning rate 2e-4, five epochs, batch 1 with
16 gradient accumulation steps, maximum row length 2,845, and seed 1.

The exact input contains 4,189 rows. Tokenization admits 4,073 and drops 116
whole rows that exceed the length limit. The run completed all 1,275 optimizer
steps. A complete checkpoint, including optimizer and RNG state, was moved
after step 300; the base revision, trainer bytes, data bytes, and package
versions were checked before resuming on the new GPU.

Checkpoint 400 was then preserved and resumed on H100 after a bounded
throughput probe. The probe performed ten updates on a separate copy of
checkpoint 300; its weights are excluded from evaluation. The full training
run retains its recipe and optimizer state across the moves.

The input identity, construction, and panel hashes are in
[DATA-student-v6.json](DATA-student-v6.json). The input snapshot remains beside
the adapter. The [training receipt](evidence/v6-training-complete.json) records
the final metrics, all 25 saved-file hashes, and complete checkpoints at steps
1,200 and 1,275. The final invocation resumed at step 400; its reported loss
and duration describe that invocation. The adapter was transferred to the
export worker with its checksums verified.

## Data and its limits

The input is a deduplicated mixture of the corrected v5 reconstruction and
later training data. It is not the original v5 dataset with rows appended:
the shipped v5 trained on 5,095 rows before its overlap and lineage corrections.
The raw mixture has 5,073 rows; keeping the first unique prompt/answer pair
produces the candidate's 4,189 rows.

There are 909 `judge-python` rows, each marked `proof: none`. They are Python
programs checked against stored uDebug outputs. All match their recorded source
programs, and none belongs to the 377 withheld judge questions. Six historical
receipts counted inputs without stored expected outputs in their totals; fresh
replays pass every usable stored output. One replay needed the original judge
budget after timing out under a shorter one.

The remaining rows include English-to-program examples, specifications, proofs
from Python, and repair examples. They are not 3,280 independent all-seven
proofs. The current panel and GPL-lineage audit flags no row, and the separate
33-specification textual audit finds no match. All 182 unparsed t blocks are
deliberately broken repair prompts; none is a chosen answer. These checks do
not establish universal semantic independence across arbitrary programs.

## Evaluation and release gate

Both preserved checkpoints and their registered equal-weight average have
completed the same Q8_0 development evaluation.
All accepted t answers pass the problem examples; the clean counts also require
formal proof and the independent specification checks.

| Fixed development-95 | V5 | V6 step 400 | V6 step 1275 | V6 average |
|---|---:|---:|---:|---:|
| Tested Python solutions | 51 | 60 | 46 | 53 |
| Accepted t answers | 13 | 9 | 10 | 9 |
| Clean answers, at least one kernel | 6 | 4 | 4 | 4 |
| Clean answers, all seven kernels | 3 | 3 | 2 | 1 |

The [early receipt](evidence/v6-development-early.json) and
[final receipt](evidence/v6-development-final.json) preserve the paired results.
The final checkpoint loses problems 543 and 634 against v5 and gains none.
Its [kernel matrix](evidence/v6-dev-final-kernels.md) records refusals and failures.
The [average receipt](evidence/v6-development-average.json) records four clean
answers and one all-seven answer. It gains none over v5 and loses problems
549 and 634. Its [kernel matrix](evidence/v6-dev-average-kernels.md) retains
refusals and failures. The average adds no training updates or data and fails
the registered gate of seven clean answers and at least three all-seven
answers. No checkpoint has qualified for promotion, and no new held-out
model answers have been generated.

A bounded [training-contract audit](evidence/v6-training-strength-full.json)
finds surviving behavior-changing mutants in 102 of 1,011 unique training
programs; nine timeouts remain unknown and three searches are capped. Some
survivors reflect intended latitude. Reviewed English examples expose missing
output-length or result-selection constraints. These findings motivate
data-repair controls, but do not establish a cause of the development failures
or automatically change training admission.

Two [reviewed repair controls](evidence/v6-training-repair-interpreter.json)
eliminate their sampled surviving mutants under the interpreter. The
[native comparison](evidence/v6-training-repair-native.json) does not satisfy
its prediction: one repaired contract loses a passing kernel, while the
other retains two. No training rows were changed on the basis of these
controls, and their interpreter results are not counted as all-seven proofs.

An equivalent [length-ordered repair](evidence/v6-length-order-control.json)
restores the fresh original's six passing kernels while still rejecting the
seven sampled surviving mutants. F* still does not refute the twin, so the
repair is not counted as all-seven. Reference checks of flagged training
programs also exposed a missing APPS input; a
[preserved copy](evidence/v6-restored-reference-input.json) matches the original
compressed and uncompressed manifest hashes. The completed
[reference audit](evidence/v6-training-reference-audit.json) confirms 23 of
44 flagged programs under the full gate. Nineteen fail completeness, one
disagrees on a larger input, and one has no valid larger draws.

All seven [direct repairs](evidence/v6-direct-repair-controls.json) retain
their fresh original proof counts; five pass all seven systems. These seven
and the two earlier successful repairs all pass the unchanged
[reference checks](evidence/v6-repaired-reference-audit.json). A separate
[corrected snapshot](evidence/v6-corrected-data.json) updates 41 prompt/answer rows and quarantines 100 positive
t targets whose unrepaired contracts failed that audit. Its 4,089 rows retain
all 909 judge-Python rows unchanged. Original data and quarantined rows are
preserved. The fixed split, lineage and GPL-origin audit flags no row; this
does not establish that a corrected model will outperform v5.

The next registered trial initializes from the preserved step-400 adapter,
uses a fresh optimizer and the corrected data, and runs one epoch at `2e-5`.
Its [CPU preflight](evidence/v6-corrective-preflight.json) reproduces the exact
token stream on the training image: 3,980 rows fit, 109 exceed the original
2,845-token limit, and all 41 repaired rows fit. The trial is 249 updates.
It must still pass the existing development and release gates.

A [follow-up audit](evidence/v6-structure-audit.json) finds all 994 distinct
nonempty programs in that active input structurally valid under the inference
gate. Three corpus views of weak contracts remained because their problem
IDs appeared in names instead of `task_id`. The builder now recognizes those
identities; a separate, untrained 4,086-row snapshot removes them and passes
the same lineage audit. The active trial remains tied to its 4,089-row input.

The correct-source specification control currently reaches 32/33 in all seven
proof systems ([complete table](evidence/v6-prover-controls.md)). Frama-C rejects one twin certificate; all 33 pass in each of
the other six systems. That instrument limitation is retained for both arms.

The full 33-specification panel includes 19 functions whose behavior appeared
in v5 training under another name, as recorded in the
[v5 model card](MODEL-CARD-student-v5.md). Its score is a compatibility
comparison, not a wholly unseen generalization measurement for v5.

The matched comparison uses Q8_0 versions of v5 and v6, the same pinned
llama.cpp server, the same prompts and panels, and the same Python-first route.
It permits at most 17 calls per programming problem, with 1,024 new tokens per
call. Development evaluation comes first. The held-out panel cannot guide
candidate training or selection.

The held-out driver loads the versioned GGUF shards intended for installation
and checks their manifest before serving. Packaging compares every tensor's
name, dimensions, type and bytes with the Q8 export, and preserves its model
metadata. The [step-400 packaging probe](evidence/v6-packaging-probe.json)
passed all 426 tensors and a native loader/API check. The final checkpoint's
[packaging receipt](evidence/v6-packaging-final.json) also confirms all 426
tensors and metadata. Installed-format quality evaluation remains pending;
successful packaging does not qualify the failed development candidate.

| Measurement | Historical v5 | New matched v5 | Candidate |
|---|---:|---|---|
| Clean-182, at least one kernel, including specification checks | 17 | pending | pending |
| Clean-182, all seven kernels | 12 | pending | pending |
| Supplied specifications, all seven kernels | 27/33 | pending | pending |

The historical programming result used full-precision HF decoding. It must not
be treated as a fresh matched Q8_0 result. The candidate must improve the new
matched clean-182 count by at least one while reaching at least 18, retain at
least the matched all-seven count and 12, and retain at least the matched
specification count and 27/33. The installed-format artifact must retain the
qualifying results. A one-problem gain on one training seed alone would not
establish a general gain across seeds.

V6 has not been published or selected as the installer default. The
[rolling channel](ROLLING.md) currently serves v5.

The application has separate terminal-usability improvements: help before
installation, command examples, custom storage paths, and a refreshed model
manifest. A fresh CPU installation and one real read-only repository task
passed on Ubuntu 24.04.5; the [receipt](evidence/v6-terminal-smoke.json) states
that check's scope. This application result is separate from model qualification.

A further terminal test switched from a repository task to checked code on
the same 8-GiB CPU machine. Automatic memory settings avoided the loading
failures seen in the first two trials. Dafny and SPARK proved a three-example
`double` function and rejected its broken twin; certificate replay passed.
The [checked-code receipt](evidence/v6-terminal-checked-code.json) limits this
result to the tested example and installed v5 weights.
