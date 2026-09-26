"""t/lift_corpora.py --only-stems: a lift restricted to a listed subset of the staged files.

The 2026-09-26 lift refused 432 files as let-expressions; once the lifter lowers lets
(t/lift_let.py) the queue step lift-2026-09-26-let lifts exactly those again through the
same gates. The list is read the way rsync's --files-from reads its own
(download.samba.org/pub/rsync/rsync.1: one entry per line, blank lines and '#' comments
ignored, an entry that cannot be resolved is an error), and the filter runs after the full
staging copy, so everything downstream is the unrestricted run's code. No dafny needed.

    cd t && python3 -m unittest test_lift_corpora_stems
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lift_corpora                                              # noqa: E402


class OnlyStemsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.staged = self.tmp / "staged"
        self.staged.mkdir()

    def stage(self, *stems):
        for stem in stems:
            (self.staged / f"{stem}.dfy").write_text("// empty\n", encoding="utf-8")

    def test_the_staging_filter_keeps_only_the_listed_stems(self):
        self.stage("vericoding_DX0001", "vericoding_DX0002", "humaneval_dafny_000_x")
        stems = self.tmp / "stems.txt"
        stems.write_text("# the let-refused files\nvericoding_DX0002\n\nhumaneval_dafny_000_x\n", encoding="utf-8")
        self.assertEqual(lift_corpora.restrict_staged(self.staged, stems), 2)
        self.assertEqual(sorted(p.stem for p in self.staged.glob("*.dfy")),
                         ["humaneval_dafny_000_x", "vericoding_DX0002"])

    def test_a_listed_stem_that_was_never_staged_is_refused(self):
        self.stage("vericoding_DX0001")
        stems = self.tmp / "stems.txt"
        stems.write_text("vericoding_DX0001\nvericoding_DX9999\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            lift_corpora.restrict_staged(self.staged, stems)
        self.assertIn("vericoding_DX9999", str(caught.exception))
        self.assertTrue((self.staged / "vericoding_DX0001.dfy").exists())

    def test_the_option_is_parsed_and_defaults_to_every_file(self):
        args = lift_corpora.parse_args(["--out", "x", "--split", "y", "--only-stems", "z.txt"])
        self.assertEqual(args.only_stems, "z.txt")
        self.assertIsNone(lift_corpora.parse_args(["--out", "x", "--split", "y"]).only_stems)


if __name__ == "__main__":
    unittest.main()
