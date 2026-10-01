"""t/score_levels.py (2026-10-01): what counts at each trust level. One sound verifier is the
published filter (SAFE, arXiv:2410.15756); the level is reported, never rounded up. No kernel."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import score_levels  # noqa: E402
import spec_check  # noqa: E402

ALL = {k: "verified / refuted" for k in spec_check.KERNELS}


def row(**cells):
    return {**ALL, **cells}


class Level(unittest.TestCase):
    def test_all_seven_with_the_specification_checked_is_seven(self):
        self.assertEqual(score_levels.answer_level("pass", ALL, "agrees"), (7, 7))

    def test_a_kernel_that_could_not_decide_lowers_the_level(self):
        r = row(spark="timeout / refuted", framac="abstain / abstain")
        self.assertEqual(score_levels.answer_level("pass", r, "agrees"), (5, 5))

    def test_a_refuting_kernel_makes_it_nothing_at_any_level(self):
        self.assertEqual(score_levels.answer_level("pass", row(lean="refuted / refuted"), "agrees"), (0, 0))

    def test_tests_must_pass(self):
        self.assertEqual(score_levels.answer_level("fail", ALL, "agrees"), (0, 0))
        self.assertEqual(score_levels.answer_level(None, ALL, "agrees"), (0, 0))

    def test_without_an_agreeing_specification_it_counts_only_in_the_unchecked_column(self):
        for status in ("disagrees", None):
            self.assertEqual(score_levels.answer_level("pass", ALL, status), (0, 7))

    def test_a_twin_that_was_not_refuted_is_not_a_proof(self):
        r = {k: "verified / verified" for k in spec_check.KERNELS}
        self.assertEqual(score_levels.answer_level("pass", r, "agrees"), (0, 0))

    def test_a_table_without_exactly_the_seven_kernels_does_not_count(self):
        r = dict(ALL)
        del r["rocq"]
        self.assertEqual(score_levels.answer_level("pass", r, "agrees"), (0, 0))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
