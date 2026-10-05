# The teacher round on a rented GPU: registered before any sample is drawn

> **Correction, 2026-10-05:** counts on the clean 200 in this file include 18 problems that an audit of the training rows
> later took out of the panel. Every published row is restated on the clean 182 in
> [DECONTAMINATION-2026-10-05.md](DECONTAMINATION-2026-10-05.md).

Registered 2026-09-30 (the day before the run) by the operator's standing direction to keep with
the plan. `t/EXPERT-ITERATION-2026-09-26.md` staged a teacher round and generated nothing: the
27B teacher needs a 30 GB card and the shared ones never had it. r12's core then judged flat and
its base rate by sampling read zero (`t/PREDICT-2026-09-30-dawnr-r12-core.md`,
`t/PREDICT-2026-09-30-dawnr-base-rate.md`), which leaves the proved corpus as the lever and a
teacher as the only source of new agreeing answers. `locallm/cloud_serve.py` now serves the same
teacher on one rented H100 within the month's free credit, so the round runs as designed.

## The run

- **Teacher:** `Qwen/Qwen3.8-27B-FP8` (the model behind every `qwen3.8-27b-fp8*` arm on the
  scoreboard), vLLM 0.29 on one rented H100, weights already cached in the rented volume; the
  pipeline's own client (`t/spec_experiment.py chat`, `--api openai`, bearer key). k = 8 samples
  per prompt at temperature 0.7, seeds 1 to 8: the `qwen3.8-27b-fp8-v3-s2` precedent.
- **Specification prompts:** the 442 gated vericoding specifications
  (`t/out/rl-2026-09-26/spec-pool/prompts.jsonl`, `gated.jsonl`), `rl_teacher_expert_iter.py
  sample-spec --k 8 --temperature 0.7 --tokens 1024`, then `score-spec` (Dafny, on the lab's CPUs).
- **Training-problem prompts:** 356 ids staged by `t/stage_teacher_prompts.py` against the r12
  corpus on 2026-09-30 (372 MBPP/HumanEval RL ids, 76 named in the corpus and left out, 296 kept,
  plus 60 APPS ids sampled with seed 2026; held-out, dev and decontamination exclusions applied by
  `rl_reward.rl_prompt_ids`), `spec_experiment.py generate --pool v5 --prompt v5 --num-predict 3072
  --temperature 0.7 --seed N --tag rl-teacher-s<N>` for N = 1..8, then `consolidate-training` and
  `rl_feasibility.py score` (the tiered reward; Dafny in the loop).
- **Assembly:** `rl_teacher_expert_iter.py assemble`: every answer at the reward's top tier is
  re-graded in all seven kernels with the twin gate and the repaired specification check
  (`t/spec_check.py`, 2026-09-30), and what passes becomes candidate documents under
  `t/out/spec-experiment/rl-teacher-verified` and the spec-pool destination.
- **Budget:** the rented server is stopped by the run script when generation ends and by a
  watchdog at 3 hours regardless; the expected serving time is one to two hours (about $4 to $8).
  Nothing runs before the month's credit is confirmed renewed; the free limit is not crossed.

## Predictions

1. **At least 100 of the 356 training problems have a sample that passes the problem's own
   tests** (the tests tier). The teacher passed tests on 81 of 232 held-out problems at one
   sample; eight samples on training-side problems of the same sources should reach more.
   Falsified below 100.
2. **At least 60 of the 356 have a sample that passes its tests and agrees with the
   specification check** on drawn inputs. Falsified below 60.
3. **At least 40 of the 442 specification prompts have a sample at the reward's top tier**
   (proved by Dafny against the given specification). The policy managed 1 of 120. Falsified
   below 40.
4. **The assembled set adds at least 50 documents clean in all seven kernels** to the proved
   corpus (569 with graded trust today). Falsified below 50.

## What each outcome decides

- Predictions 1, 2 and 4 hold: a corpus registration follows that adds the new documents, the
  specification documents and the relabel rows the r12 corpus left out, and the next locallm round
  trains on it; the base rate is measured again on that model.
- 1 holds and 4 fails: the teacher solves the problems but the proof gate or the twin gate rejects
  its specifications; the gap between 1 and 4 is reported per gate before anything else is tried.
- 1 fails: the prompt or the pool is the problem; the precedent arm's settings are re-checked
  before a second round.

## What it cannot show

The teacher has read the public MBPP and HumanEval; some of its answers will be recall. The
held-out 232 are never prompted, so the scoreboard stays clean, but a document admitted here is
admitted for being proved, not for being novel, and the clean-200 gate stays where it is.

## Launch note, 2026-10-01 01:52Z (before any teacher sample)

- **Credit.** The provider's own billing summary reads October's metered cost as 0.00 and
  September's as 32.19 against 30.00 of credit, 2.07 billed: the last month ran over the free
  limit by 2.07, which the running estimate (about 27) had not shown. From this run on the limit
  is enforced against the billing summary itself, not an estimate: a guard reads it every ten
  minutes and stops the server at 14.00 metered for the month, well inside the 30.00.
- **What the samples are for now.** The direction changed on 2026-10-01
  (`internal/LADDER-PLAN-2026-10-01.md`): the answers this round's gate admits train a pretrained
  student (`t/graded_pool.py`, `t/student_sft.py`), not the from-scratch core. The generation
  commands, the prompts and the four predictions above are unchanged; the corpus re-registration
  the text mentions is replaced by the student's pool, at every trust level with the level
  recorded.

## Stopped, 2026-10-01 02:22Z: not an outcome

The operator's instruction at 02:21Z: use our own machines; no outside compute unless it is
Google or AWS. The rented server was stopped at once (the provider lists the app as stopped and
nothing deployed), 30 minutes after launch and 19 minutes after it became healthy. October's
metered cost at the stop reads 2.36, all of it credit, 0.00 billed.

What exists: 74 of the specification-prompt sample files on the lab
(`t/out/rl-2026-10-01/specpool/samples`); none of the eight training-problem answer sets was
started. Nothing was scored. **None of the four predictions above was tested**, and this round is
not a result. A teacher round on our own hardware, with whatever model fits it, is a new
registration with its own predictions; these stand unresolved.
