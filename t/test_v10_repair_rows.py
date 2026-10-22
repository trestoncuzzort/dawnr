"""The repair-trace row builder's witness phrasing and pairing rules (t/recipes/v10_repair_rows.py).
Source: arXiv:2507.02778 (error-correction traces as training data)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "recipes"))
import v10_repair_rows as v10  # noqa: E402


class WitnessTest(unittest.TestCase):
    def test_a_disagreement_names_the_input_and_the_right_answer(self):
        w = v10.reference_witness({"status": "disagrees", "args": [3, 4], "reference_said": 7})
        self.assertEqual(len(w), 1)
        self.assertIn("[3, 4]", w[0]) and self.assertIn("answers 7", w[0])

    def test_a_weak_spec_names_the_wrong_result_it_accepts(self):
        w = v10.reference_witness({"status": "agrees", "completeness": 0.5,
                                   "weak_witness": {"args": [1], "reference_said": 2, "also_accepts": 3}})
        self.assertIn("also accepts the wrong result 3", w[0])

    def test_a_weak_spec_without_a_stored_witness_states_the_share(self):
        w = v10.reference_witness({"status": "agrees", "completeness": 0.75})
        self.assertIn("25%", w[0])


if __name__ == "__main__":
    unittest.main()
