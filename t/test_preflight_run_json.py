"""preflight --run-json: step 5 of the r12 checklist reads the trainer's record.

Written 2026-09-25 with the track T4 record layout (locallm/continue_from_checkpoint.py
schema 2). Each test builds the record it needs; nothing is trained.
"""
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import preflight


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class RunJsonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.split = self.tmp / "split.json"
        self.split.write_text(json.dumps({"eval_ids": [1, 2, 3], "train_ids": [4]}))
        self.corpus = self.tmp / "corpus.txt"
        self.corpus.write_text("Signature: mbpp_4__f(int) -> int\nt 1\ntask mbpp_4__f(a: int) returns (r: int)\n{\n  r := a;\n}\n")

    def record(self, **overrides):
        ident = {"split_seed": 1337, "split": {"by": "hash", "seed": 1337},
                 "batches": {"kind": "documents", "cut_documents": 0},
                 "reproducibility": {"requested": True, "use_deterministic_algorithms": True},
                 "corpus": str(self.corpus), "corpus_sha256": sha(self.corpus),
                 "evaluation_split": str(self.split), "evaluation_split_sha256": sha(self.split)}
        report = {"schema": 2, "status": "complete", "identities": ident}
        for key, value in overrides.items():
            target, _, leaf = key.rpartition(".")
            node = report
            for part in target.split(".") if target else []:
                node = node[part]
            node[leaf] = value
        path = self.tmp / "run.json"
        path.write_text(json.dumps(report))
        return path

    def check(self, path):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ok = preflight.check_run_json(path, self.split, [self.corpus])
        return ok, out.getvalue()

    def test_a_complete_hash_split_document_batch_deterministic_run_passes(self):
        ok, out = self.check(self.record())
        self.assertTrue(ok, out)
        self.assertNotIn("FAIL", out)

    def test_each_demand_of_the_recipe_is_its_own_refusal(self):
        for key, value, phrase in (
                ("schema", 1, "schema 2"),
                ("status", "running", "run complete"),
                ("identities.split_seed", None, "own split seed"),
                ("identities.split.by", "order", "document hash"),
                ("identities.batches.kind", "windows", "whole-document rows"),
                ("identities.reproducibility.use_deterministic_algorithms", False, "deterministic algorithms"),
                ("identities.evaluation_split_sha256", "0" * 64, "this split by digest"),
                ("identities.corpus_sha256", "0" * 64, "selected corpus by digest")):
            with self.subTest(key=key):
                ok, out = self.check(self.record(**{key: value}))
                self.assertFalse(ok, out)
                self.assertIn("FAIL", out)
                self.assertIn(phrase, out)

    def test_an_unreadable_or_shapeless_record_fails_by_name(self):
        missing = self.tmp / "absent.json"
        ok, out = self.check(missing)
        self.assertFalse(ok)
        self.assertIn("readable", out)
        shapeless = self.tmp / "shapeless.json"
        shapeless.write_text(json.dumps({"schema": 2}))
        ok, out = self.check(shapeless)
        self.assertFalse(ok)
        self.assertIn("identities", out)


if __name__ == "__main__":
    unittest.main()
