"""The CLI's public output and exit status are contracts for build pipelines."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cli
import harness
import tasks_io


class DirectoryVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tasks = self.root / "input"
        self.tasks.mkdir()
        self.source = self.tasks / "flight-check.t"
        self.source.write_bytes((cli.HERE / "tasks" / "abs.t").read_bytes())
        self.table = self.root / "report.md"
        self.table.write_text("previous complete report\n")
        self.out = self.root / "lowered"
        self.calls = []
        self.original_out = harness.OUT
        self.addCleanup(setattr, harness, "OUT", self.original_out)
        self.enterContext(patch.dict(os.environ, {"T_MIN_KERNELS": "2"}))
        self.probe = self.enterContext(patch.object(
            cli.run_par, "probe_backends", return_value=(
                [("dafny", "test 1"), ("lean", "test 1"), ("rocq", "ABSENT: unavailable")],
                [("dafny", None, "dfy"), ("lean", None, "lean")])))
        self.enterContext(patch.object(cli.run_par, "lower_and_dispatch", self.dispatch))

    def dispatch(self, paths, present, jobs, flake):
        self.calls.append((paths, present, jobs, flake))
        print("lowering and verifier progress")
        return ({tasks_io.load_task(p)["name"]: {
            k: ("verified", "refuted", True) for k, _, _ in present} for p in paths}, {}, True)

    def invoke(self, *extra):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli.main(["verify", str(self.tasks), "--table", str(self.table),
                             "--out", str(self.out), *extra])
        return code, stdout.getvalue(), stderr.getvalue()

    def records(self, output):
        return [json.loads(line) for line in output.splitlines() if line.strip()]

    def test_json_stdout_contains_only_json_and_progress_goes_to_stderr(self):
        code, out, err = self.invoke("--json")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.records(out)), 2)
        self.assertIn("verifier progress", err)

    def test_reports_actual_source_filename(self):
        _, out, _ = self.invoke("--json")
        records = self.records(out)
        self.assertEqual({r["file"] for r in records}, {str(self.source)})

    def test_reports_actual_json_source_filename(self):
        task = tasks_io.load_task(self.source)
        self.source.unlink()
        self.source = self.tasks / "imported-program.json"
        self.source.write_text(json.dumps(task))
        _, out, _ = self.invoke("--json")
        self.assertEqual({r["file"] for r in self.records(out)}, {str(self.source)})

    def test_explicit_missing_kernel_refuses_before_dispatch(self):
        code, out, _ = self.invoke("--json", "--kernels", "dafny,lean,rocq")
        self.assertEqual(code, 2)
        self.assertFalse(self.calls)
        self.assertIn("rocq", self.records(out)[0]["message"])
        self.assertEqual(self.table.read_text(), "previous complete report\n")

    def test_minimum_kernels_refuses_before_dispatch(self):
        with patch.dict(os.environ, {"T_MIN_KERNELS": "3"}):
            code, out, _ = self.invoke("--json")
        self.assertEqual(code, 2)
        self.assertFalse(self.calls)
        self.assertEqual(self.records(out)[0]["severity"], "error")

    def test_empty_input_refuses_before_probing(self):
        self.source.unlink()
        code, out, _ = self.invoke("--json")
        self.assertEqual(code, 2)
        self.probe.assert_not_called()
        self.assertFalse(self.calls)
        self.assertIn("no tasks", self.records(out)[0]["message"])

    def test_partial_repetitions_cannot_publish_an_agreement_table(self):
        for repeats in (1, 2):
            with self.subTest(repeats=repeats):
                code, out, _ = self.invoke("--json", "--flake", str(repeats))
                self.assertEqual(code, 2)
                self.assertFalse(self.calls)
                self.assertEqual(self.table.read_text(), "previous complete report\n")
                self.assertIn("three", self.records(out)[0]["message"])

    def test_nonpositive_worker_counts_refuse_before_dispatch(self):
        for jobs in (0, -1):
            with self.subTest(jobs=jobs):
                code, out, _ = self.invoke("--json", "--jobs", str(jobs))
                self.assertEqual(code, 2)
                self.assertFalse(self.calls)
                self.assertIn("positive", self.records(out)[0]["message"])

    def test_failed_atomic_replacement_preserves_previous_report(self):
        with patch("os.replace", side_effect=OSError("injected report failure")):
            code, out, _ = self.invoke("--json")
        self.assertEqual(code, 1)
        self.assertEqual(self.table.read_text(), "previous complete report\n")
        self.assertEqual(self.records(out)[0]["severity"], "error")
        self.assertEqual(sorted(p.name for p in self.root.iterdir()),
                         ["input", "lowered", "report.md"])

    def test_successful_call_restores_output_directory_for_next_caller(self):
        code, _, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(harness.OUT, self.original_out)

    def test_report_symlink_keeps_pointing_to_the_updated_target(self):
        target = self.root / "saved-report.md"
        self.table.rename(target)
        self.table.symlink_to(target)
        code, _, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertTrue(self.table.is_symlink())
        self.assertIn("verified / refuted", target.read_text())

    def test_default_text_mode_still_publishes_three_repeat_agreement(self):
        code, out, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(self.calls[0][3], 3)
        self.assertIn("FULL AGREEMENT", out)
        self.assertIn("verified / refuted", self.table.read_text())


if __name__ == "__main__":
    unittest.main()
