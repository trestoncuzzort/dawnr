import hashlib
import json
from pathlib import Path
import sys
from threading import Lock

import pytest

sys.path.insert(0, str(Path(__file__).parent / "recipes"))
import diagnose_framac as diagnostic
from verifiers import Result


def inputs(tmp_path):
    pair = {"id": "control"}
    for side in ("real", "twin"):
        path = tmp_path / (side + ".c")
        path.write_text(side)
        pair[side] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"pairs": [pair]}))
    return path


def test_replay_retains_disagreement_and_every_repetition(tmp_path):
    manifest = inputs(tmp_path)
    seen, lock = {}, Lock()

    def verify(path):
        with lock:
            index = seen.get(path.name, 0)
            seen[path.name] = index + 1
        outcome = "refuted" if path.name == "twin.c" else ("verified" if index == 0 else "timeout")
        return Result("framac", "test", diagnostic.digest(path), outcome, error=str(index))

    output = tmp_path / "results"
    record = diagnostic.diagnose(manifest, output, verify)
    pair = record["pairs"][0]
    assert len(pair["calls"]) == 6
    assert pair["agreement"] == {"real": False, "twin": True}
    assert sorted(c["outcome"] for c in pair["calls"] if c["side"] == "real") == ["timeout", "timeout", "verified"]
    assert list(p.name for p in output.iterdir()) == ["diagnostic.json"]
    assert "passes_spec33_requirement" not in record


def test_changed_source_is_refused_before_any_kernel_call(tmp_path):
    manifest = inputs(tmp_path)
    (tmp_path / "real.c").write_text("changed")
    with pytest.raises(ValueError, match="digest"):
        diagnostic.diagnose(manifest, tmp_path / "results", lambda path: pytest.fail("kernel called"))
    assert not (tmp_path / "results").exists()
