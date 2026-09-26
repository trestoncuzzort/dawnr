#!/usr/bin/env python3
"""t/test_run_tree_exit_paths.py -- verifiers.run_tree kills the prover's
whole process group on EVERY exit path, not only on a timeout (r12 blocker
A5, 2026-09-25).

run_tree started every prover in its own session and killed the group when
communicate() raised TimeoutExpired; on a normal return, on any other
exception and on KeyboardInterrupt its finally block only dropped the group
from _LIVE_GROUPS, so a grandchild the leader left behind (why3server's z3
under gnatprove, measured as 12 and then 26 orphaned z3 processes on the lab
that ran for a day) outlived the cell with nobody to kill it. CPython's
subprocess.run kills its child on every path ("except:  # Including
KeyboardInterrupt", Lib/subprocess.py); this applies the same shape to the
group.

Each case starts `sh -c 'sleep 300 & echo $! > pidfile; <leader action>'`
in run_tree and checks that the background sleep, the grandchild, is gone
within five seconds and that no group is left registered. The first three
cases fail on the old code; the timeout case passed before and must still.

Standard library only, Linux (reads /proc). unittest.
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

import verifiers                                              # noqa: E402

GRANDCHILD = 'sleep 300 </dev/null >/dev/null 2>&1 & echo $! > "$0"; '


def gone(pid: int) -> bool:
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return True
    return state in ("Z", "X")


def wait_gone(pid: int, seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if gone(pid):
            return True
        time.sleep(0.05)
    return gone(pid)


class _Raise:
    """A SIGALRM handler that raises `exc` in the main thread, so the
    exception surfaces inside proc.communicate() exactly as a driver's own
    failure or a user's ^C would."""

    def __init__(self, exc):
        self.exc = exc

    def __call__(self, signum, frame):
        raise self.exc


class RunTreeExitPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pidfile = Path(self.tmp.name) / "pid"
        self.old_alarm = signal.getsignal(signal.SIGALRM)

    def tearDown(self):
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self.old_alarm)
        pid = self.grandchild()
        if pid and not gone(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        self.tmp.cleanup()

    def grandchild(self) -> int | None:
        try:
            return int(self.pidfile.read_text().split()[0])
        except (OSError, ValueError, IndexError):
            return None

    def cmd(self, leader_action: str) -> list[str]:
        return ["sh", "-c", GRANDCHILD + leader_action, str(self.pidfile)]

    def check_dead(self):
        pid = self.grandchild()
        self.assertIsNotNone(pid, "the leader never wrote the grandchild's pid")
        self.assertTrue(wait_gone(pid), f"grandchild {pid} survived the cell")
        self.assertEqual(verifiers._LIVE_GROUPS, set())

    def test_normal_return_kills_the_stragglers(self):
        r = verifiers.run_tree(self.cmd("exit 3"), timeout=30)
        self.assertEqual(r.returncode, 3)
        self.check_dead()

    def test_an_exception_during_communicate_kills_the_group(self):
        signal.signal(signal.SIGALRM, _Raise(RuntimeError("driver failure")))
        signal.setitimer(signal.ITIMER_REAL, 0.5)
        with self.assertRaises(RuntimeError):
            verifiers.run_tree(self.cmd("sleep 300"), timeout=60)
        self.check_dead()

    def test_keyboard_interrupt_kills_the_group(self):
        signal.signal(signal.SIGALRM, _Raise(KeyboardInterrupt()))
        signal.setitimer(signal.ITIMER_REAL, 0.5)
        with self.assertRaises(KeyboardInterrupt):
            verifiers.run_tree(self.cmd("sleep 300"), timeout=60)
        self.check_dead()

    def test_timeout_still_kills_the_group(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            verifiers.run_tree(self.cmd("sleep 300"), timeout=0.5)
        self.check_dead()

    def test_output_and_return_code_are_unchanged(self):
        r = verifiers.run_tree(self.cmd("echo hi; exit 3"), timeout=30, text=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (3, "hi"))
        self.check_dead()


if __name__ == "__main__":
    unittest.main()
