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
    ("light", dict(paper="#F2EDE1", card="#FBF8F1", line="#DCD3C2",
                   ink="#23201C", muted="#6A6357", proved="#2C6E49",
                   refuted="#A63328", unsettled="#8A6410")),
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


def system_wants_dark() -> bool:
    """Follow the operating system's own light/dark setting.

    Windows records it in the registry as AppsUseLightTheme (0 = dark). There is
    no Tk API for this, so it is read directly and every failure falls back to
    light - a wrong guess about a colour scheme should never stop the app
    opening. LOCALLLM_THEME=dark|light overrides, which is also how the check
    is tested without touching anyone's settings.

    Moved here unchanged from studio, so both halves of the window ask the same
    way. It has one known gap, stated rather than papered over: on Linux it
    always answers light, because nothing here reads the desktop's own setting
    yet. MEASURED on the operator's desk 2026-09-20, where the window opens light
    while the desktop is set dark: `gsettings get org.gnome.desktop.interface
    color-scheme` is 'prefer-dark'. That is the key, not the
    org.freedesktop.appearance this comment claimed until it was run - that name
    is the XDG portal's, read over D-Bus (org.freedesktop.portal.Settings.Read),
    and gsettings answers `No such schema` for it. Either is a reasonable thing to
    read; neither is read, and the default is light anyway, so the gap costs a
    dark-desktop operator the dark theme and costs nobody a working window.
    """
    forced = os.environ.get("LOCALLLM_THEME", "").strip().lower()
    if forced in ("dark", "light"):
        return forced == "dark"
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        with key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except Exception:                                    # noqa: BLE001
        return False


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
_SANS = ["SF Pro Text", "Segoe UI", "Cantarell", "Ubuntu", "Noto Sans",
         "DejaVu Sans"]
_MONO = ["SF Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono"]
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
