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


def check_manifest(path: Path):
    names = set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'([0-9a-fA-F]{64})\s+([A-Za-z0-9][A-Za-z0-9._-]*\.gguf)', line.strip())
        if not match or match[2] in names:
            raise ValueError('model manifest needs unique GGUF filenames and SHA-256 hashes')
        names.add(match[2])
    if not names:
        raise ValueError('model manifest is empty')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check-manifest')
    check.add_argument('path', type=Path)
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
