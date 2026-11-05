#!/usr/bin/env python3
"""Fetch the pinned Ventoy test-host package and reuse source_lock verification."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "sources"))
from acquire import fetch
from source_lock import Refusal, verify_record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    record = json.loads((HERE / "ventoy-source.json").read_bytes())
    try:
        fetch(record["url"], args.cache / record["name"], maximum=32 * 1024 * 1024)
        result = verify_record(record, args.cache, HERE / "evidence", None)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, KeyError) as error:
        print("Ventoy acquisition refused: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
