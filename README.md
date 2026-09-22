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
material. On the remaining 200 problems, locallm had 0 clean answers and Phi
had 2. The audit changed the project from trying to defend a tie to building a
fresh comparison that can survive scrutiny.

The historical tables, caveats, and raw definitions live in
[SCOREBOARD.md](SCOREBOARD.md),
[LIMITS.md](LIMITS.md), and
[t/DECONTAMINATION-2026-09-21.md](t/DECONTAMINATION-2026-09-21.md).

## What is being built now

The current lab track compares a pinned
[Phi-4-mini-instruct](https://huggingface.co/microsoft/Phi-4-mini-instruct)
baseline with a LocalLLM LoRA adapter. Both sides run through vLLM with the
same frozen request plan, chat rendering, decoder settings, token cap, and
grader. The adapter training path, managed vLLM runners, source manifests, and
paired-result checks are in place. They are infrastructure, not evidence of a
win.

The new v7 panel is being assembled from source-qualified CodeContests tasks.
Before any task can be selected, the pipeline removes exact prompt collisions,
checks historic exposure against v1 through v6, and retires any development
panel before another is chosen. Prompts, replies, hidden tests, and adapter
files stay in the lab. Public receipts contain hashes, counts, and the settings
needed to audit a run without publishing the benchmark material.

The evaluation design takes the same basic lesson as
[lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness)
and [HELM](https://arxiv.org/abs/2211.09110): model comparisons need a shared
setup and enough evidence for someone else to inspect the comparison.

## What will count as a win

The detailed preregistration lives with the active Phi experiment branch. A
claim that LocalLLM beats Phi requires all of the following:

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
