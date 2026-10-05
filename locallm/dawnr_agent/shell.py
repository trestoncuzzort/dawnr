"""dawnr_agent/shell.py: any command, run for real over an overlay; what it changed is shown, and becomes real
only when the person approves it (2026-10-05).

The command allowlist (commands.py) is safe because it is short, and for the same reason it cannot rename a file.
`sh` runs whatever the model writes, a whole shell line, and is safe for another reason: where it runs.

  the sandbox   bubblewrap, as commands.py builds it: no network, its own process ids, the file system read-only,
                the secret folders hidden
  the overlay   each writable root is mounted as an overlay over itself (bubblewrap's --overlay-src/--overlay): the
                command sees the folder and changes it freely, and every change lands in a directory of dawnr's own.
                The folder is not touched
  the changes   read back from that directory by the kernel's rules (Documentation/filesystems/overlayfs.rst): a file
                there is a file written, a character device 0/0 (or a file marked overlay.whiteout) a name removed,
                a directory marked opaque one replaced whole
  the decision  a command that changed nothing was a read, and its output is returned. One that changed something is
                asked for, with the changes it made as the reason: the person approves effects, not a command line
  applying      through the journaled file operations (files.py), so every file changed or removed can be put back;
                refused if a file moved since the command ran

The idea is `try`'s (github.com/binpash/try, MIT, OSDI'26): run the command over an overlay, look, then commit or
not. try overlays the whole system and leaves the network open, and says it is not a sandbox; here only the folder
is overlaid, inside one. Research receipt d24c962e67be.

What this does not do. A command's effects that are not files in the folder do not exist: it cannot install a
package, change a setting or start a program that outlives it; those are asked for another way. Links, devices and
files over the journal's size limit are listed and not applied. Where bubblewrap or the overlay does not work
(Linux before 5.11, bubblewrap before 0.8, macOS, Windows without WSL), the tool is not offered.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import paths
from .commands import HIDE_UNDER_HOME, base_env, run_argv
from .files import FileOps, Preview
from .journal import sha256
from .paths import PathRefused, Space, Target
from dawnr_harness.tools import CallContext, Tool, ToolResult

MAX_COMMAND = 4000             # characters of one shell line
MAX_CHANGES = 400              # files one command may change and still be applied (each is kept for undo)
KEPT = 4                       # runs kept waiting for an answer; older ones are dropped
ORDER = {"mkdir": 0, "write": 1, "delete": 2, "rmdir": 3, "skip": 4}


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
        if len(text) > limit:
            text = text[:limit] + f"\n[{len(text) - limit} more characters not shown]"
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


class ShellTools:
    def __init__(self, space: Space, ops: FileOps, *, program: str, state: Path, exec_path: str, env: dict | None = None,
                 timeout: float = 60.0, max_output: int = 20_000, hide: list | None = None):
        self.space, self.ops, self.program = space, ops, program
        self.scratch = Path(state) / "sh"
        self.env = {**base_env(exec_path), "TMPDIR": "/tmp", **(env or {})}
        self.timeout, self.max_output = timeout, max_output
        home = os.path.expanduser("~")
        self.hide = [p for p in (hide if hide is not None else [os.path.join(home, h) for h in HIDE_UNDER_HOME])
                     if os.path.lexists(p)]
        self.roots = [r for r in space.roots if r.write]
        self.runs: dict[str, Run] = {}
        self._lock = threading.Lock()
        self.problem = self.probe()

    # ------------------------------------------------------------ the sandbox --

    def _argv(self, command: list, cwd: str, layers: dict) -> list:
        a = [self.program, "--die-with-parent", "--new-session", "--unshare-all",
             "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp", "--tmpfs", "/run"]
        for h in self.hide:
            if os.path.isdir(h) and not os.path.islink(h):
                a += ["--tmpfs", h]
            elif os.path.isfile(h) and not os.path.islink(h):
                a += ["--ro-bind", "/dev/null", h]
        for root, (upper, work) in layers.items():
            a += ["--overlay-src", root, "--overlay", upper, work, root]
        return a + ["--chdir", cwd, "--"] + command

    def _layers(self, scratch: Path) -> dict:
        layers = {}
        for i, r in enumerate(self.roots):
            upper, work = scratch / f"upper{i}", scratch / f"work{i}"
            upper.mkdir(parents=True)
            work.mkdir(parents=True)
            layers[r.path] = (str(upper), str(work))
        return layers

    def probe(self) -> str | None:
        """None if a command can be run over an overlay here, else why not."""
        if not self.roots:
            return "no folder here may be changed"
        if os.name == "nt" or not hasattr(os, "getxattr"):
            return "overlays are a Linux feature"
        try:
            self.scratch.mkdir(parents=True, exist_ok=True, mode=0o700)
            scratch = self.scratch / f"probe-{os.getpid()}"
            if scratch.exists():
                _force_remove(str(scratch))
            got = run_argv(self._argv(["true"], self.roots[0].path, self._layers(scratch)), cwd=self.roots[0].path,
                           env=self.env, timeout=20, max_output=2000)
            _force_remove(str(scratch))
        except OSError as e:
            return f"the sandbox could not start: {e}"
        if got["exit"] != 0:
            return "bubblewrap cannot mount an overlay here: " + (got["stderr"].strip()[:200] or f"exit {got['exit']}")
        return None

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
        return sorted(out, key=lambda c: (ORDER[c.kind], -c.path.count("/") if c.kind == "rmdir" else c.path.count("/"), c.path))

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
                           timeout=self.timeout, max_output=self.max_output)
            changes: list = []
            for root in self.roots:
                changes += self._read_upper(root, layers[root.path][0])
            run = Run(key, command, shown, got["exit"], got["seconds"], got["timed_out"], got["stdout"], got["stderr"],
                      changes, str(scratch))
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
        if not run.changes:
            return "allow", "the command changed nothing (it ran over an overlay, in a sandbox with no network)"
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
            text = run.output(self.max_output)
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

    def tools(self) -> list[Tool]:
        schema = {"type": "object",
                  "properties": {"command": {"type": "string", "minLength": 1, "maxLength": MAX_COMMAND},
                                 "cwd": {"type": "string", "minLength": 1, "maxLength": paths.MAX_PATH}},
                  "required": ["command"], "additionalProperties": False}
        return [Tool("sh", "Run a shell command in the folder (no network). It runs in a sandbox over a copy: files change "
                           "only after the person approves what it changed.",
                     schema, self.sh, permission="allow", trust="untrusted", network=False, consequential=False,
                     origin="agent", decide_call=self.decide)]
