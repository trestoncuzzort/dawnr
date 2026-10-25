# Measure the checked JSON teacher on the original 50 training problems

Registered before pilot dispatch. The full-schema provider check passed as run `40159613022`; it established
transport compatibility, not real-problem yield. This pilot uses the same original 50 training IDs as the
earlier Cohere comparisons, SHA-256 `446fbee835307badfa317826dceee48c9f5f6b7c26921d051503b86ed02351d4`.
No easier panel is selected. The original Command A pilot retains all four problems and nine specifications
under the new static check; the old result and its costs remain historical measurements.

## Recipe and budget

Use `teacher.yml`, one job, `representation=json`, `command-a-03-2025`, no explicit thinking budget,
8,000 output tokens, ten candidates per problem (`spec_samples=9`), seed offset 30000, and the same original
six-example primer. The first candidate is greedy; the other nine use the existing temperature 0.7 and
top-p 0.95. Concurrency remains eight. Model/schema/converter identities bind the private caches.

This changes the representation, reply allowance and placement of the static check before the existing
candidate cap. It tests the complete recipe, not the isolated causal contribution of JSON. No model writes
Python solutions: the existing `--reference-python --specs-only` route supplies the same problem references.
Keep at most three candidates per problem through the existing SAFE and reference checks, then the strict
1,000-draw request budget, minimum ten valid draws and 0.9 rejection floor on both mutant families.

The proxy's spending ceiling is $25. Reserve $32 to include requests already in flight when a ceiling is
reached; the ceiling is not a hard billing cap. The reconciled conservative prior is $310.666400, so planning
with this reservation totals $342.666400 against the $950 stop. Record actual charges once and release unused
allocation after collection. Provider retries retain the existing proxy policy; distinguish successful calls,
logical candidate requests and provider errors. Missing billing evidence is not zero cost.

Outputs, actual wire requests, provider replies, conversion refusals and ledgers remain encrypted. The current
curated archive is 7,123 rows, SHA-256
`eb139437b33b4797023e1f6ef121628588d5397f9f57241695d654071c4457b5`; it already has specifications on 12 of these
50 IDs. New coverage is measured against that archive, with row construction and the whole panel/GPL audit
on GitHub before any addition is accepted. The unchanged tokenizer/window must account for skipped rows.

## Predictions and expansion decision

The yield and efficiency predictions that govern expansion are:

1. At least eight problems have a statically valid, strictly reference-kept specification.
2. At least four problems outside the current archive's covered IDs produce a specification row that fits
   the unchanged 2,845-token window. Count usable new problems, not only raw candidates.
3. The strict-kept problem count per $100 is at least 62, the same Command A efficiency bar used in the wider
   pilot. Use the reconciled actual recorded cost, with complete billing evidence.

Expansion also requires all 50 IDs accounted for, all 500 logical candidate requests accounted for, no budget
ceiling truncation, at most 5% provider-error replies, and at most 5% token-limit finishes. Every successful
provider response must match its preserved billed-unit evidence and ledger entry. Missing evidence or a
failed final data audit prevents expansion. No repeat is selected to replace an unfavorable result.

As a separate diagnostic prediction, expect at least 80% of the 500 candidates to finish complete and pass
schema, static and exact round-trip conversion. Report its success or failure and the refusal categories.
This diagnostic does not by itself override the yield/efficiency decision above: the final accepted coverage
and cost are the expansion criteria, and semantic refusals remain excluded from training.

Useful accepted rows may be integrated even if expansion fails, as with earlier pilots. No training job,
weight change, model-quality claim or held-out-182 reading follows from this teacher run.

Sources: `t/PREDICT-2026-10-25-cohere-json-transport.md`, `t/recipes/teacher_cohere_specs.sh`,
`t/recipes/cohere_proxy.py`, `t/recipes/v9_strict_specs.py`, and the original pilot/source receipts.

## Accounting instrument prepared while the pilot runs

The pilot was already live when `cohere_json_audit.py` was added. This changes no recipe, prediction or
expansion condition. Before reading any pilot output, the expected 500 requests were reconstructed from
the earlier wider pilot's same 50 original prompt groups, checking all 1,000 historical requests against
their original stage/seed rule. Only the registered reply allowance, sample count and seed offset change.
The expected request manifest stays private; its SHA-256 is
`7fbc287d5f2966ef028badeb1d92cac89c531f20e452fcec23d6b9355bb57ac7`.

After artifact verification, the audit requires that complete request set and the 569 registered source/data
hashes, then replays the JSON wire mapping and conversion without model calls or reference/proof grading.
Successful responses, including
paid conversion refusals, must match billed input/output units, per-call rounded charges and proxy logs.
Concurrent charges lack request IDs, so the check matches their full billing signatures and multiplicities.
It reports recorded charges rather than an invoice, and does not infer the number of physical API retries.
Missing billing remains unresolved. Counts, novelty, token fit and the final data audit remain separate
requirements. Aggregate input evidence is in
`release/evidence/cohere-json-pilot-accounting-inputs-2026-10-25.json`.
