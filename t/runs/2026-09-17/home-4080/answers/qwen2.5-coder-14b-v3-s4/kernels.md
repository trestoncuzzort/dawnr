# t cross-kernel agreement, 2026-09-17 09:52Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_127__multiply_int | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_176__perimeter_triangle | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_18__remove_dirty_chars | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | abstain / abstain | verified / refuted |
| mbpp_192__check_String | unproved / refuted | unproved / refuted | unproved / refuted | verified / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| mbpp_195__first | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_199__highest_Power_of_2 | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / unproved | unproved / refuted |
| mbpp_19__test_duplicate | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_201__chkList | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_204__count | verified / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | verified / refuted | timeout / refuted |
| mbpp_227__min_of_three | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_22__find_first_duplicate | refuted / refuted | refuted / refuted | refuted / unproved | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_240__replace_list | refuted / refuted | refuted / refuted | timeout / unproved | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_281__all_unique | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_329__neg_count | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | timeout / refuted |
| mbpp_33__decimal_To_Binary | unproved / unproved | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_356__find_angle | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_35__find_rect_num | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_373__volume_cuboid | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_378__move_first | unproved / refuted | unproved / refuted | verified / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_3__is_not_prime | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | timeout / unproved | unproved / refuted |
| mbpp_412__remove_odd | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| mbpp_41__filter_evennumbers | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| mbpp_426__filter_oddnumbers | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | timeout / timeout | timeout / refuted | unproved / refuted |
| mbpp_427__change_date_format | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_441__surfacearea_cube | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_46__test_distinct | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_491__sum_gp | unproved / unproved | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_505__re_order | refuted / refuted | refuted / refuted | refuted / malformed | abstain / abstain | unproved / unproved | unproved / unproved | refuted / refuted |
| mbpp_518__sqrt_root | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| mbpp_529__jacobsthal_lucas | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_52__parallelogram_area | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_532__check_permutation | unproved / unproved | unproved / unproved | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / unproved |
| mbpp_554__Split | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | timeout / refuted | timeout / timeout |
| mbpp_586__split_Arr | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| mbpp_593__removezero_ip | verified / unproved | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | abstain / abstain |
| mbpp_59__is_octagonal | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_619__move_num | unproved / refuted | unproved / refuted | abstain / abstain | abstain / abstain | unproved / refuted | refuted / refuted | unproved / refuted |
| mbpp_629__Split | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | timeout / timeout | timeout / refuted | unproved / refuted |
| mbpp_648__exchange_elements | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | timeout / timeout | refuted / refuted | refuted / refuted |
| mbpp_66__pos_count | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_673__convert | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_680__increasing_trend | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| mbpp_687__recur_gcd | unproved / unproved | unproved / refuted | timeout / refuted | refuted / unproved | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_690__mul_consecutive_nums | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted |
| mbpp_69__is_sublist | unproved / unproved | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| mbpp_718__alternate_elements | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_729__add_list | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_730__consecutive_duplicates | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / timeout |
| mbpp_733__find_first_occurrence | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_736__left_insertion | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / unproved | refuted / refuted | refuted / refuted |
| mbpp_741__all_Characters_Same | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_754__extract_index_list | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_786__right_insertion | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_789__perimeter_polygon | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_801__test_three_equal | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_802__count_Rotation | refuted / refuted | refuted / refuted | timeout / refuted | refuted / refuted | refuted / unproved | refuted / refuted | refuted / refuted |
| mbpp_804__is_Product_Even | unproved / refuted | unproved / refuted | timeout / refuted | refuted / refuted | unproved / refuted | refuted / refuted | unproved / refuted |
| mbpp_810__count_variable | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_824__remove_even | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| mbpp_865__ntimes_list | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_866__check_monthnumb | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | timeout / refuted | verified / refuted |
| mbpp_908__find_fixed_point | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_917__text_uppercase_lowercase | unproved / refuted | unproved / refuted | unproved / refuted | abstain / abstain | unproved / unproved | timeout / unproved | unproved / refuted |
| mbpp_928__change_date_format | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_944__num_position | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_127__multiply_int.dfy` 11e1c208fd2e549a…, `mbpp_127__multiply_int.rs` 558c63a751cb1bed…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| lean | 3 | 6 | mbpp_412__remove_odd, mbpp_41__filter_evennumbers, mbpp_824__remove_even |
| framac | 2 | 7 | mbpp_586__split_Arr, mbpp_690__mul_consecutive_nums |
| dafny | 0 | 4 | (none) |
| verus | 0 | 4 | (none) |
| spark | 0 | 2 | (none) |
| rocq | 0 | 6 | (none) |
| fstar | 0 | 6 | (none) |

Of the 5 tasks in six, 3 are lean alone, 2 are framac alone.
