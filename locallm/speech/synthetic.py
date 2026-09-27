"""synthetic.py — a handful of synthetic utterances, no download, no microphone.

Generates short WAV files, each a distinct tone plus a little seeded noise,
paired with a distinct short label, and a manifest.jsonl pointing at them.
The point is not phonetic realism: it is exercising the *real* code path
(``dataset.load_wav`` reading real 16-bit PCM off disk, real STFT-based
log-mel features, the real ``AcousticModel`` and ``F.ctc_loss``, greedy
decoding, WER/CER) on data that a laptop CPU can memorize in seconds,
so ``test_speech_ctc.py`` measures the pipeline rather than trusting it.
A model that cannot drive these few, easily-separable utterances to zero
error could not possibly be trusted on real speech; passing this is a floor,
not a claim about LibriSpeech.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import torch

from .dataset import save_wav
from .text import CTCVocab

# Short, alphabet-only labels, each mapped to its own tone so the acoustic
# pattern is trivially separable from the others; kept short so a handful of
# frames per utterance is already enough context for CTC to align against.
_LABELS = ("go", "stop", "cat", "dog", "red", "blue", "up", "down")


def _tone(frequency_hz: float, duration_s: float, sample_rate: int, seed: int) -> torch.Tensor:
    n = int(duration_s * sample_rate)
    t = torch.arange(n, dtype=torch.float32) / sample_rate
    tone = 0.5 * torch.sin(2 * math.pi * frequency_hz * t)
    noise = torch.Generator().manual_seed(seed)
    tone = tone + 0.02 * torch.randn(n, generator=noise)
    fade = min(n // 10, sample_rate // 100)  # ~10 ms or 10% of the clip, whichever is shorter
    if fade > 1:
        ramp = torch.linspace(0.0, 1.0, fade)
        tone[:fade] *= ramp
        tone[-fade:] *= ramp.flip(0)
    return tone.clamp(-1.0, 1.0)


@dataclass
class SmokeSet:
    manifest_path: Path
    directory: Path
    labels: tuple[str, ...]


def build_smoke_manifest(out_dir: str | Path, *, n: int = 6, sample_rate: int = 16_000,
                         duration_s: float = 0.8, seed: int = 0,
                         vocab: CTCVocab | None = None) -> SmokeSet:
    """Writes ``n`` utterances (at most ``len(_LABELS)``) and their manifest
    under ``out_dir``, and returns where they landed."""
    if not 1 <= n <= len(_LABELS):
        raise ValueError(f"n must be between 1 and {len(_LABELS)}")
    vocab = vocab or CTCVocab()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    labels = _LABELS[:n]
    rows = []
    for i, label in enumerate(labels):
        text = vocab.normalize(label)
        if not text:
            raise ValueError(f"label {label!r} normalized to empty text")
        frequency = 220.0 * (2 ** (i / 3))     # spread across roughly 220 Hz - 1.4 kHz
        waveform = _tone(frequency, duration_s, sample_rate, seed=seed * 1000 + i)
        path = out_dir / f"utt{i:02d}.wav"
        save_wav(path, waveform, sample_rate)
        rows.append({"audio": str(path), "text": text})
    manifest_path = out_dir / "manifest.jsonl"
    manifest_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return SmokeSet(manifest_path, out_dir, labels)
