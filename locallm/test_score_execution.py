"""Lab tests for the execution scorer: the comparison, not the model."""
import unittest

import score_execution as scorer

ROW = {"task_name": "probe", "split": "eval_pattern", "pattern": ["affine"], "x": 3,
       "prompt": "execute x = 3\ntrace\n",
       "parts": [["enter 0 | r=? x=3\nexit 0 | r=3\n", "execution"],
                 ["output r = 7\n", "answer"]]}


class ComparisonTests(unittest.TestCase):
    def test_a_perfect_continuation_scores_everything(self):
        lines, output = scorer.parse_generated(
            "enter 0 | r=? x=3\nexit 0 | r=3\noutput r = 7\n")
        reference, answer = scorer.split_reference(ROW)
        self.assertEqual(lines, reference)
        self.assertEqual(output, answer.rstrip("\n"))
        self.assertEqual(scorer.prefix_match(lines, reference), 2)

    def test_a_derailed_trace_keeps_only_its_matching_prefix(self):
        lines, output = scorer.parse_generated(
            "enter 0 | r=? x=3\nexit 0 | r=4\noutput r = 8\n")
        reference, answer = scorer.split_reference(ROW)
        self.assertEqual(scorer.prefix_match(lines, reference), 1)
        self.assertNotEqual(lines, reference)
        self.assertNotEqual(output, answer.rstrip("\n"))

    def test_a_right_answer_after_a_wrong_trace_is_reported_as_both(self):
        rows = [{"task_name": "a", "split": "eval_pattern", "pattern": ["affine"], "x": 1,
                 "reference_lines": 2, "matched_prefix_lines": 1, "trace_exact": False,
                 "produced_output": True, "output_correct": True}]
        summary = scorer.summarize(rows)["eval_pattern"]
        self.assertEqual(summary["trace_exact"], 0.0)
        self.assertEqual(summary["output_correct"], 1.0)
        self.assertEqual(summary["line_prefix_accuracy"], 0.5)

    def test_a_missing_output_line_is_not_an_answer(self):
        lines, output = scorer.parse_generated("enter 0 | r=? x=3\nexit 0 | r=3\n")
        self.assertIsNone(output)
        self.assertEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main()
