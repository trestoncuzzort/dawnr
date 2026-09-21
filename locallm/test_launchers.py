"""Do the three front doors open from wherever the folder happens to be?

WHAT IS TESTED HERE. A launcher has one job: start home.py from the folder the
launcher is in, on a computer nobody prepared, and say something readable when
it cannot. The failure that motivates this file is the double-click: on macOS
the Finder hands a .command a shell whose working directory is the user's home
folder, and on Linux a file manager does the same, so a launcher that runs
`python3 home.py` looks for the program in the wrong place and reports that it
does not exist. That bug cannot be caught by reading the text of the script, so
it is not tested by reading it: test_it_runs_home_py_from_its_own_folder copies
the tree into a temporary directory whose path contains a space, puts a decoy
home.py in the working directory, runs the real start-linux.sh with a stub
python on PATH that records its arguments, and checks which home.py was asked
for. A launcher that trusted the working directory would find the decoy.

The two failure paths are run as well, not grepped for: no Python at all, and a
Python whose tkinter is missing, which is the ordinary state of a stock python3
on Debian and Ubuntu (packages.debian.org/stable/python3-tk).

Nothing here imports torch, opens a window or needs a network. The stub python
is a four-line shell script, so these tests do not need a second real Python
either.

    python3 -m unittest test_launchers -v

RED WITNESS, each mutation applied to a copy of the launcher and the output
quoted:

    start-linux.sh: `"$PY" home.py "$@"` — the double-click bug itself
      FAIL test_it_runs_home_py_from_its_own_folder: Lists differ:
        ['/tmp/tmpht06c5fy/My USB Stick/locallm/home.py'] != ['home.py']
      FAIL test_the_space_in_the_path_survives_as_one_argument: ' ' not found
        in 'home.py'

    start-linux.sh: `here=$(pwd)` in place of the ${0%/*} resolution
      FAIL test_it_runs_home_py_from_its_own_folder: Lists differ:
        ['/tmp/tmp3sb7gbv9/My USB Stick/locallm/home.py'] !=
        ['/tmp/tmp3sb7gbv9/home.py'] — it started the decoy
      FAIL test_a_launcher_on_its_own_says_so: 1 != 0 — with the launcher's own
        home.py deleted it started anyway, off the working directory

    start-linux.sh: the tkinter check deleted
      FAIL test_the_tkinter_check_runs_before_the_window: [] is not true : no
        invocation asked for tkinter: [['-c', 'import sys; sys.exit(0 if
        sys.version_info >= (3, 10) else 1)'], ['/tmp/.../locallm/home.py']]
      FAIL test_a_missing_tkinter_names_the_package_and_waits: 1 != 0 — the
        program was started with no window to draw in
      FAIL test_every_launcher_checks_tkinter_before_starting: 'import tkinter'
        not found in ... : start-linux.sh starts the window without checking Tk

    start-linux.sh: wait_for_reader deleted from the no-Python path
      FAIL test_no_python_at_all_explains_where_to_get_it: 'Press Enter' not
        found in '\\n  No Python 3.10 or newer was found on this computer...' —
        on a double-click that window is gone before the message is read

    start-windows.bat: %CD%\\ in place of %~dp0
      FAIL test_the_bat_finds_its_own_folder_with_dp0: '%~dp0' not found
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

LINUX = "start-linux.sh"
MACOS = "start-macos.command"
WINDOWS = "start-windows.bat"
SHELL_LAUNCHERS = (LINUX, MACOS)
LAUNCHERS = (LINUX, MACOS, WINDOWS)

# The stub that stands in for Python. One line per argument rather than one
# line per invocation, because a path that lost its quoting arrives as two
# arguments and that has to be visible: joined back together with spaces it
# would read exactly like the path that survived.
STUB_PYTHON = """#!/bin/sh
{ echo RUN; for a in "$@"; do echo "ARG $a"; done; } >> "$LAUNCHER_RECORD"
case "$*" in
    *"import tkinter"*) exit "${LAUNCHER_TK_STATUS:-0}" ;;
esac
exit 0
"""

# Syntax the launchers may not use. macOS has shipped bash 3.2 since 2007 --
# the licence on bash 4 is why -- so a bash-4 spelling that works here is a
# launcher that fails on half the computers it is aimed at. `[[` is in the
# list because both scripts declare #!/bin/sh, and /bin/sh is dash on Debian
# and Ubuntu, which does not have it.
TOO_NEW = (
    (r"\bmapfile\b", "mapfile arrived in bash 4"),
    (r"\breadarray\b", "readarray arrived in bash 4"),
    (r"\bcoproc\b", "coproc arrived in bash 4"),
    (r"\b(declare|typeset|local)\s+-A\b", "associative arrays arrived in bash 4"),
    (r"\$\{[A-Za-z_][A-Za-z0-9_]*(\^\^|,,)", "case conversion arrived in bash 4"),
    (r"&>>", "the &>> redirection arrived in bash 4"),
    (r";;&", "the ;;& case terminator arrived in bash 4"),
    (r"\[\[\s+-v\s", "[[ -v ]] arrived in bash 4.2"),
    (r"\$\{[A-Za-z_][A-Za-z0-9_]*\[-[0-9]", "negative array indices arrived in bash 4.3"),
    (r"\bglobstar\b", "globstar arrived in bash 4"),
    (r"\[\[", "[[ is a bash word and these scripts run under /bin/sh"),
)


def read(name: str) -> str:
    return (HERE / name).read_text(encoding="utf-8")


def invocations(record: Path) -> list[list[str]]:
    """Every call the stub python saw, as the argument lists it really got."""
    calls: list[list[str]] = []
    for line in record.read_text(encoding="utf-8").splitlines():
        if line == "RUN":
            calls.append([])
        elif line.startswith("ARG "):
            calls[-1].append(line[4:])
    return calls


class Stick:
    """A copy of the folder on a path with a space in it, and a stub python.

    The space is not decoration. A USB stick mounts at /Volumes/My Drive on a
    Mac and /media/you/My Drive on Linux, and an unquoted path breaks there and
    nowhere else, which is why the bug reaches strangers and not authors.
    """

    def __init__(self, tmp: str) -> None:
        self.root = Path(tmp)
        self.folder = self.root / "My USB Stick" / "locallm"
        self.folder.mkdir(parents=True)
        for name in SHELL_LAUNCHERS:
            shutil.copy2(HERE / name, self.folder / name)
            (self.folder / name).chmod(0o755)
        (self.folder / "home.py").write_text(
            "# the real one, next to the launcher\n", encoding="utf-8")

        # The decoy. A launcher that trusts the working directory finds this
        # one and starts, so the bug would otherwise look like success.
        (self.root / "home.py").write_text(
            "# the wrong one, in the working directory\n", encoding="utf-8")

        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.record = self.root / "record.txt"
        self.record.write_text("", encoding="utf-8")

    def with_python(self) -> "Stick":
        for name in ("python3", "python"):
            (self.bin / name).write_text(STUB_PYTHON, encoding="utf-8")
            (self.bin / name).chmod(0o755)
        return self

    def run(self, name: str = LINUX, *, tk_status: str = "0",
            path: str | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PATH"] = str(self.bin) if path is None else path
        env["LAUNCHER_RECORD"] = str(self.record)
        env["LAUNCHER_TK_STATUS"] = tk_status
        return subprocess.run(
            [str(self.folder / name)],
            # Standing anywhere but the folder, which is the whole point.
            cwd=str(self.root),
            env=env,
            # A launcher that waits for a keypress must not wait forever when
            # there is nobody there: read returns at once on a closed input.
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=60)


class TestItStarts(unittest.TestCase):
    def test_it_runs_home_py_from_its_own_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            stick = Stick(tmp).with_python()
            done = stick.run()
            self.assertEqual(0, done.returncode, done.stdout)
            calls = invocations(stick.record)
            self.assertTrue(calls, "the launcher never started a python")
            self.assertEqual([str(stick.folder / "home.py")], calls[-1],
                             "one argument, the home.py beside the launcher")
            self.assertNotIn(str(stick.root / "home.py"),
                             [arg for call in calls for arg in call])

    def test_the_space_in_the_path_survives_as_one_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            stick = Stick(tmp).with_python()
            stick.run()
            last = invocations(stick.record)[-1]
            self.assertEqual(1, len(last), f"quoting was lost: {last}")
            self.assertIn(" ", last[0], "the test path has no space in it")

    def test_the_tkinter_check_runs_before_the_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            stick = Stick(tmp).with_python()
            stick.run()
            calls = invocations(stick.record)
            asked = [i for i, c in enumerate(calls)
                     if any("import tkinter" in arg for arg in c)]
            self.assertTrue(asked, f"no invocation asked for tkinter: {calls}")
            self.assertLess(asked[0], len(calls) - 1,
                            "the check has to come before the program starts")

    def test_the_macos_launcher_starts_the_same_way(self):
        # Same body, different file: the .command is the one a stranger
        # double-clicks, so it cannot be the one that was never run.
        with tempfile.TemporaryDirectory() as tmp:
            stick = Stick(tmp).with_python()
            done = stick.run(MACOS)
            self.assertEqual(0, done.returncode, done.stdout)
            self.assertEqual([str(stick.folder / "home.py")],
                             invocations(stick.record)[-1])


class TestItExplainsItself(unittest.TestCase):
    def test_no_python_at_all_explains_where_to_get_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            stick = Stick(tmp)  # no stub python written
            done = stick.run(path=str(stick.bin))
            self.assertEqual(1, done.returncode, done.stdout)
            self.assertIn("python.org", done.stdout)
            self.assertIn("3.10", done.stdout)
            # Without this line the window closes on the message.
            self.assertIn("Press Enter", done.stdout)

    def test_a_missing_tkinter_names_the_package_and_waits(self):
        with tempfile.TemporaryDirectory() as tmp:
            stick = Stick(tmp).with_python()
            done = stick.run(tk_status="1")
            self.assertEqual(1, done.returncode, done.stdout)
            self.assertIn("python3-tk", done.stdout)
            self.assertIn("python3-tkinter", done.stdout)
            self.assertIn("Press Enter", done.stdout)
            started = [c for c in invocations(stick.record)
                       if any(arg.endswith("home.py") for arg in c)]
            self.assertEqual([], started,
                             "the program was started with no window to draw in")

    def test_a_missing_tkinter_on_macos_names_the_homebrew_formula(self):
        with tempfile.TemporaryDirectory() as tmp:
            stick = Stick(tmp).with_python()
            done = stick.run(MACOS, tk_status="1")
            self.assertEqual(1, done.returncode, done.stdout)
            self.assertIn("python-tk", done.stdout)
            self.assertIn("Press Enter", done.stdout)

    def test_a_launcher_on_its_own_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            stick = Stick(tmp).with_python()
            (stick.folder / "home.py").unlink()
            done = stick.run()
            self.assertEqual(1, done.returncode, done.stdout)
            self.assertIn(str(stick.folder), done.stdout,
                          "the message has to name the folder it looked in")
            self.assertIn("Press Enter", done.stdout)


class TestTheFilesThemselves(unittest.TestCase):
    def test_each_launcher_exists_and_is_not_empty(self):
        for name in LAUNCHERS:
            path = HERE / name
            self.assertTrue(path.is_file(), f"{name} is missing")
            self.assertGreater(path.stat().st_size, 0, f"{name} is empty")

    def test_the_shell_scripts_parse(self):
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("no bash on this machine")
        for name in SHELL_LAUNCHERS:
            done = subprocess.run([bash, "-n", str(HERE / name)],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True)
            self.assertEqual(0, done.returncode, f"{name}: {done.stdout}")

    def test_the_shell_scripts_parse_as_plain_sh_too(self):
        # They say #!/bin/sh, so the claim to check is the one they make.
        for name in SHELL_LAUNCHERS:
            done = subprocess.run(["/bin/sh", "-n", str(HERE / name)],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True)
            self.assertEqual(0, done.returncode, f"{name}: {done.stdout}")

    def test_the_shebang_is_posix_sh(self):
        for name in SHELL_LAUNCHERS:
            self.assertEqual("#!/bin/sh", read(name).splitlines()[0])

    def test_the_posix_launchers_are_executable(self):
        # The Finder refuses to run a .command without this bit, and git
        # carries the executable bit and nothing else about a file's mode.
        for name in SHELL_LAUNCHERS:
            self.assertTrue(os.access(HERE / name, os.X_OK),
                            f"{name} is not executable: chmod +x it")

    def test_no_launcher_uses_syntax_older_shells_lack(self):
        for name in SHELL_LAUNCHERS:
            text = read(name)
            for pattern, why in TOO_NEW:
                self.assertIsNone(re.search(pattern, text),
                                  f"{name}: {why}")

    def test_the_bat_finds_its_own_folder_with_dp0(self):
        self.assertIn("%~dp0", read(WINDOWS))

    def test_every_launcher_checks_tkinter_before_starting(self):
        for name in LAUNCHERS:
            self.assertIn("import tkinter", read(name),
                          f"{name} starts the window without checking Tk")

    def test_every_launcher_waits_before_closing(self):
        for name in SHELL_LAUNCHERS:
            self.assertIn("Press Enter", read(name))
        self.assertIn("pause", read(WINDOWS))

    def test_no_launcher_carries_an_absolute_home_path(self):
        # The release must work from wherever it is unpacked, and a path out of
        # the machine that built it is also a name that does not belong in a
        # public folder.
        for name in LAUNCHERS:
            self.assertNotIn("/home/", read(name), f"{name} names a home folder")

    def test_the_mac_launcher_says_what_to_do_about_gatekeeper(self):
        # A downloaded script is unsigned, so macOS refuses it once. Somebody
        # reading the file before running it should find the answer in it.
        text = read(MACOS)
        self.assertIn("Open Anyway", text)
        self.assertIn("support.apple.com", text)


if __name__ == "__main__":
    unittest.main()
