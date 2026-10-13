import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Nine findings of the review on the verifier package (run_tree, the group reaper, flake_check, the run lock) and one on kernel discovery, each reproduced before its fix.


def test_timeout_kills_other_process_groups_before_draining():
    import subprocess
    import sys
    import time
    import verifiers as v
    if not sys.platform.startswith('linux'):
        return
    code = "import os,subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(3)'], preexec_fn=os.setpgrp); time.sleep(30)"
    start = time.monotonic()
    try:
        v.run_tree([sys.executable, '-c', code], timeout=0.2)
    except subprocess.TimeoutExpired:
        pass
    else:
        raise AssertionError('expected TimeoutExpired')
    assert time.monotonic() - start < 1.5, 'timeout waited for the surviving descendant'


def test_normal_return_without_posix_killpg():
    import sys
    from types import SimpleNamespace
    from unittest.mock import patch
    import verifiers as v
    windows_os = SimpleNamespace(name='nt', path=SimpleNamespace(isdir=lambda p: False))
    with patch.object(v, 'os', windows_os), patch.object(v, '_LIVE_GROUPS', set()):
        result = v.run_tree([sys.executable, '-c', 'pass'], timeout=5)
    assert result.returncode == 0


def test_explicit_stdout_redirection():
    import subprocess
    import sys
    import verifiers as v
    result = v.run_tree(
        [sys.executable, '-c', "print('ok')"],
        timeout=5, capture_output=False, stdout=subprocess.PIPE, text=True)
    assert result.returncode == 0
    assert result.stdout == 'ok\n'


def test_stale_takeover_has_only_one_winner():
    import os
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import verifiers as v
    with tempfile.TemporaryDirectory() as directory:
        dead_pid = os.getpid() + 1000000
        (Path(directory) / '.run.lock').write_text(str(dead_pid) + '\n')
        entered = False
        acquisitions = []
        def probe(pid, sig):
            nonlocal entered
            if pid != dead_pid:
                return None
            if not entered:
                entered = True
                acquisitions.append(v.acquire_run_lock(directory))
            raise ProcessLookupError()
        try:
            with patch('os.kill', side_effect=probe):
                acquisitions.append(v.acquire_run_lock(directory))
            assert sum(callable(x) for x in acquisitions) == 1
        finally:
            for acquisition in acquisitions:
                if callable(acquisition):
                    acquisition()


def test_different_source_hashes_do_not_agree():
    import os
    from pathlib import Path
    from unittest.mock import patch
    import verifiers as v
    samples = iter([
        v.Result('test', 'v1', 'a' * 64, v.Outcome.VERIFIED, ok=True),
        v.Result('test', 'v1', 'b' * 64, v.Outcome.VERIFIED, ok=True),
    ])
    with patch.dict(os.environ, {'T_CELL_SERIAL': '1'}):
        _, agreed = v.flake_check(lambda path: next(samples), Path('changing.dfy'), n=2)
    assert not agreed, 'different source snapshots were counted as repeated verification'


def test_exit_reaper_kills_other_groups_in_session():
    import os
    import signal
    import subprocess
    import sys
    import time
    from pathlib import Path
    from unittest.mock import patch
    import verifiers as v
    if not sys.platform.startswith('linux'):
        return
    code = "import os,subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'], preexec_fn=os.setpgrp); print(p.pid,flush=True); time.sleep(30)"
    leader = subprocess.Popen([sys.executable, '-c', code], start_new_session=True, stdout=subprocess.PIPE, text=True)
    descendant = None
    try:
        descendant = int(leader.stdout.readline())
        def running():
            try:
                stat = Path('/proc/%d/stat' % descendant).read_text()
            except FileNotFoundError:
                return False
            return stat.rsplit(')', 1)[1].split()[0] not in ('Z', 'X')
        with patch.object(v, '_LIVE_GROUPS', {leader.pid}):
            v._kill_live_groups()
        leader.wait(timeout=3)
        deadline = time.monotonic() + 1
        while running() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not running(), 'same-session descendant survived the reaper'
    finally:
        if descendant is not None:
            try:
                os.kill(descendant, signal.SIGKILL)
            except ProcessLookupError:
                pass
        leader.kill()
        leader.wait(timeout=3)
        leader.stdout.close()


def test_forked_worker_does_not_kill_parent_prover():
    import os
    import signal
    import subprocess
    import sys
    from unittest.mock import patch
    import verifiers as v
    if not hasattr(os, 'fork'):
        return
    prover = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
    try:
        with patch.object(v, '_LIVE_GROUPS', {prover.pid}):
            worker = os.fork()
            if worker == 0:
                v._kill_live_groups_and_die(signal.SIGTERM, None)
                os._exit(0)
            os.waitpid(worker, 0)
            try:
                prover.wait(timeout=0.3)
            except subprocess.TimeoutExpired:
                pass
            assert prover.poll() is None, 'worker cleanup killed a parent-owned prover'
    finally:
        prover.kill()
        prover.wait(timeout=3)


def test_windows_liveness_resource_error_fails_closed():
    import ctypes
    import os
    import sys
    import tempfile
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import patch
    import verifiers as v
    kernel32 = SimpleNamespace(OpenProcess=lambda *args: 0, GetLastError=lambda: 8)
    with tempfile.TemporaryDirectory() as directory:
        lock = Path(directory) / '.run.lock'
        lock.write_text(str(os.getpid()) + '\n')
        with patch.object(sys, 'platform', 'win32'), patch.object(ctypes, 'windll', SimpleNamespace(kernel32=kernel32), create=True):
            result = v.acquire_run_lock(directory)
        try:
            assert isinstance(result, str), 'inconclusive liveness error stole an active lock'
        finally:
            if callable(result):
                result()


def test_invalid_lock_encoding_is_a_named_refusal():
    import tempfile
    from pathlib import Path
    import verifiers as v
    with tempfile.TemporaryDirectory() as directory:
        lock = Path(directory) / '.run.lock'
        lock.write_bytes(b'\xff')
        result = v.acquire_run_lock(directory)
        assert isinstance(result, str)
        assert '.run.lock' in result


def test_find_rejects_directory_override():
    import os
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from unittest.mock import patch
    from verifiers.discover import find

    with TemporaryDirectory() as tmp:
        installation = Path(tmp) / 'verus'
        installation.mkdir()
        with patch.dict(os.environ, {'T_VERUS_BIN': str(installation)}):
            assert find('T_VERUS_BIN', ['verus']) is None
