# The lifter over DafnyBench: the 785, measured 2026-09-06

Produced by `t/lifter.py --dir <DafnyBench ground_truth> --jobs 4 --timeout 200`
and `t/lift_census.py` at the commit that adds this file, on the Dell with
dafny 4.11.0. One row per gradable method (968 over 785 files); the census
column is `t/coverage_census.py`'s lexical verdict and the disagreement
verdict follows LIFTER-DESIGN.md section 8. A lifted row has passed
check_wf, executed under interp.py, verified its equivalence lemmas
(section 9) and agreed with the source on every differential point run
(section 10, capped at 512 points in shell order, so the row says N of M).
Body fidelity is a bounded sample; nl/FIDELITY.md states what that sample
covers and the five conditions a coverage claim over nl/ must meet. The
per-row records (task, sidecar, checker and differential files) are not in
the repo; regenerate them with the commands above.

# Lifter census disagreement table

Method rows: 968 total, 159 lifted, 154 counted (decision 17).
Program rows: 785 total, 99 lifted (every method lifts), 91 multi-method.
Census in_fragment: 77 method rows, 77 program rows.

Disagreement verdict counts:
- agree: 569
- lifter: 58
- census: 0
- undecided: 26
- gap-name: 315

Refusal reason counts:
- array: 61
- array-mutation: 4
- as-cast: 7
- bodyless-function: 10
- bodyless-method: 13
- calls-other-method: 5
- datatype: 38
- div-mod: 62
- early-exit: 15
- function-contract: 41
- function-method: 1
- generics: 1
- ghost-local: 2
- heap: 50
- higher-order: 8
- let-expression: 27
- lift-check-failed: 4
- map: 1
- multi-return: 57
- nested-seq: 20
- no-method: 132
- nondet: 2
- old: 1
- parse-failure: 1
- real: 16
- resolve-failure: 2
- return-not-assigned-on-all-paths: 5
- seq-literal: 12
- seq-return: 23
- seq-slice: 31
- set: 5
- string-char: 22
- such-that-exec: 1
- tuple: 3
- type-decl: 5
- unbounded-quantifier: 52
- zero-returns: 69

## Disagreement pair tally (gap-name and lifter rows)

Lifter side (refusal reason, or `lifted`) paired with each census gap name that fired, tallied over every row whose disagreement verdict is `gap-name` or `lifter`; a row with no fired gap (an in-fragment `lifter` row) is tallied under `(in-fragment)`.

| lifter side | census gap | count |
|---|---|---|
| lifted | multi-method | 57 |
| no-method | zero-returns | 46 |
| function-contract | array | 41 |
| no-method | heap | 38 |
| no-method | module | 37 |
| no-method | set | 37 |
| unbounded-quantifier | array | 35 |
| no-method | multi-method | 33 |
| unbounded-quantifier | multi-method | 32 |
| heap | array | 28 |
| lifted | zero-returns | 28 |
| no-method | nested-seq | 28 |
| no-method | seq-literal | 28 |
| no-method | seq-slice | 28 |
| unbounded-quantifier | seq-slice | 28 |
| no-method | bodyless-function | 24 |
| no-method | div-mod | 24 |
| no-method | generics | 24 |
| no-method | array | 21 |
| unbounded-quantifier | div-mod | 20 |
| no-method | (in-fragment) | 19 |
| no-method | type-decl | 18 |
| function-contract | array-mutation | 17 |
| function-contract | multi-method | 17 |
| no-method | datatype | 17 |
| function-contract | seq-slice | 16 |
| lifted | div-mod | 16 |
| lifted | multi-return | 16 |
| unbounded-quantifier | set | 16 |
| function-contract | zero-returns | 15 |
| no-method | array-mutation | 14 |
| no-method | seq-return | 14 |
| unbounded-quantifier | zero-returns | 14 |
| no-method | early-exit | 13 |
| unbounded-quantifier | array-mutation | 13 |
| unbounded-quantifier | early-exit | 13 |
| heap | early-exit | 12 |
| no-method | string-char | 12 |
| function-contract | set | 11 |
| let-expression | array | 11 |
| let-expression | unbounded-quantifier | 11 |
| unbounded-quantifier | multi-return | 11 |
| lifted | bodyless-method | 10 |
| no-method | map | 10 |
| no-method | unbounded-quantifier | 10 |
| unbounded-quantifier | seq-literal | 10 |
| no-method | bodyless-method | 9 |
| unbounded-quantifier | seq-return | 9 |
| heap | array-mutation | 8 |
| heap | zero-returns | 8 |
| let-expression | datatype | 8 |
| let-expression | seq-slice | 8 |
| no-method | higher-order | 8 |
| no-method | io | 8 |
| as-cast | string-char | 7 |
| function-contract | div-mod | 7 |
| function-contract | early-exit | 7 |
| no-method | nondet | 7 |
| let-expression | map | 6 |
| let-expression | multi-method | 6 |
| let-expression | set | 6 |
| lifted | nondet | 6 |
| no-method | real | 6 |
| no-method | such-that-exec | 6 |
| no-method | tuple | 6 |
| calls-other-method | multi-method | 5 |
| function-contract | multi-return | 5 |
| function-contract | seq-literal | 5 |
| function-contract | seq-return | 5 |
| let-expression | generics | 5 |
| let-expression | seq-update | 5 |
| lifted | early-exit | 5 |
| no-method | multi-return | 5 |
| type-decl | multi-method | 5 |
| type-decl | set | 5 |
| type-decl | such-that-exec | 5 |
| heap | div-mod | 4 |
| heap | seq-slice | 4 |
| let-expression | early-exit | 4 |
| let-expression | nested-seq | 4 |
| lifted | decreases-star | 4 |
| lifted | real | 4 |
| lifted | string-char | 4 |
| unbounded-quantifier | nested-seq | 4 |
| unbounded-quantifier | seq-update | 4 |
| unbounded-quantifier | string-char | 4 |
| as-cast | char-arith | 3 |
| as-cast | div-mod | 3 |
| as-cast | seq-literal | 3 |
| function-contract | real | 3 |
| heap | multi-method | 3 |
| heap | set | 3 |
| heap | string-char | 3 |
| let-expression | array-mutation | 3 |
| let-expression | bodyless-function | 3 |
| let-expression | heap | 3 |
| let-expression | seq-literal | 3 |
| let-expression | string-char | 3 |
| let-expression | tuple | 3 |
| let-expression | type-decl | 3 |
| lift-check-failed | array | 3 |
| lifted | seq-return | 3 |
| type-decl | early-exit | 3 |
| type-decl | seq-literal | 3 |
| type-decl | seq-return | 3 |
| as-cast | early-exit | 2 |
| as-cast | set | 2 |
| function-contract | nondet | 2 |
| heap | io | 2 |
| let-expression | (in-fragment) | 2 |
| let-expression | div-mod | 2 |
| let-expression | higher-order | 2 |
| let-expression | module | 2 |
| let-expression | multi-return | 2 |
| let-expression | seq-return | 2 |
| let-expression | zero-returns | 2 |
| lift-check-failed | multi-method | 2 |
| lift-check-failed | zero-returns | 2 |
| lifted | nested-seq | 2 |
| lifted | such-that-exec | 2 |
| no-method | decreases-star | 2 |
| no-method | seq-update | 2 |
| return-not-assigned-on-all-paths | div-mod | 2 |
| return-not-assigned-on-all-paths | early-exit | 2 |
| return-not-assigned-on-all-paths | multi-method | 2 |
| type-decl | seq-slice | 2 |
| type-decl | string-char | 2 |
| type-decl | zero-returns | 2 |
| unbounded-quantifier | bodyless-method | 2 |
| unbounded-quantifier | heap | 2 |
| calls-other-method | div-mod | 1 |
| calls-other-method | io | 1 |
| calls-other-method | multi-return | 1 |
| calls-other-method | seq-literal | 1 |
| calls-other-method | seq-return | 1 |
| calls-other-method | string-char | 1 |
| calls-other-method | zero-returns | 1 |
| datatype | generics | 1 |
| function-contract | heap | 1 |
| function-contract | higher-order | 1 |
| function-contract | io | 1 |
| function-contract | nested-seq | 1 |
| function-contract | seq-update | 1 |
| function-contract | string-char | 1 |
| function-contract | type-decl | 1 |
| function-contract | unbounded-quantifier | 1 |
| generics | array | 1 |
| generics | array-mutation | 1 |
| generics | early-exit | 1 |
| generics | multi-method | 1 |
| generics | zero-returns | 1 |
| ghost-local | array | 1 |
| ghost-local | div-mod | 1 |
| ghost-local | multi-method | 1 |
| ghost-local | multi-return | 1 |
| ghost-local | zero-returns | 1 |
| heap | bodyless-function | 1 |
| heap | generics | 1 |
| heap | higher-order | 1 |
| heap | module | 1 |
| heap | type-decl | 1 |
| higher-order | generics | 1 |
| higher-order | heap | 1 |
| let-expression | bitvector | 1 |
| let-expression | extreme-predicate | 1 |
| let-expression | mutual-recursion | 1 |
| let-expression | nondet | 1 |
| let-expression | real | 1 |
| let-expression | such-that-exec | 1 |
| lift-check-failed | array-mutation | 1 |
| lift-check-failed | early-exit | 1 |
| lift-check-failed | multi-return | 1 |
| lifted | io | 1 |
| lifted | seq-literal | 1 |
| lifted | seq-slice | 1 |
| lifted | set | 1 |
| nested-seq | seq-literal | 1 |
| nested-seq | seq-return | 1 |
| nested-seq | tuple | 1 |
| no-method | bitvector | 1 |
| no-method | extreme-predicate | 1 |
| no-method | iterator | 1 |
| no-method | mutual-recursion | 1 |
| no-method | seq-comprehension | 1 |
| old | array | 1 |
| old | array-mutation | 1 |
| old | multi-method | 1 |
| old | seq-slice | 1 |
| old | set | 1 |
| old | zero-returns | 1 |
| parse-failure | bitvector | 1 |
| resolve-failure | (in-fragment) | 1 |
| resolve-failure | datatype | 1 |
| resolve-failure | generics | 1 |
| return-not-assigned-on-all-paths | array | 1 |
| return-not-assigned-on-all-paths | nondet | 1 |
| return-not-assigned-on-all-paths | seq-slice | 1 |
| type-decl | div-mod | 1 |
| unbounded-quantifier | decreases-star | 1 |
| unbounded-quantifier | generics | 1 |
| unbounded-quantifier | higher-order | 1 |
| unbounded-quantifier | such-that-exec | 1 |

## Lifter-verdict rows (58)

Rows where the section-8 rule says the census is wrong (a detector fault, a verified rewrite, or an in-fragment refusal naming a real construct).

| file | method | census gaps | lifter verdict |
|---|---|---|---|
| Dafny-Exercises_tmp_tmpjm75muf__Session2Exercises_ExerciseFibonacci.dfy | fibonacci1 | multi-method | lifted |
| Dafny-Exercises_tmp_tmpjm75muf__Session2Exercises_ExerciseFibonacci.dfy | fibonacci2 | multi-method | lifted |
| Dafny-Exercises_tmp_tmpjm75muf__Session2Exercises_ExerciseFibonacci.dfy | fibonacci3 | multi-method | lifted |
| Dafny-Exercises_tmp_tmpjm75muf__Session2Exercises_ExerciseSquare_root.dfy | mroot1 | div-mod, multi-method | lifted |
| Dafny-Exercises_tmp_tmpjm75muf__Session2Exercises_ExerciseSquare_root.dfy | mroot2 | div-mod, multi-method | lifted |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week1_7_week5_ComputePower.dfy | CalcPower | multi-method | lifted |
| Dafny_Programs_tmp_tmp99966ew4_mymax.dfy | Max | multi-method, zero-returns | lifted |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Function.dfy | TripleConditions | div-mod, multi-method, zero-returns | lifted |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Ghost.dfy | M | div-mod, multi-method, multi-return, zero-returns | lifted |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Ghost.dfy | MyMethod | div-mod, multi-method, multi-return, zero-returns | lifted |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Index.dfy | Min | div-mod, multi-method, multi-return, zero-returns | lifted |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_LoopInvariant.dfy | UpWhileLess | multi-method, zero-returns | lifted |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_LoopInvariant.dfy | UpWhileNotEqual | multi-method, zero-returns | lifted |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_LoopInvariant.dfy | DownWhileNotEqual | multi-method, zero-returns | lifted |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_LoopInvariant.dfy | DownWhileGreater | multi-method, zero-returns | lifted |
| Dafny_tmp_tmp0wu8wmfr_tests_F1a.dfy | F | div-mod, multi-method | lifted |
| Dafny_tmp_tmpmvs2dmry_examples1.dfy | Abs | multi-method, multi-return, zero-returns | lifted |
| Dafny_tmp_tmpmvs2dmry_examples1.dfy | Max | multi-method, multi-return, zero-returns | lifted |
| Dafny_tmp_tmpmvs2dmry_examples2.dfy | add_by_inc | div-mod, early-exit, multi-method, real | lifted |
| Dafny_tmp_tmpmvs2dmry_examples2.dfy | Product | div-mod, early-exit, multi-method, real | lifted |
| Dafny_tmp_tmpmvs2dmry_examples2.dfy | gcdCalc | div-mod, early-exit, multi-method, real | lifted |
| Final-Project-Dafny_tmp_tmpmcywuqox_Final_Project_3.dfy | nonZeroReturn | multi-method, zero-returns | lifted |
| Formal-methods-of-software-development_tmp_tmppryvbyty_Bloque 1_Lab3.dfy | ComputeFact | bodyless-method, multi-method, multi-return | lifted |
| Formal-methods-of-software-development_tmp_tmppryvbyty_Bloque 1_Lab3.dfy | ComputeFact2 | bodyless-method, multi-method, multi-return | lifted |
| Formal-methods-of-software-development_tmp_tmppryvbyty_Bloque 1_Lab3.dfy | Sqare | bodyless-method, multi-method, multi-return | lifted |
| Formal-methods-of-software-development_tmp_tmppryvbyty_Bloque 1_Lab3.dfy | Sqare2 | bodyless-method, multi-method, multi-return | lifted |
| Metodos_Formais_tmp_tmpbez22nnn_Aula_4_ex3.dfy | ComputeFib | multi-method, zero-returns | lifted |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_examples_simpleMultiplication.dfy | Foo | set, string-char | lifted |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_basic examples_add_by_one.dfy | add_by_one | multi-method, nondet | lifted |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_basic examples_add_by_one_details.dfy | plus_one | multi-method, nondet | lifted |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_basic examples_sumto_sol.dfy | SumUpTo | multi-method, seq-slice | lifted |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_04_Hoangkim_ex_04_Hoangkim.dfy | sumOdds | bodyless-method, div-mod, multi-method, multi-return | lifted |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_05_Hoangkim_ex_05_Hoangkim.dfy | fibIter | multi-method | lifted |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_05_Hoangkim_ex_05_Hoangkim.dfy | factIter | multi-method | lifted |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_05_Hoangkim_ex_05_Hoangkim.dfy | gcdI | multi-method | lifted |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_10_Hoangkim_ex10_hoangkim.dfy | square0 | bodyless-method, multi-method, nondet, zero-returns | lifted |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_10_Hoangkim_ex10_hoangkim.dfy | square1 | bodyless-method, multi-method, nondet, zero-returns | lifted |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_example_DafnyIntro_01_Simple_Loops.dfy | sumOdds | div-mod, multi-method | lifted |
| Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula2.dfy | max | multi-method | lifted |
| Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula2.dfy | mystery1 | multi-method | lifted |
| Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula2.dfy | m3 | multi-method | lifted |
| Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula2.dfy | m4 | multi-method | lifted |
| cs357_tmp_tmpn4fsvwzs_lab7_question5.dfy | A1 | multi-method | lifted |
| dafny-language-server_tmp_tmpkir0kenl_Test_VSI-Benchmarks_b1.dfy | Add | io, multi-method, string-char, zero-returns | lifted |
| dafny-learn_tmp_tmpn94ir40q_R01_assertions.dfy | Abs | multi-method, zero-returns | lifted |
| dafny-learn_tmp_tmpn94ir40q_R01_assertions.dfy | Max | multi-method, zero-returns | lifted |
| dafny-learn_tmp_tmpn94ir40q_R01_functions.dfy | Abs | multi-method, zero-returns | lifted |
| dafny-learn_tmp_tmpn94ir40q_R01_functions.dfy | TestDouble | multi-method, zero-returns | lifted |
| dafny-programs_tmp_tmpcwodh6qh_src_max.dfy | Max | multi-method, zero-returns | lifted |
| dafny-training_tmp_tmp_n2kixni_session1_training1.dfy | abs | decreases-star, early-exit, multi-method, nested-seq, seq-return, string-char, zero-returns | lifted |
| dafny-training_tmp_tmp_n2kixni_session1_training1.dfy | max | decreases-star, early-exit, multi-method, nested-seq, seq-return, string-char, zero-returns | lifted |
| dafny-workout_tmp_tmp0abkw6f8_starter_ex03.dfy | Abs | multi-method, real | lifted |
| formal-methods-in-software-engineering_tmp_tmpe7fjnek6_Labs4_gr2.dfy | HoareTripleReqEns | decreases-star, multi-method, multi-return, nondet, such-that-exec, zero-returns | lifted |
| formal-methods-in-software-engineering_tmp_tmpe7fjnek6_Labs4_gr2.dfy | SqrSum1 | decreases-star, multi-method, multi-return, nondet, such-that-exec, zero-returns | lifted |
| nitwit_tmp_tmplm098gxz_nit.dfy | max_nit | div-mod, multi-method, multi-return, seq-literal, seq-return | lifted |
| stunning-palm-tree_tmp_tmpr84c2iwh_ch1.dfy | Triple | bodyless-method, div-mod, multi-method, multi-return, zero-returns | lifted |
| stunning-palm-tree_tmp_tmpr84c2iwh_ch1.dfy | MinUnderSpec | bodyless-method, div-mod, multi-method, multi-return, zero-returns | lifted |
| stunning-palm-tree_tmp_tmpr84c2iwh_ch1.dfy | Min | bodyless-method, div-mod, multi-method, multi-return, zero-returns | lifted |

## Undecided rows (26)

Rows section 8 leaves for a human: a policy reason or gap, a lift-check failure (a bug report against the lifter), an incomplete pipeline stage, or an unchecked lift.

| file | method | reason |
|---|---|---|
| Clover_min_array.dfy | minArray | policy-gap:array |
| Dafny-Exercises_tmp_tmpjm75muf__Session3Exercises_ExerciseMaximum.dfy | mmaximum1 | policy-gap:array |
| Dafny-Exercises_tmp_tmpjm75muf__Session3Exercises_ExerciseMaximum.dfy | mfirstMaximum | policy-gap:array |
| Dafny-Exercises_tmp_tmpjm75muf__Session4Exercises_ExercisefirstZero.dfy | mfirstCero | policy-gap:array |
| Dafny-experiences_tmp_tmp150sm9qy_dafny_started_tutorial_dafny_tutorial_array.dfy | FindMax | policy-gap:array |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week1_7_A2_Q1_trimmed copy - 副本.dfy | Mult | policy-gap:array |
| Dafny_Verify_tmp_tmphq7j0row_AI_agent_validation_examples.dfy | ComputePower | policy-gap:array |
| Dafny_Verify_tmp_tmphq7j0row_AI_agent_validation_examples.dfy | Cube | policy-gap:array |
| Dafny_Verify_tmp_tmphq7j0row_Generated_Code_Minimum.dfy | Minimum | policy-gap:array |
| Dafny_Verify_tmp_tmphq7j0row_dataset_bql_exampls_Min.dfy | min | policy-gap:array |
| Dafny_Verify_tmp_tmphq7j0row_dataset_bql_exampls_SmallNum.dfy | add_small_numbers | policy-gap:array |
| Dafny_tmp_tmpj88zq5zt_2-Kontrakte_max.dfy | max | policy-gap:array |
| Dafny_tmp_tmpv_d3qi10_2_min.dfy | minMethod | policy-gap:array |
| Final-Project-Dafny_tmp_tmpmcywuqox_Attempts_Insertion_Sort_Normal.dfy | lookForMin | policy-gap:array |
| MFES_2021_tmp_tmpuljn8zd9_FCUL_Exercises_10_find.dfy | find | policy-gap:array |
| Prog-Fun-Solutions_tmp_tmp7_gmnz5f_mockExam2_p6.dfy | problem6 | lift-check-failed |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny2_Classics.dfy | AdditiveFactorial | policy-gap:array |
| bbfny_tmp_tmpw4m0jvl0_enjoying.dfy | Max | policy-gap:array |
| bbfny_tmp_tmpw4m0jvl0_enjoying.dfy | Abs | policy-gap:array |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1-assignment-2.dfy | PlusOne | policy-gap:array |
| dafny-exercise_tmp_tmpouftptir_maxArray.dfy | MaxArray | policy-gap:array |
| dafny-synthesis_task_id_101.dfy | KthElement | policy-gap:array |
| dafny-workout_tmp_tmp0abkw6f8_starter_ex12.dfy | FindMax | policy-gap:array |
| dafny_projects_tmp_tmpjutqwjv4_tutorial_tutorial.dfy | ComputeFib | policy-gap:array |
| laboratory_tmp_tmps8ws6mu2_dafny-tutorial_exercise12.dfy | FindMax | policy-gap:array |
| software_analysis_tmp_tmpmt6bo9sf_ss.dfy | find_min_index | policy-gap:array |

## Refusal reason tally by census in_fragment

| reason | in_fragment | out_of_fragment |
|---|---|---|
| array | 0 | 61 |
| array-mutation | 0 | 4 |
| as-cast | 0 | 7 |
| bodyless-function | 0 | 10 |
| bodyless-method | 0 | 13 |
| calls-other-method | 0 | 5 |
| datatype | 0 | 38 |
| div-mod | 0 | 62 |
| early-exit | 0 | 15 |
| function-contract | 0 | 41 |
| function-method | 0 | 1 |
| generics | 0 | 1 |
| ghost-local | 0 | 2 |
| heap | 0 | 50 |
| higher-order | 0 | 8 |
| let-expression | 0 | 27 |
| lift-check-failed | 1 | 3 |
| map | 0 | 1 |
| multi-return | 0 | 57 |
| nested-seq | 0 | 20 |
| no-method | 0 | 132 |
| nondet | 0 | 2 |
| old | 0 | 1 |
| parse-failure | 0 | 1 |
| real | 0 | 16 |
| resolve-failure | 0 | 2 |
| return-not-assigned-on-all-paths | 0 | 5 |
| seq-literal | 0 | 12 |
| seq-return | 0 | 23 |
| seq-slice | 0 | 31 |
| set | 0 | 5 |
| string-char | 0 | 22 |
| such-that-exec | 0 | 1 |
| tuple | 0 | 3 |
| type-decl | 0 | 5 |
| unbounded-quantifier | 0 | 52 |
| zero-returns | 0 | 69 |

| file | method | in_fragment | verdict | disagreement |
|---|---|---|---|---|
| 630-dafny_tmp_tmpz2kokaiq_Solution.dfy | BinarySearch | False | refused:function-contract | gap-name |
| 703FinalProject_tmp_tmpr_10rn4z_DP-GD.dfy | (file) | False | refused:no-method | gap-name |
| 703FinalProject_tmp_tmpr_10rn4z_gaussian.dfy | (file) | False | refused:no-method | gap-name |
| AssertivePrograming_tmp_tmpwf43uz0e_DivMode_Unary.dfy | (file) | False | refused:datatype | agree |
| AssertivePrograming_tmp_tmpwf43uz0e_Find_Substring.dfy | FindFirstOccurrence | False | refused:seq-slice | agree |
| AssertivePrograming_tmp_tmpwf43uz0e_MergeSort.dfy | MergeSort | False | refused:unbounded-quantifier | gap-name |
| AssertivePrograming_tmp_tmpwf43uz0e_MergeSort.dfy | Merge | False | refused:unbounded-quantifier | gap-name |
| AssertivePrograming_tmp_tmpwf43uz0e_MergeSort.dfy | MergeLoop | False | refused:unbounded-quantifier | gap-name |
| BPTree-verif_tmp_tmpq1z6xm1d_Utils.dfy | GetInsertIndex | False | refused:unbounded-quantifier | gap-name |
| BPTree-verif_tmp_tmpq1z6xm1d_Utils.dfy | InsertIntoSorted | False | refused:unbounded-quantifier | gap-name |
| BelowZero.dfy | BelowZero | False | refused:seq-slice | agree |
| BinaryAddition.dfy | (file) | False | refused:let-expression | gap-name |
| BinarySearchTree_tmp_tmp_bn2twp5_bst4copy.dfy | (file) | False | refused:datatype | agree |
| CO3408-Advanced-Software-Modelling-Assignment-2022-23-Part-2-A-Specification-Spectacular_tmp_tmp4pj4p2zx_car_park.dfy | (file) | False | refused:heap | agree |
| CS494-final-project_tmp_tmp7nof55uq_bubblesort.dfy | BubbleSort | False | refused:heap | gap-name |
| CS5232_Project_tmp_tmpai_cfrng_LFUSimple.dfy | (file) | False | refused:heap | agree |
| CS5232_Project_tmp_tmpai_cfrng_test.dfy | (file) | False | refused:no-method | gap-name |
| CSC8204-Dafny_tmp_tmp11yhjb53_stack.dfy | (file) | False | refused:no-method | gap-name |
| CSU55004---Formal-Verification_tmp_tmp4ki9iaqy_Project_Project_Part_1_project_pt_1.dfy | (file) | False | refused:no-method | gap-name |
| CVS-Projto1_tmp_tmpb1o0bu8z_Hoare.dfy | (file) | False | refused:datatype | agree |
| CVS-Projto1_tmp_tmpb1o0bu8z_fact.dfy | (file) | False | refused:datatype | agree |
| CVS-Projto1_tmp_tmpb1o0bu8z_proj1_proj1.dfy | (file) | False | refused:datatype | agree |
| CVS-Projto1_tmp_tmpb1o0bu8z_searchSort.dfy | (file) | False | refused:no-method | gap-name |
| CVS-handout1_tmp_tmptm52no3k_1.dfy | query | False | refused:function-contract | gap-name |
| CVS-handout1_tmp_tmptm52no3k_1.dfy | queryFast | False | refused:function-contract | gap-name |
| CVS-handout1_tmp_tmptm52no3k_2.dfy | (file) | False | refused:datatype | agree |
| Clover_abs.dfy | Abs | True | lifted | agree |
| Clover_all_digits.dfy | allDigits | False | refused:string-char | agree |
| Clover_array_append.dfy | append | False | refused:array | agree |
| Clover_array_concat.dfy | (file) | False | refused:let-expression | gap-name |
| Clover_array_copy.dfy | iter_copy | False | refused:array | agree |
| Clover_array_product.dfy | arrayProduct | False | refused:array | agree |
| Clover_array_sum.dfy | arraySum | False | refused:array | agree |
| Clover_avg.dfy | ComputeAvg | False | refused:div-mod | agree |
| Clover_below_zero.dfy | below_zero | False | refused:multi-return | agree |
| Clover_binary_search.dfy | BinarySearch | False | refused:unbounded-quantifier | gap-name |
| Clover_bubble_sort.dfy | BubbleSort | False | refused:zero-returns | agree |
| Clover_cal_ans.dfy | CalDiv | False | refused:multi-return | agree |
| Clover_cal_sum.dfy | Sum | False | refused:div-mod | agree |
| Clover_canyon_search.dfy | (file) | False | refused:let-expression | gap-name |
| Clover_compare.dfy | Compare | False | refused:datatype | gap-name |
| Clover_convert_map_key.dfy | convert_map_key | False | refused:map | agree |
| Clover_copy_part.dfy | copy | False | refused:array | agree |
| Clover_count_lessthan.dfy | (file) | False | refused:let-expression | gap-name |
| Clover_double_array_elements.dfy | double_array_elements | False | refused:zero-returns | agree |
| Clover_double_quadruple.dfy | DoubleQuadruple | False | refused:multi-return | agree |
| Clover_even_list.dfy | FindEvenNumbers | False | refused:array | agree |
| Clover_find.dfy | Find | False | refused:early-exit | agree |
| Clover_has_close_elements.dfy | (file) | False | refused:let-expression | gap-name |
| Clover_insert.dfy | insert | False | refused:zero-returns | agree |
| Clover_integer_square_root.dfy | SquareRoot | True | lifted | agree |
| Clover_is_even.dfy | ComputeIsEven | False | refused:div-mod | agree |
| Clover_is_palindrome.dfy | IsPalindrome | False | refused:nested-seq | agree |
| Clover_linear_search1.dfy | LinearSearch | False | refused:early-exit | agree |
| Clover_linear_search2.dfy | LinearSearch | False | refused:early-exit | agree |
| Clover_linear_search3.dfy | LinearSearch3 | False | refused:array | agree |
| Clover_longest_prefix.dfy | (file) | False | refused:let-expression | gap-name |
| Clover_match.dfy | Match | False | refused:string-char | agree |
| Clover_max_array.dfy | (file) | False | refused:let-expression | gap-name |
| Clover_min_array.dfy | minArray | False | lifted | undecided |
| Clover_min_of_two.dfy | Min | True | lifted | agree |
| Clover_modify_2d_array.dfy | modify_array_element | False | refused:zero-returns | agree |
| Clover_multi_return.dfy | MultipleReturns | False | refused:multi-return | agree |
| Clover_online_max.dfy | onlineMax | False | refused:multi-return | agree |
| Clover_only_once.dfy | only_once | False | refused:array | agree |
| Clover_quotient.dfy | Quotient | False | refused:multi-return | agree |
| Clover_remove_front.dfy | remove_front | False | refused:array | agree |
| Clover_replace.dfy | replace | False | refused:zero-returns | agree |
| Clover_return_seven.dfy | M | True | lifted | agree |
| Clover_reverse.dfy | reverse | False | refused:zero-returns | agree |
| Clover_rotate.dfy | rotate | False | refused:array | agree |
| Clover_selectionsort.dfy | SelectionSort | False | refused:zero-returns | agree |
| Clover_seq_to_array.dfy | ToArray | False | refused:nested-seq | agree |
| Clover_set_to_seq.dfy | SetToSeq | False | refused:set | agree |
| Clover_slope_search.dfy | SlopeSearch | False | refused:multi-return | agree |
| Clover_swap.dfy | Swap | False | refused:multi-return | agree |
| Clover_swap_arith.dfy | SwapArithmetic | False | refused:multi-return | agree |
| Clover_swap_bitvector.dfy | SwapBitvectors | False | refused:multi-return | agree |
| Clover_swap_in_array.dfy | swap | False | refused:zero-returns | agree |
| Clover_swap_sim.dfy | SwapSimultaneous | False | refused:multi-return | agree |
| Clover_test_array.dfy | TestArrayElements | False | refused:zero-returns | agree |
| Clover_triple.dfy | Triple | True | lifted | agree |
| Clover_triple2.dfy | Triple | False | refused:return-not-assigned-on-all-paths | gap-name |
| Clover_triple3.dfy | Triple | True | lifted | agree |
| Clover_triple4.dfy | Triple | True | lifted | agree |
| Clover_two_sum.dfy | twoSum | False | refused:multi-return | agree |
| Clover_update_array.dfy | UpdateElements | False | refused:zero-returns | agree |
| Clover_update_map.dfy | (file) | False | refused:let-expression | gap-name |
| Correctness_tmp_tmpwqvg5q_4_HoareLogic_exam.dfy | GCD1 | False | refused:bodyless-function | agree |
| Correctness_tmp_tmpwqvg5q_4_HoareLogic_exam.dfy | GCD2 | False | refused:bodyless-function | agree |
| Correctness_tmp_tmpwqvg5q_4_MethodCalls_q1.dfy | ComputeFusc | False | refused:bodyless-function | agree |
| Correctness_tmp_tmpwqvg5q_4_Sorting_Tangent.dfy | Tangent | False | refused:array | agree |
| Correctness_tmp_tmpwqvg5q_4_Sorting_Tangent.dfy | BinarySearch | False | refused:unbounded-quantifier | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session10Exercises_ExerciseBarrier.dfy | barrier | False | refused:unbounded-quantifier | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session2Exercises_ExerciseExp.dfy | (file) | False | refused:no-method | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session2Exercises_ExerciseFibonacci.dfy | fibonacci1 | False | lifted | lifter |
| Dafny-Exercises_tmp_tmpjm75muf__Session2Exercises_ExerciseFibonacci.dfy | fibonacci2 | False | lifted | lifter |
| Dafny-Exercises_tmp_tmpjm75muf__Session2Exercises_ExerciseFibonacci.dfy | fibonacci3 | False | lifted | lifter |
| Dafny-Exercises_tmp_tmpjm75muf__Session2Exercises_ExercisePositive.dfy | mpositive | False | refused:seq-slice | agree |
| Dafny-Exercises_tmp_tmpjm75muf__Session2Exercises_ExercisePositive.dfy | mpositive3 | False | refused:seq-slice | agree |
| Dafny-Exercises_tmp_tmpjm75muf__Session2Exercises_ExercisePositive.dfy | mpositive4 | False | refused:seq-slice | agree |
| Dafny-Exercises_tmp_tmpjm75muf__Session2Exercises_ExercisePositive.dfy | mpositivertl | False | refused:seq-slice | agree |
| Dafny-Exercises_tmp_tmpjm75muf__Session2Exercises_ExerciseSquare_root.dfy | mroot1 | False | lifted | lifter |
| Dafny-Exercises_tmp_tmpjm75muf__Session2Exercises_ExerciseSquare_root.dfy | mroot2 | False | lifted | lifter |
| Dafny-Exercises_tmp_tmpjm75muf__Session2Exercises_ExerciseSquare_root.dfy | mroot3 | False | refused:div-mod | agree |
| Dafny-Exercises_tmp_tmpjm75muf__Session3Exercises_ExerciseMaximum.dfy | mmaximum1 | False | lifted | undecided |
| Dafny-Exercises_tmp_tmpjm75muf__Session3Exercises_ExerciseMaximum.dfy | mmaximum2 | False | refused:unbounded-quantifier | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session3Exercises_ExerciseMaximum.dfy | mfirstMaximum | False | lifted | undecided |
| Dafny-Exercises_tmp_tmpjm75muf__Session3Exercises_ExerciseMaximum.dfy | mlastMaximum | False | refused:unbounded-quantifier | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session3Exercises_ExerciseMaximum.dfy | mmaxvalue1 | False | refused:array | agree |
| Dafny-Exercises_tmp_tmpjm75muf__Session3Exercises_ExerciseMaximum.dfy | mmaxvalue2 | False | refused:array | agree |
| Dafny-Exercises_tmp_tmpjm75muf__Session4Exercises_ExerciseAllEqual.dfy | mallEqual1 | False | refused:unbounded-quantifier | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session4Exercises_ExerciseAllEqual.dfy | mallEqual2 | False | refused:unbounded-quantifier | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session4Exercises_ExerciseAllEqual.dfy | mallEqual3 | False | refused:unbounded-quantifier | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session4Exercises_ExerciseAllEqual.dfy | mallEqual4 | False | refused:unbounded-quantifier | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session4Exercises_ExerciseAllEqual.dfy | mallEqual5 | False | refused:unbounded-quantifier | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session4Exercises_ExerciseContained.dfy | mcontained | False | refused:unbounded-quantifier | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session4Exercises_ExerciseFirstNegative.dfy | mfirstNegative | False | refused:multi-return | agree |
| Dafny-Exercises_tmp_tmpjm75muf__Session4Exercises_ExerciseFirstNegative.dfy | mfirstNegative2 | False | refused:multi-return | agree |
| Dafny-Exercises_tmp_tmpjm75muf__Session4Exercises_ExercisefirstZero.dfy | mfirstCero | False | lifted | undecided |
| Dafny-Exercises_tmp_tmpjm75muf__Session5Exercises_ExerciseSumElems.dfy | sumElems | False | refused:seq-literal | agree |
| Dafny-Exercises_tmp_tmpjm75muf__Session5Exercises_ExerciseSumElems.dfy | sumElemsB | False | refused:seq-literal | agree |
| Dafny-Exercises_tmp_tmpjm75muf__Session6Exercises_ExerciseCountEven.dfy | mcountEven | False | refused:seq-literal | agree |
| Dafny-Exercises_tmp_tmpjm75muf__Session6Exercises_ExerciseCountMin.dfy | mCountMin | False | refused:function-contract | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session6Exercises_ExercisePeekSum.dfy | mPeekSum | False | refused:function-contract | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session7Exercises_ExerciseBinarySearch.dfy | (file) | False | refused:let-expression | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session7Exercises_ExerciseBubbleSort.dfy | bubbleSorta | False | refused:function-contract | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session7Exercises_ExerciseBubbleSort.dfy | bubbleSort | False | refused:function-contract | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session7Exercises_ExerciseReplace.dfy | replace | False | refused:zero-returns | agree |
| Dafny-Exercises_tmp_tmpjm75muf__Session7Exercises_ExerciseSelSort.dfy | selSort | False | refused:function-contract | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session7Exercises_ExerciseSeparate.dfy | separate | False | refused:function-contract | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session8Exercises_ExerciseInsertionSort.dfy | InsertionSort | False | refused:function-contract | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session9Exercises_ExerciseSeqMaxSum.dfy | segMaxSum | False | refused:function-contract | gap-name |
| Dafny-Exercises_tmp_tmpjm75muf__Session9Exercises_ExerciseSeqMaxSum.dfy | segSumaMaxima2 | False | refused:function-contract | gap-name |
| Dafny-Grind75_tmp_tmpsxfz3i4r_problems_twoSum.dfy | twoSum | False | refused:tuple | agree |
| Dafny-Practice_tmp_tmphnmt4ovh_BST.dfy | (file) | False | refused:datatype | agree |
| Dafny-Practice_tmp_tmphnmt4ovh_Pattern Matching.dfy | FindAllOccurrences | False | refused:string-char | agree |
| Dafny-Projects_tmp_tmph399drhy_p2_arraySplit.dfy | ArraySplit | False | refused:multi-return | agree |
| Dafny-VMC_tmp_tmpzgqv0i1u_src_Math_Exponential.dfy | (file) | False | refused:no-method | gap-name |
| Dafny-VMC_tmp_tmpzgqv0i1u_src_Math_Helper.dfy | (file) | False | refused:no-method | gap-name |
| Dafny-demo_tmp_tmpkgr_dvdi_Dafny_BinarySearch.dfy | BinarySearch | False | refused:heap | gap-name |
| Dafny-experiences_tmp_tmp150sm9qy_dafny_started_tutorial_dafny_tutorial_array.dfy | FindMax | False | lifted | undecided |
| Dafny-programs_tmp_tmpnso9eu7u_Algorithms + sorting_bubble-sort.dfy | BubbleSort | False | refused:function-contract | gap-name |
| DafnyExercises_tmp_tmpd6qyevja_Part1_Q1.dfy | addArrays | False | refused:array | agree |
| DafnyExercises_tmp_tmpd6qyevja_QuickExercises_testing2.dfy | (file) | False | refused:no-method | gap-name |
| DafnyPrograms_tmp_tmp74_f9k_c_automaton.dfy | (file) | False | refused:no-method | gap-name |
| DafnyPrograms_tmp_tmp74_f9k_c_invertarray.dfy | InvertArray | False | refused:zero-returns | agree |
| DafnyPrograms_tmp_tmp74_f9k_c_map-multiset-implementation.dfy | (file) | False | refused:no-method | gap-name |
| DafnyPrograms_tmp_tmp74_f9k_c_prime-database.dfy | (file) | False | refused:heap | agree |
| DafnyProjects_tmp_tmp2acw_s4s_CombNK.dfy | (file) | False | refused:function-method | agree |
| DafnyProjects_tmp_tmp2acw_s4s_Graph.dfy | (file) | False | refused:heap | agree |
| DafnyProjects_tmp_tmp2acw_s4s_Power.dfy | powerDC | False | refused:real | agree |
| DafnyProjects_tmp_tmp2acw_s4s_RawSort.dfy | (file) | False | refused:such-that-exec | agree |
| DafnyProjects_tmp_tmp2acw_s4s_findMax.dfy | findMax | False | refused:array | agree |
| DafnyProjects_tmp_tmp2acw_s4s_longestPrefix.dfy | longestPrefix | False | refused:seq-slice | agree |
| DafnyProjects_tmp_tmp2acw_s4s_partitionOddEven.dfy | partitionOddEven | False | refused:zero-returns | agree |
| DafnyProjects_tmp_tmp2acw_s4s_sqrt.dfy | sqrt | False | refused:bodyless-method | agree |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week1_7_A2_Q1_trimmed copy - 副本.dfy | FooCount | False | refused:div-mod | agree |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week1_7_A2_Q1_trimmed copy - 副本.dfy | ComputeCount | False | refused:div-mod | agree |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week1_7_A2_Q1_trimmed copy - 副本.dfy | PreCompute | False | refused:div-mod | agree |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week1_7_A2_Q1_trimmed copy - 副本.dfy | Mult | False | lifted | undecided |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week1_7_MaxSum.dfy | MaxSum | False | refused:multi-return | agree |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week1_7_Week4__LinearSearch.dfy | LinearSeach0 | False | refused:array | agree |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week1_7_Week4__LinearSearch.dfy | LinearSeach1 | False | refused:div-mod | agree |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week1_7_week4_tute_ex4.dfy | LinearSearch | False | refused:array | agree |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week1_7_week4_tute_ex4.dfy | LinearSearch1 | False | refused:array | agree |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week1_7_week4_tute_ex4.dfy | LinearSearch2 | False | refused:array | agree |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week1_7_week4_tute_ex4.dfy | LinearSearch3 | False | refused:array | agree |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week1_7_week5_ComputePower.dfy | CalcPower | False | lifted | lifter |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week1_7_week5_ComputePower.dfy | ComputePower | False | refused:calls-other-method | gap-name |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week8_12_a3 copy 2.dfy | (file) | False | refused:no-method | gap-name |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week8_12_a3_search_findPositionOfIndex.dfy | FindPositionOfElement | False | refused:multi-return | agree |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week8_12_week10_BoundedQueue_01.dfy | (file) | False | refused:no-method | gap-name |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week8_12_week10_ExtensibleArray.dfy | (file) | False | refused:no-method | gap-name |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week8_12_week8_CheckSumCalculator.dfy | (file) | False | refused:no-method | gap-name |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week8_12_week8_CoffeeMaker2.dfy | (file) | False | refused:heap | agree |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week8_12_week9_lemma.dfy | AssignmentsToMark | False | refused:div-mod | agree |
| Dafny_Learning_Experience_tmp_tmpuxvcet_u_week8_12_week9_lemma.dfy | AssignmentsToMarkOne | False | refused:div-mod | agree |
| Dafny_ProgrammingLanguages_tmp_tmp82_e0kji_ExtraCredit.dfy | (file) | False | refused:datatype | agree |
| Dafny_Programs_tmp_tmp99966ew4_binary_search.dfy | BinarySearch | False | refused:heap | gap-name |
| Dafny_Programs_tmp_tmp99966ew4_lemma.dfy | FindZero | False | refused:array | agree |
| Dafny_Programs_tmp_tmp99966ew4_mymax.dfy | Max | False | lifted | lifter |
| Dafny_Programs_tmp_tmp99966ew4_trig.dfy | test | False | refused:bodyless-function | agree |
| Dafny_Verify_tmp_tmphq7j0row_AI_agent_validation_examples.dfy | ComputePower | False | lifted | undecided |
| Dafny_Verify_tmp_tmphq7j0row_AI_agent_validation_examples.dfy | Max | False | refused:lift-check-failed | gap-name |
| Dafny_Verify_tmp_tmphq7j0row_AI_agent_validation_examples.dfy | Cube | False | lifted | undecided |
| Dafny_Verify_tmp_tmphq7j0row_AI_agent_validation_examples.dfy | IncrementMatrix | False | refused:zero-returns | agree |
| Dafny_Verify_tmp_tmphq7j0row_AI_agent_validation_examples.dfy | CopyMatrix | False | refused:zero-returns | agree |
| Dafny_Verify_tmp_tmphq7j0row_AI_agent_validation_examples.dfy | DoubleArray | False | refused:zero-returns | agree |
| Dafny_Verify_tmp_tmphq7j0row_AI_agent_validation_examples.dfy | RotateLeft | False | refused:zero-returns | agree |
| Dafny_Verify_tmp_tmphq7j0row_AI_agent_validation_examples.dfy | RotateRight | False | refused:zero-returns | agree |
| Dafny_Verify_tmp_tmphq7j0row_AI_agent_verify_examples_ComputePower.dfy | ComputePower | True | lifted | agree |
| Dafny_Verify_tmp_tmphq7j0row_AI_agent_verify_examples_CopyMatrix.dfy | CopyMatrix | False | refused:zero-returns | agree |
| Dafny_Verify_tmp_tmphq7j0row_AI_agent_verify_examples_Cube.dfy | Cube | True | lifted | agree |
| Dafny_Verify_tmp_tmphq7j0row_AI_agent_verify_examples_DoubleArray.dfy | DoubleArray | False | refused:zero-returns | agree |
| Dafny_Verify_tmp_tmphq7j0row_AI_agent_verify_examples_IncrementMatrix.dfy | IncrementMatrix | False | refused:zero-returns | agree |
| Dafny_Verify_tmp_tmphq7j0row_AI_agent_verify_examples_RotateRight.dfy | RotateRight | False | refused:zero-returns | agree |
| Dafny_Verify_tmp_tmphq7j0row_Fine_Tune_Examples_50_examples_28.dfy | main | False | refused:multi-return | agree |
| Dafny_Verify_tmp_tmphq7j0row_Fine_Tune_Examples_50_examples_37.dfy | main | False | refused:multi-return | agree |
| Dafny_Verify_tmp_tmphq7j0row_Fine_Tune_Examples_50_examples_38.dfy | main | False | refused:multi-return | agree |
| Dafny_Verify_tmp_tmphq7j0row_Fine_Tune_Examples_50_examples_41.dfy | main | False | refused:multi-return | agree |
| Dafny_Verify_tmp_tmphq7j0row_Fine_Tune_Examples_50_examples_BinarySearch.dfy | BinarySearch | False | refused:unbounded-quantifier | gap-name |
| Dafny_Verify_tmp_tmphq7j0row_Fine_Tune_Examples_50_examples_SumArray.dfy | SumArray | False | refused:function-contract | gap-name |
| Dafny_Verify_tmp_tmphq7j0row_Fine_Tune_Examples_error_data_completion_06_n.dfy | (file) | False | refused:no-method | gap-name |
| Dafny_Verify_tmp_tmphq7j0row_Fine_Tune_Examples_error_data_completion_07.dfy | main | False | refused:multi-return | agree |
| Dafny_Verify_tmp_tmphq7j0row_Fine_Tune_Examples_error_data_completion_11.dfy | main | False | refused:multi-return | agree |
| Dafny_Verify_tmp_tmphq7j0row_Fine_Tune_Examples_normal_data_completion_MaxPerdV2.dfy | max | False | refused:function-contract | gap-name |
| Dafny_Verify_tmp_tmphq7j0row_Generated_Code_15.dfy | main | True | lifted | agree |
| Dafny_Verify_tmp_tmphq7j0row_Generated_Code_ComputePower.dfy | ComputePower | True | lifted | agree |
| Dafny_Verify_tmp_tmphq7j0row_Generated_Code_Count.dfy | count | False | refused:function-contract | gap-name |
| Dafny_Verify_tmp_tmphq7j0row_Generated_Code_LinearSearch.dfy | LinearSearch | False | refused:array | agree |
| Dafny_Verify_tmp_tmphq7j0row_Generated_Code_Minimum.dfy | Minimum | False | lifted | undecided |
| Dafny_Verify_tmp_tmphq7j0row_Generated_Code_Mult.dfy | mult | True | lifted | agree |
| Dafny_Verify_tmp_tmphq7j0row_Generated_Code_rand.dfy | (file) | False | refused:no-method | gap-name |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Function.dfy | TripleConditions | False | lifted | lifter |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Function.dfy | Triple' | False | refused:div-mod | agree |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Ghost.dfy | Triple | False | refused:div-mod | agree |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Ghost.dfy | Triple1 | False | refused:ghost-local | gap-name |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Ghost.dfy | DoubleQuadruple | False | refused:multi-return | agree |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Ghost.dfy | M | False | lifted | lifter |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Ghost.dfy | MyMethod | False | lifted | lifter |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Index.dfy | Index | False | refused:div-mod | agree |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Index.dfy | Min | False | lifted | lifter |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Index.dfy | MaxSum | False | refused:multi-return | agree |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Index.dfy | ReconstructFromMaxSum | False | refused:multi-return | agree |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_LoopInvariant.dfy | UpWhileLess | False | lifted | lifter |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_LoopInvariant.dfy | UpWhileNotEqual | False | lifted | lifter |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_LoopInvariant.dfy | DownWhileNotEqual | False | lifted | lifter |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_LoopInvariant.dfy | DownWhileGreater | False | lifted | lifter |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Triple.dfy | TripleConditions | False | refused:div-mod | agree |
| Dafny_Verify_tmp_tmphq7j0row_Test_Cases_solved_1_select.dfy | SelectionSort | False | refused:zero-returns | agree |
| Dafny_Verify_tmp_tmphq7j0row_dataset_C_convert_examples_01.dfy | main | False | refused:multi-return | agree |
| Dafny_Verify_tmp_tmphq7j0row_dataset_C_convert_examples_06_n.dfy | (file) | False | refused:no-method | gap-name |
| Dafny_Verify_tmp_tmphq7j0row_dataset_C_convert_examples_07.dfy | main | False | refused:multi-return | agree |
| Dafny_Verify_tmp_tmphq7j0row_dataset_C_convert_examples_11.dfy | main | False | refused:multi-return | agree |
| Dafny_Verify_tmp_tmphq7j0row_dataset_C_convert_examples_15.dfy | main | True | lifted | agree |
| Dafny_Verify_tmp_tmphq7j0row_dataset_C_convert_examples_23_x.dfy | (file) | False | refused:no-method | gap-name |
| Dafny_Verify_tmp_tmphq7j0row_dataset_bql_exampls_Min.dfy | min | False | lifted | undecided |
| Dafny_Verify_tmp_tmphq7j0row_dataset_bql_exampls_SmallNum.dfy | add_small_numbers | False | lifted | undecided |
| Dafny_Verify_tmp_tmphq7j0row_dataset_bql_exampls_Square.dfy | square | True | lifted | agree |
| Dafny_Verify_tmp_tmphq7j0row_dataset_detailed_examples_SelectionSort.dfy | SelectionSort | False | refused:zero-returns | agree |
| Dafny_Verify_tmp_tmphq7j0row_dataset_error_data_real_error_IsEven_success_1.dfy | is_even | True | lifted | agree |
| Dafny_tmp_tmp0wu8wmfr_Heimaverkefni 1_LinearSearch.dfy | SearchRecursive | False | refused:early-exit | agree |
| Dafny_tmp_tmp0wu8wmfr_Heimaverkefni 1_LinearSearch.dfy | SearchLoop | False | refused:early-exit | agree |
| Dafny_tmp_tmp0wu8wmfr_Heimaverkefni 2_BinarySearchDec.dfy | SearchRecursive | False | refused:nested-seq | agree |
| Dafny_tmp_tmp0wu8wmfr_Heimaverkefni 2_BinarySearchDec.dfy | SearchLoop | False | refused:nested-seq | agree |
| Dafny_tmp_tmp0wu8wmfr_Heimaverkefni 3_InsertionSortMultiset.dfy | Search | False | refused:unbounded-quantifier | gap-name |
| Dafny_tmp_tmp0wu8wmfr_Heimaverkefni 3_InsertionSortMultiset.dfy | Sort | False | refused:type-decl | gap-name |
| Dafny_tmp_tmp0wu8wmfr_Heimaverkefni 3_SelectionSortMultiset.dfy | MinOfMultiset | False | refused:type-decl | gap-name |
| Dafny_tmp_tmp0wu8wmfr_Heimaverkefni 3_SelectionSortMultiset.dfy | Sort | False | refused:type-decl | gap-name |
| Dafny_tmp_tmp0wu8wmfr_Heimaverkefni 8_H8.dfy | Partition | False | refused:multi-return | agree |
| Dafny_tmp_tmp0wu8wmfr_Heimaverkefni 8_H8.dfy | QuickSelect | False | refused:multi-return | agree |
| Dafny_tmp_tmp0wu8wmfr_tests_F1a.dfy | F | False | lifted | lifter |
| Dafny_tmp_tmp0wu8wmfr_tests_F1a.dfy | Mid | False | refused:div-mod | agree |
| Dafny_tmp_tmp0wu8wmfr_tests_InsertionSortSeq.dfy | InsertionSort | False | refused:unbounded-quantifier | gap-name |
| Dafny_tmp_tmp0wu8wmfr_tests_Search1000.dfy | Search1000 | False | refused:unbounded-quantifier | gap-name |
| Dafny_tmp_tmp0wu8wmfr_tests_Search1000.dfy | Search2PowLoop | False | refused:div-mod | agree |
| Dafny_tmp_tmp0wu8wmfr_tests_Search1000.dfy | Search2PowRecursive | False | refused:div-mod | agree |
| Dafny_tmp_tmp0wu8wmfr_tests_SumIntsLoop.dfy | SumIntsLoop | False | refused:div-mod | agree |
| Dafny_tmp_tmpj88zq5zt_2-Kontrakte_max.dfy | max | False | lifted | undecided |
| Dafny_tmp_tmpj88zq5zt_2-Kontrakte_reverse3.dfy | swap3 | False | refused:zero-returns | agree |
| Dafny_tmp_tmpmvs2dmry_SlowMax.dfy | slow_max | True | lifted | agree |
| Dafny_tmp_tmpmvs2dmry_examples1.dfy | Abs | False | lifted | lifter |
| Dafny_tmp_tmpmvs2dmry_examples1.dfy | MultiReturn | False | refused:multi-return | agree |
| Dafny_tmp_tmpmvs2dmry_examples1.dfy | Max | False | lifted | lifter |
| Dafny_tmp_tmpmvs2dmry_examples2.dfy | add_by_inc | False | lifted | lifter |
| Dafny_tmp_tmpmvs2dmry_examples2.dfy | Product | False | lifted | lifter |
| Dafny_tmp_tmpmvs2dmry_examples2.dfy | gcdCalc | False | lifted | lifter |
| Dafny_tmp_tmpmvs2dmry_examples2.dfy | exp_by_sqr | False | refused:real | agree |
| Dafny_tmp_tmpmvs2dmry_pancakesort_findmax.dfy | findMax | False | refused:unbounded-quantifier | gap-name |
| Dafny_tmp_tmpmvs2dmry_pancakesort_flip.dfy | flip | False | refused:zero-returns | agree |
| Dafny_tmp_tmpv_d3qi10_2_min.dfy | minMethod | False | lifted | undecided |
| Dafny_tmp_tmpv_d3qi10_2_min.dfy | minArray | False | refused:heap | gap-name |
| Dafny_tmp_tmpv_d3qi10_3_cumsum.dfy | cumsum | False | refused:function-contract | gap-name |
| FMSE-2022-2023_tmp_tmp6_x_ba46_Lab10_Lab10.dfy | (file) | False | refused:no-method | gap-name |
| FMSE-2022-2023_tmp_tmp6_x_ba46_Lab1_Lab1.dfy | (file) | False | refused:no-method | gap-name |
| FMSE-2022-2023_tmp_tmp6_x_ba46_Lab2_Lab2.dfy | (file) | False | refused:datatype | agree |
| FMSE-2022-2023_tmp_tmp6_x_ba46_Lab3_Lab3.dfy | (file) | False | refused:datatype | agree |
| Final-Project-Dafny_tmp_tmpmcywuqox_Attempts_Exercise3_Increment_Array.dfy | incrementArray | False | refused:zero-returns | agree |
| Final-Project-Dafny_tmp_tmpmcywuqox_Attempts_Exercise4_Find_Max.dfy | findMax | False | refused:multi-return | agree |
| Final-Project-Dafny_tmp_tmpmcywuqox_Attempts_Exercise6_Binary_Search.dfy | binarySearch | False | refused:unbounded-quantifier | gap-name |
| Final-Project-Dafny_tmp_tmpmcywuqox_Attempts_Insertion_Sort_Normal.dfy | lookForMin | False | lifted | undecided |
| Final-Project-Dafny_tmp_tmpmcywuqox_Attempts_Insertion_Sort_Normal.dfy | insertionSort | False | refused:function-contract | gap-name |
| Final-Project-Dafny_tmp_tmpmcywuqox_Attempts_Insertion_Sorted_Standard.dfy | sorting | False | refused:function-contract | gap-name |
| Final-Project-Dafny_tmp_tmpmcywuqox_Attempts_Merge_Sort.dfy | (file) | False | refused:no-method | gap-name |
| Final-Project-Dafny_tmp_tmpmcywuqox_Attempts_Quick_Sort.dfy | threshold | False | refused:multi-return | agree |
| Final-Project-Dafny_tmp_tmpmcywuqox_Attempts_Quick_Sort.dfy | quickSort | False | refused:seq-return | agree |
| Final-Project-Dafny_tmp_tmpmcywuqox_Attempts_Selection_Sort_Standard.dfy | selectionSorted | False | refused:zero-returns | agree |
| Final-Project-Dafny_tmp_tmpmcywuqox_Final_Project_3.dfy | nonZeroReturn | False | lifted | lifter |
| FlexWeek_tmp_tmpc_tfdj_3_ex2.dfy | aba | False | refused:array | agree |
| FlexWeek_tmp_tmpc_tfdj_3_ex3.dfy | Max | False | refused:seq-slice | agree |
| FlexWeek_tmp_tmpc_tfdj_3_ex4.dfy | join | False | refused:array | agree |
| FlexWeek_tmp_tmpc_tfdj_3_reverse.dfy | Reverse | False | refused:array | agree |
| Formal-Methods-Project_tmp_tmphh2ar2xv_BubbleSort.dfy | (file) | False | refused:no-method | gap-name |
| Formal-Methods-Project_tmp_tmphh2ar2xv_Factorial.dfy | (file) | False | refused:no-method | gap-name |
| Formal-Verification-Project_tmp_tmp9gmwsmyp_strings3.dfy | isPrefix | False | refused:seq-slice | agree |
| Formal-Verification-Project_tmp_tmp9gmwsmyp_strings3.dfy | isSubstring | False | refused:seq-slice | agree |
| Formal-Verification-Project_tmp_tmp9gmwsmyp_strings3.dfy | haveCommonKSubstring | False | refused:seq-slice | agree |
| Formal-Verification-Project_tmp_tmp9gmwsmyp_strings3.dfy | maxCommonSubstringLength | False | refused:seq-slice | agree |
| Formal-Verification_tmp_tmpuyt21wjt_Dafny_strings1.dfy | isPrefix | False | refused:string-char | agree |
| Formal-Verification_tmp_tmpuyt21wjt_Dafny_strings1.dfy | isSubstring | False | refused:seq-slice | agree |
| Formal-Verification_tmp_tmpuyt21wjt_Dafny_strings1.dfy | haveCommonKSubstring | False | refused:seq-slice | agree |
| Formal-Verification_tmp_tmpuyt21wjt_Dafny_strings1.dfy | maxCommonSubstringLength | False | refused:seq-slice | agree |
| Formal-Verification_tmp_tmpuyt21wjt_Dafny_strings3.dfy | isPrefix | False | refused:seq-slice | agree |
| Formal-Verification_tmp_tmpuyt21wjt_Dafny_strings3.dfy | isSubstring | False | refused:seq-slice | agree |
| Formal-Verification_tmp_tmpuyt21wjt_Dafny_strings3.dfy | haveCommonKSubstring | False | refused:seq-slice | agree |
| Formal-Verification_tmp_tmpuyt21wjt_Dafny_strings3.dfy | maxCommonSubstringLength | False | refused:seq-slice | agree |
| Formal-methods-of-software-development_tmp_tmppryvbyty_Bloque 1_Lab3.dfy | multipleReturns | False | refused:bodyless-method | agree |
| Formal-methods-of-software-development_tmp_tmppryvbyty_Bloque 1_Lab3.dfy | multipleReturns2 | False | refused:bodyless-method | agree |
| Formal-methods-of-software-development_tmp_tmppryvbyty_Bloque 1_Lab3.dfy | multipleReturns3 | False | refused:bodyless-method | agree |
| Formal-methods-of-software-development_tmp_tmppryvbyty_Bloque 1_Lab3.dfy | ComputeFact | False | lifted | lifter |
| Formal-methods-of-software-development_tmp_tmppryvbyty_Bloque 1_Lab3.dfy | ComputeFact2 | False | lifted | lifter |
| Formal-methods-of-software-development_tmp_tmppryvbyty_Bloque 1_Lab3.dfy | Sqare | False | lifted | lifter |
| Formal-methods-of-software-development_tmp_tmppryvbyty_Bloque 1_Lab3.dfy | Sqare2 | False | lifted | lifter |
| Formal-methods-of-software-development_tmp_tmppryvbyty_Bloque 2_Lab6.dfy | (file) | False | refused:no-method | gap-name |
| Formal-methods-of-software-development_tmp_tmppryvbyty_Examenes_Beni_Heusel-Benedikt-Ass-1.dfy | (file) | False | refused:no-method | gap-name |
| FormalMethods_tmp_tmpvda2r3_o_dafny_Invariants_ex1.dfy | Mult | True | lifted | agree |
| FormalMethods_tmp_tmpvda2r3_o_dafny_Invariants_ex2.dfy | Pot | True | lifted | agree |
| Formal_Verification_With_Dafny_tmp_tmp5j79rq48_Counter.dfy | (file) | False | refused:heap | agree |
| Formal_Verification_With_Dafny_tmp_tmp5j79rq48_LimitedStack.dfy | (file) | False | refused:heap | agree |
| HATRA-2022-Paper_tmp_tmp5texxy8l_copilot_verification_Binary Search_binary_search.dfy | BinarySearch | False | refused:array | agree |
| HATRA-2022-Paper_tmp_tmp5texxy8l_copilot_verification_Largest Sum_largest_sum.dfy | largest_sum | False | refused:array | agree |
| HATRA-2022-Paper_tmp_tmp5texxy8l_copilot_verification_Sort Array_sort_array.dfy | sortArray | False | refused:array | agree |
| HATRA-2022-Paper_tmp_tmp5texxy8l_copilot_verification_Two Sum_two_sum.dfy | twoSum | False | refused:multi-return | agree |
| Invoker_tmp_tmpypx0gs8x_dafny_abstract-interpreter_SimpleVerifier.dfy | (file) | False | refused:no-method | gap-name |
| M2_tmp_tmp2laaavvl_Software Verification_Exercices_Exo4-CountAndReturn.dfy | CountToAndReturnN | True | lifted | agree |
| M2_tmp_tmp2laaavvl_Software Verification_Exercices_Exo7-ComputeSum.dfy | ComputeSum | True | lifted | agree |
| M2_tmp_tmp2laaavvl_Software Verification_Exercices_Exo9-Carre.dfy | Carre | True | lifted | agree |
| MFDS_tmp_tmpvvr5y1t9_Assignments_Ass-1-2020-21-Sol-eGela.dfy | (file) | False | refused:no-method | gap-name |
| MFES_2021_tmp_tmpuljn8zd9_Exams_Special_Exam_03_2020_4_CatalanNumbers.dfy | calcC | False | refused:div-mod | agree |
| MFES_2021_tmp_tmpuljn8zd9_FCUL_Exercises_10_find.dfy | find | False | lifted | undecided |
| MFES_2021_tmp_tmpuljn8zd9_FCUL_Exercises_8_sum.dfy | sum | False | refused:div-mod | agree |
| MFES_2021_tmp_tmpuljn8zd9_PracticalClasses_TP3_2_Insertion_Sort.dfy | insertionSort | False | refused:zero-returns | agree |
| MFES_2021_tmp_tmpuljn8zd9_TheoreticalClasses_Power.dfy | powerIter | False | refused:real | agree |
| MFES_2021_tmp_tmpuljn8zd9_TheoreticalClasses_Power.dfy | powerOpt | False | refused:real | agree |
| MFS_tmp_tmpmmnu354t_Praticas_TP9_Power.dfy | powerIter | False | refused:real | agree |
| MFS_tmp_tmpmmnu354t_Praticas_TP9_Power.dfy | powerOpt | False | refused:real | agree |
| MFS_tmp_tmpmmnu354t_Testes anteriores_T2_ex5_2020_2.dfy | leq | False | refused:seq-slice | agree |
| MIEIC_mfes_tmp_tmpq3ho7nve_TP3_binary_search.dfy | binarySearch | False | refused:function-contract | gap-name |
| MIEIC_mfes_tmp_tmpq3ho7nve_exams_appeal_20_p4.dfy | calcF | True | lifted | agree |
| MIEIC_mfes_tmp_tmpq3ho7nve_exams_mt2_19_p4.dfy | calcR | True | lifted | agree |
| MIEIC_mfes_tmp_tmpq3ho7nve_exams_mt2_19_p5.dfy | partition | False | refused:array | agree |
| MIEIC_mfes_tmp_tmpq3ho7nve_exams_special_20_p5.dfy | binarySearch | False | refused:function-contract | gap-name |
| Metodos_Formais_tmp_tmpbez22nnn_Aula_2_ex1.dfy | Mult | True | lifted | agree |
| Metodos_Formais_tmp_tmpbez22nnn_Aula_2_ex2.dfy | Pot | True | lifted | agree |
| Metodos_Formais_tmp_tmpbez22nnn_Aula_4_ex1.dfy | (file) | False | refused:no-method | gap-name |
| Metodos_Formais_tmp_tmpbez22nnn_Aula_4_ex3.dfy | ComputeFib | False | lifted | lifter |
| Metodos_Formais_tmp_tmpql2hwcsh_Arrays_explicacao.dfy | buscar | False | refused:early-exit | agree |
| Metodos_Formais_tmp_tmpql2hwcsh_Arrays_somatorioArray.dfy | somatorio | False | refused:function-contract | gap-name |
| Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_fatorial2.dfy | Fatorial | True | lifted | agree |
| Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_fibonacci.dfy | ComputeFib | True | lifted | agree |
| Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_multiplicador.dfy | Mult | True | lifted | agree |
| Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_potencia.dfy | Pot | True | lifted | agree |
| Prog-Fun-Solutions_tmp_tmp7_gmnz5f_extra_mod.dfy | mod | False | refused:div-mod | agree |
| Prog-Fun-Solutions_tmp_tmp7_gmnz5f_extra_mod2.dfy | mod2 | False | refused:div-mod | agree |
| Prog-Fun-Solutions_tmp_tmp7_gmnz5f_extra_pow.dfy | Pow | True | lifted | agree |
| Prog-Fun-Solutions_tmp_tmp7_gmnz5f_extra_sum.dfy | Sum | True | lifted | agree |
| Prog-Fun-Solutions_tmp_tmp7_gmnz5f_mockExam2_p2.dfy | problem2 | False | refused:multi-return | agree |
| Prog-Fun-Solutions_tmp_tmp7_gmnz5f_mockExam2_p3.dfy | problem3 | True | lifted | agree |
| Prog-Fun-Solutions_tmp_tmp7_gmnz5f_mockExam2_p5.dfy | problem5 | True | lifted | agree |
| Prog-Fun-Solutions_tmp_tmp7_gmnz5f_mockExam2_p6.dfy | problem6 | True | refused:lift-check-failed | undecided |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_advanced examples_ArrayMap.dfy | ArrayMap | False | refused:zero-returns | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_advanced examples_EvenPredicate.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_advanced examples_GenericMax.dfy | GenericMax | False | refused:higher-order | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_advanced examples_InsertionSort.dfy | InsertionSort | False | refused:heap | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_advanced examples_MatrixMultiplication.dfy | multiply | False | refused:heap | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_advanced examples_Modules.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_advanced examples_OneHundredPrisonersAndALightbulb.dfy | CardinalitySubsetLt | False | refused:zero-returns | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_advanced examples_OneHundredPrisonersAndALightbulb.dfy | strategy | False | refused:set | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_advanced examples_Percentile.dfy | Percentile | False | refused:function-contract | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_advanced examples_Percentile.dfy | PercentileNonUniqueAnswer | False | refused:function-contract | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_advanced examples_Refinement.dfy | (file) | False | refused:heap | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_advanced examples_ReverseString.dfy | yarra | False | refused:heap | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_advanced examples_demo.dfy | Partition | False | refused:multi-return | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_ProgramProofs_ch15.dfy | SelectionSort | False | refused:function-contract | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_ProgramProofs_ch15.dfy | QuickSort | False | refused:zero-returns | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_ProgramProofs_ch15.dfy | QuickSortAux | False | refused:function-contract | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_ProgramProofs_ch15.dfy | Partition | False | refused:function-contract | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_examples_bubblesort.dfy | BubbleSort | False | refused:div-mod | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_examples_relativeOrder.dfy | FindEvenNumbers | False | refused:div-mod | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_examples_simpleMultiplication.dfy | Foo | False | lifted | lifter |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_heap2.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_leetcode_BoatsToSavePeople.dfy | numRescueBoats | False | refused:seq-literal | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_leetcode_FindPivotIndex.dfy | FindPivotIndex | False | refused:seq-slice | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_leetcode_ReverseLinkedList.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_leetcode_lc-remove-element.dfy | removeElement | False | refused:array-mutation | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_leetcode_pathSum.dfy | (file) | False | refused:datatype | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_leetcode_stairClimbing.dfy | (file) | False | refused:datatype | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_leetcode_validAnagram.dfy | toMultiset | False | refused:string-char | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_leetcode_validAnagram.dfy | msetEqual | False | refused:type-decl | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_leetcode_validAnagram.dfy | isAnagram | False | refused:string-char | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_lib_seq.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_math_pearson.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_basic examples_BubbleSort.dfy | bubbleSort | False | refused:heap | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_basic examples_BubbleSort_sol.dfy | bubbleSort | False | refused:heap | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_basic examples_add_by_one.dfy | add_by_one | False | lifted | lifter |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_basic examples_add_by_one.dfy | bar | False | refused:nondet | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_basic examples_add_by_one_details.dfy | plus_one | False | lifted | lifter |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_basic examples_find_max.dfy | FindMax | False | refused:heap | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_basic examples_product_details.dfy | CalcProduct | False | refused:nondet | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_basic examples_sumto_sol.dfy | SumUpTo | False | lifted | lifter |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_basic examples_sumto_sol.dfy | Total | False | refused:seq-slice | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny0_GhostITECompilation.dfy | (file) | False | refused:let-expression | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny0_ModulePrint.dfy | (file) | False | refused:heap | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny1_BDD.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny1_ListContents.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny1_Queue.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny2_COST-verif-comp-2011-2-MaxTree-class.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny2_COST-verif-comp-2011-3-TwoDuplicates.dfy | Search | False | refused:function-contract | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny2_Classics.dfy | AdditiveFactorial | False | lifted | undecided |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny2_Classics.dfy | FIND | False | refused:zero-returns | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny2_MajorityVote.dfy | (file) | False | refused:let-expression | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny2_StoreAndRetrieve.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny3_CachedContainer.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny3_CalcExample.dfy | CalculationalStyleProof | False | refused:bodyless-function | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny3_CalcExample.dfy | DifferentStyleProof | False | refused:bodyless-function | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny3_InfiniteTrees.dfy | (file) | False | refused:let-expression | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny3_Iter.dfy | (file) | False | refused:heap | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny3_Streams.dfy | (file) | False | refused:datatype | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny4_ACL2-extractor.dfy | (file) | False | refused:resolve-failure | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny4_Bug170.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny4_ClassRefinement.dfy | (file) | False | refused:heap | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny4_NipkowKlein-chapter3.dfy | (file) | False | refused:datatype | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny4_Primes.dfy | (file) | False | refused:let-expression | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from_dafny_main_repo_dafny0_snapshots_Inputs_Snapshots1.dfy | N | False | refused:bodyless-method | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from_dafny_main_repo_dafny0_snapshots_Inputs_Snapshots5.dfy | N | False | refused:bodyless-method | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_lightening_verifier.dfy | (file) | False | refused:let-expression | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_mathematical objects verification_examples_fast_exp.dfy | fast_exp | False | refused:seq-literal | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_mathematical objects verification_examples_interval_example.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_mathematical objects verification_examples_library.dfy | (file) | False | refused:datatype | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_mathematical objects verification_examples_logic.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_pregel algorithms_skeleton_nondet-permutation.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_vampire project_original_Searching.dfy | Find | False | refused:heap | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_variant examples_KatzManna.dfy | NinetyOne | False | refused:early-exit | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_variant examples_SumOfCubes.dfy | (file) | False | refused:no-method | gap-name |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_verified algorithms_inductive_props.dfy | (file) | False | refused:datatype | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_verified algorithms_lol_sort.dfy | swap | False | refused:zero-returns | agree |
| Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_verified algorithms_lol_sort.dfy | lol_sort | False | refused:unbounded-quantifier | gap-name |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_04_Hoangkim_ex_04_Hoangkim.dfy | sumOdds | False | lifted | lifter |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_04_Hoangkim_ex_04_Hoangkim.dfy | intDiv | False | refused:bodyless-method | agree |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_04_Hoangkim_ex_04_Hoangkim.dfy | intDivImpl | False | refused:multi-return | agree |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_05_Hoangkim_ex_05_Hoangkim.dfy | fibIter | False | lifted | lifter |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_05_Hoangkim_ex_05_Hoangkim.dfy | factIter | False | lifted | lifter |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_05_Hoangkim_ex_05_Hoangkim.dfy | gcdI | False | lifted | lifter |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_06_Hoangkim_ex06-solution.dfy | gcdI | True | lifted | agree |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_06_Hoangkim_ex_06_hoangkim.dfy | gcdI | True | lifted | agree |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_07_Hoangkim_ex07_Hoangkim.dfy | swap | False | refused:zero-returns | agree |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_07_Hoangkim_ex07_Hoangkim.dfy | FindMin | False | refused:heap | gap-name |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_10_Hoangkim_ex10_hoangkim.dfy | square0 | False | lifted | lifter |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_10_Hoangkim_ex10_hoangkim.dfy | square1 | False | lifted | lifter |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_10_Hoangkim_ex10_hoangkim.dfy | q | False | refused:bodyless-method | agree |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_10_Hoangkim_ex10_hoangkim.dfy | strange | False | refused:zero-returns | agree |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_example_DafnyIntro_01_Simple_Loops.dfy | Gauss | False | refused:div-mod | agree |
| Programmverifikation-und-synthese_tmp_tmppurk6ime_example_DafnyIntro_01_Simple_Loops.dfy | sumOdds | False | lifted | lifter |
| ProjectosCVS_tmp_tmp_02_gmcw_Handout 1_CVS_handout1_55754_55780.dfy | peasantMult | False | refused:div-mod | agree |
| ProjectosCVS_tmp_tmp_02_gmcw_Handout 1_CVS_handout1_55754_55780.dfy | euclidianDiv | False | refused:multi-return | agree |
| QS_BoilerPlate1_tmp_tmpa29vtz9__Ex2.dfy | copyArr | False | refused:array | agree |
| QS_BoilerPlate1_tmp_tmpa29vtz9__Ex2.dfy | mergeArr | False | refused:unbounded-quantifier | gap-name |
| QS_BoilerPlate1_tmp_tmpa29vtz9__Ex2.dfy | sort | False | refused:unbounded-quantifier | gap-name |
| QS_BoilerPlate1_tmp_tmpa29vtz9__Ex2.dfy | sortAux | False | refused:unbounded-quantifier | gap-name |
| RollingMax.dfy | max | False | refused:seq-literal | agree |
| RollingMax.dfy | RollingMax | False | refused:seq-return | agree |
| SENG2011_tmp_tmpgk5jq85q_ass1_ex7.dfy | (file) | False | refused:no-method | gap-name |
| SENG2011_tmp_tmpgk5jq85q_ass1_ex8.dfy | GetEven | False | refused:zero-returns | agree |
| SENG2011_tmp_tmpgk5jq85q_ass2_ex1.dfy | StringSwap | False | refused:string-char | agree |
| SENG2011_tmp_tmpgk5jq85q_ass2_ex2.dfy | String3Sort | False | refused:unbounded-quantifier | gap-name |
| SENG2011_tmp_tmpgk5jq85q_ass2_ex3.dfy | BadSort | False | refused:unbounded-quantifier | gap-name |
| SENG2011_tmp_tmpgk5jq85q_ass2_ex5.dfy | (file) | False | refused:no-method | gap-name |
| SENG2011_tmp_tmpgk5jq85q_exam_ex2.dfy | Getmini | False | refused:return-not-assigned-on-all-paths | gap-name |
| SENG2011_tmp_tmpgk5jq85q_exam_ex3.dfy | Symmetric | False | refused:unbounded-quantifier | gap-name |
| SENG2011_tmp_tmpgk5jq85q_exam_ex4.dfy | (file) | False | refused:no-method | gap-name |
| SENG2011_tmp_tmpgk5jq85q_flex_ex1.dfy | sum | False | refused:function-contract | gap-name |
| SENG2011_tmp_tmpgk5jq85q_flex_ex2.dfy | max | False | refused:seq-slice | agree |
| SENG2011_tmp_tmpgk5jq85q_flex_ex5.dfy | firste | False | refused:array | agree |
| SENG2011_tmp_tmpgk5jq85q_p1.dfy | Reverse | False | refused:array | agree |
| SENG2011_tmp_tmpgk5jq85q_p2.dfy | AbsIt | False | refused:zero-returns | agree |
| SiLemma_tmp_tmpfxtryv2w_utils.dfy | (file) | False | refused:no-method | gap-name |
| Simulink-To_dafny_tmp_tmpbcuesj2t_Tank.dfy | checkRegulation | False | refused:zero-returns | agree |
| Software-Verification_tmp_tmpv4ueky2d_Best Time to Buy and Sell Stock_best_time_to_buy_and_sell_stock.dfy | best_time_to_buy_and_sell_stock | False | refused:unbounded-quantifier | gap-name |
| Software-Verification_tmp_tmpv4ueky2d_Contains Duplicate_contains_duplicate.dfy | contains_duplicate | False | refused:unbounded-quantifier | gap-name |
| Software-Verification_tmp_tmpv4ueky2d_Counting Bits_counting_bits.dfy | counting_bits | False | refused:array | agree |
| Software-Verification_tmp_tmpv4ueky2d_Longest Increasing Subsequence_longest_increasing_subsequence.dfy | longest_increasing_subsequence | False | refused:array | agree |
| Software-Verification_tmp_tmpv4ueky2d_Non-overlapping Intervals_non_overlapping_intervals.dfy | non_overlapping_intervals | False | refused:generics | gap-name |
| Software-Verification_tmp_tmpv4ueky2d_Non-overlapping Intervals_non_overlapping_intervals.dfy | bubble_sort | False | refused:zero-returns | agree |
| Software-Verification_tmp_tmpv4ueky2d_Remove Duplicates from Sorted Array_remove_duplicates_from_sorted_array.dfy | remove_duplicates_from_sorted_array | False | refused:seq-return | agree |
| Software-Verification_tmp_tmpv4ueky2d_Remove Element_remove_element.dfy | remove_element | False | refused:array-mutation | agree |
| Software-Verification_tmp_tmpv4ueky2d_Valid Anagram_valid_anagram.dfy | is_anagram | False | refused:string-char | agree |
| Software-Verification_tmp_tmpv4ueky2d_Valid Anagram_valid_anagram.dfy | is_equal | False | refused:type-decl | gap-name |
| Software-Verification_tmp_tmpv4ueky2d_Valid Palindrome_valid_panlindrome.dfy | isPalindrome | False | refused:array | agree |
| Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula1.dfy | (file) | False | refused:no-method | gap-name |
| Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula2.dfy | max | False | lifted | lifter |
| Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula2.dfy | mystery1 | False | lifted | lifter |
| Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula2.dfy | mystery2 | False | refused:calls-other-method | gap-name |
| Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula2.dfy | m1 | False | refused:return-not-assigned-on-all-paths | gap-name |
| Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula2.dfy | m2 | False | refused:return-not-assigned-on-all-paths | gap-name |
| Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula2.dfy | m3 | False | lifted | lifter |
| Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula2.dfy | m4 | False | lifted | lifter |
| Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula3.dfy | (file) | False | refused:datatype | agree |
| Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula5.dfy | (file) | False | refused:no-method | gap-name |
| Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_handout1.dfy | (file) | False | refused:datatype | agree |
| Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_handout2.dfy | (file) | False | refused:datatype | agree |
| TFG_tmp_tmpbvsao41w_Algoritmos Dafny_div_ent_it.dfy | div_ent_it | False | refused:multi-return | agree |
| TFG_tmp_tmpbvsao41w_Algoritmos Dafny_suma_it.dfy | suma_it | False | refused:array | agree |
| Trab1-Metodos-Formais_tmp_tmp_8fa4trr_circular-array.dfy | (file) | False | refused:heap | agree |
| VerifiedMergeSortDafny_tmp_tmpva7qms1b_MergeSort.dfy | mergeSimple | False | refused:zero-returns | agree |
| VerifiedMergeSortDafny_tmp_tmpva7qms1b_MergeSort.dfy | merge | False | refused:zero-returns | agree |
| Workshop_tmp_tmp0cu11bdq_Lecture_Answers_max_array.dfy | max | False | refused:heap | gap-name |
| Workshop_tmp_tmp0cu11bdq_Lecture_Answers_selection_sort.dfy | SelectionSort | False | refused:heap | gap-name |
| Workshop_tmp_tmp0cu11bdq_Lecture_Answers_sum_array.dfy | sum_array | False | refused:heap | gap-name |
| Workshop_tmp_tmp0cu11bdq_Lecture_Answers_triangle_number.dfy | TriangleNumber | False | refused:div-mod | agree |
| Workshop_tmp_tmp0cu11bdq_Workshop_Answers_Question5.dfy | rev | False | refused:zero-returns | agree |
| Workshop_tmp_tmp0cu11bdq_Workshop_Answers_Question6.dfy | arrayUpToN | False | refused:array | agree |
| WrappedEther.dfy | (file) | False | refused:no-method | gap-name |
| assertive-programming-assignment-1_tmp_tmp3h_cj44u_FindRange.dfy | (file) | False | refused:higher-order | agree |
| assertive-programming-assignment-1_tmp_tmp3h_cj44u_ProdAndCount.dfy | ProdAndCount | False | refused:seq-literal | agree |
| assertive-programming-assignment-1_tmp_tmp3h_cj44u_SearchAddends.dfy | FindAddends | False | refused:unbounded-quantifier | gap-name |
| bbfny_tmp_tmpw4m0jvl0_enjoying.dfy | MultipleReturns | False | refused:multi-return | agree |
| bbfny_tmp_tmpw4m0jvl0_enjoying.dfy | Max | False | lifted | undecided |
| bbfny_tmp_tmpw4m0jvl0_enjoying.dfy | Abs | False | lifted | undecided |
| bbfny_tmp_tmpw4m0jvl0_enjoying.dfy | Find | False | refused:early-exit | agree |
| bbfny_tmp_tmpw4m0jvl0_enjoying.dfy | FindMax | False | refused:lift-check-failed | gap-name |
| circular-queue-implemetation_tmp_tmpnulfdc9l_Queue.dfy | (file) | False | refused:heap | agree |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1-assignment-2.dfy | PlusOne | False | lifted | undecided |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1-assignment-2.dfy | IntDiv | False | refused:multi-return | agree |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1-assignment-2.dfy | ArraySum | False | refused:array | agree |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1-assignment-2.dfy | Euclid | False | refused:bodyless-method | agree |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1-assignment-2.dfy | IsSorted | False | refused:unbounded-quantifier | gap-name |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1-assignment-2.dfy | IsPrime | False | refused:div-mod | agree |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1-assignment-2.dfy | Reverse | False | refused:array | agree |
| cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1-assignment-2.dfy | NoDups | False | refused:unbounded-quantifier | gap-name |
| cs245-verification_tmp_tmp0h_nxhqp_A8_Q1.dfy | A8Q1 | True | lifted | agree |
| cs245-verification_tmp_tmp0h_nxhqp_A8_Q2.dfy | A8Q1 | True | lifted | agree |
| cs245-verification_tmp_tmp0h_nxhqp_Assignments_simple.dfy | simple | True | lifted | agree |
| cs245-verification_tmp_tmp0h_nxhqp_SortingIssues_BubbleSortCode.dfy | (file) | False | refused:no-method | gap-name |
| cs245-verification_tmp_tmp0h_nxhqp_SortingIssues_FirstAttempt.dfy | sort | False | refused:zero-returns | agree |
| cs245-verification_tmp_tmp0h_nxhqp_power.dfy | compute_power | True | lifted | agree |
| cs245-verification_tmp_tmp0h_nxhqp_quicksort-partition.dfy | QuicksortPartition | False | refused:multi-return | agree |
| cs357_tmp_tmpn4fsvwzs_lab7_question2.dfy | Two | True | lifted | agree |
| cs357_tmp_tmpn4fsvwzs_lab7_question5.dfy | M1 | False | refused:calls-other-method | gap-name |
| cs357_tmp_tmpn4fsvwzs_lab7_question5.dfy | A1 | False | lifted | lifter |
| cs686_tmp_tmpdhuh5dza_classNotes_notes-9-8-21.dfy | (file) | False | refused:heap | agree |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_dafny0_ContainerRanks.dfy | (file) | False | refused:no-method | gap-name |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_dafny0_DividedConstructors.dfy | (file) | False | refused:no-method | gap-name |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_dafny0_ForallCompilationNewSyntax.dfy | (file) | False | refused:heap | agree |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_dafny0_InSetComprehension.dfy | (file) | False | refused:no-method | gap-name |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_dafny0_PrecedenceLinter.dfy | (file) | False | refused:let-expression | gap-name |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_dafny0_SeqFromArray.dfy | (file) | False | refused:no-method | gap-name |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_dafny0_SharedDestructorsCompile.dfy | (file) | False | refused:datatype | agree |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_binary-search.dfy | binSearch | False | refused:function-contract | gap-name |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_fibonacci.dfy | ComputeFib | True | lifted | agree |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_find.dfy | Find | False | refused:heap | gap-name |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_modifying-arrays.dfy | NewArray | False | refused:array | agree |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_modifying-arrays.dfy | InitArray | False | refused:zero-returns | agree |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_modifying-arrays.dfy | UpdateElements | False | refused:zero-returns | agree |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_modifying-arrays.dfy | IncrementArray | False | refused:zero-returns | agree |
| dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_modifying-arrays.dfy | CopyArray | False | refused:zero-returns | agree |
| dafleet_tmp_tmpa2e4kb9v_0001-0050_0001-two-sum.dfy | (file) | False | refused:let-expression | gap-name |
| dafleet_tmp_tmpa2e4kb9v_0001-0050_0003-longest-substring-without-repeating-characters.dfy | (file) | False | refused:let-expression | gap-name |
| dafleet_tmp_tmpa2e4kb9v_0001-0050_0005-longest-palindromic-substring.dfy | (file) | False | refused:tuple | agree |
| dafny-aoc-2019_tmp_tmpj6suy_rv_parser_split.dfy | (file) | False | refused:no-method | gap-name |
| dafny-duck_tmp_tmplawbgxjo_ex3.dfy | BadSort | False | refused:unbounded-quantifier | gap-name |
| dafny-duck_tmp_tmplawbgxjo_ex5.dfy | (file) | False | refused:no-method | gap-name |
| dafny-duck_tmp_tmplawbgxjo_p1.dfy | SumArray | False | refused:seq-slice | agree |
| dafny-duck_tmp_tmplawbgxjo_p2.dfy | absx | False | refused:array | agree |
| dafny-duck_tmp_tmplawbgxjo_p3.dfy | max | False | refused:seq-slice | agree |
| dafny-duck_tmp_tmplawbgxjo_p4.dfy | single | False | refused:array | agree |
| dafny-duck_tmp_tmplawbgxjo_p6.dfy | FilterVowelsArray | False | refused:seq-literal | agree |
| dafny-exercise_tmp_tmpouftptir_absIt.dfy | AbsIt | False | refused:zero-returns | agree |
| dafny-exercise_tmp_tmpouftptir_appendArray.dfy | appendArray | False | refused:array | agree |
| dafny-exercise_tmp_tmpouftptir_countNeg.dfy | CountNeg | False | refused:function-contract | gap-name |
| dafny-exercise_tmp_tmpouftptir_filter.dfy | Filter | False | refused:nested-seq | agree |
| dafny-exercise_tmp_tmpouftptir_firstE.dfy | firstE | False | refused:array | agree |
| dafny-exercise_tmp_tmpouftptir_maxArray.dfy | MaxArray | False | lifted | undecided |
| dafny-exercise_tmp_tmpouftptir_prac1_ex1.dfy | (file) | False | refused:no-method | gap-name |
| dafny-exercise_tmp_tmpouftptir_prac1_ex2.dfy | Deli | False | refused:zero-returns | agree |
| dafny-exercise_tmp_tmpouftptir_prac3_ex2.dfy | GetEven | False | refused:zero-returns | agree |
| dafny-exercise_tmp_tmpouftptir_prac4_ex2.dfy | GetTriple | False | refused:function-contract | gap-name |
| dafny-exercise_tmp_tmpouftptir_reverse.dfy | Reverse | False | refused:array | agree |
| dafny-exercise_tmp_tmpouftptir_zapNegatives.dfy | ZapNegatives | False | refused:zero-returns | agree |
| dafny-exercises_tmp_tmp5mvrowrx_leetcode_26-remove-duplicates-from-sorted-array.dfy | RemoveDuplicates | False | refused:array-mutation | agree |
| dafny-exercises_tmp_tmp5mvrowrx_paper_krml190.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_LanguageServerTest_DafnyFiles_symbolTable_15_array.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_VSComp2010_Problem1-SumMax.dfy | M | False | refused:multi-return | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_VSI-Benchmarks_b1.dfy | Add | False | lifted | lifter |
| dafny-language-server_tmp_tmpkir0kenl_Test_VSI-Benchmarks_b1.dfy | Mul | False | refused:calls-other-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_VSI-Benchmarks_b2.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_allocated1_dafny0_fun-with-slices.dfy | seqIntoArray | False | refused:zero-returns | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_comp_Arrays.dfy | (file) | False | refused:heap | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny0_FuelTriggers.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny0_snapshots_Inputs_Snapshots0.dfy | bar | False | refused:bodyless-method | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny1_Cubes.dfy | Cubes | False | refused:zero-returns | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny1_ListReverse.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny1_MatrixFun.dfy | MirrorImage | False | refused:zero-returns | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny1_MatrixFun.dfy | Flip | False | refused:zero-returns | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny2_COST-verif-comp-2011-1-MaxArray.dfy | max | False | refused:ghost-local | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny2_Intervals.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny2_SegmentSum.dfy | MaxSegSum | False | refused:multi-return | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny2_TreeBarrier.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny2_TuringFactorial.dfy | ComputeFactorial | True | lifted | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny3_InductionVsCoinduction.dfy | (file) | False | refused:datatype | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny4_Bug144.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny4_Bug165.dfy | Select | False | refused:bodyless-function | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny4_Bug58.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny4_Bug92.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny4_Fstar-QuickSort.dfy | (file) | False | refused:datatype | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny4_Lucas-down.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny4_MonadicLaws.dfy | (file) | False | refused:datatype | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny4_Regression19.dfy | (file) | False | refused:higher-order | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny4_git-issue133.dfy | (file) | False | refused:datatype | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny4_git-issue40.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny4_git-issue41.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny4_git-issue67.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny4_git-issue74.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_dafny4_git-issue76.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_git-issues_git-issue-336.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_hofs_Compilation.dfy | (file) | False | refused:higher-order | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_hofs_Requires.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_hofs_SumSum.dfy | (file) | False | refused:higher-order | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_hofs_WhileLoop.dfy | (file) | False | refused:higher-order | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_triggers_auto-triggers-fix-an-issue-listed-in-the-ironclad-notebook.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_triggers_function-applications-are-triggers.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_triggers_large-quantifiers-dont-break-dafny.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_triggers_loop-detection-looks-at-ranges-too.dfy | (file) | False | refused:no-method | gap-name |
| dafny-language-server_tmp_tmpkir0kenl_Test_tutorial_maximum.dfy | Maximum | False | refused:seq-literal | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_vacid0_Composite.dfy | (file) | False | refused:heap | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_vstte2012_Two-Way-Sort.dfy | swap | False | refused:zero-returns | agree |
| dafny-language-server_tmp_tmpkir0kenl_Test_vstte2012_Two-Way-Sort.dfy | two_way_sort | False | refused:zero-returns | agree |
| dafny-learn_tmp_tmpn94ir40q_R01_assertions.dfy | Abs | False | lifted | lifter |
| dafny-learn_tmp_tmpn94ir40q_R01_assertions.dfy | Max | False | lifted | lifter |
| dafny-learn_tmp_tmpn94ir40q_R01_functions.dfy | Abs | False | lifted | lifter |
| dafny-learn_tmp_tmpn94ir40q_R01_functions.dfy | TestDouble | False | lifted | lifter |
| dafny-mini-project_tmp_tmpjxr3wzqh_src_project2a.dfy | (file) | False | refused:no-method | gap-name |
| dafny-programs_tmp_tmpcwodh6qh_src_expt.dfy | expt | True | lifted | agree |
| dafny-programs_tmp_tmpcwodh6qh_src_factorial.dfy | factorial | True | lifted | agree |
| dafny-programs_tmp_tmpcwodh6qh_src_max.dfy | Max | False | lifted | lifter |
| dafny-programs_tmp_tmpcwodh6qh_src_ticketsystem.dfy | (file) | False | refused:no-method | gap-name |
| dafny-rope_tmp_tmpl4v_njmy_Rope.dfy | (file) | False | refused:no-method | gap-name |
| dafny-sandbox_tmp_tmp3tu2bu8a_Stlc.dfy | (file) | False | refused:datatype | agree |
| dafny-synthesis_task_id_101.dfy | KthElement | False | lifted | undecided |
| dafny-synthesis_task_id_105.dfy | CountTrue | False | refused:heap | gap-name |
| dafny-synthesis_task_id_106.dfy | AppendArrayToSeq | False | refused:seq-return | agree |
| dafny-synthesis_task_id_113.dfy | IsInteger | False | refused:as-cast | gap-name |
| dafny-synthesis_task_id_126.dfy | SumOfCommonDivisors | False | refused:div-mod | agree |
| dafny-synthesis_task_id_127.dfy | Multiply | True | lifted | agree |
| dafny-synthesis_task_id_133.dfy | SumOfNegatives | False | refused:heap | gap-name |
| dafny-synthesis_task_id_135.dfy | NthHexagonalNumber | True | lifted | agree |
| dafny-synthesis_task_id_139.dfy | CircleCircumference | False | refused:real | agree |
| dafny-synthesis_task_id_14.dfy | TriangularPrismVolume | False | refused:div-mod | agree |
| dafny-synthesis_task_id_142.dfy | CountIdenticalPositions | False | refused:set | agree |
| dafny-synthesis_task_id_143.dfy | CountArrays | False | refused:nested-seq | agree |
| dafny-synthesis_task_id_145.dfy | MaxDifference | False | refused:unbounded-quantifier | gap-name |
| dafny-synthesis_task_id_161.dfy | RemoveElements | False | refused:function-contract | gap-name |
| dafny-synthesis_task_id_17.dfy | SquarePerimeter | True | lifted | agree |
| dafny-synthesis_task_id_170.dfy | SumInRange | False | refused:heap | gap-name |
| dafny-synthesis_task_id_171.dfy | PentagonPerimeter | True | lifted | agree |
| dafny-synthesis_task_id_18.dfy | RemoveChars | False | refused:string-char | agree |
| dafny-synthesis_task_id_2.dfy | SharedElements | False | refused:function-contract | gap-name |
| dafny-synthesis_task_id_227.dfy | MinOfThree | True | lifted | agree |
| dafny-synthesis_task_id_230.dfy | ReplaceBlanksWithChar | False | refused:string-char | agree |
| dafny-synthesis_task_id_233.dfy | CylinderLateralSurfaceArea | False | refused:real | agree |
| dafny-synthesis_task_id_234.dfy | CubeVolume | True | lifted | agree |
| dafny-synthesis_task_id_238.dfy | CountNonEmptySubstrings | False | refused:string-char | agree |
| dafny-synthesis_task_id_240.dfy | ReplaceLastElement | False | refused:seq-return | agree |
| dafny-synthesis_task_id_242.dfy | CountCharacters | False | refused:string-char | agree |
| dafny-synthesis_task_id_249.dfy | Intersection | False | refused:function-contract | gap-name |
| dafny-synthesis_task_id_251.dfy | InsertBeforeEach | False | refused:nested-seq | agree |
| dafny-synthesis_task_id_257.dfy | Swap | False | refused:seq-return | agree |
| dafny-synthesis_task_id_261.dfy | ElementWiseDivision | False | refused:seq-return | agree |
| dafny-synthesis_task_id_262.dfy | SplitArray | False | refused:multi-return | agree |
| dafny-synthesis_task_id_264.dfy | DogYears | True | lifted | agree |
| dafny-synthesis_task_id_266.dfy | LateralSurfaceArea | True | lifted | agree |
| dafny-synthesis_task_id_267.dfy | SumOfSquaresOfFirstNOddNumbers | False | refused:div-mod | agree |
| dafny-synthesis_task_id_268.dfy | StarNumber | True | lifted | agree |
| dafny-synthesis_task_id_269.dfy | AsciiValue | False | refused:string-char | agree |
| dafny-synthesis_task_id_273.dfy | SubtractSequences | False | refused:seq-return | agree |
| dafny-synthesis_task_id_276.dfy | CylinderVolume | False | refused:real | agree |
| dafny-synthesis_task_id_279.dfy | NthDecagonalNumber | True | lifted | agree |
| dafny-synthesis_task_id_282.dfy | ElementWiseSubtraction | False | refused:array | agree |
| dafny-synthesis_task_id_284.dfy | AllElementsEqual | False | refused:heap | gap-name |
| dafny-synthesis_task_id_290.dfy | MaxLengthList | False | refused:nested-seq | agree |
| dafny-synthesis_task_id_292.dfy | Quotient | False | refused:div-mod | agree |
| dafny-synthesis_task_id_3.dfy | IsNonPrime | False | refused:div-mod | agree |
| dafny-synthesis_task_id_304.dfy | ElementAtIndexAfterRotation | False | refused:div-mod | agree |
| dafny-synthesis_task_id_307.dfy | DeepCopySeq | False | refused:seq-return | agree |
| dafny-synthesis_task_id_309.dfy | Max | True | lifted | agree |
| dafny-synthesis_task_id_310.dfy | ToCharArray | False | refused:string-char | agree |
| dafny-synthesis_task_id_312.dfy | ConeVolume | False | refused:real | agree |
| dafny-synthesis_task_id_396.dfy | StartAndEndWithSameChar | False | refused:string-char | agree |
| dafny-synthesis_task_id_397.dfy | MedianOfThree | True | lifted | agree |
| dafny-synthesis_task_id_399.dfy | BitwiseXOR | False | refused:nested-seq | agree |
| dafny-synthesis_task_id_401.dfy | IndexWiseAddition | False | refused:nested-seq | agree |
| dafny-synthesis_task_id_404.dfy | Min | True | lifted | agree |
| dafny-synthesis_task_id_406.dfy | IsOdd | False | refused:div-mod | agree |
| dafny-synthesis_task_id_412.dfy | RemoveOddNumbers | False | refused:div-mod | agree |
| dafny-synthesis_task_id_414.dfy | AnyValueExists | False | refused:early-exit | agree |
| dafny-synthesis_task_id_424.dfy | ExtractRearChars | False | refused:nested-seq | agree |
| dafny-synthesis_task_id_426.dfy | FilterOddNumbers | False | refused:div-mod | agree |
| dafny-synthesis_task_id_430.dfy | ParabolaDirectrix | False | refused:real | agree |
| dafny-synthesis_task_id_431.dfy | HasCommonElement | False | refused:heap | gap-name |
| dafny-synthesis_task_id_432.dfy | MedianLength | False | refused:div-mod | agree |
| dafny-synthesis_task_id_433.dfy | IsGreater | False | refused:heap | gap-name |
| dafny-synthesis_task_id_435.dfy | LastDigit | False | refused:div-mod | agree |
| dafny-synthesis_task_id_436.dfy | FindNegativeNumbers | False | refused:seq-return | agree |
| dafny-synthesis_task_id_441.dfy | CubeSurfaceArea | True | lifted | agree |
| dafny-synthesis_task_id_445.dfy | MultiplyElements | False | refused:seq-return | agree |
| dafny-synthesis_task_id_447.dfy | CubeElements | False | refused:array | agree |
| dafny-synthesis_task_id_452.dfy | CalculateLoss | True | lifted | agree |
| dafny-synthesis_task_id_454.dfy | ContainsZ | False | refused:string-char | agree |
| dafny-synthesis_task_id_455.dfy | MonthHas31Days | False | refused:set | agree |
| dafny-synthesis_task_id_457.dfy | MinLengthSublist | False | refused:nested-seq | agree |
| dafny-synthesis_task_id_458.dfy | RectangleArea | True | lifted | agree |
| dafny-synthesis_task_id_460.dfy | GetFirstElements | False | refused:nested-seq | agree |
| dafny-synthesis_task_id_461.dfy | CountUppercase | False | refused:as-cast | gap-name |
| dafny-synthesis_task_id_470.dfy | PairwiseAddition | False | refused:array | agree |
| dafny-synthesis_task_id_472.dfy | ContainsConsecutiveNumbers | False | refused:unbounded-quantifier | gap-name |
| dafny-synthesis_task_id_474.dfy | ReplaceChars | False | refused:string-char | agree |
| dafny-synthesis_task_id_476.dfy | (file) | False | refused:let-expression | gap-name |
| dafny-synthesis_task_id_477.dfy | ToLowercase | False | refused:as-cast | gap-name |
| dafny-synthesis_task_id_554.dfy | FindOddNumbers | False | refused:div-mod | agree |
| dafny-synthesis_task_id_555.dfy | DifferenceSumCubesAndSumNumbers | False | refused:div-mod | agree |
| dafny-synthesis_task_id_557.dfy | ToggleCase | False | refused:as-cast | gap-name |
| dafny-synthesis_task_id_565.dfy | SplitStringIntoChars | False | refused:string-char | agree |
| dafny-synthesis_task_id_566.dfy | (file) | False | refused:higher-order | agree |
| dafny-synthesis_task_id_567.dfy | IsSorted | False | refused:unbounded-quantifier | gap-name |
| dafny-synthesis_task_id_572.dfy | RemoveDuplicates | False | refused:seq-return | agree |
| dafny-synthesis_task_id_573.dfy | (file) | False | refused:let-expression | gap-name |
| dafny-synthesis_task_id_574.dfy | CylinderSurfaceArea | False | refused:real | agree |
| dafny-synthesis_task_id_576.dfy | IsSublist | False | refused:seq-slice | agree |
| dafny-synthesis_task_id_577.dfy | FactorialOfLastDigit | False | refused:div-mod | agree |
| dafny-synthesis_task_id_578.dfy | Interleave | False | refused:seq-return | agree |
| dafny-synthesis_task_id_579.dfy | DissimilarElements | False | refused:function-contract | gap-name |
| dafny-synthesis_task_id_58.dfy | HasOppositeSign | True | lifted | agree |
| dafny-synthesis_task_id_581.dfy | SquarePyramidSurfaceArea | True | lifted | agree |
| dafny-synthesis_task_id_586.dfy | SplitAndAppend | False | refused:seq-return | agree |
| dafny-synthesis_task_id_587.dfy | ArrayToSeq | False | refused:seq-return | agree |
| dafny-synthesis_task_id_588.dfy | (file) | False | refused:let-expression | gap-name |
| dafny-synthesis_task_id_59.dfy | NthOctagonalNumber | True | lifted | agree |
| dafny-synthesis_task_id_591.dfy | SwapFirstAndLast | False | refused:zero-returns | agree |
| dafny-synthesis_task_id_594.dfy | FirstEvenOddDifference | False | refused:div-mod | agree |
| dafny-synthesis_task_id_598.dfy | IsArmstrong | False | refused:div-mod | agree |
| dafny-synthesis_task_id_599.dfy | SumAndAverage | False | refused:multi-return | agree |
| dafny-synthesis_task_id_600.dfy | IsEven | False | refused:div-mod | agree |
| dafny-synthesis_task_id_602.dfy | FindFirstRepeatedChar | False | refused:multi-return | agree |
| dafny-synthesis_task_id_603.dfy | LucidNumbers | False | refused:seq-return | agree |
| dafny-synthesis_task_id_605.dfy | IsPrime | False | refused:div-mod | agree |
| dafny-synthesis_task_id_606.dfy | DegreesToRadians | False | refused:real | agree |
| dafny-synthesis_task_id_61.dfy | CountSubstringsWithSumOfDigitsEqualToLength | False | refused:as-cast | gap-name |
| dafny-synthesis_task_id_610.dfy | RemoveElement | False | refused:array | agree |
| dafny-synthesis_task_id_616.dfy | ElementWiseModulo | False | refused:array | agree |
| dafny-synthesis_task_id_618.dfy | ElementWiseDivide | False | refused:seq-return | agree |
| dafny-synthesis_task_id_62.dfy | FindSmallest | False | refused:lift-check-failed | gap-name |
| dafny-synthesis_task_id_622.dfy | FindMedian | False | refused:heap | gap-name |
| dafny-synthesis_task_id_623.dfy | PowerOfListElements | False | refused:seq-return | agree |
| dafny-synthesis_task_id_624.dfy | ToUppercase | False | refused:as-cast | gap-name |
| dafny-synthesis_task_id_625.dfy | SwapFirstAndLast | False | refused:zero-returns | agree |
| dafny-synthesis_task_id_626.dfy | AreaOfLargestTriangleInSemicircle | True | lifted | agree |
| dafny-synthesis_task_id_627.dfy | SmallestMissingNumber | False | refused:unbounded-quantifier | gap-name |
| dafny-synthesis_task_id_629.dfy | FindEvenNumbers | False | refused:div-mod | agree |
| dafny-synthesis_task_id_632.dfy | MoveZeroesToEnd | False | refused:zero-returns | agree |
| dafny-synthesis_task_id_632.dfy | swap | False | refused:zero-returns | agree |
| dafny-synthesis_task_id_637.dfy | IsBreakEven | True | lifted | agree |
| dafny-synthesis_task_id_641.dfy | NthNonagonalNumber | False | refused:div-mod | agree |
| dafny-synthesis_task_id_644.dfy | Reverse | False | refused:zero-returns | agree |
| dafny-synthesis_task_id_644.dfy | ReverseUptoK | False | refused:zero-returns | agree |
| dafny-synthesis_task_id_69.dfy | ContainsSequence | False | refused:nested-seq | agree |
| dafny-synthesis_task_id_70.dfy | AllSequencesEqualLength | False | refused:nested-seq | agree |
| dafny-synthesis_task_id_728.dfy | AddLists | False | refused:seq-return | agree |
| dafny-synthesis_task_id_732.dfy | ReplaceWithColon | False | refused:string-char | agree |
| dafny-synthesis_task_id_733.dfy | FindFirstOccurrence | False | refused:heap | gap-name |
| dafny-synthesis_task_id_741.dfy | AllCharactersSame | False | refused:string-char | agree |
| dafny-synthesis_task_id_743.dfy | RotateRight | False | refused:seq-return | agree |
| dafny-synthesis_task_id_750.dfy | AddTupleToList | False | refused:nested-seq | gap-name |
| dafny-synthesis_task_id_751.dfy | IsMinHeap | False | refused:heap | gap-name |
| dafny-synthesis_task_id_755.dfy | SecondSmallest | False | refused:seq-literal | agree |
| dafny-synthesis_task_id_759.dfy | IsDecimalWithTwoPrecision | False | refused:string-char | agree |
| dafny-synthesis_task_id_760.dfy | HasOnlyOneDistinctElement | False | refused:heap | gap-name |
| dafny-synthesis_task_id_762.dfy | IsMonthWith30Days | True | lifted | agree |
| dafny-synthesis_task_id_764.dfy | CountDigits | False | refused:as-cast | gap-name |
| dafny-synthesis_task_id_769.dfy | Difference | False | refused:seq-return | agree |
| dafny-synthesis_task_id_77.dfy | IsDivisibleBy11 | False | refused:div-mod | agree |
| dafny-synthesis_task_id_770.dfy | SumOfFourthPowerOfOddNumbers | False | refused:div-mod | agree |
| dafny-synthesis_task_id_775.dfy | IsOddAtIndexOdd | False | refused:div-mod | agree |
| dafny-synthesis_task_id_776.dfy | CountVowelNeighbors | False | refused:set | agree |
| dafny-synthesis_task_id_784.dfy | FirstEvenOddIndices | False | refused:div-mod | agree |
| dafny-synthesis_task_id_784.dfy | ProductEvenOdd | False | refused:div-mod | agree |
| dafny-synthesis_task_id_79.dfy | IsLengthOdd | False | refused:string-char | agree |
| dafny-synthesis_task_id_790.dfy | IsEvenAtIndexEven | False | refused:div-mod | agree |
| dafny-synthesis_task_id_792.dfy | CountLists | False | refused:nested-seq | agree |
| dafny-synthesis_task_id_793.dfy | LastPosition | False | refused:unbounded-quantifier | gap-name |
| dafny-synthesis_task_id_798.dfy | ArraySum | False | refused:heap | gap-name |
| dafny-synthesis_task_id_799.dfy | (file) | False | refused:parse-failure | gap-name |
| dafny-synthesis_task_id_8.dfy | SquareElements | False | refused:array | agree |
| dafny-synthesis_task_id_80.dfy | TetrahedralNumber | False | refused:div-mod | agree |
| dafny-synthesis_task_id_801.dfy | CountEqualNumbers | True | lifted | agree |
| dafny-synthesis_task_id_803.dfy | IsPerfectSquare | False | refused:unbounded-quantifier | agree |
| dafny-synthesis_task_id_804.dfy | IsProductEven | False | refused:div-mod | agree |
| dafny-synthesis_task_id_807.dfy | FindFirstOdd | False | refused:div-mod | agree |
| dafny-synthesis_task_id_808.dfy | ContainsK | False | refused:early-exit | agree |
| dafny-synthesis_task_id_809.dfy | IsSmaller | False | refused:early-exit | agree |
| dafny-synthesis_task_id_82.dfy | SphereVolume | False | refused:real | agree |
| dafny-synthesis_task_id_85.dfy | SphereSurfaceArea | False | refused:real | agree |
| dafny-synthesis_task_id_86.dfy | CenteredHexagonalNumber | True | lifted | agree |
| dafny-synthesis_task_id_89.dfy | ClosestSmaller | True | lifted | agree |
| dafny-synthesis_task_id_94.dfy | MinSecondValueFirst | False | refused:array | agree |
| dafny-synthesis_task_id_95.dfy | SmallestListLength | False | refused:nested-seq | agree |
| dafny-training_tmp_tmp_n2kixni_session1_training1.dfy | abs | False | lifted | lifter |
| dafny-training_tmp_tmp_n2kixni_session1_training1.dfy | max | False | lifted | lifter |
| dafny-training_tmp_tmp_n2kixni_session1_training1.dfy | ex1 | False | refused:zero-returns | agree |
| dafny-training_tmp_tmp_n2kixni_session1_training1.dfy | foo2 | False | refused:zero-returns | agree |
| dafny-training_tmp_tmp_n2kixni_session1_training1.dfy | find | False | refused:early-exit | agree |
| dafny-training_tmp_tmp_n2kixni_session1_training1.dfy | unique | False | refused:unbounded-quantifier | gap-name |
| dafny-workout_tmp_tmp0abkw6f8_starter_ex01.dfy | Max | True | lifted | agree |
| dafny-workout_tmp_tmp0abkw6f8_starter_ex02.dfy | Abs | True | lifted | agree |
| dafny-workout_tmp_tmp0abkw6f8_starter_ex03.dfy | Abs | False | lifted | lifter |
| dafny-workout_tmp_tmp0abkw6f8_starter_ex03.dfy | Abs2 | False | refused:real | agree |
| dafny-workout_tmp_tmp0abkw6f8_starter_ex09.dfy | ComputeFib | False | refused:early-exit | agree |
| dafny-workout_tmp_tmp0abkw6f8_starter_ex12.dfy | FindMax | False | lifted | undecided |
| dafny_examples_tmp_tmp8qotd4ez_leetcode_0001-two-sum.dfy | TwoSum | False | refused:tuple | agree |
| dafny_examples_tmp_tmp8qotd4ez_leetcode_0027-remove-element.dfy | RemoveElement | False | refused:array-mutation | agree |
| dafny_examples_tmp_tmp8qotd4ez_leetcode_0069-sqrt.dfy | mySqrt | False | refused:return-not-assigned-on-all-paths | gap-name |
| dafny_examples_tmp_tmp8qotd4ez_leetcode_0070-climbing-stairs.dfy | ClimbStairs | True | lifted | agree |
| dafny_examples_tmp_tmp8qotd4ez_leetcode_0277-find-the-celebrity.dfy | isCelebrityP | False | refused:bodyless-function | agree |
| dafny_examples_tmp_tmp8qotd4ez_leetcode_0277-find-the-celebrity.dfy | findCelebrity | False | refused:bodyless-function | agree |
| dafny_examples_tmp_tmp8qotd4ez_lib_math_DivMod.dfy | (file) | False | refused:no-method | gap-name |
| dafny_examples_tmp_tmp8qotd4ez_test_shuffle.dfy | random | False | refused:bodyless-method | agree |
| dafny_examples_tmp_tmp8qotd4ez_test_shuffle.dfy | swap | False | refused:zero-returns | agree |
| dafny_examples_tmp_tmp8qotd4ez_test_shuffle.dfy | getAllShuffledDataEntries | False | refused:array | agree |
| dafny_experiments_tmp_tmpz29_3_3i_circuit.dfy | (file) | False | refused:no-method | gap-name |
| dafny_misc_tmp_tmpg4vzlnm1_rosetta_code_factorial.dfy | IterativeFactorial | True | lifted | agree |
| dafny_misc_tmp_tmpg4vzlnm1_rosetta_code_fibonacci_sequence.dfy | (file) | False | refused:datatype | agree |
| dafny_projects_tmp_tmpjutqwjv4_tutorial_tutorial.dfy | ComputeFib | False | lifted | undecided |
| dafny_projects_tmp_tmpjutqwjv4_tutorial_tutorial.dfy | Find | False | refused:early-exit | agree |
| dafny_projects_tmp_tmpjutqwjv4_tutorial_tutorial.dfy | BinarySearch | False | refused:function-contract | gap-name |
| dafny_projects_tmp_tmpjutqwjv4_tutorial_tutorial.dfy | FindZero | False | refused:array | agree |
| dafny_tmp_tmp2ewu6s7x_ListReverse.dfy | (file) | False | refused:no-method | gap-name |
| dafny_tmp_tmp49a6ihvk_m4.dfy | (file) | False | refused:datatype | agree |
| dafny_tmp_tmp59p638nn_examples_GenericSelectionSort.dfy | (file) | False | refused:heap | agree |
| dafny_tmp_tmp59p638nn_examples_SelectionSort.dfy | (file) | False | refused:old | gap-name |
| dafny_tmp_tmp59p638nn_examples_derangement.dfy | (file) | False | refused:higher-order | agree |
| dafny_tmp_tmp59p638nn_examples_minmax2.dfy | (file) | False | refused:let-expression | gap-name |
| dafny_tmp_tmp59p638nn_examples_realExponent.dfy | pow | False | refused:bodyless-function | agree |
| eth2-dafny_tmp_tmpcrgexrgb_src_dafny_utils_SetHelpers.dfy | (file) | False | refused:no-method | gap-name |
| feup-mfes_tmp_tmp6_a1y5a5_examples_SelectionSort.dfy | selectionSort | False | refused:function-contract | gap-name |
| feup-mfes_tmp_tmp6_a1y5a5_examples_SelectionSort.dfy | findMin | False | refused:array | agree |
| formal-methods-in-software-engineering_tmp_tmpe7fjnek6_Labs2_gr2.dfy | (file) | False | refused:datatype | agree |
| formal-methods-in-software-engineering_tmp_tmpe7fjnek6_Labs2_hw1.dfy | (file) | False | refused:datatype | agree |
| formal-methods-in-software-engineering_tmp_tmpe7fjnek6_Labs4_gr2.dfy | HoareTripleReqEns | False | lifted | lifter |
| formal-methods-in-software-engineering_tmp_tmpe7fjnek6_Labs4_gr2.dfy | SqrSum1 | False | lifted | lifter |
| formal-methods-in-software-engineering_tmp_tmpe7fjnek6_Labs4_gr2.dfy | DivMod1 | False | refused:multi-return | agree |
| formal-verification_tmp_tmpoepcssay_strings3.dfy | isPrefix | False | refused:seq-slice | agree |
| formal-verification_tmp_tmpoepcssay_strings3.dfy | isSubstring | False | refused:seq-slice | agree |
| formal-verification_tmp_tmpoepcssay_strings3.dfy | haveCommonKSubstring | False | refused:seq-slice | agree |
| formal-verification_tmp_tmpoepcssay_strings3.dfy | maxCommonSubstringLength | False | refused:seq-slice | agree |
| formal_verication_dafny_tmp_tmpwgl2qz28_Challenges_ex1.dfy | PalVerify | False | refused:array | agree |
| formal_verication_dafny_tmp_tmpwgl2qz28_Challenges_ex2.dfy | Forbid42 | False | refused:div-mod | agree |
| formal_verication_dafny_tmp_tmpwgl2qz28_Challenges_ex2.dfy | Allow42 | False | refused:multi-return | agree |
| formal_verication_dafny_tmp_tmpwgl2qz28_Challenges_ex6.dfy | BullsCows | False | refused:unbounded-quantifier | gap-name |
| formal_verication_dafny_tmp_tmpwgl2qz28_Challenges_ex7.dfy | (file) | False | refused:datatype | agree |
| fv2020-tms_tmp_tmpnp85b47l_modeling_concurrency_safety.dfy | (file) | False | refused:datatype | agree |
| fv2020-tms_tmp_tmpnp85b47l_simple_tm.dfy | (file) | False | refused:no-method | gap-name |
| groupTheory_tmp_tmppmmxvu8h_assignment1.dfy | (file) | False | refused:resolve-failure | gap-name |
| groupTheory_tmp_tmppmmxvu8h_tutorial2.dfy | (file) | False | refused:no-method | gap-name |
| groupTheory_tmp_tmppmmxvu8h_yair_yair2.dfy | (file) | False | refused:no-method | gap-name |
| iron-sync_tmp_tmps49o3tyz_Impl_CommitterCommitModel.dfy | (file) | False | refused:no-method | gap-name |
| iron-sync_tmp_tmps49o3tyz_concurrency_docs_code_ShardedStateMachine.dfy | (file) | False | refused:no-method | gap-name |
| iron-sync_tmp_tmps49o3tyz_lib_Base_MapRemove.dfy | (file) | False | refused:no-method | gap-name |
| ironsync-osdi2023_tmp_tmpx80antoe_lib_Marshalling_Math.dfy | (file) | False | refused:no-method | gap-name |
| ironsync-osdi2023_tmp_tmpx80antoe_lib_Math_div_def.dfy | (file) | False | refused:no-method | gap-name |
| ironsync-osdi2023_tmp_tmpx80antoe_linear-dafny_Test_c++_arrays.dfy | returnANullArray | False | refused:array | agree |
| ironsync-osdi2023_tmp_tmpx80antoe_linear-dafny_Test_c++_arrays.dfy | returnANonNullArray | False | refused:array | agree |
| ironsync-osdi2023_tmp_tmpx80antoe_linear-dafny_Test_c++_arrays.dfy | LinearSearch | False | refused:array | agree |
| ironsync-osdi2023_tmp_tmpx80antoe_linear-dafny_Test_c++_maps.dfy | GenericMap | False | refused:multi-return | agree |
| ironsync-osdi2023_tmp_tmpx80antoe_linear-dafny_Test_c++_sets.dfy | (file) | False | refused:no-method | gap-name |
| ironsync-osdi2023_tmp_tmpx80antoe_linear-dafny_Test_git-issues_git-issue-1158.dfy | (file) | False | refused:no-method | gap-name |
| ironsync-osdi2023_tmp_tmpx80antoe_linear-dafny_Test_git-issues_git-issue-283.dfy | (file) | False | refused:heap | agree |
| ironsync-osdi2023_tmp_tmpx80antoe_linear-dafny_Test_git-issues_git-issue-506.dfy | (file) | False | refused:no-method | gap-name |
| ironsync-osdi2023_tmp_tmpx80antoe_linear-dafny_Test_git-issues_git-issue-975.dfy | (file) | False | refused:let-expression | gap-name |
| ironsync-osdi2023_tmp_tmpx80antoe_linear-dafny_docs_DafnyRef_examples_Example-Old.dfy | (file) | False | refused:no-method | gap-name |
| ironsync-osdi2023_tmp_tmpx80antoe_linear-dafny_docs_DafnyRef_examples_Example-Old2.dfy | (file) | False | refused:no-method | gap-name |
| ironsync-osdi2023_tmp_tmpx80antoe_linear-dafny_docs_DafnyRef_examples_Example-Old3.dfy | (file) | False | refused:no-method | gap-name |
| laboratory_tmp_tmps8ws6mu2_dafny-tutorial_exercise12.dfy | FindMax | False | lifted | undecided |
| laboratory_tmp_tmps8ws6mu2_dafny-tutorial_exercise9.dfy | ComputeFib | True | lifted | agree |
| lets-prove-blocking-queue_tmp_tmptd_aws1k_dafny_prod-cons.dfy | (file) | False | refused:no-method | gap-name |
| libraries_tmp_tmp9gegwhqj_examples_MutableMap_MutableMapDafny.dfy | (file) | False | refused:no-method | gap-name |
| llm-verified-eval_tmp_tmpd2deqn_i_dafny_0.dfy | has_close_elements | False | refused:nested-seq | agree |
| llm-verified-eval_tmp_tmpd2deqn_i_dafny_160.dfy | (file) | False | refused:datatype | agree |
| llm-verified-eval_tmp_tmpd2deqn_i_dafny_161.dfy | Reverse | False | refused:nested-seq | agree |
| llm-verified-eval_tmp_tmpd2deqn_i_dafny_161.dfy | solve | False | refused:div-mod | agree |
| llm-verified-eval_tmp_tmpd2deqn_i_dafny_3.dfy | below_zero | False | refused:seq-slice | agree |
| llm-verified-eval_tmp_tmpd2deqn_i_dafny_5.dfy | intersperse | False | refused:seq-return | agree |
| llm-verified-eval_tmp_tmpd2deqn_i_dafny_9.dfy | max | False | refused:seq-literal | agree |
| llm-verified-eval_tmp_tmpd2deqn_i_dafny_9.dfy | rolling_max | False | refused:seq-return | agree |
| metodosFormais_tmp_tmp4q2kmya4_T1-MetodosFormais_examples_ex1.dfy | buscar | False | refused:early-exit | agree |
| metodosFormais_tmp_tmp4q2kmya4_T1-MetodosFormais_examples_somatoriov2.dfy | somatorio | False | refused:function-contract | gap-name |
| nitwit_tmp_tmplm098gxz_nit.dfy | nit_increment | False | refused:multi-return | agree |
| nitwit_tmp_tmplm098gxz_nit.dfy | max_nit | False | lifted | lifter |
| nitwit_tmp_tmplm098gxz_nit.dfy | nit_flip | False | refused:calls-other-method | gap-name |
| nitwit_tmp_tmplm098gxz_nit.dfy | nit_add | False | refused:multi-return | agree |
| nitwit_tmp_tmplm098gxz_nit.dfy | nit_add_three | False | refused:multi-return | agree |
| nitwit_tmp_tmplm098gxz_nit.dfy | bibble_add | False | refused:unbounded-quantifier | gap-name |
| nitwit_tmp_tmplm098gxz_nit.dfy | bibble_increment | False | refused:unbounded-quantifier | gap-name |
| nitwit_tmp_tmplm098gxz_nit.dfy | bibble_flip | False | refused:unbounded-quantifier | gap-name |
| nitwit_tmp_tmplm098gxz_nit.dfy | n_complement | False | refused:unbounded-quantifier | gap-name |
| paxos_proof_tmp_tmpxpmiksmt_triggers.dfy | (file) | False | refused:no-method | gap-name |
| protocol-verification-fa2023_tmp_tmpw6hy3mjp_demos_ch01_fast_exp.dfy | fast_exp | False | refused:seq-literal | agree |
| protocol-verification-fa2023_tmp_tmpw6hy3mjp_demos_ch03_nim_v3.dfy | (file) | False | refused:let-expression | gap-name |
| protocol-verification-fa2023_tmp_tmpw6hy3mjp_demos_ch04_inductive_chain.dfy | (file) | False | refused:no-method | gap-name |
| protocol-verification-fa2023_tmp_tmpw6hy3mjp_demos_ch04_invariant_proof.dfy | (file) | False | refused:no-method | gap-name |
| protocol-verification-fa2023_tmp_tmpw6hy3mjp_demos_ch04_leader_election.dfy | (file) | False | refused:let-expression | gap-name |
| protocol-verification-fa2023_tmp_tmpw6hy3mjp_demos_ch04_toy_consensus.dfy | (file) | False | refused:let-expression | gap-name |
| protocol-verification-fa2023_tmp_tmpw6hy3mjp_demos_ch06_refinement_proof.dfy | (file) | False | refused:let-expression | gap-name |
| protocol-verification-fa2023_tmp_tmpw6hy3mjp_demos_dafny-internals_02-triggers_triggers2.dfy | (file) | False | refused:no-method | gap-name |
| protocol-verification-fa2023_tmp_tmpw6hy3mjp_demos_dafny-internals_03-encoding_lemma_call.dfy | (file) | False | refused:no-method | gap-name |
| protocol-verification-fa2023_tmp_tmpw6hy3mjp_demos_dafny-internals_03-encoding_pair.dfy | (file) | False | refused:no-method | gap-name |
| protocol-verification-fa2023_tmp_tmpw6hy3mjp_exercises_chapter04-invariants_ch03exercise03.dfy | (file) | False | refused:datatype | agree |
| pucrs-metodos-formais-t1_tmp_tmp7gvq3cw4_fila.dfy | (file) | False | refused:heap | agree |
| repo-8967-Ironclad_tmp_tmp4q25en_1_ironclad-apps_src_Dafny_Libraries_Util_seqs_simple.dfy | (file) | False | refused:no-method | gap-name |
| sat_dfy_tmp_tmpfcyj8am9_dfy_Seq.dfy | (file) | False | refused:no-method | gap-name |
| se2011_tmp_tmp71eb82zt_ass1_ex4.dfy | Eval | True | lifted | agree |
| se2011_tmp_tmp71eb82zt_ass1_ex6.dfy | Ceiling7 | False | refused:div-mod | agree |
| se2011_tmp_tmp71eb82zt_ass2_ex2.dfy | (file) | False | refused:no-method | gap-name |
| software-specification-p1_tmp_tmpz9x6mpxb_BoilerPlate_Ex1.dfy | (file) | False | refused:datatype | agree |
| software_analysis_tmp_tmpmt6bo9sf_ss.dfy | find_min_index | False | lifted | undecided |
| software_analysis_tmp_tmpmt6bo9sf_ss.dfy | selection_sort | False | refused:unbounded-quantifier | gap-name |
| specTesting_tmp_tmpueam35lx_examples_binary_search_binary_search_specs.dfy | (file) | False | refused:no-method | gap-name |
| specTesting_tmp_tmpueam35lx_examples_increment_decrement_spec.dfy | (file) | False | refused:no-method | gap-name |
| specTesting_tmp_tmpueam35lx_examples_max_max.dfy | (file) | False | refused:no-method | gap-name |
| specTesting_tmp_tmpueam35lx_examples_sort_sort.dfy | quickSort | False | refused:bodyless-method | agree |
| stunning-palm-tree_tmp_tmpr84c2iwh_ch1.dfy | Triple | False | lifted | lifter |
| stunning-palm-tree_tmp_tmpr84c2iwh_ch1.dfy | MinUnderSpec | False | lifted | lifter |
| stunning-palm-tree_tmp_tmpr84c2iwh_ch1.dfy | Min | False | lifted | lifter |
| stunning-palm-tree_tmp_tmpr84c2iwh_ch1.dfy | MaxSum | False | refused:bodyless-method | agree |
| stunning-palm-tree_tmp_tmpr84c2iwh_ch1.dfy | ReconstructFromMaxSum | False | refused:multi-return | agree |
| stunning-palm-tree_tmp_tmpr84c2iwh_ch1.dfy | Triple' | False | refused:div-mod | agree |
| stunning-palm-tree_tmp_tmpr84c2iwh_ch10.dfy | (file) | False | refused:no-method | gap-name |
| stunning-palm-tree_tmp_tmpr84c2iwh_ch5.dfy | (file) | False | refused:datatype | agree |
| stunning-palm-tree_tmp_tmpr84c2iwh_ch8.dfy | (file) | False | refused:datatype | agree |
| summer-school-2020_tmp_tmpn8nf7zf0_chapter01_solutions_exercise04_solution.dfy | (file) | False | refused:no-method | gap-name |
| summer-school-2020_tmp_tmpn8nf7zf0_chapter01_solutions_exercise11_solution.dfy | (file) | False | refused:no-method | gap-name |
| summer-school-2020_tmp_tmpn8nf7zf0_chapter02_solutions_exercise01_solution.dfy | (file) | False | refused:no-method | gap-name |
| summer-school-2020_tmp_tmpn8nf7zf0_chapter02_solutions_exercise02_solution.dfy | test_prime | False | refused:div-mod | agree |
| summer-school-2020_tmp_tmpn8nf7zf0_chapter02_solutions_exercise03_solution.dfy | merge_sort | False | refused:unbounded-quantifier | gap-name |
| summer-school-2020_tmp_tmpn8nf7zf0_chapter02_solutions_exercise03_solution.dfy | merge | False | refused:unbounded-quantifier | gap-name |
| t1_MF_tmp_tmpi_sqie4j_exemplos_classes_parte1_contadorV1b.dfy | (file) | False | refused:heap | agree |
| t1_MF_tmp_tmpi_sqie4j_exemplos_colecoes_arrays_ex4.dfy | Somatorio | False | refused:function-contract | gap-name |
| t1_MF_tmp_tmpi_sqie4j_exemplos_colecoes_arrays_ex5.dfy | Busca | False | refused:array | agree |
| t1_MF_tmp_tmpi_sqie4j_exemplos_colecoes_conjuntos_ex5.dfy | (file) | False | refused:no-method | gap-name |
| t1_MF_tmp_tmpi_sqie4j_exemplos_colecoes_sequences_ex3.dfy | Delete | False | refused:zero-returns | agree |
| t1_MF_tmp_tmpi_sqie4j_exemplos_introducao_ex4.dfy | Fatorial | True | lifted | agree |
| tangent-finder_tmp_tmpgyzf44ve_circles.dfy | Tangent | False | refused:unbounded-quantifier | gap-name |
| test-generation-examples_tmp_tmptwyqofrp_IntegerSet_dafny_IntegerSet.dfy | (file) | False | refused:heap | agree |
| test-generation-examples_tmp_tmptwyqofrp_IntegerSet_dafny_Utils.dfy | (file) | False | refused:no-method | gap-name |
| test-generation-examples_tmp_tmptwyqofrp_ParamTests_dafny_Utils.dfy | (file) | False | refused:no-method | gap-name |
| test-generation-examples_tmp_tmptwyqofrp_RussianMultiplication_dafny_RussianMultiplication.dfy | (file) | False | refused:no-method | gap-name |
| type-definition_tmp_tmp71kdzz3p_final.dfy | (file) | False | refused:datatype | agree |
| veri-sparse_tmp_tmp15fywna6_dafny_concurrent_poc_6.dfy | (file) | False | refused:heap | agree |
| veri-sparse_tmp_tmp15fywna6_dafny_dspmspv.dfy | DSpMSpV | False | refused:function-contract | gap-name |
| veri-sparse_tmp_tmp15fywna6_dafny_spmv.dfy | SpMV | False | refused:unbounded-quantifier | gap-name |
| veri-titan_tmp_tmpbg2iy0kf_spec_crypto_fntt512.dfy | (file) | False | refused:no-method | gap-name |
| veribetrkv-osdi2020_tmp_tmpra431m8q_docker-hdd_src_veribetrkv-linear_lib_Base_SetBijectivity.dfy | (file) | False | refused:no-method | gap-name |
| veribetrkv-osdi2020_tmp_tmpra431m8q_docker-hdd_src_veribetrkv-linear_lib_Base_Sets.dfy | (file) | False | refused:no-method | gap-name |
| verification-class_tmp_tmpz9ik148s_2022_chapter05-distributed-state-machines_exercises_UtilitiesLibrary.dfy | (file) | False | refused:no-method | gap-name |
| verified-isort_tmp_tmp7hhb8ei__dafny_isort.dfy | Isort | False | refused:zero-returns | agree |
| verified-using-dafny_tmp_tmp7jatpjyn_longestZero.dfy | longestZero | False | refused:multi-return | agree |
| vfag_tmp_tmpc29dxm1j_Verificacion_torneo.dfy | torneo | False | refused:multi-return | agree |
| vfag_tmp_tmpc29dxm1j_mergesort.dfy | (file) | False | refused:no-method | gap-name |
| vfag_tmp_tmpc29dxm1j_sumar_componentes.dfy | suma_componentes | False | refused:array | agree |
| vmware-verification-2023_tmp_tmpoou5u54i_demos_leader_election.dfy | (file) | False | refused:let-expression | gap-name |
