"""dawnr_interp.browser: rendering a dictionary's top activating contexts as markdown.
What must hold: contexts come back strongest activation first; a feature that never
fired is reported as dead rather than silently empty (an empty section reads as a cut
-off file, not as a measurement); and `features=` actually restricts which sections
get written, so a wide dictionary's full browser stays an explicit choice, not the
only option. Needs torch; CPU only, milliseconds.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

from dawnr_interp.activations import CachedActivations  # noqa: E402
from dawnr_interp.browser import feature_browser_markdown, feature_stats, top_contexts  # noqa: E402


def cached_with(contexts):
    n = len(contexts)
    return CachedActivations(torch.zeros(n, 1), [0] * n, list(range(n)), [0] * n, layer=3, contexts=contexts)


class TopContextsTest(unittest.TestCase):
    def test_orders_by_activation_descending(self):
        cached = cached_with(["c0", "c1", "c2", "c3"])
        code = torch.tensor([[0.1], [0.9], [0.0], [0.5]])
        result = top_contexts(cached, code, feature=0, k=3)
        self.assertEqual([context for _, context in result], ["c1", "c3", "c0"])
        self.assertEqual([round(value, 1) for value, _ in result], [0.9, 0.5, 0.1])

    def test_k_larger_than_available_rows_is_clamped(self):
        cached = cached_with(["only"])
        code = torch.tensor([[1.0]])
        self.assertEqual(len(top_contexts(cached, code, 0, k=50)), 1)

    def test_rejects_a_feature_index_out_of_range(self):
        cached = cached_with(["a"])
        code = torch.tensor([[1.0]])
        with self.assertRaises(ValueError):
            top_contexts(cached, code, feature=1, k=1)

    def test_rejects_mismatched_row_count(self):
        cached = cached_with(["a", "b"])
        code = torch.zeros(3, 1)
        with self.assertRaises(ValueError):
            top_contexts(cached, code, feature=0, k=1)


class FeatureStatsTest(unittest.TestCase):
    def test_dead_feature_reports_zero_max(self):
        stats = feature_stats(torch.zeros(5, 2), feature=0)
        self.assertEqual(stats, {"fires": 0, "total": 5, "max": 0.0})

    def test_live_feature_reports_its_max(self):
        code = torch.tensor([[0.0], [2.5], [0.0]])
        stats = feature_stats(code, feature=0)
        self.assertEqual(stats["fires"], 1)
        self.assertAlmostEqual(stats["max"], 2.5, places=5)


class FeatureBrowserMarkdownTest(unittest.TestCase):
    def test_dead_feature_gets_a_dead_note_not_an_empty_section(self):
        cached = cached_with(["a", "b"])
        code = torch.zeros(2, 1)
        md = feature_browser_markdown(cached, code)
        self.assertIn("## Feature 0", md)
        self.assertIn("dead", md)

    def test_live_feature_lists_its_contexts(self):
        cached = cached_with(["alpha", "beta"])
        code = torch.tensor([[0.2], [0.8]])
        md = feature_browser_markdown(cached, code, top_k=2)
        self.assertIn("beta", md)
        self.assertIn("alpha", md)
        self.assertNotIn("dead", md)

    def test_features_argument_restricts_sections(self):
        cached = cached_with(["a", "b"])
        code = torch.tensor([[0.1, 0.2], [0.3, 0.4]])
        md = feature_browser_markdown(cached, code, features=[1])
        self.assertNotIn("## Feature 0", md)
        self.assertIn("## Feature 1", md)

    def test_rejects_mismatched_row_count(self):
        cached = cached_with(["a", "b", "c"])
        with self.assertRaises(ValueError):
            feature_browser_markdown(cached, torch.zeros(2, 1))


if __name__ == "__main__":
    unittest.main()
