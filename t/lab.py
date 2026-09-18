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

# the data run of internal/HANDOFF-2026-09-17-rtx4080.md, one button per step; commands run from the repo root
PY = "~/.venv-t/bin/python"
SE = "t/out/spec-experiment"
GEN = "qwen2.5-coder-14b-v3-s"
HELDOUT = "phi4-mini-v3 qwen15b-base-v3 student-r4-v3 locallm-r4"
POOL_TAGS = "qwen3.8-27b-fp8 qwen3.8-27b-fp8-v3 qwen3.8-27b-fp8-v3-s2 " + " ".join(f"{GEN}{i}" for i in range(1, 9))
EVAL = "--pool v3 --prompt v3 --ids-file t/out/loop/eval-ids.txt"
GEN2 = "deepseek-coder-v2:16b"      # a second generator family, for answers the first one does not write
GEN2_TAG = "deepseek-coder-v2-16b-v4-s"
HE = "qwen2.5-coder-14b-he-s"       # the first generator on pool v4's HumanEval problems
QWEN_FIX = " ".join(f"{GEN}{i}-fix1" for i in range(1, 9))
GROWTH_TAGS = " ".join([f"{HE}{i}" for i in range(1, 9)] + [f"{GEN2_TAG}{i}" for i in (1, 2)])
GROWTH_FIX = " ".join(f"{t}-fix1" for t in GROWTH_TAGS.split())
# every answer set whose clean answers train a model: the 27B's, then everything this run wrote
SAMPLE_TAGS = ("$(cd t/out/spec-experiment && ls -d qwen3.8-27b-fp8 qwen3.8-27b-fp8-v3 qwen3.8-27b-fp8-v3-s2 "
               "qwen2.5-coder-14b-* deepseek-coder-v2-16b-* 2>/dev/null)")
# (key, title, what it does and what good looks like, command, done when this succeeds, uses: gpu/cpu/sudo/"")
STEPS = [
    ("packages", "Python packages", "Installs the training libraries into ~/.venv-t.",
     f"{PY} -m pip install transformers peft trl datasets accelerate bitsandbytes safetensors",
     f"{PY} -c 'import transformers, peft, trl, datasets, accelerate, bitsandbytes'", ""),
    ("data", "Committed data", "Copies the 2026-09-16 answers and split into t/out. Good: the score table's clean "
     "column reads 12 and 0.",
     "mkdir -p t/out/spec-experiment t/out/loop && cp -r t/runs/2026-09-16/27b-answers/* t/out/spec-experiment/ && "
     "cp -r t/runs/2026-09-16/heldout-locallm-r0 t/out/spec-experiment/locallm-r0 && "
     "cp t/runs/2026-09-16/loop-data/{split-v3.json,sft-r3-27b.jsonl,pairs-r3-27b.jsonl} t/out/loop/ && "
     "python3 -c \"import json; print('\\n'.join(map(str, json.load(open('t/out/loop/split-v3.json'))['eval_ids'])))\" "
     "> t/out/loop/eval-ids.txt && python3 t/score_heldout.py qwen3.8-27b-fp8-v3 locallm-r0 && "
     "for T in qwen3.8-27b-fp8 qwen3.8-27b-fp8-v3 qwen3.8-27b-fp8-v3-s2; do python3 t/pool_pick.py t/out/spec-experiment/$T; done",
     "test -s t/out/loop/eval-ids.txt && test -s t/out/pool-keys.txt", ""),
    ("ollama-install", "Install Ollama", "Opens a terminal because it asks for your password. Turns off Ollama's own "
     "service afterwards so the next step owns the port.",
     "curl -fsSL https://ollama.com/install.sh | sh && sudo systemctl disable --now ollama",
     "command -v ollama", "sudo"),
    ("ollama-serve", "Start Ollama", "Keeps running in the background, also after this window closes. Models live in "
     "/data/ollama. Flash attention and an 8-bit KV cache keep 4 parallel answers inside the 16 GB card, "
     "so nothing spills into the 14 GB of RAM.", "OLLAMA_MODELS=${OLLAMA_MODELS:-/data/ollama} OLLAMA_NUM_PARALLEL=4 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 exec ollama serve",
     "curl -sf http://127.0.0.1:11434/ >/dev/null", ""),
    ("pull", "Download qwen2.5-coder:14b", "About 9 GB. Needs Ollama started.", "ollama pull qwen2.5-coder:14b",
     # on disk, not through the server: a pulled model stays pulled while Ollama is stopped for a GPU step
     'test -e "${OLLAMA_MODELS:-/data/ollama}/manifests/registry.ollama.ai/library/qwen2.5-coder/14b" || '
     "ollama list 2>/dev/null | grep -q 'qwen2.5-coder:14b'", ""),
    ("generate", "Write answers, 8 seeds", "Hours. Seed 1 at temperature 0, seeds 2 to 8 at 0.7. A finished seed is "
     "skipped, so Stop and Run again resumes. Good: each seed puts tasks in grade-in/.",
     f"for S in 1 2 3 4 5 6 7 8; do T={GEN}$S; D={SE}/$T; [ -d $D/grade-in ] && continue; TEMP=0.7; [ $S = 1 ] && TEMP=0; "
     "echo \"== seed $S\"; python3 t/spec_experiment.py generate --model qwen2.5-coder:14b --tag $T --pool v3 --prompt v3 "
     "--seed $S --temperature $TEMP --num-ctx 8192 --num-predict 3072 --timeout 1800 --jobs 4 && "
     "python3 t/spec_experiment.py extract --model $T --pool v3 && python3 t/spec_experiment.py tests --model $T --pool v3 && "
     "python3 t/pool_pick.py $D && ls $D/grade-in | wc -l || exit 1; done",
     f"for S in 1 2 3 4 5 6 7 8; do [ -d {SE}/{GEN}$S/grade-in ] || exit 1; done", "gpu"),
    ("matrix", "Check the checkers", "On the lab workstation, where all grading runs: regrades the 34 committed tasks. "
     "Good: 30 of 34 in all seven, as in t/AGREEMENT.md. Table comes back to t/out/AGREEMENT-lab.md.",
     "bash t/grade_lab.sh matrix", "test -s t/out/AGREEMENT-lab.md", "lab"),
    ("grade", "Grade the answers", "On the lab workstation (120 threads, CPU only, 16 jobs; every checker run of "
     "this project goes there): sends each finished "
     "seed's grade-in/, brings kernels.md back, checks show on Live checks. Runs T_VPN_CMD first when the "
     "workstation needs a VPN. Skips graded seeds, so Run again after more seeds finish.", "bash t/grade_lab.sh seeds",
     f"for S in 1 2 3 4 5 6 7 8; do [ -s {SE}/{GEN}$S/kernels.md ] || exit 1; done", "lab"),
    ("more-problems", "New problems and a second model", "Needs Ollama started. The 88 HumanEval problems of pool v4 "
     f"(8 answer sets, as for MBPP), then {GEN2} over all 737 problems (seed 1 at temperature 0, seed 2 at 0.7).",
     f"for S in 1 2 3 4 5 6 7 8; do T={HE}$S; D={SE}/$T; [ -d $D/grade-in ] && continue; TEMP=0.7; [ $S = 1 ] && TEMP=0; "
     "python3 t/spec_experiment.py generate --model qwen2.5-coder:14b --tag $T --pool v4 --min-id 100000 --prompt v3 "
     "--seed $S --temperature $TEMP --num-ctx 8192 --num-predict 3072 --timeout 1800 --jobs 4 && "
     "python3 t/spec_experiment.py extract --model $T --pool v4 && python3 t/spec_experiment.py tests --model $T --pool v4 && "
     f"python3 t/pool_pick.py $D || exit 1; done && ollama pull {GEN2} && "
     f"for S in 1 2; do T={GEN2_TAG}$S; D={SE}/$T; [ -d $D/grade-in ] && continue; TEMP=0.7; [ $S = 1 ] && TEMP=0; "
     f"python3 t/spec_experiment.py generate --model {GEN2} --tag $T --pool v4 --prompt v3 "
     "--seed $S --temperature $TEMP --num-ctx 6144 --num-predict 2048 --timeout 1800 --jobs 2 && "
     "python3 t/spec_experiment.py extract --model $T --pool v4 && python3 t/spec_experiment.py tests --model $T --pool v4 && "
     "python3 t/pool_pick.py $D || exit 1; done",
     f"for T in {GROWTH_TAGS}; do [ -d {SE}/$T/grade-in ] || exit 1; done", "gpu"),
    ("grade-growth", "Grade new problems and model", "On the lab workstation.", f"bash t/grade_lab.sh tags {GROWTH_TAGS}",
     f"n=0; for T in {GROWTH_TAGS}; do [ -d {SE}/$T/grade-in ] || continue; n=$((n+1)); "
     f"[ -s {SE}/$T/kernels.md ] || exit 1; done; [ $n -gt 0 ]", "lab"),
    ("pool", "Build the clean pool", "Every answer set that is not a held-out one, over split-v4 (split-v3's held-out "
     "problems unchanged, plus HumanEval as training problems). Good: many more problems than the 47 of r3.",
     f"python3 t/loop_dataset.py --from-samples {SAMPLE_TAGS} --split t/out/loop/split-v4.json --min-kernels 7 "
     "--out-suffix r4 && wc -l t/out/loop/sft-r4.jsonl t/out/loop/pairs-r4.jsonl",
     "test -s t/out/loop/sft-r4.jsonl", ""),
    ("phi", "Phi-4-mini answers", "The model to beat, in bf16, on the 232 held-out problems. If it fails, go back to "
     "deciding, before using a 4-bit Phi.",
     f"{PY} t/loop_generate.py --adapter none --base microsoft/Phi-4-mini-instruct --tag phi4-mini-v3 {EVAL} --max-new 3072",
     f"test $(ls {SE}/phi4-mini-v3/raw 2>/dev/null | wc -l) -ge 232", "gpu"),
    ("base", "Small base answers", "The untrained 1.5B, the starting point of the student.",
     f"{PY} t/loop_generate.py --adapter none --tag qwen15b-base-v3 {EVAL}",
     f"test $(ls {SE}/qwen15b-base-v3/raw 2>/dev/null | wc -l) -ge 232", "gpu"),
    ("train", "Train the student", "The 1.5B trained on the clean pool.",
     # --max-len 4608: the prompt alone is about 3,100 tokens (the few-shot grammar) and the default 1024
     # dropped every pair as fully truncated, so the preference phase got nothing (2026-09-17)
     f"{PY} t/loop_train.py --sft t/out/loop/sft-r4.jsonl --pairs t/out/loop/pairs-r4.jsonl --sft-first "
     "--max-len 4608 --out t/out/loop/adapter-r4",
     "test -s t/out/loop/adapter-r4/adapter_model.safetensors", "gpu"),
    ("student", "Student answers", "", f"{PY} t/loop_generate.py --adapter t/out/loop/adapter-r4 --tag student-r4-v3 {EVAL}",
     f"test $(ls {SE}/student-r4-v3/raw 2>/dev/null | wc -l) -ge 232", "gpu"),
    ("locallm", "Build a locallm model", "From scratch, on the clean pool, then its held-out answers.",
     "python3 t/loop_locallm.py corpus --base t/runs/2026-09-16/loop-data/corpus.txt --sft t/out/loop/sft-r4.jsonl "
     f"--out t/out/loop-locallm/corpus-r4.txt && {PY} t/loop_locallm.py train --corpus t/out/loop-locallm/corpus-r4.txt "
     f"--model t/out/loop-locallm/model-r4 && {PY} t/loop_locallm.py generate --model t/out/loop-locallm/model-r4 --tag locallm-r4",
     f"test $(ls {SE}/locallm-r4/raw 2>/dev/null | wc -l) -ge 232", "gpu"),
    ("grade-heldout", "Grade held-out answers", "Every extracted task this time, so proven but wrong can be "
     "counted. Extract and tests run here, the checkers on the lab workstation.", "bash t/grade_lab.sh heldout",
     f"for T in {HELDOUT}; do [ -s {SE}/$T/kernels.md ] || exit 1; done", "lab"),
    ("score", "Score against Phi", "The result. Saved to t/out/score-r4.md.",
     f"python3 t/score_heldout.py qwen3.8-27b-fp8-v3 {HELDOUT} locallm-r0 | tee t/out/score-r4.md",
     "test -s t/out/score-r4.md", ""),
]
STEPS_DEFAULT = STEPS
# What must be finished before a step can start. t/autopilot.py reads this; a key missing here has no
# prerequisites. Not a schedule: the orchestrator and a person may still run a step whenever they like.
NEEDS = {
    "data": ["packages"], "ollama-serve": ["ollama-install"], "pull": ["ollama-serve"], "run-all": ["data"],
    "generate": ["pull", "data"], "grade": ["generate"],
    # a grading step takes whatever answer sets exist and skips the rest, so it waits on nothing
    "grade-growth": [],
    "more-problems": ["pull", "data"],
    "phi": ["data", "packages"], "base": ["data", "packages"],
    "pool": ["grade", "grade-growth"], "train": ["pool"],
    "student": ["train"], "locallm": ["pool"], "grade-heldout": ["phi"], "score": ["grade-heldout"],
}
RUNS = HERE / "runs" / time.strftime("%Y-%m-%d")
STEPS_FILE = HERE / "steps.json"


def load_steps() -> list:
    """The Collect data steps. t/steps.json wins when it is there, so a step can be added, reordered or its
    command changed without touching this file; the list above is written out as the starting point the first
    time t lab runs. One entry: [key, title, what it does, shell command, test that says it is done, uses]
    where uses is "" (anything), "gpu" (the graphics card), "cpu" (this machine's cores) or "lab" (the lab
    workstation over SSH). Press Reload steps after editing. Progress counting is by key; a new key with no
    rule shows none."""
    try:
        got = json.loads(STEPS_FILE.read_text(encoding="utf-8"))
        rows = [tuple(r[:6]) for r in got if isinstance(r, list) and len(r) >= 6]
        if rows:
            return rows
    except (OSError, ValueError):
        pass
    try:
        STEPS_FILE.write_text(json.dumps([list(s) for s in STEPS_DEFAULT], indent=1) + "\n", encoding="utf-8")
    except OSError:
        pass
    return list(STEPS_DEFAULT)


SPEC_EXP = HERE / "out" / "spec-experiment"
GEOMETRY = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "t-lab" / "geometry"
STEPS = load_steps()
STEPS_TITLE = [(s[0], s[1]) for s in STEPS]

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
    """The program with its name, format version and gate erased (rename_task
    edits in place, so a copy). None of the three changes what the kernels
    check; keeping the version let a `t 1` sample copy a `t 0` corpus task
    unseen (loop_filter.key, 2026-09-17)."""
    t = se.rename_task(copy.deepcopy(task), "x_task")
    t.pop("gate", None); t["t"] = 1
    return surface.canon(t)


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
        EVENTS.parent.mkdir(parents=True, exist_ok=True)   # run_par.py drops events silently when the folder is missing
        self.offset = EVENTS.stat().st_size if EVENTS.exists() else 0
        self.running: dict[tuple[str, str], dict] = {}
        self.counts = {"done": 0, "proven": 0, "not": 0}
        self.samples: dict[str, str] = {}
        self.end_times: list[float] = []     # every finished check's time, for the data run's progress bar
        self.end_pairs: list[tuple[float, str]] = []   # (time, task) for the same, to count one answer set's own
        try:                                 # earlier checks too, so a reopened window keeps a running bar right
            self.end_pairs = [(json.loads(l).get("t", 0), json.loads(l).get("task", ""))
                              for l in EVENTS.read_text(errors="replace").splitlines() if '"ev": "end"' in l]
            self.end_times = [t for t, _ in self.end_pairs]
        except (OSError, ValueError):
            pass

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
        for name in ("Live checks", "Test a model", "Collect data", "Results", "AI"):
            b = tk.Label(tabs, text=name, cursor="hand2", padx=18, pady=7, font=self.f_bold)
            b.pack(side="left", padx=(0, 8))
            b.bind("<Button-1>", lambda _e, n=name: self.show_page(n))
            self.tab_buttons[name] = b
            self.pages[name] = tk.Frame(body, bg=BG)
        self.build_live(self.pages["Live checks"])
        Button(self.follow_btn_parent, "Follow a loop run", self.follow_loop, BLUE, self,
               filled=False).pack(side="right", padx=(0, 16))
        self.build_test(self.pages["Test a model"])
        self.build_collect(self.pages["Collect data"])
        self.build_results(self.pages["Results"])
        self.build_ai(self.pages["AI"])
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
                        self.end_times.append(ev.get("t", time.time()))
                        self.end_pairs.append((ev.get("t", time.time()), ev.get("task", "")))
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
                if kind == "results":
                    self.show_results(*payload)
                elif kind == "status":
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

    # -- Collect data ----------------------------------------------------------------
    USES_WORDS = {"gpu": "graphics card", "cpu": "cores here", "lab": "lab workstation"}

    def reload_steps(self):
        """Re-read t/steps.json and rebuild the boxes, so a step added by hand appears without a restart."""
        STEPS[:] = load_steps()
        for w in list(self.box_area.winfo_children()):
            w.destroy()
        self.boxes = {}
        self.build_boxes()
        self.step_hint.configure(text=f"{len(STEPS)} steps from t/steps.json", fg=FAINT)

    def build_boxes(self):
        """One box per step: what it is, a bar with its percentage, its own Run button. Green while it runs."""
        for i, (key, title, what, _cmd, _check, uses) in enumerate([s[:6] for s in STEPS], 1):
            box = tk.Frame(self.box_area, bg=CARD, highlightthickness=2, highlightbackground=LINE)
            box.pack(fill="x", pady=(0, 8))
            edge = tk.Frame(box, bg=LINE, width=4)
            edge.pack(side="left", fill="y")
            body = tk.Frame(box, bg=CARD)
            body.pack(side="left", fill="both", expand=True, padx=12, pady=10)
            head = tk.Frame(body, bg=CARD)
            head.pack(fill="x")
            name = tk.Label(head, text=f"{i}.  {title}", bg=CARD, fg=TEXT, font=self.f_h2)
            name.pack(side="left")
            state = tk.Label(head, text="not yet", bg=CARD, fg=FAINT, font=self.f_bold)
            state.pack(side="right")
            Button(head, "Run", lambda k=key: self.run_step(k), GREEN, self).pack(side="right", padx=10)
            where = self.USES_WORDS.get(uses, "")
            tk.Label(head, text=f"on the {where}" if where else "", bg=CARD, fg=MUTED,
                     font=self.f_small).pack(side="right", padx=8)
            bar = tk.Canvas(body, bg=SURFACE, height=8, highlightthickness=0)
            bar.pack(fill="x", pady=(8, 4))
            prog = tk.Label(body, text="", bg=CARD, fg=MUTED, font=self.f_small, anchor="w")
            prog.pack(fill="x")
            desc = tk.Label(body, text=what, bg=CARD, fg=FAINT, font=self.f_small, justify="left", anchor="w",
                            wraplength=1100)
            desc.pack(fill="x", pady=(2, 0))
            self.boxes[key] = {"box": box, "edge": edge, "state": state, "bar": bar, "prog": prog,
                               "paint": [box, body, head, name, state, prog, desc]}
            for w in (box, body, head, name, desc, prog):
                w.bind("<Button-1>", lambda _e, k=key: self.select_step(k))

    def scroll_by(self, pixels: float):
        """A wheel notch moves a target, which scroll_ease glides towards: smooth instead of jumping by rows."""
        if self.pages["Collect data"].winfo_ismapped():
            span = max(1, self.box_area.winfo_height() - self.scroll_canvas.winfo_height())
            self.scroll_to = min(1.0, max(0.0, self.scroll_to + pixels / span))

    def scroll_ease(self):
        at = self.scroll_canvas.yview()[0]
        if abs(self.scroll_to - at) > 0.0008:
            self.scroll_canvas.yview_moveto(at + (self.scroll_to - at) * 0.22)
        else:
            self.scroll_to = at
        self.root.after(16, self.scroll_ease)

    def select_step(self, key: str):
        self.sel_key = key
        self.show_log()
        self.refresh_steps(once=True)

    def restart_app(self):
        """Reload t lab's own code in place, keeping the window where it is: the geometry is written to
        GEOMETRY and read back on start, so a refresh after an edit costs no repositioning."""
        try:
            GEOMETRY.parent.mkdir(parents=True, exist_ok=True)
            GEOMETRY.write_text(self.root.winfo_geometry())
        except OSError:
            pass
        self.root.destroy()
        os.execv(sys.executable, [sys.executable, str(HERE / "lab.py")])

    def build_collect(self, page):
        self.jobs: dict[str, subprocess.Popen] = {}
        self.step_state: dict[str, str] = {}
        self.step_prog: dict[str, tuple] = {}
        self.boxes: dict[str, dict] = {}
        self.sel_key = STEPS[0][0]
        (RUNS / "logs").mkdir(parents=True, exist_ok=True)
        head = tk.Frame(page, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text="Collect data", bg=BG, fg=TEXT, font=self.f_h2).pack(side="left")
        self.step_hint = tk.Label(head, text="", bg=BG, fg=FAINT, font=self.f_small)
        self.step_hint.pack(side="left", padx=12)
        Button(head, "Open notes", lambda: subprocess.Popen(["xdg-open", str(RUNS / "NOTES-home.md")]), BLUE, self,
               filled=False).pack(side="right")
        Button(head, "Reload steps", self.reload_steps, BLUE, self, filled=False).pack(side="right", padx=8)
        Button(head, "Refresh t lab", self.restart_app, BLUE, self, filled=False).pack(side="right", padx=8)
        self.show_done = tk.BooleanVar(value=False)
        Chip(head, "Show finished", self.show_done, self, command=lambda: self.refresh_steps(once=True)).pack(
            side="right", padx=8)
        Button(head, "Stop", lambda: self.stop_step(self.sel_key), RED, self, filled=False).pack(side="right", padx=8)

        holder = tk.Frame(page, bg=BG)          # scrollable: there are more steps than fit on a screen
        holder.pack(fill="both", expand=True, pady=(10, 0))
        canvas = tk.Canvas(holder, bg=BG, highlightthickness=0)
        sbar = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sbar.set)
        sbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.box_area = tk.Frame(canvas, bg=BG)
        window = canvas.create_window((0, 0), window=self.box_area, anchor="nw")
        self.box_area.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        self.scroll_canvas, self.scroll_to = canvas, 0.0
        canvas.bind_all("<Button-4>", lambda _e: self.scroll_by(-120))
        canvas.bind_all("<Button-5>", lambda _e: self.scroll_by(120))
        canvas.bind_all("<MouseWheel>", lambda e: self.scroll_by(-e.delta))
        self.root.after(16, self.scroll_ease)
        self.build_boxes()

        c = self.card(page, "Output", "last lines of the chosen step's log", fill="x", pady=(10, 0))
        self.log_text = tk.Text(c, bg=SURFACE, fg=TEXT, font=self.f_mono, relief="flat", height=9, wrap="none")
        self.log_text.pack(fill="both", expand=True)
        live = self.pages["Live checks"]
        strip = tk.Frame(live, bg=CARD, highlightthickness=1, highlightbackground=LINE)
        strip.pack(fill="x", pady=(0, 12), before=live.winfo_children()[0])
        tk.Frame(strip, bg=GREEN, width=3).pack(side="left", fill="y")
        self.run_line = tk.Label(strip, text="", bg=CARD, fg=TEXT, font=self.f_bold, anchor="w", padx=14, pady=8)
        self.run_line.pack(side="left")
        self.run_bar = tk.Canvas(strip, bg=SURFACE, height=10, width=260, highlightthickness=0)
        self.run_bar.pack(side="left", padx=(0, 12))
        self.run_tail = tk.Label(strip, text="", bg=CARD, fg=MUTED, font=self.f_mono, anchor="w")
        self.run_tail.pack(side="left", fill="x", expand=True)
        Button(strip, "Open Collect data", lambda: self.show_page("Collect data"), BLUE, self,
               filled=False).pack(side="right", padx=8, pady=6)
        threading.Thread(target=self.check_steps, daemon=True).start()
        self.root.after(1000, self.refresh_steps)
    # -- AI ---------------------------------------------------------------------------
    def build_ai(self, page):
        """The two things that run the run: the orchestrator (a fixed plan) and the autopilot (a local model
        choosing the next legal step every minute). Both live here rather than among the data steps."""
        c = self.card(page, "Orchestrator", "t/run_everything.py: the fixed plan, start to score, unattended")
        tk.Label(c, bg=CARD, fg=MUTED, font=self.f_small, justify="left", wraplength=1200, anchor="w", text=(
            "Runs the steps of Collect data in order without asking: it waits for each one, retries a failed step "
            "once, writes what it did to NOTES-home.md and raises an alert it cannot fix. Press the steps by hand "
            "instead whenever you would rather drive.")).pack(fill="x", pady=(0, 6))
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x", pady=(0, 8))
        self.orch_state = tk.Label(row, text="", bg=CARD, fg=TEXT, font=self.f_bold)
        self.orch_state.pack(side="left")
        Button(row, "Run everything", self.start_orchestrator, GREEN, self).pack(side="right")
        Button(row, "Stop", lambda: self.unit("stop", "t-run-all"), RED, self, filled=False).pack(side="right", padx=8)
        self.orch_log = tk.Text(c, bg=SURFACE, fg=TEXT, font=self.f_mono, relief="flat", height=6, wrap="none")
        self.orch_log.pack(fill="x")

        c = self.card(page, "Alerts", "what the autopilot could not fix: t/runs/<date>/ALERTS.md", fill="both",
                      expand=True)
        self.alert_text = tk.Text(c, bg=SURFACE, fg=TEXT, font=self.f_mono, relief="flat", height=10, wrap="word")
        self.alert_text.pack(fill="both", expand=True)
        self.root.after(2000, self.tick_ai)

    @staticmethod
    def unit(verb: str, name: str):
        subprocess.Popen(["systemctl", "--user", verb, name])

    def start_orchestrator(self):
        (RUNS / "logs").mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["bash", "-lc",
                          "systemctl --user reset-failed t-run-all 2>/dev/null; systemd-run --user --unit=t-run-all "
                          f"--working-directory={TUP} -p StandardOutput=append:{RUNS}/logs/run-all.log "
                          f"-p StandardError=append:{RUNS}/logs/run-all.log --setenv=HOME=$HOME --setenv=DISPLAY=:0 "
                          "/usr/bin/python3 t/run_everything.py"], cwd=TUP)

    def tick_ai(self):
        def active(name):
            return subprocess.run(["systemctl", "--user", "is-active", name],
                                  capture_output=True, text=True).stdout.strip()
        st = active("t-run-all")
        self.orch_state.configure(text=f"●  {st}", fg=GREEN if st == "active" else FAINT)
        for widget, path, n in ((self.orch_log, RUNS / "logs" / "run-all.log", 8),
                                (self.alert_text, RUNS / "ALERTS.md", 60)):
            try:
                text = "\n".join(path.read_text(errors="replace").splitlines()[-n:]) or "nothing yet"
            except OSError:
                text = "nothing yet"
            if widget.get("1.0", "end").strip() != text.strip():
                widget.delete("1.0", "end")
                widget.insert("end", text)
                widget.see("end")
        self.root.after(5000, self.tick_ai)

    # -- Results ---------------------------------------------------------------------
    def build_results(self, page):
        c = self.card(page, "Answer sets", "counted from tests.json and kernels.md, refreshed every 30 seconds")
        tk.Label(c, bg=CARD, fg=MUTED, font=self.f_small, justify="left", wraplength=1200, anchor="w", text=(
            "Clean: the tests pass and all seven checkers proved it with the broken copy caught. Proven but wrong: "
            "all seven proved it and the tests fail, which is the number that must stay small. Problems: distinct "
            "problems with a clean answer.")).pack(fill="x", pady=(0, 8))
        self.res_table = self.table(c, [("set", "Answer set", 320), ("graded", "Graded", 80), ("clean", "Clean", 70),
                                      ("wrong", "Proven but wrong", 130), ("problems", "Problems", 90),
                                      ("passed", "Tests pass", 100), ("tasks", "Well formed", 100)], 12)
        c = self.card(page, "Pool and score", fill="both", expand=True)
        self.results_text = tk.Text(c, bg=SURFACE, fg=TEXT, font=self.f_mono, relief="flat", height=12, wrap="word")
        self.results_text.pack(fill="both", expand=True)
        threading.Thread(target=self.results_loop, daemon=True).start()

    @staticmethod
    def count_set(d: Path) -> dict:
        """One answer set: well-formed answers, tests passed, clean in all seven, proven but wrong, problems."""
        r = {"tasks": 0, "passed": 0, "graded": 0, "clean": 0, "wrong": 0, "problems": set()}
        try:
            ext = json.loads((d / "extract.json").read_text(errors="replace"))
            r["tasks"] = sum(1 for e in ext.values() if e.get("stage") == "task")
        except (OSError, ValueError):
            pass
        passing = set()
        try:
            tests = json.loads((d / "tests.json").read_text(errors="replace"))
            for v in tests.values():
                if v.get("overall") == "pass":
                    passing.add(v.get("name"))
            r["passed"] = len(passing)
        except (OSError, ValueError):
            pass
        cols, rows = [], {}
        try:
            for line in (d / "kernels.md").read_text(errors="replace").splitlines():
                if not line.startswith("|"):
                    continue
                cells = [x.strip() for x in line.strip().strip("|").split("|")]
                if cells[0] == "task":
                    cols = cells[1:]
                elif cols and len(cells) == len(cols) + 1 and set(cells[0]) - {"-"}:
                    rows[cells[0]] = dict(zip(cols, cells[1:]))
        except OSError:
            pass
        r["graded"] = len(rows)
        for name, row in rows.items():
            if len(cols) < len(KERNELS) or not all(row.get(k, "").startswith("verified / refuted") for k in KERNELS):
                continue
            if name in passing:
                r["clean"] += 1
                r["problems"].add(name.split("__")[0])
            elif r["passed"]:
                r["wrong"] += 1
        return r

    def results_loop(self):
        while True:
            sets, totals, problems = [], {k: 0 for k in ("tasks", "passed", "graded", "clean", "wrong")}, set()
            for d in sorted(SPEC_EXP.glob("*")) if SPEC_EXP.is_dir() else []:
                if not d.is_dir():
                    continue
                r = self.count_set(d)
                if not any(r[k] for k in ("tasks", "graded")):
                    continue
                sets.append((d.name, r))
                problems |= r["problems"]
                for k in totals:
                    totals[k] += r[k]
            lines = []
            for f, label in (("out/loop/sft-r4.jsonl", "clean answers in the new pool (sft-r4.jsonl)"),
                             ("out/loop/pairs-r4.jsonl", "answer/broken-copy pairs (pairs-r4.jsonl)"),
                             ("out/loop/sft-r3-27b.jsonl", "the earlier pool (sft-r3-27b.jsonl)")):
                path = HERE / f
                if path.exists():
                    lines.append(f"{sum(1 for _ in open(path)):>6}  {label}")
            for f in ("out/score-r4.md", "out/AGREEMENT-lab.md"):
                path = HERE / f
                if path.exists():
                    lines.append("")
                    lines.append(f"{f}, written {time.strftime('%H:%M', time.localtime(path.stat().st_mtime))}:")
                    lines.append(path.read_text(errors="replace").strip()[:4000])
            self.q.put(("results", (sets, totals, len(problems), "\n".join(lines) or "Nothing built yet.")))
            time.sleep(30)

    def show_results(self, sets, totals, n_problems, text):
        self.res_table.delete(*self.res_table.get_children())
        for name, r in sets:
            tag = "green" if r["clean"] else ("red" if r["wrong"] else "muted")
            self.res_table.insert("", "end", tags=(tag,), values=(
                name, r["graded"] or "", r["clean"] or "", r["wrong"] or "", len(r["problems"]) or "",
                r["passed"] or "", r["tasks"] or ""))
        self.res_table.insert("", "end", tags=("blue",), values=(
            f"all {len(sets)} answer sets", totals["graded"], totals["clean"], totals["wrong"], n_problems,
            totals["passed"], totals["tasks"]))
        if self.results_text.get("1.0", "end").strip() != text.strip():
            self.results_text.delete("1.0", "end")
            self.results_text.insert("end", text)

    def step_env(self):
        return dict(os.environ, PATH=KERNEL_PATH + os.pathsep + os.environ.get("PATH", ""), T_WATCH=str(EVENTS))

    def note(self, line):
        with open(RUNS / "NOTES-home.md", "a") as f:
            f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {line}\n")

    def title_of(self, key: str) -> str:
        return next((s[1] for s in STEPS if s[0] == key), key)

    def run_step(self, key: str):
        st = next((s for s in STEPS if s[0] == key), None)
        if st is None:
            return
        _key, title, _what, cmd, _check, uses = st[:6]
        live = {k for k, *_r in self.running_steps()}
        if key in live:
            self.step_hint.configure(text=f"{title} is already running.", fg=RED)
            return
        # one step per machine: this desktop can work while the lab workstation grades, but never two here
        # or two there
        where = "the lab workstation" if uses == "lab" else "this desktop"
        busy = [t for k, t, _w, _c, _ck, u, *_n in [s[:6] + (None,) for s in STEPS]
                if k in live and k not in ("ollama-serve", "run-all") and (u == "lab") == (uses == "lab")]
        if busy:
            self.step_hint.configure(text=f"Wait: {', '.join(busy)} is using {where}.", fg=RED)
            return
        unmet = [self.title_of(n) for n in NEEDS.get(key, []) if self.step_state.get(n) != "done"]
        if unmet:
            self.step_hint.configure(text=f"{title} needs {', '.join(unmet)} first.", fg=RED)
            return
        log = RUNS / "logs" / f"{key}.log"
        self.note(f"start `{key}`: `{cmd}` (log `logs/{key}.log`)")
        if uses == "sudo":
            script = RUNS / "logs" / f"{key}.sh"
            script.write_text(f"#!/bin/bash\ncd {shlex.quote(str(TUP))}\nsudo -v\n"
                              f"( {cmd} ) 2>&1 | tee -a {shlex.quote(str(log))}\nread -p 'Enter to close'\n")
            script.chmod(0o755)
            term = "ptyxis" if subprocess.run(["which", "ptyxis"], capture_output=True).returncode == 0 \
                else "x-terminal-emulator"
            subprocess.Popen([term, "-x", str(script)] if term == "ptyxis" else [term, "-e", str(script)])
            self.step_hint.configure(text=f"{title} opened in a terminal.", fg=MUTED)
            return
        out = open(log, "a")
        out.write(f"\n### {time.strftime('%Y-%m-%d %H:%M:%S')} {cmd}\n")
        out.flush()
        gpu_busy = any(u == "gpu" and k in live for k, _t, _w, _c, _ck, u in [s[:6] for s in STEPS])
        self.jobs[key] = subprocess.Popen(
            ["bash", "-lc", cmd], cwd=TUP, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True,
            env=dict(self.step_env(), T_JOBS="6" if uses == "cpu" and gpu_busy else "12"))
        self.jobs[key].started = time.time()
        (RUNS / "logs" / f"{key}.pid").write_text(f"{self.jobs[key].pid} {self.jobs[key].started}")
        self.sel_key = key
        self.step_hint.configure(text=f"{title} started.", fg=GREEN)
        if uses == "lab":
            self.show_page("Live checks")
        self.refresh_steps(once=True)

    def running_steps(self):
        """(key, title, started) for every step with a live process, including ones started before this window."""
        out = []
        for key, title, *_r in STEPS:
            job = self.jobs.get(key)
            if job:
                if job.poll() is None:
                    out.append((key, title, job.started))
                continue
            try:                     # the pid file alone lies: a dead step's number may belong to something else
                pid, started = (RUNS / "logs" / f"{key}.pid").read_text().split()
                os.kill(int(pid), 0)
                cmd = Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace").replace("\0", " ")
                want = next((s[3] for s in STEPS if s[0] == key), "")
                first = next((w for w in want.split() if "/" in w or w.endswith(".py") or w.endswith(".sh")), "")
                if (first and first in cmd) or key in cmd:
                    out.append((key, title, float(started)))
            except (OSError, ValueError):
                pass
        return out

    def stop_step(self, key: str):
        if key not in [k for k, *_r in self.running_steps()]:
            self.step_hint.configure(text=f"{self.title_of(key)} is not running.", fg=FAINT)
            return
        import signal
        job = self.jobs.get(key)
        pid = job.pid if job else int((RUNS / "logs" / f"{key}.pid").read_text().split()[0])
        os.killpg(pid, signal.SIGTERM)
        self.note(f"stopped `{key}` by hand")
        self.step_hint.configure(text=f"{self.title_of(key)} stopped.", fg=RED)

    def check_steps(self):
        while True:
            for key, _t, _w, _c, check, _u in [s[:6] for s in STEPS]:
                ok = subprocess.run(["bash", "-lc", check], cwd=TUP, capture_output=True,
                                    env=self.step_env()).returncode == 0
                self.step_state[key] = "done" if ok else ""
                self.step_prog[key] = self.progress_of(key)
            time.sleep(10)

    @staticmethod
    def answers(tag: str) -> int:
        try:
            return sum(1 for _ in (SPEC_EXP / tag / "raw").glob("*.json"))
        except OSError:
            return 0

    def progress_of(self, key: str) -> tuple:
        """(what it has produced so far, how far along from 0 to 1), counted from the files themselves."""
        heldout = {"phi": ("phi4-mini-v3", 232), "base": ("qwen15b-base-v3", 232),
                   "student": ("student-r4-v3", 232), "locallm": ("locallm-r4", 232)}
        if key in heldout:
            tag, total = heldout[key]
            n = self.answers(tag)
            return f"{n} of {total} answers", n / total
        if key == "generate":
            per = [self.answers(f"{GEN}{i}") for i in range(1, 9)]
            whole = sum(1 for n in per if n >= 649)
            total = 8 * 649
            return (("all 8 seeds written" if whole == 8 else
                     f"{sum(per)} of {total} answers, seed {whole + 1}"), sum(per) / total)
        if key == "more-problems":
            he, ds = [self.answers(f"{HE}{i}") for i in range(1, 9)], [self.answers(f"{GEN2_TAG}{i}") for i in (1, 2)]
            total = 8 * 88 + 2 * 737
            return (f"{sum(he)} of {8 * 88} HumanEval, {sum(ds)} of {2 * 737} second model",
                    (sum(he) + sum(ds)) / total)
        if key in ("repair", "repair-growth"):
            tags = QWEN_FIX.split() if key == "repair" else GROWTH_FIX.split()
            n = sum(self.answers(t) for t in tags)
            return f"{n} answers repaired", (1.0 if self.step_state.get(key) == "done" else None) if not n else None
        graded = {"grade": [f"{GEN}{i}" for i in range(1, 9)], "grade-repair": QWEN_FIX.split(),
                  "grade-growth": GROWTH_TAGS.split(), "grade-growth-repair": GROWTH_FIX.split(),
                  "grade-heldout": HELDOUT.split()}
        if key in graded:
            tags = graded[key]
            done_n = sum(1 for t in tags if (SPEC_EXP / t / "kernels.md").exists())
            waiting = sum(1 for t in tags if (SPEC_EXP / t / "grade-in").is_dir()) or len(tags)
            part, part_text = 0.0, ""
            here = [st for k, _t, st in self.running_steps() if k == key]
            if here:                           # the set being graded now, cell by cell, so the bar keeps moving
                tag, tasks = self.grading_now(key)
                if tag:
                    total = tasks * len(KERNELS)
                    # the step's own lines, one per cell: a cell that abstains runs no checker and sends no
                    # event, and seed 7's Rocq column is mostly abstains (nested loops), so events alone stall
                    done_c = self.cells_printed(key)
                    part = min(1.0, done_c / total) if total else 0.0
                    part_text = f"; {tag.split('-')[-1]} at {min(done_c, total)} of {total} cells"
            return (f"{done_n} of {waiting} answer sets{part_text}",
                    min(1.0, (done_n + part) / waiting))
        return "", None

    def cells_printed(self, key: str) -> int:
        """Cells the running step has reported since it last said which answer set it is on."""
        try:
            lines = (RUNS / "logs" / f"{key}.log").read_text(errors="replace").splitlines()
        except OSError:
            return 0
        start = max((i for i, l in enumerate(lines) if re.match(r"== \S+: \d+ tasks", l)), default=0)
        return sum(1 for l in lines[start:] if re.match(r"  \S+ x \S+", l))

    def grading_now(self, key: str) -> tuple:
        """(tag, task count) of the answer set a grading step is working on, from its log's own line."""
        try:
            lines = (RUNS / "logs" / f"{key}.log").read_text(errors="replace").splitlines()
        except OSError:
            return "", 0
        for line in reversed(lines):
            m = re.match(r"== (\S+): (\d+) tasks", line)
            if m:
                if f"== {m.group(1)}: kernels.md back" in "\n".join(lines[-40:]):
                    return "", 0
                return m.group(1), int(m.group(2))
        return "", 0

    def refresh_steps(self, once: bool = False):
        live = {k: (t, st) for k, t, st in self.running_steps()}
        finished = 0
        for key, title, *_r in STEPS:
            b = self.boxes.get(key)
            if b is None:
                continue
            job, state, color = self.jobs.get(key), self.step_state.get(key, ""), FAINT
            if key in live:
                state, color = f"running {int(time.time() - live[key][1]) // 60} min", GREEN
            elif job and not getattr(job, "noted", False):
                job.noted = True
                self.note(f"end `{key}`: exit {job.returncode} after {int(time.time() - job.started) // 60} min")
            if state == "done":
                state, color, finished = "done", GREEN, finished + 1
            elif job is not None and job.poll() not in (None, 0) and key not in live:
                state, color = f"failed ({job.returncode})", RED
            prog, frac = self.step_prog.get(key, ("", None))
            if state == "done" and frac is None:
                frac = 1.0
            b["state"].configure(text=state or "not yet", fg=color)
            b["prog"].configure(text=(f"{prog}   {frac * 100:.0f}%" if frac is not None and prog else
                                      prog or (f"{frac * 100:.0f}%" if frac is not None else "")))
            bar, w = b["bar"], max(1, b["bar"].winfo_width())
            bar.delete("all")
            if frac is not None:
                bar.create_rectangle(0, 0, int(w * min(1.0, max(0.0, frac))), 8,
                                     fill=GREEN if key in live or state == "done" else BLUE, width=0)
            running = key in live
            b["edge"].configure(bg=GREEN if running else (LINE if state != "done" else GREEN_DIM))
            bg = GREEN_DIM if running else CARD
            b["box"].configure(highlightbackground=GREEN if running else
                               (BLUE if key == self.sel_key else LINE))
            for w2 in b["paint"]:
                w2.configure(bg=bg)
            hide = state == "done" and not running and not self.show_done.get()
            if hide:
                b["box"].pack_forget()
            elif not b["box"].winfo_ismapped():
                b["box"].pack(fill="x", pady=(0, 8))
        self.step_hint.configure(
            text=(f"{finished} of {len(STEPS)} steps finished and hidden" if finished and not self.show_done.get()
                  else f"{finished} of {len(STEPS)} steps finished"), fg=FAINT)
        if live:
            names = ", ".join(f"{t} ({int(time.time() - st) // 60} min)" for t, st in live.values())
            self.run_line.configure(text=f"Data run:  {names}")
            shown = next((k for k in ("grade", "grade-repair", "grade-growth", "grade-growth-repair",
                                      "grade-heldout", "matrix", "phi", "base", "student", "locallm", "repair",
                                      "more-problems", "generate") if k in live), next(iter(live)))
            try:
                last = [l for l in (RUNS / "logs" / f"{shown}.log").read_text(errors="replace")
                        .replace("\r", "\n").splitlines() if l.strip()][-1]
            except (OSError, IndexError):
                last = ""
            self.draw_progress(shown, live[shown][1], last)
        else:
            self.run_line.configure(text="Data run:  nothing running")
            self.run_tail.configure(text="")
            self.run_bar.delete("all")
        self.show_log()                      # the Output box tails the chosen step's log, live
        if not once:
            self.root.after(2000, self.refresh_steps)

    def draw_progress(self, key, started, last):
        """The Live checks strip: the running step's own count when it has one, else checks finished of the
        answer set being graded (the log's '== <tag>: N tasks' line), less the sets already brought back."""
        prog, frac = self.step_prog.get(key, ("", None))
        text = f"{self.title_of(key)}: {prog}    {last[:70]}" if prog else last[:140]
        if frac is None:
            try:
                lines = (RUNS / "logs" / f"{key}.log").read_text(errors="replace").splitlines()
                for line in reversed(lines):
                    m = re.match(r"== (\S+): (\d+) tasks", line)
                    if not m:
                        continue
                    total = int(m.group(2)) * len(KERNELS)
                    run = lines[max(i for i, l in enumerate(lines) if l.startswith("###")):]
                    earlier = sum(int(n) * len(KERNELS)
                                  for tag, n in re.findall(r"== (\S+): (\d+) tasks", "\n".join(run))
                                  if f"== {tag}: kernels.md back" in run)
                    try:
                        mine = {q.stem for q in (SPEC_EXP / m.group(1) / "grade-in").glob("*.json")}
                    except OSError:
                        mine = set()
                    done = sum(1 for t, name in self.end_pairs if t >= started and (not mine or name in mine))
                    done = max(0, done - earlier)
                    frac = min(1.0, done / total) if total else None
                    text = (f"{m.group(1)}: {done} of {total} checks" if done else
                            f"{m.group(1)}: translating {m.group(2)} tasks for the seven checkers")
                    break
            except OSError:
                pass
        self.run_tail.configure(text=text)
        self.run_bar.delete("all")
        if frac is not None:
            self.run_bar.create_rectangle(0, 0, int(260 * frac), 10, fill=GREEN, width=0)

    ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[()][A-B0-9]")

    def show_log(self):
        log = RUNS / "logs" / f"{self.sel_key}.log"
        try:
            text = self.ANSI.sub("", log.read_text(errors="replace"))
            # a download's progress bar redraws one line with carriage returns: keep what it ended up saying
            lines = [l.split("\r")[-1].rstrip() for l in text.splitlines()]
            keep, last = [], None
            for l in lines:
                head = l.split(":")[0][:40]
                if l.strip() and head == last and "%" in l:      # the same bar, drawn again
                    keep[-1] = l
                    continue
                keep.append(l)
                last = head if "%" in l else None
            tail = "\n".join(keep[-200:])
        except OSError:
            tail = "No log yet. Press Run on this step."
        if self.log_text.get("1.0", "end").strip() == tail.strip():
            return
        at_end = self.log_text.yview()[1] > 0.999       # leave the view alone when it has been scrolled up
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", tail)
        if at_end:
            self.log_text.see("end")


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
    try:                                  # where it was left, so Refresh t lab does not move the window
        root.geometry(GEOMETRY.read_text().strip())
    except (OSError, tk.TclError):
        root.geometry(f"{w}x{h}+10+30")
    root.minsize(1000, 700)
    Lab(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
