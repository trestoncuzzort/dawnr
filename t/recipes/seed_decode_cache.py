"""Copy cached requests without sharing mutable files between evaluation runs.

Only the request records named by v6_server_route.Decoder are reusable. Protocols,
completion receipts and locks belong to one run and must never be imported.
Source: v6_server_route.Decoder's atomic cache writes and request identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile

from v6_server_route import canonical


def seed_cache(source: Path, destination: Path) -> int:
    if source.is_symlink() or destination.is_symlink():
        raise ValueError("cache directories must not be symbolic links")
    destination.mkdir(parents=True, exist_ok=True)
    if source.resolve() == destination.resolve():
        return 0
    copied = 0
    for path in sorted(source.iterdir()):
        if not re.fullmatch(r"[0-9a-f]{64}\.json", path.name):
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError("cached requests must be regular files")
        target = destination / path.name
        if target.is_symlink():
            raise ValueError("destination cached request is a symbolic link")
        if target.exists():
            continue
        contents = path.read_bytes()
        record = json.loads(contents)
        if (not isinstance(record, dict) or not isinstance(record.get("identity"), str)
                or not isinstance(record.get("request"), dict)
                or not isinstance(record.get("response"), dict)):
            raise ValueError("invalid cached request")
        expected = hashlib.sha256(canonical([record["identity"], record["request"]])).hexdigest()
        if path.stem != expected:
            raise ValueError("cached request filename does not match its identity")
        with tempfile.NamedTemporaryFile(dir=destination, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(contents)
        try:
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        copied += 1
    return copied


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(f"Copied {seed_cache(args.source, args.destination)} cached requests")


if __name__ == "__main__":
    main()
