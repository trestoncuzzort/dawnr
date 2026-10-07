# DafnyBench tasks in t (the D8 corpus)

These 326 tasks restate programs from [DafnyBench](https://github.com/sun-wendy/DafnyBench), 785 Dafny programs
collected from public repositories, with their specifications and verified bodies. DafnyBench is licensed under the
Apache License 2.0, and a copy is in `LICENSE-DafnyBench`. The programs were read from its `ground_truth` directory at
commit 0cd28feed9cd0179b07fdb9d002f8c39063658e4.

**How they were made.** dawnr's lifter (github.com/trestoncuzzort/dawnr, `t/lift_*.py`) translated each method whose
constructs t states into t's JSON form on 2026-09-15. It translated the `requires`, the `ensures`, the body, the loop
invariants and the predicates the method uses (as spec functions), and kept nothing else. Each file is named
`<DafnyBench file>.<method>.json`. 326 of the 785 programs have a method the lifter carried.

**The selection is not random.** The lifted methods are the ones whose constructs t states: integers, booleans,
sequences, bounded quantifiers, loops and recursion. Classes, generics, sets, multisets, maps over arbitrary types and
most array mutation are out. Numbers measured here describe these 326, not DafnyBench as a whole.

**What they are for.** `t/audit.py` measures each specification: every one-edit mutant of the body is run over the
task's bounded domain, and a mutant that computes something different while meeting the `ensures` everywhere is a
survivor. Dafny then checks the real body and the survivors. The table is `t/AUDIT-DAFNYBENCH.md` (PREDICT T54).
