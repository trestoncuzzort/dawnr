# The spec experiment on MBPP: qwen3.8-27b-fp8-np1024

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
| replies with a t block | 86 |
| blocks that parse | 37 |
| tasks that are well-formed (graded below) | 32 |

Refusals, by named reason:

- 31 x `parse: <string>:N:N: unexpected character '?' [Id]`
- 4 x `parse: <string>:N:N: expected '{', found 'end of input' [Stmt]`
- 4 x `wf: bool literal in a vN task [SPEC: the bool literal is a vN construct (G`
- 2 x `parse: <string>:N:N: 'end of input' does not start an expression [Expr]`
- 2 x `parse: <string>:N:N: unterminated block [Stmt]`
- 2 x `parse: <string>:N:N: unexpected character '`' [Id]`
- 1 x `parse: <string>:N:N: a char literal holds exactly one code point, found N [St`
- 1 x `parse: <string>:N:N: expected 'decreases', found 'end of input' [Stmt]`
- 1 x `parse: <string>:N:N: expected 'eof', found 'Need' [Task]`
- 1 x `parse: <string>:N:N: unexpected character '^' [Id]`
- 1 x `parse: <string>:N:N: expected 'task', found 'end of input' [Task]`
- 1 x `parse: <string>:N:N: 'if' does not start an expression [Expr]`
- 1 x `wf: vN expression form in a vN task [SPEC: ite/forall/exists/call are vN e`
- 1 x `parse: <string>:N:N: expected 'id', found 'end of input' [Task]`
- 1 x `parse: <string>:N:N: unterminated literal [Strings as sequences of code point`

## The problem's own tests (interp on the MBPP assertions)

| outcome | tasks |
|---|---:|
| pass | 31 |
| requires-excluded | 1 |

## The seven kernels (real / twin), over the well-formed tasks

| kernel | verified / refuted | of tasks |
|---|---:|---:|
| dafny | 30 | 32 |
| verus | 31 | 32 |
| spark | 30 | 32 |
| framac | 31 | 32 |
| lean | 30 | 32 |
| rocq | 30 | 32 |
| fstar | 30 | 32 |

| columns counting | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|---|
| tasks | 30 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |

Tasks with no twin at all (every mutation on the ladder computes what the real body computes, or no input satisfies requires): 0.

## 12.6's table: verifies with a refuted twin, against passes its tests

| verifies with refuted twin in | tests pass | tests fail | requires-excluded | undefined | signature |
|---|---:|---:|---:|---:|---:|
| all seven | 30 | 0 | 0 | 0 | 0 |
| some column | 1 | 0 | 0 | 0 | 0 |
| none | 0 | 0 | 1 | 0 | 0 |

**30 of 368 problems** got a task that verifies with a refuted twin in all seven columns and passes its tests; 31 in at least one column. Verified-with-twin but failing its tests, the class 12.6 warns about: 0 in all seven, 0 in some column.

MBPP-DFY subset: 67 pool problems are MBPP-DFY problems (ROADMAP 16.2's family); 13 of them reached the kernels and 12 verify in all seven and pass their tests.

## Every task

| task_id | task | columns counting | tests | dafny | verus | spark | framac | lean | rocq | fstar |
|---:|---|---:|---|---|---|---|---|---|---|---|
| 17 | mbpp_17__square_perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 35 | mbpp_35__find_rect_num | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 52 | mbpp_52__parallelogram_area | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 59 | mbpp_59__is_octagonal | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 86 | mbpp_86__centered_hexagonal_number | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 89 | mbpp_89__closest_num | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 112 | mbpp_112__perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 171 | mbpp_171__perimeter_pentagon | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 176 | mbpp_176__perimeter_triangle | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 225 | mbpp_225__find_Min | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 227 | mbpp_227__min_of_three | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 234 | mbpp_234__volume_cube | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 266 | mbpp_266__lateralsurface_cube | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 309 | mbpp_309__maximum | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 356 | mbpp_356__find_angle | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 369 | mbpp_369__lateralsurface_cuboid | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 373 | mbpp_373__volume_cuboid | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 379 | mbpp_379__surfacearea_cuboid | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 404 | mbpp_404__minimum | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 420 | mbpp_420__cube_Sum | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 441 | mbpp_441__surfacearea_cube | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 458 | mbpp_458__rectangle_area | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 499 | mbpp_499__diameter_circle | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 654 | mbpp_654__rectangle_perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 672 | mbpp_672__max_of_three | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 716 | mbpp_716__rombus_perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 789 | mbpp_789__perimeter_polygon | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 793 | mbpp_793__last | 0 | requires-excluded | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 870 | mbpp_870__sum_positivenum | 2 | pass | unproved / unproved | verified / refuted | unproved / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 882 | mbpp_882__parallelogram_perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 924 | mbpp_924__max_of_two | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 970 | mbpp_970__min_of_two | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

## Problems that produced no graded task

| task_id | fn | stage | why |
|---:|---|---|---|
| 3 | is_not_prime | no-block |  |
| 5 | count_ways | no-block |  |
| 6 | differ_At_One_Bit_Pos | no-block |  |
| 14 | find_Volume | no-block |  |
| 19 | test_duplicate | no-block |  |
| 20 | is_woodall | no-block |  |
| 22 | find_first_duplicate | no-block |  |
| 24 | binary_to_decimal | no-block |  |
| 25 | find_Product | no-block |  |
| 28 | binomial_Coeff | parse | <string>:21:73: unexpected character '?' [Id] |
| 29 | get_Odd_Occurrence | no-block |  |
| 32 | max_Prime_Factors | no-block |  |
| 33 | decimal_To_Binary | no-block |  |
| 34 | find_missing | no-block |  |
| 36 | find_Nth_Digit | no-block |  |
| 38 | div_even_odd | no-block |  |
| 42 | find_Sum | parse | <string>:5:49: unexpected character '?' [Id] |
| 45 | get_gcd | no-block |  |
| 46 | test_distinct | no-block |  |
| 47 | compute_Last_Digit | no-block |  |
| 48 | odd_bit_set_number | no-block |  |
| 51 | check_equilateral | no-block |  |
| 55 | tn_gp | parse | <string>:22:41: unexpected character '?' [Id] |
| 56 | check | parse | <string>:8:40: 'end of input' does not start an expression [Expr] |
| 57 | find_Max_Num | no-block |  |
| 58 | opposite_Signs | parse | <string>:16:135: unexpected character '?' [Id] |
| 60 | max_len_sub | no-block |  |
| 62 | smallest_num | parse | <string>:24:225: a char literal holds exactly one code point, found 25 [Strings as sequences of code points (v1)] |
| 66 | pos_count | no-block |  |
| 67 | bell_number | no-block |  |
| 68 | is_Monotonic | parse | <string>:28:376: unexpected character '?' [Id] |
| 69 | is_sublist | no-block |  |
| 72 | dif_Square | no-block |  |
| 76 | count_Squares | no-block |  |
| 77 | is_Diff | no-block |  |
| 78 | count_With_Odd_SetBits | no-block |  |
| 84 | sequence | no-block |  |
| 93 | power | no-block |  |
| 96 | divisor | no-block |  |
| 100 | next_smallest_palindrome | no-block |  |
| 101 | kth_element | no-block |  |
| 103 | eulerian_num | no-block |  |
| 107 | count_Hexadecimal | no-block |  |
| 119 | search | no-block |  |
| 121 | check_triplet | no-block |  |
| 122 | smartNumber | no-block |  |
| 123 | amicable_numbers_sum | no-block |  |
| 126 | sum | no-block |  |
| 127 | multiply_int | parse | <string>:9:48: unexpected character '?' [Id] |
| 133 | sum_negativenum | parse | <string>:12:1: expected 'decreases', found 'end of input' [Stmt] |
| 135 | hexagonal_num | no-block |  |
| 138 | is_Sum_Of_Powers_Of_Two | no-block |  |
| 142 | count_samepair | no-block |  |
| 144 | sum_Pairs | no-block |  |
| 148 | sum_digits_twoparts | no-block |  |
| 149 | longest_subseq_with_diff_one | no-block |  |
| 150 | does_Contain_B | no-block |  |
| 151 | is_coprime | no-block |  |
| 155 | even_bit_toggle_number | no-block |  |
| 158 | min_Ops | no-block |  |
| 162 | sum_series | no-block |  |
| 164 | areEquivalent | no-block |  |
| 166 | find_even_Pair | no-block |  |
| 167 | next_Power_Of_2 | parse | <string>:4:1: expected '{', found 'end of input' [Stmt] |
| 168 | frequency | no-block |  |
| 169 | get_pell | no-block |  |
| 170 | sum_range_list | no-block |  |
| 179 | is_num_keith | no-block |  |
| 183 | count_pairs | no-block |  |
| 184 | greater_specificnum | no-block |  |
| 188 | prod_Square | no-block |  |
| 189 | first_Missing_Positive | parse | <string>:16:66: unexpected character '?' [Id] |
| 190 | count_Intgral_Points | no-block |  |
| 194 | octal_To_Decimal | no-block |  |
| 195 | first | parse | <string>:14:14: 'end of input' does not start an expression [Expr] |
| 199 | highest_Power_of_2 | parse | <string>:7:24: unexpected character '?' [Id] |
| 203 | hamming_Distance | no-block |  |
| 211 | count_Num | no-block |  |
| 212 | fourth_Power_Sum | no-block |  |
| 218 | min_Operations | no-block |  |
| 221 | first_even | no-block |  |
| 223 | is_majority | no-block |  |
| 224 | count_Set_Bits | no-block |  |
| 228 | all_Bits_Set_In_The_Given_Range | no-block |  |
| 235 | even_bit_set_number | no-block |  |
| 236 | No_of_Triangle | no-block |  |
| 239 | get_total_number_of_sequences | no-block |  |
| 244 | next_Perfect_Square | no-block |  |
| 245 | max_sum | no-block |  |
| 256 | count_Primes_nums | no-block |  |
| 258 | count_odd | no-block |  |
| 260 | newman_prime | no-block |  |
| 264 | dog_age | no-block |  |
| 267 | square_Sum | no-block |  |
| 268 | find_star_num | no-block |  |
| 270 | sum_even_and_even_index | no-block |  |
| 271 | even_Power_Sum | no-block |  |
| 274 | even_binomial_Coeff_Sum | no-block |  |
| 275 | get_Position | no-block |  |
| 279 | is_num_decagonal | no-block |  |
| 281 | all_unique | no-block |  |
| 283 | validate | no-block |  |
| 286 | max_sub_array_sum_repeated | no-block |  |
| 287 | square_Sum | parse | <string>:4:18: expected '{', found 'end of input' [Stmt] |
| 288 | modular_inverse | no-block |  |
| 289 | odd_Days | no-block |  |
| 291 | count_no_of_ways | parse | <string>:16:61: unexpected character '?' [Id] |
| 292 | find | no-block |  |
| 295 | sum_div | no-block |  |
| 296 | get_Inv_Count | parse | <string>:6:23: unexpected character '?' [Id] |
| 302 | set_Bit_Number | no-block |  |
| 303 | solve | no-block |  |
| 306 | max_sum_increasing_subseq | no-block |  |
| 311 | set_left_most_unset_bit | no-block |  |
| 313 | pos_nos | no-block |  |
| 316 | find_last_occurrence | parse | <string>:26:45: unexpected character '?' [Id] |
| 318 | max_volume | no-block |  |
| 320 | sum_difference | no-block |  |
| 325 | get_Min_Squares | no-block |  |
| 327 | check_isosceles | parse | <string>:16:37: unexpected character '?' [Id] |
| 329 | neg_count | parse | <string>:4:23: unexpected character '?' [Id] |
| 331 | count_unset_bits | no-block |  |
| 334 | check_Validity | no-block |  |
| 335 | ap_sum | no-block |  |
| 339 | find_Divisor | no-block |  |
| 340 | sum_three_smallest_nums | no-block |  |
| 344 | count_Odd_Squares | no-block |  |
| 346 | zigzag | no-block |  |
| 347 | count_Squares | no-block |  |
| 348 | find_ways | no-block |  |
| 351 | first_Element | no-block |  |
| 354 | tn_ap | parse | <string>:8:14: unexpected character '?' [Id] |
| 355 | count_Rectangles | no-block |  |
| 360 | get_carol | no-block |  |
| 362 | max_occurrences | no-block |  |
| 365 | count_Digit | no-block |  |
| 366 | adjacent_num_product | no-block |  |
| 371 | smallest_missing | no-block |  |
| 375 | round_num | no-block |  |
| 382 | find_rotation_count | no-block |  |
| 383 | even_bit_toggle_number | no-block |  |
| 384 | frequency_Of_Smallest | parse | <string>:7:123: unexpected character '?' [Id] |
| 385 | get_perrin | no-block |  |
| 388 | highest_Power_of_2 | no-block |  |
| 389 | find_lucas | parse | <string>:35:48: unexpected character '?' [Id] |
| 392 | get_max_sum | no-block |  |
| 402 | ncr_modp | no-block |  |
| 407 | rearrange_bigger | no-block |  |
| 414 | overlapping | no-block |  |
| 416 | breakSum | no-block |  |
| 430 | parabola_directrix | no-block |  |
| 435 | last_Digit | no-block |  |
| 436 | neg_nos | no-block |  |
| 439 | multiple_to_single | no-block |  |
| 443 | largest_neg | parse | <string>:35:44: unexpected character '?' [Id] |
| 448 | cal_sum | no-block |  |
| 453 | sumofFactors | no-block |  |
| 455 | check_monthnumb_number | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 463 | max_subarray_product | no-block |  |
| 466 | find_peak | no-block |  |
| 467 | decimal_to_Octal | no-block |  |
| 468 | max_product | no-block |  |
| 469 | max_profit | no-block |  |
| 471 | find_remainder | no-block |  |
| 472 | check_Consecutive | parse | <string>:21:1: expected 'eof', found 'Need' [Task] |
| 476 | big_sum | no-block |  |
| 479 | first_Digit | no-block |  |
| 481 | is_subset_sum | no-block |  |
| 483 | first_Factorial_Divisible_Number | no-block |  |
| 485 | largest_palindrome | no-block |  |
| 489 | frequency_Of_Largest | parse | <string>:10:91: unexpected character '?' [Id] |
| 491 | sum_gp | parse | <string>:8:54: unexpected character '^' [Id] |
| 492 | binary_search | no-block |  |
| 498 | gcd | no-block |  |
| 501 | num_comm_div | parse | <string>:15:16: unterminated block [Stmt] |
| 502 | find | no-block |  |
| 504 | sum_Of_Series | parse | <string>:2:11: expected 'task', found 'end of input' [Task] |
| 506 | permutation_coefficient | no-block |  |
| 509 | average_Odd | no-block |  |
| 510 | no_of_subsequences | no-block |  |
| 511 | find_Min_Sum | no-block |  |
| 515 | modular_sum | no-block |  |
| 517 | largest_pos | no-block |  |
| 518 | sqrt_root | no-block |  |
| 520 | get_lcm | no-block |  |
| 521 | check_isosceles | parse | <string>:7:38: unexpected character '?' [Id] |
| 522 | lbs | no-block |  |
| 524 | max_sum_increasing_subsequence | no-block |  |
| 525 | parallel_lines | no-block |  |
| 527 | get_pairs_count | no-block |  |
| 529 | jacobsthal_lucas | no-block |  |
| 531 | min_coins | no-block |  |
| 540 | find_Diff | no-block |  |
| 541 | check_abundant | no-block |  |
| 543 | count_digits | parse | <string>:5:13: unexpected character '?' [Id] |
| 545 | toggle_F_and_L_bits | no-block |  |
| 547 | Total_Hamming_Distance | no-block |  |
| 548 | longest_increasing_subsequence | no-block |  |
| 549 | odd_Num_Sum | no-block |  |
| 550 | find_Max | no-block |  |
| 555 | difference | no-block |  |
| 556 | find_Odd_Pair | no-block |  |
| 558 | digit_distance_nums | no-block |  |
| 559 | max_sub_array_sum | no-block |  |
| 564 | count_Pairs | parse | <string>:4:1: expected '{', found 'end of input' [Stmt] |
| 566 | sum_digits | no-block |  |
| 567 | issort_list | parse | <string>:9:16: unexpected character '?' [Id] |
| 571 | max_sum_pair_diff_lessthan_K | no-block |  |
| 573 | unique_product | no-block |  |
| 575 | count_no | no-block |  |
| 576 | is_Sub_Array | no-block |  |
| 577 | last_Digit_Factorial | parse | <string>:4:16: 'if' does not start an expression [Expr] |
| 581 | surface_Area | no-block |  |
| 583 | catalan_number | no-block |  |
| 588 | big_diff | no-block |  |
| 592 | sum_Of_product | no-block |  |
| 594 | diff_even_odd | no-block |  |
| 597 | find_kth | no-block |  |
| 598 | armstrong_number | no-block |  |
| 600 | is_Even | no-block |  |
| 605 | prime_num | parse | <string>:31:41: unexpected character '?' [Id] |
| 608 | bell_Number | no-block |  |
| 609 | floor_Min | no-block |  |
| 620 | largest_subset | no-block |  |
| 626 | triangle_area | no-block |  |
| 627 | find_First_Missing | no-block |  |
| 633 | pair_OR_Sum | no-block |  |
| 634 | even_Power_Sum | no-block |  |
| 637 | noprofit_noloss | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 638 | wind_chill | no-block |  |
| 641 | is_nonagonal | no-block |  |
| 646 | No_of_cubes | no-block |  |
| 649 | sum_Range_list | no-block |  |
| 650 | are_Equal | no-block |  |
| 655 | fifth_Power_Sum | no-block |  |
| 656 | find_Min_Sum | no-block |  |
| 657 | first_Digit | no-block |  |
| 658 | max_occurrences | no-block |  |
| 661 | max_sum_of_three_consecutive | no-block |  |
| 663 | find_max_val | no-block |  |
| 664 | average_Even | no-block |  |
| 670 | decreasing_trend | no-block |  |
| 671 | set_Right_most_Unset_Bit | no-block |  |
| 673 | convert | no-block |  |
| 675 | sum_nums | wf | v1 expression form in a v0 task [SPEC: ite/forall/exists/call are v1 expression forms (v1: the three gates)] |
| 677 | validity_triangle | parse | <string>:8:89: unexpected character '`' [Id] |
| 680 | increasing_trend | no-block |  |
| 681 | smallest_Divisor | no-block |  |
| 683 | sum_Square | no-block |  |
| 685 | sum_Of_Primes | no-block |  |
| 687 | recur_gcd | no-block |  |
| 689 | min_jumps | no-block |  |
| 692 | last_Two_Digits | no-block |  |
| 697 | count_even | no-block |  |
| 701 | equilibrium_index | no-block |  |
| 702 | removals | no-block |  |
| 706 | is_subset | no-block |  |
| 707 | count_Set_Bits | no-block |  |
| 711 | product_Equal | no-block |  |
| 714 | count_Fac | no-block |  |
| 723 | count_same_pair | no-block |  |
| 724 | power_base_sum | no-block |  |
| 733 | find_first_occurrence | parse | <string>:23:357: unexpected character '?' [Id] |
| 734 | sum_Of_Subarray_Prod | no-block |  |
| 735 | toggle_middle_bits | no-block |  |
| 736 | left_insertion | parse | <string>:11:2: unterminated block [Stmt] |
| 739 | find_Index | no-block |  |
| 751 | check_min_heap | no-block |  |
| 752 | jacobsthal_num | parse | <string>:24:48: unexpected character '?' [Id] |
| 762 | check_monthnumber_number | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 765 | is_polite | no-block |  |
| 767 | get_Pairs_Count | parse | <string>:6:12: expected '{', found 'end of input' [Stmt] |
| 768 | check_Odd_Parity | no-block |  |
| 770 | odd_Num_Sum | no-block |  |
| 775 | odd_position | no-block |  |
| 777 | find_Sum | no-block |  |
| 782 | Odd_Length_Sum | no-block |  |
| 784 | mul_even_odd | parse | <string>:4:12: unexpected character '?' [Id] |
| 786 | right_insertion | no-block |  |
| 790 | even_position | parse | <string>:2:11: unexpected character '?' [Id] |
| 797 | sum_in_Range | no-block |  |
| 798 | _sum | no-block |  |
| 799 | left_Rotate | parse | <string>:23:60: unexpected character '?' [Id] |
| 801 | test_three_equal | parse | <string>:18:88: unexpected character '`' [Id] |
| 802 | count_Rotation | no-block |  |
| 803 | is_Perfect_Square | parse | <string>:4:50: unexpected character '?' [Id] |
| 804 | is_Product_Even | no-block |  |
| 807 | first_odd | parse | <string>:2:5: expected 'id', found 'end of input' [Task] |
| 814 | rombus_area | no-block |  |
| 820 | check_monthnum_number | no-block |  |
| 831 | count_Pairs | no-block |  |
| 836 | max_sub_array_sum | no-block |  |
| 837 | cube_Sum | parse | <string>:10:70: unexpected character '?' [Id] |
| 841 | get_inv_count | no-block |  |
| 842 | get_odd_occurence | no-block |  |
| 843 | nth_super_ugly_number | no-block |  |
| 844 | get_Number | no-block |  |
| 845 | find_Digits | no-block |  |
| 846 | find_platform | no-block |  |
| 848 | area_trapezium | no-block |  |
| 849 | Sum | no-block |  |
| 850 | is_triangleexists | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 853 | sum_of_odd_Factors | no-block |  |
| 855 | check_Even_Parity | no-block |  |
| 856 | find_Min_Swaps | no-block |  |
| 863 | find_longest_conseq_subseq | no-block |  |
| 867 | min_Num | no-block |  |
| 873 | fibonacci | parse | <string>:22:17: unexpected character '?' [Id] |
| 876 | lcm | parse | <string>:7:14: unexpected character '?' [Id] |
| 881 | sum_even_odd | no-block |  |
| 884 | all_Bits_Set_In_The_Given_Range | no-block |  |
| 887 | is_odd | no-block |  |
| 890 | find_Extra | no-block |  |
| 891 | same_Length | no-block |  |
| 895 | max_sum_subseq | no-block |  |
| 899 | check | no-block |  |
| 901 | smallest_multiple | no-block |  |
| 903 | count_Unset_Bits | no-block |  |
| 905 | sum_of_square | no-block |  |
| 908 | find_fixed_point | no-block |  |
| 909 | previous_palindrome | no-block |  |
| 911 | maximum_product | no-block |  |
| 918 | coin_change | no-block |  |
| 919 | multiply_list | parse | <string>:21:597: unterminated literal [Strings as sequences of code points (v1)] |
| 926 | rencontres_number | no-block |  |
| 931 | sum_series | no-block |  |
| 934 | dealnnoy_num | no-block |  |
| 935 | series_sum | no-block |  |
| 952 | nCr_mod_p | no-block |  |
| 953 | subset | no-block |  |
| 955 | is_abundant | no-block |  |
| 957 | get_First_Set_Bit_Pos | no-block |  |
| 960 | get_noOfways | no-block |  |
| 962 | sum_Even | no-block |  |
| 968 | floor_Max | no-block |  |
| 971 | maximum_segments | no-block |  |

