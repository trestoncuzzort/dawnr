#!/usr/bin/env python3
"""t/test_interp_seq_caps.py -- every sequence the interpreter builds stays under MAX_SEQ, and one specification
evaluation in t/spec_quality.py stops at a wall clock (2026-10-04).

join and replace were the two operations whose result can outgrow their arguments; a specification function joining
a sequence with itself doubled it at each step, and teacher3 seed 1's specification stage was killed twice near 122 GB
inside the 60,000-step budget. They now raise Budget past MAX_SEQ, as fill and seq + already did, and scoring gives an
evaluation EVAL_SECONDS of wall clock (a Python signal handler runs at the next bytecode of the main thread,
docs.python.org/3/library/signal.html). Standard library only. unittest.
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import interp                                                 # noqa: E402
import spec_quality                                           # noqa: E402

CAP = interp.MAX_SEQ


class Join(unittest.TestCase):
    def test_under_the_cap_unchanged(self):
        self.assertEqual(interp._str_join(((1, 2), (3,), ()), (0,)), (1, 2, 0, 3, 0))
        self.assertEqual(interp._str_join((), (0,)), ())

    def test_past_the_cap_refused(self):
        half = tuple(range(CAP // 2 + 1))
        with self.assertRaises(interp.Budget):
            interp._str_join((half, half), ())
        with self.assertRaises(interp.Budget):                      # the separator counts too
            interp._str_join(((1,),) * 3, (0,) * (CAP // 2))

    def test_through_the_evaluator(self):
        half = tuple(range(CAP // 2 + 1))
        e = {"op": "join", "args": [{"var": "rows"}, {"var": "sep"}]}
        with self.assertRaises(interp.Budget):
            interp.ev(e, {"rows": (half, half), "sep": ()}, {}, interp.St())

    def test_doubling_stops_fast(self):
        s, t0 = (7,), time.monotonic()
        with self.assertRaises(interp.Budget):
            for _ in range(64):
                s = interp._str_join((s, s), ())
        self.assertLess(time.monotonic() - t0, 5)
        self.assertLessEqual(len(s), CAP)


class Replace(unittest.TestCase):
    def test_under_the_cap_unchanged(self):
        self.assertEqual(interp._str_replace((1, 9, 2, 9), (9,), (5, 5)), (1, 5, 5, 2, 5, 5))
        self.assertEqual(interp._str_replace((1, 2), (), (0,)), (0, 1, 0, 2, 0))
        self.assertEqual(interp._str_replace((1, 2, 3), (4,), (5,)), (1, 2, 3))

    def test_past_the_cap_refused(self):
        with self.assertRaises(interp.Budget):                      # empty pattern: u before every element
            interp._str_replace(tuple(range(300)), (), tuple(range(300)))
        with self.assertRaises(interp.Budget):                      # each match grows the result
            interp._str_replace((9,) * 1000, (9,), tuple(range(100)))


class EvaluationClock(unittest.TestCase):
    def test_time_limit_raises(self):
        t0 = time.monotonic()
        with self.assertRaises(spec_quality.Overtime):
            with spec_quality.time_limit(0.2):
                while True:
                    pass
        self.assertLess(time.monotonic() - t0, 3)

    def test_time_limit_quiet_when_fast(self):
        with spec_quality.time_limit(5):
            x = sum(range(1000))
        self.assertEqual(x, 499500)

    def test_a_slow_evaluation_counts_as_not_holding(self):
        task = {"name": "f", "params": [{"name": "n", "type": "int"}], "returns": [{"name": "r", "type": "int"}],
                "requires": [], "ensures": [{"op": "==", "args": [{"var": "r"}, {"var": "n"}]}], "body": []}
        real_ev, old = interp.ev, spec_quality.EVAL_SECONDS

        def slow(*a, **k):
            while True:
                pass
        try:
            spec_quality.EVAL_SECONDS = 0.2
            interp.ev = slow
            entry = {"points": [{"args": [["int", 3]], "expected": ["int", 3]}]}
            got = None
            try:
                got = spec_quality.scores(task, entry)
            except Exception as e:                                  # noqa: BLE001
                self.fail(f"scores raised {type(e).__name__}: {e}")
        finally:
            interp.ev, spec_quality.EVAL_SECONDS = real_ev, old
        self.assertIn("correctness", got, got)
        self.assertEqual(got["correctness"], 0.0)

    def test_a_slow_specification_is_unscorable(self):
        task = {"name": "f", "params": [{"name": "n", "type": "int"}], "returns": [{"name": "r", "type": "int"}],
                "requires": [], "ensures": [{"op": "==", "args": [{"var": "r"}, {"var": "n"}]}], "body": []}
        real_ev, old_e, old_s = interp.ev, spec_quality.EVAL_SECONDS, spec_quality.SPEC_SECONDS

        def slow(*a, **k):
            while True:
                pass
        try:
            spec_quality.EVAL_SECONDS, spec_quality.SPEC_SECONDS = 0.2, 0.5
            interp.ev = slow
            entry = {"points": [{"args": [["int", v]], "expected": ["int", v]} for v in range(20)]}
            t0 = time.monotonic()
            got = spec_quality.scores(task, entry)
            took = time.monotonic() - t0
        finally:
            interp.ev, spec_quality.EVAL_SECONDS, spec_quality.SPEC_SECONDS = real_ev, old_e, old_s
        self.assertIn("unscorable", got, got)
        self.assertLess(took, 3, "the specification's clock bounds all of its evaluations together")


if __name__ == "__main__":
    unittest.main()
