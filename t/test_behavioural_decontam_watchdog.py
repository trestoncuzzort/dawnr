"""behavioural_decontam.run_reference on a platform without setitimer (2026-09-30): the wall-clock
watchdog thread stands in for the CPU timer and the backstop, raising ReferenceTimeout with
PyThreadState_SetAsyncExc (docs.python.org/3/c-api/threads.html) as stopit's ThreadingTimeout does
(github.com/glenfant/stopit). The Unix path is untouched (the other decontam tests cover it); this
forces the watchdog path on every platform. No kernel."""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import behavioural_decontam as bd  # noqa: E402


def spin_forever():
    while True:
        pass


def quick(x):
    return x + 1


class Watchdog(unittest.TestCase):
    def setUp(self):
        self._had = bd._HAS_ITIMER
        bd._HAS_ITIMER = False

    def tearDown(self):
        bd._HAS_ITIMER = self._had
        bd._TIMER["fired"] = False

    def test_a_quick_reference_answers_and_nothing_fires_later(self):
        self.assertEqual(bd.run_reference(quick, [1], timeout_s=0.5), ("ok", bd.canon(2)))
        time.sleep(0.7)                               # the cancelled watchdog must not raise here
        self.assertFalse(bd._TIMER["fired"])

    def test_a_spinning_reference_is_a_timeout(self):
        t0 = time.monotonic()
        self.assertEqual(bd.run_reference(spin_forever, [], timeout_s=0.3), ("timeout",))
        self.assertLess(time.monotonic() - t0, 5.0)

    def test_a_raising_reference_is_still_reported_as_raised(self):
        def boom(_):
            raise ValueError("x")
        self.assertEqual(bd.run_reference(boom, [1], timeout_s=0.5), ("raised", "ValueError"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
