"""commands.py: run_command (denied by default) and ps_list, through the harness like every other tool.

A command runs only if the operator's allowlist has a rule whose argv shape
it matches, token for token. Allowing a program by name is not enough, and
Trail of Bits showed why (blog.trailofbits.com, 2025-10-22, on prompt
injection turned into code execution): with the shell gone, pre-approved
commands were still turned into code execution through their own options
(`go test -exec`, `git show --output`, `rg --pre`, `fd -x`). So a rule is the whole command
line the operator means, and the model fills only typed placeholders:

    {path}     one path inside a root (the fs tools' spelling), passed on as
               its absolute path; never a secret or protected path, never
               through a symbolic link, and in a writable root unless the
               rule says it does not write ("writes": false)
    {arg}      one value
    {int}      one non-negative integer
    {path}...  {arg}...   any number of those, last in the rule only

and no placeholder value may begin with "-", so the model cannot add an
option the operator did not write. Where a program accepts it, the operator
writes "--" before a placeholder, the separator that post recommends.

Then: no shell ever (an argv list, executed directly: Python's subprocess
documentation), the program resolved once when the configuration loads and
pinned by absolute path, never one inside a writable root (the agent could
replace it), a working directory inside a root, a scrubbed environment (the
operator's secrets in the harness's own environment are not inherited), a
new session so the whole process group is killed at the deadline (Stack
Overflow q/4789837: killing only the child leaves its children), output kept
up to a cap through a selector (reader threads on Windows) while the rest is
drained and dropped (the documentation warns that communicate() buffers
everything), every process of the group killed when the command exits, and
the call back half a second later whatever the command left behind. A child
that put itself in a new session escapes the group kill; under the sandbox
its process namespace ends with the command, without it the child lives on.

The network is off unless the harness is online, and a rule counts as
reaching the network unless the operator marks it "network": false. That
mark is enforced by the required sandbox: every command runs under bubblewrap
(github.com/containers/bubblewrap) with its own network namespace holding only
a loopback device, the file system read-only except the writable roots,
/run and /tmp empty (the session bus and display sockets are not reachable),
the secret directories hidden, a new session and its own process ids. If the
sandbox does not work, no command runs. There is no unsandboxed fallback.
"""
from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

from . import paths
from .paths import PathRefused, Space, Target

PLACEHOLDERS = ("{path}", "{arg}", "{int}", "{path}...", "{arg}...")
MAX_ARGV = 64
MAX_ARG = 4096
DEFAULT_TIMEOUT = 60.0
MAX_TIMEOUT = 3600.0
DEFAULT_MAX_OUTPUT = 20_000
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class CommandRefused(ValueError):
    """A command the agent will not run; the message is what the model is told."""


@dataclass(frozen=True)
class CommandRule:
    index: int
    argv: tuple
    program: str
    permission: str = "ask"
    network: bool = True
    writes: bool = True
    timeout: float = DEFAULT_TIMEOUT
    max_output: int = DEFAULT_MAX_OUTPUT
    env: tuple = ()
    cwd: str | None = None

    @property
    def shape(self) -> str:
        return " ".join(self.argv)


@dataclass
class Invocation:
    """A matched call: the exact argv that would run, and where."""
    rule: CommandRule
    argv: list
    cwd: str
    cwd_display: str
    env: dict = field(default_factory=dict)


def _check_value(kind: str, value) -> str:
    if not isinstance(value, str) or not value:
        raise CommandRefused(f"a {kind} value must be a nonempty string")
    if len(value) > MAX_ARG:
        raise CommandRefused(f"a {kind} value is over {MAX_ARG} characters")
    if _CONTROL.search(value):
        raise CommandRefused(f"a {kind} value contains a control character")
    if value.startswith("-"):
        raise CommandRefused(f"{value[:40]!r}: a {kind} value may not begin with '-' (it would be read as an "
                             "option the operator did not allow)")
    return value


def safe_exec_path(space: Space, path: str | None = None) -> str:
    """PATH for commands: the operator's, else this process's, without relative entries or entries in a root."""
    entries = (path if path is not None else os.environ.get("PATH", os.defpath)).split(os.pathsep)
    keep = []
    for e in entries:
        if not e or not os.path.isabs(e):
            continue
        real = os.path.realpath(e)
        if space.display_of(real) is not None:
            continue
        if e not in keep:
            keep.append(e)
    return os.pathsep.join(keep)


def base_env(exec_path: str) -> dict:
    env = {"PATH": exec_path, "HOME": os.path.expanduser("~"), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
           "TERM": "dumb", "NO_COLOR": "1"}
    if os.name == "nt":
        for k in ("SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "USERPROFILE"):
            if k in os.environ:
                env[k] = os.environ[k]
    return env


# ------------------------------------------------------------------ sandbox --

HIDE_UNDER_HOME = (".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker", ".password-store", ".netrc", ".pgpass",
                   ".git-credentials", ".npmrc", ".pypirc", ".config/gh", ".local/share/keyrings")


class Bwrap:
    """Commands under bubblewrap: network namespace, read-only file system but for the writable roots."""

    def __init__(self, space: Space, program: str, hide: list | None = None):
        self.space = space
        self.program = program
        home = os.path.expanduser("~")
        self.hide = [os.path.realpath(p) for p in (hide if hide is not None else [os.path.join(home, h) for h in HIDE_UNDER_HOME])
                     if os.path.lexists(p)]

    def wrap(self, argv: list, cwd: str, network: bool) -> list:
        a = [self.program, "--die-with-parent", "--new-session", "--unshare-all"]
        if network:
            a.append("--share-net")
        a += ["--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp", "--tmpfs", "/run"]
        for h in self.hide:
            if os.path.isdir(h) and not os.path.islink(h):
                a += ["--tmpfs", h]
            elif os.path.isfile(h) and not os.path.islink(h):
                a += ["--ro-bind", "/dev/null", h]
        for r in self.space.roots:
            if r.write:
                a += ["--bind", r.path, r.path]
        return a + ["--chdir", cwd, "--"] + list(argv)

    def probe(self) -> str | None:
        """None if the sandbox works here, else why not."""
        try:
            p = subprocess.run([self.program, "--ro-bind", "/", "/", "--unshare-net", "--die-with-parent", "--",
                                "true"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired) as e:
            return f"bubblewrap could not start: {e}"
        if p.returncode != 0:
            return f"bubblewrap does not work here: {p.stderr.strip()[:300] or 'exit ' + str(p.returncode)}"
        return None


# ------------------------------------------------------------------ running --

def _reader(stream, cap: int, box: dict, key: str) -> None:
    kept, total = [], 0
    try:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                break
            if total < cap:
                kept.append(chunk[:cap - total])
            total += len(chunk)
    except (OSError, ValueError):
        pass
    box[key] = (b"".join(kept), total)


def _kill_group(proc) -> None:
    if os.name == "nt":
        try:
            proc.kill()
        except OSError:
            pass
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass


def _exited(proc, timeout: float) -> bool:
    """True once the process has exited, within timeout, WITHOUT reaping it: while the leader is an unreaped
    zombie its pid (and so its process group id) cannot be given to a new process, so killing the group
    afterwards can only reach what the command left behind (waitid with WNOWAIT, POSIX)."""
    if os.name == "nt" or not hasattr(os, "waitid"):
        try:
            proc.wait(timeout=timeout)
            return True
        except subprocess.TimeoutExpired:
            return False
    deadline = time.monotonic() + timeout
    delay = 0.001
    while True:
        try:
            if os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOWAIT | os.WNOHANG) is not None:
                return True
        except ChildProcessError:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(delay)
        delay = min(delay * 2, 0.05)


GRACE = 0.5      # seconds to keep reading after the command exits: what it wrote is already in the pipes


def run_argv(argv: list, *, cwd: str, env: dict, timeout: float, max_output: int) -> dict:
    """Run argv with no shell; {"exit", "seconds", "timed_out", "stdout", "stderr", "bytes_out", "bytes_err"}.

    The call returns GRACE seconds after the command exits (or at its deadline) at the latest, whatever it left
    behind: a descendant that holds the output pipes open does not hold the call (it once held it 10 s)."""
    kwargs = dict(stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, env=env,
                  close_fds=True)
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    started = time.monotonic()
    proc = subprocess.Popen(argv, **kwargs)
    if os.name == "nt":
        return _collect_threads(proc, started, timeout, max_output)
    import selectors
    kept = {proc.stdout.fileno(): bytearray(), proc.stderr.fileno(): bytearray()}
    total = dict.fromkeys(kept, 0)
    sel = selectors.DefaultSelector()
    for fd in kept:
        os.set_blocking(fd, False)
        sel.register(fd, selectors.EVENT_READ)
    deadline, ended, timed_out = started + timeout, None, False
    try:
        while True:
            now = time.monotonic()
            if ended is None:
                if _exited(proc, 0):
                    ended = now
                elif now >= deadline:
                    timed_out, ended = True, now
                if ended is not None:
                    _kill_group(proc)     # at the deadline, or whatever the command left running
            if ended is not None and (now - ended > GRACE or not sel.get_map()):
                break
            for key, _ in sel.select(timeout=0.05):
                try:
                    chunk = os.read(key.fd, 65536)
                except BlockingIOError:
                    continue
                except OSError:
                    chunk = b""
                if not chunk:
                    sel.unregister(key.fd)
                    continue
                room = max_output - len(kept[key.fd])
                if room > 0:
                    kept[key.fd] += chunk[:room]
                total[key.fd] += len(chunk)
    finally:
        sel.close()
        _kill_group(proc)
        proc.wait()
        for s in (proc.stdout, proc.stderr):
            try:
                s.close()
            except OSError:
                pass
    out_fd, err_fd = list(kept)
    return {"exit": proc.returncode, "seconds": (ended or time.monotonic()) - started, "timed_out": timed_out,
            "stdout": bytes(kept[out_fd]).decode("utf-8", errors="replace"),
            "stderr": bytes(kept[err_fd]).decode("utf-8", errors="replace"),
            "bytes_out": total[out_fd], "bytes_err": total[err_fd]}


def _collect_threads(proc, started: float, timeout: float, max_output: int) -> dict:
    """Windows: pipes cannot be selected, so reader threads, with the same bound on waiting for them."""
    box: dict = {}
    threads = [threading.Thread(target=_reader, args=(proc.stdout, max_output, box, "out"), daemon=True),
               threading.Thread(target=_reader, args=(proc.stderr, max_output, box, "err"), daemon=True)]
    for t in threads:
        t.start()
    timed_out = not _exited(proc, timeout)
    ended = time.monotonic()
    _kill_group(proc)
    proc.wait()
    for t in threads:
        t.join(timeout=max(0.0, GRACE - (time.monotonic() - ended)))
    out, n_out = box.get("out", (b"", 0))
    err, n_err = box.get("err", (b"", 0))
    return {"exit": proc.returncode, "seconds": ended - started, "timed_out": timed_out,
            "stdout": out.decode("utf-8", errors="replace"), "stderr": err.decode("utf-8", errors="replace"),
            "bytes_out": n_out, "bytes_err": n_err}


# -------------------------------------------------------------------- tools --

from dawnr_harness.tools import CallContext, Tool, ToolResult  # noqa: E402


class CommandTools:
    def __init__(self, space: Space, rules: list, *, exec_path: str, env: dict | None = None,
                 sandbox: Bwrap | None = None, sandbox_problem: str | None = None, offline=lambda: True,
                 runner=run_argv):
        self.space = space
        self.rules = list(rules)
        self.exec_path = exec_path
        self.env = dict(env or {})
        self.sandbox = sandbox
        self.sandbox_problem = sandbox_problem
        self.offline = offline
        self.runner = runner

    # ------------------------------------------------------------ matching --

    def _path(self, value: str, writes: bool) -> str:
        """The absolute path a {path} value names, after every rule a file tool would apply to it: inside a root,
        no link on the way or at the end, not secret, not protected (by name or identity), a file with no name
        outside the roots (Space.link_problem), and in a writable root when the rule writes. The program opens it
        later by name; DAWNR-AGENT.md says what that leaves."""
        _check_value("{path}", value)
        try:
            target = self.space.resolve(value)
            self.space._check_read_names(target)
            hit = self.space._glob_hit(self.space.protect_names, target)
            if hit:
                raise PathRefused(f"{target.display} is protected ({hit!r}); commands are not given it")
            if writes and not target.root.write:
                raise PathRefused(f"root {target.root.name} is read-only and this command writes")
            if target.parts:
                parent = self.space.walk(target, len(target.parts) - 1, write=writes)
                try:
                    try:
                        st = paths.lstat_child(parent, target.name)
                    except FileNotFoundError:
                        st = None
                    if st is not None:
                        if paths.is_link(st):
                            raise self.space._link_refusal(target, len(target.parts) - 1, parent)
                        self.space.check_file_ident(st, target, write=True)
                        # a file with a name outside the roots (or a secret one): a program would read it, or write
                        # through the link into the other name (a command writes in place; fs_write renames)
                        problem = self.space.link_problem(st, target)
                        if problem:
                            raise PathRefused(problem)
                        if paths.is_dir(st):
                            paths.close(self.space.walk(target, write=writes))
                finally:
                    paths.close(parent)
            else:
                paths.close(self.space.walk(target, write=writes))
        except PathRefused as e:
            raise CommandRefused(f"{{path}} {value!r}: {e}") from None
        return target.abspath

    def _value(self, kind: str, value, writes: bool) -> str:
        if kind == "{path}":
            return self._path(value, writes)
        _check_value(kind, value)
        if kind == "{int}" and not re.fullmatch(r"[0-9]{1,18}", value):
            raise CommandRefused(f"{value[:40]!r} is not a non-negative integer")
        return value

    def _fill(self, rule: CommandRule, argv: list) -> list | None:
        """The argv to run if argv matches the rule, else None; a matched but invalid value raises."""
        pattern = rule.argv
        if not argv or argv[0] != pattern[0]:
            return None
        out = [rule.program]
        i = 1
        for tok in pattern[1:]:
            if tok in ("{path}...", "{arg}..."):
                out += [self._value(tok[:-3], v, rule.writes) for v in argv[i:]]
                i = len(argv)
                break
            if i >= len(argv):
                return None
            v = argv[i]
            if tok in ("{path}", "{arg}", "{int}"):
                out.append(self._value(tok, v, rule.writes))
            elif v != tok:
                return None
            else:
                out.append(v)
            i += 1
        return out if i == len(argv) else None

    def match(self, args: dict) -> Invocation:
        argv = args.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
            raise CommandRefused("argv is a nonempty list of strings")
        if not self.rules:
            raise CommandRefused("no command is allowed: the operator's allowlist is empty")
        problems = []
        for rule in self.rules:
            try:
                full = self._fill(rule, argv)
            except CommandRefused as e:
                problems.append(f"rule {rule.index} ({rule.shape}): {e}")
                continue
            if full is None:
                continue
            cwd, shown = self._cwd(args.get("cwd") or rule.cwd, rule)
            env = dict(base_env(self.exec_path))
            env.update(self.env)
            env.update(dict(rule.env))
            return Invocation(rule, full, cwd, shown, env)
        if problems:
            raise CommandRefused("; ".join(problems))
        shapes = " | ".join(r.shape for r in self.rules)
        raise CommandRefused(f"{' '.join(argv)[:200]!r} matches no allowed command; allowed: {shapes}")

    def _cwd(self, value, rule: CommandRule) -> tuple[str, str]:
        if value:
            try:
                target = self.space.resolve(value)
            except PathRefused as e:
                raise CommandRefused(f"cwd: {e}") from None
        else:
            roots = [r for r in self.space.roots if r.write] if rule.writes else list(self.space.roots)
            if not roots:
                raise CommandRefused("no root to run in" + (" (the rule writes and no root is writable)"
                                                            if rule.writes else ""))
            target = Target(roots[0], ())
        if rule.writes and not target.root.write:
            raise CommandRefused(f"cwd {target.display}: root {target.root.name} is read-only and this command "
                                 "writes")
        try:
            paths.close(self.space.walk(target, write=rule.writes))
        except PathRefused as e:
            raise CommandRefused(f"cwd: {e}") from None
        return target.abspath, target.display

    def decide(self, args: dict) -> tuple[str, str]:
        try:
            inv = self.match(args)
        except CommandRefused as e:
            return "deny", str(e)
        return self._gate(inv.rule)

    def _gate(self, rule: CommandRule) -> tuple[str, str]:
        if self.sandbox_problem:
            return "deny", f"the configured sandbox does not work here ({self.sandbox_problem}); no command runs"
        if self.sandbox is None:
            return "deny", "a working bubblewrap sandbox is required; no command runs on the host"
        if rule.network and self.offline():
            return "deny", ("offline: this command rule may reach the network (the operator marks a rule "
                            "\"network\": false when it does not)")
        return rule.permission, f"command rule {rule.index}: {rule.shape}"

    def wrapped(self, inv: Invocation) -> list:
        if self.sandbox is None:
            raise CommandRefused("a working bubblewrap sandbox is required")
        return self.sandbox.wrap(inv.argv, inv.cwd, inv.rule.network and not self.offline())

    # --------------------------------------------------------------- tools --

    def run_command(self, args: dict, ctx: CallContext) -> ToolResult:
        try:
            inv = self.match(args)
        except CommandRefused as e:
            return ToolResult(f"refused: {e}", is_error=True)
        decision, why = self._gate(inv.rule)
        if decision == "deny":
            return ToolResult(f"refused: {why}", is_error=True)
        argv = self.wrapped(inv)
        try:
            r = self.runner(argv, cwd=inv.cwd, env=inv.env, timeout=inv.rule.timeout,
                            max_output=inv.rule.max_output)
        except OSError as e:
            return ToolResult(f"refused: {inv.argv[0]} could not start: {e.strerror or e}", is_error=True,
                              trust="untrusted")
        shown = " ".join(args["argv"])
        head = (f"timed out after {inv.rule.timeout:g} s (the process group was killed): {shown}" if r["timed_out"]
                else f"exit {r['exit']} after {r['seconds']:.2f} s: {shown}") + f" (in {inv.cwd_display})"
        parts = [head, r["stdout"].rstrip("\n")]
        if r["bytes_out"] > inv.rule.max_output:
            parts.append(f"[stdout truncated: {r['bytes_out']} bytes, first {inv.rule.max_output} shown]")
        if r["stderr"].strip():
            parts += ["[stderr]", r["stderr"].rstrip("\n")]
        if r["bytes_err"] > inv.rule.max_output:
            parts.append(f"[stderr truncated: {r['bytes_err']} bytes, first {inv.rule.max_output} shown]")
        return ToolResult("\n".join(p for p in parts if p != ""), is_error=r["timed_out"] or r["exit"] != 0,
                          trust="untrusted")

    def preview(self, args: dict) -> "object":
        from .files import Preview
        try:
            inv = self.match(args)
        except CommandRefused as e:
            return Preview(error=str(e))
        decision, why = self._gate(inv.rule)
        if decision == "deny":
            return Preview(error=why)
        where = "under bubblewrap, " + ("with" if inv.rule.network and not self.offline() else "without") + " network"
        summary = (f"runs {' '.join(args['argv'])} in {inv.cwd_display} (rule {inv.rule.index}: {inv.rule.shape}; "
                   f"timeout {inv.rule.timeout:g} s; {where}); its output enters as untrusted data; its effects on "
                   "files are not simulated")
        detail = ["exact argv: " + " ".join(_quote(a) for a in self.wrapped(inv)),
                  "environment: " + ", ".join(sorted(inv.env))]
        return Preview(summary=summary, detail=detail)

    def tools(self) -> list[Tool]:
        shapes = " | ".join(r.shape for r in self.rules) or "none (the allowlist is empty)"
        schema = {"type": "object",
                  "properties": {"argv": {"type": "array", "minItems": 1, "maxItems": MAX_ARGV,
                                          "items": {"type": "string", "maxLength": MAX_ARG}},
                                 "cwd": {"type": "string", "minLength": 1, "maxLength": paths.MAX_PATH}},
                  "required": ["argv"], "additionalProperties": False}
        run = Tool("run_command", f"Run one allowed command (an argv list, no shell) inside a root. Allowed: {shapes}",
                   schema, self.run_command, permission="deny", trust="untrusted", network=False, consequential=True,
                   origin="agent", decide_call=self.decide)
        return [run]


def _quote(a: str) -> str:
    return a if re.fullmatch(r"[A-Za-z0-9_@%+=:,./-]+", a) else "'" + a.replace("'", "'\\''") + "'"


# ------------------------------------------------------------------ processes --

def list_processes(match: str | None = None, limit: int = 200) -> list[dict]:
    """Processes on this machine: pid, ppid, whether they are this user's, name, command line (own only)."""
    me = os.getuid() if hasattr(os, "getuid") else None
    rows = []
    if sys.platform.startswith("linux") and os.path.isdir("/proc"):
        for d in os.listdir("/proc"):
            if not d.isdigit():
                continue
            try:
                with open(f"/proc/{d}/stat", "rb") as f:
                    raw = f.read().decode("utf-8", errors="replace")
                name = raw[raw.index("(") + 1:raw.rindex(")")]
                fields = raw[raw.rindex(")") + 2:].split()
                ppid = int(fields[1])
                uid = None
                with open(f"/proc/{d}/status", "rb") as f:
                    for line in f.read().decode("utf-8", errors="replace").splitlines():
                        if line.startswith("Uid:"):
                            uid = int(line.split()[1])
                            break
                cmd = ""
                if uid == me:
                    with open(f"/proc/{d}/cmdline", "rb") as f:
                        cmd = f.read(4096).replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
            except (OSError, ValueError, IndexError):
                continue
            rows.append({"pid": int(d), "ppid": ppid, "own": uid == me, "name": name, "cmd": cmd})
    elif os.name == "nt":
        p = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=20,
                           stdin=subprocess.DEVNULL)
        for line in p.stdout.splitlines():
            cells = [c.strip('"') for c in line.split('","')]
            if len(cells) >= 2 and cells[1].isdigit():
                rows.append({"pid": int(cells[1]), "ppid": None, "own": None, "name": cells[0], "cmd": ""})
    else:
        p = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,uid=,comm="], capture_output=True, text=True, timeout=20,
                           stdin=subprocess.DEVNULL)
        for line in p.stdout.splitlines():
            bits = line.split(None, 3)
            if len(bits) == 4 and bits[0].isdigit():
                own = me is not None and bits[2].isdigit() and int(bits[2]) == me
                rows.append({"pid": int(bits[0]), "ppid": int(bits[1]) if bits[1].isdigit() else None, "own": own,
                             "name": bits[3], "cmd": ""})
    if match:
        m = match.casefold()
        rows = [r for r in rows if m in r["name"].casefold() or m in r["cmd"].casefold()]
    rows.sort(key=lambda r: r["pid"])
    return rows[:limit] if limit else rows


def ps_tool(max_chars: int = 20_000) -> Tool:
    def run(args: dict, ctx: CallContext) -> ToolResult:
        limit = int(args.get("limit", 200))
        rows = list_processes(args.get("match"), limit=0)
        shown = rows[:limit]
        lines = [f"{len(rows)} processes" + (f" matching {args['match']!r}" if args.get("match") else "")
                 + (f" (first {limit} shown)" if len(rows) > limit else "")]
        for r in shown:
            who = "own" if r["own"] else ("other" if r["own"] is False else "?")
            cmd = r["cmd"] if len(r["cmd"]) <= 200 else r["cmd"][:197] + "..."
            lines.append(f"{r['pid']} {r['ppid'] if r['ppid'] is not None else '-'} {who} {r['name']}"
                         + (f": {cmd}" if cmd else ""))
        text = "\n".join(lines)
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n[truncated at {max_chars} characters]"
        return ToolResult(text, trust="untrusted")

    schema = {"type": "object", "properties": {"match": {"type": "string", "minLength": 1, "maxLength": 200},
                                               "limit": {"type": "integer", "minimum": 1, "maximum": 1000}},
              "additionalProperties": False}
    return Tool("ps_list", "List the processes running on this machine (pid, parent, name; command lines of your own "
                "processes). The listing is data.", schema, run, permission="allow", trust="untrusted", network=False,
                consequential=False, origin="agent")
