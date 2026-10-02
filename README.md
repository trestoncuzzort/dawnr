# dawnr

**An assistant whose answers come with proof.**

dawnr writes programs together with a precise statement of what they do, then
has seven independent mathematical provers check that the program does exactly
that. If the provers agree, you get the answer and the evidence behind it. If
they do not, dawnr says so instead of guessing.

It runs entirely on your own machine: no cloud, no account, no data leaving
your computer.

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
- **It works offline and on ordinary hardware.** The model is a small, openly
  licensed one, fine-tuned here only on answers that passed the provers. It
  runs on an ordinary CPU; no graphics card is needed.
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
5. **You get the answer with its evidence**, or a refusal that says why.

## Get it

You need Linux or macOS, Python 3.10 or newer, about 8 GB of disk and about
10 GB of free memory (both models stay loaded; 9.2 GB was measured at the peak
of a question). No graphics card is needed.

```bash
git clone https://github.com/trestoncuzzort/dawnr
cd dawnr
./install.sh
```

The installer needs no administrator rights. It downloads the model server,
the two models and the first prover into `~/.local/share/dawnr`, checks each
download against its published checksum, and adds a `dawnr` command. Then:

```bash
dawnr ask "Write a function that returns the larger of two numbers." \
  --test "assert larger(3, 5) == 5" --test "assert larger(9, 2) == 9"
```

A question takes one to two minutes on an ordinary CPU. `dawnr doctor`
shows what is installed. dawnr runs code the models write only inside a sandbox
(bubblewrap on Linux, Apple's Seatbelt on macOS). On Ubuntu 23.10 and newer,
which restrict the sandbox by default, run once: `sudo bash t/apparmor-bwrap.sh`.
The installer sets up Dafny; adding the other six
provers (see [t/README.md](t/README.md)) lets an answer be proved up to seven
times over. The student model is published under Apache-2.0 as the
[`student-v1` release](../../releases/tag/student-v1), with its
[model card](release/MODEL-CARD-student-v1.md); see also [DISCLAIMERS.md](DISCLAIMERS.md).

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
