# Source corpus construction, 2026-09-19

Written before the builder runs. The local source inventory contains about 193 MB
of candidate source text across CPython Lib/Doc, Rust library, and Mathlib. Pin:

- CPython: `1d0f1ad0aa7a933e8d03f855d9b5eed7e00e775d`.
- Rust: `971903d9aee24befd88423f42826c232e27c8190`.
- Mathlib: `dec5b2b780537b6eaf7f5e5f000c12f7387fb24d`.

Predictions: the declared exclusions and global deduplication retain more than
100 MB of source text; every selected path is accounted for; no file is truncated;
training and validation share zero module families, exact hashes, or normalized
hashes. Any missing selected path or nonzero overlap fails the integrity bar.
Retaining 100 MB or less falsifies the size prediction but does not justify relaxing
the filters. A second build from the same commits and seed, with a different worker
count, must reproduce the corpus and provenance hashes exactly.

Default validation assignment is a stable hash of seed 1337 and module family
with a 0.1 probability per family. The measured fraction by bytes may differ from
0.1. The family heuristic groups related implementation, test, and module-doc paths
where names match; it does not claim to identify every semantic dependency.

No model-generated additions, source execution, learned tokenizer, training, or
task evaluation is part of construction. Preserve upstream text, root and nested
license snapshots, origin URLs, resolved commits, per-file hashes, and exclusions.
Run the fixture integrity tests before the real build. A missing root license or
a changed tracked checkout causes a refusal. Existing output is never overwritten.

## Follow-up after decoded-window inspection

The first corpus passed its structural checks, but a decoded training window
exposed the generated CPython `mac_cyrillic.py` codec table. Its quoted
`Python Character Mapping Codec ... generated from` header was not recognized.
The first build remains unchanged and fails this content inspection.

Before rebuilding v2: recognize that specific codec header and quoted explicit
`This file/code is/was generated` notices. Ordinary prose describing code
generation must remain eligible. Predict at least two newly excluded generated
files, more than 100 MB retained, and zero cross-split family/hash overlap.
Fixture tests must cover the actual codec header and retain generation docs.
Write v2 to a new directory; do not replace the failed v1 artifacts.
