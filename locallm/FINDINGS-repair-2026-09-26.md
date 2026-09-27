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

## Results

Not run yet.
