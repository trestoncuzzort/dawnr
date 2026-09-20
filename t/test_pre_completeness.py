"""The fourth quadrant: does a requires reject inputs the problem does not define?

The corpus ships no negative inputs, so the problem's own reference solution is
the oracle for its domain: an input the reference refuses to compute is one the
problem does not define. See locallm/FINDINGS-pre-completeness-2026-09-20.md.

The guard is the part worth testing. The first version of this metric scored a
confident 0.000 on answers where the reference could not accept the argument
SHAPE at all (t represents a string as a sequence of ints; the corpus's Python
solution wants a str, so every call raises TypeError). On one answer set, 54 of
97 measurements were that artifact. A refusal only counts when the reference is
known to run on that problem.
"""
import random
import unittest

import spec_check
import surface

PARTIAL = {"code": "def first(s):\n    return s[0]\n"}          # undefined on []
TOTAL = {"code": "def size(s):\n    return len(s)\n"}           # defined everywhere
WRONG_SHAPE = {"code": "def up(s):\n    return s.upper()\n"}    # wants str, gets list: always raises

def entry(rec, fn, expected=("int", 3)):
    return {"fn": fn, "rec": rec,
            "points": [{"args": [["seq", [3, 1, 2]]], "expected": list(expected)}]}

def check(src, rec, fn, n=40):
    return spec_check.check_task(surface.parse(src), entry(rec, fn), n, random.Random(7))

# Each task must COMPUTE what its reference computes, or check_task reports
# "disagrees" and never reaches the quadrant under test.
FIRST_NO_REQ = ("t 1\ntask first(s: seq) returns (r: int)\n"
                "  ensures r == s[0]\n{\n  r := s[0];\n}\n")
FIRST_GUARDED = ("t 1\ntask first(s: seq) returns (r: int)\n  requires len(s) > 0\n"
                 "  ensures r == s[0]\n{\n  r := s[0];\n}\n")
SIZE = ("t 1\ntask size(s: seq) returns (r: int)\n"
        "  ensures r == len(s)\n{\n  r := len(s);\n}\n")
UP = ("t 1\ntask up(s: seq) returns (r: int)\n"
      "  ensures r == len(s)\n{\n  r := len(s);\n}\n")


class PreCompletenessTests(unittest.TestCase):
    def test_a_missing_precondition_is_pre_incomplete(self):
        r = check(FIRST_NO_REQ, PARTIAL, "first")
        self.assertGreater(r["domain_probes"], 0, "the reference should refuse the empty sequence")
        self.assertEqual(r["pre_completeness"], 0.0)
        self.assertTrue(r["pre_incomplete"])
        self.assertIn("domain_witness", r)

    def test_a_precondition_that_excludes_it_is_pre_complete(self):
        r = check(FIRST_GUARDED, PARTIAL, "first")
        self.assertGreater(r["domain_probes"], 0)
        self.assertEqual(r["pre_completeness"], 1.0)
        self.assertFalse(r["pre_incomplete"])

    def test_a_total_problem_reports_nothing_rather_than_a_perfect_score(self):
        """No boundary to find is not the same as finding the boundary handled."""
        r = check(SIZE, TOTAL, "size")
        self.assertNotIn("pre_completeness", r)
        self.assertNotIn("pre_completeness_unmeasurable", r)

    def test_a_reference_that_never_runs_is_refused_not_scored(self):
        """The artifact that made the first version of this wrong."""
        r = check(UP, WRONG_SHAPE, "up")
        self.assertNotIn("pre_completeness", r,
                         "a reference that never ran must not produce a score")
        self.assertEqual(r.get("pre_completeness_unmeasurable"), "reference never ran")

    def test_the_existing_verdict_is_untouched_either_way(self):
        """Adding the quadrant must not move status or draws."""
        for src, rec, fn in ((FIRST_NO_REQ, PARTIAL, "first"),
                             (FIRST_GUARDED, PARTIAL, "first")):
            r = check(src, rec, fn)
            self.assertEqual(r["status"], "agrees")
            self.assertGreater(r["draws"], 0)


if __name__ == "__main__":
    unittest.main()
