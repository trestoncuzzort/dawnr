"""Refusal regressions for the Kconfig qualification script; no kernel source or make runs here."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest


HARDWARE = Path(__file__).resolve().parents[1] / "hardware"
SPEC = importlib.util.spec_from_file_location("hardware_qualify_kconfig", HARDWARE / "qualify_kconfig.py")
qualify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qualify)

MAKEFILE = b"# SPDX-License-Identifier: GPL-2.0\nVERSION = 9\nPATCHLEVEL = 8\nSUBLEVEL = 7\nEXTRAVERSION =\n"
FILES = {"Makefile": MAKEFILE, "Kconfig": b'mainmenu "fixture"\n', "scripts/kconfig/merge_config.sh": b"exit 1\n"}


class QualifyRefusalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tup-qualify-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source, self.archive = self.root / "linux-9.8.7", self.root / "linux-9.8.7.tar.xz"
        self.lock, self.output = self.root / "lock.json", self.root / "output"
        with tarfile.open(self.archive, "w:xz") as tar:
            for name in ("", "scripts", "scripts/kconfig"):
                member = tarfile.TarInfo(("linux-9.8.7/" + name).rstrip("/"))
                member.type, member.mode = tarfile.DIRTYPE, 0o755
                tar.addfile(member)
            for name, raw in FILES.items():
                member = tarfile.TarInfo("linux-9.8.7/" + name)
                member.size = len(raw)
                tar.addfile(member, io.BytesIO(raw))
                (self.source / name).parent.mkdir(parents=True, exist_ok=True)
                (self.source / name).write_bytes(raw)
        self.write_lock(hashlib.sha256(self.archive.read_bytes()).hexdigest())

    def write_lock(self, sha256, name="linux-9.8.7.tar.xz"):
        self.lock.write_text(json.dumps({"sources": [{"name": name, "sha256": sha256}]}))

    def refused(self, pattern, output=None):
        with self.assertRaisesRegex(qualify.Refusal, pattern):
            qualify.qualify(self.source, self.archive, output or self.output, lock=self.lock)
        self.assertFalse(self.output.exists())

    def test_fixture_tree_matches_its_archive(self):
        self.assertEqual(qualify.release_of(self.source), "9.8.7")
        self.assertEqual(set(qualify.check_source(self.source, self.archive, "9.8.7")),
                         {".", "Kconfig", "Makefile", "scripts", "scripts/kconfig", "scripts/kconfig/merge_config.sh"})

    def test_existing_output_directory_refuses(self):
        existing = self.root / "existing"
        existing.mkdir()
        self.refused("already exists", existing)
        self.assertEqual(list(existing.iterdir()), [])

    def test_output_inside_source_tree_or_without_parent_refuses(self):
        before = qualify.snapshot(self.source)
        self.refused("outside the source tree", self.source / "out")
        self.refused("outside the source tree", self.source / "scripts" / "out")
        self.refused("existing parent", self.root / "absent" / "out")
        self.assertEqual(qualify.snapshot(self.source), before)

    def test_release_absent_from_source_lock_or_wrong_archive_refuses(self):
        self.write_lock("0" * 64, name="linux-1.2.3.tar.xz")
        self.refused("source lock does not hold exactly one linux-9.8.7.tar.xz")
        self.write_lock("0" * 64)
        self.refused("input digest mismatch")

    def test_changed_missing_or_extra_source_entries_refuse(self):
        (self.source / "Kconfig").write_bytes(FILES["Kconfig"].replace(b"fixture", b"altered"))
        self.refused("differs from the locked archive: Kconfig")
        (self.source / "Kconfig").unlink()
        self.refused("differs from the locked archive: Kconfig")
        (self.source / "Kconfig").write_bytes(FILES["Kconfig"])
        (self.source / ".config").write_bytes(b"CONFIG_STALE=y\n")
        self.refused("entries the locked archive lacks: .config")

    def test_source_snapshot_sees_a_created_then_removed_file(self):
        before = qualify.snapshot(self.source)
        self.assertEqual(qualify.snapshot(self.source), before)
        (self.source / "scripts" / "extra").write_bytes(b"x")
        self.assertNotEqual(qualify.snapshot(self.source), before)

    def test_main_reports_refusal_without_creating_output(self):
        self.assertEqual(qualify.main(["--source", str(self.root / "absent"), "--archive", str(self.archive),
                                       "--output", str(self.output)]), 1)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
