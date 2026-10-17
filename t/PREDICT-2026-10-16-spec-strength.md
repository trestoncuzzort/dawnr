# PREDICT 2026-10-16 — specification-strength scorer (t/spec_strength.py)

**What it measures.** Per task, the mutation-based specification strength

    strength = killed / (killed + survivors)

over behaviour-changing one-edit mutants (`audit.classify`), plus a ranked worklist of the
survivors (operator, changed line, separating witness) — i.e. the under-constrained specs and the
exact counterexamples a stronger `ensures` must exclude.

**Why.** E1 measured a seven-kernel false-accept floor that is a SPECIFICATION gap, not a prover
gap (`internal/E1-FINDINGS-2026-10-14.md`): a false-accept is a survivor the spec accepts. The
literature our own notes distilled says the fix is to strengthen the spec against each surviving
mutant — mutation score AS specification strength, then refine against the surviving variant:
MutDafny (arXiv:2511.15403), FormalBench (arXiv:2503.04779), A1/FMCAD'24 (arXiv:2406.09757),
SpecRL negative-example completeness (arXiv:2604.05820), SpecSyn variant-discrimination refinement
(arXiv:2604.21570), ExVerus counterexample generalisation (arXiv:2603.25810). See
`internal/research/spec-validation.md` and `internal/research/vacuity-spec-strength-sweep-2026-09-20.md`.
This tool is the MEASUREMENT half; the refiner that consumes its worklist is the next step
(`t/spec_refine.py`), measured separately.

**Predictions, each with the number that falsifies it.**

1. On `t/tasks`, corpus spec-strength < 100% OR at least one task reports ≥ 1 survivor.
   FALSIFIED IF every task has strength 1.0 and zero survivors — then there is no gap on this
   corpus for the paper method to act on, and this is recorded as such.
2. The scorer is CONSISTENT with `audit.audit_file` on the same files: for every ok task,
   `killed == audit.killed`, `changing == audit.killed + len(audit.survivors)`, and
   `strength == killed/changing`. FALSIFIED IF any ok task disagrees (the scorer is wrong).
3. The scorer's corpus kill-rate equals `e1_adequacy`'s `spec_level.kill_rate` on the same corpus,
   within rounding. FALSIFIED IF they differ beyond rounding (one of them mismeasures).

**Success for THIS step.** The scorer runs on a corpus; predictions 2 and 3 hold (it measures the
same thing audit/E1 do, now as a ranked refinement worklist); prediction 1 reports whether a gap
exists to strengthen. It makes NO claim that any spec was strengthened — that is the next step.

## Result (measured 2026-10-16)

Prediction 2 HOLDS: t/test_spec_strength.py cross-checks the scorer against `audit.audit_file`
on a t/tasks sample; killed / changing / strength agree exactly. Both tests pass (run without
pytest — the two functions invoked directly).

Prediction 1, by corpus (pure interpreter, --seconds 15):
- t/tasks (114 hand-written): spec-strength 100.0% (1591/1591), 0 survivors — curated specs leave
  no behaviour-changing mutant un-refuted. Falsified-and-recorded here: no gap to strengthen.
- t/acslbyexample (16): 100.0% (457/457), 0 survivors — also clean.
- t/humanevaldafny (45 audited): 93.5% (1287/1377); 6 of 45 specs under-constrained. CONFIRMED.
  Weakest first, with the concrete counterexample:
    24%  parse_nested_parens  45 survivors  (witness s=[41] -> real 0, twin 1)
    49%  generate_integers    25            (compare-flip <=/< ; a=0,b=2 -> real [2], twin [])
    61%  specialFilter        13
    89%  make_palindrome       4
    93%  can_arrange           2
    96%  is_prime              1  (admits is_prime(1)=True; k=1 -> real False, twin True)

E1's benchmark false-accept floor is thus reproduced as a RANKED, per-survivor, witnessed worklist
(out/spec-strength-<corpus>.worklist.json, gitignored): the exact specs to strengthen and the
counterexample each must exclude. This step claims measurement only; no spec was strengthened yet —
that is t/spec_refine.py (next), which consumes this worklist.
