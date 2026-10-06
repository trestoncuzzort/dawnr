# The commands, in depth

What each `dawnr` command does, how it decides what to show, and what it was measured on. The short list is in
the [README](../README.md); the install and the page are in [USER-GUIDE.md](USER-GUIDE.md). This page holds the
long account that the README carried until 2026-10-06, moved here as it was.

## The assistant: `dawnr` and `dawnr do`

`dawnr` on its own opens an assistant in that folder, on the base model, with
nothing to configure. It reads the files there (and in any folder you name with
`--root`): text, PDFs, Word files, spreadsheets (a sheet at a time, dates as
dates), slides, OpenDocument files, EPUB books, saved web pages and saved
emails. The folder you start it in is the only place it may change. A write or
an edit is shown first, as a plan with the exact difference, and asked for
once; every change is journaled with what it replaced, so `/undo` puts it
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

It also looks at the computer itself, and acts on it. A question about the
machine as it is now (what is running, how much disk is free, whether a service
is up, what is installed) is answered by running a command that can only look,
without asking you, and from what that command printed. To do something (open
a file or a program, turn on dark mode, set the volume, start a service) it
proposes one command; you are shown the exact line and asked, every time,
whatever `--yes` says. Nothing is ever run as administrator: a line that needs
sudo, and any package install, is handed to you to run yourself. A command
that names a place where keys are kept is not run, and with the network off no
address is opened. In a repository it reads with git freely (status, diff,
log) and commits through the same asked-for command; what would discard work
that is in no commit is handed to you instead of run.

With `--online` it can search the web and read pages, and each search and each
page is asked for. The search needs no account or key: it reads DuckDuckGo's
page for browsers without JavaScript, as a text browser would. A page is not
handed to the model whole: told what it is looking for, the fetch returns the
paragraphs about that, in the page's order and within a budget, so a long
page costs a few hundred tokens rather than thousands. A search or an
address that carries text it read from one of your files is marked as that
before you are asked.

## Code you can prove: `spec`, `prove`, `ask`, `check`, `verify`

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
write `largest.t` yourself ([the notation](../t/SYNTAX.md)). Or ask in one step
and let dawnr choose the specification:

```bash
dawnr ask "Write a function that returns the larger of two numbers." \
  --test "assert larger(3, 5) == 5" --test "assert larger(9, 2) == 9" --save-python larger.py
```

Tests may use whole numbers, strings, lists, tuples and lists of lists; when a
test uses something `t` has no value for yet (a decimal number, a dictionary),
dawnr says so before asking anything.

Give tests when you can. Without `--test`, in a terminal, `dawnr ask` runs a
few drafts on small inputs and puts their results to you as examples to accept
or correct, and what you accept becomes the tests. Measured with a benchmark's
reference solution standing in for the person, on 80 questions: two or more
examples were made for 64, and an answer was shown for 9 where the benchmark's
own tests gave 6. But 3 of the 9 were proved answers to a slightly different
question, one the accepted examples did not rule out, where all of the answers
shown with real tests were right
([the record](../t/PREDICT-2026-10-05-examples.md)).

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
questions ([the record](../t/PREDICT-2026-10-05-verify-python.md)). What it adds
is the comparison with the function you already have.

## Documents: `cite` and `extract`

And for documents rather than code, two commands answer only from your own
files:

```bash
dawnr cite "When is payment due?" invoice.txt
dawnr extract invoice.txt --field "total(number): the amount due" --field "due(date): when payment is due"
```

The files can be plain text in any common encoding, Word documents, saved
web pages or PDFs (read with `pdftotext` when your machine has it and with
dawnr's own copy of PDFium when it does not; a quote from a PDF is shown with
its page), in any script: sentences are found by
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
did on 72% ([DISCLAIMERS.md](../DISCLAIMERS.md)).

## Numbers: `calc`

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

## Tools for a model: `tools`

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

## A larger writer behind the same checks

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

## As a checker for the assistant you already use: `mcp`

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

## The page and the API: `ui` and `serve api`

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

## Time, provers and the sandbox

A question takes one to two minutes on an ordinary CPU (the two commands above
took 130 and 92 seconds on a desktop's), and 11 to 27 seconds
on that laptop's card (19 for a first question that also starts the models, 27
for a refusal, which tries every answer). `dawnr doctor`
shows what is installed. dawnr runs code the models write only inside a sandbox
(bubblewrap on Linux, Apple's Seatbelt on macOS). On Ubuntu 23.10 and newer,
which restrict the sandbox by default, run once: `sudo bash t/apparmor-bwrap.sh`.
The installer sets up Dafny; adding the other six
provers (see [t/README.md](../t/README.md)) lets an answer be proved up to seven

