# Retain the useful new row from the failed first JSON teacher pilot

The first JSON pilot remains a failed expansion decision: three strict-kept problems, five specifications,
and $10.180194 recorded. Its raw request, conversion and billing audit passed. A fresh download of artifact
`12587911718` matches SHA-256 `60a4b6c5a73db2cfea2c9d2ad80905aa1b50f337b5ae83a78abc5affd1b197b5`;
all 516 extracted files match the previously audited collection.

Against the current 6,954-row archive, two of those three problems already have specification rows. The other
has one accepted specification and no existing training row. Use the existing `prepare-rows.yml` build mode
and `prepare_release_rows.py`, preserving the entire current archive and applying the normal coverage/deduplication
rule. The exact base and source hashes are in the encrypted input manifest;
[public input receipt](../release/evidence/cohere-json-salvage-inputs-2026-10-29.json).

Predictions before the cloud build:

1. Add two rows on one new problem: the checked specification and its reference-Python row, total 6,956.
2. Both additions fit the unchanged 2,845-token window; no row is truncated.
3. Post-render static contract checks and the full panel/GPL audit pass, preserving the existing 339 unparsed
   blocks in other row kinds without creating new ones.

Any failure is recorded and no failed row is promoted. This build makes no API calls and starts no model training.
The already registered 6,954-row model candidate and the concurrent JSON-v2 pilot each keep their frozen inputs.
This addition becomes available for a subsequent candidate only after independent artifact and audit verification.

Sources: `t/recipes/prepare_release_rows.py`, `t/recipes/v8_spec_rows.py`,
`t/PREDICT-2026-10-25-cohere-json-pilot.md`, and `t/PREDICT-2026-10-25-cohere-data-increment.md`.
