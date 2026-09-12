"""t/test_lower_spark.py: unit tests for the split-concat lemma detector
added to lower_spark.py (ROADMAP 16.2, 2026-09-11, dafny_synthesis_task_id_262
splitArray). See lower_spark.py's own SPLIT_CONCAT_LEMMA_PREAMBLE docstring
for the gnatprove-side measurement history (why the naive `for all` goal
times out and why this shape verifies); this file only tests the detector
that decides WHEN to route a task through the lemma, and that every
previously-committed task's own lowering is unaffected by its addition.

Measured by `python3 test_lower_spark.py` from t/.
"""
import glob
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lower_spark as ls
import tasks_io


def _slice(s, a, b):
    return {"op": "slice", "args": [{"var": s}, a, b]}


def _len(s):
    return {"op": "len", "args": [{"var": s}]}


def _split_task():
    """dafny_synthesis_task_id_262 splitArray's own shape: a pair of two
    contiguous slices whose concat the ensures compares against the whole
    array, reached through a pair() body and fst/snd in the ensures."""
    return {
        "params": [{"name": "arr", "type": "seq"}, {"name": "l", "type": "int"}],
        "returns": [{"name": "r", "type": {"pair": ["seq", "seq"]}}],
        "requires": [],
        "ensures": [
            {"op": "==", "args": [
                {"op": "+", "args": [
                    {"op": "fst", "args": [{"var": "r"}]},
                    {"op": "snd", "args": [{"var": "r"}]},
                ]},
                {"var": "arr"},
            ]},
        ],
    }, [
        {"var": {"name": "firstPart", "type": "seq",
                 "init": {"op": "seq", "args": []}}},
        {"var": {"name": "secondPart", "type": "seq",
                 "init": {"op": "seq", "args": []}}},
        {"assign": ["firstPart", _slice("arr", {"int": 0}, {"var": "l"})]},
        {"assign": ["secondPart", _slice("arr", {"var": "l"}, _len("arr"))]},
        {"assign": ["r", {"op": "pair", "args": [
            {"var": "firstPart"}, {"var": "secondPart"}]}]},
    ]


class SplitConcatLemmaTargetTest(unittest.TestCase):
    def test_matches_the_splitArray_shape(self):
        task, body = _split_task()
        target = ls._split_concat_lemma_target(task, body)
        self.assertIsNotNone(target)
        s_ast, l_ast = target
        self.assertEqual(s_ast, {"var": "arr"})
        self.assertEqual(l_ast, {"var": "l"})

    def test_no_match_when_the_slice_is_not_contiguous(self):
        # A gap between the two slices (l+1, not l): the concatenation is
        # not the source array at all, so the lemma this file emits would
        # state a FALSE fact -- must not fire.
        task, body = _split_task()
        body[3] = {"assign": ["secondPart",
                              _slice("arr", {"op": "+", "args": [
                                  {"var": "l"}, {"int": 1}]}, _len("arr"))]}
        self.assertIsNone(ls._split_concat_lemma_target(task, body))

    def test_no_match_when_the_ensures_is_unrelated(self):
        task, body = _split_task()
        task["ensures"] = [{"op": "==", "args": [
            {"op": "fst", "args": [{"var": "r"}]}, {"var": "arr"}]}]
        self.assertIsNone(ls._split_concat_lemma_target(task, body))

    def test_no_match_when_the_first_slice_does_not_start_at_zero(self):
        task, body = _split_task()
        body[2] = {"assign": ["firstPart",
                              _slice("arr", {"int": 1}, {"var": "l"})]}
        self.assertIsNone(ls._split_concat_lemma_target(task, body))

    def test_wires_through_lower_and_emits_the_preamble(self):
        task, body = _split_task()
        task = {**task, "t": 0, "name": "fz_split_concat_probe"}
        out = ls.lower(task, body)
        self.assertIn("Split_Concat_Lemma", out)
        self.assertIn("T_Concat_Slice_Lemma", out)
        self.assertIn("if Split_Concat_Lemma (Arr, L)", out)


class AstEqTest(unittest.TestCase):
    def test_equal_dicts_and_lists(self):
        a = {"op": "len", "args": [{"var": "arr"}]}
        b = {"op": "len", "args": [{"var": "arr"}]}
        self.assertTrue(ls._ast_eq(a, b))

    def test_unequal_dicts(self):
        a = {"op": "len", "args": [{"var": "arr"}]}
        b = {"op": "len", "args": [{"var": "other"}]}
        self.assertFalse(ls._ast_eq(a, b))


class CommittedTasksUnaffectedTest(unittest.TestCase):
    """The split-concat detector is narrow on purpose (its own docstring):
    every task committed before this change must relower BYTE-IDENTICAL,
    the same regression discipline test_names.py already applies to the
    rename pass."""

    def test_no_committed_task_triggers_the_new_pattern(self):
        here = os.path.dirname(os.path.abspath(__file__))
        for path in sorted(glob.glob(os.path.join(here, "tasks", "*.t"))):
            task = tasks_io.load_task(path)
            body = task["body"]
            self.assertIsNone(
                ls._split_concat_lemma_target(task, body),
                f"{path} unexpectedly matches the split-concat pattern; "
                f"lower_spark.py's own note assumed no committed task does")


if __name__ == "__main__":
    unittest.main()
