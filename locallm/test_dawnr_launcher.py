"""The first CLI steps work before configuration or expensive model startup."""
import os
from pathlib import Path
import shlex
import subprocess
import sys

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


# `dawnr forget` as the person runs it. Every folder it is told about (HOME, XDG_STATE_HOME, DAWNR_HOME) is the test's
# own, and no process id is written, so the model servers it stops first are none.

def forget_place(tmp_path):
    """(home, data folder, environment, the default state folder) for one run of the launcher."""
    home, data = tmp_path / 'home', tmp_path / 'data'
    home.mkdir()
    data.mkdir()
    (data / 'env').write_text('')                      # the launcher reads its settings before any command
    env = {**os.environ, 'HOME': str(home), 'XDG_STATE_HOME': str(tmp_path / 'state home'), 'DAWNR_HOME': str(data)}
    default = (home / 'Library' / 'Application Support' if sys.platform == 'darwin' else tmp_path / 'state home')
    return home, data, env, default / 'dawnr-agent'


def forget(env, *args):
    return subprocess.run(['bash', str(ROOT/'bin/dawnr'), 'forget', *args], env=env, capture_output=True, text=True,
                          timeout=60)


def assistant_session(tmp_path, env, *options):
    """One session of the assistant as `dawnr do` starts it (locallm/dawnr_cli.py), against a model server that is not
    there: it makes its state folder, and stops at its first call to the model."""
    work = tmp_path / 'work'
    work.mkdir(exist_ok=True)
    got = subprocess.run([sys.executable, str(ROOT/'locallm/dawnr_cli.py'), '--host', '127.0.0.1:9', '--cwd', str(work),
                          *options, 'list the files'], cwd=work, env=env, capture_output=True, text=True, timeout=120)
    assert got.returncode == 0, got.stderr


def journal_a_change(state):
    """What a session that changed a file adds to its state folder, written by the journal itself
    (locallm/dawnr_agent/journal.py): the replaced bytes under backups/ and a line in journal.jsonl."""
    code = ('import sys; sys.path[:0] = [sys.argv[1], sys.argv[2]]; from dawnr_agent.journal import Journal\n'
            'j = Journal(sys.argv[3]); old = j.keep(b"the bytes the change replaced\\n")\n'
            'j.record(action="write", root="here", path="notes.txt", before=old, after=None)')
    subprocess.run([sys.executable, '-c', code, str(ROOT/'locallm'), str(ROOT/'t'), str(state)], check=True, timeout=60)


def snapshot(top):
    """Every name under `top`, links not followed: a file's bytes, a link's target, a folder's existence."""
    out = {}
    for at, dirs, files in os.walk(top):
        for name in dirs + files:
            path = os.path.join(at, name)
            rel = os.path.relpath(path, top)
            if os.path.islink(path):
                out[rel] = 'link to ' + os.readlink(path)
            elif os.path.isdir(path):
                out[rel] = 'folder'
            else:
                out[rel] = Path(path).read_bytes()
    return out


def test_a_folder_given_with_state_is_erased_by_forget(tmp_path):
    _home, data, env, _default = forget_place(tmp_path)
    given = tmp_path / 'my state'
    assistant_session(tmp_path, env, '--state', '../my state')       # relative to the folder it is started in
    journal_a_change(given)
    assert (given / 'journal.jsonl').is_file() and (given / 'backups').is_dir()
    got = forget(env)
    assert got.returncode == 0, got.stderr
    assert f'erased {given}' in got.stdout.splitlines(), got.stdout
    assert not os.path.lexists(given)
    assert not os.path.lexists(data / 'state-folders')               # and the record of it


@pytest.mark.parametrize('args', [[], ['--all']])
def test_forget_leaves_nothing_of_what_dawnr_kept_in_any_place_it_keeps_it(tmp_path, args):
    # Each place PRIVACY.md lists as erased by `dawnr forget` (and by `--all`), with what dawnr itself writes there.
    _home, data, env, default = forget_place(tmp_path)
    given = tmp_path / 'given state'
    assistant_session(tmp_path, env)                                 # the default state folder
    assistant_session(tmp_path, env, '--state', str(given))          # a folder given with --state, and its record
    for state in (default, given):
        journal_a_change(state)
    # the page's and the API's jobs (t/serve_api.py: a folder a job, the files given to it, what it printed)
    job = data / 'jobs' / '0123456789abcdef'
    (job / 'files').mkdir(parents=True)
    (job / 'files' / 'invoice.txt').write_text('Total due: 120\n')
    (job / 'stdout.txt').write_text('the answer\n')
    # the run folder: a model server's log, the API's token, the file that opens the page; no process id
    (data / 'run').mkdir(exist_ok=True)
    for name in ('base.log', 'api.token', 'open.html'):
        (data / 'run' / name).write_text('kept\n')
    # what install.sh puts in the data folder, and the folders it unpacks into when it stops before moving them
    installed = ['models/dawnr.gguf', 'downloads/llama.tar.gz.part', 'llama.cpp/llama-server', 'provers/dafny/dafny',
                 'pylib/pypdfium2/__init__.py', 'llama.cpp.tmp/llama-server', 'cudart.tmp/libcudart.so',
                 'pylib.tmp/pypdfium2/__init__.py']
    for rel in installed:
        (data / rel).parent.mkdir(parents=True, exist_ok=True)
        (data / rel).write_text('installed\n')
    assert (default / 'journal.jsonl').is_file() and (given / 'journal.jsonl').is_file()
    got = forget(env, *args)
    assert got.returncode == 0, got.stderr
    # what is left: of the two state folders nothing, of the data folder only what install.sh put there (or nothing)
    left = [str(p) for p in (default, given) if os.path.lexists(p)] + sorted(p.name for p in data.iterdir())
    assert left == ([] if args else sorted({rel.split('/')[0] for rel in installed} | {'env'})), f'left: {left}\n{got.stdout}'
    assert 'PRIVACY.md (Erasing)' in got.stdout.splitlines()[-1]     # what it does not erase is said, and where


def test_forget_keeps_a_recorded_folder_that_is_not_a_dawnr_state_folder(tmp_path):
    home, data, env, _default = forget_place(tmp_path)
    mixed = tmp_path / 'project'                    # the journal beside a file of the person's own
    journal_a_change(mixed)
    (mixed / 'thesis.tex').write_text('my own words\n')
    real = tmp_path / 'real state'                  # a dawnr state folder, named through a link to it
    journal_a_change(real)
    link = tmp_path / 'linked state'
    link.symlink_to(real, target_is_directory=True)
    elsewhere = tmp_path / 'elsewhere'              # a state folder reached through a link above it
    journal_a_change(elsewhere / 'state')
    (tmp_path / 'linked parent').symlink_to(elsewhere, target_is_directory=True)
    through = tmp_path / 'linked parent' / 'state'
    journal_a_change(home)                          # the home folder itself, holding nothing but a journal
    recorded = [mixed, link, through, home, 'relative/state']
    (data / 'state-folders').write_text(''.join(f'{p}\n' for p in recorded))
    before = {str(top): snapshot(top) for top in (mixed, real, elsewhere, home)}
    got = forget(env)
    assert got.returncode == 0, got.stderr
    for p in recorded:
        assert f'kept {p}: it does not look like a dawnr state folder' in got.stdout.splitlines(), got.stdout
    assert {str(top): snapshot(top) for top in (mixed, real, elsewhere, home)} == before
    assert os.path.islink(link) and os.path.islink(tmp_path / 'linked parent')
    assert not os.path.lexists(data / 'state-folders')


def test_forget_erases_a_state_folder_holding_the_copy_a_cut_of_the_plan_log_left_when_it_was_stopped(tmp_path):
    # the plan log is cut by writing the shortened copy beside it (.plans.jsonl.XXXXXXXX.tmp, dawnr_agent/config.py)
    # and putting it in place; a computer that stopped between the two leaves the copy, which is dawnr's own file
    _home, data, env, _default = forget_place(tmp_path)
    left, odd = tmp_path / 'left', tmp_path / 'odd'
    for state in (left, odd):
        journal_a_change(state)
        (state / 'plans.jsonl').write_text('{}\n')
    (left / '.plans.jsonl.0a1b2c3d.tmp').write_text('{}\n')
    (odd / '.plans.jsonl.notes.tmp').write_text('my own file\n')              # the same kind of name, not the agent's
    (data / 'state-folders').write_text(f'{left}\n{odd}\n')
    before = snapshot(odd)
    got = forget(env)
    assert got.returncode == 0, got.stderr
    assert f'erased {left}' in got.stdout.splitlines(), got.stdout
    assert not os.path.lexists(left)
    assert f'kept {odd}: it does not look like a dawnr state folder' in got.stdout.splitlines(), got.stdout
    assert snapshot(odd) == before


def test_forget_erases_a_state_folder_holding_the_lock_file_and_keeps_one_where_that_name_is_something_else(tmp_path):
    # every write to the plan log and the journal is made under a lock on `.lock` in the state folder
    # (locallm/dawnr_agent/statelock.py): an empty file of dawnr's own, so a folder holding it is still dawnr's
    _home, data, env, _default = forget_place(tmp_path)
    locked, linked, folder = tmp_path / 'locked', tmp_path / 'linked', tmp_path / 'folder'
    for state in (locked, linked, folder):
        journal_a_change(state)
    (locked / '.lock').write_bytes(b'')                                       # as the journal's writes leave it
    for state in (linked, folder):
        (state / '.lock').unlink(missing_ok=True)                             # this test's own folders: swap it
    (tmp_path / 'theirs.txt').write_text('my own file\n')
    (linked / '.lock').symlink_to(tmp_path / 'theirs.txt')                    # a link at that name: not dawnr's file
    (folder / '.lock').mkdir()                                                # a folder at that name: not dawnr's file
    (data / 'state-folders').write_text(f'{locked}\n{linked}\n{folder}\n')
    before = {str(top): snapshot(top) for top in (linked, folder)}
    got = forget(env)
    assert got.returncode == 0, got.stderr
    assert f'erased {locked}' in got.stdout.splitlines(), got.stdout
    assert not os.path.lexists(locked)
    for kept in (linked, folder):
        assert f'kept {kept}: it does not look like a dawnr state folder' in got.stdout.splitlines(), got.stdout
    assert {str(top): snapshot(top) for top in (linked, folder)} == before
    assert (tmp_path / 'theirs.txt').read_text() == 'my own file\n'
