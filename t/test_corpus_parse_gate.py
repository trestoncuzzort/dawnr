"""The corpus builder must refuse, by name, any document it is about to write
that does not parse with the current surface -- never write it and move on.

Found 2026-09-27: the finite-sets feature (SPEC.md "Finite sets (v1)", merged
2026-09-27) reserved `diff` as a keyword. `diff` is a common variable/return
name (4 documents of the proved corpus and 5 lifted task files used it), so
those documents stopped parsing while the corpus builder kept writing them
unchecked: `chat_data.build()` silently dropped them later and `t_tool` would
reject any model answer that named a variable `diff`. `diff` is now spelled
`setminus` at the surface (this file's own SPEC.md/SYNTAX.md sections), which
fixes that specific collision, but the builder had no gate at all -- these
tests are that gate, independent of which word next collides with a corpus
identifier.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Names use ids far outside any real MBPP range, kept out of the corpus
# builder's own held-out/dev split files rather than the small ids a real
# split is likely to hold out (test_corpus_split.py hits this the honest
# way, by reading the real split; these fixtures use an empty synthetic
# split instead so a coincidence there can never make this test flaky).
GOOD = "t 1\ntask mbpp_9000001__f(diff: int) returns (r: int)\n  ensures r == diff\n{\n  r := diff;\n}\n"
# `setminus` is reserved (this file's fix for SPEC.md "Finite sets"), so a
# document naming a parameter `setminus` no longer parses -- exactly the
# failure shape the corpus builder must now catch and name, not skip.
BAD = ("t 1\ntask mbpp_9000002__g(setminus: int) returns (r: int)\n  ensures r == setminus\n"
      "{\n  r := setminus;\n}\n")
SPEC_DOC = ("Problem: keep every element\nSignature: f(seq) -> seq\nSpec:\n"
            "t 1\ntask mbpp_9000003__f(s: seq) returns (r: seq)\n  requires len(s) >= 0\n  ensures len(r) == len(s)\n")


def run_corpus(base_text, extra=()):
    with tempfile.TemporaryDirectory() as temp:
        d = Path(temp)
        base = d / "base.txt"
        base.write_text(base_text, encoding="utf-8")
        out = d / "corpus.txt"
        split = d / "split.json"
        split.write_text(json.dumps({"eval_ids": []}), encoding="utf-8")
        args = [sys.executable, str(HERE / "loop_locallm.py"), "corpus", "--pool", "v5",
                "--base", str(base), "--out", str(out), "--split", str(split)]
        args += list(extra)
        r = subprocess.run(args, capture_output=True, text=True, cwd=HERE)
        return r, (out.read_text(encoding="utf-8") if out.exists() else None)


class CorpusParseGateTests(unittest.TestCase):
    def test_a_document_that_no_longer_parses_is_refused_by_name_not_skipped(self):
        r, text = run_corpus("\n\n".join([GOOD, BAD]))
        self.assertNotEqual(r.returncode, 0, "a corpus with an unparseable document must be refused, not written")
        self.assertIn("mbpp_9000002__g", r.stderr, "the refusal must name the document, not just count it")
        self.assertIn("do not parse", r.stderr)
        self.assertIsNone(text, "the builder must not write a corpus it is about to refuse")

    def test_a_document_using_diff_as_an_ordinary_identifier_still_parses(self):
        r, text = run_corpus(GOOD)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("mbpp_9000001__f", text)

    def test_a_spec_document_is_exempt_the_gate_knows_it_has_no_body_by_design(self):
        r, text = run_corpus("\n\n".join([GOOD, SPEC_DOC]))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Spec:\n", text)


if __name__ == "__main__":
    unittest.main()
