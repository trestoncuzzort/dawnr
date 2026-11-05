"""Host-independent refusal/receipt fixtures; these do not boot or build LFS."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


MODULE = Path(__file__).resolve().parents[1] / "native/build.py"
SPEC = importlib.util.spec_from_file_location("native_build", MODULE)
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class NativeBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="tup-native-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.book = self.base / "book"
        self.book.mkdir()
        (self.book / "BOOK-SOURCE").write_bytes(
            b"arch=x86_64\nbase=https://www.linuxfromscratch.org/lfs/view/12.4/\n")
        for chapter in ("ch05", "ch06", "ch07", "ch08"):
            (self.book / chapter).mkdir()
        (self.book / "ch05/01-package.sh").write_bytes(b"# TUP_TARBALL=fixture.tar.xz\ntrue\n")
        self.cache = self.base / "cache"
        self.cache.mkdir()
        (self.cache / "fixture.tar.xz").write_bytes(b"fixture source bytes\r\n")
        self.lock = {
            "schema": "tup-source-lock-v1", "architecture": "x86_64",
            "book_source_sha256": build.digest(self.book / "BOOK-SOURCE"),
            "provenance": "test-only independently supplied fixture digest",
            "sources": [{"name": "fixture.tar.xz", "url": "https://example.invalid/fixture.tar.xz",
                         "sha256": build.digest(self.cache / "fixture.tar.xz")}],
        }
        self.lock_path = self.base / "sources.lock.json"
        self.state = self.base / "state"
        self.state.mkdir()
        self.identity = hashlib.sha256(b"fixture identity").hexdigest()

    def write_lock(self):
        self.lock_path.write_bytes(build.encoded(self.lock))
        return build.digest(self.lock_path)

    def test_pinned_original_bytes_accept_and_tampered_archive_refuses(self):
        lock = build.load_lock(self.lock_path, self.write_lock(), self.book)
        build.verify_sources(self.cache, lock)
        (self.cache / "fixture.tar.xz").write_bytes(b"fixture source bytes\n")
        with self.assertRaisesRegex(build.Refusal, "mismatched source"):
            build.verify_sources(self.cache, lock)

    def test_observed_lock_changes_do_not_update_expected_pin(self):
        expected = self.write_lock()
        self.lock["provenance"] = "changed after authentication"
        self.write_lock()
        with self.assertRaisesRegex(build.Refusal, "source-lock SHA256 mismatch"):
            build.load_lock(self.lock_path, expected, self.book)

    def test_wrong_architecture_and_missing_book_archive_refuse(self):
        self.lock["architecture"] = "arm64"
        with self.assertRaisesRegex(build.Refusal, "not for x86_64"):
            build.load_lock(self.lock_path, self.write_lock(), self.book)
        self.lock["architecture"] = "x86_64"
        self.lock["sources"][0]["name"] = "other.tar.xz"
        with self.assertRaisesRegex(build.Refusal, "omits book archives"):
            build.load_lock(self.lock_path, self.write_lock(), self.book)

    def test_source_traversal_duplicate_and_insecure_url_refuse(self):
        self.lock["sources"][0]["name"] = "../escape.tar.xz"
        with self.assertRaisesRegex(build.Refusal, "unsafe source basename"):
            build.load_lock(self.lock_path, self.write_lock(), self.book)
        self.lock["sources"][0]["name"] = "fixture.tar.xz"
        self.lock["sources"].append(dict(self.lock["sources"][0]))
        with self.assertRaisesRegex(build.Refusal, "duplicate"):
            build.load_lock(self.lock_path, self.write_lock(), self.book)
        self.lock["sources"].pop()
        self.lock["sources"][0]["url"] = "http://example.invalid/source"
        with self.assertRaisesRegex(build.Refusal, "HTTPS"):
            build.load_lock(self.lock_path, self.write_lock(), self.book)

    def test_source_lock_cannot_be_reused_with_changed_book(self):
        expected = self.write_lock()
        (self.book / "BOOK-SOURCE").write_bytes(b"arch=x86_64\nchanged-book\n")
        with self.assertRaisesRegex(build.Refusal, "different book"):
            build.load_lock(self.lock_path, expected, self.book)

    def test_source_symlink_refuses_even_when_content_matches(self):
        source = self.cache / "fixture.tar.xz"
        real = self.base / "original.tar.xz"
        source.rename(real)
        try:
            source.symlink_to(real)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        with self.assertRaisesRegex(build.Refusal, "mismatched source"):
            build.verify_sources(self.cache, self.lock)

    def test_staged_extra_patch_and_changed_manifest_refuse(self):
        (self.cache / "log").mkdir()
        manifest = self.cache / "SHA256-MANIFEST-NATIVE.txt"
        manifest.write_bytes(build.manifest_bytes(self.lock))
        build.verify_sources(self.cache, self.lock, staged=True)
        extra = self.cache / "untrusted.patch"
        extra.write_bytes(b"unlisted patch")
        with self.assertRaisesRegex(build.Refusal, "unlisted"):
            build.verify_sources(self.cache, self.lock, staged=True)
        extra.unlink()
        manifest.write_bytes(b"changed manifest")
        with self.assertRaisesRegex(build.Refusal, "manifest changed"):
            build.verify_sources(self.cache, self.lock, staged=True)

    def test_book_architecture_and_unsupported_release_refuse(self):
        for metadata, reason in (
            (b"arch=arm64\nbase=https://www.linuxfromscratch.org/lfs/view/12.4/\n", "x86_64"),
            (b"arch=x86_64\nbase=https://www.linuxfromscratch.org/lfs/view/13.1-systemd/\n", "unsupported extracted book"),
        ):
            with self.subTest(metadata=metadata):
                (self.book / "BOOK-SOURCE").write_bytes(metadata)
                self.lock["book_source_sha256"] = build.digest(self.book / "BOOK-SOURCE")
                with self.assertRaisesRegex(build.Refusal, reason):
                    build.load_lock(self.lock_path, self.write_lock(), self.book)

    def test_workspace_cannot_overlap_source_or_cache(self):
        workspace = self.base / "build"
        workspace.mkdir()
        with self.assertRaisesRegex(build.Refusal, "disjoint"):
            build.validate_workspace(workspace, workspace / "checkout", self.cache)
        with self.assertRaisesRegex(build.Refusal, "disjoint"):
            build.validate_workspace(workspace, self.book, self.base)
        build.validate_workspace(workspace, self.book, self.cache)

    def test_crlf_build_scripts_refuse_without_normalizing_evidence(self):
        script = self.base / "page.sh"
        script.write_bytes(b"true\r\n")
        with self.assertRaisesRegex(build.Refusal, "CRLF"):
            build.map_identity({"book/ch05/page.sh": script})
        self.assertEqual(script.read_bytes(), b"true\r\n")

    def test_explicit_book_and_native_override_are_bound_and_staged_changes_refuse(self):
        source = self.base / "source"
        source.mkdir()
        (source / "driver.sh").write_bytes(b"true\n")
        for name in ("overrides", "buildlib", "native/profiles/x86_64/overrides/x86_64/ch08"):
            (source / name).mkdir(parents=True, exist_ok=True)
        (source / "buildlib/state.sh").write_bytes(b"true\n")
        (source / "native/profiles/x86_64/overrides/x86_64/ch08/shadow.sh").write_bytes(b"passwd -l root\n")
        names = ["01-introduction.sh", "02-changingowner.sh", "03-kernfs.sh", "04-chroot.sh",
                 "05-creatingdirs.sh", "06-createfiles.sh", "07-gettext.sh", "08-bison.sh",
                 "09-perl.sh", "10-Python.sh", "11-texinfo.sh", "12-util-linux.sh", "13-cleanup.sh"]
        (self.book / "ch07/ORDER").write_bytes(("\n".join(names) + "\n").encode())
        for name in names:
            (self.book / "ch07" / name).write_bytes(b"true\n")
        files = build.input_map(source, self.book)
        self.assertEqual(files["book/BOOK-SOURCE"], self.book / "BOOK-SOURCE")
        self.assertEqual(files["overrides/x86_64/ch08/shadow.sh"].read_bytes(), b"passwd -l root\n")
        inputs = {"inputs": build.map_identity(files)}
        staged = self.base / "root/tup-build"
        for name, item in files.items():
            path = staged / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(item if isinstance(item, bytes) else item.read_bytes())
            path.chmod(0o755 if name.endswith(".sh") else 0o644)
        (staged / "BUILD-INPUTS.json").write_bytes(build.encoded(inputs))
        build.verify_staged(staged.parent, inputs)
        (staged / "overrides/x86_64/ch08/shadow.sh").write_bytes(b"changed\n")
        with self.assertRaisesRegex(build.Refusal, "staged build input changed"):
            build.verify_staged(staged.parent, inputs)
        # Still eight numeric05-12 pages, but a newly inserted package must not disappear.
        changed = names[:-1] + ["13-new-package.sh", "14-cleanup.sh"]
        (self.book / "ch07/ORDER").write_bytes(("\n".join(changed) + "\n").encode())
        with self.assertRaisesRegex(build.Refusal, "chapter 7 inner selection changed"):
            build.input_map(source, self.book)

    def test_failed_child_has_failed_receipt_and_no_successful_resume(self):
        command = [sys.executable, "-c", "print('controlled failure'); raise SystemExit(17)"]
        with self.assertRaisesRegex(build.Refusal, "exit 17"):
            build.run_stage(self.state, "ch05", command, self.identity)
        receipt = json.loads((self.state / "ch05.json").read_bytes())
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["exit_code"], 17)
        with self.assertRaisesRegex(build.Refusal, "failed attempt"):
            build.run_stage(self.state, "ch05", [sys.executable, "-c", "raise SystemExit(0)"], self.identity)

    def test_success_requires_same_inputs_unchanged_log_and_ledger_validation(self):
        marker = self.base / "executed"
        command = [sys.executable, "-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()", str(marker)]
        build.run_stage(self.state, "ch05", command, self.identity)
        marker.unlink()
        build.run_stage(self.state, "ch05", command, self.identity,
                        [sys.executable, "-c", "raise SystemExit(0)"])
        self.assertFalse(marker.exists(), "completed stage must not replay package commands")
        with self.assertRaisesRegex(build.Refusal, "command failed"):
            build.run_stage(self.state, "ch05", command, self.identity,
                            [sys.executable, "-c", "raise SystemExit(9)"])
        with self.assertRaisesRegex(build.Refusal, "changed inputs"):
            build.stage_record(self.state, "ch05", "0" * 64)
        (self.state / "ch05.log").write_bytes(b"changed evidence")
        with self.assertRaisesRegex(build.Refusal, "log is missing or changed"):
            build.stage_record(self.state, "ch05", self.identity)

    def test_receipt_fsync_failure_prevents_child_execution(self):
        marker = self.base / "must-not-run"
        command = [sys.executable, "-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()", str(marker)]
        with patch.object(build.os, "fsync", side_effect=OSError("injected full disk")):
            with self.assertRaisesRegex(OSError, "full disk"):
                build.run_stage(self.state, "ch05", command, self.identity)
        self.assertFalse(marker.exists())
        self.assertFalse((self.state / "ch05.json").exists())

    def test_receipt_failure_after_execution_retains_uncertain_intent(self):
        real_atomic = build.atomic_json
        calls = 0

        def fail_completion(path, value):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected completion persistence failure")
            real_atomic(path, value)

        with patch.object(build, "atomic_json", side_effect=fail_completion):
            with self.assertRaisesRegex(OSError, "persistence failure"):
                build.run_stage(self.state, "ch05", [sys.executable, "-c", "print('ran')"], self.identity)
        self.assertEqual(build.read_json(self.state / "ch05.json")["status"], "running")
        with self.assertRaisesRegex(build.Refusal, "interrupted/failed"):
            build.stage_record(self.state, "ch05", self.identity)

    def test_input_change_cannot_be_authorized_by_stage_marker(self):
        old = {"profile": "native", "source": "old"}
        with self.assertRaisesRegex(build.Refusal, "inputs changed"):
            build.require_identity(old, {"profile": "native", "source": "new"})

    def test_non_linux_and_arm_hosts_refuse(self):
        for system, architecture in (("Windows", "AMD64"), ("Linux", "aarch64")):
            with self.subTest(system=system, architecture=architecture):
                with patch.object(build.platform, "system", return_value=system), \
                     patch.object(build.platform, "machine", return_value=architecture):
                    with self.assertRaisesRegex(build.Refusal, "Linux x86_64"):
                        build.host_identity(self.base, 4, 6144, 40)


if __name__ == "__main__":
    unittest.main()
