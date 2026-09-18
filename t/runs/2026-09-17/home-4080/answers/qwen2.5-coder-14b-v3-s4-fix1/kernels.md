# t cross-kernel agreement, 2026-09-17 23:41Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_199__highest_Power_of_2 | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / refuted |
| mbpp_412__remove_odd | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| mbpp_41__filter_evennumbers | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| mbpp_518__sqrt_root | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| mbpp_586__split_Arr | unproved / refuted | unproved / refuted | malformed / malformed | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| mbpp_593__removezero_ip | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | timeout / unproved | refuted / refuted | abstain / abstain |
| mbpp_619__move_num | unproved / refuted | unproved / refuted | abstain / abstain | abstain / abstain | timeout / timeout | refuted / refuted | unproved / refuted |
| mbpp_629__Split | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | timeout / timeout | timeout / refuted | unproved / refuted |
| mbpp_66__pos_count | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | unproved / refuted |
| mbpp_673__convert | unproved / unproved | unproved / refuted | abstain / abstain | abstain / abstain | unproved / refuted | unproved / unproved | unproved / refuted |
| mbpp_69__is_sublist | unproved / unproved | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| mbpp_718__alternate_elements | verified / refuted | verified / refuted | verified / timeout | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| mbpp_733__find_first_occurrence | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_754__extract_index_list | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | timeout / timeout | refuted / refuted | timeout / timeout |
| mbpp_802__count_Rotation | refuted / refuted | refuted / refuted | vacuous / vacuous | refuted / refuted | refuted / unproved | refuted / refuted | refuted / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_199__highest_Power_of_2.dfy` bfbbf211483d75a3…, `mbpp_199__highest_Power_of_2.rs` 8b6460d41b3aac13…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| dafny | 0 | 0 | (none) |
| verus | 0 | 2 | (none) |
| spark | 0 | 1 | (none) |
| framac | 0 | 0 | (none) |
| lean | 0 | 3 | (none) |
| rocq | 0 | 3 | (none) |
| fstar | 0 | 0 | (none) |

Of the 0 tasks in six, none are blocked alone.
