"""Regression tests for the general-English pretraining prep (2026-09-26).

Covers the parts that run without a GPU, a download, or the lab's larger
nl/data files: the token-budget arithmetic and the 13-gram decontamination
filter's index/match logic against the repository's own committed MBPP data
and the real held-out/dev id files.
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


budget = _load("dawnr_token_budget", HERE / "dawnr_token_budget.py")
decontam = _load("dawnr_ngram_decontam", HERE / "dawnr_ngram_decontam.py")


class TokenBudgetTest(unittest.TestCase):
    def test_core_and_312M_ratios(self):
        rows = {r["model"]: r for r in budget.budgets()}
        core = rows["core-92.9M"]
        self.assertEqual(core["parameters"], 92_920_320)
        self.assertEqual(core["chinchilla_20to1_tokens"], 92_920_320 * 20)
        self.assertEqual(core["minicpm_192to1_tokens"], 92_920_320 * 192)
        big = rows["312M"]
        self.assertEqual(big["parameters"], 311_224_320)
        self.assertEqual(big["chinchilla_20to1_tokens"], 311_224_320 * 20)
        self.assertEqual(big["minicpm_192to1_tokens"], 311_224_320 * 192)
        # MiniCPM's ratio is strictly the more generous budget, for every size.
        for row in rows.values():
            self.assertGreater(row["minicpm_192to1_tokens"], row["chinchilla_20to1_tokens"])


class ProtectedIdsTest(unittest.TestCase):
    """Uses the repository's own committed split and dev-id files, not fixtures,
    so a change to either one that breaks this filter's assumptions is caught
    here rather than only during a real run."""

    def test_eval_and_dev_ids_are_disjoint_mbpp_ids(self):
        ids = decontam.protected_ids(HERE / "out" / "loop" / "split-v5.json", HERE / "r12-dev-ids.json")
        self.assertEqual(len(ids), 332)
        self.assertEqual(sum(v == "eval" for v in ids.values()), 232)
        self.assertEqual(sum(v == "dev" for v in ids.values()), 100)
        # every dev id must be absent from eval (r12-dev-ids.json's own rule draws
        # only from train_ids, which a split never overlaps with eval_ids)
        eval_ids = {i for i, v in ids.items() if v == "eval"}
        dev_ids = {i for i, v in ids.items() if v == "dev"}
        self.assertEqual(eval_ids & dev_ids, set())


class NgramFilterTest(unittest.TestCase):
    def setUp(self):
        self.ids = decontam.protected_ids(HERE / "out" / "loop" / "split-v5.json", HERE / "r12-dev-ids.json")
        self.records = decontam.mbpp_records(HERE.parent / "nl" / "data")
        self.index, self.owners, self.missing = decontam.build_index(self.records, self.ids)

    def test_every_protected_id_found_in_nl_data(self):
        self.assertEqual(self.missing, [])

    def test_smoke_needle_is_caught(self):
        some_id = next(iter(self.ids))
        needle = decontam.problem_text(self.records[some_id])
        fake_doc = "Here is a tutorial about programming interview questions.\n\n" + needle + "\n\nThanks for reading!"
        words = decontam.WORD.findall(fake_doc.lower())
        pos, gram = decontam.find_match(words, self.index)
        self.assertIsNotNone(gram)
        self.assertIn(some_id, self.owners[gram])

    def test_unrelated_prose_is_not_flagged(self):
        clean = ("The quick brown fox jumps over the lazy dog near the riverbank at sunset "
                 "while birds sing softly in the trees above the old wooden bridge that creaks "
                 "under the weight of travelers passing through the quiet village every morning "
                 "before the sun rises fully over the distant mountains near the old mill.")
        words = decontam.WORD.findall(clean.lower())
        pos, gram = decontam.find_match(words, self.index)
        self.assertIsNone(gram)


if __name__ == "__main__":
    unittest.main()
