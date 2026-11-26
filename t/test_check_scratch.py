"""A check killed with SIGKILL leaves its private copy in the temporary folder; the next check removes it, and only it.

Each kill test runs a real check in a child process, SIGKILLs it, then runs a second check in another child and looks
at the temporary folder (the parent process never imports the code under test for those, so the red on the old bytes
is the leftover itself). The safety tests plant what a sweep must not remove: a live owner's folder, a folder held by
a live lock, a link to a folder with files, a name off the pattern, a folder outside the scratch parent."""
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

PARENT_NAME = f"dawnr-checks-{os.geteuid()}"


@pytest.fixture
def tmp(tmp_path, monkeypatch):
    folder = tmp_path / "tmp"
    folder.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(folder))
    monkeypatch.setenv("TMPDIR", str(folder))
    return folder


def _env(tmp):
    env = dict(os.environ, TMPDIR=str(tmp), PYTHONDONTWRITEBYTECODE="1")
    env["PYTHONPATH"] = os.pathsep.join([str(HERE), str(HERE.parent)])
    return env


def _everything(tmp):
    """Every path under the temporary folder, relative, files and folders (links not followed)."""
    out = []
    for root, dirs, files in os.walk(tmp):
        for n in dirs + files:
            out.append(os.path.relpath(os.path.join(root, n), tmp))
    return sorted(out)


def _spawn(tmp, code):
    p = subprocess.Popen([sys.executable, "-c", code], env=_env(tmp), stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "ready"
    return p


def _run(tmp, code):
    r = subprocess.run([sys.executable, "-c", code], env=_env(tmp), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r


LIFTER_HOLD = """
import sys, time
import lifter
with lifter._scratch_dfy(None, "s", "m") as p:
    p.write_text("method M() {}", encoding="utf-8")
    print("ready", flush=True)
    time.sleep(120)
"""
LIFTER_QUICK = """
import lifter
with lifter._scratch_dfy(None, "s", "m") as p:
    p.write_text("method M() {}", encoding="utf-8")
"""
DAFNY_HOLD = """
import subprocess, sys, time
from pathlib import Path
from unittest.mock import patch
import t.verifiers.dafny as d
src = Path(sys.argv[0] if False else "SRC")
def kernel(argv, **kw):
    print("ready", flush=True)
    time.sleep(120)
with patch.object(d, "DAFNY", "dafny"), patch.object(d, "_solver_args", return_value=[]), \\
        patch.object(d, "version", return_value="dafny test"), patch.object(d, "run_tree", side_effect=kernel):
    d.verify(src)
"""
DAFNY_QUICK = DAFNY_HOLD.replace("    print(\"ready\", flush=True)\n    time.sleep(120)\n", "    return subprocess.CompletedProcess(argv, 0, 'Dafny program verifier finished with 1 verified, 0 errors\\n', '')\n")


def _kill(p):
    p.send_signal(signal.SIGKILL)
    p.wait()


def test_killed_lifter_check_leaves_nothing_after_the_next_check(tmp):
    p = _spawn(tmp, LIFTER_HOLD)
    assert any(n.endswith(".dfy") for n in _everything(tmp))                 # the copy exists while the check runs
    _kill(p)
    assert any(n.endswith(".dfy") for n in _everything(tmp))                 # SIGKILL ran no cleanup
    _run(tmp, LIFTER_QUICK)
    assert _everything(tmp) in ([], [PARENT_NAME])


def test_killed_dafny_check_leaves_nothing_after_the_next_check(tmp, tmp_path):
    src = tmp_path / "task.dfy"
    src.write_text("method M() ensures true {}\n", encoding="utf-8")
    p = _spawn(tmp, DAFNY_HOLD.replace("SRC", str(src)))
    assert any(n.endswith(".dfy") for n in _everything(tmp))
    _kill(p)
    assert any(n.endswith(".dfy") for n in _everything(tmp))
    _run(tmp, DAFNY_QUICK.replace("SRC", str(src)))
    assert _everything(tmp) in ([], [PARENT_NAME])


def test_a_check_whose_owner_is_alive_is_kept_until_it_is_killed(tmp):
    p = _spawn(tmp, LIFTER_HOLD)
    try:
        _run(tmp, LIFTER_QUICK)                                              # a sweep runs while the owner lives
        assert any(n.endswith(".dfy") for n in _everything(tmp))
    finally:
        _kill(p)
    _run(tmp, LIFTER_QUICK)
    assert _everything(tmp) in ([], [PARENT_NAME])


def _dead_pid():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def _mk(tmp, name, files=True):
    parent = tmp / PARENT_NAME
    parent.mkdir(mode=0o700, exist_ok=True)
    folder = parent / name
    folder.mkdir(mode=0o700)
    if files:
        (folder / "solution.py").write_text("secret", encoding="utf-8")
    return folder


def test_a_dead_owner_without_a_lock_is_removed_and_a_live_one_is_kept(tmp):
    import check_scratch as cs
    gone = _mk(tmp, f"t-db-p{_dead_pid()}-s1-{'a' * 16}")
    alive = _mk(tmp, f"t-db-p{os.getpid()}-s{cs.start_time(os.getpid())}-{'b' * 16}")
    assert cs.sweep() == [gone.name]
    assert not gone.exists() and alive.exists() and (alive / "solution.py").exists()


def test_a_stale_folder_is_removed_on_a_python_whose_rmtree_has_no_dir_fd(tmp, monkeypatch):
    # Python 3.10, which CI runs, has shutil.rmtree(path, ignore_errors=False, onerror=None): no dir_fd. The sweep
    # removes the folder there too, and keeps refusing what it refused.
    import shutil
    import check_scratch as cs
    real = shutil.rmtree

    def rmtree_310(path, ignore_errors=False, onerror=None):
        return real(path, ignore_errors=ignore_errors, onerror=onerror)
    rmtree_310.avoids_symlink_attacks = real.avoids_symlink_attacks
    monkeypatch.setattr(shutil, "rmtree", rmtree_310)
    gone = _mk(tmp, f"t-db-p{_dead_pid()}-s1-{'e' * 16}")
    alive = _mk(tmp, f"t-db-p{os.getpid()}-s{cs.start_time(os.getpid())}-{'f' * 16}")
    assert cs.sweep() == [gone.name]
    assert not gone.exists() and alive.exists()


def test_a_reused_pid_is_not_taken_for_the_owner(tmp):
    import check_scratch as cs
    reused = _mk(tmp, f"t-db-p{os.getpid()}-s1-{'c' * 16}")                   # a live pid, another start time
    assert cs.start_time(os.getpid()) != "1"
    assert cs.sweep() == [reused.name]


def test_a_folder_a_live_lock_holds_is_kept_though_its_owner_is_dead(tmp):
    import fcntl
    import check_scratch as cs
    held = _mk(tmp, f"t-db-p{_dead_pid()}-s1-{'d' * 16}")
    fd = os.open(held, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        assert cs.sweep() == []
        assert (held / "solution.py").exists()
    finally:
        os.close(fd)
    assert cs.sweep() == [held.name]


def test_a_link_in_the_parent_is_never_followed(tmp, tmp_path):
    import check_scratch as cs
    target = tmp_path / "precious"
    target.mkdir()
    (target / "a.txt").write_text("keep", encoding="utf-8")
    (target / "sub").mkdir()
    (target / "sub" / "b.txt").write_text("keep", encoding="utf-8")
    parent = tmp / PARENT_NAME
    parent.mkdir(mode=0o700)
    link = parent / f"t-db-p{_dead_pid()}-s1-{'e' * 16}"
    link.symlink_to(target, target_is_directory=True)
    cs.sweep()
    assert (target / "a.txt").read_text() == "keep" and (target / "sub" / "b.txt").read_text() == "keep"
    assert link.is_symlink()                                                  # a link is not a real folder: left


def test_a_link_inside_a_stale_folder_is_removed_as_a_link(tmp, tmp_path):
    import check_scratch as cs
    target = tmp_path / "precious"
    target.mkdir()
    (target / "a.txt").write_text("keep", encoding="utf-8")
    stale = _mk(tmp, f"t-db-p{_dead_pid()}-s1-{'f' * 16}")
    (stale / "inner").symlink_to(target, target_is_directory=True)
    assert cs.sweep() == [stale.name]
    assert (target / "a.txt").read_text() == "keep"


def test_a_name_off_the_pattern_and_a_file_are_kept(tmp):
    import check_scratch as cs
    dead = _dead_pid()
    others = [_mk(tmp, "notes"), _mk(tmp, f"t-db-p{dead}-s1-{'a' * 15}"), _mk(tmp, f"t-db-p{dead}-s1-{'a' * 16}x"),
              _mk(tmp, f"p{dead}-s1-{'a' * 16}")]
    afile = tmp / PARENT_NAME / f"t-db-p{dead}-s1-{'9' * 16}"
    afile.write_text("x", encoding="utf-8")
    assert cs.sweep() == []
    assert all(o.exists() for o in others) and afile.exists()


def test_a_matching_folder_outside_the_parent_is_kept(tmp):
    import check_scratch as cs
    outside = tmp / f"t-db-p{_dead_pid()}-s1-{'a' * 16}"
    outside.mkdir()
    (outside / "x").write_text("x", encoding="utf-8")
    cs.sweep()
    assert (outside / "x").exists()


def test_a_parent_that_is_a_link_is_refused(tmp, tmp_path):
    import check_scratch as cs
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    (tmp / PARENT_NAME).symlink_to(real, target_is_directory=True)
    with pytest.raises(cs.ScratchRefused):
        cs.sweep()
    with pytest.raises(cs.ScratchRefused):
        cs.TemporaryDirectory(prefix="t-")
    assert list(real.iterdir()) == []


def test_a_parent_group_or_world_writable_is_refused(tmp):
    import check_scratch as cs
    parent = tmp / PARENT_NAME
    parent.mkdir()
    for mode in (0o770, 0o707, 0o777, 0o720):
        os.chmod(parent, mode)
        with pytest.raises(cs.ScratchRefused):
            cs.TemporaryDirectory(prefix="t-")
        assert list(parent.iterdir()) == []


def test_a_parent_that_is_a_file_is_refused(tmp):
    import check_scratch as cs
    (tmp / PARENT_NAME).write_text("x", encoding="utf-8")
    with pytest.raises(cs.ScratchRefused):
        cs.TemporaryDirectory(prefix="t-")


def test_the_parent_and_each_folder_are_private_and_removed_at_the_end(tmp):
    import check_scratch as cs
    with cs.TemporaryDirectory(prefix="t-db-") as name:
        assert os.stat(name).st_mode & 0o777 == 0o700
        assert os.stat(tmp / PARENT_NAME).st_mode & 0o777 == 0o700
        assert os.path.dirname(name) == str(tmp / PARENT_NAME)
        assert cs.sweep() == []                                              # our own live folder
    assert not os.path.exists(name)


def test_an_object_that_is_collected_removes_its_folder(tmp):
    import gc
    import check_scratch as cs
    d = cs.TemporaryDirectory(prefix="t-")
    name = d.name
    del d
    gc.collect()
    assert not os.path.exists(name)
