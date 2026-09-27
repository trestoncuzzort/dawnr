# t cross-kernel agreement, 2026-09-27 06:55Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| humaneval_dafny_049_modp__modp | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_082_prime_length__prime_length | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| humaneval_dafny_134_check_if_last_char_is_a_letter__check_if_last_char_is_a_letter | verified / unproved | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_138_is_equal_to_sum_even__is_equal_to_sum_even | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0083__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0098__solve | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| vericoding_da0152__computeMinimalSteps | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0528__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0532__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0000__binarySearch | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_dd0048__computeAvg | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0061__find | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0067__linearSearch | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0112__mfirstMaximum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0113__mlastMaximum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0114__mmaximum1 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0132__binarySearch | verified / refuted | unproved / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_dd0151__findMax | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0340__binarySearch | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_dd0462__best_time_to_buy_and_sell_stock | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / unproved | timeout / unproved | timeout / refuted |
| vericoding_dd0520__find | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0521__findMax | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0535__isPrime | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dd0598__linearSearch | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0675__maxDifference | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0676__removeElements | verified / refuted | verified / refuted | malformed / malformed | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_dd0683__countNonEmptySubstrings | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0720__medianLength | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0735__containsConsecutiveNumbers | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0751__dissimilarElements | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| vericoding_dd0763__isPrime | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0795__isOddAtIndexOdd | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / timeout | unproved / refuted | verified / refuted |
| vericoding_dd0806__isProductEven | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / unproved | unproved / unproved | verified / refuted |
| vericoding_dh0029__is_prime | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | unproved / refuted |
| vericoding_dh0084__prime_length | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dh0136__check_if_last_char_is_a_letter | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_dj0023__myFun1 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0069__maxDifference | verified / unproved | verified / refuted | verified / refuted | verified / timeout | verified / refuted | timeout / refuted | verified / refuted |
| vericoding_dj0129__isProductEven | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted | verified / refuted |
| vericoding_dj0153__maxArray | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0154__maxDafnyLsp | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_ds0003__argmax | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0029__longestIncreasingStreak | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / unproved | unproved / refuted | verified / refuted |
| vericoding_dv0095__containsConsecutiveNumbers | vacuous / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / unproved | timeout / unproved | verified / refuted |
| vericoding_dv0108__isPrime | vacuous / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / unproved | verified / refuted |
| vericoding_dv0124__isOddAtIndexOdd | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / timeout | timeout / refuted | verified / refuted |
| vericoding_dv0142__find | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0148__linearSearch | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `humaneval_dafny_049_modp__modp.dfy` 8a2e7a4f387f37f6…, `humaneval_dafny_049_modp__modp.rs` eb457340ea8b1eb6…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| lean | 1 | 15 | vericoding_dh0136__check_if_last_char_is_a_letter |
| rocq | 1 | 16 | vericoding_dj0129__isProductEven |
| dafny | 0 | 4 | (none) |
| verus | 0 | 3 | (none) |
| spark | 0 | 1 | (none) |
| framac | 0 | 9 | (none) |
| fstar | 0 | 8 | (none) |

Of the 2 tasks in six, 1 is lean alone, 1 is rocq alone.
