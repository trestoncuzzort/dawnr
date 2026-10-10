"""The Landlock backend (t/landlock_exec.py, T_SANDBOX=landlock): the same verdicts as bubblewrap, and every way out
that bubblewrap's namespaces hide is refused instead (docs.kernel.org/userspace-api/landlock.html; Codex CLI's
codex-rs/linux-sandbox/src/landlock.rs is the shape of the seccomp half)."""
import os
import signal
import stat
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import py_sandbox                                               # noqa: E402


@pytest.fixture(autouse=True)
def landlock(monkeypatch):
    monkeypatch.setenv("T_SANDBOX", "landlock")
    # Landlock is a Linux kernel feature. On macOS py_sandbox.backend() is seatbelt whatever T_SANDBOX says, and
    # seatbelt is available there, so the check below alone let every test here run against the wrong sandbox:
    # the macOS job of the tests workflow failed on all four from 2026-10-03 to 2026-10-05.
    if py_sandbox.backend() != "landlock":
        pytest.skip(f"the Landlock backend is Linux's; this platform's sandbox is {py_sandbox.backend()}")
    if not py_sandbox.available():
        pytest.skip(f"no Landlock sandbox here: {py_sandbox.why_unavailable()}")


def denied(body: str) -> list[str]:
    """Each line of `body` is one attempt, run as an assertion in the sandbox; the verdicts come back."""
    code = "import os, socket, resource, fcntl, signal, threading\ndef f(): pass\n"
    return py_sandbox.run_tests(code, [line.strip() for line in body.strip().splitlines()])["verdicts"]


def test_the_same_verdicts_as_bubblewrap_on_a_right_a_wrong_a_slow_and_a_broken_solution():
    assert py_sandbox.backend() == "landlock"
    assert py_sandbox.run_tests("def f(n):\n    return n * n\n", ["assert f(3) == 9"])["verdicts"] == ["pass"]
    assert py_sandbox.run_tests("def f(n):\n    return [n][n]\n", ["assert f(0) == 1", "assert f(1) == 1"])["verdicts"] \
        == ["fail", "error: IndexError"]
    assert py_sandbox.run_tests("def f(n):\n    while n:\n        pass\n", ["assert f(1) is None"], per_test=1)["verdicts"] \
        == ["timeout"]
    assert py_sandbox.run_tests("def f(:\n", ["assert f(1) == 1"])["status"] == "load-error"


def test_nothing_of_the_users_can_be_read_or_written(tmp_path):
    secret = Path.home() / ".cache" / "py-sandbox-landlock-secret"
    secret.parent.mkdir(exist_ok=True)
    secret.write_text("do not read me")
    outside = tmp_path / "outside"
    try:
        v = denied(f"""
            open({str(secret)!r}).read()
            os.listdir({str(Path.home())!r})
            open({str(outside)!r}, "w").write("x")
            open("/tmp/py-sandbox-landlock-escape", "w").write("x")
            open("/etc/passwd").read()
            os.chmod({str(secret)!r}, 0o777)
            open("here.txt", "w").write("x") and open("here.txt").read() == "x"
        """)
        assert v[:6] == ["error: PermissionError"] * 6
        assert v[6] == "pass"                                   # its own working folder is writable
        assert not outside.exists() and not Path("/tmp/py-sandbox-landlock-escape").exists()
        assert stat.S_IMODE(secret.stat().st_mode) != 0o777
    finally:
        secret.unlink()


def test_no_network_no_new_processes_and_no_threads():
    assert denied("""
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        socket.socket(socket.AF_UNIX)
        os.fork()
        threading.Thread(target=f).start()
        len(socket.socketpair()) == 2
    """) == ["error: PermissionError", "error: PermissionError", "error: PermissionError", "error: BlockingIOError",
             "error: RuntimeError", "pass"]


def test_other_processes_cannot_be_signalled_limited_or_read():
    other = subprocess.Popen(["sleep", "60"])
    try:
        v = denied(f"""
            os.kill({other.pid}, signal.SIGKILL)
            os.kill(-1, 0)
            os.kill(0, 0)
            resource.prlimit({other.pid}, resource.RLIMIT_AS, (1, 1))
            os.setpriority(os.PRIO_USER, os.getuid(), 19)
            fcntl.fcntl(os.open("/dev/null", os.O_RDONLY), fcntl.F_SETOWN, {other.pid})
            open("/proc/{other.pid}/environ").read()
            os.kill(os.getpid(), 0) is None
            resource.getrlimit(resource.RLIMIT_AS)[0] > 0
        """)
        assert v[:7] == ["error: PermissionError"] * 7 and v[7:] == ["pass", "pass"]
        assert other.poll() is None                             # still running
        assert py_sandbox.run_tests("import resource\ndef f(): pass\n", ["assert True"])["all_pass"]
    finally:
        other.send_signal(signal.SIGTERM)
        other.wait()


def test_a_kernel_without_landlock_runs_nothing(tmp_path):
    """Fail closed: the wrapper exits 125 and never execs the program when it cannot restrict itself."""
    marker = tmp_path / "ran"
    p = subprocess.run([sys.executable, "-I", "-S", "-c",
                        "import sys; sys.argv = ['x', sys.argv[1], '/usr/bin/touch', sys.argv[2]]; "
                        f"exec(open({str(py_sandbox.LANDLOCK_EXEC)!r}).read().replace('def abi_version', "
                        "'def abi_version(nr): return 0\\ndef _unused'))",
                        str(tmp_path), str(marker)], capture_output=True, text=True)
    assert p.returncode == 125 and "no Landlock" in p.stderr and not marker.exists()
