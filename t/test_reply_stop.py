"""The reply stop is the document terminator (2026-09-29, r12 seed 1).

A fine-tune on `document + DOC_END` rows (data.DocumentBatches, DOC_END a blank
line) teaches the model to end its program with a blank line and nothing after
it; the stop rule that waited for the NEXT head after the blank line never
fired, and 832 of 832 r12 seed-1 replies ran to the token budget unparseable
with a complete program before the first blank line. No corpus document and no
committed task holds an internal blank line (measured), so the first blank line
after the body starts is the reply's end. No torch, no kernel.

Run: python3 t/test_reply_stop.py
"""
import glob
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import loop_locallm as ll  # noqa: E402

HEAD = "Problem: Count the ways.\nSignature: count_ways(n) -> int\n"
PROG = "t 1\ntask count_ways(n: int) returns (r: int)\n  ensures r == n\n{\n  r := n;\n}"


class ReplyStopTests(unittest.TestCase):
    def test_a_blank_line_then_the_next_head_cuts_where_it_always_did(self):
        text = HEAD + PROG + "\n\nProblem: the next one\nSignature: f(x) -> int\n"
        self.assertEqual(ll.reply_cut(HEAD, text), len(HEAD) + len(PROG))

    def test_a_blank_line_then_drift_now_cuts_at_the_terminator(self):
        text = HEAD + PROG + "\n\n# file: mathlib4/Mathlib/Domino.lean\n/- Copyright -/\n"
        self.assertEqual(ll.reply_cut(HEAD, text), len(HEAD) + len(PROG))
        self.assertEqual(ll.REPLY_BOUNDARY.split(text[len(HEAD):], maxsplit=1)[0], PROG)

    def test_no_blank_line_means_no_stop_yet(self):
        self.assertIsNone(ll.reply_cut(HEAD, HEAD + PROG))
        self.assertIsNone(ll.reply_cut(HEAD, HEAD + PROG + "\n"))

    def test_the_stop_is_a_prefix_property(self):
        # a match in a prefix is the match in the full text: the sampler checks after every token
        full = HEAD + PROG + "\n\nmore"
        for n in range(len(HEAD) + 1, len(full) + 1):
            cut = ll.reply_cut(HEAD, full[:n])
            self.assertTrue(cut is None or cut == len(HEAD) + len(PROG), (n, cut))

    def test_no_committed_task_holds_an_internal_blank_line(self):
        files = glob.glob(os.path.join(HERE, "tasks", "*.t")) + glob.glob(os.path.join(HERE, "lemmas", "*.t")) \
            + glob.glob(os.path.join(HERE, "nested", "*.t"))
        self.assertGreater(len(files), 0)
        bad = [f for f in files if re.search(r"\n[ \t]*\n", open(f, encoding="utf-8").read().strip("\n"))]
        self.assertEqual(bad, [], "a blank line inside a task would be cut by the reply stop")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
