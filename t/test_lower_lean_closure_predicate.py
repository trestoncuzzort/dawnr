"""t/test_lower_lean_closure_predicate.py: unit tests for lower_lean.py's
2026-09-14 lean-closure fixes (ROADMAP 16.2, this session's own item:
"the closure-predicate timeouts and the seq-typed local abstains").

Two independent fixes, pinned separately below:

1. `Lower.sfun_quantified` / `Lower._grind_base`: a spec_fun called
   inside a `forall`/`exists` (isEven/isOdd/isNegative-style closure
   predicates over a loop's own invariant, dafny_synthesis 412/426/436/
   554/629's shared shape) used to hand `grind` the spec_fun's own
   equation as a raw E-matching hint (`grind [isEven_s]`) at every
   grind call site in the file -- measured (`lean -DmaxHeartbeats=
   400000` on the emitted 412.RemoveOddNumbers file, `set_option
   trace.grind.ematch true`) to exhaust the WHOLE per-command heartbeat
   budget searching whether to unfold the spec_fun at every quantifier
   instantiation combined with the invariant list's own case splits (a
   `deterministic timeout` is not a normal tactic failure: `first`
   never gets a turn to try the next branch, so real and twin both read
   TIMEOUT). The fix cites the spec_fun's own equation as a
   deterministic `simp only` rewrite first instead (closes over the
   whole goal, including under a quantifier binder, with no E-matching
   search), and drops it from grind's own hint list. Gated strictly on
   `sfun_quantified`, so a task lowered before this session (none of
   which call a spec_fun under a quantifier -- none use spec_funs at
   all, `grep -l spec_funs t/tasks/*.t` reads empty) sees byte-
   identical output; pinned below by an inline non-quantified spec_fun
   task alongside the quantified one, so a future change cannot widen
   the gate without failing a test.

2. `Lower._loop_zero`: a bare `seq`-typed return var not yet set
   entering the loop (307 DeepCopySeq: `copy` is assigned only in the
   SUFFIX, `copy := newSeq`, never touched in the prefix or the loop
   itself) hit an unconditional `None` placeholder, an honest
   `NotImplementedError` ("state var 'copy' uninitialized before the
   loop") -- ABSTAIN, never a kernel call. `List Int`'s own canonical
   placeholder, the empty list, is total and well-typed exactly like
   `(0 : Int)`/`false` for `int`/`bool`; adding it only changes a
   lowering that previously raised (the docstring at `_loop_zero`
   itself: dead for reverse/filter_pos, both of which assign `r` in
   their own prefix), so this too is regression-free by construction.

Both pinned via inline tasks (not read from t/out/lifted-tasks,
gitignored, read-only) so these tests are reproducible from the
committed repo alone, the same convention test_lower_lean_loop_cert.py
uses.

Run: cd <repo>/t && python3 test_lower_lean_closure_predicate.py

MEASURED 2026-09-14 by `python3 t/test_lower_lean_closure_predicate.py`:
see the printed unittest summary this run produces.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lower_lean


class ClosurePredicateQuantifiedTest(unittest.TestCase):
    """A spec_fun (`isPos`) called inside a loop invariant's own
    `forall` -- the 412/426/436/554/629 shared shape, shrunk to a
    single invariant. `sfun_quantified` must read True, and the emitted
    source must never hand `grind` the spec_fun's equation as a raw
    E-match hint (`grind [isPos_s]`, unqualified by a preceding `simp
    only`) anywhere -- every one of the 12 `grind{self.ga}`-derived
    call sites in the file goes through `_grind_base` now."""

    TASK = {
        "name": "closure_pred_probe",
        "params": [{"name": "arr", "type": "seq"}],
        "returns": [{"name": "count", "type": "int"}],
        "requires": [],
        "ensures": [
            {"op": "<=", "args": [{"int": 0}, {"var": "count"}]}],
        "spec_funs": [{
            "name": "isPos",
            "params": [{"name": "n", "type": "int"}],
            "result": "bool",
            "body": {"op": ">", "args": [{"var": "n"}, {"int": 0}]},
        }],
        "body": [
            {"assign": ["count", {"int": 0}]},
            {"var": {"name": "h", "type": "int",
                     "init": {"op": "len", "args": [{"var": "arr"}]}}},
            {"var": {"name": "i_v", "type": "int", "init": {"int": 0}}},
            {"while": {
                "cond": {"op": "<", "args": [{"var": "i_v"}, {"var": "h"}]},
                "decreases": {"op": "-", "args": [{"var": "h"},
                                                  {"var": "i_v"}]},
                "invariants": [
                    {"op": "and", "args": [
                        {"op": "<=", "args": [{"int": 0}, {"var": "i_v"}]},
                        {"op": "<=", "args": [{"var": "i_v"}, {"var": "h"}]}]},
                    {"forall": {
                        "var": "k", "lo": {"int": 0}, "hi": {"var": "i_v"},
                        "body": {"op": "==", "args": [
                            {"call": {"fun": "isPos", "args": [
                                {"op": "at", "args": [{"var": "arr"},
                                                       {"var": "k"}]}]}},
                            {"bool": True}]}}}],
                "body": [
                    {"if": {
                        "cond": {"call": {"fun": "isPos", "args": [
                            {"op": "at", "args": [{"var": "arr"},
                                                   {"var": "i_v"}]}]}},
                        "then": [{"assign": ["count", {"op": "+", "args": [
                            {"var": "count"}, {"int": 1}]}]}],
                        "else": []}},
                    {"assign": ["i_v", {"op": "+", "args": [
                        {"var": "i_v"}, {"int": 1}]}]}],
            }},
        ],
    }

    def test_sfun_quantified_detected(self):
        lw = lower_lean.Lower(self.TASK, self.TASK["body"])
        self.assertTrue(lw.sfun_quantified)

    def test_no_raw_grind_ematch_hint_for_the_quantified_spec_fun(self):
        src = lower_lean.lower(self.TASK, self.TASK["body"])
        self.assertIn("simp only [isPos_s] at * <;> grind", src)
        # every remaining "grind [isPos_s]" must be preceded by the
        # deterministic simp pass, never handed to grind bare.
        idx = 0
        while True:
            idx = src.find("grind [isPos_s]", idx)
            if idx == -1:
                break
            window = src[max(0, idx - 40):idx]
            self.assertIn("simp only [isPos_s] at * <;> ", window,
                          "a bare grind ematch hint on the quantified "
                          "spec_fun survived _grind_base")
            idx += 1

    def test_lowers_without_raising(self):
        # the regression this whole item chases: this used to be a
        # `deterministic timeout` on the kernel side, but at minimum
        # the lowering itself must not raise or hang.
        src = lower_lean.lower(self.TASK, self.TASK["body"])
        self.assertIn("theorem closure_pred_probe_t_loop_spec", src)


class NonQuantifiedSpecFunUnchangedTest(unittest.TestCase):
    """A spec_fun called OUTSIDE any quantifier (a plain `if isPos(x)`
    with no forall/exists anywhere in the task) must still see the
    pre-existing `grind [isPos_s]` hint, unchanged -- `sfun_quantified`
    must read False, and `_grind_base` must fall back to
    `f"grind{self.ga}"` byte-for-byte."""

    TASK = {
        "name": "plain_sfun_probe",
        "params": [{"name": "n", "type": "int"}],
        "returns": [{"name": "r", "type": "bool"}],
        "requires": [],
        "ensures": [
            {"op": "==", "args": [
                {"var": "r"},
                {"call": {"fun": "isPos", "args": [{"var": "n"}]}}]}],
        "spec_funs": [{
            "name": "isPos",
            "params": [{"name": "n", "type": "int"}],
            "result": "bool",
            "body": {"op": ">", "args": [{"var": "n"}, {"int": 0}]},
        }],
        "body": [
            {"assign": ["r", {"call": {"fun": "isPos",
                                       "args": [{"var": "n"}]}}]},
        ],
    }

    def test_sfun_quantified_false(self):
        lw = lower_lean.Lower(self.TASK, self.TASK["body"])
        self.assertFalse(lw.sfun_quantified)

    def test_grind_base_is_the_plain_hint(self):
        lw = lower_lean.Lower(self.TASK, self.TASK["body"])
        self.assertEqual(lw._grind_base(), "grind [isPos_s]")


class SeqTypedLocalPlaceholderTest(unittest.TestCase):
    """307 DeepCopySeq's own shape, shrunk: a bare `seq`-typed return
    var (`copy`) assigned only in the suffix (`copy := newSeq`, after
    the loop), never in the prefix or the loop body. Used to raise
    NotImplementedError("state var 'copy' uninitialized before the
    loop"); must now lower using the empty-list placeholder."""

    TASK = {
        "name": "seq_local_probe",
        "params": [{"name": "s", "type": "seq"}],
        "returns": [{"name": "copy", "type": "seq"}],
        "requires": [],
        "ensures": [
            {"op": "==", "args": [
                {"op": "len", "args": [{"var": "copy"}]},
                {"op": "len", "args": [{"var": "s"}]}]}],
        "body": [
            {"var": {"name": "newSeq", "type": "seq",
                     "init": {"op": "seq", "args": []}}},
            {"var": {"name": "h", "type": "int",
                     "init": {"op": "len", "args": [{"var": "s"}]}}},
            {"var": {"name": "i_v", "type": "int", "init": {"int": 0}}},
            {"while": {
                "cond": {"op": "<", "args": [{"var": "i_v"}, {"var": "h"}]},
                "decreases": {"op": "-", "args": [{"var": "h"},
                                                  {"var": "i_v"}]},
                "invariants": [
                    {"op": "and", "args": [
                        {"op": "<=", "args": [{"int": 0}, {"var": "i_v"}]},
                        {"op": "<=", "args": [{"var": "i_v"}, {"var": "h"}]}]}],
                "body": [
                    {"assign": ["newSeq", {"op": "+", "args": [
                        {"var": "newSeq"},
                        {"op": "seq", "args": [
                            {"op": "at", "args": [{"var": "s"},
                                                  {"var": "i_v"}]}]}]}]},
                    {"assign": ["i_v", {"op": "+", "args": [
                        {"var": "i_v"}, {"int": 1}]}]}],
            }},
            {"assign": ["copy", {"var": "newSeq"}]},
        ],
    }

    def test_loop_zero_has_a_seq_placeholder(self):
        lw = lower_lean.Lower(self.TASK, self.TASK["body"])
        self.assertEqual(lw._loop_zero("seq"), "([] : List Int)")

    def test_lowers_without_raising(self):
        src = lower_lean.lower(self.TASK, self.TASK["body"])
        self.assertIn("([] : List Int)", src)
        self.assertIn("theorem seq_local_probe_t_spec", src)


if __name__ == "__main__":
    unittest.main()
