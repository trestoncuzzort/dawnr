# Move the saved v5 ceiling instrument to GitHub

Registered before the cloud measurement. Condition 2 of the release requires at least 0.70 specification-gate
precision. The original v5 reference is 73 correct among 93 kept candidates (0.7849462365591398), measured by
`t/recipes/spec_ceiling.py` on `v5-20261021-spec20`. This control reuses those saved answers. No model is asked
again, no training happens, and no held-out-182 reading is made.

## Inputs and procedure

The original three files were fetched from their existing source without modification:

| input | SHA-256 |
|---|---|
| spec_first.json | 5f8aef31132e4bdc07184e30b460646b6a2c563cbad94a79f8a04e38df485ef9 |
| python.jsonl | ab2703d5ef79648726995f3ecc3cb31cfa96096352e24a48d525fa94efa8cb0e |
| scored-specs.jsonl | de468d92c8a0e81567107e36489bedbb4e0e37ee22a46a2865be851c4fd18698 |
| development 95 | f807aec7e6b89e524ded720d9ccfb670c1d504a5a5717966a4b870516701daf7 |

`.github/workflows/ceiling.yml` validates all input digests and exact panel membership, then runs the unchanged
instrument at `01c94ef5509fc51ab6484c1350c1cb9f8504e459`, pool v5, 200 reference draws, three selected candidates
per problem and four CPU workers. It saves the result, source hashes, input manifest and completion receipt.
Inputs and detailed outputs are encrypted using the existing transport. Public logs contain aggregate counts.
The reference-check source files match the current tree. Python 3.12 and the cloud sandbox are recorded; a
disagreement with the old reading remains a disagreement to investigate, rather than a model-performance claim.

## Prediction

Predict 95 accounted problems, 63 with passing Python, 980 scored candidates, 93 kept by the three-test gate,
73 reference-correct among those kept, and precision exactly 73/93. Any count difference falsifies the control
prediction. Keep every result; do not rerun until a particular cause justifies it. A candidate measurement will
use this same frozen instrument and the same saved-input format, once its answers exist on approved GPU compute.

Sources: `t/PREDICT-2026-10-21-spec-ceiling.md`, `t/recipes/spec_ceiling.py`, and the encrypted input/output flow in
`.github/workflows/prepare-rows.yml`. This adds a remote execution path, not a new scoring rule.
