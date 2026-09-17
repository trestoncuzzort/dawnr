"""t/test_lower_lean_loop_cert.py: unit tests for lower_lean.py's
2026-09-14 ROADMAP 16.2 addition (key lean-cert): value-witness
refutation certificates through loop bodies.

Two independent fixes, pinned separately below:

1. `Lower.lower_loop`'s constant-return-condition special case. A
   collapse-if twin whose mutated `if` condition becomes the literal
   Lean `True` (first_even's and is_prime's own committed twins) used
   to still emit the pre-existing `(if _hr : True then {retval} else
   {rec_call})` dite for the loop's early-return step. Measured
   directly (`lean -DmaxHeartbeats=1000000` on the emitted file,
   2026-09-14): Lean's termination elaborator does not thread `_hr`'s
   own `¬True` hypothesis into the `decreasing_by` obligation for the
   now-dead `rec_call` occurrence (confirmed via `set_option
   pp.all`: the obligation carries only the OUTER `_hg` hypothesis),
   so the obligation is the raw (and false, since the recursive call's
   own decreasing argument does not itself decrease) inequality with no
   way to derive `False` -- `first | omega | grind` fails, Lean
   recovers with `sorryAx`, and since `WellFounded.fix`'s `Acc.rec`
   motive is Type-valued (not proof-irrelevant the way a Prop-motived
   recursor would be), that `sorryAx` makes the WHOLE function stuck on
   `decide`/`simp`/`grind` forever after -- no certificate tactic can
   recover from a definition that cannot compute. The fix skips the
   dite entirely when the return condition is this literal constant
   (the guard-true step then ALWAYS returns, so the recursive call is
   not merely unreachable in principle, it is absent from the honest
   control flow), never firing for the real (whose own `if` condition
   is never a bare boolean literal).

2. `_cert_undefined_loop`, extending `_cert_undefined`'s pre-existing
   (loop-free-only) coverage to a body-level undefined witness whose
   task's body has a `while` -- reverse's own compare-flip twin (guard
   `i < len(s)` widened to `i <= len(s)`) is the committed example:
   at s=[], the guard now holds once, the loop body runs, and
   `s[len(s)-1-i] = s[-1]` is out of bounds. Unlike (1), this
   certificate never mentions the compiled `{name}_t`/`{name}_t_loop`
   at all (SPEC.md's definedness calculus is a fact about the raw spec
   body at the ground witness, independent of whether the compiled
   function elaborates cleanly): the loop is unrolled concretely,
   exactly as many iterations as interp.py's own execution takes
   before raising Undef, mirroring lower_framac.py's `_cert_stmts`
   while-case and lower_spark.py's own while-body replay (both dated
   2026-09-12).

Tests 1-2 below are pure-Python source-shape checks (no lean binary
invoked, matching test_lower_lean_seqcomp.py's/
test_lower_lean_divisorbound.py's own discipline: catch a regression in
the fix's own logic, not the kernel's). Test 3 pins first_even's
committed row's REFUTED verdict by actually invoking the lean kernel
(verifiers.lean.verify), skipped by name when no lean binary is on
PATH -- the same "skip a missing tool, name it, never fake a pass"
discipline t/test_framac_while_cert.py's own missing-corpus skip uses.

Run: cd <repo>/t && python3 test_lower_lean_loop_cert.py

MEASURED 2026-09-14 by `python3 t/test_lower_lean_loop_cert.py`: see the
printed unittest summary this run produces.

2026-09-15 (lean-sole, "the nine sole-blocked rows", ROADMAP 16.2/
COVERAGE-lifted-785.md's "Sole blockers"): added `ParamStateProductBridgeTest`
and `ParamStateProductBridgeKernelTest`, pinning `lower_lean.Lower.
_param_state_bridge_lines` (THE PARAM-STATE PRODUCT GAP, see that
method's own docstring) -- pow's and factorial's own committed shapes
(a param times a loop-state accumulator, both nonneg) needed `Int.
mul_nonneg` bridging `_t_loop_spec`'s recursive-apply closer never
offered before. MEASURED by `python3 t/test_lower_lean_loop_cert.py`:
`Ran 16 tests ... OK` (lean binary present on this run; the two new
kernel-invoking tests are not skipped). Regression: `python3 t/grade.py
--tasks t/tasks --kernels lean,dafny --flake 3 --jobs 4` over all 34
committed tasks reproduces t/AGREEMENT.md's lean column cell-for-cell
(count_vowels' pre-existing `unproved / unproved` included, unchanged);
a lean-only pass of t/conformance.py's own manifest (`probe_manifest()`/
`run_items()` restricted to the lean column) read 66 PASS, 0 FAIL,
matching t/CONFORMANCE.md's own baseline (0 FAIL in lean there too).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness
import interp
import lower_lean
import tasks_io

HERE = os.path.dirname(os.path.abspath(__file__))


class ConstantReturnConditionLoopDefTest(unittest.TestCase):
    """Pins fix (1)'s SHAPE: first_even's own collapse-if twin (task
    file, not hand-built -- the exact committed row the regression bar
    measures) must lower to a NON-recursive `_t_loop` def (no `_hr`
    dite, no recursive call at all in its body) once the guard-true
    step's own return condition is the literal `True`."""

    def _twin_src(self, task_name):
        task = tasks_io.load_task(
            os.path.join(HERE, "tasks", f"{task_name}.t"))
        twin, op, w = harness.twin_for(task)
        self.assertIsNotNone(w, f"{task_name}: no witness from twin_for")
        return lower_lean.lower(task, twin, w), op, w

    def test_first_even_collapse_if_loop_has_no_dead_recursive_branch(self):
        src, op, w = self._twin_src("first_even")
        self.assertEqual(op, "collapse-if")
        self.assertEqual(w.get("_kind"), "value")
        # the def itself: no `_hr` dite (the special case's whole point)
        loop_def = src.split("def first_even_t_loop", 1)[1].split(
            "def first_even_t ", 1)[0]
        self.assertNotIn("_hr", loop_def, loop_def)
        # ... and, since the branch never fires, no recursive occurrence
        # of the loop function's own name inside its own body either.
        body_start = loop_def.index(":=")
        self.assertNotIn("first_even_t_loop", loop_def[body_start:],
                         loop_def)
        # `termination_by`/`decreasing_by` are still emitted (harmless on
        # a now non-recursive def, matching every other lowered shape).
        self.assertIn("termination_by", loop_def)
        self.assertIn("t_refutation_certificate", src)

    def test_is_prime_collapse_if_loop_has_no_dead_recursive_branch(self):
        src, op, w = self._twin_src("is_prime")
        self.assertEqual(op, "collapse-if")
        self.assertEqual(w.get("_kind"), "value")
        loop_def = src.split("def is_prime_t_loop", 1)[1].split(
            "def is_prime_t ", 1)[0]
        self.assertNotIn("_hr", loop_def, loop_def)
        body_start = loop_def.index(":=")
        self.assertNotIn("is_prime_t_loop", loop_def[body_start:], loop_def)
        self.assertIn("t_refutation_certificate", src)

    def test_real_body_is_untouched_by_the_special_case(self):
        """The REAL (never a twin) never has a bare-literal `if`
        condition, so its own `_t_loop` def must still carry the
        pre-existing `_hr`-dite/recursive shape byte-for-byte -- this
        fix touches no path the real's own lowering takes."""
        task = tasks_io.load_task(os.path.join(HERE, "tasks",
                                                "first_even.t"))
        src = lower_lean.lower(task, task["body"], witness=None)
        loop_def = src.split("def first_even_t_loop", 1)[1].split(
            "def first_even_t ", 1)[0]
        self.assertIn("_hr", loop_def, loop_def)
        self.assertIn("first_even_t_loop", loop_def)


class UndefinedLoopCertificateTest(unittest.TestCase):
    """Pins fix (2)'s SHAPE: reverse's own compare-flip twin (an OOB
    access one loop iteration in) must build a certificate that never
    mentions the compiled `reverse_t`/`reverse_t_loop`."""

    def test_reverse_compare_flip_certificate_avoids_the_compiled_loop(self):
        task = tasks_io.load_task(os.path.join(HERE, "tasks", "reverse.t"))
        twin, op, w = harness.twin_for(task)
        self.assertEqual(op, "compare-flip")
        self.assertEqual(w.get("_kind"), "undefined")
        self.assertIsNone(w.get("_site"))
        src = lower_lean.lower(task, twin, w)
        self.assertIn("t_refutation_certificate", src)
        cert = src.split("theorem t_refutation_certificate", 1)[1]
        # the theorem's own STATEMENT (its type, before ":= by") never
        # mentions the compiled loop function -- `_closer()`'s generic
        # `simp [reverse_t] | ... | grind [reverse_t]` FALLBACK tactics
        # do name it (harmless: the certificate's own `decide` alternative
        # is what actually closes this goal, matching `_cert_undefined`'s
        # loop-free sibling, whose closer names `self.cert_fns` the same
        # way), so only the STATEMENT half is checked here.
        stmt = cert.split(":= by", 1)[0]
        self.assertNotIn("reverse_t", stmt, stmt)
        # verifiers/lean.py's own BANNED regex is the actual authority on
        # what disqualifies a file (`sorry`, `admit`, `assume_val`, a
        # bare `axiom` DECLARATION -- never the legitimate `#print
        # axioms` audit line every lowered file ends with); this is only
        # a sanity check that the certificate text itself never spells
        # any of the actually-banned tactics.
        for banned in ("sorry", "admit", "assume_val"):
            self.assertNotIn(banned, src.lower())

    def test_loop_free_undefined_path_is_unchanged(self):
        """A loop-free task's own undefined-kind certificate (swap's
        committed off-by-one twin, `to_expr`'s pre-existing path) must
        still route through `_cert_undefined`'s original body, never
        `_cert_undefined_loop` (no `while` in swap's body at all)."""
        task = tasks_io.load_task(os.path.join(HERE, "tasks", "swap.t"))
        self.assertFalse(any("while" in s for s in task["body"]))
        twin, op, w = harness.twin_for(task)
        src = lower_lean.lower(task, twin, w)
        self.assertIn("t_refutation_certificate", src)

    def test_seq_param_updated_in_loop_replays_as_tuples(self):
        """Sweep r24 (2026-09-14) found the loop replay crashing on a seq
        parameter: incrementArray (a seq param, `update` in the loop body,
        a compare-flip twin whose witness is undefined one iteration past
        the end) read LOWER-ERROR "can only concatenate list (not tuple)
        to list" in lean on both real and twin. interp.py's seq ops build
        tuples, and `_cert_undefined_loop` handed the witness's lists to
        interp.exec_body as they came. The same task, inline, must lower
        with a certificate and never raise."""
        task = {
            "name": "inc_array_probe",
            "params": [{"name": "a", "type": "seq"}],
            "returns": [{"name": "a_out", "type": "seq"}],
            "requires": [{"op": ">", "args": [{"op": "len", "args": [{"var": "a"}]}, {"int": 0}]}],
            "ensures": [
                {"op": "==", "args": [{"op": "len", "args": [{"var": "a_out"}]},
                                      {"op": "len", "args": [{"var": "a"}]}]},
                {"forall": {"var": "i", "lo": {"int": 0},
                            "hi": {"op": "len", "args": [{"var": "a_out"}]},
                            "body": {"op": "==", "args": [
                                {"op": "at", "args": [{"var": "a_out"}, {"var": "i"}]},
                                {"op": "+", "args": [{"op": "at", "args": [{"var": "a"}, {"var": "i"}]},
                                                     {"int": 1}]}]}}}],
            "body": [
                {"assign": ["a_out", {"var": "a"}]},
                {"var": {"name": "j", "type": "int", "init": {"int": 0}}},
                {"while": {
                    "cond": {"op": "<", "args": [{"var": "j"}, {"op": "len", "args": [{"var": "a_out"}]}]},
                    "decreases": {"op": "-", "args": [{"op": "len", "args": [{"var": "a_out"}]}, {"var": "j"}]},
                    "invariants": [
                        {"op": "==", "args": [{"op": "len", "args": [{"var": "a_out"}]},
                                              {"op": "len", "args": [{"var": "a"}]}]},
                        {"op": "and", "args": [{"op": "<=", "args": [{"int": 0}, {"var": "j"}]},
                                               {"op": "<=", "args": [{"var": "j"}, {"op": "len", "args": [{"var": "a_out"}]}]}]},
                        {"forall": {"var": "k", "lo": {"var": "j"},
                                    "hi": {"op": "len", "args": [{"var": "a_out"}]},
                                    "body": {"op": "==", "args": [
                                        {"op": "at", "args": [{"var": "a_out"}, {"var": "k"}]},
                                        {"op": "at", "args": [{"var": "a"}, {"var": "k"}]}]}}},
                        {"forall": {"var": "m", "lo": {"int": 0}, "hi": {"var": "j"},
                                    "body": {"op": "==", "args": [
                                        {"op": "at", "args": [{"var": "a_out"}, {"var": "m"}]},
                                        {"op": "+", "args": [{"op": "at", "args": [{"var": "a"}, {"var": "m"}]},
                                                             {"int": 1}]}]}}}],
                    "body": [
                        {"assign": ["a_out", {"op": "update", "args": [
                            {"var": "a_out"}, {"var": "j"},
                            {"op": "+", "args": [{"op": "at", "args": [{"var": "a_out"}, {"var": "j"}]},
                                                 {"int": 1}]}]}]},
                        {"assign": ["j", {"op": "+", "args": [{"var": "j"}, {"int": 1}]}]}]}}],
        }
        twin, op, w = harness.twin_for(task)
        self.assertEqual(op, "compare-flip")
        self.assertEqual(w.get("_kind"), "undefined")
        src = lower_lean.lower(task, twin, w)
        self.assertIn("t_refutation_certificate", src)


class DomainHypothesisLoopValueCertificateTest(unittest.TestCase):
    """2026-09-14 (lean-loopcert2, ROADMAP 16.2's value-witness-through-
    domain-hypothesis-loop item). `_cert_value_loop`'s own two measured
    shapes, each an inline task matching one of the two lifted rows Wave
    N left open by name (Clover_cal_sum.Sum, Dafny_Verify_..
    LoopInvariant.DownWhileGreater) -- built inline rather than read from
    t/out/lifted-tasks (gitignored, read-only) so this test is
    reproducible from the committed repo alone."""

    DOWN_WHILE_GREATER = {
        "name": "down_while_greater_probe",
        "params": [{"name": "n", "type": "int"}],
        "returns": [{"name": "i", "type": "int"}],
        "requires": [{"op": "<=", "args": [{"int": 0}, {"var": "n"}]}],
        "ensures": [{"op": "==", "args": [{"var": "i"}, {"int": 0}]}],
        "body": [
            {"assign": ["i", {"var": "n"}]},
            {"while": {
                "cond": {"op": "<", "args": [{"int": 0}, {"var": "i"}]},
                "decreases": {"var": "i"},
                "invariants": [
                    {"op": "and", "args": [
                        {"op": "<=", "args": [{"int": 0}, {"var": "i"}]},
                        {"op": "<=", "args": [{"var": "i"}, {"var": "n"}]}]}],
                "body": [
                    {"assign": ["i", {"op": "-",
                                      "args": [{"var": "i"}, {"int": 1}]}]}],
            }},
        ],
    }

    CAL_SUM = {
        "name": "cal_sum_probe",
        "params": [{"name": "n", "type": "int"}],
        "returns": [{"name": "s", "type": "int"}],
        "requires": [{"op": ">=", "args": [{"var": "n"}, {"int": 0}]}],
        "ensures": [{"op": "==", "args": [
            {"var": "s"},
            {"op": "div", "args": [
                {"op": "*", "args": [{"var": "n"}, {"op": "+", "args": [
                    {"var": "n"}, {"int": 1}]}]}, {"int": 2}]}]}],
        "body": [
            {"var": {"name": "n_v", "type": "int", "init": {"int": 0}}},
            {"assign": ["s", {"int": 0}]},
            {"while": {
                "cond": {"op": "!=", "args": [{"var": "n_v"}, {"var": "n"}]},
                "decreases": {"ite": {
                    "cond": {"op": "<=", "args": [{"var": "n_v"}, {"var": "n"}]},
                    "then": {"op": "-", "args": [{"var": "n"}, {"var": "n_v"}]},
                    "else": {"op": "-", "args": [{"var": "n_v"}, {"var": "n"}]}}},
                "invariants": [
                    {"op": "and", "args": [
                        {"op": "<=", "args": [{"int": 0}, {"var": "n_v"}]},
                        {"op": "<=", "args": [{"var": "n_v"}, {"var": "n"}]}]},
                    {"op": "==", "args": [
                        {"var": "s"},
                        {"op": "div", "args": [
                            {"op": "*", "args": [
                                {"var": "n_v"},
                                {"op": "+", "args": [{"var": "n_v"}, {"int": 1}]}]},
                            {"int": 2}]}]}],
                "body": [
                    {"assign": ["n_v", {"op": "+",
                                        "args": [{"var": "n_v"}, {"int": 1}]}]},
                    {"assign": ["s", {"op": "+",
                                      "args": [{"var": "s"}, {"var": "n_v"}]}]}],
            }},
        ],
    }

    def _stmt_of(self, src):
        cert = src.split("theorem t_refutation_certificate", 1)[1]
        return cert.split(":= by", 1)[0]

    def test_down_while_greater_compare_flip_avoids_the_can_dite_placeholder(self):
        """downWhileGreater's own compare-flip twin: `_t_loop`'s
        `can_dite`/`hok` mechanism (THE PRESERVATION-HAVE COLLISION's own
        fix) computes `_loop_zero`'s placeholder (0) at this witness, not
        the twin's actual value (-1) -- the certificate must never
        mention the compiled function at all, exactly like the undefined-
        witness certificates above."""
        task = self.DOWN_WHILE_GREATER
        twin, op, w = harness.twin_for(task)
        self.assertEqual(op, "compare-flip")
        self.assertEqual(w.get("_kind"), "value")
        self.assertEqual(w.get("_real"), 0)
        self.assertEqual(w.get("_twin"), -1)
        src = lower_lean.lower(task, twin, w)
        self.assertIn("if hok :", src)   # the can_dite/hok shape did fire
        self.assertIn("t_refutation_certificate", src)
        stmt = self._stmt_of(src)
        self.assertNotIn("down_while_greater_probe_t", stmt, stmt)
        for banned in ("sorry", "admit", "assume_val"):
            self.assertNotIn(banned, src.lower())

    def test_cal_sum_off_by_one_avoids_the_poisoned_entry_proof(self):
        """cal_sum's own off-by-one twin: `_t`'s own entry call to
        `_t_loop` bakes a GENERIC `(by grind)` proof of the (here
        genuinely false at entry) invariant, poisoning `_t` itself with
        `sorryAx` for every input -- the certificate must never mention
        the compiled function."""
        task = self.CAL_SUM
        twin, op, w = harness.twin_for(task)
        self.assertEqual(op, "off-by-one")
        self.assertEqual(w.get("_kind"), "value")
        src = lower_lean.lower(task, twin, w)
        self.assertIn("t_refutation_certificate", src)
        stmt = self._stmt_of(src)
        self.assertNotIn("cal_sum_probe_t", stmt, stmt)
        for banned in ("sorry", "admit", "assume_val"):
            self.assertNotIn(banned, src.lower())

    def test_plain_loop_value_witness_is_unaffected(self):
        """first_even's own committed collapse-if twin needs no domain
        hypothesis at all (`_loop_needs_domain_hyp` reads False) -- this
        wave's own new path must not fire, so the certificate keeps
        mentioning the compiled `first_even_t`/`first_even_t_loop`
        exactly as the pre-existing `{name}_t`-based path already did."""
        task = tasks_io.load_task(os.path.join(HERE, "tasks",
                                                "first_even.t"))
        twin, op, w = harness.twin_for(task)
        self.assertEqual(op, "collapse-if")
        self.assertEqual(w.get("_kind"), "value")
        src = lower_lean.lower(task, twin, w)
        stmt = self._stmt_of(src)
        self.assertIn("first_even_t", stmt, stmt)


class DomainHypothesisLoopValueCertificateKernelTest(unittest.TestCase):
    """Integration pin: both inline tasks above actually read REFUTED
    from the lean kernel (real stays VERIFIED), skipped by name when no
    lean binary is on PATH."""

    @classmethod
    def setUpClass(cls):
        try:
            from verifiers import lean as lean_backend
        except Exception as e:                          # noqa: BLE001
            cls.lean_backend = None
            cls.skip_reason = f"verifiers.lean import failed: {e}"
            return
        if not getattr(lean_backend, "LEAN", None):
            cls.lean_backend = None
            cls.skip_reason = "no lean binary on PATH"
            return
        cls.lean_backend = lean_backend

    def _check(self, task):
        if self.lean_backend is None:
            self.skipTest(self.skip_reason)
        import tempfile
        from pathlib import Path
        from verifiers import Outcome
        twin, op, w = harness.twin_for(task)
        real_src = lower_lean.lower(task, task["body"], witness=None)
        twin_src = lower_lean.lower(task, twin, w)
        with tempfile.TemporaryDirectory() as d:
            rp = Path(d) / "real.lean"
            tp = Path(d) / "twin.lean"
            rp.write_text(real_src, encoding="utf-8")
            tp.write_text(twin_src, encoding="utf-8")
            r_real = self.lean_backend.verify(rp)
            r_twin = self.lean_backend.verify(tp)
        self.assertEqual(r_real.outcome, Outcome.VERIFIED,
                         getattr(r_real, "error", ""))
        self.assertEqual(r_twin.outcome, Outcome.REFUTED,
                         getattr(r_twin, "error", ""))

    def test_down_while_greater_real_verified_twin_refuted(self):
        self._check(DomainHypothesisLoopValueCertificateTest.DOWN_WHILE_GREATER)

    def test_cal_sum_real_verified_twin_refuted(self):
        self._check(DomainHypothesisLoopValueCertificateTest.CAL_SUM)

    def test_value_witness_loop_replay_stays_small_with_a_return_in_the_body(self):
        """Sweep r25 (2026-09-15): `_cert_value_loop` threaded sym's own
        output env into the next iteration, and a body with a `return`
        wraps every state term in an if per iteration, so the terms
        doubled: clover_linear_search1's collapse-if twin hit MemoryError
        after 23 GB. linear_search's committed twin has the same shape
        (a value witness, a return inside the loop). Its lowering must
        finish inside a 4 GB address space and 60 seconds, in a child
        process so the cap cannot touch this runner."""
        import subprocess
        task_path = os.path.join(HERE, "tasks", "linear_search.t")
        code = (
            "import sys; sys.path.insert(0, %r)\n"
            "import tasks_io, harness, lower_lean\n"
            "task = tasks_io.load_task(%r)\n"
            "twin, op, w = harness.twin_for(task)\n"
            "assert w and w.get('_kind') == 'value', (op, w)\n"
            "src = lower_lean.lower(task, twin, w)\n"
            "print('OK' if 't_refutation_certificate' in src else 'NOCERT')\n"
        ) % (HERE, task_path)
        # `ulimit -v` is Linux; macOS rejects it ("cannot modify limit: Invalid
        # argument", 2026-09-16), so there the replay runs unbounded and only
        # the exit code and OK line are checked.
        import sys as _sys
        limit = "" if _sys.platform == "darwin" else "ulimit -v 4194304 && "
        proc = subprocess.run(
            ["bash", "-c", limit + "exec python3 -c \"$0\"", code],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        self.assertIn("OK", proc.stdout, proc.stdout)


class CommittedRowKernelVerdictTest(unittest.TestCase):
    """Integration pin: first_even's committed collapse-if twin actually
    reads REFUTED from the lean kernel (not just a plausible-looking
    certificate), and its own real still reads VERIFIED -- the two
    numbers the regression bar cares about. Skipped by name, never
    silently passed, when no lean binary is on PATH."""

    @classmethod
    def setUpClass(cls):
        try:
            from verifiers import lean as lean_backend
        except Exception as e:                          # noqa: BLE001
            cls.lean_backend = None
            cls.skip_reason = f"verifiers.lean import failed: {e}"
            return
        if not getattr(lean_backend, "LEAN", None):
            cls.lean_backend = None
            cls.skip_reason = "no lean binary on PATH"
            return
        cls.lean_backend = lean_backend

    def test_first_even_real_verified_twin_refuted(self):
        if self.lean_backend is None:
            self.skipTest(self.skip_reason)
        import tempfile
        from pathlib import Path
        task = tasks_io.load_task(os.path.join(HERE, "tasks",
                                                "first_even.t"))
        twin, op, w = harness.twin_for(task)
        real_src = lower_lean.lower(task, task["body"], witness=None)
        twin_src = lower_lean.lower(task, twin, w)
        with tempfile.TemporaryDirectory() as d:
            rp = Path(d) / "first_even.lean"
            tp = Path(d) / "first_even_twin.lean"
            rp.write_text(real_src, encoding="utf-8")
            tp.write_text(twin_src, encoding="utf-8")
            r_real = self.lean_backend.verify(rp)
            r_twin = self.lean_backend.verify(tp)
        from verifiers import Outcome
        self.assertEqual(r_real.outcome, Outcome.VERIFIED,
                         getattr(r_real, "error", ""))
        self.assertEqual(r_twin.outcome, Outcome.REFUTED,
                         getattr(r_twin, "error", ""))


class ParamStateProductBridgeTest(unittest.TestCase):
    """2026-09-15 (lean-sole, "the nine sole-blocked rows"): `_t_loop_
    spec`'s own recursive-apply closer needs `0 <= a * x` (a PARAM times
    a loop-STATE var, both nonneg) to discharge an `hinv`'s recursive-
    call instance -- built inline, matching Prog-Fun-Solutions_tmp_
    tmp7_gmnz5f_extra_pow.Pow's own committed shape (a param `a`, an
    accumulator `x`, `x := a * x` each iteration), not read from
    t/out/lifted-tasks (gitignored, read-only) so this test is
    reproducible from the committed repo alone."""

    POW_PROBE = {
        "name": "pow_probe",
        "params": [{"name": "a", "type": "int"}, {"name": "n", "type": "int"}],
        "returns": [{"name": "y", "type": "int"}],
        "requires": [
            {"op": ">=", "args": [{"var": "a"}, {"int": 0}]},
            {"op": ">=", "args": [{"var": "n"}, {"int": 0}]}],
        "ensures": [
            {"op": ">=", "args": [{"var": "y"}, {"int": 0}]},
            {"op": "==", "args": [{"var": "y"}, {
                "call": {"fun": "pow_v", "args": [{"var": "a"}, {"var": "n"}]}}]}],
        "spec_funs": [{
            "name": "pow_v",
            "params": [{"name": "a_v", "type": "int"}, {"name": "e", "type": "int"}],
            "result": "int",
            "decreases": {"var": "e"},
            "body": {"ite": {
                "cond": {"op": ">=", "args": [{"var": "e"}, {"int": 0}]},
                "then": {"ite": {
                    "cond": {"op": "==", "args": [{"var": "e"}, {"int": 0}]},
                    "then": {"int": 1},
                    "else": {"op": "*", "args": [{"var": "a_v"}, {
                        "call": {"fun": "pow_v", "args": [
                            {"var": "a_v"},
                            {"op": "-", "args": [{"var": "e"}, {"int": 1}]}]}}]}}},
                "else": {"int": 0}}},
        }],
        "body": [
            {"var": {"name": "x", "type": "int", "init": {"int": 1}}},
            {"var": {"name": "k", "type": "int", "init": {"int": 0}}},
            {"while": {
                "cond": {"op": "<", "args": [{"var": "k"}, {"var": "n"}]},
                "decreases": {"op": "-", "args": [{"var": "n"}, {"var": "k"}]},
                "invariants": [
                    {"op": "==", "args": [{"var": "x"}, {
                        "call": {"fun": "pow_v", "args": [{"var": "a"}, {"var": "k"}]}}]},
                    {"op": "and", "args": [
                        {"op": "<=", "args": [{"int": 0}, {"var": "k"}]},
                        {"op": "<=", "args": [{"var": "k"}, {"var": "n"}]}]},
                    {"op": ">=", "args": [{"var": "x"}, {"int": 0}]}],
                "body": [
                    {"assign": ["x", {"op": "*", "args": [{"var": "a"}, {"var": "x"}]}]},
                    {"assign": ["k", {"op": "+", "args": [{"var": "k"}, {"int": 1}]}]}],
            }},
            {"assign": ["y", {"var": "x"}]},
        ],
    }

    def test_recursive_apply_closer_carries_param_state_products(self):
        """The emitted `_t_loop_spec` tactic text must offer a `0 <= a *
        x`-shaped fact (either multiplication order) as a `first`-
        alternative on the recursive-apply closer -- the source-shape
        half of this fix, no lean binary needed."""
        task = self.POW_PROBE
        src = lower_lean.lower(task, task["body"], witness=None)
        spec = src.split("theorem pow_probe_t_loop_spec", 1)[1].split(
            "theorem pow_probe_t_spec", 1)[0]
        self.assertIn("Int.mul_nonneg", spec, spec)
        self.assertTrue(
            "(a) * (x)" in spec or "(x) * (a)" in spec, spec)

    def test_real_body_unaffected_when_no_nonlinear_goal_arises(self):
        """A loop task with no param/state product at all (first_even's
        committed real) must lower its `_t_loop_spec` byte-identically:
        `_param_state_bridge_lines` still returns a (harmless, `try`-
        wrapped) alternative, never removing or reordering the pre-
        existing `self._gr()` FIRST alternative every already-passing
        task closes on."""
        task = tasks_io.load_task(os.path.join(HERE, "tasks",
                                                "first_even.t"))
        src = lower_lean.lower(task, task["body"], witness=None)
        spec = src.split("theorem first_even_t_loop_spec", 1)[1].split(
            "theorem first_even_t_spec", 1)[0]
        # the pre-existing plain closer is still the FIRST alternative
        # tried at the recursive-apply site.
        self.assertIn("apply first_even_t_loop_spec <;> (first | grind |",
                      spec.replace("\n", " "), spec)


class ParamStateProductBridgeKernelTest(unittest.TestCase):
    """Integration pin: pow_probe's REAL reads VERIFIED from the lean
    kernel with this fix (measured UNPROVED before it, `grind` failing
    on `0 <= a * x` with no theory relating a product's sign to its two
    factors'). Skipped by name, never silently passed, when no lean
    binary is on PATH."""

    @classmethod
    def setUpClass(cls):
        try:
            from verifiers import lean as lean_backend
        except Exception as e:                          # noqa: BLE001
            cls.lean_backend = None
            cls.skip_reason = f"verifiers.lean import failed: {e}"
            return
        if not getattr(lean_backend, "LEAN", None):
            cls.lean_backend = None
            cls.skip_reason = "no lean binary on PATH"
            return
        cls.lean_backend = lean_backend

    def test_pow_probe_real_verified(self):
        if self.lean_backend is None:
            self.skipTest(self.skip_reason)
        import tempfile
        from pathlib import Path
        from verifiers import Outcome
        task = ParamStateProductBridgeTest.POW_PROBE
        real_src = lower_lean.lower(task, task["body"], witness=None)
        with tempfile.TemporaryDirectory() as d:
            rp = Path(d) / "pow_probe.lean"
            rp.write_text(real_src, encoding="utf-8")
            r_real = self.lean_backend.verify(rp)
        self.assertEqual(r_real.outcome, Outcome.VERIFIED,
                         getattr(r_real, "error", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
