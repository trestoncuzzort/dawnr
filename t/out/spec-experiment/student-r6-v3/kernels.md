# t cross-kernel agreement, 2026-09-19 03:51Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_10__small_nnum | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_158__min_Ops | unproved / unproved | unproved / refuted | unproved / unproved | refuted / refuted | refuted / unproved | refuted / unproved | unproved / refuted |
| mbpp_212__fourth_Power_Sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_220__replace_max_specialchar | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_228__all_Bits_Set_In_The_Given_Range | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_232__larg_nnum | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_24__binary_to_decimal | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_287__square_Sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_313__pos_nos | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_347__count_Squares | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_351__first_Element | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_355__count_Rectangles | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_358__moddiv_list | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_375__round_num | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| mbpp_436__neg_nos | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_467__decimal_to_Octal | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_472__check_Consecutive | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | timeout / timeout | unproved / refuted | unproved / refuted |
| mbpp_47__compute_Last_Digit | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_502__find | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_503__add_consecutive_nums | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_536__nth_items | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_565__split | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_566__sum_digits | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_629__Split | refuted / refuted | refuted / refuted | refuted / refuted (FLAKED) | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_670__decreasing_trend | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_675__sum_nums | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_680__increasing_trend | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_768__check_Odd_Parity | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_769__Diff | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_814__rombus_area | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_86__centered_hexagonal_number | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_882__parallelogram_perimeter | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_931__sum_series | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_935__series_sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_953__subset | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / refuted | refuted / refuted | timeout / timeout |
| mbpp_957__get_First_Set_Bit_Pos | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

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
| dafny | 0 | 1 | (none) |
| verus | 0 | 1 | (none) |
| spark | 0 | 1 | (none) |
| framac | 0 | 1 | (none) |
| lean | 0 | 1 | (none) |
| rocq | 0 | 1 | (none) |
| fstar | 0 | 0 | (none) |

Of the 0 tasks in six, none are blocked alone.
