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


def test_incomplete_average_identity_is_refused(tmp_path):
    manifest = fixture(tmp_path)
    with pytest.raises(ValueError, match="both an adapter and its manifest"):
        export.export_inputs(tmp_path, manifest, tmp_path)


def test_checkpoint_average_preserves_the_two_saved_linear_models(tmp_path):
    torch = pytest.importorskip("torch")
    peft = pytest.importorskip("peft")
    from collections import OrderedDict
    import copy

    torch.manual_seed(23)
    base = torch.nn.Sequential(OrderedDict([("proj", torch.nn.Linear(4, 3, bias=False))]))
    inputs = torch.randn(11, 4)
    predictions, paths, identities = [], [], []
    for i in range(2):
        model = peft.get_peft_model(copy.deepcopy(base), peft.LoraConfig(
            r=2, lora_alpha=4, target_modules=["proj"], lora_dropout=0, bias="none"))
        with torch.no_grad():
            model.base_model.model.proj.lora_A.default.weight.copy_(torch.randn(2, 4))
            model.base_model.model.proj.lora_B.default.weight.copy_(torch.randn(3, 2))
        model.eval()
        predictions.append(model(inputs).detach())
        path = tmp_path / str(i)
        model.save_pretrained(path)
        record = {"step": i, "files": {name: export.digest(path / name) for name in
                  ("adapter_config.json", "adapter_model.safetensors")}}
        (path / "manifest.json").write_text(json.dumps(record))
        paths.append(path)
        identities.append(record)

    source = export.export_inputs(paths[0], paths[0] / "manifest.json",
                                  paths[1], paths[1] / "manifest.json")
    assert source["components"] == identities and "step" not in source
    merged = export.merge_saved_adapters(copy.deepcopy(base), *paths)
    torch.testing.assert_close(merged(inputs), (predictions[0] + predictions[1]) / 2,
                               rtol=1e-5, atol=1e-5)
    assert all("lora" not in name for name, _ in merged.named_parameters())
    for path, identity in zip(paths, identities):
        assert export.verify_adapter(path, path / "manifest.json") == identity

    config_path = paths[1] / "adapter_config.json"
    config = json.loads(config_path.read_text())
    config["lora_alpha"] += 1
    config_path.write_text(json.dumps(config))
    identities[1]["files"]["adapter_config.json"] = export.digest(config_path)
    (paths[1] / "manifest.json").write_text(json.dumps(identities[1]))
    with pytest.raises(ValueError, match="identical adapter configurations"):
        export.export_inputs(paths[0], paths[0] / "manifest.json",
                             paths[1], paths[1] / "manifest.json")
