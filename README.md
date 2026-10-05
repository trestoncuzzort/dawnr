# dawnr

**An assistant whose answers come with proof.**

> **New, 5 October 2026: dawnr v5.** The dawnr model now proves **18 of 182 held-out programming
> problems** with a specification checked against the problem's own solution, **12 of them by all seven provers**.
> Phi-4-mini, given the same 17 tries a problem and its output forced into valid `t`, proves 7 and 5. Every training
> seed of the recipe beats it at both levels, and given a specification the new model proves **27 of 33** held-out
> ones by all seven provers, more than any earlier release. It is a small model (Qwen3.5-4B, fine-tuned here) that
> runs offline on an ordinary CPU or an 8 GB laptop graphics card.
> [The release](../../releases/tag/student-v5) · [how it was measured](t/PREDICT-2026-10-05-release-v5.md) ·
> [every number, good and bad](DISCLAIMERS.md)
>
> *Corrected the same day.* This first read 26 of 200, and 16. An audit of the training data then found 18 of
> those 200 problems in it under other names, so they are no longer counted, for any model; and 19 of the 33
> specifications are functions the training data also holds under another name (on the other 14 it proves 10).
> [What was found and how](t/DECONTAMINATION-2026-10-05.md).
>
> *A note on names:* dawnr is the name for the models from now on. Earlier versions were called the student, and the
> release tags, files and commands that still say `student` (the `student-v5` release among them) are these same
> dawnr models.

dawnr writes programs together with a precise statement of what they do, then
has seven independent mathematical provers check that the program does exactly
that. If the provers agree, you get the answer and the evidence behind it. If
they do not, dawnr says so instead of guessing.

It runs entirely on your own machine: no cloud, no account, no data leaving
your computer.

## What it has achieved

On 182 programming problems no training row touches (from MBPP), a problem counts only when the
program passes its tests, a prover verifies it, and its specification agrees with the problem's reference solution
and rejects most wrong answers:

| | proved by at least one prover | proved by all seven |
|---|---:|---:|
| **dawnr v5** (Qwen3.5-4B, fine-tuned here on proved answers) | **18** | **12** |
| the same recipe, its two other training seeds | 18, 14 | 10, 8 |
| the same 4B before any fine-tuning, prompted, 17 tries a problem | 9 | 6 |
| Phi-4-mini (3.8B), output forced into valid `t`, 17 tries a problem | 7 | 5 |
| Phi-4-mini, prompted, 17 tries a problem | 2 | 2 |
| Qwen3.5-27B, six times larger, prompted, 17 tries a problem | 33 | 23 |

Plainly: much of the lead over Phi comes from the base model, chosen by measurement among openly licensed ones;
training on answers the provers admitted, some written by two openly licensed teacher models, adds 9 problems and 6
by all seven for this release. Doubling Phi on every training seed, the bar set in [AMBITION.md](AMBITION.md), is met
by two seeds of three, and a much larger model still does better. Every row links to its run in
[DISCLAIMERS.md](DISCLAIMERS.md); the curve across model sizes is in
[t/PREDICT-2026-10-04-size-curve.md](t/PREDICT-2026-10-04-size-curve.md).

## Why it is useful

- **You can trust what it shows you.** Every answer is checked by seven provers
  of the kind used to verify safety-critical software: Dafny, Verus, SPARK,
  Frama-C, Lean 4, Rocq and F*. An answer is shown with how
  many of the seven proved it.
- **It knows when it does not know.** When no answer survives the checks, it
  refuses and names the check that stopped it. A refusal you can see is safer
  than a confident mistake.
- **It catches answers to the wrong question.** A proof only shows a program
  meets its specification. dawnr also checks the specification against the
  problem's own examples and against a second solution written independently,
  so a correct proof of the wrong thing does not get through.
- **You get code you can run.** The proved program also comes back as a Python
  function under your own name. It is shown only when it gave the same answer as
  the proved program on your tests and on up to 200 further inputs, and it says
  plainly that it is tested against the proof, not proved itself.
- **It works offline and on ordinary hardware.** The model is a small, openly
  licensed one, fine-tuned here only on answers that passed the provers. It
  runs on an ordinary CPU, and much faster on a gaming laptop's graphics card
  when there is one; none is needed.
- **It is open about itself.** Every claim links to the run that measured it.
  What it cannot do yet is in [DISCLAIMERS.md](DISCLAIMERS.md).

## How it works

1. **You ask** for a function in plain English, with a few example tests.
2. **The model answers** in `t`, a small language where a program states what
   it requires and what it guarantees.
3. **Cheap checks first.** The answer must parse, type-check and pass your
   tests. A separate solution is written and tested, and the specification must
   agree with it.
4. **The provers decide.** The program is translated into each prover's own
   language. Each must prove it, and each must reject a deliberately broken
   twin of it.
5. **You get the answer with its evidence**, and the same function in Python,
   or a refusal that says why.

If you can say precisely what you want, you can start one step later: give
dawnr the specification, or let it propose some and pick one, and the model
only has to write a body the provers accept. That is where it is strongest,
and it puts your own check where it belongs, on the statement of what the
program must do.

## Get it

You need Linux, macOS or Windows (through WSL2's Ubuntu: run `wsl --install`
in PowerShell, then everything below inside Ubuntu), Python 3.10 or newer and
about 9 GB of disk. No graphics card is needed: on the CPU, both models stay
loaded in about 10 GB of free memory (9.2 GB was measured at the peak of a
question). With an NVIDIA card the installer picks the GPU build by itself; on
a laptop's 8 GB RTX 5050 the models took 7.6 GB of the card and 2.2 GB of
memory.

```bash
git clone https://github.com/trestoncuzzort/dawnr
cd dawnr
./install.sh
```

A fresh Ubuntu (WSL's included) first needs
`sudo apt install libgomp1 unzip bubblewrap`; the installer checks for them
before downloading anything and prints the line with what is missing. The installer itself
needs no administrator rights. It downloads the model server,
the two models and the first prover into `~/.local/share/dawnr`, checks each
download against its published checksum, and adds a `dawnr` command. Then,
starting from a specification:

```bash
dawnr spec "Write a function that returns the largest element of a non-empty list." \
  --test "assert largest([1, 5, 2]) == 5" --test "assert largest([-3, -1]) == -1" --save largest.t
dawnr prove largest.t --save-python largest.py
```

`dawnr spec` shows the specifications the model proposes that hold on your
tests and at an independently written solution's answers, each with the share
of wrong results it rejects. You read them, and the one you keep is what gets
proved. `dawnr prove` asks the model for a body that keeps your specification
unchanged, lets the provers decide, tells you what else your specification
would accept if it is loose, and writes the function in Python. Give it your
own examples with `--test` and it will say so when a proved program still
fails one of them, which means the specification is not yet what you meant. You can also
write `largest.t` yourself ([the notation](t/SYNTAX.md)). Or ask in one step
and let dawnr choose the specification:

```bash
dawnr ask "Write a function that returns the larger of two numbers." \
  --test "assert larger(3, 5) == 5" --test "assert larger(9, 2) == 9" --save-python larger.py
```

Tests may use whole numbers, strings, lists, tuples and lists of lists; when a
test uses something `t` has no value for yet (a decimal number, a dictionary),
dawnr says so before asking anything.

Nobody has to take the answer on trust, including from you. Add
`--certificate larger.cert.json` to `ask` or `prove` and dawnr writes the
answer's record: the program, its specification, the tests, the Python, and
the independently written solution the specification was held against. Anyone
with dawnr installed can replay it, with no model involved:

```bash
dawnr check larger.cert.json
```

That runs the tests again, searches for an input that breaks the
specification, runs the provers on their machine against the program and its
sabotaged twin, and runs the Python beside the proved program. It prints
`REPRODUCED`, `FAILED` with the first thing that did not hold, or
`UNDECIDED HERE` when nothing failed and no prover there finished; a prover
their machine lacks is named, never counted. A certificate that was altered
fails. What a replay cannot tell them is whether the specification is what
you meant, and it says so.

The Python that comes back refuses what was not proved: an input outside the
program's `requires` raises `ValueError`, an argument of another type raises
`TypeError`, and that guard is itself run beside the proved program before
the function is shown.

A question takes one to two minutes on an ordinary CPU (the two commands above
took 130 and 92 seconds on a desktop's), and 11 to 27 seconds
on that laptop's card (19 for a first question that also starts the models, 27
for a refusal, which tries every answer). `dawnr doctor`
shows what is installed. dawnr runs code the models write only inside a sandbox
(bubblewrap on Linux, Apple's Seatbelt on macOS). On Ubuntu 23.10 and newer,
which restrict the sandbox by default, run once: `sudo bash t/apparmor-bwrap.sh`.
The installer sets up Dafny; adding the other six
provers (see [t/README.md](t/README.md)) lets an answer be proved up to seven
times over. The student model is published under Apache-2.0 as the
[`student-v5` release](../../releases/tag/student-v5), with its
[model card](release/MODEL-CARD-student-v5.md); see also [DISCLAIMERS.md](DISCLAIMERS.md).

## Learn more

| If you want to... | Read... |
|---|---|
| know what is measured, what works and what does not | [DISCLAIMERS.md](DISCLAIMERS.md) |
| see where dawnr is going | [AMBITION.md](AMBITION.md) |
| understand `t` and the seven provers | [t/README.md](t/README.md) |
| let dawnr act on your machine, and see its threat model | [DAWNR-AGENT.md](DAWNR-AGENT.md) |

## License

Research and education use only; see [LICENSE](LICENSE) and
[DISCLAIMERS.md](DISCLAIMERS.md).

Copyright (c) 2026 Treston Malachi Cuzzort.
