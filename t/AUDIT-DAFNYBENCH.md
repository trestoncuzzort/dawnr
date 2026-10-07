# Specification audit

Every one-edit mutant of each body, classed by the interpreter over the task's bounded domain (t/audit.py): **killed** (the spec rejects its result somewhere), **same** (computes the same everywhere), **diverges** (runs out of steps where the real body ends), **survivor** (computes something different, and the spec accepts it everywhere).

- tasks: 326; audited: 320; not audited: 4 no-input, 2 real-violates-spec
- behaviour-changing mutants the specs kill: 6829 of 7247 (94.2%)
- tasks whose spec admits a survivor: 53 of 320
- dafny: real body verified in 316 of 320; of those, a survivor proved too (a wrong program with a proof) in 44

| task | mutants | killed | same | diverges | survivors | proved by the kernel | a survivor: change at input |
|---|---|---|---|---|---|---|---|
| bbfny_tmp_tmpw4m0jvl0_enjoying__abs | 0 | 0 | 0 | 0 | 0 | 0 |  |
| bbfny_tmp_tmpw4m0jvl0_enjoying__max | 12 | 11 | 1 | 0 | 0 | 0 |  |
| bbfny_tmp_tmpw4m0jvl0_enjoying__multipleReturns | 33 | 24 | 8 | 0 | 1 | 1 | wrong-constant#5: `less := x - y;` -> `less := x - y + -1;` at x=0, y=1 -> real [1, -1], twin [1, -2] |
| clover_abs__abs | 10 | 8 | 2 | 0 | 0 | 0 |  |
| clover_array_product__arrayProduct | 28 | 22 | 4 | 2 | 0 | 0 |  |
| clover_array_sum__arraySum | 26 | 20 | 4 | 2 | 0 | 0 |  |
| clover_avg__computeAvg | 9 | 9 | 0 | 0 | 0 | 0 |  |
| clover_cal_ans__calDiv | 62 | 26 | 27 | 9 | 0 | 0 |  |
| clover_cal_sum__sum | 18 | 9 | 2 | 7 | 0 | 0 |  |
| clover_double_array_elements__double_array_elements | 20 | 18 | 0 | 2 | 0 | 0 |  |
| clover_double_quadruple__doubleQuadruple | 29 | 21 | 8 | 0 | 0 | 0 |  |
| clover_find__find | 24 | 20 | 2 | 2 | 0 | 0 |  |
| clover_integer_square_root__squareRoot | 22 | 16 | 2 | 4 | 0 | 0 |  |
| clover_is_even__computeIsEven | 7 | 7 | 0 | 0 | 0 | 0 |  |
| clover_linear_search1__linearSearch | 12 | 10 | 0 | 2 | 0 | 0 |  |
| clover_min_array__minArray | 24 | 19 | 3 | 2 | 0 | 0 |  |
| clover_min_of_two__min | 12 | 11 | 1 | 0 | 0 | 0 |  |
| clover_multi_return__multipleReturns | 33 | 25 | 8 | 0 | 0 | 0 |  |
| clover_quotient__quotient | 51 | 35 | 8 | 8 | 0 | 0 |  |
| clover_replace__replace | 27 | 24 | 0 | 3 | 0 | 0 |  |
| clover_return_seven__m | 4 | 4 | 0 | 0 | 0 | 0 |  |
| clover_rotate__rotate | 28 | 23 | 2 | 3 | 0 | 0 |  |
| clover_swap__swap | 69 | 48 | 21 | 0 | 0 | 0 |  |
| clover_swap_arith__swapArithmetic | 84 | 62 | 22 | 0 | 0 | 0 |  |
| clover_swap_in_array__swap | 17 | 13 | 4 | 0 | 0 | 0 |  |
| clover_swap_sim__swapSimultaneous | 81 | 56 | 25 | 0 | 0 | 0 |  |
| clover_test_array__testArrayElements | 4 | 4 | 0 | 0 | 0 | 0 |  |
| clover_triple3__triple | 18 | 18 | 0 | 0 | 0 | 0 |  |
| clover_triple4__triple | 10 | 10 | 0 | 0 | 0 | 0 |  |
| clover_triple__triple | 6 | 6 | 0 | 0 | 0 | 0 |  |
| clover_update_array__updateElements | no-input | | | | | | |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1_assignment_2__arraySum | 26 | 20 | 4 | 2 | 0 | 0 |  |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1_assignment_2__intDiv | 53 | 43 | 10 | 0 | 0 | 0 |  |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1_assignment_2__isPrime | 28 | 23 | 1 | 4 | 0 | 0 |  |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1_assignment_2__plusOne | 4 | 3 | 0 | 0 | 1 | 1 | off-by-one: `y := x + 1;` -> `y := x + 2;` at x=0 -> real 1, twin 2 |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1_assignment_2__reverse | 26 | 22 | 2 | 2 | 0 | 0 |  |
| cs245_verification_tmp_tmp0h_nxhqp_a8_q1__a8Q1 | 29 | 21 | 0 | 8 | 0 | 0 |  |
| cs245_verification_tmp_tmp0h_nxhqp_a8_q2__a8Q1 | 40 | 33 | 3 | 0 | 4 | 1 | wrong-constant#1: `m := z;` -> `m := z + -1;` at x=1, y=1, z=0 -> real 0, twin -1 |
| cs245_verification_tmp_tmp0h_nxhqp_assignments_simple__simple | 4 | 4 | 0 | 0 | 0 | 0 |  |
| cs245_verification_tmp_tmp0h_nxhqp_power__compute_power | 28 | 23 | 0 | 5 | 0 | 0 |  |
| cs245_verification_tmp_tmp0h_nxhqp_sortingissues_firstattempt__sort | 19 | 16 | 0 | 2 | 1 | 0 | wrong-var#3: `a_out := a_out[k := k];` -> `a_out := a_out[k := n];` at a=[0], n=1 -> real [0], twin [1] |
| cs357_tmp_tmpn4fsvwzs_lab7_question2__two | 20 | 20 | 0 | 0 | 0 | 0 |  |
| cs357_tmp_tmpn4fsvwzs_lab7_question5__a1 | 48 | 23 | 2 | 23 | 0 | 0 |  |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_fibonacci__computeFib | 54 | 47 | 4 | 3 | 0 | 0 |  |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_modifying_arrays__incrementArray | 16 | 14 | 0 | 2 | 0 | 0 |  |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_modifying_arrays__updateElements | no-input | | | | | | |
| dafny_duck_tmp_tmplawbgxjo_p3__max | 24 | 19 | 3 | 2 | 0 | 0 |  |
| dafny_examples_tmp_tmp8qotd4ez_leetcode_0070_climbing_stairs__climbStairs | 65 | 59 | 2 | 4 | 0 | 0 |  |
| dafny_exercise_tmp_tmpouftptir_appendarray__appendArray | 46 | 40 | 2 | 4 | 0 | 0 |  |
| dafny_exercise_tmp_tmpouftptir_maxarray__maxArray | 24 | 19 | 3 | 2 | 0 | 0 |  |
| dafny_exercise_tmp_tmpouftptir_prac3_ex2__getEven | 29 | 27 | 0 | 2 | 0 | 0 |  |
| dafny_exercises_tmp_tmpjm75muf__session2exercises_exercisefibonacci__fibonacci1 | 49 | 44 | 2 | 3 | 0 | 0 |  |
| dafny_exercises_tmp_tmpjm75muf__session2exercises_exercisefibonacci__fibonacci2 | 53 | 50 | 0 | 3 | 0 | 0 |  |
| dafny_exercises_tmp_tmpjm75muf__session2exercises_exercisefibonacci__fibonacci3 | 45 | 42 | 0 | 3 | 0 | 0 |  |
| dafny_exercises_tmp_tmpjm75muf__session2exercises_exercisesquare_root__mroot1 | 22 | 16 | 2 | 4 | 0 | 0 |  |
| dafny_exercises_tmp_tmpjm75muf__session2exercises_exercisesquare_root__mroot2 | 14 | 6 | 1 | 7 | 0 | 0 |  |
| dafny_exercises_tmp_tmpjm75muf__session2exercises_exercisesquare_root__mroot3 | 53 | 15 | 11 | 27 | 0 | 0 |  |
| dafny_exercises_tmp_tmpjm75muf__session3exercises_exercisemaximum__mfirstMaximum | 26 | 22 | 2 | 2 | 0 | 0 |  |
| dafny_exercises_tmp_tmpjm75muf__session3exercises_exercisemaximum__mmaximum1 | 26 | 21 | 2 | 2 | 1 | 1 | compare-flip#1: `if v[j] > v[i] {` -> `if v[j] >= v[i] {` at v=[0, 0] -> real 0, twin 1 |
| dafny_exercises_tmp_tmpjm75muf__session4exercises_exercisefirstzero__mfirstCero | 18 | 16 | 0 | 2 | 0 | 0 |  |
| dafny_experiences_tmp_tmp150sm9qy_dafny_started_tutorial_dafny_tutorial_array__findMax | 26 | 21 | 2 | 2 | 1 | 1 | compare-flip#1: `if a[index] > a[i] {` -> `if a[index] >= a[i] {` at a=[0, 0] -> real 0, twin 1 |
| dafny_language_server_tmp_tmpkir0kenl_test_dafny1_cubes__cubes | 61 | 59 | 0 | 2 | 0 | 0 |  |
| dafny_language_server_tmp_tmpkir0kenl_test_dafny2_turingfactorial__computeFactorial | 51 | 40 | 2 | 9 | 0 | 0 |  |
| dafny_language_server_tmp_tmpkir0kenl_test_tutorial_maximum__maximum | 24 | 19 | 3 | 2 | 0 | 0 |  |
| dafny_language_server_tmp_tmpkir0kenl_test_vscomp2010_problem1_summax__m | 71 | 36 | 10 | 4 | 21 | 1 | off-by-one#5: `sum := 0;` -> `sum := -1;` at n=0, a=[] -> real [0, 0], twin [-1, 0] |
| dafny_language_server_tmp_tmpkir0kenl_test_vsi_benchmarks_b1__add | 48 | 23 | 2 | 23 | 0 | 0 |  |
| dafny_learn_tmp_tmpn94ir40q_r01_assertions__abs | 10 | 8 | 2 | 0 | 0 | 0 |  |
| dafny_learn_tmp_tmpn94ir40q_r01_assertions__max | 11 | 8 | 1 | 0 | 2 | 1 | wrong-constant: `c := a;` -> `c := a + 1;` at a=0, b=0 -> real 0, twin 1 |
| dafny_learn_tmp_tmpn94ir40q_r01_functions__abs | 10 | 8 | 2 | 0 | 0 | 0 |  |
| dafny_learn_tmp_tmpn94ir40q_r01_functions__testDouble | 6 | 6 | 0 | 0 | 0 | 0 |  |
| dafny_learning_experience_tmp_tmpuxvcet_u_week1_7_a2_q1_trimmed_copy_______mult | 21 | 14 | 0 | 7 | 0 | 0 |  |
| dafny_learning_experience_tmp_tmpuxvcet_u_week1_7_maxsum__maxSum | 58 | 44 | 14 | 0 | 0 | 0 |  |
| dafny_learning_experience_tmp_tmpuxvcet_u_week1_7_week5_computepower__calcPower | 6 | 6 | 0 | 0 | 0 | 0 |  |
| dafny_learning_experience_tmp_tmpuxvcet_u_week8_12_a3_search_findpositionofindex__findPositionOfElement | 74 | 41 | 20 | 2 | 11 | (real vacuous) | off-by-one#12: `position := count + 1;` -> `position := count + 2;` at a=[0], element=0, n1=1, s1=[0] -> real [1, 0], twin [2, 0] |
| dafny_learning_experience_tmp_tmpuxvcet_u_week8_12_week9_lemma__assignmentsToMarkOne | 5 | 4 | 0 | 0 | 1 | (real timeout) | wrong-constant#1: `r := students / tutors;` -> `r := students / tutors + -1;` at students=1, tutors=2 -> real 0, twin -1 |
| dafny_misc_tmp_tmpg4vzlnm1_rosetta_code_factorial__iterativeFactorial | 24 | 16 | 2 | 6 | 0 | 0 |  |
| dafny_programs_tmp_tmp99966ew4_mymax__max | 12 | 9 | 1 | 0 | 2 | 1 | wrong-constant: `c := b;` -> `c := b + 1;` at a=0, b=1 -> real 1, twin 2 |
| dafny_programs_tmp_tmpcwodh6qh_src_expt__expt | 32 | 25 | 0 | 7 | 0 | 0 |  |
| dafny_programs_tmp_tmpcwodh6qh_src_factorial__factorial | 28 | 21 | 2 | 5 | 0 | 0 |  |
| dafny_programs_tmp_tmpcwodh6qh_src_max__max | 12 | 11 | 1 | 0 | 0 | 0 |  |
| dafny_projects_tmp_tmpjutqwjv4_tutorial_tutorial__computeFib | 65 | 60 | 2 | 3 | 0 | 0 |  |
| dafny_synthesis_task_id_101__kthElement | 6 | 6 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_106__appendArrayToSeq | 23 | 21 | 0 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_126__sumOfCommonDivisors | 54 | 29 | 2 | 10 | 13 | 1 | collapse-if: `if a % i == 0 and b % i == 0 {` -> `sum := sum + i;` at a=2, b=2147483647 -> real 1, twin 3 |
| dafny_synthesis_task_id_127__multiply | 6 | 6 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_135__nthHexagonalNumber | 12 | 12 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_145__maxDifference | 75 | 64 | 4 | 4 | 3 | 1 | wrong-constant#4: `diff := maxVal - minVal;` -> `diff := maxVal - minVal + 1;` at a=[0, 0] -> real 0, twin 1 |
| dafny_synthesis_task_id_14__triangularPrismVolume | 15 | 15 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_161__removeElements | 52 | 39 | 0 | 2 | 11 | 1 | off-by-one#3: `while i_v2 < h` -> `while i_v2 < h + -1` at a=[0], b=[] -> real [0], twin [] |
| dafny_synthesis_task_id_171__pentagonPerimeter | 6 | 6 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_17__squarePerimeter | 6 | 6 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_227__minOfThree | 44 | 36 | 8 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_234__cubeVolume | 6 | 6 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_238__countNonEmptySubstrings | 11 | 11 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_240__replaceLastElement | 13 | 13 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_242__countCharacters | 2 | 2 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_249__intersection | 52 | 39 | 0 | 2 | 11 | 1 | off-by-one#3: `while i_v2 < h` -> `while i_v2 < h + -1` at a=[0], b=[0] -> real [0], twin [] |
| dafny_synthesis_task_id_257__swap | 2 | 2 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_261__elementWiseDivision | 20 | 17 | 1 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_262__splitArray | 21 | 21 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_264__dogYears | 6 | 6 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_266__lateralSurfaceArea | 8 | 8 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_267__sumOfSquaresOfFirstNOddNumbers | 49 | 44 | 1 | 4 | 0 | 0 |  |
| dafny_synthesis_task_id_268__starNumber | 14 | 14 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_269__asciiValue | 2 | 2 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_273__subtractSequences | 21 | 18 | 1 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_279__nthDecagonalNumber | 14 | 14 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_282__elementWiseSubtraction | 28 | 22 | 4 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_284__allElementsEqual | 28 | 25 | 0 | 3 | 0 | 0 |  |
| dafny_synthesis_task_id_292__quotient | 5 | 5 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_2__sharedElements | 52 | 39 | 0 | 2 | 11 | 1 | off-by-one#3: `while i_v2 < h` -> `while i_v2 < h + -1` at a=[0], b=[0] -> real [0], twin [] |
| dafny_synthesis_task_id_304__elementAtIndexAfterRotation | 9 | 3 | 6 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_307__deepCopySeq | 24 | 21 | 1 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_309__max | 12 | 11 | 1 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_396__startAndEndWithSameChar | 10 | 10 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_397__medianOfThree | 64 | 6 | 10 | 0 | 48 | 1 | collapse-if: `if a <= b and b <= c or c <= b and b <= a {` -> `median := b;` at a=0, b=1, c=0 -> real 0, twin 1 |
| dafny_synthesis_task_id_3__isNonPrime | 25 | 20 | 0 | 5 | 0 | 0 |  |
| dafny_synthesis_task_id_404__min | 12 | 11 | 1 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_406__isOdd | 5 | 5 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_412__removeOddNumbers | 25 | 23 | 0 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_414__anyValueExists | 30 | 27 | 0 | 3 | 0 | 0 |  |
| dafny_synthesis_task_id_426__filterOddNumbers | 25 | 23 | 0 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_432__medianLength | 9 | 9 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_433__isGreater | 22 | 19 | 0 | 3 | 0 | (real vacuous) |  |
| dafny_synthesis_task_id_435__lastDigit | 5 | 5 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_436__findNegativeNumbers | 25 | 23 | 0 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_441__cubeSurfaceArea | 8 | 8 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_445__multiplyElements | 21 | 18 | 1 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_447__cubeElements | 43 | 38 | 3 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_452__calculateLoss | 16 | 15 | 1 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_458__rectangleArea | 6 | 6 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_460__getFirstElements | 24 | 22 | 0 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_470__pairwiseAddition | 40 | 36 | 2 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_472__containsConsecutiveNumbers | 37 | 35 | 0 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_554__findOddNumbers | 25 | 23 | 0 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_567__isSorted | 35 | 19 | 0 | 2 | 14 | (real vacuous) | boundary-swap: `while i_v2 < h` -> `while h < i_v2` at a=[1, 0] -> real False, twin True |
| dafny_synthesis_task_id_576__isSublist | 42 | 18 | 22 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_577__factorialOfLastDigit | 6 | 6 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_578__interleave | 34 | 28 | 4 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_581__squarePyramidSurfaceArea | 14 | 14 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_586__splitAndAppend | 16 | 16 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_587__arrayToSeq | 20 | 18 | 0 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_58__hasOppositeSign | 20 | 20 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_591__swapFirstAndLast | 20 | 20 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_594__firstEvenOddDifference | 111 | 88 | 19 | 4 | 0 | 0 |  |
| dafny_synthesis_task_id_598__isArmstrong | 67 | 4 | 63 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_59__nthOctagonalNumber | 12 | 12 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_600__isEven | 5 | 5 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_603__lucidNumbers | 24 | 9 | 2 | 6 | 7 | 1 | compare-flip: `while i_v3 <= n` -> `while i_v3 < n` at n=0 -> real [0], twin [] |
| dafny_synthesis_task_id_605__isPrime | 25 | 20 | 0 | 5 | 0 | 0 |  |
| dafny_synthesis_task_id_610__removeElement | 49 | 42 | 2 | 5 | 0 | 0 |  |
| dafny_synthesis_task_id_616__elementWiseModulo | 27 | 21 | 4 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_618__elementWiseDivide | 27 | 24 | 1 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_622__findMedian | 36 | 32 | 4 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_625__swapFirstAndLast | 20 | 20 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_626__areaOfLargestTriangleInSemicircle | 4 | 4 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_629__findEvenNumbers | 25 | 23 | 0 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_62__findSmallest | 31 | 26 | 3 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_637__isBreakEven | 2 | 2 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_641__nthNonagonalNumber | 15 | 15 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_69__containsSequence | 22 | 20 | 0 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_70__allSequencesEqualLength | 38 | 33 | 2 | 3 | 0 | 0 |  |
| dafny_synthesis_task_id_728__addLists | 26 | 23 | 1 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_743__rotateRight | 37 | 31 | 1 | 5 | 0 | 0 |  |
| dafny_synthesis_task_id_760__hasOnlyOneDistinctElement | 36 | 31 | 2 | 3 | 0 | 0 |  |
| dafny_synthesis_task_id_762__isMonthWith30Days | 8 | 8 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_770__sumOfFourthPowerOfOddNumbers | 59 | 54 | 1 | 4 | 0 | 0 |  |
| dafny_synthesis_task_id_775__isOddAtIndexOdd | 25 | 21 | 2 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_77__isDivisibleBy11 | 5 | 5 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_792__countLists | 2 | 2 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_79__isLengthOdd | 5 | 5 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_801__countEqualNumbers | 40 | 39 | 1 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_804__isProductEven | 22 | 20 | 0 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_808__containsK | 28 | 25 | 0 | 3 | 0 | 0 |  |
| dafny_synthesis_task_id_809__isSmaller | 30 | 27 | 1 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_80__tetrahedralNumber | 17 | 17 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_86__centeredHexagonalNumber | 14 | 14 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_89__closestSmaller | 6 | 6 | 0 | 0 | 0 | 0 |  |
| dafny_synthesis_task_id_8__squareElements | 32 | 28 | 2 | 2 | 0 | 0 |  |
| dafny_synthesis_task_id_95__smallestListLength | 35 | 30 | 3 | 2 | 0 | 0 |  |
| dafny_tmp_tmp0wu8wmfr_heimaverkefni_1_linearsearch__searchRecursive | 40 | 36 | 2 | 2 | 0 | 0 |  |
| dafny_tmp_tmp0wu8wmfr_heimaverkefni_3_insertionsortmultiset__search | 76 | 60 | 4 | 7 | 5 | 1 | off-by-one#2: `var m: int := p_v + (q_v - p_v) / 2;` -> `var m: int := p_v + (q_v - p_v) / 3;` at s=[0, 0], x=0 -> real 1, twin 0 |
| dafny_tmp_tmp0wu8wmfr_tests_f1a__f | 4 | 2 | 0 | 0 | 2 | 1 | off-by-one#1: `r := 0;` -> `r := -1;` at  -> real 0, twin -1 |
| dafny_tmp_tmp0wu8wmfr_tests_f1a__mid | 9 | 9 | 0 | 0 | 0 | 0 |  |
| dafny_tmp_tmp0wu8wmfr_tests_search1000__search1000 | no-input | | | | | | |
| dafny_tmp_tmp0wu8wmfr_tests_sumintsloop__sumIntsLoop | 18 | 9 | 2 | 7 | 0 | 0 |  |
| dafny_tmp_tmpj88zq5zt_2_kontrakte_max__max | 20 | 15 | 5 | 0 | 0 | 0 |  |
| dafny_tmp_tmpj88zq5zt_2_kontrakte_reverse3__swap3 | no-input | | | | | | |
| dafny_tmp_tmpmvs2dmry_examples1__abs | 10 | 8 | 2 | 0 | 0 | 0 |  |
| dafny_tmp_tmpmvs2dmry_examples1__max | 12 | 11 | 1 | 0 | 0 | 0 |  |
| dafny_tmp_tmpmvs2dmry_examples1__multiReturn | 33 | 18 | 8 | 0 | 7 | 1 | wrong-var#4: `more := x + y;` -> `more := x + more;` at x=0, y=1 -> real [1, -1], twin [0, -1] |
| dafny_tmp_tmpmvs2dmry_examples2__add_by_inc | 25 | 20 | 0 | 5 | 0 | 0 |  |
| dafny_tmp_tmpmvs2dmry_examples2__gcdCalc | 48 | 13 | 2 | 33 | 0 | 0 |  |
| dafny_tmp_tmpmvs2dmry_examples2__product | 42 | 17 | 0 | 25 | 0 | 0 |  |
| dafny_tmp_tmpmvs2dmry_pancakesort_flip__flip | 61 | 43 | 18 | 0 | 0 | 0 |  |
| dafny_tmp_tmpmvs2dmry_slowmax__slow_max | 69 | 42 | 20 | 7 | 0 | 0 |  |
| dafny_tmp_tmpv_d3qi10_2_min__minArray | 24 | 19 | 3 | 2 | 0 | 0 |  |
| dafny_tmp_tmpv_d3qi10_2_min__minMethod | 12 | 11 | 1 | 0 | 0 | 0 |  |
| dafny_training_tmp_tmp_n2kixni_session1_training1__abs | 10 | 0 | 2 | 0 | 8 | 1 | collapse-if: `if x < 0 {` -> `y := -x;` at x=1 -> real 1, twin -1 |
| dafny_training_tmp_tmp_n2kixni_session1_training1__find | 24 | 7 | 0 | 1 | 16 | 1 | negate-cond: `return 0;` -> `} else {` at a=[0], key=0 -> real 0, twin -10 |
| dafny_training_tmp_tmp_n2kixni_session1_training1__max | 24 | 0 | 4 | 0 | 20 | 1 | collapse-if: `if x > y {` -> `r := 0;` at x=0, y=0 -> real 1, twin 0 |
| dafny_verify_tmp_tmphq7j0row_ai_agent_validation_examples__computePower | 25 | 14 | 0 | 11 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_ai_agent_validation_examples__cube | 80 | 64 | 0 | 16 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_ai_agent_verify_examples_computepower__computePower | 25 | 14 | 0 | 11 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_ai_agent_verify_examples_cube__cube | 80 | 64 | 0 | 16 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_dataset_bql_exampls_min__min | 33 | 24 | 7 | 2 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_dataset_bql_exampls_smallnum__add_small_numbers | 30 | 19 | 6 | 3 | 2 | 1 | off-by-one#5: `r := 0;` -> `r := -1;` at a=[0], n=1, max=0 -> real 0, twin -1 |
| dafny_verify_tmp_tmphq7j0row_dataset_bql_exampls_square__square | 44 | 31 | 9 | 4 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_dataset_c_convert_examples_11__main_v | 41 | 28 | 9 | 3 | 1 | 1 | wrong-var#12: `r := (j, i);` -> `r := (j, j);` at x=1 -> real [2, 1], twin [2, 2] |
| dafny_verify_tmp_tmphq7j0row_dataset_c_convert_examples_15__main_v | 27 | 2 | 0 | 4 | 21 | 0 | compare-flip: `while j < n` -> `while j <= n` at n=1, k=2 -> real 1, twin 0 |
| dafny_verify_tmp_tmphq7j0row_dataset_error_data_real_error_iseven_success_1__is_even | 15 | 12 | 0 | 3 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_fine_tune_examples_50_examples_41__main_v | 48 | 17 | 11 | 5 | 15 | 0 | compare-flip: `while i < n` -> `while i <= n` at n=0, k=0 -> real [0, 0], twin [1, 1] |
| dafny_verify_tmp_tmphq7j0row_fine_tune_examples_error_data_completion_11__main_v | 41 | 28 | 9 | 3 | 1 | 1 | wrong-var#12: `r := (j, i);` -> `r := (j, j);` at x=1 -> real [2, 1], twin [2, 2] |
| dafny_verify_tmp_tmphq7j0row_generated_code_15__main_v | 27 | 2 | 0 | 4 | 21 | 0 | compare-flip: `while j < n` -> `while j <= n` at n=1, k=2 -> real 1, twin 0 |
| dafny_verify_tmp_tmphq7j0row_generated_code_computepower__computePower | 21 | 14 | 0 | 7 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_generated_code_minimum__minimum | 20 | 15 | 3 | 2 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_generated_code_mult__mult | 27 | 19 | 0 | 8 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_test_cases_function__tripleConditions | 6 | 6 | 0 | 0 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_test_cases_function__triple_p | 6 | 6 | 0 | 0 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_test_cases_ghost__doubleQuadruple | 29 | 21 | 8 | 0 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_test_cases_ghost__m | 4 | 4 | 0 | 0 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_test_cases_ghost__myMethod | 40 | 4 | 8 | 0 | 28 | 1 | collapse-if: `if x < 20 {` -> `b := 32 - x;` at x=20 -> real 39, twin 35 |
| dafny_verify_tmp_tmphq7j0row_test_cases_ghost__triple | 8 | 8 | 0 | 0 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_test_cases_index__index | 5 | 4 | 0 | 0 | 1 | 1 | off-by-one: `i := n / 2;` -> `i := n / 3;` at n=2 -> real 1, twin 0 |
| dafny_verify_tmp_tmphq7j0row_test_cases_index__maxSum | 43 | 34 | 9 | 0 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_test_cases_index__min | 12 | 11 | 1 | 0 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_test_cases_index__reconstructFromMaxSum | 30 | 19 | 10 | 0 | 1 | 1 | wrong-var#9: `r := (x, y);` -> `r := (y, x);` at s=0, m=1 -> real [1, -1], twin [-1, 1] |
| dafny_verify_tmp_tmphq7j0row_test_cases_loopinvariant__downWhileGreater | 14 | 9 | 1 | 4 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_test_cases_loopinvariant__downWhileNotEqual | 10 | 1 | 1 | 8 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_test_cases_loopinvariant__upWhileLess | 12 | 7 | 2 | 3 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_test_cases_loopinvariant__upWhileNotEqual | 8 | 0 | 2 | 6 | 0 | 0 |  |
| dafny_verify_tmp_tmphq7j0row_test_cases_triple__tripleConditions | 12 | 12 | 0 | 0 | 0 | 0 |  |
| dafny_workout_tmp_tmp0abkw6f8_starter_ex01__max | 12 | 11 | 1 | 0 | 0 | 0 |  |
| dafny_workout_tmp_tmp0abkw6f8_starter_ex02__abs | 2 | 2 | 0 | 0 | 0 | 0 |  |
| dafny_workout_tmp_tmp0abkw6f8_starter_ex03__abs | 4 | 4 | 0 | 0 | 0 | 0 |  |
| dafny_workout_tmp_tmp0abkw6f8_starter_ex09__computeFib | 66 | 56 | 7 | 3 | 0 | 0 |  |
| dafny_workout_tmp_tmp0abkw6f8_starter_ex12__findMax | 26 | 21 | 2 | 2 | 1 | 1 | compare-flip#1: `if a[i] > a[max_idx] {` -> `if a[i] >= a[max_idx] {` at a=[0, 0] -> real 0, twin 1 |
| dafnyexercises_tmp_tmpd6qyevja_part1_q1__addArrays | 26 | 20 | 4 | 2 | 0 | 0 |  |
| dafnyprograms_tmp_tmp74_f9k_c_invertarray__invertArray | 46 | 44 | 0 | 2 | 0 | 0 |  |
| dafnyprojects_tmp_tmp2acw_s4s_longestprefix__longestPrefix | 27 | 25 | 0 | 2 | 0 | 0 |  |
| final_project_dafny_tmp_tmpmcywuqox_attempts_exercise3_increment_array__incrementArray | 20 | 18 | 0 | 2 | 0 | 0 |  |
| final_project_dafny_tmp_tmpmcywuqox_attempts_exercise4_find_max__findMax | 55 | 40 | 10 | 4 | 1 | 1 | compare-flip#1: `if a[j] > maxVal {` -> `if a[j] >= maxVal {` at a=[0, 0] -> real [0, 0], twin [1, 0] |
| final_project_dafny_tmp_tmpmcywuqox_attempts_exercise6_binary_search__binarySearch | 96 | 81 | 2 | 8 | 5 | 1 | off-by-one#8: `return -(1);` -> `return -(2);` at a=[0], val=1 -> real -1, twin -2 |
| final_project_dafny_tmp_tmpmcywuqox_attempts_insertion_sort_normal__lookForMin | 27 | 21 | 2 | 3 | 1 | 1 | compare-flip#1: `if a[j] < a[m] {` -> `if a[j] <= a[m] {` at a=[0, 0], i=0 -> real 0, twin 1 |
| final_project_dafny_tmp_tmpmcywuqox_final_project_3__nonZeroReturn | 10 | 8 | 0 | 0 | 2 | 1 | off-by-one#2: `y := x + 1;` -> `y := x + 2;` at x=0 -> real 1, twin 2 |
| flexweek_tmp_tmpc_tfdj_3_ex3__max | 32 | 27 | 3 | 2 | 0 | 0 |  |
| formal_methods_in_software_engineering_tmp_tmpe7fjnek6_labs4_gr2__divMod1 | 51 | 35 | 8 | 8 | 0 | 0 |  |
| formal_methods_in_software_engineering_tmp_tmpe7fjnek6_labs4_gr2__hoareTripleReqEns | 12 | 12 | 0 | 0 | 0 | 0 |  |
| formal_methods_in_software_engineering_tmp_tmpe7fjnek6_labs4_gr2__sqrSum1 | 52 | 37 | 8 | 7 | 0 | 0 |  |
| formal_methods_of_software_development_tmp_tmppryvbyty_bloque_1_lab3__computeFact | 25 | 17 | 2 | 6 | 0 | 0 |  |
| formal_methods_of_software_development_tmp_tmppryvbyty_bloque_1_lab3__computeFact2 | 24 | 19 | 2 | 3 | 0 | 0 |  |
| formal_methods_of_software_development_tmp_tmppryvbyty_bloque_1_lab3__sqare | 32 | 29 | 0 | 3 | 0 | 0 |  |
| formal_methods_of_software_development_tmp_tmppryvbyty_bloque_1_lab3__sqare2 | 32 | 29 | 0 | 3 | 0 | 0 |  |
| formal_verication_dafny_tmp_tmpwgl2qz28_challenges_ex2__allow42 | 37 | 30 | 7 | 0 | 0 | 0 |  |
| formal_verication_dafny_tmp_tmpwgl2qz28_challenges_ex2__forbid42 | 9 | 9 | 0 | 0 | 0 | 0 |  |
| formalmethods_tmp_tmpvda2r3_o_dafny_invariants_ex1__mult | 34 | 23 | 1 | 10 | 0 | 0 |  |
| formalmethods_tmp_tmpvda2r3_o_dafny_invariants_ex2__pot | 36 | 27 | 1 | 8 | 0 | 0 |  |
| laboratory_tmp_tmps8ws6mu2_dafny_tutorial_exercise12__findMax | 32 | 27 | 2 | 2 | 1 | 1 | compare-flip#1: `if max < a[i] {` -> `if max <= a[i] {` at a=[0, 0] -> real 0, twin 1 |
| laboratory_tmp_tmps8ws6mu2_dafny_tutorial_exercise9__computeFib | 49 | 44 | 2 | 3 | 0 | 0 |  |
| m2_tmp_tmp2laaavvl_software_verification_exercices_exo4_countandreturn__countToAndReturnN | 18 | 12 | 3 | 3 | 0 | 0 |  |
| m2_tmp_tmp2laaavvl_software_verification_exercices_exo7_computesum__computeSum | 26 | 21 | 2 | 3 | 0 | 0 |  |
| m2_tmp_tmp2laaavvl_software_verification_exercices_exo9_carre__carre | 26 | 19 | 0 | 7 | 0 | 0 |  |
| metodos_formais_tmp_tmpbez22nnn_aula_2_ex1__mult | 34 | 23 | 1 | 10 | 0 | 0 |  |
| metodos_formais_tmp_tmpbez22nnn_aula_2_ex2__pot | 36 | 27 | 1 | 8 | 0 | 0 |  |
| metodos_formais_tmp_tmpbez22nnn_aula_4_ex3__computeFib | 49 | 44 | 2 | 3 | 0 | 0 |  |
| metodos_formais_tmp_tmpql2hwcsh_invariantes_fatorial2__fatorial | 24 | 16 | 2 | 6 | 0 | 0 |  |
| metodos_formais_tmp_tmpql2hwcsh_invariantes_fibonacci__computeFib | 49 | 44 | 2 | 3 | 0 | 0 |  |
| metodos_formais_tmp_tmpql2hwcsh_invariantes_multiplicador__mult | 34 | 23 | 1 | 10 | 0 | 0 |  |
| metodos_formais_tmp_tmpql2hwcsh_invariantes_potencia__pot | 36 | 27 | 1 | 8 | 0 | 0 |  |
| mfes_2021_tmp_tmpuljn8zd9_fcul_exercises_10_find__find | 16 | 11 | 0 | 2 | 3 | 0 | off-by-one: `index := 0;` -> `index := 1;` at a=[0], key=0 -> real 0, twin 1 |
| mfes_2021_tmp_tmpuljn8zd9_fcul_exercises_8_sum__sum | 22 | 17 | 2 | 3 | 0 | 0 |  |
| mfs_tmp_tmpmmnu354t_testes_anteriores_t2_ex5_2020_2__leq | 44 | 42 | 0 | 2 | 0 | 0 |  |
| mieic_mfes_tmp_tmpq3ho7nve_exams_appeal_20_p4__calcF | 99 | 92 | 3 | 4 | 0 | 0 |  |
| mieic_mfes_tmp_tmpq3ho7nve_exams_mt2_19_p4__calcR | 32 | 27 | 2 | 3 | 0 | 0 |  |
| nitwit_tmp_tmplm098gxz_nit__max_nit | 6 | 6 | 0 | 0 | 0 | 0 |  |
| nitwit_tmp_tmplm098gxz_nit__nit_add | 51 | 21 | 8 | 0 | 22 | 1 | wrong-var: `z := (x + y) % b;` -> `z := (b + y) % b;` at b=2, x=1, y=0 -> real [1, 0], twin [0, 0] |
| nitwit_tmp_tmplm098gxz_nit__nit_increment | 41 | 13 | 8 | 0 | 20 | 1 | off-by-one#4: `sum := (n + 1) % b;` -> `sum := (n + 2) % b;` at b=2, n=0 -> real [1, 0], twin [0, 0] |
| prog_fun_solutions_tmp_tmp7_gmnz5f_extra_mod2__mod2 | real-violates-spec | | | | | | |
| prog_fun_solutions_tmp_tmp7_gmnz5f_extra_mod__mod | 64 | 54 | 0 | 10 | 0 | 0 |  |
| prog_fun_solutions_tmp_tmp7_gmnz5f_extra_pow__pow | 40 | 34 | 0 | 6 | 0 | 0 |  |
| prog_fun_solutions_tmp_tmp7_gmnz5f_extra_sum__sum | 48 | 37 | 3 | 8 | 0 | 0 |  |
| prog_fun_solutions_tmp_tmp7_gmnz5f_mockexam2_p2__problem2 | 138 | 113 | 25 | 0 | 0 | 0 |  |
| prog_fun_solutions_tmp_tmp7_gmnz5f_mockexam2_p3__problem3 | 33 | 26 | 7 | 0 | 0 | 0 |  |
| prog_fun_solutions_tmp_tmp7_gmnz5f_mockexam2_p5__problem5 | 57 | 47 | 3 | 7 | 0 | 0 |  |
| program_verification_dataset_tmp_tmpgbdrlnu__dafny_algorithms_and_leetcode_examples_simplemultiplication__foo | 22 | 13 | 0 | 9 | 0 | 0 |  |
| program_verification_dataset_tmp_tmpgbdrlnu__dafny_basic_examples_add_by_one__add_by_one | 26 | 21 | 0 | 5 | 0 | 0 |  |
| program_verification_dataset_tmp_tmpgbdrlnu__dafny_basic_examples_add_by_one_details__plus_one | 4 | 4 | 0 | 0 | 0 | 0 |  |
| program_verification_dataset_tmp_tmpgbdrlnu__dafny_basic_examples_find_max__findMax | 26 | 21 | 2 | 2 | 1 | 1 | compare-flip#1: `if a[i] > a[max] {` -> `if a[i] >= a[max] {` at a=[0, 0] -> real 0, twin 1 |
| program_verification_dataset_tmp_tmpgbdrlnu__dafny_basic_examples_sumto_sol__sumUpTo | 23 | 20 | 0 | 3 | 0 | 0 |  |
| program_verification_dataset_tmp_tmpgbdrlnu__dafny_from_dafny_main_repo_dafny2_classics__additiveFactorial | 47 | 33 | 4 | 10 | 0 | 0 |  |
| program_verification_dataset_tmp_tmpgbdrlnu__dafny_variant_examples_katzmanna__ninetyOne | 64 | 34 | 8 | 22 | 0 | 0 |  |
| programmverifikation_und_synthese_tmp_tmppurk6ime_example_dafnyintro_01_simple_loops__gauss | 22 | 17 | 2 | 3 | 0 | 0 |  |
| programmverifikation_und_synthese_tmp_tmppurk6ime_example_dafnyintro_01_simple_loops__sumOdds | 30 | 27 | 0 | 3 | 0 | 0 |  |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_04_hoangkim_ex_04_hoangkim__intDivImpl | real-violates-spec | | | | | | |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_04_hoangkim_ex_04_hoangkim__sumOdds | 34 | 31 | 0 | 3 | 0 | 0 |  |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_05_hoangkim_ex_05_hoangkim__factIter | 24 | 16 | 2 | 6 | 0 | 0 |  |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_05_hoangkim_ex_05_hoangkim__fibIter | 49 | 44 | 2 | 3 | 0 | 0 |  |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_05_hoangkim_ex_05_hoangkim__gcdI | 32 | 5 | 5 | 22 | 0 | 0 |  |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_06_hoangkim_ex06_solution__gcdI | 52 | 13 | 6 | 33 | 0 | 0 |  |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_06_hoangkim_ex_06_hoangkim__gcdI | 32 | 5 | 5 | 22 | 0 | 0 |  |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_07_hoangkim_ex07_hoangkim__findMin | 27 | 21 | 2 | 3 | 1 | 1 | compare-flip#1: `if a[j] < a[minIdx] {` -> `if a[j] <= a[minIdx] {` at a=[0, 0], lo=0 -> real 0, twin 1 |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_07_hoangkim_ex07_hoangkim__swap | 23 | 15 | 8 | 0 | 0 | 0 |  |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_10_hoangkim_ex10_hoangkim__square0 | 40 | 32 | 5 | 3 | 0 | 0 |  |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_10_hoangkim_ex10_hoangkim__square1 | 33 | 29 | 1 | 3 | 0 | 0 |  |
| projectoscvs_tmp_tmp_02_gmcw_handout_1_cvs_handout1_55754_55780__euclidianDiv | 55 | 29 | 8 | 8 | 10 | 1 | compare-flip: `while r_v - b >= 0` -> `while r_v - b > 0` at a=1, b=1 -> real [1, 0], twin [0, 1] |
| projectoscvs_tmp_tmp_02_gmcw_handout_1_cvs_handout1_55754_55780__peasantMult | 83 | 54 | 3 | 26 | 0 | 0 |  |
| se2011_tmp_tmp71eb82zt_ass1_ex4__eval | 32 | 25 | 0 | 7 | 0 | 0 |  |
| se2011_tmp_tmp71eb82zt_ass1_ex6__ceiling7 | 7 | 7 | 0 | 0 | 0 | 0 |  |
| seng2011_tmp_tmpgk5jq85q_ass1_ex8__getEven | 29 | 26 | 0 | 2 | 1 | 1 | wrong-operator#1: `a_out := a_out[i_v := a_out[i_v] + 1];` -> `a_out := a_out[i_v := a_out[i_v] - 1];` at a=[1] -> real [2], twin [0] |
| seng2011_tmp_tmpgk5jq85q_flex_ex2__max | 24 | 19 | 3 | 2 | 0 | 0 |  |
| seng2011_tmp_tmpgk5jq85q_p2__absIt | 24 | 20 | 2 | 2 | 0 | 0 |  |
| software_analysis_tmp_tmpmt6bo9sf_ss__find_min_index | 34 | 16 | 16 | 2 | 0 | 0 |  |
| software_building_and_verification_projects_tmp_tmp5tm1srrn_cvs_projeto_aula2__m3 | 4 | 4 | 0 | 0 | 0 | 0 |  |
| software_building_and_verification_projects_tmp_tmp5tm1srrn_cvs_projeto_aula2__m4 | 4 | 0 | 0 | 0 | 4 | 1 | collapse-if: `if x == y {` -> `z := true;` at x=0, y=1 -> real False, twin True |
| software_building_and_verification_projects_tmp_tmp5tm1srrn_cvs_projeto_aula2__max | 12 | 1 | 1 | 0 | 10 | 1 | collapse-if: `if a > b {` -> `z := a;` at a=0, b=1 -> real 1, twin 0 |
| software_building_and_verification_projects_tmp_tmp5tm1srrn_cvs_projeto_aula2__mystery1 | 20 | 13 | 0 | 7 | 0 | 0 |  |
| software_verification_tmp_tmpv4ueky2d_best_time_to_buy_and_sell_stock_best_time_to_buy_and_sell_stock__best_time_to_buy_and_sell_stock | 56 | 36 | 10 | 4 | 6 | 1 | off-by-one#2: `max_profit := 0;` -> `max_profit := 1;` at prices=[0] -> real 0, twin 1 |
| stunning_palm_tree_tmp_tmpr84c2iwh_ch1__min | 12 | 11 | 1 | 0 | 0 | 0 |  |
| stunning_palm_tree_tmp_tmpr84c2iwh_ch1__minUnderSpec | 20 | 9 | 1 | 0 | 10 | 1 | off-by-one: `r := x - 1;` -> `r := x - 2;` at x=0, y=0 -> real -1, twin -2 |
| stunning_palm_tree_tmp_tmpr84c2iwh_ch1__reconstructFromMaxSum | 30 | 19 | 10 | 0 | 1 | 1 | wrong-var#9: `r := (x, y);` -> `r := (y, x);` at s=0, m=1 -> real [1, -1], twin [-1, 1] |
| stunning_palm_tree_tmp_tmpr84c2iwh_ch1__triple | 10 | 10 | 0 | 0 | 0 | 0 |  |
| stunning_palm_tree_tmp_tmpr84c2iwh_ch1__triple_p | 4 | 4 | 0 | 0 | 0 | 0 |  |
| t1_mf_tmp_tmpi_sqie4j_exemplos_introducao_ex4__fatorial | 24 | 19 | 2 | 3 | 0 | 0 |  |
| tfg_tmp_tmpbvsao41w_algoritmos_dafny_div_ent_it__div_ent_it | 51 | 35 | 8 | 8 | 0 | 0 |  |
| workshop_tmp_tmp0cu11bdq_lecture_answers_triangle_number__triangleNumber | 22 | 17 | 2 | 3 | 0 | 0 |  |
| workshop_tmp_tmp0cu11bdq_workshop_answers_question6__arrayUpToN | 24 | 13 | 4 | 2 | 5 | 0 | boundary-swap: `while i < n` -> `while n < i` at n=2 -> real [0, 1], twin [0, 0] |
