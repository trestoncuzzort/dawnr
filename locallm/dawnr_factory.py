"""dawnr_factory.py: tasks by the thousand for a driver to be taught on, each made with its own judge and its own
solution (2026-10-05).

`locallm/dawnr_tasks.py` holds 161 tasks written by hand; they measure, and nothing is trained on them. Four sizes
of driver read them: on short work nothing separates a 4B from a 35B, and on longer work the 4B does 19 of 26 where
the 35B does 25 (PREDICT-2026-10-05-assistant.md). The project's own method for such a gap is to let the larger
model do the work, keep only what an independent check admits, and train the smaller one on that (SAFE,
arXiv:2410.15756; this repository's teacher rounds). Here the check is the task's judge: the folder's end state,
the line let through, the answer against what the files or the machine say. A trajectory is kept only when the
judge says done and nothing was touched or let through that the task did not ask for.

That needs tasks in number, and no model writes them: each *family* is a small program that draws a task from a
seed (its files, its request in one of several wordings, what must hold at the end) together with a solution, a
piece of work that is right. A task is used only if the judge calls it not done as it starts and done once its
solution is in place (`selfcheck`): a task nobody can pass, or one a wrong state passes, would teach the wrong
thing or throw good work away.

    python3 locallm/dawnr_factory.py --list                    # the families and what each is
    python3 locallm/dawnr_factory.py --check 20                # 20 seeds of every family through selfcheck
    python3 locallm/dawnr_factory.py --show rename_numbered 3  # one task, as the driver would get it

What is kept apart from the measuring tasks. No family is one of the 161 with other names: `twin` holds each
measuring request, and a made task whose request is the same sentence (names and numbers aside) is refused. The
skills overlap, as they must; the instances do not.

What never enters a row. The machine a task is run on is somebody's: its host name, its user, its addresses. A
question about "this computer" is therefore asked of a described machine (`Machine`, below), whose every answer is
made up from the seed, and a trajectory that mentions the real home folder, user or host is thrown away
(`identifiers`).
"""
from __future__ import annotations

import argparse
import getpass
import os
import random
import re
import socket
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "t"))

FAMILIES: dict = {}

PEOPLE = ("Ana", "Bo", "Cy", "Dara", "Eli", "Fay", "Gus", "Hana", "Ivo", "Jun", "Kit", "Lena", "Milo", "Nia", "Oren", "Pia", "Quin", "Rosa",
          "Sol", "Tess", "Uma", "Vik", "Wren", "Xan", "Yara", "Zed")
THINGS = ("lamp", "desk", "chair", "kettle", "ladder", "radio", "tent", "stove", "shelf", "mirror", "clock", "basket", "bench", "drill", "fan",
          "globe", "heater", "iron", "jug", "kite", "locker", "mug", "notebook", "oven", "pump", "quilt", "rug", "saw", "tray", "vase")
PLACES = ("Lisbon", "Oslo", "Quito", "Hanoi", "Lagos", "Perth", "Turin", "Kyoto", "Bergen", "Dakar", "Malmo", "Porto", "Riga", "Tunis", "Split")
STEMS = ("notes", "draft", "report", "summary", "plan", "list", "ledger", "minutes", "budget", "survey", "outline", "memo", "log", "index",
         "agenda", "review", "sketch", "digest", "record", "brief")
PACKAGES = ("htop", "tree", "jq", "ripgrep", "tmux", "curl", "rsync", "ncdu", "fzf", "bat", "nmap", "git", "vim", "zip", "unzip", "wget")
SERVICES = ("syncthing", "mpd", "redshift", "dunst", "emacs", "ssh-agent", "pipewire", "gpg-agent")
SYSTEM_SERVICES = ("nginx", "bluetooth", "cups", "ssh", "cron", "docker", "postgresql", "NetworkManager")


def family(fn):
    """Register a family: fn(rng) -> {"kind", "files", "request", "expect", "solution"} (see `make`)."""
    FAMILIES[fn.__name__] = fn
    return fn


def say(rng: random.Random, *ways: str) -> str:
    """One of several wordings of the same request."""
    return rng.choice(ways)


def make(name: str, seed: int) -> dict:
    """The task a family draws from a seed, the same every time:

        kind      a word for the summary's table
        files     {relative path: text or bytes} the folder starts with
        request   what the person asks, in one of the family's wordings
        expect    the judge's keys (dawnr_tasks.judge): files, json, answer, any, says, lacks, run, fn, pc, ...
        solution  {"answer": text, "files": {path: text or None to remove}, "acted": [pc lines]}: work that is right
        machine   optionally a `Machine`: the computer the task is about, described and simulated
    """
    rng = random.Random(f"{name}:{seed}")
    task = FAMILIES[name](rng)
    task.update(id=f"{name}:{seed}", family=name)
    task.setdefault("solution", {})
    for key, value in (("answer", ""), ("files", {}), ("acted", [])):
        task["solution"].setdefault(key, value)
    return task


def as_tuple(task: dict) -> tuple:
    """The shape dawnr_tasks.run_one takes."""
    expect = dict(task["expect"])
    if task.get("machine") is not None:
        expect["machine"], expect["simulated"] = task["machine"].sentence, task["machine"]
    return (task["id"], task["kind"], task["files"], task["request"], expect)


# ------------------------------------------------------------- a described machine --

class Machine:
    """A computer that exists only as a description: what its commands print is made up from a seed, so that a
    question about "this computer" has an answer that is nobody's. `run(line)` answers a line the way `sysinfo`
    would have; a program it does not have is "command not found", like the shell's."""

    def __init__(self, rng: random.Random):
        self.host = rng.choice(STEMS) + "-" + rng.choice(("box", "pc", "node", "station", "book")) + str(rng.randint(2, 99))
        self.user = rng.choice(PEOPLE).lower()
        self.distro, self.version, self.manager = rng.choice((("Ubuntu", "24.04.3 LTS", "apt"), ("Debian GNU/Linux", "13 (trixie)", "apt"), ("Fedora Linux", "42 (Workstation Edition)", "dnf"),
                                                              ("Arch Linux", "", "pacman"), ("openSUSE Tumbleweed", "", "zypper"), ("Linux Mint", "22.1", "apt")))
        self.desktop = rng.choice(("GNOME", "GNOME", "KDE", "KDE", "XFCE", ""))
        self.kernel = f"{rng.randint(5, 6)}.{rng.randint(1, 15)}.{rng.randint(0, 20)}-{rng.randint(1, 60)}-generic"
        self.cpus = rng.choice((2, 4, 6, 8, 12, 16, 24, 32))
        self.cpu_model = rng.choice(("AMD Ryzen 5 5600X 6-Core Processor", "Intel(R) Core(TM) i7-1165G7 CPU @ 2.80GHz", "AMD Ryzen 7 7840U w/ Radeon 780M Graphics",
                                     "Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz", "AMD Ryzen 9 5950X 16-Core Processor", "Intel(R) Xeon(R) E-2276M CPU @ 2.80GHz"))
        self.memory_gib = rng.choice((4, 8, 16, 32, 64))
        self.memory_used = round(self.memory_gib * rng.uniform(0.2, 0.8), 1)
        self.disk_gib, self.disk_used = rng.choice(((120, 0.31), (250, 0.58), (500, 0.44), (1000, 0.71), (2000, 0.12)))
        self.timezone = rng.choice(("Europe/Lisbon", "America/Chicago", "Asia/Tokyo", "Europe/Oslo", "Africa/Lagos", "Australia/Perth", "America/Lima"))
        self.address = f"192.168.{rng.randint(0, 20)}.{rng.randint(2, 250)}"
        self.uptime_days = rng.randint(0, 40)
        self.dark = rng.random() < 0.5
        self.volume = rng.choice((0.25, 0.4, 0.55, 0.7, 1.0))
        self.active = set(rng.sample(SYSTEM_SERVICES, rng.randint(2, 5)))
        self.installed = {p: f"{rng.randint(0, 9)}.{rng.randint(0, 30)}.{rng.randint(0, 9)}" for p in rng.sample(PACKAGES, rng.randint(5, 10))}
        self.processes = [(rng.randint(900, 60000), p, round(rng.uniform(0.1, 9.0), 1), round(rng.uniform(0.1, 12.0), 1))
                          for p in rng.sample(("firefox", "code", "python3", "gnome-shell", "Xorg", "pipewire", "node", "postgres", "nginx", "thunderbird", "steam", "java"), rng.randint(4, 8))]

    @property
    def sentence(self) -> str:
        services = ", services with systemd"
        desktop = f"desktop {self.desktop} on wayland" if self.desktop else "no desktop session"
        return f"This computer: {self.distro} {self.version}".rstrip() + f", packages with {self.manager}{services}, {desktop}."

    @property
    def top_process(self) -> tuple:
        return max(self.processes, key=lambda p: p[3])

    def _one(self, argv: list) -> tuple[int, str]:
        name, args = argv[0], argv[1:]
        free = self.disk_gib * (1 - self.disk_used)
        if name == "hostname":
            return 0, self.address if "-I" in args else self.host
        if name == "whoami":
            return 0, self.user
        if name == "uname":
            return 0, (f"Linux {self.host} {self.kernel} #1 SMP PREEMPT_DYNAMIC x86_64 GNU/Linux" if "-a" in args else self.kernel if "-r" in args else "Linux")
        if name == "nproc":
            return 0, str(self.cpus)
        if name == "lscpu":
            return 0, f"Architecture:            x86_64\nCPU(s):                  {self.cpus}\nModel name:              {self.cpu_model}\nThread(s) per core:      2"
        if name == "free":
            total, used = self.memory_gib, self.memory_used
            unit = "Gi" if any(a in ("-h", "--human") for a in args) else ""
            scale = 1 if unit else 1024 * (1024 if "-m" not in args else 1)
            row = lambda a, b: f"{a * scale:.1f}{unit}" if unit else f"{int(a * scale)}"
            return 0, (f"               total        used        free      shared  buff/cache   available\nMem:      {row(total, 0):>10}  {row(used, 0):>10}  {row(total - used, 0):>10}"
                       f"  {row(0.3, 0):>10}  {row(1.0, 0):>10}  {row(total - used, 0):>10}\nSwap:     {row(2, 0):>10}  {row(0, 0):>10}  {row(2, 0):>10}")
        if name == "df":
            return 0, (f"Filesystem      Size  Used Avail Use% Mounted on\n/dev/nvme0n1p2  {self.disk_gib}G  {self.disk_gib * self.disk_used:.0f}G  {free:.0f}G  {self.disk_used * 100:.0f}% /\n"
                       "tmpfs           3.9G     0  3.9G   0% /dev/shm")
        if name == "uptime":
            return 0, f" 10:14:07 up {self.uptime_days} days,  3:02,  1 user,  load average: 0.42, 0.37, 0.31"
        if name == "date":
            return 0, "Mon Oct  5 10:14:07 UTC 2026"
        if name == "timedatectl":
            return 0, f"               Local time: Mon 2026-10-05 10:14:07\n                Time zone: {self.timezone} (+00, +0000)\nSystem clock synchronized: yes\n              NTP service: active"
        if name == "cat" and args[-1:] in (["/etc/os-release"], ["/usr/lib/os-release"]):
            return 0, f'PRETTY_NAME="{(self.distro + " " + self.version).strip()}"\nNAME="{self.distro}"\nVERSION_ID="{self.version.split()[0] if self.version else ""}"\nID={self.distro.split()[0].lower()}'
        if name == "cat" and args[-1:] == ["/etc/hostname"]:
            return 0, self.host
        if name == "cat" and args[-1:] == ["/proc/meminfo"]:
            return 0, f"MemTotal:       {self.memory_gib * 1024 * 1024} kB\nMemFree:        {int((self.memory_gib - self.memory_used) * 1024 * 1024)} kB"
        if name == "cat" and args[-1:] == ["/proc/cpuinfo"]:
            return 0, "\n".join(f"processor\t: {i}\nmodel name\t: {self.cpu_model}" for i in range(self.cpus))
        if name == "lsb_release":
            return 0, f"Distributor ID:\t{self.distro.split()[0]}\nDescription:\t{(self.distro + ' ' + self.version).strip()}\nRelease:\t{self.version.split()[0] if self.version else 'rolling'}"
        if name in ("ps", "top"):
            rows = sorted(self.processes, key=lambda p: -p[3] if any("mem" in a for a in args) else -p[2])
            return 0, "USER         PID %CPU %MEM COMMAND\n" + "\n".join(f"{self.user:<10} {pid:>6} {cpu:>4} {mem:>4} {cmd}" for pid, cmd, cpu, mem in rows)
        if name in ("pgrep", "pidof"):
            want = next((a for a in args if not a.startswith("-")), "")
            found = [str(pid) for pid, cmd, _c, _m in self.processes if want and want in cmd]
            return (0, "\n".join(found)) if found else (1, "")
        if name == "systemctl":
            words = [a for a in args if not a.startswith("-")]
            if words[:1] in (["is-active"], ["status"]) and len(words) > 1:
                unit = words[1].removesuffix(".service")
                if unit in self.active:
                    return 0, "active" if words[0] == "is-active" else f"* {unit}.service - {unit}\n     Loaded: loaded (/usr/lib/systemd/system/{unit}.service; enabled)\n     Active: active (running) since Mon 2026-10-05 07:12:01 UTC; 3h 2min ago"
                if unit in SYSTEM_SERVICES:
                    return 3, "inactive" if words[0] == "is-active" else f"o {unit}.service - {unit}\n     Loaded: loaded (/usr/lib/systemd/system/{unit}.service; disabled)\n     Active: inactive (dead)"
                return 4, f"Unit {unit}.service could not be found."
            if words[:1] == ["list-units"]:
                return 0, "\n".join(f"  {unit}.service loaded active running {unit}" for unit in sorted(self.active))
            return 1, "Unknown command verb."
        if name in ("ip",):
            return 0, f"lo               UNKNOWN        127.0.0.1/8\nenp3s0           UP             {self.address}/24"
        if name == "nmcli":
            return 0, "DEVICE  TYPE      STATE      CONNECTION\nenp3s0  ethernet  connected  Wired connection 1\nlo      loopback  connected (externally)  lo"
        if name == "gsettings" and args[:1] == ["get"] and self.desktop == "GNOME":
            return (0, "'prefer-dark'" if self.dark else "'default'") if "color-scheme" in args else (0, "''")
        if name == "wpctl" and args[:1] == ["get-volume"]:
            return 0, f"Volume: {self.volume:.2f}"
        if name in ("which", "command", "type"):
            want = args[-1] if args else ""
            known = {"apt": "apt", "dnf": "dnf", "pacman": "pacman", "zypper": "zypper"}
            have = want in self.installed or want in ("ls", "cat", "bash", "python3", "systemctl", "git", self.manager) or (want in known and known[want] == self.manager)
            return (0, f"/usr/bin/{want}") if have else (1, "")
        if name == "dpkg" and self.manager == "apt" and args[:1] in (["-s"], ["-l"]):
            want = args[1] if len(args) > 1 else ""
            if want in self.installed:
                return 0, f"Package: {want}\nStatus: install ok installed\nVersion: {self.installed[want]}" if args[0] == "-s" else f"ii  {want}  {self.installed[want]}  amd64  {want}"
            return (1, f"dpkg-query: package '{want}' is not installed and no information is available") if want else (0, "\n".join(f"ii  {p}  {v}  amd64  {p}" for p, v in sorted(self.installed.items())))
        if name == "rpm" and self.manager in ("dnf", "zypper") and args[:1] in (["-q"], ["-qa"]):
            want = args[1] if len(args) > 1 else ""
            if args[0] == "-qa":
                return 0, "\n".join(f"{p}-{v}-1.x86_64" for p, v in sorted(self.installed.items()))
            return (0, f"{want}-{self.installed[want]}-1.x86_64") if want in self.installed else (1, f"package {want} is not installed")
        if name == "pacman" and self.manager == "pacman" and args[:1] and args[0].startswith("-Q"):
            want = args[1] if len(args) > 1 else ""
            if not want:
                return 0, "\n".join(f"{p} {v}-1" for p, v in sorted(self.installed.items()))
            return (0, f"{want} {self.installed[want]}-1") if want in self.installed else (1, f"error: package '{want}' was not found")
        if name == "apt" and self.manager == "apt" and args[:1] == ["list"]:
            return 0, "Listing...\n" + "\n".join(f"{p}/stable,now {v} amd64 [installed]" for p, v in sorted(self.installed.items()))
        if name in self.installed and args[:1] in (["--version"], ["-V"], ["version"]):
            return 0, f"{name} {self.installed[name]}"
        if name == "echo":
            return 0, " ".join(args)
        if name in ("true",):
            return 0, ""
        return 127, f"bash: line 1: {name}: command not found"

    def run(self, line: str) -> dict:
        """What `sysinfo` gets back for a line (pipes into grep, head, tail, wc and sort are carried out)."""
        import shlex
        out, code = "", 0
        for part in re.split(r"\s*(?:&&|;)\s*", line.strip()):
            pieces = [p.strip() for p in part.split("|")]
            try:
                first = shlex.split(re.sub(r"\s*(2>\s*/dev/null|2>&1|>\s*/dev/null)", "", pieces[0]))
            except ValueError:
                first = pieces[0].split()
            if not first:
                continue
            code, text = self._one(first)
            for piece in pieces[1:]:
                try:
                    words = shlex.split(re.sub(r"\s*(2>\s*/dev/null|2>&1)", "", piece))
                except ValueError:
                    words = piece.split()
                lines = text.split("\n") if text else []
                if words[:1] == ["grep"]:
                    pattern = next((w for w in words[1:] if not w.startswith("-")), "")
                    flags = "".join(w[1:] for w in words[1:] if w.startswith("-") and not w.startswith("--"))
                    try:
                        hit = lambda l: bool(re.search(pattern.replace("\\|", "|"), l, re.I if "i" in flags else 0))
                        lines = [l for l in lines if hit(l) != ("v" in flags)]
                    except re.error:
                        lines = [l for l in lines if (pattern in l) != ("v" in flags)]
                    text, code = ("\n".join(lines) if "c" not in flags else str(len(lines))), (0 if lines else 1)
                elif words[:1] in (["head"], ["tail"]):
                    n = next((int(re.sub(r"\D", "", w)) for w in words[1:] if re.search(r"\d", w)), 10)
                    text = "\n".join(lines[:n] if words[0] == "head" else lines[-n:])
                elif words[:1] == ["wc"]:
                    text = str(len(lines))
                elif words[:1] == ["sort"]:
                    text = "\n".join(sorted(lines, reverse="-r" in words or "-rn" in words or "-nr" in words))
                elif words[:1] in (["awk"], ["cut"], ["tr"], ["sed"], ["xargs"], ["column"]):
                    text = text                                 # left as it is: the columns are short enough to read
                else:
                    code, text = 127, f"bash: line 1: {words[0] if words else '?'}: command not found"
            out += (text + "\n") if text else ""
        return {"exit": code, "seconds": 0.0, "timed_out": False, "stdout": out, "stderr": "" if code != 127 else out, "bytes_out": len(out), "bytes_err": 0}


# ------------------------------------------------------------------ the gates --

def identifiers() -> list:
    """What must not be in a row: this machine's own names."""
    names = {str(Path.home()), socket.gethostname(), getpass.getuser() + "@"}
    return sorted(n for n in names if n and len(n) >= 3)


def _shape(text: str) -> str:
    """A request with its names and numbers taken out: two requests of one shape ask the same thing."""
    text = re.sub(r"`[^`]*`|\"[^\"]*\"|'[^']*'", "Q", text.lower())
    text = re.sub(r"\b[\w.-]+\.[a-z0-9]{1,5}\b|\b[\w-]*\d[\w-]*\b", "N", text)
    return " ".join(re.sub(r"[^a-zN Q]", " ", text).split())


def twin(task: dict) -> str | None:
    """The measuring task this one is the same request as, names and numbers aside; None when it is its own."""
    import dawnr_tasks
    shape = _shape(task["request"])
    for tasks in dawnr_tasks.SETS.values():
        for held in tasks:
            if _shape(held[3]) == shape:
                return f"the same request as measuring task {held[0]}: {held[3][:80]}"
    return None


def selfcheck(task: dict, tmp: Path, shell_for=None) -> list:
    """Why a task cannot be used, or []: it must start not done, end done under its own solution with nothing else
    touched, and be nobody's twin. `shell_for(work)` gives a sandbox for the checks that run the result."""
    import dawnr_tasks
    why = [twin(task)] if twin(task) else []
    work = tmp / "work"
    work.mkdir(parents=True, exist_ok=True)
    for rel, text in task["files"].items():
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    expect = as_tuple(task)[4]
    if expect.get("setup"):
        expect["setup"](work)
    before = dawnr_tasks.snapshot(work)
    shell = shell_for(work) if shell_for is not None else None
    if "run" in expect and shell is None:
        return why + ["its check runs the result, and there is no sandbox here"]
    start = dawnr_tasks.judge(work, before, "I looked at the folder.", expect, shell, [])
    if start["done"]:
        why.append("it is done before anything is done")
    for rel, text in task["solution"]["files"].items():
        if text is None:
            (work / rel).unlink()
        else:
            (work / rel).parent.mkdir(parents=True, exist_ok=True)
            (work / rel).write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    # folders a move left empty, deepest first. (The first version looked only at the parents of what was still on
    # disk, and an emptied folder is nothing's parent: no folder was ever removed.)
    for folder in sorted((p for p in work.rglob("*") if p.is_dir() and not p.is_symlink()), key=lambda p: -len(p.parts)):
        if not any(folder.iterdir()) and task["solution"].get("prune", True):
            folder.rmdir()
    if shell is not None:
        from dawnr_agent.shell import _force_remove
        for run in list(shell.runs.values()):
            _force_remove(shell.runs.pop(run.id).scratch)
    end = dawnr_tasks.judge(work, before, task["solution"]["answer"], expect, shell, list(task["solution"]["acted"]))
    if not end["done"] or end["harm"]:
        why.append(f"its own solution is judged {end}")
    return why


def main(argv=None) -> int:
    import dawnr_families  # noqa: F401  (registers the families)
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--check", type=int, metavar="SEEDS", help="this many seeds of every family (or of --family) through selfcheck")
    ap.add_argument("--family", action="append")
    ap.add_argument("--show", nargs=2, metavar=("FAMILY", "SEED"))
    a = ap.parse_args(argv)
    if a.list:
        for name, fn in sorted(FAMILIES.items()):
            print(f"{name:28s} {(fn.__doc__ or '').strip().splitlines()[0] if fn.__doc__ else ''}")
        print(f"{len(FAMILIES)} families")
    if a.show:
        task = make(a.show[0], int(a.show[1]))
        print("REQUEST:", task["request"])
        for rel, text in task["files"].items():
            print(f"--- {rel}\n{text if isinstance(text, str) else f'<{len(text)} bytes>'}"[:600])
        print("EXPECT:", {k: (v if not callable(v) else "<function>") for k, v in task["expect"].items()})
        print("SOLUTION:", str(task["solution"])[:800])
        if task.get("machine") is not None:
            print("MACHINE:", task["machine"].sentence)
    if a.check:
        import tempfile
        import dawnr_cli as cli
        from dawnr_agent.shell import _force_remove
        bad = total = 0
        for name in sorted(a.family or FAMILIES):
            shapes = set()
            for seed in range(a.check):
                task, base = make(name, seed), Path(tempfile.mkdtemp(prefix="dawnr-factory-"))
                opened = []

                def shell_for(work, base=base, opened=opened):
                    harness, agent = cli.build_agent(cli.default_config(work, state=base / "state"))
                    opened.append(harness)
                    return agent.shell
                try:
                    why = selfcheck(task, base, shell_for if "run" in task["expect"] else None)
                finally:
                    for harness in opened:
                        harness.close()
                    _force_remove(str(base))
                total += 1
                shapes.add((task["request"], tuple(sorted(task["files"]))))
                if why:
                    bad += 1
                    print(f"{task['id']}: " + "; ".join(why)[:400])
            print(f"{name:28s} {a.check} seeds, {len(shapes)} different tasks")
        print(f"{total - bad} of {total} usable")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    import dawnr_factory                    # the families register with the module of that name, not with __main__
    raise SystemExit(dawnr_factory.main())
