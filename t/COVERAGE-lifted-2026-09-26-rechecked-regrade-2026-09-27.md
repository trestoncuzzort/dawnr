# t cross-kernel agreement, 2026-09-27 07:13Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| humaneval_dafny_010_is_palindrome__reverse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | unproved / refuted | unproved / refuted |
| humaneval_dafny_011_string_xor__string_xor | verified / unproved | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| humaneval_dafny_031_is_prime__is_prime | vacuous / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| humaneval_dafny_034_unique__uniqueSorted | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | unproved / refuted | timeout / timeout |
| humaneval_dafny_038_encode_cyclic__encode_cyclic | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | timeout / timeout | timeout / refuted | unproved / refuted |
| humaneval_dafny_112_reverse_delete__check_palindrome | verified / unproved | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| humaneval_dafny_130_tri__tri | timeout / refuted | abstain / abstain | timeout / unproved | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| humaneval_dafny_139_special_factorial__special_factorial | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | timeout / refuted |
| humaneval_dafny_146_specialfilter__specialFilter | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | unproved / unproved | timeout / refuted | timeout / timeout |
| humaneval_dafny_152_compare__compare | verified / unproved | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_161_solve__reverse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | verified / refuted |
| vericoding_da0003__solve | verified / decorative | verified / decorative | verified / decorative | verified / decorative | unproved / unproved | verified / decorative | verified / decorative |
| vericoding_da0014__solve | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / unproved | verified / refuted | verified / refuted |
| vericoding_da0047__findOptimalT | unproved / unproved | malformed / malformed | timeout / timeout | abstain / abstain | abstain / abstain | abstain / abstain | timeout / timeout |
| vericoding_da0054__solve | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0072__solve | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0090__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_da0120__solve | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0140__minBacteria | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0161__solve | verified / decorative | verified / decorative | verified / decorative | abstain / abstain | unproved / unproved | abstain / abstain | verified / decorative |
| vericoding_da0200__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0210__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / unproved | verified / refuted |
| vericoding_da0216__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| vericoding_da0263__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / unproved | unproved / refuted |
| vericoding_da0264__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_da0292__checkFormattingHelper | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_da0422__determineWinner | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / unproved | unproved / refuted |
| vericoding_da0466__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | timeout / timeout | abstain / abstain | malformed / malformed |
| vericoding_da0483__solve | verified / refuted | verified / malformed | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | timeout / refuted |
| vericoding_da0488__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0496__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0516__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | unproved / refuted |
| vericoding_da0519__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0540__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / unproved | unproved / refuted |
| vericoding_da0543__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_da0545__solve | verified / unproved | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | abstain / abstain | verified / refuted |
| vericoding_da0551__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_da0558__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | abstain / abstain |
| vericoding_da0562__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0569__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0584__solve | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_da0588__solve | unproved / refuted | unproved / refuted | timeout / refuted | timeout / unproved | unproved / refuted | unproved / unproved | timeout / refuted |
| vericoding_da0602__solve | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | unproved / refuted |
| vericoding_da0620__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0623__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | unproved / refuted |
| vericoding_da0624__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / unproved | unproved / refuted |
| vericoding_da0629__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0654__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| vericoding_da0667__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / unproved | verified / unproved |
| vericoding_da0672__solve | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | unproved / refuted |
| vericoding_da0675__solve | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | unproved / refuted |
| vericoding_db0006__lexicographicCompare | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_dd0050__binarySearch | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_dd0066__isPalindrome | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / unproved | timeout / unproved | verified / refuted |
| vericoding_dd0068__linearSearch | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0069__longestCommonPrefix | verified / refuted | verified / refuted | verified / refuted | lower-error / lower-error | unproved / timeout | unproved / refuted | verified / refuted |
| vericoding_dd0070__match | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0100__binarySearch | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_dd0105__mpositive | unproved / refuted | unproved / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / unproved |
| vericoding_dd0537__noDups | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dd0587__getTriple | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_dd0667__isInteger | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / unproved | timeout / unproved | verified / refuted |
| vericoding_dd0680__replaceBlanksWithChar | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0714__removeOddNumbers | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | timeout / refuted | timeout / refuted |
| vericoding_dd0723__findNegativeNumbers | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | timeout / refuted | timeout / refuted |
| vericoding_dd0736__replaceChars | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0742__splitStringIntoChars | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_dd0769__powerOfListElements | verified / unproved | verified / refuted | verified / refuted | verified / timeout | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_dd0782__replaceWithColon | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted |
| vericoding_dd0784__allCharactersSame | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | unproved / unproved | timeout / unproved | verified / refuted |
| vericoding_dd0789__isDecimalWithTwoPrecision | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0797__firstEvenOddIndices | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted |
| vericoding_dd0799__isEvenAtIndexEven | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / timeout | unproved / refuted | verified / refuted |
| vericoding_dh0011__string_xor | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| vericoding_dh0085__starts_one_ends | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_dh0101__make_a_pile | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | malformed / malformed |
| vericoding_dh0108__f | verified / unproved | malformed / malformed | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / timeout |
| vericoding_dh0110__digitSum | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dh0122__maximum | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dh0123__solution | verified / refuted | unproved / refuted | verified / refuted | timeout / unproved | verified / refuted | verified / refuted | unproved / refuted |
| vericoding_dh0125__get_odd_collatz | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_dh0127__next_odd_collatz_iter | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| vericoding_dh0133__tribonacci | timeout / refuted | abstain / abstain | timeout / timeout | verified / refuted | unproved / unproved | malformed / malformed | timeout / refuted |
| vericoding_dh0143__sum_squares | verified / unproved | verified / refuted | verified / refuted | verified / timeout | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_dh0154__compare | verified / unproved | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | abstain / abstain | verified / refuted |
| vericoding_dj0016__fibonacci | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / unproved | timeout / refuted | verified / refuted |
| vericoding_dj0057__isNonPrime | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | malformed / unproved | verified / refuted |
| vericoding_dj0058__squareNums | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0072__replaceBlanksWithChars | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / timeout | timeout / refuted | verified / refuted |
| vericoding_dj0089__findNegativeNumbers | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | timeout / refuted | verified / refuted |
| vericoding_dj0099__findOddNumbers | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | timeout / refuted | verified / refuted |
| vericoding_dj0110__primeNum | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_dj0128__sum | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | verified / refuted |
| vericoding_dj0133__getElementCheckProperty | unproved / refuted | unproved / refuted | verified / malformed | timeout / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_dj0161__rollingMax | verified / unproved | verified / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | verified / refuted |
| vericoding_ds0041__power | verified / unproved | verified / refuted | verified / refuted | verified / timeout | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_ds0046__right_shift | verified / unproved | verified / refuted | verified / refuted | verified / timeout | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_dt0257__bitwiseNot | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted |
| vericoding_dt0555__insertSorted | verified / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dv0008__countSumDivisibleBy | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0017__isArmstrong | verified / refuted | verified / refuted | abstain / abstain | timeout / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0061__rain | verified / unproved | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_dv0068__searchInsert | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_dv0069__semiOrderedPermutation | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted | verified / refuted | verified / refuted |
| vericoding_dv0073__solution | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0076__trapRainWater | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_dv0094__containsZ | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted |
| vericoding_dv0117__findFirstOccurrence | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | malformed / malformed | verified / refuted |
| vericoding_dv0118__allCharactersSame | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / unproved | timeout / unproved | verified / refuted |
| vericoding_dv0149__linearSearch | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| vericoding_dv0153__matchStrings | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `humaneval_dafny_010_is_palindrome__reverse.dfy` 0c2fbf396771e570…, `humaneval_dafny_010_is_palindrome__reverse.rs` 06e54319ec183722…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| lean | 5 | 53 | humaneval_dafny_161_solve__reverse, vericoding_dd0050__binarySearch, vericoding_dh0127__next_odd_collatz_iter, vericoding_dv0068__searchInsert, vericoding_dv0069__semiOrderedPermutation |
| framac | 2 | 52 | vericoding_da0054__solve, vericoding_da0072__solve |
| rocq | 2 | 60 | vericoding_dd0782__replaceWithColon, vericoding_dv0094__containsZ |
| verus | 1 | 27 | vericoding_dh0122__maximum |
| dafny | 0 | 19 | (none) |
| spark | 0 | 10 | (none) |
| fstar | 0 | 37 | (none) |

Of the 10 tasks in six, 5 are lean alone, 2 are framac alone, 2 are rocq alone, 1 is verus alone.
