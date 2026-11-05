"""Source authentication refusals, with disposable bytes and no network/build."""
from __future__ import annotations

import copy
import base64
import hashlib
import importlib.util
import io
import json
import tempfile
import tarfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "source_lock", Path(__file__).resolve().parents[1] / "sources" / "source_lock.py")
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class PublishedDigestTests(unittest.TestCase):
    def test_sourceforge_exact_project_file_and_missing_digest(self):
        item = {"name": "x", "path": "/Release/1", "full_path": "Release/1/x",
                "type": "f", "sha256": "a" * 64}
        def page(value):
            return ("<script>net.sf.files = " + json.dumps({"x": value}) + ";</script>").encode()
        selection = {"format": "sourceforge-files", "project_path": "Release/1"}
        self.assertEqual(source.published_digest(page(item), selection, "x"), "a" * 64)
        for change in ({"sha256": None}, {"path": "/Other"}, {"name": "other"}, {"type": "d"}):
            with self.subTest(change=change), self.assertRaises(source.Refusal):
                source.published_digest(page({**item, **change}), selection, "x")
        with self.assertRaises(source.Refusal):
            source.published_digest(page(item) * 2, selection, "x")

    def test_sha512_announcement_has_explicit_algorithm_and_exact_filename(self):
        raw = ("<p>SHA-512 checksums</p>\n" + "a" * 128 + "\n  x\n").encode()
        self.assertEqual(source.published_digest(raw, {"format": "sha512-announcement"}, "x"), "a" * 128)
        for modified, name in ((raw, "other"), (raw.replace(b"SHA-512", b"SHA-1"), "x"), (raw * 2, "x")):
            with self.subTest(name=name), self.assertRaises(source.Refusal):
                source.published_digest(modified, {"format": "sha512-announcement"}, name)

    def test_gnu_release_formats_bind_exact_filename(self):
        hexadecimal = "a" * 64
        b64 = base64.b64encode(bytes.fromhex(hexadecimal)).decode()
        cases = [f"File: x\nSHA1 sum: {'b' * 40}\nSHA256 sum: {hexadecimal}\n",
                 f"SHA256 (x) = {b64}\n", f"{b64.rstrip('=')}  x\n",
                 f"{hexadecimal}  \nx\n"]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(source.published_digest(case.encode(), {"format": "gnu-announcement"}, "x"), hexadecimal)
                with self.assertRaises(source.Refusal):
                    source.published_digest(case.encode(), {"format": "gnu-announcement"}, "neighbor")

    def test_exact_filename_and_crlf_are_supported(self):
        data = f"{'b' * 64}  neighbor.tar.xz\r\n{'a' * 64} *selected.tar.xz\r\n".encode()
        self.assertEqual(source.published_digest(data, {"format": "sha256sum"}, "selected.tar.xz"), "a" * 64)

    def test_neighbor_filename_does_not_authenticate_selection(self):
        with self.assertRaises(source.Refusal):
            source.published_digest(f"{'a' * 64}  neighbor.tar.xz\n".encode(),
                                    {"format": "sha256sum"}, "selected.tar.xz")

    def test_filename_override_cannot_select_neighbor(self):
        with self.assertRaises(source.Refusal):
            source.published_digest(f"{'a' * 64}  neighbor.tar.xz\n".encode(),
                                    {"format": "sha256sum", "filename": "neighbor.tar.xz"}, "selected.tar.xz")

    def test_duplicate_and_weak_digests_are_rejected(self):
        for data in (f"{'a' * 64}  x\n" * 2, f"{'a' * 32}  x\n"):
            with self.subTest(data=data), self.assertRaises(source.Refusal):
                source.published_digest(data.encode(), {"format": "sha256sum"}, "x")

    def test_github_exact_tag_asset_and_strong_digest(self):
        payload = {"tag_name": "v1", "assets": [{"name": "x", "digest": "sha256:" + "a" * 64}]}
        selection = {"format": "github-release", "tag": "v1"}
        self.assertEqual(source.published_digest(json.dumps(payload).encode(), selection, "x"), "a" * 64)
        for changed in ({"tag_name": "v2", "assets": payload["assets"]},
                        {"tag_name": "v1", "assets": [{"name": "x", "digest": None}]}):
            with self.subTest(changed=changed), self.assertRaises(source.Refusal):
                source.published_digest(json.dumps(changed).encode(), selection, "x")

    def test_pypi_exact_version_and_filename(self):
        payload = {"info": {"version": "1"}, "urls": [{"filename": "x", "digests": {"sha256": "a" * 64}}]}
        selection = {"format": "pypi-release", "version": "1"}
        self.assertEqual(source.published_digest(json.dumps(payload).encode(), selection, "x"), "a" * 64)
        payload["info"]["version"] = "2"
        with self.assertRaises(source.Refusal):
            source.published_digest(json.dumps(payload).encode(), selection, "x")

    def test_html_only_exact_download_row(self):
        raw = (f'<tr><td><a href="https://publisher.invalid/x">source</a></td><td>{"a" * 64}</td></tr>'
               f'<tr><td><a href="https://publisher.invalid/y">other</a></td><td>{"b" * 64}</td></tr>').encode()
        selection = {"format": "html-table", "artifact_url": "https://publisher.invalid/x"}
        self.assertEqual(source.published_digest(raw, selection, "x"), "a" * 64)
        with self.assertRaises(source.Refusal):
            source.published_digest(raw + raw, selection, "x")

    def test_python_html_checksum_spans_and_word_breaks(self):
        raw = ('<tr><td><a href="https://publisher.invalid/x">XZ source</a></td>'
               '<td>23.1&nbsp;MB</td><td><code class="checksum">'
               f'<span>{"a" * 16}<wbr>{"a" * 16}</span><wbr>'
               f'<span>{"b" * 16}<wbr>{"b" * 16}</span></code></td></tr>').encode()
        selection = {"format": "html-table", "artifact_url": "https://publisher.invalid/x"}
        self.assertEqual(source.published_digest(raw, selection, "x"), "a" * 32 + "b" * 32)


class VerificationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache, self.evidence = self.root / "cache", self.root / "evidence"
        self.cache.mkdir()
        self.evidence.mkdir()
        self.archive = self.cache / "x.tar.xz"
        self.archive.write_bytes("source bytes: caf\u00e9\r\n".encode())
        self.expected = source.digest(self.archive)
        self.inventory = self.put("inventory", b"https://publisher.invalid/x.tar.xz\n")
        checksums = self.put("SHA256SUMS", f"{self.expected}  x.tar.xz\n".encode())
        self.record = {"baseline_name": "x.tar.xz", "name": "x.tar.xz", "url": "https://publisher.invalid/x.tar.xz",
                       "disposition": "retain", "sha256": self.expected,
                       "authentication": {"method": "https-published-sha256", "material": checksums,
                                          "selection": {"format": "sha256sum"}}}
        self.catalog = {"schema": source.CATALOG_SCHEMA, "architecture": "x86_64", "inventory": self.inventory,
                        "sources": [self.record], "advisory_review": {"status": "unresolved", "dispositions": []}}
        self.book = self.root / "BOOK-SOURCE.json"
        self.book.write_bytes(b'{"fixture":true}\n')

    def put(self, name, raw):
        (self.evidence / name).write_bytes(raw)
        return {"path": name, "url": "https://publisher.invalid/" + name, "sha256": sha(raw)}

    def verify(self):
        return source.verify_catalog(self.catalog, self.cache, self.evidence)

    def test_actual_bytes_verify_with_explicit_weaker_trust_class(self):
        report = self.verify()
        self.assertTrue(report["complete"])
        verified = report["sources"][0]
        self.assertEqual(verified["sha256"], self.expected)
        self.assertEqual(verified["authentication"]["trust_class"], "https-published-sha256")
        self.assertIn("no signature verified", verified["authentication"]["assurance"])

    def test_observed_hash_alone_is_not_authentication(self):
        self.record["authentication"] = {"method": "unresolved"}
        report = self.verify()
        self.assertFalse(report["complete"])
        self.assertIn("no supported authentication", report["sources"][0]["reason"])

    def test_missing_archive_is_unresolved(self):
        self.archive.unlink()
        self.assertFalse(self.verify()["complete"])

    def test_changed_archive_is_unresolved(self):
        self.archive.write_bytes(b"changed bytes\n")
        self.assertIn("differs from publisher", self.verify()["sources"][0]["reason"])

    def test_missing_material_is_unresolved(self):
        (self.evidence / "SHA256SUMS").unlink()
        self.assertFalse(self.verify()["complete"])

    def test_changed_material_is_unresolved(self):
        (self.evidence / "SHA256SUMS").write_bytes(b"changed material\n")
        self.assertIn("material SHA256 mismatch", self.verify()["sources"][0]["reason"])

    def test_reviewed_pin_mismatch_is_unresolved(self):
        self.record["sha256"] = "0" * 64
        self.assertIn("reviewed pin", self.verify()["sources"][0]["reason"])

    def test_path_escape_and_http_material_are_rejected(self):
        for field, value in (("path", "../SHA256SUMS"), ("path", "C:/SHA256SUMS"),
                             ("url", "http://publisher.invalid/SHA256SUMS")):
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(self.record["authentication"]["material"])
                changed[field] = value
                with self.assertRaises(source.Refusal):
                    source.material(self.evidence, changed)

    def test_inventory_omission_and_duplicate_are_rejected(self):
        for records in ([], [self.record, self.record]):
            self.catalog["sources"] = records
            with self.subTest(records=records), self.assertRaises(source.Refusal):
                self.verify()

    def test_changed_inventory_material_is_rejected(self):
        (self.evidence / "inventory").write_bytes(b"https://publisher.invalid/other.tar.xz\n")
        with self.assertRaises(source.Refusal):
            self.verify()

    def test_omission_cannot_close_candidate_verification(self):
        self.record.update(disposition="omit", reason="fixture")
        self.assertFalse(self.verify()["complete"])

    def test_openpgp_requires_actual_verifier_and_material(self):
        self.record["authentication"] = {"method": "openpgp", "primary_fingerprint": "A" * 40}
        self.assertFalse(self.verify()["complete"])

    def test_unresolved_advisories_block_export(self):
        with self.assertRaisesRegex(source.Refusal, "advisory review"):
            source.export_lock(self.catalog, self.verify(), self.book)

    def test_unverified_candidate_blocks_export(self):
        self.record["authentication"]["method"] = "unresolved"
        with self.assertRaisesRegex(source.Refusal, "unverified candidate"):
            source.export_lock(self.catalog, self.verify(), self.book)

    def test_unresolved_conflicting_evidence_blocks_verification(self):
        self.record["integrity_review"] = {"status": "unresolved"}
        self.assertIn("conflicting source evidence", self.verify()["sources"][0]["reason"])

    def test_changed_catalog_cannot_reuse_report(self):
        report = self.verify()
        self.record["url"] += ".changed"
        with self.assertRaisesRegex(source.Refusal, "does not describe"):
            source.export_lock(self.catalog, report, self.book)

    def test_truncated_report_cannot_claim_complete(self):
        report = self.verify()
        report["sources"] = []
        with self.assertRaisesRegex(source.Refusal, "unverified candidate"):
            source.export_lock(self.catalog, report, self.book)


class OpenPGPStatusTests(unittest.TestCase):
    primary = "A" * 40
    signer = "B" * 40

    def status(self, algorithm="8", primary=None):
        return (f"[GNUPG:] VALIDSIG {self.signer} 2026-11-05 123 0 4 0 1 {algorithm} 00 "
                f"{primary or self.primary}\n").encode()

    def test_approved_primary_can_sign_via_subkey(self):
        self.assertEqual(source.approved_signature(self.status(), 0, self.primary), self.signer)

    def test_wrong_primary_weak_digest_bad_status_and_nonzero_exit_refused(self):
        cases = [(self.status(primary="C" * 40), 0), (self.status(algorithm="2"), 0),
                 (self.status(algorithm="11"), 0), (self.status() + b"[GNUPG:] BADSIG bad signer\n", 0),
                 (self.status(), 1), (self.status() * 2, 0), (b"[GNUPG:] GOODSIG key user\n", 0)]
        for raw, code in cases:
            with self.subTest(raw=raw, code=code), self.assertRaises(source.Refusal):
                source.approved_signature(raw, code, self.primary)


class DistributorLinkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache, self.evidence = self.root / "cache", self.root / "evidence"
        self.cache.mkdir()
        self.evidence.mkdir()
        self.archive = self.cache / "x.tar.xz"
        self.archive.write_bytes(b"upstream bytes\r\n")
        self.member = "gentoo-20261103/app-shells/example/Manifest"
        self.expected = hashlib.sha512(self.archive.read_bytes()).hexdigest()
        self.raw = f"DIST x.tar.xz {self.archive.stat().st_size} SHA512 {self.expected}\n".encode()
        self.bundle = self.cache / "snapshot.tar.xz"
        self.write_snapshot({self.member: self.raw})
        (self.evidence / "Manifest").write_bytes(self.raw)
        (self.evidence / "keys.html").write_text(source.GENTOO_PRIMARY)
        self.auth = {
            "method": "distributor-openpgp-manifest", "distributor": "Gentoo",
            "snapshot": {"material": self.material(self.bundle), "authentication": {
                "method": "openpgp", "primary_fingerprint": source.GENTOO_PRIMARY,
                "approval": {"material": self.material(self.evidence / "keys.html",
                    "https://www.gentoo.org/downloads/signatures/")}}},
            "manifest_member": self.member, "manifest": self.material(self.evidence / "Manifest")}
        self.record = {"name": "x.tar.xz", "disposition": "retain", "authentication": self.auth}

    def material(self, path, url="https://publisher.invalid/material"):
        return {"path": path.name, "url": url, "sha256": source.digest(path)}

    def write_snapshot(self, entries):
        with tarfile.open(self.bundle, "w:xz") as archive:
            for name, raw in entries.items():
                entry = tarfile.TarInfo(name)
                entry.size = len(raw)
                archive.addfile(entry, io.BytesIO(raw))

    def verify(self):
        with patch.object(source, "verify_pgp", return_value={"trust_class": "publisher-openpgp"}) as check:
            result = source.verify_record(self.record, self.cache, self.evidence, None)
            check.assert_called_once()
            self.assertEqual(check.call_args.args[0], self.bundle)
            return result

    def test_exact_signed_snapshot_manifest_size_and_hash_linkage(self):
        result = self.verify()
        self.assertEqual(result["authentication"]["trust_class"], "distributor-openpgp-manifest")
        self.assertEqual(result["authentication"]["source_digest"], self.expected)
        self.assertEqual(result["sha256"], source.digest(self.archive))

    def test_snapshot_signature_failure_is_not_ignored(self):
        with patch.object(source, "verify_pgp", side_effect=source.Refusal("bad signature")):
            with self.assertRaisesRegex(source.Refusal, "bad signature"):
                source.verify_record(self.record, self.cache, self.evidence, None)

    def test_wrong_snapshot_bytes_are_rejected_before_signature_check(self):
        self.bundle.write_bytes(b"different signed or unsigned snapshot")
        with self.assertRaisesRegex(source.Refusal, "material SHA256 mismatch"):
            self.verify()

    def test_other_valid_snapshot_cannot_supply_missing_manifest(self):
        self.write_snapshot({"other/Manifest": self.raw})
        self.auth["snapshot"]["material"] = self.material(self.bundle)
        with self.assertRaisesRegex(source.Refusal, "every requested Manifest"):
            self.verify()

    def test_missing_snapshot_and_missing_retained_manifest_are_rejected(self):
        for path in (self.bundle, self.evidence / "Manifest"):
            raw = path.read_bytes()
            path.unlink()
            with self.subTest(path=path), self.assertRaisesRegex(source.Refusal, "missing evidence"):
                self.verify()
            path.write_bytes(raw)

    def test_tampered_manifest_cannot_be_laundered_by_repinning_it(self):
        path = self.evidence / "Manifest"
        path.write_bytes(self.raw + b"DIST neighbor 1 SHA512 " + b"a" * 128 + b"\n")
        self.auth["manifest"] = self.material(path)
        with self.assertRaisesRegex(source.Refusal, "not linked"):
            self.verify()

    def test_manifest_for_another_file_cannot_authenticate_source(self):
        wrong = self.raw.replace(b"x.tar.xz", b"other.tar.xz")
        self.write_snapshot({self.member: wrong})
        (self.evidence / "Manifest").write_bytes(wrong)
        self.auth["snapshot"]["material"] = self.material(self.bundle)
        self.auth["manifest"] = self.material(self.evidence / "Manifest")
        with self.assertRaisesRegex(source.Refusal, "exact filename"):
            self.verify()

    def test_source_size_and_same_size_corruption_are_rejected(self):
        raw = self.archive.read_bytes()
        for changed, expected in ((raw + b"x", "source size"), (b"X" + raw[1:], "source SHA512")):
            self.archive.write_bytes(changed)
            with self.subTest(changed=changed), self.assertRaisesRegex(source.Refusal, expected):
                self.verify()

    def test_unapproved_primary_and_missing_official_approval_are_rejected(self):
        signature = self.auth["snapshot"]["authentication"]
        signature["primary_fingerprint"] = "A" * 40
        with self.assertRaisesRegex(source.Refusal, "unapproved Gentoo"):
            self.verify()
        signature["primary_fingerprint"] = source.GENTOO_PRIMARY
        signature.pop("approval")
        with self.assertRaises(source.Refusal):
            self.verify()

    def test_partial_linkage_and_unsafe_member_paths_are_rejected(self):
        for field in ("snapshot", "manifest", "manifest_member"):
            saved = self.auth.pop(field)
            with self.subTest(field=field), self.assertRaises(source.Refusal):
                self.verify()
            self.auth[field] = saved
        self.auth["manifest_member"] = "../Manifest"
        with self.assertRaisesRegex(source.Refusal, "unsafe"):
            self.verify()

    def test_duplicate_dist_and_weak_digest_are_rejected(self):
        for raw in (self.raw * 2, b"DIST x.tar.xz 1 SHA1 " + b"a" * 40 + b"\n"):
            with self.subTest(raw=raw), self.assertRaises(source.Refusal):
                source.gentoo_manifest_entry(raw, "x.tar.xz")


if __name__ == "__main__":
    unittest.main()
