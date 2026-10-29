# Internal Cohere teacher: prevent malformed operand lists during generation

Cohere is an internal resource for improving Dawnr's local model. This change adds no hosted backend to
the product. It affects only the private teacher workflow and its synthetic capability probe.

The completed JSON pilot accepted only 115 of 500 conversions, and ultimately 3 strictly checked problems
for $10.180194 recorded. Its expansion criteria failed. Refusal inspection found missing/excess operands
and noncanonical `seq<int>` types among the avoidable structural errors. The unchanged recipe is not expanded.

Cohere's [supported schema subset](https://docs.cohere.com/docs/structured-outputs) does not implement
`minItems` or `maxItems`. The opt-in `json-v2` transport therefore gives fixed-arity operators required
`arg1`, `arg2`, `arg3` fields. Variadic operators, calls and constructors keep argument arrays. A recursive
type definition excludes the noncanonical object spelling of sequences/sets of integers. Nothing is silently
repaired: decoding restores the original AST, then the original schema, static checker and exact
printer/parser comparison run. Reference, mutant, dataset and held-out gates are unchanged.

The six primer examples and user problem evidence remain the same. Cache identities distinguish the transport.
All 200 historically statically valid full-pass contracts round-trip unchanged; the 50 original static refusals
remain excluded. These are compatibility checks, not new reference or proof results.

## Capability check registered before spending

Run `cohere-schema-smoke.yml`, scope `teacher`, representation `json-v2`, label `cohere-json-v2-20261029`.
Use the input digest in [the input receipt](../release/evidence/cohere-json-v2-inputs-2026-10-29.json).
The existing synthetic recursive specification, six-example primer, Command A, 8,000-token allowance and
single request with no retries remain. Reserve $1 from the privately reconciled current grant balance.
Inputs, replies and diagnostics are sealed by the existing workflow.

Predictions:

1. The provider accepts the complete recursive schema and finishes the one response.
2. The response restores exactly the expected contract, passing schema, static and round-trip checks.
3. The preserved billed units reconcile to exactly one recorded charge below the $1 reservation.

A failure remains in the record. A passing capability check establishes only that the teacher transport works.
Real training yield must be measured separately before expansion or promotion of rows. No new training run,
weight change, model-quality claim or held-out-182 evaluation follows from this capability probe.

Sources: `t/check_wf.py`, `t/recipes/cohere_task_json.py`, `t/recipes/cohere_json_smoke.py`,
[Cohere structured outputs](https://docs.cohere.com/docs/structured-outputs).
