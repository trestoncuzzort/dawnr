"""Identical labels cannot substitute for matching weights and observed inputs."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent / 'recipes'))
import release_model_identity as identity


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    export_root = tmp_path / 'export'; export_root.mkdir()
    spec_root = tmp_path / 'spec33'; spec_root.mkdir()
    config_sha = 'c' * 64; model_sha = 'd' * 64
    config = {'root': '/registered/job', 'checkout': '/registered/code', 'llama': '/registered/llama',
              'unit': 'registered-model.service', 'questions_path': 'questions.jsonl',
              'questions_sha256': '', 'server_revision': identity.selection.CONVERTER,
              'observer_sha256': 'e' * 64, 'training_manifest_sha256': 'a' * 64,
              'worker_sha256': {'train.py': 'f' * 64},
              'seeds': {'1': {'prefix': 'candidate-s1', 'export_name': 'export-s1'}}}
    registration = {'seeds': config['seeds'], 'training_rows_sha256': '1' * 64,
                    'training_input_manifest_sha256': 'a' * 64, 'trainer_sha256': 'b' * 64,
                    'steps_per_seed': 2160}
    manifest = {'input_sha256': {'training-rows.jsonl': '1' * 64},
                'rows': 6954, 'rows_used': 6904, 'rows_skipped': 50, 'steps': 2160,
                'recipe': {'lr': 2e-4, 'epochs': 5, 'max_len': 2845, 'batch': 1,
                           'grad_accum': 16, 'rank': 64, 'alpha': 16, 'dropout': .1}}
    run = {'sft_sha256': '1' * 64, 'rows_selected': 6954, 'rows_used': 6904,
           'rows_dropped_too_long': 50, 'steps': 2160, 'train_loss': .1,
           'recipe': {'seed': 1, **{k: manifest['recipe'][k] for k in ('lr', 'epochs', 'max_len', 'batch', 'grad_accum')},
                      'lora': {'r': 64, 'alpha': 16, 'dropout': .1}}}
    prepared = {'manifest_sha256': 'a' * 64, 'seed': 1, 'trainer_sha256': 'b' * 64, 'worker_sha256': 'f' * 64}
    write(export_root / 'run.json', run); write(export_root / 'prepared.json', prepared)
    adapter = {'kind': 'cohere-curated-sft', 'seed': 1, 'step': 2160, 'data_sha256': '1' * 64,
               'prepared_sha256': identity.digest(export_root / 'prepared.json'),
               'files': {'run.json': identity.digest(export_root / 'run.json'),
                         'prepared.json': identity.digest(export_root / 'prepared.json'),
                         'adapter_config.json': '2' * 64, 'adapter_model.safetensors': '3' * 64}}
    exported = {'base': identity.selection.MODEL, 'revision': identity.selection.REVISION,
                'converter_commit': identity.selection.CONVERTER, 'quantization': 'Q8_0',
                'merge_dtype': 'bfloat16', 'name': 'export-s1', 'adapter': adapter,
                'output': {'filename': 'model-Q8_0.gguf', 'bytes': 2048, 'sha256': model_sha}}
    write(export_root / 'export.json', exported)
    write(export_root / 'inputs.json', {k: v for k, v in exported.items() if k != 'output'})
    write(export_root / 'adapter-manifest.json', adapter)
    (export_root / 'SHA256SUMS').write_text(model_sha + '  model-Q8_0.gguf\n')
    observed = {'seed': 1, 'model_sha256': model_sha, 'registration_sha256': config_sha,
                'export_sha256': identity.digest(export_root / 'export.json'),
                'model_file': {'bytes': 2048, 'device': 1, 'inode': 10, 'mtime_ns': 100, 'ctime_ns': 100},
                'files': identity.files(export_root)}
    write(export_root / 'observed.json', observed)
    questions = ''.join(json.dumps({'name': f'q{i}'}) + '\n' for i in range(33)).encode()
    config['questions_sha256'] = hash_bytes(questions)
    monkeypatch.setattr(identity, 'QUESTIONS_SHA', hash_bytes(questions))
    answers = [{'name': f'q{i}', 'model': 'candidate-s1', 'system': 's1',
                'tokens': 3, 'stopped': True, 'reply': 'fixture'} for i in range(33)]
    (spec_root / 'answers.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in answers))
    (spec_root / 'server.log').write_text('fixture log')
    server = {'pid': 10, 'parent_pid': 9, 'start_ticks': 100, 'state': 'S',
              'command': identity.server_command(config, 1), 'cwd': config['checkout'],
              'exe': config['llama'] + '/build/bin/llama-server',
              'cgroup': ['0::/system.slice/' + config['unit']]}
    start = {'seed': 1, 'initial_answer_bytes': 0, 'registration_sha256': config_sha, 'server': server,
             'export_observation_sha256': identity.digest(export_root / 'observed.json'),
             'model_sha256': model_sha, 'server_binary_sha256': '4' * 64,
             'runtime_files_sha256': {server['exe']: '4' * 64}, 'utc': '2026-10-29T00:00:00+00:00'}
    client = {'pid': 11, 'parent_pid': 9, 'start_ticks': 101, 'state': 'R',
              'command': ['python3'] + identity.client_command(config, 1),
              'cwd': config['checkout'], 'cgroup': server['cgroup'],
              'server_owned_listener': True, 'observed_utc': '2026-10-29T00:00:01+00:00'}
    record = {'kind': 'observed-spec33-generation', 'seed': 1, 'prefix': 'candidate-s1', 'start': start, 'client': client,
              'model_sha256': model_sha, 'observer_sha256': config['observer_sha256'],
              'server_revision': config['server_revision'], 'model_file_unchanged': True, 'sources_rechecked': True,
              'complete_answers': 33, 'completed_utc': '2026-10-29T00:00:02+00:00',
              'questions_sha256': hash_bytes(questions), 'answers_sha256': identity.digest(spec_root / 'answers.jsonl'),
              'server_log_sha256': identity.digest(spec_root / 'server.log')}
    write(spec_root / 'start.json', start); write(spec_root / 'client.json', client); write(spec_root / 'identity.json', record)
    return export_root, spec_root, registration, manifest, config, config_sha, questions


def exported(evidence):
    folder, _, reg, manifest, config, config_sha, _ = evidence
    return identity.export_identity(folder, 1, reg, manifest, config, config_sha)


def measured(evidence):
    _, folder, _, _, config, config_sha, questions = evidence
    return identity.spec33_identity(folder, 1, exported(evidence), config, config_sha, questions)


def test_complete_observed_identity_matches_the_final_export(evidence):
    record = measured(evidence)
    assert record['model_sha256'] == 'd' * 64
    assert record['answers_sha256'] == identity.digest(evidence[1] / 'answers.jsonl')


@pytest.mark.parametrize('change', ['checksum', 'input-receipt', 'adapter', 'training', 'prepared', 'missing', 'foreign', 'model-stat'])
def test_changed_export_or_training_metadata_is_refused(evidence, change):
    root = evidence[0]
    if change == 'checksum': (root / 'SHA256SUMS').write_text('0' * 64 + '  model-Q8_0.gguf')
    elif change == 'input-receipt': write(root / 'inputs.json', {})
    elif change == 'adapter': write(root / 'adapter-manifest.json', {})
    elif change == 'training': write(root / 'run.json', {})
    elif change == 'prepared': write(root / 'prepared.json', {})
    elif change == 'missing': (root / 'observed.json').unlink()
    elif change == 'foreign': write(root / 'foreign.json', {})
    else:
        data = identity.read(root / 'observed.json'); data['model_file']['bytes'] = 4096
        write(root / 'observed.json', data)
    with pytest.raises(ValueError): exported(evidence)


@pytest.mark.parametrize('change', ['weight', 'registration', 'existing-answer', 'observer', 'source', 'command',
                                    'parent', 'listener', 'process-order', 'clock', 'question', 'runtime'])
def test_consistent_labels_do_not_hide_changed_generation_provenance(evidence, change):
    root = evidence[1]; record = identity.read(root / 'identity.json')
    if change == 'weight': record['model_sha256'] = record['start']['model_sha256'] = '9' * 64
    elif change == 'registration': record['start']['registration_sha256'] = '9' * 64
    elif change == 'existing-answer': record['start']['initial_answer_bytes'] = 1
    elif change == 'observer': record['observer_sha256'] = '9' * 64
    elif change == 'source': record['sources_rechecked'] = False
    elif change == 'command': record['client']['command'][-1] = '2048'
    elif change == 'parent': record['client']['parent_pid'] = 12
    elif change == 'listener': record['client']['server_owned_listener'] = False
    elif change == 'process-order': record['client']['start_ticks'] = 99
    elif change == 'clock': record['completed_utc'] = '2026-10-28T00:00:00+00:00'
    elif change == 'question': record['questions_sha256'] = '9' * 64
    else: record['start']['runtime_files_sha256'] = {}
    # Keep the duplicated component records consistent, so rejection must come
    # from the actual provenance check rather than just unequal copies.
    write(root / 'start.json', record['start']); write(root / 'client.json', record['client'])
    write(root / 'identity.json', record)
    with pytest.raises(ValueError): measured(evidence)


@pytest.mark.parametrize('change', ['different-answer', 'missing-answer', 'foreign-answer'])
def test_observed_answer_bytes_and_exact_panel_are_required(evidence, change):
    root = evidence[1]; rows = identity.read_jsonl((root / 'answers.jsonl').read_bytes())
    if change == 'different-answer': rows[0]['reply'] = 'changed'
    elif change == 'missing-answer': rows.pop()
    else: rows[0]['name'] = 'foreign'
    (root / 'answers.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    with pytest.raises(ValueError): measured(evidence)
