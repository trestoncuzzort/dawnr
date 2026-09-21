"""look.py — the one design system both halves of the window import.

The window is one window: t/lab.py is the shell and locallm/studio.py is the
training page embedded inside it. Until now each half kept its own copy of the
fonts, the colours and the marks, and the copies drifted — the shell resolved to
Inter and the embedded page to Cantarell in the same frame, the shell's palette
is cool grey and the page's was a third set of literals, and t/lab.py holds a
second copy of the two font lists with a note saying the two must stay
IDENTICAL. A rule that says "keep these two lists the same" is a rule with no
enforcement; one list has enforcement for free. This file is that list, for
every visual decision the two halves share.

WHAT IS HERE: the palette (both themes), the spacing scale, the two corner
radii, the font lists with their memoised resolution, the four marks, and the
`Say` shape that every judgement the program makes comes back in. Nothing here
draws anything, and nothing here decides anything about training.

IT MUST STAY IMPORTABLE IN A BARE PROCESS. No torch, no studio, and tkinter only
inside the one function that has to ask Tk a question — so the palette and the
contrast test that guards it run on a machine with no display and no torch,
which is where this file's own tests run.
"""
from __future__ import annotations

import math
import os
import sys
import subprocess
import re
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:                       # tkinter is imported lazily, see _family
    import tkinter as tk


# --------------------------------------------------------------------------
# THE PALETTE.
#
# Sampled from marked-up paper: warm engineering quadrille for the ground,
# pencil graphite for text, and the three colours of a marking pencil for the
# only three things this project ever says about a piece of work — it holds, it
# is broken, it is not settled yet. Three statements, three colours, and no
# fourth accent, because a fourth colour on a screen that says three things is a
# colour with no meaning attached.
#
# MEASURED, not eyeballed. Every text pair below was computed with the WCAG
# formula (w3.org/WAI/GL/wiki/Relative_luminance, w3.org/WAI/GL/wiki/Contrast_ratio)
# and clears 4.5:1, the Level AA body-text bar in SC 1.4.3
# (w3.org/WAI/WCAG21/Understanding/contrast-minimum.html). The tightest pair in
# either theme is `unsettled` on light `paper` at 4.60:1; most are above 5 and
# ink is 13-15. test_look.py recomputes all of them from the hex, so a colour
# cannot be nudged into illegibility without a failing test.
#
# CARDS TAKE BOTH A FILL SHIFT AND A HAIRLINE. card against paper measures
# 1.101:1 (light) and 1.107:1 (dark): that is a real difference on this desk and
# no difference at all on a dim laptop screen at an angle. The hairline does the
# rest — 1.27/1.40 light and 1.44/1.30 dark against paper and card. Neither cue
# is claimed to meet SC 1.4.11's 3:1, and neither has to: a card is not a
# control, the content inside it carries the meaning, and the seam only has to
# survive a bad screen. What IS pinned by a test is that the hairline
# out-contrasts the fill shift alone in both themes, since a hairline that does
# not is decoration.
#
# LIGHT IS THE DEFAULT AND DARK FOLLOWS THE SYSTEM, which is what the platform
# this runs on asks for: "Most apps should use the standard light UI style by
# default ... apps that use the light UI style are encouraged to follow the
# system style setting" (developer.gnome.org/hig/guidelines/ui-styling.html).
# The previous studio was light-only because its colours were literals spread
# through the widgets; the shell was dark-only for the same reason.
#
# THE EXTRA KEYS ARE ALIASES, NOT NEW COLOURS. Everything below the eight roles
# exists so locallm/studio.py's THEMES and t/lab.py's TRAIN_PALETTE can adopt
# this file without losing a key, and every one of them is one of the eight
# values above it — there is no ninth colour hiding in the alias block. Where an
# alias points somewhere surprising the reason is beside it.
# --------------------------------------------------------------------------

#: The eight role names. Every value in either palette is one of these eight.
ROLES = ("paper", "card", "line", "ink", "muted", "proved", "refuted",
         "unsettled")

PALETTES: dict[str, dict[str, str]] = {}

for _name, _p in (
    # Cream in coffee rather than paper white. The first light ground was
    # #F2EDE1 at 84.9% relative luminance, which is bright enough to glare in a
    # dim room, and the operator asked for something warmer and softer that does
    # not hurt to look at. This one is 72.5%, twelve points dimmer and browner.
    #
    # The accents had to come down with it, and that is the part worth knowing:
    # they were tuned against the bright ground, so simply darkening the paper
    # dropped proved, unsettled and muted BELOW WCAG AA — measured 4.51, 3.96 and
    # 4.71 against the new ground. Each was deepened until the whole set cleared
    # AA again. The result is better than what it replaced on both counts at once:
    # dimmer to look at, and a weakest pair of 5.51 where the old palette's was
    # 4.60. locallm/test_look.py computes every ratio rather than asserting a
    # remembered number, so this cannot quietly rot.
    ("light", dict(paper="#E8DCC8", card="#F3EADA", line="#CBB795",
                   ink="#241E16", muted="#5E5140", proved="#24603C",
                   refuted="#8F2B20", unsettled="#6F4E0C")),
    ("dark", dict(paper="#1B1917", card="#26221A", line="#3A352C",
                  ink="#EDE7D9", muted="#A49B8A", proved="#6BBF8A",
                  refuted="#F08070", unsettled="#D9A93F")),
):
    _p.update(
        # studio.py's THEMES names, and t/lab.py's TRAIN_PALETTE names.
        bg=_p["paper"], panel=_p["card"], fg=_p["ink"],
        ok=_p["proved"], bad=_p["refuted"], warn=_p["unsettled"],

        # `field` is the ground SHOWING THROUGH a card, which is what a sunken
        # entry or a log pane looks like on paper, and it needs no tenth value.
        field=_p["paper"],

        # THERE IS NO THIRD TEXT TIER. `faint` was a step quieter than `muted`
        # in both old palettes, and every use of it in the shell is real text:
        # hints, the status line, step descriptions, the "not yet" state. A tier
        # quieter than muted cannot reach 4.5:1 on this paper — muted itself is
        # 5.08 light and 6.37 dark, so the next step down lands under the bar.
        # It is kept as an alias so no call site breaks, and it is the same
        # colour, so nothing is silently made unreadable.
        faint=_p["muted"],

        # THE CHART SITS ON THE PAPER. Both old palettes plotted on near-black
        # in the light theme as well, which put one dark rectangle in an
        # otherwise light window and made the chart look like a different
        # application. Grid in the hairline, axis in muted.
        plot_bg=_p["card"], plot_grid=_p["line"], plot_axis=_p["muted"],

        # THE THREE SERIES, with no new hue. The training curve is the pencil
        # line itself, so it is graphite. The held-out curve is the number that
        # is not settled until training ends, so it is the amber. The
        # pure-guessing baseline is a reference, not a judgement, so it is
        # muted. Green and red are deliberately NOT spent here: a loss curve is
        # not a verdict, and lending the marking colours to it would make them
        # mean two different things on one screen.
        learn=_p["ink"], unseen=_p["unsettled"], guess=_p["muted"],

        # The transcript is a recessed sheet with pencil on it.
        log_bg=_p["paper"], log_fg=_p["ink"],

        # A SELECTED ROW IS A SHADED BAND, not an inverted one. Measured on the
        # band: ink is 10.92 light and 9.87 dark, so selected text stays ink. In
        # the light theme muted, proved and unsettled on this band come to 4.00,
        # 4.12 and 3.62, under the body bar, and refuted only just clears it at
        # 4.52 — so nothing but ink goes on a selection.
        select=_p["line"],
    )
    PALETTES[_name] = _p
del _name, _p


# When nothing can be read, open LIGHT. Reversed 2026-09-21, the same day it was
# set to dark, because the evidence went the other way on every ground looked at
# and this module already said so eighty lines up.
#
# Two of the three platform owners publish a default and both say light. GNOME:
# "Most apps should use the standard light UI style by default", with the stated
# exception being apps that display rich visual content like images or video,
# which this is not (developer.gnome.org/hig/guidelines/ui-styling.html).
# Microsoft: "Windows uses Light mode by default, but users can choose Dark mode"
# (learn.microsoft.com/en-us/windows/apps/desktop/modernize/apply-windows-themes).
# Apple publishes no default. The usability review adds: "we don't recommend
# switching to dark mode by default if your target audience includes the general
# population" (nngroup.com/articles/dark-mode).
#
# The measurement is about this exact fallback. It fires when no desktop service
# answers, which is most likely on a bare or minimal Linux install, which is also
# the machine most likely to be in a dim room at night. Dobres, Chahine and
# Reimer, Applied Ergonomics 60 (2017), 34 participants, lexical decision with an
# adaptive staircase: at 0 lux, 3 mm text needed 122.3 ms (SD 50.0) in dark
# against 84.1 ms (SD 43.7) in light, F(1,33) = 49.60, p < 0.001; at 4750 lux the
# difference was not significant. So opening dark here picked the one combination
# with a measured legibility penalty, in the one situation where it applies.
#
# Dark itself is untouched: it still follows the system wherever the system says.
# What is gone is guessing dark when nobody asked. See locallm/DESIGN-BRIEF.md C1.
_DARK_WHEN_UNKNOWN = False


def system_wants_dark() -> bool:
    """Follow the operating system's own light/dark setting, on all three.

    Each platform keeps this somewhere different and none of them is exposed
    through Tk, so each is read directly and every failure falls back to the
    default below rather than stopping the window opening. A wrong guess about a
    colour scheme is not worth a traceback.

      * Linux and the BSDs: the XDG desktop portal first, because it is
        desktop-agnostic and works under KDE and GNOME alike --
        org.freedesktop.portal.Settings.Read on org.freedesktop.appearance
        color-scheme, where the specification defines 1 as prefer-dark, 2 as
        prefer-light and 0 as no preference
        (flatpak.github.io/xdg-desktop-portal, Settings interface). Measured here
        2026-09-21: it answers `(<<uint32 1>>,)`. If the portal is absent, GNOME's
        own key, `gsettings get org.gnome.desktop.interface color-scheme`,
        measured the same day as 'prefer-dark'.
      * Windows: AppsUseLightTheme in the registry, 0 meaning dark.
      * macOS: `defaults read -g AppleInterfaceStyle`, which prints Dark when dark
        and EXITS NON-ZERO when light rather than printing Light, so the absence
        of the key is the light answer.

    THIS USED TO READ THE WINDOWS REGISTRY AND NOTHING ELSE, so on Linux and
    macOS it always answered light however the desktop was set, and the operator's
    own dark desktop opened a light window. That gap was documented here and in
    t/lab.py rather than fixed, and LOCALLLM_THEME=dark was the workaround.

    The unknown case now answers DARK, which is a decision rather than a
    discovery: the operator asked for a darker window, and when nothing can be
    read the warm graphite ground is the one to land on.

    Both spellings of the override are accepted. The variable was introduced as
    LOCALLLM_THEME, with three Ls, which is a typo nobody would guess; LOCALLM_THEME
    is the spelling to use and the old one keeps working so no one's setup breaks.
    """
    for name in ("LOCALLM_THEME", "LOCALLLM_THEME"):
        forced = os.environ.get(name, "").strip().lower()
        if forced in ("dark", "light"):
            return forced == "dark"

    if sys.platform.startswith("win"):
        try:
            import winreg                                      # noqa: PLC0415
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            with key:
                return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
        except Exception:                                      # noqa: BLE001
            return _DARK_WHEN_UNKNOWN

    if sys.platform == "darwin":
        try:
            done = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                                  capture_output=True, text=True, timeout=1.0)
        except (OSError, subprocess.SubprocessError):
            return _DARK_WHEN_UNKNOWN
        if done.returncode != 0:
            return False                  # the key is absent, which is how macOS says light
        return "dark" in done.stdout.strip().lower()

    # Every timeout here is short on purpose: this runs while the window is being
    # built, so a desktop service that has wandered off must cost a moment, not
    # the startup.
    try:
        done = subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.freedesktop.portal.Desktop",
             "--object-path", "/org/freedesktop/portal/desktop",
             "--method", "org.freedesktop.portal.Settings.Read",
             "org.freedesktop.appearance", "color-scheme"],
            capture_output=True, text=True, timeout=1.0)
        if done.returncode == 0:
            found = re.search(r"uint32\s+(\d+)", done.stdout)
            if found:
                return found.group(1) == "1"          # 1 dark, 2 light, 0 no preference
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        done = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=1.0)
        if done.returncode == 0:
            return "dark" in done.stdout.strip().lower()
    except (OSError, subprocess.SubprocessError):
        pass
    return _DARK_WHEN_UNKNOWN

def palette(dark: bool | None = None) -> dict[str, str]:
    """The active palette. `dark=None` asks the operating system."""
    want = system_wants_dark() if dark is None else dark
    return PALETTES["dark" if want else "light"]


# --------------------------------------------------------------------------
# SPACING: ONE SCALE, SIX STEPS, NO OTHER NUMBER.
#
# t/lab.py currently uses fourteen distinct padding values, among them the run
# 1, 2, 3, 5, 6, 7 — the signature of nudging a number until it looked right in
# one place, which is how two panels end up 6 and 7 pixels apart for no reason
# anyone can name. The scale is not invented here either: 4/8/12/16/24/32 are
# exactly Carbon's $spacing-02 through $spacing-07
# (carbondesignsystem.com/elements/spacing/overview/), a published scale built
# on multiples of two, four and eight.
#
# The names exist so a call site reads as an intention rather than a number. A
# value that does not fit one of the six is a layout question, not a licence to
# add a seventh step.
# --------------------------------------------------------------------------
SCALE = (4, 8, 12, 16, 24, 32)


class _Space(NamedTuple):
    tight: int    # inside one control: a mark and the word beside it
    inner: int    # between controls on the same row
    item: int     # between rows inside a card
    card: int     # a card's own padding
    group: int    # between cards
    page: int     # the window's outer margin


SPACE = _Space(*SCALE)


# RADIUS: two values, from the platform's own stylesheet rather than taste.
# libadwaita 1.6.0 sets $button_radius: 6px and $card_radius: $button_radius + 6
# (github.com/GNOME/libadwaita/blob/1.6.0/src/stylesheet/_common.scss), which is
# where 6 and 12 come from. Worth knowing before anyone "modernises" it: main has
# since moved buttons to 9px and pinned cards at 12px, so 6 is a dated choice, not
# a timeless one — and it is the one the rest of this desktop still draws.
class _Radius(NamedTuple):
    control: int
    card: int


RADIUS = _Radius(control=6, card=12)


# --------------------------------------------------------------------------
# FONTS.
#
# Moved from studio.py unchanged, including both fallbacks: TkDefaultFont and
# TkFixedFont are the only two family names guaranteed to exist on every
# platform Tk runs on.
# --------------------------------------------------------------------------
# Fonts are RESOLVED, not asserted. studio.py named a Windows-only sans in ten
# places (four of them bold) and a Windows-only mono in one. Measured on a Linux
# box 2026-09-20: neither family is installed, and Tk resolves them silently to
# Adwaita Sans and DejaVu Sans Mono without warning. A family name that becomes a
# different family on every platform is not a design decision, it is an
# unspecified default wearing one, so the sizes and weights at the call sites
# (which are decisions) are kept and the family is looked up.
#
# EACH PLATFORM'S OWN UI FACE LEADS. Inter used to sit at the front of the sans
# list, ahead of every native face, so any machine with Inter installed for some
# other reason rendered this window in a face nothing else on that desktop uses
# - which is the same fault the paragraph above describes, one layer further in.
# The operator's order is native first: SF Pro Text (macOS), Segoe UI (Windows),
# Cantarell (GNOME), Ubuntu, then the Noto/DejaVu faces that are what a bare
# Linux box actually has. Mono the same way: SF Mono, Consolas, then JetBrains
# Mono for whoever installed it, then DejaVu Sans Mono.
#
# AFTER THE LATIN FALLBACKS COMES A SCRIPT TAIL, and it changes nothing for
# anybody whose machine has one of the faces above. _family takes the FIRST
# installed name, so a face added here can only win on a machine where every
# name before it is missing — which is exactly the machine the tail is for: an
# install whose only real UI face covers Chinese or Arabic rather than Latin. The
# alternative on that machine is TkDefaultFont, an unspecified default nobody
# chose. Within the tail the CJK faces lead because they are the only ones
# measured to carry Latin as well: fc-list ':family=Noto Sans CJK SC:charset=0041'
# matches and so does Noto Sans Mono, while ':family=Noto Sans Arabic:charset=0041'
# and the Hebrew, Devanagari and Thai faces do not (measured 2026-09-21), so a
# machine that lands on one of those draws this window's own English labels
# through Tk's per-character fallback.
#
# THE NAMES ARE LOOKED UP, NOT GUESSED, because a family name that is one letter
# off does nothing at all and says nothing about it. "Noto Sans Arabic", "Noto
# Sans Hebrew", "Noto Sans Devanagari", "Noto Sans Thai", "Noto Sans SC" and
# "Noto Sans Mono" are family names in Google's own catalogue
# (fonts.google.com/metadata/fonts, 1946 families, read 2026-09-21); the
# operating-system packages of the CJK collection are named "Noto Sans CJK SC"
# and "Noto Sans Mono CJK SC" with the two-letter region code
# (github.com/googlefonts/noto-cjk), which is also how fontconfig's own
# preference list spells them
# (gitlab.freedesktop.org/fontconfig/fontconfig/-/raw/main/conf.d/65-nonlatin.conf).
# All fourteen names below were then checked against tkfont.families() on this
# machine, which sees every one of them under exactly this spelling.
_SANS = ["SF Pro Text", "Segoe UI", "Cantarell", "Ubuntu", "Noto Sans",
         "DejaVu Sans",
         # the script tail — see above; Latin-carrying faces first
         "Noto Sans CJK SC", "Noto Sans CJK JP", "Noto Sans SC",
         "Noto Sans Arabic", "Noto Sans Hebrew", "Noto Sans Devanagari",
         "Noto Sans Thai"]
# The mono tail takes only faces that are actually fixed-width: a proportional
# face in the reply box loses the alignment the box is mono for. FreeMono earns
# its place by measurement rather than reputation — fc-list says it carries
# Arabic, Hebrew and Devanagari as well as Latin, and it is the face Tk fell
# back to for Hebrew and Devanagari here when the base was DejaVu Sans Mono.
_MONO = ["SF Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono",
         "Noto Sans Mono CJK SC", "Noto Sans Mono CJK JP", "Noto Sans Mono",
         "FreeMono"]
_resolved: dict[str, str] = {}


def _family(kind: str, w: tk.Misc | None = None) -> str:
    """The first installed family from the list, memoised, asking `w`'s Tk.

    IT TAKES THE WIDGET TO ASK. tkfont.families() with no root falls back to
    tkinter's implicit default root
    (docs.python.org/3/library/tkinter.font.html#tkinter.font.families), which is
    whichever Tk() was created first - and this page is embedded in a window it
    did not create, so there need not be one at the moment it asks. When there is
    not, families() raises, the old code turned that into an empty set, and every
    font in the window fell back to TkDefaultFont for the rest of the session
    without saying so. With no widget and nothing memoised it returns Tk's named
    font WITHOUT caching it, so a later call that does have a widget still
    resolves properly rather than inheriting the failure.
    """
    if kind in _resolved:
        return _resolved[kind]
    names, fb = (_SANS, "TkDefaultFont") if kind == "sans" else (_MONO, "TkFixedFont")
    if w is None:
        return fb
    from tkinter import font as tkfont
    try:
        have = set(tkfont.families(w))
    except Exception:                                           # noqa: BLE001
        have = set()
    _resolved[kind] = next((n for n in names if n in have), fb)
    return _resolved[kind]


def resolve_fonts(w: tk.Misc) -> None:
    """Resolve both families against w's interpreter, before a widget asks.

    Whichever half of the window builds first calls this, so the bare
    SANS()/MONO() calls spread through widget construction hit the memo and
    never need a default root.
    """
    _family("sans", w)
    _family("mono", w)


def SANS(size: int, *style, w: tk.Misc | None = None) -> tuple:
    return (_family("sans", w), size, *style)


def MONO(size: int, *style, w: tk.Misc | None = None) -> tuple:
    return (_family("mono", w), size, *style)


# --------------------------------------------------------------------------
# THE MARKS, and what a judgement looks like.
#
# All four are present in DejaVu Sans and none is an emoji. TIMED_OUT was ⏱
# U+23F1 until fc-match showed DejaVu Sans carries no glyph for it, so it fell
# through to FreeSerif and drew serif beside the sans marks. ◷ U+25F7 is in
# DejaVu Sans and in Geometric Shapes, the block ● ▾ ▶ ■ already come from. The
# obvious hourglass ⌛ U+231B is wrong twice over: also absent from DejaVu Sans,
# and Emoji_Presentation=Yes, so it is the one candidate that really would come
# out as a colour emoji (unicode.org/Public/UCD/latest/ucd/emoji/emoji-data.txt
# v18.0.0, dated 2026-01-30, read 2026-09-20).
# --------------------------------------------------------------------------
PROVED = "✔"
REFUTED = "✘"
NOT_APPLICABLE = "–"
TIMED_OUT = "◷"
MARKS = (PROVED, REFUTED, NOT_APPLICABLE, TIMED_OUT)


class Say(NamedTuple):
    """What the program says about one piece of work.

    t/lab.py's verdict() already returns (symbol, short word, one plain
    sentence, colour) for one proof check. This is the same shape for every
    judgement anywhere in the window, with one difference: `tone` is a PALETTE
    KEY, not a colour. verdict() returns a literal from the dark palette, which
    is why it could only ever be used in the dark half of the window.

    mark  one of MARKS
    word  the headline, one or two words
    why   one plain sentence, no jargon and no number a reader cannot act on
    tone  a key of PALETTES["light"] — normally proved, refuted, unsettled or
          muted
    """
    mark: str
    word: str
    why: str
    tone: str


# The dash carries "no claim was made", and the tone says whether that is a
# problem: amber where a claim was expected and could not be made, muted where
# nothing went wrong and we simply do not know. That pairing is why SUSPECT and
# "Not checked" can share a mark without saying the same thing.
_NOT_CHECKED = Say(
    NOT_APPLICABLE, "Not checked",
    "The repetition check did not finish, so nothing is claimed about this "
    "text either way.", "muted")

_LEAKAGE = {
    "CLEAN": Say(PROVED, "Clean", "Looks fine to train on.", "proved"),
    "SUSPECT": Say(NOT_APPLICABLE, "Repetitive",
                   "Some passages repeat — the fairness test may be weak.",
                   "unsettled"),
    "CONTAMINATED": Say(REFUTED, "Leaking",
                        "Heavy repetition — the fairness test will not mean "
                        "much.", "refuted"),
}


def say_corpus(leakage_verdict: str | None,
               trustworthy: bool = False,
               split: str | None = None,
               achievable_val_frac: float | None = None) -> Say:
    """What to say about a corpus, from the two checks studio already runs.

    leakage_verdict     leakage.scan(...).verdict — "CLEAN", "SUSPECT" or
                        "CONTAMINATED"; None (or anything unrecognised) means
                        the scan did not produce one
    trustworthy         the report's own .trustworthy. The split problem is only
                        allowed to speak when the leakage report is trustworthy,
                        because a contaminated corpus has a worse problem than
                        an unlucky split and must not be relabelled as one
    split               data.split_verdict(...) — "corpus", "splitter", or any
                        other truthy value (in practice "empty"); None when the
                        holdout is fine
    achievable_val_frac split_health()["achievable_val_frac"], used only in the
                        "corpus" sentence

    THE PRECEDENCE IS STUDIO'S and is kept exactly: the leakage verdict decides
    first, then a split problem overrides it, and only while the report is
    trustworthy. One deliberate change: studio's `except` arm fell back to green
    with an empty note, so a check that crashed looked exactly like a check that
    passed. A green tick for a check that did not run is the failure this
    project keeps fixing elsewhere, so that path now says so.
    """
    say = _LEAKAGE.get(leakage_verdict or "")
    if say is None:
        return _NOT_CHECKED
    if trustworthy and split:
        if split == "corpus":
            if achievable_val_frac is None:
                why = ("This text cannot be split into a fair test. More, "
                       "smaller files would help.")
            else:
                why = (f"This text cannot be split into a fair test — at most "
                       f"{achievable_val_frac:.1%} can be held back. More, "
                       f"smaller files would help.")
            say = Say(NOT_APPLICABLE, "Unsplittable", why, "unsettled")
        elif split == "splitter":
            say = Say(NOT_APPLICABLE, "Mis-split",
                      "Only a sliver was held back for testing, though this "
                      "text could support more — another seed would split it "
                      "better.", "unsettled")
        else:
            say = Say(NOT_APPLICABLE, "No holdout",
                      "Nothing could be held back for testing.", "unsettled")
    return say


def say_progress(train_loss: float, vocab: int) -> Say:
    """How far the model has got, in characters rather than log-probability.

    exp(loss) is the number of characters the model is effectively still
    choosing between for each next character — a quantity with units a person
    can say out loud. It starts at the size of the alphabet (pure guessing) and
    falls as the model learns. Raw cross-entropy, where 2.774 means nothing to
    anyone who has not taken the course, is the same number untranslated.

    The 0.95 bar for "still guessing" and all three sentences are studio's own
    _headline, unchanged; what is added is the mark, the word and the tone, so
    the headline can be shown the same way as every other judgement. Above the
    bar the tone is amber rather than green: no progress has been measured yet,
    and that is where every model starts rather than something being wrong.
    """
    choices = math.exp(min(train_loss, 20))
    if not vocab:
        # No alphabet, so there is no "out of how many" and no fraction of the
        # way to certainty — the count is reported and nothing is claimed.
        return Say(NOT_APPLICABLE, "Unmeasured",
                   f"Narrowed down to about {choices:.0f} choices per "
                   f"character.", "muted")
    if choices >= vocab * 0.95:
        return Say(NOT_APPLICABLE, "Guessing",
                   f"Still guessing: all {vocab} characters look equally "
                   f"likely to it. This is where every model starts.",
                   "unsettled")
    pct = (1 - (choices - 1) / max(vocab - 1, 1)) * 100
    return Say(PROVED, "Learning",
               f"It has narrowed each next character down to about "
               f"{choices:.1f} of {vocab} possibilities "
               f"— {pct:.0f}% of the way from guessing to certainty.",
               "proved")


# --------------------------------------------------------------------------
# CAN THE FONT WE RESOLVED DRAW THIS PERSON'S OWN WRITING?
#
# Every face at the front of both lists is a Latin UI face, and home.py's prompt
# box and reply box are where somebody watches their own language come back to
# them. On a machine with no face for their script that is a row of empty boxes
# and no explanation — the one failure in this window a person cannot even
# describe well enough to ask about. So the window asks first and says what to
# install.
#
# TK ALREADY ANSWERS HALF OF IT, and the answer was looked up rather than
# invented: `font actual FONT ?-displayof W? ?option? ?--? char` returns the
# attributes "of the specific font used to render that character, which will be
# different from the base font if the base font does not contain the given
# character" (github.com/tcltk/tk/blob/core-8-6-branch/doc/font.n). A family name
# that comes back DIFFERENT from the one asked about is therefore proof the glyph
# draws: some installed face has it and Tk has already found it.
#
# THE OTHER HALF IT WILL NOT TELL YOU. tkUnixRFont.c's GetFont() walks the
# fontconfig match list for the first face whose charset holds the codepoint and,
# when none does, falls to `i = 0` — the base face, silently
# (github.com/tcltk/tk/blob/core-8-6-branch/unix/tkUnixRFont.c). Windows does the
# same thing in the same place: win/tkWinFont.c's FindSubFontForChar ends at
# `return &fontPtr->subFontArray[0]`, the base subfont. And the non-Xft unix build
# says it outright in a comment, unix/tkUnixFont.c lines 2164-2165: "No font can
# display this character, so it will be displayed as a control character
# expansion" — it draws the expansion and tells the caller nothing. So the SAME
# family coming back means either the base font covers the character or nothing on
# the machine does, and those two have to be separated some other way.
#
# MEASURING THE BOX DOES NOT SEPARATE THEM. The obvious idea — a box is a
# different width from a letter you know is present — is false here, and was
# measured before it was trusted. At size 12 DejaVu Sans draws a missing
# codepoint at an advance of 10px and sixteen present Latin letters
# (abdeghnopquEPSTY) measure exactly 10px too; DejaVu Sans Mono reports `font
# metrics -fixed 1` and measures every character, present or missing, at 10px.
# Width can never prove a glyph ABSENT. It does prove one PRESENT, which is the
# direction kept: an advance that differs from the missing-glyph advance is a
# glyph that exists, and that is how DejaVu Sans's own Arabic alef (4px against
# 10px) is recognised.
#
# SO THREE SIGNALS, and boxes are only predicted when none of them fires: Tk's
# per-character family, the advance against the missing-glyph advance, and last
# whether the machine has any family for that script at all. The order matters
# because only the first two are about the actual text; the third is a table and
# a table can be out of date.
#
# INVENTED: the three-signal ladder, the plane-15 ruler and the script table are
# this project's own, and they are here because the published answer covers only
# half the question. Searched for a library or a documented method that reports a
# MISSING glyph from Tk or Tcl: Tk's own manual and source (doc/font.n,
# unix/tkUnixRFont.c, win/tkWinFont.c), the tcl-lang wiki, Stack Exchange for
# per-character font fallback, and GitHub for a Tkinter glyph-coverage helper.
# What exists answers presence only — `font actual ... char` naming a different
# family is proof a glyph draws — and nothing exposes the case tkUnixRFont.c's
# `i = 0` creates, where no face has the codepoint and the base face is returned
# anyway. Toolkits that DO answer it do not go through Tk: fontconfig's
# FcCharSetHasChar (which is what Tk itself calls) and HarfBuzz's
# hb_font_get_nominal_glyph both take a codepoint and answer honestly, and either
# would settle this in one call. Neither is reachable here — fontconfig is absent
# on Windows and macOS, and shelling out to fc-list while somebody types is not a
# cost this path can pay — so the absence half is a fallback of our own, built to
# abstain rather than guess: a width can only ever prove presence, and the family
# table is the one thing allowed to turn "no evidence" into "no font".
#
# TWO THINGS THIS PROJECT HAD WRONG, both found by measuring instead of
# assuming. DejaVu Sans is NOT Latin-only: fc-list ':family=DejaVu Sans:charset=0627'
# matches, and so does 05d0 — it carries Arabic and Hebrew, and DejaVu Sans Mono
# carries Arabic. What DejaVu has no glyph for is Han, Devanagari and Thai. And
# Cantarell, the face this desktop resolves to, has no ✔ U+2714 and no ◷ U+25F7 —
# the marks above are drawn by Tk's fallback, not by the window's own face.
#
# WHAT THIS DOES NOT CLAIM: that the text will look right, only that it will not
# be boxes. Tk draws Arabic unjoined — measured, `font measure` of the three-letter
# word ابت equals the sum of the three isolated advances in both DejaVu Sans (34px)
# and Noto Sans Arabic (36px), so no shaping happened — and it has no bidirectional
# reordering either. Those are separate defects and this function must not be read
# as covering them.
# --------------------------------------------------------------------------


class _Script(NamedTuple):
    """A writing system, the codepoints that identify it, and who can draw it.

    name      what to call it in a sentence somebody reads
    ranges    inclusive codepoint ranges, first match wins, so they do not
              overlap. Taken from unicode.org/Public/UCD/latest/ucd/Blocks.txt
              (Blocks-18.0.0, dated 2026-07-08)
    families  families known to cover it, best first. This is the third signal
              and the source of the "install this" sentence, so the names are
              spellings from a published catalogue —
              fonts.google.com/metadata/fonts for the "Noto Sans <script>" and
              "Noto Sans <script> UI" faces, github.com/googlefonts/noto-cjk for
              the CJK collection's region codes — plus any face measured on this
              machine with fc-list to carry the script
    """
    name: str
    ranges: tuple[tuple[int, int], ...]
    families: tuple[str, ...]


# ASCII IS THE ONLY THING NOT CHECKED. Not because every face is assumed to have
# it, but because a face without it would have turned every label in this window
# into boxes already, which the person can see without being told. Everything
# above U+007F is asked about, including Greek and Cyrillic: Cantarell covers α
# but not U+0180, Ubuntu covers U+0180 but not Vietnamese ạ (measured), so "the
# UI faces obviously have European text" is not a claim this file can make.
_SCRIPTS: tuple[_Script, ...] = (
    # STARTS AT U+00A0, not at U+0180. It started at Latin Extended-B until
    # say_can_draw("Grüße") came back "U+00FC and U+00DF": ü and ß live in the
    # Latin-1 Supplement, so half of Europe's own writing was falling through to
    # the unnamed branch and being reported by codepoint.
    _Script("accented Latin",
            ((0x00A0, 0x036F), (0x1E00, 0x1EFF), (0x2C60, 0x2C7F),
             (0xA720, 0xA7FF)),
            ("Noto Sans", "DejaVu Sans", "Noto Sans Mono", "FreeMono")),
    _Script("Greek", ((0x0370, 0x03FF), (0x1F00, 0x1FFF)),
            ("Noto Sans", "DejaVu Sans", "Noto Sans Mono")),
    _Script("Cyrillic", ((0x0400, 0x052F), (0x2DE0, 0x2DFF), (0xA640, 0xA69F)),
            ("Noto Sans", "DejaVu Sans", "Noto Sans Mono")),
    _Script("Armenian", ((0x0530, 0x058F),),
            ("Noto Sans Armenian", "Noto Serif Armenian")),
    _Script("Hebrew", ((0x0590, 0x05FF), (0xFB1D, 0xFB4F)),
            ("Noto Sans Hebrew", "Noto Rashi Hebrew", "DejaVu Sans",
             "FreeMono")),
    _Script("Arabic",
            ((0x0600, 0x06FF), (0x0750, 0x077F), (0x0870, 0x089F),
             (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)),
            ("Noto Sans Arabic", "Noto Naskh Arabic", "Noto Kufi Arabic",
             "Noto Sans Arabic UI", "DejaVu Sans", "FreeMono")),
    _Script("Devanagari", ((0x0900, 0x097F), (0xA8E0, 0xA8FF),
                           (0x11B00, 0x11B5F)),
            ("Noto Sans Devanagari", "Noto Sans Devanagari UI", "FreeMono")),
    _Script("Bengali", ((0x0980, 0x09FF), (0x11DF0, 0x11DFF)),
            ("Noto Sans Bengali", "Noto Sans Bengali UI")),
    _Script("Gurmukhi", ((0x0A00, 0x0A7F),),
            ("Noto Sans Gurmukhi", "Noto Sans Gurmukhi UI")),
    _Script("Gujarati", ((0x0A80, 0x0AFF),),
            ("Noto Sans Gujarati", "Noto Sans Gujarati UI")),
    _Script("Odia", ((0x0B00, 0x0B7F),),
            ("Noto Sans Oriya", "Noto Sans Oriya UI")),
    _Script("Tamil", ((0x0B80, 0x0BFF), (0x11FC0, 0x11FFF)),
            ("Noto Sans Tamil", "Noto Sans Tamil UI")),
    _Script("Telugu", ((0x0C00, 0x0C7F),),
            ("Noto Sans Telugu", "Noto Sans Telugu UI")),
    _Script("Kannada", ((0x0C80, 0x0CFF),),
            ("Noto Sans Kannada", "Noto Sans Kannada UI")),
    _Script("Malayalam", ((0x0D00, 0x0D7F),),
            ("Noto Sans Malayalam", "Noto Sans Malayalam UI")),
    _Script("Sinhala", ((0x0D80, 0x0DFF),),
            ("Noto Sans Sinhala", "Noto Sans Sinhala UI")),
    _Script("Thai", ((0x0E00, 0x0E7F),),
            ("Noto Sans Thai", "Noto Sans Thai UI", "Noto Serif Thai",
             "Noto Looped Thai")),
    _Script("Lao", ((0x0E80, 0x0EFF),),
            ("Noto Sans Lao", "Noto Sans Lao UI", "Noto Looped Lao")),
    # Google's catalogue has no "Noto Sans Tibetan" — checked, not assumed; the
    # serif is the family, and it is what Tk picked for U+0F40 on this machine.
    _Script("Tibetan", ((0x0F00, 0x0FFF),), ("Noto Serif Tibetan",)),
    _Script("Myanmar", ((0x1000, 0x109F),),
            ("Noto Sans Myanmar", "Noto Sans Myanmar UI")),
    _Script("Georgian", ((0x10A0, 0x10FF),),
            ("Noto Sans Georgian", "Noto Serif Georgian")),
    _Script("Ethiopic", ((0x1200, 0x137F),),
            ("Noto Sans Ethiopic", "Noto Serif Ethiopic")),
    _Script("Khmer", ((0x1780, 0x17FF),),
            ("Noto Sans Khmer", "Noto Sans Khmer UI")),
    # One entry for the whole CJK collection because one font file covers it:
    # kana, Hangul and Han share Noto Sans CJK, and naming "Japanese" at somebody
    # typing Chinese would be worse than naming all three.
    _Script("Chinese, Japanese or Korean",
            ((0x2E80, 0x2EFF), (0x3000, 0x303F), (0x3040, 0x30FF),
             (0x3100, 0x312F), (0x3130, 0x318F), (0x31C0, 0x31EF),
             (0x3200, 0x33FF), (0x4E00, 0x9FFF), (0xA960, 0xA97F),
             (0xAC00, 0xD7AF), (0xD7B0, 0xD7FF), (0xF900, 0xFAFF),
             (0xFE30, 0xFE4F), (0xFF00, 0xFFEF), (0x1B000, 0x1B0FF),
             (0x20000, 0x2A6DF), (0x2A700, 0x2B73F)),
            ("Noto Sans CJK SC", "Noto Sans CJK JP", "Noto Sans CJK TC",
             "Noto Sans CJK KR", "Noto Sans CJK HK", "Noto Sans Mono CJK SC",
             "Noto Sans SC", "Noto Sans JP", "Noto Sans TC", "Noto Sans KR")),
    # PUNCTUATION IS IN THE TABLE because a person who pastes a quotation gets
    # curly quotes and an em dash whether they asked for them or not, and those
    # are U+2019 and U+2014 — above ASCII, so checked, and worth a name rather
    # than a codepoint. This range also holds the four marks above, which is how
    # Cantarell's missing ✔ came to light. "Noto Sans Symbols 2" is Google's
    # spelling and "Noto Sans Symbols2" is the spelling installed here; both are
    # listed because a family name that is one character off finds nothing.
    _Script("punctuation and symbols", ((0x2000, 0x2BFF),),
            ("DejaVu Sans", "Noto Sans", "Noto Sans Symbols",
             "Noto Sans Symbols 2", "Noto Sans Symbols2", "FreeSerif")),
    # Emoji, and the honest part is that a font being present is all this claims:
    # Tk 8.6 has no colour bitmap path, so an emoji it can draw at all it draws
    # flat. Family names from fontconfig's own generic list
    # (gitlab.freedesktop.org/fontconfig/fontconfig/-/raw/main/conf.d/45-generic.conf).
    # The older symbol-block emoji (☺ U+263A and friends) are deliberately NOT
    # here: they are inside the punctuation range above, DejaVu Sans draws them,
    # and two entries claiming one codepoint would make the table's first-match
    # rule a coin toss.
    _Script("emoji", ((0x1F000, 0x1FAFF),),
            ("Noto Color Emoji", "Apple Color Emoji", "Segoe UI Emoji",
             "Noto Emoji")),
)

_BY_NAME = {s.name: s for s in _SCRIPTS}

# The reference size for every question below. `font actual`'s family answer does
# not depend on it, and the two `font measure` calls are only ever compared with
# each other, so one size keeps the memo small.
_ASK_SIZE = 12

# THE MISSING-GLYPH RULER. A codepoint in plane 15's private use area has no
# standard glyph, so measuring it measures whatever the font draws for "I do not
# have this" — and comparing a real character against it is the one width test
# that survived measurement. It is verified before use rather than trusted: some
# fonts (icon patches, for one) DO map this area, and if Tk reports a different
# family for it then this font's answer is not a missing glyph and the test is
# skipped instead of quietly lying.
_NO_GLYPH_CP = 0xF0000

_glyph_memo: dict[tuple[str, str, int], str] = {}
_families_memo: dict[str, frozenset[str]] = {}


#: How many distinct codepoints of one script get asked about. Four rather than
#: one because of what one costs: U+0870 is an Arabic letter no font on this
#: machine has, and with a single sample a message beginning with it made the
#: check announce "nothing on this computer can draw Arabic" while every ordinary
#: Arabic letter drew perfectly. Four rather than all of them because these are
#: Tk round trips on a path that runs while somebody types, and because a script
#: is one font file in the Noto design — a family that has the first four letters
#: of a person's writing is not going to be missing the fifth.
_SAMPLE = 4


def _needed(text: str) -> dict[str, tuple[int, ...]]:
    """Writing system -> up to _SAMPLE distinct codepoints of it in `text`.

    A name from _SCRIPTS where one matches, and "U+XXXX" for a codepoint no entry
    covers — an unlisted script, a symbol, an emoji. The unnamed case is
    deliberate: the check still runs on it and still reports boxes, it just
    cannot name a font to install, and saying "this character has no font here"
    beats saying nothing because the table is short.

    A FEW CODEPOINTS PER SCRIPT, not all of them, is what makes the check cheap
    enough to run while somebody types: the questions below are Tk round trips,
    and a paragraph of Arabic asks no more of them than four letters of it does.
    """
    found: dict[str, list[int]] = {}
    for ch in dict.fromkeys(text):          # distinct, first appearance kept
        cp = ord(ch)
        if cp < 0x80:
            continue
        name = next((s.name for s in _SCRIPTS
                     if any(lo <= cp <= hi for lo, hi in s.ranges)), None)
        seen = found.setdefault(name or f"U+{cp:04X}", [])
        if len(seen) < _SAMPLE:
            seen.append(cp)
    return {name: tuple(cps) for name, cps in found.items()}


def scripts_in(text: str) -> tuple[str, ...]:
    """The writing systems `text` needs beyond ASCII, in order of appearance."""
    return tuple(_needed(text))


def _ask(w: tk.Misc, *args) -> str | None:
    """One `font` subcommand on w's interpreter, or None if it would not answer.

    Every caller treats None as "no signal" rather than as bad news, for the
    reason _family already has a bare except: the widget may belong to a window
    this page did not create, and a question that cannot be asked must not become
    a verdict.
    """
    try:
        return str(w.tk.call("font", *args))
    except Exception:                                           # noqa: BLE001
        return None


def _drawn_by(w: tk.Misc, family: str, cp: int) -> str | None:
    """The family Tk will really use for this codepoint in this font.

    The same name back is not an answer either way — see the section comment.
    """
    return _ask(w, "actual", (family, _ASK_SIZE), "-displayof", str(w),
                "-family", "--", chr(cp))


def _measures_as_missing(w: tk.Misc, family: str, cp: int) -> bool | None:
    """Does this codepoint measure exactly what this font's missing glyph does?

    None means the question has no answer in this font: a fixed-width font gives
    every character the same advance (measured: DejaVu Sans Mono, 10px for all of
    them including the missing one), and a font that maps the plane-15 ruler has
    no missing-glyph advance to compare against. True is weak evidence of absence
    and False is strong evidence of presence, which is why only False is acted on
    alone.
    """
    if _ask(w, "metrics", (family, _ASK_SIZE), "-displayof", str(w),
            "-fixed") == "1":
        return None
    ruler = _drawn_by(w, family, _NO_GLYPH_CP)
    if ruler is None or ruler.lower() != family.lower():
        return None
    here = _ask(w, "measure", (family, _ASK_SIZE), "-displayof", str(w), chr(cp))
    gone = _ask(w, "measure", (family, _ASK_SIZE), "-displayof", str(w),
                chr(_NO_GLYPH_CP))
    if here is None or gone is None:
        return None
    return here == gone


def _installed(w: tk.Misc) -> frozenset[str]:
    """Every family name on this display, lowercased; empty if Tk would not say.

    `font families` returns "the case-insensitive names of all font families"
    (github.com/tcltk/tk/blob/core-8-6-branch/doc/font.n), hence the fold. Held
    per window path because it is 316 names on this machine and the answer cannot
    change while the window is open; an empty answer is not cached, for the reason
    _family does not cache its fallback. Tk's 316 and fc-list's 361 are not the
    same count and neither is wrong — fontconfig lists a family per style file,
    so the tests that measure this machine ask fc-list and the window asks Tk.

    IT MUST NOT GO THROUGH _ask, and that is the whole reason this asks Tk
    directly. _ask ends in str(), which is right for the three questions that
    answer with one value and silently wrong for this one: tkinter hands a Tcl
    list back as a PYTHON TUPLE, so str() renders it as Python source —
    measured 2026-09-21, the first 60 characters came back as
    `('Noto Sans Gurmukhi', 'Inter Display', 'Noto Sans Display',` — and
    splitlist then cut that repr on its spaces into 314 fragments like `('Noto`
    and `Sans`. Not one real family name survived, so `"noto sans arabic" in
    have` was False on a machine with Noto Sans Arabic installed, and the whole
    family-table signal below had never once fired. What it cost is in
    _can_draw's docstring: this desktop told a Greek speaker their own ε would
    come out as an empty box. splitlist takes the tuple unchanged, which is why
    the call is made here rather than borrowed.
    """
    key = str(w)
    if key in _families_memo:
        return _families_memo[key]
    try:
        have = frozenset(
            str(n).lower()
            for n in w.tk.splitlist(w.tk.call("font", "families",
                                              "-displayof", key)))
    except Exception:                                           # noqa: BLE001
        return frozenset()
    if not have:
        return frozenset()
    _families_memo[key] = have
    return have


def _can_draw(w: tk.Misc, cp: int, families: tuple[str, ...]) -> str:
    """"drawn", "absent" or "unsure" for one codepoint in both resolved fonts.

    BOTH FONTS, because home.py's prompt box and reply box are mono while its
    labels are sans, and a person who can read their own prompt but not their own
    reply has still lost.

    A WIDTH NEVER CONCLUDES ABSENCE, and the first version of this function had
    it doing exactly that. Run against this desktop it announced "nothing on this
    computer can draw accented Latin" for "Grüße aus Köln", and the same for
    Greek, for Cyrillic and for curly quotes: the resolved sans is Cantarell, ü
    measures the same 8px as Cantarell's missing glyph, and one coincidence of
    advance was being read as proof. The same was already in the measurement above
    — sixteen present DejaVu letters share its missing-glyph advance — so the rule
    is now the one the measurement supports. An advance that DIFFERS proves
    presence; an advance that matches proves nothing and leaves the codepoint
    unsure, and only the family table can turn unsure into absent.

    Which makes the order of the three signals an order of strength: what Tk says
    it will use, then what the advance says, then a list of family names that is a
    belief about other machines rather than a measurement of this one.

    THE TABLE'S CLAIM IS ABOUT A SCRIPT, NOT A CODEPOINT, and the measurement that
    fixes its limit is worth stating because it cannot be improved from inside Tk.
    Measured here 2026-09-21, Greek ε U+03B5 and Arabic U+0870 produce the SAME
    four answers: base family back unchanged from both fonts, an advance equal to
    the missing-glyph advance in the sans, and no advance answer at all from the
    fixed-width mono. Cantarell draws ε perfectly and nothing on this machine
    draws U+0870. Tk cannot tell those apart — tkUnixRFont.c returns the base face
    for both — so the table breaks the tie for both, and it is right about the
    first and generous about the second. That trade is deliberate: reading it the
    other way told this desktop's own Greek, Cyrillic and accented-Latin text
    "some of this will be empty boxes", which is a false alarm on the most common
    text there is, against one unassigned-looking Arabic codepoint being called
    readable. The headline sentence is therefore a claim about the SCRIPT having a
    home on this computer, not a promise about every character in the string.
    """
    signals = []
    for kind in ("sans", "mono"):
        base = _family(kind, w)
        if base.startswith("Tk"):
            # Tk's own named font: there is no family name to compare an answer
            # against, so this font can only be reported on by the table.
            continue
        got = _drawn_by(w, base, cp)
        if got is None:
            continue
        if got.lower() != base.lower() or _measures_as_missing(w, base,
                                                               cp) is False:
            signals.append("drawn")
        else:
            signals.append("unsure")
    have = _installed(w)
    capable = bool(have) and any(f.lower() in have for f in families)
    if signals and all(v == "drawn" for v in signals):
        return "drawn"
    if capable:
        return "drawn"
    if "drawn" in signals:
        # One box will draw it and the other gave no signal — that is not enough
        # to promise boxes, and this project would rather abstain than be wrong.
        return "unsure"
    return "absent" if signals else "unsure"


def _and(names: list[str], cap: int = 3) -> str:
    """"a", "a and b", "a, b and c", then "a, b, c and 2 more"."""
    if len(names) > cap:
        names = names[:cap] + [f"{len(names) - cap} more"]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def say_can_draw(text: str, w: tk.Misc | None = None) -> Say:
    """Whether this computer can draw `text`, and what to install if it cannot.

    IT TAKES THE WIDGET TO ASK, for the same reason _family does: the question is
    about one Tk interpreter's display and there need not be a default root. With
    no widget it answers for ASCII (where the window's own labels are the
    evidence) and otherwise says plainly that nothing was checked, because a
    green tick for a check that did not run is the failure this project keeps
    finding elsewhere.

    The Say a caller gets:
      proved / "Readable"      every script in the text has a font here
      refuted / "No font"      at least one has none, and the sentence names the
                               family to install
      unsettled / "Not sure"   Tk gave no usable answer for some script
      unsettled / "Some boxes" part of one script is missing — the sentence says
                               which character, and that the rest is fine
      muted / "Not checked"    nothing was asked: no widget, or no text yet
    """
    if not text or not text.strip():
        return Say(NOT_APPLICABLE, "Not checked", "There is no text to check.",
                   "muted")
    need = _needed(text)
    if not need:
        return Say(PROVED, "Readable",
                   "Every character here is in the face this window already "
                   "draws its own labels in.", "proved")
    if w is None:
        return Say(NOT_APPLICABLE, "Not checked",
                   f"The window has not opened yet, so nothing is claimed about "
                   f"whether this computer can draw {_and(list(need))}.",
                   "muted")
    sans, mono = _family("sans", w), _family("mono", w)
    gone, partial, unsure = [], [], []
    for name, cps in need.items():
        script = _BY_NAME.get(name)
        marks = []
        for cp in cps:
            memo = (sans, mono, cp)
            verdict = _glyph_memo.get(memo)
            if verdict is None:
                verdict = _can_draw(w, cp, script.families if script else ())
                _glyph_memo[memo] = verdict
            marks.append(verdict)
        missing = [cp for cp, v in zip(cps, marks) if v == "absent"]
        fams = script.families if script else ()
        here = _installed(w)
        if missing and len(missing) == len(marks) and not (
                here and any(f.lower() in here for f in fams)):
            gone.append(name)
        elif missing:
            # Some sampled letters of this script draw and some do not, on a
            # machine with no family listed for it. "No font for <script>" would
            # be false — it would send somebody to install a font that would not
            # help — so the codepoint is named instead of the script.
            partial.append((name, missing[0]))
        elif "unsure" in marks:
            unsure.append(name)
    if gone:
        fixes = [s.families[0] for s in (_BY_NAME.get(n) for n in gone)
                 if s is not None]
        fix = (f" — installing {_and(fixes, 2)} fixes it" if fixes else
               " — a font that covers it has to be installed")
        return Say(REFUTED, "No font",
                   f"Nothing on this computer can draw {_and(gone)}, so that "
                   f"text will come out as empty boxes{fix}.", "refuted")
    if partial:
        shown = [f"U+{cp:04X}" for _, cp in partial]
        return Say(NOT_APPLICABLE, "Some boxes",
                   f"A few characters here have no font on this computer "
                   f"({_and(shown)}), so those will come out as empty boxes.",
                   "unsettled")
    if unsure:
        return Say(NOT_APPLICABLE, "Not sure",
                   f"This computer could not say whether it has a font for "
                   f"{_and(unsure)}, so nothing is claimed either way.",
                   "unsettled")
    return Say(PROVED, "Readable",
               f"This computer has a font for {_and(list(need))}, so the text "
               f"will draw as itself.", "proved")

# MOVED HERE FROM studio.py, 2026-09-21, because it could not do its job there.
# studio.py imports torch at module scope, so t/lab.py could only reach this
# through `from studio import fit_to_screen` inside a try/except -- and on a host
# with no torch that import raises ModuleNotFoundError and the window silently
# fell back to a hardcoded 1400x900 with a 1000x700 minimum. A machine with no
# torch is not an edge case here, it is the target: the point of the portable
# build is a stranger's laptop that has never installed anything. So the geometry
# helper lives with the other things that decide how the window looks, where
# nothing needs torch to ask a question about the screen.
def fit_to_screen(widget: tk.Misc, want: tuple[int, int] | None = None) -> None:
    """Size and place the window so it cannot open off-screen or clipped.

    FOR THE HOST TO CALL, not just main(). This only ever ran under
    `if __name__ == "__main__"`, so in the merged window - where t/lab.py owns
    the root - none of it applied and that window could still open taller than
    the screen. It therefore takes any widget and resolves the toplevel itself
    (winfo_toplevel is the identity on a root), and it touches nothing but
    geometry and minsize: no title, no ttk theme, no colours, no scaling, because
    the window belongs to the caller. `want=None` means "whatever the layout asks
    for", for a host that has no pixel preference of its own. Nothing on this
    path touches torch. Importing this module still does, deliberately - t/lab.py
    reads that ImportError to put up its "training needs torch" panel - so a host
    that wants only the geometry helpers must import inside a try/except, the way
    its build_train already does.

    Three things went wrong before, and all three are the same mistake -- a
    pixel size written down in advance by someone who could not see the screen
    it would open on:

      * a fixed 1180x820 is bigger than the usable area on a 1366x768 laptop,
        so the bottom of the window - which is where the buttons are - was
        simply not reachable;
      * turning on DPI awareness scales every font by the display factor (1.5
        here) while leaving that pixel count alone, so the content grew and the
        window did not, and the right-hand column was cut off mid-sentence;
      * a window remembered at a position from a second monitor opens off the
        edge of a single-monitor machine.

    So: ask the layout how big it actually wants to be, scale the preference by
    the same factor the fonts were scaled by, clamp both to the work area, and
    centre it. The minimum is clamped too, because a minsize larger than the
    screen is unrecoverable - the user cannot resize their way out of it.
    """
    import tkinter as tk                       # runtime, not just typing
    root = widget.winfo_toplevel()
    root.update_idletasks()
    try:
        scale = root.winfo_fpixels("1i") / 72.0
    except tk.TclError:
        scale = 1.0

    # Leave room for the taskbar and window chrome rather than assuming none.
    avail_w = max(640, root.winfo_screenwidth() - int(80 * scale))
    avail_h = max(480, root.winfo_screenheight() - int(100 * scale))

    want_w, want_h = want if want else (0, 0)
    need_w = max(root.winfo_reqwidth(), int(want_w * scale))
    need_h = max(root.winfo_reqheight(), int(want_h * scale))
    w, h = min(need_w, avail_w), min(need_h, avail_h)

    x = max(0, (root.winfo_screenwidth() - w) // 2)
    y = max(0, (root.winfo_screenheight() - h) // 3)
    root.geometry(f"{w}x{h}+{x}+{y}")
    # Clamped to the size just set, not only to the work area: a minsize larger
    # than the window makes the window manager grow it straight back, which is
    # the clipping this function exists to prevent.
    root.minsize(min(int(760 * scale), w), min(int(560 * scale), h))
