# t cross-kernel agreement, 2026-09-17 23:54Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_238__number_of_substrings | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_365__count_Digit | unproved / unproved | refuted / refuted | malformed / malformed | abstain / abstain | unproved / refuted | refuted / refuted | abstain / abstain |
| mbpp_388__highest_Power_of_2 | refuted / refuted | refuted / refuted | timeout / refuted | unproved / refuted | refuted / refuted | unproved / refuted | refuted / refuted |
| mbpp_505__re_order | unproved / unproved | malformed / malformed | refuted / malformed | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_552__Seq_Linear | unproved / refuted | unproved / refuted | timeout / timeout | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| mbpp_565__split | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_610__remove_kth_element | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| mbpp_629__Split | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | timeout / timeout | timeout / refuted | unproved / refuted |
| mbpp_664__average_Even | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| mbpp_668__replace | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | timeout / timeout | timeout / refuted | abstain / abstain |
| mbpp_732__replace_specialchar | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / refuted | abstain / abstain |
| mbpp_804__is_Product_Even | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted |
| mbpp_871__are_Rotations | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | timeout / refuted | unproved / unproved |
| mbpp_883__div_of_nums | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_890__find_Extra | unproved / refuted | unproved / refuted | unproved / refuted | refuted / refuted | unproved / unproved | refuted / refuted | unproved / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_238__number_of_substrings.dfy` fdc0e8d8fdbeeb2d…, `mbpp_238__number_of_substrings.rs` a60b3f6813aa2f7e…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| lean | 1 | 0 | mbpp_804__is_Product_Even |
| dafny | 0 | 0 | (none) |
| verus | 0 | 0 | (none) |
| spark | 0 | 0 | (none) |
| framac | 0 | 0 | (none) |
| rocq | 0 | 0 | (none) |
| fstar | 0 | 0 | (none) |

Of the 1 tasks in six, 1 is lean alone.
