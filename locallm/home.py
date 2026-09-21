"""home.py — point it at your own text, get a model. Four steps, no jargon.

WHAT THIS IS FOR. locallm's whole claim is that you can aim it at your own words
on your own computer and get a model out. Today that claim is one tab behind a
seven-prover verification dashboard, so the first thing a stranger sees is a wall
about proof kernels — a thing they did not come for and cannot use. This file is
the front page instead, and it is written for someone who has never heard of a
transformer, a proof kernel or a holdout split. The goal it is measured against:
somebody anywhere boots this off a USB stick, points it at whatever text they
care about, and has a model training — or has a trained one talking back — before
they understand anything about either.

FOUR CARDS, NUMBERED, IN ORDER:

    1  Your text            a big drop target and a Choose button
    2  How big, how long    one slider
    3  Train                one primary button
    4  Try it               a prompt box and the model's reply

WHAT IT DOES NOT DO. It does not train, sample, measure or judge anything itself.
Every number on the page comes from code that already existed: the presets and
the timing arithmetic from studio.py, the corpus checks from data.py and
leakage.py, the training loop from studio.TrainWorker, the chart from
studio.LearningPlot, the sampling from checkpoint.sample, and every word of every
judgement from look.py's Say. This file is layout and wording. That is on purpose:
a second opinion about whether a corpus is safe to train on is a second thing to
keep true.

NOTHING WAS REMOVED, ONLY MOVED. Every setting on studio.py's left column is
still reachable here, behind "More settings" — the eleven fields, force CPU and
the save folder included. Progressive disclosure, which is the same pattern
studio.py's advanced door already uses: "Initially, show users only a few of the
most important options. Offer a larger set of specialized options upon request"
(nngroup.com/articles/progressive-disclosure/, read 2026-09-20).

IT OPENS ON A MACHINE WITH NO TORCH. studio.py imports torch at module scope, so
it is imported here lazily, once, through engine(). With no torch the page still
opens and still explains itself: the cards say plainly which parts cannot work and
why, rather than the window refusing to appear. That is the same reason t/lab.py
imports studio inside build_train.

NOTHING HERE READS A USER'S FILE. ingest.read_any does, and it is the only thing
allowed to: it either decodes a file properly and says which encoding worked, or
it refuses and says why in a sentence. This page renders that answer and gates
the Train button on it. What stood here before was
`read_text(encoding="utf-8", errors="ignore")`, which is the failure that rule
exists to stop — a PDF came back as the fragments that happen to be valid UTF-8
and a UTF-16 file from a Windows Save as box came back nearly empty, both with a
green tick beside them.

Dependencies: tkinter (stdlib) and locallm/look.py. ingest is reached lazily and
its absence is a REFUSAL, not a fallback. torch, studio, data, leakage,
checkpoint and get_corpus are all reached lazily too, and each absence has a
sentence.
"""
from __future__ import annotations

import queue
import sys
import threading
import traceback
from pathlib import Path
from typing import Callable, NamedTuple

import tkinter as tk
from tkinter import filedialog, ttk

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import look  # noqa: E402
from look import MONO, SANS, resolve_fonts  # noqa: E402

# Where a release drops a ready-made model, so "try the one that came with it"
# has something to try before anybody has trained anything. It is a plain
# checkpoint directory — ckpt.pt plus tokenizer.json, exactly what a training run
# writes — so nothing special has to be built to produce one, and nothing here
# behaves differently when it is absent beyond saying so.
INCLUDED = "included-model"

# The hairline is one pixel, and one pixel is not a spacing step: it is the line
# itself, the same width _Card strokes its own edge with. Named so it cannot be
# read as a seventh value on look.SCALE, and so the test that forbids a seventh
# value can tell the two apart.
HAIRLINE = 1


# --------------------------------------------------------------------------
# THE ONE LAZY IMPORT.
#
# studio.py is `import torch` at module scope, and this page has to open on a
# machine that has never installed it — a stranger with a stick has not run
# install.py yet, and the first thing they see must not be a traceback. So the
# import happens once, here, and the failure is kept as a sentence for the cards
# to show. t/lab.py does exactly this inside build_train, for the same reason and
# with the same wording about what still works without it.
# --------------------------------------------------------------------------
_ENGINE: list[tuple[object | None, str]] = []


def engine() -> tuple[object | None, str]:
    """(studio module, "") or (None, why not). Imported at most once per process."""
    if not _ENGINE:
        try:
            import studio                                       # noqa: PLC0415
            _ENGINE.append((studio, ""))
        except Exception as e:                                   # noqa: BLE001
            _ENGINE.append((None, f"{type(e).__name__}: {e}"))
    return _ENGINE[0]


# --------------------------------------------------------------------------
# THE SECOND LAZY IMPORT: THE ONLY THING ALLOWED TO READ A USER'S FILE.
#
# ingest.py owns every read: read_any(path) for one file, read_corpus(paths) for
# several or a folder, can_train_on(path) as the cheap yes/no a picker or a drop
# target can afford to ask before either. All three come back with a look.Say,
# which is the shape this page already renders, so none of the judgement is
# repeated here — the same reason measure_text leaves the corpus verdict to
# look.say_corpus.
#
# WHY LAZY, when ingest needs no torch and would import at module scope fine. The
# same reason as engine(): a module that is missing has to arrive as a sentence on
# a card, not as a traceback before the window exists. The difference is what
# happens next — with no studio this page still explains itself, and with no
# ingest it reads NOTHING AT ALL. There is deliberately no fallback read here,
# because reading the file the other way is the bug being fixed.
# --------------------------------------------------------------------------
_READER: list[tuple[object | None, str]] = []


def reader() -> tuple[object | None, str]:
    """(ingest module, "") or (None, why not). Imported at most once per process."""
    if not _READER:
        try:
            import ingest                                        # noqa: PLC0415
            _READER.append((ingest, ""))
        except Exception as e:                                    # noqa: BLE001
            _READER.append((None, f"{type(e).__name__}: {e}"))
    return _READER[0]


# --------------------------------------------------------------------------
# TYPE: FOUR SIZES, ONE BOLD WEIGHT, AND THE FAMILY IS look.py's.
#
# The families are not chosen here and must not be: look.SANS/look.MONO resolve
# each platform's own UI face against the live interpreter and memoise it, and
# look.py carries the measurement behind that order (a named family that is not
# installed becomes a different family silently, which is an unspecified default
# wearing a decision's clothes). This file only picks sizes.
#
# FOUR, because GNOME's typography guidance says to "make an effort to minimize
# the number of font sizes and weights" and warns that "too many variants, sizes,
# and weights can make text harder to read"
# (developer.gnome.org/hig/guidelines/typography.html, read 2026-09-20). The same
# page sanctions the large one: its Title style is "infrequently used for display
# headings in greeters or assistants ... only ... in conjunction with large
# amounts of white space". A greeter is exactly what this page is, and the white
# space is look.SPACE's top two steps.
#
# The sizes are POINTS, which is what Tk means by a positive font size, so they
# follow the display's own dpi rather than a pixel count that survives one
# screen. studio.py's body text is 9-10 pt; this page is deliberately larger,
# because it is read once by someone who does not yet know what they are looking
# at, not lived in by someone who does.
# --------------------------------------------------------------------------
class _Type(NamedTuple):
    caption: int    # the quiet second line under a control
    body: int       # every sentence the page says
    head: int       # a card's heading, and the numeral beside it
    title: int      # the page's one display heading


TYPE = _Type(caption=10, body=12, head=16, title=24)

# A Say's tone is a ROLE name; a host may hand over a palette that names only the
# aliases. Studio's table and studio's reasoning, unchanged: look.PALETTES holds
# both spellings of each colour, so this is not a translation between colours —
# it is what lets the ALIAS the host overrode win on the one line that goes
# through a role key. `.get(tone, tone)` covers `muted`, which is a tone with no
# alias and a palette key already.
TONE_KEY = {"proved": "ok", "refuted": "bad", "unsettled": "warn"}

# Shown while something is in flight. The fourth mark earns its place here: a Say
# whose claim has not come back yet is not proved, refuted or inapplicable.
_WORKING = look.TIMED_OUT


# --------------------------------------------------------------------------
# GEOMETRY: a card with a corner.
# --------------------------------------------------------------------------
def round_rect(x0: float, y0: float, x1: float, y1: float,
               radius: float) -> tuple[float, ...]:
    """Control points for a rounded rectangle drawn as ONE smoothed polygon.

    ttk has no border-radius, so a 12 px card corner has to be drawn. This is the
    smoothed-polygon recipe from wiki.tcl-lang.org/page/Drawing+rounded+rectangles
    (read 2026-09-20), in Python and with its precondition kept. Why it works, in
    the wiki's own terms: Tk's parabolic spline passes through the MIDPOINT of the
    segment joining two consecutive control points and is tangent there, and two
    collinear segments come out as a straight line between their midpoints. So
    setting the control points back from each corner by TWICE the radius makes
    the curve break at exactly the right place, and the straight sides stay
    straight.

    THE CLAMP IS THE PRECONDITION, not a defensive flourish. A card one row tall
    is a real state of this page — the effort card with its slider hidden is
    about 40 px high, and twice the 12 px card radius is more than that.

    AND THE WIKI'S OWN BOUND IS TOO LOOSE, which took a test to notice. It states
    the restriction as "the radius has to be at most 3/8 the length of the
    shorter side ... or else the line segment will overshoot the curve segments",
    and clamps 2*radius to 0.75 of each side to match. But the control points are
    x0, x0+d, x1-d, x1 with d = 2*radius, so they run backwards as soon as
    d > side/2 — at the wiki's own limit, d = 0.75*side, the top edge is
    0, 0.75w, 0.25w, w, which is a zig-zag rather than a rectangle. Anything
    between radius = side/4 and the wiki's side*3/8 draws that. So the clamp here
    is side/2, which is the real bound: at the limit the two set-backs meet in
    the middle and the shape is a stadium, which is the correct answer for a box
    that short.

    The same wiki page offers a four-ovals-plus-two-rectangles variant. It is not
    used: the reader who benchmarked the two there could not get it to work, and
    it cannot carry an outline, while every card on this page needs BOTH a fill
    shift and a hairline (look.py measures the fill shift alone at 1.10:1, which
    is no difference at all on a dim screen).
    """
    d = 2 * radius
    d = min(d, (x1 - x0) / 2, (y1 - y0) / 2)
    d = max(d, 0.0)
    xa, xb = x0 + d, x1 - d
    ya, yb = y0 + d, y1 - d
    return (x0, y0, xa, y0, xb, y0, x1, y0,
            x1, ya, x1, yb, x1, y1,
            xb, y1, xa, y1, x0, y1,
            x0, yb, x0, ya)


def edge_box(width: int, height: int) -> tuple[int, int, int, int]:
    """The coordinates that put a one-pixel outline ON a widget's own four edges.

    MEASURED on this display 2026-09-20, twice, because the obvious arithmetic is
    wrong twice over. Both mistakes are the same one: a half-pixel coordinate,
    which is what you write when you think of a line as having a centre.

    Scanned pixel by pixel on a 900x120 canvas, hairline #DCD3C2 on card #FBF8F1,
    counting the edge pixels that did NOT come out as the hairline:

        (0.5, 0.5, w-0.5, h-0.5)     bottom and right edges MISSING ENTIRELY.
                                     Tk rasterises a one-pixel line centred at c
                                     onto row ceil(c), so w-0.5 lands one row
                                     past the widget and is clipped. The card
                                     had a seam down two sides and none along
                                     the other two.
        (-0.5, -0.5, w-1.5, h-1.5)   all four edges present at the midpoint, and
                                     72 of 820 bottom pixels and 10 right ones
                                     still missing: a coordinate exactly on .5 is
                                     ambiguous, so the spline's own floating
                                     point decides per segment whether it rounds
                                     up or down and the hairline flickers between
                                     two rows along its length. This is the one
                                     that looks like a rendering fault rather
                                     than a bug, which is why it was measured
                                     rather than eyeballed.
        (0, 0, w-1, h-1)             0 missing on all four edges.

    So: integers. There is no rounding left to get wrong, and the card lands
    exactly on the box the geometry manager gave it.
    """
    return 0, 0, width - 1, height - 1

# --------------------------------------------------------------------------
# THE ONE SLIDER.
#
# Two presets, one control. studio.py asks twice — three radio buttons for how
# big and three more for how long — which is six clicks' worth of screen for a
# choice a beginner makes once and cannot reason about anyway. Here the nine
# combinations are the stops of one slider, so the question becomes "how much am
# I asking for", which is the only form of it a stranger can answer.
#
# ORDERED BY THE WAIT, THEN BY THE SIZE. This is the one ordering that never
# surprises: moving right never makes the wait shorter. It is also the measured
# one — studio derives the step count from the measured ms/step so that each
# length hits its wall-clock target whatever the size, which means the length
# alone decides the minutes and the size decides what you get for them. Ordering
# by size first would have made "Small, fifteen minutes" sit left of "Medium, one
# minute", i.e. moving right could halve the wait, which is what a slider must
# never do.
#
# Nine ordered stops with live text is not the shape GNOME's slider guidance was
# written for — it asks for a range where "the number of potential values is
# high" (developer.gnome.org/hig/patterns/controls/sliders.html, read
# 2026-09-20). Recorded rather than hidden: the other two requirements on that
# page are met exactly, the range being "fixed and ordered" and the label
# changing as the handle moves, and nine named stops are what the operator chose
# over a second column of radio buttons.
# --------------------------------------------------------------------------
class Stop(NamedTuple):
    size: str       # a key of studio.SIZES
    length: str     # a key of studio.LENGTHS


def effort_stops(sizes, lengths) -> tuple[Stop, ...]:
    """Every (size, length) pair, ordered by wall-clock target then by size.

    Both arguments are studio's own preset dicts, and the order INSIDE them is
    the operator's — Small/Medium/Large and Quick look/Normal/Thorough, which is
    ascending in both cases. Python dicts iterate in insertion order, so the
    ordering here is theirs, not a second opinion about which size is bigger.
    """
    return tuple(Stop(size, length) for length in lengths for size in sizes)


def stop_index(stops, size: str, length: str, fallback: int = 0) -> int:
    """Where a named (size, length) sits on the slider; `fallback` if it is gone.

    Used for the opening position, which is studio's own default of Medium +
    Normal. A missing name is a preset that was renamed, and opening at the left
    end is a worse answer than opening at the middle but a much better one than
    raising during __init__.
    """
    try:
        return stops.index(Stop(size, length))
    except ValueError:
        return fallback


def steps_for(target_seconds: float, ms_per_step: float | None,
              normal_seconds: float, untimed_normal: int) -> int:
    """Practice steps for one length, from the measured speed of one size.

    STUDIO'S ARITHMETIC, not a second rule: the timed branch is
    target / (ms/1000) rounded to the nearest hundred with a floor of 200, and
    the untimed branch scales studio.UNTIMED_NORMAL_STEPS in proportion to the
    wall-clock targets. It is written out here because in studio.py it lives
    inside _apply_preset, a method of a widget, and cannot be called without a
    Studio instance and therefore without torch. If it ever becomes a
    module-level function there, delete this one and call it.

    The untimed branch matters more than it looks. It used to hand back a flat
    2000 steps for all three lengths, so picking Thorough over Quick look changed
    the label and nothing else; the proportions do not need a benchmark, only
    turning them into minutes does.
    """
    if ms_per_step:
        return max(200, int(round(target_seconds / (ms_per_step / 1000) / 100) * 100))
    return max(200, int(round(untimed_normal * target_seconds / normal_seconds / 100) * 100))


def say_effort(size: str, blurb: str, params: int, steps: int,
               how_long: str | None, edited: bool = False) -> look.Say:
    """What the slider's position means, in one sentence with no bare number.

    `how_long` is already formatted by studio.human_time, so this function is
    arithmetic-free and testable without torch; None means this computer has
    never been timed.

    THE MARK IS THE HONEST ONE. With a measured time there is a claim and it
    holds, so the tick. Without one a claim was EXPECTED and cannot be made,
    which look.py distinguishes from "nothing went wrong and we do not know": the
    dash in amber, not in muted. Inventing minutes is the one thing this project
    will not do in a "how long will this take" field.
    """
    if edited:
        return look.Say(
            look.NOT_APPLICABLE, "Edited",
            "You changed the settings by hand under “More settings”, so this "
            "slider no longer describes what will run. Move it to go back to a "
            "ready-made choice.", "unsettled")
    if how_long is None:
        return look.Say(
            look.NOT_APPLICABLE, size,
            f"{params:,} numbers to learn, over {steps:,} rounds of practice. "
            f"This computer has not been timed yet, so there is no honest "
            f"estimate of the minutes — run “Check My Computer” once and this "
            f"will say. {blurb}", "unsettled")
    return look.Say(
        look.PROVED, size,
        f"About {how_long} on this machine: {params:,} numbers to learn, over "
        f"{steps:,} rounds of practice. {blurb}", "proved")


# --------------------------------------------------------------------------
# WHAT IS ALREADY ON THE DISK.
# --------------------------------------------------------------------------
def trained_models(folder: Path) -> list[Path]:
    """Every directory in `folder` holding a usable model, newest first.

    BOTH FILES, not one: a ckpt.pt with no tokenizer.json cannot decode what it
    generates, which is checkpoint.checkpoint_exists's rule and the reason it
    exists. Newest by the weights' own mtime, so the model you trained last is
    the one offered back — the save folder is an advanced setting and says where
    the NEXT run goes, which is not a statement about which model you want.

    A directory that cannot be listed (a permission, a vanished stick) is not a
    reason to fail the page, so the walk is quiet about it and the caller's card
    says there is no model.
    """
    try:
        here = list(folder.iterdir())
    except OSError:
        return []
    found = [p for p in here if p.is_dir()
             and (p / "ckpt.pt").is_file() and (p / "tokenizer.json").is_file()]
    return sorted(found, key=lambda p: (p / "ckpt.pt").stat().st_mtime, reverse=True)


def ready_made(folder: Path) -> Path | None:
    """The model that came with this copy, if one did.

    INCLUDED first, then the newest trained one, because "try the model that came
    with it" and "try the model I trained yesterday" are the same wish from the
    outside — something that talks back before anything is understood. Returns
    None when the stick shipped without one and nothing has been trained, which
    is a state with its own sentence rather than a disabled button.
    """
    shipped = folder / INCLUDED
    if (shipped / "ckpt.pt").is_file() and (shipped / "tokenizer.json").is_file():
        return shipped
    models = trained_models(folder)
    return models[0] if models else None


def say_model(where: Path | None, params: int | None = None,
              why_not: str = "") -> look.Say:
    """What to say about the model card 4 would sample from."""
    if why_not:
        return look.Say(look.REFUTED, "Unreadable",
                        f"There is a model in “{where.name}” and it cannot be "
                        f"read — {why_not} — so there is nothing here to talk "
                        f"to yet.", "refuted")
    if where is None:
        return look.Say(
            look.NOT_APPLICABLE, "Nothing yet",
            "No model has been trained on this computer yet, and none came with "
            "this copy. Train one in step 3 — even the quickest setting is "
            "enough to see this work.", "muted")
    count = f"{params:,} numbers it learned" if params else "a model it learned"
    return look.Say(look.PROVED, "Ready",
                    f"Loaded from the “{where.name}” folder, with {count}. Type "
                    f"something below and it will carry on from it.", "proved")


# --------------------------------------------------------------------------
# WHAT IS IN THE TEXT.
#
# The measurement path is studio._scan_corpus's, function for function, and the
# judgement is look.say_corpus's: leakage.scan for whether the same passages sit
# on both sides of the split, data.split_health plus data.split_verdict for
# whether a fair test can be held back at all, and data.documents for how many
# files it came from. None of that is repeated here — what this does is keep the
# calls behind an injected `Tools`, so the page can report the plain facts on a
# machine with no torch instead of showing nothing.
#
# WHY A SAMPLE. leakage.scan costs about 0.9 seconds per megabyte, so the full
# check on a 200 MB corpus does not finish in any time a person will sit through:
# studio measured it and simply hung. The sample is labelled as one on screen and
# the real check still runs over the real split inside TrainWorker.
# --------------------------------------------------------------------------
class Tools(NamedTuple):
    group_split: Callable
    scan: Callable
    split_health: Callable
    split_verdict: Callable
    documents: Callable


def load_tools() -> Tools | None:
    """data.py and leakage.py, or None on a machine that cannot import them.

    data.py imports torch (its Corpus builds tensors), so the fairness checks are
    torch-gated even though none of the three functions used here needs a GPU or
    a model. That is worth knowing and not worth working around from this file:
    the one honest consequence is that the card reports sizes and says the
    repetition check has not run, which is a state look.say_corpus already has a
    sentence for.
    """
    try:
        from data import documents, group_split, split_health, split_verdict  # noqa: PLC0415
        from leakage import scan                                             # noqa: PLC0415
    except Exception:                                            # noqa: BLE001
        return None
    return Tools(group_split, scan, split_health, split_verdict, documents)


# WHICH ENCODING WORKED, in words rather than in codec names.
#
# Silence is right for UTF-8 and only for UTF-8: that is what a person means by a
# text file, so saying it back to them is noise. Anything else changed the answer,
# and being told which one worked is what separates "this file is fine, it just
# came off a different machine" from "this file is not what I thought it was".
#
# UTF-16 EARNS THE LONGEST PHRASE because it is the most ordinary way to end up
# here. Notepad's own Save as list is ANSI, UTF-8, UTF-8 with BOM, UTF-16 LE and
# UTF-16 BE (learn.microsoft.com/en-us/answers/questions/2152989/windows-10-notepad-encoding-options,
# read 2026-09-21), so a UTF-16 text file is not exotic — it is what somebody gets
# by picking the entry next to the one they meant. Decoded as UTF-8 with
# errors="ignore" almost none of it survives, which is the near-empty corpus this
# page used to show a tick beside.
#
# Keys are ingest.Read.encoding with any parenthetical dropped and lowered. An
# encoding nobody wrote a phrase for is still NAMED rather than skipped: not
# having prose ready is no reason to go quiet about which encoding was used.
_ENCODING_WORDS = {
    "utf-16": "UTF-16, one of the five choices in a Windows Save as box",
    "utf-16le": "UTF-16, one of the five choices in a Windows Save as box",
    "utf-16be": "UTF-16, one of the five choices in a Windows Save as box",
    # utf-8-sig is PYTHON'S name for a BOM in front of UTF-8, and it reaches this
    # dictionary as often as utf-16 does, because "UTF-8 with BOM" is a line in
    # the same Notepad Save as list. Without an entry the card said "Read as
    # utf-8-sig (BOM), not plain UTF-8" — measured on the fixture, 2026-09-21 —
    # which breaks the one rule this dictionary exists to keep, from
    # developer.gnome.org/hig/guidelines/writing-style.html (read 2026-09-21):
    # "use words, phrases, and concepts that are familiar to the people who will
    # be using your app, rather than terms from the underlying system".
    "utf-8-sig": "UTF-8 with a byte order mark, the “UTF-8 with BOM” choice in a "
                 "Windows Save as box",
    "utf-32": "UTF-32",
    "cp1252": "cp1252, the single-byte Windows encoding for western Europe",
    "latin-1": "Latin-1, a single-byte encoding older than Unicode",
    "iso-8859-1": "Latin-1, a single-byte encoding older than Unicode",
    "ascii": "plain ASCII",
}


def encoding_note(encoding: str) -> str:
    """One sentence naming the encoding that worked, or "" for plain UTF-8."""
    name = encoding.strip()
    if not name or name.lower() in ("utf-8", "utf8"):
        return ""
    bare = name.split("(")[0].strip().lower()
    return f" Read as {_ENCODING_WORDS.get(bare, name)}, not plain UTF-8."


def text_facts(chars: int, distinct: int, docs: int | None,
               sampled_mb: int | None, read_as: str = "") -> str:
    """The plain facts about a file, in a sentence rather than as a row of numbers."""
    # Both counts take the separator. `distinct` did not, which nobody noticed
    # while the only corpora on this page were Latin ones: a Chinese corpus read
    # "5183 different characters" beside "12,345,678 characters" on the same line.
    parts = [f"{chars:,} characters", f"{distinct:,} different characters"]
    if docs is not None:
        parts.append(f"{docs:,} document{'' if docs == 1 else 's'}")
    facts = ", ".join(parts[:-1]) + f" and {parts[-1]}."
    facts += encoding_note(read_as)
    if sampled_mb is not None:
        facts += (f" Checked the first {sampled_mb} MB of it; the whole thing is "
                  f"checked when training starts.")
    return facts


# --------------------------------------------------------------------------
# HOW MANY DIFFERENT CHARACTERS, AND WHAT THAT COSTS.
#
# NOT IN THE SHARED CONTRACT. ingest.py's contract is read_any, can_train_on,
# read_corpus and Read, and none of them judges an alphabet, so the judgement sits
# here beside the counts it is about. If ingest grows one, delete this and show
# that instead — one judgement in one place is the rule the rest of this file
# follows.
#
# THE COST IS ARITHMETIC AND NOT A FEELING. studio.param_count spends
# vocab * n_embd on the character table, tied to the output head and counted once,
# and the Medium preset (n_embd 256, 4 layers) is 3,159,552 parameters before that
# table. So the table is 25,600 of a 3.19M model at 100 different characters —
# 0.8%, a rounding error — and 1,280,000 of a 4.44M model at 5,000, which is 29%:
# nearly a third of everything it learns spent on knowing the alphabet rather than
# on how the writing goes. The same count is where step 3's chart starts, since
# look.say_progress measures progress against "all vocab characters look equally
# likely", so a wider alphabet is also further to fall before anything reads as
# language.
#
# WHERE THE TWO BOUNDS COME FROM. 200 covers any Latin, Greek or Cyrillic text
# with punctuation and both cases, and is the range the measured presets were
# chosen against. 1,000 is where the table passes 7% of a Medium model and the
# sentence has to change from "worth knowing" to "choose a bigger size" — which
# step 2 can still do, and that timing is the whole reason this is said on the
# card instead of in the training log where studio said it.
#
# INVENTED: searched for a published rule of thumb for character-level vocabulary
# size against model width and found none — the tokenizer literature is about
# subword merges, and this repository's own study is a 1,382-entry byte-level BPE
# (tokenizer-results-2026-09-19.json), a different question. The two bounds are
# ours, and the arithmetic above is what they are answerable to.
# --------------------------------------------------------------------------

#: studio.SIZES["Medium"]["n_embd"] — one row of this many numbers per character.
VOCAB_ROW = 256
#: An alphabet at or under this many characters costs the model nothing worth saying.
VOCAB_PLAIN = 200
#: Above this the alphabet is a real share of the model and the size should change.
VOCAB_WIDE = 1_000


def say_vocab(distinct: int) -> look.Say:
    """What an alphabet costs, while step 2 can still be changed."""
    if distinct <= 0:
        return look.Say(look.NOT_APPLICABLE, "No alphabet",
                        "Nothing has been read yet, so there is no alphabet to "
                        "count.", "muted")
    table = distinct * VOCAB_ROW
    if distinct <= VOCAB_PLAIN:
        return look.Say(
            look.PROVED, "Ordinary alphabet",
            f"{distinct:,} different characters. The model keeps a row of numbers "
            f"for each one — {table:,} of its numbers at the usual size, a "
            f"rounding error — and this is the range the sizes in step 2 were "
            f"measured on.", "proved")
    if distinct <= VOCAB_WIDE:
        return look.Say(
            look.NOT_APPLICABLE, "Wide alphabet",
            f"{distinct:,} different characters, so {table:,} of the model's "
            f"numbers go on the alphabet before it learns anything about how "
            f"your writing goes. It will still train; it has more to get "
            f"through.", "unsettled")
    return look.Say(
        look.NOT_APPLICABLE, "Big alphabet",
        f"{distinct:,} different characters, which is normal for Chinese, Japanese "
        f"or Korean. That is {table:,} numbers spent on the alphabet alone at the "
        f"usual size, against about 3.2 million in the rest of a medium model, "
        f"and that many possibilities to choose between at every step. Pick a "
        f"bigger size in step 2 before training, or expect a long climb.",
        "unsettled")


def say_not_ready(state: str, path: str) -> look.Say | None:
    """Why step 3 cannot start on step 1's text, or None when it can.

    A FUNCTION AND NOT FOUR IFS INSIDE THE BUTTON because this is the guard that
    matters most on the page and it has to be checkable without a window: the
    button being disabled is a courtesy, and this is the thing that actually stops
    a refused file, a half-read one or a folder from reaching the training loop.
    "text" — one file, read properly by ingest — is the only state that proceeds.
    """
    if state == "text":
        return None
    if state == "reading":
        return look.Say(
            _WORKING, "Still reading",
            "Step 1 is still reading that text. The button comes back on by "
            "itself the moment it is ready.", "muted")
    if state == "folder":
        return look.Say(
            look.REFUTED, "One file",
            "Step 1 read that whole folder and can say what is in it, but "
            "training reads one file at a time, so point step 1 at a single file "
            "— or at one that holds the lot.", "refuted")
    return look.Say(
        look.REFUTED, "No text",
        f"Step 1 has not accepted anything to learn from: “{path}” is either not "
        f"there or was refused, and step 1 says which. Choose something there "
        f"first.", "refuted")


def as_say(got: object) -> look.Say:
    """ingest's Say, or a Say saying it did not come back as one.

    _show reads all four fields and turns `tone` into a colour, so a tone that is
    not a palette key raises KeyError — and it would raise it inside the message
    pump, whose only `except` is queue.Empty. One malformed Say would therefore
    stop every later message on this page without printing a word, including the
    ones that report training finishing. The contract says ingest returns a
    look.Say; this is what happens if it ever does not, and it is cheaper than
    trusting it.
    """
    try:
        mark, word, why, tone = got.mark, got.word, got.why, got.tone
        if mark in look.MARKS and tone in look.PALETTES["light"] and str(why).strip():
            return look.Say(mark, str(word), str(why), tone)
    except AttributeError:
        pass
    return look.Say(look.NOT_APPLICABLE, "Not checked",
                    "The part that reads your files came back with something this "
                    "page cannot show, so nothing is claimed about that text "
                    "either way.", "muted")


def measure_text(text: str, sample_bytes: int, tools: Tools | None,
                 read_as: str = "") -> tuple[str, look.Say]:
    """(the facts, the judgement) for one file's contents.

    Precedence is studio's and look.say_corpus's, untouched: the leakage verdict
    decides, a split problem overrides it, and only while the leakage report is
    trustworthy. A check that raises reports "Not checked" rather than falling
    back to a tick, which is the failure this project keeps finding elsewhere — a
    green mark for a check that did not run.
    """
    distinct = len(set(text))
    sampled = len(text) > sample_bytes
    sample = text[:sample_bytes] if sampled else text
    sampled_mb = sample_bytes // 1_000_000 if sampled else None
    if tools is None:
        return (text_facts(len(text), distinct, None, None, read_as),
                look.say_corpus(None))
    docs = None
    say = look.say_corpus(None)
    try:
        tr, va = tools.group_split(sample)
        rep = tools.scan(tr, va, doc_aligned=True)      # group_split: it is
        health = tools.split_health(sample)
        say = look.say_corpus(rep.verdict, rep.trustworthy,
                              tools.split_verdict(health),
                              health["achievable_val_frac"])
        docs = len(tools.documents(sample))
    except Exception:                       # never let the scan block training
        pass
    return text_facts(len(text), distinct, docs, sampled_mb, read_as), say


# --------------------------------------------------------------------------
# THE WIDGETS. Three of them, because a card, a button and a drop target are the
# only shapes on this page that Tk does not already have.
# --------------------------------------------------------------------------
class _Card(tk.Frame):
    """A soft card: a fill shift, a hairline, and a 12 px corner.

    HOW IT IS PUT TOGETHER, and why not more simply. The rounded rectangle is
    drawn on a canvas that is `place`d to fill the frame, so it takes part in no
    geometry negotiation at all; the content lives in a separate frame gridded
    normally, so the card's height comes from its content the way a Frame's
    always does. Gridding straight into the canvas would have left the card's
    height depending on whether Tk's canvas propagates its slaves' request, which
    is not something to find out on a stranger's laptop.

    THE CONTENT IS INSET BY MORE THAN THE RADIUS. SPACE.card is 16 and
    look.RADIUS.card is 12, so the content frame's own square corners sit inside
    the curve and cannot show through it. That is why the inset is not a taste
    decision and why nothing here may be padded with a seventh number.
    """

    def __init__(self, parent, palette: dict, **kw):
        self.C = palette
        super().__init__(parent, bg=palette["paper"], **kw)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._bg = tk.Canvas(self, bg=palette["paper"], highlightthickness=0,
                             borderwidth=0)
        self._bg.place(x=0, y=0, relwidth=1, relheight=1)
        self.body = tk.Frame(self, bg=palette["card"])
        self.body.grid(row=0, column=0, sticky="nsew", padx=look.SPACE.card,
                       pady=look.SPACE.card)
        self.body.columnconfigure(0, weight=1)
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _e=None):
        self._bg.delete("card")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2 or h < 2:
            return
        self._bg.create_polygon(
            round_rect(*edge_box(w, h), look.RADIUS.card),
            smooth=True, fill=self.C["card"], outline=self.C["line"], width=1,
            tags="card")


class _Button(tk.Canvas):
    """A drawn button, so the one primary action can look like one.

    ttk cannot round a corner and a natively drawn ttk theme ignores the colours
    you configure at all — "the user gets what she expects from the theme she has
    chosen for Windows" (wiki.tcl-lang.org/page/Ttk, quoted in studio.py) — which
    is how a warm-paper palette ends up with platform-grey boxes sitting on it.
    Drawn here, in the palette, at look.RADIUS.control.

    EXACTLY ONE PRIMARY BUTTON PER VIEW, which is GNOME's rule and not a
    preference: "Each view should only ever include a single button using either
    the suggested or destructive styles"
    (developer.gnome.org/hig/patterns/controls/buttons.html, read 2026-09-20).
    On this page that one is Train. The same page's pill shape is declined,
    because the radius scale has two values and a third would be a number nobody
    chose.

    THE COLOURS ARE MEASURED. The primary label is the CARD colour on the marking
    green: 5.77:1 in light and 7.12:1 in dark by the WCAG formula, against the
    4.5:1 of SC 1.4.3. It works in both themes without a branch because look's
    green is dark on light paper and light on dark paper. A quiet button is ink on
    card, 15.29 and 12.84. Disabled is muted on card, 5.60 and 5.76 — still
    readable, because a greyed-out label a beginner cannot read is how you get
    somebody clicking at nothing.

    HOVER AND PRESS ARE SHOWN WITH AN OUTLINE, not with a lighter or darker fill.
    A lighter green is a ninth colour, and look.py refuses a ninth colour on a
    screen that says three things. Disabled means insensitive rather than a
    complaint on click, which is the same page's rule: "Make invalid buttons
    insensitive, rather than showing an error message when the user clicks them."
    """

    def __init__(self, parent, palette: dict, text: str, command,
                 primary: bool = False, size: int | None = None):
        self.C = palette
        self.primary = primary
        self.command = command
        self._label = text
        self._enabled = True
        self._hot = False
        self._font = SANS(size or TYPE.body, *(("bold",) if primary else ()))
        super().__init__(parent, bg=palette["card"], highlightthickness=0,
                         borderwidth=0, takefocus=1)
        self._measure()
        for seq, fn in (("<Configure>", self._draw),
                        ("<Enter>", self._enter), ("<Leave>", self._leave),
                        ("<FocusIn>", self._draw), ("<FocusOut>", self._draw),
                        ("<Button-1>", self._press), ("<Return>", self._press),
                        ("<space>", self._press)):
            self.bind(seq, fn)

    def _measure(self):
        """Ask the font how wide the label is, then add padding from the scale.

        A pixel width written down in advance is what does not survive a scaled
        display or a different platform's UI face: Font.measure reports what this
        font actually did on this screen
        (docs.python.org/3/library/tkinter.font.html#tkinter.font.Font.measure),
        which is the same reason studio.py sizes its settings column in
        characters rather than pixels.
        """
        from tkinter import font as tkfont                       # noqa: PLC0415
        try:
            f = tkfont.Font(root=self, font=self._font)
            w, h = f.measure(self._label), f.metrics("linespace")
        except tk.TclError:                  # no interpreter to ask, see look._family
            w, h = 8 * len(self._label), 2 * TYPE.body
        pad = look.SPACE.card if self.primary else look.SPACE.item
        self.configure(width=w + 2 * pad, height=h + 2 * look.SPACE.item)

    def set_text(self, text: str):
        self._label = text
        self._measure()
        self._draw()

    def set_enabled(self, on: bool):
        self._enabled = bool(on)
        self.configure(takefocus=1 if on else 0)
        self._draw()

    def _enter(self, _e=None):
        self._hot = True
        self._draw()

    def _leave(self, _e=None):
        self._hot = False
        self._draw()

    def _press(self, _e=None):
        if self._enabled and self.command:
            self.command()

    def _draw(self, _e=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2 or h < 2:
            return
        if not self._enabled:
            fill, fg = self.C["card"], self.C["muted"]
        elif self.primary:
            fill, fg = self.C["proved"], self.C["card"]
        else:
            fill, fg = self.C["card"], self.C["ink"]
        edge = self.C["line"]
        dash = None
        if self._enabled and self._hot:
            edge = self.C["ink"]
        elif self._enabled and self.focus_get() is self:
            edge, dash = self.C["ink"], (2, 2)
        self.create_polygon(
            round_rect(*edge_box(w, h), look.RADIUS.control),
            smooth=True, fill=fill, outline=edge, width=1,
            **({"dash": dash} if dash else {}))
        self.create_text(w / 2, h / 2, text=self._label, fill=fg, font=self._font)


class _DropTarget(tk.Canvas):
    """The big place to put your text. A click target first, a drop target if it can be.

    A REAL FILE DROP IS NOT IN TK. It needs George Petasis' tkdnd Tcl extension,
    and the Python wrapper's own documentation says drag and drop is enabled by
    using "TkinterDnD.Tk() ... as application main window instead of a regular
    tkinter.Tk() window" (github.com/pmgagne/tkinterdnd2, read 2026-09-20) — a
    root this page does not own, since t/lab.py owns it. MEASURED on this box
    2026-09-20: `import tkinterdnd2` is ModuleNotFoundError and
    `package require tkdnd` answers with an error on Tk 8.6.17.

    So the drop is an ADDITION and the click is the mechanism. Somebody with a
    USB stick must not need a compiled Tcl extension to choose a file, and a big
    dashed rectangle that says "Drop a text file here, or click to choose" works
    whether or not the extension loaded. When it does load, `<<Drop>>` arrives as
    well and the same callback runs; event.data goes through tk.splitlist,
    because several files and a filename with a space in it both come back as a
    Tcl list and str() on that is a filename nobody has.

    NOTHING IS ACCEPTED HERE. A dropped path goes to the same on_file the click
    goes to, which is Home._choose_file, so ingest.can_train_on and then
    ingest.read_any decide in one place whether it is text at all. This widget
    only draws; what it says about a file is set from there through set_lines.
    """

    def __init__(self, parent, palette: dict, on_file, height: int):
        self.C = palette
        self.on_file = on_file
        self._hot = False
        self._lines = ("Drop a text file here", "or click to choose one")
        super().__init__(parent, bg=palette["card"], highlightthickness=0,
                         borderwidth=0, height=height, cursor="hand2")
        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", lambda _e: self._heat(True))
        self.bind("<Leave>", lambda _e: self._heat(False))
        self.bind("<Button-1>", lambda _e: self.on_file(None))
        self.dnd = self._register_drop()

    def _register_drop(self) -> bool:
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD         # noqa: PLC0415
            TkinterDnD._require(self.winfo_toplevel())
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._dropped)
            return True
        except Exception:                                        # noqa: BLE001
            return False

    def _dropped(self, event):
        paths = self.tk.splitlist(event.data)
        if paths:
            self.on_file(paths[0])

    def _heat(self, on: bool):
        self._hot = on
        self._draw()

    def _draw(self, _e=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2 or h < 2:
            return
        self.create_polygon(
            round_rect(*edge_box(w, h), look.RADIUS.control),
            smooth=True, fill=self.C["card"],
            outline=self.C["ink"] if self._hot else self.C["line"],
            width=1, dash=(4, 3))
        first, second = self._lines
        self.create_text(w / 2, h / 2 - look.SPACE.item, text=first,
                         fill=self.C["ink"], font=SANS(TYPE.head))
        self.create_text(w / 2, h / 2 + look.SPACE.item, text=second,
                         fill=self.C["muted"], font=SANS(TYPE.body))

    def set_lines(self, first: str, second: str):
        self._lines = (first, second)
        self._draw()


class _Slider(tk.Canvas):
    """A slider whose handle you can see, drawn rather than themed.

    tk.Scale COLOURS ITS HANDLE WITH ITS OWN BACKGROUND, and its background has
    to be the card it sits on, so on this palette the handle came out card on
    paper: 1.101:1, which look.py already measures and rejects as "a real
    difference on this desk and no difference at all on a dim laptop screen".
    Rendered, the control read as two grey bars with a gap between them and no
    handle at all — on the one control this page is built around. ttk's scale
    would take the colours under 'clam' and ignore them under a natively drawn
    theme, and embedded here the theme belongs to the host, so it is not a fix
    either.

    Drawn: a hairline trough, a tick per stop while there are few enough to
    count, and a graphite handle — ink on card, 15.29:1 light and 12.84:1 dark.
    Keyboard is arrows plus Home and End, because a slider that only takes the
    mouse is a slider half the people cannot use.

    Real-time feedback is the requirement this exists to meet: "Ensure that
    real-time feedback is provided as the slider position is changed, in order to
    enable people to make adjustments"
    (developer.gnome.org/hig/patterns/controls/sliders.html, read 2026-09-20), so
    `command` runs on every movement rather than on release.
    """

    #: Above this many stops a tick each is noise rather than a count.
    COUNTABLE = 12

    def __init__(self, parent, palette: dict, var: tk.IntVar, lo: int, hi: int,
                 command, ground: str = "card", step: int = 1):
        self.C = palette
        self.ground = ground
        self.var, self.lo, self.hi, self.step = var, lo, hi, max(1, step)
        self.command = command
        self._hot = False
        super().__init__(parent, bg=palette[ground], highlightthickness=0,
                         borderwidth=0, height=look.SPACE.page, takefocus=1,
                         cursor="hand2")
        for seq, fn in (("<Configure>", self._draw),
                        ("<Enter>", self._enter), ("<Leave>", self._leave),
                        ("<FocusIn>", self._draw), ("<FocusOut>", self._draw),
                        ("<Button-1>", self._to_pointer),
                        ("<B1-Motion>", self._to_pointer),
                        ("<Left>", lambda _e: self._nudge(-1)),
                        ("<Right>", lambda _e: self._nudge(1)),
                        ("<Home>", lambda _e: self._set(self.lo)),
                        ("<End>", lambda _e: self._set(self.hi))):
            self.bind(seq, fn)

    # The handle's radius, which is also how far the trough is inset from each
    # end so a handle at either stop still lands inside the widget.
    @property
    def _r(self) -> int:
        return look.SPACE.inner

    def _positions(self) -> int:
        return (self.hi - self.lo) // self.step + 1

    def _set(self, value: int) -> str:
        value = max(self.lo, min(self.hi, value))
        if value != self.var.get():
            self.var.set(value)
            if self.command:
                self.command()
        self._draw()
        return "break"

    def _nudge(self, by: int) -> str:
        return self._set(self.var.get() + by * self.step)

    def _to_pointer(self, event) -> str:
        self.focus_set()
        w = self.winfo_width() - 2 * self._r
        if w <= 0:
            return "break"
        frac = min(1.0, max(0.0, (event.x - self._r) / w))
        n = self._positions() - 1
        return self._set(self.lo + round(frac * n) * self.step)

    def _enter(self, _e=None):
        self._hot = True
        self._draw()

    def _leave(self, _e=None):
        self._hot = False
        self._draw()

    def _draw(self, _e=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2 * self._r + 2 or h < 2:
            return
        mid = h // 2
        x0, x1 = self._r, w - self._r
        self.create_line(x0, mid, x1, mid, fill=self.C["line"],
                         width=look.SPACE.tight // 2)
        n = self._positions() - 1
        if n and self._positions() <= self.COUNTABLE:
            for i in range(self._positions()):
                x = x0 + (x1 - x0) * i / n
                self.create_line(x, mid - look.SPACE.tight, x,
                                 mid + look.SPACE.tight, fill=self.C["line"])
        at = (self.var.get() - self.lo) / self.step
        x = x0 + (x1 - x0) * (at / n if n else 0)
        edge = self.C["muted"] if (self._hot or self.focus_get() is self) else self.C["ink"]
        self.create_polygon(
            round_rect(x - self._r, mid - self._r, x + self._r, mid + self._r,
                       look.RADIUS.control),
            smooth=True, fill=self.C["ink"], outline=edge, width=1)


class _Scroller(tk.Frame):
    """A column that can never be taller than the screen.

    Four cards with large type do not fit a 1366x768 laptop, and what runs off
    the bottom is step 4 — the part that shows a stranger the thing works. The
    canvas-plus-inner-frame recipe is studio.py's left column, including the
    scrollbar that appears only when it is needed.

    THE WHEEL DIVISOR IS studio.py's WHEN IT CAN BE ASKED. A delta of 120 is one
    notch on win32 alone, and dividing by it on aqua floors every real event to
    zero, which is a dead wheel rather than a stiff one; studio.wheel_convention
    carries that table and the TIP 474 version split behind it. With no torch
    studio cannot be imported at all, and this page still has to scroll, so the
    fallback moves one unit per event in the event's own direction: exactly right
    on 8.6 aqua and on X11 buttons (which carry no delta), a little slow on
    Windows, and too fast on a Windows precision touchpad. That is the lesser
    failure, and it is only ever reached on a machine where there is nothing to
    train and the page is being read rather than used.

    PER WIDGET, NOT bind_all. The "all" tag holds one script per sequence for the
    whole application, and t/lab.py binds the wheel there for its own step list;
    whichever was built second would replace the other and one of the two areas
    would silently stop scrolling.
    """

    def __init__(self, parent, palette: dict):
        self.C = palette
        super().__init__(parent, bg=palette["paper"])
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, bg=palette["paper"], highlightthickness=0,
                                borderwidth=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.bar = ttk.Scrollbar(self, orient="vertical",
                                 command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.inner = tk.Frame(self.canvas, bg=palette["paper"])
        self._win = self.canvas.create_window((0, 0), window=self.inner,
                                              anchor="nw")
        self.inner.bind("<Configure>", self._fit)
        self.canvas.bind("<Configure>", self._fit)
        self._carry = 0.0
        self._bound = -1
        self._seqs = self._wheel_seqs()
        self._bind_wheel()

    def _wheel_seqs(self):
        studio, _ = engine()
        if studio is not None:
            divisor, buttons = studio.tk_wheel_setup(self.canvas)

            def on_wheel(e):
                units, self._carry = studio.wheel_units(-e.delta, divisor,
                                                        self._carry)
                if units:
                    self.canvas.yview_scroll(units, "units")
                return "break"
        else:
            def on_wheel(e):
                if e.delta:
                    self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
                return "break"
            # Only on a Tk that does not translate X11 buttons 4 and 5 into
            # MouseWheel itself. From 8.7 it does, and script-level buttons 4
            # and 5 mean physical thumb buttons there, so binding them would
            # steal clicks rather than scroll.
            buttons = tk.TkVersion < 8.7

        seqs = [("<MouseWheel>", on_wheel)]
        if buttons:
            seqs += [("<Button-4>", lambda _e: self._step(-1)),
                     ("<Button-5>", lambda _e: self._step(1))]
        return seqs

    def _step(self, units: int) -> str:
        self.canvas.yview_scroll(units, "units")
        return "break"

    def _fit(self, _e=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.itemconfigure(self._win, width=self.canvas.winfo_width())
        if self.inner.winfo_reqheight() > self.canvas.winfo_height():
            self.bar.grid(row=0, column=1, sticky="ns")
        else:
            self.bar.grid_remove()
        self._bind_wheel()

    def _bind_wheel(self):
        tree, stack = [], [self]
        while stack:                          # iterative: a deep column is fine
            w = stack.pop()
            tree.append(w)
            stack.extend(w.winfo_children())
        # Walk every time, bind only when the column grew: _fit runs on every
        # <Configure>, which during a resize drag is dozens a second.
        if len(tree) == self._bound:
            return
        self._bound = len(tree)
        for w in tree:
            for seq, fn in self._seqs:
                w.bind(seq, fn)


# --------------------------------------------------------------------------
# THE PAGE.
# --------------------------------------------------------------------------
class Home(ttk.Frame):
    """locallm's front page: four numbered cards, one primary action.

    Constructed exactly the way t/lab.py constructs Studio — a ttk.Frame taking a
    parent and, embedded, the host's palette — so the shell can host it as a page
    without a second Tk root. Two tk.Tk() roots in one process is undefined
    behaviour rather than untidy: the first mainloop() opens both windows and
    blocks until both close (stackoverflow.com/q/39417091).

    `embedded=True` skips the two calls that would repaint the host: theme_use and
    the toplevel's own background. It does not skip the ttk style database, which
    is process-wide whatever is passed, so every named style below is prefixed
    `Home.` — "." is "the theme root style on which derived styles are based"
    (core.tcl-lang.org/tk/doc/trunk/doc/ttk_style.n), and a page that configures
    it restyles the shell's widgets too.
    """

    def __init__(self, root, embedded: bool = False, palette: dict | None = None):
        self.C = dict(look.PALETTES["dark" if look.system_wants_dark() else "light"])
        if palette:
            # The host's colours win for every key it names; this page keeps the
            # ones it alone has (the plot series, the log surface), because those
            # carry meaning and a shell palette has no equivalent.
            self.C.update(palette)
        self.dark = self.C["bg"] == look.PALETTES["dark"]["bg"]
        self.embedded = embedded
        super().__init__(root, style="Home.TFrame", padding=look.SPACE.page)
        # After super(), so the style database is asked through THIS widget's
        # interpreter rather than through tkinter's implicit default root, which
        # embedded is the shell's and right only by luck. A ttk style name is
        # hierarchical, so "Home.TFrame" already inherits TFrame's layout before
        # this configures it and the widget above cannot be created too early.
        self._style()
        # Resolve both families against THIS interpreter before any widget asks
        # for a font, rather than leaving look._family() to find a default root
        # that, embedded, is the shell's and right only by luck.
        resolve_fonts(self)
        self.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.studio, self.why_no_engine = engine()
        self.tools = load_tools()
        self.q: queue.Queue = queue.Queue()
        self.stop_evt = threading.Event()
        self.worker = None
        # WHAT STEP 1 CURRENTLY CLAIMS, in one word, because three other places
        # have to branch on it: the Train button, _start's own guard, and what the
        # drop target says. "none" nothing chosen, "reading" a read in flight,
        # "text" one file accepted, "folder" a folder accepted, "refused" ingest
        # said no. Only "text" lets training start, and that is the whole point of
        # the field: before this, a refusal left the button live.
        self.text_state = "none"
        #: The path step 1 actually accepted, so a path typed into More settings
        #: cannot reach the training loop without going through ingest first.
        self.text_path = ""
        # Read requests are numbered so a stale answer can be dropped. There is no
        # way to interrupt a thread that is already inside a read — nothing in
        # docs.python.org/3/library/threading.html offers one (read 2026-09-21) —
        # so a second choice does not cancel the first, it supersedes it: the
        # window stays live throughout and the earlier answer is discarded when it
        # arrives. That is weaker than a cancel and is not called one.
        self._read_seq = 0
        self.model = None
        self.tok = None
        self.vocab = 0
        self.model_dir: Path | None = None
        self.more_open = False
        self.edited = False
        self.speeds = self.studio.load_speeds() if self.studio else {}
        self.device = self.studio.pick_device() if self.studio else "cpu"
        self.stops = (effort_stops(self.studio.SIZES, self.studio.LENGTHS)
                      if self.studio else ())

        self.v_data = tk.StringVar(value=str(HERE / "corpus.txt"))
        self.v_prompt = tk.StringVar(value="Once upon a time")
        self.v_effort = tk.IntVar(value=stop_index(self.stops, "Medium", "Normal",
                                                   len(self.stops) // 2))
        self.v_style = tk.IntVar(value=2)

        self._build_title()
        self._build_body()
        self._look_at_text(quiet=True)
        self._offer_existing_model()
        self._drain_after = None
        self.bind("<Destroy>", self._stop_draining, add="+")
        self._keep_draining()

    # ----------------------------------------------------------------- style
    def _style(self):
        """Named styles only, plus the ground when this page owns the window.

        Almost every widget on this page is plain Tk with explicit colours, which
        is what t/lab.py does and what a warm-paper palette needs: a natively
        drawn ttk theme ignores the colours you hand it, so a dark palette under
        'vista' produced light grey boxes with pale text on them. What is left to
        ttk is the frame, the entries and the scrollbar.
        """
        C = self.C
        st = ttk.Style(self)
        if not self.embedded:
            try:
                st.theme_use("clam")        # drawn by Tk, so it honours colours
            except tk.TclError:
                pass
        st.configure("Home.TFrame", background=C["paper"])
        st.configure("Home.TEntry", fieldbackground=C["paper"],
                     foreground=C["ink"], insertcolor=C["ink"],
                     bordercolor=C["line"], lightcolor=C["line"],
                     darkcolor=C["line"])
        st.configure("Home.Vertical.TScrollbar", background=C["card"],
                     troughcolor=C["paper"], bordercolor=C["line"],
                     arrowcolor=C["ink"])

    def _tone(self, tone: str) -> str:
        """A Say's tone is a role name; the alias is what a partial palette names."""
        return self.C[TONE_KEY.get(tone, tone)]

    # ----------------------------------------------------------------- frame
    def _build_title(self):
        head = tk.Frame(self, bg=self.C["paper"])
        head.grid(row=0, column=0, sticky="ew", pady=(0, look.SPACE.group))
        tk.Label(head, bg=self.C["paper"], fg=self.C["ink"],
                 font=SANS(TYPE.title, "bold"), anchor="w",
                 text="Make a model out of your own words").grid(
            row=0, column=0, sticky="w")
        tk.Label(head, bg=self.C["paper"], fg=self.C["muted"],
                 font=SANS(TYPE.body), anchor="w", justify="left",
                 wraplength=760,
                 text="Point this at any text you have — your notes, your "
                      "letters, a book you like — and it builds a model from "
                      "scratch on this computer. Nothing is uploaded, nothing "
                      "is downloaded, and nothing was trained before you "
                      "pressed the button.").grid(
            row=1, column=0, sticky="w", pady=(look.SPACE.inner, 0))
        self._title_wrap = head
        head.bind("<Configure>", self._rewrap)

    def _rewrap(self, event):
        """Track the real width instead of guessing one.

        A hard-coded wraplength is a guess about the window width, and in studio
        it was wrong at the default size: the sentence ran off the right edge
        mid-word. This keeps it right when the window is resized or maximised.
        """
        width = max(320, event.width - look.SPACE.group)
        for child in self._title_wrap.winfo_children():
            if isinstance(child, tk.Label) and int(child.cget("wraplength")):
                child.configure(wraplength=width)
        for label in getattr(self, "_wrapped", ()):
            try:
                label.configure(wraplength=max(280, width - 2 * look.SPACE.card))
            except tk.TclError:
                pass

    def _build_body(self):
        self._wrapped: list[tk.Label] = []
        self.scroll = _Scroller(self, self.C)
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self.scroll.bar.configure(style="Home.Vertical.TScrollbar")
        col = self.scroll.inner
        col.columnconfigure(0, weight=1)
        self.cards: dict[int, _Card] = {}
        self._says: dict[int, tk.Label] = {}
        self._marks: dict[int, tk.Label] = {}
        for i, (n, title) in enumerate(((1, "Your text"),
                                        (2, "How big, how long"),
                                        (3, "Train"),
                                        (4, "Try it"))):
            card = _Card(col, self.C)
            card.grid(row=i, column=0, sticky="ew",
                      pady=(0, look.SPACE.group))
            self.cards[n] = card
            self._card_head(card, n, title)
        self._build_text_card(self.cards[1])
        self._build_effort_card(self.cards[2])
        self._build_train_card(self.cards[3])
        self._build_try_card(self.cards[4])
        self._build_more(col)
        self.status = tk.Label(self, bg=self.C["paper"], fg=self.C["muted"],
                               font=SANS(TYPE.caption), anchor="w")
        self.status.grid(row=2, column=0, sticky="ew", pady=(look.SPACE.item, 0))

    def _card_head(self, card: _Card, n: int, title: str):
        """The numeral, the two-word title, the mark and the one sentence.

        Every card says the same four things in the same places: which step this
        is, what it is called, what the program currently claims about it, and why
        in one sentence. The claim is always a look.Say — never a bare number,
        because a number on its own is the thing this project keeps having to
        translate afterwards.
        """
        head = tk.Frame(card.body, bg=self.C["card"])
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(1, weight=1)
        tk.Label(head, bg=self.C["card"], fg=self.C["muted"],
                 font=SANS(TYPE.head, "bold"), text=str(n)).grid(
            row=0, column=0, padx=(0, look.SPACE.item))
        tk.Label(head, bg=self.C["card"], fg=self.C["ink"], anchor="w",
                 font=SANS(TYPE.head, "bold"), text=title).grid(
            row=0, column=1, sticky="w")
        mark = tk.Label(head, bg=self.C["card"], fg=self.C["muted"],
                        font=SANS(TYPE.body, "bold"), text="")
        mark.grid(row=0, column=2, sticky="e")
        say = tk.Label(card.body, bg=self.C["card"], fg=self.C["muted"],
                       font=SANS(TYPE.body), anchor="w", justify="left",
                       wraplength=640, text="")
        say.grid(row=1, column=0, sticky="ew", pady=(look.SPACE.item,
                                                     look.SPACE.item))
        self._marks[n], self._says[n] = mark, say
        self._wrapped.append(say)

    def _show(self, n: int, say: look.Say, prefix: str = ""):
        colour = self._tone(say.tone)
        self._marks[n].configure(text=f"{say.mark}  {say.word}", fg=colour)
        self._says[n].configure(text=f"{prefix}{say.why}", fg=colour)

    def _hairline(self, parent) -> tk.Frame:
        """A sunken field is the ground showing through the card, edged by a hairline.

        One frame in the hairline colour with HAIRLINE of padding, because a
        tk.Entry's own relief is the platform's 3D border and there is no such
        thing on paper.
        """
        edge = tk.Frame(parent, bg=self.C["line"])
        edge.columnconfigure(0, weight=1)
        return edge

    def _entry(self, parent, var, width: int | None = None) -> tk.Entry:
        e = tk.Entry(parent, textvariable=var, bg=self.C["paper"],
                     fg=self.C["ink"], insertbackground=self.C["ink"],
                     relief="flat", highlightthickness=0, font=SANS(TYPE.body),
                     **({"width": width} if width else {}))
        e.grid(row=0, column=0, sticky="ew", padx=HAIRLINE, pady=HAIRLINE)
        return e

    # ------------------------------------------------------------ 1  text
    def _build_text_card(self, card: _Card):
        body = card.body
        self.drop = _DropTarget(body, self.C, self._choose_file,
                                height=6 * TYPE.head)
        self.drop.grid(row=2, column=0, sticky="ew")
        row = tk.Frame(body, bg=self.C["card"])
        row.grid(row=3, column=0, sticky="ew", pady=(look.SPACE.item, 0))
        _Button(row, self.C, "Choose a file…", lambda: self._choose_file(None)).grid(
            row=0, column=0)
        _Button(row, self.C, "Get text to practise on…", self._download).grid(
            row=0, column=1, padx=(look.SPACE.inner, 0))
        self.l_facts = tk.Label(body, bg=self.C["card"], fg=self.C["muted"],
                                font=SANS(TYPE.caption), anchor="w",
                                justify="left", wraplength=640, text="")
        self.l_facts.grid(row=4, column=0, sticky="ew", pady=(look.SPACE.item, 0))
        self._wrapped.append(self.l_facts)
        # The alphabet's judgement goes UNDER THE COUNTS and not in the card's one
        # Say, because it is about the numbers on the line above it and because
        # that Say is already spoken for by the fairness verdict. It is the one
        # label on this page whose colour changes with what it says, which is why
        # it is a judgement and not another grey fact: an amber line here at the
        # moment step 2 is still open is the difference between a person choosing a
        # bigger model and a person wondering later why the output is noise.
        self.l_vocab = tk.Label(body, bg=self.C["card"], fg=self.C["muted"],
                                font=SANS(TYPE.caption), anchor="w",
                                justify="left", wraplength=640, text="")
        self.l_vocab.grid(row=5, column=0, sticky="ew", pady=(look.SPACE.tight, 0))
        self._wrapped.append(self.l_vocab)

    def _choose_file(self, path: str | None):
        """The picker and the drop both land here, and both get the same check.

        ("All", "*.*") STAYS IN THE PICKER. A text file called .log or .jsonl, or
        with no extension at all, is a file people really have — test_ingest.py's
        red witness is four of them wrongly refused by a set literal, "the whole
        industrial and commercial case silently excluded". What was missing was
        never a narrower filter, it was a check on the way out, so every door stays
        open and _look_at_text decides what came through it. A dropped path arrives
        here too, by the same call, which is what makes "the same check" true by
        construction rather than by two lists staying in step.
        """
        if path is None:
            path = filedialog.askopenfilename(
                title="Pick a text file to learn from",
                filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if path:
            self.v_data.set(path)
            self._look_at_text()

    def _text_not_ready(self, state: str):
        """Step 1 holds nothing training can use, so step 3 cannot be started."""
        self.text_state = state
        self.text_path = ""
        b = getattr(self, "b_train", None)
        if b is not None:
            b.set_enabled(False)

    def _blank_text_card(self):
        for label in (self.l_facts, self.l_vocab):
            label.configure(text="")
        self.vocab = 0

    def _look_at_text(self, quiet: bool = False):
        """Start reading whatever v_data points at, and return immediately.

        NOTHING IS READ ON THIS THREAD ANY MORE. Tcl/Tk is single-threaded, so
        "event handlers must respond quickly, otherwise they will block other
        events from being processed ... any long-running computations should not
        run in an event handler, but are either broken into smaller pieces using
        timers, or run in another thread"
        (docs.python.org/3/library/tkinter.html#threading-model, read 2026-09-21).
        What stood here was a read_text() call in the handler, so a large file
        froze the whole window: no redraw, no progress, and no way to tell a slow
        read from a hung program. The read now goes on a daemon thread and comes
        back through self.q, exactly as this file's download already does.

        MEASURED BOTH WAYS on this machine, 2026-09-21. Old: reading an 88 MB
        mixed Japanese/Latin/Cyrillic file and counting its distinct characters
        held the Tk thread 0.67 s with nothing on screen to say so — and that is
        the cheap half, since measure_text's scan then runs over
        studio.SCAN_SAMPLE_BYTES (2 MB) at the 0.9 s/MB measure_text's own comment
        records, about 1.8 s more, on the same thread. New, against a stand-in
        ingest that takes 2 s to answer: this method hands control back in 3.6 ms,
        and a 50 ms repeating timer kept firing throughout with a longest gap of
        54 ms. A read that takes a minute costs the window 3.6 ms either way.

        THE WORKER TOUCHES THE QUEUE AND NEVER A WIDGET, from the same section:
        "if the Tcl interpreter is not running the event loop ... any tkinter
        calls made from threads other than the one running the Tcl interpreter
        will fail". Every widget call below happens on this thread or in _drain.
        """
        raw = self.v_data.get().strip()
        p = Path(raw) if raw else None
        folder = bool(p and p.is_dir())
        if p is None or not (folder or p.is_file()):
            self.drop.set_lines("Drop a text file here", "or click to choose one")
            self._show(1, look.Say(
                look.NOT_APPLICABLE, "No text yet",
                "Nothing has been chosen to learn from. Any plain text file "
                "will do — the longer the better, and at least a few hundred "
                "thousand characters if you want sentences back.", "muted"))
            self._blank_text_card()
            self._text_not_ready("none")
            self._apply_stop()
            return
        mod, why = reader()
        if mod is None:
            self.drop.set_lines("Cannot read files",
                                "the part that reads them safely is missing")
            self._show(1, look.Say(
                look.REFUTED, "Cannot read",
                f"The part of locallm that reads your files is missing, so that "
                f"text was not read at all rather than read wrongly. What Python "
                f"said: {why}.", "refuted"))
            self._blank_text_card()
            self._text_not_ready("refused")
            self._apply_stop()
            return
        # can_train_on is the cheap half of the contract and this is the place it
        # was written for: an answer fast enough to put on the drop target the
        # instant something lands on it. It decides nothing — read_any decides, and
        # read_any is the only thing allowed to say WHY, so a no here still goes
        # through the same read and comes back with ingest's own sentence instead
        # of one invented on this side. A folder skips it, because the cheap check
        # is about one file and read_corpus is what a folder goes through.
        try:
            welcome = folder or bool(mod.can_train_on(p))
        except Exception:                                        # noqa: BLE001
            welcome = True          # the cheap check is not the authority here
        if folder:
            first = f"Reading the files in “{p.name}”…"
        elif welcome:
            first = f"Reading “{p.name}”…"
        else:
            first = f"“{p.name}” does not look like text…"
        self.drop.set_lines(first, "the window stays usable — click to choose another")
        self._show(1, look.Say(
            _WORKING, "Reading",
            f"Working through “{p.name}” now. Nothing is claimed about it yet, and "
            f"training cannot start until this comes back.", "muted"))
        self._blank_text_card()
        self._text_not_ready("reading")
        self._set_status(f"Reading “{p.name}” — this window is still yours.")
        self._read_seq += 1
        threading.Thread(target=self._read_text,
                         args=(mod, p, folder, self._read_seq, quiet),
                         daemon=True).start()

    def _read_text(self, ingest, p: Path, folder: bool, seq: int, quiet: bool):
        """ingest plus the corpus scan, off the Tk thread. Touches only self.q.

        read_corpus is handed a LIST even for a single folder, because the contract
        names that parameter `paths`. If it also takes a bare path the list costs
        nothing, and if it does not, a one-element list is the reading that cannot
        be wrong.

        The scan runs here too rather than back on the Tk thread. It is the
        expensive half — leakage.scan costs about 0.9 seconds per megabyte, which
        is the measurement behind measure_text's sample in the first place — so
        leaving it behind would have moved the freeze rather than removed it.
        """
        try:
            got = (ingest.read_corpus([p]) if folder else ingest.read_any(p))
            m = {"seq": seq, "path": str(p), "folder": folder, "quiet": quiet,
                 "say": got.say, "accepted": got.text is not None,
                 "facts": "", "distinct": 0}
            if got.text is not None:
                sample = (self.studio.SCAN_SAMPLE_BYTES if self.studio
                          else len(got.text) + 1)
                m["distinct"] = len(set(got.text))
                m["facts"], corpus_say = measure_text(got.text, sample,
                                                      self.tools, got.encoding)
                m["read_say"] = got.say
                # THE CORPUS VERDICT ONLY OUTRANKS THE READ WHEN IT RAN. With no
                # tools measure_text returns look.say_corpus(None) — "Not
                # checked" — and load_tools returns None whenever data.py and
                # leakage.py cannot be imported, which on this machine is always:
                # both of them `import torch` at module scope. MEASURED on the
                # Arabic fixture, 2026-09-21: card 1 showed a grey dash and "The
                # repetition check did not finish, so nothing is claimed about
                # this text either way" over a file ingest had read perfectly,
                # while ingest's own "Read 4,026 characters out of “arabic.txt”"
                # went nowhere — the log it would have gone to is built inside
                # the training card, which needs torch too. A check that could
                # not run is not a stronger claim than a read that did; it is no
                # claim. _text_arrived's precedence rule is unchanged — the
                # stronger claim wins — this only stops a check that never
                # happened from counting as one.
                m["say"] = corpus_say if self.tools is not None else got.say
            self.q.put(("text", m))
        except Exception:
            self.q.put(("read-failed", {"seq": seq, "path": str(p),
                                        "why": traceback.format_exc()}))

    def _text_arrived(self, m: dict):
        """One read's answer, back on the Tk thread.

        PRECEDENCE, which is the only decision in here worth arguing about. On a
        REFUSAL the card shows ingest's Say, because ingest is the only thing that
        knows why a file was refused and the sentence has to be one a person can
        act on. On an ACCEPT the card shows look.say_corpus's verdict, because that
        is the stronger claim about whether training on this text will measure
        anything — and what ingest found out is not thrown away: the encoding goes
        into the facts line beside the counts, and its sentence goes in the log.
        """
        if m["seq"] != self._read_seq:
            return              # superseded by a later choice; this one is stale
        p = Path(m["path"])
        say = as_say(m["say"])
        self._show(1, say)
        if not m["accepted"]:
            self.drop.set_lines(f"“{p.name}” was not taken",
                                "drop another, or click to choose")
            self._blank_text_card()
            self._text_not_ready("refused")
            self._apply_stop()
            self._set_status(f"“{p.name}” was not taken — step 1 says why.")
            self._log(f"Refused {p.name}: {say.why}")
            return
        self.vocab = m["distinct"]
        self.text_state = "folder" if m["folder"] else "text"
        self.text_path = m["path"]
        self.drop.set_lines(p.name, "click to choose a different "
                                    + ("one" if m["folder"] else "file"))
        self.l_facts.configure(text=m["facts"])
        v = say_vocab(m["distinct"])
        self.l_vocab.configure(text=f"{v.mark}  {v.word} — {v.why}",
                               fg=self._tone(v.tone))
        b = getattr(self, "b_train", None)
        if b is not None and not (self.worker is not None and self.worker.is_alive()):
            b.set_enabled(self.text_state == "text")
        self._apply_stop()
        if self.plot is not None:
            # Show the pure-guessing baseline as soon as a file is read, not only
            # once training starts: before this the chart opened as an empty box
            # with nothing to compare anything against, which is the exact
            # problem the baseline exists to solve.
            self.plot.reset(self.plot.total_steps, self.vocab)
        self._set_status(f"“{p.name}” is ready.")
        if not m["quiet"]:
            self._log(f"Loaded {p.name}: {m['facts']}")
            if m.get("read_say") is not None:
                self._log(as_say(m["read_say"]).why)

    def _read_failed(self, m: dict):
        """The read itself raised, which is not the same as ingest refusing."""
        name = Path(m["path"]).name
        if m["seq"] == self._read_seq:
            self._show(1, look.Say(
                look.REFUTED, "Unreadable",
                f"“{name}” could not be read at all, so nothing is claimed about "
                f"it either way. The panel in step 3 has what Python said, which "
                f"is worth keeping if you ask anyone about it.", "refuted"))
            self._blank_text_card()
            self._text_not_ready("refused")
            self._apply_stop()
            self._set_status(f"“{name}” could not be read.")
        self._log("\nReading that text failed:\n" + m["why"])

    def _download(self):
        """Fetch ready-made text, in the words get_corpus.py already uses.

        WHY THIS EXISTS AT ALL. The corpus that shipped with the studio was this
        repository's own Python, and a 3M-parameter character model cannot make
        anything readable out of that however long it trains — which made the
        whole tool look like a harness for something unusable. Which corpus a
        small model wants is a settled question and get_corpus.py holds the
        answer, so every label below is read out of get_corpus.SOURCES rather
        than restated here.
        """
        try:
            import get_corpus                                    # noqa: PLC0415
        except Exception as e:                                    # noqa: BLE001
            self._log(f"Cannot download text: {e}")
            return
        win = tk.Toplevel(self)
        win.title("Get text to practise on")
        win.configure(bg=self.C["paper"])
        win.transient(self.winfo_toplevel())
        win.resizable(False, False)
        choice = tk.StringVar(value="stories")
        mb = tk.IntVar(value=200)
        r = 0
        tk.Label(win, bg=self.C["paper"], fg=self.C["ink"], anchor="w",
                 font=SANS(TYPE.head, "bold"), text="What should it read?").grid(
            row=r, column=0, sticky="w", padx=look.SPACE.card,
            pady=(look.SPACE.card, look.SPACE.item))
        for name in sorted(get_corpus.SOURCES):
            src = get_corpus.SOURCES[name]
            r += 1
            tk.Radiobutton(win, text=name, value=name, variable=choice,
                           bg=self.C["paper"], fg=self.C["ink"],
                           activebackground=self.C["paper"],
                           activeforeground=self.C["ink"],
                           selectcolor=self.C["card"], font=SANS(TYPE.body),
                           highlightthickness=0, anchor="w").grid(
                row=r, column=0, sticky="w", padx=look.SPACE.card)
            r += 1
            tk.Label(win, bg=self.C["paper"], fg=self.C["muted"], anchor="w",
                     justify="left", wraplength=420, font=SANS(TYPE.caption),
                     text=src["best_for"]).grid(
                row=r, column=0, sticky="w",
                padx=(look.SPACE.group, look.SPACE.card),
                pady=(0, look.SPACE.item))
        r += 1
        size_row = tk.Frame(win, bg=self.C["paper"])
        size_row.grid(row=r, column=0, sticky="ew", padx=look.SPACE.card)
        howmuch = tk.Label(size_row, bg=self.C["paper"], fg=self.C["muted"],
                           font=SANS(TYPE.body), text="")
        self._slider(size_row, mb, 20, 600,
                    lambda *_: howmuch.configure(
                        text=f"{int(mb.get())} MB of text"),
                    ground="paper", step=20).grid(
            row=0, column=0, sticky="ew")
        howmuch.grid(row=0, column=1, padx=(look.SPACE.item, 0))
        howmuch.configure(text="200 MB of text")
        size_row.columnconfigure(0, weight=1)
        r += 1
        tk.Label(win, bg=self.C["paper"], fg=self.C["muted"], anchor="w",
                 justify="left", wraplength=420, font=SANS(TYPE.caption),
                 text="Downloaded once and kept, so this is a one-time wait. "
                      "Only plain text is fetched — the model itself is always "
                      "built from scratch on this computer.").grid(
            row=r, column=0, sticky="w", padx=look.SPACE.card,
            pady=look.SPACE.item)
        r += 1
        btns = tk.Frame(win, bg=self.C["paper"])
        btns.grid(row=r, column=0, sticky="e", padx=look.SPACE.card,
                  pady=(0, look.SPACE.card))

        def go():
            src, want = choice.get(), int(mb.get())
            win.destroy()
            self._log(f"Downloading {want} MB of “{src}”. This runs once and is "
                      f"then kept on disk.")
            threading.Thread(target=self._fetch_corpus, args=(get_corpus, src, want),
                             daemon=True).start()

        _Button(btns, self.C, "Download", go).grid(row=0, column=0)
        _Button(btns, self.C, "Cancel", win.destroy).grid(
            row=0, column=1, padx=(look.SPACE.inner, 0))
        win.grab_set()

    def _fetch_corpus(self, get_corpus, src: str, want: int):
        """get_corpus.main() off the UI thread, driven by argv as studio drives it."""
        import contextlib                                        # noqa: PLC0415
        import io                                                # noqa: PLC0415
        buf, argv = io.StringIO(), sys.argv
        try:
            sys.argv = ["get_corpus.py", src, "--mb", str(want),
                        "--out", str(HERE / "corpus.txt")]
            with contextlib.redirect_stdout(buf):
                get_corpus.main()
            self.q.put(("corpus", buf.getvalue()))
        except Exception:
            self.q.put(("error", traceback.format_exc()))
        finally:
            sys.argv = argv

    def _slider(self, parent, var, lo, hi, command, ground: str = "card",
                step: int = 1) -> "_Slider":
        """One way to make a slider, so all three on this page are one control."""
        return _Slider(parent, self.C, var, lo, hi, command, ground=ground,
                       step=step)

    # ---------------------------------------------------------- 2  effort
    def _build_effort_card(self, card: _Card):
        body = card.body
        if not self.stops:
            self._show(2, look.Say(
                look.NOT_APPLICABLE, "Not available",
                "This computer cannot train yet, so there is nothing to choose "
                "between here. Step 3 says what is missing and how to fix it.",
                "unsettled"))
            return
        self.effort = self._slider(body, self.v_effort, 0, len(self.stops) - 1,
                                  lambda *_: self._apply_stop())
        self.effort.grid(row=2, column=0, sticky="ew")
        ends = tk.Frame(body, bg=self.C["card"])
        ends.grid(row=3, column=0, sticky="ew")
        ends.columnconfigure(1, weight=1)
        # Marking the ends is the third of GNOME's three slider rules: "it is
        # helpful to mark significant values along the length of the slider with
        # text or tick marks".
        for col, (text, anchor) in enumerate((("quickest", "w"),
                                              ("", "center"),
                                              ("best it can do", "e"))):
            tk.Label(ends, bg=self.C["card"], fg=self.C["muted"], text=text,
                     font=SANS(TYPE.caption), anchor=anchor).grid(
                row=0, column=col, sticky="ew")

    def _stop(self) -> Stop | None:
        if not self.stops:
            return None
        return self.stops[max(0, min(int(self.v_effort.get()), len(self.stops) - 1))]

    def _plan(self) -> dict | None:
        """Everything the slider's position implies, as one dict.

        The presets are the source of truth and the fields under More settings
        are written FROM here, one direction only, so the two can never silently
        disagree — which is studio's rule and the reason its advanced panel is
        safe to leave open.
        """
        stop = self._stop()
        if stop is None or self.studio is None:
            return None
        s = self.studio
        size = dict(s.SIZES[stop.size])
        target = s.LENGTHS[stop.length]["seconds"]
        device = "cpu" if self.v_cpu.get() else self.device
        ms = self.speeds.get(f"{device}/{size['key']}")
        steps = steps_for(target, ms, s.LENGTHS["Normal"]["seconds"],
                          s.UNTIMED_NORMAL_STEPS)
        return {
            "stop": stop, "size": size, "steps": steps, "device": device,
            "seconds": steps * ms / 1000 if ms else None,
            "blurb": s.SIZES[stop.size]["blurb"],
            "params": s.param_count(max(self.vocab, 1), size["block_size"],
                                    size["n_layer"], size["n_head"],
                                    size["n_embd"]),
        }

    def _apply_stop(self):
        plan = self._plan()
        if plan is None:
            return
        s = self.studio
        self.edited = False
        # The traces below fire while the fields are still the PREVIOUS stop's,
        # so without this guard moving the slider marks its own move as a hand
        # edit. studio.py survives the same race only because _apply_preset
        # happens to rewrite the label afterwards, which leaves its flag wrong.
        self._applying = True
        for key, var in (("n_layer", self.v_layer), ("n_head", self.v_head),
                         ("n_embd", self.v_embd), ("block_size", self.v_block),
                         ("batch_size", self.v_batch)):
            var.set(str(plan["size"][key]))
        self.v_lr.set(f"{s.auto_lr(plan['size']['n_embd']):.2g}")
        self.v_steps.set(str(plan["steps"]))
        self.v_eval.set(str(max(10, plan["steps"] // 25)))
        self._applying = False
        self._preset = self._field_snapshot()
        how_long = (s.human_time(plan["seconds"]) if plan["seconds"] is not None
                    else None)
        self._show(2, say_effort(plan["stop"].size, plan["blurb"],
                                 plan["params"], plan["steps"], how_long))

    def _field_snapshot(self) -> dict:
        return {k: v.get() for k, v in (("layers", self.v_layer),
                                        ("heads", self.v_head),
                                        ("embd", self.v_embd),
                                        ("block", self.v_block),
                                        ("steps", self.v_steps),
                                        ("batch", self.v_batch))}

    def _note_edited(self, *_):
        """A hand edit that disagrees with the slider relabels the slider.

        The alternative is a page that shows "Small, about one minute" while
        running something else entirely, which is the disagreement studio's
        one-direction rule exists to prevent.
        """
        if getattr(self, "_applying", False) or self.edited:
            return
        if not getattr(self, "_preset", None):
            return
        if self._field_snapshot() != self._preset:
            self.edited = True
            self._show(2, say_effort("Custom", "", 0, 0, None, edited=True))

    # ----------------------------------------------------------- 3  train
    def _build_train_card(self, card: _Card):
        body = card.body
        self.plot = None
        if self.studio is None:
            self._show(3, look.Say(
                look.NOT_APPLICABLE, "Needs one install",
                "Training needs PyTorch, the library locallm learns with, and it "
                "is not installed for this Python yet. Run install.py once (or "
                "“INSTALL.bat” on Windows) and this page can train. Everything "
                "else here still works.", "unsettled"))
            tk.Label(body, bg=self.C["card"], fg=self.C["muted"], anchor="w",
                     justify="left", wraplength=640, font=SANS(TYPE.caption),
                     text=f"What Python said: {self.why_no_engine}").grid(
                row=2, column=0, sticky="ew")
            return
        row = tk.Frame(body, bg=self.C["card"])
        row.grid(row=2, column=0, sticky="ew")
        self.b_train = _Button(row, self.C, "Start training", self._start,
                               primary=True, size=TYPE.head)
        self.b_train.grid(row=0, column=0)
        self.b_stop = _Button(row, self.C, "Stop", self._stop_training)
        self.b_stop.grid(row=0, column=1, padx=(look.SPACE.item, 0))
        self.b_stop.set_enabled(False)

        # studio.LearningPlot unchanged, including its height: its y axis is
        # exp(loss) — how many characters the model is still choosing between
        # for each next one — which is the one number on either page a person can
        # say out loud, and it is already the best data-simplification here.
        self.plot = self.studio.LearningPlot(body, self.C, height=190)
        self.plot.grid(row=3, column=0, sticky="ew", pady=(look.SPACE.item, 0))
        self.plot.reset(1, self.vocab)

        logframe = tk.Frame(body, bg=self.C["line"])
        logframe.grid(row=4, column=0, sticky="ew", pady=(look.SPACE.item, 0))
        logframe.columnconfigure(0, weight=1)
        self.logbox = tk.Text(logframe, height=6, bg=self.C["log_bg"],
                              fg=self.C["log_fg"], insertbackground=self.C["log_fg"],
                              font=MONO(TYPE.caption), wrap="word", relief="flat",
                              highlightthickness=0)
        self.logbox.grid(row=0, column=0, sticky="ew", padx=HAIRLINE,
                         pady=HAIRLINE)
        self._show(3, look.Say(
            look.NOT_APPLICABLE, "Not started",
            "Nothing has been trained yet. Press Start training and this will "
            "fill in — the chart shows how many characters it is still choosing "
            "between for each next one, which starts at the size of your "
            "alphabet and falls as it learns.", "muted"))

    def _log(self, msg: str):
        box = getattr(self, "logbox", None)
        if box is None:
            return
        box.insert("end", msg + "\n")
        box.see("end")

    def _start(self):
        if self.worker is not None and self.worker.is_alive():
            return
        plan = self._plan()
        if plan is None:
            return
        try:
            cfg = {
                "data": self.v_data.get(), "out": self.v_out.get().strip() or "out_gui",
                "n_layer": int(self.v_layer.get()), "n_head": int(self.v_head.get()),
                "n_embd": int(self.v_embd.get()), "block_size": int(self.v_block.get()),
                "dropout": float(self.v_drop.get()), "steps": int(self.v_steps.get()),
                "batch_size": int(self.v_batch.get()), "lr": float(self.v_lr.get()),
                "eval_interval": int(self.v_eval.get()), "seed": int(self.v_seed.get()),
                "device": plan["device"],
            }
        except ValueError as e:
            # Said on the card, not in a message box. A modal that appears over a
            # page whose whole job is to explain itself is one more thing to
            # dismiss before reading the sentence that was already there.
            self._show(3, look.Say(look.REFUTED, "A setting is not a number",
                                   f"One of the fields under More settings could "
                                   f"not be read: {e}", "refuted"))
            return
        if cfg["n_embd"] % cfg["n_head"]:
            self._show(3, look.Say(
                look.REFUTED, "Those do not fit",
                f"Embed dim {cfg['n_embd']} has to divide evenly by "
                f"{cfg['n_head']} heads. Move the slider to get back to a "
                f"combination that works.", "refuted"))
            return
        # STEP 1 IS THE GATE, not a path check. `is_file()` was the whole of the
        # old guard and it says nothing about whether the file is text: the file
        # that started this work was a real file on disk and a PDF. What is
        # checked here is what step 1 ACCEPTED, which is also why the button is
        # disabled in every other state — this is the half that a path typed into
        # More settings goes past, since nothing reads that field on the way here.
        #
        # BOTH SIDES GO THROUGH Path() FIRST, because text_path is str(Path(...))
        # and this field is whatever was typed into it. Compared raw, " corpus.txt "
        # never equals "corpus.txt", so pressing the button would have read the
        # file, accepted it, and asked to be pressed again — for ever.
        want = cfg["data"].strip()
        if (str(Path(want)) if want else "") != self.text_path:
            self.v_data.set(want)
            self._look_at_text()
            self._show(3, look.Say(
                _WORKING, "Checking first",
                "That text has not been read yet. Step 1 is looking at it now — "
                "press Start training again once it says it is ready.", "muted"))
            return
        stop = say_not_ready(self.text_state, cfg["data"])
        if stop is not None:
            self._show(3, stop)
            return
        # The training loop is handed the path step 1 READ, not the text of the
        # field, so the two cannot be different strings for the same file.
        cfg["data"] = self.text_path
        self.logbox.delete("1.0", "end")
        self.plot.reset(cfg["steps"], self.vocab)
        self.stop_evt.clear()
        self.b_train.set_enabled(False)
        self.b_stop.set_enabled(True)
        self._show(3, look.Say(_WORKING, "Starting",
                               "Building a brand-new model out of random "
                               "numbers. Nothing is being downloaded.", "muted"))
        # studio.TrainWorker unchanged: the loop, the leakage check over the real
        # split, the baseline comparison and the run log all belong to it.
        self.worker = self.studio.TrainWorker(cfg, self.q, self.stop_evt)
        self.worker.start()

    def _stop_training(self):
        self.stop_evt.set()
        self.b_stop.set_enabled(False)
        self._set_status("Stopping after this step — what it has learned is kept.")

    # ------------------------------------------------------------- 4  try
    def _build_try_card(self, card: _Card):
        body = card.body
        field = self._hairline(body)
        field.grid(row=2, column=0, sticky="ew")
        self._entry(field, self.v_prompt)

        row = tk.Frame(body, bg=self.C["card"])
        row.grid(row=3, column=0, sticky="ew", pady=(look.SPACE.item, 0))
        self.b_write = _Button(row, self.C, "Write something", self._write_something)
        self.b_write.grid(row=0, column=0)
        self.b_write.set_enabled(False)
        # BOTH DOORS, because a stranger with a stick should get something
        # working before they understand anything. One of these leads back to
        # step 3; the other picks up whatever model is already on the disk,
        # shipped or trained last week, and needs no waiting at all.
        _Button(row, self.C, "Train your own", self._goto_train).grid(
            row=0, column=1, padx=(look.SPACE.inner, 0))
        self.b_ready = _Button(row, self.C, "Try the model that came with it",
                               self._use_ready_made)
        self.b_ready.grid(row=0, column=2, padx=(look.SPACE.inner, 0))

        if self.studio is not None:
            styles = tk.Frame(body, bg=self.C["card"])
            styles.grid(row=4, column=0, sticky="ew", pady=(look.SPACE.item, 0))
            styles.columnconfigure(0, weight=1)
            self.l_style = tk.Label(styles, bg=self.C["card"], fg=self.C["muted"],
                                    font=SANS(TYPE.caption), anchor="w")
            self._slider(styles, self.v_style, 0, len(self.studio.STYLES) - 1,
                        lambda *_: self._style_label()).grid(
                row=0, column=0, sticky="ew")
            self.l_style.grid(row=1, column=0, sticky="w")
            self._style_label()

        out = self._hairline(body)
        out.grid(row=5, column=0, sticky="ew", pady=(look.SPACE.item, 0))
        self.reply = tk.Text(out, height=8, bg=self.C["log_bg"],
                             fg=self.C["log_fg"], insertbackground=self.C["log_fg"],
                             font=MONO(TYPE.body), wrap="word", relief="flat",
                             highlightthickness=0)
        self.reply.grid(row=0, column=0, sticky="ew", padx=HAIRLINE,
                        pady=HAIRLINE)

    def _style_label(self):
        name = self.studio.STYLES[int(self.v_style.get())][0]
        note = self.studio.STYLE_NOTES.get(name, "")
        self.l_style.configure(text=f"{name} — {note}")

    def _goto_train(self):
        card = self.cards[3]
        self.scroll.canvas.yview_moveto(
            max(0.0, card.winfo_y() / max(self.scroll.inner.winfo_height(), 1)))
        if getattr(self, "b_train", None) is not None:
            self.b_train.focus_set()

    def _offer_existing_model(self):
        """Load whatever is already on the disk, so step 4 can work immediately."""
        where = ready_made(HERE)
        if where is None:
            self.b_ready.set_enabled(False)
            self._show(4, say_model(None))
            return
        if self.studio is None:
            self._show(4, look.Say(
                look.NOT_APPLICABLE, "Cannot open it",
                f"There is a trained model in “{where.name}”, but reading it "
                f"needs PyTorch, which is not installed for this Python yet.",
                "unsettled"))
            self.b_ready.set_enabled(False)
            return
        self._show(4, look.Say(
            look.NOT_APPLICABLE, "One is waiting",
            f"There is already a trained model in the “{where.name}” folder. "
            f"Press “Try the model that came with it” and you can talk to it "
            f"now, without training anything.", "muted"))

    def _use_ready_made(self):
        where = ready_made(HERE)
        if where is None or self.studio is None:
            return
        try:
            import checkpoint                                    # noqa: PLC0415
            model, tok, _cfg = checkpoint.load_checkpoint(where, self.device)
        except Exception as e:                                   # noqa: BLE001
            self._show(4, say_model(where, why_not=f"{type(e).__name__}: {e}"))
            return
        self.model, self.tok, self.model_dir = model, tok, where
        self.vocab = tok.vocab_size
        self.b_write.set_enabled(True)
        self._show(4, say_model(where, model.num_params()))

    def _write_something(self):
        if self.model is None:
            self._show(4, say_model(None))
            return
        _, temp, topk = self.studio.STYLES[int(self.v_style.get())]
        try:
            tokens = max(1, int(self.v_tokens.get()))
        except ValueError:
            self._show(4, look.Say(
                look.REFUTED, "Not a number",
                "“How much text to write”, under More settings, is not a "
                "number.", "refuted"))
            self.b_write.set_enabled(True)
            return
        self.b_write.set_enabled(False)
        self._show(4, look.Say(_WORKING, "Writing",
                               "It is carrying on from what you typed.", "muted"))

        def work():
            try:
                # checkpoint.sample, which is what studio._generate calls and
                # what generate.py calls: one implementation, so the GUI and the
                # command line cannot drift apart about what sampling means.
                import checkpoint                                # noqa: PLC0415
                self.q.put(("sample", checkpoint.sample(
                    self.model, self.tok, self.v_prompt.get(), tokens,
                    temperature=temp, top_k=topk, device=self.device)))
            except Exception:
                self.q.put(("error", traceback.format_exc()))

        threading.Thread(target=work, daemon=True).start()

    # --------------------------------------------------------- more settings
    def _build_more(self, col):
        """Every knob studio.py's left column has, behind one shut door.

        NOTHING WAS REMOVED. The eleven fields, force CPU and the save folder are
        the same eleven, in the same order, meaning the same things; what changed
        is that they start shut, because "the very fact that something appears on
        the initial display tells users that it's important"
        (nngroup.com/articles/progressive-disclosure/). A field here that
        disagrees with the slider relabels the slider rather than silently
        overriding it.
        """
        self.v_layer = tk.StringVar(value="4")
        self.v_head = tk.StringVar(value="4")
        self.v_embd = tk.StringVar(value="256")
        self.v_block = tk.StringVar(value="128")
        self.v_drop = tk.StringVar(value="0.1")
        self.v_steps = tk.StringVar(value="2000")
        self.v_batch = tk.StringVar(value="32")
        # studio's own opening values, and _apply_stop overwrites every one of
        # them from the presets the moment a slider position is applied. The
        # learn rate is the only one written as a literal: it is auto_lr(256) to
        # two figures, and auto_lr lives behind the torch import, so on a machine
        # that cannot train it would otherwise be blank — and on one that can, it
        # is replaced before the field is ever read.
        self.v_lr = tk.StringVar(value="0.0011")
        self.v_eval = tk.StringVar(value="100")
        self.v_seed = tk.StringVar(value="1337")
        self.v_out = tk.StringVar(value="out_gui")
        self.v_tokens = tk.StringVar(value="400")
        self.v_cpu = tk.BooleanVar(value=False)

        self.b_more = _Button(col, self.C, "More settings ▸", self._toggle_more)
        self.b_more.grid(row=90, column=0, sticky="w")
        self.more = _Card(col, self.C)
        rows = [("your text", self.v_data), ("layers", self.v_layer),
                ("heads", self.v_head), ("embed dim", self.v_embd),
                ("context", self.v_block), ("dropout", self.v_drop),
                ("steps", self.v_steps), ("batch size", self.v_batch),
                ("learn rate", self.v_lr), ("eval every", self.v_eval),
                ("seed", self.v_seed), ("save to", self.v_out),
                ("how much text to write", self.v_tokens)]
        grid = self.more.body
        grid.columnconfigure(1, weight=1)
        tk.Label(grid, bg=self.C["card"], fg=self.C["muted"], anchor="w",
                 justify="left", wraplength=640, font=SANS(TYPE.caption),
                 text="These are the same settings the older screen had, "
                      "unchanged. Nothing here has to be touched; changing one "
                      "tells the slider above that it no longer describes what "
                      "will run.").grid(row=0, column=0, columnspan=2, sticky="ew",
                                        pady=(0, look.SPACE.item))
        for i, (label, var) in enumerate(rows, start=1):
            tk.Label(grid, bg=self.C["card"], fg=self.C["ink"], text=label,
                     font=SANS(TYPE.body), anchor="w").grid(
                row=i, column=0, sticky="w", padx=(0, look.SPACE.item),
                pady=look.SPACE.tight)
            field = self._hairline(grid)
            field.grid(row=i, column=1, sticky="ew", pady=look.SPACE.tight)
            entry = self._entry(field, var)
            if var is self.v_data:
                # A typed path has not been through ingest, and this is the one
                # field on the page that can name a file without the picker. It is
                # checked when the field is LEFT or Enter is pressed, not on every
                # keystroke: a trace_add here would start a read per character
                # typed, and the whole point of the rewrite is that a read is
                # expensive enough to keep off this thread.
                for seq in ("<Return>", "<FocusOut>"):
                    entry.bind(seq, lambda _e: self._look_at_text())
        tk.Checkbutton(grid, text="force the processor (ignore the graphics card)",
                       variable=self.v_cpu, command=self._apply_stop,
                       bg=self.C["card"], fg=self.C["ink"],
                       activebackground=self.C["card"],
                       activeforeground=self.C["ink"],
                       selectcolor=self.C["paper"], font=SANS(TYPE.body),
                       highlightthickness=0, anchor="w").grid(
            row=len(rows) + 1, column=0, columnspan=2, sticky="w",
            pady=(look.SPACE.item, 0))
        for v in (self.v_layer, self.v_head, self.v_embd, self.v_block,
                  self.v_steps, self.v_batch):
            v.trace_add("write", self._note_edited)
        self._preset: dict = {}

    def _toggle_more(self):
        self.more_open = not self.more_open
        if self.more_open:
            self.more.grid(row=91, column=0, sticky="ew",
                           pady=(look.SPACE.item, 0))
            self.b_more.set_text("More settings ▾")
        else:
            self.more.grid_remove()
            self.b_more.set_text("More settings ▸")

    # ---------------------------------------------------------------- pump
    def _set_status(self, msg: str):
        self.status.configure(text=msg)

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
        """One message pump for the training thread and the sampling thread.

        Every kind TrainWorker puts on the queue is handled here, because a
        message with no arm is a run whose warning nobody sees: `valtrust` in
        particular is how the chart learns that the orange line means nothing on
        this corpus.
        """
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "vocab":
                    self.vocab = payload
                    if self.plot is not None:
                        self.plot.vocab = payload
                elif kind == "valtrust":
                    if self.plot is not None:
                        self.plot.unseen_ok = payload
                elif kind == "metrics":
                    m = payload
                    if self.plot is not None:
                        self.plot.add(m["step"], m["train"], m["val"])
                    self._show(3, look.say_progress(m["train"], self.vocab))
                    self._set_status(
                        f"Training… {m['step'] + 1:,} rounds done, about "
                        f"{self.studio.human_time(m['remaining'])} left.")
                elif kind == "done":
                    self.model = payload["model"]
                    self.tok = payload["tok"]
                    self.device = payload["device"]
                    self.vocab = payload["vocab"]
                    self.model_dir = Path(self.v_out.get().strip() or "out_gui")
                    self.b_train.set_enabled(True)
                    self.b_stop.set_enabled(False)
                    self.b_write.set_enabled(True)
                    self._show(3, look.say_progress(payload["train"], self.vocab),
                               prefix="Finished. ")
                    self._show(4, say_model(self.model_dir,
                                            payload["model"].num_params()))
                    self._set_status(
                        f"Finished in "
                        f"{self.studio.human_time(payload['elapsed'])}. Step 4 "
                        f"can talk to it now.")
                elif kind == "text":
                    self._text_arrived(payload)
                elif kind == "read-failed":
                    self._read_failed(payload)
                elif kind == "corpus":
                    for line in payload.splitlines():
                        if line.strip():
                            self._log(line.rstrip())
                    self.v_data.set(str(HERE / "corpus.txt"))
                    self._look_at_text(quiet=True)
                    self._set_status("New text ready — step 3 can train on it.")
                elif kind == "sample":
                    self.reply.delete("1.0", "end")
                    self.reply.insert("end", payload)
                    self.b_write.set_enabled(True)
                    self._show(4, say_model(
                        self.model_dir,
                        self.model.num_params() if self.model is not None else None))
                elif kind == "error":
                    self._log("\nSomething went wrong:\n" + payload)
                    if getattr(self, "b_train", None) is not None:
                        self.b_train.set_enabled(True)
                        self.b_stop.set_enabled(False)
                    self._show(3, look.Say(
                        look.REFUTED, "Stopped",
                        "Training stopped with an error. The panel below has "
                        "what Python said, which is worth keeping if you ask "
                        "anyone about it.", "refuted"))
        except queue.Empty:
            pass
        self._keep_draining()


def main():
    """Open this page as its own window, for a stick with nothing else on it."""
    studio, _ = engine()
    if studio is not None:
        studio.claim_dpi_awareness()
    root = tk.Tk()
    if studio is not None:
        studio.apply_tk_scaling(root)
    root.title("locallm — make a model out of your own words")
    root.configure(bg=look.palette()["paper"])
    Home(root)
    if studio is not None:
        studio.fit_to_screen(root, want=(960, 880))
    root.mainloop()


if __name__ == "__main__":
    main()
