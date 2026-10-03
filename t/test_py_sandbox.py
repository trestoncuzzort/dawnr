"""Model-written Python runs only inside the sandbox (github.com/openai/human-eval execution.py is
the shape; bubblewrap is the isolation)."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import py_sandbox                                               # noqa: E402

pytestmark = pytest.mark.skipif(not py_sandbox.available(), reason="bubblewrap is not installed")
SQUARE = "def f(n):\n    return n * n\n"


def test_a_right_solution_passes_every_assertion():
    out = py_sandbox.run_tests(SQUARE, ["assert f(2) == 4", "assert f(3) == 9"])
    assert out == {"status": "ran", "verdicts": ["pass", "pass"], "all_pass": True}


def test_a_wrong_one_fails_and_an_exception_is_named():
    out = py_sandbox.run_tests("def f(n):\n    return [n][n]\n", ["assert f(0) == 1", "assert f(1) == 1"])
    assert out["verdicts"] == ["fail", "error: IndexError"] and out["all_pass"] is False


def test_an_endless_loop_is_one_timed_out_assertion_and_the_rest_still_run():
    code = "def f(n):\n    while n:\n        pass\n    return 0\n"
    out = py_sandbox.run_tests(code, ["assert f(1) == 0", "assert f(0) == 0"], per_test=1)
    assert out["verdicts"] == ["timeout", "pass"]


def test_code_that_does_not_load_is_reported_as_that():
    assert py_sandbox.run_tests("def f(:\n", ["assert f(1) == 1"])["status"] == "load-error"


def test_the_sandbox_has_no_home_no_network_and_no_new_processes():
    probe = Path.home() / "py-sandbox-probe-must-not-appear"
    code = f'''
import os, socket, subprocess
def wrote():
    try:
        open({str(probe)!r}, "w").write("x"); return True
    except OSError:
        return False
def read_home():
    try:
        return bool(os.listdir({str(Path.home())!r}))
    except OSError:
        return False
def net():
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=1); return True
    except OSError:
        return False
def spawned():
    try:
        subprocess.run(["/usr/bin/true"]); return True
    except (OSError, subprocess.SubprocessError):
        return False
'''
    out = py_sandbox.run_tests(code, ["assert not wrote()", "assert not read_home()", "assert not net()",
                                      "assert not spawned()"])
    assert out["verdicts"] == ["pass", "pass", "pass", "pass"], out
    assert not probe.exists()


def test_without_a_sandbox_nothing_is_run(monkeypatch):
    monkeypatch.setattr(py_sandbox, "available", lambda: False)
    with pytest.raises(RuntimeError):
        py_sandbox.run_tests(SQUARE, ["assert f(2) == 4"])


# -- Session: one sandboxed interpreter, many calls (t/spec_gate.py's agreement stage) -----------

SESSION_CODE = '''
def f(xs, k):
    if k == 13:
        raise ValueError("unlucky")
    if k == 99:
        while True:
            pass
    if k == 7:
        return {1, 2}
    if k == 5:
        print("noise without a newline", end="")
        return (1, "a", [True, None])
    return sorted(xs)[:k]
'''


def test_a_session_calls_the_function_and_values_cross_as_json():
    with py_sandbox.Session(SESSION_CODE, "f", per_call=2) as s:
        assert s.call([[3, 1, 2], 2]) == [1, 2]
        assert s.call([[3, 1, 2], 5]) == [1, "a", [True, None]]     # a tuple arrives as a list; prints are skipped
        assert s.restarts == 0


def test_a_session_names_an_exception_and_refuses_a_value_json_cannot_carry():
    with py_sandbox.Session(SESSION_CODE, "f", per_call=2) as s:
        with pytest.raises(py_sandbox.CallError, match="ValueError"):
            s.call([[1], 13])
        with pytest.raises(py_sandbox.Unrepresentable):
            s.call([[1], 7])
        assert s.call([[2, 1], 1]) == [1]                           # and it is still alive


def test_a_call_that_does_not_return_is_a_timeout_and_the_next_call_gets_a_fresh_interpreter():
    with py_sandbox.Session(SESSION_CODE, "f", per_call=1) as s:
        with pytest.raises(py_sandbox.CallTimeout):
            s.call([[1], 99])
        assert s.call([[2, 1], 1]) == [1]
        assert s.restarts == 1


def test_a_session_refuses_code_that_does_not_define_the_function():
    with pytest.raises(py_sandbox.LoadError):
        py_sandbox.Session("def g():\n    return 1\n", "f")
    with pytest.raises(py_sandbox.LoadError):
        py_sandbox.Session("f = 3\n", "f")


def test_a_session_cannot_read_the_home_directory():
    """A file in the real home folder is out of reach: bwrap mounts an empty /home (Linux), Seatbelt denies the
    read (macOS, where CI's runner showed listing /home raise PermissionError, 2026-10-02)."""
    import uuid
    secret = Path.home() / f".py-sandbox-probe-{uuid.uuid4().hex}"
    secret.write_text("not for the sandbox")
    try:
        probe = ("def f(path):\n    try:\n        return open(path).read()\n"
                 "    except OSError as e:\n        return type(e).__name__\n")
        with py_sandbox.Session(probe, "f") as s:
            got = s.call([str(secret)])
        assert got in ("FileNotFoundError", "PermissionError"), got
    finally:
        secret.unlink()


def test_macos_command_is_seatbelt_with_codex_policies_and_ours(tmp_path, monkeypatch):
    """On macOS the job runs under /usr/bin/sandbox-exec with Codex CLI's vendored base and read-only platform
    policies followed by ours. The construction is checked here; the other tests in this file run it for real on
    CI's macOS runner."""
    import sys as _sys
    monkeypatch.setattr(_sys, "platform", "darwin")
    cmd = py_sandbox._command(tmp_path)
    assert cmd[0] == "/usr/bin/sandbox-exec" and cmd[1] == "-p"
    profile = cmd[2]
    assert profile.lstrip().startswith(";") or "(version 1)" in profile
    assert "(deny default)" in profile and '(subpath (param "TMP"))' in profile
    assert "network-outbound (remote" not in profile and "network*" not in profile
    real = tmp_path.resolve()                          # Seatbelt matches real paths (/var is /private/var on macOS)
    assert f"-DJOB={real}" in cmd and f"-DTMP={real / 'tmp'}" in cmd
    assert cmd[-2:] == ["-I", str(real / "runner.py")]
    assert (tmp_path / "tmp").is_dir()


def test_runner_reads_its_own_folder(tmp_path):
    """The runner finds solution.py and asserts.json beside itself: /job under bwrap, the job folder elsewhere."""
    assert 'open("/job/' not in py_sandbox.RUNNER and 'open("/job/' not in py_sandbox.SESSION_RUNNER
    assert "os.path.join(JOB" in py_sandbox.RUNNER and "os.path.join(JOB" in py_sandbox.SESSION_RUNNER


def test_a_session_runs_in_a_session_of_its_own_so_it_cannot_reach_our_terminal():
    """TIOCSTI (CVE-2017-5226): a sandboxed process that shares our session can push keystrokes into the shell.
    bwrap's --new-session and, on macOS, start_new_session put it in its own session."""
    probe = "import os\ndef f():\n    return os.getsid(0)\n"
    with py_sandbox.Session(probe, "f") as s:
        assert s.call([]) != os.getsid(0)


def test_run_tests_gives_the_job_no_stdin_and_a_new_session(monkeypatch):
    seen = {}
    real = py_sandbox.subprocess.run

    def spy(cmd, **kw):
        seen.update(kw)
        return real(cmd, **kw)
    monkeypatch.setattr(py_sandbox.subprocess, "run", spy)
    py_sandbox.run_tests("def f(n):\n    return n\n", ["assert f(1) == 1"])
    assert seen["stdin"] is py_sandbox.subprocess.DEVNULL and seen["start_new_session"] is True


def test_the_macos_profile_denies_the_terminal_after_codex_s_rules():
    """Seatbelt takes the last matching rule, so our deny must come after every terminal rule Codex's files grant."""
    profile = py_sandbox.seatbelt_profile()
    ours = profile.index(py_sandbox.SEATBELT_OURS)
    deny = profile.index('(deny file-read* file-write* file-ioctl (literal "/dev/tty")')
    assert deny > ours > profile[:ours].rfind("/dev/ttys") > 0
