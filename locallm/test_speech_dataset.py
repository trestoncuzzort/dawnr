"""Tests for speech/dataset.py: manifest parsing, real WAV file I/O through
the standard library's wave module, and CTC batch collation. CPU, needs torch.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

from speech.dataset import ManifestDataset, collate, load_wav, read_manifest, save_wav  # noqa: E402
from speech.synthetic import build_smoke_manifest  # noqa: E402
from speech.text import CTCVocab  # noqa: E402


class ReadManifestTest(unittest.TestCase):
    def test_reads_one_row_per_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.jsonl"
            path.write_text('{"audio": "a.wav", "text": "hi"}\n'
                            '{"audio": "b.wav", "text": "there"}\n', encoding="utf-8")
            rows = read_manifest(path)
        self.assertEqual(rows, [{"audio": "a.wav", "text": "hi"}, {"audio": "b.wav", "text": "there"}])

    def test_blank_lines_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.jsonl"
            path.write_text('{"audio": "a.wav", "text": "hi"}\n\n\n', encoding="utf-8")
            self.assertEqual(len(read_manifest(path)), 1)

    def test_malformed_json_names_the_line_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.jsonl"
            path.write_text('{"audio": "a.wav", "text": "hi"}\nnot json\n', encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                read_manifest(path)
            self.assertIn(":2:", str(ctx.exception))

    def test_missing_field_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.jsonl"
            path.write_text('{"audio": "a.wav"}\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                read_manifest(path)

    def test_empty_manifest_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.jsonl"
            path.write_text("", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_manifest(path)


class WavRoundTripTest(unittest.TestCase):
    def test_save_then_load_matches_within_int16_quantization(self):
        waveform = 0.5 * torch.sin(torch.linspace(0, 100, 4_000))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.wav"
            save_wav(path, waveform, 16_000)
            loaded, rate = load_wav(path)
        self.assertEqual(rate, 16_000)
        self.assertEqual(loaded.numel(), waveform.numel())
        self.assertTrue(torch.allclose(waveform, loaded, atol=2.0 / 32768))

    def test_stereo_is_averaged_to_mono(self):
        import wave
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stereo.wav"
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(2)
                handle.setsampwidth(2)
                handle.setframerate(16_000)
                # left channel max positive, right channel max negative -> mono mean ~0
                handle.writeframes((32767).to_bytes(2, "little", signed=True) +
                                   (-32768).to_bytes(2, "little", signed=True))
            waveform, rate = load_wav(path)
        self.assertEqual(rate, 16_000)
        self.assertEqual(waveform.numel(), 1)
        self.assertAlmostEqual(waveform.item(), 0.0, places=3)

    def test_non_16_bit_is_refused_by_name(self):
        import wave
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "eight_bit.wav"
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(1)   # 8-bit, unsupported
                handle.setframerate(16_000)
                handle.writeframes(bytes([128, 130, 126]))
            with self.assertRaises(ValueError) as ctx:
                load_wav(path)
        self.assertIn("16-bit", str(ctx.exception))


class ManifestDatasetTest(unittest.TestCase):
    def test_loads_features_and_normalized_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            smoke = build_smoke_manifest(tmp, n=3, sample_rate=16_000, duration_s=0.4)
            ds = ManifestDataset(smoke.manifest_path)
            self.assertEqual(len(ds), 3)
            example = ds[0]
            self.assertEqual(example.text, smoke.labels[0])
            self.assertEqual(example.features.shape[1], 40)     # default n_mels
            self.assertGreater(example.target.numel(), 0)

    def test_wrong_sample_rate_is_refused_not_silently_resampled(self):
        vocab = CTCVocab()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            smoke = build_smoke_manifest(tmp, n=1, sample_rate=8_000, duration_s=0.4)
            from speech.audio_features import FeatureConfig
            ds = ManifestDataset(smoke.manifest_path, vocab, FeatureConfig(sample_rate=16_000))
            with self.assertRaises(ValueError) as ctx:
                ds[0]
            self.assertIn("resample", str(ctx.exception))

    def test_transcript_longer_than_frames_is_refused(self):
        vocab = CTCVocab()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            import torch as _torch
            from speech.dataset import save_wav
            save_wav(tmp / "tiny.wav", _torch.zeros(10), 16_000)   # far too short
            manifest = tmp / "m.jsonl"
            manifest.write_text(json.dumps({"audio": str(tmp / "tiny.wav"),
                                           "text": "a rather long sentence indeed"}) + "\n",
                               encoding="utf-8")
            ds = ManifestDataset(manifest, vocab)
            with self.assertRaises(ValueError):
                ds[0]


class CollateTest(unittest.TestCase):
    def test_pads_features_and_packs_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            smoke = build_smoke_manifest(tmp, n=3, sample_rate=16_000, duration_s=0.8)
            ds = ManifestDataset(smoke.manifest_path)
            batch = collate([ds[i] for i in range(len(ds))])
        max_t = int(batch["feature_lengths"].max())
        self.assertEqual(batch["features"].shape, (3, max_t, 40))
        self.assertEqual(batch["feature_lengths"].numel(), 3)
        self.assertEqual(batch["targets"].numel(), int(batch["target_lengths"].sum()))
        # rows shorter than max_t are zero-padded, not garbage
        for i in range(3):
            t = int(batch["feature_lengths"][i])
            if t < max_t:
                self.assertTrue(torch.equal(batch["features"][i, t:], torch.zeros(max_t - t, 40)))

    def test_refuses_empty_batch(self):
        with self.assertRaises(ValueError):
            collate([])


if __name__ == "__main__":
    unittest.main()
