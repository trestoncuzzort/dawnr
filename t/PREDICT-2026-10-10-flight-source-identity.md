# Flight source identity and comparison receipts

Registered before fetching the new manifest or running cache controls. The preceding correspondence change has
passed the native PX4 function and statement comparisons on the integration host; its complete-execution gates
must remain in force.

Read first: `t/cache.py` (write-once-visible atomic replacement), `t/cli.py` (fsync before replacement),
`t/verifiers/__init__.py` (SHA-256 of exact bytes), and the consumer's
`internal/RESEARCH-2026-10-10-verification-next.md`. External basis:
[GitHub's Git blob API](https://docs.github.com/en/rest/git/blobs) and
[SV-COMP's reproducible component inventory](https://sv-comp.sosy-lab.org/reproduce.php).

## Predictions

1. A committed manifest binds repository, full commit and source path to expected SHA-256 and byte length.
   Expected values come from fresh HTTPS responses at the pinned upstream locations, independently of an existing
   local cache. Reading an old cache alone can never establish its upstream identity.
2. A complete matching cache works offline. Altered cached bytes are refused, not silently replaced. Truncated
   or wrong downloads are never installed; files become visible only after validation and atomic replacement.
   Repository identity participates in the statement cache location, preventing cross-repository aliasing.
3. Optional JSON receipts identify the source manifest, actual source/task/generated-wrapper/input bytes,
   compiler version/target/flags, planned and returned counts, execution outcomes and explicit skipped coverage.
   Changing a source, task, wrapper, compiler flag or input changes the relevant identity. Public receipts omit
   local absolute paths, hostnames and raw diagnostics.
4. Existing complete-execution negative controls and flight-task audits still pass. A receipt documents bounded
   correspondence, not equivalence beyond sampled inputs or flight certification. Fixed working trees have a
   separate observed-bytes scope; their hashes must not be described as authenticated pinned upstream sources.

## Validation

Use deterministic temporary-cache tests for tampering, truncation, repository collision, changed inputs and
offline reuse. Compare freshly fetched source bytes with the committed manifest and run the existing flight
suite. The integration host replays both comparison scripts after review and consumer sync; do not invent its
result in this registration.

## Read

All four bars held in the local controls. Fresh GitHub Contents API responses supplied **48 source records**.
Each response named a full pinned revision; decoded bytes matched its returned Git blob SHA-1 and length before
the manifest's SHA-256 was calculated. Direct raw-source requests stalled and were stopped; no old cache supplied
an expected digest. The manifest retains the blob identifier as acquisition evidence.

`python3 -m pytest -q t/test_flight.py t/test_flight_execution.py t/test_flight_evidence.py` passed
**46 tests and 35 subtests**. These include changed cached bytes, truncated/wrong/oversized downloads, interrupted
installation, repository separation, validated legacy migration, unknown source refusal, offline reuse, source
manifest coverage, changed task/input/wrapper/flag identities, and path-free failure receipts. Python compilation
and `git diff --check` also passed.

Both native runners then completed with network access disabled and caches populated from those independently
acquired source bytes:

| runner | exit | receipt cases | planned/runtime result rows | source identities | explicit skips |
|---|---:|---:|---:|---:|---:|
| `px4_diff.py --receipt ...` | 0 | 27 | 7,062 / 7,062 | 36 | 10 |
| `px4_stmt.py --receipt ...` | 0 | 14 | 1,490 / 1,490 | 48 | 0 |

The first row includes 26 routine comparisons over 7,060 points and one finding replay with two inputs.
The compiler identified itself as GCC 16.2.1, target `x86_64-pc-linux-gnu`. Statement comparisons skipped no
inputs. Receipts contained no local checkout path. This is a fresh local replay; the subsequent clean consumer
sync and integration-host replay remain separate measurements.

Receipts are deliberately scoped identity records, not standalone bundles. They omit compiler executable bytes,
system headers, linked libraries and raw diagnostics. Fixed-tree files are marked observed/unverified. The
manifest checks sources before compilation and does not protect against external concurrent source mutation.
Legacy caches migrate only if their contents already match the manifest; mismatch leaves them untouched.

## Integration-host read

A frozen candidate snapshot with per-file SHA-256 checks replayed both commands
on the integration host, capped at 16 CPU equivalents and 8 GiB. Existing legacy
caches migrated through manifest validation. Both exited zero with GCC 13.3.0,
target `x86_64-linux-gnu`: 27 function/finding cases returned all 7,062 planned
rows, and 14 statement cases returned all 1,490 planned rows. Source identities
and skip counts matched the local replay. The consumer retains those JSON
receipts under `internal/evidence/2026-10-10-flight/`.

Independent review checked both local receipts against cached SHA-256 and Git
blob SHA-1, complete compile/runtime events, and planned/returned row counts;
it found no acceptance or pinned-identity defect. The combined flight and
changed-lowering targeted suite passed 91 tests and 35 subtests. Consumer sync
and its integration suite remain a subsequent step, not part of this result.
