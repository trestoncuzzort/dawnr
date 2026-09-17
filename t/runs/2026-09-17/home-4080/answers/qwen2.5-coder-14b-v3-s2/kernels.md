# t cross-kernel agreement, 2026-09-17 09:28Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_151__is_coprime | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_161__remove_elements | refuted / refuted | refuted / refuted | malformed / malformed | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_169__get_pell | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_171__perimeter_pentagon | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_19__test_duplicate | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_201__chkList | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_21__multiples_of_num | unproved / refuted | malformed / malformed | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_227__min_of_three | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_240__replace_list | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_266__lateralsurface_cube | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_281__all_unique | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_316__find_last_occurrence | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_329__neg_count | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | unproved / refuted |
| mbpp_345__diff_consecutivenums | unproved / refuted | unproved / refuted | timeout / refuted | timeout / timeout | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_369__lateralsurface_cuboid | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_385__get_perrin | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_3__is_not_prime | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / timeout | unproved / refuted |
| mbpp_414__overlapping | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_41__filter_evennumbers | unproved / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | timeout / unproved | timeout / timeout |
| mbpp_426__filter_oddnumbers | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | timeout / refuted | unproved / unproved | unproved / refuted |
| mbpp_458__rectangle_area | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_466__find_peak | unproved / unproved | unproved / refuted | timeout / timeout | refuted / refuted | unproved / refuted | refuted / refuted | unproved / refuted |
| mbpp_46__test_distinct | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_499__diameter_circle | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_503__add_consecutive_nums | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted |
| mbpp_506__permutation_coefficient | unproved / unproved | unproved / refuted | unproved / refuted | refuted / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_509__average_Odd | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| mbpp_517__largest_pos | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_518__sqrt_root | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| mbpp_525__parallel_lines | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_52__parallelogram_area | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_567__issort_list | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_581__surface_Area | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_593__removezero_ip | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | abstain / abstain |
| mbpp_594__diff_even_odd | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | unproved / unproved | refuted / refuted |
| mbpp_629__Split | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | timeout / timeout | unproved / unproved | timeout / refuted |
| mbpp_62__smallest_num | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_646__No_of_cubes | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_663__find_max_val | unproved / refuted | unproved / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / unproved | unproved / refuted |
| mbpp_664__average_Even | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| mbpp_668__replace | unproved / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_672__max_of_three | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_680__increasing_trend | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_690__mul_consecutive_nums | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted |
| mbpp_730__consecutive_duplicates | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| mbpp_741__all_Characters_Same | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_754__extract_index_list | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| mbpp_775__odd_position | unproved / refuted | unproved / refuted | timeout / refuted | verified / refuted | unproved / timeout | unproved / refuted | unproved / refuted |
| mbpp_786__right_insertion | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| mbpp_789__perimeter_polygon | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_804__is_Product_Even | unproved / refuted | unproved / refuted | timeout / refuted | refuted / refuted | unproved / refuted | refuted / refuted | unproved / refuted |
| mbpp_810__count_variable | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_815__sort_by_dnf | unproved / refuted | unproved / refuted | timeout / refuted | lower-error / lower-error | unproved / unproved | unproved / refuted | unproved / refuted |
| mbpp_824__remove_even | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted |
| mbpp_852__remove_negs | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | timeout / timeout | timeout / refuted | unproved / refuted |
| mbpp_865__ntimes_list | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_870__sum_positivenum | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | unproved / refuted |
| mbpp_873__fibonacci | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_885__is_Isomorphic | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | timeout / refuted | verified / refuted |
| mbpp_908__find_fixed_point | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_934__dealnnoy_num | unproved / unproved | unproved / refuted | unproved / refuted | timeout / unproved | unproved / unproved | unproved / unproved | unproved / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_151__is_coprime.dfy` 1c8a9d9d3fbeead3…, `mbpp_151__is_coprime.rs` 4225d8b138570c96…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| framac | 2 | 2 | mbpp_503__add_consecutive_nums, mbpp_690__mul_consecutive_nums |
| lean | 1 | 2 | mbpp_824__remove_even |
| dafny | 0 | 2 | (none) |
| verus | 0 | 2 | (none) |
| spark | 0 | 1 | (none) |
| rocq | 0 | 3 | (none) |
| fstar | 0 | 2 | (none) |

Of the 3 tasks in six, 2 are framac alone, 1 is lean alone.
