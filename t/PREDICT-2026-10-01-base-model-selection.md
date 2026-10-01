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

## Outcome for the first two fine-tuned students, 2026-10-01 02:19Z

Qwen2.5-Coder-1.5B and Qwen3.5-2B, each fine-tuned on the 527 rows (standard loss, healthy loss
curves, 0.73 to 0.08 and 0.67 to 0.06), merged, served, one answer per dev problem under prompt
`s1`, extracted with `--promote-header`, all seven kernels on the lab (exit 0, both tables
written), the specification check on every task-stage answer (100 draws), scored by
`t/score_levels.py`.

| candidate | reach a task | tests pass | proved by at least 1, spec checked | at least 3 | at least 5 | all seven |
|---|---:|---:|---:|---:|---:|---:|
| Qwen2.5-Coder-1.5B, prompted (v5) | 5 | 0 | 0 | 0 | 0 | 0 |
| Qwen2.5-Coder-1.5B, fine-tuned | 23 | 4 | **1** | 1 | 0 | 0 |
| Qwen3.5-2B, prompted (v5) | 2 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.5-2B, fine-tuned | 45 | 4 | **1** | 1 | 0 | 0 |
| the two students pooled | 54 | 7 | 1 | 1 | 0 | 0 |
| Qwen3.5-9B, prompted (v5), for reference | 12 | 4 | 1 | 1 | 0 | 0 |

Without `--promote-header` the students reach a task on 17 and 42 and pass the tests on 3 and 4.

4. **Every fine-tuned candidate at least 10 tests passed: falsified.** Both pass 4.
6. **Every candidate a valid task on at least 40: falsified.** The 1.5B reaches 23; the 2B, 45.
5. Not yet measurable: the 4B has no sound run (see the stability probe above).

**Reading.** Fine-tuning taught the language and not the problem. The 2B went from 2 valid tasks
to 45, and through the gate each student has one proved, specification-checked answer in a
hundred, the same as the untrained 9B. Of the 68 task-stage answers the two students wrote, the
specification agrees with the problem's reference on 6 and disagrees on 57: they write well-formed
`t` whose `ensures` describes a different function. That is the step
`internal/RESEARCH-NEXT-2026-09-20.md` named (English to specification), and 527 rows did not
move it at this size.

**What the instrument can and cannot say.** By the registered rule the two students tie on every
criterion (0 at seven, 1 at one prover, 4 tests passed). One answer per problem on 100 problems
cannot rank bases whose proved rate is about one percent: the differences it would show between
further candidates are one or two problems. Ranking needs more successes to count, which means
several answers per problem with the gate as the filter (SAFE reports its 1.3B backbone at 21.6%
with one answer and 40.3% with ten, arXiv:2410.15756 table 8). That measurement is registered
separately before it runs.

## Correction, 2026-10-01 02:33Z: the 4B run was not damaged; the logging was wrong, and it was my change

The section above ("The 4B's fine-tune was damaged in its first steps") is wrong in its title, its
table's reading and its account. It is left in place as written; this replaces it.

**What the probe showed.** Three arms ran on the code as it was (A constant 2e-4, B with a
ten-step warm-up, C constant 1e-4); D was stopped. All three log the same loss at step 1, 16.564,
and step 1 is logged before any update. From there each only falls (A to 3.55, B to 4.66, C to
4.23 by step 12). Nothing raises the loss; it starts there.

7. **Arm A reproduces the damage: falsified.** No step exceeds step 1. There was no damage to
   reproduce.
8. **At least one of B, C, D is stable:** true and empty, since A is stable too.

**The cause, from the library's source.** `transformers/trainer.py` divides a micro-batch's loss
by the accumulation count only when the model does not take loss arguments or no token count is
given, and says of a custom loss: "If you are not using `num_items_in_batch` when computing your
loss, make sure to overwrite `self.model_accepts_loss_kwargs` to `False`." The library's own
loss (`loss/loss_utils.py`, `fixed_cross_entropy`) sums the token losses and divides by the
window's token count. The `compute_loss` override added in a08bd1a8 ignored that count and
returned each row's mean, so with sixteen accumulated rows the logged loss was the SUM of sixteen
row means and the gradient before clipping was sixteen times too large. Earlier tonight this
file said the loss change "is not the cause". That was wrong: the function's value was checked
and is right; how the override met the trainer was not checked, and that is where the fault was.
Fixed: `response_loss` takes the count and reduces as the library does (a test pins it).

**Measured afterwards.**

- One step of the corrected code on the same first batch logs 0.651 where the old code logged
  16.564, a factor of 25.4, not 16. Sixteen accounts for the sum; the rest is that the old code
  averaged over rows and the library averages over tokens. On 66 training rows the untrained 4B
  reads 0.998 as a mean of row means and 0.808 token-weighted (a ratio of 1.23), so the direction
  is measured; that it makes up all of the extra factor on that one batch is not.
- **The 4B student is sound.** Plain forward passes on 66 training rows, no trainer involved:

  | | mean of row means | token-weighted |
  |---|---:|---:|
  | 4B, untrained | 0.998 | 0.808 |
  | 4B student | 0.042 | 0.038 |
  | 2B, untrained | 1.341 | 1.132 |
  | 2B student | 0.061 | 0.048 |

  It fits the training rows better than the 2B student does.

**What the 4B student's result is.** A valid measurement, with one difference from the other two
stated beside it: it was trained on the row-weighted loss with the oversized, clipped gradient;
they were trained on the library's token-weighted loss. On the 100 dev problems it reaches a
task on 35 and passes the tests on 4 (extracted with `--promote-header`). Its answers went to
the provers at 02:31Z.

**So far, three bases from 1.5B to 4B, each fine-tuned on these rows, pass the tests on 4, 4 and
4 of 100.** The best training fit (the 4B) writes fewer valid tasks than the 2B (35 against 45)
and passes no more tests.

**Decisions taken on the wrong reading, and undone.** The 4B's answers were held out of the
ranking: they are in. The 9B was stopped before training: it was restarted at 02:31Z with the
corrected loss and ran out of memory at its second step (13.9 GiB allocated, a further 1.5 GiB
asked for, 16 GB card, rank 16, response-only output layer). It has no result. The four-schedule
probe answered a question that did not exist; its numbers are kept in
`~/scratch/student/probe/`.

## Outcome for the fine-tuned 4B, 2026-10-01 03:02Z

The 4B student's answers (the run of the correction above: trained on the row-weighted loss with
the oversized, clipped gradient; the other two on the library's token-weighted loss) went through
the same gate: all seven kernels on the lab (exit 0, table written), the specification check on
every task-stage answer (100 draws: 7 agree, 26 disagree, 2 could not be checked), scored by
`t/score_levels.py`. The evidence record was saved before the check and restored after it.

| candidate | reach a task | tests pass | proved by at least 1, spec checked | at least 3 | at least 5 | at least 6 | all seven |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3.5-4B, prompted (v5) | 9 | 1 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.5-4B, fine-tuned | 35 | 4 | **3** | 2 | 1 | 0 | 0 |
| Qwen3.5-2B, fine-tuned | 45 | 4 | 1 | 1 | 0 | 0 | 0 |
| Qwen2.5-Coder-1.5B, fine-tuned | 23 | 4 | 1 | 1 | 0 | 0 | 0 |
| the three students pooled | 62 | 10 | 4 | 3 | 1 | 0 | 0 |
| the three students and the prompted 9B pooled | 64 | 12 | 4 | 3 | 1 | 0 | 0 |

5. **The fine-tuned 4B passes more tests than the prompted 9B and the prompted 14B: falsified.**
   It passes 4, the same as the prompted 9B (and more than the 14B's 2).

**Answer by answer.** The 4B's four test-passing answers, by kernel (`verified / refuted` counts
toward the level; anything else does not):

| problem | specification | kernels that prove it and refute its twin | the others |
|---|---|---|---|
| 449 `check_Triangle` | agrees | Dafny, Verus, SPARK, Frama-C, Lean (5) | Rocq proves it and leaves the twin unproved; F\* leaves it unproved |
| 727 `remove_char` | agrees | Dafny, SPARK, Frama-C, F\* (4) | Verus unproved; Lean and Rocq time out |
| 459 `remove_uppercase` | agrees | Verus, SPARK (2) | Dafny and Lean prove it and time out on the twin; Frama-C and F\* abstain; the task is too big for the Rocq lowering |
| 92 `is_undulating` | disagrees | Frama-C (1) | six leave it unproved; not counted: its specification is not the problem's |

The first two students' one proved answer is the same problem for both (543 `count_digits`, four
kernels, the same one the prompted 9B proves). So the three students answer four different
problems at the first level, and no answer of any of them is proved by six or seven kernels.

**The rule's reading.** All three are at zero for all seven, so the tie goes to at-least-one-kernel:
the 4B has 3, the other two 1 each. By the rule fixed before any answer, **Qwen3.5-4B is the base**
for the 8 GB class, and it is the best measured candidate for the 16 GB class too (the 9B has no
fine-tuned result: it does not fit the card for training at these row lengths).

**What that reading is worth.** The rule picks; the instrument has not shown a difference. The
4B and the 2B differ on four problems (three only the 4B answers, one only the 2B); an exact
paired test on four discordant problems gives p = 0.63. The 4B's specification agrees with the
reference on 7 of the 33 it could be checked on, the first two students' on 6 of 63: more often,
on counts this small. What it does establish: 25 of the 4B's 35 valid tasks fail their problem's
tests and 26 of 33 carry a specification that is not the problem's, the same failure as the
smaller students, at the best training fit of the three. Size from 1.5B to 4B did not move the
step from English to the right specification on 527 rows.

**What follows.** The 4B is the base for the runs after this one. The specification-given
measurement already training on the 2B (`t/PREDICT-2026-10-01-spec-given.md`) finishes as
registered; the ranking between bases is settled by counting more successes (several answers per
problem with the gate as the filter), registered separately before it runs.

## Where the students' 300 answers stop, counted 2026-10-01 03:10Z; a correction to "they learned the language"

Every answer of the three students, by the first gate it fails (from each set's
`extract.json`, `tests.json` and the specification-check verdicts):

| | 1.5B | 2B | 4B | all | share |
|---|---:|---:|---:|---:|---:|
| does not parse | 45 | 43 | 54 | 142 | 47% |
| parses, not well formed | 32 | 12 | 11 | 55 | 18% |
| a valid task | 23 | 45 | 35 | 103 | 34% |

The 103 valid tasks, two ways:

| tests | | specification against the reference | |
|---|---:|---|---:|
| pass | 12 | agrees | 13 |
| fail | 76 | disagrees | 83 |
| signature differs, undefined, or outside its own `requires` | 15 | could not be checked | 7 |

Six answers have both (tests pass and the specification agrees); five of those are proved by at
least one kernel. Six pass the tests on a specification that is not the problem's, and five carry
the right specification over a program that fails the tests.

**The correction.** The outcome above and the README said the students "learned the language"
and that the specification is the failing step. The count does not support the first half: two
answers in three are not valid `t` at all. Fine-tuning raised valid tasks from 2 to 9 of 100 to
23 to 45, and it stopped there. The failing parse errors are not typos. They are constructs the
language does not have or spells another way, on problems whose natural statement needs them:
the 4B writes `seq of seq` for a nested result (9 answers), a Python-style comprehension inside
`sum([...])` (8), a quantifier where an expression must start (4). The 527 training answers come
from 262 problems the earlier models could already prove, which are the easy ones; the dev
problems are 73 sequence and string problems of 100. So the measured order of losses is: the
language's sequence and specification-function idioms first (197 of 300 answers), then the
program and the specification together (76 of 103 valid tasks fail the tests, 83 of 96 carry a
wrong specification), then the proof.

What follows from the count: rows that show those idioms are the lever, and the specification-given
rows in the next training set (476 lifted programs with recursion, loops and specification
functions) are the first test of that; the dev result of the student trained on them is
prediction 12 of `t/PREDICT-2026-10-01-spec-given.md`.

## Two instrument faults touch this file's tables, 2026-10-01 04:17Z

Found while following the students' answers gate by gate (the section above).

**The test harness.** `run_point` refused an answer that declared a nested parameter `seq<seq>`
(fixed in cf84b8ea). Of this file's answer sets it touched six answers of three prompted
candidates, and three of them pass their problem's tests once read correctly: the 4B and the 9B
on dev problem 186, the 14B on 450. The fine-tuned students were not touched (they did not write
`seq<seq>`).

**The specification check.** It could not check the 9B's answer to 186 (the problem's solution
returns None when given no patterns); repaired and registered in
`t/PREDICT-2026-10-01-spec-check-coverage.md`.

Both tables again, under the repaired check and with the refused answers read (the registered
tables above stay as measured):

| candidate | reach a task | tests pass | proved by at least 1, spec checked | at least 3 | at least 5 | at least 6 | all seven |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen2.5-Coder-1.5B, prompted | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.5-2B, prompted | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.5-4B, prompted | 9 | 2 (was 1) | 0 | 0 | 0 | 0 | 0 |
| Qwen2.5-Coder-7B, prompted | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.5-9B, prompted | 12 | 5 (was 4) | **2** (was 1) | 2 | 1 | 1 | 0 |
| Qwen2.5-Coder-14B, prompted | 15 | 3 (was 2) | 0 | 0 | 0 | 0 | 0 |
| Qwen2.5-Coder-1.5B, fine-tuned | 23 | 4 | 1 | 1 | 0 | 0 | 0 |
| Qwen3.5-2B, fine-tuned | 45 | 4 | 1 | 1 | 0 | 0 | 0 |
| Qwen3.5-4B, fine-tuned | 35 | 4 | 3 | 2 | 1 | 0 | 0 |
| all nine pooled | 69 | 15 | 5 | 4 | 2 | 1 | 0 |

The rule's pick among the fine-tuned candidates is unchanged. What changes is the reference
beside it: the untrained 9B, prompted, has 2 proved and specification-checked answers of 100, one
of them by six kernels, against the fine-tuned 4B's 3. Prediction 5 ("the fine-tuned 4B passes
more tests than the prompted 9B") now reads 4 against 5 and stays falsified.

**The denominator.** Nine of these 100 dev problems cannot be passed by any task: their own
tests disagree about the type at one position (a one-character string is read as an integer, a
longer one as a sequence; 6 in the result, 3 in an argument), and no answer set has ever passed
one. Every count in this file is of 100 with at most 91 reachable. The held-out 200 has two
such problems. Not repaired here: it changes the pool, so it needs a new pool version and a
re-measurement.

## The dev table under all three instrument repairs, 2026-10-01 05:05Z

A third fault surfaced after the section above: a one-character string in a test was read as an
integer, so a string parameter or result failed such a test
(`t/PREDICT-2026-10-01-spec-check-coverage.md`, the amendment). This table replaces the one in
the section above; the registered tables further up stay as measured.

| candidate | reach a task | tests pass | proved by at least 1, spec checked | at least 3 | at least 5 | at least 6 | all seven |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen2.5-Coder-1.5B, prompted | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.5-2B, prompted | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.5-4B, prompted | 9 | 3 | 0 | 0 | 0 | 0 | 0 |
| Qwen2.5-Coder-7B, prompted | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3.5-9B, prompted | 12 | 6 | 2 | 2 | 1 | 1 | 0 |
| Qwen2.5-Coder-14B, prompted | 15 | 4 | 0 | 0 | 0 | 0 | 0 |
| Qwen2.5-Coder-1.5B, fine-tuned on the 527 rows | 23 | 4 | 1 | 1 | 0 | 0 | 0 |
| Qwen3.5-2B, fine-tuned on the 527 rows | 45 | 5 | 1 | 1 | 0 | 0 | 0 |
| **Qwen3.5-4B, fine-tuned on the 527 rows** | 35 | 6 | **5** | 3 | 1 | 0 | 0 |
| Qwen3.5-2B, fine-tuned on the v4 rows | 53 | 5 | 2 | 2 | 1 | 1 | 1 |

The instruments had been hiding two of the 4B student's five proved answers. The rule's pick is
the same and stands on more: 5 against 1 and 1. A paired test still does not make it certain
(the 4B and the 2B differ on six problems, five to one; exact p = 0.22). Of the nine dev
problems that no task could pass, six were unreachable only because of this fault. Three remain
with no signature that fits all of their tests (15 `split_lowerstring`, 407 `rearrange_bigger`,
910 `check_date`), computed by trying every signature; the held-out set has one (699). Counts
on dev are of at most 97.

## Can the 9B be trained on this card at all? A memory probe, 2026-10-01 07:49Z

Not a result about the 9B's answers. Three optimizer steps (48 rows) on the longest v5 rows
under each length cap, rank 16, the response-only output layer, the 16 GB card:

| rows no longer than | outcome |
|---|---|
| 2,048 tokens | out of memory |
| 1,536 tokens | the run died with a CUDA illegal memory access (the kernel logged Xid 31, a GPU memory page fault in that process); the card kept working afterwards |
| 1,024 tokens | fits: three steps in 72 seconds |

So a 9B student can be trained here only on rows of at most 1,024 tokens: 406 of the 3,767 v5
rows (11%) would be dropped, most of them debugging and APPS rows, and a full run would take
about four hours. By the rule the 9B matters only if it more than doubles the 4B's tests passed.
It is not trained tonight; the card is spent on the 4B.

## The dev table on complete specifications, 2026-10-01 08:16Z

"Specification checked" in the tables above means the specification is true of the reference's
answer on every drawn input. It does not mean it pins the answer down
(`t/PREDICT-2026-10-01-several-answers.md`, the correction of 08:16Z). The same answers, counted
only when the specification also rejects at least 60% of the mutated outputs tried (SAFE's rule,
arXiv:2410.15756 3.2; `t/score_levels.py --min-completeness 0.6`). The prompted candidates
with nothing counted are left out.

| candidate | tests pass | agreement only: at least 1 | at least 3 | at least 5 | complete specification: at least 1 | at least 3 | at least 5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3.5-9B, prompted | 6 | 2 | 2 | 1 | 2 | 2 | 1 |
| Qwen2.5-Coder-1.5B, fine-tuned on the 527 rows | 4 | 1 | 1 | 0 | 1 | 1 | 0 |
| Qwen3.5-2B, fine-tuned on the 527 rows | 5 | 1 | 1 | 0 | 1 | 1 | 0 |
| **Qwen3.5-4B, fine-tuned on the 527 rows** | 6 | 5 | 3 | 1 | **4** | 2 | 0 |
| Qwen3.5-2B, fine-tuned on the v4 rows | 5 | 2 | 2 | 1 | 2 | 2 | 1 |

One of the 4B's five does not stand: problem 449 (is it a triangle), proved by five kernels on a
specification that says what must hold if the answer is "Yes" and if it is "No" and never that
the answer is one of them; it rejects none of the wrong outputs tried. The rule's pick is the
same, 4 against 1 and 1.
