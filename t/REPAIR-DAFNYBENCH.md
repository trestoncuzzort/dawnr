# Specification repair

For each task whose spec admits a survivor (`t/audit.py`), the clauses `t/contract_repair.py` adds: each holds for the real program at every domain point, and together they kill every survivor they can. **after** is the repaired task's own audit, from scratch.

- tasks with survivors: 53; repaired to zero survivors: 24
- refused because the real body never reads its parameters: 0
- dafny: repaired contract proved for the real body, twin refuted: 19 of 24

| task | survivors before | after | dafny real / twin | clauses added |
|---|---|---|---|---|
| bbfny_tmp_tmpw4m0jvl0_enjoying__multipleReturns | 1 | 0 | verified / refuted | `r.1 == x + -y` |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1_assignment_2__plusOne | 1 | 0 | verified / refuted | `y == x + 1` |
| cs245_verification_tmp_tmp0h_nxhqp_a8_q2__a8Q1 | 4 | 0 | verified / refuted | `(m == x or m == y) or m == z` |
| cs245_verification_tmp_tmp0h_nxhqp_sortingissues_firstattempt__sort | 1 | 1 |  /  | (none found) |
| dafny_exercises_tmp_tmpjm75muf__session3exercises_exercisemaximum__mmaximum1 | 1 | 1 |  /  | (none found) |
| dafny_experiences_tmp_tmp150sm9qy_dafny_started_tutorial_dafny_tutorial_array__findMax | 1 | 1 |  /  | (none found) |
| dafny_language_server_tmp_tmpkir0kenl_test_vscomp2010_problem1_summax__m | 21 | 5 | unproved / refuted | `forall t_rk in [0, len(a)) . a[t_rk] <= r.0`; `0 <= r.1` |
| dafny_learn_tmp_tmpn94ir40q_r01_assertions__max | 2 | 0 | verified / refuted | `c == a or c == b` |
| dafny_learning_experience_tmp_tmpuxvcet_u_week8_12_a3_search_findpositionofindex__findPositionOfElement | 11 | 6 | unproved / refuted | `r.0 <= 1`; `r.1 <= 1` |
| dafny_learning_experience_tmp_tmpuxvcet_u_week8_12_week9_lemma__assignmentsToMarkOne | 1 | 0 | timeout / refuted | `0 <= r` |
| dafny_programs_tmp_tmp99966ew4_mymax__max | 2 | 0 | verified / refuted | `c == a or c == b` |
| dafny_synthesis_task_id_126__sumOfCommonDivisors | 13 | 13 |  /  | (none found) |
| dafny_synthesis_task_id_145__maxDifference | 3 | 0 | verified / refuted | `exists i in [0, len(a)) . exists j in [0, len(a)) . a[i] - a[j] == diff` |
| dafny_synthesis_task_id_161__removeElements | 11 | 0 | verified / refuted | `forall t_rj in [0, len(a)) . inArray(a, a[t_rj]) and not inArray(b, a[t_rj]) ==> (exists t_rm in [0, len(result)) . result[t_rm] == a[t_rj])` |
| dafny_synthesis_task_id_249__intersection | 11 | 0 | verified / refuted | `forall t_rj in [0, len(a)) . inArray(a, a[t_rj]) and inArray(b, a[t_rj]) ==> (exists t_rm in [0, len(result)) . result[t_rm] == a[t_rj])` |
| dafny_synthesis_task_id_2__sharedElements | 11 | 0 | verified / refuted | `forall t_rj in [0, len(a)) . inArray(a, a[t_rj]) and inArray(b, a[t_rj]) ==> (exists t_rm in [0, len(result)) . result[t_rm] == a[t_rj])` |
| dafny_synthesis_task_id_397__medianOfThree | 48 | 48 |  /  | (none found) |
| dafny_synthesis_task_id_567__isSorted | 14 | 14 |  /  | (none found) |
| dafny_synthesis_task_id_603__lucidNumbers | 7 | 7 |  /  | (none found) |
| dafny_tmp_tmp0wu8wmfr_heimaverkefni_3_insertionsortmultiset__search | 5 | 5 |  /  | (none found) |
| dafny_tmp_tmp0wu8wmfr_tests_f1a__f | 2 | 0 | verified / refuted | `r == 0` |
| dafny_tmp_tmpmvs2dmry_examples1__multiReturn | 7 | 0 | verified / refuted | `r.1 == x + -y`; `r.0 == x + y` |
| dafny_training_tmp_tmp_n2kixni_session1_training1__abs | 8 | 3 | verified / refuted | `0 <= y` |
| dafny_training_tmp_tmp_n2kixni_session1_training1__find | 16 | 8 | verified / refuted | `index == -10 or index == 0` |
| dafny_training_tmp_tmp_n2kixni_session1_training1__max | 20 | 12 | verified / refuted | `m == 1 or m == 0` |
| dafny_verify_tmp_tmphq7j0row_dataset_bql_exampls_smallnum__add_small_numbers | 2 | 0 | unproved / refuted | `exists t_rk in [0, len(a)) . a[t_rk] == r` |
| dafny_verify_tmp_tmphq7j0row_dataset_c_convert_examples_11__main_v | 1 | 0 | verified / refuted | `r.1 == x` |
| dafny_verify_tmp_tmphq7j0row_dataset_c_convert_examples_15__main_v | 21 | 0 | verified / refuted | `k_out == -n + k` |
| dafny_verify_tmp_tmphq7j0row_fine_tune_examples_50_examples_41__main_v | 15 | 8 | verified / refuted | `r.0 == n` |
| dafny_verify_tmp_tmphq7j0row_fine_tune_examples_error_data_completion_11__main_v | 1 | 0 | verified / refuted | `r.1 == x` |
| dafny_verify_tmp_tmphq7j0row_generated_code_15__main_v | 21 | 0 | verified / refuted | `k_out == -n + k` |
| dafny_verify_tmp_tmphq7j0row_test_cases_ghost__myMethod | 28 | 23 | verified / refuted | `x <= y` |
| dafny_verify_tmp_tmphq7j0row_test_cases_index__index | 1 | 1 |  /  | (none found) |
| dafny_verify_tmp_tmphq7j0row_test_cases_index__reconstructFromMaxSum | 1 | 0 | verified / refuted | `r.0 == m` |
| dafny_workout_tmp_tmp0abkw6f8_starter_ex12__findMax | 1 | 1 |  /  | (none found) |
| final_project_dafny_tmp_tmpmcywuqox_attempts_exercise4_find_max__findMax | 1 | 1 |  /  | (none found) |
| final_project_dafny_tmp_tmpmcywuqox_attempts_exercise6_binary_search__binarySearch | 5 | 1 | verified / refuted | `-1 <= pos` |
| final_project_dafny_tmp_tmpmcywuqox_attempts_insertion_sort_normal__lookForMin | 1 | 1 |  /  | (none found) |
| final_project_dafny_tmp_tmpmcywuqox_final_project_3__nonZeroReturn | 2 | 2 |  /  | (none found) |
| laboratory_tmp_tmps8ws6mu2_dafny_tutorial_exercise12__findMax | 1 | 1 |  /  | (none found) |
| mfes_2021_tmp_tmpuljn8zd9_fcul_exercises_10_find__find | 3 | 3 |  /  | (none found) |
| nitwit_tmp_tmplm098gxz_nit__nit_add | 22 | 0 | timeout / refuted | `r.0 == (x + y) % b`; `r.1 == (x + y) / b` |
| nitwit_tmp_tmplm098gxz_nit__nit_increment | 20 | 13 | verified / refuted | `r.1 <= n`; `r.1 <= 1` |
| program_verification_dataset_tmp_tmpgbdrlnu__dafny_basic_examples_find_max__findMax | 1 | 1 |  /  | (none found) |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_07_hoangkim_ex07_hoangkim__findMin | 1 | 1 |  /  | (none found) |
| projectoscvs_tmp_tmp_02_gmcw_handout_1_cvs_handout1_55754_55780__euclidianDiv | 10 | 0 | timeout / refuted | `r.1 == (a + b) % b` |
| seng2011_tmp_tmpgk5jq85q_ass1_ex8__getEven | 1 | 1 |  /  | (none found) |
| software_building_and_verification_projects_tmp_tmp5tm1srrn_cvs_projeto_aula2__m4 | 4 | 0 | verified / refuted | `z == (x == y)` |
| software_building_and_verification_projects_tmp_tmp5tm1srrn_cvs_projeto_aula2__max | 10 | 0 | verified / refuted | `a <= z`; `b <= z`; `z == a or z == b` |
| software_verification_tmp_tmpv4ueky2d_best_time_to_buy_and_sell_stock_best_time_to_buy_and_sell_stock__best_time_to_buy_and_sell_stock | 6 | 0 | unproved / refuted | `max_profit == 0 or (exists i_v in [0, len(prices)) . exists j in [i_v + 1, len(prices)) . prices[j] - prices[i_v] == max_profit)` |
| stunning_palm_tree_tmp_tmpr84c2iwh_ch1__minUnderSpec | 10 | 4 | verified / refuted | `r < y` |
| stunning_palm_tree_tmp_tmpr84c2iwh_ch1__reconstructFromMaxSum | 1 | 0 | verified / refuted | `r.0 == m` |
| workshop_tmp_tmp0cu11bdq_workshop_answers_question6__arrayUpToN | 5 | 5 |  /  | (none found) |
