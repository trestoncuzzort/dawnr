# Which pretrained weights go behind the gate, registered 2026-10-01 00:28Z

The operator, 2026-09-30: build on the ladders others have made; someone else's weights are fine,
but they must be the best for this job and usable by everyone. `internal/RESEARCH-2026-10-01-is-
the-bet-supported.md` shows why: with no training, pretrained models already put proved,
specification-checked answers through this gate on the clean 200, and the from-scratch core reads
zero. This file picks the weights by measurement instead of by reputation.

## Usable by everyone

Only weights whose model card states a licence that lets anyone use, change and redistribute them,
commercially too, and that are not gated. Read from the cards on 2026-10-01
(`huggingface.co/api/models/<id>`):

| candidate | parameters | licence | fits |
|---|---:|---|---|
| Qwen2.5-Coder-1.5B-Instruct | 1.5B | Apache-2.0 | any 8 GB card |
| Qwen3.5-2B | 2.3B | Apache-2.0 | any 8 GB card |
| Qwen3.5-4B | 4.7B | Apache-2.0 | 8 GB at 4-bit |
| Qwen2.5-Coder-7B-Instruct | 7.6B | Apache-2.0 | 8 GB at 4-bit, tight; 16 GB |
| Qwen3.5-9B | 9.7B | Apache-2.0 | 16 GB at 4-bit |
| Qwen2.5-Coder-14B-Instruct | 14.8B | Apache-2.0 | 16 GB at 4-bit |

Left out by the rule: Qwen2.5-Coder-3B (research licence), DeepSeek-Coder-V2 (its own licence),
StarCoder2 (OpenRAIL-M use restrictions), CodeGemma (gated, Gemma terms). Phi-4-mini (MIT) was
measured on 2026-09-19 and reads 4 tests passed and 1 proved on the clean 200; it stays as a
reference, not a candidate. The 27B (Apache-2.0) is the teacher, not a student: it does not fit
ordinary hardware.

## The measurement

The 100 dev problems of `t/r12-dev-ids.json` (disjoint from the held-out 232 and from every
training document), so the held-out set is not used to choose. Each candidate, served by ollama on
the desktop card at its default 4-bit quantisation, answers once per problem through the pipeline
every earlier pretrained run used:

    python3 t/spec_experiment.py generate --model <tag> --tag base-sel-<name> --pool v5 --prompt v5 \
        --ids-file dev-ids-100.txt --seed 1 --temperature 0 --num-predict 3072
    extract; tests; all seven kernels on the lab (t/grade_lab.sh); t/spec_check.py --n 100

Reported per candidate: answers that reach a task, pass the problem's tests, are verified by at
least one kernel with the twin refuted, by all seven, and all seven with the specification check.

## The rule, fixed before any answer

Rank by all-seven-and-specification-checked; ties by at-least-one-kernel, then by tests passed.
The best candidate that fits an 8 GB card is the student everyone can run; the best that fits
16 GB is the desktop student. If the 8 GB winner has at least half the 16 GB winner's tests
passed, the 8 GB one is the single base (one model for everyone beats two).

## Predictions

1. Every candidate passes the tests on at least 5 of the 100 (the from-scratch core: 0 to 1).
   Falsified by any candidate under 5.
2. The 14B code model passes the most tests. Falsified if a smaller or a general model beats it.
3. Some candidate that fits 8 GB reaches half the best candidate's tests passed. Falsified
   otherwise; then the base is the 16 GB winner and the 8 GB class waits for distillation.

## Amendment, 2026-10-01 01:02Z, before any fine-tuned answer: prompting cannot choose the small model

The generation half of the measurement above is in (the kernels are still grading it): on the 100
dev problems the candidates pass the tests on 0 (1.5B, 2B, 7B), 1 (4B), 2 (14B) and 4 (9B). None of
them knows `t`, so the instrument sits at its floor for everything that fits 8 GB and cannot rank
them. Prediction 1 is already falsified (five of six are under 5) and prediction 2 as well (the 9B
general model passes more than the 14B code model). The outcome section will say so.

What chooses the weights is therefore the measurement that matches how the weights will be used:
each small candidate is **fine-tuned on the same proved answers** and then asked the same 100
problems through the same gate.

- **Data.** `t/graded_pool.py` at `--min-kernels 1` over the 54 train-side answer sets on the lab:
  527 rows over 262 training problems (271 of them proved by all seven), none from a held-out,
  dev or policy-excluded problem (checked). Each row: tests pass, at least one kernel proves it and
  refutes its twin, no kernel refutes it, the specification agrees with the reference.
- **Recipe.** `t/student_sft.py` as committed (QLoRA, arXiv:2305.14314 B.2: NF4 4-bit, r 64,
  alpha 16, dropout 0.1, all linear layers, constant 2e-4, response-only loss; five epochs as SAFE,
  arXiv:2410.15756 C.3), seed 1, prompt `s1` (the task alone; a fine-tuned student needs no grammar
  text).
- **Candidates.** Qwen2.5-Coder-1.5B-Instruct, Qwen3.5-2B, Qwen3.5-4B first (the 8 GB class); the
  9B after them if the card has time.
- **Evaluation.** The adapter served on the 4-bit base it was trained on (`transformers serve`),
  prompt `s1`, temperature 0, seed 1, the same 100 dev problems, then extract, tests, seven
  kernels on the lab, the specification check.
- **Rule.** Unchanged: all seven and specification-checked first, then at least one kernel, then
  tests passed; the best 8 GB candidate is the base everyone can run.

Predictions for this half:

4. Every fine-tuned candidate passes the tests on at least 10 of the 100 (prompted: 0 to 1).
   Falsified by any under 10.
5. The fine-tuned 4B passes more tests than the prompted 9B (4) and the prompted 14B (2).
   Falsified otherwise.
6. Fine-tuning moves well-formed output most: every candidate reaches a valid task on at least 40
   of the 100 (prompted: 2 to 9). Falsified by any under 40.

**Correction to the evaluation line, 2026-10-01 01:08Z, before any fine-tuned answer.** The
server (`transformers serve`) does not load an adapter folder, so each adapter is folded into its
full-precision base (`t/student_sft.py --merge`, peft's `merge_and_unload` in bf16) and the merged
model is served in bf16, not on the 4-bit base. That is the form that would be released, so it is
the form measured. Reply budget 1,024 tokens (a `t` answer is a few hundred).

## Outcome of the prompted half, 2026-10-01 01:23Z

Six candidates, the 100 dev problems, prompt v5, temperature 0, one answer each; kernels on the
lab (12 cells), the specification check on every task-stage answer (100 draws).

| candidate | answers | reach a task | tests pass | some prover, none refuting | all seven | all seven, spec checked | some prover, spec checked |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen2.5-Coder-1.5B | 99 | 5 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.5-2B | 100 | 2 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.5-4B | 100 | 9 | 1 | 0 | 0 | 0 | 0 |
| Qwen2.5-Coder-7B | 100 | 4 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.5-9B | 100 | 12 | 4 | 1 | 0 | 0 | 1 |
| Qwen2.5-Coder-14B | 100 | 15 | 2 | 0 | 0 | 0 | 0 |

The 1.5B's server answered HTTP 500 on dev problem 621 at every attempt; that problem is
unanswered for it. The three Qwen3.5 models were asked with thinking off
(`t/spec_experiment.py --think off`); left on, they spend the reply budget thinking and return
nothing.

1. **Every candidate at least 5 tests passed: falsified.** Five of six are under 5.
2. **The 14B code model passes the most: falsified.** The 9B general model passes 4, the 14B 2.
3. **An 8 GB candidate at half the best: falsified.** The best is 4; the 4B has 1.

By the rule the 16 GB winner is **Qwen3.5-9B** (the only candidate with a proved,
specification-checked answer), and no 8 GB candidate is separable by prompting: the dev set is
73 sequence and string problems of 100 and none of these models has seen `t`. A correction to
the table of candidates: the 9B at 4-bit is about 6.6 GB, so it answers on an 8 GB card too; it
was listed as a 16 GB model for training, not for use. The fine-tuned half (the amendment above)
decides the small base and now includes the 9B.

**Two notes before the 9B's fine-tuned answers exist, 2026-10-01 01:42Z.** (1) The 9B is trained
at LoRA rank 16 instead of 64: the 4B at rank 64 already takes 14.7 GB of the 16 GB card, and
QLoRA reports that "LoRA r is unrelated to final performance if LoRA is used on all layers"
(arXiv:2305.14314 B.2, figure 4). Everything else is unchanged. (2) Answers are extracted with
`--promote-header` (608ac34a) for every fine-tuned candidate and the counts without it are given
beside them: a task that states `t 0` over a body that is well formed only as `t 1` is read as
`t 1`, since the format line is derivable.

## The 4B's fine-tune was damaged in its first steps; a stability probe, registered 2026-10-01 02:17Z

Three students have trained on the same 527 rows with the same command. Their logged losses:

| base | loss before training (first rows) | logged at step 5 (mean of steps 1 to 5) | step 160 | whole-run mean |
|---|---:|---:|---:|---:|
| Qwen2.5-Coder-1.5B | not measured | 0.730 | 0.079 | 0.151 |
| Qwen3.5-2B | 1.355 | 0.666 | 0.062 | 0.137 |
| Qwen3.5-4B | 0.890 | **9.793** | 0.724 | 1.780 |

The 4B starts better than the 2B (0.89 against 1.36, measured on the 4-bit base with a fresh
adapter) and its first five steps raise its loss elevenfold; it ends at 0.72, hardly below where
it began. That student is a damaged run and is **not a measurement of the 4B**. Its dev answers,
when they are scored, are recorded as that and kept out of the ranking.

What it is not. The 4B was the first run through `student_sft.response_loss` (a08bd1a8), which was
the obvious suspect. Measured on the real stack (4-bit base, k-bit preparation with gradient
checkpointing, a fresh rank-64 adapter), that function and the model's own forward-with-labels
give the same loss to four decimals on six rows, in train and eval mode, on the 2B (1.3550) and on
the 4B (0.8898). The function is not the cause. The run also completed all 165 steps on a 16 GB
card, which the first attempt could not: the memory change does what it was for.

What is not known: why. The learning rate is QLoRA's for its 7B and 13B models (2e-4, constant
from the first step, arXiv:2305.14314 table 9), applied here to other sizes for 165 steps; that
table lists 1e-4 for its larger models. Whether the first update at 2e-4 is what damages the 4B is
a hypothesis until it is measured.

**The probe.** The 4B, the same rows and seed (so every arm sees the same first batches), twelve
optimizer steps, the loss logged at every step (`--max-steps 12 --log-every 1`):

- A: constant 2e-4, no warm-up (the recipe as run)
- B: 2e-4 with a ten-step linear warm-up
- C: constant 1e-4
- D: constant 5e-5

**Stable**, fixed now: no step's loss exceeds 1.5 times the loss at step 1 (which is measured
before any update), and the mean of steps 8 to 12 is below the loss at step 1.

**Predictions.** (7) Arm A reproduces the damage: some step from 2 to 6 exceeds 1.5 times step 1.
Falsified if A is stable; then the account above is wrong and the cause is still open.
(8) At least one of B, C and D is stable. Falsified if none is; then the recipe needs more than a
schedule change.

**What follows.** The stable arm with the highest learning rate becomes the recipe, and all four
candidates are trained again with that one recipe so the comparison stays like for like. The
1.5B and 2B results already measured stand, labelled with the recipe they used. The 9B was
stopped before it trained.
