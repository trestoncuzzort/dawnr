"""A tokenizer with the right size can still assign every token the wrong ID."""
import json
from pathlib import Path
import tempfile
import unittest

import torch

import checkpoint
from data import BPETokenizer, CharTokenizer, load_tokenizer, tokenizer_fingerprint
from model import GPT, GPTConfig


def save_checkpoint(path, tokenizer, fingerprint=True):
    cfg = GPTConfig(vocab_size=tokenizer.vocab_size, block_size=16,
                    n_layer=1, n_head=2, n_embd=8)
    model = GPT(cfg)
    payload = {"config": cfg.__dict__, "model": model.state_dict()}
    if fingerprint:
        payload["tokenizer_fingerprint"] = tokenizer_fingerprint(tokenizer)
    torch.save(payload, path / "ckpt.pt")
    tokenizer.save(path / "tokenizer.json")


class TokenizerIntegrityTests(unittest.TestCase):
    def test_matching_character_ids_load(self):
        tok = CharTokenizer(["a", "b", "c"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            save_checkpoint(path, tok)
            _, restored, _ = checkpoint.load_checkpoint(path, device="cpu")
            self.assertEqual(restored.encode("cab"), tok.encode("cab"))

    def test_same_size_permuted_character_ids_are_rejected(self):
        original = CharTokenizer(["a", "b", "c"])
        permuted = CharTokenizer(["b", "a", "c"])
        self.assertEqual(original.vocab_size, permuted.vocab_size)
        self.assertNotEqual(original.encode("ab"), permuted.encode("ab"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            save_checkpoint(path, original)
            permuted.save(path / "tokenizer.json")
            with self.assertRaisesRegex(ValueError, "tokenizer fingerprint"):
                checkpoint.load_checkpoint(path, device="cpu")

    def test_legacy_checkpoint_without_fingerprint_still_loads(self):
        tok = CharTokenizer(["a", "b", "c"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            save_checkpoint(path, tok, fingerprint=False)
            _, restored, _ = checkpoint.load_checkpoint(path, device="cpu")
            self.assertEqual(restored.encode("cab"), tok.encode("cab"))

    def test_bpe_fingerprint_roundtrip_ignores_training_metadata(self):
        text = "task add(x: int) returns (r: int) { r := x + 1; }\n" * 8
        tok = BPETokenizer.from_text(text, vocab_size=300)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            save_checkpoint(path, tok)
            original_fingerprint = tokenizer_fingerprint(tok)
            payload = json.loads((path / "tokenizer.json").read_text())
            payload["training"] = {"description": "same encoding, different metadata"}
            (path / "tokenizer.json").write_text(json.dumps(payload, sort_keys=True, indent=2))
            _, restored, _ = checkpoint.load_checkpoint(path, device="cpu")
            self.assertEqual(tokenizer_fingerprint(restored), original_fingerprint)
            self.assertEqual(restored.encode(text), tok.encode(text))
            self.assertEqual(restored.decode(restored.encode("Σ🙂\t\r\n")), "Σ🙂\t\r\n")

    def test_bpe_encoding_configuration_changes_fingerprint(self):
        from tokenizers import pre_tokenizers
        text = "abc abc abc abc"
        tok = BPETokenizer.from_text(text, vocab_size=270)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tokenizer.json"
            tok.save(path)
            modified = load_tokenizer(path)
            modified.backend.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=True)
            self.assertEqual(tok.vocab_size, modified.vocab_size)
            self.assertNotEqual(tok.encode("abc"), modified.encode("abc"))
            self.assertNotEqual(tokenizer_fingerprint(tok), tokenizer_fingerprint(modified))


if __name__ == "__main__":
    unittest.main()
