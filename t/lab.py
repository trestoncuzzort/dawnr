#!/usr/bin/env python3
"""t/lab.py -- one window to watch the filter at work and to test the models
it produces (2026-09-16).

Two tabs.

Runs. The locallm -> t filter -> retrain loop's rounds, read from its log
(samples, parsed, well-formed, novel, clean in all seven, clean share), and
every kernel cell as it runs: run_par.py appends a start and an end event to
the file named by T_WATCH, and this tab lists the running cells with their
live prover processes and memory (read from /proc) and the finished cells
with their verdicts, green for verified / refuted and red otherwise.

Test a model. Pick any model directory locallm wrote (a ckpt.pt beside a
tokenizer.json), a prompt, how many samples and how they are drawn, then
tick the checks to apply to every sample:

  - parses as t,
  - well-formed (fuzz_lower.check_wf),
  - not a copy of the model's training corpus (canonical AST, name erased),
  - any subset of the seven kernels, each sample graded with its twin
    (run_par.py --kernels, so the cells also show on the Runs tab),
  - a command of your own, run once per sample with {file} replaced by the
    sample's path; exit code 0 passes.

A second model can be tested with the same settings for a side-by-side
summary. Click a result row to read that sample.

Run under a Python that has torch (locallm's), on the desktop's display:

    DISPLAY=:10.0 ~/.venv-train/bin/python t/lab.py
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
from tkinter import filedialog, ttk

HERE = Path(__file__).resolve().parent
TUP = HERE.parent
LOCALLM = TUP / "locallm"
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(LOCALLM))

import fuzz_lower                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402

EVENTS = Path.home() / ".cache" / "t-watch" / "events.jsonl"
SCRATCH = Path(os.environ.get("T_LAB_SCRATCH", Path.home() / ".cache" / "t-lab"))
KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
KERNEL_PATH = ":".join(str(Path.home() / p) for p in (
    ".cargo/bin", ".opam/default/bin", ".elan/bin", ".local/fstar/fstar/bin",
    ".local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin", ".local/verus/verus-x86-linux"))
GOOD, BAD, DIM = "#d8f5dc", "#f8d7d7", "#666666"
PAGE_KB = os.sysconf("SC_PAGE_SIZE") // 1024
ROUND_RE = re.compile(r"round (\d+): corpus (\d+) docs; samples (\d+), parsed (\d+), "
                      r"well-formed (\d+), novel (\d+)")
CLEAN_RE = re.compile(r"round (\d+): clean in all seven (\d+), in at least one (\d+)")


# ---------------------------------------------------------------- t checks --

def task_key(task: dict) -> str:
    """Canonical form with the name erased. rename_task edits its argument in
    place, so it gets a copy."""
    return surface.canon(se.rename_task(copy.deepcopy(task), "x_task"))


def first_task(text: str):
    """The first prefix of `text` ending at a "}" line that parses, or None."""
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
    for doc in re.split(r"(?m)^(?=t \d+\s*$)", path.read_text(encoding="utf-8", errors="replace")):
        try:
            keys.add(task_key(surface.parse(doc)))
        except Exception:                                       # noqa: BLE001
            pass
    return keys


def guess_corpus(model_dir: Path) -> Path | None:
    for c in (model_dir.parent / "corpus.txt", model_dir.with_suffix(".txt")):
        if c.is_file():
            return c
    return None


def find_models(patterns: list[str]) -> list[Path]:
    """Model directories (a ckpt.pt beside a tokenizer.json) matching any glob
    pattern; patterns, not a walk, because the scratch trees hold hundreds of
    thousands of kernel files."""
    found = set()
    for pat in patterns:
        for ck in Path("/").glob(pat.lstrip("/")):
            if (ck.parent / "tokenizer.json").is_file():
                found.add(ck.parent)
    return sorted(found)


def proc_table() -> dict[int, tuple[int, str, int]]:
    out = {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat", encoding="utf-8", errors="replace") as f:
                raw = f.read()
            with open(f"/proc/{d}/statm") as f:
                rss = int(f.read().split()[1]) * PAGE_KB
        except (OSError, IndexError, ValueError):
            continue
        lp, rp = raw.find("("), raw.rfind(")")
        out[int(d)] = (int(raw[rp + 2:].split()[1]), raw[lp + 1:rp], rss)
    return out


def descendants(root: int, table) -> list[int]:
    kids: dict[int, list[int]] = {}
    for pid, row in table.items():
        kids.setdefault(row[0], []).append(pid)
    found, stack = [], [root]
    while stack:
        for c in kids.get(stack.pop(), []):
            found.append(c)
            stack.append(c)
    return found


# ------------------------------------------------------------------- app --

class Lab(ttk.Frame):
    def __init__(self, root: tk.Tk):
        super().__init__(root)
        self.root = root
        self.pack(fill="both", expand=True)
        self.q: queue.Queue = queue.Queue()
        self.stop_flag = threading.Event()
        self.offset = EVENTS.stat().st_size if EVENTS.exists() else 0
        self.running: dict[tuple[str, str], dict] = {}
        self.counts = {"started": 0, "done": 0, "clean": 0}
        self.samples: dict[str, str] = {}
        style = ttk.Style()
        style.configure("Treeview", rowheight=22)
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.runs_tab(nb)
        self.test_tab(nb)
        self.root.after(250, self.poll_events)
        self.root.after(1000, self.tick)
        self.root.after(200, self.drain)

    # -- Runs tab ------------------------------------------------------------
    def runs_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="Runs")
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(6, 2))
        ttk.Label(top, text="Loop log").pack(side="left")
        loop_dirs = sorted(Path("/tmp").glob(f"claude-{os.getuid()}/*/*/scratchpad/locallm-t"))
        self.log_var = tk.StringVar(value=str(loop_dirs[-1] / "loop.log") if loop_dirs else "")
        ttk.Entry(top, textvariable=self.log_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="Browse", command=lambda: self.browse_file(self.log_var)).pack(side="left")
        cols = ("round", "corpus", "samples", "parsed", "well-formed", "novel", "clean 7", "clean 1+", "clean share")
        self.rounds = self.tree(f, cols, 5, widths=[70] * 8 + [110])
        self.counter = ttk.Label(f, text="")
        self.counter.pack(fill="x", pady=(8, 2))
        ttk.Label(f, text="Running now", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        self.now = self.tree(f, ("task", "kernel", "seconds", "provers", "memory MB"), 8,
                             widths=[260, 80, 70, 360, 90])
        ttk.Label(f, text="Finished", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(6, 0))
        self.done = self.tree(f, ("time", "task", "kernel", "real", "twin", "seconds"), 10,
                              widths=[80, 260, 80, 110, 110, 70])
        self.done.tag_configure("good", background=GOOD)
        self.done.tag_configure("bad", background=BAD)

    def tree(self, parent, cols, height, widths):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        t = ttk.Treeview(frame, columns=cols, show="headings", height=height)
        for c, w in zip(cols, widths):
            t.heading(c, text=c)
            t.column(c, width=w, anchor="w", stretch=True)
        sb = ttk.Scrollbar(frame, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sb.set)
        t.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return t

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
                        self.counts["started"] += 1
                        self.running[key] = ev
                    elif ev.get("ev") == "end":
                        start = self.running.pop(key, None)
                        self.counts["done"] += 1
                        good = ev.get("real") == "verified" and ev.get("twin") == "refuted"
                        self.counts["clean"] += good
                        secs = f"{ev['t'] - start['t']:.1f}" if start else ""
                        self.done.insert("", 0, tags=("good" if good else "bad",), values=(
                            time.strftime("%H:%M:%S", time.localtime(ev["t"])), key[0], key[1],
                            ev.get("real"), ev.get("twin"), secs))
                        for extra in self.done.get_children()[300:]:
                            self.done.delete(extra)
        except FileNotFoundError:
            pass
        self.root.after(250, self.poll_events)

    def tick(self):
        # running cells, with their live prover processes
        self.now.delete(*self.now.get_children())
        table = proc_table() if self.running else {}
        now = time.time()
        for (task, kernel), ev in sorted(self.running.items(), key=lambda kv: kv[1]["t"]):
            pids = [p for p in descendants(ev.get("pid", -1), table) if table[p][1] not in ("sh", "bash")]
            names = sorted({table[p][1] for p in pids})
            mem = sum(table[p][2] for p in pids) / 1024
            self.now.insert("", "end", values=(task, kernel, f"{now - ev['t']:.0f}",
                                               ", ".join(names) or "between calls", f"{mem:.0f}"))
        c = self.counts
        self.counter.configure(text=f"cells started {c['started']}, finished {c['done']}, "
                                    f"verified / refuted {c['clean']}, other {c['done'] - c['clean']}, "
                                    f"running {len(self.running)}")
        # the loop's rounds
        rows = {}
        try:
            for line in Path(self.log_var.get()).read_text(errors="replace").splitlines():
                m = ROUND_RE.search(line)
                if m:
                    rows.setdefault(m.group(1), {}).update(
                        corpus=m.group(2), samples=m.group(3), parsed=m.group(4), wf=m.group(5), novel=m.group(6))
                m = CLEAN_RE.search(line)
                if m:
                    rows.setdefault(m.group(1), {}).update(c7=m.group(2), c1=m.group(3))
        except OSError:
            pass
        self.rounds.delete(*self.rounds.get_children())
        for r, v in sorted(rows.items(), key=lambda kv: int(kv[0])):
            share = (f"{100 * int(v['c7']) / int(v['samples']):.1f}%"
                     if "c7" in v and int(v.get("samples", 0)) else "grading")
            self.rounds.insert("", "end", values=(r, v.get("corpus"), v.get("samples"), v.get("parsed"),
                                                  v.get("wf"), v.get("novel"), v.get("c7", ""),
                                                  v.get("c1", ""), share))
        self.root.after(1000, self.tick)

    # -- Test tab ------------------------------------------------------------
    def test_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="Test a model")
        self.models = [str(p) for p in find_models([
            f"tmp/claude-{os.getuid()}/*/*/scratchpad/locallm-t/*/*/ckpt.pt",
            f"tmp/claude-{os.getuid()}/*/*/scratchpad/locallm-t/*/*/*/ckpt.pt",
            str(TUP / "locallm" / "*" / "ckpt.pt"), str(Path.home() / ".cache" / "t-lab" / "models" / "*" / "ckpt.pt")])]
        grid = ttk.Frame(f)
        grid.pack(fill="x", pady=6)
        self.model_a = tk.StringVar(value=self.models[-1] if self.models else "")
        self.model_b = tk.StringVar(value="")
        self.corpus_var = tk.StringVar(value="")
        for row, (label, var) in enumerate((("Model", self.model_a), ("Compare with (optional)", self.model_b),
                                            ("Training corpus (for the copy check)", self.corpus_var))):
            ttk.Label(grid, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
            box = ttk.Combobox(grid, textvariable=var, values=self.models if row < 2 else [])
            box.grid(row=row, column=1, sticky="ew", pady=2)
            ttk.Button(grid, text="Browse", command=lambda v=var, r=row: (
                self.browse_dir(v) if r < 2 else self.browse_file(v))).grid(row=row, column=2, padx=4)
        grid.columnconfigure(1, weight=1)
        self.model_a.trace_add("write", lambda *_: self.fill_corpus())
        self.fill_corpus()
        self.info = ttk.Label(f, text="")
        self.info.pack(fill="x")

        knobs = ttk.Frame(f)
        knobs.pack(fill="x", pady=4)
        ttk.Label(knobs, text="Prompt").pack(side="left")
        self.prompt = tk.Text(knobs, height=2, width=40)
        self.prompt.insert("1.0", "t 1\n")
        self.prompt.pack(side="left", padx=6)
        self.n_var, self.len_var = tk.IntVar(value=50), tk.IntVar(value=700)
        self.temp_var, self.topk_var = tk.DoubleVar(value=0.8), tk.IntVar(value=40)
        self.jobs_var = tk.IntVar(value=16)
        for label, var, lo, hi, inc in (("samples", self.n_var, 1, 5000, 10), ("characters", self.len_var, 50, 5000, 50),
                                        ("temperature", self.temp_var, 0.05, 2.0, 0.05), ("top-k", self.topk_var, 1, 200, 5),
                                        ("kernel jobs", self.jobs_var, 1, 64, 1)):
            ttk.Label(knobs, text=label).pack(side="left", padx=(8, 2))
            ttk.Spinbox(knobs, textvariable=var, from_=lo, to=hi, increment=inc, width=6).pack(side="left")

        checks = ttk.LabelFrame(f, text="Checks on every sample")
        checks.pack(fill="x", pady=4)
        self.chk = {k: tk.BooleanVar(value=True) for k in ("parse", "wf", "novel")}
        for k, label in (("parse", "parses as t"), ("wf", "well-formed"), ("novel", "not a copy of the training corpus")):
            ttk.Checkbutton(checks, text=label, variable=self.chk[k]).pack(side="left", padx=6)
        ttk.Separator(checks, orient="vertical").pack(side="left", fill="y", padx=6)
        self.kchk = {k: tk.BooleanVar(value=(k == "dafny")) for k in KERNELS}
        for k in KERNELS:
            ttk.Checkbutton(checks, text=k, variable=self.kchk[k]).pack(side="left", padx=3)
        custom = ttk.Frame(f)
        custom.pack(fill="x", pady=2)
        ttk.Label(custom, text="Your own check (a command, {file} is the sample; exit 0 passes)").pack(side="left")
        self.custom_var = tk.StringVar(value="")
        ttk.Entry(custom, textvariable=self.custom_var).pack(side="left", fill="x", expand=True, padx=6)

        buttons = ttk.Frame(f)
        buttons.pack(fill="x", pady=4)
        self.run_btn = ttk.Button(buttons, text="Run test", command=self.start_test)
        self.run_btn.pack(side="left")
        ttk.Button(buttons, text="Stop", command=self.stop_flag.set).pack(side="left", padx=6)
        self.status = ttk.Label(buttons, text="")
        self.status.pack(side="left", padx=10)
        self.summary = ttk.Label(f, text="", font=("TkDefaultFont", 10, "bold"), justify="left")
        self.summary.pack(fill="x", pady=4)

        pane = ttk.Panedwindow(f, orient="horizontal") if hasattr(ttk, "Panedwindow") else ttk.Frame(f)
        pane.pack(fill="both", expand=True)
        left = ttk.Frame(pane)
        cols = ("model", "#", "parses", "well-formed", "novel", *KERNELS, "yours", "passes all")
        self.results = ttk.Treeview(left, columns=cols, show="headings", height=12)
        for c in cols:
            self.results.heading(c, text=c)
            self.results.column(c, width=52 if c in KERNELS else 70, anchor="w", stretch=True)
        self.results.tag_configure("good", background=GOOD)
        self.results.tag_configure("bad", background=BAD)
        sb = ttk.Scrollbar(left, orient="vertical", command=self.results.yview)
        self.results.configure(yscrollcommand=sb.set)
        self.results.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.results.bind("<<TreeviewSelect>>", self.show_sample)
        self.sample_text = tk.Text(pane, width=48, wrap="none", font=("monospace", 9))
        if isinstance(pane, ttk.Panedwindow):
            pane.add(left, weight=3)
            pane.add(self.sample_text, weight=2)
        else:
            left.pack(side="left", fill="both", expand=True)
            self.sample_text.pack(side="right", fill="both")

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

    def show_sample(self, _ev=None):
        sel = self.results.selection()
        if sel:
            self.sample_text.delete("1.0", "end")
            self.sample_text.insert("1.0", self.samples.get(sel[0], ""))

    def start_test(self):
        models = [m for m in (self.model_a.get(), self.model_b.get()) if m]
        if not models:
            self.status.configure(text="pick a model first")
            return
        settings = dict(prompt=self.prompt.get("1.0", "end-1c"), n=self.n_var.get(), length=self.len_var.get(),
                        temp=self.temp_var.get(), topk=self.topk_var.get(), jobs=self.jobs_var.get(),
                        parse=self.chk["parse"].get(), wf=self.chk["wf"].get(), novel=self.chk["novel"].get(),
                        kernels=[k for k in KERNELS if self.kchk[k].get()], custom=self.custom_var.get().strip(),
                        corpus=self.corpus_var.get())
        self.results.delete(*self.results.get_children())
        self.samples.clear()
        self.summary.configure(text="")
        self.stop_flag.clear()
        self.run_btn.state(["disabled"])
        threading.Thread(target=self.run_tests, args=(models, settings), daemon=True).start()

    def drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "status":
                    self.status.configure(text=payload)
                elif kind == "info":
                    self.info.configure(text=payload)
                elif kind == "row":
                    iid, values, text, good = payload
                    self.samples[iid] = text
                    if self.results.exists(iid):
                        self.results.item(iid, values=values, tags=("good" if good else "bad",))
                    else:
                        self.results.insert("", "end", iid=iid, values=values, tags=("good" if good else "bad",))
                elif kind == "summary":
                    self.summary.configure(text=payload)
                elif kind == "done":
                    self.run_btn.state(["!disabled"])
        except queue.Empty:
            pass
        self.root.after(200, self.drain)

    # -- the test itself (worker thread) -------------------------------------
    def run_tests(self, models, s):
        lines = []
        try:
            for mi, model in enumerate(models):
                label = "A" if mi == 0 else "B"
                lines.append(self.test_one(label, Path(model), s))
                self.q.put(("summary", "\n".join(lines)))
                if self.stop_flag.is_set():
                    break
        except Exception as e:                                  # noqa: BLE001
            self.q.put(("status", f"error: {type(e).__name__}: {e}"))
        finally:
            self.q.put(("done", None))

    def test_one(self, label, model_dir: Path, s) -> str:
        import torch
        import checkpoint
        self.q.put(("status", f"{label}: loading {model_dir}"))
        model, tok, _cfg = checkpoint.load_checkpoint(str(model_dir))
        params = sum(p.numel() for p in model.parameters())
        self.q.put(("info", f"{label}: {model_dir}  ({params / 1e6:.2f}M parameters)"))
        corpus = guess_corpus(model_dir) if label == "B" else (Path(s["corpus"]) if s["corpus"] else None)
        seen = corpus_keys(corpus) if (s["novel"] and corpus and corpus.is_file()) else set()
        run = SCRATCH / time.strftime("%Y%m%d-%H%M%S") / label
        (run / "tasks").mkdir(parents=True, exist_ok=True)
        rows, texts = {}, {}
        torch.manual_seed(1)
        for i in range(s["n"]):
            if self.stop_flag.is_set():
                break
            self.q.put(("status", f"{label}: sampling {i + 1} of {s['n']}"))
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
                if s["novel"]:
                    k = task_key(task)
                    r["novel"] = k not in seen if corpus else None
                if r["wf"] and (r["novel"] is not False or not s["novel"]):
                    (run / "tasks" / f"{name}.t").write_text(surface.print_task(task), encoding="utf-8")
            (run / f"{name}.txt").write_text(text, encoding="utf-8")
            if s["custom"]:
                cmd = s["custom"].replace("{file}", shlex.quote(str(run / f"{name}.txt")))
                r["custom"] = subprocess.run(cmd, shell=True, capture_output=True).returncode == 0
            rows[name], texts[name] = r, text
            self.emit(label, i, name, r, s, texts[name])
        if s["kernels"] and any((run / "tasks").iterdir()) and not self.stop_flag.is_set():
            n_tasks = len(list((run / "tasks").iterdir()))
            self.q.put(("status", f"{label}: grading {n_tasks} samples in {', '.join(s['kernels'])} (watch the Runs tab)"))
            env = dict(os.environ, PATH=KERNEL_PATH + ":" + os.environ.get("PATH", ""), T_WATCH=str(EVENTS),
                       T_MIN_KERNELS="1")
            EVENTS.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["python3", str(HERE / "run_par.py"), "--kernels", ",".join(s["kernels"]),
                            "--jobs", str(s["jobs"]), "--tasks", str(run / "tasks"), "--out", str(run / "kernels"),
                            "--table", str(run / "table.md")], env=env, capture_output=True)
            try:
                header = None
                for line in (run / "table.md").read_text().splitlines():
                    cells = [c.strip() for c in line.strip().strip("|").split("|")]
                    if cells and cells[0] == "task":
                        header = cells
                    elif header and cells and cells[0] in rows:
                        rows[cells[0]]["k"] = dict(zip(header[1:], cells[1:]))
            except OSError:
                pass
            for i, name in enumerate(rows):
                self.emit(label, i, name, rows[name], s, texts[name])
        # summary for this model
        n = len(rows)
        def count(fn):
            return sum(1 for r in rows.values() if fn(r))
        parts = [f"{label}: {n} samples, {params / 1e6:.2f}M parameters"]
        if s["parse"]:
            parts.append(f"parse {count(lambda r: r['parse'])}")
        if s["wf"]:
            parts.append(f"well-formed {count(lambda r: r['wf'])}")
        if s["novel"]:
            parts.append(f"novel {count(lambda r: r['novel'])}" if corpus else "novel: no corpus given")
        for k in s["kernels"]:
            parts.append(f"{k} {count(lambda r, k=k: r['k'].get(k) == 'verified / refuted')}")
        if s["custom"]:
            parts.append(f"yours {count(lambda r: r['custom'])}")
        parts.append(f"PASS ALL {count(lambda r: self.passes(r, s))} ({100 * count(lambda r: self.passes(r, s)) / max(n, 1):.1f}%)")
        self.q.put(("status", f"{label}: done, samples and tables in {run}"))
        return ", ".join(parts)

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
        def yn(v):
            return "" if v is None else ("yes" if v else "no")
        kcells = [(r["k"].get(k, "") if k in s["kernels"] else "") for k in KERNELS]
        values = (label, i, yn(r["parse"]), yn(r["wf"]), yn(r["novel"]), *kcells, yn(r["custom"]),
                  yn(self.passes(r, s)))
        self.q.put(("row", (name, values, text, self.passes(r, s))))


def main() -> int:
    root = tk.Tk()
    root.title("t lab: the filter and its models")
    w, h = min(1380, root.winfo_screenwidth() - 20), min(840, root.winfo_screenheight() - 60)
    root.geometry(f"{w}x{h}+10+30")
    Lab(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
