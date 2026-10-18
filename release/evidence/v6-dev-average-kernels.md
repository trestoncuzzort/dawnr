# t cross-kernel agreement, 2026-10-18 08:51Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_186__check_literals | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | timeout / timeout | unproved / unproved | refuted / refuted |
| mbpp_251__insert_element | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | malformed / refuted | timeout / refuted | verified / refuted |
| mbpp_450__extract_string | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | timeout / timeout | verified / refuted |
| mbpp_476__big_sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_520__get_lcm | timeout / unproved | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | unproved / unproved | refuted / refuted |
| mbpp_543__count_digits | verified / unproved | verified / refuted | tool_error / tool_error | abstain / abstain | verified / refuted | verified / timeout | abstain / abstain |
| mbpp_549__odd_Num_Sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_92__is_undulating | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| mbpp_967__check | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / unproved | verified / unproved |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_186__check_literals.dfy` c774e3a93e0f22ac…, `mbpp_186__check_literals.rs` a800b1d94fd78475…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| dafny | 0 | 1 | (none) |
| verus | 0 | 1 | (none) |
| spark | 0 | 1 | (none) |
| framac | 0 | 4 | (none) |
| lean | 0 | 3 | (none) |
| rocq | 0 | 5 | (none) |
| fstar | 0 | 2 | (none) |

Of the 0 tasks in six, none are blocked alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| dafny | 9 | 7 | 6 of 7 (85%) | 0 |
| verus | 9 | 6 | 6 of 6 (100%) | 0 |
| spark | 9 | 6 | 6 of 6 (100%) | 0 |
| framac | 3 | 3 | 3 of 3 (100%) | 6 |
| lean | 9 | 4 | 4 of 4 (100%) | 0 |
| rocq | 9 | 4 | 2 of 4 (50%) | 0 |
| fstar | 8 | 6 | 5 of 6 (83%) | 1 |

Verified with the twin refuted in all seven columns: 2 of 9 tasks.
