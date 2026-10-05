# A tool call released only when its values were said: registered before any test item's reply is read

Registered 2026-10-05 11:33Z. `locallm/tool_check.py` is written and unit-tested. It has been looked at on the dev
part described below and on nothing else. Plan row 6 of `internal/PLAN-2026-10-05-usable-for-everyone.md`;
research receipt 0a4596ca86e5.

## What it is for

A model that is offered tools fills every required parameter of the call it writes, whether or not the person
gave a value. When2Call (Ross, Mahabaleshwarkar and Suhara, arXiv:2504.18851) builds 1,062 requests with one
required value removed, where the right reply is a question, and "Calibration is the Bottleneck"
(arXiv:2609.00949) reports tool-trained models calling anyway with placeholders that the benchmark's own grader
then passes. The remedies in those papers are training and prompting. The runtimes that serve small models hold
a call to its schema, which says nothing about where a value came from; enterprise stacks add a second model to
judge the call. `tool_check` is neither: each value of a call must be accounted for by the conversation (its
words or its number were said), by the schema's default, or by a choice among the schema's `enum` that the
conversation makes; a required parameter that is not accounted for becomes a question that names it, and an
optional one is left out and said. The rule is the one schema-guided dialogue used for slots (arXiv:1909.05855).

## What is measured

When2Call's test set (3,652 items from BFCL v2 Live; CC BY 4.0; kept out of this repository), three kinds:
`tool_call` (a tool fits and every required value is given), `request_for_info` (one required value removed),
`cannot_answer` (the tool that fits was taken away). One fixed shuffle a kind (seed 2026) splits it: **dev** is
the first 100 of each kind, **test** is the next 300 of each kind.

The base Qwen3.5-4B at 4 bits under llama-server, the tools offered natively, temperature 0, one request an item.
Two readings of the same replies (`locallm/tool_check_eval.py`): `native`, a call is released whenever the model
wrote one; `checked`, `tool_check.check_all` decides. Scoring uses no judge: calls released are counted; for
`tool_call` items a released call is compared with the benchmark's reference call (`agrees`); for
`request_for_info` items the question the check asks is compared with the removed parameter's name. What the model
says when it writes no call is not classified.

## What was looked at before this registration, all of it on dev or without a model

- Before any model was asked, the benchmark's own reference calls for all 1,295 `tool_call` items were pushed
  through an early form of the rule: 160 would have become questions. That count includes test items; it used the
  references, not model replies, and nothing about the rule was chosen from it.
- The dev part (300 items) was asked once and read closely. Four things were changed from what it showed: a
  word is compared as written (`card123` is not `card`); a value that only repeats the parameter's own name
  (`Project Name`) and an empty list are not values; a choice among an `enum` must be one the conversation makes,
  with stems allowed (`Music` in "a musical performance"), where at first any member was released; afternoon hours
  and initials are read (`23:00` in "11PM", `San Francisco` in "SF").
- Dev under the rule as frozen (not a result; the rule was fitted to these items):

| kind (100 each) | native: a call released | checked: a call released | checked: asked |
|---|---|---|---|
| tool_call | 97, of which 83 agree with the reference | 86, of which 80 agree | 11 |
| request_for_info | 71 | 18 | 53, of which 51 name the removed parameter |
| cannot_answer | 22 | 14 | 8 |

  Of calls released over the 300, the share that agree with a reference call: 43.7% native, 67.8% checked.

## Predictions, on the test part (300 of each kind, no reply read)

- **T1, the failure is this model's too.** On the 300 `request_for_info` items the model alone releases a call on
  at least 55%.
- **T2, the check turns most of them into the right question.** With the check a call is released on at most 30%
  of them, and of the items where the check asks, at least 85% name the removed parameter.
- **T3, what it costs.** On the 300 `tool_call` items, of the model's calls that agree with the reference call, at
  least 90% are still released by the check.
- **T4, what is released is more often right.** Over all 900 items, the share of released calls that agree with a
  reference call is at least 15 points higher checked than native.

## What each outcome changes

- T2 and T3 hold: the check goes between the model and the caller wherever dawnr hands back tool calls (the
  local API's chat endpoint for requests that carry `tools`, the harness's pre-call hook), documented with the
  test numbers.
- T3 fails: it ships off by default, and the README states the cost.
- T2 fails: no claim is made for it beyond the measured counts, and it is not wired in.
- T1 fails (the model alone asks more often than expected): the check matters less for this model than the papers
  suggest for others; said, with the numbers.

## Not measured here

Conversations of more than one turn (BFCL v3's `miss_param`), whether the question asked gets an answer that
completes the call, requests that need no tool at all, any model but this one, and the leaks the dev part showed
the rule cannot see: an identifier assembled from the request's own words, and a value the benchmark removed but
the request still implies.
