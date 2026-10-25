# Integrate the completed Cohere outputs as a data update

Registered before the row build. The existing dawnr improves through independent checked updates; this batch
integrates useful teacher material while the rest of the full pass finishes. It neither starts training nor
changes installed weights. Later completed shards can form another audited increment.

## Inputs and procedure

Start from the audited 6,803-row draft, SHA-256
`04ae5b85527d83d64eedb0b796c9400bfbca2a92e873b38ccb0d8e135e7f545c`.
Use completed shards 0, 1, 2, 3, 5, 7, 8 and 9 of teacher run `40138722401`, in that order. Their encrypted artifact
digests were verified and the strict reports reconciled. Every saved candidate passed 1,000 reference draws
with both mutant families at the 0.9 floor. All successful-call ledgers name `command-a-03-2025`.

These eight shards cover 1,364 planned training problems and keep 179 specifications on 110 problems. Ten of
those problems are already covered by the parent draft. The remaining 100 problems carry 163 specifications.
The recorded cost of these completed shards is $171.049850, already inside the full pass's existing allocation.
This is a partial run total, not the final grant reconciliation.

`prepare-rows.yml` uses the existing `prepare_release_rows.py` flow: verify input digests and strict evidence,
preserve source tags, skip already-covered problems, deduplicate identical prompt/answer rows, then run the full
`heldout_audit.py --panels --refuse-gpl` on GitHub. The parent rows retain their order and content. Inputs and
outputs stay encrypted; aggregate input identities are in `release/evidence/cohere-data-2026-10-25a-inputs.json`.

## Predictions

1. Expect 263 added rows (100 reference-Python rows and 163 specification rows), giving 7,066 total. A different
   count falsifies the exact prediction; explain it using the builder's skip/deduplication counts.
2. Expect zero current-panel or GPL-lineage findings and no additional unparsed program blocks beyond the parent's
   339. A new finding or additional unparsed block falsifies this prediction. The inherited blocks remain an audit
   limitation, not evidence that they passed parsing.
3. Expect every added row to fit the pinned Qwen tokenizer's 2,845-token training limit. Any longer row falsifies
   this prediction and must be accounted for before these rows are used in a weight update.

Retain the complete results even if a prediction fails. Useful accepted data can still be kept under the standing
audit rules. No model-quality gain is inferred from a row count, and no held-out-182 model reading occurs here.

Sources: `t/recipes/prepare_release_rows.py`, `t/recipes/v8_spec_rows.py`, the eight original strict reports, and
the source receipts retained under the teacher run.
