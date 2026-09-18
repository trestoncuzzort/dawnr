# t cross-kernel agreement, 2026-09-17 22:22Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_161__remove_elements | refuted / refuted | refuted / refuted | malformed / malformed | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_3__is_not_prime | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / timeout | unproved / refuted |
| mbpp_517__largest_pos | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_518__sqrt_root | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| mbpp_593__removezero_ip | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / refuted | abstain / abstain |
| mbpp_663__find_max_val | unproved / refuted | unproved / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / unproved | unproved / refuted |
| mbpp_664__average_Even | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| mbpp_730__consecutive_duplicates | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| mbpp_786__right_insertion | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| mbpp_824__remove_even | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| mbpp_852__remove_negs | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | timeout / timeout |
| mbpp_865__ntimes_list | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | verified / refuted | verified / refuted |
| mbpp_908__find_fixed_point | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_161__remove_elements.dfy` 072d7b70d4110135…, `mbpp_161__remove_elements.rs` d89be2859896ccda…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| dafny | 0 | 0 | (none) |
| verus | 0 | 1 | (none) |
| spark | 0 | 0 | (none) |
| framac | 0 | 1 | (none) |
| lean | 0 | 3 | (none) |
| rocq | 0 | 2 | (none) |
| fstar | 0 | 1 | (none) |

Of the 0 tasks in six, none are blocked alone.
