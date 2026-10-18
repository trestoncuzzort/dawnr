# t cross-kernel agreement, 2026-10-18 05:40Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_11__remove_Occ | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| mbpp_200__position_max | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | timeout / unproved | timeout / refuted |
| mbpp_251__insert_element | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | malformed / refuted | timeout / refuted | verified / refuted |
| mbpp_450__extract_string | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | timeout / timeout | verified / refuted |
| mbpp_476__big_sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_543__count_digits | unproved / unproved | refuted / refuted | tool_error / tool_error | abstain / abstain | unproved / refuted | refuted / refuted | abstain / abstain |
| mbpp_549__odd_Num_Sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_708__Convert | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_829__second_frequent | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_92__is_undulating | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_11__remove_Occ.dfy` 8ac3253cda4dc176…, `mbpp_11__remove_Occ.rs` 21014eb5d096f0d4…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| rocq | 1 | 3 | mbpp_92__is_undulating |
| dafny | 0 | 0 | (none) |
| verus | 0 | 2 | (none) |
| spark | 0 | 0 | (none) |
| framac | 0 | 2 | (none) |
| lean | 0 | 3 | (none) |
| fstar | 0 | 0 | (none) |

Of the 1 tasks in six, 1 is rocq alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| dafny | 10 | 6 | 6 of 6 (100%) | 0 |
| verus | 10 | 4 | 4 of 4 (100%) | 0 |
| spark | 10 | 6 | 6 of 6 (100%) | 0 |
| framac | 5 | 4 | 4 of 4 (100%) | 5 |
| lean | 10 | 3 | 3 of 3 (100%) | 0 |
| rocq | 10 | 2 | 2 of 2 (100%) | 0 |
| fstar | 9 | 6 | 6 of 6 (100%) | 1 |

Verified with the twin refuted in all seven columns: 2 of 10 tasks.
