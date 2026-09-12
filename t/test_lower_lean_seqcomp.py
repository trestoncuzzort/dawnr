"""t/test_lower_lean_seqcomp.py: unit tests for lower_lean.py's 2026-09-11
ROADMAP 16.2 additions (key lean-seqcomp): the nonlinear sign bridge
(`_mul_sign_pairs`, `_is_affine`, `_sign_compare_operands`/
`_resolve_to_body_expr`) and the composed seq-bridge shape detectors
(`_has_seq_update_chain`, `_has_seq_append_of_slice`).

Pure-Python unit tests over `Lower.__init__`/`_mul_sign_pairs` -- no lean
binary invoked here (that is what t/grade.py's kernel calls are for);
these tests catch a regression in the DETECTION/GUARD logic itself, the
exact class of bug this wave's own two caught-and-fixed regressions
(remainder's `(x/y)*y`, cubeVolume's `(size*size)*size`) came from: an
over-eager detector emitting a lemma for a task that either did not need
one, or whose factors were not the affine shape the case-split's own
`exfalso; omega` leaves can actually decide.

Run: python3 t/test_lower_lean_seqcomp.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lower_lean


def _task(name, params, ensures, body, requires=None, ret_type="int"):
    return {
        "t": 0,
        "name": name,
        "params": params,
        "returns": [{"name": "result", "type": ret_type}],
        "requires": requires or [],
        "ensures": ensures,
        "body": body,
    }


class MulSignPairsTest(unittest.TestCase):
    def test_fires_on_sign_comparison_over_affine_product(self):
        # centeredHexagonalNumber's own shape: result := 3*n*(n-1)+1,
        # ensures result >= 0 (a real sign comparison against 0).
        task = _task(
            "hexnum",
            [{"name": "n", "type": "int"}],
            [{"op": ">=", "args": [{"var": "result"}, {"int": 0}]}],
            [{"assign": ["result", {
                "op": "+",
                "args": [
                    {"op": "*", "args": [
                        {"op": "*", "args": [{"int": 3}, {"var": "n"}]},
                        {"op": "-", "args": [{"var": "n"}, {"int": 1}]}]},
                    {"int": 1}]}]}],
            requires=[{"op": ">=", "args": [{"var": "n"}, {"int": 0}]}],
        )
        lw = lower_lean.Lower(task, task["body"])
        pairs = lw._mul_sign_pairs()
        self.assertEqual(len(pairs), 1)
        a, b = pairs[0]
        self.assertIn("n", a)
        self.assertIn("n", b)

    def test_silent_on_equality_only_ensures(self):
        # cubeVolume's own shape (REGRESSION #2, 2026-09-11): a product
        # appears in the body, but ensures is EQUALITY only -- no `>=`/
        # `<=`/`>`/`<` node anywhere, so there is no sign obligation to
        # bridge and no lemma should be emitted (the one that was, before
        # this guard, broke this exact task: `(size*size)*size`'s own
        # inner factor is not affine, and the emitted lemma's own
        # `exfalso; omega` leaf could not close, sorryAx-tainting the
        # whole file).
        task = _task(
            "cubevol",
            [{"name": "size", "type": "int"}],
            [{"op": "==", "args": [
                {"var": "result"},
                {"op": "*", "args": [
                    {"op": "*", "args": [{"var": "size"}, {"var": "size"}]},
                    {"var": "size"}]}]}],
            [{"assign": ["result", {
                "op": "*", "args": [
                    {"op": "*", "args": [{"var": "size"}, {"var": "size"}]},
                    {"var": "size"}]}]}],
            requires=[{"op": ">", "args": [{"var": "size"}, {"int": 0}]}],
        )
        lw = lower_lean.Lower(task, task["body"])
        self.assertEqual(lw._mul_sign_pairs(), [])

    def test_silent_on_nonaffine_outer_factor(self):
        # A synthetic sign-comparison over `(size * size) * size`
        # (cubeVolume's REGRESSION #2 shape): the OUTER pair, one factor
        # itself nonlinear (`size * size`), must never be collected --
        # omega cannot relate a squared atom's sign to its own base
        # variable, so a lemma for THAT pair would be the same shape of
        # failure cubeVolume's `mulsign_1` was. The INNER `size * size`
        # sub-pair (both factors bare, identical vars) may legitimately
        # still appear -- `0 <= size * size` is always true and the
        # case-split's own leaves close it trivially (`hAp`/`hBp` on the
        # SAME variable can never actually disagree, so the "opposite
        # sign" branches are immediate `omega` contradictions) -- this
        # test only asserts the unprovable OUTER pair is absent.
        task = _task(
            "sq",
            [{"name": "size", "type": "int"}],
            [{"op": ">=", "args": [{"var": "result"}, {"int": 0}]}],
            [{"assign": ["result", {
                "op": "*", "args": [
                    {"op": "*", "args": [{"var": "size"}, {"var": "size"}]},
                    {"var": "size"}]}]}],
        )
        lw = lower_lean.Lower(task, task["body"])
        for a, b in lw._mul_sign_pairs():
            self.assertNotIn("*", a)
            self.assertNotIn("*", b)

    def test_silent_on_division(self):
        # remainder's own shape (REGRESSION #1, 2026-09-11): `r >= 0`
        # resolves to body's `r := x % y`, no `*` node in sight at all,
        # so no pair -- and even if a `*` involving a `/`-built operand
        # appeared, `_is_affine` (no `/`/`%` in its allowed op set)
        # would refuse it independently.
        task = _task(
            "remainder_like",
            [{"name": "x", "type": "int"}, {"name": "y", "type": "int"}],
            [{"op": ">=", "args": [{"var": "result"}, {"int": 0}]}],
            [{"assign": ["result", {"op": "mod",
                                    "args": [{"var": "x"}, {"var": "y"}]}]}],
            requires=[{"op": "!=", "args": [{"var": "y"}, {"int": 0}]}],
        )
        lw = lower_lean.Lower(task, task["body"])
        self.assertEqual(lw._mul_sign_pairs(), [])


class SeqComposedDetectionTest(unittest.TestCase):
    def _seq_task(self, name, params, ensures, body):
        t = _task(name, params, ensures, body, ret_type="seq")
        t["returns"] = [{"name": "result", "type": "seq"}]
        return t

    def test_update_chain_detected(self):
        # swapFirstAndLast's own shape: a_out reassigned via `update`
        # twice in sequence, each self-referencing.
        body = [
            {"assign": ["a_out", {"var": "a"}]},
            {"assign": ["a_out", {"op": "update", "args": [
                {"var": "a_out"}, {"int": 0}, {"int": 1}]}]},
            {"assign": ["a_out", {"op": "update", "args": [
                {"var": "a_out"}, {"int": 1}, {"int": 2}]}]},
        ]
        task = self._seq_task(
            "swaplike",
            [{"name": "a", "type": "seq"}],
            [{"op": "==", "args": [{"var": "result"}, {"var": "a_out"}]}],
            body)
        lw = lower_lean.Lower(task, body)
        self.assertTrue(lw.seq_composed_update2)

    def test_single_update_not_flagged(self):
        body = [
            {"assign": ["a_out", {"op": "update", "args": [
                {"var": "a"}, {"int": 0}, {"int": 1}]}]},
        ]
        task = self._seq_task(
            "singleupdate",
            [{"name": "a", "type": "seq"}],
            [{"op": "==", "args": [{"var": "result"}, {"var": "a_out"}]}],
            body)
        lw = lower_lean.Lower(task, body)
        self.assertFalse(lw.seq_composed_update2)

    def test_append_of_slices_detected(self):
        # splitArray's own shape: two locals each initialized to a
        # slice, then concatenated.
        body = [
            {"var": {"name": "firstPart", "type": "seq", "init": {
                "op": "slice", "args": [
                    {"var": "arr"}, {"int": 0}, {"var": "l"}]}}},
            {"var": {"name": "secondPart", "type": "seq", "init": {
                "op": "slice", "args": [
                    {"var": "arr"}, {"var": "l"},
                    {"op": "len", "args": [{"var": "arr"}]}]}}},
            {"assign": ["result", {"op": "+", "args": [
                {"var": "firstPart"}, {"var": "secondPart"}]}]},
        ]
        task = self._seq_task(
            "splitlike",
            [{"name": "arr", "type": "seq"}, {"name": "l", "type": "int"}],
            [{"op": "==", "args": [{"var": "result"}, {"var": "arr"}]}],
            body)
        lw = lower_lean.Lower(task, body)
        self.assertTrue(lw.seq_composed_append_slice)

    def test_append_of_bare_seqs_not_flagged(self):
        body = [
            {"assign": ["result", {"op": "+", "args": [
                {"var": "a"}, {"var": "b"}]}]},
        ]
        task = self._seq_task(
            "appendlike",
            [{"name": "a", "type": "seq"}, {"name": "b", "type": "seq"}],
            [{"op": "==", "args": [{"var": "result"}, {"var": "a"}]}],
            body)
        lw = lower_lean.Lower(task, body)
        self.assertFalse(lw.seq_composed_append_slice)


if __name__ == "__main__":
    unittest.main()
