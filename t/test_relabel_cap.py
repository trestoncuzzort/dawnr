"""loop_dataset --relabel-cap: at most N relabeled rows per target problem, in file order."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_dataset                                          # noqa: E402


class RelabelCapTests(unittest.TestCase):
    ROWS = [{"task_id": 960, "task": f"mbpp_960__f{i}"} for i in range(8)] + \
           [{"task_id": 5, "task": "mbpp_5__g"}, {"task_id": 960, "task": "mbpp_960__f8"}, {"task_id": 7, "task": "mbpp_7__h"}]

    def test_the_first_n_rows_of_a_problem_stay_in_file_order(self):
        kept, capped = loop_dataset.cap_relabel_rows(self.ROWS, 3)
        self.assertEqual(capped, 6)
        self.assertEqual([r["task"] for r in kept], ["mbpp_960__f0", "mbpp_960__f1", "mbpp_960__f2", "mbpp_5__g", "mbpp_7__h"])

    def test_zero_keeps_every_row(self):
        kept, capped = loop_dataset.cap_relabel_rows(self.ROWS, 0)
        self.assertEqual((len(kept), capped), (len(self.ROWS), 0))


if __name__ == "__main__":
    unittest.main()
