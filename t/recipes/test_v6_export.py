"""Export must consume the exact adapter that was selected and preserved."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("v6_export", Path(__file__).with_name("v6_export.py"))
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


def fixture(tmp_path):
    for name, data in [("adapter_config.json", b'{}'), ("adapter_model.safetensors", b'weights')]:
        (tmp_path / name).write_bytes(data)
    record = {"step": 400, "files": {name: export.digest(tmp_path / name) for name in
                                    ("adapter_config.json", "adapter_model.safetensors")}}
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(record))
    return manifest


def test_a_preserved_adapter_is_identified_without_changing_its_files(tmp_path):
    manifest = fixture(tmp_path)
    assert export.verify_adapter(tmp_path, manifest)["step"] == 400
    assert (tmp_path / "adapter_model.safetensors").read_bytes() == b"weights"


@pytest.mark.parametrize("name", ["adapter_config.json", "adapter_model.safetensors"])
def test_a_changed_adapter_cannot_be_exported_as_the_selected_one(tmp_path, name):
    manifest = fixture(tmp_path)
    (tmp_path / name).write_bytes(b"different")
    with pytest.raises(ValueError, match="identity mismatch"):
        export.verify_adapter(tmp_path, manifest)
