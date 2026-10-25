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
