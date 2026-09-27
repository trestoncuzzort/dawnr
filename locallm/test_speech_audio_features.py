"""Tests for speech/audio_features.py. CPU only, needs torch."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

from speech.audio_features import FeatureConfig, log_mel_spectrogram  # noqa: E402


class FeatureConfigTest(unittest.TestCase):
    def test_rejects_nonpositive_fields(self):
        for field in ("sample_rate", "n_mels", "hop_length"):
            with self.assertRaises(ValueError):
                FeatureConfig(**{field: 0})
        with self.assertRaises(ValueError):
            FeatureConfig(n_fft=1)   # n_fft must be >= 2

    def test_fmax_must_exceed_fmin(self):
        with self.assertRaises(ValueError):
            FeatureConfig(fmin=100.0, fmax=100.0)

    def test_output_length_matches_stft_center_framing(self):
        cfg = FeatureConfig(hop_length=160)
        # torch.stft with center=True: floor(num_samples / hop_length) + 1 frames.
        self.assertEqual(cfg.output_length(16_000), 16_000 // 160 + 1)
        self.assertEqual(cfg.output_length(1), 1)


class LogMelSpectrogramTest(unittest.TestCase):
    def setUp(self):
        self.cfg = FeatureConfig(sample_rate=16_000, n_mels=40, n_fft=400, hop_length=160)

    def test_rejects_batched_or_empty_input(self):
        with self.assertRaises(ValueError):
            log_mel_spectrogram(torch.zeros(2, 16_000), self.cfg)
        with self.assertRaises(ValueError):
            log_mel_spectrogram(torch.zeros(0), self.cfg)

    def test_shape_matches_output_length_and_n_mels(self):
        waveform = torch.zeros(16_000)
        features = log_mel_spectrogram(waveform, self.cfg)
        self.assertEqual(features.shape, (self.cfg.output_length(16_000), 40))

    def test_silence_is_finite_not_nan_or_inf(self):
        # log(0 + eps) must never become -inf and poison a downstream matmul.
        features = log_mel_spectrogram(torch.zeros(4_000), self.cfg)
        self.assertTrue(torch.isfinite(features).all())

    def test_two_different_tones_give_different_features(self):
        t = torch.arange(4_000, dtype=torch.float32) / self.cfg.sample_rate
        low = log_mel_spectrogram(0.5 * torch.sin(2 * math.pi * 220.0 * t), self.cfg)
        high = log_mel_spectrogram(0.5 * torch.sin(2 * math.pi * 2000.0 * t), self.cfg)
        self.assertGreater((low - high).abs().mean().item(), 0.1)

    def test_a_pure_tone_peaks_near_its_own_mel_bin(self):
        # A weak but real correctness check on the filterbank itself, not just
        # "it runs": a 1 kHz tone's energy should peak closer to the mel bin
        # nearest 1 kHz than at the very top of the 8 kHz (Nyquist) range.
        t = torch.arange(4_000, dtype=torch.float32) / self.cfg.sample_rate
        tone = 0.8 * torch.sin(2 * math.pi * 1_000.0 * t)
        features = log_mel_spectrogram(tone, self.cfg)
        mean_energy = features[2:-2].mean(dim=0)             # drop edge frames (STFT padding)
        peak_bin = int(mean_energy.argmax())
        self.assertLess(peak_bin, self.cfg.n_mels * 3 // 4)  # nowhere near the top of the band

    def test_caching_does_not_leak_across_different_configs(self):
        # _mel_filterbank is lru_cache'd by its exact arguments; two configs
        # that differ only in n_mels must not collide on that cache key.
        a = log_mel_spectrogram(torch.zeros(4_000), FeatureConfig(n_mels=20))
        b = log_mel_spectrogram(torch.zeros(4_000), FeatureConfig(n_mels=40))
        self.assertEqual(a.shape[1], 20)
        self.assertEqual(b.shape[1], 40)


if __name__ == "__main__":
    unittest.main()
