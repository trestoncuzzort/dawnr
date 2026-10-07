# t cross-kernel agreement, 2026-10-07 01:37Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| abs | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| all_nonneg | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| all_positive | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | verified / refuted | verified / refuted | abstain / abstain |
| any_neg_for | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| average | verified / refuted | abstain / abstain | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| by_second | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| cheapest | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| clamp | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| color_code | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | verified / refuted | abstain / abstain | abstain / abstain |
| contains | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| count_evens_skip | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| count_matches | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| count_pos_for | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| count_vowels | verified / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | verified / refuted | timeout / refuted |
| cube | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| diffs | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| digit_sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| distance | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| divmod_pair | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| double_all | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted |
| doubled | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| evens | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | verified / refuted | abstain / abstain | abstain / abstain |
| every_other | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| factorial | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| fib | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| filter_pos | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| find_zero | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| first_even | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| first_sorted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | verified / refuted | verified / refuted | abstain / abstain |
| floor_ceil | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| gcd | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| gcd_of | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| grid_row_sums | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | verified / refuted | verified / refuted |
| half_way | verified / refuted | abstain / abstain | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| has_duplicate | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| has_elem | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| has_negative | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | verified / refuted | verified / refuted | abstain / abstain |
| index_map | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| index_of | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| is_prime | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| largest | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| last_of | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| last_pos | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| linear_search | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| longest_row | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | verified / refuted | abstain / abstain | abstain / abstain |
| lookup_or | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| members_upto | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| min_max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| odd_positions | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| pad_right_len | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| palindrome | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| probe_names_dafny | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| probe_names_framac | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| probe_names_fstar | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| probe_names_lean | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| probe_names_rocq | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| probe_names_spark | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| probe_names_upper | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| probe_names_verus | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| put_key | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| remainder | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| reverse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| root_floor | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| row_max_len | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| safe_ratio | verified / refuted | abstain / abstain | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| seq_max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| set_collect | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted | verified / refuted |
| set_toggle | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted | verified / refuted |
| signs | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| sort3 | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| sort_it | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | verified / refuted | verified / refuted | abstain / abstain |
| split_join | verified / refuted | verified / refuted | timeout / refuted | abstain / abstain | verified / refuted | verified / refuted | unproved / refuted |
| squares | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| strip_dots | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| sum_one | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| sum_tail | verified / refuted | verified / refuted | timeout / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| sum_upto | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| swap | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| swap_ends | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| swap_prefix | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| swap_rows | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| tail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| weighted_sum | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | verified / refuted | abstain / abstain | abstain / abstain |
| word_count | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| words_seen | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| zeros_for | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| zip_pairs | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `abs.dfy` 9fe1e7e805cfacce…, `abs.rs` 750a8322fb7abf25…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| framac | 3 | 36 | double_all, palindrome, swap_rows |
| lean | 1 | 26 | odd_positions |
| dafny | 0 | 0 | (none) |
| verus | 0 | 8 | (none) |
| spark | 0 | 32 | (none) |
| rocq | 0 | 26 | (none) |
| fstar | 0 | 29 | (none) |

Of the 4 tasks in six, 3 are framac alone, 1 is lean alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| dafny | 88 | 88 | 88 of 88 (100%) | 0 |
| verus | 81 | 80 | 80 of 80 (100%) | 7 |
| spark | 59 | 56 | 56 of 56 (100%) | 29 |
| framac | 50 | 49 | 49 of 49 (100%) | 38 |
| lean | 64 | 61 | 61 of 61 (100%) | 24 |
| rocq | 62 | 62 | 62 of 62 (100%) | 26 |
| fstar | 61 | 59 | 59 of 59 (100%) | 27 |

Verified with the twin refuted in all seven columns: 48 of 88 tasks.
