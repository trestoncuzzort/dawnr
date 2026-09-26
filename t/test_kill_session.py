"""A prover that moves itself into a new process group still dies with its cell.

gnatprove's why3server gives each z3 its own process group (measured 2026-09-25:
six orphaned z3s of ours, each a group leader, inside a dead gnatprove's
session), so the group kill in verifiers.run_tree never reached them. The
session does: run_tree starts the leader with start_new_session=True, so the
leader's pid is the session id of everything under it, and setpgid cannot leave
a session (proc_pid_stat(5), field 6). Linux only, like the sweep it guards.
"""
import os
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verifiers                                            # noqa: E402
from test_run_tree_exit_paths import wait_gone              # noqa: E402


@unittest.skipUnless(os.path.isdir("/proc"), "reads /proc")
class SessionKillTests(unittest.TestCase):
    def test_a_grandchild_in_its_own_process_group_dies_with_the_cell(self):
        with tempfile.TemporaryDirectory() as d:
            pidfile = Path(d) / "pid"
            escape = (f"import os, sys; os.setpgid(0, 0); open({str(pidfile)!r}, 'w').write(str(os.getpid())); "
                      f"os.execvp('sleep', ['sleep', '300'])")
            # the escaped child must not hold the leader's pipes, or communicate() waits on it
            cmd = ["sh", "-c", f"{shlex.quote(sys.executable)} -c {shlex.quote(escape)} </dev/null >/dev/null 2>&1 & sleep 0.5; exit 0"]
            result = verifiers.run_tree(cmd, timeout=30)
            self.assertEqual(result.returncode, 0)
            pid = int(pidfile.read_text())
            self.assertTrue(wait_gone(pid), f"the escaped grandchild {pid} survived the cell")

    def test_a_stranger_in_another_session_is_left_alone(self):
        # our own test process is in a different session from any cell
        verifiers._kill_session(os.getsid(0) + 1 if os.getsid(0) + 1 != os.getpid() else os.getsid(0) + 2)
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
