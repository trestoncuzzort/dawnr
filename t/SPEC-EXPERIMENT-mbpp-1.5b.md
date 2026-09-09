# The spec experiment on MBPP: qwen2.5-coder:1.5b

ROADMAP 12.6. One reply per problem, temperature 0, fixed seed; the
prompt is `spec_experiment.build_prompt` (grammar, five committed tasks
as examples, the problem text and its three assertions). Every stage
is a count, every refusal is named, and the two failures 12.6 keeps
apart are kept apart here: a task that VERIFIES with a REFUTED twin,
and a task that passes the problem's own tests.

## Stages

| stage | count |
|---|---:|
| MBPP problems whose tests are in t's fragment (the pool) | 368 |
| replies recorded | 368 |
| replies with a t block | 368 |
| blocks that parse | 141 |
| tasks that are well-formed (graded below) | 51 |

Refusals, by named reason:

- 33 x `parse: line N: expected '{', found 'if'`
- 32 x `wf: task decreases without a self-call`
- 30 x `parse: line N: '[' does not start an expression`
- 29 x `parse: line N: expected ']', found ':'`
- 12 x `parse: line N: unexpected character '&'`
- 10 x `parse: line N: expected ')', found 'for'`
- 10 x `wf: unbound var True`
- 9 x `parse: line N: unexpected character '^'`
- 9 x `parse: line N: '*' does not start an expression`
- 8 x `parse: line N: '/' does not start an expression`
- 7 x `parse: line N: expected 'else', found 'i'`
- 6 x `parse: line N: expected '{', found 'is'`
- 6 x `parse: line N: 'end of input' does not start an expression`
- 5 x `wf: call of unknown fun sum_upto`
- 5 x `parse: line N: comparisons do not chain`
- 5 x `wf: unbound var null`
- 4 x `wf: unbound var x`
- 4 x `parse: line N: expected 'eof', found 'spec'`
- 4 x `parse: line N: expected 'then', found 'end of input'`
- 4 x `parse: line N: expected '{', found 'of'`
- 3 x `parse: line N: unexpected character '|'`
- 3 x `parse: line N: expected ']', found '.'`
- 3 x `parse: line N: expected 'else', found 'end of input'`
- 3 x `wf: unbound var False`
- 3 x `wf: call of unknown fun str`

## The problem's own tests (interp on the MBPP assertions)

| outcome | tasks |
|---|---:|
| pass | 23 |
| fail | 26 |
| undefined | 1 |
| signature | 1 |

## The seven kernels (real / twin), over the well-formed tasks

| kernel | verified / refuted | of tasks |
|---|---:|---:|
| dafny | 28 | 51 |
| verus | 27 | 51 |
| spark | 26 | 51 |
| framac | 27 | 51 |
| lean | 23 | 51 |
| rocq | 27 | 51 |
| fstar | 9 | 51 |

| columns counting | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|---|
| tasks | 3 | 22 | 2 | 1 | 0 | 0 | 0 | 23 |

Tasks with no twin at all (every mutation on the ladder computes what the real body computes, or no input satisfies requires): 3.

## 12.6's table: verifies with a refuted twin, against passes its tests

| verifies with refuted twin in | tests pass | tests fail | requires-excluded | undefined | signature |
|---|---:|---:|---:|---:|---:|
| all seven | 1 | 2 | 0 | 0 | 0 |
| some column | 19 | 6 | 0 | 0 | 0 |
| none | 3 | 18 | 0 | 1 | 1 |

**1 of 368 problems** got a task that verifies with a refuted twin in all seven columns and passes its tests; 20 in at least one column. Verified-with-twin but failing its tests, the class 12.6 warns about: 2 in all seven, 6 in some column.

MBPP-DFY subset: 67 pool problems are MBPP-DFY problems (ROADMAP 16.2's family); 19 of them reached the kernels and 0 verify in all seven and pass their tests.

## Every task

| task_id | task | columns counting | tests | dafny | verus | spark | framac | lean | rocq | fstar |
|---:|---|---:|---|---|---|---|---|---|---|---|
| 14 | mbpp_14__find_Volume | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 17 | mbpp_17__square_perimeter | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 22 | mbpp_22__find_first_duplicate | 0 | fail | unproved / unproved | malformed / malformed | timeout / unproved | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 35 | mbpp_35__find_rect_num | 6 | fail | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 47 | mbpp_47__compute_Last_Digit | 0 | fail | unproved / unproved | malformed / malformed | timeout / timeout | abstain / abstain | unproved / unproved | unproved / unproved | unproved / unproved |
| 51 | mbpp_51__check_equilateral | 5 | pass | verified / refuted | verified / refuted | verified / refuted | verified / unproved | abstain / abstain | verified / refuted | verified / refuted |
| 52 | mbpp_52__parallelogram_area | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 58 | mbpp_58__opposite_Signs | 5 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | malformed / refuted |
| 59 | mbpp_59__is_octagonal | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 89 | mbpp_89__closest_num | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| 112 | mbpp_112__perimeter | 0 | undefined | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 135 | mbpp_135__hexagonal_num | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 158 | mbpp_158__min_Ops | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 171 | mbpp_171__perimeter_pentagon | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 176 | mbpp_176__perimeter_triangle | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 190 | mbpp_190__count_Intgral_Points | 0 | fail | unproved / refuted | unproved / refuted | unproved / unproved | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 221 | mbpp_221__first_even | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 234 | mbpp_234__volume_cube | 0 | pass | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 264 | mbpp_264__dog_age | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 266 | mbpp_266__lateralsurface_cube | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 268 | mbpp_268__find_star_num | 6 | fail | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 320 | mbpp_320__sum_difference | 0 | fail | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 347 | mbpp_347__count_Squares | 0 | fail | unproved / unproved | unproved / unproved | timeout / unproved | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 351 | mbpp_351__first_Element | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 354 | mbpp_354__tn_ap | 0 | fail | unproved / unproved | unproved / unproved | unproved / unproved | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 355 | mbpp_355__count_Rectangles | 0 | fail | malformed / malformed | malformed / malformed | malformed / malformed | malformed / malformed | unproved / unproved | malformed / malformed | malformed / malformed |
| 356 | mbpp_356__find_angle | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 369 | mbpp_369__lateralsurface_cuboid | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 373 | mbpp_373__volume_cuboid | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 379 | mbpp_379__surfacearea_cuboid | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 441 | mbpp_441__surfacearea_cube | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 455 | mbpp_455__check_monthnumb_number | 0 | fail | unproved / unproved | unproved / unproved | unproved / unproved | timeout / timeout | unproved / refuted | timeout / refuted | unproved / unproved |
| 458 | mbpp_458__rectangle_area | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 479 | mbpp_479__first_Digit | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| 499 | mbpp_499__diameter_circle | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 525 | mbpp_525__parallel_lines | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | abstain / abstain | abstain / abstain | unproved / refuted | unproved / refuted |
| 566 | mbpp_566__sum_digits | 0 | fail | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 627 | mbpp_627__find_First_Missing | 0 | fail | unproved / unproved | unproved / unproved | unproved / unproved | timeout / timeout | unproved / refuted | timeout / refuted | unproved / unproved |
| 637 | mbpp_637__noprofit_noloss | 4 | pass | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | abstain / abstain | malformed / malformed | verified / refuted |
| 654 | mbpp_654__rectangle_perimeter | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 663 | mbpp_663__find_max_val | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 716 | mbpp_716__rombus_perimeter | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 762 | mbpp_762__check_monthnumber_number | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 768 | mbpp_768__check_Odd_Parity | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted |
| 793 | mbpp_793__last | 0 | signature | unproved / unproved | unproved / unproved | unproved / unproved | timeout / timeout | unproved / refuted | timeout / refuted | unproved / unproved |
| 820 | mbpp_820__check_monthnum_number | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 850 | mbpp_850__is_triangleexists | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 855 | mbpp_855__check_Even_Parity | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted |
| 882 | mbpp_882__parallelogram_perimeter | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 924 | mbpp_924__max_of_two | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 970 | mbpp_970__min_of_two | 0 | pass | verified / verified | verified / verified | verified / verified | verified / verified | verified / unproved | verified / verified | verified / malformed |

## Problems that produced no graded task

| task_id | fn | stage | why |
|---:|---|---|---|
| 3 | is_not_prime | parse | line 5: 'not' does not start an expression |
| 5 | count_ways | wf | call of unknown fun mbpp_5__count_ways; call of unknown fun mbpp_5__count_ways; + over non-int; ensures references the t |
| 6 | differ_At_One_Bit_Pos | parse | line 6: unexpected character '^' |
| 19 | test_duplicate | parse | line 5: expected ')', found 'for' |
| 20 | is_woodall | parse | line 5: '/' does not start an expression |
| 24 | binary_to_decimal | wf | call of unknown fun mbpp_24__binary_to_decimal; * over non-int |
| 25 | find_Product | parse | line 9: expected ']', found ':' |
| 28 | binomial_Coeff | parse | line 14: expected '{', found 'if' |
| 29 | get_Odd_Occurrence | wf | unbound var x; == wants two ints, two bools or two seqs; unbound var x; != wants two ints, two bools or two seqs; unboun |
| 32 | max_Prime_Factors | parse | line 5: expected '{', found 'is' |
| 33 | decimal_To_Binary | parse | line 14: unexpected character "'" |
| 34 | find_missing | parse | line 4: expected '{', found 'is' |
| 36 | find_Nth_Digit | wf | task decreases without a self-call; unbound var count; + over non-int; unbound var count; + over non-int |
| 38 | div_even_odd | parse | line 13: expected '{', found 'if' |
| 42 | find_Sum | parse | line 9: expected ']', found ':' |
| 45 | get_gcd | parse | line 9: expected ']', found ':' |
| 46 | test_distinct | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 48 | odd_bit_set_number | parse | line 5: unexpected character '/' |
| 55 | tn_gp | parse | line 5: unexpected character '^' |
| 56 | check | wf | call of unknown fun reverse; * over non-int; unbound var False; assign r: None into bool; call of unknown fun str; len o |
| 57 | find_Max_Num | parse | line 9: expected ']', found ':' |
| 60 | max_len_sub | parse | line 22: expected 'eof', found 'spec' |
| 62 | smallest_num | parse | line 4: '[' does not start an expression |
| 66 | pos_count | parse | line 5: '[' does not start an expression |
| 67 | bell_number | wf | call of unknown fun sum_upto; * over non-int; task decreases without a self-call; call of unknown fun sum_upto; * over n |
| 68 | is_Monotonic | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 69 | is_sublist | parse | line 5: expected ']', found '.' |
| 72 | dif_Square | wf | unbound var True; assign r: None into bool; unbound var True; assign r: None into bool; unbound var False; assign r: Non |
| 76 | count_Squares | wf | task decreases without a self-call |
| 77 | is_Diff | parse | line 5: comparisons do not chain; parenthesise |
| 78 | count_With_Odd_SetBits | parse | line 5: unexpected character '&' |
| 84 | sequence | wf | call of unknown fun mbpp_84__sequence; ite branches differ: None vs int; ite branches differ: int vs None; call of unkno |
| 86 | centered_hexagonal_number | wf | task decreases without a self-call |
| 93 | power | parse | line 6: '*' does not start an expression |
| 96 | divisor | parse | line 5: '[' does not start an expression |
| 100 | next_smallest_palindrome | parse | line 9: expected 'then', found 'end of input' |
| 101 | kth_element | parse | line 13: expected '{', found 'if' |
| 103 | eulerian_num | parse | line 13: expected '{', found 'if' |
| 107 | count_Hexadecimal | parse | line 10: unexpected character "'" |
| 119 | search | parse | line 4: expected '{', found 'is' |
| 121 | check_triplet | wf | bound var i shadows a name in scope |
| 122 | smartNumber | wf | call of unknown fun mbpp_122__smartNumber; + over non-int |
| 123 | amicable_numbers_sum | parse | line 9: expected 'else', found 'end of input' |
| 126 | sum | wf | call of unknown fun mbpp_126__sum; call of unknown fun mbpp_126__sum; ite branches differ: None vs int; ite branches dif |
| 127 | multiply_int | wf | call of unknown fun mbpp_127__multiply_int; call of unknown fun mbpp_127__multiply_int; ite branches differ: None vs int |
| 133 | sum_negativenum | parse | line 5: '[' does not start an expression |
| 138 | is_Sum_Of_Powers_Of_Two | parse | line 5: unexpected character '&' |
| 142 | count_samepair | parse | line 4: comparisons do not chain; parenthesise |
| 144 | sum_Pairs | parse | line 5: expected ')', found 'for' |
| 148 | sum_digits_twoparts | wf | call of unknown fun sum_digits; call of unknown fun sum_digits |
| 149 | longest_subseq_with_diff_one | parse | line 21: expected 'else', found '}' |
| 150 | does_Contain_B | parse | line 9: expected 'decreases', found 'end of input' |
| 151 | is_coprime | wf | task decreases without a self-call; assign r: int into bool; assign r: int into bool; assign r: int into bool; assign r: |
| 155 | even_bit_toggle_number | parse | line 5: unexpected character '^' |
| 162 | sum_series | wf | task decreases without a self-call |
| 164 | areEquivalent | wf | task decreases without a self-call; unbound var n; == wants two ints, two bools or two seqs; assign r: int into bool; un |
| 166 | find_even_Pair | parse | line 5: unexpected character '^' |
| 167 | next_Power_Of_2 | parse | line 13: expected '{', found 'if' |
| 168 | frequency | parse | line 9: expected ']', found ':' |
| 169 | get_pell | parse | line 13: expected '{', found 'if' |
| 170 | sum_range_list | parse | line 5: expected ']', found ':' |
| 179 | is_num_keith | wf | call of unknown fun sum_of_keith; == wants two ints, two bools or two seqs; unbound var False; assign r: None into bool; |
| 183 | count_pairs | parse | line 9: expected ']', found ':' |
| 184 | greater_specificnum | wf | unbound var False; assign r: None into bool; unbound var True; assign r: None into bool |
| 188 | prod_Square | wf | task decreases without a self-call; assign r: int into bool; assign r: int into bool; assign r: int into bool; assign r: |
| 189 | first_Missing_Positive | parse | line 5: expected '{', found 'if' |
| 194 | octal_To_Decimal | parse | line 5: '*' does not start an expression |
| 195 | first | wf | unbound var null; != wants two ints, two bools or two seqs |
| 199 | highest_Power_of_2 | parse | line 9: '/' does not start an expression |
| 203 | hamming_Distance | parse | line 6: unexpected character '^' |
| 211 | count_Num | parse | line 17: expected 'else', found 'i' |
| 212 | fourth_Power_Sum | parse | line 5: '[' does not start an expression |
| 218 | min_Operations | wf | task decreases without a self-call |
| 223 | is_majority | wf | unbound var False; assign r: None into bool; bound var i shadows a name in scope; bound var i shadows a name in scope; u |
| 224 | count_Set_Bits | parse | line 9: unexpected character '&' |
| 225 | find_Min | parse | line 5: expected ']', found ':' |
| 227 | min_of_three | parse | line 8: expected '{', found 'if' |
| 228 | all_Bits_Set_In_The_Given_Range | parse | line 59: 'end of input' does not start an expression |
| 235 | even_bit_set_number | parse | line 5: unexpected character '/' |
| 236 | No_of_Triangle | parse | line 30: expected 'eof', found 'spec' |
| 239 | get_total_number_of_sequences | parse | line 10: 'end of input' does not start an expression |
| 244 | next_Perfect_Square | parse | line 9: expected 'then', found 'end of input' |
| 245 | max_sum | parse | line 13: expected '{', found 'if' |
| 256 | count_Primes_nums | parse | line 9: expected 'else', found 'end of input' |
| 258 | count_odd | parse | line 5: '[' does not start an expression |
| 260 | newman_prime | parse | line 9: expected 'else', found 'end of input' |
| 267 | square_Sum | wf | call of unknown fun mbpp_267__square_Sum; + over non-int |
| 270 | sum_even_and_even_index | parse | line 5: '[' does not start an expression |
| 271 | even_Power_Sum | parse | line 5: '[' does not start an expression |
| 274 | even_binomial_Coeff_Sum | parse | line 5: expected ')', found 'for' |
| 275 | get_Position | parse | line 14: expected '{', found 'if' |
| 279 | is_num_decagonal | parse | line 5: comparisons do not chain; parenthesise |
| 281 | all_unique | wf | unbound var True; assign r: None into bool; unbound var j; at wants (seq, int); unbound var False; assign r: None into b |
| 283 | validate | parse | line 14: 'int' does not start an expression |
| 286 | max_sub_array_sum_repeated | wf | call of unknown fun max_sub_array_sum; * over non-int; call of unknown fun max_sub_array_sum; * over non-int; call of un |
| 287 | square_Sum | wf | call of unknown fun mbpp_287__square_Sum; + over non-int |
| 288 | modular_inverse | parse | line 5: '[' does not start an expression |
| 289 | odd_Days | parse | line 10: expected 'decreases', found 'end of input' |
| 291 | count_no_of_ways | parse | line 14: expected '{', found 'if' |
| 292 | find | parse | line 3: '/' does not start an expression |
| 295 | sum_div | wf | task decreases without a self-call |
| 296 | get_Inv_Count | parse | line 5: expected '{', found 'in' |
| 302 | set_Bit_Number | wf | call of unknown fun mbpp_302__set_Bit_Number; * over non-int |
| 303 | solve | parse | line 5: expected ']', found ':' |
| 306 | max_sum_increasing_subseq | parse | line 25: expected 'else', found 'j' |
| 309 | maximum | wf | v1 expression form in a v0 task; call of unknown fun max; == wants two ints, two bools or two seqs |
| 311 | set_left_most_unset_bit | parse | line 15: unexpected character '&' |
| 313 | pos_nos | parse | line 5: '[' does not start an expression |
| 316 | find_last_occurrence | parse | line 4: expected '{', found 'is' |
| 318 | max_volume | parse | line 14: expected ']', found ':' |
| 325 | get_Min_Squares | parse | line 9: 'end of input' does not start an expression |
| 327 | check_isosceles | wf | unbound var True; assign r: None into bool; unbound var True; assign r: None into bool; unbound var True; assign r: None |
| 329 | neg_count | parse | line 5: '[' does not start an expression |
| 331 | count_unset_bits | parse | line 5: unexpected character '&' |
| 334 | check_Validity | wf | unbound var False; assign r: None into bool; unbound var True; assign r: None into bool |
| 335 | ap_sum | wf | task decreases without a self-call |
| 339 | find_Divisor | wf | task decreases without a self-call |
| 340 | sum_three_smallest_nums | parse | line 4: '[' does not start an expression |
| 344 | count_Odd_Squares | parse | line 13: '/' does not start an expression |
| 346 | zigzag | wf | call of unknown fun mbpp_346__zigzag; call of unknown fun mbpp_346__zigzag; ite branches differ: int vs None |
| 348 | find_ways | wf | call of unknown fun sum_upto; call of unknown fun sum_upto; * over non-int; call of unknown fun sum_upto; call of unknow |
| 360 | get_carol | wf | task decreases without a self-call |
| 362 | max_occurrences | parse | line 4: '[' does not start an expression |
| 365 | count_Digit | wf | call of unknown fun str; len of a non-seq; call of unknown fun str; len of a non-seq; call of unknown fun str; len of a  |
| 366 | adjacent_num_product | parse | line 5: expected ')', found 'for' |
| 371 | smallest_missing | wf | unbound var x; != wants two ints, two bools or two seqs; unbound var x; != wants two ints, two bools or two seqs; unboun |
| 375 | round_num | parse | line 6: expected '{', found 'if' |
| 382 | find_rotation_count | parse | line 4: '[' does not start an expression |
| 383 | even_bit_toggle_number | parse | line 5: unexpected character '&' |
| 384 | frequency_Of_Smallest | parse | line 5: '[' does not start an expression |
| 385 | get_perrin | parse | line 13: expected '{', found 'if' |
| 388 | highest_Power_of_2 | parse | line 9: '/' does not start an expression |
| 389 | find_lucas | wf | task decreases without a self-call |
| 392 | get_max_sum | wf | call of unknown fun max; ite branches differ: int vs None; call of unknown fun max; == wants two ints, two bools or two  |
| 402 | ncr_modp | parse | line 15: expected '{', found 'if' |
| 404 | minimum | wf | v1 expression form in a v0 task; call of unknown fun min; == wants two ints, two bools or two seqs |
| 407 | rearrange_bigger | parse | line 35: expected ':=', found '(' |
| 414 | overlapping | parse | line 5: expected ')', found 'in' |
| 416 | breakSum | wf | call of unknown fun mbpp_416__breakSum; argument type mismatch calling max; call of unknown fun mbpp_416__breakSum; argu |
| 420 | cube_Sum | parse | line 5: expected ')', found 'for' |
| 430 | parabola_directrix | parse | line 5: '*' does not start an expression |
| 435 | last_Digit | wf | task decreases without a self-call |
| 436 | neg_nos | wf | unbound var null; != wants two ints, two bools or two seqs |
| 439 | multiple_to_single | parse | line 10: expected ']', found '.' |
| 443 | largest_neg | parse | line 4: '[' does not start an expression |
| 448 | cal_sum | parse | line 13: expected '{', found 'if' |
| 453 | sumofFactors | parse | line 5: expected '{', found 'of' |
| 463 | max_subarray_product | parse | line 9: expected 'then', found '=' |
| 466 | find_peak | wf | unbound var x; == wants two ints, two bools or two seqs; unbound var x; != wants two ints, two bools or two seqs; unboun |
| 467 | decimal_to_Octal | parse | line 5: unexpected character '&' |
| 468 | max_product | parse | line 9: expected ']', found 'end of input' |
| 469 | max_profit | parse | line 13: expected '{', found 'if' |
| 471 | find_remainder | parse | line 5: '.' does not start an expression |
| 472 | check_Consecutive | parse | line 14: expected ':=', found ';' |
| 476 | big_sum | parse | line 10: expected ']', found ':' |
| 481 | is_subset_sum | parse | line 6: expected ')', found 'ensures' |
| 483 | first_Factorial_Divisible_Number | parse | line 15: expected ':=', found ';' |
| 485 | largest_palindrome | wf | call of unknown fun max; == wants two ints, two bools or two seqs |
| 489 | frequency_Of_Largest | parse | line 16: expected '[', found 'end of input' |
| 491 | sum_gp | parse | line 5: unexpected character '^' |
| 492 | binary_search | parse | line 12: comparisons do not chain; parenthesise |
| 498 | gcd | wf | task decreases without a self-call |
| 501 | num_comm_div | wf | task decreases without a self-call |
| 502 | find | wf | operator 'mod' not in v0; == wants two ints, two bools or two seqs; operator 'mod' not in v0; assign r: None into int |
| 504 | sum_Of_Series | wf | task decreases without a self-call |
| 506 | permutation_coefficient | parse | line 14: expected '{', found 'if' |
| 509 | average_Odd | parse | line 7: expected ':', found 'returns' |
| 510 | no_of_subsequences | parse | line 12: expected ']', found ':' |
| 511 | find_Min_Sum | wf | task decreases without a self-call |
| 515 | modular_sum | parse | line 5: expected ']', found ':' |
| 517 | largest_pos | parse | line 4: '[' does not start an expression |
| 518 | sqrt_root | wf | task decreases without a self-call |
| 520 | get_lcm | parse | line 4: '[' does not start an expression |
| 521 | check_isosceles | parse | line 9: expected '{', found 'if' |
| 522 | lbs | parse | line 7: 'seq' is not one of int bool |
| 524 | max_sum_increasing_subsequence | parse | line 13: expected '{', found 'if' |
| 527 | get_pairs_count | parse | line 20: expected '{', found 'if' |
| 529 | jacobsthal_lucas | parse | line 13: expected '{', found 'if' |
| 531 | min_coins | wf | unbound var null; != wants two ints, two bools or two seqs; assign to value, not a return or local |
| 540 | find_Diff | parse | line 18: expected 'else', found 'if' |
| 541 | check_abundant | parse | line 17: expected 'else', found 'i' |
| 543 | count_digits | parse | line 5: expected ':', found ':=' |
| 545 | toggle_F_and_L_bits | parse | line 5: unexpected character '^' |
| 547 | Total_Hamming_Distance | parse | line 5: expected ')', found 'for' |
| 548 | longest_increasing_subsequence | parse | line 7: 'seq' is not one of int bool |
| 549 | odd_Num_Sum | parse | line 5: '[' does not start an expression |
| 550 | find_Max | parse | line 20: expected 'else', found 'i' |
| 555 | difference | wf | task decreases without a self-call |
| 556 | find_Odd_Pair | parse | line 5: unexpected character '^' |
| 558 | digit_distance_nums | wf | task decreases without a self-call |
| 559 | max_sub_array_sum | parse | line 9: expected 'then', found '=' |
| 564 | count_Pairs | parse | line 7: expected 'id', found 'len' |
| 567 | issort_list | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 571 | max_sum_pair_diff_lessthan_K | parse | line 5: expected '{', found 'for' |
| 573 | unique_product | parse | line 4: '[' does not start an expression |
| 575 | count_no | wf | call of unknown fun mbpp_575__count_no; call of unknown fun mbpp_575__count_no; ite branches differ: int vs None; call o |
| 576 | is_Sub_Array | parse | line 5: expected ']', found '.' |
| 577 | last_Digit_Factorial | wf | task decreases without a self-call |
| 581 | surface_Area | parse | line 6: '*' does not start an expression |
| 583 | catalan_number | parse | line 13: expected '{', found 'if' |
| 588 | big_diff | parse | line 9: expected ']', found ':' |
| 592 | sum_Of_product | parse | line 5: expected ')', found 'for' |
| 594 | diff_even_odd | parse | line 9: expected ']', found ':' |
| 597 | find_kth | parse | line 12: expected '{', found 'if' |
| 598 | armstrong_number | parse | line 5: '*' does not start an expression |
| 600 | is_Even | parse | line 5: unexpected character '&' |
| 605 | prime_num | parse | line 5: 'exists' does not start an expression |
| 608 | bell_Number | wf | call of unknown fun sum_upto; * over non-int; task decreases without a self-call; call of unknown fun sum_upto; * over n |
| 609 | floor_Min | parse | line 15: expected '{', found 'if' |
| 620 | largest_subset | parse | line 60: expected '{', found 'end of input' |
| 626 | triangle_area | wf | unbound var s; at wants (seq, int); unbound var x; != wants two ints, two bools or two seqs; unbound var s; len of a non |
| 633 | pair_OR_Sum | parse | line 5: unexpected character '^' |
| 634 | even_Power_Sum | parse | line 5: '[' does not start an expression |
| 638 | wind_chill | parse | line 2: expected 'id', found 't' |
| 641 | is_nonagonal | wf | task decreases without a self-call |
| 646 | No_of_cubes | parse | line 6: '*' does not start an expression |
| 649 | sum_Range_list | parse | line 5: expected ']', found ':' |
| 650 | are_Equal | parse | line 9: expected ']', found ':' |
| 655 | fifth_Power_Sum | parse | line 5: '[' does not start an expression |
| 656 | find_Min_Sum | parse | line 5: expected ')', found 'for' |
| 657 | first_Digit | parse | line 17: expected 'eof', found 'spec' |
| 658 | max_occurrences | wf | unbound var null; != wants two ints, two bools or two seqs; call of unknown fun max; == wants two ints, two bools or two |
| 661 | max_sum_of_three_consecutive | parse | line 9: expected 'eof', found 'spec' |
| 664 | average_Even | parse | line 7: expected ':', found 'returns' |
| 670 | decreasing_trend | parse | line 17: expected 'else', found 'i' |
| 671 | set_Right_most_Unset_Bit | parse | line 41: 'end of input' does not start an expression |
| 672 | max_of_three | parse | line 8: expected '{', found 'if' |
| 673 | convert | parse | line 10: expected ']', found ':' |
| 675 | sum_nums | parse | line 9: expected 'else', found '}' |
| 677 | validity_triangle | wf | unbound var True; assign r: None into bool; unbound var True; assign r: None into bool; unbound var True; assign r: None |
| 680 | increasing_trend | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 681 | smallest_Divisor | parse | line 9: expected 'then', found 'end of input' |
| 683 | sum_Square | parse | line 5: 'int' does not start an expression |
| 685 | sum_Of_Primes | parse | line 9: expected 'then', found 'end of input' |
| 687 | recur_gcd | wf | task decreases without a self-call |
| 689 | min_jumps | parse | line 17: expected 'else', found 'if' |
| 692 | last_Two_Digits | parse | line 9: 'end of input' does not start an expression |
| 697 | count_even | parse | line 5: '[' does not start an expression |
| 701 | equilibrium_index | parse | line 5: expected ']', found ':' |
| 702 | removals | parse | line 5: '[' does not start an expression |
| 706 | is_subset | parse | line 7: expected 'id', found 'exists' |
| 707 | count_Set_Bits | wf | call of unknown fun sum_upto; == wants two ints, two bools or two seqs; call of unknown fun sum_upto; == wants two ints, |
| 711 | product_Equal | parse | line 7: expected ':', found ':=' |
| 714 | count_Fac | parse | line 9: '/' does not start an expression |
| 723 | count_same_pair | parse | line 5: '[' does not start an expression |
| 724 | power_base_sum | parse | line 6: '*' does not start an expression |
| 733 | find_first_occurrence | parse | line 4: expected '{', found 'is' |
| 734 | sum_Of_Subarray_Prod | parse | line 5: expected ')', found 'for' |
| 735 | toggle_middle_bits | parse | line 5: unexpected character '&' |
| 736 | left_insertion | wf | unbound var nil; != wants two ints, two bools or two seqs |
| 739 | find_Index | parse | line 5: '[' does not start an expression |
| 751 | check_min_heap | parse | line 9: '/' does not start an expression |
| 752 | jacobsthal_num | wf | task decreases without a self-call |
| 765 | is_polite | parse | line 74: 'end of input' does not start an expression |
| 767 | get_Pairs_Count | parse | line 9: expected ']', found ':' |
| 770 | odd_Num_Sum | parse | line 5: '*' does not start an expression |
| 775 | odd_position | wf | unbound var True; == wants two ints, two bools or two seqs; unbound var False; == wants two ints, two bools or two seqs; |
| 777 | find_Sum | parse | line 9: expected ']', found ':' |
| 782 | Odd_Length_Sum | parse | line 5: '[' does not start an expression |
| 784 | mul_even_odd | parse | line 9: expected ']', found ':' |
| 786 | right_insertion | wf | unbound var nil; != wants two ints, two bools or two seqs |
| 789 | perimeter_polygon | wf | task decreases without a self-call |
| 790 | even_position | wf | unbound var True; == wants two ints, two bools or two seqs; task decreases without a self-call; unbound var i; == wants  |
| 797 | sum_in_Range | parse | line 5: expected '{', found 'of' |
| 798 | _sum | parse | line 3: unexpected character '_' |
| 799 | left_Rotate | parse | line 6: unexpected character '/' |
| 801 | test_three_equal | parse | line 10: expected '{', found 'if' |
| 802 | count_Rotation | parse | line 18: expected 'else', found 'i' |
| 803 | is_Perfect_Square | wf | call of unknown fun sqrt; call of unknown fun sqrt; * over non-int; unbound var False; assign r: None into bool; call of |
| 804 | is_Product_Even | parse | line 17: expected ']', found ':' |
| 807 | first_odd | parse | line 4: '[' does not start an expression |
| 814 | rombus_area | wf | task decreases without a self-call |
| 831 | count_Pairs | parse | line 5: expected ')', found 'for' |
| 836 | max_sub_array_sum | parse | line 9: expected ']', found ':' |
| 837 | cube_Sum | parse | line 5: '*' does not start an expression |
| 841 | get_inv_count | parse | line 5: expected ')', found '.' |
| 842 | get_odd_occurence | wf | unbound var x; == wants two ints, two bools or two seqs; unbound var x; != wants two ints, two bools or two seqs; unboun |
| 843 | nth_super_ugly_number | parse | line 5: '[' does not start an expression |
| 844 | get_Number | wf | task decreases without a self-call |
| 845 | find_Digits | wf | call of unknown fun str; len of a non-seq; task decreases without a self-call |
| 846 | find_platform | parse | line 3: expected 'id', found 't' |
| 848 | area_trapezium | wf | operator 'div' not in v0; == wants two ints, two bools or two seqs; operator 'div' not in v0; assign r: None into int |
| 849 | Sum | parse | line 9: '/' does not start an expression |
| 853 | sum_of_odd_Factors | parse | line 5: expected '{', found 'of' |
| 856 | find_Min_Swaps | parse | line 9: expected ']', found ':' |
| 863 | find_longest_conseq_subseq | parse | line 7: 'seq' is not one of int bool |
| 867 | min_Num | parse | line 5: comparisons do not chain; parenthesise |
| 870 | sum_positivenum | parse | line 5: '[' does not start an expression |
| 873 | fibonacci | parse | line 13: expected '{', found 'if' |
| 876 | lcm | wf | call of unknown fun mbpp_876__lcm; call of unknown fun mbpp_876__lcm; call of unknown fun gcd; div over non-int; ite bra |
| 881 | sum_even_odd | parse | line 5: expected ']', found ':' |
| 884 | all_Bits_Set_In_The_Given_Range | parse | line 15: unexpected character '&' |
| 887 | is_odd | parse | line 5: unexpected character '&' |
| 890 | find_Extra | parse | line 4: expected '{', found 'is' |
| 891 | same_Length | wf | call of unknown fun str; len of a non-seq; call of unknown fun str; len of a non-seq; unbound var False; assign r: None  |
| 895 | max_sum_subseq | parse | line 9: expected ']', found ':' |
| 899 | check | parse | line 17: expected 'else', found 'i' |
| 901 | smallest_multiple | wf | task decreases without a self-call |
| 903 | count_Unset_Bits | wf | call of unknown fun sum_upto; call of unknown fun sum_upto; - over non-int; call of unknown fun sum_upto; call of unknow |
| 905 | sum_of_square | wf | task decreases without a self-call |
| 908 | find_fixed_point | wf | unbound var null; != wants two ints, two bools or two seqs |
| 909 | previous_palindrome | parse | line 5: expected '{', found 'end of input' |
| 911 | maximum_product | parse | line 21: expected ')', found 'end of input' |
| 918 | coin_change | parse | line 9: expected 'then', found '=' |
| 919 | multiply_list | parse | line 9: expected ']', found ':' |
| 926 | rencontres_number | parse | line 13: expected '{', found 'if' |
| 931 | sum_series | wf | task decreases without a self-call |
| 934 | dealnnoy_num | parse | line 14: expected '{', found 'if' |
| 935 | series_sum | wf | task decreases without a self-call |
| 952 | nCr_mod_p | parse | line 15: expected '{', found 'if' |
| 953 | subset | parse | line 9: expected ']', found ':' |
| 955 | is_abundant | parse | line 17: expected 'else', found 'i' |
| 957 | get_First_Set_Bit_Pos | parse | line 14: unexpected character '&' |
| 960 | get_noOfways | parse | line 13: expected '{', found 'if' |
| 962 | sum_Even | parse | line 5: expected '{', found 'of' |
| 968 | floor_Max | parse | line 15: expected '{', found 'if' |
| 971 | maximum_segments | parse | line 13: expected '{', found 'if' |

