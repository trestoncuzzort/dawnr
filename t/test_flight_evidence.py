#!/usr/bin/env python3
"""Reviewed source digests and path-free receipts must reject mismatched or incomplete evidence."""
from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "flight"))
import evidence  # noqa: E402
import px4_diff as diff  # noqa: E402
import px4_stmt as stmt  # noqa: E402


class SourceIdentity(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = b"int value() { return 3; }\n"
        self.revision = "1" * 40
        self.relative = "src/value.cpp"
        self.records = [{"repository": repo, "revision": self.revision, "path": self.relative,
                         "sha256": evidence.digest(self.data), "bytes": len(self.data)}
                        for repo in ("upstream/core", "fork/core")]
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({"schema": 1, "sources": self.records}))
        self.cache = evidence.SourceCache(self.root / "cache", self.manifest)

    def destination(self, repo="upstream/core"):
        return self.cache.root / repo / self.revision / self.relative

    def get(self, repo="upstream/core", **kwargs):
        return self.cache.get(repo, self.revision, self.relative, **kwargs)

    def install(self, data=None, repo="upstream/core"):
        destination = self.destination(repo)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.data if data is None else data)
        return destination

    def test_matching_cache_is_usable_with_network_disabled(self):
        self.install()
        with patch.object(evidence.urllib.request, "urlopen", side_effect=AssertionError("network forbidden")):
            self.assertEqual(self.get().read_bytes(), self.data)

    def test_tampered_cached_bytes_are_refused_without_replacement(self):
        destination = self.install(self.data.replace(b"3", b"4"))
        with patch.object(evidence.urllib.request, "urlopen", side_effect=AssertionError("network forbidden")):
            with self.assertRaisesRegex(ValueError, "cached source digest mismatch"):
                self.get()
        self.assertEqual(destination.read_bytes(), self.data.replace(b"3", b"4"))

    def test_truncated_wrong_and_oversized_downloads_are_not_installed(self):
        for content in (self.data[:-1], self.data.replace(b"3", b"4"), self.data + b"extra"):
            with self.subTest(content=content), patch.object(evidence.urllib.request, "urlopen", return_value=io.BytesIO(content)):
                with self.assertRaisesRegex(ValueError, "downloaded source digest mismatch"):
                    self.get()
            self.assertFalse(self.destination().exists())
            self.assertEqual(list(self.cache.root.rglob("*.tmp")), [])

    def test_valid_download_is_installed_at_once(self):
        with patch.object(evidence.urllib.request, "urlopen", return_value=io.BytesIO(self.data)), \
                patch.object(evidence.os, "replace", wraps=evidence.os.replace) as replace:
            self.assertEqual(self.get().read_bytes(), self.data)
        replace.assert_called_once()
        self.assertEqual(list(self.cache.root.rglob("*.tmp")), [])

    def test_failed_atomic_install_leaves_no_partial_destination(self):
        with patch.object(evidence.urllib.request, "urlopen", return_value=io.BytesIO(self.data)), \
                patch.object(evidence.os, "replace", side_effect=OSError("test disk failure")):
            with self.assertRaises(OSError):
                self.get()
        self.assertFalse(self.destination().exists())
        self.assertEqual(list(self.cache.root.rglob("*.tmp")), [])

    def test_repositories_have_distinct_cache_locations(self):
        first = self.install()
        second = self.install(repo="fork/core")
        first.write_bytes(b"corrupt")
        with patch.object(evidence.urllib.request, "urlopen", side_effect=AssertionError("network forbidden")):
            self.assertEqual(self.get("fork/core"), second)
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                self.get()
        self.assertNotEqual(first, second)

    def test_legacy_cache_migrates_only_after_matching_the_manifest(self):
        legacy = self.root / "old.cpp"
        legacy.write_bytes(self.data)
        with patch.object(evidence.urllib.request, "urlopen", side_effect=AssertionError("network forbidden")):
            self.assertEqual(self.get(legacy=legacy).read_bytes(), self.data)
        legacy.write_bytes(b"wrong")
        with self.assertRaisesRegex(ValueError, "cached source digest mismatch"):
            self.get("fork/core", legacy=legacy)
        self.assertFalse(self.destination("fork/core").exists())

    def test_unregistered_source_never_fetches(self):
        with patch.object(evidence.urllib.request, "urlopen") as request:
            with self.assertRaisesRegex(ValueError, "reviewed digest"):
                self.get("unknown/core")
            request.assert_not_called()

    def test_traversal_and_abbreviated_revisions_are_refused(self):
        for repo, rev, path in (("../core", self.revision, self.relative),
                                ("upstream/core", "main", self.relative),
                                ("upstream/core", self.revision, "../outside"),
                                ("upstream/core", self.revision, "/absolute")):
            with self.subTest(repo=repo, rev=rev, path=path), self.assertRaises(ValueError):
                self.cache.get(repo, rev, path)

    def test_duplicate_manifest_record_is_refused(self):
        self.manifest.write_text(json.dumps({"schema": 1, "sources": self.records + self.records[:1]}))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evidence.SourceCache(self.cache.root, self.manifest)


class ManifestCoverage(unittest.TestCase):
    def test_all_registered_native_sources_have_expected_digests(self):
        cache = evidence.SourceCache(Path("unused"))
        expected = {("PX4/PX4-Autopilot", diff.PX4_COMMIT, path) for path in diff.HEADERS
                    + [f"src/lib/matrix/matrix/{name}.hpp" for name in diff.MATRIX] + ["LICENSE"]}
        for spec in stmt.PAIRS.values():
            expected.add(("PX4/PX4-Autopilot", spec.get("pinned", diff.PX4_COMMIT), spec["file"]))
            expected.add((stmt.FORK, spec["fix_commit"], spec["file"]))
        self.assertEqual(set(cache.records), expected)


class ReceiptIdentity(unittest.TestCase):
    def make_case(self, *, task=None, inputs=None, wrapper="int main() {}", flags=None, source=b"task bytes"):
        receipt = evidence.Receipt("test")
        token = evidence.ACTIVE.set(receipt)
        try:
            evidence.start_case("sample", task or {"name": "sample"}, inputs or [{"x": 1}], wrapper,
                                task_bytes=source, flags=flags or ["-O1"])
            evidence.finish_case({"status": "agrees", "points": 1, "returned_rows": 1})
        finally:
            evidence.ACTIVE.reset(token)
        return receipt.data["cases"][0]

    def test_changed_task_source_ast_input_wrapper_and_flags_change_their_identity(self):
        baseline = self.make_case()
        for field, changed in (("task_ast_sha256", self.make_case(task={"name": "changed"})),
                ("task_source_sha256", self.make_case(source=b"other task bytes")),
                ("inputs_sha256", self.make_case(inputs=[{"x": 2}])),
                ("wrapper_sha256", self.make_case(wrapper="int main() { return 1; }")),
                ("compiler_flags", self.make_case(flags=["-O2"]))):
            with self.subTest(field=field):
                self.assertNotEqual(baseline[field], changed[field])

    def test_matching_identities_ignore_dictionary_key_order(self):
        self.assertEqual(evidence.object_digest({"x": 1, "y": 2}), evidence.object_digest({"y": 2, "x": 1}))

    def test_process_failure_and_sensitive_diagnostics_are_hashed_not_embedded(self):
        receipt = evidence.Receipt("test")
        token = evidence.ACTIVE.set(receipt)
        try:
            evidence.start_case("sample", {}, [1], "code")
            outcome = subprocess.CompletedProcess(["/private/machine/tool"], 7, "1\n", "/private/machine: secret")
            evidence.process_result("runtime", outcome.args, result=outcome, stdin="1\n2\n")
            evidence.finish_case({"status": "runtime error: /private/machine diagnostic"})
        finally:
            evidence.ACTIVE.reset(token)
        text = json.dumps(receipt.data)
        self.assertNotIn("/private", text)
        self.assertNotIn("secret", text)
        event = receipt.data["cases"][0]["processes"][0]
        self.assertEqual(event["outcome"], "failed")
        self.assertEqual(event["exit_code"], 7)
        self.assertEqual(event["stdout_lines"], 1)
        self.assertEqual(event["stdin_sha256"], evidence.digest(b"1\n2\n"))

    def test_failed_run_still_writes_an_error_receipt_and_restores_context(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            with self.assertRaisesRegex(RuntimeError, "test failure"):
                with evidence.recording(path, "test"):
                    raise RuntimeError("test failure with /private/path")
            result = json.loads(path.read_text())
            self.assertEqual(result["run_outcome"], "error")
            self.assertEqual(result["error_kind"], "RuntimeError")
            self.assertNotIn("/private", path.read_text())
            self.assertIsNone(evidence.ACTIVE.get())

    def test_working_tree_hashes_are_explicitly_unverified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.cpp").write_text("int value = 1;\n")
            with evidence.recording(root / "receipt.json", "test"):
                evidence.observed_tree(root, ["source.cpp"])
            row = json.loads((root / "receipt.json").read_text())["sources"][0]
            self.assertEqual(row["identity_scope"], "observed_working_tree_bytes")
            self.assertEqual(row["revision"], "unverified")


if __name__ == "__main__":
    unittest.main()
