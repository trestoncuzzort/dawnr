"""t/graded_pool.py (2026-10-01): the student's training pool at a stated trust level.

SAFE (arXiv:2410.15756) trains on proofs ONE verifier accepted, with specifications filtered by
tests and mutants; this gate asks for at least K of seven, no kernel refuting, the tests and a
current hash-bound specification verdict, and records the level on every row. The seven-kernel
gate in t/loop_dataset.py is not touched. These tests fix what each gate refuses. No kernel."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import graded_pool  # noqa: E402
import spec_check  # noqa: E402
from test_loop_dataset import evidence, sample  # noqa: E402


def with_row(s, **cells):
    out = copy.deepcopy(s)
    out["kernel_row"].update(cells)
    return out


class Gate(unittest.TestCase):
    def test_all_seven_is_admitted_at_every_level(self):
        s = sample()
        for k in (1, 5, 7):
            self.assertIsNone(graded_pool.rejection(s, evidence(s), "v5", k))

    def test_a_kernel_that_could_not_decide_lowers_the_level_and_nothing_else(self):
        s = with_row(sample(), spark="timeout / refuted", framac="abstain / abstain")
        self.assertEqual(graded_pool.kernel_level(s), (5, [], ["spark", "framac"]))
        self.assertIsNone(graded_pool.rejection(s, evidence(s), "v5", 5))
        self.assertEqual(graded_pool.rejection(s, evidence(s), "v5", 6), "proved-by-fewer-than-6")

    def test_a_kernel_that_refutes_the_program_refuses_it_at_every_level(self):
        s = with_row(sample(), lean="refuted / refuted")
        for k in (1, 6):
            self.assertEqual(graded_pool.rejection(s, evidence(s), "v5", k), "a-kernel-refutes-the-program")

    def test_a_twin_that_was_not_refuted_does_not_count_as_a_proof(self):
        s = with_row(sample(), **{k: "verified / verified" for k in spec_check.KERNELS})
        self.assertEqual(graded_pool.rejection(s, evidence(s), "v5", 1), "proved-by-fewer-than-1")

    def test_tests_and_specification_evidence_are_required_at_the_lowest_level(self):
        s = sample()
        failing = dict(s, tests_pass=False)
        self.assertEqual(graded_pool.rejection(failing, evidence(s), "v5", 1), "tests-not-passing")
        self.assertEqual(graded_pool.rejection(s, {}, "v5", 1), "spec-unchecked")
        key = f"{s['tag']}/{s['name']}"
        for change, expected in (({"status": "disagrees"}, "spec-not-agrees"),
                                 ({"draws": 0}, "spec-no-valid-draws"),
                                 ({"draws": graded_pool.MIN_AGREEING_DRAWS - 1}, "spec-agrees-on-too-few-draws"),
                                 ({"task_sha256": "0" * 64}, "spec-hash-missing-or-stale"),
                                 ({"pool": "v4"}, "spec-pool-mismatch"),
                                 ({"points_failed": 1}, "spec-contradicts-example")):
            ev = evidence(s)
            ev[key].update(change)
            self.assertEqual(graded_pool.rejection(s, ev, "v5", 1), expected, change)

    def test_the_answer_names_the_task_as_the_prompt_asks_and_its_self_calls_follow(self):
        import surface
        task = surface.parse("t 1\ngate recursion\ntask mbpp_9__fact(n: int) returns (r: int)\n"
                             "  requires n >= 0\n  ensures r >= 1\n  decreases n\n{\n"
                             "  if n == 0 { r := 1; } else { r := mbpp_9__fact(n - 1); r := r * n; }\n}\n")
        before = spec_check.task_sha256(task)
        text = graded_pool.answer_text(task, "fact")
        self.assertIn("task fact(n: int)", text)
        self.assertIn("r := fact(n - 1)", text)
        self.assertNotIn("mbpp_9__", text)
        self.assertEqual(spec_check.task_sha256(task), before)          # the graded task is untouched

    def test_a_name_the_surface_syntax_cannot_print_keeps_the_internal_one(self):
        import surface
        task = surface.parse("t 0\ntask mbpp_3__f(a: int) returns (r: int)\n  ensures r == a\n{ r := a; }\n")
        self.assertIn("task mbpp_3__f(", graded_pool.answer_text(task, "task"))

    def test_the_level_is_one_to_seven(self):
        for bad in (0, 8):
            with self.assertRaises(SystemExit):
                graded_pool.build([], HERE / "out" / "loop" / "split-v5.json", HERE / "nope.json", bad)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
