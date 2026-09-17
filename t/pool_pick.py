#!/usr/bin/env python3
"""t/pool_pick.py -- pick which answers are worth the kernels' time (2026-09-17).

    python3 t/pool_pick.py t/out/spec-experiment/<tag> [--keys FILE]

Copies into <tag>/grade-in/ only the extracted tasks that pass every one of
their problem's tests (tests.json) and are not an exact copy of a task picked
from an earlier answer set. "Exact copy" uses t/loop_filter.py's key: the
canonical program with its name, format version and gate erased, none of which
changes what the kernels check. The keys of every picked task are appended to
FILE (default t/out/pool-keys.txt), so a later answer set skips what an earlier
one already sent to grading.

Grading then runs only on grade-in/:

    python3 t/run_par.py --jobs N --tasks <tag>/grade-in --out <tag>/kernels --table <tag>/kernels.md

A task that fails its tests can never enter the clean pool, so grading it only
spends CPU. This replaces t/runs/2026-09-16/scripts/pick.py, which kept the
format version in its key (the hole t/runs/2026-09-17/README.md describes).
Standard library only.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402


def key(task: dict) -> str:
    t = se.rename_task(copy.deepcopy(task), "x_task")
    t.pop("gate", None)
    t["t"] = 1
    return surface.canon(t)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("tag_dir", type=Path)
    ap.add_argument("--keys", type=Path, default=HERE / "out" / "pool-keys.txt")
    a = ap.parse_args()
    d = a.tag_dir
    tests = json.loads((d / "tests.json").read_text(encoding="utf-8"))
    seen = set(a.keys.read_text(encoding="utf-8").splitlines()) if a.keys.exists() else set()
    out = d / "grade-in"
    out.mkdir(exist_ok=True)
    passing = picked = 0
    new_keys = []
    for v in tests.values():
        if v.get("overall") != "pass":
            continue
        passing += 1
        src = d / "tasks" / f"{v['name']}.json"
        if not src.exists():
            continue
        k = key(json.loads(src.read_text(encoding="utf-8")))
        if k in seen:
            continue
        seen.add(k)
        new_keys.append(k)
        shutil.copy(src, out / src.name)
        picked += 1
    a.keys.parent.mkdir(parents=True, exist_ok=True)
    with open(a.keys, "a", encoding="utf-8") as f:
        for k in new_keys:
            f.write(k + "\n")
    print(f"{d.name}: {len(tests)} tasks, {passing} pass their tests, {picked} new -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
