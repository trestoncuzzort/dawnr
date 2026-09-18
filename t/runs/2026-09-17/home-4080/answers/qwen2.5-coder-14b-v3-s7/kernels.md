# t cross-kernel agreement, 2026-09-17 23:34Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_112__perimeter | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_127__multiply_int | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_171__perimeter_pentagon | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_199__highest_Power_of_2 | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| mbpp_210__is_allowed_specific_char | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_21__multiples_of_num | unproved / refuted | malformed / malformed | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_221__first_even | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / refuted | refuted / refuted | refuted / refuted |
| mbpp_234__volume_cube | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_238__number_of_substrings | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_281__all_unique | unproved / refuted | unproved / refuted | timeout / unproved | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_292__find | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_345__diff_consecutivenums | unproved / refuted | unproved / refuted | timeout / refuted | timeout / timeout | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_349__check | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | unproved / refuted |
| mbpp_352__unique_Characters | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_369__lateralsurface_cuboid | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_385__get_perrin | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_3__is_not_prime | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | malformed / timeout | verified / refuted |
| mbpp_414__overlapping | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_41__filter_evennumbers | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | timeout / timeout | unproved / unproved | timeout / timeout |
| mbpp_426__filter_oddnumbers | unproved / refuted | unproved / refuted | verified / refuted | timeout / refuted | timeout / timeout | timeout / unproved | timeout / timeout |
| mbpp_427__change_date_format | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_46__test_distinct | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_472__check_Consecutive | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| mbpp_474__replace_char | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_478__remove_lowercase | verified / timeout | verified / refuted | verified / refuted | abstain / abstain | verified / timeout | lower-too-big / lower-too-big | abstain / abstain |
| mbpp_518__sqrt_root | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| mbpp_536__nth_items | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / refuted | refuted / refuted | refuted / refuted |
| mbpp_557__toggle_string | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| mbpp_577__last_Digit_Factorial | unproved / unproved | malformed / refuted | refuted / refuted | abstain / abstain | unproved / unproved | unproved / unproved | refuted / refuted |
| mbpp_578__interleave_lists | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | timeout / timeout | verified / refuted | verified / refuted |
| mbpp_586__split_Arr | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| mbpp_594__diff_even_odd | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | unproved / unproved | refuted / refuted |
| mbpp_637__noprofit_noloss | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | verified / refuted |
| mbpp_643__text_match_wordz_middle | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | unproved / refuted |
| mbpp_648__exchange_elements | unproved / refuted | unproved / refuted | timeout / timeout | abstain / abstain | timeout / timeout | timeout / refuted | unproved / refuted |
| mbpp_663__find_max_val | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_664__average_Even | unproved / unproved | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_680__increasing_trend | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_69__is_sublist | unproved / unproved | unproved / refuted | timeout / refuted | timeout / refuted | verified / refuted | timeout / refuted | verified / refuted |
| mbpp_700__count_range_in_list | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| mbpp_718__alternate_elements | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| mbpp_730__consecutive_duplicates | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| mbpp_733__find_first_occurrence | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_736__left_insertion | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_741__all_Characters_Same | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_754__extract_index_list | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_794__text_starta_endb | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / unproved | verified / refuted | unproved / refuted |
| mbpp_804__is_Product_Even | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_810__count_variable | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_815__sort_by_dnf | unproved / refuted | unproved / refuted | timeout / refuted | lower-error / lower-error | unproved / unproved | unproved / refuted | unproved / refuted |
| mbpp_825__access_elements | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_852__remove_negs | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / refuted | timeout / refuted | verified / refuted |
| mbpp_866__check_monthnumb | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | timeout / refuted | verified / refuted |
| mbpp_871__are_Rotations | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | timeout / refuted | timeout / unproved |
| mbpp_890__find_Extra | unproved / refuted | unproved / refuted | unproved / unproved | refuted / refuted | unproved / refuted | refuted / refuted | unproved / refuted |
| mbpp_908__find_fixed_point | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_99__decimal_to_binary | unproved / unproved | refuted / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_112__perimeter.dfy` d309d6e8cbc3f7bc…, `mbpp_112__perimeter.rs` 1b24e58370cc6748…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| framac | 1 | 7 | mbpp_586__split_Arr |
| lean | 1 | 7 | mbpp_557__toggle_string |
| dafny | 0 | 3 | (none) |
| verus | 0 | 4 | (none) |
| spark | 0 | 1 | (none) |
| rocq | 0 | 8 | (none) |
| fstar | 0 | 4 | (none) |

Of the 2 tasks in six, 1 is framac alone, 1 is lean alone.
