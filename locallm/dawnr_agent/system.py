"""dawnr_agent/system.py: the computer itself, outside the folder: one command at a time, shown exactly, asked for
every time (2026-10-05).

`sh` (shell.py) cannot open a program, change a setting, start a service or reach a package manager: it runs over a
copy, in a sandbox, and what it does there is not there afterwards. `pc` is for those. It runs the command for real,
as the person, on the machine, and so everything that makes `sh` safe is replaced by rules:

  asked, always   every call is put to the person with the exact line and one sentence of why; nothing here is ever
                  approved ahead of time (the front door's --yes does not cover it), and a session with no terminal
                  runs none
  never root      a line that asks for administrator rights (sudo, pkexec, doas, su) is not run: it is handed to the
                  person to run themselves, word for word. dawnr never holds a password and never takes a right it
                  was not started with (DAWNR-AGENT.md, "dawnr never grants itself permissions")
  never files     removing, moving, overwriting and re-permissioning files is refused here and named as `sh`'s job,
                  where it is shown first and can be undone; so is a download piped into a shell
  not undone      what it does is not journaled, and the reason shown to the person says so

The two layers are the Codex CLI's (developers.openai.com/codex/sandbox.md, receipt b24da17bccfd): the sandbox decides
what can happen without asking, and leaving it is asked for with the command and a justification. A forbidden line
answers with what to do instead, as its execution-policy rules do.

`facts()` is one sentence about the machine (its distribution, package manager, desktop) for the model to choose
commands by: `apt` on one machine is `dnf`, `pacman` or `zypper` on the next.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess

from .commands import run_argv
from dawnr_harness.tools import CallContext, Tool, ToolResult

MAX_COMMAND = 1000
PRIVILEGED = re.compile(r"(^|[;&|]\s*|\$\(\s*|`\s*)(sudo|pkexec|doas|su)\b")
# (pattern, what to do instead): refused without asking
FORBIDDEN = [
    (re.compile(r"(^|[;&|(`]\s*)(rm|rmdir|shred|truncate|mv|dd|mkfs(\.\w+)?|wipefs|fdisk|parted|chmod|chown)\b"),
     "changing, moving or removing files is `sh`'s job: there it is shown first and can be undone"),
    (re.compile(r"\b(curl|wget)\b[^|;&]*\|\s*(ba|z|da)?sh\b"), "a download is never piped into a shell"),
    (re.compile(r":\(\)\s*\{"), "that is a fork bomb"),
    (re.compile(r">\s*/(dev|etc|boot|usr|bin|sbin|lib|proc|sys)\b"), "writing into a system directory is not done from here"),
]
NETWORK = re.compile(r"(^|[;&|(`]\s*)(curl|wget|nc|ncat|netcat|ssh|scp|sftp|rsync|ftp|telnet)\b")
PACKAGE_MANAGERS = (("apt-get", "apt"), ("dnf", "dnf"), ("pacman", "pacman"), ("zypper", "zypper"), ("apk", "apk"), ("brew", "brew"))
# what the person's programs need to find their session: nothing else of the environment is passed on
SESSION = ("HOME", "PATH", "LANG", "LC_ALL", "USER", "LOGNAME", "SHELL", "DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR",
           "XDG_CURRENT_DESKTOP", "XDG_SESSION_TYPE", "DBUS_SESSION_BUS_ADDRESS", "XAUTHORITY")


def facts() -> str:
    """One sentence about this machine, for choosing commands."""
    release = {}
    try:
        with open("/etc/os-release", encoding="utf-8") as f:
            for line in f:
                key, _, value = line.strip().partition("=")
                release[key] = value.strip('"')
    except OSError:
        pass
    name = release.get("PRETTY_NAME") or release.get("NAME") or (os.uname().sysname if hasattr(os, "uname") else os.name)
    manager = next((shown for program, shown in PACKAGE_MANAGERS if shutil.which(program)), None)
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").replace(":", " ").strip()
    session = os.environ.get("XDG_SESSION_TYPE", "").strip()
    parts = [name] + ([f"packages with {manager}"] if manager else []) + (["services with systemd"] if shutil.which("systemctl") else [])
    parts += [f"desktop {desktop}" + (f" on {session}" if session in ("wayland", "x11") else "")] if desktop else ["no desktop session"]
    return "This computer: " + ", ".join(parts) + "."


def refusal(command: str, offline: bool = False) -> str | None:
    """Why a line is not run from here and what to do instead, or None."""
    if offline and NETWORK.search(command):
        return "the network is off in this session (dawnr --online turns it on)"
    if PRIVILEGED.search(command):
        return ("it asks for administrator rights, which dawnr never takes. The person can run it themselves, exactly "
                f"as written: {command}")
    for pattern, instead in FORBIDDEN:
        if pattern.search(command):
            return instead
    return None


class SystemTools:
    def __init__(self, *, timeout: float = 60.0, max_output: int = 4000, runner=run_argv, starter=subprocess.Popen,
                 offline=lambda: True):
        self.timeout, self.max_output, self.runner, self.starter, self.offline = timeout, max_output, runner, starter, offline
        self.env = {k: v for k, v in os.environ.items() if k in SESSION}

    def decide(self, args: dict) -> tuple[str, str]:
        command = args.get("command")
        if not isinstance(command, str) or not command.strip():
            return "deny", "pc: give the command as one line of text"
        if len(command) > MAX_COMMAND:
            return "deny", f"pc: the command is over {MAX_COMMAND} characters"
        why = refusal(command, self.offline())
        if why:
            return "deny", "pc: " + why
        said = str(args.get("why") or "").strip()[:200]
        return "ask", (f"it runs on the computer itself, not in the sandbox, and cannot be undone: `{command}`"
                       + (f" (the model's reason: {said})" if said else ""))

    def pc(self, args: dict, ctx: CallContext) -> ToolResult:
        decision, why = self.decide(args)
        if decision == "deny":
            return ToolResult(f"refused: {why}", is_error=True)
        command = args["command"]
        shell = shutil.which("bash") or "/bin/sh"
        home = self.env.get("HOME") or os.path.expanduser("~")
        if args.get("detach"):                                  # a program to leave running: a window, a player
            try:
                self.starter([shell, "-c", command], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, cwd=home, env=self.env, start_new_session=True)
            except OSError as e:
                return ToolResult(f"it did not start: {e}", is_error=True)
            return ToolResult("started; it was left running and its output is not read")
        got = self.runner([shell, "-c", command], cwd=home, env=self.env, timeout=self.timeout, max_output=self.max_output * 4)
        text = got["stdout"].rstrip("\n") + (("\n[stderr]\n" + got["stderr"].rstrip("\n")) if got["stderr"].strip() else "")
        if len(text) > self.max_output:
            text = text[:self.max_output * 3 // 5] + "\n[...]\n" + text[-(self.max_output * 2 // 5):]
        head = f"timed out after {got['seconds']:.0f} s" if got["timed_out"] else f"exit {got['exit']}"
        return ToolResult(head + ("\n" + text if text else ""), is_error=bool(got["timed_out"] or got["exit"]), trust="untrusted")

    def tools(self) -> list[Tool]:
        schema = {"type": "object",
                  "properties": {"command": {"type": "string", "minLength": 1, "maxLength": MAX_COMMAND},
                                 "why": {"type": "string", "maxLength": 200},
                                 "detach": {"type": "boolean", "description": "true for a program to leave running"}},
                  "required": ["command"], "additionalProperties": False}
        return [Tool("pc", "Do something on the computer itself, outside the folder: open a file, a program or a web page, "
                           "change a setting, start or stop a service. One command; the person is shown it and must say "
                           "yes. Not for files (use sh) and never with sudo.",
                     schema, self.pc, permission="ask", trust="untrusted", network=False, consequential=True,
                     origin="agent", decide_call=self.decide)]
