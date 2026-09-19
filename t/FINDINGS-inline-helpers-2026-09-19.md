# Inline helpers: results, 2026-09-19

The predicted four complete seven-kernel rows did not appear: **three of
seven rows passed**, with **29 of 49 cells verified/refuted**. Scalar helper
composition, pair returns and guarded indexing passed all seven. Sequence
composition passed six; Frama-C was its sole blocker. This is a useful source
language extension, not evidence that every backend supports every result
shape, and not evidence of improved model accuracy.

The [preregistration](PREREG-inline-helpers-2026-09-19.md) is unchanged. The
[generated matrix](INLINE-HELPERS-2026-09-19.md) records every cell. There were
31 cells with actual kernel execution: three runs per real and twin, 186
fresh verifier invocations (excluding backend-internal audit subprocesses),
with no recorded flake. The remaining 18 cells were 4 named
lowering abstentions and 14 no-twin refusals, not kernel successes.

| Probe | Complete cells | What the result establishes or blocks |
|---|---:|---|
| scalar | 7/7 | Earlier-helper composition expands and verifies. |
| pair | 7/7 | Pair-valued division/remainder helper retains `y > 0` and its obligations. |
| guard | 7/7 | Empty-sequence guard preserves short-circuit indexing definedness. |
| seq | 6/7 | Existing Frama-C lowering refuses concat into an exact-length return. |
| hygiene | 2/7 | SPARK/F* pass; Dafny/Verus real is unproved; Frama-C/Lean/Rocq abstain on executable quantifiers. |
| nested | 0/7 | Existing mutation selector finds no twin for `[[x]]`; no kernel claim was made. |
| spec | 0/7 | Existing mutation selector finds no twin for `twice(x)`; no kernel claim was made. |

These limits concern the expanded core shapes and the existing suite. A
separate regression test compares all seven expanded bodies to independently
written core expressions, including the renamed quantifier and expanded
spec-function definition. The source extension introduces no backend node,
assumed contract, extra precondition, or change to mutation selection.
The unsupported rows remain in the matrix unchanged; no post-hoc replacement
probe or reduced success bar is used.

The implementation checks every definition and actual argument before
substitution, renames quantifier binders, preserves the contextual type of
empty nested sequences, and checks the expanded task again with no helper
signatures. The [tests](test_inline_helpers.py) exercise unused bad arguments,
invalid unused definitions, duplicate names/parameters, forward and recursive
references, spec-function boundaries, expansion budgets, source positions,
short-circuit definedness, and 150 seeded capture-avoidance programs at five
inputs each against an independent semantic oracle. The canonical printer
prints the expanded program; declarations are source sugar.

Validation was run on the lab workstation. Twelve helper tests pass, including
xgrammar acceptance and handwritten-core equivalence. Existing regression
checks pass: 9 malformed parser fixtures, 43 positioned WF fixtures, 35
committed tasks with no WF errors, 44 direct WF checks, and the generated
identifier grammar check. Structural fuzz round-trips **5,000/5,000** random
ASTs (seed 19). The full surface check round-trips **1,783/1,783** well-formed
tasks in both directions, with 22/22 documented examples, 3/3 literal probes
and 8/8 expected syntax refusals. No helper-expansion defect was observed.

The existing remote preflight passed for all seven kernels. Its version did
not have `--quick`; the existing remote runner did not have `--no-cache` and
runs fresh by default. Accordingly the measured command omitted those two
unsupported switches. Inherited unverified local lowering/runner/cache edits
were deliberately not copied into this measurement. The exact measured remote
[source hashes](inline-source-sha256-2026-09-19.txt) and backend versions in the
matrix identify the instrument. CPU load before the run was about 13 on 120
logical CPUs; `--jobs 7` permits 42 concurrent kernel calls. No GPU was used.

```
python3 t/preflight.py
python3 t/run_par.py --tasks t/inline-probes --jobs 7 \
  --out t/out/inline-helpers-2026-09-19 \
  --table t/INLINE-HELPERS-2026-09-19.md
```

Next language work should address measured functional limits separately:
executable finite quantifiers, the concat-return lowering, and meaningful
mutation of nested constructors/spec calls. The inline feature itself does
not remove those barriers, supply recursion/contracts for helpers, or prove
that the external function-contract census has been recovered.
