"""A real PEFT adapter must load exactly, update, and leave its parent untouched."""
from collections import OrderedDict
import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v6_corrective_sft import load_trainable_adapter
from v6_export import digest


def test_saved_adapter_is_exactly_loaded_and_only_its_copy_updates(tmp_path):
    torch = pytest.importorskip('torch')
    peft = pytest.importorskip('peft')
    torch.manual_seed(23)
    base = torch.nn.Sequential(OrderedDict([('proj', torch.nn.Linear(4, 3, bias=False))]))
    config = peft.LoraConfig(r=2, lora_alpha=4, target_modules=['proj'], lora_dropout=0, bias='none')
    parent = peft.get_peft_model(copy.deepcopy(base), config)
    with torch.no_grad():
        parent.base_model.model.proj.lora_A.default.weight.normal_()
        parent.base_model.model.proj.lora_B.default.weight.normal_()
    parent.eval()
    inputs = torch.randn(11, 4)
    expected = parent(inputs).detach()
    parent.save_pretrained(tmp_path)
    hashes = {n:digest(tmp_path / n) for n in ('adapter_config.json', 'adapter_model.safetensors')}
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'files': hashes}))
    child = load_trainable_adapter(copy.deepcopy(base), config, tmp_path, manifest)
    child.eval()
    torch.testing.assert_close(child(inputs), expected, rtol=0, atol=0)
    before = {n:p.detach().clone() for n,p in child.named_parameters()}
    child.train()
    optimizer = torch.optim.AdamW([p for p in child.parameters() if p.requires_grad], lr=.01)
    optimizer.zero_grad()
    child(inputs).square().mean().backward()
    optimizer.step()
    changed = [n for n,p in child.named_parameters() if not torch.equal(before[n], p.detach())]
    assert changed and all('lora_' in n for n in changed)
    for name, expected_hash in hashes.items():
        assert digest(tmp_path / name) == expected_hash
    wrong = copy.deepcopy(config)
    wrong.lora_alpha += 1
    with pytest.raises(ValueError, match='configuration differs'):
        load_trainable_adapter(copy.deepcopy(base), wrong, tmp_path, manifest)
    (tmp_path / 'adapter_model.safetensors').write_bytes(b'changed')
    with pytest.raises(ValueError, match='identity mismatch'):
        load_trainable_adapter(copy.deepcopy(base), config, tmp_path, manifest)
