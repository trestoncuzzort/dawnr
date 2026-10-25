# Integrate the final completed Cohere sources

Registered before the row build. This is another data update to the existing dawnr project.
It uses the remaining useful outputs from completed teacher runs, without starting training.

## Inputs and procedure

Start with the audited 7,066-row draft, SHA-256
`633ededffc2be4718c3341393845272268fdbe316d10e7e2fa4549f74ce606dc`.
Apply Command A shards 4 and 6 of run `40138722401`, then the bounded North pilot
`40149580546`, in that order. All encrypted source artifact digests were verified. The full
Command A collection matched all 280 archived files; the North collection matched all 516.

After skipping problems covered by the parent, shard 4 contributes 20 problems and 36
specifications, shard 6 contributes 18 and 34, and North contributes one and one. North's
failed expansion conditions remain failed; retaining its one accepted example does not
qualify that recipe for more calls. Source labels preserve the actual model and run.

Use the existing `prepare-rows.yml` and `prepare_release_rows.py`: validate strict evidence,
skip covered problems, deduplicate prompt/answer pairs, and audit the complete result with
`heldout_audit.py --panels --refuse-gpl` on GitHub. Preserve the parent rows and their order.
Inputs and outputs stay encrypted. Aggregate identities are in
`release/evidence/cohere-data-2026-10-25b-inputs.json`.

The reference checks requested 1,000 draws, retaining the existing minimum of 10 valid
draws and the 0.9 floor on both mutant families. Actual valid draws for these 71 proposed
specifications range from 20 to 1,000; the input receipt records their distribution.
No acceptance rule changes.

## Predictions

1. Expect 110 added rows: 39 reference-Python rows and 71 specification rows, for 7,176
   total. A different count falsifies this prediction and must be explained by the builder's
   skip and deduplication records.
2. Expect zero current-panel or GPL-lineage findings, with exactly the parent's 339
   unparsed blocks and no new ones. A new finding or additional unparsed block falsifies
   this prediction. Inherited unparsed blocks remain a coverage limitation.
3. Expect every added row to fit the pinned Qwen tokenizer's 2,845-token training limit.
   Any longer row falsifies this prediction and needs accounting before weight training.

Keep complete results even if a prediction fails. Counts do not establish model-quality
gains. This build performs no held-out-182 model reading.

Sources: `t/recipes/prepare_release_rows.py`, `t/recipes/v8_spec_rows.py`, the original
strict reports, and `release/evidence/cohere-full-pass-2026-10-25.json`.
