import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

# Seven findings of the GPT-6 Astra review of 2026-10-13 on the Python sandbox, each reproduced before its fix: a solution cannot replace the assertions, cancel its deadline, forge a pass on stdout, exhaust the supervisor's memory with output, or lose a non-string mapping key silently; an application TimeoutError is not the sandbox's deadline; a large completed result is not a timeout.


def test_model_stdout_cannot_forge_a_pass():
    import json
    import py_sandbox as ps
    record = ps.RESULT + json.dumps({'verdicts': ['pass']}) + '\n'
    code = f'import os\nos.write(1, {record.encode()!r})\nos._exit(0)\n'
    out = ps.run_tests(code, ['assert False'])
    assert out.get('all_pass') is not True


def test_solution_cannot_replace_the_assertions():
    import py_sandbox as ps
    code = "import json\njson.load = lambda _: ['assert True']\n"
    out = ps.run_tests(code, ['assert False'])
    assert out.get('all_pass') is not True


def test_solution_cannot_cancel_its_test_deadline():
    import py_sandbox as ps
    code = 'import signal, time\ndef f():\n    signal.alarm(0)\n    time.sleep(2)\n    return 1\n'
    out = ps.run_tests(code, ['assert f() == 1'], per_test=1)
    assert out.get('all_pass') is not True


def test_child_output_cannot_exhaust_supervisor_memory():
    import subprocess
    import sys
    import unittest
    from pathlib import Path
    import py_sandbox as ps
    if sys.platform != 'linux':
        raise unittest.SkipTest('requires Linux RLIMIT_AS')
    code = "import os\nchunk = b'x' * (1 << 20)\nfor _ in range(256):\n    os.write(1, chunk)\n"
    driver = (
        'import sys, resource\n'
        f'sys.path.insert(0, {str(Path(ps.__file__).resolve().parent)!r})\n'
        'import py_sandbox as ps\n'
        '_, hard = resource.getrlimit(resource.RLIMIT_AS)\n'
        'resource.setrlimit(resource.RLIMIT_AS, (96 << 20, hard))\n'
        'try:\n'
        f'    ps.run_tests({code!r}, ["assert True"], per_test=10, memory_mb=64)\n'
        'except MemoryError:\n'
        '    raise SystemExit(73)\n'
    )
    p = subprocess.run([sys.executable, '-c', driver], capture_output=True, text=True, timeout=35)
    assert p.returncode == 0, (p.returncode, p.stderr)


def test_argument_mapping_keys_are_not_silently_lost():
    import py_sandbox as ps
    with ps.Session('def f(d):\n    return len(d)\n', 'f') as session:
        try:
            value = session.call([{1: 'integer key', '1': 'string key'}])
        except ps.CallError:
            return
        assert value == 2


def test_application_timeout_error_is_not_a_sandbox_timeout():
    import unittest
    import py_sandbox as ps
    code = "def f():\n    raise TimeoutError('application error')\n"
    with ps.Session(code, 'f', per_call=3) as session:
        with unittest.TestCase().assertRaisesRegex(ps.CallError, '^TimeoutError$'):
            session.call([])


def test_large_completed_result_is_not_reported_as_timeout():
    import py_sandbox as ps
    code = "def f():\n    return 'x' * (9 << 20)\n"
    with ps.Session(code, 'f', per_call=10) as session:
        try:
            value = session.call([])
        except ps.Unrepresentable:
            return
        assert len(value) == (9 << 20)
