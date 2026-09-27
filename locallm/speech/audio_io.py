"""audio_io.py — microphone in, speaker out. An optional dependency, lazily
imported, exactly like ``tkinterdnd2`` in home.py and ``charset_normalizer``
in ingest.py: importing this whole package must not require it, so it is
never imported at module scope, only inside the two functions that need it.

python-sounddevice (MIT; PortAudio bindings; NumPy arrays in and out;
blocking ``rec()``/``play()``; docs at python-sounddevice.readthedocs.io,
fetched 2026-09-27) was chosen over PyAudio for the reason given in the
research receipt for this topic: it needs no compiled C-extension build step
of its own beyond the PortAudio shared library, which is friendlier on
Windows, and its blocking calls match a push-to-talk button directly. See
DAWNR-SPEECH.md's "hearing and speaking in the Tk app" section for the full
plan this implements the input/output half of; ``chat_bridge.py`` in this
package is where a chat window would wire a button to these two functions.

Nothing here grants itself anything: opening a microphone stream still goes
through whatever OS permission prompt or ``dawnr_harness`` tool policy calls
it, the same as any other tool. This module is the mechanism, not the
policy.
"""
from __future__ import annotations

import torch

INSTALL_HINT = "pip install sounddevice"


def _missing(exc: ImportError) -> RuntimeError:
    return RuntimeError(
        f"audio needs the optional 'sounddevice' package ({INSTALL_HINT}); {exc}")


def record(seconds: float, sample_rate: int = 16_000) -> torch.Tensor:
    """Blocking mono recording, returned the same way ``dataset.load_wav``
    returns audio: a ``(num_samples,)`` float32 tensor in [-1, 1], so a
    caller can hand it straight to ``audio_features.log_mel_spectrogram``."""
    if seconds <= 0 or not torch.isfinite(torch.tensor(float(seconds))):
        raise ValueError("seconds must be a finite positive number")
    if sample_rate < 1:
        raise ValueError("sample_rate must be positive")
    try:
        import sounddevice as sd                                   # noqa: PLC0415
    except ImportError as exc:
        raise _missing(exc) from exc
    frames = sd.rec(int(round(seconds * sample_rate)), samplerate=sample_rate,
                    channels=1, dtype="float32")
    sd.wait()
    return torch.from_numpy(frames[:, 0]).clone()


def play(waveform: torch.Tensor, sample_rate: int = 16_000) -> None:
    """Blocking playback of a ``(num_samples,)`` float32 waveform in
    [-1, 1] -- the format ``dataset.load_wav`` and ``record`` both use, so a
    round trip is always ``play(record(seconds), sample_rate)``."""
    if waveform.ndim != 1 or waveform.numel() == 0:
        raise ValueError("play takes a nonempty 1-D waveform")
    if sample_rate < 1:
        raise ValueError("sample_rate must be positive")
    try:
        import sounddevice as sd                                   # noqa: PLC0415
    except ImportError as exc:
        raise _missing(exc) from exc
    sd.play(waveform.detach().cpu().numpy(), samplerate=sample_rate)
    sd.wait()


def microphone_available() -> bool:
    """True when ``sounddevice`` is importable AND reports at least one
    input device. Used to grey out a mic button instead of letting it fail
    on click; never imported at module scope so checking this stays free
    when the optional dependency is absent."""
    try:
        import sounddevice as sd                                   # noqa: PLC0415
    except ImportError:
        return False
    try:
        return any(d["max_input_channels"] > 0 for d in sd.query_devices())
    except Exception:
        # PortAudio can raise its own error type here depending on host API
        # and OS; "no usable device" and "PortAudio is unhappy" look the
        # same to a caller deciding whether to show a mic button.
        return False
