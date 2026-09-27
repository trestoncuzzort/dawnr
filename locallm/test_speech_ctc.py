"""Tests for speech/ctc_model.py, including the CPU smoke test that overfits
a handful of synthetic utterances -- the measurement predicted, before this
file's smoke test was run and reported, in
PREDICT-speech-ctc-smoke-2026-09-27.md (see FINDINGS-speech-ctc-smoke-2026-09-27.md
for the outcome). CPU only, needs torch, seconds to run; see the FINDINGS
file for the measured time and loss curve.
"""
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

from speech.ctc_decode import decode_text  # noqa: E402
from speech.ctc_model import AcousticConfig, AcousticModel  # noqa: E402
from speech.dataset import ManifestDataset, collate  # noqa: E402
from speech.metrics import cer, wer  # noqa: E402
from speech.synthetic import build_smoke_manifest  # noqa: E402
from speech.text import CTCVocab  # noqa: E402


def config(**updates):
    values = dict(n_mels=40, vocab_size=CTCVocab().vocab_size,
                 conv_channels=16, rnn_hidden=16, rnn_layers=1, dropout=0.0)
    values.update(updates)
    return AcousticConfig(**values)


class AcousticConfigTest(unittest.TestCase):
    def test_rejects_nonpositive_dims(self):
        for field in ("n_mels", "conv_channels", "rnn_hidden", "rnn_layers"):
            with self.assertRaises(ValueError):
                config(**{field: 0})

    def test_rejects_vocab_smaller_than_blank_plus_one_symbol(self):
        with self.assertRaises(ValueError):
            config(vocab_size=1)

    def test_rejects_even_conv_kernel(self):
        with self.assertRaises(ValueError):
            config(conv_kernel=4)

    def test_output_length_formula(self):
        # kernel 5, stride 2, padding 2 (the default): (L + 4 - 5)//2 + 1
        cfg = config()
        for length in (1, 2, 5, 16, 101, 200):
            expected = (length + 2 * cfg.conv_padding - cfg.conv_kernel) // cfg.conv_stride + 1
            self.assertEqual(cfg.output_length(length), expected)
        self.assertGreaterEqual(cfg.output_length(1), 1)   # never zero or negative


class AcousticModelForwardTest(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(11)

    def test_rejects_malformed_input(self):
        model = AcousticModel(config())
        with self.assertRaises(ValueError):
            model(torch.zeros(2, 5), torch.tensor([5, 5]))                    # not 3-D
        with self.assertRaises(ValueError):
            model(torch.zeros(2, 5, 40), torch.tensor([5]))                   # wrong length count
        with self.assertRaises(ValueError):
            model(torch.zeros(2, 5, 40), torch.tensor([0, 5]))                # zero length
        with self.assertRaises(ValueError):
            model(torch.zeros(2, 5, 40), torch.tensor([6, 5]))                # exceeds padded T

    def test_output_shapes_and_finite_loss_with_gradient(self):
        model = AcousticModel(config())
        features = torch.randn(3, 60, 40)
        lengths = torch.tensor([60, 45, 20])
        targets = torch.tensor([1, 2, 3, 1, 2, 3])
        target_lengths = torch.tensor([2, 2, 2])
        log_probs, out_lengths, loss = model(features, lengths, targets=targets,
                                             target_lengths=target_lengths)
        self.assertEqual(log_probs.shape[0], 3)
        self.assertEqual(log_probs.shape[2], config().vocab_size)
        self.assertEqual(out_lengths.tolist(),
                         [model.config.output_length(n) for n in (60, 45, 20)])
        self.assertTrue(torch.isfinite(loss).item())
        loss.backward()
        for name, p in model.named_parameters():
            self.assertIsNotNone(p.grad, name)
            self.assertTrue(torch.isfinite(p.grad).all(), name)

    def test_log_probs_sum_to_one_per_frame(self):
        model = AcousticModel(config()).eval()
        with torch.no_grad():
            log_probs, out_lengths, _ = model(torch.randn(1, 30, 40), torch.tensor([30]))
        total = log_probs[0, : out_lengths[0]].exp().sum(dim=-1)
        torch.testing.assert_close(total, torch.ones_like(total), atol=1e-4, rtol=0)

    def test_no_loss_without_targets(self):
        model = AcousticModel(config()).eval()
        with torch.no_grad():
            _, _, loss = model(torch.randn(1, 30, 40), torch.tensor([30]))
        self.assertIsNone(loss)

    def test_padded_batch_matches_unpadded_single_example(self):
        # The frames a shorter row's padding adds must not change that row's
        # own logits at the positions its output_length actually covers --
        # otherwise a padded batch would train a different function than an
        # unpadded one.
        model = AcousticModel(config()).eval()
        long_features = torch.randn(1, 60, 40)
        short_features = long_features[:, :20]
        padded = torch.zeros(2, 60, 40)
        padded[0] = long_features[0]
        padded[1, :20] = short_features[0]
        with torch.no_grad():
            lp_batch, ol_batch, _ = model(padded, torch.tensor([60, 20]))
            lp_single, ol_single, _ = model(short_features, torch.tensor([20]))
        n = ol_single[0]
        torch.testing.assert_close(lp_batch[1, :n], lp_single[0, :n], atol=1e-5, rtol=1e-4)


class GreedyDecodeConsistencyTest(unittest.TestCase):
    def test_untrained_model_decodes_without_crashing(self):
        torch.manual_seed(3)
        model = AcousticModel(config()).eval()
        with torch.no_grad():
            log_probs, out_lengths, _ = model(torch.randn(2, 40, 40), torch.tensor([40, 25]))
        texts = decode_text(log_probs, out_lengths, CTCVocab())
        self.assertEqual(len(texts), 2)
        self.assertTrue(all(isinstance(t, str) for t in texts))


class SmokeTestOverfitsAHandfulOfUtterances(unittest.TestCase):
    """The measured claim: this from-scratch CTC acoustic model can drive
    training loss and word/character error rate to (near) zero on a handful
    of short, easily-separable synthetic utterances, on CPU, in well under a
    minute. This is a floor, not a claim about real speech (synthetic.py's
    module docstring says so); it exists to catch a broken pipeline -- wrong
    CTC alignment, a decoder that never collapses, a feature extractor that
    washes out every utterance to the same features -- before any real
    corpus or GPU time is spent. See PREDICT-2026-09-27-speech-ctc-smoke.md
    for the prediction this test was written to check, and
    FINDINGS-2026-09-27-speech-ctc-smoke.md for the measured outcome.
    """

    def test_overfits_six_synthetic_utterances(self):
        torch.manual_seed(0)
        vocab = CTCVocab()
        with tempfile.TemporaryDirectory() as tmp:
            smoke = build_smoke_manifest(tmp, n=6, sample_rate=16_000, duration_s=0.8, seed=0)
            dataset = ManifestDataset(smoke.manifest_path, vocab)
            batch = collate([dataset[i] for i in range(len(dataset))])
            references = [dataset[i].text for i in range(len(dataset))]

            model = AcousticModel(config(conv_channels=64, rnn_hidden=64, rnn_layers=2))
            optimizer = torch.optim.Adam(model.parameters(), lr=3e-3)

            started = time.time()
            losses = []
            for _ in range(400):
                model.train()
                optimizer.zero_grad()
                _, _, loss = model(batch["features"], batch["feature_lengths"],
                                   targets=batch["targets"], target_lengths=batch["target_lengths"])
                self.assertTrue(torch.isfinite(loss).item(), "CTC loss must stay finite every step")
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                optimizer.step()
                losses.append(loss.item())
            elapsed = time.time() - started

            model.eval()
            with torch.no_grad():
                log_probs, out_lengths, _ = model(batch["features"], batch["feature_lengths"])
            hypotheses = decode_text(log_probs, out_lengths, vocab)

        mean_wer = sum(wer(r, h) for r, h in zip(references, hypotheses)) / len(references)
        mean_cer = sum(cer(r, h) for r, h in zip(references, hypotheses)) / len(references)
        print(f"\n  [speech smoke] {elapsed:.1f}s, loss {losses[0]:.2f} -> {losses[-1]:.4f}, "
             f"meanWER {mean_wer:.3f}, meanCER {mean_cer:.3f}, hyps {hypotheses}")

        self.assertLess(losses[-1], 0.05, "final CTC loss did not collapse toward zero")
        self.assertEqual(mean_wer, 0.0, f"expected exact memorization, got {list(zip(references, hypotheses))}")
        self.assertEqual(mean_cer, 0.0)
        self.assertLess(elapsed, 60.0, "the smoke test must stay a smoke test, not a training run")


if __name__ == "__main__":
    unittest.main()
