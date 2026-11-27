"""statelock.py: one lock for the files two dawnr sessions share.

Every session started without --state uses the same state folder, so two terminals write the same plan log
(plans.jsonl) and journal at once. A file one session cuts down (it reads the newest lines, writes a copy and swaps
it in) loses a line the other appended meanwhile, so every append to those files and every rewrite of them, and
the first writing of the sandbox's marker files, is made while holding this lock, and a rewrite never runs
beside another process's append or rewrite. The lock is on the file `.lock` in the state folder, held by one
process at a time:

  POSIX    fcntl.flock(fd, LOCK_EX | LOCK_NB): an advisory lock on the open file, dropped when the process ends or
           the descriptor is closed (https://docs.python.org/3/library/fcntl.html#fcntl.flock)
  Windows  msvcrt.locking(fd, LK_NBLCK, 1): one byte at the start of the file, "may continue beyond the end of the
           file", so the file stays empty (https://docs.python.org/3/library/msvcrt.html#msvcrt.locking). The
           blocking mode, LK_LOCK, gives up after ten tries a second apart and cannot be given a longer wait, so
           the non-blocking mode is tried again here, on both systems, until WAIT seconds have passed.

The lock file is opened without following a link where the system has O_NOFOLLOW, and what was opened is then
compared with what the name holds now, so that a link (or a junction, or another file swapped in) at that name is
refused and never followed. It is created owner-only, holds nothing and is never written. The state folder stays
outside the model's roots like the files in it (paths.py), and `dawnr forget` knows the name (bin/dawnr).
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
WAIT = 30.0                    # seconds to wait for another process's turn; a write holds the lock for milliseconds
POLL = 0.005
REPARSE_POINT = 0x400          # FILE_ATTRIBUTE_REPARSE_POINT: a Windows link, junction or mount point


class StateLockRefused(OSError):
    """The name `.lock` holds something other than an ordinary file of its own."""


def _refuse_unless_ordinary(fd: int, path: Path) -> None:
    opened = os.fstat(fd)
    named = os.lstat(path)
    if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1 or stat.S_ISLNK(named.st_mode)
            or getattr(named, "st_file_attributes", 0) & REPARSE_POINT
            or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)):
        raise StateLockRefused(errno.EPERM, f"{path} is a link or not an ordinary file of its own; not used as a lock")


def _try(fd: int) -> bool:
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        return True
    except OSError as e:
        if e.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):     # held by another process
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
        pass                                                   # closing the descriptor lets go of it anyway


@contextmanager
def state_lock(state_dir, wait: float | None = None):
    """Hold the state folder's lock for the block. Raises OSError when the lock file is not an ordinary file of its
    own (StateLockRefused) or another process keeps the lock past the wait (TimeoutError); the block is not run."""
    folder = Path(state_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / LOCK_NAME
    flags = (os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
             | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
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
