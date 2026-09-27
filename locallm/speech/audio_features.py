"""audio_features.py — waveform to log-mel spectrogram, torch only.

No torchaudio, no librosa: the front end every acoustic model here reads is
built from ``torch.stft`` plus a mel filterbank computed once and cached, so
training and the CPU smoke test need nothing beyond the dependency locallm
already has. The pipeline (frame the signal, take the power spectrum, apply
a triangular mel filterbank, take the log) and the HTK mel-scale formula
below are the standard recipe read from "Mel Frequency Cepstral Coefficient
(MFCC) tutorial" (practicalcryptography.com/miscellaneous/machine-learning/
guide-mel-frequency-cepstral-coefficients-mfccs, fetched 2026-09-27). Unlike
that tutorial's MFCCs, this stops at log-mel energies with no DCT and no
liftering: a neural acoustic model consumes the (correlated) filterbank
energies directly, which is what Deep Speech 2 (arXiv:1512.02595) and every
later CTC/attention acoustic model does -- the DCT step of classic MFCCs
exists to decorrelate features for an HMM/GMM's diagonal covariance, which is
not a constraint a neural network has.
"""
from __future__ import annotations

import functools
import math
from dataclasses import dataclass

import torch


@dataclass
class FeatureConfig:
    sample_rate: int = 16_000
    n_mels: int = 40
    n_fft: int = 400          # 25 ms at 16 kHz
    hop_length: int = 160     # 10 ms at 16 kHz
    fmin: float = 0.0
    fmax: float | None = None  # None -> Nyquist

    def __post_init__(self):
        if self.sample_rate < 1 or self.n_mels < 1 or self.n_fft < 2 or self.hop_length < 1:
            raise ValueError("sample_rate, n_mels, n_fft and hop_length must be positive")
        if self.fmin < 0 or (self.fmax is not None and self.fmax <= self.fmin):
            raise ValueError("fmax must be greater than fmin")

    def output_length(self, num_samples: int) -> int:
        """Frame count ``log_mel_spectrogram`` returns for a waveform this long,
        matching ``torch.stft``'s ``center=True`` framing (pads by n_fft // 2 on
        each side, so even a waveform shorter than n_fft yields one frame)."""
        if num_samples < 1:
            raise ValueError("num_samples must be positive")
        return num_samples // self.hop_length + 1


def _hz_to_mel(hz: float) -> float:
    return 2595.0 * math.log10(1.0 + hz / 700.0)


def _mel_to_hz(mel):
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)


@functools.lru_cache(maxsize=8)
def _mel_filterbank(n_fft: int, n_mels: int, sample_rate: int, fmin: float,
                     fmax: float | None) -> torch.Tensor:
    """(n_mels, n_fft // 2 + 1) triangular filterbank, each filter normalized
    to unit peak. Cached: every utterance with the same FeatureConfig reuses
    the same matrix instead of rebuilding it per call."""
    fmax = fmax if fmax is not None else sample_rate / 2
    n_bins = n_fft // 2 + 1
    mel_points = torch.linspace(_hz_to_mel(fmin), _hz_to_mel(fmax), n_mels + 2)
    hz_points = torch.tensor([_mel_to_hz(m.item()) for m in mel_points])
    bin_points = torch.floor((n_fft + 1) * hz_points / sample_rate).long().clamp_(0, n_bins - 1)

    bank = torch.zeros(n_mels, n_bins)
    for m in range(n_mels):
        left, center, right = bin_points[m].item(), bin_points[m + 1].item(), bin_points[m + 2].item()
        if center == left:
            center += 1  # a filter this narrow still gets one nonzero bin, never a silent row
        if right == center:
            right += 1
        for k in range(left, min(center, n_bins)):
            bank[m, k] = (k - left) / (center - left)
        for k in range(center, min(right, n_bins)):
            bank[m, k] = (right - k) / (right - center)
    return bank


def log_mel_spectrogram(waveform: torch.Tensor, config: FeatureConfig = FeatureConfig(),
                        *, eps: float = 1e-6) -> torch.Tensor:
    """One utterance, ``(num_samples,)`` float32 in roughly [-1, 1], to
    ``(time, n_mels)`` log filterbank energies. Batched utterances are
    handled by the caller (``dataset.py``'s collate function), each through
    this same call, then padded across the batch: audio lengths vary per
    utterance, and padding raw waveforms to a common length before framing
    would let the padded tail's silence still contribute an extra frame or
    two of near-zero energy depending on where the pad boundary falls inside
    a frame, so features are computed on the true length first.
    """
    if waveform.ndim != 1 or waveform.numel() == 0:
        raise ValueError("log_mel_spectrogram takes one nonempty 1-D waveform")
    window = torch.hann_window(config.n_fft, device=waveform.device, dtype=waveform.dtype)
    # pad_mode="constant" (zero-padding), not torch.stft's own default
    # "reflect": reflection padding requires the pad width (n_fft // 2) to be
    # smaller than the waveform itself, so a waveform shorter than half a
    # frame -- a clipped recording, or a manifest bug -- would crash inside
    # torch.stft with an internal padding error instead of ever reaching this
    # module's own checks. Zero-padding has no such minimum length.
    spectrum = torch.stft(waveform, n_fft=config.n_fft, hop_length=config.hop_length,
                          win_length=config.n_fft, window=window, center=True,
                          pad_mode="constant", return_complex=True)   # (n_fft//2+1, time)
    power = spectrum.real.square() + spectrum.imag.square()
    bank = _mel_filterbank(config.n_fft, config.n_mels, config.sample_rate,
                           config.fmin, config.fmax).to(power.dtype)
    mel = bank @ power                                                # (n_mels, time)
    return torch.log(mel.clamp_min(eps)).transpose(0, 1).contiguous()  # (time, n_mels)
