# t cross-kernel agreement, 2026-09-17 10:14Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_127__multiply_int | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_161__remove_elements | verified / refuted | unproved / refuted | malformed / malformed | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_18__remove_dirty_chars | unproved / refuted | unproved / refuted | malformed / malformed | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_210__is_allowed_specific_char | unproved / refuted | unproved / refuted | unproved / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_227__min_of_three | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_238__number_of_substrings | verified / refuted | verified / refuted | verified / refuted | verified / refuted | lower-error / lower-error | verified / refuted | verified / refuted |
| mbpp_281__all_unique | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_320__sum_difference | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_345__diff_consecutivenums | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted |
| mbpp_349__check | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_352__unique_Characters | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_356__find_angle | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_365__count_Digit | unproved / unproved | refuted / refuted | malformed / malformed | abstain / abstain | unproved / refuted | refuted / refuted | abstain / abstain |
| mbpp_388__highest_Power_of_2 | refuted / refuted | refuted / refuted | timeout / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted |
| mbpp_412__remove_odd | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | timeout / timeout | unproved / unproved | unproved / refuted |
| mbpp_426__filter_oddnumbers | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| mbpp_46__test_distinct | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_47__compute_Last_Digit | unproved / unproved | malformed / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_503__add_consecutive_nums | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted |
| mbpp_505__re_order | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_517__largest_pos | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_51__check_equilateral | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | verified / refuted |
| mbpp_552__Seq_Linear | unproved / refuted | unproved / refuted | timeout / timeout | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_554__Split | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| mbpp_565__split | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / refuted | refuted / refuted | refuted / refuted |
| mbpp_567__issort_list | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_578__interleave_lists | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | verified / refuted |
| mbpp_581__surface_Area | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_589__perfect_squares | refuted / refuted | malformed / malformed | refuted / refuted | abstain / abstain | timeout / timeout | unproved / refuted | timeout / timeout |
| mbpp_610__remove_kth_element | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_629__Split | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | timeout / timeout | timeout / refuted | unproved / refuted |
| mbpp_646__No_of_cubes | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_648__exchange_elements | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | refuted / refuted |
| mbpp_663__find_max_val | unproved / refuted | unproved / refuted | timeout / refuted | refuted / unproved | unproved / refuted | unproved / unproved | unproved / refuted |
| mbpp_664__average_Even | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| mbpp_668__replace | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | timeout / refuted | abstain / abstain |
| mbpp_672__max_of_three | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_680__increasing_trend | unproved / refuted | unproved / refuted | unproved / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_690__mul_consecutive_nums | unproved / refuted | unproved / refuted | timeout / refuted | timeout / timeout | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_69__is_sublist | unproved / unproved | malformed / malformed | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_718__alternate_elements | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| mbpp_732__replace_specialchar | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / unproved | abstain / abstain |
| mbpp_736__left_insertion | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_741__all_Characters_Same | verified / refuted | verified / refuted | verified / unproved | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| mbpp_786__right_insertion | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_789__perimeter_polygon | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_804__is_Product_Even | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | malformed / refuted | unproved / refuted |
| mbpp_817__div_of_nums | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_824__remove_even | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| mbpp_825__access_elements | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| mbpp_865__ntimes_list | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_871__are_Rotations | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | timeout / refuted | unproved / unproved |
| mbpp_883__div_of_nums | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_890__find_Extra | unproved / refuted | unproved / refuted | unproved / refuted | refuted / refuted | unproved / unproved | refuted / refuted | unproved / refuted |
| mbpp_908__find_fixed_point | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_913__end_num | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| mbpp_934__dealnnoy_num | unproved / unproved | unproved / refuted | unproved / refuted | timeout / unproved | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_935__series_sum | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_944__num_position | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_127__multiply_int.dfy` f6bf981dbb7780e3…, `mbpp_127__multiply_int.rs` c869bc792d605606…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| lean | 4 | 7 | mbpp_238__number_of_substrings, mbpp_578__interleave_lists, mbpp_825__access_elements, mbpp_913__end_num |
| framac | 2 | 3 | mbpp_345__diff_consecutivenums, mbpp_503__add_consecutive_nums |
| spark | 1 | 4 | mbpp_935__series_sum |
| dafny | 0 | 2 | (none) |
| verus | 0 | 7 | (none) |
| rocq | 0 | 9 | (none) |
| fstar | 0 | 5 | (none) |

Of the 7 tasks in six, 4 are lean alone, 2 are framac alone, 1 is spark alone.
