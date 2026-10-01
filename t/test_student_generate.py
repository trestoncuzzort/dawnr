"""t/student_generate.py reply_of (2026-10-01): where a generated row ends. A row that finishes
early in a batch is padded after its end token; the end token is found first, so a tokenizer whose
pad token IS its end token still reports a finished reply as finished. A stand-in tokenizer."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import student_generate  # noqa: E402


class Tok:
    def __init__(self, eos, pad):
        self.eos_token_id, self.pad_token_id = eos, pad

    def decode(self, tokens, skip_special_tokens):
        return "".join(chr(t) for t in tokens)


A, B, C = ord("a"), ord("b"), ord("c")


class ReplyOf(unittest.TestCase):
    def test_a_finished_row_ends_at_its_end_token_and_says_so(self):
        self.assertEqual(student_generate.reply_of([A, B, 2, 1, 1, 1], Tok(eos=2, pad=1)), ("ab", True, 2))

    def test_pad_equal_to_the_end_token_still_reads_as_finished(self):
        self.assertEqual(student_generate.reply_of([A, B, 2, 2, 2], Tok(eos=2, pad=2)), ("ab", True, 2))

    def test_a_row_cut_off_at_the_budget_is_not_finished(self):
        self.assertEqual(student_generate.reply_of([A, B, C], Tok(eos=2, pad=1)), ("abc", False, 3))

    def test_an_empty_reply_that_ends_at_once_is_finished_and_empty(self):
        self.assertEqual(student_generate.reply_of([2, 1, 1], Tok(eos=2, pad=1)), ("", True, 0))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
