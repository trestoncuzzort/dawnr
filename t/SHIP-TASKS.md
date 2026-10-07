# Shipped at machine width

Each routine's C lowering proved with WP's machine-integer model and `-wp-rte`, so every signed operation owes a no-overflow proof (t/ship.py). Where an overflow guard is open for the full range, the largest bound ±2^k on every int input and sequence element (lengths at most 1000) under which every goal proves is the routine's proved operating envelope.

- ships for every int32 input: 47
- ships within an envelope: 7
- no envelope found: 17
- contract open at machine width: 1
- not shipped (the C lowering refuses it): 42

| task | status | goals at full width (before inference) | bounds inferred and proved (R4c) | open goals at full width |
|---|---|---|---|---|
| abs | ships within ±2^30 | 6/7 |  | typed_abs_t_assert_rte_signed_overflow |
| all_nonneg | ships for every int32 input | 15/15 |  |  |
| all_pos_set | not shipped: the C lowering refuses it |  |  |  |
| all_positive | not shipped: the C lowering refuses it |  |  |  |
| any_neg_for | ships for every int32 input | 20/20 |  |  |
| average | not shipped: the C lowering refuses it |  |  |  |
| bag_size | ships for every int32 input | 6/6 |  |  |
| by_second | not shipped: the C lowering refuses it |  |  |  |
| cheapest | not shipped: the C lowering refuses it |  |  |  |
| checked_tail | not shipped: the C lowering refuses it |  |  |  |
| clamp | ships for every int32 input | 10/10 |  |  |
| clamp_all | ships for every int32 input | 34/34 |  |  |
| color_code | ships for every int32 input | 11/11 |  |  |
| contains | ships for every int32 input | 15/15 |  |  |
| count_evens_skip | not shipped: the C lowering refuses it |  |  |  |
| count_matches | ships for every int32 input | 16/17 | 0 <= i; 0 <= r; i <= s_n; r <= i; r <= s_n | typed_count_matches_t_assert_rte_signed_overflow |
| count_pos_for | ships for every int32 input | 18/19 | 0 <= c; 0 <= i; c <= i; c <= s_n; i <= s_n | typed_count_pos_for_t_assert_rte_signed_overflow |
| count_vowels | not shipped: the C lowering refuses it |  |  |  |
| cube | no envelope found (open even at ±2^4) | 17/23 |  | typed_cube_t_assert_rte_signed_overflow_2, typed_cube_t_assert_rte_signed_overflow_3, typed_cube_t_assert_rte_signed_overflow_4, typed_cube_t_ensures, typed_t_pow_c_assert_rte_signed_overflow, typed_t_pow_c_assert_rte_signed_overflow_2 |
| deadband | ships for every int32 input | 9/9 |  |  |
| diffs | no envelope found (open even at ±2^4) | 22/24 |  | typed_diffs_t_assert_rte_signed_overflow_2, typed_diffs_t_assert_rte_signed_overflow_3 |
| digit_sum | no envelope found (open even at ±2^4) | 24/25 | 0 <= m; 0 <= r; m <= n | typed_digit_sum_t_assert_rte_signed_overflow_6 |
| distance | ships within ±2^29 | 10/13 |  | typed_distance_t_assert_rte_signed_overflow, typed_distance_t_assert_rte_signed_overflow_2, typed_distance_t_assert_rte_signed_overflow_5 |
| divmod_pair | ships for every int32 input | 33/33 |  |  |
| double_all | no envelope found (open even at ±2^4) | 31/34 |  | typed_double_all_t_assert_rte_signed_overflow, typed_double_all_t_assert_rte_signed_overflow_2, typed_double_all_t_loop_invariant_preserved |
| doubled | no envelope found (open even at ±2^4) | 19/21 |  | typed_doubled_t_assert_rte_signed_overflow, typed_doubled_t_assert_rte_signed_overflow_2 |
| doubled_head | ships within ±2^29 | 21/23 |  | typed_doubled_head_t_assert_rte_signed_overflow, typed_doubled_head_t_assert_rte_signed_overflow_2 |
| evens | not shipped: the C lowering refuses it |  |  |  |
| every_other | ships for every int32 input | 28/28 |  |  |
| factorial | no envelope found (open even at ±2^4) | 12/14 |  | typed_factorial_t_assert_rte_signed_overflow_2, typed_factorial_t_assert_rte_signed_overflow_3 |
| fib | no envelope found (open even at ±2^4) | 19/21 |  | typed_fib_t_assert_rte_signed_overflow_3, typed_fib_t_assert_rte_signed_overflow_4 |
| filter_pos | not shipped: the contract is open at machine width | 36/37 |  | typed_filter_pos_t_loop_invariant_3_preserved |
| find_zero | ships for every int32 input | 20/20 |  |  |
| first_even | ships for every int32 input | 27/27 |  |  |
| first_sorted | not shipped: the C lowering refuses it |  |  |  |
| floor_ceil | not shipped: the C lowering refuses it |  |  |  |
| gcd | ships for every int32 input | 22/22 |  |  |
| gcd_of | no envelope found (open even at ±2^4) | 27/29 |  | typed_t_gcd_c_assert_rte_signed_overflow, typed_t_gcd_c_assert_rte_signed_overflow_2 |
| grid_row_sums | not shipped: the C lowering refuses it |  |  |  |
| half_way | not shipped: the C lowering refuses it |  |  |  |
| has_duplicate | ships for every int32 input | 34/34 |  |  |
| has_elem | ships for every int32 input | 27/27 |  |  |
| has_negative | not shipped: the C lowering refuses it |  |  |  |
| index_map | not shipped: the C lowering refuses it |  |  |  |
| index_of | ships for every int32 input | 20/20 |  |  |
| is_prime | ships for every int32 input | 31/31 |  |  |
| largest | ships for every int32 input | 70/70 |  |  |
| last_of | ships for every int32 input | 7/7 |  |  |
| last_pos | not shipped: the C lowering refuses it |  |  |  |
| linear_search | ships for every int32 input | 19/19 |  |  |
| longest_row | not shipped: the C lowering refuses it |  |  |  |
| lookup_or | not shipped: the C lowering refuses it |  |  |  |
| manhattan | no envelope found (open even at ±2^4) | 18/25 |  | typed_manhattan_t_assert_rte_signed_overflow, typed_manhattan_t_assert_rte_signed_overflow_12, typed_manhattan_t_assert_rte_signed_overflow_16, typed_manhattan_t_assert_rte_signed_overflow_2, typed_manhattan_t_assert_rte_signed_overflow_5, typed_manhattan_t_assert_rte_signed_overflow_8 |
| max | ships for every int32 input | 7/7 |  |  |
| members_upto | not shipped: the C lowering refuses it |  |  |  |
| min_max | ships for every int32 input | 36/36 |  |  |
| none_neg | ships for every int32 input | 15/15 |  |  |
| odd_positions | ships for every int32 input | 29/29 |  |  |
| offset_all | ships within ±2^29 | 29/31 |  | typed_offset_all_t_assert_rte_signed_overflow, typed_offset_all_t_assert_rte_signed_overflow_2 |
| pad_right_len | not shipped: the C lowering refuses it |  |  |  |
| palindrome | ships for every int32 input | 37/37 |  |  |
| probe_names_dafny | ships for every int32 input | 7/7 |  |  |
| probe_names_framac | ships for every int32 input | 7/7 |  |  |
| probe_names_fstar | ships for every int32 input | 7/7 |  |  |
| probe_names_lean | ships for every int32 input | 7/7 |  |  |
| probe_names_rocq | ships for every int32 input | 7/7 |  |  |
| probe_names_spark | ships for every int32 input | 7/7 |  |  |
| probe_names_upper | ships for every int32 input | 7/7 |  |  |
| probe_names_verus | ships for every int32 input | 7/7 |  |  |
| put_key | not shipped: the C lowering refuses it |  |  |  |
| rate_limit | ships for every int32 input | 17/17 |  |  |
| rect_area | no envelope found (open even at ±2^4) | 6/8 |  | typed_rect_area_t_assert_rte_signed_overflow, typed_rect_area_t_assert_rte_signed_overflow_2 |
| relu_all | ships for every int32 input | 28/28 |  |  |
| remainder | no envelope found (open even at ±2^4) | 18/21 |  | typed_remainder_t_assert_rte_signed_overflow, typed_remainder_t_assert_rte_signed_overflow_7, typed_remainder_t_ensures_2 |
| rev_equal | ships for every int32 input | 37/37 |  |  |
| reverse | ships for every int32 input | 38/38 |  |  |
| reverse_in_place | not shipped: the C lowering refuses it |  |  |  |
| ring_push | ships for every int32 input | 28/28 |  |  |
| root_floor | no envelope found (open even at ±2^4) | 29/30 |  | typed_t_isqrt_c_assert_rte_signed_overflow_5 |
| row_max_len | no envelope found (open even at ±2^4) | 32/33 | 0 <= i; 0 <= r | typed_row_max_len_t_assert_rte_signed_overflow_5 |
| safe_ratio | not shipped: the C lowering refuses it |  |  |  |
| sat_scale | ships for every int32 input | 11/11 |  |  |
| scale_all | ships within ±2^15 | 27/29 |  | typed_scale_all_t_assert_rte_signed_overflow, typed_scale_all_t_assert_rte_signed_overflow_2 |
| seq_max | ships for every int32 input | 22/22 |  |  |
| set_collect | not shipped: the C lowering refuses it |  |  |  |
| set_first | ships within ±2^29 | 24/26 |  | typed_set_first_t_assert_rte_signed_overflow_2, typed_set_first_t_assert_rte_signed_overflow_3 |
| set_toggle | not shipped: the C lowering refuses it |  |  |  |
| shape_area | no envelope found (open even at ±2^4) | 11/14 |  | typed_shape_area_t_assert_rte_signed_overflow_2, typed_shape_area_t_assert_rte_signed_overflow_4, typed_shape_area_t_assert_rte_signed_overflow_6 |
| signs | not shipped: the C lowering refuses it |  |  |  |
| some_negative | ships for every int32 input | 33/33 |  |  |
| sort3 | not shipped: the C lowering refuses it |  |  |  |
| sort_it | not shipped: the C lowering refuses it |  |  |  |
| split_join | not shipped: the C lowering refuses it |  |  |  |
| squares | no envelope found (open even at ±2^4) | 18/19 |  | typed_squares_t_assert_rte_signed_overflow_2 |
| strip_dots | not shipped: the C lowering refuses it |  |  |  |
| sum_one | no envelope found (open even at ±2^4) | 18/20 |  | typed_t_sum_c_assert_rte_signed_overflow, typed_t_sum_c_assert_rte_signed_overflow_2 |
| sum_tail | not shipped: the C lowering refuses it |  |  |  |
| sum_upto | ships within ±2^15 | 14/15 | -(i * 32768) <= r; -(n * 32768) <= i; -(n * 32768) <= r; -(r * 32768) <= i; 0 <= i; 0 <= r; i <= n; i <= n * 32768; i <= r; i <= r * 32768; r <= i * 32768; r <= n * 32768 | typed_sum_upto_t_assert_rte_signed_overflow_3 |
| swap | ships for every int32 input | 29/29 |  |  |
| swap_at | ships for every int32 input | 17/17 |  |  |
| swap_ends | not shipped: the C lowering refuses it |  |  |  |
| swap_prefix | not shipped: the C lowering refuses it |  |  |  |
| swap_rows | not shipped: the C lowering refuses it |  |  |  |
| tail | ships for every int32 input | 19/19 |  |  |
| tree_count | not shipped: the C lowering refuses it |  |  |  |
| tree_height | not shipped: the C lowering refuses it |  |  |  |
| tree_insert | not shipped: the C lowering refuses it |  |  |  |
| tree_mirror | not shipped: the C lowering refuses it |  |  |  |
| tree_sum | not shipped: the C lowering refuses it |  |  |  |
| weighted_sum | not shipped: the C lowering refuses it |  |  |  |
| word_count | no envelope found (open even at ±2^4) | 73/75 |  | typed_t_wc_c_assert_rte_signed_overflow_11, typed_t_wc_c_loop_invariant_2_preserved |
| words_seen | not shipped: the C lowering refuses it |  |  |  |
| zeros_for | ships for every int32 input | 25/25 |  |  |
| zip_pairs | not shipped: the C lowering refuses it |  |  |  |
