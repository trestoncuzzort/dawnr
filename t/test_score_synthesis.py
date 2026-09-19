"""Lab tests for the synthesis scorer: a right answer, and every way to fail."""
import unittest

import build_composition_dataset as build
import composition_reference as ref
from execution_trace import digest
import score_synthesis as scorer


def entry_for(stages, name="probe", inputs=(-3, 0, 4)):
    source, task = build.build_task(name, stages)
    example = build.synthesis_example(source)
    contract = {key: task.get(key) for key in
                ("name", "params", "returns", "requires", "ensures", "spec_funs")}
    entry = {"task_name": name, "split": "eval_pattern", "pattern": [s[0] for s in stages],
             "prompt": example["prompt"], "contract_sha256": digest(contract),
             "tests": {"in_range": [{"x": x, "r": ref.final_value(stages, x)} for x in inputs]}}
    return entry, example["completion"]


class ScorerTests(unittest.TestCase):
    def score(self, entry, completion, **kwargs):
        options = {"time_limit": 5.0, "max_chars": 4000, **kwargs}
        return scorer.score_candidate(entry, completion, **options)

    def test_the_reference_body_scores_correct(self):
        for stages in ((("affine", 2, 1),), (("cap", 5), ("affine", 3, -2)), (("tri", 4),)):
            entry, completion = entry_for(stages)
            result = self.score(entry, completion)
            self.assertEqual(result["verdict"], "correct", (stages, result))
            self.assertEqual(result["tests_passed"], result["tests_run"])

    def test_a_different_program_scores_wrong_output(self):
        entry, _ = entry_for((("affine", 2, 1),))
        result = self.score(entry, "  r := x;\n  r := 2 * r + 2;\n}\n")
        self.assertEqual(result["verdict"], "wrong_output")
        self.assertLess(result["tests_passed"], result["tests_run"])

    def test_an_almost_right_program_still_fails(self):
        entry, _ = entry_for((("cap", 5),), inputs=(4, 5, 6, 12))
        result = self.score(entry, "  r := x;\n  if r > 6 { r := 6 } else { }\n}\n")
        self.assertEqual(result["verdict"], "wrong_output")

    def test_unparseable_text_is_malformed(self):
        entry, _ = entry_for((("affine", 2, 1),))
        for text in ("  r := ;\n}\n", "not t at all\n", "", "  r := x;\n"):
            self.assertEqual(self.score(entry, text)["verdict"], "malformed", text)

    def test_a_body_that_never_assigns_the_return_is_undefined(self):
        entry, _ = entry_for((("affine", 2, 1),))
        self.assertEqual(self.score(entry, "  var q: int := x;\n}\n")["verdict"], "undefined")

    def test_a_runaway_loop_is_over_budget(self):
        entry, _ = entry_for((("affine", 2, 1),))
        body = ("  r := x;\n  var i: int := 0;\n"
                "  while i < 100000 decreases 100000 - i { r := r + 1; i := i + 1; }\n}\n")
        self.assertEqual(self.score(entry, body)["verdict"], "over_budget")

    def test_the_wall_clock_cap_fires(self):
        # A candidate that stays inside the step cap can still be too slow to wait for.
        entry, completion = entry_for((("tri", 4),), inputs=tuple(range(1400, 1500)))
        result = self.score(entry, completion, time_limit=0.02)
        self.assertEqual(result["verdict"], "timeout")
        self.assertLess(result["seconds"], 5.0)

    def test_an_overlong_candidate_is_rejected_before_parsing(self):
        entry, completion = entry_for((("affine", 2, 1),))
        result = self.score(entry, completion + " " * 5000, max_chars=100)
        self.assertEqual(result["verdict"], "too_long")
        self.assertEqual(result["tests_run"], 0)

    def test_a_changed_contract_is_refused(self):
        entry, completion = entry_for((("affine", 2, 1),))
        entry = {**entry, "contract_sha256": "0" * 64}
        self.assertEqual(self.score(entry, completion)["verdict"], "contract_modified")

    def test_a_missing_candidate_counts_as_a_failure(self):
        entry, _ = entry_for((("affine", 2, 1),))
        report = scorer.score([entry], {}, time_limit=5.0, max_chars=4000)
        self.assertEqual(report["verdicts"], {"malformed": 1})
        self.assertEqual(report["by_split"]["eval_pattern"], {"tasks": 1, "correct": 0})

    def test_the_report_counts_strata_separately(self):
        stages = (("affine", 3, 1),)
        entry, completion = entry_for(stages)
        entry["tests"]["extrapolation"] = [{"x": x, "r": ref.final_value(stages, x)}
                                           for x in (25, 30)]
        report = scorer.score([entry], {"probe": completion}, time_limit=5.0, max_chars=4000)
        self.assertEqual(report["tests_by_stratum"]["extrapolation"], {"passed": 2, "total": 2})
        self.assertEqual(report["tests_by_stratum"]["in_range"], {"passed": 3, "total": 3})


if __name__ == "__main__":
    unittest.main()
