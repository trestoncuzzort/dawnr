"""Incomplete or mixed evidence must not satisfy the 33-specification release condition."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "recipes"))
import grade_spec33 as grade


@pytest.fixture
def inputs(tmp_path):
    questions = tmp_path / "questions.jsonl"
    shutil.copyfile(grade.REPO / "t/out/gcp-student-2026-10-11-s1/spec-heldout.jsonl", questions)
    answers = tmp_path / "answers.jsonl"
    rows = [{"name": row["name"], "reply": "no program", "model": "test-model", "system": "s1"}
            for row in grade.read_rows(questions)]
    answers.write_text("".join(json.dumps(row) + "\n" for row in rows))
    manifest = {"label": "test", "answer_model": "test-model",
                "questions": {"path": questions.name, "sha256": grade.digest(questions)},
                "answers": {"path": answers.name, "sha256": grade.digest(answers)}}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def replace_answers(path, rows):
    manifest = json.loads(path.read_text())
    answers = path.parent / manifest["answers"]["path"]
    answers.write_text("".join(json.dumps(row) + "\n" for row in rows))
    manifest["answers"]["sha256"] = grade.digest(answers)
    path.write_text(json.dumps(manifest))


def test_all_failed_answers_are_a_measured_zero_without_invoking_provers(inputs, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("there are no ready programs to grade")
    monkeypatch.setattr(grade.subprocess, "run", forbidden)
    receipt = grade.grade(inputs, tmp_path / "result")
    assert receipt["levels"]["questions"] == 33
    assert receipt["levels"]["proved by all seven"] == 0
    assert receipt["passes_spec33_requirement"] is False


def test_missing_or_duplicate_answer_is_refused(inputs):
    rows = grade.read_rows(inputs.parent / "answers.jsonl")
    replace_answers(inputs, rows[:-1])
    with pytest.raises(ValueError, match="exactly once"):
        grade.validate_inputs(inputs)
    replace_answers(inputs, rows[:-1] + [rows[0]])
    with pytest.raises(ValueError, match="exactly once"):
        grade.validate_inputs(inputs)


def test_an_altered_question_panel_cannot_be_selected(inputs):
    path = inputs.parent / "questions.jsonl"
    path.write_text(path.read_text() + "\n")
    manifest = json.loads(inputs.read_text())
    manifest["questions"]["sha256"] = grade.digest(path)
    inputs.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="registered 33 questions"):
        grade.validate_inputs(inputs)


def test_mixed_model_or_prompt_metadata_is_refused(inputs):
    rows = grade.read_rows(inputs.parent / "answers.jsonl")
    rows[0]["system"] = "v5"
    replace_answers(inputs, rows)
    with pytest.raises(ValueError, match="metadata differs"):
        grade.validate_inputs(inputs)


def test_partial_kernel_matrix_is_refused(tmp_path, monkeypatch):
    report = {"entries": {"first": {"stage": "ready"}, "second": {"stage": "ready"}}}
    monkeypatch.setattr(grade.spec_experiment, "parse_kernel_table", lambda _: (grade.spec_check.KERNELS, {"first": {}}))
    with pytest.raises(ValueError, match="incomplete or foreign"):
        grade.checked_levels(report, tmp_path / "table.md")


def test_missing_kernel_column_is_refused(tmp_path, monkeypatch):
    report = {"entries": {"first": {"stage": "ready"}}}
    monkeypatch.setattr(grade.spec_experiment, "parse_kernel_table", lambda _: (["dafny"], {"first": {}}))
    with pytest.raises(ValueError, match="seven-kernel table"):
        grade.checked_levels(report, tmp_path / "table.md")


@pytest.mark.skipif(sys.platform != "linux", reason="the remote decode launcher uses Linux flock")
def test_ask_mode_stops_before_any_local_grading(tmp_path):
    repo = tmp_path / "repo"
    (repo / "t").mkdir(parents=True)
    (repo / "t/score_spec_given.py").write_text(
        'import os,sys\nfrom pathlib import Path\n'
        'with Path(os.environ["CALL_LOG"]).open("a") as out: out.write(sys.argv[1]+"\\n")\n'
        'raise SystemExit(0 if sys.argv[1]=="ask" else 9)\n')
    binaries = tmp_path / "bin"
    binaries.mkdir()
    (binaries / "curl").write_text('#!/bin/sh\ntest -s "$SERVER_PID_FILE"\n')
    (binaries / "llama-server").write_text('#!/bin/sh\nprintf "%s\\n" "$$" > "$SERVER_PID_FILE"\nexec sleep 120\n')
    for path in binaries.iterdir():
        path.chmod(0o755)
    pid_file, log = tmp_path / "server.pid", tmp_path / "calls"
    environment = {**os.environ, "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
                   "D": str(repo), "L": str(binaries), "SERVER_PID_FILE": str(pid_file), "CALL_LOG": str(log)}
    script = grade.REPO / "t/recipes/spec33.sh"
    result = subprocess.run(["bash", str(script), "check", "unused.gguf", "ask"],
                            env=environment, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == ["ask"]
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)
