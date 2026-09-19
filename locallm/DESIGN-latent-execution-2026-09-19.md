# Combined latent and execution supervision

Status: design fixed before scored outputs; dataset identities, launch schedule
and hardware calibration remain outstanding. This is not launch authorization
by itself and not a claim that the experiment has run.

Question: does token-conditioned latent prediction combine with concrete
execution supervision to improve the owned core's unaided program synthesis?
Sources and method limitations are in
[the research audit](../internal/RESEARCH-ANGLES-2026-09-19.md).

## Four treatments

| Arm | NextLat-style auxiliary loss | Intermediate execution-token loss |
|---|---|---|
| baseline | off | off |
| latent | on | off |
| execution | off | on |
| combined | on | on |

All arms see exactly the same serialized examples in the same order within a
seed, including code-synthesis examples and execution examples. Synthesis
completion and final execution-output tokens are supervised in every arm.
Intermediate execution-state tokens are present in every arm's input but
supervised only in execution/combined. Thus this comparison tests the added
supervision, not exposure to additional examples or a different format. It
does not estimate the effect of introducing traces into a trace-free corpus.

Normalize final-answer/synthesis cross entropy separately from intermediate
execution cross entropy, adding the latter with weight 1.0 when enabled.
Do not average them into a single token loss: longer traces would otherwise
reduce the relative synthesis weight and confound the intended intervention.

Prompts, padding and role delimiters receive no completion loss. Latent loss
uses in-example positions including prompt states; that is explicitly a
representation objective, not assistant-token cross entropy. No examples are
packed together in this first comparison. Reject overlength examples identically
for all arms before freezing the dataset, and report their counts.

Use one-step token-conditioned transitions initially, regression weight 1.0
and KL weight 0.1. These are pilot choices, not copied optimal hyperparameters.
Keep modern architecture, frozen source BPE, optimizer settings and synthesis
decoding fixed. Every arm retains ordinary autoregressive inference.

## Initialization, budget and evaluation

Use each completed 4000-step modern seed checkpoint as the corresponding
initialization for all four treatments. Seeds are 1337, 7 and 42; randomize
arm execution order within seed before launch and record the resulting order.
Initialize identical auxiliary weights across the two latent-enabled arms in
each block. Backbone initialization must be byte-identical within the block.
Reset optimizers identically; do not accidentally resume one arm's training
state into another. Preserve full wrapper/optimizer/RNG state for resumability
and export backbone-only weights separately for inference.

Proposed main budget is 1000 optimizer updates per arm, batch 32, maximum
context 512. Record actual non-padding input tokens, supervised output tokens,
updates, total parameters, wall time and peak memory. Do not call equal padded
tokens equal compute. Calibrate memory before freezing the final launch
configuration, using development data only. No learning-rate or checkpoint
selection based on held-out task scores.

Train on primitive operations and selected compositions. Hold out complete
composition patterns and longer programs, keeping numerical extrapolation a
separate stratum. Freeze task/reference/contract hashes before training. The
735 inspected development traces are infrastructure fixtures, not a sealed
evaluation. Independent references and corruption-rejection checks must cover
every generated operation; a label outside that coverage is not accepted.

Primary response: one greedy program per held-out task, scored by independent
execution tests under fixed output and time caps. No repair or reranking.
Secondary responses: next-state accuracy, final-output accuracy, source loss,
and cost. A subsequent seven-verifier/twin/spec evaluation is required before
calling a gain an improvement on the project's original acceptance target.

Predictions to falsify: combined supervision improves held-out unaided
synthesis by at least 5 percentage points over baseline, with a positive
paired difference for every seed; the factorial interaction
`combined - latent - execution + baseline` is positive. Report these as
separate predictions: additive improvements can help even without synergy.
Keep every failed seed and count malformed, truncated and timed-out outputs
as failures. Training seed and held-out family are the replication levels;
hundreds of variants of one template are not hundreds of independent families.

## Required before launch

- Dataset generator, independent references, family exclusion manifest, hashes
  and card; examples for synthesis as well as execution.
- Tokenized mask audit on at least five complete examples, and proof that
  baseline/treated examples share all input IDs and synthesis targets.
- Trainer with frozen identities, resumable optimizer/RNG state, token/time
  accounting, ordinary inference export and completion/failure monitoring.
- Memory calibration, fixed launch manifest and randomized schedule.
- Scorer tested with correct, incorrect, malformed and timed-out candidates.

The active source study is not part of this intervention and remains frozen.
