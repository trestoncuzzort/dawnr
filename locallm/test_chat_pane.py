"""chat_pane's torch-free half: TokenEvents, run_chat, the config file, the approver.

No Tk root is constructed anywhere in this file (chat_pane.py itself still
needs tkinter installed to import, the same way test_home.py needs home.py's
own unconditional `import tkinter as tk` — nothing here opens a display, and
nothing here needs torch). test_chat_pane_window.py is the other half: a real
window, skipped cleanly without a display.
"""
from __future__ import annotations

import pathlib
import queue
import sys
import tempfile
import threading
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import chat                                                       # noqa: E402
import chat_pane                                                  # noqa: E402


class FakeTokenizer:
    """The two calls TokenEvents/chat.py need, over plain ASCII.

    Ordinary tokens are `ord(ch)`, always under 128; sentinel ids start at
    10_000, so the two spaces can never collide in a test that only ever
    encodes plain ASCII text.
    """

    def __init__(self, sentinels=()):
        self.sentinels = tuple(sentinels)

    def sentinel_id(self, name: str) -> int:
        return 10_000 + self.sentinels.index(name)

    def encode(self, text: str) -> list[int]:
        return [ord(c) for c in text]

    def decode(self, ids: list[int]) -> str:
        return "".join(chr(i) for i in ids)


def toks(tok, *pieces) -> list[int]:
    """Flatten a mix of plain strings (encoded char by char) and sentinel names."""
    out: list[int] = []
    for p in pieces:
        out.append(tok.sentinel_id(p)) if p in tok.sentinels else out.extend(tok.encode(p))
    return out


class TokenEventsTests(unittest.TestCase):
    def setUp(self):
        self.harness_tok = FakeTokenizer(chat.CHAT_TOKENS + chat.HARNESS_TOKENS)
        self.plain_tok = FakeTokenizer(chat.CHAT_TOKENS)

    def feed_all(self, tok, *pieces):
        events = chat_pane.TokenEvents(tok)
        out = []
        for t in toks(tok, *pieces):
            out += events.feed(t)
        return out

    def test_plain_text_streams_one_event_per_token_in_order(self):
        got = self.feed_all(self.plain_tok, "Hi!")
        self.assertEqual(got, [("text", "H"), ("text", "i"), ("text", "!")])

    def test_a_tool_call_then_its_trusted_output_in_order(self):
        got = self.feed_all(self.harness_tok, "go ", chat.T_START, "ok", chat.T_END,
                            chat.OUTPUT_START, "42", chat.OUTPUT_END, " done")
        self.assertEqual(got, [
            ("text", "g"), ("text", "o"), ("text", " "),
            ("call_start", "t"),
            ("call_text", "o"), ("call_text", "k"),
            ("call_end", None),
            ("output_start", {"untrusted": False}), ("output_text", "4"),
            ("output_text", "2"),
            ("output_end", None),
            ("text", " "), ("text", "d"), ("text", "o"), ("text", "n"), ("text", "e"),
        ])

    def test_untrusted_output_is_marked_and_the_marker_itself_produces_no_text(self):
        got = self.feed_all(self.harness_tok, chat.TOOL_START, "x", chat.TOOL_END,
                            chat.OUTPUT_START, chat.UNTRUSTED, "hi", chat.OUTPUT_END)
        self.assertEqual(got, [
            ("call_start", "tool"), ("call_text", "x"), ("call_end", None),
            ("output_start", {"untrusted": True}),
            ("output_text", "h"), ("output_text", "i"),
            ("output_end", None),
        ])

    def test_an_empty_output_span_still_opens_and_closes(self):
        got = self.feed_all(self.harness_tok, chat.OUTPUT_START, chat.OUTPUT_END)
        self.assertEqual(got, [("output_start", {"untrusted": False}), ("output_end", None)])

    def test_a_t_call_works_with_no_harness_tokens_at_all(self):
        got = self.feed_all(self.plain_tok, chat.T_START, "p", chat.T_END,
                            chat.OUTPUT_START, "1", chat.OUTPUT_END)
        self.assertEqual(got, [
            ("call_start", "t"), ("call_text", "p"), ("call_end", None),
            ("output_start", {"untrusted": False}), ("output_text", "1"), ("output_end", None),
        ])

    def test_a_tool_call_is_illegal_without_harness_tokens_and_read_as_text(self):
        """TOOL_START has no id on a tokenizer with only the chat tokens.

        chat.special would raise for it, so a TokenEvents built for one never
        looks for it (self._tool_start is None) — this pins that the
        constructor does not call chat.special(tokenizer, chat.TOOL_START) at
        all in that case, since doing so would raise ValueError from
        `self.sentinels.index(name)` before a single token was ever fed.
        """
        events = chat_pane.TokenEvents(self.plain_tok)          # must not raise
        self.assertIsNone(events._tool_start)
        self.assertIsNone(events._tool_end)
        self.assertIsNone(events._untrusted)


class RunChatTests(unittest.TestCase):
    """run_chat is home.write_pieces's own shape for events, tested the same way
    (test_home.py's TalkingWithNothingInstalled): touches only q and stop, and
    a fake Event that force-sets itself after N checks makes Stop
    deterministic with no real thread or sleep."""

    def drain(self, q: queue.Queue) -> list:
        out = []
        while not q.empty():
            out.append(q.get_nowait())
        return out

    def test_every_event_arrives_in_order_then_a_summary(self):
        events = [("text", "a"), ("call_start", "t"), ("call_end", None)]
        q: queue.Queue = queue.Queue()
        chat_pane.run_chat(lambda: iter(events), q, threading.Event())
        got = self.drain(q)
        self.assertEqual([k for k, _ in got], ["chat-event"] * 3 + ["chat-done"])
        self.assertEqual([p for _, p in got[:3]], events)
        self.assertFalse(got[-1][1]["stopped"])

    def test_stop_ends_it_between_events_and_closes_the_stream(self):
        class PressedAfterThree(threading.Event):
            checks = 0

            def is_set(self):
                self.checks += 1
                if self.checks == 4:
                    self.set()
                return super().is_set()

        def forever():
            i = 0
            while True:
                yield ("text", str(i))
                i += 1

        stream = forever()
        stop = PressedAfterThree()
        q: queue.Queue = queue.Queue()
        chat_pane.run_chat(lambda: stream, q, stop)
        got = self.drain(q)
        self.assertEqual([k for k, _ in got], ["chat-event"] * 3 + ["chat-done"])
        self.assertTrue(got[-1][1]["stopped"])
        with self.assertRaises(StopIteration):
            next(stream)                                        # closed, not merely abandoned

    def test_a_failure_is_put_on_the_queue_not_raised(self):
        def broken():
            yield ("text", "a")
            raise RuntimeError("the tool crashed")
        q: queue.Queue = queue.Queue()
        chat_pane.run_chat(broken, q, threading.Event())
        got = self.drain(q)
        self.assertEqual(got[-1][0], "chat-failed")
        self.assertIn("the tool crashed", got[-1][1])

    def test_it_touches_only_make_events_q_and_stop(self):
        import inspect
        self.assertEqual(list(inspect.signature(chat_pane.run_chat).parameters),
                         ["make_events", "q", "stop"])


class HarnessConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.tmp.name) / "harness.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_missing_file_defaults_to_offline(self):
        self.assertEqual(chat_pane.load_harness_config(self.path), {"offline": True})

    def test_a_malformed_file_defaults_to_offline_rather_than_raising(self):
        self.path.write_text("not json", encoding="utf-8")
        self.assertEqual(chat_pane.load_harness_config(self.path), {"offline": True})

    def test_saving_then_loading_round_trips(self):
        chat_pane.save_harness_config(self.path, {"offline": False, "permissions": {"t": "allow"}})
        self.assertEqual(chat_pane.load_harness_config(self.path),
                         {"offline": False, "permissions": {"t": "allow"}})

    def test_saving_preserves_keys_this_file_never_writes(self):
        chat_pane.save_harness_config(self.path, {"offline": True, "skills": ["skills"],
                                                   "mcp_servers": {"dawnr": {"command": "x"}}})
        config = chat_pane.load_harness_config(self.path)
        config["offline"] = False
        chat_pane.save_harness_config(self.path, config)
        after = chat_pane.load_harness_config(self.path)
        self.assertEqual(after["skills"], ["skills"])
        self.assertEqual(after["mcp_servers"], {"dawnr": {"command": "x"}})
        self.assertFalse(after["offline"])

    def test_saving_leaves_no_partial_file_behind(self):
        chat_pane.save_harness_config(self.path, {"offline": True})
        leftovers = list(self.path.parent.glob("*.tmp"))
        self.assertEqual(leftovers, [])


class ApproverTests(unittest.TestCase):
    """The one place a background thread and the Tk thread meet, tested with a
    real thread — the blocking wait is the point, so a fake Event (as
    RunChatTests uses for Stop) would not exercise it."""

    def test_blocks_until_answered_and_returns_the_answer(self):
        q: queue.Queue = queue.Queue()
        answered = threading.Event()
        answer: dict = {}
        approver = chat_pane.make_approver(q, answered, answer)
        result = {}

        def worker():
            result["value"] = approver("web_fetch", {"url": "http://x"}, "the tool's default")

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        kind, payload = q.get(timeout=5)
        self.assertEqual(kind, "chat-ask")
        self.assertEqual(payload, {"name": "web_fetch", "arguments": {"url": "http://x"},
                                   "why": "the tool's default"})
        self.assertFalse(answered.is_set())                     # still blocked
        answer["approved"] = True
        answered.set()
        t.join(timeout=5)
        self.assertFalse(t.is_alive())
        self.assertTrue(result["value"])

    def test_a_denied_answer_comes_back_false(self):
        q: queue.Queue = queue.Queue()
        answered = threading.Event()
        answer: dict = {}
        approver = chat_pane.make_approver(q, answered, answer)
        result = {}
        t = threading.Thread(target=lambda: result.setdefault(
            "value", approver("t", {}, "asked")), daemon=True)
        t.start()
        q.get(timeout=5)
        answer["approved"] = False
        answered.set()
        t.join(timeout=5)
        self.assertFalse(result["value"])

    def test_two_calls_in_sequence_each_get_their_own_fresh_answer(self):
        """The single shared slot must not leak a stale answer into the next ask."""
        q: queue.Queue = queue.Queue()
        answered = threading.Event()
        answer: dict = {}
        approver = chat_pane.make_approver(q, answered, answer)

        answer["approved"] = True
        answered.set()                                            # stale, from "before"
        result = {}
        t = threading.Thread(target=lambda: result.setdefault(
            "value", approver("t", {}, "asked")), daemon=True)
        t.start()
        q.get(timeout=5)
        self.assertFalse(answered.is_set(), "make_approver must clear() before waiting")
        self.assertEqual(answer, {}, "make_approver must clear() before waiting")
        answer["approved"] = False
        answered.set()
        t.join(timeout=5)
        self.assertFalse(result["value"])


class LabelTests(unittest.TestCase):
    def test_trust_label(self):
        self.assertEqual(chat_pane.trust_label(False), "from a tool")
        self.assertEqual(chat_pane.trust_label(True), "untrusted: from outside")

    def test_call_label(self):
        self.assertEqual(chat_pane.call_label("t"), "t program")
        self.assertEqual(chat_pane.call_label("tool"), "Tool call")


class ChatEngineDetectionTests(unittest.TestCase):
    """chat_engine() is the lazy import: a sentence on the card, never a
    traceback, and computed at most once per process (home.py's engine()/
    reader()/talker() are the same shape)."""

    def setUp(self):
        self.saved = list(chat_pane._ENGINE)
        chat_pane._ENGINE.clear()
        # Some other test file in a full `discover` run leaves a broken stand-
        # in for torch behind in sys.modules (measured 2026-09-27: it still
        # reproduces with none of this file's tests in the run at all, so it
        # is not this file's bug to fix) — only `import torch`'s own success
        # or failure decides the branch this test checks, so that entry is
        # saved and popped here rather than trusted to reflect this machine.
        self.saved_torch = sys.modules.pop("torch", None)

    def tearDown(self):
        chat_pane._ENGINE[:] = self.saved
        if self.saved_torch is not None:
            sys.modules["torch"] = self.saved_torch

    def test_the_result_is_memoised(self):
        first = chat_pane.chat_engine()
        second = chat_pane.chat_engine()
        self.assertIs(first, second)

    def test_matches_whether_torch_is_actually_installed_here(self):
        bundle, why = chat_pane.chat_engine()
        try:
            import torch                                          # noqa: F401
        except ImportError:
            self.assertIsNone(bundle)
            self.assertEqual(why, "PyTorch is not installed.")
        else:
            self.assertIsNotNone(bundle, why)
            self.assertEqual(why, "")


if __name__ == "__main__":
    unittest.main()
