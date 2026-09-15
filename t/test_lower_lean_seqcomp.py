"""t/test_lower_lean_seqcomp.py: unit tests for lower_lean.py's 2026-09-11
ROADMAP 16.2 additions (key lean-seqcomp): the nonlinear sign bridge
(`_mul_sign_pairs`, `_is_affine`, `_sign_compare_operands`/
`_resolve_to_body_expr`) and the composed seq-bridge shape detectors
(`_has_seq_update_chain`, `_has_seq_append_of_slice`).

Pure-Python unit tests over `Lower.__init__`/`_mul_sign_pairs` -- no lean
binary invoked here (that is what t/grade.py's kernel calls are for);
these tests catch a regression in the DETECTION/GUARD logic itself, the
exact class of bug this wave's own two caught-and-fixed regressions
(remainder's `(x/y)*y`, cubeVolume's `(size*size)*size`) came from: an
over-eager detector emitting a lemma for a task that either did not need
one, or whose factors were not the affine shape the case-split's own
`exfalso; omega` leaves can actually decide.

Run: python3 t/test_lower_lean_seqcomp.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lower_lean


def _task(name, params, ensures, body, requires=None, ret_type="int"):
    return {
        "t": 0,
        "name": name,
        "params": params,
        "returns": [{"name": "result", "type": ret_type}],
        "requires": requires or [],
        "ensures": ensures,
        "body": body,
    }


class MulSignPairsTest(unittest.TestCase):
    def test_fires_on_sign_comparison_over_affine_product(self):
        # centeredHexagonalNumber's own shape: result := 3*n*(n-1)+1,
        # ensures result >= 0 (a real sign comparison against 0).
        task = _task(
            "hexnum",
            [{"name": "n", "type": "int"}],
            [{"op": ">=", "args": [{"var": "result"}, {"int": 0}]}],
            [{"assign": ["result", {
                "op": "+",
                "args": [
                    {"op": "*", "args": [
                        {"op": "*", "args": [{"int": 3}, {"var": "n"}]},
                        {"op": "-", "args": [{"var": "n"}, {"int": 1}]}]},
                    {"int": 1}]}]}],
            requires=[{"op": ">=", "args": [{"var": "n"}, {"int": 0}]}],
        )
        lw = lower_lean.Lower(task, task["body"])
        pairs = lw._mul_sign_pairs()
        self.assertEqual(len(pairs), 1)
        a, b = pairs[0]
        self.assertIn("n", a)
        self.assertIn("n", b)

    def test_silent_on_equality_only_ensures(self):
        # cubeVolume's own shape (REGRESSION #2, 2026-09-11): a product
        # appears in the body, but ensures is EQUALITY only -- no `>=`/
        # `<=`/`>`/`<` node anywhere, so there is no sign obligation to
        # bridge and no lemma should be emitted (the one that was, before
        # this guard, broke this exact task: `(size*size)*size`'s own
        # inner factor is not affine, and the emitted lemma's own
        # `exfalso; omega` leaf could not close, sorryAx-tainting the
        # whole file).
        task = _task(
            "cubevol",
            [{"name": "size", "type": "int"}],
            [{"op": "==", "args": [
                {"var": "result"},
                {"op": "*", "args": [
                    {"op": "*", "args": [{"var": "size"}, {"var": "size"}]},
                    {"var": "size"}]}]}],
            [{"assign": ["result", {
                "op": "*", "args": [
                    {"op": "*", "args": [{"var": "size"}, {"var": "size"}]},
                    {"var": "size"}]}]}],
            requires=[{"op": ">", "args": [{"var": "size"}, {"int": 0}]}],
        )
        lw = lower_lean.Lower(task, task["body"])
        self.assertEqual(lw._mul_sign_pairs(), [])

    def test_silent_on_nonaffine_outer_factor(self):
        # A synthetic sign-comparison over `(size * size) * size`
        # (cubeVolume's REGRESSION #2 shape): the OUTER pair, one factor
        # itself nonlinear (`size * size`), must never be collected --
        # omega cannot relate a squared atom's sign to its own base
        # variable, so a lemma for THAT pair would be the same shape of
        # failure cubeVolume's `mulsign_1` was. The INNER `size * size`
        # sub-pair (both factors bare, identical vars) may legitimately
        # still appear -- `0 <= size * size` is always true and the
        # case-split's own leaves close it trivially (`hAp`/`hBp` on the
        # SAME variable can never actually disagree, so the "opposite
        # sign" branches are immediate `omega` contradictions) -- this
        # test only asserts the unprovable OUTER pair is absent.
        task = _task(
            "sq",
            [{"name": "size", "type": "int"}],
            [{"op": ">=", "args": [{"var": "result"}, {"int": 0}]}],
            [{"assign": ["result", {
                "op": "*", "args": [
                    {"op": "*", "args": [{"var": "size"}, {"var": "size"}]},
                    {"var": "size"}]}]}],
        )
        lw = lower_lean.Lower(task, task["body"])
        for a, b in lw._mul_sign_pairs():
            self.assertNotIn("*", a)
            self.assertNotIn("*", b)

    def test_silent_on_division(self):
        # remainder's own shape (REGRESSION #1, 2026-09-11): `r >= 0`
        # resolves to body's `r := x % y`, no `*` node in sight at all,
        # so no pair -- and even if a `*` involving a `/`-built operand
        # appeared, `_is_affine` (no `/`/`%` in its allowed op set)
        # would refuse it independently.
        task = _task(
            "remainder_like",
            [{"name": "x", "type": "int"}, {"name": "y", "type": "int"}],
            [{"op": ">=", "args": [{"var": "result"}, {"int": 0}]}],
            [{"assign": ["result", {"op": "mod",
                                    "args": [{"var": "x"}, {"var": "y"}]}]}],
            requires=[{"op": "!=", "args": [{"var": "y"}, {"int": 0}]}],
        )
        lw = lower_lean.Lower(task, task["body"])
        self.assertEqual(lw._mul_sign_pairs(), [])


class SeqComposedDetectionTest(unittest.TestCase):
    def _seq_task(self, name, params, ensures, body):
        t = _task(name, params, ensures, body, ret_type="seq")
        t["returns"] = [{"name": "result", "type": "seq"}]
        return t

    def test_update_chain_detected(self):
        # swapFirstAndLast's own shape: a_out reassigned via `update`
        # twice in sequence, each self-referencing.
        body = [
            {"assign": ["a_out", {"var": "a"}]},
            {"assign": ["a_out", {"op": "update", "args": [
                {"var": "a_out"}, {"int": 0}, {"int": 1}]}]},
            {"assign": ["a_out", {"op": "update", "args": [
                {"var": "a_out"}, {"int": 1}, {"int": 2}]}]},
        ]
        task = self._seq_task(
            "swaplike",
            [{"name": "a", "type": "seq"}],
            [{"op": "==", "args": [{"var": "result"}, {"var": "a_out"}]}],
            body)
        lw = lower_lean.Lower(task, body)
        self.assertTrue(lw.seq_composed_update2)

    def test_single_update_not_flagged(self):
        body = [
            {"assign": ["a_out", {"op": "update", "args": [
                {"var": "a"}, {"int": 0}, {"int": 1}]}]},
        ]
        task = self._seq_task(
            "singleupdate",
            [{"name": "a", "type": "seq"}],
            [{"op": "==", "args": [{"var": "result"}, {"var": "a_out"}]}],
            body)
        lw = lower_lean.Lower(task, body)
        self.assertFalse(lw.seq_composed_update2)

    def test_append_of_slices_detected(self):
        # splitArray's own shape: two locals each initialized to a
        # slice, then concatenated.
        body = [
            {"var": {"name": "firstPart", "type": "seq", "init": {
                "op": "slice", "args": [
                    {"var": "arr"}, {"int": 0}, {"var": "l"}]}}},
            {"var": {"name": "secondPart", "type": "seq", "init": {
                "op": "slice", "args": [
                    {"var": "arr"}, {"var": "l"},
                    {"op": "len", "args": [{"var": "arr"}]}]}}},
            {"assign": ["result", {"op": "+", "args": [
                {"var": "firstPart"}, {"var": "secondPart"}]}]},
        ]
        task = self._seq_task(
            "splitlike",
            [{"name": "arr", "type": "seq"}, {"name": "l", "type": "int"}],
            [{"op": "==", "args": [{"var": "result"}, {"var": "arr"}]}],
            body)
        lw = lower_lean.Lower(task, body)
        self.assertTrue(lw.seq_composed_append_slice)

    def test_append_of_bare_seqs_not_flagged(self):
        body = [
            {"assign": ["result", {"op": "+", "args": [
                {"var": "a"}, {"var": "b"}]}]},
        ]
        task = self._seq_task(
            "appendlike",
            [{"name": "a", "type": "seq"}, {"name": "b", "type": "seq"}],
            [{"op": "==", "args": [{"var": "result"}, {"var": "a"}]}],
            body)
        lw = lower_lean.Lower(task, body)
        self.assertFalse(lw.seq_composed_append_slice)


class SeqUpdate2ScriptTest(unittest.TestCase):
    """2026-09-12, ROADMAP 16.2, lean's own item: `_seq_update2_script`
    (the per-site codegen closing the ITE-SPLIT GAP's own residual --
    `grind only [t_seq_update2_get, ..._hi, ..._mid, ..._lo]` cites the
    composed lemma but does not itself split the ite the general form
    leaves, measured directly on task_id_591/625). Pure-Python checks on
    the emitted TEXT (the `.lean` file itself is exercised by t/grade.py,
    not here); these catch a regression in the GATE (None exactly when
    `seq_composed_update2` is False, unchanged for every other task) and
    in the script's own required pieces (never `grind`'s own e-matching
    alone, never `split_ifs` -- unavailable core-Lean-only, measured
    directly, 2026-09-12 -- and the new `t_seq_index_congr` bridge)."""

    def _seq_task(self, name, params, ensures, body):
        t = _task(name, params, ensures, body, ret_type="seq")
        t["returns"] = [{"name": "result", "type": "seq"}]
        return t

    def _swap_task(self):
        # swapFirstAndLast's own shape (task_id_591/625).
        body = [
            {"assign": ["a_out", {"var": "a"}]},
            {"var": {"init": {"op": "at", "args": [
                {"var": "a_out"}, {"int": 0}]},
                "name": "temp", "type": "int"}},
            {"assign": ["a_out", {"op": "update", "args": [
                {"var": "a_out"}, {"int": 0},
                {"op": "at", "args": [{"var": "a_out"}, {"op": "-", "args": [
                    {"op": "len", "args": [{"var": "a_out"}]},
                    {"int": 1}]}]}]}]},
            {"assign": ["a_out", {"op": "update", "args": [
                {"var": "a_out"}, {"op": "-", "args": [
                    {"op": "len", "args": [{"var": "a_out"}]},
                    {"int": 1}]},
                {"var": "temp"}]}]},
        ]
        return self._seq_task(
            "swaplike",
            [{"name": "a", "type": "seq"}],
            [{"op": "==", "args": [{"var": "result"}, {"var": "a_out"}]}],
            body)

    def test_none_when_gate_false(self):
        body = [
            {"assign": ["a_out", {"op": "update", "args": [
                {"var": "a"}, {"int": 0}, {"int": 1}]}]},
        ]
        task = self._seq_task(
            "singleupdate",
            [{"name": "a", "type": "seq"}],
            [{"op": "==", "args": [{"var": "result"}, {"var": "a_out"}]}],
            body)
        lw = lower_lean.Lower(task, body)
        self.assertIsNone(lw._seq_update2_script())

    def test_script_present_and_shaped_when_gate_true(self):
        task = self._swap_task()
        lw = lower_lean.Lower(task, task["body"])
        self.assertTrue(lw.seq_composed_update2)
        script = lw._seq_update2_script()
        self.assertIsNotNone(script)
        # the unconditional lemma (simp's own e-matching supplies base/
        # i1/v1/i2/v2/j from the goal, never a Python-threaded term),
        # never the ite-carrying corollaries (those stay `_seq_hints`'s
        # own `grind only` fallback, unchanged) and the new bridge.
        self.assertIn("t_seq_update2_get]", script)
        self.assertNotIn("t_seq_update2_get_hi", script)
        self.assertIn("t_seq_index_congr", script)
        # `split`, never `split_ifs` (unavailable, core Lean only,
        # measured 2026-09-12: "unknown tactic").
        self.assertIn("split", script)
        self.assertNotIn("split_ifs", script)
        # every step chained by `<;>`, never a bare `;` (measured,
        # 2026-09-12: a bare `;` after `repeat'` here makes the whole
        # tactic silently a no-op, no error, goal left unchanged).
        self.assertNotIn("; all_goals", script)

    def test_close_tries_the_script_before_grind_only_fallback(self):
        task = self._swap_task()
        lw = lower_lean.Lower(task, task["body"])
        closed = lw._close([task["ensures"], task["body"]], {},
                           lw.types, "grind")
        script = lw._seq_update2_script()
        self.assertIn(script, closed)
        self.assertLess(closed.index(script),
                        closed.index("grind only ["))

    def test_emit_seq_helpers_declares_index_congr_bridge(self):
        task = self._swap_task()
        lw = lower_lean.Lower(task, task["body"])
        src = lw.emit_seq_helpers()
        self.assertIn("theorem t_seq_index_congr", src)

    def test_no_change_for_non_composed_seq_task(self):
        # `_close`'s new branch is additive: a plain seq-mut task with no
        # composed update chain sees a byte-identical `grind only [...]`
        # fallback, no new alternative spliced in.
        body = [
            {"assign": ["a_out", {"op": "update", "args": [
                {"var": "a"}, {"int": 0}, {"int": 1}]}]},
        ]
        task = self._seq_task(
            "singleupdate",
            [{"name": "a", "type": "seq"}],
            [{"op": "==", "args": [{"var": "result"}, {"var": "a_out"}]}],
            body)
        lw = lower_lean.Lower(task, body)
        closed = lw._close([task["ensures"], body], {}, lw.types, "grind")
        self.assertEqual(closed,
                         f"first | (grind) | (grind only [{lw._seq_hints()}])")


class SeqAppendReadScriptTest(unittest.TestCase):
    """2026-09-12, ROADMAP 16.2, lean's own item (the append-of-slices
    shape and the three timeouts): `_seq_append_read_script`, the
    `_seq_update2_script` template one level down -- READ-after-`++`/
    slice instead of READ-after-chained-`.set`. Pure-Python checks on
    the emitted TEXT (the `.lean` file itself is exercised by
    `t/grade.py`, not here; see `t/COVERAGE-lifted-785.md`'s
    dafny_synthesis rows for the kernel-checked measurement) -- these
    catch a regression in the GATE (`None` exactly when `self.seq_new`
    is False, unchanged for every other task) and in the two things
    measured to matter for this shape: `Nat.min_def` must NOT appear in
    this method's own hypothesis normalization or its `simp`'s `disch`
    (measured 2026-09-12: `omega` already understands `Nat.min`
    natively -- unfolding it into an `ite` first only gives `omega` an
    opaque atom it cannot split back out of a `disch` goal, the actual
    blocker an earlier version of this method could not get past), and
    `t_seq_ext` is offered only when `self.seq_eq_comp` is set (citing
    an undeclared name is a compile error, not a soft failure)."""

    def _seq_task(self, name, params, ensures, body):
        t = _task(name, params, ensures, body, ret_type="seq")
        t["returns"] = [{"name": "result", "type": "seq"}]
        return t

    def _split_task(self):
        # splitArray's own shape (task_id_262): two locals each a
        # slice of the same base seq, concatenated back into `result`,
        # whose own ensures equates it to the base seq -- a whole-
        # SEQUENCE equality, never an indexed read on its own, so this
        # shape also exercises the `t_seq_ext` opening step. (`result`,
        # not the bare locals, in `ensures`: `self.types` only tracks
        # params + the return, so a raw local there would raise inside
        # `Lower.__init__` on an unrelated pre-existing gap this test
        # is not about.)
        body = [
            {"var": {"name": "firstPart", "type": "seq", "init": {
                "op": "slice", "args": [
                    {"var": "arr"}, {"int": 0}, {"var": "l"}]}}},
            {"var": {"name": "secondPart", "type": "seq", "init": {
                "op": "slice", "args": [
                    {"var": "arr"}, {"var": "l"},
                    {"op": "len", "args": [{"var": "arr"}]}]}}},
            {"assign": ["result", {"op": "+", "args": [
                {"var": "firstPart"}, {"var": "secondPart"}]}]},
        ]
        return self._seq_task(
            "splitlike",
            [{"name": "arr", "type": "seq"}, {"name": "l", "type": "int"}],
            [{"op": "==", "args": [{"var": "result"}, {"var": "arr"}]}],
            body)

    def _bare_append_task(self):
        # a plain `a ++ b` with no slice on either side: `seq_new` fires
        # (some seq literal/concat/slice construct is present) but
        # `seq_composed_append_slice` does not.
        body = [
            {"assign": ["result", {"op": "+", "args": [
                {"var": "a"}, {"var": "b"}]}]},
        ]
        return self._seq_task(
            "appendlike",
            [{"name": "a", "type": "seq"}, {"name": "b", "type": "seq"}],
            [{"op": "==", "args": [
                {"op": "at", "args": [{"var": "result"}, {"int": 0}]},
                {"op": "at", "args": [{"var": "a"}, {"int": 0}]}]}],
            body)

    def test_none_when_not_seq_new(self):
        body = [
            {"assign": ["a_out", {"op": "update", "args": [
                {"var": "a"}, {"int": 0}, {"int": 1}]}]},
        ]
        task = self._seq_task(
            "singleupdate",
            [{"name": "a", "type": "seq"}],
            [{"op": "==", "args": [{"var": "result"}, {"var": "a_out"}]}],
            body)
        lw = lower_lean.Lower(task, body)
        self.assertFalse(lw.seq_new)
        self.assertIsNone(lw._seq_append_read_script())

    def test_script_present_for_bare_append(self):
        task = self._bare_append_task()
        lw = lower_lean.Lower(task, task["body"])
        self.assertTrue(lw.seq_new)
        self.assertFalse(lw.seq_composed_append_slice)
        script = lw._seq_append_read_script()
        self.assertIsNotNone(script)
        self.assertIn("t_seq_append_get", script)
        self.assertIn("t_seq_index_congr", script)
        # no seq-equality conjunct in this task's own ensures -> no
        # `t_seq_ext` opening step offered.
        self.assertNotIn("t_seq_ext", script)

    def test_script_offers_seq_ext_when_seq_eq_comp(self):
        task = self._split_task()
        lw = lower_lean.Lower(task, task["body"])
        self.assertTrue(lw.seq_new)
        self.assertTrue(lw.seq_composed_append_slice)
        self.assertTrue(lw.seq_eq_comp)
        script = lw._seq_append_read_script()
        self.assertIsNotNone(script)
        self.assertIn("apply t_seq_ext", script)
        self.assertIn("t_seq_append_slice2_get", script)

    def test_no_nat_min_def_in_script(self):
        # THE NAT-CAST TRAP (2026-09-12): `Nat.min_def` in this method's
        # own normalization or `disch` manufactures an ite `omega`
        # cannot split back out of a `disch` goal -- measured directly,
        # named in this method's own docstring. `_seq_hints`'s `grind
        # only [...]` fallback keeps citing `Nat.min_def` (a different
        # tactic, `grind`, with the opposite need); this script must not.
        task = self._split_task()
        lw = lower_lean.Lower(task, task["body"])
        script = lw._seq_append_read_script()
        self.assertIsNotNone(script)
        self.assertNotIn("Nat.min_def", script)
        self.assertIn("List.length_take", script)
        self.assertIn("List.length_drop", script)

    def test_index_congr_declared_for_seq_new_alone(self):
        # promoted (2026-09-12) from `seq_composed_update2`-only to
        # `seq_composed_update2 or seq_new`, declared exactly once.
        task = self._bare_append_task()
        lw = lower_lean.Lower(task, task["body"])
        self.assertFalse(lw.seq_composed_update2)
        self.assertTrue(lw.seq_new)
        src = lw.emit_seq_helpers()
        self.assertEqual(src.count("theorem t_seq_index_congr"), 1)

    def test_close_tries_the_script_before_grind_only_fallback(self):
        task = self._split_task()
        lw = lower_lean.Lower(task, task["body"])
        closed = lw._close([task["ensures"], task["body"]], {},
                           lw.types, "grind")
        script = lw._seq_append_read_script()
        self.assertIn(script, closed)
        self.assertLess(closed.index(script),
                        closed.index("grind only ["))

    def test_no_change_for_non_seq_task(self):
        task = _task(
            "plain", [{"name": "x", "type": "int"}],
            [{"op": "==", "args": [{"var": "result"}, {"var": "x"}]}],
            [{"assign": ["result", {"var": "x"}]}])
        lw = lower_lean.Lower(task, task["body"])
        self.assertFalse(lw.seq_new)
        closed = lw._close([task["ensures"], task["body"]], {},
                           lw.types, "grind")
        self.assertEqual(closed, "grind")


class SeqAppendReadScriptDischTest(unittest.TestCase):
    """2026-09-14, ROADMAP 16.2, key lean-seqcomp ("closing the composed
    seq goals"): THE SILENT-DISCH GAP fix. `simp (disch := omega) only
    [t_seq_append_get, ...]` discharges EVERY side condition a cited
    lemma's own instantiation carries -- `hju : j < ((l1++l2).length :
    Int)`, whose `.length` of a `List.take`/`.drop`/`++` term `omega`
    alone cannot see through -- so a bare `omega` disch left the lemma
    UNAPPLIED (`simp` reports "made no progress", measured directly,
    probe240c/f.lean, this session's own scratch probes) rather than
    applied with a wrong answer; 240 replaceLastElement and 586
    splitAndAppend stayed `unproved` at the 2026-09-12 baseline for
    exactly this reason. The fix wraps the length-normalizing `simp
    only [...]` in its own `try` INSIDE the disch (never around the
    whole disch, which would just swallow a genuine failure and hand
    `omega` an unrewritten length term again): a side condition with no
    length term to rewrite (`hj : 0 ≤ j`) sees the `try` no-op and falls
    through to `omega` unchanged; one that does (`hju`) gets the
    rewrite first. These are pure-Python checks on the emitted TEXT --
    the kernel-checked measurement (240/586/262, lean+dafny, flake 3;
    262 held as the standing regression bar named in this method's own
    docstring) lives in t/COVERAGE-lifted-785.md's own dafny_synthesis
    rows and this session's dated docstring note, not here.

    A `| grind` (and a `t_seq_singleton_get` lemma) were ALSO tried at
    this leaf, for 106 appendArrayToSeq's own `_t_loop_spec` residual,
    and REVERTED: two `t/grade.py --kernels lean,dafny --flake 3` runs
    over the byte-identical generated source (240/262 included, neither
    touched by that change) disagreed on 240 and 262 with no code
    change between them (`verified` on one run, `unproved` on the
    next) -- `-DmaxHeartbeats` bounds elaboration STEPS, not which
    steps a run's own `grind` takes to get there, so an extra
    expensive, failure-prone alternative ahead of nothing measurably
    changed which OTHER theorem's own budget ran out first. Asserting
    its ABSENCE here pins that revert against a future reintroduction
    that skips re-measuring the flake."""

    def _seq_task(self, name, params, ensures, body):
        t = _task(name, params, ensures, body, ret_type="seq")
        t["returns"] = [{"name": "result", "type": "seq"}]
        return t

    def _append_task(self):
        body = [
            {"assign": ["result", {"op": "+", "args": [
                {"var": "a"}, {"var": "b"}]}]},
        ]
        return self._seq_task(
            "appendlike",
            [{"name": "a", "type": "seq"}, {"name": "b", "type": "seq"}],
            [{"op": "==", "args": [
                {"op": "at", "args": [{"var": "result"}, {"int": 0}]},
                {"op": "at", "args": [{"var": "a"}, {"int": 0}]}]}],
            body)

    def test_disch_tries_length_normalization_before_omega(self):
        task = self._append_task()
        lw = lower_lean.Lower(task, task["body"])
        script = lw._seq_append_read_script()
        self.assertIsNotNone(script)
        self.assertIn(
            "disch := ((try simp only [List.length_append, "
            "List.length_take, List.length_drop, List.length_cons, "
            "List.length_nil]); omega)", script)

    def test_disch_length_simp_step_itself_is_try_guarded(self):
        # THE regression this fix is for: a bare (non-`try`) length
        # simp inside disch raises "simp made no progress" on a side
        # condition with no length term (`hj : 0 ≤ j`), aborting the
        # `;`-sequenced `omega` that would otherwise have closed it --
        # measured directly, probe240g.lean. The `try` must wrap the
        # `simp only [...]` step alone, not the whole `disch := (...)`.
        task = self._append_task()
        lw = lower_lean.Lower(task, task["body"])
        script = lw._seq_append_read_script()
        self.assertIsNotNone(script)
        self.assertIn("(try simp only [List.length_append", script)

    def test_singleton_get_and_bare_grind_not_reintroduced(self):
        # THE LOOP-PRESERVATION GAP's own `| grind` alternative, and a
        # dedicated `t_seq_singleton_get` lemma, were both tried for
        # 106 appendArrayToSeq's own residual and reverted (measured
        # flaky: 240/262 disagreed run to run with no code change) --
        # pinned absent so a future change does not silently reintroduce
        # the same flake.
        task = self._append_task()
        lw = lower_lean.Lower(task, task["body"])
        script = lw._seq_append_read_script()
        self.assertIsNotNone(script)
        self.assertNotIn("grind", script)
        self.assertNotIn("t_seq_singleton_get", script)
        src = lw.emit_seq_helpers()
        self.assertNotIn("t_seq_singleton_get", src)


if __name__ == "__main__":
    unittest.main()
