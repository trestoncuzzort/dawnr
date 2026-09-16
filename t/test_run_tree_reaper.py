#!/usr/bin/env python3
"""t/test_run_tree_reaper.py -- verifiers.run_tree must not leave a prover
running when its driver is killed (2026-09-16).

run_tree starts every prover in its own session so a timeout can kill the
whole tree, which also detaches the prover from its driver: a driver killed
from outside left six rocqworker processes running for 24 to 44 hours,
holding about 290 GB. This test starts a driver that runs two process
trees through run_tree from worker threads, kills the driver with SIGTERM
and then SIGHUP, and checks that no process of either group survives. It
also checks the ordinary paths: a return code and output come back
unchanged, a timeout still raises TimeoutExpired, and no group is left
registered after either.

Standard library only, Linux (reads process groups with ps). Exit code 0
on success, 1 on any failure; prints one PASS/FAIL line per check.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import verifiers                                              # noqa: E402

DRIVER = f"""
import sys, threading, time
sys.path.insert(0, {HERE!r})
import verifiers
def go():
    verifiers.run_tree(["sh", "-c", "sleep 300 & sleep 300"], timeout=600)
for _ in range(2):
    threading.Thread(target=go, daemon=True).start()
while len(verifiers._LIVE_GROUPS) < 2:
    time.sleep(0.05)
print(" ".join(map(str, sorted(verifiers._LIVE_GROUPS))), flush=True)
time.sleep(600)
"""


def members(groups: list[int]) -> int:
    n = 0
    for g in groups:
        p = subprocess.run(["ps", "-o", "pid=", "-g", str(g)],
                           capture_output=True, text=True)
        n += len(p.stdout.split())
    return n


def killed_driver(sig: int) -> tuple[bool, str]:
    d = subprocess.Popen([sys.executable, "-c", DRIVER],
                         stdout=subprocess.PIPE, text=True)
    groups = [int(g) for g in d.stdout.readline().split()]
    time.sleep(0.5)
    before = members(groups)
    d.send_signal(sig)
    d.wait(timeout=30)
    for _ in range(50):
        if members(groups) == 0:
            break
        time.sleep(0.1)
    after = members(groups)
    return (len(groups) == 2 and before > 0 and after == 0,
            f"groups {groups}, processes before {before}, after {after}, "
            f"driver rc {d.returncode}")


def main() -> int:
    fails = 0

    def report(name: str, ok: bool, detail: str) -> None:
        nonlocal fails
        print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")
        fails += not ok

    r = verifiers.run_tree(["sh", "-c", "echo hi; exit 3"], timeout=10,
                           text=True)
    report("return", r.returncode == 3 and r.stdout.strip() == "hi"
           and not verifiers._LIVE_GROUPS,
           f"rc {r.returncode}, stdout {r.stdout.strip()!r}, "
           f"live {sorted(verifiers._LIVE_GROUPS)}")
    try:
        verifiers.run_tree(["sleep", "5"], timeout=0.5)
        report("timeout", False, "no TimeoutExpired")
    except subprocess.TimeoutExpired:
        report("timeout", not verifiers._LIVE_GROUPS,
               f"TimeoutExpired, live {sorted(verifiers._LIVE_GROUPS)}")
    for sig in (signal.SIGTERM, signal.SIGHUP):
        ok, detail = killed_driver(sig)
        report(f"driver {sig.name}", ok, detail)
    print(f"{4 - fails} of 4 checks pass")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
