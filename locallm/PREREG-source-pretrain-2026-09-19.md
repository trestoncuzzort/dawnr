# Source-code pretraining pilot, 2026-09-19

Written before training on the newly collected source corpus. This is a test of
the owned core's learning and scaling, not evidence of beating Phi. The order of
work is core reliability, t expansion, corpus validation, then these runs.

## Data and acceptance before launch

Use pinned public CPython, Rust library and mathlib source revisions, with source
text, tests, documentation and proofs kept in their original languages. No
pretrained weights or external tokenizer vocabulary are used. The source builder
must preserve copyright text, snapshot licenses, record revisions and per-file
hashes, remove exact/normalized duplicates, and keep related modules on one side
of an explicit training/validation split. Module grouping is not a proof that all
semantic equivalents have been separated. Benchmark-name exclusions are likewise
a filter, not a claim of zero benchmark contamination.

Freeze the builder manifest and both partition hashes before training. Train BPE
on the training partition only. Check its exact round trip on each partition and
inspect at least ten decoded training windows before scaling. Do not recycle
validation documents into training when a metric disappoints. Public artifacts
contain recipes and measured summaries; fetched source/corpora and checkpoints
stay in ignored output folders with their provenance.

## Infrastructure gate

Two-rank CPU resume must reproduce model, optimizer and rank RNG state exactly.
Four-rank CUDA training must have finite losses/gradients and resumable state.
For a deterministic CUDA comparison, record the determinism settings and compare
uninterrupted training against a stop/resume with the **same total schedule**.
If independent CUDA runs diverge before the stop, investigate that separately
from checkpoint fidelity and retain the failed observation. Any unsupported
deterministic kernel must be reported rather than silently disabled.

Measure available memory and batch fit before picking a training batch. Four
cards are authorized; use all that have room. A capacity failure permits a smaller
microbatch and larger accumulation preserving the effective batch/token budget.
It does not permit changing held-out data.

## Pilot and predictions

First run the medium modern core (12 layers, width 768, 12 heads), context 2048,
8192-entry byte-BPE, from random initialization. Select the largest measured
microbatch that leaves allocation headroom on the least-free participating card;
fix the effective batch before the experiment. Use BF16, AdamW, gradient clipping
at 1, peak learning rate 0.0003, 5% warmup and cosine decay to 10% of peak.
Dropout is 0.0 for this pretraining pilot. The initial horizon is 1000 optimizer
steps. Save and evaluate every 100 steps; record a baseline before step one.

1. All optimizer updates and held-out losses remain finite. Any nonfinite value
   falsifies the stability prediction and stops that run at the last saved state.
2. The final fixed-window held-out loss is at least 20% below the random-weight
   baseline. A smaller drop falsifies the learning prediction. This is an easy
   pipeline check and does not establish useful task completion.
3. Modern architecture's final held-out loss is at least 3% lower than the old GPT
   architecture with the same layer/width/head configuration, tokenizer, data,
   token budget, batch streams, seed and optimizer schedule. A smaller difference
   falsifies this pilot's architecture-benefit prediction. Report exact parameter
   counts and elapsed time; topology counts differ slightly. No default speed
   advantage is predicted: the existing modern-step benchmark was slower.

The old-architecture control gets its own random initialization under the same
seed. Both runs use the exact frozen BPE tokenizer, not independently trained
copies with possibly different IDs. Run order is fixed to modern then GPT for
this initial operational pilot and is a limitation on wall-time comparisons.
Use seed 1337 first; if feasible, repeat the matched comparison under seeds 7 and
42, reporting every run. Do not report the best seed as the result.

## Measurements and next decisions

Record initial and every-100-step train/validation nats per BPE token on fixed
validation windows, token count, model/tokenizer/source hashes, wall time, and
peak allocated memory per rank. These losses are comparable only with the same
token IDs and partition. CUDA allocated memory excludes some driver overhead.
Keep failures and interrupted runs visible. A run may stop at an earlier saved
step for diagnostics, but that is not the preregistered final endpoint.

Inspect fixed completion prompts from each source category after training.
Source-language fluency is descriptive: no proof claim follows from it. The next
stage must measure executable correctness on new held-out tasks and t's exact
seven-kernel real/twin checks, then compare to an explicitly versioned Phi model
under equal task requirements. Until those measurements exist, neither a loss
drop nor a larger model is a Phi win.

## Frozen launch configuration

Recorded after capacity tests and manual data inspection, before the first
training arm. Use corpus v2: 12,880 files, 181,200,765 source bytes, with
48,798,892 training tokens and 10,355,041 validation tokens. The original corpus
was rejected after its decoded windows exposed generated codec tables; v2
removes 65 files and leaves the validation text unchanged. All ten v2 windows
were read in full and accepted; both partitions round-trip exactly.

- Train SHA-256: `737af894db2a6060a41ba903f3d8adf8f1197036653604047426458e9cb61ffb`
- Validation SHA-256: `c73c6af8f3fcdbdefc93babcfa536cf81bc2eb818b3732a01bb191068e0c31be`
- Tokenizer file SHA-256: `f2d09c7a155474d2b34fdfc4ee38f1c0f3a9ed34ca1585053f1888661a617b5b`
- Audit SHA-256: `f772ec9fa09a5b93461c240d17e8f5b0aa07bfdbdec205e7001d63f28cfa1d9a`

The fixed batch is eight sequences per GPU on four GPUs, accumulation one,
context 2048: 65,536 tokens per update and 65,536,000 tokens per arm. No gradient
checkpointing; deterministic BF16 training with four CPU threads per rank.
Capacity tests measured 11.90 GiB reserved per rank for the modern model;
admission requires at least 13 GiB free per GPU. All three seeds (1337, 7, 42)
are now planned, modern followed by GPT for each seed. Both architectures use
12 layers, width 768 and 12 heads; modern has 91,245,312 parameters and GPT has
92,920,320. Learning rate, dropout, warmup, horizon, and evaluation cadence
remain as specified above. The study ledger binds the exact training source,
runtime, corpus and tokenizer and preserves every attempt. A failure stops the
sequence for diagnosis; recovery resumes a saved checkpoint where compatible.
