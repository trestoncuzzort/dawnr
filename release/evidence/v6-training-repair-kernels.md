# t cross-kernel agreement, 2026-10-18 09:35Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| findLUSlength_original | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved |
| findLUSlength_strengthened | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / unproved |
| move_first_original | unproved / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| move_first_strengthened | unproved / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `findLUSlength_original.dfy` 677d956cc466b3c5…, `findLUSlength_original.rs` 1c0941da3822905f…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| fstar | 1 | 3 | findLUSlength_original |
| dafny | 0 | 2 | (none) |
| verus | 0 | 2 | (none) |
| spark | 0 | 0 | (none) |
| framac | 0 | 0 | (none) |
| lean | 0 | 2 | (none) |
| rocq | 0 | 3 | (none) |

Of the 1 tasks in six, 1 is fstar alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| dafny | 4 | 2 | 2 of 2 (100%) | 0 |
| verus | 4 | 2 | 2 of 2 (100%) | 0 |
| spark | 4 | 4 | 4 of 4 (100%) | 0 |
| framac | 4 | 4 | 4 of 4 (100%) | 0 |
| lean | 4 | 2 | 2 of 2 (100%) | 0 |
| rocq | 4 | 1 | 1 of 1 (100%) | 0 |
| fstar | 4 | 2 | 0 of 2 (0%) | 0 |

Verified with the twin refuted in all seven columns: 0 of 4 tasks.
