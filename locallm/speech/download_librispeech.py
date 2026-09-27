#!/usr/bin/env python3
"""download_librispeech.py — fetch one LibriSpeech split. Run this ON THE LAB
workstation (`t/RUN-NEXT-locallm-r12.md`'s two-machine split applies here
too: downloads and builds are CPU/disk work, not GPU work), not the desktop
-- even the smallest training split, train-clean-100, is 6.3 GB, and
DAWNR-SPEECH.md budgets at most 80 GB total for everything this project
downloads for speech.

LibriSpeech (Panayotov, Chen, Povey & Khudanpur, "LibriSpeech: an ASR corpus
based on public domain audiobooks", ICASSP 2015) is CC BY 4.0, read English
speech from LibriVox, distributed as one .tar.gz per split from OpenSLR
resource 12 (https://www.openslr.org/12, fetched 2026-09-27). The base URL
and every split's official MD5 below were read directly from
https://www.openslr.org/resources/12/md5sum.txt (fetched 2026-09-27); this
script downloads, checks that sum against the file it actually received, and
only then extracts -- a corrupted or partial archive is refused rather than
silently trained on whatever tarfile could still make sense of.

    python3 download_librispeech.py --subset dev-clean          # 337 MB, try this first
    python3 download_librispeech.py --subset train-clean-100    # 6.3 GB, the first real train split

Stdlib only, like get_corpus.py: this is a download-and-extract tool, usable
on a machine that has not set up a training environment at all.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_URL = "https://www.openslr.org/resources/12"
UA = {"User-Agent": "Mozilla/5.0 (dawnr download_librispeech.py)"}
DEFAULT_BUDGET_GB = 80.0  # DAWNR-SPEECH.md: every speech corpus this project keeps, combined

# name -> (official md5, download size in MB), both from openslr.org/resources/12/md5sum.txt
# and openslr.org/12 (fetched 2026-09-27). Sizes are for the budget check, not verification.
SPLITS = {
    "dev-clean":       ("42e2234ba48799c1f50f24a7926300a1", 337),
    "dev-other":       ("c8d0bcc9cca99d4f8b62fcc847357931", 314),
    "test-clean":      ("32fa31d27d2e1cad72775fee3f4849a9", 346),
    "test-other":      ("fb5a50374b501bb3bac4815ee91d3135", 328),
    "train-clean-100": ("2a93770f6d5c6c964bc36631d331a522", 6300),
    "train-clean-360": ("c0e676e450a7ff2f54aeade5171606fa", 23_000),
    "train-other-500": ("d1a0fd59409feb2c614ce4d30c387708", 30_000),
}


def md5sum(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def speech_data_budget_used(speech_root: Path) -> int:
    """Bytes already on disk under the shared speech-data root (the parent
    both download_librispeech.py and download_ljspeech.py write into), so
    the budget check below sees every corpus this project has kept, not just
    the one this run is about to add."""
    if not speech_root.exists():
        return 0
    return sum(f.stat().st_size for f in speech_root.rglob("*") if f.is_file())


def check_budget(speech_root: Path, subset: str, budget_gb: float) -> None:
    used = speech_data_budget_used(speech_root)
    incoming = SPLITS[subset][1] * 1_000_000
    budget = budget_gb * 1_000_000_000
    if used + incoming > budget:
        raise SystemExit(
            f"downloading {subset} (~{incoming / 1e9:.2f} GB) would put {speech_root} "
            f"over the {budget_gb:g} GB speech-data budget (already {used / 1e9:.2f} GB "
            f"there); pass --budget-gb to raise it, or remove a split you no longer need")


def download(subset: str, out: Path) -> Path:
    """Stream to disk with an atomic rename at the end. A cached archive
    whose md5 already matches is reused instead of re-fetched; one that does
    not match is deleted and re-downloaded, never silently kept."""
    out.mkdir(parents=True, exist_ok=True)
    archive = out / f"{subset}.tar.gz"
    expected_md5, _ = SPLITS[subset]
    if archive.exists():
        if md5sum(archive) == expected_md5:
            print(f"  cached and verified: {archive}")
            return archive
        print(f"  {archive} exists but its md5 does not match; re-downloading")
        archive.unlink()

    url = f"{BASE_URL}/{subset}.tar.gz"
    tmp = archive.with_suffix(archive.suffix + ".part")
    request = urllib.request.Request(url, headers=UA)
    started = time.time()
    # 420s, not a shorter default: get_corpus.py's own downloader measured a
    # 169s TLS handshake to a file host before the transfer itself started at
    # several MB/s, and a short timeout would kill that handshake and read as
    # "no internet" -- the wrong diagnosis and the wrong fix.
    with urllib.request.urlopen(request, timeout=420) as response, tmp.open("wb") as handle:
        total = int(response.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            handle.write(chunk)
            got += len(chunk)
            if total:
                speed = got / max(time.time() - started, 1e-9) / 1e6
                print(f"\r  {subset}: {got / 1e6:8.1f} / {total / 1e6:.1f} MB "
                     f"({100 * got / total:5.1f}%)  {speed:5.1f} MB/s", end="", flush=True)
    print()
    tmp.replace(archive)
    return archive


def verify(archive: Path, subset: str) -> None:
    expected_md5, _ = SPLITS[subset]
    actual = md5sum(archive)
    if actual != expected_md5:
        archive.unlink()
        raise SystemExit(
            f"{archive.name}: md5 {actual} does not match the official {expected_md5} "
            f"(openslr.org/resources/12/md5sum.txt) -- deleted rather than extracted")
    print(f"  md5 verified: {actual}")


def extract(archive: Path, out: Path) -> Path:
    # tarfile's "data" extraction filter (Python 3.12+, backported to the
    # 3.9/3.10/3.11 security releases; PEP 706 / CVE-2007-4559) rejects
    # absolute paths and paths that escape `out` before writing anything.
    # Older interpreters have no `filter` argument at all, not even None.
    data_filter = getattr(tarfile, "data_filter", None)
    with tarfile.open(archive) as tar:
        if data_filter is not None:
            tar.extractall(out, filter=data_filter)
        else:
            tar.extractall(out)
    extracted = out / "LibriSpeech" / subset_dir_name(archive)
    print(f"  extracted to {extracted}")
    return extracted


def subset_dir_name(archive: Path) -> str:
    return archive.name.removesuffix(".tar.gz")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--subset", choices=sorted(SPLITS), default="dev-clean",
                        help="default dev-clean: the smallest real split, for trying the "
                             "pipeline before committing to train-clean-100 (6.3 GB)")
    parser.add_argument("--out", type=Path, default=HERE.parent / "corpora" / "speech" / "librispeech",
                        help="default locallm/corpora/speech/librispeech (already gitignored)")
    parser.add_argument("--budget-gb", type=float, default=DEFAULT_BUDGET_GB)
    parser.add_argument("--keep-archive", action="store_true",
                        help="keep the .tar.gz after a verified extraction (default: delete it)")
    args = parser.parse_args(argv)

    check_budget(args.out.parent, args.subset, args.budget_gb)
    archive = download(args.subset, args.out)
    verify(archive, args.subset)
    extract(archive, args.out)
    if not args.keep_archive:
        archive.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
