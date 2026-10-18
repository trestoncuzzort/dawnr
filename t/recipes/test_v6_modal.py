"""A stopped run must resume complete, unchanged data without discarding partial artifacts."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip("modal")
spec = importlib.util.spec_from_file_location("v6_modal", Path(__file__).with_name("v6_modal.py"))
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.setattr(recipe, "RUN", tmp_path)
    monkeypatch.setattr(recipe, "ROWS_SHA", hashlib.sha256(b"rows").hexdigest())
    monkeypatch.setattr(recipe, "data", type("Volume", (), {"commit": lambda self: None})())
    out = tmp_path / "adapter"
    out.mkdir()
    (out / "training-rows.jsonl").write_bytes(b"rows")
    (out / "training-data.json").write_text("{}")
    (tmp_path / "resume.json").write_text(json.dumps(
        {"trainer_sha256": recipe.TRAINER_SHA, "data_sha256": recipe.ROWS_SHA, "from_step": 300}))
    return tmp_path


def save(run, step, complete=True):
    directory = run / "adapter/trainer" / f"checkpoint-{step}"
    directory.mkdir(parents=True)
    for name in ["adapter_config.json", "adapter_model.safetensors", "optimizer.pt",
                 "scheduler.pt", "rng_state.pth", "training_args.bin"]:
        (directory / name).write_bytes(b"saved")
    if complete:
        (directory / "trainer_state.json").write_text(json.dumps({"global_step": step, "max_steps": 1275}))
    return directory


def test_resume_chooses_latest_complete_checkpoint_and_preserves_partial_files(run):
    save(run, 300)
    save(run, 400)
    partial = save(run, 500, complete=False)
    result = recipe.checkpoint.local()
    assert result["step"] == 400 and result["skipped_incomplete"] == ["checkpoint-500"]
    assert not partial.exists()
    preserved = list((run / "incomplete-checkpoints").glob("checkpoint-500-*"))
    assert len(preserved) == 1 and (preserved[0] / "optimizer.pt").read_bytes() == b"saved"
    manifest = json.loads((run / "checkpoint-manifest.json").read_text())
    assert manifest["checkpoint"] == "checkpoint-400"
    assert all("checkpoint-500" not in name for name in manifest["files"])


def test_changed_rows_cannot_resume(run):
    save(run, 400)
    (run / "adapter/training-rows.jsonl").write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="data changed"):
        recipe.checkpoint.local()
    assert not (run / "checkpoint-manifest.json").exists()


def test_cannot_resume_before_the_previously_registered_progress(run):
    save(run, 200)
    with pytest.raises(RuntimeError, match="registered continuation"):
        recipe.checkpoint.local()


def test_completed_training_is_not_resumed(run):
    (run / "adapter/run.json").write_text("{}")
    with pytest.raises(RuntimeError, match="complete"):
        recipe.checkpoint.local()
