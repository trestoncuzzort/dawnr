# Can Command A generate the expression structure the teacher needs?

Registered before any capability call. The completed wider pilot lost 639 of 1,000 replies at the parser.
The earlier uDebug teacher trials also failed their prose-instruction and parser-feedback targets
(`PREDICT-2026-10-12-udebug-teacher.md`). The October 22 repository survey catalogued constrained generation
in `internal/research-2026-10-22/plateau-repos-B.md`; no earlier Cohere JSON-expression adapter was found.
The existing handoff and research records were checked before choosing this experiment.

Command A supports schema output, references and `anyOf`. Its documentation does not explicitly establish
recursive-reference support. This is a capability question before a new teacher recipe, not a quality claim.
The engine already uses JSON task trees (`t/SPEC.md`) and has a parser, printer and well-formedness checker.

## Procedure and budget

Run `cohere-schema-smoke.yml` on GitHub. Make at most three requests to `command-a-03-2025`, temperature zero,
seeds 31000, 31001 and 31002, with 2,048 output tokens each and no automatic retries. Reserve $1 from the
grant: the prior conservative total is $310.646105, no other teacher calls are live, and the combined
planning amount is $311.646105 against the $950 stop. Billed input/output units use the documented
$2.50/$10 per million. Missing billing or uncertain transport retains the reservation for reconciliation.
Quota or transport failures stop subsequent calls. HTTP 400 schema refusals are recorded and the other
independent capability cases may still run. Workflow reruns are refused; preserve the original outcome.

Three synthetic contracts, in order:

1. An inline schema for `r == 7`, using integer/variable alternatives and an array of arguments.
2. The same contract with the atom alternatives moved into `$defs` and reached through `$ref`.
3. A recursive expression definition for `r == ((((((x + 1) + 1) + 1) + 1) + 1) + 1)`, preserving all six
   additions. Its expected expression depth is eight, exceeding plain JSON mode's five-level limit.

Each returned expression is checked for exact fields, operator arity and permitted variables; placed into
a fixed synthetic task; checked by `check_wf`; printed and parsed back without change; and compared with
the requested expression tree. Duplicate JSON fields, non-finite numbers and truncated replies are refused.
No kernel, reference solution, training panel or held-out problem is used. All request/response text and
diagnostics are sealed with the existing output public key. Public logs contain only aggregate metrics.

## Predictions and next decision

1. All three schemas are accepted and return complete, nonempty JSON. Any API refusal, empty reply or token
   limit falsifies this prediction; keep the per-case distinction between inline, referenced and recursive.
2. All three expressions pass the structural/type checks and exact printer/parser round trip, and match the
   requested trees. A wrong tree, ill-typed expression or changed round trip falsifies this prediction.
3. All calls have billed-unit evidence and the recorded total stays at or below $1. Missing accounting or a
   higher cost falsifies this prediction; do not treat missing evidence as free usage.

Only if all three predictions hold may a training-only teacher pilot using this representation be prepared.
That pilot still needs its own registration, full grammar support, unchanged strict reference/mutant checks,
coverage comparison and budget. A valid synthetic JSON expression establishes none of those quality results.

Sources: [structured outputs](https://docs.cohere.com/docs/structured-outputs),
[Chat API](https://docs.cohere.com/reference/chat), [Command A pricing](https://docs.cohere.com/docs/command-a),
`t/recipes/cohere_proxy.py`, `t/SPEC.md`, `t/surface.py`, and `t/check_wf.py`.

## Result

Run `40156495978` passed all three predictions at revision `2fbc4de2`. Each case returned complete,
nonempty JSON, matched its requested expression, passed well-formedness, and survived an exact printer/parser
round trip. The recursive case had expression depth eight. Exactly three calls were made, with no retries.
Their billed-unit total was $0.002285. The $1 reservation is released; the conservative consolidated grant
estimate is now $310.648390, with $639.351610 below the $950 stop and no live reservation.

All source hashes, original input bytes, the encrypted artifact digest and the three response/ledger records
were checked. Receipt: `release/evidence/cohere-schema-smoke-2026-10-25.json`. A teacher pilot may now be
prepared under the conditions above. The smoke does not establish that real specifications become more
correct, that the full expression language is covered, or that any training problem is newly solved.
