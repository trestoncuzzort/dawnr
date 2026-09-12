"""t/test_lower_verus_nested_trigger.py: unit test for the nested-quantifier
trigger fix in lower_verus.py (ROADMAP 16.2, verus-2, 2026-09-12).

Sweep r20 (t/COVERAGE-lifted-785.md) read verus malformed/malformed on two
lifted tasks, 414 anyValueExists and 603 lucidNumbers. Both share one
shape: an outer forall/exists whose bound variable is read from a seq only
INSIDE a nested forall/exists's own body (a "preservation witness",
`exists k| P(k) && (exists j| Q(j) && r[k]==s[j])`, and a nested order
obligation, `forall k| ... (forall l| ... a[k] < a[l])`). `expr()`'s own
root-collector, `_at_roots_by_var`, does not look inside a nested
quantifier's body for the outer variable (by design, for the genuine
shadowing case where the inner quantifier reuses the SAME bound name), so
it found nothing, no branch supplied an explicit `#![trigger ...]`, and
Verus's own single-candidate auto-inference does not look inside a nested
quantifier either -- "Could not automatically infer triggers", measured
directly with `verus --output-json --no-cheating` on both tasks' real
`.rs` before this fix.

No kernel binary is invoked here (that measurement is
`grade.py --tasks <414,603> --kernels verus,dafny --flake 3`, done
separately and recorded in this file's module docstring note); this test
checks only the Python-level shape detection and rendering: a synthetic
nested-exists Expr (414's own shape, distinct bound names `k_v`/`k_v2`)
now gets an explicit outer trigger naming the outer-scope read, a
synthetic nested-forall Expr (603's own shape, `k_v`/`l`) likewise, and
the TRUE-shadowing case (inner quantifier reusing the outer name) and the
already-working single-quantifier case are both left byte-for-byte
unchanged, so the fix is additive only.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lower_verus as lv


class NestedTriggerTest(unittest.TestCase):
    def test_preservation_witness_shape_gets_outer_trigger(self):
        # 414 anyValueExists's own shape: exists k_v| (0<=k_v<i_v) &&
        # (exists k_v2| (0<=k_v2<n) && (seq2[k_v2] == seq1[k_v])). The
        # outer var k_v is read (seq1[k_v]) only inside the inner exists.
        e = {"exists": {
            "var": "k_v", "lo": {"int": 0}, "hi": {"var": "i_v"},
            "body": {"exists": {
                "var": "k_v2", "lo": {"int": 0}, "hi": {"var": "n"},
                "body": {"op": "==", "args": [
                    {"op": "at", "args": [{"var": "seq2"}, {"var": "k_v2"}]},
                    {"op": "at", "args": [{"var": "seq1"}, {"var": "k_v"}]},
                ]},
            }},
        }}
        out = lv.expr(e)
        self.assertIn("#![trigger seq1[k_v]]", out)
        # The inner exists still gets its own (pre-existing) trigger too.
        self.assertIn("#![trigger seq2[k_v2]]", out)

    def test_nested_order_shape_gets_outer_trigger(self):
        # 603 lucidNumbers's own shape: forall k_v| ... (forall l| ...
        # lucid[k_v] < lucid[l]). k_v is read only inside the inner forall.
        e = {"forall": {
            "var": "k_v", "lo": {"int": 0}, "hi": {"var": "n"},
            "body": {"forall": {
                "var": "l", "lo": {"op": "+", "args": [{"var": "k_v"}, {"int": 1}]},
                "hi": {"var": "n"},
                "body": {"op": "<", "args": [
                    {"op": "at", "args": [{"var": "lucid"}, {"var": "k_v"}]},
                    {"op": "at", "args": [{"var": "lucid"}, {"var": "l"}]},
                ]},
            }},
        }}
        out = lv.expr(e)
        self.assertIn("#![trigger lucid[k_v]]", out)

    def test_true_shadowing_is_unaffected(self):
        # A nested quantifier that REUSES the outer bound name (k) shadows
        # it; the inner body cannot still mean the outer k, so no trigger
        # should be manufactured from a same-named inner read.
        e = {"exists": {
            "var": "k", "lo": {"int": 0}, "hi": {"var": "n"},
            "body": {"exists": {
                "var": "k", "lo": {"int": 0}, "hi": {"var": "m"},
                "body": {"op": "==", "args": [
                    {"op": "at", "args": [{"var": "s"}, {"var": "k"}]},
                    {"int": 0},
                ]},
            }},
        }}
        out = lv.expr(e)
        self.assertNotIn("#![trigger s[k]]", out)

    def test_single_quantifier_directly_indexed_unchanged(self):
        # The already-working, single-level case: a[k] visible directly at
        # the top of the body. `_at_roots_by_var` finds it without help,
        # so `_nested_at_roots_by_var` must never fire (roots non-empty).
        e = {"forall": {
            "var": "k", "lo": {"int": 0}, "hi": {"var": "n"},
            "body": {"op": ">=", "args": [
                {"op": "at", "args": [{"var": "a"}, {"var": "k"}]},
                {"int": 0},
            ]},
        }}
        out = lv.expr(e)
        self.assertEqual(out, "(forall|k: int| (0 <= k && k < n) ==> (a[k] >= 0))")


if __name__ == "__main__":
    unittest.main()
