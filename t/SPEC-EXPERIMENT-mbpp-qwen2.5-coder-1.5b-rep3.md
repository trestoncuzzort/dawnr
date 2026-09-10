# The spec experiment on MBPP: qwen2.5-coder-1.5b-rep3

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
| replies recorded | 161 |
| replies with a t block | 161 |
| blocks that parse | 52 |
| tasks that are well-formed (graded below) | 28 |

Refusals, by named reason:

- 16 x `parse: line N: expected 'nat', found 'length'`
- 10 x `parse: line N: unexpected character '&'`
- 9 x `parse: line N: unexpected character '^'`
- 9 x `parse: line N: '/' does not start an expression`
- 9 x `parse: line N: expected ')', found 'for'`
- 4 x `parse: line N: 'int' does not start an expression`
- 4 x `parse: line N: expected ']', found 'for'`
- 4 x `parse: line N: expected ')', found 'x'`
- 4 x `wf: task decreases without a self-call`
- 3 x `parse: line N: expected '{', found 'if'`
- 3 x `parse: line N: unexpected character '|'`
- 3 x `parse: line N: expected 'id', found 't'`
- 2 x `parse: line N: expected 'returns', found 'requires'`
- 2 x `parse: line N: '/' does not start a statement`
- 2 x `wf: unbound var False`
- 2 x `parse: line N: expected ')', found 'div'`
- 2 x `parse: line N: expected '{', found 'xor'`
- 2 x `parse: line N: expected ')', found 'in'`
- 2 x `wf: unbound var True`
- 2 x `wf: unbound var nil`
- 2 x `parse: line N: expected 'id', found 'seq'`
- 1 x `parse: line N: expected ':=', found 'N'`
- 1 x `wf: call of unknown fun sum_divisors`
- 1 x `parse: line N: expected ':=', found '='`
- 1 x `parse: line N: expected ':=', found '['`

## The problem's own tests (interp on the MBPP assertions)

| outcome | tasks |
|---|---:|
| pass | 5 |
| fail | 21 |
| signature | 2 |

## The seven kernels (real / twin), over the well-formed tasks

| kernel | verified / refuted | of tasks |
|---|---:|---:|
| dafny | 10 | 28 |
| verus | 12 | 28 |
| spark | 10 | 28 |
| framac | 10 | 28 |
| lean | 11 | 28 |
| rocq | 12 | 28 |
| fstar | 7 | 28 |

| columns counting | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|---|
| tasks | 2 | 8 | 2 | 0 | 0 | 0 | 0 | 16 |

Tasks with no twin at all (every mutation on the ladder computes what the real body computes, or no input satisfies requires): 3.

## 12.6's table: verifies with a refuted twin, against passes its tests

| verifies with refuted twin in | tests pass | tests fail | requires-excluded | undefined | signature |
|---|---:|---:|---:|---:|---:|
| all seven | 0 | 1 | 0 | 0 | 1 |
| some column | 2 | 8 | 0 | 0 | 0 |
| none | 3 | 12 | 0 | 0 | 1 |

**0 of 368 problems** got a task that verifies with a refuted twin in all seven columns and passes its tests; 2 in at least one column. Verified-with-twin but failing its tests, the class 12.6 warns about: 1 in all seven, 8 in some column.

MBPP-DFY subset: 67 pool problems are MBPP-DFY problems (ROADMAP 16.2's family); 3 of them reached the kernels and 0 verify in all seven and pass their tests.

## Every task

| task_id | task | columns counting | tests | dafny | verus | spark | framac | lean | rocq | fstar |
|---:|---|---:|---|---|---|---|---|---|---|---|
| 47 | mbpp_47__compute_Last_Digit | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 86 | mbpp_86__centered_hexagonal_number | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 122 | mbpp_122__smartNumber | 6 | fail | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 151 | mbpp_151__is_coprime | 0 | signature | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 212 | mbpp_212__fourth_Power_Sum | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 221 | mbpp_221__first_even | 5 | fail | verified / unproved | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| 287 | mbpp_287__square_Sum | 6 | fail | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 347 | mbpp_347__count_Squares | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 355 | mbpp_355__count_Rectangles | 0 | fail | malformed / malformed | malformed / malformed | malformed / malformed | malformed / malformed | unproved / unproved | malformed / malformed | malformed / malformed |
| 375 | mbpp_375__round_num | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 420 | mbpp_420__cube_Sum | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 443 | mbpp_443__largest_neg | 5 | fail | verified / unproved | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| 479 | mbpp_479__first_Digit | 0 | pass | unproved / refuted | unproved / refuted | unproved / unproved | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 483 | mbpp_483__first_Factorial_Divisible_Number | 0 | fail | unproved / unproved | unproved / unproved | unproved / unproved | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 502 | mbpp_502__find | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 566 | mbpp_566__sum_digits | 0 | fail | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 592 | mbpp_592__sum_Of_product | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 663 | mbpp_663__find_max_val | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 675 | mbpp_675__sum_nums | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 687 | mbpp_687__recur_gcd | 7 | signature | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 692 | mbpp_692__last_Two_Digits | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 765 | mbpp_765__is_polite | 0 | fail | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 768 | mbpp_768__check_Odd_Parity | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted |
| 793 | mbpp_793__last | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 814 | mbpp_814__rombus_area | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 882 | mbpp_882__parallelogram_perimeter | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 931 | mbpp_931__sum_series | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 935 | mbpp_935__series_sum | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |

## Problems that produced no graded task

| task_id | fn | stage | why |
|---:|---|---|---|
| 3 | is_not_prime | parse | line 4: expected 'returns', found 'requires' |
| 6 | differ_At_One_Bit_Pos | parse | line 6: unexpected character '^' |
| 20 | is_woodall | parse | line 5: '/' does not start an expression |
| 24 | binary_to_decimal | parse | line 5: 'int' does not start an expression |
| 28 | binomial_Coeff | parse | line 14: expected '{', found 'if' |
| 32 | max_Prime_Factors | parse | line 20: '/' does not start a statement |
| 34 | find_missing | parse | line 4: expected 'nat', found 'length' |
| 38 | div_even_odd | parse | line 9: unexpected character '&' |
| 45 | get_gcd | parse | line 4: expected 'nat', found 'length' |
| 51 | check_equilateral | wf | unbound var False; assign r: None into bool; unbound var True; assign r: None into bool |
| 56 | check | parse | line 16: expected ':=', found '10' |
| 60 | max_len_sub | parse | line 5: expected ')', found 'for' |
| 66 | pos_count | parse | line 5: expected ']', found 'for' |
| 68 | is_Monotonic | parse | line 5: expected ')', found 'x' |
| 72 | dif_Square | parse | line 5: 'int' does not start an expression |
| 78 | count_With_Odd_SetBits | parse | line 9: expected ')', found 'div' |
| 96 | divisor | parse | line 9: '/' does not start an expression |
| 103 | eulerian_num | parse | line 13: expected '{', found 'if' |
| 119 | search | parse | line 4: expected 'nat', found 'length' |
| 126 | sum | wf | task decreases without a self-call |
| 138 | is_Sum_Of_Powers_Of_Two | parse | line 5: unexpected character '/' |
| 144 | sum_Pairs | parse | line 5: expected ')', found 'for' |
| 149 | longest_subseq_with_diff_one | parse | line 17: expected 'id', found 't' |
| 158 | min_Ops | parse | line 4: expected 'nat', found 'length' |
| 164 | areEquivalent | wf | call of unknown fun sum_divisors; call of unknown fun sum_divisors; unbound var False; assign r: None into bool; call of |
| 167 | next_Power_Of_2 | parse | line 5: unexpected character '^' |
| 169 | get_pell | wf | task decreases without a self-call |
| 179 | is_num_keith | parse | line 7: expected ':=', found '=' |
| 184 | greater_specificnum | parse | line 11: unexpected character '&' |
| 189 | first_Missing_Positive | parse | line 21: expected ':=', found '[' |
| 194 | octal_To_Decimal | parse | line 6: 'int' does not start an expression |
| 203 | hamming_Distance | parse | line 6: unexpected character '^' |
| 224 | count_Set_Bits | parse | line 5: unexpected character '&' |
| 228 | all_Bits_Set_In_The_Given_Range | parse | line 7: comparisons do not chain; parenthesise |
| 235 | even_bit_set_number | parse | line 5: unexpected character '/' |
| 239 | get_total_number_of_sequences | parse | line 18: unexpected character '&' |
| 245 | max_sum | wf | call of unknown fun sum; == wants two ints, two bools, two seqs or two pairs of the same type; call of unknown fun sum;  |
| 258 | count_odd | parse | line 5: expected ')', found 'x' |
| 267 | square_Sum | parse | line 5: '/' does not start an expression |
| 271 | even_Power_Sum | parse | line 5: '*' does not start an expression |
| 275 | get_Position | parse | line 7: unexpected character '&' |
| 283 | validate | parse | line 5: expected ')', found ']' |
| 289 | odd_Days | parse | line 5: '/' does not start an expression |
| 295 | sum_div | wf | task decreases without a self-call |
| 302 | set_Bit_Number | parse | line 6: unexpected character '^' |
| 306 | max_sum_increasing_subseq | parse | line 5: expected ')', found 'for' |
| 313 | pos_nos | parse | line 21: '/' does not start a statement |
| 318 | max_volume | parse | line 4: expected 'nat', found 'length' |
| 325 | get_Min_Squares | wf | call of unknown fun min_squares; == wants two ints, two bools, two seqs or two pairs of the same type |
| 329 | neg_count | parse | line 5: expected ')', found 'x' |
| 334 | check_Validity | wf | unbound var False; assign r: None into bool; unbound var True; assign r: None into bool |
| 339 | find_Divisor | wf | unbound var max_divisor; == wants two ints, two bools, two seqs or two pairs of the same type; task decreases without a  |
| 344 | count_Odd_Squares | wf | task decreases without a self-call; unbound var a; == wants two ints, two bools, two seqs or two pairs of the same type; |
| 351 | first_Element | parse | line 6: expected '.', found ')' |
| 362 | max_occurrences | parse | line 23: expected 'else', found 'count' |
| 366 | adjacent_num_product | parse | line 5: expected ')', found 'for' |
| 383 | even_bit_toggle_number | parse | line 5: expected '{', found 'xor' |
| 385 | get_perrin | parse | line 13: expected 'else', found '{' |
| 389 | find_lucas | wf | call of unknown fun mbpp_389__find_lucas; call of unknown fun mbpp_389__find_lucas; + over non-int; call of unknown fun  |
| 402 | ncr_modp | wf | arity mismatch calling ncr; task decreases without a self-call; arity mismatch calling ncr |
| 414 | overlapping | parse | line 4: expected ')', found 'in' |
| 436 | neg_nos | wf | unbound var null; != wants two ints, two bools, two seqs or two pairs of the same type |
| 453 | sumofFactors | parse | line 5: expected ']', found 'for' |
| 463 | max_subarray_product | parse | line 9: expected ':', found ':=' |
| 467 | decimal_to_Octal | parse | line 11: unexpected character '^' |
| 469 | max_profit | parse | line 4: expected 'nat', found 'length' |
| 472 | check_Consecutive | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 489 | frequency_Of_Largest | parse | line 5: expected ')', found 'x' |
| 492 | binary_search | parse | line 4: expected 'nat', found 'length' |
| 506 | permutation_coefficient | parse | line 6: unexpected character '!' |
| 510 | no_of_subsequences | parse | line 4: expected 'nat', found 'length' |
| 515 | modular_sum | parse | line 17: unexpected character '/' |
| 518 | sqrt_root | parse | line 9: expected ')', found 'div' |
| 521 | check_isosceles | wf | unbound var True; assign r: None into bool; unbound var True; assign r: None into bool; unbound var True; assign r: None |
| 524 | max_sum_increasing_subsequence | parse | line 5: expected '{', found 'for' |
| 527 | get_pairs_count | parse | line 4: expected 'returns', found 'requires' |
| 531 | min_coins | wf | call of unknown fun mbpp_531__min_coins; == wants two ints, two bools, two seqs or two pairs of the same type; ensures r |
| 541 | check_abundant | parse | line 26: expected 'else', found '}' |
| 545 | toggle_F_and_L_bits | parse | line 5: expected '{', found 'xor' |
| 548 | longest_increasing_subsequence | parse | line 20: expected 'id', found 't' |
| 550 | find_Max | parse | line 13: '/' does not start an expression |
| 556 | find_Odd_Pair | parse | line 14: unexpected character '^' |
| 559 | max_sub_array_sum | parse | line 4: expected 'nat', found 'length' |
| 571 | max_sum_pair_diff_lessthan_K | parse | line 4: expected 'nat', found 'length' |
| 575 | count_no | wf | unbound var n; + over non-int; unbound var n; call of unknown fun mbpp_575__count_no; call of unknown fun mbpp_575__coun |
| 583 | catalan_number | wf | call of unknown fun mbpp_583__catalan_number; + over non-int |
| 597 | find_kth | parse | line 4: unexpected character '&' |
| 605 | prime_num | parse | line 5: unexpected character '&' |
| 609 | floor_Min | wf | call of unknown fun min; == wants two ints, two bools, two seqs or two pairs of the same type |
| 626 | triangle_area | parse | line 5: unexpected character '^' |
| 633 | pair_OR_Sum | parse | line 9: unexpected character '^' |
| 638 | wind_chill | parse | line 6: unexpected character '^' |
| 650 | are_Equal | parse | line 17: expected 'else', found 'i' |
| 656 | find_Min_Sum | parse | line 5: expected ')', found 'for' |
| 658 | max_occurrences | parse | line 25: expected 'else', found 'current_count' |
| 670 | decreasing_trend | parse | line 4: expected 'nat', found 'length' |
| 672 | max_of_three | parse | line 13: expected '{', found 'if' |
| 680 | increasing_trend | parse | line 4: expected 'nat', found 'length' |
| 683 | sum_Square | wf | call of unknown fun sqrt; call of unknown fun sqrt; * over non-int; unbound var False; assign r: None into bool; unbound |
| 701 | equilibrium_index | parse | line 5: expected ']', found ':' |
| 706 | is_subset | parse | line 5: expected ')', found 'in' |
| 711 | product_Equal | parse | line 17: 'int' does not start an expression |
| 723 | count_same_pair | parse | line 4: expected 'nat', found 'length' |
| 734 | sum_Of_Subarray_Prod | parse | line 5: expected ')', found 'for' |
| 736 | left_insertion | wf | unbound var nil; != wants two ints, two bools, two seqs or two pairs of the same type |
| 751 | check_min_heap | parse | line 5: unexpected character '&' |
| 775 | odd_position | parse | line 5: expected ')', found 'for' |
| 782 | Odd_Length_Sum | parse | line 5: expected ')', found 'for' |
| 786 | right_insertion | wf | unbound var nil; != wants two ints, two bools, two seqs or two pairs of the same type |
| 798 | _sum | parse | line 3: unexpected character '_' |
| 802 | count_Rotation | parse | line 4: expected 'nat', found 'length' |
| 804 | is_Product_Even | parse | line 3: expected 'id', found 'seq' |
| 831 | count_Pairs | parse | line 5: expected ')', found 'for' |
| 837 | cube_Sum | parse | line 5: '/' does not start an expression |
| 842 | get_odd_occurence | parse | line 29: expected 'eof', found 'spec' |
| 844 | get_Number | parse | line 6: '/' does not start an expression |
| 846 | find_platform | parse | line 3: expected 'id', found 't' |
| 849 | Sum | parse | line 9: '/' does not start an expression |
| 853 | sum_of_odd_Factors | parse | line 5: expected ']', found 'for' |
| 856 | find_Min_Swaps | parse | line 16: expected ':=', found '(' |
| 867 | min_Num | parse | line 4: expected 'nat', found 'len' |
| 876 | lcm | parse | line 10: '/' does not start an expression |
| 887 | is_odd | parse | line 4: unexpected character '&' |
| 891 | same_Length | wf | call of unknown fun str; len of a non-seq; call of unknown fun str; len of a non-seq; call of unknown fun str; len of a  |
| 899 | check | parse | line 16: expected ':=', found ';' |
| 903 | count_Unset_Bits | parse | line 5: unexpected character '&' |
| 908 | find_fixed_point | parse | line 4: expected 'nat', found 'length' |
| 911 | maximum_product | parse | line 4: expected 'nat', found 'length' |
| 919 | multiply_list | parse | line 9: expected 'nat', found 'isEmpty' |
| 953 | subset | parse | line 7: expected 'id', found 'seq' |
| 957 | get_First_Set_Bit_Pos | parse | line 17: expected 'else', found 'n' |
| 962 | sum_Even | parse | line 6: expected ']', found 'for' |
| 970 | min_of_two | wf | v1 expression form in a v0 task; call of unknown fun min; == wants two ints, two bools, two seqs or two pairs of the sam |

