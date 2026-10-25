# Matched v5 controls after the certificate-normalization repair

Registered before these regrades. The upstream repair passed its native regression, negative controls, four-task
seven-kernel control and matched 114-task Frama-C columns. It is merged as `d1b57dc6` and imported into dawnr at
`66be29b4de81dbfe5a09e794274a58087867c42b` using only its certificate-related diff. The base engine and the earlier
adapter import retain their recorded versions. The old development baseline and the failed 26-all-seven private
control remain historical results; this run does not replace either with selected diagnostic cells.

## Fixed inputs and procedure

Regrade the same six v5 development parts at offsets 0, 1000 and 2000, covering the original development 95 and
wider 145. Every saved answer and route summary in the release archives was checked byte-for-byte against the
previously verified baseline reading. Archive digests and the unchanged panel digests bind the workflow inputs.
Validate each full-panel receipt before filtering and joining the clean 206.

Regrade the same saved v5 answers to the 33 given specifications. Questions and answers retain their exact
digests; only the input manifest's measurement label and purpose change. No model is called. The workflow first
runs the native certificate regression and negative controls against the imported dawnr code in the pinned image.
Private answers, native-control logs and grading evidence leave encrypted.

Both workflows check out grader `66be29b4de81dbfe5a09e794274a58087867c42b`. The image remains pinned to `d13d11d0`;
solver budgets, panels, grading rules and release thresholds are unchanged. The development grader is byte-identical
to the old development control, and the specification grader is byte-identical to the old specification control.
The changed lowering is the measured variable. Input identities are in
`release/evidence/v5-control-refresh-inputs-2026-10-25.json`.

## Predictions and interpretation

- The native certificate controls pass with no skipped tests.
- Development clean counts are at least 20, 19 and 19, respectively, and all-seven counts at least 9, 8 and 9.
  Any lower count falsifies that prediction; report every changed cell and investigate its cause.
- The private specification control reads 28 all-seven and 29 at one or more kernels. A different count falsifies
  the exact prediction. The previous 26 remains recorded. Do not select a favorable repeat if timing varies.

These are evaluator controls, not a new model result. Candidate comparisons must use the resulting matched
baseline and the same grader pin. A control failure must be understood before model promotion. Gate precision
continues to use its separately frozen `01c94ef5` instrument, which does not invoke Frama-C. The held-out 182 are
still unread and remain reserved for the candidate selected after release conditions 1 through 3.

Sources: `t/PREDICT-2026-10-25-framac-certificate-binding.md`, `release/evidence/v5-cloud-baseline-2026-10-25.json`,
`release/evidence/spec33-cloud-control-2026-10-25.json`, and `t/recipes/three_decode_report.py`.
