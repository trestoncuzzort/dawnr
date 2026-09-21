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
"""
from __future__ import annotations

import math
import pathlib
import sys
import unittest

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
        """LOCALLLM_THEME is the only override; an unreadable value means light.

        GNOME's guidance is light by default and dark only on the system's say
        (developer.gnome.org/hig/guidelines/ui-styling.html), and the registry
        read this wraps has to be allowed to fail without stopping the window.
        """
        import os
        keep = os.environ.get("LOCALLLM_THEME")
        try:
            for value, want_dark in (("dark", True), ("light", False),
                                     ("DARK", True), ("nonsense", False),
                                     ("", False)):
                os.environ["LOCALLLM_THEME"] = value
                if value in ("nonsense", "") and sys.platform == "win32":
                    continue        # a real registry answers on Windows
                self.assertEqual(want_dark, look.system_wants_dark(), value)
            os.environ["LOCALLLM_THEME"] = "dark"
            self.assertIs(look.PALETTES["dark"], look.palette())
            self.assertIs(look.PALETTES["light"], look.palette(dark=False))
        finally:
            if keep is None:
                os.environ.pop("LOCALLLM_THEME", None)
            else:
                os.environ["LOCALLLM_THEME"] = keep


class Metrics(unittest.TestCase):

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
        """
        self.assertEqual(["SF Pro Text", "Segoe UI", "Cantarell"],
                         look._SANS[:3])
        self.assertNotIn("Inter", look._SANS)
        self.assertEqual(["SF Mono", "Consolas"], look._MONO[:2])
        self.assertEqual("DejaVu Sans", look._SANS[-1])
        self.assertEqual("DejaVu Sans Mono", look._MONO[-1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
