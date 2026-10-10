# T75: proof-engine correctness audit

Registered before the audit runs and implementation changes, from engine commit
`48c5e10`. The objective is to find and repair correctness defects in the engine
and its use by tup. Absolute flawlessness is not an established result: finite
testing, proof kernels, the host runtime and the stated specifications each have
limits. This record keeps those limits and outstanding work visible.

## First hypotheses and bars

1. Run the full collected engine test suite with the installed Dafny and Lean
   kernels. Record failures and skips; an unavailable dependency is not a pass.
2. A syntactically valid but ill-formed task must be rejected before twin search,
   lowering, cache lookup or kernel execution. The applications work already
   encountered an assertion outside a lemma that crashed verification. Probe
   `check`, `lower`, single-file and directory `verify`, and the library boundary.
   Named diagnostics must replace the traceback without accepting the task or
   silently weakening its specification. Valid controls must retain behavior.
3. Audit the evidence gate: a provisional result, a stale cache entry or an
   unconfirmed twin must not be described as established agreement. Register any
   additional concrete hypotheses before their experiments.
4. In tup, examine the native build driver and boot gate against their documented
   success conditions. Keep native execution, finite correspondence checks and
   mathematical model proofs distinct. No Linux correctness or new VM boot is
   inferred from a model proof.

Repairs require a failing control on the previous code, a passing control on the
repair, and relevant existing regression tests. A lowering change additionally
requires its whole kernel column. Canonical seven-kernel agreement tables are not
replaced by a partial run. Clean checkout checks will identify the exact revision
and commands; local development output alone is not a release claim.

## Prior work

Read `AGENTS.md`, `t/SPEC.md` (lemma bodies and well-formedness), the applications
prediction/read, `t/cli.py`, `t/tlib.py`, and existing well-formedness tests.
[LLVM's well-formedness rules](https://llvm.org/docs/LangRef.html#well-formedness)
distinguish parseable representation from valid input to subsequent passes. The
existing engine checker already supplies the required semantic diagnostics; the
initial hypothesis concerns which public entry points actually invoke it.

## Cache and confirmation probes (registered before their runs)

Source inspection found that `run_par` fingerprints its verifier adapter and
includes the repetition count in its cache key, but `tlib` includes neither.
Prediction: a library result measured with `flake=1` is reused for `flake=3`
without the extra runs, and an adapter change can reuse the old interpretation.
Use a deterministic fake backend to count calls; this tests orchestration and
does not claim a kernel proof. An unchanged three-run control must still hit the
cache. Changes to the adapter fingerprint, repetition count, source, version or
budget must miss. Corrupt cache data must be a miss rather than a traceback or a
verdict; timeout/tool-error results must not become permanent cached answers.

The library explanation and single-file CLI currently test only the last real
and twin outcomes. Prediction: a disagreeing repeat that ends verified/refuted
is labelled COUNTS and exits successfully despite `provisional=True`. Inject
that entry and require refusal; a confirmed entry must retain success.
Non-positive repetition counts must fail before any kernel runs.

Prior work: `run_par.adapter_fingerprint`, `cache_key`, `_cached_outcome`, and
`_record_sides` already implement the directory driver's stricter policy.
[Bazel's action cache](https://bazel.build/remote/caching) describes cache reuse
in terms of declared action inputs and results. Reuse the existing repository
policy at the library boundary rather than create a second weaker one.

## Read

Additional concurrency audit: library calls given one output root currently
write the same task filenames, and cache writers in one process share a
PID-derived temporary filename. Prediction: two simultaneous calls can verify
each other's source bytes, and two cache writes can collide at rename. Bar:
coordinate two threads with a barrier, require each verifier to read its own
task's source and both cache writers to finish with one complete readable entry.
The unique cache temporary-file implementation was drafted during inspection
before this race probe was registered; its race hypothesis is retrospective.
The source isolation probe and repair have not yet run.

The unchanged baseline (`python -m pytest -q .` from `t/`, Python 3.14.7,
pytest 9.1.1, Dafny 4.11.0 and Lean 4.33.1 on PATH) completed with 819 passed,
45 skipped, one expected failure, 23 passing subtests and five warnings. Other
kernels were absent. This result alone did not expose the input-boundary bugs.

The new invalid-input regression reached twin search, lowering and kernel
probing on the old library, and directory syntax errors escaped as exceptions.
The repaired CLI validates the whole directory before dispatch and emits the
same positioned semantic diagnostics as `check`. The library raises ValueError
before its witness or kernel work. Sixteen targeted existing/new checks and
eight subtests pass. The positive-control test initially misspelled Dafny's
capitalized method name; correcting that test is not an engine defect.

The cache probes reproduced stale repetition/adapter reuse, provisional COUNTS,
invalid-cache crashes/acceptance and cached transient failures. Library and
directory drivers now share adapter/repetition key construction and cacheable
outcomes. Library caches with the previous incomplete identity are deliberately
missed. Invalid counts fail before dispatch; provisional outcomes refuse success.

The coordinated source probe reproduced one call reading the other call's
`x + 2` program when it expected `x + 1`. Each call now owns a private source
directory, including when callers share an explicit output root. This changes
the source-file layout under `out_dir`, but not verdict fields or task syntax.
The original cache implementation, loaded from `48c5e10`, also reproduced a
FileNotFoundError when two same-process writes renamed one temporary filename.
Unique temporary files remove that collision. Sixteen new targeted tests and
41 subtests pass before adding the existing malformed corpus to the gate test.

The final targeted gate/cache/concurrency suite passed 17 tests and 127 subtests,
including all 86 existing semantic-error fixtures. Clean checkout `f3cb6a5`
then ran the complete collected suite: **836 passed, 45 skipped, one expected
failure, 150 passing subtests, five warnings**, no failing tests. The warnings
come from existing standalone test helpers returning counts after assertions;
they are not ignored failed assertions. The receipt is in
`t/evidence/2026-10-10-audit.json`.

The same clean engine verified tup's boot-acceptance task and its broken twin
with Dafny and Lean, three repeats per side. Both kernels refuted the legacy
integer model at the overflowing counter in three repeats, and compiled models
matched the original/fixed native Bash gates in all 3,872 comparisons. These
are additional end-to-end controls on the changed library and directory paths.

The broader audit remains open. Five kernels are not installed here; no full
seven-kernel matrix or new operating-system boot was performed. Parser and
lowering semantics beyond the registered cases, trusted toolchain dependencies,
remaining public entry points and tup's other build/release paths still need
review. In particular, five sandbox tests skipped because `landlock_exec.py`
is absent from this checkout; this is an explicit packaging/audit gap, not a
passed sandbox check. The existing expected failure is SPARK's two-loop
certificate fallback. Passing these checks does not establish absolute
flawlessness. The Landlock packaging gap is subsequently addressed in
`t/PREDICT-2026-10-10-sandbox-packaging.md` (T76); its restoration and runtime
checks are separate from the historical T75 counts above.
