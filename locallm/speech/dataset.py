"""dataset.py — a manifest of (audio path, transcript) to CTC-ready batches.

The manifest is one JSON object per line: ``{"audio": <path>, "text":
<transcript>}`` (an optional ``"duration"`` in seconds is carried through if
present but never required). ``prepare_manifest.py`` writes this format from
a downloaded corpus; ``synthetic.py`` writes it for the CPU smoke test's
generated utterances; both are consumed the same way from here down, so the
model code never knows whether an utterance came from a real recording or a
synthetic tone.

Audio is read with the standard library's ``wave`` module: 16-bit PCM mono,
the format both LJSpeech ships natively (keithito.com/LJ-Speech-Dataset,
fetched 2026-09-27: "single-channel 16-bit PCM WAV") and the format
``prepare_manifest.py`` converts LibriSpeech's FLAC into on the lab before
any of this code sees it. Keeping the model-facing dataset to the narrowest,
simplest audio format on purpose means training and the smoke test never
depend on a FLAC/MP3 decoder being installed -- only the one-time,
lab-side preparation step does.
"""
from __future__ import annotations

import json
import wave
from dataclasses import dataclass
from pathlib import Path

import torch

from .audio_features import FeatureConfig, log_mel_spectrogram
from .text import CTCVocab


def read_manifest(path: str | Path) -> list[dict]:
    """One dict per nonblank line. Raises with the line number on malformed
    JSON or a missing ``audio``/``text`` field, rather than skipping a bad
    line silently and training on a manifest quietly shorter than it looks."""
    rows = []
    with open(path, encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: not valid JSON") from exc
            if "audio" not in row or "text" not in row:
                raise ValueError(f"{path}:{lineno}: needs both 'audio' and 'text'")
            rows.append(row)
    if not rows:
        raise ValueError(f"{path}: no utterances")
    return rows


def load_wav(path: str | Path) -> tuple[torch.Tensor, int]:
    """16-bit PCM WAV to a ``(num_samples,)`` float32 tensor in [-1, 1] plus
    its sample rate. Stereo is averaged to mono. Any other sample width is
    refused by name (the "refuse rather than mis-decode" rule ``ingest.py``
    applies to text encodings, applied here to audio): resampling or bit
    depth conversion belongs in ``prepare_manifest.py``, once, on the lab,
    not silently redone (and possibly done wrong) on every training read.
    """
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if width != 2:
        raise ValueError(f"{path}: {width * 8}-bit PCM is not supported; "
                         f"convert to 16-bit PCM first (prepare_manifest.py)")
    waveform = torch.frombuffer(bytearray(frames), dtype=torch.int16).to(torch.float32) / 32768.0
    if channels > 1:
        waveform = waveform.view(-1, channels).mean(dim=1)
    if waveform.numel() == 0:
        raise ValueError(f"{path}: zero-length audio")
    return waveform, rate


def save_wav(path: str | Path, waveform: torch.Tensor, sample_rate: int) -> None:
    """The write side of ``load_wav``: ``(num_samples,)`` float32 in [-1, 1]
    to 16-bit mono PCM WAV. Shared by ``synthetic.py`` (writes the smoke
    test's tones) and ``audio_io.py`` (writes what the microphone captured),
    so both take the same round trip through ``load_wav`` that training
    data does, rather than a second, unchecked audio path of their own."""
    if waveform.ndim != 1 or waveform.numel() == 0:
        raise ValueError("save_wav takes a nonempty 1-D waveform")
    ints = (waveform.clamp(-1.0, 1.0) * 32767.0).round().to(torch.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(ints.numpy().tobytes())


@dataclass
class SpeechExample:
    features: torch.Tensor   # (time, n_mels)
    target: torch.Tensor     # (target_length,) CTC ids, no blank
    text: str                # normalized transcript, for readable evaluation output


class ManifestDataset(torch.utils.data.Dataset):
    """Loads and featurizes lazily in ``__getitem__`` (audio is small per
    utterance but a full corpus is not: LibriSpeech train-clean-100 alone is
    100 hours), so a DataLoader's worker processes do the decoding in
    parallel instead of one process paying for all of it up front."""

    def __init__(self, manifest_path: str | Path, vocab: CTCVocab | None = None,
                 feature_config: FeatureConfig | None = None):
        self.rows = read_manifest(manifest_path)
        self.vocab = vocab or CTCVocab()
        self.feature_config = feature_config or FeatureConfig()

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> SpeechExample:
        row = self.rows[index]
        waveform, rate = load_wav(row["audio"])
        if rate != self.feature_config.sample_rate:
            raise ValueError(
                f"{row['audio']}: {rate} Hz, expected {self.feature_config.sample_rate} Hz "
                f"(resample in prepare_manifest.py, not silently here)")
        features = log_mel_spectrogram(waveform, self.feature_config)
        text = self.vocab.normalize(row["text"])
        if not text:
            raise ValueError(f"{row['audio']}: transcript is empty after normalization")
        target = torch.tensor(self.vocab.encode(text), dtype=torch.long)
        if target.numel() > self.feature_config.output_length(waveform.numel()):
            raise ValueError(
                f"{row['audio']}: transcript ({target.numel()} symbols) longer than the "
                f"audio has feature frames; CTC cannot align this pair")
        return SpeechExample(features, target, text)


def collate(batch: list[SpeechExample]) -> dict[str, torch.Tensor]:
    """Right-zero-pad ``features`` to the batch's longest; concatenate
    targets into CTC's 1-D packed form. Returns exactly the keyword names
    ``AcousticModel.forward`` and ``F.ctc_loss`` take, so a training loop is
    ``model(**collate(batch))``."""
    if not batch:
        raise ValueError("collate takes a nonempty batch")
    max_time = max(ex.features.size(0) for ex in batch)
    n_mels = batch[0].features.size(1)
    features = torch.zeros(len(batch), max_time, n_mels)
    feature_lengths = torch.zeros(len(batch), dtype=torch.long)
    for i, ex in enumerate(batch):
        t = ex.features.size(0)
        features[i, :t] = ex.features
        feature_lengths[i] = t
    targets = torch.cat([ex.target for ex in batch])
    target_lengths = torch.tensor([ex.target.numel() for ex in batch], dtype=torch.long)
    return dict(features=features, feature_lengths=feature_lengths,
               targets=targets, target_lengths=target_lengths)
