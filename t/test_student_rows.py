"""t/student_rows.py (2026-10-01): "specification given, write the body" rows, the vericoding
setting (arXiv:2509.22908). The question keeps the contract and drops the body; the answer is the
whole proved task; a held-out problem stops the build. No kernel."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import student_rows  # noqa: E402
import surface  # noqa: E402

DOC = ("Problem: Count.\nSignature: f(seq) -> int\nt 1\ngate loops\ntask mbpp_8__f(s: seq) returns (r: int)\n"
       "  ensures r == len(s)\n{\n  r := 0;\n  var i: int := 0;\n  while i < len(s)\n    invariant 0 <= i\n"
       "    invariant i <= len(s)\n    invariant r == i\n    decreases len(s) - i\n  {\n    r := r + 1;\n"
       "    i := i + 1;\n  }\n}\n")
BARE = "t 0\ntask g(a: int) returns (r: int)\n  ensures r == a + 1\n{\n  r := a + 1;\n}\n"


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
        self.assertTrue(row["chosen"].startswith("```t\n") and row["chosen"].endswith("```"))
        self.assertEqual(row["kind"], "spec-given")

    def test_a_held_out_problem_stops_the_build(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / "c.txt"
            corpus.write_text(DOC, encoding="utf-8")
            with patch.object(student_rows, "blocked_ids", lambda _p: {8}):
                with self.assertRaises(SystemExit) as stop:
                    student_rows.build(corpus, Path(tmp) / "split.json")
            self.assertIn("mbpp_8__f", str(stop.exception))
            with patch.object(student_rows, "blocked_ids", lambda _p: set()):
                self.assertEqual(len(student_rows.build(corpus, Path(tmp) / "split.json")), 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
