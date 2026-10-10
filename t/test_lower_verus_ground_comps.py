"""Ground comprehension certificates preserve semantics and refuse unsupported inputs."""
import itertools
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness
import interp
import lower_verus as lv
import surface


class GroundComprehensionCertificateTests(unittest.TestCase):
    def test_band_counterexample_gets_a_computational_certificate(self):
        task = surface.parse_file(str(Path(__file__).parent / "autonomy/readings_in_band.t"))
        body, _op, witness = harness.twin_cached(task)
        src = lv.lower(task, body, witness=witness)
        self.assertIn("proof fn t_refutation_certificate()", src)
        cert = src.split("proof fn t_refutation_certificate()", 1)[1]
        self.assertIn("by (compute_only)", cert)
        self.assertNotIn("t_comp", cert)
        self.assertIn("if", cert)
        self.assertIn("<=", cert)

    def test_filters_and_maps_match_independent_oracle(self):
        with patch.dict(lv._COMP_INDEX, {}, clear=True):
            for values in itertools.product(range(-1, 2), repeat=3):
                for lo, hi in ((-1, 0), (0, 0), (0, 1), (2, 3)):
                    expr = surface.parse_expr(
                        "[2 * x + 1 for x in [%s] if %d <= x and x <= %d]"
                        % (", ".join(map(str, values)), lo, hi))
                    # The certificate's source display has already been grounded.
                    expr["comp"]["seq"] = {"_seq": list(values)}
                    expanded = lv._ground_certificate_comps(expr, [lv._UNROLL_CAP])
                    got = interp.ev(expanded, {}, {}, interp.St())
                    self.assertEqual(got, tuple(2 * x + 1 for x in values if lo <= x <= hi))

    def test_ranges_empty_sources_and_filtered_undefined_body(self):
        with patch.dict(lv._COMP_INDEX, {}, clear=True):
            for text, expected in (
                ("[x * x for x in [-2, 3) if x != 0]", (4, 1, 1, 4)),
                ("[x for x in [3, -1)]", ()),
                ("[10 / x for x in [0, 2] if x != 0]", (5,)),
            ):
                expanded = lv._ground_certificate_comps(surface.parse_expr(text), [lv._UNROLL_CAP])
                self.assertEqual(interp.ev(expanded, {}, {}, interp.St()), expected)
            empty = surface.parse_expr("[x for x in [1]]")
            empty["comp"]["seq"] = {"_seq": []}
            self.assertEqual(interp.ev(lv._ground_certificate_comps(empty, [0]), {}, {}, interp.St()), ())

    def test_expansion_budget_and_unsupported_sources_fail_closed(self):
        with patch.dict(lv._COMP_INDEX, {}, clear=True):
            for text, budget in (
                ("[x for x in [0, 1000000000000)]", 64),
                ("[x for x in [1, 2, 3]]", 2),
                ("[x for x in s]", 64),
                ("[x for x in [0, n)]", 64),
                ("[x == 0 for x in [1]]", 64),
            ):
                with self.assertRaises(NotImplementedError, msg=text):
                    lv._ground_certificate_comps(surface.parse_expr(text), [budget])

    def test_wrong_twin_value_is_not_replaced_with_true(self):
        task = surface.parse_file(str(Path(__file__).parent / "autonomy/readings_in_band.t"))
        body, _op, witness = harness.twin_cached(task)
        lv.lower(task, body, witness=witness)
        bad_witness = {**witness, "_twin": 0}
        cert = lv._certificate(task, body, bad_witness)
        self.assertIsNotNone(cert)
        # The incorrect output remains inside the actual negated postcondition;
        # only the kernel can accept or reject that proposition.
        self.assertIn("by (compute_only)", cert)
        self.assertNotIn("assert(true)", cert)
        self.assertNotEqual(cert, lv._certificate(task, body, witness))


if __name__ == "__main__":
    unittest.main()
