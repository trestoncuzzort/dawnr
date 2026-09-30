"""stage_teacher_prompts (2026-09-30): the training-problem half of a teacher round, as a command.
MBPP/HumanEval ids named in the corpus are left out; the APPS sample is seeded. No kernel."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import stage_teacher_prompts as stp  # noqa: E402


class Staging(unittest.TestCase):
    def test_named_ids_are_left_out_and_the_apps_sample_is_seeded(self):
        corpus = "Problem: mbpp_5__foo\n... Problem: humaneval_3__bar\n"
        ids = [5, 7, 11] + [100000 + i for i in range(10)]
        r = stp.stage(corpus, ids, apps_base=100000, apps=3, seed=1)
        self.assertEqual((r["mbpp_he_total"], r["apps_available"], r["apps_sampled"]), (3, 10, 3))
        self.assertNotIn(5, r["ids"])
        self.assertIn(7, r["ids"])
        again = stp.stage(corpus, ids, apps_base=100000, apps=3, seed=1)
        self.assertEqual(r["ids"], again["ids"])
        self.assertEqual(len(r["ids"]), 2 + 3)

    def test_no_apps_when_asked(self):
        r = stp.stage("", [1, 2, 100001], apps_base=100000, apps=0, seed=1)
        self.assertEqual(r["ids"], [1, 2])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
