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


# A pair-of-seq return, splitArray's own shape (task_id_262, ROCQ-3,
# 2026-09-12): `r := (firstPart, secondPart)`, both components seq-typed.
_PAIR_SEQ_TASK = {
    "t": 1,
    "name": "t_pairseq_probe",
    "params": [{"name": "arr", "type": "seq"}, {"name": "l", "type": "int"}],
    "requires": [
        {"op": "<=", "args": [{"int": 0}, {"var": "l"}]},
        {"op": "<=", "args": [{"var": "l"}, {"op": "len", "args": [{"var": "arr"}]}]},
    ],
    "returns": [{"name": "r", "type": {"pair": ["seq", "seq"]}}],
    "body": [
        {"var": {"init": {"op": "slice", "args": [{"var": "arr"}, {"int": 0}, {"var": "l"}]},
                 "name": "firstPart", "type": "seq"}},
        {"var": {"init": {"op": "slice", "args": [
            {"var": "arr"}, {"var": "l"}, {"op": "len", "args": [{"var": "arr"}]}]},
                 "name": "secondPart", "type": "seq"}},
        {"assign": ["r", {"op": "pair", "args": [{"var": "firstPart"}, {"var": "secondPart"}]}]},
    ],
    "ensures": [
        {"op": "==", "args": [{"op": "len", "args": [{"op": "fst", "args": [{"var": "r"}]}]},
                               {"var": "l"}]},
        {"op": "==", "args": [{"op": "len", "args": [{"op": "snd", "args": [{"var": "r"}]}]},
                               {"op": "-", "args": [{"op": "len", "args": [{"var": "arr"}]},
                                                     {"var": "l"}]}]},
    ],
}


class PairOfSeqComponentTest(unittest.TestCase):
    """`comp_term`'s seq branch used to abstain outright (`pair_comp_ty`
    already gave a seq pair COMPONENT a Coq type, `((Z -> Z) * Z)`, but
    nothing built a TERM of it): a `pair` literal with a seq component
    (splitArray's `r := (firstPart, secondPart)`, task_id_262) hit
    `NotImplementedError: a pair component of type seq is refused` before
    ever reaching a proof attempt. Fixed by rendering the component as
    `(fn, len)`, the same (function, length) pair `seq_fn` already reads
    back out of a pair projection (ROADMAP 13.4's own `fst`/`snd` case)."""

    def test_lowers_without_abstain(self):
        src = lower_rocq.lower(dict(_PAIR_SEQ_TASK), _PAIR_SEQ_TASK["body"])
        self.assertIn("t_pairseq_probe_t_spec", src)

    @unittest.skipUnless(COQC, "coqc not on PATH")
    def test_compiles(self):
        src = lower_rocq.lower(dict(_PAIR_SEQ_TASK), _PAIR_SEQ_TASK["body"])
        ok, out = _compile(src)
        self.assertTrue(ok, out)

    def test_refutation_certificate_reaches_a_wrong_twin(self):
        # off-by-one twin: swap firstPart/secondPart's own slice bounds
        # so the pair's components land in the wrong lengths.
        task = dict(_PAIR_SEQ_TASK)
        twin_body, op, w = harness.twin_for(task)
        if w is None:
            self.skipTest("harness found no witness for this task's twin "
                          "ladder (not this fix's concern)")
        chunk = lower_rocq._try_cert_v1(task, twin_body, w)
        self.assertIsNotNone(
            chunk, "no certificate built for the pair-of-seq twin: "
            "comp_term's seq branch regressed back to abstaining")


# `t_v`, tetrahedralNumber's own return name (task_id_80, ROCQ-3,
# 2026-09-12): collides with this file's own `t_`-prefixed certificate/
# tactic namespace, caught by `_ck` (RESERVED/prefix/suffix check) inside
# `Ctx.__init__`, reached only if the identifier survives `lower()`'s own
# `t_names.sanitize` call unrenamed -- which it did, since
# `t_names.KEYWORDS["rocq"]` is Rocq's own reserved-word list, not this
# file's private `t_`/`sf_`/`_len` convention.
_TCOLLISION_TASK = {
    "t": 1,
    "name": "t_tv_probe",
    "params": [{"name": "n", "type": "int"}],
    "requires": [{"op": "<=", "args": [{"int": 0}, {"var": "n"}]}],
    "returns": [{"name": "t_v", "type": "int"}],
    "body": [
        {"assign": ["t_v", {"op": "div", "args": [
            {"op": "*", "args": [
                {"op": "*", "args": [{"var": "n"},
                                     {"op": "+", "args": [{"var": "n"}, {"int": 1}]}]},
                {"op": "+", "args": [{"var": "n"}, {"int": 2}]}]},
            {"int": 6}]}]},
    ],
    "ensures": [
        {"op": "==", "args": [{"var": "t_v"}, {"op": "div", "args": [
            {"op": "*", "args": [
                {"op": "*", "args": [{"var": "n"},
                                     {"op": "+", "args": [{"var": "n"}, {"int": 1}]}]},
                {"op": "+", "args": [{"var": "n"}, {"int": 2}]}]},
            {"int": 6}]}]},
    ],
}


class TPrefixCollisionRenameTest(unittest.TestCase):
    """A user identifier spelled `t_v` (or any other name `_ck` would
    refuse: `t_`/`sf_`-prefixed, `_len`-suffixed, or in `RESERVED`) is
    renamed away by `lower()`'s own `t_names.sanitize` call, the same
    rename mechanism a `t_names.KEYWORDS["rocq"]` collision already gets,
    BEFORE `Ctx.__init__`'s `_ck` ever sees it -- so lowering the task
    below no longer raises, and the rename is recorded in the emitted
    source's own `t renames:` comment."""

    def test_lowers_without_abstain(self):
        # lower() raising NotImplementedError here (the pre-fix behavior)
        # would fail this test outright; reaching the assert is the point.
        src = lower_rocq.lower(dict(_TCOLLISION_TASK), _TCOLLISION_TASK["body"])
        self.assertIn("t_tv_probe_t_spec", src)

    def test_rename_recorded_in_comment(self):
        src = lower_rocq.lower(dict(_TCOLLISION_TASK), _TCOLLISION_TASK["body"])
        # The task's own name (`t_tv_probe`) also starts with `t_` and is
        # renamed too (an honest, harmless side effect of the same rule,
        # not this test's concern); only the RETURN's rename is checked.
        self.assertIn("t_v -> tn_t_v", src)

    @unittest.skipUnless(COQC, "coqc not on PATH")
    def test_compiles(self):
        src = lower_rocq.lower(dict(_TCOLLISION_TASK), _TCOLLISION_TASK["body"])
        ok, out = _compile(src)
        self.assertTrue(ok, out)


class NoApplicableTacticIsUnprovedTest(unittest.TestCase):
    """ROCQ-4, 2026-09-12 (ROADMAP 16.2's rocq item, sumOfCommonDivisors's
    own real side): `verifiers/rocq.py` classified a nonzero-exit coqc run
    as MALFORMED whenever its output matched neither `UNPROVED_MARKS` nor
    `MALFORMED_MARKS` -- the catch-all `else` two lines under the
    `MALFORMED_MARKS` check. `Error: No applicable tactic.` (a `match goal
    with` -- here, inside a `first [...]` combinator built exactly like
    task_id_126 SumOfCommonDivisors's own `_loop_spec` proof -- that finds
    no matching clause on the live goal) fell into that catch-all: measured
    on task_id_126's own real side, real=malformed, though the file parses
    and resolves fine and only a LATER tactic script ran out of applicable
    branches, the same "stopped without a countermodel" event `UNPROVED_
    MARKS`'s other four strings already name. Fixed by adding it to
    `UNPROVED_MARKS`. This test reproduces the exact message directly
    (Rocq 9.2, standalone probe): `first [ t1 | t2 | ... ]` with every
    alternative failing and NO explicit `fail "msg"` on any of them
    raises `Error: No applicable tactic.` verbatim -- the shape
    task_id_126's own `_loop_spec` combines a `first` around, one branch
    of which itself contains a `match goal with` that can raise the same
    way before the designed trailing `fail 1 "unsolved..."` is ever
    reached."""

    SRC = (
        "Theorem t_unit_spec : True.\n"
        "Proof.\n"
        "  first [ discriminate | congruence ].\n"
        "Qed.\n")

    @unittest.skipUnless(COQC, "coqc not on PATH")
    def test_reads_unproved_not_malformed(self):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from verifiers import rocq as rocq_backend
        from verifiers import Outcome
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "t_unit_probe.v"
            p.write_text(self.SRC, encoding="utf-8")
            r = rocq_backend.verify(p)
        self.assertEqual(r.outcome, Outcome.UNPROVED, r.error)
        self.assertIn("No applicable tactic", r.error)


class NestedAndMultipleLoops(unittest.TestCase):
    """ROADMAP WS-20 move 1, 2026-09-18: the two loop shapes `find_while`
    used to refuse outright -- a loop nested inside a loop, and two or
    more loops in one body -- now lower through `gen_loops` (lower_rocq.py
    has the design note). `has_duplicate` is the committed task this was
    built for; it read `ABSTAIN: rocq lowering: nested loops are not
    lowered yet` before, and real=verified / twin=refuted after (measured
    directly, and in `run_par.py --kernels rocq` over `t/tasks`).

    The two synthetic probes below are the shapes has_duplicate does NOT
    cover and that measurement therefore has to add: two SEQUENTIAL loops
    in one body, and a THREE-deep nest. The three-deep one is not
    decoration -- it is the probe that found the frame-substitution bug
    (`_DECOMP`'s own dated note: a middle loop whose body leaves the
    outer index alone states `i' = i` in its conclusion while its own
    induction hypothesis offers `i' = <the called loop's rebound name>`,
    and `apply IH` could not unify the two until the rebound names are
    `subst`ed). has_duplicate could never have found it: its outer body
    assigns every state slot it has, so its frame list is empty."""

    NESTED = """t 1
gate loops
task t_nest_probe(s: seq) returns (r: bool)
  ensures r ==> (exists i in [0, len(s)) . exists j in [0, len(s)) . i < j and s[i] == s[j])
{
  r := false;
  var i: int := 0;
  while i < len(s) and not r
    invariant i >= 0 and i <= len(s)
    invariant r ==> (exists a in [0, len(s)) . exists b in [0, len(s)) . a < b and s[a] == s[b])
    decreases len(s) - i
  {
    var j: int := i + 1;
    while j < len(s) and not r
      invariant i >= 0 and i < len(s)
      invariant j >= i + 1 and j <= len(s)
      invariant r ==> (exists a in [0, len(s)) . exists b in [0, len(s)) . a < b and s[a] == s[b])
      decreases len(s) - j
    {
      if s[i] == s[j] {
        r := true;
      } else {
      }
      j := j + 1;
    }
    i := i + 1;
  }
}
"""

    TWO = """t 1
gate loops
task t_two_probe(n: int) returns (r: int)
  requires n >= 0
  ensures r == 2 * n
{
  r := 0;
  var i: int := 0;
  while i < n
    invariant i >= 0 and i <= n
    invariant r == i
    decreases n - i
  {
    r := r + 1;
    i := i + 1;
  }
  var k: int := 0;
  while k < n
    invariant k >= 0 and k <= n
    invariant r == n + k
    decreases n - k
  {
    r := r + 1;
    k := k + 1;
  }
}
"""

    TRIPLE = """t 1
gate loops
task t_triple_probe(n: int) returns (r: int)
  requires n >= 0
  ensures r >= 0
{
  r := 0;
  var i: int := 0;
  while i < n
    invariant i >= 0 and i <= n
    invariant r >= 0
    decreases n - i
  {
    var j: int := 0;
    while j < n
      invariant j >= 0 and j <= n
      invariant r >= 0
      decreases n - j
    {
      var k: int := 0;
      while k < n
        invariant k >= 0 and k <= n
        invariant r >= 0
        decreases n - k
      {
        r := r + 1;
        k := k + 1;
      }
      j := j + 1;
    }
    i := i + 1;
  }
}
"""

    SINGLE = """t 1
gate loops
task t_single_probe(n: int) returns (r: int)
  requires n >= 0
  ensures r == n
{
  r := 0;
  var i: int := 0;
  while i < n
    invariant i >= 0 and i <= n
    invariant r == i
    decreases n - i
  {
    r := r + 1;
    i := i + 1;
  }
}
"""

    @staticmethod
    def _task(src: str) -> dict:
        import tasks_io
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "probe.t"
            p.write_text(src, encoding="utf-8")
            return tasks_io.load_task(p)

    def _lower(self, src: str) -> str:
        task = self._task(src)
        return lower_rocq.lower(task, task["body"])

    # ---- the shapes that now lower -----------------------------------
    def test_nested_emits_one_fixpoint_and_one_spec_per_loop(self):
        out = self._lower(self.NESTED)
        for k in (0, 1):
            self.assertIn(f"Fixpoint t_nest_probe_loop{k} ", out)
            self.assertIn(f"Lemma t_nest_probe_loop{k}_spec :", out)
        self.assertNotIn("t_nest_probe_loop2", out)
        # the inner loop is CALLED, once, through a `let` -- never
        # inlined or unrolled (the 27.7 GB hazard this file's history
        # names). One occurrence in the outer Fixpoint body, plus its own
        # definition/lemma sites.
        body = out.split("Fixpoint t_nest_probe_loop0 ")[1].split("end.")[0]
        self.assertEqual(body.count("t_nest_probe_loop1 "), 1)
        self.assertIn("let '(", body)

    def test_two_sequential_loops_chain_their_lets(self):
        out = self._lower(self.TWO)
        for k in (0, 1):
            self.assertIn(f"Fixpoint t_two_probe_loop{k} ", out)
        defn = out.split("Definition t_two_probe_t ")[1].split(".\n\n")[0]
        self.assertEqual(defn.count("t_two_probe_loop0 "), 1)
        self.assertEqual(defn.count("t_two_probe_loop1 "), 1)

    def test_three_deep_nest_lowers(self):
        out = self._lower(self.TRIPLE)
        for k in (0, 1, 2):
            self.assertIn(f"Fixpoint t_triple_probe_loop{k} ", out)

    def test_no_axioms_anywhere(self):
        """`Admitted`, `admit` and axioms are forbidden outright: a
        lowering that cannot express a shape abstains, it never leaves a
        hole a kernel would read as a proof."""
        for src in (self.NESTED, self.TWO, self.TRIPLE):
            out = self._lower(src)
            # substrings, not words: the PRELUDE's own prose contains
            # "admits", so the check is on the TACTIC/COMMAND spellings.
            for bad in ("Admitted", " admit.", " admit;", " admit ",
                        "Axiom ", "Parameter ", "Hypothesis "):
                self.assertNotIn(bad, out, bad)
            self.assertIn("Print Assumptions ", out)

    # ---- the shapes that still abstain, by name ----------------------
    def test_return_inside_nested_loops_abstains(self):
        """gen_loop's early exit turns a loop's result into a `(state,
        returned?)` pair and its conclusion into a disjunction;
        propagating one OUT of a CALLED loop through its caller's state
        tuple is a second design this wave did not build, so it abstains
        by name rather than emitting something that verifies."""
        src = self.NESTED.replace("        r := true;", "        return true;")
        self.assertIn("return true;", src)
        with self.assertRaises(NotImplementedError) as cm:
            self._lower(src)
        self.assertIn("return", str(cm.exception))

    def test_loop_under_a_conditional_still_abstains_at_depth(self):
        """`find_while`'s own pre-existing refusal, now checked at every
        depth rather than only the top level: the general path admits a
        loop inside a loop BODY, so a loop inside an `if` inside a loop
        body would otherwise have reached `exec_straight`'s bare
        AssertionError -- a crash, not the named abstain this file owes."""
        src = """t 1
gate loops
task t_ifloop_probe(n: int) returns (r: int)
  requires n >= 0
  ensures r >= 0
{
  r := 0;
  var i: int := 0;
  while i < n
    invariant i >= 0 and i <= n
    invariant r >= 0
    decreases n - i
  {
    if n > 0 {
      var k: int := 0;
      while k < n
        invariant k >= 0 and k <= n
        invariant r >= 0
        decreases n - k
      {
        r := r + 1;
        k := k + 1;
      }
    } else {
    }
    i := i + 1;
  }
}
"""
        task = self._task(src)
        with self.assertRaises(NotImplementedError) as cm:
            lower_rocq.lower(task, task["body"])
        self.assertIn("conditional", str(cm.exception))

    # ---- the path that must NOT have moved ---------------------------
    def test_one_flat_loop_still_takes_the_old_path(self):
        """A single top-level loop with nothing nested still goes through
        `gen_loop`, whose Fixpoint is `{name}_loop`, unnumbered. This is
        the whole regression bar for the change: every task committed
        before 2026-09-18 lowers byte-identically, and the numbered
        `_loop0` naming is the general path's own tell."""
        out = self._lower(self.SINGLE)
        self.assertIn("Fixpoint t_single_probe_loop (fuel : nat)", out)
        self.assertNotIn("t_single_probe_loop0", out)
        self.assertNotIn("Ltac t_gwit", out)

    # ---- the only positive evidence this kernel accepts ---------------
    @unittest.skipUnless(COQC, "coqc not on PATH")
    def test_coqc_accepts_all_three_shapes(self):
        for src in (self.NESTED, self.TWO, self.TRIPLE):
            ok, log = _compile(self._lower(src))
            self.assertTrue(ok, log[-3000:])


if __name__ == "__main__":
    unittest.main()
