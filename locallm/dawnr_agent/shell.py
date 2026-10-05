"""dawnr_agent/shell.py: any command, run for real over an overlay; what it changed is shown, and becomes real
only when the person approves it (2026-10-05).

The command allowlist (commands.py) is safe because it is short, and for the same reason it cannot rename a file.
`sh` runs whatever the model writes, a whole shell line, and is safe for another reason: where it runs.

  the sandbox   bubblewrap, as commands.py builds it: no network, its own process ids, the file system read-only,
                the secret folders hidden, and the Unix sockets found under the home folder masked (a socket can
                be connected to on a read-only file system; /run and /tmp, where most live, are empty here)
  the overlay   each writable root is mounted as an overlay over itself (bubblewrap's --overlay-src/--overlay): the
                command sees the folder and changes it freely, and every change lands in a directory of dawnr's own.
                The folder is not touched
  the changes   read back from that directory by the kernel's rules (Documentation/filesystems/overlayfs.rst): a file
                there is a file written, a character device 0/0 (or a file marked overlay.whiteout) a name removed,
                a directory marked opaque one replaced whole
  or a copy     bubblewrap mounts overlays from 0.11 on; Ubuntu 24.04 ships 0.9 and Debian 12 ships 0.8. There the
                folder is copied, the command runs with the copy in the folder's place, and the changes are the
                differences between the two. The same sandbox, the same question to the person, slower, and only
                for a folder of at most 256 MB and 20,000 files
  the decision  a command that changed nothing was a read, and its output is returned. One that changed something is
                asked for, with the changes it made as the reason: the person approves effects, not a command line
  not caches    what a tool writes into its own cache folder as it runs (__pycache__, .pytest_cache, .mypy_cache,
                .ruff_cache) is neither shown nor kept: running the tests changes nothing
  applying      through the journaled file operations (files.py), so every file changed or removed can be put back;
                refused if a file moved since the command ran

The idea is `try`'s (github.com/binpash/try, MIT, OSDI'26): run the command over an overlay, look, then commit or
not. try overlays the whole system and leaves the network open, and says it is not a sandbox; here only the folder
is overlaid, inside one. Research receipt d24c962e67be.

What this does not do. A command's effects that are not files in the folder do not exist: it cannot install a
package, change a setting or start a program that outlives it; those are asked for another way. Links, devices and
files over the journal's size limit are listed and not applied. A file the file tools never read (a key, a
`.env`) is not there for the command either. Where bubblewrap does not work at all (macOS, Windows without WSL, a
system that forbids user namespaces), the tool is not offered.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import paths
from .commands import HIDE_UNDER_HOME, base_env, run_argv
from .system import SECRET
from .files import FileOps, Preview
from .journal import sha256
from .paths import DEFAULT_SECRETS, PathRefused, Space, Target
from dawnr_harness.tools import CallContext, Tool, ToolResult

MAX_COMMAND = 4000             # characters of one shell line
MAX_CHANGES = 400              # files one command may change and still be applied (each is kept for undo)
COPY_BYTES = 256 * 1024 * 1024  # where there is no overlay: the largest folder a command is run over a copy of
COPY_FILES = 20_000
KEPT = 4                       # runs kept waiting for an answer; older ones are dropped
KEPT_OUTPUT = 200_000          # bytes of a command's output read at all; the model is shown the start and the end of it
ORDER = {"mkdir": 0, "write": 1, "delete": 2, "rmdir": 3, "skip": 4}
# what a tool writes for itself when it runs: never shown and never kept, so running a test is not a change (try
# leaves the same to the person, `-E PATTERN`: "exclude paths that match PATTERN on summary and commit"; receipt
# 3b9ab2c6cefa). Removing one of these is still a change like any other
CACHES = ("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache")
# programs that report on the running machine. In here they would report on the sandbox (its own processes, no
# network, no session) and the answer would be wrong, not missing: so, where `sysinfo` can look, they are sent there
LIVE = re.compile(r"(?:^|[;&|]\s*)(ps|pgrep|pidof|top|htop|ip|ss|nmcli|iwgetid|systemctl|journalctl|loginctl|timedatectl|"
                  r"hostnamectl|pactl|wpctl|amixer|playerctl|brightnessctl|bluetoothctl|rfkill|upower|xrandr|nvidia-smi|"
                  r"gsettings|dconf|xdg-open|notify-send|gio|shutdown|reboot|poweroff|plasma-apply-colorscheme|ktrash[56]?)\b")
# what a command sees in the place of a folder or a file that is hidden from it: not an empty one. An empty `~/.ssh`
# was reported to the person as "there are no SSH private keys in your ~/.ssh directory"
HIDDEN_FOLDER = "This folder is hidden from every command dawnr runs. It is not empty on the computer: what is in it is not shown.\n"
# In a repository a secret file's text is also in .git, under no name: `git diff` and `git log -p` would print it.
# Inside the sandbox git is told these names are binary, so it says that they differ and not how
GIT_ATTRIBUTES = "".join(f"{name} binary\n{name}/** binary\n" for name in sorted(DEFAULT_SECRETS))
HIDDEN_FILE = "# hidden by dawnr: this file is on the computer, and its contents are not shown to any command\n"
# said after the output of a command that ran into the sandbox's walls, so that they are not taken for the computer's
NOTES = [(re.compile(r"Read-only file system"),
          "[Only the folder can be changed from here: everything outside it is read-only in this sandbox, and stays so. "
          "If what was asked for is outside the folder, it was not done: say so.]"),
         (re.compile(r"Could not resolve host|Temporary failure in name resolution|Network is unreachable|Name or service not known"),
          "[`sh` has no network, whatever the computer's own connection is.]")]


def _kept(changes: list) -> list:
    return [c for c in changes if c.kind in ("delete", "rmdir") or not any(part in CACHES for part in c.path.split("/"))]


@dataclass
class Change:
    kind: str                  # write | delete | mkdir | rmdir | skip
    path: str                  # as the file tools write it: root/relative
    data: bytes | None = None
    mode: int | None = None
    before: str | None = None  # the real file's sha256 when the command ran; None when it was not there
    why: str = ""              # for a skip: why it is not applied

    def line(self) -> str:
        if self.kind == "skip":
            return f"not applied: {self.path} ({self.why})"
        what = {"write": "create" if self.before is None else "change", "delete": "remove", "mkdir": "new folder",
                "rmdir": "remove folder"}[self.kind]
        return f"{what} {self.path}"


@dataclass
class Run:
    id: str
    command: str
    cwd: str
    exit: int | None
    seconds: float
    timed_out: bool
    stdout: str
    stderr: str
    changes: list = field(default_factory=list)
    scratch: str = ""
    shown: bool = False        # its changes were put to the harness as the reason to ask
    applied: bool = False
    refused: str = ""          # why none of its changes can be made real (it changed the repository itself)

    @property
    def real(self) -> list:
        return [c for c in self.changes if c.kind != "skip"]

    def summary(self) -> str:
        if not self.changes:
            return "it changed nothing"
        lines = [c.line() for c in self.changes]
        return f"it would change {len(self.real)}: " + "; ".join(lines[:12]) + (f"; and {len(lines) - 12} more" if len(lines) > 12 else "")

    def output(self, limit: int) -> str:
        head = (f"timed out after {self.seconds:.0f} s" if self.timed_out else f"exit {self.exit}")
        text = self.stdout.rstrip("\n")
        if self.stderr.strip():
            text += ("\n" if text else "") + "[stderr]\n" + self.stderr.rstrip("\n")
        if len(text) > limit:                                   # the start and the end: an error is usually the last line
            first, last = text[:limit * 3 // 5], text[-(limit * 2 // 5):]
            cut = text[len(first):len(text) - len(last)]
            text = f"{first}\n[{cut.count(chr(10)) + 1} lines ({len(cut)} characters) not shown]\n{last}"
        return head + ("\n" + text if text else "")


def _xattr(path: str, name: str) -> bytes | None:
    for space in ("user", "trusted"):
        try:
            return os.getxattr(path, f"{space}.overlay.{name}", follow_symlinks=False)
        except (OSError, AttributeError):
            continue
    return None


def _force_remove(path: str) -> None:
    """Remove a run's scratch directory. The overlay leaves a work directory with no permissions at all, so each
    directory is opened up before it is entered."""
    try:
        os.chmod(path, 0o700)
        with os.scandir(path) as it:
            entries = list(it)
    except OSError:
        entries = []
    for e in entries:
        if e.is_dir(follow_symlinks=False):
            _force_remove(e.path)
        else:
            try:
                os.unlink(e.path)
            except OSError:
                pass
    try:
        os.rmdir(path)
    except OSError:
        pass


def home_sockets(home: str, skip: list, entries: int = 150_000, seconds: float = 1.0) -> list:
    """The Unix sockets under the home folder, outside `skip`: a listener there is a way out of the sandbox that
    the read-only file system does not close (connecting to a socket is allowed on a read-only mount; a command in
    the sandbox reached one and wrote to it, 2026-10-05). The search is breadth-first and bounded."""
    found, queue, seen, started = [], [home], 0, time.monotonic()
    skip = [os.path.realpath(p) for p in skip]
    while queue and seen < entries and time.monotonic() - started < seconds:
        at = queue.pop(0)
        try:
            with os.scandir(at) as it:
                for e in it:
                    seen += 1
                    try:
                        if e.is_symlink():
                            continue
                        if e.is_dir(follow_symlinks=False):
                            if os.path.realpath(e.path) not in skip:
                                queue.append(e.path)
                        elif stat.S_ISSOCK(e.stat(follow_symlinks=False).st_mode):
                            found.append(e.path)
                    except OSError:
                        continue
        except OSError:
            continue
    return found


class ShellTools:
    def __init__(self, space: Space, ops: FileOps, *, program: str, state: Path, exec_path: str, env: dict | None = None,
                 timeout: float = 60.0, max_output: int = 4_000, hide: list | None = None):
        self.space, self.ops, self.program = space, ops, program
        self.scratch = Path(state) / "sh"
        self.env = {**base_env(exec_path), "TMPDIR": "/tmp", **(env or {})}
        self.timeout, self.max_output = timeout, max_output
        self.elsewhere = ""                                     # where a look at the running computer is sent, if anywhere
        self.markers = Path(state) / "sh-hidden"                # what stands in a hidden folder's and a hidden file's place
        self.env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.attributesFile", GIT_CONFIG_VALUE_0="/run/dawnr-gitattributes")
        home = os.path.expanduser("~")
        # where a secret folder is a link (~/.ssh kept on another volume), what is hidden is where the link leads
        self.hide = sorted({os.path.realpath(p) for p in (hide if hide is not None else [os.path.join(home, h) for h in HIDE_UNDER_HOME])
                            if os.path.lexists(p)})
        self.roots = [r for r in space.roots if r.write]
        self.sockets = home_sockets(home, [r.path for r in space.roots] + self.hide) if os.path.isdir(home) else []
        self.runs: dict[str, Run] = {}
        self._lock = threading.Lock()
        self.mode = "overlay"                                   # or "copy", where bubblewrap cannot mount an overlay
        self.problem = self.probe()

    # ------------------------------------------------------------ the sandbox --

    def _secrets(self) -> tuple[list, list]:
        """(files, folders) inside the roots that the file tools never read: a command does not read them either."""
        files, dirs, seen = [], [], 0
        for r in self.space.roots:
            for at, dnames, fnames in os.walk(r.path):
                rel = os.path.relpath(at, r.path)
                parts = () if rel == "." else tuple(rel.split(os.sep))
                for d in list(dnames):
                    if self.space.secret_reason(Target(r, parts + (d,))):
                        dirs.append(os.path.join(at, d))
                        dnames.remove(d)
                files += [os.path.join(at, f) for f in fnames if self.space.secret_reason(Target(r, parts + (f,)))]
                seen += len(dnames) + len(fnames)
                if seen > 50_000:
                    break
        return files, dirs

    def _markers(self) -> tuple[str, str]:
        folder, file = self.markers / "folder", self.markers / "file"
        if not file.is_file():
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "hidden-by-dawnr").write_text(HIDDEN_FOLDER)
            (self.markers / "gitattributes").write_text(GIT_ATTRIBUTES)
            file.write_text(HIDDEN_FILE)
        return str(folder), str(file)

    def _argv(self, command: list, cwd: str, layers: dict) -> list:
        a = [self.program, "--die-with-parent", "--new-session", "--unshare-all",
             "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp", "--tmpfs", "/run"]
        no_folder, no_file = self._markers()
        a += ["--ro-bind", str(self.markers / "gitattributes"), "/run/dawnr-gitattributes"]
        for h in self.hide:
            if os.path.isdir(h) and not os.path.islink(h):
                a += ["--ro-bind", no_folder, h]
            elif os.path.isfile(h) and not os.path.islink(h):
                a += ["--ro-bind", no_file, h]
        for sock in self.sockets:                               # nothing listens behind these inside the sandbox
            if os.path.lexists(sock):
                a += ["--ro-bind", "/dev/null", sock]
        for root, (upper, work) in layers.items():
            a += ["--overlay-src", root, "--overlay", upper, work, root] if work else ["--bind", upper, root]
        files, dirs = self._secrets()
        copied = [root for root, (_u, work) in layers.items() if not work]
        for path in files + dirs:                               # a copy was made without them; elsewhere they are masked
            if not any(path.startswith(root.rstrip("/") + "/") for root in copied):
                a += ["--ro-bind", no_folder if path in dirs else no_file, path]
        for r in self.roots:                                    # the file tools call the folder by its name: so may a command
            if (r.path in layers and not os.path.lexists(os.path.join(r.path, r.name))      # (not in a repository, where
                    and not os.path.lexists(os.path.join(r.path, ".git"))):                 # git would report the link)
                a += ["--symlink", ".", os.path.join(r.path, r.name)]
        return a + ["--chdir", cwd, "--"] + command

    def _copy(self, root, to: Path) -> None:
        """The folder, copied for a command to run over: links as links, no secret, nothing that is not a file or a
        folder. Refused over COPY_BYTES or COPY_FILES."""
        files, dirs = self._secrets()
        secret = set(files) | set(dirs)
        count = size = 0
        for at, dnames, fnames in os.walk(root.path):
            target = to / os.path.relpath(at, root.path)
            target.mkdir(parents=True, exist_ok=True)
            for d in [d for d in dnames if os.path.join(at, d) in secret]:      # its place is kept, and says it is hidden
                (target / d).mkdir(exist_ok=True)
                (target / d / "hidden-by-dawnr").write_text(HIDDEN_FOLDER)
            dnames[:] = [d for d in dnames if os.path.join(at, d) not in secret]
            for d in list(dnames):
                if os.path.islink(os.path.join(at, d)):
                    os.symlink(os.readlink(os.path.join(at, d)), target / d)
                    dnames.remove(d)
            for name in fnames:
                path = os.path.join(at, name)
                if path in secret:
                    (target / name).write_text(HIDDEN_FILE)
                    continue
                st = os.lstat(path)
                count += 1
                if stat.S_ISLNK(st.st_mode):
                    os.symlink(os.readlink(path), target / name)
                elif stat.S_ISREG(st.st_mode):
                    size += st.st_size
                    if size > COPY_BYTES or count > COPY_FILES:
                        raise PathRefused(f"sh: this folder is over {COPY_BYTES >> 20} MB or {COPY_FILES} files, too large to run a "
                                          "command over a copy of it; with bubblewrap 0.11 or newer no copy is needed")
                    shutil.copy2(path, target / name)
            try:
                shutil.copystat(at, target)
            except OSError:
                pass

    def _layers(self, scratch: Path) -> dict:
        layers = {}
        for i, r in enumerate(self.roots):
            if self.mode == "copy":
                self._copy(r, scratch / f"copy{i}")
                layers[r.path] = (str(scratch / f"copy{i}"), None)
                continue
            upper, work = scratch / f"upper{i}", scratch / f"work{i}"
            upper.mkdir(parents=True)
            work.mkdir(parents=True)
            layers[r.path] = (str(upper), str(work))
        return layers

    def _try(self) -> str | None:
        scratch = self.scratch / f"probe-{os.getpid()}"
        if scratch.exists():
            _force_remove(str(scratch))
        try:
            layers = {self.roots[0].path: ((str(scratch / "u"), str(scratch / "w")) if self.mode == "overlay" else (str(scratch / "c"), None))}
            for part in layers[self.roots[0].path]:
                if part:
                    Path(part).mkdir(parents=True)
            got = run_argv(self._argv(["true"], self.roots[0].path, layers), cwd=self.roots[0].path, env=self.env,
                           timeout=20, max_output=2000)
        finally:
            _force_remove(str(scratch))
        return None if got["exit"] == 0 else (got["stderr"].strip()[:200] or f"exit {got['exit']}")

    def probe(self) -> str | None:
        """None if a command can be run here over an overlay or, failing that, over a copy; else why not."""
        if not self.roots:
            return "no folder here may be changed"
        if os.name == "nt":
            return "the sandbox is bubblewrap, a Linux program"
        forced = os.environ.get("DAWNR_SH_MODE")
        try:
            self.scratch.mkdir(parents=True, exist_ok=True, mode=0o700)
            why = "overlay switched off"
            if forced != "copy" and hasattr(os, "getxattr"):
                self.mode = "overlay"
                why = self._try()
                if why is None:
                    return None
            if forced == "overlay":
                return "bubblewrap cannot mount an overlay here: " + why
            self.mode = "copy"
            again = self._try()
        except OSError as e:
            return f"the sandbox could not start: {e}"
        return None if again is None else f"bubblewrap does not work here: {again}"

    # --------------------------------------------------------- reading a run --

    def _real(self, root, rel: str) -> str:
        return os.path.join(root.path, rel) if rel else root.path

    def _removed(self, root, rel: str, out: list) -> None:
        """The changes that remove what is really at root/rel: a file, or a folder and all under it."""
        real = self._real(root, rel)
        try:
            st = os.lstat(real)
        except OSError:
            return                                              # made and removed within the run
        display = f"{root.name}/{rel}"
        if stat.S_ISDIR(st.st_mode):
            for sub in sorted(os.listdir(real)):
                self._removed(root, f"{rel}/{sub}", out)
            out.append(Change("rmdir", display))
        elif stat.S_ISREG(st.st_mode):
            out.append(self._checked(Change("delete", display)))
        else:
            out.append(Change("skip", display, why="it is not a regular file, so it is not removed"))

    def _checked(self, change: Change) -> Change:
        """The change with the real file's hash, or as a skip when the file tools would refuse it."""
        try:
            target = self.space.resolve(change.path)
            self.space.check_names(target, write=True)
            now = self.ops.current(target)
        except PathRefused as e:
            return Change("skip", change.path, why=str(e))
        if change.kind == "delete" and now is None:
            return Change("skip", change.path, why="it is not there")
        if change.kind == "write" and change.data is not None and len(change.data) > self.ops.limits.max_write_bytes:
            return Change("skip", change.path, why=f"over {self.ops.limits.max_write_bytes} bytes, too large to keep for undo")
        change.before = sha256(now) if now is not None else None
        return change

    def _read_upper(self, root, upper: str) -> list:
        out: list = []
        for at, dirs, files in os.walk(upper):
            rel_dir = os.path.relpath(at, upper)
            rel_dir = "" if rel_dir == "." else rel_dir
            for name in sorted(dirs) + sorted(files):
                path = os.path.join(at, name)
                rel = f"{rel_dir}/{name}" if rel_dir else name
                display = f"{root.name}/{rel}"
                st = os.lstat(path)
                real = self._real(root, rel)
                if stat.S_ISCHR(st.st_mode) and st.st_rdev == 0 or (
                        stat.S_ISREG(st.st_mode) and st.st_size == 0 and _xattr(path, "whiteout") is not None):
                    self._removed(root, rel, out)
                elif stat.S_ISLNK(st.st_mode):
                    if rel == root.name and os.readlink(path) == ".":
                        continue                                # the sandbox's own name for the folder (_argv)
                    out.append(Change("skip", display, why="a link is not applied"))
                elif stat.S_ISDIR(st.st_mode):
                    real_is_dir = os.path.isdir(real) and not os.path.islink(real)
                    if not real_is_dir:
                        if os.path.lexists(real):
                            self._removed(root, rel, out)
                        out.append(Change("mkdir", display))
                    elif _xattr(path, "opaque") == b"y":         # replaced whole: what the run did not put back is gone
                        for sub in sorted(set(os.listdir(real)) - set(os.listdir(path))):
                            self._removed(root, f"{rel}/{sub}", out)
                elif stat.S_ISREG(st.st_mode):
                    if st.st_size > self.ops.limits.max_write_bytes:
                        out.append(Change("skip", display, why=f"over {self.ops.limits.max_write_bytes} bytes, too large to keep for undo"))
                        continue
                    with open(path, "rb") as f:
                        data = f.read()
                    change = self._checked(Change("write", display, data=data, mode=stat.S_IMODE(st.st_mode)))
                    if change.kind == "write" and change.before == sha256(data):
                        try:
                            same_mode = stat.S_IMODE(os.lstat(real).st_mode) == change.mode
                        except OSError:
                            same_mode = False
                        if same_mode:
                            continue                            # opened for writing and left as it was
                    out.append(change)
                else:
                    out.append(Change("skip", display, why="it is not a regular file"))
        return sorted(_kept(out), key=lambda c: (ORDER[c.kind], -c.path.count("/") if c.kind == "rmdir" else c.path.count("/"), c.path))

    def _read_copy(self, root, copy: str) -> list:
        """What a command changed, where it ran over a copy: the differences between the copy and the folder."""
        out: list = []
        files, dirs = self._secrets()
        secret = set(files) | set(dirs)
        for at, dnames, fnames in os.walk(copy):
            rel_dir = os.path.relpath(at, copy)
            rel_dir = "" if rel_dir == "." else rel_dir
            dnames[:] = [d for d in dnames if self._real(root, f"{rel_dir}/{d}" if rel_dir else d) not in secret]
            for name in sorted(dnames) + sorted(fnames):
                path = os.path.join(at, name)
                rel = f"{rel_dir}/{name}" if rel_dir else name
                display, real = f"{root.name}/{rel}", self._real(root, rel)
                if real in secret:
                    continue                                    # a secret's place in the copy is not the secret, changed
                st = os.lstat(path)
                if stat.S_ISLNK(st.st_mode):
                    if rel == root.name and os.readlink(path) == ".":
                        continue                                # the sandbox's own name for the folder (_argv)
                    if not (os.path.islink(real) and os.readlink(real) == os.readlink(path)):
                        out.append(Change("skip", display, why="a link is not applied"))
                elif stat.S_ISDIR(st.st_mode):
                    if not (os.path.isdir(real) and not os.path.islink(real)):
                        if os.path.lexists(real):
                            self._removed(root, rel, out)
                        out.append(Change("mkdir", display))
                elif stat.S_ISREG(st.st_mode):
                    if st.st_size > self.ops.limits.max_write_bytes:
                        try:
                            was = os.lstat(real)
                            same = (was.st_size, was.st_mtime_ns) == (st.st_size, st.st_mtime_ns)
                        except OSError:
                            same = False
                        if not same:
                            out.append(Change("skip", display, why=f"over {self.ops.limits.max_write_bytes} bytes, too large to keep for undo"))
                        continue
                    with open(path, "rb") as f:
                        data = f.read()
                    try:                                        # as it was: not a change, whatever the file (a protected
                        was = os.lstat(real)                    # one, which _checked would list as "not applied", too)
                        if (stat.S_ISREG(was.st_mode) and was.st_size == len(data) and stat.S_IMODE(was.st_mode) == stat.S_IMODE(st.st_mode)
                                and Path(real).read_bytes() == data):
                            continue
                    except OSError:
                        pass
                    change = self._checked(Change("write", display, data=data, mode=stat.S_IMODE(st.st_mode)))
                    out.append(change)
                else:
                    out.append(Change("skip", display, why="it is not a regular file"))
        for at, dnames, fnames in os.walk(root.path):               # what the folder has and the copy no longer does
            dnames[:] = [d for d in dnames if os.path.join(at, d) not in secret]
            rel_dir = os.path.relpath(at, root.path)
            rel_dir = "" if rel_dir == "." else rel_dir
            for name in sorted(dnames) + sorted(fnames):
                if os.path.join(at, name) in secret:
                    continue
                rel = f"{rel_dir}/{name}" if rel_dir else name
                if not os.path.lexists(os.path.join(copy, rel)):
                    self._removed(root, rel, out)
                    if name in dnames:
                        dnames.remove(name)
        return sorted(_kept(out), key=lambda c: (ORDER[c.kind], -c.path.count("/") if c.kind == "rmdir" else c.path.count("/"), c.path))

    # ---------------------------------------------------------------- running --

    def _key(self, args: dict) -> str:
        return hashlib.sha256(repr((args.get("command"), args.get("cwd"))).encode()).hexdigest()[:16]

    def _cwd(self, value) -> tuple[str, str]:
        if not value:
            return self.roots[0].path, self.roots[0].name
        target = self.space.resolve(str(value))
        real = os.path.join(target.root.path, *target.parts)
        if not os.path.isdir(real) or os.path.islink(real):
            raise PathRefused(f"{target.display} is not a folder")
        return real, target.display

    def run(self, args: dict) -> Run:
        """The command, run over the overlay; the same call again answers from the run already made."""
        command = args.get("command")
        if not isinstance(command, str) or not command.strip():
            raise PathRefused("sh: give the command as one line of text")
        if len(command) > MAX_COMMAND:
            raise PathRefused(f"sh: the command is over {MAX_COMMAND} characters")
        if self.problem:
            raise PathRefused(f"sh: no command runs here: {self.problem}")
        secret = SECRET.search(command)
        if secret:
            raise PathRefused(f"sh: this line names `{secret.group(1)}`, a place where secrets are kept. No command here sees "
                              "such a place (it looks hidden or missing, and is neither), and dawnr does not read or pass on "
                              "what is in it. Say so")
        live = LIVE.search(command.split("\n", 1)[0].split("<<", 1)[0]) if self.elsewhere else None
        if live:
            raise PathRefused(f"sh: `{live.group(1)}` reports on the running computer, and `sh` runs in a sandbox that does not "
                              f"see it (its own processes, no network, no desktop session). {self.elsewhere}")
        key = self._key(args)
        with self._lock:
            kept = self.runs.get(key)
            if kept is not None and not kept.applied:
                return kept
            cwd, shown = self._cwd(args.get("cwd"))
            scratch = self.scratch / f"{key}-{int(time.time() * 1000)}"
            layers = self._layers(scratch)
            shell = shutil.which("bash", path=self.env["PATH"]) or "/bin/sh"
            got = run_argv(self._argv([shell, "-c", command], cwd, layers), cwd=self.roots[0].path, env=self.env,
                           timeout=self.timeout, max_output=KEPT_OUTPUT)
            changes: list = []
            for root in self.roots:
                changes += (self._read_copy if self.mode == "copy" else self._read_upper)(root, layers[root.path][0])
            # A repository's own folder is never written by the journal. `git status` refreshes .git/index there and
            # means nothing by it: that is dropped. Anything else in .git (a commit's objects, a branch, a stash) cannot
            # be carried out of the sandbox, and carrying out the rest without it would leave the two disagreeing (a
            # stash that reverted the files and was not kept): none of such a run is made real
            in_git = [c for c in changes if ".git" in c.path.split("/")[1:]]
            refused = ""
            if in_git and all(c.path.endswith("/.git/index") for c in in_git):
                changes = [c for c in changes if c not in in_git]
            elif in_git:
                refused = ("sh: this command changes the repository itself (the .git folder), and that cannot be carried out "
                           "of the sandbox it ran in; nothing it did was kept. "
                           + ("To stage, commit, switch branch or stash, call `pc` with the git line: it is shown to the person "
                              "and runs on the repository itself." if "`pc`" in self.elsewhere else "It is not done from here."))
            run = Run(key, command, shown, got["exit"], got["seconds"], got["timed_out"], got["stdout"], got["stderr"],
                      changes, str(scratch), refused=refused)
            self.runs[key] = run
            for old in list(self.runs)[:-KEPT]:
                _force_remove(self.runs.pop(old).scratch)
            return run

    def decide(self, args: dict) -> tuple[str, str]:
        """allow when the run changed nothing; ask, with what it changed, when it did."""
        try:
            run = self.run(args)
        except PathRefused as e:
            return "deny", str(e)
        if run.refused:
            return "deny", run.refused
        if not run.changes:
            return "allow", f"the command changed nothing (it ran over {'a copy' if self.mode == 'copy' else 'an overlay'}, in a sandbox with no network)"
        if len(run.real) > MAX_CHANGES:
            return "deny", f"the command changes {len(run.real)} files, more than the {MAX_CHANGES} that are kept for undo"
        run.shown = True
        return "ask", run.summary()

    def preview(self, args: dict, overlay: dict | None = None) -> Preview:
        if overlay:
            return Preview(error="an earlier step of this plan changes files, and this command has to see them: "
                                 "send it in a plan of its own, after that one has run")
        try:
            run = self.run(args)
        except PathRefused as e:
            return Preview(error=str(e))
        if run.refused:
            return Preview(error=run.refused)
        detail = [f"$ {run.command}    (in {run.cwd}; {run.output(400).splitlines()[0]})"] + ["  " + c.line() for c in run.changes]
        writes = {}
        for c in run.real:
            target = self.space.resolve(c.path)
            if c.kind in ("write", "delete"):
                writes[(target.root.name, tuple(target.parts))] = c.data if c.kind == "write" else None
        return Preview(summary=f"ran `{run.command[:120]}` in a sandbox, over a copy: {run.summary()}; its output "
                               "enters as untrusted data", detail=detail, writes=writes or None)

    def apply(self, run: Run, session: str = "") -> list[str]:
        """Make a run's changes real, each through the journal. Stops at the first file that moved since."""
        done = []
        extra = {"group": run.id, "command": run.command[:200]}
        for c in run.real:
            target = self.space.resolve(c.path)
            if c.kind == "mkdir":
                if self.ops.make_dir(target, session=session, extra=extra) is not None:
                    done.append(c.line())
                continue
            if c.kind == "rmdir":
                self.ops.remove_dir(target, session=session, extra=extra)
                done.append(c.line())
                continue
            now = self.ops.current(target)
            if (sha256(now) if now is not None else None) != c.before:
                raise PathRefused(f"{c.path} changed since the command ran; {len(done)} of {len(run.real)} changes were "
                                  "applied, the rest were not. Run the command again")
            if c.kind == "delete":
                self.ops.delete(target, action="sh", session=session, extra=extra)
            else:
                self.ops.write(target, c.data, create_only=now is None, expect=c.before, make_dirs=True, action="sh",
                               session=session, extra=extra)
                if c.mode is not None and (now is None or c.mode & 0o111):
                    self.ops.set_mode(target, c.mode)
            done.append(c.line())
        run.applied = True
        _force_remove(run.scratch)
        return done

    def sh(self, args: dict, ctx: CallContext) -> ToolResult:
        try:
            run = self.run(args)
            if run.refused:
                return ToolResult("refused: " + run.refused, is_error=True)
            text = run.output(self.max_output)
            text += "".join("\n" + note for pattern, note in NOTES if pattern.search(text))
            if run.changes and not run.shown:                   # nobody was shown these: they stay where they are
                return ToolResult(text + "\nNothing was applied: " + run.summary() + ". Send the same call again to have "
                                  "the changes shown and asked for.")
            if run.changes:
                done = self.apply(run, ctx.session.id if ctx is not None and ctx.session is not None else "")
                skipped = [c.line() for c in run.changes if c.kind == "skip"]
                text += f"\nApplied {len(done)} change{'s' if len(done) != 1 else ''}: " + "; ".join(done[:20])
                text += ("\n" + "\n".join(skipped[:10])) if skipped else ""
            else:
                with self._lock:
                    self.runs.pop(run.id, None)
                _force_remove(run.scratch)
            return ToolResult(text, is_error=bool(run.timed_out))
        except PathRefused as e:
            return ToolResult(str(e), is_error=True)

    def close(self) -> None:
        """Drop the runs nobody answered: their changes were never applied, and now cannot be."""
        with self._lock:
            for run in self.runs.values():
                _force_remove(run.scratch)
            self.runs = {}

    def tools(self) -> list[Tool]:
        schema = {"type": "object",
                  "properties": {"command": {"type": "string", "minLength": 1, "maxLength": MAX_COMMAND},
                                 "cwd": {"type": "string", "minLength": 1, "maxLength": paths.MAX_PATH}},
                  "required": ["command"], "additionalProperties": False}
        return [Tool("sh", "Run a shell command in the folder: mv, cp, rm, mkdir, wc, sort, grep, python3 and the like (no "
                           "network). It runs in a sandbox over a copy: files change only after the person approves "
                           "what it changed.",
                     schema, self.sh, permission="allow", trust="untrusted", network=False, consequential=False,
                     origin="agent", decide_call=self.decide)]
