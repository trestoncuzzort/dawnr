# t cross-kernel agreement, 2026-10-10 12:25Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | lean | fstar |
|---|---|---|---|---|---|
| abs | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| gcd | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| reverse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

Kernels present: 5 of 5 (dafny, verus, spark, lean, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- lean: Lean (version 4.33.1
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `abs.dfy` 9fe1e7e805cfacce…, `abs.rs` 750a8322fb7abf25…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all five |
|---|---|---|---|
| dafny | 0 | 0 | (none) |
| verus | 0 | 0 | (none) |
| spark | 0 | 0 | (none) |
| lean | 0 | 0 | (none) |
| fstar | 0 | 0 | (none) |

Of the 0 tasks in four, none are blocked alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| dafny | 3 | 3 | 3 of 3 (100%) | 0 |
| verus | 3 | 3 | 3 of 3 (100%) | 0 |
| spark | 3 | 3 | 3 of 3 (100%) | 0 |
| lean | 3 | 3 | 3 of 3 (100%) | 0 |
| fstar | 3 | 3 | 3 of 3 (100%) | 0 |

Verified with the twin refuted in all five columns: 3 of 3 tasks.
