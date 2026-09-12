"""t/test_lower_lean_divisorbound.py: unit tests for lower_lean.py's
2026-09-12 ROADMAP 16.2 additions (key lean-2): the divisor-bound
detector (`_divisor_bound_target`, ported from lower_fstar.py) and the
declare-then-reassign fix to `_has_seq_append_of_slice`.

Pure-Python unit tests over `Lower.__init__`/module-level detectors -- no
lean binary invoked here (t/grade.py's kernel calls are for that); these
catch a regression in the DETECTION/GUARD logic itself, the same
discipline test_lower_lean_seqcomp.py already uses.

Run: python3 t/test_lower_lean_divisorbound.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lower_lean


def _task(name, params, ensures, body, requires=None, ret_type="int"):
    return {
        "t": 1,
        "name": name,
        "params": params,
        "returns": [{"name": "result", "type": ret_type}],
        "requires": requires or [],
        "ensures": ensures,
        "body": body,
    }


def _mod_ne(dividend, k_name):
    return {"op": "!=", "args": [
        {"op": "mod", "args": [dividend, {"var": k_name}]}, {"int": 0}]}


def _mod_eq(dividend, k_name):
    return {"op": "==", "args": [
        {"op": "mod", "args": [dividend, {"var": k_name}]}, {"int": 0}]}


def _isprime_like(relop):
    """dafny_synthesis isPrime's own shape (relop='!=') or isNonPrime's
    (relop='==', "exists" instead of "forall")."""
    n = {"var": "n"}
    mod_body = (_mod_ne(n, "k") if relop == "!=" else _mod_eq(n, "k"))
    mod_body_inv = (_mod_ne(n, "k_v") if relop == "!="
                    else _mod_eq(n, "k_v"))
    kind = "forall" if relop == "!=" else "exists"
    ensures = [{"op": "==", "args": [{"var": "result"}, {
        kind: {"var": "k", "lo": {"int": 2}, "hi": n, "body": mod_body}}]}]
    invariants = [
        {"op": "<=", "args": [{"int": 2}, {"var": "i"}]},
        {"op": "==", "args": [{"var": "result"}, {
            kind: {"var": "k_v", "lo": {"int": 2}, "hi": {"var": "i"},
                  "body": mod_body_inv}}]},
    ]
    w = {
        "cond": {"op": "<=", "args": [
            {"var": "i"}, {"op": "div", "args": [n, {"int": 2}]}]},
        "invariants": invariants,
        "body": [
            {"if": {"cond": mod_body_inv, "then": [], "else": [
                {"assign": ["i", {"op": "+", "args": [
                    {"var": "i"}, {"int": 1}]}]}]}}],
    }
    body = [
        {"assign": ["result", {"bool": True}]},
        {"var": {"name": "i", "type": "int", "init": {"int": 2}}},
        {"while": w},
    ]
    task = _task("primelike", [{"name": "n", "type": "int"}], ensures,
                body, requires=[{"op": ">=", "args": [{"var": "n"},
                                                       {"int": 2}]}],
                ret_type="bool")
    return task, w


class DivisorBoundTargetTest(unittest.TestCase):
    def test_forall_family_matches_isprime_shape(self):
        task, w = _isprime_like("!=")
        plan = lower_lean._divisor_bound_target(task, w)
        self.assertIsNotNone(plan)
        self.assertEqual(plan["kind"], "forall")
        self.assertEqual(plan["relop"], "!=")
        self.assertEqual(plan["i_name"], "i")
        self.assertEqual(plan["lo"], {"int": 2})
        self.assertEqual(plan["dividend"], {"var": "n"})
        # the matched invariant is invariants[1] (0-based), so inv_index=1
        self.assertEqual(plan["inv_index"], 1)

    def test_exists_family_matches_isnonprime_shape(self):
        task, w = _isprime_like("==")
        plan = lower_lean._divisor_bound_target(task, w)
        self.assertIsNotNone(plan)
        self.assertEqual(plan["kind"], "exists")
        self.assertEqual(plan["relop"], "==")

    def test_no_match_when_cond_is_not_half_bound(self):
        task, w = _isprime_like("!=")
        # a trial-divide-to-N loop (cond: i <= n, not i <= n/2) must not
        # match: the lemma this family needs is specific to the
        # half-bound shape.
        w = dict(w)
        w["cond"] = {"op": "<=", "args": [{"var": "i"}, {"var": "n"}]}
        plan = lower_lean._divisor_bound_target(task, w)
        self.assertIsNone(plan)

    def test_no_match_when_ensures_has_no_matching_quantifier(self):
        task, w = _isprime_like("!=")
        task = dict(task)
        task["ensures"] = [{"op": ">=", "args": [{"var": "result"},
                                                  {"int": 0}]}]
        plan = lower_lean._divisor_bound_target(task, w)
        self.assertIsNone(plan)

    def test_lower_init_sets_plan_and_indices(self):
        task, w = _isprime_like("!=")
        lw = lower_lean.Lower(task, task["body"])
        self.assertIsNotNone(lw._divisor_bound_plan)
        self.assertEqual(lw._divisor_bound_inv_idx, 2)   # 1-based
        self.assertEqual(lw._divisor_bound_bound_idx, 3)  # 2 invariants + 1

    def test_lower_init_none_for_ordinary_loop_task(self):
        # sum_upto-like: no quantified ensures at all, no divisor-bound
        # shape anywhere -- plan must stay None.
        w = {
            "cond": {"op": "<", "args": [{"var": "i"}, {"var": "n"}]},
            "invariants": [
                {"op": "<=", "args": [{"int": 0}, {"var": "i"}]}],
            "body": [{"assign": ["i", {"op": "+", "args": [
                {"var": "i"}, {"int": 1}]}]}],
        }
        body = [
            {"assign": ["result", {"int": 0}]},
            {"var": {"name": "i", "type": "int", "init": {"int": 0}}},
            {"while": w},
        ]
        task = _task("sumlike", [{"name": "n", "type": "int"}],
                    [{"op": ">=", "args": [{"var": "result"}, {"int": 0}]}],
                    body)
        lw = lower_lean.Lower(task, body)
        self.assertIsNone(lw._divisor_bound_plan)


class SeqAppendOfSliceReassignTest(unittest.TestCase):
    def _seq_task(self, name, params, ensures, body):
        return {
            "t": 1,
            "name": name,
            "params": params,
            "returns": [{"name": "result", "type": {
                "pair": ["seq", "seq"]}}],
            "requires": [],
            "ensures": ensures,
            "body": body,
        }

    def test_declare_then_reassign_slice_is_detected(self):
        # splitArray's own shape (2026-09-12 fix): firstPart/secondPart
        # are DECLARED with an empty-seq init, then REASSIGNED to a
        # slice by a later `assign` -- the pre-fix detector only ever
        # read the `var` node's own `init`, missing the reassignment
        # entirely.
        body = [
            {"var": {"name": "firstPart", "type": "seq",
                    "init": {"op": "seq", "args": []}}},
            {"var": {"name": "secondPart", "type": "seq",
                    "init": {"op": "seq", "args": []}}},
            {"assign": ["firstPart", {"op": "slice", "args": [
                {"var": "arr"}, {"int": 0}, {"var": "l"}]}]},
            {"assign": ["secondPart", {"op": "slice", "args": [
                {"var": "arr"}, {"var": "l"},
                {"op": "len", "args": [{"var": "arr"}]}]}]},
            {"assign": ["result", {"op": "pair", "args": [
                {"var": "firstPart"}, {"var": "secondPart"}]}]},
        ]
        ensures = [{"op": "==", "args": [
            {"op": "+", "args": [
                {"op": "fst", "args": [{"var": "result"}]},
                {"op": "snd", "args": [{"var": "result"}]}]},
            {"var": "arr"}]}]
        task = self._seq_task(
            "splitlike",
            [{"name": "arr", "type": "seq"}, {"name": "l", "type": "int"}],
            ensures, body)
        lw = lower_lean.Lower(task, body)
        self.assertTrue(lw.seq_composed_append_slice)

    def test_direct_init_slice_still_detected(self):
        # splitAndAppend's own shape (never regressed by the fix): `var`
        # initialized DIRECTLY to a slice, no reassignment.
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
            "splitlike2",
            [{"name": "arr", "type": "seq"}, {"name": "l", "type": "int"}],
            [{"op": "==", "args": [{"var": "result"}, {"var": "arr"}]}],
            body)
        lw = lower_lean.Lower(task, body)
        self.assertTrue(lw.seq_composed_append_slice)


if __name__ == "__main__":
    unittest.main()
