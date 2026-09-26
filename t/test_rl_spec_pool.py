"""t/rl_spec_pool.py: the stub body, the prompt cut at the body's brace, and the
answer assembled from the prompt and the model's continuation."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rl_spec_pool as sp                                         # noqa: E402
import surface                                                    # noqa: E402

SPEC = """// <vc-preamble>
predicate ValidInput(n: nat) { n >= 1 }
// </vc-preamble>
// <vc-spec>
method solve(n: nat, s: string) returns (result: nat, ok: bool)
    requires ValidInput(n)
    ensures result <= n
// </vc-spec>
// <vc-code>
{
  assume {:axiom} false;
}
// </vc-code>
"""

TASK = """t 1
task vericoding_da0001__solve(n: int) returns (r: int)
  requires n >= 0
  ensures r == n + 1
{
  r := 0;
}
"""


class Stub(unittest.TestCase):
    def test_every_return_gets_a_default_and_nothing_else(self):
        out = sp.stub_source(SPEC)
        self.assertNotIn("assume", out)
        self.assertIn("result := 0;", out)
        self.assertIn("ok := false;", out)
        self.assertIn("ensures result <= n", out)

    def test_a_return_type_without_a_default_is_refused(self):
        self.assertIsNone(sp.stub_source(SPEC.replace("ok: bool", "a: array<int>")))

    def test_a_file_without_the_assume_body_is_refused(self):
        self.assertIsNone(sp.stub_source(SPEC.replace("assume {:axiom} false;", "result := 1; ok := true;")))


class PromptAndAnswer(unittest.TestCase):
    def setUp(self):
        self.task = surface.parse(TASK)
        self.prompt = sp.spec_prompt("Add one.", self.task)

    def test_prompt_ends_at_the_body_brace_and_keeps_the_spec(self):
        self.assertTrue(self.prompt.startswith("Problem: Add one.\nSignature: "))
        self.assertTrue(self.prompt.endswith("{\n"))
        self.assertIn("ensures r == n + 1", self.prompt)
        self.assertNotIn("r := 0", self.prompt)                 # the stub never reaches a prompt

    def test_answer_is_prefix_plus_body_cut_at_the_next_document(self):
        text = sp.answer_task(self.prompt, "  r := n + 1;\n}\n\nProblem: another one\n")
        task = surface.parse(text)
        self.assertEqual(task["ensures"], self.task["ensures"])
        self.assertNotIn("Problem:", text)

    def test_a_continuation_that_opens_a_new_document_is_an_empty_body(self):
        text = sp.answer_task(self.prompt, "\nProblem: something else\nSignature: f(int) -> int\n")
        self.assertNotIn("Problem:", text)
        self.assertTrue(text.rstrip().endswith("{"))


if __name__ == "__main__":
    unittest.main()
