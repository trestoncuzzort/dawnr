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

## Result

Build `40155901277` passed its full audit. Predictions 1 and 2 held: 110 rows were added
on 39 new problems, giving 7,176 rows with SHA-256
`52404c473208d01cb8f074a540c3cbe988f301c063d976a44fa25c40e76e3c03`.
The 7,066 parent rows remain unchanged and in order. There are zero current-panel or
GPL-lineage findings, with the same 339 inherited unparsed blocks.

**Prediction 3 failed.** Three specifications for one problem require 2,896, 2,982 and
3,778 tokens, exceeding the registered 2,845-token window. The other 107 new rows fit.
The existing `student_sft.encode_row` skips overlong rows and counts them; it never
truncates them. At this window, the additions supply 39 reference-Python rows and 68
specification rows covering 38 new specification problems, plus one reference-only
problem. The three longer specifications stay in the private audited archive, with
their exclusions explicitly recorded. The training window is unchanged. A future
training manifest must account for all parent and new exclusions before any run.

All artifact, input, builder and output digests were verified. The length reading used
the pinned tokenizer and unchanged trainer encoder offline, without loading a model.
Aggregate receipt: `release/evidence/cohere-data-2026-10-25b.json`.

The subsequent whole-archive encoding check accounts for the parent too: 7,124 of 7,176 rows fit, with
52 skipped at the unchanged window. Forty-nine are inherited from candidate A, whose existing training
log independently reports 6,678 used and 49 skipped; the other three are the failed prediction above.
All 449 additions since candidate A contribute 446 fitting rows. Receipt:
`release/evidence/cohere-data-window-2026-10-25.json`. The archive stays intact and no new training starts.
