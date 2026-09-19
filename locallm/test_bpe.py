"""BPE must preserve code, avoid holdout fitting, and reload with model weights."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

import checkpoint
from data import BPETokenizer, CharTokenizer, Corpus, build_tokenizer, load_tokenizer
from model import GPT, GPTConfig


class BPETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.training = "\n".join(f"task example{i}(x: int) returns (r: int) {{ r := x + 1; }}" for i in range(80))
        cls.tok = BPETokenizer.from_text(cls.training, vocab_size=512)

    def test_unseen_unicode_and_code_whitespace_survive(self):
        for text in ("", "\t  x := -2;\r\n", "Σ🙂漢字 café\u0301\x00", "x / y % z != 0", " leading trailing "):
            with self.subTest(text=repr(text)):
                self.assertEqual(self.tok.decode(self.tok.encode(text)), text)

    def test_subwords_reduce_repetitive_code_length(self):
        self.assertLess(len(self.tok.encode(self.training)), len(self.training) // 2)

    def test_only_training_split_is_used_for_merges(self):
        with patch("data.group_split", return_value=(self.training, "heldout-only text")):
            tok = build_tokenizer("ignored", kind="bpe", vocab_size=512)
        self.assertEqual(tok.training["text_sha256"], hashlib.sha256(self.training.encode()).hexdigest())

    def test_reload_preserves_token_ids_and_legacy_vocab(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tokenizer.json"
            self.tok.save(path)
            loaded = load_tokenizer(path)
            self.assertEqual(loaded.encode(self.training), self.tok.encode(self.training))
            char = CharTokenizer.from_text("abc")
            char.save(path)
            self.assertEqual(load_tokenizer(path).encode("cab"), char.encode("cab"))

    def test_explicit_family_split_is_never_shuffled_or_refitted(self):
        train = "  train one\n\ntrain two\n"
        val = "  heldout only 🙂\n"
        with patch("data.group_split", side_effect=AssertionError("explicit partitions must not be split")):
            tok = build_tokenizer(train + val, kind="bpe", vocab_size=256, training_text=train)
            corpus = Corpus(train, tok, "cpu", validation_text=val, seed=91, val_frac=0.75)
        self.assertEqual(tok.training["text_sha256"], hashlib.sha256(train.encode()).hexdigest())
        self.assertEqual(corpus.split_mode, "explicit")
        self.assertEqual(tok.decode(corpus.train.tolist()), train)
        self.assertEqual(tok.decode(corpus.val.tolist()), val)
        self.assertEqual((corpus.train_text, corpus.val_text), (train, val))

    def test_bpe_model_checkpoint_loads_and_keeps_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            cfg = GPTConfig(vocab_size=self.tok.vocab_size, block_size=32, n_layer=1, n_head=2, n_embd=16)
            model = GPT(cfg)
            torch.save({"config": cfg.__dict__, "model": model.state_dict()}, path / "ckpt.pt")
            self.tok.save(path / "tokenizer.json")
            loaded, tok, _ = checkpoint.load_checkpoint(path, device="cpu")
            text = checkpoint.sample(loaded, tok, "x := Σ;\n", tokens=2)
            self.assertTrue(text.startswith("x := Σ;\n"))

    def test_bad_vocabulary_request_and_unknown_format_fail(self):
        with self.assertRaises(ValueError):
            BPETokenizer.from_text("abc", vocab_size=255)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tokenizer.json"
            path.write_text(json.dumps({"version": 999}))
            with self.assertRaises(ValueError):
                load_tokenizer(path)


if __name__ == "__main__":
    unittest.main()
