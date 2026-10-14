# E1 paired grounded-witness run data (two independent runs)

`pass1/` and `pass2/` hold each run's RESULT and identity artifacts: the frozen manifest
(`E1PAIRS2-MAN.json`), run metadata (`E1PAIRS2-RUNMETA.json`), the authoritative per-cell resolution
(`E1PAIRS2-RESOLUTION.<eff>.json`), the lowered-source index (`E1PAIRS2-SRC-INDEX.<eff>.json`, content
digests of every lowered source) and the aggregated curve (`CURVE-postfix.json`). The coverage curve is
recomputable from the resolution alone.

NOT committed (size): the raw append-log `E1PAIRS2.jsonl` (~6 MB/run) and the retained lowered sources
`src/` (~32 MB/run, 4,295 files). Those are retained on the lab run dirs
(`out/e1-pairs-v2-pf`, `out/e1-pairs-v2-pass2`); the independent structural validator
(`../e1_structural_validator.py`) byte-re-hashes `src/` against the index THERE, and its attestation is
committed as `../E1-PASS1-STRUCTURAL-2026-10-14.json` / `../E1-PASS2-STRUCTURAL-2026-10-14.json` (both
PASS: 2982/2982, 0 missing/dup/unexpected, 4295 unique sources re-hashed, 0 stable-VERIFIED twins).

Gate reproducibility in-repo does NOT need those files: each verdict's certificate replays from the
archived pair in `t/twins/pairs` via `dawnr check` (re-lowers + re-runs the kernel, no model). Regenerate
the full 2,982-cert set with `t/e1_batch_cert.py mint-run <run-dir> t/twins/pairs <cert-dir>`.
