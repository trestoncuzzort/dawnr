# PREDICT 2026-10-16 — specification-refinement verify harness (t/spec_refine.py)

**What it is.** The VERIFY half of specification refinement (ExVerus arXiv:2603.25810, SpecSyn
arXiv:2604.21570): given a task and a proposed strengthening `extra` (one or more t AST `ensures`
conjuncts), `check(task, extra)` appends them and reports, kernel-free, whether the real body still
satisfies the strengthened spec (`audit.classify` returns status `real-violates-spec` when it does
not) and how many behaviour-changing mutants the spec still admits (survivors before/after). A
proposal is `accepted` only if the real body still verifies AND strictly fewer survivors remain.
A proposer (a model, or a human) supplies `extra`; this harness is the gate every proposal passes.

**Worked case.** `humaneval_dafny_031_is_prime` is under-constrained (t/spec_strength: 96%, one
survivor — the spec admits `is_prime(1)=True`; witness k=1 → real False, twin True). The missing
clause is `result ==> k >= 2`. Real `is_prime(1)=False` makes `False ==> …` hold; a mutant returning
True makes `True ==> 1>=2` false, so it is killed.

**Predictions, with the number that falsifies each.**

1. `check(is_prime, [result ==> k>=2])` returns `real_ok=True`, `survivors_before>=1`,
   `survivors_after==0`, `accepted=True` (strength 96% → 100%). FALSIFIED IF the real body is
   reported as violating the strengthened spec, or any survivor remains.
2. Negative control (fail-closed, AGENTS.md Rule 2): `check(is_prime, [result])` — forcing the
   postcondition `result` true always — returns `real_ok=False`, `accepted=False`, because the real
   body returns False at k=1. FALSIFIED IF such a spec-breaking strengthening is `accepted`.

**Success for THIS step.** The harness strengthens one real under-constrained spec against its
surviving twin and verifies it deterministically, and rejects a strengthening that breaks the real
program. It does NOT yet auto-propose clauses for all weak specs — that is the next step (a model
proposer over the t/spec_strength worklist, verified by this harness; AWS/Fable available).
