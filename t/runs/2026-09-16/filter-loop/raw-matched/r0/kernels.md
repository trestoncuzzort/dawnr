# t cross-kernel agreement, 2026-09-16 22:40Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| r0_s168 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| r0_s182 | verified / refuted | verified / refuted | verified / refuted (FLAKED) | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| r0_s254 | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| r0_s279 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| r0_s460 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| r0_s499 | refuted / refuted | refuted / refuted | timeout / vacuous | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| r0_s68 | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `r0_s168.dfy` 774aa86aa3ac3c9f…, `r0_s168.rs` a26a17e32a11af0e…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| spark | 1 | 0 | r0_s182 |
| dafny | 0 | 0 | (none) |
| verus | 0 | 0 | (none) |
| framac | 0 | 0 | (none) |
| lean | 0 | 0 | (none) |
| rocq | 0 | 0 | (none) |
| fstar | 0 | 0 | (none) |

Of the 1 tasks in six, 1 is spark alone.
