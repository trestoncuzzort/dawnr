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


class HeldoutLeaks(unittest.TestCase):
    """leaks_heldout (2026-10-04): the textual check let a training row through whose specification equals a held-out
    question's once the held-out copy's `gate loops` line is ignored (vericoding_DD0680)."""
    HELD = {"name": "vericoding_dd0680__replace", "chosen": "```t\nt 1\ngate loops\ntask vericoding_dd0680__replace(s: seq, ch: int) returns (v: seq)\n"
            "  ensures len(v) == len(s)\n{\n  v := s;\n}\n```"}

    def row(self, name, text):
        return {"name": name, "chosen": "```t\n" + text + "```"}

    def test_the_same_specification_without_the_gate_line_is_a_leak(self):
        r = self.row("teacher_doc", "t 1\ntask other_name(s: seq, ch: int) returns (v: seq)\n  ensures len(v) == len(s)\n{\n  v := [];\n  v := s;\n}\n")
        self.assertEqual(student_rows.leaks_heldout([r], [self.HELD]), [(0, "spec-without-gate")])

    def test_the_same_vericoding_problem_is_a_leak_whatever_its_text(self):
        r = self.row("vericoding_DD0680", "t 1\ntask vericoding_DD0680(a: int) returns (r: int)\n  ensures r == a\n{\n  r := a;\n}\n")
        self.assertEqual(student_rows.leaks_heldout([r], [self.HELD]), [(0, "stem")])

    def test_the_textual_match_is_still_caught_and_an_unrelated_row_is_not(self):
        same = self.row("x", "t 1\ngate loops\ntask y(s: seq, ch: int) returns (v: seq)\n  ensures len(v) == len(s)\n{\n  v := s;\n}\n")
        other = self.row("z", "t 0\ntask g(a: int) returns (r: int)\n  ensures r == a + 1\n{\n  r := a + 1;\n}\n")
        self.assertEqual(student_rows.leaks_heldout([same, other], [self.HELD]), [(0, "text")])

    def test_a_row_without_a_t_block_is_skipped(self):
        self.assertEqual(student_rows.leaks_heldout([{"name": "p", "chosen": "def f(x):\n    return x\n"}], [self.HELD]), [])
