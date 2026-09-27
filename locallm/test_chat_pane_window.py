"""The chat pane in a real Tk window: rendering, collapsing, Stop, the ask dialog.

test_chat_pane.py never builds a window; this file does, so it needs a
display and skips without one, the same way test_home_window.py does for
step 4:

    xvfb-run -a python3 -m unittest test_chat_pane_window -v

Nothing here needs torch either: chat_engine()'s cache (chat_pane._ENGINE) is
filled with a fake EngineBundle whose Engine/checkpoint/build_harness are
plain Python test doubles, the same trick test_home_window.py plays on
home._ENGINE to make studio look absent.
"""
from __future__ import annotations

import json
import os
import pathlib
import queue
import sys
import tempfile
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import chat                                                        # noqa: E402
import chat_pane                                                   # noqa: E402
import home                                                         # noqa: E402
import look                                                         # noqa: E402
from test_chat_pane import FakeTokenizer, toks                     # noqa: E402


def usable():
    if not (os.environ.get("DISPLAY") or sys.platform in ("win32", "darwin")):
        return "no display; run under xvfb-run -a"
    return ""


class FakeCheckpointModule:
    """Stands in for checkpoint.py: no disk, no torch, just what refresh()/send() call."""

    def __init__(self, tokenizer, model="model", fail_tokenizer=None, fail_checkpoint=None):
        self.tokenizer = tokenizer
        self.model = model
        self.fail_tokenizer = fail_tokenizer
        self.fail_checkpoint = fail_checkpoint
        self.load_checkpoint_calls: list = []

    def load_tokenizer(self, path):
        if self.fail_tokenizer is not None:
            raise self.fail_tokenizer
        return self.tokenizer

    def load_checkpoint(self, directory):
        self.load_checkpoint_calls.append(directory)
        if self.fail_checkpoint is not None:
            raise self.fail_checkpoint
        return self.model, self.tokenizer, {}


class FakeEngine:
    def __init__(self, columns, delay=0.0):
        self.columns = columns
        self.delay = delay

    def generate(self, prompt_tokens, **kw):
        for tok in self.columns:
            if self.delay:
                time.sleep(self.delay)
            yield [tok], [1]


class FakeEngineModule:
    """Stands in for engine.py: Engine.generate and reply_parts, nothing else."""

    def __init__(self, columns, final_parts=None, delay=0.0):
        self.columns = columns
        self.final_parts = final_parts if final_parts is not None else [{"type": "text", "text": ""}]
        self.delay = delay
        self.harness_seen: list = []

    def Engine(self, model, tokenizer, harness=None, **kw):
        self.harness_seen.append(harness)
        return FakeEngine(self.columns, self.delay)

    def reply_parts(self, tokenizer, produced):
        return self.final_parts


def fake_bundle(tok, columns, checkpoint=None, final_parts=None, delay=0.0):
    checkpoint = checkpoint or FakeCheckpointModule(tok)
    engine_mod = FakeEngineModule(columns, final_parts, delay)
    harnesses: list = []

    def build_harness(config, approver=None):
        harnesses.append((config, approver))
        return object()

    bundle = chat_pane.EngineBundle(engine_mod, checkpoint, build_harness)
    return bundle, engine_mod, harnesses


@unittest.skipIf(usable(), usable())
class HomeIntegrationTests(unittest.TestCase):
    """Card 5 exists, is a chat_pane.ChatPane, and Home._drain really forwards
    "chat-*" queue messages to it through the page's own .after loop — not a
    second pump."""

    def setUp(self):
        import tkinter as tk                                       # noqa: PLC0415
        self.root = tk.Tk()
        self.page = home.Home(self.root)

    def tearDown(self):
        for cb in self.root.tk.call("after", "info"):
            self.root.after_cancel(cb)
        self.root.destroy()

    def pump(self, until, seconds=5.0):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.root.update()
            if until():
                return True
            time.sleep(0.01)
        return False

    def test_card_five_is_chat(self):
        self.assertEqual(sorted(self.page.cards), [1, 2, 3, 4, 5])
        self.assertIsInstance(self.page.chat, chat_pane.ChatPane)

    def test_an_event_put_on_the_shared_queue_reaches_the_transcript(self):
        self.page.q.put(("chat-event", ("text", "hello from the queue")))
        self.page.q.put(("chat-done", {"stopped": False}))
        ok = self.pump(lambda: "hello from the queue" in
                       self.page.chat.transcript.get("1.0", "end-1c"))
        self.assertTrue(ok, "the pane's own event never reached the transcript")

    def test_the_status_line_is_a_plain_sentence_not_a_traceback(self):
        mark, say = self.page._marks[5].cget("text"), self.page._says[5].cget("text")
        self.assertIn(mark[0], look.MARKS)
        self.assertNotIn("Traceback", say)


@unittest.skipIf(usable(), usable())
class ChatPaneTests(unittest.TestCase):
    """ChatPane built directly against a bare frame, decoupled from whichever
    checkpoint (if any) happens to sit on disk in this checkout."""

    def setUp(self):
        import tkinter as tk                                       # noqa: PLC0415
        self.tk = tk
        self.saved_engine = list(chat_pane._ENGINE)
        chat_pane._ENGINE.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = tk.Tk()
        self.parent = tk.Frame(self.root)
        self.parent.grid()
        self.q: queue.Queue = queue.Queue()
        self.statuses: list = []
        self.pane = chat_pane.ChatPane(
            self.parent, look.palette(dark=False), self.q,
            checkpoint_dir=pathlib.Path(self.tmp.name), on_status=self.statuses.append)

    def tearDown(self):
        for cb in self.root.tk.call("after", "info"):
            self.root.after_cancel(cb)
        self.root.destroy()
        self.tmp.cleanup()
        chat_pane._ENGINE[:] = self.saved_engine

    def drain(self):
        while True:
            try:
                kind, payload = self.q.get_nowait()
            except queue.Empty:
                return
            self.pane.handle(kind, payload)

    def find(self, predicate, widget=None):
        widget = widget or self.parent.winfo_toplevel()
        out = []
        for w in widget.winfo_children():
            if predicate(w):
                out.append(w)
            out += self.find(predicate, w)
        return out

    def button(self, label, widget=None):
        found = self.find(lambda w: isinstance(w, self.tk.Canvas)
                          and getattr(w, "_label", None) == label, widget)
        self.assertEqual(len(found), 1, f"expected exactly one {label!r} button, found {len(found)}")
        return found[0]

    # ---------------------------------------------------------- rendering
    def test_text_streams_in_the_order_it_is_fed(self):
        for item in [("text", "Hel"), ("text", "lo"), ("text", "!")]:
            self.q.put(("chat-event", item))
        self.drain()
        self.assertEqual(self.pane.transcript.get("1.0", "end-1c"), "Hello!")

    def test_a_tool_call_and_its_trusted_output_are_collapsed_by_default(self):
        for item in [("call_start", "t"), ("call_text", "assert 1"), ("call_end", None),
                    ("output_start", {"untrusted": False}), ("output_text", "ok"),
                    ("output_end", None)]:
            self.q.put(("chat-event", item))
        self.drain()
        text = self.pane.transcript.get("1.0", "end-1c")
        self.assertIn("t program", text)
        self.assertIn("from a tool", text)
        self.assertNotIn("untrusted", text)
        self.assertEqual(self.pane.transcript.tag_cget("body1", "elide"), "1")
        self.assertEqual(self.pane.transcript.tag_cget("body2", "elide"), "1")

    def test_untrusted_output_says_so_and_is_coloured_differently(self):
        for item in [("output_start", {"untrusted": True}), ("output_text", "a page"),
                    ("output_end", None)]:
            self.q.put(("chat-event", item))
        self.drain()
        self.assertIn("untrusted: from outside", self.pane.transcript.get("1.0", "end-1c"))
        untrusted_colour = self.pane.transcript.tag_cget("hdr1", "foreground")
        self.assertEqual(untrusted_colour, self.pane.C["unsettled"])
        self.assertNotEqual(untrusted_colour, self.pane.C["muted"])

    def test_clicking_a_header_expands_it_and_clicking_again_collapses_it(self):
        self.q.put(("chat-event", ("call_start", "t")))
        self.q.put(("chat-event", ("call_end", None)))
        self.drain()
        self.assertEqual(self.pane.transcript.tag_cget("body1", "elide"), "1")
        self.pane._toggle("body1", "mark1")
        self.assertEqual(self.pane.transcript.tag_cget("body1", "elide"), "0")
        self.assertEqual(self.pane.transcript.get("mark1", "mark1+1c"), "▾")
        self.pane._toggle("body1", "mark1")
        self.assertEqual(self.pane.transcript.tag_cget("body1", "elide"), "1")
        self.assertEqual(self.pane.transcript.get("mark1", "mark1+1c"), "▸")

    # -------------------------------------------------------------- ready
    def test_needs_torch_message(self):
        chat_pane._ENGINE[:] = [(None, "PyTorch is not installed.")]
        say = self.pane.refresh()
        self.assertEqual(say.word, "Needs PyTorch")
        self.assertFalse(self.pane._ready)
        self.assertFalse(self.pane.b_send._enabled)

    def test_needs_a_checkpoint_when_none_is_given(self):
        tok = FakeTokenizer(chat.CHAT_TOKENS)
        bundle, _engine, _h = fake_bundle(tok, [])
        chat_pane._ENGINE[:] = [(bundle, "")]
        self.pane.checkpoint_dir = None
        say = self.pane.refresh()
        self.assertEqual(say.word, "Needs a chat checkpoint")

    def test_needs_a_checkpoint_when_the_tokenizer_file_is_missing(self):
        tok = FakeTokenizer(chat.CHAT_TOKENS)
        checkpoint = FakeCheckpointModule(tok, fail_tokenizer=FileNotFoundError("gone"))
        bundle, _engine, _h = fake_bundle(tok, [], checkpoint=checkpoint)
        chat_pane._ENGINE[:] = [(bundle, "")]
        say = self.pane.refresh()
        self.assertEqual(say.word, "Needs a chat checkpoint")

    def test_not_a_chat_checkpoint_when_the_tokenizer_lacks_chat_tokens(self):
        tok = FakeTokenizer(())                                    # no chat tokens at all
        bundle, _engine, _h = fake_bundle(tok, [])
        chat_pane._ENGINE[:] = [(bundle, "")]
        say = self.pane.refresh()
        self.assertEqual(say.word, "Not a chat checkpoint")
        self.assertFalse(self.pane._ready)

    def test_ready_when_torch_the_modules_and_a_chat_checkpoint_all_exist(self):
        tok = FakeTokenizer(chat.CHAT_TOKENS)
        bundle, _engine, _h = fake_bundle(tok, [])
        chat_pane._ENGINE[:] = [(bundle, "")]
        say = self.pane.refresh()
        self.assertEqual(say.word, "Ready")
        self.assertTrue(self.pane._ready)
        self.assertTrue(self.pane.b_send._enabled)

    # --------------------------------------------------------- send / stop
    def test_send_streams_text_a_tool_call_and_untrusted_output_end_to_end(self):
        tok = FakeTokenizer(chat.CHAT_TOKENS + chat.HARNESS_TOKENS)
        columns = toks(tok, "Hi ", chat.T_START, "ok", chat.T_END,
                      chat.OUTPUT_START, "4", chat.OUTPUT_END,
                      chat.TOOL_START, "web {}", chat.TOOL_END,
                      chat.OUTPUT_START, chat.UNTRUSTED, "a page", chat.OUTPUT_END,
                      " bye", chat.ASSISTANT_END)
        bundle, engine_mod, harnesses = fake_bundle(tok, columns)
        chat_pane._ENGINE[:] = [(bundle, "")]
        self.pane.refresh()
        self.assertTrue(self.pane._ready)

        self.pane.entry.insert(0, "hello")
        self.pane.send()
        self.assertFalse(self.pane.b_send._enabled)
        self.assertTrue(self.pane.b_stop._enabled)

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.drain()
            if not self.pane.b_stop._enabled:
                break
            time.sleep(0.01)

        text = self.pane.transcript.get("1.0", "end-1c")
        self.assertIn("You: hello", text)
        self.assertIn("t program", text)
        self.assertIn("from a tool", text)
        self.assertIn("Tool call", text)
        self.assertIn("untrusted: from outside", text)
        # streaming order: the user's turn, then "Hi", then the t call and its
        # trusted output, then the tool call and its untrusted output, then
        # the closing "bye" — never out of sequence.
        marks = ("You: hello", "Hi", "t program", "from a tool", "Tool call",
                "untrusted: from outside", "bye")
        positions = [text.index(m) for m in marks]
        self.assertEqual(positions, sorted(positions))
        self.assertTrue(self.pane.b_send._enabled)
        self.assertFalse(self.pane.b_stop._enabled)
        self.assertEqual(len(self.pane.messages), 2)
        self.assertEqual(self.pane.messages[0], {"role": "user", "content": "hello"})
        self.assertEqual(len(engine_mod.harness_seen), 1)
        self.assertEqual(len(harnesses), 1)

    def test_stop_ends_a_long_reply_early(self):
        tok = FakeTokenizer(chat.CHAT_TOKENS)
        columns = toks(tok, "x" * 2000)
        bundle, _engine, _h = fake_bundle(tok, columns, delay=0.01)
        chat_pane._ENGINE[:] = [(bundle, "")]
        self.pane.refresh()
        self.pane.entry.insert(0, "go on forever")
        self.pane.send()

        seen: list = []

        def look():
            self.drain()
            seen.append(len(self.pane.transcript.get("1.0", "end-1c")))
            if len(seen) == 3:
                self.pane.stop()
            # b_stop disables itself the instant Stop is pressed (stop()'s own
            # doing, mirroring home.py's _stop_writing) — b_send only comes
            # back once _on_done actually runs, which is the real "finished"
            # signal a background thread's Stop must be waited for.
            if not self.pane.b_send._enabled:
                self.root.after(15, look)
            else:
                self.root.quit()

        self.root.after(15, look)
        self.root.after(30_000, self.root.quit)          # a hang fails, not blocks
        self.root.mainloop()
        self.drain()

        self.assertFalse(self.pane.b_stop._enabled)
        self.assertTrue(self.pane.b_send._enabled)
        self.assertLess(len(self.pane.transcript.get("1.0", "end-1c")), 1500,
                        "it went on writing after Stop")

    # --------------------------------------------------------- ask dialog
    def test_the_ask_dialog_shows_the_call_and_why(self):
        self.pane.handle("chat-ask", {"name": "web_fetch", "arguments": {"url": "http://x"},
                                     "why": "the tool's default"})
        self.assertIsNotNone(self.pane._ask_win)
        text = self.pane._ask_win.winfo_children()[0]
        shown = " ".join(w.cget("text") for w in text.winfo_children()
                         if isinstance(w, self.tk.Label))
        self.assertIn("web_fetch", shown)
        self.assertIn("http://x", shown)
        self.assertIn("the tool's default", shown)
        self.pane._answer_ask(False)

    def test_clicking_deny_answers_false_and_closes_the_dialog(self):
        self.pane.handle("chat-ask", {"name": "t", "arguments": {}, "why": "asked"})
        self.button("Deny")._press()
        self.assertIsNone(self.pane._ask_win)
        self.assertFalse(self.pane._ask_answer["approved"])
        self.assertTrue(self.pane._ask_evt.is_set())

    def test_clicking_approve_answers_true(self):
        self.pane.handle("chat-ask", {"name": "t", "arguments": {}, "why": "asked"})
        self.button("Approve")._press()
        self.assertIsNone(self.pane._ask_win)
        self.assertTrue(self.pane._ask_answer["approved"])

    def test_stop_denies_a_pending_ask_and_unblocks_the_waiting_caller(self):
        import threading                                            # noqa: PLC0415
        approver = chat_pane.make_approver(self.q, self.pane._ask_evt, self.pane._ask_answer)
        result: dict = {}
        t = threading.Thread(target=lambda: result.setdefault(
            "value", approver("web_fetch", {}, "the tool's default")), daemon=True)
        t.start()
        kind, payload = self.q.get(timeout=5)
        self.pane.handle(kind, payload)
        self.assertIsNotNone(self.pane._ask_win)
        self.pane.stop()
        t.join(timeout=5)
        self.assertFalse(t.is_alive())
        self.assertFalse(result["value"])
        self.assertIsNone(self.pane._ask_win)
        self.assertTrue(self.pane.stop_evt.is_set())

    # ----------------------------------------------------------- settings
    def test_settings_dialog_defaults_to_offline_and_save_writes_the_flag(self):
        config_path = self.pane.config_path
        self.assertFalse(config_path.exists())
        self.pane.open_settings()
        box = self.find(lambda w: isinstance(w, self.tk.Checkbutton))[0]
        box.invoke()                                                # turn network ON
        self.button("Save")._press()
        self.assertTrue(config_path.is_file())
        self.assertEqual(json.loads(config_path.read_text(encoding="utf-8")), {"offline": False})

    def test_settings_cancel_does_not_write(self):
        self.pane.open_settings()
        self.button("Cancel")._press()
        self.assertFalse(self.pane.config_path.exists())

    def test_settings_preserves_keys_it_does_not_understand(self):
        chat_pane.save_harness_config(self.pane.config_path,
                                      {"offline": True, "skills": ["skills"]})
        self.pane.open_settings()
        box = self.find(lambda w: isinstance(w, self.tk.Checkbutton))[0]
        box.invoke()
        self.button("Save")._press()
        after = json.loads(self.pane.config_path.read_text(encoding="utf-8"))
        self.assertEqual(after, {"offline": False, "skills": ["skills"]})


if __name__ == "__main__":
    unittest.main()
