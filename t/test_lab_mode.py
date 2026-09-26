"""t/lab_mode.sh: one driver, two grading machines.

With T_LAB=local, remote() runs a command here in a login shell with ~/tup meaning
this checkout, fetch()/store() drop the host and copy locally, and a copy whose
two ends are the same tree does nothing. With a user@host every function is the
ssh or rsync it replaced (checked with a stub SSH that echoes its arguments).
GNU parallel's ':' login (gnu.org/software/parallel/parallel.html, --sshlogin) and
rsync's local mode (download.samba.org/pub/rsync/rsync.1) are the pattern.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def run(script: str, lab: str = "local", env: dict | None = None) -> subprocess.CompletedProcess:
    full = f'cd "{ROOT}"; LAB={lab}; REPO=tup; SSH="echo SSH"; . t/lab_mode.sh; {script}'
    return subprocess.run(["bash", "-c", full], capture_output=True, text=True, env={**os.environ, **(env or {})})


class LocalModeTests(unittest.TestCase):
    def test_localize_rewrites_the_repository_and_drops_the_host(self):
        out = run('localize "local:~/tup/t/out/x ~/tup ~/tup-grade/y"').stdout
        self.assertEqual(out, f"{ROOT}/t/out/x {ROOT} ~/tup-grade/y")

    def test_remote_runs_here_with_the_checkout_as_the_repository(self):
        out = run('remote "cd ~/tup && pwd"').stdout.strip()
        self.assertEqual(Path(out).resolve(), ROOT.resolve())

    def test_remote_passes_stdin_through(self):
        out = run("printf 'print(6*7)' | remote 'python3 -'").stdout.strip()
        self.assertEqual(out, "42")

    def test_fetch_copies_locally_and_skips_the_same_tree(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "a"
            src.mkdir()
            (src / "f.txt").write_text("x")
            dst = Path(d) / "b"
            r = run(f'fetch -a "local:{src}/" "{dst}/" && cat "{dst}/f.txt"')
            self.assertEqual(r.stdout.strip(), "x", r.stderr)
            # the same directory on both sides: nothing to do, status 0, no rsync invoked
            r = run(f'fetch -a --delete "local:{src}/" "{src}/" && echo skipped')
            self.assertEqual(r.stdout.strip(), "skipped", r.stderr)
            # files stored into the directory they already sit in: skipped too
            r = run(f'store -a "{src}/f.txt" "local:{src}/" && echo skipped')
            self.assertEqual(r.stdout.strip(), "skipped", r.stderr)

    def test_a_workstation_login_still_uses_ssh_and_rsync_unchanged(self):
        out = run('remote "cd ~/tup && true"', lab="user@host").stdout.strip()
        self.assertEqual(out, "SSH user@host cd ~/tup && true")
        lines = run('reachable && echo yes', lab="user@host").stdout.strip().splitlines()
        self.assertEqual(lines, ["SSH user@host true", "yes"])   # the probe went through the stub SSH

    def test_defaults_follow_the_machine(self):
        self.assertEqual(run("default_jobs; default_sets").stdout.split(), ["8", "1"])
        self.assertEqual(run("default_jobs; default_sets", lab="user@host").stdout.split(), ["32", "4"])
        self.assertEqual(run("default_work_dir", lab="user@host").stdout.strip(), "/dev/shm/tup-grade")
        local = run("default_work_dir").stdout.strip()
        self.assertIn(local, ("/dev/shm/tup-grade", str(Path.home() / "tup-grade")))

    def test_the_scripts_parse_and_source_the_mode(self):
        for name in ("grade_lab.sh", "r12_data_queue.sh"):
            r = subprocess.run(["bash", "-n", str(HERE / name)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(". t/lab_mode.sh", (HERE / name).read_text())


if __name__ == "__main__":
    unittest.main()
