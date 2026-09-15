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


class TestGaussSumInvariant(unittest.TestCase):
    """spark-sole (2026-09-14, `_gauss_sum_target`'s own docstring): a loop
    invariant `sum == div(i * (i + 1), 2)` gets the extra, ordinary
    invariant `2 * sum == i * (i + 1)`, so gnatprove's inductive step never
    has to cross a T_Div case split and a nonlinear product in the same
    goal. MEASURED gap this pins (this session, gnatprove FSF 16.1.0):
    gauss's and triangleNumber's own spark REAL used to TIMEOUT
    (VC_POSTCONDITION severity medium/limit, budget exhausted) even
    standalone, no contention; with the fix both verify in ~5-7s and their
    twins (kind "value", already routed through `F_Cert`) read REFUTED,
    unchanged."""

    def _gauss_task(self):
        return {
            "t": 1, "name": "gauss_t", "params": [{"name": "n", "type": "int"}],
            "returns": [{"name": "sum", "type": "int"}],
            "requires": [{"op": ">=", "args": [{"var": "n"}, {"int": 0}]}],
            "ensures": [{"op": "==", "args": [
                {"var": "sum"},
                {"op": "div", "args": [
                    {"op": "*", "args": [{"var": "n"}, {"op": "+", "args": [
                        {"var": "n"}, {"int": 1}]}]}, {"int": 2}]}]}],
            "gate": "loops",
            "body": [
                {"var": {"name": "sum", "type": "int", "init": {"int": 0}}},
                {"var": {"name": "i", "type": "int", "init": {"int": 0}}},
                {"while": {
                    "cond": {"op": "<", "args": [{"var": "i"}, {"var": "n"}]},
                    "decreases": {"op": "-", "args": [
                        {"var": "n"}, {"var": "i"}]},
                    "invariants": [
                        {"op": "==", "args": [
                            {"var": "sum"},
                            {"op": "div", "args": [
                                {"op": "*", "args": [
                                    {"var": "i"}, {"op": "+", "args": [
                                        {"var": "i"}, {"int": 1}]}]},
                                {"int": 2}]}]}],
                    "body": [
                        {"assign": ["i", {"op": "+", "args": [
                            {"var": "i"}, {"int": 1}]}]},
                        {"assign": ["sum", {"op": "+", "args": [
                            {"var": "sum"}, {"var": "i"}]}]}]}},
            ],
        }

    def test_target_matches_running_total_invariant(self):
        w = self._gauss_task()["body"][2]["while"]
        found = lower_spark._gauss_sum_target(w)
        self.assertIsNotNone(found)
        self.assertEqual(found["var"], "sum")
        self.assertEqual(found["numerator"], {"op": "*", "args": [
            {"var": "i"}, {"op": "+", "args": [{"var": "i"}, {"int": 1}]}]})

    def test_no_match_returns_none(self):
        w = {"invariants": [{"op": ">=", "args": [{"var": "i"}, {"int": 0}]}]}
        self.assertIsNone(lower_spark._gauss_sum_target(w))

    def test_real_lowering_carries_the_extra_invariant(self):
        task = self._gauss_task()
        src = lower_spark.lower(task, task["body"])
        # The doubled restatement appears somewhere in W_1's Pre/Post
        # (not pinned to exact whitespace of one particular rendering).
        self.assertIn("Big_Integer'(2) * Sum", src)
        self.assertIn("I * (I + Big_Integer'(1))", src)


class TestUndefinedCondCertificate(unittest.TestCase):
    """spark-sole (2026-09-14, `_undef_obligation`'s own dated note): a
    compare-flip twin whose loop guard runs one iteration too far can make
    the FIRST undefined operation sit in the loop body's own `if` (or
    `while`) COND rather than in a `var`/`assign` RHS -- `_walk` used to
    answer `return None` (no certificate at all) the instant it met that
    shape, even though `interp.ev` had just confirmed the cond's own
    definedness obligation false at this concrete witness. MEASURED gap
    this pins (this session, gnatprove FSF 16.1.0, mmaximum1/findMax/
    findMin/lookForMin/find_min_index's own spark twins): no
    T_Refutation_Certificate was ever emitted, so gnatprove reported the
    file's own honest (but here IRRELEVANT to the twin question) W_1
    contract failure -- verified/unproved, never verified/refuted. Fixed
    by surfacing the cond's own false definedness obligation as the found
    one, the same reading a var/assign RHS's already got two lines below."""

    def _one_at_task(self):
        # v[0] > v[i]-shaped guard collapsed to a length-1 case: a
        # compare-flip mutation (`<` -> `<=`) makes the loop run one
        # iteration too far and read `v[j]` with `j == len(v)`.
        return {
            "t": 1, "name": "first_ge_t",
            "params": [{"name": "v", "type": "seq"}],
            "returns": [{"name": "r", "type": "int"}],
            "requires": [{"op": ">", "args": [
                {"op": "len", "args": [{"var": "v"}]}, {"int": 0}]}],
            "ensures": [{"op": ">=", "args": [{"var": "r"}, {"int": 0}]}],
            "gate": "loops",
            "body": [
                {"var": {"name": "j", "type": "int", "init": {"int": 0}}},
                {"var": {"name": "r", "type": "int", "init": {"int": 0}}},
                {"while": {
                    "cond": {"op": "<", "args": [
                        {"var": "j"},
                        {"op": "len", "args": [{"var": "v"}]}]},
                    "decreases": {"op": "-", "args": [
                        {"op": "len", "args": [{"var": "v"}]}, {"var": "j"}]},
                    "invariants": [
                        {"op": "<=", "args": [
                            {"var": "j"},
                            {"op": "len", "args": [{"var": "v"}]}]}],
                    "body": [
                        {"if": {
                            "cond": {"op": ">", "args": [
                                {"op": "at", "args": [
                                    {"var": "v"}, {"var": "j"}]},
                                {"int": 0}]},
                            "then": [{"assign": ["r", {"var": "j"}]}],
                            "else": []}},
                        {"assign": ["j", {"op": "+", "args": [
                            {"var": "j"}, {"int": 1}]}]}]}},
            ],
        }

    def test_walk_surfaces_the_ifs_own_cond(self):
        task = self._one_at_task()
        # The twin: `<` -> `<=` in the while's own guard, a one-line
        # compare-flip exactly like harness's own mutator would produce.
        twin_body = [dict(s) for s in task["body"]]
        twin_while = dict(twin_body[2]["while"])
        twin_while["cond"] = {"op": "<=", "args": twin_while["cond"]["args"]}
        twin_body[2] = {"while": twin_while}
        w = {"v": [0], "_kind": "undefined", "_real": "no value"}
        sub = {"v": lower_spark._cert_lit([0])}
        vals = {"v": [0]}
        L = lower_spark.Lower(task)
        ob = lower_spark._undef_obligation(task, twin_body, sub, vals, L)
        self.assertIsNotNone(ob, "the if's own cond must now be surfaced")
        self.assertIn("not", ob)

    def test_certificate_now_emitted_end_to_end(self):
        task = self._one_at_task()
        twin_body = [dict(s) for s in task["body"]]
        twin_while = dict(twin_body[2]["while"])
        twin_while["cond"] = {"op": "<=", "args": twin_while["cond"]["args"]}
        twin_body[2] = {"while": twin_while}
        w = {"v": [0], "_kind": "undefined", "_real": "no value"}
        src = lower_spark.lower(task, twin_body, witness=w)
        self.assertIn("T_Refutation_Certificate", src)


class TestEarlyExitOneSidedJoin(unittest.TestCase):
    """spark-tail, 2026-09-15 (ROADMAP 16.2): compile_r's own "if" merge
    used to raise NotImplementedError("... assigned on only one branch of
    an `if` and read later; no join value") whenever the RETURN NAME
    itself was live on only one side of an if -- exactly the shape
    `if cond { ...; return X; }` followed by the real "else" as separate
    statements after the if (the early-exit encoding SPEC.md's own note
    above describes), because lower()'s own env seed `{ret_name: None}`
    means the never-taken side of the merge reads Python None, not an
    Ada expression, and the OLD per-variable loop joined it exactly like
    an ordinary local instead of recognizing the escape. MEASURED (this
    session, gnatprove FSF 16.1.0) on
    formal_verication_dafny_tmp_tmpwgl2qz28_Challenges_ex2.Allow42.json:
    ABSTAIN "spark: 'r' assigned on only one branch of an `if` and read
    later; no join value" before the fix; verified/refuted (matching
    dafny) after it. This is the minimal task-shaped reproduction of that
    exact bug, independent of the corpus file."""

    def _early_return_task(self) -> dict:
        return {
            "name": "one_sided_join",
            "params": [{"name": "y", "type": "int"}],
            "returns": [{"name": "r", "type": {"pair": ["int", "bool"]}}],
            "requires": [],
            "ensures": [
                {"op": "implies", "args": [
                    {"op": "==", "args": [{"var": "y"}, {"int": 0}]},
                    {"op": "and", "args": [
                        {"op": "==", "args": [
                            {"op": "fst", "args": [{"var": "r"}]},
                            {"int": 1}]},
                        {"op": "==", "args": [
                            {"op": "snd", "args": [{"var": "r"}]},
                            {"bool": True}]}]}]},
                {"op": "implies", "args": [
                    {"op": "!=", "args": [{"var": "y"}, {"int": 0}]},
                    {"op": "and", "args": [
                        {"op": "==", "args": [
                            {"op": "fst", "args": [{"var": "r"}]},
                            {"int": 0}]},
                        {"op": "==", "args": [
                            {"op": "snd", "args": [{"var": "r"}]},
                            {"bool": False}]}]}]},
            ],
            "gate": "loops",
            "body": [
                {"if": {
                    "cond": {"op": "==", "args": [{"var": "y"}, {"int": 0}]},
                    "then": [
                        {"return": ["r", {"op": "pair", "args": [
                            {"int": 1}, {"bool": True}]}]}],
                    "else": []}},
                {"assign": ["r", {"op": "pair", "args": [
                    {"int": 0}, {"bool": False}]}]},
            ],
        }

    def test_no_longer_abstains_on_the_return_name(self):
        task = self._early_return_task()
        src = lower_spark.lower(task, task["body"])
        self.assertNotIn("None", src)
        self.assertIn("function F ", src)

    def test_lowered_pair_matches_both_ensures_arms(self):
        task = self._early_return_task()
        src = lower_spark.lower(task, task["body"])
        # The escaping branch's literal (1, True) and the fall-through's
        # (0, False) must both appear in F's body, joined on the SAME
        # `y = 0` condition the ensures itself splits on -- not one of
        # them silently dropped by a bad join.
        self.assertIn("True", src)
        self.assertIn("False", src)


if __name__ == "__main__":
    unittest.main()
