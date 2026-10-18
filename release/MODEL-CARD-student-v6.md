# Dawnr v6 candidate (unreleased)

This candidate has completed training. No improvement over v5 has been established.
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

The preserved step-400 adapter has completed an early development pass at
Q8_0. On the fixed 95 problems, v5 produced 51 test-passing Python solutions
and 13 accepted t answers; step 400 produced 60 and 9 respectively. All saved
t answers pass their problem tests. After full formal and specification
scoring, v5 has 6/95 answers at one or more kernels and 3/95 at all seven;
step 400 has 4/95 and 3/95. The [paired receipt](evidence/v6-development-early.json)
records the matching protocols, scores, and individual outcomes. The early checkpoint has not demonstrated an
improvement. The full five-epoch candidate has completed training and is being
exported for development evaluation.

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
passed all 426 tensors and a native loader/API check. Final-candidate packaging
and evaluation are still pending.

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
