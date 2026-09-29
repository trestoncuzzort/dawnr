"""continue_from_checkpoint --init takes a run directory or a checkpoint file
(2026-09-29): the r12 launcher hands over the pretraining run's best.pt, the
early-stopped state, and the directory reading (ckpt.pt, the last state) could
never reach it. init_paths resolves both, the way checkpoint.load_checkpoint
already reads a kept weights-only checkpoint for generation, and load_core
initializes from either. CPU only, a few seconds."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import continue_from_checkpoint as cfc  # noqa: E402


class InitPathsTests(unittest.TestCase):
    def test_directory_reads_its_ckpt_and_tokenizer(self):
        with tempfile.TemporaryDirectory() as d:
            ckpt, tok = cfc.init_paths(Path(d))
            self.assertEqual(ckpt, Path(d) / "ckpt.pt")
            self.assertEqual(tok, Path(d) / "tokenizer.json")

    def test_file_reads_itself_and_the_tokenizer_beside_it(self):
        with tempfile.TemporaryDirectory() as d:
            best = Path(d) / "best.pt"
            best.write_bytes(b"")
            ckpt, tok = cfc.init_paths(best)
            self.assertEqual(ckpt, best)
            self.assertEqual(tok, Path(d) / "tokenizer.json")

    def test_load_core_from_a_weights_only_file(self):
        import torch
        from model import GPT, GPTConfig
        cfg = GPTConfig(vocab_size=16, block_size=8, n_layer=1, n_head=1, n_embd=8, dropout=0.0)
        model = GPT(cfg)
        with tempfile.TemporaryDirectory() as d:
            best = Path(d) / "best.pt"
            torch.save({"model": model.state_dict(), "config": cfg.__dict__, "step": 3}, best)
            loaded, config, fp = cfc.load_core(best, "cpu", 0.1, torch, GPT, GPTConfig)
            self.assertEqual(config.vocab_size, 16)
            self.assertEqual(config.dropout, 0.1)
            for k, v in model.state_dict().items():
                self.assertTrue(torch.equal(v, loaded.state_dict()[k]), k)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
