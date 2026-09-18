# t cross-kernel agreement, 2026-09-17 23:50Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_168__frequency | refuted / refuted | refuted / refuted | timeout / refuted (FLAKED) | abstain / abstain | refuted / refuted | unproved / unproved | refuted / refuted |
| mbpp_220__replace_max_specialchar | unproved / unproved | refuted / refuted | timeout / timeout (FLAKED) | abstain / abstain | refuted / refuted | unproved / unproved | refuted / refuted |
| mbpp_240__replace_list | verified / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | verified / refuted | verified / refuted |
| mbpp_412__remove_odd | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| mbpp_434__text_match_one | unproved / refuted | unproved / refuted | timeout / refuted (FLAKED) | abstain / abstain | unproved / refuted | timeout / unproved | unproved / refuted |
| mbpp_498__gcd | unproved / unproved | unproved / refuted | timeout / refuted | timeout / unproved | unproved / refuted | unproved / unproved | unproved / refuted |
| mbpp_517__largest_pos | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_518__sqrt_root | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| mbpp_794__text_starta_endb | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_804__is_Product_Even | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted |
| mbpp_810__count_variable | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| mbpp_815__sort_by_dnf | refuted / refuted | refuted / refuted | timeout / refuted | lower-error / lower-error | timeout / timeout | unproved / unproved | refuted / refuted |
| mbpp_818__lower_ctr | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | timeout / refuted |
| mbpp_825__access_elements | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_890__find_Extra | unproved / refuted | unproved / refuted | unproved / refuted | refuted / refuted | unproved / unproved | refuted / refuted | unproved / refuted |
| mbpp_913__end_num | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| mbpp_973__left_rotate | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | unproved / refuted | refuted / refuted | refuted / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_168__frequency.dfy` 73deedf79b03e347…, `mbpp_168__frequency.rs` 76bea20d82fb7ae8…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| lean | 2 | 2 | mbpp_804__is_Product_Even, mbpp_913__end_num |
| dafny | 0 | 0 | (none) |
| verus | 0 | 2 | (none) |
| spark | 0 | 1 | (none) |
| framac | 0 | 1 | (none) |
| rocq | 0 | 1 | (none) |
| fstar | 0 | 0 | (none) |

Of the 2 tasks in six, 2 are lean alone.
