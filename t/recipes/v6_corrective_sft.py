"""Initialize a separate SFT stage from a verified adapter using the unchanged trainer.

This loads adapter weights, not the parent's optimizer or data cursor. A later
interruption may resume only this new stage's own saved state and exact recipe.
Source: https://huggingface.co/docs/peft/package_reference/peft_model
Prior art: student_sft.snapshot_rows and v6_export.verify_adapter.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

from v6_export import digest, verify_adapter

TRAINER_SHA = 'e43c27df1ee1e796b1799d38a16e0c5725dd09df762be3fabb2940ad8cb4a46f'
PARENT_WEIGHTS = 'af314c4595d8e648b1a219097d5985ba30b5afb420733ae9da600bb967b54583'
PARENT_CONFIG = '9c8bb1b245107292a495fde1a14d2323ee70eb985a5bed887a865719e65ac178'


def load_trainable_adapter(base, requested, adapter, manifest):
    import peft
    import torch
    from safetensors.torch import load_file

    verify_adapter(adapter, manifest)
    saved = json.loads((adapter / 'adapter_config.json').read_text())
    for key in ('r', 'lora_alpha', 'lora_dropout', 'bias', 'task_type', 'peft_type'):
        expected = getattr(requested, key)
        if saved.get(key) != expected:
            raise ValueError('parent adapter configuration differs: ' + key)
    if any(saved.get(key) for key in ('modules_to_save', 'lora_bias', 'use_dora', 'use_rslora',
            'use_qalora', 'use_bdlora', 'rank_pattern', 'alpha_pattern', 'target_parameters',
            'trainable_token_indices', 'alora_invocation_tokens')):
        raise ValueError('only the registered plain LoRA adapter is supported')
    if requested.target_modules != 'all-linear' and set(saved['target_modules']) != set(requested.target_modules):
        raise ValueError('parent target modules differ')
    model = peft.PeftModel.from_pretrained(base, str(adapter), is_trainable=True)
    expected = load_file(str(adapter / 'adapter_model.safetensors'), device='cpu')
    actual = peft.get_peft_model_state_dict(model)
    if expected.keys() != actual.keys():
        raise ValueError('loaded adapter tensor names differ from the saved parent')
    for key, value in expected.items():
        loaded = actual[key].detach().cpu()
        if value.shape != loaded.shape or not torch.equal(value.to(loaded.dtype), loaded):
            raise ValueError('loaded parent adapter tensor differs: ' + key)
    trainable = {name: parameter for name, parameter in model.named_parameters() if parameter.requires_grad}
    if not trainable or any('lora_' not in name for name in trainable):
        raise ValueError('only adapter parameters may be trainable')
    if sum(p.numel() for p in trainable.values()) != sum(p.numel() for p in expected.values()):
        raise ValueError('some saved adapter parameters are not trainable')
    model.train()
    return model


def initialization_record(parent, manifest, trainer, trainer_args, out):
    if digest(trainer) != TRAINER_SHA:
        raise ValueError('the pinned trainer source changed')
    source = verify_adapter(parent, manifest)
    if source['step'] != 400 or source['files']['adapter_model.safetensors'] != PARENT_WEIGHTS:
        raise ValueError('corrective stage must start from the preserved step-400 adapter')
    if source['files']['adapter_config.json'] != PARENT_CONFIG:
        raise ValueError('preserved step-400 configuration changed')
    record = {'schema': 1, 'kind': 'new-stage-from-parent-adapter',
        'parent_step': 400, 'parent_files': {n:source['files'][n] for n in
            ('adapter_config.json', 'adapter_model.safetensors')},
        'parent_manifest_sha256': digest(manifest), 'trainer_sha256': TRAINER_SHA,
        'wrapper_sha256': digest(Path(__file__)), 'trainer_args': trainer_args,
        'parent_optimizer_loaded': False, 'parent_data_cursor_loaded': False}
    path = out / 'initialization.json'
    if path.exists():
        if json.loads(path.read_text()) != record:
            raise ValueError('the corrective stage recipe or parent changed')
        if (out / 'run.json').exists():
            raise ValueError('corrective training already completed')
    else:
        if out.exists() and any(out.iterdir()):
            raise ValueError('use a fresh output directory for the corrective stage')
        out.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2) + '\n')
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--parent-adapter', type=Path, required=True)
    parser.add_argument('--parent-manifest', type=Path, required=True)
    parser.add_argument('--trainer', type=Path, required=True)
    args, training_args = parser.parse_known_args(argv)
    if '--merge' in training_args or '--out' not in training_args or '--sft-sha256' not in training_args:
        parser.error('training requires an explicit output directory and dataset checksum')
    out = Path(training_args[training_args.index('--out') + 1])
    initialization_record(args.parent_adapter, args.parent_manifest, args.trainer, training_args, out)
    module_spec = importlib.util.spec_from_file_location('corrective_student_sft', args.trainer)
    trainer = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(trainer)
    loaded = []

    def initialize(base, config):
        if loaded:
            raise ValueError('trainer attempted to initialize the adapter twice')
        model = load_trainable_adapter(base, config, args.parent_adapter, args.parent_manifest)
        loaded.append(True)
        return model

    # The import inside student_sft.main sees this scoped factory. Its loss,
    # tokenizer, quantization, optimizer and checkpoint handling stay unchanged.
    with patch('peft.get_peft_model', initialize):
        code = trainer.main(training_args)
    if loaded != [True] or code != 0:
        raise RuntimeError('the trainer did not finish through the registered initializer')
    verify_adapter(args.parent_adapter, args.parent_manifest)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
