"""A final reading needs the frozen qualified choice and complete private evidence."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent / 'recipes'))
import release_heldout_inputs as heldout
import release_heldout_launch as launch
import test_release_seed_selection as selection_tests


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def freeze(bundle):
    reg, report, ids = bundle['registration'], bundle['development'], bundle['development_ids']
    seeds = {int(k): v for k, v in bundle['seeds'].items()}
    hashes = selection_tests.bindings(reg, report, seeds)
    decision = heldout.choose.decide(reg, report, ids, seeds, hashes)
    bundle['evidence_sha256'] = hashes
    bundle['frozen_choice'] = {'decision_sha256': heldout.choose.sha(decision), 'decision': decision}


def invocation_fixture(root, claim, values):
    """Synthetic provenance only; no server, model, program or proof is executed."""
    bundle, panel, _, decoder, protocol, _ = values
    generation = heldout.completed(root, claim, bundle, panel, decoder, protocol)
    parent = 100; python = '/fixture/python'; cwd = claim['paths']['checkout']
    def process(pid, command, exe):
        return {'pid': pid, 'parent_pid': parent, 'start_ticks': pid, 'command': command, 'exe': exe, 'cwd': cwd}
    model_file = {'ino': 1, 'size': 4096, 'mtime_ns': 1, 'ctime_ns': 1}
    start = {'attempt': 1, 'claim_sha256': heldout.choose.sha(claim), 'model_sha256': claim['model_sha256'],
             'model_file': model_file, 'runtime_files_sha256': protocol['server_files_sha256'],
             'cache_before': {}, 'parent_pid': parent, 'python': python, 'python_exe': python,
             'server': process(101, launch.server_command(claim), claim['paths']['server_dir'] + '/llama-server'),
             'server_owned_listener': True}
    end = {'status': 'completed', 'start': start, 'client': process(102, launch.client_command(claim, python), python),
           'cache_after': {}, 'returncode': 0}
    receipt = launch.receipt(claim, protocol, generation, model_file, [end])
    write(root / 't/out/laptop-runs' / ('private-heldout-' + claim['tag']) / 'receipt.json', receipt)
    return receipt


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    reg, report, ids, seeds = selection_tests.evidence.__wrapped__()
    panel = ''.join(str(i) + '\n' for i in range(1000, 1182)).encode()
    sha = hashlib.sha256(panel).hexdigest()
    monkeypatch.setattr(heldout, 'PANEL_SHA', sha)
    reg['heldout_panel_sha256'] = sha
    bundle = {'registration': reg, 'development': report, 'development_ids': ids,
              'seeds': {str(k): v for k, v in seeds.items()}}
    freeze(bundle)
    decoder = {'checkout_revision': heldout.FIXED_PROTOCOL['execution_revision'], 'route_driver_sha256': 'b' * 64,
               'sources': {'t/spec_first.py': 'c' * 64, 't/recipes/laptop_route.sh': 'd' * 64},
               'seeds': {str(s): {'prefix': reg['seeds'][str(s)]['prefix'],
                                  'identity_prefix': f'fixture-s{s}:'} for s in (1, 2)}}
    protocol = {**deepcopy(heldout.FIXED_PROTOCOL),
                'launcher_sources_sha256': {'release_heldout_launch.py': 'f' * 64},
                'server_files_sha256': {'llama-server': 'e' * 64},
                'generation_registration_sha256': heldout.choose.sha(heldout.decoder_registration(decoder)),
                'candidate': reg['candidate'], 'training_rows_sha256': reg['training_rows_sha256'],
                'development_panel_sha256': reg['development_panel_sha256'],
                'server_revision': heldout.SERVER_REVISION, 'settings': heldout.SETTINGS,
                'heldout_panel_sha256': sha}
    paths = {'checkout': '/registered/evaluation', 'server_dir': '/registered/server',
             'model': '/registered/model.gguf', 'panel': '/registered/clean-182.txt'}
    return bundle, panel, '1' * 64, decoder, protocol, paths


def test_qualified_choice_creates_one_immutable_claim(prepared, tmp_path):
    path = tmp_path / 'claim.json'
    first = heldout.claim(path, *prepared)
    assert first['seed'] == 1 and first['logical_calls_per_problem'] == 17
    assert heldout.claim(path, *prepared) == first
    changed = list(prepared); changed[-1] = {**changed[-1], 'model': '/another/model.gguf'}
    with pytest.raises(ValueError, match='already claimed'):
        heldout.claim(path, *changed)
    assert json.loads(path.read_text()) == first


@pytest.mark.parametrize('change', ['unqualified', 'choice', 'weights', 'panel', 'decoder', 'procedure', 'floor', 'missing'])
def test_no_claim_is_created_from_unqualified_or_changed_evidence(prepared, tmp_path, change):
    bundle, panel, model, decoder, protocol, paths = deepcopy(prepared)
    if change == 'unqualified':
        for data in bundle['seeds'].values():
            data['precision'].update(safe_precision=.6, safe_kept_reference_correct=60)
        freeze(bundle)
    elif change == 'choice': bundle['frozen_choice']['decision']['selected_seed'] = 2
    elif change == 'weights': model = '2' * 64
    elif change == 'panel': panel += b'9999\n'
    elif change == 'decoder': decoder['route_driver_sha256'] = '0' * 64
    elif change == 'procedure': protocol['settings'] = {**protocol['settings'], 'CONCURRENCY': '8'}
    elif change == 'floor': protocol['required_clean'] = 0
    else: bundle.pop('development')
    path = tmp_path / 'claim.json'
    with pytest.raises(ValueError):
        heldout.claim(path, bundle, panel, model, decoder, protocol, paths)
    assert not path.exists()


@pytest.fixture
def completed(prepared, tmp_path):
    claim = heldout.claim(tmp_path / 'claim.json', *prepared)
    root = tmp_path / 'checkout'; tag = claim['tag']
    runs = root / 't/out/laptop-runs'; cache = runs / ('cache-' + tag)
    protocol = {'schema': 1, 'decoder': 'llama.cpp-Q8_0', 'model': 'dawnr-route',
                'identity': claim['identity'], 'route_args': claim['route_args'],
                'panel_sha256': claim['panel_sha256'], 'sources': claim['route_sources'],
                'driver_sha256': claim['route_driver_sha256'], 'seed_rule': heldout.SEED_RULE}
    write(cache / 'protocol.json', protocol); write(cache / 'completed.json', protocol)
    (runs / (tag + '.done')).write_text('0\n')
    directory = root / 't/out/spec-experiment' / tag; (directory / 'raw').mkdir(parents=True)
    write(directory / 'spec_first.json', {'problems': 182, 'answered': 0,
          'per_problem': {i: {'python': None, 'taken': None} for i in prepared[1].decode().split()}})
    for name in ('python.jsonl', 'kept-specs.jsonl', 'scored-specs.jsonl'): (directory / name).write_text('')
    invocation_fixture(root, claim, prepared)
    return root, claim, prepared, directory, cache


def test_complete_zero_answer_reading_is_valid_evidence(completed):
    root, claim, values, _, _ = completed
    bundle, panel, _, decoder, protocol, _ = values
    result = heldout.completed(root, claim, bundle, panel, decoder, protocol)
    assert result['problems'] == 182 and result['saved_answers'] == 0
    assert result['model_sha256'] == '1' * 64


@pytest.mark.parametrize('change', ['completion', 'raw-dir', 'foreign-raw', 'panel-row', 'python-row', 'protocol'])
def test_incomplete_or_foreign_final_reading_is_refused(completed, change):
    root, claim, values, directory, cache = completed
    if change == 'completion': write(cache / 'completed.json', {})
    elif change == 'raw-dir': (directory / 'raw').rmdir()
    elif change == 'foreign-raw': write(directory / 'raw/9999.json', {'task_id': 9999})
    elif change == 'panel-row':
        summary = heldout.read(directory / 'spec_first.json'); summary['per_problem'].pop('1000')
        write(directory / 'spec_first.json', summary)
    elif change == 'python-row': (directory / 'python.jsonl').write_text(json.dumps({'task_id': 1000}) + '\n')
    else:
        value = heldout.read(cache / 'protocol.json'); value['identity'] = 'another-model'
        write(cache / 'protocol.json', value)
    bundle, panel, _, decoder, protocol, _ = values
    with pytest.raises(ValueError):
        heldout.completed(root, claim, bundle, panel, decoder, protocol)
