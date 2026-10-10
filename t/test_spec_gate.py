"""Regression test for spec_gate.promote_for_loop_dataset: spec_gate's per-sample
record must be consumable by loop_dataset.positive_rejection without a manual flatten.

The bug (2026-10-10): judge() nested status/draws under result["agreement"], while
loop_dataset reads them at the top level, so 121 genuinely spec-agreeing answers were
rejected as "spec-not-agrees". This pins the contract in both directions.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import loop_dataset
import spec_check
import spec_gate
import surface

# A real, parseable t task so spec_check.task_sha256 (which canonicalizes via surface) works.
TASK = surface.parse("t 1\ntask f(x: int) returns (r: int)\n{\n  r := x;\n}\n")


def _clean_seven_sample(task):
    """A well-formed, tests-passing sample that reads verified / refuted in all seven kernels."""
    return {
        "wellformed": True,
        "tests_pass": True,
        "kernel_columns": list(spec_check.KERNELS),
        "kernel_row": {k: "verified / refuted" for k in spec_check.KERNELS},
        "tag": "tag0",
        "name": "name0",
        "task": task,
        "task_id": 123,
    }


class PromoteForLoopDatasetTest(unittest.TestCase):
    def _agreeing_judge_record(self, task):
        # the shape judge() produces for an answer that agrees on random draws
        return {
            "passes": True,
            "why": "agrees",
            "agreement": {"status": "agrees", "draws": 100, "completeness": 1.0},
            "task_sha256": spec_check.task_sha256(task),
        }

    def test_promotes_the_fields_loop_dataset_reads(self):
        out = spec_gate.promote_for_loop_dataset(self._agreeing_judge_record(TASK), 123, "v5")
        self.assertEqual(out["status"], "agrees")
        self.assertEqual(out["draws"], 100)
        self.assertEqual(out["task_id"], 123)
        self.assertEqual(out["pool"], "v5")
        # the nested form stays for the report's other readers
        self.assertEqual(out["agreement"]["status"], "agrees")

    def test_promoted_record_is_admitted_by_loop_dataset(self):
        rec = spec_gate.promote_for_loop_dataset(self._agreeing_judge_record(TASK), 123, "v5")
        results = {"tag0/name0": rec}
        self.assertIsNone(
            loop_dataset.positive_rejection(_clean_seven_sample(TASK), results, "v5"),
            "a clean-in-seven, spec-agreeing, promoted record must be admitted",
        )

    def test_unpromoted_nested_record_is_rejected(self):
        # the pre-fix shape: status/draws only under "agreement" -> must NOT be admitted
        rec = self._agreeing_judge_record(TASK)  # NOT promoted
        results = {"tag0/name0": rec}
        self.assertEqual(
            loop_dataset.positive_rejection(_clean_seven_sample(TASK), results, "v5"),
            "spec-not-agrees",
            "the nested-only record is exactly the bug this fix closes",
        )


if __name__ == "__main__":
    unittest.main()
