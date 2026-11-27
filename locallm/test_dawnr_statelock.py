"""dawnr_agent/statelock.py: the lock two dawnr sessions take turns on before they append to or rewrite the state
folder's shared files. Standard library only, so that it runs in the standard-library job on Windows (the msvcrt
branch of the lock) as well as on Linux and macOS (the fcntl branch). The module is loaded from its file, not through
the dawnr_agent package, which imports more than the lock needs. What cannot apply on a platform is skipped, and
says why."""
import errno
import importlib.util
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
STATELOCK = HERE / "dawnr_agent" / "statelock.py"


def load():
    spec = importlib.util.spec_from_file_location("statelock_under_test", STATELOCK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


statelock = load()

# a process that takes the lock, says so, and lets go when its input has a line (or after `hold` seconds)
HOLDER = r'''
import importlib.util, sys, time
spec = importlib.util.spec_from_file_location("statelock_under_test", sys.argv[1])
lock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lock)
with lock.state_lock(sys.argv[2]):
    print("held", flush=True)
    if len(sys.argv) > 3:
        time.sleep(float(sys.argv[3]))
    else:
        sys.stdin.readline()
    gone = time.time()
print("released", gone, flush=True)
'''


class StateLock(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="dawnr-statelock-"))
        self.state = self.base / "state"

    def tearDown(self):
        # everything is under this test's own folder: its files and folders are taken apart here
        for at, dirs, files in os.walk(self.base, topdown=False):
            for name in files:
                try:
                    os.unlink(os.path.join(at, name))
                except OSError:
                    pass
            for name in dirs:
                path = os.path.join(at, name)
                try:
                    os.rmdir(path) if not os.path.islink(path) else os.unlink(path)
                except OSError:
                    pass
        try:
            os.rmdir(self.base)
        except OSError:
            pass

    def _holder(self, *more):
        proc = subprocess.Popen([sys.executable, "-c", HOLDER, str(STATELOCK), str(self.state), *map(str, more)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self._end, proc)
        self.assertEqual(proc.stdout.readline().strip(), "held", "the holder did not take the lock")
        return proc

    @staticmethod
    def _end(proc):
        if proc.poll() is None:
            proc.kill()
        proc.communicate()

    def _let_go(self, proc):
        proc.stdin.write("\n")
        proc.stdin.flush()
        out, err = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0, err)
        return out

    def test_each_platform_uses_its_own_lock_call(self):
        self.assertEqual(statelock.fcntl is None, os.name == "nt")
        self.assertEqual(statelock.msvcrt is None, os.name != "nt")

    def test_the_lock_is_taken_and_let_go_and_the_file_it_leaves_is_empty(self):
        with statelock.state_lock(self.state):
            self.assertTrue((self.state / statelock.LOCK_NAME).is_file())     # the state folder is made if it is not there
        with statelock.state_lock(self.state):                                # and the same process can take it again
            pass
        self.assertEqual((self.state / statelock.LOCK_NAME).read_bytes(), b"")
        self.assertEqual([p.name for p in self.state.iterdir()], [statelock.LOCK_NAME])

    @unittest.skipIf(os.name == "nt", "Windows has no owner-only file mode to look at")
    def test_the_lock_file_is_created_for_its_owner_only(self):
        with statelock.state_lock(self.state):
            pass
        self.assertEqual((self.state / statelock.LOCK_NAME).stat().st_mode & 0o077, 0)

    def test_another_process_cannot_take_the_lock_while_it_is_held_and_can_when_it_is_let_go(self):
        holder = self._holder()
        with mock.patch.object(statelock, "WAIT", 0.3):
            with self.assertRaises(OSError):
                with statelock.state_lock(self.state):
                    self.fail("took the lock while another process held it")
        out = self._let_go(holder)
        self.assertIn("released", out)
        with statelock.state_lock(self.state, wait=10):
            pass

    def test_a_second_holder_waits_for_the_first_and_then_gets_it(self):
        holder = self._holder(1.5)                      # lets go after a second and a half of its own accord
        started = time.time()
        with statelock.state_lock(self.state, wait=60):
            got = time.time()
        out, err = holder.communicate(timeout=60)
        self.assertEqual(holder.returncode, 0, err)
        released = float(out.split("released")[1])
        self.assertGreaterEqual(got, released - 0.05, "the second holder had the lock before the first let go")
        self.assertGreater(got - started, 0.5, "the second holder did not wait")

    def test_a_wait_that_runs_out_is_a_timeout_after_the_time_given_and_the_block_does_not_run(self):
        holder = self._holder()
        ran = []
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            with statelock.state_lock(self.state, wait=0.4):
                ran.append(1)
        self.assertGreaterEqual(time.monotonic() - started, 0.35)
        self.assertEqual(ran, [])
        self.assertTrue(issubclass(TimeoutError, OSError))      # what the plan log and the journal already catch
        self._let_go(holder)

    def test_the_lock_is_let_go_when_what_runs_under_it_raises(self):
        with self.assertRaises(ZeroDivisionError):
            with statelock.state_lock(self.state):
                1 / 0
        with statelock.state_lock(self.state, wait=0.3):                      # at once, in this process
            pass
        holder = self._holder()                                               # and in another
        self._let_go(holder)

    def test_a_link_planted_at_the_lock_files_name_is_refused_and_not_followed(self):
        self.state.mkdir()
        victim = self.base / "victim.txt"
        victim.write_text("somebody's own file\n")
        lock = self.state / statelock.LOCK_NAME
        try:
            lock.symlink_to(victim)
        except (OSError, NotImplementedError) as e:
            self.skipTest(f"links cannot be made here: {e}")
        with self.assertRaises(OSError):
            with statelock.state_lock(self.state):
                self.fail("followed the link")
        self.assertEqual(victim.read_text(), "somebody's own file\n")
        os.unlink(lock)
        lock.symlink_to(self.base / "not-there-yet")                          # a link to nothing: nothing made through it
        with self.assertRaises(OSError):
            with statelock.state_lock(self.state):
                self.fail("followed the link")
        self.assertFalse((self.base / "not-there-yet").exists())

    def test_a_second_hard_link_to_another_file_is_refused_and_the_file_is_untouched(self):
        self.state.mkdir()
        theirs = self.base / "theirs.txt"
        theirs.write_text("theirs\n")
        try:
            os.link(theirs, self.state / statelock.LOCK_NAME)
        except (OSError, NotImplementedError) as e:
            self.skipTest(f"hard links cannot be made here: {e}")
        with self.assertRaises(OSError):
            with statelock.state_lock(self.state):
                self.fail("took a lock on a file that has another name")
        self.assertEqual(theirs.read_text(), "theirs\n")

    def test_a_folder_at_the_lock_files_name_is_refused(self):
        (self.state / statelock.LOCK_NAME).mkdir(parents=True)
        with self.assertRaises(OSError):
            with statelock.state_lock(self.state):
                self.fail("took a lock on a folder")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "this system has no named pipes")
    def test_a_named_pipe_at_the_lock_files_name_is_refused_and_not_waited_for(self):
        self.state.mkdir()
        os.mkfifo(self.state / statelock.LOCK_NAME)
        started = time.monotonic()
        with self.assertRaises(OSError):
            with statelock.state_lock(self.state):
                self.fail("took a lock on a pipe")
        self.assertLess(time.monotonic() - started, 5)

    @unittest.skipUnless(os.name == "nt", "a junction is a Windows kind of link")
    def test_a_junction_at_the_lock_files_name_is_refused(self):
        self.state.mkdir()
        target = self.base / "elsewhere"
        target.mkdir()
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(self.state / statelock.LOCK_NAME), str(target)],
                              capture_output=True, text=True)
        if made.returncode != 0:
            self.skipTest(f"a junction could not be made here: {made.stdout} {made.stderr}")
        with self.assertRaises(OSError):
            with statelock.state_lock(self.state):
                self.fail("followed the junction")
        self.assertEqual(os.listdir(target), [])

    def test_an_unexpected_error_from_the_lock_call_is_raised_and_not_waited_out(self):
        call = "flock" if statelock.fcntl is not None else "locking"
        module = statelock.fcntl if statelock.fcntl is not None else statelock.msvcrt
        with mock.patch.object(module, call, side_effect=OSError(errno.ENOLCK, "no locks left")):
            started = time.monotonic()
            with self.assertRaises(OSError) as raised:
                with statelock.state_lock(self.state, wait=30):
                    self.fail("ran without a lock")
        self.assertEqual(raised.exception.errno, errno.ENOLCK)
        self.assertLess(time.monotonic() - started, 5)


if __name__ == "__main__":
    unittest.main()
