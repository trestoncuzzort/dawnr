#!/usr/bin/env python3
"""The stdin pool's two claims, tested where they can actually fail.

`t/nl_stdin_pool.py` turns a stdin-shaped problem into a pool entry with a
CALLABLE reference, which is what `spec_check.reference()` needs and what
`nl_stdin.in_pool` does not provide. Two things have to hold or the entry is
worse than useless -- it becomes a problem no answer can ever be a positive for,
and nothing says so at grading time:

1. `render_stdin` must be the exact inverse of the grammar in `nl_stdin`. If it
   renders text the matchers read back as DIFFERENT arguments, the reference is
   being asked a different question than the model was, and every disagreement
   is charged to the model. So the round trip is tested per rule, through the
   real `to_lines` / `classify_lines` / `build_args`, not a copy of them.
2. A task id must be derived from the problem, not from the order problems were
   walked in. `loop_dataset.positive_rejection` rejects a sample whose recorded
   `task_id` does not match, so an id that moves between runs silently
   invalidates every result measured under an earlier one.

Stdlib only, no corpus on disk required: every fixture is built here.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import nl_stdin                                                  # noqa: E402
import nl_stdin_pool as pool                                     # noqa: E402


def round_trip(rule: str, args: list) -> tuple[str, list]:
    """args -> rendered stdin -> back through nl_stdin's own reader."""
    text = pool.render_stdin(rule, args)
    status, payload = nl_stdin.classify_lines(nl_stdin.to_lines(text))
    if status != "ok":
        raise AssertionError(f"{rule}: rendered text refused as {payload!r}\n{text!r}")
    return nl_stdin.label_from_key(nl_stdin.rule_key(payload)), nl_stdin.build_args(payload)


class TestRenderIsTheInverse(unittest.TestCase):
    """Every rule nl_stdin can accept, rendered and read back."""

    CASES = [
        ("a(k=1)", [["int", 7]]),
        ("a(k=3)", [["int", 1], ["int", -2], ["int", 300]]),
        ("b", [["int", 3], ["seq", [4, 5, 6]]]),
        ("c", [["int", 2], ["seq", [8, 9]]]),
        ("d", [["int", 2], ["int", 5], ["seq", [11, 12]]]),
    ]

    def test_rule_and_args_survive_the_round_trip(self):
        for rule, args in self.CASES:
            with self.subTest(rule=rule):
                got_rule, got_args = round_trip(rule, args)
                self.assertEqual(got_rule, rule)
                self.assertEqual(got_args, args)

    def test_b_and_c_are_not_confused(self):
        """Same args, different layout. Reading the args alone cannot tell them
        apart, which is why the label is carried rather than recomputed."""
        args = [["int", 2], ["seq", [4, 5]]]
        self.assertEqual(round_trip("b", args)[0], "b")
        self.assertEqual(round_trip("c", args)[0], "c")
        self.assertNotEqual(pool.render_stdin("b", args), pool.render_stdin("c", args))

    def test_single_case_wrapper_round_trips(self):
        """`e:` is a t==1 test-count line the extractor drops; rendering has to
        put it back or the solution reads the first value as the case count."""
        args = [["int", 3], ["seq", [1, 2, 3]]]
        text = pool.render_stdin("e:b", args)
        self.assertTrue(text.startswith("1\n"), text)
        got_rule, got_args = round_trip("e:b", args)
        self.assertEqual(got_args, args)
        self.assertIn(got_rule, ("e:b", "b"))   # the reader may drop the wrapper

    def test_an_unknown_rule_is_refused_not_guessed(self):
        with self.assertRaises(ValueError):
            pool.render_stdin("z", [["int", 1]])


SUM_SOLUTION = "a, b = map(int, input().split())\nprint(a + b)\n"
GUARDED_SOLUTION = (
    "def main():\n"
    "    a, b = map(int, input().split())\n"
    "    print(a * b)\n"
    "if __name__ == '__main__':\n"
    "    main()\n"
)
STATEFUL_SOLUTION = (
    "seen = globals().setdefault('_seen', [])\n"
    "seen.append(1)\n"
    "a, b = map(int, input().split())\n"
    "print(a + b + len(seen) - 1)\n"
)


def build(code: str, rule: str = "a(k=2)", fn: str = "f"):
    ns: dict = {}
    exec(compile(pool.callable_source(code, rule, fn), "<test>", "exec"), ns)
    return ns[fn]


class TestTheCallable(unittest.TestCase):
    """A stdin script, wrapped so `spec_check.reference()` can call it."""

    def test_it_computes_the_answer(self):
        self.assertEqual(build(SUM_SOLUTION)(2, 3), 5)

    def test_a_main_guarded_script_still_runs(self):
        """The wrapper execs with __name__ == '__main__' precisely so the most
        common competitive-programming shape is not a silent no-output."""
        self.assertEqual(build(GUARDED_SOLUTION)(4, 5), 20)

    def test_no_state_leaks_between_calls(self):
        """A fresh namespace per call, or the second draw answers with the
        first draw's leftovers and the disagreement is charged to the model."""
        f = build(STATEFUL_SOLUTION)
        self.assertEqual(f(1, 1), 2)
        self.assertEqual(f(1, 1), 2)

    def test_a_sequence_argument_is_rendered_as_its_rule_says(self):
        code = "n = int(input())\nxs = list(map(int, input().split()))\nprint(sum(xs) + n)\n"
        self.assertEqual(build(code, rule="b")(3, [1, 2, 3]), 9)

    def test_more_than_one_output_token_raises(self):
        """The extractor accepted the problem because every sample output is a
        single integer. A solution printing two is not that problem, and an int
        silently taken from the first token would be a wrong verdict."""
        with self.assertRaises(ValueError):
            build("print(1, 2)\n")(0, 0)

    def test_a_solution_that_prints_nothing_raises(self):
        with self.assertRaises(ValueError):
            build("pass\n")(0, 0)


class TestIdsAreDerivedFromTheProblem(unittest.TestCase):
    """The property that lets the pool gate stay strict."""

    EX = {"id": "apps_raw_train:1234", "grammar_rule": "a(k=2)",
          "points": [{"args": [["int", 2], ["int", 3]], "expected": ["int", 5]}],
          "solution": SUM_SOLUTION, "text": "add two numbers"}

    def entry(self):
        return pool._entry("APPS", self.EX["id"], pool.STDIN_APPS_BASE, "1234",
                           self.EX, self.EX["solution"], self.EX["text"])

    def test_the_same_problem_gets_the_same_id_every_time(self):
        first, second = self.entry(), self.entry()
        self.assertIsNotNone(first)
        self.assertEqual(first[0], second[0])

    def test_the_id_is_the_problems_own_id_over_the_base(self):
        tid, _entry = self.entry()
        self.assertEqual(tid, pool.STDIN_APPS_BASE + 1234)

    def test_the_entry_carries_that_id_into_the_record(self):
        tid, entry = self.entry()
        self.assertEqual(entry["rec"]["task_id"], tid)

    def test_an_unrenderable_rule_is_refused_before_grading(self):
        ex = dict(self.EX, grammar_rule="z")
        self.assertIsNone(pool._entry("APPS", ex["id"], pool.STDIN_APPS_BASE,
                                      "1234", ex, ex["solution"], ex["text"]))

    def test_a_codecontests_name_gets_a_stable_hashed_id(self):
        """CodeContests has no own-id integer. The id must still be a function
        of the problem alone -- same name, same id, forever, whatever else was
        walked first."""
        name = "1575_A. Another Sorting Problem"
        first = pool.stable_id("CC", pool.STDIN_CC_BASE, name)
        self.assertIsNotNone(first)
        self.assertEqual(first, pool.stable_id("CC", pool.STDIN_CC_BASE, name))
        self.assertNotEqual(first, pool.stable_id("CC", pool.STDIN_CC_BASE, name + "x"))
        self.assertGreaterEqual(first, pool.STDIN_CC_BASE)
        self.assertLess(first, pool.STDIN_CC_BASE + pool.STDIN_CC_SPAN)

    def test_an_apps_record_without_a_numeric_id_is_refused(self):
        """Fail closed: APPS ids are integers, so a non-integer one means the
        record is not what this code thinks it is."""
        self.assertIsNone(pool.stable_id("APPS", pool.STDIN_APPS_BASE, "not-a-number"))

    def test_the_hashed_space_cannot_reach_the_apps_space(self):
        self.assertGreater(pool.STDIN_CC_BASE, pool.STDIN_APPS_BASE + 100000)

    def test_the_two_sources_cannot_collide(self):
        self.assertGreaterEqual(abs(pool.STDIN_CC_BASE - pool.STDIN_APPS_BASE), 100000)


if __name__ == "__main__":
    unittest.main()
