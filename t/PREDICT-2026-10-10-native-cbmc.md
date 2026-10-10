# Native machine-width pilot with CBMC, 2026-10-10

This is an experimental check of one extracted PX4 function, separate from the
seven t backends and their agreement counts. Existing research read first:
`internal/RESEARCH-2026-10-06-landscape.md`, the engine rules, the flight tasks,
and dawnr's `internal/RESEARCH-2026-10-10-verification-next.md` (rank 3).

Primary sources read before implementation:

- CBMC's [tutorial](https://diffblue.github.io/cbmc/cprover-manual/md_cbmc-tutorial.html):
  traces, module harnesses and successful unwinding assertions for complete scope.
- CBMC's [assumption coverage](https://diffblue.github.io/cbmc/cprover-manual/md_modeling-assumptions.html):
  check state-space non-emptiness separately from property success.
- [Kroening, Schrammel and Tautschnig, CBMC](https://arxiv.org/abs/2302.02384):
  bit-precise semantics; success with zero properties is vacuous.

Tool: official CBMC 6.11.0 Ubuntu 24.04 x86-64 release asset, SHA-256
`b3721aa541038384d7801ea3aeabbcddc3e8845ac8f1cbff637cf8dec7481ac8`,
extracted under a user-owned cache. No system installation.

Source: `src/lib/collision_prevention/ObstacleMath.cpp`, full source bytes retained
with the PX4 license under `t/native_fixtures/px4-wrap-bin/`:

- Original PX4 revision `dd804e4b9c490aed051bb36f8d3fca1ee137be2a`, SHA-256
  `90146c4c5d67ec86a97da974f92e892a0d75ad81c3e33c1d4f849830514e7ba6`.
- Published fix, PR #29030 head `07d30f9341dc02720eac2ed6fb9ee7524f8bd713`, SHA-256
  `d01b82d5cb76ae8449a3d0411c9a4dadf6c905ef44cce419f7d63cd9090fb8c2`.

The exact `int wrap_bin(int bin, int bin_count)` definition is extracted into a C
translation unit. Its body is unchanged; includes and the surrounding namespace
are omitted. Scope: 32-bit signed `int`, little-endian ILP32, all `bin` values,
`bin_count == 72`. A 72-element harness array tests the index result. This does
not verify PX4 callers, the entire module, hardware, timing or float semantics.

Predictions registered before the native runs:

1. Original code produces a traced counterexample to the range/array bound or
   signed-overflow check. A defined-arithmetic counterexample is replayable by
   the compiled native harness; an overflow witness is reported as undefined
   behavior rather than assigning it a mathematical result.
2. The exact published fix passes all generated safety/property checks over the
   stated 32-bit inputs. A mutation restoring the original expression is caught.
3. Contradictory input assumptions cannot receive a complete-check verdict even
   if ordinary assertion checking succeeds: assumption coverage must expose them.
4. A loop control checked with insufficient unwinding is incomplete. A sufficient
   bound passes with successful unwinding assertions. Bounded bug hunting is never
   labelled an unbounded proof.
5. Missing tools, timeouts, parser errors, empty/truncated JSON, missing property
   rows and contradictory terminal outcomes cannot produce a complete verdict.

Every receipt identifies source, extracted definition, generated wrapper, entry
function, tool version and binary, flags, process result and output digests. Runs
use a bounded CPU/memory allocation on the shared machine. No training or model
claims follow from this pilot.

## Outcome

The pilot is implemented in `t/native_check.py`; the negative controls and optional
real-tool integration suite are `t/test_native_check.py`. The six final receipts
are summarized in `t/native_fixtures/px4-wrap-bin/pilot-2026-10-10.json`, including
source/definition/wrapper/adapter hashes, CBMC binary identity, compiler identity,
exact flags, property outcomes, assumption coverage and native witness replay.
The full sanitized receipts and generated units were retained under
`t/out/native-cbmc-2026-10-10/`; raw tool streams remain in each run directory.

| case | unwind | measured result |
|---|---:|---|
| exact original definition | 4 | counterexample; 14 inventoried properties |
| exact published fixed definition | 4 | complete within the stated harness; all 14 properties succeed |
| fix mutated back to original definition | 4 | counterexample; 14 inventoried properties |
| fixed definition with contradictory assumptions | 4 | vacuous; assumption coverage rejects it |
| synthetic loop control, n in [0,3] | 1 | incomplete; unwinding assertion fails |
| same loop control | 4 | complete; all 6 properties, including unwinding, succeed |

Original and mutant both produce `bin = -2147483584, bin_count = 72`, with
`result = -64`; the actual extracted function compiled by GCC prints `-64`.
A separate trace gives `bin = 2147483632, bin_count = 72`; UBSan reports signed
integer overflow. That witness has no defined native result and is recorded as
undefined behavior, not as a wrapping arithmetic answer.

The first harness draft failed an additional conversion property introduced by
its own width diagnostic, `(unsigned int)-1`. This is a defined C conversion that
CBMC's stronger conversion-check policy rejects. The diagnostic now uses `sizeof`
checks without that conversion; production code and conversion checking were not
weakened. This caught a harness issue before the fixed-code result was accepted.

Measurements:

- Local: `python -m pytest -q t/test_native_check.py`: **30 passed, 6 skipped**
  (the six integrations require the `CBMC` environment variable).
- Lab, user-prefix CBMC 6.11.0:
  `CBMC=/path/to/cbmc python -m pytest -q test_native_check.py`: **36 passed**,
  no skips, **1.23 seconds**. The job was capped at 2 CPU equivalents and 4 GiB.
- The final six inventory/coverage/checking groups each took **0.12–0.14 seconds**
  on this machine. These tiny cases establish feasibility, not throughput on
  larger programs.
- Python compilation and diff whitespace checks passed.

All registered bars hold after the width-diagnostic correction. `complete` here
means the explicit range, array-access, arithmetic/conversion and other enabled
safety properties passed for all modeled int32 inputs with count 72. This pilot
does not establish the full mathematical modulo specification, equivalence of
all C++ contexts, safety for other counts, or whole-module correctness. The
independent SAT solver is trusted; no proof certificate was checked by one of the
seven t kernels, and their agreement counts are unchanged.

The gate checks a separate `--show-properties` inventory, exact assertion names,
one terminal result consistent with the property rows, per-property failure
traces, paired before/after assumption goals, and required unwinding assertions.
A successful process exit by itself never yields `complete`. The adapter accepts
only the two reviewed source hashes and the documented synthetic controls; it is
not a general C/C++ verification front end.
