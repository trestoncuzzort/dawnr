"""Private data builds must preserve input identity and fail before publishing a completed receipt."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "recipes"))
import prepare_release_rows as prep


@pytest.fixture
def inputs(tmp_path):
    root = tmp_path / "inputs"
    root.mkdir()
    (root / "base.jsonl").write_text('{"prompt":"base","chosen":"original"}\n')
    row = {"task_id": 7, "tasks": [{"name": "spec"}],
           "reference": [{"status": "agrees", "draws": 1000, "completeness": 1.0, "cross_completeness": 0.95}]}
    (root / "kept.jsonl").write_text(json.dumps(row) + "\n")
    report = {"pool": "v5", "draws": 1000, "floor": 0.9, "problems_kept": 1, "candidates_kept": 1}
    (root / "strict.json").write_text(json.dumps(report))
    entry = lambda name: {"path": name, "sha256": prep.digest(root / name)}
    manifest = {"label": "pilot", "base": {**entry("base.jsonl"), "rows": 1},
                "sources": [{"tag": "cohere:command-a:pilot", "kept": entry("kept.jsonl"), "report": entry("strict.json")}]}
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def test_pinned_strict_inputs_are_accepted(inputs):
    manifest, base, sources = prep.validate_inputs(inputs)
    assert manifest["base"]["rows"] == 1
    assert base.name == "base.jsonl" and sources[0][0]["tag"] == "cohere:command-a:pilot"


def test_changed_input_is_refused_before_build(inputs):
    (inputs.parent / "kept.jsonl").write_text("changed")
    with pytest.raises(ValueError, match="digest differs"):
        prep.validate_inputs(inputs)


def test_a_source_without_strict_evidence_is_refused(inputs):
    path = inputs.parent / "kept.jsonl"
    rows = prep.read_rows(path)
    rows[0]["reference"] = []
    path.write_text(json.dumps(rows[0]) + "\n")
    manifest = json.loads(inputs.read_text())
    manifest["sources"][0]["kept"]["sha256"] = prep.digest(path)
    inputs.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="strict evidence"):
        prep.validate_inputs(inputs)


def test_input_cannot_escape_the_archive_directory(inputs):
    manifest = json.loads(inputs.read_text())
    manifest["base"]["path"] = "../elsewhere.jsonl"
    inputs.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="within the private input"):
        prep.validate_inputs(inputs)


def stand_in_builder(monkeypatch):
    def build(arguments):
        args = dict(zip(arguments[::2], arguments[1::2]))
        rows = prep.read_rows(Path(args["--base"]))
        rows.append({"prompt": "new", "chosen": "checked", "tag": args["--tag"]})
        Path(args["--out"]).write_text("".join(json.dumps(row) + "\n" for row in rows))
        Path(args["--report"]).write_text(json.dumps({"added": {"rows": 1, "problems": 1}}))
    monkeypatch.setattr(prep.v8_spec_rows, "main", build)


def test_failed_whole_dataset_audit_never_writes_completion(inputs, tmp_path, monkeypatch):
    stand_in_builder(monkeypatch)
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])
    monkeypatch.setattr(prep.subprocess, "run", fail)
    out = tmp_path / "result"
    with pytest.raises(subprocess.CalledProcessError):
        prep.build(inputs, out, 2)
    assert not (out / "COMPLETE").exists()
    assert not (out / "rows-manifest.json").exists()


def test_success_retains_source_and_requires_the_named_audit_flags(inputs, tmp_path, monkeypatch):
    stand_in_builder(monkeypatch)
    def audit(command, **kwargs):
        assert "--panels" in command and "--refuse-gpl" in command
        report = Path(command[command.index("--json") + 1])
        report.write_text(json.dumps({"rows": 2, "flagged": [], "findings": [], "unparsed": 0}))
    monkeypatch.setattr(prep.subprocess, "run", audit)
    out = tmp_path / "result"
    receipt = prep.build(inputs, out, 2)
    rows = prep.read_rows(out / "training-rows.jsonl")
    assert rows[0] == {"prompt": "base", "chosen": "original"}
    assert rows[1]["tag"] == "cohere:command-a:pilot"
    assert receipt["output"]["rows"] == 2 and receipt["audit"]["flagged"] == 0
    assert (out / "COMPLETE").read_text().strip() == prep.digest(out / "training-rows.jsonl")
