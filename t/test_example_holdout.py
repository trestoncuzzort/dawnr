"""The gap is the measurement, so the gap has to be right."""
import unittest

import example_holdout


def answer(name, verdicts):
    return {"name": name, "points": [{"verdict": v} for v in verdicts]}


def pool(n_points):
    """A problem whose prompt pair is NOT the first two points: discriminative()
    ranks (30, 900) and (40, 1600) above (1, 1), so the hidden point is index 0."""
    values = [1, 30, 40, 50][:n_points]
    return {1: {"task_id": 1, "fn": "sq", "rec": {"text": "square it"},
                "points": [{"args": [["int", v]], "expected": ["int", v * v]} for v in values]}}


class SplitTests(unittest.TestCase):
    def test_an_answer_with_no_held_out_point_says_nothing(self):
        rows = example_holdout.split_rates({"1": answer("a", ["pass", "pass"])}, 2, pool(2))
        self.assertEqual(rows, [])

    def test_the_split_lands_where_the_prompt_cut_it(self):
        # verdicts by index: 0 fails (the hidden point), 1 and 2 pass (the shown pair), 3 fails
        rows = example_holdout.split_rates({"1": answer("a", ["fail", "pass", "pass", "fail"])}, 2, pool(4))
        self.assertEqual(rows[0]["visible_passed"], 2)
        self.assertEqual(rows[0]["visible_total"], 2)
        self.assertEqual(rows[0]["held_passed"], 0)
        self.assertEqual(rows[0]["held_total"], 2)
        self.assertEqual(sorted(rows[0]["shown_indices"]), [1, 2])

    def test_the_first_two_points_are_not_assumed_shown(self):
        rows = example_holdout.split_rates({"1": answer("a", ["pass", "pass", "fail", "fail"])}, 2, pool(4))
        self.assertEqual(rows[0]["visible_passed"], 1)
        self.assertEqual(rows[0]["held_passed"], 1)

    def test_a_shown_count_of_zero_puts_everything_in_the_held_out_half(self):
        rows = example_holdout.split_rates({"1": answer("a", ["pass", "fail"])}, 0, pool(2))
        self.assertEqual(rows[0]["visible_total"], 0)
        self.assertEqual(rows[0]["held_total"], 2)


if __name__ == "__main__":
    unittest.main()
