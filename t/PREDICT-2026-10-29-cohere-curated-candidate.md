# Train the existing audited Cohere-curated candidate on two seeds

The goal is an incremental Dawnr model improvement using Cohere internally. The product remains local.
This experiment uses the data already accepted on 2026-10-25 while the new `json-v2` teacher yield trial runs
separately. New teacher results are not inserted into an in-progress training run.

## Frozen data and recipe

Dataset: 6,954 rows, SHA-256 `18f3b204abd15c8e497c83840f909877ce5d131a8c23ce6c8633a117e5dbb4f9`, from the
verified inherited-specification curation. The panel/GPL audit reports no findings; the unchanged 339 unparsed
blocks in other row kinds remain a recorded limitation. All 1,662 retained specification targets passed the
corrected static declaration checks. The established tokenizer yields 6,904 fitting rows and 50 skips at 2,845
tokens, without truncation. [Dataset and window evidence](../release/evidence/inherited-spec-curation-2026-10-25.json).

The dataset includes the previously accepted Cohere teacher specifications and associated reference-Python rows.
It also includes static curation of inherited specifications. This is a combined dataset change, not an isolated
causal estimate of Cohere's contribution. Original candidate A and all its archives are preserved.

Use Qwen/Qwen3.5-4B at `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`; trainer `t/student_sft.py` at
`e43c27df1ee1e796b1799d38a16e0c5725dd09df762be3fabb2940ad8cb4a46f`. Keep the published model's recipe:
NF4 double quantization with bf16 compute, LoRA rank 64, alpha 16, dropout 0.1, all linear modules, learning rate
2e-4, five epochs, batch one, gradient accumulation 16, response-only loss, and seeds 1 and 2. Expect 2,160
optimizer steps per seed. Save complete checkpoints every 100 steps; resume only against the same pinned inputs.

The private worker validates all input hashes, the dataset audit, tokenization counts, checkpoint identity,
final recipe and finite adapter tensors. It reuses the original trainer, exporter and development decoder.
Its private input manifest SHA-256 is `cb3c1969978bdf7285a717cb1fd1da1abf7b7bae17b2caab99ff4a5ce000fafe`.
Training and model decoding run on cloud compute; no new training runs on the laptop or desktop.

### Parallel second seed, requested before candidate measurements

On October 29 the user requested faster execution. Seed 1 is already running on
the L4. Move the unstarted second seed to one Modal H100 concurrently, using the
same frozen input manifest, original worker and trainer bytes, pinned Python
packages, reference kernels, optimizer settings, row window and seed 2. This is
a hardware and scheduling amendment, not an added seed or a data change. Record
the actual device and package versions; it does not establish an isolated causal
effect of the training data or hardware.

Before GPU execution, remotely verify all input digests and the 6,904 fitting
rows. Bound the H100 call to eight hours with no automatic retry and a $40
planning allowance, including CPU and memory. The existing Modal account's
monthly free credits are used, so this is paid compute under the user's compute
authorization. Independently verify the completed adapter and import it into the
original seed-2 location before its serial worker would train it. Prevent a
duplicate second-seed run; preserve any interrupted attempt and its diagnostics.
Export, decode, grade and apply the existing release decision on the original
registered pipeline. All five release conditions stay in force.

Prediction before launch: the second seed completes within eight hours and
before the original first seed. A measured progress interval will refine the ETA;
hardware specifications alone are not a throughput measurement. If the remote
call fails or the adoption checks disagree, preserve that failure and its
checkpoints rather than starting an unregistered replacement.
[Execution and cost receipt](../release/evidence/parallel-seed2-inputs-2026-10-29.json),
[Modal training pattern](https://modal.com/docs/examples/long-training),
[current pricing](https://modal.com/pricing).

The parallel call is now active after its remote input/tokenizer checks passed.
The completion collector observes that original call only. On success it verifies
the final manifest and every adapter file, then sends the bounded archive to the
original cloud host. The unchanged worker rechecks the completed run and finite
tensors before an atomic import that refuses an existing second-seed directory.
Only the orchestration shell is briefly held during that import; its first-seed
training child continues. The shell is resumed through a stable process handle,
with a recovery record for an interrupted handoff. The ordinary worker will then
read the completed second seed and skip duplicate training.

Twenty-three focused checks cover this transport, immutable result binding,
exclusive import and harmless process controls. The actual adapter is not yet
complete or imported. [Handoff checks](../release/evidence/parallel-seed2-handoff-2026-10-29.json).

The observed H100 rate may exceed its original eight-hour bound. Register one
conditional continuation of seed 2, with unchanged inputs and training code,
from the latest complete checkpoint at step 1,900 or later. Only the exact
original execution timeout permits it; observation timeouts do not. Stop the
original dedicated container before validating the checkpoint and retain all
optimizer, scheduler and random states. The additional GPU call is bounded to
90 minutes with no retries, within a revised $50 Modal planning allowance.
Fourteen software controls pass. No continuation has been allocated and no
model-quality requirement changes.
[Continuation registration](../release/evidence/parallel-seed2-continuation-2026-10-29.json).

Before launch, the cache-seeding receipt bug was reproduced and corrected. The cloud
checkout includes that correction and records the new seeder hash. The frozen trainer
digest, data, recipe and release criteria above are unchanged. See
[the cache-seeding record](PREDICT-2026-10-29-cache-seeding.md). The deployment input
manifest is `90e8e5486cba022d15bd8bea54837ba20cdf23eed3b4e257c4c03990b516bae0`;
only its execution revision and annotation changed. The initial manifest above remains
the data registration. [Execution inputs](../release/evidence/cohere-curated-execution-inputs-2026-10-29.json)
bind the private worker hashes and the unchanged precision instrument before training.

## Predictions and release decision

The completed matched grader control preserves the predicted baseline counts:
20, 19 and 19 clean; 9, 8 and 9 all-seven. All problem sets and emitted source
bytes match. Nine timeout-related cell changes are recorded without reruns.
Before candidate grading, freeze workflow `a51043aab69e34f4c2e939169f9ee27c2e0701ba`
at `r61-grading-20261029`, whose development grader is
`1e033b50c2c53fb3d40932d9561e1a8eefe9aa7d`. Both collectors now use this pin;
the precision and spec33 workflows are byte-identical to the previous pin.
The 149 focused checks and six reaudited baseline parts passed. See
[the matched control](../release/evidence/matched-grading-control-2026-10-29.json).

1. Both seeds complete exactly 2,160 steps on 6,904 usable rows, preserving the data hash and producing finite weights.
2. On the clean 206 development problems, the six candidate decodes have mean clean coverage of at least 21
   problems and mean all-seven coverage of at least 10. The released model's matched means are 19.33 and 8.67.
3. The candidate passes the existing release gate: more improved than regressed problems and paired permutation
   p at or below 0.05; specification-gate precision at least 0.70; at least 27 of the 33 given specifications
   proved by all seven; then a single held-out-182 reading at least 17 clean and 12 all-seven; and the laptop
   functionality, memory and timing condition. Report each condition independently. A mean alone is not a verdict.

Decode both seeds on the existing development panels with offsets 0, 1000 and 2000, preserving every completed
arm and its input hashes. Grade with the pinned cloud grader and compare through `three_decode_report.py` with
three baseline and six candidate decodes. Precision and spec33 use the established instruments. The held-out
182 never selects a candidate and is not decoded before the development, precision and spec33 decision.

Before any held-out reading, select the release seed among those meeting the precision and spec33 thresholds
by mean clean coverage across its three development decodes on the 206, then mean all-seven coverage, then
lower seed number. The combined six-decode paired release gate still must pass. If neither seed qualifies,
promote neither. If the selected seed fails the held-out reading, do not try the other seed on that panel.

A failed condition leaves released weights unchanged. Preserve failures and their receipts. A passing candidate
must still complete packaging, install tests, local final testing and publication; training completion is not a release.

Sources: `internal/RELEASE-6.0-PLAN.md`, `t/recipes/v7_modal.py`, `t/recipes/v6_export.py`,
`t/recipes/release_arms.sh`, `t/recipes/spec33.sh`, and the existing dataset audit receipts.
