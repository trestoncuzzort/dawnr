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


class DiscriminativeExampleTests(unittest.TestCase):
    """TiCoder (arXiv:2208.05950): show the example that separates candidates."""

    @staticmethod
    def point(args, expected):
        return {"args": [["int", a] for a in args], "expected": ["int", expected]}

    def test_an_example_the_obvious_wrong_answers_match_is_ranked_last(self):
        import loop_locallm
        identity = self.point([7], 7)          # refutes almost nothing
        informative = self.point([7], 128)     # refutes identity, +1, doubling, zero
        chosen = loop_locallm.discriminative([identity, informative], 1)
        self.assertIs(chosen[0], informative)

    def test_the_measured_failure_is_what_it_rules_out(self):
        # A model specified `r == x + 1` for a predicate problem on 2026-09-20.
        import loop_locallm
        matches_successor = self.point([4], 5)
        breaks_successor = self.point([4], 99)
        self.assertIs(loop_locallm.discriminative([matches_successor, breaks_successor], 1)[0],
                      breaks_successor)

    def test_ties_keep_the_problem_s_own_order(self):
        import loop_locallm
        a, b = self.point([3], 100), self.point([4], 200)
        self.assertEqual(loop_locallm.discriminative([a, b], 2), [a, b])

    def test_asking_for_more_than_exist_returns_what_exists(self):
        import loop_locallm
        self.assertEqual(len(loop_locallm.discriminative([self.point([1], 2)], 5)), 1)

    def test_a_malformed_point_does_not_crash_the_ranking(self):
        import loop_locallm
        self.assertEqual(len(loop_locallm.discriminative([{"args": None}, self.point([1], 9)], 2)), 2)
