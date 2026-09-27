"""window.py: the person's memory in a window -- every record dawnr keeps of them, and their controls over it.

The same controls as `python locallm/dawnr_memory` (DAWNR-MEMORY.md section 5), for a person who never opens a
terminal: the records, newest first; forget the selected ones; correct one in their own words; pin a note; export
everything to a file only they can read; forget everything (asked first: nothing can undo it); and the two
switches, remembering and recalling. Opened from the chat card's "Memory..." button (chat_pane.py).

Every action is a method that takes its input as arguments (forget, correct, pin, export, forget_everything,
set_switch) and the dialogs only gather that input, so a test drives the window without clicking through modal
dialogs, the split chat_pane.py makes between its approver and its dialog. The list is a ttk.Treeview with
extended selection; input comes from tkinter.simpledialog.askstring, tkinter.filedialog.asksaveasfilename and
tkinter.messagebox (docs.python.org/3/library/tkinter.ttk.html, docs.python.org/3/library/dialog.html).
"""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable

from .store import MemoryStore, StoreError, write_owner_only

COLUMNS = (("kind", 90), ("date", 90), ("text", 560))
PAD, GAP = 16, 8                     # look.SPACE.card and look.SPACE.inner, the page's own scale


class MemoryWindow:
    """A window over one person's MemoryStore. `button` is home.py's drawn button class, `font(size, *style)` the
    page's sans font, so the window looks like the page that opened it."""

    def __init__(self, master: tk.Misc, palette: dict, store: MemoryStore, *, button, font: Callable,
                 remembering: bool = True):
        self.C, self.store, self.font = palette, store, font
        C = palette
        self.win = tk.Toplevel(master)
        self.win.title(f"What dawnr remembers of {store.person}")
        self.win.configure(bg=C["paper"])
        self.win.transient(master.winfo_toplevel())
        self.win.columnconfigure(0, weight=1)
        self.win.rowconfigure(0, weight=1)
        body = tk.Frame(self.win, bg=C["paper"], padx=PAD, pady=PAD)
        body.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)
        where = "on" if remembering else "off in the chat's Settings"
        tk.Label(body, text=f"Everything dawnr keeps about {store.person}, on this machine only, in {store.dir}. "
                            f"Remembering new conversations is {where}.",
                 bg=C["paper"], fg=C["muted"], font=font(10), wraplength=720, justify="left",
                 anchor="w").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, GAP))
        self.tree = ttk.Treeview(body, columns=[c for c, _w in COLUMNS], show="headings", selectmode="extended",
                                 height=12)
        for name, width in COLUMNS:
            self.tree.heading(name, text=name)
            self.tree.column(name, width=width, stretch=(name == "text"), anchor="w")
        self.tree.grid(row=1, column=0, sticky="nsew")
        bar = ttk.Scrollbar(body, command=self.tree.yview)
        bar.grid(row=1, column=1, sticky="ns")
        self.tree["yscrollcommand"] = bar.set

        switches = tk.Frame(body, bg=C["paper"])
        switches.grid(row=2, column=0, columnspan=2, sticky="w", pady=(GAP, 0))
        settings = store.settings()
        self.remember = tk.BooleanVar(value=settings["remember"])
        self.recall = tk.BooleanVar(value=settings["recall"])
        for i, (var, key, text) in enumerate(((self.remember, "remember", "Remember what I say about myself"),
                                              (self.recall, "recall", "Recall this at the start of a conversation"))):
            tk.Checkbutton(switches, text=text, variable=var, command=lambda k=key, v=var: self.set_switch(k, v.get()),
                           bg=C["paper"], fg=C["ink"], activebackground=C["paper"], activeforeground=C["ink"],
                           selectcolor=C["card"], highlightthickness=0, font=font(12),
                           anchor="w").grid(row=0, column=i, sticky="w", padx=(0 if i == 0 else GAP * 2, 0))

        buttons = tk.Frame(body, bg=C["paper"])
        buttons.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(GAP, 0))
        actions = (("Forget selected", self._forget_selected), ("Correct…", self._correct_dialog),
                   ("Pin a note…", self._pin_dialog), ("Export…", self._export_dialog),
                   ("Forget everything…", self._forget_everything_dialog))
        for i, (label, command) in enumerate(actions):
            button(buttons, C, label, command).grid(row=0, column=i, padx=(0 if i == 0 else GAP, 0))
        button(buttons, C, "Close", self.win.destroy, primary=True).grid(row=0, column=len(actions),
                                                                         padx=(GAP * 2, 0))
        self.status = tk.Label(body, text="", bg=C["paper"], fg=C["muted"], font=font(10), anchor="w")
        self.status.grid(row=4, column=0, columnspan=2, sticky="w", pady=(GAP, 0))
        self.refresh()

    # ------------------------------------------------------------ actions --
    def refresh(self, said: str = "") -> int:
        self.tree.delete(*self.tree.get_children())
        records = self.store.records()
        for r in records:
            date = str(r.get("date") or r.get("last_seen") or r.get("updated") or "")[:10]
            self.tree.insert("", "end", iid=r["id"], values=(r["kind"], date, r["text"]))
        count = f"{len(records)} record{'s' if len(records) != 1 else ''}"
        self.status.configure(text=f"{said}  {count}." if said else f"{count}.")
        return len(records)

    def selected(self) -> list[str]:
        return list(self.tree.selection())

    def forget(self, ids) -> int:
        gone = sum(1 for i in ids if self.store.forget(i))
        self.refresh(f"Forgot {gone}.")
        return gone

    def correct(self, record_id: str, text: str) -> dict:
        record = self.store.correct(record_id, text)
        self.refresh("Corrected.")
        return record

    def pin(self, text: str) -> dict:
        record = self.store.pin(text)
        self.refresh("Pinned.")
        return record

    def export(self, path: str | Path) -> Path:
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.store.export(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"
        write_owner_only(path, text.encode("utf-8"), "export")
        self.refresh(f"Exported to {path}.")
        return path

    def forget_everything(self) -> int:
        removed = self.store.forget_everything()
        self.refresh(f"Forgot everything ({removed} files).")
        return removed

    def set_switch(self, key: str, value: bool) -> dict:
        settings = self.store.set_settings(**{key: bool(value)})
        self.refresh(f"{'Remembering' if key == 'remember' else 'Recalling'} is {'on' if value else 'off'}.")
        return settings

    # ------------------------------------------------------------ dialogs --
    def _forget_selected(self):
        ids = self.selected()
        if ids:
            self.forget(ids)

    def _correct_dialog(self):
        ids = self.selected()
        if len(ids) != 1:
            self.status.configure(text="Select one record to correct.")
            return
        record = self.store.get(ids[0])
        if record is None:
            self.refresh()
            return
        text = simpledialog.askstring("Correct", "In your own words:", initialvalue=record["text"], parent=self.win)
        if text and text.strip():
            self.correct(ids[0], text)

    def _pin_dialog(self):
        text = simpledialog.askstring("Pin a note", "A note dawnr reads first, every conversation:", parent=self.win)
        if text and text.strip():
            self.pin(text)

    def _export_dialog(self):
        path = filedialog.asksaveasfilename(parent=self.win, title="Export memory", defaultextension=".json",
                                            initialfile=f"{self.store.person}-memory.json",
                                            filetypes=[("JSON", "*.json")])
        if path:
            self.export(path)

    def _forget_everything_dialog(self):
        if messagebox.askyesno("Forget everything",
                               f"Remove every record dawnr keeps about {self.store.person}? Nothing can undo it.",
                               icon="warning", default="no", parent=self.win):
            self.forget_everything()


def open_for_config(master: tk.Misc, palette: dict, config: dict, config_dir: Path | None, *, button,
                    font: Callable) -> MemoryWindow | None:
    """The memory window for the person a harness configuration names (the default person when memory is off, so
    old memory can still be read and erased); None with a message box when the folder cannot be opened."""
    from .harness_hooks import parse_config
    spec = config.get("memory")
    try:
        memory = parse_config(spec if isinstance(spec, dict) else {}, config_dir)
        store = MemoryStore(memory.root, memory.person)
    except (ValueError, StoreError, OSError) as e:
        messagebox.showerror("Memory", f"The memory folder cannot be opened: {e}", parent=master)
        return None
    return MemoryWindow(master, palette, store, button=button, font=font, remembering=spec not in (None, False))
