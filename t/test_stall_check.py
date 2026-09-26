#!/usr/bin/env python3
"""t/test_stall_check.py -- stall_check names stopped, frozen and orphaned
processes of this user, and a stale output directory, from /proc alone
(r12 blocker A5, 2026-09-25).

A fake /proc tree covers each finding, a process of another user that
must be ignored, a comm with a space and a parenthesis, a reused pid told
apart by its start time, and the exit codes. Two live cases run real
processes: a stopped sleep, and a prover-named sleep that is orphaned.

Standard library only, Linux. unittest.
"""
from __future__ import annotations

import os

import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import stall_check                                            # noqa: E402

CLK = float(os.sysconf("SC_CLK_TCK"))
BTIME = 1_000_000


def fake_proc(root: Path, procs: list[tuple[int, str, str, int, int, float]]) -> None:
    """procs: (pid, comm, state, ppid, uid, start_epoch)."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "stat").write_text(f"cpu  1 2 3 4\nbtime {BTIME}\nprocesses 5\n")
    for pid, comm, state, ppid, uid, start in procs:
        d = root / str(pid)
        d.mkdir()
        ticks = int((start - BTIME) * CLK)
        rest = " ".join(["0"] * 17)      # fields 5..21, then starttime at 22
        (d / "stat").write_text(f"{pid} ({comm}) {state} {ppid} {rest} {ticks} 0 0 0\n")
        (d / "status").write_text(f"Name:\t{comm}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n")


class ParseTests(unittest.TestCase):
    def test_comm_with_space_and_paren_splits_at_the_last_paren(self):
        comm, state, ppid, start = stall_check.parse_stat(
            "42 ((a) b) T 7 " + " ".join(["0"] * 17) + " 12345 0 0\n")
        self.assertEqual((comm, state, ppid, start), ("(a) b", "T", 7, 12345))


class FakeProcTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "proc"
        self.uid = 1234
        t0 = BTIME + 100
        fake_proc(self.root, [
            (1, "systemd", "S", 0, 0, t0),
            (100, "python3", "R", 1, self.uid, t0),          # ours, running, parent 1, not a prover
            (101, "python3", "T", 100, self.uid, t0),        # STOPPED
            (102, "python3", "T", 1, 4321, t0),              # another user: ignored
            (103, "z3", "S", 1, self.uid, t0),               # ORPHAN under pid 1
            (104, "(a) b", "S", 1, self.uid, t0),            # odd comm, not a prover
            (200, "systemd", "S", 1, self.uid, t0),          # the user's subreaper
            (105, "rocqworker", "S", 200, self.uid, t0),     # ORPHAN under systemd
            (106, "z3", "S", 100, self.uid, t0),             # a prover with its driver: fine
            (107, "python3", "S", 100, self.uid, t0 + 1000), # started after frozen.pids: reused
            (108, "python3", "t", 100, self.uid, t0),        # tracing stop: not counted
        ])
        self.frozen = Path(self.tmp.name) / "frozen.pids"
        self.frozen.write_text("100\n101\n999\n107\n\n")
        os.utime(self.frozen, (t0 + 500, t0 + 500))

    def run_main(self, *extra: str) -> tuple[int, str]:
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = stall_check.main(["--proc", str(self.root), "--uid", str(self.uid),
                                   "--frozen", str(self.frozen), *extra])
        return rc, buf.getvalue()

    def test_each_finding_is_named_and_the_rest_ignored(self):
        rc, out = self.run_main()
        self.assertEqual(rc, 1, out)
        self.assertIn("STOPPED pid 101", out)
        self.assertNotIn("pid 102", out)
        self.assertNotIn("pid 108", out)
        self.assertIn("ORPHAN pid 103 (z3) parent pid 1", out)
        self.assertIn("ORPHAN pid 105 (rocqworker) parent systemd (pid 200)", out)
        self.assertNotIn("ORPHAN pid 106", out)
        self.assertNotIn("pid 104", out)
        self.assertIn("FROZEN pid 100", out)
        self.assertIn("FROZEN pid 101", out)
        self.assertNotIn("999", out)
        self.assertIn("note: frozen.pids lists 107", out)
        self.assertNotIn("FROZEN pid 107", out)
        self.assertIn("stall_check: 5 problem(s)", out)

    def test_a_clean_tree_exits_zero(self):
        root = Path(self.tmp.name) / "clean"
        fake_proc(root, [(1, "systemd", "S", 0, 0, BTIME + 1),
                         (300, "python3", "S", 1, self.uid, BTIME + 2),
                         (301, "z3", "S", 300, self.uid, BTIME + 3)])
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = stall_check.main(["--proc", str(root), "--uid", str(self.uid),
                                   "--frozen", str(Path(self.tmp.name) / "none.pids")])
        self.assertEqual(rc, 0, buf.getvalue())
        self.assertIn("clean", buf.getvalue())

    def test_an_unreadable_proc_is_exit_two_not_clean(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = stall_check.main(["--proc", str(Path(self.tmp.name) / "missing")])
        self.assertEqual(rc, 2)
        self.assertNotIn("clean", buf.getvalue())

    def test_watch_reads_the_newest_file_as_the_heartbeat(self):
        d = Path(self.tmp.name) / "watch"
        (d / "sub").mkdir(parents=True)
        old = d / "sub" / "old.log"
        old.write_text("x")
        os.utime(old, (time.time() - 3600, time.time() - 3600))
        rc, out = self.run_main("--watch", str(d), "--stale", "27")
        self.assertIn("STALE", out)
        fresh = d / "fresh.log"
        fresh.write_text("y")
        rc, out = self.run_main("--watch", str(d), "--stale", "27")
        self.assertNotIn("STALE", out)
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        rc, out = self.run_main("--watch", str(empty))
        self.assertIn("STALE", out)
        self.assertIn("no file", out)


@unittest.skipUnless(sys.platform.startswith("linux"), "reads /proc")
class LiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.frozen = Path(self.tmp.name) / "frozen.pids"   # absent: nothing frozen

    def output(self) -> str:
        p = subprocess.run([sys.executable, str(HERE / "stall_check.py"), "--frozen", str(self.frozen)],
                           capture_output=True, text=True, timeout=60)
        return p.stdout

    def test_a_stopped_process_of_ours_is_named_until_it_is_resumed(self):
        child = subprocess.Popen(["sleep", "60"])
        try:
            os.kill(child.pid, signal.SIGSTOP)
            time.sleep(0.2)
            self.assertIn(f"STOPPED pid {child.pid} (sleep)", self.output())
            os.kill(child.pid, signal.SIGCONT)
            time.sleep(0.2)
            self.assertNotIn(f"pid {child.pid}", self.output())
        finally:
            child.kill()
            child.wait()

    def test_an_orphaned_prover_is_named(self):
        # A script named z3 (comm is the executed file's basename; a symlink
        # would not do, this box's coreutils is a multi-call binary that
        # dispatches on argv[0]) that keeps a sleep as its child, started by
        # a shell that exits at once, so the script is orphaned.
        script = Path(self.tmp.name) / "z3"
        script.write_text('#!/bin/sh\nsleep "$@"\n')
        script.chmod(0o755)
        marker = Path(self.tmp.name) / "pid"
        subprocess.run(["sh", "-c", '"$0" 60 & echo $! > "$1"; exit 0', str(script), str(marker)],
                       check=True, timeout=30)
        pid = int(marker.read_text().split()[0])
        try:
            time.sleep(0.3)
            stat = Path(f"/proc/{pid}/stat").read_text()
            comm, _state, ppid, _start = stall_check.parse_stat(stat)
            self.assertEqual(comm, "z3")
            parent_comm = stall_check.parse_stat(Path(f"/proc/{ppid}/stat").read_text())[0]
            if ppid != 1 and parent_comm not in stall_check.SUBREAPER_NAMES:
                self.skipTest(f"orphan reparented to {parent_comm} (pid {ppid}), neither pid 1 "
                              f"nor systemd; the check cannot see it here")
            self.assertIn(f"ORPHAN pid {pid} (z3)", self.output())
        finally:
            victims = [pid]
            for entry in os.listdir("/proc"):
                if entry.isdigit():
                    try:
                        if stall_check.parse_stat(Path(f"/proc/{entry}/stat").read_text())[2] == pid:
                            victims.append(int(entry))
                    except (OSError, IndexError, ValueError):
                        pass
            for victim in victims:
                try:
                    os.kill(victim, signal.SIGKILL)
                except OSError:
                    pass


if __name__ == "__main__":
    unittest.main()
