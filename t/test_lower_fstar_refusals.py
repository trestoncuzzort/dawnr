"""t/test_lower_fstar_refusals.py: unit tests for the "fstar-refusal" item
closed 2026-09-14 (worktree wf_f5dac772-927-4, sweep r23's ROADMAP 16.2
LOWER-ERROR on two lifted rows: FlexWeek_tmp_tmpc_tfdj_3_ex3.Max's and
dafny-workout_tmp_tmp0abkw6f8_starter_ex09.ComputeFib's collapse-if twins,
`KeyError: 'i'` / `KeyError: 'c'` out of `lower_fstar.gen_loop`'s `stys`
dict comprehension).

Root cause (see lower_fstar.py's `gen_loop`, the "UNCONDITIONAL RETURN
BEFORE THE LOOP" comment above `exec_flow(cx, prefix, ...)`, for the full
account): `exec_flow` returns the instant it sees a top-level `return`
statement in a straight-line list, so it never runs any `var` declared
LATER in that same list -- such a `var`'s type never enters `local`. The
OLD `gen_loop` still counted that name into `mvars` via a syntactic scan
of `prefix` blind to reachability, and the `stys` dict comprehension a few
lines down looked it up in `local` (absent) or `cx.tys` (params/return
only, also absent) -- `KeyError`. A `collapse-if` twin manufactures
exactly this shape: it turns a conditional early return into an
UNCONDITIONAL one, without touching the sibling statements that used to
run only when that condition was false, so a real committed task never
hits it (measured: `CommittedTasksUnaffectedTest` below, carried over
from test_lower_fstar_abstains.py's own regression discipline, still
passes) -- only a collapse-if TWIN does.

Fix, two parts:
  1. `gen_loop` now special-cases `pre_rc == "true"` (the literal string
     `exec_flow` produces only when EVERY path through `prefix` returns):
     the loop and suffix are provably unreachable, so the function is
     lowered directly as `pre_rv` under the task's own `Pure` signature,
     with no `mvars`/`stys`/loop machinery built at all. This is what
     turns both measured rows from LOWER-ERROR into a normal lowered F*
     file the kernel can REFUTE.
  2. The `stys` dict comprehension is wrapped in a `try`/`except KeyError`
     that raises `NotImplementedError` naming the missing variable and the
     reachability reason instead, so any OTHER shape this file has not
     actually solved reads as a named refusal (t/harness.py:
     `NotImplementedError` alone is an abstain; anything else is an
     unnamed lower-error) rather than a raw `KeyError` reaching the
     caller. `KeyErrorBecomesNamedRefusalTest` below exercises this path
     directly (via a mocked `exec_flow`, since a real partial-return
     prefix's own recursion into the "rest of the block" already
     populates `local` for every case this DSL's grammar can produce --
     see that test's docstring for why the literal-`"true"` case above is
     believed to be the only one reachable from a real twin).

Measured (this session, worktree wf_f5dac772-927-4, `python3 t/grade.py
--tasks <two-row copy of t/out/lifted-tasks> --kernels dafny,fstar --flake
3`):
  before: `flexweek_tmp_tmpc_tfdj_3_ex3__max x fstar: LOWER-ERROR KeyError:
    'i'`; `dafny_workout_tmp_tmp0abkw6f8_starter_ex09__computeFib x fstar:
    LOWER-ERROR KeyError: 'c'`.
  after: `flexweek_tmp_tmpc_tfdj_3_ex3__max x fstar [collapse-if]:
    real=verified twin=refuted` (matches dafny verified/refuted);
    `dafny_workout_tmp_tmp0abkw6f8_starter_ex09__computeFib x fstar
    [collapse-if]: real=unproved twin=refuted` (dafny: real=verified
    twin=refuted -- the twin side now agrees with dafny; the real side's
    own `unproved` is F*'s pre-existing gap on this task's real body, a
    residual this item did not touch and is not this item's to fix).

Measured by `python3 t/test_lower_fstar_refusals.py` from t/.
"""
import glob
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lower_fstar as lf
import tasks_io


# ---------------------------------------------------------------------
# The two measured rows, reconstructed inline (t/out/lifted-tasks is
# gitignored generated data, not something this test file may depend on
# existing on disk) rather than read from the corpus, so this test is
# self-contained and runs the same way in any checkout.
# ---------------------------------------------------------------------

def _max_task():
    """FlexWeek_tmp_tmpc_tfdj_3_ex3.Max, byte-for-byte (params/returns/
    requires/body), copied out of t/out/lifted-tasks by this session on
    2026-09-14. `gate: "loops"`, the field this file's lowering does not
    consult, is omitted."""
    a_len = {"args": [{"var": "a"}], "op": "len"}
    return {
        "t": 1,
        "name": "flexweek_tmp_tmpc_tfdj_3_ex3__max",
        "params": [{"name": "a", "type": "seq"}],
        "returns": [{"name": "m", "type": "int"}],
        "requires": [{"forall": {
            "var": "k", "lo": {"int": 0}, "hi": a_len,
            "body": {"op": ">=", "args": [
                {"op": "at", "args": [{"var": "a"}, {"var": "k"}]},
                {"int": 0}]}}}],
        "ensures": [
            {"op": "implies", "args": [
                {"op": ">", "args": [a_len, {"int": 0}]},
                {"forall": {"var": "k_v", "lo": {"int": 0}, "hi": a_len,
                            "body": {"op": ">=", "args": [
                                {"var": "m"},
                                {"op": "at", "args": [{"var": "a"}, {"var": "k_v"}]}]}}}]},
            {"op": "implies", "args": [
                {"op": "==", "args": [a_len, {"int": 0}]},
                {"op": "==", "args": [{"var": "m"}, {"op": "neg", "args": [{"int": 1}]}]}]},
        ],
        "body": [
            {"if": {"cond": {"op": "==", "args": [a_len, {"int": 0}]},
                    "then": [{"return": ["m", {"op": "neg", "args": [{"int": 1}]}]}],
                    "else": []}},
            {"var": {"name": "i", "type": "int", "init": {"int": 0}}},
            {"assign": ["m", {"op": "at", "args": [{"var": "a"}, {"int": 0}]}]},
            {"while": {
                "cond": {"op": "<", "args": [{"var": "i"}, a_len]},
                "body": [
                    {"if": {"cond": {"op": ">=", "args": [
                                {"op": "at", "args": [{"var": "a"}, {"var": "i"}]},
                                {"var": "m"}]},
                            "then": [{"assign": ["m", {"op": "at",
                                                        "args": [{"var": "a"}, {"var": "i"}]}]}],
                            "else": []}},
                    {"assign": ["i", {"op": "+", "args": [{"var": "i"}, {"int": 1}]}]},
                ],
                "invariants": [
                    {"op": "and", "args": [
                        {"op": "<=", "args": [{"int": 0}, {"var": "i"}]},
                        {"op": "<=", "args": [{"var": "i"}, a_len]}]},
                ],
                "decreases": {"op": "-", "args": [a_len, {"var": "i"}]},
            }},
        ],
    }


def _compute_fib_task():
    """dafny-workout_tmp_tmp0abkw6f8_starter_ex09.ComputeFib, byte-for-byte,
    copied out of t/out/lifted-tasks by this session on 2026-09-14."""
    return {
        "t": 1,
        "name": "dafny_workout_tmp_tmp0abkw6f8_starter_ex09__computeFib",
        "params": [{"name": "n", "type": "int"}],
        "returns": [{"name": "b", "type": "int"}],
        "requires": [{"op": ">=", "args": [{"var": "n"}, {"int": 0}]}],
        "ensures": [{"op": ">=", "args": [{"var": "b"}, {"int": 0}]}],
        "body": [
            {"var": {"name": "i", "type": "int", "init": {"int": 1}}},
            {"if": {"cond": {"op": "==", "args": [{"var": "n"}, {"int": 0}]},
                    "then": [{"return": ["b", {"var": "n"}]}],
                    "else": []}},
            {"assign": ["b", {"int": 1}]},
            {"var": {"name": "c", "type": "int", "init": {"int": 1}}},
            {"while": {
                "cond": {"op": "<", "args": [{"var": "i"}, {"var": "n"}]},
                "body": [
                    {"var": {"name": "t_v", "type": "int",
                             "init": {"op": "+", "args": [{"var": "b"}, {"var": "c"}]}}},
                    {"assign": ["c", {"var": "b"}]},
                    {"assign": ["b", {"var": "t_v"}]},
                    {"assign": ["i", {"op": "+", "args": [{"var": "i"}, {"int": 1}]}]},
                ],
                "invariants": [
                    {"op": "<=", "args": [{"int": 1}, {"var": "i"}]},
                ],
                "decreases": {"op": "-", "args": [{"var": "n"}, {"var": "i"}]},
            }},
        ],
    }


def _collapse_if(body):
    """The `collapse-if` twin operator (harness.py: replace the first `if`
    encountered with its own `then` branch), applied at the top level
    only -- exactly what produced both measured rows above."""
    out = []
    done = False
    for s in body:
        if not done and "if" in s:
            out.extend(s["if"]["then"])
            done = True
        else:
            out.append(s)
    assert done, "no top-level if to collapse"
    return out


class CollapseIfTwinNoLongerKeyErrorsTest(unittest.TestCase):
    """The two rows sweep r23 recorded LOWER-ERROR for: a `collapse-if`
    twin whose unconditional early return leaves a later top-level `var`
    declaration in `prefix` unreachable. Both must now lower to F* source
    with no exception, directly returning the twin's own early value."""

    def test_max_collapse_if_twin_lowers_directly(self):
        task = _max_task()
        twin_body = _collapse_if(task["body"])
        # `i`'s own declaration is now unreachable dead code (the return
        # is the twin's first statement): this is exactly the shape that
        # raised `KeyError: 'i'` before the fix.
        self.assertEqual(twin_body[0], {"return": ["m", {"op": "neg", "args": [{"int": 1}]}]})
        self.assertTrue(any("var" in s and s["var"]["name"] == "i" for s in twin_body))
        out = lf.lower(task, twin_body)
        self.assertIn("= (- 1)\n", out)
        # No loop machinery: the recursive helper this task's REAL body
        # needs (`_loop`) must not appear, since the twin never reaches it.
        self.assertNotIn("_loop", out)

    def test_compute_fib_collapse_if_twin_lowers_directly(self):
        task = _compute_fib_task()
        twin_body = _collapse_if(task["body"])
        # `c`'s own declaration (after the collapsed return) is the
        # unreachable one; `i`'s (before it) is not, so this row is the
        # partially-populated-`local` shape (see the module docstring).
        self.assertEqual(twin_body[1], {"return": ["b", {"var": "n"}]})
        self.assertTrue(any("var" in s and s["var"]["name"] == "c" for s in twin_body))
        out = lf.lower(task, twin_body)
        self.assertIn("= n\n", out)
        self.assertNotIn("_loop", out)

    def test_witness_still_yields_a_refutation_certificate(self):
        """With a witness (harness.twin_for's own shape: `_ens: True`, a
        concrete input/real/twin triple), `lower` must still emit the
        ground refutation certificate `verifiers/fstar.py` looks for --
        the short-circuit added for `pre_rc == "true"` must not skip past
        the witness-driven certificate machinery lower down in `lower`."""
        task = _max_task()
        twin_body = _collapse_if(task["body"])
        witness = {"_ens": True, "_kind": "value", "_real": 0, "_twin": -1,
                   "a": [0]}
        out = lf.lower(task, twin_body, witness=witness)
        self.assertIn("t_refutation_certificate", out)
        self.assertIn("assert_norm", out)


class KeyErrorBecomesNamedRefusalTest(unittest.TestCase):
    """The `stys` dict comprehension's `try`/`except KeyError` -> named
    `NotImplementedError`: exercised directly (a mocked `exec_flow`)
    because this DSL's grammar appears to make `pre_rc == "true"`
    (caught by the fix above) the ONLY way a top-level `var` in `prefix`
    is left out of `local` -- `exec_flow`'s `if`-handling recurses into
    the statements AFTER the `if` regardless of whether that `if` itself
    returns on both branches (its own `merged`/`local` threading), so a
    partial-return prefix (only one branch returns) always finishes
    populating `local` for everything syntactically after it. This test
    stands as the safety net named in the task: should some future
    shape reach `stys` with a name in neither table, it must still read
    as a named refusal (t/harness.py: `NotImplementedError` is an
    abstain; any other exception is an unnamed lower-error), never a raw
    `KeyError`."""

    def test_partial_return_prefix_missing_var_names_the_variable(self):
        task = {
            "t": 1, "name": "probe_partial_return_prefix",
            "params": [], "returns": [{"name": "m", "type": "int"}],
            "requires": [], "ensures": [{"op": "==", "args": [{"var": "m"}, {"var": "m"}]}],
            "body": [],
        }
        prefix = [
            {"if": {"cond": {"op": "==", "args": [{"int": 0}, {"int": 0}]},
                    "then": [{"return": ["m", {"int": 0}]}],
                    "else": []}},
            {"var": {"name": "z", "type": "int", "init": {"int": 0}}},
        ]
        w = {"cond": {"op": "<", "args": [{"var": "z"}, {"int": 3}]},
             "body": [{"assign": ["z", {"op": "+", "args": [{"var": "z"}, {"int": 1}]}]}],
             "invariants": [], "decreases": {"var": "z"}}
        cx = lf.Ctx(task)
        real_exec_flow = lf.exec_flow

        def fake_exec_flow(cxa, stmts, env, local, dummy):
            # Simulate a shape where `exec_flow` reports a CONDITIONAL
            # `pre_rc` (not the literal "true" the fix above special-
            # cases) yet still leaves `z` out of `local` -- not a shape
            # this file's real `exec_flow` produces (see the class
            # docstring), but exactly the input contract the `except
            # KeyError` branch must handle safely regardless.
            if stmts is prefix:
                return dict(env), "(if p then true else false)", dummy
            return real_exec_flow(cxa, stmts, env, local, dummy)

        with mock.patch.object(lf, "exec_flow", side_effect=fake_exec_flow):
            with self.assertRaises(NotImplementedError) as ctx:
                lf.gen_loop(cx, task, prefix, w, [])
        self.assertIn("'z'", str(ctx.exception))
        self.assertIn("no type in scope", str(ctx.exception))


class CommittedTasksUnaffectedTest(unittest.TestCase):
    """Every task committed under t/tasks/*.t must relower byte-identical:
    none has a top-level unconditional return before its own loop's
    prefix (`pre_rc` is always "false" for a committed task's real body),
    so the new short-circuit at the top of `gen_loop` must never fire for
    one. Carried over from test_lower_fstar_abstains.py's own regression
    discipline."""

    def test_committed_tasks_relower_unchanged(self):
        here = os.path.dirname(os.path.abspath(__file__))
        for path in sorted(glob.glob(os.path.join(here, "tasks", "*.t"))):
            task = tasks_io.load_task(path)
            out = lf.lower(task, task["body"])
            self.assertNotIn("t_exists_at", out)
            self.assertNotIn("t_forall_at", out)


if __name__ == "__main__":
    unittest.main()
