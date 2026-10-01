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
    probe = "import os\ndef f():\n    return sorted(os.listdir('/home'))\n"
    with py_sandbox.Session(probe, "f") as s:
        assert s.call([]) == []
