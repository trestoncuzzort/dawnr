"""Narrow exception, advisory coverage and payload-equivalence boundaries."""
from __future__ import annotations

import copy
import gzip
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "source_lock", Path(__file__).resolve().parents[1] / "sources" / "source_lock.py")
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)


class PolicyFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache, self.evidence = self.root / "cache", self.root / "evidence"
        self.cache.mkdir()
        self.evidence.mkdir()

    def put(self, name, raw, url="https://publisher.invalid/material"):
        path = self.evidence / name
        path.write_bytes(raw)
        return {"path": name, "sha256": source.digest(path), "url": url}

    def approved_constant(self, name, value):
        mock = patch.object(source, name, value)
        mock.start()
        self.addCleanup(mock.stop)


class ExceptionTests(PolicyFixture):
    def setUp(self):
        super().setUp()
        self.archive = self.cache / "one.patch"
        self.archive.write_bytes(b"exact patch bytes\r\n")
        corroboration = self.put("corroboration.json", b"{}\n")
        policy = {"schema": "tup-reviewed-lfs-patch-exceptions-v1",
                  "decision": "approved-provenance-exception", "commit": "a" * 40,
                  "corroboration_sha256": corroboration["sha256"], "assurance": "fixture exception",
                  "patches": [{"name": self.archive.name, "sha256": source.digest(self.archive), "git_blob": "b" * 40}]}
        reviewed = self.put("policy.json", source.encoded(policy))
        self.approved_constant("PATCH_POLICY_SHA256", reviewed["sha256"])
        self.approved_constant("PATCH_CORROBORATION_SHA256", corroboration["sha256"])
        self.auth = {"method": "reviewed-lfs-patch-exception", "policy": reviewed, "corroboration": corroboration}

    def test_exception_is_distinct_from_authentication(self):
        row = source.verify_record({"name": self.archive.name, "disposition": "retain", "authentication": self.auth},
                                   self.cache, self.evidence, None)
        self.assertEqual(row["status"], "accepted-exception")
        self.assertEqual(row["authentication"]["status"], "accepted-exception")
        self.assertIn("required-package-tests", row["authentication"]["required_gates"])

    def test_wrong_bytes_or_neighbor_filename_cannot_use_policy(self):
        self.archive.write_bytes(b"changed patch")
        with self.assertRaises(source.Refusal):
            source.verify_patch_exception(self.archive, self.auth, self.evidence)
        neighbor = self.cache / "other.patch"
        neighbor.write_bytes(b"exact patch bytes\r\n")
        with self.assertRaises(source.Refusal):
            source.verify_patch_exception(neighbor, self.auth, self.evidence)

    def test_repinning_review_or_missing_corroboration_is_refused(self):
        self.auth["policy"]["sha256"] = "f" * 64
        with self.assertRaises(source.Refusal):
            source.verify_patch_exception(self.archive, self.auth, self.evidence)
        self.auth["policy"]["sha256"] = source.PATCH_POLICY_SHA256
        (self.evidence / "corroboration.json").unlink()
        with self.assertRaises(source.Refusal):
            source.verify_patch_exception(self.archive, self.auth, self.evidence)


class AdvisoryTests(PolicyFixture):
    def setUp(self):
        super().setUp()
        raw = ("<table><tr><th>ID</th><tr><td>sa-13.1-088</td><td>python</td>"
               "<td>2026-10-27</td><td>Medium</td></tr><tr><td colspan='4'>"
               "Python issue. Cross-reference sa-13.1-044 is not another record.</td></tr>"
               "<tr><td>sa-13.1-100</td><td>libarchive</td><td>2026-10-31</td><td>Medium</td></tr>"
               "<tr><td colspan='4'>Archive issue.</td></tr></table>").encode()
        snapshot = self.put("advisories.html", raw, "https://www.linuxfromscratch.org/advisories/index.php")
        proof = self.put("upstream.json", b'{"issue":"open"}\n')
        patch_input = self.put("python-3.14.10-security-backports.patch", b"fixture reviewed backport\n")
        patch_review = self.put("PYTHON-BACKPORT-REVIEW.json", b'{"decision":"fixture"}\n')
        self.approved_constant("PYTHON_BACKPORT_SHA256", patch_input["sha256"])
        self.approved_constant("PYTHON_BACKPORT_REVIEW_SHA256", patch_review["sha256"])
        def native(ref):
            return {"path": "tup/native/profiles/lfs-13.1-systemd/" + ref["path"], "sha256": ref["sha256"]}
        self.rows = [
            {"id": "sa-13.1-088", "package": "python", "disposition": "fixed-by-native-patch",
             "selected_sources": ["Python-3.14.10.tar.xz"], "reason": "reviewed exact backport",
             "evidence": [proof], "native_patch": native(patch_input), "native_review": native(patch_review)},
            {"id": "sa-13.1-100", "package": "libarchive", "disposition": "not-in-base",
             "selected_sources": [], "reason": "absent from scoped core", "evidence": []},
            {"id": "upstream-expat-2.10.0", "package": "expat", "disposition": "fixed-by-selection",
             "selected_sources": ["expat-2.10.0.tar.xz"], "reason": "selected fixes", "evidence": [proof]},
            {"id": "upstream-expat-CVE-2025-66382", "package": "expat", "disposition": "deferred-release-gate",
             "gate_id": "H55", "selected_sources": ["expat-2.10.0.tar.xz"], "reason": "still open", "evidence": [proof]}]
        self.review = {"status": "reviewed", "reviewed_at": "2026-11-05", "snapshot": snapshot,
                       "request": {"method": "POST", "fields": {"stype": "Book", "release": "13.1", "desc": "true", "submit": "Search"}},
                       "material_sha256": snapshot["sha256"],
                       "inventory_sha256": hashlib.sha256(source.encoded(source.advisory_inventory(raw))).hexdigest(),
                       "package_sources": {"python": ["Python-3.14.10.tar.xz"], "expat": ["expat-2.10.0.tar.xz"]},
                       "dispositions": self.rows}
        self.catalog = {"sources": [{"name": n} for n in ["Python-3.14.10.tar.xz", "expat-2.10.0.tar.xz"]],
                        "advisory_review": self.review}

    def verify(self):
        return source.verify_advisory_review(self.catalog, self.evidence)

    def test_complete_review_authorizes_only_build_not_release(self):
        result = self.verify()
        self.assertEqual(result["snapshot_count"], 2)
        self.assertEqual(result["lock_purpose"], "build-only")
        self.assertFalse(result["release_eligible"])
        self.assertEqual(result["release_gates"][0]["id"], "H55")

    def test_partial_duplicate_and_unknown_advisories_are_refused(self):
        for rows in (self.rows[:-1], self.rows + [self.rows[0]],
                     self.rows + [{**self.rows[-1], "id": "unreviewed"}]):
            with self.subTest(rows=rows), self.assertRaises(source.Refusal):
                self.review["dispositions"] = rows
                self.verify()

    def test_unreviewed_deferral_and_false_fixed_residual_are_refused(self):
        for change in ({"gate_id": "other"}, {"disposition": "fixed-by-selection"},
                       {"selected_sources": ["Python-3.14.10.tar.xz"]}):
            self.review["dispositions"] = copy.deepcopy(self.rows)
            self.review["dispositions"][-1].update(change)
            with self.subTest(change=change), self.assertRaises(source.Refusal):
                self.verify()

    def test_mutated_or_missing_backport_review_is_refused(self):
        (self.evidence / "python-3.14.10-security-backports.patch").write_bytes(b"different")
        with self.assertRaises(source.Refusal):
            self.verify()
        self.rows[0]["native_patch"]["sha256"] = source.digest(self.evidence / "python-3.14.10-security-backports.patch")
        with self.assertRaises(source.Refusal):
            self.verify()

    def test_python_archive_alone_cannot_claim_the_backport_fixes(self):
        self.rows[0]["disposition"] = "fixed-by-selection"
        with self.assertRaises(source.Refusal):
            self.verify()

    def test_base_package_cannot_be_dismissed_as_outside_scope(self):
        self.rows[0].update(disposition="not-in-base", selected_sources=[])
        with self.assertRaises(source.Refusal):
            self.verify()

    def test_snapshot_or_query_or_package_scope_mutation_is_refused(self):
        for change in ({"inventory_sha256": "0" * 64}, {"request": {"method": "GET"}},
                       {"package_sources": {"expat": ["expat-2.10.0.tar.xz"]}}, {"reviewed_at": "2020-01-01"}):
            original = self.catalog["advisory_review"]
            self.catalog["advisory_review"] = {**original, **change}
            with self.subTest(change=change), self.assertRaises(source.Refusal):
                self.verify()
            self.catalog["advisory_review"] = original

    def test_duplicate_or_truncated_html_record_is_refused(self):
        raw = (self.evidence / "advisories.html").read_bytes()
        for changed in (raw + raw, raw[:raw.index(b"Python issue.")]):
            with self.subTest(changed=changed), self.assertRaises(source.Refusal):
                source.advisory_inventory(changed)


class EquivalenceTests(PolicyFixture):
    def setUp(self):
        super().setUp()
        self.archive = self.cache / "make-4.4.1.tar.gz"
        self.archive.write_bytes(gzip.compress(b"whole tar bytes\0\0"))
        self.reference = self.cache / "make-4.4.1.tar.lz"
        self.reference.write_bytes(b"fixture reference")
        self.auth = {"method": "distributor-openpgp-tar-equivalence",
                     "reference_archive": {"path": self.reference.name, "url": "https://publisher.invalid/reference",
                                           "sha256": source.digest(self.reference)},
                     "reference_authentication": {"method": "distributor-openpgp-manifest"}}

    def verify(self, payload=b"whole tar bytes\0\0"):
        with patch.object(source, "verify_distributor", return_value={"trust_class": "distributor-openpgp-manifest"}), \
             patch.object(source, "lzip_tar_identity", return_value=(len(payload), hashlib.sha256(payload).hexdigest(), "a" * 64)):
            return source.verify_tar_equivalence(self.archive, self.auth, self.cache, self.evidence, None, {})

    def test_whole_tar_identity_has_distinct_assurance(self):
        result = self.verify()
        self.assertEqual(result["trust_class"], "distributor-openpgp-tar-equivalence")
        self.assertEqual(result["reference_authentication"]["status"], "verified")
        self.assertEqual(result["reference_authentication"]["evidence_sha256"],
                         hashlib.sha256(source.encoded(self.auth["reference_authentication"])).hexdigest())

    def test_payload_difference_or_unapproved_reference_fails(self):
        with self.assertRaises(source.Refusal):
            self.verify(b"different tar bytes")
        self.auth["reference_authentication"]["method"] = "unresolved"
        with self.assertRaises(source.Refusal):
            self.verify()

    def test_actual_decoder_and_snapshot_verification_are_required(self):
        with self.assertRaises(source.Refusal):
            source.lzip_tar_identity(self.reference, None)
        with patch.object(source, "verify_distributor", side_effect=source.Refusal("bad signed snapshot")):
            with self.assertRaisesRegex(source.Refusal, "signed snapshot"):
                source.verify_tar_equivalence(self.archive, self.auth, self.cache, self.evidence, None, {})


class DocumentationTests(PolicyFixture):
    def write(self, member):
        path = self.cache / "manuals.tar.xz"
        with tarfile.open(path, "w:xz") as bundle:
            bundle.addfile(member, io.BytesIO(b"x") if member.isfile() else None)
        return path

    def test_regular_manual_is_inventoried_by_raw_content(self):
        member = tarfile.TarInfo("systemd-man-pages-261.2/man1/a.1")
        member.mode, member.size = 0o644, 1
        rows = source.documentation_members(self.write(member))
        self.assertEqual(rows[0]["sha256"], hashlib.sha256(b"x").hexdigest())

    def test_link_traversal_executable_or_nonmanual_file_is_refused(self):
        for name, mode, kind in (("systemd-man-pages-261.2/man1/../../a.1", 0o644, tarfile.REGTYPE),
                                 ("systemd-man-pages-261.2/man1/a.1", 0o755, tarfile.REGTYPE),
                                 ("systemd-man-pages-261.2/man1/a.1", 0o644, tarfile.SYMTYPE),
                                 ("systemd-man-pages-261.2/bin/a", 0o644, tarfile.REGTYPE)):
            member = tarfile.TarInfo(name)
            member.mode, member.type, member.size = mode, kind, 1 if kind == tarfile.REGTYPE else 0
            member.linkname = "/outside" if kind == tarfile.SYMTYPE else ""
            with self.subTest(name=name, kind=kind), self.assertRaises(source.Refusal):
                source.documentation_members(self.write(member))


class DistributorExceptionTests(PolicyFixture):
    def setUp(self):
        super().setUp()
        self.archive = self.cache / "fixture.tar.gz"
        self.archive.write_bytes(b"fixture exact source")
        value = hashlib.sha512(self.archive.read_bytes()).hexdigest()
        distinfo = self.put("distinfo", (f"SHA512 ({self.archive.name}) = {value}\n"
                                       f"Size ({self.archive.name}) = {self.archive.stat().st_size} bytes\n").encode())
        self.policy = {"decision": "approved-exact-provenance-exceptions", "sources": [{
            "name": self.archive.name, "sha256": source.digest(self.archive), "size": self.archive.stat().st_size,
            "proposed_class": "reviewed-distributor-https-exception", "material": distinfo,
            "published_sha512": value, "distributor": "NetBSD pkgsrc", "assurance": "fixture lower assurance"}]}
        reviewed = self.put("policy.json", source.encoded(self.policy))
        self.approved_constant("SOURCE_POLICY_SHA256", reviewed["sha256"])
        self.auth = {"method": "reviewed-distributor-https-exception", "policy": reviewed, "material": distinfo}

    def test_exact_published_size_and_digest_remain_an_exception(self):
        checked = source.verify_source_exception(self.archive, self.auth, self.evidence)
        self.assertEqual(checked["status"], "accepted-exception")
        self.assertEqual(checked["source_digest_algorithm"], "sha512")

    def test_missing_or_changed_distinfo_and_wrong_name_are_refused(self):
        original = (self.evidence / "distinfo").read_bytes()
        (self.evidence / "distinfo").write_bytes(original.replace(b"SHA512", b"SHA1"))
        with self.assertRaises(source.Refusal):
            source.verify_source_exception(self.archive, self.auth, self.evidence)
        (self.evidence / "distinfo").write_bytes(original)
        other = self.cache / "other.tar.gz"
        other.write_bytes(self.archive.read_bytes())
        with self.assertRaises(source.Refusal):
            source.verify_source_exception(other, self.auth, self.evidence)
        (self.evidence / "distinfo").unlink()
        with self.assertRaises(source.Refusal):
            source.verify_source_exception(self.archive, self.auth, self.evidence)

    def test_changed_policy_cannot_expand_exact_source_set(self):
        self.policy["sources"][0]["sha256"] = "c" * 64
        (self.evidence / "policy.json").write_bytes(source.encoded(self.policy))
        self.auth["policy"]["sha256"] = source.digest(self.evidence / "policy.json")
        with self.assertRaises(source.Refusal):
            source.verify_source_exception(self.archive, self.auth, self.evidence)


if __name__ == "__main__":
    unittest.main()
