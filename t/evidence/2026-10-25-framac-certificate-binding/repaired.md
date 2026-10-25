# t cross-kernel agreement, 2026-10-25 01:48Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | framac |
|---|---|
| abs | verified / refuted |
| all_nonneg | verified / refuted |
| all_pos_set | abstain / abstain |
| all_positive | abstain / abstain |
| any_neg_for | verified / refuted |
| average | abstain / abstain |
| bag_size | verified / refuted |
| by_second | abstain / abstain |
| cheapest | abstain / abstain |
| checked_tail | abstain / abstain |
| clamp | verified / refuted |
| clamp_all | verified / refuted |
| color_code | verified / refuted |
| contains | verified / refuted |
| count_evens_skip | abstain / abstain |
| count_matches | verified / refuted |
| count_pos_for | verified / refuted |
| count_vowels | abstain / abstain |
| cube | verified / refuted |
| deadband | verified / refuted |
| diffs | verified / refuted |
| digit_sum | verified / refuted |
| distance | verified / refuted |
| divmod_pair | verified / refuted |
| double_all | timeout / refuted |
| doubled | verified / refuted |
| doubled_head | verified / refuted |
| evens | abstain / abstain |
| every_other | verified / refuted |
| factorial | verified / refuted |
| fib | verified / refuted |
| filter_pos | verified / refuted |
| find_zero | verified / refuted |
| first_even | verified / refuted |
| first_sorted | abstain / abstain |
| floor_ceil | abstain / abstain |
| gcd | verified / refuted |
| gcd_of | verified / refuted |
| grid_row_sums | abstain / abstain |
| half_way | abstain / abstain |
| has_duplicate | verified / refuted |
| has_elem | verified / refuted |
| has_negative | abstain / abstain |
| index_map | abstain / abstain |
| index_of | verified / refuted |
| is_prime | verified / refuted |
| largest | verified / refuted |
| last_of | verified / refuted |
| last_pos | abstain / abstain |
| linear_search | verified / refuted |
| longest_row | abstain / abstain |
| lookup_or | abstain / abstain |
| manhattan | verified / refuted |
| max | verified / refuted |
| members_upto | abstain / abstain |
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
| rate_limit | verified / refuted |
| rect_area | verified / refuted |
| relu_all | verified / refuted |
| remainder | verified / refuted |
| rev_equal | verified / refuted |
| reverse | verified / refuted |
| reverse_in_place | abstain / abstain |
| ring_push | verified / refuted |
| root_floor | verified / refuted |
| row_max_len | verified / refuted |
| safe_ratio | abstain / abstain |
| sat_scale | verified / refuted |
| scale_all | verified / refuted |
| seq_max | verified / refuted |
| set_collect | abstain / abstain |
| set_first | verified / refuted |
| set_toggle | abstain / abstain |
| shape_area | verified / refuted |
| signs | abstain / abstain |
| some_negative | verified / refuted |
| sort3 | abstain / abstain |
| sort_it | abstain / abstain |
| split_join | abstain / abstain |
| squares | verified / refuted |
| strip_dots | abstain / abstain |
| sum_one | verified / refuted |
| sum_tail | abstain / abstain |
| sum_upto | verified / refuted |
| swap | verified / refuted |
| swap_at | verified / refuted |
| swap_ends | abstain / abstain |
| swap_prefix | abstain / abstain |
| swap_rows | abstain / abstain |
| tail | verified / refuted |
| tree_count | abstain / abstain |
| tree_height | abstain / abstain |
| tree_insert | abstain / abstain |
| tree_mirror | abstain / abstain |
| tree_sum | abstain / abstain |
| weighted_sum | abstain / abstain |
| word_count | verified / refuted |
| words_seen | abstain / abstain |
| zeros_for | verified / refuted |
| zip_pairs | abstain / abstain |

Kernels present: 1 of 1 (framac)

Backends:
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free

Verdict basis: every source file hashed.

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all one |
|---|---|---|---|
| framac | 0 | 0 | (none) |

Of the 0 tasks in zero, none are blocked alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| framac | 72 | 71 | 71 of 71 (100%) | 42 |

Verified with the twin refuted in all one columns: 71 of 114 tasks.
