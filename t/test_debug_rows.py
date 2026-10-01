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


class SpecificationWitness(unittest.TestCase):
    """The specification check's own witness, in words (VeriMed, arXiv:2605.13817: the concrete
    counterexample is what drives repair, 98.5% against 58.5% for a generic retry)."""

    def setUp(self):
        import random
        import surface
        self.random, self.surface = random, surface
        self.entry = {"fn": "remove_upper", "rec": {"code": "def remove_upper(s):\n    return ''.join(c for c in s if not c.isupper())\n",
                                                    "test_list": ['assert remove_upper("aBc") == "ac"'], "text": ""},
                      "points": [{"ok": True, "fn": "remove_upper", "args": [["seq", [97, 66, 99]]], "expected": ["seq", [97, 99]]}]}

    def task(self, ensures):
        return self.surface.parse("t 1\ntask remove_upper(s: seq) returns (r: seq)\n" + "".join(f"  ensures {e}\n" for e in ensures)
                                  + "{\n  r := s;\n}\n")

    def check(self, task):
        return spec_check.check_task(task, self.entry, 100, self.random.Random(1))

    def test_a_weak_specification_is_told_a_wrong_output_it_also_accepts_in_the_problems_notation(self):
        task = self.task(["len(r) <= len(s)", "forall k in [0, len(r)) . r[k] < 65 or r[k] > 90"])
        result = self.check(task)
        self.assertEqual(result["status"], "agrees")
        said = debug_rows.spec_message(self.entry, task, result)
        self.assertTrue(said.startswith(debug_rows.SPEC_WEAK))
        self.assertIn("remove_upper('", said)                       # the call, with a string as a string
        self.assertIn("the answer is '", said)
        self.assertIn("also accepts '", said)

    def test_a_false_specification_is_told_the_input_the_answer_and_the_clause(self):
        task = self.task(["len(r) == len(s)"])
        result = self.check(task)
        self.assertEqual(result["status"], "disagrees")
        said = debug_rows.spec_message(self.entry, task, result)
        self.assertTrue(said.startswith(debug_rows.SPEC_WRONG))
        self.assertIn("this clause does not hold there:\n  ensures len(r) == len(s)", said)

    def test_a_right_and_complete_specification_gets_no_message(self):
        task = self.surface.parse("t 1\ntask remove_upper(s: seq) returns (r: seq)\n  ensures r == s\n{\n  r := s;\n}\n")
        lower = dict(self.entry, rec=dict(self.entry["rec"], code="def remove_upper(s):\n    return s\n"))
        result = spec_check.check_task(task, lower, 100, self.random.Random(1))
        self.assertEqual((result["status"], result.get("completeness")), ("agrees", 1.0))
        self.assertIsNone(debug_rows.spec_message(lower, task, result))

    def test_a_verdict_without_a_witness_or_one_that_does_not_render_says_nothing(self):
        task = self.task(["len(r) <= len(s)"])
        self.assertIsNone(debug_rows.spec_message(self.entry, task, {"status": "disagrees"}))
        self.assertIsNone(debug_rows.spec_message(self.entry, task, {"status": "agrees", "completeness": 0.1}))
        self.assertIsNone(debug_rows.spec_message(self.entry, task, {"status": "no valid draws"}))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
