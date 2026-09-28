"""t/preflight.py's grading-machine plumbing (2026-09-28): `T_LAB=local`
runs the same inspection here instead of over ssh to oneself, and the
environment's T_LAB wins over t/lab-workstation.conf, as the launcher
documents. No kernel, no network."""
import os
import tempfile
import unittest
from pathlib import Path

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
