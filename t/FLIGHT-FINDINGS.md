# t cross-kernel agreement, 2026-10-07 23:29Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| px4_wrap_bin_any | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `px4_wrap_bin_any.dfy` ace9d2edca80527f…, `px4_wrap_bin_any.rs` 8dcf3aabf599eb90…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| dafny | 0 | 0 | (none) |
| verus | 0 | 0 | (none) |
| spark | 0 | 0 | (none) |
| framac | 0 | 0 | (none) |
| lean | 0 | 0 | (none) |
| rocq | 0 | 0 | (none) |
| fstar | 0 | 0 | (none) |

Of the 0 tasks in six, none are blocked alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| dafny | 1 | 0 | 0 of 0 | 0 |
| verus | 1 | 0 | 0 of 0 | 0 |
| spark | 1 | 0 | 0 of 0 | 0 |
| framac | 1 | 0 | 0 of 0 | 0 |
| lean | 1 | 0 | 0 of 0 | 0 |
| rocq | 1 | 0 | 0 of 0 | 0 |
| fstar | 1 | 0 | 0 of 0 | 0 |

Verified with the twin refuted in all seven columns: 0 of 1 tasks.
