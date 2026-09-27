# t cross-kernel agreement, 2026-09-27 05:45Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| vericoding_da0018__solve | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0031__solve | verified / refuted | verified / unproved | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_da0071__solve | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0078__solve | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | lower-error / lower-error | unproved / refuted | verified / refuted |
| vericoding_da0080__solve | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0101__solve | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| vericoding_da0105__solve | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0108__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_da0110__solve | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0123__solve | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_da0144__solve | verified / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_da0151__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_da0153__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_da0157__solve | timeout / refuted | unproved / refuted | verified / refuted | timeout / refuted | unproved / refuted | unproved / unproved | verified / refuted |
| vericoding_da0159__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0168__solve | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0173__solve | verified / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_da0205__solve | timeout / refuted | unproved / refuted | timeout / refuted | timeout / timeout | timeout / unproved | unproved / unproved | timeout / timeout |
| vericoding_da0239__solve | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | lower-error / lower-error | unproved / refuted | verified / refuted |
| vericoding_da0282__solve | timeout / refuted | verified / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0368__solve | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0399__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted |
| vericoding_da0429__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0482__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0484__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0497__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0505__solve | verified / refuted | unproved / refuted | verified / refuted | timeout / timeout | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0524__solve | timeout / refuted | unproved / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_da0530__solve | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0538__computeMaxGroups | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0556__solveCakeProblem | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | unproved / refuted | unproved / refuted |
| vericoding_da0577__solve | unproved / refuted | unproved / unproved | timeout / refuted | abstain / abstain | unproved / unproved | abstain / abstain | unproved / refuted |
| vericoding_da0585__solve | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0586__solve | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0609__getRow | verified / refuted | unproved / refuted | malformed / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_da0659__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_db0053__modExp_int | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | verified / refuted | unproved / refuted |
| vericoding_dd0356__mod | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_dd0518__findAddends | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_dd0794__sumOfFourthPowerOfOddNumbers | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_dd0875__rolling_max | verified / refuted | unproved / unproved | timeout / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_dh0021__largest_divisor | unproved / refuted | unproved / refuted | timeout / timeout | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_dh0051__modp | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| vericoding_dh0074__smallest_change | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dh0079__is_cube | timeout / refuted | unproved / refuted | verified / refuted | timeout / refuted | unproved / refuted | unproved / unproved | verified / refuted |
| vericoding_ds0053__sumArray | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / unproved | unproved / refuted |
| vericoding_dt0088__leftShift | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | timeout / refuted | unproved / refuted |
| vericoding_dt0258__numpyBitwiseOr | refuted / unproved | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `vericoding_da0018__solve.dfy` ea78c20c6d315e6f…, `vericoding_da0018__solve.rs` b7b4925f8bd6cf59…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| rocq | 2 | 29 | vericoding_da0538__computeMaxGroups, vericoding_da0659__solve |
| lean | 1 | 25 | vericoding_da0399__solve |
| dafny | 0 | 6 | (none) |
| verus | 0 | 18 | (none) |
| spark | 0 | 9 | (none) |
| framac | 0 | 25 | (none) |
| fstar | 0 | 9 | (none) |

Of the 3 tasks in six, 2 are rocq alone, 1 is lean alone.
