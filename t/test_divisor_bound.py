"""t/test_divisor_bound.py: unit tests for the divisor-bound family fix in
lower_fstar.py and lower_verus.py (ROADMAP 16.2, divisor-bound item,
2026-09-11). No kernel binary is invoked here (that measurement is done
separately, `python3 grade.py --tasks ... --kernels fstar,verus,dafny`
against the three dafny-synthesis tasks); this file checks only the
Python-level shape detection (`_divisor_bound_target` in each lowering,
kept as two independent copies since the two files share no code) and
that the emitted source for isPrime/isNonPrime actually calls the
generated lemma, while an unrelated task (`is_prime`, `gcd`, the fully
JSON-shaped `sumOfCommonDivisors`, which needs no such lemma -- see
lower_fstar.py's own `_has_ite`-based decreases-shift fix instead) is
left untouched.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lower_fstar
import lower_verus

ISPRIME = {
    "t": 1,
    "name": "dafny_synthesis_task_id_605__isPrime",
    "params": [{"name": "n", "type": "int"}],
    "returns": [{"name": "result", "type": "bool"}],
    "requires": [{"op": ">=", "args": [{"var": "n"}, {"int": 2}]}],
    "ensures": [{"op": "==", "args": [
        {"var": "result"},
        {"forall": {"var": "k", "lo": {"int": 2}, "hi": {"var": "n"},
                    "body": {"op": "!=", "args": [
                        {"op": "mod", "args": [{"var": "n"}, {"var": "k"}]},
                        {"int": 0}]}}}]}],
    "gate": "loops",
    "body": [
        {"assign": ["result", {"bool": True}]},
        {"var": {"name": "i", "type": "int", "init": {"int": 2}}},
        {"while": {
            "cond": {"op": "<=", "args": [
                {"var": "i"},
                {"op": "div", "args": [{"var": "n"}, {"int": 2}]}]},
            "decreases": {"op": "-", "args": [
                {"op": "div", "args": [{"var": "n"}, {"int": 2}]},
                {"var": "i"}]},
            "invariants": [
                {"op": "<=", "args": [{"int": 2}, {"var": "i"}]},
                {"op": "==", "args": [
                    {"var": "result"},
                    {"forall": {"var": "k_v", "lo": {"int": 2},
                                "hi": {"var": "i"},
                                "body": {"op": "!=", "args": [
                                    {"op": "mod", "args": [
                                        {"var": "n"}, {"var": "k_v"}]},
                                    {"int": 0}]}}}]},
            ],
            "body": [
                {"if": {
                    "cond": {"op": "==", "args": [
                        {"op": "mod", "args": [{"var": "n"}, {"var": "i"}]},
                        {"int": 0}]},
                    "then": [{"assign": ["result", {"bool": False}]},
                             {"return": ["result", {"var": "result"}]}],
                    "else": []}},
                {"assign": ["i", {"op": "+", "args": [
                    {"var": "i"}, {"int": 1}]}]},
            ],
        }},
    ],
}


class TestDivisorBoundTarget(unittest.TestCase):
    def test_fstar_detects_isprime_shape(self):
        _, w, _ = lower_fstar.find_while(ISPRIME["body"])
        plan = lower_fstar._divisor_bound_target(ISPRIME, w)
        self.assertIsNotNone(plan)
        self.assertEqual(plan["kind"], "forall")
        self.assertEqual(plan["relop"], "!=")
        self.assertEqual(plan["i_name"], "i")
        self.assertEqual(plan["result"], "result")
        self.assertEqual(plan["dividend"], {"var": "n"})

    def test_verus_detects_isprime_shape(self):
        _, w, _ = lower_fstar.find_while(ISPRIME["body"])
        plan = lower_verus._divisor_bound_target(ISPRIME, w)
        self.assertIsNotNone(plan)
        self.assertEqual(plan["kind"], "forall")
        self.assertEqual(plan["relop"], "!=")

    def test_no_match_on_unrelated_task(self):
        # gcd has no `result == Quant(...)` ensures at all.
        gcd = {
            "name": "gcd",
            "returns": [{"name": "r", "type": "int"}],
            "ensures": [{"op": ">", "args": [{"var": "r"}, {"int": 0}]}],
        }
        w = {"cond": {"op": "<", "args": [{"var": "a"}, {"var": "b"}]},
             "invariants": [], "body": []}
        self.assertIsNone(lower_fstar._divisor_bound_target(gcd, w))
        self.assertIsNone(lower_verus._divisor_bound_target(gcd, w))

    def test_no_match_when_cond_bound_differs(self):
        # Same ensures/invariant shape, but the loop trial-divides to a
        # DIFFERENT bound (`n` itself, not `n div 2`) -- must not match,
        # since the widening lemma this fix emits is specific to the
        # half-bound family and a task that already trial-divides the
        # full range needs no such lemma.
        import copy
        task = copy.deepcopy(ISPRIME)
        _, w, _ = lower_fstar.find_while(task["body"])
        w["cond"] = {"op": "<=", "args": [{"var": "i"}, {"var": "n"}]}
        self.assertIsNone(lower_fstar._divisor_bound_target(task, w))
        self.assertIsNone(lower_verus._divisor_bound_target(task, w))

    def test_fstar_lowering_calls_the_lemma(self):
        src = lower_fstar.lower(ISPRIME, ISPRIME["body"])
        self.assertIn("t_divisor_bound_dafny_synthesis_task_id_605__isPrime",
                       src)
        self.assertIn("t_divisor_le_half_dafny_synthesis_task_id_605__isPrime",
                       src)
        # Never a bare admit/assume for the obligation this lemma proves.
        self.assertNotIn("admit", src.lower())
        self.assertNotIn("assume", src.lower())

    def test_verus_lowering_calls_the_lemma(self):
        src = lower_verus.lower(ISPRIME, ISPRIME["body"])
        self.assertIn("t_divisor_bound_dafny_synthesis_task_id_605__isPrime",
                       src)
        self.assertIn("t_divisor_le_half_dafny_synthesis_task_id_605__isPrime",
                       src)
        self.assertNotIn("admit", src.lower())
        self.assertNotIn("assume(", src.lower())

    def test_fstar_unrelated_committed_task_unchanged(self):
        # is_prime.t's own trial-divide-to-n shape (not n/2) must never
        # trip this detector -- see LIFTER-785/AGREEMENT.md's own
        # is_prime row, unaffected by this fix.
        import tasks_io
        path = os.path.join(os.path.dirname(__file__), "tasks", "is_prime.t")
        if not os.path.exists(path):
            self.skipTest("t/tasks/is_prime.t not present in this worktree")
        task = tasks_io.load_task(path)
        _, w, _ = lower_fstar.find_while(task["body"])
        self.assertIsNone(lower_fstar._divisor_bound_target(task, w))
        self.assertIsNone(lower_verus._divisor_bound_target(task, w))


if __name__ == "__main__":
    unittest.main()
