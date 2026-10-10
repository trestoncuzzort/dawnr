#!/usr/bin/env python3
"""A flight correspondence verdict requires a complete, successful, nonempty execution."""
from __future__ import annotations

import contextlib
import io
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "flight"))
import px4_diff as diff  # noqa: E402
import px4_stmt as stmt  # noqa: E402


def completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(["test-tool"], returncode, stdout, stderr)


class ProcessOutcomes(unittest.TestCase):
    def test_diff_rejects_unsuccessful_runtime_even_with_complete_stdout(self):
        for code in (7, -9):
            with self.subTest(returncode=code), patch.object(diff.subprocess, "run", side_effect=[
                    completed(), completed(code, "1\n", "deliberate failure")]):
                out, error = diff._compile_run("", Path("unused"))
                self.assertIsNone(out)
                self.assertIn("runtime", error)
                self.assertIn(str(code), error)

    def test_statement_rejects_unsuccessful_runtime_even_with_complete_stdout(self):
        for code in (7, -9):
            with self.subTest(returncode=code), patch.object(diff.subprocess, "run", side_effect=[
                    completed(), completed(code, "1\n2\n", "deliberate failure")]):
                with self.assertRaisesRegex(RuntimeError, "runtime"):
                    stmt.run_cpp("", "", [1, 2], False, Path("unused"))

    def test_diff_names_compile_and_runtime_start_or_timeout_errors(self):
        for stage in ("compile", "runtime"):
            for failure in (FileNotFoundError("missing-tool"), subprocess.TimeoutExpired("tool", 1)):
                with self.subTest(stage=stage, failure=type(failure).__name__):
                    effects = [failure] if stage == "compile" else [completed(), failure]
                    with patch.object(diff.subprocess, "run", side_effect=effects):
                        out, error = diff._compile_run("", Path("unused"))
                    self.assertIsNone(out)
                    self.assertIn(stage, error)

    def test_statement_names_compile_and_runtime_start_or_timeout_errors(self):
        for stage in ("compile", "runtime"):
            for failure in (FileNotFoundError("missing-tool"), subprocess.TimeoutExpired("tool", 1)):
                with self.subTest(stage=stage, failure=type(failure).__name__):
                    effects = [failure] if stage == "compile" else [completed(), failure]
                    with patch.object(diff.subprocess, "run", side_effect=effects):
                        with self.assertRaisesRegex(RuntimeError, stage):
                            stmt.run_cpp("", "", [1], False, Path("unused"))

    def test_compilation_failures_remain_errors(self):
        with patch.object(diff.subprocess, "run", return_value=completed(1, stderr="compile control")):
            out, error = diff._compile_run("", Path("unused"))
        self.assertIsNone(out)
        self.assertIn("compile error", error)
        with patch.object(diff.subprocess, "run", return_value=completed(1, stderr="compile control")):
            with self.assertRaisesRegex(RuntimeError, "compile error"):
                stmt.run_cpp("", "", [1], False, Path("unused"))

    @unittest.skipUnless(shutil.which("g++"), "requires a local C++ compiler")
    def test_real_process_stopping_after_a_prefix_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            header = root / "src/lib/mathlib/mathlib.h"
            header.parent.mkdir(parents=True)
            header.write_text("")
            wrapper = "#include <cstdlib>\nlong long run(long long x) { {LINES} }"
            body = "if (x == 2) { fflush(stdout); std::exit(7); } return x;"
            with self.assertRaisesRegex(RuntimeError, "runtime.*7"):
                stmt.run_cpp(body, wrapper, [1, 2, 3], False, root)


class StatementCoverage(unittest.TestCase):
    def run_output(self, stdout, *, inputs=(1, 2), two=False):
        with patch.object(diff.subprocess, "run", side_effect=[completed(), completed(stdout=stdout)]):
            return stmt.run_cpp("", "", list(inputs), two, Path("unused"))

    def test_complete_single_and_paired_results_are_preserved(self):
        self.assertEqual(self.run_output("1\n2\n"), [(1,), (2,)])
        self.assertEqual(self.run_output("10 1\n20 2\n", two=True), [(10, 1), (20, 2)])

    def test_missing_extra_and_malformed_output_rows_are_errors(self):
        for output in ("", "1\n", "1\n2\n3\n", "1\nno-number\n", "1\n\n", "1\n2\n\n"):
            with self.subTest(output=output), self.assertRaisesRegex(RuntimeError, "output"):
                self.run_output(output)

    def test_wrong_result_width_is_an_error(self):
        for output, two in (("1 9\n2 9\n", False), ("1\n2\n", True), ("\n2\n", False)):
            with self.subTest(output=output, two=two), self.assertRaisesRegex(RuntimeError, "output"):
                self.run_output(output, two=two)

    def test_empty_input_set_is_refused_before_compilation(self):
        with patch.object(diff.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "input"):
                stmt.run_cpp("", "", [], False, Path("unused"))
            run.assert_not_called()

    def test_comparison_refuses_short_results_instead_of_counting_the_prefix(self):
        spec = dict(stmt.PAIRS["arm_disarm"], domain=[0, 1, 257])
        with patch.object(stmt, "source", return_value=""), patch.object(stmt, "cut", return_value=""), \
                patch.object(stmt, "run_cpp", return_value=[(0,)]), patch.object(stmt, "t_result", return_value=0):
            with self.assertRaisesRegex(RuntimeError, "output"):
                stmt.check("arm_disarm", spec, Path("unused"))

    def test_comparison_refuses_a_domain_outside_the_preconditions(self):
        spec = dict(stmt.PAIRS["arm_disarm"], domain=[0, 1, 257])
        with patch.object(stmt, "source", return_value=""), patch.object(stmt, "cut", return_value=""), \
                patch.object(stmt, "run_cpp", return_value=[(0,), (0,), (0,)]), \
                patch.object(stmt, "t_result", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "admissible"):
                stmt.check("arm_disarm", spec, Path("unused"))

    def test_complete_statement_comparisons_keep_the_real_input(self):
        spec = dict(stmt.PAIRS["arm_disarm"], domain=[0, 1, 257])
        with patch.object(stmt, "source", return_value=""), patch.object(stmt, "cut", return_value=""), \
                patch.object(stmt, "run_cpp", return_value=[(0,), (0,), (0,)]), \
                patch.object(stmt, "t_result", return_value=0):
            result = stmt.check("arm_disarm", spec, Path("unused"))
        self.assertEqual([(row["inputs"], row["agree"], row["px4_at_real"]) for row in result["rows"]],
                         [(3, 3, 0), (3, 3, 0)])


class CorrespondenceCoverage(unittest.TestCase):
    def test_empty_diff_domain_is_refused_before_compilation(self):
        with patch.object(diff, "program", return_value=("", [], [])), patch.object(diff, "_compile_run") as run:
            result = diff.diff_task(diff.HERE / "px4_min.t", Path("unused"))
        run.assert_not_called()
        self.assertNotEqual(result["status"], "agrees")
        self.assertIn("input", result["status"])

    def test_empty_fix_domain_is_refused_before_compilation(self):
        with patch.object(diff, "program", return_value=("", [], [])), patch.object(diff, "_compile_run") as run:
            result = diff.diff_fix(diff.FIXES / "px4_wrap_bin_fixed.t", Path("unused"), Path("stub"))
        run.assert_not_called()
        self.assertNotEqual(result["status"], "agrees")
        self.assertIn("input", result["status"])

    def test_malformed_float_results_are_named_errors(self):
        with patch.object(diff, "program", return_value=("", ["0x0.0p+0"], [{}])), \
                patch.object(diff, "_compile_run", return_value=(["not-a-float"], "")):
            result = diff.diff_task(diff.HERE / "px4_constrain_f.t", Path("unused"))
        self.assertIn("output", result["status"])

    def test_findings_need_a_counterexample_input(self):
        with patch.object(diff.harness, "real_witness", return_value=None), patch.object(diff, "PROBES", {}), \
                patch.object(diff, "_compile_run") as run:
            result = diff.finding(diff.FINDINGS / "px4_wrap_bin_any.t", Path("unused"))
        run.assert_not_called()
        self.assertEqual(result["status"], "NOT REPRODUCED")

    def test_full_integer_results_preserve_success(self):
        with patch.object(diff, "program", return_value=("", ["1", "2"], [{}, {}])), \
                patch.object(diff, "_compile_run", return_value=(["1", "2"], "")):
            result = diff.diff_task(diff.HERE / "px4_min.t", Path("unused"))
        self.assertEqual(result["status"], "agrees")
        self.assertEqual(result["points"], 2)

    def test_documented_float_parameter_narrowing_still_passes(self):
        task = diff.tasks_io.load_task(str(diff.HERE / "px4_alpha_update.t"))
        reference = diff.interp.Reference(task)
        reference.points = [({"state": 0.0, "sample": 1.0, "alpha": 0.1}, 0.1)]
        narrowed = struct.unpack("f", struct.pack("f", 0.1))[0]
        with patch.object(diff.interp, "Reference", return_value=reference), \
                patch.object(diff, "program", return_value=("", [0.1.hex()], [reference.points[0][0]])), \
                patch.object(diff, "_compile_run", return_value=([narrowed.hex()], "")):
            result = diff.diff_task(diff.HERE / "px4_alpha_update.t", Path("unused"))
        self.assertEqual(result["narrowed_points"], 1)
        self.assertTrue(diff._comparison_passed(result))


class CommandOutcomes(unittest.TestCase):
    def diff_main(self, compare, finding, args=()):
        with patch.object(diff, "fetch_px4", return_value=Path("unused")), \
                patch.object(diff, "diff_task", side_effect=compare), \
                patch.object(diff, "finding", side_effect=finding), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return diff.main(list(args))

    def test_all_compilation_errors_are_a_failed_command(self):
        failure = lambda p, _: {"name": p.stem, "status": "compile error: negative control"}
        self.assertEqual(self.diff_main(failure, failure), 1)

    def test_a_single_execution_error_makes_the_command_fail(self):
        def compare(path, _):
            return {"name": path.stem, "points": 1,
                    "status": "runtime error: negative control" if path.stem == "px4_min" else "agrees"}
        finding = lambda p, _: {"name": p.stem, "status": "PX4 breaks the contract here, as t's body does",
                               "rows": [{"breaks_contract": True}]}
        self.assertEqual(self.diff_main(compare, finding), 1)

    def test_known_skip_does_not_hide_successful_comparisons(self):
        def compare(path, _):
            return {"name": path.stem, "points": 0 if path.stem in diff.NOT_DIFFED else 1,
                    "status": "not diffed: internal" if path.stem in diff.NOT_DIFFED else "agrees"}
        finding = lambda p, _: {"name": p.stem, "status": "PX4 breaks the contract here, as t's body does",
                               "rows": [{"breaks_contract": True}]}
        self.assertEqual(self.diff_main(compare, finding), 0)

    def test_a_completely_empty_or_skipped_run_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for skipped in (False, True):
                if skipped:
                    (root / "px4_interp_index.t").write_text("")
                with self.subTest(skipped=skipped), patch.object(diff, "HERE", root), \
                        patch.object(diff, "FINDINGS", root / "findings"):
                    compare = lambda p, _: {"name": p.stem, "status": "not diffed: internal"}
                    self.assertEqual(self.diff_main(compare, None), 1)

    def test_fixed_tree_without_selected_tasks_fails(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(diff, "FIXES", Path(directory)):
            self.assertEqual(self.diff_main(None, None, ["--fixed-tree", directory]), 1)

    def test_statement_runtime_failure_is_a_failed_command(self):
        with patch.object(stmt, "fetch_px4", return_value=Path("unused")), \
                patch.object(stmt, "check", side_effect=RuntimeError("runtime error: exit 7")), \
                contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(stmt.main([]), 1)
        self.assertIn("runtime error", error.getvalue())

    def test_statement_command_without_pairs_fails(self):
        with patch.object(stmt, "fetch_px4", return_value=Path("unused")), patch.object(stmt, "PAIRS", {}), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(stmt.main([]), 1)


if __name__ == "__main__":
    unittest.main()
