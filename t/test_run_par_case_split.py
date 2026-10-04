#!/usr/bin/env python3
"""t/test_run_par_case_split.py -- the case split (2026-10-04): a loop inside a
branch, which lean, rocq and fstar abstain on, graded through Dijkstra's rule
for the conditional (wp(if E then S1 else S2, R) = (E => wp(S1, R)) and
(not E => wp(S2, R)), en.wikipedia.org/wiki/Predicate_transformer_semantics,
research receipt bf9e04160124) as two tasks with the loop at top level.

What is pinned here, with no kernel run:
  * which conditions qualify: parameters only (a parameter is never assigned,
    check_wf Gate 2), and nothing that can be undefined or call anything;
  * the two halves: requires + [E] / requires + [not E], the arm in place of
    the `if`, the statements after it dropped only where the arm always
    returns (a `return` is the last statement of its block, SPEC.md);
  * a witness goes to the half whose guard holds at it, and a witness the
    guard cannot be read at keeps the abstention;
  * how two halves' outcomes combine, and that an unsplit side run in both
    units must agree with itself;
  * on a guarded copy of the committed is_prime, the three kernels' own
    lowerings abstain on the whole body and lower both halves, and dafny
    still lowers the whole body (the split is never asked of it).

Standard library only. unittest.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_par                                                # noqa: E402
import surface                                                # noqa: E402
from verifiers import Outcome                                 # noqa: E402

V, R, U, T = Outcome.VERIFIED, Outcome.REFUTED, Outcome.UNPROVED, Outcome.TIMEOUT

# t/tasks/is_prime.t with its `requires n >= 2` moved into a guard: the shape
# the student writes (the edge case first, the loop in the `else`).
GUARDED = """t 1
gate loops
task is_prime_guarded(n: int) returns (r: bool)
  ensures r == (n >= 2 and (forall d in [2, n) . n % d != 0))
{
  if n < 2 {
    r := false;
  } else {
    var d: int := 2;
    while d < n
      invariant d >= 2 and d <= n
      invariant forall k in [2, d) . n % k != 0
      decreases n - d
    {
      if n % d == 0 {
        return false;
      } else {
      }
      d := d + 1;
    }
    r := true;
  }
}
"""


def e(src: str) -> dict:
    return surface.parse_expr(src)


def guarded() -> dict:
    return surface.parse(GUARDED)


class Conditions(unittest.TestCase):
    P = {"n", "m", "s"}

    def test_total_over_parameters(self):
        for src in ("n < 2", "len(s) == 0 or len(s) == 1", "not (n >= 3)",
                    "n + 1 > 2 * m", "n - m <= 0 ==> len(s) > 0", "true", "-n < 0"):
            self.assertTrue(run_par._total_over(e(src), self.P), src)

    def test_undefined_or_foreign_refused(self):
        for src in ("s[0] == 1", "n / 2 > 1", "n % 2 == 0", "i < 2",
                    "forall k in [0, n) . k >= 0", "len(s[1..]) > 0"):
            self.assertFalse(run_par._total_over(e(src), self.P), src)


class Halves(unittest.TestCase):
    def test_always_returns(self):
        ret = {"return": ["r", {"bool": True}]}
        asg = {"assign": ["r", {"bool": True}]}
        both = {"if": {"cond": {"bool": True}, "then": [ret], "else": [ret]}}
        one = {"if": {"cond": {"bool": True}, "then": [ret], "else": [asg]}}
        self.assertTrue(run_par._always_returns([asg, ret]))
        self.assertTrue(run_par._always_returns([asg, both]))
        self.assertFalse(run_par._always_returns([one]))
        self.assertFalse(run_par._always_returns([asg]))
        self.assertFalse(run_par._always_returns([]))

    def test_split_of_the_guarded_task(self):
        task = guarded()
        cond, halves = run_par.case_split(task, task["body"])
        self.assertEqual(cond, e("n < 2"))
        (t1, b1), (t2, b2) = halves
        self.assertEqual(t1["requires"], [e("n < 2")])
        self.assertEqual(t2["requires"], [{"op": "not", "args": [e("n < 2")]}])
        self.assertEqual(b1, task["body"][0]["if"]["then"])
        self.assertEqual(b2, task["body"][0]["if"]["else"])
        self.assertEqual(t1["body"], b1)
        for t in (t1, t2):
            self.assertEqual(t["ensures"], task["ensures"])
            self.assertEqual(t["name"], task["name"])
        self.assertEqual(task["requires"], [], "the original task is not changed")

    def test_prefix_and_suffix_are_kept_unless_the_arm_returns(self):
        task = guarded()
        loop_if = task["body"][0]
        pre = {"assign": ["r", {"bool": False}]}
        post = {"assign": ["r", {"var": "r"}]}
        returning = {"if": dict(loop_if["if"], then=[{"return": ["r", {"bool": False}]}])}
        cond, ((_t1, b1), (_t2, b2)) = run_par.case_split(task, [pre, returning, post])
        self.assertEqual(b1, [pre, {"return": ["r", {"bool": False}]}])
        self.assertEqual(b2, [pre] + loop_if["if"]["else"] + [post])

    def test_no_split(self):
        task = guarded()
        body = task["body"]
        local = {"if": dict(body[0]["if"], cond=e("d < 2"))}
        partial = {"if": dict(body[0]["if"], cond=e("n % 2 == 0"))}
        no_loop = {"if": dict(body[0]["if"], **{"else": [{"assign": ["r", {"bool": True}]}]})}
        self.assertIsNone(run_par.case_split(task, [local]))
        self.assertIsNone(run_par.case_split(task, [partial]))
        self.assertIsNone(run_par.case_split(task, [no_loop]))
        recursive = dict(task, name="is_prime_guarded")
        call = {"assign": ["r", {"call": {"fun": "is_prime_guarded", "args": [{"var": "n"}]}}]}
        selfcall = {"if": dict(body[0]["if"], then=[call])}
        self.assertIsNone(run_par.case_split(recursive, [selfcall]))


class Witnesses(unittest.TestCase):
    def test_guard_at(self):
        task = guarded()
        self.assertTrue(run_par._guard_at(e("n < 2"), {"n": 1, "_kind": "value"}, task))
        self.assertFalse(run_par._guard_at(e("n < 2"), {"n": 2, "d": 2, "_kind": "exit"}, task))
        self.assertIsNone(run_par._guard_at(e("n < 2"), {"m": 2}, task))
        seq_task = dict(task, params=[{"name": "s", "type": "seq"}])
        c = e("len(s) == 0 or len(s) == 1")
        self.assertFalse(run_par._guard_at(c, {"s": [0, 1]}, seq_task))
        self.assertTrue(run_par._guard_at(c, {"s": [7]}, seq_task))

    def test_lower_side_routes_the_witness(self):
        task = guarded()
        seen = []

        def fake(t, body, witness=None):
            if any("if" in s and run_par._has_while(s["if"]["then"] + s["if"]["else"]) for s in body):
                raise NotImplementedError("a loop inside a branch is not lowered for lean")
            seen.append((t["requires"], witness))
            return f"src{len(seen)}"
        srcs, cond = run_par._lower_side(task, task["body"], {"n": 7, "_kind": "value"}, fake)
        self.assertEqual(srcs, ["src1", "src2"])
        self.assertEqual(cond, e("n < 2"))
        self.assertIsNone(seen[0][1], "n = 7 is not in the n < 2 half")
        self.assertEqual(seen[1][1], {"n": 7, "_kind": "value"})

    def test_lower_side_keeps_other_abstentions_and_unroutable_witnesses(self):
        task = guarded()

        def other(t, body, witness=None):
            raise NotImplementedError("nested / multiple loops are not lowered for lean")
        with self.assertRaises(NotImplementedError):
            run_par._lower_side(task, task["body"], None, other)

        def loop(t, body, witness=None):
            if t["requires"] == []:
                raise NotImplementedError("rocq lowering: a loop under a conditional is not lowered yet")
            return "x"
        with self.assertRaises(NotImplementedError):
            run_par._lower_side(task, task["body"], {"m": 1}, loop)   # no `n`: cannot route
        self.assertEqual(run_par._lower_side(task, task["body"], None, loop)[0], ["x", "x"])


class Combine(unittest.TestCase):
    REAL = {"real": True, "twin": False}

    def test_split_real(self):
        self.assertEqual(run_par.combine_units((V, R, True), (V, R, True), self.REAL), (V, R, True))
        self.assertEqual(run_par.combine_units((V, R, True), (U, R, True), self.REAL), (U, R, True))
        self.assertEqual(run_par.combine_units((R, R, True), (V, R, True), self.REAL), (R, R, True))
        self.assertEqual(run_par.combine_units((T, R, True), (U, R, True), self.REAL), (T, R, True))

    def test_unsplit_side_must_agree_with_itself(self):
        self.assertEqual(run_par.combine_units((V, R, True), (V, T, True), self.REAL), (V, R, False))
        self.assertEqual(run_par.combine_units((V, R, False), (V, R, True), self.REAL), (V, R, False))

    def test_split_twin(self):
        both = {"real": True, "twin": True}
        self.assertEqual(run_par.combine_units((V, R, True), (V, V, True), both), (V, R, True))
        self.assertEqual(run_par.combine_units((V, V, True), (V, V, True), both), (V, V, True))


class OnTheKernelsOwnLowerings(unittest.TestCase):
    def test_three_abstain_whole_and_lower_halves(self):
        import lower_fstar
        import lower_lean
        import lower_rocq
        task = guarded()
        for mod in (lower_lean, lower_rocq, lower_fstar):
            with self.assertRaises(NotImplementedError) as cm:
                mod.lower(task, task["body"])
            self.assertRegex(str(cm.exception), run_par.SPLIT_REASON, mod.__name__)
            srcs, cond = run_par._lower_side(task, task["body"], None, mod.lower)
            self.assertEqual(len(srcs), 2, mod.__name__)
            self.assertTrue(all(isinstance(s, str) and s for s in srcs), mod.__name__)

    def test_dafny_lowers_the_whole_body(self):
        import lower_dafny
        task = guarded()
        srcs, cond = run_par._lower_side(task, task["body"], None, lower_dafny.lower)
        self.assertEqual(len(srcs), 1)
        self.assertIsNone(cond)


if __name__ == "__main__":
    unittest.main()
