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

Dependencies: torch + tkinter (stdlib). Nothing else.
"""
from __future__ import annotations

import json
import math
import os
import queue
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
import runlog  # noqa: E402

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
# COLOURS, in one place and per theme.
#
# They were scattered as literals through the widgets, which is why the app was
# light-only: there was no single thing to change. Both palettes are defined
# here and every widget reads from the active one.
# --------------------------------------------------------------------------
THEMES = {
    "light": dict(
        bg="#f0f0f0", panel="#f0f0f0", fg="#1a1c20", muted="#666a70",
        faint="#7a7f87", ok="#2d7d46", warn="#8a6100", bad="#c0392b",
        field="#ffffff", plot_bg="#14161a", plot_grid="#2a2f38",
        plot_axis="#8a91a0", learn="#4da3ff", unseen="#ff9f43",
        guess="#5a6273", log_bg="#14161a", log_fg="#c8d0dc"),
    "dark": dict(
        bg="#1b1d21", panel="#22252a", fg="#e6e8ec", muted="#a2a8b2",
        faint="#8b919b", ok="#5fd08a", warn="#e0b050", bad="#ff6b5e",
        field="#2a2e34", plot_bg="#101215", plot_grid="#2a2f38",
        plot_axis="#8a91a0", learn="#5fb0ff", unseen="#ffb066",
        guess="#6b7280", log_bg="#101215", log_fg="#c8d0dc"),
}


def system_wants_dark() -> bool:
    """Follow the operating system's own light/dark setting.

    Windows records it in the registry as AppsUseLightTheme (0 = dark). There is
    no Tk API for this, so it is read directly and every failure falls back to
    light - a wrong guess about a colour scheme should never stop the app
    opening. LOCALLLM_THEME=dark|light overrides, which is also how the check
    is tested without touching anyone's settings.
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


def human_time(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f} seconds"
    if seconds < 5400:
        return f"{seconds / 60:.0f} minutes"
    return f"{seconds / 3600:.1f} hours"


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
                             font=("Segoe UI", 8),
                             text=f"{hi - (hi - lo) * i / 4:.0f}")

        self.create_text(14, (y0 + y1) / 2, anchor="center", angle=90,
                         fill=self.AXIS, font=("Segoe UI", 8),
                         text="characters it's choosing between  (lower = smarter)")
        self.create_text((x0 + x1) / 2, h - 9, fill=self.AXIS,
                         font=("Segoe UI", 8), text="training progress →")

        def to_xy(step, val):
            fx = x0 + (x1 - x0) * (step / self.total_steps)
            fy = y1 - (y1 - y0) * ((val - lo) / (hi - lo))
            return fx, max(y0, min(y1, fy))

        if self.vocab:
            _, gy = to_xy(0, self.vocab)
            self.create_line(x0, gy, x1, gy, fill=self.GUESS, dash=(4, 3))
            self.create_text(x0 + 6, gy - 9, anchor="w", fill=self.GUESS,
                             font=("Segoe UI", 8),
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
                             font=("Segoe UI", 9), text=label)
        if not self.unseen_ok and self.learn_pts:
            self.create_text(x1 - 6, y0 + 4 + 15, anchor="ne", fill=self.GUESS,
                             font=("Segoe UI", 8),
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

        text = Path(c["data"]).read_text(encoding="utf-8", errors="ignore")
        tok = CharTokenizer.from_text(text)
        corpus = Corpus(text, tok, device)
        self.q.put(("vocab", tok.vocab_size))
        self.log(f"Your text: {len(text):,} characters, {tok.vocab_size} different "
                 f"characters. Training on {'the CPU' if device == 'cpu' else 'the graphics card'}.")

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
    def __init__(self, root):
        super().__init__(root, padding=10)
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
        self.dark = system_wants_dark()
        self.C = THEMES["dark" if self.dark else "light"]
        self._apply_theme()
        self.speeds = load_speeds()
        self.advanced_open = False
        self.val_ok = True

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
        self.after(100, self._drain)

    def _apply_theme(self):
        """Restyle ttk for the active palette.

        On Windows the default 'vista' theme draws its widgets from native
        bitmaps and IGNORES background colour, so a dark palette produced light
        grey boxes with pale text on them - unreadable, and worse than not
        offering dark mode at all. 'clam' is drawn by Tk itself and does honour
        the colours, so dark mode switches theme as well as palette. Light mode
        keeps 'vista' because it should look like the rest of Windows.
        """
        C = self.C
        style = ttk.Style()
        try:
            style.theme_use("clam" if self.dark else "vista")
        except tk.TclError:
            pass
        if not self.dark:
            return
        style.configure(".", background=C["bg"], foreground=C["fg"],
                        fieldbackground=C["field"], bordercolor=C["panel"],
                        lightcolor=C["panel"], darkcolor=C["panel"])
        style.configure("TFrame", background=C["bg"])
        style.configure("TLabel", background=C["bg"], foreground=C["fg"])
        style.configure("TLabelframe", background=C["bg"], bordercolor="#3a3f47")
        style.configure("TLabelframe.Label", background=C["bg"],
                        foreground=C["fg"])
        style.configure("TRadiobutton", background=C["bg"], foreground=C["fg"])
        style.configure("TCheckbutton", background=C["bg"], foreground=C["fg"])
        style.configure("TButton", background=C["panel"], foreground=C["fg"])
        style.map("TButton",
                  background=[("active", "#333840"), ("disabled", C["bg"])],
                  foreground=[("disabled", C["faint"])])
        style.map("TRadiobutton", background=[("active", C["bg"])])
        style.configure("TEntry", fieldbackground=C["field"],
                        foreground=C["fg"], insertcolor=C["fg"])
        style.configure("TScale", background=C["bg"], troughcolor=C["field"])
        style.configure("TScrollbar", background=C["panel"],
                        troughcolor=C["bg"], arrowcolor=C["fg"])
        self.winfo_toplevel().configure(bg=C["bg"])

    # ---------------------------------------------------------------- left
    def _build_left(self):
        # SCROLLABLE, so the column can never be taller than the screen.
        # The settings column is the tall part of this window, and on a laptop
        # or a scaled display it is exactly what runs off the bottom and takes
        # the Start button with it. A scrollbar that appears only when it is
        # needed is the difference between "cramped" and "the button is gone".
        outer = ttk.Frame(self)
        outer.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        outer.rowconfigure(0, weight=1)
        canvas = tk.Canvas(outer, highlightthickness=0, borderwidth=0,
                           width=340, bg=self.C["bg"])
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
        left.bind("<Configure>", _fit)
        canvas.bind("<Configure>", _fit)
        canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
            if str(canvas) in str(e.widget) or self._left_bar.winfo_ismapped()
            else None)

        # --- 1. text
        box = ttk.LabelFrame(left, text=" 1 · What should it learn from? ")
        box.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        box.columnconfigure(0, weight=1)
        self.v_data = tk.StringVar(value=str(HERE / "corpus.txt"))
        self.l_file = ttk.Label(box, text="—", font=("Segoe UI", 9, "bold"))
        self.l_file.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 0))
        self.l_corpus = ttk.Label(box, text="—", foreground=self.C["muted"],
                                  wraplength=300, justify="left")
        self.l_corpus.grid(row=1, column=0, sticky="w", padx=10, pady=(2, 4))
        brow = ttk.Frame(box)
        brow.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 9))
        ttk.Button(brow, text="Get better text…",
                   command=self._get_corpus).grid(row=0, column=0)
        ttk.Button(brow, text="Use my own file…", command=self._browse).grid(
            row=0, column=1, padx=(6, 0))

        # --- 2. size
        arch = ttk.LabelFrame(left, text=" 2 · How big should it be? ")
        arch.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        arch.columnconfigure(0, weight=1)
        # Radio and blurb get their OWN rows. Sharing one cell and separating
        # them with padding put the description on top of the option's name, so
        # the three sizes rendered with no readable labels at all.
        for i, name in enumerate(SIZES):
            ttk.Radiobutton(arch, text=name, value=name, variable=self.size_name,
                            command=self._apply_preset).grid(
                row=2 * i, column=0, sticky="w", padx=10,
                pady=(8 if i == 0 else 6, 0))
            ttk.Label(arch, text=SIZES[name]["blurb"], foreground=self.C["faint"],
                      wraplength=280, justify="left").grid(
                row=2 * i + 1, column=0, sticky="w", padx=(30, 10), pady=(0, 2))
        self.l_params = ttk.Label(arch, text="", font=("Segoe UI", 9, "bold"),
                                  foreground=self.C["ok"], wraplength=300,
                                  justify="left")
        self.l_params.grid(row=2 * len(SIZES), column=0, sticky="w",
                           padx=10, pady=(6, 9))

        # --- 3. how long
        tr = ttk.LabelFrame(left, text=" 3 · How long should it practise? ")
        tr.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        tr.columnconfigure(0, weight=1)
        for i, name in enumerate(LENGTHS):
            ttk.Radiobutton(tr, text=name, value=name, variable=self.length_name,
                            command=self._apply_preset).grid(
                row=i, column=0, sticky="w", padx=10, pady=(6 if i == 0 else 2, 0))
        self.l_time = ttk.Label(tr, text="", foreground=self.C["muted"], wraplength=300,
                                justify="left")
        self.l_time.grid(row=len(LENGTHS), column=0, sticky="w", padx=10, pady=(4, 9))

        # --- run
        run = ttk.Frame(left)
        run.grid(row=3, column=0, sticky="ew")
        run.columnconfigure(0, weight=1)
        self.b_train = ttk.Button(run, text="▶   Start training",
                                  command=self._start)
        self.b_train.grid(row=0, column=0, sticky="ew", ipady=8)
        self.b_stop = ttk.Button(run, text="■  Stop", command=self._stop,
                                 state="disabled")
        self.b_stop.grid(row=0, column=1, padx=(6, 0), ipady=8)

        # --- advanced, shut by default
        self.b_adv = ttk.Button(left, text="▸  Show advanced settings",
                                command=self._toggle_advanced)
        self.b_adv.grid(row=4, column=0, sticky="w", pady=(12, 0))
        self.adv = ttk.LabelFrame(left, text=" Advanced — every knob, as before ")
        self.adv.columnconfigure(1, weight=1)
        self._build_advanced()

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
                                                 padx=(10, 6), pady=1)
            ttk.Entry(self.adv, textvariable=var, width=12).grid(
                row=r, column=1, sticky="w", pady=1)
        ttk.Checkbutton(self.adv, text="force CPU", variable=self.v_cpu).grid(
            row=len(rows), column=0, columnspan=2, sticky="w", padx=10, pady=(4, 8))

        self._preset_values: dict[str, str] = {}
        for v in (self.v_layer, self.v_head, self.v_embd, self.v_block,
                  self.v_steps, self.v_batch):
            v.trace_add("write", lambda *_: self._note_custom())

    def _toggle_advanced(self):
        self.advanced_open = not self.advanced_open
        if self.advanced_open:
            self.adv.grid(row=5, column=0, sticky="ew", pady=(6, 0))
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
            font=("Segoe UI", 12, "bold"), wraplength=640, justify="left")
        self.l_headline.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.plot = LearningPlot(right, self.C, height=190)
        self.plot.grid(row=1, column=0, sticky="nsew")

        self.l_explain = ttk.Label(
            right, foreground=self.C["muted"], wraplength=640, justify="left",
            text="The blue line is how well it predicts the text you gave it. "
                 "The orange line is text it was never shown — if orange stops "
                 "falling while blue keeps going, it has started memorising "
                 "instead of learning.")
        self.l_explain.grid(row=2, column=0, sticky="ew", pady=(6, 8))

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
                           insertbackground=self.C["log_fg"], font=("Consolas", 9),
                           wrap="word", relief="flat")
        self.log.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        sb = ttk.Scrollbar(logbox, command=self.log.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.log["yscrollcommand"] = sb.set

        # --- 4. try it
        gen = ttk.LabelFrame(right, text=" 4 · Try it out ")
        gen.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        gen.columnconfigure(1, weight=1)

        ttk.Label(gen, text="Start it off with:").grid(
            row=0, column=0, padx=(10, 6), pady=(8, 2), sticky="w")
        self.v_prompt = tk.StringVar(value="def ")
        ttk.Entry(gen, textvariable=self.v_prompt).grid(
            row=0, column=1, sticky="ew", pady=(8, 2), padx=(0, 10))

        ttk.Label(gen, text="How adventurous?").grid(
            row=1, column=0, padx=(10, 6), sticky="w")
        srow = ttk.Frame(gen)
        srow.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        srow.columnconfigure(0, weight=1)
        ttk.Scale(srow, from_=0, to=len(STYLES) - 1, orient="horizontal",
                  variable=self.style_idx,
                  command=lambda *_: self._style_label()).grid(
            row=0, column=0, sticky="ew")
        self.l_style = ttk.Label(srow, text="", width=16, foreground=self.C["muted"])
        self.l_style.grid(row=0, column=1, padx=(8, 0))
        # Inside srow, not in `gen`: gen's row 2 already holds the length slider,
        # and gridding on top of it would stack two widgets in one cell.
        self.l_style_note = ttk.Label(srow, text="", foreground=self.C["faint"])
        self.l_style_note.grid(row=1, column=0, columnspan=2, sticky="w",
                               pady=(1, 0))

        ttk.Label(gen, text="How much text?").grid(
            row=2, column=0, padx=(10, 6), sticky="w", pady=(2, 8))
        lrow = ttk.Frame(gen)
        lrow.grid(row=2, column=1, sticky="ew", padx=(0, 10), pady=(2, 8))
        lrow.columnconfigure(0, weight=1)
        ttk.Scale(lrow, from_=100, to=2000, orient="horizontal",
                  variable=self.sample_len,
                  command=lambda *_: self._len_label()).grid(
            row=0, column=0, sticky="ew")
        self.l_len = ttk.Label(lrow, text="", width=16, foreground=self.C["muted"])
        self.l_len.grid(row=0, column=1, padx=(8, 0))

        self.b_gen = ttk.Button(gen, text="Write something",
                                command=self._generate, state="disabled")
        self.b_gen.grid(row=3, column=0, columnspan=2, sticky="ew",
                        padx=10, pady=(0, 10), ipady=4)

        self.status = ttk.Label(self, text="", foreground=self.C["muted"])
        self.status.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
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
            self.l_params.config(
                text=self.l_params.cget("text").split("  —")[0] + "  — edited by hand",
                foreground="#b8860b")

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
        ms = self.speeds.get(f"{dev}/{s['key']}")
        target = LENGTHS[self.length_name.get()]["seconds"]
        if ms:
            steps = max(200, int(round(target / (ms / 1000) / 100) * 100))
            self.l_time.config(
                text=f"About {human_time(steps * ms / 1000)} on this machine "
                     f"({steps:,} practice steps).  "
                     f"{LENGTHS[self.length_name.get()]['blurb']}")
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
        p = filedialog.askopenfilename(title="Pick a text file to learn from",
                                       filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if p:
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
                  font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 8))
        for i, name in enumerate(sorted(get_corpus.SOURCES)):
            s = get_corpus.SOURCES[name]
            label = {"stories": "Simple stories  (recommended)",
                     "books": "Classic books"}.get(name, name)
            ttk.Radiobutton(win, text=label, value=name, variable=choice).grid(
                row=1 + 2 * i, column=0, sticky="w", padx=14)
            ttk.Label(win, text=s["best_for"], foreground=self.C["faint"],
                      wraplength=430, justify="left").grid(
                row=2 + 2 * i, column=0, sticky="w", padx=(36, 14), pady=(0, 8))

        size_row = ttk.Frame(win)
        size_row.grid(row=9, column=0, sticky="ew", padx=14, pady=(4, 2))
        ttk.Label(size_row, text="How much?").grid(row=0, column=0)
        l_mb = ttk.Label(size_row, text="", width=22, foreground=self.C["muted"])
        ttk.Scale(size_row, from_=20, to=600, orient="horizontal", variable=mb,
                  length=250,
                  command=lambda *_: l_mb.config(
                      text=f"{int(mb.get())} MB  (~{int(mb.get())*1_000_000/1e6:.0f}M characters)")
                  ).grid(row=0, column=1, padx=8)
        l_mb.grid(row=0, column=2)
        l_mb.config(text="200 MB  (~200M characters)")

        ttk.Label(win, wraplength=430, justify="left", foreground=self.C["faint"],
                  text="Downloaded once and kept, so this is a one-time wait. "
                       "Only plain text is fetched — the model itself is always "
                       "built from scratch on this computer.").grid(
            row=10, column=0, sticky="w", padx=14, pady=(6, 8))

        btns = ttk.Frame(win)
        btns.grid(row=11, column=0, sticky="e", padx=14, pady=(0, 12))
        b_go = ttk.Button(btns, text="Download")
        b_go.grid(row=0, column=0)
        ttk.Button(btns, text="Cancel", command=win.destroy).grid(
            row=0, column=1, padx=(6, 0))

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
        p = Path(self.v_data.get())
        self.l_file.config(text=p.name)
        if not p.is_file():
            self.l_corpus.config(text="That file is not there any more.",
                                 foreground=self.C["bad"])
            self.vocab = 0
            return
        text = p.read_text(encoding="utf-8", errors="ignore")
        self.vocab = len(set(text))
        sampled = len(text) > SCAN_SAMPLE_BYTES
        sample = text[:SCAN_SAMPLE_BYTES] if sampled else text
        try:
            tr_txt, va_txt = group_split(sample)
            rep = leakage_scan(tr_txt, va_txt, doc_aligned=True)  # group_split: it is
            health = split_health(sample)
            colour = {"CLEAN": self.C["ok"], "SUSPECT": self.C["warn"],
                      "CONTAMINATED": self.C["bad"]}[rep.verdict]
            note = {"CLEAN": "Looks fine to train on.",
                    "SUSPECT": "Some passages repeat — the fairness test may be weak.",
                    "CONTAMINATED": "Heavy repetition — the fairness test will not "
                                    "mean much."}[rep.verdict]
            verdict = split_verdict(health)
            if rep.trustworthy and verdict == "corpus":
                colour = self.C["warn"]
                note = (f"This text cannot be split into a fair test — at most "
                        f"{health['achievable_val_frac']:.1%} can be held back. More, "
                        f"smaller files would help.")
            elif rep.trustworthy and verdict == "splitter":
                colour = self.C["warn"]
                note = ("Only a sliver was held back for testing, though this text "
                        "could support more — another seed would split it better.")
            elif rep.trustworthy and verdict:
                colour = self.C["warn"]
                note = "Nothing could be held back for testing."
        except Exception:                       # never let the scan block training
            colour, note, rep = self.C["ok"], "", None
        docs = len(documents(sample))
        self.l_corpus.config(
            text=f"{len(text):,} characters · {self.vocab} different characters"
                 + (f" · {docs:,} document(s)\n{note}" if not sampled else
                    f"\n{note}  (checked the first "
                    f"{SCAN_SAMPLE_BYTES // 1_000_000} MB; the full check runs "
                    f"when training starts)"),
            foreground=colour)
        # Show the "pure guessing" baseline as soon as a file is chosen, not only
        # once training starts. Before this the chart opened as an empty 1-10 box
        # with nothing to compare anything against, which is the exact problem the
        # baseline exists to solve.
        self.plot.reset(self.plot.total_steps, self.vocab)
        self._apply_preset()
        if not quiet:
            self._write(f"Loaded {p.name}: {len(text):,} characters.")
            if rep is not None:
                self._write(rep.report())

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

        self.log.delete("1.0", "end")
        self.plot.reset(cfg["steps"], self.vocab)
        self.stop_evt.clear()
        self.b_train.config(state="disabled")
        self.b_stop.config(state="normal")
        self.b_gen.config(state="disabled")
        self.l_headline.config(text="Starting…")
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
    def _headline(self, train_loss: float) -> str:
        """One sentence a person can act on, from the same number the chart plots."""
        choices = math.exp(min(train_loss, 20))
        if not self.vocab:
            return f"Narrowed down to about {choices:.0f} choices per character."
        if choices >= self.vocab * 0.95:
            return (f"Still guessing: all {self.vocab} characters look equally "
                    f"likely to it. This is where every model starts.")
        pct = (1 - (choices - 1) / max(self.vocab - 1, 1)) * 100
        return (f"It has narrowed each next character down to about "
                f"{choices:.1f} of {self.vocab} possibilities "
                f"— {pct:.0f}% of the way from guessing to certainty.")

    # -------------------------------------------------------------- pump
    def _drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self._write(payload)
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
                    self.l_headline.config(text=self._headline(m["train"]))
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
                    self.l_headline.config(
                        text="Done. " + self._headline(payload["train"]))
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
        self.after(100, self._drain)


def main():
    # DPI AWARENESS, BEFORE THE ROOT EXISTS. Windows scales unaware apps by
    # stretching their bitmap, so on a 150%-scaled display every label came out
    # soft and slightly blurred. Telling Windows we handle it ourselves, then
    # telling Tk the real pixel density, gets crisp text at any scale. Wrapped
    # because neither call exists off Windows and neither is worth failing over.
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)   # per-monitor aware
    except Exception:                                    # noqa: BLE001
        pass

    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", root.winfo_fpixels("1i") / 72.0)
    except tk.TclError:
        pass
    root.title("Train My AI — built from scratch on this computer")
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    Studio(root)
    fit_to_screen(root, want=(1180, 820))
    root.mainloop()


def fit_to_screen(root: tk.Tk, want: tuple[int, int]) -> None:
    """Size and place the window so it cannot open off-screen or clipped.

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
    root.update_idletasks()
    try:
        scale = root.winfo_fpixels("1i") / 72.0
    except tk.TclError:
        scale = 1.0

    # Leave room for the taskbar and window chrome rather than assuming none.
    avail_w = max(640, root.winfo_screenwidth() - int(80 * scale))
    avail_h = max(480, root.winfo_screenheight() - int(100 * scale))

    need_w = max(root.winfo_reqwidth(), int(want[0] * scale))
    need_h = max(root.winfo_reqheight(), int(want[1] * scale))
    w, h = min(need_w, avail_w), min(need_h, avail_h)

    x = max(0, (root.winfo_screenwidth() - w) // 2)
    y = max(0, (root.winfo_screenheight() - h) // 3)
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.minsize(min(int(760 * scale), avail_w), min(int(560 * scale), avail_h))


if __name__ == "__main__":
    main()
