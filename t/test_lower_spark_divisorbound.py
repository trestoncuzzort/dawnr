"""t/test_lower_spark_divisorbound.py: unit tests for the divisor-bound
family wiring in lower_spark.py (ROADMAP 16.2, spark's own item,
2026-09-12). No kernel binary is invoked here (that measurement is done
separately, `python3 grade.py --tasks ... --kernels spark,dafny` against
the two dafny-synthesis tasks, and against t/tasks/ for the regression
bar); this file checks only the Python-level shape detection
(`_divisor_bound_target`/`_find_divisor_bound_plan`, ported the same way
lower_fstar.py's/lower_lean.py's own copies are) and that the emitted
source for isPrime/isNonPrime actually calls the generated lemma family
at the loop's own post-loop state, while an unrelated task (`gcd`, the
committed `is_prime.t`, which trial-divides to `n` rather than `n div 2`)
is left untouched.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lower_spark

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

ISNONPRIME = {
    "t": 1,
    "name": "dafny_synthesis_task_id_3__isNonPrime",
    "params": [{"name": "n", "type": "int"}],
    "returns": [{"name": "result", "type": "bool"}],
    "requires": [{"op": ">=", "args": [{"var": "n"}, {"int": 2}]}],
    "ensures": [{"op": "==", "args": [
        {"var": "result"},
        {"exists": {"var": "k", "lo": {"int": 2}, "hi": {"var": "n"},
                    "body": {"op": "==", "args": [
                        {"op": "mod", "args": [{"var": "n"}, {"var": "k"}]},
                        {"int": 0}]}}}]}],
    "gate": "loops",
    "body": [
        {"assign": ["result", {"bool": False}]},
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
                    {"exists": {"var": "k_v", "lo": {"int": 2},
                                "hi": {"var": "i"},
                                "body": {"op": "==", "args": [
                                    {"op": "mod", "args": [
                                        {"var": "n"}, {"var": "k_v"}]},
                                    {"int": 0}]}}}]},
            ],
            "body": [
                {"if": {
                    "cond": {"op": "==", "args": [
                        {"op": "mod", "args": [{"var": "n"}, {"var": "i"}]},
                        {"int": 0}]},
                    "then": [{"assign": ["result", {"bool": True}]},
                             {"return": ["result", {"var": "result"}]}],
                    "else": []}},
                {"assign": ["i", {"op": "+", "args": [
                    {"var": "i"}, {"int": 1}]}]},
            ],
        }},
    ],
}


class TestDivisorBoundTarget(unittest.TestCase):
    def test_detects_isprime_shape(self):
        w = ISPRIME["body"][2]["while"]
        plan = lower_spark._divisor_bound_target(ISPRIME, w)
        self.assertIsNotNone(plan)
        self.assertEqual(plan["kind"], "forall")
        self.assertEqual(plan["relop"], "!=")
        self.assertEqual(plan["i_name"], "i")
        self.assertEqual(plan["result"], "result")
        self.assertEqual(plan["dividend"], {"var": "n"})

    def test_detects_isnonprime_shape(self):
        w = ISNONPRIME["body"][2]["while"]
        plan = lower_spark._divisor_bound_target(ISNONPRIME, w)
        self.assertIsNotNone(plan)
        self.assertEqual(plan["kind"], "exists")
        self.assertEqual(plan["relop"], "==")

    def test_find_plan_matches_target(self):
        plan = lower_spark._find_divisor_bound_plan(ISPRIME, ISPRIME["body"])
        self.assertIsNotNone(plan)
        self.assertEqual(plan["i_name"], "i")

    def test_no_match_on_unrelated_task(self):
        # gcd has no `result == Quant(...)` ensures at all.
        gcd = {
            "name": "gcd",
            "returns": [{"name": "r", "type": "int"}],
            "ensures": [{"op": ">", "args": [{"var": "r"}, {"int": 0}]}],
        }
        w = {"cond": {"op": "<", "args": [{"var": "a"}, {"var": "b"}]},
             "invariants": [], "body": []}
        self.assertIsNone(lower_spark._divisor_bound_target(gcd, w))

    def test_no_match_when_cond_bound_differs(self):
        # Same ensures/invariant shape, but the loop trial-divides to a
        # DIFFERENT bound (`n` itself, not `n div 2`) -- must not match,
        # since the widening lemma this fix emits is specific to the
        # half-bound family and a task that already trial-divides the
        # full range needs no such lemma (t/tasks/is_prime.t's own shape).
        import copy
        task = copy.deepcopy(ISPRIME)
        w = task["body"][2]["while"]
        w["cond"] = {"op": "<=", "args": [{"var": "i"}, {"var": "n"}]}
        self.assertIsNone(lower_spark._divisor_bound_target(task, w))

    def test_spark_unrelated_committed_task_unchanged(self):
        import tasks_io
        path = os.path.join(os.path.dirname(__file__), "tasks", "is_prime.t")
        if not os.path.exists(path):
            self.skipTest("t/tasks/is_prime.t not present in this worktree")
        task = tasks_io.load_task(path)
        w = next((s["while"] for s in task["body"] if "while" in s), None)
        self.assertIsNotNone(w)
        self.assertIsNone(lower_spark._divisor_bound_target(task, w))


class TestDivisorBoundLowering(unittest.TestCase):
    def test_isprime_lowering_calls_the_lemma_at_the_return_site(self):
        src = lower_spark.lower(ISPRIME, ISPRIME["body"])
        self.assertIn("Divisor_Bound_Lemma", src)
        self.assertIn("Divisor_Le_Half_Lemma", src)
        self.assertIn("Divisor_Bound_Range_Lemma", src)
        # The call site reads the loop's own post-loop counter (`.I`) and
        # result (`.Result`) off the W_k helper's own return value, not a
        # fresh/unrelated name.
        self.assertIn("W_1 (N, True, Big_Integer'(2)).I", src)
        self.assertIn("Divisor_Bound_Lemma (N, "
                      "W_1 (N, True, Big_Integer'(2)).I, "
                      "W_1 (N, True, Big_Integer'(2)).Result)", src)
        # Never a bare admit/assume-style escape for the obligation this
        # lemma proves (SPARK has no `assume`/`admit`; this is the
        # honesty rule's own general form for this kernel).
        self.assertNotIn("pragma Assume", src)

    def test_isnonprime_lowering_calls_the_exists_lemma(self):
        src = lower_spark.lower(ISNONPRIME, ISNONPRIME["body"])
        self.assertIn("Divisor_Bound_Lemma", src)
        self.assertIn("for some Kx", src)
        self.assertIn("for some K in T_Range", src)

    def test_isprime_reserves_the_lemma_names(self):
        # A t identifier that would capitalize onto one of the lemma
        # family's own names must be refused, the same collision check
        # ROTATE_LEMMA_PREAMBLE's own names already get (ROADMAP 16.2,
        # 2026-09-12, the note above `rotate_target`'s computation).
        import copy
        task = copy.deepcopy(ISPRIME)
        task["params"] = [{"name": "divisor_bound_lemma", "type": "int"}]
        # Not a faithful task any more (the body still reads `n`), but the
        # collision check runs before compile() ever needs the body to be
        # semantically consistent -- it only needs `divisor_target` to
        # match against the WHILE loop still present, and the renamed
        # param name to collide case-insensitively with a reserved name.
        with self.assertRaises(NotImplementedError):
            lower_spark.lower(task, task["body"])

    def test_gcd_unaffected_no_lemma_emitted(self):
        gcd = {
            "t": 1,
            "name": "gcd",
            "params": [{"name": "a", "type": "int"},
                      {"name": "b", "type": "int"}],
            "returns": [{"name": "r", "type": "int"}],
            "requires": [{"op": ">", "args": [{"var": "a"}, {"int": 0}]},
                        {"op": ">", "args": [{"var": "b"}, {"int": 0}]}],
            "ensures": [{"op": ">", "args": [{"var": "r"}, {"int": 0}]}],
            "gate": "loops",
            "body": [
                {"var": {"name": "x", "type": "int", "init": {"var": "a"}}},
                {"var": {"name": "y", "type": "int", "init": {"var": "b"}}},
                {"while": {
                    "cond": {"op": "!=", "args": [{"var": "y"}, {"int": 0}]},
                    "decreases": {"var": "y"},
                    "invariants": [
                        {"op": ">", "args": [{"var": "x"}, {"int": 0}]},
                        {"op": ">=", "args": [{"var": "y"}, {"int": 0}]}],
                    "body": [
                        {"var": {"name": "t0", "type": "int",
                                "init": {"var": "y"}}},
                        {"assign": ["y", {"op": "mod", "args": [
                            {"var": "x"}, {"var": "y"}]}]},
                        {"assign": ["x", {"var": "t0"}]},
                    ],
                }},
                {"assign": ["r", {"var": "x"}]},
            ],
        }
        src = lower_spark.lower(gcd, gcd["body"])
        self.assertNotIn("Divisor_Bound_Lemma", src)


if __name__ == "__main__":
    unittest.main()
