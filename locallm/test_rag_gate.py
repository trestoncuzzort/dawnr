"""Tests for rag_gate.py: AlignScore's chunking and aggregation (github.com/yuh-zha/AlignScore inference.py)."""
import unittest

from locallm import rag_gate

split = lambda t: [s.strip() + "." for s in t.split(".") if s.strip()]


class TestChunks(unittest.TestCase):
    def test_short_premise_is_one_sentence_a_chunk_group(self):
        # 3 sentences, 6 words: n_chunk = 6 // 350 + 1 = 1, then max(3 // 1, 1) = 3 sentences a chunk
        self.assertEqual(rag_gate.chunks("a b. c d. e f.", split), ["a b. c d. e f."])

    def test_long_premise_split_near_350_words(self):
        sents = [" ".join(["w"] * 99) + " x." for _ in range(8)]    # 800 words in 8 sentences
        parts = rag_gate.chunks(" ".join(sents), split)
        # n_chunk = 800 // 350 + 1 = 3; sentences a chunk = 8 // 3 = 2; four chunks
        self.assertEqual(len(parts), 4)

    def test_empty_premise(self):
        self.assertEqual(rag_gate.chunks("", split), [""])


class TestScore(unittest.TestCase):
    def test_mean_of_best_chunk_per_claim_sentence(self):
        table = {("A.", "x."): 0.9, ("A.", "y."): 0.1, ("B.", "x."): 0.2, ("B.", "y."): 0.7}
        align = lambda pre, hyp: [table[(p, h)] for p, h in zip(pre, hyp)]
        one_a_chunk = lambda t: [s.strip() + "." for s in t.split(".") if s.strip()]
        chunks = rag_gate.chunks
        try:
            rag_gate.chunks = lambda premise, split=None: ["A.", "B."]
            self.assertAlmostEqual(rag_gate.alignscore("A. B.", "x. y.", align, one_a_chunk), (0.9 + 0.7) / 2)
        finally:
            rag_gate.chunks = chunks

    def test_sentence_support_keeps_each_sentence(self):
        table = {("A.", "x."): 0.9, ("A.", "y."): 0.1, ("B.", "x."): 0.2, ("B.", "y."): 0.7}
        align = lambda pre, hyp: [table[(p, h)] for p, h in zip(pre, hyp)]
        one = lambda t: [s.strip() + "." for s in t.split(".") if s.strip()]
        chunks = rag_gate.chunks
        try:
            rag_gate.chunks = lambda premise, split=None: ["A.", "B."]
            self.assertEqual(rag_gate.sentence_support("A. B.", "x. y.", align, one), [0.9, 0.7])
        finally:
            rag_gate.chunks = chunks
        self.assertEqual(rag_gate.sentence_support("A.", "", lambda p, h: [1.0] * len(p), split), [])

    def test_empty_claim_scores_zero(self):
        self.assertEqual(rag_gate.alignscore("A.", "", lambda p, h: [1.0] * len(p), split), 0.0)


class TestReport(unittest.TestCase):
    def test_counts(self):
        data = {1: {"answer": [["Paris"]]}, 2: {"answer": [["Rome"]]}, 3: {"answer": [["Oslo"]]}}
        rows = [
            {"id": 1, "noise_rate": 0.4, "passage_num": 5, "prediction": "It is Paris.", "label": [1]},
            {"id": 2, "noise_rate": 0.4, "passage_num": 5, "prediction": "It is Milan.", "label": [0]},
            {"id": 3, "noise_rate": 0.4, "passage_num": 5, "prediction": "insufficient information", "label": [-1]},
            {"id": 1, "noise_rate": 1.0, "passage_num": 5, "prediction": "Paris.", "label": [1]},
            {"id": 2, "noise_rate": 1.0, "passage_num": 5, "prediction": "Milan.", "label": [0]},
            {"id": 3, "noise_rate": 1.0, "passage_num": 5, "prediction": "insufficient information", "label": [-1]},
        ]
        scores = {(1, 0.4): 0.95, (2, 0.4): 0.4, (1, 1.0): 0.2, (2, 1.0): 0.6}
        rep = rag_gate.report(data, rows, scores)
        self.assertEqual(rep["0.4"]["right"], 1)
        self.assertEqual((rep["0.4"]["shown at 0.5"], rep["0.4"]["shown and right at 0.5"]), (1, 1))
        self.assertEqual(rep["0.4"]["shown at 0.3"], 2)
        self.assertEqual(rep["1.0"]["rejected"], 1)
        self.assertEqual(rep["1.0"]["answered, holding the true answer"], 1)
        self.assertEqual(rep["1.0"]["answered, holding neither"], 1)
        self.assertEqual(rep["1.0"]["shown at 0.5"], 1)


if __name__ == "__main__":
    unittest.main()
