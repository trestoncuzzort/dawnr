"""Authenticate explicit installation inputs and exercise their loopback handoff."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import install_candidate_package as candidate


@pytest.fixture
def released(tmp_path, monkeypatch):
    blobs = {'dawnr-6.1.0-00001-of-00002.gguf': b'first synthetic shard',
             'dawnr-6.1.0-00002-of-00002.gguf': b'second synthetic shard'}
    manifest = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n' for name, data in blobs.items()).encode()
    blobs['dawnr.sha256'] = manifest
    assets = [{'id': i, 'name': name, 'size': len(data), 'state': 'uploaded',
               'digest': 'sha256:' + hashlib.sha256(data).hexdigest()}
              for i, (name, data) in enumerate(blobs.items(), 1)]
    release = {'id': 123, 'tag_name': 'v6.1.0', 'draft': True, 'assets': assets}
    calls = []

    def gh(args, **kwargs):
        calls.append(args)
        if args[-1].endswith('/releases/123'):
            return SimpleNamespace(stdout=json.dumps(release), returncode=0)
        assert args[:4] == ['gh', 'api', '-H', 'Accept: application/octet-stream']
        item = next(a for a in assets if a['id'] == int(args[-1].rsplit('/', 1)[1]))
        kwargs['stdout'].write(blobs[item['name']])
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(candidate.subprocess, 'run', gh)
    return release, blobs, hashlib.sha256(manifest).hexdigest(), tmp_path / 'downloads', calls


def test_explicit_package_is_checked_file_by_file(released):
    release, blobs, sha, directory, calls = released
    receipt = candidate.fetch(123, sha, directory)
    assert receipt['release_id'] == 123 and receipt['release_was_draft'] is True
    assert set(receipt['files']) == set(blobs) and receipt['first_shard'] == next(iter(blobs))
    assert all((directory / name).read_bytes() == data for name, data in blobs.items())
    assert len(calls) == 4
    with pytest.raises(FileExistsError):
        candidate.fetch(123, sha, directory)
    assert len(calls) == 4


@pytest.mark.parametrize('change', ['wrong_release', 'wrong_tag', 'missing_manifest', 'duplicate_manifest',
                                  'unfinished', 'metadata_digest', 'manifest_bytes', 'shard_bytes', 'size', 'name'])
def test_changed_release_inputs_fail_before_installation(released, change):
    release, blobs, sha, directory, calls = released
    if change == 'wrong_release': release['id'] = 999
    elif change == 'wrong_tag': release['tag_name'] = 'rolling'
    elif change == 'missing_manifest': release['assets'].pop()
    elif change == 'duplicate_manifest': release['assets'].append(deepcopy(release['assets'][-1]))
    elif change == 'unfinished': release['assets'][-1]['state'] = 'new'
    elif change == 'metadata_digest': release['assets'][-1]['digest'] = 'sha256:' + 'f' * 64
    elif change == 'manifest_bytes': blobs['dawnr.sha256'] = b'changed manifest'
    elif change == 'shard_bytes': blobs[next(iter(blobs))] = b'changed shard'
    elif change == 'size': release['assets'][0]['size'] += 1
    else: release['assets'][0]['name'] = 'another-model.gguf'
    with pytest.raises(ValueError):
        candidate.fetch(123, sha, directory)
    assert all(command[:2] == ['gh', 'api'] for command in calls)


@pytest.mark.parametrize('release_id,sha', [(0, 'a' * 64), (-1, 'a' * 64), (True, 'a' * 64),
                                         (123, 'no checksum'), (123, 'A' * 64)])
def test_missing_identity_is_refused_before_api_access(released, release_id, sha):
    _, _, _, directory, calls = released
    with pytest.raises(ValueError):
        candidate.fetch(release_id, sha, directory)
    assert not calls


@pytest.mark.parametrize('corrupt', [False, True])
def test_installer_reads_only_checked_files_and_installed_bytes_are_verified(released, tmp_path, monkeypatch, corrupt):
    _, blobs, sha, directory, _ = released
    receipt = candidate.fetch(123, sha, directory)
    home = tmp_path / 'home'
    monkeypatch.setenv('GH_TOKEN', 'synthetic-test-secret')
    monkeypatch.setenv('GITHUB_TOKEN', 'another-synthetic-test-secret')

    def installer(args, **kwargs):
        assert args[:2] == ['bash', str(candidate.REPO / 'install.sh')]
        assert args[2:4] == ['--home', str(home)] and args[4] == '--model'
        assert 'GH_TOKEN' not in kwargs['env'] and 'GITHUB_TOKEN' not in kwargs['env']
        base = args[5]
        assert base.startswith('http://127.0.0.1:')
        for forbidden in ('/', '/outside.txt', '/../VERSION', '/%2e%2e/VERSION'):
            with pytest.raises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(base + forbidden)
            assert error.value.code == 404
        models = home / 'models'
        models.mkdir(parents=True)
        for name, expected in blobs.items():
            with urllib.request.urlopen(base + '/' + name) as response:
                data = response.read()
            assert data == expected
            (models / name).write_bytes(data)
        if corrupt:
            (models / receipt['first_shard']).write_bytes(b'wrong installed file')
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(candidate.subprocess, 'run', installer)
    monkeypatch.setattr(candidate.subprocess, 'check_output', lambda *args, **kwargs: 'a' * 40 + '\n')
    if corrupt:
        with pytest.raises(ValueError, match='installed package differs'):
            candidate.install(directory, receipt, home)
    else:
        result = candidate.install(directory, receipt, home)
        assert result['installed_model_files_verified'] is True
        assert result['application_revision'] == 'a' * 40
