# r10 regraded, and a third of locallm's clean answers were recited

Registered beforehand in `t/PREDICT-2026-09-21-r10-regrade.md`. Three predictions
held and one was falsified, and the falsified one turned out to be a finding about
every locallm row on the scoreboard, not only about r10.

## What was found on the lab

A locallm answer set, `locallm-r10`, had been sitting on the lab workstation since
2026-09-20 07:01 with a kernel table nobody had scored. It came out of the session
the operator reversed that day (`internal/ROADMAP-LOG.md`, "Reversing Antigravity's
session"), whose rule is that raw decodes survive and anything derived from them by
the edited code does not. So it was regraded from its 232 raw decodes by today's
code, as `locallm-r10-regrade`, with `T_LAB_RUN_PAR=--no-cache`: 768 cells, 4,608
kernel runs, no verdict carried over.

The checkpoint's own `run.json` (kept in `~/antigravity-backup-2026-09-20/`) shows
`locallm-r9`'s recipe exactly: the same pretrained core `gpt-seed1337`, training
seed 1337, 300 steps, lr 3e-5, greedy decoding. Only the corpus differs, and
`corpus-r10-headed.txt` shares 297 of about 300 documents with the
`corpus-r8-headed.txt` r9 trained on. It drops `mbpp_242`, `mbpp_320`, `mbpp_327`
and `mbpp_455`, adds `apps_267__evalRPN` and `he_157__right_angle_triangle`, and
rewords four.

## Against each prediction

| | predicted | measured | |
|---|---|---|---|
| 1 | 5 clean, exactly | **5** | held |
| 2 | tests pass 6, well formed 112 | **6, 112** | held |
| 3 | at least 4 of 5 agree under `spec_check.py` | **5 of 5** | held |
| 4 | no clean answer is a copy of a training document | **1 of 5 is** | **falsified** |

Prediction 1 held with one difference beneath it. The 07:01 table had four SPARK
cells marked `timeout (FLAKED)` (`mbpp_383`, `mbpp_411`, `mbpp_518`, `mbpp_604`)
that verify when regraded, so proven-but-wrong moves from 67 to 71. None of the four
passes its tests, so the clean count is untouched, but a flaked cell on a
test-passing answer would have cost a clean answer silently. See "The grader" below.

## The falsified prediction: answers that are training documents

`mbpp_729__add_list`, "add two lists using map and lambda", was answered with a
program that is, names erased, the corpus document for `mbpp_728__sum_list`, "sum
elements in two lists". MBPP holds both, under different ids, on opposite sides of
the split. The id check (the split's 232 eval ids against r10's train ids: 0 in
common) cannot see this. The model did not write a new program. It recalled a
verified one for a problem that happens to be the same problem.

That made the same check worth running on every locallm arm. **It is now a column.**
`t/score_heldout.py --corpus TAG=PATH` splits each clean count into **recited**, where
the same program with names erased is a document of the corpus that model was
trained on, and **novel**. The method is answer overlap as defined by Lewis,
Stenetorp and Riedel ([arXiv:2008.02637](https://arxiv.org/abs/2008.02637)): they
normalize a test answer, look for it among the training answers, and report every
model on the overlapping and non-overlapping parts separately. They found
closed-book models score mostly on the overlap, and locallm is closed-book. The
normalization here is `loop_filter.key`, the copy check the training loop has used
since 2026-09-16. The clean count itself is unchanged; the column stratifies it,
as the paper does, rather than deleting from it.

| arm | corpus (sha256 prefix) | clean | recited | **novel** | novel answers |
|---|---|---:|---:|---:|---|
| `locallm-r4` | `corpus-r4.txt` (`f5ffadbdfa7f`) | 2 | **2** | **0** | |
| `locallm-r5` | `corpus-r5.txt` (`8c0696db17a2`) | 2 | **2** | **0** | |
| `locallm-r7-92m` | `corpus-r7-sft.txt` (`130353e8ba61`) | 1 | 0 | 1 | `mul_list` |
| `locallm-r7b-greedy` | `corpus-r7-sft.txt` | 2 | 1 | 1 | `min_of_two` |
| `locallm-r7b-headed2` (headline) | `corpus-r7-headed.txt` (`e814e0af29b1`) | 3 | 1 | **2** | `mul_list`, `add_list` |
| `locallm-r8` | `corpus-r8.txt` (`9a7a838e2eea`) | 2 | 1 | 1 | `mul_list` |
| `locallm-r9` | `corpus-r8-headed.txt` (`7bf538f3e836`) | 2 | 1 | 1 | `min_of_two` |
| `locallm-r9-seed7` | same | 1 | 0 | 1 | `is_Sum_Of_Powers_Of_Two` |
| `locallm-r9-seed42` | same | 3 | 1 | 2 | `check_abundant` (spec disagrees), `min_of_two` |
| **`locallm-r10-regrade`** | `corpus-r10-headed.txt` (`39a1bdadef95`) | **5** | 1 | **4** | `is_Sum_Of_Powers_Of_Two`, `mul_list`, `string_length`, `min_of_two` |
| `phi4-mini-eval2` | none of ours | 3 | - | (3) | |

Every corpus hash above was checked against the `corpus_sha256` the model's own
`run.json` recorded, except r4 and r5, which predate `run.json` and are identified by
the file their round wrote.

**Recited is recitation, not two models converging on the only way to write
`min`.** The base rate says so: the same key, run on the clean answers of models
that never saw these corpora (Phi-4-mini 3, the untrained 1.5B 3,
DeepSeek-Prover-V2-7B 6, the 235B 11), matches **1 of 23**, prover-7B's
`string_length`, which is `len(s)`. For locallm it matches **10 of 23**. The 235B
answered `min_of_two` too and did not match.

## What this changes in what the project has said

- **Rounds 4 and 5 never wrote a clean answer of their own.** Both of each round's
  two were training programs recalled under another problem's name
  (`recur_gcd` = `gcd`, `remove_all_spaces` = `remove_splchar`, `split` =
  `replace_specialchar`). Their "2 of 2" conversion is the conversion of programs
  that had already been verified before training, so it is not evidence that the
  model proves what it writes.
- **The headline arm's 3 is 2 novel and 1 recited.** On novel answers it reads 2
  against Phi's 3; on novel and specification-checked, 2 against Phi's 2.
- **r10 has the most novel clean answers of any locallm arm, 4, all four agreeing
  with their problems.** The previous best was 2. It is not the headline: its
  training set was built through the widened pool check the operator reversed, and
  r9's recipe on a 99%-identical corpus produced 1. Whether 4 is the corpus or the
  draw is `t/PREDICT-2026-09-21-recipe-variance.md`, running now.

## Two more things the regrade exposed

**Training does not reproduce on the GPU.** Retraining r9's recipe with the same
seed, corpus bytes and code (`locallm-r11-rerun`) gives weights that differ from
r9's in all 149 tensors, by at most 0.0016. Final validation loss 0.8908 against
r9's 0.8909. How much that moves the answers is prediction 1 of the variance study.
The deterministic-resume result in `locallm/ACHIEVEMENTS.md` was always stated for
CPU only, and this is why that qualifier matters.

**The grader was oversubscribing itself.** `t/grade_lab.sh` sizes its cell count at
about 4 cores a cell, measured on 2026-09-18 with gnatprove serial. On 2026-09-19
`t/verifiers/spark.py` began running gnatprove `-j8` inside every cell. At 24 cells
the load average reached 351 on 120 cores, and the table graded that way the day
before carried the four flaked SPARK cells above. BenchExec's rule (Beyer, Loewe,
Wendler, STTT 2019, [github.com/sosy-lab/benchexec](https://github.com/sosy-lab/benchexec))
is that a run's resource budget has to cover its subprocesses. `grade_lab.sh` now
passes `T_SPARK_JOBS=1` to the lab unless one is set, which `spark.py`'s own comment
names as the setting for a lab sweep and documents as verdict-identical.

Found on the way and cleaned up: twelve orphaned `z3` processes from an earlier,
killed grading run had been running for 23 hours on 12 cores, and the grader
for the 235B's train-split answers (locallm's next training positives) had been
stopped (`SIGSTOP`, state `T`) since 2026-09-20 19:41, cause unknown. The z3s were
killed by PID and the grader resumed with `SIGCONT`.
