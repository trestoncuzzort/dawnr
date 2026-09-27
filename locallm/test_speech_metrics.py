"""Tests for speech/metrics.py, checked against jiwer's own published edge
cases (see metrics.py's module docstring for the citation). No torch."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from speech.metrics import cer, levenshtein, wer  # noqa: E402


class LevenshteinTest(unittest.TestCase):
    def test_identical_sequences(self):
        self.assertEqual(levenshtein("cat", "cat"), 0)

    def test_one_substitution(self):
        self.assertEqual(levenshtein("cat", "bat"), 1)

    def test_one_insertion(self):
        self.assertEqual(levenshtein("cat", "cats"), 1)

    def test_one_deletion(self):
        self.assertEqual(levenshtein("cats", "cat"), 1)

    def test_empty_vs_empty(self):
        self.assertEqual(levenshtein("", ""), 0)

    def test_empty_vs_nonempty_is_every_insertion(self):
        self.assertEqual(levenshtein("", "abc"), 3)

    def test_symmetric(self):
        self.assertEqual(levenshtein("kitten", "sitting"), levenshtein("sitting", "kitten"))

    def test_classic_kitten_sitting_is_three(self):
        self.assertEqual(levenshtein("kitten", "sitting"), 3)


class WerCerJiwerParityTest(unittest.TestCase):
    """jiwer (Apache-2.0), raw.githubusercontent.com/jitsi/jiwer/master/README.md,
    fetched 2026-09-27: these exact assertions appear there as the documented
    behaviour, including the empty-reference edge case."""

    def test_wer_both_empty_is_zero(self):
        self.assertEqual(wer("", ""), 0)

    def test_wer_empty_reference_one_word_hypothesis(self):
        self.assertEqual(wer("", "silence"), 1)

    def test_wer_empty_reference_two_word_hypothesis(self):
        self.assertEqual(wer("", "peaceful silence"), 2)

    def test_cer_empty_reference_one_char(self):
        self.assertEqual(cer("", "a"), 1)

    def test_cer_empty_reference_five_chars(self):
        self.assertEqual(cer("", "abcde"), 5)

    def test_wer_example_from_jiwer_readme(self):
        # jiwer's own headline example: "hello world" vs "hello duck" is one
        # substitution over two reference words.
        self.assertAlmostEqual(wer("hello world", "hello duck"), 0.5)

    def test_wer_perfect_match_is_zero(self):
        self.assertEqual(wer("the quick brown fox", "the quick brown fox"), 0)

    def test_cer_counts_spaces(self):
        # "ab" -> "a b": one insertion (a space), so cer == 1/2.
        self.assertAlmostEqual(cer("ab", "a b"), 0.5)


if __name__ == "__main__":
    unittest.main()
