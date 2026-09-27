#!/usr/bin/env python3
"""download_ljspeech.py — fetch LJSpeech, for the text-to-speech side of
DAWNR-SPEECH.md. Run this ON THE LAB workstation: the archive is 2.6 GB, and
DAWNR-SPEECH.md budgets at most 80 GB total across every speech corpus this
project keeps.

LJSpeech (keithito.com/LJ-Speech-Dataset, fetched 2026-09-27) is public
domain: 13,100 short single-speaker clips of public-domain texts read by the
LibriVox project in 2016-17, already 16-bit PCM WAV at 22050 Hz -- the one
corpus here that needs no format conversion before ``dataset.py`` can read
it. The page publishes no official checksum, so this script's integrity
check is the two facts it does publish and this project can check for
itself: exactly 13,100 rows in ``metadata.csv``, and one ``.wav`` file per
row. A download that landed short or a mirror that changed silently would
show up as a count that does not match, not as a model quietly trained on
however many clips actually arrived.

    python3 download_ljspeech.py --out corpora/speech/ljspeech

Stdlib only, like get_corpus.py and download_librispeech.py.
"""
from __future__ import annotations

import argparse
import csv
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
URL = "https://data.keithito.com/data/speech/LJSpeech-1.1.tar.bz2"
UA = {"User-Agent": "Mozilla/5.0 (dawnr download_ljspeech.py)"}
EXPECTED_CLIPS = 13_100          # keithito.com/LJ-Speech-Dataset, "Total Clips", fetched 2026-09-27
DOWNLOAD_MB = 2_600
DEFAULT_BUDGET_GB = 80.0


def speech_data_budget_used(speech_root: Path) -> int:
    if not speech_root.exists():
        return 0
    return sum(f.stat().st_size for f in speech_root.rglob("*") if f.is_file())


def check_budget(speech_root: Path, budget_gb: float) -> None:
    used = speech_data_budget_used(speech_root)
    incoming = DOWNLOAD_MB * 1_000_000
    budget = budget_gb * 1_000_000_000
    if used + incoming > budget:
        raise SystemExit(
            f"downloading LJSpeech (~{incoming / 1e9:.2f} GB) would put {speech_root} over "
            f"the {budget_gb:g} GB speech-data budget (already {used / 1e9:.2f} GB there)")


def download(out: Path, url: str = URL) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    archive = out / "LJSpeech-1.1.tar.bz2"
    if archive.exists() and archive.stat().st_size > 0:
        print(f"  cached: {archive} ({archive.stat().st_size / 1e6:.1f} MB) -- "
             f"delete it to force a re-download")
        return archive
    tmp = archive.with_suffix(archive.suffix + ".part")
    request = urllib.request.Request(url, headers=UA)
    started = time.time()
    try:
        # 420s: see download_librispeech.py's download() for why this is generous.
        response = urllib.request.urlopen(request, timeout=420)
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise SystemExit(
            f"could not reach {url} ({exc}). keithito.com/LJ-Speech-Dataset publishes the "
            f"current link if this one has moved; pass --url to use a different one.") from exc
    with response, tmp.open("wb") as handle:
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
                print(f"\r  LJSpeech-1.1: {got / 1e6:8.1f} / {total / 1e6:.1f} MB "
                     f"({100 * got / total:5.1f}%)  {speed:5.1f} MB/s", end="", flush=True)
    print()
    tmp.replace(archive)
    return archive


def extract(archive: Path, out: Path) -> Path:
    data_filter = getattr(tarfile, "data_filter", None)
    with tarfile.open(archive) as tar:
        if data_filter is not None:
            tar.extractall(out, filter=data_filter)
        else:
            tar.extractall(out)
    return out / "LJSpeech-1.1"


def verify(root: Path) -> None:
    """The two facts the dataset page publishes instead of a checksum: row
    count and one wav per row (see this file's docstring)."""
    metadata = root / "metadata.csv"
    if not metadata.exists():
        raise SystemExit(f"{root}: no metadata.csv -- extraction did not produce the expected layout")
    with open(metadata, encoding="utf-8") as handle:
        rows = list(csv.reader(handle, delimiter="|"))
    if len(rows) != EXPECTED_CLIPS:
        raise SystemExit(
            f"{metadata}: {len(rows)} rows, expected {EXPECTED_CLIPS} -- "
            f"the download may be incomplete or the dataset version may have changed")
    missing = [r[0] for r in rows if not (root / "wavs" / f"{r[0]}.wav").exists()]
    if missing:
        raise SystemExit(f"{root}: {len(missing)} clip(s) listed in metadata.csv have no .wav "
                         f"file, e.g. {missing[0]}")
    print(f"  verified: {len(rows)} clips, each with its .wav file")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=HERE.parent / "corpora" / "speech" / "ljspeech",
                        help="default locallm/corpora/speech/ljspeech (already gitignored)")
    parser.add_argument("--url", default=URL, help="override if the canonical link has moved")
    parser.add_argument("--budget-gb", type=float, default=DEFAULT_BUDGET_GB)
    parser.add_argument("--keep-archive", action="store_true")
    args = parser.parse_args(argv)

    check_budget(args.out.parent, args.budget_gb)
    archive = download(args.out, args.url)
    root = extract(archive, args.out)
    verify(root)
    if not args.keep_archive:
        archive.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
