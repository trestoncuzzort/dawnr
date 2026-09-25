# Traps before the next locallm run: audit of 2026-09-21

Read-only audit of `/home/t/tup` (code as of 02f6d350; 3f57ec8b changed docs only) and of the lab at 3bd13d2b. Three things are wrong right now:

- **Held-out leak.** `corpus-r7-headed.txt` (the headline arm) and `corpus-r8-headed.txt` (r9, all r11 seeds and the soups) contain `dafny_synthesis_task_id_269__…` and `…_626__…`. Those are held-out MBPP problems 269 and 626. Neither `loop_locallm.mbpp_id()` nor preflight's `mbpp_(\d+)` catches that name, even though `loop_dataset.py:91` maps it to MBPP N. No published clean answer came from the leak.
- **Lab.** 27 z3 processes with PPID 1 are still running after their grader exited. `t/lab_status.py` (PID 2699319) has been stopped for 22.5 h. `~/.local/share/cpu-yield/frozen.pids` (written 09-20 19:43) lists it and the qwen235-train grader, so the "unknown" SIGSTOP came from the cpu-yield watcher, which exited without resuming them. 48 generation workers ran during that grading (load 78-112).
- **Question overlap.** 24 of the 232 held-out statements score ≥0.5 token Jaccard against corpus-r8 heads. Eval 970 is train 404 word for word. `min_of_two` and `mul_list` still count as "novel" in four arms each.

## 1. Traps

| trap | where | guarded automatically? | source |
|---|---|---|---|
| fleet dropped `--temperature 0` | gen_fleet.sh | PARTIAL: fixed :46,:69; no test, no record check | CORRECTIONS; 9dc0b4cc |
| mode overwritten; exit 0 having graded nothing | grade_lab.sh | PARTIAL: fixed :78; no test | trap 3; 042e35c3 |
| Verus never started, every cell malformed | grade_lab/run_par | PARTIAL: `bash -lc` :185; check 11b preflight.py:558 (after the fact); run_par.py:271 grades `verus ?` | trap 2 |
| tokenizer eats spaces; mask narrower than logits | loop_generate.py:584,:445 | YES (+preflight.py:643) | CORRECTIONS |
| `--grammar` missed a call site | loop_generate.py | PARTIAL: check 8 checks the grammar file, not the call sites | d35a99fd |
| SPARK -j8 inside a 4-core cell | spark.py:437 | PARTIAL: only grade_lab.sh:185 sets 1; RUN-NEXT step 4 bypasses it | FINDINGS-r10 |
| corpus built without a split filter | loop_locallm.py:121-212 | PARTIAL: `--split` opt-in (steps.json:398 omits it); preflight.py:173 (local files only) | #30 |
| lifted MBPP-DFY names get past both leak checks | loop_locallm.py:144; preflight.py:161,176 | NO | this audit |
| splitter merged documents; head-blind readers | loop_locallm.py:171,278; loop_filter.py:25 | YES: test_head_handling.py; score_heldout.py:96 | CORRECTIONS |
| near-duplicate problems recited | score_heldout.py:61-147 | PARTIAL: after the fact, exact-AST only | FINDINGS-r10 |
| GPU nondeterminism; seed also picks the validation split | continue_from_checkpoint.py:77-87 | NO | FINDINGS-r10 |
| grader SIGSTOPped for a day | cpu-yield | NO | FINDINGS-r10 |
| orphan provers | verifiers/__init__.py:152 | NO: killpg only on TimeoutExpired | FINDINGS-r10 |
| generation during grading | gen_fleet.sh:17; grade_lab.sh:70-92 | PARTIAL: grade_lab lowers its cell count | trap 5 |
| sentinel means exited, not finished | gen_fleet.sh:82 | PARTIAL: checks rc, not the count | trap 7 |
| partial set extracted and scored | grade_lab.sh:227; score_heldout.py:123 | NO | code |
| Lean/SPARK flakes under load | preflight.py:210 | PARTIAL: FLAKED/timeout refused; load-induced `unproved` only by manual recheck, and it gets cached (run_par.py:110) | trap 8 |
| stale evaluator | grade_lab.sh:99; preflight.py:278 | PARTIAL: warns only | 97aa4a49 |
| unchecked tag scored as checked | spec_check.py:582; score_heldout.py:45 | YES | CORRECTIONS |
| pool-disagreement check reads r4/r5 files only | preflight.py:238 | NO | RUN-NEXT:95 |
| SFT rows dropped when `--pool` lacks their ids | loop_locallm.py:184-191 | NO | 082d388b |
| ids in neither half of the split skipped | loop_dataset.py:936 | PARTIAL: split-v6 exists; the skip is still silent | FINDINGS-split-v6 |
| widened pool gate | loop_dataset.py:596 | YES (test :163) | ROADMAP-LOG |
| `t/out` gitignored | .gitignore; preflight.py:456 | PARTIAL: input files only | trap 1 |
| `pkill -f` matches its own shell | lab_gpu.sh:31,71 | PARTIAL: `stop` misses `loop_locallm.py`/`continue_from_checkpoint.py`, exits 0 | trap 6 |
| verdict cache reused on a regrade | run_par.py:110,521 | NO: `--no-cache` must be set by hand | PREDICT-r10-regrade |
| stale remote table; stale `.grading` lock | grade_lab.sh:166-186 | NO: run_par exit ignored | code |
| width/heads, null prompt, reply head | loop_locallm.py:232,286; loop_dataset.py | YES | commits |

## 2. The run checklist

1. Lab quiet: none of our processes in state T, `frozen.pids` empty, no prover with PPID 1, no fleet during grading, load below core count. MANUAL
2. Desktop and lab at one commit. AUTOMATED (warns only)
3. `bash -lc 'python3 t/preflight.py --split t/out/loop/split-v5.json --strict'` on the lab. AUTOMATED
4. Predictions written in `t/PREDICT-*.md`. MANUAL
5. `loop_dataset.py` positive gate. AUTOMATED
6. `loop_locallm.py corpus --pool v5 --split …`: log says "excluded", SFT count equals rows. MANUAL
7. Grep the corpus for `task_id_<eval id>` and near-duplicate heads. MANUAL
8. `head_align_corpus` reports `unparsed` = 0. MANUAL
9. Train. Tokenizer, vocabulary and finite-loss checks: AUTOMATED. run.json `complete` with a matching corpus sha: MANUAL
10. At least 5 seeds per recipe. MANUAL
11. `gen_fleet.sh … --temperature 0 --tokens 1200`: sentinel AUTOMATED. 232 records with identical `options`: MANUAL
12. Extract and test only after the sentinel. MANUAL. Check 10: AUTOMATED
13. `grade_lab.sh heldout` from the desktop: AUTOMATED. `--no-cache`, watching the load: MANUAL
14. Checks 4, 11, 11b: AUTOMATED. Table rows equal tasks: MANUAL
15. `recheck_near.py --only unproved|timeout --flake 3`. MANUAL
16. `spec_check.py --pool v3 --only clean <tags>` on one machine, with no "NOT CHECKED" line. MANUAL
17. `score_heldout.py --corpus TAG=<corpus>`: AUTOMATED. answered = 232, corpus sha matches run.json: MANUAL
18. Report the mean and range; `git add` the table. MANUAL

## 3. Top 7 unguarded risks

1. **Leak through lifted names.** A `problem_id(name)` in `t/loop_filter.py` maps `mbpp_N__`, `dafny_synthesis_task_id_N__`, `he_N__` and `apps_N__` to the pool id. `loop_locallm.cmd_corpus`, `preflight.check_split` and `continue_from_checkpoint.main` use it to refuse any held-out id and record the scan in run.json. Tested on the real name. Prior art: BigCode decontamination, which matches on content rather than ids. Receipt **bbd18e61a31d**.
2. **Question overlap.** `score_heldout.question_overlap()` computes token-set Jaccard ≥0.58 between each held-out problem (text, code and tests) and each corpus document. It prints "clean, non-overlapping", and the corpus builder writes the same list before training. Prior art: Lewis et al. arXiv:2008.02637, and BigCode `minhash.py`. Receipt **6d9b2b8e2399**.
3. **Partial sets.** `gen_fleet.sh` writes the sentinel only when the raw ids equal the eval ids. `cmd_generate` exits non-zero if it skipped any id. `grade_lab.sh heldout` refuses a set with no sentinel and re-extracts when `raw/` is newer than `extract.json`. `score_heldout.score` refuses a set with answered < eval unless given `--allow-partial`. Prior art: Deequ `hasSize`/`isComplete`. Receipt **e43dae1eaab5**.
4. **Contention and orphaned provers.** `verifiers.run_tree` kills its process group on every exit path. `grade_lab.sh` refuses to start while any of our provers has PPID 1 or a fleet is running. `run_par.main` defaults `T_SPARK_JOBS=1` when `--jobs` > 1. Prior art: BenchExec, which uses cgroups to cover subprocesses. Receipt **29188ff4619a**.
5. **Silent freezes.** A `t/stall_check.py`, run at start and every 10 minutes, fails when any of our processes is in state T, when `frozen.pids` names a live PID, or when the newest output is older than 27 minutes. Prior art: Airflow's zombie heartbeat threshold. Receipt **f519256b655f**.
6. **Decoding settings.** `cmd_generate` has no temperature default and refuses to resume into records whose options or model differ. `gen_fleet.sh` compares the first record against the flags it forwarded. `score_heldout` refuses a tag with mixed options. Prior art: Xu et al., OSDI'16 PCheck. Receipt **bf9cc1e25aa1**.
7. **Seed confounds.** `continue_from_checkpoint.main` gets a separate `--split-seed` and records `use_deterministic_algorithms(True, warn_only=False)` and `CUBLAS_WORKSPACE_CONFIG`. The r11 validation losses (0.635-1.094) come from ten different validation sets. Prior art: Dodge et al. arXiv:2002.06305, and the PyTorch reproducibility notes. Receipt **c54d197ed061**.

**What was gained:** a real held-out leak that both automated guards miss, the cause of the "unknown" SIGSTOP, and evidence that the "novel" column the variance study decides on counts problems whose near-duplicates are in the training corpus.
