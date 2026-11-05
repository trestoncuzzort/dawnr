"""Audited-block and source-export fixtures; no package or OS operations."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "native/build.py"
SPEC = importlib.util.spec_from_file_location("native_profile_build", MODULE)
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)
BASH = os.environ.get("TUP_TEST_BASH") or shutil.which("bash")


def shell_path(path):
    text = path.resolve().as_posix()
    return "/" + text[0].lower() + text[2:] if os.name == "nt" else text


class NativeProfileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tup-native-profile-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.page = self.directory / "page.sh"
        self.script = self.directory / "override.sh"
        self.events = self.directory / "events.jsonl"
        self.marker = self.directory / "executed"

    def page_plan(self, command, action="run-suite", classification="test", replacement=None):
        body = command.rstrip("\n").encode()
        self.page.write_bytes(b"# TUP_REQUIRES_OVERRIDE=fixture\nexit 97\n"
                              b"# TUP_BOOK_COMMANDS_BEGIN\n# TUP_BLOCK_BEGIN=000\n" + body + b"\n" +
                              b"# TUP_BLOCK_END=000\n")
        item = {"id": "000", "sha256": hashlib.sha256(body).hexdigest(),
                "action": action, "classification": classification, "reason": "fixture policy"}
        if replacement is not None:
            item["replacement"] = replacement
        return {"page_sha256": build.digest(self.page), "archive": None, "blocks": [item]}

    def run_recipe(self, plan, cwd=None, **extra_env):
        if not BASH:
            self.skipTest("Bash is required for isolated recipe fixtures")
        self.script.write_bytes(build.render_native_page("ch05/01-fixture.sh", self.page.read_bytes(), plan))
        environment = dict(os.environ, TUP_PAGE=shell_path(self.page), TUP_PAGE_ID="ch05/01-fixture",
                           TUP_PROFILE="native-x86_64-lfs-13.1-systemd-core", TUP_JOBS="4",
                           TUP_NATIVE_CHROOT="0", LFS=shell_path(self.directory),
                           CONFIG_SITE=shell_path(self.directory) + "/usr/share/config.site",
                           RECEIPTS=shell_path(self.events), NATIVE_MARKER=shell_path(self.marker))
        environment.update(extra_env)
        launcher = '''
tup_json_str() { printf '"%s"' "$1"; }
tup_receipt_skip_tests() { printf '{"tests_skipped":true}\\n' >> "$RECEIPTS"; }
ninja() { printf 'ninja ran\\n' >> "$NATIVE_MARKER"; return "${NATIVE_NINJA_RC:-0}"; }
passwd() { printf '%s\\n' "$*" > "$NATIVE_MARKER"; }
export -f tup_json_str tup_receipt_skip_tests ninja passwd
exec bash "$1"
'''
        return subprocess.run([BASH, "-c", launcher, "native-fixture", shell_path(self.script)],
                              env=environment, capture_output=True, text=True, timeout=30, cwd=cwd)

    def test_raw_block_selection_never_executes_extractor_guard(self):
        plan = self.page_plan("ninja test\n")
        result = self.run_recipe(plan)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.marker.read_text(), "ninja ran\n")
        rows = [json.loads(line) for line in self.events.read_text().splitlines()]
        self.assertEqual([row["native_status"] for row in rows], ["suite-started", "suite-passed"])

    def test_ninja_suite_skip_is_explicit_and_does_not_execute(self):
        result = self.run_recipe(self.page_plan("ninja test\n", action="skip-suite"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.marker.exists())
        rows = [json.loads(line) for line in self.events.read_text().splitlines()]
        self.assertEqual(rows[0]["native_status"], "suite-skipped")
        self.assertTrue(rows[1]["tests_skipped"])

    def test_failed_ninja_suite_retains_failure_and_never_emits_pass(self):
        result = self.run_recipe(self.page_plan("ninja test\n"), NATIVE_NINJA_RC="41")
        self.assertEqual(result.returncode, 41, result.stderr)
        statuses = [json.loads(line)["native_status"] for line in self.events.read_text().splitlines()]
        self.assertEqual(statuses, ["suite-started", "suite-failed"])

    def test_combined_build_and_test_cannot_be_skipped(self):
        plan = self.page_plan("ninja\n", action="skip-suite", classification="build-test")
        with self.assertRaisesRegex(build.Refusal, "combined build/test cannot be skipped"):
            build.render_native_page("ch05/01-fixture.sh", self.page.read_bytes(), plan)

    def test_test_block_cannot_be_reclassified_as_ordinary_execution(self):
        plan = self.page_plan("ninja test\n", action="run")
        with self.assertRaisesRegex(build.Refusal, "no explicit suite disposition"):
            build.render_native_page("ch05/01-fixture.sh", self.page.read_bytes(), plan)

    def test_explicit_root_lock_replacement_uses_no_password_prompt(self):
        plan = self.page_plan("passwd root\n", action="replace", classification="interactive",
                              replacement="passwd -l root\n")
        result = self.run_recipe(plan)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.marker.read_text(), "-l root\n")

    def test_audited_glibc_timeout_diagnostic_survives_the_err_trap_when_nothing_timed_out(self):
        # The rendered prologue traps ERR, and "set +e" does not disable that trap:
        # the earlier spelling of this diagnostic exited 1 exactly when the suite
        # was clean (no "Timed out" line), before the package could be installed.
        audit = json.loads((MODULE.parent / "profiles/lfs-13.1-systemd/AUDIT.json").read_bytes())
        block = next(item for item in audit["pages"]["ch08/05-glibc.sh"]["blocks"] if item["id"] == "007")
        self.assertEqual((block["action"], block["classification"]), ("replace", "diagnostic"))
        tree = self.directory / "build"
        (tree / "posix").mkdir(parents=True)
        (tree / "posix/tst-fixture.out").write_text("completed normally\n", encoding="utf-8")
        plan = self.page_plan("grep fixture\n", action="replace", classification="diagnostic",
                              replacement=block["replacement"] + 'printf reached > "$NATIVE_MARKER"\n')
        result = self.run_recipe(plan, cwd=tree)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.marker.read_text(), "reached")
        self.marker.unlink()
        (tree / "posix/tst-slow.out").write_text("Timed out: killed the child process\n", encoding="utf-8")
        result = self.run_recipe(plan, cwd=tree)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("tst-slow.out:Timed out", result.stdout)
        self.assertEqual(self.marker.read_text(), "reached")

    def test_no_audited_replacement_relies_on_disabling_errexit(self):
        audit = json.loads((MODULE.parent / "profiles/lfs-13.1-systemd/AUDIT.json").read_bytes())
        for key, plan in audit["pages"].items():
            for item in plan["blocks"]:
                with self.subTest(page=key, block=item["id"]):
                    self.assertNotRegex(item.get("replacement", ""), r"(?m)^\s*set \+[a-zA-Z]*e")

    def test_wrong_build_context_refuses_before_command_execution(self):
        plan = self.page_plan("ninja test\n")
        for change in ({"TUP_NATIVE_CHROOT": "1"}, {"CONFIG_SITE": "/wrong/site"},
                       {"TUP_PROFILE": "legacy"}, {"TUP_JOBS": "0"}):
            with self.subTest(change=change):
                result = self.run_recipe(plan, **change)
                self.assertEqual(result.returncode, 96, result.stderr)
                self.assertFalse(self.marker.exists())

    def test_changed_or_missing_block_refuses_before_recipe_creation(self):
        plan = self.page_plan("ninja test\n")
        original = self.page.read_bytes()
        with self.assertRaisesRegex(build.Refusal, "page changed"):
            build.render_native_page("ch05/01-fixture.sh", original + b"# changed\n", plan)
        plan["blocks"] = []
        with self.assertRaisesRegex(build.Refusal, "cover each block"):
            build.render_native_page("ch05/01-fixture.sh", original, plan)

    def test_nested_and_unclosed_delimiters_refuse(self):
        for data in (b"# TUP_BLOCK_BEGIN=000\n# TUP_BLOCK_BEGIN=001\n",
                     b"# TUP_BLOCK_BEGIN=000\ntrue\n",
                     b"# TUP_BLOCK_BEGIN=000\ntrue\n# TUP_BLOCK_END=001\n"):
            with self.subTest(data=data):
                with self.assertRaises(build.Refusal):
                    build.raw_blocks(data)

    def test_block_hash_removes_only_one_formatter_newline(self):
        command = b"printf 'x'  \n"
        page = b"# TUP_BLOCK_BEGIN=001\n" + command + b"\n# TUP_BLOCK_END=001\n"
        self.assertEqual(build.raw_blocks(page)["001"], command)

    def test_python_archive_selection_matches_driver_precedence_and_refusals(self):
        self.assertEqual(build.archive_metadata(b"# TUP_TARBALL=generic.tar\n"
                                               b"# TUP_TARBALL_x86_64=native.tar\n"), "native.tar")
        self.assertEqual(build.archive_metadata(b"# TUP_TARBALL_arm64=arm.tar\n"), "")
        for data in (b"# TUP_TARBALL=one.tar\n# TUP_TARBALL=two.tar\n",
                     b"# TUP_TARBALL=../bad.tar\n", b"# TUP_TARBALL=\n"):
            with self.subTest(data=data), self.assertRaises(build.Refusal):
                build.archive_metadata(data)

    def test_native13_requires_exported_source_and_advisory_evidence(self):
        book = self.directory / "book"
        book.mkdir()
        for chapter in ("ch05", "ch06", "ch07", "ch08"):
            (book / chapter).mkdir()
        (book / "BOOK-SOURCE").write_bytes(
            b"arch=x86_64\nversion=13.1\ninit=systemd\nprofile=lfs-13.1-systemd\n"
            b"base=https://www.linuxfromscratch.org/lfs/view/13.1-systemd/\n"
            b"snapshot_sha256=" + b"1" * 64 + b"\naudit_profile_sha256=" + b"2" * 64 + b"\n")
        (book / "ch05/01-demo.sh").write_bytes(b"# TUP_TARBALL=original.tar\n")
        lock = {"schema": "tup-source-lock-v1", "architecture": "x86_64",
                "lock_purpose": "production", "release_eligible": True, "release_gates": [],
                "book_source_sha256": build.digest(book / "BOOK-SOURCE"), "provenance": "fixture evidence",
                "sources": [{"name": "updated.tar", "url": "https://example.invalid/updated.tar", "sha256": "3" * 64,
                             "authentication": {"status": "verified", "trust_class": "https-published-sha256",
                                                "evidence_sha256": "4" * 64}}],
                "source_verification": {"schema": "tup-source-verification-v1", "status": "complete",
                                        "source_count": 1, "report_sha256": "5" * 64},
                "advisory_review": {"status": "reviewed", "material_sha256": "6" * 64,
                                    "dispositions": [{"id": "fixture", "disposition": "fixed-by-selection"}]}}
        path = self.directory / "source-lock.json"
        effective = {"overrides/x86_64/ch05/01-demo.sh": b"# TUP_TARBALL=updated.tar\n",
                     "native/profiles/lfs-13.1-systemd/AUDIT.json": build.encoded({"source_names": ["updated.tar"]})}
        backport_fields = {}
        for field, name in (("native_patch", "python-3.14.10-security-backports.patch"),
                            ("native_review", "PYTHON-BACKPORT-REVIEW.json")):
            key = "native/profiles/lfs-13.1-systemd/" + name
            effective[key] = build.TUP / key
            backport_fields[field] = {"path": "tup/" + key, "sha256": build.digest(effective[key])}
        for advisory in ("sa-13.1-088", "sa-13.1-089"):
            lock["advisory_review"]["dispositions"].append({"id": advisory, "package": "python",
                "disposition": "fixed-by-native-patch", "selected_sources": ["Python-3.14.10.tar.xz"], **backport_fields})

        def load():
            path.write_bytes(build.encoded(lock))
            return build.load_lock(path, build.digest(path), book, profile="lfs-13.1-systemd", effective_inputs=effective)

        self.assertEqual(load()["sources"][0]["name"], "updated.tar")
        lock["source_verification"]["status"] = "candidate"
        with self.assertRaisesRegex(build.Refusal, "complete exported"):
            load()
        lock["source_verification"]["status"] = "complete"
        lock["advisory_review"]["dispositions"][0]["disposition"] = "unresolved"
        with self.assertRaisesRegex(build.Refusal, "reviewed advisory"):
            load()


if __name__ == "__main__":
    unittest.main()
