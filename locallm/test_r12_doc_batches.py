"""r12 section C: one whole document per training row.

Corpus.get_batch cuts random windows from the joined corpus, so about 23% of
r12's target tokens would belong to a row whose Problem/Signature head was cut
off, and the head sits at position 0, the only place generation puts it, in
under 1% of windows. DocumentBatches gives every row its document from the
first token, right-padded with the ignore index (Ding et al., arXiv:2404.10830;
Zhao et al., arXiv:2402.13991). Needs torch: run on the lab CPU.
"""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

import data  # noqa: E402
from model import GPT, GPTConfig  # noqa: E402

ALPHABET = "\nProblem: task number 0123456789\nSignature: f(int) -> int\nr := + ;}abcdefghijklmnopqrstuvwxyz"
TOK = data.CharTokenizer.from_text(ALPHABET)


def docs(n=50):
    return [f"Problem: task number {i}\nSignature: f{i}(int) -> int\n" + ("r := r + %d;\n" % i) * (1 + i % 5) + "}"
            for i in range(n)]


class RowLayoutTests(unittest.TestCase):
    def test_a_row_starts_at_the_first_token_even_after_a_leading_newline(self):
        rows = data.DocumentBatches(["\n\nProblem: a\n}"], TOK, block_size=16, seed=0)
        x, _ = rows.get_batch(0, 1)
        self.assertEqual(int(x[0, 0]), TOK.encode("P")[0])

    def test_layout_is_exact(self):
        rows = data.DocumentBatches(["ab"], TOK, block_size=8, seed=0)
        ids = TOK.encode("ab" + data.DOC_END)
        x, y = rows.get_batch(0, 1)
        self.assertEqual(x[0].tolist(), ids[:-1] + [0] * (8 - len(ids) + 1))
        self.assertEqual(y[0].tolist(), ids[1:] + [data.IGNORE_INDEX] * (8 - len(ids) + 1))
        self.assertEqual(rows.target_tokens, len(ids) - 1)
        self.assertEqual(rows.cut_documents, 0)

    def test_a_long_document_is_cut_at_the_end_and_counted(self):
        long = "r := r + 1;\n" * 5 + "}"
        rows = data.DocumentBatches([long, "ab"], TOK, block_size=8, seed=0)
        ids = TOK.encode(long + data.DOC_END)
        self.assertEqual(rows.cut_documents, 1)
        self.assertEqual(rows.cut_tokens, len(ids) - 9)
        self.assertEqual(rows.longest_tokens, len(ids))
        for step in range(rows.batches_per_epoch(1)):
            x, y = rows.get_batch(step, 1)
            self.assertEqual(x.shape, (1, 8))
            if int(x[0, 0]) == ids[0] and x[0].tolist() == ids[:8]:
                self.assertEqual(y[0].tolist(), ids[1:9])   # the head, then the cut
        self.assertEqual(rows.record()["cut_documents"], 1)

    def test_pad_id_does_not_change_real_positions(self):
        cfg = GPTConfig(vocab_size=TOK.vocab_size, block_size=16, n_layer=1, n_head=2, n_embd=16)
        torch.manual_seed(0)
        model = GPT(cfg).eval()
        doc = "Problem: x\n}"
        a = data.DocumentBatches([doc], TOK, block_size=16, seed=0, pad_id=0)
        b = data.DocumentBatches([doc], TOK, block_size=16, seed=0, pad_id=5)
        xa, ya = a.get_batch(0, 1)
        xb, yb = b.get_batch(0, 1)
        n = int((ya[0] != data.IGNORE_INDEX).sum())
        with torch.no_grad():
            la, loss_a = model(xa, ya)
            lb, loss_b = model(xb, yb)
            ids = torch.tensor([TOK.encode(doc + data.DOC_END)])
            _, loss_plain = model(ids[:, :-1], ids[:, 1:])
        self.assertTrue(torch.equal(la[0, :n], lb[0, :n]))
        self.assertAlmostEqual(float(loss_a), float(loss_b), places=6)
        self.assertAlmostEqual(float(loss_a), float(loss_plain), places=5)


class OrderTests(unittest.TestCase):
    def test_every_document_once_per_epoch(self):
        rows = data.DocumentBatches(docs(50), TOK, block_size=64, seed=1)
        self.assertEqual(sorted(rows.order(0)), list(range(50)))
        self.assertEqual(sorted(rows.order(1)), list(range(50)))
        self.assertNotEqual(rows.order(0), rows.order(1))
        per_epoch = rows.batches_per_epoch(8)
        self.assertEqual(per_epoch, math.ceil(50 / 8))
        seen = []
        for step in range(per_epoch):
            x, _ = rows.get_batch(step, 8)
            seen.append(x.shape[0])
        self.assertEqual(sum(seen), 50)
        self.assertEqual(seen[-1], 50 - 8 * (per_epoch - 1))

    def test_seeds(self):
        a = data.DocumentBatches(docs(50), TOK, block_size=64, seed=1)
        b = data.DocumentBatches(docs(50), TOK, block_size=64, seed=1)
        c = data.DocumentBatches(docs(50), TOK, block_size=64, seed=2)
        self.assertEqual(a.order(0), b.order(0))
        self.assertNotEqual(a.order(0), c.order(0))
        # seed s at epoch 1 must not equal seed s+1 at epoch 0 (DistributedSampler's
        # seed+epoch would make consecutive arms share orders)
        self.assertNotEqual(a.order(1), c.order(0))

    def test_get_batch_is_a_pure_function_of_seed_and_step(self):
        a = data.DocumentBatches(docs(50), TOK, block_size=64, seed=3)
        b = data.DocumentBatches(docs(50), TOK, block_size=64, seed=3)
        for step in range(37):
            a.get_batch(step, 4)
        xa, ya = a.get_batch(37, 4)
        xb, yb = b.get_batch(37, 4)
        self.assertTrue(torch.equal(xa, xb) and torch.equal(ya, yb))

    def test_in_order_covers_every_row_once(self):
        rows = data.DocumentBatches(docs(11), TOK, block_size=64, seed=0)
        n = sum(x.shape[0] for x, _ in rows.in_order(4))
        self.assertEqual(n, 11)


class RefusalTests(unittest.TestCase):
    def test_refusals(self):
        with self.assertRaises(ValueError):
            data.DocumentBatches([], TOK, block_size=8, seed=0)
        with self.assertRaises(ValueError):
            data.DocumentBatches(["ab"], TOK, block_size=0, seed=0)
        no_newline = data.CharTokenizer.from_text("ab")
        with self.assertRaises(ValueError):
            data.DocumentBatches(["ab"], no_newline, block_size=8, seed=0)
        with self.assertRaises(ValueError):
            data.DocumentBatches([""], TOK, block_size=8, seed=0)

    def test_dropped_characters_and_blank_lines_are_counted(self):
        rows = data.DocumentBatches(["abé", "a\n\nb"], TOK, block_size=8, seed=0)
        self.assertEqual(rows.dropped_characters, 1)
        self.assertEqual(rows.blank_line_documents, [1])
        self.assertEqual(rows.record()["blank_line_documents"], 1)


if __name__ == "__main__":
    unittest.main()
