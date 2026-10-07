# Specification audit

Every one-edit mutant of each body, classed by the interpreter over the task's bounded domain (t/audit.py): **killed** (the spec rejects its result somewhere), **same** (computes the same everywhere), **diverges** (runs out of steps where the real body ends), **survivor** (computes something different, and the spec accepts it everywhere).

- tasks: 114; audited: 114; not audited: none
- behaviour-changing mutants the specs kill: 1568 of 1570 (99.9%)
- tasks whose spec admits a survivor: 1 of 114
- dafny: real body verified in 111 of 114; of those, a survivor proved too (a wrong program with a proof) in 1

| task | mutants | killed | same | diverges | survivors | proved by the kernel | a survivor: change at input |
|---|---|---|---|---|---|---|---|
| abs | 10 | 8 | 2 | 0 | 0 | 0 |  |
| all_nonneg | 20 | 18 | 0 | 2 | 0 | 0 |  |
| all_pos_set | 4 | 4 | 0 | 0 | 0 | 0 |  |
| all_positive | 4 | 4 | 0 | 0 | 0 | 0 |  |
| any_neg_for | 22 | 19 | 0 | 3 | 0 | 0 |  |
| average | 2 | 2 | 0 | 0 | 0 | 0 |  |
| bag_size | 8 | 8 | 0 | 0 | 0 | 0 |  |
| by_second | 1 | 1 | 0 | 0 | 0 | 0 |  |
| cheapest | 2 | 2 | 0 | 0 | 0 | 0 |  |
| checked_tail | 12 | 12 | 0 | 0 | 0 | 0 |  |
| clamp | 10 | 10 | 0 | 0 | 0 | 0 |  |
| clamp_all | 34 | 29 | 1 | 4 | 0 | 0 |  |
| color_code | 9 | 9 | 0 | 0 | 0 | 0 |  |
| contains | 20 | 17 | 0 | 3 | 0 | 0 |  |
| count_evens_skip | 36 | 31 | 0 | 5 | 0 | 0 |  |
| count_matches | 28 | 25 | 0 | 3 | 0 | 0 |  |
| count_pos_for | 39 | 35 | 0 | 4 | 0 | 0 |  |
| count_vowels | 42 | 38 | 2 | 2 | 0 | 0 |  |
| cube | 6 | 6 | 0 | 0 | 0 | 0 |  |
| deadband | 9 | 9 | 0 | 0 | 0 | (real abstain) |  |
| diffs | 16 | 16 | 0 | 0 | 0 | 0 |  |
| digit_sum | 25 | 18 | 0 | 7 | 0 | 0 |  |
| distance | 6 | 6 | 0 | 0 | 0 | 0 |  |
| divmod_pair | 7 | 7 | 0 | 0 | 0 | 0 |  |
| double_all | 18 | 16 | 0 | 2 | 0 | 0 |  |
| doubled | 4 | 4 | 0 | 0 | 0 | 0 |  |
| doubled_head | 9 | 9 | 0 | 0 | 0 | 0 |  |
| evens | 6 | 6 | 0 | 0 | 0 | 0 |  |
| every_other | 27 | 27 | 0 | 0 | 0 | 0 |  |
| factorial | 16 | 11 | 0 | 5 | 0 | 0 |  |
| fib | 24 | 14 | 0 | 10 | 0 | 0 |  |
| filter_pos | 22 | 20 | 0 | 2 | 0 | 0 |  |
| find_zero | 18 | 16 | 0 | 2 | 0 | 0 |  |
| first_even | 27 | 25 | 0 | 2 | 0 | 0 |  |
| first_sorted | 4 | 4 | 0 | 0 | 0 | 0 |  |
| floor_ceil | 1 | 1 | 0 | 0 | 0 | 0 |  |
| gcd | 41 | 20 | 6 | 15 | 0 | 0 |  |
| gcd_of | 4 | 4 | 0 | 0 | 0 | 0 |  |
| grid_row_sums | 16 | 14 | 0 | 2 | 0 | 0 |  |
| half_way | 6 | 6 | 0 | 0 | 0 | 0 |  |
| has_duplicate | 39 | 28 | 5 | 6 | 0 | 0 |  |
| has_elem | 10 | 10 | 0 | 0 | 0 | 0 |  |
| has_negative | 4 | 4 | 0 | 0 | 0 | 0 |  |
| index_map | 19 | 16 | 0 | 3 | 0 | 0 |  |
| index_of | 23 | 21 | 0 | 2 | 0 | 0 |  |
| is_prime | 22 | 17 | 1 | 4 | 0 | 0 |  |
| largest | 3 | 3 | 0 | 0 | 0 | 0 |  |
| last_of | 6 | 6 | 0 | 0 | 0 | 0 |  |
| last_pos | 2 | 2 | 0 | 0 | 0 | 0 |  |
| linear_search | 31 | 28 | 0 | 3 | 0 | 0 |  |
| longest_row | 1 | 1 | 0 | 0 | 0 | 0 |  |
| lookup_or | 5 | 5 | 0 | 0 | 0 | 0 |  |
| manhattan | 10 | 10 | 0 | 0 | 0 | 0 |  |
| max | 12 | 11 | 1 | 0 | 0 | 0 |  |
| members_upto | 6 | 6 | 0 | 0 | 0 | 0 |  |
| min_max | 57 | 49 | 4 | 4 | 0 | 0 |  |
| none_neg | 20 | 18 | 0 | 2 | 0 | 0 |  |
| odd_positions | 27 | 27 | 0 | 0 | 0 | 0 |  |
| offset_all | 11 | 10 | 1 | 0 | 0 | 0 |  |
| pad_right_len | 2 | 2 | 0 | 0 | 0 | 0 |  |
| palindrome | 2 | 2 | 0 | 0 | 0 | 0 |  |
| probe_names_dafny | 19 | 16 | 3 | 0 | 0 | 0 |  |
| probe_names_framac | 19 | 16 | 3 | 0 | 0 | 0 |  |
| probe_names_fstar | 19 | 16 | 3 | 0 | 0 | 0 |  |
| probe_names_lean | 19 | 16 | 3 | 0 | 0 | 0 |  |
| probe_names_rocq | 19 | 16 | 3 | 0 | 0 | 0 |  |
| probe_names_spark | 19 | 16 | 3 | 0 | 0 | 0 |  |
| probe_names_upper | 19 | 16 | 3 | 0 | 0 | 0 |  |
| probe_names_verus | 19 | 16 | 3 | 0 | 0 | 0 |  |
| put_key | 4 | 4 | 0 | 0 | 0 | 0 |  |
| rate_limit | 34 | 32 | 2 | 0 | 0 | (real abstain) |  |
| rect_area | 4 | 4 | 0 | 0 | 0 | 0 |  |
| relu_all | 13 | 11 | 2 | 0 | 0 | 0 |  |
| remainder | 5 | 5 | 0 | 0 | 0 | 0 |  |
| rev_equal | 5 | 5 | 0 | 0 | 0 | 0 |  |
| reverse | 26 | 22 | 2 | 2 | 0 | 0 |  |
| reverse_in_place | 44 | 42 | 0 | 2 | 0 | 0 |  |
| ring_push | 14 | 9 | 5 | 0 | 0 | 0 |  |
| root_floor | 2 | 2 | 0 | 0 | 0 | 0 |  |
| row_max_len | 28 | 23 | 3 | 2 | 0 | 0 |  |
| safe_ratio | 13 | 13 | 0 | 0 | 0 | 0 |  |
| sat_scale | 35 | 33 | 2 | 0 | 0 | (real abstain) |  |
| scale_all | 7 | 7 | 0 | 0 | 0 | 0 |  |
| seq_max | 24 | 19 | 3 | 2 | 0 | 0 |  |
| set_collect | 14 | 12 | 0 | 2 | 0 | 0 |  |
| set_first | 14 | 13 | 1 | 0 | 0 | 0 |  |
| set_toggle | 2 | 2 | 0 | 0 | 0 | 0 |  |
| shape_area | 12 | 12 | 0 | 0 | 0 | 0 |  |
| signs | 18 | 16 | 0 | 2 | 0 | 0 |  |
| some_negative | 22 | 20 | 0 | 2 | 0 | 0 |  |
| sort3 | 154 | 139 | 15 | 0 | 0 | 0 |  |
| sort_it | 1 | 1 | 0 | 0 | 0 | 0 |  |
| split_join | 3 | 2 | 1 | 0 | 0 | 0 |  |
| squares | 4 | 4 | 0 | 0 | 0 | 0 |  |
| strip_dots | 2 | 2 | 0 | 0 | 0 | 0 |  |
| sum_one | 2 | 2 | 0 | 0 | 0 | 0 |  |
| sum_tail | 2 | 2 | 0 | 0 | 0 | 0 |  |
| sum_upto | 22 | 17 | 2 | 3 | 0 | 0 |  |
| swap | 17 | 13 | 4 | 0 | 0 | 0 |  |
| swap_at | 19 | 15 | 4 | 0 | 0 | 0 |  |
| swap_ends | 3 | 3 | 0 | 0 | 0 | 0 |  |
| swap_prefix | 6 | 6 | 0 | 0 | 0 | 0 |  |
| swap_rows | 12 | 12 | 0 | 0 | 0 | 0 |  |
| tail | 6 | 6 | 0 | 0 | 0 | 0 |  |
| tree_count | 8 | 8 | 0 | 0 | 0 | 0 |  |
| tree_height | 9 | 9 | 0 | 0 | 0 | 0 |  |
| tree_insert | 6 | 4 | 0 | 0 | 2 | 1 | compare-flip: `m := case tr { Leaf => Tree.Node(x, Tree.Leaf, Tree.Leaf), Node(v, l, r) => if x < v then Tree.Node(v, tree_insert(l, x), r) else Tree.Node(v, l, tree_insert(r, x)) };` -> `m := case tr { Leaf => Tree.Node(x, Tree.Leaf, Tree.Leaf), Node(v, l, r) => if x <= v then Tree.Node(v, tree_insert(l, x), r) else Tree.Node(v, l, tree_insert(r, x)) };` at tr=Tree.Node(0, Tree.Leaf, Tree.Leaf), x=0 -> real Tree.Node(0, Tree.Leaf, Tree.Node(0, Tree.Leaf, Tree.Leaf)), twin Tree.Node(0, Tree.Node(0, Tree.Leaf, Tree.Leaf), Tree.Leaf) |
| tree_mirror | 2 | 2 | 0 | 0 | 0 | 0 |  |
| tree_sum | 4 | 4 | 0 | 0 | 0 | 0 |  |
| weighted_sum | 30 | 26 | 0 | 4 | 0 | 0 |  |
| word_count | 9 | 8 | 1 | 0 | 0 | 0 |  |
| words_seen | 14 | 11 | 1 | 2 | 0 | 0 |  |
| zeros_for | 17 | 14 | 0 | 3 | 0 | 0 |  |
| zip_pairs | 20 | 17 | 1 | 2 | 0 | 0 |  |
