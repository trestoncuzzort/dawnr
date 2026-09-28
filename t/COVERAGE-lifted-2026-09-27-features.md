# t cross-kernel agreement, 2026-09-27 21:55Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| humaneval_dafny_005_intersperse__intersperse | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| humaneval_dafny_006_parse_nested_parens__parse_paren_group | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| humaneval_dafny_035_max_element__max_element | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_038_encode_cyclic__decode_cyclic | verified / refuted | verified / refuted | timeout / refuted | abstain / abstain | timeout / timeout | timeout / unproved | unproved / refuted |
| humaneval_dafny_052_below_threshold__below_threshold | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_077_iscube__iscube | timeout / timeout | unproved / unproved | timeout / timeout | timeout / timeout | unproved / refuted | unproved / unproved | unproved / unproved |
| humaneval_dafny_163_generate_integers__generate_integers | verified / refuted | unproved / unproved | timeout / refuted | abstain / abstain | timeout / timeout | malformed / malformed | unproved / unproved |
| vericoding_da0017__solve | verified / refuted | verified / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0018__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0026__solve | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0029__solve | verified / refuted | unproved / refuted | timeout / refuted | malformed / malformed | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_da0031__solve | verified / refuted | verified / unproved | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_da0035__solve | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_da0043__solve | timeout / timeout | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0044__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0046__minimumMoves | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0062__solve | verified / unproved | unproved / refuted | timeout / timeout | verified / unproved | verified / unproved | unproved / malformed | verified / refuted |
| vericoding_da0063__shellGame | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | unproved / unproved | verified / refuted |
| vericoding_da0071__solve | verified / refuted | unproved / refuted | verified / refuted | malformed / malformed | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0078__solve | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_da0080__solve | verified / refuted | unproved / refuted | verified / refuted | timeout / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_da0085__findMinimumTotalDistance | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0086__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0101__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0105__solve | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0108__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_da0110__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0113__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_da0121__solve | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0123__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0131__solve | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | timeout / refuted |
| vericoding_da0144__solve | verified / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | abstain / abstain | unproved / refuted |
| vericoding_da0145__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0148__solve | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0151__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_da0153__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | malformed / malformed |
| vericoding_da0157__solve | timeout / timeout | verified / refuted | verified / refuted | timeout / refuted | unproved / refuted | verified / unproved | verified / refuted |
| vericoding_da0159__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0168__solve | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0172__solve | unproved / refuted | unproved / unproved | timeout / refuted | abstain / abstain | unproved / unproved | abstain / abstain | unproved / refuted |
| vericoding_da0173__solve | verified / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_da0174__solve | verified / refuted | malformed / malformed | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | timeout / timeout |
| vericoding_da0176__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0178__solve | verified / refuted | verified / unproved | timeout / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0188__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0201__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0205__solve | timeout / timeout | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / unproved | timeout / timeout |
| vericoding_da0217__solve | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_da0239__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_da0246__solve | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_da0282__solve | timeout / refuted | verified / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0285__solve | verified / refuted | unproved / unproved | timeout / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0287__solve | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0296__solveGraph | verified / unproved | verified / unproved | verified / refuted | abstain / abstain | timeout / timeout | abstain / abstain | verified / refuted |
| vericoding_da0297__calculateDistances | verified / unproved | verified / unproved | verified / refuted | abstain / abstain | timeout / unproved | abstain / abstain | malformed / malformed |
| vericoding_da0305__solve | unproved / refuted | unproved / unproved | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_da0308__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0326__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0328__solve | unproved / refuted | unproved / unproved | timeout / refuted | abstain / abstain | unproved / unproved | abstain / abstain | timeout / refuted |
| vericoding_da0333__solve | verified / refuted | malformed / malformed | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | lower-error / lower-error |
| vericoding_da0334__computeCombination | timeout / refuted | timeout / timeout | abstain / abstain | timeout / refuted | abstain / abstain | timeout / refuted | timeout / timeout |
| vericoding_da0334__computeModInverse | verified / timeout | verified / unproved | abstain / abstain | verified / timeout | abstain / abstain | verified / unproved | verified / timeout |
| vericoding_da0334__solve | timeout / refuted | timeout / refuted | abstain / abstain | timeout / refuted | abstain / abstain | timeout / refuted | timeout / timeout |
| vericoding_da0345__solve | unproved / refuted | unproved / unproved | timeout / refuted | abstain / abstain | unproved / unproved | abstain / abstain | malformed / malformed |
| vericoding_da0360__solve | verified / refuted | verified / unproved | timeout / refuted | abstain / abstain | unproved / unproved | abstain / abstain | malformed / malformed |
| vericoding_da0368__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_da0375__solveCase | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0386__solve | timeout / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | unproved / refuted |
| vericoding_da0396__solve | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | unproved / refuted |
| vericoding_da0399__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0409__solveRivalDistance | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0423__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0429__solve | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_da0469__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0470__solve | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| vericoding_da0472__solve | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_da0476__solve | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / unproved | verified / refuted | unproved / refuted |
| vericoding_da0478__solve | verified / refuted | verified / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0482__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0484__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0489__solve | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_da0497__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0505__solve | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0517__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | malformed / malformed |
| vericoding_da0523__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_da0524__solve | verified / refuted | unproved / refuted | unproved / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_da0529__solve | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_da0530__solve | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0531__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0538__computeMaxGroups | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0556__solveCakeProblem | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted |
| vericoding_da0577__solve | vacuous / unproved | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0585__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_da0586__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_da0609__getRow | verified / refuted | unproved / refuted | malformed / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_da0642__solve | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0657__solve | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_da0659__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_db0020__modExpPow2_int | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted |
| vericoding_db0034__modPowExec | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_db0052__modExp_int | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted |
| vericoding_db0053__modExp_int | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_dd0040__query | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0041__queryFast | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_dd0130__mCountMin | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / unproved | unproved / refuted |
| vericoding_dd0131__mPeekSum | verified / refuted | unproved / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| vericoding_dd0133__binarySearchRec | verified / refuted | unproved / unproved | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_dd0144__barrier | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dd0356__mod | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| vericoding_dd0493__queryFast | verified / refuted | verified / malformed | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_dd0508__mergeSimple | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_dd0517__prodAndCount | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | unproved / refuted |
| vericoding_dd0518__findAddends | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_dd0643__sharedElements | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| vericoding_dd0668__sumOfCommonDivisors | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / unproved | unproved / refuted |
| vericoding_dd0716__extractRearChars | verified / refuted | malformed / malformed | verified / refuted | timeout / timeout | verified / timeout | verified / refuted | verified / refuted |
| vericoding_dd0794__sumOfFourthPowerOfOddNumbers | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_dh0008__sum_product | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | timeout / refuted |
| vericoding_dh0021__largest_divisor | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_dh0024__remove_duplicates | verified / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | verified / refuted |
| vericoding_dh0051__modp | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| vericoding_dh0073__will_it_fly | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_dh0074__smallest_change | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dh0079__is_cube | timeout / refuted | unproved / refuted | verified / refuted | timeout / refuted | unproved / refuted | unproved / unproved | verified / timeout |
| vericoding_dh0112__exchange | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | unproved / unproved | unproved / refuted |
| vericoding_dh0141__special_factorial | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted | unproved / unproved | unproved / unproved | verified / refuted |
| vericoding_dj0077__splitArray | verified / unproved | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / unproved | verified / refuted |
| vericoding_dj0142__binarySearchRecursive | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | unproved / refuted | verified / refuted |
| vericoding_ds0053__sumArray | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted | unproved / unproved | malformed / unproved | unproved / refuted |
| vericoding_dt0088__leftShift | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_dt0258__numpyBitwiseOr | refuted / unproved | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted |
| vericoding_dt0662__ntypes | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved |
| vericoding_dv0079__twoSum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | timeout / refuted |
| vericoding_dv0131__binarySearchLoop | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_dv0139__doubleQuadruple | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0158__multipleReturns | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0171__swap | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0172__swapArithmetic | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0173__swapBitvectors | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0176__swapSimultaneous | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `humaneval_dafny_005_intersperse__intersperse.dfy` d572143f7643ab8f…, `humaneval_dafny_005_intersperse__intersperse.rs` 2e3ec3328cc4ae2f…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| lean | 9 | 62 | vericoding_da0113__solve, vericoding_da0239__solve, vericoding_da0368__solve, vericoding_da0523__solve, vericoding_da0585__solve, vericoding_da0586__solve, vericoding_db0020__modExpPow2_int, vericoding_db0034__modPowExec, vericoding_db0052__modExp_int |
| framac | 4 | 59 | vericoding_da0026__solve, vericoding_da0168__solve, vericoding_da0530__solve, vericoding_dv0139__doubleQuadruple |
| fstar | 1 | 28 | vericoding_da0556__solveCakeProblem |
| dafny | 0 | 14 | (none) |
| verus | 0 | 45 | (none) |
| spark | 0 | 31 | (none) |
| rocq | 0 | 62 | (none) |

Of the 14 tasks in six, 9 are lean alone, 4 are framac alone, 1 is fstar alone.
