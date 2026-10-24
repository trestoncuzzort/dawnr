"""Write the installed launcher and shell configuration without losing path boundaries.

Keeps install.sh's custom DAWNR_* settings and replaces its old launcher symlink
atomically, so reinstalling never writes through that link into the checkout.
Source: https://docs.python.org/3/library/shlex.html#shlex.quote
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shlex
import tempfile


def atomic_write(path: Path, text: str, mode: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f'.{path.name}-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def configure(repo: Path, home: Path, bin_dir: Path, settings: dict[str, str]):
    repo, home, bin_dir = repo.resolve(), home.resolve(), bin_dir.resolve()
    values = {**settings, 'DAWNR_REPO': str(repo), 'DAWNR_HOME': str(home)}
    old = home / 'env'
    kept = []
    if old.exists():
        for line in old.read_text().splitlines():
            match = re.match(r'(DAWNR_[A-Z_]+)=', line)
            if match and match[1] not in values:
                kept.append(line)
    config = ''.join(f'{key}={shlex.quote(str(value))}\n' for key, value in values.items())
    if kept:
        config += '\n'.join(kept) + '\n'
    launcher = ('#!/usr/bin/env bash\nset -euo pipefail\n'
                'if [ -z "${DAWNR_HOME:-}" ]; then\n'
                f'  export DAWNR_HOME={shlex.quote(str(home))}\nfi\n'
                f'exec {shlex.quote(str(repo / "bin/dawnr"))} "$@"\n')
    atomic_write(old, config, 0o600)
    atomic_write(bin_dir / 'dawnr', launcher, 0o755)


GGUF_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*\.gguf')
# a model file of one of this repository's releases: a release that keeps the model of an earlier one lists the files
# where that release published them, so a new version never uploads the same weights again
RELEASE_FILE = re.compile(r'https://github\.com/trestoncuzzort/dawnr/releases/download/[A-Za-z0-9._-]+/'
                          r'([A-Za-z0-9][A-Za-z0-9._-]*\.gguf)')


def manifest_entries(path: Path, base_url: str = '') -> list[tuple[str, str, str]]:
    """(SHA-256, download URL, local file name) for every line of a model manifest.

    A line is a SHA-256 and either a file name of the release the manifest came from, or the URL of a model file in
    one of this repository's releases. Local names stay plain file names, so no entry can write outside the models
    directory, and two entries may not name the same file."""
    entries, names = [], set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2 or not re.fullmatch(r'[0-9a-fA-F]{64}', parts[0]):
            raise ValueError('model manifest needs unique GGUF filenames and SHA-256 hashes')
        digest, ref = parts
        published = RELEASE_FILE.fullmatch(ref)
        if published:
            name, url = published[1], ref
        elif GGUF_NAME.fullmatch(ref):
            name, url = ref, base_url.rstrip('/') + '/' + ref
        else:
            raise ValueError('model manifest needs unique GGUF filenames and SHA-256 hashes')
        if name in names:
            raise ValueError('model manifest needs unique GGUF filenames and SHA-256 hashes')
        names.add(name)
        entries.append((digest.lower(), url, name))
    if not entries:
        raise ValueError('model manifest is empty')
    return entries


def check_manifest(path: Path):
    manifest_entries(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check-manifest')
    check.add_argument('path', type=Path)
    entries = sub.add_parser('manifest-entries', help='print "SHA256 URL NAME" for every file a manifest lists')
    entries.add_argument('path', type=Path)
    entries.add_argument('base_url')
    write = sub.add_parser('write')
    for name in ('repo', 'home', 'bin-dir', 'python', 'server', 'build', 'student', 'base'):
        write.add_argument('--' + name, required=True)
    write.add_argument('--dafny')
    write.add_argument('--draft', action='store_true')
    write.add_argument('--invariant', action='store_true')
    args = parser.parse_args()
    if args.command == 'check-manifest':
        try:
            check_manifest(args.path)
        except (OSError, ValueError) as error:
            parser.error(str(error))
        return
    if args.command == 'manifest-entries':
        try:
            for digest, url, name in manifest_entries(args.path, args.base_url):
                print(digest, url, name)
        except (OSError, ValueError) as error:
            parser.error(str(error))
        return
    settings = {'DAWNR_PYTHON': args.python, 'LLAMA_SERVER': args.server,
                'DAWNR_BUILD': args.build, 'STUDENT_GGUF': args.student, 'BASE_GGUF': args.base}
    if args.dafny:
        settings['T_DAFNY'] = args.dafny
    if args.draft:
        settings['BASE_DRAFT'] = 'mtp'
    if args.invariant:
        settings['DOTNET_SYSTEM_GLOBALIZATION_INVARIANT'] = '1'
    configure(Path(args.repo), Path(args.home), Path(args.bin_dir), settings)


if __name__ == '__main__':
    main()
