# t cross-kernel agreement, 2026-09-12 08:36Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| clover_abs__abs | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_array_product__arrayProduct | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| clover_array_sum__arraySum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| clover_avg__computeAvg | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_cal_ans__calDiv | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | malformed / refuted | unproved / refuted |
| clover_cal_sum__sum | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| clover_double_array_elements__double_array_elements | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| clover_double_quadruple__doubleQuadruple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_find__find | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| clover_integer_square_root__squareRoot | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted | unproved / unproved | verified / refuted | unproved / refuted |
| clover_is_even__computeIsEven | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_linear_search1__linearSearch | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| clover_min_array__minArray | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_min_of_two__min | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_multi_return__multipleReturns | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_quotient__quotient | verified / refuted | unproved / refuted | verified / refuted | timeout / refuted | unproved / refuted | verified / refuted | verified / refuted |
| clover_replace__replace | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / unproved | verified / refuted |
| clover_return_seven__m | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_rotate__rotate | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | verified / unproved | verified / unproved | verified / refuted |
| clover_swap__swap | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_swap_arith__swapArithmetic | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_swap_in_array__swap | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_swap_sim__swapSimultaneous | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_test_array__testArrayElements | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_triple__triple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_triple3__triple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_triple4__triple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_update_array__updateElements | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| dafny_exercises_tmp_tmpjm75muf__session2exercises_exercisefibonacci__fibonacci1 | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| dafny_exercises_tmp_tmpjm75muf__session2exercises_exercisefibonacci__fibonacci2 | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| dafny_exercises_tmp_tmpjm75muf__session2exercises_exercisefibonacci__fibonacci3 | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| dafny_exercises_tmp_tmpjm75muf__session2exercises_exercisesquare_root__mroot1 | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_exercises_tmp_tmpjm75muf__session2exercises_exercisesquare_root__mroot2 | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / unproved | verified / refuted | verified / refuted |
| dafny_exercises_tmp_tmpjm75muf__session2exercises_exercisesquare_root__mroot3 | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | timeout / unproved | verified / refuted | verified / refuted |
| dafny_exercises_tmp_tmpjm75muf__session3exercises_exercisemaximum__mfirstMaximum | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_exercises_tmp_tmpjm75muf__session3exercises_exercisemaximum__mmaximum1 | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| dafny_exercises_tmp_tmpjm75muf__session4exercises_exercisefirstzero__mfirstCero | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| dafny_experiences_tmp_tmp150sm9qy_dafny_started_tutorial_dafny_tutorial_array__findMax | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| dafnyexercises_tmp_tmpd6qyevja_part1_q1__addArrays | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| dafnyprograms_tmp_tmp74_f9k_c_invertarray__invertArray | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | timeout / unproved | verified / refuted |
| dafnyprojects_tmp_tmp2acw_s4s_longestprefix__longestPrefix | verified / refuted | unproved / refuted | unproved / timeout | verified / refuted | unproved / unproved | unproved / unproved | unproved / refuted |
| dafny_learning_experience_tmp_tmpuxvcet_u_week1_7_a2_q1_trimmed_copy_______mult | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| dafny_learning_experience_tmp_tmpuxvcet_u_week1_7_maxsum__maxSum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_learning_experience_tmp_tmpuxvcet_u_week1_7_week5_computepower__calcPower | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_learning_experience_tmp_tmpuxvcet_u_week8_12_a3_search_findpositionofindex__findPositionOfElement | vacuous / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | timeout / refuted | unproved / refuted |
| dafny_learning_experience_tmp_tmpuxvcet_u_week8_12_week9_lemma__assignmentsToMarkOne | timeout / refuted | unproved / refuted | verified / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| dafny_programs_tmp_tmp99966ew4_mymax__max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_ai_agent_validation_examples__computePower | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_ai_agent_validation_examples__cube | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_ai_agent_verify_examples_computepower__computePower | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_ai_agent_verify_examples_cube__cube | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_fine_tune_examples_50_examples_41__main_v | verified / refuted | unproved / refuted | verified / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_fine_tune_examples_error_data_completion_11__main_v | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_generated_code_15__main_v | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_generated_code_computepower__computePower | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_generated_code_minimum__minimum | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_generated_code_mult__mult | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| dafny_verify_tmp_tmphq7j0row_test_cases_function__triple_p | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_test_cases_function__tripleConditions | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_test_cases_ghost__doubleQuadruple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_test_cases_ghost__m | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_test_cases_ghost__myMethod | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_test_cases_ghost__triple | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_test_cases_index__index | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_test_cases_index__maxSum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_test_cases_index__min | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_test_cases_index__reconstructFromMaxSum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_test_cases_loopinvariant__downWhileGreater | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_test_cases_loopinvariant__downWhileNotEqual | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_test_cases_loopinvariant__upWhileLess | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_test_cases_loopinvariant__upWhileNotEqual | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| dafny_verify_tmp_tmphq7j0row_test_cases_triple__tripleConditions | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_dataset_c_convert_examples_11__main_v | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_dataset_c_convert_examples_15__main_v | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_dataset_bql_exampls_min__min | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_dataset_bql_exampls_smallnum__add_small_numbers | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / unproved | unproved / refuted |
| dafny_verify_tmp_tmphq7j0row_dataset_bql_exampls_square__square | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_verify_tmp_tmphq7j0row_dataset_error_data_real_error_iseven_success_1__is_even | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| dafny_tmp_tmp0wu8wmfr_heimaverkefni_1_linearsearch__searchRecursive | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| dafny_tmp_tmp0wu8wmfr_heimaverkefni_3_insertionsortmultiset__search | verified / refuted | verified / unproved | abstain / abstain | abstain / abstain | unproved / unproved | timeout / unproved | verified / unproved |
| dafny_tmp_tmp0wu8wmfr_tests_f1a__f | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_tmp_tmp0wu8wmfr_tests_f1a__mid | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_tmp_tmp0wu8wmfr_tests_search1000__search1000 | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| dafny_tmp_tmp0wu8wmfr_tests_sumintsloop__sumIntsLoop | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| dafny_tmp_tmpj88zq5zt_2_kontrakte_max__max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_tmp_tmpj88zq5zt_2_kontrakte_reverse3__swap3 | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| dafny_tmp_tmpmvs2dmry_slowmax__slow_max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_tmp_tmpmvs2dmry_examples1__abs | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_tmp_tmpmvs2dmry_examples1__max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_tmp_tmpmvs2dmry_examples1__multiReturn | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_tmp_tmpmvs2dmry_examples2__product | verified / refuted | unproved / refuted | timeout / unproved | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| dafny_tmp_tmpmvs2dmry_examples2__add_by_inc | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_tmp_tmpmvs2dmry_examples2__gcdCalc | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / unproved | unproved / refuted | verified / refuted |
| dafny_tmp_tmpmvs2dmry_pancakesort_flip__flip | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / unproved | timeout / refuted | verified / refuted |
| dafny_tmp_tmpv_d3qi10_2_min__minArray | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_tmp_tmpv_d3qi10_2_min__minMethod | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| final_project_dafny_tmp_tmpmcywuqox_attempts_exercise3_increment_array__incrementArray | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| final_project_dafny_tmp_tmpmcywuqox_attempts_exercise4_find_max__findMax | verified / refuted | verified / refuted | verified / unproved | verified / refuted | unproved / unproved | timeout / unproved | verified / refuted |
| final_project_dafny_tmp_tmpmcywuqox_attempts_exercise6_binary_search__binarySearch | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | unproved / unproved | malformed / malformed | unproved / refuted |
| final_project_dafny_tmp_tmpmcywuqox_attempts_insertion_sort_normal__lookForMin | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| final_project_dafny_tmp_tmpmcywuqox_final_project_3__nonZeroReturn | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| flexweek_tmp_tmpc_tfdj_3_ex3__max | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | unproved / unproved | timeout / unproved | lower-error / lower-error |
| formal_methods_of_software_development_tmp_tmppryvbyty_bloque_1_lab3__computeFact | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| formal_methods_of_software_development_tmp_tmppryvbyty_bloque_1_lab3__computeFact2 | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| formal_methods_of_software_development_tmp_tmppryvbyty_bloque_1_lab3__sqare | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| formal_methods_of_software_development_tmp_tmppryvbyty_bloque_1_lab3__sqare2 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| formalmethods_tmp_tmpvda2r3_o_dafny_invariants_ex1__mult | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| formalmethods_tmp_tmpvda2r3_o_dafny_invariants_ex2__pot | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| m2_tmp_tmp2laaavvl_software_verification_exercices_exo4_countandreturn__countToAndReturnN | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| m2_tmp_tmp2laaavvl_software_verification_exercices_exo7_computesum__computeSum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| m2_tmp_tmp2laaavvl_software_verification_exercices_exo9_carre__carre | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| mfes_2021_tmp_tmpuljn8zd9_fcul_exercises_10_find__find | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| mfes_2021_tmp_tmpuljn8zd9_fcul_exercises_8_sum__sum | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mfs_tmp_tmpmmnu354t_testes_anteriores_t2_ex5_2020_2__leq | verified / unproved | lower-error / lower-error | timeout / refuted | verified / refuted | unproved / unproved | timeout / refuted | abstain / abstain |
| mieic_mfes_tmp_tmpq3ho7nve_exams_appeal_20_p4__calcF | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mieic_mfes_tmp_tmpq3ho7nve_exams_mt2_19_p4__calcR | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| metodos_formais_tmp_tmpbez22nnn_aula_2_ex1__mult | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| metodos_formais_tmp_tmpbez22nnn_aula_2_ex2__pot | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| metodos_formais_tmp_tmpbez22nnn_aula_4_ex3__computeFib | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| metodos_formais_tmp_tmpql2hwcsh_invariantes_fatorial2__fatorial | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| metodos_formais_tmp_tmpql2hwcsh_invariantes_fibonacci__computeFib | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| metodos_formais_tmp_tmpql2hwcsh_invariantes_multiplicador__mult | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| metodos_formais_tmp_tmpql2hwcsh_invariantes_potencia__pot | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| prog_fun_solutions_tmp_tmp7_gmnz5f_extra_mod__mod | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| prog_fun_solutions_tmp_tmp7_gmnz5f_extra_mod2__mod2 | refuted / refuted | refuted / refuted | timeout / refuted | refuted / refuted | refuted / refuted | refuted / refuted | timeout / refuted |
| prog_fun_solutions_tmp_tmp7_gmnz5f_extra_pow__pow | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| prog_fun_solutions_tmp_tmp7_gmnz5f_extra_sum__sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| prog_fun_solutions_tmp_tmp7_gmnz5f_mockexam2_p2__problem2 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| prog_fun_solutions_tmp_tmp7_gmnz5f_mockexam2_p3__problem3 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| prog_fun_solutions_tmp_tmp7_gmnz5f_mockexam2_p5__problem5 | verified / refuted | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| program_verification_dataset_tmp_tmpgbdrlnu__dafny_algorithms_and_leetcode_examples_simplemultiplication__foo | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| program_verification_dataset_tmp_tmpgbdrlnu__dafny_basic_examples_add_by_one__add_by_one | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| program_verification_dataset_tmp_tmpgbdrlnu__dafny_basic_examples_add_by_one_details__plus_one | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| program_verification_dataset_tmp_tmpgbdrlnu__dafny_basic_examples_find_max__findMax | verified / refuted | unproved / refuted | unproved / unproved | timeout / refuted | unproved / unproved | unproved / unproved | unproved / refuted |
| program_verification_dataset_tmp_tmpgbdrlnu__dafny_basic_examples_sumto_sol__sumUpTo | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| program_verification_dataset_tmp_tmpgbdrlnu__dafny_from_dafny_main_repo_dafny2_classics__additiveFactorial | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| program_verification_dataset_tmp_tmpgbdrlnu__dafny_variant_examples_katzmanna__ninetyOne | verified / unproved | unproved / unproved | unproved / unproved | timeout / timeout | unproved / refuted | timeout / refuted | unproved / unproved |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_04_hoangkim_ex_04_hoangkim__intDivImpl | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_04_hoangkim_ex_04_hoangkim__sumOdds | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_05_hoangkim_ex_05_hoangkim__factIter | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_05_hoangkim_ex_05_hoangkim__fibIter | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_05_hoangkim_ex_05_hoangkim__gcdI | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_06_hoangkim_ex06_solution__gcdI | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_06_hoangkim_ex_06_hoangkim__gcdI | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_07_hoangkim_ex07_hoangkim__findMin | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_07_hoangkim_ex07_hoangkim__swap | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_10_hoangkim_ex10_hoangkim__square0 | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_10_hoangkim_ex10_hoangkim__square1 | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| programmverifikation_und_synthese_tmp_tmppurk6ime_example_dafnyintro_01_simple_loops__gauss | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| programmverifikation_und_synthese_tmp_tmppurk6ime_example_dafnyintro_01_simple_loops__sumOdds | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| projectoscvs_tmp_tmp_02_gmcw_handout_1_cvs_handout1_55754_55780__euclidianDiv | verified / refuted | unproved / refuted | unproved / timeout | verified / refuted | verified / unproved | verified / refuted | unproved / refuted |
| projectoscvs_tmp_tmp_02_gmcw_handout_1_cvs_handout1_55754_55780__peasantMult | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| seng2011_tmp_tmpgk5jq85q_ass1_ex8__getEven | verified / refuted | verified / refuted | verified / timeout | verified / refuted | timeout / timeout | verified / refuted | verified / refuted |
| seng2011_tmp_tmpgk5jq85q_flex_ex2__max | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / refuted | timeout / refuted | verified / refuted |
| seng2011_tmp_tmpgk5jq85q_p2__absIt | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / unproved | verified / refuted |
| software_verification_tmp_tmpv4ueky2d_best_time_to_buy_and_sell_stock_best_time_to_buy_and_sell_stock__best_time_to_buy_and_sell_stock | verified / refuted | verified / refuted | verified / unproved | verified / refuted | timeout / refuted | timeout / refuted | timeout / timeout |
| software_building_and_verification_projects_tmp_tmp5tm1srrn_cvs_projeto_aula2__m3 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| software_building_and_verification_projects_tmp_tmp5tm1srrn_cvs_projeto_aula2__m4 | verified / decorative | verified / decorative | verified / decorative | verified / decorative | verified / decorative | verified / decorative | verified / decorative |
| software_building_and_verification_projects_tmp_tmp5tm1srrn_cvs_projeto_aula2__max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| software_building_and_verification_projects_tmp_tmp5tm1srrn_cvs_projeto_aula2__mystery1 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| tfg_tmp_tmpbvsao41w_algoritmos_dafny_div_ent_it__div_ent_it | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| workshop_tmp_tmp0cu11bdq_lecture_answers_triangle_number__triangleNumber | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| workshop_tmp_tmp0cu11bdq_workshop_answers_question6__arrayUpToN | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / unproved | verified / unproved | verified / refuted |
| bbfny_tmp_tmpw4m0jvl0_enjoying__abs | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| bbfny_tmp_tmpw4m0jvl0_enjoying__max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| bbfny_tmp_tmpw4m0jvl0_enjoying__multipleReturns | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1_assignment_2__arraySum | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / unproved | unproved / refuted |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1_assignment_2__intDiv | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1_assignment_2__isPrime | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1_assignment_2__plusOne | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1_assignment_2__reverse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| cs245_verification_tmp_tmp0h_nxhqp_a8_q1__a8Q1 | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| cs245_verification_tmp_tmp0h_nxhqp_a8_q2__a8Q1 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| cs245_verification_tmp_tmp0h_nxhqp_assignments_simple__simple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| cs245_verification_tmp_tmp0h_nxhqp_sortingissues_firstattempt__sort | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / unproved | unproved / refuted |
| cs245_verification_tmp_tmp0h_nxhqp_power__compute_power | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| cs357_tmp_tmpn4fsvwzs_lab7_question2__two | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| cs357_tmp_tmpn4fsvwzs_lab7_question5__a1 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_fibonacci__computeFib | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_modifying_arrays__incrementArray | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_modifying_arrays__updateElements | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| dafny_duck_tmp_tmplawbgxjo_p3__max | verified / refuted | verified / refuted | verified / unproved | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| dafny_exercise_tmp_tmpouftptir_appendarray__appendArray | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | verified / refuted |
| dafny_exercise_tmp_tmpouftptir_maxarray__maxArray | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_exercise_tmp_tmpouftptir_prac3_ex2__getEven | verified / refuted | verified / refuted | verified / timeout | verified / refuted | timeout / timeout | verified / unproved | verified / refuted |
| dafny_language_server_tmp_tmpkir0kenl_test_vscomp2010_problem1_summax__m | verified / refuted | unproved / refuted | timeout / unproved | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| dafny_language_server_tmp_tmpkir0kenl_test_vsi_benchmarks_b1__add | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| dafny_language_server_tmp_tmpkir0kenl_test_dafny1_cubes__cubes | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| dafny_language_server_tmp_tmpkir0kenl_test_dafny2_turingfactorial__computeFactorial | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| dafny_language_server_tmp_tmpkir0kenl_test_tutorial_maximum__maximum | verified / refuted | unproved / refuted | unproved / unproved | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| dafny_learn_tmp_tmpn94ir40q_r01_assertions__abs | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_learn_tmp_tmpn94ir40q_r01_assertions__max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_learn_tmp_tmpn94ir40q_r01_functions__abs | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_learn_tmp_tmpn94ir40q_r01_functions__testDouble | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| dafny_programs_tmp_tmpcwodh6qh_src_expt__expt | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| dafny_programs_tmp_tmpcwodh6qh_src_factorial__factorial | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| dafny_programs_tmp_tmpcwodh6qh_src_max__max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_101__kthElement | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_106__appendArrayToSeq | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / unproved | verified / unproved | verified / refuted |
| dafny_synthesis_task_id_126__sumOfCommonDivisors | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | verified / unproved | unproved / unproved | verified / refuted |
| dafny_synthesis_task_id_127__multiply | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_135__nthHexagonalNumber | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_14__triangularPrismVolume | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_17__squarePerimeter | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_171__pentagonPerimeter | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_227__minOfThree | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_234__cubeVolume | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_238__countNonEmptySubstrings | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_240__replaceLastElement | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_242__countCharacters | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_257__swap | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_261__elementWiseDivision | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| dafny_synthesis_task_id_262__splitArray | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_264__dogYears | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_266__lateralSurfaceArea | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_268__starNumber | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_269__asciiValue | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_273__subtractSequences | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| dafny_synthesis_task_id_279__nthDecagonalNumber | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_282__elementWiseSubtraction | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| dafny_synthesis_task_id_292__quotient | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_3__isNonPrime | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | unproved / unproved | timeout / unproved | verified / refuted |
| dafny_synthesis_task_id_304__elementAtIndexAfterRotation | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_309__max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_396__startAndEndWithSameChar | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_397__medianOfThree | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_404__min | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_406__isOdd | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_414__anyValueExists | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| dafny_synthesis_task_id_432__medianLength | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_435__lastDigit | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_441__cubeSurfaceArea | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_445__multiplyElements | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| dafny_synthesis_task_id_452__calculateLoss | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_458__rectangleArea | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_460__getFirstElements | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / unproved | verified / unproved | verified / refuted |
| dafny_synthesis_task_id_470__pairwiseAddition | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | timeout / timeout | verified / unproved | verified / refuted |
| dafny_synthesis_task_id_576__isSublist | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | unproved / unproved | unproved / unproved | verified / refuted |
| dafny_synthesis_task_id_577__factorialOfLastDigit | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_578__interleave | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / unproved | verified / refuted |
| dafny_synthesis_task_id_58__hasOppositeSign | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_581__squarePyramidSurfaceArea | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_586__splitAndAppend | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | unproved / refuted | verified / refuted |
| dafny_synthesis_task_id_587__arrayToSeq | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| dafny_synthesis_task_id_59__nthOctagonalNumber | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_591__swapFirstAndLast | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_598__isArmstrong | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_600__isEven | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_603__lucidNumbers | verified / refuted | verified / refuted | timeout / timeout | abstain / abstain | timeout / timeout | verified / unproved | verified / refuted |
| dafny_synthesis_task_id_605__isPrime | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / unproved | timeout / unproved | verified / refuted |
| dafny_synthesis_task_id_610__removeElement | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | verified / refuted |
| dafny_synthesis_task_id_616__elementWiseModulo | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| dafny_synthesis_task_id_618__elementWiseDivide | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| dafny_synthesis_task_id_62__findSmallest | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_625__swapFirstAndLast | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_626__areaOfLargestTriangleInSemicircle | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_637__isBreakEven | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_641__nthNonagonalNumber | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_69__containsSequence | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / unproved | unproved / refuted | verified / refuted |
| dafny_synthesis_task_id_728__addLists | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| dafny_synthesis_task_id_762__isMonthWith30Days | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_77__isDivisibleBy11 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_79__isLengthOdd | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_792__countLists | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_8__squareElements | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| dafny_synthesis_task_id_80__tetrahedralNumber | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_801__countEqualNumbers | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_808__containsK | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | unproved / refuted | verified / refuted |
| dafny_synthesis_task_id_809__isSmaller | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / timeout | unproved / refuted | verified / refuted |
| dafny_synthesis_task_id_86__centeredHexagonalNumber | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_89__closestSmaller | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_synthesis_task_id_95__smallestListLength | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_training_tmp_tmp_n2kixni_session1_training1__abs | verified / decorative | verified / decorative | verified / decorative | verified / decorative | verified / decorative | verified / decorative | verified / decorative |
| dafny_training_tmp_tmp_n2kixni_session1_training1__find | verified / refuted | unproved / refuted | unproved / unproved | timeout / refuted | unproved / unproved | unproved / unproved | unproved / refuted |
| dafny_training_tmp_tmp_n2kixni_session1_training1__max | verified / decorative | verified / decorative | verified / decorative | verified / decorative | verified / decorative | verified / decorative | verified / decorative |
| dafny_workout_tmp_tmp0abkw6f8_starter_ex01__max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_workout_tmp_tmp0abkw6f8_starter_ex02__abs | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_workout_tmp_tmp0abkw6f8_starter_ex03__abs | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_workout_tmp_tmp0abkw6f8_starter_ex09__computeFib | verified / refuted | unproved / refuted | abstain / abstain | timeout / refuted | unproved / unproved | unproved / unproved | lower-error / lower-error |
| dafny_workout_tmp_tmp0abkw6f8_starter_ex12__findMax | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| dafny_examples_tmp_tmp8qotd4ez_leetcode_0070_climbing_stairs__climbStairs | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| dafny_misc_tmp_tmpg4vzlnm1_rosetta_code_factorial__iterativeFactorial | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| dafny_projects_tmp_tmpjutqwjv4_tutorial_tutorial__computeFib | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| formal_methods_in_software_engineering_tmp_tmpe7fjnek6_labs4_gr2__divMod1 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| formal_methods_in_software_engineering_tmp_tmpe7fjnek6_labs4_gr2__hoareTripleReqEns | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| formal_methods_in_software_engineering_tmp_tmpe7fjnek6_labs4_gr2__sqrSum1 | verified / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| formal_verication_dafny_tmp_tmpwgl2qz28_challenges_ex2__allow42 | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| formal_verication_dafny_tmp_tmpwgl2qz28_challenges_ex2__forbid42 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| laboratory_tmp_tmps8ws6mu2_dafny_tutorial_exercise12__findMax | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| laboratory_tmp_tmps8ws6mu2_dafny_tutorial_exercise9__computeFib | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| nitwit_tmp_tmplm098gxz_nit__max_nit | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| nitwit_tmp_tmplm098gxz_nit__nit_add | verified / refuted | unproved / refuted | verified / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| nitwit_tmp_tmplm098gxz_nit__nit_increment | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| se2011_tmp_tmp71eb82zt_ass1_ex4__eval | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| se2011_tmp_tmp71eb82zt_ass1_ex6__ceiling7 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| software_analysis_tmp_tmpmt6bo9sf_ss__find_min_index | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / unproved | verified / unproved | verified / refuted |
| stunning_palm_tree_tmp_tmpr84c2iwh_ch1__min | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| stunning_palm_tree_tmp_tmpr84c2iwh_ch1__minUnderSpec | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| stunning_palm_tree_tmp_tmpr84c2iwh_ch1__reconstructFromMaxSum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| stunning_palm_tree_tmp_tmpr84c2iwh_ch1__triple_p | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| stunning_palm_tree_tmp_tmpr84c2iwh_ch1__triple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| t1_mf_tmp_tmpi_sqie4j_exemplos_introducao_ex4__fatorial | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `clover_abs__abs.dfy` 33f1a307d5f4103c…, `clover_abs__abs.rs` 732e707fbd23a808…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| spark | 10 | 81 | clover_min_array__minArray, dafny_exercise_tmp_tmpouftptir_maxarray__maxArray, dafny_exercises_tmp_tmpjm75muf__session3exercises_exercisemaximum__mfirstMaximum, dafny_synthesis_task_id_62__findSmallest, dafny_synthesis_task_id_95__smallestListLength, dafny_tmp_tmpv_d3qi10_2_min__minArray, dafny_verify_tmp_tmphq7j0row_dataset_bql_exampls_min__min, mieic_mfes_tmp_tmpq3ho7nve_exams_mt2_19_p4__calcR, programmverifikation_und_synthese_tmp_tmppurk6ime_example_dafnyintro_01_simple_loops__gauss, workshop_tmp_tmp0cu11bdq_lecture_answers_triangle_number__triangleNumber |
| verus | 5 | 54 | dafny_exercises_tmp_tmpjm75muf__session2exercises_exercisesquare_root__mroot1, formalmethods_tmp_tmpvda2r3_o_dafny_invariants_ex1__mult, metodos_formais_tmp_tmpbez22nnn_aula_2_ex1__mult, metodos_formais_tmp_tmpql2hwcsh_invariantes_multiplicador__mult, mfes_2021_tmp_tmpuljn8zd9_fcul_exercises_8_sum__sum |
| lean | 5 | 124 | clover_find__find, clover_linear_search1__linearSearch, dafny_programs_tmp_tmpcwodh6qh_src_factorial__factorial, dafny_verify_tmp_tmphq7j0row_test_cases_loopinvariant__downWhileGreater, prog_fun_solutions_tmp_tmp7_gmnz5f_extra_pow__pow |
| framac | 4 | 45 | dafny_synthesis_task_id_262__splitArray, dafny_synthesis_task_id_577__factorialOfLastDigit, dafny_synthesis_task_id_86__centeredHexagonalNumber, dafny_verify_tmp_tmphq7j0row_test_cases_ghost__triple |
| rocq | 4 | 106 | dafny_learn_tmp_tmpn94ir40q_r01_functions__testDouble, dafny_verify_tmp_tmphq7j0row_dataset_error_data_real_error_iseven_success_1__is_even, prog_fun_solutions_tmp_tmp7_gmnz5f_extra_sum__sum, software_building_and_verification_projects_tmp_tmp5tm1srrn_cvs_projeto_aula2__mystery1 |
| dafny | 0 | 2 | (none) |
| fstar | 0 | 40 | (none) |

Of the 28 tasks in six, 10 are spark alone, 5 are verus alone, 5 are lean alone, 4 are framac alone, 4 are rocq alone.
