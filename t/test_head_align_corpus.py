"""The head must come from the program, never from imagination."""
import unittest

import head_align_corpus as align
import surface


class HeadTests(unittest.TestCase):
    def test_a_bare_program_gets_its_own_signature(self):
        program = ("t 1\ntask f(x: int, s: seq) returns (r: bool)\n"
                   "  ensures r == (x > 0)\n{\n  r := x > 0;\n}\n")
        documents, counts = align.align(program)
        self.assertEqual(counts["heads_added"], 1)
        self.assertTrue(documents[0].startswith("Signature: f(int, seq) -> bool\n"))
        self.assertIn("task f(x: int, s: seq)", documents[0])

    def test_a_document_that_already_has_a_head_is_untouched(self):
        text = ("Problem: add one\nSignature: g(int) -> int\nt 1\ntask g(x: int) returns (r: int)\n"
                "  ensures r == x + 1\n{\n  r := x + 1;\n}\n")
        documents, counts = align.align(text)
        self.assertEqual(counts["already_headed"], 1)
        self.assertEqual(counts["heads_added"], 0)
        self.assertEqual(documents[0], text.strip() + "\n")

    def test_the_head_matches_what_the_task_declares(self):
        task = surface.parse("t 1\ntask h(a: seq) returns (r: seq)\n  ensures len(r) == len(a)\n"
                             "{\n  r := a;\n}\n")
        self.assertEqual(align.head_for(task), "Signature: h(seq) -> seq\n")

    def test_unparseable_text_is_left_alone_and_counted(self):
        documents, counts = align.align("not a program at all\n")
        self.assertEqual(counts["unparsed"], 1)
        self.assertEqual(documents, ["not a program at all\n"])


if __name__ == "__main__":
    unittest.main()
