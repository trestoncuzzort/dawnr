"""spec_check.deadline (2026-09-30): the time limit around a reference call, so the evaluation
path runs on Windows too. Unix keeps signal.alarm ("Availability: Unix",
docs.python.org/3/library/signal.html) and nothing measured there changes; elsewhere a watchdog
thread raises Timeout with PyThreadState_SetAsyncExc (docs.python.org/3/c-api/threads.html), as
stopit's ThreadingTimeout does (github.com/glenfant/stopit). Both variants are exercised where the
platform allows. No kernel."""
from __future__ import annotations

import signal
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_check  # noqa: E402


def spin(seconds: float) -> int:
    """Pure-Python busy work, interruptible by either mechanism."""
    n, stop = 0, time.monotonic() + seconds
    while time.monotonic() < stop:
        n += 1
    return n


class ThreadWatchdog(unittest.TestCase):
    def test_a_quick_block_returns_and_leaves_nothing_pending(self):
        with spec_check._deadline_thread(1):
            value = spin(0.05)
        self.assertGreater(value, 0)
        spin(1.2)                                   # would raise if the firing had not been cleared

    def test_a_long_block_is_stopped(self):
        with self.assertRaises(spec_check.Timeout):
            with spec_check._deadline_thread(0.3):
                spin(5)


@unittest.skipUnless(hasattr(signal, "SIGALRM"), "the alarm exists on Unix only")
class AlarmOnUnix(unittest.TestCase):
    def test_a_long_block_is_stopped_and_the_alarm_is_cleared(self):
        with self.assertRaises(spec_check.Timeout):
            with spec_check._deadline_alarm(1):
                spin(5)
        self.assertEqual(signal.alarm(0), 0)        # nothing left armed

    def test_deadline_picks_the_alarm_here(self):
        self.assertEqual(spec_check.deadline(1).gen.__name__, "_deadline_alarm")


class Chooser(unittest.TestCase):
    def test_deadline_is_a_context_manager_on_every_platform(self):
        with spec_check.deadline(1):
            value = spin(0.01)
        self.assertGreater(value, 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
