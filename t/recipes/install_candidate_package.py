"""Install an explicitly identified release package during clean-machine checks.

Download through authenticated GitHub APIs, verify the expected manifest and
every shard, then serve those exact files on loopback to the normal installer.
Sources: install.sh and locallm/install_runtime.py;
https://docs.github.com/en/rest/releases/assets#get-a-release-asset
https://cli.github.com/manual/gh_api
"""
from __future__ import annotations

import argparse
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from locallm.install_runtime import manifest_entries

REPOSITORY = 'trestoncuzzort/dawnr'


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def metadata(release_id):
    result = subprocess.run(['gh', 'api', f'repos/{REPOSITORY}/releases/{release_id}'],
                            capture_output=True, text=True, check=True, timeout=60)
    release = json.loads(result.stdout)
    require(release['id'] == release_id and re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', release['tag_name']),
            'release ID or versioned tag differs')
    return release


def asset(release, name):
    found = [a for a in release['assets'] if a['name'] == name]
    require(len(found) == 1 and found[0]['state'] == 'uploaded', 'missing, duplicate or incomplete release asset')
    value = found[0]
    require(type(value['id']) is int and value['id'] > 0 and type(value['size']) is int
            and 0 < value['size'] < 2 * 1024**3, 'invalid release asset size or ID')
    return value


def download_asset(record, destination, expected_sha):
    require(not destination.exists() and not destination.is_symlink(), 'preserve the existing download for inspection')
    require(record.get('digest') in (None, 'sha256:' + expected_sha), 'GitHub asset digest differs from the expected file')
    part = destination.with_suffix(destination.suffix + '.part')
    with part.open('xb') as output:
        subprocess.run(['gh', 'api', '-H', 'Accept: application/octet-stream',
                        f'repos/{REPOSITORY}/releases/assets/{record["id"]}'],
                       stdout=output, stderr=subprocess.PIPE, check=True, timeout=1800)
    require(part.stat().st_size == record['size'] and digest(part) == expected_sha,
            'downloaded release asset differs from its registered size or checksum')
    part.replace(destination)


def fetch(release_id, manifest_sha, directory):
    require(type(release_id) is int and release_id > 0 and re.fullmatch(r'[0-9a-f]{64}', manifest_sha),
            'provide a release ID and the exact expected manifest SHA-256')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    release = metadata(release_id)
    manifest = asset(release, 'dawnr.sha256')
    require(manifest['size'] <= 64 * 1024, 'model manifest is too large')
    download_asset(manifest, directory / 'dawnr.sha256', manifest_sha)
    entries = manifest_entries(directory / 'dawnr.sha256')
    stem = 'dawnr-' + release['tag_name'][1:]
    names = [name for _, _, name in entries]
    require(1 <= len(names) <= 8 and names == [f'{stem}-{i:05d}-of-{len(names):05d}.gguf'
                                             for i in range(1, len(names) + 1)],
            'candidate manifest must name all versioned shards in order')
    require(all(url == '/' + name for _, url, name in entries),
            'candidate checks require the exact package in this release')
    files = {'dawnr.sha256': {'sha256': manifest_sha, 'bytes': manifest['size'], 'asset_id': manifest['id']}}
    for sha, _, name in entries:
        item = asset(release, name)
        download_asset(item, directory / name, sha)
        files[name] = {'sha256': sha, 'bytes': item['size'], 'asset_id': item['id']}
    return {'release_id': release_id, 'release_tag': release['tag_name'], 'release_was_draft': release['draft'],
            'manifest_sha256': manifest_sha, 'first_shard': names[0], 'files': files}


class PackageHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, allowed, **kwargs):
        self.allowed = allowed
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if urlsplit(self.path).path not in {'/' + name for name in self.allowed}:
            self.send_error(404)
            return
        super().do_GET()

    def do_HEAD(self):
        if urlsplit(self.path).path not in {'/' + name for name in self.allowed}:
            self.send_error(404)
            return
        super().do_HEAD()

    def log_message(self, *_args):
        pass


def install(directory, receipt, home):
    directory, home = Path(directory), Path(home)
    handler = partial(PackageHandler, directory=str(directory), allowed=set(receipt['files']))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        env = {key: value for key, value in os.environ.items() if key not in ('GH_TOKEN', 'GITHUB_TOKEN')}
        subprocess.run(['bash', str(REPO / 'install.sh'), '--home', str(home), '--model',
                        'http://127.0.0.1:' + str(server.server_port)], cwd=REPO, env=env, check=True, timeout=5400)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=10)
    for name, record in receipt['files'].items():
        installed = home / 'models' / name
        require(installed.is_file() and not installed.is_symlink() and installed.stat().st_size == record['bytes']
                and digest(installed) == record['sha256'], 'installed package differs from the checked release')
    return {**receipt, 'installed_model_files_verified': True,
            'application_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
            'application_version': (REPO / 'VERSION').read_text().strip()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-id', type=int, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--home', type=Path, default=Path.home() / '.local/share/dawnr')
    args = parser.parse_args()
    require(not args.receipt.exists(), 'preserve the existing installation receipt')
    receipt = fetch(args.release_id, args.manifest_sha256, args.directory)
    result = install(args.directory, receipt, args.home)
    args.receipt.write_text(json.dumps(result, indent=2) + '\n')
    shutil.rmtree(args.directory)  # The installed, reverified copy remains for the smoke workload.
    print(json.dumps({'release_id': result['release_id'], 'release_tag': result['release_tag'],
                      'manifest_sha256': result['manifest_sha256'], 'installed_model_files_verified': True}))


if __name__ == '__main__':
    main()
