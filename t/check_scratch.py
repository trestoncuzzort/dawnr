"""check_scratch.py -- private scratch folders for the copies a check makes, and a sweep of those a kill leaves.

Why it exists: a check removes its copy of the program when it ends (a `with` block or a `finally`), but SIGKILL runs
neither, so a killed check would leave its copy in the temporary folder (see PRIVACY.md, the row on copies of a program
being checked). The next check removes it.

Layout:
- `<temporary folder>/dawnr-checks-<uid>/` is the parent. It is created mode 0700 with mkdir, which fails if the name
  exists, so a planted name is never adopted. It is then opened with O_NOFOLLOW | O_DIRECTORY and checked on the open
  descriptor: a link, a non-folder, a folder owned by another user, or one that group or others can write to is refused
  (ScratchRefused), and nothing is made in it.
- Each check's folder is made directly inside the parent, mode 0700, named `<prefix>-p<pid>-s<start>-<16 hex>`. The
  owner's PID and process start time (Linux: field 22 of /proc/<pid>/stat; `x` where the platform gives none) are in
  the name, so they exist the instant the folder does.
- The creator opens its folder and takes an exclusive flock on that descriptor for as long as the check runs. A lock
  lives in the open file description, so the kernel drops it when the process dies, SIGKILL included.

Sweep (runs at the start of every scratch folder made here). A folder in the parent is removed only if ALL hold:
- it is a real folder (lstat, not a link) directly inside the parent;
- its name matches the pattern above exactly;
- its lock can be taken without waiting: no live holder, including a child that inherited the descriptor;
- its recorded PID is dead, or is alive with a different start time.
Everything else is left alone: links, files, names off the pattern, folders a live process holds or whose owner is
alive, folders owned by another user, and anything the sweep cannot decide.

The removal is shutil.rmtree through the parent's descriptor (`dir_fd`, Python 3.11 and later) or, on Python 3.10, by
the folder's full path inside this user's own 0700 parent (`_rmtree_in`). The sweep does nothing where
shutil.rmtree.avoids_symlink_attacks is false, so it never follows a link and never touches anything outside the
parent.

Two outside designs explain the choices. systemd's tmpfiles.d(5) age cleanup also takes an exclusive lock on what it
removes and skips what is locked. pytest's numbered temp folders (`_pytest/pathlib.py`) trust a lock file's age rather
than whether its owner is alive, which is why this module uses flock plus PID and start time."""
from __future__ import annotations

import inspect
import os
import re
import secrets
import shutil
import stat
import tempfile
import weakref

try:
    import fcntl
except ImportError:                                      # a platform without flock: plain private folders, no sweep
    fcntl = None

_NAME = re.compile(r"\A[A-Za-z0-9_.-]+-p(\d+)-s(\d+|x)-[0-9a-f]{16}\Z")


class ScratchRefused(OSError):
    """The scratch parent exists but is not safe to use; nothing was made or removed."""


def parent_path() -> str:
    return os.path.join(tempfile.gettempdir(), f"dawnr-checks-{os.geteuid()}" if hasattr(os, "geteuid")
                        else "dawnr-checks")


def _open_parent() -> int:
    """The scratch parent as an open descriptor, made if absent, refused if unsafe."""
    path = parent_path()
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as e:
        raise ScratchRefused(f"{path}: not a folder, or a link: {e}") from e
    try:
        st = os.fstat(fd)
        if not stat.S_ISDIR(st.st_mode):
            raise ScratchRefused(f"{path}: not a folder")
        if hasattr(os, "geteuid") and st.st_uid != os.geteuid():
            raise ScratchRefused(f"{path}: owned by another user")
        if st.st_mode & 0o022:
            raise ScratchRefused(f"{path}: group or others can write to it")
    except BaseException:
        os.close(fd)
        raise
    return fd


def start_time(pid: int) -> str:
    """The process start time in clock ticks since boot as digits, or `x` when this platform does not give it."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            data = f.read().decode("utf-8", "replace")
        return str(int(data.rsplit(")", 1)[1].split()[19]))
    except (OSError, ValueError, IndexError):
        return "x"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:                                      # PermissionError: it exists; anything else: cannot decide
        return True
    return True


def _owner_gone(pid: int, start: str) -> bool:
    if not _alive(pid):
        return True
    now = start_time(pid)
    return start != "x" and now != "x" and now != start


def sweep() -> list[str]:
    """Remove the stale folders of killed checks from the scratch parent; return their names. A folder it cannot
    decide is left; a refused parent raises ScratchRefused."""
    if fcntl is None or not shutil.rmtree.avoids_symlink_attacks:
        return []
    pfd = _open_parent()
    removed = []
    try:
        for name in os.listdir(pfd):
            m = _NAME.match(name)
            if m is None:
                continue
            try:
                st = os.stat(name, dir_fd=pfd, follow_symlinks=False)
                if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid():
                    continue
                if not _owner_gone(int(m.group(1)), m.group(2)):
                    continue
                dfd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=pfd)
            except OSError:
                continue
            try:
                try:
                    fcntl.flock(dfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    continue                             # a live holder
                if os.fstat(dfd).st_ino != st.st_ino:    # replaced between the check and the open
                    continue
                _rmtree_in(pfd, name)
                removed.append(name)
            except OSError:
                continue
            finally:
                os.close(dfd)
    finally:
        os.close(pfd)
    return removed


def _rmtree_in(pfd: int, name: str) -> None:
    """Remove the folder `name` inside the open scratch parent `pfd`.

    Python 3.11 and later take the parent as `dir_fd`. Python 3.10 has no `dir_fd` on rmtree, so there the folder is
    removed by its full path instead. That is still safe: the parent is this user's own 0700 folder (`_open_parent`
    refuses any other), so no one else can swap a link in, and rmtree never follows links inside the tree
    (`shutil.rmtree.avoids_symlink_attacks`, checked by `sweep` before it calls this)."""
    if "dir_fd" in inspect.signature(shutil.rmtree).parameters:
        shutil.rmtree(name, dir_fd=pfd)
    else:
        shutil.rmtree(os.path.join(parent_path(), name))


def _remove(pid: int, path: str, fd: int | None) -> None:
    if os.getpid() != pid:                               # a forked child does not remove its parent's folder
        return
    shutil.rmtree(path, ignore_errors=True)
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass


class TemporaryDirectory:
    """A drop-in for tempfile.TemporaryDirectory(prefix=...): `.name`, `.cleanup()`, `with ... as name`; the folder is
    made in the scratch parent, locked while this object lives, and removed by cleanup, by leaving the `with`, or when
    the object is collected. A killed process's folder is removed by the next sweep."""

    def __init__(self, prefix: str = "t"):
        prefix = re.sub(r"[^A-Za-z0-9_.-]", "_", prefix or "t").rstrip("-") or "t"
        if fcntl is None:
            self.name = tempfile.mkdtemp(prefix=prefix + "-")
            self._fd = None
        else:
            sweep()
            pfd = _open_parent()
            try:
                pid = os.getpid()
                for _ in range(100):
                    name = f"{prefix}-p{pid}-s{start_time(pid)}-{secrets.token_hex(8)}"
                    try:
                        os.mkdir(name, 0o700, dir_fd=pfd)
                        break
                    except FileExistsError:
                        continue
                else:
                    raise ScratchRefused("no free folder name")
                self._fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=pfd)
                fcntl.flock(self._fd, fcntl.LOCK_EX)
                self.name = os.path.join(parent_path(), name)
            finally:
                os.close(pfd)
        self._finalizer = weakref.finalize(self, _remove, os.getpid(), self.name, self._fd)

    def cleanup(self) -> None:
        self._finalizer()

    def __enter__(self) -> str:
        return self.name

    def __exit__(self, *_) -> None:
        self.cleanup()

    def __repr__(self) -> str:
        return f"<TemporaryDirectory {self.name!r}>"
