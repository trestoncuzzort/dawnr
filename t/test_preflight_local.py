"""t/preflight.py's grading-machine plumbing (2026-09-28): `T_LAB=local`
runs the same inspection here instead of over ssh to oneself, and the
environment's T_LAB wins over t/lab-workstation.conf, as the launcher
documents. No kernel, no network."""
import os
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import preflight


class GraderRunTests(unittest.TestCase):
    def test_local_runs_here_from_home(self):
        out = preflight.grader_run("local", "echo hi; pwd", 10)
        self.assertEqual(out.returncode, 0)
        lines = out.stdout.splitlines()
        self.assertEqual(lines[0], "hi")
        self.assertEqual(Path(lines[1]).resolve(), Path.home().resolve())

    def test_local_relative_cd_resolves_like_an_ssh_login(self):
        # the files check does `cd tup` (LAB_DIR) relative to the login cwd
        out = preflight.grader_run("local", "cd .. && echo ok", 10)
        self.assertEqual(out.stdout.strip(), "ok")

    def test_local_exit_code_is_the_commands(self):
        self.assertEqual(preflight.grader_run("local", "exit 9", 10).returncode, 9)

    @unittest.skipIf(os.name == "nt", "POSIX executable PATH probe")
    def test_local_keeps_the_kernel_path_already_checked_by_preflight(self):
        with tempfile.TemporaryDirectory() as directory:
            probe = Path(directory) / "dawnr-preflight-path-probe"
            probe.write_text("#!/bin/sh\nprintf 'inherited-path\\n'\n")
            probe.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": directory + os.pathsep + os.environ["PATH"]}):
                result = preflight.grader_run("local", probe.name, 10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "inherited-path\n")

    @unittest.skipIf(os.name == "nt", "POSIX checkout-path probe")
    def test_local_inspects_the_current_checkout_in_a_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="preflight checkout ") as directory:
            root = Path(directory)
            (root / "sentinel").write_text("this checkout\n")
            with mock.patch.object(preflight, "ROOT", root):
                command = f"cd {shlex.quote(preflight.grading_directory('local'))} && cat sentinel"
                result = preflight.grader_run("local", command, 10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "this checkout\n")


class GradingMachineTests(unittest.TestCase):
    def test_environment_wins_over_the_conf(self):
        with tempfile.TemporaryDirectory() as d:
            conf = Path(d) / "lab-workstation.conf"
            conf.write_text("T_LAB=someone@10.0.0.9\n", encoding="utf-8")
            self.assertEqual(preflight.grading_machine({"T_LAB": "local"}, conf), "local")
            self.assertEqual(preflight.grading_machine({}, conf), "someone@10.0.0.9")

    def test_no_conf_no_env_means_no_grading_machine(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(preflight.grading_machine({}, Path(d) / "absent.conf"))
            self.assertIsNone(preflight.grading_machine({"T_LAB": ""}, Path(d) / "absent.conf"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
