#!/usr/bin/env python3
"""What `t/proc.py` has to get right, tested against real processes on this machine.

Four of these tests are behaviour -- a live child, a dead child, a tree that has to go, a pid that
was never there -- and they run on POSIX, which is where they can actually run. The fifth reads
`t/proc.py`'s own source and refuses to let the Windows branch call `os.kill` with a signal number,
because that is the bug the module exists to fix and it cannot be caught from here: the POSIX
`os.kill(pid, 0)` probe is correct, the same line on Windows terminates the process it asks about
(docs.python.org/3/library/os.html#os.kill), and nothing on this box would notice if someone copied
the working line into the branch that must not have it. A source test is the only guard available.

Nothing here signals a pid it did not create. pid 1 is *probed* -- as a non-root user that is the
one reliable EPERM on the machine, and EPERM has to read as alive
(stackoverflow.com/q/568271) -- but it is never passed to `stop_tree`, which would ask init to
exit if these tests were ever run as root.

Stdlib only, no corpus and no model: every process here is started by the test.
"""
from __future__ import annotations

import ast
import subprocess
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import proc  # noqa: E402

SLEEPER = "import time; time.sleep(60)"
# A parent that starts one child, says which pid it got, and then sleeps: `stop_tree` has to take
# both, and the grandchild is the half that a plain kill(pid) leaves holding the GPUs.
#
# The grandchild's own streams go to DEVNULL and the sleeps are a minute rather than the five that
# read better. Both are about what happens when this test FAILS, which was tried by breaking
# t/proc.py on purpose: the grandchild would otherwise inherit the pipe this test reads the pid
# from, so an orphan holds its write end, and `python3 -m unittest ... | tail` -- how the suite is
# run -- blocks on the pipe for the whole sleep instead of reporting the failure. A test that hangs
# the suite is worse than a test that fails it.
TREE = ("import subprocess, sys, time; "
        "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
        "print(c.pid, flush=True); time.sleep(60)")


def a_pid_that_is_gone() -> int:
    """A pid nothing can be using.

    Linux allocates pids strictly below `pid_max`, so `pid_max` itself is never live. Where that
    file is absent, a child is started and waited for, which frees its pid; a wrap-around could in
    principle hand it to someone else between the wait and the assert, and reading `pid_max` avoids
    even that.
    """
    try:
        return int(Path("/proc/sys/kernel/pid_max").read_text())
    except OSError:
        done = subprocess.Popen([sys.executable, "-c", "pass"])
        done.wait()
        return done.pid


class Alive(unittest.TestCase):
    def test_true_while_a_child_runs_and_false_once_it_is_gone(self):
        child = subprocess.Popen([sys.executable, "-c", SLEEPER])
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        self.assertTrue(proc.alive(child.pid), "a sleeping child of ours should read as alive")
        child.kill()
        child.wait()     # without the wait it is a zombie, and a zombie is still in the table
        self.assertFalse(proc.alive(child.pid), "a killed and reaped child should read as dead")

    def test_probing_repeatedly_does_not_harm_the_process(self):
        """The whole point: on Windows this exact call used to be a kill. 200 probes, still there."""
        child = subprocess.Popen([sys.executable, "-c", SLEEPER])
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        for _ in range(200):
            self.assertTrue(proc.alive(child.pid))
        self.assertIsNone(child.poll(), "the probe ended the process it was asked about")

    def test_false_for_a_pid_that_cannot_exist(self):
        self.assertFalse(proc.alive(a_pid_that_is_gone()))

    def test_false_for_pids_that_are_not_processes(self):
        # 0 is our own process group to kill(2) and a negative pid is a group; neither is a step.
        self.assertFalse(proc.alive(0))
        self.assertFalse(proc.alive(-1))

    @unittest.skipIf(proc.WINDOWS, "EPERM is the POSIX spelling of it")
    def test_a_pid_we_may_not_signal_is_alive(self):
        """Getting this backwards makes the window call a running job finished."""
        self.assertTrue(proc.alive(1), "pid 1 exists whether or not we are allowed to signal it")


class StopTree(unittest.TestCase):
    def start_tree(self):
        parent = subprocess.Popen([sys.executable, "-c", TREE], stdout=subprocess.PIPE, text=True,
                                  # what t/lab.py passes, and what makes the pid a group id
                                  start_new_session=not proc.WINDOWS)
        self.addCleanup(self.cleanup, parent)
        grandchild = int(parent.stdout.readline())
        self.assertTrue(proc.alive(parent.pid))
        self.assertTrue(proc.alive(grandchild))
        return parent, grandchild

    def cleanup(self, parent):
        if parent.poll() is None:
            parent.kill()
        parent.wait()
        parent.stdout.close()

    def test_stops_a_real_sleeping_child(self):
        child = subprocess.Popen([sys.executable, "-c", SLEEPER], start_new_session=not proc.WINDOWS)
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        self.assertTrue(proc.stop_tree(child.pid), "stop_tree said the child was still there")
        self.assertFalse(proc.alive(child.pid))

    def test_stops_the_children_too(self):
        parent, grandchild = self.start_tree()
        self.assertTrue(proc.stop_tree(parent.pid))
        self.assertFalse(proc.alive(parent.pid))
        # The grandchild is not our child, so we cannot reap it: it is left to whoever adopts it,
        # measured at 0.011 s worst of ten runs on this machine. Ten seconds is slack, not a claim.
        deadline = time.monotonic() + 10
        while proc.alive(grandchild) and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertFalse(proc.alive(grandchild),
                         f"pid {grandchild} outlived its parent; the tree was not stopped")

    def test_returns_without_raising_on_a_pid_that_is_already_gone(self):
        self.assertTrue(proc.stop_tree(a_pid_that_is_gone()))

    def test_returns_without_raising_on_a_pid_that_is_not_a_process(self):
        self.assertTrue(proc.stop_tree(0))
        self.assertTrue(proc.stop_tree(-1))


class WindowsBranchNeverSignals(unittest.TestCase):
    """Read t/proc.py and check where `os.kill` is allowed to appear.

    This is the test that outlives the memory of why. `os.kill(pid, 0)` is the right probe on POSIX
    and a `TerminateProcess` call on Windows, so the two branches cannot share it, and the mistake
    looks like a tidy-up when someone makes it.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = (HERE / "proc.py").read_text()
        cls.tree = ast.parse(cls.source)
        cls.owner = {}                        # every node -> the function it is written inside
        for node in ast.walk(cls.tree):
            holder = cls.owner.get(node)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                holder = node.name
            for child in ast.iter_child_nodes(node):
                cls.owner[child] = holder

    def signal_calls(self):
        """Every `os.kill`/`os.killpg` call, with the name of the function it sits in."""
        for node in ast.walk(self.tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("kill", "killpg")
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "os"):
                yield self.owner.get(node), node

    def test_every_signal_call_is_in_a_posix_helper(self):
        found = list(self.signal_calls())
        self.assertTrue(found, "no os.kill call at all -- this test has stopped testing anything")
        for where, node in found:
            self.assertIsNotNone(where, f"os.kill at module level, line {node.lineno}")
            self.assertTrue(where.endswith("_posix"),
                            f"os.{node.func.attr} in {where}() at line {node.lineno}: signalling "
                            f"belongs in a _posix helper, since on Windows os.kill terminates")

    def test_the_windows_helpers_exist_and_signal_nothing(self):
        names = {n.name for n in ast.walk(self.tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertLessEqual({"_alive_windows", "_stop_windows"}, names)
        for node in ast.walk(self.tree):
            if not (isinstance(node, ast.FunctionDef) and node.name.endswith("_windows")):
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Attribute) and inner.attr in ("kill", "killpg"):
                    self.fail(f"{node.name}() reaches for .{inner.attr} at line {inner.lineno}")
                # No signal number can reach a Windows call if no signal name is spelled there.
                if isinstance(inner, ast.Attribute) and isinstance(inner.value, ast.Name) \
                        and inner.value.id == "signal":
                    self.fail(f"{node.name}() uses signal.{inner.attr} at line {inner.lineno}; "
                              f"CTRL_BREAK_EVENT would need CREATE_NEW_PROCESS_GROUP, which the "
                              f"steps are not started with")


class _Stub:
    """A kernel32 entry point: callable, and willing to have argtypes/restype set on it."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        return self.result


class WindowsProbeReadings(unittest.TestCase):
    """Run the Windows branch on this Linux box with kernel32 stood in for.

    This is not a claim that it works on Windows -- only that the readings which decide a job's fate
    are wired the right way round: WAIT_TIMEOUT means running, WAIT_OBJECT_0 means exited,
    ERROR_ACCESS_DENIED means alive and ERROR_INVALID_PARAMETER means gone. An inverted comparison
    in any of those is invisible to every other test in this file, and the first two differ by one
    character.
    """

    def probe(self, handle, wait=0, last_error=0):
        import ctypes
        from unittest import mock
        stub = type("k32", (), {})()
        stub.OpenProcess = _Stub(handle)
        stub.WaitForSingleObject = _Stub(wait)
        stub.CloseHandle = _Stub(1)
        with mock.patch.object(ctypes, "WinDLL", create=True, new=lambda *a, **k: stub), \
             mock.patch.object(ctypes, "get_last_error", create=True, new=lambda: last_error):
            return proc._alive_windows(4321), stub

    def setUp(self):
        try:
            from ctypes import wintypes                     # noqa: F401
        except (ImportError, ValueError) as exc:            # not importable away from Windows
            self.skipTest(f"ctypes.wintypes unavailable here: {exc}")

    def test_wait_timeout_means_the_process_is_still_running(self):
        self.assertTrue(self.probe(handle=0x2c, wait=0x00000102)[0])

    def test_wait_object_0_means_it_has_exited(self):
        self.assertFalse(self.probe(handle=0x2c, wait=0x00000000)[0])

    def test_a_broken_wait_reads_as_alive(self):
        self.assertTrue(self.probe(handle=0x2c, wait=0xFFFFFFFF)[0], "WAIT_FAILED must not read dead")

    def test_access_denied_means_alive_and_invalid_parameter_means_gone(self):
        self.assertTrue(self.probe(handle=0, last_error=5)[0], "ERROR_ACCESS_DENIED: not ours, but there")
        self.assertFalse(self.probe(handle=0, last_error=87)[0], "ERROR_INVALID_PARAMETER: no such pid")
        self.assertTrue(self.probe(handle=0, last_error=0)[0], "psutil issue 1877: no error, still alive")

    def test_the_handle_asks_for_no_right_to_terminate(self):
        _answer, stub = self.probe(handle=0x2c, wait=0x00000102)
        access = stub.OpenProcess.calls[0][0]
        self.assertFalse(access & 0x0001, "PROCESS_TERMINATE in a probe's access mask")
        self.assertTrue(stub.CloseHandle.calls, "the handle was not closed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
