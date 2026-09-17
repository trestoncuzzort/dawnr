"""test_lower_dafny_closure.py: regression test for ROADMAP 16.2's
dafny-closure item, 2026-09-14.

Sweep r25 found five newly lifted rows unproved on the dafny real:
dafny-synthesis 412/426/436/554/629, each a closure predicate (isEven,
isOdd, isNegative) called in executable position inside a loop that
appends to its accumulator. Measured directly (see lower_dafny.py's
module docstring and `_seq_membership`'s docstring): the cause is not the
closure predicate call itself but the lifter's `x in someSeq` rewrite,
which always produces the exact shape `exists k :: 0<=k<len(seq) &&
seq[k]==elem`; a generic Dafny quantifier lowering of that shape cannot
reprove a membership witness across `evenList := evenList + [x]`, while
Dafny's own `in` primitive can. `expr`'s `exists` branch now special-cases
that shape to `elem in seq`.

This test lowers each of the five affected records (read from the
read-only lifted corpus) with the CURRENT lower_dafny.py and asks dafny to
verify the real program: it must read "N verified, 0 errors" with N >= 1,
and the generated source must use the native `in` operator (never a raw
`exists ... ==` for a whole-sequence membership check) -- a return to the
generic quantifier lowering for this shape is exactly the regression this
guards against. Skips (not fails) when the lifted corpus or the `dafny`
binary is unavailable, matching every other t test that depends on
external, gitignored, or optional state.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import lower_dafny

LIFTED_DIR = Path(__file__).resolve().parent / "out" / "lifted-tasks"

# (lifted-tasks file stem, predicate name) for the five sweep-r25 rows.
CLOSURE_ROWS = [
    "dafny-synthesis_task_id_412.RemoveOddNumbers",
    "dafny-synthesis_task_id_426.FilterOddNumbers",
    "dafny-synthesis_task_id_436.FindNegativeNumbers",
    "dafny-synthesis_task_id_554.FindOddNumbers",
    "dafny-synthesis_task_id_629.FindEvenNumbers",
]


def _load(stem: str) -> dict | None:
    p = LIFTED_DIR / f"{stem}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


@unittest.skipUnless(LIFTED_DIR.is_dir(), "lifted corpus not present here")
class SeqMembershipLoweringTest(unittest.TestCase):
    """`_seq_membership` matches the lifter's exact `in`-rewrite shape and
    the exists branch in `expr` uses it for whole-sequence membership."""

    def test_matches_whole_sequence_membership(self):
        q = {
            "var": "k",
            "lo": {"int": 0},
            "hi": {"op": "len", "args": [{"var": "arr"}]},
            "body": {
                "op": "==",
                "args": [
                    {"op": "at", "args": [{"var": "arr"}, {"var": "k"}]},
                    {"var": "elem"},
                ],
            },
        }
        mem = lower_dafny._seq_membership(q)
        self.assertIsNotNone(mem)
        seq, elem = mem
        self.assertEqual(seq, {"var": "arr"})
        self.assertEqual(elem, {"var": "elem"})
        lowered = lower_dafny.expr({"exists": q})
        self.assertEqual(lowered, "(elem in arr)")

    def test_flipped_equality_also_matches(self):
        q = {
            "var": "k",
            "lo": {"int": 0},
            "hi": {"op": "len", "args": [{"var": "arr"}]},
            "body": {
                "op": "==",
                "args": [
                    {"var": "elem"},
                    {"op": "at", "args": [{"var": "arr"}, {"var": "k"}]},
                ],
            },
        }
        self.assertEqual(lower_dafny.expr({"exists": q}), "(elem in arr)")

    def test_partial_range_does_not_match(self):
        """lo != 0 (a partial-range read) is left on the generic quantifier
        path: `elem in seq[lo..hi]` would need a fresh `0<=lo<=hi<=|seq|`
        obligation this fix must not introduce."""
        q = {
            "var": "k",
            "lo": {"int": 1},
            "hi": {"op": "len", "args": [{"var": "arr"}]},
            "body": {
                "op": "==",
                "args": [
                    {"op": "at", "args": [{"var": "arr"}, {"var": "k"}]},
                    {"var": "elem"},
                ],
            },
        }
        lowered = lower_dafny.expr({"exists": q})
        self.assertNotIn(" in ", lowered)
        self.assertIn("exists", lowered)

    def test_non_membership_exists_unaffected(self):
        """A comparison that is not an index-equality (`n <= a[k]`, the
        433/567 shape) must still fall through to the generic quantifier
        lowering, unchanged."""
        q = {
            "var": "k",
            "lo": {"int": 0},
            "hi": {"op": "len", "args": [{"var": "a"}]},
            "body": {
                "op": "<=",
                "args": [
                    {"var": "n"},
                    {"op": "at", "args": [{"var": "a"}, {"var": "k"}]},
                ],
            },
        }
        lowered = lower_dafny.expr({"exists": q})
        self.assertIn("exists k: int ::", lowered)
        self.assertNotIn(" in ", lowered)


@unittest.skipUnless(LIFTED_DIR.is_dir(), "lifted corpus not present here")
@unittest.skipUnless(shutil.which("dafny"), "dafny binary not on PATH")
class ClosurePredicateRealVerifiesTest(unittest.TestCase):
    """The real program for each sweep-r25 row verifies, and its source
    uses the native `in` operator rather than a raw membership `exists`."""

    def test_five_rows_verify_and_use_native_in(self):
        for stem in CLOSURE_ROWS:
            task = _load(stem)
            if task is None:
                self.skipTest(f"{stem} not in the lifted corpus")
            with self.subTest(stem=stem):
                src = lower_dafny.lower(task, task["body"])
                self.assertIn(
                    " in ", src,
                    f"{stem}: expected a native `in` membership test, "
                    f"got:\n{src}")
                with tempfile.NamedTemporaryFile(
                        suffix=".dfy", mode="w", encoding="utf-8",
                        delete=False) as f:
                    f.write(src)
                    dfy_path = f.name
                try:
                    p = subprocess.run(
                        ["dafny", "verify", "--resource-limit", "500000",
                         "--log-format", "text", dfy_path],
                        capture_output=True, text=True, timeout=120)
                finally:
                    Path(dfy_path).unlink(missing_ok=True)
                out = p.stdout + p.stderr
                self.assertRegex(
                    out, r"finished with [1-9]\d* verified, 0 error",
                    f"{stem}: dafny did not verify the real program:\n{out}")


if __name__ == "__main__":
    unittest.main()
