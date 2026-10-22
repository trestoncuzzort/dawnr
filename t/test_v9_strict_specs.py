"""The strict keep rule of t/recipes/v9_strict_specs.py (source: arXiv:2605.30914, filtering underspecified tasks)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "recipes"))
import v9_strict_specs as v9  # noqa: E402


class StrictKeepTest(unittest.TestCase):
    def test_keeps_only_agreeing_specs_that_reject_both_mutant_families_at_the_floor(self):
        ok = {"status": "agrees", "draws": 40, "completeness": 0.95, "cross_completeness": 0.9}
        self.assertTrue(v9.strict_keeps(ok, 0.9))
        self.assertFalse(v9.strict_keeps(dict(ok, completeness=0.85), 0.9))
        self.assertFalse(v9.strict_keeps(dict(ok, cross_completeness=0.5), 0.9))
        self.assertFalse(v9.strict_keeps(dict(ok, status="disagrees"), 0.9))
        self.assertFalse(v9.strict_keeps(dict(ok, draws=3), 0.9))

    def test_a_candidate_with_no_judged_mutant_is_dropped(self):
        self.assertFalse(v9.strict_keeps({"status": "agrees", "draws": 40}, 0.9))

    def test_the_old_floor_would_have_kept_what_the_strict_one_drops(self):
        weak = {"status": "agrees", "draws": 40, "completeness": 0.7}
        self.assertTrue(v9.strict_keeps(weak, 0.6))
        self.assertFalse(v9.strict_keeps(weak, 0.9))


if __name__ == "__main__":
    unittest.main()
