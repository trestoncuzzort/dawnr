"""The three-decode report's statistics (t/recipes/three_decode_report.py): fractions, the exact sign test, the
paired permutation test. Source: arXiv:2605.30315 (paired per-item evaluation)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "recipes"))
import three_decode_report as r  # noqa: E402


class ThreeDecodeTest(unittest.TestCase):
    def test_fractions_count_each_problem_over_the_decodes(self):
        f = r.fractions([{1, 2}, {1}, {1, 3}], [1, 2, 3, 4])
        self.assertEqual(f, {1: 1.0, 2: 1 / 3, 3: 1 / 3, 4: 0.0})

    def test_sign_test_is_exact_and_two_sided(self):
        self.assertEqual(r.sign_test({1: 0.0, 2: 0.0}), {"up": 0, "down": 0, "p": 1.0})
        one = r.sign_test({1: 1.0})
        self.assertEqual((one["up"], one["down"]), (1, 0)) and self.assertAlmostEqual(one["p"], 1.0)
        five = r.sign_test({i: 1.0 for i in range(5)})
        self.assertAlmostEqual(five["p"], 2 / 32)

    def test_permutation_test_is_small_for_a_one_sided_shift_and_one_for_none(self):
        self.assertEqual(r.permutation_test({1: 0.0})["p"], 1.0)
        p = r.permutation_test({i: 1 / 3 for i in range(12)}, draws=4000)["p"]
        self.assertLess(p, .01)
        q = r.permutation_test({i: (1 / 3 if i % 2 else -1 / 3) for i in range(12)}, draws=4000)["p"]
        self.assertGreater(q, .5)

    def test_compare_reports_the_mean_difference_and_the_moved_problems(self):
        ids = [1, 2, 3]
        base = r.model_reading("b", [("b0", {1, 2}), ("b1", {1}), ("b2", {1, 2})], ids)
        cand = r.model_reading("c", [("c0", {1, 3}), ("c1", {1, 3}), ("c2", {1})], ids)
        out = r.compare(base, cand, ids)
        self.assertAlmostEqual(out["mean_difference"], 0.0)
        self.assertEqual(set(out["moved"]), {"2", "3"})
        self.assertEqual(out["sign_test"]["up"], 1) and self.assertEqual(out["sign_test"]["down"], 1)


class JoinedDecodeTest(unittest.TestCase):
    def test_a_decode_graded_in_parts_joins_the_parts_sets(self):
        def fake_arm(spec, ids):
            tag = spec.split(":", 1)[0]
            return None, {"1": {1, 2} if tag == "a" else {7}, "7": {1} if tag == "a" else set()}, None
        sets = r.decode_sets("a:/x+b:/y", [1, 2, 7, 9], fake_arm)
        self.assertEqual(sets["1"], {1, 2, 7})
        self.assertEqual(sets["7"], {1})

    def test_a_single_part_decode_is_unchanged(self):
        sets = r.decode_sets("a:/x", [1], lambda spec, ids: (None, {"1": {1}, "7": set()}, None))
        self.assertEqual(sets, {"1": {1}, "7": set()})


if __name__ == "__main__":
    unittest.main()
