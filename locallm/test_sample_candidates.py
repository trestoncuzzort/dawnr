"""The stop rule is the only text transform between a model and its score."""
import unittest

import sample_candidates as sampler


class TruncationTests(unittest.TestCase):
    def test_a_closed_body_is_cut_after_its_brace(self):
        text, stopped = sampler.truncate("  r := x;\n}\n  r := 3;\n}\n")
        self.assertEqual(text, "  r := x;\n}\n")
        self.assertTrue(stopped)

    def test_an_unclosed_body_reaches_the_scorer_unchanged(self):
        text, stopped = sampler.truncate("  r := x;\n  r := r + 1;")
        self.assertEqual(text, "  r := x;\n  r := r + 1;")
        self.assertFalse(stopped)

    def test_a_brace_inside_a_line_does_not_stop_generation(self):
        text, stopped = sampler.truncate("  if r > 2 { r := 2 } else { }\n}\n")
        self.assertEqual(text, "  if r > 2 { r := 2 } else { }\n}\n")
        self.assertTrue(stopped)


if __name__ == "__main__":
    unittest.main()
