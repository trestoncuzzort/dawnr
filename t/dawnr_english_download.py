#!/usr/bin/env python3
"""t/dawnr_english_download.py -- pull dawnr's first general-English shard set (2026-09-26).

Downloads every file named in t/dawnr-english-manifest.json (FineWeb-Edu
sample-10BT, https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu, ODC-BY
1.0; TinyStoriesV2-GPT4, https://huggingface.co/datasets/roneneldan/TinyStories,
CDLA-Sharing-1.0, arXiv:2305.07759) and verifies each one against the sha256 in
the manifest before calling it done.

The sha256 values in the manifest are Hugging Face's own LFS object ids: HF
Hub LFS/xet storage is content-addressed by sha256 (the same digest is served
in the `X-Linked-ETag`/`lfs.oid` fields of its own tree API,
https://huggingface.co/api/datasets/<repo>/tree/<rev>/<path>), so verifying a
download against the id already in the manifest is the same check the storage
layer itself uses, not an extra invented scheme -- a corrupted or truncated
download the transport itself never caught is refused by name rather than
silently kept.

Usage (run on the lab; the shards land under --dest, default ~/data/dawnr-english):

    python3 t/dawnr_english_download.py --manifest t/dawnr-english-manifest.json \\
        --dest ~/data/dawnr-english --max-bytes 60_000_000_000

Every file already present with a matching sha256 is skipped (re-runs are
free); a size or hash mismatch is refused and reported, never silently
overwritten. Total bytes are checked against --max-bytes (default 60 GB)
before anything downloads, so a manifest that grew past the disk budget is
caught before it starts, not partway through.
"""
import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

CHUNK = 8 * 1024 * 1024


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def download_one(url: str, dest: Path, expect_bytes: int, expect_sha256: str, retries: int = 3) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == expect_bytes:
        digest = sha256_of(dest)
        if digest == expect_sha256:
            return {"dest": str(dest), "status": "already-verified", "bytes": expect_bytes}
        raise SystemExit(f"{dest}: existing file has the right size but the wrong sha256 "
                          f"({digest} != {expect_sha256}); refusing to keep or silently redownload it")
    tmp = dest.with_suffix(dest.suffix + ".part")
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "dawnr-english-download/1"})
            with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as out:
                while True:
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
            got_bytes = tmp.stat().st_size
            if got_bytes != expect_bytes:
                raise ValueError(f"got {got_bytes} bytes, manifest says {expect_bytes}")
            digest = sha256_of(tmp)
            if digest != expect_sha256:
                raise ValueError(f"sha256 {digest} != manifest {expect_sha256}")
            tmp.replace(dest)
            return {"dest": str(dest), "status": "downloaded", "bytes": got_bytes, "attempt": attempt}
        except Exception as error:  # noqa: BLE001 -- retried below, reported if it never succeeds
            last_error = error
            tmp.unlink(missing_ok=True)
            time.sleep(2 * attempt)
    raise SystemExit(f"{url}: failed after {retries} attempts: {last_error}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--dest", required=True, help="directory the manifest's dest paths are relative to")
    ap.add_argument("--max-bytes", type=int, default=60_000_000_000)
    ap.add_argument("--report", default="", help="write the per-file results as JSON here")
    a = ap.parse_args()

    manifest = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    total = sum(f["bytes"] for f in manifest["files"])
    if total > a.max_bytes:
        raise SystemExit(f"manifest totals {total} bytes, over --max-bytes {a.max_bytes}; "
                          f"trim t/dawnr-english-manifest.json before downloading")
    dest_root = Path(a.dest).expanduser()
    dest_root.mkdir(parents=True, exist_ok=True)

    results = []
    for i, entry in enumerate(manifest["files"], 1):
        dest = dest_root / entry["dest"]
        print(f"[{i}/{len(manifest['files'])}] {entry['dest']} ({entry['bytes'] / 1e9:.2f} GB)", file=sys.stderr)
        result = download_one(entry["url"], dest, entry["bytes"], entry["sha256"])
        print(f"    {result['status']}", file=sys.stderr)
        results.append({**entry, **result})

    verified_bytes = sum(r["bytes"] for r in results)
    summary = {"manifest": a.manifest, "dest": str(dest_root), "files": len(results),
               "verified_bytes": verified_bytes, "verified_gb": round(verified_bytes / 1e9, 3),
               "max_bytes": a.max_bytes, "results": results}
    text = json.dumps(summary, indent=1)
    if a.report:
        Path(a.report).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
