"""Receipt evidence must identify the bytes collected, even on Windows.

Run with python3 -m unittest discover -s tup/tests -p 'test_bundle_receipts*.py'.
Fixtures are disposable; no build VM or source tarballs are needed.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "bundle_receipts", Path(__file__).resolve().parents[1] / "bundle_receipts.py")
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class BundleEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case_number = 0
        self.make_case()

    def make_case(self, newline=b"\n", non_ascii=False):
        self.case_number += 1
        self.here = self.root / str(self.case_number) / "tup"
        self.log = self.here / "log"
        self.log.mkdir(parents=True)
        self.out = self.here / "receipts"
        page = "ch08/01-café.sh" if non_ascii else "ch08/01-test.sh"
        row = {"page": page, "exit": 0, "seconds": 2,
               "package": "café" if non_ascii else "example"}
        self.receipts = json.dumps(row, ensure_ascii=False).encode("utf-8") + newline
        self.state = page.encode("utf-8") + newline
        filename = "café.tar.xz" if non_ascii else "example.tar.xz"
        self.manifest = ("a" * 64 + "  " + filename).encode("utf-8") + newline
        (self.log / "receipts.jsonl").write_bytes(self.receipts)
        (self.log / "driver.state").write_bytes(self.state)
        (self.log / "SHA256-MANIFEST-test.txt").write_bytes(self.manifest)

    def run_bundle(self, local=True):
        stdout, stderr = io.StringIO(), io.StringIO()
        args = ["bundle_receipts.py"] + (["--local", str(self.log)] if local else [])
        with patch.object(bundle, "HERE", self.here), patch.object(bundle, "OUT", self.out), \
                patch.object(bundle.sys, "argv", args), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = bundle.main()
        reports = list(self.out.glob("BUILD-*.md"))
        report = reports[0].read_text(encoding="utf-8") if reports else ""
        return result, report, stdout.getvalue() + stderr.getvalue()

    def assert_hash(self, report, name, raw):
        self.assertIn(f"{bundle.md_code(name)} sha256 `{digest(raw)}`", report)

    def assert_rejected(self, expected):
        result, report, output = self.run_bundle()
        self.assertNotEqual(result, 0, output)
        self.assertEqual(report, "", "invalid evidence must not produce a build report")
        self.assertIn(expected, output)

    def test_local_hashes_and_archives_preserve_original_bytes(self):
        for newline in (b"\n", b"\r\n"):
            for non_ascii in (False, True):
                with self.subTest(newline=newline, non_ascii=non_ascii):
                    self.make_case(newline, non_ascii)
                    result, report, output = self.run_bundle()
                    self.assertEqual(result, 0, output)
                    self.assert_hash(report, "receipts.jsonl", self.receipts)
                    self.assert_hash(report, "driver.state", self.state)
                    self.assert_hash(report, "SHA256-MANIFEST", self.manifest)
                    self.assertEqual(next(self.out.glob("receipts-*.jsonl")).read_bytes(),
                                     self.receipts)
                    self.assertEqual(next(self.out.glob("SHA256-MANIFEST-*.txt")).read_bytes(),
                                     self.manifest)
                    self.assertEqual(next(self.out.glob("driver-state-*.txt")).read_bytes(),
                                     self.state)

    def test_manifests_have_per_file_identity_and_explicit_concatenation_order(self):
        (self.log / "SHA256-MANIFEST-test.txt").unlink()
        parts = {
            "SHA256-MANIFEST-a.txt": b"a" * 64 + b"  second.tar.xz\r\n",
            # No newline at EOF: aggregate bytes must not invent a delimiter.
            "SHA256-MANIFEST-Z.txt": b"b" * 64 + b"  first.tar.xz",
            "SHA256-MANIFEST-é.txt": b"c" * 64 + b" *third.tar.xz\n",
        }
        for name, raw in parts.items():
            (self.log / name).write_bytes(raw)
        result, report, output = self.run_bundle()
        self.assertEqual(result, 0, output)
        ordered = sorted(parts, key=lambda name: name.encode("utf-8"))
        aggregate = b"".join(parts[name] for name in ordered)
        self.assert_hash(report, "SHA256-MANIFEST", aggregate)
        self.assertIn("source manifest entries: **3**", report)
        self.assertIn("UTF-8 basename byte order", report)
        self.assertIn("no inserted separators", report)
        self.assertIn("does not bind filenames or file boundaries", report)
        previous = -1
        for name in ordered:
            self.assert_hash(report, name, parts[name])
            position = report.index(bundle.md_code(name))
            self.assertGreater(position, previous)
            previous = position
        components = next(self.out.glob("manifest-components-*"))
        for number, name in enumerate(ordered, 1):
            self.assertEqual((components / f"{number}.txt").read_bytes(), parts[name])
        self.assertEqual(next(self.out.glob("SHA256-MANIFEST-*.txt")).read_bytes(), aggregate)

    def test_local_manifests_take_precedence_over_parent(self):
        (self.log.parent / "SHA256-MANIFEST-parent.txt").write_bytes(b"invalid parent")
        result, report, output = self.run_bundle()
        self.assertEqual(result, 0, output)
        self.assert_hash(report, "SHA256-MANIFEST", self.manifest)
        self.assertNotIn("SHA256-MANIFEST-parent.txt", report)

    def test_parent_manifests_are_used_when_no_local_manifest_exists(self):
        (self.log / "SHA256-MANIFEST-test.txt").rename(
            self.log.parent / "SHA256-MANIFEST-test.txt")
        result, report, output = self.run_bundle()
        self.assertEqual(result, 0, output)
        self.assert_hash(report, "SHA256-MANIFEST", self.manifest)

    def test_missing_required_evidence_is_not_hashed_as_empty(self):
        for name in ("receipts.jsonl", "driver.state", "SHA256-MANIFEST-test.txt"):
            with self.subTest(name=name):
                self.make_case()
                (self.log / name).unlink()
                self.assert_rejected("manifest" if name.startswith("SHA256") else name)

    def test_empty_state_is_valid_for_a_failed_first_page(self):
        (self.log / "driver.state").write_bytes(b"")
        row = {"page": "ch08/01-test.sh", "exit": 1, "seconds": 2}
        (self.log / "receipts.jsonl").write_bytes(json.dumps(row).encode() + b"\n")
        result, report, output = self.run_bundle()
        self.assertEqual(result, 0, output)
        self.assert_hash(report, "driver.state", b"")
        self.assertIn("plus 1 failed page(s)", report)

    def test_invalid_utf8_evidence_is_rejected_before_output(self):
        for name in ("receipts.jsonl", "driver.state", "SHA256-MANIFEST-test.txt",
                     "PROVENANCE-NOTE-bootscripts.txt"):
            with self.subTest(name=name):
                self.make_case()
                (self.log / name).write_bytes(b"invalid\xff\n")
                self.assert_rejected(name)

    def test_invalid_or_empty_receipts_are_rejected_before_output(self):
        for raw in (b"", b"\r\n", b'{"page":', b"[]\n", b"null\n"):
            with self.subTest(raw=raw):
                self.make_case()
                (self.log / "receipts.jsonl").write_bytes(raw)
                self.assert_rejected("receipts.jsonl")

    def test_invalid_or_empty_manifests_are_rejected_before_output(self):
        for raw in (b"", b"\r\n", b"not a checksum\n", b"0" * 63 + b"  file\n",
                    b"0" * 64 + b"  \n"):
            with self.subTest(raw=raw):
                self.make_case()
                (self.log / "SHA256-MANIFEST-test.txt").write_bytes(raw)
                self.assert_rejected("SHA256-MANIFEST-test.txt")

    def test_gnu_escaped_filename_records_remain_supported(self):
        raw = b"\\" + b"a" * 64 + b"  file\\nname\\\\.tar.xz\r\n"
        (self.log / "SHA256-MANIFEST-test.txt").write_bytes(raw)
        result, report, output = self.run_bundle()
        self.assertEqual(result, 0, output)
        self.assert_hash(report, "SHA256-MANIFEST", raw)

    def test_present_unreadable_provenance_note_is_not_treated_as_absent(self):
        # A directory reliably fails as a file on Windows and Linux, including root.
        (self.log / "PROVENANCE-NOTE-bootscripts.txt").mkdir()
        self.assert_rejected("PROVENANCE-NOTE-bootscripts.txt")

    def test_provenance_note_is_hashed_and_preserved_as_bytes(self):
        raw = "exception: café\r\n".encode("utf-8")
        (self.log / "PROVENANCE-NOTE-bootscripts.txt").write_bytes(raw)
        result, report, output = self.run_bundle()
        self.assertEqual(result, 0, output)
        self.assert_hash(report, "PROVENANCE-NOTE-bootscripts.txt", raw)
        self.assertEqual(next(self.out.glob("provenance-note-*.txt")).read_bytes(), raw)

    def test_unicode_line_separator_is_not_a_jsonl_record_boundary(self):
        row = {"page": "ch08/01-test.sh", "exit": 0, "package": "one\u2028two"}
        raw = json.dumps(row, ensure_ascii=False).encode("utf-8") + b"\r\n"
        (self.log / "receipts.jsonl").write_bytes(raw)
        result, report, output = self.run_bundle()
        self.assertEqual(result, 0, output)
        self.assert_hash(report, "receipts.jsonl", raw)
        self.assertIn("distinct pages built: **1**", report)

    def test_failed_evidence_copy_does_not_emit_a_report(self):
        original_write = Path.write_bytes

        def fail_archive(path, raw):
            if path.parent == self.out and path.name.startswith("receipts-"):
                raise OSError("injected archive write failure")
            return original_write(path, raw)

        with patch.object(Path, "write_bytes", new=fail_archive):
            self.assert_rejected("injected archive write failure")

    def remote_run(self, failures=None):
        files = {
            f"{bundle.REMOTE_LOG}/receipts.jsonl": self.receipts,
            f"{bundle.REMOTE_LOG}/driver.state": self.state,
            f"{bundle.REMOTE_SRC}/SHA256-MANIFEST-test.txt": self.manifest,
        }

        def run(args, **kwargs):
            self.assertFalse(kwargs.get("text") or kwargs.get("encoding") or
                             kwargs.get("universal_newlines"))
            if args[-1] == bundle.REMOTE_SRC:
                key, raw = "manifest list", b"SHA256-MANIFEST-test.txt\0"
            elif args[-1].endswith("PROVENANCE-NOTE-bootscripts.txt"):
                key, raw = "provenance note", b"0"
            else:
                key, raw = args[-1], files[args[-1]]
            code, raw = (failures or {}).get(key, (0, raw))
            return subprocess.CompletedProcess(args, code, raw, b"fixture stderr")

        return run

    def test_remote_bundle_hashes_and_preserves_binary_evidence(self):
        self.make_case(b"\r\n", non_ascii=True)
        with patch.object(bundle.subprocess, "run", side_effect=self.remote_run()):
            result, report, output = self.run_bundle(local=False)
        self.assertEqual(result, 0, output)
        self.assert_hash(report, "receipts.jsonl", self.receipts)
        self.assert_hash(report, "driver.state", self.state)
        self.assert_hash(report, "SHA256-MANIFEST-test.txt", self.manifest)
        self.assertEqual(next(self.out.glob("receipts-*.jsonl")).read_bytes(), self.receipts)

    def test_remote_failures_never_hash_partial_or_missing_evidence(self):
        cases = {
            "manifest list": (1, b"SHA256-MANIFEST-test.txt\0"),
            f"{bundle.REMOTE_LOG}/driver.state": (1, b""),
            f"{bundle.REMOTE_SRC}/SHA256-MANIFEST-test.txt": (1, self.manifest),
            "provenance note": (1, b"0"),
        }
        for key, failure in cases.items():
            with self.subTest(key=key):
                self.make_case()
                with patch.object(bundle.subprocess, "run",
                                  side_effect=self.remote_run({key: failure})):
                    result, report, output = self.run_bundle(local=False)
                self.assertNotEqual(result, 0, output)
                self.assertEqual(report, "")
                self.assertIn("remote exit 1", output)

    def test_empty_or_malformed_remote_manifest_list_is_rejected(self):
        for listing in (b"", b"SHA256-MANIFEST-test.txt", b"../SHA256-MANIFEST-test.txt\0",
                        b"SHA256-MANIFEST-test.txt\0SHA256-MANIFEST-test.txt\0"):
            with self.subTest(listing=listing):
                self.make_case()
                with patch.object(bundle.subprocess, "run",
                                  side_effect=self.remote_run({"manifest list": (0, listing)})):
                    result, report, output = self.run_bundle(local=False)
                self.assertNotEqual(result, 0, output)
                self.assertEqual(report, "")
                self.assertIn("manifest", output)

    def test_remote_reads_do_not_use_text_conversion(self):
        raw = "café\r\n".encode("utf-8")

        def fake_run(args, **kwargs):
            data = raw
            if kwargs.get("text") or kwargs.get("universal_newlines") or kwargs.get("encoding"):
                data = io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8").read()
            return subprocess.CompletedProcess(args, 0, data, b"")

        with patch.object(bundle.subprocess, "run", side_effect=fake_run):
            self.assertEqual(bundle.vm_read("/evidence/receipts.jsonl"), raw)


if __name__ == "__main__":
    unittest.main()
