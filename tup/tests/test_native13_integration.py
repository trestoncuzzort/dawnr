"""Native13 policy integration with harmless files/commands only; no LFS build."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tarfile
import unittest
from unittest.mock import patch


TUP = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native13_integration", TUP / "native/build.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)
BOOK = TUP / "book-x86_64-13.1-systemd"
AUDIT = TUP / "native/profiles/lfs-13.1-systemd/AUDIT.json"
BASH = os.environ.get("TUP_TEST_BASH") or shutil.which("bash")


def shell_path(path):
    text = path.resolve().as_posix()
    return "/" + text[0].lower() + text[2:] if os.name == "nt" else text


class Native13IntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tup-native13-fixture-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def test_audited_pages_compile_and_select_advisory_archives_without_legacy_overrides(self):
        files = build.input_map(TUP, BOOK, profile="lfs-13.1-systemd")
        # This previously leaked shared historical recipes into the new book.
        overrides = {name: body for name, body in files.items() if name.startswith("overrides/")}
        self.assertEqual(len(overrides), 124)
        self.assertTrue(all(name.startswith("overrides/x86_64/ch") for name in overrides))
        self.assertEqual(build.archive_metadata(overrides["overrides/x86_64/ch05/04-linux-headers.sh"]), "linux-6.18.60.tar.xz")
        self.assertEqual(build.archive_metadata(overrides["overrides/x86_64/ch08/54-Python.sh"]), "Python-3.14.10.tar.xz")
        self.assertIn(b"passwd -l root", overrides["overrides/x86_64/ch08/30-shadow.sh"])
        self.assertNotIn(b"passwd root", overrides["overrides/x86_64/ch08/30-shadow.sh"])
        self.assertIn(b"glibc-2.44-upstream_fixes-3.patch", overrides["overrides/x86_64/ch08/05-glibc.sh"])
        self.assertEqual(files["book/ch07-inner/ORDER"].splitlines()[-1], b"15-cleanup.sh")
        self.assertNotIn(b"--target=i386", overrides["overrides/x86_64/ch08/65-grub.sh"])
        self.assertIn(b"--target=x86_64", overrides["overrides/x86_64/ch08/65-grub.sh"])
        self.assertNotIn(b"spawn make tests", overrides["overrides/x86_64/ch08/39-bash.sh"])
        self.assertNotIn(b"bash tests/run.sh", overrides["overrides/x86_64/ch08/81-util-linux.sh"])
        self.assertIn(b"NINJAJOBS", overrides["overrides/x86_64/ch08/20-ninja.sh"])
        if not BASH:
            self.skipTest("Bash is required for syntax checks")
        for key, data in overrides.items():
            target = self.directory / "override.sh"
            target.write_bytes(data)
            result = subprocess.run([BASH, "-n", shell_path(target)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, f"{key}: {result.stderr}")

    def test_changed_order_or_uncovered_block_is_refused(self):
        audit = json.loads(AUDIT.read_bytes())
        audit["orders"]["ch07"][9], audit["orders"]["ch07"][10] = audit["orders"]["ch07"][10], audit["orders"]["ch07"][9]
        with patch.object(build, "read_json", return_value=audit), self.assertRaisesRegex(build.Refusal, "chapter order"):
            build.native13_overrides(TUP, BOOK)
        audit = json.loads(AUDIT.read_bytes())
        audit["pages"]["ch08/77-systemd.sh"]["blocks"].pop()
        with patch.object(build, "read_json", return_value=audit), self.assertRaisesRegex(build.Refusal, "cover each block"):
            build.native13_overrides(TUP, BOOK)

    def test_critical_suite_cannot_be_replaced_with_record_only_success(self):
        audit = json.loads(AUDIT.read_bytes())
        item = audit["pages"]["ch08/32-gcc.sh"]["blocks"][5]
        item["replacement"] = "make -k check || true\n"
        with patch.object(build, "read_json", return_value=audit), self.assertRaisesRegex(build.Refusal, "required suite omitted"):
            build.native13_overrides(TUP, BOOK)

    def test_unpackaged_python_uses_cpython_runshared_instead_of_bare_interpreter(self):
        # Core run 001: a bare ./python exited 127 before installation because
        # the loader could not find the build tree's libpython. After the
        # temporary Python is installed, the same spelling would silently load
        # that older library while judging the final interpreter.
        files = build.input_map(TUP, BOOK, profile="lfs-13.1-systemd")
        helper_name = "native/profiles/lfs-13.1-systemd/python-built.mk"
        self.assertIn(helper_name, files)
        helper = (TUP / helper_name).read_bytes()
        self.assertNotIn(b"\r", helper)
        for target in (b"tup-backport-regressions", b"tup-suite-results"):
            self.assertRegex(helper, rb"(?m)^" + target + rb": tup-built-library\n\t\$\(RUNSHARED\) \$\(PYTHON_FOR_BUILD\) \$\(TUP_NATIVE13\)/")
        select = b"-f Makefile -f /tup-build/" + helper_name.encode() + b" "
        temporary, final = files["overrides/x86_64/ch07/12-Python.sh"], files["overrides/x86_64/ch08/54-Python.sh"]
        for page in (temporary, final):
            self.assertNotRegex(page, rb"(?m)(^|[\s;&|'\"(])\./python(\s|$)")
            self.assertIn(select + b"tup-backport-regressions", page)
        self.assertIn(select + b"tup-suite-results", final)
        self.assertNotIn(b"tup-suite-results", temporary)

    def test_built_python_helper_applies_generated_variables_and_refuses_empty_library_path(self):
        make = shutil.which("make")
        if os.name == "nt" or not make:
            self.skipTest("GNU make on a POSIX host is required for the recipe fixture")
        helper = TUP / "native/profiles/lfs-13.1-systemd/python-built.mk"
        (self.directory / "Makefile").write_text(
            "RUNSHARED=       TUP_FIXTURE_LIBRARY=build-tree\nPYTHON_FOR_BUILD=" + shutil.which("python3") + " -E\n", encoding="utf-8")
        script = "import os, sys\nopen(sys.argv[-1], 'x').write(os.environ.get('TUP_FIXTURE_LIBRARY', 'missing'))\n"
        (self.directory / "python-backport-tests.py").write_text(script, encoding="utf-8")
        (self.directory / "python-suite-results.py").write_text(script, encoding="utf-8")
        command = [make, "-f", "Makefile", "-f", str(helper), f"TUP_NATIVE13={self.directory}"]
        for target, output in (("tup-backport-regressions", "native-python-backports.trs"),
                               ("tup-suite-results", "native-python-full.trs")):
            subprocess.run([*command, target], cwd=self.directory, check=True, capture_output=True, timeout=30)
            self.assertEqual((self.directory / output).read_text(encoding="utf-8"), "build-tree")
            (self.directory / output).unlink()
            refused = subprocess.run([*command, "RUNSHARED=", target], cwd=self.directory, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("RUNSHARED is empty", refused.stderr)
            self.assertFalse((self.directory / output).exists())

    def judge(self, package, summaries, console="", exceptions=None):
        if not BASH:
            self.skipTest("Bash is required for result-gate fixtures")
        results = self.directory / "results"
        results.mkdir(exist_ok=True)
        for child in results.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
        for stale in self.directory.glob("nonpass.*"):
            stale.unlink()
        for name, value in summaries.items():
            (results / name).parent.mkdir(parents=True, exist_ok=True)
            (results / name).write_text(value, encoding="utf-8")
        (self.directory / "command.console").write_text(console, encoding="utf-8")
        helper = TUP / "native/profiles/lfs-13.1-systemd/required-suite.sh"
        if exceptions is not None:
            # The helper finds reviewed lists beside itself; give a fixture copy its own.
            profile = self.directory / "profile"
            shutil.rmtree(profile, ignore_errors=True)
            (profile / "suite-exceptions").mkdir(parents=True)
            shutil.copyfile(helper, profile / "required-suite.sh")
            helper = profile / "required-suite.sh"
            for name, value in exceptions.items():
                (profile / "suite-exceptions" / name).write_text(value, encoding="utf-8", newline="\n")
        return subprocess.run([BASH, "-c", 'set -euo pipefail; source "$1"; native_judge_suite "$2" "$3"',
                               "suite-fixture", shell_path(helper), package, shell_path(self.directory)],
                              text=True, capture_output=True, timeout=30)

    def test_required_suite_result_gate_rejects_missing_and_zero_pass_evidence(self):
        self.assertNotEqual(self.judge("glibc", {}).returncode, 0)
        self.assertNotEqual(self.judge("glibc", {"tests.sum": "UNSUPPORTED: only-test\n"}).returncode, 0)
        self.assertEqual(self.judge("glibc", {"tests.sum": "PASS: real-test\nUNSUPPORTED: optional-test\n"}).returncode, 0)

    def test_required_suite_result_gate_rejects_failure_even_after_zero_exit(self):
        for verdict in ("FAIL", "XPASS", "UNRESOLVED", "ERROR"):
            with self.subTest(verdict=verdict):
                result = self.judge("glibc", {"tests.sum": f"PASS: one\n{verdict}: broken\n"})
                self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(self.judge("gmp", {"one.trs": ":test-result: PASS\n", "two.trs": ":test-result: FAIL\n"}).returncode, 0)

    def test_compiler_result_gate_requires_each_component_and_ignores_compile_error_text(self):
        results = {name: "# of expected passes\t12\n" for name in ("gcc.sum", "g++.sum", "libstdc++.sum")}
        results["config.log"] = "ERROR: intentionally unsupported configure probe\n"
        self.assertEqual(self.judge("gcc", results).returncode, 0)
        del results["libstdc++.sum"]
        self.assertNotEqual(self.judge("gcc", results).returncode, 0)

    def test_reviewed_exception_accepts_only_the_exact_named_result(self):
        allow = {"glibc.allow": "# reviewed fixture\n@min-pass 2\nFAIL: io/tst-lchmod\n"}
        passing = "PASS: one\nPASS: two\nFAIL: io/tst-lchmod\nXFAIL: expected\nUNSUPPORTED: optional\n"
        self.assertEqual(self.judge("glibc", {"tests.sum": passing}, exceptions=allow).returncode, 0)
        self.assertEqual((self.directory / "nonpass.observed").read_text(), "FAIL: io/tst-lchmod\n")
        self.assertEqual((self.directory / "nonpass.unexplained").read_text(), "")
        expected = hashlib.sha256(allow["glibc.allow"].encode()).hexdigest()
        # GNU sha256sum separates digest and name with two spaces, or " *" in binary mode.
        self.assertEqual((self.directory / "nonpass.exceptions.sha256").read_text().split(" ", 1)[0], expected)
        for extra in ("FAIL: io/tst-lchmod2\n", "FAIL: io/tst-lchmo\n", "XPASS: io/tst-lchmod\n",
                      "FAIL: io/tst-lchmod \n", "ERROR: io/tst-other\n", "UNRESOLVED: io/tst-other\n"):
            with self.subTest(extra=extra):
                self.assertNotEqual(self.judge("glibc", {"tests.sum": passing + extra}, exceptions=allow).returncode, 0)
                self.assertEqual((self.directory / "nonpass.unexplained").read_text(), extra)
        # The same summary without a reviewed list, or with one for another package, still refuses.
        self.assertNotEqual(self.judge("glibc", {"tests.sum": passing}).returncode, 0)
        self.assertNotEqual(self.judge("glibc", {"tests.sum": passing}, exceptions={"gcc.allow": allow["glibc.allow"]}).returncode, 0)

    def test_reviewed_exception_requires_positive_coverage_and_a_single_floor(self):
        summary = "PASS: one\nPASS: two\nFAIL: io/tst-lchmod\n"
        for text in ("@min-pass 3\nFAIL: io/tst-lchmod\n", "FAIL: io/tst-lchmod\n", "@min-pass 0\nFAIL: io/tst-lchmod\n",
                     "@min-pass 1\n@min-pass 2\nFAIL: io/tst-lchmod\n", "@min-pass two\nFAIL: io/tst-lchmod\n"):
            with self.subTest(text=text):
                self.assertNotEqual(self.judge("glibc", {"tests.sum": summary}, exceptions={"glibc.allow": text}).returncode, 0)
        # glibc lists each result in tests.sum and again in a per-directory summary:
        # a repeated line is one result, for the exception count and for the floor.
        repeated = {"tests.sum": summary, "io/subdir-tests.sum": summary}
        self.assertEqual(self.judge("glibc", repeated, exceptions={"glibc.allow": "@min-pass 2\nFAIL: io/tst-lchmod\n"}).returncode, 0)
        self.assertEqual((self.directory / "nonpass.observed").read_text(), "FAIL: io/tst-lchmod\n")
        self.assertNotEqual(self.judge("glibc", repeated, exceptions={"glibc.allow": "@min-pass 3\nFAIL: io/tst-lchmod\n"}).returncode, 0)
        # Automake .trs verdicts carry no test name, so those suites cannot use a reviewed list.
        self.assertNotEqual(self.judge("gmp", {"one.trs": ":test-result: PASS\n", "two.trs": ":test-result: FAIL\n"},
                                       exceptions={"gmp.allow": "@min-pass 1\n:test-result: FAIL\n"}).returncode, 0)

    def test_reviewed_exception_must_account_for_every_dejagnu_total(self):
        allow = {"gcc.allow": "@min-pass 30\nFAIL: gcc.target/i386/pr115102.c scan-assembler-times bswap 1\n"
                              "XPASS: gcc.dg/plugin/crash-test-nested-ice.c (test for excess errors)\n"}
        clean = {name: "# of expected passes\t12\n" for name in ("g++.sum", "libstdc++.sum")}
        failing = ("PASS: first\nFAIL: gcc.target/i386/pr115102.c scan-assembler-times bswap 1\n"
                   "# of expected passes\t12\n# of unexpected failures\t1\n")
        self.assertEqual(self.judge("gcc", dict(clean, **{"gcc.sum": failing}), exceptions=allow).returncode, 0)
        # A total that the named lines do not explain, in either direction, refuses.
        hidden = failing.replace("unexpected failures\t1", "unexpected failures\t2")
        self.assertNotEqual(self.judge("gcc", dict(clean, **{"gcc.sum": hidden}), exceptions=allow).returncode, 0)
        uncounted = failing + "XPASS: gcc.dg/plugin/crash-test-nested-ice.c (test for excess errors)\n"
        self.assertNotEqual(self.judge("gcc", dict(clean, **{"gcc.sum": uncounted}), exceptions=allow).returncode, 0)
        counted = uncounted + "# of unexpected successes\t1\n"
        self.assertEqual(self.judge("gcc", dict(clean, **{"gcc.sum": counted}), exceptions=allow).returncode, 0)
        self.assertEqual(len((self.directory / "nonpass.observed").read_text().splitlines()), 2)
        # A count with no named result cannot be reviewed line by line.
        nameless = "# of expected passes\t12\n# of unexpected failures\t1\n"
        self.assertNotEqual(self.judge("gcc", dict(clean, **{"gcc.sum": nameless}), exceptions=allow).returncode, 0)
        # The reviewed exception does not replace the per-component positive results.
        self.assertNotEqual(self.judge("gcc", {"gcc.sum": failing, "g++.sum": clean["g++.sum"]}, exceptions=allow).returncode, 0)
        low = dict(allow, **{"gcc.allow": allow["gcc.allow"].replace("@min-pass 30", "@min-pass 37")})
        self.assertNotEqual(self.judge("gcc", dict(clean, **{"gcc.sum": failing}), exceptions=low).returncode, 0)

    def test_committed_exception_lists_are_exact_lines_with_one_floor_and_a_recorded_basis(self):
        directory = AUDIT.parent / "suite-exceptions"
        lists = sorted(directory.glob("*.allow"))
        self.assertTrue({path.stem for path in lists} <= set(build.REVIEWED_EXCEPTION_SUITES))
        for path in lists:
            raw = path.read_bytes()
            lines = raw.decode("utf-8").splitlines()
            with self.subTest(path=path.name):
                self.assertNotIn(b"\r", raw)
                self.assertEqual(sum(line.startswith("@min-pass ") for line in lines), 1)
                self.assertEqual([line for line in lines if line.startswith("@") and not line.startswith("@min-pass ")], [])
                results = [line for line in lines if line and not line.startswith(("#", "@"))]
                self.assertEqual(len(results), len(set(results)))
                for line in results:
                    self.assertRegex(line, r"^(FAIL|XPASS|UNRESOLVED|ERROR): \S")
                    self.assertEqual(line, line.rstrip())
                # Every list states where its entries were observed and why they are expected.
                self.assertTrue(any(line.startswith("# Basis:") for line in lines))
                self.assertTrue(any(line.startswith("# Observed:") for line in lines))

    def test_reviewed_exception_receipt_is_bound_to_the_staged_list(self):
        root = self.directory / "root"
        log = root / "sources/log"
        evidence = log / "native-suites/ch08-05-glibc-006"
        evidence.mkdir(parents=True)
        staged = root / "tup-build/native/profiles/lfs-13.1-systemd/suite-exceptions"
        staged.mkdir(parents=True)
        (staged / "glibc.allow").write_bytes(b"@min-pass 1\nFAIL: io/tst-lchmod\n")
        (evidence / "nonpass.observed").write_bytes(b"FAIL: io/tst-lchmod\n")
        (evidence / "nonpass.unexplained").write_bytes(b"")
        manifest = evidence / "files.sha256"

        def receipt(**changes):
            manifest.write_bytes("".join(f"{build.digest(path)}  {path.name}\n" for path in sorted(evidence.iterdir())
                                         if path.name != "files.sha256").encode())
            row = {"package": "glibc", "status": "passed", "exit_code": 0, "directory": "native-suites/ch08-05-glibc-006",
                   "manifest_sha256": build.digest(manifest), "command_exit_code": 2, "reviewed_exceptions": 1,
                   "exceptions_sha256": build.digest(staged / "glibc.allow")}
            row.update(changes)
            (log / "receipts.jsonl").write_bytes(build.encoded({"native_suite_evidence": row}).replace(b"\n", b"") + b"\n")

        receipt()
        self.assertEqual(build.verify_suite_evidence(root)["glibc"]["reviewed_exceptions"], 1)
        for changes in ({"exceptions_sha256": "0" * 64}, {"reviewed_exceptions": 2}, {"reviewed_exceptions": "1"},
                        {"reviewed_exceptions": 0}, {"reviewed_exceptions": 0, "exceptions_sha256": None}):
            with self.subTest(changes=changes):
                receipt(**changes)
                with self.assertRaisesRegex(build.Refusal, "exception"):
                    build.verify_suite_evidence(root)
        (evidence / "nonpass.unexplained").write_bytes(b"FAIL: other\n")
        receipt()
        with self.assertRaisesRegex(build.Refusal, "differ from the reviewed staged list"):
            build.verify_suite_evidence(root)

    def test_retained_suite_manifest_detects_tamper_and_extra_files(self):
        root = self.directory / "root"
        log = root / "sources/log"
        evidence = log / "native-suites/ch08-05-glibc-006"
        evidence.mkdir(parents=True)
        result = evidence / "result.log"
        result.write_bytes(b"PASS: fixture\n")
        manifest = evidence / "files.sha256"
        manifest.write_bytes(f"{build.digest(result)}  result.log\n".encode())
        row = {"native_suite_evidence": {"package": "glibc", "status": "passed", "exit_code": 0,
               "directory": "native-suites/ch08-05-glibc-006", "manifest_sha256": build.digest(manifest)}}
        (log / "receipts.jsonl").write_bytes(build.encoded(row).replace(b"\n", b"") + b"\n")
        self.assertIn("glibc", build.verify_suite_evidence(root))
        with self.assertRaisesRegex(build.Refusal, "not every required"):
            build.verify_suite_evidence(root, require_complete=True)
        result.write_bytes(b"PASS: changed\n")
        with self.assertRaisesRegex(build.Refusal, "changed or unlisted"):
            build.verify_suite_evidence(root)
        result.write_bytes(b"PASS: fixture\n")
        (evidence / "unlisted.log").write_bytes(b"extra")
        with self.assertRaisesRegex(build.Refusal, "changed or unlisted"):
            build.verify_suite_evidence(root)

    def test_distributor_verified_flag_without_signature_linkage_is_refused(self):
        with self.assertRaisesRegex(build.Refusal, "incomplete distributor"):
            build.validate_distributor_auth({"name": "fixture.tar", "authentication": {"status": "verified"}})

    def distributor_fixture(self):
        def material(url="https://example.invalid/evidence"):
            return {"path": "fixture.evidence", "url": url, "sha256": "1" * 64}
        fingerprint = "DCD05B71EAB94199527F44ACDB6B8C1F96D8BF6D"
        entry = {"name": "fixture.tar", "authentication": {
            "distributor": "Gentoo", "primary_fingerprint": fingerprint, "signing_fingerprint": "A" * 40,
            "snapshot_sha256": "1" * 64, "manifest_sha256": "1" * 64,
            "manifest_member": "gentoo-20261103/sys-libs/fixture/Manifest", "source_digest_algorithm": "sha512",
            "source_digest": "2" * 128, "source_size": 12, "verifier_sha256": "3" * 64, "status_sha256": "4" * 64},
            "verification_material": {"method": "distributor-openpgp-manifest", "distributor": "Gentoo",
                "snapshot": {"material": material(), "authentication": {"method": "openpgp",
                    "primary_fingerprint": fingerprint, "key": material(), "signature": material(),
                    "approval": {"reviewed_at": "fixture", "basis": "fixture", "material": material("https://www.gentoo.org/downloads/signatures/")}}},
                "manifest_member": "gentoo-20261103/sys-libs/fixture/Manifest", "manifest": material(),
                "reviewed_exception": {"reviewed_at": "fixture", "reason": "fixture"}}}
        return entry

    def test_distributor_linkage_must_match_approved_snapshot_and_manifest(self):
        entry = self.distributor_fixture()
        build.validate_distributor_auth(entry)
        for field, value in (("snapshot_sha256", "5" * 64), ("manifest_member", "../escape"),
                             ("primary_fingerprint", "F" * 40), ("source_size", 0)):
            changed = copy.deepcopy(entry)
            changed["authentication"][field] = value
            with self.subTest(field=field), self.assertRaises(build.Refusal):
                build.validate_distributor_auth(changed)

    def test_make_equivalence_requires_verified_nested_reference_and_exact_archive_pair(self):
        reference = self.distributor_fixture()
        reference["authentication"].update(status="verified", trust_class="distributor-openpgp-manifest", evidence_sha256="6" * 64)
        entry = {"name": "make-4.4.1.tar.gz", "authentication": {
                    "reference_name": "make-4.4.1.tar.lz", "reference_sha256": "7" * 64,
                    "uncompressed_sha256": "8" * 64, "uncompressed_size": 512, "source_size": 128,
                    "decompressor": {"sha256": "9" * 64}, "reference_authentication": reference["authentication"]},
                 "verification_material": {"method": "distributor-openpgp-tar-equivalence",
                    "reference_archive": {"path": "make-4.4.1.tar.lz", "url": "https://example.invalid/make", "sha256": "7" * 64},
                    "reference_authentication": reference["verification_material"]}}
        build.validate_tar_equivalence(entry)
        for mutate in (
            lambda item: item.update(name="other.tar.gz"),
            lambda item: item["authentication"]["reference_authentication"].pop("status"),
            lambda item: item["authentication"].update(uncompressed_size=0),
            lambda item: item["authentication"].update(reference_sha256="0" * 64),
        ):
            changed = copy.deepcopy(entry)
            mutate(changed)
            with self.assertRaises(build.Refusal):
                build.validate_tar_equivalence(changed)

    def test_extra_suite_formats_require_passes_and_preserve_skipped_cases(self):
        console = "all.tcl:\tTotal\t10\tPassed\t8\tSkipped\t2\tFailed\t0\n"
        self.assertEqual(self.judge("expect", {}, console).returncode, 0)
        self.assertNotEqual(self.judge("expect", {}, console.replace("Failed\t0", "Failed\t1")).returncode, 0)
        self.assertNotEqual(self.judge("tcl", {}, console + "all.tcl: Total 2 Passed 1 Skipped 0 Failed 1\n").returncode, 0)
        self.assertEqual(self.judge("tar", {"tests/testsuite.log": "All 2 tests were successful.\n"}, " 1: first ok\n 2: second ok\n").returncode, 0)
        self.assertNotEqual(self.judge("tar", {"tests/testsuite.log": "0 tests were successful.\n"}, "").returncode, 0)
        self.assertNotEqual(self.judge("python-temporary", {"native-python-backports.trs": ":test-result: PASS\n"}).returncode, 0)
        self.assertEqual(self.judge("python-temporary", {"native-python-backports.trs": ":test-result: PASS\n" * 2}).returncode, 0)

    def test_python_full_suite_cannot_be_all_skipped_or_hide_junit_errors(self):
        spec = importlib.util.spec_from_file_location("python_results", AUDIT.parent / "python-suite-results.py")
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        xml = self.directory / "results.xml"
        xml.write_text('<testsuites><testsuite failures="0" errors="0"><testcase name="pass"/><testcase name="skip"><skipped/></testcase></testsuite></testsuites>')
        self.assertEqual(helper.judge(xml), (1, 1))
        for body in ('<testcase><skipped/></testcase>', '<testcase><failure/></testcase>', '<testcase><error/></testcase>', ''):
            xml.write_text('<testsuites><testsuite>' + body + '</testsuite></testsuites>')
            with self.assertRaises(ValueError):
                helper.judge(xml)

    def test_backport_dispositions_require_both_exact_current_inputs(self):
        inputs, fields = {}, {}
        for field, name in (("native_patch", "python-3.14.10-security-backports.patch"), ("native_review", "PYTHON-BACKPORT-REVIEW.json")):
            key = "native/profiles/lfs-13.1-systemd/" + name
            inputs[key] = TUP / key
            fields[field] = {"path": "tup/" + key, "sha256": build.digest(inputs[key])}
        records = [{"id": identifier, "package": "python", "disposition": "fixed-by-native-patch",
                    "selected_sources": ["Python-3.14.10.tar.xz"], **fields} for identifier in ("sa-13.1-088", "sa-13.1-089")]
        build.validate_native_patch_dispositions(records, inputs)
        with self.assertRaises(build.Refusal):
            build.validate_native_patch_dispositions(records[:1], inputs)
        changed = copy.deepcopy(records)
        changed[0]["native_patch"]["sha256"] = "0" * 64
        with self.assertRaises(build.Refusal):
            build.validate_native_patch_dispositions(changed, inputs)

    def test_manual_inventory_refuses_links_traversal_and_executable_members(self):
        spec = importlib.util.spec_from_file_location("manual_inventory", AUDIT.parent / "install-systemd-man.py")
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        members = []
        for number in range(1256):
            member = tarfile.TarInfo(f"systemd-man-pages-261.2/man1/fixture-{number}.1")
            member.mode, member.size = 0o644, 20
            members.append(member)
        class Archive:
            def getmembers(self):
                return members
        self.assertEqual(len(helper.inventory(Archive())), 1256)
        for field, value in (("name", "systemd-man-pages-261.2/../../escape"),
                             ("type", tarfile.SYMTYPE), ("mode", 0o755),
                             ("name", "systemd-man-pages-261.2/bin/tool")):
            original = copy.copy(members[0])
            setattr(members[0], field, value)
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                helper.inventory(Archive())
            members[0] = original

    def test_remaining_exceptions_require_exact_reviewed_source_tuples(self):
        policy = json.loads((AUDIT.parent / "REMAINING-SOURCE-PROVENANCE.json").read_bytes())
        for item in policy["sources"]:
            auth = {"status": "accepted-exception", "trust_class": item["proposed_class"],
                    "policy_sha256": build.REMAINING_SOURCE_POLICY, "source_size": item["size"], "assurance": item["assurance"]}
            material = {"method": item["proposed_class"], "policy": {"path": "remaining-source-provenance-review.json", "sha256": build.REMAINING_SOURCE_POLICY}}
            if "material" in item:
                auth.update(distributor="NetBSD pkgsrc", source_digest_algorithm="sha512", source_digest=item["published_sha512"],
                            material_sha256=item["material"]["sha256"], required_gates=["required-package-tests"])
                material["material"] = item["material"]
            else:
                auth.update(inventory_sha256=item["inventory"]["sha256"], install_destination="/usr/share/man",
                            required_gates=["documentation-install-confinement", "documentation-inventory"])
                material.update(inventory=item["inventory"], book_material=item["book_material"])
            entry = {"name": item["name"], "sha256": item["sha256"], "authentication": auth, "verification_material": material}
            build.validate_remaining_exception(entry)
            entry["sha256"] = "0" * 64
            with self.assertRaises(build.Refusal):
                build.validate_remaining_exception(entry)

    def test_python_patch_adapter_refuses_changed_original_bytes(self):
        spec = importlib.util.spec_from_file_location("native_python_adapter", TUP / "native/profiles/lfs-13.1-systemd/adapt-python-openssl.py")
        adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter)
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            adapter.adapt(b"different patch\n")

    def test_patch_exception_is_limited_to_exact_approved_name_digest_and_policy(self):
        name = "glibc-fhs-1.patch"
        expected = build.LFS_PATCH_EXCEPTIONS[name]
        entry = {"name": name, "sha256": expected[0], "authentication": {
                    "status": "accepted-exception", "policy_sha256": build.LFS_PATCH_POLICY,
                    "corroboration_sha256": build.LFS_PATCH_CORROBORATION, "git_commit": build.LFS_PATCH_COMMIT,
                    "git_blob": expected[1], "required_gates": ["selected-version-patch-application", "required-package-tests"],
                    "assurance": "fixture unsigned provenance exception"},
                 "verification_material": {"method": "reviewed-lfs-patch-exception",
                    "policy": {"path": "lfs-patch-provenance-review.json", "sha256": build.LFS_PATCH_POLICY},
                    "corroboration": {"path": "lfs-patch-corroboration-13.1.json", "sha256": build.LFS_PATCH_CORROBORATION}}}
        build.validate_patch_exception(entry)
        for field, value in (("name", "other.patch"), ("sha256", "0" * 64)):
            changed = copy.deepcopy(entry)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(build.Refusal):
                build.validate_patch_exception(changed)
        for field, value in (("status", "verified"), ("policy_sha256", "0" * 64),
                             ("git_blob", "0" * 40), ("required_gates", [])):
            changed = copy.deepcopy(entry)
            changed["authentication"][field] = value
            with self.subTest(field=field), self.assertRaises(build.Refusal):
                build.validate_patch_exception(changed)

    def test_context_adapter_refuses_unknown_or_changed_patches(self):
        spec = importlib.util.spec_from_file_location("native_context_adapter", TUP / "native/profiles/lfs-13.1-systemd/adapt-patch-context.py")
        adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter)
        for name in ("coreutils-9.11-i18n-1.patch", "kbd-2.10.0-backspace-1.patch", "unknown.patch"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "unreviewed"):
                adapter.adapt(name, b"different context\n")

    def test_validation_only_cannot_execute_an_incomplete_stage(self):
        with patch.object(build.subprocess, "run") as child, self.assertRaisesRegex(build.Refusal, "validation never executes"):
            build.run_stage(self.directory, "ch05", ["must-not-run"], "1" * 64, validation_only=True)
        child.assert_not_called()
        self.assertFalse((self.directory / "ch05.json").exists())

    def test_only_exact_build_only_h55_deferral_is_accepted(self):
        lock = {"lock_purpose": "build-only", "release_eligible": False,
                "release_gates": [{"id": "H55", "status": "open", "advisories": ["CVE-2025-66382"],
                                   "required_evidence": ["host XML exposure review", "workload CPU/time containment demonstrated or qualified upstream fix"]}],
                "advisory_review": {"dispositions": [{"id": "upstream-expat-CVE-2025-66382", "package": "expat",
                    "disposition": "deferred-release-gate", "gate_id": "H55", "selected_sources": ["expat-2.10.0.tar.xz"],
                    "reason": "known CPU denial of service remains unfixed", "evidence": [{"sha256": "1" * 64}]}]}}
        build.validate_release_policy(lock)
        for field, value in (("lock_purpose", "production"), ("release_eligible", True), ("release_gates", [])):
            changed = copy.deepcopy(lock)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(build.Refusal):
                build.validate_release_policy(changed)
        changed = copy.deepcopy(lock)
        changed["advisory_review"]["dispositions"][0]["id"] = "arbitrary-exception"
        with self.assertRaisesRegex(build.Refusal, "unknown or incomplete"):
            build.validate_release_policy(changed)

    def stage_fixture(self):
        root = self.directory / "root"
        home = self.directory / "home"
        home.mkdir()
        for relative in ("usr/bin", "usr/lib", "usr/sbin", "etc", "var", "lib64", "sources/log", "tup-build"):
            (root / relative).mkdir(parents=True, exist_ok=True)
        for name in ("bin", "lib", "sbin"):
            (root / name).symlink_to("usr/" + name, target_is_directory=True)
        (root / "tup-build/BUILD-INPUTS.json").write_bytes(b'{"fixture":true}\n')
        (root / "tup-build/driver.sh").write_bytes(b'''#!/bin/bash
set -eu
[ -z "${NATIVE_POISON+set}" ]
printf '%s\\n' "$TUP_PROFILE" "$TUP_TESTS" "$MAKEFLAGS" "$TESTSUITEFLAGS" "$NINJAJOBS" "$TUP_TEST_JOBS" "$TUP_NATIVE_CHROOT" "$TUP_VALIDATE_ONLY" "$PIP_NO_INDEX" > "$HOME/environment.capture"
''')
        shim = self.directory / "shim"
        shim.mkdir()
        for name, data in {"id": "#!/bin/bash\nprintf '0\\n'\n",
                           "runuser": '#!/bin/bash\n[ "$1" = -u ] && [ "$3" = -- ] || exit 90\nshift 3\nexec "$@"\n'}.items():
            (shim / name).write_text(data, encoding="utf-8")
            (shim / name).chmod(0o755)
        environment = dict(os.environ, PATH=str(shim) + ":/usr/bin:/bin", NATIVE_POISON="must-not-leak")
        command = [BASH, str(TUP / "native/run-stage.sh"), "ch05", str(root), "fixture", str(home), "8", "lfs-13.1-systemd"]
        return root, home, environment, command

    def test_chroot_entry_and_keymap_check_match_how_the_target_runs(self):
        # Both were measured in the rehearsal: with the empty supplementary group
        # list of a service unit, coreutils' chroot-credentials root test fails;
        # and upstream's qwerty/lt.map compiles only in the Unicode mode that
        # systemd-vconsole-setup uses.
        runner = (TUP / "native/run-stage.sh").read_text(encoding="utf-8")
        self.assertEqual(runner.count("exec chroot "), 1)
        self.assertIn('exec chroot --groups=+0 "$root" /usr/bin/env -i ', runner)
        keymaps = (AUDIT.parent / "kbd-keymap-tests.sh").read_text(encoding="utf-8")
        commands = [line.strip() for line in keymaps.splitlines() if line.strip().startswith("./src/loadkeys")]
        self.assertEqual(commands, ['./src/loadkeys --unicode --bkeymap "data/keymaps/i386/$map" > "$output"'])

    @unittest.skipIf(os.name != "posix", "Linux runner with harmless account/driver stubs")
    def test_stage_runner_cleans_environment_and_bounds_build_and_test_jobs(self):
        root, home, environment, command = self.stage_fixture()
        result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((home / "environment.capture").read_text().splitlines(),
                         ["native-x86_64-lfs-13.1-systemd-core", build.NATIVE13_TESTS,
                          "-j8", "-j4", "8", "4", "0", "0", "1"])
        result = subprocess.run([*command, "--validate"], env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((home / "environment.capture").read_text().splitlines()[7], "1")

    @unittest.skipIf(os.name != "posix", "Linux runner path/context fixture")
    def test_stage_runner_refuses_redirected_inputs_and_unknown_profile_before_child(self):
        root, home, environment, command = self.stage_fixture()
        result = subprocess.run([*command[:-1], "other-profile"], env=environment, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        original = root / "tup-build/BUILD-INPUTS.json"
        original.rename(root / "original.json")
        original.symlink_to(root / "original.json")
        result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((home / "environment.capture").exists())

    @unittest.skipIf(os.name != "posix", "Linux filesystem ownership/context fixture")
    def test_control_path_symlink_and_writable_ancestor_refuse(self):
        workspace = self.directory / "workspace"
        workspace.mkdir()
        # A root-owned marker cannot authorize a writable /tmp ancestor.
        with self.assertRaisesRegex(build.Refusal, "root-owned"):
            build.validate_control_paths(workspace)
        redirected = self.directory / "redirected"
        redirected.symlink_to(workspace, target_is_directory=True)
        with self.assertRaisesRegex(build.Refusal, "symlink/redirected"):
            build.plain_path(str(redirected))


if __name__ == "__main__":
    unittest.main()
