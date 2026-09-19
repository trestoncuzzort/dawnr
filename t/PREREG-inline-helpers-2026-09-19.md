# Typed inline helpers: preregistration, 2026-09-19

Before the first kernel run of these probes, the change under test is a
surface extension: acyclic typed `inline fun` expression templates, including
seq, pair and nested-seq results, expanded hygienically to the existing AST.
No backend or core definedness rules change. This does not supply contracts,
recursive helpers, modules, or arbitrary imperative function calls.

Predictions and falsifiers:

1. Every accepted helper source elaborates to a well-formed old AST, which
   round-trips through the canonical printer. Any mismatch fails this gate.
   Existing surface/WF regression scripts and the grammar regeneration check
   must pass. The new tests include 150 seeded capture-avoidance cases, evaluated
   at five inputs each against the finite-quantifier meaning, plus explicit
   type/scope/arity rejection and short-circuit partial-expression cases.
2. The seven tasks in `inline-probes/` cover scalar composition, seq returns,
   pair returns, nested-seq returns, quantifier hygiene, guarded indexing and
   use from a spec function. Each is checked by all seven available kernels,
   with three flake repetitions for both real and mutated twin, no verdict
   cache. I predict at least four complete verified/refuted rows (28 cells),
   including scalar composition and pairs. Fewer falsifies this prediction.
   Unsupported lowerings, failures, timeouts and decorative twins are reported
   as outcomes, never counted as passes or repaired by narrowing preconditions.
3. Expanded ASTs have no inline declarations or calls. Thus backend support
   is precisely support for the resulting core shape; an unsupported nested
   sequence or quantifier remains an honest abstention. No increase in model
   accuracy or recovered external benchmark problems is predicted from this
   syntax measurement.

Run remotely after `python3 t/preflight.py --quick`, with the documented kernel
PATH, observing current CPU load. Cell concurrency is six kernel calls per job.
Start at 7 jobs (42 calls), using available CPUs as authorized; report flakes.

```
~/.venv-vllm/bin/python -m unittest discover -s t -p test_inline_helpers.py -v
python3 t/run_par.py --tasks t/inline-probes --jobs 7 --no-cache \
  --out t/out/inline-helpers-2026-09-19 \
  --table t/INLINE-HELPERS-2026-09-19.md
```
