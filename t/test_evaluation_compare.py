"""Exact comparison tests use fixed maps and exact p-values, not random simulations."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from fractions import Fraction
from pathlib import Path

import evaluation_compare as comparison


def paired_maps(b, c):
    """Return paired clean maps with b Local-only and c Phi-only successes."""
    local, phi = {}, {}
    for task_id in range(b):
        local[task_id], phi[task_id] = True, False
    for task_id in range(b, b + c):
        local[task_id], phi[task_id] = False, True
    return local, phi


class ExactComparisonTests(unittest.TestCase):
    def test_paired_mcnemar_has_known_exact_two_sided_p_values(self):
        cases = (
            (6, 0, Fraction(1, 32)),
            (8, 1, Fraction(5, 128)),
            (10, 2, Fraction(79, 2048)),
            (9, 10, Fraction(1)),
        )
        for b, c, expected_p in cases:
            with self.subTest(b=b, c=c):
                local, phi = paired_maps(b, c)
                report = comparison.paired_mcnemar(local, phi)
                self.assertEqual((report["b"], report["c"]), (b, c))
                self.assertEqual(Fraction(report["p_value_exact"]), expected_p)
                self.assertEqual(report["p_value"], float(expected_p))
                self.assertTrue(report["two_sided"])

    def test_zero_discordant_pairs_and_all_tied_seeds_have_p_one(self):
        paired = comparison.paired_mcnemar({1: True, 2: False}, {1: True, 2: False})
        self.assertEqual((paired["b"], paired["c"], paired["ties"], paired["p_value_exact"]),
                         (0, 0, 2, "1/1"))
        seeds = comparison.seed_sign_test([3, 3], 3)
        self.assertEqual((seeds["b"], seeds["c"], seeds["ties"], seeds["p_value_exact"]),
                         (0, 0, 2, "1/1"))

    def test_paired_mcnemar_rejects_different_task_populations(self):
        with self.assertRaisesRegex(ValueError, "identical task ids"):
            comparison.paired_mcnemar({1: True}, {2: False})

    def test_seed_sign_test_uses_one_fixed_phi_count_and_drops_ties(self):
        report = comparison.seed_sign_test([11] * 8 + [9] + [10], 10)
        self.assertEqual((report["b"], report["c"], report["ties"]), (8, 1, 1))
        self.assertEqual(report["p_value_exact"], "5/128")
        self.assertEqual(report["fixed_phi_clean_count"], 10)
        with self.assertRaises(TypeError):
            comparison.seed_sign_test([11], [10])

    def test_clean_outcome_export_requires_complete_boolean_panel_map(self):
        export = {
            "schema_version": 1,
            "panels": {
                "clean-2": {
                    "task_ids": [3, 4],
                    "tags": {"local": {
                        "clean": {"3": True, "4": False}, "clean_count": 1,
                        "spec_agrees": {"3": True, "4": False}, "spec_agrees_count": 1,
                    }},
                },
            },
        }
        self.assertEqual(comparison.clean_outcomes_from_export(export, "clean-2", "local"), {3: True, 4: False})
        self.assertEqual(comparison.spec_agrees_outcomes_from_export(export, "clean-2", "local"),
                         {3: True, 4: False})
        export["panels"]["clean-2"]["tags"]["local"]["clean"].pop("4")
        with self.assertRaisesRegex(ValueError, "cover exactly"):
            comparison.clean_outcomes_from_export(export, "clean-2", "local")

    def test_schema_two_exports_are_read_and_unknown_schemas_refused(self):
        export = {
            "schema_version": 2,
            "panels": {
                "clean-1": {
                    "task_ids": [3],
                    "tags": {"local": {
                        "clean": {"3": True}, "clean_count": 1,
                        "spec_agrees": {"3": False}, "spec_agrees_count": 0,
                        "tests_pass": {"3": True}, "tests_pass_count": 1,
                        "answered_count": 1, "partial": False,
                    }},
                },
            },
        }
        self.assertEqual(comparison.clean_outcomes_from_export(export, "clean-1", "local"), {3: True})
        self.assertEqual(comparison.tests_pass_outcomes_from_export(export, "clean-1", "local"), {3: True})
        export["schema_version"] = 3
        with self.assertRaisesRegex(ValueError, "schema"):
            comparison.clean_outcomes_from_export(export, "clean-1", "local")

    def test_cli_reports_paired_and_fixed_baseline_seed_results(self):
        export = {
            "schema_version": 1,
            "panels": {
                "clean-3": {
                    "task_ids": [1, 2, 3],
                    "tags": {
                        "local-confirm": {"clean": {"1": True, "2": True, "3": False}, "clean_count": 2},
                        "phi-fixed": {"clean": {"1": False, "2": True, "3": False}, "clean_count": 1},
                        "local-s1": {"clean": {"1": True, "2": True, "3": False}, "clean_count": 2},
                        "local-s2": {"clean": {"1": False, "2": False, "3": False}, "clean_count": 0},
                    },
                },
            },
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "outcomes.json"
            path.write_text(json.dumps(export), encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(comparison.main([
                    str(path), "--panel", "clean-3", "--local-tag", "local-confirm",
                    "--phi-tag", "phi-fixed", "--seed-tag", "local-s1", "--seed-tag", "local-s2",
                ]), 0)
        report = json.loads(stdout.getvalue())
        self.assertEqual((report["comparisons"]["phi-fixed"]["b"],
                          report["comparisons"]["phi-fixed"]["c"]), (1, 0))
        self.assertEqual((report["seed_sign_tests"]["phi-fixed"]["b"],
                          report["seed_sign_tests"]["phi-fixed"]["c"]), (1, 1))
        self.assertEqual(report["seed_sign_tests"]["phi-fixed"]["fixed_phi_clean_count"], 1)


if __name__ == "__main__":
    unittest.main()
