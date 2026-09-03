# t coverage census: DafnyBench (785 programs)

What this corpus needs that t does not have, program by program, and
which gate opens the most programs. Lexical census, no kernel run; the
in-fragment count says a program's constructs fit SYNTAX.md, not that
seven kernels verify its t rendering. Method and detectors at the end.

## Headline

- programs: 785; with a method and an ensures (gradable): 661
- in t's fragment today: **77** of 661 gradable (11.6%)
- programs blocked by exactly one gap: 140

## Gaps, by programs that need them

| gap | programs | sole blocker for | meaning |
|---|---|---|---|
| array | 309 | 39 | array type or allocation |
| multi-method | 212 | 12 | more than one method (Main excluded) |
| div-mod | 173 | 32 | integer division or modulo |
| early-exit | 172 | 8 | return inside a block, break, continue |
| seq-slice | 169 | 0 | slicing s[a..b] |
| array-mutation | 150 | 0 | element assignment a[i] := e |
| set | 150 | 5 | set, iset, multiset, set comprehension or set literal |
| seq-literal | 136 | 1 | sequence literal [..] in an expression |
| generics | 90 | 1 | type parameters |
| multi-return | 84 | 18 | several return values |
| string-char | 81 | 3 | string or char type |
| datatype | 78 | 2 | algebraic datatypes and match |
| heap | 78 | 1 | classes, object allocation, this |
| nested-seq | 76 | 2 | seq of non-int elements |
| seq-return | 60 | 0 | sequence-valued return |
| module | 43 | 2 | modules and imports |
| unbounded-quantifier | 42 | 3 | quantifier without an int range |
| higher-order | 40 | 0 | lambdas or function types |
| real | 35 | 6 | real numbers |
| seq-update | 35 | 0 | functional update s[i := v] |
| map | 34 | 2 | map, imap, map comprehension or map literal |
| type-decl | 33 | 0 | newtype, type synonyms, subset types |
| io | 24 | 1 | print or expect |
| tuple | 24 | 0 | tuples |
| bitvector | 6 | 1 | bit vectors or bitwise operators |
| decreases-star | 6 | 0 | decreases * (a loop or call allowed not to terminate) |
| seq-comprehension | 3 | 0 | seq(n, i => e) |
| char-arith | 3 | 0 | char arithmetic |
| iterator | 2 | 1 | iterators |
| function-method | 1 | 0 | compiled functions |

## Greedy gate order (open the gate that unlocks the most programs)

| step | gate | newly unlocked | cumulative in fragment | of gradable |
|---|---|---|---|---|
| 1 | array | 38 | 115 | 17.4% |
| 2 | array-mutation | 33 | 148 | 22.4% |
| 3 | div-mod | 38 | 186 | 28.1% |
| 4 | early-exit | 40 | 226 | 34.2% |
| 5 | multi-method | 41 | 267 | 40.4% |
| 6 | multi-return | 40 | 307 | 46.4% |
| 7 | seq-slice | 28 | 335 | 50.7% |
| 8 | string-char | 30 | 365 | 55.2% |
| 9 | set | 34 | 399 | 60.4% |
| 10 | real | 19 | 418 | 63.2% |
| 11 | seq-literal | 17 | 435 | 65.8% |
| 12 | seq-return | 38 | 473 | 71.6% |
| 13 | nested-seq | 22 | 495 | 74.9% |
| 14 | heap | 19 | 514 | 77.8% |
| 15 | generics | 18 | 532 | 80.5% |
| 16 | datatype | 18 | 550 | 83.2% |
| 17 | seq-update | 13 | 563 | 85.2% |
| 18 | higher-order | 13 | 576 | 87.1% |
| 19 | unbounded-quantifier | 9 | 585 | 88.5% |
| 20 | io | 10 | 595 | 90.0% |
| 21 | module | 12 | 607 | 91.8% |
| 22 | map | 12 | 619 | 93.6% |
| 23 | tuple | 14 | 633 | 95.8% |
| 24 | type-decl | 13 | 646 | 97.7% |
| 25 | decreases-star | 5 | 651 | 98.5% |
| 26 | bitvector | 4 | 655 | 99.1% |
| 27 | char-arith | 3 | 658 | 99.5% |
| 28 | seq-comprehension | 1 | 659 | 99.7% |
| 29 | iterator | 1 | 660 | 99.8% |
| 30 | function-method | 1 | 661 | 100.0% |


### The same order on the MBPP-DFY family alone (164 gradable, the LLM-shaped subset)

| step | gate | newly unlocked | cumulative | of gradable |
|---|---|---|---|---|
| 1 | div-mod | 16 | 42 | 25.6% |
| 2 | array | 10 | 52 | 31.7% |
| 3 | early-exit | 17 | 69 | 42.1% |
| 4 | string-char | 10 | 79 | 48.2% |
| 5 | array-mutation | 9 | 88 | 53.7% |
| 6 | real | 9 | 97 | 59.1% |
| 7 | set | 6 | 103 | 62.8% |
| 8 | nested-seq | 5 | 108 | 65.9% |
| 9 | seq-literal | 4 | 112 | 68.3% |
| 10 | seq-return | 23 | 135 | 82.3% |
| 11 | seq-slice | 15 | 150 | 91.5% |
| 12 | multi-return | 4 | 154 | 93.9% |
| 13 | multi-method | 3 | 157 | 95.7% |
| 14 | char-arith | 3 | 160 | 97.6% |
| 15 | bitvector | 2 | 162 | 98.8% |
| 16 | tuple | 1 | 163 | 99.4% |
| 17 | higher-order | 0 | 163 | 99.4% |
| 18 | seq-comprehension | 1 | 164 | 100.0% |

A step with 0 newly unlocked is a gate that unlocks nothing alone but
is the most frequent remaining gap; the programs it belongs to need
more than one gate.

## By family

| family | programs | gradable | in fragment |
|---|---|---|---|
| MBPP-DFY (dafny-synthesis) | 164 | 164 | 26 |
| GitHub (Dafny) | 76 | 72 | 9 |
| GitHub (Program-Verification-Dataset) | 65 | 52 | 1 |
| Clover | 62 | 62 | 5 |
| GitHub (dafny-language-server) | 43 | 21 | 1 |
| GitHub (Dafny-Exercises) | 21 | 20 | 0 |
| GitHub (dafny) | 18 | 14 | 2 |
| GitHub (SENG) | 14 | 12 | 0 |
| GitHub (dafny-exercise) | 12 | 11 | 0 |
| GitHub (ironsync-osdi) | 12 | 4 | 0 |
| GitHub (dafl) | 11 | 7 | 1 |
| GitHub (protocol-verification-fa) | 11 | 1 | 0 |
| GitHub (Metodos) | 10 | 9 | 6 |
| GitHub (Final-Project-Dafny) | 9 | 8 | 0 |
| GitHub (Software-Verification) | 9 | 9 | 0 |
| GitHub (DafnyProjects) | 8 | 8 | 0 |
| GitHub (Prog-Fun-Solutions) | 8 | 8 | 5 |
| GitHub (Programmverifikation-und-synthese) | 7 | 7 | 2 |
| GitHub (cs245-verification) | 7 | 6 | 4 |
| GitHub (dafny-duck) | 7 | 6 | 0 |
| GitHub (Software-building-and-verification-Projects) | 6 | 6 | 1 |
| GitHub (Workshop) | 6 | 6 | 0 |
| GitHub (llm-verified-eval) | 6 | 5 | 0 |
| GitHub (t) | 6 | 5 | 1 |
| GitHub (MFES) | 5 | 5 | 0 |
| GitHub (MIEIC) | 5 | 5 | 2 |
| GitHub (dafny-workout) | 5 | 5 | 1 |
| GitHub (summer-school-) | 5 | 2 | 0 |
| GitHub (CVS-Projto) | 4 | 2 | 0 |
| GitHub (DafnyPrograms) | 4 | 4 | 0 |
| GitHub (FMSE-2022-) | 4 | 1 | 0 |
| GitHub (FlexWeek) | 4 | 4 | 0 |
| GitHub (HATRA-2022-Paper) | 4 | 4 | 0 |
| GitHub (dafny-programs) | 4 | 4 | 2 |
| GitHub (formal) | 4 | 4 | 0 |
| GitHub (specTesting) | 4 | 1 | 0 |
| GitHub (stunning-palm-tree) | 4 | 3 | 0 |
| GitHub (test-generation-examples) | 4 | 3 | 0 |
| GitHub (AssertivePrograming) | 3 | 3 | 0 |
| GitHub (Correctness) | 3 | 3 | 0 |
| GitHub (Formal-methods-of-software-development) | 3 | 1 | 0 |
| GitHub (M) | 3 | 3 | 3 |
| GitHub (assertive-programming-assignment-) | 3 | 3 | 0 |
| GitHub (cs) | 3 | 3 | 1 |
| GitHub (dafleet) | 3 | 3 | 0 |
| GitHub (formal-methods-in-software-engineering) | 3 | 1 | 0 |
| GitHub (groupTheory) | 3 | 1 | 0 |
| GitHub (iron-sync) | 3 | 1 | 0 |
| GitHub (se) | 3 | 2 | 1 |
| GitHub (veri-sparse) | 3 | 3 | 0 |
| GitHub (vfag) | 3 | 2 | 0 |
| GitHub (703FinalProject) | 2 | 0 | 0 |
| GitHub (CS) | 2 | 1 | 0 |
| GitHub (CVS-handout) | 2 | 2 | 0 |
| GitHub (Dafny-Practice) | 2 | 2 | 0 |
| GitHub (Dafny-VMC) | 2 | 0 | 0 |
| GitHub (DafnyExercises) | 2 | 1 | 0 |
| GitHub (Formal-Methods-Project) | 2 | 0 | 0 |
| GitHub (Formal-Verification) | 2 | 2 | 0 |
| GitHub (FormalMethods) | 2 | 2 | 2 |
| GitHub (Formal) | 2 | 2 | 0 |
| GitHub (MFS) | 2 | 2 | 0 |
| GitHub (TFG) | 2 | 2 | 0 |
| GitHub (dafny-exercises) | 2 | 2 | 0 |
| GitHub (dafny-learn) | 2 | 2 | 0 |
| GitHub (fv2020-tms) | 2 | 2 | 0 |
| GitHub (laboratory) | 2 | 2 | 1 |
| GitHub (metodosFormais) | 2 | 2 | 0 |
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
| GitHub (Dafny-experiences) | 1 | 1 | 0 |
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
| GitHub (software-specification-p) | 1 | 1 | 0 |
| GitHub (software) | 1 | 1 | 0 |
| GitHub (tangent-finder) | 1 | 1 | 0 |
| GitHub (type-definition) | 1 | 0 | 0 |
| GitHub (veri-titan) | 1 | 0 | 0 |
| GitHub (verification-class) | 1 | 0 | 0 |
| GitHub (verified-isort) | 1 | 1 | 0 |
| GitHub (verified-using-dafny) | 1 | 1 | 0 |
| GitHub (vmware-verification-) | 1 | 0 | 0 |

## Burdens (expressible at a translation cost)

| burden | programs | meaning |
|---|---|---|
| spec-only-quantifier | 467 | quantifiers (bounded ones are in t) |
| untyped-var | 437 | var without a type (t declares every type) |
| function-or-predicate | 379 | pure functions, as spec_funs when first-order over int and seq |
| while-no-decreases | 275 | a loop without its decreases (t requires one) |
| nat | 220 | nat, as int with a >= 0 clause |
| frame-clause | 192 | modifies / reads (array frames when no class is present) |
| no-if-no-loop | 173 | straight-line body: the twin ladder has only its extensional operators to try |
| if-no-else | 171 | if without else |
| seq-membership | 148 | in / !in (a bounded exists over a seq; set and map membership are their own gaps) |
| trailing-return | 108 | a return as the last statement (assign the result instead) |
| main-harness | 105 | a Main test harness (stripped before tagging) |
| for-loop | 100 | for loop (a while with a bound) |
| parallel-assign | 95 | x, y := a, b (sequenced through a temporary) |
| iff | 91 | <==> (== on bools) |
| as-cast | 15 | as int / as nat casts |

## Hints (proof scaffolding a kernel may need; t has none)

| hint | programs | meaning |
|---|---|---|
| assert | 315 | assert statements |
| lemma | 151 | lemmas |
| ghost | 116 | ghost code |
| old | 110 | old() (two-state; heap or array frames) |
| attribute | 73 | attributes |
| ghost-var | 62 | ghost variables |
| assign-such-that | 53 | assign-such-that |
| calc | 44 | calc proofs |
| forall-statement | 32 | forall statements |
| assume | 28 | assume (unsound as a hint; refused by every t adapter) |
| assert-by | 22 | assert ... by { } |
| reveal-opaque | 17 | reveal / opaque |

## In fragment today

- Clover_integer_square_root.dfy
- Clover_return_seven.dfy
- Clover_triple.dfy
- Clover_triple3.dfy
- Clover_triple4.dfy
- Dafny_Programs_tmp_tmp99966ew4_trig.dfy
- Dafny_Verify_tmp_tmphq7j0row_AI_agent_verify_examples_ComputePower.dfy
- Dafny_Verify_tmp_tmphq7j0row_AI_agent_verify_examples_Cube.dfy
- Dafny_Verify_tmp_tmphq7j0row_Generated_Code_15.dfy
- Dafny_Verify_tmp_tmphq7j0row_Generated_Code_ComputePower.dfy
- Dafny_Verify_tmp_tmphq7j0row_Generated_Code_Mult.dfy
- Dafny_Verify_tmp_tmphq7j0row_dataset_C_convert_examples_15.dfy
- Dafny_Verify_tmp_tmphq7j0row_dataset_bql_exampls_Square.dfy
- Dafny_Verify_tmp_tmphq7j0row_dataset_error_data_real_error_IsEven_success_1.dfy
- FormalMethods_tmp_tmpvda2r3_o_dafny_Invariants_ex1.dfy
- FormalMethods_tmp_tmpvda2r3_o_dafny_Invariants_ex2.dfy
- M2_tmp_tmp2laaavvl_Software Verification_Exercices_Exo4-CountAndReturn.dfy
- M2_tmp_tmp2laaavvl_Software Verification_Exercices_Exo7-ComputeSum.dfy
- M2_tmp_tmp2laaavvl_Software Verification_Exercices_Exo9-Carre.dfy
- MIEIC_mfes_tmp_tmpq3ho7nve_exams_appeal_20_p4.dfy
- MIEIC_mfes_tmp_tmpq3ho7nve_exams_mt2_19_p4.dfy
- Metodos_Formais_tmp_tmpbez22nnn_Aula_2_ex1.dfy
- Metodos_Formais_tmp_tmpbez22nnn_Aula_2_ex2.dfy
- Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_fatorial2.dfy
- Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_fibonacci.dfy
- Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_multiplicador.dfy
- Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_potencia.dfy
- Prog-Fun-Solutions_tmp_tmp7_gmnz5f_extra_pow.dfy
- Prog-Fun-Solutions_tmp_tmp7_gmnz5f_extra_sum.dfy
- Prog-Fun-Solutions_tmp_tmp7_gmnz5f_mockExam2_p3.dfy
- Prog-Fun-Solutions_tmp_tmp7_gmnz5f_mockExam2_p5.dfy
- Prog-Fun-Solutions_tmp_tmp7_gmnz5f_mockExam2_p6.dfy
- Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_basic examples_product_details.dfy
- Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_06_Hoangkim_ex06-solution.dfy
- Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_06_Hoangkim_ex_06_hoangkim.dfy
- Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula1.dfy
- cs245-verification_tmp_tmp0h_nxhqp_A8_Q1.dfy
- cs245-verification_tmp_tmp0h_nxhqp_A8_Q2.dfy
- cs245-verification_tmp_tmp0h_nxhqp_Assignments_simple.dfy
- cs245-verification_tmp_tmp0h_nxhqp_power.dfy
- cs357_tmp_tmpn4fsvwzs_lab7_question2.dfy
- dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_fibonacci.dfy
- dafny-language-server_tmp_tmpkir0kenl_Test_dafny2_TuringFactorial.dfy
- dafny-programs_tmp_tmpcwodh6qh_src_expt.dfy
- dafny-programs_tmp_tmpcwodh6qh_src_factorial.dfy
- dafny-synthesis_task_id_127.dfy
- dafny-synthesis_task_id_135.dfy
- dafny-synthesis_task_id_17.dfy
- dafny-synthesis_task_id_171.dfy
- dafny-synthesis_task_id_227.dfy
- dafny-synthesis_task_id_234.dfy
- dafny-synthesis_task_id_264.dfy
- dafny-synthesis_task_id_266.dfy
- dafny-synthesis_task_id_268.dfy
- dafny-synthesis_task_id_279.dfy
- dafny-synthesis_task_id_309.dfy
- dafny-synthesis_task_id_397.dfy
- dafny-synthesis_task_id_404.dfy
- dafny-synthesis_task_id_441.dfy
- dafny-synthesis_task_id_452.dfy
- dafny-synthesis_task_id_458.dfy
- dafny-synthesis_task_id_58.dfy
- dafny-synthesis_task_id_581.dfy
- dafny-synthesis_task_id_59.dfy
- dafny-synthesis_task_id_626.dfy
- dafny-synthesis_task_id_637.dfy
- dafny-synthesis_task_id_762.dfy
- dafny-synthesis_task_id_801.dfy
- dafny-synthesis_task_id_803.dfy
- dafny-synthesis_task_id_86.dfy
- dafny-synthesis_task_id_89.dfy
- dafny-workout_tmp_tmp0abkw6f8_starter_ex02.dfy
- dafny_examples_tmp_tmp8qotd4ez_leetcode_0070-climbing-stairs.dfy
- dafny_misc_tmp_tmpg4vzlnm1_rosetta_code_factorial.dfy
- laboratory_tmp_tmps8ws6mu2_dafny-tutorial_exercise9.dfy
- se2011_tmp_tmp71eb82zt_ass1_ex4.dfy
- t1_MF_tmp_tmpi_sqie4j_exemplos_introducao_ex4.dfy

## Method

Source is masked (comments, string and char literals blanked, their
presence recorded) and each detector is a regular expression or a small
scanner over the masked text; `coverage_census.py` lists every one.
Lexical detection is approximate in both directions: `+` on sequences
is not distinguished from `+` on integers (concatenation is not tagged,
so seq needs are under-counted), `nat` is a burden not a gap, and a
quantifier is read as unbounded when its variables carry a non-int type
or no comparison bounds them before the body. Every file's tag set is
in the JSON beside this report when `--json` is given, so any row can
be checked against its source.
