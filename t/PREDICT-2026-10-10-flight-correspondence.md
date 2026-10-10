# Flight correspondence must reject incomplete executions

Registered 2026-10-10 after read-only probes against the current implementation and before changing the harnesses.

The existing `px4_stmt.py` runner ignored the executable's exit status. A compiled negative control printed its
first result and trapped on its second input; the runner returned the one-result prefix without error. A separate
control supplied one result for three scheduled inputs: both statement comparisons reported `1/1`, although the
real counterexample had not run. With every compilation replaced by an explicit failure, `px4_diff.main` returned 0.
These are instrument defects, not evidence that a particular recorded PX4 run was incomplete.

The design follows [BenchExec's resource and termination accounting](https://github.com/sosy-lab/benchexec/blob/main/doc/resources.md)
and the distinction between execution outcomes and verified properties in the
[CBMC tutorial](https://diffblue.github.io/cbmc/cprover-manual/md_cbmc-tutorial.html).
Only successful, complete executions on a nonempty set of admissible inputs may establish correspondence.

## Predictions

1. Regressions fail before the patch for nonzero runtime exits, truncated output, and compilation errors that
   previously resulted in successful CLI status. Full output followed by a nonzero exit is also refused.
2. Missing, extra, malformed, and wrong-width statement result rows are refused before comparison. Empty domains
   and domains with no admissible input cannot produce agreement; malformed integer/float output cannot either.
3. Compile/runtime timeouts and unavailable executables are named execution errors. CLI runs containing one cannot
   succeed. Explicitly documented unsupported tasks remain named skips, but an entirely skipped run fails.
4. Complete, successful controls preserve integer, float-narrowing, and original/fixed statement comparisons.
   The existing flight-task tests keep their assertions. No specification, witness, source pin, or proof verdict changes.

## Validation plan

Run `python3 -m unittest discover -s t -p 'test_flight_execution.py' -v` against the unchanged runner first, then
against the patch. Use mocked subprocess outcomes for deterministic error coverage and a real local C++ subprocess
that exits unsuccessfully after a flushed prefix where a compiler is available. Run
`python3 -m pytest -q t/test_flight.py t/test_flight_execution.py`. Real pinned PX4 comparisons are a separate integration check, with
their exit statuses retained. No matrix rerun is needed: lowerings and kernel adapters are untouched.

## Read

The original 22 regression methods produced **21 failed assertions and 13 errors** across their subtests before
the patch. In particular, the real compiled prefix-then-exit control was accepted, and an all-compilation-error
CLI run returned success. The same 22 methods passed after the patch.

Four additional controls preserve complete original/fixed comparisons and the documented float narrowing case,
and require the statement CLI to fail on execution errors or an empty pair set. The combined run
`python3 -m pytest -q t/test_flight.py t/test_flight_execution.py` passed **30 tests and 23 subtests**. That includes
all four existing flight task/finding/fix audits. `git diff --check` passed for the changed files.

All four predictions held in these controls. The local cache of pinned PX4 sources is absent, so the real-source
integration replay is still owed; this patch does not claim a fresh count of PX4 comparisons. Source-cache hashes
and persisted toolchain receipts are separate follow-up work. No task, contract, source pin or backend changed.
