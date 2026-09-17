# t cross-kernel agreement, 2026-09-17 10:01Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_118__string_to_list | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_127__multiply_int | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_161__remove_elements | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | abstain / abstain | verified / refuted |
| mbpp_168__frequency | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_173__remove_splchar | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_201__chkList | unproved / refuted | unproved / refuted | unproved / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_220__replace_max_specialchar | unproved / unproved | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | unproved / unproved | refuted / refuted |
| mbpp_227__min_of_three | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_240__replace_list | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| mbpp_266__lateralsurface_cube | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_281__all_unique | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_309__maximum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_345__diff_consecutivenums | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted |
| mbpp_349__check | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_352__unique_Characters | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_373__volume_cuboid | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_382__find_rotation_count | unproved / refuted | refuted / refuted | timeout / timeout | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_388__highest_Power_of_2 | refuted / refuted | refuted / refuted | refuted / refuted | timeout / refuted | refuted / refuted | unproved / refuted | refuted / refuted |
| mbpp_412__remove_odd | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| mbpp_427__change_date_format | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_434__text_match_one | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | timeout / unproved | unproved / refuted |
| mbpp_44__text_match_string | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | unproved / unproved | abstain / abstain |
| mbpp_46__test_distinct | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_498__gcd | unproved / unproved | unproved / refuted | timeout / refuted | refuted / unproved | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_503__add_consecutive_nums | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_506__permutation_coefficient | unproved / unproved | unproved / refuted | timeout / refuted | refuted / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_517__largest_pos | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_518__sqrt_root | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| mbpp_532__check_permutation | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | timeout / refuted | verified / refuted |
| mbpp_557__toggle_string | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| mbpp_566__sum_digits | unproved / unproved | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_567__issort_list | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_629__Split | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| mbpp_631__replace_spaces | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_654__rectangle_perimeter | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_663__find_max_val | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_66__pos_count | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | unproved / unproved | verified / refuted |
| mbpp_675__sum_nums | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_676__remove_extra_char | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_680__increasing_trend | unproved / refuted | unproved / refuted | unproved / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_690__mul_consecutive_nums | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_69__is_sublist | unproved / unproved | malformed / malformed | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_706__is_subset | unproved / refuted | unproved / refuted | timeout / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_736__left_insertion | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_741__all_Characters_Same | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_764__number_ctr | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | timeout / refuted |
| mbpp_787__text_match_three | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | timeout / unproved | unproved / refuted |
| mbpp_794__text_starta_endb | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_804__is_Product_Even | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | malformed / refuted | unproved / refuted |
| mbpp_810__count_variable | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_815__sort_by_dnf | refuted / refuted | refuted / refuted | timeout / refuted | lower-error / lower-error | timeout / refuted | unproved / unproved | refuted / refuted |
| mbpp_818__lower_ctr | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_825__access_elements | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_860__check_alphanumeric | unproved / refuted | unproved / refuted | timeout / timeout | abstain / abstain | refuted / unproved | refuted / unproved | unproved / refuted |
| mbpp_866__check_monthnumb | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | timeout / refuted | verified / refuted |
| mbpp_873__fibonacci | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_883__div_of_nums | unproved / unproved | refuted / refuted | refuted / timeout | abstain / abstain | refuted / refuted | unproved / unproved | refuted / refuted |
| mbpp_890__find_Extra | unproved / refuted | unproved / refuted | unproved / refuted | refuted / refuted | unproved / unproved | refuted / refuted | unproved / refuted |
| mbpp_897__is_Word_Present | refuted / unproved | refuted / refuted | timeout / timeout | timeout / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_89__closest_num | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_8__square_nums | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_913__end_num | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| mbpp_973__left_rotate | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_127__multiply_int.dfy` 6c88cbdb1d6f61eb…, `mbpp_127__multiply_int.rs` 1dd9cc505a28fcd6…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| lean | 3 | 4 | mbpp_412__remove_odd, mbpp_557__toggle_string, mbpp_913__end_num |
| framac | 2 | 5 | mbpp_240__replace_list, mbpp_345__diff_consecutivenums |
| dafny | 0 | 2 | (none) |
| verus | 0 | 3 | (none) |
| spark | 0 | 2 | (none) |
| rocq | 0 | 8 | (none) |
| fstar | 0 | 3 | (none) |

Of the 5 tasks in six, 3 are lean alone, 2 are framac alone.
