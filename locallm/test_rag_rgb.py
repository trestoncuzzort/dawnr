"""Tests for rag_rgb.py: the port of RGB's evalue.py (github.com/chen700564/RGB)."""
import math
import random
import unittest

from locallm import rag_rgb


def evalue_processdata(instance, noise_rate, passage_num):
    """RGB evalue.py processdata, plain dataset branch, as it runs after random.seed(2333)."""
    random.seed(2333)
    neg_num = math.ceil(passage_num * noise_rate)
    pos_num = passage_num - neg_num
    if noise_rate == 1:
        neg_num = passage_num; pos_num = 0
    else:
        if neg_num > len(instance['negative']):
            neg_num = len(instance['negative']); pos_num = passage_num - neg_num
        elif pos_num > len(instance['positive']):
            pos_num = len(instance['positive']); neg_num = passage_num - pos_num
    docs = instance['positive'][:pos_num] + instance['negative'][:neg_num]
    random.shuffle(docs)
    return docs


INST = {"id": 0, "query": "q", "answer": [["Jan 2, 2022", "January 2 2022"]],
        "positive": [f"p{i}" for i in range(12)], "negative": [f"n{i}" for i in range(27)]}


class TestSelect(unittest.TestCase):
    def test_same_documents_and_order_as_evalue(self):
        for rate in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
            self.assertEqual(rag_rgb.select(INST, rate, 5), evalue_processdata(INST, rate, 5), rate)

    def test_noise_share(self):
        docs = rag_rgb.select(INST, 0.4, 5)
        self.assertEqual(sum(d.startswith("n") for d in docs), 2)
        self.assertTrue(all(d.startswith("n") for d in rag_rgb.select(INST, 1.0, 5)))

    def test_few_positives_filled_with_negatives(self):
        inst = dict(INST, positive=["p0"])
        docs = rag_rgb.select(inst, 0.2, 5)
        self.assertEqual(sorted(docs), sorted(evalue_processdata(inst, 0.2, 5)))
        self.assertEqual(sum(d.startswith("p") for d in docs), 1)


class TestScore(unittest.TestCase):
    def test_any_alternative(self):
        self.assertEqual(rag_rgb.label("It premiered on Jan 2, 2022.", INST["answer"]), [1])
        self.assertEqual(rag_rgb.label("It premiered in March.", INST["answer"]), [0])

    def test_every_part_needed(self):
        ans = [["Paris"], ["Rome", "Roma"]]
        self.assertFalse(rag_rgb.right(rag_rgb.label("paris", ans), 0.4))
        self.assertTrue(rag_rgb.right(rag_rgb.label("Paris and Roma", ans), 0.4))

    def test_rejection(self):
        reply = "I can not answer the question because of the insufficient information in documents."
        self.assertEqual(rag_rgb.label(reply, INST["answer"]), [-1])
        self.assertTrue(rag_rgb.right([-1], 1.0))
        self.assertFalse(rag_rgb.right([-1], 0.4))
        self.assertFalse(rag_rgb.right([1], 1.0))

    def test_report(self):
        rows = [{"label": [-1]}, {"label": [1]}, {"label": [0], "error": "x"}]
        self.assertEqual(rag_rgb.report(rows, 1.0)["tt"], 1)
        self.assertEqual(rag_rgb.report(rows, 0.4)["tt"], 1)
        self.assertEqual(rag_rgb.report(rows, 0.4)["errors"], 1)


class TestPrompt(unittest.TestCase):
    def test_closed_book_has_no_system(self):
        m = rag_rgb.messages("q?", [])
        self.assertEqual([x["role"] for x in m], ["user"])
        self.assertEqual(m[0]["content"], "Document:\n \n\nQuestion:\nq?")

    def test_documents_joined_by_newline(self):
        m = rag_rgb.messages("q?", ["a", "b"])
        self.assertEqual(m[0]["role"], "system")
        self.assertEqual(m[1]["content"], "Document:\na\nb \n\nQuestion:\nq?")

    def test_ask_greedy(self):
        seen = {}
        def post(url, body):
            seen.update(body, url=url)
            return {"choices": [{"message": {"content": "x"}}]}
        self.assertEqual(rag_rgb.ask("h:1", [{"role": "user", "content": "c"}], post=post), "x")
        self.assertEqual((seen["temperature"], seen["max_tokens"], seen["url"]), (0, 512, "http://h:1/v1/chat/completions"))


if __name__ == "__main__":
    unittest.main()
