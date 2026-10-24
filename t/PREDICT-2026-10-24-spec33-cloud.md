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
