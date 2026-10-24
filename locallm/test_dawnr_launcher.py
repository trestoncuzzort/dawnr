"""The first CLI steps work before configuration or expensive model startup."""
import os
from pathlib import Path
import shlex
import subprocess

import pytest

from locallm.install_runtime import check_manifest, configure, manifest_entries

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


@pytest.mark.parametrize('arg', ['version', '--version'])
def test_version_prints_the_checkout_release_without_setup(tmp_path, arg):
    env = {**os.environ, 'DAWNR_HOME': str(tmp_path/'missing')}
    result = subprocess.run(['bash', str(ROOT/'bin/dawnr'), arg], env=env, capture_output=True, text=True, timeout=5)
    expected = (ROOT/'VERSION').read_text().strip()
    assert result.returncode == 0, result.stderr
    assert result.stdout == f'dawnr {expected}\n'
    assert not (tmp_path/'missing').exists()


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


@pytest.mark.parametrize('option', ['--home', '--model', '--student', '--release', '--build'])
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


def test_manifest_may_point_at_files_an_earlier_release_published(tmp_path):
    kept = 'https://github.com/trestoncuzzort/dawnr/releases/download/v6.0.0/dawnr-6.0.0-00001-of-00002.gguf'
    path = tmp_path/'manifest'
    path.write_text('A'*64+'  '+kept+'\n'+'b'*64+'  dawnr-6.1.0-00002-of-00002.gguf\n')
    assert manifest_entries(path, 'https://example.invalid/release/') == [
        ('a'*64, kept, 'dawnr-6.0.0-00001-of-00002.gguf'),
        ('b'*64, 'https://example.invalid/release/dawnr-6.1.0-00002-of-00002.gguf', 'dawnr-6.1.0-00002-of-00002.gguf')]


@pytest.mark.parametrize('ref', ['https://elsewhere.example/releases/download/v1/model.gguf',
                                 'https://github.com/someone/else/releases/download/v1/model.gguf',
                                 'https://github.com/trestoncuzzort/dawnr/releases/download/v1/../model.gguf',
                                 'https://github.com/trestoncuzzort/dawnr/releases/download/v1/model.bin'])
def test_manifest_refuses_files_from_anywhere_else(tmp_path, ref):
    path = tmp_path/'manifest'
    path.write_text('a'*64+'  '+ref+'\n')
    with pytest.raises(ValueError):
        check_manifest(path)


def test_manifest_refuses_two_entries_for_one_local_file(tmp_path):
    path = tmp_path/'manifest'
    path.write_text('a'*64+'  https://github.com/trestoncuzzort/dawnr/releases/download/v6.0.0/m.gguf\n'
                    +'b'*64+'  m.gguf\n')
    with pytest.raises(ValueError):
        check_manifest(path)


def test_installer_refuses_a_release_tag_that_is_not_a_plain_name():
    result = subprocess.run(['bash', str(ROOT/'install.sh'), '--release', '../elsewhere'],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 2 and '--release takes a tag' in result.stderr


def test_the_persons_tool_folders_join_a_bare_path(tmp_path):
    # An editor's MCP client or a service starts dawnr with a PATH like /usr/local/bin:/usr/bin, where Lean and the Rust
    # toolchain Verus runs are not; two of the seven provers then read as undecided (2026-10-24). The launcher adds
    # the person's own tool folders that exist. Here `dawnr version` can only print through the stand-in `cat` that
    # lives in ~/.cargo/bin, which a bare PATH does not contain.
    home = tmp_path / 'home'
    tools = home / '.cargo' / 'bin'
    tools.mkdir(parents=True)
    for name, body in (('cat', 'echo 9.9.9-from-the-tool-folder'), ('dirname', 'exec /usr/bin/dirname "$@"'),
                       ('readlink', 'exec /usr/bin/readlink "$@"')):
        (tools / name).write_text('#!/bin/sh\n' + body + '\n')
        (tools / name).chmod(0o755)
    result = subprocess.run(['/bin/bash', str(ROOT/'bin/dawnr'), 'version'], capture_output=True, text=True, timeout=5,
                            env={'HOME': str(home), 'PATH': str(tmp_path / 'nothing-here')})
    assert result.stdout == 'dawnr 9.9.9-from-the-tool-folder\n', result.stderr

