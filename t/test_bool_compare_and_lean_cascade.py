"""t/test_bool_compare_and_lean_cascade.py: PREDICT T68's two lowering changes, read from the emitted text. No kernel
is invoked here; the kernels' verdicts are in t/FLIGHT.md.

- Frama-C: a t bool is carried by a C int, so a bool `==`/`!=` in executable C compares the negations (`!a != !b`)
  and never the ints themselves, which would call 1 and 2 different (CERT EXP20-C's class).
- Lean: the loop closer tries `simp_all` only after every earlier alternative, so a goal that proved before proves
  by the same branch.

Run: python3 t/test_bool_compare_and_lean_cascade.py
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import harness  # noqa: E402
import lower_framac  # noqa: E402
import lower_lean  # noqa: E402
import tasks_io  # noqa: E402


def _load(rel):
    task = tasks_io.load_task(os.path.join(HERE, rel))
    harness._set_ctx(task)
    return task


class FramacBoolCompare(unittest.TestCase):
    def test_bool_inequality_compares_truth_values(self):
        task = _load("flight/px4_hysteresis_set.t")
        c = lower_framac.lower(task, task["body"])
        self.assertIn("((!(new_state)) != (!(state)))", c)
        self.assertNotIn("(new_state != state)", c)

    def test_int_comparison_unchanged(self):
        task = _load("flight/px4_hysteresis_update.t")
        c = lower_framac.lower(task, task["body"])
        self.assertIn("(now >= (last + time_from_true))", c)


class LeanCascadeOrder(unittest.TestCase):
    def test_simp_all_comes_after_grind_and_omega(self):
        task = _load("flight/px4_hysteresis_switches.t")
        src = lower_lean.lower(task, task["body"])
        i_grind = src.index("(first | grind")
        i_omega = src.index("at *; omega)", i_grind)
        i_simp = src.index("(simp_all; done)", i_grind)
        self.assertLess(i_omega, i_simp)
        self.assertIn("(simp_all; grind", src)


if __name__ == "__main__":
    unittest.main()
