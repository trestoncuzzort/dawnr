# dawnr

**An assistant for your computer that runs offline and checks its own work.**

dawnr works in a folder on your machine. It reads your files (text, PDFs, Word, spreadsheets, slides, saved
pages, mail), changes them only as a plan you have seen, runs commands in a sandbox that cannot touch the
folder until you say yes, answers questions about the computer by looking at it, and acts on it with one
command you are shown first. For code it goes further: it writes programs with a precise statement of what
they do and has up to seven independent provers check them. Nothing leaves your machine unless you turn the
network on. There is no account, no cloud and no telemetry.

## Install

Linux, macOS, or Windows through WSL2 (`wsl --install` in PowerShell, then everything below inside Ubuntu).
Python 3.10 or newer, about 9 GB of disk, and about 10 GB of free memory on the CPU. No graphics card is
needed; with an NVIDIA card the installer picks the GPU build by itself (an 8 GB laptop card is plenty).

```bash
git clone https://github.com/trestoncuzzort/dawnr
cd dawnr
./install.sh
```

A fresh Ubuntu first needs `sudo apt install libgomp1 unzip bubblewrap`; the installer checks and prints the
line if anything is missing. It needs no administrator rights, downloads the model server, the models and the
first prover into `~/.local/share/dawnr`, checks every download against its published checksum, and adds a
`dawnr` command. `dawnr doctor` shows what is installed.

## Use it

### In a folder

```bash
cd ~/notes
dawnr                                   # an assistant in this folder; type what you need
dawnr do "Rename the photos by date and tell me how many there are."
dawnr do "Which invoice is overdue? Answer from the PDFs here." --read-only
```

It reads the folder and the folders you add with `--root`, changes files only after showing you the exact
difference, journals every change so `/undo` puts it back, and runs commands in a sandbox with no network over
a copy of the folder: a command that changed nothing is a read, one that would change something is shown to you
with what it would change, and only your yes makes it real. The network stays off unless you pass `--online`.

### On the computer

```bash
dawnr do "How much disk is free, and what is using the CPU?"
dawnr do "Turn on dark mode."
```

Questions about the machine are answered by running a command that can only look. Doing something takes one
command you are shown and asked about every time. Nothing is ever run as administrator: a line that needs
`sudo` is handed to you. Under WSL the desktop is Windows, and dawnr uses Windows's own lines for it.

### Documents

```bash
dawnr cite "When is payment due?" invoice.pdf
dawnr extract invoice.pdf --field "total(number): the amount due" --field "due(date): when payment is due"
```

Both answer only from your files, quoting the sentence each value comes from, and leave a field empty when
the files do not say.

### Numbers

```bash
dawnr calc "A recipe needs 2.5 cups of flour for 12 muffins. How many cups for 30?"
```

The model reasons in words; the working is written as arithmetic and computed exactly, and the answer is shown
only when the two agree.

### Code you can prove

```bash
dawnr ask "Write a function that returns the larger of two numbers." \
  --test "assert larger(3, 5) == 5" --test "assert larger(9, 2) == 9" --save-python larger.py
dawnr verify largest.py                 # a proved twin of a function you already have
dawnr prove largest.t                   # a body for a specification you wrote
dawnr check larger.cert.json            # replay someone's certificate, no model involved
```

An answer is shown only when it passes your tests, its specification holds at an independently written
solution's answers, and a prover proves it; otherwise dawnr says which check stopped it.

### A page instead of a terminal

```bash
dawnr ui
```

opens everything above in your browser, on this machine only. `dawnr serve api` gives the same as a local
HTTP API (`POST /v1/jobs`) and an OpenAI-compatible address for chat programs.

### With the assistant you already use

```bash
claude mcp add dawnr -- dawnr mcp
```

gives an MCP client dawnr's checks as tools (prove, check a certificate, exact arithmetic, quote checking);
its own model is trusted exactly as far as dawnr's: not at all.

All commands, their options and what each one measures: [docs/COMMANDS.md](docs/COMMANDS.md). The guide to
installing, the page and the harness settings: [docs/USER-GUIDE.md](docs/USER-GUIDE.md).

## Commands

| command | what it does |
|---|---|
| `dawnr` | the assistant in the folder you are in (`--read-only`, `--root DIR`, `--online`, `--yes`) |
| `dawnr do "TASK"` | one task, then back to the shell |
| `dawnr cite "QUESTION" FILE...` | an answer from your files, every claim quoting one of their sentences |
| `dawnr extract FILE... --field ...` | fields from your files, each with the sentence it is in |
| `dawnr calc "QUESTION"` | a number reasoned in words, shown when an exact working gives it too |
| `dawnr ask "QUESTION" --test ...` | a proved function from a description and tests, as `t` and Python |
| `dawnr spec` / `dawnr prove SPEC.t` | specifications to pick from; a proved body for one you wrote |
| `dawnr verify FILE.py` | a proved twin of your function, or why not |
| `dawnr check CERT.json` | replay a certificate on this machine's provers |
| `dawnr tools TOOLS.json "REQUEST"` | a tool call handed back only when every value was said |
| `dawnr ui` / `dawnr serve api` | the page in your browser; the local API |
| `dawnr mcp` | the checks as Model Context Protocol tools |
| `dawnr doctor` / `dawnr forget` | what is installed; erase what dawnr kept about your work |

## How it is kept safe

- **Plans, not surprises.** Every change to a file is shown as the exact difference and asked for once; every
  change is journaled with what it replaced, and `/undo` restores it.
- **A sandbox for commands.** Commands run with no network over a copy-on-write layer of the folder
  (bubblewrap on Linux, Seatbelt on macOS); the rest of the disk is read-only and your keys are hidden.
- **The computer, with your yes.** Looking is free; doing takes one command you are shown. Never `sudo`.
- **Nothing is taken on the model's word.** Files, commands and answers are judged by what happened, not by
  what the model said; a plan that would destroy a file goes back to the model before it reaches you.
- **The threat model and what it has been measured against:** [DAWNR-AGENT.md](DAWNR-AGENT.md). What dawnr
  keeps and what leaves the machine (nothing by default): [PRIVACY.md](PRIVACY.md).

## What it needs, and how fast it goes

| machine | the assistant | a proved answer |
|---|---|---|
| a 12-core CPU, no card | 27–29 tokens a second; a task about three model calls | one to two minutes a question |
| a laptop's 8 GB card (RTX 5050, WSL2) | 65–72 tokens a second; 161 tasks in 12.5 minutes | 11 to 27 seconds |
| a 48 GB workstation card | 273 tokens a second | |

The first call of each task costs only the task's own text: the system-and-tools prefix is kept warm between
conversations. The model drafts several tokens at a time from its own prediction layer and from runs it has
already written, which on six CPU cores is 1.9× the tokens a second of plain decoding
([how each number was measured](docs/MEASURED.md)).

## Measured, good and bad

Every number here names the run that produced it; the full account, with what went wrong, is in
[DISCLAIMERS.md](DISCLAIMERS.md) and [docs/MEASURED.md](docs/MEASURED.md).

**The assistant** is judged on 161 hand-written tasks in six sets and on 660 fresh tasks drawn from 66 task
families, each judged by the folder's end state, the command let through, or what the machine itself says,
never by the model's account. On the unseen halves of the hand-written sets, on a CPU: 20 of 20 files tasks,
14 of 15 harder ones, 8 of 11 past those, 21 of 21 about the computer, 9 of 13 of longer work; the same
laptop read 141 of 161. The untaught 4B did 415 of 530 fresh taught-family tasks and 84 of 130 held-out ones,
with 33 judged as harm (a file lost, or a change outside what was asked): each caught by the judge, each
restorable by `/undo`, and the reason the warnings were rewritten.

**Proofs.** On 182 programming problems no training row touches, a problem counts only when the program
passes its tests, a prover verifies it, and its specification agrees with the problem's reference solution on
inputs larger than the examples:

| | proved by at least one prover | an algorithm, not a restatement | proved by all seven |
|---|---:|---:|---:|
| **dawnr v5** (Qwen3.5-4B, fine-tuned here on proved answers) | **17** | **9** | **12** |
| the same 4B before fine-tuning, prompted, 17 tries a problem | 9 | 2 | 6 |
| Phi-4-mini (3.8B), output forced into valid `t`, 17 tries | 7 | 0 | 5 |
| Qwen3.5-27B, six times larger, prompted, 17 tries | 32 | 17 | 22 |

Plainly: much of the lead over Phi comes from the base model, chosen by measurement among openly licensed
ones; the training adds 8 problems. These counts were corrected three times on the day they were published
(contaminated problems removed, inputs made larger, proofs sorted by what they prove); the corrections and
their reasons are in [CORRECTIONS.md](CORRECTIONS.md). A much larger model still does better.

**The seven kernels.** Every committed `t` task is lowered into seven independent proof systems. Each must prove
the program and refute a deliberately broken twin at a concrete input, or refuse by name. Of the 88 tasks, Dafny
proves 88, Verus 80, F* 53, SPARK 50, Rocq 43, Lean 40 and Frama-C 36. In every kernel, the twin of every proved
program is refuted (100%). 36 tasks are proved, with the twin refuted, in all seven; the rest are named refusals,
mostly of the constructs added on 2026-10-06, which the other kernels are being taught now
([the matrix](t/AGREEMENT.md)).

**What went wrong**, kept on the record: a file written into a folder the request did not name; two files
"swapped" with a command that lost one; the smaller of two files removed when the larger was asked for; a
warning misread by the model as "try again". Each is why a check now exists, and each check is measured.

## Models

The model that comes with dawnr is **dawnr v5**, a fine-tuned Qwen3.5-4B (Apache-2.0) published as the
[`student-v5` release](../../releases/tag/student-v5) with its
[model card](release/MODEL-CARD-student-v5.md); the assistant drives the base 4B, 2.8 GB at 4 bits, and a
machine with 24 GB for the model does longer work better with the 35B of the same family. Earlier versions
were called "the student"; files and tags that still say so are these same dawnr models. The writing can also
be done by a larger model behind any OpenAI-compatible address (`DAWNR_WRITER_URL`): whatever writes is never
trusted, and the checks stay on your machine.

## Learn more

| If you want to... | Read... |
|---|---|
| use every command, with its options | [docs/COMMANDS.md](docs/COMMANDS.md) |
| install, run the page, set the harness up | [docs/USER-GUIDE.md](docs/USER-GUIDE.md) |
| know what is measured, what works and what does not | [DISCLAIMERS.md](DISCLAIMERS.md), [docs/MEASURED.md](docs/MEASURED.md) |
| see what was corrected, and why | [CORRECTIONS.md](CORRECTIONS.md) |
| let dawnr act on your machine, and see its threat model | [DAWNR-AGENT.md](DAWNR-AGENT.md) |
| know what dawnr keeps on your machine, what leaves it, and how to erase it | [PRIVACY.md](PRIVACY.md) |
| read the terms of use | [TERMS.md](TERMS.md) |
| understand `t` and the seven provers | [t/README.md](t/README.md) |
| see where dawnr is going | [AMBITION.md](AMBITION.md), [ROADMAP.md](ROADMAP.md) |
| contribute, or report a wrong number | [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) |

## License

Research and education use only; see [LICENSE](LICENSE) and [DISCLAIMERS.md](DISCLAIMERS.md).

Copyright (c) 2026 Treston Malachi Cuzzort.
