# North Mini Code as a teacher for dawnr

Registered before generation on 2026-10-24. The grant notes, release plan, proxy and previous session notes held
no earlier North Mini Code pilot. Cohere's current documentation lists `north-mini-code-1-0`, a coding model,
through Chat V2 with free API evaluation within rate limits. The authenticated model-list endpoint returned it
for this account. Those facts justify a bounded test, not a claim about dawnr's performance.

Sources: [model and API pricing](https://docs.cohere.com/docs/north-mini-code-1.0),
[per-model limits](https://docs.cohere.com/docs/rate-limits),
[model availability endpoint](https://docs.cohere.com/reference/list-models).

## Procedure

- The original 50 training problems, SHA-256
  `446fbee835307badfa317826dceee48c9f5f6b7c26921d051503b86ed02351d4`, with the same primer and reference Python.
- Ten candidates each, seed offset 0, 4096-token replies. Leave the model's thinking setting at its default
  (`THINK=0` omits the setting); no unverified model-specific reasoning parameters.
- One GitHub teacher job. Reserve $25 against the grant even though the documented API price is zero. Prior
  recorded spend plus outstanding allocations, including this one, is $733.082037, below the $950 stop.
  The finite 50-problem list bounds this to 500 logical generation requests; transient retries remain bounded
  by the existing proxy. No paid Model Vault or local model process is provisioned.
- The existing 1000-draw strict check at 0.9 on both mutant families; outputs remain encrypted. Accepted rows
  retain the teacher model and run tag when included in candidate B.

## Predictions and decision

Predict at least 8 strictly kept problems and at least 4 problems outside the union of 12 kept by the original
Command A, A Reasoning and A+ pilots. Below either threshold falsifies that prediction. Both must hold before a
larger pass uses this recipe. Also report overlap with the wider Command A pilot once that result arrives.

A run that fails to account for all 50 problems, hits its ceiling, or has more than 5% transport/quota/model-access
errors does not qualify the recipe for expansion. Service unavailability is reported separately from model
quality. A zero-dollar run has no finite per-dollar yield; compare strict-kept problems, novel problems, calls
and elapsed time, not an invented infinite score.

Model and reply budget change together relative to the original Command A pilot. This chooses a practical
teacher recipe on training problems; it isolates neither change and establishes no model-level gain. The five
release conditions remain unchanged.

## Result, 2026-10-25: neither expansion prediction held

Run `40142664557` completed all 500 requests over all 50 problems without proxy errors. The strict check kept
seven candidates on four problems; none are outside the original pilots' union of 12 or the current data draft.
Both predictions failed and this recipe is not eligible for expansion. Recorded API evaluation cost is zero.
Of 500 replies, 481 ended at the token limit and 480 contained no final text. This identifies a budgeting problem
with default thinking, not the model's quality under a different budget. Counts and hashes:
`release/evidence/cohere-north-pilot-2026-10-25.json`. No new training rows are added under the existing coverage rule.
