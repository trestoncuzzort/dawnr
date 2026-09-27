#!/usr/bin/env python3
"""prepare_manifest.py — a downloaded corpus to the manifest.jsonl dataset.py
reads. Run this ON THE LAB, right after download_librispeech.py or
download_ljspeech.py: LibriSpeech's audio is FLAC, and the only format
conversion in this whole speech track happens here, once, so that
``dataset.py`` (and the model that reads it) never needs an audio codec
library at all -- only the standard library's ``wave`` module for 16-bit PCM.

LibriSpeech (``--corpus librispeech``): each ``<speaker>-<chapter>.trans.txt``
sits beside its ``.flac`` files (torchaudio's LIBRISPEECH dataset docs,
pytorch.org/audio, fetched 2026-09-27, confirm this per-chapter layout); this
walks every ``*.trans.txt`` under ``--root`` rather than assuming a fixed
directory depth, converts each FLAC once with ``ffmpeg`` (already 16 kHz per
openslr.org/12; ``-ar`` is passed anyway as a defensive guarantee, never a
silent assumption) and caches the result, so re-running after adding more
transcripts does not re-encode audio that has not changed.

LJSpeech (``--corpus ljspeech``): already 16-bit PCM WAV at 22050 Hz
(keithito.com/LJ-Speech-Dataset, fetched 2026-09-27) -- no conversion, just
reading ``metadata.csv`` and pointing at the existing ``wavs/``. The third
(normalized) column is used as the transcript, not the second: LJSpeech's own
page documents it as "numbers, ordinals, and monetary units expanded into
full words", and ``text.CTCVocab.normalize`` drops digits outright, so
reading the un-normalized column here would silently turn "1893" into
nothing rather than "eighteen ninety three".

    python3 prepare_manifest.py --corpus librispeech \\
        --root corpora/speech/librispeech/LibriSpeech/dev-clean \\
        --out corpora/speech/librispeech/dev-clean.jsonl
    python3 prepare_manifest.py --corpus ljspeech \\
        --root corpora/speech/ljspeech/LJSpeech-1.1 \\
        --out corpora/speech/ljspeech/manifest.jsonl
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    # run as `python3 locallm/speech/prepare_manifest.py`: import the package's
    # copy of this module and run it (same idiom as dawnr_harness/__main__.py,
    # needed because relative imports below only work once this file is loaded
    # as part of the `speech` package, not as a bare top-level script).
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from speech.prepare_manifest import main as _main
    raise SystemExit(_main())

from .text import CTCVocab  # noqa: E402

HERE = Path(__file__).resolve().parent


def _require_ffmpeg(ffmpeg: str) -> None:
    if shutil.which(ffmpeg) is None:
        raise SystemExit(
            f"'{ffmpeg}' is not on PATH. Install it first (on the lab: "
            f"'sudo apt-get install ffmpeg' or your distribution's equivalent); "
            f"this project does not decode FLAC itself so training stays "
            f"dependency-free (see prepare_manifest.py's module docstring).")


def _convert_flac(src: Path, dst: Path, sample_rate: int, ffmpeg: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [ffmpeg, "-nostdin", "-y", "-loglevel", "error", "-i", str(src),
         "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(dst)],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed on {src}: {result.stderr.strip()}")


def prepare_librispeech(root: Path, out: Path, *, sample_rate: int = 16_000,
                        ffmpeg: str = "ffmpeg", wav_dir: Path | None = None,
                        force: bool = False) -> int:
    if not root.is_dir():
        raise SystemExit(f"{root}: not a directory (did download_librispeech.py finish?)")
    _require_ffmpeg(ffmpeg)
    vocab = CTCVocab()
    wav_dir = wav_dir or out.parent / "wav"
    rows = []
    skipped = 0
    for trans_file in sorted(root.rglob("*.trans.txt")):
        for line in trans_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            uttid, _, transcript = line.partition(" ")
            flac = trans_file.parent / f"{uttid}.flac"
            if not flac.exists():
                skipped += 1
                continue
            text = vocab.normalize(transcript)
            if not text:
                skipped += 1
                continue
            wav = wav_dir / f"{uttid}.wav"
            if force or not wav.exists():
                _convert_flac(flac, wav, sample_rate, ffmpeg)
            rows.append({"audio": str(wav), "text": text})
    _write_manifest(out, rows)
    print(f"  {len(rows)} utterances written to {out}" +
         (f" ({skipped} skipped: missing audio or empty transcript)" if skipped else ""))
    return len(rows)


def prepare_ljspeech(root: Path, out: Path) -> int:
    if not root.is_dir():
        raise SystemExit(f"{root}: not a directory (did download_ljspeech.py finish?)")
    metadata = root / "metadata.csv"
    if not metadata.exists():
        raise SystemExit(f"{metadata}: missing")
    vocab = CTCVocab()
    rows = []
    skipped = 0
    with open(metadata, encoding="utf-8") as handle:
        for fields in csv.reader(handle, delimiter="|", quoting=csv.QUOTE_NONE):
            if len(fields) < 2:
                skipped += 1
                continue
            clip_id = fields[0]
            transcript = fields[2] if len(fields) > 2 else fields[1]  # normalized column preferred
            wav = root / "wavs" / f"{clip_id}.wav"
            text = vocab.normalize(transcript)
            if not wav.exists() or not text:
                skipped += 1
                continue
            rows.append({"audio": str(wav), "text": text})
    _write_manifest(out, rows)
    print(f"  {len(rows)} utterances written to {out}" +
         (f" ({skipped} skipped)" if skipped else ""))
    return len(rows)


def _write_manifest(out: Path, rows: list[dict]) -> None:
    if not rows:
        raise SystemExit("no utterances found; nothing written")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", choices=("librispeech", "ljspeech"), required=True)
    parser.add_argument("--root", type=Path, required=True,
                        help="the extracted corpus directory (see the examples above)")
    parser.add_argument("--out", type=Path, required=True, help="manifest.jsonl to write")
    parser.add_argument("--sample-rate", type=int, default=16_000,
                        help="LibriSpeech only; LJSpeech keeps its native 22050 Hz")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--force", action="store_true",
                        help="LibriSpeech only: re-convert audio even where a .wav already exists")
    args = parser.parse_args(argv)

    if args.corpus == "librispeech":
        prepare_librispeech(args.root, args.out, sample_rate=args.sample_rate,
                           ffmpeg=args.ffmpeg, force=args.force)
    else:
        prepare_ljspeech(args.root, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
