#!/usr/bin/env python3
"""t/watch_gui.py -- one window per running kernel cell, closed when the
cell is done (2026-09-16).

A cell is one task graded in one kernel: the real and its twin, each up to
flake_n times (run_par._run_cell). With T_WATCH=<file> in its environment,
run_par.py appends a JSON line when a cell starts and when it ends; this
program follows that file and, for every running cell, keeps a small window
titled "<task> x <kernel>" that shows:

  - the elapsed time,
  - the prover processes the cell's worker has running right now (read from
    /proc: command name, state, resident memory),
  - when the cell ends, its verdict (real / twin), green when the cell reads
    verified / refuted and red otherwise; the window closes two seconds
    later.

Windows tile in a grid across the screen; more running cells than slots
stack from the top-left corner.

Usage (the desktop session's display, e.g. DISPLAY=:10.0):

    python3 t/watch_gui.py [--events FILE]
    T_WATCH=FILE python3 t/run_par.py --tasks ... --out ... --table ...

FILE defaults to ~/.cache/t-watch/events.jsonl for both. Standard library
only (tkinter).
"""

from __future__ import annotations

import argparse
import json
import os
import time
import tkinter as tk
from pathlib import Path

DEFAULT_EVENTS = Path.home() / ".cache" / "t-watch" / "events.jsonl"
SLOT_W, SLOT_H = 350, 170
CLOSE_AFTER_S = 2.0
PAGE_KB = os.sysconf("SC_PAGE_SIZE") // 1024


def proc_table() -> dict[int, tuple[int, str, str, int]]:
    """pid -> (ppid, comm, state, rss_kb) for every readable process."""
    out = {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat", encoding="utf-8", errors="replace") as f:
                raw = f.read()
            with open(f"/proc/{d}/statm") as f:
                rss_pages = int(f.read().split()[1])
        except OSError:
            continue
        # comm is parenthesized and may hold spaces; fields resume after ")"
        lp, rp = raw.find("("), raw.rfind(")")
        rest = raw[rp + 2:].split()
        out[int(d)] = (int(rest[1]), raw[lp + 1:rp], rest[0], rss_pages * PAGE_KB)
    return out


def descendants(root: int, table) -> list[int]:
    kids: dict[int, list[int]] = {}
    for pid, row in table.items():
        ppid = row[0]
        kids.setdefault(ppid, []).append(pid)
    found, stack = [], [root]
    while stack:
        for c in kids.get(stack.pop(), []):
            found.append(c)
            stack.append(c)
    return found


class Watch:
    def __init__(self, events: Path):
        self.events = events
        self.offset = 0
        self.root = tk.Tk()
        self.root.withdraw()
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()
        self.cols = max(1, self.sw // SLOT_W)
        self.rows = max(1, (self.sh - 40) // SLOT_H)
        self.cells: dict[tuple[str, str], dict] = {}
        self.slots: dict[int, tuple[str, str]] = {}
        self.poll()
        self.tick()

    # -- windows ---------------------------------------------------------
    def open(self, ev: dict) -> None:
        key = (ev["task"], ev["kernel"])
        if key in self.cells:
            self.close(key)
        slot = next(i for i in range(len(self.slots) + 1) if i not in self.slots)
        self.slots[slot] = key
        n = self.cols * self.rows
        if slot < n:
            x, y = (slot % self.cols) * SLOT_W, 30 + (slot // self.cols) * SLOT_H
        else:
            x = y = 30 + 20 * ((slot - n) % 20)
        w = tk.Toplevel(self.root)
        w.title(f"{ev['task']} x {ev['kernel']}")
        w.geometry(f"{SLOT_W - 10}x{SLOT_H - 40}+{x}+{y}")
        w.configure(bg="#1e1e1e")
        head = tk.Label(w, text=f"{ev['kernel']}  {ev['task']}", fg="#ffffff",
                        bg="#1e1e1e", font=("monospace", 10, "bold"), anchor="w")
        head.pack(fill="x", padx=6, pady=(4, 0))
        clock = tk.Label(w, text="", fg="#9cdcfe", bg="#1e1e1e",
                         font=("monospace", 9), anchor="w")
        clock.pack(fill="x", padx=6)
        body = tk.Label(w, text="starting", fg="#d4d4d4", bg="#1e1e1e",
                        font=("monospace", 9), anchor="nw", justify="left")
        body.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        w.protocol("WM_DELETE_WINDOW", lambda k=key: self.close(k))
        self.cells[key] = {"win": w, "head": head, "clock": clock, "body": body, "pid": ev["pid"],
                           "t0": ev["t"], "slot": slot, "done": None}

    def finish(self, ev: dict) -> None:
        key = (ev["task"], ev["kernel"])
        c = self.cells.get(key)
        if c is None:
            return
        good = ev.get("real") == "verified" and ev.get("twin") == "refuted"
        color = "#1f5f2f" if good else "#6f1f1f"
        c["done"] = time.time()
        for part in ("win", "head", "clock", "body"):
            c[part].configure(bg=color)
        c["clock"].configure(text=f"done in {ev['t'] - c['t0']:.1f}s")
        c["body"].configure(text=f"real: {ev.get('real')}\ntwin: {ev.get('twin')}",
                            fg="#ffffff", font=("monospace", 12, "bold"))
        self.root.after(int(CLOSE_AFTER_S * 1000), lambda k=key, d=c["done"]: self.close(k, d))

    def close(self, key, done_at=None) -> None:
        c = self.cells.get(key)
        if c is None or (done_at is not None and c["done"] != done_at):
            return
        del self.cells[key]
        self.slots.pop(c["slot"], None)
        try:
            c["win"].destroy()
        except tk.TclError:
            pass

    # -- loops -----------------------------------------------------------
    def poll(self) -> None:
        try:
            size = self.events.stat().st_size
            if size < self.offset:          # truncated or replaced: start over
                self.offset = 0
            if size > self.offset:
                with open(self.events, encoding="utf-8") as f:
                    f.seek(self.offset)
                    chunk = f.read()
                keep = chunk.rfind("\n") + 1  # a partial last line waits
                self.offset += len(chunk[:keep].encode("utf-8"))
                for line in chunk[:keep].splitlines():
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("ev") == "start":
                        self.open(ev)
                    elif ev.get("ev") == "end":
                        self.finish(ev)
        except FileNotFoundError:
            pass
        self.root.after(250, self.poll)

    def tick(self) -> None:
        running = [c for c in self.cells.values() if c["done"] is None]
        if running:
            table = proc_table()
            now = time.time()
            for c in running:
                c["clock"].configure(text=f"running {now - c['t0']:.0f}s")
                lines = []
                for pid in descendants(c["pid"], table):
                    comm, state, rss = table[pid][1:]
                    if comm in ("sh", "bash"):
                        continue
                    lines.append(f"{comm[:18]:18} {state} {rss / 1024:8.0f} MB")
                c["body"].configure(text="\n".join(lines[:6]) or "between prover calls")
        self.root.after(1000, self.tick)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--events", default=str(DEFAULT_EVENTS))
    a = ap.parse_args()
    events = Path(a.events)
    events.parent.mkdir(parents=True, exist_ok=True)
    events.touch()
    # skip what is already in the file: watch cells that start from now on
    w = Watch(events)
    w.offset = events.stat().st_size
    w.root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
