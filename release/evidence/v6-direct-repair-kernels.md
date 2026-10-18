# t cross-kernel agreement, 2026-10-18 10:05Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| addDigits_original | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| addDigits_strengthened | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| check_original | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | unproved / refuted |
| check_strengthened | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | unproved / refuted |
| combat_original | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| combat_strengthened | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| enough_original | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| enough_strengthened | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| expression_matter_original | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| expression_matter_strengthened | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| last_Digit_Factorial_original | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| last_Digit_Factorial_strengthened | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| make_negative_original | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| make_negative_strengthened | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `addDigits_original.dfy` 35117bb46c809850…, `addDigits_original.rs` 2e575288ae4adac2…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| lean | 2 | 2 | expression_matter_original, expression_matter_strengthened |
| dafny | 0 | 0 | (none) |
| verus | 0 | 0 | (none) |
| spark | 0 | 0 | (none) |
| framac | 0 | 2 | (none) |
| rocq | 0 | 2 | (none) |
| fstar | 0 | 2 | (none) |

Of the 2 tasks in six, 2 are lean alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| dafny | 14 | 14 | 14 of 14 (100%) | 0 |
| verus | 14 | 14 | 14 of 14 (100%) | 0 |
| spark | 14 | 14 | 14 of 14 (100%) | 0 |
| framac | 12 | 12 | 12 of 12 (100%) | 2 |
| lean | 14 | 10 | 10 of 10 (100%) | 0 |
| rocq | 12 | 12 | 12 of 12 (100%) | 2 |
| fstar | 14 | 12 | 12 of 12 (100%) | 0 |

Verified with the twin refuted in all seven columns: 10 of 14 tasks.
