# Bedrock request accounting before paid verification work

Registered before the regression run. Prior code and records read:
`bedrock_proxy.py`, `t/PREDICT-2026-10-03-teacher-round-bedrock.md`, and the
existing offline retrieval journal recovery tests.

The proxy currently holds reservations only in memory, skips malformed ledger
rows, prices missing usage as zero, reserves at the requested rather than the
maximum registered rate, and retries ambiguous transport failures. Its default
output limit is used in the estimate without necessarily being sent upstream.
Those behaviors cannot support the advertised hard spending cap.

Sources: [AWS token counting](https://docs.aws.amazon.com/bedrock/latest/userguide/count-tokens.html),
[AWS cost and usage dimensions](https://docs.aws.amazon.com/bedrock/latest/userguide/cost-mgmt-understanding-cur-data.html),
and [Python fsync](https://docs.python.org/3/library/os.html#os.fsync).
Token counting is model/API-specific; a byte-based estimate is not a provider
token count. Document the limit as a local estimated request budget, not an
account-wide billing ceiling.

Bars:

1. A reservation survives process restart before an outcome is known. A corrupt,
   negative or non-finite ledger entry prevents further spending.
2. Missing/invalid usage and uncertain transport outcomes retain the full
   reservation. No automatic retry can hide a second billable attempt.
3. Requests have a positive output limit actually forwarded upstream, one
   completion, no streaming or non-text inputs, and a registered price tier.
   Reservations use the highest registered rate and a conservative text-size
   estimate. An observed charge above its reservation stops further admission.
4. Concurrent reservations cannot exceed the local budget; one writer owns a
   ledger. Ledger write failure prevents dispatch. No request data or credentials
   is written into the accounting ledger.

Regressions use injected transports and temporary ledgers; no paid call is
needed to falsify these bars. Live inference awaits an explicit spending cap
and current price verification. An AWS bill remains the authority for charges.

## HTTP and transport extension, registered before its tests

The durable ledger has ten passing offline tests, but the HTTP handler still calls the old amount-based
settlement API. Before dispatch, require a JSON object with bounded content length, plain text messages,
one completion, no streaming, a registered model/tier and a positive integer output cap. Forward the default
4096 cap rather than merely estimating it. Reject unsupported charge-changing fields instead of forwarding
them unaccounted. UTF-8 request bytes plus explicit framing headroom are a conservative admission estimate,
not a measured token count; reserve at the highest registered input and output prices independently.

Predictions: loopback HTTP requests with a fake provider demonstrate that refused or journal-write-failed
requests never dispatch; overlapping reservations cannot exceed the estimate budget; malformed or missing
usage, unknown returned tiers and transport exceptions consume the full reservation. A transport attempt
returning 429/500 or losing its response is never automatically retried. Invalid framing, request fields,
nonfinite settings and corrupt journal records fail closed. Restart preserves unresolved reservations and
an overrun blocks future admission. The ledger records accounting metadata only, never prompt text, provider
response text, credentials or raw exception messages.

These additions are grounded in the existing request shape in `t/spec_experiment.py` and
[AWS's token-counting documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/count-tokens.html).
All HTTP and transport tests run against fake responses or loopback servers without an AWS call.

## Results

`python3 locallm/test_bedrock_accounting.py -v`: **32 tests pass**, with fake HTTP responses or loopback servers.
The suite covers the original ten journal cases, overlapping ledger and HTTP reservations, restart after an
overrun, symlink aliases of the journal lock, failed fsync, malformed requests/framing, invalid rates and regions,
both output-limit spellings, missing or invalid provider usage, malformed provider JSON, private diagnostic text,
settlement write failure and one-attempt transport behavior for 429/500/503/timeouts.

The HTTP handler now forwards the 4096 default, settles using the durable reservation identity, and refuses
unsupported fields. In particular, `structured_outputs` is rejected rather than silently discarding a requested
grammar. Prices remain the registered values in the source; this offline run does not verify current AWS prices.

The journal also rejects zero and reused reservation identities. Canonicalizing its path makes symlink aliases
share a lock. The first journal creation fsyncs its parent directory as well as its data. Uncertain outcomes are
retained as `uncertain_reserved_cost`; requests that exceed a reservation block later admission, including after
restart. No paid call was made, and no account-wide billing ceiling is claimed.

An initial `unittest discover -s locallm` invocation imported the unrelated `dawnr_interp` package and failed
because the system Python lacks Torch; the accounting tests themselves passed. Directly running the named test
file above avoids that unrelated discovery import. The CLI help and Python compilation checks pass without AWS
libraries. The live pilot still requires current price verification and the approved run budget.
