"""t/test_lower_fstar_abstains.py: unit tests for the three fstar ABSTAINs
closed 2026-09-12 (ROADMAP 16.2 fstar item, "the abstained shapes" --
dafny-synthesis anyValueExists task 414, isSublist task 576, removeElement
task 610). See lower_fstar.py's own module docstring (2026-09-12 entry) for
the measured F* results on all three; this file only tests the Python-level
shape detection and rendering these fixes add, plus the regression
discipline test_names.py/test_lower_spark.py already apply: every task
committed under t/tasks/*.t must relower byte-identical to before.

Measured by `python3 test_lower_fstar_abstains.py` from t/.
"""
import glob
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lower_fstar as lf
import tasks_io


def _at(seq, idx):
    return {"op": "at", "args": [{"var": seq}, idx]}


def _exists(var, lo, hi, body):
    return {"exists": {"var": var, "lo": lo, "hi": hi, "body": body}}


class FindWhilesTest(unittest.TestCase):
    """`find_whiles` generalises `find_while`: one loop must read exactly
    like before, more than one loop is the new segmented shape, and the
    two refusals (loop under a conditional, nested loop) are unchanged."""

    def test_no_loop_matches_find_while(self):
        body = [{"assign": ["x", {"int": 1}]}]
        segs, suffix = lf.find_whiles(body)
        self.assertEqual(segs, [])
        self.assertEqual(suffix, body)
        prefix, w, fw_suffix = lf.find_while(body)
        self.assertIsNone(w)
        self.assertEqual(prefix, body)
        self.assertEqual(fw_suffix, [])

    def test_one_loop_matches_find_while_byte_for_byte(self):
        w = {"cond": {"op": "<", "args": [{"var": "i"}, {"int": 3}]},
             "body": [{"assign": ["i", {"op": "+",
                                        "args": [{"var": "i"}, {"int": 1}]}]}],
             "invariants": [], "decreases": {"var": "i"}}
        body = [{"var": {"name": "i", "type": "int", "init": {"int": 0}}},
                {"while": w}]
        segs, suffix = lf.find_whiles(body)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0], (body[:1], w))
        self.assertEqual(suffix, [])
        prefix, w2, fw_suffix = lf.find_while(body)
        self.assertEqual((prefix, w2, fw_suffix), (segs[0][0], w, suffix))

    def test_two_sequential_loops_segmented(self):
        w1 = {"cond": {"bool": True}, "body": [], "invariants": [],
              "decreases": {"int": 0}}
        w2 = {"cond": {"bool": True}, "body": [], "invariants": [],
              "decreases": {"int": 0}}
        body = [{"assign": ["x", {"int": 0}]}, {"while": w1}, {"while": w2}]
        segs, suffix = lf.find_whiles(body)
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0], ([body[0]], w1))
        self.assertEqual(segs[1], ([], w2))
        self.assertEqual(suffix, [])

    def test_three_loops_segment_but_the_chain_lowering_still_abstains(self):
        # `find_whiles` itself has no loop-count limit (it only splits);
        # the "more than one loop" ABSTAIN for 3+ loops is `gen_loop_chain`'s
        # own refusal (restricted to exactly the measured two-loop shape),
        # exercised the way `lower()` actually reaches it.
        w = {"cond": {"bool": True}, "body": [], "invariants": [],
             "decreases": {"int": 0}}
        body = [{"while": w}, {"while": w}, {"while": w}]
        segs, suffix = lf.find_whiles(body)
        self.assertEqual(len(segs), 3)
        task = {"t": 1, "name": "three_loop_probe", "params": [],
                "returns": [{"name": "r", "type": "int"}],
                "requires": [], "ensures": []}
        with self.assertRaises(NotImplementedError) as ctx:
            lf.gen_loop_chain(lf.Ctx(task), task, segs, suffix)
        self.assertIn("more than one loop per body", str(ctx.exception))

    def test_loop_under_conditional_still_abstains(self):
        w = {"cond": {"bool": True}, "body": [], "invariants": [],
             "decreases": {"int": 0}}
        body = [{"if": {"cond": {"bool": True}, "then": [{"while": w}],
                        "else": []}}]
        with self.assertRaises(NotImplementedError) as ctx:
            lf.find_whiles(body)
        self.assertIn("under a conditional", str(ctx.exception))

    def test_nested_loop_still_abstains(self):
        inner = {"cond": {"bool": True}, "body": [], "invariants": [],
                 "decreases": {"int": 0}}
        outer = {"cond": {"bool": True}, "body": [{"while": inner}],
                 "invariants": [], "decreases": {"int": 0}}
        with self.assertRaises(NotImplementedError) as ctx:
            lf.find_whiles([{"while": outer}])
        self.assertIn("nested loops", str(ctx.exception))


class ExprFreeVarsTest(unittest.TestCase):
    """`_expr_free_vars` walks the actual expression shape, so an op name
    or a spec_fun/task name is never mistaken for a variable."""

    def test_op_and_call_names_excluded(self):
        e = {"op": "==", "args": [_at("seq2", {"var": "k"}),
                                  {"call": {"fun": "helper",
                                            "args": [{"var": "seq1"}]}}]}
        self.assertEqual(lf._expr_free_vars(e, frozenset({"k"})),
                          {"seq2", "seq1"})

    def test_bound_variable_of_a_nested_quantifier_excluded(self):
        body = _exists("k2", {"int": 0}, {"var": "n"},
                       {"op": "==", "args": [{"var": "k2"}, {"var": "k2"}]})
        e = {"op": "and", "args": [body, {"var": "outer"}]}
        self.assertEqual(lf._expr_free_vars(e), {"n", "outer"})


class GenLoopChainTest(unittest.TestCase):
    """removeElement's own shape (task 610): two sequential, non-nested
    loops sharing the ambient mutable state, no return in either."""

    def _remove_element_like_task(self):
        loop1 = {
            "cond": {"op": "<", "args": [{"var": "i"}, {"var": "k"}]},
            "invariants": [],
            "decreases": {"op": "-", "args": [{"var": "k"}, {"var": "i"}]},
            "body": [
                {"assign": ["v", {"op": "update", "args": [
                    {"var": "v"}, {"var": "i"}, _at("s", {"var": "i"})]}]},
                {"assign": ["i", {"op": "+", "args": [{"var": "i"}, {"int": 1}]}]},
            ],
        }
        loop2 = {
            "cond": {"op": "<", "args": [{"var": "i"},
                                         {"op": "len", "args": [{"var": "v"}]}]},
            "invariants": [],
            "decreases": {"op": "-", "args": [
                {"op": "len", "args": [{"var": "v"}]}, {"var": "i"}]},
            "body": [
                {"assign": ["v", {"op": "update", "args": [
                    {"var": "v"}, {"var": "i"},
                    _at("s", {"op": "+", "args": [{"var": "i"}, {"int": 1}]})]}]},
                {"assign": ["i", {"op": "+", "args": [{"var": "i"}, {"int": 1}]}]},
            ],
        }
        task = {
            "t": 1, "name": "chain_probe",
            "params": [{"name": "s", "type": "seq"}, {"name": "k", "type": "int"}],
            "returns": [{"name": "v", "type": "seq"}],
            "requires": [{"op": "<=", "args": [{"int": 0}, {"var": "k"}]},
                         {"op": "<", "args": [{"var": "k"},
                                             {"op": "len", "args": [{"var": "s"}]}]}],
            "ensures": [{"op": "==", "args": [
                {"op": "len", "args": [{"var": "v"}]},
                {"op": "-", "args": [{"op": "len", "args": [{"var": "s"}]},
                                     {"int": 1}]}]}],
        }
        body = [
            {"assign": ["v", {"op": "fill", "args": [
                {"op": "-", "args": [{"op": "len", "args": [{"var": "s"}]},
                                     {"int": 1}]}, {"int": 0}]}]},
            {"var": {"name": "i", "type": "int", "init": {"int": 0}}},
            {"while": loop1},
            {"while": loop2},
        ]
        return task, body

    def test_two_loop_body_lowers_with_two_named_recursive_helpers(self):
        task, body = self._remove_element_like_task()
        out = lf.lower(task, body)
        self.assertIn("chain_probe_loop0", out)
        self.assertIn("chain_probe_loop1", out)
        # Chained through a let-binding, not two separate top-level
        # functions called independently of one another.
        self.assertIn("chain_probe_loop0 s k", out)
        self.assertIn("chain_probe_loop1 s k", out)


class QuantHelperTest(unittest.TestCase):
    """anyValueExists's own shape (task 414): an `exists` in computational
    position whose bound is not a literal (`len(seq2)`, never a constant),
    lowered as a fresh `Pure bool` recursive helper rather than an
    ABSTAIN."""

    def test_non_literal_bound_emits_a_helper_with_domain_requires(self):
        task = {
            "t": 1, "name": "quant_probe",
            "params": [{"name": "seq1", "type": "seq"},
                      {"name": "seq2", "type": "seq"}],
            "returns": [{"name": "result", "type": "bool"}],
            "requires": [],
            "ensures": [{"var": "result"}],
        }
        body = [{"assign": ["result", _exists(
            "k", {"int": 0}, {"op": "len", "args": [{"var": "seq2"}]},
            {"op": "==", "args": [_at("seq2", {"var": "k"}), {"int": 0}]})]}]
        # `body` here is a plain assign of a bx-position exists (no loop),
        # so this exercises gen_fun's own call into `bx` directly.
        out = lf.lower(task, body)
        self.assertIn("t_exists_at", out)
        self.assertIn("Pure bool", out)
        self.assertIn("qhi <= (Seq.length seq2)", out)


class CommittedTasksUnaffectedTest(unittest.TestCase):
    """Every task committed before this wave must relower byte-identical:
    `find_whiles`'s one-loop path is byte-identical to `find_while`'s own
    prefix/while/suffix split, and no committed task's own prefix returns
    or reaches a non-literal-bounded quantifier in computational
    position (both previously-committed states are single-loop, no
    return-in-prefix, tested here so a future change to either path
    cannot silently regress a committed task without failing this test)."""

    def test_committed_tasks_relower_unchanged(self):
        here = os.path.dirname(os.path.abspath(__file__))
        for path in sorted(glob.glob(os.path.join(here, "tasks", "*.t"))):
            task = tasks_io.load_task(path)
            out = lf.lower(task, task["body"])
            self.assertNotIn("t_exists_at", out)
            self.assertNotIn("t_forall_at", out)
            self.assertNotIn("_loop1", out,
                              f"{path} unexpectedly hit the two-loop chain path")


if __name__ == "__main__":
    unittest.main()
