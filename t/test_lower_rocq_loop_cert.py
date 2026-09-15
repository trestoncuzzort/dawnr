"""t/test_lower_rocq_loop_cert.py: pins ROADMAP 16.2's rocq-cert item,
2026-09-14 -- "rocq: value-witness certificates through loop bodies".

The reordered twin ladder (SPEC.md "The twins", d38da32) tries a
behavioral rung (collapse-if, negate-cond, compare-flip, boundary-swap,
off-by-one, wrong-var, drop-guard, wrong-constant, wrong-operator) before
invariant-drop; a "value"-kind witness on a loop task now reaches
`lower_rocq._value_cert` far more often than the old ladder's mostly
"exit"/"preservation" traffic that function's loop machinery was built
for, and an "undefined"-kind witness on a loop task now reaches
`_undef_cert` at all (it used to refuse a `while` outright). Before this
date's fix, three committed rows read rocq unproved where they read
refuted before the reorder: filter_pos (collapse-if, seq return, no
`return` in the loop), is_prime (collapse-if, bool return, a `return`
inside the loop), reverse (compare-flip, an "undefined" witness whose
first violation sits inside the loop's own guard). See lower_rocq.py's
own 2026-09-14 dated note, just above `_first_undef_body`, for the full
mechanism and the three separate narrow gaps this closes:

  1. `_undef_cert`'s own while-loop refusal is lifted: `_first_undef_body`
     (via the new `_undef_walk`) replays a `while` by CONCRETE UNROLLING
     at the witness, mirroring lower_framac.py's `_cert_stmts` while case
     and lower_spark.py's while-body replay -- reverse's own regression.

  2. `_value_cert`'s seq branch grounds the twin's own output LENGTH to a
     literal (`Ht_rlen`, `vm_compute; reflexivity`) before its `repeat
     match` runs, widens that match from an equality-only body to any
     Prop, and widens the closing tactic from bare `lia` to a small
     `first [...]` that also covers the raw `comparison`-constructor
     leftovers an over-eager `cbv` can produce -- filter_pos's own
     regression.

  3. `_value_cert` now calls `_forall_true_quants` for a return-bearing
     loop (`has_return(w["body"])`) and asserts each forall it finds
     concretely TRUE at the witness (`_forall_proof_block`, a bounded
     enumeration closed by `vm_compute`) into the certificate's own proof
     context before `t_dis` runs -- is_prime's own regression (its
     return-branch ensures needs the RHS forall PROVED, not merely
     falsified, to force the `<->`'s hard direction).

Each test below lowers a committed `.t` task (surface.parse, harness.
twin_for -- no hand-built AST, unlike test_lower_rocq.py's own probes:
the whole point here is the REAL committed shape, not a minimal
reproduction) and, when coqc is on PATH, actually compiles the emitted
certificate -- this kernel's own only positive evidence (verifiers/
rocq.py's own docstring). Skipped, not failed, when coqc is absent."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness
import lower_rocq
import tasks_io
from verifiers import Outcome
from verifiers import rocq as rocq_backend

COQC = shutil.which("coqc")
HERE = Path(__file__).resolve().parent


def _compile(src: str) -> tuple[bool, str]:
    """(accepted, stderr-or-stdout) for one coqc invocation on `src`."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "t_test.v"
        p.write_text(src, encoding="utf-8")
        r = subprocess.run([COQC, "-q", str(p)], capture_output=True,
                           text=True, timeout=180, cwd=td)
        return r.returncode == 0, (r.stdout + r.stderr)


_BANNED = re.compile(
    r"\b(admit|Admitted|sorry|assume|Axiom|trusted)\b", re.IGNORECASE)


def _assert_no_shortcuts(test: unittest.TestCase, src: str) -> None:
    """The honesty rule this whole item exists to serve: a REFUTED verdict
    comes from a certificate the kernel actually checks, never a token
    that fakes one. Word-boundary matched (`\\b...\\b`), not a bare
    substring: an ordinary English word like "admits" (this file's own
    PRELUDE prose, e.g. "a Prop admits an unbounded forall") must not
    trip a plain `"admit" in src.lower()` check -- MEASURED, this date,
    a first draft of this helper did exactly that."""
    m = _BANNED.search(src)
    if m is not None:
        test.fail(f"banned token {m.group(0)!r} in emitted Coq")


def _twin_source(task_file: str):
    """(task, twin_body, witness, source) for the committed `.t` task
    named `task_file` (a path under t/tasks/), lowered exactly the way
    grade.py/harness.py do: `harness.twin_for` picks the ladder's own
    rung and witness, `lower_rocq.lower` gets that witness so the
    certificate path (`_try_cert_v1`) is tried before the ordinary,
    unprovable-by-design theorem."""
    task = tasks_io.load_task(str(HERE / "tasks" / task_file))
    twin_body, rung, witness = harness.twin_for(task)
    src = lower_rocq.lower(task, twin_body, witness=witness)
    return task, twin_body, witness, src, rung


class FilterPosLoopCertTest(unittest.TestCase):
    """filter_pos (SEQ return, no `return` in the loop): a collapse-if
    twin's falsified conjunct is a SELF-referential forall inequality
    over the twin's own output length (`forall k, 0 <= k < len(r) ->
    r[k] > 0`), not the two-seq-PARAM pointwise equality the certificate's
    `repeat match` was originally built for."""

    def test_witness_is_value_kind_collapse_if(self):
        _task, _body, witness, _src, rung = _twin_source("filter_pos.t")
        self.assertEqual(rung, "collapse-if")
        self.assertEqual(witness.get("_kind"), "value")

    def test_certificate_grounds_the_return_length(self):
        # Pins the SHAPE of the fix: the return length is grounded to a
        # literal by `vm_compute` before the per-conjunct `repeat match`
        # (rocq-perconj, 2026-09-14: one arm per ensures conjunct, keyed
        # on its own exact rendered text post-`Ht_rlen`-rewrite, each
        # specializing at ITS OWN falsifying index -- no longer one
        # generic `_ <= t_k < _` wildcard arm shared by every conjunct
        # at a single shared index) ever runs, and the closer widens
        # past bare `lia`.
        _task, _body, _witness, src, _rung = _twin_source("filter_pos.t")
        self.assertIn("Ht_rlen", src)
        self.assertIn("vm_compute; reflexivity", src)
        self.assertIn("|- False =>\n      specialize (H 0 ltac:(lia))", src)
        self.assertIn("first [ lia | congruence | intuition congruence ]",
                      src)

    @unittest.skipUnless(COQC, "coqc not on PATH")
    def test_certificate_compiles_and_refutes(self):
        _task, _body, _witness, src, _rung = _twin_source("filter_pos.t")
        ok, out = _compile(src)
        self.assertTrue(ok, out)
        _assert_no_shortcuts(self, src)


class IsPrimeLoopCertTest(unittest.TestCase):
    """is_prime (a `return` inside the loop): a collapse-if twin forces
    `is_prime_t 3 = false`, so refuting the ensures' own `<->` needs the
    RHS forall (`forall d, 2 <= d < 3 -> n mod d <> 0`) PROVED true, the
    mirror image of `_loop_cert`'s own has_return fix (2026-09-09) for a
    forall that must be FALSIFIED."""

    def test_witness_is_value_kind_collapse_if(self):
        _task, _body, witness, _src, rung = _twin_source("is_prime.t")
        self.assertEqual(rung, "collapse-if")
        self.assertEqual(witness.get("_kind"), "value")

    def test_certificate_asserts_the_bounded_forall(self):
        _task, _body, _witness, src, _rung = _twin_source("is_prime.t")
        self.assertIn("t_bq0", src)
        # A single-value range (2 <= d < 3) takes the `subst`-only path,
        # never the (invalid, MEASURED) bare-arrow `destruct` pattern.
        self.assertIn("subst d", src)
        self.assertNotIn("as ->", src)

    @unittest.skipUnless(COQC, "coqc not on PATH")
    def test_certificate_compiles_and_refutes(self):
        task, body, witness, src, _rung = _twin_source("is_prime.t")
        ok, out = _compile(src)
        self.assertTrue(ok, out)
        _assert_no_shortcuts(self, src)


class ReverseLoopCertTest(unittest.TestCase):
    """reverse (an "undefined" witness whose first violation sits inside
    the loop's own guard): `_undef_cert` used to refuse a `while`
    outright; `_undef_walk` now unrolls it concretely at the witness."""

    def test_witness_is_undefined_kind_compare_flip(self):
        _task, _body, witness, _src, rung = _twin_source("reverse.t")
        self.assertEqual(rung, "compare-flip")
        self.assertEqual(witness.get("_kind"), "undefined")

    def test_certificate_is_built_at_all(self):
        # Before this fix `_undef_cert` returned None the moment
        # `find_while` found a loop, so `lower()` fell through to the
        # ordinary, unprovable theorem -- no `t_refutation_certificate`
        # comment, no witness text, in the emitted source at all.
        _task, _body, witness, src, _rung = _twin_source("reverse.t")
        self.assertIn("t_refutation_certificate", src)
        self.assertIn(harness.witness(witness), src)

    @unittest.skipUnless(COQC, "coqc not on PATH")
    def test_certificate_compiles_and_refutes(self):
        _task, _body, _witness, src, _rung = _twin_source("reverse.t")
        ok, out = _compile(src)
        self.assertTrue(ok, out)
        _assert_no_shortcuts(self, src)


_LUCID_JSON = Path(
    "/home/tmcuzzort/tup/t/out/lifted-tasks/"
    "dafny-synthesis_task_id_603.LucidNumbers.json")


@unittest.skipUnless(_LUCID_JSON.is_file(), "lifted corpus row not present")
class LucidNumbersPerConjunctTest(unittest.TestCase):
    """dafny_synthesis_task_id_603__lucidNumbers (rocq-perconj, 2026-09-14:
    "a per-conjunct falsifying index in the seq-return certificate"): the
    lifted row named in ROADMAP 16.2 as `_value_cert`'s seq branch's
    Sole blocker. Its ensures has THREE forall conjuncts over the twin's
    own output (a mod-3 property, an upper bound, a strict monotonicity
    nested two foralls deep); the witness (n=1, twin=[0, 1]) falsifies
    only the FIRST, at index 1 -- the OLD single-shared-index match
    (`specialize (H 0 ...)` everywhere) proved nothing and coqc read "No
    applicable tactic" (MEASURED, this date, before this fix). This task
    is not in the committed 34 (`t/tasks`, AGREEMENT.md's own regression
    set), so it is read directly from the read-only lifted corpus named
    in this item's own instructions; the test is skipped, not failed,
    when that file is absent."""

    def _lower(self):
        task = tasks_io.load_task(str(_LUCID_JSON))
        twin_body, rung, witness = harness.twin_for(task)
        src = lower_rocq.lower(task, twin_body, witness=witness)
        return task, twin_body, witness, src, rung

    def test_witness_is_value_kind_collapse_if(self):
        _task, _body, witness, _src, rung = self._lower()
        self.assertEqual(rung, "collapse-if")
        self.assertEqual(witness.get("_kind"), "value")

    def test_three_arms_at_three_distinct_index_lists(self):
        # Pins the FIX's own shape: one match arm per forall conjunct
        # (three, for this task), the first specialized at index 1 (the
        # actual falsifying index, not the old shared default 0), the
        # third (nested two levels) specialized twice on the same `H`.
        _task, _body, _witness, src, _rung = self._lower()
        self.assertEqual(src.count("|- False =>"), 3)
        self.assertIn(
            "-> ((t_mod ((dafny_synthesis_task_id_603__lucidNumbers_t 1) "
            "i) 3) = 0)) |- False =>\n      specialize (H 1 ltac:(lia))",
            src)
        self.assertIn(
            "specialize (H 0 ltac:(lia)); specialize (H 1 ltac:(lia)); "
            "cbv in H",
            src)

    @unittest.skipUnless(COQC, "coqc not on PATH")
    def test_certificate_compiles_and_refutes(self):
        _task, _body, _witness, src, _rung = self._lower()
        ok, out = _compile(src)
        self.assertTrue(ok, out)
        _assert_no_shortcuts(self, src)

    @unittest.skipUnless(COQC and shutil.which("coqchk"),
                         "coqc/coqchk not on PATH")
    def test_graded_verdict_is_refuted(self):
        task, _body, _witness, src, _rung = self._lower()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / f"{task['name']}_twin.v"
            p.write_text(src, encoding="utf-8")
            result = rocq_backend.verify(p)
            self.assertEqual(result.outcome, Outcome.REFUTED,
                             getattr(result, "detail", ""))


_TESTDOUBLE_JSON = Path(
    "/home/tmcuzzort/tup/t/out/lifted-tasks/"
    "dafny-learn_tmp_tmpn94ir40q_R01_functions.TestDouble.json")


@unittest.skipUnless(_TESTDOUBLE_JSON.is_file(), "lifted corpus row not present")
class TestDoubleReflexivityTest(unittest.TestCase):
    """dafny_learn_tmp_tmpn94ir40q_r01_functions__testDouble (2026-09-15,
    this item's rocq-sole task): one of t/COVERAGE-lifted-785.md's eight
    rocq-sole-blocked rows. `sf_double` is a degenerate, non-recursive
    spec_fun (coqc's own "Not a truly recursive fixpoint" warning), so the
    REAL theorem's goal (`2 * val = sf_double val`) is already true BY
    COMPUTATION before any rewrite runs -- and `t_eqs`'s own `try rewrite
    sf_double_eq` step FAILS outright with coqc's "Tactic generated a
    subgoal identical to the original goal" (silently swallowed by
    `try`), leaving the goal exactly as it started for `t_vc0` to fail on
    a second time. `t_leaf` had no `reflexivity` arm to close this
    directly (MEASURED before this date's fix: real=unproved, coqc's own
    "Tactic failure: unsolved t verification condition"). This task is
    not in the committed 34, so it is read from the read-only lifted
    corpus; skipped, not failed, when that file is absent."""

    def _lower(self):
        task = tasks_io.load_task(str(_TESTDOUBLE_JSON))
        src = lower_rocq.lower(task, task["body"], witness=None)
        return task, src

    def test_prelude_has_reflexivity_leaf(self):
        # Pins the fix itself: reflexivity, tried first, sound (it can
        # only close a goal already definitionally true on both sides).
        _task, src = self._lower()
        self.assertIn(
            "Ltac t_leaf := solve [ reflexivity | lia | assumption "
            "| congruence | discriminate | (exfalso; lia) ].", src)

    @unittest.skipUnless(COQC, "coqc not on PATH")
    def test_real_compiles(self):
        _task, src = self._lower()
        ok, out = _compile(src)
        self.assertTrue(ok, out)

    @unittest.skipUnless(COQC and shutil.which("coqchk"),
                         "coqc/coqchk not on PATH")
    def test_graded_verdict_is_verified(self):
        task, src = self._lower()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / f"{task['name']}.v"
            p.write_text(src, encoding="utf-8")
            result = rocq_backend.verify(p)
            self.assertEqual(result.outcome, Outcome.VERIFIED,
                             getattr(result, "detail", ""))


class ConjunctionSplitTest(unittest.TestCase):
    """t_go/t_go_ext had NO rule for a conjunctive goal before this date
    (2026-09-15): `t_leaf`'s `assumption` cannot introduce a conjunction
    even when every conjunct is individually a hypothesis, so a
    `_loop_spec`'s own five-plus-conjunct conclusion relied entirely on
    `lia`'s partial (opaque-spec_fun-blind) native `/\\` handling inside
    `t_leaf`. Prelude-only (no committed/lifted task's OWN outcome flips
    on this arm alone -- every row it also touches needs a further,
    separately-named proof step, see lower_rocq.py's 2026-09-15 note),
    so this pins the Ltac feature directly against a synthetic goal
    shaped exactly like a `_loop_spec` conclusion."""

    def test_go_split_arm_present(self):
        prelude = lower_rocq.PRELUDE_CORE_4
        self.assertIn("| |- _ /\\ _ => split; t_go m\n        end\n",
                      prelude)
        self.assertIn("| |- _ /\\ _ => split; t_go_ext m\n        end\n",
                      prelude)

    @unittest.skipUnless(COQC, "coqc not on PATH")
    def test_conjunctive_goal_closes_from_matching_hypotheses(self):
        # A synthetic task whose real theorem's conclusion is a five-way
        # conjunction, each conjunct individually a hypothesis (mirrors a
        # `_loop_spec` base-case conclusion after `inversion`/`subst`) --
        # UNPROVED without the split arm (confirmed by reverting it),
        # closes now.
        task = {
            "t": 1, "name": "t_conj_probe",
            "params": [{"name": "i", "type": "int"},
                       {"name": "n", "type": "int"},
                       {"name": "b", "type": "int"}],
            "requires": [
                {"op": "and", "args": [
                    {"op": "and", "args": [
                        {"op": "<", "args": [{"int": 0}, {"var": "i"}]},
                        {"op": "<=", "args": [{"var": "i"}, {"var": "n"}]}]},
                    {"op": "and", "args": [
                        {"op": ">=", "args": [{"var": "b"}, {"int": 0}]},
                        {"op": "not", "args": [
                            {"op": "<", "args": [{"var": "i"}, {"var": "n"}]}]}]}]}],
            "returns": [{"name": "result", "type": "bool"}],
            "body": [{"assign": ["result", {"bool": True}]}],
            "ensures": [
                {"op": "and", "args": [
                    {"op": "and", "args": [
                        {"op": "<", "args": [{"int": 0}, {"var": "i"}]},
                        {"op": "<=", "args": [{"var": "i"}, {"var": "n"}]}]},
                    {"op": "and", "args": [
                        {"op": ">=", "args": [{"var": "b"}, {"int": 0}]},
                        {"op": "not", "args": [
                            {"op": "<", "args": [{"var": "i"}, {"var": "n"}]}]}]}]}],
        }
        src = lower_rocq.lower(task, task["body"], witness=None)
        ok, out = _compile(src)
        self.assertTrue(ok, out)


@unittest.skipUnless(COQC, "coqc not on PATH")
class RealUnchangedTest(unittest.TestCase):
    """Never touch the real's own proof machinery: filter_pos/is_prime/
    reverse's REAL side must still lower and compile exactly as before
    this change (the fix only reaches `_try_cert_v1`'s TWIN-only code
    paths -- `_undef_cert`, `_value_cert`; `lower_v1`/`gen_loop`, which
    build the real's own theorem, are untouched by this diff)."""

    def test_reals_still_verify(self):
        for name in ("filter_pos.t", "is_prime.t", "reverse.t"):
            with self.subTest(task=name):
                task = tasks_io.load_task(str(HERE / "tasks" / name))
                src = lower_rocq.lower(task, task["body"], witness=None)
                ok, out = _compile(src)
                self.assertTrue(ok, out)


@unittest.skipUnless(COQC and shutil.which("coqchk"),
                     "coqc/coqchk not on PATH")
class GradedVerdictTest(unittest.TestCase):
    """The end-to-end contract: verifiers/rocq.py itself reads REFUTED for
    each fixed twin (not merely "coqc accepted the .v file", which a
    vacuously-true certificate could also satisfy -- Outcome.REFUTED is
    rocq.py's own, independently-decided verdict)."""

    def _refuted(self, name: str):
        task, twin_body, witness, src, _rung = _twin_source(name)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / f"{task['name']}_twin.v"
            p.write_text(src, encoding="utf-8")
            result = rocq_backend.verify(p)
            self.assertEqual(result.outcome, Outcome.REFUTED,
                             getattr(result, "detail", ""))

    def test_filter_pos_twin_refuted(self):
        self._refuted("filter_pos.t")

    def test_is_prime_twin_refuted(self):
        self._refuted("is_prime.t")

    def test_reverse_twin_refuted(self):
        self._refuted("reverse.t")


if __name__ == "__main__":
    unittest.main()
