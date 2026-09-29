"""Drawn verdicts (2026-09-29): the t tool checks inputs the prompt does not show.

On the held-out 232 one parity program answered three unrelated problems, passing each one's
two shown examples and proving its own trivial specification; the tool's verdict at training
time ran only the shown examples, so nothing in the signal told fitting two examples from
solving the problem. At training time the proved program is the oracle: t_tool.drawn_examples
takes Example lines it does not show the prompt, t_tool.call judges them as `drawn i: ...`,
chat_data puts them in every tool conversation's verdict, and repair_data turns a draft that
passes the shown examples but fails a drawn one into a repair conversation. No torch, no kernel."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "t"))

import chat_data  # noqa: E402
import chat_eval  # noqa: E402
import repair_data  # noqa: E402
import t_tool  # noqa: E402

PROVED = "t 1\ntask f(n: int) returns (r: int)\n  requires n >= 0\n  ensures r == n * 2\n{\n  r := n * 2;\n}\n"
WRONG = "t 1\ntask f(n: int) returns (r: int)\n  requires n >= 0\n  ensures r == n + n * n\n{\n  r := n + n * n;\n}\n"
PROMPT = "Problem: Double n.\nSignature: f(n) -> int\nExample: f(0) == 0\nExample: f(1) == 2"
PARITY = "t 1\ntask g(n: int) returns (r: bool)\n  ensures r == (n % 2 == 1)\n{\n  r := n % 2 == 1;\n}\n"


class Drawn(unittest.TestCase):
    def test_drawn_lines_avoid_the_prompt_and_need_no_distinct_outputs(self):
        lines = t_tool.drawn_examples(PROVED, PROMPT, 3)
        self.assertEqual(len(lines), 3, lines)
        args = [t_tool.parse_examples(ln)[0]["args"] for ln in lines]
        self.assertNotIn([0], args)
        self.assertNotIn([1], args)
        self.assertEqual(len({json.dumps(a) for a in args}), 3)
        # a bool-valued program has two outputs, and still gives k drawn inputs
        self.assertEqual(len(t_tool.drawn_examples(PARITY, "Example: g(1) == true\nExample: g(2) == false", 4)), 4)
        self.assertEqual(t_tool.drawn_examples(PROVED, PROMPT, 0), [])

    def test_the_verdict_judges_drawn_lines_after_the_shown_ones(self):
        extra = t_tool.drawn_examples(PROVED, PROMPT, 2)
        ok = t_tool.call(PROVED, PROMPT, drawn=extra).split("\n")
        self.assertEqual(ok[:2], ["parses: yes", "well formed: yes"])
        self.assertEqual([ln for ln in ok if ln.startswith("example")], ["example 1: pass", "example 2: pass"])
        self.assertEqual([ln for ln in ok if ln.startswith("drawn")], ["drawn 1: pass", "drawn 2: pass"])
        bad = t_tool.call(WRONG, PROMPT, drawn=extra).split("\n")
        self.assertEqual([ln for ln in bad if ln.startswith("example")], ["example 1: pass", "example 2: pass"])
        self.assertTrue(any(ln.startswith("drawn") and ": fail: got " in ln for ln in bad), bad)
        self.assertEqual(t_tool.call(WRONG, PROMPT), t_tool.call(WRONG, PROMPT, drawn=()))   # no drawn: as before

    def test_verdict_readers_count_drawn_lines(self):
        for reader in (repair_data.verdict_ok, chat_eval.verdict_ok):
            self.assertTrue(reader("parses: yes\nwell formed: yes\nexample 1: pass\ndrawn 1: pass"))
            self.assertFalse(reader("parses: yes\nwell formed: yes\nexample 1: pass\ndrawn 1: fail: got 6, expected 4"))
        self.assertEqual(repair_data.verdict_kind("parses: yes\nwell formed: yes\nexample 1: pass\ndrawn 1: fail: got 6, expected 4"),
                         "wrong output")

    def test_conversation_carries_drawn_verdicts(self):
        doc = "Problem: Double n.\nSignature: f(n) -> int\n" + PROVED
        conv = chat_data.conversation(doc, tool=True, drawn=2)
        verdict = conv["messages"][1]["content"][1]["text"]
        self.assertEqual(conv["drawn"], 2)
        self.assertIn("drawn 1: pass", verdict)
        self.assertIn("drawn 2: pass", verdict)
        plain = chat_data.conversation(doc, tool=True)
        self.assertEqual(plain["drawn"], 0)
        self.assertNotIn("drawn", plain["messages"][1]["content"][1]["text"])

    def test_a_draft_that_fits_the_shown_examples_but_fails_a_drawn_one_becomes_a_repair(self):
        conv = {"messages": [{"role": "user", "content": PROMPT},
                             {"role": "assistant", "content": [{"type": "t", "text": PROVED}]}],
                "source": "f", "kind": "problem", "tool": True, "examples": 2, "split": "train"}
        draft = {"index": 0, "user_sha256": repair_data.sha256_text(PROMPT), "source": "f", "fold": 0, "sample": 0,
                 "draft": WRONG, "verdict": t_tool.call(WRONG, PROMPT)}
        self.assertTrue(repair_data.verdict_ok(draft["verdict"]))               # it passes the shown examples
        rows, summary = repair_data.build([conv], [draft], drawn=0)
        self.assertEqual(rows, [])
        self.assertEqual(summary["passed_not_proved"], 1)
        rows, summary = repair_data.build([conv], [draft], drawn=3)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["built"], "repair-drawn")
        self.assertEqual(summary["passed_shown_failed_drawn"], 1)
        self.assertEqual(summary["repair_drawn_conversations"], 1)
        parts = rows[0]["messages"][1]["content"]
        self.assertEqual(parts[0]["text"], WRONG)
        self.assertFalse(parts[0]["train"])
        self.assertTrue(any(": fail: got " in ln for ln in parts[1]["text"].split("\n") if ln.startswith("drawn")))
        self.assertEqual(parts[2]["text"], PROVED)
        self.assertTrue(repair_data.verdict_ok(parts[3]["text"]))              # the proved program passes its draws


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
