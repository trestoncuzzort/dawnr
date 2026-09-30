"""spec_check calls a string problem's reference with a str (2026-09-30, receipt ad806d032e1a).

t represents a string as a seq of code points. Before this the check handed the Python reference
that list; a solution comparing against character literals then ran and computed another function
(MBPP 771's bracket balancer answered "the length is even"), and one that called a str method
raised and was skipped. Now the arguments are rebuilt the way the problem's own assertions pass
them (spec_check.python_arguments), and outputs are read the way the pool reads assertion values
(to_t: a one-character str is a character, a list of characters is a flat seq). EvalPlus keeps a
str a str when it grows test inputs (arXiv:2305.01210). No torch, no kernel."""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_check  # noqa: E402
import surface  # noqa: E402


def entry(fn, code, call, args, expected):
    return {"fn": fn, "rec": {"task_id": 1, "text": "x", "code": code, "test_list": [f"assert {call} == {expected!r}"]},
            "points": [{"ok": True, "fn": fn, "args": args, "expected": expected_kind(expected)}]}


def expected_kind(v):
    if isinstance(v, bool):
        return ("bool", v)
    if isinstance(v, int):
        return ("int", v)
    if isinstance(v, str):
        return ("int", ord(v)) if len(v) == 1 else ("seq", [ord(c) for c in v])
    return ("seq", [ord(c) if isinstance(c, str) else c for c in v])


BALANCED = '''from collections import deque
def check_expression(exp):
    if len(exp) & 1:
        return False
    stack = deque()
    for ch in exp:
        if ch == '(' or ch == '{' or ch == '[':
            stack.append(ch)
        if ch == ')' or ch == '}' or ch == ']':
            if not stack:
                return False
            top = stack.pop()
            if (top == '(' and ch != ')') or (top == '{' and ch != '}') or (top == '[' and ch != ']'):
                return False
    return not stack
'''
EVEN_LENGTH = "t 1\ntask check_expression(s: seq) returns (r: bool)\n  ensures r == (len(s) % 2 == 0)\n{\n  r := len(s) % 2 == 0;\n}"


class Arguments(unittest.TestCase):
    def test_positions_and_rebuilt_arguments(self):
        e = entry("remove_Occ", "def remove_Occ(s, ch):\n    return s.replace(ch, '', 1)", 'remove_Occ("hello", "l")',
                  [("seq", [104, 101, 108, 108, 111]), ("int", 108)], "helo")
        self.assertEqual(spec_check.string_positions(e), [0, 1])
        self.assertEqual(spec_check.python_arguments([[104, 105], 108], [0, 1]), ["hi", "l"])
        self.assertEqual(spec_check.python_arguments([[1, 2], 3], []), [[1, 2], 3])

    def test_outputs_read_as_the_pool_reads_assertions(self):
        self.assertEqual(spec_check.to_t("a", "int"), 97)          # a character where an int is declared
        self.assertEqual(spec_check.to_t("a", "seq"), (97,))       # a one-character string where a seq is
        self.assertEqual(spec_check.to_t("ab"), (97, 98))
        self.assertEqual(spec_check.to_t(["p", "y"]), (112, 121))  # split('python'): a flat seq of characters
        self.assertEqual(spec_check.to_t(["ab", "c"], "seq-of-seq"), ((97, 98), (99,)))
        self.assertEqual(spec_check.to_t([1, 2]), (1, 2))
        self.assertEqual(spec_check.to_t(True), True)


class TheBracketBalancer(unittest.TestCase):
    def test_even_length_no_longer_agrees_with_the_balancer(self):
        e = entry("check_expression", BALANCED, 'check_expression("{()}[{}]")',
                  [("seq", [123, 40, 41, 125, 91, 123, 125, 93])], True)
        r = spec_check.check_task(surface.parse(EVEN_LENGTH), e, 200, random.Random(771))
        self.assertEqual(r["status"], "disagrees", r)

    def test_a_string_method_reference_now_runs(self):
        e = entry("upper_all", "def upper_all(s):\n    return s.upper()", 'upper_all("ab")', [("seq", [97, 98])], "AB")
        task = surface.parse("t 1\ntask upper_all(s: seq) returns (r: seq)\n  ensures len(r) == len(s)\n{\n  r := s;\n}")
        r = spec_check.check_task(task, e, 100, random.Random(1))
        self.assertEqual(r["status"], "agrees", r)
        self.assertGreater(r["draws"], 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
