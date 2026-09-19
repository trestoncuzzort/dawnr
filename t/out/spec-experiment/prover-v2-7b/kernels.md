# t cross-kernel agreement, 2026-09-19 05:34Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_122__smartNumber | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_161__remove_elements | refuted / refuted | refuted / refuted | malformed / malformed | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_187__longest_common_subsequence | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_194__octal_To_Decimal | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_221__first_even | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_269__ascii_value | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_302__set_Bit_Number | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_375__round_num | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_38__div_even_odd | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_463__max_subarray_product | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_467__decimal_to_Octal | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_503__add_consecutive_nums | refuted / refuted | refuted / refuted | refuted / refuted (FLAKED) | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_510__no_of_subsequences | refuted / refuted | refuted / refuted | vacuous / vacuous | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_51__check_equilateral | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_521__check_isosceles | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_527__get_pairs_count | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| mbpp_548__longest_increasing_subsequence | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| mbpp_565__split | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_575__count_no | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted |
| mbpp_584__find_adverbs | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_626__triangle_area | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_665__move_last | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_675__sum_nums | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_682__mul_list | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_729__add_list | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_748__capital_words_spaces | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_776__count_vowels | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_78__count_With_Odd_SetBits | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_813__string_length | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_840__Check_Solution | verified / refuted | verified / refuted | timeout / refuted | abstain / abstain | verified / refuted | verified / refuted | abstain / abstain |
| mbpp_856__find_Min_Swaps | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| mbpp_866__check_monthnumb | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_86__centered_hexagonal_number | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_882__parallelogram_perimeter | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_900__match_num | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | unproved / unproved | abstain / abstain |
| mbpp_928__change_date_format | unproved / unproved | unproved / refuted | timeout / timeout | abstain / abstain | unproved / refuted | refuted / unproved | unproved / refuted |
| mbpp_931__sum_series | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_970__min_of_two | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
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

Verdict basis: every source file hashed; e.g. `mbpp_122__smartNumber.dfy` 910af8ce2b970c2a…, `mbpp_122__smartNumber.rs` fb02ca22c9044cb3…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| framac | 4 | 2 | mbpp_527__get_pairs_count, mbpp_548__longest_increasing_subsequence, mbpp_575__count_no, mbpp_856__find_Min_Swaps |
| dafny | 0 | 0 | (none) |
| verus | 0 | 0 | (none) |
| spark | 0 | 1 | (none) |
| lean | 0 | 0 | (none) |
| rocq | 0 | 1 | (none) |
| fstar | 0 | 2 | (none) |

Of the 4 tasks in six, 4 are framac alone.
