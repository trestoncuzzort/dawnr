# Named-operand Cohere teacher on the original 50 training problems

Registered before dispatch. The single full-schema capability request passed as `40809918934`; it established
transport compatibility, not useful training yield. This pilot repeats the original 50 training problems with
the new `json-v2` representation. It does not select an easier panel or change an acceptance check.

## Recipe and evidence

Use `teacher.yml`, one job, list `cohere-pilot-ids.txt`, Command A (`command-a-03-2025`), representation `json-v2`,
no explicit thinking budget, 8,000 reply tokens, ten candidates per problem (`spec_samples=9`), seed offset 30000,
the original six-example primer, concurrency eight, and series `cohere-json-v2-pilot-20261029`.
The original 500 decoder request bodies, temperatures and seed rule are unchanged; the wire representation and
its code identity differ. The historical API result is retained, not replaced by this later measurement.

The fixed panel SHA-256 is `446fbee835307badfa317826dceee48c9f5f6b7c26921d051503b86ed02351d4`.
All expected requests, source/data hashes and the original prompt groups were prepared independently before
dispatch. Their identities are in [the input receipt](../release/evidence/cohere-json-v2-pilot-inputs-2026-10-29.json).
The run must reconcile through `cohere_json_audit.py` with `representation=json-v2`, then the normal row builder
and whole panel/GPL audit. Raw prompts, responses, training rows and detailed diagnostics remain encrypted/private.

The current novelty baseline is the verified 6,954-row archive, SHA-256
`18f3b204abd15c8e497c83840f909877ce5d131a8c23ce6c8633a117e5dbb4f9`. It has specification rows on 12 of the 50
problems, and 916 problems overall. This baseline is frozen before the run. The 2,845-token training window,
static checks, minimum ten valid reference draws, 1,000-draw request budget and both 0.9 mutant rejection floors
remain unchanged. No executable task body is requested from this teacher.

## Budget and decisions

Reserve $32 from the privately reconciled current grant balance. The proxy ceiling is $25; it is a soft ceiling
with up to eight calls in flight, not a provider-enforced hard cap. Record actual billed-unit charges once and
release unused allocation after collection. Missing billing is unresolved, never zero. No concurrent teacher
allocation exists at registration.

Keep the earlier expansion targets: at least eight strictly kept problems, at least four previously uncovered
problems with rows that fit the unchanged training window, and at least 62 strictly kept problems per $100 of
reconciled recorded cost. Require all 50 IDs and all 500 logical requests accounted for, no ceiling truncation,
at most 5% provider-error replies and at most 5% token-limit finishes, complete billing evidence, and a clean final
dataset audit. The conversion diagnostic retains its earlier 80% threshold; report it separately.

Expansion requires the coverage, efficiency and accounting conditions. A failure remains a failure. Useful
accepted rows can still enter the dataset after the full audit even if expansion is refused. Model improvement
requires training and the existing release qualification protocol; this teacher run alone cannot establish it.

Sources: `t/PREDICT-2026-10-25-cohere-json-pilot.md`, `t/PREDICT-2026-10-29-cohere-json-v2.md`,
`t/recipes/cohere_json_audit.py`, `t/recipes/prepare_release_rows.py`, and
[Command A API pricing](https://docs.cohere.com/docs/command-a).

## Result: expansion refused

Run `40897787213` completed successfully as a workflow, but failed the experiment's
coverage, novelty, efficiency and conversion predictions. It accounted for all 50
problems and 500 logical requests: 498 charged responses and two HTTP 422 replies,
with $11.410546 recorded. Five responses reached the token limit; none hit the
spending ceiling. All 571 source/data hashes, expected requests, wire requests,
saved conversions and recorded billed units reconcile.

Only two problems and three specifications passed the strict check. Both problems
already have fitting specification rows in the frozen 6,954-row baseline and the
current 6,956-row archive. Novel fitting coverage and added rows are therefore zero.
The yield is 17.53 strict problems per $100, below 62; conversion acceptance is
142/500 (28.4%), below 80%. The accounting/error-rate conditions pass. No changed
dataset exists to audit, and no additional rows are admitted.

Of 356 refused conversions, 347 failed the unchanged static contract checks.
The recurring failures concern library argument types, name scope and missing
termination measures in recursive specification helpers. Named operands alone did
not produce useful new coverage. Keep this failed measurement, do not expand the
same recipe, and register any feedback-based repair experiment separately.

The independent two-seed model run continues on its frozen data. This result says
nothing about that model's quality. Billing refers to preserved recorded charges;
physical API retry attempts are not observable from final replies.

[Aggregate result and verification](../release/evidence/cohere-json-v2-pilot-result-2026-10-29.json).
