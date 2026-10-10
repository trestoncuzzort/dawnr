"""Read-only host diagnostics for repository inspection and testing.

`sysinfo` accepts only command shapes recognized by `look`; it does not expose a
host shell for desktop, service or settings changes. The old `pc` entry point is
a compatibility refusal, never a registered tool. Historical command classifiers
remain for reading older evaluation records, not as an execution policy.
"""
from __future__ import annotations

import glob
import os
import re
import shlex
import shutil
import subprocess

from .commands import HIDE_UNDER_HOME, run_argv
from .paths import DEFAULT_SECRETS
from dawnr_harness.tools import CallContext, Tool, ToolResult

MAX_COMMAND = 1000
PRIVILEGED = re.compile(r"(^|[;&|]\s*|\$\(\s*|`\s*)(sudo|pkexec|doas|su|runas(\.exe)?|sudo\.exe|gsudo(\.exe)?)\b|-Verb\s+RunAs\b", re.I)
# (pattern, what to do instead): refused without asking
FORBIDDEN = [
    (re.compile(r"(^|[;&|(`]\s*)(rm|rmdir|shred|truncate|mv|dd|mkfs(\.\w+)?|wipefs|fdisk|parted|chmod|chown)\b"),
     "changing, moving or removing files is `sh`'s job: there it is shown first and can be undone"),
    (re.compile(r"(^|[;&|(`]\s*)(mount|umount|swapon|swapoff|losetup|cryptsetup|modprobe|insmod|rmmod)\b"),
     "what is mounted or loaded into the kernel is not changed from here"),
    (re.compile(r"\b(curl|wget)\b[^|;&]*\|\s*(ba|z|da)?sh\b"), "a download is never piped into a shell"),
    (re.compile(r":\(\)\s*\{"), "that is a fork bomb"),
    (re.compile(r">\s*/(?!dev/(null|stdout|stderr)\b)(dev|etc|boot|usr|bin|sbin|lib|proc|sys)\b"),
     "writing into a system directory is not done from here"),
    # a Windows desktop reached from WSL: what formats, partitions or boots, and what sweeps a drive or Windows itself
    (re.compile(r"(^|[;&|(`]\s*)(format(\.com|\.exe)?|diskpart(\.exe)?|bcdedit(\.exe)?|cipher(\.exe)?\s+/w)\b|"
                r"\b(Format-Volume|Clear-Disk|Initialize-Disk|Remove-Partition|Set-Partition)\b", re.I),
     "disks, partitions and the boot settings are not changed from here"),
    (re.compile(r"\b(rd|rmdir|del|erase)(\.exe)?\s+(/[sq]\s+)*['\"]?[A-Za-z]:\\(Windows|Users|Program Files[^\\\s]*)?\\?['\"]?(\s|$)|"
                r"\bRemove-Item\b[^|;]*-Recurse[^|;]*['\"]?[A-Za-z]:\\(Windows|Users|Program Files[^\\\s]*)?\\?['\"]?(\s|$)", re.I),
     "sweeping a drive, Windows or every user's folder away is not done from here"),
]
NETWORK = re.compile(r"(^|[;&|(`]\s*)(curl|wget|nc|ncat|netcat|ssh|scp|sftp|rsync|ftp|telnet)(\.exe)?\b|\b(https?|ftp)://|"
                     r"\b(Invoke-WebRequest|iwr|Invoke-RestMethod|irm|Start-BitsTransfer|bitsadmin|Test-NetConnection|Test-Connection|"
                     r"ping(\.exe)?|tracert(\.exe)?|nslookup(\.exe)?|Net\.WebClient|Net\.Sockets|certutil(\.exe)?\s+-urlcache)\b", re.I)
# the names the file tools never read (paths.py) and the folders the sandbox hides (commands.py): a line that names
# one is not run, whatever program it names it to
SECRET = re.compile(r"(?:^|[\s/\\'\"=:])(" + "|".join(
    sorted({re.escape(n).replace(r"\*", r"[^\s/\\'\"]*") for n in DEFAULT_SECRETS + HIDE_UNDER_HOME}, key=len, reverse=True))
    + r")(?=$|[\s/\\'\";|&)])")
# ... and on a Windows desktop: browsers' saved passwords, the credential store, and `netsh wlan show profile ... key=clear`,
# which prints a Wi-Fi password
WINDOWS_SECRET = re.compile(r"key\s*=\s*clear|\bLogin Data\b|\blogins\.json\b|\bkey4\.db\b|\\Microsoft\\(Credentials|Vault|Protect)\\?|"
                            r"\bcmdkey(\.exe)?\b", re.I)
PACKAGE_MANAGERS = (("apt-get", "apt"), ("dnf", "dnf"), ("pacman", "pacman"), ("zypper", "zypper"), ("apk", "apk"), ("brew", "brew"))
# what the person's programs need to find their session: nothing else of the environment is passed on
SESSION = ("HOME", "PATH", "LANG", "LC_ALL", "USER", "LOGNAME", "SHELL", "DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR",
           "XDG_CURRENT_DESKTOP", "XDG_SESSION_TYPE", "DBUS_SESSION_BUS_ADDRESS", "XAUTHORITY",
           "WSL_INTEROP", "WSL_DISTRO_NAME", "WSLENV")                  # under WSL, what a Windows program needs to be reached


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
    if under_windows():
        parts += ["desktop Windows under WSL"]
        tail = (" Windows itself is the desktop here: its programs are called by name with .exe (explorer.exe, powershell.exe, "
                "clip.exe) and take Windows paths, which `wslpath -w PATH` gives.")
    else:
        parts += [f"desktop {desktop}" + (f" on {session}" if session in ("wayland", "x11") else "")] if desktop else ["no desktop session"]
        tail = ""
    return "This computer: " + ", ".join(parts) + "." + tail


def under_windows() -> bool:
    """Whether this Linux runs under Windows (WSL) with Windows's own programs reachable: the kernel says so, and
    explorer.exe is on the PATH (Microsoft's interop; a person can turn it off, and then there is no desktop here)."""
    try:
        release = os.uname().release.lower()
    except AttributeError:
        return False
    return "microsoft" in release and shutil.which("explorer.exe") is not None


# ------------------------------------------------------------------ looking --
# A line that only looks at the computer runs without asking. The shape is the Codex CLI's is_known_safe_command
# (codex-rs/core/src/command_safety/is_safe_command.rs at rust-v0.50.0; receipt 15b82d3b3d27): plain commands, bare
# words and quoted strings, joined by | && || ; and by nothing else, each a read-only program used in a read-only
# way. Two things differ. The list is of what shows a computer's state, not a repository's; and where Codex lets
# cat and grep open any file, here a file is opened only where no secret is kept. The line that runs is not the
# model's text but the words read from it, each quoted again, so the shell expands and substitutes nothing.

OPERATORS = ("|", "&&", "||", ";")
# the redirections that only throw output away or join the two streams: part of a plain command, and kept
QUIET = re.compile(r"(?:2>\s*/dev/null|2>&1|&>\s*/dev/null|>\s*/dev/null)(?=\s|$|[|&;])")
NUMBER = re.compile(r"^[+-]?\d+$")
READABLE = re.compile(r"^(/sys/|/proc/(?!\d|self\b|thread-self\b)|/usr/lib/os-release$|/etc/(os-release|lsb-release|hostname|"
                      r"timezone|issue|machine-info|debian_version|fedora-release|redhat-release|arch-release|shells|hosts|"
                      r"resolv\.conf|fstab|locale\.conf|vconsole\.conf)$)")


def _words(command: str) -> list | None:
    """[(word, kind)] for a line of plain commands, kind False for a word, True for an operator and "quiet" for a
    redirection that only discards output; None when the line holds anything else: another redirection, a
    substitution, a variable, a subshell, a background job, a comment, a backslash outside single quotes."""
    out, word, quote, i = [], None, "", 0
    while i < len(command):
        c = command[i]
        quiet = QUIET.match(command, i) if not quote and word is None else None
        if quiet:
            out.append((re.sub(r"\s", "", quiet.group(0)), "quiet"))
            i = quiet.end()
            continue
        if quote:
            if c == quote:
                quote = ""
            elif c in "\n\r" or (quote == '"' and c in "$`"):
                return None
            elif quote == '"' and c == "\\":                    # the shell keeps it before any character but these
                if command[i + 1:i + 2] in ("", "$", "`", '"', "\\", "\n"):
                    return None
                word += c
            else:
                word += c
        elif c in "'\"":
            quote, word = c, word or ""
        elif c in " \t":
            if word is not None:
                out.append((word, False))
                word = None
        elif c in "|&;":
            if word is not None:
                out.append((word, False))
                word = None
            op = c + (c if c in "|&" and command[i + 1:i + 2] == c else "")
            if op not in OPERATORS:
                return None
            out.append((op, True))
            i += len(op) - 1
        elif c in "`$<>(){}\\\n\r" or (c == "#" and word is None):
            return None
        else:
            word = (word or "") + c
        i += 1
    if quote:
        return None
    return out + ([(word, False)] if word is not None else [])


def _readable(path: str) -> bool:
    return bool(READABLE.match(path)) and ".." not in path


def _no(*bad, letters: str = ""):
    """Any arguments but these; an option is matched up to its `=`, and a cluster of short ones by its letters."""
    def rule(args):
        return not any(a in bad or a.split("=", 1)[0] in bad or
                       (letters and re.match(r"^-[A-Za-z0-9]", a) and any(ch in a for ch in letters)) for a in args)
    return rule


def _sub(*ok, bare: bool = True, bad=(), takes=()):
    """Its first word that is not an option (or an option's value, for the options in `takes`) is one of `ok`; with
    none it is allowed where `bare`; no word is one of `bad`."""
    def rule(args):
        first, skip = None, False
        for a in args:
            if a in bad or a.split("=", 1)[0] in bad:
                return False
            if skip:
                skip = False
            elif a in takes:
                skip = True
            elif not a.startswith("-") and first is None:
                first = a
        return bare if first is None else first in ok
    return rule


def _only(*ok):
    return lambda args: all(a in ok or a.split("=", 1)[0] in ok for a in args)


def _reads(flags: str, values: str = ""):
    """Options matching `flags`, numbers, and files only from where nothing secret is kept. An option in `values`
    takes the next word."""
    ok = re.compile(flags)

    def rule(args):
        skip = False
        for a in args:
            if skip:
                skip = False
            elif a in values.split():
                skip = True
            elif a.startswith("-") and len(a) > 1:
                if not ok.match(a):
                    return False
            elif not (NUMBER.match(a) or _readable(a)):
                return False
        return True
    return rule


def _grep(args) -> bool:
    """A pattern, plain options, and files only from where nothing secret is kept (none: it filters a pipe)."""
    flags = re.compile(r"^-[inovEFPcwxhHqsABCm0-9]+$|^--(ignore-case|invert-match|count|only-matching|line-number|"
                       r"extended-regexp|fixed-strings|perl-regexp|word-regexp|colou?r=\w+|max-count=\d+|no-filename|with-filename)$")
    operands, previous = [], ""
    for a in args:
        if a.startswith("-") and len(a) > 1:
            if not flags.match(a):
                return False
        elif not (NUMBER.match(a) and re.match(r"^-[A-Za-z]*[ABCm]$", previous)):
            operands.append(a)
        previous = a
    return bool(operands) and all(_readable(f) for f in operands[1:])


def _top(args) -> bool:                                         # once, in batch mode: never the screen that waits
    short = "".join(a[1:] for a in args if re.match(r"^-[A-Za-z]", a))
    return "b" in short and "n" in short and not any(a.startswith("--") for a in args)


def _version(args) -> bool:
    return len(args) == 1 and args[0] in ("--version", "-V", "-version", "version")


_SYSTEMD = dict(bad=("-H", "--host", "-M", "--machine", "--root", "--image"),
                takes=("-t", "--type", "-p", "--property", "-n", "--lines", "-o", "--output", "--state"))
_NMCLI_ACTS = ("up", "down", "add", "modify", "mod", "delete", "del", "edit", "connect", "disconnect", "on", "off", "set",
               "reload", "load", "import", "export", "clone", "rescan", "hotspot", "reapply", "monitor", "permissions",
               "logging", "hostname", "show-password", "migrate", "agent", "-s", "--show-secrets", "-a", "--ask")
LOOK = {
    # the machine
    "df": _no(), "free": _no(), "uptime": _no(), "uname": _no(), "nproc": _no(), "arch": _no(), "lscpu": _no(),
    "lsblk": _no(), "lsusb": _no(), "lspci": _no(), "lsmem": _no(), "lsmod": _no(), "lsb_release": _no(), "findmnt": _no(),
    "getconf": _no(), "locale": _no(), "cal": _no(), "systemd-detect-virt": _no(),
    "vmstat": lambda a: all(x.startswith("-") or NUMBER.match(x) for x in a),
    "mount": lambda a: not a, "swapon": _only("--show", "-s", "--summary"),
    "hostname": lambda a: all(x.startswith("-") for x in a) and _no("--file", "--boot", letters="Fb")(a),
    "date": lambda a: all((x.startswith("+") or x.startswith("-")) and not x.startswith(("-s", "--set", "-f", "--file")) for x in a),
    "sensors": _only("-A", "-u", "-j", "-f", "--fahrenheit", "--no-adapter"), "acpi": lambda a: all(x.startswith("-") for x in a),
    "upower": _sub(bare=True, takes=("-i", "--show-info"), bad=("--monitor", "--monitor-detail", "-m")),
    "nvidia-smi": lambda a: all(x in ("-L", "-q", "-x") or x.startswith(("--query-", "--format=", "--id=")) for x in a),
    "glxinfo": _only("-B"), "vulkaninfo": _only("--summary"),
    "systemd-analyze": _sub("time", "blame", "critical-chain"), "powerprofilesctl": _sub("get", "list"),
    # who and what is running
    "whoami": _no(), "id": _no(), "groups": _no(), "w": _no(), "who": _no(), "last": _no("-f", "--file"),
    "ps": _no(), "pgrep": _no(), "pidof": _no(), "top": _top,
    # the network, as it is (nothing here sends a packet)
    "ip": _sub("a", "addr", "address", "l", "link", "r", "route", "n", "neigh", "neighbor", "neighbour", "rule", "maddr",
               bad=("add", "del", "delete", "set", "flush", "change", "replace", "append", "prepend", "exec", "save",
                    "restore", "monitor", "-b", "-batch", "-force", "-n", "-netns")),
    "ss": _no("--kill", "--diag", letters="KD"), "iwgetid": _no(),
    "nmcli": _sub("general", "g", "device", "d", "dev", "connection", "c", "con", "radio", "r", "networking", "n",
                  bad=_NMCLI_ACTS, takes=("-f", "--fields", "-g", "--get-values", "-m", "--mode", "-c", "--colors",
                                          "-e", "--escape", "-w", "--wait")),
    "resolvectl": _sub("status", "statistics"), "rfkill": _sub("list"), "bluetoothctl": _sub("show", "devices", "paired-devices", "list", "info", bare=False),
    # services and the session
    "systemctl": _sub("status", "is-active", "is-enabled", "is-failed", "is-system-running", "list-units", "list-unit-files",
                      "list-timers", "list-sockets", "list-jobs", "list-dependencies", "show", "cat", "get-default", **_SYSTEMD),
    "journalctl": _no("-f", "--follow", "--rotate", "--flush", "--sync", "--relinquish-var", "--smart-relinquish-var",
                      "--setup-keys", "--update-catalog", "--cursor-file", "--root", "--image", "--vacuum-size",
                      "--vacuum-time", "--vacuum-files", "-M", "--machine", letters="fM"),
    "loginctl": _sub("list-sessions", "list-users", "list-seats", "session-status", "user-status", "seat-status",
                     "show-session", "show-user", "show-seat", **_SYSTEMD),
    "timedatectl": _sub("status", "show", "list-timezones", "timesync-status", "show-timesync", **_SYSTEMD),
    "hostnamectl": _sub("status", **_SYSTEMD), "localectl": _sub("status", "list-locales", "list-keymaps", **_SYSTEMD),
    # the desktop: settings, sound, the screen
    "gsettings": _sub("get", "list-schemas", "list-keys", "list-children", "list-recursively", "range", "describe",
                      "writable", bare=False),
    "dconf": _sub("read", "list", "dump", bare=False), "xdg-mime": _sub("query", bare=False),
    "xdg-settings": lambda a: a[:1] in (["get"], ["check"], ["--list"]), "xdg-user-dir": _no(),
    "xrandr": _only("-q", "--query", "--listmonitors", "--listactivemonitors", "--current", "--verbose", "--props", "--version"),
    "pactl": _sub("info", "list", "stat", "get-default-sink", "get-default-source", "get-sink-volume", "get-sink-mute",
                  "get-source-volume", "get-source-mute", bare=False, bad=("-s", "--server"), takes=("-f", "--format")),
    "wpctl": _sub("status", "get-volume", "inspect", bare=False),
    "amixer": _sub("get", "sget", "cget", "scontrols", "scontents", "controls", "contents", "info", takes=("-c", "-D")),
    "playerctl": _sub("status", "metadata", takes=("-p", "--player", "-f", "--format"), bare=False),
    "brightnessctl": _sub("get", "max", "info"),
    # what is installed (each manager's local database: nothing here refreshes from a mirror)
    "dpkg": lambda a: a[:1] != [] and a[0] in ("-l", "-s", "-L", "-S", "-p", "--list", "--status", "--listfiles", "--search",
                                                "--get-selections", "--print-architecture", "--version")
    and not any(x.startswith("-") for x in a[1:]),
    "dpkg-query": _no("--admindir", "--root", "--load-avail"),
    "apt": _sub("list", "show", "search", "policy", "depends", "rdepends", bare=False, bad=("-o", "--option", "-c", "--config-file")),
    "apt-cache": _no("-o", "--option", "-c", "--config-file"), "apt-mark": _sub("showmanual", "showauto", "showhold", bare=False),
    "rpm": lambda a: a[:1] != [] and bool(re.match(r"^(-q[ailfcdRp]*|--query)$", a[0]))
    and all(not x.startswith("-") or x in ("-a", "-i", "-l", "-f", "-c", "-d", "-R", "--all", "--info", "--list", "--file",
                                           "--requires", "--provides", "--whatprovides", "--whatrequires", "--last",
                                           "--changelog") for x in a[1:]),
    "pacman": lambda a: a[:1] != [] and bool(re.match(r"^-Q[a-z]*$", a[0])) and not any(x.startswith("-") for x in a[1:]),
    "apk": _sub("info", "list", "version", "stats", bare=False), "flatpak": _sub("list", "info", "remotes", "history", "ps", bare=False),
    "snap": _sub("list", "version", "services", "connections", "changes", bare=False),
    "pip": _sub("list", "show", "freeze", "check", bare=False, bad=("-o", "--outdated", "-u", "--uptodate", "--index-url", "-i")),
    "brew": _sub("list", "leaves", bare=False),
    # the manual: what a program is for and how it is called, read and not recalled
    "man": lambda a: 1 <= len(a) <= 2 and all(re.fullmatch(r"[\w.+-]+", x) and not x.startswith("-") for x in a),
    "apropos": lambda a: bool(a) and all(not x.startswith("-") for x in a), "whatis": lambda a: bool(a) and all(not x.startswith("-") for x in a),
    # where a program is, and saying something between two commands
    "which": _no(), "whereis": _no(), "type": _no(), "command": lambda a: len(a) == 2 and a[0] in ("-v", "-V"),
    "printenv": _no(), "echo": _no(), "true": _no(), "false": _no(),
    # a file, only where nothing secret is kept; and the filters of a pipe
    "cat": _reads(r"^-[nAbsETv]+$"), "grep": _grep, "tr": _no(),
    "head": _reads(r"^-(\d+|[nc]-?\d*|q|v)$|^--(lines|bytes)=-?\d+$"), "tail": _reads(r"^-(\d+|[nc][+-]?\d*|q|v)$|^--(lines|bytes)=[+-]?\d+$"),
    "wc": _reads(r"^-[lwcmL]+$|^--(lines|words|chars|bytes|max-line-length)$"),
    "sort": _reads(r"^-[bdfgiMhnRrVkuzc0-9,.]+$|^--(numeric-sort|reverse|human-numeric-sort|unique|general-numeric-sort|"
                   r"version-sort|ignore-case|key=[\w,.]+|field-separator=.)$", values="-t"),
    "uniq": lambda a: all(re.match(r"^-[cdui]+$|^--count$", x) for x in a),
    "cut": _reads(r"^-[dfcbs]\S*$|^--(delimiter|fields|characters|bytes|complement|only-delimited|output-delimiter)(=.*)?$", values="-d"),
    "column": _reads(r"^-[tx]+$", values="-s"),
}
LOOK["pip3"] = LOOK["pip"]
for _name in ("apt", "dpkg", "rpm", "pacman", "apk", "flatpak", "snap", "brew"):       # ... and any of them asked its version
    LOOK[_name] = (lambda rule: lambda a: _version(a) or rule(a))(LOOK[_name])
for _name in ("dnf", "yum", "zypper", "apt-get", "python3", "python", "git", "node", "npm", "gcc", "g++", "cc", "clang", "make", "cmake", "java", "javac", "go",
              "rustc", "cargo", "docker", "podman", "bash", "zsh", "fish", "ffmpeg", "curl", "wget", "code", "firefox",
              "chromium", "chromium-browser", "google-chrome", "libreoffice", "soffice", "vim", "nvim", "emacs", "nano",
              "tmux", "ssh", "openssl", "perl", "ruby", "php", "R", "julia", "dotnet", "gnome-shell", "plasmashell"):
    LOOK[_name] = _version
# A Windows desktop under WSL: Windows's own programs, called by their .exe names (Microsoft's interop), where they only
# look. PowerShell takes the Codex CLI's shape for it (codex-rs/core/src/command_safety/windows_safe_commands.rs at
# rust-v0.50.0; receipt f69fc63e80f2): a few plain switches, one -Command script, the script split into pipeline
# segments, any token holding a separator, a redirection, a variable, a call or a block refuses the whole line, and
# each segment's first word must be on a short list. The list here is what shows the computer's state; Codex's has the
# file readers (Get-Content, Get-ChildItem), which are left out, since a file is read only where no secret is kept.
_PS_FLAGS = {"-nologo", "-noprofile", "-noninteractive", "-mta", "-sta"}
_PS_READS = {"get-ciminstance", "get-wmiobject", "get-process", "get-service", "get-date", "get-psdrive", "get-volume", "get-disk",
             "get-partition", "get-physicaldisk", "get-netadapter", "get-netipaddress", "get-netipconfiguration",
             "get-netconnectionprofile", "get-netroute", "get-dnsclientserveraddress", "get-computerinfo", "get-timezone",
             "get-culture", "get-uiculture", "get-hotfix", "get-printer", "get-pnpdevice", "get-appxpackage", "get-startapps",
             "get-localuser", "get-localgroup", "get-scheduledtask", "get-host", "get-executionpolicy", "get-command",
             "get-module", "get-help", "get-member", "select-object", "sort-object", "measure-object", "group-object",
             "format-list", "format-table", "format-wide", "out-string", "select-string", "where-object"}


def _powershell(args) -> bool:
    i = 0
    while i < len(args) and args[i].lower() in _PS_FLAGS:
        i += 1
    if i >= len(args):
        return False
    if args[i].lower() in ("-command", "-c"):
        if i + 2 != len(args):
            return False
        try:
            tokens = shlex.split(args[i + 1])
        except ValueError:
            return False
    elif args[i].startswith("-"):
        return False
    else:
        tokens = list(args[i:])
    segments, current = [], []
    for t in tokens:
        if t in ("|", "||", "&&", ";"):
            if not current:
                return False
            segments.append(current)
            current = []
        elif any(ch in t for ch in "|;<>&$`{}()[]@") or t.startswith("."):
            return False
        else:
            current.append(t)
    if not current:
        return False
    segments.append(current)
    return all(seg[0].lower() in _PS_READS for seg in segments)


def _tasklist(args) -> bool:
    a = [x.lower() for x in args]
    for i, x in enumerate(a):
        if x in ("/v", "/nh", "/svc", "/apps", "/m"):
            continue
        if x in ("/fo", "/fi") and i + 1 < len(a):
            continue
        if i and a[i - 1] in ("/fo", "/fi"):
            continue
        return False
    return True


_REG_KEYS = ("hklm\\software\\microsoft\\windows nt\\currentversion", "hkcu\\software\\microsoft\\windows\\currentversion\\themes",
             "hkcu\\control panel\\desktop", "hkcu\\control panel\\international", "hklm\\system\\currentcontrolset\\control\\timezoneinformation",
             "hklm\\hardware\\description\\system")


def _reg(args) -> bool:
    a = [x.lower().strip('"') for x in args]
    if len(a) < 2 or a[0] != "query" or not any(a[1].startswith(k) for k in _REG_KEYS):
        return False
    return all(x in ("/v", "/ve") or (i and a[i - 1] == "/v") for i, x in enumerate(a[2:], 2))


def _netsh(args) -> bool:
    a = [x.lower() for x in args]
    if any(x.startswith("key") for x in a) or any(x in ("set", "add", "delete", "reset", "connect", "disconnect") for x in a):
        return False
    return ((a[:2] == ["wlan", "show"] and len(a) >= 3 and a[2] in ("interfaces", "networks", "profiles", "drivers", "settings"))
            or (a[:1] == ["interface"] and "show" in a[1:4]))


WINDOWS_LOOK = {
    "powershell.exe": _powershell, "pwsh.exe": _powershell,
    "tasklist.exe": _tasklist,
    "systeminfo.exe": lambda a: all(x.lower() in ("/fo", "table", "list", "csv", "/nh") for x in a),
    "ipconfig.exe": lambda a: all(x.lower() in ("/all", "/displaydns") for x in a),
    "hostname.exe": _no(), "whoami.exe": lambda a: all(x.lower() in ("/user", "/groups", "/priv", "/all", "/upn", "/fqdn", "/logonid") for x in a),
    "tzutil.exe": lambda a: [x.lower() for x in a] == ["/g"],
    "wslpath": _no(), "where.exe": _no(),
    "reg.exe": _reg, "netsh.exe": _netsh,
    "cmd.exe": lambda a: [x.lower() for x in a] == ["/c", "ver"],
    # the filter of a pipe (a file named instead would be read from anywhere: not here)
    "findstr.exe": lambda a: bool(a) and all(re.match(r"^/[a-zA-Z]+(:.*)?$", x) or not any(ch in x for ch in "\\/:") for x in a),
    "find.exe": lambda a: bool(a) and all(re.match(r"^/[a-zA-Z]+$", x) or not any(ch in x for ch in "\\/:") for x in a),
}
LOOK.update(WINDOWS_LOOK)
# PowerShell's own file readers: like `cat` and `ls`, they belong to the file tools, where secrets stay hidden
PS_FILE_READERS = re.compile(r"(?<![\w-])(Get-Content|gc|cat|type|Get-ChildItem|gci|dir|ls|Get-Item|gi|Get-ItemProperty|gp|Test-Path|"
                             r"Resolve-Path|Select-String|sls|Out-File|Set-Content|Add-Content|Copy-Item|Move-Item|Remove-Item|New-Item)(?![\w-])", re.I)
# sent to `pc` or `sysinfo`, these are pointed to `sh`, which reads files with the secret ones hidden
FILE_READERS = ("ls", "cat", "head", "tail", "less", "more", "find", "du", "stat", "tree", "file", "grep", "wc")


def look(command: str) -> str | None:
    """The line to run, when `command` only looks at the computer; None when it may do more or cannot be told.
    What comes back is the words of the line quoted again, a pattern for a readable file replaced by its matches."""
    words = _words(command) if isinstance(command, str) else None
    if not words:
        return None
    out, argv, quiet = [], [], []
    for word, kind in words + [(";", True)]:
        if kind == "quiet":
            quiet.append(word)
            continue
        if not kind:
            if quiet:
                return None                                     # a word after the redirection: not the plain shape
            argv.append(word)
            continue
        if not argv or "/" in argv[0] or argv[0] not in LOOK or not LOOK[argv[0]](argv[1:]):
            return None                                         # also: nothing between two operators
        for i, a in enumerate(argv):
            found = sorted(glob.glob(a)) if i and any(ch in a for ch in "*?[") and _readable(a) else []
            if any(not _readable(f) for f in found):
                return None
            out += [shlex.quote(f) for f in found] or [shlex.quote(a)]
        out += quiet + [word]
        argv, quiet = [], []
    return " ".join(out[:-1])


# the system's package managers, told to change what is installed: that takes an administrator whether or not the
# line says sudo, so it is handed over like a line that does
_INSTALLS = ("install", "remove", "erase", "purge", "autoremove", "upgrade", "update", "dist-upgrade", "full-upgrade", "dup", "up",
             "in", "rm", "add", "del", "downgrade", "reinstall", "refresh")
_INSTALL_FLAGS = {"pacman": r"^-[SRU][a-z]*$", "dpkg": r"^(-i|--install|-r|--remove|-P|--purge)$",
                  "rpm": r"^(-[iUe][a-zA-Z]*|--install|--upgrade|--erase)$"}


class _Managers:
    """`.match(line)`: true when a command of the line is a package manager changing what is installed. Each command
    is judged by its own first words (`apt list --installed | grep -i x` holds an "-i", and is a look)."""

    @staticmethod
    def match(command: str) -> bool:
        for part in re.split(r"&&|\|\||[;|\n]", command or ""):
            words = part.split()
            if not words or words[0] not in ("apt", "apt-get", "dnf", "yum", "zypper", "pacman", "apk", "dpkg", "rpm", "snap"):
                continue
            if words[0] in _INSTALL_FLAGS:
                if any(re.match(_INSTALL_FLAGS[words[0]], w) for w in words[1:]):
                    return True
            elif next((w for w in words[1:] if not w.startswith("-")), "") in _INSTALLS:
                return True
        return False


MANAGERS = _Managers


# ---------------------------------------------------------------------- git --
# A repository is read inside the sandbox like any other files (`sh`). What changes it (a commit, a branch, a stash)
# cannot be carried out of a sandbox, since `.git` is never written by the journal; those lines are `pc`'s, shown and
# asked for, and git's own reflog is what undoes them. Two kinds are not run at all and are handed to the person:
# what reaches a remote while offline, and what discards work that is in no commit.

GIT_READS = ("status", "diff", "log", "show", "blame", "grep", "ls-files", "ls-tree", "rev-parse", "rev-list", "describe",
             "shortlog", "reflog", "cat-file", "merge-base", "name-rev", "whatchanged", "count-objects", "help", "version")
GIT_REMOTE = ("push", "pull", "fetch", "clone", "ls-remote")
GIT_DISCARDS = re.compile(r"^(reset\b.*(--hard|\s(HEAD|@)(~\d*|\^+)(\s|$)|\s[0-9a-f]{7,40}(\s|$))|commit\b.*--amend|clean\b.*(-[a-zA-Z]*f|--force)|"
                          r"checkout\b.*(\s--(\s|$)|\s\.(\s|$))|restore\b(?!.*--staged)|"
                          r"stash\s+(drop|clear)|branch\b.*\s-D\b|push\b.*(--force\b|\s-f\b|--force-with-lease)|filter-branch|"
                          r"reflog\s+expire|gc\b.*--prune|rebase\b|update-ref\b.*-d)")


def git_kind(command: str) -> str | None:
    """What a line's git commands do at most: "read", "write", "remote" (reaches another machine) or "discard"
    (throws away work that is in no commit, or rewrites what is). None for a line with no git command in it."""
    worst, order = None, ("read", "write", "remote", "discard")
    for part in re.split(r"&&|\|\||[;|\n]", command or ""):
        words = part.split()
        if not words or words[0] != "git":
            continue
        rest, skip = [], False
        for w in words[1:]:                                     # past git's own options to the command
            if skip:
                skip = False
            elif not rest and w in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
                skip = True
            elif not rest and w.startswith("-"):
                continue
            else:
                rest.append(w)
        sub, tail = (rest[0] if rest else "help"), " ".join(rest)
        if GIT_DISCARDS.match(tail):
            kind = "discard"
        elif sub in GIT_REMOTE or tail.startswith(("remote update", "submodule update")):
            kind = "remote"
        elif sub in GIT_READS or tail in ("branch", "tag", "remote", "stash list", "remote -v", "branch -a", "branch -v", "branch -vv",
                                           "branch --list", "tag -l", "tag --list") or tail.startswith(("config --get", "config --list", "config -l", "stash show")):
            kind = "read"
        else:
            kind = "write"
        worst = kind if worst is None or order.index(kind) > order.index(worst) else worst
    return worst


def refusal(command: str, offline: bool = False) -> str | None:
    """Why a line is not run from here and what to do instead, or None."""
    git = git_kind(command)
    if git == "discard":
        return ("it throws away work that is in no commit, or rewrites what is, and nothing here can put that back. "
                f"dawnr does not run it; the person can, exactly as written: {command}")
    if git == "remote" and offline:
        return ("the network is off in this session, and it reaches another machine. Only the person can turn the network "
                "on, by starting dawnr again with --online. Tell them that")
    if git == "read":
        return "that only reads the repository: `sh` does that, with the same line"
    if offline and NETWORK.search(command):
        return ("the network is off in this session, and nothing here can turn it on: only the person can, by starting "
                "dawnr again with --online. Tell them that")
    if PRIVILEGED.search(command):
        return ("it asks for administrator rights, which dawnr never takes. The person can run it themselves, exactly "
                f"as written: {command}")
    if MANAGERS.match(command):
        return ("it changes what is installed, which takes administrator rights, and dawnr never takes them. The person "
                f"can run it themselves: sudo {command.strip()}")
    if re.match(r"\s*dawnr\b", command):
        return "dawnr does not start itself: how it is started is the person's to decide"
    secret = SECRET.search(command) or WINDOWS_SECRET.search(command)
    if secret:
        return f"it names a place where secrets are kept (`{secret.group(1) or secret.group(0)}`), and dawnr does not read or pass on what is there"
    for pattern, instead in FORBIDDEN:
        if pattern.search(command):
            return instead
    if look(command) is not None:
        return "that only looks, and needs nobody's yes: call `sysinfo` with it"
    if re.match(r"\s*(%s)\b" % "|".join(FILE_READERS), command):
        return "reading and listing files is done with fs_list, fs_read and fs_search, or with `sh`"
    if re.match(r"\s*(powershell|pwsh)(\.exe)?\b", command, re.I) and PS_FILE_READERS.search(command):
        return ("reading, listing and changing files is done with fs_list, fs_read, fs_search, fs_write and fs_edit, or with `sh` "
                "(a Windows folder is reachable under /mnt/c)")
    return None


class SystemTools:
    def __init__(self, *, timeout: float = 60.0, max_output: int = 4000, runner=run_argv, starter=subprocess.Popen,
                 reader=run_argv, offline=lambda: True, act: bool = False, cwd: str | None = None,
                 exec_path: str | None = None):
        self.timeout, self.max_output, self.runner, self.starter, self.offline = timeout, max_output, runner, starter, offline
        self.reader, self.act = reader, False                   # legacy `act` cannot restore the retired host tool
        self.env = {k: v for k, v in os.environ.items() if k in SESSION}
        # The CLI supplies safe_exec_path(space): repository programs cannot
        # impersonate a read-only utility or the shell executing its pipeline.
        self.env["PATH"] = os.defpath if exec_path is None else exec_path
        # where a command starts: the folder the session works in, as a terminal opened there would
        self.cwd = cwd or self.env.get("HOME") or os.path.expanduser("~")

    def _run(self, runner, line: str) -> ToolResult:
        shell = shutil.which("bash", path=self.env["PATH"]) or "/bin/sh"
        got = runner([shell, "-c", line], cwd=self.cwd, env=self.env, timeout=self.timeout, max_output=self.max_output * 4)
        text = got["stdout"].rstrip("\n") + (("\n[stderr]\n" + got["stderr"].rstrip("\n")) if got["stderr"].strip() else "")
        if len(text) > self.max_output:
            text = text[:self.max_output * 3 // 5] + "\n[...]\n" + text[-(self.max_output * 2 // 5):]
        head = f"timed out after {got['seconds']:.0f} s" if got["timed_out"] else f"exit {got['exit']}"
        if not text and not got["timed_out"]:                   # "exit 0" alone was taken for nothing having happened,
            head += ": it ran and printed nothing" if got["exit"] == 0 else ": it failed and printed nothing"   # and sent again
        return ToolResult(head + ("\n" + text if text else ""), is_error=bool(got["timed_out"] or got["exit"]), trust="untrusted")

    def decide_sysinfo(self, args: dict) -> tuple[str, str]:
        command = args.get("command")
        if not isinstance(command, str) or not command.strip() or len(command) > MAX_COMMAND:
            return "deny", f"sysinfo: give the command as one line of text, at most {MAX_COMMAND} characters"
        if look(command) is not None:
            return "allow", ""
        if re.match(r"\s*(%s)\b" % "|".join(FILE_READERS), command):
            return "deny", "sysinfo: reading and listing files is done with fs_list, fs_read and fs_search, or with `sh`"
        return "deny", ("sysinfo: this is not a line that is known only to look (one read-only command, or several joined "
                        "by | with no redirection, variable or substitution)."
                        + " Host changes are not supported.")

    def sysinfo(self, args: dict, ctx: CallContext) -> ToolResult:
        line = look(args.get("command"))
        if line is None:
            return ToolResult("refused: " + self.decide_sysinfo(args)[1], is_error=True)
        return self._run(self.reader, line)

    def decide(self, args: dict) -> tuple[str, str]:
        return "deny", "pc: host control has been retired; use repository file tools and sandboxed tests"

    def pc(self, args: dict, ctx: CallContext) -> ToolResult:
        """Fail closed for an old caller, even with approval or `detach` supplied."""
        return ToolResult("refused: " + self.decide(args)[1], is_error=True)

    def tools(self) -> list[Tool]:
        line = {"type": "string", "minLength": 1, "maxLength": MAX_COMMAND}
        looks = Tool("sysinfo", "The live state of this computer, not its files: what is running, memory and disk space, "
                                "the network, services, sound, settings, what is installed. One read-only command, or "
                                "several joined by | (df -h; ps aux --sort=-%mem | head; systemctl status cups; nmcli "
                                "device status). It runs at once. `apropos WORD` finds the program for a job and "
                                "`man NAME | head -40` says how it is called.",
                     {"type": "object", "properties": {"command": line}, "required": ["command"], "additionalProperties": False},
                     self.sysinfo, permission="allow", trust="untrusted", network=False, consequential=False,
                     origin="agent", decide_call=self.decide_sysinfo)
        return [looks]
