#!/usr/bin/env python3
"""Grade a complete, private answer set for the registered 33 given specifications.

Use the existing strict specification-preservation gate and seven-kernel scorer. Inputs are pinned
by digest; duplicate, missing, foreign or mixed-prompt answers are refused before grading. This is
one release condition, never a model promotion decision.

Sources: v5-matched-2026-10-11-grade.sh; t/score_spec_given.py;
https://github.com/trestoncuzzort/dawnr/blob/main/t/recipes/v6-grade.sh
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "t"))
import score_spec_given as scorer
import spec_check
import spec_experiment

QUESTIONS_SHA = "effc2f4e586e0c4f7638a5a9a2b75515aaf7019de03ca819d46e5aa3d593ab24"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def checked_file(root: Path, entry: dict) -> Path:
    relative = Path(entry["path"])
    path = (root / relative).resolve()
    if relative.is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("input paths must stay inside the private input directory")
    if digest(path) != entry["sha256"]:
        raise ValueError("input digest differs from the manifest")
    return path


def validate_inputs(path: Path) -> tuple[dict, list[dict], dict[str, str]]:
    manifest = json.loads(path.read_text())
    questions_path = checked_file(path.parent, manifest["questions"])
    answers_path = checked_file(path.parent, manifest["answers"])
    if digest(questions_path) != QUESTIONS_SHA:
        raise ValueError("the specification panel differs from the registered 33 questions")
    questions, answers = read_rows(questions_path), read_rows(answers_path)
    question_names = [row["name"] for row in questions]
    answer_names = [row["name"] for row in answers]
    if len(questions) != 33 or len(set(question_names)) != 33:
        raise ValueError("the question panel must contain 33 distinct questions")
    if len(answers) != 33 or len(set(answer_names)) != 33 or set(answer_names) != set(question_names):
        raise ValueError("answers must cover every question exactly once")
    if not all(row.get("model") == manifest["answer_model"] and row.get("system") == "s1"
               and isinstance(row.get("reply"), str) for row in answers):
        raise ValueError("answer model or prompt metadata differs from the registered procedure")
    return manifest, questions, {row["name"]: row["reply"] for row in answers}


def checked_levels(report: dict, table: Path) -> dict:
    expected = {name for name, row in report["entries"].items() if row["stage"] == "ready"}
    if expected:
        columns, rows = spec_experiment.parse_kernel_table(table)
        if set(columns) != set(spec_check.KERNELS) or set(rows) != expected:
            raise ValueError("incomplete or foreign seven-kernel table")
    levels = scorer.levels(report, table)
    if levels["no row in the table"]:
        raise ValueError("a ready answer lacks a complete seven-kernel measurement")
    return levels


def grade(manifest_path: Path, output: Path) -> dict:
    manifest, questions, answers = validate_inputs(manifest_path)
    if output.exists():
        raise ValueError("use a fresh output directory; never reuse an old table")
    output.mkdir(parents=True)
    tasks = output / "tasks"
    report = scorer.prepare(questions, answers, tasks, normalise_name=False)
    (output / "spec-report.json").write_text(json.dumps(report, indent=2) + "\n")
    table = output / "spec-kernels.md"
    if report["stages"].get("ready", 0):
        command = [sys.executable, str(REPO / "t/recipes/bounded-grading-python.py"), "t/run_par.py",
                   "--tasks", str(tasks), "--table", str(table), "--out", str(output / "kernels"),
                   "--jobs", "1", "--no-cache"]
        with (output / "kernels.log").open("w") as log:
            result = subprocess.run(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode not in (0, 1) or not table.is_file():
            raise RuntimeError("the seven-kernel run failed before producing a complete table")
    levels = checked_levels(report, table)
    (output / "spec-levels.json").write_text(json.dumps(levels, indent=2) + "\n")
    sources = sorted((REPO / "t").glob("*.py")) + sorted((REPO / "t/verifiers").rglob("*.py"))
    sources += [Path(__file__), REPO / "t/recipes/bounded-grading-python.py"]
    receipt = {"label": manifest["label"], "answer_model": manifest["answer_model"],
               "input_manifest_sha256": digest(manifest_path), "questions": manifest["questions"],
               "answers": manifest["answers"], "levels": levels,
               "passes_spec33_requirement": levels["proved by all seven"] >= 27,
               "code_sha256": {str(path.relative_to(REPO)): digest(path) for path in sources}}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (output / "GRADED").write_text(digest(output / "receipt.json") + "\n")
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt = grade(args.manifest.resolve(), args.out.resolve())
    print(json.dumps({"levels": receipt["levels"], "passes_spec33_requirement": receipt["passes_spec33_requirement"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
