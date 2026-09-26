# locallm

locallm is a local code-generation research project built around a stubborn
idea: passing tests is not enough. A candidate program has to survive the
problem's tests, seven independent proof backends, a deliberately broken twin,
and a task-specific check that its specification describes the problem it was
asked to solve.

## Status: no win over Phi

locallm has **not** beaten Phi. There is no verified Phi-versus-LocalLLM result
from the new confirmation protocol, no frozen final v7 panel, and no v7
head-to-head generation result to report.

The earlier 232-task MBPP comparison is still useful history, but it is not a
win. The best scratch-trained locallm arm and Phi-4-mini each reached 3 clean
answers. A later contamination audit found that every clean locallm answer was
in the 32 problems whose function had effectively appeared in its training
material. Nine seeds of the same recipe, run as the r11 baseline, passed 0 of those 200 problems' tests in eight seeds and 2 in one. On the remaining 200 problems, locallm had 0 clean answers and Phi
had 2. The audit changed the project from trying to defend a tie to building a
fresh comparison that can survive scrutiny.

The historical tables, caveats, and raw definitions live in
[SCOREBOARD.md](SCOREBOARD.md),
[LIMITS.md](LIMITS.md), and
[t/DECONTAMINATION-2026-09-21.md](t/DECONTAMINATION-2026-09-21.md).

## What is being built now

The next run is **r12**, and it trains locallm the way this project defines
it: from random weights, on the proved corpus, with no borrowed base. Nine
defects that had each corrupted an earlier number are fixed and tested before
anything trains ([`t/RUN-NEXT-locallm-r12.md`](t/RUN-NEXT-locallm-r12.md),
section A and the build status at its end): held-out problems that hid in the
corpus under a Dafny dataset's names, the 32 same-task overlaps, a committed
proof table overwritten by a one-task run, partial answer sets scored as whole,
mixed decoding settings, a validation split that moved with the corpus,
orphaned provers, oversubscribed SPARK jobs, and a gaming check that read the
wrong examples. The recipe changes (whole-document training rows, a split seed
of its own, deterministic algorithms, kept checkpoints, a stopping step chosen
on a dev split the model never trains on) and the sampling pilot with its
examples-only selector are in place. Ten seeds per recipe, one pre-registered
look, and an exact paired test (`t/compare_arms.py`) decide the result; the
number to move is tests passed on the 200 held-out problems that no training
document answers.

A lab worktree from 2026-09-22 holds a comparison rig for a pinned BF16
[Phi-4-mini-instruct](https://huggingface.co/microsoft/Phi-4-mini-instruct)
served through vLLM, a fresh 200-task panel drawn from CodeContests (the v1-v6
pools are used up: 4,030 of their 4,035 problems have been opened by some
model's output), and an exposure ledger that retires any panel opened for
development. Its one trained artifact is a QLoRA adapter on top of Phi, which
is not locallm and is not this project's result; the panel and the ledger are
what r12's confirmation step will use after the pre-registered look. Prompts,
replies, hidden tests and adapters stay in the lab; public receipts carry
hashes, counts and settings.

The evaluation design takes the same basic lesson as
[lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness)
and [HELM](https://arxiv.org/abs/2211.09110): model comparisons need a shared
setup and enough evidence for someone else to inspect the comparison.

## What will count as a win

A Phi claim has its own preregistration, drafted in the lab worktree of
2026-09-22 and landing with r12's confirmation step. It requires all of the
following:

- A fresh, previously unopened 200-task confirmation panel that is disjoint
  from training and development exposure.
- The same vLLM execution path and one greedy completion per task for both
  arms. No repair loop, answer selector, or decoder change is allowed after
  looking at results.
- Complete task evidence: response, extraction, tests, all seven proof-kernel
  outcomes, and a task-specific specification check.
- A paired seed-1337 advantage with an exact two-sided McNemar/binomial
  p-value of at most 0.05.
- Ten LocalLLM training seeds, with at least nine clean-count wins over the
  fixed Phi responses and an exact sign-test result.
- Manual review of every LocalLLM-only clean answer.

Missing any gate is a non-win. Development can continue, but the panel cannot
be reinterpreted afterward.

## Why the proof pipeline exists

The project trains and evaluates code in a small specification language called
`t`. A program is called **clean** only when it passes the problem's own tests,
its specification verifies in Dafny, Verus, SPARK, Frama-C, Lean 4, Rocq, and
F*, and each backend rejects a sabotaged twin at a concrete counterexample.

That bar still has limits. A proof can show that a program meets its
specification while the specification describes the wrong function. The
pipeline therefore keeps tests, proof checks, twins, and task-specific
specification checks separate. The old experiments found that locallm was much
better at writing well-formed formal programs than at solving unseen problems.
That distinction is the reason the new comparison measures both.

## Run the local app

The desktop app starts with:

```bash
python3 locallm/app.py
```

It uses Tk. On Debian or Ubuntu, install `python3-tk` if it is missing. The
standard-library generator can also inspect a downloaded checkpoint without
PyTorch or NumPy:

```bash
git lfs pull
python3 locallm/plain_generate.py \
  --out t/runs/2026-09-17/home-4080/models/model-r4 \
  --prompt "function to "
```

The release archive includes a model under `included-model/`. A plain clone
contains Git LFS pointers until `git lfs pull` runs.

## Find your way around

| If you want to... | Read... |
|---|---|
| see the historical measurements | [SCOREBOARD.md](SCOREBOARD.md) |
| read every known limitation | [LIMITS.md](LIMITS.md) |
| understand the model builder and desktop app | [locallm/README.md](locallm/README.md) |
| inspect the specification language and proof pipeline | [t/README.md](t/README.md) |
| see the project corrections | [CORRECTIONS.md](CORRECTIONS.md) |
| read the engineering record | [internal/ROADMAP-LOG.md](internal/ROADMAP-LOG.md) |

## Repository map

| Path | Contents |
|---|---|
| [locallm/](locallm/) | The local transformer, desktop app, and generation tools. |
| [t/](t/) | The specification language, seven-backend pipeline, evaluation code, and the Phi confirmation work. |
| [t/twins/](t/twins/) | Verified programs, near-miss twins, and separating inputs. |
| [nl/](nl/) | Natural-language programming problems and tests. |
| [internal/](internal/) | Dated lab notes, handoffs, and the engineering log. |

## License

Research and education use only. See [LICENSE](LICENSE). Third-party material
keeps its own license; the problem-corpus licenses are documented under `nl/`.

Copyright (c) 2026 Treston Malachi Cuzzort.
