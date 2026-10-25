# Curate all rows explicitly labelled as specification targets

Registered before the remote build. The inherited census and contract-context correction are recorded in
`t/PREDICT-2026-10-25-baseline-spec-static.md`. The corrected gate preserves task termination measures while
deferring their relationship to an implementation that has not yet been supplied. Measure typing, scope,
specification-function termination and the complete-program checks remain enforced.

## Inputs and procedure

Use `prepare-rows.yml`, operation `curate`, with the explicit manifest scope `all_source_spec`. The candidate
input is the current 7,123-row archive, SHA-256
`eb139437b33b4797023e1f6ef121628588d5397f9f57241695d654071c4457b5`.
Its original 6,727-row prefix is checked against the frozen training input, SHA-256
`2c2eff287493fd8774d1a71bc9e799ca4cc40f21fd9a1b082c17f8206f7351d8`, before filtering.
That identifies the input; this new output is allowed to correct inherited specification rows.

Check only rows whose exact `source` field is `spec`. Drop invalid contracts, apply only the already-supported
checked v0-to-v1 header promotion, and deduplicate exact prompt/answer pairs after that normalization.
Preserve every other row as the same object in the same relative order, including repair and debug examples
whose prompts may deliberately contain faults. Preserve the order and provenance of retained specification
rows. No expression, clause, helper, termination measure or frame is rewritten.

Input analysis finds 1,831 specification rows: 1,637 valid unchanged, 70 needing the checked promotion, and
124 refused. Deduplication removes 45 rows: 42 already-identical pairs and three pairs that become identical
through the checked normalization. The projected output has 1,662 specification targets: 1,593 unchanged
and 69 promoted. The other 5,292 rows are retained. These are input-analysis counts, not a completed build.

The remote build rechecks the serialized retained specifications and runs the full resulting archive through
`heldout_audit.py --panels --refuse-gpl`. Completion requires that whole-data audit. Inputs, row actions,
diagnostics and outputs remain private/encrypted; publish only counts and hashes.

## Predictions and limits

1. The completed archive has exactly 6,954 rows: 5,292 unchanged non-specification rows and 1,662 retained
   specification targets. All retained `source=spec` answers pass the corrected contract check without another
   promotion. Verify every dropped, duplicated and promoted row by its recorded original/new hashes.
2. The whole-data audit has zero current-panel/GPL findings and exactly the existing 339 unparsed blocks.
   No changed clause, measure, non-specification row or ordering is permitted. Any discrepancy fails the build.
3. Under the unchanged tokenizer and 2,845-token training window, no retained row that previously fit becomes
   too long. Report every inherited skip and any contrary result; do not truncate rows or alter the window.

The active training continues with its original frozen inputs. This archive is data for a later update and
establishes no model-quality gain. Other row kinds were preserved, not newly checked for static validity.
The running Cohere JSON pilot keeps its original recipe, stricter gate, accounting code and registered
7,123-row novelty baseline; this curation cannot retroactively change its measured success criteria.

Sources: `t/recipes/curate_spec_rows.py`, `t/recipes/spec_contract.py`, the inherited census registration,
and `release/evidence/baseline-spec-static-2026-10-25.json`.

## Result

Build `40162353906` passed at `d4f4cca8`. All three predictions held. The verified archive contains
**6,954 rows**, SHA-256 `18f3b204abd15c8e497c83840f909877ce5d131a8c23ce6c8633a117e5dbb4f9`.
All 5,292 other rows are identical and ordered, and all 1,662 retained specification targets pass the
corrected contract check without another promotion. Every original/new action hash and the resulting row
sequence were verified. The build removed 124 invalid specification targets, 42 existing duplicates and
three normalization-created duplicates, and retained 69 checked header promotions without changing measures.

The whole-data audit reports zero current-panel/GPL findings and the same 339 inherited unparsed blocks.
Every fenced t block in the selected specification rows parses; the inherited unparsed blocks belong to
other row kinds, which this curation preserves. The encrypted artifact digest, all eight build-source hashes,
input manifest, data and audit hashes, and completion receipt were verified independently.

Offline encoding with the unchanged pinned tokenizer and trainer finds **6,904 fitting rows and 50 inherited
length skips**. One previously overlength row was removed by curation; no retained row newly exceeds 2,845
tokens, and no row was truncated. There were no model calls or new training. The original 6,727-row training
input and the running JSON pilot's 7,123-row novelty baseline remain fixed.

Aggregate receipt: `release/evidence/inherited-spec-curation-2026-10-25.json`.
