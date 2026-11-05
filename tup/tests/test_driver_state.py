"""Disposable driver fixtures; no chroot, mount, download, or real package build.

Run: python -m unittest discover -s tup/tests -p 'test_driver*.py' -v
TUP_TEST_BASH selects Bash on Windows; TUP_DRIVER_UNDER_TEST can select an old
driver for negative-control reproduction. Windows runs use a sync shim because
MSYS fsync on regular files fails with EACCES: these exercise the protocol and
injected errors, NOT Linux filesystem durability. Linux uses real GNU sync.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import tarfile
import tempfile
import time
import unittest


TUP = Path(__file__).resolve().parents[1]
BASH = os.environ.get("TUP_TEST_BASH") or shutil.which("bash")
DRIVER = Path(os.environ.get("TUP_DRIVER_UNDER_TEST", TUP / "driver.sh"))


def shell_path(path: Path) -> str:
    value = path.resolve().as_posix()
    if os.name == "nt":
        return "/" + value[0].lower() + value[2:]
    return value


@unittest.skipUnless(BASH, "Bash is required for driver fixture tests")
class DriverStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tup-driver-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lfs = self.root / "target"
        self.sources = self.lfs / "sources"
        self.log = self.sources / "log"
        self.log.mkdir(parents=True)
        self.chapter = self.root / "book" / "ch05"
        self.chapter.mkdir(parents=True)
        self.overrides = self.root / "overrides"
        self.overrides.mkdir()
        self.program = self.root / "program"
        self.program.mkdir()
        shutil.copyfile(DRIVER, self.program / "driver.sh")
        if (TUP / "buildlib").is_dir():
            shutil.copytree(TUP / "buildlib", self.program / "buildlib")
        self.inputs = self.root / "BUILD-INPUTS.json"
        self.inputs.write_text('{"schema":"tup.native.inputs.v1","fixture":true}\n', encoding="utf-8", newline="\n")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, LFS=shell_path(self.lfs),
                        TUP_ARCH="x86_64", TUP_PROFILE="fixture",
                        TUP_BUILD_INPUTS=shell_path(self.inputs),
                        TUP_OVERRIDES=shell_path(self.overrides),
                        TUP_TESTS="glibc gcc binutils", MAKEFLAGS="-j1")
        # A deterministic protocol-only adapter on MSYS, never a production
        # option or a substitute for the Linux durability gate.
        if os.name == "nt":
            self.shim("sync", "exit 0\n")
        # Windows environment names are case-insensitive; do not pass both
        # inherited Path and a distinct PATH to CreateProcess/MSYS.
        path_key = next((key for key in self.env if key.upper() == "PATH"), "PATH")
        search_path = self.env.pop(path_key, "")
        self.env["PATH"] = str(self.bin) + os.pathsep + search_path
        self.page("01-demo.sh", 'printf "ran\\n" >> "$LFS/sources/ran"\n')

    def shim(self, name: str, body: str):
        path = self.bin / name
        path.write_text("#!/bin/bash\n" + body, encoding="utf-8", newline="\n")
        path.chmod(0o755)

    def page(self, name: str, body: str, *, order: bool = True):
        path = self.chapter / name
        path.write_text("#!/bin/bash\n" + body, encoding="utf-8", newline="\n")
        if order:
            (self.chapter / "ORDER").write_text(name + "\n", encoding="utf-8", newline="\n")
        return path

    def command(self):
        # Git for Windows' launcher prepends /usr/bin before the inherited
        # PATH, so install fixture shims after entering Bash as on Linux.
        return [BASH, "-c", 'export PATH="$1:$PATH"; shift; exec bash "$@"',
                "driver-fixture", shell_path(self.bin),
                shell_path(self.program / "driver.sh"), shell_path(self.chapter)]

    def run_driver(self):
        return subprocess.run(self.command(), env=self.env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=40)

    def successful(self):
        result = self.run_driver()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("ch05 complete", result.stdout)
        return result

    def refused(self):
        result = self.run_driver()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("ch05 complete", result.stdout)
        return result

    def executions(self):
        marker = self.sources / "ran"
        return marker.read_text().splitlines() if marker.exists() else []

    def receipt_rows(self):
        return [json.loads(line) for line in (self.log / "receipts.jsonl").read_text().splitlines()]

    def test_identical_resume_does_not_execute_again(self):
        self.successful()
        before = (self.log / "receipts.jsonl").read_bytes()
        self.successful()
        self.assertEqual(self.executions(), ["ran"])
        self.assertEqual(before, (self.log / "receipts.jsonl").read_bytes())

    def test_changed_script_refuses_instead_of_skipping_or_replaying(self):
        self.successful()
        self.page("01-demo.sh", 'printf "changed\\n" >> "$LFS/sources/ran"\n')
        self.refused()
        self.assertEqual(self.executions(), ["ran"])

    def test_receipt_directory_refuses_before_page_runs(self):
        (self.log / "receipts.jsonl").mkdir()
        self.refused()
        self.assertEqual(self.executions(), [])
        self.assertFalse((self.log / "driver.state").exists())

    def test_state_directory_refuses_before_page_runs(self):
        (self.log / "driver.state").mkdir()
        self.refused()
        self.assertEqual(self.executions(), [])

    def test_missing_build_inputs_refuses_before_page_runs(self):
        self.inputs.unlink()
        self.refused()
        self.assertEqual(self.executions(), [])

    def test_changed_manifest_or_profile_or_policy_refuses(self):
        self.successful()
        original = self.inputs.read_bytes()
        self.inputs.write_bytes(original + b" ")
        self.refused()
        self.inputs.write_bytes(original)
        for key in ("TUP_PROFILE", "TUP_TESTS", "MAKEFLAGS", "TESTSUITEFLAGS", "CFLAGS", "TUP_ARCH"):
            with self.subTest(key=key):
                previous = self.env.get(key)
                self.env[key] = "different"
                self.refused()
                if previous is None:
                    del self.env[key]
                else:
                    self.env[key] = previous
        self.assertEqual(self.executions(), ["ran"])

    def test_changed_book_beneath_override_or_shared_helper_refuses(self):
        override = self.overrides / "demo.sh"
        override.write_text('#!/bin/bash\nbash -e "$TUP_PAGE"\n', encoding="utf-8", newline="\n")
        override.chmod(0o755)
        helper = self.overrides / "lib.sh"
        helper.write_text("# shared helper\n", encoding="utf-8", newline="\n")
        self.successful()
        self.page("01-demo.sh", 'printf "changed\\n" >> "$LFS/sources/ran"\n')
        self.refused()
        self.page("01-demo.sh", 'printf "ran\\n" >> "$LFS/sources/ran"\n')
        helper.write_text("# changed transitive helper\n", encoding="utf-8", newline="\n")
        self.refused()
        self.assertEqual(self.executions(), ["ran"])

    def test_changed_order_refuses_before_new_page(self):
        self.page("02-next.sh", 'printf "next\\n" >> "$LFS/sources/ran"\n', order=False)
        self.successful()
        (self.chapter / "ORDER").write_text("01-demo.sh\n02-next.sh\n", encoding="utf-8", newline="\n")
        self.refused()
        self.assertEqual(self.executions(), ["ran"])

    def archive(self, content: bytes):
        with tarfile.open(self.sources / "demo.tar", "w") as archive:
            entry = tarfile.TarInfo("demo/input")
            entry.size = len(content)
            archive.addfile(entry, io.BytesIO(content))

    def test_changed_tarball_refuses(self):
        self.page("01-demo.sh", '# TUP_TARBALL=demo.tar\nprintf "ran\\n" >> "$LFS/sources/ran"\n')
        self.archive(b"first")
        self.successful()
        self.archive(b"second")
        self.refused()
        self.assertEqual(self.executions(), ["ran"])

    def test_legacy_state_and_receipts_are_preserved_but_not_resumed(self):
        state = b"ch05/01-demo.sh\n"
        receipt = b'{"page":"ch05/01-demo.sh","exit":0,"seconds":1}\n'
        (self.log / "driver.state").write_bytes(state)
        (self.log / "receipts.jsonl").write_bytes(receipt)
        self.refused()
        self.assertEqual((self.log / "driver.state").read_bytes(), state)
        self.assertEqual((self.log / "receipts.jsonl").read_bytes(), receipt)
        self.assertEqual(self.executions(), [])

    def test_legacy_orphan_log_cannot_be_adopted_as_a_fresh_target(self):
        log = self.log / "ch05-01-demo.log"
        log.write_bytes(b"old build was interrupted before receipt append\n")
        result = self.refused()
        self.assertIn("unbound pre-existing page log", result.stdout)
        self.assertEqual(self.executions(), [])
        self.assertEqual(log.read_bytes(), b"old build was interrupted before receipt append\n")

    def test_ledger_or_state_corruption_refuses(self):
        self.successful()
        for name in ("receipts.jsonl", "driver.state"):
            with self.subTest(name=name):
                path = self.log / name
                original = path.read_bytes()
                path.write_bytes(original[:-1])
                self.refused()
                path.write_bytes(original)
        self.assertEqual(self.executions(), ["ran"])

    def test_failed_page_is_receipted_but_never_automatically_retried(self):
        self.page("01-demo.sh", 'printf "ran\\n" >> "$LFS/sources/ran"\nexit 23\n')
        self.refused()
        self.assertEqual(self.receipt_rows()[-1]["exit"], 23)
        self.assertEqual((self.log / "driver.state").read_bytes(), b"")
        self.refused()
        self.assertEqual(self.executions(), ["ran"])

    def test_pipeline_failure_is_not_banked(self):
        self.page("01-demo.sh", 'printf "ran\\n" >> "$LFS/sources/ran"\nfalse | cat\n')
        self.refused()
        self.assertNotEqual(self.receipt_rows()[-1]["exit"], 0)
        self.assertEqual((self.log / "driver.state").read_bytes(), b"")

    def test_receipt_schema_preserves_old_fields_and_adds_input_identity(self):
        self.page("01-demo.sh", 'tup_receipt_skip_tests "$TUP_PAGE_ID"\n')
        self.successful()
        rows = self.receipt_rows()
        self.assertTrue(rows[0]["tests_skipped"])
        row = rows[-1]
        self.assertTrue({"ts", "page", "package", "seconds", "exit", "log_sha256",
                         "override", "script_sha256", "tarball_sha256"} <= row.keys())
        self.assertEqual(row["exit"], 0)
        self.assertRegex(row["input_sha256"], "^[0-9a-f]{64}$")
        self.assertEqual(row["script_sha256"], hashlib.sha256((self.chapter / "01-demo.sh").read_bytes()).hexdigest())

    def test_concurrent_invocation_cannot_execute_same_page(self):
        self.page("01-demo.sh", 'printf "ran\\n" >> "$LFS/sources/ran"\nwhile [ ! -f "$LFS/sources/release" ]; do sleep 0.05; done\n')
        with subprocess.Popen(self.command(), env=self.env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as first:
            try:
                limit = time.monotonic() + 20
                while not self.executions() and time.monotonic() < limit:
                    if first.poll() is not None:
                        self.fail(first.communicate()[0])
                    time.sleep(0.05)
                self.assertEqual(self.executions(), ["ran"])
                self.refused()
            finally:
                (self.sources / "release").touch()
            output, _ = first.communicate(timeout=20)
            self.assertEqual(first.returncode, 0, output)
        self.assertEqual(self.executions(), ["ran"])

    def real_command(self, name: str) -> str:
        result = subprocess.run([BASH, "-c", 'command -v "$1"', "fixture", name],
                                text=True, capture_output=True, check=True)
        return shlex.quote(result.stdout.strip())

    def sync_fallback(self):
        return "exit 0\n" if os.name == "nt" else 'exec ' + self.real_command("sync") + ' "$@"\n'

    def committed(self):
        store = self.log / "driver.v2"
        return store / (store / "current").read_text().strip()

    def assert_blocked_after_attempt(self):
        self.assertTrue((self.log / "driver.v2" / "pending").is_dir())
        self.refused()
        self.assertEqual(self.executions(), ["ran"])

    def test_partial_snapshot_write_enospc_does_not_commit_or_replay(self):
        real = self.real_command("cp")
        self.shim("cp", 'if [ -f "$LFS/sources/ran" ]; then\n'
                  '  case "${@: -1}" in */.next.*/)\n'
                  f'    {real} "$@" || exit $?\n'
                  '    printf partial > "${@: -1}/receipts.jsonl"\n'
                  '    echo "fixture: No space left on device after partial write" >&2\n'
                  '    exit 28;; esac\nfi\n'
                  f'exec {real} "$@"\n')
        result = self.refused()
        self.assertIn("No space left", result.stdout)
        self.assertEqual((self.committed() / "driver.state").read_bytes(), b"")
        self.assertEqual((self.committed() / "receipts.jsonl").read_bytes(), b"")
        self.assert_blocked_after_attempt()

    def test_commit_pointer_rename_failure_keeps_previous_snapshot(self):
        real = self.real_command("mv")
        self.shim("mv", 'if [ -f "$LFS/sources/ran" ]; then\n'
                  '  case "${@: -1}" in */driver.v2/current) exit 28;; esac\n'
                  f'fi\nexec {real} "$@"\n')
        result = self.refused()
        self.assertIn("cannot commit snapshot", result.stdout)
        self.assertEqual((self.committed() / "driver.state").read_bytes(), b"")
        self.assert_blocked_after_attempt()

    def test_both_projection_rename_failures_preserve_canonical_result_and_intent(self):
        # Use separate fixture instances because an uncertain attempt must not
        # be reset in place just to exercise another failure branch.
        real = self.real_command("mv")
        for name in ("receipts.jsonl", "driver.state"):
            with self.subTest(name=name):
                fixture = DriverStateTests()
                fixture.setUp()
                try:
                    fixture.shim("mv", 'if [ -f "$LFS/sources/ran" ]; then\n'
                                 f'  case "${{@: -1}}" in */log/{name}) exit 28;; esac\n'
                                 f'fi\nexec {real} "$@"\n')
                    result = fixture.refused()
                    self.assertIn("cannot publish " + name, result.stdout)
                    committed = fixture.committed()
                    self.assertEqual((committed / "driver.state").read_text(), "ch05/01-demo.sh\n")
                    rows = [json.loads(row) for row in (committed / "receipts.jsonl").read_text().splitlines()]
                    self.assertEqual(rows[-1]["exit"], 0)
                    fixture.assert_blocked_after_attempt()
                finally:
                    fixture.doCleanups()

    def test_intent_flush_failure_prevents_execution(self):
        self.shim("sync", 'for arg in "$@"; do\n'
                  '  case "$arg" in */pending/intent) exit 28;; esac\n'
                  'done\n' + self.sync_fallback())
        self.refused()
        self.assertTrue((self.log / "driver.v2" / "pending").is_dir())
        self.assertEqual(self.executions(), [])
        self.refused()
        self.assertEqual(self.executions(), [])

    def test_target_flush_failure_cannot_bank_success(self):
        self.shim("sync", 'if [ "${1:-}" = -f ] && [ -f "$LFS/sources/ran" ]; then exit 28; fi\n' + self.sync_fallback())
        result = self.refused()
        self.assertIn("target filesystem flush failed", result.stdout)
        self.assertEqual((self.committed() / "driver.state").read_bytes(), b"")
        self.assert_blocked_after_attempt()

    def test_post_commit_flush_failure_is_not_a_success_or_replay(self):
        self.shim("sync", 'store="$LFS/sources/log/driver.v2"\n'
                  'if [ -f "$LFS/sources/ran" ] && [ -f "$store/current" ]; then\n'
                  '  current=$(cat "$store/current")\n'
                  '  if [ -s "$store/$current/driver.state" ]; then exit 28; fi\n'
                  'fi\n' + self.sync_fallback())
        self.refused()
        self.assertEqual((self.committed() / "driver.state").read_text(), "ch05/01-demo.sh\n")
        self.assert_blocked_after_attempt()

    def test_event_receipt_write_failure_propagates(self):
        self.page("01-demo.sh", 'printf "ran\\n" >> "$LFS/sources/ran"\n'
                  'rm -- "$RECEIPTS"\nmkdir -- "$RECEIPTS"\n'
                  'tup_receipt_skip_tests "$TUP_PAGE_ID"\n'
                  'printf "masked\\n" >> "$LFS/sources/ran"\n')
        self.refused()
        self.assertEqual((self.committed() / "driver.state").read_bytes(), b"")
        self.assert_blocked_after_attempt()

    def test_intent_retirement_failure_requires_recovery(self):
        real = self.real_command("rm")
        self.shim("rm", 'for arg in "$@"; do\n'
                  '  case "$arg" in */pending/intent) exit 28;; esac\ndone\n'
                  f'exec {real} "$@"\n')
        self.refused()
        self.assertEqual((self.committed() / "driver.state").read_text(), "ch05/01-demo.sh\n")
        self.assert_blocked_after_attempt()

    def test_abrupt_parent_death_is_never_replayed(self):
        self.page("01-demo.sh", 'printf "ran\\n" >> "$LFS/sources/ran"\n'
                  'kill -KILL "$PPID"\nexit 0\n')
        self.refused()
        self.assert_blocked_after_attempt()

    def test_inputs_modified_during_page_are_receipted_as_failure(self):
        page = self.page("01-demo.sh", 'printf "ran\\n" >> "$LFS/sources/ran"\n'
                         'printf "# modified\\n" >> "$TUP_PAGE"\n')
        before = hashlib.sha256(page.read_bytes()).hexdigest()
        self.refused()
        row = self.receipt_rows()[-1]
        self.assertEqual(row["page_exit"], 0)
        self.assertEqual(row["exit"], 125)
        self.assertEqual(row["script_sha256"], before)
        self.assert_blocked_after_attempt()

    def test_canonical_snapshot_corruption_refuses(self):
        self.successful()
        ledger = self.committed() / "receipts.jsonl"
        ledger.write_bytes(ledger.read_bytes()[:-1])
        result = self.refused()
        self.assertIn("committed ledger is corrupt", result.stdout)
        self.assertEqual(self.executions(), ["ran"])

    def test_completed_log_corruption_refuses(self):
        self.successful()
        (self.log / "ch05-01-demo.log").write_bytes(b"tampered")
        result = self.refused()
        self.assertIn("completed page log changed", result.stdout)
        self.assertEqual(self.executions(), ["ran"])

    def test_corrupt_commit_pointer_refuses(self):
        self.successful()
        pointer = self.log / "driver.v2" / "current"
        pointer.write_bytes(pointer.read_bytes() + b"\n")
        self.refused()
        self.assertEqual(self.executions(), ["ran"])

    def test_validate_only_never_executes_or_creates_a_snapshot(self):
        self.env["TUP_VALIDATE_ONLY"] = "1"
        self.refused()
        self.assertEqual(self.executions(), [])
        self.assertFalse((self.log / "driver.v2").exists())
        self.env.pop("TUP_VALIDATE_ONLY")
        self.successful()
        before = {str(p.relative_to(self.log)): p.read_bytes()
                  for p in self.log.rglob("*") if p.is_file()}
        self.env["TUP_VALIDATE_ONLY"] = "1"
        self.successful()
        after = {str(p.relative_to(self.log)): p.read_bytes()
                 for p in self.log.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(self.executions(), ["ran"])

    def test_validate_earlier_chapter_after_later_commit(self):
        self.successful()
        earlier = self.chapter
        self.chapter = self.root / "book" / "ch06"
        self.chapter.mkdir()
        self.page("01-next.sh", 'printf "next\\n" >> "$LFS/sources/ran"\n')
        result = self.run_driver()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.chapter = earlier
        self.env["TUP_VALIDATE_ONLY"] = "1"
        self.successful()
        self.assertEqual(self.executions(), ["ran", "next"])

    def test_colliding_page_log_names_refuse_instead_of_overwriting_evidence(self):
        self.page("part-01-demo.sh", 'printf "ran\\n" >> "$LFS/sources/ran"\n')
        self.successful()
        log = self.log / "ch05-part-01-demo.log"
        original = log.read_bytes()
        self.chapter = self.root / "book" / "ch05-part"
        self.chapter.mkdir()
        self.page("01-demo.sh", 'printf "collision\\n" >> "$LFS/sources/ran"\n')
        result = self.refused()
        self.assertIn("page log name collides", result.stdout)
        self.assertEqual(log.read_bytes(), original)
        self.assertEqual(self.executions(), ["ran"])

    def test_default_test_policy_reaches_child_page(self):
        self.env.pop("TUP_TESTS")
        self.page("01-demo.sh", 'tup_tests_enabled glibc\n')
        self.successful()

    def test_no_implicit_retry_after_corrupt_archive(self):
        self.page("01-demo.sh", '# TUP_TARBALL=demo.tar\nprintf "ran\\n" >> "$LFS/sources/ran"\n')
        (self.sources / "demo.tar").write_bytes(b"not a tarball")
        self.refused()
        self.assertEqual(self.executions(), [])
        self.assertTrue((self.log / "driver.v2" / "pending").exists())
        self.archive(b"now valid")
        self.refused()
        self.assertEqual(self.executions(), [])

    def test_existing_uncommitted_log_in_later_chapter_is_preserved(self):
        self.successful()
        self.chapter = self.root / "book" / "ch06"
        self.chapter.mkdir()
        self.page("01-next.sh", 'printf "next\\n" >> "$LFS/sources/ran"\n')
        old_log = self.log / "ch06-01-next.log"
        old_log.write_bytes(b"unbound attempt\n")
        result = self.refused()
        self.assertIn("unbound page log already exists", result.stdout)
        self.assertEqual(old_log.read_bytes(), b"unbound attempt\n")
        self.assertEqual(self.executions(), ["ran"])

    def test_unsupported_target_flush_fails_before_execution(self):
        self.shim("sync", 'if [ "${1:-}" = -f ]; then exit 1; fi\n' + self.sync_fallback())
        result = self.refused()
        self.assertIn("target filesystem flush is unavailable", result.stdout)
        self.assertEqual(self.executions(), [])

    def test_hash_error_or_invalid_digest_never_creates_state(self):
        for body in ('printf "%064d  -\\n" 0\nexit 23\n', 'exit 0\n', 'printf bad\\n\n'):
            with self.subTest(body=body):
                self.shim("sha256sum", body)
                self.refused()
                self.assertEqual(self.executions(), [])
                self.assertFalse((self.log / "driver.v2").exists())
    def test_invalid_order_is_rejected_before_mutation(self):
        for order in ("", "01-demo.sh\n01-demo.sh\n", "../escape.sh\n", "01-demo.sh\r\n"):
            with self.subTest(order=order):
                (self.chapter / "ORDER").write_bytes(order.encode())
                self.refused()
                self.assertEqual(self.executions(), [])
                self.assertFalse((self.log / "driver.v2").exists())

    @unittest.skipIf(os.name == "nt", "real Linux fsync/syncfs; Windows uses protocol shim")
    def test_real_linux_fsync_commits_and_validates(self):
        self.assertFalse((self.bin / "sync").exists())
        self.successful()
        self.env["TUP_VALIDATE_ONLY"] = "1"
        self.successful()


if __name__ == "__main__":
    unittest.main()
