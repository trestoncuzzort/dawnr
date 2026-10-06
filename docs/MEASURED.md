# What has been measured, in full

The long account of every reading behind the README's numbers, as the README carried it until 2026-10-06,
moved here as it was. The short version and the headline table are in the [README](../README.md); every
run, good and bad, is in [DISCLAIMERS.md](../DISCLAIMERS.md); what was corrected and why is in
[CORRECTIONS.md](../CORRECTIONS.md).

## The release of 5 October 2026, and its corrections

> **New, 5 October 2026: dawnr v5.** The dawnr model now proves **17 of 182 held-out programming
> problems** with a specification checked against the problem's own solution, **12 of them by all seven provers**.
> Phi-4-mini, given the same 17 tries a problem and its output forced into valid `t`, proves 7 and 5. Every training
> seed of the recipe beats it at both levels, and given a specification the new model proves **27 of 33** held-out
> ones by all seven provers, more than any earlier release. It is a small model (Qwen3.5-4B, fine-tuned here) that
> runs offline on an ordinary CPU or an 8 GB laptop graphics card.
> [The release](../../../releases/tag/student-v5) · [how it was measured](../t/PREDICT-2026-10-05-release-v5.md) ·
> [every number, good and bad](../DISCLAIMERS.md)
>
> *Corrected the same day.* This first read 26 of 200, and 16. An audit of the training data then found 18 of
> those 200 problems in it under other names, so they are no longer counted, for any model; and 19 of the 33
> specifications are functions the training data also holds under another name (on the other 14 it proves 10).
> [What was found and how](../t/DECONTAMINATION-2026-10-05.md).
>
> *Corrected again at 10:20 UTC.* The check of each specification drew inputs no larger than the problem's
> examples, so a specification that only lists the small cases passed it. Held to larger inputs too, the count
> reads 17, not 18; Phi-4-mini's does not move. [What was found and how](../t/LARGER-INPUTS-2026-10-05.md).
>
> *Read more closely at 12:30 UTC.* In 8 of those 17 the program is its own specification written again (one
> formula on both sides, or the same recursion), so the proof adds little to the tests behind the specification; in
> the other 9 a loop or a property is proved. All 7 of Phi-4-mini's are of the first kind, and the same 4B before
> training proves 2 of the second. [What a proof is of](../t/PROOF-KIND-2026-10-05.md).
>
> *A note on names:* dawnr is the name for the models from now on. Earlier versions were called the student, and the
> release tags, files and commands that still say `student` (the `student-v5` release among them) are these same
> dawnr models.

## Proofs on held-out problems

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

The middle column sorts each proved answer by what its proof is of ([t/PROOF-KIND-2026-10-05.md](../t/PROOF-KIND-2026-10-05.md)).
A restatement is a program that is its specification written again, such as `r := d1 * d2 / 2` under
`ensures r == d1 * d2 / 2`: the proof says the two agree, and what the answer rests on is the specification's
agreement with the problem's own solution on drawn inputs. An algorithm is a loop, or a recursion of its own,
proved to reach what the specification defines, or a program proved to have a property that does not hand over
the answer.

Plainly: much of the lead over Phi comes from the base model, chosen by measurement among openly licensed ones;
training on answers the provers admitted, some written by two openly licensed teacher models, adds 8 problems and 6
by all seven for this release. Doubling Phi on every training seed, the bar set in [AMBITION.md](../AMBITION.md), is met
by two seeds of three, and a much larger model still does better. Every row links to its run in
[DISCLAIMERS.md](../DISCLAIMERS.md); the curve across model sizes is in
[t/PREDICT-2026-10-04-size-curve.md](../t/PREDICT-2026-10-04-size-curve.md).

## The assistant on its tasks

This front door is new (2026-10-05). It is measured on 161 tasks in five sets
(`locallm/dawnr_tasks.py`), each judged by the folder's end state, by the
command that was let through, or against what the machine itself says, never by
the model's account. Half of each set stays unseen until a prediction about it
is written down
([the registrations and their outcomes](../locallm/PREDICT-2026-10-05-assistant.md)).
On the unseen halves, on a 12-core CPU with no graphics card:

- **19 of 20, then 20 of 20** on a second reading: answer from files, say when
  it is not there, change files, rename, move, delete, count, and requests that
  must change nothing (a planted "delete every file" deleted nothing).
- **14 of 15** harder ones: make failing tests pass, write a script that prints
  the right lines, find one sentence in a 2,000-line file, read a Word file, a
  saved page and a PDF, change several files at once.
- **8 of 11** past those: code that must pass a test it is given, data joined
  and summed into an exact file, questions that need a short program.
- **21 of 21** about the computer itself: questions answered from the machine
  (and checked against it), requests done by one command that was shown and
  recorded, and installs handed over as the right line for Fedora, Arch,
  openSUSE, Debian and Alpine.
- **9 of 13** of longer work, read on a workstation card: three mistakes in
  three files behind one failing test, a function written to a dozen test
  cases, three tables joined, two clauses of a long contract, a repository
  asked what changed, a chain of renames where the order matters.

It writes 27 to 29 tokens a second there, and a task takes about three model
calls. The installer gives the base model file back the prediction layer its
4-bit conversion left out (81 MB, every other weight untouched), and the model
drafts with it: that is the 29, where it wrote 17 without; 72 on a laptop's
8 GB card and 273 on a 48 GB workstation card, the same tasks done on each.

The first call of every task used to cost the 2,220-token prefix again (the
system text and the eight tools: 19 seconds on six CPU cores), because the
server can take a conversation up only from a checkpoint, and it makes one
only at the end of a prompt it has processed. Since 2026-10-06 the launcher
processes the prefix alone before each conversation, which leaves a checkpoint
where the next task needs it: the first call then costs the task's own 100 to
150 tokens (`locallm/dawnr_warm.py`, measured on the lab's CPUs). The same
morning the draft changed: on six CPU cores, the same eight tasks, the model
wrote 11.3 tokens a second with no drafting, 12.0 drafting 3 tokens from the
prediction layer, 15.8 at 5, 17.7 at 6, 16.1 at 8, and 21.2 at 6 with runs it
had already written drafted from the text as well (llama.cpp's `ngram-mod`
beside `draft-mtp`), which is what the launcher now does
([PREDICT, S](../locallm/PREDICT-2026-10-05-assistant.md)). On a machine whose
card sits on a slow PCIe link, `DAWNR_GPU_LAYERS=0` now keeps the card out of
prompt reading too (`--device none`): this desktop's link had fallen to
generation 1 of 3 and read prompts at 6 tokens a second through it, 130 to
200 without.

The assistant drives whatever model the server holds, and four sizes of the
same family were read on the same tasks and the same card. On the first four
sets nothing separates them: 129, 132, 132 and 133 of 135 for 4, 9, 27 and 35
billion parameters. On the longer work it shows: 19 and 20 of 26 for the two
small ones, 25 for each of the two large ones, and the 35B (which uses 3B of
its weights per token) finished as soon as the 4B by needing fewer turns. The
default stays the 4B, 2.8 GB, because it is what an ordinary machine holds; a
machine with 24 GB for the model does longer work better with the 35B.

On an ordinary laptop (an 8 GB card, Windows with Ubuntu under WSL2), all 161
tasks took 12.5 minutes: about three seconds a task, 65 tokens a second, 135
done. That reading was registered first and missed its bar on the first four
sets (117 of 135, where the workstation card read 129), for reasons that are
the product's and are said plainly: seven tasks that act on a desktop had
nothing to act with (under WSL the desktop is Windows, and dawnr had no lines
for it), two PDFs could not be read because a fresh Ubuntu has no
`pdftotext`, and three right answers were refused by the judge. The rest is
arithmetic: the same file on another card writes another token at a close
call, and ten tasks changed hands between the two machines for no other
reason. Since that reading the installer brings its own PDF reader (PDFium,
3.8 MB, used where `pdftotext` is missing), the three judges are corrected,
and the same machine read 141 of the 161.

Under WSL the desktop is Windows, and dawnr now treats it as one: it says so
in what the model is told about the computer, gives it Windows's own lines
(open a file with Explorer, lock the screen, empty the recycle bin, mute, the
clipboard, shut down, close a program, send a notification, and what to call
to find out the battery, the version, the programs running, the Wi-Fi network,
free space, the computer's name, the time zone, dark mode), each read from
Microsoft's documentation, runs the read-only ones unasked (`tasklist.exe`,
`tzutil.exe /g`, PowerShell `Get-*` lines in the shape the Codex CLI allows,
with no file readers), hands `runas` over like `sudo`, refuses `diskpart` and
a sweep of `C:\Windows`, and treats `key=clear` and browsers' password stores
as secrets. A sixth task set asks a real Windows laptop eight questions and
nine acts and one refusal: registered first, it read 2 of 8 questions and 9 of
9 acts (the table said how to do things and not how to look); with the
looking lines added it reads 16 of 18
([H in the registrations](../locallm/PREDICT-2026-10-05-assistant.md)).

What went wrong in those readings. One prediction failed: a file was written
into a folder the request did not name (nothing was overwritten). Twice the
model "swapped" two files with a command that loses one of them, and the
measurement's person, who says yes to everything, let it. Once, in a later
reading, it removed the smaller of two files when asked for the larger and
reported the larger deleted. `/undo` restores each. Since then: a plan that
would leave a file's contents in no file goes back to the model with that said
before you are asked, and `--yes` does not answer for it (the first wording of
that warning was itself misread as "the command did not run, try again"; it now
says what would be destroyed and why, and calls a wrong order of moves a
mistake instead of asking); an answer that does
not name a file the journal says was removed is sent back once; and a command
line copied word for word from a document reaches you marked as copied. In no
reading did a line that asks for administrator rights, names a key or reaches
the network get through.

These are small tasks in small folders: a floor, not the job. The measurement
never runs a command on the computer itself (it records the line), three of
the five other distributions are one-sentence descriptions, and all 161 tasks
have now been seen once. The containment behind it is measured in
[DAWNR-AGENT.md](../DAWNR-AGENT.md).
Commands need bubblewrap. With bubblewrap 0.11 or newer they run over an
overlay of the folder; with an older one (Ubuntu 24.04 ships 0.9, Debian 12
ships 0.8) over a private copy of it, which is slower and limited to folders
of 256 MB. Without bubblewrap (macOS, Windows outside WSL) the assistant reads
and edits files and runs nothing. The sandbox, the file tools and the front
door are tested on every push on Debian 13, Ubuntu 24.04, Fedora 44, Arch and
openSUSE Tumbleweed, each in its own container (where the copy mode is the one
that can run), and both modes on Ubuntu 26.04 on a real disk.

## Examples made by the model, measured

Give tests when you can. Without `--test`, in a terminal, `dawnr ask` runs a
few drafts on small inputs and puts their results to you as examples to accept
or correct, and what you accept becomes the tests. Measured with a benchmark's
reference solution standing in for the person, on 80 questions: two or more
examples were made for 64, and an answer was shown for 9 where the benchmark's
own tests gave 6. But 3 of the 9 were proved answers to a slightly different
question, one the accepted examples did not rule out, where all of the answers
shown with real tests were right
([the record](../t/PREDICT-2026-10-05-examples.md)).

