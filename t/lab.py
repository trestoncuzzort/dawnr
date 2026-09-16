#!/usr/bin/env python3
"""t/lab.py -- one dark window to watch the checks and to test the models
locallm builds, with every word explained (2026-09-16).

locallm builds small AI models from scratch. The models write programs in
t. Seven independent checkers each try to prove a program does what it
promises, and try to catch a deliberately broken copy of it. A program is
clean only when all seven prove it and catch the broken copy.

Live checks: every check as it runs (run_par.py writes a start and an end
line to the file named by T_WATCH, ~/.cache/t-watch/events.jsonl by
default), each result in plain words, and a loop's rounds when a loop log
is chosen.

Test a model: pick a model folder locallm wrote, say how many programs it
should write, pick the checks, press Run. Each row is one program; click it
to read the program.

Runs on macOS, Windows and Linux with Python 3.10 or newer and Tk (on macOS
the python.org installer includes Tk; with Homebrew, brew install
python-tk). Model tests also need torch, the one locallm uses:

    python3 t/lab.py
"""

from __future__ import annotations

import copy
import json
import os
import queue
import re
import shlex
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, ttk

HERE = Path(__file__).resolve().parent
TUP = HERE.parent
LOCALLM = TUP / "locallm"
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(LOCALLM))

import fuzz_lower                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402

EVENTS = Path(os.environ.get("T_WATCH", Path.home() / ".cache" / "t-watch" / "events.jsonl"))
SCRATCH = Path(os.environ.get("T_LAB_SCRATCH", Path.home() / ".cache" / "t-lab"))
KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
CHECKER = {"dafny": "Dafny", "verus": "Verus", "spark": "SPARK", "framac": "Frama-C",
           "lean": "Lean", "rocq": "Rocq", "fstar": "F*"}
KERNEL_PATH = os.pathsep.join(str(Path.home() / p) for p in (
    ".cargo/bin", ".opam/default/bin", ".elan/bin", ".local/fstar/fstar/bin",
    ".local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin", ".local/verus/verus-x86-linux"))

# dark palette: three accents, everything else greys
BG, SURFACE, CARD, LINE = "#0b0e14", "#121620", "#181d29", "#262d3d"
TEXT, MUTED, FAINT = "#e7eaf0", "#98a2b3", "#5d6678"
GREEN, RED, BLUE = "#22c55e", "#ef4444", "#3b82f6"
BLUE_DIM, GREEN_DIM, RED_DIM = "#1d3a6b", "#123d25", "#4a1a1d"
YES, NO, DASH = "✔", "✘", "–"
LOOP_RE = re.compile(r"round (\d+): corpus (\d+) docs; samples (\d+), parsed (\d+), "
                     r"well-formed (\d+), novel (\d+)")
CLEAN_RE = re.compile(r"round (\d+): clean in all seven (\d+)")


# ------------------------------------------------------------ plain words --

def verdict(real: str, twin: str) -> tuple[str, str, str, str]:
    """(symbol, short word, one plain sentence, color) for one check."""
    real, twin = (real or "").strip(), (twin or "").strip()
    if real == "verified" and twin == "refuted":
        return (YES, "Proven", "Proved the program keeps its promise, and caught the broken copy.", GREEN)
    if real == "verified":
        return (NO, "Promise too weak", "It passed, but so did a broken copy, so the promise says too little.", RED)
    if real == "vacuous":
        return (NO, "Empty promise", "It passed only because its promise can never be tested.", RED)
    if real == "refuted":
        return (NO, "Bug found", "The checker found an input where the program breaks its promise.", RED)
    if real == "unproved":
        return (NO, "Not proven", "The checker could not prove it, and found no bug either.", RED)
    if real == "timeout":
        return ("⏱", "Too slow", "The checker ran out of time. That does not mean the program is wrong.", MUTED)
    if real == "malformed":
        return ("?", "Unreadable", "The checker could not read the program.", RED)
    if real == "abstain":
        return (DASH, "Not supported yet", "This checker cannot handle this kind of program yet.", MUTED)
    if real == "no-twin":
        return (DASH, "No broken copy", "No broken copy could be made, so the promise could not be tested.", MUTED)
    return ("!", "Checker error", "The checker itself failed. This says nothing about the program.", MUTED)


def mark(v) -> str:
    return DASH if v is None else (YES if v else NO)


def pick_font(root, names, fallback):
    have = set(tkfont.families(root))
    return next((n for n in names if n in have), fallback)


# --------------------------------------------------------------- widgets --

class Tip:
    """A short explanation shown while the mouse rests on a widget."""

    def __init__(self, widget, text: str, app):
        self.widget, self.text, self.app, self.win = widget, text, app, None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, _e=None):
        if self.win:
            return
        x = self.widget.winfo_rootx() + 8
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.win = tk.Toplevel(self.widget, bg=LINE)
        self.win.wm_overrideredirect(True)
        self.win.geometry(f"+{x}+{y}")
        tk.Label(self.win, text=self.text, justify="left", bg=SURFACE, fg=TEXT, wraplength=380,
                 font=self.app.f_small, padx=10, pady=8).pack(padx=1, pady=1)

    def hide(self, _e=None):
        if self.win:
            self.win.destroy()
            self.win = None


class Button(tk.Label):
    """A flat button: filled with its color, a lighter shade on hover."""

    def __init__(self, parent, text, command, color=BLUE, app=None, filled=True):
        self.color, self.filled, self.command, self.enabled = color, filled, command, True
        super().__init__(parent, text=text, cursor="hand2", padx=16, pady=7, font=app.f_bold,
                         bg=color if filled else CARD, fg="#ffffff" if filled else color)
        self.bind("<Button-1>", lambda _e: self.enabled and self.command())
        self.bind("<Enter>", lambda _e: self.enabled and self.configure(bg=self.shade(color) if filled else LINE))
        self.bind("<Leave>", lambda _e: self.configure(bg=color if filled else CARD))

    @staticmethod
    def shade(hex_color: str) -> str:
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
        return "#%02x%02x%02x" % tuple(min(255, int(c * 1.18) + 12) for c in (r, g, b))

    def set_enabled(self, on: bool):
        self.enabled = on
        self.configure(fg=("#ffffff" if self.filled else self.color) if on else FAINT)


class Chip(tk.Label):
    """A toggle: blue with a check mark when on, grey when off."""

    def __init__(self, parent, text, var: tk.BooleanVar, app, command=None):
        self.var, self.label, self.command = var, text, command
        super().__init__(parent, cursor="hand2", padx=12, pady=5, font=app.f_body)
        self.bind("<Button-1>", self.toggle)
        self.paint()

    def toggle(self, _e=None):
        self.var.set(not self.var.get())
        self.paint()
        if self.command:
            self.command()

    def paint(self):
        on = self.var.get()
        self.configure(text=(f"{YES}  " if on else "    ") + self.label,
                       bg=BLUE_DIM if on else CARD, fg="#ffffff" if on else MUTED)


def entry(parent, var, app, width=None):
    e = tk.Entry(parent, textvariable=var, bg=SURFACE, fg=TEXT, insertbackground=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=LINE, highlightcolor=BLUE, font=app.f_body)
    if width:
        e.configure(width=width)
    return e


# --------------------------------------------------------------- t checks --

def task_key(task: dict) -> str:
    """The program with its name erased (rename_task edits in place, so a copy)."""
    return surface.canon(se.rename_task(copy.deepcopy(task), "x_task"))


def first_task(text: str):
    m = re.search(r"(?m)^t \d+\s*$", text)
    lines = (text[m.start():] if m else text).split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "}":
            try:
                return surface.parse("\n".join(lines[:i + 1]) + "\n")
            except Exception:                                   # noqa: BLE001
                pass
    return None


def corpus_keys(path: Path) -> set[str]:
    keys = set()
    for doc in re.split(r"\n\s*\n(?=Problem: |t \d)", path.read_text(encoding="utf-8", errors="replace")):
        doc = re.sub(r"^Problem: .*\nSignature: .*\n", "", doc.strip())
        try:
            keys.add(task_key(surface.parse(doc + "\n")))
        except Exception:                                       # noqa: BLE001
            pass
    return keys


def guess_corpus(model_dir: Path) -> Path | None:
    for c in (model_dir.parent / "corpus.txt", model_dir.with_suffix(".txt")):
        if c.is_file():
            return c
    return None


def find_models() -> list[str]:
    patterns = [HERE / "runs" / "*" / "filter-loop" / "*" / "*" / "model" / "ckpt.pt",
                HERE / "runs" / "*" / "*" / "model" / "ckpt.pt",
                HERE / "out" / "loop-locallm" / "model" / "ckpt.pt",
                HERE / "out" / "loop-filter" / "*" / "model" / "ckpt.pt",
                LOCALLM / "*" / "ckpt.pt", SCRATCH / "models" / "*" / "ckpt.pt"]
    found = set()
    for pat in patterns:
        anchor = Path(pat.anchor)
        for ck in anchor.glob(str(pat.relative_to(anchor))):
            if (ck.parent / "tokenizer.json").is_file():
                found.add(str(ck.parent))
    return sorted(found)


def memory_mb(root_pid: int) -> float | None:
    """Memory used by a check's processes, from /proc (Linux); None elsewhere."""
    if not os.path.isdir("/proc"):
        return None
    page_kb = os.sysconf("SC_PAGE_SIZE") // 1024
    table = {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat", encoding="utf-8", errors="replace") as f:
                raw = f.read()
            with open(f"/proc/{d}/statm") as f:
                rss = int(f.read().split()[1]) * page_kb
        except (OSError, IndexError, ValueError):
            continue
        table[int(d)] = (int(raw[raw.rfind(")") + 2:].split()[1]), rss)
    kids: dict[int, list[int]] = {}
    for pid, (ppid, _rss) in table.items():
        kids.setdefault(ppid, []).append(pid)
    total, stack = 0, [root_pid]
    while stack:
        for c in kids.get(stack.pop(), []):
            total += table[c][1]
            stack.append(c)
    return total / 1024


# ------------------------------------------------------------------- app --

class Lab:
    def __init__(self, root: tk.Tk):
        self.root = root
        sans = pick_font(root, ["Inter", "SF Pro Text", "Helvetica Neue", "Segoe UI", "Cantarell", "Ubuntu",
                                "Noto Sans", "DejaVu Sans"], "TkDefaultFont")
        mono = pick_font(root, ["JetBrains Mono", "SF Mono", "Menlo", "Consolas", "DejaVu Sans Mono"], "TkFixedFont")
        self.f_title, self.f_h2 = (sans, 20, "bold"), (sans, 13, "bold")
        self.f_body, self.f_bold, self.f_small = (sans, 11), (sans, 11, "bold"), (sans, 10)
        self.f_num, self.f_mono = (sans, 26, "bold"), (mono, 10)
        root.configure(bg=BG)
        root.option_add("*Menu.background", SURFACE)
        root.option_add("*Menu.foreground", TEXT)
        root.option_add("*Menu.activeBackground", BLUE_DIM)
        root.option_add("*Menu.activeForeground", "#ffffff")
        self.style_tables()

        self.q: queue.Queue = queue.Queue()
        self.stop_flag = threading.Event()
        self.offset = EVENTS.stat().st_size if EVENTS.exists() else 0
        self.running: dict[tuple[str, str], dict] = {}
        self.counts = {"done": 0, "proven": 0, "not": 0}
        self.samples: dict[str, str] = {}

        head = tk.Frame(root, bg=BG)
        head.pack(fill="x", padx=22, pady=(18, 6))
        tk.Label(head, text="t lab", bg=BG, fg=TEXT, font=self.f_title).pack(side="left")
        self.pulse = tk.Label(head, text="●  waiting for checks", bg=BG, fg=FAINT, font=self.f_small)
        self.pulse.pack(side="right")
        self.follow_btn_parent = head
        tk.Label(root, bg=BG, fg=MUTED, font=self.f_body, justify="left", anchor="w", wraplength=1300, text=(
            "locallm builds small AI models from scratch. The models write programs. Seven independent checkers "
            "try to prove each program keeps its promise, and try to catch a deliberately broken copy of it. "
            "A program is clean only when all seven prove it and catch the broken copy.")).pack(fill="x", padx=22)

        tabs = tk.Frame(root, bg=BG)
        tabs.pack(fill="x", padx=22, pady=(14, 8))
        self.pages, self.tab_buttons = {}, {}
        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=(0, 18))
        for name in ("Live checks", "Test a model"):
            b = tk.Label(tabs, text=name, cursor="hand2", padx=18, pady=7, font=self.f_bold)
            b.pack(side="left", padx=(0, 8))
            b.bind("<Button-1>", lambda _e, n=name: self.show_page(n))
            self.tab_buttons[name] = b
            self.pages[name] = tk.Frame(body, bg=BG)
        self.build_live(self.pages["Live checks"])
        Button(self.follow_btn_parent, "Follow a loop run", self.follow_loop, BLUE, self,
               filled=False).pack(side="right", padx=(0, 16))
        self.build_test(self.pages["Test a model"])
        self.show_page("Live checks")
        root.after(300, self.poll_events)
        root.after(1000, self.tick)
        root.after(200, self.drain)

    # -- look ------------------------------------------------------------------
    def style_tables(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT, rowheight=30,
                    borderwidth=0, font=self.f_body)
        s.map("Treeview", background=[("selected", BLUE_DIM)], foreground=[("selected", "#ffffff")])
        s.configure("Treeview.Heading", background=SURFACE, foreground=MUTED, relief="flat", font=self.f_small,
                    borderwidth=0, padding=(8, 6))
        s.map("Treeview.Heading", background=[("active", SURFACE)], foreground=[("active", TEXT)])
        s.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        s.configure("Sash", background=BG, sashthickness=8)

    def card(self, parent, title=None, hint=None, **pack):
        outer = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=LINE)
        outer.pack(**({"fill": "x", "pady": (0, 12)} | pack))
        inner = tk.Frame(outer, bg=CARD)
        inner.pack(fill="both", expand=True, padx=16, pady=12)
        if title:
            row = tk.Frame(inner, bg=CARD)
            row.pack(fill="x", pady=(0, 8))
            tk.Label(row, text=title, bg=CARD, fg=TEXT, font=self.f_h2).pack(side="left")
            if hint:
                tk.Label(row, text=hint, bg=CARD, fg=FAINT, font=self.f_small).pack(side="left", padx=10)
        return inner

    def table(self, parent, cols, height):
        frame = tk.Frame(parent, bg=CARD)
        frame.pack(fill="both", expand=True)
        t = ttk.Treeview(frame, columns=[c for c, _, _ in cols], show="headings", height=height)
        for c, label, w in cols:
            t.heading(c, text=label.upper(), anchor="w")
            t.column(c, width=w, anchor="w", stretch=True)
        for tag, color in (("green", GREEN), ("red", RED), ("muted", MUTED), ("blue", BLUE)):
            t.tag_configure(tag, foreground=color)
        t.pack(side="left", fill="both", expand=True)
        return t

    @staticmethod
    def tag(color: str) -> str:
        return {GREEN: "green", RED: "red", BLUE: "blue"}.get(color, "muted")

    def follow_loop(self):
        p = filedialog.askopenfilename(title="Choose a loop log (written by t/loop_filter.py)",
                                       initialdir=str(HERE / "runs"))
        if p:
            self.log_var.set(p)
            self.rounds_outer.pack(fill="x", pady=(0, 12), before=self.done_outer)

    def show_page(self, name):
        for n, page in self.pages.items():
            page.pack_forget()
            self.tab_buttons[n].configure(bg=BLUE if n == name else CARD, fg="#ffffff" if n == name else MUTED)
        self.pages[name].pack(fill="both", expand=True)

    # -- Live checks -------------------------------------------------------------
    def build_live(self, page):
        tiles = tk.Frame(page, bg=BG)
        tiles.pack(fill="x", pady=(0, 12))
        self.tile = {}
        for i, (key, label, color, hint) in enumerate((
                ("now", "Checking now", BLUE, "Programs a checker is working on"),
                ("proven", "Proven", GREEN, "Promise proved, broken copy caught"),
                ("not", "Not proven", RED, "Bug found, not proven, or promise too weak"),
                ("done", "Finished", TEXT, "Every check that has ended"))):
            t = tk.Frame(tiles, bg=CARD, highlightthickness=1, highlightbackground=LINE)
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 12, 0))
            tiles.columnconfigure(i, weight=1)
            tk.Frame(t, bg=color, height=3).pack(fill="x")
            n = tk.Label(t, text="0", bg=CARD, fg=color, font=self.f_num)
            n.pack(anchor="w", padx=16, pady=(10, 0))
            tk.Label(t, text=label, bg=CARD, fg=TEXT, font=self.f_bold).pack(anchor="w", padx=16)
            tk.Label(t, text=hint, bg=CARD, fg=FAINT, font=self.f_small).pack(anchor="w", padx=16, pady=(0, 12))
            self.tile[key] = n

        cols = tk.Frame(page, bg=BG)
        cols.pack(fill="both", expand=True)
        right = tk.Frame(cols, bg=BG, width=370)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)
        left = tk.Frame(cols, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        c = self.card(left, "Checking right now")
        self.now = self.table(c, [("program", "Program", 300), ("checker", "Checker", 110),
                                  ("secs", "Running for", 110), ("mem", "Memory", 100)], 3)
        c = self.card(left, "Just finished", "newest first", fill="both", expand=True)
        self.done = self.table(c, [("time", "Time", 80), ("program", "Program", 230), ("checker", "Checker", 90),
                                   ("result", "Result", 170), ("meaning", "What it means", 460)], 6)
        self.rounds_parent, self.done_outer = left, c.master

        c = self.card(right, "What the results mean")
        for real, twin in (("verified", "refuted"), ("refuted", ""), ("unproved", ""), ("verified", "verified"),
                           ("timeout", ""), ("abstain", "")):
            sym, word, sentence, color = verdict(real, twin)
            row = tk.Frame(c, bg=CARD)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=sym, bg=CARD, fg=color, font=self.f_h2, width=2, anchor="n").pack(side="left", anchor="n")
            txt = tk.Frame(row, bg=CARD)
            txt.pack(side="left", fill="x")
            tk.Label(txt, text=word, bg=CARD, fg=color, font=self.f_bold, anchor="w").pack(anchor="w")
            tk.Label(txt, text=sentence, bg=CARD, fg=MUTED, font=self.f_small, anchor="w", justify="left",
                     wraplength=290).pack(anchor="w")

        c = self.card(self.rounds_parent, "Model rounds", "from the loop log you chose", before=self.done_outer)
        self.rounds_outer = c.master
        self.rounds_outer.pack_forget()
        tk.Label(c, bg=CARD, fg=MUTED, font=self.f_small, justify="left", wraplength=900, anchor="w", text=(
            "Each round, locallm builds a new model from every clean program found so far, "
            "and that model writes new programs.")).pack(fill="x")
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x", pady=8)
        self.log_var = tk.StringVar()
        entry(row, self.log_var, self).pack(side="left", fill="x", expand=True, ipady=4)
        Button(row, "Choose another", self.follow_loop, BLUE, self, filled=False).pack(side="left", padx=(8, 0))
        self.rounds = self.table(c, [("round", "Round", 55), ("written", "Written", 70), ("new", "New", 55),
                                     ("clean", "Clean", 55), ("share", "Clean %", 70)], 3)
        tk.Label(c, bg=CARD, fg=FAINT, font=self.f_small, justify="left", wraplength=900, anchor="w", text=(
            "Written: programs the model wrote. New: not copied from what it learned from. "
            "Clean: new and proven by all seven.")).pack(fill="x", pady=(6, 0))

    def poll_events(self):
        try:
            size = EVENTS.stat().st_size
            if size < self.offset:
                self.offset = 0
            if size > self.offset:
                with open(EVENTS, encoding="utf-8") as fh:
                    fh.seek(self.offset)
                    chunk = fh.read()
                keep = chunk.rfind("\n") + 1
                self.offset += len(chunk[:keep].encode("utf-8"))
                for line in chunk[:keep].splitlines():
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    key = (ev.get("task", "?"), ev.get("kernel", "?"))
                    if ev.get("ev") == "start":
                        self.running[key] = ev
                    elif ev.get("ev") == "end":
                        self.running.pop(key, None)
                        sym, word, sentence, color = verdict(ev.get("real"), ev.get("twin"))
                        self.counts["done"] += 1
                        self.counts["proven"] += word == "Proven"
                        self.counts["not"] += color == RED
                        self.done.insert("", 0, tags=(self.tag(color),), values=(
                            time.strftime("%H:%M:%S", time.localtime(ev["t"])), key[0],
                            CHECKER.get(key[1], key[1]), f"{sym}  {word}", sentence))
                        for extra in self.done.get_children()[300:]:
                            self.done.delete(extra)
        except FileNotFoundError:
            pass
        self.root.after(300, self.poll_events)

    def tick(self):
        self.now.delete(*self.now.get_children())
        now = time.time()
        for (task, kernel), ev in sorted(self.running.items(), key=lambda kv: kv[1]["t"]):
            mem = memory_mb(ev.get("pid", -1))
            self.now.insert("", "end", tags=("blue",), values=(
                task, CHECKER.get(kernel, kernel), f"{now - ev['t']:.0f} s", "" if mem is None else f"{mem:.0f} MB"))
        for key, value in (("now", len(self.running)), ("proven", self.counts["proven"]),
                           ("not", self.counts["not"]), ("done", self.counts["done"])):
            self.tile[key].configure(text=str(value))
        busy = bool(self.running)
        self.pulse.configure(text="●  checking" if busy else "●  idle", fg=BLUE if busy else FAINT)
        rows = {}
        if self.log_var.get():
            try:
                for line in Path(self.log_var.get()).read_text(errors="replace").splitlines():
                    m = LOOP_RE.search(line)
                    if m:
                        rows.setdefault(m.group(1), {}).update(written=m.group(3), new=m.group(6))
                    m = CLEAN_RE.search(line)
                    if m:
                        rows.setdefault(m.group(1), {})["clean"] = m.group(2)
            except OSError:
                pass
        self.rounds.delete(*self.rounds.get_children())
        for r, v in sorted(rows.items(), key=lambda kv: int(kv[0])):
            share = (f"{100 * int(v['clean']) / int(v['written']):.1f}%"
                     if "clean" in v and int(v.get("written", 0) or 0) else "checking")
            self.rounds.insert("", "end", tags=("green",) if "clean" in v else (), values=(
                r, v.get("written", ""), v.get("new", ""), v.get("clean", ""), share))
        self.root.after(1000, self.tick)

    # -- Test a model --------------------------------------------------------------
    def build_test(self, page):
        top = tk.Frame(page, bg=BG)
        top.pack(fill="x")
        leftcol = tk.Frame(top, bg=BG)
        leftcol.pack(side="left", fill="both", expand=True)
        rightcol = tk.Frame(top, bg=BG)
        rightcol.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.models = find_models()

        c = self.card(leftcol, "1   Choose a model")
        self.model_a = tk.StringVar(value=self.models[0] if self.models else "")
        self.model_b, self.corpus_var = tk.StringVar(), tk.StringVar()
        for label, var, tip, is_dir in (
                ("Model", self.model_a, "A folder locallm wrote. It holds ckpt.pt (the model) and tokenizer.json.", True),
                ("Compare with", self.model_b, "Optional. A second model, tested the same way, for a side by side result.", True),
                ("Learned from", self.corpus_var, "The text the model was built from, used to spot programs it only "
                                                  "copied. Filled in when it can be found.", False)):
            row = tk.Frame(c, bg=CARD)
            row.pack(fill="x", pady=3)
            lab = tk.Label(row, text=label, bg=CARD, fg=MUTED, font=self.f_body, width=13, anchor="w")
            lab.pack(side="left")
            Tip(lab, tip, self)
            entry(row, var, self).pack(side="left", fill="x", expand=True, ipady=4)
            if is_dir:
                Button(row, "▾", lambda v=var: self.model_menu(v), BLUE, self, filled=False).pack(side="left", padx=(6, 0))
            Button(row, "Browse", (lambda v=var: self.browse_dir(v)) if is_dir else (lambda v=var: self.browse_file(v)),
                   BLUE, self, filled=False).pack(side="left", padx=(6, 0))
        self.model_a.trace_add("write", lambda *_: self.fill_corpus())
        self.fill_corpus()

        c = self.card(leftcol, "2   What should it write?")
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x")
        lab = tk.Label(row, text="Start with", bg=CARD, fg=MUTED, font=self.f_body, width=13, anchor="w")
        lab.pack(side="left")
        Tip(lab, "The text the model continues from. \"t 1\" is how a t program begins. "
                 "\"Problem: ...\" asks for a specific program.", self)
        self.prompt_var = tk.StringVar(value="t 1")
        entry(row, self.prompt_var, self, width=18).pack(side="left", ipady=4)
        tk.Label(row, text="How many", bg=CARD, fg=MUTED, font=self.f_body).pack(side="left", padx=(18, 8))
        self.n_var = tk.StringVar(value="50")
        entry(row, self.n_var, self, width=6).pack(side="left", ipady=4)
        self.more_on = tk.BooleanVar(value=False)
        Chip(row, "More settings", self.more_on, self, command=self.toggle_more).pack(side="left", padx=(18, 0))
        self.more = tk.Frame(c, bg=CARD)
        self.len_var, self.temp_var = tk.StringVar(value="700"), tk.StringVar(value="0.8")
        self.topk_var, self.jobs_var = tk.StringVar(value="40"), tk.StringVar(value="4")
        for label, var, tip in (
                ("Length", self.len_var, "How many characters the model writes for each program."),
                ("Creativity", self.temp_var, "Higher gives more varied programs, lower gives safer, repetitive ones. 0.8 is a good start."),
                ("Choices", self.topk_var, "How many likely next letters the model picks from."),
                ("Checks at once", self.jobs_var, "How many programs are checked at the same time. About a quarter of your computer's cores.")):
            lab = tk.Label(self.more, text=label, bg=CARD, fg=MUTED, font=self.f_small)
            lab.pack(side="left", padx=(0, 6))
            Tip(lab, tip, self)
            entry(self.more, var, self, width=6).pack(side="left", padx=(0, 14), ipady=2)

        c = self.card(rightcol, "3   Which checks?")
        self.chk = {k: tk.BooleanVar(value=True) for k in ("parse", "wf", "novel")}
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x")
        for k, label, tip in (("parse", "Readable", "The text is a valid t program."),
                              ("wf", "Follows the rules", "Passes t's basic rules: names defined, types line up, loops explained."),
                              ("novel", "New", "Not a copy of a program the model learned from.")):
            chip = Chip(row, label, self.chk[k], self)
            chip.pack(side="left", padx=(0, 8))
            Tip(chip, tip, self)
        lab = tk.Label(c, text="Proven by", bg=CARD, fg=MUTED, font=self.f_body, anchor="w")
        lab.pack(fill="x", pady=(12, 6))
        Tip(lab, "Each checker tries to prove the program keeps its promise and to catch a broken copy. "
                 "Every checker adds time; Dafny is the fastest.", self)
        self.kchk = {k: tk.BooleanVar(value=(k == "dafny")) for k in KERNELS}
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x")
        for k in KERNELS:
            Chip(row, CHECKER[k], self.kchk[k], self).pack(side="left", padx=(0, 6))
        lab = tk.Label(c, text="Your own test (optional)", bg=CARD, fg=MUTED, font=self.f_body, anchor="w")
        lab.pack(fill="x", pady=(12, 6))
        Tip(lab, "Any command. {file} becomes the program's file. It passes when the command exits with 0. "
                 "Example: grep -q ensures {file}", self)
        self.custom_var = tk.StringVar()
        entry(c, self.custom_var, self).pack(fill="x", ipady=4)

        bar = tk.Frame(page, bg=BG)
        bar.pack(fill="x", pady=(0, 10))
        self.run_btn = Button(bar, "▶   Run test", self.start_test, BLUE, self)
        self.run_btn.pack(side="left")
        Button(bar, "■   Stop", self.stop_flag.set, RED, self, filled=False).pack(side="left", padx=10)
        self.status = tk.Label(bar, text="", bg=BG, fg=MUTED, font=self.f_body)
        self.status.pack(side="left", padx=8)
        self.summary = tk.Label(page, text="", bg=BG, fg=TEXT, font=self.f_bold, justify="left", anchor="w",
                                wraplength=1300)
        self.summary.pack(fill="x", pady=(0, 8))

        lower = tk.Frame(page, bg=BG)
        lower.pack(fill="both", expand=True)
        c = self.card(lower, "Programs", f"{YES} yes   {NO} no   {DASH} not checked   click a row to read it",
                      side="left", fill="both", expand=True)
        cols = [("model", "Model", 60), ("n", "#", 45), ("readable", "Readable", 80), ("rules", "Rules", 60),
                ("new", "New", 50)] + [(k, CHECKER[k], 62) for k in KERNELS] + [("yours", "Yours", 55), ("clean", "Clean", 60)]
        self.results = self.table(c, cols, 8)
        for col in self.results["columns"]:
            self.results.column(col, anchor="center")
        self.results.bind("<<TreeviewSelect>>", self.show_sample)
        c = self.card(lower, "The program", side="left", fill="both", expand=True, padx=(12, 0))
        self.sample_text = tk.Text(c, width=46, height=12, wrap="none", bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                                   relief="flat", font=self.f_mono, padx=10, pady=8, highlightthickness=0)
        self.sample_text.pack(fill="both", expand=True)

    def toggle_more(self):
        if self.more_on.get():
            self.more.pack(fill="x", pady=(10, 0))
        else:
            self.more.pack_forget()

    def model_menu(self, var):
        menu = tk.Menu(self.root, tearoff=0, font=self.f_small)
        if not self.models:
            menu.add_command(label="No models found yet. Use Browse.", state="disabled")
        for m in self.models:
            menu.add_command(label=m, command=lambda m=m: var.set(m))
        menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def fill_corpus(self):
        c = guess_corpus(Path(self.model_a.get())) if self.model_a.get() else None
        if c:
            self.corpus_var.set(str(c))

    def browse_dir(self, var):
        d = filedialog.askdirectory(initialdir=var.get() or str(Path.home()))
        if d:
            var.set(d)

    def browse_file(self, var):
        p = filedialog.askopenfilename(initialdir=str(Path(var.get()).parent) if var.get() else str(Path.home()))
        if p:
            var.set(p)

    def show_sample(self, _e=None):
        sel = self.results.selection()
        if sel:
            self.sample_text.delete("1.0", "end")
            self.sample_text.insert("1.0", self.samples.get(sel[0], ""))

    @staticmethod
    def number(var, default, kind=int):
        try:
            return kind(var.get())
        except ValueError:
            return default

    def start_test(self):
        models = [m for m in (self.model_a.get(), self.model_b.get()) if m]
        if not models:
            self.status.configure(text="Choose a model first (step 1).", fg=RED)
            return
        prompt = self.prompt_var.get()
        s = dict(prompt=prompt if prompt.endswith("\n") else prompt + "\n",
                 n=self.number(self.n_var, 50), length=self.number(self.len_var, 700),
                 temp=self.number(self.temp_var, 0.8, float), topk=self.number(self.topk_var, 40),
                 jobs=self.number(self.jobs_var, 4), parse=self.chk["parse"].get(), wf=self.chk["wf"].get(),
                 novel=self.chk["novel"].get(), kernels=[k for k in KERNELS if self.kchk[k].get()],
                 custom=self.custom_var.get().strip(), corpus=self.corpus_var.get())
        self.results.delete(*self.results.get_children())
        self.samples.clear()
        self.summary.configure(text="")
        self.stop_flag.clear()
        self.run_btn.set_enabled(False)
        threading.Thread(target=self.run_tests, args=(models, s), daemon=True).start()

    def drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "status":
                    self.status.configure(text=payload, fg=MUTED)
                elif kind == "row":
                    iid, values, text, clean = payload
                    self.samples[iid] = text
                    tags = ("green" if clean else "red",)
                    if self.results.exists(iid):
                        self.results.item(iid, values=values, tags=tags)
                    else:
                        self.results.insert("", "end", iid=iid, values=values, tags=tags)
                elif kind == "summary":
                    self.summary.configure(text=payload)
                elif kind == "error":
                    self.status.configure(text=payload, fg=RED)
                elif kind == "done":
                    self.run_btn.set_enabled(True)
        except queue.Empty:
            pass
        self.root.after(200, self.drain)

    # -- the test itself, off the window's thread ---------------------------------
    def run_tests(self, models, s):
        lines = []
        try:
            for i, model in enumerate(models):
                lines.append(self.test_one("A" if i == 0 else "B", Path(model), s))
                self.q.put(("summary", "\n".join(lines)))
                if self.stop_flag.is_set():
                    break
        except Exception as e:                                  # noqa: BLE001
            self.q.put(("error", f"Something went wrong: {type(e).__name__}: {e}"))
        finally:
            self.q.put(("done", None))

    def test_one(self, label, model_dir: Path, s) -> str:
        import torch
        import checkpoint
        self.q.put(("status", f"Model {label}: loading"))
        model, tok, _cfg = checkpoint.load_checkpoint(str(model_dir))
        params = sum(p.numel() for p in model.parameters())
        corpus = guess_corpus(model_dir) if label == "B" else (Path(s["corpus"]) if s["corpus"] else None)
        seen = corpus_keys(corpus) if (s["novel"] and corpus and corpus.is_file()) else set()
        run = SCRATCH / time.strftime("%Y%m%d-%H%M%S") / label
        (run / "tasks").mkdir(parents=True, exist_ok=True)
        rows, texts = {}, {}
        torch.manual_seed(1)
        for i in range(s["n"]):
            if self.stop_flag.is_set():
                break
            self.q.put(("status", f"Model {label}: writing program {i + 1} of {s['n']}"))
            text = checkpoint.sample(model, tok, s["prompt"], s["length"], temperature=s["temp"], top_k=s["topk"])
            task = first_task(text)
            r = {"parse": task is not None, "wf": None, "novel": None, "k": {}, "custom": None}
            name = f"lab_{label.lower()}_{i}"
            if task is not None:
                try:
                    task = se.rename_task(task, name)
                    r["wf"] = not fuzz_lower.check_wf(task)
                except Exception:                               # noqa: BLE001
                    r["wf"] = False
                if s["novel"] and corpus:
                    r["novel"] = task_key(task) not in seen
                if r["wf"] and r["novel"] is not False:
                    (run / "tasks" / f"{name}.t").write_text(surface.print_task(task), encoding="utf-8")
            (run / f"{name}.txt").write_text(text, encoding="utf-8")
            if s["custom"]:
                path = str(run / f"{name}.txt")
                cmd = s["custom"].replace("{file}", f'"{path}"' if os.name == "nt" else shlex.quote(path))
                r["custom"] = subprocess.run(cmd, shell=True, capture_output=True).returncode == 0
            rows[name], texts[name] = r, text
            self.emit(label, i, name, r, s, text)
        if s["kernels"] and any((run / "tasks").iterdir()) and not self.stop_flag.is_set():
            n_tasks = len(list((run / "tasks").iterdir()))
            names = ", ".join(CHECKER[k] for k in s["kernels"])
            self.q.put(("status", f"Model {label}: {names} checking {n_tasks} programs (see Live checks)"))
            env = dict(os.environ, PATH=KERNEL_PATH + os.pathsep + os.environ.get("PATH", ""), T_WATCH=str(EVENTS),
                       T_MIN_KERNELS="1")
            EVENTS.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([sys.executable, str(HERE / "run_par.py"), "--kernels", ",".join(s["kernels"]),
                            "--jobs", str(s["jobs"]), "--tasks", str(run / "tasks"), "--out", str(run / "kernels"),
                            "--table", str(run / "table.md")], env=env, capture_output=True)
            try:
                header = None
                for line in (run / "table.md").read_text().splitlines():
                    cells = [x.strip() for x in line.strip().strip("|").split("|")]
                    if cells and cells[0] == "task":
                        header = cells
                    elif header and cells and cells[0] in rows:
                        rows[cells[0]]["k"] = dict(zip(header[1:], cells[1:]))
            except OSError:
                pass
            for i, name in enumerate(rows):
                self.emit(label, i, name, rows[name], s, texts[name])
        n = len(rows)

        def count(fn):
            return sum(1 for r in rows.values() if fn(r))
        parts = []
        if s["parse"]:
            parts.append(f"{count(lambda r: r['parse'])} readable")
        if s["wf"]:
            parts.append(f"{count(lambda r: r['wf'])} follow the rules")
        if s["novel"]:
            parts.append(f"{count(lambda r: r['novel'])} new" if corpus else "copy check skipped (no training text)")
        for k in s["kernels"]:
            parts.append(f"{count(lambda r, k=k: r['k'].get(k) == 'verified / refuted')} proven by {CHECKER[k]}")
        if s["custom"]:
            parts.append(f"{count(lambda r: r['custom'])} pass your test")
        clean = count(lambda r: self.passes(r, s))
        self.q.put(("status", f"Model {label}: done. Files in {run}"))
        return (f"Model {label}  ({params / 1e6:.1f} million parameters) wrote {n} programs:  " + ",  ".join(parts)
                + f".     {YES} CLEAN: {clean} of {n} ({100 * clean / max(n, 1):.0f}%)")

    @staticmethod
    def passes(r, s) -> bool:
        if s["parse"] and not r["parse"]:
            return False
        if s["wf"] and not r["wf"]:
            return False
        if s["novel"] and r["novel"] is False:
            return False
        if any(r["k"].get(k) != "verified / refuted" for k in s["kernels"]):
            return False
        if s["custom"] and not r["custom"]:
            return False
        return True

    def emit(self, label, i, name, r, s, text):
        cells = []
        for k in KERNELS:
            if k not in s["kernels"] or k not in r["k"]:
                cells.append(DASH)
            else:
                real, _, twin = r["k"][k].partition("/")
                cells.append(verdict(real, twin)[0])
        values = (label, i + 1, mark(r["parse"]), mark(r["wf"]), mark(r["novel"]), *cells, mark(r["custom"]),
                  mark(self.passes(r, s)))
        self.q.put(("row", (name, values, text, self.passes(r, s))))


def main() -> int:
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    root.title("t lab")
    w, h = min(1400, root.winfo_screenwidth() - 20), min(900, root.winfo_screenheight() - 60)
    root.geometry(f"{w}x{h}+10+30")
    root.minsize(1000, 700)
    Lab(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
