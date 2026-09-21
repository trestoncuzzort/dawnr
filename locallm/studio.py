"""studio.py — build and train your OWN AI from scratch, with no jargon.

    python studio.py          (or double-click "Train My AI.bat")

No pretrained weights, no API, no downloads. The architecture comes from model.py,
the tokenizer is built from YOUR text by data.py, and the training loop is
train.py's. This file is the control surface and it does not reimplement any of
the math.

WHO THIS IS FOR. Someone who has never heard of a transformer and should not have
to. Everything on the main screen is a button, a preset or a slider; there is
nothing to type and no setting whose name you must already understand. The
previous version asked for `layers`, `heads`, `embed dim`, `block_size`,
`dropout`, `learn rate`, `eval every`, `seed` and `top-k` as free text, which is
nine things you cannot fill in without already knowing the answer.

The old controls are all still here, under "Show advanced settings". Nothing was
removed - it was moved behind a door, and the door is shut by default.

THE GRAPH SHOWS SOMETHING A PERSON CAN READ. It used to plot raw cross-entropy
loss, where 2.774 means nothing to anyone who has not taken the course. It now
plots exp(loss), which is the number of characters the model is effectively still
choosing between for each next character - a quantity with units you can say out
loud. It starts at the size of your alphabet (pure guessing) and falls as the
model learns. Same numbers, same math, translated once.

EVERY VISUAL DECISION IS look.py's. The palette, the spacing scale, the two font
lists and the wording of every judgement this page makes used to live here as
well as in t/lab.py, which hosts this page as its Train tab; the two copies
drifted, and a rule saying "keep these lists identical" has no enforcement. One
list has enforcement for free, and look.py is that list.

NOTHING HERE READS ANYONE'S FILE. Every byte of a user's own text arrives through
ingest.py, which either decodes a file properly and names the encoding that
worked, or refuses and says why in a sentence a person can act on. This file used
to call read_text(encoding="utf-8", errors="ignore") in two places - once for the
on-screen preview, and once inside TrainWorker, which is the path that actually
trains - and 'ignore' is documented as "Ignore the malformed data and continue
without further notice" (docs.python.org/3/library/codecs.html#error-handlers).
"Without further notice" is the whole defect: a cp1252 or UTF-16 file lost
characters with no sign on screen, and in a character-level tokenizer the
survivors become permanent vocabulary entries of a model nobody can tell is
wrong. A file that does not decode is now refused instead of trained on.

Dependencies: torch + tkinter (stdlib), locallm/look.py and locallm/ingest.py.
Nothing else.
"""
from __future__ import annotations

import json
import math
import queue
import re
import sys
import threading
import time
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import torch  # noqa: E402

import baselines  # noqa: E402
import checkpoint  # noqa: E402
import ingest  # noqa: E402  (the ONLY way this file reads a user's text)
import look  # noqa: E402
import runlog  # noqa: E402

# The four names that were defined in this file and now live in look.py, imported
# bare so the call sites below read exactly as they did. Everything look.py adds
# (PALETTES, SPACE, say_corpus, say_progress) is reached through `look.` instead,
# so a reader can tell at a glance which decisions moved out and which are new.
from look import MONO, SANS, resolve_fonts, system_wants_dark  # noqa: E402
from look import fit_to_screen  # noqa: E402  (moved there; re-exported so main() and older callers keep working)
from model import GPT, GPTConfig  # noqa: E402
from data import (CharTokenizer, Corpus, documents, group_split,  # noqa: E402
                  split_health, split_verdict, tokenizer_fingerprint)
from leakage import scan as leakage_scan  # noqa: E402
from train import (auto_lr, cosine_lr, enable_fast_math,  # noqa: E402
                   estimate_loss, make_optimizer, pick_device, wants_bf16)

BENCH = HERE / "bench_device_result.json"

# How much of the corpus the ON-SCREEN preview inspects.
#
# leakage.scan costs about 0.9 seconds per megabyte, so the full check on a
# 200 MB corpus does not finish in any time a person will sit through - opening
# the studio simply hung. The preview is a SAMPLE and is labelled as one on
# screen. The real check still runs over the real split inside TrainWorker,
# where it belongs and where waiting is acceptable, so nothing is weakened: what
# changed is that the UI no longer blocks on it before you have pressed
# anything.
SCAN_SAMPLE_BYTES = 2_000_000

# --------------------------------------------------------------------------
# COLOURS AND SPACING ARE look.py's.
#
# Both palettes used to be a THEMES dict of literals here. They were measured
# against WCAG in one place and this half of the window kept its own copy, so the
# page and the shell hosting it disagreed about what grey meant. look.PALETTES
# carries the same alias names THEMES had - bg, panel, field, fg, muted, faint,
# ok, warn, bad, plot_*, learn, unseen, guess, log_* - so not one widget below
# needed a different key, and look's own tests now guard every contrast pair.
# --------------------------------------------------------------------------

# look's tuple, named locally only so a grid call still fits on one line.
#
# EVERY padx AND pady BELOW MOVED ONTO IT. They were eleven hand-nudged values -
# 1, 2, 4, 6, 8, 9, 10, 12, 14, 30, 36 - for six jobs, which is how the advanced
# rows end up 1 px apart, and one card's contents 10 px from its left edge and 9
# from its bottom, differences nobody chose. Each side was rounded to the nearest
# step of look.SCALE, a tie going to the larger step; no side moved by more than
# 4 px, and 0 stays 0, because "no gap on this edge" is a decision rather than a
# nudged number.
SPACE = look.SPACE

# A description that hangs under its radio button clears the indicator instead of
# starting under it. It was 30 px in the size card and 36 in the download dialog,
# two numbers for one job; both are `page` on the scale, named here because "page
# margin" is not what it means at either call site.
INDENT = SPACE.page

# A Say's tone is a ROLE name - proved, refuted, unsettled, muted - while every
# coloured widget in this file names the ALIAS for the same role: ok, bad, warn.
# The two are the same colour in look.PALETTES, so this table is not a translation
# between colours; it is what lets a host hand over a PARTIAL palette. t/lab.py
# hands over look's whole one today, role keys included, and then the table is a
# no-op - but the `palette` argument is a dict, not look.PALETTES, and a host that
# names only the aliases (which is what t/lab.py's TRAIN_PALETTE was before it
# became dict(C)) would otherwise have its green overridden on the one line that
# went through a role key. `.get(tone, tone)` is the other half: `muted` is a tone
# with no alias, and it is a palette key already.
TONE_KEY = {"proved": "ok", "refuted": "bad", "unsettled": "warn"}


# --------------------------------------------------------------------------
# THE PRESETS.
#
# These three sizes are not invented for the UI - they are the exact three that
# bench_device.py measures, so the times shown next to them are MEASURED on this
# machine rather than guessed. If the benchmark file is missing the times are
# hidden instead of estimated, because a made-up number in a "how long will this
# take" field is worse than no number.
# --------------------------------------------------------------------------
SIZES = {
    "Small": dict(
        key="small", n_layer=2, n_head=4, n_embd=128, block_size=128,
        batch_size=32,
        blurb="Quickest. Good for a first try, or when you have only a little text."),
    "Medium": dict(
        key="default", n_layer=4, n_head=4, n_embd=256, block_size=128,
        batch_size=32,
        blurb="The usual choice. Noticeably better than Small on most text."),
    "Large": dict(
        key="large", n_layer=6, n_head=8, n_embd=512, block_size=256,
        batch_size=32,
        blurb="Slowest, and only worth it if you have a lot of text to feed it."),
}

# Wall-clock targets. Steps are derived from the measured speed of the chosen
# size, so "about five minutes" means about five minutes on THIS machine rather
# than a round number of steps that takes an unknown time.
LENGTHS = {
    "Quick look":  dict(seconds=60,   blurb="Enough to see it start working."),
    "Normal":      dict(seconds=300,  blurb="A sensible default."),
    "Thorough":    dict(seconds=900,  blurb="Better results, if you can wait."),
}

# What "Normal" means on a machine that has never been timed. The three lengths
# are then scaled from it in proportion to their wall-clock targets.
#
# This exists because the untimed path used to hand back a flat 2000 steps for
# ALL THREE lengths: picking "Thorough" over "Quick look" changed the label and
# nothing else, and the only hint was a note about not being able to estimate
# MINUTES - which is a different claim from "these three are identical". The
# proportions do not need a benchmark. Only turning them into minutes does.
UNTIMED_NORMAL_STEPS = 2000

# Slider stops for generation. The user moves one slider; temperature and top-k
# move together, because they are not two independent ideas to a person who just
# wants "more surprising".
STYLES = [
    ("Very predictable", 0.35, 10),
    ("Careful",          0.60, 25),
    ("Balanced",         0.80, 40),
    ("Adventurous",      1.05, 80),
    ("Wild",             1.20, 150),
]

# What each stop actually costs, so the slider is an informed choice rather than
# a taste knob. MEASURED on the 3.18M model trained on the stories corpus: 4
# samples of 700 characters per setting, counting words that do not appear
# anywhere in 20 MB of the training text.
#
#     temp 0.35  top_k  10    0.0% invented words
#     temp 0.60  top_k  25    0.2%
#     temp 0.80  top_k  40    0.9%
#     temp 1.05  top_k  80    0.9-1.6%
#     temp 1.20  top_k 150    2.1%
#     temp 1.30  top_k 200    6.6-7.8%   <- the old top stop
#
# Degradation is gradual up to 1.20 and then triples at 1.30, which is where
# "becauset", "wunny" and "snawhered" start appearing. The top stop was 1.30 and
# is now 1.20: still visibly loose, without falling off the cliff. The notes
# below are qualitative on purpose - the exact percentages belong to THIS model
# and THIS corpus, and would be a stale claim on anyone else's.
STYLE_NOTES = {
    "Very predictable": "repeats itself, but always real words",
    "Careful":          "safe and a bit dull",
    "Balanced":         "the usual choice",
    "Adventurous":      "livelier; an odd word here and there",
    "Wild":             "expect invented words and wandering sentences",
}


def param_count(vocab: int, block: int, n_layer: int, n_head: int,
                n_embd: int, bias: bool = True) -> int:
    """Analytic parameter count so the UI can update without building a model.

    Mirrors GPT.num_params(), which excludes the positional embedding table.
    """
    b = 1 if bias else 0
    per_block = (
        (3 * n_embd * n_embd + 3 * n_embd * b)      # attn.c_attn
        + (n_embd * n_embd + n_embd * b)            # attn.c_proj
        + (4 * n_embd * n_embd + 4 * n_embd * b)    # mlp.c_fc
        + (4 * n_embd * n_embd + n_embd * b)        # mlp.c_proj
        + 4 * n_embd                                # ln_1 + ln_2
    )
    total = (
        vocab * n_embd          # wte (tied to lm_head, counted once)
        + block * n_embd        # wpe
        + n_layer * per_block
        + 2 * n_embd            # ln_f
    )
    return total - block * n_embd


def load_speeds() -> dict:
    """Measured ms/step per (device, size), or {} if never benchmarked."""
    try:
        d = json.loads(BENCH.read_text(encoding="utf-8"))
        return {k: v["ms_per_step"] for k, v in d["results"].items()}
    except Exception:                              # noqa: BLE001
        return {}


def load_bench() -> dict:
    """The whole benchmark row per (device, size), or {} if never benchmarked.

    load_speeds() above is left exactly as it is, because home.py reads it and
    expects a bare ms/step per key. This reads the same file for the one other
    field the time estimate needs: `params`, which is the only record of how big
    an ALPHABET that timing was taken on.
    """
    try:
        d = json.loads(BENCH.read_text(encoding="utf-8"))
        return {k: dict(v) for k, v in d["results"].items()}
    except Exception:                              # noqa: BLE001
        return {}


def human_time(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f} seconds"
    if seconds < 5400:
        return f"{seconds / 60:.0f} minutes"
    return f"{seconds / 3600:.1f} hours"


# WHAT A STEP COSTS, AND WHY THE ALPHABET IS IN IT.
#
# bench_device_result.json is keyed by (device, size) and by nothing else, so the
# time beside each size was the same number whether your text used 29 different
# characters or 10,000. param_count above already takes `vocab` and is right: at
# the Small preset a model grows from 400,512 numbers on a 29-character alphabet
# to 1,676,800 on a 10,000-character one - 4.19 times, from the alphabet alone -
# while "About four minutes on this machine" did not move. Someone training on
# Chinese or Japanese was quietly under-promised, and the promise is not
# cosmetic: `steps` is DERIVED from ms/step to fill a wall-clock target, so an
# ms/step that is four times too small picks four times too many steps and the
# run overruns by that much.
#
# THE SCALING IS NOT THE PARAMETER RATIO. Kaplan et al., "Scaling Laws for Neural
# Language Models" (arxiv.org/abs/2001.08361), Table 1 splits a transformer's
# forward FLOPs per token by operation, and two of its rows settle this. The
# token Embed row costs 4*d_model per token REGARDLESS of n_vocab, because it is
# a row lookup - so the vocab*n_embd numbers in the table cost nothing per step -
# while the De-embed row, the tied output projection, does multiply by the whole
# table and costs 2*d_model*n_vocab. The alphabet therefore enters the CLOCK
# through the output projection only, and everything else in Table 1's
# non-embedding total, C_forward = 2N + 2*n_layer*n_ctx*d_attn with
# N = 2*d_model*n_layer*(2*d_attn + d_ff), is vocabulary-independent. Backward is
# about twice forward and divides out of a ratio, as does the batch.
#
# THE ARITHMETIC for this model's shape, where d_attn = d_model = n_embd,
# d_ff = 4*n_embd and n_ctx = block_size:
#     core       = 24*n_layer*n_embd**2 + 2*n_layer*block*n_embd
#     alphabet   = 2*n_embd per different character
# Small (n_layer 2, n_embd 128, block 128) is core = 786,432 + 65,536 = 851,968,
# and 256 per character. The shipped benchmark was taken at vocab 136 - recovered
# from the file by bench_vocab() below, exactly, on all six of its rows - so the
# alphabet is 34,816 / 886,784 = 3.9% of a step there, and scaling that 3.9% is
# the entire correction:
#     10,000 characters on Small    time x3.85   (parameters x4.05)
#     10,000 characters on Medium   time x1.76   (parameters x1.79)
#     10,000 characters on Large    time x1.26   (parameters x1.27)
#
# IT IS A FLOOR, NOT A PROMISE, and the label says so on screen. Table 1 states
# it omits "nonlinearities, biases, and layer normalization", and it counts
# arithmetic only: not the memory traffic of materialising a batch*block*n_vocab
# logits tensor, nor the softmax and cross-entropy over it. At batch 32, block
# 128 and vocab 10,000 that tensor is 41 million floats per step, which on a
# bandwidth-bound machine can cost more than the matmul. Both of those are also
# LINEAR in n_vocab, so the shape core + 2*n_embd*vocab is right and only the
# ratio between the two terms is understated - the derived factor can come out
# too small and cannot come out too large. NOT MEASURED HERE: this machine has no
# torch, so no step was timed at two alphabets to put a number on that gap.
def step_flops(vocab: int, block: int, n_layer: int, n_embd: int) -> int:
    """Forward-pass FLOPs for one token, by the rows of Table 1 named above.

    A cost in arbitrary units, only ever used as a ratio against itself at a
    different `vocab`, which is why the backward pass and the batch are missing:
    both multiply the two sides of that ratio equally.
    """
    n_non_embd = 2 * n_embd * n_layer * (2 * n_embd + 4 * n_embd)   # Table 1's N
    return (2 * n_non_embd                       # every weight, once per token
            + 2 * n_layer * block * n_embd       # Table 1's "Attention: Mask"
            + 2 * n_embd * vocab)                # Table 1's "De-embed"


def bench_vocab(row: dict, s: dict) -> int | None:
    """How many different characters `row` was timed on; None if it cannot say.

    Not a guess and not a constant. bench_device.py and check_my_computer.py both
    record `params` beside `ms_per_step`, and param_count is linear in vocab with
    slope n_embd, so the alphabet a timing was taken on is recovered exactly by
    subtracting the vocab-free part and dividing. It has to be recovered rather
    than assumed, because the two writers disagree: bench_device.py times against
    whatever corpus.txt happens to hold (136 different characters in the file
    that ships) and check_my_computer.py against its own pangram (32). None,
    rather than a fallback, when the division does not come out even - an assumed
    benchmark alphabet is precisely the confident wrong number this removes, and
    the caller has an honest sentence for None.
    """
    got = row.get("params")
    if not isinstance(got, int):
        return None
    floor = param_count(0, s["block_size"], s["n_layer"], s["n_head"], s["n_embd"])
    if got <= floor:
        return None
    v, remainder = divmod(got - floor, s["n_embd"])
    return v if remainder == 0 else None


# WHEN AN ALPHABET IS WORTH A WORD, measured as the share of the model that goes
# on naming characters rather than on how they follow each other. Kaplan et al.
# (above) fit loss against NON-embedding parameters - the embedding table buys no
# modelling capacity in their fit - so that share is the fraction of a model the
# user is paying for and not learning from, and it is exact: param_count knows
# both halves.
#
# INVENTED: the two cut points, a half and a tenth. Searched for a published rule
# for when a character vocabulary is too large for a given model width - arXiv,
# and the embedding-dimensionality literature (baeldung.com/cs/dimensionality-
# word-embeddings collects the usual ones) - and found rules for choosing a
# dimension from a vocabulary, none for judging a vocabulary against a dimension.
# A half is the point where more of the model names characters than does anything
# else with them; a tenth is where the sentence stops being worth the space,
# since below it the alphabet moves neither the size nor the clock by an amount
# anyone would notice. On the three presets a half falls at 3,101 characters
# (Small), 12,343 (Medium) and 36,945 (Large), so which band a text lands in
# depends on the size chosen, which is the point - a bigger size is one of the
# two things that help.
#
# The same tenth gates the time estimate's own sentence in _apply_preset, there
# measured on a step's cost rather than on the parameter count - the two are
# different quantities (a step pays for the output projection, not for the table)
# and each is judged in its own units, but one line is drawn once and used twice
# rather than two lines nobody can compare.
def say_alphabet(vocab: int, s: dict) -> look.Say | None:
    """What to say about an alphabet this size on this preset, or None.

    None means an ordinary alphabet: English, or any European or Cyrillic text,
    is a fraction of a percent of any of the three sizes, and a sentence about it
    there would be noise rather than judgement.
    """
    if vocab < 1:
        return None
    table = vocab * s["n_embd"]
    total = param_count(vocab, s["block_size"], s["n_layer"], s["n_head"],
                        s["n_embd"])
    share = table / total
    if share > 0.5:
        return look.Say(
            look.NOT_APPLICABLE, "Alphabet-bound",
            f"{share:.0%} of this model would go on naming your {vocab:,} "
            f"different characters rather than on how they follow each other. "
            f"A larger size spends less of itself that way, and more text helps "
            f"every character get seen often enough to learn.", "unsettled")
    if share > 0.1:
        return look.Say(
            look.NOT_APPLICABLE, "Big alphabet",
            f"{share:.0%} of this model goes on naming your {vocab:,} different "
            f"characters, and each practice step costs more because of them.",
            "muted")
    return None


def inspect_corpus(path) -> dict:
    """Read a corpus through ingest and measure everything the sidebar reports.

    PURE, AND MEANT TO RUN OFF THE TK THREAD: it touches no widget and no Studio,
    so the read, the decode and leakage.scan over the sample all happen on a
    worker and only numbers come back. `say` is a look.Say whichever way it goes,
    so a refused file and a clean one are rendered by the same three lines.

    A refusal carries ingest's own sentence and no measurements, because there is
    no text to measure - which is the point of the contract: read_any either
    decodes a file properly and names the encoding, or returns text=None. There
    is no third answer where a partly-decoded string reaches a tokenizer.
    """
    got = ingest.read_any(path)
    out = {"ok": got.text is not None, "say": got.say, "encoding": got.encoding,
           "kind": got.kind, "chars": 0, "vocab": 0, "docs": 0,
           "sampled": False, "report": None}
    if got.text is None:
        return out
    text = got.text
    out["chars"] = len(text)
    out["vocab"] = len(set(text))
    out["sampled"] = len(text) > SCAN_SAMPLE_BYTES
    sample = text[:SCAN_SAMPLE_BYTES] if out["sampled"] else text
    # MEASURING HERE, JUDGING IN look.say_corpus. Which sentence and which colour
    # go with which verdict was an if/elif ladder in _scan_corpus, over the three
    # leakage verdicts, the three split problems and the precedence between them;
    # TrainWorker decides the same thing from the same two reports, in its own
    # longer words, for the log. The measurements stay here. Calling say_corpus
    # with no verdict is what "the scan has not produced one" looks like, so the
    # except arm needs no second copy of that sentence either.
    rep = None
    say = look.say_corpus(None)
    try:
        tr_txt, va_txt = group_split(sample)
        rep = leakage_scan(tr_txt, va_txt, doc_aligned=True)  # group_split: it is
        health = split_health(sample)
        say = look.say_corpus(rep.verdict, rep.trustworthy,
                              split_verdict(health),
                              health["achievable_val_frac"])
    except Exception:                       # never let the scan block training
        # rep too, so the report below stays quiet about a scan that did not
        # finish. THIS ARM USED TO CLAIM A PASS: it fell back to the ok colour
        # and an empty note, so a check that crashed was indistinguishable from
        # one that passed. It reads "Not checked", in muted, instead.
        rep = None
    out["say"] = say
    out["docs"] = len(documents(sample))
    out["report"] = rep.report() if rep is not None else None
    return out


# HOW WIDE THE SETTINGS COLUMN IS, in characters of the body font rather than in
# pixels. It was a flat 340, a number read off this screen at 96 dpi, and a pixel
# count is exactly what does not survive a scaled display: claim_dpi_awareness
# plus apply_tk_scaling grow every font by the display factor (1.5 on a 150%
# laptop) while a literal stays put, which is the second failure fit_to_screen's
# docstring lists - the content grew and the container did not.
#
# Tk sizes its own text widgets this way. An entry's -width is "an integer value
# indicating the desired width of the entry window, in average-size characters of
# the widget's font" (tcl-lang.org/man/tcl8.6/TkCmd/entry.htm), and a canvas
# cannot say that - its -width is screen units - so the same rule is applied by
# hand: Font.measure returns what a string occupies "as an integer number of
# pixels" on the display it is asked about
# (docs.python.org/3/library/tkinter.font.html#tkinter.font.Font.measure).
#
# MEASURED 2026-09-20 on this box, Cantarell 10 on a 96 dpi screen: measure("0")
# is 8 px, and TkDefaultFont (Noto Sans 10), which is what most of the column
# actually draws in, is also 8. Forty characters plus the padding the cards in
# this column use on each side is 344 - the 340 it replaces, within half a
# character.
#
# 340 TIMES THE SCALE FACTOR WOULD HAVE BEEN WRONG, which is why the font is
# asked instead. fit_to_screen scales its preferred window size by
# winfo_fpixels("1i") / 72 and is right to, but that factor is not what moves a
# font on every platform: measured here with `tk scaling` forced to 1.0, 1.33 and
# 2.0, a POSITIVE (point) size measured 8 px at all three, because Tk hands Xft a
# point size and fontconfig sizes it from the X server's dpi. On Windows the same
# point size does go through `tk scaling`. So the scale factor predicts the font
# on one platform and not the other, while measure() reports what the font
# actually did on both.
SIDEBAR_CHARS = 40


def sidebar_width(w: tk.Misc, chars: int = SIDEBAR_CHARS) -> int:
    """Pixels for `chars` average characters of the body font, plus card padding.

    Only the column's STARTING width: _fit hands the canvas
    left.winfo_reqwidth() on the first <Configure>, so the content has the final
    say either way. What this number decides is whether the column opens at the
    right size or visibly jumps, and on a scaled display the flat 340 opened too
    narrow for text that had already grown.
    """
    from tkinter import font as tkfont
    try:
        em = tkfont.Font(root=w, font=SANS(10, w=w)).measure("0")
    except tk.TclError:              # no interpreter to ask, see look._family
        em = 0
    if em < 1:
        # Nothing answered: fall back to the 8 px measured above, corrected for
        # how far this display is from the 96 dpi it was measured on.
        try:
            em = max(1, round(8 * w.winfo_fpixels("1i") / 96))
        except tk.TclError:
            em = 8
    return chars * em + 2 * SPACE.item


# THE WHEEL DELTA IS NOT ONE UNIT OF ANYTHING. The settings column scrolled with
# int(-e.delta / 120), which is the Windows recipe from
# wiki.tcl-lang.org/page/mousewheel copied without its precondition: 120 is one
# notch on win32 alone. On aqua a notch is a delta of 1, so that division floors
# to 0 for every real trackpad or wheel event and the column did not move at all
# - the wheel was dead on macOS, not stiff. The same page warns that Windows
# precision touchpads send deltas well under 120 "which may accumulate", which
# floors to 0 the same way, so the sub-unit remainder is carried to the next
# event instead of being thrown away.
#
# The divisor is not a property of the platform alone. TIP 474
# (core.tcl-lang.org/tips/doc/trunk/tip/474.md, Final, Tk 8.7) translates x11
# buttons 4-7 into MouseWheel events AND rescales aqua's delta by 120, warning
# that 8.6-era code will otherwise scroll "far too much" - so a mac on Tk 8.7 or
# 9 wants the Windows divisor and a mac on 8.6 wants 1. Hence tk_patchLevel is
# read as well, and `tk windowingsystem` rather than sys.platform, because a Tk
# built for x11 can run on macOS and it is Tk's answer that decides which events
# arrive. wheel_convention and wheel_units are kept pure so the aqua and win32
# branches can be exercised by calling them on the x11 box this was written on,
# where neither windowing system exists to test against.
def wheel_convention(windowing: str, tk_patchlevel: str) -> tuple[int, bool]:
    """(delta that means one scroll unit, whether the wheel also arrives as
    buttons 4 and 5) for this windowing system and Tk version."""
    # Digits only, first two groups: Tk reports pre-releases as "8.7a4", so
    # int() on the split components raises exactly where the answer changes.
    ver = tuple(int(n) for n in re.findall(r"\d+", str(tk_patchlevel))[:2])
    if len(ver) < 2:
        ver = (8, 6)                      # unreadable version: assume the old one
    if windowing == "aqua":
        return (120 if ver >= (8, 7) else 1), False
    if windowing == "x11":
        # Before Tk 8.7 the X server's wheel is buttons 4 and 5 and MouseWheel
        # never fires here at all; from 8.7 Tk translates them, and script-level
        # buttons 4 and 5 then mean physical thumb buttons, so binding those
        # would steal clicks rather than scroll.
        return 120, ver < (8, 7)
    return 120, False


def wheel_units(delta: float, divisor: int, carry: float = 0.0) -> tuple[int, float]:
    """Scroll units for one wheel event, plus the remainder to carry to the next.

    Truncating toward zero and keeping the remainder is what lets a device that
    reports a fifteenth of a notch at a time scroll one line per notch instead of
    nothing at all. Rounding away from zero - Tk 8.7's own choice for fractional
    scroll amounts, TIP 474 - is not usable here: 8.6 rejects a fractional amount
    outright, and on 8.6 aqua a single event is already a whole notch, so it would
    only make a precision device scroll a line per twitch.

    The carry is in DELTA units, not in fractions of a scroll unit. Carrying the
    fraction first, and it lost a line: fifteen events of delta 8 sum to
    0.9999999999999999 in binary floating point, so the notch the user turned
    produced no scroll at all. Integer deltas over an integer divisor are exact.
    """
    div = divisor or 1
    total = carry + float(delta)
    units = int(total / div)               # int() truncates toward zero, both signs
    return units, total - units * div


def tk_wheel_setup(w: tk.Misc) -> tuple[int, bool]:
    """wheel_convention() answered by w's own interpreter."""
    try:
        which = str(w.tk.call("tk", "windowingsystem"))
        level = str(w.tk.call("set", "tk_patchLevel"))
    except tk.TclError:
        which, level = "x11", str(tk.TkVersion)
    return wheel_convention(which, level)


class LearningPlot(tk.Canvas):
    """The learning curve, in units a person can read.

    Y AXIS IS NOT LOSS. It is exp(loss): how many different characters the model
    is effectively still choosing between when it predicts the next one. At the
    start that equals the size of your alphabet, because the model knows nothing
    and every character is equally likely - so the top of the chart is labelled
    "pure guessing" and the line falls from there.

    This is a translation, not a different measurement: exp() of the same loss
    the training loop already computes. It is drawn by hand so the whole program
    still depends on nothing but torch and tkinter.
    """

    def __init__(self, parent, palette: dict, **kw):
        self.C = palette
        self.BG = palette["plot_bg"]
        self.GRID = palette["plot_grid"]
        self.AXIS = palette["plot_axis"]
        self.LEARN = palette["learn"]
        self.UNSEEN = palette["unseen"]
        self.GUESS = palette["guess"]
        super().__init__(parent, bg=self.BG, highlightthickness=0, **kw)
        self.learn_pts: list[tuple[int, float]] = []
        self.unseen_pts: list[tuple[int, float]] = []
        self.total_steps = 1
        self.vocab = 0
        self.unseen_ok = True
        self.bind("<Configure>", lambda e: self.redraw())

    def reset(self, total_steps: int, vocab: int):
        self.learn_pts.clear()
        self.unseen_pts.clear()
        self.total_steps = max(1, total_steps)
        self.vocab = max(vocab, 2)
        self.redraw()

    def add(self, step: int, train_loss: float, val_loss: float):
        self.learn_pts.append((step, math.exp(min(train_loss, 20))))
        self.unseen_pts.append((step, math.exp(min(val_loss, 20))))
        self.redraw()

    def _size(self) -> tuple[int, int]:
        """Canvas size. Its own method so a test can drive redraw() without a
        mapped window -- an unmapped widget reports width 1 and redraw would
        bail out before drawing anything, which would make the drawing untested
        rather than tested."""
        return self.winfo_width(), self.winfo_height()

    def redraw(self):
        self.delete("all")
        w, h = self._size()
        if w < 60 or h < 40:
            return
        pad_l, pad_r, pad_t, pad_b = 62, 14, 16, 30
        x0, y0, x1, y1 = pad_l, pad_t, w - pad_r, h - pad_b

        vals = [v for _, v in self.learn_pts]
        if self.unseen_ok:
            vals += [v for _, v in self.unseen_pts]
        top = max([self.vocab] + vals) if (vals or self.vocab) else 10.0
        lo, hi = 1.0, top * 1.05

        for i in range(5):
            y = y0 + (y1 - y0) * i / 4
            self.create_line(x0, y, x1, y, fill=self.GRID)
            self.create_text(x0 - 8, y, anchor="e", fill=self.AXIS,
                             font=SANS(8),
                             text=f"{hi - (hi - lo) * i / 4:.0f}")

        # -angle is a Tk 8.6 canvas option and Apple's system Python ships Tk 8.5,
        # where create_text answers `unknown option "-angle"`
        # (tcl.tk/man/tcl8.6/TkCmd/canvas.htm lists angle under the text item,
        # added in 8.6). The plot drew without its y-axis label there, silently,
        # because the exception landed inside the redraw. Measured on macOS
        # 26.5.1, Tk 8.5, 2026-09-21. Rotated first, flat as a fallback: the label
        # says what the axis means and is worth more sideways than absent.
        try:
            self.create_text(14, (y0 + y1) / 2, anchor="center", angle=90,
                             fill=self.AXIS, font=SANS(8),
                             text="characters it's choosing between  (lower = smarter)")
        except tk.TclError:
            self.create_text(x0, y0 - 14, anchor="w", fill=self.AXIS,
                             font=SANS(8),
                             text="characters it's choosing between (lower = smarter)")
        self.create_text((x0 + x1) / 2, h - 9, fill=self.AXIS,
                         font=SANS(8), text="training progress →")

        def to_xy(step, val):
            fx = x0 + (x1 - x0) * (step / self.total_steps)
            fy = y1 - (y1 - y0) * ((val - lo) / (hi - lo))
            return fx, max(y0, min(y1, fy))

        if self.vocab:
            _, gy = to_xy(0, self.vocab)
            self.create_line(x0, gy, x1, gy, fill=self.GUESS, dash=(4, 3))
            self.create_text(x0 + 6, gy - 9, anchor="w", fill=self.GUESS,
                             font=SANS(8),
                             text=f"pure guessing — {self.vocab} characters")

        series = [(self.learn_pts, self.LEARN, "your text")]
        if self.unseen_ok:
            series.append((self.unseen_pts, self.UNSEEN, "text it hasn't seen"))
        for pts, colour, label in series:
            if len(pts) >= 2:
                flat = []
                for s, v in pts:
                    flat.extend(to_xy(s, v))
                self.create_line(*flat, fill=colour, width=2, smooth=True)
            elif len(pts) == 1:
                x, y = to_xy(*pts[0])
                self.create_oval(x - 3, y - 3, x + 3, y + 3, fill=colour,
                                 outline=colour)
        for i, (_, colour, label) in enumerate(series):
            self.create_text(x1 - 6, y0 + 4 + i * 15, anchor="ne", fill=colour,
                             font=SANS(9), text=label)
        if not self.unseen_ok and self.learn_pts:
            self.create_text(x1 - 6, y0 + 4 + 15, anchor="ne", fill=self.GUESS,
                             font=SANS(8),
                             text="(can't score unseen text with this file)")


class TrainWorker(threading.Thread):
    """Runs the training loop off the UI thread and reports through a queue.

    Unchanged from the version this file replaced, apart from the message text:
    all of the leakage and split-health logic below decides whether the val
    number means anything, and that decision is what the graph greys out.
    """

    def __init__(self, cfgs: dict, q: queue.Queue, stop: threading.Event):
        super().__init__(daemon=True)
        self.c = cfgs
        self.q = q
        self.stop = stop

    def log(self, msg):
        self.q.put(("log", msg))

    def run(self):
        try:
            self._run()
        except Exception:
            self.q.put(("error", traceback.format_exc()))

    def _run(self):
        c = self.c
        device = c["device"]
        torch.manual_seed(c["seed"])

        # THE PATH THAT ACTUALLY TRAINS, so this is the read that mattered most.
        # It was read_text(encoding="utf-8", errors="ignore"), which meant a file
        # in cp1252 or UTF-16 was silently stripped of whatever would not decode
        # and the leftovers were trained on: a wrong model, produced without one
        # word on screen. ingest.read_any either decodes it and says which
        # encoding worked, or returns text=None with a sentence saying why, and
        # None is refused here rather than turned into a smaller corpus. Raised,
        # not logged and continued: TrainWorker.run catches it onto the queue and
        # the panel shows it, which is the same route every other refusal takes.
        got = ingest.read_any(c["data"])
        if got.text is None:
            raise ValueError(f"{got.say.word}: {got.say.why}")
        text = got.text
        tok = CharTokenizer.from_text(text)
        corpus = Corpus(text, tok, device)
        self.q.put(("vocab", tok.vocab_size))
        self.log(f"Your text: {len(text):,} characters, {tok.vocab_size} different "
                 f"characters. Training on {'the CPU' if device == 'cpu' else 'the graphics card'}.")
        # Only when it was not plain UTF-8. Saying "read as utf-8" on every run
        # is noise; saying it about the one file in fifty that was cp1252 is the
        # difference between a person spotting a wrong guess and not. `kind`
        # comes with it because "read as cp1252" and "read the text out of a
        # .docx" are different facts about where the characters came from.
        if got.encoding and got.encoding != "utf-8":
            self.log(f"  That file is not plain UTF-8: it was read as "
                     f"{got.encoding} ({got.kind}). Nothing was dropped — "
                     f"anything that would not decode is refused rather than "
                     f"skipped.")

        # Before reporting a single val number, find out whether it means
        # anything. Validation text that also appears in training measures
        # memorisation, not generalisation.
        tr_txt, va_txt = group_split(text)
        rep = leakage_scan(tr_txt, va_txt, doc_aligned=True)   # group_split: it is
        health = split_health(text)
        # data.split_verdict, not a local comparison: this used to test only
        # "did the splitter fall short", which is silent on the one corpus shape
        # that matters most - a single document holding nearly all the text,
        # where the splitter does the best that is possible and the best that is
        # possible is still not a holdout. That corpus drew an orange line and
        # called it a fair test.
        verdict = split_verdict(health)
        self.val_ok = rep.trustworthy and verdict is None
        self.log(f"Checked your text for overlap: {rep.summary()}")
        if not rep.trustworthy:
            self.log("  !! The same passages appear in both halves of your text, so "
                     "the orange line is not a fair test. Judge this run on the blue line.")
        elif verdict == "corpus":
            # Report the measured numbers, not a story about them. "One file is
            # most of your text" is the COMMON cause, not the only one: fourteen
            # equal files also cap the achievable split below the request, and
            # naming a cause that is not there sends the user hunting for it.
            self.log(f"  !! Your text cannot be split into a fair test: the most any "
                     f"split could hold back is {health['achievable_val_frac']:.1%}, "
                     f"against the {health['requested_val_frac']:.0%} a fair test needs. "
                     f"You have {health['unique_documents']} document(s), the largest "
                     f"{health['largest_unique_doc_frac']:.0%} of them. More, smaller "
                     f"files would fix this. Judge this run on the blue line.")
        elif verdict == "splitter":
            # Different failure, different remedy. This corpus COULD support the
            # split; this particular one landed badly.
            self.log(f"  !! Only {health['achieved_val_frac']:.1%} of your text was held "
                     f"back for testing, though this text could support "
                     f"{health['achievable_val_frac']:.1%}. A different seed would "
                     f"probably split it better. Judge this run on the blue line.")
        elif verdict:
            self.log("  !! None of your text could be held back for testing, so there "
                     "is no orange line to judge. Judge this run on the blue line.")
        self.q.put(("valtrust", self.val_ok))

        if len(corpus.train) <= c["block_size"]:
            raise ValueError(
                f"There is not enough text to train on: after holding some back for "
                f"testing, only {len(corpus.train)} characters remain, and the model "
                f"reads {c['block_size']} at a time. Add more text, or pick a smaller "
                f"model size.")

        cfg = GPTConfig(vocab_size=tok.vocab_size, block_size=c["block_size"],
                        n_layer=c["n_layer"], n_head=c["n_head"],
                        n_embd=c["n_embd"], dropout=c["dropout"])
        model = GPT(cfg).to(device)
        self.log(f"Built a brand-new model: {model.num_params():,} numbers to learn, "
                 f"all starting at random. Nothing was downloaded.")

        enable_fast_math()
        opt = make_optimizer(model, c["lr"])
        use_bf16 = wants_bf16(device)

        steps = c["steps"]
        warmup = max(10, steps // 20)
        t0 = time.time()
        tokens_per_step = c["batch_size"] * c["block_size"]

        for step in range(steps):
            if self.stop.is_set():
                self.log(f"\nStopped at step {step}. What it learned so far is kept.")
                break

            lr = cosine_lr(step, warmup, steps, c["lr"], c["lr"] / 10)
            for g in opt.param_groups:
                g["lr"] = lr

            if step % c["eval_interval"] == 0 or step == steps - 1:
                L = estimate_loss(model, corpus, c["batch_size"], c["block_size"])
                el = time.time() - t0
                frac = (step + 1) / steps
                self.q.put(("metrics", {
                    "step": step, "train": L["train"], "val": L["val"], "lr": lr,
                    "elapsed": el, "remaining": el / max(frac, 1e-9) - el,
                    "tok_s": tokens_per_step * (step + 1) / max(el, 1e-9)}))

            x, y = corpus.get_batch("train", c["batch_size"], c["block_size"])
            if use_bf16:
                with torch.autocast(device, dtype=torch.bfloat16):
                    _, loss = model(x, y)
            else:
                _, loss = model(x, y)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()

        out = Path(c["out"])
        out.mkdir(parents=True, exist_ok=True)
        torch.save({"model": model.state_dict(), "config": cfg.__dict__,
                    "tokenizer_fingerprint": tokenizer_fingerprint(tok)}, out / "ckpt.pt")
        tok.save(out / "tokenizer.json")
        self.log(f"Saved your model to the '{out.name}' folder. It will still be "
                 f"there next time you open this.")

        # Every GUI run lands in the same append-only log as every CLI run, so a
        # week of experimenting leaves a reviewable trail.
        wall = time.time() - t0
        final = estimate_loss(model, corpus, c["batch_size"], c["block_size"])

        # The comparison that makes the loss mean something. Only shown when the
        # holdout is eligible: if the same text sits on both sides of the split,
        # or the split could never support a holdout, then the model's val loss
        # and the baseline's are wrong in the same direction and comparing them
        # says nothing. Better silence than a confident-looking ratio.
        base = None
        if self.val_ok and corpus.train_text is not None and corpus.val_text:
            base = baselines.compare(corpus.train_text, corpus.val_text,
                                     tok.vocab_size, model_val_nats=final["val"])
            self.log("")
            self.log("How does that compare to something that cannot learn?")
            for line in baselines.summary_lines(base):
                self.log(line)

        # corpus AND split AND data device, the same three the CLI trainer
        # records. A GUI run lands in the same log and is read beside those
        # rows: without the split fingerprint two runs on different holdouts
        # are indistinguishable there, and without data_device a run whose
        # corpus fell back to host memory looks like one that fitted.
        runlog.record("train", device=device, data_device=corpus.data_device,
                      out=str(out), source="studio",
                      corpus=runlog.corpus_fingerprint(text),
                      split_fingerprint=runlog.split_fingerprint(
                          corpus.val_frac, corpus.seed, corpus.val_text),
                      config={k: c[k] for k in ("n_layer", "n_head", "n_embd",
                                                "block_size", "batch_size",
                                                "steps", "lr", "dropout", "seed")},
                      metrics={"train_loss": final["train"], "val_loss": final["val"],
                               "wall_s": wall,
                               "ms_per_step": wall / max(c["steps"], 1) * 1000,
                               "params": model.num_params()},
                      baselines=base,
                      # The scan's own row, not a two-field copy of it: the
                      # verdict is the worst of three signals and this used to
                      # record the verdict beside the CONTENT fraction, which
                      # is frequently not the arm that decided. See
                      # leakage.Report.record.
                      leakage=rep.record())
        self.q.put(("done", {"model": model, "tok": tok, "device": device,
                             "elapsed": time.time() - t0,
                             "train": final["train"], "vocab": tok.vocab_size}))


class Studio(ttk.Frame):
    """The training surface. Usable standalone (main() below) or embedded.

    EMBEDDED MODE exists because t/lab.py hosts this as its Train tab, and two
    tk.Tk() roots in one process is undefined behaviour rather than merely untidy:
    the first mainloop() opens BOTH windows and blocks until both close
    (stackoverflow.com/q/39417091, read 2026-09-20 via the StackExchange API). So
    the merged app has exactly ONE root, owned by the lab shell, and this class
    takes a parent widget either way -- which it already did, being a ttk.Frame.

    What embedding must NOT do is repaint the host, so `embedded=True` skips the
    two calls in `_apply_theme` that would: `theme_use`, and the
    winfo_toplevel().configure() that would repaint the shell's root from
    whichever ground this page resolved. It does NOT skip the style database,
    which is process-wide whatever is passed: "." is "the theme root style on
    which derived styles are based" (core.tcl-lang.org/tk/doc/trunk/doc/ttk_style.n),
    so configuring it reaches the shell's ttk widgets too. That is now the point
    rather than the hazard -- both halves draw from look.py, so the styling the
    shell never wrote for its own ttk.Scrollbars arrives with the right colours in
    it. The cost, stated because it is real: the shell's scrollbars look different
    on a machine with torch (this page loads, and styles them) from one without
    (the Train tab says so instead, and clam's own grey stands).

    Which theme is live is NOT decided here. It used to be forced dark on the
    grounds that the shell was dark-only; the shell now follows the operating
    system, so it is read off the palette the host hands over -- see __init__.
    """

    def __init__(self, root, embedded: bool = False, palette: dict | None = None):
        super().__init__(root, padding=SPACE.item)
        # Resolve the families against THIS widget's interpreter before anything
        # asks for a font, rather than leaving look._family() to find a default
        # root that, embedded, is the shell's and right only by luck.
        resolve_fonts(self)
        self.embedded = embedded
        self.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.q: queue.Queue = queue.Queue()
        self.stop_evt = threading.Event()
        self.worker: TrainWorker | None = None
        self.model = None
        self.tok = None
        self.device = pick_device()
        self.vocab = 0
        self.C = dict(look.PALETTES["dark" if system_wants_dark() else "light"])
        if palette:
            # The host's colours win for every key it names; this file keeps the
            # ones it alone has (the plot series, the log surface), because the
            # lab palette has no equivalent and those carry meaning.
            self.C.update(palette)
        # WHICH THEME IS LIVE IS READ OFF THE PALETTE, not decided before it
        # arrives. Embedded, this forced dark, which was right while t/lab.py was
        # dark-only and is wrong now that the shell asks look.palette() and follows
        # the operating system: on a light desktop it hands over the light palette
        # and a flag saying dark, so every decision downstream of the flag is made
        # about the wrong theme. `bg` is the ground either way, so comparing it to
        # look's two grounds says which palette won the update above. Nothing in
        # this file branches on it any more -- every colour is a palette lookup --
        # so it is here as the answer to "which theme is this", which is what
        # test_studio asks it for.
        self.dark = self.C["bg"] == look.PALETTES["dark"]["bg"]
        self._apply_theme()
        self.speeds = load_speeds()
        # The same file as self.speeds, read once more for `params`, which is
        # what says which alphabet each timing was taken on. See step_flops.
        self.bench = load_bench()
        self.advanced_open = False
        self.val_ok = True
        # What the last finished scan concluded about the chosen file. None means
        # no scan has landed yet - the read is on a worker thread now, so "not
        # answered yet" is a real third state and _start must not read it as
        # "fine". `corpus_say` is ingest's own sentence when the file was
        # refused, so the refusal a person sees when they press Start is word for
        # word the one already under the filename.
        self.corpus_ok: bool | None = None
        self.corpus_say = None
        self._scan_token = 0

        # Chosen presets. The advanced fields are derived FROM these, so there is
        # exactly one source of truth and the two can never disagree.
        self.size_name = tk.StringVar(value="Medium")
        self.length_name = tk.StringVar(value="Normal")
        self.style_idx = tk.IntVar(value=2)
        self.sample_len = tk.IntVar(value=400)

        self._build_left()
        self._build_right()
        self._apply_preset()
        self._scan_corpus(quiet=True)
        self._load_saved(quiet=True)
        self._drain_after = None
        self.bind("<Destroy>", self._stop_draining, add="+")
        self._keep_draining()

    def _apply_theme(self):
        """Restyle ttk for the active palette.

        A natively drawn theme IGNORES the colours you configure: "The XP theme
        field element is drawn by the native XP themeing engine so you don't get
        to pick and choose - the user gets what she expects from the theme she has
        chosen for Windows" (wiki.tcl-lang.org/page/Ttk, quoting comp.lang.tcl
        2011-03-16), and vista, winnative and aqua are all drawn that way. So a
        dark palette under 'vista' produced light grey boxes with pale text on
        them, unreadable and worse than not offering dark mode at all. 'clam' is
        drawn by Tk itself and does honour the colours.

        BOTH THEMES NOW NEED IT, where light used to be skipped. Skipping was
        right while this file's light `bg` was #f0f0f0, which IS the Windows grey:
        vista drew the native widget and the native widget already matched. look's
        light ground is warm paper instead, and no native widget can be moved onto
        it, so light under vista left 59 ttk widgets on the platform grey with the
        plot, the log and the scrolling sidebar on paper around them. Every value
        below is a palette lookup rather than a branch on the theme, so one path
        serves both. What is lost is the light theme looking like the rest of
        Windows, which stopped being available when the ground stopped being that
        grey -- unrendered here, because this machine has no torch.
        """
        C = self.C
        style = ttk.Style()
        if not self.embedded:
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass
        style.configure(".", background=C["bg"], foreground=C["fg"],
                        fieldbackground=C["field"], bordercolor=C["panel"],
                        lightcolor=C["panel"], darkcolor=C["panel"])
        style.configure("TFrame", background=C["bg"])
        style.configure("TLabel", background=C["bg"], foreground=C["fg"])
        # line and select, not the two hex literals that survived here when the
        # rest of the colours were collected: a card's edge is the hairline, and a
        # button under the pointer is the shaded band. Both were dark-only greys,
        # so they were also the reason this styling could not be reused in light.
        style.configure("TLabelframe", background=C["bg"], bordercolor=C["line"])
        style.configure("TLabelframe.Label", background=C["bg"],
                        foreground=C["fg"])
        style.configure("TRadiobutton", background=C["bg"], foreground=C["fg"])
        style.configure("TCheckbutton", background=C["bg"], foreground=C["fg"])
        style.configure("TButton", background=C["panel"], foreground=C["fg"])
        style.map("TButton",
                  background=[("active", C["select"]), ("disabled", C["bg"])],
                  foreground=[("disabled", C["faint"])])
        style.map("TRadiobutton", background=[("active", C["bg"])])
        style.configure("TEntry", fieldbackground=C["field"],
                        foreground=C["fg"], insertcolor=C["fg"])
        style.configure("TScale", background=C["bg"], troughcolor=C["field"])
        style.configure("TScrollbar", background=C["panel"],
                        troughcolor=C["bg"], arrowcolor=C["fg"])
        if not self.embedded:
            self.winfo_toplevel().configure(bg=C["bg"])

    # ---------------------------------------------------------------- left
    def _build_left(self):
        # SCROLLABLE, so the column can never be taller than the screen.
        # The settings column is the tall part of this window, and on a laptop
        # or a scaled display it is exactly what runs off the bottom and takes
        # the Start button with it. A scrollbar that appears only when it is
        # needed is the difference between "cramped" and "the button is gone".
        outer = ttk.Frame(self)
        outer.grid(row=0, column=0, sticky="nsw", padx=(0, SPACE.item))
        outer.rowconfigure(0, weight=1)
        canvas = tk.Canvas(outer, highlightthickness=0, borderwidth=0,
                           width=sidebar_width(self), bg=self.C["bg"])
        canvas.grid(row=0, column=0, sticky="nsew")
        bar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        left = ttk.Frame(canvas)
        win = canvas.create_window((0, 0), window=left, anchor="nw")
        self._left_canvas, self._left_bar, self._left_outer = canvas, bar, outer

        def _fit(_=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            need = left.winfo_reqheight()
            canvas.configure(width=left.winfo_reqwidth())
            canvas.itemconfigure(win, width=left.winfo_reqwidth())
            if need > canvas.winfo_height():
                bar.grid(row=0, column=1, sticky="ns")
            else:
                bar.grid_remove()
            # A binding is per widget, so anything that joined the column since
            # the last pass needs one. Configure fires when a child is added.
            self._bind_wheel(outer)
        left.bind("<Configure>", _fit)
        canvas.bind("<Configure>", _fit)
        self._bind_wheel(outer)

        # --- 1. text
        box = ttk.LabelFrame(left, text=" 1 · What should it learn from? ")
        box.grid(row=0, column=0, sticky="ew", pady=(0, SPACE.item))
        box.columnconfigure(0, weight=1)
        self.v_data = tk.StringVar(value=str(HERE / "corpus.txt"))
        self.l_file = ttk.Label(box, text="—", font=SANS(9, "bold"))
        self.l_file.grid(row=0, column=0, sticky="w", padx=SPACE.item,
                         pady=(SPACE.inner, 0))
        self.l_corpus = ttk.Label(box, text="—", foreground=self.C["muted"],
                                  wraplength=300, justify="left")
        self.l_corpus.grid(row=1, column=0, sticky="w", padx=SPACE.item,
                           pady=SPACE.tight)
        brow = ttk.Frame(box)
        brow.grid(row=2, column=0, sticky="w", padx=SPACE.item,
                  pady=(0, SPACE.inner))
        ttk.Button(brow, text="Get better text…",
                   command=self._get_corpus).grid(row=0, column=0)
        ttk.Button(brow, text="Use my own file…", command=self._browse).grid(
            row=0, column=1, padx=(SPACE.inner, 0))

        # --- 2. size
        arch = ttk.LabelFrame(left, text=" 2 · How big should it be? ")
        arch.grid(row=1, column=0, sticky="ew", pady=(0, SPACE.item))
        arch.columnconfigure(0, weight=1)
        # Radio and blurb get their OWN rows. Sharing one cell and separating
        # them with padding put the description on top of the option's name, so
        # the three sizes rendered with no readable labels at all.
        for i, name in enumerate(SIZES):
            ttk.Radiobutton(arch, text=name, value=name, variable=self.size_name,
                            command=self._apply_preset).grid(
                row=2 * i, column=0, sticky="w", padx=SPACE.item,
                pady=(SPACE.inner, 0))
            ttk.Label(arch, text=SIZES[name]["blurb"], foreground=self.C["faint"],
                      wraplength=280, justify="left").grid(
                row=2 * i + 1, column=0, sticky="w", padx=(INDENT, SPACE.item),
                pady=(0, SPACE.tight))
        self.l_params = ttk.Label(arch, text="", font=SANS(9, "bold"),
                                  foreground=self.C["ok"], wraplength=300,
                                  justify="left")
        self.l_params.grid(row=2 * len(SIZES), column=0, sticky="w",
                           padx=SPACE.item, pady=SPACE.inner)

        # --- 3. how long
        tr = ttk.LabelFrame(left, text=" 3 · How long should it practise? ")
        tr.grid(row=2, column=0, sticky="ew", pady=(0, SPACE.item))
        tr.columnconfigure(0, weight=1)
        for i, name in enumerate(LENGTHS):
            ttk.Radiobutton(tr, text=name, value=name, variable=self.length_name,
                            command=self._apply_preset).grid(
                row=i, column=0, sticky="w", padx=SPACE.item,
                pady=(SPACE.inner if i == 0 else SPACE.tight, 0))
        self.l_time = ttk.Label(tr, text="", foreground=self.C["muted"], wraplength=300,
                                justify="left")
        self.l_time.grid(row=len(LENGTHS), column=0, sticky="w", padx=SPACE.item,
                         pady=(SPACE.tight, SPACE.inner))

        # --- run
        run = ttk.Frame(left)
        run.grid(row=3, column=0, sticky="ew")
        run.columnconfigure(0, weight=1)
        self.b_train = ttk.Button(run, text="▶   Start training",
                                  command=self._start)
        self.b_train.grid(row=0, column=0, sticky="ew", ipady=8)
        self.b_stop = ttk.Button(run, text="■  Stop", command=self._stop,
                                 state="disabled")
        self.b_stop.grid(row=0, column=1, padx=(SPACE.inner, 0), ipady=8)

        # --- advanced, shut by default
        self.b_adv = ttk.Button(left, text="▸  Show advanced settings",
                                command=self._toggle_advanced)
        self.b_adv.grid(row=4, column=0, sticky="w", pady=(SPACE.item, 0))
        self.adv = ttk.LabelFrame(left, text=" Advanced — every knob, as before ")
        self.adv.columnconfigure(1, weight=1)
        self._build_advanced()
        self._bind_wheel(outer)

    def _bind_wheel(self, w) -> None:
        """Bind the wheel on w and every widget inside it. Safe to repeat.

        PER WIDGET, NOT bind_all. The "all" tag holds one script per sequence for
        the whole application, and t/lab.py binds <MouseWheel>, <Button-4> and
        <Button-5> there for its own scrolling step list; with this page embedded
        as that window's Train tab, whichever of the two was built second
        replaced the other's script and one of the two areas silently stopped
        scrolling. Tk 8.6 sends the wheel to the window under the pointer rather
        than to the focus window (wiki.tcl-lang.org/page/mousewheel), so binding
        the subtree is sufficient and needs no Enter/Leave bookkeeping - and the
        Enter/Leave-plus-unbind_all recipe would be worse than useless here,
        since unbind_all removes the host's binding along with ours. Rebinding a
        widget just replaces its script, so calling this again from _fit costs a
        walk and nothing else. Every widget in the column is created by
        _build_left and _build_advanced, so one pass covers it; the _fit pass is
        there for anything added later, since an unbound widget is a hole in the
        scroll area -- Tk offers a wheel event to the widget's OWN bindtags, not
        to its parent's.
        """
        if not hasattr(self, "_wheel_seqs"):
            cv = self._left_canvas
            divisor, buttons = tk_wheel_setup(cv)
            self._wheel_carry = 0.0

            def on_wheel(e):
                # e.delta is 0 whenever Tk hands tkinter a non-integer %D: it
                # swallows the conversion error rather than raising (cpython
                # Lib/tkinter/__init__.py, Misc._substitute, getint(D) inside a
                # try). That scrolls nothing and leaves the carry alone, so a
                # later whole delta still lands; there is nothing better to do
                # from here, the value is gone before Python sees it.
                units, self._wheel_carry = wheel_units(-e.delta, divisor,
                                                       self._wheel_carry)
                if units:
                    cv.yview_scroll(units, "units")
                return "break"      # never let a class binding act on it as well

            self._wheel_seqs = [("<MouseWheel>", on_wheel)]
            if buttons:
                self._wheel_seqs += [("<Button-4>", lambda _e: self._wheel_step(-1)),
                                     ("<Button-5>", lambda _e: self._wheel_step(1))]
        tree, stack = [], [w]
        while stack:                            # iterative: a deep column is fine
            widget = stack.pop()
            tree.append(widget)
            stack.extend(widget.winfo_children())
        # Walk every time, bind only when the column grew. _fit runs on every
        # <Configure>, which during a resize drag is dozens a second, and
        # rebinding ~150 widgets times 3 sequences each time is thousands of Tcl
        # calls a second for no change. A count, not an identity check: this
        # column only ever gains widgets.
        if len(tree) == getattr(self, "_wheel_bound", -1):
            return
        self._wheel_bound = len(tree)
        for widget in tree:
            for seq, fn in self._wheel_seqs:
                widget.bind(seq, fn)

    def _wheel_step(self, units: int) -> str:
        """One X11 wheel button press: buttons 4 and 5 carry no delta."""
        self._left_canvas.yview_scroll(units, "units")
        return "break"

    def _build_advanced(self):
        """The original controls, unchanged in meaning and still free text.

        Kept because removing them would take real capability away from someone
        who knows what they are for. Editing any of them switches the preset
        above to "Custom" rather than silently disagreeing with it.
        """
        self.v_layer = tk.StringVar(value="4")
        self.v_head = tk.StringVar(value="4")
        self.v_embd = tk.StringVar(value="256")
        self.v_block = tk.StringVar(value="128")
        self.v_drop = tk.StringVar(value="0.1")
        self.v_steps = tk.StringVar(value="2000")
        self.v_batch = tk.StringVar(value="32")
        self.v_lr = tk.StringVar(value=f"{auto_lr(256):.2g}")
        self.v_eval = tk.StringVar(value="100")
        self.v_seed = tk.StringVar(value="1337")
        self.v_out = tk.StringVar(value="out_gui")
        self.v_cpu = tk.BooleanVar(value=False)

        rows = [("layers", self.v_layer), ("heads", self.v_head),
                ("embed dim", self.v_embd), ("context", self.v_block),
                ("dropout", self.v_drop), ("steps", self.v_steps),
                ("batch size", self.v_batch), ("learn rate", self.v_lr),
                ("eval every", self.v_eval), ("seed", self.v_seed),
                ("save to", self.v_out)]
        for r, (label, var) in enumerate(rows):
            ttk.Label(self.adv, text=label).grid(row=r, column=0, sticky="w",
                                                 padx=(SPACE.item, SPACE.inner),
                                                 pady=SPACE.tight)
            ttk.Entry(self.adv, textvariable=var, width=12).grid(
                row=r, column=1, sticky="w", pady=SPACE.tight)
        ttk.Checkbutton(self.adv, text="force CPU", variable=self.v_cpu).grid(
            row=len(rows), column=0, columnspan=2, sticky="w", padx=SPACE.item,
            pady=(SPACE.tight, SPACE.inner))

        self._preset_values: dict[str, str] = {}
        for v in (self.v_layer, self.v_head, self.v_embd, self.v_block,
                  self.v_steps, self.v_batch):
            v.trace_add("write", lambda *_: self._note_custom())

    def _toggle_advanced(self):
        self.advanced_open = not self.advanced_open
        if self.advanced_open:
            self.adv.grid(row=5, column=0, sticky="ew", pady=(SPACE.inner, 0))
            self.b_adv.config(text="▾  Hide advanced settings")
        else:
            self.adv.grid_remove()
            self.b_adv.config(text="▸  Show advanced settings")

    # --------------------------------------------------------------- right
    def _build_right(self):
        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=3)
        right.rowconfigure(3, weight=2)

        # THE HEADLINE. One sentence, in words, above the chart -- because the
        # chart is the evidence and this is the finding.
        self.l_headline = ttk.Label(
            right, text="Press “Start training” and this will fill in.",
            font=SANS(12, "bold"), wraplength=640, justify="left")
        self.l_headline.grid(row=0, column=0, sticky="w", pady=(0, SPACE.inner))

        self.plot = LearningPlot(right, self.C, height=190)
        self.plot.grid(row=1, column=0, sticky="nsew")

        self.l_explain = ttk.Label(
            right, foreground=self.C["muted"], wraplength=640, justify="left",
            text="The blue line is how well it predicts the text you gave it. "
                 "The orange line is text it was never shown — if orange stops "
                 "falling while blue keeps going, it has started memorising "
                 "instead of learning.")
        self.l_explain.grid(row=2, column=0, sticky="ew", pady=SPACE.inner)

        # A hard-coded wraplength is a guess about the window width, and it was
        # wrong: at the default size the sentence ran off the right edge mid-word.
        # Track the real width instead, so it stays right when the window is
        # resized or maximised too.
        def _rewrap(event):
            w = max(240, event.width - 12)
            self.l_headline.configure(wraplength=w)
            self.l_explain.configure(wraplength=w)
        right.bind("<Configure>", _rewrap)

        logbox = ttk.LabelFrame(right, text=" What's happening ")
        logbox.grid(row=3, column=0, sticky="nsew")
        logbox.columnconfigure(0, weight=1)
        logbox.rowconfigure(0, weight=1)
        self.log = tk.Text(logbox, height=5, bg=self.C["log_bg"], fg=self.C["log_fg"],
                           insertbackground=self.C["log_fg"], font=MONO(9),
                           wrap="word", relief="flat")
        self.log.grid(row=0, column=0, sticky="nsew", padx=SPACE.tight,
                      pady=SPACE.tight)
        sb = ttk.Scrollbar(logbox, command=self.log.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.log["yscrollcommand"] = sb.set

        # --- 4. try it
        gen = ttk.LabelFrame(right, text=" 4 · Try it out ")
        gen.grid(row=4, column=0, sticky="ew", pady=(SPACE.item, 0))
        gen.columnconfigure(1, weight=1)

        ttk.Label(gen, text="Start it off with:").grid(
            row=0, column=0, padx=(SPACE.item, SPACE.inner),
            pady=(SPACE.inner, SPACE.tight), sticky="w")
        self.v_prompt = tk.StringVar(value="def ")
        ttk.Entry(gen, textvariable=self.v_prompt).grid(
            row=0, column=1, sticky="ew", pady=(SPACE.inner, SPACE.tight),
            padx=(0, SPACE.item))

        ttk.Label(gen, text="How adventurous?").grid(
            row=1, column=0, padx=(SPACE.item, SPACE.inner), sticky="w")
        srow = ttk.Frame(gen)
        srow.grid(row=1, column=1, sticky="ew", padx=(0, SPACE.item))
        srow.columnconfigure(0, weight=1)
        ttk.Scale(srow, from_=0, to=len(STYLES) - 1, orient="horizontal",
                  variable=self.style_idx,
                  command=lambda *_: self._style_label()).grid(
            row=0, column=0, sticky="ew")
        self.l_style = ttk.Label(srow, text="", width=16, foreground=self.C["muted"])
        self.l_style.grid(row=0, column=1, padx=(SPACE.inner, 0))
        # Inside srow, not in `gen`: gen's row 2 already holds the length slider,
        # and gridding on top of it would stack two widgets in one cell.
        self.l_style_note = ttk.Label(srow, text="", foreground=self.C["faint"])
        self.l_style_note.grid(row=1, column=0, columnspan=2, sticky="w",
                               pady=(SPACE.tight, 0))

        ttk.Label(gen, text="How much text?").grid(
            row=2, column=0, padx=(SPACE.item, SPACE.inner), sticky="w",
            pady=(SPACE.tight, SPACE.inner))
        lrow = ttk.Frame(gen)
        lrow.grid(row=2, column=1, sticky="ew", padx=(0, SPACE.item),
                  pady=(SPACE.tight, SPACE.inner))
        lrow.columnconfigure(0, weight=1)
        ttk.Scale(lrow, from_=100, to=2000, orient="horizontal",
                  variable=self.sample_len,
                  command=lambda *_: self._len_label()).grid(
            row=0, column=0, sticky="ew")
        self.l_len = ttk.Label(lrow, text="", width=16, foreground=self.C["muted"])
        self.l_len.grid(row=0, column=1, padx=(SPACE.inner, 0))

        self.b_gen = ttk.Button(gen, text="Write something",
                                command=self._generate, state="disabled")
        self.b_gen.grid(row=3, column=0, columnspan=2, sticky="ew",
                        padx=SPACE.item, pady=(0, SPACE.item), ipady=4)

        self.status = ttk.Label(self, text="", foreground=self.C["muted"])
        self.status.grid(row=1, column=0, columnspan=2, sticky="w",
                         pady=(SPACE.inner, 0))
        self._style_label()
        self._len_label()
        self._set_status(f"Ready. Training will use "
                         f"{'the CPU' if self.device == 'cpu' else 'your graphics card'}.")

    # ------------------------------------------------------------- presets
    def _style_label(self):
        name = STYLES[int(self.style_idx.get())][0]
        self.l_style.config(text=name)
        if hasattr(self, "l_style_note"):
            self.l_style_note.config(text=STYLE_NOTES.get(name, ""))

    def _len_label(self):
        n = int(self.sample_len.get())
        self.l_len.config(text=f"about {n // 5} words")

    def _note_custom(self):
        """An advanced edit that disagrees with the preset relabels the preset."""
        if not hasattr(self, "_preset_values") or not self._preset_values:
            return
        now = {k: v.get() for k, v in (("layers", self.v_layer),
                                       ("heads", self.v_head),
                                       ("embd", self.v_embd),
                                       ("block", self.v_block),
                                       ("steps", self.v_steps),
                                       ("batch", self.v_batch))}
        if now != self._preset_values:
            # The one colour literal left after the move to look.py, and the only
            # text in either half of the window that misses the bar look's tests
            # hold every palette pair to: darkgoldenrod measures 2.79:1 on look's
            # light paper and 3.07:1 on its card, against the 4.5:1 of SC 1.4.3.
            # `warn` is the same amber intention at 4.60 and 5.06, and it follows
            # the theme, which a literal cannot -- the line it is reset to two
            # methods down already reads `ok` from the palette.
            self.l_params.config(
                text=self.l_params.cget("text").split("  —")[0] + "  — edited by hand",
                foreground=self.C["warn"])

    def _apply_preset(self):
        """Presets are the source of truth; the advanced fields are written FROM
        them. One direction only, so the two can never silently disagree."""
        s = SIZES[self.size_name.get()]
        self.v_layer.set(str(s["n_layer"]))
        self.v_head.set(str(s["n_head"]))
        self.v_embd.set(str(s["n_embd"]))
        self.v_block.set(str(s["block_size"]))
        self.v_batch.set(str(s["batch_size"]))
        self.v_lr.set(f"{auto_lr(s['n_embd']):.2g}")

        dev = "cpu" if getattr(self, "v_cpu", None) and self.v_cpu.get() else self.device
        key = f"{dev}/{s['key']}"
        ms = self.speeds.get(key)
        length = LENGTHS[self.length_name.get()]
        target, blurb = length["seconds"], length["blurb"]

        def steps_for(per_step_ms: float) -> int:
            """Steps that fill the wall-clock target at this speed, rounded to a
            hundred so the number reads as a choice and not as a measurement."""
            return max(200, int(round(target / (per_step_ms / 1000) / 100) * 100))

        # FOUR ARMS, AND EACH ONE KNOWS SOMETHING DIFFERENT. The estimate used to
        # be two: timed, or not timed. That collapsed "timed on an alphabet we
        # can compare with yours" together with "timed, but on an alphabet nobody
        # recorded" and printed the same confident minutes for both.
        benched_on = bench_vocab(self.bench.get(key, {}), s) if ms else None
        if ms and self.vocab and benched_on:
            shape = (s["block_size"], s["n_layer"], s["n_embd"])
            core = step_flops(0, *shape)                 # the vocab-free part
            here = step_flops(self.vocab, *shape)
            scale = here / step_flops(benched_on, *shape)
            steps = steps_for(ms * scale)
            text = (f"About {human_time(steps * ms * scale / 1000)} on this "
                    f"machine ({steps:,} practice steps).  {blurb}")
            # SAID ONLY WHEN THE ALPHABET IS MORE THAN A TENTH OF A STEP, the
            # same tenth say_alphabet uses and drawn for the same reason: the
            # correction is always applied, but below a tenth it is a percent or
            # two and a sentence about alphabets beside it is noise rather than
            # honesty. 96 characters of English against this benchmark's 136 is
            # 2.8% of a step and says nothing; 3,000 is 47% and says so.
            if here * 0.9 > core:
                text += (f"\nYour text uses {self.vocab:,} different characters "
                         f"and this machine was timed on {benched_on:,}, which "
                         f"costs {scale:.2f} times as much per step. Expect a "
                         f"little longer rather than shorter.")
            self.l_time.config(text=text)
        elif ms and self.vocab:
            # Timed, but the timing does not record its own alphabet, so it
            # cannot be carried onto this one. The untimed arm below is the
            # precedent this follows: say there is no honest estimate, rather
            # than print the unscaled minutes as though the alphabet were free.
            steps = steps_for(ms)
            self.l_time.config(
                text=f"{steps:,} practice steps. This machine was timed, but the "
                     f"timing does not record how many different characters it "
                     f"was timed on, and your text has {self.vocab:,} — so there "
                     f"is no honest estimate in minutes. Run “Check My Computer” "
                     f"again and this will show real minutes.  {blurb}")
        elif ms:
            # No text chosen yet, so there is no alphabet to correct for and none
            # is claimed. This is the sentence as it always read.
            steps = steps_for(ms)
            self.l_time.config(
                text=f"About {human_time(steps * ms / 1000)} on this machine "
                     f"({steps:,} practice steps).  {blurb}")
        else:
            ref = LENGTHS["Normal"]["seconds"]
            steps = max(200, int(round(UNTIMED_NORMAL_STEPS * target / ref / 100) * 100))
            self.l_time.config(
                text=f"{steps:,} practice steps. This computer has not been timed "
                     f"yet, so there is no honest estimate of how long that takes "
                     f"— but the three lengths do differ. Run “Check My Computer” "
                     f"once and this will show real minutes.")
        self.v_steps.set(str(steps))
        self.v_eval.set(str(max(10, steps // 25)))

        n = param_count(max(self.vocab, 1), s["block_size"], s["n_layer"],
                        s["n_head"], s["n_embd"])
        self.l_params.config(
            text=f"{n:,} numbers to learn, all starting random", foreground=self.C["ok"])
        self._preset_values = {"layers": self.v_layer.get(), "heads": self.v_head.get(),
                               "embd": self.v_embd.get(), "block": self.v_block.get(),
                               "steps": self.v_steps.get(), "batch": self.v_batch.get()}

    # ------------------------------------------------------------- helpers
    def _set_status(self, msg):
        self.status.config(text=msg)

    def _write(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def _browse(self):
        """Pick a file, and say straight away if it is one that cannot be read.

        THE FILTER LIST NAMES WHAT ingest CAN ACTUALLY OPEN, which was one entry
        - "*.txt" - beside an "All" that let anything at all through to a UTF-8
        read. Both halves were wrong in opposite directions: a .csv, .jsonl or
        .log of plain text was hidden behind the wrong filter, and a .png picked
        through "All" reached the corpus as mojibake.

        "All files" STAYS, because refusing an unknown extension is the failure
        test_ingest.py was written against - a file of plain text with no
        extension, or one called .dat, is trainable and must be reachable - and
        because a filter is a convenience while ingest.can_train_on is the
        decision. What changed is that the decision now happens: a file the
        picker allowed but ingest will not read is refused here, in ingest's own
        words, instead of at the far end of a training run.
        """
        p = filedialog.askopenfilename(
            title="Pick a text file to learn from",
            filetypes=[("Text", "*.txt *.md *.csv *.tsv *.jsonl *.log"),
                       ("Word document", "*.docx"),
                       ("EPUB book", "*.epub"),
                       ("Web page", "*.html *.htm"),
                       ("All files", "*.*")])
        if not p:
            return
        # can_train_on, not read_any: the contract offers it as the cheap check
        # for exactly this, so picking a 4 GB video does not read a 4 GB video.
        # The full sentence still comes from the scan below, which reads it
        # properly on a worker; this only stops an obviously unusable pick from
        # replacing a working corpus path.
        if not ingest.can_train_on(p):
            messagebox.showerror(
                "That file cannot be used as text",
                f"{Path(p).name} could not be read as text.\n\n"
                f"Plain text in any encoding works, and so do .docx, .epub and "
                f"saved web pages. A picture, a video, a zip or a program is "
                f"not text, whatever it is called.")
            return
        self.v_data.set(p)
        self._scan_corpus()

    def _get_corpus(self):
        """Pick ready-made training text, as presets rather than a URL box.

        WHY THIS BUTTON EXISTS. The corpus that shipped was 549 KB of this
        repository's own Python across 13 files. A 3M-parameter character model
        cannot produce anything usable from that no matter how long it trains,
        which made the whole tool look like a benchmark harness for something
        unusable. What a small model needs is simple, plentiful English, and
        which corpus that is happens to be a settled question - see get_corpus.py.
        """
        import get_corpus

        win = tk.Toplevel(self)
        win.title("Get text to learn from")
        win.transient(self.winfo_toplevel())
        win.resizable(False, False)
        choice = tk.StringVar(value="stories")
        mb = tk.IntVar(value=200)

        ttk.Label(win, text="What should your AI read?",
                  font=SANS(11, "bold")).grid(
            row=0, column=0, sticky="w", padx=SPACE.card,
            pady=(SPACE.item, SPACE.inner))
        for i, name in enumerate(sorted(get_corpus.SOURCES)):
            s = get_corpus.SOURCES[name]
            label = {"stories": "Simple stories  (recommended)",
                     "books": "Classic books"}.get(name, name)
            ttk.Radiobutton(win, text=label, value=name, variable=choice).grid(
                row=1 + 2 * i, column=0, sticky="w", padx=SPACE.card)
            ttk.Label(win, text=s["best_for"], foreground=self.C["faint"],
                      wraplength=430, justify="left").grid(
                row=2 + 2 * i, column=0, sticky="w", padx=(INDENT, SPACE.card),
                pady=(0, SPACE.inner))

        size_row = ttk.Frame(win)
        size_row.grid(row=9, column=0, sticky="ew", padx=SPACE.card,
                      pady=SPACE.tight)
        ttk.Label(size_row, text="How much?").grid(row=0, column=0)
        l_mb = ttk.Label(size_row, text="", width=22, foreground=self.C["muted"])
        ttk.Scale(size_row, from_=20, to=600, orient="horizontal", variable=mb,
                  length=250,
                  command=lambda *_: l_mb.config(
                      text=f"{int(mb.get())} MB  (~{int(mb.get())*1_000_000/1e6:.0f}M characters)")
                  ).grid(row=0, column=1, padx=SPACE.inner)
        l_mb.grid(row=0, column=2)
        l_mb.config(text="200 MB  (~200M characters)")

        ttk.Label(win, wraplength=430, justify="left", foreground=self.C["faint"],
                  text="Downloaded once and kept, so this is a one-time wait. "
                       "Only plain text is fetched — the model itself is always "
                       "built from scratch on this computer.").grid(
            row=10, column=0, sticky="w", padx=SPACE.card, pady=SPACE.inner)

        btns = ttk.Frame(win)
        btns.grid(row=11, column=0, sticky="e", padx=SPACE.card,
                  pady=(0, SPACE.item))
        b_go = ttk.Button(btns, text="Download")
        b_go.grid(row=0, column=0)
        ttk.Button(btns, text="Cancel", command=win.destroy).grid(
            row=0, column=1, padx=(SPACE.inner, 0))

        def go():
            b_go.config(state="disabled", text="Downloading…")
            src, want = choice.get(), int(mb.get())
            self._write(f"Downloading {want} MB of '{src}'. This runs once and is "
                        f"then kept on disk.")

            def work():
                try:
                    import io as _io
                    import contextlib as _ctx
                    buf = _io.StringIO()
                    argv = sys.argv
                    sys.argv = ["get_corpus.py", src, "--mb", str(want),
                                "--out", str(HERE / "corpus.txt")]
                    try:
                        with _ctx.redirect_stdout(buf):
                            get_corpus.main()
                    finally:
                        sys.argv = argv
                    self.q.put(("corpus", buf.getvalue()))
                except Exception:
                    self.q.put(("error", traceback.format_exc()))

            threading.Thread(target=work, daemon=True).start()
            win.destroy()

        b_go.config(command=go)
        win.grab_set()

    def _scan_corpus(self, quiet=False):
        """Start reading the chosen file. The answer arrives through the queue.

        OFF THE TK THREAD, because this reads a whole corpus and then runs
        leakage.scan over up to SCAN_SAMPLE_BYTES of it. "Because it is
        single-threaded, event handlers must respond quickly, otherwise they will
        block other events from being processed. To avoid this, any long-running
        computations should not run in an event handler, but are either broken
        into smaller pieces using timers, or run in another thread"
        (docs.python.org/3/library/tkinter.html, Threading model). This ran
        synchronously from three places — startup, the file picker, and a
        finished download — so a large corpus froze the window with no repaint
        and no cursor, which on Windows is the state where the shell offers to
        kill the program. The download in _get_corpus was already a daemon thread
        reporting through self.q, and this follows it exactly. No widget is
        touched from the worker, because "if the Tcl interpreter is not running
        the event loop and processing events, any tkinter calls made from threads
        other than the one running the Tcl interpreter will fail" (same page),
        and during startup the loop is not running yet.
        """
        p = Path(self.v_data.get())
        self.l_file.config(text=p.name)
        # A TOKEN, NOT A FLAG. Two picks in quick succession leave two workers
        # running, and the slower one must not paint its answer over the newer
        # one's. Only the scan whose token is still the latest is rendered.
        self._scan_token += 1
        token = self._scan_token
        self.corpus_ok = None
        self.corpus_say = None
        # STILL ANSWERED HERE, and still the original sentence. A path that is
        # not a file is one stat, not a read, and it is the state a fresh install
        # opens in - corpus.txt does not exist until the download button has been
        # pressed. Handing that to a worker would trade an instant answer for a
        # round trip, and would make ingest's behaviour on a missing path decide
        # what a first-run window says.
        if not p.is_file():
            self.l_corpus.config(text="That file is not there any more.",
                                 foreground=self.C["bad"])
            self.vocab = 0
            return
        self.l_corpus.config(text="Reading…", foreground=self.C["muted"])

        def work():
            try:
                found = inspect_corpus(p)
            except Exception:
                # ingest refuses by RETURNING a Read, so nothing here is expected
                # to raise; if something does, the panel gets the traceback and
                # the label still gets a sentence. Leaving "Reading…" on screen
                # for ever would be the one outcome worse than either.
                self.q.put(("error", traceback.format_exc()))
                found = {"ok": False, "chars": 0, "vocab": 0, "docs": 0,
                         "sampled": False, "encoding": "", "kind": "refused",
                         "report": None,
                         "say": look.Say(look.REFUTED, "Unreadable",
                                         "This file could not be read at all — "
                                         "the panel below says what went "
                                         "wrong.", "refuted")}
            found.update(token=token, quiet=quiet, name=p.name)
            self.q.put(("scan", found))

        threading.Thread(target=work, daemon=True).start()

    def _show_scan(self, found: dict) -> None:
        """Render a finished scan. Tk thread only — called from the drain loop.

        THE VOCABULARY NOW WINS OVER A LOADED CHECKPOINT'S, where before the
        ordering in __init__ gave the opposite. The scan used to finish before
        _load_saved ran and be overwritten by it; it finishes after, now that it
        is on a worker. That is the better of the two: self.vocab feeds the
        parameter count, the time estimate and the plot's guessing line, and all
        three describe the run about to start, not the model that was loaded to
        write with. TrainWorker sends its own ("vocab", …) the moment training
        begins either way.
        """
        if found.get("token") != self._scan_token:
            return                       # a newer pick has already superseded it
        say = found["say"]
        self.corpus_ok = found["ok"]
        self.corpus_say = say
        self.vocab = found["vocab"]
        note = f"{say.mark} {say.word} — {say.why}"
        if not found["ok"]:
            # No counts, because there are no characters to count. ingest's
            # sentence stands on its own, which is what the contract is for.
            self.l_corpus.config(
                text=note, foreground=self.C[TONE_KEY.get(say.tone, say.tone)])
        else:
            # THE ALPHABET IS JUDGED, NOT JUST COUNTED. "%d different characters"
            # said the same thing at 29 and at 10,000, and those are different
            # situations — see say_alphabet, which knows what fraction of the
            # size you picked goes on naming them.
            alpha = say_alphabet(found["vocab"], SIZES[self.size_name.get()])
            counts = [f"{found['chars']:,} characters",
                      f"{found['vocab']:,} different characters"]
            if not found["sampled"]:
                counts.append(f"{found['docs']:,} document(s)")
            if found["encoding"] and found["encoding"] != "utf-8":
                # Which encoding worked, said only when it was not the obvious
                # one. Last, because it is the answer to a question nobody asked
                # unless the file turned out to be unusual.
                counts.append(f"read as {found['encoding']}")
            lines = [" · ".join(counts), note]
            if found["sampled"]:
                lines[-1] += (f"  (checked the first "
                              f"{SCAN_SAMPLE_BYTES // 1_000_000} MB; the full "
                              f"check runs when training starts)")
            if alpha is not None:
                lines.append(f"{alpha.mark} {alpha.word} — {alpha.why}")
            self.l_corpus.config(
                text="\n".join(lines),
                foreground=self.C[TONE_KEY.get(say.tone, say.tone)])
        # Show the "pure guessing" baseline as soon as a file is chosen, not only
        # once training starts. Before this the chart opened as an empty 1-10 box
        # with nothing to compare anything against, which is the exact problem the
        # baseline exists to solve.
        self.plot.reset(self.plot.total_steps, self.vocab)
        self._apply_preset()
        if not found.get("quiet"):
            if found["ok"]:
                self._write(f"Loaded {found['name']}: {found['chars']:,} "
                            f"characters, read as {found['encoding']}.")
                if found["report"]:
                    self._write(found["report"])
            else:
                self._write(f"Cannot use {found['name']}: {say.why}")

    # ---------------------------------------------------------------- run
    def _start(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            n_layer = int(self.v_layer.get()); n_head = int(self.v_head.get())
            n_embd = int(self.v_embd.get()); block = int(self.v_block.get())
            cfg = {
                "data": self.v_data.get(), "out": self.v_out.get(),
                "n_layer": n_layer, "n_head": n_head, "n_embd": n_embd,
                "block_size": block, "dropout": float(self.v_drop.get()),
                "steps": int(self.v_steps.get()),
                "batch_size": int(self.v_batch.get()),
                "lr": float(self.v_lr.get()),
                "eval_interval": int(self.v_eval.get()),
                "seed": int(self.v_seed.get()),
                "device": "cpu" if self.v_cpu.get() else self.device,
            }
        except ValueError as e:
            messagebox.showerror("A setting is not a number",
                                 f"One of the advanced settings could not be read:\n{e}")
            return
        if n_embd % n_head != 0:
            messagebox.showerror(
                "Those settings do not fit together",
                f"Embed dim {n_embd} must divide evenly by {n_head} heads. "
                f"Pick one of the three sizes above to get a combination that works.")
            return
        if not Path(cfg["data"]).is_file():
            messagebox.showerror("No text to learn from",
                                 f"This file is not there:\n{cfg['data']}")
            return
        # REFUSE RATHER THAN TRAIN ON WHAT DID NOT DECODE. TrainWorker refuses
        # this file too, from its own read, and that is the guard that actually
        # protects the model; this one exists so the answer arrives when the
        # button is pressed rather than after a progress bar has started, and so
        # it arrives in ingest's own words - the same sentence already sitting
        # under the filename. `is False` deliberately, not `not`: None means no
        # scan has landed yet, and that is not a refusal.
        if self.corpus_ok is False and self.corpus_say is not None:
            messagebox.showerror(
                "That text cannot be read",
                f"{self.corpus_say.word}\n\n{self.corpus_say.why}")
            return

        self.log.delete("1.0", "end")
        self.plot.reset(cfg["steps"], self.vocab)
        self.stop_evt.clear()
        self.b_train.config(state="disabled")
        self.b_stop.config(state="normal")
        self.b_gen.config(state="disabled")
        # Explicit fg: _headline colours this label by tone, so a plain text
        # change would leave the last run's green or amber on a neutral word.
        self.l_headline.config(text="Starting…", foreground=self.C["fg"])
        self.worker = TrainWorker(cfg, self.q, self.stop_evt)
        self.worker.start()

    def _stop(self):
        self.stop_evt.set()
        self.b_stop.config(state="disabled")
        self._set_status("Stopping after this step…")

    def _find_trained_models(self) -> list[Path]:
        """Every folder here that holds a usable model, newest first.

        The save folder is an ADVANCED setting, so a beginner who trains once and
        reopens the studio should not have to know its name to get their model
        back. Without this, a model trained into any folder but the default was
        simply unreachable from the main screen.
        """
        found = []
        for p in HERE.iterdir():
            if p.is_dir() and (p / "ckpt.pt").is_file() and (p / "tokenizer.json").is_file():
                found.append(p)
        return sorted(found, key=lambda p: (p / "ckpt.pt").stat().st_mtime, reverse=True)

    def _load_saved(self, quiet: bool = False) -> bool:
        # NEWEST FIRST, not the save folder first. "save to" says where the NEXT
        # run is written; it is not a statement about which model you want back.
        # Preferring it meant that after training a better model into another
        # folder, reopening the studio silently loaded the older one and the
        # user had no way to tell which they were sampling.
        out = self.v_out.get().strip() or "out"
        found = [p.name for p in self._find_trained_models()]
        candidates = found + ([out] if out not in found else [])
        model = None
        for name in candidates:
            try:
                model, tok, cfg = checkpoint.load_checkpoint(name, self.device)
                out = name
                break
            except (FileNotFoundError, ValueError):
                continue
            except Exception:
                if not quiet:
                    messagebox.showerror("Could not load model",
                                         traceback.format_exc())
                return False
        if model is None:
            if not quiet:
                messagebox.showerror(
                    "No model to load",
                    f"No trained model found in '{out}/' or any other folder here.")
            return False
        self.model, self.tok = model, tok
        self.vocab = tok.vocab_size
        self.b_gen.config(state="normal")
        self._write(f"Found a model you trained earlier in '{out}/' "
                    f"({model.num_params():,} numbers, {self.vocab} vocabulary entries). "
                    f"You can press “Write something” straight away.")
        self._set_status("Earlier model loaded — ready to write.")
        return True

    def _generate(self):
        if self.model is None and not self._load_saved(quiet=True):
            out = self.v_out.get().strip() or "out"
            messagebox.showinfo(
                "Nothing trained yet",
                f"There is no trained model yet, and none saved in '{out}/'.\n\n"
                f"Press “Start training” first — even the Quick look setting is "
                f"enough to try this out.")
            self._set_status("Train a model first.")
            return
        _, temp, topk = STYLES[int(self.style_idx.get())]
        tokens = int(self.sample_len.get())

        self.b_gen.config(state="disabled")
        self._set_status("Writing…")

        def work():
            try:
                # checkpoint.sample, not a second copy of the same six lines --
                # the GUI and generate.py sample through one implementation.
                self.q.put(("sample", checkpoint.sample(
                    self.model, self.tok, self.v_prompt.get(), tokens,
                    temperature=temp, top_k=topk, device=self.device)))
            except Exception:
                self.q.put(("error", traceback.format_exc()))

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------ headline
    def _headline(self, train_loss: float, prefix: str = "") -> None:
        """Show how far it has got, from the same number the chart plots.

        The sentences and the 0.95 "still guessing" bar are look.say_progress's
        now; what it adds is a mark, a word and a tone, so the finding above the
        chart is shown the way every other judgement in the window is. It SETS
        the label rather than returning a string, because a Say that is rendered
        in one place cannot leave the colour of the last one behind it.
        """
        say = look.say_progress(train_loss, self.vocab)
        self.l_headline.config(
            text=f"{prefix}{say.mark} {say.word} — {say.why}",
            foreground=self.C[TONE_KEY.get(say.tone, say.tone)])

    # -------------------------------------------------------------- pump
    # WHY THE TOPLEVEL AND NOT self.after(100, self._drain). Misc.after() registers
    # a Tcl command on the widget it is called on and appends the name to THAT
    # widget's _tclCommands. Misc.after_cancel() deletes the command and then
    # removes the name from the widget it is called on. So cancelling through a
    # different widget than the one that scheduled splits the bookkeeping: the Tcl
    # command goes, the stale name stays on the scheduler, and that widget's
    # destroy() later tries to delete a command that is already gone and raises
    # TclError "can't delete Tcl command".
    #
    # That is not hypothetical. t/test_lab_gui.py's tearDown does exactly this --
    # `for cb in root.tk.call("after", "info"): root.after_cancel(cb)` and then
    # root.destroy() -- so a loop scheduled on this frame broke teardown every
    # single run, while lab.py's fourteen loops never did because they all
    # schedule on the root and so cancel consistently. Scheduling on the toplevel
    # is what keeps the register and the cancel on one widget.
    # (Mechanism read in the failing interpreter's own tkinter/__init__.py:
    # Misc.after, _register, after_cancel, deletecommand, 2026-09-21.)
    #
    # The id is still held and cancelled on destroy, for the other case: this page
    # being taken down while the window lives on, where nothing else would stop
    # the loop.
    def _keep_draining(self, ms: int = 100):
        if self.winfo_exists():
            self._drain_after = self.winfo_toplevel().after(ms, self._drain)

    def _stop_draining(self, event=None):
        if event is not None and event.widget is not self:
            return                       # a child being destroyed, not this page
        if self._drain_after is not None:
            try:
                self.winfo_toplevel().after_cancel(self._drain_after)
            except (tk.TclError, KeyError):
                pass                     # already cancelled, or the window is going
            self._drain_after = None

    def _drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self._write(payload)
                elif kind == "scan":
                    self._show_scan(payload)
                elif kind == "vocab":
                    self.vocab = payload
                    self.plot.vocab = payload
                elif kind == "valtrust":
                    self.val_ok = payload
                    self.plot.unseen_ok = payload
                    if not payload:
                        self.l_explain.config(
                            text="The orange line is hidden: your text repeats itself "
                                 "too much for a fair test of unseen material. Judge "
                                 "this run on the blue line, and add more separate "
                                 "files if you want the fair test back.")
                elif kind == "metrics":
                    m = payload
                    self.plot.add(m["step"], m["train"], m["val"])
                    self._headline(m["train"])
                    self._set_status(
                        f"Training… {m['step'] + 1:,} steps done · "
                        f"about {human_time(m['remaining'])} left")
                elif kind == "done":
                    self.model = payload["model"]
                    self.tok = payload["tok"]
                    self.device = payload["device"]
                    self.vocab = payload["vocab"]
                    self.b_train.config(state="normal")
                    self.b_stop.config(state="disabled")
                    self.b_gen.config(state="normal")
                    self._headline(payload["train"], prefix="Done. ")
                    self._set_status(
                        f"Finished in {human_time(payload['elapsed'])}. "
                        f"Press “Write something” to see what it learned.")
                elif kind == "corpus":
                    for line in payload.splitlines():
                        if line.strip():
                            self._write(line.rstrip())
                    self.v_data.set(str(HERE / "corpus.txt"))
                    self._scan_corpus(quiet=True)
                    self._set_status("New text ready — press “Start training”.")
                elif kind == "sample":
                    self._write("\n─── what YOUR model wrote ───\n" + payload + "\n")
                    self.b_gen.config(state="normal")
                    self._set_status("Ready.")
                elif kind == "error":
                    self._write("\nSomething went wrong:\n" + payload)
                    self.b_train.config(state="normal")
                    self.b_stop.config(state="disabled")
                    if self.model is not None:
                        self.b_gen.config(state="normal")
                    self._set_status("Something went wrong — see the panel above.")
        except queue.Empty:
            pass
        self._keep_draining()


def main():
    claim_dpi_awareness()
    root = tk.Tk()
    apply_tk_scaling(root)
    root.title("Train My AI — built from scratch on this computer")
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    Studio(root)
    fit_to_screen(root, want=(1180, 820))
    root.mainloop()


def claim_dpi_awareness() -> None:
    """Tell Windows this process scales itself. Must run BEFORE any Tk root.

    Windows scales unaware apps by stretching their bitmap, so on a 150%-scaled
    display every label came out soft and slightly blurred. Claiming awareness
    here and then telling Tk the real pixel density (apply_tk_scaling) gets crisp
    text at any scale. Wrapped because the call does not exist off Windows and is
    not worth failing over.

    Module level, not inside main(), because main() runs only when this file is
    the program: in the merged window t/lab.py owns the root, so a host that
    wants crisp text on a scaled display calls this before creating it.
    """
    try:
        import ctypes                                    # noqa: PLC0415
        ctypes.windll.shcore.SetProcessDpiAwareness(1)   # per-monitor aware
    except Exception:                                    # noqa: BLE001
        pass


def apply_tk_scaling(widget: tk.Misc) -> float:
    """Point Tk at the display's real pixel density; return the factor in force.

    `tk scaling` is per interpreter and there is exactly one, so this is the
    window owner's call to make and not a page's - which is why Studio does not
    make it even standalone. Idempotent: winfo_fpixels("1i") comes from the
    screen's reported geometry and does not move when the scaling factor does.
    Returns 1.0 if Tk refuses, which is also what it was using.
    """
    root = widget.winfo_toplevel()
    try:
        scale = root.winfo_fpixels("1i") / 72.0
        root.tk.call("tk", "scaling", scale)
    except tk.TclError:
        return 1.0
    return scale


if __name__ == "__main__":
    main()
