# locallm

**Point it at your own writing and it builds a language model from random
numbers, on your computer, with nothing uploaded. The same repository holds the
machine that made its training data: a specification language lowered into seven
independent proof systems, where an example is kept only if all seven prove it
and all seven catch a deliberately broken copy of it.**

The industry bet is scale: more parameters, more tokens, more scraped code. This
one bets the other way. Keep only what can be proved, then see how far a small
model gets on it.

## The result

**locallm's headline model has 92 million parameters. Phi-4-mini has 3.8
billion, 41 times more. On 232 held-out programming problems, both produced
exactly 3 answers that were correct and formally proved. All three of
locallm's are on problems its training data already answered: on the 200 that
it did not, locallm has produced none in any round, and Phi has 2.**

| | locallm | Phi-4-mini |
|---|---:|---:|
| parameters | **92M** | 3.8B |
| trained | from random numbers: pretrained on four shared GPUs, then specialized on one | by Microsoft, on a cluster |
| **clean answers of 232** | **3** | **3** |
| of those, confirmed to specify the right problem | **3** | 2 |
| of those, written rather than recalled from its training set | **2** | 3 |
| **clean answers on the 200 problems its training data does not already answer** | **0** | **2** |

An answer counts as **clean** only when it passes the problem's own tests, is
verified against its specification by **seven independent proof systems** (Dafny,
Verus, SPARK, Frama-C, Lean 4, Rocq, F\*), and all seven catch a deliberately
sabotaged copy of it at a concrete input. That is a far harder bar than passing
unit tests. Phi was regraded the same day, by the same evaluator, beside locallm,
so the two numbers are comparable rather than quoted from different weeks.

**"locallm" is several models, not one.** The 92M above is the arm
`locallm-r7b-headed2`: a core pretrained from random weights on source code, then
specialized on the proved corpus with every document headed by its problem and
signature. It was sampled at temperature 0.5, where the later rounds decode
greedily. The smaller rounds, trained from random weights on the corpus alone,
are separate checkpoints with their own sizes. Every arm is listed with its
parameter count, decoding and score in [`SCOREBOARD.md`](SCOREBOARD.md).

**The tie is on problems locallm had, in effect, already seen.** Checked on
2026-09-21: 32 of the 232 held-out problems have a training document that solves
the same function. MBPP repeats functions under different ids across the split,
and two of the 32 are the held-out problems themselves, lifted from a Dafny
dataset under a name the held-out filter did not recognize. Of locallm's 23 clean
answers across every round, 22 are on those 32, and the 23rd has a specification
that describes the wrong function. On the other 200 problems, locallm has passed
a problem's own tests once in ten runs. Phi-4-mini passes 5 there and is clean on
2. So locallm today writes well-formed, proved programs, and has not yet solved a
problem it was not effectively shown.
[`t/DECONTAMINATION-2026-09-21.md`](t/DECONTAMINATION-2026-09-21.md) has the 32
with the reason for each.

Two narrower findings from the same day, with their tables in
[`t/FINDINGS-r10-and-recitation-2026-09-21.md`](t/FINDINGS-r10-and-recitation-2026-09-21.md):
10 of locallm's 23 clean answers are a training document with names erased
(against 1 of 23 for models that never saw the corpus), and a later checkpoint,
round 10, scored 5 clean. All five are on the 32.

**What happens next is in [`t/RUN-NEXT-locallm-r12.md`](t/RUN-NEXT-locallm-r12.md):**
nine defects fixed before anything trains, a corpus decontaminated against the
32, and one number to move: tests passed on the 200. Phi has never seen t, so most
of its answers do not parse; the full caveats are in [`LIMITS.md`](LIMITS.md).

## Running it

```
python3 locallm/app.py
```

That is the whole thing on Linux and macOS. It needs Python with Tk, which on
Debian and Ubuntu means `sudo apt install python3-tk`, because tkinter ships as a
separate package there. Training additionally needs PyTorch; the window opens,
explains itself, and can still write text without it.

**It does something before you install anything else.**
`locallm/plain_generate.py` runs a trained model in the standard library alone,
no PyTorch and no numpy. Measured on the 43.5 MB round 4 checkpoint: it loads in
seconds and writes about a quarter of a second per character (249 ms including
the load on one machine, 292 ms on another). Slow, and enough to see what the
thing does on a machine that has never installed a machine learning library.

**The download carries a model. A clone does not.** The release zip built by
`locallm/release.py` includes one as `included-model/`, so unzipping and running
gives you something that talks back immediately. This repository stores its
checkpoints under `t/runs/` through Git LFS, so a plain `git clone` gets pointer
files rather than weights. To get them:

```
git lfs pull
python3 locallm/plain_generate.py --out t/runs/2026-09-17/home-4080/models/model-r4 --prompt "function to "
```

An earlier version of this section said a trained model ships with the
repository. It ships with the download. See [`CORRECTIONS.md`](CORRECTIONS.md).

## What it reads

Point it at a file or a folder. One reader decides, and it either decodes your
text properly and tells you which encoding worked, or it refuses and says why in
a sentence you can act on. It never returns half a file.

- **Whatever encoding it can identify.** A byte order mark decides outright, then
  strict UTF-8, then cp1252. This matters more than it sounds: a note saved from
  Windows Notepad as UTF-16 used to arrive as 4,960 characters of which 2,560
  were NUL, and the same note in Japanese kept one character of its eighteen.
  Both now read exactly.
- **Word documents, EPUB books and HTML**, read with the standard library alone,
  so the dependency list stays PyTorch and Tk.
- **PDF and RTF are refused by name**, with what to do instead. A PDF used to be
  accepted as prose and contributed 576 characters of printer instructions to the
  vocabulary.
- **Any script.** The window's tokenizer works on characters, so Arabic, Chinese
  and Devanagari need nothing special from it. What they need is a font that can
  draw them, and the window says so when one is missing rather than showing
  empty boxes.

## What locallm has done

Eight results, each linked to the script that produced it:
[`locallm/ACHIEVEMENTS.md`](locallm/ACHIEVEMENTS.md). The short version:

1. **It learned a formal language almost perfectly, from nothing.** Round 4,
   10.9M parameters trained from random weights, wrote a well-formed program for
   **209 of 232** unseen problems. Phi-4-mini, about 350 times larger, managed
   **12**. Everyone assumes notation is the hard part for a tiny model. It isn't.
   It's nearly free.
2. **It ties a model 41 times its size on clean answers**, 3 each, and only on
   problems its training data already answered. On the 200 held-out problems
   that it did not, locallm has 0 and Phi 2.
3. **When it is right, it is almost always provably right.** Across every round,
   **23 of the 25** locallm answers that passed their problem's tests also cleared
   all seven provers with the sabotaged copy caught. Phi's rate is 3 of 6. The
   two exceptions are one answer each in round 9 seed 7 and round 10. This is
   weaker than it sounds: 22 of the 23 are on problems whose training document
   was already verified, so it mostly measures recall of proved programs.
4. **Stop it and restart it and you get the identical model**, bit for bit, with
   a test that fails the moment that stops being true. That is resuming on a CPU.
   Retraining the same recipe from scratch on a GPU does not reproduce: every
   weight tensor differs, by up to 0.0016.
5. **It is nowhere near the size this hardware can train.** Measured by training
   until it ran out of memory: **875 million parameters** fits on one shared
   card. Nobody had ever checked.
6. **It builds its own vocabulary** instead of borrowing one: a byte-level
   vocabulary learned from the project's corpus cuts the same text into about
   **40% as many pieces** as one per character (0.39 tokens per character).
7. **It has a faster generation path that ships off, because it was measured
   first.** Cached decoding is exact, and at this model size it was not faster,
   so it is **off by default**.
8. **We tested our own architectural belief and it was wrong.** A "modern" design
   led by about a quarter early and lost at **every one of three seeds** when run
   four times longer.

**And none of it is a win yet.** The gap is problem-solving, not formality.

## Why this setup is unusual

- **Seven proof systems, not one.** Each gets its own translation of every
  program, and a training example survives only if **all seven** verify it.
  Projects that verify their training data usually use one prover.
- **Every program ships with a sabotaged twin.** [`t/twins/`](t/twins/) is 426
  pairs: 213 verified programs answering 90 problems, each paired with a
  near-miss, the concrete input where the two disagree, and seven independent
  refutations. That is what stops a prover waving through something it never
  really checked. We have not found another published set of that shape.
- **Predictions are written down before runs, including the wrong ones.** Several
  of this project's own beliefs died that way and the files that killed them are
  in the repo.
- **It corrects itself in public.** [`CORRECTIONS.md`](CORRECTIONS.md) is the
  record, and it is not decorative: it holds a case where this README described a
  safety rule that held only for a command-line script, while the window a person
  actually opens did not use it.
- **The design is researched, and then challenged.** Every colour, size and
  default in [`locallm/DESIGN-BRIEF.md`](locallm/DESIGN-BRIEF.md) carries a
  fetched source and an evidence grade. A second pass re-fetched every one of
  those sources hunting for claims the document could not support, and found
  eleven, including one in its own strongest citation.

## Start here

| I want to | Go to |
|---|---|
| run it | [`locallm/START-HERE.md`](locallm/START-HERE.md) |
| see every result with its settings and hashes | [`locallm/ACHIEVEMENTS.md`](locallm/ACHIEVEMENTS.md) |
| know what is *not* claimed | [`LIMITS.md`](LIMITS.md) |
| understand the model builder | [`locallm/README.md`](locallm/README.md) |
| understand the specification language and its seven kernels | [`t/README.md`](t/README.md) |
| see the full scoreboard against Phi and every baseline | [`SCOREBOARD.md`](SCOREBOARD.md) |
| see what was tried and ruled out | [`SCOREBOARD.md`](SCOREBOARD.md#what-has-been-ruled-out-and-what-it-cost-to-find-out) |
| read why the window looks the way it does | [`locallm/DESIGN-BRIEF.md`](locallm/DESIGN-BRIEF.md) |
| read the problem corpora | [`nl/README.md`](nl/README.md) |
| read the day-by-day record, failures included | [`internal/ROADMAP-LOG.md`](internal/ROADMAP-LOG.md) |
| know what comes next | [`ROADMAP.md`](ROADMAP.md) |

## The pipeline

```
problems in English, with tests (nl/; pool v6 is 4,035, 232 held out and never trained on)
  -> a generator model writes a specified program for each          spec_experiment.py generate
  -> keep only programs that pass their tests and copy nothing seen  spec_experiment.py tests, pool_pick.py
  -> prove each in Dafny, Verus, SPARK, Frama-C, Lean 4, Rocq, F*    run_par.py
     and require all seven to refute a deliberately broken twin
  -> check each accepted specification against the problem's own solution   spec_check.py
  -> the clean pool                                                  loop_dataset.py
  -> build a model from it: locallm from scratch, or a 1.5B student  loop_locallm.py, loop_train.py
  -> score every model on the 232 held-out problems                  score_heldout.py
```

An answer all seven prove but whose tests fail is counted separately as **proven
but wrong**. A clean answer whose program, names erased, is a document of the
model's own training corpus is counted separately as **recited**
(`score_heldout.py --corpus`). The 232 held-out problems have never changed, so
every number in this repository is comparable to every earlier one.

## What is in the repository

| Path | What it is |
|---|---|
| [`locallm/`](locallm/) | the model builder and the window: a transformer trained from random weights on your own hardware |
| [`t/`](t/) | the filter: a small specification language translated into seven proof systems, and every pipeline script |
| [`t/twins/`](t/twins/) | 426 pairs: a verified program, a near-miss, and the input that separates them |
| [`nl/`](nl/) | natural-language programming problems with tests, from four public sources |
| [`tup/`](tup/) | a Linux distribution built from source with a receipt per step |
| [`internal/`](internal/) | handoffs, the machine plan, the dated engineering log that is the roadmap of record |

## The window follows your system

Light by default, dark when your desktop is set dark, on all three platforms.
Which way round that should be was not a taste decision: two of the three
platform owners publish a default and both of them say light.

## License

Research use only: the whole repository may be used, copied, modified and
redistributed for research and education, and for nothing else without written
permission ([`LICENSE`](LICENSE)). Third-party material keeps its own licenses;
the problem corpora under `nl/` list theirs. `locallm/` was MIT until 2026-09-15.

Copyright (c) 2026 Treston Malachi Cuzzort.
