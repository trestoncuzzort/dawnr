# dawnr

dawnr is an assistant being built to be trusted: running on its own hardware
with nothing behind it, and checked by proof before anything it produces is
relied on. The bar is a model you could trust on a spaceship: no network, no
one to ask, small hardware, and a mistake that cannot be taken back.

**Nothing it says is relied on until it is proved. That is the whole point.**
The proof engine is the product; the model behind it is whichever openly
licensed weights measure best through that engine, fine-tuned here on what the
proofs accept (since 2026-10-01; before that the model was trained from random
weights, which is kept as research: [why](internal/RESEARCH-2026-10-01-is-the-bet-supported.md)).
The full goal, every part dawnr needs, where each stands and the method each
stands on, is in [AMBITION.md](AMBITION.md) and
[internal/LADDER-PLAN-2026-10-01.md](internal/LADDER-PLAN-2026-10-01.md).

## The idea

Most assistants are trusted because they sound right. dawnr is meant to be
trusted because what it writes is checked.

- **It writes programs with specifications.** Its working language is `t`, a
  small specification language: a program says what it requires and what it
  guarantees.
- **Seven independent provers check them.** Every program is lowered into
  Dafny, Verus, SPARK, Frama-C, Lean 4, Rocq and F*. A program counts as
  **clean** only when it passes its own tests, verifies in all seven, and each
  prover also rejects a deliberately sabotaged twin of it at a concrete
  counterexample. A separate check asks whether the specification describes the
  problem it was meant to solve, since a proof of the wrong thing is still
  wrong.
- **It only learns from what was proved.** The training corpus is made of
  programs that passed that bar. Data can be admitted with a recorded trust
  level, but the boundary between training data and the problems used to
  measure it is absolute.
- **It stands on other people's ladders, and says which.** The weights are a
  permissively licensed pretrained model chosen by measurement
  ([t/PREDICT-2026-10-01-base-model-selection.md](t/PREDICT-2026-10-01-base-model-selection.md));
  the fine-tuning recipe, the data filter and every other step cite the
  published method they come from. An answer is shown with how many of the
  seven provers proved it, or it is refused.

## Where it stands (2026-10-01)

| part | state |
|---|---|
| the model behind the gate | **Qwen3.5-4B (Apache-2.0), picked by the rule fixed beforehand; its results are weak.** Six Apache-2.0 candidates from 1.5B to 14B answered 100 dev problems through the gate. Prompted, none that fits a small card knows `t` (0 to 1 tests passed; the 9B passes 4 and has 1 proved, specification-checked answer). Fine-tuned on 527 proved answers, the 1.5B, 2B and 4B write valid `t` far more often (23, 45 and 35 of 100, from 5, 2 and 9) and each passes the tests on 4. Proved by at least one prover with the specification checked: 1, 1 and **3**; the 4B has one answer proved by five provers and none by six or seven. The rule ranks the 4B first; a paired test on the four problems where it and the 2B differ does not separate them (p = 0.63). The failure is the same at every size: 83 of the 96 specifications that could be checked disagree with the problem's reference. The 4B was first reported here as a damaged run, which was wrong: its logged loss was inflated by a fault in the trainer code written that night, and its fit is the best of the three. A 9B does not fit the 16 GB card for training at these row lengths and has no result ([registration and outcomes](t/PREDICT-2026-10-01-base-model-selection.md)) |
| core model (`locallm/`): a GPT trained from scratch (research since 2026-10-01) | built; pretraining sweep done; the general-English pilot ran 2026-09-29 ([outcome](t/PREDICT-2026-09-29-dawnr-english-pilot.md)): English before code beats code alone at matched tokens, no core moves the specification column off 0. r12's core ran 2026-09-30 ([outcome](t/PREDICT-2026-09-30-dawnr-r12-core.md)): 3.7B English tokens, then code, the lowest code validation loss of any core (1.140), and the judgement unchanged: well formed on 45 of 100 dev problems, none passing its shown examples, the specification column at 0. By its registration the proved corpus, not the core, is the next lever; the 16B-token English set stays staged for a larger core when a free allocation exists |
| proof engine (`t/`): `t`, seven provers, twins, specification checks | built and hardened |
| data engine: lifting verified Dafny, Verus, Lean and C programs into `t` | **464 documents clean in all seven provers** (from 194 on 2026-09-26), 569 with graded trust (six clean, the missing prover recorded); r12 trains on the 463 registered before its launch |
| learning instead of memorising | the main open problem. On the held-out 200 with the specification check applied, every arm reads 0: the ten r11 seeds, the r12 head-prompt seeds so far, and the chat pipeline's three seeds (which reach 2 and 5 by the looser metric, all rejected by the check or recited). Early stopping, best checkpoints and denoising are in place; the next lever is verdicts that draw inputs beyond the shown examples ([DAWNR-PIPELINE.md](DAWNR-PIPELINE.md), 2026-09-29) |
| pretrained models behind the same gate (measured 2026-09-08 to 09-28, read together 2026-10-01: [internal/RESEARCH-2026-10-01-is-the-bet-supported.md](internal/RESEARCH-2026-10-01-is-the-bet-supported.md)) | works, low coverage: pooled over nineteen prompted answer sets, 121 of the clean 200 have an answer that passes the tests, 63 one that some prover verifies, 23 one that all seven verify, 15 one that is also specification-checked; the from-scratch core reads 0 at every stage |
| reinforcement learning with the provers as the reward | built and tested; waits until the model succeeds often enough on new problems to have something to reinforce. Measured on r12's core by sampling, 2026-09-30 ([outcome](t/PREDICT-2026-09-30-dawnr-base-rate.md)): of 6,400 draws on 100 dev problems, 6 reach the tests tier (pass@16 0.012 against a bar of about 0.10) and none is a correct answer, by hand or by the repaired check |
| the model's own verified answers as new data (expert iteration) | staged, not yet run: 442 specification prompts and 368 problem ids are gated and the scoring and regrading pipeline is validated, but the local teacher has produced no samples for lack of a free 30 GB card ([t/EXPERT-ITERATION-2026-09-26.md](t/EXPERT-ITERATION-2026-09-26.md)); 68 earlier teacher answers are in the r12 corpus |
| a chat pipeline (format, mid-training, tools, report card), adapted from nanochat | runs end to end ([DAWNR-PIPELINE.md](DAWNR-PIPELINE.md)); its first tool is the t interpreter, which the model calls on its own draft. On the 531-document corpus and the early-stopped core it is well formed on 49 of 100 dev problems (from 19) and on 130 of the held-out 232 (the head-prompt fine-tune: 91), measured 2026-09-29 with a registered prediction; it does not yet act well on a failed check, and its correct-looking answers do not survive the specification check |
| acting on the machine: files, commands, processes, plans | built, not yet learned by any model: every action through the harness's permissions, plans shown in a dry run and approved as a whole; 0 escapes on 5,000 generated paths, 0 of 80 injected actions run ([DAWNR-AGENT.md](DAWNR-AGENT.md)) |
| learning from each person between sessions ([DAWNR-LEARNING.md](DAWNR-LEARNING.md)) | built: feedback kept per person under their control, a per-person adapter trained in guarded sleeps, a style profile inferred from their edits. Measured on four simulated persons: the profile halves their edit cost with every checked answer unchanged; the adapter fits their style only in likelihood, and where it changes what dawnr writes it costs correct answers |
| retrieval, memory, tool use, speech, vision | not started; in the order [AMBITION.md](AMBITION.md) gives |

Part by part (2026-10-01). **The gate works**: seven provers, the sabotaged
twins, the specification check and the grading stack; across 4,700 graded
programs no prover has verified what another refuted. **A pretrained model
behind the gate works at low coverage**: with no training, pooled prompted
answers are proved and specification-checked on 15 of the 200 unseen problems
by all seven provers, and on 45 when one prover's proof is counted and none
refutes. **The from-scratch model does not**: zero on every held-out measure,
after every round, core and sampling run, which is what published results
predict at its size and data. **What is being built now**: a small openly
licensed model fine-tuned on everything the gate admits, measured on problems
it has not seen. Its first measurement (2026-10-01): three small students answer 1, 1
and 3 of 100 unseen problems with a proof and a checked specification, none
proved by all seven provers. They learned the language, and their
specifications are mostly wrong. Every number links back to the run that produced it, and
failures are published beside successes ([CORRECTIONS.md](CORRECTIONS.md), [LIMITS.md](LIMITS.md)).

## How progress is measured

- **The clean 200**: held-out problems that no training document answers,
  after an audit found that earlier "clean" answers had leaked through
  same-task training data ([t/DECONTAMINATION-2026-09-21.md](t/DECONTAMINATION-2026-09-21.md)).
- **Seeds and pre-registration**: every recipe runs with several seeds, the
  prediction and decision rule are written down before the run, and a result
  that appears at one seed is not a result.
- **A milestone, not the goal**: a head-to-head against Phi-4-mini, a model
  about forty times larger, under a pre-registered protocol on a fresh panel
  ([SCOREBOARD.md](SCOREBOARD.md) has the history; no win has been claimed).

## Try it

The desktop app (Tk; on Debian or Ubuntu install `python3-tk` if it is
missing):

```bash
python3 locallm/app.py
```

It can talk to the included model without PyTorch, streaming its answer as it
writes. The standard-library generator also runs from the command line:

```bash
git lfs pull
python3 locallm/plain_generate.py \
  --out t/runs/2026-09-17/home-4080/models/model-r4 \
  --prompt "function to "
```

A plain clone holds Git LFS pointers until `git lfs pull` runs.

## Find your way around

| If you want to... | Read... |
|---|---|
| know what dawnr is for and what comes next | [AMBITION.md](AMBITION.md) |
| understand the model, trainers and desktop app | [locallm/README.md](locallm/README.md) |
| understand `t` and the seven-prover pipeline | [t/README.md](t/README.md) |
| see how verified corpora are brought in | [t/LIFT-2026-09-26.md](t/LIFT-2026-09-26.md), [t/LIFT-VERICODING-VERUS-LEAN.md](t/LIFT-VERICODING-VERUS-LEAN.md) |
| see reinforcement learning with the provers | [t/RL-DESIGN-2026-09-26.md](t/RL-DESIGN-2026-09-26.md) |
| let dawnr act on your machine, and see its threat model | [DAWNR-AGENT.md](DAWNR-AGENT.md) |
| see every measurement and limitation | [SCOREBOARD.md](SCOREBOARD.md), [LIMITS.md](LIMITS.md), [CORRECTIONS.md](CORRECTIONS.md) |
| read the engineering record | [internal/ROADMAP-LOG.md](internal/ROADMAP-LOG.md) |

## Repository map

| Path | Contents |
|---|---|
| [locallm/](locallm/) | dawnr's core model: the transformer, trainers, generators and desktop app. |
| [t/](t/) | The specification language, the seven-prover pipeline, the lifters, the data engine and evaluation. |
| [t/twins/](t/twins/) | Verified programs, their sabotaged twins and the inputs that separate them. |
| [nl/](nl/) | Natural-language programming problems and tests. |
| [internal/](internal/) | Dated notes, handoffs and the engineering log. |

## License

Research and education use only. See [LICENSE](LICENSE). Third-party material
keeps its own license (see [NOTICE](NOTICE)); the problem-corpus licenses are
documented under `nl/`.

Copyright (c) 2026 Treston Malachi Cuzzort.
