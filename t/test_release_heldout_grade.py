"""Final cloud grading accepts only the complete selected private reading."""
from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

sys.path.insert(0, str(Path(__file__).parent / 'recipes'))
import release_heldout_grade as grade
from release_grading_inputs import seal_inputs, json_bytes
from test_release_heldout_inputs import prepared, completed, write  # pytest fixtures


def archive(path, files, extra=None):
    with tarfile.open(path, 'w:gz') as tar:
        for name, data in files.items():
            member = tarfile.TarInfo(name); member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
        if extra is not None:
            tar.addfile(extra)
    return path


def rebind(files):
    manifest = json.loads(files['manifest.json'])
    manifest['files'] = grade.file_hashes({k: v for k, v in files.items() if k != 'manifest.json'})
    files['manifest.json'] = json_bytes(manifest)


@pytest.fixture
def payload(completed):
    root, claim, values, _, _ = completed
    bundle, panel, _, decoder, protocol, _ = values
    files = grade.package(root, claim, bundle, panel, decoder, protocol)
    return files, protocol, claim['tag']


def test_encrypted_complete_zero_reading_prepares_exactly_once(payload, tmp_path):
    files, protocol, tag = payload
    key = tmp_path / 'key'; key.write_text('synthetic transport test secret\n')
    sealed = tmp_path / 'input.tar.gz.enc'; seal_inputs(files, sealed, key)
    plain = tmp_path / 'opened.tar.gz'
    subprocess.run(['openssl', 'enc', '-d', '-aes-256-cbc', '-pbkdf2', '-iter', '200000',
                    '-in', str(sealed), '-out', str(plain), '-pass', 'file:' + str(key)],
                   check=True, capture_output=True)
    assert grade.read_archive(plain) == files
    root = tmp_path / 'grader'
    record = grade.prepare(plain, root, protocol, tag)
    assert record['generation']['saved_answers'] == 0
    assert (root / grade.PANEL_PATH).read_bytes() == files['panel.txt']
    assert (root / grade.OUTPUT_PATH / 'inputs/selection.json').read_bytes() == files['selection.json']
    with pytest.raises(ValueError, match='overwrite'):
        grade.prepare(plain, root, protocol, tag)


def test_saved_private_answer_is_preserved_without_execution(completed, tmp_path):
    root, claim, values, source, _ = completed
    summary = json.loads((source / 'spec_first.json').read_bytes())
    summary['per_problem']['1000']['taken'] = {'index': 0}; summary['answered'] = 1
    write(source / 'spec_first.json', summary)
    answer = {'task_id': 1000, 'reply': 'PRIVATE_FIXTURE_ANSWER'}
    write(source / 'raw/1000.json', answer)
    bundle, panel, _, decoder, protocol, _ = values
    files = grade.package(root, claim, bundle, panel, decoder, protocol)
    destination = tmp_path / 'grader'
    record = grade.prepare(archive(tmp_path / 'input.tar.gz', files), destination, protocol, claim['tag'])
    assert record['generation']['saved_answers'] == 1
    assert json.loads((destination / 't/out/spec-experiment' / claim['tag'] / 'raw/1000.json').read_text()) == answer


@pytest.mark.parametrize('change', ['hash', 'choice', 'panel', 'generation', 'completion', 'foreign', 'missing', 'label', 'protocol'])
def test_changed_evidence_never_prepares_grading(payload, tmp_path, change):
    files, protocol, tag = deepcopy(payload)
    if change == 'hash': files['python.jsonl'] = b'changed'
    elif change == 'choice':
        value = json.loads(files['selection.json']); value['frozen_choice']['decision']['selected_seed'] = 2
        files['selection.json'] = json_bytes(value); rebind(files)
    elif change == 'panel': files['panel.txt'] += b'9999\n'; rebind(files)
    elif change == 'generation':
        value = json.loads(files['generation.json']); value['saved_answers'] = 1
        files['generation.json'] = json_bytes(value); rebind(files)
    elif change == 'completion': files['route.done'] = b'1\n'; rebind(files)
    elif change == 'foreign': files['training-rows.jsonl'] = b'private'; rebind(files)
    elif change == 'missing': files.pop('scored-specs.jsonl'); rebind(files)
    elif change == 'label': tag += '-another'
    else: protocol['required_clean'] = 0
    root = tmp_path / 'grader'
    with pytest.raises(ValueError):
        grade.prepare(archive(tmp_path / 'input.tar.gz', files), root, protocol, tag)
    assert not (root / 't').exists()


@pytest.mark.parametrize('kind', ['duplicate', 'parent', 'absolute', 'nested', 'symlink', 'hardlink', 'directory'])
def test_archive_cannot_write_foreign_paths(payload, tmp_path, kind):
    files, _, _ = payload
    names = {'duplicate': 'manifest.json', 'parent': '../outside', 'absolute': '/outside', 'nested': 'dir/file'}
    extra = tarfile.TarInfo(names.get(kind, 'extra'))
    if kind == 'symlink': extra.type = tarfile.SYMTYPE; extra.linkname = '/outside'
    if kind == 'hardlink': extra.type = tarfile.LNKTYPE; extra.linkname = 'manifest.json'
    if kind == 'directory': extra.type = tarfile.DIRTYPE
    with pytest.raises(ValueError):
        grade.read_archive(archive(tmp_path / 'bad.tar.gz', files, extra))
    assert not (tmp_path / 'outside').exists()


def test_archive_member_limit_stops_before_unbounded_expansion(tmp_path, monkeypatch):
    monkeypatch.setattr(grade, 'MAX_BYTES', 1000)
    path = archive(tmp_path / 'oversized.tar.gz', {'large': b'0' * 1001})
    with pytest.raises(ValueError, match='expand'):
        grade.read_archive(path)


@pytest.fixture
def finished(payload, tmp_path):
    files, protocol, tag = payload
    root = tmp_path / 'grader'
    grade.prepare(archive(tmp_path / 'inputs.tar.gz', files), root, protocol, tag)
    out = root / grade.OUTPUT_PATH / 'v5-repair-20261021/proof-results' / tag
    out.mkdir(parents=True)
    (out / 'GRADED').write_text('')
    write(out / 'levels.json', {'ids': 182, 'rows': [{'tag': tag, 'problems': 182, '>=1': 17, '>=7': 12}]})
    write(out / 'evaluator.json', {'fixture': 'synthetic, no proof or reference executed'})
    return root, tag, out


def test_final_aggregates_do_not_claim_a_content_audit_or_laptop_pass(finished):
    root, tag, _ = finished
    record = grade.finish(root, tag, 'a' * 64, 'b' * 40, '123')
    assert record['meets_numeric_floors'] is True
    assert record['independent_content_audit_pending'] is True and record['final_laptop_checks_pending'] is True
    out = root / grade.OUTPUT_PATH
    assert (out / 'COMPLETE').read_text().strip() == grade.digest(out / 'receipt.json')
    assert (out / 'spec-experiment' / tag / 'spec_first.json').is_file()


@pytest.mark.parametrize('change', ['incomplete', 'answers', 'inputs', 'panel', 'label'])
def test_incomplete_or_changed_final_grade_cannot_make_a_completion_receipt(finished, change):
    root, tag, out = finished
    if change == 'incomplete': (out / 'GRADED').unlink()
    elif change == 'answers': (root / 't/out/spec-experiment' / tag / 'spec_first.json').write_text('changed')
    elif change == 'inputs': (root / grade.OUTPUT_PATH / 'inputs/panel.txt').write_text('changed')
    elif change == 'panel':
        value = json.loads((out / 'levels.json').read_text()); value['ids'] = 95
        write(out / 'levels.json', value)
    else: tag += '-another'
    with pytest.raises(ValueError): grade.finish(root, tag, 'a' * 64, 'b' * 40, '123')
    assert not (root / grade.OUTPUT_PATH / 'COMPLETE').exists()
