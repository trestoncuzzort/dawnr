# t cross-kernel agreement, 2026-10-18 03:41Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_133__sum_negativenum | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | unproved / refuted |
| mbpp_244__next_Perfect_Square | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| mbpp_42__find_Sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_449__check_Triangle | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved |
| mbpp_450__extract_string | unproved / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | timeout / timeout | timeout / timeout |
| mbpp_476__big_sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_549__odd_Num_Sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_634__even_Power_Sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_92__is_undulating | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_133__sum_negativenum.dfy` cc23e4786f0fe9b8…, `mbpp_133__sum_negativenum.rs` 199eb96af55678cb…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| dafny | 0 | 1 | (none) |
| verus | 0 | 1 | (none) |
| spark | 0 | 0 | (none) |
| framac | 0 | 1 | (none) |
| lean | 0 | 2 | (none) |
| rocq | 0 | 3 | (none) |
| fstar | 0 | 2 | (none) |

Of the 0 tasks in six, none are blocked alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| dafny | 9 | 6 | 6 of 6 (100%) | 0 |
| verus | 9 | 6 | 6 of 6 (100%) | 0 |
| spark | 9 | 7 | 7 of 7 (100%) | 0 |
| framac | 7 | 6 | 6 of 6 (100%) | 2 |
| lean | 9 | 5 | 5 of 5 (100%) | 0 |
| rocq | 9 | 5 | 4 of 5 (80%) | 0 |
| fstar | 9 | 6 | 5 of 6 (83%) | 0 |

Verified with the twin refuted in all seven columns: 4 of 9 tasks.
