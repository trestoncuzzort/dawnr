# A bounded follow-up to North Mini Code's truncated pilot

The original 50-problem pilot kept four problems and added no coverage beyond the earlier teachers.
Its expansion predictions failed. Of 500 calls, 481 ended at the 4096-token limit and 480 returned no final
text. Cohere's [reasoning guide](https://docs.cohere.com/docs/reasoning) explains that thinking is enabled by
default and shares the output limit; an explicit thinking budget leaves room for the answer. The existing
proxy already supports a separate thinking budget and final-answer allowance.

## Configuration smoke, registered before dispatch

Use only the first entry of the original registered 50-problem list, chosen by list order rather than its
previous result. The one-ID file has SHA-256 `01bc84aaf8874df6fbeff3a7d1ce7f770c070816d2af0bcc65ec663275c6124f`.
One greedy specification request, `north-mini-code-1-0`, thinking budget 2048, final-answer allowance 4096
(6144 total API output tokens), seed offset 20000. Reserve $1 despite the documented zero API evaluation rate.

Predict one successful API response with nonempty final text and a complete finish reason. An API error,
empty final text or token-limit finish falsifies this configuration check and prevents the larger follow-up.
The usual strict check still runs, but acceptance of this one problem is not the configuration criterion or
evidence of general teacher quality. Outputs stay encrypted. No Model Vault is provisioned.

## Conditional 50-problem follow-up

Only if the configuration smoke passes, run the same original 50 problems, ten candidates each, with that
explicit 2048 thinking budget and 4096 answer allowance, seed offset 20000, and a $25 reservation. Require
all 50 problems accounted for, at most 5% token-limit finishes, at most 5% empty final replies, no budget
ceiling, and at most 5% transport/quota/access errors. Predict at least eight strictly kept problems and
at least four outside the original pilots' union of 12. Every condition must hold before expansion.
Report overlap with the wider Command A pilot separately. A failure remains recorded; accepted data remains
subject to the usual coverage and training-row audit rules.

The completed original North pilot cost zero under the documented API rate, releasing its $25 reservation.
The conservative prior ledger total remains $83.082037; the two active Command A allocations total $625.
With this $1 smoke reservation, the planning total is $709.082037, below the $950 stop. Reconcile the smoke
before replacing its reservation with the conditional $25 pilot reservation. These are allocations and
conservative estimates, not a claim about the dashboard balance.

## Configuration result and conditional dispatch, 2026-10-25

Smoke `40149271462` passed its registered configuration check: one successful response, `COMPLETE`, nonempty
final text, no proxy error and zero recorded API cost. The strict check kept zero problems; it was explicitly
not the configuration gate. The encrypted artifact's digest and aggregate result are in
`release/evidence/cohere-thinking-smoke-2026-10-25.json`.

The conditional follow-up started at 01:10:23Z, run `40149580546`, revision `7161f773`, with the original 50 IDs
and the registered settings above. The wider Command A pilot also completed, costing $13.064852 and releasing
the rest of its $25 reservation. The conservative prior estimate is now $96.146889; the full Command A pass
reserves $600 and this follow-up reserves $25. Their combined planning total is $721.146889, leaving $228.853111
unreserved below the $950 stop. The smoke and original North pilot each cost zero under the documented API rate.
This supersedes the pre-smoke allocation snapshot above, without treating estimated spend as a verified bill.

## Follow-up result

Run `40149580546` completed all 50 problems: 485 successful calls and 15 monthly-quota errors across 500 logical
requests, zero recorded API cost, 10 strictly kept problems and 16 candidates. Nine kept problems were already
in the original pilots' union of 12. Only one problem and one specification are new to the 7,066-row draft; four
kept problems overlap the wider Command A pilot.

The two expansion conditions failed: novelty is 1 against the required 4, and 30 of 500 replies (6%) hit the token
limit against the 5% ceiling. The other conditions held: all 50 were accounted for, 10 exceeds the 8-problem bar,
there was no budget stop, and empty replies and request errors are each 15/500 (3%). All successful calls returned
nonempty final text; 455 finished complete. These results do not isolate thinking budget from total output budget
or sampling-seed effects.

Every HTTP 429 message reports the model's monthly request limit, so further calls wait for that quota to change.
The recipe does not qualify for expansion even independently of the quota. Retain the one new accepted example
for an audited data update. The encrypted ZIP digest and all 516 archived files matched the private collection;
aggregate receipt `release/evidence/cohere-thinking-pilot-2026-10-25.json`.

The $25 reservation is released and replaced by the recorded zero cost. The common conservative prior remains
$96.146889, with the full Command A pass's $600 allocation still reserved, including its completed shards.
That planning total is $696.146889, leaving $253.853111 below the $950 stop. Reconcile the full pass once before
allocating against its final cost; its partial ledger figures are already inside the $600 allocation.
