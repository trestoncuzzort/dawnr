"""Does the front page hold together without a display, a GPU or torch?

WHAT IS TESTED HERE. home.py is mostly layout, and layout is a judgement. What is
not a judgement is the arithmetic underneath it, the wording of every judgement it
shows, and the discipline the operator set for it — one spacing scale, one type
scale, two radii, no colour literals. All four are mechanically checkable and are
checked here, against the values in look.py rather than against a snapshot, so a
test fails when a change makes the page WRONG rather than merely different.

No Tk root is constructed anywhere in this file and nothing here imports torch,
so it runs on a machine with neither — which is the machine the page is written
for, since somebody with a USB stick has not installed anything yet.

    python3 -m unittest test_home -v

RED WITNESS, each mutation applied to a copy of home.py and the output quoted:

    edge_box: return 0.5, 0.5, width - 0.5, height - 0.5
      FAIL test_edge_box_is_integers_on_the_widgets_own_box: (0.5, 0.5, 199.5,
        79.5) is not the widget's own box in whole pixels — the measurement in
        edge_box's docstring is what this is pinning

    round_rect: the wiki's own clamp, min(d, 0.75*side)
      FAIL test_a_corner_never_overshoots_a_short_card: 20x200: corners cross
        in x, 15.0 not less than or equal to 5.0 — which is the measurement
        behind this file's clamp being side/2 rather than the wiki's 3/4

    effort_stops: `for size in sizes for length in lengths` (size-major)
      FAIL test_the_slider_never_gets_faster_as_it_moves_right: stop 2 asks for
        900s and stop 3 asks for 60s

    steps_for: untimed branch returns untimed_normal flat
      FAIL test_the_three_lengths_differ_even_when_untimed: 2000 == 2000

    say_effort: return the tick when how_long is None
      FAIL test_an_untimed_machine_claims_no_minutes: '✔' is the mark for a
        claim that holds, and no time was measured

    measure_text: `except Exception: say = look.say_corpus("CLEAN")`
      FAIL test_a_check_that_raises_is_not_a_pass: ('✔', 'Clean') — a green tick
        for a check that did not run
"""
from __future__ import annotations

import ast
import os
import pathlib
import re
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import home  # noqa: E402
import look  # noqa: E402

SOURCE = (HERE / "home.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)

# studio.py's own preset tables, copied here as FIXTURES rather than imported,
# because importing studio imports torch. They are inputs to the functions under
# test, not a second copy of a decision: nothing in home.py reads them from here,
# and test_the_fixtures_match_studio checks them against studio.py's source text
# so this file cannot drift into testing against presets that no longer exist.
SIZES = {
    "Small":  dict(key="small", n_layer=2, n_head=4, n_embd=128,
                   block_size=128, batch_size=32, blurb="Quickest."),
    "Medium": dict(key="default", n_layer=4, n_head=4, n_embd=256,
                   block_size=128, batch_size=32, blurb="The usual choice."),
    "Large":  dict(key="large", n_layer=6, n_head=8, n_embd=512,
                   block_size=256, batch_size=32, blurb="Slowest."),
}
LENGTHS = {
    "Quick look": dict(seconds=60, blurb="Enough to see it start working."),
    "Normal":     dict(seconds=300, blurb="A sensible default."),
    "Thorough":   dict(seconds=900, blurb="Better results, if you can wait."),
}


class TheFixtures(unittest.TestCase):
    def test_the_fixtures_match_studio(self):
        """The three size names and the three length names are still studio's.

        Read out of the source text, not imported, since importing studio imports
        torch. A renamed preset would make every test below pass while the page
        showed nothing, which is the failure this catches.
        """
        text = (HERE / "studio.py").read_text(encoding="utf-8")
        for name in list(SIZES) + list(LENGTHS):
            self.assertIn(f'"{name}"', text, f"{name} is no longer a studio preset")
        for name, length in LENGTHS.items():
            self.assertIn(f"seconds={length['seconds']}", text,
                          f"{name}'s wall-clock target moved")


class Geometry(unittest.TestCase):
    def test_a_rounded_rectangle_is_twelve_control_points(self):
        """Four corners of three points each, which is what the smoothed-polygon
        recipe needs: the spline breaks where two segments stop being collinear."""
        pts = home.round_rect(0, 0, 100, 60, 12)
        self.assertEqual(len(pts), 24, "twelve (x, y) control points")

    def test_the_straight_sides_are_straight(self):
        """The four points along each side share a coordinate, so Tk's spline
        draws them as a line between the midpoints rather than as a curve."""
        x0, y0, x1, y1 = 10, 20, 210, 120
        pts = home.round_rect(x0, y0, x1, y1, 12)
        xy = [(pts[i], pts[i + 1]) for i in range(0, len(pts), 2)]
        self.assertTrue(all(p[1] == y0 for p in xy[0:4]), f"top edge: {xy[0:4]}")
        self.assertTrue(all(p[0] == x1 for p in xy[3:7]), f"right edge: {xy[3:7]}")
        self.assertTrue(all(p[1] == y1 for p in xy[6:10]), f"bottom edge: {xy[6:10]}")

    def test_a_corner_never_overshoots_a_short_card(self):
        """The set-back is clamped to HALF of each side, not the wiki's 3/4.

        Its own bound lets the control points run backwards — at d = 0.75*side
        the top edge is 0, 0.75w, 0.25w, w, which draws a zig-zag. A one-row
        card is a real state of this page, so the bound has to be the real one.
        """
        for w, h in ((200, 20), (20, 200), (8, 8), (400, 300)):
            pts = home.round_rect(0, 0, w, h, look.RADIUS.card)
            xs = pts[0::2]
            ys = pts[1::2]
            self.assertLessEqual(max(xs) - min(xs), w, f"{w}x{h} is wider than its box")
            self.assertLessEqual(max(ys) - min(ys), h, f"{w}x{h} is taller than its box")
            # x0 <= xa <= xb <= x1 in both axes: the set-backs never cross.
            self.assertLessEqual(pts[0], pts[2], f"{w}x{h}: corners cross in x")
            self.assertLessEqual(pts[2], pts[4], f"{w}x{h}: corners cross in x")
            self.assertLessEqual(pts[7], pts[9], f"{w}x{h}: corners cross in y")

    def test_edge_box_is_integers_on_the_widgets_own_box(self):
        """MEASURED, see edge_box's docstring: a half-pixel coordinate loses the
        bottom and right hairlines or makes them flicker between two rows."""
        box = home.edge_box(200, 80)
        self.assertEqual(box, (0, 0, 199, 79))
        for v in box:
            self.assertIsInstance(v, int, f"{box} still has a half pixel in it")


class TheSlider(unittest.TestCase):
    def test_every_combination_is_reachable(self):
        stops = home.effort_stops(SIZES, LENGTHS)
        self.assertEqual(len(stops), 9)
        self.assertEqual(len(set(stops)), 9, "a combination is offered twice")
        for size in SIZES:
            for length in LENGTHS:
                self.assertIn(home.Stop(size, length), stops)

    def test_the_slider_never_gets_faster_as_it_moves_right(self):
        """Moving right may cost more and may give more; it may never cost less.

        This is the whole reason the ordering is length-major. Ordered by size
        first, "Small, fifteen minutes" would sit left of "Medium, one minute"
        and moving the handle right would halve the wait.
        """
        stops = home.effort_stops(SIZES, LENGTHS)
        waits = [LENGTHS[s.length]["seconds"] for s in stops]
        self.assertEqual(waits, sorted(waits), f"the wait goes down somewhere: {waits}")

    def test_within_one_wait_the_model_only_gets_bigger(self):
        stops = home.effort_stops(SIZES, LENGTHS)
        order = list(SIZES)
        for length in LENGTHS:
            band = [order.index(s.size) for s in stops if s.length == length]
            self.assertEqual(band, sorted(band), f"{length} is not in size order")

    def test_the_ends_are_the_cheapest_and_the_dearest(self):
        stops = home.effort_stops(SIZES, LENGTHS)
        self.assertEqual(stops[0], home.Stop("Small", "Quick look"))
        self.assertEqual(stops[-1], home.Stop("Large", "Thorough"))

    def test_it_opens_in_the_middle_on_studios_own_default(self):
        stops = home.effort_stops(SIZES, LENGTHS)
        self.assertEqual(home.stop_index(stops, "Medium", "Normal"), 4)

    def test_a_renamed_preset_does_not_raise_during_construction(self):
        stops = home.effort_stops(SIZES, LENGTHS)
        self.assertEqual(home.stop_index(stops, "Enormous", "Normal", 4), 4)


class Steps(unittest.TestCase):
    def test_a_measured_machine_gets_the_length_it_asked_for(self):
        """19.18 ms/step is the Small/cpu row of bench_device_result.json."""
        steps = home.steps_for(300, 19.18, 300, 2000)
        self.assertAlmostEqual(steps * 19.18 / 1000, 300, delta=15)

    def test_steps_are_round_numbers(self):
        for target in (60, 300, 900):
            self.assertEqual(home.steps_for(target, 19.18, 300, 2000) % 100, 0)

    def test_a_slow_machine_still_practises(self):
        """The floor is studio's: 200 steps, however slow the hardware. Without
        it, a minute on a machine at one step per second rounds to none at all."""
        self.assertEqual(home.steps_for(60, 1000.0, 300, 2000), 200)

    def test_the_three_lengths_differ_even_when_untimed(self):
        """The proportions do not need a benchmark; only the minutes do.

        studio's untimed path used to hand back a flat 2000 steps for all three,
        so choosing Thorough over Quick look changed the label and nothing else.
        """
        quick = home.steps_for(60, None, 300, 2000)
        normal = home.steps_for(300, None, 300, 2000)
        thorough = home.steps_for(900, None, 300, 2000)
        self.assertEqual(normal, 2000)
        self.assertLess(quick, normal)
        self.assertLess(normal, thorough)
        self.assertAlmostEqual(thorough / normal, 3.0, delta=0.1)


class WhatItSays(unittest.TestCase):
    def test_a_measured_machine_states_the_time(self):
        say = home.say_effort("Small", "Quickest.", 408_448, 3100, "4 minutes")
        self.assertEqual(say.mark, look.PROVED)
        self.assertEqual(say.word, "Small")
        self.assertEqual(say.tone, "proved")
        self.assertIn("4 minutes", say.why)
        self.assertIn("408,448", say.why, "a count with no thousands separator")

    def test_an_untimed_machine_claims_no_minutes(self):
        say = home.say_effort("Small", "Quickest.", 408_448, 3100, None)
        self.assertEqual(say.mark, look.NOT_APPLICABLE)
        self.assertEqual(say.tone, "unsettled",
                         "a claim was expected and could not be made")
        self.assertNotIn("minute", say.why.replace("the minutes", ""))

    def test_a_hand_edit_stops_the_slider_speaking_for_the_run(self):
        say = home.say_effort("Medium", "", 0, 0, "4 minutes", edited=True)
        self.assertEqual(say.tone, "unsettled")
        self.assertIn("More settings", say.why)

    def test_every_card_sentence_is_a_sentence(self):
        """No card ever shows a bare number: every Say's `why` is prose that
        ends in a full stop, which is what makes it readable out loud."""
        says = [
            home.say_effort("Small", "Quickest.", 1, 1, "4 minutes"),
            home.say_effort("Small", "Quickest.", 1, 1, None),
            home.say_effort("Small", "", 0, 0, None, edited=True),
            home.say_model(None),
            home.say_model(pathlib.Path("out_gui"), 3_194_368),
            home.say_model(pathlib.Path("out_gui"), why_not="boom"),
        ]
        for say in says:
            self.assertIn(say.mark, look.MARKS, f"{say.mark!r} is not one of look's four")
            self.assertIn(say.tone, look.PALETTES["light"], f"{say.tone} is not a palette key")
            self.assertTrue(say.why.strip().endswith((".", "!")), say.why)
            self.assertLessEqual(len(say.word.split()), 2, f"{say.word!r} is not a headline")

    def test_no_model_is_not_a_failure(self):
        """Nothing trained yet is muted, not amber: nothing has gone wrong."""
        say = home.say_model(None)
        self.assertEqual(say.tone, "muted")

    def test_a_model_that_will_not_load_is_a_refusal(self):
        say = home.say_model(pathlib.Path("out_gui"), why_not="ValueError: fingerprint")
        self.assertEqual(say.mark, look.REFUTED)
        self.assertIn("fingerprint", say.why, "the reason is shown, not swallowed")


class OnTheDisk(unittest.TestCase):
    def _model(self, folder: pathlib.Path, name: str, both: bool = True):
        d = folder / name
        d.mkdir()
        (d / "ckpt.pt").write_bytes(b"x")
        if both:
            (d / "tokenizer.json").write_text("{}")
        return d

    def test_half_a_checkpoint_is_not_a_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            self._model(folder, "weights_only", both=False)
            self.assertEqual(home.trained_models(folder), [])
            self.assertIsNone(home.ready_made(folder))

    def test_the_newest_model_is_offered_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            old = self._model(folder, "out_old")
            new = self._model(folder, "out_new")
            os.utime(old / "ckpt.pt", (1, 1))
            os.utime(new / "ckpt.pt", (2, 2))
            self.assertEqual(home.trained_models(folder), [new, old])

    def test_the_model_that_shipped_wins(self):
        """Whatever came with the stick is what "try the one that came with it"
        means, even when something newer was trained beside it."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            self._model(folder, home.INCLUDED)
            mine = self._model(folder, "out_gui")
            os.utime(folder / home.INCLUDED / "ckpt.pt", (1, 1))
            os.utime(mine / "ckpt.pt", (2, 2))
            self.assertEqual(home.ready_made(folder), folder / home.INCLUDED)

    def test_a_folder_that_cannot_be_read_is_not_a_crash(self):
        self.assertEqual(home.trained_models(pathlib.Path("/nonexistent-xyz")), [])


class LookingAtText(unittest.TestCase):
    """measure_text, with the data.py and leakage.py calls injected.

    The real ones need torch. What is under test is the precedence and the
    failure behaviour, which is where the page can lie to somebody.
    """

    def _tools(self, verdict="CLEAN", trustworthy=True, split=None, raises=False):
        class Report:
            pass
        rep = Report()
        rep.verdict, rep.trustworthy = verdict, trustworthy

        def scan(a, b, doc_aligned=True):
            if raises:
                raise RuntimeError("the scan fell over")
            return rep

        return home.Tools(
            group_split=lambda t: (t[: len(t) // 2], t[len(t) // 2:]),
            scan=scan,
            split_health=lambda t: {"achievable_val_frac": 0.02},
            split_verdict=lambda h: split,
            documents=lambda t: ["a", "b", "c"])

    def test_a_clean_corpus_says_so(self):
        facts, say = home.measure_text("hello world " * 100, 10_000, self._tools())
        self.assertEqual(say.mark, look.PROVED)
        self.assertIn("3 documents", facts)

    def test_a_split_problem_overrides_a_clean_scan(self):
        _facts, say = home.measure_text("x" * 100, 10_000,
                                        self._tools(split="corpus"))
        self.assertEqual(say.word, "Unsplittable")
        self.assertIn("2.0%", say.why, "the measured fraction, not a story about it")

    def test_a_contaminated_corpus_is_not_relabelled_as_a_split_problem(self):
        """look.say_corpus's precedence, pinned from this side too: an untrusted
        report has a worse problem than an unlucky split."""
        _facts, say = home.measure_text(
            "x" * 100, 10_000,
            self._tools(verdict="CONTAMINATED", trustworthy=False, split="corpus"))
        self.assertEqual(say.mark, look.REFUTED)

    def test_a_check_that_raises_is_not_a_pass(self):
        _facts, say = home.measure_text("x" * 100, 10_000, self._tools(raises=True))
        self.assertEqual(say.word, "Not checked")
        self.assertNotEqual(say.mark, look.PROVED,
                            "a green tick for a check that did not run")

    def test_with_no_torch_it_still_reports_the_plain_facts(self):
        facts, say = home.measure_text("abcabc", 10_000, None)
        self.assertIn("6 characters", facts)
        self.assertIn("3 different characters", facts)
        self.assertEqual(say.word, "Not checked")

    def test_a_big_file_says_it_only_checked_the_start(self):
        facts, _say = home.measure_text("x" * 5_000_000, 2_000_000, self._tools())
        self.assertIn("first 2 MB", facts)

    def test_one_document_is_not_one_documents(self):
        self.assertIn("1 document.", home.text_facts(10, 3, 1, None))
        self.assertIn("2 documents.", home.text_facts(10, 3, 2, None))


class TheDiscipline(unittest.TestCase):
    """The operator's four rules for this page, checked against the source.

    These are the rules that cannot survive as a comment: "one spacing scale",
    "four type sizes", "two radii" and "no colour literals" are exactly the kind
    of rule that decays one nudged number at a time, which is what t/lab.py's
    fourteen padding values are a record of.
    """

    def _pad_values(self):
        """Every numeric literal used as padding anywhere in home.py."""
        found = []
        for node in ast.walk(TREE):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg not in ("padx", "pady", "ipadx", "ipady", "padding"):
                    continue
                for sub in ast.walk(kw.value):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, int):
                        found.append((kw.arg, sub.value, sub.lineno))
        return found

    def test_every_padding_is_on_looks_one_scale(self):
        allowed = set(look.SCALE) | {0}
        bad = [f"line {ln}: {arg}={v}" for arg, v, ln in self._pad_values()
               if v not in allowed]
        self.assertEqual(bad, [], f"padding off look.SCALE {look.SCALE}: {bad}")

    def test_the_hairline_is_named_rather_than_typed(self):
        """One pixel is the line itself, not a seventh step on the scale, so it
        has a name — and the name is what keeps the test above meaningful."""
        self.assertEqual(home.HAIRLINE, 1)
        self.assertIn("padx=HAIRLINE", SOURCE)
        self.assertNotIn("padx=1,", SOURCE)

    def test_no_colour_is_written_as_a_literal(self):
        """Every colour comes from look.PALETTES through the palette the host
        handed over. A literal cannot follow the theme, which is how the studio
        ended up with one amber label at 2.79:1 after everything else moved."""
        hexes = re.findall(r"#[0-9A-Fa-f]{6}", SOURCE)
        docs = re.findall(r"#[0-9A-Fa-f]{6}", "\n".join(
            ast.get_docstring(n) or "" for n in ast.walk(TREE)
            if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef))))
        self.assertEqual([h for h in hexes if h not in docs], [],
                         "a colour literal outside a measurement comment")

    def test_every_font_size_is_one_of_the_four(self):
        """look.py owns the family; this file owns four sizes and nothing else."""
        bad = []
        for node in ast.walk(TREE):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ("SANS", "MONO") and node.args):
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant):
                bad.append(f"line {node.lineno}: {first.value}")
        self.assertEqual(bad, [], f"a font size that is not a TYPE step: {bad}")

    def test_the_type_scale_has_four_steps_and_they_ascend(self):
        sizes = list(home.TYPE)
        self.assertEqual(len(sizes), 4)
        self.assertEqual(sizes, sorted(sizes))
        self.assertGreater(home.TYPE.body, 10,
                           "the body text on a greeter page is larger than the studio's")

    def test_only_the_two_radii_are_drawn(self):
        """6 for a control, 12 for a card, and nothing in between."""
        radii = re.findall(r"look\.RADIUS\.(\w+)", SOURCE)
        self.assertTrue(radii, "nothing is drawn with a corner at all")
        self.assertEqual(set(radii), {"control", "card"})
        self.assertNotIn("RADIUS.control + ", SOURCE)

    def test_every_mark_shown_is_one_of_looks_four(self):
        marks = set(re.findall(r"look\.(PROVED|REFUTED|NOT_APPLICABLE|TIMED_OUT)",
                               SOURCE))
        self.assertTrue(marks <= {"PROVED", "REFUTED", "NOT_APPLICABLE", "TIMED_OUT"})
        self.assertIn("TIMED_OUT", marks,
                      "nothing on the page says 'this has not come back yet'")

    def test_torch_is_never_imported_at_module_scope(self):
        """The whole page has to open on a computer that has never installed it."""
        for node in TREE.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names]
                module = getattr(node, "module", "") or ""
                self.assertNotIn("torch", module + " " + " ".join(names))
                self.assertNotIn("studio", module + " " + " ".join(names))

    def test_the_page_imports_with_no_torch_installed(self):
        """This test file got here, which is the proof; stated so the reason the
        lazy import exists is not lost the next time somebody tidies it."""
        studio, why = home.engine()
        if studio is None:
            self.assertIn("torch", why, f"studio failed for another reason: {why}")

    def test_no_home_directory_ever_reaches_the_source(self):
        """AGENTS.md rule 7: this repository is public."""
        for needle in ("/home/", "C:\\Users"):
            self.assertNotIn(needle, SOURCE, f"{needle} is in a public file")


if __name__ == "__main__":
    unittest.main(verbosity=2)
