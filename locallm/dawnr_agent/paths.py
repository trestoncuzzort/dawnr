"""paths.py: the operator's roots, and opening paths inside them without ever leaving them.

A path from the model is text: a root's name, then the path inside it
(`project/src/a.t`), or an absolute path that lies inside a root. It is parsed
lexically first (resolve()): `..` is refused outright rather than normalised
away, so no spelling of a path can climb out; a NUL byte, a control character,
a Windows drive or device name are refused by name.

It is then opened one component at a time, each component through the
directory descriptor of the one before it, with O_NOFOLLOW: a symbolic link
anywhere below the root is refused, never followed. This is openat2(2)'s
RESOLVE_BENEATH with RESOLVE_NO_SYMLINKS (man7.org/linux/man-pages/man2/openat2.2.html),
done with os.open(dir_fd=...) because Python has no openat2 wrapper, and it is
what the MCP reference filesystem server (github.com/modelcontextprotocol/servers,
src/filesystem/path-validation.ts and lib.ts, read 2026-09-27) does not do:
there a path is checked with realpath and then opened by name, so a directory
swapped for a link between the check and the open is followed. Here there is
no separate check to race: the descriptor that was checked is the one that is
used. The same server once compared paths as strings and let
`/allowed_evil` pass for `/allowed` (GHSA-hc55-p739-j48w); here a root is
matched by whole components, never by a string prefix.

Beyond containment, two lists the operator controls:

* **secrets**: names and globs (`.ssh`, `*.pem`, `.env`, ...) that are
  never read, listed as secret, and skipped by search; their files anywhere
  under the home directory are also known by identity (device and inode),
  found by a bounded breadth-first scan when the agent is built
  (home_secret_identities), so a hard link to one inside a root is refused
  too.
* **protected**: what the model may read but never write: `.git` by default
  (a written `.git/config` or hook runs code the next time git does), and,
  added by the agent at load, the harness's configuration, audit log and
  state, the skills and hooks it runs, and the code that enforces all of it.
  Protected files and directories are matched by identity as well as by
  name, so case, Unicode spelling or a hard link does not get around them.

And one rule that consults no list: a file's contents are returned only when
every name the file has is one the model could read itself (check_read). A
regular file with more than one link has names elsewhere, and link(2) says it
is impossible to tell which name was the original, so the roots are searched
for them (names_in_roots) and the file is refused unless all of them are
found there, none secret, the way GNU tar's --check-links compares the links
it archived against st_nlink; a search that stops at its cap refuses. The
CERT C rule POS01-C and Postfix's safe_open() refuse every file with more
than one link; this refuses only those with a name outside the roots, so two
names inside them still work. The real path of the opened file must be
inside a root too.

Where the platform has no directory-descriptor calls (Windows), the same
rules run on path strings with a symbolic-link and reparse-point check per
component; there a check-then-use window remains and DAWNR-AGENT.md says so.
"""
from __future__ import annotations

import errno
import fnmatch
import os
import re
import stat
import sys
import time
from collections import deque
from dataclasses import dataclass, field

ROOT_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$")
MAX_PATH = 4096
MAX_COMPONENT = 255
WINDOWS = os.name == "nt"
FD_WALK = (not WINDOWS and os.open in os.supports_dir_fd and os.stat in os.supports_dir_fd
           and hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY") and os.scandir in os.supports_fd)
O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
O_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
O_NOCTTY = getattr(os, "O_NOCTTY", 0)
O_BINARY = getattr(os, "O_BINARY", 0)
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_WIN_DEVICES = {"con", "prn", "aux", "nul", "conin$", "conout$",
                *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

# never read (a leading dot matters: `.env` is a secret, `env` is not); matched case-insensitively
DEFAULT_SECRETS = (".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker", ".password-store", ".netrc", ".pgpass",
                   ".git-credentials", ".npmrc", ".pypirc", ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx",
                   "*.kdbx", "id_rsa*", "id_dsa*", "id_ecdsa*", "id_ed25519*", "credentials", "credentials.json")
# read but never written
DEFAULT_PROTECT = (".git",)
# The home directory's secret scan, once per agent: breadth-first, so a cap cuts the deepest levels rather than
# whole folders. The whole home tree of the desktop this was written on is 10,065,366 entries and took 78 s to walk
# (DAWNR-AGENT.md section 7), too long to pay at every start; 200,000 entries covers its first five levels whole.
HOME_SCAN_ENTRIES = 200_000
HOME_SCAN_SECONDS = 2.0
# The roots searched for a file's other names at read time (only for a file with more than one): past either cap
# the search stops and the file is refused, never read on a count that may be short.
LINK_SCAN_ENTRIES = 200_000
LINK_SCAN_SECONDS = 5.0
_PROC_FD = sys.platform.startswith("linux") and os.path.isdir("/proc/self/fd")


class PathRefused(ValueError):
    """A path the agent will not use; the message is what the model is told."""


@dataclass(frozen=True)
class Root:
    name: str
    path: str                  # resolved once, when the operator's configuration is loaded
    write: bool = False
    ident: tuple = ()          # (st_dev, st_ino) of the root when loaded: a root replaced later is refused

    @property
    def mode(self) -> str:
        return "write" if self.write else "read"


@dataclass(frozen=True)
class Target:
    root: Root
    parts: tuple

    @property
    def display(self) -> str:
        return "/".join((self.root.name,) + tuple(self.parts))

    @property
    def abspath(self) -> str:
        return os.path.join(self.root.path, *self.parts)

    @property
    def name(self) -> str:
        return self.parts[-1] if self.parts else ""

    def child(self, name: str) -> "Target":
        return Target(self.root, tuple(self.parts) + (name,))


def ident(st) -> tuple:
    return (st.st_dev, st.st_ino)


def _is_link(st) -> bool:
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & _REPARSE)


@dataclass
class Space:
    """The roots and the rules. Built once from the operator's configuration; nothing the model does changes it."""
    roots: tuple = ()
    secret_names: tuple = DEFAULT_SECRETS
    protect_names: tuple = DEFAULT_PROTECT
    protected_ids: set = field(default_factory=set)        # files and directories never written, by identity
    protected_entries: set = field(default_factory=set)    # (parent identity, casefolded name) not yet existing
    secret_ids: set = field(default_factory=set)           # files and directories never read, by identity
    hidden_ids: set = field(default_factory=set)           # never listed or searched (the agent's own state)
    link_scan_entries: int = LINK_SCAN_ENTRIES             # the caps of names_in_roots
    link_scan_seconds: float = LINK_SCAN_SECONDS

    def __post_init__(self):
        names = [r.name for r in self.roots]
        if len(set(names)) != len(names):
            raise ValueError("two roots share a name")
        self.secret_names = tuple(s.casefold() for s in self.secret_names)
        self.protect_names = tuple(s.casefold() for s in self.protect_names)

    # ------------------------------------------------------------ parsing --

    def root(self, name: str) -> Root | None:
        for r in self.roots:
            if r.name == name:
                return r
        return None

    def resolve(self, text) -> Target:
        """The target a path names, lexically, without touching the filesystem. Raises PathRefused."""
        if not isinstance(text, str) or not text.strip():
            raise PathRefused("give a path: a root's name, then the path inside it" + self._roots_hint())
        if len(text) > MAX_PATH:
            raise PathRefused(f"the path is over {MAX_PATH} characters")
        if "\x00" in text:
            raise PathRefused("the path contains a NUL byte")
        if _CONTROL.search(text):
            raise PathRefused("the path contains a control character")
        if not WINDOWS and re.match(r"^[A-Za-z]:([\\/]|$)", text):
            raise PathRefused("a Windows drive path on a system that has none; give a root's name, then the path "
                              "inside it" + self._roots_hint())
        seps = "/\\" if WINDOWS else "/"
        raw = [c for c in re.split("[" + re.escape(seps) + "]", text)]
        absolute = os.path.isabs(text) or (not WINDOWS and text.startswith("/"))
        comps = [c for c in raw if c not in ("", ".")]
        for k, c in enumerate(comps):
            if c == "..":
                raise PathRefused(f"{text!r}: '..' is not used; give the path from its root" + self._roots_hint())
            if len(c) > MAX_COMPONENT:
                raise PathRefused(f"a path component is over {MAX_COMPONENT} characters")
            if WINDOWS:
                self._windows_component(c, text, first=absolute and k == 0)
        if absolute:
            return self._from_absolute(text, comps)
        if not comps:
            raise PathRefused("give a path: a root's name, then the path inside it" + self._roots_hint())
        root = self.root(comps[0])
        if root is None:
            raise PathRefused(f"{text!r}: no root named {comps[0]!r}" + self._roots_hint())
        return Target(root, tuple(comps[1:]))

    def _windows_component(self, c: str, text: str, first: bool) -> None:
        if first and re.match(r"^[A-Za-z]:$", c):
            return
        if ":" in c:
            raise PathRefused(f"{text!r}: ':' is not allowed in a path component (alternate data streams)")
        if c.rstrip(" .") != c:
            raise PathRefused(f"{text!r}: a component may not end in a dot or a space")
        if c.split(".")[0].casefold() in _WIN_DEVICES:
            raise PathRefused(f"{text!r}: {c!r} is a device name")

    def _from_absolute(self, text: str, comps: list) -> Target:
        norm = os.path.normcase(os.path.normpath(text))
        best = None
        for r in self.roots:
            base = os.path.normcase(r.path)
            if norm == base or norm.startswith(base.rstrip(os.sep) + os.sep):
                if best is None or len(base) > len(os.path.normcase(best.path)):
                    best = r
        if best is None:
            raise PathRefused(f"{text!r} is outside every root" + self._roots_hint())
        rest = os.path.normpath(text)[len(best.path.rstrip(os.sep)):].lstrip(os.sep + ("/" if WINDOWS else ""))
        parts = tuple(p for p in re.split(r"[\\/]" if WINDOWS else "/", rest) if p not in ("", "."))
        return Target(best, parts)

    def _roots_hint(self) -> str:
        if not self.roots:
            return " (no roots are configured)"
        return " (roots: " + ", ".join(r.name for r in self.roots) + ")"

    # -------------------------------------------------------------- rules --

    def _glob_hit(self, patterns: tuple, target: Target) -> str | None:
        rel = "/".join(target.parts).casefold()
        for p in patterns:
            if "/" in p:
                if fnmatch.fnmatchcase(rel, p):
                    return p
                continue
            for c in target.parts:
                if fnmatch.fnmatchcase(c.casefold(), p):
                    return p
        return None

    def secret_reason(self, target: Target) -> str | None:
        hit = self._glob_hit(self.secret_names, target)
        return f"{target.display} matches the secret pattern {hit!r}; it is never read" if hit else None

    def check_names(self, target: Target, *, write: bool) -> None:
        reason = self.secret_reason(target)
        if reason:
            raise PathRefused(reason)
        if write:
            if not target.root.write:
                raise PathRefused(f"root {target.root.name} is read-only")
            hit = self._glob_hit(self.protect_names, target)
            if hit:
                raise PathRefused(f"{target.display} is protected ({hit!r}); it can be read but never written")

    # ------------------------------------------------------------ opening --

    def walk(self, target: Target, upto: int | None = None, *, write: bool = False):
        """A handle on the directory root/parts[:upto]: a directory descriptor (POSIX) or a checked path.

        Every component is opened without following a symbolic link, through its parent's descriptor. The
        caller closes the handle with close()."""
        if write:
            self.check_names(target, write=True)
        else:
            self._check_read_names(target)
        parts = tuple(target.parts[:len(target.parts) if upto is None else upto])
        if not FD_WALK:
            return self._walk_paths(target, parts, write)
        try:
            fd = os.open(target.root.path, os.O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
        except OSError as e:
            raise PathRefused(f"root {target.root.name} cannot be opened: {e.strerror}") from None
        try:
            st = os.fstat(fd)
            if target.root.ident and ident(st) != tuple(target.root.ident):
                raise PathRefused(f"root {target.root.name} was replaced since it was configured; not used")
            self._check_dir_ident(st, target, 0, write)
            for i, comp in enumerate(parts):
                try:
                    nfd = os.open(comp, os.O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC, dir_fd=fd)
                except OSError as e:
                    raise self._refusal(target, i, fd, e) from None
                os.close(fd)
                fd = nfd
                self._check_dir_ident(os.fstat(fd), target, i + 1, write)
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _check_read_names(self, target: Target) -> None:
        reason = self.secret_reason(target)
        if reason:
            raise PathRefused(reason)

    def _check_dir_ident(self, st, target: Target, depth: int, write: bool) -> None:
        shown = "/".join((target.root.name,) + tuple(target.parts[:depth]))
        if ident(st) in self.secret_ids:
            raise PathRefused(f"{shown} is a secret directory; it is never read")
        if ident(st) in self.hidden_ids:
            raise PathRefused(f"{shown} holds the agent's own records (its journal and backups); they are the "
                              "person's, not shown to the model")
        if write and ident(st) in self.protected_ids:
            raise PathRefused(f"{shown} is protected; it can be read but never written")

    def _walk_paths(self, target: Target, parts: tuple, write: bool) -> str:
        path = target.root.path
        try:
            st = os.lstat(path)
        except OSError as e:
            raise PathRefused(f"root {target.root.name} cannot be opened: {e.strerror}") from None
        if target.root.ident and ident(st) != tuple(target.root.ident):
            raise PathRefused(f"root {target.root.name} was replaced since it was configured; not used")
        self._check_dir_ident(st, target, 0, write)
        for i, comp in enumerate(parts):
            path = os.path.join(path, comp)
            try:
                st = os.lstat(path)
            except OSError as e:
                raise self._refusal(target, i, None, e) from None
            if _is_link(st):
                raise self._link_refusal(target, i, os.path.dirname(path))
            if not stat.S_ISDIR(st.st_mode):
                raise PathRefused(f"{self._shown(target, i)} is not a directory")
            self._check_dir_ident(st, target, i + 1, write)
        return path

    def _shown(self, target: Target, i: int) -> str:
        return "/".join((target.root.name,) + tuple(target.parts[:i + 1]))

    def _refusal(self, target: Target, i: int, parent, e: OSError) -> PathRefused:
        try:
            st = lstat_child(parent if parent is not None else os.path.join(target.root.path, *target.parts[:i]),
                             target.parts[i])
            if _is_link(st):
                return self._link_refusal(target, i, parent)
            if not stat.S_ISDIR(st.st_mode):
                return PathRefused(f"{self._shown(target, i)} is not a directory")
        except OSError:
            pass
        if e.errno == errno.ENOENT:
            return PathRefused(f"{self._shown(target, i)}: no such directory")
        return PathRefused(f"{self._shown(target, i)}: {e.strerror or e}")

    def _link_refusal(self, target: Target, i: int, parent) -> PathRefused:
        shown = self._shown(target, i)
        hint = ""
        try:
            real = os.path.realpath(os.path.join(target.root.path, *target.parts[:i + 1]))
            inside = self.display_of(real)
            hint = f"; it points to {inside}, use that path" if inside else "; it points outside every root"
        except (OSError, ValueError):
            pass
        return PathRefused(f"{shown} is a symbolic link; links are not followed{hint}")

    def display_of(self, real: str) -> str | None:
        """The root-relative spelling of an absolute path inside a root, else None (for messages only)."""
        norm = os.path.normcase(os.path.normpath(real))
        for r in sorted(self.roots, key=lambda r: -len(r.path)):
            base = os.path.normcase(r.path)
            if norm == base:
                return r.name
            if norm.startswith(base.rstrip(os.sep) + os.sep):
                rest = os.path.normpath(real)[len(r.path.rstrip(os.sep)) + 1:]
                return "/".join([r.name] + [p for p in re.split(r"[\\/]", rest) if p])
        return None

    def check_file_ident(self, st, target: Target, *, write: bool) -> None:
        if ident(st) in self.secret_ids:
            raise PathRefused(f"{target.display} is a secret file (by identity); it is never read")
        if write and ident(st) in self.protected_ids:
            raise PathRefused(f"{target.display} is protected; it can be read but never written")

    def check_new_entry(self, parent_st, target: Target) -> None:
        if (ident(parent_st), target.name.casefold()) in self.protected_entries:
            raise PathRefused(f"{target.display} is protected; it can be read but never written")

    # --------------------------------------------------------- hard links --

    def check_read(self, fd: int, st, target: Target, names=None) -> None:
        """What an opened file passes before a tool returns anything of its contents (read_problem)."""
        problem = self.read_problem(fd, st, target, names)
        if problem:
            raise PathRefused(problem[1])

    def read_problem(self, fd: int, st, target: Target, names=None) -> tuple[str, str] | None:
        """None, or (kind, why) when the opened file `fd` (whose fstat is `st`) must not be read: its real path is
        not inside a root ("not inside the roots"), or it has a name the model could not read itself ("hard link",
        link_problem). `names`, when given, is a function returning names_in_roots() for every file (a search asks
        once, not once per file). For a file with more than one name the descriptor is examined again after the
        search, as Postfix's safe_open() compares its two stats: a name added or removed meanwhile changes the link
        count or the status-change time, and the file is refused rather than read on a count already stale."""
        if not self.real_path_inside(fd, target):
            return "not inside the roots", (f"{target.display}: the file that was opened is not inside any root by "
                                            "its real path (a link was swapped in while it was opened); not read")
        problem = self.link_problem(st, target, names)
        if problem:
            return "hard link", problem
        if stat.S_ISREG(st.st_mode) and st.st_nlink > 1:
            now = os.fstat(fd)
            if (now.st_nlink, now.st_ctime_ns) != (st.st_nlink, st.st_ctime_ns):
                return "hard link", (f"{target.display}: its names changed while they were being counted; not read "
                                     "(read it again)")
        return None

    def real_path_inside(self, fd: int, target: Target) -> bool:
        real = real_path(fd, target.abspath)
        return real is not None and self.display_of(real) is not None

    def link_problem(self, st, target: Target, names=None) -> str | None:
        """None if every name of the file `st` describes is inside the roots and may be read there, else why not.

        A regular file with one link has only the name the model used, which the walk has already checked. With
        more, link(2): "it is impossible to tell which name was the 'original'", so a name outside the roots may be
        the file's real home (a key, a password file), and the roots are searched for the others."""
        if not stat.S_ISREG(st.st_mode) or st.st_nlink <= 1:
            return None
        found, stopped = names() if names is not None else self.names_in_roots(ident(st), st.st_nlink)
        have = len(found.get(ident(st), ()))
        if have >= st.st_nlink:
            return None
        if stopped:
            return (f"{target.display} has {st.st_nlink} names (hard links), and the search of the roots for them "
                    f"stopped {stopped} with {have} found; a file with more than one name is read only when every "
                    "name is found inside the roots, so it is not read")
        return (f"{target.display} has {st.st_nlink} names (hard links) and only {have} of them are inside the roots "
                "under a name that may be read: the file is also reached from outside the roots or through a secret "
                "name, so it is not read")

    def names_in_roots(self, want: tuple | None = None, need: int = 0) -> tuple[dict, str | None]:
        """({(st_dev, st_ino): {(directory identity, name), ...}}, None or where the search stopped).

        The names inside the roots, that the model could read itself (not secret by name, not below a secret or
        hidden directory, no link followed on the way), of the regular file `want`, or with want None of every
        regular file there with more than one link. A directory is walked once (by identity) and a name is its
        directory's identity and its spelling, so a directory two roots share (one inside the other) counts its
        names once. With want, the search ends as soon
        as `need` names are found. Past link_scan_entries entries or link_scan_seconds it stops and says so, and
        what it found is then incomplete: a caller refuses rather than trust the count."""
        found: dict = {}
        seen: set = set()
        count = 0
        deadline = time.monotonic() + self.link_scan_seconds

        def over() -> str | None:
            if count > self.link_scan_entries:
                return f"after {self.link_scan_entries} entries"
            if time.monotonic() > deadline:
                return f"after {self.link_scan_seconds:g} s"
            return None

        for root in self.roots:
            walker = _root_dirs(root)
            try:
                for did, rel, files, lstat_file, dirnames in walker:
                    count += 1
                    if over():
                        return found, over()
                    if did in seen or did in self.secret_ids or did in self.hidden_ids:
                        dirnames[:] = []                 # walked already, or nothing below is the model's to read
                        continue
                    seen.add(did)
                    for name in files:
                        count += 1
                        if over():
                            return found, over()
                        try:
                            st = lstat_file(name)
                        except OSError:
                            continue
                        if not stat.S_ISREG(st.st_mode):
                            continue
                        i = ident(st)
                        if (i != want) if want is not None else st.st_nlink < 2:
                            continue
                        if self.secret_reason(Target(root, rel + (name,))):
                            continue
                        names = found.setdefault(i, set())
                        names.add((did, name))
                        if want is not None and len(names) >= need:
                            return found, None
            except OSError as e:
                return found, f"at root {root.name} ({e.strerror or e})"
            finally:
                walker.close()
        return found, None


# ---------------------------------------------------------- handle helpers --
# A handle is a directory descriptor (int) on POSIX, a checked directory path (str) elsewhere.

def close(handle) -> None:
    if isinstance(handle, int):
        try:
            os.close(handle)
        except OSError:
            pass


def lstat_child(handle, name: str):
    if isinstance(handle, int):
        return os.stat(name, dir_fd=handle, follow_symlinks=False)
    return os.lstat(os.path.join(handle, name))


def fstat_dir(handle):
    return os.fstat(handle) if isinstance(handle, int) else os.lstat(handle)


def open_child(handle, name: str, flags: int, mode: int = 0o666) -> int:
    """os.open of one entry of a directory handle, never following a link in that last component."""
    if isinstance(handle, int):
        return os.open(name, flags | O_NOFOLLOW | O_CLOEXEC, mode, dir_fd=handle)
    path = os.path.join(handle, name)
    try:
        st = os.lstat(path)
        if _is_link(st):
            raise OSError(errno.ELOOP, "is a symbolic link", path)
    except FileNotFoundError:
        if not flags & os.O_CREAT:
            raise
    return os.open(path, flags | O_BINARY, mode)


def rename_child(handle, src: str, dst: str) -> None:
    if isinstance(handle, int):
        os.rename(src, dst, src_dir_fd=handle, dst_dir_fd=handle)
    else:
        os.replace(os.path.join(handle, src), os.path.join(handle, dst))


def unlink_child(handle, name: str) -> None:
    if isinstance(handle, int):
        os.unlink(name, dir_fd=handle)
    else:
        os.unlink(os.path.join(handle, name))


def scandir(handle):
    return os.scandir(handle)


def real_path(fd: int, fallback: str) -> str | None:
    """The real path of an open file: where the kernel says the descriptor is (/proc/self/fd/N, "a symbolic link to
    the actual file", proc_pid_fd(5)), else os.path.realpath of the path it was opened by."""
    if _PROC_FD:
        try:
            return os.readlink(f"/proc/self/fd/{fd}")
        except OSError:
            pass
    try:
        return os.path.realpath(fallback)
    except (OSError, ValueError):
        return None


def _root_dirs(root: Root):
    """(identity, parts below the root, file names, an lstat of one of them by name, subdirectory names) for each
    directory of a root, top-down, no link followed: os.fwalk with follow_symlinks=False where the platform has
    descriptor calls, os.walk otherwise. Emptying the subdirectory list prunes. A root replaced since it was
    configured raises OSError, as does a directory that cannot be examined."""
    if FD_WALK:
        rfd = os.open(root.path, os.O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
        try:
            if root.ident and ident(os.fstat(rfd)) != tuple(root.ident):
                raise OSError(errno.ESTALE, "replaced since it was configured")
            walker = os.fwalk(".", dir_fd=rfd, follow_symlinks=False)
            try:
                for dirpath, dirnames, filenames, dfd in walker:
                    rel = () if dirpath == "." else tuple(dirpath[2:].split("/"))
                    yield (ident(os.fstat(dfd)), rel, filenames,
                           lambda n, d=dfd: os.stat(n, dir_fd=d, follow_symlinks=False), dirnames)
            finally:
                walker.close()
        finally:
            os.close(rfd)
        return
    if root.ident and ident(os.lstat(root.path)) != tuple(root.ident):
        raise OSError(errno.ESTALE, "replaced since it was configured")
    for dirpath, dirnames, filenames in os.walk(root.path, followlinks=False):
        rel = tuple(p for p in os.path.relpath(dirpath, root.path).split(os.sep) if p not in ("", "."))
        st = os.lstat(dirpath)
        if _is_link(st):
            dirnames[:] = []
            continue
        yield ident(st), rel, filenames, lambda n, d=dirpath: os.lstat(os.path.join(d, n)), dirnames


def is_regular(st) -> bool:
    return stat.S_ISREG(st.st_mode)


def is_dir(st) -> bool:
    return stat.S_ISDIR(st.st_mode) and not _is_link(st)


def is_link(st) -> bool:
    return _is_link(st)


def kind(st) -> str:
    if _is_link(st):
        return "link"
    if stat.S_ISDIR(st.st_mode):
        return "dir"
    if stat.S_ISREG(st.st_mode):
        return "file"
    if stat.S_ISFIFO(st.st_mode):
        return "fifo"
    if stat.S_ISSOCK(st.st_mode):
        return "socket"
    if stat.S_ISCHR(st.st_mode) or stat.S_ISBLK(st.st_mode):
        return "device"
    return "other"


# ------------------------------------------------------------ configuration --

def make_root(name: str, path: str, write: bool = False) -> Root:
    """A root from the operator's configuration, resolved once (the operator's own links are theirs to follow)."""
    if not isinstance(name, str) or not ROOT_NAME.match(name) or name in (".", ".."):
        raise ValueError(f"root name {name!r} is not 1-64 of A-Za-z0-9_.- (not starting with . or -)")
    real = os.path.realpath(os.path.expanduser(path))
    try:
        st = os.stat(real)
    except OSError as e:
        raise ValueError(f"root {name}: {path} cannot be used: {e.strerror}") from None
    if not stat.S_ISDIR(st.st_mode):
        raise ValueError(f"root {name}: {path} is not a directory")
    return Root(name, real, bool(write), ident(st))


def identities(paths, *, max_files: int = 2000, recurse: bool = False) -> set:
    """(st_dev, st_ino) of each existing path, and, with recurse, of the files below a directory (bounded)."""
    out = set()
    for p in paths:
        try:
            st = os.stat(p)
        except (OSError, ValueError):
            continue
        out.add(ident(st))
        if recurse and stat.S_ISDIR(st.st_mode):
            seen = 0
            for dirpath, dirnames, filenames in os.walk(p):
                for n in dirnames + filenames:
                    try:
                        out.add(ident(os.stat(os.path.join(dirpath, n), follow_symlinks=False)))
                    except OSError:
                        continue
                    seen += 1
                    if seen >= max_files:
                        break
                if seen >= max_files:
                    break
    return out


def home_secret_identities(home, names, *, skip=(), devices=(), max_entries: int = HOME_SCAN_ENTRIES,
                           seconds: float = HOME_SCAN_SECONDS) -> tuple[set, dict]:
    """(identities, what the scan covered): (st_dev, st_ino) of every entry anywhere under the home directory that
    one of `names` names, by exact spelling or by glob (case-insensitively, like secret_reason; a name with a `/`
    is matched against the path from the home directory, like `.config/gh`), and of everything below a matching
    directory: the identity twin of the by-name check, so a hard link into a root under an innocent name is
    refused even when that name is not on the list (CWE-59 and CWE-62, cwe.mitre.org; stat(2): st_dev and st_ino
    identify a file whatever name reaches it).

    Breadth-first, like bfs (github.com/tavianator/bfs: "lists files from shallowest to deepest"), so the caps cut
    the deepest levels and never a whole folder near the top, where a person's keys and credential files sit. It
    follows no link, does not descend into a directory in `skip` (the operator's roots: what is inside them is
    checked by name and at read time) or on a file system other than the home directory's and `devices`' (the
    roots'): POSIX find's -xdev, and a hard link cannot cross file systems (link(2), EXDEV), so nothing on another
    one can have a name inside a root. It stops after max_entries entries or `seconds`, and says so.

    The dict: entries and directories read, seconds, depth (the deepest level with an entry read; 1 is the home
    directory's own entries), whole_levels (every entry down to that level was read), stopped (None, or why)."""
    literal, globs, slashed = set(), [], []
    for n in names:
        n = n.casefold().strip("/")
        if "/" in n:
            slashed.append(n)
        elif re.search(r"[*?\[]", n):
            globs.append(n)
        elif n:
            literal.add(n)
    glob_re = re.compile("|".join(f"(?:{fnmatch.translate(g)})" for g in globs)) if globs else None
    slash_re = re.compile("|".join(f"(?:{fnmatch.translate(g)})" for g in slashed)) if slashed else None
    out: set = set()
    info = {"entries": 0, "directories": 0, "seconds": 0.0, "depth": 0, "whole_levels": 0, "stopped": None}
    started = time.monotonic()
    try:
        hst = os.stat(home)
    except (OSError, ValueError) as e:
        info["stopped"] = f"at the start: the home directory cannot be read ({getattr(e, 'strerror', None) or e})"
        return out, info
    allowed = {hst.st_dev} | set(devices)
    skip = set(skip)
    seen = {ident(hst)}
    queue = deque([(os.fspath(home), "", 0, False)])       # (path, from home casefolded, depth, below a secret)
    while queue and info["stopped"] is None:
        path, rel, depth, below = queue.popleft()
        info["whole_levels"] = depth                         # breadth-first: every level down to depth is read
        try:
            it = os.scandir(path)
        except OSError:
            continue
        info["directories"] += 1
        with it:
            for e in it:
                if info["entries"] >= max_entries:
                    info["stopped"] = f"after {max_entries} entries"
                    break
                if time.monotonic() - started > seconds:
                    info["stopped"] = f"after {seconds:g} s"
                    break
                info["entries"] += 1
                info["depth"] = max(info["depth"], depth + 1)
                name = e.name.casefold()
                r = f"{rel}/{name}" if rel else name
                secret = (below or name in literal or (glob_re is not None and glob_re.match(name) is not None)
                          or (slash_re is not None and slash_re.match(r) is not None))
                try:
                    is_dir = e.is_dir(follow_symlinks=False)
                    st = e.stat(follow_symlinks=False) if secret or is_dir else None
                    if secret and e.is_symlink():
                        # a secret name that is a link (dotfiles kept elsewhere, as GNU Stow does): what it points
                        # to is the secret, and a directory there is scanned like one found here
                        st = os.stat(e.path)
                        is_dir = stat.S_ISDIR(st.st_mode)
                except OSError:
                    continue
                if secret:
                    out.add(ident(st))
                if is_dir:
                    i = ident(st)
                    if i in skip or i in seen or st.st_dev not in allowed:
                        continue
                    seen.add(i)
                    queue.append((e.path, r, depth + 1, secret))
    if info["stopped"] is None:
        info["whole_levels"] = info["depth"]
    info["seconds"] = round(time.monotonic() - started, 3)
    return out, info
