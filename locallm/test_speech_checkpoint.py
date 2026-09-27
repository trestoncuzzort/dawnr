"""Tests for speech/checkpoint.py: save/load round trip and the alphabet
consistency check, mirroring locallm/checkpoint.py's own tests for the GPT
checkpoint. CPU, needs torch."""
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

from speech.checkpoint import load_checkpoint, save_checkpoint  # noqa: E402
from speech.ctc_model import AcousticConfig, AcousticModel  # noqa: E402
from speech.text import CTCVocab  # noqa: E402


class CheckpointRoundTripTest(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(5)
        self.config = AcousticConfig(n_mels=40, vocab_size=CTCVocab().vocab_size,
                                     conv_channels=8, rnn_hidden=8, rnn_layers=1)
        self.model = AcousticModel(self.config).eval()

    def test_round_trip_reproduces_logits_exactly(self):
        features = torch.randn(2, 30, 40)
        lengths = torch.tensor([30, 18])
        with torch.no_grad():
            expected, expected_lengths, _ = self.model(features, lengths)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "acoustic.pt"
            save_checkpoint(path, self.model)
            loaded, vocab, config = load_checkpoint(path)
        self.assertEqual(asdict(config), asdict(self.config))
        self.assertFalse(loaded.training)                      # load_checkpoint leaves eval mode
        with torch.no_grad():
            actual, actual_lengths, _ = loaded(features, lengths)
        self.assertTrue(torch.equal(actual, expected))
        self.assertTrue(torch.equal(actual_lengths, expected_lengths))
        self.assertEqual(vocab.symbols, CTCVocab().symbols)

    def test_mismatched_alphabet_is_refused_not_silently_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "acoustic.pt"
            save_checkpoint(path, self.model)
            checkpoint_dict = torch.load(path, weights_only=True)
            checkpoint_dict["vocab_symbols"] = ["only", "these", "three"]
            torch.save(checkpoint_dict, path)
            with self.assertRaises(ValueError) as ctx:
                load_checkpoint(path)
        self.assertIn("alphabet", str(ctx.exception))

    def test_checkpoint_is_weights_only_loadable(self):
        # The same safety property locallm/checkpoint.py relies on: no
        # arbitrary object graph, just tensors and config primitives, so
        # `torch.load(..., weights_only=True)` (the call load_checkpoint
        # itself makes) never needs to execute unpickled code.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "acoustic.pt"
            save_checkpoint(path, self.model)
            raw = torch.load(path, map_location="cpu", weights_only=True)
        self.assertEqual(set(raw), {"config", "model", "vocab_symbols"})
        self.assertIsInstance(raw["config"], dict)


if __name__ == "__main__":
    unittest.main()
