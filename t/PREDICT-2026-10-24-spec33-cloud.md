# The 33-specification release condition on GitHub

Registered before dispatch. The release requires at least 27 of the 33 given specifications proved by all seven
kernels. The old `spec33.sh` recipe runs those provers locally, contrary to the current execution rule. The new
`spec33.yml` workflow reads private, encrypted answer files and grades them in the same pinned engine image as
the development arms. It uses the existing strict contract-preservation gate and scorer without changes.

## Control and prediction

- The saved October 11 matched v5 answers, not a new model decode: 33 answers, SHA-256
  `0ad976413b61e2936bef64752ee7b584bb15c9b3b3e592e5556aef40c5e9149f`.
- The registered 33 questions, SHA-256 `effc2f4e586e0c4f7638a5a9a2b75515aaf7019de03ca819d46e5aa3d593ab24`.
- This fixed answer set previously read 28 proved by all seven and 29 by at least one. The prediction is that
  both counts reproduce. Any difference falsifies that prediction and requires examining the differing cells;
  it is not a model gain or regression, since no answer changed.
- All 33 answers must be present exactly once, the panel must match its digest, and every ready answer must have
  all seven columns in the resulting table. Missing matrix rows or kernel columns fail the workflow. A task
  for which no twin can be constructed remains named and counted apart, as in the existing scorer, and cannot
  count as proved.
- The engine image is the existing `evaluate.yml` cache at engine commit `d13d11d0`; one kernel task at a time,
  with the existing lowering memory bound. No kernel source or acceptance rule changes.

The release bar remains 27, the original published reading. The saved October 11 answer set is a separate
control for this execution change. Generated answers, tasks and prover evidence remain encrypted on GitHub;
public results contain only counts and hashes. No held-out-182 evaluation is started by this workflow.

Sources: `t/recipes/v5-matched-2026-10-11-grade.sh`; `t/score_spec_given.py`; `t/recipes/v6-grade.sh`;
`internal/RELEASE-6.0-PLAN.md`, condition 3.

## Result, 2026-10-25: the all-seven prediction failed

Run `40141581001` completed the full matrix but read 26 all-seven, not the predicted 28. The at-least-one count
reproduced at 29. All 33 prepared tasks match the saved October 11 tasks. Of 231 cells, 229 agree; two Frama-C
cells changed: one real-program timeout and one twin changed from refuted to unproved. Their generated C files
are byte-identical to the rescued originals. The scorer is unchanged, but the adapter changed since October 11,
so this is not an isolated measurement of the execution environment. No model answer changed.

A printer-only diagnostic found why the newer adapter can reject the twin: Frama-C normalizes a negated
inequality into equality, while the adapter's new negation guard requires a leading negation. The original
source passes that guard and the printed form fails it. No prover was run locally for this check. The timeout's
cause remains unestablished. Aggregate evidence: `release/evidence/spec33-cloud-control-2026-10-25.json`.
The release threshold stays 27; this control does not qualify a new model.

### Registered follow-up: bounded Frama-C diagnostics

Replay only these two saved real/twin pairs in the same pinned image, using the unchanged adapter and budgets.
Use `verifiers.cell_pair` with its normal three repetitions per side, preserving all 12 detailed results and
both agreement flags. Predict that all three affected twin results are unproved with the negation-guard reason,
and that at least one of the three affected real results times out. A different twin reason/outcome or no real
timeout falsifies the corresponding prediction. This probe investigates causes; its results cannot replace the
original 26 or produce a release score. Inputs and detailed outputs remain encrypted. No engine rule changes.
