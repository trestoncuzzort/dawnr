#!/usr/bin/env python3
"""Bounded HTTPS retrieval into a private cache; downloading is not verification.

The receipt records origin, time and observed bytes. Only source_lock.py's
publisher-evidence checks can turn cached bytes into verified source records.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from source_lock import NAME, Refusal, digest, encoded, https


class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not https(newurl):
            raise Refusal("refusing a non-HTTPS redirect")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def fetch(url: str, destination: Path, *, maximum=512 * 1024 * 1024, body=None) -> dict:
    if not https(url):
        raise Refusal("download URL must use HTTPS")
    receipt_path = destination.with_name(destination.name + ".download.json")
    if destination.is_symlink() or receipt_path.is_symlink():
        raise Refusal("symlink cache target refused")
    if destination.exists() and receipt_path.exists():
        receipt = json.loads(receipt_path.read_bytes())
        if receipt.get("url") != url or digest(destination) != receipt.get("sha256"):
            raise Refusal("cached bytes or source URL changed; inspect before replacing")
        return receipt
    if destination.exists():
        raise Refusal("unreceipted cache entry; inspect before replacing")
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, data=body, headers={"User-Agent": "TUP-source-audit/1"})
    opener = urllib.request.build_opener(HTTPSOnly)
    descriptor, temporary = tempfile.mkstemp(prefix=".source-", dir=destination.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as output, opener.open(request, timeout=40) as response:
            size = 0
            h = hashlib.sha256()
            if int(response.headers.get("Content-Length", 0)) > maximum:
                raise Refusal("publisher file exceeds download budget")
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > maximum:
                    raise Refusal("publisher file exceeds download budget")
                h.update(chunk)
                output.write(chunk)
            receipt = {"url": url, "resolved_url": response.url,
                       "retrieved_at": datetime.now(timezone.utc).isoformat(),
                       "sha256": h.hexdigest(), "size": size,
                       "meaning": "observed download bytes; not authentication"}
        temporary.replace(destination)
        receipt_path.write_bytes(encoded(receipt))
        return receipt
    finally:
        temporary.unlink(missing_ok=True)


def acquire_record(record: dict, cache: Path) -> dict:
    name = record["name"]
    if not NAME.fullmatch(name):
        raise Refusal("unsafe source basename")
    urls = record.get("download_urls", [record["url"]])
    if not isinstance(urls, list) or not urls or any(not https(url) for url in urls):
        raise Refusal("download locations must be reviewed HTTPS URLs")
    if record["url"] not in urls:
        raise Refusal("download locations must preserve the upstream source URL")
    path = cache / name
    receipt = path.with_name(name + ".download.json")
    if path.exists():
        if not receipt.is_file():
            raise Refusal("unreceipted cache entry; inspect before replacing")
        previous = json.loads(receipt.read_bytes()).get("url")
        if previous not in urls:
            raise Refusal("cached source came from an unreviewed download location")
        return fetch(previous, path)
    failures = []
    for url in urls:
        try:
            return fetch(url, path)
        except (OSError, ValueError) as exc:
            failures.append(str(exc))
    raise Refusal("all reviewed download locations failed: " + " | ".join(failures))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--names", nargs="*")
    args = parser.parse_args(argv)
    if not 1 <= args.jobs <= 6:
        parser.error("--jobs must be between 1 and 6")
    catalog = json.loads(args.catalog.read_bytes())
    inputs = catalog["sources"] + catalog.get("verification_archives", [])
    records = [record for record in inputs if record.get("disposition") != "omit"
               and (not args.names or record["name"] in args.names)]
    errors = []

    def collect(record):
        name = record["name"]
        receipt = acquire_record(record, args.cache)
        return name, receipt["size"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(collect, record): record["name"] for record in records}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                _, size = future.result()
                print(f"cached {name}: {size} bytes", flush=True)
            except Exception as exc:
                errors.append({"name": name, "error": str(exc)})
                print(f"unavailable {name}: {exc}", flush=True)
    (args.cache / "acquisition-errors.json").write_bytes(encoded(errors))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
