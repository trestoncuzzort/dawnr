# t cross-kernel agreement, 2026-09-17 12:11Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_101__kth_element | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_159__month_season | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_191__check_monthnumber | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | timeout / refuted | verified / refuted |
| mbpp_192__check_String | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / unproved | refuted / refuted | refuted / refuted |
| mbpp_19__test_duplicate | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_201__chkList | unproved / refuted | unproved / refuted | timeout / unproved | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_240__replace_list | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_281__all_unique | unproved / refuted | unproved / refuted | timeout / timeout (FLAKED) | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_282__sub_list | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_285__text_match_two_three | unproved / refuted | unproved / refuted | timeout / timeout | abstain / abstain | unproved / refuted | timeout / unproved | unproved / refuted |
| mbpp_345__diff_consecutivenums | unproved / refuted | unproved / refuted | timeout / refuted | timeout / timeout | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_352__unique_Characters | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_356__find_angle | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_378__move_first | unproved / refuted | unproved / refuted | verified / refuted | lower-error / lower-error | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_412__remove_odd | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | timeout / refuted | unproved / unproved | unproved / refuted |
| mbpp_414__overlapping | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_41__filter_evennumbers | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | timeout / timeout | timeout / refuted | timeout / refuted |
| mbpp_46__test_distinct | unproved / refuted | unproved / refuted | unproved / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_472__check_Consecutive | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| mbpp_491__sum_gp | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_505__re_order | unproved / unproved | malformed / malformed | timeout / timeout | abstain / abstain | timeout / refuted | unproved / unproved | refuted / refuted |
| mbpp_517__largest_pos | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_629__Split | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | timeout / refuted | verified / refuted |
| mbpp_632__move_zero | refuted / refuted | refuted / refuted | timeout / timeout | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_644__reverse_Array_Upto_K | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_666__count_char | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / refuted | unproved / refuted |
| mbpp_668__replace | refuted / refuted | refuted / refuted | refuted / malformed | abstain / abstain | unproved / unproved | refuted / refuted | abstain / abstain |
| mbpp_680__increasing_trend | unproved / refuted | unproved / refuted | unproved / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_706__is_subset | unproved / refuted | unproved / refuted | timeout / timeout | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_730__consecutive_duplicates | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| mbpp_736__left_insertion | unproved / refuted | timeout / refuted | timeout / refuted | timeout / refuted | unproved / unproved | timeout / refuted | unproved / refuted |
| mbpp_754__extract_index_list | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_794__text_starta_endb | refuted / refuted | refuted / refuted | refuted / timeout | abstain / abstain | refuted / refuted | refuted / unproved | refuted / refuted |
| mbpp_802__count_Rotation | refuted / refuted | refuted / refuted | timeout / refuted | refuted / refuted | refuted / unproved | refuted / refuted | refuted / refuted |
| mbpp_804__is_Product_Even | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_810__count_variable | refuted / refuted | refuted / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_824__remove_even | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | timeout / timeout | timeout / refuted | unproved / refuted |
| mbpp_825__access_elements | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| mbpp_890__find_Extra | unproved / refuted | unproved / refuted | unproved / unproved | refuted / refuted | unproved / refuted | refuted / refuted | unproved / refuted |
| mbpp_899__check | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_908__find_fixed_point | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_928__change_date_format | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_943__combine_lists | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | timeout / timeout | unproved / refuted | timeout / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_101__kth_element.dfy` 7d1e145bb9012539…, `mbpp_101__kth_element.rs` d46d9f9293e070d9…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| lean | 1 | 3 | mbpp_825__access_elements |
| dafny | 0 | 2 | (none) |
| verus | 0 | 3 | (none) |
| spark | 0 | 1 | (none) |
| framac | 0 | 3 | (none) |
| rocq | 0 | 4 | (none) |
| fstar | 0 | 2 | (none) |

Of the 1 tasks in six, 1 is lean alone.
