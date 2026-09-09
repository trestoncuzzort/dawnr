# t coverage census: DafnyBench (785 programs)

What this corpus needs that t does not have, program by program, and
which gate opens the most programs. Lexical census, no kernel run; the
in-fragment count says a program's constructs fit SYNTAX.md, not that
seven kernels verify its t rendering. Method and detectors at the end.

## Headline

- programs: 785; with a method carrying its own ensures (gradable): 643
- in t's fragment today: **174** of 643 gradable (27.1%)
- gradable programs blocked by exactly one gap: 140

## Gaps, by programs that need them

| gap | programs | sole blocker for (gradable) | meaning |
|---|---|---|---|
| zero-returns | 215 | 25 | a method with no return value (t returns exactly one) |
| multi-method | 212 | 14 | more than one method (Main, and the method of function method, excluded) |
| seq-slice | 164 | 17 | slicing s[a..b] |
| set | 130 | 3 | set, iset, multiset, set comprehension or set literal |
| seq-literal | 113 | 1 | sequence literal [..] in an expression |
| string-char | 94 | 7 | string or char type |
| generics | 80 | 1 | type parameters |
| array | 79 | 4 | array2/array3, array?<..> (nullable), or a non-int/non-nat element type |
| seq-return | 78 | 0 | sequence-valued return of a method or a function |
| heap | 78 | 0 | classes, object allocation, this |
| multi-return | 74 | 27 | several return values |
| nested-seq | 74 | 4 | a nested seq or array, or a seq of non-int elements |
| datatype | 69 | 1 | algebraic datatypes and match |
| array-mutation | 49 | 0 | array mutation decision 22 does not map: more than one mutated array, multiset over a mutated array's slice, or a modifies clause naming anything but the one array |
| unbounded-quantifier | 49 | 1 | quantifier without an int range |
| module | 43 | 1 | modules and imports |
| higher-order | 40 | 3 | lambdas or function types |
| bodyless-function | 40 | 1 | an uninterpreted function or predicate: a declaration with no body, constrained only by axioms |
| early-exit | 38 | 16 | a break or continue statement in a method body |
| type-decl | 33 | 0 | newtype, type synonyms, subset types |
| real | 32 | 9 | real numbers |
| map | 31 | 0 | map, imap, map comprehension or map literal |
| io | 24 | 0 | print or expect |
| bodyless-method | 24 | 0 | a method declared without a body |
| nondet | 22 | 3 | nondeterministic choice: havoc x := *, if *, while *, guarded alternatives if { case } |
| such-that-exec | 21 | 0 | assign-such-that :| in executable code (nondeterministic choice) |
| tuple | 19 | 1 | tuples |
| seq-update | 15 | 0 | functional update s[i := v] |
| bitvector | 6 | 1 | bit vectors or bitwise operators |
| decreases-star | 6 | 0 | decreases * (a loop or call allowed not to terminate) |
| extreme-predicate | 5 | 0 | least / greatest predicate: an inductive or coinductive definition, not a well-founded recursion (least and greatest LEMMAS stay hints) |
| mutual-recursion | 4 | 0 | spec functions that call each other (t allows self-calls and calls to earlier functions) |
| seq-comprehension | 3 | 0 | seq(n, i => e) |
| char-arith | 3 | 0 | char arithmetic |
| iterator | 2 | 0 | iterators |
| function-method | 1 | 0 | compiled functions |

## Greedy gate order (open the gate that unlocks the most programs)

| step | gate | newly unlocked | cumulative in fragment | of gradable |
|---|---|---|---|---|
| 1 | multi-return | 27 | 201 | 31.3% |
| 2 | zero-returns | 25 | 226 | 35.1% |
| 3 | multi-method | 33 | 259 | 40.3% |
| 4 | seq-slice | 25 | 284 | 44.2% |
| 5 | early-exit | 19 | 303 | 47.1% |
| 6 | string-char | 18 | 321 | 49.9% |
| 7 | array | 28 | 349 | 54.3% |
| 8 | real | 16 | 365 | 56.8% |
| 9 | set | 15 | 380 | 59.1% |
| 10 | array-mutation | 21 | 401 | 62.4% |
| 11 | seq-literal | 13 | 414 | 64.4% |
| 12 | seq-return | 35 | 449 | 69.8% |
| 13 | nested-seq | 24 | 473 | 73.6% |
| 14 | heap | 15 | 488 | 75.9% |
| 15 | generics | 13 | 501 | 77.9% |
| 16 | higher-order | 12 | 513 | 79.8% |
| 17 | nondet | 11 | 524 | 81.5% |
| 18 | bodyless-method | 11 | 535 | 83.2% |
| 19 | unbounded-quantifier | 10 | 545 | 84.8% |
| 20 | datatype | 12 | 557 | 86.6% |
| 21 | io | 10 | 567 | 88.2% |
| 22 | seq-update | 8 | 575 | 89.4% |
| 23 | bodyless-function | 8 | 583 | 90.7% |
| 24 | such-that-exec | 8 | 591 | 91.9% |
| 25 | module | 9 | 600 | 93.3% |
| 26 | map | 7 | 607 | 94.4% |
| 27 | tuple | 10 | 617 | 96.0% |
| 28 | type-decl | 12 | 629 | 97.8% |
| 29 | decreases-star | 5 | 634 | 98.6% |
| 30 | bitvector | 4 | 638 | 99.2% |
| 31 | char-arith | 3 | 641 | 99.7% |
| 32 | seq-comprehension | 1 | 642 | 99.8% |
| 33 | iterator | 1 | 643 | 100.0% |


### The same order on the MBPP-DFY family alone (164 gradable, the LLM-shaped subset)

| step | gate | newly unlocked | cumulative | of gradable |
|---|---|---|---|---|
| 1 | early-exit | 16 | 72 | 43.9% |
| 2 | string-char | 10 | 82 | 50.0% |
| 3 | real | 9 | 91 | 55.5% |
| 4 | set | 6 | 97 | 59.1% |
| 5 | nested-seq | 6 | 103 | 62.8% |
| 6 | seq-literal | 4 | 107 | 65.2% |
| 7 | seq-return | 23 | 130 | 79.3% |
| 8 | seq-slice | 15 | 145 | 88.4% |
| 9 | multi-return | 4 | 149 | 90.9% |
| 10 | char-arith | 3 | 152 | 92.7% |
| 11 | array | 2 | 154 | 93.9% |
| 12 | zero-returns | 2 | 156 | 95.1% |
| 13 | multi-method | 2 | 158 | 96.3% |
| 14 | bitvector | 2 | 160 | 97.6% |
| 15 | array-mutation | 1 | 161 | 98.2% |
| 16 | unbounded-quantifier | 1 | 162 | 98.8% |
| 17 | tuple | 1 | 163 | 99.4% |
| 18 | higher-order | 0 | 163 | 99.4% |
| 19 | seq-comprehension | 1 | 164 | 100.0% |

A step with 0 newly unlocked is a gate that unlocks nothing alone but
is the most frequent remaining gap; the programs it belongs to need
more than one gate.

## By family

| family | programs | gradable | in fragment |
|---|---|---|---|
| MBPP-DFY (dafny-synthesis) | 164 | 164 | 56 |
| GitHub (Dafny) | 76 | 72 | 19 |
| GitHub (Program-Verification-Dataset) | 65 | 48 | 4 |
| Clover | 62 | 62 | 19 |
| GitHub (dafny-language-server) | 43 | 17 | 2 |
| GitHub (Dafny-Exercises) | 21 | 20 | 2 |
| GitHub (dafny) | 18 | 14 | 3 |
| GitHub (SENG) | 14 | 11 | 2 |
| GitHub (dafny-exercise) | 12 | 11 | 3 |
| GitHub (ironsync-osdi) | 12 | 3 | 0 |
| GitHub (dafl) | 11 | 5 | 3 |
| GitHub (protocol-verification-fa) | 11 | 1 | 0 |
| GitHub (Metodos) | 10 | 9 | 8 |
| GitHub (Final-Project-Dafny) | 9 | 8 | 1 |
| GitHub (Software-Verification) | 9 | 9 | 2 |
| GitHub (DafnyProjects) | 8 | 7 | 0 |
| GitHub (Prog-Fun-Solutions) | 8 | 8 | 7 |
| GitHub (Programmverifikation-und-synthese) | 7 | 7 | 2 |
| GitHub (cs245-verification) | 7 | 6 | 4 |
| GitHub (dafny-duck) | 7 | 6 | 1 |
| GitHub (Software-building-and-verification-Projects) | 6 | 5 | 0 |
| GitHub (Workshop) | 6 | 6 | 4 |
| GitHub (llm-verified-eval) | 6 | 5 | 0 |
| GitHub (t) | 6 | 5 | 2 |
| GitHub (MFES) | 5 | 5 | 3 |
| GitHub (MIEIC) | 5 | 5 | 2 |
| GitHub (dafny-workout) | 5 | 5 | 4 |
| GitHub (summer-school-) | 5 | 2 | 1 |
| GitHub (CVS-Projto) | 4 | 2 | 0 |
| GitHub (DafnyPrograms) | 4 | 4 | 0 |
| GitHub (FMSE-2022-) | 4 | 1 | 0 |
| GitHub (FlexWeek) | 4 | 4 | 1 |
| GitHub (HATRA-2022-Paper) | 4 | 4 | 2 |
| GitHub (dafny-programs) | 4 | 4 | 2 |
| GitHub (formal) | 4 | 4 | 0 |
| GitHub (specTesting) | 4 | 1 | 0 |
| GitHub (stunning-palm-tree) | 4 | 1 | 0 |
| GitHub (test-generation-examples) | 4 | 3 | 0 |
| GitHub (AssertivePrograming) | 3 | 3 | 0 |
| GitHub (Correctness) | 3 | 3 | 0 |
| GitHub (Formal-methods-of-software-development) | 3 | 1 | 0 |
| GitHub (M) | 3 | 3 | 3 |
| GitHub (assertive-programming-assignment-) | 3 | 3 | 0 |
| GitHub (cs) | 3 | 3 | 1 |
| GitHub (dafleet) | 3 | 3 | 0 |
| GitHub (formal-methods-in-software-engineering) | 3 | 1 | 0 |
| GitHub (groupTheory) | 3 | 0 | 0 |
| GitHub (iron-sync) | 3 | 1 | 0 |
| GitHub (se) | 3 | 2 | 1 |
| GitHub (veri-sparse) | 3 | 3 | 0 |
| GitHub (vfag) | 3 | 2 | 0 |
| GitHub (703FinalProject) | 2 | 0 | 0 |
| GitHub (CS) | 2 | 1 | 0 |
| GitHub (CVS-handout) | 2 | 2 | 0 |
| GitHub (Dafny-Practice) | 2 | 2 | 0 |
| GitHub (Dafny-VMC) | 2 | 0 | 0 |
| GitHub (DafnyExercises) | 2 | 1 | 1 |
| GitHub (Formal-Methods-Project) | 2 | 0 | 0 |
| GitHub (Formal-Verification) | 2 | 2 | 0 |
| GitHub (FormalMethods) | 2 | 2 | 2 |
| GitHub (Formal) | 2 | 2 | 0 |
| GitHub (MFS) | 2 | 2 | 0 |
| GitHub (TFG) | 2 | 2 | 1 |
| GitHub (dafny-exercises) | 2 | 2 | 0 |
| GitHub (dafny-learn) | 2 | 2 | 0 |
| GitHub (fv2020-tms) | 2 | 2 | 0 |
| GitHub (laboratory) | 2 | 2 | 2 |
| GitHub (metodosFormais) | 2 | 2 | 2 |
| GitHub (veribetrkv-osdi) | 2 | 0 | 0 |
| GitHub (630-dafny) | 1 | 1 | 0 |
| GitHub (BPTree-verif) | 1 | 1 | 0 |
| GitHub (BelowZero.dfy) | 1 | 1 | 0 |
| GitHub (BinaryAddition.dfy) | 1 | 1 | 0 |
| GitHub (BinarySearchTree) | 1 | 1 | 0 |
| GitHub (CO3408-Advanced-Software-Modelling-Assignment-2022-23-Part-2-A-Specification-Spectacular) | 1 | 1 | 0 |
| GitHub (CS494-final-project) | 1 | 1 | 0 |
| GitHub (CSC8204-Dafny) | 1 | 0 | 0 |
| GitHub (CSU55004---Formal-Verification) | 1 | 0 | 0 |
| GitHub (Dafny-Grind) | 1 | 1 | 0 |
| GitHub (Dafny-Projects) | 1 | 1 | 0 |
| GitHub (Dafny-demo) | 1 | 1 | 0 |
| GitHub (Dafny-experiences) | 1 | 1 | 1 |
| GitHub (Dafny-programs) | 1 | 1 | 0 |
| GitHub (Formal-Verification-Project) | 1 | 1 | 0 |
| GitHub (Invoker) | 1 | 0 | 0 |
| GitHub (MFDS) | 1 | 0 | 0 |
| GitHub (ProjectosCVS) | 1 | 1 | 0 |
| GitHub (QS) | 1 | 1 | 0 |
| GitHub (RollingMax.dfy) | 1 | 1 | 0 |
| GitHub (SiLemma) | 1 | 0 | 0 |
| GitHub (Simulink-To) | 1 | 1 | 0 |
| GitHub (Trab1-Metodos-Formais) | 1 | 1 | 0 |
| GitHub (VerifiedMergeSortDafny) | 1 | 1 | 0 |
| GitHub (WrappedEther.dfy) | 1 | 0 | 0 |
| GitHub (bbfny) | 1 | 1 | 0 |
| GitHub (circular-queue-implemetation) | 1 | 1 | 0 |
| GitHub (cmsc) | 1 | 1 | 0 |
| GitHub (dafny-aoc-) | 1 | 0 | 0 |
| GitHub (dafny-mini-project) | 1 | 1 | 0 |
| GitHub (dafny-rope) | 1 | 1 | 0 |
| GitHub (dafny-sandbox) | 1 | 0 | 0 |
| GitHub (dafny-training) | 1 | 1 | 0 |
| GitHub (eth2-dafny) | 1 | 0 | 0 |
| GitHub (feup-mfes) | 1 | 1 | 0 |
| GitHub (formal-verification) | 1 | 1 | 0 |
| GitHub (lets-prove-blocking-queue) | 1 | 1 | 0 |
| GitHub (libraries) | 1 | 1 | 0 |
| GitHub (nitwit) | 1 | 1 | 0 |
| GitHub (paxos) | 1 | 0 | 0 |
| GitHub (pucrs-metodos-formais-t) | 1 | 1 | 0 |
| GitHub (repo-8967-Ironclad) | 1 | 0 | 0 |
| GitHub (sat) | 1 | 0 | 0 |
| GitHub (software-specification-p) | 1 | 0 | 0 |
| GitHub (software) | 1 | 1 | 0 |
| GitHub (tangent-finder) | 1 | 1 | 1 |
| GitHub (type-definition) | 1 | 0 | 0 |
| GitHub (veri-titan) | 1 | 0 | 0 |
| GitHub (verification-class) | 1 | 0 | 0 |
| GitHub (verified-isort) | 1 | 1 | 0 |
| GitHub (verified-using-dafny) | 1 | 1 | 0 |
| GitHub (vmware-verification-) | 1 | 0 | 0 |

## Burdens (expressible at a translation cost)

| burden | programs | meaning |
|---|---|---|
| spec-only-quantifier | 432 | quantifiers (bounded ones are in t) |
| untyped-var | 412 | var without a type (t declares every type) |
| function-or-predicate | 379 | pure functions, as spec_funs when first-order over int and seq |
| while-no-decreases | 274 | a loop without its decreases (t requires one) |
| array-as-seq | 249 | array<int>/array<nat> (one dimension): read-only, mutated in place under modifies, or allocated and filled -- lifts to seq (decision 1, decision 22) |
| nat | 209 | nat, as int with a >= 0 clause |
| frame-clause | 192 | modifies / reads (array frames when no class is present) |
| no-if-no-loop | 192 | straight-line body: the twin ladder has only its extensional operators to try |
| if-no-else | 167 | if without else |
| seq-membership | 133 | in / !in (a bounded exists over a seq; set and map membership are their own gaps) |
| trailing-return | 125 | a return as the last statement (assign the result instead) |
| early-return | 107 | a return that is not in tail position of a method body (lifts to t's early-exit `return` statement) |
| main-harness | 105 | a Main test harness (stripped before tagging) |
| for-loop | 100 | for loop (a while with a bound) |
| parallel-assign | 88 | x, y := a, b (sequenced through a temporary) |
| iff | 77 | <==> (== on bools) |
| as-cast | 15 | as int / as nat casts |

## Hints (proof scaffolding a kernel may need; t has none)

| hint | programs | meaning |
|---|---|---|
| assert | 315 | assert statements |
| lemma | 151 | lemmas |
| ghost | 116 | ghost code |
| old | 110 | old() / old@L() (two-state; heap or array frames) |
| attribute | 73 | attributes |
| ghost-var | 62 | ghost variables |
| calc | 44 | calc proofs |
| assign-such-that | 34 | assign-such-that in a lemma, a function or on a ghost variable (the executable one is the such-that-exec gap) |
| forall-statement | 32 | forall statements |
| assume | 28 | assume (unsound as a hint; refused by every t adapter) |
| assert-by | 22 | assert ... by { } |
| reveal-opaque | 17 | reveal / opaque |

## In fragment today

- Clover_abs.dfy
- Clover_array_product.dfy
- Clover_array_sum.dfy
- Clover_avg.dfy
- Clover_binary_search.dfy
- Clover_cal_sum.dfy
- Clover_find.dfy
- Clover_integer_square_root.dfy
- Clover_is_even.dfy
- Clover_linear_search1.dfy
- Clover_linear_search2.dfy
- Clover_max_array.dfy
- Clover_min_array.dfy
- Clover_min_of_two.dfy
- Clover_return_seven.dfy
- Clover_rotate.dfy
- Clover_triple.dfy
- Clover_triple3.dfy
- Clover_triple4.dfy
- Dafny-Exercises_tmp_tmpjm75muf__Session10Exercises_ExerciseBarrier.dfy
- Dafny-Exercises_tmp_tmpjm75muf__Session4Exercises_ExercisefirstZero.dfy
- Dafny-experiences_tmp_tmp150sm9qy_dafny_started_tutorial_dafny_tutorial_array.dfy
- DafnyExercises_tmp_tmpd6qyevja_Part1_Q1.dfy
- Dafny_Programs_tmp_tmp99966ew4_binary_search.dfy
- Dafny_Programs_tmp_tmp99966ew4_lemma.dfy
- Dafny_Verify_tmp_tmphq7j0row_AI_agent_verify_examples_ComputePower.dfy
- Dafny_Verify_tmp_tmphq7j0row_AI_agent_verify_examples_Cube.dfy
- Dafny_Verify_tmp_tmphq7j0row_Fine_Tune_Examples_50_examples_BinarySearch.dfy
- Dafny_Verify_tmp_tmphq7j0row_Fine_Tune_Examples_50_examples_SumArray.dfy
- Dafny_Verify_tmp_tmphq7j0row_Fine_Tune_Examples_normal_data_completion_MaxPerdV2.dfy
- Dafny_Verify_tmp_tmphq7j0row_Generated_Code_15.dfy
- Dafny_Verify_tmp_tmphq7j0row_Generated_Code_ComputePower.dfy
- Dafny_Verify_tmp_tmphq7j0row_Generated_Code_Count.dfy
- Dafny_Verify_tmp_tmphq7j0row_Generated_Code_Minimum.dfy
- Dafny_Verify_tmp_tmphq7j0row_Generated_Code_Mult.dfy
- Dafny_Verify_tmp_tmphq7j0row_dataset_C_convert_examples_15.dfy
- Dafny_Verify_tmp_tmphq7j0row_dataset_bql_exampls_Min.dfy
- Dafny_Verify_tmp_tmphq7j0row_dataset_bql_exampls_SmallNum.dfy
- Dafny_Verify_tmp_tmphq7j0row_dataset_bql_exampls_Square.dfy
- Dafny_Verify_tmp_tmphq7j0row_dataset_error_data_real_error_IsEven_success_1.dfy
- Dafny_tmp_tmp0wu8wmfr_tests_SumIntsLoop.dfy
- Dafny_tmp_tmpmvs2dmry_SlowMax.dfy
- Final-Project-Dafny_tmp_tmpmcywuqox_Attempts_Exercise6_Binary_Search.dfy
- FlexWeek_tmp_tmpc_tfdj_3_ex2.dfy
- FormalMethods_tmp_tmpvda2r3_o_dafny_Invariants_ex1.dfy
- FormalMethods_tmp_tmpvda2r3_o_dafny_Invariants_ex2.dfy
- HATRA-2022-Paper_tmp_tmp5texxy8l_copilot_verification_Binary Search_binary_search.dfy
- HATRA-2022-Paper_tmp_tmp5texxy8l_copilot_verification_Largest Sum_largest_sum.dfy
- M2_tmp_tmp2laaavvl_Software Verification_Exercices_Exo4-CountAndReturn.dfy
- M2_tmp_tmp2laaavvl_Software Verification_Exercices_Exo7-ComputeSum.dfy
- M2_tmp_tmp2laaavvl_Software Verification_Exercices_Exo9-Carre.dfy
- MFES_2021_tmp_tmpuljn8zd9_Exams_Special_Exam_03_2020_4_CatalanNumbers.dfy
- MFES_2021_tmp_tmpuljn8zd9_FCUL_Exercises_10_find.dfy
- MFES_2021_tmp_tmpuljn8zd9_FCUL_Exercises_8_sum.dfy
- MIEIC_mfes_tmp_tmpq3ho7nve_exams_appeal_20_p4.dfy
- MIEIC_mfes_tmp_tmpq3ho7nve_exams_mt2_19_p4.dfy
- Metodos_Formais_tmp_tmpbez22nnn_Aula_2_ex1.dfy
- Metodos_Formais_tmp_tmpbez22nnn_Aula_2_ex2.dfy
- Metodos_Formais_tmp_tmpql2hwcsh_Arrays_explicacao.dfy
- Metodos_Formais_tmp_tmpql2hwcsh_Arrays_somatorioArray.dfy
- Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_fatorial2.dfy
- Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_fibonacci.dfy
- Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_multiplicador.dfy
- Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_potencia.dfy
- Prog-Fun-Solutions_tmp_tmp7_gmnz5f_extra_mod.dfy
- Prog-Fun-Solutions_tmp_tmp7_gmnz5f_extra_mod2.dfy
- Prog-Fun-Solutions_tmp_tmp7_gmnz5f_extra_pow.dfy
- Prog-Fun-Solutions_tmp_tmp7_gmnz5f_extra_sum.dfy
- Prog-Fun-Solutions_tmp_tmp7_gmnz5f_mockExam2_p3.dfy
- Prog-Fun-Solutions_tmp_tmp7_gmnz5f_mockExam2_p5.dfy
- Prog-Fun-Solutions_tmp_tmp7_gmnz5f_mockExam2_p6.dfy
- Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_examples_bubblesort.dfy
- Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_algorithms and leetcode_leetcode_lc-remove-element.dfy
- Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_basic examples_find_max.dfy
- Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_vampire project_original_Searching.dfy
- Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_06_Hoangkim_ex06-solution.dfy
- Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_06_Hoangkim_ex_06_hoangkim.dfy
- SENG2011_tmp_tmpgk5jq85q_exam_ex3.dfy
- SENG2011_tmp_tmpgk5jq85q_flex_ex1.dfy
- Software-Verification_tmp_tmpv4ueky2d_Best Time to Buy and Sell Stock_best_time_to_buy_and_sell_stock.dfy
- Software-Verification_tmp_tmpv4ueky2d_Remove Element_remove_element.dfy
- TFG_tmp_tmpbvsao41w_Algoritmos Dafny_suma_it.dfy
- Workshop_tmp_tmp0cu11bdq_Lecture_Answers_max_array.dfy
- Workshop_tmp_tmp0cu11bdq_Lecture_Answers_sum_array.dfy
- Workshop_tmp_tmp0cu11bdq_Lecture_Answers_triangle_number.dfy
- Workshop_tmp_tmp0cu11bdq_Workshop_Answers_Question6.dfy
- cs245-verification_tmp_tmp0h_nxhqp_A8_Q1.dfy
- cs245-verification_tmp_tmp0h_nxhqp_A8_Q2.dfy
- cs245-verification_tmp_tmp0h_nxhqp_Assignments_simple.dfy
- cs245-verification_tmp_tmp0h_nxhqp_power.dfy
- cs357_tmp_tmpn4fsvwzs_lab7_question2.dfy
- dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_binary-search.dfy
- dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_fibonacci.dfy
- dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_find.dfy
- dafny-duck_tmp_tmplawbgxjo_p2.dfy
- dafny-exercise_tmp_tmpouftptir_appendArray.dfy
- dafny-exercise_tmp_tmpouftptir_countNeg.dfy
- dafny-exercise_tmp_tmpouftptir_maxArray.dfy
- dafny-language-server_tmp_tmpkir0kenl_Test_dafny2_COST-verif-comp-2011-1-MaxArray.dfy
- dafny-language-server_tmp_tmpkir0kenl_Test_dafny2_TuringFactorial.dfy
- dafny-programs_tmp_tmpcwodh6qh_src_expt.dfy
- dafny-programs_tmp_tmpcwodh6qh_src_factorial.dfy
- dafny-synthesis_task_id_101.dfy
- dafny-synthesis_task_id_126.dfy
- dafny-synthesis_task_id_127.dfy
- dafny-synthesis_task_id_133.dfy
- dafny-synthesis_task_id_135.dfy
- dafny-synthesis_task_id_14.dfy
- dafny-synthesis_task_id_145.dfy
- dafny-synthesis_task_id_17.dfy
- dafny-synthesis_task_id_170.dfy
- dafny-synthesis_task_id_171.dfy
- dafny-synthesis_task_id_227.dfy
- dafny-synthesis_task_id_234.dfy
- dafny-synthesis_task_id_264.dfy
- dafny-synthesis_task_id_266.dfy
- dafny-synthesis_task_id_267.dfy
- dafny-synthesis_task_id_268.dfy
- dafny-synthesis_task_id_279.dfy
- dafny-synthesis_task_id_282.dfy
- dafny-synthesis_task_id_292.dfy
- dafny-synthesis_task_id_304.dfy
- dafny-synthesis_task_id_309.dfy
- dafny-synthesis_task_id_397.dfy
- dafny-synthesis_task_id_404.dfy
- dafny-synthesis_task_id_406.dfy
- dafny-synthesis_task_id_431.dfy
- dafny-synthesis_task_id_432.dfy
- dafny-synthesis_task_id_435.dfy
- dafny-synthesis_task_id_441.dfy
- dafny-synthesis_task_id_447.dfy
- dafny-synthesis_task_id_452.dfy
- dafny-synthesis_task_id_458.dfy
- dafny-synthesis_task_id_470.dfy
- dafny-synthesis_task_id_555.dfy
- dafny-synthesis_task_id_577.dfy
- dafny-synthesis_task_id_58.dfy
- dafny-synthesis_task_id_581.dfy
- dafny-synthesis_task_id_59.dfy
- dafny-synthesis_task_id_598.dfy
- dafny-synthesis_task_id_600.dfy
- dafny-synthesis_task_id_610.dfy
- dafny-synthesis_task_id_616.dfy
- dafny-synthesis_task_id_62.dfy
- dafny-synthesis_task_id_622.dfy
- dafny-synthesis_task_id_626.dfy
- dafny-synthesis_task_id_637.dfy
- dafny-synthesis_task_id_641.dfy
- dafny-synthesis_task_id_762.dfy
- dafny-synthesis_task_id_77.dfy
- dafny-synthesis_task_id_770.dfy
- dafny-synthesis_task_id_793.dfy
- dafny-synthesis_task_id_798.dfy
- dafny-synthesis_task_id_8.dfy
- dafny-synthesis_task_id_80.dfy
- dafny-synthesis_task_id_801.dfy
- dafny-synthesis_task_id_86.dfy
- dafny-synthesis_task_id_89.dfy
- dafny-workout_tmp_tmp0abkw6f8_starter_ex01.dfy
- dafny-workout_tmp_tmp0abkw6f8_starter_ex02.dfy
- dafny-workout_tmp_tmp0abkw6f8_starter_ex09.dfy
- dafny-workout_tmp_tmp0abkw6f8_starter_ex12.dfy
- dafny_examples_tmp_tmp8qotd4ez_leetcode_0069-sqrt.dfy
- dafny_examples_tmp_tmp8qotd4ez_leetcode_0070-climbing-stairs.dfy
- dafny_misc_tmp_tmpg4vzlnm1_rosetta_code_factorial.dfy
- laboratory_tmp_tmps8ws6mu2_dafny-tutorial_exercise12.dfy
- laboratory_tmp_tmps8ws6mu2_dafny-tutorial_exercise9.dfy
- metodosFormais_tmp_tmp4q2kmya4_T1-MetodosFormais_examples_ex1.dfy
- metodosFormais_tmp_tmp4q2kmya4_T1-MetodosFormais_examples_somatoriov2.dfy
- se2011_tmp_tmp71eb82zt_ass1_ex4.dfy
- summer-school-2020_tmp_tmpn8nf7zf0_chapter02_solutions_exercise02_solution.dfy
- t1_MF_tmp_tmpi_sqie4j_exemplos_colecoes_arrays_ex4.dfy
- t1_MF_tmp_tmpi_sqie4j_exemplos_introducao_ex4.dfy
- tangent-finder_tmp_tmpgyzf44ve_circles.dfy

## Method

Source is masked (comments, string and char literals blanked, their
presence recorded outside `{:attribute}` arguments and outside the
`method Main` harness, which is blanked in the ORIGINAL source so that
a literal elsewhere in the file is still recorded) and each detector is
a regular expression or a small scanner over the masked text;
`coverage_census.py` lists every one.

Lexical detection is approximate in both directions: `+` on sequences
is not distinguished from `+` on integers (concatenation is not tagged,
so seq needs are under-counted) and `nat` is a burden not a gap. Where
one token means two things, the detector reads its context:

- proof scaffolding is blanked before any gap or burden is read: whole
  lemma declarations, and `assert`, `assume` and `calc` statements.
  SYNTAX.md makes these hints, which never put a program outside the
  fragment, so a construct appearing only inside one is not counted;
  the hint rows below are counted on the unblanked text;
- a quantifier is unbounded when a bound variable carries a non-int
  declared type, or carries no int range on the variable itself (a bare
  `v`, not `v*v`) in the guard; membership `v in e` counts as a range,
  `v !in e` does not, and an equality `v == e` counts only when this
  file types `e` as an integer, by declaring the function it calls or
  the collection it indexes to return int or nat;
- `a[i] := e` is an element assignment only when the left-hand side
  starts a statement, so the `:=` inside a functional update
  `m[k := v]` is not one, and the index is bracket-balanced;
- `s[i := v]` is a sequence update only when its receiver is a slice,
  or is not named as a map, imap or multiset in a file that holds a
  sequence somewhere;
- a `[` opens a sequence display only when what precedes it is not an
  identifier, `]` or `)`, or is one of a fixed list of keywords
  (`then [0]`, `else []`, `return [];`);
- a brace group holding only identifiers or integers is a set display
  only in expression position: `predicate P() { false }` is a body;
- `case` alone does not prove a datatype, since a match always carries
  its `match` keyword; `if { case .. }` is the guarded-alternative
  statement and is tagged as nondeterminism instead;
- a return is early only when it is not in tail position of a `method`
  body; a return in a lemma, a function or a predicate is not an exit;
- `:|` is nondeterministic choice (a gap) in a non-ghost method or
  constructor and proof scaffolding (a hint) in a lemma, a function, a
  ghost declaration or the ghost-only `:| assume P` form;
- a program is gradable when a METHOD carries an ensures of its own:
  an ensures on a function, a lemma, a constructor or an iterator
  states nothing a kernel would grade about the method;
- a comma inside `(int, int)` or `map<K, V>` is part of one type, not a
  second return value, and such a group is a tuple only when no call,
  index, arrow type, datatype update or binder head claims it first;
- a real literal is a digit run, a dot and a digit run, never glued to
  an identifier or another dot, so `x.1.1` is a tuple projection;
- an arrow type is `->`, `-->` or `~>` with or without spaces, and a
  declaration is generic even when an attribute stands between the
  keyword and the name.

A declaration with no body (an uninterpreted function, a method
signature), a method with no return value, a least or greatest
predicate, and spec functions in a call cycle are gaps of their own.
Every file's tag set is in the JSON beside this report when `--json` is
given, so any row can be checked against its source.
