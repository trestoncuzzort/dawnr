"""chat_pane.py — the chat pane on home.py's front page.

A conversation with dawnr's chat engine (engine.py) and harness
(dawnr_harness/, DAWNR-HARNESS.md), streamed through home.py's own queue pump
instead of a second one: every background piece this file produces is put on
the `q` home.py already drains on a Tk `.after` loop, exactly as
home.write_pieces does for step 4's plain-text reply
(docs.python.org/3/library/tkinter.html, "Threading model" — no widget is
touched off that loop).

Layered so most of this file needs neither torch nor a display:

* `TokenEvents` turns a stream of token ids into UI events (plain text, a
  tool call opening/closing, an output span opening/closing, marked
  untrusted or not) by comparing ids against chat.py's special tokens. It is
  pure and torch-free, the same way chat.py itself is: it only calls
  `tokenizer.sentinel_id`/`.decode`, so a hand-built stand-in tokenizer
  drives it in a test with no torch installed.
* `run_chat` relays whatever a producer yields onto the queue until it is
  exhausted or `stop` is set — home.write_pieces's own shape, generalised
  from characters to (kind, data) events, so it is tested the same way:
  a plain iterable in, a queue and an Event touched, nothing else.
* `chat_reply_events` is the one producer that needs torch (via the modules
  `chat_engine()` hands back): it drives engine.Engine.generate and feeds
  each produced token to a TokenEvents. Not unit tested directly for that
  reason, matching test_harness_chat.py's own torch-gated classes.
* `ChatPane` is the Tk half: the message list, the input box, Stop, the
  approve/deny dialog and the network settings panel. It is composed into
  home.py's page (a `_Card.body` is handed to it), not a second window.

The approve/deny wiring is the one place a background thread and the Tk
thread must meet without either breaking the threading model.
`dawnr_harness`'s approver contract (runtime.py) is a plain, synchronous
`approver(name, arguments, why) -> bool`, called inline on whatever thread is
driving `Harness.call` — here, the same background thread `run_chat` is
draining. `make_approver` therefore puts a "chat-ask" message on the queue
and blocks on a `threading.Event` until the Tk thread (the dialog's Approve
or Deny button, or Stop) answers it by writing to a shared dict and setting
that Event — the same one-slot handoff `home.py`'s own `write_stop` Event
uses for Stop, just carrying an answer instead of only a flag.
"""
from __future__ import annotations

import json
import queue
import threading
import traceback
from pathlib import Path
from typing import Callable, Iterable, NamedTuple

import tkinter as tk
from tkinter import ttk

import chat
import dawnr_persona
import look
from look import MONO, SANS

DEFAULT_CONFIG: dict = {"offline": True}

#: home.py's own font sizes (TYPE.body, TYPE.caption) are not re-exported by
#: look.py, and importing home.py from here at module scope would be
#: circular (home.py imports this module from inside a Home method, lazily,
#: precisely so that by the time it does, home.py's own module is already
#: fully loaded — see `_home()` below). These two numbers are the same
#: choices, kept as plain literals rather than reached for through that
#: lazy import, since a font size a dialog uses once is not worth the
#: coupling.
BODY_SIZE = 12
CAPTION_SIZE = 10


# --------------------------------------------------------------------------
# LAZY IMPORTS. Same shape as home.py's own engine()/reader()/talker(): a
# module that is missing, or needs torch, becomes a sentence on the card
# instead of a traceback before the window exists.
# --------------------------------------------------------------------------
_ENGINE: list[tuple["EngineBundle | None", str]] = []
_HOME: list[object] = []


class EngineBundle(NamedTuple):
    """The modules chat_reply_events needs, all of which need torch."""
    engine: object
    checkpoint: object
    build_harness: Callable


def chat_engine() -> tuple[EngineBundle | None, str]:
    """(EngineBundle, "") once, or (None, why not). Imported at most once per process."""
    if not _ENGINE:
        try:
            import torch                                          # noqa: F401,PLC0415
        except Exception:                                          # noqa: BLE001
            _ENGINE.append((None, "PyTorch is not installed."))
            return _ENGINE[0]
        try:
            import engine as engine_mod                            # noqa: PLC0415
            import checkpoint as checkpoint_mod                    # noqa: PLC0415
            from dawnr_harness import build_harness                # noqa: PLC0415
        except Exception as e:                                     # noqa: BLE001
            _ENGINE.append((None, f"{type(e).__name__}: {e}"))
        else:
            _ENGINE.append((EngineBundle(engine_mod, checkpoint_mod, build_harness), ""))
    return _ENGINE[0]


def _home():
    """home.py's module, imported lazily so this file never imports it at load time.

    This module is only ever used from inside a Home instance (Home builds a
    ChatPane and hands it a `_Card.body` to draw into), so by the time any
    ChatPane method runs, home.py's own module has already finished loading
    and every name in it — `_Button` included — exists. Importing it at
    chat_pane.py's own top level would not: home.py imports this module from
    inside `_build_chat_card`, itself called from `Home.__init__`, which is
    to say partway through home.py's own definition.
    """
    if not _HOME:
        import home as home_mod                                    # noqa: PLC0415
        _HOME.append(home_mod)
    return _HOME[0]


# --------------------------------------------------------------------------
# PURE: token ids -> UI events. No torch, no Tk.
# --------------------------------------------------------------------------
class TokenEvents:
    """One assistant reply's token ids, incrementally, as UI events.

    `feed(token)` returns zero or more `(kind, data)` events for that one
    token, `kind` one of "text", "call_start" (data: "t" or "tool"),
    "call_text", "call_end", "output_start" (data: {"untrusted": bool}),
    "output_text", "output_end". It mirrors engine.RowState's own state
    machine (t/tool call open, output span open, `<|untrusted|>` read as one
    token of lookahead right after `<|output_start|>`, per chat.py's render
    order) closely enough to stay correct against it, but emits incremental
    events instead of engine.reply_parts's finished list, which is what a
    live reply needs and what reply_parts is not shaped to give until the
    reply ends.
    """

    def __init__(self, tokenizer, decode: Callable[[list[int]], str] | None = None):
        self._decode = decode or tokenizer.decode
        self._harness = chat.has_harness_tokens(tokenizer)
        sp = lambda name: chat.special(tokenizer, name)             # noqa: E731
        self._t_start, self._t_end = sp(chat.T_START), sp(chat.T_END)
        self._output_start, self._output_end = sp(chat.OUTPUT_START), sp(chat.OUTPUT_END)
        self._tool_start = sp(chat.TOOL_START) if self._harness else None
        self._tool_end = sp(chat.TOOL_END) if self._harness else None
        self._untrusted = sp(chat.UNTRUSTED) if self._harness else None
        self._state = "text"           # "text" | "call" | "output-open" | "output"
        self._call_kind: str | None = None

    def feed(self, token: int) -> list[tuple[str, object]]:
        if self._state == "output-open":
            self._state = "output"
            if token == self._untrusted:
                return [("output_start", {"untrusted": True})]
            events = [("output_start", {"untrusted": False})]
            if token == self._output_end:
                self._state = "text"
                return events + [("output_end", None)]
            return events + self._text(token, "output_text")
        if token == self._t_start or (self._tool_start is not None and token == self._tool_start):
            self._call_kind = "t" if token == self._t_start else "tool"
            self._state = "call"
            return [("call_start", self._call_kind)]
        if self._state == "call" and (
                (self._call_kind == "t" and token == self._t_end)
                or (self._call_kind == "tool" and token == self._tool_end)):
            self._state = "text"
            return [("call_end", None)]
        if token == self._output_start:
            self._state = "output-open"
            return []
        if token == self._output_end:
            self._state = "text"
            return [("output_end", None)]
        kind = {"text": "text", "call": "call_text", "output": "output_text"}[self._state]
        return self._text(token, kind)

    def _text(self, token: int, kind: str) -> list[tuple[str, object]]:
        s = self._decode([token])
        return [(kind, s)] if s else []


def trust_label(untrusted: bool) -> str:
    return "untrusted: from outside" if untrusted else "from a tool"


def call_label(kind: str) -> str:
    return "t program" if kind == "t" else "Tool call"


# --------------------------------------------------------------------------
# GENERIC RELAY: home.write_pieces's own shape, for (kind, data) events
# instead of characters.
# --------------------------------------------------------------------------
def run_chat(make_events: Callable[[], Iterable[tuple[str, object]]],
             q: queue.Queue, stop: threading.Event) -> None:
    """Put every event `make_events()` yields onto q, until done or `stop` is set.

    Touches only q and stop, on purpose: this runs on a background thread,
    and "any tkinter calls made from threads other than the one running the
    Tcl interpreter will fail" (docs.python.org/3/library/tkinter.html,
    "Threading model") is exactly the failure home.write_pieces is written
    to avoid the same way. `make_events()` is called here, off the Tk
    thread, because building it (loading a model, opening a harness) must
    not block the Tk thread while a previous reply might still be closing
    down.
    """
    events = None
    try:
        events = make_events()
        for item in events:
            if stop.is_set():
                break
            q.put(("chat-event", item))
    except Exception:                                               # noqa: BLE001
        q.put(("chat-failed", traceback.format_exc()))
        return
    finally:
        close = getattr(events, "close", None)
        if close is not None:
            close()
    q.put(("chat-done", {"stopped": stop.is_set()}))


def chat_reply_events(bundle: EngineBundle, model, tokenizer, harness,
                      prompt_tokens: list[int], *, max_tokens: int | None = None,
                      temperature: float = 0.7, top_k: int | None = 40, seed: int = 42):
    """Drive engine.Engine.generate for one row, yielding TokenEvents pieces.

    Needs torch (through `bundle`, from chat_engine()) — not unit tested
    directly for that reason, the same as engine.py's own tests skip
    without it (test_harness_chat.py). Ends with a "final_parts" event
    carrying engine.reply_parts' own structured parts for the finished
    reply, so the caller can store the message dawnr's chat format expects
    without re-deriving it from these incremental events; run_chat relays
    it exactly like any other event, and only ChatPane's handler treats it
    differently.

    A tool call already running (a slow web fetch, say) cannot be
    interrupted mid-call — nothing in Harness.call is cooperative about
    that, the same limitation home.py's own file reads document for a read
    already in flight. Stop takes effect at the next token boundary, or
    immediately if a call is waiting on an approval (ChatPane's Stop
    answers a pending ask as denied before it sets the stop Event).
    """
    eng = bundle.engine.Engine(model, tokenizer, harness=harness)
    end_id = chat.special(tokenizer, chat.ASSISTANT_END)
    events = TokenEvents(tokenizer)
    produced: list[int] = []
    for column, _masks in eng.generate(prompt_tokens, max_tokens=max_tokens,
                                       temperature=temperature, top_k=top_k, seed=seed):
        token = column[0]
        if token == end_id:
            break
        produced.append(token)
        yield from events.feed(token)
    yield ("final_parts", bundle.engine.reply_parts(tokenizer, produced))


def make_approver(q: queue.Queue, answered: threading.Event,
                  answer: dict) -> Callable[[str, dict, str], bool]:
    """A Harness approver that hands the ask to the Tk thread and blocks for its answer.

    Runs on the background thread, inline inside Harness.call
    (dawnr_harness/runtime.py: `approved = bool(self.approver(name, arguments, why))`),
    so it must not touch a widget itself. It puts a "chat-ask" message on
    the same queue run_chat is using and waits on `answered`, which
    ChatPane's dialog (Approve/Deny, the window's own close button, or Stop)
    sets after writing `answer["approved"]`. Only one ask is ever pending at
    a time — Harness.call is synchronous, so the next call cannot start
    until this one returns — which is why one shared Event and dict, reset
    here on every call, are enough.
    """
    def approver(name: str, arguments: dict, why: str) -> bool:
        answered.clear()
        answer.clear()
        q.put(("chat-ask", {"name": name, "arguments": arguments, "why": why}))
        answered.wait()
        return bool(answer.get("approved", False))
    return approver


# --------------------------------------------------------------------------
# THE HARNESS CONFIG FILE: read-modify-write, preserving keys this file does
# not understand. No writer exists in dawnr_harness itself (it only reads
# configuration, build_harness); this is deliberately small rather than
# growing one there, since the only thing a settings panel needs to change
# today is the one master switch.
# --------------------------------------------------------------------------
def load_harness_config(path: Path) -> dict:
    """The config at `path`, or the safe default (offline) if it is absent or unreadable."""
    if not path.is_file():
        return dict(DEFAULT_CONFIG)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULT_CONFIG)
    return data if isinstance(data, dict) else dict(DEFAULT_CONFIG)


def save_harness_config(path: Path, config: dict) -> None:
    """Write `config` back to `path`, atomically (a partial write must never be read)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


# --------------------------------------------------------------------------
# SAY-STYLE STATUS MESSAGES. Same shape as home.py's say_model etc.: a plain
# sentence, never a bare state name.
# --------------------------------------------------------------------------
def say_needs_torch() -> look.Say:
    return look.Say(
        look.NOT_APPLICABLE, "Needs PyTorch",
        "Chat calls the harness's tools mid-reply, which needs the real "
        "model, so it needs PyTorch installed — the plain “Try it” card "
        "above works without it, but this does not. Install PyTorch, then "
        "reopen this page.", "unsettled")


def say_needs_modules(why: str) -> look.Say:
    return look.Say(
        look.NOT_APPLICABLE, "Cannot open it",
        f"PyTorch is installed, but the chat engine did not load: {why}. "
        f"This is a repository problem, not a missing install.", "unsettled")


def say_needs_checkpoint() -> look.Say:
    return look.Say(
        look.NOT_APPLICABLE, "Needs a chat checkpoint",
        "No trained model was found. Train one in step 3, then mid-train it "
        "on chat conversations (dawnr_pipeline.py, DAWNR-PIPELINE.md) so it "
        "knows the chat format.", "unsettled")


def say_not_chat_checkpoint(where: Path) -> look.Say:
    return look.Say(
        look.NOT_APPLICABLE, "Not a chat checkpoint",
        f"“{where.name}” is a trained model, but its tokenizer has never "
        f"seen the chat tokens (chat.with_chat_tokens), so it cannot hold a "
        f"conversation — step 4 above can still complete plain text with "
        f"it. Mid-train it on chat conversations first "
        f"(dawnr_pipeline.py, DAWNR-PIPELINE.md).", "unsettled")


def say_ready(where: Path) -> look.Say:
    return look.Say(look.PROVED, "Ready",
                    f"Loaded from “{where.name}”. Type a message below.", "proved")


def say_replying() -> look.Say:
    return look.Say(look.TIMED_OUT, "Replying", "The model is writing a reply.", "unsettled")


def say_done(stopped: bool) -> look.Say:
    if stopped:
        return look.Say(look.PROVED, "Stopped", "Stopped, as asked.", "proved")
    return look.Say(look.PROVED, "Ready", "Type another message.", "proved")


def say_failed(last_line: str) -> look.Say:
    return look.Say(look.REFUTED, "Stopped",
                    f"The reply stopped with an error. What Python said last: "
                    f"{last_line}.", "refuted")


# --------------------------------------------------------------------------
# THE WIDGET.
# --------------------------------------------------------------------------
class ChatPane:
    """The chat card's contents: message list, input, Stop, settings.

    Composed into a `_Card.body` home.py builds, the same way home.py
    composes `_DropTarget`/`_Slider` into its own cards — this is not a
    second window and starts no second `.after` loop; `Home._drain` calls
    `handle()` for every "chat-*" message on the one queue both share.
    """

    def __init__(self, parent: tk.Widget, palette: dict, q: queue.Queue,
                checkpoint_dir: Path | None, on_status: Callable[[look.Say], None],
                config_path: Path | None = None, people_root: Path | None = None):
        self.C = palette
        self.q = q
        self.checkpoint_dir = checkpoint_dir
        self.config_path = config_path or (
            checkpoint_dir / "harness.json" if checkpoint_dir else None)
        self.on_status = on_status
        # per-person learning (DAWNR-LEARNING.md): off unless a people folder is given and the person turned it on
        from dawnr_learning.pane import PaneLearning                  # noqa: PLC0415
        self.learning = PaneLearning(people_root) if people_root is not None else None
        self.model = None
        self.tokenizer = None
        # One persona, this desktop's own operator (DAWNR-HARNESS.md's index
        # is per-session, not per-person; a future login/profile picker would
        # set person_id from whoever is at the keyboard, not from the OS
        # account, and nothing here would otherwise change).
        self.persona_store = dawnr_persona.JSONFilePersonaStore()
        self.person_id = dawnr_persona.DEFAULT_PERSON
        self.bundle: EngineBundle | None = None
        self._ready = False
        self.messages: list[dict] = []
        self.stop_evt = threading.Event()
        self._ask_evt = threading.Event()
        self._ask_answer: dict = {}
        self._ask_win: tk.Toplevel | None = None
        self._seq = 0
        self._collapsed: dict[str, bool] = {}
        self._block_hdr: dict[str, str] = {}
        self._open_call_body: str | None = None
        self._open_output_body: str | None = None
        self._build(parent)
        self.refresh()

    # ------------------------------------------------------------- layout
    def _build(self, parent: tk.Widget):
        _Button = _home()._Button
        C = self.C
        # row 0 is _card_head's own title row and row 1 its Say line, on
        # every card home.py builds this way — this page's own convention,
        # not a choice made here.
        frame = tk.Frame(parent, bg=C["card"])
        frame.grid(row=2, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.transcript = tk.Text(frame, height=14, bg=C["log_bg"], fg=C["log_fg"],
                                  insertbackground=C["log_fg"], font=MONO(BODY_SIZE),
                                  wrap="word", relief="flat", highlightthickness=0)
        self.transcript.grid(row=0, column=0, sticky="nsew")
        bar = ttk.Scrollbar(frame, command=self.transcript.yview)
        bar.grid(row=0, column=1, sticky="ns")
        self.transcript["yscrollcommand"] = bar.set
        self.transcript.tag_configure("role-user", font=SANS(BODY_SIZE, "bold"))
        self.transcript.tag_configure("role-assistant", foreground=C["ink"])
        self.transcript.tag_configure("error", foreground=C["refuted"])

        row = tk.Frame(parent, bg=C["card"])
        row.grid(row=3, column=0, sticky="ew", pady=(look.SPACE.item, 0))
        row.columnconfigure(0, weight=1)
        entry_edge = tk.Frame(row, bg=C["line"])
        entry_edge.grid(row=0, column=0, sticky="ew")
        entry_edge.columnconfigure(0, weight=1)
        self.entry = tk.Entry(entry_edge, bg=C["paper"], fg=C["ink"],
                              insertbackground=C["ink"], relief="flat",
                              highlightthickness=0, font=SANS(BODY_SIZE))
        self.entry.grid(row=0, column=0, sticky="ew", padx=1, pady=1)
        self.entry.bind("<Return>", lambda _e: self.send())
        self.b_send = _Button(row, C, "Send", self.send, primary=True)
        self.b_send.grid(row=0, column=1, padx=(look.SPACE.inner, 0))
        self.b_stop = _Button(row, C, "Stop", self.stop)
        self.b_stop.grid(row=0, column=2, padx=(look.SPACE.item, 0))
        self.b_stop.set_enabled(False)
        _Button(row, C, "Settings…", self.open_settings).grid(
            row=0, column=3, padx=(look.SPACE.item, 0))
        _Button(row, C, "Persona…", self.open_persona).grid(
            row=0, column=4, padx=(look.SPACE.item, 0))
        if self.learning is not None:                                 # the person's feedback on the last answer
            for col, (label, act) in enumerate((("Good", lambda: self._learn_note(self.learning.thumbs(True))),
                                                ("Not this", lambda: self._learn_note(self.learning.thumbs(False))),
                                                ("Correct…", self.open_correct)), start=5):
                _Button(row, C, label, act).grid(row=0, column=col, padx=(look.SPACE.item, 0))

    # ------------------------------------------------------------ status
    def refresh(self) -> look.Say:
        """Re-check torch, the engine modules and the checkpoint; report a Say."""
        bundle, why = chat_engine()
        if bundle is None:
            say = say_needs_torch() if why == "PyTorch is not installed." else say_needs_modules(why)
        elif self.checkpoint_dir is None:
            say = say_needs_checkpoint()
        else:
            tok_path = (self.checkpoint_dir.parent / "tokenizer.json" if self.checkpoint_dir.is_file()
                       else self.checkpoint_dir / "tokenizer.json")
            try:
                # Through bundle.checkpoint, not a fresh `import data`: checkpoint.py
                # already did `from data import load_tokenizer`, and reaching it that
                # way (rather than importing data again here) is what lets a test
                # substitute a fake bundle and exercise this branch with no torch.
                tok = bundle.checkpoint.load_tokenizer(tok_path)
            except FileNotFoundError:
                say = say_needs_checkpoint()
            except Exception as e:                                  # noqa: BLE001
                say = say_needs_modules(f"{type(e).__name__}: {e}")
            else:
                say = (say_ready(self.checkpoint_dir) if chat.has_chat_tokens(tok)
                      else say_not_chat_checkpoint(self.checkpoint_dir))
        self.bundle = bundle
        self._ready = bool(bundle is not None and self.checkpoint_dir is not None
                           and say.mark == look.PROVED)
        self.b_send.set_enabled(self._ready)
        self.on_status(say)
        return say

    def busy(self, say: look.Say):
        self.b_send.set_enabled(False)
        self.b_stop.set_enabled(True)
        self.on_status(say)

    # -------------------------------------------------------------- send
    def send(self):
        text = self.entry.get().strip()
        if not text or not self._ready:
            return
        if self.bundle is None or self.checkpoint_dir is None:
            return
        if self.model is None:
            try:
                self.model, self.tokenizer, _cfg = self.bundle.checkpoint.load_checkpoint(
                    self.checkpoint_dir)
            except Exception as e:                                  # noqa: BLE001
                self.on_status(say_needs_modules(f"{type(e).__name__}: {e}"))
                return
        if self.learning is not None:
            self._learn_note(self.learning.sync(self.model, self.checkpoint_dir))
            self._learn_note(self.learning.user_turn(text))
        self.entry.delete(0, "end")
        persona = self.persona_store.get(self.person_id)
        if dawnr_persona.observe(persona, text):
            self.persona_store.save(persona)
        # The preamble is folded onto the model's copy of the first turn
        # only (DAWNR-HARNESS.md's index does the same), never onto what is
        # shown in the transcript: `text` is what the person typed and reads
        # back, `model_text` is what the model sees.
        model_text = dawnr_persona.with_persona_preamble(text, persona) if not self.messages else text
        self.messages.append({"role": "user", "content": model_text})
        self._insert(f"You: {text}\n", ("role-user",))
        self._insert("dawnr: ", ("role-assistant",))
        try:
            prompt_tokens = chat.render_for_completion(self.tokenizer, {"messages": self.messages})
        except ValueError as e:
            self.messages.pop()
            self._insert(f"[{e}]\n", ("error",))
            return
        config = load_harness_config(self.config_path) if self.config_path else dict(DEFAULT_CONFIG)
        approver = make_approver(self.q, self._ask_evt, self._ask_answer)
        harness = self.bundle.build_harness(config, approver=approver)
        self.stop_evt.clear()
        self.busy(say_replying())
        bundle, model, tokenizer = self.bundle, self.model, self.tokenizer
        threading.Thread(
            target=run_chat,
            args=(lambda: chat_reply_events(bundle, model, tokenizer, harness, prompt_tokens),
                 self.q, self.stop_evt),
            daemon=True).start()

    def stop(self):
        """Ask the reply to stop; answer any pending approval as denied so it can."""
        if self._ask_win is not None:
            self._answer_ask(False)
        self.stop_evt.set()
        self.b_stop.set_enabled(False)
        self.on_status(look.Say(look.TIMED_OUT, "Stopping", "Stopping after this piece.", "unsettled"))

    # ------------------------------------------------------------- pump
    def handle(self, kind: str, payload):
        """Called from Home._drain for every "chat-*" queue message."""
        if kind == "chat-event":
            self._on_event(payload)
        elif kind == "chat-done":
            self._on_done(payload)
        elif kind == "chat-failed":
            self._on_failed(payload)
        elif kind == "chat-ask":
            self._on_ask(payload)

    def _on_event(self, item: tuple[str, object]):
        ev, data = item
        if ev == "text":
            self._insert(data, ("role-assistant",))
        elif ev == "call_start":
            self._open_call_body = self._add_block(call_label(str(data)), "muted")
        elif ev == "call_text":
            self._insert(data, (self._open_call_body,))
        elif ev == "call_end":
            self._insert("\n", (self._open_call_body,))
            self._open_call_body = None
        elif ev == "output_start":
            untrusted = bool(data.get("untrusted"))
            self._open_output_body = self._add_block(
                trust_label(untrusted), "unsettled" if untrusted else "muted")
        elif ev == "output_text":
            self._insert(data, (self._open_output_body,))
        elif ev == "output_end":
            self._insert("\n", (self._open_output_body,))
            self._open_output_body = None
        elif ev == "final_parts":
            self.messages.append({"role": "assistant", "content": data})
            if self.learning is not None:
                styled = self.learning.in_style(self.messages)        # the person's profile, if it changes it
                if styled:
                    body = self._add_block("in your style (your profile)", "muted")
                    self._insert(styled, (body,))
                    self._toggle(body, body.replace("body", "mark"))  # shown open: it is the answer now
                self.learning.replied(self.messages)

    def _on_done(self, payload: dict):
        self._insert("\n", ())
        self.b_send.set_enabled(True)
        self.b_stop.set_enabled(False)
        self.on_status(say_done(bool(payload.get("stopped"))))

    def _on_failed(self, payload: str):
        last = payload.strip().splitlines()[-1] if payload.strip() else ""
        self._insert(f"\n[stopped with an error: {last}]\n", ("error",))
        self.b_send.set_enabled(True)
        self.b_stop.set_enabled(False)
        self.on_status(say_failed(last))

    def _on_ask(self, payload: dict):
        self._show_ask_dialog(payload["name"], payload["arguments"], payload["why"])

    # ------------------------------------------------------- ask dialog
    def _show_ask_dialog(self, name: str, arguments: dict, why: str):
        _Button = _home()._Button
        C = self.C
        win = tk.Toplevel(self.transcript)
        win.title("Approve this tool call?")
        win.configure(bg=C["paper"])
        win.transient(self.transcript.winfo_toplevel())
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", lambda: self._answer_ask(False))
        body = tk.Frame(win, bg=C["paper"], padx=look.SPACE.card, pady=look.SPACE.card)
        body.grid(row=0, column=0)
        shown = json.dumps(arguments, ensure_ascii=False)
        tk.Label(body, text=f"{name} {shown}", bg=C["paper"], fg=C["ink"],
                font=MONO(BODY_SIZE), wraplength=440, justify="left",
                anchor="w").grid(row=0, column=0, sticky="w")
        tk.Label(body, text=why, bg=C["paper"], fg=C["muted"], font=SANS(CAPTION_SIZE),
                wraplength=440, justify="left", anchor="w").grid(
            row=1, column=0, sticky="w", pady=(look.SPACE.item, 0))
        btns = tk.Frame(body, bg=C["paper"])
        btns.grid(row=2, column=0, sticky="e", pady=(look.SPACE.item, 0))
        _Button(btns, C, "Approve", lambda: self._answer_ask(True), primary=True).grid(
            row=0, column=0)
        _Button(btns, C, "Deny", lambda: self._answer_ask(False)).grid(
            row=0, column=1, padx=(look.SPACE.inner, 0))
        win.grab_set()
        self._ask_win = win

    def _answer_ask(self, approved: bool):
        self._ask_answer["approved"] = approved
        if self._ask_win is not None:
            try:
                self._ask_win.destroy()
            except tk.TclError:
                pass
            self._ask_win = None
        self._ask_evt.set()

    # ------------------------------------------------------------ settings
    def open_settings(self):
        _Button = _home()._Button
        C = self.C
        config = load_harness_config(self.config_path) if self.config_path else dict(DEFAULT_CONFIG)
        win = tk.Toplevel(self.transcript)
        win.title("Chat: network tools")
        win.configure(bg=C["paper"])
        win.transient(self.transcript.winfo_toplevel())
        win.resizable(False, False)
        body = tk.Frame(win, bg=C["paper"], padx=look.SPACE.card, pady=look.SPACE.card)
        body.grid(row=0, column=0)
        allow_network = tk.BooleanVar(value=not bool(config.get("offline", True)))
        tk.Checkbutton(body, text="Allow tools to use the network (fetching pages, "
                                  "searching, MCP servers)",
                      variable=allow_network, bg=C["paper"], fg=C["ink"],
                      activebackground=C["paper"], activeforeground=C["ink"],
                      selectcolor=C["card"], highlightthickness=0,
                      font=SANS(BODY_SIZE), anchor="w").grid(row=0, column=0, sticky="w")
        where = str(self.config_path) if self.config_path else "(no checkpoint chosen yet)"
        tk.Label(body, text=f"Individual tools still ask before running. Saved to {where}.",
                bg=C["paper"], fg=C["muted"], font=SANS(CAPTION_SIZE), wraplength=420,
                justify="left", anchor="w").grid(row=1, column=0, sticky="w",
                                                 pady=(look.SPACE.item, 0))
        btns = tk.Frame(body, bg=C["paper"])
        btns.grid(row=4, column=0, sticky="e", pady=(look.SPACE.item, 0))
        learn = self.learning.settings() if self.learning is not None else None
        learn_on = tk.BooleanVar(value=bool(learn and learn["enabled"]))
        learn_name = tk.StringVar(value=learn["person"] if learn else "")
        if learn is not None:
            tk.Checkbutton(body, text="Learn from my feedback (kept on this machine; yours to read and erase)",
                           variable=learn_on, bg=C["paper"], fg=C["ink"], activebackground=C["paper"],
                           activeforeground=C["ink"], selectcolor=C["card"], highlightthickness=0,
                           font=SANS(BODY_SIZE), anchor="w").grid(row=2, column=0, sticky="w",
                                                                  pady=(look.SPACE.item, 0))
            who = tk.Frame(body, bg=C["paper"])
            who.grid(row=3, column=0, sticky="w")
            tk.Label(who, text="Your name for it:", bg=C["paper"], fg=C["muted"],
                     font=SANS(CAPTION_SIZE)).grid(row=0, column=0)
            tk.Entry(who, textvariable=learn_name, width=16, font=SANS(BODY_SIZE)).grid(row=0, column=1)

        def do_save():
            if self.config_path is not None:
                config["offline"] = not allow_network.get()
                save_harness_config(self.config_path, config)
            if learn is not None:
                try:
                    self._learn_note(self.learning.save_settings(learn_on.get(), learn_name.get()))
                except ValueError as e:
                    self._learn_note(str(e))
            win.destroy()

        _Button(btns, C, "Save", do_save, primary=True).grid(row=0, column=0)
        _Button(btns, C, "Cancel", win.destroy).grid(row=0, column=1,
                                                     padx=(look.SPACE.inner, 0))
        win.grab_set()

    # ------------------------------------------------------------- persona
    def open_persona(self):
        """dawnr_persona.py's CLI is the full editor (interests, preferences,
        history, undo, export); this is its GUI hook, kept to what fits in
        the same small dialog shape as `open_settings`: tone, detail,
        explanation depth, and forgetting everything."""
        _Button = _home()._Button
        C = self.C
        record = self.persona_store.get(self.person_id)
        win = tk.Toplevel(self.transcript)
        win.title("Chat: persona")
        win.configure(bg=C["paper"])
        win.transient(self.transcript.winfo_toplevel())
        win.resizable(False, False)
        body = tk.Frame(win, bg=C["paper"], padx=look.SPACE.card, pady=look.SPACE.card)
        body.grid(row=0, column=0)

        tone = tk.StringVar(value=record.tone)
        detail = tk.StringVar(value=record.detail_level)
        depth = tk.StringVar(value=record.explanation_depth)

        tk.Label(body, text="Tone", bg=C["paper"], fg=C["ink"], font=SANS(BODY_SIZE),
                anchor="w").grid(row=0, column=0, sticky="w")
        tk.Entry(body, textvariable=tone, bg=C["paper"], fg=C["ink"], insertbackground=C["ink"],
                relief="flat", highlightthickness=0, font=SANS(BODY_SIZE)).grid(
            row=0, column=1, sticky="ew", padx=(look.SPACE.item, 0))

        def radio_row(r: int, label: str, var: tk.StringVar, options: tuple[str, ...]):
            tk.Label(body, text=label, bg=C["paper"], fg=C["ink"], font=SANS(BODY_SIZE),
                    anchor="w").grid(row=r, column=0, sticky="nw", pady=(look.SPACE.item, 0))
            opts = tk.Frame(body, bg=C["paper"])
            opts.grid(row=r, column=1, sticky="w", padx=(look.SPACE.item, 0), pady=(look.SPACE.item, 0))
            for i, opt in enumerate(options):
                tk.Radiobutton(opts, text=opt, value=opt, variable=var, bg=C["paper"], fg=C["ink"],
                              activebackground=C["paper"], activeforeground=C["ink"],
                              selectcolor=C["card"], highlightthickness=0,
                              font=SANS(BODY_SIZE)).grid(row=0, column=i, sticky="w")

        radio_row(1, "Detail", detail, dawnr_persona.DETAIL_LEVELS)
        radio_row(2, "Explanations", depth, dawnr_persona.DEPTH_LEVELS)

        summary = (f"Interested in: {', '.join(record.interests)}." if record.interests
                  else "No interests learned yet.")
        if record.preferences:
            summary += " " + "; ".join(f"{k}: {v}" for k, v in sorted(record.preferences.items())) + "."
        summary += f" {len(record.history)} change(s) logged so far."
        tk.Label(body, text=summary, bg=C["paper"], fg=C["muted"], font=SANS(CAPTION_SIZE),
                wraplength=380, justify="left", anchor="w").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(look.SPACE.item, 0))
        tk.Label(body, text="Interests, preferences, history and undo: "
                            "locallm/dawnr_persona.py on the command line.",
                bg=C["paper"], fg=C["muted"], font=SANS(CAPTION_SIZE), wraplength=380,
                justify="left", anchor="w").grid(row=4, column=0, columnspan=2, sticky="w")
        err = tk.Label(body, text="", bg=C["paper"], fg=C["refuted"], font=SANS(CAPTION_SIZE),
                      wraplength=380, justify="left", anchor="w")
        err.grid(row=5, column=0, columnspan=2, sticky="w")

        btns = tk.Frame(body, bg=C["paper"])
        btns.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(look.SPACE.item, 0))

        def do_save():
            reason = "the person set this in the chat pane's persona dialog"
            try:
                dawnr_persona.correct(record, "tone", tone.get(), reason)
                dawnr_persona.correct(record, "detail_level", detail.get(), reason)
                dawnr_persona.correct(record, "explanation_depth", depth.get(), reason)
            except dawnr_persona.PersonaError as e:
                err.configure(text=str(e))    # refused, not crashed; the dialog stays open to fix it
                return
            self.persona_store.save(record)
            win.destroy()

        def do_forget():
            self.persona_store.delete(self.person_id)
            win.destroy()

        _Button(btns, C, "Save", do_save, primary=True).grid(row=0, column=0)
        _Button(btns, C, "Cancel", win.destroy).grid(row=0, column=1, padx=(look.SPACE.inner, 0))
        _Button(btns, C, "Forget everything", do_forget).grid(row=0, column=2, padx=(look.SPACE.inner, 0))
        win.grab_set()

    # --------------------------------------------------------- learning
    def open_correct(self):
        """The person's own version of the last answer: it replaces the answer as a training example."""
        _Button = _home()._Button
        C = self.C
        start = self.learning.last_answer_text() if self.learning is not None else ""
        if not start:
            self._learn_note(self.learning.off_sentence() if self.learning is not None else "")
            return
        win = tk.Toplevel(self.transcript)
        win.title("Correct the last answer")
        win.configure(bg=C["paper"])
        win.transient(self.transcript.winfo_toplevel())
        body = tk.Frame(win, bg=C["paper"], padx=look.SPACE.card, pady=look.SPACE.card)
        body.grid(row=0, column=0)
        text = tk.Text(body, width=72, height=18, font=MONO(BODY_SIZE), bg=C["log_bg"], fg=C["log_fg"],
                       insertbackground=C["log_fg"], relief="flat")
        text.grid(row=0, column=0)
        text.insert("1.0", start)
        btns = tk.Frame(body, bg=C["paper"])
        btns.grid(row=1, column=0, sticky="e", pady=(look.SPACE.item, 0))

        def do_save():
            self._learn_note(self.learning.correct(text.get("1.0", "end-1c")))
            win.destroy()

        _Button(btns, C, "Keep my version", do_save, primary=True).grid(row=0, column=0)
        _Button(btns, C, "Cancel", win.destroy).grid(row=0, column=1, padx=(look.SPACE.inner, 0))
        win.grab_set()

    def _learn_note(self, sentence: str | None):
        """What learning kept, said in the transcript; nothing is remembered silently."""
        if sentence:
            self._insert(f"[{sentence}]\n", ("error",) if sentence.startswith("Learning is on, but") else ())

    # ------------------------------------------------------------- text
    def _insert(self, text: str, tags: tuple[str, ...]):
        self.transcript.insert("end", text, tags)
        self.transcript.see("end")

    def _add_block(self, header_text: str, tone: str) -> str:
        """A collapsed header line; returns the body tag later text is appended to.

        Tag and mark names below have no "+" or "-" in them on purpose: Tk's
        text-index parser splits a name like "mark-1+1c" on its OWN hyphen
        first, looks for a mark named "mark" (there is none) and fails —
        measured directly (xvfb-run, Tk 8.6), not assumed.
        """
        self._seq += 1
        hdr_tag, body_tag, mark = f"hdr{self._seq}", f"body{self._seq}", f"mark{self._seq}"
        start = self.transcript.index("end-1c")
        self.transcript.insert("end", "▸ " + header_text + "\n", (hdr_tag,))
        self.transcript.mark_set(mark, start)
        # Left gravity: a mark with the default (right) gravity is pushed to
        # sit AFTER whatever is next inserted exactly at it, so a later
        # `insert(mark, glyph)` in _toggle would land the new glyph BEHIND
        # the mark instead of where it belongs — measured directly
        # (xvfb-run, Tk 8.6): with the default, `get(mark, mark+1c)` reads
        # the character that used to follow the glyph, not the glyph just
        # written.
        self.transcript.mark_gravity(mark, "left")
        self.transcript.tag_configure(hdr_tag, foreground=self.C[tone])
        self.transcript.tag_bind(hdr_tag, "<Button-1>",
                                 lambda _e, b=body_tag, m=mark: self._toggle(b, m))
        self.transcript.tag_bind(hdr_tag, "<Enter>",
                                 lambda _e: self.transcript.configure(cursor="hand2"))
        self.transcript.tag_bind(hdr_tag, "<Leave>",
                                 lambda _e: self.transcript.configure(cursor=""))
        self.transcript.tag_configure(body_tag, elide=True)
        self._collapsed[body_tag] = True
        self._block_hdr[body_tag] = hdr_tag
        return body_tag

    def _toggle(self, body_tag: str, mark: str):
        collapsed = not self._collapsed.get(body_tag, True)
        self._collapsed[body_tag] = collapsed
        self.transcript.tag_configure(body_tag, elide=collapsed)
        hdr_tag = self._block_hdr[body_tag]
        self.transcript.delete(mark, f"{mark}+1c")
        self.transcript.insert(mark, "▸" if collapsed else "▾", (hdr_tag,))
