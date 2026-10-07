# ACSL by Example in t (D8)

These 16 tasks restate C functions from [ACSL by Example](https://github.com/fraunhoferfokus/acsl-by-example),
Fraunhofer FOKUS's library of standard algorithms with ACSL contracts verified by Frama-C/WP. It is licensed under
the MIT License; a copy is in `LICENSE-acsl-by-example.md`. dawnr's C/ACSL lifter (github.com/trestoncuzzort/dawnr,
`t/lift_acsl.py`, `t/lift_acsl_corpus.py`) read `StandardAlgorithms` from the default branch on 2026-09-26 and
translated each function whose constructs t states, its contract and loop annotations included. The commit read was
not recorded; the branch head on 2026-10-07 is 3e8cd9adf79955d9b722185f9beb4518c66d57f2.

`t/audit.py --kernel framac` measures each contract: every one-edit mutant of the body is run over the bounded
domain, and Frama-C verifies the real body and any survivor. The table is `t/AUDIT-ACSLBYEXAMPLE.md` (PREDICT T56).
