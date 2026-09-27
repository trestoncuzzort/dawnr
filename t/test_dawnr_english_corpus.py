"""Regression tests for t/dawnr_english_corpus.py (2026-09-27).

Needs torch + tokenizers (locallm/data.py), so this runs under a venv that has
them (~/.venv-locallm or ~/.venv-train), not the bare system python3 -- the
same requirement locallm/test_tokenizer_integrity.py already has. Exercises
only the tinystories (.txt) shard path: the FineWeb-Edu parquet path needs
pyarrow, which is lab-only, the same gap dawnr_ngram_decontam.py's own
scan_fineweb_shard already has no local unit test for.
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCALLM = HERE.parent / "locallm"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    sys.path.insert(0, str(LOCALLM))
    import torch  # noqa: F401
    from data import BPETokenizer
    corpus = _load("dawnr_english_corpus", HERE / "dawnr_english_corpus.py")
    SKIP = None
except ImportError as exc:  # pragma: no cover - environment without torch/tokenizers
    SKIP = str(exc)


def make_tokenizer(path: Path) -> None:
    # 256 is BPETokenizer.from_text's own minimum; plenty for a handful of
    # short English sentences.
    text = ("the quick brown fox jumps over the lazy dog. " * 50 +
           "a story about a cat and a dog who became friends in the garden. " * 50)
    tok = BPETokenizer.from_text(text, vocab_size=256)
    tok.save(path)


def write_tinystories(path: Path, stories: list[str]) -> None:
    path.write_text("<|endoftext|>".join(stories), encoding="utf-8")


@unittest.skipIf(SKIP, f"needs torch + tokenizers: {SKIP}")
class AssembleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.shards = self.root / "shards"
        (self.shards / "tinystories").mkdir(parents=True)
        (self.shards / "fineweb-edu-sample-10BT").mkdir(parents=True)  # empty: no parquet needed
        self.stories = [f"Story number {i}. It has a beginning, a middle and an end." for i in range(1, 8)]
        write_tinystories(self.shards / "tinystories" / "stories.txt", self.stories)

        self.decontam = self.root / "decontam"
        self.decontam.mkdir()
        # flag stories 2 and 5 (1-based, matching iter_tinystories_docs' doc_id)
        (self.decontam / "flagged_ids.json").write_text(
            json.dumps({"stories.txt": [2, 5]}), encoding="utf-8")
        (self.decontam / "report.json").write_text(json.dumps({
            "total_contaminated": 2,
            "per_file": [{"file": "stories.txt", "documents": 7, "contaminated": 2}],
        }), encoding="utf-8")

        self.tokenizer_path = self.root / "tokenizer.json"
        make_tokenizer(self.tokenizer_path)
        self.out = self.root / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def test_flagged_documents_are_excluded_and_proof_recorded(self):
        manifest = corpus.assemble(self.shards, self.decontam, self.tokenizer_path, self.out,
                                   max_tokens=10_000_000, shard_tokens=10_000_000, text_corpus_path=None)
        self.assertEqual(manifest["documents_scanned"], 7)
        self.assertEqual(manifest["documents_excluded_flagged"], 2)
        self.assertEqual(manifest["documents_kept"], 5)
        self.assertEqual(manifest["files_processed"], ["stories.txt"])
        self.assertFalse(manifest["stopped_early_on_token_budget"])
        self.assertGreater(manifest["total_tokens"], 0)
        self.assertEqual(sum(s["tokens"] for s in manifest["shard_files"]), manifest["total_tokens"])
        # the manifest itself is the durable proof artifact, on disk beside the shards
        self.assertTrue((self.out / "manifest.json").exists())
        for shard in manifest["shard_files"]:
            self.assertTrue((self.out / shard["file"]).exists())

    def test_a_mismatched_flagged_id_is_refused_not_silently_kept(self):
        # story 99 does not exist in this file: a flagged id this pass never
        # encounters must raise, not be silently ignored (which would be the
        # failure mode of "trust the id list without re-checking it").
        (self.decontam / "flagged_ids.json").write_text(
            json.dumps({"stories.txt": [2, 5, 99]}), encoding="utf-8")
        (self.decontam / "report.json").write_text(json.dumps({
            "total_contaminated": 3,
            "per_file": [{"file": "stories.txt", "documents": 7, "contaminated": 3}],
        }), encoding="utf-8")
        with self.assertRaises(AssertionError):
            corpus.assemble(self.shards, self.decontam, self.tokenizer_path, self.out,
                            max_tokens=10_000_000, shard_tokens=10_000_000, text_corpus_path=None)

    def test_a_report_count_mismatch_is_refused(self):
        # flagged_ids.json and report.json individually consistent (both say 2
        # for this file) but load_decontam's own cross-file total check is
        # what this exercises: total_contaminated at the top level disagrees
        # with the per-file flagged_ids.json sum.
        (self.decontam / "report.json").write_text(json.dumps({
            "total_contaminated": 999,
            "per_file": [{"file": "stories.txt", "documents": 7, "contaminated": 2}],
        }), encoding="utf-8")
        with self.assertRaises(ValueError):
            corpus.assemble(self.shards, self.decontam, self.tokenizer_path, self.out,
                            max_tokens=10_000_000, shard_tokens=10_000_000, text_corpus_path=None)

    def test_documents_are_never_split_across_shards(self):
        # a tiny shard_tokens forces many shard files; each kept document's
        # tokens must still land wholly inside one shard file.
        manifest = corpus.assemble(self.shards, self.decontam, self.tokenizer_path, self.out,
                                   max_tokens=10_000_000, shard_tokens=8, text_corpus_path=None)
        self.assertGreater(len(manifest["shard_files"]), 1)
        self.assertEqual(sum(s["tokens"] for s in manifest["shard_files"]), manifest["total_tokens"])

    def test_stops_between_files_once_the_token_budget_is_reached(self):
        write_tinystories(self.shards / "tinystories" / "stories2.txt",
                          [f"Second file story {i}, unrelated to the first file entirely." for i in range(1, 6)])
        (self.decontam / "flagged_ids.json").write_text(
            json.dumps({"stories.txt": [2, 5], "stories2.txt": []}), encoding="utf-8")
        (self.decontam / "report.json").write_text(json.dumps({
            "total_contaminated": 2,
            "per_file": [{"file": "stories.txt", "documents": 7, "contaminated": 2},
                        {"file": "stories2.txt", "documents": 5, "contaminated": 0}],
        }), encoding="utf-8")
        # a token budget small enough that the first file alone satisfies it
        manifest = corpus.assemble(self.shards, self.decontam, self.tokenizer_path, self.out,
                                   max_tokens=1, shard_tokens=10_000_000, text_corpus_path=None)
        self.assertEqual(manifest["files_processed"], ["stories.txt"])
        self.assertTrue(manifest["stopped_early_on_token_budget"])

    def test_emits_a_plain_text_corpus_when_asked(self):
        text_path = self.root / "pilot.txt"
        corpus.assemble(self.shards, self.decontam, self.tokenizer_path, self.out,
                        max_tokens=10_000_000, shard_tokens=10_000_000, text_corpus_path=text_path)
        written = text_path.read_text(encoding="utf-8")
        # the two excluded stories' distinguishing numbers must not appear
        self.assertNotIn("Story number 2.", written)
        self.assertNotIn("Story number 5.", written)
        self.assertIn("Story number 1.", written)


if __name__ == "__main__":
    unittest.main()
