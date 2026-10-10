"""Native positive and negative controls for the 2026-10-10 sweep repairs."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness
import lower_lean
import lower_verus
import surface
from verifiers import Outcome, flake_check
from verifiers import lean, verus

HERE = Path(__file__).resolve().parent


class CertificateSweepKernelTests(unittest.TestCase):
    def check_source(self, adapter, source, suffix, expected):
        with tempfile.TemporaryDirectory(prefix="t-certificate-sweep-") as directory:
            path = Path(directory) / ("control" + suffix)
            path.write_text(source)
            result, agreed = flake_check(adapter.verify, path, 3)
            self.assertTrue(agreed, result)
            self.assertEqual(result.outcome, expected, result)
            self.assertEqual(result.source_sha256, hashlib.sha256(source.encode()).hexdigest())
            return result

    @unittest.skipUnless(verus.VERUS, "Verus is not installed")
    def test_grounded_filter_and_false_certificate(self):
        task = surface.parse_file(str(HERE / "autonomy/readings_in_band.t"))
        twin, _op, witness = harness.twin_cached(task)
        for body, claim, expected in (
            (task["body"], None, Outcome.VERIFIED),
            (twin, witness, Outcome.REFUTED),
            (twin, {**witness, "_twin": 0}, Outcome.UNPROVED),
        ):
            with self.subTest(expected=expected):
                self.check_source(verus, lower_verus.lower(task, body, witness=claim), ".rs", expected)

    @unittest.skipUnless(lean.LEAN, "Lean is not installed")
    def test_product_sign_classification_and_square(self):
        for path in (HERE / "autonomy/crosstrack_side.t", HERE / "flight/px4_sq.t"):
            task = surface.parse_file(str(path))
            twin, _op, witness = harness.twin_cached(task)
            for body, claim, expected in ((task["body"], None, Outcome.VERIFIED),
                                          (twin, witness, Outcome.REFUTED)):
                with self.subTest(task=task["name"], expected=expected):
                    self.check_source(lean, lower_lean.lower(task, body, witness=claim), ".lean", expected)

    @unittest.skipUnless(lean.LEAN, "Lean is not installed")
    def test_existing_nonnegative_product_bridge(self):
        task = surface.parse("""t 1
task hex_sign(n: int) returns (r: int)
  requires n >= 0
  ensures r >= 0
  ensures r == 3 * n * (n - 1) + 1
{ r := 3 * n * (n - 1) + 1; }
""")
        self.check_source(lean, lower_lean.lower(task, task["body"]), ".lean", Outcome.VERIFIED)


if __name__ == "__main__":
    unittest.main()
