"""t/test_lower_spark_loop_cert.py: unit tests for the value-witness
certificate through loop bodies (spark, key spark-cert, 2026-09-14).

MEASURED gap this file pins (this session, gnatprove FSF 16.1.0): a
"value" witness for a task whose body has exactly one while loop used to
build its certificate as `not ensures(F(args))`, calling the file's OWN
F. gnatprove reasons about F(args) by TRUSTING F's loop helper W_k's
declared Pre/Post, never by unfolding the recursion -- so a twin whose
mutation genuinely breaks the stated invariant (all_nonneg_twin.ads's
own drop-guard rung) leaves W_k's OWN recursive-call precondition
unprovable ("medium: precondition might fail, cannot prove (R = (for
all J ...))", gnatprove's own text, MEASURED on this file's unmodified
all_nonneg_twin.ads before this session's fix), and Big_Integer's own
opacity to gnatprove's counterexample engine (verifiers/spark.py's own
header) means that obligation can never escalate to a refutation
either -- the cell read verified/unproved, never verified/refuted,
whatever the step budget.

The fix (lower_while's own dated note, and certificate()'s "value" kind,
both 2026-09-14): every loop lowered also gets an UNCONTRACTED clone,
`Lower.loop_certs[name]` (a `W_k_Cert` with the SAME record and
recursive body as `W_k`, stripped of Pre/Post, owing only a
Subprogram_Variant), and, when a "value" witness's task has exactly one
loop and the task needed no rename, the certificate calls a clone of F
itself (`F_Cert`, F's own already-rendered body with `W_k` renamed to
`W_k_Cert`) instead of F -- so gnatprove computes the twin's actual
value by ordinary defining-axiom unfolding at the witness's ground
literal arguments, never by trusting the twin's own (possibly
unprovable) loop contract.

No kernel binary is invoked here (that measurement -- the seven
committed rows moving unproved/timeout -> refuted, real unchanged, at
flake 3 -- is done separately with `python3 grade.py --tasks t/tasks
--kernels spark,dafny --flake 3`, and is reported in this session's own
patch/report, not restated here since a re-run can drift under
contention); this file checks only the Python-level shape: the emitted
source actually contains the uncontracted clone and calls it from the
certificate, the clone carries no Pre/Post, and a task the new path
does not apply to (no loop, or more than one) is byte-for-byte
unaffected.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness      # noqa: E402
import lower_spark  # noqa: E402
import tasks_io     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name: str) -> dict:
    return tasks_io.load_task(os.path.join(HERE, "tasks", f"{name}.t"))


class TestLoopCertEmission(unittest.TestCase):
    """all_nonneg.t: one while loop, F's whole body is the loop call --
    the exact shape MEASURED unproved before this session's fix."""

    def setUp(self):
        self.task = _load("all_nonneg")
        self.body, self.op, self.w = harness.twin_cached(self.task)
        self.assertIsNotNone(self.body, "all_nonneg twin_cached refused")
        self.assertEqual(self.w.get("_kind"), "value")

    def test_twin_emits_uncontracted_loop_clone(self):
        src = lower_spark.lower(self.task, self.body, witness=self.w)
        self.assertIn("function W_1_Cert", src)
        self.assertIn("type W_1_State_Cert is record", src)
        # The clone owes only termination: no Pre, no Post, never a bare
        # `True` standing in for one either.
        clone_decl = src[src.index("function W_1_Cert"):
                        src.index("function F_Cert")]
        self.assertNotIn("Pre ", clone_decl)
        self.assertNotIn("Post =>", clone_decl)
        self.assertIn("Subprogram_Variant", clone_decl)

    def test_twin_certificate_calls_f_cert_not_f(self):
        src = lower_spark.lower(self.task, self.body, witness=self.w)
        self.assertIn("function F_Cert", src)
        cert = src[src.index("T_Refutation_Certificate return Boolean is"):]
        self.assertIn("F_Cert (", cert)
        self.assertNotIn("(not (F (", cert)

    def test_f_cert_body_mirrors_f_with_renamed_loop_call(self):
        src = lower_spark.lower(self.task, self.body, witness=self.w)
        f_body = src[src.index("function F (S : Seq) return Boolean is"):
                    src.index("type W_1_State_Cert")]
        f_cert_body = src[src.index("function F_Cert"):]
        self.assertIn("W_1 (S, True, Big_Integer'(0)).R", f_body)
        self.assertIn("W_1_Cert (S, True, Big_Integer'(0)).R", f_cert_body)

    def test_real_lowering_unaffected(self):
        # The real (non-twin) lowering never sees a witness and must stay
        # byte-for-byte what it was: no clone, no F_Cert, one W_1.
        src = lower_spark.lower(self.task, self.task["body"])
        self.assertNotIn("F_Cert", src)
        self.assertNotIn("_State_Cert", src)
        self.assertEqual(src.count("function W_1 "), 2)  # spec + body

    def test_real_row_still_verified(self):
        # Python-level guard only: the real lowering must still declare
        # exactly the same Post/Pre pair on F it always did (unaffected
        # by loop_certs), so nothing about the REAL column's own proof
        # obligations changed shape.
        src = lower_spark.lower(self.task, self.task["body"])
        self.assertIn("Post => (F'Result = (for all I in", src)


class TestLoopCertFallback(unittest.TestCase):
    """Tasks the new path must NOT touch: no loop, or more than one."""

    def test_no_loop_task_unaffected(self):
        task = {
            "t": 1, "name": "abs_t", "params": [{"name": "x", "type": "int"}],
            "returns": [{"name": "r", "type": "int"}],
            "requires": [], "ensures": [
                {"op": ">=", "args": [{"var": "r"}, {"int": 0}]}],
            "gate": "straightline",
            "body": [{"if": {
                "cond": {"op": "<", "args": [{"var": "x"}, {"int": 0}]},
                "then": [{"assign": ["r", {"op": "-", "args": [
                    {"int": 0}, {"var": "x"}]}]}],
                "else": [{"assign": ["r", {"var": "x"}]}]}}],
        }
        w = {"x": -1, "_kind": "value", "_real": 1, "_twin": -1,
            "_ens": True}
        src = lower_spark.lower(task, task["body"], witness=w)
        self.assertNotIn("F_Cert", src)
        self.assertNotIn("_State_Cert", src)
        self.assertIn("(not (F (", src)

    def test_two_loops_falls_back_to_plain_f_call(self):
        task = {
            "t": 1, "name": "two_loops",
            "params": [{"name": "n", "type": "int"}],
            "returns": [{"name": "r", "type": "int"}],
            "requires": [{"op": ">=", "args": [{"var": "n"}, {"int": 0}]}],
            "ensures": [{"op": ">=", "args": [{"var": "r"}, {"int": 0}]}],
            "gate": "loops",
            "body": [
                {"var": {"name": "i", "type": "int", "init": {"int": 0}}},
                {"var": {"name": "r", "type": "int", "init": {"int": 0}}},
                {"while": {
                    "cond": {"op": "<", "args": [{"var": "i"}, {"var": "n"}]},
                    "decreases": {"op": "-", "args": [
                        {"var": "n"}, {"var": "i"}]},
                    "invariants": [
                        {"op": ">=", "args": [{"var": "i"}, {"int": 0}]}],
                    "body": [{"assign": ["i", {"op": "+", "args": [
                        {"var": "i"}, {"int": 1}]}]}]}},
                {"var": {"name": "j", "type": "int", "init": {"int": 0}}},
                {"while": {
                    "cond": {"op": "<", "args": [{"var": "j"}, {"var": "n"}]},
                    "decreases": {"op": "-", "args": [
                        {"var": "n"}, {"var": "j"}]},
                    "invariants": [
                        {"op": ">=", "args": [{"var": "j"}, {"int": 0}]}],
                    "body": [{"assign": ["j", {"op": "+", "args": [
                        {"var": "j"}, {"int": 1}]}]},
                            {"assign": ["r", {"op": "+", "args": [
                                {"var": "r"}, {"int": 1}]}]}]}},
            ],
        }
        w = {"n": 1, "_kind": "value", "_real": 1, "_twin": 0,
            "_ens": True}
        src = lower_spark.lower(task, task["body"], witness=w)
        # Two loops: _cert_loops finds 2, the len(loops) == 1 guard
        # refuses the new path and the pre-existing F(args) goal is kept
        # -- still a legitimate (if possibly unproved) certificate, never
        # a crash and never a silently wrong one.
        self.assertIn("(not (F (", src)


if __name__ == "__main__":
    unittest.main()
