"""Prepare sealed final-reading inputs for the existing frozen cloud grader.

This is transport and evidence accounting, not a model selector or proof runner.
It reuses ceiling.yml's flat encrypted inputs and spec33.yml's sealed outputs.
Sources: release_heldout_inputs.py, release_grading_inputs.py, v6-grade.sh;
https://github.com/trestoncuzzort/dawnr/blob/main/.github/workflows/spec33.yml
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile
import tempfile

import release_heldout_inputs as heldout
import release_heldout_launch as launch
from release_grading_inputs import MAX_BYTES, digest, json_bytes, require, safe_name

GRADER = '1e033b50c2c53fb3d40932d9561e1a8eefe9aa7d'
PANEL_PATH = 't/out/release-6.0/clean-182.txt'
OUTPUT_PATH = 'out/heldout-grade'
GENERATION_FILES = ('spec_first.json', 'python.jsonl', 'kept-specs.jsonl', 'scored-specs.jsonl')
CONTROL_FILES = ('selection.json', 'claim.json', 'decoder.json', 'protocol.json', 'generation.json',
                 'invocation.json', 'panel.txt', 'route-protocol.json', 'route-completed.json', 'route.done')


def file_hashes(files):
    return {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}


def package(checkout, claim, bundle, panel, decoder, protocol):
    """Flat files for the existing seal_inputs function; no upload is performed."""
    generation = heldout.completed(checkout, claim, bundle, panel, decoder, protocol)
    checkout = Path(checkout); tag = claim['tag']
    source = checkout / 't/out/spec-experiment' / tag
    cache = checkout / 't/out/laptop-runs' / ('cache-' + tag)
    files = {name: json_bytes(value) for name, value in (
        ('selection.json', bundle), ('claim.json', claim), ('decoder.json', decoder),
        ('protocol.json', protocol), ('generation.json', generation))}
    files['panel.txt'] = panel
    files.update({name: (source / name).read_bytes() for name in GENERATION_FILES})
    files.update({'raw-' + Path(name).name: (source / name).read_bytes()
                  for name in generation['files_sha256'] if name.startswith('raw/')})
    files.update({'route-' + name: (cache / name).read_bytes() for name in ('protocol.json', 'completed.json')})
    files['route.done'] = (checkout / 't/out/laptop-runs' / (tag + '.done')).read_bytes()
    files['invocation.json'] = (checkout / 't/out/laptop-runs' / ('private-heldout-' + tag) / 'receipt.json').read_bytes()
    files['manifest.json'] = json_bytes({'schema': 1, 'tag': tag, 'files': file_hashes(files)})
    validate(files, protocol, tag)
    return files


def validate(files, expected_protocol, label):
    """Reconstruct only in a temporary directory, then check the original handoff."""
    required = set(CONTROL_FILES + GENERATION_FILES + ('manifest.json',))
    require(required <= set(files) and len(files) <= len(required) + 182,
            'incomplete or oversized final input bundle')
    require(all(name in required or re.fullmatch(r'raw-(0|[1-9][0-9]*)\.json', name) for name in files),
            'foreign final input file')
    require(sum(map(len, files.values())) <= MAX_BYTES, 'final inputs exceed the size limit')
    manifest = json.loads(files['manifest.json'])
    require(manifest == {'schema': 1, 'tag': label,
                         'files': file_hashes({k: v for k, v in files.items() if k != 'manifest.json'})},
            'private input manifest differs')
    bundle, claim, decoder, protocol, generation = [json.loads(files[name]) for name in (
        'selection.json', 'claim.json', 'decoder.json', 'protocol.json', 'generation.json')]
    require(heldout.choose.canonical(protocol) == heldout.choose.canonical(expected_protocol),
            'private inputs use an unregistered protocol')
    require(isinstance(label, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', label)
            and claim['tag'] == label, 'private input label differs')
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / 't/out/spec-experiment' / label
        (source / 'raw').mkdir(parents=True)
        for name in GENERATION_FILES:
            (source / name).write_bytes(files[name])
        for name in files:
            if name.startswith('raw-'):
                (source / 'raw' / name[4:]).write_bytes(files[name])
        cache = root / 't/out/laptop-runs' / ('cache-' + label); cache.mkdir(parents=True)
        for name in ('protocol.json', 'completed.json'):
            (cache / name).write_bytes(files['route-' + name])
        (cache.parent / (label + '.done')).write_bytes(files['route.done'])
        actual = heldout.completed(root, claim, bundle, files['panel.txt'], decoder, protocol)
    require(actual == generation, 'completed generation differs from its receipt')
    launch.validate_invocation(json.loads(files['invocation.json']), claim, protocol, generation)
    return {'tag': label, 'seed': claim['seed'], 'model_sha256': claim['model_sha256'],
            'panel_sha256': heldout.PANEL_SHA, 'generation': generation,
            'input_files_sha256': file_hashes(files), 'independent_content_audit_pending': True}


def read_archive(path):
    """Read bounded regular flat members without extracting archive paths."""
    path = Path(path)
    require(path.stat().st_size <= MAX_BYTES, 'private archive exceeds the size limit')
    files = {}; size = 0
    with tarfile.open(path, 'r:gz') as archive:
        for entry in archive:
            require(entry.isfile() and len(files) < 220 and entry.name not in files,
                    'linked, duplicate or excessive private input member')
            require(len(safe_name(entry.name).parts) == 1, 'private inputs must be flat')
            size += entry.size
            require(0 <= entry.size and size <= MAX_BYTES, 'private inputs expand beyond the size limit')
            files[entry.name] = archive.extractfile(entry).read()
    return files


def prepare(archive, checkout, expected_protocol, label):
    files = read_archive(archive)
    record = validate(files, expected_protocol, label)
    root = Path(checkout)
    source = root / 't/out/spec-experiment' / label
    require(not source.exists() and not source.is_symlink(), 'refusing to overwrite existing final answers')
    panel = root / PANEL_PATH
    require(not panel.is_symlink() and (not panel.exists() or panel.read_bytes() == files['panel.txt']),
            'existing final panel differs')
    output = root / OUTPUT_PATH
    require(not (output / 'input-validation.json').exists(), 'final grade inputs were already prepared')
    (source / 'raw').mkdir(parents=True)
    for name in GENERATION_FILES:
        (source / name).write_bytes(files[name])
    for name in files:
        if name.startswith('raw-'):
            (source / 'raw' / name[4:]).write_bytes(files[name])
    panel.parent.mkdir(parents=True, exist_ok=True); panel.write_bytes(files['panel.txt'])
    saved = output / 'inputs'; saved.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        (saved / name).write_bytes(data)
    (output / 'input-validation.json').write_bytes(json_bytes(record))
    return record


def finish(checkout, label, asset_sha, workflow_revision, run_id):
    """Capture the full private evidence; aggregates still need independent audit."""
    root = Path(checkout); output = root / OUTPUT_PATH
    inputs = heldout.read(output / 'input-validation.json')
    require(inputs['tag'] == label, 'final grade label differs')
    for name, sha in inputs['input_files_sha256'].items():
        require(digest(output / 'inputs' / name) == sha, 'saved final inputs changed')
    source = root / 't/out/spec-experiment' / label
    for name, sha in inputs['generation']['files_sha256'].items():
        require(digest(source / name) == sha, 'grading changed an original generated answer')
    graded = output / 'v5-repair-20261021/proof-results' / label
    require((graded / 'GRADED').is_file(), 'the final grade did not finish')
    levels = heldout.read(graded / 'levels.json')
    require(levels['ids'] == 182 and len(levels['rows']) == 1
            and levels['rows'][0]['tag'] == label and levels['rows'][0]['problems'] == 182,
            'final grade covers another panel')
    row = levels['rows'][0]
    clean, all_seven = row['>=1'], row['>=7']
    require(type(clean) is int and type(all_seven) is int and 0 <= all_seven <= clean <= 182,
            'invalid final coverage counts')
    heldout.choose.check_digest(asset_sha)
    require(re.fullmatch(r'[0-9a-f]{40}', workflow_revision) and str(run_id).isdigit(), 'invalid workflow identity')
    destination = output / 'spec-experiment' / label
    require(not any(p.is_symlink() for p in source.rglob('*')), 'linked final grading evidence')
    shutil.copytree(source, destination)
    record = {'kind': 'private-final-grade', 'tag': label, 'seed': inputs['seed'],
              'model_sha256': inputs['model_sha256'], 'panel_sha256': inputs['panel_sha256'],
              'grader_revision': GRADER, 'workflow_revision': workflow_revision, 'run_id': str(run_id),
              'input_asset_sha256': asset_sha, 'input_validation_sha256': digest(output / 'input-validation.json'),
              'levels_sha256': digest(graded / 'levels.json'), 'evaluator_sha256': digest(graded / 'evaluator.json'),
              'clean': clean, 'all_seven': all_seven, 'required_clean': 17, 'required_all_seven': 12,
              'meets_numeric_floors': clean >= 17 and all_seven >= 12,
              'independent_content_audit_pending': True, 'final_laptop_checks_pending': True}
    (output / 'receipt.json').write_bytes(json_bytes(record))
    (output / 'COMPLETE').write_text(digest(output / 'receipt.json') + '\n')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    opening = sub.add_parser('prepare')
    opening.add_argument('--archive', type=Path, required=True)
    opening.add_argument('--protocol', type=Path, required=True)
    closing = sub.add_parser('finish')
    closing.add_argument('--asset-sha256', required=True)
    closing.add_argument('--workflow-revision', required=True)
    closing.add_argument('--run-id', required=True)
    for command in (opening, closing):
        command.add_argument('--checkout', type=Path, required=True)
        command.add_argument('--label', required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.archive, args.checkout, heldout.read(args.protocol), args.label)
    else:
        record = finish(args.checkout, args.label, args.asset_sha256, args.workflow_revision, args.run_id)
        print(json.dumps({key: record[key] for key in ('clean', 'all_seven', 'meets_numeric_floors',
                                                      'independent_content_audit_pending', 'final_laptop_checks_pending')}))


if __name__ == '__main__':
    main()
