# t cross-kernel agreement, 2026-09-17 22:27Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_221__first_even | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_249__intersection_array | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | timeout / timeout | abstain / abstain | timeout / timeout |
| mbpp_337__text_match_word | timeout / refuted | unproved / refuted | timeout / refuted | abstain / abstain | timeout / timeout | timeout / refuted | unproved / refuted |
| mbpp_378__move_first | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| mbpp_474__replace_char | unproved / unproved | unproved / refuted | timeout / timeout | abstain / abstain | unproved / unproved | unproved / refuted | abstain / abstain |
| mbpp_517__largest_pos | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_518__sqrt_root | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| mbpp_586__split_Arr | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| mbpp_663__find_max_val | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / unproved | unproved / refuted |
| mbpp_668__replace | refuted / refuted | refuted / refuted | refuted / malformed | abstain / abstain | unproved / unproved | refuted / refuted | abstain / abstain |
| mbpp_786__right_insertion | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | timeout / refuted | unproved / refuted |
| mbpp_800__remove_all_spaces | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | unproved / unproved | refuted / refuted | abstain / abstain |
| mbpp_802__count_Rotation | refuted / refuted | refuted / refuted | unproved / refuted | refuted / refuted | refuted / unproved | refuted / refuted | refuted / refuted |
| mbpp_871__are_Rotations | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | timeout / refuted | unproved / unproved |
| mbpp_897__is_Word_Present | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_943__combine_lists | refuted / refuted | refuted / refuted | timeout / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_221__first_even.dfy` bbf9b989c4a5a2d4…, `mbpp_221__first_even.rs` 8bb8eef05ed67e0a…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| framac | 1 | 0 | mbpp_378__move_first |
| dafny | 0 | 0 | (none) |
| verus | 0 | 0 | (none) |
| spark | 0 | 0 | (none) |
| lean | 0 | 0 | (none) |
| rocq | 0 | 0 | (none) |
| fstar | 0 | 0 | (none) |

Of the 1 tasks in six, 1 is framac alone.
