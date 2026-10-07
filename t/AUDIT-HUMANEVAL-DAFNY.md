# Specification audit

Every one-edit mutant of each body, classed by the interpreter over the task's bounded domain (t/audit.py): **killed** (the spec rejects its result somewhere), **same** (computes the same everywhere), **diverges** (runs out of steps where the real body ends), **survivor** (computes something different, and the spec accepts it everywhere).

- tasks: 45; audited: 45; not audited: none
- behaviour-changing mutants the specs kill: 1287 of 1377 (93.5%)
- tasks whose spec admits a survivor: 6 of 45
- dafny: real body verified in 39 of 45; of those, a survivor proved too (a wrong program with a proof) in 5

| task | mutants | killed | same | diverges | survivors | proved by the kernel | a survivor: change at input |
|---|---|---|---|---|---|---|---|
| humaneval_dafny_005_intersperse__intersperse | 40 | 37 | 0 | 3 | 0 | 0 |  |
| humaneval_dafny_006_parse_nested_parens__parse_paren_group | 68 | 14 | 7 | 2 | 45 | 1 | collapse-if: `if c == 40 {` -> `depth := depth + 1;` at s=[41] -> real 0, twin 1 |
| humaneval_dafny_010_is_palindrome__make_palindrome | 39 | 32 | 1 | 2 | 4 | 1 | wrong-var#5: `var reversed: seq := humaneval_dafny_010_is_palindrome__reverse(prefix_to_reverse);` -> `var reversed: seq := humaneval_dafny_010_is_palindrome__reverse(s);` at s=[0] -> real [0], twin [0, 0] |
| humaneval_dafny_010_is_palindrome__reverse | 26 | 24 | 0 | 2 | 0 | 0 |  |
| humaneval_dafny_011_string_xor__string_xor | 29 | 23 | 4 | 2 | 0 | 0 |  |
| humaneval_dafny_024_largest_divisor__largest_divisor | 27 | 13 | 11 | 3 | 0 | 0 |  |
| humaneval_dafny_031_is_prime__is_prime | 33 | 24 | 4 | 4 | 1 | (real vacuous) | off-by-one#1: `if k == 1 {` -> `if k == 0 {` at k=1 -> real False, twin True |
| humaneval_dafny_034_unique__uniqueSorted | 26 | 24 | 0 | 2 | 0 | 0 |  |
| humaneval_dafny_035_max_element__max_element | 24 | 19 | 3 | 2 | 0 | 0 |  |
| humaneval_dafny_038_encode_cyclic__decode_cyclic | 1 | 1 | 0 | 0 | 0 | 0 |  |
| humaneval_dafny_038_encode_cyclic__encode_cyclic | 44 | 41 | 2 | 1 | 0 | 0 |  |
| humaneval_dafny_041_car_race_collision__car_race_collision | 4 | 4 | 0 | 0 | 0 | 0 |  |
| humaneval_dafny_042_incr_list__incr_list | 18 | 16 | 0 | 2 | 0 | 0 |  |
| humaneval_dafny_046_fib4__fib4 | 129 | 120 | 3 | 6 | 0 | 0 |  |
| humaneval_dafny_050_encode_shift__decode_shift | 14 | 11 | 1 | 2 | 0 | 0 |  |
| humaneval_dafny_050_encode_shift__encode_shift | 14 | 11 | 1 | 2 | 0 | 0 |  |
| humaneval_dafny_052_below_threshold__below_threshold | 22 | 19 | 0 | 3 | 0 | 0 |  |
| humaneval_dafny_053_add__add | 4 | 4 | 0 | 0 | 0 | 0 |  |
| humaneval_dafny_055_fib__computeFib | 71 | 63 | 2 | 6 | 0 | 0 |  |
| humaneval_dafny_060_sum_to_n__sum_to_n | 11 | 11 | 0 | 0 | 0 | 0 |  |
| humaneval_dafny_062_derivative__derivative | 16 | 14 | 0 | 2 | 0 | 0 |  |
| humaneval_dafny_063_fibfib__computeFibFib | 98 | 90 | 2 | 6 | 0 | 0 |  |
| humaneval_dafny_068_pluck__pluck | 83 | 77 | 2 | 4 | 0 | 0 |  |
| humaneval_dafny_072_will_it_fly__will_it_fly | 82 | 71 | 7 | 4 | 0 | (real unproved) |  |
| humaneval_dafny_077_iscube__cube_root | 16 | 10 | 2 | 4 | 0 | 0 |  |
| humaneval_dafny_077_iscube__iscube | 19 | 17 | 2 | 0 | 0 | (real timeout) |  |
| humaneval_dafny_083_starts_one_ends__starts_one_ends | 20 | 20 | 0 | 0 | 0 | (real unproved) |  |
| humaneval_dafny_088_sort_array__reverse | 20 | 18 | 0 | 2 | 0 | 0 |  |
| humaneval_dafny_089_encrypt__encrypt | 14 | 11 | 1 | 2 | 0 | 0 |  |
| humaneval_dafny_092_any_int__any_int | 24 | 24 | 0 | 0 | 0 | 0 |  |
| humaneval_dafny_097_multiply__multiply | 6 | 6 | 0 | 0 | 0 | 0 |  |
| humaneval_dafny_102_choose_num__choose_num | 73 | 61 | 4 | 8 | 0 | 0 |  |
| humaneval_dafny_110_exchange__exchange | 17 | 17 | 0 | 0 | 0 | 0 |  |
| humaneval_dafny_112_reverse_delete__check_palindrome | 40 | 36 | 4 | 0 | 0 | 0 |  |
| humaneval_dafny_130_tri__tri | 65 | 59 | 1 | 5 | 0 | (real timeout) |  |
| humaneval_dafny_135_can_arrange__can_arrange | 30 | 25 | 1 | 2 | 2 | 1 | off-by-one#2: `pos := -(1);` -> `pos := -(2);` at arr=[0] -> real -1, twin -2 |
| humaneval_dafny_139_special_factorial__special_factorial | 40 | 35 | 2 | 3 | 0 | (real unproved) |  |
| humaneval_dafny_146_specialfilter__specialFilter | 39 | 20 | 4 | 2 | 13 | 1 | off-by-one#3: `while i_v2 < len(s)` -> `while i_v2 < len(s) + -1` at s=[11] -> real [11], twin [] |
| humaneval_dafny_150_x_or_y__x_or_y | 12 | 12 | 0 | 0 | 0 | 0 |  |
| humaneval_dafny_152_compare__compare | 21 | 18 | 1 | 2 | 0 | 0 |  |
| humaneval_dafny_157_right_angle_triangle__right_angle_triangle | 60 | 55 | 5 | 0 | 0 | 0 |  |
| humaneval_dafny_159_eat__eat | 28 | 27 | 1 | 0 | 0 | 0 |  |
| humaneval_dafny_161_solve__reverse | 20 | 18 | 0 | 2 | 0 | 0 |  |
| humaneval_dafny_163_generate_integers__generate_integers | 69 | 24 | 2 | 18 | 25 | 1 | compare-flip: `while i_v2 <= upper` -> `while i_v2 < upper` at a=0, b=2 -> real [2], twin [] |
| humaneval_dafny_163_generate_integers__max | 12 | 11 | 1 | 0 | 0 | 0 |  |
