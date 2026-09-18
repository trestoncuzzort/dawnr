#!/usr/bin/env python3
"""t/restore_run.py -- put a committed run back where the tools expect it (2026-09-17).

    python3 t/restore_run.py [--run t/runs/2026-09-17/home-4080] [--force]

`t/out` is not in the repository, so a fresh clone starts with nothing on disk and every step of t lab's
Collect data tab reads as not done, however much work is recorded in `t/runs/`. This script rebuilds `t/out`
from a committed run: every answer set's replies (raw.tar.gz), extracted tasks, test results, graded table and
the tasks that were sent to the checkers, plus the run's pool, pairs and split, and the list of held-out ids.

After it, t lab opens where the run left off: the finished steps are done and hidden, and the ones that remain
are the ones that remain. Nothing is overwritten unless --force is given, so it is safe to run twice.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
FILES = ("kernels.md", "extract.json", "tests.json")


def restore_set(src: Path, force: bool) -> tuple[str, int]:
    dst = OUT / "spec-experiment" / src.name
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    raw = src / "raw.tar.gz"
    if raw.exists() and (force or not (dst / "raw").is_dir()):
        with tarfile.open(raw) as tf:
            tf.extractall(dst)                                  # noqa: S202  (our own archive, written beside it)
        n += sum(1 for _ in (dst / "raw").glob("*.json"))
    for name in FILES:
        if (src / name).exists() and (force or not (dst / name).exists()):
            shutil.copy2(src / name, dst / name)
    for folder in ("grade-in", "tasks"):
        if (src / folder).is_dir() and (force or not (dst / folder).is_dir()):
            shutil.copytree(src / folder, dst / folder, dirs_exist_ok=True)
    return src.name, n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", type=Path, default=HERE / "runs" / "2026-09-17" / "home-4080")
    ap.add_argument("--force", action="store_true", help="overwrite what is already on disk")
    a = ap.parse_args()
    run = a.run if a.run.is_absolute() else Path.cwd() / a.run
    if not run.is_dir():
        print(f"no such run: {run}")
        return 2

    (OUT / "loop").mkdir(parents=True, exist_ok=True)
    sets = sorted(p for p in (run / "answers").glob("*") if p.is_dir()) if (run / "answers").is_dir() else []
    total = 0
    for s in sets:
        name, n = restore_set(s, a.force)
        total += n
        print(f"  {name}: {n} replies" if n else f"  {name}: tables only")

    for src in sorted((run / "loop-data").glob("*")) if (run / "loop-data").is_dir() else []:
        dst = OUT / "loop" / src.name
        if a.force or not dst.exists():
            shutil.copy2(src, dst)

    # the older run this one builds on, when it is in the repository too
    for name, src in (("split-v3.json", HERE / "runs/2026-09-16/loop-data/split-v3.json"),
                      ("sft-r3-27b.jsonl", HERE / "runs/2026-09-16/loop-data/sft-r3-27b.jsonl"),
                      ("pairs-r3-27b.jsonl", HERE / "runs/2026-09-16/loop-data/pairs-r3-27b.jsonl")):
        if src.exists() and (a.force or not (OUT / "loop" / name).exists()):
            shutil.copy2(src, OUT / "loop" / name)

    # the run's own outputs that live directly in t/out: the copy-check keys and the checker table
    for name in ("pool-keys.txt", "AGREEMENT-lab.md"):
        if (run / name).exists() and (a.force or not (OUT / name).exists()):
            shutil.copy2(run / name, OUT / name)

    split = OUT / "loop" / "split-v3.json"
    if split.exists():
        ids = json.loads(split.read_text())["eval_ids"]
        (OUT / "loop" / "eval-ids.txt").write_text("\n".join(str(i) for i in ids) + "\n")

    print(f"\n{len(sets)} answer sets restored, {total} replies, into {OUT.relative_to(HERE.parent)}.")
    print("Open t lab: the steps this run finished read done, and the rest are what is left.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
