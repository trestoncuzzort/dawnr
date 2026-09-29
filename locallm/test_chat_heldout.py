"""chat_heldout.py without a model: the registration gate, the record's shape (loop_locallm.py
generate's, extractable by spec_experiment.find_block), whole-or-nothing writes, no overwrite,
resume. No torch, no kernel."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "t"))

import chat_heldout as ch  # noqa: E402
import spec_experiment as se  # noqa: E402

PROG = "t 1\ntask f(n: int) returns (r: int)\n  ensures r == n\n{\n  r := n;\n}"
META = {"model": "dawnr-chat:x", "digest": "1 params", "checkpoint_sha256": "0" * 64, "pool_version": "v5",
        "options": {"temperature": 0.0, "max_new_tokens": 8}}


def _pool():
    return {5: {"fn": "f", "rec": {"task_id": 5, "text": "Return n.", "code": "def f(n):\n    return n",
                                   "test_list": ["assert f(1) == 1"]},
                "points": [{"ok": True, "fn": "f", "args": [("int", 1)], "expected": ("int", 1)}]}}


class Registration(unittest.TestCase):
    def test_refuses_without_a_prediction_naming_the_tag(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PREDICT-x.md"
            with self.assertRaises(SystemExit):
                ch.check_prereg(p, "chat-s1")                       # absent
            p.write_text("something else\n")
            with self.assertRaises(SystemExit):
                ch.check_prereg(p, "chat-s1")                       # does not name the tag
            (Path(d) / "notes.md").write_text("chat-s1\n")
            with self.assertRaises(SystemExit):
                ch.check_prereg(Path(d) / "notes.md", "chat-s1")    # not a PREDICT file
            p.write_text("the look: chat-s1\n")
            ch.check_prereg(p, "chat-s1")                           # registered


class Records(unittest.TestCase):
    def test_record_is_the_generators_shape_and_extractable(self):
        got = {"program": PROG, "ended": True, "parts": [{"type": "text", "text": PROG}], "calls": [PROG],
               "tool_verdicts": ["parses: yes\nwell formed: yes\nexample 1: pass"], "tool_calls": 1,
               "last_program": PROG, "unclosed_call": False, "ended_in_call": False, "new_tokens": 40}
        rec = ch.record_for(5, _pool()[5], "Problem: Return n.\nSignature: f(n) -> int", got, META)
        for k in ("task_id", "fn", "model", "digest", "checkpoint_sha256", "pool_version", "prompt_version",
                  "options", "messages", "reply", "done_reason"):
            self.assertIn(k, rec)
        self.assertEqual(se.find_block(rec["reply"]), PROG + "\n")
        self.assertEqual(rec["done_reason"], "stop")
        self.assertEqual(rec["conversation"]["tool_calls"], 1)
        empty = ch.record_for(5, _pool()[5], "u", {"program": None, "ended": False}, META)
        self.assertEqual(empty["reply"], "")
        self.assertEqual(empty["done_reason"], "length")

    def test_write_resume_and_no_overwrite(self):
        calls = []

        def reply(user, tid):
            calls.append(tid)
            return {"program": PROG, "ended": True, "tool_calls": 0}
        with tempfile.TemporaryDirectory() as d:
            raw = Path(d) / "raw"
            counts = ch.write_answer_set(raw, [5], _pool(), reply, META, resume=False, log=lambda *_: None)
            self.assertEqual((counts["asked"], counts["records"], counts["with_program"]), (1, 1, 1))
            self.assertEqual(json.loads((raw / "5.json").read_text())["task_id"], 5)
            self.assertFalse(list(raw.glob("*.tmp")))
            with self.assertRaises(SystemExit):
                ch.write_answer_set(raw, [5], _pool(), reply, META, resume=False)      # never overwritten
            counts = ch.write_answer_set(raw, [5], _pool(), reply, META, resume=True, log=lambda *_: None)
            self.assertEqual((counts["asked"], counts["resumed"], counts["records"]), (0, 1, 1))
            self.assertEqual(calls, [5])                                                 # asked once


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
