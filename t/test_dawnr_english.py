"""Regression tests for the general-English pretraining prep (2026-09-26).

Covers the parts that run without a GPU, a download, or the lab's larger
nl/data files: the token-budget arithmetic and the 13-gram decontamination
filter's index/match logic against the repository's own committed MBPP data
and the real held-out/dev id files.
"""
import importlib.util
import json
import sys
import tempfile
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


class WidenedProtectedSetTest(unittest.TestCase):
    """internal/PRETRAIN-DAWNR-GENERAL.md, 'Required before the English corpus
    is assembled': the protected set must widen past the 332 held-out/dev ids
    to the HumanEval ids the decontamination policy excludes and every
    CodeContests problem text. Runs with only the repository's committed data
    (no lab-only nl/data/codecontests_*.jsonl.gz), so the CodeContests half is
    checked for shape, not count."""

    def test_humaneval_excluded_ids_match_the_policy(self):
        # t/decontamination-behavioural-2026-09-25.json's exclude_train_ids
        # merged with t/decontamination-2026-09-21.json's, restricted to the
        # HumanEval id range: today that is exactly these three. A policy
        # change that adds or removes a HumanEval exclusion should change this
        # assertion, not silently pass it.
        ids = decontam.humaneval_excluded_ids()
        self.assertEqual(ids, {"humaneval:13": "humaneval-excluded",
                               "humaneval:23": "humaneval-excluded",
                               "humaneval:57": "humaneval-excluded"})

    def test_humaneval_records_found_for_every_excluded_id(self):
        ids = decontam.humaneval_excluded_ids()
        records = decontam.humaneval_records(HERE.parent / "nl" / "data", ids)
        self.assertEqual(set(records), set(ids))
        for rec in records.values():
            self.assertTrue(rec["text"].strip())

    def test_codecontests_records_keyed_and_empty_without_lab_data(self):
        # nl/data/codecontests_*.jsonl.gz is gitignored (local-only, per
        # .gitignore); a checkout without it must contribute zero records,
        # never raise.
        records = decontam.codecontests_records(HERE.parent / "nl" / "data")
        if (HERE.parent / "nl" / "data" / "codecontests_train.jsonl.gz").exists():
            self.assertGreater(len(records), 0)
        else:
            self.assertEqual(records, {})
        for key in records:
            self.assertTrue(key.startswith("codecontests:"))

    def test_widened_set_is_a_strict_superset_of_the_held_out_boundary(self):
        records, ids = decontam.widened_protected_set(
            HERE.parent / "nl" / "data", HERE / "out" / "loop" / "split-v5.json", HERE / "r12-dev-ids.json")
        held_out = decontam.protected_ids(HERE / "out" / "loop" / "split-v5.json", HERE / "r12-dev-ids.json")
        self.assertLessEqual(held_out.keys(), ids.keys())
        for pid, reason in held_out.items():
            self.assertEqual(ids[pid], reason)  # widening never relabels the absolute boundary
        self.assertEqual(sum(v == "humaneval-excluded" for v in ids.values()), 3)
        index, owners, missing = decontam.build_index(records, ids)
        self.assertEqual(missing, [])

    def test_a_humaneval_excluded_needle_is_caught(self):
        records, ids = decontam.widened_protected_set(
            HERE.parent / "nl" / "data", HERE / "out" / "loop" / "split-v5.json", HERE / "r12-dev-ids.json")
        index, owners, missing = decontam.build_index(records, ids)
        needle = decontam.problem_text(records["humaneval:13"])
        fake_doc = "An unrelated introduction.\n\n" + needle + "\n\nAn unrelated conclusion."
        words = decontam.WORD.findall(fake_doc.lower())
        pos, gram = decontam.find_match(words, index)
        self.assertIsNotNone(gram)
        self.assertIn("humaneval:13", owners[gram])

    def test_matched_problem_ids_sort_even_when_families_mix(self):
        # owners[gram] can hold both an int (MBPP) and a str (humaneval:/
        # codecontests:) key if two different protected problems happen to
        # share one generic 13-gram: plain sorted() on such a set raises
        # TypeError (str and int are not orderable), which is exactly why the
        # report-writing code sorts with key=str instead.
        mixed = {29, "humaneval:13", "codecontests:train:0"}
        with self.assertRaises(TypeError):
            sorted(mixed)
        result = sorted(mixed, key=str)  # must not raise
        self.assertEqual(set(result), mixed)
        self.assertEqual(len(result), 3)


class FlaggedIdsUncappedTest(unittest.TestCase):
    """examples.jsonl keeps only the first 25 matches per file for human review;
    flagged_ids must record every match, uncapped, or corpus assembly cannot
    exclude a document past the 25th match in a heavily-flagged file."""

    def test_more_than_25_matches_are_all_recorded_as_flagged_ids(self):
        ids = decontam.protected_ids(HERE / "out" / "loop" / "split-v5.json", HERE / "r12-dev-ids.json")
        records = decontam.mbpp_records(HERE.parent / "nl" / "data")
        index, owners, missing = decontam.build_index(records, ids)
        some_id = next(iter(ids))
        needle = decontam.problem_text(records[some_id])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fake.txt"
            # 40 separate "stories" all containing the same needle: more than the
            # 25-example cap, so this only passes if flagged_ids is not itself capped.
            path.write_text("<|endoftext|>".join(f"story {i}\n{needle}\n" for i in range(40)),
                            encoding="utf-8")
            result = decontam.scan_tinystories_file(str(path), index, owners)
        self.assertEqual(result["contaminated"], 40)
        self.assertEqual(len(result["examples"]), 25)
        self.assertEqual(len(result["flagged_ids"]), 40)
        self.assertEqual(result["flagged_ids"], list(range(1, 41)))


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
