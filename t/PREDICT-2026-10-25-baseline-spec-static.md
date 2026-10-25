# Check the inherited specification rows with the current static gate

Written before this diagnostic audit. The prior curation deliberately preserved the original 6,727-row
training prefix and checked only its additions. Its 1,601 rows labelled `source=spec` therefore still need
this check. The current archive has 7,123 rows, SHA-256
`eb139437b33b4797023e1f6ef121628588d5397f9f57241695d654071c4457b5`.
The already-checked 230 specification additions serve as a control.

## Fixed scope and predictions

Parse each of the 1,601 inherited specification answers and apply `spec_contract.checked_contract`.
Count valid unchanged contracts, valid contracts requiring the existing checked header promotion,
missing/unparseable blocks and static refusals separately. Keep row hashes and detailed refusals private.
Use the same procedure on all 230 added specifications. This is a parser/static diagnostic: it performs
no model call, reference execution or proof grading and writes no training rows.

1. Predict at least one inherited specification is refused. The earlier reference-only teacher path
   admitted 50 invalid contracts among 250 full-pass outputs, and 763 inherited specifications carry
   the earlier builder's `self-distilled-specs` tag. Zero refusals falsifies this prediction.
2. Predict all 230 control additions remain valid without a header promotion. Any refusal or remaining
   promotion falsifies this prediction and requires investigating the instrument before curation.

Report every category and keep header promotion separate from rejection. A static refusal does not
establish that a reference-behaviour check failed, and a pass is not a proof of specification quality.
This audit does not establish the status of Python, proof, repair, corpus or other differently labelled
rows. The original prefix, active training inputs and prior measurements remain fixed. Any subsequent
data curation needs its own declared rule, complete row accounting and whole-data audit on GitHub.

Sources: `t/PREDICT-2026-10-21-v8-spec-rows.md`, `t/PREDICT-2026-10-25-static-contract-data.md`,
`t/recipes/spec_contract.py`, `t/recipes/curate_spec_rows.py` and
`release/evidence/cohere-static-contract-census-2026-10-25.json`.

## Result and the contract-context correction

Both original diagnostic predictions held. Under the initial pipeline gate, the 1,601 inherited rows
split into 1,362 valid unchanged, 68 valid after the existing header promotion, and 171 refusals. All
230 added control rows remained valid without promotion. Every selected row parsed and had an empty
body; this is separate from the archive's 339 inherited unparsed blocks in other row kinds.

The refusals exposed a bug in the new pipeline gate. The row builders deliberately retain a task's
termination measure when removing its body. The complete-program checker then reports that the task
has a measure without a self-call. The committed `t/tasks/factorial.t` reproduces this: its complete
task passes static checking, and removing only its body triggers that diagnostic. The original pipeline
gate rejects it. This is not evidence that its contract is invalid.

`spec_contract.py` now uses the checker's structured diagnostics and defers only that exact task-body
relationship when the body is empty. It preserves the measure and still checks its type, parameter scope
and calls. Specification-function bodies are present, so their termination rules still apply. The full
program checker, proof gates and specification-preservation rules are unchanged. This follows the existing
pipeline's declaration/proof distinction in `spec_given.py`; [Dafny's reference manual](https://dafny.org/dafny/DafnyRef/DafnyRef)
also distinguishes a body-free declaration from checking its implementation. A contract pass is never
reported as a completed-program proof.

The corrected contract check recovers **47 inherited rows**, preserving every task measure: 45 unchanged
headers and two checked promotions. The revised inherited census is **1,407 valid unchanged, 70 requiring
promotion, and 124 refusals**. All previously valid normalized tasks remain identical. All 230 added controls
still pass unchanged. The full Command A census remains 200 valid contracts over 125 problems and 50
refusals; its prior result does not change.

No training rows were modified by either census. The current archive remains 7,123 rows, and the active
training keeps its original inputs. Curation of the remaining inherited refusals is a separate next step.
Aggregate evidence: `release/evidence/baseline-spec-static-2026-10-25.json`. The initial registration,
row-level diagnostics and subsequent context comparison are preserved privately. The running JSON teacher
and its accounting audit remain pinned to their original code, including the original stricter gate.
