"""chat_eval.spec_agreement (2026-09-29): a dev answer's specification against the problem's
own solution on drawn inputs, the held-out scorer's step-8 check brought to the dev split.
A parity program agrees with an is-odd problem and disagrees with a problem whose solution
is not parity even when both shown examples happen to agree; no program and an unparseable
program are the check's own refusals, never counted. No torch, no kernel."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "t"))

import chat_eval  # noqa: E402

PARITY = "t 1\ntask f(n: int) returns (r: bool)\n  ensures r == (n % 2 == 1)\n{\n  r := n % 2 == 1;\n}"


def _entry(code: str) -> dict:
    return {"fn": "f", "rec": {"task_id": 1, "text": "x", "code": code, "test_list": ["assert f(5) == True", "assert f(10) == False"]},
            "points": [{"ok": True, "fn": "f", "args": [("int", 5)], "expected": ("bool", True)},
                       {"ok": True, "fn": "f", "args": [("int", 10)], "expected": ("bool", False)}]}


class SpecAgreement(unittest.TestCase):
    def test_parity_agrees_with_is_odd(self):
        r = chat_eval.spec_agreement(PARITY, _entry("def f(n):\n    return n % 2 == 1"), n=100, seed=1)
        self.assertEqual(r["status"], "agrees", r)
        self.assertGreater(r["draws"], 0)

    def test_parity_disagrees_with_difference_of_squares_despite_the_shown_examples(self):
        # n is a difference of two squares iff n % 4 != 2: 5 and 10 agree with parity, 4 does not
        r = chat_eval.spec_agreement(PARITY, _entry("def f(n):\n    return n % 4 != 2"), n=200, seed=1)
        self.assertEqual(r["status"], "disagrees", r)
        self.assertIn("args", r)

    def test_refusals_are_named_not_counted(self):
        self.assertEqual(chat_eval.spec_agreement(None, _entry("def f(n):\n    return True"))["status"], "no program")
        self.assertEqual(chat_eval.spec_agreement("t 1\ntask f(", _entry("def f(n):\n    return True"))["status"], "parse")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
