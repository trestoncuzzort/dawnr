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


def _rotate_task():
    """dafny_synthesis_task_id_586 splitAndAppend's own shape: a rotate
    by n, secondPart (slice(l,n,len(l))) then firstPart (slice(l,0,n))
    concatenated, the ensures a forall comparing r[i] against
    l[(i+n) mod len(l)]."""
    return {
        "params": [{"name": "l", "type": "seq"}, {"name": "n", "type": "int"}],
        "returns": [{"name": "r", "type": "seq"}],
        "requires": [
            {"op": ">=", "args": [{"var": "n"}, {"int": 0}]},
            {"op": "<", "args": [{"var": "n"}, _len("l")]},
        ],
        "ensures": [
            {"op": "==", "args": [_len("r"), _len("l")]},
            {"forall": {
                "lo": {"int": 0}, "hi": _len("l"), "var": "i",
                "body": {"op": "==", "args": [
                    {"op": "at", "args": [{"var": "r"}, {"var": "i"}]},
                    {"op": "at", "args": [{"var": "l"}, {
                        "op": "mod", "args": [
                            {"op": "+", "args": [{"var": "i"}, {"var": "n"}]},
                            _len("l")]}]},
                ]},
            }},
        ],
    }, [
        {"var": {"name": "firstPart", "type": "seq",
                 "init": _slice("l", {"int": 0}, {"var": "n"})}},
        {"var": {"name": "secondPart", "type": "seq",
                 "init": _slice("l", {"var": "n"}, _len("l"))}},
        {"assign": ["r", {"op": "+", "args": [
            {"var": "secondPart"}, {"var": "firstPart"}]}]},
    ]


class RotateLemmaTargetTest(unittest.TestCase):
    def test_matches_the_splitAndAppend_shape(self):
        task, body = _rotate_task()
        target = ls._rotate_lemma_target(task, body)
        self.assertIsNotNone(target)
        l_ast, n_ast = target
        self.assertEqual(l_ast, {"var": "l"})
        self.assertEqual(n_ast, {"var": "n"})

    def test_no_match_when_the_operand_order_is_reversed(self):
        # firstPart then secondPart (the OTHER order): Rotate_Lemma's own
        # proof is for THIS one operand order only (its docstring), so a
        # task built the other way must not match.
        task, body = _rotate_task()
        body[2] = {"assign": ["r", {"op": "+", "args": [
            {"var": "firstPart"}, {"var": "secondPart"}]}]}
        self.assertIsNone(ls._rotate_lemma_target(task, body))

    def test_no_match_when_the_ensures_is_unrelated(self):
        task, body = _rotate_task()
        task["ensures"] = [{"op": "==", "args": [_len("r"), _len("l")]}]
        self.assertIsNone(ls._rotate_lemma_target(task, body))

    def test_no_match_when_the_modulus_is_a_different_seq(self):
        task, body = _rotate_task()
        task["ensures"][1]["forall"]["body"]["args"][1]["args"][1]["args"][1] = \
            {"op": "len", "args": [{"var": "n"}]}
        self.assertIsNone(ls._rotate_lemma_target(task, body))

    def test_wires_through_lower_and_emits_the_preamble(self):
        task, body = _rotate_task()
        task = {**task, "t": 0, "name": "fz_rotate_probe"}
        out = ls.lower(task, body)
        self.assertIn("Rotate_Lemma", out)
        self.assertIn("Rotate_Full_Count_Lemma", out)
        self.assertIn("if Rotate_Lemma (L, N)", out)


class UndefObligationWhileDescentTest(unittest.TestCase):
    """ROADMAP 16.2, 2026-09-12 (dafny_synthesis_task_id_610
    removeElement, "the while certificate" item): `_undef_obligation`'s
    own `_walk` used to `return None` (an honest "not modeled here", the
    file's own pre-existing docstring) the instant it reached a `while`
    statement, so an undefined access sitting INSIDE a loop body -- 610's
    own twin, per the module docstring above `_walk` -- read UNPROVED
    rather than REFUTED. This test is a synthetic, minimal instance of
    the same shape (an `update` whose index runs past the seq's own
    length on the loop's SECOND iteration, not reachable from the
    outside): before the while-descent branch, `_undef_obligation`
    returned None here too; after it, the obligation is found."""

    def test_finds_the_obligation_on_the_loops_second_iteration(self):
        task = {
            "name": "fz_while_undef_probe",
            "params": [{"name": "s", "type": "seq"}, {"name": "k", "type": "int"}],
            "returns": [{"name": "v", "type": "seq"}],
            "requires": [],
            "ensures": [],
        }
        twin_body = [
            {"var": {"name": "v", "type": "seq",
                     "init": {"op": "fill", "args": [_len("s"), {"int": 0}]}}},
            {"var": {"name": "i", "type": "int", "init": {"int": 0}}},
            {"while": {
                "cond": {"op": "<", "args": [{"var": "i"}, {"var": "k"}]},
                "body": [
                    {"assign": ["v", {"op": "update", "args": [
                        {"var": "v"}, {"var": "i"}, {"int": 0}]}]},
                    {"assign": ["i", {"op": "+", "args": [
                        {"var": "i"}, {"int": 1}]}]},
                ],
            }},
        ]
        vals = {"s": [0], "k": 5}
        L = ls.Lower(task)
        sub = {"s": "S", "k": "K"}
        obligation = ls._undef_obligation(task, twin_body, sub, vals, L)
        self.assertIsNotNone(
            obligation,
            "the loop's second iteration updates v at index 1 with "
            "Len(v) = 1 -- an obligation the walk must find now that it "
            "descends into `while` bodies")

    def test_still_none_when_no_obligation_is_undefined(self):
        # The SAME loop, but k=1 (one iteration, never out of bounds):
        # the walk must replay it to the end and find nothing, an honest
        # None -- the while-descent must not manufacture a false
        # obligation on a loop that never goes wrong.
        task = {
            "name": "fz_while_undef_probe2",
            "params": [{"name": "s", "type": "seq"}, {"name": "k", "type": "int"}],
            "returns": [{"name": "v", "type": "seq"}],
            "requires": [],
            "ensures": [],
        }
        twin_body = [
            {"var": {"name": "v", "type": "seq",
                     "init": {"op": "fill", "args": [_len("s"), {"int": 0}]}}},
            {"var": {"name": "i", "type": "int", "init": {"int": 0}}},
            {"while": {
                "cond": {"op": "<", "args": [{"var": "i"}, {"var": "k"}]},
                "body": [
                    {"assign": ["v", {"op": "update", "args": [
                        {"var": "v"}, {"var": "i"}, {"int": 0}]}]},
                    {"assign": ["i", {"op": "+", "args": [
                        {"var": "i"}, {"int": 1}]}]},
                ],
            }},
        ]
        vals = {"s": [0], "k": 1}
        L = ls.Lower(task)
        sub = {"s": "S", "k": "K"}
        obligation = ls._undef_obligation(task, twin_body, sub, vals, L)
        self.assertIsNone(obligation)


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
            self.assertIsNone(
                ls._rotate_lemma_target(task, body),
                f"{path} unexpectedly matches the rotate-lemma pattern; "
                f"ROTATE_LEMMA_PREAMBLE's own note assumed no committed "
                f"task does")


if __name__ == "__main__":
    unittest.main()
