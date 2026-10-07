# Built and run: dafny-py

Each task's proven lowering, compiled with its own toolchain and run on up to 40 domain points; every result compared with t's interpreter (t/build.py).

- tasks: 114; built and run: 74; agree on every point: 74; agree on every point inside int32 and differ only beyond it: 0; disagree: 0; points run: 2881

| task | status | points | first disagreement |
|---|---|---|---|
| abs | agrees | 40 |  |
| all_nonneg | agrees | 40 |  |
| all_pos_set | not built: parameter type 'set' |  |  |
| all_positive | agrees | 40 |  |
| any_neg_for | agrees | 40 |  |
| average | not built: result type 'real' |  |  |
| bag_size | not built: parameter type {'datatype': 'Bag'} |  |  |
| by_second | not built: parameter type {'seq': {'pair': ['int', 'int']}} |  |  |
| cheapest | not built: parameter type {'seq': {'pair': ['int', 'int']}} |  |  |
| checked_tail | not built: result type {'datatype': 'Res'} |  |  |
| clamp | agrees | 40 |  |
| clamp_all | agrees | 40 |  |
| color_code | not built: parameter type {'datatype': 'Color'} |  |  |
| contains | agrees | 40 |  |
| count_evens_skip | agrees | 40 |  |
| count_matches | agrees | 40 |  |
| count_pos_for | agrees | 40 |  |
| count_vowels | agrees | 40 |  |
| cube | agrees | 40 |  |
| deadband | not built: parameter type 'float' |  |  |
| diffs | agrees | 40 |  |
| digit_sum | agrees | 40 |  |
| distance | agrees | 40 |  |
| divmod_pair | not built: result type {'pair': ['int', 'int']} |  |  |
| double_all | agrees | 40 |  |
| doubled | agrees | 40 |  |
| doubled_head | agrees | 40 |  |
| evens | agrees | 40 |  |
| every_other | agrees | 40 |  |
| factorial | agrees | 40 |  |
| fib | agrees | 17 |  |
| filter_pos | agrees | 40 |  |
| find_zero | agrees | 40 |  |
| first_even | agrees | 40 |  |
| first_sorted | agrees | 40 |  |
| floor_ceil | not built: parameter type 'real' |  |  |
| gcd | agrees | 40 |  |
| gcd_of | agrees | 40 |  |
| grid_row_sums | not built: parameter type {'seq': 'seq'} |  |  |
| half_way | not built: parameter type 'real' |  |  |
| has_duplicate | agrees | 40 |  |
| has_elem | agrees | 40 |  |
| has_negative | agrees | 40 |  |
| index_map | not built: result type {'map': ['int', 'int']} |  |  |
| index_of | agrees | 40 |  |
| is_prime | agrees | 40 |  |
| largest | agrees | 40 |  |
| last_of | agrees | 40 |  |
| last_pos | agrees | 40 |  |
| linear_search | agrees | 40 |  |
| longest_row | not built: parameter type {'seq': 'seq'} |  |  |
| lookup_or | not built: parameter type {'map': ['int', 'int']} |  |  |
| manhattan | not built: parameter type {'datatype': 'Point'} |  |  |
| max | agrees | 40 |  |
| members_upto | not built: result type 'set' |  |  |
| min_max | not built: result type {'pair': ['int', 'int']} |  |  |
| none_neg | agrees | 40 |  |
| odd_positions | agrees | 40 |  |
| offset_all | agrees | 40 |  |
| pad_right_len | agrees | 40 |  |
| palindrome | agrees | 40 |  |
| probe_names_dafny | agrees | 40 |  |
| probe_names_framac | agrees | 40 |  |
| probe_names_fstar | agrees | 40 |  |
| probe_names_lean | agrees | 40 |  |
| probe_names_rocq | agrees | 40 |  |
| probe_names_spark | agrees | 40 |  |
| probe_names_upper | agrees | 40 |  |
| probe_names_verus | agrees | 40 |  |
| put_key | not built: parameter type {'map': ['int', 'int']} |  |  |
| rate_limit | not built: parameter type 'float' |  |  |
| rect_area | not built: parameter type {'datatype': 'Shape'} |  |  |
| relu_all | agrees | 40 |  |
| remainder | agrees | 40 |  |
| rev_equal | agrees | 40 |  |
| reverse | agrees | 40 |  |
| reverse_in_place | agrees | 40 |  |
| ring_push | agrees | 40 |  |
| root_floor | error: RuntimeError: dafny run: RecursionError: maximum recursion depth exceeded |  |  |
| row_max_len | not built: parameter type {'seq': 'seq'} |  |  |
| safe_ratio | not built: parameter type 'real' |  |  |
| sat_scale | not built: parameter type 'float' |  |  |
| scale_all | agrees | 40 |  |
| seq_max | agrees | 40 |  |
| set_collect | not built: result type 'set' |  |  |
| set_first | agrees | 40 |  |
| set_toggle | not built: parameter type 'set' |  |  |
| shape_area | not built: parameter type {'datatype': 'Shape'} |  |  |
| signs | not built: result type {'seq': 'bool'} |  |  |
| some_negative | not built: result type {'datatype': 'Opt'} |  |  |
| sort3 | not built: result type {'tuple': ['int', 'int', 'int']} |  |  |
| sort_it | agrees | 40 |  |
| split_join | agrees | 40 |  |
| squares | agrees | 40 |  |
| strip_dots | agrees | 40 |  |
| sum_one | agrees | 40 |  |
| sum_tail | agrees | 40 |  |
| sum_upto | agrees | 40 |  |
| swap | agrees | 12 |  |
| swap_at | agrees | 12 |  |
| swap_ends | not built: parameter type {'pair': [{'pair': ['int', 'int']}, {'pair': ['int', 'int']}]} |  |  |
| swap_prefix | agrees | 40 |  |
| swap_rows | not built: parameter type {'seq': 'seq'} |  |  |
| tail | agrees | 40 |  |
| tree_count | not built: parameter type {'datatype': 'Tree'} |  |  |
| tree_height | not built: parameter type {'datatype': 'Tree'} |  |  |
| tree_insert | not built: parameter type {'datatype': 'Tree'} |  |  |
| tree_mirror | not built: parameter type {'datatype': 'Tree'} |  |  |
| tree_sum | not built: parameter type {'datatype': 'Tree'} |  |  |
| weighted_sum | agrees | 40 |  |
| word_count | agrees | 40 |  |
| words_seen | not built: result type {'set': 'seq'} |  |  |
| zeros_for | agrees | 40 |  |
| zip_pairs | not built: result type {'seq': {'pair': ['int', 'int']}} |  |  |
