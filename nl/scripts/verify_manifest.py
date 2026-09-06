#!/usr/bin/env python3
"""Verify every file in nl/data against nl/manifest.json.

Twenty checks over ten files: for each, the SHA-256 of the shipped .jsonl.gz,
the SHA-256 of the decompressed .jsonl, and along the way the record count and
the decompressed byte count. A manifest that is not checked is a claim, not a
receipt, so this exists to be run rather than read.

    python3 scripts/verify_manifest.py            # all files
    python3 scripts/verify_manifest.py mbpp       # only names containing "mbpp"

Exit 0 when every check passes, 1 on any mismatch or missing file. Standard
library only. The big two files decompress about 3.5 GB between them and are
streamed, never written to disk; expect a couple of minutes for a full run.
"""
import gzip
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CHUNK = 1 << 22


def gz_digest(path):
    """SHA-256 of the file as shipped, and its size on disk."""
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
            n += len(block)
    return h.hexdigest(), n


def raw_digest(path):
    """SHA-256 of the decompressed bytes, the record count and the byte count.

    Counted line by line so nothing larger than one record is ever held, and
    so the count means the same thing the builder meant: one JSON object per
    non-blank line.
    """
    h = hashlib.sha256()
    records = 0
    nbytes = 0
    with gzip.open(path, "rb") as f:
        for line in f:
            h.update(line)
            nbytes += len(line)
            if line.strip():
                records += 1
    return h.hexdigest(), records, nbytes


def check(entry):
    """Return (name, [(label, ok, detail), ...]) for one manifest entry."""
    name = entry["file"]
    path = os.path.join(ROOT, "data", name)
    if not os.path.exists(path):
        return name, [("present", False, "missing from data/")]

    results = []
    got, size = gz_digest(path)
    results.append(("gz sha256", got == entry["gz_sha256"],
                    "match" if got == entry["gz_sha256"]
                    else "got %s want %s" % (got[:16], entry["gz_sha256"][:16])))
    results.append(("gz bytes", size == entry["gz_bytes"],
                    "%d" % size if size == entry["gz_bytes"]
                    else "got %d want %d" % (size, entry["gz_bytes"])))

    got, records, nbytes = raw_digest(path)
    results.append(("raw sha256", got == entry["raw_sha256"],
                    "match" if got == entry["raw_sha256"]
                    else "got %s want %s" % (got[:16], entry["raw_sha256"][:16])))
    results.append(("records", records == entry["records"],
                    "%d" % records if records == entry["records"]
                    else "got %d want %d" % (records, entry["records"])))
    results.append(("raw bytes", nbytes == entry["raw_bytes"],
                    "%d" % nbytes if nbytes == entry["raw_bytes"]
                    else "got %d want %d" % (nbytes, entry["raw_bytes"])))
    return name, results


def main(argv):
    want = argv[1] if len(argv) > 1 else ""
    with open(os.path.join(ROOT, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)

    entries = [e for e in manifest["files"] if want in e["file"]]
    if not entries:
        print("no file in manifest.json matches %r" % want)
        return 1

    failures = 0
    total = 0
    for entry in entries:
        name, results = check(entry)
        bad = [r for r in results if not r[1]]
        failures += len(bad)
        total += len(results)
        flag = "FAIL" if bad else "ok  "
        print("%s %-32s %s" % (flag, name,
                               ", ".join("%s %s" % (label, detail)
                                         for label, _, detail in results)))

    print()
    print("%d files, %d checks, %d failed" % (len(entries), total, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
