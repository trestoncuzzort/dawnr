"""Source authentication refusals, with disposable bytes and no network/build."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "source_lock", Path(__file__).resolve().parents[1] / "sources" / "source_lock.py")
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class PublishedDigestTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
