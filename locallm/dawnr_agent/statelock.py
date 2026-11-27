"""statelock.py: one lock for the files two dawnr sessions share.

Every session started without --state uses the same state folder, so two terminals can write the plan log
(plans.jsonl) and the journal at the same time. A session that trims a file reads the newest lines, writes a copy
and swaps it in, so a line the other session appended in between is lost. To prevent that, this lock is held:

- for every append to those files;
- for every rewrite of them;
- for the first writing of the sandbox's marker files.

A rewrite therefore never overlaps another process's append or rewrite. The lock is on the file `.lock` in the state
folder and one process holds it at a time:

  POSIX    fcntl.flock(fd, LOCK_EX | LOCK_NB): an advisory lock on the open file, dropped when the process ends or
           the descriptor is closed (https://docs.python.org/3/library/fcntl.html#fcntl.flock)
  Windows  msvcrt.locking(fd, LK_NBLCK, 1): locks one byte at the start of the file, which "may continue beyond the
           end of the file", so the file stays empty
           (https://docs.python.org/3/library/msvcrt.html#msvcrt.locking). The blocking mode, LK_LOCK, gives up
           after ten tries a second apart and cannot wait longer, so on both systems the non-blocking mode is
           retried until WAIT seconds have passed.

The lock file is never followed through a link. Before opening it, the code checks the name for a link. It opens
with O_NOFOLLOW where the system has it. Then it compares the opened file with what the name holds now. A link, a
junction, or another file swapped in at that name is refused. The file is created owner-only, holds nothing and is
never written. The state folder stays outside the model's roots like the files in it (paths.py), and `dawnr forget`
knows the name (bin/dawnr).
"""
from __future__ import annotations

import errno
import os
import stat
import time
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:                                            # Windows
    fcntl = None
try:
    import msvcrt
except ImportError:                                            # POSIX
    msvcrt = None

LOCK_NAME = ".lock"
WAIT = 30.0                    # seconds to wait for the lock; a write holds it only for milliseconds
POLL = 0.005
REPARSE_POINT = 0x400          # FILE_ATTRIBUTE_REPARSE_POINT: a Windows link, junction or mount point


class StateLockRefused(OSError):
    """StateLockRefused: the name `.lock` holds something other than an ordinary file of its own."""


def _is_link(named: os.stat_result) -> bool:
    return stat.S_ISLNK(named.st_mode) or bool(getattr(named, "st_file_attributes", 0) & REPARSE_POINT)


def _refuse(path: Path) -> StateLockRefused:
    return StateLockRefused(errno.EPERM, f"{path} is a link or not an ordinary file of its own; not used as a lock")


def _refuse_a_link(path: Path) -> None:
    """_refuse_a_link: refuse a link at `path` before the file is opened, without following it.

    Where there is no O_NOFOLLOW (Windows), opening with O_CREAT through a link to nothing would create the file the
    link points at.
    """
    try:
        named = os.lstat(path)
    except FileNotFoundError:
        return
    if _is_link(named):
        raise _refuse(path)


def _refuse_unless_ordinary(fd: int, path: Path) -> None:
    opened = os.fstat(fd)
    named = os.lstat(path)
    if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1 or _is_link(named)
            or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)):
        raise _refuse(path)


def _try(fd: int) -> bool:
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        return True
    except OSError as e:
        if e.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):     # another process holds the lock
            return False
        raise


def _release(fd: int) -> None:
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_UN)
        else:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    except OSError:
        pass                                                   # closing the descriptor releases the lock anyway


@contextmanager
def state_lock(state_dir, wait: float | None = None):
    """state_lock: hold the state folder's lock for the duration of the `with` block.

    Raises OSError, and does not run the block, when the lock file is not an ordinary file of its own
    (StateLockRefused) or when another process keeps the lock past the wait (TimeoutError).
    """
    folder = Path(state_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / LOCK_NAME
    flags = (os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
             | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
    _refuse_a_link(path)
    fd = os.open(path, flags, 0o600)
    try:
        _refuse_unless_ordinary(fd, path)
        deadline = time.monotonic() + (WAIT if wait is None else wait)
        while not _try(fd):
            if time.monotonic() >= deadline:
                raise TimeoutError(errno.ETIMEDOUT, f"{path} is held by another dawnr process")
            time.sleep(POLL)
        try:
            yield
        finally:
            _release(fd)
    finally:
        os.close(fd)
