#!/usr/bin/env python3
r"""Where locallm keeps its state -- once per platform, because `~/.cache` is a Linux word.

`t/lab.py` put its event log, its scratch runs and its window geometry under
`~/.cache/...` whenever `T_WATCH`, `T_LAB_SCRATCH` or `XDG_CACHE_HOME` was unset, which
is the normal case. On Windows that is `C:\Users\<name>\.cache\t-lab`: a folder no
Windows tool, installer or backup looks in, and one nothing will ever clean up. On macOS
the platform has a documented answer and it is not that either. And none of the three
could live on the USB stick locallm is meant to run from with no install.

So the order is: an environment variable if one is set, then a `locallm-data/` folder
beside the program when that place can actually be written to, then the platform's own
per-user location. The middle step is the point of this file -- a stick carries its own
state and leaves nothing behind on a machine it was borrowed from.

The three platform answers, each from the platform's own document rather than from
folklore:

* Windows `%LOCALAPPDATA%`. FOLDERID_LocalAppData, "Default Path %LOCALAPPDATA%
  (%USERPROFILE%\AppData\Local)" (learn.microsoft.com/en-us/windows/win32/shell/knownfolderid).
  Local and not FOLDERID_RoamingAppData/`%APPDATA%`: a growing event log has no business
  being copied around a domain, and a saved pixel geometry is wrong on the next machine's
  monitors.
* macOS `~/Library/Application Support`, which holds "all app-specific data and support
  files" and which "Your app is responsible for creating" (developer.apple.com/library/
  archive/documentation/FileManagement/Conceptual/FileSystemProgrammingGuide/
  MacOSXDirectories/MacOSXDirectories.html). Not `~/Library/Caches`: the same table
  reserves that for "cached data that can be regenerated as needed", and a graded run's
  events cannot be regenerated.
* Linux `$XDG_STATE_HOME`, default `~/.local/state`
  (specifications.freedesktop.org/basedir-spec/latest). That page describes the state dir
  as what "should persist between (application) restarts" and lists "actions history
  (logs, history, recently used files, ...)" and "current state of the application that
  can be reused on a restart (view, layout, open files, undo history, ...)" -- the event
  log and the window position, named. The old `$XDG_CACHE_HOME` is the wrong one by the
  same page: it is for "non-essential (cached) data".

platformdirs (github.com/tox-dev/platformdirs) is the reference implementation of that
split and agrees on every one: its `macos.py` uses `~/Library/Application Support` and
cites the same Apple guide, its `windows.py` maps `user_state_dir` onto `user_data_dir`
which is `CSIDL_LOCAL_APPDATA`, and its XDG mixin honours the variables. It is not
imported -- this repository ships with no third-party packages and what is wanted here is
one function -- so its layout is followed instead.

The portable step follows VS Code's Portable mode, which "enables all data created and
maintained by VS Code to live near itself, so it can be moved around across environments"
and is keyed on a plain folder beside the executable (code.visualstudio.com/docs/editor/
portable). Two differences, both deliberate: VS Code makes the operator create the folder
and we create it when the place proves writable, because a borrowed machine and a stick
must work with no setup step; and VS Code's `data` folder overrides `--user-data-dir`
while here the environment variable wins, because the lab workstation sets `T_WATCH` and
a terminal-driven run, the window watching it and `t/grade_lab.sh` streaming into it must
all name one file.
"""
from __future__ import annotations

import functools
import os
import uuid
import sys
import tempfile
from pathlib import Path

__all__ = ["platform_state_dir", "program_dir", "state_dir", "state_path", "state_root", "writable"]

APP = "locallm"
# Beside the program, spelled out: an operator who finds this folder on their stick can
# tell what made it and delete it. VS Code calls its own `data`, which is too anonymous
# for something sitting next to a repository checkout.
PORTABLE = "locallm-data"


def program_dir() -> Path:
    """The folder the program itself sits in, which is the folder a stick's state belongs in.

    Frozen, that is the folder holding the executable; from source it is this repository's
    root, the parent of `t/`, so `locallm-data/` lands beside `t/` and `locallm/` rather
    than inside one of them. The frozen case has to be asked about separately because
    `sys.executable` is the *interpreter* when nothing is frozen -- reading it
    unconditionally would try to put state next to `/usr/bin/python3`
    (pyinstaller.org/en/stable/runtime-information.html).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def writable(d: Path) -> bool:
    """Can this folder be made and written in? Answered by doing it, not by reading bits.

    `os.access` and `st_mode` are the wrong instrument and the standard library says so:
    checking before opening "creates a security hole" and is better replaced by trying,
    and "I/O operations may fail even when access() indicates that they would succeed,
    particularly for operations on network filesystems which may have permissions
    semantics beyond the usual POSIX permission-bit model"
    (docs.python.org/3/library/os.html#os.access). Every case this function exists for is
    of that kind: a stick mounted `ro`, where the bits still read 755 and EROFS only
    arrives at the write; a FAT stick, which carries no POSIX ownership at all so the bits
    are whatever the mount options invented; and an SMB or NFS home where the server
    decides and the client's idea of the mode is a guess.

    The probe file carries the pid, so two copies of the window starting together cannot
    delete each other's probe and conclude the place is unusable. A folder this call
    created and could not then write to is removed again, because a stick must be left
    with nothing of ours on it.
    """
    try:
        existed = d.is_dir()
    except OSError:                   # a parent we may not read: not a place for state, and not an error either
        return False
    probe = d / f".locallm-write-probe-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    fd = None
    try:
        d.mkdir(parents=True, exist_ok=True)
        # O_EXCL|O_NOFOLLOW: a probe of this name that already exists (a symlink planted there, say) is never
        # followed or overwritten; the write goes to a file this call created
        fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.close(fd)
        fd = None
        probe.write_text("probe\n", encoding="utf-8")   # real bytes into the file just created, so a full stick fails here
    except OSError:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
            fd = None
        try:
            probe.unlink()                    # a file this call created before the write failed
        except OSError:
            pass
        if not existed:
            try:
                d.rmdir()
            except OSError:
                pass
        return False
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            if probe.is_symlink() is False and probe.exists():
                probe.unlink()
        except OSError:
            pass
    return True


def platform_state_dir() -> Path:
    """The per-user state folder this operating system documents, with the app name on it.

    Read from the environment rather than through SHGetKnownFolderPath/ctypes on Windows:
    `%LOCALAPPDATA%` is what the Known Folder page gives as that folder's own default path
    and is set by Windows itself, so the ctypes call would buy only the case of a stripped
    environment -- which the literal `AppData\\Local` under the profile covers.
    """
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "").strip()
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return base / APP
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP
    # basedir-spec, section 2: "All paths set in these environment variables must be
    # absolute. If an implementation encounters a relative path in any of these variables
    # it should consider the path invalid and ignore it."
    xdg = os.environ.get("XDG_STATE_HOME", "")
    base = Path(xdg) if xdg.strip() and os.path.isabs(xdg) else Path.home() / ".local" / "state"
    return base / APP


@functools.lru_cache(maxsize=None)
def state_root(program: Path | None = None, platform: Path | None = None) -> Path:
    """The one folder everything else here hangs off, created and proven writable.

    The two arguments are a seam for `t/test_paths.py`: a test that let this find the real
    candidates would write into the operator's own `~/.local/state`, and the read-only
    case cannot be staged at all without being able to say where "beside the program" is.
    Cached because the decision costs a mkdir, a write and an unlink and `t/lab.py` asks
    for it three times at import; a test that changes the environment calls
    `state_root.cache_clear()`.
    """
    beside = (program if program is not None else program_dir()) / PORTABLE
    if writable(beside):
        return beside
    try:
        fallback = platform if platform is not None else platform_state_dir()
    except (RuntimeError, OSError):          # no home directory can be determined: the temporary fallback stands
        fallback = None
    if fallback is not None and writable(fallback):
        return fallback
    return Path(tempfile.mkdtemp(prefix=f"{APP}-state-"))


def state_dir(*parts: str) -> Path:
    """A folder under the state root, created.

    This may raise, unlike everything above it, and that is the intent: `state_root` wrote
    a file in the root a moment earlier, so a failure here is a disk that has just gone
    away, and a traceback naming the path is worth more than a silently wrong location.
    """
    d = state_root().joinpath(*parts)
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_path(var: str, *parts: str, env_join: tuple[str, ...] = ()) -> Path:
    """`$var` when it is set, else the state root plus `parts`, with the parent made.

    `parts` names a leaf -- a file or a folder created later by whoever writes into it --
    and the folders above it are created here. The variable wins for the reason the module
    docstring gives: things outside this window are told the same path.

    `env_join` is for a variable that names a base folder rather than the path itself.
    `XDG_CACHE_HOME` is the one: the geometry file has always been
    `$XDG_CACHE_HOME/t-lab/geometry`, and `t/shots.py` sets that variable to a throwaway
    folder precisely so a documentation run cannot move the operator's real window. A
    relative value is ignored there rather than honoured, which is what basedir-spec
    section 2 says to do with one.
    """
    raw = os.environ.get(var, "")
    if raw.strip() and (not env_join or os.path.isabs(raw)):     # a base folder must be absolute as written (basedir-spec 2)
        target = Path(raw).expanduser().joinpath(*env_join)       # the value itself is kept whole: a path may end in a space
        try:
            target.parent.mkdir(parents=True, exist_ok=True)       # the promise holds for an override too
        except OSError:
            pass
        return target
    *folders, leaf = parts
    return state_dir(*folders) / leaf
