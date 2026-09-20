# locallm

**A local learning model: a small model that learns whatever your machine writes —
trained from scratch, on your own hardware, from your own data.**

No pretrained weights. No API. No account. Nothing leaves your computer.

The name is not short for "local language model." It is a **local learning model**:
point it at the text-shaped data your life actually produces — notes, code, machine
logs, query dumps, sensor exports — and it learns the structure of *that*, where the
data lives. It is built like a language model because a transformer is
the simplest honest machine for the job, but conversation is not the product. Learning
your data, measurably and verifiably, is.

You can optionally **download plain text to train on** (`get_corpus.py`), never weights.
The model is always built from random numbers on your machine; what you download is
something to read, not something that already knows how to write.

The model starts as random numbers. By default, the vocabulary contains the characters
in the data you give it. The core training presets can instead learn a byte-level BPE
tokenizer from the training text. You watch it learn.

```
python studio.py
```

**What it has done so far:** a 92M model trained this way drew level with
Microsoft's Phi-4-mini, 41 times larger, on 232 held-out program-synthesis
problems where every answer had to be proved by seven independent proof
systems. The eight results with their settings and hashes are in
[`ACHIEVEMENTS.md`](ACHIEVEMENTS.md); the scoreboard is
[`../SCOREBOARD.md`](../SCOREBOARD.md) and what is not claimed is
[`../LIMITS.md`](../LIMITS.md). That is one application of this trainer, not
what it is for; the rest of this page is the tool.

## Core training presets

The CLI now supports rotary positions, RMSNorm, SwiGLU, activation checkpointing, and
approximately 30M, 91M, and 312M parameter presets at an 8192-token vocabulary. Each size
completed real optimizer steps on the lab GPUs at context 2048. This establishes that
the larger owned models run; better learned answers remain to be measured.

```sh
python train.py --data corpus.txt --out out/core-medium \
  --preset core-medium --tokenizer bpe --vocab-size 8192 \
  --batch-size 1 --steps 2000 --lr 0.0003
```

Install `requirements-training.txt` for BPE. Existing character checkpoints and commands
remain supported. In the matched probe, the modern core was slower (11.16 versus
5.87 ms/step); checkpointing reduced its peak allocated memory about 51% while costing
more computation. Read [the measured core report](CORE-2026-09-19.md) for exact shapes,
raw observations, reproducible checks, and the limits of those numbers. The GUI keeps
its existing simple presets; these new scale presets are exposed through the CLI.

> ## 🚧 Work in progress
>
> **This is an early, actively developed project, not a finished product.** It trains real
> models today and the results below are real, but interfaces will change, features are
> missing, and the limits section further down is not modesty. It is accurate.
>
> **Setup is one script.** Run `INSTALL.bat` (Windows) and it builds a private Python
> environment beside these files, installs the PyTorch build that matches your graphics
> card, and puts a shortcut on your Desktop. The one-click bootstrapper built for the
> old standalone repository is archived at `releases-archive/v0.1.0/Install_locallm.exe`.
>
> **One requirement is not gone yet: you still need Python installed** (3.10 or newer,
> and not the very newest, see below). The installer checks, and tells you exactly what
> to get if it is missing. Bundling the Python runtime so that step disappears too is
> still the goal. See [Roadmap](#roadmap).

---

## One project, two scales

This folder lives inside **srlm-forge**, and that is not packaging — it is the point.
They were always one project; the split into two repositories was an accident of
history, now repaired.

The repository root asks: *when a model is trained and a benchmark says it improved,
how much of that number is real?* It asks at 8-billion-parameter scale, with an
execution-verified training pipeline, and the answer became a paper ("Automated
Oracles Are Not Enough") whose main finding is that the measuring instrument, not the
model, produced roughly half the gain.

This folder is the same question at a scale you can hold in your hand. Every defense
the research arm had to invent — preregistered bars, leakage gates, noise floors,
machine-checked claims, an append-only run ledger — exists here too, wrapped around a
model small enough that a full training run costs under a minute and every claim can be
re-derived on a laptop. The forge is where the method is stress-tested against a real
benchmark. locallm is where anyone can run the method themselves.

## What this actually is

A small, readable, from-scratch GPT and a GUI so you don't need a terminal to use it.

| File | What it is |
|---|---|
| `model.py` | The transformer. Decoder-only GPT, written out in full: attention, MLP, blocks, weight tying, GPT-2 scaled init. ~145 lines. |
| `data.py` | A character-level tokenizer built from *your* corpus, plus batching. No external tokenizer, nothing downloaded. |
| `train.py` | The training loop. Random init → your weights. Cosine schedule, warmup, gradient clipping, bf16 autocast where it is measured to help (CUDA and Apple-silicon GPUs). |
| `generate.py` | Sample from a model you trained. |
| `checkpoint.py` | Loads a saved model back off disk and samples from it. One implementation, shared by `generate.py` and the GUI so they cannot drift apart. |
| `make_corpus.py` | Point it at a folder; it builds `corpus.txt` from your files. Accepts any file whose **content** is text, refuses binaries by their bytes, and warns when your vocabulary gets expensive. |
| `get_corpus.py` | Downloads text worth training a small model on: simple stories, or public-domain books. Text only; weights are never downloaded. The one file here that opens a network connection. |
| `studio.py` | The GUI. Pick a size and a practice length from presets, train, watch how many characters it is still choosing between, and write something with it. Advanced settings hold every original knob. |
| `leakage.py` | Finds training text hiding in your validation set, and says so. |
| `baselines.py` | Scores a lookup table on the same held-out text as your model, so "it learned" is a comparison, not a feeling. |
| `bench_device.py` | Times a real training step on your hardware — CPU, CUDA, or Apple-silicon — and tells you what it can handle. |
| `install.py` | Sets the app up on your computer: builds a private Python environment beside these files, installs the PyTorch build that matches your graphics card, and puts a shortcut on your Desktop. Run it through `INSTALL.bat`. It uses only the standard library, so it works on a computer where nothing is installed yet, and it asks PyTorch which Python versions it supports rather than guessing. |
| `check_my_computer.py` | Run this first. Checks Python, Tk, memory, disk and graphics card, times a real training step, and says in plain words what you can train and how long it takes. Writes the file the studio reads to show real minutes instead of "not timed yet". |
| `test_detectors.py` | Tests for the leakage detector. `python test_detectors.py`, no framework. |
| `runlog.py` | Append only record of every run. `python runlog.py` to see them all. |
| `start_studio.py` | Double click entry point: rebuilds the corpus from your files, opens the studio. |
| `exp_lr_width.py` | A preregistered experiment harness (see below). |
| `verify_claims.py` | Checks this README's factual claims against the repo. `python verify_claims.py`, exits non-zero if any has drifted. |

Dependencies: **PyTorch and Tk.** That's it. Tk ships with Python.

## Install

**Windows.** Run `INSTALL.bat` in this folder. It builds a private environment, picks
the right PyTorch for your machine, checks the result, and adds a Desktop shortcut
called **Train My AI**. It needs no administrator rights and writes nothing outside
this folder and the shortcut. (The one-click bootstrapper from the standalone-repo era
is preserved at `releases-archive/v0.1.0/Install_locallm.exe`; it downloaded from a
release that no longer exists, so use `INSTALL.bat` directly now.)

**Mac and Linux.** `pip install torch`, then `python studio.py`. Apple-silicon Macs
train on the GPU automatically — no CUDA, no configuration; the device is picked in
one place (`train.pick_device`) and the studio, the CLI, and the benchmark all use it.

**What "picks the right PyTorch" means.** The installer asks `nvidia-smi` whether you
have an NVIDIA card and installs the CUDA build if you do and the processor-only build
if you don't. Both train; the CPU one is slower (there is a measured table in
[Roadmap](#roadmap)).

**About your Python version.** PyTorch does not publish a build for the newest Python
for some months after it comes out, so the newest Python is usually the one version
that cannot work. The installer does not guess at this: it looks at every Python on
your computer, asks PyTorch's own package index which of them it supports, and uses
the newest that works. If none do, it says so and tells you what to install rather
than failing part-way through with a wall of red text.

Undoing all of it is deleting the folder and the shortcut.

## Quick start

Put **any text files you have** in `training_data/`: `.txt`, `.md`, `.py`, but also
`.csv`, `.jsonl`, `.log`, `.tsv`, `.yaml`, `.sql`, or files with no extension at all,
then run `python start_studio.py`. It rebuilds the corpus and opens the studio.

Files are accepted on **content, not extension**: anything whose bytes are text gets
in, anything binary is refused and says so. That is deliberate, and it is the local
learning model idea in one rule: the point is to learn the data you actually have, not
the three file types this project happened to guess. Machine logs, sensor exports and
query dumps are all just structure to a character-level model — a model trained on
your logs learns your logs' grammar, and that has nothing to do with chat.

A worked example of exactly that: a corpus of 1,947 Dafny files (a formal verification
language — dense, non-prose, structure everywhere) trains the default model to
recognizable Dafny in under a minute on an Apple-silicon GPU, and the leakage scanner
correctly flags that boilerplate test headers straddle the train/validation split
rather than letting the val loss pass unqualified. The tooling telling you *that* is
the product working as designed.

On Windows, double click `Train My AI.bat` instead, or make a desktop shortcut to it, and
you never need a terminal at all.

**Run `Check My Computer` first.** It takes about a minute, checks that everything it
needs is installed, times a real training step on your hardware, and tells you what you
can train and how long it will take, measured here, not copied from someone else's
machine. Until you do, the studio will not guess at times; it will say so.

Have no text of your own, or want output that actually reads like English?
`python get_corpus.py stories` downloads simple short stories written for exactly this
size of model. On a 3M-parameter model that is the difference between word salad and
*"Once upon a time, there was a little boy named Timmy."*

The longer form, if you want the pieces separately:

```bash
pip install torch                       # CUDA build if you have an NVIDIA GPU
python make_corpus.py --src ./my_notes  # or --src . --ext .py to train on code
python studio.py                        # or: python train.py --data corpus.txt
```

Then in the GUI: pick a **size** → pick how long it should **practise** → **Start training**
→ **Write something**. Four choices, all of them presets or sliders; there is nothing to type
except the words you want the model to continue. Every original knob is still there under
**Show advanced settings**, which is shut by default.

Checkpoints are plain `ckpt.pt` + `tokenizer.json` in your output folder. They're yours.
`generate.py --out <folder>` reads them back.

## What makes it different

Most small-model repos show you a loss curve going down and let you feel good about it.
This one is built to stop you fooling yourself — because its sibling project spent
months learning, at 8B scale, exactly how measurement lies:

- **It refuses to hand you a fake number.** Before training, it checks whether your
  validation text also appears in your training text. If it does, val loss is measuring
  memorisation rather than generalisation, and the tool tells you so instead of letting
  you believe the number. Splitting is by whole document, after de-duplication, so
  repeated material cannot land on both sides.
- **The learning rate follows your architecture.** A fixed `3e-4` is a GPT-2-scale constant
  (width 768 to 1600) and is badly wrong at the widths this trains. `auto_lr(n_embd)` scales
  with width, and the GUI retargets it when you change the model but never overwrites a
  value you typed yourself.
- **Experiments are preregistered.** `prereg_lr_width.json` fixes the success bar, the arm
  selection rule, and the interpretation of a null result *before* the run. `exp_lr_width.py`
  then reports PASS or FAIL against it. Writing the bar first is the whole point.
- **Evaluation can't disturb training.** Eval batches come from a dedicated
  `torch.Generator`, never the global RNG, so every arm sees byte-identical batches.
- **Multiple seeds, and ranges reported.** One run is an anecdote.
- **Looking at the model cannot change it.** Evaluation draws its batches from a
  dedicated generator, so how often you evaluate has no effect on what gets trained.
  That sounds obvious and was not true here until it was measured: sharing one random
  stream between training and evaluation moved final train loss by 0.031 purely by
  changing the eval interval. It is now identical to six decimal places regardless.
- **Every run is recorded.** `runs.jsonl` gets one append only line per training run,
  experiment, benchmark and leakage scan: configuration, device, wall clock, final
  losses, a fingerprint of the corpus, and the leakage verdict sitting next to the
  val loss it qualifies. `python runlog.py` prints the history, `--review` prints a
  digest for someone who did not watch it happen. A result file that the next run
  overwrites cannot show you a trend.
- **This README is machine-checked.** `python verify_claims.py` re-derives every
  factual claim below from the repo itself and exits non-zero if one has drifted: that
  the listed files exist, that `model.py` really is ~145 lines, that the dependency
  claim holds (against the interpreter's own stdlib list, not a hand-written one), that
  nothing imports a network module, and that **every number in the worked result below
  matches `exp_lr_width_result.json` to the digit**: means, ranges, gap, overlap and
  verdict. Its limits are stated in its own docstring: it cannot check the roadmap, it
  cannot check hardware timings on your machine, and it is a fixed list of checks rather
  than a general fact-checker, so a newly added sentence is not caught automatically.
- **The detector is itself tested, against a copy of its own old bug.**
  `test_detectors.py` keeps the previous, broken fingerprinter in the file on purpose and
  runs every test against both: the current one must pass and the broken one must fail. A
  test that both pass is not testing anything. Test inputs are drawn randomly rather than
  hand picked, because the original bug was a stride of 10 and every offset a person
  reaches for by hand (0, 100, 500, 1000) is a multiple of 10 and passes on the broken
  code.

### A worked result

The first experiment run through this harness, on an RTX 4080 (4 layers, 4 heads, width 256,
block 128, batch 32, 2000 steps):

```
control   lr 3.0e-04   mean 0.1495   range [0.1471, 0.1507]
treatment lr 3.0e-03   mean 0.1056   range [0.1016, 0.1099]
gap +0.0439   bar 0.020   ranges overlap: no
PREREGISTERED VERDICT: PASS
```

Five seeds per arm, bar written down first. The hardcoded default was leaving **0.04 train
loss** on the table, more than any architecture change was worth. That is why the learning
rate scales with width now.

Reproduce it: `python exp_lr_width.py` (about 2.5 minutes on a 4080, running 4 arms
concurrently; pass `--workers 1` to run them one at a time).

There is also a one minute profile, `python exp_lr_width.py --profile fast` (measured 59s),
at 800 steps with a 4 point sweep. It is deliberately **a separate experiment, not a cheaper
version of this one**, because the effect size changes with step count: measured across
400/800/1200/2000 steps the gap decays about 9x, so a shorter run reports a *larger* number
for the same underlying phenomenon. The fast profile licenses the claim "reaches lower train
loss faster" and nothing more. To stop the two being confused later, the profile, step count,
grid size and claim are written into the result file's own verdict string rather than kept in
a filename or someone's memory:

```
PASS [fast profile: 800 steps, 4-LR grid, 5 seeds] - claim: reaches lower train loss
FASTER; NOT the canonical effect size
```

These numbers moved once since first publication, and the reason is worth stating: the
document splitter's `seed` argument was silently unused, so fixing it changed which
documents land in training. The verdict did not change, the margin did.

## Honest limits

Read this part before you expect too much.

- **A small model trained on one person's data produces mediocre output.** This is not
  ChatGPT and it is not close. That is compute and data scale, not a bug to engineer
  around. What it learns is the *structure* of your data; what it cannot do is converse.
- **The character tokenizer is still the default in `train.py`**, and it is less
  efficient per token than BPE. A BPE tokenizer trained on your own corpus is
  available with `--tokenizer bpe` and is the default in `train_distributed.py`;
  measured on this project's corpus it cuts the same text into about 60% as many
  chunks. Whichever you pick is fingerprinted into the checkpoint, so a resume
  cannot silently change it.
- **A tiny corpus, or one dominated by a single huge document, cannot be split cleanly.**
  Whole-document splitting cannot hit a 10% target when there are only three documents.
  The scanner reports the validation fraction it actually achieved and warns you when the
  document sizes, not your setting, are in charge.
- **The leakage scan is an exact substring scanner, not a near duplicate scanner,**
  and the difference is bigger than it sounds. Measured recall on this project's own
  documents: verbatim copies 100%, reformatted 90%, every identifier renamed **0%**,
  renamed plus edited **0%**. Renaming identifiers costs it almost nothing; replacing
  the string literals is what destroys detection. So a CLEAN verdict means nobody
  copied and pasted. It does not mean your validation set is independent. The tool
  says this in its own output rather than leaving you to find out.
- No gradient accumulation. Resume and multi-GPU now exist:
  `train_distributed.py` runs one process per GPU under torchrun with exact
  step-boundary resume, and a checkpoint carries the optimizer, the
  learning-rate horizon, the tokenizer identity and every rank's RNG state, so
  changing any of those on resume is refused rather than absorbed.
- Large architectures will run out of VRAM rather than warning you first.
- **You currently need Python and a terminal to install and start it.** The GUI itself
  needs neither once it is running, but getting there does. That is the single biggest
  barrier to "anyone can use this", and it is item 1 on the roadmap.

## Roadmap

In order. The training core gets sharpened before anything expands.

**1. Setup with no terminal and no Python. PARTLY DONE.**
`install.py`/`INSTALL.bat` handle the environment, the right PyTorch build, and the
Desktop shortcut today, with no administrator rights. The remaining piece is the Python
runtime itself: bundling it so the requirement disappears. Bundling a runtime is easy,
but PyTorch with CUDA is roughly 2.5 GB, which no amount of packaging polish makes
friendly. The plan: a CPU-capable default with the GPU build as an opt-in, and the
runtime bundled so the user never sees it.

The version trap the installer already solves is worth naming, because it is the one
that bites hardest: PyTorch publishes no wheels for the newest Python for some months
after release, so a user who installs Python today gets the one version that cannot
work, and the failure is an unreadable resolver error. The installer asks the package
index which versions are supported instead of carrying a hardcoded list that would go
stale.

That plan rests on CPU training being tolerable, which is a measurable claim, so it was
measured rather than assumed. Run `python bench_device.py` to get the same table for your
own machine. On an RTX 4080 with a Ryzen 7000 series CPU, for a full 2000 step run:

| size | params | CPU | GPU | GPU speedup |
|---|---|---|---|---|
| small (2L, 128 wide) | 0.41M | 63s | 8s | 7.5x |
| default (4L, 256 wide) | 3.18M | 5.4 min | 14s | 23.8x |
| large (6L, 512 wide) | 18.96M | 56.9 min | 40s | 84.9x |

And on an Apple M5 Pro (unified memory, MPS backend), same protocol:

| size | params | CPU | GPU (MPS) | GPU speedup |
|---|---|---|---|---|
| small (2L, 128 wide) | 0.41M | 38s | 11s | 3.4x |
| default (4L, 256 wide) | 3.19M | 3.8 min | 42s | 5.4x |
| large (6L, 512 wide) | 18.98M | 28.6 min | 5.2 min | 5.5x |

So a CPU only install is genuinely fine at the small size, usable at the default, and
impractical above it — and an ordinary Apple-silicon laptop with no NVIDIA card at all
trains every size this ships. That is the shape the installer should follow: detect the
hardware, pick a size the machine can actually finish, and say which it chose.

**2. Leakage scan and group aware splitting. DONE.**
Shipped in `leakage.py`, and wired into the GUI and the training loop. Measured on this
project's own corpus: the old positional split put 82.6% of validation content inside
training. Splitting by document drops that to 1.5%. The effect on the numbers is the
point: under the contaminated split, val loss came out *lower* than train loss, which is
backwards. With a clean split there is an honest gap.

Those two figures were first published as 70.1% and 0.0%, measured with a detector that
was itself broken. It sampled fingerprints at a fixed stride, so it only compared two
copies of a passage when both happened to start on the same stride phase: a document
copied verbatim into training was caught at 1 byte offset out of 10. Fingerprints are now
selected by content (winnowing), which is phase invariant, catches that case at 10 offsets
out of 10, and is cheaper than the sampler it replaced.

**3. Noise floor by default.**
Multiple seeds on every comparison, mean plus or minus 3 sigma, with test retest variance
reported separately from between configuration variance, so the tool can say "that
improvement is inside noise, it isn't real" instead of letting you believe it.

**4. Training that resumes and keeps going.**
Resume from a checkpoint and train for as long as you want, rather than a fixed step count.

**5. Learning that is verified, not just scored.**
The research arm of this repository (the root) trains against executed tests and studies
what verified feedback is actually worth; its newest tooling generates verified pairs
from Dafny, a language whose compiler proves code correct. As that machinery matures,
the goal is for what it learns about honest verification to flow back into what this
trainer reports about your model. One method, two scales — see
[One project, two scales](#one-project-two-scales).

Further out: an assistant layer that can reason and act on your machine. That is a separate
track, built against whatever local model is strongest, because a small from-scratch model
cannot do that job and pretending otherwise would be dishonest. If a model trained here
ever becomes good enough, it earns its way in on measured results.

## Why a program like this is useful

### Immunity to "Enshittification" and API Decay

Every hosted AI service follows the same arc. It launches good and cheap, because it is
buying users. Then the free tier shrinks. Then the model behind the endpoint is quietly
swapped for a smaller one, and the thing you built and tuned against changes underneath
you without a version bump. Then the API you depend on is deprecated, rate limited,
moved behind a higher tier, or switched off. Your work was never yours. It was rented,
and the landlord kept the keys.

A model you trained yourself cannot be degraded by someone else's quarterly targets.
The weights are a file on your disk. The tokenizer is a file on your disk. The training
code is a few hundred readable lines you can open right now. Nothing phones home,
nothing needs an account, nothing expires, and no terms of service update can reach
backwards and take it away. Run it in ten years on a disconnected laptop and it behaves
exactly as it does today, because every part of it is already in your hands.

That is the whole point. Not that a small model trained on your own data will beat a
frontier model. It will not, and this README says so plainly above. The point is
that it is *yours*, permanently, and that you can see and change every part of how it
works.

### The goal

Make training your own model something an ordinary person can actually do — and make
the numbers it reports mean something.

Not "download someone else's weights and run them locally", which is already a solved
problem with good tools. This is the other thing: start from random numbers, learn from
data you chose, on hardware you own, and watch it happen — with tooling that tells you
when a result is real and when it is an artifact of how it was measured. Understanding
how the thing works should not require a research group, a cloud account, or a credit
card.

The direction of travel is a single installer, no terminal, no Python, no configuration
files. Point it at a folder of your own data and press train. See the
[Roadmap](#roadmap) for where that stands.

### Free for everyone

There is no account, no telemetry, no usage limit, no paid version holding the good
features, and nothing about it that stops working if this project goes quiet. ("Free"
here is about those things, not about the licence: see License below.) It runs on hardware
people already have, including without a GPU.

## Why from scratch

Because "download someone's weights and run them locally" is a solved problem with good
tools already. This is the other thing: a model that has read **only** what you gave it,
that started as random numbers on your machine, and whose every line you can read.

It is small. It is yours. It is honest about what it is.

## License

Research use only, see [LICENSE](LICENSE) and the repository root [LICENSE](../LICENSE). locallm was MIT until 2026-09-15; a copy obtained under MIT before then keeps it. Copyright (c) 2026 Treston Malachi Cuzzort.

This section said "use it, change it, ship it, sell it" until 2026-09-20, two
sentences after saying research use only. That line was true under MIT and was
left behind when the licence changed on 2026-09-15. Research and education are
covered; anything else needs written permission, which is what the root
[`LICENSE`](../LICENSE) says.
