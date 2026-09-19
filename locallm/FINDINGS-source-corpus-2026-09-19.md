# Source corpus and training-data gate, 2026-09-19

The first source corpus failed content inspection: a decoded training window
contained a generated CPython codec table. The header filter missed quoted
codec-generation notices. Structural checks and byte-identical reproduction
had passed, so those checks alone did not establish suitable training content.
The first build remains preserved and rejected.

[The builder](build_source_corpus.py) now recognizes those notices and explicit
quoted file-generation headers while retaining ordinary documentation about
code generation. Version 2 removes exactly **65 generated codec files** and
**1,197,737 source bytes** from training. No other inclusion decision changes;
validation text is byte-identical. Generated-header exclusions rise from 43 to
108. The [registered follow-up](PREREG-source-corpus-2026-09-19.md) predicted at
least two additional exclusions and more than 100 MB retained; both hold.

Version 2 retains **12,880 files / 181,200,765 source bytes** from 13,184 selected
files in the pinned official CPython, Rust, and Mathlib repositories. Revisions,
source scopes, counts, and artifact hashes are in
[the sanitized results](source-corpus-results-2026-09-19.json).

| split | files | module families | source bytes | corpus bytes, including markers |
|---|---:|---:|---:|---:|
| train | 11,237 | 2,028 | 152,412,017 | 153,093,619 |
| validation | 1,643 | 225 | 28,788,748 | 28,886,620 |

The included mix is 40,105,764 bytes of code, 30,006,780 of tests, 12,787,340
of documentation, and 98,300,881 of proofs. Whole module families are assigned
by a stable hash with seed 1337 and validation probability 0.1; validation holds
15.8878% of source bytes. Family, exact-hash, and normalized-hash overlap across
splits are zero; no files are truncated. Normalization compares whitespace and
line endings, not meaning. Structural grouping and benchmark-name exclusions
do not establish freedom from semantic contamination.

Original file headers remain intact, alongside 23 license/copyright/notice
snapshots and per-file provenance. These records do not assign a single license
to the corpus. Eight [builder tests](test_source_corpus.py) passed, covering the
missed headers, retained documentation, attribution, exclusions, split integrity,
and deterministic output across worker counts. The rejected first full build
reproduced all 29 artifacts with four versus eight workers. Version 2 has the
fixture reproducibility check and the measured revision comparison; a second
full version-2 build was not run as part of this report.

Separately, [the supervised dataset gate](../t/loop_dataset.py) now requires
seven distinct named clean kernels and explicit spec agreement with positive
valid-draw count, matching current task hash, problem ID, and pool. It checks
evidence before deduplication. Imported pairs must also match the current
recorded prompt, an admissible negative, and the training split. Disagreement
negatives require current explicit evidence too.

A read-only audit of the 35 round-6 tags plus `prover-train`, against split-v5,
changes accepted training data from **210 distinct programs across 94 problems
to zero**. All 210 lack fresh hash-bound spec evidence. This is a corrected
evidence requirement, **not a measured quality regression**. Eval acceptance
similarly changes from 31 programs across 16 problems to zero. The audit creates
no pairs or negatives and changes no historical datasets. New supervised rounds
must obtain that missing evidence first. Seven [dataset-gate tests](../t/test_loop_dataset.py)
and six [spec-check tests](../t/test_spec_check.py) passed: **13 total**.

The source corpus is plain-text pretraining data. This report makes no claim
about model quality or a completed training run; the matched architecture
experiment is separate.
