"""t/student_loop.py (2026-10-01): the cheap checks between rounds are extract's and tests' own
verdicts on one reply, and only a refused attempt with something to show is sent back (SAFE's
self-debugging, arXiv:2410.15756 section 3.3). No model, no kernel."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import debug_rows  # noqa: E402
import spec_experiment as se  # noqa: E402
import student_loop  # noqa: E402

POOL = {str(k): v for k, v in se.pool("v5").items()}
TID = "17"                                              # square_perimeter(10) == 40
GOOD = "```t\nt 0\ntask f(side: int) returns (r: int)\n  ensures r == 4 * side\n{\n  r := 4 * side;\n}\n```"


class CheapCheck(unittest.TestCase):
    def check(self, reply):
        return student_loop.cheap_check(reply, POOL[TID], TID)

    def test_a_right_answer_passes_and_is_not_sent_back(self):
        c = self.check(GOOD)
        self.assertTrue(student_loop.passed(c))

    def test_a_wrong_program_fails_its_tests_and_the_message_names_the_values(self):
        c = self.check(GOOD.replace("4 * side", "3 * side"))
        self.assertEqual((c["stage"], c["tests"]["overall"]), ("task", "fail"))
        kind, said = debug_rows.message_for(c["stage"], c["why"], c["tests"], None, None)
        self.assertEqual(kind, "tests")
        self.assertIn("40", said)

    def test_an_unparseable_reply_carries_the_parsers_message_and_its_own_text(self):
        c = self.check(GOOD.replace("r := 4 * side;", "r := for side;"))
        self.assertEqual(c["stage"], "parse")
        self.assertIn("for", c["why"])
        self.assertIn("for side", c["attempt"])

    def test_a_v0_line_over_a_v1_body_is_read_as_v1(self):
        reply = "```t\nt 0\ntask f(side: int) returns (r: int)\n  ensures r == 4 * side\n{\n  var k: int := 4;\n  r := k * side;\n}\n```"
        c = self.check(reply)
        self.assertTrue(student_loop.passed(c), c)

    def test_a_reply_with_no_task_has_nothing_to_send_back(self):
        c = self.check("I cannot do that.")
        self.assertEqual(c["stage"], "no-block")
        self.assertIsNone(c["attempt"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
