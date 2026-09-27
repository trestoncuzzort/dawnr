# t cross-kernel agreement, 2026-09-27 07:19Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| vericoding_da0004__solve | verified / unproved | verified / unproved | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_da0008__solve | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0045__solve | verified / refuted | verified / unproved | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | timeout / refuted |
| vericoding_da0089__solve | verified / refuted | unproved / refuted | abstain / abstain | timeout / refuted | unproved / refuted | verified / refuted | verified / timeout |
| vericoding_da0107__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_da0122__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / timeout | unproved / refuted | verified / refuted |
| vericoding_da0143__solve | verified / refuted | unproved / unproved | timeout / refuted | abstain / abstain | unproved / unproved | abstain / abstain | malformed / malformed |
| vericoding_da0162__computeIntegerSquareRoot | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0181__solve | unproved / refuted | unproved / unproved | timeout / refuted | abstain / abstain | unproved / unproved | abstain / abstain | unproved / refuted |
| vericoding_da0218__parseInt | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0236__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0240__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / unproved | verified / refuted | abstain / abstain |
| vericoding_da0279__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0302__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0312__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0320__createString | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0324__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0327__solve | verified / refuted | unproved / unproved | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_da0350__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| vericoding_da0361__solve | unproved / refuted | unproved / unproved | timeout / refuted | abstain / abstain | unproved / unproved | abstain / abstain | unproved / refuted |
| vericoding_da0452__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0458__solve | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0508__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0534__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | abstain / abstain |
| vericoding_da0560__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_dh0060__isMonotonic | verified / unproved | verified / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dh0070__pluck | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | timeout / refuted |
| vericoding_dh0124__add_elements | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_dh0147__get_max_triples | timeout / refuted | verified / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_dj0091__cubeElement | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0096__replaceChars | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / timeout | timeout / refuted | verified / refuted |
| vericoding_dv0003__longestIncreasingSubsequence | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_dv0007__canCompleteCircuit | unproved / unproved | malformed / malformed | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | timeout / timeout |
| vericoding_dv0032__longestIncreasingSubsequence | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | unproved / refuted |
| vericoding_dv0043__maxSubarraySumDivisibleByK | verified / decorative | unproved / unproved | timeout / timeout | abstain / abstain | verified / decorative | unproved / unproved | unproved / unproved |
| vericoding_dv0052__minimumRightShifts | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dv0126__lastPosition | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | abstain / abstain | malformed / malformed |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `vericoding_da0004__solve.dfy` 4182df9a20cc59c7…, `vericoding_da0004__solve.rs` dfc174e6ac6c8cd8…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| dafny | 0 | 3 | (none) |
| verus | 0 | 11 | (none) |
| spark | 0 | 6 | (none) |
| framac | 0 | 17 | (none) |
| lean | 0 | 19 | (none) |
| rocq | 0 | 18 | (none) |
| fstar | 0 | 10 | (none) |

Of the 0 tasks in six, none are blocked alone.
