# The spec experiment on MBPP: qwen2.5-coder-1.5b-r2-rep3

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
| tasks that are well-formed (graded below) | 25 |

Refusals, by named reason:

- 12 x `parse: line N: unexpected character '&'`
- 12 x `parse: line N: expected 'nat', found 'length'`
- 10 x `parse: line N: unexpected character '^'`
- 9 x `parse: line N: expected ')', found 'for'`
- 8 x `parse: line N: expected ']', found 'for'`
- 7 x `parse: line N: '/' does not start an expression`
- 6 x `parse: line N: unexpected character '|'`
- 4 x `parse: line N: 'int' does not start an expression`
- 4 x `wf: unbound var True`
- 4 x `parse: line N: expected ']', found ':'`
- 3 x `wf: operator 'mod' not in vN`
- 3 x `parse: line N: expected 'eof', found 'spec'`
- 2 x `parse: line N: expected ':', found ':='`
- 2 x `parse: line N: expected 'else', found 'i'`
- 2 x `wf: task decreases without a self-call`
- 2 x `parse: line N: expected ':=', found '['`
- 2 x `parse: line N: 'seq' is not one of int bool`
- 2 x `parse: line N: unexpected character '!'`
- 2 x `parse: line N: expected 'returns', found 'requires'`
- 1 x `wf: call of unknown fun max_prime_factor`
- 1 x `wf: call of unknown fun reverse`
- 1 x `parse: line N: expected ')', found 'x'`
- 1 x `parse: line N: expected '{', found 'if'`
- 1 x `wf: call of unknown fun mbpp_N__min_Ops`
- 1 x `parse: line N: expected ':=', found '='`

## The problem's own tests (interp on the MBPP assertions)

| outcome | tasks |
|---|---:|
| pass | 3 |
| fail | 19 |
| undefined | 1 |
| signature | 2 |

## The seven kernels (real / twin), over the well-formed tasks

| kernel | verified / refuted | of tasks |
|---|---:|---:|
| dafny | 14 | 25 |
| verus | 16 | 25 |
| spark | 15 | 25 |
| framac | 14 | 25 |
| lean | 15 | 25 |
| rocq | 16 | 25 |
| fstar | 7 | 25 |

| columns counting | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|---|
| tasks | 4 | 9 | 3 | 0 | 0 | 0 | 0 | 9 |

Tasks with no twin at all (every mutation on the ladder computes what the real body computes, or no input satisfies requires): 5.

## 12.6's table: verifies with a refuted twin, against passes its tests

| verifies with refuted twin in | tests pass | tests fail | requires-excluded | undefined | signature |
|---|---:|---:|---:|---:|---:|
| all seven | 0 | 3 | 0 | 0 | 1 |
| some column | 2 | 10 | 0 | 0 | 0 |
| none | 1 | 6 | 0 | 1 | 1 |

**0 of 368 problems** got a task that verifies with a refuted twin in all seven columns and passes its tests; 2 in at least one column. Verified-with-twin but failing its tests, the class 12.6 warns about: 3 in all seven, 10 in some column.

MBPP-DFY subset: 67 pool problems are MBPP-DFY problems (ROADMAP 16.2's family); 4 of them reached the kernels and 0 verify in all seven and pass their tests.

## Every task

| task_id | task | columns counting | tests | dafny | verus | spark | framac | lean | rocq | fstar |
|---:|---|---:|---|---|---|---|---|---|---|---|
| 24 | mbpp_24__binary_to_decimal | 0 | fail | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 86 | mbpp_86__centered_hexagonal_number | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain |
| 122 | mbpp_122__smartNumber | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain |
| 151 | mbpp_151__is_coprime | 0 | signature | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 212 | mbpp_212__fourth_Power_Sum | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain |
| 221 | mbpp_221__first_even | 5 | fail | verified / unproved | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| 287 | mbpp_287__square_Sum | 6 | fail | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 289 | mbpp_289__odd_Days | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 347 | mbpp_347__count_Squares | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain |
| 355 | mbpp_355__count_Rectangles | 0 | undefined | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 420 | mbpp_420__cube_Sum | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 436 | mbpp_436__neg_nos | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 443 | mbpp_443__largest_neg | 5 | fail | verified / unproved | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| 479 | mbpp_479__first_Digit | 0 | pass | unproved / refuted | unproved / refuted | unproved / unproved | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 566 | mbpp_566__sum_digits | 0 | fail | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 592 | mbpp_592__sum_Of_product | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 675 | mbpp_675__sum_nums | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 687 | mbpp_687__recur_gcd | 7 | signature | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 692 | mbpp_692__last_Two_Digits | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain |
| 765 | mbpp_765__is_polite | 0 | fail | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 768 | mbpp_768__check_Odd_Parity | 5 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | abstain / abstain |
| 793 | mbpp_793__last | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 882 | mbpp_882__parallelogram_perimeter | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain |
| 931 | mbpp_931__sum_series | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain |
| 935 | mbpp_935__series_sum | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain |

## Problems that produced no graded task

| task_id | fn | stage | why |
|---:|---|---|---|
| 3 | is_not_prime | parse | line 10: unexpected character '&' |
| 6 | differ_At_One_Bit_Pos | parse | line 4: unexpected character '^' |
| 20 | is_woodall | parse | line 5: '/' does not start an expression |
| 28 | binomial_Coeff | parse | line 7: unexpected character '/' |
| 32 | max_Prime_Factors | wf | call of unknown fun max_prime_factor; == wants two ints, two bools, two seqs or two pairs of the same type; call of unkn |
| 34 | find_missing | parse | line 7: unexpected character '&' |
| 38 | div_even_odd | parse | line 7: expected ':', found ':=' |
| 45 | get_gcd | parse | line 4: expected 'nat', found 'length' |
| 47 | compute_Last_Digit | wf | operator 'mod' not in v0; == wants two ints, two bools, two seqs or two pairs of the same type; operator 'mod' not in v0 |
| 51 | check_equilateral | parse | line 6: unexpected character '&' |
| 56 | check | wf | call of unknown fun reverse; * over non-int; == wants two ints, two bools, two seqs or two pairs of the same type; call  |
| 60 | max_len_sub | parse | line 5: expected ')', found 'for' |
| 66 | pos_count | parse | line 5: expected ']', found 'for' |
| 68 | is_Monotonic | parse | line 4: expected ')', found 'x' |
| 72 | dif_Square | parse | line 4: 'int' does not start an expression |
| 78 | count_With_Odd_SetBits | parse | line 14: unexpected character '&' |
| 96 | divisor | parse | line 17: expected 'else', found 'i' |
| 103 | eulerian_num | parse | line 13: expected '{', found 'if' |
| 119 | search | parse | line 4: expected 'nat', found 'length' |
| 126 | sum | wf | task decreases without a self-call |
| 138 | is_Sum_Of_Powers_Of_Two | parse | line 5: unexpected character '/' |
| 144 | sum_Pairs | parse | line 5: expected ')', found 'for' |
| 149 | longest_subseq_with_diff_one | parse | line 7: expected ':=', found '[' |
| 158 | min_Ops | wf | call of unknown fun mbpp_158__min_Ops; == wants two ints, two bools, two seqs or two pairs of the same type; ensures ref |
| 164 | areEquivalent | parse | line 10: expected 'eof', found 'spec' |
| 167 | next_Power_Of_2 | parse | line 5: unexpected character '^' |
| 169 | get_pell | wf | task decreases without a self-call |
| 179 | is_num_keith | parse | line 7: expected ':=', found '=' |
| 184 | greater_specificnum | wf | unbound var True; == wants two ints, two bools, two seqs or two pairs of the same type; unbound var True; assign r: None |
| 189 | first_Missing_Positive | parse | line 21: expected ':=', found '[' |
| 194 | octal_To_Decimal | parse | line 6: 'int' does not start an expression |
| 203 | hamming_Distance | parse | line 6: unexpected character '^' |
| 224 | count_Set_Bits | parse | line 5: unexpected character '&' |
| 228 | all_Bits_Set_In_The_Given_Range | parse | line 7: comparisons do not chain; parenthesise |
| 235 | even_bit_set_number | parse | line 3: unexpected character '/' |
| 239 | get_total_number_of_sequences | parse | line 23: expected 'eof', found 'spec' |
| 245 | max_sum | parse | line 7: 'seq' is not one of int bool |
| 258 | count_odd | parse | line 5: expected ']', found 'for' |
| 267 | square_Sum | parse | line 5: '/' does not start an expression |
| 271 | even_Power_Sum | parse | line 5: '*' does not start an expression |
| 275 | get_Position | parse | line 7: unexpected character '&' |
| 283 | validate | parse | line 5: 'int' does not start an expression |
| 295 | sum_div | parse | line 3: expected ']', found 'for' |
| 302 | set_Bit_Number | parse | line 6: unexpected character '^' |
| 306 | max_sum_increasing_subseq | parse | line 5: expected ')', found 'for' |
| 313 | pos_nos | parse | line 4: expected ']', found 'for' |
| 318 | max_volume | parse | line 5: '/' does not start an expression |
| 325 | get_Min_Squares | wf | call of unknown fun min_squares; == wants two ints, two bools, two seqs or two pairs of the same type |
| 329 | neg_count | parse | line 5: expected ']', found 'for' |
| 334 | check_Validity | wf | unbound var False; assign r: None into bool; unbound var True; assign r: None into bool |
| 339 | find_Divisor | wf | unbound var max_divisor; == wants two ints, two bools, two seqs or two pairs of the same type; task decreases without a  |
| 344 | count_Odd_Squares | parse | line 18: expected 'else', found 'i' |
| 351 | first_Element | parse | line 6: expected '.', found ')' |
| 362 | max_occurrences | wf | call of unknown fun max; == wants two ints, two bools, two seqs or two pairs of the same type |
| 366 | adjacent_num_product | parse | line 5: expected ')', found 'for' |
| 375 | round_num | wf | local in a v0 task; operator 'mod' not in v0; local remainder init type mismatch; operator 'div' not in v0; < is int-onl |
| 383 | even_bit_toggle_number | parse | line 5: expected '{', found 'xor' |
| 385 | get_perrin | wf | call of unknown fun mbpp_385__get_perrin; + over non-int |
| 389 | find_lucas | wf | call of unknown fun mbpp_389__find_lucas; call of unknown fun mbpp_389__find_lucas; + over non-int; ensures references t |
| 402 | ncr_modp | wf | arity mismatch calling ncr; task decreases without a self-call; arity mismatch calling ncr |
| 414 | overlapping | parse | line 4: expected ')', found 'in' |
| 453 | sumofFactors | parse | line 5: expected ']', found 'for' |
| 463 | max_subarray_product | parse | line 7: expected 'nat', found 'length' |
| 467 | decimal_to_Octal | parse | line 10: unexpected character '^' |
| 469 | max_profit | parse | line 4: expected 'nat', found 'length' |
| 472 | check_Consecutive | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 483 | first_Factorial_Divisible_Number | parse | line 15: expected ':=', found ';' |
| 489 | frequency_Of_Largest | parse | line 7: expected ':', found ':=' |
| 492 | binary_search | parse | line 4: expected 'nat', found 'length' |
| 502 | find | wf | operator 'mod' not in v0; == wants two ints, two bools, two seqs or two pairs of the same type; operator 'mod' not in v0 |
| 506 | permutation_coefficient | parse | line 6: unexpected character '!' |
| 510 | no_of_subsequences | parse | line 4: expected 'nat', found 'length' |
| 515 | modular_sum | parse | line 17: unexpected character '/' |
| 518 | sqrt_root | parse | line 9: expected ')', found 'div' |
| 521 | check_isosceles | wf | unbound var True; assign r: None into bool; unbound var True; assign r: None into bool; unbound var True; assign r: None |
| 524 | max_sum_increasing_subsequence | parse | line 7: 'seq' is not one of int bool |
| 527 | get_pairs_count | parse | line 4: expected 'returns', found 'requires' |
| 531 | min_coins | parse | line 23: expected 'eof', found 'spec' |
| 541 | check_abundant | parse | line 26: expected 'else', found '}' |
| 545 | toggle_F_and_L_bits | parse | line 5: unexpected character '^' |
| 548 | longest_increasing_subsequence | parse | line 19: expected ':=', found '+' |
| 550 | find_Max | parse | line 12: '/' does not start an expression |
| 556 | find_Odd_Pair | parse | line 14: unexpected character '^' |
| 559 | max_sub_array_sum | parse | line 4: expected 'nat', found 'length' |
| 571 | max_sum_pair_diff_lessthan_K | parse | line 4: expected 'nat', found 'length' |
| 575 | count_no | wf | unbound var n; + over non-int; unbound var n; == wants two ints, two bools, two seqs or two pairs of the same type; call |
| 583 | catalan_number | parse | line 10: expected '{', found 'end of input' |
| 597 | find_kth | parse | line 4: unexpected character '&' |
| 605 | prime_num | parse | line 5: unexpected character '&' |
| 609 | floor_Min | parse | line 9: expected 'else', found 'if' |
| 626 | triangle_area | parse | line 5: unexpected character '^' |
| 633 | pair_OR_Sum | parse | line 21: unexpected character '^' |
| 638 | wind_chill | parse | line 5: unexpected character '^' |
| 650 | are_Equal | parse | line 4: expected 'returns', found 'requires' |
| 656 | find_Min_Sum | parse | line 5: expected ')', found 'for' |
| 658 | max_occurrences | parse | line 12: expected ':=', found 'i' |
| 663 | find_max_val | wf | operator 'mod' not in v0; == wants two ints, two bools, two seqs or two pairs of the same type; operator 'mod' not in v0 |
| 670 | decreasing_trend | parse | line 9: unexpected character '&' |
| 672 | max_of_three | parse | line 5: unexpected character '&' |
| 680 | increasing_trend | wf | unbound var True; == wants two ints, two bools, two seqs or two pairs of the same type; unbound var True; assign r: None |
| 683 | sum_Square | wf | call of unknown fun sqrt; call of unknown fun sqrt; * over non-int; unbound var False; assign r: None into bool; unbound |
| 701 | equilibrium_index | parse | line 5: expected ']', found ':' |
| 706 | is_subset | parse | line 14: unexpected character '!' |
| 711 | product_Equal | parse | line 5: 'int' does not start an expression |
| 723 | count_same_pair | parse | line 4: expected 'nat', found 'length' |
| 734 | sum_Of_Subarray_Prod | parse | line 23: expected ':=', found '*' |
| 736 | left_insertion | parse | line 5: unexpected character '/' |
| 751 | check_min_heap | parse | line 4: expected 'nat', found 'length' |
| 775 | odd_position | parse | line 5: expected ')', found 'for' |
| 782 | Odd_Length_Sum | parse | line 5: expected ')', found 'for' |
| 786 | right_insertion | parse | line 4: expected 'nat', found 'length' |
| 798 | _sum | parse | line 2: unexpected character '_' |
| 802 | count_Rotation | parse | line 9: expected ']', found ':' |
| 804 | is_Product_Even | parse | line 3: expected 'id', found 'seq' |
| 814 | rombus_area | wf | operator 'div' not in v0; == wants two ints, two bools, two seqs or two pairs of the same type; operator 'div' not in v0 |
| 831 | count_Pairs | parse | line 4: expected ')', found 'for' |
| 837 | cube_Sum | parse | line 5: '/' does not start an expression |
| 842 | get_odd_occurence | parse | line 5: '{' does not start an expression |
| 844 | get_Number | parse | line 6: '/' does not start an expression |
| 846 | find_platform | parse | line 18: expected '{', found 'decreases' |
| 849 | Sum | parse | line 9: '/' does not start an expression |
| 853 | sum_of_odd_Factors | parse | line 5: expected ']', found 'for' |
| 856 | find_Min_Swaps | parse | line 9: expected ']', found ':' |
| 867 | min_Num | wf | call of unknown fun sum; mod over non-int; call of unknown fun sum; mod over non-int |
| 876 | lcm | parse | line 30: expected 'eof', found '=' |
| 887 | is_odd | parse | line 4: unexpected character '&' |
| 891 | same_Length | wf | call of unknown fun str; len of a non-seq; call of unknown fun str; len of a non-seq; call of unknown fun str; len of a  |
| 899 | check | parse | line 5: unexpected character '/' |
| 903 | count_Unset_Bits | parse | line 5: expected ')', found 'for' |
| 908 | find_fixed_point | parse | line 4: expected 'nat', found 'length' |
| 911 | maximum_product | parse | line 15: unexpected character '&' |
| 919 | multiply_list | parse | line 8: expected ']', found ':' |
| 953 | subset | wf | call of unknown fun length; <= is int-only (SPEC.md gate 1); call of unknown fun count; == wants two ints, two bools, tw |
| 957 | get_First_Set_Bit_Pos | parse | line 18: '>' does not start an expression |
| 962 | sum_Even | parse | line 3: expected ']', found 'for' |
| 970 | min_of_two | wf | v1 expression form in a v0 task; call of unknown fun min; == wants two ints, two bools, two seqs or two pairs of the sam |

