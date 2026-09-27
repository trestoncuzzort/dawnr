# Repair conversations: does dawnr learn to act on a failed check? 2026-09-26

**In short.** Repair conversations built from the model's own cross-fitted
drafts teach dawnr to act on a failed check (a different program after 55-70%
of failing verdicts, against 5-12% without them), but they do not raise the
number of answers that pass their examples by more than seed noise: +2.3 of
133 at the three registered seeds, +1.2 at six fresh ones, INCONCLUSIVE both
times. Not adopted. The unclosed tool call is gone two ways: a grammar on the
chat tokens (0 left) and, separately, training in which calls dominate.
Learned on the way: the answer must be the call with the best verdict, not
the last; retries need a stop; and the t tool passes drafts that rewrote the
user's specification. The sections below were written in order, each
prediction before its run.

## Why

The first run of dawnr's chat pipeline (`DAWNR-PIPELINE.md`, "What has been
ported") showed the model calling the t tool on its own draft and the tool
finding real faults ("example 1: fail: got 55, expected 17"), and the model
never acting on them: after a verdict it ends. And 31 of 100 dev answers
opened a tool call they never closed (28 of them emitted `<|assistant_end|>`
inside the call, 3 ran out of tokens there), so the tool never ran on them.

Two changes, measured separately:

1. **Repair conversations** (the data). SAFE (arXiv:2410.15756) keeps a
   verifier's rejected proofs as self-debugging data: the triple (incorrect
   proof, the verifier's error on it, the correct proof), with the wrong proof
   and the error as input and the fix as the target. STaR (arXiv:2203.14465)
   fine-tunes on answers that end correct, "rationalizing" a failure given the
   correct answer. dawnr's version: a draft the model itself wrote on a
   TRAINING problem, inside a tool call; the t tool's real verdict; then the
   proved corpus program in a second call, with the tool's real verdict on it;
   then the end. The draft's text is not supervised (it is wrong; only the
   call tokens around it are), the tool's output never is, the proved program
   and the end are.
2. **A grammar on the chat tokens** (the engine). Outlines (arXiv:2307.09702)
   masks the logits of tokens illegal in the current state of a
   finite-state machine. The assistant turn is a two-state machine: inside a
   call only text and `<|t_end|>` are legal, outside it only text,
   `<|t_start|>` and `<|assistant_end|>`; the tool-output and turn tokens are
   never sampled. So a call can only end by `<|t_end|>`, and the tool then
   runs. Training examples already always close (the renderer writes
   `<|t_end|>` after every call).

SCoRe (arXiv:2409.12917) found that SFT on offline correction traces fails in
two ways: the collected mistakes are not the model's own (distribution
mismatch), and learning collapses onto one mode of correction. Both risks
apply here, since this is offline SFT. Against the first, drafts come from
**cross-fitted** mid models (K-fold sample splitting, as in double ML,
arXiv:1608.00060): the mid model trained on every training conversation has
memorised them (train loss 0.015), so its drafts on its own training problems
are recitations. A model trained with the same recipe on the other four fifths
makes the mistakes it makes on problems it has not seen. Against the second,
conversations where the draft passes and the assistant finishes are kept
beside the repairs. SCoRe's multi-turn RL is not done here; it belongs with
the RL-through-the-engine port.

## Set-up (fixed before any run)

- **Corpus and core:** the first run's inputs. `corpus-all-2026-09-26.txt`
  (358 proved documents, sha256 `d529e818...`), the r12 weight-decay core
  (`wd0.8-lr1e-3-seed1337`, 92.9M parameters, BPE 8,192), the hash split at
  seed 1337: 325 training conversations, 33 validation. Conversations are
  built by `chat_data.py` exactly as before (tool rate 0.5, tool seed 0).
- **Drafts, from training problems only** (`locallm/repair_data.py`): the
  325 training-side conversations are put in 5 folds by a salted hash of the
  user turn. For each fold, a mid model is trained by `chat_train.py` from the
  core on the other four folds' training conversations only (no validation
  conversation, no dev problem), with the first run's mid recipe: 400 steps,
  lr 1e-4, batch 8, block chosen automatically, seed 1337. It then drafts
  every conversation in its fold through the engine (grammar on, the t tool
  live): 1 greedy draft and 3 sampled at temperature 1.0, top-k 50, 400 new
  tokens. The draft is the first program the reply writes (the first call's
  text, else its text). Its verdict is `t_tool.call(draft, user turn)`.
- **Conversations from the drafts:** per training problem, up to 2 distinct
  failing drafts (greedy first, then the samples in order) become repair
  conversations; up to 1 passing draft that is the proved program (equal
  after collapsing whitespace) becomes a pass conversation
  (`[call: proved program] [verdict]`, end). A passing draft that is not the
  proved program is not trained on (it passed two examples but nothing
  proved it) and is counted. A conversation longer than the context is
  dropped and counted; every conversation passes `chat_data.gate` (held-out
  ids, same-task sources, dev ids) and a refused one is dropped by name.
- **Arms.** A: the mid stage on the 358 conversations (the first run).
  B: the mid stage on the same 358 plus the repair and pass conversations
  (training side). Everything else is the first run's: core, 400 steps, lr
  1e-4, batch 8, block automatic, via `dawnr_pipeline.py`.
  **Seeds 1337, 1338, 1339 for both arms.** Same step budget means B's base
  conversations are seen fewer times; but every repair conversation ends with
  the proved program of a training problem, so each proved program is
  supervised at least as often in B as in A.
- **Evaluation** (`chat_eval.py`, greedy): the first 100 dev problems
  (`t/r12-dev-ids.json`, as in the first run) and the 33 validation
  conversations; up to 800 new tokens (the first run's 400 leaves no room for
  a draft, a verdict and a second program; the context is 2,048). Each
  checkpoint is evaluated twice: grammar on, and grammar off (the first run's
  engine). 12 evaluations.

## Metrics

Per evaluation, on dev (100) and validation (33):

- **well formed**: dev, `rl_reward` tier at least typed; validation, the t
  tool says parses and well formed.
- **pass all examples**: the final program (the last call, else the text)
  passes every Example line of the prompt under the t tool. New for dev.
- **exact proved program**: validation only.
- **tests passed**: dev, `rl_reward` tier at least tests.
- **calls**: opened a call; ended inside a call by `<|assistant_end|>`; ran
  out of tokens inside a call; the grammar's overrides (steps where the
  model's top token was illegal).
- **acted on a failed check**: of the answers that got a failing verdict,
  how many made a later call with a different program.
- **repaired**: the first verdict failed and the final program passes every
  example.

## Predictions (written before the runs)

1. **Draft data.** Fold models draft like the first run's validation numbers
   (well formed 24 of 33, every example 15 of 33, exact 7 of 33), sampled
   drafts worse. Predicted: 450-550 repair conversations, 60-90 pass
   conversations, about 100 passing drafts that are not the proved program.
2. **Grammar, on arm A (paired, same checkpoints):** ended inside a call by
   `<|assistant_end|>` falls from about 28 of 100 dev to 0 (by construction:
   this number only checks the mask was applied); used the tool rises from
   about 4 to 30 or more; pass all examples, well formed and tests move by at
   most 1 on average, because the program in the call is the same and model
   A ends after any verdict.
3. **Repair data, B against A, both with the grammar:**
   - acted on a failed check: A about 0% (it has never seen a second call);
     B 50% or more. Falsified if B is below 25%.
   - pass all examples over the 133 prompts: B above A by about 3 (range 0 to
     6) on the mean of three seeds. Falsified if B is not above A.
   - tests passed on dev: 0 to 1 in both arms. Repair does not add knowledge
     of MBPP problems a 93M model does not have.
   - exact proved program on validation: within 2 of A.

## Decision rules

- **Repair data** becomes part of the pipeline's default mid data if, on
  pass all examples over the 133 prompts (grammar on), compare_arms' rule
  says ADOPT: exact one-sided permutation p over seeds at most 0.05 (with 3
  seeds a side, only when every B seed beats every A seed) and the upper bound
  of the bootstrap interval of P(B > A) above 0.75; and B loses no more than 2
  on average in dev well formed or validation exact. If B acts on failed checks
  (prediction 3a holds) but the primary does not pass, the verdict is "learned
  the form of repair, not the substance"; the builder stays, off by default.
- **Grammar** becomes the engine's default if, on A's three checkpoints, it
  leaves no answer ending inside a call by `<|assistant_end|>` and the mean
  of pass all examples over the 133 prompts and of dev well formed each drop by
  at most 1.

## Results (the registered runs)

Run on the desktop GPU, one job at a time, each under a user scope with
MemoryMax=8G. Every number below is read from the runs' own files by
`locallm/repair_report.py --runs <runs dir>`: each arm and seed is a
`dawnr_pipeline.py` output directory (`A-s<seed>/`, `B-s<seed>/`, with
`7-eval/stage.json` for the grammar on and `eval-nogrammar.json` for the
same checkpoint without it), and the repair data is `repair_data.py`'s
`repairs.summary.json`.

### 1. The draft data

1,300 drafts (325 training problems, 1 greedy and 3 sampled each), all from
fold models that never saw the problem. The fold models' greedy drafts on
their unseen training problems: 212 of 325 well formed, 148 pass every
example, 76 are the proved program exactly, close to the first run's
validation side (24, 15 and 7 of 33).

| draft verdict | greedy | sampled |
|---|---|---|
| passes | 154 | 395 |
| (of those, the proved program) | 76 | 188 |
| does not parse | 52 | 241 |
| not well formed | 61 | 186 |
| wrong output | 47 | 127 |
| undefined, budget, crash | 11 | 23 |
| no program | 0 | 3 |

Built: **436 repair conversations** over 234 problems and **84 pass
conversations**; 274 failing drafts over the cap of 2, 38 repeats of a failing
draft, 180 passing proved drafts over the cap of 1; none over the context;
none refused by the gates. Prediction 1 said 450-550 and 60-90: repairs a
little under, passes inside. It also said about 100 passing drafts would not
be the proved program; **285** were, and 101 of those 285 had changed the
specification the user gave (the declaration, requires or ensures): the t
tool runs the examples and never compares the draft's specification with the
prompt's, so a draft that weakens the specification to pass is invisible to
it. Not trained on, and a gap in the tool (below).

Arm B trained on 845 conversations (325 base + 520) against A's 325, 137,353
supervised tokens against 51,382, rows of 1,280 tokens against 1,024; 76 s
against 49 s, peak 5.8 GiB against 5.0. Loss on the 33 validation
conversations' assistant tokens ended the same (A 0.277/0.291/0.284, B
0.284/0.271/0.284 at seeds 1337/1338/1339).

### 2. The repair data (B against A, grammar on)

| per seed 1337 / 1338 / 1339 | A | B |
|---|---|---|
| **pass all examples, 133 prompts** | 16 / 16 / 17 (16.3) | 17 / 20 / 19 (18.7) |
| dev well formed | 32 / 12 / 22 (22.0) | 3 / 5 / 7 (5.0) |
| dev pass all examples | 0 / 0 / 0 | 0 / 1 / 1 |
| dev tests passed | 0 / 0 / 0 | 0 / 1 / 1 |
| dev answers that ended | 91 / 88 / 97 | 0 / 1 / 1 |
| dev ran out of tokens inside a call | 2 / 9 / 1 | 82 / 81 / 82 |
| dev tool calls, all answers | 39 / 33 / 21 | 308 / 352 / 278 |
| dev got a failing verdict | 34 / 33 / 21 | 93 / 93 / 93 |
| dev then a different program | 4 / 0 / 0 | 69 / 72 / 61 |
| dev then the same program again | 0 / 0 / 0 | 64 / 65 / 51 |
| val well formed | 21 / 24 / 23 (22.7) | 17 / 21 / 18 (18.7) |
| val pass all examples | 16 / 16 / 17 | 17 / 19 / 18 |
| val exact proved program | 6 / 6 / 7 (6.3) | 7 / 8 / 6 (7.0) |
| val repaired (first verdict failed, final passes) | 0 / 0 / 0 | 2 / 1 / 2 |
| val answers that ended | 33 / 33 / 33 | 17 / 19 / 18 |

Against the predictions:

- **3a, acts on a failed check: held.** B made a later call with a different
  program after 70% of its failing verdicts (A: 5 answers in all three seeds).
- **3b, pass all examples up: held in direction, not by the rule.** B is
  above A at every seed (+2.3 on the mean), but B's 17 at seed 1337 ties A's
  17 at seed 1339, so the exact permutation p is 1/10 (mid-p 1/20), P(B > A)
  17/18, bootstrap interval [0.78, 1.00]: compare_arms says INCONCLUSIVE.
  All of the gain is on the validation side plus task 350 on dev.
- **3c, tests on dev 0 to 1: held.** B passed the tests of one dev problem
  (MBPP 350, `minimum_Length`) at two of three seeds, the first dev test pass
  of the chat pipeline; A passed none.
- **3d, exact within 2: held** (+0.7).
- **Not predicted: B never stops.** On dev, 82 of 100 answers run out of the
  800 tokens inside a call, having called the tool 2 to 3 times on the
  median; on validation 14 to 16 of 33 do not end. The final program is
  then a call cut off by the budget, which is why dev well formed falls from
  22 to 5. The repair
  conversations always show one failure followed by a pass; the model never
  saw a second failure, and on a problem it cannot solve it keeps trying.
  Its retries also repeat the fault the tool named: one dev answer is told
  three times "expected 'id', found 'seq'" at line 3 (a parameter with no
  name) and rewrites the loop body each time, never the signature. SAFE's
  fix target is the whole corrected proof, and so is ours; nothing in the
  data points the retry at the line the verdict names.

**Decision: not adopted.** INCONCLUSIVE on the primary, and the guard fails
(dev well formed -17). The registered reading is "learned the form of repair,
not the substance"; the builder stays, off by default.

### 3. The grammar (on against off, arm A, same checkpoints)

| per seed 1337 / 1338 / 1339 | off | on |
|---|---|---|
| dev ended inside a call by `<\|assistant_end\|>` | 30 / 23 / 6 | 0 / 0 / 0 |
| val ended inside a call | 11 / 5 / 1 | 0 / 0 / 0 |
| dev used the tool | 4 / 10 / 15 | 34 / 33 / 21 |
| dev well formed | 37 / 13 / 22 (24.0) | 32 / 12 / 22 (22.0) |
| pass all examples, 133 prompts | 16 / 16 / 17 | 16 / 16 / 17 |

Prediction 2 held on every count but one: the calls close (the number only
checks the mask), the tool runs on about 30 answers instead of 10, and pass
all examples does not move; but dev well formed fell by 2 on the mean (5 at
seed 1337), past the rule's 1. **Decision: not adopted as the default.** Why
it cost anything, read from the rows: at seed 1337 five answers were well
formed without the grammar and not with it. In all five the grammar closed
the call on exactly the program the unmasked engine produced (the mask chose
`<|t_end|>`, as intended); the tool then said "fail", and the model, now
reading a verdict it had never been shown, wrote another program that was
worse (four made a second or third call, one opened one and ran out of
tokens). The metric takes the last call as the answer, so the worse program
counted. The cost is the answer rule, not the mask.

Not predicted either: **arm B never ends inside a call even without the
grammar** (0 of 100 and 0 of 33 at every seed; grammar off and on give the
same table). In B nearly every conversation calls the tool (687 of 845
training rows), so opening a call and closing it is the only pattern; in A
half of the conversations answer without a call, and at the end of a program
the model confuses which end token belongs to which. The data fixed the
unclosed call on its own.

## A second look (written after the results above, before it was computed or run)

This section is post hoc: it was written after reading the first look's
rows, so nothing it finds is a registered result. What it can do is say
whether the two failures above are what they appear to be, and turn that into
a prediction the next registered run can test on fresh seeds.

Both failures are about which program counts as the answer and when the
answer stops, not about what the model learned:

- **The answer rule.** The first look took the last call as the answer. A
  reply's calls are samples that the t tool has already run on the user's own
  examples, and AlphaCode (arXiv:2203.07814) filters its samples by exactly
  that: behaviour on the problem statement's example tests. **Best verdict:**
  the answer is the call whose verdict ranks highest (every example passes,
  then parses and well formed, then parses, then nothing), the latest among
  equals; a reply with no call answers with its text. It uses nothing the
  system lacks at inference: no hidden test, no reference program.
- **A call budget.** s1's budget forcing (arXiv:2501.19393) ends a segment
  when its budget is spent. Here the budget is calls: after an answer's
  second call, `<|t_start|>` is illegal, so a model that would retry forever
  must end or write text.

How it is measured:

1. **Re-analysis, no generation:** the first look's rows hold every call and
   every verdict, so best verdict is recomputed from them
   (`chat_eval.py --rescore <rows> --answer best-verdict`) for all twelve
   evaluations.
2. **The call budget, generated:** the six checkpoints again, grammar on,
   `--max-calls 2 --answer best-verdict`. Greedy decoding makes the first
   two calls the same as in the first look, so what this run adds is what
   happens when a third call is refused: does the answer end.

Predictions:

- Re-analysis, arm A: dev well formed with the grammar on rises to at least
  its grammar-off value (24.0 on the mean): at seed 1337 the five answers that
  fell had a well-formed first call.
- Re-analysis, arm B: dev well formed from 5.0 to between 15 and 30 (the
  first call is a draft like A's, and there are more of them); pass all
  examples over the 133 prompts about 19 to 20 (B) against 16 to 17 (A).
  The repair rule (compare_arms ADOPT and the guards) is then applied to
  these numbers; a pass is a hypothesis for fresh seeds, not an adoption.
- Re-analysis, the grammar rule on A with best verdict on both sides: dev
  well formed changes by at least -1 and the primary by at least -1: the
  grammar would pass.
- Call budget, arm B: dev answers that end rise from under 1 to at least 85
  of 100, validation from about 18 to at least 30 of 33; pass all examples
  within 1 of B's best-verdict re-analysis.
- Call budget, arm A: within 1 of its own re-analysis on every count (it
  rarely makes a third call).

### Second look: results

`chat_eval.py --rescore` under the first look's own rule (`--answer last`)
reproduces every number of the A seed-1337 evaluation exactly, so the
re-analysis differs from the first look only by the answer rule.

| mean of seeds 1337 / 1338 / 1339 | A last | A best | B last | B best | A budget | B budget |
|---|---|---|---|---|---|---|
| **pass all examples, 133 prompts** | 16.3 | 16.3 | 18.7 | 18.7 | 16.3 | 18.3 |
| dev well formed | 22.0 | 24.0 | 5.0 | **27.7** | 24.0 | 26.0 |
| dev tests passed | 0 | 0 | 0.7 | 0.7 | 0 | 0.7 |
| dev answers that ended | 92.0 | 92.0 | 0.7 | 0.7 | 92.3 | **81.3** |
| val well formed | 22.7 | 23.0 | 18.7 | 24.0 | 23.0 | 23.3 |
| val exact proved program | 6.3 | 6.3 | 7.0 | 7.0 | 6.3 | 7.0 |
| val answers that ended | 33 | 33 | 18.0 | 18.0 | 33 | 31.0 |

("last" and "best" are the first look's rows under each answer rule, grammar
on; "budget" is the new generation with two calls at most and best verdict.)

- **Answer rule, arm A: held.** Dev well formed with the grammar goes back to
  24.0, its grammar-off value; with best verdict on both sides the grammar
  rule passes (ended inside a call 0, primary 0, dev well formed 0).
- **Answer rule, arm B: held.** Dev well formed from 5.0 to 27.7, now above
  A's 24.0; B's retries were writing well-formed programs all along, the last
  one was just cut off. The primary does not move (18.7; predicted 19 to 20),
  because a program that passes every example already ended its answer.
- **Call budget, arm B: mostly held.** 81 of 100 dev answers end (predicted
  at least 85: missed; about 9 run out of tokens inside the second call and
  7 in text after the third call was refused), 31 of 33 validation answers
  (predicted at least 30). Pass all examples within 1 of the re-analysis.
  B makes exactly two calls on about 90 of 100 dev problems.
- **Call budget, arm A: held**, within 1 of its re-analysis everywhere.
- **The repair rule, applied to both variants: still INCONCLUSIVE.** Under
  best verdict the primary is unchanged (A 16/16/17, B 17/20/19, p 1/10) and
  the guards now pass (dev well formed +3.7, val exact +0.7). Under the
  budget, B's seed 1337 falls to 16 (a validation answer whose third call had
  repaired it) and p is 1/5. Three seeds a side with one tie cannot reach
  p 0.05: the effect, if real, is about 2 prompts in 133, and three seeds
  cannot separate that from seed noise.

What the second look settles: the collapse in the first look was the answer
rule and the missing stop, not a loss of skill. What it does not settle is
whether repair conversations raise the number of prompts whose answer passes
its examples; that needs more seeds.

## A third look: fresh seeds (registered before the runs)

- **Recipe:** arms A and B exactly as above (same conversations, same repair
  file, same mid recipe) at **six fresh seeds, 1340 to 1345**, none of which
  has been trained. Evaluated once each: grammar on, a budget of two calls,
  best-verdict answer, 800 tokens, 100 dev problems and 33 validation
  conversations (`chat_eval.py --grammar --max-calls 2 --answer best-verdict`).
- **Prediction:** B above A on pass all examples over the 133 prompts by
  about 2 (range 1 to 3) on the mean of six seeds; dev well formed within 5
  of A either way; dev tests passed 0 to 1 per seed in both arms; B's dev
  answers end on at least 75 of 100.
- **Decision:** the same repair rule on the six fresh seeds alone (the three
  seeds above are not pooled in, since they chose this variant): compare_arms
  ADOPT (exact one-sided permutation p at most 0.05 and the bootstrap upper
  bound of P(B > A) above 0.75) and B losing no more than 2 on the mean in dev
  well formed or validation exact. If it passes, repair conversations become
  the mid stage's default data with the budget and best-verdict answer as the
  evaluation's default; if not, they stay off by default and the note says
  the effect is not distinguishable from zero at this size.

## The registered decisions, applied

The grammar failed its registered rule (dev well formed -2), so the engine's
grammar is **off by default** (`Engine(grammar=False)`, `chat_eval.py
--grammar` to turn it on); it passes post hoc together with the best-verdict
answer, which is where the third look uses it. Repair conversations are off
by default (`dawnr_pipeline.py --extra-conversations` adds them).

### Third look: results (six fresh seeds)

`repair_report.py --runs <fresh runs dir> --fresh`: arms A and B at seeds
1340-1345, grammar on, two calls at most, best-verdict answer.

| per seed 1340 ... 1345 | A | B |
|---|---|---|
| **pass all examples, 133 prompts** | 17 20 16 17 19 14 (17.2) | 15 22 17 20 19 17 (18.3) |
| dev well formed | 16 25 19 15 16 32 (20.5) | 13 33 24 47 20 17 (25.7) |
| dev pass all examples | 0 1 0 0 1 0 | 0 2 0 3 0 0 |
| dev tests passed | 0 0 0 0 1 0 | 0 0 0 1 0 0 |
| dev answers that ended | 95 86 90 89 94 90 | 94 69 89 86 82 90 |
| dev a different program after a failing verdict | 3 7 2 3 3 3 | 55 41 56 53 52 50 |
| val pass all examples | 17 19 16 17 18 14 | 15 20 17 17 19 17 |
| val exact proved program | 5 8 7 6 7 6 (6.5) | 6 7 7 6 7 5 (6.3) |
| val repaired | 0 1 0 0 0 0 | 1 2 2 0 1 0 |

- **Pass all examples: B above A by 1.2 on the mean** (predicted about 2,
  range 1 to 3: inside the range, below the point). B is ahead at 3 seeds,
  level at 1, behind at 2. Exact permutation p 71/308 (0.23), P(B > A) 23/36
  with bootstrap interval [0.31, 0.92]: **INCONCLUSIVE.**
- Dev well formed B above A by 5.2 (predicted within 5 either way: just
  outside, in B's favour); validation exact -0.2; the guards pass.
- Dev tests passed: one problem at one seed in each arm (predicted 0 to 1:
  held). A's model also passed MBPP 350's tests once here, so B's two passes
  of it in the first look were not something only repair data produced.
- B's dev answers end on 85 of 100 on the mean (predicted at least 75: held
  on the mean, not at seed 1341, 69).

**Decision (registered): not adopted.** Repair conversations stay off by
default; the effect on answers that pass their examples is not
distinguishable from zero at this size.

Seed noise is the size of the effect. Over the nine seeds evaluated this way
(1337-1339 in the second look and these six; pooled for description only,
not a registered test) A ranges 14 to 20 and B 15 to 22, the mean difference
is +1.4 prompts of 133 (exact p 0.09), and a difference that size at that
spread needs about 24 seeds a side to show at 80% power.

## What this bought

- **The model acts on a failed check, and the pipeline can measure it.**
  After repair conversations it writes a different program after 55-70% of
  failing verdicts, against 5-12% without them; it repaired 0 to 2 of the 33
  validation answers per seed, against almost none. What it does not yet do
  is repair *well*: it keeps the fault the verdict names (a missing parameter
  name rewritten three times in the body) because the target of every repair
  is the whole proved program, never an edit of the draft at the line the
  tool points to.
- **The unclosed call is solved two ways.** The grammar makes it impossible
  (0 of arm A's 399 answers ended inside a call, against 41, 28 and 7 of 133
  per seed without it); and training where nearly every conversation calls
  the tool makes the model close calls on its own (arm B: 0 without any grammar). The
  grammar is off by default because its registered rule failed on the answer
  rule, not on the calls.
- **Take the best-verdict call as the answer.** Taking the last call counted
  a program the model wrote after reading a failing verdict, which was
  usually worse (dev well formed 5 against 28 for the same B rows). The
  tool's verdicts on the user's own examples pick the answer at no cost.
- **Retries need a stop.** Trained only on one failure followed by a fix,
  the model retried until its tokens ran out on 82 of 100 dev answers. A
  budget of two calls makes 81-85 of 100 end. Conversations with two
  failures and then an honest stop (dawnr's rule: what cannot be checked is
  refused) would teach the stop instead of imposing it.
- **The t tool has a hole on specification prompts.** 285 fold drafts passed
  every example without being the proved program, and 101 of them had
  changed the specification the user gave. The tool should check that a
  draft keeps the prompt's declaration, requires and ensures before it runs
  the examples; until it does, "pass" on a specification prompt can mean the
  draft weakened the specification.
- **Next:** the tool's specification check; repairs as edits of the draft
  (the twins in `t/twins/` are real near-misses with the input that
  separates them); and SCoRe's multi-turn RL through `engine.py`, with the
  proof engine as the reward, which is the port `DAWNR-PIPELINE.md` names
  next. Any rerun of this comparison needs about 24 seeds a side.

## Follow-up 2026-09-27: the specification check, built and measured

The tool's hole named above is closed: `t_tool.spec_changed` (`test_t_tool.py`)
compares a draft's declaration, requires, ensures and spec funs against the
specification the prompt actually gave (`t_tool.spec_header_from_context`,
read back out of the conversation, not re-derived), by normalized AST
equality — the same up to one consistent renaming of the task's own name,
its parameters, its return, a spec fun's own parameters and a quantifier's
bound variable, and up to reordering the requires list and, separately, the
ensures list, since each is a set of conditions, not a sequence. Anything
else differing is `call`'s new `specification: spec changed: <why>` line,
checked before the examples run (`checker.failing`/`redacted_verdict` updated
to match); a context with no formal specification in it (a "Problem:"
prompt, plain chat) is untouched, byte for byte.

**Measured** (`measure_spec_repair.py`, on this run's own saved
`conversations.jsonl` and `work/drafts.jsonl`, nothing re-generated or
re-graded): of the 285 drafts this file counted as passing every example
without being the proved program, 254 are of a "spec" prompt (the other 31
are "Problem:" prompts, which state no formal specification for this check
to compare against). Of those 254, **15 (9 distinct problems) now read
"specification: spec changed"** — a dropped or reworded `ensures` conjunct,
a dropped or added `requires`, an added parameter, or a redefined spec fun,
each read from the verdict's own line, not eyeballed. Of the 239 not
flagged, 238 are byte-identical reproductions of the prompt's own
specification (the draft's mistake is entirely in its body, which this
check does not touch — an unrelated, already-known gap: a body can satisfy
one or two given examples without being correct in general) and 1 differs
only by a quantifier bound variable renamed between two clauses (`i_v` ->
`i_v2`), which the renaming rule this file asked for correctly does not
flag.

That 15 is well under this file's own informal "101" above. That figure
carries no script name (unusual in this repository, AGENTS.md rule 1), and
given 238 of 239 non-flagged drafts match the prompt's specification
byte-for-byte, a per-draft automated comparison could not have produced 101
by comparing against the prompt's own text either; it most likely came from
a rougher pass that could not tell a harmless rename from a real change,
which is exactly the distinction this checker exists to make. 15 of 285, not
101, is the number this repository should now cite for this hole, and the
measurement script that produced it is `measure_spec_repair.py`, kept for
the next repair run to reuse.
