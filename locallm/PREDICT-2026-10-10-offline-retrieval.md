# Offline retrieval after updates and interrupted writes

Registered at dawnr ca6bc23 before the new controls or implementation changes.
The target is dawnr's existing assistant and retrieval runtime. Its network is
optional, while documents already saved locally must remain useful when the
connection goes away.

Inspection of dawnr_retrieval/cache.py suggests four failure classes: Unicode
line separators inside page text are mistaken for record boundaries; invalid
UTF-8 or malformed field types can abort the whole load; revisiting a URL can
keep obsolete chunks because the index takes the first occurrence of an id;
and appending after a truncated record can lose the next complete record.
These are hypotheses until the controls reproduce them.

Bars: preserve Unicode text exactly; report malformed individual records while
retaining surrounding valid pages; select the last valid complete snapshot of
each URL, including removal of old trailing chunks; recover a new complete
append after a partial tail; keep all fetched content untrusted. Exercise
search_knowledge through the real offline harness with network access replaced
by a failing control. Retain existing corpus holdout and passage-trust tests.

Deploy dawnr itself on the fresh Linux account using its existing pinned CPU
installer and model files. Measure its actual commands and runtime tests there;
do not infer GPU support from hardware that the account cannot access. The lab
is shared, so compilation and proof jobs keep explicit concurrency and memory
bounds. A failed install or unavailable sandbox remains a reported limitation.

Bring the tested t engine fixes into dawnr's pinned copy first. The existing
dawnr-owned landlock_exec.py and the engine's newly restored copy have identical
SHA-256 5099f8a4ec58d6099c939ae6af5019c04d9c6bef6880b342c24690c676d26e3d.
Keep that file in the sync script's explicit dawnr-owned list and verify the
bytes after syncing; do not discard a differing local implementation.

Prior work: DAWNR-RETRIEVAL.md, DAWNR-HARNESS.md, the retrieval-on-the-base
registration, the existing cache/index/harness tests, and runtime.py's audit
writer, which already escapes Unicode record separators. The local research
mirror is absent on this checkout. JSON Lines specifies UTF-8 records separated
by newline: https://jsonlines.org/. Python's JSON decoder and file byte I/O
provide independent round-trip and malformed-record controls:
https://docs.python.org/3/library/json.html.

All nine initial controls failed before repair. The loader now processes UTF-8
records one line at a time, validates complete page records and retains the
last valid snapshot per URL before chunking. The writer validates before
touching the cache and separates an interrupted tail from the next record.
The real offline-harness control returns the current page in an untrusted
span and taints the session without reaching DNS or a network connection.

The affected retrieval and harness suites passed 108 tests:

```sh
python -m pytest -q locallm/test_retrieval_cache_recovery.py \
  locallm/test_dawnr_retrieval.py locallm/test_harness.py \
  locallm/test_harness_adversarial.py
```

The t engine pin was updated to 1d584f6 in dawnr commit 45476a3. The preserved
sandbox helper retained the registered digest. Dawnr's consumer checks passed
62 tests and 108 subtests (CLI, tlib, validation, witness contexts, asynchronous
editor verdicts and sandbox packaging).

Fresh-account replication at clean dawnr revision 54dc675 completed: the same
108 retrieval/harness tests passed, as did 62 engine-consumer tests and 108
subtests. The existing CPU installer installed the published student, base
model and llama.cpp server. A real `dawnr calc` control returned 180 with three
matching exact workings; `dawnr cite` answered from README.md and quoted the
sentence supporting its --online answer. These are installation controls, not
accuracy or throughput benchmarks.

All seven native proof adapters passed abs, gcd and reverse: 21
verified/refuted cells, three repetitions per side. The original Alt-Ergo-free
2.4.3 driver configuration from the project was reproduced. Rootless build
dependencies needed relocation fixes before the opam transaction completed.

The host denies bubblewrap namespace creation. `dawnr doctor` reports that
limit, and `dawnr ask` exits unsuccessfully before running model-written
Python. No system security policy or device permissions were changed. The
complete corpus, flight, fixes, autonomy and PX4 correspondence sweep remains
in progress and is not counted in these results. Receipts are in
`locallm/evidence/2026-10-10-offline-runtime/`.
