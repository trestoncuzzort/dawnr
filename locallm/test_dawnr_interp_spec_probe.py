"""dawnr_interp.spec_probe: the first interpretability question AMBITION.md asks --
do any features fire on specifications, as opposed to memorised boilerplate? What
must hold: a line is "spec" whenever it carries one of t's own clause keywords, even
if its exact text also repeats (a keyword line is never demoted to boilerplate); the
boilerplate threshold follows its own documented formula exactly; a token's label
comes from the line its decoded text actually falls in, in token order, matching how
activations.cache_residual_stream numbers positions; and the per-feature contrast
statistic ranks an engineered spec-only feature and an engineered boilerplate-only
feature at the two opposite ends, not by accident. Standard library plus torch for
the tensor statistics; CPU only, well under a second.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

from dawnr_interp.activations import CachedActivations  # noqa: E402
from dawnr_interp.spec_probe import (boilerplate_lines, feature_label_contrast,  # noqa: E402
                                     label_cached_activations, label_lines, render_report,
                                     token_line_labels)


class LabelLinesTest(unittest.TestCase):
    def test_keyword_line_is_spec(self):
        labels = label_lines("task f(x: int) returns (y: int)\n  ensures y >= 0\n{\n  y := x;\n}")
        self.assertEqual(labels, ["other", "spec", "other", "other", "other"])

    def test_all_five_keywords_are_recognised(self):
        for keyword in ("requires", "ensures", "invariant", "decreases", "spec"):
            self.assertEqual(label_lines(f"  {keyword} something")[0], "spec", keyword)

    def test_keyword_beats_boilerplate_membership(self):
        # "decreases n" happens to also be a line this corpus repeats a lot; it
        # must still read as spec, never demoted because its text is common.
        labels = label_lines("  decreases n", boilerplate_lines=frozenset({"decreases n"}))
        self.assertEqual(labels, ["spec"])

    def test_boilerplate_membership_only_applies_to_non_spec_lines(self):
        labels = label_lines("  i := i + 1;", boilerplate_lines=frozenset({"i := i + 1;"}))
        self.assertEqual(labels, ["boilerplate"])

    def test_unmatched_line_is_other(self):
        self.assertEqual(label_lines("  y := x + 1;"), ["other"])

    def test_keyword_as_a_substring_does_not_false_positive(self):
        # "spec" must not match "specification" or similar -- word boundaries only.
        self.assertEqual(label_lines("  var specification: int := 0;"), ["other"])


class BoilerplateLinesTest(unittest.TestCase):
    def test_empty_corpus_returns_empty_set(self):
        self.assertEqual(boilerplate_lines([]), frozenset())

    def test_a_line_below_threshold_is_excluded(self):
        # 10 documents, default min_fraction=0.02 -> round(0.2)=0 -> min(8,0)=0 -> floor 2.
        docs = [f"var x{i}: int := 0;\nunique_{i}();" for i in range(10)]
        docs[0] += "\nshared();"
        self.assertNotIn("shared();", boilerplate_lines(docs))

    def test_a_line_at_threshold_is_included(self):
        docs = [f"var x{i}: int := 0;\nunique_{i}();" for i in range(10)]
        docs[0] += "\nshared();"
        docs[1] += "\nshared();"
        self.assertIn("shared();", boilerplate_lines(docs))
        self.assertNotIn("var x0: int := 0;", boilerplate_lines(docs))  # unique to one document, never repeats

    def test_repetition_within_one_document_does_not_inflate_the_count(self):
        docs = ["shared();\nshared();\nshared();"] + [f"unique_{i}();" for i in range(9)]
        self.assertNotIn("shared();", boilerplate_lines(docs))  # seen in only 1 of 10 documents

    def test_rejects_bad_min_fraction(self):
        with self.assertRaises(ValueError):
            boilerplate_lines(["a"], min_fraction=1.5)


class TokenLineLabelsTest(unittest.TestCase):
    class _CharTok:
        """A minimal one-char-per-token tokenizer, enough for this module's contract."""
        def encode(self, s):
            return [ord(c) for c in s]

        def decode(self, ids):
            return "".join(chr(i) for i in ids)

    def test_length_matches_token_count(self):
        doc = "task f()\n  ensures true\n{\n}"
        labels = token_line_labels(doc, self._CharTok())
        self.assertEqual(len(labels), len(doc))

    def test_every_character_of_the_spec_line_is_labelled_spec(self):
        doc = "task f()\n  ensures true\n{\n}"
        labels = token_line_labels(doc, self._CharTok())
        line_start = doc.index("  ensures")
        line_end = doc.index("\n", line_start)
        self.assertTrue(all(label == "spec" for label in labels[line_start:line_end]))

    def test_empty_document_yields_no_labels(self):
        self.assertEqual(token_line_labels("", self._CharTok()), [])


class LabelCachedActivationsTest(unittest.TestCase):
    def test_labels_align_with_doc_index_and_position(self):
        tok = TokenLineLabelsTest._CharTok()
        documents = ["ensures ok\nx := 1;", "y := 2;\ninvariant q"]
        cached = CachedActivations(
            activations=torch.zeros(3, 1),
            doc_index=[0, 0, 1],
            position=[0, 11, 8],   # doc0 pos0 ('e' of "ensures ok"), doc0 pos11 ('x' of "x := 1;"),
            token_id=[0, 0, 0],    # doc1 pos8 ('i' of "invariant q")
            layer=0,
            contexts=["", "", ""],
        )
        labels = label_cached_activations(cached, documents, tok)
        self.assertEqual(labels, ["spec", "other", "spec"])


class FeatureLabelContrastTest(unittest.TestCase):
    def test_ranks_engineered_features_at_the_extremes(self):
        labels = ["spec"] * 20 + ["boilerplate"] * 20 + ["other"] * 10
        n = len(labels)
        code = torch.zeros(n, 3)
        code[:20, 0] = 1.0                    # feature 0: fires only on spec rows
        code[20:40, 1] = 1.0                  # feature 1: fires only on boilerplate rows
        code[:, 2] = 0.5                      # feature 2: fires everywhere alike
        contrasts = feature_label_contrast(code, labels)
        by_feature = {c.feature: c for c in contrasts}
        self.assertGreater(by_feature[0].contrast, 0)
        self.assertLess(by_feature[1].contrast, 0)
        self.assertEqual(by_feature[2].contrast, 0.0)   # zero variance and equal means: no contrast to report
        ranked = sorted(contrasts, key=lambda c: c.contrast, reverse=True)
        self.assertEqual(ranked[0].feature, 0)
        self.assertEqual(ranked[-1].feature, 1)

    def test_a_feature_missing_one_label_entirely_reports_zero_not_inf(self):
        labels = ["other"] * 5   # no "spec" and no "boilerplate" rows at all
        code = torch.rand(5, 1)
        contrasts = feature_label_contrast(code, labels)
        self.assertEqual(contrasts[0].contrast, 0.0)

    def test_rejects_mismatched_row_count(self):
        with self.assertRaises(ValueError):
            feature_label_contrast(torch.zeros(4, 2), ["spec", "other"])


class RenderReportTest(unittest.TestCase):
    def test_report_names_both_directions_with_real_numbers(self):
        labels = ["spec"] * 5 + ["boilerplate"] * 5
        n = len(labels)
        code = torch.zeros(n, 2)
        code[:5, 0] = 1.0
        code[5:, 1] = 1.0
        cached = CachedActivations(
            activations=torch.zeros(n, 1), doc_index=[0] * n, position=list(range(n)),
            token_id=[0] * n, layer=0, contexts=[f"ctx{i}" for i in range(n)],
        )
        contrasts = feature_label_contrast(code, labels)
        report = render_report(contrasts, cached, code)
        self.assertIn("Most specification-leaning features", report)
        self.assertIn("Most boilerplate-leaning features", report)
        self.assertIn("Feature 0", report)
        self.assertIn("Feature 1", report)

    def test_rejects_empty_contrasts(self):
        cached = CachedActivations(torch.zeros(1, 1), [0], [0], [0], 0, [""])
        with self.assertRaises(ValueError):
            render_report([], cached, torch.zeros(1, 1))


if __name__ == "__main__":
    unittest.main()
