# t cross-kernel agreement, 2026-09-17 23:57Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_192__check_String | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / unproved | refuted / refuted | refuted / refuted |
| mbpp_240__replace_list | refuted / refuted | refuted / refuted | unproved / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_412__remove_odd | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | timeout / timeout | unproved / unproved | unproved / refuted |
| mbpp_41__filter_evennumbers | unproved / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | timeout / timeout |
| mbpp_517__largest_pos | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted (FLAKED) | refuted / refuted | refuted / refuted |
| mbpp_632__move_zero | refuted / refuted | refuted / refuted | timeout / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_666__count_char | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / refuted | unproved / refuted |
| mbpp_730__consecutive_duplicates | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | timeout / timeout | timeout / refuted | unproved / refuted |
| mbpp_754__extract_index_list | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | timeout / timeout | refuted / refuted | timeout / timeout |
| mbpp_824__remove_even | unproved / refuted | unproved / refuted | timeout / refuted | verified / refuted (FLAKED) | timeout / timeout | unproved / refuted | timeout / timeout |
| mbpp_890__find_Extra | unproved / refuted | unproved / refuted | unproved / vacuous | refuted / refuted | unproved / refuted | refuted / refuted | unproved / refuted |
| mbpp_943__combine_lists | refuted / refuted | refuted / refuted | timeout / refuted | refuted / refuted | timeout / timeout | unproved / refuted | timeout / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_192__check_String.dfy` 6c73aed1f129b1c3…, `mbpp_192__check_String.rs` 956087739ad7d1aa…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| dafny | 0 | 1 | (none) |
| verus | 0 | 1 | (none) |
| spark | 0 | 0 | (none) |
| framac | 0 | 0 | (none) |
| lean | 0 | 1 | (none) |
| rocq | 0 | 1 | (none) |
| fstar | 0 | 1 | (none) |

Of the 0 tasks in six, none are blocked alone.
