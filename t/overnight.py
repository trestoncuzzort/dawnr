#!/usr/bin/env python3
"""t/overnight.py -- carry the run on while nobody is awake (2026-09-18).

    python3 t/overnight.py [--dry-run] [--skip key,key] [--poll 60]

t lab's Collect data tab knows every step, what it needs, what it runs and how to tell it is done. This walks
that same list without a person: it starts any step whose prerequisites are done and whose machine is free,
waits, and starts the next one. Same commands, same logs, same pid files, so t lab shows every step running as
if it had been pressed.

The rules it will not break:

  * One step per machine. A step's `uses` says which -- `gpu` is this desktop's card, `lab` the workstation,
    `gen` a generator either side, `cpu` this desktop's cores -- and two steps never share one.
  * The lab workstation's GPUs are the operator's to lend, not ours to take. Any step whose command starts
    vLLM there is skipped by name, and so is anything wanting `sudo`, because nobody is awake to type it.
  * A step that fails is retried once. If it fails again it is recorded and the run carries on with whatever
    does not depend on it, rather than stopping the night on one failure.
  * `t/out/OVERNIGHT-STOP` ends it after the running steps finish, for a person who wants it to stop without
    hunting for a pid.

It writes `t/runs/<today>/OVERNIGHT.md` as it goes: what ran, what it cost, what failed and what is left, so
the morning starts with a page rather than a log directory.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TUP = HERE.parent
sys.path.insert(0, str(HERE))

from lab import EVENTS, KERNEL_PATH, NEEDS, RUNS, STEPS      # noqa: E402

STEP = {s[0]: s for s in STEPS}
LOGS = RUNS / "logs"
REPORT = RUNS / "OVERNIGHT.md"
STOP = HERE / "out" / "OVERNIGHT-STOP"
ENV = dict(os.environ, PATH=KERNEL_PATH + os.pathsep + os.environ.get("PATH", ""), T_WATCH=str(EVENTS))
# the lab workstation's cards are lent to us and were handed back on 2026-09-18; nothing here takes them again
LAB_GPU = ("lab_gpu.sh start", "lab_gpu.sh constrained", "lab_gpu.sh takeover")


def resource(key: str) -> str:
    """Which machine a step occupies. `gen` means a generator either side, but the lab workstation's cards were
    handed back on 2026-09-18, so tonight a generator is this desktop's card and must not run beside a training
    step that wants the same 16 GB."""
    uses = STEP[key][5]
    return "gpu" if uses in ("gpu", "gen") else uses


def already_running(key: str) -> bool:
    """A step someone started by hand before this runner did. The pid file alone lies -- a dead step's number
    may belong to something else by now -- so the process's own command line has to hold the step's script,
    which is the check t lab makes (lab.Lab.running_steps)."""
    want = STEP[key][3]
    first = next((w for w in want.split() if w.endswith((".py", ".sh"))), "")
    if not first:
        return False
    return subprocess.run(["pgrep", "-f", first], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def done(key: str) -> bool:
    test = STEP[key][4]
    if not test:
        return False
    return subprocess.run(["bash", "-lc", test], cwd=TUP, env=ENV,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def blocked(key: str) -> str:
    """Why this step cannot be started by a machine, in words, or "" if it can."""
    cmd, uses = STEP[key][3], STEP[key][5]
    if uses == "sudo" or "sudo " in cmd:
        return "needs a password nobody is awake to type"
    if any(x in cmd for x in LAB_GPU):
        return "would take the lab workstation's GPUs, which are not ours tonight"
    return ""


class Runner:
    def __init__(self, poll: int, skip: set[str]):
        self.poll, self.skip = poll, skip
        self.running: dict[str, tuple] = {}                  # key -> (Popen, started, log, attempt)
        self.results: list[tuple] = []                       # (key, outcome, seconds)
        self.attempts: dict[str, int] = {}
        LOGS.mkdir(parents=True, exist_ok=True)

    def busy(self) -> set[str]:
        # a step someone started by hand holds its machine just as firmly as one this runner started
        return ({resource(k) for k in self.running}
                | {resource(k) for k, *_ in STEPS if k not in self.running and already_running(k)})

    def start(self, key: str) -> None:
        log = LOGS / f"{key}.log"
        attempt = self.attempts.get(key, 0) + 1
        self.attempts[key] = attempt
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"\n### {time.strftime('%F %T')} overnight, attempt {attempt}: {STEP[key][3]}\n")
            fh.flush()
            p = subprocess.Popen(["bash", "-lc", STEP[key][3]], cwd=TUP, env=ENV,
                                 stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                 start_new_session=True)
        # where t lab looks, and in its two-field form, so the window shows this step as running
        (LOGS / f"{key}.pid").write_text(f"{p.pid} {time.time()}")
        self.running[key] = (p, time.time(), log, attempt)
        print(f"{time.strftime('%T')} started {key} (pid {p.pid}, {resource(key) or 'no machine'})", flush=True)

    def reap(self) -> None:
        for key in list(self.running):
            p, t0, log, attempt = self.running[key]
            if p.poll() is None:
                continue
            del self.running[key]
            secs = time.time() - t0
            ok = done(key)
            if ok:
                self.results.append((key, "done", secs))
                print(f"{time.strftime('%T')} {key} finished in {secs/60:.0f} min", flush=True)
            elif attempt == 1:
                print(f"{time.strftime('%T')} {key} failed (exit {p.returncode}); one retry", flush=True)
                self.start(key)
            else:
                self.results.append((key, f"failed twice (exit {p.returncode}), see {log.name}", secs))
                print(f"{time.strftime('%T')} {key} failed again; carrying on without it", flush=True)

    def ready(self) -> list[str]:
        out = []
        for key, *_ in STEPS:
            if key in self.running or key in self.skip or self.attempts.get(key, 0) >= 2:
                continue
            if done(key) or blocked(key) or already_running(key):
                continue
            if any(not done(n) for n in NEEDS.get(key, [])):
                continue
            uses = resource(key)
            if uses and uses in self.busy() | {u for k in out for u in [resource(k)] if u}:
                continue
            out.append(key)
        return out

    def write_report(self) -> None:
        lines = [f"# Overnight, {time.strftime('%F')}", "",
                 f"Written by `t/overnight.py`, last at {time.strftime('%T')}.", "", "## Finished", ""]
        lines += [f"- `{k}`: {why} ({s/60:.0f} min)" for k, why, s in self.results] or ["- nothing yet"]
        lines += ["", "## Running", ""]
        mine = [f"- `{k}`, started {time.strftime('%T', time.localtime(t0))}"
                for k, (_p, t0, _l, _a) in self.running.items()]
        mine += [f"- `{k}`, started before this runner" for k, *_ in STEPS
                 if k not in self.running and not done(k) and already_running(k)]
        lines += mine or ["- nothing"]
        left, why_not = [], []
        for key, *_ in STEPS:
            if key in self.running or done(key) or already_running(key):
                continue
            b = blocked(key)
            if b:
                why_not.append(f"- `{key}`: {b}")
            elif key in self.skip:
                why_not.append(f"- `{key}`: skipped by hand")
            else:
                waiting = [n for n in NEEDS.get(key, []) if not done(n)]
                left.append(f"- `{key}`" + (f", waiting on {', '.join('`' + w + '`' for w in waiting)}"
                                            if waiting else ", ready"))
        lines += ["", "## Left to do", ""] + (left or ["- nothing"])
        lines += ["", "## Not for a machine to start", ""] + (why_not or ["- nothing"])
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def loop(self, dry: bool) -> int:
        if dry:
            print("would run, in this order, as machines free up:")
            for key in self.ready():
                print(f"  {key:22s} {resource(key) or 'no machine':10s} {STEP[key][3][:80]}")
            for key, *_ in STEPS:
                b = blocked(key)
                if b and not done(key):
                    print(f"  SKIP {key:17s} {b}")
            self.write_report()
            return 0
        while True:
            self.reap()
            if STOP.exists():
                if not self.running:
                    print("OVERNIGHT-STOP is there and nothing is running; stopping", flush=True)
                    break
            else:
                for key in self.ready():
                    self.start(key)
            self.write_report()
            if not self.running and not self.ready():
                print("nothing runnable left", flush=True)
                break
            time.sleep(self.poll)
        self.write_report()
        print(f"\n{len(self.results)} steps ran; the page is {REPORT}")
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--poll", type=int, default=60)
    ap.add_argument("--skip", default="", help="comma-separated step keys to leave alone")
    a = ap.parse_args()
    return Runner(a.poll, {k for k in a.skip.split(",") if k}).loop(a.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
