"""t/test_lower_verus_refusals.py: unit tests for the 2026-09-14 fix to
`lower_verus.py`'s `loop()` (ROADMAP 16.2, verus-refusal item).

Before this fix, a loop whose body assigns no in-scope variable at all
(`state` empty in `loop()`) hit a bare `assert state, ...`, an
AssertionError -- classified by run_par.lower_and_dispatch as LOWER-ERROR,
not a named refusal (harness.py's own contract: NotImplementedError is the
only exception a lowering may raise to mean "this shape is not supported";
anything else is a crash). Measured on the lifted-corpus row
`mfs_tmp_tmpmmnu354t_testes_anteriores_t2_ex5_2020_2__leq`'s verus twin
(sweep r23, ROADMAP 16.2 2026-09-12 08:37Z): a collapse-if twin whose
`if a[i]<b[i] ... else if a[i]>b[i] ... else i=i+1` collapsed to a bare
unconditional `return result := true`, so `state` (`_assigned(body) -
_declared(body)`) came out empty.

Two things changed:
  1. The assert is now a `NotImplementedError("verus: collapse-if twin:
     loop body assigns no variable in scope")`, so the shape reads a named
     refusal (row: abstain) instead of a crash (row: lower-error) whenever
     it cannot be lowered soundly.
  2. When the body is GUARANTEED to return on every path through one
     execution (`_always_returns`), the loop runs at most once (any
     execution of the body ends the whole task, so "loop again with
     unchanged state" never happens) and is lowered instead: the exact
     lifted row above now measures verus real=unproved, twin=refuted
     (`python3 t/grade.py --tasks <dir-with-just-this-record> --kernels
     verus,dafny --flake 3`, 2026-09-14) where it used to measure
     lower-error/lower-error.

Measured by `python3 test_lower_verus_refusals.py` from t/.
"""
import glob
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lower_verus as lv
import tasks_io


def _leq_task_and_bodies():
    """The exact task and twin body that triggered the original crash
    (mfs_tmp_tmpmmnu354t_testes_anteriores_t2_ex5_2020_2__leq), read
    straight from the lifted corpus so this test tracks the real record,
    not a hand-reconstructed stand-in. Skipped (not failed) when the
    lifted corpus is not present in this checkout -- it is a large
    generated artifact, not tracked alongside the source files this task
    owns."""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(
        here, "out", "lifted-tasks",
        "MFS_tmp_tmpmmnu354t_Testes anteriores_T2_ex5_2020_2.leq.json")
    if not os.path.exists(path):
        return None
    import harness
    task = harness.load(path)
    twin_body, op, w = harness.twin_cached(task)
    return task, twin_body, op, w


class AlwaysReturnsTest(unittest.TestCase):
    """`_always_returns` decides exactly the soundness question `loop()`
    now asks of an empty-`state` body: does every path through one
    execution reach a `return` before falling off the end?"""

    def test_empty_body_never_returns(self):
        self.assertFalse(lv._always_returns([]))

    def test_bare_return_always_returns(self):
        self.assertTrue(lv._always_returns(
            [{"return": ["r", {"bool": True}]}]))

    def test_if_both_branches_return(self):
        body = [{"if": {"cond": {"bool": True},
                        "then": [{"return": ["r", {"bool": True}]}],
                        "else": [{"return": ["r", {"bool": False}]}]}}]
        self.assertTrue(lv._always_returns(body))

    def test_if_only_then_returns_does_not_always_return(self):
        body = [{"if": {"cond": {"bool": True},
                        "then": [{"return": ["r", {"bool": True}]}],
                        "else": []}}]
        self.assertFalse(lv._always_returns(body))

    def test_while_alone_never_counts(self):
        # A nested while whose OWN body always returns does not make the
        # outer statement list always-return: the while's guard can be
        # false on entry, so control can fall through it untouched.
        w = {"cond": {"bool": True}, "invariants": [],
             "decreases": {"int": 0},
             "body": [{"return": ["r", {"bool": True}]}]}
        self.assertFalse(lv._always_returns([{"while": w}]))

    def test_statement_after_a_return_is_irrelevant(self):
        body = [{"return": ["r", {"bool": True}]},
                {"assign": ["x", {"int": 1}]}]
        self.assertTrue(lv._always_returns(body))


class EmptyStateLoopRefusalTest(unittest.TestCase):
    """Two synthetic collapse-if-like shapes, both with `state` empty
    (the loop body assigns no in-scope variable), one that can never
    fall through without returning (soundly lowerable) and one that can
    (still refused, by name, not by crash)."""

    def _base_task(self):
        return {
            "t": 1, "name": "empty_state_probe",
            "params": [{"name": "a", "type": "seq"},
                      {"name": "b", "type": "seq"}],
            "returns": [{"name": "result", "type": "bool"}],
            "requires": [],
            "ensures": [{"var": "result"}],
        }

    def _cond(self):
        return {"op": "and", "args": [
            {"op": "<", "args": [{"var": "i"},
                                 {"op": "len", "args": [{"var": "a"}]}]},
            {"op": "<", "args": [{"var": "i"},
                                 {"op": "len", "args": [{"var": "b"}]}]}]}

    def test_no_return_no_assign_still_refuses_by_name(self):
        """A loop body that neither assigns nor ever returns: if the
        guard is ever true, this would loop forever with unchanged
        state -- not safe to translate into a Verus recursive function
        with a real `decreases` clause. Must raise NotImplementedError
        (a named refusal), never an AssertionError (a crash)."""
        task = self._base_task()
        w = {"cond": self._cond(), "invariants": [],
             "decreases": {"op": "-", "args": [
                 {"op": "len", "args": [{"var": "a"}]}, {"var": "i"}]},
             "body": []}
        body = [{"var": {"name": "i", "type": "int", "init": {"int": 0}}},
                {"while": w}]
        with self.assertRaises(NotImplementedError) as ctx:
            lv.lower(task, body)
        self.assertNotIsInstance(ctx.exception, AssertionError)
        self.assertIn("collapse-if twin", str(ctx.exception))
        self.assertIn("loop body assigns no variable in scope",
                      str(ctx.exception))

    def test_conditional_return_only_on_one_path_still_refuses(self):
        """Body returns on the `then` branch, does nothing on `else`: not
        every path returns, so the `else` path would loop with unchanged
        state forever. Still a named refusal."""
        task = self._base_task()
        w = {"cond": self._cond(), "invariants": [],
             "decreases": {"op": "-", "args": [
                 {"op": "len", "args": [{"var": "a"}]}, {"var": "i"}]},
             "body": [{"if": {"cond": {"bool": True},
                              "then": [{"return": ["result", {"bool": True}]}],
                              "else": []}}]}
        body = [{"var": {"name": "i", "type": "int", "init": {"int": 0}}},
                {"while": w}]
        with self.assertRaises(NotImplementedError) as ctx:
            lv.lower(task, body)
        self.assertIn("collapse-if twin", str(ctx.exception))

    def test_unconditional_return_body_lowers_instead_of_crashing(self):
        """Body is a bare, unconditional `return`: every execution of the
        body ends the task, so the loop runs at most once and this is
        sound to lower (no `assert`, no `NotImplementedError`)."""
        task = self._base_task()
        w = {"cond": self._cond(), "invariants": [],
             "decreases": {"op": "-", "args": [
                 {"op": "len", "args": [{"var": "a"}]}, {"var": "i"}]},
             "body": [{"return": ["result", {"bool": True}]}]}
        body = [{"var": {"name": "i", "type": "int", "init": {"int": 0}}},
                {"while": w}]
        out = lv.lower(task, body)
        self.assertIn("proof fn empty_state_probe", out)
        self.assertIn("-> (t_res: (bool, bool, ()))", out)


class LeqLiftedRowTest(unittest.TestCase):
    """The exact lifted-corpus record that crashed before this fix now
    lowers cleanly (skipped, not failed, if the lifted corpus is not
    present in this checkout)."""

    def test_leq_twin_lowers_without_crashing(self):
        found = _leq_task_and_bodies()
        if found is None:
            self.skipTest("t/out/lifted-tasks not present in this checkout")
        task, twin_body, op, w = found
        self.assertEqual(op, "collapse-if")
        out = lv.lower(task, twin_body, witness=w)
        self.assertIn(
            "proof fn mfs_tmp_tmpmmnu354t_testes_anteriores_t2_ex5_2020_2"
            "__leq", out)
        self.assertIn("t_refutation_certificate", out)


class CommittedTasksUnaffectedTest(unittest.TestCase):
    """None of the 34 committed t/tasks/*.t has an empty-`state` loop (the
    new code path is only reachable when `state` is empty), so every one
    of them must relower byte-identical to before this change."""

    def test_committed_tasks_relower_unchanged(self):
        here = os.path.dirname(os.path.abspath(__file__))
        for path in sorted(glob.glob(os.path.join(here, "tasks", "*.t"))):
            task = tasks_io.load_task(path)
            # Just confirm it still lowers with no exception raised; the
            # regression bar itself (byte-for-byte AGREEMENT.md cells) is
            # covered separately by grade.py against t/AGREEMENT.md.
            lv.lower(task, task["body"])


if __name__ == "__main__":
    unittest.main()
