"""Tests for speech/ctc_decode.py against hand-built logits, checking the
exact collapse rule from distill.pub/2017/ctc (fetched 2026-09-27): merge
adjacent repeats, then drop blanks -- and the reason CTC needs a blank
between two *real* repeated symbols, illustrated by the article's own
"hello" vs "helo" example. No randomness, no training: every frame's argmax
is chosen by hand. CPU, needs torch.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

from speech.ctc_decode import decode_text, greedy_ids  # noqa: E402
from speech.text import CTCVocab  # noqa: E402


def one_hot_log_probs(ids: list[int], vocab_size: int) -> torch.Tensor:
    """(1, len(ids), vocab_size) log-probs with argmax == ids at each frame,
    everything else strongly suppressed -- greedy_ids reads only the argmax,
    so this is enough to drive it exactly."""
    frames = torch.full((len(ids), vocab_size), -20.0)
    for t, i in enumerate(ids):
        frames[t, i] = 0.0
    return frames.unsqueeze(0)


class GreedyIdsTest(unittest.TestCase):
    def test_blank_only_collapses_to_nothing(self):
        ids = greedy_ids(one_hot_log_probs([0, 0, 0], 5), torch.tensor([3]))
        self.assertEqual(ids, [[]])

    def test_adjacent_repeats_collapse_to_one(self):
        # a a a -> a (no blank between them: CTC treats this as one long "a")
        ids = greedy_ids(one_hot_log_probs([1, 1, 1], 5), torch.tensor([3]))
        self.assertEqual(ids, [[1]])

    def test_blank_between_repeats_keeps_both(self):
        # a _ a -> a a: the blank is what lets a genuine double letter survive
        ids = greedy_ids(one_hot_log_probs([1, 0, 1], 5), torch.tensor([3]))
        self.assertEqual(ids, [[1, 1]])

    def test_distinct_neighbors_need_no_blank(self):
        # a b -> a b directly: collapsing only merges EQUAL neighbors
        ids = greedy_ids(one_hot_log_probs([1, 2], 5), torch.tensor([2]))
        self.assertEqual(ids, [[1, 2]])

    def test_truncates_to_given_length_ignoring_padded_tail(self):
        # frames past `lengths` (here, batch padding) must never be decoded
        ids = greedy_ids(one_hot_log_probs([1, 1, 2, 2], 5), torch.tensor([2]))
        self.assertEqual(ids, [[1]])

    def test_rejects_mismatched_lengths_argument(self):
        with self.assertRaises(ValueError):
            greedy_ids(one_hot_log_probs([1], 5), torch.tensor([1, 1]))

    def test_rejects_non_3d_input(self):
        with self.assertRaises(ValueError):
            greedy_ids(torch.zeros(3, 5), torch.tensor([3]))


class DecodeTextTest(unittest.TestCase):
    def setUp(self):
        self.vocab = CTCVocab()

    def _ids_for(self, text: str) -> list[int]:
        return [self.vocab.stoi[c] for c in text]

    def test_hello_needs_a_blank_between_the_two_ls(self):
        # distill.pub/2017/ctc's own worked example: collapsing [h,h,e,l,l,l,o]
        # gives "helo", not "hello" -- a real double letter needs a blank
        # between the two repeats to survive the collapse.
        blank = self.vocab.blank_id
        h, e, l, o = self._ids_for("h"), self._ids_for("e"), self._ids_for("l"), self._ids_for("o")
        alignment_helo = [h[0], h[0], e[0], l[0], l[0], l[0], o[0]]
        alignment_hello = [h[0], h[0], e[0], l[0], blank, l[0], l[0], o[0]]
        vocab_size = self.vocab.vocab_size
        self.assertEqual(
            decode_text(one_hot_log_probs(alignment_helo, vocab_size), torch.tensor([len(alignment_helo)]),
                       self.vocab),
            ["helo"])
        self.assertEqual(
            decode_text(one_hot_log_probs(alignment_hello, vocab_size), torch.tensor([len(alignment_hello)]),
                       self.vocab),
            ["hello"])

    def test_batch_of_two_independent_rows(self):
        vocab_size = self.vocab.vocab_size
        cat_ids = self._ids_for("cat")
        dog_ids = self._ids_for("dog")
        max_len = 3
        frames = torch.full((2, max_len, vocab_size), -20.0)
        for t, i in enumerate(cat_ids):
            frames[0, t, i] = 0.0
        for t, i in enumerate(dog_ids):
            frames[1, t, i] = 0.0
        texts = decode_text(frames, torch.tensor([3, 3]), self.vocab)
        self.assertEqual(texts, ["cat", "dog"])


if __name__ == "__main__":
    unittest.main()
