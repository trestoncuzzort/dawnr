"""t/test_lower_dafny_trigger.py: unit test for the quantifier-trigger fix
in lower_dafny.py and its BANNED_RE carve-out in verifiers/dafny.py
(ROADMAP 16.2, dafny-576, 2026-09-11).

Sweep r21 (ROADMAP 16.2) read dafny unproved/unproved on lifted task 576,
dafny_synthesis_task_id_576__isSublist, while fstar's 2026-09-12 builder
lowered the SAME task JSON and read verified/refuted there -- so the task
is provable and the gap was dafny's own lowering, not the spec.

Measured directly (`dafny verify` on the r21-sweep .dfy, 2026-09-11):
`dafny verify dafny_synthesis_task_id_576__isSublist.dfy` printed
"2 verified, 0 errors" (the proof itself went through with no fix at all)
but then "Compilation failed because warnings were found and
--allow-warnings is false", because dafny could not find a trigger for
either the ensures's or the loop invariant's `exists j :: ... && sub ==
main_v[j..j+|sub|]` and warned. verifiers/dafny.py's own doc (module
docstring, "exit 2 -- MALFORMED... any warning") maps that warning alone
to an exit-2 verdict, which reads as "unproved" upstream in grade.py's
tally: a prover's caution reported as a broken lowering, the exact
misreport that module's docstring already names for the metamorphic case
(s[j] -> s[(j + 0)] losing a trigger, 2026-09-04).

The fix is two lines of actual behavior, tested here without invoking the
dafny binary (that measurement is `grade.py --tasks <576> --kernels
dafny,verus --flake 3`, done separately and recorded in
CONFORMANCE.md/AGREEMENT.md's own regeneration, not this file):

  1. `lower_dafny.py`'s `_find_trigger_term` walks a quantifier body for
     the first non-boolean `op` application (a `slice`/`at`/function
     term, never `==`, `<`, `and`, ...) that mentions the bound variable,
     and `expr()`'s `forall`/`exists` cases state it as an explicit
     `{:trigger ...}` right after the bound variable's type. Dafny cannot
     pick a trigger out of a bare equality comparing two sequences on its
     own; the `slice` subterm inside that equality is exactly what
     e-matching needs.

  2. `verifiers/dafny.py`'s `BANNED_RE` bans every `{:attr}` pragma
     because most of them (`{:axiom}`, `{:verify false}`, `{:extern}`,
     `{:only}`) can admit an unproved fact or skip an obligation outright.
     `{:trigger ...}` cannot: it only steers which ground terms the SMT
     search matches against, never which obligations get checked, so it
     is named out of the ban while every other attribute spelling stays
     banned -- covered here by asserting the regex's behavior on both a
     `{:trigger ...}` string and a `{:axiom}`/`{:verify false}` string,
     with no dafny binary involved.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lower_dafny as ld
from verifiers.dafny import BANNED_RE


# The isSublist ensures shape (task 576's own JSON, lifted-tasks form):
# exists i in [0, h) :: sub == main_v[i..(i + |sub|)]
ISSUBLIST_EXISTS = {
    "exists": {
        "var": "i",
        "lo": {"int": 0},
        "hi": {"var": "h"},
        "body": {
            "op": "==",
            "args": [
                {"var": "sub"},
                {
                    "op": "slice",
                    "args": [
                        {"var": "main_v"},
                        {"var": "i"},
                        {"op": "+", "args": [{"var": "i"},
                                             {"op": "len", "args": [{"var": "sub"}]}]},
                    ],
                },
            ],
        },
    }
}

# A quantifier whose body never applies an operator to the bound var at
# all (only compares it to bare names/ints): no trigger term exists, and
# none should be invented.
NO_CANDIDATE_FORALL = {
    "forall": {
        "var": "k",
        "lo": {"int": 0},
        "hi": {"var": "n"},
        "body": {"op": "<", "args": [{"var": "k"}, {"var": "n"}]},
    }
}


class FindTriggerTermTest(unittest.TestCase):
    def test_finds_the_slice_subterm(self):
        term = ld._find_trigger_term(ISSUBLIST_EXISTS["exists"]["body"], "i")
        self.assertIsNotNone(term)
        self.assertEqual(term["op"], "slice")

    def test_no_candidate_returns_none(self):
        term = ld._find_trigger_term(NO_CANDIDATE_FORALL["forall"]["body"], "k")
        self.assertIsNone(term)


class ExprEmitsTriggerTest(unittest.TestCase):
    def test_exists_over_slice_equality_gets_explicit_trigger(self):
        out = ld.expr(ISSUBLIST_EXISTS)
        self.assertIn("{:trigger main_v[i..(i + |sub|)]}", out)
        # the trigger sits right after the bound variable's type, before "::"
        self.assertIn("(exists i: int {:trigger main_v[i..(i + |sub|)]} :: ",
                      out)

    def test_forall_over_at_gets_no_trigger(self):
        # 2026-09-12: a quantifier whose candidate term is an index (`at`),
        # not a slice, keeps dafny's own trigger choice (appendArrayToSeq
        # and interleave regressed when every quantifier was annotated).
        e = {"forall": {"var": "k", "lo": {"int": 0}, "hi": {"var": "n"},
             "body": {"op": "==", "args": [{"op": "at", "args": [{"var": "r"}, {"var": "k"}]},
                                            {"op": "at", "args": [{"var": "s"}, {"var": "k"}]}]}}}
        out = ld.expr(e)
        self.assertNotIn("{:trigger", out)

    def test_forall_with_no_candidate_term_gets_no_trigger(self):
        out = ld.expr(NO_CANDIDATE_FORALL)
        self.assertNotIn("{:trigger", out)
        self.assertEqual(out, "(forall k: int :: (0 <= k && k < n) ==> (k < n))")


class BannedReTriggerCarveOutTest(unittest.TestCase):
    def test_trigger_attribute_is_not_banned(self):
        src = "ensures (exists i: int {:trigger main_v[i..(i+1)]} :: true)"
        self.assertEqual(BANNED_RE.findall(src), [])

    def test_axiom_attribute_still_banned(self):
        self.assertTrue(BANNED_RE.search("lemma foo() {:axiom} {}"))

    def test_verify_false_attribute_still_banned(self):
        self.assertTrue(BANNED_RE.search("method m() {:verify false} {}"))

    def test_only_attribute_still_banned(self):
        self.assertTrue(BANNED_RE.search("method m() {:only} {}"))

    def test_trigger_lookalike_word_not_specially_exempted(self):
        # "{:triggerish}" is not the word "trigger" and must still ban --
        # the carve-out is for the exact attribute name, not a prefix.
        self.assertTrue(BANNED_RE.search("method m() {:triggerish} {}"))


if __name__ == "__main__":
    unittest.main()
