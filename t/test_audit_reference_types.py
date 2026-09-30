"""audit_reference_types (2026-09-30): a reference handed a string as a list of integers can
raise (known), agree, or silently compute another function (MBPP 771 became "even length").
Three synthetic problems, one per class. EvalPlus keeps a str a str when it grows inputs
(arXiv:2305.01210, https://github.com/evalplus/evalplus). No torch, no kernel."""
from __future__ import annotations

import signal
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit_reference_types as audit  # noqa: E402


def entry(code: str, example: str = "banana", call: str = 'f("banana")') -> dict:
    return {"fn": "f", "rec": {"task_id": 1, "text": "x", "code": code, "test_list": [f"assert {call} == 0"]},
            "points": [{"ok": True, "fn": "f", "args": [("seq", [ord(c) for c in example])], "expected": ("int", 0)}]}


@unittest.skipUnless(hasattr(signal, "SIGALRM"), "the reference is called under an alarm, as spec_check does")
class ReferenceTypes(unittest.TestCase):
    def test_a_character_comparison_silently_differs(self):
        r = audit.classify(entry("def f(s):\n    return sum(1 for c in s if c == 'a')"), draws=200, seed=1)
        self.assertEqual(r["class"], "differs", r)
        self.assertEqual(r["raised"], 0)
        self.assertEqual(r["witness"]["on_integers"], 0)          # no integer ever equals 'a'
        self.assertGreater(r["witness"]["on_the_string"], 0)

    def test_a_string_method_raises_on_every_draw(self):
        r = audit.classify(entry("def f(s):\n    return s.upper()"), draws=50, seed=1)
        self.assertEqual((r["class"], r["raised"], r["differs"], r["same"]), ("raises", 50, 0, 0))

    def test_a_type_blind_reference_is_the_same(self):
        r = audit.classify(entry("def f(s):\n    return len(s)"), draws=50, seed=1)
        self.assertEqual((r["class"], r["same"]), ("same", 50))

    def test_a_returned_character_is_the_same_answer_either_way(self):
        # an int from the integer call, a one-character str from the string call
        r = audit.classify(entry("def f(s):\n    return s[0] if s else 'x'"), draws=50, seed=1)
        self.assertEqual((r["class"], r["differs"]), ("same", 0), r)
        r = audit.classify(entry("def f(s):\n    return [c for c in s]"), draws=50, seed=1)
        self.assertEqual((r["class"], r["differs"]), ("same", 0), r)

    def test_a_character_argument_is_passed_as_a_character(self):
        e = {"fn": "f", "rec": {"task_id": 1, "text": "x", "code": "def f(s, ch):\n    return s.count(ch)",
                                "test_list": ['assert f("banana", "a") == 3']},
             "points": [{"ok": True, "fn": "f", "args": [("seq", [ord(c) for c in "banana"]), ("int", 97)],
                         "expected": ("int", 3)}]}
        self.assertEqual(audit.str_positions(e), [0, 1])
        r = audit.classify(e, draws=50, seed=1)
        self.assertEqual((r["class"], r["differs"], r["raised"]), ("same", 0, 0), r)

    def test_a_problem_without_a_string_argument_is_not_audited(self):
        e = entry("def f(s):\n    return len(s)", call="f([1, 2, 3])")
        self.assertEqual(audit.str_positions(e), [])
        self.assertIsNone(audit.classify(e))


class StrPositions(unittest.TestCase):
    def test_positions_come_from_the_problem_s_own_assertion(self):
        e = {"fn": "g", "rec": {"test_list": ["assert g(3, 'ab', [1]) == 1"]}}
        self.assertEqual(audit.str_positions(e), [1])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
