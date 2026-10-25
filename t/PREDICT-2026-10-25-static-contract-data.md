# Require static validity for new specification training rows

Registered before the remote curation build. The JSON teacher integration exposed a gap in the existing
specification-only data path: reference agreement and mutant rejection were required, but the engine's static
contract checks were not. All original outputs and results remain archived under their original gate.

## Finding and scope

On the completed Command A pass, 182 of 250 strictly reference-kept specifications are statically valid
unchanged, and 18 more pass the already-supported checked v0-to-v1 header promotion. The other 50 fail static
checks. Twenty-four of the original 149 problems have no remaining valid candidate, leaving 125. Thirty-one
of the invalid candidates include a forbidden reference to the task's own name in its ensures clauses;
other failures include undeclared calls, type mismatches and invalid termination measures. Every original
task survives its parser/printer round trip, so this is not caused by the new JSON representation.

The current 7,176-row draft adds 449 rows to the frozen 6,727-row candidate A archive: 166 reference-Python
rows and 283 specification rows. Static input analysis finds 209 specifications valid unchanged, 24 needing
the existing header promotion, and 50 invalid. Normalization creates three duplicate prompt/answer pairs.
These input counts are evidence for the predictions below, not a completed data build.

The running candidate A experiment and its 6,727-row prefix stay unchanged. This update curates the additions
only. Preserving the registered baseline does not assert that every inherited row passes the new static gate.
The existing 339 unparsed blocks remain a separate inherited audit limitation.

## Procedure

Run `prepare-rows.yml` with `operation=curate`, using `curate_spec_rows.py` on GitHub. Pinned encrypted inputs
contain the original candidate A rows (SHA-256
`2c2eff287493fd8774d1a71bc9e799ca4cc40f21fd9a1b082c17f8206f7351d8`) and the complete 7,176-row draft
(`52404c473208d01cb8f074a540c3cbe988f301c063d976a44fa25c40e76e3c03`). Require an exact preserved prefix.

For added specification rows, apply `check_wf` and an exact printer/parser round trip. Use only the header
promotion already implemented by `spec_first.accept`: a v0 task may become v1 only when that alone clears
every static error. Empty declaration lists are equivalent to their omission by the printer. No expression,
clause, parameter, result type, helper body or frame is repaired. Drop invalid additions, preserve all reference
rows, and deduplicate prompt/answer pairs after normalization. Preserve source tags and retain private action
records with original/new row hashes and refusal reasons.

Recheck every retained added specification, then run the whole resulting archive through
`heldout_audit.py --panels --refuse-gpl`. Write a completion receipt only after that audit passes. Input and
output archives remain encrypted. No model calls, new training, or held-out-182 model reading occurs.

The same static gate now runs before future `v9_strict_specs` reference checks, and row preparation independently
rejects invalid or unnormalized checked sources. The reference draw budget, minimum valid draws and both
mutant-family thresholds remain unchanged. Historical reference-only receipts remain readable and are not
silently reclassified as having passed the new gate.

## Predictions

1. Expect 7,123 output rows: the frozen 6,727 plus 396 additions (166 Python and 230 specifications).
   Expect 50 invalid specifications and three duplicates dropped, with 22 retained header promotions.
   A different count falsifies this prediction and must be explained by the recorded actions.
2. Expect all retained added specifications to pass the static gate without further normalization, the
   entire prefix to remain unchanged and in order, and zero current-panel/GPL findings. Expect exactly
   339 inherited unparsed blocks. Any violation falsifies this prediction.
3. Expect 7,072 rows to fit the unchanged pinned tokenizer and 2,845-token window: the inherited 49 skips
   plus two retained overlong additions give 51 skips. This is an accounting prediction, not a claim that
   every archived row fits. Any different count falsifies it; never truncate a contract to fit.

Keep all results, including failures. The larger JSON teacher pilot waits for this data boundary to be fixed
and tested. Static validity and reference checks do not establish a model-quality gain.

Sources: `t/spec_first.py:accept`, `t/check_wf.py`, `t/surface.py`, `t/recipes/v9_strict_specs.py`,
`t/recipes/prepare_release_rows.py`, and the archived source receipts. Header-promotion precedent:
[spec_first](https://github.com/trestoncuzzort/dawnr/blob/main/t/spec_first.py).
