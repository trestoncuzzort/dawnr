#!/usr/bin/env python3
"""Observe aggregate build-resource counters without changing the cgroup.

Kernel ABI: https://docs.kernel.org/admin-guide/cgroup-v2.html
Memory peak includes charged cache/kernel memory as well as process memory.
This is not the maximum RSS of one compiler process, nor total host memory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def keyed(raw: str) -> dict[str, int]:
    result = {}
    for line in raw.splitlines():
        key, number = line.split()
        if key in result or not number.isdigit():
            raise ValueError("invalid cgroup counter")
        result[key] = int(number)
    return result


def capture(group: Path) -> dict:
    result = {"utc": datetime.now(timezone.utc).isoformat(),
              "monotonic_seconds": time.monotonic()}
    for name in ("memory.current", "memory.peak", "memory.swap.current", "pids.current"):
        raw = (group / name).read_text().strip()
        if not raw.isdigit():
            raise ValueError("invalid integer counter: " + name)
        result[name] = int(raw)
    for name in ("memory.events", "cpu.stat", "cgroup.events"):
        result[name] = keyed((group / name).read_text())
    if (group / "memory.swap.peak").exists():
        result["memory.swap.peak"] = int((group / "memory.swap.peak").read_text())
    result["limits"] = {name: (group / name).read_text().strip()
                        for name in ("memory.max", "memory.swap.max", "cpu.max", "pids.max")}
    result["host_mem_available_kib"] = next(int(line.split()[1]) for line in
        Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemAvailable:"))
    return result


def observe(group: Path, output: Path, interval: float, max_seconds: float, command=None) -> int:
    group = group.absolute()
    parent = Path("/sys/fs/cgroup")
    if group.resolve() != group or not group.is_dir() or parent not in group.parents:
        raise ValueError("select an existing cgroup below /sys/fs/cgroup without symlinks")
    if not 0.1 <= interval <= 60 or not 1 <= max_seconds <= 172800:
        raise ValueError("invalid observation interval or duration")
    start = time.monotonic()
    summary = {"type": "summary", "status": "observing", "samples": 0,
               "max_memory_peak_bytes": 0, "max_observed_swap_bytes": 0,
               "max_processes": 0, "minimum_host_available_kib": None}
    with output.open("xb") as stream:
        os.chmod(output, 0o600)

        def emit(item):
            stream.write((json.dumps(item, sort_keys=True) + "\n").encode())
            stream.flush()

        emit({"type": "header", "schema": "tup-cgroup-observation-v1",
              "observer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "interval_seconds": interval, "max_seconds": max_seconds,
              "cgroup": group.relative_to(parent).as_posix(),
              "scope": "selected cgroup and descendants, including this collector; no build-correctness verdict",
              "command_supervised": bool(command)})
        child = subprocess.Popen(command) if command else None
        try:
            while True:
                sample = capture(group)
                sample["type"] = "sample"
                emit(sample)
                summary["samples"] += 1
                summary["max_memory_peak_bytes"] = max(summary["max_memory_peak_bytes"], sample["memory.peak"])
                summary["max_observed_swap_bytes"] = max(summary["max_observed_swap_bytes"], sample.get("memory.swap.peak", sample["memory.swap.current"]))
                summary["max_processes"] = max(summary["max_processes"], sample["pids.current"])
                available = sample["host_mem_available_kib"]
                previous = summary["minimum_host_available_kib"]
                summary["minimum_host_available_kib"] = available if previous is None else min(previous, available)
                if child is not None and child.poll() is not None:
                    # This collector stays in the same cgroup until counters
                    # have been persisted. systemd may otherwise remove an
                    # exited service's counters before an external last sample.
                    final = capture(group)
                    final["type"] = "final-sample"
                    emit(final)
                    summary["max_memory_peak_bytes"] = max(summary["max_memory_peak_bytes"], final["memory.peak"])
                    summary["max_observed_swap_bytes"] = max(summary["max_observed_swap_bytes"], final.get("memory.swap.peak", final["memory.swap.current"]))
                    summary["status"] = "command-exited"
                    summary["command_exit_code"] = child.returncode
                    summary["final_memory_events"] = final["memory.events"]
                    summary["final_cpu_stat"] = final["cpu.stat"]
                    own_threads = next(int(line.split()[1]) for line in
                        Path("/proc/self/status").read_text().splitlines() if line.startswith("Threads:"))
                    # pids.current is hierarchical and counts threads, unlike
                    # cgroup.procs which omits descendant groups entirely.
                    remaining = max(0, final["pids.current"] - own_threads)
                    summary["remaining_tasks"] = remaining
                    summary["complete_resource_lifetime"] = remaining == 0
                    if remaining:
                        summary["status"] = "command-left-processes"
                    break
                if child is None and sample["cgroup.events"].get("populated") == 0:
                    summary["status"] = "cgroup-empty"
                    summary["final_memory_events"] = sample["memory.events"]
                    summary["final_cpu_stat"] = sample["cpu.stat"]
                    break
                if time.monotonic() - start >= max_seconds:
                    summary["status"] = "observation-timeout"
                    break
                time.sleep(interval)
        except (OSError, ValueError) as exc:
            summary["status"] = "observation-incomplete"
            summary["error"] = type(exc).__name__ + ": " + str(exc)
        summary["wall_seconds"] = round(time.monotonic() - start, 3)
        if child is not None and child.poll() is None:
            # The service manager must stop the whole cgroup on observer
            # failure/timeout. Never report a still-running command as success.
            summary["command_still_running"] = True
        emit(summary)
        os.fsync(stream.fileno())
    print(json.dumps(summary, sort_keys=True))
    if summary["status"] == "command-exited":
        return summary["command_exit_code"] if 0 <= summary["command_exit_code"] <= 255 else 2
    return 0 if summary["status"] == "cgroup-empty" else 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cgroup", required=True, help="absolute cgroup path, or self for supervised command")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=2)
    parser.add_argument("--max-seconds", type=float, default=86400)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if command and args.cgroup != "self":
            raise ValueError("supervised command requires --cgroup self")
        if args.cgroup == "self":
            if not command:
                raise ValueError("--cgroup self requires an explicit command")
            memberships = Path("/proc/self/cgroup").read_text().splitlines()
            unified = [line[3:] for line in memberships if line.startswith("0::/")]
            if len(unified) != 1:
                raise ValueError("expected one unified cgroup membership")
            group = Path("/sys/fs/cgroup") / unified[0].lstrip("/")
        else:
            group = Path(args.cgroup)
        return observe(group, args.output, args.interval, args.max_seconds, command)
    except (OSError, ValueError) as exc:
        print("OBSERVATION FAILED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
