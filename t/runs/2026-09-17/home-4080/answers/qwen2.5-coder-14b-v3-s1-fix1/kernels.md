# t cross-kernel agreement, 2026-09-17 22:17Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_230__replace_blank | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / refuted | abstain / abstain |
| mbpp_451__remove_whitespaces | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / unproved | abstain / abstain |
| mbpp_474__replace_char | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / refuted | abstain / abstain |
| mbpp_517__largest_pos | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_536__nth_items | timeout / refuted | malformed / refuted | timeout / timeout | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| mbpp_542__fill_spaces | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / refuted | abstain / abstain |
| mbpp_554__Split | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | timeout / refuted | timeout / timeout |
| mbpp_586__split_Arr | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| mbpp_627__find_First_Missing | unproved / refuted | unproved / refuted | timeout / timeout | refuted / refuted | unproved / refuted | refuted / refuted | unproved / refuted |
| mbpp_629__Split | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | timeout / refuted | timeout / timeout |
| mbpp_678__remove_spaces | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / unproved | abstain / abstain |
| mbpp_69__is_sublist | unproved / unproved | unproved / refuted | timeout / refuted | timeout / refuted | verified / refuted | timeout / refuted | verified / refuted |
| mbpp_754__extract_index_list | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | timeout / timeout | refuted / refuted | timeout / timeout |
| mbpp_817__div_of_nums | refuted / refuted | refuted / refuted | timeout / timeout | abstain / abstain | timeout / timeout | unproved / refuted | timeout / timeout |
| mbpp_824__remove_even | unproved / refuted | unproved / refuted | verified / refuted | timeout / refuted | timeout / timeout | timeout / refuted | timeout / timeout |
| mbpp_825__access_elements | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_852__remove_negs | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| mbpp_856__find_Min_Swaps | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_871__are_Rotations | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | timeout / refuted | unproved / unproved |
| mbpp_890__find_Extra | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| mbpp_899__check | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_9__find_Rotations | unproved / unproved | timeout / refuted | timeout / refuted | abstain / abstain | unproved / refuted | timeout / refuted | unproved / unproved |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_230__replace_blank.dfy` 3dc87335bf40e39a…, `mbpp_230__replace_blank.rs` 8b5eee0061a5cbd7…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| dafny | 0 | 3 | (none) |
| verus | 0 | 6 | (none) |
| spark | 0 | 2 | (none) |
| framac | 0 | 5 | (none) |
| lean | 0 | 5 | (none) |
| rocq | 0 | 6 | (none) |
| fstar | 0 | 3 | (none) |

Of the 0 tasks in six, none are blocked alone.
