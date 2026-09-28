# dawnr

dawnr is an assistant being built from the ground up to be trusted: trained
here from random weights, running on its own hardware with nothing behind it,
and checked by proof before anything it produces is relied on. The bar is a
model you could trust on a spaceship: no network, no one to ask, small
hardware, and a mistake that cannot be taken back.

It is early. What exists today is the core: a small language model trained
from scratch, the proof engine that judges it, and the data engine that feeds
it only what the proofs accept. The full goal, every part dawnr needs, where
each stands and the order they are built in, is in [AMBITION.md](AMBITION.md).

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
- **It is built, not borrowed.** The model is trained from random weights on
  one machine; no one else's base model is underneath it.

## Where it stands (2026-09-26)

| part | state |
|---|---|
| core model (`locallm/`): a GPT trained from scratch | built; pretraining sweep done |
| proof engine (`t/`): `t`, seven provers, twins, specification checks | built and hardened |
| data engine: lifting verified Dafny, Verus, Lean and C programs into `t` | **457 documents clean in all seven provers** (from 194 on 2026-09-26), 566 with graded trust (six clean, the missing prover recorded) |
| learning instead of memorising | the main open problem: on problems it was not trained on, the model rarely succeeds; early stopping, best checkpoints and denoising are in place, and more data is the lever |
| reinforcement learning with the provers as the reward | built and tested; waits until the model succeeds often enough on new problems to have something to reinforce |
| the model's own verified answers as new data (expert iteration) | running with a local teacher model |
| a chat pipeline (format, mid-training, tools, report card), adapted from nanochat | runs end to end ([DAWNR-PIPELINE.md](DAWNR-PIPELINE.md)); its first tool is the t interpreter, which the model calls on its own draft; it does not yet act on a failed check |
| acting on the machine: files, commands, processes, plans | built, not yet learned by any model: every action through the harness's permissions, plans shown in a dry run and approved as a whole; 0 escapes on 5,000 generated paths, 0 of 80 injected actions run ([DAWNR-AGENT.md](DAWNR-AGENT.md)) |
| learning from each person between sessions ([DAWNR-LEARNING.md](DAWNR-LEARNING.md)) | built: feedback kept per person under their control, a per-person adapter trained in guarded sleeps, a style profile inferred from their edits. Measured on four simulated persons: the profile halves their edit cost with every checked answer unchanged; the adapter fits their style only in likelihood, and where it changes what dawnr writes it costs correct answers |
| retrieval, memory, tool use, speech, vision | not started; in the order [AMBITION.md](AMBITION.md) gives |

The honest headline: the machinery that makes dawnr trustworthy works; the
model is not yet good at problems it has not seen. The last baseline passed
0 of 200 clean held-out problems in eight of nine seeds. Every number here
links back to the run that produced it, and failures are published beside
successes ([CORRECTIONS.md](CORRECTIONS.md), [LIMITS.md](LIMITS.md)).

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
