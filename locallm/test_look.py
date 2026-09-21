"""Does the design system hold up when someone changes one value in it?

Every check here is arithmetic on the values in look.py, not a snapshot of them.
That distinction is the whole point: a snapshot test tells you a colour changed,
and this tells you whether the change made the window unreadable. The contrast
ratios are recomputed from the hex in this file, with the WCAG formula written
out, so nothing here can agree with look.py by sharing a bug with it.

WHY THE FORMULA IS COPIED HERE RATHER THAN IMPORTED: look.py does not have one.
A palette module that ships its own contrast function and its own test of that
function proves nothing — the test would be checking the module against itself.

No Tk root is constructed anywhere in this file, and nothing here imports torch,
so it runs on a machine with no display and no training stack.

    python3 -m unittest test_look -v

RED WITNESS, each mutation applied to a copy of look.py and the output quoted:

    muted "#6A6357" -> "#8F8878"   (one step lighter, the change someone makes
                                    to soften secondary text)
      FAIL test_every_pair_meets_its_bar_in_both_themes: light muted on paper:
        3.02 < 4.5; light muted on card: 3.32 < 4.5; light muted on field:
        3.02 < 4.5

    faint = "#8F8878"              (the third text tier this palette refuses)
      FAIL test_every_value_is_one_of_the_eight_roles: dark faint=#8F8878 is
        not a role colour
      FAIL test_every_pair_meets_its_bar_in_both_themes: dark faint on panel:
        4.49 < 4.5 -- which is the measurement behind there being two tiers

    SCALE = (4, 6, 8, 12, 16, 24)
      FAIL test_the_scale_is_carbons: (4, 8, 12, 16, 24, 32) != (4, 6, 8, 12,
        16, 24)

    TIMED_OUT = "⌛"                (the obvious hourglass)
      FAIL test_no_mark_has_emoji_presentation: U+231B is in
        Emoji_Presentation range U+231A..U+231B
      FAIL test_the_four_marks_are_the_chosen_codepoints

    say_corpus: `if trustworthy and split:` -> `if split:`
      FAIL test_say_corpus_table (CONTAMINATED, split="corpus"):
        ('✘', 'Leaking', 'refuted') != ('–', 'Unsplittable', 'unsettled')

    _installed asks through _ask() again        (the defect found 2026-09-21:
                                                 _ask ends in str(), and str()
                                                 of a Tcl list is a Python repr)
      FAIL test_installed_families_survive_tk_answering_with_a_tuple:
        'noto sans arabic' not found in frozenset({'a', 't', 'o', 'm', "'",
        'b', '(', 'r', ')', 'l', 'c', ' ', 's', 'n', 'i', ','})
      FAIL test_a_width_coincidence_alone_never_condemns_a_script: a width
        coincidence became an accusation: A few characters here have no font on
        this computer (U+03B5) -- which is the sentence this desktop really
        produced, for a letter Cantarell draws perfectly

    _SANS = ["Noto Sans CJK SC", "SF Pro Text", ...]
      FAIL test_native_faces_lead_both_lists: ['SF Pro Text', 'Segoe UI',
        'Cantarell'] != ['Noto Sans CJK SC', 'SF Pro Text', 'Segoe UI']

    say_can_draw's fix clause dropped
      FAIL test_a_machine_with_no_font_names_one_to_install (x3): 'Noto Sans
        Arabic' not found in 'Nothing on this computer can draw Arabic, so that
        text will come out as empty boxes.'

    every script-tail family name misspelled by one character
      FAIL test_the_script_tail_is_spelled_the_way_fontconfig_spells_it: this
        machine has 225 Noto families and not one of the 11 names in the script
        tail matches any of them

    _can_draw: `return "absent" if signals else "unsure"` -> `return "absent"`
      FAIL test_a_tk_that_will_not_answer_says_so_instead_of_crying_wolf:
        'Not sure' != 'No font'

    _can_draw: the `if capable: return "drawn"` arm deleted
      FAIL test_a_width_coincidence_alone_never_condemns_a_script -- the same
        false alarm, reached the other way
"""
from __future__ import annotations

import math
import pathlib
import subprocess
import sys
import re
import unittest

# Importing tkinter needs no display; only tk.Tk() does, and the one class
# below that calls it skips itself when there is none. This file stays
# runnable on a headless machine, which is where CI and macOS both live.
import tkinter as tk

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import look  # noqa: E402


# --------------------------------------------------------------------------
# WCAG, written out from the specification rather than remembered.
#
# w3.org/WAI/GL/wiki/Relative_luminance:
#   L = 0.2126 R + 0.7152 G + 0.0722 B, where each channel is c/12.92 when
#   c <= 0.03928 and ((c + 0.055) / 1.055) ** 2.4 above it, c being the 8-bit
#   value over 255.
# The same page carries an errata notice: 0.03928 is not the IEC sRGB threshold,
# 0.04045 is, "nevertheless for 8 bit color values the difference is not
# significant". Every value in this palette is 8-bit hex, so the normative
# number is used and the errata is recorded here rather than discovered again.
#
# w3.org/WAI/GL/wiki/Contrast_ratio:
#   (L1 + 0.05) / (L2 + 0.05), lighter over darker, range 1:1 to 21:1.
#
# THE BARS. SC 1.4.3 (w3.org/WAI/WCAG21/Understanding/contrast-minimum.html):
# 4.5:1 for text, 3:1 for large-scale text, where large is 18pt or 14pt bold.
# SC 1.4.11 (.../non-text-contrast.html): 3:1 for user interface components and
# for "parts of graphics required to understand the content" — which is what a
# plotted series is. That page also says the computed ratio must NOT be rounded,
# "e.g. 2.999:1 would not meet the 3:1 threshold", so these comparisons use the
# raw float with no epsilon and no rounding.
# --------------------------------------------------------------------------
BODY = 4.5
LARGE_OR_UI = 3.0


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    assert len(h) == 6, f"expected 6-digit hex, got {hex_colour!r}"
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = out
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


class Contrast(unittest.TestCase):
    """Nobody improves a colour into illegibility without this failing."""

    # (foreground, ground, bar). Grounds are the four surfaces text is put on
    # plus the plot; the bar is 4.5 wherever the foreground is words and 3.0
    # where it is a line or an axis in the chart.
    PAIRS = (
        # words on the three surfaces
        ("ink", "paper", BODY), ("ink", "card", BODY), ("ink", "field", BODY),
        ("muted", "paper", BODY), ("muted", "card", BODY),
        ("muted", "field", BODY),
        ("proved", "paper", BODY), ("proved", "card", BODY),
        ("refuted", "paper", BODY), ("refuted", "card", BODY),
        ("unsettled", "paper", BODY), ("unsettled", "card", BODY),
        # the aliases studio and the shell actually pass to widgets
        ("fg", "bg", BODY), ("fg", "panel", BODY), ("faint", "panel", BODY),
        ("ok", "panel", BODY), ("bad", "panel", BODY), ("warn", "panel", BODY),
        ("log_fg", "log_bg", BODY),
        # a selected row keeps ink; nothing quieter is legible on the band
        ("ink", "select", BODY),
        # the chart: graphical objects, so 3:1 (all three clear 4.5 anyway)
        ("learn", "plot_bg", LARGE_OR_UI),
        ("unseen", "plot_bg", LARGE_OR_UI),
        ("guess", "plot_bg", LARGE_OR_UI),
        ("plot_axis", "plot_bg", LARGE_OR_UI),
    )

    def test_every_pair_meets_its_bar_in_both_themes(self):
        bad = []
        for theme, p in look.PALETTES.items():
            for fg, bg, bar in self.PAIRS:
                got = contrast(p[fg], p[bg])
                if got < bar:
                    bad.append(f"{theme} {fg} on {bg}: {got:.2f} < {bar}")
        self.assertEqual([], bad, "\n".join(bad))

    def test_no_pair_is_only_just_passing(self):
        """A pair at 4.50 is one rounding away from failing on someone's screen.

        The measured floor is `unsettled` on light `paper` at 4.60, so this is
        headroom the palette already has; it exists so a future edit cannot
        spend all of it and still call the suite green.
        """
        for theme, p in look.PALETTES.items():
            for fg, bg, bar in self.PAIRS:
                if bar != BODY:
                    continue
                got = contrast(p[fg], p[bg])
                self.assertGreater(got, bar + 0.05,
                                   f"{theme} {fg} on {bg} is {got:.2f}, only "
                                   f"just over {bar}")


class Surfaces(unittest.TestCase):

    def test_both_palettes_define_exactly_the_same_keys(self):
        light, dark = look.PALETTES["light"], look.PALETTES["dark"]
        self.assertEqual(set(light), set(dark))
        self.assertEqual(set(), set(look.ROLES) - set(light),
                         "a role has no value in the palette")

    def test_every_value_is_one_of_the_eight_roles(self):
        """The alias block must not smuggle in a ninth colour."""
        for theme, p in look.PALETTES.items():
            allowed = {p[r] for r in look.ROLES}
            for key, value in p.items():
                self.assertIn(value, allowed,
                              f"{theme} {key}={value} is not a role colour")

    def test_the_aliases_point_where_the_comments_say(self):
        """Pins the mapping, so an alias cannot drift off its role silently."""
        expect = {"bg": "paper", "panel": "card", "field": "paper",
                  "fg": "ink", "faint": "muted", "ok": "proved",
                  "bad": "refuted", "warn": "unsettled", "plot_bg": "card",
                  "plot_grid": "line", "plot_axis": "muted", "learn": "ink",
                  "unseen": "unsettled", "guess": "muted", "log_bg": "paper",
                  "log_fg": "ink", "select": "line"}
        for theme, p in look.PALETTES.items():
            for alias, role in expect.items():
                self.assertEqual(p[role], p[alias], f"{theme} {alias}")
        self.assertEqual(set(look.ROLES) | set(expect),
                         set(look.PALETTES["light"]),
                         "a key exists that no test knows about")

    def test_a_card_is_separated_by_both_a_fill_shift_and_a_hairline(self):
        """The fill shift alone is about 1.1:1 and vanishes on a dim screen.

        So two things are required: the fills must actually differ, and the
        hairline must out-contrast the fill shift against BOTH surfaces. A
        hairline that does less than the fill difference is decoration.
        """
        for theme, p in look.PALETTES.items():
            fill = contrast(p["card"], p["paper"])
            self.assertNotEqual(p["card"], p["paper"], theme)
            self.assertGreater(fill, 1.0, theme)
            for ground in ("paper", "card"):
                seam = contrast(p["line"], p[ground])
                self.assertGreater(
                    seam, fill,
                    f"{theme}: hairline on {ground} is {seam:.3f}, no better "
                    f"than the {fill:.3f} fill shift it is there to back up")

    def test_light_is_the_default(self):
        """An explicit override wins; with nothing readable the answer is dark.

        This test used to assert that an unreadable value meant light, and it had
        one carve-out saying "a real registry answers on Windows". Since
        2026-09-21 a real desktop answers on Linux and macOS too, so the carve-out
        was the whole test: asserting a fallback while a live probe was running
        made the result depend on the desktop it ran on, passing here and failing
        on a machine set dark. So the probes are stubbed out and the fallback is
        tested for what it is -- a decision, not a discovery. The operator asked
        for a darker window, so unknown means dark.
        """
        import os
        import subprocess
        from unittest.mock import patch
        keep = {n: os.environ.get(n) for n in ("LOCALLM_THEME", "LOCALLLM_THEME")}
        try:
            # An explicit override wins on every platform, in either spelling and
            # in any case. LOCALLLM_THEME with three Ls was the original typo and
            # still works so nobody's setup breaks.
            for name in ("LOCALLM_THEME", "LOCALLLM_THEME"):
                os.environ.pop("LOCALLM_THEME", None)
                os.environ.pop("LOCALLLM_THEME", None)
                for value, want_dark in (("dark", True), ("light", False),
                                         ("DARK", True), ("  Light ", False)):
                    os.environ[name] = value
                    self.assertEqual(want_dark, look.system_wants_dark(),
                                     f"{name}={value!r}")
                os.environ.pop(name, None)

            # With no override and nothing readable, the answer is the decision.
            for value in ("nonsense", ""):
                os.environ["LOCALLM_THEME"] = value
                with patch.object(subprocess, "run",
                                  side_effect=OSError("no desktop here")):
                    self.assertEqual(look._DARK_WHEN_UNKNOWN,
                                     look.system_wants_dark(), value)
            os.environ.pop("LOCALLM_THEME", None)
            os.environ["LOCALLM_THEME"] = "dark"
            self.assertIs(look.PALETTES["dark"], look.palette())
            self.assertIs(look.PALETTES["light"], look.palette(dark=False))
        finally:
            for name, was in keep.items():
                if was is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = was

    def test_the_scale_has_no_duplicates_and_every_space_is_on_it(self):
        self.assertEqual(len(look.SCALE), len(set(look.SCALE)))
        self.assertEqual(list(look.SCALE), sorted(look.SCALE))
        for name, value in look.SPACE._asdict().items():
            self.assertIn(value, look.SCALE, name)
        self.assertEqual(len(look.SCALE), len(look.SPACE),
                         "a step on the scale has no name, or a name has no step")

    def test_the_scale_is_carbons(self):
        """4/8/12/16/24/32 are Carbon's $spacing-02..07, not six chosen numbers.

        carbondesignsystem.com/elements/spacing/overview/. Written out so the
        next person can see the scale was adopted rather than assembled.
        """
        self.assertEqual((4, 8, 12, 16, 24, 32), look.SCALE)

    def test_two_radii_and_no_others(self):
        self.assertEqual((6, 12), tuple(look.RADIUS))
        self.assertEqual(6, look.RADIUS.control)
        self.assertEqual(12, look.RADIUS.card)


# --------------------------------------------------------------------------
# Every Emoji_Presentation range in the BMP, from
# unicode.org/Public/UCD/latest/ucd/emoji/emoji-data.txt (v18.0.0, dated
# 2026-01-30, read 2026-09-20). The file is in code point order and its first
# entry above the BMP is 1F004, so this list is COMPLETE below U+1F000 — which
# is what lets the check below be an assertion rather than a spot check: a mark
# is safe if it is in the BMP and outside every range here.
# --------------------------------------------------------------------------
EMOJI_PRESENTATION_BMP = (
    (0x231A, 0x231B), (0x23E9, 0x23EC), (0x23F0, 0x23F0), (0x23F3, 0x23F3),
    (0x25FD, 0x25FE), (0x2614, 0x2615), (0x2648, 0x2653), (0x267F, 0x267F),
    (0x2693, 0x2693), (0x26A1, 0x26A1), (0x26AA, 0x26AB), (0x26BD, 0x26BE),
    (0x26C4, 0x26C5), (0x26CE, 0x26CE), (0x26D4, 0x26D4), (0x26EA, 0x26EA),
    (0x26F2, 0x26F3), (0x26F5, 0x26F5), (0x26FA, 0x26FA), (0x26FD, 0x26FD),
    (0x2705, 0x2705), (0x270A, 0x270B), (0x2728, 0x2728), (0x274C, 0x274C),
    (0x274E, 0x274E), (0x2753, 0x2755), (0x2757, 0x2757), (0x2795, 0x2797),
    (0x27B0, 0x27B0), (0x27BF, 0x27BF), (0x2B1B, 0x2B1C), (0x2B50, 0x2B50),
    (0x2B55, 0x2B55),
)


class Marks(unittest.TestCase):

    def test_the_four_marks_are_the_chosen_codepoints(self):
        self.assertEqual("✔", look.PROVED)          # HEAVY CHECK MARK
        self.assertEqual("✘", look.REFUTED)         # HEAVY BALLOT X
        self.assertEqual("–", look.NOT_APPLICABLE)  # EN DASH
        self.assertEqual("◷", look.TIMED_OUT)       # UPPER RIGHT OR LOWER
        self.assertEqual(4, len(look.MARKS))             # LEFT AND LOWER RIGHT
        self.assertEqual(4, len(set(look.MARKS)))        # CIRCULAR ARC

    def test_no_mark_has_emoji_presentation(self):
        """An Emoji_Presentation codepoint renders as a colour emoji by default.

        ⌛ U+231B, the obvious hourglass, is the one that would: it is in the
        first range below. ◷ U+25F7 was chosen over it and over ⏱ U+23F1 for
        this reason and because DejaVu Sans has a glyph for it.
        """
        for mark in look.MARKS:
            self.assertEqual(1, len(mark), f"{mark!r} is not one codepoint")
            cp = ord(mark)
            self.assertLess(cp, 0x1F000,
                            f"U+{cp:04X} is above the BMP, where the table in "
                            f"this file stops being complete")
            for lo, hi in EMOJI_PRESENTATION_BMP:
                self.assertFalse(
                    lo <= cp <= hi,
                    f"U+{cp:04X} is in Emoji_Presentation range "
                    f"U+{lo:04X}..U+{hi:04X}")

    def test_the_hourglass_would_have_failed_that(self):
        """The check has teeth: the rejected candidate is caught by it."""
        self.assertTrue(any(lo <= 0x231B <= hi
                            for lo, hi in EMOJI_PRESENTATION_BMP))


class Sentences(unittest.TestCase):
    """say_corpus and say_progress, as a table of inputs to expectations."""

    # (kwargs, expected mark, word, tone)
    CORPUS = (
        # the three leakage verdicts on their own
        (dict(leakage_verdict="CLEAN", trustworthy=True),
         look.PROVED, "Clean", "proved"),
        (dict(leakage_verdict="SUSPECT"),
         look.NOT_APPLICABLE, "Repetitive", "unsettled"),
        (dict(leakage_verdict="CONTAMINATED"),
         look.REFUTED, "Leaking", "refuted"),
        # the three split problems, which override a trustworthy verdict
        (dict(leakage_verdict="CLEAN", trustworthy=True, split="corpus",
              achievable_val_frac=0.031),
         look.NOT_APPLICABLE, "Unsplittable", "unsettled"),
        (dict(leakage_verdict="CLEAN", trustworthy=True, split="splitter"),
         look.NOT_APPLICABLE, "Mis-split", "unsettled"),
        (dict(leakage_verdict="CLEAN", trustworthy=True, split="empty"),
         look.NOT_APPLICABLE, "No holdout", "unsettled"),
        # PRECEDENCE: an untrustworthy report keeps its own verdict. A
        # contaminated corpus relabelled "unlucky split" is a worse problem
        # described as a smaller one.
        (dict(leakage_verdict="CONTAMINATED", split="corpus",
              achievable_val_frac=0.01),
         look.REFUTED, "Leaking", "refuted"),
        (dict(leakage_verdict="SUSPECT", split="splitter"),
         look.NOT_APPLICABLE, "Repetitive", "unsettled"),
        # the check did not run: not green, and not silent
        (dict(leakage_verdict=None), look.NOT_APPLICABLE, "Not checked",
         "muted"),
        (dict(leakage_verdict=None, trustworthy=True, split="corpus"),
         look.NOT_APPLICABLE, "Not checked", "muted"),
        (dict(leakage_verdict="something else"), look.NOT_APPLICABLE,
         "Not checked", "muted"),
    )

    def test_say_corpus_table(self):
        for kwargs, mark, word, tone in self.CORPUS:
            with self.subTest(**kwargs):
                say = look.say_corpus(**kwargs)
                self.assertEqual((mark, word, tone),
                                 (say.mark, say.word, say.tone))
                self.assertTrue(say.why.endswith((".", "…")), say.why)
                self.assertIn(say.tone, look.PALETTES["light"])

    def test_say_corpus_keeps_the_achievable_fraction_in_the_sentence(self):
        say = look.say_corpus("CLEAN", trustworthy=True, split="corpus",
                              achievable_val_frac=0.031)
        self.assertIn("3.1%", say.why)
        # and says something true when the number was not passed, rather than
        # printing None into a sentence a person is meant to act on
        say = look.say_corpus("CLEAN", trustworthy=True, split="corpus")
        self.assertNotIn("None", say.why)

    def test_nothing_green_is_ever_said_about_a_check_that_did_not_run(self):
        """The one deliberate change from studio, pinned so it cannot regress.

        studio's except arm fell back to the ok colour with an empty note, so a
        crashed scan looked exactly like a passed one.
        """
        say = look.say_corpus(None)
        self.assertNotEqual("proved", say.tone)
        self.assertNotEqual(look.PROVED, say.mark)
        self.assertTrue(say.why.strip(), "an empty sentence claims nothing")

    def test_say_progress_table(self):
        vocab = 65
        table = (
            # a loss at pure guessing: exp(loss) == the whole alphabet
            (math.log(vocab), vocab, look.NOT_APPLICABLE, "Guessing",
             "unsettled"),
            # just inside the 0.95 bar is still guessing
            (math.log(vocab * 0.96), vocab, look.NOT_APPLICABLE, "Guessing",
             "unsettled"),
            # just outside it is progress
            (math.log(vocab * 0.94), vocab, look.PROVED, "Learning", "proved"),
            (1.0, vocab, look.PROVED, "Learning", "proved"),
            # no alphabet: the count is reported, nothing is claimed
            (1.0, 0, look.NOT_APPLICABLE, "Unmeasured", "muted"),
            # a wild loss is clamped at 20 rather than overflowing
            (1e9, vocab, look.NOT_APPLICABLE, "Guessing", "unsettled"),
        )
        for loss, v, mark, word, tone in table:
            with self.subTest(loss=loss, vocab=v):
                say = look.say_progress(loss, v)
                self.assertEqual((mark, word, tone),
                                 (say.mark, say.word, say.tone))

    def test_say_progress_counts_characters_not_log_probability(self):
        """exp(loss) is the point: the number of characters still in play."""
        say = look.say_progress(math.log(4), 65)
        self.assertIn("4.0 of 65", say.why)
        self.assertIn("95% of the way", say.why)     # (1 - 3/64) * 100
        say = look.say_progress(1e9, 0)
        self.assertNotIn("inf", say.why)


class Imports(unittest.TestCase):

    def test_look_pulls_in_neither_torch_nor_studio(self):
        """It has to be importable in a bare process, which is this one."""
        self.assertNotIn("torch", sys.modules)
        self.assertNotIn("studio", sys.modules)

    def test_a_font_with_no_widget_falls_back_without_caching_the_failure(self):
        """The two families guaranteed to exist everywhere, and no memo written.

        Asking with no widget means there may be no Tk interpreter to ask
        (docs.python.org/3/library/tkinter.font.html), so the answer is Tk's own
        named font — and it must NOT be remembered, or one early call poisons
        every font in the window for the session.
        """
        self.assertEqual("TkDefaultFont", look.SANS(11)[0])
        self.assertEqual("TkFixedFont", look.MONO(10)[0])
        self.assertEqual({}, look._resolved)
        self.assertEqual((("TkDefaultFont", 13, "bold")), look.SANS(13, "bold"))

    def test_native_faces_lead_both_lists(self):
        """Inter is off the front of the sans list, on purpose.

        It is installed on the operator's desktop for something else, so with
        Inter first this window rendered in a face nothing else on that desktop
        uses — an unspecified default wearing a decision's clothes.

        THE SCRIPT TAIL MUST NOT DISTURB THIS. _family takes the first installed
        name, so what the tail can and cannot do is decided entirely by where it
        sits: every native face and both generic Latin fallbacks come first, and
        a face that covers Arabic or Chinese can only win on a machine that has
        none of them. This used to assert DejaVu Sans was the last name in the
        sans list, which stopped being the way to say "the Latin fallbacks come
        last among the Latin faces" the moment a tail existed.
        """
        self.assertEqual(["SF Pro Text", "Segoe UI", "Cantarell"],
                         look._SANS[:3])
        self.assertNotIn("Inter", look._SANS)
        self.assertEqual(["SF Mono", "Consolas"], look._MONO[:2])

        # The Latin head, in order, ending in the two faces a bare Linux box has.
        self.assertEqual(["SF Pro Text", "Segoe UI", "Cantarell", "Ubuntu",
                          "Noto Sans", "DejaVu Sans"], look._SANS[:6])
        self.assertEqual(["SF Mono", "Consolas", "JetBrains Mono",
                          "DejaVu Sans Mono"], look._MONO[:4])

        # And every script face is behind them, which is the whole safety
        # property: the tail changes nothing for anyone who has a Latin UI face.
        for names, latin in ((look._SANS, "DejaVu Sans"),
                             (look._MONO, "DejaVu Sans Mono")):
            for tail in names[names.index(latin) + 1:]:
                self.assertGreater(names.index(tail), names.index(latin),
                                   f"{tail} must not outrank {latin}")


# --------------------------------------------------------------------------
# CAN THIS COMPUTER DRAW SOMEBODY ELSE'S LANGUAGE?
#
# Two kinds of check below, and the difference is the point. The FAKE-TK tests
# describe a machine rather than this one: they are the only way to see what
# somebody with no Arabic font is told, which is the case the whole feature
# exists for and the one case this desktop cannot reproduce, having 361 family
# names installed. The fc-list tests measure THIS machine and assert only what a
# measurement can support.
#
# Neither kind opens a window. say_can_draw's questions all go through one tiny
# surface — w.tk.call("font", ...) and w.tk.splitlist — so a stand-in answers
# them, and these run where CI runs.
# --------------------------------------------------------------------------


class FakeTk:
    """The parts of a Tk interpreter the glyph check asks questions of.

    THE ONE BEHAVIOUR IT IS CAREFUL TO COPY is the one that makes the problem
    hard, and it was read from Tk's own source rather than guessed: GetFont()
    walks the faces for one whose charset holds the codepoint and, when none
    does, ends at `i = 0` and returns THE BASE FACE
    (github.com/tcltk/tk/blob/core-8-6-branch/unix/tkUnixRFont.c). So "nothing
    installed can draw this" and "the base font draws it" are the same answer
    from outside, and a fake that made them distinguishable would be testing an
    easier problem than the real one.

    `font families` answers with a TUPLE on purpose — see the tuple test below.
    """

    MISSING = 10          # the advance a font uses for "I do not have this"
    PRESENT = 7

    def __init__(self, covers, fixed=(), coincide=()):
        self.covers = covers          # family -> the codepoints it can draw
        self.fixed = set(fixed)       # families that report `metrics -fixed 1`
        # Codepoints this face DRAWS but draws at exactly the missing-glyph
        # advance. Not a contrivance: measured at size 12, sixteen present
        # DejaVu Sans letters share that advance, and Cantarell's ε is one.
        self.coincide = set(coincide)

    def _face_for(self, base, cp):
        if cp in self.covers.get(base, frozenset()):
            return base
        for family, cps in self.covers.items():
            if cp in cps:
                return family
        return base                   # GetFont's `i = 0`, see the docstring

    def call(self, *args):
        what = args[1]
        if what == "families":
            return tuple(self.covers)
        family = args[2][0]
        if what == "metrics":
            return 1 if family in self.fixed else 0
        char = args[-1]
        if what == "actual":
            return self._face_for(family, ord(char))
        if what == "measure":
            drawn = (ord(char) in self.covers.get(family, frozenset())
                     and ord(char) not in self.coincide)
            return self.PRESENT if drawn else self.MISSING
        raise AssertionError(f"unexpected font subcommand {what!r}")

    def splitlist(self, value):
        return value                  # tkinter passes a tuple straight through


class MuteTk:
    """A Tk that will not answer, which is a real state and not an error.

    The widget may belong to a window this page did not create, so every
    question can come back with nothing. What must never happen is that silence
    turns into a verdict.
    """

    def call(self, *args):
        raise RuntimeError("no display")

    def splitlist(self, value):
        return value


class FakeWidget:

    def __init__(self, tk_, path="."):
        self.tk = tk_
        self._path = path

    def __str__(self):
        return self._path


class GlyphCheck(unittest.TestCase):
    """What a person is told about their own writing, on a described machine."""

    SANS, MONO = "Latin Sans", "Latin Mono"

    #: The three the task named, and they are read left to right as a person
    #: would type them: "hello world" in each.
    SAMPLES = {
        "Arabic": "مرحبا بالعالم",
        "Chinese": "你好世界",
        "Devanagari": "नमस्ते दुनिया",
    }

    def setUp(self):
        self._saved = (dict(look._resolved), dict(look._glyph_memo),
                       dict(look._families_memo))
        for memo in (look._resolved, look._glyph_memo, look._families_memo):
            memo.clear()

    def tearDown(self):
        for memo, saved in zip(
                (look._resolved, look._glyph_memo, look._families_memo),
                self._saved):
            memo.clear()
            memo.update(saved)

    def machine(self, extra=None, path="."):
        """A computer whose two UI faces are Latin-only, plus whatever else.

        Latin-only is the shape of the defect: every face at the front of both
        lists in look.py is a Latin UI face, so this is the stock machine the
        person with Arabic or Chinese text actually sits down at.
        """
        latin = set(range(0x20, 0x250))
        covers = {self.SANS: set(latin), self.MONO: set(latin)}
        covers.update({k: set(v) for k, v in (extra or {}).items()})
        look._resolved.update(sans=self.SANS, mono=self.MONO)
        return FakeWidget(FakeTk(covers, fixed=[self.MONO]), path)

    def test_every_sample_script_gets_a_say_and_never_an_exception(self):
        """A Say back for Arabic, Chinese and Devanagari, asked every way.

        With no widget, with a machine that cannot draw them and with one that
        can — three different answers, all of them a Say with a mark from MARKS
        and a tone that is a palette key, because the caller puts this straight
        on a label and must never have to handle an exception while somebody
        is typing.
        """
        cannot = self.machine()
        can = self.machine({"Noto Sans Arabic": range(0x600, 0x700),
                            "Noto Sans CJK SC": range(0x4E00, 0xA000),
                            "Noto Sans Devanagari": range(0x900, 0x980)},
                           path=".can")
        for name, text in sorted(self.SAMPLES.items()):
            for label, widget in (("no widget", None), ("bare", cannot),
                                  ("equipped", can)):
                with self.subTest(script=name, machine=label):
                    say = look.say_can_draw(text, widget)
                    self.assertIsInstance(say, look.Say)
                    self.assertIn(say.mark, look.MARKS)
                    self.assertIn(say.tone, look.ROLES)
                    self.assertTrue(say.word)
                    self.assertTrue(say.why.strip().endswith("."))

    def test_a_machine_with_no_font_names_one_to_install(self):
        """The sentence has to be actionable, which means a family name in it.

        "Your text needs a font this computer does not have" on its own leaves
        somebody exactly where the empty boxes did.
        """
        expected = {"Arabic": "Noto Sans Arabic",
                    "Chinese": "Noto Sans CJK SC",
                    "Devanagari": "Noto Sans Devanagari"}
        for name, text in sorted(self.SAMPLES.items()):
            with self.subTest(script=name):
                say = look.say_can_draw(text, self.machine(path=f".{name}"))
                self.assertEqual(look.REFUTED, say.mark)
                self.assertEqual("No font", say.word)
                self.assertEqual("refuted", say.tone)
                self.assertIn(expected[name], say.why)
                self.assertIn("empty boxes", say.why)

    def test_the_sentence_names_the_writing_system_a_person_would_say(self):
        """Not a codepoint range and not a font name: what they call it."""
        said = {name: look.say_can_draw(text, self.machine(path=f".s{name}")).why
                for name, text in self.SAMPLES.items()}
        self.assertIn("Arabic", said["Arabic"])
        self.assertIn("Devanagari", said["Devanagari"])
        # One entry covers the whole CJK collection because one font file does,
        # and naming "Japanese" at somebody typing Chinese would be worse.
        self.assertIn("Chinese, Japanese or Korean", said["Chinese"])

    def test_installing_one_family_turns_the_same_text_readable(self):
        """The check has to be able to change its mind, or it says nothing.

        Same three strings, same code, one font added to the machine each time.
        """
        for name, family in (("Arabic", "Noto Sans Arabic"),
                             ("Chinese", "Noto Sans CJK SC"),
                             ("Devanagari", "Noto Sans Devanagari")):
            with self.subTest(script=name):
                text = self.SAMPLES[name]
                cps = {ord(c) for c in text if ord(c) > 0x7F}
                say = look.say_can_draw(text,
                                        self.machine({family: cps},
                                                     path=f".fix{name}"))
                self.assertEqual(look.PROVED, say.mark)
                self.assertEqual("Readable", say.word)
                self.assertEqual("proved", say.tone)

    def test_ascii_is_never_questioned(self):
        """The window's own labels are the evidence, so it costs no round trip."""
        say = look.say_can_draw("hello world", self.machine())
        self.assertEqual(look.PROVED, say.mark)
        self.assertEqual((), look.scripts_in("hello world"))
        self.assertEqual(("Arabic",), look.scripts_in("مرحبا"))

    def test_nothing_is_claimed_about_text_that_was_never_checked(self):
        """No widget and no text are both "not checked", never a green tick."""
        for text, widget in (("مرحبا", None), ("   ", None),
                             ("", self.machine()), ("   ", self.machine())):
            say = look.say_can_draw(text, widget)
            self.assertEqual("Not checked", say.word)
            self.assertEqual("muted", say.tone)
            self.assertEqual(look.NOT_APPLICABLE, say.mark)

    def test_a_tk_that_will_not_answer_says_so_instead_of_crying_wolf(self):
        """Silence must not become "no font", which would be a false alarm.

        Every question comes back empty here, so there is no evidence in either
        direction, and the only honest answer is that nothing is claimed.
        """
        look._resolved.update(sans=self.SANS, mono=self.MONO)
        w = FakeWidget(MuteTk(), ".mute")
        say = look.say_can_draw(self.SAMPLES["Arabic"], w)
        self.assertEqual("Not sure", say.word)
        self.assertEqual("unsettled", say.tone)
        self.assertEqual(frozenset(), look._installed(w))
        # And the failure is not remembered, for the reason _family does not
        # cache its fallback: one early miss would poison the whole session.
        self.assertNotIn(".mute", look._families_memo)

    def test_installed_families_survive_tk_answering_with_a_tuple(self):
        """The defect this check was silently failing on until 2026-09-21.

        `font families` arrives from tkinter as a PYTHON TUPLE, and the helper
        that asked for it ended in str() — right for the three questions that
        answer with a single value, wrong here, because str() of a tuple is
        Python source. Measured on the operator's desktop, the answer came back
        beginning `('Noto Sans Gurmukhi', 'Inter Display', 'Noto Sans Display',`
        and splitlist then cut that repr on its spaces into 314 fragments like
        `('Noto` and `Sans`. Not one real family name survived, so
        `"noto sans arabic" in have` was False on a machine with Noto Sans
        Arabic installed, and the family table — the third signal, and the only
        one that can name a font to install — had never once fired.

        WHAT IT COST was not silence but a false alarm, which is worse: with the
        table dead, a width coincidence was the only evidence left, and this
        desktop told a Greek speaker that their own ε U+03B5 would come out as
        an empty box. Cantarell draws ε perfectly.
        """
        w = self.machine({"Noto Sans Arabic": {0x627}}, path=".tuple")
        have = look._installed(w)
        self.assertIn("noto sans arabic", have)
        self.assertIn(self.SANS.lower(), have)
        for name in have:
            self.assertNotIn("(", name, f"a Python repr leaked into {name!r}")
            self.assertNotIn("'", name, f"a Python repr leaked into {name!r}")

    def test_a_width_coincidence_alone_never_condemns_a_script(self):
        """The Greek ε case, in the form that made it a false alarm.

        Here the base face DOES draw the character, and it happens to draw it at
        exactly the missing-glyph advance — which is not rare: measured at size
        12, sixteen present DejaVu Sans letters share that advance. Tk reports
        the base family for it either way. The only thing standing between that
        coincidence and an accusation is the family table, so this pins it.
        """
        # BOTH UI FACES COVER GREEK, as Cantarell and DejaVu Sans Mono really
        # do, so Tk answers with the base family for every letter and signal
        # one is silent. ε alone measures at the missing-glyph advance, so
        # signal two accuses ε and nothing else — which is exactly the sentence
        # this desktop produced: "a few characters here have no font (U+03B5)".
        latin_greek = set(range(0x20, 0x250)) | set(range(0x370, 0x400))
        covers = {self.SANS: set(latin_greek), self.MONO: set(latin_greek),
                  "Noto Sans": set(latin_greek)}
        look._resolved.update(sans=self.SANS, mono=self.MONO)
        w = FakeWidget(FakeTk(covers, fixed=[self.MONO], coincide={0x3B5}),
                       ".greek")
        say = look.say_can_draw("Γειά σου Κόσμε", w)
        self.assertNotEqual("Some boxes", say.word,
                            f"a width coincidence became an accusation: {say.why}")
        self.assertNotEqual("No font", say.word)
        self.assertEqual("Readable", say.word)
        self.assertEqual("proved", say.tone)

    def test_the_marks_this_window_draws_are_checked_like_anything_else(self):
        """Cantarell has no ✔ U+2714, so the marks are not exempt from this."""
        self.assertEqual(("punctuation and symbols",),
                         look.scripts_in("".join(look.MARKS)))


class ThisMachine(unittest.TestCase):
    """Measured with fc-list, so the result is this box rather than a belief.

    Measured 2026-09-21 on the operator's desktop: 694 font files under 361
    family names. Of the sans list, Cantarell, Ubuntu, Noto Sans and DejaVu Sans
    are installed and the two Apple and Microsoft faces are not, so `_family`
    lands on Cantarell; of the mono list only DejaVu Sans Mono and the three
    script faces are installed, so it lands on DejaVu Sans Mono. Of the seven
    script faces across both tails, six are installed under exactly the
    spellings look.py uses — Noto Sans CJK SC, Noto Sans CJK JP, Noto Sans
    Arabic, Noto Sans Hebrew, Noto Sans Devanagari, Noto Sans Thai — and "Noto
    Sans SC", the webfont spelling of the same Chinese face, is not, which is
    why both spellings are listed.
    """

    @staticmethod
    def families():
        """Every family name fontconfig knows, or None if it cannot be asked."""
        try:
            done = subprocess.run(["fc-list", ":", "family"],
                                  capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        if done.returncode != 0:
            return None
        return {name.strip() for line in done.stdout.splitlines()
                for name in line.split(",") if name.strip()}

    def setUp(self):
        self.have = self.families()
        if not self.have:
            self.skipTest("fc-list cannot be run here, so nothing is measured")

    def test_both_lists_resolve_to_a_face_this_machine_actually_has(self):
        """A list of names none of which is installed resolves to TkDefaultFont.

        That is the unspecified default this file exists to stop, so the
        property worth asserting is not which face wins but that a named one
        does.
        """
        for label, names in (("sans", look._SANS), ("mono", look._MONO)):
            with self.subTest(list=label):
                present = [n for n in names if n in self.have]
                self.assertTrue(
                    present,
                    f"no {label} candidate is installed here, so this window "
                    f"would fall back to Tk's own font: {names}")

    def test_the_script_tail_is_spelled_the_way_fontconfig_spells_it(self):
        """A family name one letter off does nothing and says nothing about it.

        This is the failure mode the whole tail is exposed to, so it is checked
        against the machine rather than against memory. A box with no Noto fonts
        at all cannot answer the question, and says so rather than passing.
        """
        tail = look._SANS[6:] + look._MONO[4:]
        noto = {n for n in self.have if n.startswith("Noto")}
        if not noto:
            self.skipTest("no Noto family is installed, so spelling cannot be "
                          "measured here")
        found = [n for n in tail if n in self.have]
        self.assertTrue(
            found,
            f"this machine has {len(noto)} Noto families and not one of the "
            f"{len(tail)} names in the script tail matches any of them, which "
            f"means the tail is spelled wrong: {sorted(noto)[:12]}")

    def test_the_families_named_as_a_fix_exist_where_they_are_installed(self):
        """Every fix sentence names a real family, checked where it can be.

        The table names faces for machines other than this one, so absence
        proves nothing and is not asserted. What IS asserted is that no name in
        it is a near-miss of an installed family — a trailing space, a doubled
        space, or a lowercase spelling that fontconfig would not match.
        """
        folded = {n.casefold(): n for n in self.have}
        for script in look._SCRIPTS:
            for family in script.families:
                with self.subTest(script=script.name, family=family):
                    self.assertEqual(family.strip(), family)
                    self.assertNotIn("  ", family)
                    match = folded.get(family.casefold())
                    if match is not None:
                        self.assertEqual(match, family)



class RememberedGeometry(unittest.TestCase):
    """A window position is data about a machine's displays at one moment.

    By the next launch the projector is unplugged or the laptop is off the dock,
    and a geometry applied without reconciling opens the window where a monitor
    used to be. These are the cases that matter, and the third is the one that was
    actually broken: t/lab.py clamped with fit_to_screen and then applied the saved
    string afterwards, unclamped.
    """

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.root.withdraw()
        self.W = self.root.winfo_screenwidth()
        self.H = self.root.winfo_screenheight()

    def tearDown(self):
        self.root.destroy()

    def _parts(self, spec):
        found = re.match(r"^(\d+)x(\d+)\+(\d+)\+(\d+)$", spec)
        self.assertIsNotNone(found, spec)
        return [int(g) for g in found.groups()]

    def test_a_geometry_that_already_fits_is_left_alone(self):
        self.assertEqual("900x600+10+30",
                         look.clamp_geometry(self.root, "900x600+10+30"))

    def test_a_position_from_a_monitor_that_is_gone_comes_back_on_screen(self):
        spec = look.clamp_geometry(self.root, f"800x600+{self.W + 900}+{self.H + 700}")
        w, h, x, y = self._parts(spec)
        self.assertTrue(0 <= x and x + w <= self.W, spec)
        self.assertTrue(0 <= y and y + h <= self.H, spec)

    def test_a_window_larger_than_this_screen_is_shrunk_to_fit(self):
        w, h, x, y = self._parts(
            look.clamp_geometry(self.root, f"{self.W * 3}x{self.H * 3}+0+0"))
        self.assertLessEqual(w, self.W)
        self.assertLessEqual(h, self.H)

    def test_a_negative_offset_means_from_the_far_edge_and_is_resolved(self):
        # Tk reads -20 as twenty pixels in from the right, not as minus twenty.
        w, h, x, y = self._parts(look.clamp_geometry(self.root, "800x600-20-40"))
        self.assertEqual(self.W - 800 - 20, x)
        self.assertEqual(self.H - 600 - 40, y)

    def test_a_string_that_is_not_a_geometry_is_refused_rather_than_guessed(self):
        for junk in ("", "not a geometry", "1400x900", "x+1+1", "1400*900+0+0"):
            self.assertIsNone(look.clamp_geometry(self.root, junk), junk)

if __name__ == "__main__":
    unittest.main(verbosity=2)
