"""Lab tests for where locallm's state goes.

Every test here points t/paths.py at temporary folders before asking it anything. A test
that let it find the real candidates would write into this checkout or into the operator's
own ~/.local/state, and the read-only case -- the borrowed machine, the stick mounted ro --
cannot be staged at all without being able to say where "beside the program" is.
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import paths

# A variable name nothing else in the tree reads, so a real T_WATCH in the environment of
# whoever runs the suite cannot decide the outcome of a test.
VAR = "T_TEST_PATHS_OVERRIDE"


class StateDirTests(unittest.TestCase):
    def setUp(self):
        self.program = Path(tempfile.mkdtemp(prefix="locallm-test-program-"))
        self.platform = Path(tempfile.mkdtemp(prefix="locallm-test-platform-"))
        self.real_program_dir, self.real_platform_state_dir = paths.program_dir, paths.platform_state_dir
        paths.program_dir = lambda: self.program
        paths.platform_state_dir = lambda: self.platform
        paths.state_root.cache_clear()
        os.environ.pop(VAR, None)

    def tearDown(self):
        paths.program_dir, paths.platform_state_dir = self.real_program_dir, self.real_platform_state_dir
        paths.state_root.cache_clear()
        os.environ.pop(VAR, None)
        for d in (self.program, self.platform):
            d.chmod(0o700)          # the read-only test takes the write bit off, and rmtree needs it back
            shutil.rmtree(d, ignore_errors=True)

    def test_the_environment_variable_wins_over_the_program_folder(self):
        want = self.platform / "elsewhere" / "events.jsonl"
        os.environ[VAR] = str(want)
        self.assertEqual(paths.state_path(VAR, "watch", "events.jsonl"), want)
        # and it wins early enough that nothing was created on the way to answering
        self.assertFalse((self.program / paths.PORTABLE).exists())

    def test_a_writable_program_folder_beats_the_platform_folder(self):
        self.assertEqual(paths.state_root(), self.program / paths.PORTABLE)
        self.assertEqual(list(self.platform.iterdir()), [])

    def test_a_read_only_program_folder_falls_through_rather_than_raising(self):
        if os.name != "posix":
            self.skipTest("the write bit is how a read-only stick is staged here")
        if os.geteuid() == 0:
            self.skipTest("root writes through the mode bits, so 0o500 stages nothing")
        self.program.chmod(0o500)                      # readable and listable, not writable
        paths.state_root.cache_clear()
        self.assertEqual(paths.state_root(), self.platform)
        self.assertFalse((self.program / paths.PORTABLE).exists())

    def test_the_returned_path_is_created_and_writable(self):
        d = paths.state_dir("watch")
        self.assertTrue(d.is_dir())
        (d / "events.jsonl").write_text('{"ev": "end"}\n', encoding="utf-8")
        self.assertEqual((d / "events.jsonl").read_text(encoding="utf-8"), '{"ev": "end"}\n')
        # the parent of a leaf is made too, which is what lab.py's EVENTS relies on
        self.assertTrue(paths.state_path(VAR, "watch", "events.jsonl").parent.is_dir())

    def test_the_write_probe_is_not_left_behind(self):
        # a stick must come away with nothing of ours on it, probe file included
        self.assertTrue(paths.writable(self.program))
        self.assertEqual([p.name for p in self.program.iterdir()], [])

    def test_a_base_variable_is_joined_when_absolute_and_ignored_when_not(self):
        base = self.platform / "cache"
        os.environ[VAR] = str(base)
        self.assertEqual(paths.state_path(VAR, "geometry", env_join=("t-lab", "geometry")),
                         base / "t-lab" / "geometry")
        # basedir-spec section 2: a relative path in one of these variables is invalid and ignored
        os.environ[VAR] = "relative/cache"
        fell_through = paths.state_path(VAR, "geometry", env_join=("t-lab", "geometry"))
        self.assertEqual(fell_through, self.program / paths.PORTABLE / "geometry")

    def test_the_linux_state_folder_follows_the_basedir_spec(self):
        if os.name == "nt" or sys.platform == "darwin":
            self.skipTest("XDG_STATE_HOME is the Linux branch of platform_state_dir")
        real = os.environ.get("XDG_STATE_HOME")
        try:
            os.environ["XDG_STATE_HOME"] = str(self.platform)
            self.assertEqual(self.real_platform_state_dir(), self.platform / paths.APP)
            os.environ["XDG_STATE_HOME"] = "state"
            self.assertEqual(self.real_platform_state_dir(), Path.home() / ".local" / "state" / paths.APP)
        finally:
            if real is None:
                os.environ.pop("XDG_STATE_HOME", None)
            else:
                os.environ["XDG_STATE_HOME"] = real
        # naming a folder is not making one: nothing above touched the filesystem
        self.assertFalse((self.platform / paths.APP).exists())


if __name__ == "__main__":
    unittest.main()
