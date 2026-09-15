"""t/test_lower_verus_closure.py: unit tests for the 2026-09-15 verus-
closure item (ROADMAP 16.2).

Two independent fixes to `lower_verus.py`, both measured directly against
Verus (`verus <file>.rs`) this session (2026-09-15) and both covered here
at the unit level so a later change to the shared matcher/unroll code
cannot silently regress them without a red test:

1. `_verus_closure_carry_target`/`_verus_closure_carry_assert`: the
   filter-append/witness-membership loop shape (412 removeOddNumbers, 426
   filterOddNumbers, 436 findNegativeNumbers, 554 findOddNumbers, 629
   findEvenNumbers) needs an explicit existential-carry proof spliced into
   the recursive loop helper before Verus will re-derive the invariant
   `forall k in [0, ctr): pred(src[k]) ==> exists w in [0, dst.len()):
   dst[w] == src[k]` across one iteration. `_verus_closure_carry_target`
   must match this exact structural shape and reject near-misses (a
   different predicate on the guard vs. the invariant, an `else` branch,
   a two-statement state, a `ctr` that isn't the invariant's own `hi`)
   rather than firing on a shape it was not measured against.

2. `_unroll`'s new `spec_funs` parameter: a call to a spec_fun whose body
   is DIRECTLY a bounded quantifier (`inArray`, dafny_synthesis rows 2/
   161/249) is inlined and unrolled so `compute_only` can decide it in a
   twin's certificate; a call to a RECURSIVE, `ite`-bodied spec_fun
   (`factorial`, row 577 -- the regression this session measured and
   fixed before landing) must NOT be inlined, since nothing here folds
   constants along an `ite`'s condition and inlining it recurses forever
   (measured: RecursionError). `spec_funs=None` (every OTHER existing
   caller) must render a plain call exactly as before this date.

Measured by `python3 test_lower_verus_closure.py` from t/, 2026-09-15.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lower_verus as lv


def _at(seqname, idxname):
    return {"op": "at", "args": [{"var": seqname}, {"var": idxname}]}


def _findeven_shape():
    """The exact shape of the 629 findEvenNumbers / 412 removeOddNumbers
    /426/436/554 loop: state = ["evenList", "i_v2"], ro = ["arr"]."""
    invs = [
        {"forall": {
            "var": "k_v2", "lo": {"int": 0},
            "hi": {"op": "len", "args": [{"var": "evenList"}]},
            "body": {"op": "and", "args": [
                {"call": {"fun": "isEven", "args": [_at("evenList", "k_v2")]}},
                {"exists": {
                    "var": "k_v3", "lo": {"int": 0},
                    "hi": {"op": "len", "args": [{"var": "arr"}]},
                    "body": {"op": "==",
                            "args": [_at("arr", "k_v3"), _at("evenList", "k_v2")]},
                }},
            ]},
        }},
        {"forall": {
            "var": "k_v4", "lo": {"int": 0}, "hi": {"var": "i_v2"},
            "body": {"op": "implies", "args": [
                {"call": {"fun": "isEven", "args": [_at("arr", "k_v4")]}},
                {"exists": {
                    "var": "k_v5", "lo": {"int": 0},
                    "hi": {"op": "len", "args": [{"var": "evenList"}]},
                    "body": {"op": "==",
                            "args": [_at("evenList", "k_v5"), _at("arr", "k_v4")]},
                }},
            ]},
        }},
    ]
    body = [
        {"if": {
            "cond": {"call": {"fun": "isEven", "args": [_at("arr", "i_v2")]}},
            "then": [{"assign": ["evenList", {
                "op": "+", "args": [
                    {"var": "evenList"},
                    {"op": "seq", "args": [_at("arr", "i_v2")]},
                ],
            }]}],
            "else": [],
        }},
        {"assign": ["i_v2", {"op": "+",
                             "args": [{"var": "i_v2"}, {"int": 1}]}]},
    ]
    w = {"body": body, "invariants": invs}
    return w, invs, ["arr"], ["evenList", "i_v2"]


class CarryTargetMatchTest(unittest.TestCase):
    def test_matches_the_measured_shape(self):
        w, invs, ro, state = _findeven_shape()
        c = lv._verus_closure_carry_target(w, invs, ro, state)
        self.assertIsNotNone(c)
        self.assertEqual(c["ctr"], "i_v2")
        self.assertEqual(c["dst"], "evenList")
        self.assertEqual(c["src"], "arr")
        self.assertEqual(c["fname"], "isEven")
        self.assertEqual(c["kvar"], "k_v4")
        self.assertEqual(c["wvar"], "k_v5")

    def test_no_match_when_else_branch_present(self):
        w, invs, ro, state = _findeven_shape()
        w["body"][0]["if"]["else"] = [
            {"assign": ["evenList", {"var": "evenList"}]}]
        self.assertIsNone(
            lv._verus_closure_carry_target(w, invs, ro, state))

    def test_no_match_when_guard_predicate_differs_from_invariant(self):
        w, invs, ro, state = _findeven_shape()
        w["body"][0]["if"]["cond"] = {
            "call": {"fun": "isOdd", "args": [_at("arr", "i_v2")]}}
        self.assertIsNone(
            lv._verus_closure_carry_target(w, invs, ro, state))

    def test_no_match_when_src_is_loop_state_not_read_only(self):
        w, invs, ro, state = _findeven_shape()
        # `arr` moved into state (no longer read-only) -- must not match,
        # since the carry proof assumes `src` never changes.
        self.assertIsNone(
            lv._verus_closure_carry_target(w, invs, [], state + ["arr"]))

    def test_no_match_when_ctr_is_not_the_forall_hi(self):
        w, invs, ro, state = _findeven_shape()
        invs[1]["forall"]["hi"] = {"var": "evenList"}  # wrong var, not ctr
        self.assertIsNone(
            lv._verus_closure_carry_target(w, invs, ro, state))

    def test_no_match_on_two_statement_state_change_in_body(self):
        w, invs, ro, state = _findeven_shape()
        w["body"].append(
            {"assign": ["evenList", {"var": "evenList"}]})
        self.assertIsNone(
            lv._verus_closure_carry_target(w, invs, ro, state))

    def test_assert_text_mentions_old_and_new_state(self):
        w, invs, ro, state = _findeven_shape()
        c = lv._verus_closure_carry_target(w, invs, ro, state)
        text = lv._verus_closure_carry_assert(c)
        self.assertIn("t_old_i_v2", text)
        self.assertIn("t_old_evenList", text)
        self.assertIn("choose|k_v5", text)
        self.assertIn("assert forall|k_v4", text)


class UnrollSpecFunInlineTest(unittest.TestCase):
    def _inarray(self):
        return {
            "inArray": {
                "name": "inArray",
                "params": [{"name": "a_v", "type": "seq"},
                          {"name": "x", "type": "int"}],
                "body": {"exists": {
                    "var": "i", "lo": {"int": 0},
                    "hi": {"op": "len", "args": [{"var": "a_v"}]},
                    "body": {"op": "==",
                            "args": [_at("a_v", "i"), {"var": "x"}]},
                }},
            }
        }

    def test_ground_quantifier_spec_fun_call_is_inlined(self):
        spec_funs = self._inarray()
        e = {"call": {"fun": "inArray",
                      "args": [{"_seq": [7]}, {"int": 7}]}}
        out = lv._unroll(e, [lv._UNROLL_CAP], spec_funs)
        # A single-element ground seq unrolls the exists to one instance,
        # no "call" node to inArray should remain in the result.
        self.assertFalse(lv._calls(out, "inArray"))

    def test_recursive_ite_spec_fun_call_is_left_uninlined(self):
        factorial = {
            "factorial": {
                "name": "factorial",
                "params": [{"name": "n_v", "type": "int"}],
                "body": {"ite": {
                    "cond": {"op": "==", "args": [{"var": "n_v"}, {"int": 0}]},
                    "then": {"int": 1},
                    "else": {"op": "*", "args": [
                        {"var": "n_v"},
                        {"call": {"fun": "factorial", "args": [
                            {"op": "-", "args": [{"var": "n_v"}, {"int": 1}]}]}},
                    ]},
                }},
            }
        }
        e = {"call": {"fun": "factorial", "args": [{"int": 5}]}}
        # Must not recurse forever (would raise RecursionError, the
        # measured 2026-09-15 regression on row 577); the call is left
        # as a plain call node instead of being unfolded.
        out = lv._unroll(e, [lv._UNROLL_CAP], factorial)
        self.assertIn("call", out)
        self.assertEqual(out["call"]["fun"], "factorial")

    def test_no_spec_funs_argument_is_unaffected(self):
        e = {"call": {"fun": "isEven", "args": [{"int": 4}]}}
        out = lv._unroll(e, [lv._UNROLL_CAP])
        self.assertEqual(out, {"call": {"fun": "isEven", "args": [{"int": 4}]}})


if __name__ == "__main__":
    unittest.main()
