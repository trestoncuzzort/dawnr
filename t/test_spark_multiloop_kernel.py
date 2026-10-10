"""Real SPARK controls for the two-loop certificate path (T77)."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

import lower_spark
import refute_at
import surface
import tlib
from verifiers import Outcome, flake_check
from verifiers import spark


SOURCE = """t 1
task two_phase_count(n: int) returns (r: int)
requires n >= 0
ensures r == 2 * n
{
  r := 0;
  var i: int := 0;
  while i < n
    invariant 0 <= i and i <= n
    invariant r == i
    decreases n - i
  { r := r + 1; i := i + 1; }
  var j: int := 0;
  while j < n
    invariant 0 <= j and j <= n
    invariant r == n + j
    decreases n - j
  { r := r + 1; j := j + 1; }
}
"""


def sources():
    task = surface.parse(SOURCE)
    assert not tlib.check_task(task)
    wrong = copy.deepcopy(task)
    wrong["body"][-1]["while"]["body"][0]["assign"][1] = {"var": "r"}
    witness = refute_at.witness_at(wrong, {"n": 1})
    assert witness is not None and witness["_kind"] == "value"
    assert refute_at.witness_at(task, {"n": 1}) is None
    return {
        "real": lower_spark.lower(task, task["body"]),
        "wrong": lower_spark.lower(wrong, wrong["body"], witness=witness),
        "fabricated": lower_spark.lower(task, task["body"], witness=witness),
    }


@unittest.skipUnless(spark.GNATPROVE, "GNATprove is not installed")
class SparkMultiLoopKernelTests(unittest.TestCase):
    def test_real_wrong_and_fabricated_witness(self):
        expected = {"real": {Outcome.VERIFIED}, "wrong": {Outcome.REFUTED},
                    "fabricated": {Outcome.UNPROVED, Outcome.TIMEOUT}}
        with tempfile.TemporaryDirectory(prefix="t-spark-two-loops-") as directory:
            for name, source in sources().items():
                with self.subTest(case=name):
                    path = Path(directory) / f"{name}.ads"
                    path.write_text(source)
                    result, agreed = flake_check(spark.verify, path, 3)
                    self.assertTrue(agreed, result)
                    self.assertIn(result.outcome, expected[name], result)
                    if name == "fabricated":
                        # The false certificate must reach the prover and be
                        # declined; a parse/tool error would not test this gate.
                        self.assertEqual(result.extras["cert"]["post_proved"], 0)
                        self.assertTrue(result.extras["cert"]["unproved"])
                    self.assertEqual(result.source_sha256, hashlib.sha256(source.encode()).hexdigest())


if __name__ == "__main__":
    unittest.main()
