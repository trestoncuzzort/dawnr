"""t/spec_given.py (2026-10-01): in the specification-given setting the given contract is the
ground truth, so an answer must carry it unchanged before the provers see it (AlphaVerus's
misaligned-specification filter, arXiv:2412.06176). The body, invariants, lemmas and the format
line are the answer's to write. No kernel."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_given  # noqa: E402
import surface  # noqa: E402

GIVEN = surface.parse(
    "t 1\ngate recursion\ntask abs(x: int) returns (y: int)\n  ensures y >= 0\n  ensures y == abs_v(x)\n"
    "spec fun abs_v(x_v: int): int\n  decreases x_v\n= if x_v > 0 then x_v else -x_v\n"
    "{\n  if x < 0 {\n    y := -x;\n  } else {\n    y := x;\n  }\n}\n")
QUESTION = dict(GIVEN, body=[])


def answer(**changes) -> dict:
    a = copy.deepcopy(GIVEN)
    a.update(changes)
    return a


class Kept(unittest.TestCase):
    def test_the_given_contract_with_a_body_is_kept(self):
        self.assertIsNone(spec_given.kept(QUESTION, GIVEN))

    def test_another_body_another_gate_and_a_promoted_format_line_are_the_answers_to_choose(self):
        other_body = surface.parse(
            "t 1\ntask abs(x: int) returns (y: int)\n  ensures y >= 0\n  ensures y == abs_v(x)\n"
            "spec fun abs_v(x_v: int): int\n  decreases x_v\n= if x_v > 0 then x_v else -x_v\n"
            "{\n  y := x;\n  if x < 0 {\n    y := -x;\n  } else {\n    y := x;\n  }\n}\n")   # an if needs its else in t
        self.assertIsNone(spec_given.kept(QUESTION, other_body))

    def test_an_added_ensures_only_strengthens_it(self):
        more = answer(ensures=GIVEN["ensures"] + [GIVEN["ensures"][0]])
        self.assertIsNone(spec_given.kept(QUESTION, more))

    def test_a_given_ensures_removed_is_refused(self):
        self.assertEqual(spec_given.kept(QUESTION, answer(ensures=GIVEN["ensures"][:1])),
                         "a given ensures is missing or altered")

    def test_a_requires_added_is_refused(self):
        narrowed = answer(requires=[GIVEN["ensures"][0]])
        self.assertEqual(spec_given.kept(QUESTION, narrowed), "a requires was changed, added or removed")

    def test_the_ensures_kept_word_for_word_over_a_redefined_spec_fun_is_refused(self):
        # the hole repair.spec_kept leaves open: same ensures text, another meaning
        trivial = copy.deepcopy(GIVEN["spec_funs"])
        trivial[0]["body"] = {"int": 0}
        self.assertEqual(spec_given.kept(QUESTION, answer(spec_funs=trivial)), "given spec fun abs_v was redefined")

    def test_a_given_spec_fun_left_out_is_refused(self):
        self.assertEqual(spec_given.kept(QUESTION, answer(spec_funs=[])), "given spec fun abs_v is missing")

    def test_a_helper_spec_fun_under_a_new_name_is_allowed(self):
        helper = dict(copy.deepcopy(GIVEN["spec_funs"][0]), name="helper")
        self.assertIsNone(spec_given.kept(QUESTION, answer(spec_funs=GIVEN["spec_funs"] + [helper])))

    def test_a_renamed_task_or_changed_parameters_are_refused(self):
        self.assertEqual(spec_given.kept(QUESTION, answer(name="other")), "the task was renamed")
        wider = answer(params=GIVEN["params"] + [{"name": "z", "type": "int"}])
        self.assertEqual(spec_given.kept(QUESTION, wider), "the params differ")

    def test_a_lemma_may_be_added_but_not_under_a_given_spec_funs_name(self):
        lemma = {"name": "pos", "params": [], "requires": [], "ensures": [], "body": []}
        self.assertIsNone(spec_given.kept(QUESTION, answer(lemmas=[lemma])))
        self.assertEqual(spec_given.kept(QUESTION, answer(lemmas=[dict(lemma, name="abs_v")])),
                         "a lemma takes the name of given spec fun abs_v")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
