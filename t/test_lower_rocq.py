"""t/test_lower_rocq.py: regression tests for ROADMAP 16.2's rocq rows,
2026-09-11.

Two fixes landed here, each closing a whole cluster of the 2026-09-10
lifted corpus's rocq FINDINGs (t/COVERAGE-lifted-785.md, re-measured
before this wave in t/ROADMAP.md's own 16.2 entry):

  1. gen_loop's own invariant set now carries one synthetic equality per
     prefix-declared INT local the loop body never reassigns (`h := |a|`
     held fixed as the bound while another variable walks up to it) --
     appendArrayToSeq, arrayToSeq, getFirstElements, elementWiseDivide,
     addLists, squareElements, findSmallest, smallestListLength (8 of the
     15 lifted 2026-09-10 tasks) all read real=UNPROVED before this,
     coqc's own "Tactic failure: unsolved t verification condition" on
     the loop body's own array-indexing definedness lemma, which needed
     `h = a_len` and had no way to see it.

  2. `_plain_def`'s seq-return branch used to bail outright (a STALE
     comment said its only caller, `_value_cert`, "abstains on a seq
     return outright" -- true before `_value_cert` grew a seq branch,
     stale since), so a loop-free, non-recursive task with a seq return
     and a "value" witness -- swap's own shape, `[b, a]` -- had no
     refutation certificate reachable at all: the twin fell back to the
     plain unprovable theorem, real=verified/twin=UNPROVED, not the
     honest REFUTED its own measured witness already supports. Fixed by
     giving `_plain_def` the same two-Definition (function half, length
     half) split `gen_plain`/`gen_loop` already build for a plain seq
     return. `_value_cert`'s own seq-branch proof script also needed one
     `cbv in *` before its closing `lia`: a falsifying conjunct that is a
     concrete-index equation against a scalar (`result[0] == b`, never
     wrapped in a `forall`) is not the shape the `repeat match` step
     reaches, so it survived `decompose` unreduced -- an opaque function
     application `lia` cannot see through.

  3. A SEPARATE prelude variant, POST_SF_NIA, gives `t_dis` one more
     fallback, `solve [ timeout 5 nia ]`, tried last: centeredHexagonalNumber's
     own `3 * n * (n - 1) + 1 >= 0` is a genuinely nonlinear goal (a
     product of two variables) `lia` cannot reach at all. Spliced in only
     for a task `_has_nonlinear_mul` finds a genuine variable-times-
     variable product in (never POST_SF itself, unchanged, byte-identical
     for every other task). MEASURED WRONG twice before landing here:
     bare `nia` sent isPrime's own mod-shaped, genuinely UNPROVABLE goal
     into a search long enough to blow the file's 180s wall backstop by
     itself; `timeout 5 nia` spliced into EVERY task's prelude still did,
     for isPrime and containsSequence, from the ACCUMULATED cost of many
     bounded-but-failing attempts across one file's many `t_dis` call
     sites (each paying its own 5s before `first` moves on).

Each test below lowers a small, self-contained task (the committed
shape's own essence, not a copy of a lifted corpus file) and, when coqc
is on PATH, actually compiles the result -- the only check this kernel's
own contract (verifiers/rocq.py's docstring) accepts as positive
evidence. Skipped, not failed, when coqc is absent (this machine's own
docskills/tup venvs never carry it; ROADMAP 16.2's own worktree does).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness
import lower_rocq

COQC = shutil.which("coqc")


def _compile(src: str) -> tuple[bool, str]:
    """(accepted, stderr-or-stdout) for one coqc invocation on `src`."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "t_test.v"
        p.write_text(src, encoding="utf-8")
        r = subprocess.run([COQC, "-q", str(p)], capture_output=True,
                            text=True, timeout=120, cwd=td)
        return r.returncode == 0, (r.stdout + r.stderr)


# A prefix-declared int local (`h`), initialized to a param's length and
# never reassigned in the loop body -- upWhileLess's own committed shape,
# and (word for word, ROADMAP 16.2's ds15-new set) arrayToSeq's own shape,
# dafny_synthesis_task_id_587.ArrayToSeq.json: `s := []; var h := |a|; var
# i_v := 0; while i_v < h { s := s + [a[i_v]]; i_v := i_v + 1; }`. Read
# unproved/refuted in rocq before this fix, verified/refuted after
# (grade.py, measured 2026-09-11); reused verbatim here rather than
# hand-built, since the earlier hand-built attempt below (git history)
# mismatched its own invariant and made coqc spin instead of failing
# fast -- a lesson worth leaving named.
_H_EQ_LEN_TASK = {
    "t": 1,
    "name": "t_hlen_probe",
    "params": [{"name": "a", "type": "seq"}],
    "requires": [],
    "returns": [{"name": "s", "type": "seq"}],
    "body": [
        {"assign": ["s", {"args": [], "op": "seq"}]},
        {"var": {"init": {"args": [{"var": "a"}], "op": "len"},
                 "name": "h", "type": "int"}},
        {"var": {"init": {"int": 0}, "name": "i_v", "type": "int"}},
        {"while": {
            "body": [
                {"assign": ["s", {"args": [{"var": "s"},
                                            {"args": [{"args": [{"var": "a"}, {"var": "i_v"}],
                                                       "op": "at"}], "op": "seq"}],
                            "op": "+"}]},
                {"assign": ["i_v", {"args": [{"var": "i_v"}, {"int": 1}], "op": "+"}]},
            ],
            "cond": {"args": [{"var": "i_v"}, {"var": "h"}], "op": "<"},
            "decreases": {"args": [{"var": "h"}, {"var": "i_v"}], "op": "-"},
            "invariants": [
                {"args": [{"int": 0}, {"var": "i_v"}], "op": "<="},
                {"args": [{"var": "i_v"}, {"var": "h"}], "op": "<="},
                {"args": [{"args": [{"int": 0}, {"var": "i_v"}], "op": "<="},
                          {"args": [{"var": "i_v"}, {"args": [{"var": "a"}], "op": "len"}],
                           "op": "<="}], "op": "and"},
                {"args": [{"args": [{"var": "s"}], "op": "len"}, {"var": "i_v"}], "op": "=="},
                {"forall": {"body": {"args": [{"args": [{"var": "s"}, {"var": "j"}], "op": "at"},
                                              {"args": [{"var": "a"}, {"var": "j"}], "op": "at"}],
                                     "op": "=="},
                            "hi": {"var": "i_v"}, "lo": {"int": 0}, "var": "j"}},
            ],
        }},
    ],
    "ensures": [
        {"args": [{"args": [{"var": "s"}], "op": "len"},
                  {"args": [{"var": "a"}], "op": "len"}], "op": "=="},
        {"forall": {"body": {"args": [{"args": [{"var": "s"}, {"var": "i"}], "op": "at"},
                                      {"args": [{"var": "a"}, {"var": "i"}], "op": "at"}],
                             "op": "=="},
                    "hi": {"args": [{"var": "a"}], "op": "len"}, "lo": {"int": 0}, "var": "i"}},
    ],
}


class HEqualsLenInvariantTest(unittest.TestCase):
    """gen_loop threads `h = a_len` for a prefix int local the loop body
    never reassigns, so the array-index definedness lemma that needs it
    (`0 <= i < a_len` from the guard's `i < h` plus that equality) has
    something to close with."""

    def test_synthetic_invariant_present(self):
        src = lower_rocq.lower(dict(_H_EQ_LEN_TASK), _H_EQ_LEN_TASK["body"])
        # The synthesized `h = a_len` fact (rendered through cx.prop,
        # `a_len` being the standard length name for param `a`) must
        # appear among the def lemmas' own hypotheses; its absence is
        # exactly the bug this test guards against.
        self.assertIn("h = a_len", src)

    @unittest.skipUnless(COQC, "coqc not on PATH")
    def test_compiles(self):
        src = lower_rocq.lower(dict(_H_EQ_LEN_TASK), _H_EQ_LEN_TASK["body"])
        ok, out = _compile(src)
        self.assertTrue(ok, out)


# A loop-free, non-recursive task with a seq return -- swap's own shape.
_SWAP_TASK = {
    "t": 1,
    "name": "t_swap_probe",
    "params": [{"name": "a", "type": "int"}, {"name": "b", "type": "int"}],
    "requires": [],
    "returns": [{"name": "result", "type": "seq"}],
    "body": [
        {"assign": ["result", {"op": "seq", "args": [{"var": "b"}, {"var": "a"}]}]},
    ],
    "ensures": [
        {"op": "==", "args": [{"op": "len", "args": [{"var": "result"}]}, {"int": 2}]},
        {"op": "==", "args": [{"op": "at", "args": [{"var": "result"}, {"int": 0}]},
                               {"var": "b"}]},
        {"op": "==", "args": [{"op": "at", "args": [{"var": "result"}, {"int": 1}]},
                               {"var": "a"}]},
    ],
}


class PlainSeqValueCertificateTest(unittest.TestCase):
    """A loop-free task's WRONG twin (here: returns [a, a] instead of
    [b, a]) gets an actual t_refutation_certificate, not a fallback to
    the plain (unprovable, UNPROVED-reading) theorem."""

    def test_certificate_reaches_value_cert(self):
        task = dict(_SWAP_TASK)
        twin_body, op, w = harness.twin_for(task)
        self.assertIsNotNone(w, "twin_for found no witness for the wrong "
                              "twin -- fixture itself is broken")
        chunk = lower_rocq._try_cert_v1(task, twin_body, w)
        self.assertIsNotNone(
            chunk, "no certificate built: _plain_def's seq-return branch "
            "regressed back to bailing out")
        self.assertIn(lower_rocq.CERT_NAME, chunk)

    @unittest.skipUnless(COQC, "coqc not on PATH")
    def test_certificate_compiles(self):
        task = dict(_SWAP_TASK)
        twin_body, op, w = harness.twin_for(task)
        chunk = lower_rocq._try_cert_v1(task, twin_body, w)
        self.assertIsNotNone(chunk)
        ok, out = _compile(chunk)
        self.assertTrue(ok, out)


class NiaFallbackBoundedTest(unittest.TestCase):
    """`nia` lives ONLY in POST_SF_NIA, wrapped in `timeout 5`, and that
    variant is spliced in only for a task `_has_nonlinear_mul` finds --
    never POST_SF itself, and never bare `nia`. Two measured regressions
    this guards against, both 2026-09-11: bare `nia` sent isPrime's own
    mod-shaped, genuinely unprovable goal into a search long enough to
    blow the file's 180s wall backstop by itself; splicing `timeout 5
    nia` into EVERY task's prelude still did, for isPrime and
    containsSequence, from the ACCUMULATED cost of many bounded attempts
    across one file's many `t_dis` call sites."""

    def test_original_prelude_has_no_nia(self):
        self.assertNotIn("nia", lower_rocq.POST_SF)

    def test_nia_variant_is_bounded(self):
        self.assertIn("timeout 5 nia", lower_rocq.POST_SF_NIA)
        self.assertNotIn("solve [ nia ]", lower_rocq.POST_SF_NIA)

    def test_gate_finds_genuine_nonlinear_mul(self):
        # centeredHexagonalNumber's own shape: `3 * n * (n - 1) + 1`.
        nonlinear_task = {
            "requires": [], "body": [],
            "ensures": [{"op": ">=", "args": [
                {"op": "+", "args": [
                    {"op": "*", "args": [
                        {"op": "*", "args": [{"int": 3}, {"var": "n"}]},
                        {"op": "-", "args": [{"var": "n"}, {"int": 1}]}]},
                    {"int": 1}]},
                {"int": 0}]}],
        }
        self.assertTrue(lower_rocq._has_nonlinear_mul(nonlinear_task))

    def test_gate_ignores_var_times_literal(self):
        linear_task = {
            "requires": [], "body": [],
            "ensures": [{"op": "==", "args": [
                {"op": "*", "args": [{"var": "n"}, {"int": 2}]},
                {"var": "m"}]}],
        }
        self.assertFalse(lower_rocq._has_nonlinear_mul(linear_task))


if __name__ == "__main__":
    unittest.main()
