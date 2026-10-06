# t cross-kernel agreement, 2026-10-06 23:48Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| ac_automata_search | verified / refuted | unproved / unproved | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| binary_search | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| bracket_match | verified / refuted | verified / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| bubble_sort | verified / refuted | unproved / refuted | abstain / abstain | abstain / abstain | unproved / unproved | abstain / abstain | malformed / malformed |
| fast_exponential | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| insertion_sort | verified / refuted | unproved / refuted | abstain / abstain | abstain / abstain | unproved / unproved | abstain / abstain | malformed / malformed |
| integer_exponential | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| kmp | verified / refuted | malformed / malformed | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| linear_search | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| solve_longest_common_subsequence | verified / refuted | unproved / refuted | malformed / malformed | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| longest_palindromic_substring | verified / refuted | unproved / unproved | timeout / timeout | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| matrix_multiply | verified / refuted | malformed / malformed | abstain / abstain | abstain / abstain | timeout / timeout | abstain / abstain | abstain / abstain |
| max_subarray_sum | verified / refuted | verified / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | timeout / timeout |
| merge_sort | verified / refuted | malformed / malformed | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| poly_multiply_karatsuba | verified / refuted | unproved / refuted | timeout / timeout | abstain / abstain | abstain / abstain | abstain / abstain | timeout / timeout |
| poly_multiply_naive | verified / refuted | malformed / malformed | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | timeout / timeout |
| quick_sort | verified / refuted | malformed / malformed | abstain / abstain | abstain / abstain | unproved / unproved | abstain / abstain | abstain / abstain |
| sieve_method | verified / refuted | unproved / unproved | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| string_search_naive | verified / refuted | unproved / unproved | malformed / malformed | abstain / abstain | timeout / timeout | abstain / abstain | verified / refuted |
| trial_division_naive | verified / refuted | verified / unproved | timeout / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| trial_division_optimized | verified / refuted | unproved / unproved | timeout / refuted | abstain / abstain | unproved / unproved | abstain / abstain | timeout / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `ac_automata_search.dfy` fd9ce0518f00e91e…, `ac_automata_search.rs` 19aaaf4253df518b…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| lean | 1 | 20 | integer_exponential |
| dafny | 0 | 0 | (none) |
| verus | 0 | 16 | (none) |
| spark | 0 | 18 | (none) |
| framac | 0 | 19 | (none) |
| rocq | 0 | 20 | (none) |
| fstar | 0 | 18 | (none) |

Of the 1 tasks in six, 1 is lean alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| dafny | 21 | 21 | 21 of 21 (100%) | 0 |
| verus | 21 | 6 | 5 of 6 (83%) | 0 |
| spark | 14 | 3 | 3 of 3 (100%) | 7 |
| framac | 2 | 2 | 2 of 2 (100%) | 19 |
| lean | 10 | 0 | 0 of 0 | 11 |
| rocq | 3 | 1 | 1 of 1 (100%) | 18 |
| fstar | 16 | 3 | 3 of 3 (100%) | 5 |

Verified with the twin refuted in all seven columns: 0 of 21 tasks.
