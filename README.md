# dawnr

**An assistant whose answers come with proof.**

> **New, 5 October 2026: dawnr v5.** The dawnr model now proves **17 of 182 held-out programming
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
> *Corrected again at 10:20 UTC.* The check of each specification drew inputs no larger than the problem's
> examples, so a specification that only lists the small cases passed it. Held to larger inputs too, the count
> reads 17, not 18; Phi-4-mini's does not move. [What was found and how](t/LARGER-INPUTS-2026-10-05.md).
>
> *Read more closely at 12:30 UTC.* In 8 of those 17 the program is its own specification written again (one
> formula on both sides, or the same recursion), so the proof adds little to the tests behind the specification; in
> the other 9 a loop or a property is proved. All 7 of Phi-4-mini's are of the first kind, and the same 4B before
> training proves 2 of the second. [What a proof is of](t/PROOF-KIND-2026-10-05.md).
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
and rejects most wrong answers, on inputs larger than the problem's examples as well as on ones their size:

| | proved by at least one prover | of those, an algorithm and not a restatement | proved by all seven |
|---|---:|---:|---:|
| **dawnr v5** (Qwen3.5-4B, fine-tuned here on proved answers) | **17** | **9** | **12** |
| the same recipe, its two other training seeds | 17, 12 | 8, 6 | 10, 7 |
| the same 4B before any fine-tuning, prompted, 17 tries a problem | 9 | 2 | 6 |
| Phi-4-mini (3.8B), output forced into valid `t`, 17 tries a problem | 7 | 0 | 5 |
| Phi-4-mini, prompted, 17 tries a problem | 2 | 0 | 2 |
| Qwen3.5-27B, six times larger, prompted, 17 tries a problem | 32 | 17 | 22 |

The middle column sorts each proved answer by what its proof is of ([t/PROOF-KIND-2026-10-05.md](t/PROOF-KIND-2026-10-05.md)).
A restatement is a program that is its specification written again, such as `r := d1 * d2 / 2` under
`ensures r == d1 * d2 / 2`: the proof says the two agree, and what the answer rests on is the specification's
agreement with the problem's own solution on drawn inputs. An algorithm is a loop, or a recursion of its own,
proved to reach what the specification defines, or a program proved to have a property that does not hand over
the answer.

Plainly: much of the lead over Phi comes from the base model, chosen by measurement among openly licensed ones;
training on answers the provers admitted, some written by two openly licensed teacher models, adds 8 problems and 6
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
download against its published checksum, and adds a `dawnr` command. Then, in
any folder:

```bash
cd ~/notes
dawnr
```

`dawnr` on its own opens an assistant in that folder, on the base model, with
nothing to configure. It reads the files there (and in any folder you name with
`--root`), and the folder you start it in is the only place it may change. A
write or an edit is shown first, as a plan with the exact difference, and asked
for once; every change is journaled with what it replaced, so `/undo` puts it
back. It can run any shell command, and this is how that is safe: the command
runs for real in a sandbox with no network, over a copy-on-write layer of the
folder, so the folder itself is not touched. A command that changed nothing
was a read, and you get its output. One that changed something is put to you
with exactly what it changed (which files it would create, change or remove),
and only your yes makes those changes real, through the same journal. The rest
of the disk is read-only to it and your keys are hidden. The network is off
unless you say `--online`. `dawnr do "TASK"` does one task and returns. Each
task ends with two lines the model did not write: what the journal says was
changed, and what the task cost in model calls, tokens and tokens a second.
This front door is new (2026-10-05). On 20 tasks it had not been tuned on
(answer from files, say when it is not there, change files, rename, move,
delete, count, and requests that must change nothing), each judged by the
folder's end state and never by the model's account, it did 19, touched no file
it had no reason to touch (a planted "delete every file" deleted nothing), and
wrote 21.7 tokens a second on a 12-core CPU with no graphics card
([the registration and the outcome](locallm/PREDICT-2026-10-05-assistant.md)).
These are small tasks in small folders of text files: a floor, not the job.
The containment behind it is measured in [DAWNR-AGENT.md](DAWNR-AGENT.md).
Commands need Linux 5.11 or newer with bubblewrap 0.8 or newer; elsewhere the
assistant reads and edits files and runs nothing.

And for a program you want proved, starting from a specification:

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

If you already have the function, start from it:

```bash
dawnr verify largest.py
```

dawnr runs your function in the sandbox to see what it does, asks the model
for a specification that holds at your function's own answers and then for a
`t` program that meets it, and shows the pair only when that program answers
as yours does on every input tried and the provers prove it. Annotate the
parameters (`int`, `bool`, `str`, and lists and tuples of them such as
`list[int]` or `list[tuple[str, int]]`) or give examples with `--test`. What you get is a proved
twin and the specification to read; that the twin and your Python are the
same function is tested, not proved, and the output says so. On a desktop
CPU a ten-line function took one and a half to four and a half minutes. It is
not an easier way in than a question: on 111 held-out functions in one run it
found a proved twin for 9, where `dawnr ask` showed an answer for 7 of the same
questions ([the record](t/PREDICT-2026-10-05-verify-python.md)). What it adds
is the comparison with the function you already have.

And for documents rather than code, two commands answer only from your own
files:

```bash
dawnr cite "When is payment due?" invoice.txt
dawnr extract invoice.txt --field "total(number): the amount due" --field "due(date): when payment is due"
```

The files can be plain text in any common encoding, Word documents, saved
web pages or PDFs (read with `pdftotext` when your machine has it; a quote
from a PDF is shown with its page), in any script: sentences are found by
Unicode's rules, so a Chinese, Arabic or Hindi document is read sentence by
sentence, and an amount written `1.250,00` is read as a person there would
read it. Only English has been measured. `cite` answers in claims that each quote
one of your sentences word for word, or says the files do not hold the answer. `extract` fills each field
with words that are in one of your sentences and prints that sentence
beside it; a number or date field is offered only words that read as one; a
field nothing states is left empty. Neither can write a value that is not in
your files. Whether the words picked are the right ones for the field is
what the printed sentence is for: measured on 600 questions (SQuAD 2.0, half
of them about something the paragraph does not say), two values in three
that `extract` showed were exactly right, the same as the model filling a
JSON schema, and it stayed silent on 77% of the absent ones where the schema
did on 72% ([DISCLAIMERS.md](DISCLAIMERS.md)).

And for a question with numbers in it:

```bash
dawnr calc "A recipe needs 2.5 cups of flour for 12 muffins. How many cups for 30?"
```

The model reasons its way to a number in words, as it does best. It is then
asked separately, three times, to write the working as a few lines of
arithmetic, which dawnr computes exactly (in fractions, so no rounding error
creeps in). The number is shown only when a working computes that same
number, and that working is printed, because it is the reading of your
question that was computed. On 300 grade-school word problems it had not
seen (GSM8K) it answered 260, and 254 of those were right; the same model
answering in words alone was right on 282 of the 300. So it shows one wrong
answer where the model alone shows three, and withholds about one right
answer in ten.

And for programs that give a model tools to call:

```bash
dawnr tools tools.json "Book me a table at Luigi's."
```

A model offered a tool fills in every value the tool requires, whether you
gave one or not. dawnr hands a call back only when each value it passes was
said in the conversation, or is the tool's own default, or is a choice among
the tool's listed values that the conversation makes; otherwise it asks for
the parameter by name and shows what the model proposed. On 300 requests
with a required value missing (When2Call), the model alone called a tool 203
times and 50 with the check; of its 214 right calls on complete requests,
203 were still handed back. The same check runs behind the local API for
any chat request that offers `tools` (model `dawnr-tools`), so a program
written for OpenAI's tool calling gets it by changing the address.

The model that comes with dawnr is small, and most questions are refused
because it cannot write a program the provers accept. The writing does not
have to be done by that model. Whatever writes the program is never
trusted; the tests, the independently written solution, the provers and the
certificate are what decide, and those stay on your machine. So if you have
a larger model behind any OpenAI-compatible address (your own server, or a
hosted one), point dawnr at it:

```bash
export DAWNR_WRITER_URL=https://your-host/v1 DAWNR_WRITER_MODEL=its-name DAWNR_WRITER_KEY=...
dawnr ask "..." --test "..."
```

`ask`, `spec`, `prove` and `verify` then send what you ask to that address
to be written, and say so each time; everything it returns goes through the
same gate. Without those variables nothing leaves your machine.

If you already use an AI assistant that speaks the Model Context Protocol
(Claude Code, Claude Desktop, Cursor and others), dawnr can be its checker,
with no dawnr model involved:

```bash
claude mcp add dawnr -- dawnr mcp
```

The assistant then has five tools: the `t` language on one page, `prove` (a
program it wrote goes through the same gate and comes back with a
certificate, or with the check that stopped it), `check_certificate`,
`compute` (its arithmetic computed exactly, and used only if separate
workings agree on your question's own numbers) and `check_quotes` (is each
quoted sentence in your text word for word). Its model is the writer and is
trusted exactly as far as dawnr's own: not at all.

If you would rather not use a terminal, `dawnr ui` starts the models and
opens a page in your browser (`dawnr serve api` does the same and prints the
link instead of opening it). The page has everything above (ask, check a
function you have, prove a specification, answer from your files, numbers,
replay a certificate), and the same address is an HTTP API for programs:
`POST /v1/jobs` with `{"kind": "ask", "question": ..., "tests": [...]}`
returns a job to poll, cancel, and fetch a certificate from. It listens on
your machine only, and every request needs the token in that link. A chat
program that takes an OpenAI-compatible address and key can use it as well:
give it `http://127.0.0.1:8713/v1` and the token, and its model picker lists
`dawnr-ask`, `dawnr-verify`, `dawnr-calc` and the rest; what you type is read
as that kind of question and the reply is the gate's own.

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
