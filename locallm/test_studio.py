"""Is the studio actually usable by someone who has never heard of a transformer?

THE REQUIREMENT: as simple as possible for people who are not programmers to
understand and actually use. Preset options rather than places to type, sliders
where a slider fits, and a graph that makes more than mathematical sense to the
person looking at it.

Three of those four are mechanically checkable and are checked here. The fourth
(does the graph make sense) is a judgement, but the thing it rests on -- that the
plotted quantity is a count of characters rather than a log-probability -- is
checkable, so that is what is pinned.

RED WITNESS, against the previous version of studio.py (git 7c7959c):
    FAIL test_nothing_to_type_on_the_main_screen: 13 typing box(es) on the main
      screen: ['4' (corpus path), '4' (layers), '4' (heads), '256' (embed dim),
      '128' (context), '0.1' (dropout), '2000' (steps), '32' (batch size),
      '0.0011' (learn rate), '100' (eval every), '1337' (seed), 'out_gui'
      (save to), '400' (tokens), '0.8' (temp), '40' (top-k)]
    FAIL test_there_are_sliders: no ttk.Scale anywhere in the window
    FAIL test_the_graph_is_in_characters_not_log_probability

These run against a real Tk window, withdrawn so nothing appears on screen.
"""
from __future__ import annotations
import pytest

pytest.importorskip("tkinter", exc_type=ImportError)   # the GUI needs Tk; a machine without it skips these by name


import math
import pathlib
import sys
import tkinter as tk
from tkinter import ttk

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import studio  # noqa: E402


# One hidden Tk for the whole file. Creating and destroying a root per test
# makes Tcl emit "application has been destroyed" noise from ttk::ThemeChanged,
# which buries the actual results.
_ROOT = tk.Tk()
_ROOT.withdraw()


def _studio():
    """A fresh Studio in its own container, so tests cannot leak into each other."""
    container = ttk.Frame(_ROOT)
    return container, studio.Studio(container)


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _descends_from(widget, ancestor) -> bool:
    w = widget
    while w is not None:
        if w is ancestor:
            return True
        w = getattr(w, "master", None)
    return False


# ---------------------------------------------------------------------------
# "preset options not places to type"
# ---------------------------------------------------------------------------
def test_nothing_to_type_on_the_main_screen():
    """The only typing box a beginner ever sees is the one where they type the
    words they want the AI to continue. Everything else is a preset, a slider or
    a button. Advanced settings are exempt -- they are behind a shut door."""
    root, s = _studio()
    try:
        typing = []
        for w in _walk(root):
            if isinstance(w, (ttk.Entry, tk.Entry)):
                if _descends_from(w, s.adv):
                    continue                      # behind the advanced door
                var = str(w.cget("textvariable"))
                if var == str(s.v_prompt):
                    continue                      # the one legitimate text box
                typing.append(w.get())
        assert not typing, \
            f"{len(typing)} typing box(es) on the main screen: {typing}"
    finally:
        root.destroy()


def test_the_advanced_door_is_shut_to_begin_with():
    root, s = _studio()
    try:
        assert not s.advanced_open
        assert not s.adv.winfo_ismapped(), "advanced settings are visible on startup"
        assert "Show advanced" in s.b_adv.cget("text")
    finally:
        root.destroy()


def test_the_advanced_door_still_opens_and_keeps_every_old_knob():
    """Simplifying must not remove capability from someone who knows what the
    knobs are for."""
    root, s = _studio()
    try:
        s._toggle_advanced()
        assert s.advanced_open and "Hide advanced" in s.b_adv.cget("text")
        for name in ("v_layer", "v_head", "v_embd", "v_block", "v_drop",
                     "v_steps", "v_batch", "v_lr", "v_eval", "v_seed",
                     "v_out", "v_cpu"):
            assert hasattr(s, name), f"the old setting {name} was dropped"
    finally:
        root.destroy()


def test_every_size_preset_is_a_combination_that_actually_works():
    """The old UI let you type 4 heads and 250 embed dim and only told you off
    afterwards. A preset must never be able to produce that."""
    root, s = _studio()
    try:
        for name in studio.SIZES:
            s.size_name.set(name)
            s._apply_preset()
            embd, head = int(s.v_embd.get()), int(s.v_head.get())
            assert embd % head == 0, f"{name}: {embd} does not divide by {head} heads"
            assert int(s.v_steps.get()) >= 200, f"{name}: too few steps"
            assert float(s.v_lr.get()) > 0
    finally:
        root.destroy()


def test_the_presets_drive_the_advanced_fields_and_not_the_other_way():
    """One source of truth. Picking a size must rewrite the hidden numbers, or
    the two can disagree and the user is told something false."""
    root, s = _studio()
    try:
        s.size_name.set("Small"); s._apply_preset()
        small = s.v_embd.get()
        s.size_name.set("Large"); s._apply_preset()
        large = s.v_embd.get()
        assert small != large, "changing the size preset changed nothing"
        assert int(large) > int(small)
    finally:
        root.destroy()


def test_longer_practice_means_more_steps():
    root, s = _studio()
    try:
        got = {}
        for name in studio.LENGTHS:
            s.length_name.set(name); s._apply_preset()
            got[name] = int(s.v_steps.get())
        assert got["Quick look"] < got["Normal"] < got["Thorough"], got
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# "sliders for certain things"
# ---------------------------------------------------------------------------
def test_there_are_sliders():
    root, s = _studio()
    try:
        scales = [w for w in _walk(root) if isinstance(w, (ttk.Scale, tk.Scale))]
        assert len(scales) >= 2, f"expected sliders, found {len(scales)}"
    finally:
        root.destroy()


def test_the_adventurousness_slider_is_labelled_in_words_not_numbers():
    root, s = _studio()
    try:
        seen = []
        for i in range(len(studio.STYLES)):
            s.style_idx.set(i)
            s._style_label()
            seen.append(s.l_style.cget("text"))
        assert seen == [name for name, _, _ in studio.STYLES], seen
        for label in seen:
            assert not any(ch.isdigit() for ch in label), \
                f"the slider label shows a number: {label!r}"
    finally:
        root.destroy()


def test_the_slider_moves_temperature_and_topk_together():
    temps = [t for _, t, _ in studio.STYLES]
    topks = [k for _, _, k in studio.STYLES]
    assert temps == sorted(temps), temps
    assert topks == sorted(topks), topks
    assert temps[0] < 0.5 and temps[-1] > 1.0


def test_the_top_stop_stays_below_the_measured_cliff():
    """Measured on the 3.18M stories model: invented words run 0.9-2.1% up to
    temperature 1.20 and then TRIPLE to 6.6-7.8% at 1.30. The loosest setting
    should be loose, not broken."""
    assert max(t for _, t, _ in studio.STYLES) <= 1.20, \
        "the top stop is back over the cliff measured at temp 1.30"


def test_every_stop_says_what_it_costs():
    """A slider stop named "Wild" tells you nothing about what you will get."""
    for name, _, _ in studio.STYLES:
        assert studio.STYLE_NOTES.get(name), f"{name} has no description"
    root, s = _studio()
    try:
        for i, (name, _, _) in enumerate(studio.STYLES):
            s.style_idx.set(i)
            s._style_label()
            assert s.l_style_note.cget("text") == studio.STYLE_NOTES[name]
        s.style_idx.set(len(studio.STYLES) - 1)
        s._style_label()
        assert "invented" in s.l_style_note.cget("text").lower(), \
            "the loosest setting does not warn that words will be made up"
    finally:
        root.destroy()


def test_the_length_slider_speaks_in_words():
    root, s = _studio()
    try:
        s.sample_len.set(500)
        s._len_label()
        assert "words" in s.l_len.cget("text"), s.l_len.cget("text")
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# "the graph make more than mathematical sense"
# ---------------------------------------------------------------------------
def test_the_graph_is_in_characters_not_log_probability():
    """The plotted value must be exp(loss) -- how many characters it is still
    choosing between -- not the raw loss. That is the whole translation."""
    root, s = _studio()
    try:
        s.plot.reset(100, vocab=65)
        s.plot.add(0, train_loss=math.log(65), val_loss=math.log(65))
        step, plotted = s.plot.learn_pts[0]
        assert abs(plotted - 65) < 0.01, \
            f"at random-init loss the graph should read ~65, reads {plotted}"
        s.plot.add(50, train_loss=math.log(4), val_loss=math.log(4))
        assert abs(s.plot.learn_pts[1][1] - 4) < 0.01
    finally:
        root.destroy()


def test_the_graph_has_a_pure_guessing_reference_line():
    """Without a baseline, "7" means nothing. With one, it means "7 out of 65"."""
    root, s = _studio()
    try:
        s.plot.reset(100, vocab=65)
        s.plot._size = lambda: (600, 300)     # unmapped widgets report width 1
        s.plot.add(10, train_loss=math.log(30), val_loss=math.log(30))
        texts = [s.plot.itemcget(i, "text") for i in s.plot.find_all()
                 if s.plot.type(i) == "text"]
        assert texts, "the plot drew nothing at all"
        assert any("guessing" in t for t in texts), texts
        assert any("65" in t for t in texts), texts
        assert any("lower = smarter" in t for t in texts), texts
    finally:
        root.destroy()


def test_the_headline_says_what_the_number_means():
    root, s = _studio()
    try:
        s.vocab = 65
        at_start = s._headline(math.log(65))
        assert "guessing" in at_start.lower(), at_start
        learned = s._headline(math.log(4))
        assert "65" in learned and "%" in learned, learned
        # and it must never be the raw loss
        assert "1.386" not in learned
    finally:
        root.destroy()


def test_the_explanation_warns_about_memorising_in_plain_words():
    root, s = _studio()
    try:
        txt = s.l_explain.cget("text").lower()
        assert "memoris" in txt or "memoriz" in txt, txt
        assert "loss" not in txt, "the explanation still uses the word 'loss'"
    finally:
        root.destroy()


def test_the_untrusted_val_case_hides_the_orange_line_and_says_why():
    """The leakage machinery already decides this; the UI must act on it rather
    than draw a line that means nothing."""
    root, s = _studio()
    try:
        s.q.put(("valtrust", False))
        s._drain()
        assert s.plot.unseen_ok is False
        assert "hidden" in s.l_explain.cget("text").lower()
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# time estimates
# ---------------------------------------------------------------------------
def test_time_estimates_come_from_a_real_benchmark_or_are_not_shown():
    """A made-up "about 5 minutes" is worse than saying nothing. If this machine
    was never benchmarked the UI must say so rather than guess."""
    root, s = _studio()
    try:
        s.speeds = {}
        s._apply_preset()
        assert "not been timed" in s.l_time.cget("text"), s.l_time.cget("text")
        s.speeds = studio.load_speeds()
        if s.speeds:
            s._apply_preset()
            assert "About" in s.l_time.cget("text"), s.l_time.cget("text")
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# dark mode, following the system
# ---------------------------------------------------------------------------
def test_the_theme_follows_the_system_setting():
    import os
    was = os.environ.get("LOCALLLM_THEME")
    try:
        os.environ["LOCALLLM_THEME"] = "dark"
        assert studio.system_wants_dark() is True
        os.environ["LOCALLLM_THEME"] = "light"
        assert studio.system_wants_dark() is False
        os.environ.pop("LOCALLLM_THEME")
        assert isinstance(studio.system_wants_dark(), bool)   # reads the OS
    finally:
        if was is None:
            os.environ.pop("LOCALLLM_THEME", None)
        else:
            os.environ["LOCALLLM_THEME"] = was


def test_both_palettes_define_the_same_colours():
    light, dark = studio.THEMES["light"], studio.THEMES["dark"]
    assert set(light) == set(dark), set(light) ^ set(dark)
    for name, pal in studio.THEMES.items():
        for k, v in pal.items():
            assert v.startswith("#") and len(v) == 7, f"{name}.{k} = {v!r}"


def test_dark_mode_is_actually_dark_and_readable():
    """A palette that says "dark" while drawing dark text is worse than none."""
    import os
    was = os.environ.get("LOCALLLM_THEME")
    os.environ["LOCALLLM_THEME"] = "dark"
    try:
        root, s = _studio()
        try:
            assert s.dark is True
            assert s.C is studio.THEMES["dark"]

            def lum(hexcol):
                r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
                return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255

            assert lum(s.C["bg"]) < 0.25, s.C["bg"]
            assert lum(s.C["fg"]) > 0.7, s.C["fg"]
            # every text colour must contrast with the background it sits on
            for key in ("fg", "muted", "faint", "ok", "warn", "bad"):
                assert lum(s.C[key]) - lum(s.C["bg"]) > 0.25, \
                    f"{key} {s.C[key]} is too close to the background"
            assert s.plot.BG == s.C["plot_bg"]
        finally:
            root.destroy()
    finally:
        if was is None:
            os.environ.pop("LOCALLLM_THEME", None)
        else:
            os.environ["LOCALLLM_THEME"] = was


def test_dark_mode_leaves_no_widget_on_a_native_light_background():
    """The 'vista' ttk theme draws from native bitmaps and ignores background
    colour, so dark mode has to switch to a theme Tk draws itself or the panels
    stay light grey with pale text on them."""
    import os
    was = os.environ.get("LOCALLLM_THEME")
    os.environ["LOCALLLM_THEME"] = "dark"
    try:
        root, s = _studio()
        try:
            assert ttk.Style().theme_use() == "clam", ttk.Style().theme_use()
        finally:
            root.destroy()
    finally:
        if was is None:
            os.environ.pop("LOCALLLM_THEME", None)
        else:
            os.environ["LOCALLLM_THEME"] = was


# ---------------------------------------------------------------------------
# fitting on the screen
# ---------------------------------------------------------------------------
def test_the_window_never_asks_for_more_than_a_small_screen_has():
    """A 1366x768 laptop is the floor. If the layout demands more than that at
    scale 1.0, someone cannot reach the Start button."""
    root, s = _studio()
    try:
        root.update_idletasks()
        assert s.winfo_reqwidth() <= 1286, s.winfo_reqwidth()
        assert s.winfo_reqheight() <= 668, s.winfo_reqheight()
    finally:
        root.destroy()


def test_the_settings_column_can_scroll():
    """Whatever the screen, the tall column must be reachable rather than cut."""
    root, s = _studio()
    try:
        assert isinstance(s._left_canvas, tk.Canvas)
        assert str(s._left_canvas.cget("yscrollcommand")), \
            "the settings column is not attached to a scrollbar"
    finally:
        root.destroy()


def test_human_time_reads_like_a_person_wrote_it():
    assert studio.human_time(45) == "45 seconds"
    assert studio.human_time(300) == "5 minutes"
    assert "hours" in studio.human_time(7200)


if __name__ == "__main__":
    fails = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn(); print(f"PASS {name}")
            except AssertionError as e:
                fails.append(name); print(f"FAIL {name}: {e}")
    print(f"\n{len(fails)} failed")
    raise SystemExit(1 if fails else 0)
