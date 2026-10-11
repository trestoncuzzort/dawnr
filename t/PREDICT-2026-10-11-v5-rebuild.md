# Recover the v5 inputs and make the next comparison reproducible

Registered 2026-10-11 08:03Z, before generating any new comparison answer.

The requested next run needs the released v5 dataset, not just its specification-given subset.
Its recorded identity is 5,095 rows, SHA-256
`848fca29d9399ef91fcb867006e4ff42f60b53e9e2e084e4f1e93dae37811110`
([the original audit](decontamination-rows-2026-10-05.json)). Its six kinds are 933 English answers,
933 proofs beside Python, 839 specifications beside Python, 549 Python solutions, 639
specification-given proofs and 1,202 repairs. `student_rows.py` only builds the specification-given kind.

Searches of the restored lab, this checkout, release assets and the full Git history found no copy of that
file or the scratch builders named in the registrations. The checkout was shallow; the history
search was repeated after fetching all 2,085 commits. The published weights are available and
their three checksums pass. An archive location has been requested while recovery continues.

`restore_run.restore_set(force=False)` recovers 10,563 replies from 33 committed answer sets.
Of these, 203 historically test-passing, proved candidates concern 88 current training problems;
110 were proved by all seven. Their task JSON files are absent, so reconstruction and current
checks are required before any becomes a new training row. Historical verdicts alone do not admit them.
This recovers part of the input chain, not the missing 5,095-row file.

## Work before another training bill

1. Preserve the exact training bytes with every new adapter, before model loading. Verify an optional
   expected hash before allocating a GPU. Refuse an output directory whose frozen data or row-selection
   settings differ, including on checkpoint resume. Record the hash of the bytes actually read, not a
   second reading of a possibly changed source file after training.
2. Retain the recovered archive inventory and a machine-readable identity requirement for v5. A
   missing or different dataset must refuse the claim of a matched rebuild; padding or repeating rows
   to reach 5,095 is not a reconstruction.
3. Measure the saved October 11 candidate against the released v5 weights under identical inference
   and grading settings. This establishes a current baseline while the input recovery is unresolved.

Sources read before implementation: `student_sft.py`, `student_rows.py`, `graded_pool.py`,
`spec_first_rows.py`, `debug_rows.py`, `restore_run.py`, the teacher3 and release-v5 registrations,
and `locallm/dawnr_pipeline.py`'s input fingerprints. The local research mirror is unavailable.

## Matched comparison, fixed before either model answers

Both models are Q8_0, served by the same lab llama.cpp binary (`f1cee9941`), on CPUs with GPU layers
set to zero, one slot and one request at a time, 8,192 context tokens, thinking disabled. Each arm
gets one greedy answer per question and at most 1,024 generated tokens. The problem prompt is `s2`,
which fixes the nested-type spelling already diagnosed in
[the earlier experiment](PREDICT-2026-10-01-several-answers.md). The given-specification prompt is
the exact saved 33-question panel's own prompt. No repairs or extra attempts enter either score.

Report the requested clean-200 problems and all 33 specifications. Also report clean-182, because
18 of the 200 appeared in v5's training data. Nineteen of the 33 specification functions also appeared
in v5 training; the full-33 score is qualified accordingly. Report the old clean-14 subset only if
its exact membership can be recovered; do not infer that membership from the new model's results.

Grading uses the existing seven-kernel path, original tests, 1,000 per-task-seeded reference draws,
the pinned MBPP+ corrections, completeness at least 0.6 and larger-input checks. Publish all answers,
stage counts, task-bound verdicts and paired outcomes. Unknown or partial evidence never becomes a pass.

**Prediction M1:** the small recovered-data candidate does not strictly exceed v5 on both clean-182
all-seven problems and all-33 all-seven specifications. A strict increase on both falsifies M1.
Call a measured win only if clean-182 improves and the specification count does not fall; report the
paired gains and losses, not just totals. This is one candidate and fixed panels already used before,
not independent confirmation or a reproduction of v5's historical 17-call Python-first route.

This comparison adds no cloud spend. CPU services have memory, core and wall-time limits and exit
after saving their answers. Another GPU training run waits for an explicit, audited dataset identity
and its own bounded run registration.

## Input preservation measured

`student_sft.py` now saves `training-rows.jsonl` and `training-data.json` before model imports,
and accepts `--sft-sha256`. The final receipt uses that frozen identity. Previously it reopened
the source after training to calculate the hash: changing the source during training could label
the trained model with bytes it had never read. Reuse checks the snapshot bytes, receipt, row limit
and token limit; legacy checkpoints without input evidence are refused by name.

The [real-data control](out/v5-rebuild-20261011/input-identity-control.json) freezes the prior
406-row input byte for byte and refuses it against v5's registered hash before model dependencies
can load. Thirty row, trainer and generation tests plus two subtests pass on the lab, including
source deletion, changed input, corrupted snapshot, changed selection, incomplete snapshot and
legacy-checkpoint refusals. No GPU is used for these checks.

The [full-history content search](out/v5-rebuild-20261011/history-data-search.json) hashes 1,088
reachable JSONL blobs and finds zero matches for the v5 hash. Directly stored `.jsonl.gz` files
were decompressed where readable; compressed LFS pointers were skipped. The LFS filename and
object-identity inventory also has no matching source. These searches do not rule out an external backup.

## Matched specification result

The released v5 proves **28/33** by all seven; the recovered-data candidate proves **21/33**.
Both use Q8_0, the same server, identical chat templates, and the same questions. There are no
missing matrix rows or missing twins. The candidate has one well-formedness failure; v5 has none.
The [v5 counts](out/v5-matched-20261011/v5/spec-levels.json) and
[candidate counts](out/v5-matched-20261011/recovered/spec-levels.json) retain the other proof levels.
This is the current matched reading; it does not rewrite v5's historical 27/33 measurement.

The seven-question deficit already fails the registered no-regression condition. The programming
panel continues to completion so the remaining difference is measured too. The 19 known v5
training-overlap functions still qualify the full-33 result; the exact old clean-14 membership has
not been recovered.

All eight [CI jobs](out/v5-rebuild-20261011/ci.json) pass on the input-preservation commit
`0683081c`. The [live server receipt](out/v5-matched-20261011/server-parity.json) also confirms
matching chat-template hashes, one slot each and 8,192-token contexts.

## Grading amendment after the memory failure

At 09:15Z the v5 programming grader was [killed for exceeding its service memory limit](out/v5-matched-20261011/grading-restart.json),
before writing a matrix. The last completed Rocq source precedes `mbpp_748__capital_words_spaces`,
whose answer chains 26 string replacements. This is the source-expansion failure already described
in `run_par.py` and the September 17 run notes: the source-size check occurs after allocation.
No programming score had been produced. The other arm was stopped before completion as well.

Both programming panels will restart from the saved answers with a **4 GiB address-space limit
during lowering only**, through [the grading launcher](recipes/bounded-grading-python.py).
It restores the prior limit before kernel dispatch; proof budgets and acceptance rules do not change.
The existing runner records `MemoryError` as `lower-error`, never as a proof. The pinned engine
files stay unchanged. Earlier incomplete logs are retained, and neither arm reuses partial kernel
results. The completed specification panels remain the identical, earlier paired measurement.
The wrapper and its bound become part of the comparison's evaluator evidence.

The [control](recipes/v5-matched-2026-10-11-lowering-control.py) reproduces the refusal on
that actual answer in 3.11 seconds, preserves a normal Rocq lowering byte for byte, and verifies
that normal returns, exceptions and memory refusals all restore the previous limits
([receipt](out/v5-matched-20261011/lowering-control.json)). Both programming graders restarted
through [the same retry recipe](recipes/v5-matched-2026-10-11-retry.sh).

The bounded v5 retry then suffered a second service OOM at 09:31Z during Verus execution.
The lowering guard had worked: its log names the memory refusal and continues into kernel calls.
The status monitor initially read a stale progress log and missed the failed service; subsequent
polls inspect service state as well. Neither programming matrix was complete.

Both programming arms restarted again with identical **64 GiB service limits**, ten CPU cores
each, an eight-hour service deadline and `OOMPolicy=continue`. The 4 GiB lowering bound stays in
place. This service policy lets surviving processes continue when an individual process is killed
for memory exhaustion; it does not turn a failed tool call into a proof
([systemd documentation](https://github.com/systemd/systemd/blob/main/man/systemd.service.xml#L1244)).
The [operating receipt](out/v5-matched-20261011/service-memory-adjustment.json) records the change.
The candidate had no memory-limit events and peaked at 2.48 GiB, but was restarted too because
the service manager cannot change this OOM policy in place. No partial matrix results are reused.

All eight [CI jobs](out/v5-matched-20261011/ci.json) pass for the bounded-grading change `f3ed6a39`.
