"""The gap is the measurement, so the gap has to be right."""
import unittest

import example_holdout


def answer(name, verdicts):
    return {"name": name, "points": [{"verdict": v} for v in verdicts]}


class SplitTests(unittest.TestCase):
    def test_an_answer_with_no_held_out_point_says_nothing(self):
        rows = example_holdout.split_rates({"1": answer("a", ["pass", "pass"])}, shown=2)
        self.assertEqual(rows, [])

    def test_the_split_lands_where_the_prompt_cut_it(self):
        rows = example_holdout.split_rates({"1": answer("a", ["pass", "pass", "fail", "fail"])},
                                           shown=2)
        self.assertEqual(rows[0]["visible_passed"], 2)
        self.assertEqual(rows[0]["visible_total"], 2)
        self.assertEqual(rows[0]["held_passed"], 0)
        self.assertEqual(rows[0]["held_total"], 2)

    def test_a_shown_count_of_zero_puts_everything_in_the_held_out_half(self):
        rows = example_holdout.split_rates({"1": answer("a", ["pass", "fail"])}, shown=0)
        self.assertEqual(rows[0]["visible_total"], 0)
        self.assertEqual(rows[0]["held_total"], 2)


if __name__ == "__main__":
    unittest.main()
