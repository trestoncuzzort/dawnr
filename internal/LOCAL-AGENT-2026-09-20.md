# Running a local model in place of a paid one

Written 2026-09-19 when access to the hosted model was ending. Honest about
what this replaces and what it does not.

## What is already on the lab

| model | what it is good for here | fits the free VRAM today? |
|---|---|---|
| `Qwen3-Coder-30B-A3B-Instruct-FP8` | the strongest local coder on the box | **no** at FP8 on one card with ~17 GiB free; yes across two cards with `--tensor-parallel-size 2`, or on one free card |
| `Qwen3-14B` | general reasoning, drives scripts, writes patches | **yes**, 4-bit or FP8 on one card |
| `Qwen3.8-Flash-Next-FP8` | fast, already used for pipeline generation | depends on the size on disk; it graded 116 of 232 well formed |
| `DeepSeek-Prover-V2-7B` | **the best converter measured here**, 6 of 10, 31 clean of 88 training cells | **yes**, ~5 GB in 4-bit |
| `Phi-4-mini-instruct` | the baseline. Do not use it as an agent | yes |
| `Qwen2.5-Coder-1.5B-Instruct` | the old student base | yes |

`~/.venv-vllm/bin/vllm` is installed. The four cards are shared with another
user who is currently holding about 31 GiB of each, so **the free memory, not
the card size, is the constraint**: check `nvidia-smi --query-gpu=index,memory.free
--format=csv,noheader` before choosing, and set `--gpu-memory-utilization` as a
fraction of the **total** 48 GiB, not of what is free.

    ~/.venv-vllm/bin/vllm serve Qwen/Qwen3-14B \
      --port 8000 --gpu-memory-utilization 0.30 --max-model-len 8192

That exposes an OpenAI-compatible endpoint at `http://localhost:8000/v1` with
no key, which most agent harnesses accept.

## What a local model replaces well

**All of the mechanical work, which is most of what is left.** The two scripts
committed today (`t/finish_seeds.sh`, `t/grow_pool.sh`) need no model at all:
they are shell. A 14B is entirely capable of reading the handoff, running them,
reading the score table, and reporting the numbers. So is a person.

It also replaces the *generator* role completely, because that role was never
the hosted model's: every answer in this project's pipeline is already written
by a local model. `DeepSeek-Prover-V2-7B` converts better than anything else
measured here and it runs in 5 GB.

## What it does not replace, stated plainly

The things that moved this project today were not code generation. They were:

- noticing that all 38 correct answers in a twelve-arm study sat on tasks a
  shorter program already passed, which reinterpreted the whole study;
- noticing that `git add` on a scoreboard table was failing silently, so three
  findings cited files the repository did not contain;
- noticing that the grading machine was 19 commits behind with 109 dirty
  entries while every log line looked normal;
- deciding that a prediction which "held" at 18.8 percent was hollow because
  its denominator had collapsed from 136 to 16.

A 14B or 30B will not reliably do that, and the failure mode is not that it
says nothing: it is that it produces a confident, plausible, wrong reading and
nothing in the pipeline catches it. That is the same failure this project
measures in its own models 59 to 204 times a round.

## So use it this way

1. **Let it run the scripts and report the numbers.** Low risk, high value.
2. **Let it generate answers.** That is what the pipeline is for, and every
   answer passes through tests, seven proof systems, a twin refutation and a
   specification check before it counts. The gates do not care which model
   wrote the answer.
3. **Do not let it decide what a number means, silently.** Every claim in this
   repository links to the script that produced it, and the discipline that
   keeps it honest is: predictions registered before a run, a baseline regraded
   beside the new model, and the evaluator state recorded around it. A local
   model can follow that discipline if it is told to. It will not invent it.

`internal/HANDOFF-2026-09-20-antigravity.md` is the state to hand it, and
`internal/RESEARCH-NEXT-2026-09-20.md` is the experiment to point it at.
