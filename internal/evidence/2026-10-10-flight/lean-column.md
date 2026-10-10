# t cross-kernel agreement, 2026-10-10 14:55Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | lean |
|---|---|
| abs | verified / refuted |
| all_nonneg | verified / refuted |
| all_pos_set | verified / refuted |
| all_positive | verified / refuted |
| any_neg_for | verified / refuted |
| average | abstain / abstain |
| bag_size | verified / refuted |
| by_second | abstain / abstain |
| cheapest | abstain / abstain |
| checked_tail | verified / refuted |
| clamp | verified / refuted |
| clamp_all | verified / refuted |
| color_code | verified / refuted |
| contains | verified / refuted |
| count_evens_skip | verified / refuted |
| count_matches | verified / refuted |
| count_pos_for | verified / refuted |
| count_vowels | unproved / unproved |
| cube | verified / refuted |
| deadband | abstain / abstain |
| diffs | verified / refuted |
| digit_sum | verified / refuted |
| distance | verified / refuted |
| divmod_pair | verified / refuted |
| double_all | verified / refuted |
| doubled | verified / refuted |
| doubled_head | verified / refuted |
| evens | verified / refuted |
| every_other | verified / refuted |
| factorial | verified / refuted |
| fib | verified / refuted |
| filter_pos | verified / refuted |
| find_zero | verified / refuted |
| first_even | verified / refuted |
| first_sorted | verified / refuted |
| floor_ceil | abstain / abstain |
| gcd | verified / refuted |
| gcd_of | verified / refuted |
| grid_row_sums | verified / refuted |
| half_way | abstain / abstain |
| has_duplicate | verified / refuted |
| has_elem | verified / refuted |
| has_negative | verified / refuted |
| index_map | abstain / abstain |
| index_of | verified / refuted |
| is_prime | verified / refuted |
| largest | verified / refuted |
| last_of | verified / refuted |
| last_pos | abstain / abstain |
| linear_search | verified / refuted |
| longest_row | verified / refuted |
| lookup_or | abstain / abstain |
| manhattan | verified / refuted |
| max | verified / refuted |
| members_upto | unproved / refuted |
| min_max | verified / refuted |
| none_neg | verified / refuted |
| odd_positions | verified / refuted |
| offset_all | verified / refuted |
| pad_right_len | abstain / abstain |
| palindrome | verified / refuted |
| probe_names_dafny | verified / refuted |
| probe_names_framac | verified / refuted |
| probe_names_fstar | verified / refuted |
| probe_names_lean | verified / refuted |
| probe_names_rocq | verified / refuted |
| probe_names_spark | verified / refuted |
| probe_names_upper | verified / refuted |
| probe_names_verus | verified / refuted |
| put_key | abstain / abstain |
| rate_limit | abstain / abstain |
| rect_area | verified / refuted |
| relu_all | verified / refuted |
| remainder | verified / refuted |
| rev_equal | verified / refuted |
| reverse | verified / refuted |
| reverse_in_place | unproved / refuted |
| ring_push | unproved / refuted |
| root_floor | verified / refuted |
| row_max_len | verified / refuted |
| safe_ratio | abstain / abstain |
| sat_scale | abstain / abstain |
| scale_all | verified / refuted |
| seq_max | verified / refuted |
| set_collect | verified / refuted |
| set_first | verified / refuted |
| set_toggle | verified / refuted |
| shape_area | verified / refuted |
| signs | abstain / abstain |
| some_negative | verified / refuted |
| sort3 | abstain / abstain |
| sort_it | verified / refuted |
| split_join | verified / refuted |
| squares | verified / refuted |
| strip_dots | abstain / abstain |
| sum_one | verified / refuted |
| sum_tail | verified / refuted |
| sum_upto | verified / refuted |
| swap | verified / refuted |
| swap_at | verified / refuted |
| swap_ends | abstain / abstain |
| swap_prefix | abstain / abstain |
| swap_rows | verified / refuted |
| tail | verified / refuted |
| tree_count | verified / refuted |
| tree_height | verified / refuted |
| tree_insert | verified / refuted |
| tree_mirror | verified / refuted |
| tree_sum | verified / refuted |
| weighted_sum | verified / refuted |
| word_count | verified / refuted |
| words_seen | abstain / abstain |
| zeros_for | verified / refuted |
| zip_pairs | abstain / abstain |

Kernels present: 1 of 1 (lean)

Backends:
- lean: Lean (version 4.33.1

Verdict basis: every source file hashed.

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all one |
|---|---|---|---|
| lean | 25 | 0 | average, by_second, cheapest, count_vowels, deadband, floor_ceil, half_way, index_map, last_pos, lookup_or, members_upto, pad_right_len, put_key, rate_limit, reverse_in_place, ring_push, safe_ratio, sat_scale, signs, sort3, strip_dots, swap_ends, swap_prefix, words_seen, zip_pairs |

Of the 25 tasks in zero, 25 are lean alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| lean | 93 | 89 | 89 of 89 (100%) | 21 |

Verified with the twin refuted in all one columns: 89 of 114 tasks.
