# t cross-kernel agreement, 2026-09-19 06:47Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_10__small_nnum | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_122__smartNumber | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_158__min_Ops | refuted / refuted | refuted / refuted | refuted / timeout (FLAKED) | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_161__remove_elements | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_212__fourth_Power_Sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_220__replace_max_specialchar | unproved / refuted | unproved / refuted | abstain / abstain | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_232__larg_nnum | refuted / refuted | refuted / refuted | refuted / timeout (FLAKED) | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_267__square_Sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_287__square_Sum | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_302__set_Bit_Number | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_308__large_product | refuted / refuted | refuted / refuted | malformed / malformed | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| mbpp_322__position_min | refuted / refuted | refuted / refuted | malformed / malformed | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_345__diff_consecutivenums | unproved / refuted | unproved / refuted | timeout / timeout | timeout / timeout | unproved / refuted | timeout / refuted | unproved / refuted |
| mbpp_347__count_Squares | verified / refuted | verified / refuted | verified / timeout (FLAKED) | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_34__find_missing | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / unproved | refuted / refuted |
| mbpp_351__first_Element | refuted / refuted | refuted / refuted | timeout / timeout (FLAKED) | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_355__count_Rectangles | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_358__moddiv_list | refuted / refuted | refuted / refuted | refuted / refuted (FLAKED) | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_375__round_num | refuted / refuted | refuted / refuted | refuted / refuted (FLAKED) | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_383__even_bit_toggle_number | refuted / refuted | refuted / refuted | refuted / timeout (FLAKED) | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_387__even_or_odd | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_38__div_even_odd | refuted / refuted | refuted / refuted | timeout / timeout (FLAKED) | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_39__rearange_string | refuted / refuted | refuted / refuted | malformed / malformed | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_420__cube_Sum | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_436__neg_nos | refuted / refuted | refuted / refuted | timeout / timeout (FLAKED) | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_443__largest_neg | unproved / unproved | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_467__decimal_to_Octal | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_479__first_Digit | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_4__heap_queue_largest | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / refuted | unproved / refuted |
| mbpp_502__find | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_503__add_consecutive_nums | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_536__nth_items | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_552__Seq_Linear | unproved / refuted | unproved / refuted | unproved / refuted | abstain / abstain | unproved / unproved | unproved / refuted | unproved / refuted |
| mbpp_556__find_Odd_Pair | unproved / unproved | refuted / refuted | vacuous / vacuous | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted |
| mbpp_565__split | refuted / refuted | refuted / refuted | refuted / timeout | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_566__sum_digits | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_623__nth_nums | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_626__triangle_area | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_629__Split | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_670__decreasing_trend | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_675__sum_nums | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_682__mul_list | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_6__differ_At_One_Bit_Pos | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_748__capital_words_spaces | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_757__count_reverse_pairs | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_768__check_Odd_Parity | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_769__Diff | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_800__remove_all_spaces | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / unproved | abstain / abstain |
| mbpp_814__rombus_area | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_831__count_Pairs | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| mbpp_837__cube_Sum | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_86__centered_hexagonal_number | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_882__parallelogram_perimeter | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_887__is_odd | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_899__check | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| mbpp_931__sum_series | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_935__series_sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
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

Verdict basis: every source file hashed; e.g. `mbpp_10__small_nnum.dfy` 11d01ef73ec0e1e6…, `mbpp_10__small_nnum.rs` 03078d5b4a1713ed…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| spark | 1 | 0 | mbpp_347__count_Squares |
| dafny | 0 | 0 | (none) |
| verus | 0 | 0 | (none) |
| framac | 0 | 1 | (none) |
| lean | 0 | 0 | (none) |
| rocq | 0 | 1 | (none) |
| fstar | 0 | 1 | (none) |

Of the 1 tasks in six, 1 is spark alone.
