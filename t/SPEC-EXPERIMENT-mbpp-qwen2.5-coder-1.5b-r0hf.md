# The spec experiment on MBPP: qwen2.5-coder-1.5b-r0hf

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
| blocks that parse | 139 |
| tasks that are well-formed (graded below) | 66 |

Refusals, by named reason:

- 25 x `parse: line N: expected '{', found '.'`
- 24 x `parse: line N: unexpected character '^'`
- 23 x `parse: line N: unexpected character '&'`
- 21 x `parse: line N: '[' does not start an expression`
- 18 x `wf: task decreases without a self-call`
- 17 x `parse: line N: expected ')', found 'for'`
- 16 x `parse: line N: '/' does not start an expression`
- 9 x `wf: unbound var True`
- 9 x `parse: line N: unexpected character '|'`
- 8 x `parse: line N: expected ')', found 'x'`
- 7 x `parse: line N: expected ']', found '.'`
- 5 x `parse: line N: expected '{', found 'if'`
- 5 x `parse: line N: comparisons do not chain`
- 5 x `parse: line N: expected 'else', found 'i'`
- 4 x `wf: unbound var False`
- 4 x `parse: line N: expected ')', found 'in'`
- 4 x `parse: line N: '*' does not start an expression`
- 4 x `parse: line N: expected 'eof', found 'spec'`
- 4 x `wf: vN expression form in a vN task`
- 4 x `parse: line N: expected ']', found ':'`
- 4 x `wf: unbound var nil`
- 3 x `parse: line N: expected 'else', found 'j'`
- 3 x `wf: call of unknown fun sqrt`
- 3 x `wf: unbound var null`
- 3 x `wf: call of unknown fun str`

## The problem's own tests (interp on the MBPP assertions)

| outcome | tasks |
|---|---:|
| pass | 22 |
| fail | 44 |

## The seven kernels (real / twin), over the well-formed tasks

| kernel | verified / refuted | of tasks |
|---|---:|---:|
| dafny | 39 | 66 |
| verus | 39 | 66 |
| spark | 34 | 66 |
| framac | 39 | 66 |
| lean | 36 | 66 |
| rocq | 39 | 66 |
| fstar | 11 | 66 |

| columns counting | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|---|
| tasks | 3 | 36 | 0 | 0 | 0 | 0 | 0 | 27 |

Tasks with no twin at all (every mutation on the ladder computes what the real body computes, or no input satisfies requires): 2.

## 12.6's table: verifies with a refuted twin, against passes its tests

| verifies with refuted twin in | tests pass | tests fail | requires-excluded | undefined | signature |
|---|---:|---:|---:|---:|---:|
| all seven | 2 | 1 | 0 | 0 | 0 |
| some column | 17 | 19 | 0 | 0 | 0 |
| none | 3 | 24 | 0 | 0 | 0 |

**2 of 368 problems** got a task that verifies with a refuted twin in all seven columns and passes its tests; 19 in at least one column. Verified-with-twin but failing its tests, the class 12.6 warns about: 1 in all seven, 19 in some column.

MBPP-DFY subset: 67 pool problems are MBPP-DFY problems (ROADMAP 16.2's family); 18 of them reached the kernels and 1 verify in all seven and pass their tests.

## Every task

| task_id | task | columns counting | tests | dafny | verus | spark | framac | lean | rocq | fstar |
|---:|---|---:|---|---|---|---|---|---|---|---|
| 14 | mbpp_14__find_Volume | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 17 | mbpp_17__square_perimeter | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 22 | mbpp_22__find_first_duplicate | 0 | fail | unproved / unproved | malformed / malformed | unproved / unproved | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 35 | mbpp_35__find_rect_num | 6 | fail | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 47 | mbpp_47__compute_Last_Digit | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 52 | mbpp_52__parallelogram_area | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 58 | mbpp_58__opposite_Signs | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 59 | mbpp_59__is_octagonal | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 76 | mbpp_76__count_Squares | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 86 | mbpp_86__centered_hexagonal_number | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 89 | mbpp_89__closest_num | 0 | fail | unproved / unproved | unproved / unproved | unproved / unproved | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 112 | mbpp_112__perimeter | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 122 | mbpp_122__smartNumber | 6 | fail | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 135 | mbpp_135__hexagonal_num | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 176 | mbpp_176__perimeter_triangle | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 190 | mbpp_190__count_Intgral_Points | 0 | fail | unproved / unproved | unproved / unproved | unproved / unproved | timeout / timeout | abstain / abstain | abstain / abstain | abstain / abstain |
| 212 | mbpp_212__fourth_Power_Sum | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 236 | mbpp_236__No_of_Triangle | 0 | fail | unproved / refuted | unproved / refuted | refuted / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 244 | mbpp_244__next_Perfect_Square | 0 | fail | unproved / unproved | malformed / malformed | timeout / timeout | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 264 | mbpp_264__dog_age | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 268 | mbpp_268__find_star_num | 6 | fail | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 279 | mbpp_279__is_num_decagonal | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 287 | mbpp_287__square_Sum | 6 | fail | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 288 | mbpp_288__modular_inverse | 6 | fail | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 320 | mbpp_320__sum_difference | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 335 | mbpp_335__ap_sum | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 347 | mbpp_347__count_Squares | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 354 | mbpp_354__tn_ap | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 355 | mbpp_355__count_Rectangles | 0 | fail | malformed / malformed | malformed / malformed | malformed / malformed | malformed / malformed | unproved / unproved | malformed / malformed | malformed / malformed |
| 356 | mbpp_356__find_angle | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 369 | mbpp_369__lateralsurface_cuboid | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 373 | mbpp_373__volume_cuboid | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 375 | mbpp_375__round_num | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 379 | mbpp_379__surfacearea_cuboid | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 420 | mbpp_420__cube_Sum | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 458 | mbpp_458__rectangle_area | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 479 | mbpp_479__first_Digit | 0 | pass | unproved / refuted | unproved / refuted | unproved / unproved | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 483 | mbpp_483__first_Factorial_Divisible_Number | 0 | fail | unproved / unproved | unproved / unproved | unproved / unproved | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 499 | mbpp_499__diameter_circle | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 502 | mbpp_502__find | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 504 | mbpp_504__sum_Of_Series | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 555 | mbpp_555__difference | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 566 | mbpp_566__sum_digits | 0 | fail | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 577 | mbpp_577__last_Digit_Factorial | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 592 | mbpp_592__sum_Of_product | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 637 | mbpp_637__noprofit_noloss | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted |
| 641 | mbpp_641__is_nonagonal | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 654 | mbpp_654__rectangle_perimeter | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 663 | mbpp_663__find_max_val | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 664 | mbpp_664__average_Even | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 675 | mbpp_675__sum_nums | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 692 | mbpp_692__last_Two_Digits | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 716 | mbpp_716__rombus_perimeter | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 765 | mbpp_765__is_polite | 0 | fail | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 768 | mbpp_768__check_Odd_Parity | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted |
| 784 | mbpp_784__mul_even_odd | 0 | fail | unproved / refuted | unproved / refuted | abstain / abstain | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| 789 | mbpp_789__perimeter_polygon | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 793 | mbpp_793__last | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 814 | mbpp_814__rombus_area | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 848 | mbpp_848__area_trapezium | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 855 | mbpp_855__check_Even_Parity | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted |
| 882 | mbpp_882__parallelogram_perimeter | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 901 | mbpp_901__smallest_multiple | 0 | fail | unproved / unproved | unproved / unproved | timeout / unproved | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 905 | mbpp_905__sum_of_square | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 931 | mbpp_931__sum_series | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 935 | mbpp_935__series_sum | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |

## Problems that produced no graded task

| task_id | fn | stage | why |
|---:|---|---|---|
| 3 | is_not_prime | wf | unbound var False; == wants two ints, two bools or two seqs; unbound var True; == wants two ints, two bools or two seqs; |
| 5 | count_ways | wf | call of unknown fun mbpp_5__count_ways; call of unknown fun mbpp_5__count_ways; + over non-int; ensures references the t |
| 6 | differ_At_One_Bit_Pos | parse | line 6: unexpected character '^' |
| 19 | test_duplicate | wf | unbound var False; == wants two ints, two bools or two seqs; unbound var True; == wants two ints, two bools or two seqs; |
| 20 | is_woodall | parse | line 5: '/' does not start an expression |
| 24 | binary_to_decimal | parse | line 5: '[' does not start an expression |
| 25 | find_Product | parse | line 8: expected '=', found '.' |
| 28 | binomial_Coeff | parse | line 14: expected '{', found 'if' |
| 29 | get_Odd_Occurrence | wf | task decreases without a self-call |
| 32 | max_Prime_Factors | parse | line 26: expected 'else', found '}' |
| 33 | decimal_To_Binary | parse | line 7: unexpected character '"' |
| 34 | find_missing | parse | line 4: expected '{', found '.' |
| 36 | find_Nth_Digit | parse | line 18: '/' does not start an expression |
| 38 | div_even_odd | parse | line 9: unexpected character '&' |
| 42 | find_Sum | parse | line 5: expected ']', found '.' |
| 45 | get_gcd | parse | line 4: expected '{', found '.' |
| 46 | test_distinct | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 48 | odd_bit_set_number | parse | line 5: unexpected character '/' |
| 51 | check_equilateral | wf | unbound var False; assign r: None into bool; unbound var True; assign r: None into bool |
| 55 | tn_gp | parse | line 6: unexpected character '^' |
| 56 | check | parse | line 16: expected ':=', found '10' |
| 57 | find_Max_Num | parse | line 29: expected 'else', found 'j' |
| 60 | max_len_sub | parse | line 5: expected ')', found 'for' |
| 62 | smallest_num | parse | line 4: '[' does not start an expression |
| 66 | pos_count | parse | line 5: '[' does not start an expression |
| 67 | bell_number | parse | line 9: expected ')', found 'for' |
| 68 | is_Monotonic | parse | line 5: expected ')', found 'x' |
| 69 | is_sublist | parse | line 12: expected ')', found 'invariant' |
| 72 | dif_Square | wf | call of unknown fun sqrt; mod over non-int; call of unknown fun sqrt; mod over non-int |
| 77 | is_Diff | parse | line 5: comparisons do not chain; parenthesise |
| 78 | count_With_Odd_SetBits | parse | line 9: expected ')', found 'div' |
| 84 | sequence | wf | call of unknown fun mbpp_84__sequence; call of unknown fun mbpp_84__sequence; + over non-int; call of unknown fun mbpp_8 |
| 93 | power | parse | line 6: unexpected character '^' |
| 96 | divisor | parse | line 9: '/' does not start an expression |
| 100 | next_smallest_palindrome | parse | line 17: expected ':=', found '+' |
| 101 | kth_element | parse | line 4: unexpected character '&' |
| 103 | eulerian_num | parse | line 13: expected '{', found 'if' |
| 107 | count_Hexadecimal | wf | task decreases without a self-call |
| 119 | search | parse | line 4: expected '{', found '.' |
| 121 | check_triplet | parse | line 14: unexpected character '&' |
| 123 | amicable_numbers_sum | parse | line 17: expected 'else', found 'i' |
| 126 | sum | wf | task decreases without a self-call |
| 127 | multiply_int | wf | call of unknown fun mbpp_127__multiply_int; + over non-int |
| 133 | sum_negativenum | parse | line 5: expected ')', found 'x' |
| 138 | is_Sum_Of_Powers_Of_Two | parse | line 5: unexpected character '/' |
| 142 | count_samepair | parse | line 4: unexpected character '&' |
| 144 | sum_Pairs | parse | line 5: expected ')', found 'for' |
| 148 | sum_digits_twoparts | wf | call of unknown fun sum_digits; == wants two ints, two bools or two seqs; assign to n, not a return or local; assign to  |
| 149 | longest_subseq_with_diff_one | parse | line 16: '[' does not start an expression |
| 150 | does_Contain_B | parse | line 4: expected ')', found 'in' |
| 151 | is_coprime | wf | task decreases without a self-call; assign r: int into bool; assign r: int into bool; assign r: int into bool; assign r: |
| 155 | even_bit_toggle_number | parse | line 14: unexpected character '&' |
| 158 | min_Ops | parse | line 4: expected '{', found '.' |
| 162 | sum_series | wf | call of unknown fun sum_of_positive_integers; == wants two ints, two bools or two seqs; call of unknown fun sum_of_posit |
| 164 | areEquivalent | parse | line 18: expected 'else', found 'i' |
| 166 | find_even_Pair | parse | line 5: unexpected character '^' |
| 167 | next_Power_Of_2 | parse | line 5: unexpected character '^' |
| 168 | frequency | parse | line 10: expected ']', found '.' |
| 169 | get_pell | wf | task decreases without a self-call |
| 170 | sum_range_list | parse | line 5: expected ']', found '.' |
| 171 | perimeter_pentagon | wf | local perimeter shadows a name in scope |
| 179 | is_num_keith | parse | line 7: expected ':=', found '=' |
| 183 | count_pairs | parse | line 11: unexpected character '&' |
| 184 | greater_specificnum | parse | line 11: unexpected character '&' |
| 188 | prod_Square | parse | line 5: comparisons do not chain; parenthesise |
| 189 | first_Missing_Positive | parse | line 21: expected ':=', found '[' |
| 194 | octal_To_Decimal | parse | line 6: 'int' does not start an expression |
| 195 | first | wf | unbound var null; != wants two ints, two bools or two seqs |
| 199 | highest_Power_of_2 | parse | line 10: unexpected character '^' |
| 203 | hamming_Distance | parse | line 6: unexpected character '^' |
| 211 | count_Num | parse | line 5: expected ')', found 'for' |
| 218 | min_Operations | wf | task decreases without a self-call |
| 221 | first_even | parse | line 4: '[' does not start an expression |
| 223 | is_majority | parse | line 5: '/' does not start an expression |
| 224 | count_Set_Bits | parse | line 5: unexpected character '&' |
| 225 | find_Min | parse | line 12: '/' does not start an expression |
| 227 | min_of_three | parse | line 5: unexpected character '&' |
| 228 | all_Bits_Set_In_The_Given_Range | parse | line 7: comparisons do not chain; parenthesise |
| 234 | volume_cube | parse | line 5: unexpected character '^' |
| 235 | even_bit_set_number | parse | line 5: unexpected character '/' |
| 239 | get_total_number_of_sequences | parse | line 18: unexpected character '&' |
| 245 | max_sum | parse | line 5: expected ']', found '.' |
| 256 | count_Primes_nums | parse | line 5: '[' does not start an expression |
| 258 | count_odd | parse | line 5: expected ')', found 'x' |
| 260 | newman_prime | parse | line 9: expected 'else', found 'end of input' |
| 266 | lateralsurface_cube | parse | line 5: unexpected character '^' |
| 267 | square_Sum | parse | line 5: '/' does not start an expression |
| 270 | sum_even_and_even_index | parse | line 5: expected ')', found 'for' |
| 271 | even_Power_Sum | parse | line 5: '*' does not start an expression |
| 274 | even_binomial_Coeff_Sum | parse | line 5: expected ')', found 'for' |
| 275 | get_Position | parse | line 7: unexpected character '&' |
| 281 | all_unique | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 283 | validate | parse | line 5: expected ')', found ']' |
| 286 | max_sub_array_sum_repeated | parse | line 4: unexpected character '&' |
| 289 | odd_Days | parse | line 5: '/' does not start an expression |
| 291 | count_no_of_ways | parse | line 11: expected 'eof', found 'spec' |
| 292 | find | parse | line 6: '/' does not start an expression |
| 295 | sum_div | wf | task decreases without a self-call |
| 296 | get_Inv_Count | parse | line 5: expected ')', found 'for' |
| 302 | set_Bit_Number | parse | line 6: unexpected character '^' |
| 303 | solve | parse | line 7: expected 'id', found 'len' |
| 306 | max_sum_increasing_subseq | parse | line 5: expected ')', found 'for' |
| 309 | maximum | wf | v1 expression form in a v0 task; call of unknown fun max; == wants two ints, two bools or two seqs |
| 311 | set_left_most_unset_bit | parse | line 5: unexpected character '/' |
| 313 | pos_nos | parse | line 9: '[' does not start an expression |
| 316 | find_last_occurrence | parse | line 4: expected '{', found '.' |
| 318 | max_volume | parse | line 4: expected '{', found '.' |
| 325 | get_Min_Squares | wf | call of unknown fun min_squares; == wants two ints, two bools or two seqs |
| 327 | check_isosceles | wf | unbound var True; assign r: None into bool; unbound var True; assign r: None into bool; unbound var True; assign r: None |
| 329 | neg_count | parse | line 5: expected ')', found 'x' |
| 331 | count_unset_bits | parse | line 5: unexpected character '&' |
| 334 | check_Validity | wf | unbound var False; assign r: None into bool; unbound var True; assign r: None into bool |
| 339 | find_Divisor | wf | unbound var max_divisor; == wants two ints, two bools or two seqs; task decreases without a self-call |
| 340 | sum_three_smallest_nums | parse | line 4: expected '{', found '.' |
| 344 | count_Odd_Squares | wf | task decreases without a self-call; unbound var a; == wants two ints, two bools or two seqs; unbound var b; == wants two |
| 346 | zigzag | wf | call of unknown fun mbpp_346__zigzag; call of unknown fun mbpp_346__zigzag; ite branches differ: int vs None; call of un |
| 348 | find_ways | parse | line 5: expected ')', found 'for' |
| 351 | first_Element | parse | line 6: expected '.', found ')' |
| 360 | get_carol | wf | task decreases without a self-call |
| 362 | max_occurrences | parse | line 23: expected 'else', found 'count' |
| 365 | count_Digit | wf | call of unknown fun str; len of a non-seq; call of unknown fun str; len of a non-seq; call of unknown fun str; len of a  |
| 366 | adjacent_num_product | parse | line 5: expected ')', found 'for' |
| 371 | smallest_missing | wf | unbound var x; != wants two ints, two bools or two seqs; unbound var x; != wants two ints, two bools or two seqs; unboun |
| 382 | find_rotation_count | parse | line 4: '[' does not start an expression |
| 383 | even_bit_toggle_number | parse | line 5: expected '{', found 'xor' |
| 384 | frequency_Of_Smallest | parse | line 5: expected ')', found 'x' |
| 385 | get_perrin | parse | line 13: expected 'else', found '{' |
| 388 | highest_Power_of_2 | parse | line 10: unexpected character '^' |
| 389 | find_lucas | wf | call of unknown fun mbpp_389__find_lucas; call of unknown fun mbpp_389__find_lucas; + over non-int; call of unknown fun  |
| 392 | get_max_sum | parse | line 17: expected 'else', found 'if' |
| 402 | ncr_modp | wf | arity mismatch calling ncr; task decreases without a self-call; arity mismatch calling ncr |
| 404 | minimum | wf | v1 expression form in a v0 task; call of unknown fun min; == wants two ints, two bools or two seqs |
| 407 | rearrange_bigger | parse | line 10: '[' does not start an expression |
| 414 | overlapping | parse | line 4: expected ')', found 'in' |
| 416 | breakSum | parse | line 5: '/' does not start an expression |
| 430 | parabola_directrix | parse | line 7: '*' does not start an expression |
| 435 | last_Digit | wf | operator 'mod' not in v0; == wants two ints, two bools or two seqs; operator 'mod' not in v0; assign r: None into int |
| 436 | neg_nos | wf | unbound var null; != wants two ints, two bools or two seqs |
| 439 | multiple_to_single | parse | line 10: expected ']', found ':' |
| 441 | surfacearea_cube | parse | line 5: unexpected character '^' |
| 443 | largest_neg | parse | line 4: '[' does not start an expression |
| 448 | cal_sum | parse | line 16: expected '{', found 'if' |
| 453 | sumofFactors | parse | line 5: '[' does not start an expression |
| 455 | check_monthnumb_number | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 463 | max_subarray_product | parse | line 9: expected ':', found ':=' |
| 466 | find_peak | parse | line 7: expected '{', found 'where' |
| 467 | decimal_to_Octal | parse | line 11: unexpected character '^' |
| 468 | max_product | parse | line 4: expected '{', found '.' |
| 469 | max_profit | parse | line 4: expected '{', found '.' |
| 471 | find_remainder | parse | line 5: '.' does not start an expression |
| 472 | check_Consecutive | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 476 | big_sum | parse | line 20: expected 'else', found 'if' |
| 481 | is_subset_sum | parse | line 5: 'exists' does not start an expression |
| 485 | largest_palindrome | parse | line 10: expected 'eof', found 'spec' |
| 489 | frequency_Of_Largest | parse | line 5: expected ')', found 'x' |
| 491 | sum_gp | parse | line 5: unexpected character '^' |
| 492 | binary_search | parse | line 4: expected '{', found '.' |
| 498 | gcd | wf | task decreases without a self-call |
| 501 | num_comm_div | wf | task decreases without a self-call |
| 506 | permutation_coefficient | parse | line 6: unexpected character '!' |
| 509 | average_Odd | wf | task decreases without a self-call |
| 510 | no_of_subsequences | parse | line 4: expected '{', found '.' |
| 511 | find_Min_Sum | parse | line 5: '[' does not start an expression |
| 515 | modular_sum | parse | line 17: unexpected character '/' |
| 517 | largest_pos | parse | line 4: '[' does not start an expression |
| 518 | sqrt_root | parse | line 9: expected ')', found 'div' |
| 520 | get_lcm | parse | line 4: expected '{', found '.' |
| 521 | check_isosceles | wf | unbound var True; assign r: None into bool; unbound var True; assign r: None into bool; unbound var True; assign r: None |
| 522 | lbs | parse | line 18: unexpected character '/' |
| 524 | max_sum_increasing_subsequence | parse | line 5: expected ']', found '.' |
| 525 | parallel_lines | parse | line 5: comparisons do not chain; parenthesise |
| 527 | get_pairs_count | parse | line 4: expected 'returns', found 'requires' |
| 529 | jacobsthal_lucas | wf | call of unknown fun mbpp_529__jacobsthal_lucas; == wants two ints, two bools or two seqs; ensures references the task na |
| 531 | min_coins | wf | call of unknown fun mbpp_531__min_coins; == wants two ints, two bools or two seqs; ensures references the task name (SPE |
| 540 | find_Diff | parse | line 8: '[' does not start an expression |
| 541 | check_abundant | parse | line 18: expected 'else', found 'i' |
| 543 | count_digits | wf | call of unknown fun mbpp_543__count_digits; == wants two ints, two bools or two seqs; ensures references the task name ( |
| 545 | toggle_F_and_L_bits | parse | line 5: expected '{', found 'xor' |
| 547 | Total_Hamming_Distance | parse | line 5: expected ')', found 'for' |
| 548 | longest_increasing_subsequence | parse | line 20: expected 'id', found 't' |
| 549 | odd_Num_Sum | parse | line 5: '*' does not start an expression |
| 550 | find_Max | parse | line 13: '/' does not start an expression |
| 556 | find_Odd_Pair | parse | line 14: unexpected character '^' |
| 558 | digit_distance_nums | wf | call of unknown fun abs; == wants two ints, two bools or two seqs; call of unknown fun abs; assign r: None into int |
| 559 | max_sub_array_sum | parse | line 4: expected '{', found '.' |
| 564 | count_Pairs | parse | line 26: expected 'else', found 'j' |
| 567 | issort_list | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 571 | max_sum_pair_diff_lessthan_K | parse | line 4: expected '{', found '.' |
| 573 | unique_product | parse | line 14: unexpected character '!' |
| 575 | count_no | wf | unbound var n; + over non-int; unbound var n; call of unknown fun mbpp_575__count_no; call of unknown fun mbpp_575__coun |
| 576 | is_Sub_Array | parse | line 5: comparisons do not chain; parenthesise |
| 581 | surface_Area | parse | line 6: unexpected character '^' |
| 583 | catalan_number | wf | task decreases without a self-call |
| 588 | big_diff | wf | unbound var null; != wants two ints, two bools or two seqs; call of unknown fun max; call of unknown fun min; - over non |
| 594 | diff_even_odd | parse | line 13: '[' does not start an expression |
| 597 | find_kth | parse | line 4: unexpected character '&' |
| 598 | armstrong_number | parse | line 5: unexpected character '^' |
| 600 | is_Even | parse | line 4: unexpected character '&' |
| 605 | prime_num | parse | line 5: unexpected character '&' |
| 608 | bell_Number | parse | line 9: expected ')', found 'for' |
| 609 | floor_Min | wf | call of unknown fun min; == wants two ints, two bools or two seqs |
| 620 | largest_subset | parse | line 4: expected '{', found '.' |
| 626 | triangle_area | parse | line 5: unexpected character '^' |
| 627 | find_First_Missing | wf | bound var i shadows a name in scope |
| 633 | pair_OR_Sum | parse | line 9: unexpected character '^' |
| 634 | even_Power_Sum | parse | line 5: unexpected character '^' |
| 638 | wind_chill | parse | line 6: unexpected character '^' |
| 646 | No_of_cubes | parse | line 6: unexpected character '^' |
| 649 | sum_Range_list | parse | line 5: expected ']', found ':' |
| 650 | are_Equal | parse | line 17: expected 'else', found 'i' |
| 655 | fifth_Power_Sum | parse | line 5: '/' does not start an expression |
| 656 | find_Min_Sum | parse | line 5: expected ')', found 'for' |
| 657 | first_Digit | parse | line 16: '/' does not start an expression |
| 658 | max_occurrences | parse | line 25: expected 'else', found 'current_count' |
| 661 | max_sum_of_three_consecutive | parse | line 5: expected ']', found '.' |
| 670 | decreasing_trend | parse | line 4: expected '{', found '.' |
| 671 | set_Right_most_Unset_Bit | parse | line 5: unexpected character '/' |
| 672 | max_of_three | parse | line 13: expected '{', found 'if' |
| 673 | convert | parse | line 3: expected 'id', found 'seq' |
| 677 | validity_triangle | parse | line 5: unexpected character '&' |
| 680 | increasing_trend | parse | line 4: expected '{', found '.' |
| 681 | smallest_Divisor | parse | line 15: expected ':=', found ';' |
| 683 | sum_Square | wf | call of unknown fun sqrt; call of unknown fun sqrt; * over non-int; unbound var False; assign r: None into bool; unbound |
| 685 | sum_Of_Primes | parse | line 22: unexpected character '?' |
| 687 | recur_gcd | wf | task decreases without a self-call |
| 689 | min_jumps | parse | line 4: expected '{', found '.' |
| 697 | count_even | parse | line 5: expected ')', found 'x' |
| 701 | equilibrium_index | parse | line 5: expected ']', found ':' |
| 702 | removals | parse | line 4: expected '{', found '.' |
| 706 | is_subset | parse | line 5: expected ')', found 'in' |
| 707 | count_Set_Bits | parse | line 5: unexpected character "'" |
| 711 | product_Equal | parse | line 17: 'int' does not start an expression |
| 714 | count_Fac | parse | line 7: 'seq' is not one of int bool |
| 723 | count_same_pair | parse | line 4: expected '{', found '.' |
| 724 | power_base_sum | parse | line 6: unexpected character '^' |
| 733 | find_first_occurrence | parse | line 4: expected '{', found '.' |
| 734 | sum_Of_Subarray_Prod | parse | line 5: expected ')', found 'for' |
| 735 | toggle_middle_bits | parse | line 10: unexpected character '^' |
| 736 | left_insertion | wf | unbound var nil; != wants two ints, two bools or two seqs |
| 739 | find_Index | parse | line 5: '[' does not start an expression |
| 751 | check_min_heap | parse | line 5: unexpected character '&' |
| 752 | jacobsthal_num | wf | task decreases without a self-call |
| 762 | check_monthnumber_number | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 767 | get_Pairs_Count | wf | assign to count, not a return or local |
| 770 | odd_Num_Sum | parse | line 5: '*' does not start an expression |
| 775 | odd_position | parse | line 5: expected ')', found 'for' |
| 777 | find_Sum | parse | line 9: expected ']', found '.' |
| 782 | Odd_Length_Sum | parse | line 5: expected ')', found 'for' |
| 786 | right_insertion | wf | unbound var nil; != wants two ints, two bools or two seqs |
| 790 | even_position | parse | line 5: expected ')', found 'in' |
| 797 | sum_in_Range | parse | line 6: '[' does not start an expression |
| 798 | _sum | parse | line 3: unexpected character '_' |
| 799 | left_Rotate | parse | line 6: unexpected character '/' |
| 801 | test_three_equal | parse | line 8: unexpected character '&' |
| 802 | count_Rotation | parse | line 4: expected '{', found '.' |
| 803 | is_Perfect_Square | wf | call of unknown fun sqrt; call of unknown fun sqrt; * over non-int; unbound var False; assign r: None into bool; unbound |
| 804 | is_Product_Even | parse | line 3: expected 'id', found 'seq' |
| 807 | first_odd | parse | line 4: '[' does not start an expression |
| 820 | check_monthnum_number | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 831 | count_Pairs | parse | line 5: expected ')', found 'for' |
| 836 | max_sub_array_sum | parse | line 5: expected ']', found ':' |
| 837 | cube_Sum | parse | line 5: '/' does not start an expression |
| 841 | get_inv_count | parse | line 26: expected 'else', found 'j' |
| 842 | get_odd_occurence | parse | line 29: expected 'eof', found 'spec' |
| 843 | nth_super_ugly_number | parse | line 5: expected '{', found '.' |
| 844 | get_Number | parse | line 6: '/' does not start an expression |
| 845 | find_Digits | wf | call of unknown fun str; len of a non-seq; call of unknown fun str; len of a non-seq |
| 846 | find_platform | parse | line 3: expected 'id', found 't' |
| 849 | Sum | parse | line 9: '/' does not start an expression |
| 850 | is_triangleexists | parse | line 5: unexpected character '&' |
| 853 | sum_of_odd_Factors | parse | line 5: '[' does not start an expression |
| 856 | find_Min_Swaps | parse | line 16: expected ':=', found '(' |
| 863 | find_longest_conseq_subseq | parse | line 7: '[' does not start an expression |
| 867 | min_Num | wf | call of unknown fun sum; mod over non-int |
| 870 | sum_positivenum | parse | line 5: expected ')', found 'x' |
| 873 | fibonacci | wf | call of unknown fun mbpp_873__fibonacci; call of unknown fun mbpp_873__fibonacci; + over non-int; call of unknown fun mb |
| 876 | lcm | parse | line 10: '/' does not start an expression |
| 881 | sum_even_odd | wf | unbound var nil; != wants two ints, two bools or two seqs; call of unknown fun sum; call of unknown fun sum; + over non- |
| 884 | all_Bits_Set_In_The_Given_Range | parse | line 7: unexpected character '&' |
| 887 | is_odd | parse | line 4: unexpected character '&' |
| 890 | find_Extra | parse | line 5: unexpected character '/' |
| 891 | same_Length | wf | call of unknown fun str; len of a non-seq; call of unknown fun str; len of a non-seq; call of unknown fun str; len of a  |
| 895 | max_sum_subseq | wf | unbound var nil; != wants two ints, two bools or two seqs; call of unknown fun sum; == wants two ints, two bools or two  |
| 899 | check | parse | line 16: expected ':=', found ';' |
| 903 | count_Unset_Bits | parse | line 5: unexpected character '&' |
| 908 | find_fixed_point | parse | line 4: expected '{', found '.' |
| 909 | previous_palindrome | parse | line 14: ':' does not start an expression |
| 911 | maximum_product | parse | line 4: expected '{', found '.' |
| 918 | coin_change | parse | line 25: expected 'eof', found 'spec' |
| 919 | multiply_list | parse | line 9: expected 'then', found '.' |
| 924 | max_of_two | wf | v1 expression form in a v0 task; call of unknown fun max; == wants two ints, two bools or two seqs |
| 926 | rencontres_number | parse | line 13: expected '{', found 'if' |
| 934 | dealnnoy_num | wf | task decreases without a self-call |
| 952 | nCr_mod_p | wf | unbound var p; mod over non-int; task decreases without a self-call |
| 953 | subset | parse | line 7: expected 'id', found 'seq' |
| 955 | is_abundant | parse | line 18: expected 'else', found 'i' |
| 957 | get_First_Set_Bit_Pos | parse | line 17: expected 'else', found 'n' |
| 960 | get_noOfways | wf | call of unknown fun mbpp_960__get_noOfways; call of unknown fun mbpp_960__get_noOfways; + over non-int; ensures referenc |
| 962 | sum_Even | parse | line 6: '[' does not start an expression |
| 968 | floor_Max | wf | task decreases without a self-call |
| 970 | min_of_two | wf | v1 expression form in a v0 task; call of unknown fun min; == wants two ints, two bools or two seqs |
| 971 | maximum_segments | wf | task decreases without a self-call |

