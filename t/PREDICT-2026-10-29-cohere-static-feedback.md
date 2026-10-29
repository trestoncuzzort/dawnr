# Cohere static feedback versus a fresh specification sample

Registered before any new provider call. The JSON-v2 trial failed: only two strict
problems, both already covered, for $11.410546. Of 356 conversion refusals, 347
were static contract errors. This experiment tests whether the teacher can use
those errors to produce useful training material.

This is a training-side experiment. The earlier 4B specification-repair route
failed its paired release measurement; that result stands. No product command or
acceptance rule changes here. The running two-seed candidate keeps its frozen data.

## Frozen selection

Use the original 50-problem panel from run `40897787213`. Exclude the 13 problems
already covered in the current 6,956-row archive and the two remaining problems
without a complete response that failed static checking. Include all other 35.
For each, choose the first static refusal in the original candidate order, 0 to 9.
Neither reference scores nor new model outputs select a candidate.

The private selection SHA-256 is
`cb55bfc35e6d6cd16c292e236385b92cef7975ab9b746f62221d76728d667daa`.
It binds each original request, provider response, diagnostic and source cache hash.
Original artifact SHA-256:
`de5fe8b3bb281a0ee768eee4b9538a41fcd188d34706b73d62d00de08766d30f`.
Current dataset SHA-256:
`5b961478df43b2e206b64ed108692173bc3c5b1dd30a69aee88ba57b35dfe293`.

The exact 70 expected requests and 581 source/data hashes are frozen privately;
their manifest SHA-256 is
`a64e807eff46b84d3288a11b17a9d590c7f277d57c25a1a1149fd8a42026e2fc`.
The encrypted input asset is `cohere-static-feedback-20261029.tar.gz.enc`, SHA-256
`b8b8d8e5a6715fed1b4f86352528e965fc731fc1927d6cdfec4fcd348360c9a9`.
The workflow verifies those bytes and rebuilds the request manifest before reading
the provider key. Altered sources or selection abort the run.

## Matched calls and checks

Make exactly one new call per problem in each arm, 70 logical requests total.
Both use Command A (`command-a-03-2025`), JSON-v2, the same six examples, 8,000
reply tokens, temperature 0.7, top-p 0.95, no explicit thinking budget, concurrency
eight, and the existing per-prompt seed rule with stage salt 40100.

- **Fresh:** the original problem and reference-Python prompt.
- **Feedback:** that same prompt with the complete rejected JSON and its exact
  static diagnostic appended, asking for a correction that preserves the problem's
  meaning and the empty task body.

Do not give the teacher hidden reference-check witnesses or mutate a returned
contract to make it pass. Interleave the arms, alternating which goes first for
each problem. The source refusal must replay, the problem must remain on the
training side, and all expected requests and source hashes must match before calls.

Both arms retain the normal schema, static and exact round-trip checks, the visible
test/mutant specification gate, the 100-draw reference prefilter, then the 1,000-draw
strict check with at least ten valid draws and both mutant-family rejection rates
at least 0.9. Use the same per-problem reference seeds in both arms: `100000 + i`
for the prefilter and `1000 * i` for the strict check, with zero-based selected-case
index `i`. Preserve empty rows at the strict-check input so its original seed rule
uses that same index in each arm. Source verifier functions and thresholds are unchanged.

## Predictions and decision

1. Feedback conversions reach at least 80% and exceed the fresh arm's count.
2. Feedback keeps at least eight strict problems and at least four new problems
   with rows fitting the unchanged 2,845-token training window.
3. Feedback has more strict per-problem wins than losses against fresh sampling.
   Report the exact two-sided paired binomial test; require p at or below 0.05
   before claiming that feedback is better.
4. The cumulative useful-yield comparison meets the standing 62 strict problems
   per $100 floor: the original two strict problems plus feedback's kept problems,
   divided by the original $11.410546 and all new recorded cost in both arms.
   Also report each arm's marginal cost and yield, without presenting them as the
   full cost of generating the original attempts.

Expansion requires these predictions, complete accounting for all 70 requests,
no spending-ceiling cutoff, at most 5% provider errors and token-limit finishes,
and a clean final row audit. A failed experiment stays failed. Independently useful
strict outputs from either arm can enter a later dataset only after the normal
deduplication, token-window and whole panel/GPL audits. They do not enter the model
that is already training.

Reserve $12; set the proxy's soft ceiling to $8, allowing for calls already in flight.
The pilot is expected to cost roughly $2 to $4 from the preceding run's recorded
per-call costs, but actual charges decide. Missing billing stays unresolved. Inputs
and outputs remain encrypted/private, and no new model-quality claim follows from
a teacher-data result.

Sources: `t/spec_repair.py`, `t/spec_first.py`, `t/recipes/v9_strict_specs.py`,
`t/PREDICT-2026-10-21-repair-turn.md`,
[Cohere Chat API](https://docs.cohere.com/reference/chat), and
[SAFE](https://arxiv.org/abs/2410.15756).
