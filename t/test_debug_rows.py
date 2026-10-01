"""t/debug_rows.py (2026-10-01): what the gate says about a refused attempt, in the words the
student is trained on and later asked in (SAFE's debugging pairs, arXiv:2410.15756). No kernel."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import debug_rows  # noqa: E402
import spec_check  # noqa: E402

COLS = list(spec_check.KERNELS)
ALL = {k: "verified / refuted" for k in COLS}


class Message(unittest.TestCase):
    def test_a_parse_or_wellformedness_refusal_carries_the_checkers_own_words(self):
        kind, said = debug_rows.message_for("parse", "<string>:3:1: expected ']', found 'for'", None, None, None)
        self.assertEqual(kind, "parse")
        self.assertIn("expected ']', found 'for'", said)
        self.assertEqual(debug_rows.message_for("wf", "v0 has int only", None, None, None)[0], "wf")

    def test_a_failing_test_names_what_was_returned_and_what_was_expected(self):
        tests = {"overall": "fail", "points": [{"verdict": "pass", "got": 1, "expected": 1},
                                               {"verdict": "fail", "got": 6, "expected": 3}]}
        kind, said = debug_rows.message_for("task", None, tests, ALL, COLS)
        self.assertEqual(kind, "tests")
        self.assertIn("returns 6", said)
        self.assertIn("3 is expected", said)

    def test_a_signature_mismatch_is_a_tests_failure_with_its_reason(self):
        tests = {"overall": "signature", "points": [{"verdict": "arity", "why": "3 args for 2 params"}]}
        self.assertEqual(debug_rows.message_for("task", None, tests, None, None),
                         ("tests", "It does not fit the problem's tests: 3 args for 2 params"))

    def test_tests_pass_but_a_kernel_could_not_prove_it_lists_the_provers(self):
        row = dict(ALL, lean="unproved / refuted")
        kind, said = debug_rows.message_for("task", None, {"overall": "pass"}, row, COLS)
        self.assertEqual(kind, "proof")
        self.assertIn("Lean 4", said)

    def test_an_answer_the_gate_accepted_everywhere_is_not_an_attempt(self):
        self.assertIsNone(debug_rows.message_for("task", None, {"overall": "pass"}, ALL, COLS))
        self.assertIsNone(debug_rows.message_for("no-block", None, None, None, None))

    def test_a_very_long_attempt_is_left_out(self):
        self.assertIsNone(debug_rows.attempt_text({"wellformed": False, "malformed_text": "x" * 4000}))
        self.assertEqual(debug_rows.attempt_text({"wellformed": True, "text": "ok"}), "ok")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
