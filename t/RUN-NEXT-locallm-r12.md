# The next locallm run (r12): what it has to fix, what it changes, how it is judged

Written 2026-09-21 from six research passes run the same day (each source was
fetched and read, and filed as a research-first receipt whose id sits beside
it) and from the day's own measurements. Every number names the file or
command it came from. This supersedes `t/RUN-NEXT.md` for locallm runs; that
file is the recipe for a teacher-generation run and still holds for one.

## Where locallm actually stands

Split the 232 held-out problems into the **32 that have a same-task source in
locallm's own training data** (the list, with reasons, is
`t/DECONTAMINATION-2026-09-21.md`) and the **200 that do not**. Scored with
`t/score_heldout.py` over each half:

| arm | well formed (200) | **tests pass (200)** | clean (200) | clean (the 32) |
|---|---:|---:|---:|---:|
| locallm r4 / r5 | 179 / 170 | **0 / 0** | 0 / 0 | 2 / 2 |
| locallm r7, r7b greedy, r7b headed2, r8, r9, r9 seed 7 | 73-124 | **0** | 0 | 1-3 |
| locallm r9 seed 42 | 81 | **1** (`check_abundant`, spec disagrees) | 1 | 2 |
| locallm r10, regraded | 84 | **0** | 0 | 5 |
| Phi-4-mini | 8 | 5 | 2 | 1 |
| Qwen2.5-Coder-1.5B, untrained | 32 | 10 | 3 | 0 |
| DeepSeek-Prover-V2-7B | 28 | 6 | 3 | 3 |
| Qwen3-235B | 56 | 44 | 9 | 2 |

**locallm has never computed the right function for a problem its corpus does
not already answer.** Every clean answer it has produced is on the 32. That is
the number r12 exists to move: the first test-passing answer on the 200 is the
first evidence that it generalizes at all.

Why, from the same day's measurements:
- **The problem statement is invisible to much of training.** `Corpus.get_batch`
  cuts random 512-token windows from the concatenated corpus: ~23% of training
  tokens belong to a document whose `Problem:`/`Signature:` head was cut off,
  and the head sits at position 0, the only place generation ever puts it, in
  ~0.6% of windows. (research pass "training")
- **Three quarters of the corpus has no English.** 79 of 301 documents in
  `corpus-r8-headed.txt` carry a `Problem:` line; 222 lifted tasks have only a
  signature. (research pass "training")
- **Proven-but-wrong is mostly recitation of "attractor" programs.** 34-57% of
  proven-but-wrong answers are training programs with names erased; r8 wrote
  `r := a + b` for 15 different problems. 87 positives cover 15 signatures.
  (research pass "data growth")
- **The fine-tune overfits and nothing picks the stopping step.** Train loss
  0.12 against validation 0.9; validation loss is flat from step 150 to 300 in
  all ten r11 seeds, and does not track generation quality (LIMA,
  https://ar5iv.labs.arxiv.org/html/2305.11206, receipt 63eda36902d8).

## A. Blockers: fixed and tested before r12 trains

Each of these corrupted, or would have corrupted, a number this project
published. None is guarded today.

| # | defect | fix | test that proves it | prior art |
|---|---|---|---|---|
| A1 | **Held-out problems 269 and 626 are in every corpus since r7** as lifted `dafny_synthesis_task_id_N__*` tasks; `loop_locallm.mbpp_id` and preflight's `mbpp_(\d+)` miss that name, while `loop_dataset.py:91` already reads it | one `problem_id(name)` in `t/loop_filter.py` mapping `mbpp_N__`, `dafny_synthesis_task_id_N__`, `he_N__`, `apps_N__`; used by the corpus builder, preflight and `continue_from_checkpoint.py`, which refuse any held-out id | a test on the real names; preflight fails on today's `corpus-r8-headed.txt` | BigCode decontamination, content not ids (receipt bbd18e61a31d) |
| A2 | **32 held-out problems have same-task training sources** (8 identical references, 9 near-identical statements, 12 same functions found by execution, 2 lifted copies, 1 identity) | the 37 documents and 21 train ids in `t/DECONTAMINATION-2026-09-21.md` are dropped by the corpus builder and refused by preflight; `score_heldout.py` reports every arm on all 232 **and** on the clean 200 | the builder's count drops by 37 on r8's inputs; the scorer's clean-200 column reproduces the table above | Lee et al. dedup and StarCoder decontamination (a240a8bc7a10); Riddell arXiv:2403.04811 (e0cb51c91628) |
| A3 | **`t/AGREEMENT.md` holds 1 task**: a one-task `run_par.py` run overwrote the 43-task matrix in `a3c6f955`; the corpus builder reads it (`loop_locallm.py:204`), so a corpus built today silently loses the committed tasks | restore from `0bbc05cb` after checking no lowering changed since; `run_par.py` refuses to write the committed table when its task set is a strict subset, unless `--table` names another file | a subset run leaves `AGREEMENT.md` byte-identical | none needed beyond the restore; the guard is a refusal |
| A4 | **Partial answer sets can be graded and scored as whole** (sentinel means "exited 0", not "answered all") | `gen_fleet.sh` writes the sentinel only when answered ids equal the eval ids; `score_heldout.score` refuses fewer answers than eval ids without `--allow-partial` | a shard killed mid-run leaves no sentinel and the scorer refuses | Deequ `hasSize`/`isComplete` (e43dae1eaab5) |
| A5 | **Orphaned and frozen processes.** Prover process groups are killed only on timeout (`verifiers/__init__.py:152`); 12 then 26 orphan z3s ran for a day; the cpu-yield watcher froze the grader and exited without resuming it | kill the process group on every exit path; `t/stall_check.py` fails on any stopped process of ours, a live pid in `~/.local/share/cpu-yield/frozen.pids`, or output older than 27 minutes; cpu-yield resumes what it froze on exit | kill a grader mid-cell: no prover survives; stop a job: stall_check fails | BenchExec (29188ff4619a); Airflow zombie heartbeat (f519256b655f) |
| A6 | **Decoding settings not enforced** (the headline arm sampled at 0.5 because a flag was dropped) | `cmd_generate` has no temperature default and refuses to resume into records with other options; `score_heldout` refuses a tag with mixed options | a mixed-option set is refused | PCheck, OSDI'16 (bf9cc1e25aa1) |
| A7 | **One seed sets both data order and the validation holdout**, and the holdout is a shuffle of document ORDER, not "by hash" as `locallm/data.py`'s docstring says, so r9 and r10 differed by ~53 documents, not 1% | `--split-seed` separate from `--seed`; docstring corrected; run.json records `torch.use_deterministic_algorithms` and `CUBLAS_WORKSPACE_CONFIG` | two corpora of different length hold out the same documents at one split seed | Dodge arXiv:2002.06305 (c54d197ed061) |
| A8 | **SPARK `-j8` oversubscribes any sweep that is not `grade_lab.sh`** | `run_par.py` sets `T_SPARK_JOBS=1` when `--jobs > 1` unless set | a 24-job sweep stays under the core count | BenchExec (b55d4c4555c8) |
| A9 | **The gaming check reads the wrong examples**: `t/example_holdout.py` treats `points[:2]` as shown; the prompt shows `discriminative()`'s pair, different on 54 of 232 | read the pair the prompt used | the two agree on all 232 | CodeT arXiv:2207.10397 (c6c5684f31f5) |

## B. The data r12 trains on

Strict gate (`loop_dataset.positive_rejection`), decontaminated by A2.

| source | positives now | if finished | what is owed |
|---|---:|---:|---|
| the 21 contributing tags of r8's list | 94 (86 after A2) | same | nothing |
| `qwen235-train` | 0 | ~10-25 | the /dev/shm grade (206 of 401) is finishing; 195 never queued; spec check |
| `qwen235-train-p4` | 0 | ~10-20 | never extracted |
| `qwen235-v6new-p4` | 0 | up to 45 | `spec_check --pool v6`, a split-v6 build |
| `qwen235-v6new` | 0 | +2 | 15 corrupt raw files to repair or drop |
| `prover-train2` | 0 | up to 29 | its only table is from the reversed session: regrade `--no-cache` |
| 1.5B/27B tags with clean rows never spec-checked | 0 | up to 7 | `spec_check --pool v5` |
| lifted / committed | 167 / 26 after A2 | | A3's restore |

All of it is CPU; together about **190-210 positives**, against 86. (research
pass "data inventory")

Then, in order of evidence:
1. **Relabel verified programs with the problem they actually solve**: test each
   against every same-signature training problem's tests plus `spec_check`
   (CodeIt, 220M model, 49/400 against 24/400 for sample-and-filter,
   https://arxiv.org/html/2402.04858, receipt 71ab665c8b6a).
2. **English heads for the 222 head-less documents**, kept only if a fresh
   teacher answer to the English matches the program on the twin-separating
   inputs (Humpback: curated pairs keep improving, uncurated do not,
   https://arxiv.org/html/2308.06259, receipt dc3365f2a2eb).
3. **Not yet: self-training on locallm's own samples.** Every self-training paper
   starts from a competent model; locallm passes 0 of 200 (STaR, ReST-EM,
   receipt 91a634035caf).

## C. Recipe changes, tested as one bundle against the r11 baseline

| change | where | evidence |
|---|---|---|
| **every training row starts at a document boundary**, one whole document per row, padded with ignored targets | `continue_from_checkpoint.py --doc-batches` | removing truncation: +9.2% relative on program synthesis (Ding, https://arxiv.org/html/2404.10830, receipt 67f7ca3cf599) |
| **dropout 0.1** in the fine-tune | the existing `--dropout` flag | the one regularizer that helped under repeated data, 61.7 to 62.9 (Xue, https://arxiv.org/html/2305.13230, receipt 63eda36902d8) |
| **stopping step chosen by tests passed on a dev split** of 100 train-side problems absent from the corpus, never by validation loss | `--keep-every 50`, decode with `--ids-file`, tests only | LIMA and phi-1 both chose checkpoints by generation quality (63eda36902d8, afabd547c1da) |
| **cut each reply at the end of its task** | `locallm/model.py generate` | at least 73% of decode steps are spent past the median 318-character reply (research pass "inference") |
| **uniform soup of the seeds**, if `t/PREDICT-2026-09-21-soup.md` supports it | `locallm/soup.py` | model soups, arXiv:2203.05482 (b27d1ce80a89) |

Not in r12, each with its reason: loss masking of the head (a head-to-program
ratio of ~0.4 is where it moved nothing, receipt cb3d9202395a), LoRA (receipt
1b7c0e940167), NEFTune (gains come with 2.8x longer answers), a bigger core
before it is re-pretrained with tuned weight decay (receipt 5d66d7599d7f).

The training command, one per seed, after the T4 build of `continue_from_checkpoint.py`
(schema 2: the holdout follows `--split-seed` and a hash of each document, not `--seed`):

    ~/.venv-vllm/bin/python locallm/continue_from_checkpoint.py \
        --init <core> --data t/out/loop/corpus-r12-headed.txt --split t/out/loop/split-v5.json \
        --out t/out/locallm-r12-s<seed> --steps 300 --lr 3e-5 --block-size 512 \
        --doc-batches --keep-every 50 --dropout 0.1 --split-seed 1337 --seed <seed> --deterministic

`--split-seed 1337` is the same for every arm; the trainer refuses a holdout
under 8% of the characters (the hash split's size varies with the split seed:
6.1% to 12.4% on r8 across eight seeds), so if 1337 falls short on the final
corpus the next registered split seed is used and recorded. To reproduce a run
from before schema 2, pass `--split-by order --split-seed <its --seed>`.
`--deterministic` gave bit-identical 10-step runs on the lab CPU (29 of 29
tensors equal, metrics equal); on the GPU it is unmeasured until r12 trains
one seed twice and compares tensors. `--keep-every 50` at 300 steps writes six
fp32 copies of the ~93M core, about 370 MB each, per seed.

## D. Sampling and selection: a pilot first

Keep the greedy column exactly as today. Add a pilot on 20 held-out problems:
64 samples per problem, batched with a stop rule, timed at 1, 16 and 64.
Continue only if some problem gains coverage. Selection sees only the two
examples the prompt shows (A9), never the third test, the reference or the
kernels: keep samples that pass both, then the largest group that agrees on 24
drawn inputs (AlphaCode, CodeT, MBR-exec, receipt c6c5684f31f5). Phi gets the
same samples and selector. The seven provers stay the final gate; they cannot
choose, because a proof of the model's own spec cannot tell the right function
from a wrong one (AlphaVerus, receipt cba81bca0541).

## E. How r12 is judged

(research pass "statistics", receipts e89423ae63a6, 2805f36ed185, ef7fc0d2a1a8,
e5060fc9ac04)
- **Primary metric: tests pass and clean on the clean 200**, reported beside all
  232 and split recited/written.
- **Seeds:** at least 10 per arm (a +3 difference needs 5-10, +2 needs 10-20,
  +1 is not resolvable on 232 problems). Report "mean [min-max] (n seeds)",
  never one run.
- **Test:** exact one-sided permutation test over seeds on the mean; Wilson
  intervals for single checkpoints; McNemar mid-p only for two fixed
  checkpoints.
- **Verdict** (eval-stats.md protocol step 4, computed by `t/compare_arms.py`):
  ADOPT if the permutation p is at most .05 **and** the upper bound of the
  bootstrap interval on P(B>A) is above .75; NOT MEANINGFUL if that upper bound
  is at most .75; otherwise INCONCLUSIVE, claimed as nothing. P(B>A) counts a
  tie as 1/2. This departs from Bouthillier et al. (arXiv:2103.03098) twice, on
  purpose: significance comes from the exact permutation p, not from the
  interval's lower bound above .5, and ties are not dropped, because counts of
  0-6 tie constantly. Two single checkpoints get McNemar and no recipe verdict.
- **Commands** (run step 9): `python3 t/score_heldout.py --split
  t/out/loop/split-v5.json --outcomes t/out/r12-outcomes.json <every seed tag>`
  then `python3 t/compare_arms.py --outcomes t/out/r12-outcomes.json --arm
  base=... --arm new=... --prereg t/PREDICT-r12.md`, where the prediction file
  carries one line `seeds: N` (and optionally `metric:` and `problems:`), so
  the comparison refuses to run on any other number of seeds. A tag with fewer
  than 232 answers is refused by both scripts unless `--allow-partial`, and a
  tag whose records mix decoding settings is refused outright.
- **One look.** Predictions registered in a `t/PREDICT-*` file before training;
  the 232 are looked at once per decision. Exploration uses the dev split.

## F. The run, step by step, and which steps a script checks

| step | check | AUTOMATED / MANUAL today | after A |
|---|---|---|---|
| 0 | lab quiet: nothing of ours stopped, no orphan provers, `frozen.pids` empty, load under the core count, no fleet during grading | MANUAL | AUTOMATED (A5) |
| 1 | desktop and lab at one commit | warns only | refuse |
| 2 | `bash -lc 'python3 t/preflight.py --split t/out/loop/split-v5.json --strict'` on the lab | AUTOMATED | + A1, A2, A3 |
| 3 | predictions registered | MANUAL | MANUAL |
| 4 | corpus: excluded ids logged, example count equals input rows, no held-out id by any name, decontamination applied, `head_align` unparsed 0 | MANUAL | AUTOMATED (A1, A2) |
| 5 | train: run.json `complete`, `schema` 2, corpus sha matches, `identities.split_seed` present and `identities.split.by` = `hash`, `identities.reproducibility.use_deterministic_algorithms` true, `identities.batches.kind` = `documents` with its cut counts | MANUAL | AUTOMATED (A7) |
| 6 | generate: 232 records per arm, one set of options | MANUAL | AUTOMATED (A4, A6) |
| 7 | grade: `--no-cache` for any regrade, table rows equal tasks | MANUAL | partly (A4) |
| 8 | spec check on one machine, no "NOT CHECKED" | MANUAL | MANUAL |
| 9 | score: all 232 and clean 200, recited/written, mean over seeds | MANUAL | AUTOMATED (A2, E) |

## What r12 is predicted to show

Registered separately, before training, in `t/PREDICT-...-r12.md`. The number
that matters: **tests pass on the clean 200, today 0 in nine of ten arms.**
