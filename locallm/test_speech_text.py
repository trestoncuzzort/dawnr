"""Tests for speech/text.py. No torch: this module is pure Python."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from speech.text import CTCVocab  # noqa: E402


class CTCVocabTest(unittest.TestCase):
    def setUp(self):
        self.vocab = CTCVocab()

    def test_blank_is_index_zero_and_alone(self):
        self.assertEqual(self.vocab.blank_id, 0)
        self.assertEqual(self.vocab.decode([0]), "")

    def test_vocab_size_is_blank_plus_28_symbols(self):
        self.assertEqual(len(self.vocab.symbols), 28)         # space + apostrophe + 26 letters
        self.assertEqual(self.vocab.vocab_size, 29)            # + blank

    def test_normalize_lowercases_and_keeps_apostrophes(self):
        self.assertEqual(self.vocab.normalize("Mister Quilter's"), "mister quilter's")

    def test_normalize_drops_digits_and_punctuation(self):
        self.assertEqual(self.vocab.normalize("It cost $12.50!"), "it cost")

    def test_normalize_collapses_repeated_spaces(self):
        self.assertEqual(self.vocab.normalize("a   b"), "a b")

    def test_normalize_strips_accents_to_base_letter(self):
        self.assertEqual(self.vocab.normalize("café"), "cafe")   # e + combining acute

    def test_encode_decode_round_trip(self):
        text = self.vocab.normalize("a quick test with spaces and it's apostrophe")
        self.assertEqual(self.vocab.decode(self.vocab.encode(text)), text)

    def test_every_symbol_round_trips_alone(self):
        for symbol in self.vocab.symbols:
            self.assertEqual(self.vocab.decode(self.vocab.encode(symbol)), symbol)

    def test_encode_rejects_characters_outside_the_alphabet(self):
        with self.assertRaises(ValueError):
            self.vocab.encode("has a digit 5")

    def test_decode_never_raises_on_out_of_range_ids(self):
        # Only ever reachable through a decoder's own bug, not through encode();
        # decode() is deliberately total rather than raising mid-transcript.
        self.assertEqual(self.vocab.decode([0, 999, -1]), "")

    def test_two_instances_agree(self):
        # The alphabet is fixed, not built from a corpus: a second instance
        # must assign identical ids, or a checkpoint saved under one and
        # loaded under another would silently decode to the wrong text.
        other = CTCVocab()
        self.assertEqual(self.vocab.stoi, other.stoi)


if __name__ == "__main__":
    unittest.main()
