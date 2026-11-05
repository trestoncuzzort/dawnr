#!/usr/bin/env python3
"""Collect publisher checksum metadata; never derive expected hashes from downloads.

This tool records the explicitly weaker HTTPS-published-SHA256 trust class.
The publisher origin is a reviewed trust anchor. Signature verification is a
separate step; a checksum in a .asc document is not called signature-verified.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from acquire import fetch
from source_lock import Refusal, digest, encoded, published_digest


def metadata_for(record):
    url, name = record["url"], record["name"]
    parsed = urlsplit(url)
    parts = parsed.path.strip("/").split("/")
    if parsed.hostname == "github.com" and len(parts) >= 6 and parts[2:4] == ["releases", "download"]:
        owner, repo, _, _, tag = parts[:5]
        return (f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}",
                f"github-{owner}-{repo}-{tag}.json", {"format": "github-release", "tag": tag})
    if parsed.hostname in {"pypi.org", "files.pythonhosted.org"}:
        match = re.fullmatch(r"(.+)-([0-9][^-]+)\.tar\.gz", name)
        if match:
            project, version = match.groups()
            return (f"https://pypi.org/pypi/{project}/{version}/json",
                    f"pypi-{project}-{version}.json", {"format": "pypi-release", "version": version})
    if parsed.hostname in {"www.kernel.org", "cdn.kernel.org"}:
        directory = url.rsplit("/", 1)[0]
        label = "kernel-" + "-".join(parts[1:-1]) + "-sha256sums.asc"
        return directory + "/sha256sums.asc", label, {"format": "sha256sum"}
    if name == "Python-3.14.10.tar.xz":
        return ("https://www.python.org/downloads/release/python-31410/", "python-31410.html",
                {"format": "html-table", "artifact_url": url})
    return None


def collect(record, evidence):
    proposal = metadata_for(record)
    if proposal is None:
        return None
    url, filename, selection = proposal
    filename = re.sub(r"[^A-Za-z0-9_.+-]", "_", filename)
    path = evidence / filename
    fetch(url, path, maximum=8 * 1024 * 1024)
    expected = published_digest(path.read_bytes(), selection, record["name"])
    return {"method": "https-published-sha256",
            "material": {"path": filename, "url": url, "sha256": digest(path)},
            "selection": selection}, expected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    catalog = json.loads(args.catalog.read_bytes())
    changed, errors = 0, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        pending = {pool.submit(collect, record, args.evidence): record for record in catalog["sources"]
                   if record["authentication"]["method"] == "unresolved"}
        for future in concurrent.futures.as_completed(pending):
            record = pending[future]
            try:
                result = future.result()
                if result:
                    record["authentication"], record["sha256"] = result
                    changed += 1
                    print("publisher checksum:", record["name"], flush=True)
            except Exception as exc:
                errors.append({"name": record["name"], "reason": str(exc)})
                print("unresolved:", record["name"], str(exc), flush=True)
    args.catalog.write_bytes(encoded(catalog))
    print(f"Recorded {changed} publisher SHA256 checksums; {len(errors)} metadata failures")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
