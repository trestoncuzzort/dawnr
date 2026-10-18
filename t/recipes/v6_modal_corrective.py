"""Run the registered corrected-data stage on one H100 with preserved inputs.

Reuse the original v6 Modal image, cached base and volumes. This is a new
optimizer stage initialized from step 400, never a changed-data resume.
Sources: https://modal.com/docs/examples/long-training
https://huggingface.co/docs/peft/package_reference/peft_model
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import modal

if not modal.is_local():
    sys.path.insert(0, '/opt/dawnr/recipes')
from v6_modal import image as original_image, data, models, volumes, CACHE, MODEL, REVISION
from v6_corrective_sft import PARENT_CONFIG, PARENT_WEIGHTS, TRAINER_SHA
from v6_export import digest, verify_adapter

RUN = Path('/data/v6-20261018')
INPUT = RUN / 'corrective-inputs'
OUT = RUN / 'corrective-adapter'
PARENT = RUN / 'retained/checkpoint-400'
ROWS_SHA = '8aa1b7528363ebfa149e9b6a18ea9081c4904ff3d8687c240a9ea511d45c4794'
RECIPE_DIR = Path(__file__).resolve().parent if modal.is_local() else Path('/opt/dawnr/recipes')
image = original_image
for name in ('v6_modal.py', 'v6_corrective_sft.py', 'v6_export.py'):
    image = image.add_local_file(str(RECIPE_DIR / name), '/opt/dawnr/recipes/' + name)
app = modal.App('dawnr-v6-corrective', image=image)


@app.function(timeout=1200, cpu=4, memory=8192, volumes=volumes)
def prepare():
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer
    import importlib.util

    assert digest(INPUT / 'training-rows.jsonl') == ROWS_SHA
    build = json.loads((INPUT / 'build.json').read_text())
    assert build['files']['training-rows.jsonl'] == ROWS_SHA and build['rows'] == 4089
    audit = json.loads((INPUT / 'heldout-audit.json').read_text())
    assert audit['rows'] == 4089 and audit['flagged'] == []
    profile = json.loads((INPUT / 'tokenization.json').read_text())
    assert profile['sha256'] == ROWS_SHA and profile['rows'] == 4089 and profile['base_revision'] == REVISION
    parent_files = {'adapter_config.json': PARENT_CONFIG, 'adapter_model.safetensors': PARENT_WEIGHTS}
    for name, expected in parent_files.items():
        assert digest(PARENT / name) == expected
    assert json.loads((PARENT / 'trainer_state.json').read_text())['global_step'] == 400
    assert digest('/opt/dawnr/student_sft.py') == TRAINER_SHA
    snapshot = Path(snapshot_download(MODEL, revision=REVISION, cache_dir=CACHE, local_files_only=True))
    assert snapshot.name == REVISION
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
    spec = importlib.util.spec_from_file_location('corrective_encoder', '/opt/dawnr/student_sft.py')
    trainer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trainer)
    rows = trainer.load_rows(INPUT / 'training-rows.jsonl')
    used, encoded_hash = 0, hashlib.sha256()
    for row in rows:
        encoded = trainer.encode_row(tokenizer, row, 2**31 - 1)
        encoded_hash.update(json.dumps(encoded, sort_keys=True).encode() + b'\n')
        used += len(encoded['input_ids']) <= 2845
    assert encoded_hash.hexdigest() == profile['encoded_sha256']
    assert used == profile['used'] and len(rows) - used == len(profile['dropped'])
    manifest = {'step': 400, 'files': parent_files}
    path = INPUT / 'parent-manifest.json'
    if path.exists():
        assert json.loads(path.read_text()) == manifest
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    record = {'dataset_sha256': ROWS_SHA, 'base': MODEL, 'base_revision': REVISION,
        'snapshot': str(snapshot), 'parent': manifest, 'parent_manifest_sha256': digest(path),
        'rows': len(rows), 'rows_used': used, 'dropped_too_long': len(rows) - used,
        'encoded_sha256': encoded_hash.hexdigest(),
        'steps': math.ceil(used / 16), 'epochs': 1, 'lr': 2e-5, 'seed': 1,
        'batch': 1, 'grad_accum': 16, 'max_len': 2845, 'save_steps': 50,
        'trainer_sha256': TRAINER_SHA, 'wrapper_sha256': digest('/opt/dawnr/recipes/v6_corrective_sft.py'),
        'inputs_sha256': {name:digest(INPUT / name) for name in
            ('training-rows.jsonl', 'build.json', 'heldout-audit.json', 'tokenization.json', 'registration.md')}}
    path = INPUT / 'prepared.json'
    if path.exists():
        assert json.loads(path.read_text()) == record
    path.write_text(json.dumps(record, indent=2) + '\n')
    data.commit()
    return record


@app.function(gpu='H100', timeout=5700, cpu=8, memory=32768,
              max_containers=1, volumes=volumes)
def train():
    ready = json.loads((INPUT / 'prepared.json').read_text())
    assert ready['dataset_sha256'] == ROWS_SHA
    for name, expected in ready['inputs_sha256'].items():
        assert digest(INPUT / name) == expected
    assert digest('/opt/dawnr/student_sft.py') == ready['trainer_sha256'] == TRAINER_SHA
    assert digest('/opt/dawnr/recipes/v6_corrective_sft.py') == ready['wrapper_sha256']
    assert not (OUT / 'run.json').exists(), 'training is already complete'
    checkpoints = sorted((OUT / 'trainer').glob('checkpoint-*'), key=lambda p:int(p.name.split('-')[-1]))
    if checkpoints:
        required = ('adapter_config.json', 'adapter_model.safetensors', 'optimizer.pt',
                    'scheduler.pt', 'rng_state.pth', 'trainer_state.json', 'training_args.bin')
        latest = checkpoints[-1]
        assert all((latest / name).is_file() and (latest / name).stat().st_size for name in required), \
            'latest checkpoint is incomplete; preserve it and register a complete checkpoint before resuming'
        state = json.loads((latest / 'trainer_state.json').read_text())
        assert state['max_steps'] == ready['steps'] and state['global_step'] == int(latest.name.split('-')[-1])
    command = ['python', '/opt/dawnr/recipes/v6_corrective_sft.py',
        '--parent-adapter', str(PARENT), '--parent-manifest', str(INPUT / 'parent-manifest.json'),
        '--trainer', '/opt/dawnr/student_sft.py', '--model', ready['snapshot'],
        '--sft', str(INPUT / 'training-rows.jsonl'), '--sft-sha256', ROWS_SHA, '--out', str(OUT),
        '--rank', '64', '--alpha', '16', '--dropout', '0.1', '--lr', '2e-5', '--epochs', '1',
        '--max-len', '2845', '--seed', '1', '--batch', '1', '--grad-accum', '16',
        '--save-steps', '50', '--log-every', '10']
    attempts = RUN / 'corrective-attempts'
    attempts.mkdir(exist_ok=True)
    attempt = {'command': command, 'started': time.time(), 'gpu': 'H100',
               'prepared_sha256': digest(INPUT / 'prepared.json'), 'resume_checkpoint': checkpoints[-1].name if checkpoints else None}
    (attempts / (str(time.time_ns()) + '.json')).write_text(json.dumps(attempt, indent=2) + '\n')
    data.commit()
    stop = threading.Event()

    def sync():
        while not stop.wait(120):
            data.commit()

    thread = threading.Thread(target=sync, daemon=True)
    thread.start()
    try:
        with (RUN / 'corrective-train.log').open('a', buffering=1) as log:
            log.write(json.dumps(attempt) + '\n')
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=5400,
                env={**os.environ, 'HF_HUB_OFFLINE': '1', 'PYTHONUNBUFFERED': '1'})
        if process.returncode:
            raise RuntimeError('corrective trainer failed; inspect preserved log and checkpoints')
        record = json.loads((OUT / 'run.json').read_text())
        assert record['steps'] == ready['steps'] and record['rows_used'] == ready['rows_used']
        assert record['sft_sha256'] == ROWS_SHA and math.isfinite(record['train_loss'])
        assert all(math.isfinite(entry['loss']) for entry in record['log'])
        return {'steps': record['steps'], 'seconds': record['seconds'], 'train_loss': record['train_loss']}
    finally:
        stop.set()
        thread.join(timeout=5)
        data.commit()


@app.function(timeout=1200, cpu=4, memory=8192, volumes=volumes)
def finalize():
    import torch
    from safetensors.torch import load_file

    ready = json.loads((INPUT / 'prepared.json').read_text())
    record = json.loads((OUT / 'run.json').read_text())
    assert record['steps'] == ready['steps'] and record['sft_sha256'] == ROWS_SHA
    assert (record['recipe']['lr'], record['recipe']['epochs']) == (2e-5, 1)
    verify_adapter(PARENT, INPUT / 'parent-manifest.json')
    tensors = load_file(str(OUT / 'adapter_model.safetensors'))
    assert tensors and all(torch.isfinite(value).all() for value in tensors.values())
    assert digest(OUT / 'adapter_model.safetensors') != PARENT_WEIGHTS
    manifest = {'kind': 'corrective-sft', 'step': record['steps'], 'parent_step': 400,
        'parent_files': ready['parent']['files'], 'data_sha256': ROWS_SHA,
        'prepared_sha256': digest(INPUT / 'prepared.json'),
        'files': {str(path.relative_to(OUT)): digest(path) for path in sorted(OUT.rglob('*')) if path.is_file()}}
    path = RUN / 'corrective-manifest.json'
    if path.exists():
        assert json.loads(path.read_text()) == manifest
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    data.commit()
    return {'step': record['steps'], 'files': len(manifest['files']),
            'adapter_sha256': manifest['files']['adapter_model.safetensors']}


@app.local_entrypoint()
def main(mode: str = 'prepare'):
    functions = {'prepare': prepare, 'train': train, 'finalize': finalize}
    if mode not in functions:
        raise ValueError('mode must be prepare, train or finalize')
    call = functions[mode].spawn()
    print('Function call: ' + call.object_id, flush=True)
    print(json.dumps(call.get()), flush=True)
