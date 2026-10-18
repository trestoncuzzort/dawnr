"""The first CLI steps work before configuration or expensive model startup."""
import os
from pathlib import Path
import shlex
import subprocess

import pytest

from locallm.install_runtime import check_manifest, configure

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('args', [[], ['--help'], ['help'], ['help', 'ask'],
                                   ['do', '--help'], ['ask', 'example', '--help'],
                                   ['serve', '--help']])
def test_help_never_loads_configuration_or_starts_a_model(tmp_path, args):
    data = tmp_path / 'data'
    data.mkdir()
    marker = tmp_path / 'configuration-was-read'
    (data / 'env').write_text('touch ' + shlex.quote(str(marker)) + '\nexit 99\n')
    result = subprocess.run(['bash', str(ROOT/'bin/dawnr'), *args], input='', text=True,
                            capture_output=True, env={**os.environ, 'DAWNR_HOME': str(data)}, timeout=5)
    assert result.returncode == 0, result.stderr
    assert 'Usage:' in result.stdout
    assert not marker.exists() and not (data/'run').exists()


def test_unknown_command_and_missing_setup_have_actionable_errors(tmp_path):
    env = {**os.environ, 'DAWNR_HOME': str(tmp_path/'missing')}
    bad = subprocess.run(['bash', str(ROOT/'bin/dawnr'), 'dotor'], env=env, capture_output=True, text=True)
    assert bad.returncode == 2 and 'unknown command: dotor' in bad.stderr and '--help' in bad.stderr
    missing = subprocess.run(['bash', str(ROOT/'bin/dawnr'), 'doctor'], env=env, capture_output=True, text=True)
    assert missing.returncode == 1 and './install.sh' in missing.stderr


def test_custom_storage_and_quoted_paths_survive_install_and_reinstall(tmp_path):
    repo = tmp_path / "Dawnr's checkout"
    data = tmp_path / 'model data $literal'
    bins = tmp_path / 'local bin'
    (repo/'bin').mkdir(parents=True)
    source = repo/'bin/dawnr'
    source.write_text('#!/usr/bin/env bash\n. "$DAWNR_HOME/env"\nprintf "%s\\n" "$DAWNR_REPO" "$STUDENT_GGUF" "$DAWNR_THREADS" "$1"\n')
    source.chmod(0o755)
    before = source.read_bytes()
    bins.mkdir()
    (bins/'dawnr').symlink_to(source)  # the installer's old layout
    data.mkdir()
    (data/'env').write_text('DAWNR_THREADS=3\nDAWNR_HOME=stale\n')
    model = str(data/"weights' $(touch should-not-exist).gguf")
    configure(repo, data, bins, {'STUDENT_GGUF': model, 'DAWNR_BUILD': 'cpu'})
    configure(repo, data, bins, {'STUDENT_GGUF': model, 'DAWNR_BUILD': 'cpu'})
    env = {k:v for k,v in os.environ.items() if k != 'DAWNR_HOME'}
    result = subprocess.run([str(bins/'dawnr'), 'a task with spaces'], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [str(repo), model, '3', 'a task with spaces']
    assert source.read_bytes() == before and not (bins/'dawnr').is_symlink()
    assert not (tmp_path/'should-not-exist').exists()
    assert (data/'env').stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('option', ['--home', '--student', '--build'])
def test_installer_missing_option_value_is_reported_before_downloads(option):
    result = subprocess.run(['bash', str(ROOT/'install.sh'), option], capture_output=True, text=True, timeout=5)
    assert result.returncode == 2 and option+' needs a value' in result.stderr
    assert 'unbound variable' not in result.stderr


@pytest.mark.parametrize('content', ['', 'invalid model.gguf\n',
    'a'*64+'  ../outside.gguf\n', 'a'*64+'  a.gguf\n'+'b'*64+'  a.gguf\n'])
def test_download_manifest_cannot_escape_storage_or_silently_select_conflicting_files(tmp_path, content):
    path = tmp_path/'manifest'
    path.write_text(content)
    with pytest.raises(ValueError):
        check_manifest(path)


def test_versioned_rolling_artifacts_are_accepted(tmp_path):
    path = tmp_path/'manifest'
    path.write_text('a'*64+'  dawnr-v6-00001-of-00002.gguf\n'+'b'*64+'  dawnr-v6-00002-of-00002.gguf\n')
    check_manifest(path)
