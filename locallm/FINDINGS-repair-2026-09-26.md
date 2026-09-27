# Repair conversations: does dawnr learn to act on a failed check? 2026-09-26

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
