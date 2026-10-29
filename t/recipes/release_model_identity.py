"""Bind authenticated export and observed generation artifacts to one trained seed.

The caller authenticates the encrypted objects and frozen observer configuration.
These checks read metadata and saved answers only; they never run model inference.
Sources: release_seed_selection.validate_export; the registered training worker's
completed check; the prospective identity observer; v6_export.py.
https://github.com/trestoncuzzort/dawnr/blob/main/t/recipes/v6_export.py
"""
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

import release_seed_selection as selection
from release_grading_inputs import QUESTIONS_SHA, require, digest, read_jsonl
from release_grade_audit import files

EXPORT_FILES = {'export.json', 'inputs.json', 'SHA256SUMS', 'adapter-manifest.json',
                'run.json', 'prepared.json', 'observed.json'}
SPEC_FILES = {'identity.json', 'start.json', 'client.json', 'answers.jsonl', 'server.log'}


def read(path):
    return json.loads(Path(path).read_text())


def exact_files(root, expected):
    hashes = files(root)
    require(set(hashes) == expected, 'missing or foreign identity evidence file')
    return hashes


def export_identity(root, seed, registration, training_manifest, config, config_sha):
    root = Path(root); hashes = exact_files(root, EXPORT_FILES)
    exported, observed = read(root / 'export.json'), read(root / 'observed.json')
    model_sha = selection.validate_export(exported, seed, registration)
    require(read(root / 'inputs.json') == {k: v for k, v in exported.items() if k != 'output'},
            'export input receipt differs')
    adapter = read(root / 'adapter-manifest.json')
    require(adapter == exported['adapter'], 'export uses another adapter manifest')
    require((root / 'SHA256SUMS').read_text().split() == [model_sha, 'model-Q8_0.gguf'],
            'export checksum list differs')
    require(observed['seed'] == seed and observed['model_sha256'] == model_sha
            and observed['export_sha256'] == hashes['export.json']
            and observed['registration_sha256'] == config_sha
            and observed['files'] == {k: v for k, v in hashes.items() if k != 'observed.json'},
            'observed export differs from its sealed files')
    identity = observed['model_file']
    require(set(identity) == {'device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns'}
            and all(selection.integer(v) for v in identity.values())
            and identity['bytes'] == exported['output']['bytes'], 'observed weight-file identity differs')
    require(training_manifest['input_sha256']['training-rows.jsonl'] == registration['training_rows_sha256']
            and config['training_manifest_sha256'] == registration['training_input_manifest_sha256'],
            'training input registration differs')
    for name in ('run.json', 'prepared.json'):
        require(hashes[name] == adapter['files'][name], 'training metadata differs from exported adapter')
    prepared = read(root / 'prepared.json')
    require(prepared == {'manifest_sha256': registration['training_input_manifest_sha256'], 'seed': seed,
                          'trainer_sha256': registration['trainer_sha256'],
                          'worker_sha256': config['worker_sha256']['train.py']}, 'training preparation differs')
    run = read(root / 'run.json'); recipe = run['recipe']; expected = training_manifest['recipe']
    require(run['sft_sha256'] == registration['training_rows_sha256']
            and run['rows_selected'] == training_manifest['rows']
            and run['rows_used'] == training_manifest['rows_used']
            and run['rows_dropped_too_long'] == training_manifest['rows_skipped']
            and run['steps'] == registration['steps_per_seed'] == training_manifest['steps']
            and recipe['seed'] == seed and type(run['train_loss']) in (float, int)
            and math.isfinite(run['train_loss']), 'completed training differs')
    require(all(recipe[name] == expected[name] for name in ('lr', 'epochs', 'max_len', 'batch', 'grad_accum'))
            and recipe['lora']['r'] == expected['rank'] and recipe['lora']['alpha'] == expected['alpha']
            and recipe['lora']['dropout'] == expected['dropout'], 'completed training recipe differs')
    return {'kind': 'audited-final-export-identity', 'seed': seed, 'model_sha256': model_sha,
            'export': exported, 'export_observation_sha256': hashes['observed.json'],
            'registration_sha256': config_sha, 'files_sha256': hashes}


def server_command(config, seed):
    return [config['llama'] + '/build/bin/llama-server', '--model',
            config['root'] + f'/export-{seed}/model-Q8_0.gguf', '--alias', 'dawnr-33',
            '--host', '127.0.0.1', '--port', '8853', '--n-gpu-layers', '99', '--threads', '8',
            '--parallel', '1', '--ctx-size', '8192', '--chat-template-kwargs', '{"enable_thinking":false}']


def client_command(config, seed):
    prefix = config['seeds'][str(seed)]['prefix']
    return ['t/score_spec_given.py', 'ask', '--model', prefix, '--host', '127.0.0.1:8853',
            '--questions', config['questions_path'], '--out',
            config['checkout'] + '/t/out/spec33-' + prefix + '/spec-answers.jsonl',
            '--system', 's1', '--max-new', '1024']


def instant(value):
    value = datetime.fromisoformat(value)
    require(value.tzinfo is not None, 'observation time lacks a timezone')
    return value


def spec33_identity(root, seed, export_audit, config, config_sha, questions):
    root = Path(root); hashes = exact_files(root, SPEC_FILES)
    identity, start, client = (read(root / name) for name in ('identity.json', 'start.json', 'client.json'))
    prefix = config['seeds'][str(seed)]['prefix']; model_sha = export_audit['model_sha256']
    require(export_audit['seed'] == seed and export_audit['registration_sha256'] == config_sha,
            'spec33 observation uses another export registration')
    require(identity['kind'] == 'observed-spec33-generation' and identity['seed'] == seed
            and identity['prefix'] == prefix and identity['start'] == start and identity['client'] == client,
            'spec33 observation belongs to another invocation')
    require(start['seed'] == seed and start['initial_answer_bytes'] == 0 and start['registration_sha256'] == config_sha
            and start['export_observation_sha256'] == export_audit['export_observation_sha256']
            and identity['model_sha256'] == start['model_sha256'] == model_sha,
            'spec33 answers are not bound to the observed model')
    require(identity['observer_sha256'] == config['observer_sha256']
            and identity['server_revision'] == config['server_revision']
            and identity['model_file_unchanged'] is True and identity['sources_rechecked'] is True
            and identity['complete_answers'] == 33, 'generation observation is incomplete or changed')
    server = start['server']
    require(server['command'] == server_command(config, seed) and server['cwd'] == config['checkout']
            and server['exe'] == config['llama'] + '/build/bin/llama-server', 'observed server command differs')
    require(client['command'][1:] == client_command(config, seed) and client['cwd'] == config['checkout']
            and client['parent_pid'] == server['parent_pid'] and client['cgroup'] == server['cgroup']
            and client['server_owned_listener'] is True, 'client is not bound to the observed server')
    require(any(line.split(':', 2)[-1] == '/system.slice/' + config['unit'] for line in server['cgroup']),
            'server is outside the registered job')
    for process in (server, client):
        require(all(selection.integer(process[name], 1) for name in ('pid', 'parent_pid', 'start_ticks'))
                and process['state'] in ('R', 'S', 'D', 'I'), 'invalid observed process identity')
    require(server['pid'] != client['pid'] and server['start_ticks'] <= client['start_ticks'],
            'server/client process ordering differs')
    runtime = start['runtime_files_sha256']
    require(runtime and runtime.get(server['exe']) == start['server_binary_sha256'], 'server runtime fingerprint differs')
    for value in runtime.values(): selection.check_digest(value)
    require(instant(start['utc']) <= instant(client['observed_utc']) <= instant(identity['completed_utc']),
            'observation chronology differs')
    require(hashlib.sha256(questions).hexdigest() == identity['questions_sha256'] == config['questions_sha256'] == QUESTIONS_SHA,
            'spec33 question identity differs')
    names = [row['name'] for row in read_jsonl(questions)]
    answers = read_jsonl((root / 'answers.jsonl').read_bytes())
    require(len(names) == len(set(names)) == len(answers) == 33
            and {row['name'] for row in answers} == set(names), 'missing, duplicate or foreign observed answers')
    require(all(row.get('model') == prefix and row.get('system') == 's1' and isinstance(row.get('reply'), str)
                and selection.integer(row.get('tokens'), 0, 1024) and type(row.get('stopped')) is bool for row in answers),
            'observed answer metadata differs')
    require(identity['answers_sha256'] == hashes['answers.jsonl'] and identity['server_log_sha256'] == hashes['server.log'],
            'observed outputs changed')
    return {'kind': 'audited-spec33-model-identity', 'seed': seed, 'model_sha256': model_sha,
            'answers_sha256': hashes['answers.jsonl'], 'identity_sha256': hashes['identity.json'],
            'questions_sha256': QUESTIONS_SHA, 'files_sha256': hashes,
            'source': 'Authenticated prospective observer; no new model or grading execution.'}
