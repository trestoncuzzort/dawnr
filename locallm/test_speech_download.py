"""Tests for the pure logic in download_librispeech.py and
download_ljspeech.py: checksums and the disk-space budget guard. No network
call is made anywhere in this file -- that is the point of testing these
functions in isolation rather than only by hand against the real internet.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from speech import download_librispeech as dl_librispeech  # noqa: E402
from speech import download_ljspeech as dl_ljspeech  # noqa: E402


class Md5sumTest(unittest.TestCase):
    def test_matches_a_known_value(self):
        # md5("") is a fixed, well-known constant.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty"
            path.write_bytes(b"")
            self.assertEqual(dl_librispeech.md5sum(path), "d41d8cd98f00b204e9800998ecf8427e")

    def test_differs_for_different_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "b"
            a.write_bytes(b"hello")
            b.write_bytes(b"world")
            self.assertNotEqual(dl_librispeech.md5sum(a), dl_librispeech.md5sum(b))


class LibrispeechBudgetTest(unittest.TestCase):
    def test_allows_a_split_within_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            dl_librispeech.check_budget(Path(tmp) / "speech", "dev-clean", budget_gb=80.0)  # must not raise

    def test_refuses_a_split_that_would_exceed_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as ctx:
                dl_librispeech.check_budget(Path(tmp) / "speech", "train-other-500", budget_gb=1.0)
            self.assertIn("budget", str(ctx.exception))

    def test_counts_what_is_already_on_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            speech_root = Path(tmp) / "speech"
            (speech_root / "librispeech").mkdir(parents=True)
            big = speech_root / "librispeech" / "already-here.bin"
            big.write_bytes(b"0" * 1_000_000)                    # 1 MB already used
            self.assertEqual(dl_librispeech.speech_data_budget_used(speech_root), 1_000_000)
            # A tiny remaining budget plus something already on disk still refuses.
            with self.assertRaises(SystemExit):
                dl_librispeech.check_budget(speech_root, "dev-clean", budget_gb=0.0003)


class LjspeechBudgetTest(unittest.TestCase):
    def test_allows_within_budget_and_refuses_over_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            dl_ljspeech.check_budget(Path(tmp) / "speech", budget_gb=80.0)   # must not raise
            with self.assertRaises(SystemExit):
                dl_ljspeech.check_budget(Path(tmp) / "speech", budget_gb=0.001)


class SplitsTableConsistencyTest(unittest.TestCase):
    def test_every_official_md5_is_32_lowercase_hex_chars(self):
        for subset, (md5, _mb) in dl_librispeech.SPLITS.items():
            with self.subTest(subset=subset):
                self.assertRegex(md5, r"^[0-9a-f]{32}$")

    def test_subset_dir_name_strips_tar_gz_not_just_gz(self):
        self.assertEqual(dl_librispeech.subset_dir_name(Path("dev-clean.tar.gz")), "dev-clean")


if __name__ == "__main__":
    unittest.main()
