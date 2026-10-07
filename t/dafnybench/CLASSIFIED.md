# The 44 kernel-proved survivors, read by hand

`t/AUDIT-DAFNYBENCH.md` lists 44 tasks where Dafny proves the real body **and** a one-edit mutant that computes something different at a ground input. A survivor shows the specification admits a second program; whether that program is wrong is a judgement about intent, so each was read against the routine's name and body (2026-10-07):

- **gap** (23): the spec admits a result that is wrong for what the routine evidently computes;
- **no spec** (3): the contract is `ensures true`;
- **test** (3): a test case whose contract is deliberately a bound;
- **latitude** (15): the spec deliberately allows several answers (ties, either order, any negative sentinel, a competition's stated property).

| class | task | why | the proved survivor: change at input |
|---|---|---|---|
| gap | bbfny_tmp_tmpw4m0jvl0_enjoying__multipleReturns | bounds only: `less` need not be x - y | wrong-constant#5: `less := x - y;` -> `less := x - y + -1;` at x=0, y=1 -> real [1, -1], twin [1, -2] |
| gap | cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1_assignment_2__plusOne | `y > 0` admits x + 2 | off-by-one: `y := x + 1;` -> `y := x + 2;` at x=0 -> real 1, twin 2 |
| gap | cs245_verification_tmp_tmp0h_nxhqp_a8_q2__a8Q1 | lower bounds only: the minimum of three need not be one of them | wrong-constant#1: `m := z;` -> `m := z + -1;` at x=1, y=1, z=0 -> real 0, twin -1 |
| gap | dafny_learn_tmp_tmpn94ir40q_r01_assertions__max | `c >= a and c >= b` admits a + 1 | wrong-constant: `c := a;` -> `c := a + 1;` at a=0, b=0 -> real 0, twin 1 |
| gap | dafny_programs_tmp_tmp99966ew4_mymax__max | `c >= a and c >= b` admits b + 1: the result need not be a or b | wrong-constant: `c := b;` -> `c := b + 1;` at a=0, b=1 -> real 1, twin 2 |
| gap | dafny_synthesis_task_id_126__sumOfCommonDivisors | `sum >= every common divisor` admits summing every i (MutDafny's weak spec) | collapse-if: `if a % i == 0 and b % i == 0 {` -> `sum := sum + i;` at a=2, b=2147483647 -> real 1, twin 3 |
| gap | dafny_synthesis_task_id_145__maxDifference | an upper bound on differences, not the maximum | wrong-constant#4: `diff := maxVal - minVal;` -> `diff := maxVal - minVal + 1;` at a=[0, 0] -> real 0, twin 1 |
| gap | dafny_synthesis_task_id_161__removeElements | only `result within a minus b`, never the converse (MutDafny's weak spec) | off-by-one#3: `while i_v2 < h` -> `while i_v2 < h + -1` at a=[0], b=[] -> real [0], twin [] |
| gap | dafny_synthesis_task_id_249__intersection | only `result within a and b`, never the converse (MutDafny's weak spec) | off-by-one#3: `while i_v2 < h` -> `while i_v2 < h + -1` at a=[0], b=[0] -> real [0], twin [] |
| gap | dafny_synthesis_task_id_2__sharedElements | only `result within a and b`, never the converse (MutDafny's weak spec) | off-by-one#3: `while i_v2 < h` -> `while i_v2 < h + -1` at a=[0], b=[0] -> real [0], twin [] |
| gap | dafny_synthesis_task_id_397__medianOfThree | the result lies between SOME pair, not the other two: 1 is accepted for (0, 1, 0) | collapse-if: `if a <= b and b <= c or c <= b and b <= a {` -> `median := b;` at a=0, b=1, c=0 -> real 0, twin 1 |
| gap | dafny_synthesis_task_id_603__lucidNumbers | only `every element is a multiple of 3 up to n, increasing`; nothing requires them all | compare-flip: `while i_v3 <= n` -> `while i_v3 < n` at n=0 -> real [0], twin [] |
| gap | dafny_tmp_tmpmvs2dmry_examples1__multiReturn | bounds only: `more` need not be x + y | wrong-var#4: `more := x + y;` -> `more := x + more;` at x=0, y=1 -> real [1, -1], twin [0, -1] |
| gap | dafny_verify_tmp_tmphq7j0row_dataset_bql_exampls_smallnum__add_small_numbers | an upper bound only: -1 is accepted where the sum of [0] is 0 | off-by-one#5: `r := 0;` -> `r := -1;` at a=[0], n=1, max=0 -> real 0, twin -1 |
| gap | dafny_verify_tmp_tmphq7j0row_dataset_c_convert_examples_11__main_v | the second result is unconstrained | wrong-var#12: `r := (j, i);` -> `r := (j, j);` at x=1 -> real [2, 1], twin [2, 2] |
| gap | dafny_verify_tmp_tmphq7j0row_fine_tune_examples_error_data_completion_11__main_v | the second result is unconstrained | wrong-var#12: `r := (j, i);` -> `r := (j, j);` at x=1 -> real [2, 1], twin [2, 2] |
| gap | nitwit_tmp_tmplm098gxz_nit__nit_add | only ranges: the digit need not be (x + y) mod b | wrong-var: `z := (x + y) % b;` -> `z := (b + y) % b;` at b=2, x=1, y=0 -> real [1, 0], twin [0, 0] |
| gap | nitwit_tmp_tmplm098gxz_nit__nit_increment | only ranges: the digit need not be (n + 1) mod b | off-by-one#4: `sum := (n + 1) % b;` -> `sum := (n + 2) % b;` at b=2, n=0 -> real [1, 0], twin [0, 0] |
| gap | projectoscvs_tmp_tmp_02_gmcw_handout_1_cvs_handout1_55754_55780__euclidianDiv | no `0 <= r < b`: quotient 0 remainder 1 is accepted for 1 / 1 | compare-flip: `while r_v - b >= 0` -> `while r_v - b > 0` at a=1, b=1 -> real [1, 0], twin [0, 1] |
| gap | seng2011_tmp_tmpgk5jq85q_ass1_ex8__getEven | only evenness: the output need not be derived from the input | wrong-operator#1: `a_out := a_out[i_v := a_out[i_v] + 1];` -> `a_out := a_out[i_v := a_out[i_v] - 1];` at a=[1] -> real [2], twin [0] |
| gap | software_building_and_verification_projects_tmp_tmp5tm1srrn_cvs_projeto_aula2__m4 | operator precedence: `z ==> x == y && x == y ==> z` is `z ==> ((x == y && x == y) ==> z)`, a tautology | collapse-if: `if x == y {` -> `z := true;` at x=0, y=1 -> real False, twin True |
| gap | software_building_and_verification_projects_tmp_tmp5tm1srrn_cvs_projeto_aula2__max | `z >= a || z >= b` admits the smaller one | collapse-if: `if a > b {` -> `z := a;` at a=0, b=1 -> real 1, twin 0 |
| gap | software_verification_tmp_tmpv4ueky2d_best_time_to_buy_and_sell_stock_best_time_to_buy_and_sell_stock__best_time_to_buy_and_sell_stock | an upper bound on profits, not the maximum: 1 is accepted for [0] | off-by-one#2: `max_profit := 0;` -> `max_profit := 1;` at prices=[0] -> real 0, twin 1 |
| no spec | dafny_training_tmp_tmp_n2kixni_session1_training1__abs | `ensures true` (a training exercise's starting point) | collapse-if: `if x < 0 {` -> `y := -x;` at x=1 -> real 1, twin -1 |
| no spec | dafny_training_tmp_tmp_n2kixni_session1_training1__find | `ensures true` | negate-cond: `return 0;` -> `} else {` at a=[0], key=0 -> real 0, twin -10 |
| no spec | dafny_training_tmp_tmp_n2kixni_session1_training1__max | `ensures true` | collapse-if: `if x > y {` -> `r := 0;` at x=0, y=0 -> real 1, twin 0 |
| test | dafny_tmp_tmp0wu8wmfr_tests_f1a__f | a test: `r <= 0` | off-by-one#1: `r := 0;` -> `r := -1;` at  -> real 0, twin -1 |
| test | dafny_verify_tmp_tmphq7j0row_test_cases_ghost__myMethod | a test of ghost code; a bound only | collapse-if: `if x < 20 {` -> `b := 32 - x;` at x=20 -> real 39, twin 35 |
| test | dafny_verify_tmp_tmphq7j0row_test_cases_index__index | a test: any index below n | off-by-one: `i := n / 2;` -> `i := n / 3;` at n=2 -> real 1, twin 0 |
| latitude | dafny_exercises_tmp_tmpjm75muf__session3exercises_exercisemaximum__mmaximum1 | ties: any index of a maximum | compare-flip#1: `if v[j] > v[i] {` -> `if v[j] >= v[i] {` at v=[0, 0] -> real 0, twin 1 |
| latitude | dafny_experiences_tmp_tmp150sm9qy_dafny_started_tutorial_dafny_tutorial_array__findMax | ties: any index of a maximum | compare-flip#1: `if a[index] > a[i] {` -> `if a[index] >= a[i] {` at a=[0, 0] -> real 0, twin 1 |
| latitude | dafny_language_server_tmp_tmpkir0kenl_test_vscomp2010_problem1_summax__m | VSComp 2010 problem 1 states exactly `sum <= N * max` | off-by-one#5: `sum := 0;` -> `sum := -1;` at n=0, a=[] -> real [0, 0], twin [-1, 0] |
| latitude | dafny_tmp_tmp0wu8wmfr_heimaverkefni_3_insertionsortmultiset__search | with duplicates either split point is correct | off-by-one#2: `var m: int := p_v + (q_v - p_v) / 2;` -> `var m: int := p_v + (q_v - p_v) / 3;` at s=[0, 0], x=0 -> real 1, twin 0 |
| latitude | dafny_verify_tmp_tmphq7j0row_test_cases_index__reconstructFromMaxSum | the two results may come in either order | wrong-var#9: `r := (x, y);` -> `r := (y, x);` at s=0, m=1 -> real [1, -1], twin [-1, 1] |
| latitude | dafny_workout_tmp_tmp0abkw6f8_starter_ex12__findMax | ties: any index of a maximum | compare-flip#1: `if a[i] > a[max_idx] {` -> `if a[i] >= a[max_idx] {` at a=[0, 0] -> real 0, twin 1 |
| latitude | final_project_dafny_tmp_tmpmcywuqox_attempts_exercise4_find_max__findMax | ties: any index of a maximum | compare-flip#1: `if a[j] > maxVal {` -> `if a[j] >= maxVal {` at a=[0, 0] -> real [0, 0], twin [1, 0] |
| latitude | final_project_dafny_tmp_tmpmcywuqox_attempts_exercise6_binary_search__binarySearch | any negative position means absent | off-by-one#8: `return -(1);` -> `return -(2);` at a=[0], val=1 -> real -1, twin -2 |
| latitude | final_project_dafny_tmp_tmpmcywuqox_attempts_insertion_sort_normal__lookForMin | ties: any index of a minimum | compare-flip#1: `if a[j] < a[m] {` -> `if a[j] <= a[m] {` at a=[0, 0], i=0 -> real 0, twin 1 |
| latitude | final_project_dafny_tmp_tmpmcywuqox_final_project_3__nonZeroReturn | the contract is only that the result is non-zero | off-by-one#2: `y := x + 1;` -> `y := x + 2;` at x=0 -> real 1, twin 2 |
| latitude | laboratory_tmp_tmps8ws6mu2_dafny_tutorial_exercise12__findMax | ties: any index of a maximum | compare-flip#1: `if max < a[i] {` -> `if max <= a[i] {` at a=[0, 0] -> real 0, twin 1 |
| latitude | program_verification_dataset_tmp_tmpgbdrlnu__dafny_basic_examples_find_max__findMax | ties: any index of a maximum | compare-flip#1: `if a[i] > a[max] {` -> `if a[i] >= a[max] {` at a=[0, 0] -> real 0, twin 1 |
| latitude | programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_07_hoangkim_ex07_hoangkim__findMin | ties: any index of a minimum | compare-flip#1: `if a[j] < a[minIdx] {` -> `if a[j] <= a[minIdx] {` at a=[0, 0], lo=0 -> real 0, twin 1 |
| latitude | stunning_palm_tree_tmp_tmpr84c2iwh_ch1__minUnderSpec | named an underspecified minimum by its author | off-by-one: `r := x - 1;` -> `r := x - 2;` at x=0, y=0 -> real -1, twin -2 |
| latitude | stunning_palm_tree_tmp_tmpr84c2iwh_ch1__reconstructFromMaxSum | the two results may come in either order | wrong-var#9: `r := (x, y);` -> `r := (y, x);` at s=0, m=1 -> real [1, -1], twin [-1, 1] |
