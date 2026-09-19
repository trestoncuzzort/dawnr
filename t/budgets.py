#!/usr/bin/env python3
"""t/budgets.py -- what each proof system costs, so an editor knows which of them it can afford (2026-09-19).

    python3 t/budgets.py [--tasks t/tasks] [--kernels a,b,c] [--limit N] [--out t/BUDGETS-2026-09-19.md]

ROADMAP 15.1 shipped the harness as a library with a verdict cache and left one thing unmeasured, by name:
"interactive budgets per kernel are still unmeasured; `budget` is passed through, not characterised".
AGREEMENT.md records what each kernel decided and never how long it took, so nothing in this repository could
answer the question an editor has to answer first -- which of the seven can run while someone is typing, and
which belong on a keystroke they choose.

This times one verification of the real program per task per kernel, with the cache bypassed so every call
launches its kernel, and reports what an editor can plan against: the median, the slowest, and how many tasks
finish inside a second, three seconds and ten. The twin is not timed: an editor checks the program in front of
the person, not its deliberate near-miss.

It runs no training and needs no GPU. On the lab workstation, keep --jobs low elsewhere while it runs: a
timing measured against a loaded box measures the box.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import tlib                                                     # noqa: E402

INTERACTIVE = (1.0, 3.0, 10.0)                                  # a keystroke, a pause, a deliberate wait


SUFFIX = {b: ext for b, _lmod, ext in tlib.BACKENDS}


def time_one(task: dict, kernel: str, budget) -> tuple[str, float]:
    """One kernel launch on one task's real program, cache bypassed. (outcome, seconds).

    The file keeps the task's own name: SPARK derives its unit name from the filename and Lean and Rocq read
    better in a log that names the task, so a temporary file called x.ads would measure a different thing.
    """
    import importlib
    if kernel not in SUFFIX:
        return "no such kernel", 0.0
    try:
        backend = importlib.import_module(f"verifiers.{kernel}")
    except Exception:                                           # noqa: BLE001
        return "absent", 0.0
    try:
        source = tlib.lower(task, kernel)
    except NotImplementedError:
        return "abstain", 0.0
    except Exception:                                           # noqa: BLE001
        return "lower-error", 0.0
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / f"{task.get('name', 'task')}.{SUFFIX[kernel]}"
        p.write_text(source, encoding="utf-8")
        t0 = time.monotonic()
        try:
            # the backends take a Path, not a string: verifiers/dafny.py reads it with read_bytes
            outcome = backend.verify(p, budget) if budget is not None else backend.verify(p)
        except Exception as e:                                  # noqa: BLE001
            return f"error: {type(e).__name__}: {e}"[:60], time.monotonic() - t0
        secs = time.monotonic() - t0
    word = getattr(outcome, "outcome", outcome)
    word = word[0] if isinstance(word, (tuple, list)) else word
    return str(word), secs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tasks", type=Path, default=HERE / "tasks")
    ap.add_argument("--kernels", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--budget", default=None)
    ap.add_argument("--out", type=Path, default=HERE / "BUDGETS-2026-09-19.md")
    a = ap.parse_args()

    import tasks_io
    paths = sorted(a.tasks.glob("*.t"))
    if a.limit:
        paths = paths[:a.limit]
    kernels = [k for k in (a.kernels.split(",") if a.kernels else [b for b, _m, _e in tlib.BACKENDS]) if k]
    print(f"{len(paths)} tasks x {len(kernels)} kernels, cache bypassed", flush=True)

    per: dict[str, list[tuple[str, str, float]]] = {k: [] for k in kernels}
    for path in paths:
        task = tasks_io.load_task(str(path))
        for k in kernels:
            word, secs = time_one(task, k, a.budget)
            per[k].append((path.stem, word, secs))
            print(f"  {path.stem:26s} {k:7s} {word:12s} {secs:7.2f} s", flush=True)

    lines = [f"# What each proof system costs on one task, {time.strftime('%Y-%m-%d %H:%MZ', time.gmtime())}", "",
             "Measured by `t/budgets.py`: one verification of the real program per task per kernel, the verdict",
             "cache bypassed so every call launches its kernel. The twin is not timed -- an editor checks the",
             "program in front of the person, not its near-miss. ROADMAP 15.1 left this unmeasured by name.", "",
             f"{len(paths)} committed tasks. Times are wall clock on the machine that ran it, which is the only",
             "thing an editor can plan against.", "",
             "| kernel | timed | median | slowest | under 1 s | under 3 s | under 10 s |",
             "|---|---|---|---|---|---|---|"]
    verdict_lines = []
    for k in kernels:
        secs = [s for _n, w, s in per[k] if w not in ("abstain", "lower-error", "no such kernel") and s > 0]
        if not secs:
            lines.append(f"| `{k}` | 0 | - | - | - | - | - |")
            continue
        ok = [sum(1 for s in secs if s <= t) for t in INTERACTIVE]
        lines.append(f"| `{k}` | {len(secs)} | {statistics.median(secs):.2f} s | {max(secs):.1f} s | "
                     + " | ".join(f"{n} of {len(secs)}" for n in ok) + " |")
        verdict_lines.append((k, statistics.median(secs), ok[0] / len(secs)))
    lines += ["", "## What an editor can afford", ""]
    fast = [k for k, med, share in verdict_lines if med <= INTERACTIVE[0]]
    mid = [k for k, med, share in verdict_lines if INTERACTIVE[0] < med <= INTERACTIVE[2]]
    slow = [k for k, med, share in verdict_lines if med > INTERACTIVE[2]]
    lines += [f"- **While someone types** (median at or under a second): {', '.join(fast) or 'none'}.",
              f"- **On a pause, or a save** (a second to ten): {', '.join(mid) or 'none'}.",
              f"- **Only when asked for** (over ten seconds): {', '.join(slow) or 'none'}.", "",
              "An editor that wants a verdict per keystroke can have one from the first group and must show the",
              "rest as pending. The flake rule is unchanged and costs three runs, not one, so a verdict an",
              "editor is willing to write anywhere a table reads from costs three times the numbers above.", ""]
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines[8:]))
    print(f"written to {a.out.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
