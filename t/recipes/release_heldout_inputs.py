"""Validate one qualified seed and its private held-out generation handoff.

Artifact audits precede this module. It recomputes the decision and binds a
single claim; it never starts a model, a prover, a cloud job or publication.
Sources: release_seed_selection.py; v6_server_route.py; release_decode_arms.py.
https://github.com/trestoncuzzort/dawnr/blob/main/t/recipes/v6_server_route.py
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

import release_seed_selection as choose
from release_grading_inputs import require, check_summary, digest, read_jsonl

PANEL_SHA = '837e2ac5a70980d2ac7b35a97af258997d153e7c755cd166555d232c371ad51f'
SERVER_REVISION = 'f1cee9941b0e843ea260bf8dd9a090fbd9711b6a'
SETTINGS = {'PARALLEL': '4', 'CONCURRENCY': '4', 'BATCH': '16',
            'SLOT_CTX': '4096', 'PYTHON_ATTEMPTS': '3', 'POOL': 'v5', 'SEED': ''}
SEED_RULE = 'sha256(canonical_json([stage, messages]))[:8] & 0x7fffffff'
FIXED_PROTOCOL = {'schema': 1, 'kind': 'Registered one-selected-seed private final reading',
                  'execution_revision': 'b3e9b0d9d71f684d9c68c9334160827fcc501b66',
                  'server_revision': SERVER_REVISION, 'settings': SETTINGS,
                  'model_alias': 'dawnr-route', 'python_attempts': 3, 'specification_samples': 5,
                  'kept_specifications': 3, 'implementation_samples_per_specification': 3,
                  'max_new_tokens': 1024, 'seed_offset': 0, 'logical_calls_per_problem': 17,
                  'required_clean': 17, 'required_all_seven': 12, 'heldout_model_calls_started': False}


def read(path):
    return json.loads(Path(path).read_text())


def decoder_registration(value):
    return {key: value[key] for key in ('checkout_revision', 'sources', 'route_driver_sha256', 'seeds')}


def qualified(bundle):
    require(set(bundle) == {'registration', 'development', 'development_ids', 'seeds', 'evidence_sha256', 'frozen_choice'},
            'selection bundle is incomplete or has foreign fields')
    require(set(bundle['seeds']) == {'1', '2'}, 'both complete seeds are required')
    decision = choose.decide(bundle['registration'], bundle['development'], bundle['development_ids'],
                             {int(key): value for key, value in bundle['seeds'].items()}, bundle['evidence_sha256'])
    require(decision['status'] == 'eligible-for-heldout' and decision['selected_seed'] in (1, 2),
            'the candidate has not qualified for a final reading')
    frozen = {'decision_sha256': choose.sha(decision), 'decision': decision}
    require(choose.canonical(bundle['frozen_choice']) == choose.canonical(frozen),
            'selection differs from the immutable choice')
    require(decision['heldout_panel_sha256'] == PANEL_SHA, 'another final panel was selected')
    return decision


def panel_ids(data):
    require(hashlib.sha256(data).hexdigest() == PANEL_SHA, 'held-out panel bytes changed')
    ids = data.decode().split()
    require(len(ids) == len(set(ids)) == 182 and all(str(int(i)) == i and int(i) >= 0 for i in ids),
            'the final panel must contain exactly 182 distinct problem IDs')
    return ids


def request(bundle, panel, actual_model_sha, decoder, protocol, paths):
    decision = qualified(bundle)
    panel_ids(panel)
    seed = decision['selected_seed']; registration = bundle['registration']
    require(actual_model_sha == decision['selected_model_sha256'], 'model bytes differ from the selected export')
    choose.check_digest(actual_model_sha)
    require(all(protocol.get(key) == value for key, value in FIXED_PROTOCOL.items())
            and protocol['generation_registration_sha256'] == choose.sha(decoder_registration(decoder))
            and decoder['checkout_revision'] == protocol['execution_revision']
            and protocol['heldout_panel_sha256'] == PANEL_SHA
            and protocol['candidate'] == registration['candidate']
            and protocol['training_rows_sha256'] == registration['training_rows_sha256']
            and protocol['development_panel_sha256'] == registration['development_panel_sha256'],
            'unregistered final decoder procedure')
    require(decoder['seeds'][str(seed)]['prefix'] == registration['seeds'][str(seed)]['prefix'],
            'decoder belongs to another seed')
    require(isinstance(protocol.get('launcher_sources_sha256'), dict)
            and 'release_heldout_launch.py' in protocol['launcher_sources_sha256']
            and isinstance(protocol.get('server_files_sha256'), dict)
            and 'llama-server' in protocol['server_files_sha256'], 'missing registered invocation sources')
    for value in list(protocol['launcher_sources_sha256'].values()) + list(protocol['server_files_sha256'].values()):
        choose.check_digest(value)
    require(set(paths) == {'checkout', 'server_dir', 'model', 'panel'}
            and all(isinstance(value, str) and PurePosixPath(value).is_absolute()
                    and '..' not in PurePosixPath(value).parts for value in paths.values()), 'invalid execution paths')
    prefix = registration['seeds'][str(seed)]['prefix']
    tag = prefix + '-heldout'
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', tag), 'invalid final reading tag')
    model_identity = decoder['seeds'][str(seed)]['identity_prefix'] + actual_model_sha + ':llama-' + SERVER_REVISION
    route_args = ['--tag', tag, '--ids-file', paths['panel'], '--pool', 'v5',
                  '--python', '3', '--spec-samples', '4', '--per-problem', '3', '--samples', '2',
                  '--max-new', '1024', '--batch', '16', '--seed-offset', '0']
    return {'schema': 1, 'kind': 'one-selected-private-heldout-reading', 'candidate': registration['candidate'],
            'seed': seed, 'tag': tag, 'model_sha256': actual_model_sha, 'identity': model_identity,
            'panel_sha256': PANEL_SHA, 'panel_problems': 182, 'selection_bundle_sha256': choose.sha(bundle),
            'choice_sha256': choose.sha(bundle['frozen_choice']), 'procedure_sha256': choose.sha(protocol),
            'generation_registration_sha256': protocol['generation_registration_sha256'],
            'settings': dict(SETTINGS), 'paths': dict(paths), 'route_args': route_args,
            'route_sources': {k: v for k, v in decoder['sources'].items() if not k.startswith('t/recipes/')},
            'route_driver_sha256': decoder['route_driver_sha256'], 'logical_calls_per_problem': 17}


def claim(path, bundle, panel, actual_model_sha, decoder, protocol, paths):
    value = request(bundle, panel, actual_model_sha, decoder, protocol, paths)
    path = Path(path)
    if path.exists():
        require(path.is_file() and not path.is_symlink(), 'invalid existing generation claim')
        require(choose.canonical(read(path)) == choose.canonical(value),
                'a final reading is already claimed with different evidence or procedure')
        return value
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
    return value


def completed(checkout, claim_record, bundle, panel, decoder, protocol):
    expected = request(bundle, panel, claim_record['model_sha256'], decoder, protocol, claim_record['paths'])
    require(choose.canonical(claim_record) == choose.canonical(expected), 'final generation claim differs')
    checkout = Path(checkout); tag = claim_record['tag']
    runs = checkout / 't/out/laptop-runs'; cache = runs / ('cache-' + tag)
    require((runs / (tag + '.done')).read_text().strip() == '0', 'final generation did not complete')
    recorded = read(cache / 'protocol.json')
    expected_protocol = {'schema': 1, 'decoder': 'llama.cpp-Q8_0', 'model': 'dawnr-route',
                         'identity': claim_record['identity'], 'route_args': claim_record['route_args'],
                         'panel_sha256': PANEL_SHA, 'sources': claim_record['route_sources'],
                         'driver_sha256': claim_record['route_driver_sha256'], 'seed_rule': SEED_RULE}
    require(recorded == expected_protocol and read(cache / 'completed.json') == expected_protocol,
            'final decoder protocol or completion differs')
    directory = checkout / 't/out/spec-experiment' / tag
    ids = set(panel_ids(panel))
    summary, taken = check_summary((directory / 'spec_first.json').read_bytes(), ids)
    require(type(summary['problems']) is int and type(summary['answered']) is int, 'invalid final answer count')
    require((directory / 'raw').is_dir() and not (directory / 'raw').is_symlink(), 'missing raw-answer directory')
    raw = {p.name for p in (directory / 'raw').glob('*') if p.name != '.generate.lock'}
    require(raw == {tid + '.json' for tid in taken}
            and all((directory / 'raw' / name).is_file() and not (directory / 'raw' / name).is_symlink() for name in raw),
            'final saved answers differ from the complete panel')
    for name in raw:
        require(str(read(directory / 'raw' / name)['task_id']) == Path(name).stem, 'final raw answer identity differs')
    files = {'spec_first.json': digest(directory / 'spec_first.json')}
    files.update({'raw/' + name: digest(directory / 'raw' / name) for name in sorted(raw)})
    for name in ('python.jsonl', 'kept-specs.jsonl', 'scored-specs.jsonl'):
        path = directory / name
        require(path.is_file() and not path.is_symlink(), 'final generation evidence is missing or linked')
        require(all(str(row['task_id']) in ids for row in read_jsonl(path.read_bytes())), 'foreign final generation row')
        files[name] = digest(path)
    python_ids = [str(row['task_id']) for row in read_jsonl((directory / 'python.jsonl').read_bytes())]
    passing = {tid for tid, state in summary['per_problem'].items() if state.get('python') is not None}
    require(len(python_ids) == len(set(python_ids)) and set(python_ids) == passing,
            'final Python evidence differs from the generation summary')
    return {'kind': 'complete-private-heldout-generation', 'tag': tag, 'seed': claim_record['seed'],
            'claim_sha256': choose.sha(claim_record), 'model_sha256': claim_record['model_sha256'],
            'panel_sha256': PANEL_SHA, 'problems': 182, 'saved_answers': len(taken),
            'protocol_sha256': digest(cache / 'protocol.json'), 'files_sha256': files}
