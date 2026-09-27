# t cross-kernel agreement, 2026-09-27 06:30Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| humaneval_dafny_010_is_palindrome__make_palindrome | verified / refuted | unproved / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| humaneval_dafny_010_is_palindrome__reverse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | unproved / refuted | unproved / refuted |
| humaneval_dafny_034_unique__uniqueSorted | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | unproved / refuted | timeout / timeout |
| humaneval_dafny_038_encode_cyclic__decode_cyclic | verified / refuted | verified / refuted | timeout / refuted | abstain / abstain | timeout / timeout | timeout / unproved | unproved / refuted |
| humaneval_dafny_038_encode_cyclic__encode_cyclic | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | timeout / timeout | timeout / refuted | unproved / refuted |
| humaneval_dafny_077_iscube__cube_root | verified / refuted | unproved / refuted | unproved / refuted | timeout / timeout | unproved / unproved | unproved / refuted | unproved / refuted |
| humaneval_dafny_077_iscube__iscube | timeout / timeout | unproved / unproved | timeout / timeout | timeout / timeout | unproved / refuted | unproved / unproved | unproved / unproved |
| humaneval_dafny_088_sort_array__reverse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_161_solve__reverse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | verified / refuted |
| vericoding_da0018__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0031__solve | verified / refuted | verified / unproved | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_da0063__shellGame | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | unproved / unproved | verified / refuted |
| vericoding_da0071__solve | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0078__solve | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | lower-error / lower-error | unproved / refuted | verified / refuted |
| vericoding_da0080__solve | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0101__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / unproved | unproved / refuted | verified / refuted |
| vericoding_da0105__solve | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0108__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_da0110__solve | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0123__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0144__solve | verified / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_da0148__solve | timeout / refuted | unproved / refuted | timeout / refuted | timeout / timeout | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0151__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_da0153__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_da0157__solve | timeout / timeout | verified / refuted | verified / refuted | timeout / refuted | unproved / refuted | unproved / unproved | verified / refuted |
| vericoding_da0159__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0168__solve | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0173__solve | verified / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_da0205__solve | timeout / timeout | unproved / refuted | timeout / refuted | timeout / timeout | unproved / unproved | unproved / unproved | timeout / timeout |
| vericoding_da0239__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | lower-error / lower-error | unproved / refuted | verified / refuted |
| vericoding_da0246__solve | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_da0282__solve | timeout / refuted | verified / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0287__solve | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | lower-error / lower-error | unproved / refuted | verified / refuted |
| vericoding_da0292__checkFormattingHelper | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_da0308__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0368__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0399__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted |
| vericoding_da0429__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0482__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0484__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0497__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0505__solve | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0524__solve | verified / refuted | unproved / refuted | unproved / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_da0530__solve | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0531__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0538__computeMaxGroups | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0556__solveCakeProblem | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | unproved / refuted | unproved / refuted |
| vericoding_da0577__solve | vacuous / unproved | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0585__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0586__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0609__getRow | verified / refuted | unproved / refuted | malformed / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_da0642__solve | verified / refuted | verified / refuted | timeout / refuted | abstain / abstain | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0657__solve | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_da0659__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_db0006__lexicographicCompare | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_db0020__computeExp | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_db0020__modExpPow2_int | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | verified / refuted |
| vericoding_db0052__modExp_int | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | verified / refuted |
| vericoding_db0052__pow | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_db0053__modExp_int | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_dd0356__mod | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_dd0518__findAddends | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_dd0794__sumOfFourthPowerOfOddNumbers | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_dd0875__rolling_max | verified / refuted | unproved / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_dh0021__largest_divisor | verified / refuted | verified / refuted | verified / timeout | abstain / abstain | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_dh0051__modp | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| vericoding_dh0074__smallest_change | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dh0079__is_cube | timeout / refuted | unproved / refuted | verified / refuted | timeout / refuted | unproved / refuted | unproved / unproved | verified / timeout |
| vericoding_dh0141__factorial | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted | unproved / unproved | unproved / unproved | verified / refuted |
| vericoding_dh0141__special_factorial | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted | unproved / unproved | unproved / unproved | verified / refuted |
| vericoding_ds0053__sumArray | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted | unproved / unproved | unproved / unproved | unproved / refuted |
| vericoding_dt0088__leftShift | verified / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_dt0258__numpyBitwiseOr | refuted / unproved | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted |
| vericoding_dt0555__insertSorted | verified / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `humaneval_dafny_010_is_palindrome__make_palindrome.dfy` d923f17f67983bae…, `humaneval_dafny_010_is_palindrome__make_palindrome.rs` 0f1446803491aaf0…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| lean | 3 | 46 | humaneval_dafny_088_sort_array__reverse, humaneval_dafny_161_solve__reverse, vericoding_da0399__solve |
| rocq | 3 | 53 | vericoding_da0123__solve, vericoding_da0538__computeMaxGroups, vericoding_da0659__solve |
| dafny | 0 | 6 | (none) |
| verus | 0 | 24 | (none) |
| spark | 0 | 21 | (none) |
| framac | 0 | 38 | (none) |
| fstar | 0 | 19 | (none) |

Of the 6 tasks in six, 3 are lean alone, 3 are rocq alone.
