"""t/test_nested_return_and_scopes.py: PREDICT T69's lowering fixes, read from the emitted text. No kernel is invoked
here; the kernels' verdicts are in t/FLIGHT.md.

PX4's Ringbuffer::push_back returns `(false, _end)` two `if`s deep and declares `available` in both arms of an `if`.
That one function found four lowering faults:
- Lean dropped a `return` nested inside a branch that does not always return: `if x > 0 { if y > 0 { return 1; } }
  r := 2;` lowered to the constant 2.
- F* collapsed a one-sided return to the outer condition alone, giving `if x > 0 then 1 else 2`.
- Rocq refused the sanitizer's own rename of a `_len` name (`buf_len` -> `tn_buf_len`).
- Rocq treated a `var` in each arm of an `if` as a redeclaration, and Frama-C's certificate, which hoists every
  local into one scope, refused the twin a certificate for the same reason.
- Rocq's pair-returning straight-line proof and Lean's needed one more fallback each (a comparison sweep; unfolding
  `t_min`), tried only after every earlier alternative.

Run: python3 t/test_nested_return_and_scopes.py
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import harness  # noqa: E402
import lower_framac  # noqa: E402
import lower_fstar  # noqa: E402
import tasks_io  # noqa: E402
import lower_lean  # noqa: E402
import lower_rocq  # noqa: E402
import surface  # noqa: E402

RET_MIN = """t 1
task ret_min(x: int, y: int) returns (r: int)
  ensures x > 0 and y > 0 ==> r == 1
  ensures not (x > 0 and y > 0) ==> r == 2
{
  if x > 0 {
    if y > 0 {
      return 1;
    }
  }
  r := 2;
}
"""

SIBLING_VARS = """t 1
task sibling_vars(a: int, buf_len: int) returns (r: int)
  ensures a > 0 ==> r == a + buf_len
  ensures a <= 0 ==> r == buf_len - a
{
  if a > 0 {
    var available: int := a + buf_len;
    r := available;
  } else {
    var available: int := buf_len - a;
    r := available;
  }
}
"""


def _task(src):
    task = surface.parse(src)
    harness._set_ctx(task)
    return task


class NestedReturn(unittest.TestCase):
    def test_lean_keeps_the_inner_condition(self):
        task = _task(RET_MIN)
        src = lower_lean.lower(task, task["body"])
        body = src[src.index("def ret_min_t"):src.index("theorem ret_min_t_spec")]
        self.assertIn("(y > (0 : Int))", body)
        self.assertIn("(1 : Int)", body)
        self.assertIn("(2 : Int)", body)

    def test_fstar_conjoins_the_inner_condition(self):
        task = _task(RET_MIN)
        src = lower_fstar.lower(task, task["body"])
        self.assertIn("(if ((x > 0) && (y > 0)) then 1 else 2)", src)


class RocqScopesAndRenames(unittest.TestCase):
    def test_sibling_vars_and_len_rename_lower(self):
        task = _task(SIBLING_VARS)
        src = lower_rocq.lower(task, task["body"])
        self.assertIn("tn_buf_len", src)
        self.assertIn("Theorem sibling_vars_t_spec", src)


class CertificatesAndFallbacks(unittest.TestCase):
    def _flight(self, name):
        task = tasks_io.load_task(os.path.join(HERE, "flight", name + ".t"))
        harness._set_ctx(task)
        return task

    def test_framac_certificate_with_sibling_locals(self):
        for name in ("px4_rb_push_back", "px4_rb_pop_front"):
            task = self._flight(name)
            body, _op, w = harness.twin_for(task)
            self.assertIn("t_refutation_certificate", lower_framac.lower(task, body, witness=w), name)

    def test_rocq_pair_sweep_comes_after_t_dis(self):
        task = self._flight("px4_rb_push_back")
        src = lower_rocq.lower(task, task["body"])
        self.assertIn("first [ t_dis | (t_sweep; cbn [fst snd] in *; t_dis) ].", src)

    def test_lean_unfolds_min_last(self):
        task = self._flight("px4_rb_pop_front")
        src = lower_lean.lower(task, task["body"])
        i_grind = src.index("  | grind [px4_rb_pop_front_t")
        self.assertLess(i_grind, src.index("  | (unfold px4_rb_pop_front_t t_min; grind)"))


if __name__ == "__main__":
    unittest.main()
