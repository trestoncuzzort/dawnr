# t cross-kernel agreement, 2026-10-18 03:19Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_133__sum_negativenum | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | unproved / refuted |
| mbpp_186__check_literals | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | unproved / unproved | unproved / unproved | refuted / refuted |
| mbpp_200__position_max | unproved / unproved | unproved / refuted | refuted / refuted | abstain / abstain | timeout / unproved | refuted / unproved | unproved / refuted |
| mbpp_207__find_longest_repeating_subseq | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / unproved | refuted / refuted | refuted / refuted |
| mbpp_251__insert_element | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | malformed / refuted | timeout / refuted | verified / refuted |
| mbpp_337__text_match_word | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | unproved / refuted | abstain / abstain |
| mbpp_377__remove_Char | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_450__extract_string | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | timeout / timeout | verified / refuted |
| mbpp_459__remove_uppercase | verified / timeout | verified / refuted | verified / refuted | abstain / abstain | verified / timeout | lower-error / lower-error | abstain / abstain |
| mbpp_476__big_sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_543__count_digits | verified / unproved | verified / refuted | tool_error / tool_error | abstain / abstain | verified / refuted | verified / malformed | abstain / abstain |
| mbpp_549__odd_Num_Sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_634__even_Power_Sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_133__sum_negativenum.dfy` 636f117bbe9a30f0…, `mbpp_133__sum_negativenum.rs` d05ab26c489adadd…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| dafny | 0 | 2 | (none) |
| verus | 0 | 1 | (none) |
| spark | 0 | 1 | (none) |
| framac | 0 | 5 | (none) |
| lean | 0 | 3 | (none) |
| rocq | 0 | 5 | (none) |
| fstar | 0 | 3 | (none) |

Of the 0 tasks in six, none are blocked alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| dafny | 13 | 8 | 6 of 8 (75%) | 0 |
| verus | 13 | 7 | 7 of 7 (100%) | 0 |
| spark | 13 | 7 | 7 of 7 (100%) | 0 |
| framac | 5 | 3 | 3 of 3 (100%) | 8 |
| lean | 13 | 6 | 5 of 6 (83%) | 0 |
| rocq | 13 | 4 | 3 of 4 (75%) | 0 |
| fstar | 10 | 5 | 5 of 5 (100%) | 3 |

Verified with the twin refuted in all seven columns: 3 of 13 tasks.
