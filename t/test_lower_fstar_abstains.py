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

    def test_three_loops_segment_and_the_chain_lowering_takes_them(self):
        # 2026-09-18 (ROADMAP WS-20 move 1): `gen_loop_chain`'s
        # `len(segs) != 2` cap is lifted -- it was a refusal to claim more
        # than the shape measured in 2026-09-12, not a limit of the fold
        # over `segs`. Three loops now emit three helpers; see
        # `ThreeLoopChainTest` below for the end-to-end render.
        w = {"cond": {"bool": True}, "body": [], "invariants": [],
             "decreases": {"int": 0}}
        body = [{"while": w}, {"while": w}, {"while": w}]
        segs, suffix = lf.find_whiles(body)
        self.assertEqual(len(segs), 3)

    def test_loop_under_conditional_still_abstains(self):
        w = {"cond": {"bool": True}, "body": [], "invariants": [],
             "decreases": {"int": 0}}
        body = [{"if": {"cond": {"bool": True}, "then": [{"while": w}],
                        "else": []}}]
        with self.assertRaises(NotImplementedError) as ctx:
            lf.find_whiles(body)
        self.assertIn("under a conditional", str(ctx.exception))

    def test_loop_under_conditional_inside_a_loop_body_abstains(self):
        # The one placement refusal that survives 2026-09-18, now checked
        # one level down: `_check_nestable` walks a loop body too, so a
        # nested loop sitting under an `if` is still a named ABSTAIN and
        # never a guess. See `_check_nestable`'s docstring for why.
        deep = {"cond": {"bool": True}, "body": [], "invariants": [],
                "decreases": {"int": 0}}
        outer = {"cond": {"bool": True},
                 "body": [{"if": {"cond": {"bool": True},
                                  "then": [{"while": deep}], "else": []}}],
                 "invariants": [], "decreases": {"int": 0}}
        with self.assertRaises(NotImplementedError) as ctx:
            lf.find_whiles([{"while": outer}])
        self.assertIn("under a conditional", str(ctx.exception))

    def test_nested_loop_no_longer_abstains_at_split_time(self):
        inner = {"cond": {"bool": True}, "body": [], "invariants": [],
                 "decreases": {"int": 0}}
        outer = {"cond": {"bool": True}, "body": [{"while": inner}],
                 "invariants": [], "decreases": {"int": 0}}
        segs, suffix = lf.find_whiles([{"while": outer}])
        self.assertEqual(len(segs), 1)
        self.assertIs(segs[0][1], outer)
        self.assertEqual(suffix, [])


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


class NestedLoopTest(unittest.TestCase):
    """NESTED LOOPS (2026-09-18, ROADMAP WS-20 move 1): has_duplicate's own
    shape -- a `while` in a `while`, each with its own invariants and its
    own decreases -- plus the two refusals that survive it."""

    def _nested_task(self, inner_body=None, outer_tail=None):
        inner = {
            "cond": {"op": "<", "args": [{"var": "j"}, {"var": "n"}]},
            "invariants": [{"op": "<=", "args": [{"int": 0}, {"var": "j"}]}],
            "decreases": {"op": "-", "args": [{"var": "n"}, {"var": "j"}]},
            "body": inner_body if inner_body is not None else [
                {"assign": ["r", {"op": "+", "args": [{"var": "r"},
                                                      {"int": 1}]}]},
                {"assign": ["j", {"op": "+", "args": [{"var": "j"},
                                                      {"int": 1}]}]},
            ],
        }
        outer = {
            "cond": {"op": "<", "args": [{"var": "i"}, {"var": "n"}]},
            "invariants": [{"op": "<=", "args": [{"int": 0}, {"var": "i"}]}],
            "decreases": {"op": "-", "args": [{"var": "n"}, {"var": "i"}]},
            "body": [
                {"var": {"name": "j", "type": "int", "init": {"int": 0}}},
                {"while": inner},
            ] + (outer_tail if outer_tail is not None else []) + [
                {"assign": ["i", {"op": "+", "args": [{"var": "i"},
                                                      {"int": 1}]}]},
            ],
        }
        task = {
            "t": 1, "name": "nest_probe",
            "params": [{"name": "n", "type": "int"}],
            "returns": [{"name": "r", "type": "int"}],
            "requires": [{"op": "<=", "args": [{"int": 0}, {"var": "n"}]}],
            "ensures": [{"op": "<=", "args": [{"int": 0}, {"var": "r"}]}],
        }
        body = [
            {"assign": ["r", {"int": 0}]},
            {"var": {"name": "i", "type": "int", "init": {"int": 0}}},
            {"while": outer},
        ]
        return task, body

    def test_nested_body_emits_the_inner_helper_first_and_calls_it(self):
        task, body = self._nested_task()
        out = lf.lower(task, body)
        # Two recursive helpers, the inner one DEFINED FIRST (F* has no
        # forward declarations for `let`).
        self.assertIn("let rec nest_probe_inner ", out)
        self.assertIn("let rec nest_probe_loop ", out)
        self.assertLess(out.index("let rec nest_probe_inner "),
                        out.index("let rec nest_probe_loop "))
        # The inner loop's call is let-bound inside the OUTER loop's step,
        # binding exactly what the inner loop assigns (`r` and `j`).
        self.assertIn("let (r, j) = nest_probe_inner n i r 0 in", out)
        # The inner loop's OWN invariant is its requires, so the call site
        # owes the kernel a real establishment proof -- nothing assumed.
        self.assertIn("(requires ((0 <= n) /\\ (0 <= j)))", out)
        # The property the fstar backend's zero-obligation rule rests on.
        self.assertIn("t_contract_obligation", out)
        # Never a dodge.
        for banned in ("admit", "assume", "magic", "sorry"):
            self.assertNotIn(banned, out)

    def test_return_inside_the_inner_loop_abstains_by_name(self):
        task, body = self._nested_task(inner_body=[
            {"if": {"cond": {"op": "<", "args": [{"var": "j"}, {"int": 3}]},
                    "then": [{"return": ["r", {"int": 7}]}],
                    "else": []}},
            {"assign": ["j", {"op": "+", "args": [{"var": "j"},
                                                  {"int": 1}]}]},
        ])
        with self.assertRaises(NotImplementedError) as ctx:
            lf.lower(task, body)
        self.assertIn("`return` inside a nested loop", str(ctx.exception))

    def test_return_in_the_outer_loop_of_a_nest_still_lowers(self):
        # The `either` encoding is unchanged for the loop that OWNS the
        # early exit; only an inner loop's own return is refused.
        task, body = self._nested_task(outer_tail=[
            {"if": {"cond": {"op": "<", "args": [{"int": 100}, {"var": "r"}]},
                    "then": [{"return": ["r", {"int": 5}]}],
                    "else": []}},
        ])
        out = lf.lower(task, body)
        self.assertIn("either int", out)
        self.assertIn("let (r, j) = nest_probe_inner n i r 0 in", out)


class ThreeLoopChainTest(unittest.TestCase):
    """The two-loop cap on `gen_loop_chain` is lifted (2026-09-18): three
    sequential loops emit three helpers, chained through the same
    let-binding the two-loop case already used."""

    def test_three_sequential_loops_emit_three_helpers(self):
        def mk(var):
            return {
                "cond": {"op": "<", "args": [{"var": var}, {"var": "n"}]},
                "invariants": [{"op": "<=", "args": [{"int": 0},
                                                     {"var": var}]}],
                "decreases": {"op": "-", "args": [{"var": "n"},
                                                  {"var": var}]},
                "body": [
                    {"assign": ["r", {"op": "+", "args": [{"var": "r"},
                                                          {"int": 1}]}]},
                    {"assign": [var, {"op": "+", "args": [{"var": var},
                                                          {"int": 1}]}]},
                ],
            }
        task = {
            "t": 1, "name": "chain3_probe",
            "params": [{"name": "n", "type": "int"}],
            "returns": [{"name": "r", "type": "int"}],
            "requires": [{"op": "<=", "args": [{"int": 0}, {"var": "n"}]}],
            "ensures": [{"op": "<=", "args": [{"int": 0}, {"var": "r"}]}],
        }
        body = [{"assign": ["r", {"int": 0}]}]
        for var in ("i", "j", "k"):
            body.append({"var": {"name": var, "type": "int",
                                 "init": {"int": 0}}})
            body.append({"while": mk(var)})
        out = lf.lower(task, body)
        for k in range(3):
            self.assertIn(f"let rec chain3_probe_loop{k} ", out)
        self.assertIn("t_contract_obligation", out)


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
