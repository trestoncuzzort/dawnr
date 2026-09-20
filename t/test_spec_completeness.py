"""A specification true of the right answer and of a wrong one says nothing.

The soundness half of spec_check asks whether the ensures holds when the
problem's own solution supplies the result. These tests cover the completeness
half, after arXiv 2603.17150: mutate the output and require the ensures to
fail. A specification that cannot tell a right answer from a wrong one is
exactly what this project's proven-but-wrong column is made of, 59 to 204
answers a round.
"""
import random
import unittest

import spec_check
import surface

REFERENCE = "def f(x):\n    return x * 2\n"


def entry(args, expected, code=REFERENCE, fn="f"):
    return {"fn": fn, "rec": {"code": code, "text": "double it"},
            "points": [{"args": args, "expected": expected}]}


def task_of(ensures, params="x: int", ret="r: int"):
    return surface.parse(f"t 1\ntask probe({params}) returns ({ret})\n"
                         f"  ensures {ensures}\n{{\n  r := x;\n}}\n")


class MutationTests(unittest.TestCase):
    def test_a_wrong_answer_is_never_the_right_one(self):
        for value in (5, 0, -3, True, False, (), (1, 2, 3), ((1,), (2,))):
            self.assertNotIn(value, spec_check.mutations(value), repr(value))

    def test_mutations_are_deterministic(self):
        self.assertEqual(spec_check.mutations((1, 2)), spec_check.mutations((1, 2)))

    def test_a_dropped_element_is_a_wrong_sequence(self):
        self.assertIn((1, 2), spec_check.mutations((1, 2, 3)))

    def test_an_empty_sequence_still_has_a_wrong_answer(self):
        self.assertTrue(spec_check.mutations(()))


class CompletenessTests(unittest.TestCase):
    def check(self, ensures, args=(("int", 4),), expected=("int", 8), **kw):
        return spec_check.check_task(task_of(ensures, **kw), entry(list(args), list(expected)),
                                     6, random.Random(1))

    def test_a_strong_specification_rejects_every_wrong_answer(self):
        result = self.check("r == x * 2")
        self.assertEqual(result["status"], "agrees")
        self.assertEqual(result["mutants_accepted"], 0)
        self.assertFalse(result["weak"])
        self.assertEqual(result["completeness"], 1.0)

    def test_a_weak_specification_is_caught_with_its_witness(self):
        result = self.check("r >= 0")
        self.assertEqual(result["status"], "agrees")       # sound: true of every right answer
        self.assertTrue(result["weak"])                    # and true of wrong ones too
        self.assertGreater(result["mutants_accepted"], 0)
        self.assertIn("also_accepts", result["weak_witness"])

    def test_the_weakest_specification_of_all_is_caught(self):
        result = self.check("r == r")
        self.assertTrue(result["weak"])
        self.assertEqual(result["mutants_rejected"], 0)
        self.assertEqual(result["completeness"], 0.0)

    def test_a_sequence_specification_notices_a_dropped_element(self):
        result = spec_check.check_task(
            task_of("len(r) == len(s)", params="s: seq", ret="r: seq"),
            entry([["seq", [1, 2, 3]]], ["seq", [1, 2, 3]],
                  code="def f(s):\n    return list(s)\n"),
            4, random.Random(1))
        self.assertEqual(result["status"], "agrees")
        self.assertGreater(result["mutants_rejected"], 0)

    def test_completeness_never_changes_the_soundness_verdict(self):
        # A specification that disagrees with the problem must still read
        # disagrees, with the same keys it always had.
        result = self.check("r == x * 3")
        self.assertEqual(result["status"], "disagrees")
        self.assertIn("reference_said", result)
        self.assertNotIn("weak", result)


if __name__ == "__main__":
    unittest.main()


class ExampleConsistencyTests(unittest.TestCase):
    """Clover's third edge: the specification against the problem's own examples."""

    def points(self, ensures, args, expected, params="x: int", ret="r: int"):
        return spec_check.check_points(task_of(ensures, params=params, ret=ret),
                                       entry([list(a) for a in args], list(expected)))

    def test_a_specification_that_matches_the_example_holds(self):
        out = self.points("r == x * 2", [("int", 4)], ("int", 8))
        self.assertEqual(out["points_failed"], 0)
        self.assertGreater(out["points_held"], 0)

    def test_a_specification_of_another_function_contradicts_the_example(self):
        out = self.points("r == x + 1", [("int", 4)], ("int", 8))
        self.assertGreater(out["points_failed"], 0)
        self.assertEqual(out["contradicts_example"]["expected"], 8)

    def test_a_predicate_problem_answered_with_arithmetic_is_caught(self):
        # The real shape of the failure, from locallm-r7b-greedy on 2026-09-20:
        # the problem asks a yes/no question and the model specified r == x + 1.
        out = self.points("r == x + 1", [("int", 4)], ("bool", True), ret="r: bool")
        self.assertGreater(out["points_failed"], 0)

    def test_a_point_the_task_cannot_be_asked_about_is_skipped_not_failed(self):
        out = self.points("r == x * 2", [("int", 1), ("int", 2)], ("int", 2))
        self.assertEqual(out["points_failed"], 0)
        self.assertEqual(out["points_held"], 0)

    def test_it_says_nothing_outside_the_specification_s_own_precondition(self):
        task = surface.parse("t 1\ntask probe(x: int) returns (r: int)\n"
                             "  requires x > 100\n  ensures r == x * 2\n{\n  r := x;\n}\n")
        out = spec_check.check_points(task, entry([["int", 4]], ["int", 8]))
        self.assertEqual(out["points_failed"], 0)
        self.assertEqual(out["points_held"], 0)
