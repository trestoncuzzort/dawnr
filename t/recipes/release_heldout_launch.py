"""Run one qualified final reading with the frozen decoder and observed model bytes.

Sources: laptop_route.sh, v6_server_route.py, release_decode_arms.py and the
prospective model-identity observer; https://docs.kernel.org/filesystems/proc.html
Only the explicit CLI execution path starts processes. Importing is read-only.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import release_heldout_inputs as heldout

require, digest, read = heldout.require, heldout.digest, heldout.read
PORT = 8851
CONTROL_MODULES = {'release_heldout_launch.py', 'release_heldout_inputs.py', 'release_seed_selection.py',
                   'release_grading_inputs.py', 'release_decode_arms.py', 'three_decode_report.py', 'v6_export.py'}


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    temporary = path.with_name(path.name + '.part')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n'); temporary.replace(path)


def file_identity(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'missing or linked model file')
    state = path.stat()
    return {key: getattr(state, 'st_' + key) for key in ('ino', 'size', 'mtime_ns', 'ctime_ns')}


def process(pid):
    root = Path('/proc') / str(pid)
    before = (root / 'stat').read_text().rsplit(')', 1)[1].split()
    value = {'pid': pid, 'parent_pid': int(before[1]), 'start_ticks': int(before[19]),
             'command': (root / 'cmdline').read_bytes().rstrip(b'\0').decode().split('\0'),
             'cwd': str((root / 'cwd').resolve(strict=True)), 'exe': str((root / 'exe').resolve(strict=True))}
    require((root / 'stat').read_text().rsplit(')', 1)[1].split()[19] == before[19], 'process identity changed')
    return value


def owns_listener(pid, port):
    root = Path('/proc') / str(pid)
    address = '0100007F:' + format(port, '04X')
    inodes = {line.split()[9] for line in (root / 'net/tcp').read_text().splitlines()[1:]
              if line.split()[1] == address and line.split()[3] == '0A'}
    sockets = set()
    for path in (root / 'fd').iterdir():
        try: target = os.readlink(path)
        except FileNotFoundError: continue
        if target.startswith('socket:['): sockets.add(target[8:-1])
    return bool(inodes & sockets)


def server_command(claim):
    paths = claim['paths']
    return [paths['server_dir'] + '/llama-server', '--model', paths['model'], '--alias', 'dawnr-route',
            '--host', '127.0.0.1', '--port', str(PORT), '--n-gpu-layers', '99', '--threads', '8',
            '--threads-batch', '8', '--parallel', '4', '--ctx-size', '16384', '--cache-ram', '512',
            '--chat-template-kwargs', '{"enable_thinking":false}']


def client_command(claim, python):
    root = claim['paths']['checkout']
    return [python, root + '/t/recipes/v6_server_route.py', '--endpoint',
            f'http://127.0.0.1:{PORT}/v1/chat/completions', '--model', 'dawnr-route',
            '--identity', claim['identity'], '--cache', root + '/t/out/laptop-runs/cache-' + claim['tag'],
            '--concurrency', '4', '--', *claim['route_args']]


def runtime_files(folder):
    folder = Path(folder)
    paths = {(folder / 'llama-server').resolve(strict=True)}
    paths |= {p.resolve(strict=True) for p in folder.glob('*.so*') if p.is_file()}
    require(all(p.parent == folder.resolve() for p in paths), 'server runtime file is outside its registered directory')
    return {p.name: digest(p) for p in sorted(paths)}


def verify_sources(claim, decoder, protocol):
    root = Path(claim['paths']['checkout'])
    revision = subprocess.check_output(['git', '-c', 'safe.directory=' + str(root), '-C', str(root),
                                        'rev-parse', 'HEAD'], text=True).strip()
    require(revision == protocol['execution_revision'], 'decoder checkout revision changed')
    require(all(digest(root / name) == sha for name, sha in decoder['sources'].items())
            and digest(root / 't/recipes/v6_server_route.py') == claim['route_driver_sha256'],
            'frozen decoder sources changed')
    require(set(protocol['launcher_sources_sha256']) == CONTROL_MODULES
            and all(digest(Path(__file__).parent / name) == sha
                    for name, sha in protocol['launcher_sources_sha256'].items()), 'launcher implementation changed')
    require(runtime_files(claim['paths']['server_dir']) == protocol['server_files_sha256'],
            'server binary or shared libraries changed')


def cache_files(cache, claim):
    """Read only atomically completed request records; retain temporary files in place."""
    result = {}
    for path in sorted(cache.glob('*.json')):
        if path.name in ('protocol.json', 'completed.json'): continue
        require(re.fullmatch(r'[0-9a-f]{64}\.json', path.name) and not path.is_symlink(), 'foreign cache record')
        value = read(path)
        # v6_server_route.canonical deliberately preserves UTF-8 rather than ASCII escapes.
        encoded = json.dumps([claim['identity'], value['request']], sort_keys=True,
                             ensure_ascii=False, separators=(',', ':')).encode()
        require(value['identity'] == claim['identity'] and hashlib.sha256(encoded).hexdigest() == path.stem
                and value['request']['model'] == 'dawnr-route' and value['request']['max_tokens'] == 1024,
                'cached request identity differs')
        result[path.name] = digest(path)
    require(len(result) <= 182 * 17, 'final reading exceeded its logical request bound')
    return result


def check_process(value, command, executable, root, parent_pid):
    require(value['command'] == command and value['exe'] == executable and value['cwd'] == root
            and value['parent_pid'] == parent_pid and type(value['pid']) is int and value['pid'] > 0
            and type(value['start_ticks']) is int and value['start_ticks'] > 0, 'observed process differs')


def validate_invocation(record, claim, protocol, generation):
    require(record['kind'] == 'observed-private-heldout-generation'
            and record['claim_sha256'] == heldout.choose.sha(claim)
            and record['generation_sha256'] == heldout.choose.sha(generation)
            and record['launcher_sources_sha256'] == protocol['launcher_sources_sha256']
            and record['server_files_sha256'] == protocol['server_files_sha256']
            and record['model_sha256_before'] == record['model_sha256_after'] == claim['model_sha256']
            and record['model_file_before'] == record['model_file_after']
            and record['sources_rechecked'] is True, 'model invocation binding differs')
    attempts = record['attempts']
    require(isinstance(attempts, list) and attempts and attempts[-1]['status'] == 'completed'
            and all(a['status'] in ('failed', 'interrupted') for a in attempts[:-1]), 'invalid final invocation history')
    previous = {}
    for number, attempt in enumerate(attempts, 1):
        start = attempt['start']
        require(start['attempt'] == number and start['claim_sha256'] == record['claim_sha256']
                and start['model_sha256'] == claim['model_sha256']
                and start['model_file'] == record['model_file_before']
                and start['runtime_files_sha256'] == record['server_files_sha256'], 'attempt identity changed')
        require(all(start['cache_before'].get(k) == v for k, v in previous.items()), 'resumed cache changed')
        require(all(attempt['cache_after'].get(k) == v for k, v in start['cache_before'].items()), 'cached answers were replaced')
        for sha in attempt['cache_after'].values(): heldout.choose.check_digest(sha)
        require(len(attempt['cache_after']) <= 182 * 17, 'request count exceeds its bound')
        check_process(start['server'], server_command(claim), claim['paths']['server_dir'] + '/llama-server',
                      claim['paths']['checkout'], start['parent_pid'])
        require(start['server_owned_listener'] is True, 'server did not own the model endpoint')
        if attempt.get('client') is not None:
            check_process(attempt['client'], client_command(claim, start['python']), start['python_exe'],
                          claim['paths']['checkout'], start['parent_pid'])
            require(start['server']['pid'] != attempt['client']['pid'], 'server and client identities overlap')
        else:
            require(attempt['status'] != 'completed' and attempt['cache_after'] == start['cache_before'],
                    'cached answers lack an observed client')
        previous = attempt['cache_after']
    require(attempts[-1]['returncode'] == 0 and record['cache_sha256'] == previous,
            'final invocation did not complete with its recorded cache')
    return record


def terminate(child):
    if child is None or child.poll() is not None: return
    child.terminate()
    try: child.wait(timeout=20)
    except subprocess.TimeoutExpired:
        child.kill(); child.wait(timeout=10)


def receipt(claim, protocol, generation, model_file, attempts):
    value = {'kind': 'observed-private-heldout-generation', 'claim_sha256': heldout.choose.sha(claim),
             'generation_sha256': heldout.choose.sha(generation), 'model_sha256_before': claim['model_sha256'],
             'model_sha256_after': claim['model_sha256'], 'model_file_before': model_file, 'model_file_after': model_file,
             'launcher_sources_sha256': protocol['launcher_sources_sha256'],
             'server_files_sha256': protocol['server_files_sha256'], 'sources_rechecked': True,
             'attempts': attempts, 'cache_sha256': attempts[-1]['cache_after']}
    return validate_invocation(value, claim, protocol, generation)


def run(bundle, decoder, protocol, paths, ready_file, resume=False):
    import fcntl  # GPU execution is Linux-only; importing the module remains portable.
    require(os.environ.get('DAWNR_REMOTE_COMPUTE') == '1' and sys.platform == 'linux',
            'final generation requires the approved remote compute environment')
    decision = heldout.qualified(bundle)
    require(all(str(Path(value).resolve()) == value for value in paths.values()), 'execution paths must be canonical')
    require(ready_file.is_file() and not ready_file.is_symlink(), 'registered development generation is still incomplete')
    panel = Path(paths['panel']).read_bytes()
    request = heldout.request(bundle, panel, decision['selected_model_sha256'], decoder, protocol, paths)
    root = Path(paths['checkout']); runs = root / 't/out/laptop-runs'; runs.mkdir(parents=True, exist_ok=True)
    folder = runs / ('private-heldout-' + request['tag']); folder.mkdir(exist_ok=True)
    with (folder / 'launch.lock').open('a') as lock, (root / 't/out/.laptop-gpu.lock').open('a') as gpu:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(gpu, fcntl.LOCK_EX | fcntl.LOCK_NB)
        verify_sources(request, decoder, protocol)
        model_file = file_identity(paths['model'])
        model_sha = digest(Path(paths['model']))
        require(model_sha == decision['selected_model_sha256'] and file_identity(paths['model']) == model_file
                and model_file['size'] == bundle['seeds'][str(decision['selected_seed'])]['export']['output']['bytes'],
                'model file differs from the selected export')
        cache = runs / ('cache-' + request['tag'])
        claim_path = folder / 'claim.json'
        if not claim_path.exists():
            require(not cache.exists() and not (root / 't/out/spec-experiment' / request['tag']).exists(),
                    'unreceipted final generation already exists')
        claim = heldout.claim(claim_path, bundle, panel, model_sha, decoder, protocol, paths)
        if (folder / 'receipt.json').exists():
            completed = heldout.completed(root, claim, bundle, panel, decoder, protocol)
            value = validate_invocation(read(folder / 'receipt.json'), claim, protocol, completed)
            require(cache_files(cache, claim) == value['cache_sha256'], 'completed cache changed')
            return value
        attempts = []
        for path in sorted(folder.glob('attempt-*/start.json')):
            require(resume, 'an original reading exists; explicit same-cache recovery is required')
            start = read(path)
            require(start['model_file'] == model_file and start['model_sha256'] == model_sha
                    and start['claim_sha256'] == heldout.choose.sha(claim), 'interrupted model identity changed')
            end = path.parent / 'end.json'
            if end.exists():
                attempts.append(read(end))
            else:
                interrupted = {'status': 'interrupted', 'start': start,
                               'client': read(path.parent / 'client.json') if (path.parent / 'client.json').exists() else None,
                               'cache_after': cache_files(cache, claim), 'returncode': None, 'observed_recovery_utc': now()}
                write(end, interrupted); attempts.append(interrupted)
            require(attempts[-1].get('client') is not None
                    or attempts[-1]['cache_after'] == start['cache_before'], 'cached answers lack an observed client')
        if attempts:
            if attempts[-1]['status'] == 'completed':
                generation = heldout.completed(root, claim, bundle, panel, decoder, protocol)
                require(cache_files(cache, claim) == attempts[-1]['cache_after'], 'completed original cache changed')
                value = receipt(claim, protocol, generation, model_file, attempts)
                write(folder / 'receipt.json', value)
                return value
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(('127.0.0.1', PORT))
        cache.mkdir(exist_ok=True)
        before = cache_files(cache, claim)
        if attempts:
            require(all(before.get(k) == v for k, v in attempts[-1]['cache_after'].items()), 'original cached answers changed')
        # A server that failed before a client was launched still retains its own diagnostics.
        directory_number = len(list(folder.glob('attempt-*'))) + 1
        attempt = folder / ('attempt-' + str(directory_number).zfill(3)); attempt.mkdir()
        env = {**os.environ, **heldout.SETTINGS, 'LD_LIBRARY_PATH': paths['server_dir'],
               'PYTHONPATH': str(root / 't'), 'PYTHONUNBUFFERED': '1'}
        server = client = None; start = client_record = None; returncode = None
        try:
            with (attempt / 'server.log').open('wb') as log:
                server = subprocess.Popen(server_command(claim), cwd=root, env=env, stdout=log,
                                          stderr=subprocess.STDOUT, pass_fds=(lock.fileno(), gpu.fileno()))
            for _ in range(240):
                require(server.poll() is None, 'registered server exited before readiness')
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=2) as response:
                        if response.status == 200: break
                except (urllib.error.URLError, TimeoutError): time.sleep(1)
            else: raise TimeoutError('registered server did not become ready')
            server_record = process(server.pid)
            check_process(server_record, server_command(claim), paths['server_dir'] + '/llama-server', str(root), os.getpid())
            require(owns_listener(server.pid, PORT), 'the configured server does not own the model endpoint')
            require(file_identity(paths['model']) == model_file, 'selected model changed before generation')
            start = {'attempt': len(attempts) + 1, 'utc': now(), 'claim_sha256': heldout.choose.sha(claim),
                     'model_sha256': model_sha, 'model_file': model_file, 'runtime_files_sha256': protocol['server_files_sha256'],
                     'cache_before': before, 'parent_pid': os.getpid(), 'server': server_record,
                     'server_owned_listener': True, 'python': sys.executable,
                     'python_exe': str(Path(sys.executable).resolve())}
            write(attempt / 'start.json', start)
            with (attempt / 'route.log').open('wb') as log:
                client = subprocess.Popen(client_command(claim, sys.executable), cwd=root, env=env,
                                          stdout=log, stderr=subprocess.STDOUT, pass_fds=(lock.fileno(), gpu.fileno()))
            client_record = process(client.pid)
            check_process(client_record, client_command(claim, sys.executable), start['python_exe'], str(root), os.getpid())
            write(attempt / 'client.json', client_record)
            returncode = client.wait(timeout=12 * 3600)
            require(returncode == 0, 'original decoder failed; preserve its cache and diagnostics')
            (runs / (claim['tag'] + '.done')).write_text('0\n')
            generation = heldout.completed(root, claim, bundle, panel, decoder, protocol)
            verify_sources(claim, decoder, protocol)
            require(file_identity(paths['model']) == model_file and digest(Path(paths['model'])) == model_sha,
                    'selected model bytes changed during generation')
            after = cache_files(cache, claim)
            require(all(after.get(k) == v for k, v in before.items()), 'original cached answers changed')
            end = {'status': 'completed', 'start': start, 'client': client_record,
                   'cache_after': after, 'returncode': returncode, 'utc': now()}
            write(attempt / 'end.json', end); attempts.append(end)
            value = receipt(claim, protocol, generation, model_file, attempts)
            write(folder / 'receipt.json', value)
            return value
        finally:
            terminate(client); terminate(server)
            if start is not None and not (attempt / 'end.json').exists():
                write(attempt / 'end.json', {'status': 'failed', 'start': start, 'client': client_record,
                                           'cache_after': cache_files(cache, claim), 'returncode': returncode, 'utc': now()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'decoder', 'protocol', 'paths', 'development-ready'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--resume-original', action='store_true')
    args = parser.parse_args()
    result = run(read(args.bundle), read(args.decoder), read(args.protocol), read(args.paths),
                 args.development_ready, args.resume_original)
    print(json.dumps({'complete': True, 'model_sha256': result['model_sha256_after'],
                      'original_cache_records': len(result['cache_sha256'])}))


if __name__ == '__main__':
    main()
