"""t/test_lower_lean_append1.py: unit tests for lower_lean.py's 2026-09-19
ROADMAP 16.2 additions (lean's own item, "the append-one-element loop"):
`_if_in_branch` / `Lower._split_tac` (THE NESTED-IF SPLIT GAP) and
`_append1_targets` / `Lower.seq_append1` / `Lower._seq_append1_pres_script`
(THE INVARIANT-APPLICATION LEAF, closed).

Pure-Python tests over the detectors, the gate and the emitted tactic
TEXT -- no lean binary is invoked here (the kernel's own verdict is what
`t/run_par.py` and `t/recheck_near.py` measure). What these catch is the
class of bug this wave had to measure its way out of twice:

  - a GATE that fires for a task the script cannot close, which would put
    two extra lemmas and a failing `first`-alternative into a file that
    was byte-identical before (the file's whole additive discipline);
  - a SPLIT rule that silently reverts to the old form for the nested
    shape, which is what left `mbpp_557__toggle_string`'s own `isFalse`
    branch with an un-split `ite` no append lemma can rewrite under;
  - the `by`-swallows-the-rest parse trap (`have h : P := by omega; subst
    h` runs `subst` INSIDE the `have`'s own tactic block), which this
    file's standing docstrings name twice and which cost this wave a
    measurement round; and
  - a chain that can succeed without closing its goal -- the emitted
    script must end in `done`.

Run: python3 t/test_lower_lean_append1.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lower_lean


def _append_stmt(var="r", elem=None):
    """`var := var + [elem]`, the write shape `_append1_targets` keys on."""
    return {"assign": [var, {"op": "+", "args": [
        {"var": var},
        {"op": "seq", "args": [elem or {"op": "at", "args": [
            {"var": "s"}, {"var": "i"}]}]}]}]}


def _forall_inv(body=None):
    return {"forall": {"var": "j", "lo": {"int": 0},
                       "hi": {"op": "len", "args": [{"var": "r"}]},
                       "body": body or {"op": "==", "args": [
                           {"op": "at", "args": [{"var": "r"}, {"var": "j"}]},
                           {"op": "at", "args": [{"var": "s"},
                                                 {"var": "j"}]}]}}}


def _loop_task(loop_body, invariants, name="build"):
    """A one-loop task in the shape of the 26 near-miss answers: a seq
    return built one element per iteration under a counter."""
    return {
        "t": 1,
        "name": name,
        "params": [{"name": "s", "type": "seq"}],
        "returns": [{"name": "r", "type": "seq"}],
        "requires": [],
        "ensures": [{"op": "==", "args": [
            {"op": "len", "args": [{"var": "r"}]},
            {"op": "len", "args": [{"var": "s"}]}]}],
        "body": [
            {"assign": ["r", {"op": "seq", "args": []}]},
            {"var": {"name": "i", "type": "int", "init": {"int": 0}}},
            {"while": {
                "cond": {"op": "<", "args": [
                    {"var": "i"}, {"op": "len", "args": [{"var": "s"}]}]},
                "invariants": invariants,
                "decreases": {"op": "-", "args": [
                    {"op": "len", "args": [{"var": "s"}]}, {"var": "i"}]},
                "body": loop_body + [
                    {"assign": ["i", {"op": "+", "args": [
                        {"var": "i"}, {"int": 1}]}]}],
            }},
        ],
    }


class IfInBranchTest(unittest.TestCase):
    """THE NESTED-IF SPLIT GAP's own detector."""

    def test_flat_if_is_not_nested(self):
        body = [{"if": {"cond": {"var": "c"},
                        "then": [_append_stmt()], "else": []}}]
        self.assertFalse(lower_lean._if_in_branch(body))

    def test_two_sequential_ifs_are_not_nested(self):
        # min_max's own shape: two TOP-LEVEL ifs, which the pre-existing
        # `repeat (all_goals split)` rule already covers -- it must NOT
        # be rerouted to the new form, or that measured row changes.
        one = {"if": {"cond": {"var": "c"}, "then": [], "else": []}}
        self.assertFalse(lower_lean._if_in_branch([one, dict(one)]))

    def test_if_in_else_is_nested(self):
        # toggle_string's own shape: `if lower .. else if upper .. else ..`
        inner = {"if": {"cond": {"var": "d"}, "then": [], "else": []}}
        body = [{"if": {"cond": {"var": "c"},
                        "then": [], "else": [inner]}}]
        self.assertTrue(lower_lean._if_in_branch(body))

    def test_if_in_then_is_nested(self):
        inner = {"if": {"cond": {"var": "d"}, "then": [], "else": []}}
        body = [{"if": {"cond": {"var": "c"},
                        "then": [inner], "else": []}}]
        self.assertTrue(lower_lean._if_in_branch(body))

    def test_deeper_nesting_is_found(self):
        deep = {"if": {"cond": {"var": "e"}, "then": [], "else": []}}
        mid = {"if": {"cond": {"var": "d"}, "then": [], "else": [deep]}}
        body = [{"if": {"cond": {"var": "c"}, "then": [], "else": [mid]}}]
        self.assertTrue(lower_lean._if_in_branch(body))

    def test_non_list_is_not_nested(self):
        self.assertFalse(lower_lean._if_in_branch(None))
        self.assertFalse(lower_lean._if_in_branch({"if": {}}))


class SplitTacTest(unittest.TestCase):
    """The three forms, and that the two older ones are untouched."""

    def test_zero_or_one_if_keeps_repeat_split(self):
        self.assertEqual(lower_lean.Lower._split_tac([]), "repeat split")
        one = [{"if": {"cond": {"var": "c"}, "then": [], "else": []}}]
        self.assertEqual(lower_lean.Lower._split_tac(one), "repeat split")

    def test_two_top_level_ifs_keep_all_goals_form(self):
        one = {"if": {"cond": {"var": "c"}, "then": [], "else": []}}
        self.assertEqual(lower_lean.Lower._split_tac([one, dict(one)]),
                         "repeat (all_goals split)")

    def test_nested_if_uses_repeat_prime(self):
        inner = {"if": {"cond": {"var": "d"}, "then": [], "else": []}}
        body = [{"if": {"cond": {"var": "c"}, "then": [], "else": [inner]}}]
        self.assertEqual(lower_lean.Lower._split_tac(body), "repeat' split")

    def test_nesting_outranks_the_count(self):
        # A body with BOTH two top-level ifs and nesting needs the
        # per-goal recursion; `repeat (all_goals split)` reverts its whole
        # round the moment one sibling has nothing left to split.
        inner = {"if": {"cond": {"var": "d"}, "then": [], "else": []}}
        a = {"if": {"cond": {"var": "c"}, "then": [], "else": [inner]}}
        b = {"if": {"cond": {"var": "e"}, "then": [], "else": []}}
        self.assertEqual(lower_lean.Lower._split_tac([a, b]),
                         "repeat' split")


class Append1TargetsTest(unittest.TestCase):
    """THE APPEND-ONE-ELEMENT LOOP's own write-shape detector."""

    def test_finds_a_flat_self_append(self):
        self.assertEqual(lower_lean._append1_targets([_append_stmt()]),
                         {"r"})

    def test_finds_one_nested_under_two_ifs(self):
        inner = {"if": {"cond": {"var": "d"},
                        "then": [_append_stmt()], "else": []}}
        body = [{"if": {"cond": {"var": "c"},
                        "then": [], "else": [inner]}}]
        self.assertEqual(lower_lean._append1_targets(body), {"r"})

    def test_ignores_appending_a_whole_seq(self):
        # `r := r + t` -- the seam index is not provably |r| + nothing,
        # so `t_seq_append1_get` does not apply and the shape is left to
        # the pre-existing machinery.
        body = [{"assign": ["r", {"op": "+", "args": [
            {"var": "r"}, {"var": "t"}]}]}]
        self.assertEqual(lower_lean._append1_targets(body), set())

    def test_ignores_a_two_element_literal(self):
        body = [{"assign": ["r", {"op": "+", "args": [
            {"var": "r"},
            {"op": "seq", "args": [{"int": 1}, {"int": 2}]}]}]}]
        self.assertEqual(lower_lean._append1_targets(body), set())

    def test_ignores_appending_to_something_else(self):
        body = [{"assign": ["r", {"op": "+", "args": [
            {"var": "q"}, {"op": "seq", "args": [{"int": 1}]}]}]}]
        self.assertEqual(lower_lean._append1_targets(body), set())

    def test_ignores_int_addition(self):
        body = [{"assign": ["i", {"op": "+", "args": [
            {"var": "i"}, {"int": 1}]}]}]
        self.assertEqual(lower_lean._append1_targets(body), set())


class SeqAppend1GateTest(unittest.TestCase):
    """Both halves of the gate are required, so a task outside this shape
    keeps its exact prior emitted source."""

    def test_fires_on_append_under_a_forall_invariant(self):
        task = _loop_task([_append_stmt()], [_forall_inv()])
        lw = lower_lean.Lower(task, task["body"])
        self.assertEqual(lw.seq_append1, {"r"})

    def test_silent_without_a_quantified_invariant(self):
        task = _loop_task([_append_stmt()], [
            {"op": "<=", "args": [{"int": 0}, {"var": "i"}]}])
        lw = lower_lean.Lower(task, task["body"])
        self.assertEqual(lw.seq_append1, set())

    def test_silent_without_an_append(self):
        task = _loop_task(
            [{"assign": ["r", {"op": "update", "args": [
                {"var": "r"}, {"var": "i"}, {"int": 0}]}]}],
            [_forall_inv()])
        lw = lower_lean.Lower(task, task["body"])
        self.assertEqual(lw.seq_append1, set())

    def test_silent_on_a_loopless_task(self):
        task = {
            "t": 1, "name": "noloop",
            "params": [{"name": "s", "type": "seq"}],
            "returns": [{"name": "r", "type": "seq"}],
            "requires": [], "ensures": [],
            "body": [{"assign": ["r", {"op": "+", "args": [
                {"var": "r"}, {"op": "seq", "args": [{"int": 1}]}]}]}],
        }
        lw = lower_lean.Lower(task, task["body"])
        self.assertEqual(lw.seq_append1, set())

    def test_helper_lemmas_follow_the_gate(self):
        on = _loop_task([_append_stmt()], [_forall_inv()])
        off = _loop_task([_append_stmt()], [
            {"op": "<=", "args": [{"int": 0}, {"var": "i"}]}])
        src_on = lower_lean.Lower(on, on["body"]).emit_seq_helpers()
        src_off = lower_lean.Lower(off, off["body"]).emit_seq_helpers()
        for name in ("t_seq_append_get_lo", "t_seq_append1_get"):
            self.assertIn(f"theorem {name} ", src_on)
            self.assertNotIn(f"theorem {name} ", src_off)
        # the pre-existing bridge is emitted either way: only the two
        # ite-free corollaries are new, and only under the gate.
        self.assertIn("theorem t_seq_append_get ", src_off)


class PresScriptTest(unittest.TestCase):
    """The emitted tactic text: the traps this wave measured, asserted."""

    def _script(self):
        task = _loop_task([_append_stmt()], [_forall_inv()])
        lw = lower_lean.Lower(task, task["body"])
        return lw._seq_append1_pres_script(
            ["r", "i"], {"r": "seq", "i": "int", "s": "seq"},
            [{"op": "<=", "args": [{"int": 0}, {"var": "i"}]}, _forall_inv()])

    def test_none_outside_the_gate(self):
        task = _loop_task([_append_stmt()], [
            {"op": "<=", "args": [{"int": 0}, {"var": "i"}]}])
        lw = lower_lean.Lower(task, task["body"])
        self.assertIsNone(lw._seq_append1_pres_script(
            ["r", "i"], {"r": "seq", "i": "int"}, []))

    def test_none_without_a_quantified_invariant_in_the_list(self):
        task = _loop_task([_append_stmt()], [_forall_inv()])
        lw = lower_lean.Lower(task, task["body"])
        self.assertIsNone(lw._seq_append1_pres_script(
            ["r", "i"], {"r": "seq", "i": "int"},
            [{"op": "<=", "args": [{"int": 0}, {"var": "i"}]}]))

    def test_cites_the_quantified_invariant_by_its_hinv_index(self):
        # the forall is invariant 2 of 2, so `hinv2` -- never `hinv1`,
        # whose goal has no binders to `intro` at all.
        s = self._script()
        self.assertIn("exact hinv2 _tj (by omega) (by omega)", s)
        self.assertNotIn("hinv1 _tj", s)

    def test_decides_the_seam_on_the_appended_variable(self):
        self.assertIn("by_cases _tlo : _tj < ((r).length : Int)",
                      self._script())

    def test_cites_both_ite_free_corollaries(self):
        s = self._script()
        self.assertIn("only [t_seq_append_get_lo]", s)
        self.assertIn("only [t_seq_append1_get]", s)

    def test_normalizes_the_singleton_length(self):
        # `List.length_append` alone leaves `[x].length` an opaque atom
        # omega cannot see through -- THE SINGLETON-LENGTH GAP.
        s = self._script()
        self.assertIn("List.length_cons", s)
        self.assertIn("List.length_nil", s)

    def test_by_is_parenthesized_at_every_have(self):
        # `have h : P := by omega; subst h` parses as `have h : P := by
        # (omega; subst h)`, which runs `subst` with no goals left. Every
        # `:=` in this script must be followed by a parenthesized `by`.
        s = self._script()
        self.assertIn(":= (by omega); subst _tji", s)
        self.assertNotIn(":= by omega; subst", s)

    def test_ends_in_done(self):
        # the standing rule: an alternative must close its goal, never
        # merely make progress and leave the rest to Lean's own sorryAx.
        self.assertTrue(self._script().rstrip().endswith("done)"))

    def test_only_int_typed_variables_get_a_subst(self):
        task = _loop_task([_append_stmt()], [_forall_inv()])
        lw = lower_lean.Lower(task, task["body"])
        s = lw._seq_append1_pres_script(
            ["r", "i"], {"r": "seq", "i": "int"}, [_forall_inv()])
        self.assertIn("have _tji : _tj = i :=", s)
        self.assertNotIn("_tj = r :=", s)
        self.assertNotIn("_tj = s :=", s)


class ExitScriptTest(unittest.TestCase):
    """The guard-false branch's own closer -- the loop is over, so there
    is no append to rewrite and the ensures IS the invariant."""

    def _task(self):
        return _loop_task([_append_stmt()], [
            {"op": "==", "args": [
                {"op": "len", "args": [{"var": "r"}]}, {"var": "i"}]},
            _forall_inv()])

    def test_none_outside_the_gate(self):
        task = _loop_task([_append_stmt()], [
            {"op": "<=", "args": [{"int": 0}, {"var": "i"}]}])
        lw = lower_lean.Lower(task, task["body"])
        self.assertIsNone(lw._seq_append1_exit_script([_forall_inv()]))

    def test_none_without_a_quantified_invariant_in_the_list(self):
        task = self._task()
        lw = lower_lean.Lower(task, task["body"])
        self.assertIsNone(lw._seq_append1_exit_script(
            [{"op": "<=", "args": [{"int": 0}, {"var": "i"}]}]))

    def test_cites_the_invariant_with_an_inferred_index(self):
        # the opener's `intro` leaves an inaccessible binder name, so the
        # index MUST be `_` and recovered by unification.
        task = self._task()
        lw = lower_lean.Lower(task, task["body"])
        s = lw._seq_append1_exit_script(
            [{"op": "<=", "args": [{"int": 0}, {"var": "i"}]}, _forall_inv()])
        self.assertIn("exact hinv2 _ (by omega) (by omega)", s)
        self.assertNotIn("hinv1 _ (by", s)
        self.assertTrue(s.rstrip().endswith("done)"))

    def test_does_not_rewrite_anything(self):
        # no append survives the guard-false branch, so citing an append
        # lemma here would only be dead text.
        task = self._task()
        lw = lower_lean.Lower(task, task["body"])
        s = lw._seq_append1_exit_script([_forall_inv()])
        self.assertNotIn("t_seq_append_get_lo", s)
        self.assertNotIn("t_seq_append1_get", s)


class EmittedLoopTest(unittest.TestCase):
    """The two changes where they actually land, in `lower_loop`'s text."""

    def test_nested_body_gets_repeat_prime_and_the_pres_script(self):
        inner = {"if": {"cond": {"op": ">=", "args": [
            {"op": "at", "args": [{"var": "s"}, {"var": "i"}]},
            {"int": 65}]},
            "then": [_append_stmt()],
            "else": [_append_stmt(elem={"int": 0})]}}
        body = [{"if": {"cond": {"op": ">=", "args": [
            {"op": "at", "args": [{"var": "s"}, {"var": "i"}]},
            {"int": 97}]},
            "then": [_append_stmt()], "else": [inner]}}]
        task = _loop_task(body, [
            {"op": "==", "args": [
                {"op": "len", "args": [{"var": "r"}]}, {"var": "i"}]},
            _forall_inv()])
        src = lower_lean.lower(task, task["body"])
        self.assertIn("  · repeat' split\n", src)
        self.assertIn("by_cases _tlo : _tj < ((r).length : Int)", src)
        self.assertIn("theorem t_seq_append_get_lo ", src)
        self.assertIn("#print axioms t_seq_append1_get", src)

    def test_a_task_outside_the_shape_is_untouched(self):
        # no append, no forall: none of this wave's text appears at all.
        task = _loop_task(
            [{"assign": ["r", {"op": "update", "args": [
                {"var": "r"}, {"var": "i"}, {"int": 0}]}]}],
            [{"op": "<=", "args": [{"int": 0}, {"var": "i"}]}])
        src = lower_lean.lower(task, task["body"])
        for token in ("repeat' split\n", "_tlo", "t_seq_append_get_lo",
                      "t_seq_append1_get"):
            self.assertNotIn(token, src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
