# Built and run: c64

Each task's proven lowering, compiled with its own toolchain and run on up to 40 domain points; every result compared with t's interpreter (t/build.py).

- tasks: 114; built and run: 56; agree on every point: 54; agree on every point inside int32 and differ only beyond it: 2; disagree: 0; points run: 2189

| task | status | points | first disagreement |
|---|---|---|---|
| abs | agrees | 40 |  |
| all_nonneg | agrees | 40 |  |
| all_pos_set | not built: parameter type 'set' |  |  |
| all_positive | not built: the lowering refuses it |  |  |
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
| count_evens_skip | not built: the lowering refuses it |  |  |
| count_matches | agrees | 40 |  |
| count_pos_for | agrees | 40 |  |
| count_vowels | not built: the lowering refuses it |  |  |
| cube | agrees within int32 | 40 | {"input": {"x": -2147483649}, "expected": "-9903520328118100260917608449", "got": "4611686011984936959"} |
| deadband | agrees | 40 |  |
| diffs | not built: no C function in the lowering |  |  |
| digit_sum | agrees | 40 |  |
| distance | agrees | 40 |  |
| divmod_pair | not built: result type {'pair': ['int', 'int']} |  |  |
| double_all | agrees | 40 |  |
| doubled | not built: no C function in the lowering |  |  |
| doubled_head | agrees | 40 |  |
| evens | not built: the lowering refuses it |  |  |
| every_other | not built: no C function in the lowering |  |  |
| factorial | agrees within int32 | 40 | {"input": {"n": 21}, "expected": "51090942171709440000", "got": "-4249290049419214848"} |
| fib | agrees | 17 |  |
| filter_pos | agrees | 40 |  |
| find_zero | agrees | 40 |  |
| first_even | agrees | 40 |  |
| first_sorted | not built: the lowering refuses it |  |  |
| floor_ceil | not built: parameter type 'real' |  |  |
| gcd | agrees | 40 |  |
| gcd_of | agrees | 40 |  |
| grid_row_sums | not built: parameter type {'seq': 'seq'} |  |  |
| half_way | not built: parameter type 'real' |  |  |
| has_duplicate | agrees | 40 |  |
| has_elem | agrees | 40 |  |
| has_negative | not built: the lowering refuses it |  |  |
| index_map | not built: result type {'map': ['int', 'int']} |  |  |
| index_of | agrees | 40 |  |
| is_prime | agrees | 40 |  |
| largest | agrees | 40 |  |
| last_of | agrees | 40 |  |
| last_pos | not built: the lowering refuses it |  |  |
| linear_search | agrees | 40 |  |
| longest_row | not built: parameter type {'seq': 'seq'} |  |  |
| lookup_or | not built: parameter type {'map': ['int', 'int']} |  |  |
| manhattan | not built: parameter type {'datatype': 'Point'} |  |  |
| max | agrees | 40 |  |
| members_upto | not built: result type 'set' |  |  |
| min_max | not built: result type {'pair': ['int', 'int']} |  |  |
| none_neg | agrees | 40 |  |
| odd_positions | not built: no C function in the lowering |  |  |
| offset_all | agrees | 40 |  |
| pad_right_len | not built: the lowering refuses it |  |  |
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
| rate_limit | agrees | 40 |  |
| rect_area | not built: parameter type {'datatype': 'Shape'} |  |  |
| relu_all | agrees | 40 |  |
| remainder | agrees | 40 |  |
| rev_equal | agrees | 40 |  |
| reverse | agrees | 40 |  |
| reverse_in_place | not built: the lowering refuses it |  |  |
| ring_push | agrees | 40 |  |
| root_floor | agrees | 40 |  |
| row_max_len | not built: parameter type {'seq': 'seq'} |  |  |
| safe_ratio | not built: parameter type 'real' |  |  |
| sat_scale | agrees | 40 |  |
| scale_all | agrees | 40 |  |
| seq_max | agrees | 40 |  |
| set_collect | not built: result type 'set' |  |  |
| set_first | agrees | 40 |  |
| set_toggle | not built: parameter type 'set' |  |  |
| shape_area | not built: parameter type {'datatype': 'Shape'} |  |  |
| signs | not built: result type {'seq': 'bool'} |  |  |
| some_negative | not built: result type {'datatype': 'Opt'} |  |  |
| sort3 | not built: result type {'tuple': ['int', 'int', 'int']} |  |  |
| sort_it | not built: the lowering refuses it |  |  |
| split_join | not built: the lowering refuses it |  |  |
| squares | not built: no C function in the lowering |  |  |
| strip_dots | not built: the lowering refuses it |  |  |
| sum_one | agrees | 40 |  |
| sum_tail | not built: the lowering refuses it |  |  |
| sum_upto | agrees | 40 |  |
| swap | not built: no C function in the lowering |  |  |
| swap_at | agrees | 12 |  |
| swap_ends | not built: parameter type {'pair': [{'pair': ['int', 'int']}, {'pair': ['int', 'int']}]} |  |  |
| swap_prefix | not built: the lowering refuses it |  |  |
| swap_rows | not built: parameter type {'seq': 'seq'} |  |  |
| tail | not built: no C function in the lowering |  |  |
| tree_count | not built: parameter type {'datatype': 'Tree'} |  |  |
| tree_height | not built: parameter type {'datatype': 'Tree'} |  |  |
| tree_insert | not built: parameter type {'datatype': 'Tree'} |  |  |
| tree_mirror | not built: parameter type {'datatype': 'Tree'} |  |  |
| tree_sum | not built: parameter type {'datatype': 'Tree'} |  |  |
| weighted_sum | not built: the lowering refuses it |  |  |
| word_count | agrees | 40 |  |
| words_seen | not built: result type {'set': 'seq'} |  |  |
| zeros_for | agrees | 40 |  |
| zip_pairs | not built: result type {'seq': {'pair': ['int', 'int']}} |  |  |
