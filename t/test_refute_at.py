"""t/test_refute_at.py: refute_at.witness_at, the interpreter half of refuting a finding at a named input. No kernel
is invoked here; t/FLIGHT-FINDINGS.md has the kernels' verdicts.

Run: python3 t/test_refute_at.py
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import refute_at  # noqa: E402
import tasks_io  # noqa: E402


def _task(rel):
    return tasks_io.load_task(os.path.join(HERE, rel))


class WitnessAt(unittest.TestCase):
    def test_value_witness_at_the_named_input(self):
        w = refute_at.witness_at(_task("flight/findings/px4_wrap_bin_any.t"), {"bin": -73, "bin_count": 72})
        self.assertEqual((w["_kind"], w["_real"], w["bin"]), ("value", -1, -73))

    def test_undefined_witness_at_px4s_buffer_size(self):
        w = refute_at.witness_at(_task("flight/findings/px4_sumd_receive_any.t"),
                                 {"sumd_data": refute_at._value({"fill": 0, "len": 64}), "length": 32})
        self.assertEqual(w["_kind"], "undefined")
        self.assertIn("sumd_data[64]", w["_twin"])

    def test_no_witness_where_the_contract_holds(self):
        self.assertIsNone(refute_at.witness_at(_task("flight/findings/px4_wrap_bin_any.t"), {"bin": -1, "bin_count": 72}))

    def test_input_outside_requires_is_refused(self):
        with self.assertRaises(ValueError):
            refute_at.witness_at(_task("flight/findings/px4_wrap_bin_any.t"), {"bin": 0, "bin_count": 0})


if __name__ == "__main__":
    unittest.main()
