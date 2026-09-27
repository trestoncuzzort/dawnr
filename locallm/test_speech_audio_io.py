"""Tests for speech/audio_io.py: validation runs even without the optional
dependency installed, and its absence is reported as a plain, actionable
RuntimeError rather than an ImportError leaking out of a function nobody
expected to touch imports. CPU, needs torch; does not need sounddevice or
a real audio device, and skips nothing when neither is present -- that is
the situation this module exists to handle cleanly.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

from speech import audio_io  # noqa: E402

try:
    import sounddevice as _sd  # noqa: F401
    _HAS_SOUNDDEVICE = True
except ImportError:
    _HAS_SOUNDDEVICE = False


class ValidationRunsWithoutTheOptionalDependencyTest(unittest.TestCase):
    """These checks must fire before ``import sounddevice`` is ever
    attempted, so a bad argument is reported as itself, not disguised as a
    missing package."""

    def test_record_rejects_nonpositive_seconds(self):
        with self.assertRaises(ValueError):
            audio_io.record(0, 16_000)
        with self.assertRaises(ValueError):
            audio_io.record(-1.0, 16_000)

    def test_record_rejects_bad_sample_rate(self):
        with self.assertRaises(ValueError):
            audio_io.record(1.0, 0)

    def test_play_rejects_empty_or_multi_dimensional_waveform(self):
        with self.assertRaises(ValueError):
            audio_io.play(torch.zeros(0), 16_000)
        with self.assertRaises(ValueError):
            audio_io.play(torch.zeros(2, 5), 16_000)

    def test_play_rejects_bad_sample_rate(self):
        with self.assertRaises(ValueError):
            audio_io.play(torch.zeros(5), 0)


@unittest.skipIf(_HAS_SOUNDDEVICE, "exercises the code path taken when the optional dependency is absent")
class MissingDependencyIsReportedPlainlyTest(unittest.TestCase):
    def test_record_names_the_install_command(self):
        with self.assertRaises(RuntimeError) as ctx:
            audio_io.record(1.0, 16_000)
        self.assertIn("pip install sounddevice", str(ctx.exception))

    def test_play_names_the_install_command(self):
        with self.assertRaises(RuntimeError) as ctx:
            audio_io.play(torch.zeros(160), 16_000)
        self.assertIn("pip install sounddevice", str(ctx.exception))

    def test_microphone_available_is_false_rather_than_raising(self):
        self.assertFalse(audio_io.microphone_available())


if __name__ == "__main__":
    unittest.main()
