"""The visible half of the gap is the pair the prompt printed, on every held-out problem.

Until 2026-09-25 `example_holdout` scored `points[:2]` as shown while the prompt
builder prints `discriminative()`'s pair; on the real split they differ on 54 of
232 problems. These tests pin the fix to the prompt builder's own functions.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import example_holdout
import loop_locallm
import spec_experiment as se

HERE = Path(__file__).resolve().parent
SPLIT = HERE / "out" / "loop" / "split-v3.json"


def _real_split():
    if not SPLIT.exists():
        raise AssertionError(f"{SPLIT} is tracked and must exist; this test does not skip")
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    pool = se.pool(split.get("pool", "v3"))
    ids = sorted(int(i) for i in split["eval_ids"])
    return pool, ids


def _record(entry, verdict_of):
    """A tests.json-shaped record whose verdict at each index is verdict_of(index)."""
    return {"name": f"mbpp_{entry.get('rec', {}).get('task_id', '?')}__{entry['fn']}", "overall": "fail",
            "points": [{"verdict": verdict_of(i)} for i in range(len(entry["points"]))]}


class ShownIndicesOnTheRealSplit(unittest.TestCase):
    def test_the_prompt_lines_are_exactly_the_shown_indices_on_all_232(self):
        pool, ids = _real_split()
        not_first_two = 0
        for tid in ids:
            entry = pool[tid]
            idx = example_holdout.shown_indices(entry, 2)
            rebuilt = "".join(loop_locallm.examples({"fn": entry["fn"], "points": [entry["points"][i]]}, 1)
                              for i in idx)
            head = loop_locallm.problem_head(entry, True)
            prompt_lines = "".join(line + "\n" for line in head.splitlines() if line.startswith("Example: "))
            self.assertEqual(rebuilt, prompt_lines, tid)
            not_first_two += set(idx) != {0, 1}
        self.assertEqual(len(ids), 232)
        self.assertGreater(not_first_two, 0, "the pair never differs from points[:2]; the fix would be moot")

    def test_an_answer_that_solved_only_the_shown_pair_reads_a_full_gap(self):
        """The review's constructed failure: passes exactly the two examples the prompt printed and fails
        the hidden one, on every eval id. The old positional split read 65.09 points and 178 flagged."""
        pool, ids = _real_split()
        tests = {}
        for tid in ids:
            shown = set(example_holdout.shown_indices(pool[tid], 2))
            tests[str(tid)] = _record(pool[tid], lambda i, s=shown: "pass" if i in s else "fail")
        rows = example_holdout.split_rates(tests, 2, pool)
        self.assertEqual(len(rows), 232)
        self.assertTrue(all(r["visible_passed"] == r["visible_total"] == 2 for r in rows))
        self.assertTrue(all(r["held_passed"] == 0 and r["held_total"] == 1 for r in rows))
        mirror = {str(tid): _record(pool[tid], lambda i, s=set(example_holdout.shown_indices(pool[tid], 2)):
                                    "fail" if i == min(s) else "pass") for tid in ids}
        rows = example_holdout.split_rates(mirror, 2, pool)
        self.assertTrue(all(r["visible_passed"] == 1 and r["held_passed"] == 1 for r in rows))

    def test_a_real_problem_where_the_pair_is_not_the_first_two(self):
        pool, ids = _real_split()
        tid = next(t for t in ids if set(example_holdout.shown_indices(pool[t], 2)) != {0, 1})
        hidden = ({0, 1, 2} - set(example_holdout.shown_indices(pool[tid], 2))).pop()
        self.assertNotEqual(hidden, 2)
        record = _record(pool[tid], lambda i: "fail" if i == hidden else "pass")
        row = example_holdout.split_rates({str(tid): record}, 2, pool)[0]
        self.assertEqual((row["visible_passed"], row["held_passed"]), (2, 0))
        self.assertEqual(sorted(row["shown_indices"]), sorted(example_holdout.shown_indices(pool[tid], 2)))


FAKE_POOL = {7: {"task_id": 7, "fn": "sq", "rec": {"text": "square it"},
                 "points": [{"args": [["int", 1]], "expected": ["int", 1]},
                            {"args": [["int", 30]], "expected": ["int", 900]},
                            {"args": [["int", 40]], "expected": ["int", 1600]}]}}


class Refusals(unittest.TestCase):
    def test_a_point_count_that_differs_from_the_pool_is_refused(self):
        record = {"name": "x", "points": [{"verdict": "pass"}] * 4}
        with self.assertRaises(ValueError):
            example_holdout.split_rates({"7": record}, 2, FAKE_POOL)

    def test_an_id_outside_the_pool_is_refused(self):
        record = {"name": "x", "points": [{"verdict": "pass"}] * 3}
        with self.assertRaises(ValueError):
            example_holdout.split_rates({"8": record}, 2, FAKE_POOL)

    def test_no_pool_is_refused_rather_than_falling_back_to_the_first_two(self):
        record = {"name": "x", "points": [{"verdict": "pass"}] * 3}
        with self.assertRaises(ValueError):
            example_holdout.split_rates({"7": record}, 2, None)

    def test_a_reconstruction_that_differs_from_the_prompt_builder_raises(self):
        with mock.patch.object(loop_locallm, "examples", side_effect=lambda entry, n=2: "Example: sq(1) == 1\n"):
            with self.assertRaises(ValueError):
                example_holdout.shown_indices(FAKE_POOL[7], 2)


class Report(unittest.TestCase):
    def test_report_end_to_end_and_the_prompt_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "t1" / "raw").mkdir(parents=True)
            tests = {"7": {"name": "mbpp_7__sq", "points": [{"verdict": "fail"}, {"verdict": "pass"},
                                                               {"verdict": "pass"}]}}
            (root / "t1" / "tests.json").write_text(json.dumps(tests), encoding="utf-8")
            head = loop_locallm.problem_head(FAKE_POOL[7], True)
            (root / "t1" / "raw" / "7.json").write_text(json.dumps(
                {"task_id": 7, "messages": [{"role": "user", "content": head}]}), encoding="utf-8")
            r = example_holdout.report("t1", 2, root, FAKE_POOL)
            self.assertEqual((r["visible_rate"], r["held_out_rate"], r["gap_points"]), (1.0, 0.0, 100.0))
            self.assertEqual(r["passed_all_shown_and_none_held"], 1)
            self.assertEqual(r["prompts_with_examples"], 1)
            self.assertEqual(r["shown_rule"], "loop_locallm.examples (discriminative pair)")
            # a prompt whose Example lines are not the recomputed pair is refused, not rescored
            (root / "t1" / "raw" / "7.json").write_text(json.dumps(
                {"task_id": 7, "messages": [{"role": "user", "content": "Problem: square it\nExample: sq(1) == 1\n"}]}),
                encoding="utf-8")
            with self.assertRaises(ValueError):
                example_holdout.report("t1", 2, root, FAKE_POOL)


if __name__ == "__main__":
    unittest.main()
