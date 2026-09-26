# t cross-kernel agreement, 2026-09-26 20:26Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| humaneval_dafny_024_largest_divisor__largest_divisor | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_041_car_race_collision__car_race_collision | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_042_incr_list__incr_list | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_046_fib4__fib4 | verified / refuted | unproved / refuted | timeout / timeout | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| humaneval_dafny_053_add__add | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_055_fib__computeFib | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / unproved | unproved / refuted |
| humaneval_dafny_060_sum_to_n__sum_to_n | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_062_derivative__derivative | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_063_fibfib__computeFibFib | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / unproved | unproved / refuted |
| humaneval_dafny_068_pluck__pluck | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | timeout / timeout | timeout / refuted | verified / unproved |
| humaneval_dafny_077_iscube__cube_root | verified / refuted | unproved / refuted | unproved / refuted | timeout / timeout | unproved / unproved | unproved / refuted | unproved / refuted |
| humaneval_dafny_083_starts_one_ends__starts_one_ends | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| humaneval_dafny_088_sort_array__reverse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_092_any_int__any_int | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_097_multiply__multiply | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_102_choose_num__choose_num | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| humaneval_dafny_135_can_arrange__can_arrange | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| humaneval_dafny_150_x_or_y__x_or_y | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | unproved / refuted |
| humaneval_dafny_157_right_angle_triangle__right_angle_triangle | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_159_eat__eat | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_163_generate_integers__max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0001__solve | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0010__solve | verified / refuted | unproved / refuted | verified / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0036__solve | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0049__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0057__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | unproved / refuted |
| vericoding_da0060__computeDistanceToHouse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0084__solve | timeout / refuted | unproved / refuted | verified / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0119__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0133__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0180__solve | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | unproved / refuted | unproved / unproved | verified / refuted |
| vericoding_da0190__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0211__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0212__gildCells | timeout / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | timeout / refuted | verified / refuted |
| vericoding_da0229__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0233__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_da0234__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0278__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0347__solve | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0366__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0426__solve | verified / unproved | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_da0475__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0493__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0500__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0513__solve | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| vericoding_da0522__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0533__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0539__calculateMaxPies | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0554__countEvenOddPairs | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0615__calculateBlackSquares | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0644__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0658__solve | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0662__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0664__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0668__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_da0671__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0674__solve | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_da0676__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_db0020__computeExp | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_db0052__pow | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_dd0008__getInsertIndex | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_dd0045__concat | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_dd0052__calDiv | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0053__sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0054__canyonSearch | timeout / refuted | verified / refuted | verified / timeout | timeout / timeout | timeout / timeout | timeout / refuted | timeout / timeout |
| vericoding_dd0058__double_array_elements | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0059__doubleQuadruple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0071__maxArray | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0075__multipleReturns | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0077__quotient | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0079__replace | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0080__m | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0081__reverse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_dd0085__swap | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0086__swapArithmetic | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0088__swap | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0089__swapSimultaneous | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0090__testArrayElements | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0091__triple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0092__triple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0093__triple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0094__triple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0096__updateElements | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_dd0102__fibonacci1 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dd0124__mfirstNegative | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / unproved |
| vericoding_dd0155__invertArray | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_dd0167__longestPrefix | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / unproved | timeout / refuted | unproved / refuted |
| vericoding_dd0187__findPositionOfElement | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| vericoding_dd0225__computePower | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0256__max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0271__incrementArray | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0275__lookForMin | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0342__calcR | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / unproved | verified / unproved | verified / refuted |
| vericoding_dd0355__mod2 | timeout / refuted | verified / refuted | verified / refuted | timeout / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_dd0454__getmini | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0464__counting_bits | unproved / refuted | unproved / refuted | timeout / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_dd0533__euclid | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0534__intDiv | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_dd0539__reverse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted |
| vericoding_dd0580__appendArray | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_dd0586__getEven | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | verified / refuted |
| vericoding_dd0611__maximum | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_dd0634__expt | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_dd0635__factorial | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0646__triangularPrismVolume | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0653__containsSequence | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted |
| vericoding_dd0654__allSequencesEqualLength | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | unproved / unproved | timeout / unproved | verified / refuted |
| vericoding_dd0663__smallestListLength | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0669__multiply | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0678__pentagonPerimeter | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0679__minOfThree | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0682__cubeVolume | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0684__replaceLastElement | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0689__elementWiseDivision | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0690__splitArray | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0696__subtractSequences | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0701__maxLengthList | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | verified / refuted | timeout / refuted | verified / refuted |
| vericoding_dd0703__elementAtIndexAfterRotation | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0722__lastDigit | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0724__cubeSurfaceArea | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0727__calculateLoss | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0730__minLengthSublist | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | verified / refuted | timeout / refuted | verified / refuted |
| vericoding_dd0732__getFirstElements | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0739__findOddNumbers | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | timeout / refuted | timeout / timeout |
| vericoding_dd0740__differenceSumCubesAndSumNumbers | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0749__factorialOfLastDigit | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0752__squarePyramidSurfaceArea | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0758__isArmstrong | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0762__lucidNumbers | verified / refuted | verified / refuted | timeout / refuted | abstain / abstain | timeout / timeout | verified / refuted | verified / refuted |
| vericoding_dd0765__removeElement | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_dd0767__elementWiseDivide | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0771__swapFirstAndLast | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_dd0772__areaOfLargestTriangleInSemicircle | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0777__isBreakEven | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0778__nthNonagonalNumber | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0785__rotateRight | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | unproved / refuted | verified / unproved | verified / refuted |
| vericoding_dd0791__isMonthWith30Days | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0800__countLists | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0804__countEqualNumbers | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0809__isSmaller | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted |
| vericoding_dd0826__climbStairs | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / unproved | unproved / refuted |
| vericoding_dd0830__iterativeFactorial | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0839__findMin | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0847__divMod1 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0848__hoareTripleReqEns | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0873__intersperse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dd0897__find_min_index | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0923__longestZero | timeout / unproved | malformed / malformed | verified / refuted | verified / refuted | unproved / refuted | timeout / refuted | timeout / timeout |
| vericoding_dh0005__insertDelimiter | verified / refuted | malformed / malformed | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dh0040__decode_cyclic | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| vericoding_dh0043__car_race_collision | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| vericoding_dh0044__incr_list | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | abstain / abstain | verified / refuted |
| vericoding_dh0048__fib4 | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_dh0055__checkBelowThreshold | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| vericoding_dh0056__add | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dh0058__fib | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dh0063__sum_to_n | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dh0064__derivative | verified / refuted | malformed / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dh0065__fibfib | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_dh0078__cube_root | verified / refuted | unproved / refuted | unproved / refuted | timeout / timeout | unproved / unproved | verified / refuted | unproved / refuted |
| vericoding_dh0102__chooseNum | verified / unproved | verified / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dh0141__factorial | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted | unproved / unproved | unproved / unproved | verified / refuted |
| vericoding_dh0152__x_or_y | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | unproved / refuted |
| vericoding_dj0004__myfun | verified / refuted | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_dj0014__myfun | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | verified / refuted |
| vericoding_dj0015__myfun | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0020__findMax | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0026__myfun | verified / refuted | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_dj0027__myfun | verified / refuted | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_dj0028__myfun | verified / refuted | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_dj0037__myfun | verified / refuted | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_dj0038__myfun | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0039__myfun | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0040__myfun | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0041__myfun | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0044__myfun | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0045__myfun | verified / refuted | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| vericoding_dj0048__myfun | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0073__replaceLastElement | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_dj0075__insertBeforeEach | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_dj0076__elementWiseDivision | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / timeout | verified / refuted | verified / refuted |
| vericoding_dj0078__elementWiseSubtract | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0079__elementWiseSubtract | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0080__allElementsEquals | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0088__isGreater | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0111__removeKthElement | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0113__elementWiseDivide | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0116__reverseToK | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_dj0130__findFirstOdd | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| vericoding_dj0132__isSmaller | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / unproved | verified / unproved | verified / refuted |
| vericoding_dj0135__arithmeticWeird | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0136__arrayAppend | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_dj0137__arrayConcat | verified / refuted | verified / refuted | verified / timeout | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0143__cubes | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0148__intersperse | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dj0156__removeElement | verified / refuted | verified / refuted | timeout / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0160__reverse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_dj0170__binarySearchExists | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_ds0010__clip | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_ds0015__cumProd | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_ds0016__cumSum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_ds0020__floorDivide | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| vericoding_ds0026__invert | verified / unproved | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_ds0029__lcmInt | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_ds0033__max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_ds0049__sign | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_ds0051__square | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_ds0052__subtract | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0015__insertionSort | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_dv0038__maxOfList | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| vericoding_dv0039__maxOfList | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0042__maxStrength | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0057__nthUglyNumber | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0062__removeDuplicates | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_dv0084__kthElementImpl | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0085__multiply | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0086__minOfThree | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0090__isGreater | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0104__firstEvenOddDifference | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / timeout | timeout / refuted | verified / refuted |
| vericoding_dv0112__swapFirstAndLast | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_dv0135__compare | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0138__doubleArrayElements | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0152__append | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0162__removeFront | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0163__concat | verified / refuted | verified / refuted | verified / timeout | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0164__replace | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0165__reverse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0177__testArrayElements | verified / refuted | verified / refuted | timeout / refuted | abstain / abstain | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_dv0178__triple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0179__triple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0180__triple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0181__triple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0183__update_elements | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `humaneval_dafny_024_largest_divisor__largest_divisor.dfy` 431a574f4506be04…, `humaneval_dafny_024_largest_divisor__largest_divisor.rs` 98dce1112a7a8702…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| rocq | 14 | 70 | vericoding_da0060__computeDistanceToHouse, vericoding_da0119__solve, vericoding_da0211__solve, vericoding_da0475__solve, vericoding_da0493__solve, vericoding_da0533__solve, vericoding_da0539__calculateMaxPies, vericoding_da0615__calculateBlackSquares, vericoding_da0664__solve, vericoding_da0668__solve, vericoding_dd0539__reverse, vericoding_dd0634__expt, vericoding_dd0653__containsSequence, vericoding_dh0065__fibfib |
| lean | 11 | 65 | humaneval_dafny_088_sort_array__reverse, vericoding_dd0586__getEven, vericoding_dd0765__removeElement, vericoding_dd0771__swapFirstAndLast, vericoding_dd0809__isSmaller, vericoding_dj0014__myfun, vericoding_dj0076__elementWiseDivision, vericoding_dj0160__reverse, vericoding_ds0015__cumProd, vericoding_ds0016__cumSum, vericoding_ds0029__lcmInt |
| framac | 7 | 44 | humaneval_dafny_097_multiply__multiply, vericoding_da0658__solve, vericoding_dd0684__replaceLastElement, vericoding_dd0690__splitArray, vericoding_dd0732__getFirstElements, vericoding_dd0749__factorialOfLastDigit, vericoding_dj0111__removeKthElement |
| spark | 3 | 24 | vericoding_dd0533__euclid, vericoding_dd0758__isArmstrong, vericoding_dd0830__iterativeFactorial |
| verus | 2 | 29 | humaneval_dafny_062_derivative__derivative, vericoding_dj0143__cubes |
| dafny | 0 | 10 | (none) |
| fstar | 0 | 28 | (none) |

Of the 37 tasks in six, 14 are rocq alone, 11 are lean alone, 7 are framac alone, 3 are spark alone, 2 are verus alone.
