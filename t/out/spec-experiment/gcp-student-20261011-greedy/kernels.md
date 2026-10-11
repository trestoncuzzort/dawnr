# t cross-kernel agreement, 2026-10-11 07:51Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_10__small_nnum | unproved / refuted | unproved / refuted | timeout / refuted | refuted / refuted | timeout / timeout | refuted / refuted | unproved / refuted |
| mbpp_122__smartNumber | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_141__pancake_sort | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | refuted / refuted | unproved / refuted |
| mbpp_149__longest_subseq_with_diff_one | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_151__is_coprime | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| mbpp_175__is_valid_parenthese | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted |
| mbpp_184__greater_specificnum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_194__octal_To_Decimal | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_203__hamming_Distance | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_20__is_woodall | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_228__all_Bits_Set_In_The_Given_Range | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_267__square_Sum | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_269__ascii_value | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_271__even_Power_Sum | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_275__get_Position | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_287__square_Sum | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_289__odd_Days | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_313__pos_nos | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_318__max_volume | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_322__position_min | refuted / unproved | refuted / refuted | refuted / refuted | abstain / abstain | refuted / unproved | refuted / unproved | refuted / refuted |
| mbpp_32__max_Prime_Factors | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | malformed / unproved | refuted / refuted |
| mbpp_334__check_Validity | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_344__count_Odd_Squares | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_345__diff_consecutivenums | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_347__count_Squares | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_351__first_Element | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_358__moddiv_list | refuted / refuted | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_366__adjacent_num_product | timeout / timeout | lower-error / lower-error | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | unproved / unproved |
| mbpp_375__round_num | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_38__div_even_odd | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_39__rearange_string | refuted / refuted | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_411__snake_to_camel | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_420__cube_Sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_428__shell_sort | unproved / refuted | unproved / refuted | timeout / timeout | abstain / abstain | timeout / timeout | refuted / refuted | unproved / refuted |
| mbpp_436__neg_nos | unproved / unproved | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_443__largest_neg | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_447__cube_nums | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_472__check_Consecutive | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_474__replace_char | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_479__first_Digit | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_483__first_Factorial_Divisible_Number | refuted / refuted | refuted / refuted | refuted / refuted | timeout / refuted | unproved / unproved | unproved / refuted | refuted / refuted |
| mbpp_502__find | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_503__add_consecutive_nums | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| mbpp_515__modular_sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_518__sqrt_root | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_51__check_equilateral | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_521__check_isosceles | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_527__get_pairs_count | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_536__nth_items | refuted / refuted | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_550__find_Max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_556__find_Odd_Pair | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / unproved | refuted / refuted | refuted / refuted |
| mbpp_565__split | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_575__count_no | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_593__removezero_ip | unproved / refuted | unproved / refuted | timeout / refuted | refuted / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| mbpp_597__find_kth | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_604__reverse_words | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_609__floor_Min | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_626__triangle_area | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_629__Split | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | timeout / refuted | refuted / refuted | refuted / refuted |
| mbpp_633__pair_OR_Sum | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / unproved | refuted / refuted | refuted / refuted |
| mbpp_644__reverse_Array_Upto_K | unproved / refuted | unproved / refuted | refuted / refuted | refuted / refuted | unproved / refuted | refuted / refuted | unproved / refuted |
| mbpp_665__move_last | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_670__decreasing_trend | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_672__max_of_three | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_675__sum_nums | refuted / refuted | lower-error / lower-error | refuted / refuted | refuted / refuted | refuted / refuted | lower-error / lower-error | refuted / refuted |
| mbpp_680__increasing_trend | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_682__mul_list | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_68__is_Monotonic | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_723__count_same_pair | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_729__add_list | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_72__dif_Square | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_736__left_insertion | refuted / refuted | refuted / refuted | refuted / unproved | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_748__capital_words_spaces | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_765__is_polite | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_768__check_Odd_Parity | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_775__odd_position | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_786__right_insertion | refuted / refuted | refuted / refuted | refuted / unproved | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_793__last | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_800__remove_all_spaces | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_804__is_Product_Even | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_813__string_length | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_814__rombus_area | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_826__check_Type_Of_Triangle | verified / refuted | verified / refuted | verified / timeout | timeout / refuted | verified / refuted | verified / unproved | verified / unproved |
| mbpp_831__count_Pairs | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_837__cube_Sum | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_844__get_Number | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_866__check_monthnumb | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted |
| mbpp_86__centered_hexagonal_number | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_876__lcm | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| mbpp_882__parallelogram_perimeter | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_891__same_Length | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_899__check | refuted / refuted | refuted / refuted | refuted / refuted | refuted / unproved | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_900__match_num | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_908__find_fixed_point | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_931__sum_series | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_935__series_sum | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_961__roman_to_int | refuted / refuted | refuted / refuted | timeout / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / unproved |
| mbpp_970__min_of_two | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_973__left_rotate | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_10__small_nnum.dfy` 4e0ddb942404589f…, `mbpp_10__small_nnum.rs` 101fc0af330a4ff9…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| spark | 1 | 1 | mbpp_287__square_Sum |
| rocq | 1 | 1 | mbpp_866__check_monthnumb |
| dafny | 0 | 0 | (none) |
| verus | 0 | 0 | (none) |
| framac | 0 | 1 | (none) |
| lean | 0 | 0 | (none) |
| fstar | 0 | 1 | (none) |

Of the 2 tasks in six, 1 is spark alone, 1 is rocq alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| dafny | 99 | 40 | 40 of 40 (100%) | 0 |
| verus | 99 | 40 | 40 of 40 (100%) | 0 |
| spark | 99 | 39 | 38 of 39 (97%) | 0 |
| framac | 94 | 39 | 39 of 39 (100%) | 5 |
| lean | 99 | 40 | 40 of 40 (100%) | 0 |
| rocq | 99 | 39 | 38 of 39 (97%) | 0 |
| fstar | 99 | 40 | 39 of 40 (97%) | 0 |

Verified with the twin refuted in all seven columns: 37 of 99 tasks.
