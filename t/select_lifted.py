#!/usr/bin/env python3
"""select_lifted.py -- the run-ready subset of a lifter run, for the sweep.

ROADMAP 12.5 runs the lifted corpus through seven kernels. `run_par.py
--tasks DIR` globs `DIR/*.json` and hands every match to `harness.load`,
which asserts on the `t` key. `t/out/lift` cannot be that directory: beside
each `<stem>.<method>.json` task it holds a `<stem>.<method>.lift.json`
sidecar, a `<stem>.outcome.json` marker and one `run_summary.json`, none of
which is a task. Pointing the driver at it does not skip them, it dies on
the first one.

So this picks the tasks out. A method is taken when its outcome entry says
`"checked": true`, which means `lift_check.check` ran and returned no
refusal. `refusal is None` is NOT the same test and would be wrong here:
`--skip-check` also leaves the refusal None, on a task nothing verified.

    python3 select_lifted.py                       # report only
    python3 select_lifted.py --out out/lift-checked
    python3 select_lifted.py --only dafny-synthesis  # a named subset

Two things it refuses rather than papers over:

  - a duplicate task `name`. `run_par` keys its rows by `task["name"]` and
    does not check, so two lifted methods sharing a name would silently
    become one row and the table would quietly be short.
  - a `task_file` an outcome entry names but that is not on disk.

Standard library only, no dafny.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_LIFT = HERE / "out" / "lift"


def scan(lift_dir: Path, only: str = ""):
    """Walk the outcome markers; return (taken, refused_counter, problems)."""
    taken, problems = [], []
    refused = Counter()
    markers = sorted(lift_dir.glob("*.outcome.json"))
    for m in markers:
        if only and only not in m.name:
            continue
        try:
            rec = json.loads(m.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            problems.append((m.name, "unreadable outcome: %s" % e))
            continue
        # A file-level refusal carries its OWN named reason. Counting these
        # as "parse-failure" would be wrong and was, on the first run here:
        # design 18.2 made the front end name the construct, so a parse-stage
        # refusal usually reads `let-expression` or `heap`, and only a genuinely
        # unnamed one reads `parse-failure`.
        for key in ("parse_refusal", "resolve_refusal"):
            r = rec.get(key)
            if r:
                refused[r.get("reason") or key.replace("_", "-")] += 1
        for entry in rec.get("methods", []):
            if not entry.get("checked"):
                r = entry.get("refusal") or {}
                refused[r.get("reason") or "unchecked"] += 1
                continue
            tf = entry.get("task_file")
            if not tf:
                problems.append((m.name, "checked method with no task_file: %s"
                                 % entry.get("method")))
                continue
            path = Path(tf)
            if not path.is_absolute():
                path = lift_dir / path
            if not path.exists():
                problems.append((m.name, "task_file missing: %s" % tf))
                continue
            taken.append((path, entry.get("method")))
    return taken, refused, problems, len(markers)


def names_of(taken):
    """{task name: [paths]} so a collision is visible before it matters."""
    by_name = defaultdict(list)
    for path, _method in taken:
        try:
            name = json.loads(path.read_text(encoding="utf-8"))["name"]
        except (OSError, json.JSONDecodeError, KeyError) as e:
            by_name["<unreadable:%s>" % path.name].append(path)
            continue
        by_name[name].append(path)
    return by_name


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lift", type=Path, default=DEFAULT_LIFT,
                    help="the lifter's output directory (default out/lift)")
    ap.add_argument("--out", type=Path, default=None,
                    help="copy the selected tasks here, one clean directory")
    ap.add_argument("--only", default="",
                    help="substring a source file name must contain")
    args = ap.parse_args(argv)

    if not args.lift.exists():
        print("no lifter output at %s. Run lifter.py --dir <corpus> first."
              % args.lift)
        return 1

    taken, refused, problems, n_markers = scan(args.lift, args.only)
    by_name = names_of(taken)
    dupes = {n: ps for n, ps in by_name.items() if len(ps) > 1}

    print("source files scanned:      %d" % n_markers)
    print("methods checked and taken: %d" % len(taken))
    print("distinct task names:       %d" % len(by_name))
    print("methods not taken:         %d" % sum(refused.values()))
    if refused:
        print()
        print("why not, by reason:")
        for reason, n in refused.most_common(12):
            print("  %-28s %4d" % (reason, n))
        if len(refused) > 12:
            print("  (%d more reasons)" % (len(refused) - 12))

    if problems:
        print()
        print("PROBLEMS (%d):" % len(problems))
        for where, what in problems[:10]:
            print("  %-44s %s" % (where, what))

    if dupes:
        print()
        print("REFUSED: %d task name(s) are claimed by more than one method."
              % len(dupes))
        print("run_par keys its rows by task name and does not check, so the")
        print("second would overwrite the first and the table would be short.")
        for n, ps in list(dupes.items())[:8]:
            print("  %-30s %s" % (n, ", ".join(p.name for p in ps)))
        return 2

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        existing = list(args.out.glob("*.json"))
        for p in existing:
            p.unlink()
        for path, _method in taken:
            shutil.copy2(path, args.out / path.name)
        n = len(list(args.out.glob("*.json")))
        print()
        print("wrote %d task files to %s (cleared %d stale)"
              % (n, args.out, len(existing)))
        if n != len(taken):
            print("REFUSED: wrote %d but selected %d" % (n, len(taken)))
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
