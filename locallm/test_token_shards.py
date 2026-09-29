"""token_shards.TokenShards (2026-09-29): a pretraining corpus read from uint16 token shards through
memmap, serving Corpus's get_batch contract without holding Python ints. nanoGPT's design
(github.com/karpathy/nanoGPT, prepare.py and train.py get_batch). Needs numpy and torch."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from token_shards import TokenShards  # noqa: E402


def _shards(d: Path, sizes) -> list:
    paths, start = [], 0
    for i, n in enumerate(sizes):
        arr = np.arange(start, start + n, dtype=np.uint16)
        p = d / f"english-{i:05d}.bin"
        arr.tofile(p)
        paths.append(p)
        start += n
    return paths


class Shards(unittest.TestCase):
    def test_used_range_split_and_limit(self):
        with tempfile.TemporaryDirectory() as d:
            paths = _shards(Path(d), [1000, 1000, 1000])
            ts = TokenShards(paths, val_tokens=100)
            self.assertEqual((len(ts.train), len(ts.val)), (2900, 100))
            self.assertEqual(int(ts.val[0]), 2900)                      # the tail of the used range
            lim = TokenShards(paths, val_tokens=100, limit_tokens=1500)
            self.assertEqual((len(lim.train), len(lim.val)), (1400, 100))
            self.assertEqual(int(lim.data[-1]), 1499)                   # file order, first N tokens
            self.assertIn("english-00000.bin", ts.train_text)

    def test_batches_are_shifted_windows_and_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            paths = _shards(Path(d), [5000])
            ts = TokenShards(paths, val_tokens=500)
            g = torch.Generator().manual_seed(7)
            x, y = ts.get_batch("train", 4, 16, generator=g)
            self.assertEqual(tuple(x.shape), (4, 16))
            self.assertEqual(x.dtype, torch.int64)
            self.assertTrue(torch.equal(y[:, :-1], x[:, 1:]))          # y is x shifted by one
            self.assertTrue(torch.equal(x[:, 1:] - x[:, :-1], torch.ones(4, 15, dtype=torch.int64)))
            self.assertTrue(bool((x < 4500).all()))                     # never into the validation tail
            g2 = torch.Generator().manual_seed(7)
            x2, _ = ts.get_batch("train", 4, 16, generator=g2)
            self.assertTrue(torch.equal(x, x2))
            vx, _ = ts.get_batch("val", 2, 8, generator=g)
            self.assertTrue(bool((vx >= 4500).all()))

    def test_refusals(self):
        with tempfile.TemporaryDirectory() as d:
            paths = _shards(Path(d), [200])
            with self.assertRaises(ValueError):
                TokenShards(paths, val_tokens=200)                      # nothing left to train on
            with self.assertRaises(ValueError):
                TokenShards([], val_tokens=1)
            ts = TokenShards(paths, val_tokens=50)
            with self.assertRaises(ValueError):
                ts.get_batch("val", 1, 64)                              # block longer than the split


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
