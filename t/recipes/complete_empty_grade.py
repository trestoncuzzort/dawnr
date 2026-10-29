"""Record a complete zero-task grade without inventing proof or reference results.

Nonempty task sets continue through v6-grade.sh unchanged. Only a complete,
consistent generation/extraction record with no task can take this branch.
Sources: grade_spec33.grade's empty-answer path; score_levels.table;
https://github.com/trestoncuzzort/dawnr/blob/main/t/recipes/v6-grade.sh
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import score_levels
import spec_check
import spec_experiment as se


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def complete(tag, panel, output):
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", tag), "invalid generation tag")
    directory = se.OUT_ROOT / tag
    tasks = directory / "tasks"
    require(tasks.is_dir() and not tasks.is_symlink(), "extraction did not produce a task directory")
    if any(tasks.glob("*.json")):
        return False
    panel, output = Path(panel), Path(output)
    ids = panel.read_text().split()
    require(ids and len(ids) == len(set(ids)) and all(str(int(i)) == i and int(i) >= 0 for i in ids), "invalid problem panel")
    summary = read(directory / "spec_first.json")
    require(summary["problems"] == len(ids) and set(summary["per_problem"]) == set(ids), "generation does not account for the exact panel")
    raw = directory / "raw"
    require(raw.is_dir() and not raw.is_symlink(), "generation evidence is missing")
    paths = list(raw.iterdir())
    require(all(p.is_file() and not p.is_symlink() and p.suffix == ".json" and p.stem in ids for p in paths), "foreign or invalid raw answer")
    raw_ids = {p.stem for p in paths}
    taken = {tid for tid, value in summary["per_problem"].items() if value.get("taken") is not None}
    require(type(summary["answered"]) is int and summary["answered"] == len(taken) and raw_ids == taken, "generation answer accounting differs")
    extracted, tests = read(directory / "extract.json"), read(directory / "tests.json")
    require(set(extracted) == raw_ids, "extraction does not cover every saved answer")
    require(all(value.get("stage") and value["stage"] != "task" for value in extracted.values()), "a claimed task is missing its file")
    require(tests == {}, "a zero-task run has unexpected test results")
    require((output / "evaluator.json").is_file(), "missing evaluator identity")
    require(not (output / "GRADED").exists() and not (directory / "kernels.md").exists()
            and not (output / "levels.json").exists() and not (output / "verdicts.json").exists(), "refusing to replace grading results")
    table = "| task | " + " | ".join(spec_check.KERNELS) + " |\n|---|" + "---|" * len(spec_check.KERNELS) + "\n"
    (directory / "kernels.md").write_text(table)
    rows, pooled = score_levels.table([tag], set(map(int, ids)), {}, .6, True)
    require(all(row["task"] == row["tests pass"] == 0 and all(row[">=" + str(k)] == 0 for k in score_levels.LEVELS)
                for row in rows), "empty grading unexpectedly admitted an answer")
    write(output / "verdicts.json", {"tags": [tag], "results": {}})
    write(output / "levels.json", {"rows": rows, "pooled": pooled, "ids": len(ids)})
    write(output / "empty-grade.json", {"kind": "complete-zero-task-grade", "tag": tag,
          "panel_problems": len(ids), "panel_sha256": digest(panel), "saved_raw_answers": len(paths),
          "procedure_sha256": digest(Path(__file__)), "kernel_or_reference_calls": 0,
          "input_sha256": {name: digest(directory / name) for name in ("spec_first.json", "extract.json", "tests.json")},
          "raw_sha256": {p.name: digest(p) for p in sorted(paths)}, "evaluator_sha256": digest(output / "evaluator.json")})
    (output / "GRADED").touch()
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag"); parser.add_argument("panel", type=Path); parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if complete(args.tag, args.panel, args.output):
        print("Complete panel recorded with zero tasks and zero admitted answers.")
        return 0
    return 3  # A nonempty set continues through the existing proof/reference grader.


if __name__ == "__main__":
    raise SystemExit(main())
