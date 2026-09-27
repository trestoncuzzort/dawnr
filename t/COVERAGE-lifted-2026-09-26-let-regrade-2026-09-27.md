# t cross-kernel agreement, 2026-09-27 06:50Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| humaneval_dafny_059_largest_prime_factor__is_prime | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / unproved | verified / refuted |
| vericoding_da0002__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / unproved | verified / refuted |
| vericoding_da0044__count_eights_iterative | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0069__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0070__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0075__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0132__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0136__solve | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / unproved | verified / refuted |
| vericoding_da0162__parseInteger | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0203__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0334__computeFactorial | timeout / refuted | timeout / refuted | abstain / abstain | timeout / refuted | unproved / refuted | timeout / refuted | timeout / timeout |
| vericoding_da0334__computePower | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_da0383__checkLampArrangement | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0419__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0439__skipNewline | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0455__solveCookieDistribution | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0535__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_da0590__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / refuted |
| vericoding_da0621__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0641__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0661__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_db0028__computeExp | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_db0042__exp_int_exec | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_db0044__pow_nat | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_dh0036__count7 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dh0099__multiply | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_dh0160__eat | verified / timeout | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / refuted |
| vericoding_dv0154__maxArray | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `humaneval_dafny_059_largest_prime_factor__is_prime.dfy` c9c933328e8ddbff…, `humaneval_dafny_059_largest_prime_factor__is_prime.rs` 2c32ba064de2d9b9…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| lean | 2 | 5 | vericoding_db0042__exp_int_exec, vericoding_db0044__pow_nat |
| rocq | 1 | 6 | vericoding_da0590__solve |
| dafny | 0 | 1 | (none) |
| verus | 0 | 1 | (none) |
| spark | 0 | 1 | (none) |
| framac | 0 | 1 | (none) |
| fstar | 0 | 0 | (none) |

Of the 3 tasks in six, 2 are lean alone, 1 is rocq alone.
