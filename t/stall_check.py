#!/usr/bin/env python3
"""t/stall_check.py -- is the machine quiet enough to trust a run? (r12
blocker A5, 2026-09-25)

    python3 t/stall_check.py [--watch DIR [--stale MIN]] [--frozen PATH]

Exit 0 when nothing below is found, 1 with one line per problem, 2 when
/proc could not be read. It never reports clean when it could not look.

  STOPPED  a process of this user in state T, stopped on a signal. The
           cpu-yield watcher froze the grader on 2026-09-20 and died
           without resuming it; the run sat at 0% for hours and looked
           alive. A tracing stop (state t, a debugger) is not counted.
  FROZEN   a pid listed in ~/.local/share/cpu-yield/frozen.pids that is
           alive and ours. A listed pid that started after the file was
           last written, or that belongs to another user, is a reused pid
           and is printed as a note, not a problem: a freeze appends to the
           file after the process started, so a real freeze is always older
           than the file.
  ORPHAN   a prover of ours whose parent is pid 1 or a process named
           systemd. An orphan is reparented to the nearest living subreaper
           (PR_SET_CHILD_SUBREAPER(2const)), and the user's own systemd is
           one, so "parent 1" alone would miss every orphan on a desktop
           session; on the lab, over ssh, 27 z3 processes sat under pid 1
           on 2026-09-21 after their gnatprove had exited.
  STALE    with --watch DIR --stale MIN: the newest file under DIR is older
           than MIN minutes, or DIR has no file. Airflow fails a task whose
           heartbeat is older than a timeout instead of trusting it; here
           the heartbeat is the newest output the run wrote.

Everything is read from /proc: /proc/<pid>/stat gives comm (in
parentheses, at most 15 characters, possibly holding spaces and parens, so
the line is split at the LAST ')'), state, ppid and starttime;
/proc/<pid>/status gives the real uid; /proc/stat gives btime
(proc_pid_stat(5), fetched 2026-09-25 from man7.org/linux/man-pages/man5/
proc_pid_stat.5.html). It never reads a command line: a pattern over argv
matches its own shell, and that has broken three times here. It reports;
it does not resume, kill or write anything.

Limits, stated so nobody trusts a clean exit for more than it says: a
prover that escaped its process group with setsid/setpgid is seen here
only once it is orphaned; a watcher killed with SIGKILL runs no trap, so
its freezes stay until this script names them and a person runs
`yield-watch.sh --thaw`; a process of ours stopped on purpose (^Z in a
shell) is a STOPPED finding too, and that is the intended reading, since
the run checklist wants nothing of ours stopped.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

PROVERS = frozenset({
    # the scope's list
    "z3", "cvc5", "alt-ergo", "gnatprove", "gnatwhy3", "why3server", "lean",
    "coqc", "dafny", "verus", "fstar.exe",
    # names measured on the lab: opam's rocq, gnatprove's libexec, verus's own z3
    "rocq", "rocqworker", "rocqworker_wit", "coqchk", "rocqchk", "frama-c",
    "rust_verify", "gnat2why", "why3", "why3cpulimit",
})
SUBREAPER_NAMES = frozenset({"systemd"})
DEFAULT_FROZEN = Path.home() / ".local" / "share" / "cpu-yield" / "frozen.pids"
DEFAULT_STALE_MIN = 27


@dataclass(frozen=True)
class Proc:
    pid: int
    comm: str
    state: str
    ppid: int
    uid: int | None
    start: float          # epoch seconds, from btime + starttime / CLK_TCK


def parse_stat(text: str) -> tuple[str, str, int, int]:
    """(comm, state, ppid, starttime_ticks) from one /proc/<pid>/stat line.
    comm is split at the last ')' because it may itself contain ')' or
    spaces (proc_pid_stat(5) field 2)."""
    head, _, tail = text.rpartition(")")
    comm = head.split("(", 1)[1]
    fields = tail.split()
    # tail starts at field 3 (state); starttime is field 22, so index 22 - 3
    return comm, fields[0], int(fields[1]), int(fields[19])


def read_uid(status_text: str) -> int | None:
    for line in status_text.splitlines():
        if line.startswith("Uid:"):
            parts = line.split()
            if len(parts) > 1 and parts[1].isdigit():
                return int(parts[1])
    return None


def boot_time(proc_root: Path) -> float:
    for line in (proc_root / "stat").read_text().splitlines():
        if line.startswith("btime "):
            return float(line.split()[1])
    raise OSError(f"no btime in {proc_root / 'stat'}")


def scan(proc_root: Path, clk_tck: float) -> dict[int, Proc]:
    """Every process readable under proc_root. One that vanishes between
    the listing and the read is skipped: it is gone, not a finding."""
    btime = boot_time(proc_root)
    procs: dict[int, Proc] = {}
    for entry in os.listdir(proc_root):
        if not entry.isdigit():
            continue
        pid = int(entry)
        try:
            comm, state, ppid, start_ticks = parse_stat((proc_root / entry / "stat").read_text())
        except (OSError, IndexError, ValueError):
            continue
        try:
            uid = read_uid((proc_root / entry / "status").read_text())
        except OSError:
            uid = None
        procs[pid] = Proc(pid, comm, state, ppid, uid, btime + start_ticks / clk_tck)
    return procs


def read_frozen(path: Path) -> tuple[list[int], float | None]:
    """The pids listed in frozen.pids and the file's mtime; ([], None) when
    there is no file, which means nothing is frozen."""
    try:
        text = path.read_text()
        mtime = path.stat().st_mtime
    except OSError:
        return [], None
    pids = []
    for line in text.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids, mtime


def check(procs: dict[int, Proc], uid: int, frozen: Path | None = None,
          watch: Path | None = None, stale_min: float = DEFAULT_STALE_MIN,
          now: float | None = None) -> tuple[list[str], list[str]]:
    """(problems, notes), one string each, over an already-scanned table."""
    problems, notes = [], []
    mine = {p.pid: p for p in procs.values() if p.uid == uid}
    for p in sorted(mine.values(), key=lambda q: q.pid):
        if p.state == "T":
            problems.append(f"STOPPED pid {p.pid} ({p.comm}) state T, parent {p.ppid}")
    for p in sorted(mine.values(), key=lambda q: q.pid):
        if p.comm not in PROVERS:
            continue
        parent = procs.get(p.ppid)
        if p.ppid == 1 or (parent is not None and parent.comm in SUBREAPER_NAMES):
            who = "pid 1" if p.ppid == 1 else f"{parent.comm} (pid {p.ppid})"
            problems.append(f"ORPHAN pid {p.pid} ({p.comm}) parent {who}: its driver is gone")
    if frozen is not None:
        listed, mtime = read_frozen(frozen)
        for pid in listed:
            p = procs.get(pid)
            if p is None or p.state in ("Z", "X"):
                continue
            if p.uid != uid:
                notes.append(f"note: frozen.pids lists {pid}, now another user's process (pid reused)")
                continue
            if mtime is not None and p.start > mtime:
                notes.append(f"note: frozen.pids lists {pid}, which started after the file was "
                             f"written (pid reused); not ours to resume")
                continue
            problems.append(f"FROZEN pid {pid} ({p.comm}) state {p.state}: listed in {frozen}, "
                            f"still alive; run yield-watch.sh --thaw")
    if watch is not None:
        now = time.time() if now is None else now
        newest = None
        if watch.is_dir():
            for root, _dirs, files in os.walk(watch):
                for name in files:
                    try:
                        m = os.stat(os.path.join(root, name)).st_mtime
                    except OSError:
                        continue
                    newest = m if newest is None or m > newest else newest
        if newest is None:
            problems.append(f"STALE {watch}: no file to read a heartbeat from")
        elif now - newest > stale_min * 60:
            problems.append(f"STALE {watch}: newest file is {(now - newest) / 60:.0f} min old, "
                            f"limit {stale_min:g}")
    return problems, notes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="report stopped, frozen and orphaned processes "
                                             "of this user, and a stale output directory")
    ap.add_argument("--watch", type=Path, help="directory whose newest file is the run's heartbeat")
    ap.add_argument("--stale", type=float, default=DEFAULT_STALE_MIN,
                    help=f"minutes without a new file under --watch that count as a stall "
                         f"(default {DEFAULT_STALE_MIN})")
    ap.add_argument("--frozen", type=Path, default=DEFAULT_FROZEN,
                    help="cpu-yield's frozen.pids (default ~/.local/share/cpu-yield/frozen.pids)")
    ap.add_argument("--proc", type=Path, default=Path("/proc"), help="proc root (tests)")
    ap.add_argument("--uid", type=int, default=None, help="the user whose processes count (default: mine)")
    a = ap.parse_args(argv)
    uid = os.getuid() if a.uid is None else a.uid
    try:
        procs = scan(a.proc, float(os.sysconf("SC_CLK_TCK")))
    except (OSError, ValueError) as e:
        print(f"stall_check: cannot read {a.proc}: {e}")
        return 2
    if not procs:
        print(f"stall_check: no process readable under {a.proc}")
        return 2
    problems, notes = check(procs, uid, frozen=a.frozen, watch=a.watch, stale_min=a.stale)
    for line in notes:
        print(line)
    for line in problems:
        print(line)
    mine = sum(1 for p in procs.values() if p.uid == uid)
    if problems:
        print(f"stall_check: {len(problems)} problem(s); {mine} process(es) of uid {uid} scanned")
        return 1
    print(f"stall_check: clean; {mine} process(es) of uid {uid} scanned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
