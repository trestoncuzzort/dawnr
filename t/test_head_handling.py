"""Every place that reads a training document must know every head we write.

The corpus grew a `Signature:` line and then an `Example:` line on 2026-09-19.
Each addition broke a different reader that knew only the heads that existed
when it was written: the answer splitter left two programs in one reply and 216
of 232 answers failed to parse, and the copy check's stripper dropped documents
silently. These tests fail if a new head is added without teaching the readers.
"""
import re
import unittest

import head_align_corpus
import loop_filter
import loop_locallm
import surface

HEADS = ("Problem: find squares\n", "Signature: f(seq) -> seq\n", "Example: f([1]) == [1]\n")
PROGRAM = ("t 1\ntask f(s: seq) returns (r: seq)\n  ensures len(r) == len(s)\n"
           "{\n  r := s;\n}\n")


class HeadTests(unittest.TestCase):
    def test_the_stripper_removes_every_head_we_write(self):
        document = "".join(HEADS) + PROGRAM
        self.assertEqual(loop_filter.strip_head(document), PROGRAM)
        self.assertTrue(surface.parse(loop_filter.strip_head(document)))

    def test_the_stripper_leaves_a_bare_program_alone(self):
        self.assertEqual(loop_filter.strip_head(PROGRAM), PROGRAM)

    def test_both_splitters_cut_at_every_head(self):
        corpus = "".join(HEADS) + PROGRAM + "\n\n" + "Signature: g(int) -> int\n" + PROGRAM
        for pattern in (r"\n\s*\n(?=Problem: |Signature: |t \d)",):
            self.assertEqual(len([d for d in re.split(pattern, corpus) if d.strip()]), 2)
        # the modules themselves must carry that pattern, not just this test
        for module in (loop_filter, loop_locallm):
            source = open(module.__file__).read()
            self.assertIn("Signature: |t ", source, module.__name__)

    def test_the_head_aligner_agrees_with_the_stripper(self):
        aligned, counts = head_align_corpus.align(PROGRAM)
        self.assertEqual(counts["heads_added"], 1)
        self.assertEqual(loop_filter.strip_head(aligned[0]), PROGRAM)

    def test_an_example_head_round_trips_through_generate_and_back(self):
        entry = {"fn": "f", "rec": {"text": "find squares"},
                 "points": [{"args": [["seq", [1, 2]]], "expected": ["seq", [1, 4]]}]}
        head = loop_locallm.problem_head(entry, True)
        self.assertIn("Example: f([1, 2]) == [1, 4]", head)
        self.assertEqual(loop_filter.strip_head(head + PROGRAM), PROGRAM)


if __name__ == "__main__":
    unittest.main()
