"""t/student_rows.py (2026-10-01): "specification given, write the body" rows, the vericoding
setting (arXiv:2509.22908). The question keeps the contract and drops the body; training rows come
from the train side of the corpus split only; a held-out document that shares a problem, a program
or a specification with training is removed and counted by reason. No kernel."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import student_rows  # noqa: E402
import surface  # noqa: E402

DOC = ("Problem: Count.\nSignature: f(seq) -> int\nt 1\ngate loops\ntask mbpp_8__f(s: seq) returns (r: int)\n"
       "  ensures r == len(s)\n{\n  r := 0;\n  var i: int := 0;\n  while i < len(s)\n    invariant 0 <= i\n"
       "    invariant i <= len(s)\n    invariant r == i\n    decreases len(s) - i\n  {\n    r := r + 1;\n"
       "    i := i + 1;\n  }\n}\n")
BARE = "t 0\ntask g(a: int) returns (r: int)\n  ensures r == a + 1\n{\n  r := a + 1;\n}\n"


def task(name: str, ensures: str, body: str) -> dict:
    return surface.parse(f"t 0\ntask {name}(a: int) returns (r: int)\n  ensures {ensures}\n{{\n  {body}\n}}\n")


class Rows(unittest.TestCase):
    def test_documents_with_and_without_a_head_both_parse(self):
        tasks = student_rows.documents(DOC + "\n\n" + BARE)
        self.assertEqual([t["name"] for t in tasks], ["mbpp_8__f", "g"])

    def test_the_question_keeps_the_contract_and_drops_the_body(self):
        row = student_rows.row_for(surface.parse(DOC.split("\n", 2)[2]))
        question = row["prompt"][1]["content"]
        block = question[question.index("```t"):]               # the task as asked, without the instruction
        self.assertIn("ensures r == len(s)", block)
        self.assertNotIn("invariant", block)
        self.assertNotIn("while", block)
        self.assertIn("invariant r == i", row["chosen"])
        self.assertEqual(row["kind"], "spec-given")


class HeldOut(unittest.TestCase):
    TRAIN = [task("mbpp_1__inc", "r == a + 1", "r := a + 1;"), task("dbl", "r == 2 * a", "r := 2 * a;")]

    def clean(self, held, ids=frozenset()):
        return student_rows.clean_heldout(self.TRAIN, held, set(ids))

    def test_a_document_that_shares_nothing_with_training_is_kept(self):
        keep, removed = self.clean([task("neg", "r == 0 - a", "r := 0 - a;")])
        self.assertEqual([t["name"] for t in keep], ["neg"])
        self.assertEqual(sum(removed.values()), 0)

    def test_a_problem_answered_in_the_other_training_rows_is_removed(self):
        keep, removed = self.clean([task("mbpp_7__neg", "r == 0 - a", "r := 0 - a;")], ids={7})
        self.assertEqual(keep, [])
        self.assertEqual(removed["problem answered in the other training rows"], 1)

    def test_the_same_program_under_another_name_is_removed(self):
        keep, removed = self.clean([task("increment", "r == a + 1", "r := a + 1;")])
        self.assertEqual(keep, [])
        self.assertEqual(removed["same program as a training document"], 1)

    def test_the_same_specification_with_another_body_is_removed(self):
        keep, removed = self.clean([task("twice", "r == 2 * a", "r := a + a;")])
        self.assertEqual(keep, [])
        self.assertEqual(removed["same specification as a training document"], 1)

    def test_the_comparison_is_textual_and_a_renamed_variable_is_not_caught(self):
        # stated in the module: this is the limit of the check, not a claim of independence
        other = surface.parse("t 0\ntask twice(b: int) returns (r: int)\n  ensures r == 2 * b\n{\n  r := b + b;\n}\n")
        keep, _removed = self.clean([other])
        self.assertEqual(len(keep), 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
