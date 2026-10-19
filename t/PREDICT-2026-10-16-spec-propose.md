# PREDICT 2026-10-16 — model proposer for spec strengthening (t/spec_propose.py)

**What it is.** The full ExVerus/SpecSyn loop (arXiv:2603.25810, arXiv:2604.21570): for an
under-constrained task, a model is shown the spec + body (surface.print_task) and the surviving
mutants with their separating witnesses (real vs twin output), and asked for t boolean expressions
that, added as `ensures` conjuncts, exclude those wrong behaviours while staying true for the real
program. Each proposal is parsed with surface.parse_expr and run through spec_refine.check; a
proposal is kept ONLY if the gate accepts it (real body still verifies, strictly fewer survivors).
The model proposes; the interpreter gate decides. Model: `~/.local/bin/fable` (Fable on the Console
credits) by default; AWS Bedrock is an alternative.

**Prediction, with the number that falsifies it.**

- Run on the 6 under-constrained t/humanevaldafny specs. At least 1 (beyond the hand-proven is_prime)
  is strengthened by a model-proposed clause that PASSES the gate (real_ok, survivors_after < before).
  FALSIFIED IF zero model proposals pass the gate — recorded honestly as: a single-shot surface-clause
  proposer is insufficient for these specs, and (importantly) the gate correctly rejected every
  unsound proposal (no weak/breaking clause was ever accepted). A negative result is valid.

**Success for THIS step.** The automated proposer runs end-to-end, every accepted strengthening is
gate-verified (never trusted from the model), and the accepted count is reported with the exact
clauses. Accepted clauses are candidate spec fixes for the imported benchmark tasks, not training
data; nothing the model emits is trusted without the interpreter gate.

## Result (measured 2026-10-16)

Proposer run over the 6 under-constrained t/humanevaldafny specs with Fable (`~/.local/bin/fable`);
every accepted clause passed spec_refine.check (real body still valid, survivors strictly reduced).
All 6 strengthened — 4 to strength 1.0, 2 partial:

  is_prime            0.96 -> 1.00  (1 -> 0)    result ==> k >= 2   (model re-derived the hand clause)
  can_arrange         0.93 -> 1.00  (2 -> 0)    pos >= -1
  make_palindrome     0.89 -> 1.00  (4 -> 0)    forall m in [0,len(result)-len(s)) . not is_palindrome(s[m..len(s)])
  specialFilter       0.61 -> 1.00  (13 -> 0)   forall k ... ==> exists j ... r[j]==s[k]
  generate_integers   0.49 -> 0.96  (25 -> 2)   forall x in [2,9) ... ==> exists j ...   [partial]
  parse_nested_parens 0.24 -> 0.41  (45 -> 35)  max_depth <= len(s)                      [partial]

Prediction CONFIRMED (>=1 strengthened; 6/6 improved, 4 fully). Partials are reported as partial: a
single extra conjunct did not close parse_nested_parens (needs a result<->paren-structure relation)
or generate_integers (a tighter even-in-range characterisation). Survivors across these 6 specs
dropped 90 -> 37; every real body still satisfies its strengthened spec (the gate rejected anything
that broke it). Nothing was trusted from the model. Deterministic gate test: t/test_spec_propose.py.
Persisting accepted clauses back and re-scoring the corpus false-accept floor is step 4.


## Result (dafnybench, step 4, measured 2026-10-17)

Step 4 run over the 53 under-constrained `t/dafnybench` specs (weakest first, from the
`t/spec_strength.py` worklist) with Fable (`~/.local/bin/fable`), eight processes. Every
accepted clause passed `spec_refine.check`, which is **interpreter-only**: `audit.classify`
draws bounded inputs and reports that the real body still satisfies the strengthened spec on
those draws **and** that strictly fewer behaviour-changing mutants survive. No kernel was asked
to prove anything. (Correction, 2026-10-19: the first version of this section said "a prover
confirms the real body still verifies ... provably true of the real program"; that was false.
An interpreter-accepted clause is a *candidate*, and the 2026-10-18 v6 training-contract
control showed why the distinction matters: a `findLUSlength` strengthening passed this same
gate with 7 → 0 survivors, then under the native seven kernels fell from six to five passing
because Rocq did not prove it, `release/evidence/v6-training-repair-native.json`.)
Nothing the model emitted was trusted without the gate.

- **40 of 53** under-constrained specs strengthened; **31 fully closed** (0 survivors).
- Surviving mutants across these 53 specs: **418 → 152  (−64%)**.
- dafnybench corpus spec-strength (interpreter audit, 320 tasks / 7,255 behaviour-changing
  mutants) was measured at **94.2%** killed before this run. The **97.9%** figure is arithmetic
  on the per-spec deltas — what the corpus number *would* be if the 40 clauses were persisted —
  not a re-measurement; nothing was persisted (see below).
- 0 errors. (An earlier thread-parallel pass errored on all 53 with `signal only works in
  main thread of the main interpreter` — the gate's per-check timeout uses `signal.alarm`,
  which needs a process's main thread; the run is therefore per-process, not per-thread.)

**Scope, stated honestly.** This is the interpreter spec-strength instrument on the
dafnybench corpus (the tasks happen to be Dafny-derived; no Dafny ran here). It is **not** the seven-kernel false-accept FLOOR of E1
(`internal/E1-FINDINGS-2026-10-14.md`); that floor is a broader measurement across all
seven kernels and is re-scored only by re-running E1, not by this run. What this shows is
that the ExVerus/SpecSyn proposer+gate loop closes real `ensures` gaps automatically — the
very mechanism E1 attributes its floor to.

**On persisting into the corpus.** The `t/dafnybench` tasks are a pinned copy of
t-proof-engine content (`t/ENGINE.md`: "the tasks"). Merging these clauses into the
benchmark is a t-proof-engine change (then `bash t/sync_engine.sh`), not a dawnr-only edit,
so the clauses are recorded here as a candidate engine strengthening rather than written
into the corpus in this repository. Machine-readable per-spec record (clause, witness,
before/after) and the pre-run worklist: `t/evidence/2026-10-17-spec-propose-dafnybench/`
(moved into the tree 2026-10-19; it had been left untracked under `out/`).

### Accepted strengthenings (40, all gate-verified)

| spec | added `ensures` | survivors |
|---|---|---|
| `bbfny_tmp_tmpw4m0jvl0_enjoying__multipleReturns` | `r.1 == x - y` | 1 → 0 |
| `cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1_assignment_2__plusOne` | `y == x + 1` | 1 → 0 |
| `dafny_exercises_tmp_tmpjm75muf__session3exercises_exercisemaximum__mmaximum1` | `forall k in [0, i) . v[k] < v[i]` | 1 → 0 |
| `dafny_experiences_tmp_tmp150sm9qy_dafny_started_tutorial_dafny_tutorial_array__findMax` | `forall k in [0, i) . a[k] < a[i]` | 1 → 0 |
| `dafny_learning_experience_tmp_tmpuxvcet_u_week8_12_week9_lemma__assignmentsToMarkOne` | `r == students / tutors` | 1 → 0 |
| `dafny_synthesis_task_id_126__sumOfCommonDivisors` | `(forall d in [2, a + 1) . a % d != 0 or b % d != 0) ==> sum == 1` | 13 → 0 |
| `dafny_synthesis_task_id_145__maxDifference` | `exists i in [0, len(a)) . exists j in [0, len(a)) . a[i] - a[j] == diff` | 3 → 0 |
| `dafny_synthesis_task_id_161__removeElements` | `forall i in [0, len(a)) . not inArray(b, a[i]) ==> inArray(result, a[i])` | 11 → 0 |
| `dafny_synthesis_task_id_249__intersection` | `forall i in [0, len(a)) . inArray(b, a[i]) ==> inArray(result, a[i])` | 11 → 0 |
| `dafny_synthesis_task_id_2__sharedElements` | `forall i in [0, len(a)) . inArray(b, a[i]) ==> inArray(result, a[i])` | 11 → 0 |
| `dafny_synthesis_task_id_397__medianOfThree` | `(median == a and (b <= a and a <= c or c <= a and a <= b)) or (median == b and (a <= b and b <= c or c <= b and b <= a)) or (median == c and (a <= c and c <= b or b <= c and c <= a))` | 48 → 0 |
| `dafny_synthesis_task_id_567__isSorted` | `sorted ==> (forall i in [0, len(a)) . forall j in [i + 1, len(a)) . a[i] <= a[j])` | 14 → 0 |
| `dafny_synthesis_task_id_603__lucidNumbers` | `len(lucid) == n / 3 + 1` | 7 → 0 |
| `dafny_tmp_tmp0wu8wmfr_tests_f1a__f` | `r == 0` | 2 → 0 |
| `dafny_verify_tmp_tmphq7j0row_dataset_c_convert_examples_11__main_v` | `r.1 == x` | 1 → 0 |
| `dafny_verify_tmp_tmphq7j0row_dataset_c_convert_examples_15__main_v` | `k_out == k - n` | 21 → 0 |
| `dafny_verify_tmp_tmphq7j0row_fine_tune_examples_error_data_completion_11__main_v` | `r.1 == x` | 1 → 0 |
| `dafny_verify_tmp_tmphq7j0row_generated_code_15__main_v` | `k_out == k - n` | 21 → 0 |
| `dafny_verify_tmp_tmphq7j0row_test_cases_index__index` | `i == n / 2` | 1 → 0 |
| `dafny_verify_tmp_tmphq7j0row_test_cases_index__reconstructFromMaxSum` | `r.0 == m` | 1 → 0 |
| `dafny_workout_tmp_tmp0abkw6f8_starter_ex12__findMax` | `forall j in [0, max_idx) . a[max_idx] > a[j]` | 1 → 0 |
| `final_project_dafny_tmp_tmpmcywuqox_attempts_exercise4_find_max__findMax` | `forall i_v5 in [0, r.0) . a[i_v5] < r.1` | 1 → 0 |
| `final_project_dafny_tmp_tmpmcywuqox_attempts_insertion_sort_normal__lookForMin` | `forall k in [i, m) . a[k] > a[m]` | 1 → 0 |
| `final_project_dafny_tmp_tmpmcywuqox_final_project_3__nonZeroReturn` | `x == 0 ==> y == 1` | 2 → 0 |
| `laboratory_tmp_tmps8ws6mu2_dafny_tutorial_exercise12__findMax` | `forall k in [0, i) . a[k] < a[i]` | 1 → 0 |
| `mfes_2021_tmp_tmpuljn8zd9_fcul_exercises_10_find__find` | `forall x in [0, index) . a[x] != key` | 3 → 0 |
| `nitwit_tmp_tmplm098gxz_nit__nit_increment` | `r.0 + r.1 * b == n + 1` | 20 → 0 |
| `program_verification_dataset_tmp_tmpgbdrlnu__dafny_basic_examples_find_max__findMax` | `forall x in [0, max) . a[x] < a[max]` | 1 → 0 |
| `seng2011_tmp_tmpgk5jq85q_ass1_ex8__getEven` | `forall i in [0, len(a)) . a_out[i] >= a[i]` | 1 → 0 |
| `software_building_and_verification_projects_tmp_tmp5tm1srrn_cvs_projeto_aula2__m4` | `z == (x == y)` | 4 → 0 |
| `stunning_palm_tree_tmp_tmpr84c2iwh_ch1__reconstructFromMaxSum` | `r.0 == m` | 1 → 0 |
| `final_project_dafny_tmp_tmpmcywuqox_attempts_exercise6_binary_search__binarySearch` | `pos >= -1` | 5 → 1 |
| `software_building_and_verification_projects_tmp_tmp5tm1srrn_cvs_projeto_aula2__max` | `z >= a and z >= b` | 10 → 2 |
| `dafny_tmp_tmpmvs2dmry_examples1__multiReturn` | `r.0 == x + y` | 7 → 4 |
| `projectoscvs_tmp_tmp_02_gmcw_handout_1_cvs_handout1_55754_55780__euclidianDiv` | `0 <= r.1` | 10 → 4 |
| `dafny_learning_experience_tmp_tmpuxvcet_u_week8_12_a3_search_findpositionofindex__findPositionOfElement` | `r.0 >= 1 ==> r.0 == r.1 + 1` | 11 → 5 |
| `stunning_palm_tree_tmp_tmpr84c2iwh_ch1__minUnderSpec` | `r < x` | 10 → 7 |
| `dafny_verify_tmp_tmphq7j0row_fine_tune_examples_50_examples_41__main_v` | `r.0 == n` | 15 → 8 |
| `dafny_verify_tmp_tmphq7j0row_test_cases_ghost__myMethod` | `x < 20 ==> y == 35` | 28 → 8 |
| `dafny_language_server_tmp_tmpkir0kenl_test_vscomp2010_problem1_summax__m` | `r.1 >= 0` | 21 → 19 |

### No proposal passed (13)

`cs245_verification_tmp_tmp0h_nxhqp_a8_q2__a8Q1`, `cs245_verification_tmp_tmp0h_nxhqp_sortingissues_firstattempt__sort`, `dafny_learn_tmp_tmpn94ir40q_r01_assertions__max`, `dafny_programs_tmp_tmp99966ew4_mymax__max`, `dafny_tmp_tmp0wu8wmfr_heimaverkefni_3_insertionsortmultiset__search`, `dafny_training_tmp_tmp_n2kixni_session1_training1__abs`, `dafny_training_tmp_tmp_n2kixni_session1_training1__find`, `dafny_training_tmp_tmp_n2kixni_session1_training1__max`, `dafny_verify_tmp_tmphq7j0row_dataset_bql_exampls_smallnum__add_small_numbers`, `nitwit_tmp_tmplm098gxz_nit__nit_add`, `programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_07_hoangkim_ex07_hoangkim__findMin`, `software_verification_tmp_tmpv4ueky2d_best_time_to_buy_and_sell_stock_best_time_to_buy_and_sell_stock__best_time_to_buy_and_sell_stock`, `workshop_tmp_tmp0cu11bdq_workshop_answers_question6__arrayUpToN`

These 13 are not failures of the gate — the gate correctly rejected every unsound
or non-reducing proposal; a single surface clause from one model call did not close them
(most need a quantified relation between `result` and the loop structure, as
`parse_nested_parens` and `generate_integers` did in the humanevaldafny run above).
