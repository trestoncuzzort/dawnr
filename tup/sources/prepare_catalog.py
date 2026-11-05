#!/usr/bin/env python3
"""Capture the published LFS source inventory without approving its downloads."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from acquire import fetch
from source_lock import CATALOG_SCHEMA, Refusal, digest, encoded

BASE = "https://www.linuxfromscratch.org/lfs/view/13.1-systemd/"


def prepare(wget: bytes, md5sums: bytes, selections: dict, inventory: dict) -> dict:
    urls = wget.decode("utf-8").splitlines()
    urls = [url for url in urls if url.strip()]
    md5s = {}
    for line in md5sums.decode("ascii").splitlines():
        match = re.fullmatch(r"([a-f0-9]{32}) [ *](.+)", line)
        if not match or match[2] in md5s:
            raise Refusal("invalid or duplicate book MD5 inventory")
        md5s[match[2]] = match[1]
    names = [url.rsplit("/", 1)[-1] for url in urls]
    if len(names) != 94 or set(names) != set(md5s):
        raise Refusal("book source/patch inventory changed; review before regenerating")
    replacements = selections["replacements"]
    if set(replacements) - set(names):
        raise Refusal("replacement does not identify a baseline source")
    sources = []
    for original_url, baseline in zip(urls, names):
        selected = replacements.get(baseline, {})
        url = selected.get("url", original_url)
        # Use the canonical publisher, not a redirect-to-arbitrary-mirror URL.
        url = url.replace("https://ftpmirror.gnu.org/", "https://ftp.gnu.org/gnu/")
        url = url.replace("https://github.com//", "https://github.com/")
        sources.append({"baseline_name": baseline, "book_url": original_url,
                        "book_md5": md5s[baseline], "name": selected.get("name", baseline),
                        "url": url, "disposition": "replace" if selected else "retain",
                        "reason": selected.get("reason", "Retain the pinned book input."),
                        "authentication": {"method": "unresolved",
                                           "reason": "No publisher SHA256 or signature verified yet."}})
    return {"schema": CATALOG_SCHEMA, "architecture": "x86_64", "book_version": "13.1-systemd",
            "prepared_at": datetime.now(timezone.utc).isoformat(), "inventory": inventory,
            "advisory_review": {"status": "unresolved", "dispositions": []}, "sources": sources}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--selections", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("refusing to overwrite an existing reviewed catalog")
    args.evidence.mkdir(parents=True, exist_ok=True)
    for name in ("wget-list-systemd", "md5sums"):
        fetch(BASE + name, args.evidence / name, maximum=1024 * 1024)
    inventory = {"path": "wget-list-systemd", "url": BASE + "wget-list-systemd",
                 "sha256": digest(args.evidence / "wget-list-systemd")}
    catalog = prepare((args.evidence / "wget-list-systemd").read_bytes(),
                      (args.evidence / "md5sums").read_bytes(),
                      json.loads(args.selections.read_bytes()), inventory)
    args.output.write_bytes(encoded(catalog))
    print(f"Prepared {len(catalog['sources'])} unresolved source records")


if __name__ == "__main__":
    main()
